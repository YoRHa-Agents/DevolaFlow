"""Gate quality mechanism data models.

Design ref: design_decomposition_gate.md §5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

Severity = Literal["blocker", "critical", "major", "minor", "info"]
GateDecision = Literal["PASS", "FAIL", "ESCALATE"]


class BudgetAction(StrEnum):
    """Outcome of a :class:`devolaflow.gate.budget.TokenBudgetBreaker` check.

    Three paths follow the v8.0.0 P-03 patch plan §3:

    - ``CONTINUE`` — utilization below the warning threshold (default 75 %).
    - ``WARN`` — utilization within the warning band but below 100 %.
    - ``BREAK`` — utilization at or above 100 %; circuit broken.
    """

    CONTINUE = "CONTINUE"
    WARN = "WARN"
    BREAK = "BREAK"


class BudgetRecommendation(StrEnum):
    """Suggested follow-up action paired with a :class:`BudgetAction`.

    The recommendation depends on both action and profile severity:
    STRICT/AUDIT escalate immediately on BREAK, STANDARD/RELAXED first
    iterate with a throttled budget. See ``patch_plan §3 P-03 AC #6``.
    """

    NONE = "NONE"
    THROTTLE = "THROTTLE"
    ITERATE = "ITERATE"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class BudgetDecision:
    """Result of a :class:`devolaflow.gate.budget.TokenBudgetBreaker` check.

    All fields are populated even on the ``CONTINUE`` path so callers can log
    every measurement uniformly without conditional branches. ``utilization``
    is rounded to 4 decimal places and is ``0.0`` whenever ``max_tokens == 0``
    (the unlimited / disabled state).
    """

    action: BudgetAction
    cumulative_tokens: int
    max_tokens: int
    utilization: float
    rationale: str
    recommendation: BudgetRecommendation


GateType = Literal[
    "standard",
    "convergence",
    "passthrough",
    "acceptance_readiness",
    "preflight",
    "revision",
    "escalation",
    "abort",
]

GATE_TYPE_ALIASES: dict[str, str] = {
    "standard": "revision",
    "convergence": "revision",
}
ProfileName = Literal["strict", "standard", "relaxed", "audit"]
LintPolicy = Literal["zero_warnings", "zero_errors", "advisory"]
BenchmarkPolicy = Literal["required", "optional", "disabled", "required_with_regression_check"]


@dataclass(frozen=True)
class AcceptanceCriterionResult:
    """Quality scores for a single acceptance criterion.

    Each dimension is scored 0–100. Used by the acceptance_readiness gate
    to evaluate criteria quality before work begins.
    """

    criterion_id: str
    text: str
    testability: float
    completeness: float
    measurability: float
    independence: float
    clarity: float


@dataclass(frozen=True)
class Finding:
    """A single review finding produced by code/architecture review."""

    finding_id: str
    severity: Severity
    category: str
    location: str
    description: str
    suggestion: str = ""
    rule_id: str = ""


@dataclass
class CheckResult:
    """Result of a single gate check (build/test/lint/review)."""

    status: Literal["pass", "fail", "skip"]
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class GateInput:
    """Aggregated inputs fed into gate evaluation."""

    build_status: CheckResult
    test_results: CheckResult
    lint_status: CheckResult
    review_findings: list[Finding] = field(default_factory=list)
    acceptance_criteria_results: CheckResult | None = None
    acceptance_readiness_criteria: list[AcceptanceCriterionResult] = field(
        default_factory=list,
    )
    # v5.4.0: User-facing verification inputs
    visual_test_results: CheckResult | None = None
    interaction_test_results: CheckResult | None = None
    accessibility_results: CheckResult | None = None
    acceptance_verification_results: CheckResult | None = None


@dataclass
class GateVerdict:
    """The output of a gate evaluation."""

    decision: GateDecision
    rationale: str
    composite_score: float | None = None
    meets_threshold: bool = False
    details: dict[str, object] = field(default_factory=dict)
    escalation_context: str = ""
    post_mortem: dict[str, object] = field(default_factory=dict)
    advisor_recommended: bool = False
    advisor_verdict: str = ""
    advisor_context: str = ""


@dataclass(frozen=True)
class GateProfile:
    """Configurable quality profile controlling gate strictness.

    See §5.4 for the four predefined profiles.
    """

    name: ProfileName
    composite_threshold: float
    coverage_threshold: float
    max_blocker: int
    max_critical: int
    max_rounds: int
    min_rounds: int
    lint_policy: LintPolicy
    benchmark_policy: BenchmarkPolicy
    acceptance_readiness_threshold: float = 80.0
    # v5.4.0: User-facing verification thresholds
    visual_fidelity_threshold: float = 0.0
    interaction_quality_threshold: float = 0.0
    accessibility_threshold: float = 0.0
    acceptance_verification_threshold: float = 0.0
    advisor_margin: float = 5.0
    # v7.2.2: Convergence-loop noise filter (P-01).
    # Fraction of the 0-100 composite-score scale to treat as the noise band
    # when calling :func:`devolaflow.gate.convergence.detect_stagnation` and
    # :func:`devolaflow.gate.convergence.compute_smoothed_trend`. Default 0.0
    # preserves bytewise pre-v7.2.2 behavior (single non-improving round =
    # stagnation, pairwise trend). Values > 0 require >= 2 consecutive rounds
    # of within-band deltas before declaring stagnation, and switch the
    # trend classifier to a window-3 moving average.
    noise_tolerance_pct: float = 0.0
    # v8.0.0 (P-03) — token-budget circuit breaker ceiling per task. ``0``
    # (the default) means *unlimited* and renders the breaker a no-op,
    # preserving byte-identical pre-P-03 behaviour for any caller that does
    # not opt in via ``devolaflow.gate.budget.TokenBudgetBreaker``.
    # Profile-specific defaults (per patch_plan §3 P-03):
    #   STRICT   80_000   STANDARD 50_000
    #   RELAXED       0   AUDIT   100_000
    max_tokens: int = 0
    # v8.0.0 (P-05) — verification-ladder opt-in flag. ``False`` (the
    # default) makes :func:`devolaflow.gate.scorer.evaluate_ladder`
    # delegate to :func:`devolaflow.gate.scorer.evaluate_gate` for
    # byte-identical pre-P-05 behaviour. ``True`` activates the 6-rung
    # short-circuit ladder per ``patch_plan §3 P-05 AC #1/#2/#3``.
    # Profile-specific defaults: STRICT/AUDIT enable, STANDARD/RELAXED
    # remain disabled until the orchestrator opts in.
    ladder_enabled: bool = False
    abort_categories: list[str] = field(
        default_factory=lambda: ["security", "data_loss"],
    )
    preflight_checks: list[str] = field(default_factory=list)


@dataclass
class ConvergenceRound:
    """Snapshot of a single convergence round for trend tracking."""

    round_num: int
    composite_score: float
    blocker_count: int
    critical_count: int
    timestamp: str


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-05) — Verification Ladder Formalization
#
# Formalizes a 6-rung verification ladder R1..R6 with deterministic
# short-circuit semantics. When an earlier rung FAILs, all later rungs are
# marked ``skip`` and not executed (per ``patch_plan §3 P-05 AC #1``).
#
# ``LadderRung`` (R1..R6) maps to the canonical ordering:
#
#     R1 = lint        (cheap, run first)
#     R2 = typecheck   (compile-time guarantees)
#     R3 = unit_test   (deterministic, fast)
#     R4 = integration (slower, may need fixtures)
#     R5 = benchmark   (perf budget enforcement)
#     R6 = convergence (composite-score / quality-gate evaluation)
#
# Earlier rungs are intentionally cheaper so failures abort before LLM /
# review cycles spend tokens — Karpathy "fail fast on cheap signals" per
# upstream tweet analysis ``v7.8`` §4.10.
# ─────────────────────────────────────────────────────────────────────────────


class LadderRung(StrEnum):
    """One of the 6 rungs in the v8.0.0 P-05 verification ladder.

    Order matters — :func:`devolaflow.gate.scorer.evaluate_ladder` walks
    R1 → R6 and short-circuits on the first ``fail`` (later rungs are
    marked ``skip``).
    """

    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"
    R6 = "R6"


# Stable mapping from each :class:`LadderRung` to its canonical name. Used
# by :class:`LadderEvaluation` consumers for human-facing reports and by
# the test suite for naming assertions. Pinned to satisfy S-4 (no ghost
# features — the rung names appear in CHANGELOG / docs verbatim).
LADDER_RUNG_NAMES: dict[LadderRung, str] = {
    LadderRung.R1: "lint",
    LadderRung.R2: "typecheck",
    LadderRung.R3: "unit_test",
    LadderRung.R4: "integration_test",
    LadderRung.R5: "benchmark",
    LadderRung.R6: "convergence",
}


# Canonical iteration order for the ladder — R1 → R6 (used by the scorer).
# Wrapped in a tuple so it is immutable from the caller's perspective.
LADDER_RUNG_ORDER: tuple[LadderRung, ...] = (
    LadderRung.R1,
    LadderRung.R2,
    LadderRung.R3,
    LadderRung.R4,
    LadderRung.R5,
    LadderRung.R6,
)


LadderRungStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class LadderEvaluation:
    """Outcome of evaluating one rung in the verification ladder.

    Three :pyattr:`status` paths follow ``patch_plan §3 P-05 AC #5``
    (S-5 No Silent Failures — the enum is exhaustive):

    - ``pass`` — rung executed and succeeded.
    - ``fail`` — rung executed and failed; later rungs short-circuit to ``skip``.
    - ``skip`` — rung not applicable (no input) OR short-circuited by an
      earlier failing rung. The :pyattr:`message` distinguishes the two.

    All fields are populated even on the ``skip`` path so callers can log
    every rung uniformly without conditional branches.
    """

    rung: LadderRung
    status: LadderRungStatus
    message: str
    name: str = ""
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Auto-fill the human-facing name from the canonical mapping. The
        # ``object.__setattr__`` dance is needed because the dataclass is
        # frozen — we still want a stable default without forcing every
        # caller to repeat ``LADDER_RUNG_NAMES[rung]``.
        if not self.name:
            object.__setattr__(self, "name", LADDER_RUNG_NAMES[self.rung])
