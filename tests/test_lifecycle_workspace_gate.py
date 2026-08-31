"""Runtime entrance-gate coverage for active and future task workspaces."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from devolaflow.agent_workspace.entrance import render_entrance_md
from devolaflow.agent_workspace.handoff import HandoffStore, make_envelope
from devolaflow.agent_workspace.round_engine import (
    ROUND_BLOCKERS_PRESENT,
    evaluate_round_pass,
)
from devolaflow.lifecycle import (
    POST_TASK_COMPLETE_EVENT,
    HookViolation,
    run_hooks,
    test_on_complete,
)
from devolaflow.lifecycle.runtime_wiring import fire_task_stop
from devolaflow.lifecycle.workspace_gate import (
    inspect_workspace_entrance,
    resolve_workspace,
)


def _active_folder(root: Path, change_id: str = "gate-change") -> Path:
    folder = root / ".local" / ".agent" / "active" / change_id
    folder.mkdir(parents=True)
    return folder


def _clean_report(**extra: object) -> dict[str, object]:
    return {
        "tests_passed": 1,
        "tests_failed": 0,
        "lint_status": "clean",
        **extra,
    }


def test_active_resolver_and_lint_reuse_the_entrance_finding(tmp_path: Path) -> None:
    folder = _active_folder(tmp_path)

    workspace = resolve_workspace(
        {"change_context": {"change_id": "gate-change"}},
        repo_root=tmp_path,
    )
    assert workspace is not None
    assert workspace.surface == "active_change"
    assert workspace.folder == folder

    check = inspect_workspace_entrance(
        {"change_id": "gate-change"},
        repo_root=tmp_path,
    )
    assert check is not None
    assert len(check.findings) == 1
    assert check.findings[0].kind == "ENTRANCE_MISSING"


def test_lite_task_stop_warns_and_records_missing_entrance(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _active_folder(tmp_path)
    payload = _clean_report(change_id="gate-change", _workspace_repo_root=str(tmp_path))

    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        result = test_on_complete(payload)

    assert result.passed is False
    finding = next(v for v in result.violations if v.code == "ENTRANCE_MISSING")
    assert finding.severity == "warning"
    assert any("ENTRANCE_MISSING" in record.message for record in caplog.records)


def test_strict_task_stop_blocks_missing_entrance(tmp_path: Path) -> None:
    _active_folder(tmp_path)
    payload = _clean_report(change_id="gate-change", _workspace_repo_root=str(tmp_path))

    with pytest.raises(HookViolation) as exc_info:
        test_on_complete(payload, strict=True)

    assert exc_info.value.code == "ENTRANCE_MISSING"
    assert exc_info.value.severity == "blocker"


def test_runtime_strict_and_lite_modes_use_workspace_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _active_folder(tmp_path)
    monkeypatch.setenv("DEVOLAFLOW_AGENT_WORKSPACE", "1")
    payload = _clean_report(change_id="gate-change")

    with pytest.raises(HookViolation) as exc_info:
        fire_task_stop(payload, repo_root=tmp_path)
    assert exc_info.value.code == "ENTRANCE_MISSING"
    assert exc_info.value.severity == "blocker"

    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        result = fire_task_stop(payload, repo_root=tmp_path, strict=False)
    assert result is not None
    assert any(v.code == "ENTRANCE_MISSING" and v.severity == "warning" for v in result.violations)


def test_present_entrance_keeps_task_stop_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = _active_folder(tmp_path)
    (folder / "entrance.md").write_text(
        render_entrance_md("gate-change", "Gate change"),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOLAFLOW_AGENT_WORKSPACE", "1")

    result = fire_task_stop(
        _clean_report(change_id="gate-change"),
        repo_root=tmp_path,
    )

    assert result is not None
    assert result.passed is True
    assert not any(v.code.startswith("ENTRANCE_") for v in result.violations)


def test_canonical_post_task_complete_strictly_consumes_entrance_gate(
    tmp_path: Path,
) -> None:
    _active_folder(tmp_path)

    with pytest.raises(HookViolation) as exc_info:
        run_hooks(
            POST_TASK_COMPLETE_EVENT,
            _clean_report(change_id="gate-change", _workspace_repo_root=str(tmp_path)),
            strict=True,
        )

    assert exc_info.value.code == "ENTRANCE_MISSING"
    assert exc_info.value.severity == "blocker"


def test_handoff_status_report_passes_repository_context_to_task_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _active_folder(tmp_path)
    monkeypatch.setenv("DEVOLAFLOW_AGENT_WORKSPACE", "1")
    store = HandoffStore(repo_root=tmp_path)
    envelope = make_envelope(
        seq=1,
        from_layer="L2",
        to_layer="L1",
        change_id="gate-change",
        envelope_kind="StatusReport",
        payload={"metrics": {"tests_passed": 1, "tests_failed": 0, "lint_status": "clean"}},
    )

    with pytest.raises(HookViolation) as exc_info:
        store.write_envelope(envelope)

    assert exc_info.value.code == "ENTRANCE_MISSING"
    assert not (store.handoff_root / envelope.filename).exists()


def test_no_workspace_context_keeps_clean_status_report_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _active_folder(tmp_path)
    monkeypatch.setenv("DEVOLAFLOW_AGENT_WORKSPACE", "1")

    result = fire_task_stop(_clean_report(task_id="T-ordinary"), repo_root=tmp_path)

    assert result is not None
    assert result.passed is True
    assert result.violations == []


def test_future_task_surface_resolves_and_checks_entrance(tmp_path: Path) -> None:
    task_folder = tmp_path / ".local" / "tasks" / "future-task"
    task_folder.mkdir(parents=True)
    check = inspect_workspace_entrance(
        {"workspace_context": {"surface": "task", "name": "future-task"}},
        repo_root=tmp_path,
    )

    assert check is not None
    assert check.workspace.surface == "task"
    assert [finding.kind for finding in check.findings] == ["ENTRANCE_MISSING"]


def test_round_gate_consumes_the_same_blocking_entrance_finding(tmp_path: Path) -> None:
    _active_folder(tmp_path)
    check = inspect_workspace_entrance(
        {"change_id": "gate-change"},
        repo_root=tmp_path,
    )
    assert check is not None
    finding = check.findings[0]

    result = evaluate_round_pass(
        ("C-1",),
        ("C-1",),
        0,
        entrance_finding=finding,
    )

    assert result.passed is False
    assert result.reasons == (ROUND_BLOCKERS_PRESENT,)


def test_round_gate_does_not_block_on_lite_entrance_warning() -> None:
    from devolaflow.lifecycle.dispatcher import HookViolation

    warning = HookViolation("ENTRANCE_MISSING", "missing", severity="warning")
    result = evaluate_round_pass(("C-1",), ("C-1",), 0, entrance_finding=warning)

    assert result.passed is True
