"""Pre-dispatch lifecycle hook — ``reject_subagent_banner_emission``.

v12.4.0 PV-05 closure for the v12.3.0 PV-02 Session Banner Contract
runtime layer (the prompt-side guarantee was discharged in v12.3.0 via
SKILL.md §"Version & Update" → "Session Banner Contract"; this PV adds
the runtime-side enforcement that subagent (L1/L2) dispatches MUST
NOT carry banner literals, since banners are L0-only operator chat
output per CO-2 / Rule C-2 Lean Message Format).

Contract: a dispatch payload routed through the ``pre_dispatch`` event
chain whose ``target_layer ∈ {"L1", "L2"}`` (plus the legacy ``"L3"``
spelling, tolerated for stray v1 payloads) MUST NOT carry the
``🌸 DevolaFlow vX.Y.Z`` literal pattern in any free-text field
(``predecessor_artifacts[*].summary``, ``acceptance_criteria``,
top-level ``summary`` / ``description``). When ``target_layer == "L0"``
the hook is a no-op (banners are legitimate L0 output). The check
ignores nested occurrences inside ``predecessor_artifacts`` because
those are IMMUTABLE historical evidence carried forward from prior
L0-authored rounds (the v12.2.0 PV-04 top-level-only precedent for
``reject_subagent_quality_score`` is mirrored here).

Permissive default — emits a WARNING via the lifecycle logger and
returns a :class:`HookResult` with the violations attached per S-5
(no silent failures). Strict mode (``strict=True``) re-raises the
top-severity :class:`HookViolation` so callers can abort + escalate
per P4.

Registration — **default-wired since v15.0.0** (G-038 flip 3, rides
the DEFAULTS-PERMISSIVE-IN-MINOR / STRICT-IN-NEXT-MAJOR pattern):
``lifecycle/__init__.py`` calls
``register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)``
at import time, mirroring the v12.2.0 PV-04
``reject_subagent_quality_score`` wiring, so every
``run_hooks("pre_dispatch", ...)`` dispatch includes the banner check
with no operator action. The v12.4.0..v14.x opt-in helper
:func:`register_pre_dispatch_extra` is retained for operators who
re-wire after a ``clear_hooks()``; the documented OPT-OUT is
:func:`unregister_pre_dispatch_extra` (removes ONLY this hook; sibling
extras stay registered). No env flag in either direction (W-20
zero-new-flags).

Source: `.local/research/v12.4.0_l0_only_audit.md` §B.1 (banner
literal enumeration) + `.local/research/v12.4.0_gap_analysis.md`
§2 D-4 (L0-only surfaces leak cluster — 派发分层 user-feedback theme) +
`.local/research/v14.2.0_gap_analysis.md` §2.7 G-038 (default-wire
graduation).
"""

from __future__ import annotations

import re
from typing import Any

from devolaflow.lifecycle.dispatcher import (
    HookResult,
    HookViolation,
    finalize,
    register_hook,
    unregister_hook,
)

EVENT = "pre_dispatch"

_BANNER_PATTERN: re.Pattern[str] = re.compile(r"🌸\s*DevolaFlow\s+v\d+\.\d+\.\d+")
"""Matches the SKILL.md §'Session Banner Contract' v12.3.0+ banner literal.

The pattern intentionally allows the version digits to drift across
patch / minor / major bumps (per `scripts/bump_version.py` which keeps
the SKILL.md literal in sync with `src/devolaflow/__init__.py`). The
``🌸`` flower emoji is the load-bearing visual anchor — it ONLY
appears in DevolaFlow banner literals (verified by grep across
`workflow-system/agent/` at v12.3.0+).
"""

_VIOLATION_CODE = "BAN-001"

_VIOLATION_MESSAGE_TEMPLATE = (
    "subagent_banner_emission_in_dispatch: dispatch to {target_layer!r} "
    "carries a '🌸 DevolaFlow vX.Y.Z' banner literal in {field!r}. "
    "Per SKILL.md §'Session Banner Contract', banners are L0-only "
    "operator chat output — subagents (L1/L2) MUST NOT receive "
    "banner lines in dispatch context. Strip the banner from the "
    "upstream summary before re-dispatching."
)

# "L3" is the legacy v1 Task spelling — kept for stray legacy payloads.
_SUBAGENT_TARGET_LAYERS: frozenset[str] = frozenset({"L1", "L2", "L3"})

_TARGET_LAYER_KEY = "target_layer"

_PREDECESSOR_ARTIFACTS_KEY = "predecessor_artifacts"

_ACCEPTANCE_CRITERIA_KEY = "acceptance_criteria"

_FREE_TEXT_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "summary",
    "description",
)


def _payload_target_layer(payload: object) -> str | None:
    """Return the payload's ``target_layer`` field, or None if absent.

    Defensive against non-dict inputs (returns None) so a malformed
    payload does NOT cause the hook to raise — the
    :func:`validate_dispatch` default already covers schema-level
    malformation.
    """
    if not isinstance(payload, dict):
        return None
    value = payload.get(_TARGET_LAYER_KEY)
    if isinstance(value, str):
        return value
    return None


def _scan_free_text_fields(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Enumerate (field_path, text) pairs to check for banner literals.

    Returns a list of ``(field_path, text)`` tuples covering the
    top-level free-text keys + the ``acceptance_criteria`` list (each
    entry rendered as its own field-path) — but DELIBERATELY EXCLUDES
    ``predecessor_artifacts[*].summary`` per the top-level-only
    discipline (nested predecessor summaries are immutable historical
    evidence carried forward from prior L0-authored rounds).
    """
    fields: list[tuple[str, str]] = []
    for key in _FREE_TEXT_TOP_LEVEL_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            fields.append((key, value))
    acceptance = payload.get(_ACCEPTANCE_CRITERIA_KEY)
    if isinstance(acceptance, list):
        for idx, entry in enumerate(acceptance):
            if isinstance(entry, str) and entry:
                fields.append((f"{_ACCEPTANCE_CRITERIA_KEY}[{idx}]", entry))
    return fields


def reject_subagent_banner_emission(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Reject subagent dispatch payloads carrying banner literals.

    Args:
      payload: Dispatch payload (lean format per
        ``schemas/lean-dispatch.yaml``).
      strict: When True, re-raise the violation as a HookViolation per
        the lifecycle dispatcher's strict-mode contract.

    Returns:
      HookResult with the violation attached when a banner literal is
      detected in a subagent dispatch payload; clean result otherwise.
      The result's ``metadata`` carries ``checked_pattern`` so
      downstream observers can distinguish this hook's pass from
      "no extras registered".

    Per S-5 (no silent failures) the hook never swallows exceptions:
    the violation is either attached to HookResult (permissive) or
    re-raised (strict). The permissive default mirrors the v12.2.0
    PV-04 ``reject_subagent_quality_score`` precedent — operators
    opt into strict mode at the call site.

    The hook is a no-op (clean result) when:
    * ``payload`` is not a dict (defensive; validate_dispatch covers
      schema-level malformation)
    * ``payload[target_layer]`` is absent or ``"L0"`` (banners are
      legitimate L0 output)
    * Banner literals only appear in ``predecessor_artifacts[*].summary``
      (immutable historical evidence, NOT a fresh emission)
    """
    target_layer = _payload_target_layer(payload)
    violations: list[HookViolation] = []

    if isinstance(payload, dict) and target_layer in _SUBAGENT_TARGET_LAYERS:
        for field_path, text in _scan_free_text_fields(payload):
            if _BANNER_PATTERN.search(text):
                violations.append(
                    HookViolation(
                        code=_VIOLATION_CODE,
                        message=_VIOLATION_MESSAGE_TEMPLATE.format(
                            target_layer=target_layer,
                            field=field_path,
                        ),
                        severity="error",
                        context={
                            "field": field_path,
                            "target_layer": target_layer,
                            "rule": (
                                "v12.4.0 PV-05 D-4 / SKILL.md §'Session "
                                "Banner Contract' (banners are L0-only)"
                            ),
                        },
                    )
                )

    result = finalize(EVENT, violations, strict=strict)
    result.metadata["checked_pattern"] = _BANNER_PATTERN.pattern
    return result


def register_pre_dispatch_extra() -> None:
    """Re-registration helper for :func:`reject_subagent_banner_emission`.

    Calls ``register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)``
    so subsequent ``run_hooks("pre_dispatch", ...)`` invocations include
    this hook in the extras chain. The registration is **idempotent at
    the helper-contract level only**: re-calling the helper appends the
    hook AGAIN (preserving the ``register_hook`` insertion-order
    semantics), so callers MUST invoke this helper at most once per
    registry state.

    Since v15.0.0 (G-038 flip 3) the hook is ALREADY auto-wired by
    :mod:`devolaflow.lifecycle.__init__` at import time — this helper
    is retained for operators re-wiring after a ``clear_hooks()`` (the
    same convention the v12.2.0 PV-04 ``reject_subagent_quality_score``
    test fixtures use) or after an :func:`unregister_pre_dispatch_extra`
    opt-out.
    """
    register_hook(EVENT, reject_subagent_banner_emission)


def unregister_pre_dispatch_extra() -> bool:
    """Opt out of the v15.0.0 default wiring (G-038 flip 3 opt-out).

    Removes :func:`reject_subagent_banner_emission` from the
    ``pre_dispatch`` extras chain via
    :func:`devolaflow.lifecycle.dispatcher.unregister_hook`. Sibling
    extras (``validate_owned_files``,
    ``reject_subagent_quality_score``) and the ``validate_dispatch``
    default are untouched — this is the per-flip opt-out surface, NOT a
    registry reset (use ``clear_hooks`` for that). No env flag (W-20).

    Returns ``True`` when a registration was removed, ``False`` when
    the hook was already absent (idempotent opt-out).
    """
    return unregister_hook(EVENT, reject_subagent_banner_emission)


__all__ = [
    "EVENT",
    "register_pre_dispatch_extra",
    "reject_subagent_banner_emission",
    "unregister_pre_dispatch_extra",
]
