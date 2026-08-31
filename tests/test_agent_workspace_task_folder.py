"""Coverage for direct ``.local/tasks/<task-name>/`` workspace folders."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.agent_workspace import (
    TaskFolderError,
    lint_change,
    lint_task,
    scaffold_task_folder,
)
from devolaflow.agent_workspace.lint import main as lint_main
from devolaflow.local.workspace import scaffold_task_folder as local_scaffold_task_folder
from devolaflow.skills.slash_commands import scaffold_change_folder


def test_task_lint_missing_entrance_fails(tmp_path: Path) -> None:
    folder = scaffold_task_folder("missing-entrance", tmp_path)
    (folder / "entrance.md").unlink()

    report = lint_task("missing-entrance", repo_root=tmp_path)

    assert report.exit_code == 1
    assert [finding.kind for finding in report.hard_failures if hasattr(finding, "kind")] == [
        "ENTRANCE_MISSING"
    ]
    assert report.hard_failures[0].severity == "FAIL"


def test_complete_task_scaffold_passes_and_materializes_inventory(tmp_path: Path) -> None:
    folder = local_scaffold_task_folder("complete-task", tmp_path, title="Complete task")

    assert folder == tmp_path / ".local" / "tasks" / "complete-task"
    for artifact in (
        "entrance.md",
        "goal.md",
        "checklist.md",
        "stage.md",
        "preflight.md",
        "spec.md",
        "STATUS.yaml",
        "owned_files.txt",
    ):
        assert (folder / artifact).is_file()
    assert (folder / "evidence").is_dir()

    report = lint_task("complete-task", repo_root=tmp_path)

    assert report.exit_code == 0, [
        finding.render(report.change_id) for finding in report.violations
    ]
    assert not report.hard_failures


def test_lint_change_keeps_active_behavior_and_finds_task_fallback(tmp_path: Path) -> None:
    active = scaffold_change_folder("active compatibility", tmp_path)
    assert lint_change(active.name, repo_root=tmp_path).change_folder == active

    task = scaffold_task_folder("task-fallback", tmp_path)
    report = lint_change(task.name, repo_root=tmp_path)
    assert report.exit_code == 0
    assert report.change_folder == task


def test_task_lint_cli_selects_task_surface(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold_task_folder("cli-task", tmp_path)

    assert lint_main(["--repo-root", str(tmp_path), "--task", "cli-task"]) == 0
    assert "cli-task/goal.md" in capsys.readouterr().err


@pytest.mark.parametrize(
    "unsafe_name", ["/tmp/outside", "../escape", "nested/task", ".", "..", "Bad"]
)
def test_task_scaffold_rejects_unsafe_names(tmp_path: Path, unsafe_name: str) -> None:
    with pytest.raises(TaskFolderError):
        scaffold_task_folder(unsafe_name, tmp_path)

    assert not (tmp_path / ".local" / "tasks").exists()


def test_task_lint_rejects_symlinked_folder(tmp_path: Path) -> None:
    tasks_root = tmp_path / ".local" / "tasks"
    tasks_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tasks_root / "linked-task").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="must not be a symlink"):
        lint_task("linked-task", repo_root=tmp_path)
