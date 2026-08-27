"""Focused tests for the explicit local-task archive console command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from devolaflow.cli import LOCAL_ARCHIVE_SAFETY_REFUSAL, local_archive_cmd


def _task(repo: Path, relative: str = ".local/tasks/flat-done") -> Path:
    path = repo / relative
    path.mkdir(parents=True)
    (path / "task.yaml").write_text("status: done\ncluster: quality\n", encoding="utf-8")
    (path / "context.txt").write_text("preserve me\n", encoding="utf-8")
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _clean_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=archive-cli-test",
            "-c",
            "user.email=archive-cli-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _invoke(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> pytest.ExceptionInfo[SystemExit]:
    monkeypatch.setattr(sys, "argv", ["devola-local-archive", *args])
    with pytest.raises(SystemExit) as exc_info:
        local_archive_cmd()
    return exc_info


def test_default_invocation_is_report_only_and_zero_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    help_result = _invoke(monkeypatch, ["--help"])
    help_output = capsys.readouterr()

    assert help_result.value.code == 0
    assert "devola-local-archive" in help_output.out
    assert "--apply PLAN" in help_output.out

    _task(tmp_path)
    before = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    result = _invoke(monkeypatch, ["--repo-root", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)
    after = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )

    assert result.value.code == 0
    assert report["artifact_type"] == "task-archive-plan"
    assert report["entries"][0]["action"] == "move"
    assert before == after
    assert not (tmp_path / ".local/tasks/INDEX.md").exists()
    assert not (tmp_path / ".local/tasks/archive-mappings.yaml").exists()


def test_apply_uses_approved_plan_and_moves_only_its_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _task(tmp_path)
    _clean_repo(tmp_path)
    _invoke(monkeypatch, ["--repo-root", str(tmp_path)])
    plan_payload = json.loads(capsys.readouterr().out)
    plan_path = tmp_path / "approved-plan.json"
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
    _git(tmp_path, "add", plan_path.name)
    _git(
        tmp_path,
        "-c",
        "user.name=archive-cli-test",
        "-c",
        "user.email=archive-cli-test@example.invalid",
        "commit",
        "-qm",
        "approved plan",
    )

    result = _invoke(monkeypatch, ["--repo-root", str(tmp_path), "--apply", str(plan_path)])
    payload = json.loads(capsys.readouterr().out)

    assert result.value.code == 0
    assert payload["success"] is True
    destination = tmp_path / ".local/tasks/quality/archive/undated/flat-done"
    assert not source.exists()
    assert destination.joinpath("context.txt").read_text(encoding="utf-8") == "preserve me\n"
    assert (tmp_path / ".local/tasks/archive-mappings.yaml").is_file()


@pytest.mark.parametrize(
    "finding_code",
    ["APPLY_ERROR", "INDEX_WRITE_ERROR", "NOT_MOVABLE", "SYMLINK_INDEX", "UNREADABLE_INDEX"],
)
def test_apply_failed_findings_return_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    finding_code: str,
) -> None:
    from devolaflow.local.archive import ArchiveResult, Finding

    plan = SimpleNamespace(entries=(SimpleNamespace(action="move"),))
    monkeypatch.setattr("devolaflow.cli._local_archive_load_plan", lambda _: plan)

    def fake_apply(root: Path, loaded_plan: object, approved: object) -> ArchiveResult:
        assert loaded_plan is plan
        assert len(approved) == 1
        return ArchiveResult(
            findings=(Finding(finding_code, "simulated archive failure"),),
            refused=True,
        )

    monkeypatch.setattr("devolaflow.local.archive.apply_archive_plan", fake_apply)

    result = _invoke(
        monkeypatch,
        ["--repo-root", str(tmp_path), "--apply", str(tmp_path / "approved-plan.json")],
    )
    payload = json.loads(capsys.readouterr().out)

    assert result.value.code == LOCAL_ARCHIVE_SAFETY_REFUSAL
    assert payload["findings"][0]["code"] == finding_code
    assert payload["refused"] is True
    assert payload["success"] is False


def test_apply_rejects_malformed_and_changed_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _task(tmp_path)
    _clean_repo(tmp_path)
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{broken", encoding="utf-8")

    malformed_result = _invoke(
        monkeypatch, ["--repo-root", str(tmp_path), "--apply", str(malformed)]
    )
    malformed_payload = json.loads(capsys.readouterr().out)
    assert malformed_result.value.code == 2
    assert malformed_payload["findings"][0]["code"] == "MALFORMED_PLAN"

    _invoke(monkeypatch, ["--repo-root", str(tmp_path)])
    plan_payload = json.loads(capsys.readouterr().out)
    plan_path = tmp_path / "changed-plan.json"
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
    _git(tmp_path, "add", plan_path.name)
    _git(
        tmp_path,
        "-c",
        "user.name=archive-cli-test",
        "-c",
        "user.email=archive-cli-test@example.invalid",
        "commit",
        "-qm",
        "changed plan",
    )
    (source / "task.yaml").write_text("status: active\ncluster: quality\n", encoding="utf-8")

    changed_result = _invoke(monkeypatch, ["--repo-root", str(tmp_path), "--apply", str(plan_path)])
    changed_payload = json.loads(capsys.readouterr().out)
    assert changed_result.value.code == 4
    assert any(item["code"] == "PLAN_CHANGED" for item in changed_payload["findings"])
    assert source.is_dir()


def test_deletion_request_is_rejected_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _task(tmp_path)

    result = _invoke(monkeypatch, ["--repo-root", str(tmp_path), "--delete"])

    assert result.value.code == 2
    assert source.is_dir()
    assert "--delete" in capsys.readouterr().err
