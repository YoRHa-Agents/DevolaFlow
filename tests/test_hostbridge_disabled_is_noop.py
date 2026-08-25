"""R5 strict baseline — the host bridge is a zero-IO no-op when
``DEVOLAFLOW_HOST_ENFORCE`` is absent / not the literal ``"1"``.

W-20 checklist step 3 for the NEW flag authored in v17.0.0 R2 (see
``references/env-flags.md`` §2.18): with the flag off,

1. ``decide()`` allows with ZERO filesystem IO (Path watchers + a
   nonexistent repo_root prove no probe fires), and
2. the CLI allows for every host protocol and writes NO audit ledger.

The filename mirrors ``tests/test_shell_proxy_disabled_is_noop.py`` —
do not delete without an explicit retrospective entry.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from devolaflow.hostbridge.__main__ import main as hb_main
from devolaflow.hostbridge.audit import AUDIT_LEDGER_RELPATH
from devolaflow.hostbridge.decision import ENV_FLAG, decide, is_host_enforce_active
from devolaflow.hostbridge.normalize import BridgeEvent

_WATCHED_PATH_METHODS = (
    "open",
    "read_text",
    "write_text",
    "glob",
    "iterdir",
    "is_file",
    "is_dir",
    "mkdir",
    "stat",
)


@pytest.mark.parametrize("flag_value", [None, "", "0", "true", "yes", "on", "01", " 1 "])
def test_decide_zero_filesystem_io_when_flag_off(
    monkeypatch: pytest.MonkeyPatch, flag_value: str | None
) -> None:
    """Only literal "1" activates; every OFF spelling is a zero-IO allow."""
    if flag_value is None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
    else:
        monkeypatch.setenv(ENV_FLAG, flag_value)
    assert is_host_enforce_active() is False

    calls: list[str] = []

    def _watcher(method: str):
        def _record(self: Path, *args: object, **kwargs: object) -> None:
            calls.append(f"Path.{method}({self})")
            raise AssertionError(f"R5 strict: Path.{method} called with flag off")

        return _record

    for method in _WATCHED_PATH_METHODS:
        monkeypatch.setattr(Path, method, _watcher(method))

    # Nonexistent repo root: any probe would raise / record.
    ghost_root = Path("/nonexistent/devolaflow-hostbridge-r5-strict")
    for event in (
        BridgeEvent(host="cursor", kind="file_write", path="src/x.py"),
        BridgeEvent(host="claude", kind="shell", command="pytest tests/ -q"),
        BridgeEvent(host="dsh", kind="unknown"),
    ):
        decision = decide(event, ghost_root)
        assert decision.allow is True
        assert decision.verdict == "allow"
        assert ENV_FLAG in decision.reason
        assert decision.audit == {}  # nothing ledgered on the fast path

    assert calls == [], f"R5 strict: filesystem IO observed with flag off: {calls}"


def test_cli_allows_and_writes_no_ledger_when_flag_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(ENV_FLAG, raising=False)
    payload = json.dumps({"tool": "Write", "tool_input": {"path": "src/evil.py"}})

    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hb_main(["--host", "cursor", "--repo-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"permission": "allow"}

    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hb_main(["--host", "claude", "--repo-root", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""

    assert not (tmp_path / AUDIT_LEDGER_RELPATH).exists(), (
        "flag-off CLI runs must not create the audit ledger"
    )
