"""Focused tests for local-task archive contract diagnostics."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from devolaflow.cli import local_archive_cmd


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit(repo: Path, message: str) -> None:
    if not (repo / ".git").is_dir():
        _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=archive-doctor-test",
        "-c",
        "user.email=archive-doctor-test@example.invalid",
        "commit",
        "-qm",
        message,
    )


def _task(repo: Path, name: str = "task") -> Path:
    path = repo / ".local/tasks" / name
    path.mkdir(parents=True)
    (path / "task.yaml").write_text("status: done\ncluster: quality\n", encoding="utf-8")
    return path


def _invoke(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> pytest.ExceptionInfo[SystemExit]:
    monkeypatch.setattr(sys, "argv", ["devola-local-archive", *args])
    with pytest.raises(SystemExit) as exc_info:
        local_archive_cmd()
    return exc_info


def test_doctor_reports_duplicate_destinations_and_missing_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _task(tmp_path, "first")
    second = _task(tmp_path, "second")
    for path in (first, second):
        (path / "task.yaml").write_text(
            "status: done\ncluster: quality\nid: same\n", encoding="utf-8"
        )
    _commit(tmp_path, "doctor fixture")

    result = _invoke(monkeypatch, ["--repo-root", str(tmp_path), "doctor"])
    payload = json.loads(capsys.readouterr().out)
    codes = {finding["code"] for finding in payload["findings"]}

    assert result.value.code == 5
    assert payload["healthy"] is False
    assert {"DUPLICATE_DESTINATION", "INDEX_MISSING"} <= codes
    (second / "task.yaml").write_text(
        "status: done\ncluster: quality\nid: different\n", encoding="utf-8"
    )
    _commit(tmp_path, "remove duplicate")
    index = tmp_path / ".local/tasks/INDEX.md"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        "<!-- devolaflow: generated task archive index -->\n"
        "# Local task archive index\n\n"
        "- `.local/tasks/quality/archive/undated/wrong` ← `.local/tasks/wrong`\n",
        encoding="utf-8",
    )
    _commit(tmp_path, "stale index")

    result = _invoke(monkeypatch, ["--repo-root", str(tmp_path), "doctor"])
    payload = json.loads(capsys.readouterr().out)

    assert result.value.code == 3
    assert any(item["code"] == "INDEX_DRIFT" for item in payload["findings"])


def test_doctor_reports_protected_plan_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _task(tmp_path)
    _commit(tmp_path, "doctor fixture")
    plan_path = tmp_path / "protected-plan.json"
    plan_payload = {
        "artifact_type": "task-archive-plan",
        "schema_version": 1,
        "source_boundary": ".local/tasks",
        "entries": [
            {
                "source": ".local/tasks/task",
                "destination": ".local/tasks/quality/archive/undated/task",
                "cluster_key": "quality",
                "classification": "done",
                "action": "move",
                "protection": "protected",
                "protection_reason": "operator review",
                "findings": [],
            }
        ],
        "findings": [],
    }
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
    _commit(tmp_path, "protected plan")

    result = _invoke(
        monkeypatch,
        ["--repo-root", str(tmp_path), "doctor", "--plan", str(plan_path)],
    )
    payload = json.loads(capsys.readouterr().out)

    assert result.value.code == 3
    assert any(item["code"] == "PROTECTED_PATH" for item in payload["findings"])
    mapping = tmp_path / ".local/tasks/archive-mappings.yaml"
    mapping.write_text("sequence: nope\n", encoding="utf-8")
    _commit(tmp_path, "malformed mapping")

    result = _invoke(monkeypatch, ["--repo-root", str(tmp_path), "doctor"])
    payload = json.loads(capsys.readouterr().out)

    assert result.value.code == 5
    assert any(item["code"] == "MALFORMED_MAPPING" for item in payload["findings"])
