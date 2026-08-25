"""Pre-dispatch lifecycle hook — ``reject_subagent_quality_score``.

v12.2.0 PV-04 closure for the v12.1.0 D-1 runtime layer (the prompt-side
guarantee was discharged in v12.1.0 via SKILL.md §"Task Quality Score
(L0 ONLY)"; this PV adds the runtime-side enforcement that was
telegraphed to "v12.2.0+" in the v12.0.0/v12.1.0 CHANGELOG entries).

Contract: a dispatch payload routed through the ``pre_dispatch`` event
chain MUST NOT carry a ``quality_score`` (or bare ``quality``) field at
the top level OR inside the ``metrics`` / ``self_check`` evidence
blocks. The field is **L0-only** per SKILL.md §"Task Quality Score" —
subagents (L1/L2) MUST NOT score, and accidentally embedding a
``quality_score`` in a mid-stage dispatch (e.g. L1 → L2 wave dispatch
that propagates a stale L2 report scoring) is a contract violation. The
hook surfaces an **error-severity** violation per the v12.2.0 PV-04
runtime layer.

v15.0.0 strict graduation (G-038, rides the DEFAULTS-PERMISSIVE-IN-MINOR
/ STRICT-IN-NEXT-MAJOR pattern):

* **STRICT default** — a direct invocation without an explicit
  ``strict`` argument now RAISES the top-severity
  :class:`HookViolation` (the v12.2.0..v14.x permissive default warned
  + returned). Opt-out: pass ``strict=False`` explicitly at the call
  site (no env flag — W-20 zero-new-flags). NOTE: the ``run_hooks``
  chain is unaffected — the dispatcher invokes every handler with
  ``strict=False`` and centralises the strict-raise decision (S-10
  emission stays permissive per ``feedback_emit._fire_hook_chain``).
* **Nested-block scan** — the v14.3.0 evidence blocks made
  ``metrics.gate_input_score`` legitimate (G-013 one-doctrine rename),
  so the scan extends beyond the top level into ``metrics`` and
  ``self_check``: a ``quality_score`` / ``quality`` key in EITHER block
  is a fresh subagent score smuggled through evidence transport (the
  nested-block scan the v14.3.0 ghost note deferred to v15.0.0 per the
  ADR-007 phase split). ``predecessor_artifacts`` / ``pred`` entries
  remain exempt — historical L0 scoring carried forward as read-only
  evidence is legitimate.

Registered as an **extra** handler on the ``pre_dispatch`` event by
:mod:`devolaflow.lifecycle.__init__` so it runs AFTER the canonical
:func:`devolaflow.lifecycle.validate_dispatch` default — preserves the
S-10 byte-id contract (no replacement of defaults; pure additive
extension).

Source: `.local/research/v12.2.0_gap_analysis.md` §2 D-4 +
`.local/research/v14.2.0_gap_analysis.md` §2.7 G-038 (strict cluster) +
§2 G-013 (nested-scan enablement) + v15-ADR-007 (evidence-only doctrine).
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "pre_dispatch"

_QUALITY_SCORE_KEY = "quality_score"

_FORBIDDEN_KEYS: tuple[str, ...] = ("quality_score", "quality")
"""Keys that signal a subagent-produced score (L0-only doctrine).

``gate_input_score`` (the G-013 rename) is deliberately ABSENT — it is
gate-dimension input EVIDENCE, not the Task Quality Score.
"""

_NESTED_SCAN_BLOCKS: tuple[str, ...] = ("metrics", "self_check")
"""Evidence blocks scanned in ADDITION to the top level (v15.0.0).

``predecessor_artifacts`` / ``pred`` stay exempt: nested occurrences
there are read-only references to historical L0 scoring carried forward
as predecessor evidence.
"""

_VIOLATION_CODE = "QS-001"

_VIOLATION_MESSAGE_TEMPLATE = (
    "subagent_quality_score_in_dispatch: dispatch payload carries a "
    "{key!r} field at {location}. Per SKILL.md §'Task Quality Score "
    "(L0 ONLY)', scoring is an L0-only responsibility; subagents "
    "(L1/L2) MUST NOT produce a quality score. Strip the field from "
    "the upstream report before re-dispatching (gate-dimension input "
    "evidence belongs in 'metrics.gate_input_score'). Strict by default "
    "since v15.0.0 — pass strict=False explicitly to downgrade this "
    "raise to a logged warning."
)


def _scan_for_forbidden_keys(payload: object) -> list[tuple[str, str]]:
    """Return ``(key, location)`` pairs for every forbidden score field.

    Defensive against non-dict inputs (returns ``[]``) so a malformed
    payload does NOT cause the hook to raise — the validate_dispatch
    default already covers schema-level malformation.

    Scanned scopes (v15.0.0 nested-block scan per the ADR-007 phase
    split): the payload top level, plus the ``metrics`` and
    ``self_check`` evidence blocks. Other nested occurrences (e.g.
    ``payload['predecessor_artifacts'][0]['quality_score']``) are
    legitimate read-only references to historical L0 scoring and are
    NOT flagged.
    """
    if not isinstance(payload, dict):
        return []
    hits: list[tuple[str, str]] = []
    for key in _FORBIDDEN_KEYS:
        if key in payload:
            hits.append((key, "top level"))
    for block in _NESTED_SCAN_BLOCKS:
        nested = payload.get(block)
        if not isinstance(nested, dict):
            continue
        for key in _FORBIDDEN_KEYS:
            if key in nested:
                hits.append((key, f"'{block}' block"))
    return hits


def reject_subagent_quality_score(
    payload: dict[str, Any],
    *,
    strict: bool = True,
) -> HookResult:
    """Reject dispatch payloads that carry a subagent quality score.

    Args:
      payload: Dispatch payload (lean format per
        ``schemas/lean-dispatch.yaml``).
      strict: STRICT by default since v15.0.0 (G-038 graduation) —
        a violation raises the top-severity :class:`HookViolation`.
        Pass ``strict=False`` explicitly to opt out (permissive
        warn-and-return, the v12.2.0..v14.x behaviour). The
        ``run_hooks`` chain always invokes handlers permissively and
        applies its own strict policy at aggregate time.

    Returns:
      HookResult with violations attached when a ``quality_score`` /
      ``quality`` key is present at the top level or inside the
      ``metrics`` / ``self_check`` blocks; clean result otherwise. The
      result's ``metadata`` carries ``checked_key`` so downstream
      observers can distinguish this hook's pass from "no extras
      registered".

    Per S-5 (no silent failures) the hook never swallows exceptions:
    the violation is either re-raised (strict default) or attached to
    HookResult with a WARNING log (explicit ``strict=False`` opt-out).
    """
    violations: list[HookViolation] = []
    for key, location in _scan_for_forbidden_keys(payload):
        violations.append(
            HookViolation(
                code=_VIOLATION_CODE,
                message=_VIOLATION_MESSAGE_TEMPLATE.format(key=key, location=location),
                severity="error",
                context={
                    "field": key,
                    "location": location,
                    "rule": (
                        "v12.2.0 PV-04 D-4 / SKILL.md §Task Quality Score (L0 ONLY); "
                        "strict + nested metrics/self_check scan since v15.0.0 G-038"
                    ),
                },
            )
        )

    result = finalize(EVENT, violations, strict=strict)
    result.metadata["checked_key"] = _QUALITY_SCORE_KEY
    return result


__all__ = ["EVENT", "reject_subagent_quality_score"]
