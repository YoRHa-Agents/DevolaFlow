"""Comprehensive tests for the v8.0.0 P-05 verification ladder.

Covers:

- All 6 rungs (R1 lint / R2 typecheck / R3 unit_test / R4 integration_test
  / R5 benchmark / R6 convergence) — pass / fail / skip paths.
- Short-circuit semantics — R3 fail ⇒ R4/R5/R6 not executed (mock-verified
  per ``patch_plan §3 P-05 AC #1/#2``).
- ``profile.ladder_enabled=False`` ⇒ ``evaluate_ladder`` byte-identical
  to ``evaluate_gate`` (``patch_plan §3 P-05 AC #3``).
- Profile-driven enable: STRICT/AUDIT default ``True``; STANDARD/RELAXED
  default ``False``.
- Verdict aggregation: PASS / FAIL / ESCALATE; ``details['ladder']``
  schema; ``ladder_short_circuit`` flag; ``first_failing_rung``.
- ``rung_overrides`` injection — both :class:`LadderEvaluation` and
  :class:`CheckResult` return shapes.
- Edge cases: empty extra_checks, all-skip ladder, integration fallback
  to ``acceptance_criteria_results``, benchmark threshold computation.

Target: 100 % line coverage on the v8.0.0 P-05 ladder code path in
``src/devolaflow/gate/scorer.py``.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from devolaflow.gate.models import (
    LADDER_RUNG_NAMES,
    LADDER_RUNG_ORDER,
    CheckResult,
    ConvergenceRound,
    Finding,
    GateInput,
    LadderEvaluation,
    LadderRung,
)
from devolaflow.gate.profiles import AUDIT, PROFILES, RELAXED, STANDARD, STRICT
from devolaflow.gate.scorer import (
    _check_benchmark,
    _check_convergence,
    _check_integration,
    _check_lint,
    _check_typecheck,
    _check_unit_test,
    _ladder_skip,
    _wrap_check_result,
    evaluate_gate,
    evaluate_ladder,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _pass_input(**overrides: object) -> GateInput:
    """All-PASS gate input shaped for ladder evaluation."""
    base = GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        review_findings=[],
        acceptance_criteria_results=CheckResult(status="pass"),
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _round(num: int, score: float) -> ConvergenceRound:
    return ConvergenceRound(
        round_num=num,
        composite_score=score,
        blocker_count=0,
        critical_count=0,
        timestamp="2026-04-21T00:00:00Z",
    )


def _ladder_entries(verdict_details: dict[str, object]) -> list[dict[str, object]]:
    ladder = verdict_details["ladder"]
    assert isinstance(ladder, list)
    return list(ladder)


# ---------------------------------------------------------------------------
# 1. profile-driven enable defaults
# ---------------------------------------------------------------------------


class TestProfileLadderDefaults:
    """``patch_plan §3 P-05`` — STRICT/AUDIT=True, STANDARD/RELAXED=False."""

    def test_strict_enabled(self) -> None:
        assert STRICT.ladder_enabled is True

    def test_audit_enabled(self) -> None:
        assert AUDIT.ladder_enabled is True

    def test_standard_disabled(self) -> None:
        assert STANDARD.ladder_enabled is False

    def test_relaxed_disabled(self) -> None:
        assert RELAXED.ladder_enabled is False

    def test_profiles_dict_contains_all_four(self) -> None:
        assert {"strict", "standard", "relaxed", "audit"} <= set(PROFILES)


# ---------------------------------------------------------------------------
# 2. ladder_enabled=False ⇒ byte-identical to evaluate_gate (AC #3)
# ---------------------------------------------------------------------------


class TestLadderDisabledByteIdentical:
    """``patch_plan §3 P-05 AC #3`` — disabled ladder must delegate verbatim."""

    def test_disabled_pass_input_byte_identical(self) -> None:
        gi = _pass_input()
        v_gate = evaluate_gate(gi, STANDARD)
        v_ladder = evaluate_ladder(gi, STANDARD)
        assert v_gate.decision == v_ladder.decision
        assert v_gate.rationale == v_ladder.rationale
        assert v_gate.composite_score == v_ladder.composite_score
        assert v_gate.meets_threshold == v_ladder.meets_threshold
        assert v_gate.details == v_ladder.details
        assert v_gate.escalation_context == v_ladder.escalation_context

    def test_disabled_fail_input_byte_identical(self) -> None:
        gi = _pass_input()
        gi.lint_status = CheckResult(status="fail", details={"file": "x.py", "msg": "E1"})
        v_gate = evaluate_gate(gi, RELAXED)
        v_ladder = evaluate_ladder(gi, RELAXED)
        assert v_gate.decision == v_ladder.decision == "FAIL"
        assert v_gate.rationale == v_ladder.rationale
        assert v_gate.details == v_ladder.details

    def test_disabled_propagates_breaker_kwargs(self) -> None:
        from devolaflow.gate.budget import TokenBudgetBreaker

        gi = _pass_input()
        breaker = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        v_gate = evaluate_gate(gi, STANDARD, breaker=breaker, cumulative_tokens=15_000)
        v_ladder = evaluate_ladder(gi, STANDARD, breaker=breaker, cumulative_tokens=15_000)
        assert v_gate.decision == v_ladder.decision == "FAIL"
        assert v_gate.rationale == v_ladder.rationale
        assert v_gate.details == v_ladder.details

    def test_disabled_propagates_history(self) -> None:
        gi = _pass_input()
        gi.test_results = CheckResult(status="pass", details={"coverage_pct": 95})
        gi.lint_status = CheckResult(status="pass", details={"architecture_score": 90})
        history = [_round(1, 80.0)]
        v_gate = evaluate_gate(gi, STANDARD, round_num=2, history=history, gate_type="convergence")
        v_ladder = evaluate_ladder(
            gi, STANDARD, round_num=2, history=history, gate_type="convergence"
        )
        assert v_gate.decision == v_ladder.decision
        assert v_gate.composite_score == v_ladder.composite_score
        assert v_gate.details == v_ladder.details


# ---------------------------------------------------------------------------
# 3. ladder_enabled=True ⇒ all-pass walk through R1..R6
# ---------------------------------------------------------------------------


class TestLadderAllPassWalk:
    def test_all_six_rungs_walked(self) -> None:
        gi = _pass_input()
        verdict = evaluate_ladder(gi, STRICT)
        assert verdict.decision == "PASS"
        entries = _ladder_entries(verdict.details)
        assert len(entries) == 6
        rungs_seen = [e["rung"] for e in entries]
        assert rungs_seen == [r.value for r in LADDER_RUNG_ORDER]
        assert verdict.details["ladder_short_circuit"] is False
        assert verdict.details["first_failing_rung"] is None
        # R6 ran (status='pass'); composite_score follows _evaluate_standard
        # semantics (None for standard gate type — see evaluate_gate body).
        assert entries[5]["status"] == "pass"

    def test_convergence_gate_type_populates_composite(self) -> None:
        # When R6 uses gate_type='convergence' with history, the inner
        # evaluate_gate call produces a numeric composite_score that
        # propagates onto the ladder verdict.
        gi = _pass_input()
        gi.test_results = CheckResult(status="pass", details={"coverage_pct": 95})
        gi.lint_status = CheckResult(status="pass", details={"architecture_score": 90})
        history = [_round(1, 80.0)]
        verdict = evaluate_ladder(gi, STRICT, round_num=2, history=history, gate_type="convergence")
        assert verdict.decision == "PASS"
        assert verdict.composite_score is not None
        assert verdict.composite_score >= STRICT.composite_threshold

    def test_all_pass_rationale_summary_format(self) -> None:
        gi = _pass_input()
        verdict = evaluate_ladder(gi, STRICT)
        for rung in LADDER_RUNG_ORDER:
            # Every rung tag should appear in the rationale summary line.
            assert f"{rung.value}=" in verdict.rationale
        assert verdict.rationale.startswith("Verification ladder PASS")

    def test_all_pass_meets_threshold(self) -> None:
        verdict = evaluate_ladder(_pass_input(), STRICT)
        assert verdict.meets_threshold is True
        assert verdict.decision == "PASS"


# ---------------------------------------------------------------------------
# 4. R1 lint rung — pass / fail / skip + short-circuit
# ---------------------------------------------------------------------------


class TestR1Lint:
    def test_r1_pass_inline(self) -> None:
        ev = _check_lint(_pass_input(), STRICT)
        assert ev.rung is LadderRung.R1
        assert ev.status == "pass"
        assert ev.name == "lint"

    def test_r1_skip_when_lint_skipped(self) -> None:
        gi = _pass_input()
        gi.lint_status = CheckResult(status="skip")
        ev = _check_lint(gi, STRICT)
        assert ev.status == "skip"
        assert "skipped" in ev.message

    def test_r1_fail_short_circuits_r2_to_r6(self) -> None:
        gi = _pass_input()
        gi.lint_status = CheckResult(status="fail", details={"file": "src/a.py", "msg": "E1"})
        verdict = evaluate_ladder(gi, STRICT)
        entries = _ladder_entries(verdict.details)
        assert verdict.decision == "FAIL"
        assert entries[0]["status"] == "fail"
        assert entries[0]["rung"] == LadderRung.R1.value
        for entry in entries[1:]:
            assert entry["status"] == "skip"
            assert "short-circuited by failing rung R1" in entry["message"]
        assert verdict.details["first_failing_rung"] == LadderRung.R1.value
        assert verdict.details["ladder_short_circuit"] is True


# ---------------------------------------------------------------------------
# 5. R2 typecheck rung — opt-in via extra_checks
# ---------------------------------------------------------------------------


class TestR2Typecheck:
    def test_r2_skip_when_not_provided(self) -> None:
        ev = _check_typecheck(_pass_input(), STRICT, extra_checks=None)
        assert ev.rung is LadderRung.R2
        assert ev.status == "skip"
        assert "not provided" in ev.message

    def test_r2_skip_when_status_skip(self) -> None:
        ev = _check_typecheck(
            _pass_input(),
            STRICT,
            extra_checks={"typecheck": CheckResult(status="skip")},
        )
        assert ev.status == "skip"

    def test_r2_pass_when_status_pass(self) -> None:
        ev = _check_typecheck(
            _pass_input(),
            STRICT,
            extra_checks={"typecheck": CheckResult(status="pass", details={"errors": 0})},
        )
        assert ev.status == "pass"
        assert ev.details == {"errors": 0}

    def test_r2_fail_short_circuits_r3_to_r6(self) -> None:
        gi = _pass_input()
        verdict = evaluate_ladder(
            gi,
            STRICT,
            extra_checks={
                "typecheck": CheckResult(status="fail", details={"errors": 7, "file": "a.py"})
            },
        )
        entries = _ladder_entries(verdict.details)
        assert verdict.decision == "FAIL"
        assert entries[0]["status"] == "pass"  # R1 lint pass
        assert entries[1]["status"] == "fail"  # R2 typecheck fail
        for entry in entries[2:]:
            assert entry["status"] == "skip"
        assert verdict.details["first_failing_rung"] == LadderRung.R2.value


# ---------------------------------------------------------------------------
# 6. R3 unit_test rung — short-circuits R4/R5/R6 (CRITICAL AC #2)
# ---------------------------------------------------------------------------


class TestR3UnitTestShortCircuit:
    """``patch_plan §3 P-05 AC #2`` — R3 fail ⇒ R4/R5/R6 NOT executed."""

    def test_r3_pass_inline(self) -> None:
        ev = _check_unit_test(_pass_input(), STRICT)
        assert ev.status == "pass"
        assert ev.rung is LadderRung.R3
        assert ev.name == "unit_test"

    def test_r3_skip_when_status_skip(self) -> None:
        gi = _pass_input()
        gi.test_results = CheckResult(status="skip")
        ev = _check_unit_test(gi, STRICT)
        assert ev.status == "skip"

    def test_r3_fail_does_not_invoke_r4_r5_r6_overrides(self) -> None:
        # Build mock checkers for R4, R5, R6 that record invocation.
        invocations: dict[LadderRung, int] = {
            LadderRung.R4: 0,
            LadderRung.R5: 0,
            LadderRung.R6: 0,
        }

        def make_spy(rung: LadderRung):
            def spy(_gi, _profile, **_kwargs) -> LadderEvaluation:
                invocations[rung] += 1
                return LadderEvaluation(rung=rung, status="pass", message="spy")

            return spy

        gi = _pass_input()
        gi.test_results = CheckResult(status="fail", details={"failed": 3})
        verdict = evaluate_ladder(
            gi,
            STRICT,
            rung_overrides={
                LadderRung.R4: make_spy(LadderRung.R4),
                LadderRung.R5: make_spy(LadderRung.R5),
                LadderRung.R6: make_spy(LadderRung.R6),
            },
        )
        # AC #2 — R4/R5/R6 must NOT be executed when R3 fails.
        assert invocations[LadderRung.R4] == 0
        assert invocations[LadderRung.R5] == 0
        assert invocations[LadderRung.R6] == 0
        # Verdict reflects R3 failure with short-circuit.
        entries = _ladder_entries(verdict.details)
        assert verdict.decision == "FAIL"
        assert entries[2]["status"] == "fail"
        assert entries[2]["rung"] == LadderRung.R3.value
        for entry in entries[3:]:
            assert entry["status"] == "skip"
        assert verdict.details["first_failing_rung"] == LadderRung.R3.value
        # composite_score stays None — R6 never produced one.
        assert verdict.composite_score is None

    def test_r3_fail_rationale_calls_out_first_failure(self) -> None:
        gi = _pass_input()
        gi.test_results = CheckResult(status="fail", details={"reason": "assertion"})
        verdict = evaluate_ladder(gi, STRICT)
        assert "first failure at R3" in verdict.rationale
        assert "unit_test" in verdict.rationale


# ---------------------------------------------------------------------------
# 7. R4 integration rung — extra_checks first, AC fallback
# ---------------------------------------------------------------------------


class TestR4Integration:
    def test_r4_skip_when_no_signal(self) -> None:
        gi = _pass_input(acceptance_criteria_results=None)
        ev = _check_integration(gi, STRICT, extra_checks=None)
        assert ev.status == "skip"
        assert "not provided" in ev.message

    def test_r4_uses_acceptance_criteria_fallback(self) -> None:
        gi = _pass_input()
        gi.acceptance_criteria_results = CheckResult(status="pass", details={"covered": 3})
        ev = _check_integration(gi, STRICT, extra_checks=None)
        assert ev.status == "pass"
        assert ev.details == {"covered": 3}

    def test_r4_extra_checks_wins_over_acceptance(self) -> None:
        gi = _pass_input()
        gi.acceptance_criteria_results = CheckResult(status="pass")
        ev = _check_integration(
            gi,
            STRICT,
            extra_checks={"integration_test": CheckResult(status="fail", details={"x": 1})},
        )
        assert ev.status == "fail"
        assert ev.details == {"x": 1}

    def test_r4_skip_when_status_skip(self) -> None:
        gi = _pass_input()
        gi.acceptance_criteria_results = CheckResult(status="skip")
        ev = _check_integration(gi, STRICT, extra_checks=None)
        assert ev.status == "skip"


# ---------------------------------------------------------------------------
# 8. R5 benchmark rung — extra_checks first, build_status fallback,
#    threshold compare
# ---------------------------------------------------------------------------


class TestR5Benchmark:
    def test_r5_skip_when_no_signal(self) -> None:
        ev = _check_benchmark(_pass_input(), STRICT, extra_checks=None)
        assert ev.status == "skip"

    def test_r5_uses_extra_checks_pass(self) -> None:
        ev = _check_benchmark(
            _pass_input(),
            STRICT,
            extra_checks={"benchmark": CheckResult(status="pass", details={"score": 95})},
        )
        assert ev.status == "pass"

    def test_r5_uses_extra_checks_fail(self) -> None:
        ev = _check_benchmark(
            _pass_input(),
            STRICT,
            extra_checks={"benchmark": CheckResult(status="fail", details={"score": 50})},
        )
        assert ev.status == "fail"

    def test_r5_extra_checks_skip(self) -> None:
        ev = _check_benchmark(
            _pass_input(),
            STRICT,
            extra_checks={"benchmark": CheckResult(status="skip")},
        )
        assert ev.status == "skip"

    def test_r5_build_status_score_below_threshold_fails(self) -> None:
        gi = _pass_input()
        gi.build_status = CheckResult(status="pass", details={"benchmark_score": 50})
        # STRICT.composite_threshold=90 → 50 < 90 → FAIL
        ev = _check_benchmark(gi, STRICT, extra_checks=None)
        assert ev.status == "fail"
        assert ev.details["benchmark_score"] == 50.0
        assert ev.details["threshold"] == 90.0

    def test_r5_build_status_score_at_threshold_passes(self) -> None:
        gi = _pass_input()
        gi.build_status = CheckResult(status="pass", details={"benchmark_score": 90})
        ev = _check_benchmark(gi, STRICT, extra_checks=None)
        assert ev.status == "pass"


# ---------------------------------------------------------------------------
# 9. R6 convergence rung — delegates to evaluate_gate
# ---------------------------------------------------------------------------


class TestR6Convergence:
    def test_r6_pass_passthrough_gate(self) -> None:
        ev = _check_convergence(_pass_input(), STRICT, gate_type="passthrough")
        assert ev.rung is LadderRung.R6
        assert ev.status == "pass"
        assert ev.details["verdict_decision"] == "PASS"

    def test_r6_fail_when_inner_gate_fails(self) -> None:
        gi = _pass_input()
        gi.review_findings = [
            Finding(
                finding_id="F1",
                severity="blocker",
                category="test",
                location="x.py",
                description="d",
            )
        ]
        ev = _check_convergence(gi, STRICT, gate_type="standard")
        assert ev.status == "fail"
        assert ev.details["verdict_decision"] == "FAIL"

    def test_r6_escalate_propagates_through_ladder(self) -> None:
        # Use abort-category finding to force ESCALATE on the inner gate.
        gi = _pass_input()
        gi.review_findings = [
            Finding(
                finding_id="F1",
                severity="blocker",
                category="security",
                location="x.py",
                description="leak",
            )
        ]
        verdict = evaluate_ladder(gi, STRICT, gate_type="abort")
        # All earlier rungs (R1..R5) PASS or SKIP; R6 ⇒ ESCALATE
        assert verdict.decision == "ESCALATE"
        assert "ESCALATE" in verdict.rationale
        # R6 entry carries the inner verdict_decision='ESCALATE' verbatim.
        entries = _ladder_entries(verdict.details)
        assert entries[5]["details"]["verdict_decision"] == "ESCALATE"
        assert verdict.details["first_failing_rung"] == LadderRung.R6.value

    def test_r6_escalate_escalation_context_propagates_when_present(self) -> None:
        # Mock the R6 checker so the inner verdict carries a non-empty
        # escalation_context — the ladder verdict MUST forward it
        # (S-5 — never silently downgrade an escalation).
        def my_r6(_gi, _profile, **_kw):
            return LadderEvaluation(
                rung=LadderRung.R6,
                status="fail",
                message="convergence: ESCALATE — token budget exhausted",
                details={
                    "verdict_decision": "ESCALATE",
                    "composite_score": None,
                    "meets_threshold": False,
                    "escalation_context": "Token budget exhausted: 80001/80000.",
                },
            )

        verdict = evaluate_ladder(
            _pass_input(),
            STRICT,
            rung_overrides={LadderRung.R6: my_r6},
        )
        assert verdict.decision == "ESCALATE"
        assert verdict.escalation_context == "Token budget exhausted: 80001/80000."


# ---------------------------------------------------------------------------
# 10. rung_overrides — LadderEvaluation + CheckResult shapes; type errors
# ---------------------------------------------------------------------------


class TestRungOverrides:
    def test_override_returns_ladder_evaluation(self) -> None:
        def my_r1(_gi, _profile, **_kw):
            return LadderEvaluation(
                rung=LadderRung.R1, status="pass", message="custom", details={"x": 1}
            )

        verdict = evaluate_ladder(_pass_input(), STRICT, rung_overrides={LadderRung.R1: my_r1})
        entries = _ladder_entries(verdict.details)
        assert entries[0]["message"] == "custom"
        assert entries[0]["details"] == {"x": 1}

    def test_override_returns_plain_check_result_is_wrapped(self) -> None:
        def my_r1(_gi, _profile, **_kw):
            return CheckResult(status="pass", details={"message": "wrapped ok"})

        verdict = evaluate_ladder(_pass_input(), STRICT, rung_overrides={LadderRung.R1: my_r1})
        entries = _ladder_entries(verdict.details)
        assert entries[0]["status"] == "pass"
        assert entries[0]["message"] == "wrapped ok"

    def test_override_returning_wrong_rung_raises(self) -> None:
        def bad_override(_gi, _profile, **_kw):
            return LadderEvaluation(rung=LadderRung.R6, status="pass", message="oops")

        with pytest.raises(ValueError, match="rung tag must match the slot"):
            evaluate_ladder(
                _pass_input(),
                STRICT,
                rung_overrides={LadderRung.R1: bad_override},
            )

    def test_override_returning_wrong_type_raises(self) -> None:
        def bad_override(_gi, _profile, **_kw):
            return "not a CheckResult"

        with pytest.raises(TypeError, match="must return LadderEvaluation or CheckResult"):
            evaluate_ladder(
                _pass_input(),
                STRICT,
                rung_overrides={LadderRung.R1: bad_override},
            )


# ---------------------------------------------------------------------------
# 11. helper utilities — _ladder_skip / _wrap_check_result / metadata
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_ladder_skip_carries_reason(self) -> None:
        ev = _ladder_skip(LadderRung.R2, "no input")
        assert ev.status == "skip"
        assert ev.message == "no input"
        assert ev.rung is LadderRung.R2

    def test_wrap_check_result_uses_message_detail(self) -> None:
        ev = _wrap_check_result(
            LadderRung.R3, CheckResult(status="pass", details={"message": "hello"})
        )
        assert ev.status == "pass"
        assert ev.message == "hello"
        assert ev.rung is LadderRung.R3

    def test_wrap_check_result_default_message(self) -> None:
        ev = _wrap_check_result(LadderRung.R4, CheckResult(status="fail", details={}))
        assert "integration_test" in ev.message
        assert ev.status == "fail"

    def test_ladder_rung_names_complete(self) -> None:
        for rung in LADDER_RUNG_ORDER:
            assert rung in LADDER_RUNG_NAMES
        assert LADDER_RUNG_NAMES[LadderRung.R1] == "lint"
        assert LADDER_RUNG_NAMES[LadderRung.R3] == "unit_test"
        assert LADDER_RUNG_NAMES[LadderRung.R6] == "convergence"

    def test_ladder_evaluation_post_init_fills_name(self) -> None:
        ev = LadderEvaluation(rung=LadderRung.R5, status="pass", message="m")
        assert ev.name == "benchmark"

    def test_ladder_evaluation_explicit_name_preserved(self) -> None:
        ev = LadderEvaluation(rung=LadderRung.R5, status="pass", message="m", name="custom")
        assert ev.name == "custom"


# ---------------------------------------------------------------------------
# 12. profile-aware integration — STANDARD opt-in via replace
# ---------------------------------------------------------------------------


class TestProfileOptInIntegration:
    """Tests that any profile can opt in via ``dataclasses.replace``."""

    def test_standard_opt_in_runs_ladder(self) -> None:
        std_with_ladder = replace(STANDARD, ladder_enabled=True)
        gi = _pass_input()
        gi.test_results = CheckResult(status="fail")
        verdict = evaluate_ladder(gi, std_with_ladder)
        # Ladder runs ⇒ details carry ladder schema.
        assert "ladder" in verdict.details
        assert verdict.details["first_failing_rung"] == LadderRung.R3.value

    def test_strict_opt_out_falls_back_to_evaluate_gate(self) -> None:
        strict_no_ladder = replace(STRICT, ladder_enabled=False)
        gi = _pass_input()
        v_gate = evaluate_gate(gi, strict_no_ladder)
        v_ladder = evaluate_ladder(gi, strict_no_ladder)
        assert v_gate.details == v_ladder.details
        assert "ladder" not in v_ladder.details

    def test_audit_default_runs_ladder(self) -> None:
        gi = _pass_input()
        verdict = evaluate_ladder(gi, AUDIT)
        assert "ladder" in verdict.details
        assert verdict.details["ladder_profile"] == "audit"


# ---------------------------------------------------------------------------
# 13. Verdict aggregation edge cases
# ---------------------------------------------------------------------------


class TestVerdictAggregation:
    def test_all_skip_ladder_passes_with_no_composite(self) -> None:
        # Every rung skips: lint=skip, no typecheck/integration/benchmark,
        # test=skip, convergence runs but yields PASS via passthrough.
        gi = _pass_input()
        gi.lint_status = CheckResult(status="skip")
        gi.test_results = CheckResult(status="skip")
        gi.acceptance_criteria_results = None
        gi.build_status = CheckResult(status="skip")
        verdict = evaluate_ladder(gi, STRICT, gate_type="passthrough")
        entries = _ladder_entries(verdict.details)
        # R1, R2, R3, R4, R5 all skip; R6 passes (passthrough).
        statuses = [e["status"] for e in entries]
        assert statuses[:5] == ["skip", "skip", "skip", "skip", "skip"]
        assert statuses[5] == "pass"
        assert verdict.decision == "PASS"
        assert verdict.details["ladder_short_circuit"] is False

    def test_short_circuit_at_r5_reports_first_fail(self) -> None:
        gi = _pass_input()
        gi.build_status = CheckResult(status="pass", details={"benchmark_score": 10})
        # STRICT threshold=90 → score 10 fails R5
        verdict = evaluate_ladder(gi, STRICT)
        entries = _ladder_entries(verdict.details)
        assert verdict.decision == "FAIL"
        assert entries[4]["status"] == "fail"
        assert entries[5]["status"] == "skip"
        assert verdict.details["first_failing_rung"] == LadderRung.R5.value

    def test_ladder_details_preserve_per_rung_payload(self) -> None:
        gi = _pass_input()
        gi.lint_status = CheckResult(status="pass", details={"warnings": 0})
        verdict = evaluate_ladder(gi, STRICT)
        entries = _ladder_entries(verdict.details)
        assert entries[0]["details"] == {"warnings": 0}

    def test_ladder_includes_profile_name(self) -> None:
        verdict = evaluate_ladder(_pass_input(), STRICT)
        assert verdict.details["ladder_profile"] == "strict"

    def test_ladder_includes_first_failing_rung_none_on_pass(self) -> None:
        verdict = evaluate_ladder(_pass_input(), STRICT)
        assert verdict.details["first_failing_rung"] is None
