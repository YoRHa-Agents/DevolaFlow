"""Pre-dispatch lifecycle hook — ``validate_dispatch``.

Documented in ``workflow-system/agent/SKILL.md`` §"Lifecycle Hooks".
Bound to the ``pre_dispatch`` event by :mod:`devolaflow.lifecycle.__init__`.

Contract: a dispatch payload (lean format per
``schemas/lean-dispatch.yaml``) MUST carry at least one **testable**
acceptance criterion before being released to an L3 task agent. The
hook recognises both the lean ``accept`` key and the verbose
``acceptance_criteria`` key for backward compatibility.

Permissive default — emits a WARNING via the lifecycle logger and
returns a :class:`HookResult` with the violations attached. Strict mode
re-raises the top-severity :class:`HookViolation`.
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "pre_dispatch"

# Tokens that are explicitly NOT testable acceptance criteria. Lower-cased
# verbatim form is checked against ``criterion.strip().lower()``.
_NON_TESTABLE_TOKENS: frozenset[str] = frozenset(
    {
        "",
        "tbd",
        "to be determined",
        "to be defined",
        "todo",
        "todo:",
        "n/a",
        "na",
        "various",
        "see above",
        "see below",
        "see design",
        "(none)",
    }
)


def _is_testable(criterion: object) -> bool:
    """Return True iff *criterion* is a non-trivial testable string.

    A criterion is testable when it is a non-empty string whose stripped
    lower-case form is not in :data:`_NON_TESTABLE_TOKENS` AND has at
    least 4 characters of substantive text. The 4-char floor catches
    placeholders like "ok" / "yes" that slip past the explicit deny set.
    """
    if not isinstance(criterion, str):
        return False
    stripped = criterion.strip()
    if len(stripped) < 4:
        return False
    return stripped.lower() not in _NON_TESTABLE_TOKENS


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Collect all :class:`HookViolation` instances for *payload*.

    Separated from :func:`validate_dispatch` so :func:`run_hooks` can
    invoke this directly without the wrapper's logging/strict logic.
    """
    if not isinstance(payload, dict):
        return [
            HookViolation(
                code="VD001",
                message="dispatch payload is not a mapping",
                severity="error",
                context={"payload_type": type(payload).__name__},
            )
        ]

    accept_value = payload.get("accept")
    if accept_value is None:
        accept_value = payload.get("acceptance_criteria")

    if accept_value is None:
        return [
            HookViolation(
                code="VD002",
                message=(
                    "dispatch payload missing required field: 'accept' (or 'acceptance_criteria')"
                ),
                severity="blocker",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    if not isinstance(accept_value, list):
        return [
            HookViolation(
                code="VD003",
                message="'accept' field must be a list of acceptance criteria",
                severity="error",
                context={"accept_type": type(accept_value).__name__},
            )
        ]

    testable = [c for c in accept_value if _is_testable(c)]
    if not testable:
        return [
            HookViolation(
                code="VD004",
                message=(
                    "dispatch must include ≥1 testable acceptance criterion "
                    "(non-empty string ≥4 chars, not in placeholder set)"
                ),
                severity="blocker",
                context={
                    "received_count": len(accept_value),
                    "received_values": list(accept_value),
                },
            )
        ]

    return []


def validate_dispatch(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Validate that *payload* carries at least one testable acceptance criterion.

    See module docstring for the contract. Returns a :class:`HookResult`
    in both modes; raises the top :class:`HookViolation` only when
    ``strict=True`` AND a violation was found.
    """
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "validate_dispatch"]
