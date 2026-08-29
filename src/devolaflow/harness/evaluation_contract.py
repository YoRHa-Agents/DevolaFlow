"""Shared public contract values for deterministic harness evaluation."""

from __future__ import annotations

from typing import Final

DIMENSION_WEIGHTS: Final[dict[str, float]] = {
    "code_quality": 0.20,
    "architecture_rationality": 0.20,
    "test_adequacy": 0.20,
    "maintainability": 0.15,
    "compatibility": 0.10,
    "performance_impact": 0.15,
}
DEFAULT_THRESHOLD: Final[float] = 8.5
DEFAULT_CROSS_VALIDATION_DELTA: Final[float] = 1.0
HISTORICAL_COMPANION_METHOD: Final[str] = "historical_w3_hybrid_companion_v15_final"


class EvaluationError(ValueError):
    """Evaluation inputs or signal values violate the evaluator contract."""


__all__ = [
    "DEFAULT_CROSS_VALIDATION_DELTA",
    "DEFAULT_THRESHOLD",
    "DIMENSION_WEIGHTS",
    "EvaluationError",
    "HISTORICAL_COMPANION_METHOD",
]
