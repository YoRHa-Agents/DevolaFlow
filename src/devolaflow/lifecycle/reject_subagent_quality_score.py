"""Pre-dispatch lifecycle hook — ``reject_subagent_quality_score``.

v12.2.0 PV-04 closure for the v12.1.0 D-1 runtime layer (the prompt-side
guarantee was discharged in v12.1.0 via SKILL.md §"Task Quality Score
(L0 ONLY)"; this PV adds the runtime-side enforcement that was
telegraphed to "v12.2.0+" in the v12.0.0/v12.1.0 CHANGELOG entries).

Contract: a dispatch payload routed through the ``pre_dispatch`` event
chain MUST NOT carry a top-level ``quality_score`` field. The field is
**L0-only** per SKILL.md §"Task Quality Score" — subagents (L1/L2/L3)
MUST NOT score, and accidentally embedding a ``quality_score`` in a
mid-stage dispatch (e.g. L1 → L2 wave dispatch that propagates a stale
L3 report scoring) is a soft contract violation. The hook surfaces a
**major-severity** violation per the v12.2.0 PV-04 runtime layer.

Permissive default — emits a WARNING via the lifecycle logger and
returns a :class:`HookResult` with the violations attached. Strict mode
(``strict=True``) re-raises the top-severity :class:`HookViolation` so
callers can abort + escalate per P4.

Registered as an **extra** handler on the ``pre_dispatch`` event by
:mod:`devolaflow.lifecycle.__init__` so it runs AFTER the canonical
:func:`devolaflow.lifecycle.validate_dispatch` default — preserves the
S-10 byte-id contract (no replacement of defaults; pure additive
extension).

Source: `.local/research/v12.2.0_gap_analysis.md` §2 D-4 +
``CHANGELOG.md`` §[12.0.0] + §[12.1.0] telegraph "Runtime enforcement
of forbidden patterns (e.g., a `pre_dispatch` hook that rejects L3
reports carrying `quality_score` fields)".
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "pre_dispatch"

_QUALITY_SCORE_KEY = "quality_score"

_VIOLATION_CODE = "QS-001"

_VIOLATION_MESSAGE = (
    "subagent_quality_score_in_dispatch: dispatch payload carries a "
    "top-level 'quality_score' field. Per SKILL.md §'Task Quality Score "
    "(L0 ONLY)', scoring is an L0-only responsibility; subagents "
    "(L1/L2/L3) MUST NOT produce a quality_score. Strip the field from "
    "the upstream report before re-dispatching."
)


def _payload_carries_quality_score(payload: object) -> bool:
    """Return True iff *payload* carries a top-level ``quality_score`` key.

    Defensive against non-dict inputs (returns False) so a malformed
    payload does NOT cause the hook to raise — the validate_dispatch
    default already covers schema-level malformation.

    The check is intentionally **top-level only** — nested occurrences
    (e.g. ``payload['predecessor_artifacts'][0]['quality_score']``) are
    legitimate read-only references to historical L0 scoring carried
    forward as predecessor evidence; only a top-level field signals
    that a subagent itself produced a score that has been propagated
    into the dispatch envelope.
    """
    if not isinstance(payload, dict):
        return False
    return _QUALITY_SCORE_KEY in payload


def reject_subagent_quality_score(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Reject dispatch payloads that carry a top-level ``quality_score``.

    Args:
      payload: Dispatch payload (lean format per
        ``schemas/lean-dispatch.yaml``).
      strict: When True, re-raise the violation as a HookViolation per
        the lifecycle dispatcher's strict-mode contract.

    Returns:
      HookResult with the violation attached when ``quality_score`` is
      present at the top level; clean result otherwise. The result's
      ``metadata`` carries ``checked_key`` so downstream observers can
      distinguish this hook's pass from "no extras registered".

    Per S-5 (no silent failures) the hook never swallows exceptions:
    the violation is either attached to HookResult (permissive) or
    re-raised (strict). The permissive default mirrors v8.4.4
    post_dispatch — operators opt into strict mode at the call site.
    """
    violations: list[HookViolation] = []
    if _payload_carries_quality_score(payload):
        violations.append(
            HookViolation(
                code=_VIOLATION_CODE,
                message=_VIOLATION_MESSAGE,
                severity="error",
                context={
                    "field": _QUALITY_SCORE_KEY,
                    "rule": "v12.2.0 PV-04 D-4 / SKILL.md §Task Quality Score (L0 ONLY)",
                },
            )
        )

    result = finalize(EVENT, violations, strict=strict)
    result.metadata["checked_key"] = _QUALITY_SCORE_KEY
    return result


__all__ = ["EVENT", "reject_subagent_quality_score"]
