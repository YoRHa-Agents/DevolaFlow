"""Unit tests for ``scripts/nines_to_sichip_eval_adapter.py`` (D-N-1).

Pin the schema mapping between NineS self-eval JSON output and
Si-Chip's ``runs-dir``/``baseline-dir`` layout. Cover the APPROVE path
and the REJECT path (R-1 fallback) both. The tests use small inline
fixtures + ``tmp_path`` to keep the suite fast and hermetic.

W-18 sequencing: this module is referenced by
``test_v10_2_2_new_symbols_have_coverage`` in
``tests/test_no_ghost_features.py``; the lint pin asserts the file
exists before the v10.2.2 CHANGELOG entry references the adapter.

Source: v10.2.0 cycle plan §3 PV-03 (D-N-1 closure unit-test deliverable).
External tools (S-7):

* DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
* NineS: https://github.com/YoRHa-Agents/NineS
* Si-Chip: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

# Direct-import the adapter from scripts/ (it is not part of the
# devolaflow package, but is importable as a script). Tests use a fresh
# module spec so no global mutation leaks across test runs.
_ADAPTER_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "nines_to_sichip_eval_adapter.py"
)


def _load_adapter_module():  # pragma: no cover - import shim
    """Load the adapter script as an importable module."""
    spec = importlib.util.spec_from_file_location("nines_to_sichip_eval_adapter", _ADAPTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


adapter = _load_adapter_module()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _well_formed_nines_payload() -> dict[str, Any]:
    """Return a minimal NineS self-eval payload that mirrors the v10.0.0 shape.

    Only the fields the adapter consumes are populated; every other
    NineS axis is omitted so the fixture stays compact + intent-clear.
    """
    return {
        "scores": [
            {
                "name": "scoring_accuracy",
                "value": 0.9,
                "max_value": 1.0,
                "normalized": 0.9,
                "metadata": {
                    "total_tasks": 3,
                    "accurate_tasks": 2,
                    "tolerance": 0.1,
                    "details": {
                        "devolaflow-task-001": {
                            "nines_score": 1.0,
                            "golden_score": 1.0,
                            "delta": 0.0,
                            "accurate": True,
                            "scorer": "exact",
                        },
                        "devolaflow-task-002": {
                            "nines_score": 0.5,
                            "golden_score": 1.0,
                            "delta": 0.5,
                            "accurate": False,
                            "scorer": "exact",
                        },
                        "devolaflow-task-003": {
                            "nines_score": 1.0,
                            "golden_score": 1.0,
                            "delta": 0.0,
                            "accurate": True,
                            "scorer": "fuzzy",
                        },
                    },
                },
            },
            {
                "name": "lint_cleanliness",
                "value": 100.0,
                "max_value": 100.0,
                "normalized": 1.0,
                "metadata": {"unit": "score", "violation_count": 0},
            },
        ],
        "overall": 0.9073,
        "version": "3.3.0",
        "timestamp": "2026-05-03T12:00:00+00:00",
        "weighted_overall": 0.7281,
    }


@pytest.fixture
def nines_json_path(tmp_path: Path) -> Path:
    """Write a well-formed NineS payload to disk and return the path."""
    payload = _well_formed_nines_payload()
    path = tmp_path / "nines_self_eval.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def baseline_nines_json_path(tmp_path: Path) -> Path:
    """Variant payload with lower scores — useful for sample-mode tests."""
    payload = _well_formed_nines_payload()
    details = payload["scores"][0]["metadata"]["details"]
    for task_id in details:
        details[task_id]["nines_score"] = 0.2
    payload["overall"] = 0.20
    path = tmp_path / "nines_baseline.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test 1: load_nines_json — well-formed input
# ---------------------------------------------------------------------------


def test_load_nines_json_well_formed(nines_json_path: Path) -> None:
    """Well-formed NineS JSON parses into a dict with the expected keys."""
    data = adapter.load_nines_json(nines_json_path)
    assert isinstance(data, dict)
    assert "scores" in data
    assert isinstance(data["scores"], list)
    assert data["scores"][0]["name"] == "scoring_accuracy"


# ---------------------------------------------------------------------------
# Test 2: load_nines_json — malformed input raises loud error
# ---------------------------------------------------------------------------


def test_load_nines_json_malformed_raises(tmp_path: Path) -> None:
    """Corrupted JSON raises with the source path stitched into the message."""
    bad_path = tmp_path / "broken.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as exc_info:
        adapter.load_nines_json(bad_path)
    assert str(bad_path) in str(exc_info.value)


def test_load_nines_json_missing_file_raises(tmp_path: Path) -> None:
    """Missing path raises FileNotFoundError per S-5."""
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError) as exc_info:
        adapter.load_nines_json(missing)
    assert str(missing) in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 3: validate_nines_shape — accepts well-formed v3.3.0 payload
# ---------------------------------------------------------------------------


def test_validate_nines_shape_accepts_v3_3_0() -> None:
    """The reference shape (mirroring v10.0.0_nines.json) validates True."""
    payload = _well_formed_nines_payload()
    valid, reason = adapter.validate_nines_shape(payload)
    assert valid, f"expected True, got False with reason: {reason}"
    assert reason == ""


# ---------------------------------------------------------------------------
# Test 4: validate_nines_shape — rejects empty / scoreless payloads
# ---------------------------------------------------------------------------


def test_validate_nines_shape_rejects_empty_dict() -> None:
    """Empty dict (no ``scores`` array) → REJECT with descriptive reason."""
    valid, reason = adapter.validate_nines_shape({})
    assert valid is False
    assert "scores" in reason


def test_validate_nines_shape_rejects_minimal_skeleton() -> None:
    """Skeleton with empty ``scores`` array → REJECT."""
    valid, reason = adapter.validate_nines_shape({"scores": []})
    assert valid is False
    assert "non-empty" in reason or "scores" in reason


def test_validate_nines_shape_rejects_no_scoring_accuracy() -> None:
    """Payload with scores but no ``scoring_accuracy`` entry → REJECT."""
    payload = {"scores": [{"name": "lint_cleanliness", "value": 100.0, "metadata": {}}]}
    valid, reason = adapter.validate_nines_shape(payload)
    assert valid is False
    assert "scoring_accuracy" in reason


def test_validate_nines_shape_rejects_empty_details() -> None:
    """``scoring_accuracy.metadata.details`` empty dict → REJECT."""
    payload = {
        "scores": [
            {
                "name": "scoring_accuracy",
                "metadata": {"details": {}},
            }
        ]
    }
    valid, reason = adapter.validate_nines_shape(payload)
    assert valid is False
    assert "details" in reason


def test_validate_nines_shape_rejects_non_numeric_score() -> None:
    """A task with non-numeric ``nines_score`` triggers REJECT."""
    payload = _well_formed_nines_payload()
    payload["scores"][0]["metadata"]["details"]["devolaflow-task-001"]["nines_score"] = (
        "not_a_number"
    )
    valid, reason = adapter.validate_nines_shape(payload)
    assert valid is False
    assert "nines_score" in reason


# ---------------------------------------------------------------------------
# Test 5: build_runs — synthetic + sample modes both produce expected shape
# ---------------------------------------------------------------------------


def test_build_runs_includes_all_required_sichip_keys() -> None:
    """Every produced result.json carries Si-Chip's REQUIRED_KEYS."""
    payload = _well_formed_nines_payload()
    runs = adapter.build_runs(payload)
    assert len(runs) == 3
    for task_id, result in runs.items():
        assert task_id.startswith("devolaflow-task-")
        for required_key in adapter.SICHIP_REQUIRED_KEYS:
            assert required_key in result, (
                f"task {task_id} missing Si-Chip required key {required_key!r}"
            )


def test_build_runs_pass_rate_equals_nines_score() -> None:
    """Per-task ``pass_rate`` matches the NineS ``nines_score`` exactly."""
    payload = _well_formed_nines_payload()
    runs = adapter.build_runs(payload)
    assert runs["devolaflow-task-001"]["pass_rate"] == 1.0
    assert runs["devolaflow-task-002"]["pass_rate"] == 0.5
    assert runs["devolaflow-task-003"]["pass_rate"] == 1.0
    # pass_k_4 + trigger_F1 share the same value (single-sample assumption)
    assert runs["devolaflow-task-002"]["pass_k_4"] == 0.5
    assert runs["devolaflow-task-002"]["trigger_F1"] == 0.5


def test_build_baselines_synthetic_mode_zeros_every_task() -> None:
    """``mode='synthetic'`` produces ``pass_rate=0.0`` for every task."""
    payload = _well_formed_nines_payload()
    baselines = adapter.build_baselines(payload, mode="synthetic")
    assert len(baselines) == 3
    for task_id, result in baselines.items():
        assert result["pass_rate"] == 0.0, (
            f"synthetic baseline for {task_id} must be 0.0, got {result['pass_rate']}"
        )
        assert result["pass_k_4"] == 0.0
        assert result["trigger_F1"] == 0.0


def test_build_baselines_sample_mode_uses_baseline_scores() -> None:
    """``mode='sample'`` uses the baseline NineS payload's per-task scores."""
    with_payload = _well_formed_nines_payload()
    baseline_payload = _well_formed_nines_payload()
    for task_id in baseline_payload["scores"][0]["metadata"]["details"]:
        baseline_payload["scores"][0]["metadata"]["details"][task_id]["nines_score"] = 0.2
    baselines = adapter.build_baselines(
        with_payload,
        mode="sample",
        baseline_nines_data=baseline_payload,
    )
    for task_id, result in baselines.items():
        assert result["pass_rate"] == 0.2, (
            f"sample mode baseline for {task_id} must be 0.2, got {result['pass_rate']}"
        )


def test_build_baselines_sample_mode_requires_baseline_data() -> None:
    """``mode='sample'`` without a baseline payload raises ValueError."""
    payload = _well_formed_nines_payload()
    with pytest.raises(ValueError) as exc_info:
        adapter.build_baselines(payload, mode="sample", baseline_nines_data=None)
    assert "baseline_nines_data" in str(exc_info.value)


def test_build_baselines_unknown_mode_raises() -> None:
    """An unknown mode raises ValueError per S-5."""
    payload = _well_formed_nines_payload()
    with pytest.raises(ValueError) as exc_info:
        adapter.build_baselines(payload, mode="kaboom")
    assert "kaboom" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 6: write_runs_dir + write_baseline_dir produce expected on-disk shape
# ---------------------------------------------------------------------------


def test_write_runs_dir_emits_one_file_per_task(tmp_path: Path) -> None:
    """Each task lands in its own subdirectory with a ``result.json``."""
    payload = _well_formed_nines_payload()
    runs = adapter.build_runs(payload)
    out_dir = tmp_path / "runs"
    count = adapter.write_runs_dir(out_dir, runs)
    assert count == 3
    written_files = sorted(out_dir.rglob("result.json"))
    assert len(written_files) == 3
    expected_task_ids = {
        "devolaflow-task-001",
        "devolaflow-task-002",
        "devolaflow-task-003",
    }
    written_task_dirs = {p.parent.name for p in written_files}
    assert written_task_dirs == expected_task_ids


def test_write_runs_dir_files_parse_as_valid_json(tmp_path: Path) -> None:
    """The written ``result.json`` files round-trip through json.loads."""
    payload = _well_formed_nines_payload()
    runs = adapter.build_runs(payload)
    out_dir = tmp_path / "runs"
    adapter.write_runs_dir(out_dir, runs)
    for result_path in sorted(out_dir.rglob("result.json")):
        loaded = json.loads(result_path.read_text(encoding="utf-8"))
        assert "pass_rate" in loaded
        assert "_provenance" in loaded
        assert loaded["_provenance"]["adapter"].endswith("nines_to_sichip_eval_adapter")


def test_write_baseline_dir_matches_runs_shape(tmp_path: Path) -> None:
    """Baseline directory writes the same file-count as the runs dir."""
    payload = _well_formed_nines_payload()
    runs = adapter.build_runs(payload)
    baselines = adapter.build_baselines(payload, mode="synthetic")
    runs_count = adapter.write_runs_dir(tmp_path / "runs", runs)
    baseline_count = adapter.write_baseline_dir(tmp_path / "baseline", baselines)
    assert runs_count == baseline_count == 3


# ---------------------------------------------------------------------------
# Test 7: main(argv) CLI entry — APPROVE + REJECT exit codes
# ---------------------------------------------------------------------------


def test_main_returns_0_on_approve(tmp_path: Path, nines_json_path: Path) -> None:
    """main() exits 0 + writes both directories on a valid input."""
    out_runs = tmp_path / "runs"
    out_baseline = tmp_path / "baseline"
    rc = adapter.main(
        [
            "--nines-json",
            str(nines_json_path),
            "--out-runs-dir",
            str(out_runs),
            "--out-baseline-dir",
            str(out_baseline),
            "--mode",
            "synthetic",
        ]
    )
    assert rc == 0
    assert (out_runs / "devolaflow-task-001" / "result.json").is_file()
    assert (out_baseline / "devolaflow-task-001" / "result.json").is_file()


def test_main_returns_1_on_reject_malformed_input(tmp_path: Path) -> None:
    """main() exits 1 when the NineS JSON is malformed."""
    bad_path = tmp_path / "broken.json"
    bad_path.write_text("not even json", encoding="utf-8")
    out_runs = tmp_path / "runs"
    out_baseline = tmp_path / "baseline"
    rc = adapter.main(
        [
            "--nines-json",
            str(bad_path),
            "--out-runs-dir",
            str(out_runs),
            "--out-baseline-dir",
            str(out_baseline),
        ]
    )
    assert rc == 1
    assert not out_runs.exists()
    assert not out_baseline.exists()


def test_main_returns_1_on_reject_unmappable_shape(tmp_path: Path) -> None:
    """main() exits 1 when the NineS shape lacks scoring_accuracy."""
    payload = {"scores": [{"name": "lint_cleanliness", "value": 100.0}]}
    bad_path = tmp_path / "no_accuracy.json"
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    rc = adapter.main(
        [
            "--nines-json",
            str(bad_path),
            "--out-runs-dir",
            str(tmp_path / "runs"),
            "--out-baseline-dir",
            str(tmp_path / "baseline"),
        ]
    )
    assert rc == 1


def test_main_sample_mode_requires_baseline_nines_json(
    tmp_path: Path, nines_json_path: Path
) -> None:
    """``--mode sample`` without ``--baseline-nines-json`` exits 1."""
    rc = adapter.main(
        [
            "--nines-json",
            str(nines_json_path),
            "--out-runs-dir",
            str(tmp_path / "runs"),
            "--out-baseline-dir",
            str(tmp_path / "baseline"),
            "--mode",
            "sample",
        ]
    )
    assert rc == 1


def test_main_sample_mode_full_round_trip(
    tmp_path: Path,
    nines_json_path: Path,
    baseline_nines_json_path: Path,
) -> None:
    """``--mode sample`` round-trip with both JSONs supplied → APPROVE."""
    out_runs = tmp_path / "runs"
    out_baseline = tmp_path / "baseline"
    rc = adapter.main(
        [
            "--nines-json",
            str(nines_json_path),
            "--baseline-nines-json",
            str(baseline_nines_json_path),
            "--out-runs-dir",
            str(out_runs),
            "--out-baseline-dir",
            str(out_baseline),
            "--mode",
            "sample",
        ]
    )
    assert rc == 0
    baseline_result = json.loads(
        (out_baseline / "devolaflow-task-002" / "result.json").read_text(encoding="utf-8")
    )
    # Sample-mode baseline must equal the lower fixture score (0.2)
    assert baseline_result["pass_rate"] == 0.2
