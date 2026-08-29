"""Focused tests for the v21.0.0 PV-02 S1 short-path contract."""

from __future__ import annotations

import logging

import pytest

from devolaflow.lifecycle import (
    POST_TASK_COMPLETE_EVENT,
    TASK_STOP_EVENT,
    HookViolation,
    clear_hooks,
    list_handlers,
    register_hook,
    run_hooks,
    test_on_complete,
    validate_trivial_path,
)
from devolaflow.lifecycle.runtime_wiring import fire_task_stop
from devolaflow.lifecycle.validate_surgical_scope import DiffStats, FileDiffStat
from devolaflow.skills.change_activation import evaluate_trivial_path


def _stats(files: int, insertions: int, deletions: int) -> dict[str, int]:
    return {"files": files, "insertions": insertions, "deletions": deletions}


@pytest.fixture(scope="module", autouse=True)
def _restore_task_stop_extra_after_isolated_hook_tests():
    """Keep this module's canonical extra wired after other hook tests clear extras."""
    clear_hooks(TASK_STOP_EVENT)
    register_hook(POST_TASK_COMPLETE_EVENT, validate_trivial_path)
    yield
    clear_hooks(TASK_STOP_EVENT)


def test_evaluate_trivial_path_passes_canonical_diff_stats() -> None:
    stats = DiffStats(
        base_ref="HEAD",
        files=(FileDiffStat("src/task.py", 4, 2),),
        insertions=4,
        deletions=2,
    )

    result = evaluate_trivial_path("TRIVIAL", stats)

    assert result.passed is True
    assert result.upgrade_target is None
    assert result.diff_stats is stats
    assert result.as_dict()["diff_stats"] == _stats(1, 4, 2)


@pytest.mark.parametrize(
    ("diff_stats", "code", "target"),
    [
        (_stats(1, 10, 10), "TSP003", "SIMPLE"),
        (_stats(2, 1, 1), "TSP002", "SIMPLE"),
        (_stats(0, 0, 0), "TSP001", "SIMPLE"),
    ],
)
def test_evaluate_trivial_path_rejects_boundaries(
    diff_stats: dict[str, int],
    code: str,
    target: str,
) -> None:
    result = evaluate_trivial_path("TRIVIAL", diff_stats)

    assert result.passed is False
    assert code in {violation.code for violation in result.violations}
    assert result.upgrade_target == target


def test_evaluate_trivial_path_rejects_cross_cutting_and_mismatch() -> None:
    result = evaluate_trivial_path(
        "TRIVIAL",
        _stats(1, 2, 1),
        is_cross_cutting=True,
    )

    assert result.passed is False
    assert "TSP004" in {violation.code for violation in result.violations}
    assert "TSP005" in {violation.code for violation in result.violations}
    assert result.actual_complexity == "STANDARD"
    assert result.upgrade_target == "STANDARD"


@pytest.mark.parametrize("field", ["files", "insertions", "deletions"])
def test_evaluate_trivial_path_rejects_negative_counts(field: str) -> None:
    values = _stats(1, 1, 1)
    values[field] = -1

    with pytest.raises(ValueError, match=f"diff_stats\\.{field} must be >= 0"):
        evaluate_trivial_path("TRIVIAL", values)


def test_validate_trivial_path_legacy_payload_is_noop() -> None:
    result = validate_trivial_path({"task_id": "legacy", "metrics": {}})

    assert result.passed is True
    assert "compatibility no-op" in result.metadata["reason"]


def test_validate_trivial_path_exposes_structured_result_and_lite_warning(caplog) -> None:
    payload = {
        "task_id": "T1",
        "trivial_path": {"declared_complexity": "TRIVIAL"},
        "diff_stats": _stats(1, 19, 1),
    }

    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        result = validate_trivial_path(payload, strict=False)

    assert result.passed is False
    assert result.violations[0].code == "TSP003"
    assert result.metadata["trivial_path"]["upgrade_target"] == "SIMPLE"
    assert result.metadata["trivial_path"]["diff_stats"] == _stats(1, 19, 1)
    assert any("TSP003" in record.message for record in caplog.records)


def test_validate_trivial_path_strict_raises_hook_violation() -> None:
    payload = {
        "trivial_path": {"declared_complexity": "TRIVIAL"},
        "diff_stats": _stats(2, 1, 0),
    }

    with pytest.raises(HookViolation) as exc_info:
        validate_trivial_path(payload, strict=True)

    assert exc_info.value.code == "TSP002"
    assert exc_info.value.context["upgrade_target"] == "SIMPLE"


def test_validate_trivial_path_ignores_nontrivial_declaration() -> None:
    result = validate_trivial_path(
        {
            "trivial_path": {"declared_complexity": "SIMPLE"},
            "diff_stats": _stats(2, 50, 10),
        }
    )

    assert result.passed is True
    assert "not TRIVIAL" in result.metadata["reason"]


def test_task_stop_wiring_uses_legacy_and_canonical_aliases() -> None:
    handlers = list_handlers(TASK_STOP_EVENT)

    assert handlers[0] is test_on_complete
    assert validate_trivial_path in handlers
    assert list_handlers(POST_TASK_COMPLETE_EVENT) == handlers


def test_task_stop_aggregates_short_path_result_for_upstream() -> None:
    result = run_hooks(
        TASK_STOP_EVENT,
        {
            "tests_passed": 1,
            "tests_failed": 0,
            "lint_status": "clean",
            "trivial_path": {"declared_complexity": "TRIVIAL"},
            "diff_stats": _stats(1, 2, 1),
        },
    )

    assert result.passed is True
    assert result.metadata["trivial_path"]["declared_complexity"] == "TRIVIAL"
    assert result.metadata["trivial_path"]["upgrade_target"] is None


def test_fire_task_stop_runs_short_path_hook_when_engaged(monkeypatch) -> None:
    monkeypatch.setenv("DEVOLAFLOW_AGENT_WORKSPACE", "1")

    result = fire_task_stop(
        {
            "tests_passed": 1,
            "tests_failed": 0,
            "lint_status": "clean",
            "trivial_path": {"declared_complexity": "TRIVIAL"},
            "diff_stats": _stats(2, 1, 0),
        },
        strict=False,
    )

    assert result is not None
    assert result.passed is False
    assert "TSP002" in {violation.code for violation in result.violations}
    assert result.metadata["trivial_path"]["upgrade_target"] == "SIMPLE"
