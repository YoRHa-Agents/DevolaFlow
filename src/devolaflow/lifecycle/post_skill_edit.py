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
   the handler ALSO writes a deferred-changes feedback doc to the
   PRIVATE agent tree ``.local/.agent/sichip-deferred/`` (relocated in
   v14.0.0 ADR-8 / design §5b out of the human-facing
   ``.local/feedbacks/`` — these docs are AGENT output, not
   human-authored feedback). On first run the writer performs a
   one-time best-effort migration of any legacy
   ``sichip_deferred_*.md`` docs + the
   ``.sichip_deferred_fingerprints.txt`` sidecar from the old location
   (preserving the dedup set) and dual-reads the legacy location during
   the transition window so a pre-relocation fingerprint still
   suppresses a duplicate.

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

import hashlib
import json
import logging
import os
import shutil
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
#
# v14.0.0 ADR-8 / design §5b — RELOCATED from the human-facing
# ``.local/feedbacks/`` into the PRIVATE agent tree
# ``.local/.agent/sichip-deferred/``. These docs are AGENT output (the
# Si-Chip dogfood pass authored them), NOT human-authored feedback, so they
# polluted the human surface. They are NOT moved under ``.local/human/``
# either — that tree is reserved for human INPUT / agent-draft OUTPUT (design
# §5b). The injectable ``feedback_dir`` payload key still overrides this
# default (e.g. tests pass a tmp dir); the path is NOT hardcoded downstream.
FEEDBACK_DIR_DEFAULT: Path = Path(".local") / ".agent" / "sichip-deferred"

# v14.0.0 ADR-8 — the LEGACY default location (pre-relocation). When the
# default new dir is in use, the writer performs a one-time best-effort
# migration of any ``sichip_deferred_*.md`` docs + the
# ``.sichip_deferred_fingerprints.txt`` sidecar from here into
# FEEDBACK_DIR_DEFAULT (preserving the dedup set verbatim, F-5), and — as a
# transition-window safety-net — dual-reads this location for dedup
# fingerprints so a pre-relocation fingerprint still suppresses a duplicate
# DEFER doc. Relative path per S-2.
LEGACY_FEEDBACK_DIR_DEFAULT: Path = Path(".local") / "feedbacks"

# v10.2.1 PV-02 D-S-5 — DEFER doc dedupe sidecar. Closes the gap from
# `.local/research/v10.2.0_gap_analysis.md` §3.2 D-S-5: with DEEP integration
# always-on (`DEVOLAFLOW_SI_CHIP_DEEP=1`), every skill-corpus commit produced
# a NEW feedback doc even when (skill_files, verdict, notes) were identical
# to a prior write — `.local/feedbacks/` would fill with low-information
# DEFER timestamps over time.
#
# Design choice: append-only sidecar file (NOT per-doc embedded fingerprints)
# because:
#   1. Cheaper read path — one open() instead of N for the directory walk.
#   2. Append-only matches S-9 envelope contract semantics (no rewrites of
#      historical docs).
#   3. Avoids polluting the operator-facing markdown with HTML comments /
#      YAML frontmatter that would distract reviewers.
#
# The fingerprint set is the SHA-256 hash of a deterministic JSON
# serialisation of (sorted skill_files, verdict, sorted notes). When the
# fingerprint is already on disk, the new doc write is SKIPPED and the
# helper returns the prior doc path (located via filesystem glob).
FINGERPRINT_SIDECAR_NAME: str = ".sichip_deferred_fingerprints.txt"

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


def _compute_fingerprint(
    skill_files: list[str],
    verdict: str,
    notes: list[str],
) -> str:
    """Compute a deterministic SHA-256 fingerprint of DEFER content.

    Idiomatic helper introduced in v10.2.3 PV-04 alongside the parent-
    function CC reduction (NineS PV-03 deep-analysis row #7,
    `post_skill_edit` CC=13). Argument order (skill_files, verdict,
    notes) matches the natural English reading order ("for these
    skill_files and this verdict, hash these notes").

    The fingerprint is content-based (not timestamp-based) so two
    DEFER writes with the same ``(skill_files, verdict, notes)``
    produce the same hex digest regardless of when they fire.

    Sort order: ``skill_files`` and ``notes`` are sorted before hashing
    so that callers reordering a list (e.g. set→list conversion that
    yields different orderings across Python sessions) still hash to
    the same fingerprint. ``verdict`` is included verbatim so an
    ``APPLY`` doc never collides with a ``DEFER`` doc on otherwise
    identical inputs.
    """
    payload = {
        "skill_files": sorted(skill_files),
        "notes": sorted(notes),
        "verdict": verdict,
    }
    serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _compute_defer_fingerprint(
    skill_files: list[str],
    notes: list[str],
    verdict: str,
) -> str:
    """Backward-compat wrapper around :func:`_compute_fingerprint`.

    Original signature from v10.2.1 PV-02 D-S-5 closure: ``(skill_files,
    notes, verdict)``. The v10.2.3 PV-04 idiomatic helper reorders to
    ``(skill_files, verdict, notes)`` to match natural reading order;
    this thin wrapper keeps the v10.2.1 callers (e.g.
    `tests/test_sichip_dedup_feedback_doc.py`) working byte-identically.

    DO NOT remove without first migrating every caller — the public-
    private boundary here is that this helper has at least one in-tree
    test caller per `tests/test_sichip_dedup_feedback_doc.py`.
    """
    return _compute_fingerprint(skill_files, verdict, notes)


def _read_sidecar_fingerprints(feedback_dir: Path) -> set[str]:
    """Return the fingerprint set recorded in ``feedback_dir``'s sidecar.

    Single-directory read — the original :func:`_load_existing_fingerprints`
    body, extracted in v14.0.0 ADR-8 so the dual-read orchestrator can reuse
    it per location. Returns an empty set when the sidecar file does not yet
    exist or cannot be read (per S-5 the OSError is logged at WARNING but does
    NOT raise — a missing sidecar simply means no prior fingerprint state
    exists, which is the fresh-clone case).
    """
    sidecar_path = feedback_dir / FINGERPRINT_SIDECAR_NAME
    if not sidecar_path.is_file():
        return set()
    try:
        text = sidecar_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "post_skill_edit: cannot read fingerprint sidecar %s: %s; "
            "treating as empty (will write fresh)",
            sidecar_path,
            exc,
        )
        return set()
    return {line.strip() for line in text.splitlines() if line.strip()}


def _load_existing_fingerprints(
    feedback_dir: Path,
    *,
    legacy_feedback_dir: Path | None = None,
) -> set[str]:
    """Return the fingerprints recorded for ``feedback_dir`` (dual-read aware).

    Idiomatic helper introduced in v10.2.3 PV-04 to match the
    `_compute_fingerprint` naming pattern. Reads the new-location sidecar;
    when ``legacy_feedback_dir`` is supplied (and distinct), v14.0.0 ADR-8
    ALSO unions in the legacy-location sidecar — the transition-window
    dual-read (design §5b / F-5) so a fingerprint recorded before the
    relocation still suppresses a duplicate DEFER doc afterwards, even if the
    one-time migration has not yet folded the legacy sidecar in.

    With ``legacy_feedback_dir=None`` (the default) the behaviour is
    byte-identical to the pre-v14.0.0 single-directory read.
    """
    fingerprints = _read_sidecar_fingerprints(feedback_dir)
    if legacy_feedback_dir is not None and legacy_feedback_dir != feedback_dir:
        fingerprints |= _read_sidecar_fingerprints(legacy_feedback_dir)
    return fingerprints


def _read_fingerprint_sidecar(feedback_dir: Path) -> set[str]:
    """Backward-compat alias for :func:`_load_existing_fingerprints`.

    Preserved for any out-of-tree callers that imported the v10.2.1
    name. New code should prefer :func:`_load_existing_fingerprints`.
    """
    return _load_existing_fingerprints(feedback_dir)


def _scan_dir_for_fingerprint(
    directory: Path,
    marker: str,
    fingerprint: str,
) -> Path | None:
    """Return the first ``sichip_deferred_*.md`` in ``directory`` with ``marker``.

    Cheap O(N) substring scan over the doc count (not a full YAML parse).
    Per S-5 an unreadable doc is logged at WARNING and skipped, never raised.
    """
    if not directory.is_dir():
        return None
    for entry in sorted(directory.glob("sichip_deferred_*.md")):
        try:
            text = entry.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "post_skill_edit: cannot read prior DEFER doc %s while "
                "scanning for fingerprint %s: %s",
                entry,
                fingerprint,
                exc,
            )
            continue
        if marker in text:
            return entry
    return None


def _find_existing_doc_for_fingerprint(
    feedback_dir: Path,
    fingerprint: str,
    *,
    legacy_feedback_dir: Path | None = None,
) -> Path | None:
    """Locate the prior DEFER doc carrying ``fingerprint`` (best-effort).

    Scans ``feedback_dir`` for the doc whose body embeds the fingerprint
    marker (written by :func:`_write_feedback_doc` as a single HTML comment
    line near the top). v14.0.0 ADR-8: when ``legacy_feedback_dir`` is
    supplied (and distinct) and the doc is not found in the new dir, ALSO
    scans the legacy location — so a duplicate is suppressed with the correct
    prior path even if the one-time migration's doc-move step has not yet run
    (transition-window dual-read, design §5b / F-5).

    Returns ``None`` when no prior doc carries the fingerprint — the
    sidecar may have an entry that predates the marker convention OR
    the corresponding doc was manually deleted.
    """
    marker = f"<!-- sichip_fingerprint:{fingerprint} -->"
    found = _scan_dir_for_fingerprint(feedback_dir, marker, fingerprint)
    if found is not None:
        return found
    if legacy_feedback_dir is not None and legacy_feedback_dir != feedback_dir:
        return _scan_dir_for_fingerprint(legacy_feedback_dir, marker, fingerprint)
    return None


def _append_fingerprint_sidecar(feedback_dir: Path, fingerprint: str) -> None:
    """Append ``fingerprint`` to the sidecar; loud on OSError per S-5."""
    sidecar_path = feedback_dir / FINGERPRINT_SIDECAR_NAME
    with sidecar_path.open("a", encoding="utf-8") as fh:
        fh.write(fingerprint + "\n")


def _migrate_legacy_sidecar(legacy_dir: Path, new_dir: Path) -> list[str]:
    """Union the legacy fingerprint sidecar into ``new_dir``'s, then drop legacy.

    Preserves the dedup set verbatim (F-5): the legacy fingerprints are
    merged with any already present in ``new_dir`` and rewritten (sorted, so
    the result is deterministic) to ``new_dir``'s sidecar; the legacy sidecar
    is then removed so a re-run is a no-op (idempotent). Returns a one-element
    issues list on OSError (also logged at WARNING per S-5), else ``[]``.
    """
    legacy_sidecar = legacy_dir / FINGERPRINT_SIDECAR_NAME
    if not legacy_sidecar.is_file():
        return []
    try:
        merged = _read_sidecar_fingerprints(new_dir) | _read_sidecar_fingerprints(legacy_dir)
        if merged:
            new_sidecar = new_dir / FINGERPRINT_SIDECAR_NAME
            new_sidecar.write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")
        legacy_sidecar.unlink()
    except OSError as exc:
        logger.warning(
            "post_skill_edit: failed migrating legacy fingerprint sidecar %s into %s: %s",
            legacy_sidecar,
            new_dir,
            exc,
        )
        return [f"sidecar {legacy_sidecar}: {exc}"]
    logger.info("post_skill_edit: migrated legacy fingerprint sidecar into %s", new_dir)
    return []


def _migrate_legacy_docs(legacy_dir: Path, new_dir: Path) -> list[str]:
    """Move every legacy ``sichip_deferred_*.md`` doc into ``new_dir`` (best-effort).

    Already-migrated docs (target name present in ``new_dir``) have their
    stale legacy copy removed so re-runs converge (the timestamp+fingerprint
    name guarantees same-name == same logical doc). Per S-5 each per-file
    failure is logged at WARNING AND appended to the returned issues list;
    the loop continues with the remaining docs rather than aborting.
    """
    issues: list[str] = []
    try:
        legacy_docs = sorted(legacy_dir.glob("sichip_deferred_*.md"))
    except OSError as exc:
        logger.warning("post_skill_edit: cannot list legacy DEFER docs in %s: %s", legacy_dir, exc)
        return [f"glob {legacy_dir}: {exc}"]
    for doc in legacy_docs:
        target = new_dir / doc.name
        try:
            if target.exists():
                doc.unlink()
            else:
                shutil.move(str(doc), str(target))
        except OSError as exc:
            logger.warning(
                "post_skill_edit: failed migrating legacy DEFER doc %s into %s: %s",
                doc,
                target,
                exc,
            )
            issues.append(f"move {doc}: {exc}")
    if legacy_docs and not issues:
        logger.info(
            "post_skill_edit: migrated %d legacy DEFER doc(s) into %s",
            len(legacy_docs),
            new_dir,
        )
    return issues


def _migrate_legacy_feedback_dir(legacy_dir: Path, new_dir: Path) -> list[str]:
    """One-time best-effort move of legacy DEFER docs + sidecar into ``new_dir``.

    v14.0.0 ADR-8 / design §5b (F-5). Relocates every ``sichip_deferred_*.md``
    doc AND the ``.sichip_deferred_fingerprints.txt`` sidecar from the legacy
    ``.local/feedbacks/`` location into the new private agent tree, PRESERVING
    the dedup fingerprint set verbatim (the legacy sidecar is unioned into the
    new sidecar, never dropped).

    Idempotent: after a successful migration the legacy docs + sidecar are
    gone, so a re-run finds nothing to move and returns ``[]``.

    S-5 (no silent failure): every failure is logged at WARNING AND surfaced
    in the returned issues list; the migration continues best-effort rather
    than aborting. Returns the list of human-readable issue strings
    (empty == fully clean).
    """
    try:
        legacy_is_dir = legacy_dir.is_dir()
    except OSError as exc:
        logger.warning("post_skill_edit: cannot stat legacy feedback dir %s: %s", legacy_dir, exc)
        return [f"stat {legacy_dir}: {exc}"]
    if not legacy_is_dir:
        return []

    try:
        new_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("post_skill_edit: cannot create relocation target %s: %s", new_dir, exc)
        return [f"mkdir {new_dir}: {exc}"]

    issues = _migrate_legacy_sidecar(legacy_dir, new_dir)
    issues.extend(_migrate_legacy_docs(legacy_dir, new_dir))
    return issues


def _write_feedback_doc(
    feedback_dir: Path,
    skill_files: list[str],
    notes: list[str],
    install_source: str | None,
    verdict: str,
    *,
    legacy_feedback_dir: Path | None = None,
) -> Path:
    """Write the DEFER feedback doc to ``feedback_dir``; return path.

    Per the v9.5.0 user requirement: "if not, I want you to summarise
    into a feedback document". This is the operator-visible deferred-
    changes record.

    v14.0.0 ADR-8 (design §5b / F-5): when ``legacy_feedback_dir`` is
    supplied (and distinct from ``feedback_dir``), a one-time best-effort
    migration FIRST relocates any legacy ``sichip_deferred_*.md`` docs + the
    fingerprint sidecar into ``feedback_dir`` (preserving the dedup set), and
    the dedup check dual-reads the legacy location so a pre-relocation
    fingerprint still suppresses a duplicate. With ``legacy_feedback_dir=None``
    (the default) the behaviour is byte-identical to the pre-v14.0.0
    single-directory writer.

    v10.2.1 PV-02 (D-S-5 closure) adds content-based deduplication: a
    SHA-256 fingerprint of ``(sorted(skill_files), sorted(notes), verdict)``
    is computed via :func:`_compute_defer_fingerprint`. The fingerprint
    is checked against an append-only sidecar at
    ``<feedback_dir>/.sichip_deferred_fingerprints.txt``:

    * **Fingerprint already in sidecar** — locate the prior doc via the
      embedded HTML-comment marker and return its path WITHOUT writing
      a new file. Idempotent: the same inputs always resolve to the
      same path.
    * **Fingerprint absent** — write a new dated doc with the
      fingerprint marker embedded as ``<!-- sichip_fingerprint:HEX -->``
      on line 2. Then append the fingerprint to the sidecar. Both
      operations are loud-on-OSError per S-5.

    The sidecar design (vs per-doc fingerprint scanning) keeps the
    common case (no duplicates → write fresh) at one O(1) sidecar read
    + one O(1) append; the dedup case (duplicate detected) costs an
    additional O(N) directory scan to locate the prior path. For the
    expected operating pattern (most commits produce a unique
    fingerprint, occasional duplicate suppressed) this is the cheaper
    shape than per-doc scanning every write.
    """
    feedback_dir.mkdir(parents=True, exist_ok=True)
    if legacy_feedback_dir is not None and legacy_feedback_dir != feedback_dir:
        migration_issues = _migrate_legacy_feedback_dir(legacy_feedback_dir, feedback_dir)
        if migration_issues:
            logger.warning(
                "post_skill_edit: legacy feedback migration completed with %d issue(s): %s",
                len(migration_issues),
                "; ".join(migration_issues),
            )
    fingerprint = _compute_fingerprint(skill_files, verdict, notes)
    known = _load_existing_fingerprints(feedback_dir, legacy_feedback_dir=legacy_feedback_dir)
    if fingerprint in known:
        prior = _find_existing_doc_for_fingerprint(
            feedback_dir, fingerprint, legacy_feedback_dir=legacy_feedback_dir
        )
        if prior is not None:
            logger.info(
                "post_skill_edit: DEFER fingerprint %s already on disk; "
                "skipping duplicate write — prior doc at %s",
                fingerprint[:12],
                prior,
            )
            return prior
        # Fingerprint in sidecar but no doc carries the marker — could be a
        # manually-deleted doc OR a sidecar entry that predates the marker
        # convention. Fall through to write a fresh doc; the fingerprint
        # already in the sidecar is harmless (set semantics).
        logger.info(
            "post_skill_edit: fingerprint %s in sidecar but no doc found; writing fresh doc",
            fingerprint[:12],
        )

    # Microsecond precision avoids collisions for distinct fingerprints
    # written within the same second (the dedupe contract demands distinct
    # paths; timestamp granularity must therefore be sub-second).
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    out_path = feedback_dir / f"sichip_deferred_{timestamp}.md"
    body_lines = [
        f"# Si-Chip DEEP Integration — Deferred Verdict ({timestamp})",
        f"<!-- sichip_fingerprint:{fingerprint} -->",
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
    _append_fingerprint_sidecar(feedback_dir, fingerprint)
    logger.info("post_skill_edit: wrote deferred-changes feedback doc to %s", out_path)
    return out_path


def _run_si_chip_evaluation(
    primary_skill: Path,
    skill_files: list[str],
    ability_name: str,
    threshold: float,
) -> tuple[Any, list[HookViolation], str | None]:
    """Run :func:`run_dogfood_cycle` and classify the outcome.

    Helper extracted in v10.2.3 PV-04 to address the NineS PV-03 deep-
    analysis finding at
    `.local/research/v10.2.2_nines.md` §2 row #7 (CC=13 in
    :func:`post_skill_edit`). The parent function's three exception
    branches (SiChipUnavailable / SiChipError / unexpected) plus the
    success path were the dominant complexity contributors; pulling
    them into this orchestrator drops the parent below the warn
    threshold.

    Returns ``(result, violations, terminal_verdict)``:

    * ``result`` — the :class:`SiChipResult` on the success path; ``None``
      when an exception fired.
    * ``violations`` — at most ONE typed :class:`HookViolation` capturing
      the exception (PSE001 for SiChipUnavailable / PSE002 for SiChipError);
      empty on the success path.
    * ``terminal_verdict`` — when set ("SKIPPED_PERMISSIVE" / "ERROR"),
      the parent MUST set ``metadata["verdict"]`` to this string and
      return WITHOUT calling ``_write_feedback_doc``. ``None`` on the
      success path tells the parent to continue with the verdict-based
      branching.

    Per S-5: domain exceptions (SiChipUnavailable / SiChipError) become
    typed violations; any OTHER exception logs at WARNING and is
    RE-RAISED — the helper never silently swallows non-domain failures.
    """
    from devolaflow.si_chip_bridge import (
        SiChipError,
        SiChipUnavailable,
        run_dogfood_cycle,
    )

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
        violation = HookViolation(
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
        return None, [violation], "SKIPPED_PERMISSIVE"
    except SiChipError as exc:
        logger.warning(
            "post_skill_edit: Si-Chip subprocess failed for %r: %s",
            primary_skill,
            exc,
        )
        violation = HookViolation(
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
        return None, [violation], "ERROR"
    except Exception:
        logger.warning(
            "post_skill_edit: unexpected exception evaluating %r "
            "(re-raising per S-5 no-silent-failure)",
            primary_skill,
            exc_info=True,
        )
        raise
    return result, [], None


def _resolve_legacy_feedback_dir(
    payload: dict[str, Any],
    feedback_dir_raw: Any,
) -> Path | None:
    """Resolve the legacy DEFER-doc dir for migration + dual-read (ADR-8).

    v14.0.0 design §5b. Three cases:

    * Explicit ``payload["legacy_feedback_dir"]`` → use it (tests / custom
      callers control both ends of the relocation).
    * No explicit legacy AND no explicit ``feedback_dir`` (the relocated
      default dir is in use) → the real legacy default
      ``.local/feedbacks/``, so the production relocation migrates +
      dual-reads the actual pre-v14.0.0 location.
    * A CUSTOM ``feedback_dir`` supplied WITHOUT an explicit legacy →
      ``None`` (no implicit migration of the real ``.local/feedbacks/`` into
      an unrelated injected dir — keeps injected-dir callers/tests hermetic).
    """
    legacy_raw = payload.get("legacy_feedback_dir")
    if legacy_raw is not None:
        return Path(legacy_raw)
    if feedback_dir_raw is None:
        return LEGACY_FEEDBACK_DIR_DEFAULT
    return None


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

    Implementation note: per the v10.2.3 PV-04 cyclomatic-complexity
    reduction (NineS PV-03 deep-analysis row #7), the dogfood-cycle
    invocation + exception-classification body lives in
    :func:`_run_si_chip_evaluation`. Behaviour is byte-identical to
    v10.2.1 baseline.
    """
    if not is_deep_integration_active():
        return finalize(EVENT, [], strict=strict)

    if not isinstance(payload, dict):
        return finalize(EVENT, [], strict=strict)

    skill_files = _extract_skill_files(payload)
    if not skill_files:
        return finalize(EVENT, [], strict=strict)

    from devolaflow.si_chip_bridge import ApplyVerdict

    ability_name = str(payload.get("ability_name") or DEFAULT_ABILITY)
    feedback_dir_raw = payload.get("feedback_dir")
    feedback_dir = Path(feedback_dir_raw or FEEDBACK_DIR_DEFAULT)
    legacy_feedback_dir = _resolve_legacy_feedback_dir(payload, feedback_dir_raw)
    threshold = float(payload.get("threshold") or 0.10)

    metadata: dict[str, Any] = {
        "skill_files": skill_files,
        "ability_name": ability_name,
        "threshold": threshold,
    }

    primary_skill = Path(skill_files[0])
    result, violations, terminal_verdict = _run_si_chip_evaluation(
        primary_skill,
        skill_files,
        ability_name,
        threshold,
    )

    if terminal_verdict is not None:
        result_envelope = finalize(EVENT, violations, strict=strict)
        result_envelope.metadata.update(metadata)
        result_envelope.metadata["verdict"] = terminal_verdict
        return result_envelope

    metadata["verdict"] = result.verdict.value
    metadata["install_source"] = result.install_source
    metadata["notes"] = result.notes
    if result.delta is not None:
        metadata["iteration_delta"] = result.delta.iteration_delta

    if result.verdict == ApplyVerdict.DEFER:
        try:
            feedback_path = _write_feedback_doc(
                feedback_dir,
                skill_files,
                result.notes,
                result.install_source,
                result.verdict.value,
                legacy_feedback_dir=legacy_feedback_dir,
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
    "FINGERPRINT_SIDECAR_NAME",
    "LEGACY_FEEDBACK_DIR_DEFAULT",
    "SKILL_CORPUS_PREFIX",
    "is_deep_integration_active",
    "metadata_to_json",
    "post_skill_edit",
]
