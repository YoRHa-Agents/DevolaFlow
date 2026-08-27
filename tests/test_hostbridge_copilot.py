"""Copilot command-hook protocol tests."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from devolaflow.hostbridge.__main__ import main as hb_main
from devolaflow.hostbridge.install import (
    _render_copilot_boundary_script,
    _render_copilot_hooks_json,
    install_copilot,
)


def _make_repo(tmp_path: Path) -> Path:
    active = tmp_path / ".local/.agent/active/copilot-smoke"
    active.mkdir(parents=True)
    (active / "owned_files.txt").write_text("src/owned.py\n", encoding="utf-8")
    return tmp_path


def _run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: str,
    repo: Path,
    *,
    extra_args: list[str] | None = None,
) -> tuple[int, dict[str, str]]:
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    args = ["--host", "copilot", "--repo-root", str(repo), *(extra_args or [])]
    code = hb_main(args)
    output = json.loads(capsys.readouterr().out)
    return code, output


def test_copilot_allow_and_deny_are_stdout_json_and_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DEVOLAFLOW_HOST_ENFORCE", "1")
    repo = _make_repo(tmp_path)
    deny_code, deny = _run(
        monkeypatch,
        capsys,
        json.dumps({"toolName": "edit", "toolArgs": {"file_path": "src/evil.py"}}),
        repo,
    )
    assert deny_code == 0
    assert deny["permissionDecision"] == "deny"
    assert "src/evil.py" in deny["permissionDecisionReason"]

    allow_code, allow = _run(
        monkeypatch,
        capsys,
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": "src/owned.py"}}),
        repo,
    )
    assert allow_code == 0
    assert allow == {"permissionDecision": "allow"}


def test_copilot_malformed_stdin_fails_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, output = _run(monkeypatch, capsys, "{not json", tmp_path)
    assert code == 0
    assert output == {"permissionDecision": "allow"}


def test_copilot_internal_error_fails_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "devolaflow.hostbridge.__main__.decide",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    code, output = _run(
        monkeypatch,
        capsys,
        json.dumps({"toolName": "edit", "toolArgs": {"file_path": "src/evil.py"}}),
        tmp_path,
    )
    assert code == 0
    assert output == {"permissionDecision": "allow"}


def test_copilot_installer_is_idempotent(tmp_path: Path) -> None:
    first = install_copilot(tmp_path)
    second = install_copilot(tmp_path)
    assert all(status == "written" for status in first.values())
    assert all(status == "unchanged" for status in second.values())
    assert json.loads(_render_copilot_hooks_json())["hooks"]["preToolUse"]
    assert _render_copilot_boundary_script().startswith("#!/usr/bin/env bash")
