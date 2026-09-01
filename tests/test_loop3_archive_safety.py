"""Loop v3 archive safety regressions."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import devolaflow.agent_workspace.change as change_module
import devolaflow.local.archive as archive_module
from devolaflow.agent_workspace.archive import ArchiveError, ArchiveManager
from devolaflow.agent_workspace.change import ChangeStore, ChangeStoreError
from devolaflow.local.archive import (
    ArchiveApproval,
    apply_archive_plan,
    build_archive_plan,
    inspect_safety,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _clean_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=loop3-test",
            "-c",
            "user.email=loop3-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _task(repo: Path, name: str) -> Path:
    path = repo / ".local/tasks" / name
    path.mkdir(parents=True)
    (path / "task.yaml").write_text("status: done\ncluster: quality\n", encoding="utf-8")
    (path / "context.txt").write_text(name, encoding="utf-8")
    return path


def _codes(findings: tuple[object, ...]) -> set[str]:
    return {finding.code for finding in findings}


def test_separate_approval_selects_exact_entries_and_drives_index(
    tmp_path: Path,
) -> None:
    first = _task(tmp_path, "first")
    second = _task(tmp_path, "second")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    selected = next(entry for entry in plan.entries if entry.source.endswith("/first"))
    approval = ArchiveApproval(
        plan_fingerprint=plan.fingerprint,
        entries=(selected.key,),
    )

    result = apply_archive_plan(tmp_path, plan, approval)

    assert result.success
    assert not first.exists()
    assert second.exists()
    index = (tmp_path / ".local/tasks/INDEX.md").read_text(encoding="utf-8")
    assert selected.source in index
    assert all(entry.source not in index for entry in plan.entries if entry is not selected)


def test_approval_fingerprint_mismatch_refuses_without_mutation(tmp_path: Path) -> None:
    source = _task(tmp_path, "fingerprint")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    approval = ArchiveApproval("wrong-fingerprint", (plan.entries[0].key,))

    result = apply_archive_plan(tmp_path, plan, approval)

    assert result.refused
    assert "APPROVAL_MISMATCH" in _codes(result.findings)
    assert source.exists()


def test_partial_apply_returns_explicit_recovery_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _task(tmp_path, "first")
    second = _task(tmp_path, "second")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    entries = tuple(plan.entries)
    original_append = archive_module.append_mapping_record

    def fail_second(*args, **kwargs):
        if args[1].endswith("/second"):
            raise archive_module.ArchiveError("simulated mapping persistence failure")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(archive_module, "append_mapping_record", fail_second)
    result = apply_archive_plan(tmp_path, plan, entries)

    assert result.refused
    assert result.recovery_required
    assert "PARTIAL_APPLY" in _codes(result.findings)
    assert not first.exists()
    assert not second.exists()
    assert len(result.mappings) == 1
    assert result.recovery_hint


def test_cross_device_preflight_refuses_atomic_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _task(tmp_path, "cross-device")
    _clean_repo(tmp_path)
    monkeypatch.setattr(archive_module, "_same_device", lambda *_: False)
    plan = build_archive_plan(tmp_path)

    inspection = inspect_safety(tmp_path, plan.entries[0].source, plan.entries[0].destination)
    result = apply_archive_plan(tmp_path, plan, [plan.entries[0]])

    assert "CROSS_DEVICE" in _codes(inspection.findings)
    assert result.refused
    assert source.exists()


def test_archive_consolidation_failure_restores_active_change(tmp_path: Path) -> None:
    active = tmp_path / ".local/.agent/active/rollback"
    active.mkdir(parents=True)
    (active / "STATUS.yaml").write_text(
        "schema_version: 1\nchange_id: rollback\nstate: VERIFYING\n"
        "last_updated: 2026-08-28T10:00:00Z\n",
        encoding="utf-8",
    )
    for name in ("goal.md", "checklist.md", "stage.md", "preflight.md", "spec.md"):
        (active / name).write_text("", encoding="utf-8")
    (active / "owned_files.txt").write_text("", encoding="utf-8")
    manager = ArchiveManager(store=ChangeStore(repo_root=tmp_path))

    def fail_consolidation(*args, **kwargs):
        raise ArchiveError("simulated consolidation failure")

    manager._consolidate_change_learnings = fail_consolidation

    with pytest.raises(ArchiveError, match="active change was retained"):
        manager.archive("rollback", archive_date="2026-08-28", auto_regenerate_reports=False)

    assert active.is_dir()
    assert not (tmp_path / ".local/.agent/archive/2026-08-28-rollback").exists()
    assert "state: VERIFYING" in (active / "STATUS.yaml").read_text(encoding="utf-8")


def test_ignored_review_note_outside_operation_scope_does_not_refuse(
    tmp_path: Path,
) -> None:
    source = _task(tmp_path, "first")
    (tmp_path / ".gitignore").write_text("code-review-notes.md\n", encoding="utf-8")
    (tmp_path / "code-review-notes.md").write_text("operator note", encoding="utf-8")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    entry = next(item for item in plan.entries if item.source.endswith("/first"))

    inspection = inspect_safety(tmp_path, entry.source, entry.destination)
    result = apply_archive_plan(tmp_path, plan, [entry])

    assert "UNTRACKED_REVIEW_NOTE" not in _codes(inspection.findings)
    assert inspection.safe
    assert result.success
    assert not source.exists()


def test_ignored_review_note_inside_moved_source_still_refuses(
    tmp_path: Path,
) -> None:
    source = _task(tmp_path, "second")
    (tmp_path / ".gitignore").write_text("scratch-review.md\n", encoding="utf-8")
    (source / "scratch-review.md").write_text("in-flight review", encoding="utf-8")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    entry = next(item for item in plan.entries if item.source.endswith("/second"))

    inspection = inspect_safety(tmp_path, entry.source, entry.destination)
    result = apply_archive_plan(tmp_path, plan, [entry])

    assert "UNTRACKED_REVIEW_NOTE" in _codes(inspection.findings)
    assert result.refused
    assert source.exists()


def test_archive_move_rolls_back_when_directory_flush_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / ".local/.agent/active/durable"
    active.mkdir(parents=True)
    (active / "STATUS.yaml").write_text(
        "schema_version: 1\nchange_id: durable\nstate: VERIFYING\n",
        encoding="utf-8",
    )
    store = ChangeStore(repo_root=tmp_path)
    calls = 0
    original_fsync = change_module._fsync_directory

    def fail_destination_flush(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated directory flush failure")
        original_fsync(path)

    monkeypatch.setattr(change_module, "_fsync_directory", fail_destination_flush)

    with pytest.raises(ChangeStoreError, match="rolled back"):
        store.move_to_archive("durable", archive_date="2026-08-28")

    assert active.is_dir()
    assert not (tmp_path / ".local/.agent/archive/2026-08-28-durable").exists()
