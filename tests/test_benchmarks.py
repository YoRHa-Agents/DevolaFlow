"""Tests for the EvoBench context density benchmark suite.

Verifies: scenario loading, evaluator scoring, baseline comparison,
runner orchestration, and quality threshold enforcement.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from benchmarks.devolaflow_context.evaluator import (
    BenchmarkScore,
    compare_to_baseline,
    evaluate_scenario,
)
from benchmarks.devolaflow_context.runner import (
    BASELINES_DIR,
    SCENARIOS_DIR,
    _newest_baseline_path,
    discover_scenarios,
    load_baseline,
    load_scenario,
    run_all,
    run_scenario,
)

V6_BASELINE_PATH = BASELINES_DIR / "v7.8.0_baseline.json"

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

    # ------------------------------------------------------------------
    # v6.0.5 full-coverage baseline (C1 closure — was 3/29, now 29/29).
    # ------------------------------------------------------------------

    def test_v6_baseline_exists(self) -> None:
        """v7.4.0_baseline.json must be present in baselines/ (regenerated each release cut)."""
        assert V6_BASELINE_PATH.exists(), (
            f"Missing {V6_BASELINE_PATH.relative_to(REPO_ROOT)}. "
            f"Regenerate via: python -m benchmarks.devolaflow_context.generate_baseline"
        )

    def test_v6_baseline_covers_all_scenarios(self) -> None:
        """Full coverage: every scenario YAML has a baseline entry."""
        with open(V6_BASELINE_PATH) as f:
            data = json.load(f)
        baseline_keys = set(data.keys())
        scenario_stems = {p.stem for p in SCENARIOS_DIR.glob("*.yaml")}
        missing_from_baseline = scenario_stems - baseline_keys
        extra_in_baseline = baseline_keys - scenario_stems
        assert not missing_from_baseline, (
            f"{V6_BASELINE_PATH.name} is missing entries for scenarios "
            f"{sorted(missing_from_baseline)}. "
            f"Regenerate via: python -m benchmarks.devolaflow_context.generate_baseline"
        )
        assert not extra_in_baseline, (
            f"{V6_BASELINE_PATH.name} has entries for scenarios that no longer exist: "
            f"{sorted(extra_in_baseline)}. Regenerate the baseline."
        )
        assert baseline_keys == scenario_stems

    def test_v6_baseline_scores_positive(self) -> None:
        """Every scenario in the latest baseline has a strictly positive composite."""
        with open(V6_BASELINE_PATH) as f:
            data = json.load(f)
        for name, entry in data.items():
            assert entry["composite"] > 0, (
                f"{name} has non-positive composite ({entry.get('composite')})"
            )
            for required_field in (
                "information_density",
                "section_relevance",
                "budget_utilization",
                "noise_ratio",
                "total_tokens",
                "budget",
                "selected_count",
            ):
                assert required_field in entry, f"{name} baseline entry missing '{required_field}'"

    def test_runner_prefers_latest_baseline(self) -> None:
        """load_baseline() picks the latest baseline file over older ones, falls back as needed.

        v9.7.0 PV-05 (cycle v10.0.0 FINAL minor) ships a per-PV regen
        of all 53 EvoBench scenarios as ``v9.7.0_baseline.json`` — this
        is NOT a W-16 wholesale regen (those happen at MINOR cycle
        START, e.g. v9.3.0_baseline.json was the v10.0.0 cycle start).
        The v9.3.0 wholesale baseline + the v9.x mid-cycle baselines
        (v9.6.0 / v9.7.0) stay on disk for cumulative drift detection
        per W-16 / v8.4.0 retro §"R-7 wholesale-vs-piecemeal baseline
        lesson".
        """
        newest = _newest_baseline_path()
        assert newest is not None
        assert newest.name == "v9.7.0_baseline.json", (
            f"Expected load_baseline() to prefer v9.7.0_baseline.json; got {newest.name}"
        )

        # load_baseline() returns data for a scenario covered only by v6+ baselines
        # (not present in the legacy v2.1.0_baseline.json fallback).
        entry = load_baseline("visual_regression_webapp")
        assert entry is not None, (
            "load_baseline() did not return an entry for a scenario present in "
            "the v7.1.0 baseline — runner is still falling back to v2.1.0."
        )
        assert entry["composite"] > 0

    def test_v6_baseline_matches_current_results_within_tolerance(self) -> None:
        """Sanity: the recorded baseline reflects the current evaluator output.

        A recorded composite that drifts >5pp from a fresh re-run indicates the
        baseline is stale and must be regenerated.
        """
        with open(V6_BASELINE_PATH) as f:
            data = json.load(f)
        for path in discover_scenarios("all"):
            scenario_data = load_scenario(path)
            name = scenario_data.get("name", path.stem)
            if name not in data:
                continue
            current = run_scenario(scenario_data)
            recorded = data[name]["composite"]
            drift = abs(current.composite - recorded)
            assert drift <= 5.0, (
                f"{name}: recorded baseline composite {recorded} drifted "
                f"{drift:.2f} points from current run ({current.composite}). "
                f"Regenerate with: python -m benchmarks.devolaflow_context.generate_baseline"
            )


class TestBaselineRegressionDetection:
    """Verify compare_to_baseline flags a simulated 10% composite drop."""

    def test_ten_percent_drop_is_flagged_as_regression(self) -> None:
        """A -10% composite vs baseline must be classified as REGRESSION."""
        with open(V6_BASELINE_PATH) as f:
            data = json.load(f)
        baseline_entry = data["hotfix_jwt"]
        baseline_composite = baseline_entry["composite"]

        # Construct a synthetic score 10% below baseline composite.
        # composite = 40*relevance + 30*density + 20*(1-noise) + 10*utilization
        # To land ~10% below, tank section_relevance (the dominant term).
        target_composite = baseline_composite * 0.9
        synthetic = BenchmarkScore(
            scenario_name="hotfix_jwt",
            profile_name=baseline_entry["profile_name"],
            information_density=baseline_entry["information_density"],
            section_relevance=max(0.0, baseline_entry["section_relevance"] - 0.30),
            budget_utilization=baseline_entry["budget_utilization"],
            noise_ratio=baseline_entry["noise_ratio"] + 0.10,
            total_tokens=baseline_entry["total_tokens"],
            budget=baseline_entry["budget"],
            selected_count=baseline_entry["selected_count"],
            expected_count=7,
            matched_count=5,
        )
        # Sanity: synthetic score must actually be below target.
        assert synthetic.composite < target_composite + 0.1, (
            f"Synthetic score {synthetic.composite} did not drop to ~10% below "
            f"baseline {baseline_composite}"
        )

        result = compare_to_baseline(synthetic, baseline_entry)
        assert result["verdict"] == "REGRESSION", (
            f"Expected REGRESSION for a 10% composite drop; "
            f"got {result['verdict']} with delta {result['delta']}"
        )
        assert result["regressed"] is True
        assert result["pct_change"] < -5.0

    def test_one_percent_drop_not_flagged(self) -> None:
        """A -1% composite drop must NOT be classified as REGRESSION."""
        synthetic = BenchmarkScore(
            scenario_name="near_baseline",
            profile_name="hotfix",
            information_density=0.5,
            section_relevance=0.5,
            budget_utilization=0.5,
            noise_ratio=0.0,
            total_tokens=100,
            budget=200,
            selected_count=3,
            expected_count=3,
            matched_count=3,
        )
        # compare_to_baseline uses 5% threshold; a 1% drop is well inside.
        adjusted_baseline = {"composite": synthetic.composite * 1.01}
        result = compare_to_baseline(synthetic, adjusted_baseline)
        assert result["verdict"] == "PASS"
        assert result["regressed"] is False


class TestLayoutInvariantBaseline:
    """v7.0.0 cache-layout-invariant golden baseline (per ADR-001 §6 #5).

    Renders the canonical dispatch via
    ``yaml.safe_dump(..., sort_keys=False, default_flow_style=False)`` and
    byte-compares against ``layout_invariant_v7.0.0.yaml``. Any drift
    (renderer upgrade, layout reorder, payload edit) fails CI here.

    v7.2.6 P-06 extends this with the v7.3.0 dual baseline:
    ``layout_invariant_v7.3.0.yaml`` adds the additive ``repos`` field at
    canonical position 13 (per ADR-001 §2). The v7.0.0 byte-comparison MUST
    STILL PASS unchanged — that is the proof that the schema bump 1 → 2 is
    purely additive and the cached prefix is preserved.
    """

    BASELINE_PATH = BASELINES_DIR / "layout_invariant_v7.0.0.yaml"
    BASELINE_PATH_V7_3_0 = BASELINES_DIR / "layout_invariant_v7.3.0.yaml"

    @staticmethod
    def _canonical_baseline_payload() -> dict:
        """Canonical dispatch matching the v7.0.0 golden baseline file. Order
        MUST follow ``lean-dispatch.yaml#layout_invariant.canonical_order``."""
        return {
            "hdr": {"id": "d-baseline-v7.0.0", "parent": "stage-baseline", "layer": "wave"},
            "task": {"id": "T-BASELINE-001", "type": "code", "title": "cache layout baseline"},
            "goal": "golden rendered dispatch for layout invariant",
            "assumptions": ["yaml renderer preserves insertion order", "utf-8 byte comparison"],
            "pred": [
                {
                    "ref": ".local/research/adr/v7-ADR-001-cache-layout-invariant.md",
                    "key_facts": [
                        "canonical 12-key order",
                        "additive rule for new keys",
                        "LCP thresholds 0.80 and 0.70",
                    ],
                }
            ],
            "files": ["src/devolaflow/compressor.py", "schemas/lean-dispatch.yaml"],
            "rules": {"strategy": "standard", "lang": "python", "focus": ["cache-discipline"]},
            "shared": "Python 3.11+, PyYAML, pytest",
            "accept": [
                "render byte-stable across CI runs",
                "top-level keys remain in canonical order",
                "reinforce slot present at position 10",
            ],
            "reinforce": {
                "round": 2,
                "prior": 78.0,
                "target": 85,
                "rules": [
                    {
                        "id": "F-LAY-001",
                        "sev": "blocker",
                        "mandate": "MUST validate via assert_dispatch_layout before send",
                        "file": "src/devolaflow/compressor.py",
                    }
                ],
            },
            "verify_cfg": {
                "visual": False,
                "accept": True,
                "interact": False,
                "a11y": False,
                "threshold": 0.85,
            },
            "gate": {"coverage": 85, "quality": 85, "blockers": 0, "retries": 2},
        }

    @classmethod
    def _canonical_baseline_payload_v7_3_0(cls) -> dict:
        """v7.3.0-shape baseline payload — v7.0.0 baseline + appended ``repos``
        block at canonical position 13. The first 12 keys are byte-identical to
        the v7.0.0 baseline so ``compute_dispatch_lcp_pct(v7.0.0, v7.3.0)``
        returns 1.0 (the v7.0.0 render is a perfect prefix of v7.3.0). 3 repos
        — one ``primary: true`` (auth-service) plus 2 dependents (web-frontend,
        api-gateway) — model the multi-repo coordination case targeted by P-06.
        """
        payload = cls._canonical_baseline_payload()
        payload["repos"] = [
            {
                "name": "auth-service",
                "root_path": "repos/auth-service",
                "primary": True,
                "branch": "main",
            },
            {
                "name": "web-frontend",
                "root_path": "repos/web-frontend",
                "primary": False,
                "branch": "develop",
            },
            {
                "name": "api-gateway",
                "root_path": "repos/api-gateway",
                "primary": False,
                "branch": "main",
            },
        ]
        return payload

    def test_layout_invariant_baseline(self) -> None:
        assert self.BASELINE_PATH.exists(), f"Missing {self.BASELINE_PATH} (see ADR-001 §6)."
        recorded = self.BASELINE_PATH.read_text()
        rendered = yaml.safe_dump(
            self._canonical_baseline_payload(), sort_keys=False, default_flow_style=False
        )
        assert rendered == recorded, (
            "layout_invariant_v7.0.0.yaml has drifted from the canonical renderer output. "
            "See .local/research/adr/v7-ADR-001-cache-layout-invariant.md §6."
        )

    def test_layout_invariant_baseline_v7_3_0(self) -> None:
        """v7.3.0 dual-baseline byte-comparison (P-06). The new golden contains
        the same first 12 keys as v7.0.0 plus the additive ``repos`` block."""
        assert self.BASELINE_PATH_V7_3_0.exists(), (
            f"Missing {self.BASELINE_PATH_V7_3_0} — v7.2.6 P-06 introduced the "
            "v7.3.0 schema-version golden alongside the v7.0.0 baseline."
        )
        recorded = self.BASELINE_PATH_V7_3_0.read_text()
        rendered = yaml.safe_dump(
            self._canonical_baseline_payload_v7_3_0(),
            sort_keys=False,
            default_flow_style=False,
        )
        assert rendered == recorded, (
            "layout_invariant_v7.3.0.yaml has drifted from the canonical renderer output. "
            "See schemas/lean-dispatch.yaml#layout_invariant (version: 2)."
        )

    def test_layout_invariant_v7_0_0_prefix_lcp_v7_3_0(self) -> None:
        """LCP between v7.0.0 and v7.3.0 baselines on the first 12 keys must be
        >= 0.95 (margin over ``schemas/lean-dispatch.yaml#layout_invariant.
        enforcement.lcp_threshold_round_1_to_2`` of 0.80). This is the P6 cache
        prefix preservation proof — appending ``repos`` AT THE END must NOT
        invalidate the cached prefix that downstream LLM caches see for round 1.
        """
        from devolaflow.compressor import compute_dispatch_lcp_pct

        v7_0_0 = self._canonical_baseline_payload()
        v7_3_0 = self._canonical_baseline_payload_v7_3_0()
        lcp = compute_dispatch_lcp_pct(v7_0_0, v7_3_0)
        assert lcp >= 0.95, (
            f"LCP(v7.0.0, v7.3.0) = {lcp:.4f} violates the 0.95 margin "
            f"(lean-dispatch.yaml#layout_invariant.enforcement."
            f"lcp_threshold_round_1_to_2 = 0.80). The v7.3.0 schema bump must "
            "preserve the v7.0.0 cached prefix; if this assertion fails, the "
            "additive rule (ADR-001 §2) was violated — REORDERING ANY EXISTING "
            "KEY IS A RELEASE BLOCKER per devola-flow-rules.mdc Rule 6."
        )
