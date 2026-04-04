"""Convergence detection helpers.

Design ref: design_decomposition_gate.md §5.7, §7.3
"""

from __future__ import annotations

from devolaflow.gate.models import ConvergenceRound


def detect_stagnation(history: list[ConvergenceRound]) -> bool:
    """Return *True* when the composite score has not improved for 2 consecutive rounds.

    Stagnation requires ``len(history) >= 2`` and the last two rounds showing
    no score increase.
    """
    if len(history) < 2:
        return False
    return history[-1].composite_score <= history[-2].composite_score


def compute_trend(history: list[ConvergenceRound]) -> str:
    """Classify the recent score trajectory.

    Returns
    -------
    "improving"
        Latest score is strictly higher than the previous.
    "degrading"
        Latest score is strictly lower than the previous.
    "stagnant"
        Latest score equals the previous, or fewer than 2 rounds recorded.
    """
    if len(history) < 2:
        return "stagnant"
    delta = history[-1].composite_score - history[-2].composite_score
    if delta > 0:
        return "improving"
    if delta < 0:
        return "degrading"
    return "stagnant"
