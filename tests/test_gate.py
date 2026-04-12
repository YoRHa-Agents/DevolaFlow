"""Comprehensive tests for the gate quality mechanism.

Design ref: design_decomposition_gate.md §5
"""

from __future__ import annotations

from dataclasses import replace

from devolaflow.gate.convergence import compute_trend, detect_stagnation
from devolaflow.gate.models import (
    GATE_TYPE_ALIASES,
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
    _resolve_gate_type,
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


# ---------------------------------------------------------------------------
# 13. gate type alias resolution
# ---------------------------------------------------------------------------


class TestGateTypeAliases:
    def test_standard_resolves_to_revision(self) -> None:
        assert _resolve_gate_type("standard") == "revision"

    def test_convergence_resolves_to_revision(self) -> None:
        assert _resolve_gate_type("convergence") == "revision"

    def test_canonical_types_unchanged(self) -> None:
        for canonical in ("preflight", "revision", "escalation", "abort", "passthrough"):
            assert _resolve_gate_type(canonical) == canonical

    def test_alias_dict_matches(self) -> None:
        assert GATE_TYPE_ALIASES == {"standard": "revision", "convergence": "revision"}


# ---------------------------------------------------------------------------
# 14. preflight gate
# ---------------------------------------------------------------------------


def _security_finding(fid: str = "F100") -> Finding:
    return Finding(
        finding_id=fid,
        severity="blocker",
        category="security",
        location="src/auth.py:42",
        description="hardcoded secret",
    )


class TestPreflightGate:
    def test_preflight_pass_clean(self) -> None:
        verdict = evaluate_gate(_pass_input(), STANDARD, gate_type="preflight")
        assert verdict.decision == "PASS"
        assert verdict.meets_threshold is True

    def test_preflight_fail_abort_category(self) -> None:
        gi = _pass_input()
        gi.review_findings = [_security_finding()]
        verdict = evaluate_gate(gi, STANDARD, gate_type="preflight")
        assert verdict.decision == "FAIL"
        assert "security" in verdict.rationale
        assert verdict.escalation_context != ""
        assert "security" in verdict.escalation_context

    def test_preflight_fail_build(self) -> None:
        gi = _pass_input()
        gi.build_status = CheckResult(status="fail")
        verdict = evaluate_gate(gi, STANDARD, gate_type="preflight")
        assert verdict.decision == "FAIL"
        assert "build" in verdict.rationale

    def test_preflight_abort_category_takes_priority(self) -> None:
        """Abort-category findings are reported even if basic checks also fail."""
        gi = _pass_input()
        gi.build_status = CheckResult(status="fail")
        gi.review_findings = [_security_finding()]
        verdict = evaluate_gate(gi, STANDARD, gate_type="preflight")
        assert verdict.decision == "FAIL"
        assert verdict.escalation_context != ""


# ---------------------------------------------------------------------------
# 15. abort gate
# ---------------------------------------------------------------------------


class TestAbortGate:
    def test_abort_escalates_on_abort_category(self) -> None:
        gi = _pass_input()
        gi.review_findings = [_security_finding("F200")]
        verdict = evaluate_gate(gi, STANDARD, gate_type="abort")
        assert verdict.decision == "ESCALATE"
        assert "security" in verdict.rationale
        assert verdict.post_mortem["abort_categories_found"] == ["security"]
        assert verdict.post_mortem["finding_count"] == 1
        assert "F200" in verdict.post_mortem["findings"]

    def test_abort_pass_no_abort_category(self) -> None:
        gi = _pass_input()
        gi.review_findings = [_make_finding("major")]
        verdict = evaluate_gate(gi, STANDARD, gate_type="abort")
        assert verdict.decision == "PASS"

    def test_abort_multiple_categories(self) -> None:
        gi = _pass_input()
        gi.review_findings = [
            _security_finding("F300"),
            Finding(
                finding_id="F301",
                severity="blocker",
                category="data_loss",
                location="src/db.py:10",
                description="unprotected delete",
            ),
        ]
        verdict = evaluate_gate(gi, STANDARD, gate_type="abort")
        assert verdict.decision == "ESCALATE"
        assert set(verdict.post_mortem["abort_categories_found"]) == {"security", "data_loss"}
        assert verdict.post_mortem["finding_count"] == 2


# ---------------------------------------------------------------------------
# 16. escalation gate
# ---------------------------------------------------------------------------


class TestEscalationGate:
    def test_escalation_pass(self) -> None:
        verdict = evaluate_gate(_pass_input(), STANDARD, gate_type="escalation")
        assert verdict.decision == "PASS"
        assert verdict.escalation_context == ""

    def test_escalation_fail_adds_context(self) -> None:
        gi = _pass_input()
        gi.build_status = CheckResult(status="fail")
        verdict = evaluate_gate(gi, STANDARD, gate_type="escalation")
        assert verdict.decision == "FAIL"
        assert verdict.escalation_context != ""
        assert "Escalation gate failed" in verdict.escalation_context


# ---------------------------------------------------------------------------
# 17. backward compatibility — "standard" and "convergence" aliases
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_standard_alias_pass(self) -> None:
        verdict = evaluate_gate(_pass_input(), STANDARD, gate_type="standard")
        assert verdict.decision == "PASS"
        assert verdict.meets_threshold is True

    def test_standard_alias_fail(self) -> None:
        gi = _pass_input()
        gi.review_findings = [_make_finding("blocker")]
        verdict = evaluate_gate(gi, STANDARD, gate_type="standard")
        assert verdict.decision == "FAIL"
        assert "blockers" in verdict.rationale

    def test_convergence_alias_with_history(self) -> None:
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
        verdict = evaluate_gate(gi, STANDARD, round_num=2, history=history, gate_type="convergence")
        assert verdict.decision == "PASS"
        assert verdict.composite_score is not None

    def test_revision_direct_no_history(self) -> None:
        verdict = evaluate_gate(_pass_input(), STANDARD, gate_type="revision")
        assert verdict.decision == "PASS"


# ---------------------------------------------------------------------------
# 18. GateVerdict default fields
# ---------------------------------------------------------------------------


class TestGateVerdictDefaults:
    def test_escalation_context_default(self) -> None:
        v = GateVerdict(decision="PASS", rationale="ok")
        assert v.escalation_context == ""

    def test_post_mortem_default(self) -> None:
        v = GateVerdict(decision="PASS", rationale="ok")
        assert v.post_mortem == {}

    def test_advisor_fields_default(self) -> None:
        v = GateVerdict(decision="PASS", rationale="ok")
        assert v.advisor_recommended is False
        assert v.advisor_verdict == ""
        assert v.advisor_context == ""

    def test_details_default(self) -> None:
        v = GateVerdict(decision="PASS", rationale="ok")
        assert v.details == {}


# ---------------------------------------------------------------------------
# 19. advisor borderline detection
# ---------------------------------------------------------------------------


def _convergence_input(coverage_pct: float, architecture_score: float) -> GateInput:
    """Build a GateInput that produces a predictable composite score.

    With no findings (code_review=100) and no benchmark_score (defaults to 100):
    composite = coverage_pct * 0.30 + 100 * 0.30 + arch * 0.20 + 100 * 0.20
    """
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(
            status="pass",
            details={"coverage_pct": coverage_pct},
        ),
        lint_status=CheckResult(
            status="pass",
            details={"architecture_score": architecture_score},
        ),
        review_findings=[],
    )


class TestAdvisorBorderlineDetection:
    def test_borderline_score_triggers_advisor(self) -> None:
        """Score 82 with threshold 85 → margin 3 <= 5 → advisor_recommended."""
        gi = _convergence_input(coverage_pct=64, architecture_score=64)
        history = [_round(1, 75.0)]
        verdict = evaluate_gate(gi, STANDARD, round_num=2, history=history, gate_type="convergence")
        assert verdict.composite_score is not None
        assert abs(verdict.composite_score - 82.0) < 0.1
        assert verdict.advisor_recommended is True
        assert verdict.advisor_context != ""
        assert "±5.0" in verdict.advisor_context

    def test_clear_pass_no_advisor(self) -> None:
        """Score 95 with threshold 85 → margin 10 > 5 → no advisor."""
        gi = _convergence_input(coverage_pct=90, architecture_score=90)
        history = [_round(1, 80.0)]
        verdict = evaluate_gate(gi, STANDARD, round_num=2, history=history, gate_type="convergence")
        assert verdict.decision == "PASS"
        assert verdict.composite_score is not None
        assert abs(verdict.composite_score - 95.0) < 0.1
        assert verdict.advisor_recommended is False
        assert verdict.advisor_context == ""

    def test_clear_fail_no_advisor(self) -> None:
        """Score 70 with threshold 85 → margin 15 > 5 → no advisor."""
        gi = _convergence_input(coverage_pct=40, architecture_score=40)
        history = [_round(1, 60.0)]
        verdict = evaluate_gate(gi, STANDARD, round_num=2, history=history, gate_type="convergence")
        assert verdict.decision == "FAIL"
        assert verdict.composite_score is not None
        assert abs(verdict.composite_score - 70.0) < 0.1
        assert verdict.advisor_recommended is False
        assert verdict.advisor_context == ""

    def test_advisor_margin_zero_disables_detection(self) -> None:
        """advisor_margin=0 disables borderline detection even for borderline scores."""
        profile = replace(STANDARD, advisor_margin=0)
        gi = _convergence_input(coverage_pct=64, architecture_score=64)
        history = [_round(1, 75.0)]
        verdict = evaluate_gate(gi, profile, round_num=2, history=history, gate_type="convergence")
        assert verdict.composite_score is not None
        assert abs(verdict.composite_score - 82.0) < 0.1
        assert verdict.advisor_recommended is False
        assert verdict.advisor_context == ""
