"""Contract tests for the real CLI calibration matrix and ROI report."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from devolaflow.harness.__main__ import main
from devolaflow.harness.calibration import (
    CalibrationError,
    CalibrationRunner,
    aggregate_calibration_results,
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
    return subprocess.CompletedProcess(
        argv,
        0,
        stdout=json.dumps(
            {
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "skill_loaded": True,
            }
        ),
        stderr="",
    )


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
    assert report["summary"]["comparisons"][0]["pass_rate_difference"]["ci95"] == [0.0, 0.0]
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
