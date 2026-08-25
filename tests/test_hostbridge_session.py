"""Session-start resume adapter suite — v17.0.0 R4 (design §D-R4-1).

Covers ``python -m devolaflow.hostbridge resume``: the R5-strict
``DEVOLAFLOW_AGENT_WORKSPACE`` gate (W-20 REUSE — zero filesystem IO
when off), the three active-change states (0 → silent; 1 → compact
summary; >1 → id list, never auto-picked), the GOAL_DRIFT warning
line, the S-5 ``error_allow`` audit path, and ONE subprocess smoke
across the three states. The workspace arrangement deliberately runs
through :func:`checkpoint_round_pass` so the D-R4-2 composition API is
exercised end-to-end against ``plan_checklist_resume``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from devolaflow.agent_workspace import checkpoint_round_pass
from devolaflow.hostbridge import session as hb_session
from devolaflow.hostbridge.audit import AUDIT_LEDGER_RELPATH
from devolaflow.hostbridge.session import main as session_main
from devolaflow.skills.change_activation import ENV_FLAG_NAME

_WATCHED_PATH_METHODS = (
    "open",
    "read_text",
    "read_bytes",
    "write_text",
    "glob",
    "iterdir",
    "is_file",
    "is_dir",
    "mkdir",
    "stat",
)


class _StageStub:
    current_round = 1
    max_rounds = 3


class _PassStub:
    passed = True


def _arrange_change(root: Path, change_id: str) -> None:
    """One resumable change: goal + checklist + checkpointed round 1 + stage."""

    config = root / ".local" / "project_config.yaml"
    if not config.is_file():
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(b"quality:\n  max_rounds: 3\n")
    folder = root / ".local" / ".agent" / "active" / change_id
    folder.mkdir(parents=True)
    (folder / "goal.md").write_text("# Goal\nShip the R4 session smoke.\n", encoding="utf-8")
    (folder / "checklist.md").write_text(
        "\n".join(
            [
                "---",
                f"parent: {change_id}",
                "schema_version: 1",
                "total_items: 2",
                "checked: 1",
                "priority_dist: {P0: 2, P1: 0, P2: 0}",
                "reverted_open: 0",
                "---",
                "",
                "# Checklist",
                "",
                "## G1: Session resume smoke",
                "- [x] C-G1.1 (P0) C-G1.1 has deterministic resume state",
                "      verify: manual",
                "      evidence: evidence/C-G1.1.txt | checked_by: user | "
                "round: 1 | at: 2026-08-24T10:00:00Z",
                "- [ ] C-G1.2 (P0) C-G1.2 has deterministic resume state",
                "      verify: manual",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = checkpoint_round_pass(
        root,
        change_id,
        _PassStub(),
        ["C-G1.1"],
        stage_view=_StageStub(),
        score=90.0,
    )
    (folder / "stage.md").write_text(
        "\n".join(
            [
                "---",
                f"parent: {change_id}",
                "schema_version: 1",
                "current_round: 1",
                "max_rounds: 3",
                "capacity_per_round: 5",
                "---",
                "",
                "# Stage — Round Control",
                "",
                "## Priority Settings",
                "- 2026-08-24T09:00:00Z initial: P0=[C-G1.1, C-G1.2] P1=[] P2=[]",
                "",
                "## Round History",
                "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |",
                "|---|---|---|---|---|---|---|",
                f"| 1 | C-G1.1(P0) | W1 | 1/1 | 0 | {result.stage_reference} | 90.0 |",
                "",
                "## Next Round Plan",
                "- Candidates: []",
                "- Estimated remaining rounds: 1",
                "",
            ]
        ),
        encoding="utf-8",
    )


@pytest.fixture
def engaged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_FLAG_NAME, "1")


@pytest.mark.parametrize("flag_value", [None, "", "0", "true", "01", " 1 "])
def test_resume_gate_off_is_zero_io_and_silent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flag_value: str | None,
) -> None:
    """Only literal "1" activates; every OFF spelling is a zero-IO silent exit 0."""
    if flag_value is None:
        monkeypatch.delenv(ENV_FLAG_NAME, raising=False)
    else:
        monkeypatch.setenv(ENV_FLAG_NAME, flag_value)

    def _forbidden_scan(repo_root: Path) -> None:
        raise AssertionError("R5 strict: scan_workspace ran with the flag off")

    monkeypatch.setattr(hb_session, "scan_workspace", _forbidden_scan)
    calls: list[str] = []

    def _watcher(method: str):
        def _record(self: Path, *args: object, **kwargs: object) -> None:
            calls.append(f"Path.{method}({self})")
            raise AssertionError(f"R5 strict: Path.{method} called with flag off")

        return _record

    for method in _WATCHED_PATH_METHODS:
        monkeypatch.setattr(Path, method, _watcher(method))

    assert session_main(["--repo-root", "/nonexistent/devolaflow-r4-session"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert calls == [], f"R5 strict: filesystem IO observed with flag off: {calls}"


def test_resume_silent_when_no_active_change(
    tmp_path: Path, engaged: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert session_main(["--repo-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""
    assert not (tmp_path / AUDIT_LEDGER_RELPATH).exists()


def test_resume_single_change_prints_compact_summary(
    tmp_path: Path, engaged: None, capsys: pytest.CaptureFixture[str]
) -> None:
    _arrange_change(tmp_path, "r4-session")
    assert session_main(["--host", "claude", "--repo-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "change 'r4-session'" in out
    assert "disposition: READY" in out
    assert "resume round: 2" in out
    assert "checkpoint cp_r4-session_round_1" in out
    assert "checked items: 1" in out
    assert "next-round selection: C-G1.2" in out
    assert "GOAL_DRIFT" not in out
    assert not (tmp_path / AUDIT_LEDGER_RELPATH).exists()


def test_resume_multiple_changes_lists_ids_without_auto_pick(
    tmp_path: Path, engaged: None, capsys: pytest.CaptureFixture[str]
) -> None:
    for change_id in ("change-a", "change-b"):
        (tmp_path / ".local" / ".agent" / "active" / change_id).mkdir(parents=True)
    assert session_main(["--repo-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 active changes" in out
    assert "- change-a" in out and "- change-b" in out
    assert "disposition:" not in out  # never auto-picks / never plans


def test_resume_exception_is_silent_and_ledgered_error_allow(
    tmp_path: Path, engaged: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A change with no checkpoint yet degrades silently but is ledgered (S-5)."""
    (tmp_path / ".local" / ".agent" / "active" / "fresh-change").mkdir(parents=True)
    assert session_main(["--repo-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""
    ledger = tmp_path / AUDIT_LEDGER_RELPATH
    (record,) = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert record["verdict"] == "error_allow"
    assert record["kind"] == "session_resume"
    assert "ResumePlanningError" in record["reason"]


def test_resume_goal_drift_prints_warning_line(
    tmp_path: Path, engaged: None, capsys: pytest.CaptureFixture[str]
) -> None:
    _arrange_change(tmp_path, "r4-session")
    goal_path = tmp_path / ".local" / ".agent" / "active" / "r4-session" / "goal.md"
    goal_path.write_text("# Goal\nPivoted to a NEW objective.\n", encoding="utf-8")
    assert session_main(["--repo-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "disposition: GOAL_DRIFT" in out
    assert "WARNING: GOAL_DRIFT" in out
    assert "human review required" in out


def test_resume_subprocess_smoke_three_states(tmp_path: Path) -> None:
    """THE e2e: real subprocess across gate-off / no-change / single-change."""

    def run(cwd: Path, *, flag_on: bool) -> subprocess.CompletedProcess[str]:
        env = {**os.environ}
        env.pop(ENV_FLAG_NAME, None)
        if flag_on:
            env[ENV_FLAG_NAME] = "1"
        return subprocess.run(
            [sys.executable, "-m", "devolaflow.hostbridge", "resume", "--host", "cursor"],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    arranged_repo = tmp_path / "arranged"
    arranged_repo.mkdir()
    _arrange_change(arranged_repo, "r4-session")

    gate_off = run(arranged_repo, flag_on=False)
    assert (gate_off.returncode, gate_off.stdout) == (0, "")

    no_change = run(empty_repo, flag_on=True)
    assert (no_change.returncode, no_change.stdout) == (0, "")

    single = run(arranged_repo, flag_on=True)
    assert single.returncode == 0
    assert "change 'r4-session'" in single.stdout
    assert "disposition: READY" in single.stdout
    assert "next-round selection: C-G1.2" in single.stdout
