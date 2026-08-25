"""Comprehensive tests for deterministic local complexity inspection.

Covers the patch_plan §3 P-09 acceptance criteria:

- ``ComplexityDetector.evaluate()`` correctly classifies the OK /
  WARNING / CRITICAL paths across the 4 task complexity tiers
  (trivial / simple / standard / complex).
- ``inspect_complexity_path()`` measures sorted local Python files without
  invoking an external binary.
- Legacy NineS-named aliases were removed in v17.0.0; absence is pinned.
- ``complexity_detector=None`` keeps :func:`evaluate_gate` byte-identical
  to pre-P-09 behaviour (``patch_plan §3 P-09 AC #6``).

Target: ≥ 90 % line coverage on
``src/devolaflow/gate/complexity_detector.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

import devolaflow.gate as gate_namespace
import devolaflow.gate.complexity_detector as complexity_detector_module
from devolaflow.gate import (
    AUDIT,
    RELAXED,
    STANDARD,
    STRICT,
    CheckResult,
    ComplexityDetector,
    ComplexityEvaluation,
    ComplexityProbeResult,
    ComplexitySignals,
    ComplexityVerdict,
    GateInput,
    evaluate_gate,
    inspect_complexity_path,
)
from devolaflow.gate.complexity_detector import (
    CRITICAL_CC_THRESHOLD,
    CRITICAL_REASON_CC,
    CRITICAL_REASON_ERROR_FINDINGS,
    TIER_BUDGETS,
    WARN_REASON_ABSTRACTIONS,
    WARN_REASON_CC,
    WARN_REASON_FILES,
    WARN_REASON_LINES,
    WARN_REASON_NESTING,
    WARN_REASON_RATIO,
    WARN_REASON_WARNING_FINDINGS,
    WARNING_CC_THRESHOLD,
    TierBudgets,
    _conservative_mock_signals,
    _zero_complexity_signals,
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
        "error_findings": 0,
        "warning_findings": 0,
    }
    defaults.update(kwargs)
    if "nines_error_findings" in kwargs:
        defaults.pop("error_findings")
    if "nines_warn_findings" in kwargs:
        defaults.pop("warning_findings")
    return ComplexitySignals(**defaults)


def _write_python(path: Path, source: str) -> Path:
    """Write one deterministic Python fixture and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


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
# 5. CRITICAL paths — cc > 15 OR ERROR-severity finding
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
        assert CRITICAL_REASON_ERROR_FINDINGS in result.reasons

    def test_critical_takes_precedence_over_warning(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(lines_changed=99999, cyclomatic_complexity=20, nines_error_findings=2)
        result = detector.evaluate(signals, "trivial")
        assert result.verdict is ComplexityVerdict.CRITICAL
        # Both critical reasons present; warn reasons NOT in result.reasons
        assert CRITICAL_REASON_CC in result.reasons
        assert CRITICAL_REASON_ERROR_FINDINGS in result.reasons
        assert WARN_REASON_LINES not in result.reasons


# ===========================================================================
# 6. Warning-severity findings → WARNING (not CRITICAL)
# ===========================================================================


class TestNinesWarnFindings:
    def test_nines_warn_finding_returns_warning(self) -> None:
        detector = ComplexityDetector()
        signals = _signals(nines_warn_findings=3)
        result = detector.evaluate(signals, "standard")
        assert result.verdict is ComplexityVerdict.WARNING
        assert WARN_REASON_WARNING_FINDINGS in result.reasons


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
            ("error_findings", -1),
            ("warning_findings", -1),
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
        assert signals.error_findings == 0
        assert signals.warning_findings == 0
        assert signals.nines_error_findings == signals.error_findings
        assert signals.nines_warn_findings == signals.warning_findings


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
# 9. Degraded local inspection
# ===========================================================================


class TestLocalInspectionDegraded:
    """Missing and unsupported paths produce explicit logged degradation."""

    def test_missing_path_returns_degraded(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        result = inspect_complexity_path(tmp_path / "missing")
        assert result.is_degraded is True
        assert result.mode == "degraded"
        assert result.signals == _zero_complexity_signals()
        assert result.errors and "does not exist" in result.errors[0]
        assert any("degraded" in record.message for record in caplog.records)

    def test_non_python_file_returns_degraded(self, tmp_path: Path) -> None:
        target = tmp_path / "notes.txt"
        target.write_text("not Python\n", encoding="utf-8")
        result = inspect_complexity_path(target)
        assert result.is_degraded is True
        assert "not a Python file" in result.errors[0]

    def test_legacy_probe_names_are_removed(self) -> None:
        # v17.0.0: the deprecated NineS-named compatibility aliases are gone.
        for removed in (
            "wrap_nines_complexity",
            "NinesWrapResult",
            "NINES_BINARY",
            "NINES_TIMEOUT_SECONDS",
            "WARN_REASON_NINES_WARN",
            "CRITICAL_REASON_NINES_ERROR",
        ):
            assert not hasattr(complexity_detector_module, removed)
            assert not hasattr(gate_namespace, removed)
        assert _conservative_mock_signals is _zero_complexity_signals

    def test_degraded_result_keeps_verdict_ok(self, tmp_path: Path) -> None:
        result = inspect_complexity_path(tmp_path / "missing", binary="ignored")
        evaluation = ComplexityDetector().evaluate(result.signals, "trivial")
        assert evaluation.verdict is ComplexityVerdict.OK


# ===========================================================================
# 10. Deterministic local metrics and ignored legacy arguments
# ===========================================================================


class TestLocalInspectionMetrics:
    def test_directory_inspection_measures_sorted_python_files(self, tmp_path: Path) -> None:
        _write_python(
            tmp_path / "z.py",
            "class Z:\n    pass\n",
        )
        _write_python(
            tmp_path / "a.py",
            "class A:\n"
            "    def branch(self, value):\n"
            "        if value:\n"
            "            for item in range(value):\n"
            "                if item:\n"
            "                    return item\n"
            "        return 0\n",
        )
        result = inspect_complexity_path(tmp_path)
        assert result.mode == "local"
        assert [Path(path).name for path in result.inspected_files] == ["a.py", "z.py"]
        assert result.signals.lines_changed == 9
        assert result.signals.files_touched == 2
        assert result.signals.new_abstractions == 2
        assert result.signals.nesting_depth_max == 3
        assert result.signals.cyclomatic_complexity == 4

    def test_single_python_file_is_supported(self, tmp_path: Path) -> None:
        target = _write_python(tmp_path / "one.py", "def one():\n    return 1\n")
        result = inspect_complexity_path(target)
        assert result.mode == "local"
        assert result.signals.files_touched == 1
        assert result.signals.lines_changed == 2
        assert result.inspected_files == (target.as_posix(),)

    def test_ratio_is_explicitly_unmeasurable(self, tmp_path: Path) -> None:
        _write_python(tmp_path / "one.py", "value = 1\n")
        result = inspect_complexity_path(tmp_path)
        assert result.signals.ratio_to_minimal == 0.0
        assert "unmeasurable" in result.rationale

    def test_legacy_runner_argument_is_never_called(self, tmp_path: Path) -> None:
        _write_python(tmp_path / "one.py", "value = 1\n")
        called = False

        def runner(*_args: Any, **_kwargs: Any) -> None:
            nonlocal called
            called = True
            raise AssertionError("legacy runner must never execute")

        result = inspect_complexity_path(tmp_path, runner=runner)
        assert result.mode == "local"
        assert called is False

    def test_legacy_binary_and_timeout_arguments_are_ignored(self, tmp_path: Path) -> None:
        _write_python(tmp_path / "one.py", "value = 1\n")
        result = inspect_complexity_path(
            tmp_path,
            binary="definitely-not-executable",
            timeout=1,
        )
        assert result.mode == "local"
        assert result.errors == ()

    def test_syntax_error_is_explicitly_degraded(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _write_python(tmp_path / "broken.py", "def broken(:\n")
        caplog.set_level(logging.WARNING)
        result = inspect_complexity_path(tmp_path)
        assert result.mode == "degraded"
        assert result.errors and "SyntaxError" in result.errors[0]
        assert any("cannot measure" in record.message for record in caplog.records)

    def test_non_python_files_are_ignored_in_directory(self, tmp_path: Path) -> None:
        _write_python(tmp_path / "kept.py", "value = 1\n")
        (tmp_path / "ignored.json").write_text('{"value": 2}\n', encoding="utf-8")
        result = inspect_complexity_path(tmp_path)
        assert result.mode == "local"
        assert [Path(path).name for path in result.inspected_files] == ["kept.py"]
        assert result.signals.files_touched == 1


# ===========================================================================
# 11. Local measurement edge cases
# ===========================================================================


class TestLocalMeasurementEdges:
    def test_empty_directory_yields_zero_signals(self, tmp_path: Path) -> None:
        result = inspect_complexity_path(tmp_path)
        assert result.mode == "local"
        assert result.signals == _zero_complexity_signals()

    def test_loc_counts_physical_source_lines(self, tmp_path: Path) -> None:
        _write_python(tmp_path / "a.py", "first = 1\n\nthird = 3\n")
        _write_python(tmp_path / "b.py", "only = 1\n")
        assert inspect_complexity_path(tmp_path).signals.lines_changed == 4

    def test_class_count_includes_nested_classes(self, tmp_path: Path) -> None:
        _write_python(
            tmp_path / "classes.py",
            "class Outer:\n    class Inner:\n        pass\n",
        )
        assert inspect_complexity_path(tmp_path).signals.new_abstractions == 2

    def test_max_control_flow_nesting_is_measured(self, tmp_path: Path) -> None:
        _write_python(
            tmp_path / "nested.py",
            "def nested(items):\n"
            "    for item in items:\n"
            "        if item:\n"
            "            while item:\n"
            "                item -= 1\n",
        )
        assert inspect_complexity_path(tmp_path).signals.nesting_depth_max == 3

    def test_max_cyclomatic_complexity_is_measured(self, tmp_path: Path) -> None:
        _write_python(
            tmp_path / "branch.py",
            "def decide(left, right):\n"
            "    if left and right:\n"
            "        return True\n"
            "    return False\n",
        )
        assert inspect_complexity_path(tmp_path).signals.cyclomatic_complexity == 3

    def test_unreadable_file_is_logged_degraded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        target = _write_python(tmp_path / "blocked.py", "value = 1\n")
        original_read_text = Path.read_text

        def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
            if path == target:
                raise PermissionError("blocked fixture")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)
        caplog.set_level(logging.WARNING)
        result = inspect_complexity_path(tmp_path)
        assert result.mode == "degraded"
        assert result.errors and "PermissionError" in result.errors[0]
        assert any("blocked fixture" in record.message for record in caplog.records)


# ===========================================================================
# 12. evaluate_path convenience method
# ===========================================================================


class TestEvaluatePath:
    def test_evaluate_path_uses_local_inspector(self, tmp_path: Path) -> None:
        target = _write_python(tmp_path / "simple.py", "def simple():\n    return 1\n")
        detector = ComplexityDetector()
        result = detector.evaluate_path(
            target,
            "trivial",
            binary="ignored",
            runner=lambda *_args, **_kwargs: pytest.fail("runner executed"),
        )
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
        details = verdict.details["complexity"]["signals"]
        assert details["cyclomatic_complexity"] == 5
        assert details["error_findings"] == details["nines_error_findings"] == 0
        assert details["warning_findings"] == details["nines_warn_findings"] == 0

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
# 16. ComplexityProbeResult and compatibility surface
# ===========================================================================


class TestComplexityProbeResultSurface:
    def test_is_mock_property_live(self) -> None:
        signals = _zero_complexity_signals()
        result = ComplexityProbeResult(signals=signals, mode="local", rationale="ok")
        assert result.is_degraded is False
        assert result.is_mock is False

    def test_is_mock_property_mock(self) -> None:
        signals = _zero_complexity_signals()
        result = ComplexityProbeResult(signals=signals, mode="degraded", rationale="fallback")
        assert result.is_degraded is True
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
            inspect_complexity_path as public_inspect,
        )

        assert PublicDetector is ComplexityDetector
        assert PublicSignals is ComplexitySignals
        assert PublicVerdict is ComplexityVerdict
        assert public_inspect is inspect_complexity_path

    def test_round_trip_signals_to_verdict_to_evaluation(self) -> None:
        # Build, evaluate, inspect — happy path smoke test
        signals = _signals(cyclomatic_complexity=11)
        detector = ComplexityDetector()
        evaluation = detector.evaluate(signals, "complex")
        assert isinstance(evaluation, ComplexityEvaluation)
        assert evaluation.verdict is ComplexityVerdict.WARNING


# ===========================================================================
# 20. Threshold constants
# ===========================================================================


class TestThresholdConstants:
    def test_critical_threshold_higher_than_warning(self) -> None:
        assert CRITICAL_CC_THRESHOLD > WARNING_CC_THRESHOLD
