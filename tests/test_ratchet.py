"""Comprehensive tests for the v8.0.0 P-07 Monotonic Ratchet (G13 closure).

Covers:

- All four verdict paths (``ADVANCE`` / ``TOLERATE`` / ``ROLLBACK`` /
  ``ESCALATE``) per ``patch_plan §3 P-07 AC #1-#4``.
- :func:`compute_deterministic_oracle_score` S/O/R-resistance proof:
  adding / removing / mutating ``review_findings`` MUST NOT change the
  oracle (per ``patch_plan §3 P-07 AC #5`` — non-gameable success).
- ``ratchet=None`` ⇒ ``evaluate_gate`` byte-identical to v7.8.0
  (``patch_plan §3 P-07 AC #4``).
- Schema invariant: ``schemas/lean-dispatch.yaml#layout_invariant``
  ``canonical_order`` length = 14, ``version`` = 3 PRESERVED (P6).
- Integration with the convergence helper
  :func:`devolaflow.gate.convergence.record_round_with_ratchet`.
- ``apply_round_escalation`` refactor regression
  (NineS ``[CC-448821-0001]`` closure: 11 → ≤6 cc per helper).
- Edge cases: empty history, score in ``[0, 100]`` bounds, monotonic
  round numbering, snapshot rotation.

Target: ≥ 95 % line coverage on ``src/devolaflow/gate/ratchet.py``.
"""

from __future__ import annotations

import copy
import dataclasses
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from devolaflow.compressor import assert_dispatch_layout
from devolaflow.gate import (
    STANDARD,
    ArtifactSnapshot,
    CheckResult,
    ConvergenceRound,
    Finding,
    GateInput,
    MonotonicRatchet,
    RatchetAction,
    RatchetLogEntry,
    compute_deterministic_oracle_score,
    detect_ratchet_escalation,
    evaluate_gate,
    record_round_with_ratchet,
)
from devolaflow.gate.ratchet import (
    DEFAULT_MAX_REGRESSIONS,
    DEFAULT_REGRESSION_TOLERANCE,
    ORACLE_WEIGHT_BUILD,
    ORACLE_WEIGHT_LINT,
    ORACLE_WEIGHT_TEST,
    _check_pct,
    hash_payload,
)
from devolaflow.task_adaptive_selector import (
    apply_round_escalation,
    apply_severity_filter,
    escalate_round,
    select_round_result,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _pass_input() -> GateInput:
    """Build a baseline PASS-PASS-PASS GateInput for oracle tests."""
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        review_findings=[],
    )


def _failing_input(*, build="fail", test="fail", lint="fail") -> GateInput:
    return GateInput(
        build_status=CheckResult(status=build),
        test_results=CheckResult(status=test),
        lint_status=CheckResult(status=lint),
        review_findings=[],
    )


def _finding(severity: str = "blocker", fid: str = "F001") -> Finding:
    return Finding(
        finding_id=fid,
        severity=severity,  # type: ignore[arg-type]
        category="test",
        location="src/foo.py:1",
        description="ratchet S/O/R test finding",
    )


# ---------------------------------------------------------------------------
# 1. compute_deterministic_oracle_score — basic semantics
# ---------------------------------------------------------------------------


class TestOracleScoreBasics:
    def test_all_pass_returns_100(self) -> None:
        score = compute_deterministic_oracle_score(_pass_input())
        assert score == 100.0

    def test_all_fail_returns_zero(self) -> None:
        gi = _failing_input()
        assert compute_deterministic_oracle_score(gi) == 0.0

    def test_partial_test_pass_interpolates(self) -> None:
        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(
                status="fail",
                details={"tests_passed": 90, "tests_total": 100},
            ),
            lint_status=CheckResult(status="pass"),
        )
        # test=90 (50%), lint=100 (20%), build=100 (30%) → 45 + 20 + 30 = 95
        score = compute_deterministic_oracle_score(gi)
        assert score == pytest.approx(95.0, abs=0.01)

    def test_skip_counts_as_neutral_pass(self) -> None:
        gi = GateInput(
            build_status=CheckResult(status="skip"),
            test_results=CheckResult(status="skip"),
            lint_status=CheckResult(status="skip"),
        )
        assert compute_deterministic_oracle_score(gi) == 100.0

    def test_weights_sum_to_one(self) -> None:
        assert pytest.approx(1.0) == ORACLE_WEIGHT_TEST + ORACLE_WEIGHT_LINT + ORACLE_WEIGHT_BUILD

    def test_score_clamped_to_unit_range(self) -> None:
        gi = GateInput(
            build_status=CheckResult(status="fail", details={"tests_passed": 5, "tests_total": 1}),
            test_results=CheckResult(status="pass"),
            lint_status=CheckResult(status="pass"),
        )
        score = compute_deterministic_oracle_score(gi)
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# 2. S/O/R-RESISTANCE PROOF — review_findings MUST NOT influence oracle
# ---------------------------------------------------------------------------


class TestOracleSORResistance:
    """Per ``patch_plan §3 P-07 AC #5``: review_findings cannot game the oracle."""

    def test_adding_blocker_finding_does_not_change_oracle(self) -> None:
        baseline = _pass_input()
        baseline_score = compute_deterministic_oracle_score(baseline)

        with_blocker = _pass_input()
        with_blocker.review_findings = [_finding("blocker"), _finding("critical", "F002")]
        gamed_score = compute_deterministic_oracle_score(with_blocker)

        assert baseline_score == gamed_score, (
            "S/O/R-resistance violated: adding a review_finding changed the deterministic "
            f"oracle ({baseline_score} → {gamed_score})"
        )

    def test_removing_findings_does_not_change_oracle(self) -> None:
        gi = _pass_input()
        gi.review_findings = [_finding("blocker"), _finding("major", "F002")]
        score_with = compute_deterministic_oracle_score(gi)

        gi.review_findings = []
        score_without = compute_deterministic_oracle_score(gi)
        assert score_with == score_without

    def test_mutating_finding_severity_does_not_change_oracle(self) -> None:
        gi = _pass_input()
        gi.review_findings = [_finding("info")]
        before = compute_deterministic_oracle_score(gi)
        gi.review_findings = [_finding("blocker")]
        after = compute_deterministic_oracle_score(gi)
        assert before == after

    def test_oracle_only_consults_three_fields(self) -> None:
        """Exhaustive: every other GateInput field is irrelevant."""
        gi = _pass_input()
        baseline = compute_deterministic_oracle_score(gi)

        gi.review_findings = [_finding("blocker", f"F{i:03d}") for i in range(50)]
        gi.acceptance_criteria_results = CheckResult(status="fail")
        gi.visual_test_results = CheckResult(status="fail")
        gi.interaction_test_results = CheckResult(status="fail")
        gi.accessibility_results = CheckResult(status="fail")
        gi.acceptance_verification_results = CheckResult(status="fail")
        assert compute_deterministic_oracle_score(gi) == baseline


# ---------------------------------------------------------------------------
# 3. _check_pct — internal helper coverage
# ---------------------------------------------------------------------------


class TestCheckPct:
    def test_pass_returns_100(self) -> None:
        assert _check_pct("pass", {}) == 100.0

    def test_skip_returns_100(self) -> None:
        assert _check_pct("skip", {}) == 100.0

    def test_fail_with_no_counters_returns_zero(self) -> None:
        assert _check_pct("fail", {}) == 0.0

    def test_fail_with_tests_counters_interpolates(self) -> None:
        assert _check_pct("fail", {"tests_passed": 8, "tests_total": 10}) == 80.0

    def test_fail_with_files_counters_interpolates(self) -> None:
        assert _check_pct("fail", {"files_passed": 5, "files_total": 10}) == 50.0

    def test_fail_clamps_above_one_hundred(self) -> None:
        assert _check_pct("fail", {"tests_passed": 200, "tests_total": 100}) == 100.0


# ---------------------------------------------------------------------------
# 4. ADVANCE path — first round + strict score lifts
# ---------------------------------------------------------------------------


class TestAdvancePath:
    def test_first_round_returns_advance(self) -> None:
        ratchet = MonotonicRatchet()
        action = ratchet.record_round(1, 80.0, artifact={"file": "v1"})
        assert action is RatchetAction.ADVANCE
        assert ratchet.best_score == 80.0
        assert ratchet.best_round == 1

    def test_first_round_saves_artifact_snapshot(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0, artifact={"file": "v1", "size": 100})
        snap = ratchet.best_artifact_snapshot
        assert snap is not None
        assert snap.round_num == 1
        assert snap.score == 80.0
        assert snap.payload == {"file": "v1", "size": 100}
        assert len(snap.payload_hash) == 64  # sha256 hex digest

    def test_strict_lift_returns_advance_and_rotates_best(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 70.0)
        action = ratchet.record_round(2, 80.0, artifact={"v": 2})
        assert action is RatchetAction.ADVANCE
        assert ratchet.best_score == 80.0
        assert ratchet.best_round == 2

    def test_advance_resets_consecutive_regressions(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 70.0)  # TOLERATE (1st regression below band)
        assert ratchet.consecutive_regressions == 1
        ratchet.record_round(3, 90.0)  # ADVANCE
        assert ratchet.consecutive_regressions == 0


# ---------------------------------------------------------------------------
# 5. TOLERATE path — within-tolerance regression
# ---------------------------------------------------------------------------


class TestToleratePath:
    def test_within_tolerance_below_returns_tolerate(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        action = ratchet.record_round(2, 78.5)  # 1.5pp below, within ±2pp band
        assert action is RatchetAction.TOLERATE
        assert ratchet.best_score == 80.0  # best preserved

    def test_exact_equal_returns_tolerate(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        action = ratchet.record_round(2, 80.0)
        assert action is RatchetAction.TOLERATE

    def test_first_below_tolerance_regression_returns_tolerate(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        action = ratchet.record_round(2, 70.0)  # 10pp below, beyond band
        assert action is RatchetAction.TOLERATE
        assert ratchet.consecutive_regressions == 1

    def test_within_band_does_not_increment_regression_counter(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 79.0)  # within band
        assert ratchet.consecutive_regressions == 0


# ---------------------------------------------------------------------------
# 6. ROLLBACK path — second consecutive below-tolerance regression
# ---------------------------------------------------------------------------


class TestRollbackPath:
    def test_second_consecutive_regression_returns_rollback(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0, artifact={"v": 1})
        action_2 = ratchet.record_round(2, 70.0)
        action_3 = ratchet.record_round(3, 65.0)
        assert action_2 is RatchetAction.TOLERATE
        assert action_3 is RatchetAction.ROLLBACK

    def test_rollback_preserves_best_artifact_snapshot(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0, artifact={"v": 1, "best": True})
        ratchet.record_round(2, 70.0)
        ratchet.record_round(3, 65.0)
        snap = ratchet.best_artifact_snapshot
        assert snap is not None
        assert snap.round_num == 1
        assert snap.score == 80.0
        assert snap.payload == {"v": 1, "best": True}

    def test_rollback_after_jitter_then_real_drop(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        # 79.0 = within band, does NOT count as regression
        assert ratchet.record_round(2, 79.0) is RatchetAction.TOLERATE
        # 60.0 = first beyond-band regression → TOLERATE
        assert ratchet.record_round(3, 60.0) is RatchetAction.TOLERATE
        # 55.0 = second beyond-band regression → ROLLBACK
        assert ratchet.record_round(4, 55.0) is RatchetAction.ROLLBACK


# ---------------------------------------------------------------------------
# 7. ESCALATE path — post-rollback failure to recover
# ---------------------------------------------------------------------------


class TestEscalatePath:
    def test_escalate_after_rollback_no_recovery(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0, artifact={"v": 1})
        ratchet.record_round(2, 70.0)  # TOLERATE
        ratchet.record_round(3, 65.0)  # ROLLBACK
        action = ratchet.record_round(4, 65.0)  # post-rollback, still cannot exceed best
        assert action is RatchetAction.ESCALATE

    def test_escalate_then_recover_advances(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 70.0)
        ratchet.record_round(3, 65.0)
        ratchet.record_round(4, 65.0)  # ESCALATE
        action = ratchet.record_round(5, 90.0)  # finally beats best
        assert action is RatchetAction.ADVANCE
        assert ratchet.best_score == 90.0

    def test_escalate_carries_into_history_log(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 60.0)
        ratchet.record_round(3, 60.0)
        ratchet.record_round(4, 60.0)
        actions = [entry.action for entry in ratchet.history]
        assert actions == [
            RatchetAction.ADVANCE,
            RatchetAction.TOLERATE,
            RatchetAction.ROLLBACK,
            RatchetAction.ESCALATE,
        ]


# ---------------------------------------------------------------------------
# 8. Constructor + tunable parameters
# ---------------------------------------------------------------------------


class TestRatchetConstructor:
    def test_default_tolerance_and_max_regressions(self) -> None:
        ratchet = MonotonicRatchet()
        assert ratchet.regression_tolerance == DEFAULT_REGRESSION_TOLERANCE
        assert ratchet.max_regressions == DEFAULT_MAX_REGRESSIONS

    def test_custom_tolerance_widens_band(self) -> None:
        ratchet = MonotonicRatchet(regression_tolerance=0.10)  # ±10pp band
        ratchet.record_round(1, 80.0)
        # 71 is 9pp below — would normally be regression, now within band
        assert ratchet.record_round(2, 71.0) is RatchetAction.TOLERATE
        assert ratchet.consecutive_regressions == 0

    def test_custom_max_regressions_delays_rollback(self) -> None:
        ratchet = MonotonicRatchet(max_regressions=3)
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 60.0)  # 1st regression
        ratchet.record_round(3, 60.0)  # 2nd regression — would be ROLLBACK at default
        assert ratchet.history[-1].action is RatchetAction.TOLERATE
        ratchet.record_round(4, 60.0)  # 3rd regression
        assert ratchet.history[-1].action is RatchetAction.ROLLBACK

    def test_tolerance_band_property(self) -> None:
        assert MonotonicRatchet(regression_tolerance=0.05).tolerance_band == 5.0


# ---------------------------------------------------------------------------
# 9. Input validation — never silent failures (S-5)
# ---------------------------------------------------------------------------


class TestRatchetInputValidation:
    def test_zero_round_num_raises(self) -> None:
        ratchet = MonotonicRatchet()
        with pytest.raises(ValueError, match="positive int"):
            ratchet.record_round(0, 80.0)

    def test_negative_round_num_raises(self) -> None:
        ratchet = MonotonicRatchet()
        with pytest.raises(ValueError, match="positive int"):
            ratchet.record_round(-1, 80.0)

    def test_non_int_round_num_raises(self) -> None:
        ratchet = MonotonicRatchet()
        with pytest.raises(ValueError, match="positive int"):
            ratchet.record_round("1", 80.0)  # type: ignore[arg-type]

    def test_score_below_zero_raises(self) -> None:
        ratchet = MonotonicRatchet()
        with pytest.raises(ValueError, match=r"\[0.0, 100.0\]"):
            ratchet.record_round(1, -5.0)

    def test_score_above_one_hundred_raises(self) -> None:
        ratchet = MonotonicRatchet()
        with pytest.raises(ValueError, match=r"\[0.0, 100.0\]"):
            ratchet.record_round(1, 105.0)

    def test_non_numeric_score_raises(self) -> None:
        ratchet = MonotonicRatchet()
        with pytest.raises(ValueError, match="numeric"):
            ratchet.record_round(1, "80")  # type: ignore[arg-type]

    def test_non_monotonic_round_num_raises(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(2, 80.0)
        with pytest.raises(ValueError, match="strictly greater"):
            ratchet.record_round(2, 90.0)
        with pytest.raises(ValueError, match="strictly greater"):
            ratchet.record_round(1, 90.0)


# ---------------------------------------------------------------------------
# 10. reset() + state isolation
# ---------------------------------------------------------------------------


class TestRatchetReset:
    def test_reset_clears_state(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0, artifact={"v": 1})
        ratchet.record_round(2, 70.0)
        ratchet.reset()
        assert ratchet.best_score == 0.0
        assert ratchet.best_round == 0
        assert ratchet.best_artifact_snapshot is None
        assert ratchet.history == []
        assert ratchet.consecutive_regressions == 0
        assert ratchet.last_action is None

    def test_reset_preserves_tunable_params(self) -> None:
        ratchet = MonotonicRatchet(regression_tolerance=0.05, max_regressions=5)
        ratchet.record_round(1, 80.0)
        ratchet.reset()
        assert ratchet.regression_tolerance == 0.05
        assert ratchet.max_regressions == 5


# ---------------------------------------------------------------------------
# 11. RatchetLogEntry & history log
# ---------------------------------------------------------------------------


class TestRatchetLog:
    def test_history_records_every_round_in_order(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(3, 90.0)  # round numbers strictly increasing
        ratchet.record_round(5, 85.0)
        rounds = [e.round_num for e in ratchet.history]
        assert rounds == [1, 3, 5]

    def test_log_entry_marks_new_best(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 78.0)
        ratchet.record_round(3, 90.0)
        bests = [e.new_best for e in ratchet.history]
        assert bests == [True, False, True]

    def test_log_entry_carries_human_note(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 78.5)
        notes = [e.note for e in ratchet.history]
        assert "first round" in notes[0]
        assert "within" in notes[1]

    def test_rollback_note_mentions_snapshot_round(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 60.0)
        ratchet.record_round(3, 60.0)
        assert "round 1" in ratchet.history[-1].note

    def test_log_entry_is_frozen(self) -> None:
        entry = RatchetLogEntry(
            round_num=1, score=80.0, action=RatchetAction.ADVANCE, new_best=True
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.score = 90.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 12. ArtifactSnapshot dataclass
# ---------------------------------------------------------------------------


class TestArtifactSnapshot:
    def test_snapshot_is_frozen(self) -> None:
        snap = ArtifactSnapshot(round_num=1, score=80.0, payload_hash="abc")
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.score = 90.0  # type: ignore[misc]

    def test_snapshot_default_payload_is_empty_dict(self) -> None:
        snap = ArtifactSnapshot(round_num=1, score=80.0)
        assert snap.payload == {}
        assert snap.payload_hash == ""

    def test_hash_payload_is_deterministic(self) -> None:
        a = hash_payload({"x": 1, "y": [1, 2]})
        b = hash_payload({"y": [1, 2], "x": 1})
        assert a == b

    def test_hash_payload_is_unique(self) -> None:
        a = hash_payload({"x": 1})
        b = hash_payload({"x": 2})
        assert a != b

    def test_explicit_artifact_hash_overrides_computed(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0, artifact={"v": 1}, artifact_hash="custom-hash")
        snap = ratchet.best_artifact_snapshot
        assert snap is not None
        assert snap.payload_hash == "custom-hash"


# ---------------------------------------------------------------------------
# 13. Scorer integration — ratchet=None byte-identical
# ---------------------------------------------------------------------------


class TestScorerRatchetNoneByteIdentical:
    """Per ``patch_plan §3 P-07 AC #4``: ratchet=None ⇒ pre-P-07 behavior."""

    def test_no_ratchet_produces_no_ratchet_details(self) -> None:
        gi = _pass_input()
        verdict = evaluate_gate(gi, STANDARD)
        assert "ratchet" not in verdict.details

    def test_ratchet_none_verdict_equals_baseline(self) -> None:
        gi = _pass_input()
        v_no_param = evaluate_gate(gi, STANDARD)
        v_explicit_none = evaluate_gate(gi, STANDARD, ratchet=None)
        assert v_no_param.decision == v_explicit_none.decision
        assert v_no_param.composite_score == v_explicit_none.composite_score
        assert v_no_param.rationale == v_explicit_none.rationale
        assert v_no_param.details == v_explicit_none.details
        assert v_no_param.escalation_context == v_explicit_none.escalation_context

    def test_failing_input_no_ratchet_byte_identical(self) -> None:
        gi = _failing_input(test="fail")
        v1 = evaluate_gate(gi, STANDARD)
        v2 = evaluate_gate(gi, STANDARD, ratchet=None)
        assert v1.decision == v2.decision == "FAIL"
        assert v1.details == v2.details

    def test_ratchet_none_with_history_byte_identical(self) -> None:
        gi = _pass_input()
        history = [
            ConvergenceRound(
                round_num=1,
                composite_score=70.0,
                blocker_count=0,
                critical_count=0,
                timestamp="2026-04-01T00:00:00Z",
            )
        ]
        v1 = evaluate_gate(gi, STANDARD, round_num=2, history=history)
        v2 = evaluate_gate(gi, STANDARD, round_num=2, history=history, ratchet=None)
        assert v1.decision == v2.decision
        assert v1.composite_score == v2.composite_score
        assert v1.details == v2.details


# ---------------------------------------------------------------------------
# 14. Scorer integration — ratchet attached
# ---------------------------------------------------------------------------


class TestScorerRatchetAttached:
    def test_ratchet_attaches_action_to_details(self) -> None:
        ratchet = MonotonicRatchet()
        gi = _pass_input()
        verdict = evaluate_gate(gi, STANDARD, ratchet=ratchet)
        assert "ratchet" in verdict.details
        assert verdict.details["ratchet"]["action"] == "ADVANCE"
        assert verdict.details["ratchet"]["oracle_score"] == 100.0
        assert verdict.details["ratchet"]["best_score"] == 100.0
        assert verdict.details["ratchet"]["best_round"] == 1

    def test_ratchet_uses_oracle_not_composite(self) -> None:
        """The recorded score must come from compute_deterministic_oracle_score,
        not from the composite review-finding-aware score."""
        ratchet = MonotonicRatchet()
        gi = _pass_input()
        gi.review_findings = [_finding("blocker") for _ in range(5)]
        verdict = evaluate_gate(gi, STANDARD, ratchet=ratchet)
        # Oracle must be 100 (test+lint+build all pass) regardless of the 5 blockers.
        assert verdict.details["ratchet"]["oracle_score"] == 100.0
        # Standard verdict failed because of blockers.
        assert verdict.decision == "FAIL"

    def test_ratchet_artifact_payload_snapshot(self) -> None:
        ratchet = MonotonicRatchet()
        gi = _pass_input()
        evaluate_gate(
            gi,
            STANDARD,
            ratchet=ratchet,
            ratchet_artifact={"dispatch_id": "T-S03-W01-T01"},
        )
        snap = ratchet.best_artifact_snapshot
        assert snap is not None
        assert snap.payload == {"dispatch_id": "T-S03-W01-T01"}

    def test_ratchet_escalate_upgrades_pass_to_escalate(self) -> None:
        """Per AC #4: ratchet ESCALATE upgrades the verdict decision."""
        ratchet = MonotonicRatchet()
        # Drive the ratchet into ESCALATE state via recorded rounds.
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 60.0)  # TOLERATE
        ratchet.record_round(3, 55.0)  # ROLLBACK
        # Now invoke the gate with a (still failing) state — the ratchet emits
        # ESCALATE because oracle=100 ≥ best=80? Actually 100 > 80 → ADVANCE.
        # We need to use a low-oracle input so post-rollback ESCALATE fires.
        gi = GateInput(
            build_status=CheckResult(status="fail"),
            test_results=CheckResult(status="fail"),
            lint_status=CheckResult(status="pass"),
        )  # oracle = 0 + 0 + 20 = 20
        verdict = evaluate_gate(gi, STANDARD, round_num=4, ratchet=ratchet)
        assert verdict.decision == "ESCALATE"
        assert verdict.details["ratchet"]["action"] == "ESCALATE"
        assert "Ratchet escalation" in verdict.escalation_context

    def test_ratchet_advance_does_not_alter_pass_verdict(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 50.0)
        gi = _pass_input()
        verdict = evaluate_gate(gi, STANDARD, round_num=2, ratchet=ratchet)
        assert verdict.decision == "PASS"
        assert verdict.details["ratchet"]["action"] == "ADVANCE"


# ---------------------------------------------------------------------------
# 15. Convergence helper integration (record_round_with_ratchet)
# ---------------------------------------------------------------------------


class TestConvergenceRatchetBridge:
    def test_record_round_with_ratchet_appends_history(self) -> None:
        ratchet = MonotonicRatchet()
        history: list[ConvergenceRound] = []
        entry = ConvergenceRound(
            round_num=1,
            composite_score=80.0,
            blocker_count=0,
            critical_count=0,
            timestamp="2026-04-01T00:00:00Z",
        )
        action = record_round_with_ratchet(history, entry, ratchet)
        assert action is RatchetAction.ADVANCE
        assert len(history) == 1
        assert history[0] is entry
        assert ratchet.best_score == 80.0

    def test_detect_ratchet_escalation_false_when_no_action(self) -> None:
        ratchet = MonotonicRatchet()
        assert detect_ratchet_escalation(ratchet) is False

    def test_detect_ratchet_escalation_true_after_escalate(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        ratchet.record_round(2, 60.0)
        ratchet.record_round(3, 55.0)
        ratchet.record_round(4, 50.0)
        assert detect_ratchet_escalation(ratchet) is True

    def test_detect_ratchet_escalation_false_after_advance(self) -> None:
        ratchet = MonotonicRatchet()
        ratchet.record_round(1, 80.0)
        assert detect_ratchet_escalation(ratchet) is False


# ---------------------------------------------------------------------------
# 16. apply_round_escalation refactor — NineS [CC-448821-0001] closure
# ---------------------------------------------------------------------------


class TestApplyRoundEscalationRefactor:
    """Per ``patch_plan §3 P-07 AC #6``: cc 11 → ≤ 6 per helper."""

    def test_select_round_result_exact_match(self) -> None:
        cfg = {2: {"model_hint_override": "balanced"}, 3: {"token_budget_increase_pct": 30}}
        assert select_round_result(2, cfg) == cfg[2]

    def test_select_round_result_overflow_picks_highest_budget(self) -> None:
        cfg = {2: {"token_budget_increase_pct": 10}, 3: {"token_budget_increase_pct": 30}}
        assert select_round_result(5, cfg) == cfg[3]

    def test_select_round_result_below_min_returns_none(self) -> None:
        cfg = {2: {"x": 1}, 3: {"x": 2}}
        assert select_round_result(1, cfg) is None

    def test_select_round_result_uses_default_when_none(self) -> None:
        result = select_round_result(2)
        assert result is not None
        assert "section_priority_overrides" in result

    def test_apply_severity_filter_merges_priorities(self) -> None:
        result = {"section_priorities": {"foo": "supplementary"}}
        overrides = {"section_priority_overrides": {"bar": "critical"}}
        apply_severity_filter(result, overrides)
        assert result["section_priorities"] == {"foo": "supplementary", "bar": "critical"}

    def test_apply_severity_filter_sets_model_hint(self) -> None:
        result: dict = {}
        apply_severity_filter(result, {"model_hint_override": "quality"})
        assert result["model_hint"] == "quality"

    def test_apply_severity_filter_no_op_for_empty_overrides(self) -> None:
        before = {"section_priorities": {"foo": "important"}}
        result = dict(before)
        apply_severity_filter(result, {})
        assert result == before

    def test_escalate_round_increases_token_budget(self) -> None:
        result = {"token_budget": 5000}
        escalate_round(result, {"token_budget_increase_pct": 20})
        assert result["token_budget"] == 6000

    def test_escalate_round_sets_compression_intensity(self) -> None:
        result: dict = {}
        escalate_round(result, {"compression_intensity": "minimal"})
        assert result["compression_intensity"] == "minimal"

    def test_apply_round_escalation_byte_identical_to_pre_p07(self) -> None:
        """v8.0.0 P-07 refactor regression — the round-3 default must still
        promote convergence_loop and bump token_budget by 20 %."""
        baseline = {"section_priorities": {}, "token_budget": 5000}
        result = apply_round_escalation(baseline, 3)
        assert result["section_priorities"]["convergence_loop"] == "critical"
        assert result["section_priorities"]["gate_mechanism"] == "critical"
        assert result["model_hint"] == "quality"
        assert result["token_budget"] == 6000

    def test_apply_round_escalation_round_1_is_no_op(self) -> None:
        baseline = {"section_priorities": {"foo": "important"}, "token_budget": 5000}
        result = apply_round_escalation(baseline, 1)
        assert result is baseline  # untouched (preserved v7.x identity contract)

    def test_apply_round_escalation_does_not_mutate_input(self) -> None:
        baseline = {"section_priorities": {"a": "important"}, "token_budget": 6000}
        snapshot = deepcopy(baseline)
        apply_round_escalation(baseline, 2)
        assert baseline == snapshot


# ---------------------------------------------------------------------------
# 17. Schema invariant — P6 cached prefix preserved
# ---------------------------------------------------------------------------


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "lean-dispatch.yaml"


class TestSchemaInvariantP6Preserved:
    """Per ``patch_plan §3 P-07``: schema canonical_order must NOT change."""

    def test_layout_invariant_canonical_order_length_is_14(self) -> None:
        schema = yaml.safe_load(SCHEMA_PATH.read_text())
        assert len(schema["layout_invariant"]["canonical_order"]) == 14

    def test_layout_invariant_version_is_3(self) -> None:
        schema = yaml.safe_load(SCHEMA_PATH.read_text())
        assert schema["layout_invariant"]["version"] == 3

    def test_assert_dispatch_layout_still_passes_canonical_payload(self) -> None:
        payload = {
            "hdr": "h",
            "task": "t",
            "goal": "g",
            "assumptions": "a",
            "pred": "p",
            "files": [],
            "rules": [],
            "shared": "s",
            "accept": [],
            "reinforce": "",
            "verify_cfg": {},
            "gate": {},
            "repos": {},
            "behavioral_guidelines": None,
        }
        assert_dispatch_layout(payload)


# ---------------------------------------------------------------------------
# 18. Hashing + payload-snapshot determinism
# ---------------------------------------------------------------------------


class TestHashPayloadDeterminism:
    def test_two_independent_calls_produce_same_hash(self) -> None:
        payload = {"file": "ratchet.py", "lines": 250, "extra": [1, 2, 3]}
        h1 = hash_payload(payload)
        h2 = hash_payload(copy.deepcopy(payload))
        assert h1 == h2

    def test_hash_is_64_char_hex(self) -> None:
        h = hash_payload({"x": 1})
        assert len(h) == 64
        int(h, 16)  # raises if not hex

    def test_non_string_keys_serialize_via_default_str(self) -> None:
        # The default=str fallback in json.dumps lets us hash payloads
        # whose values include non-JSON types (e.g. Path objects).
        payload = {"path": Path("/tmp/foo")}
        assert hash_payload(payload) == hash_payload({"path": Path("/tmp/foo")})


# ---------------------------------------------------------------------------
# 19. Complex multi-round trajectory — full AC #1-#4 scenario
# ---------------------------------------------------------------------------


class TestFullACScenario:
    """Reproduces ``patch_plan §3 P-07 AC #1-#4`` end-to-end."""

    def test_full_ac_scenario_advance_tolerate_rollback_escalate(self) -> None:
        ratchet = MonotonicRatchet()

        # AC #1 — round 1 score=80.0 → ADVANCE (best=80)
        a1 = ratchet.record_round(1, 80.0, artifact={"file": "v1"})
        assert a1 is RatchetAction.ADVANCE
        assert ratchet.best_score == 80.0

        # AC #2 — round 2 score=78.5 (1.5pp below, within ±2pp) → TOLERATE
        a2 = ratchet.record_round(2, 78.5)
        assert a2 is RatchetAction.TOLERATE

        # AC #3 — round 3 score=70.0 (10pp below, beyond band, 1st regression) → TOLERATE
        a3 = ratchet.record_round(3, 70.0)
        assert a3 is RatchetAction.TOLERATE
        # Round 4 score=70.0 (still beyond band, 2nd regression) → ROLLBACK
        a4 = ratchet.record_round(4, 70.0)
        assert a4 is RatchetAction.ROLLBACK

        # AC #4 — round 5 still cannot exceed best → ESCALATE
        a5 = ratchet.record_round(5, 70.0)
        assert a5 is RatchetAction.ESCALATE

        # Best-snapshot still points to round 1
        assert ratchet.best_artifact_snapshot is not None
        assert ratchet.best_artifact_snapshot.round_num == 1
