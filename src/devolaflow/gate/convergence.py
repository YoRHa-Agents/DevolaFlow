"""Convergence detection helpers.

Design ref: design_decomposition_gate.md §5.7, §7.3
"""

from __future__ import annotations

from typing import Literal

from devolaflow.gate.models import ConvergenceRound

Trend = Literal["improving", "degrading", "stagnant"]


def detect_stagnation(
    history: list[ConvergenceRound],
    noise_tolerance_pct: float = 0.0,
) -> bool:
    """Return *True* when the composite score has not improved.

    Parameters
    ----------
    history:
        Convergence-round snapshots, oldest first.
    noise_tolerance_pct:
        Optional fraction of the 0-100 composite-score scale (so ``0.05``
        means a ``±5pp`` noise band) treated as verifier-side jitter rather
        than real stagnation. Default ``0.0`` preserves the v7.1.x semantics
        where a single non-improving round suffices.

    Default behavior (``noise_tolerance_pct == 0.0``) is byte-stable with
    earlier releases: stagnation requires ``len(history) >= 2`` and the last
    two rounds showing no score increase.

    With ``noise_tolerance_pct > 0`` (added in v7.2.2 P-01 — convergence-loop
    noise filter, EvoBench v2.2.0 Tier 1 #2):

    * deltas strictly above ``+tolerance_band`` → not stagnant (clear lift),
    * deltas strictly below ``-tolerance_band`` → stagnant (clear regression
      retains the existing fail-fast signal),
    * deltas within ``±tolerance_band`` → stagnant *only* once two
      consecutive rounds (i.e. the last two deltas, requiring 3 entries)
      both fall inside the band. This prevents the gen-verify loop from
      misclassifying a real-but-noisy improvement trajectory as stagnation
      after a single jitter sample.
    """
    if len(history) < 2:
        return False

    if noise_tolerance_pct <= 0.0:
        return history[-1].composite_score <= history[-2].composite_score

    tolerance_band = noise_tolerance_pct * 100.0
    delta_n = history[-1].composite_score - history[-2].composite_score

    if delta_n > tolerance_band:
        return False
    if delta_n < -tolerance_band:
        return True

    if len(history) < 3:
        return False
    delta_n1 = history[-2].composite_score - history[-3].composite_score
    return abs(delta_n1) <= tolerance_band


def compute_trend(history: list[ConvergenceRound]) -> Trend:
    """Classify the recent score trajectory using pairwise comparison.

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


def compute_smoothed_trend(
    history: list[ConvergenceRound],
    window: int = 3,
) -> Trend:
    """Classify trajectory using a moving-average window (v7.2.2 P-01).

    Compares the mean composite score of the most recent ``window`` rounds
    against the mean of the immediately-preceding window of the same size,
    so that single-round jitter (the eb220 ``±2-3pp`` verifier-noise
    pattern) does not flip the classification across consecutive rounds.

    Parameters
    ----------
    history:
        Convergence-round snapshots, oldest first.
    window:
        Moving-average window size. Defaults to ``3`` per the v7.3.0 patch
        plan §P-01. Window of ``2`` collapses to pairwise comparison.

    Returns
    -------
    Same three-valued vocabulary as :func:`compute_trend`. When
    ``len(history) < window`` the classifier falls back to
    :func:`compute_trend` so the helper is safe to invoke at every round
    of a convergence loop. When ``len(history) == window`` exactly, only
    one full window is available and the classifier compares the last
    score in the window to the first (single-window slope).

    This helper is invoked by :func:`devolaflow.gate.scorer._evaluate_convergence`
    only when ``profile.noise_tolerance_pct > 0``; default-zero callers
    keep the pairwise :func:`compute_trend` path bytewise unchanged.
    """
    if window <= 1:
        return compute_trend(history)
    if len(history) < window:
        return compute_trend(history)

    if len(history) < window + 1:
        scores = [r.composite_score for r in history[-window:]]
        delta = scores[-1] - scores[0]
        if delta > 0:
            return "improving"
        if delta < 0:
            return "degrading"
        return "stagnant"

    current_window = [r.composite_score for r in history[-window:]]
    previous_window = [r.composite_score for r in history[-window - 1 : -1]]
    current_ma = sum(current_window) / window
    previous_ma = sum(previous_window) / window
    delta = current_ma - previous_ma
    if delta > 0:
        return "improving"
    if delta < 0:
        return "degrading"
    return "stagnant"
