"""Runtime-wiring regression tests — v14.3.0 G-001 closure (ADR-003).

Pins the execution-side adapter contract from
``docs/cycle-archive/adr/v15-ADR-003-output-closure-enforcement-locus.md``:

* ``file_write`` (``check_file_ownership``) fires from the framework's
  change-driven write surface —
  ``agent_workspace.change.Change.to_active_folder`` — BEFORE each
  artifact write, via ``lifecycle.runtime_wiring.fire_file_write``.
* ``task_stop`` (``test_on_complete``) fires from the L2 report
  emission surface — ``agent_workspace.handoff.HandoffStore.
  write_envelope`` for ``StatusReport`` envelopes — via
  ``lifecycle.runtime_wiring.fire_task_stop``.
* Both adapters default STRICT since v15.0.0 (G-038 flip 5 per ADR-003
  §Decision 3: violation → top-severity ``HookViolation`` raise, S-8
  "mode: full" block + escalate; opt-out = explicit ``strict=False``,
  S-8 "mode: lite" warn + log) and are byte-identical ZERO-IO no-ops
  unless ``DEVOLAFLOW_AGENT_WORKSPACE`` is the literal string ``"1"``
  (W-20 env-flag reuse — same activation surface as A-6 /
  ``pre_handoff``; NO new flag authored; the activation gate is
  UNCHANGED by the strict flip).
* ``DEFAULT_EVENTS`` is at 17 entries since v15.0.0 (G-038 flip 4
  appended ``check_human_input_write`` at position 17 per A-2.2);
  ``file_write`` / ``task_stop`` (and their D-Q-3 canonical aliases)
  were already registered at v14.3.0.
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
        checklist_md="checklist",
        stage_md="stage",
        preflight_md="preflight",
        spec_md="spec",
        status={"state": "PROPOSED"},
        owned_files=owned_files,
    )


def _status_report_envelope(metrics: dict) -> object:
    return make_envelope(
        seq=1,
        from_layer="L2",
        to_layer="L1",
        change_id="t3-hook-wiring",
        envelope_kind="StatusReport",
        payload={"task_id": "T-1", "metrics": metrics},
    )


# ---------------------------------------------------------------------------
# file_write — change-driven write surface (Change.to_active_folder)
# ---------------------------------------------------------------------------


def test_file_write_fires_at_change_write_surface(tmp_path, monkeypatch) -> None:
    """ADR-003 locus: every ``to_active_folder`` artifact write fires the hook.

    With the env flag ON, all 8 artifact writes (``learnings.jsonl`` is
    absent here; ``entrance.md`` is backfilled from the scaffold template
    per the v20.0.x always-generated fix) run through
    ``run_hooks("file_write", ...)`` BEFORE
    touching disk — in STRICT mode since v15.0.0 (the call site defers
    to the adapter's strict default per G-038 flip 5) — with the
    owned_files manifest from the change attached AND the S-8 §2
    change-folder exemption materialised (the target itself appears in
    the allowed set).
    """
    monkeypatch.setenv(ENV_FLAG, "1")
    folder = tmp_path / "active" / "t3-hook-wiring"
    calls, fake = _make_recorder()

    with patch(_RUN_HOOKS_TARGET, side_effect=fake):
        _make_change(owned_files=["src/foo.py"]).to_active_folder(folder)

    assert [event for event, _, _ in calls] == ["file_write"] * 8
    written_names = {Path(payload["path"]).name for _, payload, _ in calls}
    assert written_names == {
        "goal.md",
        "checklist.md",
        "stage.md",
        "preflight.md",
        "spec.md",
        "entrance.md",
        "STATUS.yaml",
        "owned_files.txt",
    }
    for _, payload, strict in calls:
        assert strict is True, (
            "v15.0.0 G-038 flip 5: the production call site must defer to the "
            "strict default (S-8 'mode: full')"
        )
        assert "src/foo.py" in payload["owned_files"], "manifest must reach the hook"
        assert payload["path"] in payload["owned_files"], (
            "S-8 §2: writes inside the change folder are exempt — the adapter "
            "materialises the exemption by including the exact target"
        )
    # The writes themselves still happened (hook fires BEFORE, never instead;
    # in-manifest/exempt writes are clean so strict mode does not block them).
    assert (folder / "goal.md").read_text(encoding="utf-8") == "goal"
    assert (folder / "owned_files.txt").read_text(encoding="utf-8") == "src/foo.py\n"


def test_file_write_violation_warns_permissive(monkeypatch, caplog) -> None:
    """Flip-5 opt-out: explicit ``strict=False`` (S-8 'mode: lite') WARNs, never raises."""
    monkeypatch.setenv(ENV_FLAG, "1")
    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        result = fire_file_write("src/outside.py", owned_files=["src/allowed.py"], strict=False)
    assert result is not None
    assert result.passed is False
    assert result.violations[0].code == "CFO006"
    assert result.violations[0].severity == "blocker"
    # S-5: the WARN must actually log via the standard logging module.
    assert any("CFO006" in rec.message for rec in caplog.records)


def test_file_write_strict_blocks(monkeypatch) -> None:
    """v15.0.0 strict DEFAULT (no explicit kwarg) raises the blocker violation."""
    monkeypatch.setenv(ENV_FLAG, "1")
    with pytest.raises(HookViolation) as exc_info:
        fire_file_write("src/outside.py", owned_files=["src/allowed.py"])
    assert exc_info.value.code == "CFO006"
    assert exc_info.value.severity == "blocker"


def test_file_write_resolves_manifest_from_change_id_on_disk(tmp_path, monkeypatch) -> None:
    """v15.0.0 R3: the ``change_id`` path reads the on-disk manifest.

    ``fire_file_write(change_id=...)`` (no explicit ``owned_files``) must
    resolve ``.local/.agent/active/<id>/owned_files.txt`` from
    ``repo_root``, attach the change_id to the payload, enforce S-8 in
    strict mode against the RESOLVED manifest, and treat a change with
    no manifest on disk as "no change context" (Gate 2 → ``None``).
    """
    from devolaflow.agent_workspace.change import ACTIVE_DIR_DEFAULT

    monkeypatch.setenv(ENV_FLAG, "1")
    change_folder = tmp_path / ACTIVE_DIR_DEFAULT / "r3-manifest"
    change_folder.mkdir(parents=True)
    (change_folder / "owned_files.txt").write_text("src/mod.py\n\n  src/other.py  \n")

    # In-manifest write passes; the payload carries the resolved manifest.
    calls, fake = _make_recorder()
    with patch(_RUN_HOOKS_TARGET, side_effect=fake):
        result = fire_file_write("src/mod.py", change_id="r3-manifest", repo_root=tmp_path)
    assert result is not None
    [(event, payload, strict)] = calls
    assert event == "file_write" and strict is True
    assert payload["change_id"] == "r3-manifest"
    assert payload["owned_files"] == ["src/mod.py", "src/other.py"], (
        "manifest lines must be stripped and blank lines dropped"
    )

    # Out-of-manifest write blocks under the strict default (real hook chain).
    with pytest.raises(HookViolation) as exc_info:
        fire_file_write("src/outside.py", change_id="r3-manifest", repo_root=tmp_path)
    assert exc_info.value.code == "CFO006"

    # S-8 §2: a write INSIDE the resolved change folder is exempt even
    # though it is not a manifest entry (exemption materialised).
    in_folder = fire_file_write(
        str(change_folder / "notes.md"), change_id="r3-manifest", repo_root=tmp_path
    )
    assert in_folder is not None and in_folder.passed is True

    # Gate 2: a change id with NO manifest on disk → clean no-op (None).
    assert fire_file_write("src/mod.py", change_id="ghost", repo_root=tmp_path) is None


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
# task_stop — L2 report emission surface (HandoffStore.write_envelope)
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
    assert strict is True, (
        "v15.0.0 G-038 flip 5: the production call site must defer to the "
        "strict default (S-8 'mode: full')"
    )
    assert payload["task_id"] == "T-1"
    assert payload["metrics"]["tests_passed"] == 5
    assert written.is_file(), "envelope must still be materialised on disk"


def test_task_stop_violation_blocks_envelope_write_by_default(tmp_path, monkeypatch) -> None:
    """v15.0.0 strict default: a failing report raises TOC004 and BLOCKS the write.

    The S-8 "mode: full" / P4 retry-trigger semantics per ADR-003
    §Decision 3: the hook fires BEFORE materialisation, so the
    blocker-severity TOC004 raise means the envelope never lands on
    disk — the wave-level retry classifier catches the HookViolation
    and routes the task back through a convergence round.
    """
    monkeypatch.setenv(ENV_FLAG, "1")
    store = HandoffStore(repo_root=tmp_path)
    envelope = _status_report_envelope(
        {"tests_passed": 3, "tests_failed": 2, "lint_status": "clean"}
    )

    with pytest.raises(HookViolation) as exc_info:
        store.write_envelope(envelope)

    assert exc_info.value.code == "TOC004"
    assert exc_info.value.severity == "blocker"
    target = store.handoff_root / envelope.filename
    assert not target.exists(), "strict default must block the envelope write (fires BEFORE disk)"


def test_fire_task_stop_strict_false_opt_out_warns(monkeypatch, caplog) -> None:
    """Flip-5 opt-out: ``fire_task_stop(..., strict=False)`` (S-8 'mode: lite')
    WARNs (TOC004) and returns the populated HookResult — the v14.3.0
    permissive behaviour, reachable per call site with no env flag."""
    monkeypatch.setenv(ENV_FLAG, "1")
    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        result = fire_task_stop(
            {"tests_passed": 3, "tests_failed": 2, "lint_status": "clean"},
            strict=False,
        )
    assert result is not None
    assert result.passed is False
    assert result.violations[0].code == "TOC004"
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
    """Only StatusReport envelopes are an L2 report finalisation — dispatches skip."""
    monkeypatch.setenv(ENV_FLAG, "1")
    store = HandoffStore(repo_root=tmp_path)
    envelope = make_envelope(
        seq=1,
        from_layer="L1",
        to_layer="L2",
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
    """The 4 wired event names are registered; tuple length is 17 at v15.0.0.

    The v14.3.0 landing added CALL SITES (runtime_wiring adapters), not
    events — ``file_write`` / ``task_stop`` and their D-Q-3 canonical
    aliases (``check_file_write`` / ``post_task_complete``) were already
    in ``DEFAULT_EVENTS``. v15.0.0 G-038 flip 4 then grew the tuple
    16 → 17 by APPENDING ``check_human_input_write`` per A-2.2
    (positions 1-16 byte-stable; both former ``len == 16`` pins
    re-pinned in the same MAJOR).
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
    assert len(DEFAULT_EVENTS) == 17, (
        "v15.0.0 G-038 flip 4: check_human_input_write appended at position 17"
    )

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
