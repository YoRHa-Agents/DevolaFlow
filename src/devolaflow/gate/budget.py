"""Token-budget circuit breaker for gate evaluation.

v8.0.0 (P-03) — implements primitive 4.3 from
``.local/research/tweet_analysis_harness_engineering_v7.8.md`` §4.3 and
``.local/research/v8.0.0_patch_plan.md`` §3 P-03.

Three decision paths (see :class:`devolaflow.gate.models.BudgetAction`):

- ``CONTINUE`` — utilization < 0.75 of profile ``max_tokens``.
- ``WARN``     — 0.75 ≤ utilization < 1.00.
- ``BREAK``    — utilization ≥ 1.00; circuit broken.

The recommendation paired with each action depends on the profile severity
(see :class:`devolaflow.gate.models.BudgetRecommendation`):

- ``STRICT`` / ``AUDIT`` profiles → BREAK escalates to a human (no auto-iter).
- ``STANDARD`` / ``RELAXED`` profiles → BREAK first iterates with throttle.

Pure semantics: :meth:`TokenBudgetBreaker.check` is a pure function of
``(cumulative_tokens, max_tokens, profile.name)``. The optional
:meth:`record` / :pyattr:`cumulative_tokens` / :meth:`check_recorded`
helpers offer round-level state tracking for callers that want it
(see ``patch_plan §3 P-03 — "持久化 round-level token tracking"``).

Honors S-5 (No Silent Failures): every invalid input raises
:class:`ValueError`; missing profile resolution falls back to ``STANDARD``
with an explicit log via :func:`from_profile_name`.
"""

from __future__ import annotations

import logging

from devolaflow.gate.models import (
    BudgetAction,
    BudgetDecision,
    BudgetRecommendation,
    GateProfile,
)
from devolaflow.gate.profiles import PROFILES, STANDARD

logger = logging.getLogger(__name__)

# Threshold constants — see ``patch_plan §3 P-03 AC #1``:
# ``check(5_000)`` ⇒ CONTINUE, ``check(8_000)`` ⇒ WARN, ``check(15_000)`` ⇒ BREAK
# against ``max_tokens=10_000`` (utilizations 0.50 / 0.80 / 1.50).
WARN_UTILIZATION_THRESHOLD: float = 0.75
BREAK_UTILIZATION_THRESHOLD: float = 1.00

# Profiles that escalate immediately on BREAK rather than asking the
# orchestrator to iterate with a throttled budget. STRICT and AUDIT both
# carry composite_threshold ≥ 90 — token exhaustion at that quality bar
# is a human-attention signal per ``patch_plan §3 P-03 AC #6``.
_ESCALATE_PROFILES: frozenset[str] = frozenset({"strict", "audit"})


def _resolve_max_tokens(profile: GateProfile, override: int | None) -> int:
    """Resolve the effective ``max_tokens`` budget at construction time.

    Explicit override wins; otherwise the value comes from the profile.
    Negative budgets are rejected (S-5 — no silent fallback to ``0``).
    """
    if override is not None:
        if override < 0:
            raise ValueError(
                f"max_tokens override must be >= 0 (got {override}); "
                "0 means unlimited (breaker disabled)"
            )
        return int(override)
    if profile.max_tokens < 0:
        raise ValueError(
            f"profile.max_tokens must be >= 0 (got {profile.max_tokens}); "
            "0 means unlimited (breaker disabled)"
        )
    return int(profile.max_tokens)


def _classify_utilization(utilization: float) -> BudgetAction:
    """Map a utilization ratio into a :class:`BudgetAction`."""
    if utilization >= BREAK_UTILIZATION_THRESHOLD:
        return BudgetAction.BREAK
    if utilization >= WARN_UTILIZATION_THRESHOLD:
        return BudgetAction.WARN
    return BudgetAction.CONTINUE


def _recommendation_for(action: BudgetAction, profile_name: str) -> BudgetRecommendation:
    """Pair an action with a follow-up recommendation per profile severity."""
    if action is BudgetAction.CONTINUE:
        return BudgetRecommendation.NONE
    if action is BudgetAction.WARN:
        return BudgetRecommendation.THROTTLE
    if profile_name in _ESCALATE_PROFILES:
        return BudgetRecommendation.ESCALATE
    return BudgetRecommendation.ITERATE


def _format_rationale(
    action: BudgetAction,
    cumulative_tokens: int,
    max_tokens: int,
    utilization: float,
    profile_name: str,
) -> str:
    """Render a short, single-line rationale for a :class:`BudgetDecision`."""
    pct = utilization * 100.0
    if action is BudgetAction.CONTINUE:
        return (
            f"Token usage {cumulative_tokens}/{max_tokens} ({pct:.1f}%) "
            f"within {WARN_UTILIZATION_THRESHOLD * 100:.0f}% warn threshold "
            f"(profile={profile_name})."
        )
    if action is BudgetAction.WARN:
        return (
            f"Token usage {cumulative_tokens}/{max_tokens} ({pct:.1f}%) "
            f"crossed {WARN_UTILIZATION_THRESHOLD * 100:.0f}% warn threshold "
            f"(profile={profile_name}); throttle recommended."
        )
    return (
        f"Token usage {cumulative_tokens}/{max_tokens} ({pct:.1f}%) exceeded "
        f"100% budget — circuit broken (profile={profile_name})."
    )


def _disabled_decision(cumulative_tokens: int, profile_name: str) -> BudgetDecision:
    """Return the canonical CONTINUE verdict for an *unlimited* breaker.

    When ``max_tokens == 0`` the breaker is a no-op — every call returns
    ``CONTINUE`` with utilization ``0.0`` and an explicit rationale. This is
    the byte-identical pre-P-03 path.
    """
    return BudgetDecision(
        action=BudgetAction.CONTINUE,
        cumulative_tokens=cumulative_tokens,
        max_tokens=0,
        utilization=0.0,
        rationale=(f"Profile {profile_name!r} sets max_tokens=0 (unlimited); breaker disabled."),
        recommendation=BudgetRecommendation.NONE,
    )


class TokenBudgetBreaker:
    """Token-budget circuit breaker.

    Wraps a :class:`GateProfile` with an optional explicit ``max_tokens``
    override. The default budget is read from ``profile.max_tokens``;
    a value of ``0`` means *unlimited* and renders the breaker a no-op
    (byte-identical pre-P-03 behaviour).

    Use :meth:`check` for pure evaluation against an externally tracked
    cumulative token count, or :meth:`record` + :meth:`check_recorded`
    for stateful round-level tracking.

    Examples
    --------
    >>> from devolaflow.gate.profiles import STANDARD
    >>> b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
    >>> b.check(5_000).action
    <BudgetAction.CONTINUE: 'CONTINUE'>
    >>> b.check(8_000).action
    <BudgetAction.WARN: 'WARN'>
    >>> b.check(15_000).action
    <BudgetAction.BREAK: 'BREAK'>
    """

    def __init__(
        self,
        profile: GateProfile,
        max_tokens: int | None = None,
    ) -> None:
        if not isinstance(profile, GateProfile):
            raise TypeError(f"profile must be a GateProfile (got {type(profile).__name__})")
        self._profile = profile
        self._effective_max = _resolve_max_tokens(profile, max_tokens)
        self._cumulative = 0

    # ---- read-only views ----------------------------------------------------

    @property
    def profile(self) -> GateProfile:
        """The :class:`GateProfile` this breaker was initialized with."""
        return self._profile

    @property
    def max_tokens(self) -> int:
        """Effective ``max_tokens`` budget (``0`` = unlimited)."""
        return self._effective_max

    @property
    def cumulative_tokens(self) -> int:
        """Cumulative token count recorded via :meth:`record` (or ``0``)."""
        return self._cumulative

    @property
    def is_unlimited(self) -> bool:
        """``True`` when ``max_tokens == 0`` and the breaker is disabled."""
        return self._effective_max == 0

    # ---- stateful tracking --------------------------------------------------

    def record(self, delta: int) -> int:
        """Accumulate ``delta`` tokens; return the new cumulative total.

        Negative deltas are rejected (S-5 — no silent fallback). A delta of
        ``0`` is a valid no-op (e.g. for round boundaries with no work).
        """
        if delta < 0:
            raise ValueError(f"token delta must be >= 0 (got {delta})")
        self._cumulative += int(delta)
        return self._cumulative

    def reset(self) -> None:
        """Reset the cumulative counter to ``0``.

        Useful when a new task or convergence cycle begins and the breaker
        instance is being reused. The ``max_tokens`` budget is preserved.
        """
        self._cumulative = 0

    def check_recorded(self) -> BudgetDecision:
        """Convenience: check the running ``cumulative_tokens`` total."""
        return self.check(self._cumulative)

    # ---- pure semantics -----------------------------------------------------

    def check(self, cumulative_tokens: int) -> BudgetDecision:
        """Evaluate the breaker against ``cumulative_tokens``.

        Pure function of ``(cumulative_tokens, profile.max_tokens, profile.name)``
        — no side effects, no I/O, idempotent.

        Parameters
        ----------
        cumulative_tokens:
            Total tokens consumed so far in this round / task. MUST be
            non-negative; negative values raise :class:`ValueError`.

        Returns
        -------
        BudgetDecision
            Carries action, utilization, rationale, and recommendation.
        """
        if cumulative_tokens < 0:
            raise ValueError(f"cumulative_tokens must be >= 0 (got {cumulative_tokens})")

        max_tokens = self._effective_max
        profile_name = self._profile.name

        if max_tokens == 0:
            return _disabled_decision(cumulative_tokens, profile_name)

        utilization = cumulative_tokens / max_tokens
        action = _classify_utilization(utilization)
        recommendation = _recommendation_for(action, profile_name)
        rationale = _format_rationale(
            action, cumulative_tokens, max_tokens, utilization, profile_name
        )

        return BudgetDecision(
            action=action,
            cumulative_tokens=int(cumulative_tokens),
            max_tokens=max_tokens,
            utilization=round(utilization, 4),
            rationale=rationale,
            recommendation=recommendation,
        )


def from_profile_name(
    profile_name: str,
    max_tokens: int | None = None,
) -> TokenBudgetBreaker:
    """Construct a :class:`TokenBudgetBreaker` from a registered profile name.

    Falls back to :data:`devolaflow.gate.profiles.STANDARD` when the profile
    name is unknown, mirroring the resolution policy in
    :func:`devolaflow.gate.scorer.run_gate_cli`. The fallback is logged at
    WARNING (S-5 — no silent fallback).
    """
    profile = PROFILES.get(profile_name)
    if profile is None:
        logger.warning(
            "Unknown profile %r; falling back to STANDARD. Known profiles: %s",
            profile_name,
            sorted(PROFILES),
        )
        profile = STANDARD
    return TokenBudgetBreaker(profile=profile, max_tokens=max_tokens)


__all__ = [
    "BREAK_UTILIZATION_THRESHOLD",
    "WARN_UTILIZATION_THRESHOLD",
    "TokenBudgetBreaker",
    "from_profile_name",
]
