"""Post-skill-edit lifecycle hook — ``post_skill_edit``.

Closes D-S-4 + D-S-5 from `.local/research/v9.5.0_gap_analysis.md` §3.1.
Implements the **DEEP integration** path signed off as user Q2=B for the
v9.5.0 cycle: the Si-Chip iteration_delta gate fires automatically after
any commit touching ``workflow-system/agent/**``, gated on the
``DEVOLAFLOW_SI_CHIP_DEEP=1`` opt-in env flag.

Bound to the ``post_skill_edit`` event by
:mod:`devolaflow.lifecycle.__init__`. Fires AFTER the v9.4.0 PV-02
``pre_plugin_invocation`` slot at DEFAULT_EVENTS position 10 per A-2.2
append-only invariant.

Behaviour contract (R5 strict):

1. **Gate 1 (env-flag OFF)** — if ``DEVOLAFLOW_SI_CHIP_DEEP`` is
   unset or anything other than the literal string ``"1"``, the
   handler returns an empty :class:`HookResult` with zero filesystem
   IO AND zero subprocess work AND zero lazy-imports of the
   :mod:`devolaflow.si_chip_bridge` package. This is the
   byte-identical no-op invariant: every dispatch path that does NOT
   opt-in MUST produce identical bytes to v9.4.0 behaviour.

   Per Workflow Rule W-20 (env-flag reuse-first analysed in
   `.local/research/v9.5.0_gap_analysis.md` §3.2 D-S-5), this flag
   is a NEW flag (orthogonal to existing ``DEVOLAFLOW_AUTO_INSTALL``,
   ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS``, ``DEVOLAFLOW_AGENT_WORKSPACE``)
   — see :file:`workflow-system/agent/references/env-flags.md` §2.14
   for the full orthogonality argument.

2. **Gate 2 (no skill files in payload)** — if the payload's
   ``touched_files`` (or ``files_changed``) list contains zero entries
   under ``workflow-system/agent/``, the handler returns an empty
   :class:`HookResult`. A commit that doesn't touch the skill corpus
   has nothing for Si-Chip to evaluate; silent no-op is the correct
   behaviour (NOT an error).

3. **Action (both gates open)** — for the touched skill file, lazy-
   imports :mod:`devolaflow.si_chip_bridge` and calls
   :func:`run_dogfood_cycle`. The verdict (APPLY / DEFER) is captured
   in the :class:`HookResult` metadata. When the verdict is DEFER,
   the handler ALSO writes a deferred-changes feedback doc to
   ``.local/feedbacks/`` (the canonical operator-visible feedback
   surface telegraphed in the v9.5.0 user requirement).

S-5 compliance (no silent failures): every failure mode is surfaced
through a typed :class:`HookViolation`:

* ``PSE001`` (severity ``warning``) — Si-Chip not installed (resolver
  returned None). DEEP integration is gracefully degraded; the
  handler returns a WARNING-level violation but does NOT block the
  dispatch. CI environments without network access typically lack
  Si-Chip and would hit this case on every commit.
* ``PSE002`` (severity ``error``) — Si-Chip installed but the
  subprocess invocation failed (e.g. malformed Si-Chip output or
  non-zero exit). The error details carry the verbatim Si-Chip
  stderr per S-5.

In permissive mode the handler NEVER crashes the dispatch — failures
are aggregated into the result envelope and emitted via WARNING-level
logs by :func:`finalize`. The dispatcher receives the populated
:class:`HookResult` and may inspect ``result.violations`` to surface
the Si-Chip evaluation summary in the operator UI.

A genuinely unexpected exception (e.g. ``OSError`` on disk full) is
logged at WARNING via the lifecycle logger AND re-raised — the
handler never silently swallows non-domain exceptions.

Lazy import of :mod:`devolaflow.si_chip_bridge` keeps this module
import-light: the lifecycle package import path does NOT pull in the
~1070-LOC bridge package unless the env-flag is ON AND the payload
carries skill-corpus touches.

Source: v9.5.0 PV-04 (cycle plan §3 Phase 3, user Q2=B DEEP signoff).
External tool reference: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT: str = "post_skill_edit"
ENV_FLAG: str = "DEVOLAFLOW_SI_CHIP_DEEP"
ENV_FLAG_TRUTHY: str = "1"

# Skill-corpus file prefix — touches under this path trigger the hook.
# Mirrors `runtime-plugins.yaml#plugins[*].invoked_by_workflows` in spirit:
# the v9.5.0 PV-03 templates declare si-chip for skill-optimization +
# self-update + nines-assisted; this hook is the cross-cutting catch-all
# for any direct skill-corpus edit (commits made outside those workflows).
SKILL_CORPUS_PREFIX: str = "workflow-system/agent/"

# Default ability name for DevolaFlow's own skill corpus (the dogfood pass).
DEFAULT_ABILITY: str = "devola-flow"

# Where the deferred-changes feedback doc lands when verdict == DEFER.
# Operators review this folder for Si-Chip suggestions that didn't clear
# the +0.10 spec §23 threshold. Per the v9.5.0 user requirement: "if not,
# I want you to summarise into a feedback document."
FEEDBACK_DIR_DEFAULT: Path = Path(".local") / "feedbacks"

logger = logging.getLogger(__name__)


def is_deep_integration_active() -> bool:
    """Return ``True`` iff ``DEVOLAFLOW_SI_CHIP_DEEP`` is exactly ``"1"``.

    R5 strict — rejects ``"true"`` / ``"yes"`` / ``"on"`` / ``"01"`` /
    ``"1\\n"`` / ``""`` / unset. Pure ``os.environ.get`` comparison; no
    file IO, no subprocess, no ``shutil.which`` lookup. Codified by
    :func:`tests.test_post_skill_edit_hook.test_disabled_is_noop_byte_identical`.

    The strict literal-only matching mirrors the v8.3.2 PV-02 RTK
    proxy contract (``DEVOLAFLOW_RTK_PROXY``), the v8.3.3 PV-03 memory
    router contract (``DEVOLAFLOW_MEMORY_ROUTER``), the v9.3.0 PV-06
    simple-shortcut contract (``DEVOLAFLOW_SIMPLE_SHORTCUT``), and the
    v9.4.0 PV-02 plugin auto-install contract
    (``DEVOLAFLOW_AUTO_INSTALL_PLUGINS``).
    """
    return os.environ.get(ENV_FLAG, "") == ENV_FLAG_TRUTHY


def _extract_skill_files(payload: dict[str, Any]) -> list[str]:
    """Return the subset of touched files that fall under the skill corpus.

    Looks at two payload conventions:
    * ``payload["touched_files"]`` — the v9.5.0 PV-04 canonical key.
    * ``payload["files_changed"]`` — the v8.x legacy key still used by
      some templates. Either form is accepted to avoid forcing every
      caller to migrate.

    Returns an empty list when the payload contains neither key OR when
    no entries fall under :data:`SKILL_CORPUS_PREFIX`. The empty list
    is the byte-stable signal for "no skill-corpus edit; silent no-op".
    """
    raw = payload.get("touched_files") or payload.get("files_changed") or []
    if not isinstance(raw, list):
        return []
    matches: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        # Normalise leading "./" so both "./workflow-system/agent/..." and
        # "workflow-system/agent/..." match.
        normalised = entry[2:] if entry.startswith("./") else entry
        if normalised.startswith(SKILL_CORPUS_PREFIX):
            matches.append(normalised)
    return matches


def _write_feedback_doc(
    feedback_dir: Path,
    skill_files: list[str],
    notes: list[str],
    install_source: str | None,
    verdict: str,
) -> Path:
    """Write the DEFER feedback doc to ``feedback_dir``; return path.

    Per the v9.5.0 user requirement: "if not, I want you to summarise
    into a feedback document". This is the operator-visible deferred-
    changes record. The doc is append-only (per S-9 spirit) — repeated
    DEFERS for the same skill files accumulate in dated entries.
    """
    feedback_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = feedback_dir / f"sichip_deferred_{timestamp}.md"
    body_lines = [
        f"# Si-Chip DEEP Integration — Deferred Verdict ({timestamp})",
        "",
        "**Source:** `devolaflow.lifecycle.post_skill_edit` hook (v9.5.0 PV-04 DEEP integration).",
        f"**Install source:** `{install_source or 'unavailable'}`",
        f"**Verdict:** `{verdict}`",
        "",
        "## Touched skill files",
        "",
    ]
    body_lines.extend(f"- `{f}`" for f in skill_files)
    body_lines.append("")
    body_lines.append("## Si-Chip run notes (verbatim)")
    body_lines.append("")
    body_lines.extend(f"- {n}" for n in notes)
    body_lines.append("")
    body_lines.append("## Action recommendation")
    body_lines.append("")
    body_lines.append(
        "Review the iteration_delta scores. Re-run with extra optimisation "
        "candidates OR accept that the proposed change is sub-threshold "
        "AND defer to a future cycle. Per the v9.5.0 user requirement, "
        "DO NOT auto-apply changes that score below +0.10."
    )
    out_path.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    logger.info("post_skill_edit: wrote deferred-changes feedback doc to %s", out_path)
    return out_path


def post_skill_edit(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Run the Si-Chip iteration_delta gate after a SKILL-touching commit.

    See module docstring for the full contract. Returns a
    :class:`HookResult` in both modes. Strict mode re-raises the
    top-severity :class:`HookViolation` aggregated across the
    Si-Chip evaluation; permissive mode aggregates them on the result
    envelope and emits WARNING logs via :func:`finalize` without
    raising.

    The payload schema is intentionally minimal — the dispatcher /
    git-hook adapter is responsible for populating ``touched_files``
    from the post-commit file list. Tests can invoke the hook
    directly with ``{"touched_files": ["workflow-system/agent/SKILL.md"]}``.
    """
    if not is_deep_integration_active():
        return finalize(EVENT, [], strict=strict)

    if not isinstance(payload, dict):
        return finalize(EVENT, [], strict=strict)

    skill_files = _extract_skill_files(payload)
    if not skill_files:
        return finalize(EVENT, [], strict=strict)

    # Lazy-import — keep the lifecycle package import-light when env flag is
    # off OR the payload has no skill-corpus touches (the common dispatch shape).
    from devolaflow.si_chip_bridge import (
        ApplyVerdict,
        SiChipError,
        SiChipUnavailable,
        run_dogfood_cycle,
    )

    ability_name = str(payload.get("ability_name") or DEFAULT_ABILITY)
    feedback_dir = Path(payload.get("feedback_dir") or FEEDBACK_DIR_DEFAULT)
    threshold = float(payload.get("threshold") or 0.10)

    violations: list[HookViolation] = []
    metadata: dict[str, Any] = {
        "skill_files": skill_files,
        "ability_name": ability_name,
        "threshold": threshold,
    }

    # Evaluate the FIRST touched skill file — the post-commit hook fires
    # once per commit and the skill-corpus edit pattern typically touches
    # a single primary file (SKILL.md or a single reference). Multi-file
    # batch evaluation is a v9.7.0 candidate per gap analysis §5.
    primary_skill = Path(skill_files[0])
    try:
        result = run_dogfood_cycle(
            ability_name=ability_name,
            skill_md=primary_skill,
            threshold=threshold,
        )
    except SiChipUnavailable as exc:
        install_hint = (
            "curl -fsSL https://yorha-agents.github.io/Si-Chip/install.sh "
            "| bash -s -- --target cursor --scope global --yes"
        )
        logger.warning(
            "post_skill_edit: Si-Chip not installed; DEEP integration "
            "skipped for %r. Install with: %s",
            primary_skill,
            install_hint,
        )
        violations.append(
            HookViolation(
                code="PSE001",
                message=(
                    "post_skill_edit: Si-Chip not installed; DEEP integration "
                    f"skipped for {primary_skill} — {exc}"
                ),
                severity="warning",
                context={
                    "primary_skill": str(primary_skill),
                    "skill_files": skill_files,
                    "canonical_url": "https://github.com/YoRHa-Agents/Si-Chip",
                },
            )
        )
        result_envelope = finalize(EVENT, violations, strict=strict)
        result_envelope.metadata.update(metadata)
        result_envelope.metadata["verdict"] = "SKIPPED_PERMISSIVE"
        return result_envelope
    except SiChipError as exc:
        logger.warning(
            "post_skill_edit: Si-Chip subprocess failed for %r: %s",
            primary_skill,
            exc,
        )
        violations.append(
            HookViolation(
                code="PSE002",
                message=(f"post_skill_edit: Si-Chip subprocess failed for {primary_skill}: {exc}"),
                severity="error",
                context={
                    "primary_skill": str(primary_skill),
                    "skill_files": skill_files,
                    "exception_type": type(exc).__name__,
                    "details": getattr(exc, "details", {}),
                },
            )
        )
        result_envelope = finalize(EVENT, violations, strict=strict)
        result_envelope.metadata.update(metadata)
        result_envelope.metadata["verdict"] = "ERROR"
        return result_envelope
    except Exception:
        logger.warning(
            "post_skill_edit: unexpected exception evaluating %r "
            "(re-raising per S-5 no-silent-failure)",
            primary_skill,
            exc_info=True,
        )
        raise

    # Si-Chip ran cleanly — capture the verdict + delta in metadata.
    metadata["verdict"] = result.verdict.value
    metadata["install_source"] = result.install_source
    metadata["notes"] = result.notes
    if result.delta is not None:
        metadata["iteration_delta"] = result.delta.iteration_delta

    if result.verdict == ApplyVerdict.DEFER:
        # Per the v9.5.0 user requirement, write the deferred-changes
        # feedback doc; reviewers consume this file at PV-05 cycle close.
        try:
            feedback_path = _write_feedback_doc(
                feedback_dir,
                skill_files,
                result.notes,
                result.install_source,
                result.verdict.value,
            )
        except OSError:
            logger.warning(
                "post_skill_edit: feedback dir write failed for %r (re-raising per S-5)",
                feedback_dir,
                exc_info=True,
            )
            raise
        metadata["feedback_doc"] = str(feedback_path)
        logger.info(
            "post_skill_edit: DEFER verdict for %r (delta=%s); feedback doc at %s",
            primary_skill,
            metadata.get("iteration_delta"),
            feedback_path,
        )
    else:
        logger.info(
            "post_skill_edit: APPLY verdict for %r (delta=%s)",
            primary_skill,
            metadata.get("iteration_delta"),
        )

    result_envelope = finalize(EVENT, violations, strict=strict)
    result_envelope.metadata.update(metadata)
    return result_envelope


def metadata_to_json(result: HookResult) -> str:
    """Serialise the HookResult.metadata to JSON (for logging surfaces).

    Convenience helper used by the v9.5.0 PV-05 dogfood pass + by
    operators tailing the lifecycle log. Returns a single-line JSON
    string with sorted keys (deterministic across runs).
    """
    return json.dumps(result.metadata, sort_keys=True, default=str)


__all__ = [
    "DEFAULT_ABILITY",
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "EVENT",
    "FEEDBACK_DIR_DEFAULT",
    "SKILL_CORPUS_PREFIX",
    "is_deep_integration_active",
    "metadata_to_json",
    "post_skill_edit",
]
