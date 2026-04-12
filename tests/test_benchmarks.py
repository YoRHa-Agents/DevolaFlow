"""Tests for the EvoBench context density benchmark suite.

Verifies: scenario loading, evaluator scoring, baseline comparison,
runner orchestration, and quality threshold enforcement.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.devolaflow_context.evaluator import (
    BenchmarkScore,
    compare_to_baseline,
    evaluate_scenario,
)
from benchmarks.devolaflow_context.runner import (
    BASELINES_DIR,
    discover_scenarios,
    load_scenario,
    run_all,
    run_scenario,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestEvaluator:
    def test_perfect_scenario(self) -> None:
        selector_result = {
            "profile_name": "hotfix",
            "selected_sections": [
                {"name": "dispatch_report", "tokens": 100},
                {"name": "context_isolation", "tokens": 100},
            ],
            "total_tokens": 200,
            "budget": 400,
        }
        score = evaluate_scenario(
            "test_perfect",
            selector_result,
            expected_sections=["dispatch_report", "context_isolation"],
        )
        assert score.section_relevance == 1.0
        assert score.noise_ratio == 0.0
        assert score.composite > 0

    def test_partial_relevance(self) -> None:
        selector_result = {
            "profile_name": "feature",
            "selected_sections": [
                {"name": "dispatch_report", "tokens": 100},
                {"name": "stage_primitives", "tokens": 100},
            ],
            "total_tokens": 200,
            "budget": 500,
        }
        score = evaluate_scenario(
            "test_partial",
            selector_result,
            expected_sections=["dispatch_report", "context_isolation", "gate_mechanism"],
        )
        assert 0 < score.section_relevance < 1.0
        assert score.matched_count == 1
        assert score.expected_count == 3

    def test_noise_detection(self) -> None:
        selector_result = {
            "profile_name": "hotfix",
            "selected_sections": [
                {"name": "dispatch_report", "tokens": 100},
                {"name": "stage_primitives", "tokens": 100},
            ],
            "total_tokens": 200,
            "budget": 400,
        }
        score = evaluate_scenario(
            "test_noise",
            selector_result,
            expected_sections=["dispatch_report"],
            unwanted_sections=["stage_primitives"],
        )
        assert score.noise_ratio == 0.5

    def test_empty_selection(self) -> None:
        selector_result = {
            "profile_name": "hotfix",
            "selected_sections": [],
            "total_tokens": 0,
            "budget": 400,
        }
        score = evaluate_scenario(
            "test_empty",
            selector_result,
            expected_sections=["dispatch_report"],
        )
        assert score.section_relevance == 0.0
        assert score.noise_ratio == 0.0
        assert score.budget_utilization == 0.0

    def test_empty_expected(self) -> None:
        selector_result = {
            "profile_name": "hotfix",
            "selected_sections": [{"name": "a", "tokens": 10}],
            "total_tokens": 10,
            "budget": 100,
        }
        score = evaluate_scenario("test_no_expected", selector_result, expected_sections=[])
        assert score.section_relevance == 0.0

    def test_to_dict(self) -> None:
        score = BenchmarkScore(
            scenario_name="test",
            profile_name="hotfix",
            information_density=0.5,
            section_relevance=0.8,
            budget_utilization=0.6,
            noise_ratio=0.1,
            total_tokens=100,
            budget=200,
            selected_count=5,
            expected_count=4,
            matched_count=3,
        )
        d = score.to_dict()
        assert "composite" in d
        assert d["scenario_name"] == "test"
        assert isinstance(d["composite"], float)

    def test_format_compliance_field(self) -> None:
        """New format_compliance dimension present in results."""
        report = run_all("all")
        for r in report["results"]:
            assert "format_compliance" in r
            assert 0 <= r["format_compliance"] <= 1

    def test_format_compliance_with_assembled_text(self) -> None:
        """format_compliance is computed when assembled_text is present."""
        selector_result = {
            "profile_name": "hotfix",
            "selected_sections": [
                {"name": "dispatch_report", "tokens": 100},
            ],
            "total_tokens": 100,
            "budget": 400,
            "assembled_text": "JWT auth middleware validates tokens and returns 401 on failure",
        }
        score = evaluate_scenario(
            "test_compliance_clean",
            selector_result,
            expected_sections=["dispatch_report"],
        )
        assert score.format_compliance > 0.0

    def test_format_compliance_dirty_text(self) -> None:
        """format_compliance penalizes drop-list violations."""
        selector_result = {
            "profile_name": "hotfix",
            "selected_sections": [
                {"name": "dispatch_report", "tokens": 100},
            ],
            "total_tokens": 100,
            "budget": 400,
            "assembled_text": (
                "I think basically it seems the JWT middleware might perhaps "
                "work. Let me explain: Great question, sorry for the confusion."
            ),
        }
        score = evaluate_scenario(
            "test_compliance_dirty",
            selector_result,
            expected_sections=["dispatch_report"],
        )
        assert score.format_compliance < 1.0

    def test_format_compliance_no_assembled_text(self) -> None:
        """format_compliance is 0.0 when no assembled_text is provided."""
        selector_result = {
            "profile_name": "hotfix",
            "selected_sections": [
                {"name": "dispatch_report", "tokens": 100},
            ],
            "total_tokens": 100,
            "budget": 400,
        }
        score = evaluate_scenario(
            "test_compliance_none",
            selector_result,
            expected_sections=["dispatch_report"],
        )
        assert score.format_compliance == 0.0


class TestBaselineComparison:
    def test_pass_when_no_regression(self) -> None:
        score = BenchmarkScore(
            scenario_name="test",
            profile_name="hotfix",
            information_density=0.5,
            section_relevance=0.8,
            budget_utilization=0.6,
            noise_ratio=0.1,
            total_tokens=100,
            budget=200,
            selected_count=5,
            expected_count=4,
            matched_count=3,
        )
        baseline = {"composite": score.composite - 1}
        result = compare_to_baseline(score, baseline)
        assert result["verdict"] == "PASS"
        assert not result["regressed"]

    def test_regression_detected(self) -> None:
        score = BenchmarkScore(
            scenario_name="test",
            profile_name="hotfix",
            information_density=0.2,
            section_relevance=0.3,
            budget_utilization=0.2,
            noise_ratio=0.5,
            total_tokens=50,
            budget=200,
            selected_count=2,
            expected_count=4,
            matched_count=1,
        )
        baseline = {"composite": 80.0}
        result = compare_to_baseline(score, baseline)
        assert result["verdict"] == "REGRESSION"
        assert result["regressed"]

    def test_zero_baseline(self) -> None:
        score = BenchmarkScore(
            scenario_name="t",
            profile_name="h",
            information_density=0.5,
            section_relevance=0.8,
            budget_utilization=0.6,
            noise_ratio=0.0,
            total_tokens=100,
            budget=200,
            selected_count=3,
            expected_count=3,
            matched_count=3,
        )
        result = compare_to_baseline(score, {"composite": 0.0})
        assert result["verdict"] == "PASS"


class TestScenarioDiscovery:
    def test_discover_all(self) -> None:
        scenarios = discover_scenarios("all")
        assert len(scenarios) >= 3

    def test_discover_single(self) -> None:
        scenarios = discover_scenarios("hotfix_jwt")
        assert len(scenarios) == 1
        assert scenarios[0].stem == "hotfix_jwt"

    def test_discover_nonexistent(self) -> None:
        scenarios = discover_scenarios("nonexistent_xyzzy")
        assert len(scenarios) == 0

    def test_scenario_yaml_valid(self) -> None:
        for path in discover_scenarios("all"):
            data = load_scenario(path)
            assert "name" in data
            assert "task_type" in data
            assert "expected_sections" in data


class TestRunner:
    def test_run_all_passes(self) -> None:
        report = run_all("all")
        assert report["scenario_count"] >= 3
        assert report["overall_verdict"] == "PASS"
        for r in report["results"]:
            assert r["composite"] > 0
            assert r["section_relevance"] >= 0
            assert r["noise_ratio"] >= 0

    def test_run_single_scenario(self) -> None:
        report = run_all("hotfix_jwt")
        assert report["scenario_count"] == 1
        assert report["results"][0]["profile_name"] == "hotfix"

    def test_run_with_baseline(self) -> None:
        report = run_all("all", compare_baseline=True)
        if "baseline_comparisons" in report:
            for cmp in report["baseline_comparisons"]:
                assert "verdict" in cmp
                assert "delta" in cmp

    def test_run_nonexistent_returns_error(self) -> None:
        report = run_all("nonexistent_xyzzy_999")
        assert "error" in report

    def test_quality_thresholds(self) -> None:
        """Each scenario must meet its own quality_thresholds."""
        for path in discover_scenarios("all"):
            data = load_scenario(path)
            score = run_scenario(data)
            thresholds = data.get("quality_thresholds", {})
            if "min_composite" in thresholds:
                min_c = thresholds["min_composite"]
                assert score.composite >= min_c, (
                    f"{data['name']}: composite {score.composite} < min {min_c}"
                )
            if "max_noise_ratio" in thresholds:
                max_n = thresholds["max_noise_ratio"]
                assert score.noise_ratio <= max_n, (
                    f"{data['name']}: noise {score.noise_ratio} > max {max_n}"
                )
            if "min_relevance" in thresholds:
                min_r = thresholds["min_relevance"]
                assert score.section_relevance >= min_r, (
                    f"{data['name']}: relevance {score.section_relevance} < min {min_r}"
                )


class TestBaselineFile:
    def test_baseline_exists(self) -> None:
        baseline_path = BASELINES_DIR / "v2.1.0_baseline.json"
        assert baseline_path.exists()

    def test_baseline_valid_json(self) -> None:
        baseline_path = BASELINES_DIR / "v2.1.0_baseline.json"
        with open(baseline_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert len(data) >= 3

    def test_baseline_has_expected_scenarios(self) -> None:
        baseline_path = BASELINES_DIR / "v2.1.0_baseline.json"
        with open(baseline_path) as f:
            data = json.load(f)
        assert "hotfix_jwt" in data
        assert "feature_middleware" in data
        assert "full_pipeline_auth" in data

    def test_baseline_scores_positive(self) -> None:
        baseline_path = BASELINES_DIR / "v2.1.0_baseline.json"
        with open(baseline_path) as f:
            data = json.load(f)
        for name, entry in data.items():
            assert entry["composite"] > 0, f"{name} has composite <= 0"
            assert entry["section_relevance"] > 0, f"{name} has relevance <= 0"
