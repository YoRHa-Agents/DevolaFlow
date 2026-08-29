"""Reproducibility metadata contracts for harness output and telemetry."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from devolaflow.harness.aggregator import aggregate_ledger
from devolaflow.harness.evaluator import evaluate_harness, render_evaluation
from devolaflow.harness.metadata import MetadataError, build_run_metadata
from devolaflow.harness.telemetry import append_gate_telemetry


def _git_runner(outputs: list[str]):
    def runner(argv: list[str], **_kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.pop(0), stderr="")

    return runner


def _ledger(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "ts": "2026-08-29T00:00:00+00:00",
                "change_id": "metadata",
                "round": 1,
                "layer": "L0",
                "dispatch_id": "dispatch-1",
                "tokens_injected_measured": 10,
                "tokens_budget": 100,
                "constraint_count": 1,
                "quantifiable_ratio": 1.0,
                "tier_breakdown": {"invariant": 1, "guard": 0, "advisory": 0},
                "advisory_folded": False,
                "model_hint": "inherit",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _signals() -> dict[str, object]:
    return {
        "ruff_lint": True,
        "ruff_format": True,
        "test_suite": True,
        "coverage_pct": 100,
        "layout_invariant": True,
        "compatibility_suite": True,
        "w17_new_tests": 0,
        "docstring_coverage_pct": 100,
        "agents_md_tokens": 1,
        "suite_wall_seconds": 1.0,
        "cjk_violations": 0,
        "ghost_loc": 1,
    }


def test_metadata_records_supplied_salt_and_repository_facts(tmp_path: Path) -> None:
    ledger = tmp_path / ".local" / "telemetry" / "harness.jsonl"
    ledger.parent.mkdir(parents=True)
    _ledger(ledger)
    metadata = build_run_metadata(
        ledger,
        repo_root=tmp_path,
        sampled_at="2026-08-29T00:00:00+00:00",
        salt=70000001,
        runner=_git_runner(["main\n", "a" * 40 + "\n", "b" * 40 + "\n"]),
    )

    assert metadata["run_id"].startswith("run-")
    assert metadata["salt"] == 70000001
    assert metadata["salt_status"] == "AVAILABLE"
    assert metadata["ledger_path"] == ".local/telemetry/harness.jsonl"
    assert metadata["repo_ref"] == "main"
    assert metadata["repo_sha"] == "a" * 40
    assert metadata["base_ref"] == "HEAD~1"
    assert metadata["status"] == "AVAILABLE"
    assert not metadata["ledger_path"].startswith("/")


def test_metadata_marks_missing_salt_and_git_facts_insufficient(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    _ledger(ledger)

    def unavailable(*_args, **_kwargs):
        raise OSError("git unavailable")

    metadata = build_run_metadata(
        ledger,
        repo_root=tmp_path,
        sampled_at="2026-08-29T00:00:00+00:00",
        runner=unavailable,
    )

    assert metadata["salt"] is None
    assert metadata["salt_status"] == "INSUFFICIENT"
    assert metadata["repo_ref"] is None
    assert metadata["repo_sha"] is None
    assert metadata["repo_status"] == "INSUFFICIENT"
    assert metadata["status"] == "INSUFFICIENT"
    json.dumps(metadata, allow_nan=False)


def test_metadata_rejects_absolute_ledger_path_outside_repo(tmp_path: Path) -> None:
    ledger = tmp_path / "outside" / "harness.jsonl"
    ledger.parent.mkdir()
    _ledger(ledger)
    metadata = build_run_metadata(
        ledger,
        repo_root=tmp_path / "repo",
        sampled_at="2026-08-29T00:00:00+00:00",
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, stdout="", stderr=""),
    )

    assert metadata["ledger_path"] is None
    assert metadata["ledger_status"] == "INSUFFICIENT"


def test_evaluation_metadata_is_nested_and_repeated_rendering_is_stable(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    _ledger(ledger)
    results = [
        evaluate_harness(
            ledger,
            signals=_signals(),
            repo_root=tmp_path,
            sampled_at="2026-08-29T00:00:00+00:00",
        )
        for _ in range(2)
    ]

    assert results[0]["harness_summary"]["metadata"]["status"] == "INSUFFICIENT"
    assert render_evaluation(results[0]) == render_evaluation(results[1])
    assert (
        results[0]["harness_summary"]["metadata"]["run_id"]
        == results[1]["harness_summary"]["metadata"]["run_id"]
    )
    explicit = evaluate_harness(
        ledger,
        signals=_signals(),
        repo_root=tmp_path,
        sampled_at="2026-08-29T00:00:00+00:00",
        run_id="run-explicit",
        salt="70000003",
    )
    assert explicit["metadata"]["run_id"] == "run-explicit"
    assert explicit["metadata"]["salt"] == "70000003"


def test_telemetry_carries_the_same_metadata_envelope(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    _ledger(ledger)
    metadata = build_run_metadata(
        ledger,
        repo_root=tmp_path,
        sampled_at="2026-08-29T00:00:00+00:00",
        salt="70000002",
        runner=_git_runner(["main\n", "a" * 40 + "\n", "b" * 40 + "\n"]),
    )

    append_gate_telemetry(
        ledger,
        "PV-05",
        "test-harness",
        "PASS",
        timestamp="2026-08-29T00:00:00+00:00",
        metadata=metadata,
    )

    summary = aggregate_ledger(ledger)
    assert summary["metadata"] == metadata


def test_metadata_rejects_non_finite_salt(tmp_path: Path) -> None:
    with pytest.raises(MetadataError, match="salt"):
        build_run_metadata(
            tmp_path / "harness.jsonl",
            repo_root=tmp_path,
            sampled_at="2026-08-29T00:00:00+00:00",
            salt=float("nan"),
        )
