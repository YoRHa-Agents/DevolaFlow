"""Comprehensive tests for the gate quality mechanism.

Design ref: design_decomposition_gate.md §5
"""

from __future__ import annotations

from devolaflow.gate.convergence import compute_trend, detect_stagnation
from devolaflow.gate.models import (
    AcceptanceCriterionResult,
    CheckResult,
    ConvergenceRound,
    Finding,
    GateInput,
    GateVerdict,
)
from devolaflow.gate.profiles import AUDIT, PROFILES, RELAXED, STANDARD, STRICT
from devolaflow.gate.reporter import generate_markdown_report, generate_yaml_report
from devolaflow.gate.scorer import (
    composite_score,
    evaluate_gate,
    quality_score,
    score_acceptance_readiness,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_finding(severity: str, fid: str = "F001") -> Finding:
    return Finding(
        finding_id=fid,
        severity=severity,  # type: ignore[arg-type]
        category="test",
        location="src/foo.py:1",
        description="test finding",
    )


def _pass_input() -> GateInput:
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        review_findings=[],
        acceptance_criteria_results=CheckResult(status="pass"),
    )


def _round(num: int, score: float, blockers: int = 0, criticals: int = 0) -> ConvergenceRound:
    return ConvergenceRound(
        round_num=num,
        composite_score=score,
        blocker_count=blockers,
        critical_count=criticals,
        timestamp="2026-04-04T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# 1. quality_score — empty findings
# ---------------------------------------------------------------------------


class TestQualityScore:
    def test_quality_score_empty_findings(self) -> None:
        assert quality_score([]) == 100.0

    def test_quality_score_with_findings(self) -> None:
        findings = [
            _make_finding("blocker", "F001"),
            _make_finding("critical", "F002"),
            _make_finding("major", "F003"),
            _make_finding("minor", "F004"),
            _make_finding("info", "F005"),
        ]
        expected = max(0, 100 - (25 * 1 + 15 * 1 + 5 * 1 + 1 * 1 + 0 * 1))
        assert quality_score(findings) == expected  # 100 - 46 = 54

    def test_quality_score_clamps_at_zero(self) -> None:
        findings = [_make_finding("blocker", f"F{i:03d}") for i in range(10)]
        assert quality_score(findings) == 0.0


# ---------------------------------------------------------------------------
# 3. composite_score — design_agent_hierarchy.md §7.1 example
# ---------------------------------------------------------------------------


class TestCompositeScore:
    def test_composite_score_example(self) -> None:
        """88×0.3 + 92×0.3 + 85×0.4 = 88.0"""
        dims = {"code_review": 88.0, "security": 92.0, "architecture": 85.0}
        weights = {"code_review": 0.3, "security": 0.3, "architecture": 0.4}
        assert composite_score(dims, weights) == 88.0

    def test_composite_score_defaults(self) -> None:
        dims = {
            "test_quality": 100.0,
            "code_review": 100.0,
            "architecture": 100.0,
            "benchmark": 100.0,
        }
        assert composite_score(dims) == 100.0


# ---------------------------------------------------------------------------
# 4-5. evaluate_gate — standard mode
# ---------------------------------------------------------------------------


class TestGateStandard:
    def test_gate_pass_standard(self) -> None:
        verdict = evaluate_gate(_pass_input(), STANDARD, gate_type="standard")
        assert verdict.decision == "PASS"
        assert verdict.meets_threshold is True

    def test_gate_fail_blockers(self) -> None:
        gi = _pass_input()
        gi.review_findings = [_make_finding("blocker")]
        verdict = evaluate_gate(gi, STANDARD, gate_type="standard")
        assert verdict.decision == "FAIL"
        assert "blockers" in verdict.rationale

    def test_gate_fail_build(self) -> None:
        gi = _pass_input()
        gi.build_status = CheckResult(status="fail")
        verdict = evaluate_gate(gi, STANDARD, gate_type="standard")
        assert verdict.decision == "FAIL"

    def test_gate_passthrough(self) -> None:
        verdict = evaluate_gate(_pass_input(), STANDARD, gate_type="passthrough")
        assert verdict.decision == "PASS"
        assert "Passthrough" in verdict.rationale


# ---------------------------------------------------------------------------
# 6-7. evaluate_gate — convergence mode
# ---------------------------------------------------------------------------


class TestGateConvergence:
    def test_gate_convergence_pass(self) -> None:
        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(
                status="pass",
                details={"coverage_pct": 95, "tests_passed": 50, "tests_total": 50},
            ),
            lint_status=CheckResult(status="pass", details={"architecture_score": 90}),
            review_findings=[],
        )
        history = [_round(1, 80.0)]
        verdict = evaluate_gate(
            gi,
            STANDARD,
            round_num=2,
            history=history,
            gate_type="convergence",
        )
        assert verdict.decision == "PASS"
        assert verdict.composite_score is not None
        assert verdict.composite_score >= STANDARD.composite_threshold

    def test_gate_convergence_escalate(self) -> None:
        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(status="pass", details={"coverage_pct": 60}),
            lint_status=CheckResult(status="pass"),
            review_findings=[_make_finding("major", f"F{i:03d}") for i in range(10)],
        )
        history = [_round(1, 50.0), _round(2, 50.0)]
        verdict = evaluate_gate(
            gi,
            STANDARD,
            round_num=3,
            history=history,
            gate_type="convergence",
        )
        assert verdict.decision == "ESCALATE"


# ---------------------------------------------------------------------------
# 8-9. convergence helpers
# ---------------------------------------------------------------------------


class TestConvergence:
    def test_stagnation_detection(self) -> None:
        history = [_round(1, 80.0), _round(2, 80.0)]
        assert detect_stagnation(history) is True

    def test_stagnation_not_detected_if_improving(self) -> None:
        history = [_round(1, 80.0), _round(2, 85.0)]
        assert detect_stagnation(history) is False

    def test_stagnation_not_detected_single_round(self) -> None:
        assert detect_stagnation([_round(1, 80.0)]) is False

    def test_trend_improving(self) -> None:
        history = [_round(1, 70.0), _round(2, 80.0)]
        assert compute_trend(history) == "improving"

    def test_trend_degrading(self) -> None:
        history = [_round(1, 80.0), _round(2, 70.0)]
        assert compute_trend(history) == "degrading"

    def test_trend_stagnant(self) -> None:
        history = [_round(1, 80.0), _round(2, 80.0)]
        assert compute_trend(history) == "stagnant"

    def test_trend_single_round(self) -> None:
        assert compute_trend([_round(1, 80.0)]) == "stagnant"


# ---------------------------------------------------------------------------
# 10. profiles thresholds
# ---------------------------------------------------------------------------


class TestProfiles:
    def test_profiles_thresholds(self) -> None:
        assert STRICT.composite_threshold == 90
        assert STRICT.coverage_threshold == 85
        assert STRICT.max_blocker == 0
        assert STRICT.max_critical == 0
        assert STRICT.max_rounds == 4
        assert STRICT.min_rounds == 2

        assert STANDARD.composite_threshold == 85
        assert STANDARD.coverage_threshold == 80
        assert STANDARD.max_blocker == 0
        assert STANDARD.max_critical == 2
        assert STANDARD.max_rounds == 3
        assert STANDARD.min_rounds == 1

        assert RELAXED.composite_threshold == 70
        assert RELAXED.coverage_threshold == 60
        assert RELAXED.max_blocker == 0
        assert RELAXED.max_critical == 5
        assert RELAXED.max_rounds == 2
        assert RELAXED.min_rounds == 1

        assert AUDIT.composite_threshold == 95
        assert AUDIT.coverage_threshold == 90
        assert AUDIT.max_blocker == 0
        assert AUDIT.max_critical == 0
        assert AUDIT.max_rounds == 6
        assert AUDIT.min_rounds == 3

    def test_profiles_dict(self) -> None:
        assert set(PROFILES) == {"strict", "standard", "relaxed", "audit"}
        assert PROFILES["strict"] is STRICT


# ---------------------------------------------------------------------------
# 11. report generation
# ---------------------------------------------------------------------------


class TestReporter:
    def test_markdown_report_format(self) -> None:
        verdict = GateVerdict(
            decision="PASS",
            rationale="All good.",
            composite_score=88.0,
            meets_threshold=True,
        )
        checks = {
            "build": CheckResult(status="pass", details={"command": "make build"}),
            "test": CheckResult(status="pass", details={"tests_total": 10, "tests_passed": 10}),
        }
        history = [_round(1, 80.0), _round(2, 88.0)]
        md = generate_markdown_report(
            verdict,
            checks,
            history,
            STANDARD,
            stage_id="S04",
            stage_name="implement",
            gate_type="convergence",
        )
        assert "# Gate Report:" in md
        assert "## Summary" in md
        assert "## Check Results" in md
        assert "## Convergence History" in md
        assert "## Decision" in md
        assert "**PASS**" in md

    def test_yaml_report_structure(self) -> None:
        verdict = GateVerdict(decision="FAIL", rationale="Tests failed.", meets_threshold=False)
        checks = {"build": CheckResult(status="pass"), "test": CheckResult(status="fail")}
        yml = generate_yaml_report(
            verdict,
            checks,
            profile=STANDARD,
            stage_id="S04",
            stage_name="implement",
        )
        assert "gate_report:" in yml
        assert "decision: FAIL" in yml
        assert "stage_id: S04" in yml


# ---------------------------------------------------------------------------
# 12. acceptance readiness gate
# ---------------------------------------------------------------------------


def _make_criterion(
    cid: str,
    text: str,
    *,
    testability: float = 85.0,
    completeness: float = 85.0,
    measurability: float = 85.0,
    independence: float = 85.0,
    clarity: float = 85.0,
) -> AcceptanceCriterionResult:
    return AcceptanceCriterionResult(
        criterion_id=cid,
        text=text,
        testability=testability,
        completeness=completeness,
        measurability=measurability,
        independence=independence,
        clarity=clarity,
    )


class TestAcceptanceReadinessGate:
    def test_acceptance_readiness_pass(self) -> None:
        """High-quality criteria should pass the standard profile threshold."""
        criteria = [
            _make_criterion(
                "AC-1",
                "All pytest tests pass with 0 failures",
                testability=95,
                completeness=85,
                measurability=90,
                clarity=92,
                independence=88,
            ),
            _make_criterion(
                "AC-2",
                "Code coverage >= 85%",
                testability=90,
                completeness=80,
                measurability=95,
                clarity=90,
                independence=90,
            ),
        ]
        gi = _pass_input()
        gi.acceptance_readiness_criteria = criteria

        verdict = evaluate_gate(gi, STANDARD, gate_type="acceptance_readiness")

        assert verdict.decision == "PASS"
        assert verdict.meets_threshold is True
        assert verdict.composite_score is not None
        assert verdict.composite_score >= STANDARD.acceptance_readiness_threshold

    def test_acceptance_readiness_fail(self) -> None:
        """Vague criteria should fail and report failing dimensions."""
        criteria = [
            _make_criterion(
                "AC-1",
                "Code should work correctly",
                testability=15,
                completeness=20,
                measurability=10,
                clarity=25,
                independence=50,
            ),
        ]
        gi = _pass_input()
        gi.acceptance_readiness_criteria = criteria

        verdict = evaluate_gate(gi, STANDARD, gate_type="acceptance_readiness")

        assert verdict.decision == "FAIL"
        assert verdict.meets_threshold is False
        assert verdict.composite_score is not None
        assert verdict.composite_score < STANDARD.acceptance_readiness_threshold
        assert "failing_dimensions" in verdict.details
        assert "suggestions" in verdict.details
        assert len(verdict.details["suggestions"]) > 0

    def test_acceptance_readiness_missing_criteria(self) -> None:
        """Empty criteria list should fail immediately."""
        gi = _pass_input()
        gi.acceptance_readiness_criteria = []

        verdict = evaluate_gate(gi, STANDARD, gate_type="acceptance_readiness")

        assert verdict.decision == "FAIL"
        assert verdict.composite_score == 0.0
        assert verdict.meets_threshold is False
        assert "No acceptance criteria" in verdict.rationale

    def test_acceptance_readiness_relaxed_vs_strict(self) -> None:
        """Same criteria should pass relaxed but fail strict profile."""
        criteria = [
            _make_criterion(
                "AC-1",
                "Function returns correct output",
                testability=75,
                completeness=72,
                measurability=70,
                clarity=78,
                independence=80,
            ),
        ]

        verdict_relaxed = score_acceptance_readiness(criteria, RELAXED)
        assert verdict_relaxed.decision == "PASS"
        assert verdict_relaxed.composite_score >= RELAXED.acceptance_readiness_threshold

        verdict_strict = score_acceptance_readiness(criteria, STRICT)
        assert verdict_strict.decision == "FAIL"
        assert verdict_strict.composite_score < STRICT.acceptance_readiness_threshold
