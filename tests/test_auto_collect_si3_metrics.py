"""Tests for ``scripts/auto_collect_si3_metrics.py`` (v10.7.0 D-O-2).

Pins the contract from `.local/research/v11.0.0_patches/D-O-2.md`:

* Per-dim objective scoring math is correct for every code-path branch.
* Composite weighting reflects the W-3 SI-3 6-dim formula.
* S-5 "no silent failures" — unavailable sub-components are EXPLICITLY
  marked, never silently zeroed.
* The auto-fill rate is the fraction of (available / total) sub-components.
* `--mock-data` short-circuits subprocess invocation so the test suite
  doesn't depend on a working ruff / pytest / git environment.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


def _load_collector_module() -> object:
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "auto_collect_si3_metrics.py"
    name = "auto_collect_si3_metrics"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_COLLECTOR = _load_collector_module()


def test_dimension_weights_sum_to_one() -> None:
    """W-3 SI-3 weighted formula must sum to 1.0."""
    total = sum(_COLLECTOR.DIMENSION_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-6


def test_objective_subjective_weights_complementary() -> None:
    """Per cycle plan §6 R-10: 0.6 / 0.4 split."""
    assert (
        pytest.approx(1.0)
        == _COLLECTOR.DEFAULT_OBJECTIVE_WEIGHT + _COLLECTOR.DEFAULT_SUBJECTIVE_WEIGHT
    )
    assert pytest.approx(0.6) == _COLLECTOR.DEFAULT_OBJECTIVE_WEIGHT


def test_compute_objective_score_with_all_clean_subs() -> None:
    """Synthetic clean metrics → composite ≈ 10.0; auto_fill_rate = 1.0."""
    sub = _COLLECTOR.SubcomponentResult
    metrics = {
        "code_quality": [
            sub("ruff_lint", True, "clean"),
            sub("ruff_format", True, "clean"),
            sub("coverage_pct", True, 90),
        ],
        "architecture": [sub("multi_baseline_pass", True, 12)],
        "test_adequacy": [
            sub("coverage_pct", True, 90),
            sub("test_count", True, 4000),
            sub("w17_new_test_fn_count", True, 25),
        ],
        "maintainability": [sub("ruff_format", True, "clean")],
        "compatibility": [sub("multi_baseline_pass", True, 12)],
        "performance_impact": [sub("multi_baseline_pass", True, 12)],
    }
    score = _COLLECTOR.compute_objective_score(metrics, sampled_at="2026-05-04T00:00:00Z")
    assert score.composite_objective == pytest.approx(10.0)
    assert score.auto_fill_rate == pytest.approx(1.0)
    for dim_score in score.per_dim_scores.values():
        assert dim_score == pytest.approx(10.0)


def test_unavailable_subcomponents_are_explicit_per_s5() -> None:
    """S-5: when a probe is unavailable, the score reflects partial data.

    A dim with one unavailable sub MUST NOT silently zero — it should
    score the average of AVAILABLE subs (so missing data is penalty-free
    in proportion). The auto_fill_rate captures the absence explicitly.
    """
    sub = _COLLECTOR.SubcomponentResult
    metrics = {
        "code_quality": [
            sub("ruff_lint", True, "clean"),
            sub("ruff_format", False, error="ruff binary not found"),
            sub("coverage_pct", True, 90),
        ],
        "architecture": [sub("multi_baseline_pass", False, error="timeout")],
        "test_adequacy": [
            sub("coverage_pct", True, 90),
            sub("test_count", True, 4000),
            sub("w17_new_test_fn_count", True, 25),
        ],
        "maintainability": [sub("ruff_format", False, error="ruff binary not found")],
        "compatibility": [sub("multi_baseline_pass", False, error="timeout")],
        "performance_impact": [sub("multi_baseline_pass", False, error="timeout")],
    }
    score = _COLLECTOR.compute_objective_score(metrics, sampled_at="2026-05-04T00:00:00Z")
    # Code quality has 2/3 available subs; both clean → score = 10.0.
    assert score.per_dim_scores["code_quality"] == pytest.approx(10.0)
    # Architecture / Maintainability / Compatibility / Performance: 0/1
    # available → score = 0.0 (no available data to score).
    assert score.per_dim_scores["architecture"] == pytest.approx(0.0)
    assert score.per_dim_scores["maintainability"] == pytest.approx(0.0)
    assert score.per_dim_scores["compatibility"] == pytest.approx(0.0)
    assert score.per_dim_scores["performance_impact"] == pytest.approx(0.0)
    # Auto-fill rate: 5 available out of 10 total
    # (3 + 1 + 3 + 1 + 1 + 1 = 10 subcomponents per the metrics shape above) = 0.5.
    assert score.auto_fill_rate == pytest.approx(0.5)


def test_render_yaml_round_trips_through_yaml_safe_load() -> None:
    """The emitted YAML must parse cleanly + carry the canonical keys."""
    sub = _COLLECTOR.SubcomponentResult
    metrics = {
        "code_quality": [sub("ruff_lint", True, "clean")],
        "architecture": [sub("multi_baseline_pass", True, 12)],
        "test_adequacy": [sub("test_count", True, 4000)],
        "maintainability": [sub("ruff_format", True, "clean")],
        "compatibility": [sub("multi_baseline_pass", True, 12)],
        "performance_impact": [sub("multi_baseline_pass", True, 12)],
    }
    score = _COLLECTOR.compute_objective_score(metrics, sampled_at="2026-05-04T00:00:00Z")
    body = _COLLECTOR.render_yaml(score)
    payload = yaml.safe_load(body)
    assert payload["schema_version"] == 1
    assert payload["sampled_at"] == "2026-05-04T00:00:00Z"
    assert payload["objective_weight"] == pytest.approx(0.6)
    assert payload["subjective_weight"] == pytest.approx(0.4)
    assert "per_dim" in payload
    assert set(payload["per_dim"].keys()) == set(_COLLECTOR.DIMENSION_WEIGHTS.keys())
    # Every dim payload must carry weight + objective_score + subcomponents.
    for _dim, dim_payload in payload["per_dim"].items():
        assert "weight" in dim_payload
        assert "objective_score" in dim_payload
        assert "subcomponents" in dim_payload


def test_run_with_mock_data_emits_json_payload(tmp_path: Path) -> None:
    """The ``--mock-data`` short-circuit produces a parseable artifact.

    This test is the W-7 / SI-8 friendly path: the test suite runs in
    < 1s without invoking real ruff / pytest / git probes, while still
    exercising the full driver end-to-end.
    """
    output = tmp_path / "v10.7.3_si3_auto.md"
    rc = _COLLECTOR.run(
        Path.cwd(),
        output=output,
        mock_data=True,
        json_out=False,
    )
    assert rc == 0
    text = output.read_text(encoding="utf-8")
    assert "SI-3 Objective Auto-Collection Summary" in text
    assert "Auto-fill rate" in text
    assert "code_quality" in text


def test_run_with_mock_data_json_output_parses(tmp_path: Path) -> None:
    """JSON output path emits a parseable composite + per-dim block."""
    output = tmp_path / "v10.7.3_si3_auto.json"
    rc = _COLLECTOR.run(
        Path.cwd(),
        output=output,
        mock_data=True,
        json_out=True,
    )
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "composite_objective" in payload
    assert "auto_fill_rate" in payload
    assert set(payload["per_dim_scores"].keys()) == set(_COLLECTOR.DIMENSION_WEIGHTS.keys())
    # With mock_data the auto_fill_rate is 1.0 (every probe hard-wired available).
    assert payload["auto_fill_rate"] == pytest.approx(1.0)
