"""Runtime-wiring regression tests — v14.3.0 G-001 closure (ADR-003).

Pins the execution-side adapter contract from
``.local/research/adr/v15-ADR-003-output-closure-enforcement-locus.md``:

* ``file_write`` (``check_file_ownership``) fires from the framework's
  change-driven write surface —
  ``agent_workspace.change.Change.to_active_folder`` — BEFORE each
  artifact write, via ``lifecycle.runtime_wiring.fire_file_write``.
* ``task_stop`` (``test_on_complete``) fires from the L3 report
  emission surface — ``agent_workspace.handoff.HandoffStore.
  write_envelope`` for ``StatusReport`` envelopes — via
  ``lifecycle.runtime_wiring.fire_task_stop``.
* Both adapters default PERMISSIVE (violation → WARNING log via the
  lifecycle logger, no raise; ``strict=True`` raises the top-severity
  ``HookViolation``) and are byte-identical ZERO-IO no-ops unless
  ``DEVOLAFLOW_AGENT_WORKSPACE`` is the literal string ``"1"`` (W-20
  env-flag reuse — same activation surface as A-6 / ``pre_handoff``;
  NO new flag authored).
* ``DEFAULT_EVENTS`` is UNCHANGED at 16 entries — the v14.3.0 landing
  adds CALL SITES, not events; ``file_write`` / ``task_stop`` (and
  their D-Q-3 canonical aliases) were already registered.

The strict default flip is telegraphed for v15.0.0 per ADR-003
§Decision 3 — these tests pin the v14.3.0 permissive baseline that the
graduation will be measured against.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from devolaflow.agent_workspace.change import Change
from devolaflow.agent_workspace.handoff import HandoffStore, make_envelope
from devolaflow.lifecycle import HookResult, HookViolation, clear_hooks
from devolaflow.lifecycle.runtime_wiring import (
    ENV_FLAG,
    fire_file_write,
    fire_task_stop,
)

_RUN_HOOKS_TARGET = "devolaflow.lifecycle.runtime_wiring.run_hooks"


@pytest.fixture(autouse=True)
def _reset_extras():
    """Clear extra hook handlers between tests (defaults stay installed)."""
    clear_hooks()
    yield
    clear_hooks()


def _make_recorder() -> tuple[list[tuple], callable]:
    calls: list[tuple] = []

    def fake_run_hooks(event, payload, *, strict=False):
        calls.append((event, copy.deepcopy(payload), strict))
        return HookResult(event=event, passed=True)

    return calls, fake_run_hooks


def _make_change(owned_files: list[str]) -> Change:
    return Change(
        change_id="t3-hook-wiring",
        goal_md="goal",
        acceptance_md="acceptance",
        spec_md="spec",
        tasks_md="tasks",
        status={"state": "PROPOSED"},
        owned_files=owned_files,
    )


def _status_report_envelope(metrics: dict) -> object:
    return make_envelope(
        seq=1,
        from_layer="L3",
        to_layer="L2",
        change_id="t3-hook-wiring",
        envelope_kind="StatusReport",
        payload={"task_id": "T-1", "metrics": metrics},
    )


# ---------------------------------------------------------------------------
# file_write — change-driven write surface (Change.to_active_folder)
# ---------------------------------------------------------------------------


def test_file_write_fires_at_change_write_surface(tmp_path, monkeypatch) -> None:
    """ADR-003 locus: every ``to_active_folder`` artifact write fires the hook.

    With the env flag ON, all 6 artifact writes (``learnings.jsonl`` is
    absent here) run through ``run_hooks("file_write", ...)`` BEFORE
    touching disk, in permissive mode, with the owned_files manifest
    from the change attached AND the S-8 §2 change-folder exemption
    materialised (the target itself appears in the allowed set).
    """
    monkeypatch.setenv(ENV_FLAG, "1")
    folder = tmp_path / "active" / "t3-hook-wiring"
    calls, fake = _make_recorder()

    with patch(_RUN_HOOKS_TARGET, side_effect=fake):
        _make_change(owned_files=["src/foo.py"]).to_active_folder(folder)

    assert [event for event, _, _ in calls] == ["file_write"] * 6
    written_names = {Path(payload["path"]).name for _, payload, _ in calls}
    assert written_names == {
        "goal.md",
        "acceptance.md",
        "spec.md",
        "tasks.md",
        "STATUS.yaml",
        "owned_files.txt",
    }
    for _, payload, strict in calls:
        assert strict is False, "v14.3.0 call site must be permissive (strict=False)"
        assert "src/foo.py" in payload["owned_files"], "manifest must reach the hook"
        assert payload["path"] in payload["owned_files"], (
            "S-8 §2: writes inside the change folder are exempt — the adapter "
            "materialises the exemption by including the exact target"
        )
    # The writes themselves still happened (hook fires BEFORE, never instead).
    assert (folder / "goal.md").read_text(encoding="utf-8") == "goal"
    assert (folder / "owned_files.txt").read_text(encoding="utf-8") == "src/foo.py\n"


def test_file_write_violation_warns_permissive(monkeypatch, caplog) -> None:
    """Permissive default: an out-of-manifest write WARNs, never raises (S-8 lite)."""
    monkeypatch.setenv(ENV_FLAG, "1")
    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        result = fire_file_write("src/outside.py", owned_files=["src/allowed.py"])
    assert result is not None
    assert result.passed is False
    assert result.violations[0].code == "CFO006"
    assert result.violations[0].severity == "blocker"
    # S-5: the WARN must actually log via the standard logging module.
    assert any("CFO006" in rec.message for rec in caplog.records)


def test_file_write_strict_blocks(monkeypatch) -> None:
    """Strict opt-in (the v15.0.0 graduation path) raises the blocker violation."""
    monkeypatch.setenv(ENV_FLAG, "1")
    with pytest.raises(HookViolation) as exc_info:
        fire_file_write("src/outside.py", owned_files=["src/allowed.py"], strict=True)
    assert exc_info.value.code == "CFO006"
    assert exc_info.value.severity == "blocker"


def test_runtime_wiring_zero_io_noop_without_env_flag(monkeypatch) -> None:
    """R5 strict: env flag absent / non-"1" → byte-identical no-op, ZERO IO.

    Neither adapter may dispatch ``run_hooks`` NOR resolve the manifest
    from disk when ``DEVOLAFLOW_AGENT_WORKSPACE`` is not the literal
    string ``"1"`` (W-20 reuse of the R5 strict parsing pattern).
    """
    hook_calls, fake_hooks = _make_recorder()
    io_calls: list[tuple] = []

    def fake_resolve(change_id, repo_root):
        io_calls.append((change_id, repo_root))
        return ["src/foo.py"], None

    with (
        patch(_RUN_HOOKS_TARGET, side_effect=fake_hooks),
        patch(
            "devolaflow.lifecycle.runtime_wiring._resolve_manifest",
            side_effect=fake_resolve,
        ),
    ):
        monkeypatch.delenv(ENV_FLAG, raising=False)
        assert fire_file_write("src/outside.py", change_id="t3-hook-wiring") is None
        assert fire_task_stop({"tests_failed": 5}) is None
        for non_truthy in ("0", "true", "yes", " 1", "1 "):
            monkeypatch.setenv(ENV_FLAG, non_truthy)
            assert fire_file_write("src/outside.py", change_id="t3-hook-wiring") is None
            assert fire_task_stop({"tests_failed": 5}) is None

    assert hook_calls == [], "run_hooks must NOT be dispatched when the flag is OFF"
    assert io_calls == [], "manifest must NOT be read from disk when the flag is OFF"


# ---------------------------------------------------------------------------
# task_stop — L3 report emission surface (HandoffStore.write_envelope)
# ---------------------------------------------------------------------------


def test_task_stop_fires_at_status_report_emission(tmp_path, monkeypatch) -> None:
    """ADR-003 locus: a StatusReport envelope write fires ``task_stop`` once."""
    monkeypatch.setenv(ENV_FLAG, "1")
    store = HandoffStore(repo_root=tmp_path)
    envelope = _status_report_envelope(
        {"tests_passed": 5, "tests_failed": 0, "lint_status": "clean"}
    )
    calls, fake = _make_recorder()

    with patch(_RUN_HOOKS_TARGET, side_effect=fake):
        written = store.write_envelope(envelope)

    assert len(calls) == 1
    event, payload, strict = calls[0]
    assert event == "task_stop"
    assert strict is False, "v14.3.0 call site must be permissive (strict=False)"
    assert payload["task_id"] == "T-1"
    assert payload["metrics"]["tests_passed"] == 5
    assert written.is_file(), "envelope must still be materialised on disk"


def test_task_stop_violation_warns_permissive_and_envelope_still_written(
    tmp_path, monkeypatch, caplog
) -> None:
    """Permissive default: a failing report WARNs (TOC004) but never blocks the write."""
    monkeypatch.setenv(ENV_FLAG, "1")
    store = HandoffStore(repo_root=tmp_path)
    envelope = _status_report_envelope(
        {"tests_passed": 3, "tests_failed": 2, "lint_status": "clean"}
    )

    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        written = store.write_envelope(envelope)

    assert written.is_file(), "permissive mode must not block the envelope write"
    assert any("TOC004" in rec.message for rec in caplog.records), (
        "S-5: the P4 retry-trigger violation must actually log at WARNING"
    )


def test_task_stop_noop_without_env_flag(tmp_path, monkeypatch) -> None:
    """R5 strict: with the flag OFF, write_envelope behaviour is byte-identical."""
    monkeypatch.delenv(ENV_FLAG, raising=False)
    store = HandoffStore(repo_root=tmp_path)
    envelope = _status_report_envelope(
        {"tests_passed": 0, "tests_failed": 9, "lint_status": "warnings"}
    )
    calls, fake = _make_recorder()

    with patch(_RUN_HOOKS_TARGET, side_effect=fake):
        written = store.write_envelope(envelope)

    assert calls == [], "no hook dispatch when the activation flag is OFF"
    assert written.is_file()


def test_task_stop_not_fired_for_task_dispatch_envelope(tmp_path, monkeypatch) -> None:
    """Only StatusReport envelopes are an L3 report finalisation — dispatches skip."""
    monkeypatch.setenv(ENV_FLAG, "1")
    store = HandoffStore(repo_root=tmp_path)
    envelope = make_envelope(
        seq=1,
        from_layer="L2",
        to_layer="L3",
        change_id="t3-hook-wiring",
        envelope_kind="TaskDispatch",
        payload={
            "task_id": "T-1",
            "type": "implement",
            "acceptance_criteria_ref": "x",
            "owned_files_ref": "y",
        },
    )
    calls, fake = _make_recorder()

    with patch(_RUN_HOOKS_TARGET, side_effect=fake):
        written = store.write_envelope(envelope)

    assert calls == [], "TaskDispatch envelopes must not fire task_stop"
    assert written.is_file()


# ---------------------------------------------------------------------------
# DEFAULT_EVENTS + honesty contract
# ---------------------------------------------------------------------------


def test_default_events_contains_wired_runtime_events() -> None:
    """The 4 wired event names are registered; tuple length stays at 16.

    The v14.3.0 landing adds CALL SITES (runtime_wiring adapters), not
    events — ``file_write`` / ``task_stop`` and their D-Q-3 canonical
    aliases (``check_file_write`` / ``post_task_complete``) were already
    in ``DEFAULT_EVENTS``, so the A-2.2-style append-only pins in
    ``tests/test_lifecycle_hooks.py`` + ``tests/test_no_ghost_features.py``
    (len == 16) stay byte-stable.
    """
    import inspect

    import devolaflow.lifecycle as lifecycle_pkg
    from devolaflow.lifecycle import (
        DEFAULT_EVENTS,
        check_file_ownership,
        fire_file_write,
        fire_task_stop,
        is_workspace_engaged,
        list_handlers,
        test_on_complete,
    )

    assert {"file_write", "task_stop", "check_file_write", "post_task_complete"}.issubset(
        set(DEFAULT_EVENTS)
    )
    assert len(DEFAULT_EVENTS) == 16, "v14.3.0 wiring must NOT grow the event tuple"

    # Default handlers stay bound to the documented hooks.
    assert list_handlers("file_write") == (check_file_ownership,)
    assert list_handlers("task_stop") == (test_on_complete,)

    # Adapters are exported on the package surface.
    assert callable(fire_file_write)
    assert callable(fire_task_stop)
    assert callable(is_workspace_engaged)

    # Honesty contract: the stale "deferred to a future patch (likely
    # v7.6.x)" wiring deferral is gone; the wiring truth + v15.0.0 strict
    # telegraph stand. (The narrower v14.0.0 `check_human_input_append_only`
    # DEFAULT_EVENTS note is a different, still-true statement and stays.)
    pkg_source = inspect.getsource(lifecycle_pkg)
    assert "deferred to a future patch" not in pkg_source, (
        "v14.3.0 must replace the stale v7.6.x deferral note with the wiring truth"
    )
    assert "likely v7.6.x" not in pkg_source
    assert "runtime_wiring" in pkg_source
    assert "v15.0.0" in pkg_source, "the strict graduation telegraph must be documented"
