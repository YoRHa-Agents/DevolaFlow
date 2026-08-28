"""Focused Loop v3 PV-1A regression coverage."""

from __future__ import annotations

import asyncio
import time

import pytest

from devolaflow.agent_workspace.dispatch_executor import ExecutorError
from devolaflow.dispatch import async_dispatch_wave_tasks, dispatch_wave_tasks
from devolaflow.gate.models import CheckResult, GateInput
from devolaflow.gate.profiles import STANDARD
from devolaflow.gate.scorer import evaluate_gate


@pytest.mark.parametrize(
    ("required_check", "failure_label"),
    [
        ("build_status", "build"),
        ("test_results", "test"),
        ("lint_status", "lint"),
        ("acceptance_criteria_results", "acceptance_criteria"),
    ],
)
def test_standard_gate_rejects_required_skip(required_check: str, failure_label: str) -> None:
    gate_input = GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        acceptance_criteria_results=CheckResult(status="pass"),
    )
    setattr(gate_input, required_check, CheckResult(status="skip"))

    verdict = evaluate_gate(gate_input, STANDARD)

    assert verdict.decision == "FAIL"
    assert failure_label in verdict.rationale


@pytest.mark.parametrize("invalid_parallelism", [0, -1])
def test_dispatch_rejects_explicit_invalid_parallelism(invalid_parallelism: int) -> None:
    wave = {
        "tasks": [
            {"task_id": "one", "timeout_seconds": None},
            {"task_id": "two", "timeout_seconds": None},
        ],
        "sync_barrier": {"mode": "parallel", "max_parallelism": invalid_parallelism},
    }

    with pytest.raises(ExecutorError):
        dispatch_wave_tasks(wave, lambda task: lambda: task["task_id"])


def test_async_wave_dispatch_runs_inside_active_loop() -> None:
    async def run_wave() -> list:
        wave = {
            "tasks": [
                {"task_id": "one", "timeout_seconds": None},
                {"task_id": "two", "timeout_seconds": None},
            ],
            "sync_barrier": {"mode": "parallel", "max_parallelism": 2},
        }
        return await async_dispatch_wave_tasks(wave, lambda task: lambda: task["task_id"])

    outcomes = asyncio.run(run_wave())

    assert [outcome.result for outcome in outcomes] == ["one", "two"]
    assert all(outcome.succeeded for outcome in outcomes)


def test_timed_sync_callable_is_stopped_before_side_effect(tmp_path) -> None:
    marker = tmp_path / "post-timeout.txt"
    wave = {
        "tasks": [{"task_id": "slow", "timeout_seconds": 0.05}],
        "sync_barrier": {"mode": "all"},
    }

    def slow_callable() -> None:
        time.sleep(0.25)
        marker.write_text("must not be written", encoding="utf-8")

    outcomes = dispatch_wave_tasks(wave, lambda task: slow_callable)

    assert outcomes[0].succeeded is False
    assert isinstance(outcomes[0].exception, TimeoutError)
    assert not marker.exists()
    time.sleep(0.3)
    assert not marker.exists()


def test_sync_wave_dispatch_happy_path_remains_ordered() -> None:
    wave = {
        "tasks": [
            {"task_id": "one", "timeout_seconds": None},
            {"task_id": "two", "timeout_seconds": None},
        ],
        "sync_barrier": {"mode": "all"},
    }

    outcomes = dispatch_wave_tasks(wave, lambda task: lambda: task["task_id"])

    assert [outcome.task_id for outcome in outcomes] == ["one", "two"]
    assert [outcome.result for outcome in outcomes] == ["one", "two"]
    assert all(outcome.succeeded for outcome in outcomes)
