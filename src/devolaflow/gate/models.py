"""Gate quality mechanism data models.

Design ref: design_decomposition_gate.md §5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["blocker", "critical", "major", "minor", "info"]
GateDecision = Literal["PASS", "FAIL", "ESCALATE"]
GateType = Literal["standard", "convergence", "passthrough"]
ProfileName = Literal["strict", "standard", "relaxed", "audit"]
LintPolicy = Literal["zero_warnings", "zero_errors", "advisory"]
BenchmarkPolicy = Literal["required", "optional", "disabled", "required_with_regression_check"]


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


@dataclass
class GateVerdict:
    """The output of a gate evaluation."""

    decision: GateDecision
    rationale: str
    composite_score: float | None = None
    meets_threshold: bool = False


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


@dataclass
class ConvergenceRound:
    """Snapshot of a single convergence round for trend tracking."""

    round_num: int
    composite_score: float
    blocker_count: int
    critical_count: int
    timestamp: str
