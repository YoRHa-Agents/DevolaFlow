"""Comprehensive tests for the v8.0.0 P-09 Overcomplexity Detector.

Covers the patch_plan §3 P-09 acceptance criteria:

- ``ComplexityDetector.evaluate()`` correctly classifies the OK /
  WARNING / CRITICAL paths across the 4 task complexity tiers
  (trivial / simple / standard / complex).
- ``wrap_nines_complexity()`` returns a conservative MOCK signal when
  the ``nines`` binary is unavailable (per ``patch_plan §3 P-09 AC #4``).
- ``complexity_detector=None`` keeps :func:`evaluate_gate` byte-identical
  to pre-P-09 behaviour (``patch_plan §3 P-09 AC #6``).

Target: ≥ 90 % line coverage on
``src/devolaflow/gate/complexity_detector.py``.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any

import pytest

from devolaflow.gate import (
    AUDIT,
    RELAXED,
    STANDARD,
    STRICT,
    CheckResult,
    ComplexityDetector,
    ComplexityEvaluation,
    ComplexitySignals,
    ComplexityVerdict,
    GateInput,
    NinesWrapResult,
    evaluate_gate,
    wrap_nines_complexity,
)
from devolaflow.gate.complexity_detector import (
    CRITICAL_CC_THRESHOLD,
    CRITICAL_REASON_CC,
    CRITICAL_REASON_NINES_ERROR,
    NINES_BINARY,
    TIER_BUDGETS,
    WARN_REASON_ABSTRACTIONS,
    WARN_REASON_CC,
    WARN_REASON_FILES,
    WARN_REASON_LINES,
    WARN_REASON_NESTING,
    WARN_REASON_NINES_WARN,
    WARN_REASON_RATIO,
    WARNING_CC_THRESHOLD,
    TierBudgets,
    _conservative_mock_signals,
    _parse_nines_payload,
    _resolve_nines_binary,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _signals(**kwargs: Any) -> ComplexitySignals:
    """Build a ComplexitySignals with sensible defaults for tests."""
    defaults: dict[str, Any] = {
        "lines_changed": 50,
        "files_touched": 1,
        "new_abstractions": 0,
        "nesting_depth_max": 2,
        "cyclomatic_complexity": 5,
        "ratio_to_minimal": 1.0,
        "nines_error_findings": 0,
        "nines_warn_findings": 0,
    }
    defaults.update(kwargs)
    return ComplexitySignals(**defaults)


@dataclass
class _FakeRunResult:
    """Stand-in for :class:`subprocess.CompletedProcess` for runner mocks."""

    returncode: int
    stdout: str
    stderr: str = ""


def _make_runner(result: _FakeRunResult):
    """Return a callable mimicking ``subprocess.run``'s positional signature."""

    def runner(*_args: Any, **_kwargs: Any) -> _FakeRunResult:
        return result

    return runner


def _gate_input_pass() -> GateInput:
    """All-pass GateInput used to verify byte-identical regression."""
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        review_findings=[],
    )


# ===========================================================================
# 1. Verdict matrix — TRIVIAL tier
# ===========================================================================


class TestTrivialTier:
    """AC #1 + #2 — trivial tier OK / WARNING split."""

    def test_trivial_baseline_returns_ok(self) -> None:
        # AC #1: lines_changed=50 + cc=5 + ratio=1.0 → OK
        detector = ComplexityDetector()
        signals = _signals(lines_changed=50, cyclomatic_complexity=5, ratio_to_minimal=1.0)
        result = detector.evaluate(signals, "trivial")
        assert result.verdict is ComplexityVerdict.OK
        assert result.is_ok is True
        assert result.reasons == ()
        assert result.task_complexity == "trivial"

    def test_trivial_lines_above_budget_returns_warning(self) -> None:
        # AC #2: same signals, lines_changed=100 → WARNING
        detector = ComplexityDetector()
        signals = _signals(lines_changed=100, cyclomatic_complexity=5, ratio_to_minimal=1.0)
        result = detector.evaluate(signals, "trivial")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_LINES in result.reasons

    def test_trivial_new_abstraction_warns(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(new_abstractions=1)
        result = detector.evaluate(signals, "trivial")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_ABSTRACTIONS in result.reasons

    def test_trivial_cc_above_warning_warns(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(cyclomatic_complexity=11)
        result = detector.evaluate(signals, "trivial")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_CC in result.reasons


# ===========================================================================
# 2. Verdict matrix — SIMPLE tier
# ===========================================================================


class TestSimpleTier:
    def test_simple_within_budget_ok(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(
            lines_changed=180, files_touched=2, new_abstractions=2, cyclomatic_complexity=8
        )
        result = detector.evaluate(signals, "simple")
        assert result.verdict is ComplexityVerdict.OK

    def test_simple_files_above_budget_warns(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(files_touched=3)
        result = detector.evaluate(signals, "simple")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_FILES in result.reasons

    def test_simple_nesting_above_budget_warns(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(nesting_depth_max=4)
        result = detector.evaluate(signals, "simple")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_NESTING in result.reasons


# ===========================================================================
# 3. Verdict matrix — STANDARD tier
# ===========================================================================


class TestStandardTier:
    def test_standard_within_budget_ok(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(
            lines_changed=400, files_touched=4, new_abstractions=4, cyclomatic_complexity=9
        )
        result = detector.evaluate(signals, "standard")
        assert result.verdict is ComplexityVerdict.OK

    def test_standard_ratio_at_threshold_warns(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(ratio_to_minimal=4.0)
        result = detector.evaluate(signals, "standard")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_RATIO in result.reasons


# ===========================================================================
# 4. Verdict matrix — COMPLEX tier (AC #3)
# ===========================================================================


class TestComplexTier:
    def test_complex_baseline_ok(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(
            lines_changed=900,
            files_touched=8,
            new_abstractions=8,
            nesting_depth_max=4,
            cyclomatic_complexity=10,
            ratio_to_minimal=4.5,
        )
        result = detector.evaluate(signals, "complex")
        assert result.verdict is ComplexityVerdict.OK

    def test_complex_ratio_six_returns_warning(self) -> None:
        # AC #3: complex tier + ratio_to_minimal=6.0 → WARNING (5x threshold)
        detector = ComplexityDetector()
        signals = _signals(ratio_to_minimal=6.0)
        result = detector.evaluate(signals, "complex")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_RATIO in result.reasons

    def test_complex_lines_at_budget_ok(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(lines_changed=999)
        result = detector.evaluate(signals, "complex")
        assert result.verdict is ComplexityVerdict.OK

    def test_complex_lines_above_budget_warns(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(lines_changed=1000)
        result = detector.evaluate(signals, "complex")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_LINES in result.reasons


# ===========================================================================
# 5. CRITICAL paths — cc > 15 OR NineS ERROR
# ===========================================================================


class TestCriticalPath:
    def test_cc_above_critical_threshold_returns_critical(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(cyclomatic_complexity=16)
        result = detector.evaluate(signals, "trivial")
        assert result.verdict is ComplexityVerdict.CRITICAL
        assert CRITICAL_REASON_CC in result.reasons

    def test_cc_at_critical_threshold_only_warns(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(cyclomatic_complexity=15)
        result = detector.evaluate(signals, "trivial")
        # cc=15 > 10 (warn) but NOT > 15 (critical)
        assert result.verdict is ComplexityVerdict.WARNING

    def test_nines_error_finding_returns_critical(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(nines_error_findings=1)
        result = detector.evaluate(signals, "complex")
        assert result.verdict is ComplexityVerdict.CRITICAL
        assert CRITICAL_REASON_NINES_ERROR in result.reasons

    def test_critical_takes_precedence_over_warning(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(lines_changed=99999, cyclomatic_complexity=20, nines_error_findings=2)
        result = detector.evaluate(signals, "trivial")
        assert result.verdict is ComplexityVerdict.CRITICAL
        # Both critical reasons present; warn reasons NOT in result.reasons
        assert CRITICAL_REASON_CC in result.reasons
        assert CRITICAL_REASON_NINES_ERROR in result.reasons
        assert WARN_REASON_LINES not in result.reasons


# ===========================================================================
# 6. NineS warning findings → WARNING (not CRITICAL)
# ===========================================================================


class TestNinesWarnFindings:
    def test_nines_warn_finding_returns_warning(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(nines_warn_findings=3)
        result = detector.evaluate(signals, "standard")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_NINES_WARN in result.reasons


# ===========================================================================
# 7. ComplexitySignals validation
# ===========================================================================


class TestComplexitySignalsValidation:
    @pytest.mark.parametrize(
        "field_name,bad_value",
        [
            ("lines_changed", -1),
            ("files_touched", -1),
            ("new_abstractions", -1),
            ("nesting_depth_max", -1),
            ("cyclomatic_complexity", -1),
            ("ratio_to_minimal", -0.1),
            ("nines_error_findings", -1),
            ("nines_warn_findings", -1),
        ],
    )
    def test_negative_field_raises_value_error(self, field_name: str, bad_value: float) -> None:
        with pytest.raises(ValueError, match=field_name):
            ComplexitySignals(**{field_name: bad_value})

    def test_default_signals_are_zero(self) -> None:
        signals = ComplexitySignals()
        assert signals.lines_changed == 0
        assert signals.cyclomatic_complexity == 0
        assert signals.ratio_to_minimal == 0.0


# ===========================================================================
# 8. Detector configuration / validation
# ===========================================================================


class TestDetectorConfig:
    def test_default_thresholds_match_constants(self) -> None:
        detector = ComplexityDetector()
        assert detector.warning_cc_threshold == WARNING_CC_THRESHOLD
        assert detector.critical_cc_threshold == CRITICAL_CC_THRESHOLD

    def test_critical_must_exceed_warning(self) -> None:
        with pytest.raises(ValueError, match="critical_cc_threshold"):
            ComplexityDetector(warning_cc_threshold=10, critical_cc_threshold=10)

    def test_negative_warning_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="warning_cc_threshold"):
            ComplexityDetector(warning_cc_threshold=-1, critical_cc_threshold=5)

    def test_invalid_tier_string_raises(self) -> None:
        detector = ComplexityDetector()
        with pytest.raises(ValueError, match="task_complexity"):
            detector.evaluate(_signals(), "ridiculous")

    def test_non_string_tier_raises_type_error(self) -> None:
        detector = ComplexityDetector()
        with pytest.raises(TypeError, match="task_complexity"):
            detector.evaluate(_signals(), 42)  # type: ignore[arg-type]

    def test_tier_lookup_is_case_insensitive(self) -> None:
        detector = ComplexityDetector()
        # uppercase tier name should still resolve
        result = detector.evaluate(_signals(lines_changed=50), "TRIVIAL")
        assert result.task_complexity == "trivial"

    def test_custom_tier_budget_override(self) -> None:
        # Override trivial's line budget down to 25 — value 50 should now warn
        custom = TierBudgets(
            line_budget=25,
            files_budget=1,
            new_abstractions_budget=0,
            nesting_depth_budget=2,
            ratio_threshold=2.0,
        )
        detector = ComplexityDetector(tier_budgets={"trivial": custom})
        result = detector.evaluate(_signals(lines_changed=50), "trivial")
        assert result.verdict is ComplexityVerdict.WARNING
        # Other tiers preserved (merged on top of TIER_BUDGETS)
        assert detector.tier_budgets["complex"] == TIER_BUDGETS["complex"]


# ===========================================================================
# 9. wrap_nines_complexity — MOCK fallback (AC #4)
# ===========================================================================


class TestWrapNinesMockFallback:
    """AC #4: when ``nines`` binary missing, return conservative MOCK."""

    def test_missing_binary_returns_mock(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        result = wrap_nines_complexity("/tmp/some_path", binary="this_binary_does_not_exist_xyz")
        assert result.is_mock is True
        assert result.mode == "mock"
        assert "MOCK" in result.rationale or "MOCK".lower() in result.rationale.lower()
        # Conservative MOCK signals → all-zero
        assert result.signals == _conservative_mock_signals()
        # WARNING log emitted
        assert any("MOCK" in rec.message or "binary" in rec.message for rec in caplog.records)

    def test_resolve_binary_returns_none_for_missing(self) -> None:
        path = _resolve_nines_binary("definitely_not_a_real_binary_zzz")
        assert path is None

    def test_resolve_binary_default_name(self) -> None:
        # Whatever NINES_BINARY resolves to (likely None on test runner)
        result = _resolve_nines_binary(None)
        # No assertion on truthiness — both None and a real path are valid
        assert result is None or isinstance(result, str)

    def test_mock_fallback_keeps_verdict_ok(self) -> None:
        # AC #4 spirit: NineS unavailable should not cause spurious CRITICAL
        result = wrap_nines_complexity("/tmp/x", binary="nope_zzz")
        detector = ComplexityDetector()
        evaluation = detector.evaluate(result.signals, "trivial")
        assert evaluation.verdict is ComplexityVerdict.OK


# ===========================================================================
# 10. wrap_nines_complexity — runner injection (live path simulation)
# ===========================================================================


class TestWrapNinesRunnerInjection:
    def test_runner_success_parses_payload(self) -> None:
        payload = {
            "findings": [
                {"severity": "warn", "metric": "cyclomatic", "value": 12},
                {"severity": "warn", "metric": "cyclomatic", "value": 14},
                {"severity": "error", "metric": "cyclomatic", "value": 22},
            ],
            "summary": {
                "total_lines": 150,
                "total_files": 3,
                "new_classes": 2,
                "max_nesting_depth": 3,
                "ratio_to_minimal": 1.5,
            },
        }
        runner = _make_runner(_FakeRunResult(returncode=0, stdout=json.dumps(payload)))
        result = wrap_nines_complexity("/tmp/x", binary="nines", runner=runner)
        assert result.mode == "live"
        assert result.signals.cyclomatic_complexity == 22  # max of [12, 14, 22]
        assert result.signals.nines_error_findings == 1
        assert result.signals.nines_warn_findings == 2
        assert result.signals.lines_changed == 150
        assert result.signals.files_touched == 3
        assert result.signals.new_abstractions == 2
        assert len(result.raw_findings) == 3

    def test_runner_non_zero_exit_falls_back_to_mock(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        runner = _make_runner(_FakeRunResult(returncode=2, stdout="", stderr="boom"))
        result = wrap_nines_complexity("/tmp/x", binary="nines", runner=runner)
        assert result.is_mock is True
        assert "non-zero" in result.rationale or "exited" in result.rationale.lower()

    def test_runner_invalid_json_falls_back_to_mock(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)
        runner = _make_runner(_FakeRunResult(returncode=0, stdout="not json"))
        result = wrap_nines_complexity("/tmp/x", binary="nines", runner=runner)
        assert result.is_mock is True
        assert "JSON" in result.rationale.upper() or "parse" in result.rationale.lower()

    def test_runner_non_dict_payload_falls_back(self) -> None:
        runner = _make_runner(_FakeRunResult(returncode=0, stdout=json.dumps([1, 2, 3])))
        result = wrap_nines_complexity("/tmp/x", binary="nines", runner=runner)
        assert result.is_mock is True

    def test_runner_timeout_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)

        def runner(*args: Any, **kwargs: Any) -> _FakeRunResult:
            raise subprocess.TimeoutExpired(cmd="nines", timeout=1)

        result = wrap_nines_complexity("/tmp/x", binary="nines", runner=runner)
        assert result.is_mock is True
        assert "timed out" in result.rationale or "timeout" in result.rationale.lower()

    def test_runner_oserror_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.WARNING)

        def runner(*args: Any, **kwargs: Any) -> _FakeRunResult:
            raise OSError("perm denied")

        result = wrap_nines_complexity("/tmp/x", binary="nines", runner=runner)
        assert result.is_mock is True

    def test_runner_filenotfound_falls_back(self) -> None:
        def runner(*args: Any, **kwargs: Any) -> _FakeRunResult:
            raise FileNotFoundError("no such bin")

        result = wrap_nines_complexity("/tmp/x", binary="nines", runner=runner)
        assert result.is_mock is True


# ===========================================================================
# 11. _parse_nines_payload edge cases
# ===========================================================================


class TestParseNinesPayload:
    def test_empty_payload_yields_zero_signals(self) -> None:
        signals = _parse_nines_payload({})
        assert signals.cyclomatic_complexity == 0
        assert signals.nines_error_findings == 0
        assert signals.nines_warn_findings == 0

    def test_findings_not_list_treated_as_empty(self) -> None:
        signals = _parse_nines_payload({"findings": "not a list"})
        assert signals.nines_error_findings == 0

    def test_summary_not_dict_treated_as_empty(self) -> None:
        signals = _parse_nines_payload({"summary": "not a dict"})
        assert signals.lines_changed == 0

    def test_unknown_severity_ignored(self) -> None:
        signals = _parse_nines_payload(
            {"findings": [{"severity": "info", "metric": "cc", "value": 8}]}
        )
        assert signals.nines_error_findings == 0
        assert signals.nines_warn_findings == 0
        assert signals.cyclomatic_complexity == 8

    def test_non_dict_finding_skipped(self) -> None:
        signals = _parse_nines_payload(
            {"findings": ["not a dict", 42, {"severity": "error", "metric": "cc", "value": 20}]}
        )
        assert signals.nines_error_findings == 1
        assert signals.cyclomatic_complexity == 20

    def test_unparseable_cc_value_defaults_to_zero(self) -> None:
        signals = _parse_nines_payload(
            {"findings": [{"severity": "warn", "metric": "cc", "value": "garbage"}]}
        )
        assert signals.cyclomatic_complexity == 0
        assert signals.nines_warn_findings == 1


# ===========================================================================
# 12. evaluate_path convenience method
# ===========================================================================


class TestEvaluatePath:
    def test_evaluate_path_uses_wrapper(self) -> None:
        detector = ComplexityDetector()
        runner = _make_runner(_FakeRunResult(returncode=1, stdout=""))
        result = detector.evaluate_path("/tmp/x", "trivial", binary="nines", runner=runner)
        # Non-zero exit → MOCK fallback → all-zero signals → OK
        assert result.verdict is ComplexityVerdict.OK


# ===========================================================================
# 13. Profile defaults — STRICT/AUDIT 0.10, STANDARD/RELAXED 0.0
# ===========================================================================


class TestProfileComplexityWeights:
    def test_strict_profile_default_weight(self) -> None:
        assert STRICT.complexity_weight == 0.10

    def test_audit_profile_default_weight(self) -> None:
        assert AUDIT.complexity_weight == 0.10

    def test_standard_profile_default_weight(self) -> None:
        assert STANDARD.complexity_weight == 0.0

    def test_relaxed_profile_default_weight(self) -> None:
        assert RELAXED.complexity_weight == 0.0


# ===========================================================================
# 14. AC #6 — complexity_detector=None is byte-identical
# ===========================================================================


class TestByteIdenticalRegression:
    """AC #6: ``complexity_detector=None`` MUST NOT change verdict bytes."""

    def test_evaluate_gate_without_detector_unchanged(self) -> None:
        gi = _gate_input_pass()
        baseline = evaluate_gate(gi, STANDARD)
        # Same call with explicit complexity_detector=None
        with_default = evaluate_gate(gi, STANDARD, complexity_detector=None)
        assert baseline.decision == with_default.decision
        assert baseline.composite_score == with_default.composite_score
        assert "complexity" not in baseline.details
        assert "complexity" not in with_default.details

    def test_signals_without_detector_skipped(self) -> None:
        # Supplying signals but no detector → no-op
        gi = _gate_input_pass()
        signals = _signals(cyclomatic_complexity=20, nines_error_findings=5)
        verdict = evaluate_gate(
            gi, STANDARD, complexity_signals=signals, complexity_task_complexity="trivial"
        )
        assert "complexity" not in verdict.details
        assert verdict.decision == "PASS"

    def test_detector_without_signals_skipped(self) -> None:
        # Supplying detector but no signals → no-op
        gi = _gate_input_pass()
        detector = ComplexityDetector()
        verdict = evaluate_gate(gi, STANDARD, complexity_detector=detector)
        assert "complexity" not in verdict.details
        assert verdict.decision == "PASS"

    def test_evaluate_gate_critical_with_zero_weight_does_not_flip(self) -> None:
        # STANDARD profile carries complexity_weight=0.0 — even CRITICAL
        # signals must NOT flip a PASS to FAIL (S-5 + AC #6 spirit).
        gi = _gate_input_pass()
        detector = ComplexityDetector()
        verdict = evaluate_gate(
            gi,
            STANDARD,
            complexity_detector=detector,
            complexity_signals=_signals(cyclomatic_complexity=20),
            complexity_task_complexity="trivial",
        )
        assert verdict.decision == "PASS"
        assert verdict.details["complexity"]["verdict"] == "CRITICAL"
        assert verdict.details["complexity"]["weight"] == 0.0


# ===========================================================================
# 15. evaluate_gate integration — STRICT profile (weight=0.10)
# ===========================================================================


class TestEvaluateGateStrictIntegration:
    def test_critical_with_strict_weight_flips_to_fail(self) -> None:
        # STRICT profile carries complexity_weight=0.10 — CRITICAL
        # complexity verdict MUST flip a PASS to FAIL.
        gi = _gate_input_pass()
        detector = ComplexityDetector()
        verdict = evaluate_gate(
            gi,
            STRICT,
            complexity_detector=detector,
            complexity_signals=_signals(cyclomatic_complexity=20),
            complexity_task_complexity="trivial",
        )
        assert verdict.decision == "FAIL"
        assert verdict.details["complexity"]["verdict"] == "CRITICAL"
        assert verdict.details["complexity"]["weight"] == 0.10
        assert "Overcomplexity gate CRITICAL" in verdict.rationale

    def test_warning_with_strict_weight_does_not_flip(self) -> None:
        # WARNING surfaces metadata but does NOT change gate decision.
        gi = _gate_input_pass()
        detector = ComplexityDetector()
        verdict = evaluate_gate(
            gi,
            STRICT,
            complexity_detector=detector,
            complexity_signals=_signals(cyclomatic_complexity=11),
            complexity_task_complexity="trivial",
        )
        assert verdict.decision == "PASS"
        assert verdict.details["complexity"]["verdict"] == "WARNING"

    def test_ok_attaches_metadata_only(self) -> None:
        gi = _gate_input_pass()
        detector = ComplexityDetector()
        verdict = evaluate_gate(
            gi,
            STRICT,
            complexity_detector=detector,
            complexity_signals=_signals(),
            complexity_task_complexity="trivial",
        )
        assert verdict.decision == "PASS"
        assert verdict.details["complexity"]["verdict"] == "OK"
        # Signals echoed back for audit logging
        assert verdict.details["complexity"]["signals"]["cyclomatic_complexity"] == 5

    def test_critical_reduces_composite_when_present(self) -> None:
        # Convergence path produces composite_score; CRITICAL should
        # subtract weight*100 from it.
        gi = _gate_input_pass()
        history: list[Any] = []
        # Trigger convergence path with min_rounds satisfied — STRICT
        # min_rounds=2 so we pass round_num=2 with non-empty history.
        from devolaflow.gate.models import ConvergenceRound

        history.append(
            ConvergenceRound(
                round_num=1,
                composite_score=80.0,
                blocker_count=0,
                critical_count=0,
                timestamp="2026-04-21T00:00:00Z",
            )
        )
        detector = ComplexityDetector()
        verdict = evaluate_gate(
            gi,
            STRICT,
            round_num=2,
            history=history,
            complexity_detector=detector,
            complexity_signals=_signals(cyclomatic_complexity=20),
            complexity_task_complexity="trivial",
        )
        assert verdict.composite_score is not None
        # Penalty = 0.10 * 100 = 10.0
        assert verdict.details["complexity"]["composite_penalty"] == 10.0


# ===========================================================================
# 16. NinesWrapResult dataclass surface
# ===========================================================================


class TestNinesWrapResultSurface:
    def test_is_mock_property_live(self) -> None:
        signals = _conservative_mock_signals()
        result = NinesWrapResult(signals=signals, mode="live", rationale="ok")
        assert result.is_mock is False

    def test_is_mock_property_mock(self) -> None:
        signals = _conservative_mock_signals()
        result = NinesWrapResult(signals=signals, mode="mock", rationale="fallback")
        assert result.is_mock is True


# ===========================================================================
# 17. ComplexityEvaluation dataclass surface
# ===========================================================================


class TestComplexityEvaluationSurface:
    def test_evaluation_carries_signals(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(lines_changed=42)
        result = detector.evaluate(signals, "trivial")
        assert result.signals == signals

    def test_evaluation_rationale_is_human_readable(self) -> None:
        detector = ComplexityDetector()
        result = detector.evaluate(_signals(lines_changed=200), "trivial")
        # WARNING rationale mentions tier and the failing dimension
        assert "trivial" in result.rationale
        assert "lines" in result.rationale or "WARNING" in result.rationale.upper()


# ===========================================================================
# 18. TIER_BUDGETS constants invariants
# ===========================================================================


class TestTierBudgetInvariants:
    def test_all_four_tiers_present(self) -> None:
        assert set(TIER_BUDGETS) == {"trivial", "simple", "standard", "complex"}

    def test_budgets_are_monotonic(self) -> None:
        # Each successive tier has a larger or equal budget on every axis
        order = ["trivial", "simple", "standard", "complex"]
        for prev, nxt in zip(order, order[1:], strict=False):
            assert TIER_BUDGETS[nxt].line_budget >= TIER_BUDGETS[prev].line_budget
            assert TIER_BUDGETS[nxt].files_budget >= TIER_BUDGETS[prev].files_budget
            assert (
                TIER_BUDGETS[nxt].new_abstractions_budget
                >= TIER_BUDGETS[prev].new_abstractions_budget
            )
            assert TIER_BUDGETS[nxt].nesting_depth_budget >= TIER_BUDGETS[prev].nesting_depth_budget
            assert TIER_BUDGETS[nxt].ratio_threshold >= TIER_BUDGETS[prev].ratio_threshold


# ===========================================================================
# 19. Integration smoke test — end-to-end via gate __init__
# ===========================================================================


class TestIntegrationSmoke:
    def test_imports_resolve_via_gate_namespace(self) -> None:
        # All public names exported from devolaflow.gate
        from devolaflow.gate import (
            ComplexityDetector as PublicDetector,
        )
        from devolaflow.gate import (
            ComplexitySignals as PublicSignals,
        )
        from devolaflow.gate import (
            ComplexityVerdict as PublicVerdict,
        )
        from devolaflow.gate import (
            wrap_nines_complexity as public_wrap,
        )

        assert PublicDetector is ComplexityDetector
        assert PublicSignals is ComplexitySignals
        assert PublicVerdict is ComplexityVerdict
        assert public_wrap is wrap_nines_complexity

    def test_round_trip_signals_to_verdict_to_evaluation(self) -> None:
        # Build, evaluate, inspect — happy path smoke test
        signals = _signals(cyclomatic_complexity=11)
        detector = ComplexityDetector()
        evaluation = detector.evaluate(signals, "complex")
        assert isinstance(evaluation, ComplexityEvaluation)
        assert evaluation.verdict is ComplexityVerdict.WARNING


# ===========================================================================
# 20. Default NINES_BINARY constant
# ===========================================================================


class TestNinesConstants:
    def test_default_binary_name(self) -> None:
        assert NINES_BINARY == "nines"

    def test_critical_threshold_higher_than_warning(self) -> None:
        assert CRITICAL_CC_THRESHOLD > WARNING_CC_THRESHOLD
