"""Post-hoc verifier for the S1/trivial task path.

The task-stop hook consumes an optional ``trivial_path`` declaration and the
existing StatusReport ``diff_stats`` evidence. It never collects statistics
itself: L2 supplies the facts, while
``devolaflow.skills.change_activation.evaluate_trivial_path`` performs the
pure decision. Reports without the declaration or without diff telemetry are
explicit compatibility no-ops.
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize
from devolaflow.skills.change_activation import evaluate_trivial_path

EVENT = "task_stop"


def _no_op(reason: str) -> HookResult:
    """Build a clean result for a legacy or telemetry-free report."""
    return HookResult(event=EVENT, passed=True, metadata={"reason": reason})


def _declaration_block(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the canonical block, with a flat additive compatibility form."""
    block = payload.get("trivial_path")
    if block is not None:
        if not isinstance(block, dict):
            return None
        return block
    if "declared_complexity" not in payload:
        return None
    return {
        "declared_complexity": payload["declared_complexity"],
        "diff_stats": payload.get("diff_stats"),
        "is_cross_cutting": payload.get("is_cross_cutting", False),
    }


def _error_result(message: str, *, error_type: str, strict: bool) -> HookResult:
    """Surface malformed declaration/evidence as an explicit hook error."""
    return finalize(
        EVENT,
        [
            HookViolation(
                code="TSP006",
                message=message,
                severity="error",
                context={"error_type": error_type},
            )
        ],
        strict=strict,
    )


def validate_trivial_path(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Validate an S1 declaration at ``task_stop``.

    Canonical payload shape::

        trivial_path:
          declared_complexity: TRIVIAL
          is_cross_cutting: false
        diff_stats: {files: 1, insertions: 3, deletions: 2}

    The returned metadata contains ``passed``, ``declared_complexity``,
    aggregate actual ``diff_stats``, ``actual_complexity``, and
    ``upgrade_target`` so the StatusReport consumer can route a failed short
    path without parsing human-readable messages. Scope violations are
    blocker-severity in strict mode and warning-logged results in lite mode.
    """
    if not isinstance(payload, dict):
        return _no_op("no trivial_path declaration — compatibility no-op")

    block = _declaration_block(payload)
    if block is None:
        if payload.get("trivial_path") is not None:
            return _error_result(
                "'trivial_path' block must be a mapping",
                error_type="TypeError",
                strict=strict,
            )
        return _no_op("no trivial_path declaration — compatibility no-op")

    diff_stats = block.get("diff_stats", payload.get("diff_stats"))
    if diff_stats is None:
        return _no_op("no diff_stats telemetry — compatibility no-op")

    declared = block.get("declared_complexity", block.get("complexity"))
    if declared is None:
        return _error_result(
            "trivial_path declaration missing 'declared_complexity'",
            error_type="KeyError",
            strict=strict,
        )
    if declared not in ("TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"):
        return _error_result(
            f"trivial_path declaration has invalid complexity {declared!r}",
            error_type="ValueError",
            strict=strict,
        )
    if declared != "TRIVIAL":
        return _no_op(
            f"declared complexity is {declared!r}, not TRIVIAL — short-path verifier no-op"
        )
    cross_cutting = block.get("is_cross_cutting", block.get("cross_cutting", False))

    try:
        decision = evaluate_trivial_path(
            declared,
            diff_stats,
            is_cross_cutting=cross_cutting,
        )
    except (TypeError, ValueError, AttributeError) as exc:
        return _error_result(
            f"trivial_path evaluation failed: {exc}",
            error_type=type(exc).__name__,
            strict=strict,
        )

    violations = [
        HookViolation(
            code=violation.code,
            message=violation.message,
            severity="blocker",
            context={
                "violation_code": violation.code,
                "declared_complexity": decision.declared_complexity,
                "actual_complexity": decision.actual_complexity,
                "diff_stats": decision.as_dict()["diff_stats"],
                "is_cross_cutting": decision.is_cross_cutting,
                "upgrade_target": decision.upgrade_target,
            },
        )
        for violation in decision.violations
    ]
    result = finalize(EVENT, violations, strict=strict)
    result.metadata["trivial_path"] = decision.as_dict()
    return result


__all__ = ["EVENT", "validate_trivial_path"]
