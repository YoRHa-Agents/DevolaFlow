"""Loop v3 subprocess coverage for hostbridge and the RTK shell proxy.

These tests exercise the public process boundaries with synthetic stdin,
stdout, stderr, and executable fake binaries.  They intentionally preserve
the live contracts: hostbridge failures fail open, while a missing or
unusable optional RTK binary degrades to shell passthrough.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from devolaflow.shell_proxy import ShellProxy, proxy_command

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_ENFORCE = "DEVOLAFLOW_HOST_ENFORCE"
RTK_PROXY = "DEVOLAFLOW_RTK_PROXY"
RTK_TIER2 = "DEVOLAFLOW_RTK_PROXY_TIER2"

pytestmark = [pytest.mark.functional, pytest.mark.fast]


def _active_repo(tmp_path: Path) -> Path:
    """Create one active change with a deliberately narrow owned set."""
    manifest = tmp_path / ".local" / ".agent" / "active" / "loop3-protocol"
    manifest.mkdir(parents=True)
    (manifest / "owned_files.txt").write_text("src/owned.py\n", encoding="utf-8")
    return tmp_path


def _hostbridge_process(
    repo: Path,
    host: str,
    payload: str,
    *,
    enforce: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run the source package with one synthetic host hook payload."""
    env = os.environ.copy()
    env[HOST_ENFORCE] = "1" if enforce else "0"
    source_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (source_path, env.get("PYTHONPATH", "")) if part
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "devolaflow.hostbridge",
            "--host",
            host,
            "--repo-root",
            str(repo),
        ],
        cwd=repo,
        env=env,
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def _write_fake_rtk(bin_dir: Path, body: str) -> Path:
    """Install an executable fake ``rtk`` whose body handles ``gain``."""
    binary = bin_dir / "rtk"
    binary.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return binary


def test_hostbridge_cursor_protocol_covers_deny_allow_and_malformed_stdin(
    tmp_path: Path,
) -> None:
    """Cursor consumes JSON stdout and always receives exit code zero."""
    repo = _active_repo(tmp_path)
    cases = (
        (
            json.dumps({"tool": "Write", "tool_input": {"path": "src/evil.py"}}),
            {"permission": "deny", "agent_message": "src/evil.py"},
        ),
        (
            json.dumps({"tool": "Write", "tool_input": {"path": "src/owned.py"}}),
            {"permission": "allow"},
        ),
        ("not-json", {"permission": "allow"}),
    )

    for payload, expected in cases:
        result = _hostbridge_process(repo, "cursor", payload)
        assert result.returncode == 0
        observed = json.loads(result.stdout)
        assert observed["permission"] == expected["permission"]
        if "agent_message" in expected:
            assert expected["agent_message"] in observed["agent_message"]
            assert "CFO006" in result.stderr
        else:
            assert result.stderr == ""

    ledger = repo / ".local" / "telemetry" / "hostbridge.jsonl"
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == len(cases)


def test_hostbridge_exit_code_hosts_use_stderr_for_required_protocol_denials(
    tmp_path: Path,
) -> None:
    """Claude, Codex, Kimi, and DSH use exit 2 plus stderr to block."""
    repo = _active_repo(tmp_path)
    deny_payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "src/evil.py"}})
    allow_payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "src/owned.py"}})

    for host in ("claude", "codex", "kimi", "dsh"):
        denied = _hostbridge_process(repo, host, deny_payload)
        assert denied.returncode == 2
        assert denied.stdout == ""
        assert "src/evil.py" in denied.stderr

        allowed = _hostbridge_process(repo, host, allow_payload)
        assert allowed.returncode == 0
        assert allowed.stdout == ""
        assert allowed.stderr == ""


def test_hostbridge_copilot_protocol_and_malformed_input_fail_open(tmp_path: Path) -> None:
    """Copilot receives its native JSON decision shape on stdout."""
    repo = _active_repo(tmp_path)
    denied = _hostbridge_process(
        repo,
        "copilot",
        json.dumps({"toolName": "edit", "toolArgs": {"file_path": "src/evil.py"}}),
    )
    assert denied.returncode == 0
    denied_payload = json.loads(denied.stdout)
    assert denied_payload["permissionDecision"] == "deny"
    assert "src/evil.py" in denied_payload["permissionDecisionReason"]

    malformed = _hostbridge_process(repo, "copilot", "{ malformed")
    assert malformed.returncode == 0
    assert json.loads(malformed.stdout) == {"permissionDecision": "allow"}


def test_hostbridge_flag_off_is_protocol_allow_without_audit(tmp_path: Path) -> None:
    """The disabled bridge keeps host protocol output and performs no audit."""
    result = _hostbridge_process(
        tmp_path,
        "cursor",
        json.dumps({"tool": "Write", "tool_input": {"path": "src/evil.py"}}),
        enforce=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"permission": "allow"}
    assert result.stderr == ""
    assert not (tmp_path / ".local" / "telemetry" / "hostbridge.jsonl").exists()


def test_shell_proxy_fake_rtk_success_and_malformed_output_still_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero exit code enables RTK; gain stdout is not a live contract."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    _write_fake_rtk(
        bin_dir,
        f'printf "%s\\n" "$*" > "{calls}"\nprintf "not a gain report" >&1',
    )
    monkeypatch.setenv("PATH", str(bin_dir))

    env = {RTK_PROXY: "1"}
    proxy = ShellProxy(env)
    assert proxy.config.proxy_enabled is True
    assert proxy.config.distinguish_passed is True
    assert proxy.wrap_command("pytest tests/ -q") == "rtk pytest tests/ -q"
    assert calls.read_text(encoding="utf-8").strip() == "gain"

    # The module only contracts on ``rtk gain``'s exit status, not its text.
    assert proxy_command("git status", env=env) == "rtk git status"


def test_shell_proxy_fake_rtk_nonzero_timeout_and_missing_degrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Optional RTK failures warn and preserve the original shell command."""
    env = {RTK_PROXY: "1"}
    command = "pytest tests/ -q"

    missing_bin = tmp_path / "missing-bin"
    missing_bin.mkdir()
    monkeypatch.setenv("PATH", str(missing_bin))
    missing = ShellProxy(env)
    assert missing.config.proxy_enabled is False
    assert missing.wrap_command(command) == command
    assert "binary not found on PATH" in missing.config.warnings[0]

    nonzero_bin = tmp_path / "nonzero-bin"
    nonzero_bin.mkdir()
    _write_fake_rtk(nonzero_bin, "printf 'wrong package\\n'; exit 7")
    monkeypatch.setenv("PATH", str(nonzero_bin))
    nonzero = ShellProxy(env)
    assert nonzero.config.proxy_enabled is False
    assert nonzero.wrap_command(command) == command
    assert "rtk gain exited 7" in (nonzero.config.distinguish_error or "")

    timeout_bin = tmp_path / "timeout-bin"
    timeout_bin.mkdir()
    _write_fake_rtk(timeout_bin, "exec /bin/sleep 2")
    monkeypatch.setenv("PATH", str(timeout_bin))
    monkeypatch.setattr(
        "devolaflow.shell_proxy.proxy._DISTINGUISH_TIMEOUT_SECONDS",
        0.05,
    )
    timed_out = ShellProxy(env)
    assert timed_out.config.proxy_enabled is False
    assert timed_out.wrap_command(command) == command
    assert "timed out" in (timed_out.config.distinguish_error or "")
    assert any("passthrough enabled" in record.message for record in caplog.records)


def test_shell_proxy_tier2_public_process_rewrite_requires_secondary_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real successful probe still honors the independent Tier 2 gate."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_rtk(bin_dir, "exit 0")
    monkeypatch.setenv("PATH", str(bin_dir))

    assert ShellProxy({RTK_PROXY: "1"}).wrap_command("make test") == "make test"
    assert ShellProxy({RTK_PROXY: "1", RTK_TIER2: "1"}).wrap_command("make test") == "rtk make test"
