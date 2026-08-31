"""Contract tests for the real CLI calibration matrix and ROI report."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from devolaflow.harness.__main__ import main
from devolaflow.harness.calibration import (
    CalibrationError,
    CalibrationRunner,
    aggregate_calibration_results,
    render_calibration_report,
)
from devolaflow.harness.cli_probe import ChannelConfig, ProbeSpec


def _commands() -> dict[str, ChannelConfig]:
    return {
        channel: ChannelConfig(channel, sys.executable, ("{prompt}",))
        for channel in ("claude", "codex", "kimi")
    }


def _fake_runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    if argv[-1] == "--version":
        return subprocess.CompletedProcess(argv, 0, stdout="Python\n", stderr="")
    canary_match = re.search(r"DF-SKILL-CANARY-[A-Za-z0-9]+", argv[-1])
    response = {
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "skill_loaded": False,
    }
    if canary_match:
        response["skill_canary_echo"] = canary_match.group(0)
    return subprocess.CompletedProcess(
        argv,
        0,
        stdout=json.dumps(response),
        stderr="",
    )


def _paired_specs(replicates: int = 5) -> list[ProbeSpec]:
    return [
        ProbeSpec(
            channel="claude",
            task_class="read-only",
            arm=arm,
            seed="seed",
            replicate=replicate,
            prompt="p",
            salt="salt",
        )
        for arm in ("skill-off", "skill-on")
        for replicate in range(1, replicates + 1)
    ]


def _paired_result(
    spec: ProbeSpec,
    *,
    passed: bool = True,
    token_available: bool = True,
    wall_available: bool = True,
) -> dict:
    return {
        "status": "PASS" if passed else "FAIL",
        "task_class": spec.task_class,
        "channel": spec.channel,
        "arm": spec.arm,
        "metadata": {
            "replicate": spec.replicate,
            "run_id": f"{spec.arm}-{spec.replicate}",
            "seed": spec.seed,
            "salt": spec.salt,
        },
        "execution": {
            "reason": "completed" if wall_available else "unavailable",
            "wall_time_seconds": float(spec.replicate) if wall_available else 0.0,
        },
        "token_usage": {
            "total_tokens": 100 + spec.replicate if token_available else None,
            "status": "AVAILABLE" if token_available else "INSUFFICIENT",
        },
        "skill_loaded": {"value": spec.arm == "skill-on", "status": "AVAILABLE"},
    }


def test_plan_filters_after_canonical_matrix_order(tmp_path: Path) -> None:
    specs = CalibrationRunner(repo_root=tmp_path, commands=_commands()).plan(
        seed="seed",
        salt="70000002",
        replicates=2,
        channels=("kimi", "claude"),
        task_classes=("recovery", "read-only"),
        raw_output_dir=".local/raw",
        generated_at="2026-08-29T00:00:00+00:00",
    )

    assert [(spec.task_class, spec.channel, spec.arm, spec.replicate) for spec in specs[:8]] == [
        ("read-only", "claude", "skill-off", 1),
        ("read-only", "claude", "skill-off", 2),
        ("read-only", "claude", "skill-on", 1),
        ("read-only", "claude", "skill-on", 2),
        ("read-only", "kimi", "skill-off", 1),
        ("read-only", "kimi", "skill-off", 2),
        ("read-only", "kimi", "skill-on", 1),
        ("read-only", "kimi", "skill-on", 2),
    ]
    assert len(specs) == 16


def test_plan_rejects_invalid_generated_timestamp(tmp_path: Path) -> None:
    with pytest.raises(CalibrationError, match="ISO-8601"):
        CalibrationRunner(repo_root=tmp_path, commands=_commands()).plan(
            seed="seed",
            salt="70000002",
            replicates=2,
            generated_at="not-a-timestamp",
        )


def test_run_records_real_outcomes_and_writes_reports(tmp_path: Path) -> None:
    runner = CalibrationRunner(repo_root=tmp_path, commands=_commands(), runner=_fake_runner)
    report = runner.run(
        seed="seed",
        salt="70000002",
        replicates=2,
        channels=("claude",),
        task_classes=("read-only",),
        output_dir=".local/research",
        raw_output_dir=".local/raw",
        generated_at="2026-08-29T00:00:00+00:00",
    )
    markdown, machine = runner.write_report(report, output_dir=".local/research")

    assert report["summary"]["counts"] == {
        "planned": 4,
        "observed": 4,
        "completed": 4,
        "pass": 4,
        "fail": 0,
        "insufficient": 0,
        "unrecorded": 0,
    }
    assert report["summary"]["roi"]["status"] == "AVAILABLE"
    assert report["telemetry"]["attempted_records"] == 4
    assert report["telemetry"]["appended_records"] == 4
    assert report["execution"]["timeout_phase"] is None
    assert report["summary"]["comparisons"][0]["pass_rate_difference"]["ci95"] == [0.0, 0.0]
    assert "Wilson intervals are descriptive success-rate intervals only" in report["markdown"]
    assert "MDE and statistical power are limited" in report["markdown"]
    assert markdown.exists()
    assert json.loads(machine.read_text())["run_id"] == report["run_id"]
    assert str(tmp_path) not in report["markdown"]


def test_unavailable_channel_fills_every_spec_as_insufficient(tmp_path: Path) -> None:
    commands = {
        channel: ChannelConfig(channel, "definitely-missing-devola-cli", ())
        for channel in ("claude", "codex", "kimi")
    }
    runner = CalibrationRunner(repo_root=tmp_path, commands=commands)
    report = runner.run(
        seed="seed",
        salt="70000002",
        replicates=2,
        channels=("claude",),
        task_classes=("read-only",),
        output_dir=".local/research",
        raw_output_dir=".local/raw",
        generated_at="2026-08-29T00:00:00+00:00",
    )

    assert report["summary"]["counts"]["observed"] == 4
    assert report["summary"]["counts"]["insufficient"] == 4
    assert report["summary"]["roi"]["status"] == "INSUFFICIENT"
    assert report["preflight"][0]["executable_available"] is False
    assert len(list((tmp_path / ".local/raw").glob("*.json"))) == 4


def test_outer_timeout_records_calibration_phase_and_termination(tmp_path: Path) -> None:
    runner = CalibrationRunner(repo_root=tmp_path, commands=_commands(), runner=_fake_runner)
    report = runner.run(
        seed="timeout-seed",
        salt="timeout-salt",
        replicates=1,
        channels=("claude",),
        task_classes=("read-only",),
        total_timeout_seconds=0.000001,
        output_dir=".local/research",
        raw_output_dir=".local/raw",
        generated_at="2026-08-29T00:00:00+00:00",
    )

    assert report["execution"]["timeout_phase"] == "calibration"
    assert report["execution"]["termination_reason"] == "outer_timeout"
    artifacts = list((tmp_path / ".local/raw").glob("*.json"))
    assert len(artifacts) == 2
    for artifact in artifacts:
        execution = json.loads(artifact.read_text())["execution"]
        assert execution["timeout_phase"] == "calibration"
        assert execution["termination_reason"] == "outer_timeout"
        assert execution["started_at"] == execution["finished_at"]


def test_aggregate_marks_missing_usage_and_skill_insufficient() -> None:
    spec = ProbeSpec(
        channel="claude",
        task_class="read-only",
        arm="skill-on",
        seed="seed",
        replicate=1,
        prompt="p",
    )
    result = {
        "status": "PASS",
        "task_class": spec.task_class,
        "channel": spec.channel,
        "arm": spec.arm,
        "token_usage": {"total_tokens": None, "status": "INSUFFICIENT"},
        "skill_loaded": {"value": None, "status": "INSUFFICIENT"},
        "execution": {"reason": "completed", "wall_time_seconds": 0.1},
    }
    cell = aggregate_calibration_results([result], planned_specs=[spec], run_id="calibration-test")
    assert cell["cells"][0]["counts"] == {"n": 1, "pass": 1, "fail": 0, "insufficient": 0}
    assert cell["cells"][0]["token_cost"]["status"] == "INSUFFICIENT"
    assert cell["cells"][0]["skill_loaded"]["status"] == "INSUFFICIENT"


def test_paired_differences_match_replicates_and_bootstrap_is_deterministic() -> None:
    specs = _paired_specs()
    results = [
        _paired_result(
            spec,
            passed=(
                spec.replicate in {1, 4, 5}
                if spec.arm == "skill-off"
                else spec.replicate in {1, 2, 4, 5}
            ),
        )
        for spec in specs
    ]
    first = aggregate_calibration_results(results, planned_specs=specs, run_id="run")
    second = aggregate_calibration_results(results, planned_specs=specs, run_id="run")
    paired = first["comparisons"][0]["paired_differences"]

    assert paired == second["comparisons"][0]["paired_differences"]
    assert paired["status"] == "AVAILABLE"
    assert paired["pairing"]["key"] == "task_class/channel/replicate"
    assert paired["pairing"]["unit"] == "matched skill-on/skill-off replicate pair"
    assert paired["pairing"]["observed_pairs"] == 5
    assert paired["pairing"]["replicate_ids"] == [1, 2, 3, 4, 5]
    assert paired["bootstrap"] == {
        "method": "paired percentile bootstrap",
        "seed": 20260901,
        "replicates": 2000,
        "resample_unit": "matched replicate pair",
        "cluster": "read-only/claude cell",
        "interval": "percentile 95%",
    }
    assert paired["pass_rate"]["skill_on_minus_skill_off"] == pytest.approx(0.2)
    assert paired["pass_rate"]["status"] == "AVAILABLE"
    assert paired["wall_time_seconds"]["skill_on_minus_skill_off"] == 0.0
    assert paired["token_cost"]["skill_on_minus_skill_off"] == 0.0


def test_incomplete_cells_hide_partial_metrics_from_default_report() -> None:
    specs = _paired_specs()
    observed = [_paired_result(spec) for spec in specs if spec.replicate <= 2]
    summary = aggregate_calibration_results(observed, planned_specs=specs, run_id="run")
    on_cell = next(cell for cell in summary["cells"] if cell["arm"] == "skill-on")

    assert on_cell["completeness_status"] == "INSUFFICIENT"
    assert on_cell["token_cost"]["status"] == "INSUFFICIENT"
    assert on_cell["token_cost"]["mean"] is None
    assert on_cell["token_cost"]["p50"] is None
    assert on_cell["token_cost"]["observed_partial"]["status"] == "PARTIAL"
    assert on_cell["wall_time_seconds"]["p95"] is None
    assert on_cell["wall_time_seconds"]["observed_partial"]["p95"] == 2.0

    report = {
        "run_id": "run",
        "metadata": {"generated_at": "now", "salt": "salt", "seed": "seed"},
        "matrix": {
            "task_classes": ["read-only"],
            "channels": ["claude"],
            "arms": ["skill-off", "skill-on"],
            "replicates": 5,
            "planned_specs": 10,
            "timeout_seconds": 1,
            "total_timeout_seconds": 1,
        },
        "preflight": [],
        "summary": summary,
    }
    markdown = render_calibration_report(report)
    assert "INSUFFICIENT" in markdown
    assert "mean=101.0" not in markdown
    assert "p50=1.0000" not in markdown
    legacy_comparison = dict(summary["comparisons"][0])
    legacy_comparison.pop("paired_differences")
    legacy_summary = {**summary, "comparisons": [legacy_comparison]}
    assert "no matched-replicate bootstrap data" in render_calibration_report(
        {**report, "summary": legacy_summary}
    )


def test_missing_tokens_are_not_zero_in_paired_difference() -> None:
    specs = _paired_specs()
    results = [_paired_result(spec, token_available=spec.replicate != 3) for spec in specs]
    summary = aggregate_calibration_results(results, planned_specs=specs, run_id="run")
    paired = summary["comparisons"][0]["paired_differences"]
    on_cell = next(cell for cell in summary["cells"] if cell["arm"] == "skill-on")

    assert on_cell["token_cost"]["status"] == "INSUFFICIENT"
    assert on_cell["token_cost"]["mean"] is None
    assert on_cell["token_cost"]["observed_partial"]["observed_n"] == 4
    assert paired["token_cost"]["status"] == "INSUFFICIENT"
    assert paired["token_cost"]["observed_n"] == 4
    assert paired["token_cost"]["skill_on_minus_skill_off"] is None
    assert paired["token_cost"]["observed_partial"]["skill_on_minus_skill_off"] == 0.0


def test_calibration_cli_dry_run_does_not_execute(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    exit_code = main(
        [
            "calibration",
            "--seed",
            "seed",
            "--salt",
            "70000002",
            "--replicates",
            "2",
            "--channels",
            "claude",
            "--task-classes",
            "read-only",
            "--output-dir",
            str(output_dir),
            "--raw-output-dir",
            ".local/raw",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    plan = json.loads((output_dir / "v21.1.0_calibration_plan.json").read_text())
    assert plan["status"] == "PLAN"
    assert plan["count"] == 4
