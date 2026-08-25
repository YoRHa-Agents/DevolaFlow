"""Host-bridge suite — v17.0.0 R2 (G17-B1 closure, design §D-R2-1..§D-R2-4).

Covers ``devolaflow.hostbridge``: per-host stdin normalization (fixture
corpus under ``tests/fixtures/hostbridge/``), the S-8 owned-files
decision core (deny / allow / union / exemptions / fail-open), the
advisory-only shell path, the audit ledger, the per-host CLI response
protocols (ONE subprocess e2e for the cursor JSON protocol), and the
idempotent host-config installer whose output the committed dogfood
configs must match byte-for-byte.

The R5-strict flag-off contract lives in the companion module
``tests/test_hostbridge_disabled_is_noop.py`` (W-20 checklist step 3).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from devolaflow.hostbridge import install as hb_install
from devolaflow.hostbridge.__main__ import main as hb_main
from devolaflow.hostbridge.audit import AUDIT_LEDGER_RELPATH, CMD_SUMMARY_MAX_CHARS
from devolaflow.hostbridge.decision import (
    ENV_FLAG,
    VERDICT_ALLOW,
    VERDICT_DENY,
    VERDICT_ERROR_ALLOW,
    decide,
)
from devolaflow.hostbridge.normalize import BridgeEvent, normalize_event

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "hostbridge"


def _load_fixture_cases() -> list[pytest.param]:
    params: list[pytest.param] = []
    for fixture_path in sorted(_FIXTURE_DIR.glob("*.json")):
        spec = json.loads(fixture_path.read_text(encoding="utf-8"))
        for case in spec["cases"]:
            params.append(
                pytest.param(
                    spec["host"],
                    case,
                    id=f"{fixture_path.stem}-{case['name']}",
                )
            )
    return params


def _make_repo(tmp_path: Path, changes: dict[str, list[str]]) -> Path:
    for change_id, owned in changes.items():
        folder = tmp_path / ".local" / ".agent" / "active" / change_id
        folder.mkdir(parents=True)
        (folder / "owned_files.txt").write_text("\n".join(owned) + "\n", encoding="utf-8")
    return tmp_path


def _ledger_lines(repo: Path) -> list[dict]:
    ledger = repo / AUDIT_LEDGER_RELPATH
    assert ledger.is_file(), f"audit ledger missing: {ledger}"
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_FLAG, "1")


# ── normalization (fixture corpus — parametrize expansions are W-17-free) ──


@pytest.mark.parametrize(("host", "case"), _load_fixture_cases())
def test_normalize_fixture_shapes(host: str, case: dict) -> None:
    """Every documented per-host stdin spelling normalizes as pinned."""
    event = normalize_event(host, case["input"], event_override=case.get("event_override"))
    expected = case["expected"]
    assert event.host == host
    assert event.kind == expected["kind"]
    assert event.path == expected.get("path")
    assert event.command == expected.get("command")
    assert event.extra_paths == tuple(expected.get("extra_paths", []))


# ── decision core (flag ON) ─────────────────────────────────────────


def test_decide_allows_when_no_active_change(tmp_path: Path, enforced: None) -> None:
    event = BridgeEvent(host="cursor", kind="file_write", path="src/anything.py")
    decision = decide(event, tmp_path)
    assert decision.allow is True
    assert decision.verdict == VERDICT_ALLOW
    assert "no active change" in decision.reason
    assert _ledger_lines(tmp_path)[0]["verdict"] == VERDICT_ALLOW


def test_decide_denies_unowned_write_quoting_path_and_change_id(
    tmp_path: Path, enforced: None
) -> None:
    repo = _make_repo(tmp_path, {"r2-demo": ["src/owned.py"]})
    decision = decide(BridgeEvent(host="cursor", kind="file_write", path="src/evil.py"), repo)
    assert decision.allow is False
    assert decision.verdict == VERDICT_DENY
    assert "src/evil.py" in decision.reason
    assert "r2-demo" in decision.reason
    assert "CFO006" in decision.reason
    (record,) = _ledger_lines(repo)
    assert record["verdict"] == VERDICT_DENY
    assert record["active_changes"] == ["r2-demo"]
    # Ledger schema pin (host-bridges.md §6).
    assert {"ts", "host", "kind", "path", "verdict", "reason", "elapsed_ms"} <= set(record)


@pytest.mark.parametrize(
    "target",
    [
        "src/owned.py",  # S-8 §1: owned_files manifest entry
        ".local/.agent/active/r2-demo/notes.md",  # S-8 §2: change folder itself
        ".local/.agent/handoff/l2__l1__r2-demo__1.yaml",  # S-8 §3: handoff outbox
    ],
)
def test_decide_allows_owned_write_and_s8_exemptions(
    tmp_path: Path, enforced: None, target: str
) -> None:
    repo = _make_repo(tmp_path, {"r2-demo": ["src/owned.py"]})
    decision = decide(BridgeEvent(host="claude", kind="file_write", path=target), repo)
    assert decision.allow is True, decision.reason
    assert decision.verdict == VERDICT_ALLOW


def test_decide_unions_multiple_active_changes(tmp_path: Path, enforced: None) -> None:
    repo = _make_repo(tmp_path, {"change-a": ["src/a.py"], "change-b": ["src/b.py"]})
    decision = decide(BridgeEvent(host="codex", kind="file_write", path="src/b.py"), repo)
    assert decision.allow is True, decision.reason
    assert decision.audit["active_changes"] == ["change-a", "change-b"]
    denied = decide(BridgeEvent(host="codex", kind="file_write", path="src/c.py"), repo)
    assert denied.allow is False
    assert "change-a" in denied.reason and "change-b" in denied.reason


def test_decide_checks_every_apply_patch_target(tmp_path: Path, enforced: None) -> None:
    repo = _make_repo(tmp_path, {"r2-demo": ["src/a.py"]})
    event = BridgeEvent(
        host="codex", kind="file_write", path="src/a.py", extra_paths=("src/rogue.py",)
    )
    decision = decide(event, repo)
    assert decision.allow is False
    assert "src/rogue.py" in decision.reason


def test_decide_shell_is_advisory_allow_with_metadata(tmp_path: Path, enforced: None) -> None:
    long_cmd = "echo " + "x" * 300
    decision = decide(BridgeEvent(host="dsh", kind="shell", command=long_cmd), tmp_path)
    assert decision.allow is True
    assert decision.verdict == VERDICT_ALLOW
    (record,) = _ledger_lines(tmp_path)
    advisory = record["shell_advisory"]
    assert advisory["wrapped_cmd"] == long_cmd
    assert advisory["proxy_enabled"] is False
    assert advisory["was_rewritten"] is False
    assert len(record["cmd"]) == CMD_SUMMARY_MAX_CHARS  # 120-char summary cap


def test_decide_shell_advisory_error_is_swallowed_and_ledgered(
    tmp_path: Path, enforced: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(payload: dict, *, strict: bool = False) -> None:
        raise RuntimeError("advisory machinery unavailable")

    monkeypatch.setattr("devolaflow.lifecycle.pre_shell_call", _boom)
    decision = decide(BridgeEvent(host="kimi", kind="shell", command="ls"), tmp_path)
    assert decision.allow is True
    assert decision.verdict == VERDICT_ALLOW  # advisory failure never blocks
    (record,) = _ledger_lines(tmp_path)
    assert "advisory machinery unavailable" in record["shell_advisory_error"]


def test_decide_internal_error_fails_open_as_error_allow(
    tmp_path: Path, enforced: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "devolaflow.hostbridge.decision._discover_active_changes",
        lambda repo_root: (_ for _ in ()).throw(OSError("manifest scan exploded")),
    )
    decision = decide(BridgeEvent(host="cursor", kind="file_write", path="src/x.py"), tmp_path)
    assert decision.allow is True
    assert decision.verdict == VERDICT_ERROR_ALLOW
    (record,) = _ledger_lines(tmp_path)
    assert record["verdict"] == VERDICT_ERROR_ALLOW
    assert "manifest scan exploded" in record["error"]


def test_decide_unknown_kind_allows_and_audits(tmp_path: Path, enforced: None) -> None:
    decision = decide(BridgeEvent(host="cursor", kind="unknown"), tmp_path)
    assert decision.allow is True
    assert "fail-open" in decision.reason
    assert _ledger_lines(tmp_path)[0]["kind"] == "unknown"


# ── CLI response protocols ──────────────────────────────────────────


def test_cli_e2e_cursor_subprocess(tmp_path: Path) -> None:
    """THE e2e: real subprocess, real stdin fixture, tmp repo, flag on."""
    repo = _make_repo(tmp_path, {"r2-demo": ["src/owned.py"]})
    env = {**os.environ, ENV_FLAG: "1"}

    def run(stdin_text: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "devolaflow.hostbridge", "--host", "cursor"],
            input=stdin_text,
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    # Deny leg drives the REAL fixture corpus shape (path-key precedence
    # case writes to src/demo.py, which the tmp change does not own).
    fixture = json.loads((_FIXTURE_DIR / "cursor.json").read_text(encoding="utf-8"))
    deny_input = fixture["cases"][0]["input"]
    deny = run(json.dumps(deny_input))
    assert deny.returncode == 0
    verdict = json.loads(deny.stdout)
    assert verdict["permission"] == "deny"
    assert "src/demo.py" in verdict["agent_message"]
    assert "r2-demo" in verdict["agent_message"]

    allow = run(json.dumps({"tool": "Write", "tool_input": {"path": "src/owned.py"}}))
    assert allow.returncode == 0
    assert json.loads(allow.stdout) == {"permission": "allow"}

    malformed = run("this is not json {{{")
    assert malformed.returncode == 0
    assert json.loads(malformed.stdout) == {"permission": "allow"}

    assert [line["verdict"] for line in _ledger_lines(repo)] == ["deny", "allow", "allow"]


def test_cli_exit_code_hosts_and_cursor_json(
    tmp_path: Path,
    enforced: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_repo(tmp_path, {"r2-demo": ["src/owned.py"]})
    deny_payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "src/evil.py"}})
    allow_payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "src/owned.py"}})
    argv_tail = ["--repo-root", str(repo)]

    for host in ("claude", "codex", "kimi", "dsh"):
        monkeypatch.setattr("sys.stdin", io.StringIO(deny_payload))
        assert hb_main(["--host", host, *argv_tail]) == 2
        captured = capsys.readouterr()
        assert "src/evil.py" in captured.err and captured.out == ""

        monkeypatch.setattr("sys.stdin", io.StringIO(allow_payload))
        assert hb_main(["--host", host, *argv_tail]) == 0
        captured = capsys.readouterr()
        assert captured.out == "" and captured.err == ""

    # Cursor speaks stdout JSON and ALWAYS exits 0.
    monkeypatch.setattr("sys.stdin", io.StringIO(deny_payload))
    assert hb_main(["--host", "cursor", *argv_tail]) == 0
    assert json.loads(capsys.readouterr().out)["permission"] == "deny"

    monkeypatch.setattr("sys.stdin", io.StringIO(allow_payload))
    assert hb_main(["--host", "cursor", *argv_tail]) == 0
    assert json.loads(capsys.readouterr().out) == {"permission": "allow"}

    # Unparseable argv MUST fail open (exit 0, conservative allow JSON).
    assert hb_main(["--host", "not-a-host"]) == 0
    assert json.loads(capsys.readouterr().out) == {"permission": "allow"}


# ── installer + dogfood parity ──────────────────────────────────────


def test_install_generates_host_configs_idempotently(tmp_path: Path) -> None:
    foreign_settings = {
        "model": "opus",
        "hooks": {
            "PreToolUse": [
                {"matcher": "WebFetch", "hooks": [{"type": "command", "command": "echo hi"}]}
            ]
        },
    }
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps(foreign_settings), encoding="utf-8")

    first = {
        **hb_install.install_cursor(tmp_path),
        **hb_install.install_claude(tmp_path),
        **hb_install.install_codex(tmp_path),
    }
    assert all(status == "written" for status in first.values()), first

    second = {
        **hb_install.install_cursor(tmp_path),
        **hb_install.install_claude(tmp_path),
        **hb_install.install_codex(tmp_path),
    }
    assert all(status == "unchanged" for status in second.values()), second

    for rel in (".cursor/hooks.json", ".codex/hooks.json", ".claude/settings.json"):
        json.loads((tmp_path / rel).read_text(encoding="utf-8"))  # valid JSON
    for rel in (
        ".cursor/hooks/devola-boundary.sh",
        ".claude/hooks/devola-boundary.sh",
        ".codex/hooks/devola-boundary.sh",
    ):
        script = tmp_path / rel
        assert os.access(script, os.X_OK), f"{rel} must be executable"
        text = script.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert '"$DEVOLAFLOW_HOST_ENFORCE" != "1"' in text  # pure-bash fast path
        assert "failClosed" not in text

    # v17 R4 session scripts gate on the WORKSPACE flag (W-20 reuse),
    # never on the boundary-enforcement flag.
    for rel in (
        ".cursor/hooks/devola-session.sh",
        ".claude/hooks/devola-session.sh",
    ):
        script = tmp_path / rel
        assert os.access(script, os.X_OK), f"{rel} must be executable"
        text = script.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert '"$DEVOLAFLOW_AGENT_WORKSPACE" != "1"' in text  # pure-bash fast path
        assert "DEVOLAFLOW_HOST_ENFORCE" not in text
        assert "hostbridge resume" in text

    # Claude merge is ADDITIVE: foreign keys + foreign hook entries survive.
    merged = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert merged["model"] == "opus"
    matchers = [entry["matcher"] for entry in merged["hooks"]["PreToolUse"]]
    assert matchers == ["WebFetch", "Edit|Write|MultiEdit", "Bash"]
    session_matchers = [entry["matcher"] for entry in merged["hooks"]["SessionStart"]]
    assert session_matchers == ["startup|resume"]

    # Cursor hooks.json carries the sessionStart entry (v17 R4).
    cursor_hooks = json.loads((tmp_path / ".cursor/hooks.json").read_text(encoding="utf-8"))
    assert cursor_hooks["hooks"]["sessionStart"] == [{"command": ".cursor/hooks/devola-session.sh"}]


def test_install_kimi_prints_toml_snippet(capsys: pytest.CaptureFixture[str]) -> None:
    assert hb_main(["install", "kimi"]) == 0
    out = capsys.readouterr().out
    assert "[[hooks]]" in out
    assert 'event = "PreToolUse"' in out
    assert 'matcher = "WriteFile|StrReplaceFile|Shell"' in out
    assert "python3 -m devolaflow.hostbridge --host kimi" in out


def test_committed_dogfood_configs_match_installer_output(project_root: Path) -> None:
    """§D-R2-3: the committed host configs ARE the installer's output."""
    read = lambda rel: (project_root / rel).read_text(encoding="utf-8")  # noqa: E731
    assert read(".cursor/hooks.json") == hb_install._render_cursor_hooks_json()
    assert read(".codex/hooks.json") == hb_install._render_codex_hooks_json()
    for host, rel in (
        ("cursor", ".cursor/hooks/devola-boundary.sh"),
        ("claude", ".claude/hooks/devola-boundary.sh"),
        ("codex", ".codex/hooks/devola-boundary.sh"),
    ):
        assert read(rel) == hb_install._render_boundary_script(host)
    for host, rel in (
        ("cursor", ".cursor/hooks/devola-session.sh"),
        ("claude", ".claude/hooks/devola-session.sh"),
    ):
        assert read(rel) == hb_install._render_session_script(host)
    committed_claude = read(".claude/settings.json")
    assert hb_install._merge_claude_settings(committed_claude) == committed_claude
