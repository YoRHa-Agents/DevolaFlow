"""Gate quality mechanism data models.

Design ref: design_decomposition_gate.md §5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["blocker", "critical", "major", "minor", "info"]
GateDecision = Literal["PASS", "FAIL", "ESCALATE"]
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
