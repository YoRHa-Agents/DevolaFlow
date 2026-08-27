"""Focused tests for the explicit local-task archive owner."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import devolaflow.local.archive as archive_module
from devolaflow.local.archive import (
    ArchivePlan,
    Lifecycle,
    ProtectionVerdict,
    TaskRecord,
    append_mapping_record,
    apply_archive_plan,
    build_archive_plan,
    inspect_safety,
    inventory_tasks,
    render_index,
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
            "user.name=archive-test",
            "-c",
            "user.email=archive-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repo,
        check=True,
    )


def _task(
    repo: Path,
    relative: str,
    *,
    status: str | None = None,
    cluster: str | None = None,
) -> Path:
    path = repo / relative
    path.mkdir(parents=True, exist_ok=True)
    if status is not None:
        lines = [f"status: {status}"]
        if cluster is not None:
            lines.append(f"cluster: {cluster}")
        (path / "task.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (path / "context.txt").write_text("task context\n", encoding="utf-8")
    return path


def _codes(findings) -> set[str]:
    return {finding.code for finding in findings}


def test_inventory_reads_canonical_and_brownfield_layouts(tmp_path: Path) -> None:
    canonical = _task(tmp_path, ".local/tasks/quality/active/T-active", status="active")
    archived = _task(
        tmp_path,
        ".local/tasks/quality/archive/2026-08/T-done",
        status="done",
    )
    flat = _task(tmp_path, ".local/tasks/legacy-task", status="stale", cluster="legacy")

    records = inventory_tasks(tmp_path)

    assert [record.source for record in records] == [
        ".local/tasks/legacy-task",
        ".local/tasks/quality/active/T-active",
        ".local/tasks/quality/archive/2026-08/T-done",
    ]
    assert canonical.is_dir() and archived.is_dir() and flat.is_dir()
    assert records[0].layout == "flat"
    assert records[1].layout == "canonical-active"
    assert records[2].layout == "canonical-archive"
    missing = _task(tmp_path, ".local/tasks/missing")
    malformed = _task(tmp_path, ".local/tasks/malformed")
    (malformed / "task.yaml").write_text("status: [\n", encoding="utf-8")

    records = inventory_tasks(tmp_path)

    by_source = {record.source: record for record in records}
    assert by_source[".local/tasks/missing"].lifecycle is Lifecycle.UNKNOWN
    assert by_source[".local/tasks/malformed"].lifecycle is Lifecycle.UNKNOWN
    assert "MISSING_METADATA" in _codes(by_source[".local/tasks/missing"].findings)
    assert "MALFORMED_METADATA" in _codes(by_source[".local/tasks/malformed"].findings)
    assert missing.name == "missing"


@pytest.mark.parametrize("value", ["active", "done", "stale", "unknown"])
def test_lifecycle_enum_accepts_exact_values(tmp_path: Path, value: str) -> None:
    _task(tmp_path, f".local/tasks/{value}", status=value)

    record = inventory_tasks(tmp_path)[0]

    assert record.lifecycle.value == value
    assert record.lifecycle.value in {"active", "done", "stale", "unknown"}


def test_protection_is_separate_from_lifecycle(tmp_path: Path) -> None:
    _task(tmp_path, ".local/tasks/quality/active/protected", status="active")
    record = inventory_tasks(tmp_path)[0]

    assert record.lifecycle is Lifecycle.ACTIVE
    assert record.protection is ProtectionVerdict.ALLOWED
    assert record.protected is False
    outside = inspect_safety(tmp_path, ".local/.agent/active/change")
    assert outside.safe is False
    assert "PROTECTED_PATH" in _codes(outside.findings)


def test_report_only_plan_performs_zero_writes(tmp_path: Path) -> None:
    _task(tmp_path, ".local/tasks/flat-done", status="done")
    before = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    plan = build_archive_plan(tmp_path)

    after = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert plan.entries[0].action == "move"
    assert before == after
    assert not (tmp_path / ".local/tasks/archive-mappings.yaml").exists()


def test_plan_and_index_are_deterministic(tmp_path: Path) -> None:
    _task(tmp_path, ".local/tasks/z", status="done", cluster="zeta")
    _task(tmp_path, ".local/tasks/a", status="active", cluster="alpha")

    first = build_archive_plan(tmp_path)
    second = build_archive_plan(tmp_path)

    assert first == second
    assert first.fingerprint == second.fingerprint
    assert render_index(first) == render_index(second)
    assert all(not Path(entry.source).is_absolute() for entry in first.entries)
    assert all("/" in entry.destination for entry in first.entries)


def test_apply_refusals_cover_approval_and_existing_artifacts(tmp_path: Path) -> None:
    _task(tmp_path, ".local/tasks/done", status="done")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)

    required = apply_archive_plan(tmp_path, plan)
    mismatch = apply_archive_plan(tmp_path, plan, [".local/tasks/not-in-plan"])
    (tmp_path / ".local/tasks/INDEX.md").write_text("# human index\n", encoding="utf-8")
    human_result = apply_archive_plan(tmp_path, plan, [plan.entries[0]])
    (tmp_path / ".local/tasks/INDEX.md").unlink()
    (tmp_path / ".local/tasks/archive-mappings.yaml").write_text("[broken\n", encoding="utf-8")
    malformed_result = apply_archive_plan(tmp_path, plan, [plan.entries[0]])

    assert required.refused and "APPROVAL_REQUIRED" in _codes(required.findings)
    assert mismatch.refused and "APPROVAL_MISMATCH" in _codes(mismatch.findings)
    assert human_result.refused and "HUMAN_INDEX" in _codes(human_result.findings)
    assert malformed_result.refused and "MALFORMED_MAPPING" in _codes(malformed_result.findings)
    assert (tmp_path / ".local/tasks/done").is_dir()


def test_approved_move_preserves_contents_and_writes_mapping(tmp_path: Path) -> None:
    source = _task(tmp_path, ".local/tasks/flat-done", status="done", cluster="quality")
    other = _task(tmp_path, ".local/tasks/other-done", status="done", cluster="quality")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    entry = next(item for item in plan.entries if item.source == ".local/tasks/flat-done")

    result = apply_archive_plan(tmp_path, plan, [entry])

    assert result.success
    assert not source.exists()
    assert other.exists()
    destination = tmp_path / entry.destination
    assert destination.joinpath("context.txt").read_text(encoding="utf-8") == "task context\n"
    assert result.mappings[0].sequence == 1
    assert (
        (tmp_path / ".local/tasks/INDEX.md")
        .read_text(encoding="utf-8")
        .startswith("<!-- devolaflow: generated")
    )


def test_plan_change_refuses_after_source_metadata_changes(tmp_path: Path) -> None:
    source = _task(tmp_path, ".local/tasks/change-me", status="done")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    (source / "task.yaml").write_text("status: active\n", encoding="utf-8")

    result = apply_archive_plan(tmp_path, plan, [plan.entries[0]])

    assert result.refused
    assert "PLAN_CHANGED" in _codes(result.findings)
    assert source.exists()
    (source / "task.yaml").write_text("status: done\n", encoding="utf-8")
    (tmp_path / "review-note.md").write_text("review\n", encoding="utf-8")

    inspection = inspect_safety(tmp_path, plan.entries[0].source, plan.entries[0].destination)
    dirty_result = apply_archive_plan(tmp_path, plan, [plan.entries[0]])

    assert not inspection.safe
    assert "DIRTY_TREE" in _codes(inspection.findings)
    assert dirty_result.refused
    assert source.exists()


def test_symlink_and_traversal_are_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    tasks = tmp_path / ".local/tasks"
    tasks.mkdir(parents=True)
    (tasks / "link").symlink_to(outside, target_is_directory=True)

    records = inventory_tasks(tmp_path)
    traversal = inspect_safety(tmp_path, "../outside")

    assert records[0].protection is ProtectionVerdict.UNSAFE
    assert "PATH_TRAVERSAL" in _codes(traversal.findings)
    assert "SYMLINK_PATH" in _codes(records[0].findings)


def test_nested_repository_refuses_action(tmp_path: Path) -> None:
    source = _task(tmp_path, ".local/tasks/nested", status="done")
    (source / ".git").mkdir()
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)

    inspection = inspect_safety(tmp_path, plan.entries[0].source, plan.entries[0].destination)

    assert not inspection.safe
    assert "NESTED_REPOSITORY" in _codes(inspection.findings)


def test_worktree_registry_refuses_ambiguous_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _task(tmp_path, ".local/tasks/worktree", status="done")
    _clean_repo(tmp_path)
    original = archive_module._run_git

    def fake_run_git(root: Path, args: list[str]):
        if args == ["worktree", "list", "--porcelain"]:
            return f"worktree {tmp_path / '.local'}\n", None
        return original(root, args)

    monkeypatch.setattr(archive_module, "_run_git", fake_run_git)
    plan = build_archive_plan(tmp_path)
    inspection = inspect_safety(tmp_path, plan.entries[0].source, plan.entries[0].destination)

    assert source.exists()
    assert not inspection.safe
    assert "WORKTREE_REGISTRY" in _codes(inspection.findings)


def test_duplicate_destinations_are_refusal_findings(tmp_path: Path) -> None:
    records = (
        TaskRecord(
            source=".local/tasks/a",
            task_id="same",
            cluster_key="cluster",
            layout="flat",
            lifecycle=Lifecycle.DONE,
            protection=ProtectionVerdict.ALLOWED,
            protection_reason="",
        ),
        TaskRecord(
            source=".local/tasks/b",
            task_id="same",
            cluster_key="cluster",
            layout="flat",
            lifecycle=Lifecycle.DONE,
            protection=ProtectionVerdict.ALLOWED,
            protection_reason="",
        ),
    )

    plan = build_archive_plan(tmp_path, records=records)

    assert "DUPLICATE_DESTINATION" in _codes(plan.findings)
    assert all(entry.action == "refuse" for entry in plan.entries)


def test_unknown_candidates_cannot_be_deleted(tmp_path: Path) -> None:
    _task(tmp_path, ".local/tasks/unknown")
    plan = build_archive_plan(tmp_path)

    assert plan.entries[0].classification == "unknown"
    assert plan.entries[0].action == "review"
    assert "delete" not in {entry.action for entry in plan.entries}


def test_mapping_append_only_and_no_clobber(tmp_path: Path) -> None:
    first = append_mapping_record(
        tmp_path,
        ".local/tasks/a",
        ".local/tasks/archive/a",
        "first",
        timestamp="2026-08-27T10:00:00Z",
    )
    ledger = tmp_path / ".local/tasks/archive-mappings.yaml"
    before = ledger.read_bytes()
    second = append_mapping_record(
        tmp_path,
        ".local/tasks/b",
        ".local/tasks/archive/b",
        "second",
        timestamp="2026-08-27T10:01:00Z",
    )

    assert first.sequence == 1 and second.sequence == 2
    assert ledger.read_bytes().startswith(before)
    with pytest.raises(RuntimeError, match="refusing duplicate"):
        append_mapping_record(tmp_path, ".local/tasks/a", ".local/tasks/archive/c", "duplicate")


def test_archive_plan_dataclass_can_be_approved_as_subset(tmp_path: Path) -> None:
    _task(tmp_path, ".local/tasks/done", status="done")
    _clean_repo(tmp_path)
    plan = build_archive_plan(tmp_path)
    approval = ArchivePlan(entries=(plan.entries[0],))

    result = apply_archive_plan(tmp_path, plan, approval)

    assert result.success
