"""Comprehensive tests for the NineS integration modules.

Covers: detector, scorer, advisor, and gate/scorer NineS bridge.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from devolaflow.gate.models import (
    CheckResult,
    ConvergenceRound,
    GateInput,
    GateVerdict,
)
from devolaflow.gate.profiles import STANDARD
from devolaflow.gate.scorer import evaluate_gate_with_nines
from devolaflow.nines.advisor import (
    NinesAdvisorConfig,
    _interpret_result,
    _run_nines_command,
    get_research_advice,
    run_nines_advisor,
    should_invoke_advisor,
)
from devolaflow.nines.detector import (
    _KNOWN_SUBCOMMANDS,
    NinesStatus,
    detect_nines,
    ensure_nines,
    get_nines_capabilities,
)
from devolaflow.nines.researcher import (
    NinesResearchConfig,
    analyze_target,
    collect_research,
    run_self_evaluation,
    run_skill_iteration,
)
from devolaflow.nines.scorer import (
    DIMENSION_KEYS,
    FALLBACK_SCORE,
    NinesScorerConfig,
    _run_cli,
    _score_or_fallback,
    nines_dimension_scores,
    run_nines_analyze,
    run_nines_eval,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _pass_input() -> GateInput:
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        review_findings=[],
        acceptance_criteria_results=CheckResult(status="pass"),
    )


def _make_verdict(
    *,
    advisor_recommended: bool = False,
    composite_score: float | None = None,
) -> GateVerdict:
    return GateVerdict(
        decision="FAIL",
        rationale="Borderline score",
        composite_score=composite_score,
        meets_threshold=False,
        advisor_recommended=advisor_recommended,
    )


def _mock_proc(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


def _round(num: int, score: float) -> ConvergenceRound:
    return ConvergenceRound(
        round_num=num,
        composite_score=score,
        blocker_count=0,
        critical_count=0,
        timestamp="2026-04-13T00:00:00Z",
    )


# ===========================================================================
# detector.py
# ===========================================================================


class TestNinesStatus:
    def test_default_values(self) -> None:
        s = NinesStatus()
        assert s.available is False
        assert s.version is None
        assert s.path is None
        assert s.capabilities == []

    def test_frozen(self) -> None:
        s = NinesStatus(available=True, version="1.0.0", path="/usr/bin/nines")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.available = False  # type: ignore[misc]

    def test_custom_values(self) -> None:
        s = NinesStatus(
            available=True,
            version="2.1.0",
            path="/usr/local/bin/nines",
            capabilities=["eval", "analyze"],
        )
        assert s.available is True
        assert s.version == "2.1.0"
        assert s.path == "/usr/local/bin/nines"
        assert s.capabilities == ["eval", "analyze"]


class TestDetectNines:
    @patch("devolaflow.nines.detector.subprocess.run")
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_detect_when_available(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="nines version 1.2.3")
        status = detect_nines()
        assert status.available is True
        assert status.version == "1.2.3"
        assert status.path == "/usr/bin/nines"
        mock_which.assert_called_once_with("nines")
        mock_run.assert_called_once()

    @patch("devolaflow.nines.detector.shutil.which", return_value=None)
    def test_detect_when_not_on_path(self, mock_which: MagicMock) -> None:
        status = detect_nines()
        assert status.available is False
        assert status.version is None
        assert status.path is None

    @patch(
        "devolaflow.nines.detector.subprocess.run",
        side_effect=subprocess.TimeoutExpired("nines", 30),
    )
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_detect_timeout(self, _which: MagicMock, _run: MagicMock) -> None:
        status = detect_nines()
        assert status.available is False
        assert status.path == "/usr/bin/nines"
        assert status.version is None

    @patch("devolaflow.nines.detector.subprocess.run", side_effect=OSError("exec failed"))
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_detect_oserror(self, _which: MagicMock, _run: MagicMock) -> None:
        status = detect_nines()
        assert status.available is False
        assert status.path == "/usr/bin/nines"

    @patch("devolaflow.nines.detector.subprocess.run")
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_version_parsing_semver(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="nines version 2.0.0-rc1")
        status = detect_nines()
        assert status.version == "2.0.0-rc1"

    @patch("devolaflow.nines.detector.subprocess.run")
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_version_parsing_no_match(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="nines unknown output")
        status = detect_nines()
        assert status.available is True
        assert status.version is None

    @patch("devolaflow.nines.detector.subprocess.run")
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_version_nonzero_exit(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1, stdout="version 3.0.0")
        status = detect_nines()
        assert status.available is True
        assert status.version is None


class TestEnsureNines:
    @patch("devolaflow.nines.detector.detect_nines")
    def test_ensure_already_available(self, mock_detect: MagicMock) -> None:
        mock_detect.return_value = NinesStatus(
            available=True, version="1.0.0", path="/usr/bin/nines"
        )
        status = ensure_nines()
        assert status.available is True
        mock_detect.assert_called_once()

    @patch("devolaflow.nines.detector.detect_nines")
    def test_ensure_not_available_no_install(self, mock_detect: MagicMock) -> None:
        mock_detect.return_value = NinesStatus()
        status = ensure_nines(auto_install=False)
        assert status.available is False
        mock_detect.assert_called_once()

    @patch("devolaflow.nines.detector.detect_nines")
    @patch("devolaflow.nines.detector.subprocess.run")
    def test_ensure_auto_install(self, mock_run: MagicMock, mock_detect: MagicMock) -> None:
        mock_detect.side_effect = [
            NinesStatus(),
            NinesStatus(available=True, version="1.0.0", path="/usr/bin/nines"),
        ]
        mock_run.return_value = _mock_proc()
        status = ensure_nines(auto_install=True)
        assert status.available is True
        assert mock_detect.call_count == 2
        mock_run.assert_called_once()

    @patch("devolaflow.nines.detector.detect_nines")
    @patch("devolaflow.nines.detector.subprocess.run", side_effect=OSError("no bash"))
    def test_ensure_auto_install_failure(self, _run: MagicMock, mock_detect: MagicMock) -> None:
        mock_detect.return_value = NinesStatus()
        status = ensure_nines(auto_install=True)
        assert status.available is False


class TestGetCapabilities:
    @patch("devolaflow.nines.detector.subprocess.run")
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_capabilities_when_available(self, _which: MagicMock, mock_run: MagicMock) -> None:
        help_text = (
            "Commands:\n  eval      Run evaluation\n"
            "  analyze   Analyze code\n  collect   Collect metrics\n"
        )
        mock_run.return_value = _mock_proc(stdout=help_text)
        caps = get_nines_capabilities()
        assert "eval" in caps
        assert "analyze" in caps
        assert "collect" in caps

    @patch("devolaflow.nines.detector.shutil.which", return_value=None)
    def test_capabilities_when_not_available(self, _which: MagicMock) -> None:
        caps = get_nines_capabilities()
        assert caps == []

    @patch("devolaflow.nines.detector.subprocess.run", side_effect=OSError("exec failed"))
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_capabilities_fallback_on_error(self, _which: MagicMock, _run: MagicMock) -> None:
        caps = get_nines_capabilities()
        assert caps == list(_KNOWN_SUBCOMMANDS)

    @patch("devolaflow.nines.detector.subprocess.run")
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_capabilities_nonzero_exit(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1)
        caps = get_nines_capabilities()
        assert caps == list(_KNOWN_SUBCOMMANDS)

    @patch("devolaflow.nines.detector.subprocess.run")
    @patch("devolaflow.nines.detector.shutil.which", return_value="/usr/bin/nines")
    def test_capabilities_empty_output_returns_known(
        self, _which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = _mock_proc(stdout="")
        caps = get_nines_capabilities()
        assert caps == list(_KNOWN_SUBCOMMANDS)


# ===========================================================================
# scorer.py
# ===========================================================================


class TestNinesScorerConfig:
    def test_default_values(self) -> None:
        cfg = NinesScorerConfig()
        assert cfg.test_suite is None
        assert cfg.review_path is None
        assert cfg.architecture_path is None
        assert cfg.benchmark_suite is None
        assert cfg.timeout == 120
        assert cfg.extra_eval_args == []
        assert cfg.extra_analyze_args == []

    def test_custom_values(self) -> None:
        cfg = NinesScorerConfig(
            test_suite="tests/",
            review_path="src/",
            architecture_path="docs/arch.md",
            benchmark_suite="bench/",
            timeout=60,
            extra_eval_args=["--verbose"],
            extra_analyze_args=["--deep"],
        )
        assert cfg.test_suite == "tests/"
        assert cfg.review_path == "src/"
        assert cfg.timeout == 60
        assert cfg.extra_eval_args == ["--verbose"]


class TestRunCli:
    @patch("devolaflow.nines.scorer.subprocess.run")
    def test_run_cli_success(self, mock_run: MagicMock) -> None:
        payload = {"score": 85.0, "status": "pass"}
        mock_run.return_value = _mock_proc(stdout=json.dumps(payload))
        result = _run_cli(["nines", "eval", "."], timeout=60)
        assert result == payload

    @patch(
        "devolaflow.nines.scorer.subprocess.run",
        side_effect=subprocess.TimeoutExpired("nines", 60),
    )
    def test_run_cli_timeout(self, _run: MagicMock) -> None:
        assert _run_cli(["nines", "eval", "."], timeout=60) == {}

    @patch("devolaflow.nines.scorer.subprocess.run", side_effect=OSError("not found"))
    def test_run_cli_oserror(self, _run: MagicMock) -> None:
        assert _run_cli(["nines", "eval", "."], timeout=60) == {}

    @patch("devolaflow.nines.scorer.subprocess.run")
    def test_run_cli_bad_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="not valid json {{{")
        assert _run_cli(["nines", "eval", "."], timeout=60) == {}

    @patch("devolaflow.nines.scorer.subprocess.run")
    def test_run_cli_nonzero_exit(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1, stderr="error")
        assert _run_cli(["nines", "eval", "."], timeout=60) == {}


class TestScoreOrFallback:
    def test_valid_score(self) -> None:
        assert _score_or_fallback({"score": 88.5}) == 88.5

    def test_missing_key(self) -> None:
        assert _score_or_fallback({}) == FALLBACK_SCORE

    def test_none_value(self) -> None:
        assert _score_or_fallback({"score": None}) == FALLBACK_SCORE

    def test_non_numeric_value(self) -> None:
        assert _score_or_fallback({"score": "bad"}) == FALLBACK_SCORE

    def test_string_numeric_coerced(self) -> None:
        assert _score_or_fallback({"score": "92"}) == 92.0

    def test_custom_key(self) -> None:
        assert _score_or_fallback({"quality": 77.0}, key="quality") == 77.0


class TestRunNinesEval:
    @patch("devolaflow.nines.scorer._run_cli")
    def test_eval_success(self, mock_cli: MagicMock) -> None:
        mock_cli.return_value = {"score": 90.0}
        result = run_nines_eval("artifact/")
        assert result == {"score": 90.0}
        cmd = mock_cli.call_args[0][0]
        assert cmd[:3] == ["nines", "eval", "artifact/"]
        assert "--scorer" in cmd
        assert "--format" in cmd

    @patch("devolaflow.nines.scorer._run_cli", return_value={})
    def test_eval_timeout(self, mock_cli: MagicMock) -> None:
        result = run_nines_eval("artifact/", timeout=5)
        assert result == {}
        assert mock_cli.call_args[0][1] == 5

    @patch("devolaflow.nines.scorer._run_cli", return_value={})
    def test_eval_bad_json(self, mock_cli: MagicMock) -> None:
        assert run_nines_eval("artifact/") == {}

    @patch("devolaflow.nines.scorer._run_cli", return_value={})
    def test_eval_nonzero_exit(self, mock_cli: MagicMock) -> None:
        assert run_nines_eval("artifact/") == {}

    @patch("devolaflow.nines.scorer._run_cli")
    def test_eval_extra_args(self, mock_cli: MagicMock) -> None:
        mock_cli.return_value = {"score": 80.0}
        run_nines_eval("artifact/", extra_args=["--verbose", "--strict"])
        cmd = mock_cli.call_args[0][0]
        assert "--verbose" in cmd
        assert "--strict" in cmd


class TestRunNinesAnalyze:
    @patch("devolaflow.nines.scorer._run_cli")
    def test_analyze_success(self, mock_cli: MagicMock) -> None:
        mock_cli.return_value = {"score": 75.0, "issues": 3}
        result = run_nines_analyze("src/")
        assert result == {"score": 75.0, "issues": 3}
        cmd = mock_cli.call_args[0][0]
        assert cmd[:3] == ["nines", "analyze", "src/"]
        assert "--depth" in cmd

    @patch("devolaflow.nines.scorer._run_cli", return_value={})
    def test_analyze_failure(self, mock_cli: MagicMock) -> None:
        assert run_nines_analyze("src/") == {}

    @patch("devolaflow.nines.scorer._run_cli")
    def test_analyze_extra_args(self, mock_cli: MagicMock) -> None:
        mock_cli.return_value = {}
        run_nines_analyze("src/", extra_args=["--agent-impact"])
        cmd = mock_cli.call_args[0][0]
        assert "--agent-impact" in cmd


class TestNinesDimensionScores:
    @patch("devolaflow.nines.scorer.run_nines_analyze")
    @patch("devolaflow.nines.scorer.run_nines_eval")
    def test_all_dimensions_configured(self, mock_eval: MagicMock, mock_analyze: MagicMock) -> None:
        mock_eval.return_value = {"score": 88.0}
        mock_analyze.return_value = {"score": 92.0}
        cfg = NinesScorerConfig(
            test_suite="tests/",
            review_path="src/",
            architecture_path="docs/",
            benchmark_suite="bench/",
        )
        scores = nines_dimension_scores(cfg, "artifact/")
        assert set(scores.keys()) == set(DIMENSION_KEYS)
        assert scores["test_quality"] == 88.0
        assert scores["code_review"] == 92.0
        assert scores["architecture"] == 92.0
        assert scores["benchmark"] == 88.0

    def test_no_dimensions_configured(self) -> None:
        cfg = NinesScorerConfig()
        scores = nines_dimension_scores(cfg, "artifact/")
        for key in DIMENSION_KEYS:
            assert scores[key] == FALLBACK_SCORE

    @patch("devolaflow.nines.scorer.run_nines_eval")
    def test_partial_config(self, mock_eval: MagicMock) -> None:
        mock_eval.return_value = {"score": 80.0}
        cfg = NinesScorerConfig(test_suite="tests/")
        scores = nines_dimension_scores(cfg, "artifact/")
        assert scores["test_quality"] == 80.0
        assert scores["code_review"] == FALLBACK_SCORE
        assert scores["architecture"] == FALLBACK_SCORE
        assert scores["benchmark"] == FALLBACK_SCORE

    @patch("devolaflow.nines.scorer.run_nines_eval", return_value={})
    def test_eval_failure_uses_fallback(self, _eval: MagicMock) -> None:
        cfg = NinesScorerConfig(test_suite="tests/")
        scores = nines_dimension_scores(cfg, "artifact/")
        assert scores["test_quality"] == FALLBACK_SCORE


class TestDimensionKeysConstant:
    def test_dimension_keys(self) -> None:
        assert DIMENSION_KEYS == ("test_quality", "code_review", "architecture", "benchmark")

    def test_fallback_score(self) -> None:
        assert FALLBACK_SCORE == 100.0


# ===========================================================================
# advisor.py
# ===========================================================================


class TestNinesAdvisorConfig:
    def test_default_values(self) -> None:
        cfg = NinesAdvisorConfig()
        assert cfg.enabled is False
        assert "self-eval" in cfg.commands
        assert cfg.triggers == ["self-eval"]
        assert cfg.max_retries == 2

    def test_custom_values(self) -> None:
        cfg = NinesAdvisorConfig(
            enabled=True,
            commands={"check": "nines check"},
            triggers=["check"],
            max_retries=5,
        )
        assert cfg.enabled is True
        assert cfg.commands == {"check": "nines check"}
        assert cfg.max_retries == 5


class TestShouldInvokeAdvisor:
    def test_invoke_when_recommended_and_enabled(self) -> None:
        verdict = _make_verdict(advisor_recommended=True)
        config = NinesAdvisorConfig(enabled=True)
        assert should_invoke_advisor(verdict, config) is True

    def test_no_invoke_when_not_recommended(self) -> None:
        verdict = _make_verdict(advisor_recommended=False)
        config = NinesAdvisorConfig(enabled=True)
        assert should_invoke_advisor(verdict, config) is False

    def test_no_invoke_when_disabled(self) -> None:
        verdict = _make_verdict(advisor_recommended=True)
        config = NinesAdvisorConfig(enabled=False)
        assert should_invoke_advisor(verdict, config) is False

    def test_no_invoke_when_both_false(self) -> None:
        verdict = _make_verdict(advisor_recommended=False)
        config = NinesAdvisorConfig(enabled=False)
        assert should_invoke_advisor(verdict, config) is False


class TestRunNinesCommand:
    @patch("devolaflow.nines.advisor.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        payload = {"score": 85, "status": "pass"}
        mock_run.return_value = _mock_proc(stdout=json.dumps(payload))
        result = _run_nines_command("nines self-eval --format json", retries=2)
        assert result == payload

    @patch("devolaflow.nines.advisor.subprocess.run")
    def test_nonzero_exit_retries(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1, stderr="error")
        result = _run_nines_command("nines self-eval", retries=2)
        assert result is None
        assert mock_run.call_count == 2

    @patch(
        "devolaflow.nines.advisor.subprocess.run",
        side_effect=subprocess.TimeoutExpired("nines", 120),
    )
    def test_timeout_retries(self, mock_run: MagicMock) -> None:
        result = _run_nines_command("nines self-eval", retries=3)
        assert result is None
        assert mock_run.call_count == 3

    @patch("devolaflow.nines.advisor.subprocess.run", side_effect=OSError("not found"))
    def test_oserror_retries(self, mock_run: MagicMock) -> None:
        result = _run_nines_command("nines self-eval", retries=2)
        assert result is None
        assert mock_run.call_count == 2

    @patch("devolaflow.nines.advisor.subprocess.run")
    def test_bad_json_retries(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="not json")
        result = _run_nines_command("nines self-eval", retries=2)
        assert result is None
        assert mock_run.call_count == 2

    @patch("devolaflow.nines.advisor.subprocess.run")
    def test_success_on_second_attempt(self, mock_run: MagicMock) -> None:
        payload = {"score": 80}
        mock_run.side_effect = [
            _mock_proc(returncode=1, stderr="error"),
            _mock_proc(stdout=json.dumps(payload)),
        ]
        result = _run_nines_command("nines self-eval", retries=2)
        assert result == payload
        assert mock_run.call_count == 2


class TestInterpretResult:
    def test_score_above_threshold(self) -> None:
        verdict, reasoning = _interpret_result({"score": 85, "reasoning": "looks good"})
        assert verdict == "APPROVE"
        assert "looks good" in reasoning

    def test_score_below_threshold(self) -> None:
        verdict, reasoning = _interpret_result({"score": 50, "reasoning": "many issues"})
        assert verdict == "REJECT"
        assert "many issues" in reasoning

    def test_score_at_threshold(self) -> None:
        verdict, _ = _interpret_result({"score": 70})
        assert verdict == "APPROVE"

    def test_status_pass(self) -> None:
        verdict, _ = _interpret_result({"status": "pass"})
        assert verdict == "APPROVE"

    def test_status_approved(self) -> None:
        verdict, _ = _interpret_result({"status": "approved"})
        assert verdict == "APPROVE"

    def test_status_ok(self) -> None:
        verdict, _ = _interpret_result({"status": "ok"})
        assert verdict == "APPROVE"

    def test_no_score_no_status(self) -> None:
        verdict, reasoning = _interpret_result({})
        assert verdict == "REJECT"
        assert "not return a passing status" in reasoning

    def test_overall_score_key(self) -> None:
        verdict, _ = _interpret_result({"overall_score": 90})
        assert verdict == "APPROVE"

    def test_quality_score_key(self) -> None:
        verdict, _ = _interpret_result({"quality_score": 40})
        assert verdict == "REJECT"

    def test_summary_used_as_reasoning(self) -> None:
        _, reasoning = _interpret_result({"score": 80, "summary": "Good quality"})
        assert reasoning == "Good quality"

    def test_non_numeric_score_falls_to_status(self) -> None:
        verdict, _ = _interpret_result({"score": "not_a_number", "status": "pass"})
        assert verdict == "APPROVE"


class TestRunNinesAdvisor:
    @patch("devolaflow.nines.advisor._run_nines_command")
    def test_advisor_enriches_verdict(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = {"score": 85, "reasoning": "Quality meets bar"}
        verdict = _make_verdict(advisor_recommended=True)
        config = NinesAdvisorConfig(enabled=True, triggers=["self-eval"])
        result = run_nines_advisor(verdict, config, artifact_path="artifact/")
        assert result.advisor_verdict == "APPROVE"
        assert "NineS (self-eval)" in result.advisor_context
        assert "Quality meets bar" in result.advisor_context

    def test_advisor_skips_when_not_recommended(self) -> None:
        verdict = _make_verdict(advisor_recommended=False)
        config = NinesAdvisorConfig(enabled=True)
        result = run_nines_advisor(verdict, config, artifact_path="artifact/")
        assert result.advisor_verdict == ""
        assert result is verdict

    def test_advisor_skips_when_disabled(self) -> None:
        verdict = _make_verdict(advisor_recommended=True)
        config = NinesAdvisorConfig(enabled=False)
        result = run_nines_advisor(verdict, config, artifact_path="artifact/")
        assert result.advisor_verdict == ""
        assert result is verdict

    @patch("devolaflow.nines.advisor._run_nines_command", return_value=None)
    def test_advisor_handles_cli_failure(self, _cmd: MagicMock) -> None:
        verdict = _make_verdict(advisor_recommended=True)
        config = NinesAdvisorConfig(enabled=True, triggers=["self-eval"])
        result = run_nines_advisor(verdict, config, artifact_path="artifact/")
        assert result.advisor_verdict == ""
        assert result is verdict

    @patch("devolaflow.nines.advisor._run_nines_command")
    def test_advisor_with_path_formatting(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = {"score": 90, "reasoning": "ok"}
        verdict = _make_verdict(advisor_recommended=True)
        config = NinesAdvisorConfig(
            enabled=True,
            triggers=["review"],
        )
        run_nines_advisor(verdict, config, artifact_path="src/main.py")
        called_cmd = mock_cmd.call_args[0][0]
        assert "src/main.py" in called_cmd

    @patch("devolaflow.nines.advisor._run_nines_command")
    def test_advisor_unknown_trigger_skipped(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = {"score": 90}
        verdict = _make_verdict(advisor_recommended=True)
        config = NinesAdvisorConfig(
            enabled=True,
            commands={"self-eval": "nines self-eval --format json"},
            triggers=["nonexistent"],
        )
        result = run_nines_advisor(verdict, config, artifact_path="artifact/")
        assert result.advisor_verdict == ""
        mock_cmd.assert_not_called()


# ===========================================================================
# gate/scorer.py — evaluate_gate_with_nines
# ===========================================================================


class TestEvaluateGateWithNines:
    def test_without_nines_config_delegates_to_standard(self) -> None:
        verdict = evaluate_gate_with_nines(
            _pass_input(), STANDARD, gate_type="standard", nines_config=None
        )
        assert verdict.decision == "PASS"

    @patch("devolaflow.nines.advisor.run_nines_advisor")
    @patch("devolaflow.nines.scorer.nines_dimension_scores")
    @patch("devolaflow.nines.detector.detect_nines")
    def test_with_nines_config_enriches_verdict(
        self,
        mock_detect: MagicMock,
        mock_scores: MagicMock,
        _mock_advisor: MagicMock,
    ) -> None:
        mock_detect.return_value = NinesStatus(available=True, version="1.0.0")
        mock_scores.return_value = {
            "test_quality": 90.0,
            "code_review": 90.0,
            "architecture": 90.0,
            "benchmark": 90.0,
        }

        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(status="pass", details={"coverage_pct": 95}),
            lint_status=CheckResult(status="pass", details={"architecture_score": 90}),
            review_findings=[],
        )
        history = [_round(1, 80.0)]
        nines_cfg = NinesScorerConfig(test_suite="tests/")

        verdict = evaluate_gate_with_nines(
            gi,
            STANDARD,
            round_num=2,
            history=history,
            gate_type="convergence",
            nines_config=nines_cfg,
            artifact_path="artifact/",
        )
        assert verdict.decision == "PASS"
        assert "nines_dimension_scores" in verdict.details

    @patch.dict(
        "sys.modules",
        {"devolaflow.nines.detector": None, "devolaflow.nines.scorer": None},
    )
    def test_nines_import_error_fallback(self) -> None:
        nines_cfg = NinesScorerConfig(test_suite="tests/")
        verdict = evaluate_gate_with_nines(
            _pass_input(),
            STANDARD,
            gate_type="standard",
            nines_config=nines_cfg,
        )
        assert verdict.decision == "PASS"

    @patch("devolaflow.nines.detector.detect_nines")
    def test_nines_not_available_fallback(self, mock_detect: MagicMock) -> None:
        mock_detect.return_value = NinesStatus(available=False)
        nines_cfg = NinesScorerConfig(test_suite="tests/")
        verdict = evaluate_gate_with_nines(
            _pass_input(),
            STANDARD,
            gate_type="standard",
            nines_config=nines_cfg,
        )
        assert verdict.decision == "PASS"
        assert "nines_dimension_scores" not in verdict.details

    @patch("devolaflow.nines.advisor.run_nines_advisor")
    @patch("devolaflow.nines.scorer.nines_dimension_scores")
    @patch("devolaflow.nines.detector.detect_nines")
    def test_advisor_invoked_on_borderline(
        self,
        mock_detect: MagicMock,
        mock_scores: MagicMock,
        mock_advisor: MagicMock,
    ) -> None:
        mock_detect.return_value = NinesStatus(available=True, version="1.0.0")
        mock_scores.return_value = {
            "test_quality": 84.0,
            "code_review": 84.0,
            "architecture": 84.0,
            "benchmark": 84.0,
        }

        def advisor_side_effect(
            verdict: GateVerdict, config: NinesAdvisorConfig, path: str
        ) -> GateVerdict:
            verdict.advisor_verdict = "APPROVE"
            verdict.advisor_context = "NineS approves"
            return verdict

        mock_advisor.side_effect = advisor_side_effect

        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(status="pass", details={"coverage_pct": 80}),
            lint_status=CheckResult(status="pass", details={"architecture_score": 80}),
            review_findings=[],
        )
        history = [_round(1, 75.0)]
        nines_cfg = NinesScorerConfig(test_suite="tests/")
        advisor_cfg = NinesAdvisorConfig(enabled=True, triggers=["self-eval"])

        verdict = evaluate_gate_with_nines(
            gi,
            STANDARD,
            round_num=2,
            history=history,
            gate_type="convergence",
            nines_config=nines_cfg,
            advisor_config=advisor_cfg,
            artifact_path="artifact/",
        )
        assert "nines_dimension_scores" in verdict.details

    def test_no_advisor_config_skips_advisor(self) -> None:
        verdict = evaluate_gate_with_nines(
            _pass_input(),
            STANDARD,
            gate_type="standard",
            nines_config=None,
            advisor_config=None,
        )
        assert verdict.advisor_verdict == ""


# ===========================================================================
# researcher.py
# ===========================================================================


class TestNinesResearchConfig:
    def test_default_values(self) -> None:
        cfg = NinesResearchConfig()
        assert cfg.search_queries == []
        assert cfg.analysis_targets == []
        assert cfg.eval_suite is None
        assert cfg.iteration_max_rounds == 5
        assert cfg.convergence_threshold == 0.02
        assert cfg.timeout == 120

    def test_custom_values(self) -> None:
        cfg = NinesResearchConfig(
            search_queries=["agent framework"],
            analysis_targets=["src/"],
            eval_suite="benchmarks/",
            iteration_max_rounds=10,
            convergence_threshold=0.01,
            timeout=300,
        )
        assert cfg.search_queries == ["agent framework"]
        assert cfg.analysis_targets == ["src/"]
        assert cfg.eval_suite == "benchmarks/"
        assert cfg.iteration_max_rounds == 10
        assert cfg.convergence_threshold == 0.01
        assert cfg.timeout == 300


class TestCollectResearch:
    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        payload = {"results": [{"title": "paper1"}], "count": 1}
        mock_run.return_value = _mock_proc(stdout=json.dumps(payload))
        result = collect_research("agent framework", limit=10)
        assert result == payload
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["nines", "collect", "github"]
        assert "agent framework" in cmd
        assert "--limit" in cmd

    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1, stderr="error")
        result = collect_research("query")
        assert result == {}

    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_custom_source(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout=json.dumps({"results": []}))
        collect_research("deep learning", source="arxiv")
        cmd = mock_run.call_args[0][0]
        assert cmd[2] == "arxiv"

    @patch(
        "devolaflow.nines.researcher.subprocess.run",
        side_effect=subprocess.TimeoutExpired("nines", 120),
    )
    def test_timeout(self, _run: MagicMock) -> None:
        assert collect_research("query") == {}

    @patch(
        "devolaflow.nines.researcher.subprocess.run",
        side_effect=OSError("not found"),
    )
    def test_oserror(self, _run: MagicMock) -> None:
        assert collect_research("query") == {}


class TestAnalyzeTarget:
    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        payload = {"complexity": 42, "issues": []}
        mock_run.return_value = _mock_proc(stdout=json.dumps(payload))
        result = analyze_target("src/module.py")
        assert result == payload
        cmd = mock_run.call_args[0][0]
        assert "src/module.py" in cmd
        assert "--decompose" in cmd
        assert "--index" in cmd

    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_without_decompose(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout=json.dumps({"ok": True}))
        analyze_target("src/", decompose=False)
        cmd = mock_run.call_args[0][0]
        assert "--decompose" not in cmd
        assert "--index" not in cmd

    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1, stderr="fail")
        assert analyze_target("src/") == {}


class TestRunSelfEvaluation:
    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        payload = {"score": 85.0, "dimensions": {"clarity": 90}}
        mock_run.return_value = _mock_proc(stdout=json.dumps(payload))
        result = run_self_evaluation()
        assert result == payload
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["nines", "self-eval"]
        assert "--dimensions" in cmd

    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_custom_dimensions(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout=json.dumps({"score": 70}))
        run_self_evaluation(dimensions="clarity,coverage")
        cmd = mock_run.call_args[0][0]
        idx = cmd.index("--dimensions")
        assert cmd[idx + 1] == "clarity,coverage"


class TestRunSkillIteration:
    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        payload = {"rounds": 3, "converged": True, "final_score": 92.0}
        mock_run.return_value = _mock_proc(stdout=json.dumps(payload))
        result = run_skill_iteration()
        assert result == payload
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["nines", "iterate"]

    @patch("devolaflow.nines.researcher.subprocess.run")
    def test_custom_params(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout=json.dumps({"ok": True}))
        run_skill_iteration(max_rounds=10, convergence_threshold=0.05)
        cmd = mock_run.call_args[0][0]
        assert "--max-rounds" in cmd
        idx_mr = cmd.index("--max-rounds")
        assert cmd[idx_mr + 1] == "10"
        idx_ct = cmd.index("--convergence-threshold")
        assert cmd[idx_ct + 1] == "0.05"


class TestGetResearchAdvice:
    @patch("devolaflow.nines.advisor.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        payload = {
            "score": 85,
            "reasoning": "Good quality",
            "next_steps": ["improve tests", "add docs"],
        }
        mock_run.return_value = _mock_proc(stdout=json.dumps(payload))
        config = NinesAdvisorConfig(enabled=True, triggers=["self-eval"])
        result = get_research_advice(config, target_path="src/")
        assert result["status"] == "ok"
        assert len(result["recommendations"]) > 0
        assert "self-eval" in result["raw_outputs"]

    @patch("devolaflow.nines.advisor.subprocess.run")
    def test_failure_graceful(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1, stderr="error")
        config = NinesAdvisorConfig(enabled=True, triggers=["self-eval"])
        result = get_research_advice(config, target_path="src/")
        assert result["status"] == "no_result"
        assert result["recommendations"] == []

    def test_disabled_config(self) -> None:
        config = NinesAdvisorConfig(
            enabled=False,
            triggers=["nonexistent"],
            commands={},
        )
        result = get_research_advice(config, target_path="src/")
        assert result["status"] == "no_result"
        assert result["recommendations"] == []


# ===========================================================================
# Deprecation warnings
# ===========================================================================


class TestDeprecationWarnings:
    def test_evaluate_gate_with_nines_warns(self) -> None:
        with pytest.warns(DeprecationWarning, match="evaluate_gate_with_nines is deprecated"):
            evaluate_gate_with_nines(
                _pass_input(),
                STANDARD,
                gate_type="standard",
                nines_config=None,
            )

    def test_run_nines_advisor_warns(self) -> None:
        verdict = _make_verdict(advisor_recommended=False)
        config = NinesAdvisorConfig(enabled=False)
        with pytest.warns(DeprecationWarning, match="run_nines_advisor is deprecated"):
            run_nines_advisor(verdict, config, artifact_path="artifact/")
