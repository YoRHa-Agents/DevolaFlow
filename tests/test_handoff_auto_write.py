"""Tests for the ``auto_write_handoff`` lifecycle hook (v9.1.3 PV-03).

Closes G-005 deferred from v9.1.0 by creating the FIRST production
caller of :meth:`devolaflow.agent_workspace.handoff.HandoffStore.write_envelope`
outside the module itself. The hook is bound to the new ``pre_handoff``
event and fires from ``feedback.ProposalGenerator._emit_dispatch`` after
``pre_dispatch`` and ``post_dispatch`` (Soul Rule S-10 governance tail).

Test strategy mirrors the patterns established by
:mod:`tests.test_lifecycle_envelope_append_only` (S-9 hook unit tests)
and :mod:`tests.test_handoff_envelope_immutable` (S-9 filesystem
immutability):

* **Gate 1** — ``DEVOLAFLOW_AGENT_WORKSPACE`` unset / not literal ``"1"``
  → byte-identical no-op. Zero filesystem writes; ``HookResult`` is
  empty. R5 strict env-flag parsing: every variant other than the
  literal ``"1"`` is treated as OFF.

* **Gate 2** — env-flag ON but ``payload["change_context"]`` empty /
  missing → no envelope written (legitimate free-floating dispatch per
  the v8.3.0 PV-05 schema's OPTIONAL contract).

* **Action** — env-flag ON + populated ``change_context`` → envelope
  written under ``.local/.agent/handoff/<from>__<to>__<change-id>__<seq>.yaml``;
  seq monotonically increases across calls (Rule S-9 append-only proof).

* **AWH002** — pre-existing envelope at ``seq=N`` produces an
  :class:`EnvelopeImmutableError` from the writer; in permissive mode
  the handler surfaces it as a ``HookViolation(code="AWH002",
  severity="warning")`` and does NOT raise. In strict mode the original
  :class:`EnvelopeImmutableError` propagates so the caller sees the
  Rule S-9 recovery hint verbatim.

* **AWH001** — payload missing ``change_id`` / ``from_layer`` /
  ``to_layer`` → ``HookViolation(code="AWH001", severity="error")`` in
  permissive mode; ``finalize`` re-raises the violation in strict mode.

All tests use ``tmp_path`` fixtures + ``monkeypatch.chdir`` for
filesystem isolation. ``HandoffStore()`` resolves ``repo_root`` from
``Path.cwd()`` so chdir-to-tmp_path is sufficient — no real-repo writes
ever leak out of the test sandbox.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.agent_workspace.handoff import (
    EnvelopeImmutableError,
    HandoffStore,
    make_envelope,
)
from devolaflow.lifecycle import HookViolation
from devolaflow.lifecycle.auto_write_handoff import (
    ENV_FLAG,
    ENV_FLAG_TRUTHY,
    EVENT,
    auto_write_handoff,
)

_CHANGE_ID = "v9-1-3-pv03-test"


def _make_payload(
    *,
    change_id: str = _CHANGE_ID,
    from_layer: str = "L0",
    to_layer: str = "L2",
    include_change_context: bool = True,
) -> dict:
    """Build a minimal valid dispatch payload for the auto-write hook.

    Mirrors the lean dispatch shape consumed by ``feedback._emit_dispatch``
    (``hdr`` / ``task`` / ``accept`` / ``context`` / ``change_context``)
    so the test fixture is realistic — but trims it to the smallest
    possible surface that still satisfies the v8.3.0 PV-05
    ``change_context`` schema and the v8.2.4 envelope contract.
    """
    payload: dict = {
        "task": {"id": "T-PV03", "type": "implement", "title": "auto-write handoff"},
        "accept": ["envelope materialised under .local/.agent/handoff/"],
        "context": {"applicable_rules": {"loading_strategy": "standard"}},
    }
    if include_change_context:
        payload["change_context"] = {
            "change_id": change_id,
            "active_folder": f".local/.agent/active/{change_id}",
            "state": "IN_PROGRESS",
            "spec_delta_target": "agent_workspace",
            "owned_files_ref": f".local/.agent/active/{change_id}/owned_files.txt",
            "acceptance_ref": f".local/.agent/active/{change_id}/acceptance.md",
            "from_layer": from_layer,
            "to_layer": to_layer,
        }
    return payload


def _handoff_dir(tmp_path: Path) -> Path:
    return tmp_path / ".local" / ".agent" / "handoff"


# ---------------------------------------------------------------------------
# Gate 1 — env-flag OFF / non-literal-"1" is byte-identical no-op
# ---------------------------------------------------------------------------


def test_env_flag_off_is_byte_identical_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-flag absent → dispatch unchanged AND zero filesystem writes (R5 strict)."""
    monkeypatch.delenv(ENV_FLAG, raising=False)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload()

    result = auto_write_handoff(payload)

    assert result.passed is True
    assert result.violations == []
    assert result.event == EVENT
    handoff_dir = _handoff_dir(tmp_path)
    assert not handoff_dir.exists() or list(handoff_dir.iterdir()) == [], (
        "R5 strict violation: env-flag absent must produce ZERO filesystem writes "
        "under .local/.agent/handoff/"
    )


@pytest.mark.parametrize("flag_value", ["0", "true", "yes", " 1 ", "1.0", "TRUE", ""])
def test_env_flag_any_value_other_than_1_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag_value: str
) -> None:
    """R5 strict: ``DEVOLAFLOW_AGENT_WORKSPACE`` truthy iff EXACTLY ``"1"``.

    Every other variant (``"0"`` / ``"true"`` / ``"yes"`` / whitespace-
    padded ``" 1 "`` / ``"1.0"`` / ``""``) is treated as OFF. Mirrors
    the W-20 reuse-first parsing pattern established by
    ``devolaflow.skills.change_activation.from_env`` (v9.1.2 PV-02) so
    the agent-workspace activation surface stays SINGLE-source-of-truth.
    """
    monkeypatch.setenv(ENV_FLAG, flag_value)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload()
    result = auto_write_handoff(payload)

    assert result.passed is True
    assert result.violations == []
    handoff_dir = _handoff_dir(tmp_path)
    assert not handoff_dir.exists() or list(handoff_dir.iterdir()) == [], (
        f"R5 strict violation: ENV_FLAG={flag_value!r} (not literal '1') must "
        f"produce ZERO filesystem writes — got non-empty handoff dir"
    )


# ---------------------------------------------------------------------------
# Gate 2 — env-flag ON but no change_context → no-op
# ---------------------------------------------------------------------------


def test_env_flag_on_but_no_change_context_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-flag ON + missing/empty ``change_context`` → no envelope written.

    A dispatch without ``change_context`` is a free-floating workflow per
    the v8.3.0 PV-05 OPTIONAL schema — the auto-write handler MUST treat
    it as a legitimate no-op, NOT an error.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload(include_change_context=False)
    result = auto_write_handoff(payload)
    assert result.passed is True
    assert result.violations == []

    payload_empty_cc = _make_payload()
    payload_empty_cc["change_context"] = {}
    result_empty = auto_write_handoff(payload_empty_cc)
    assert result_empty.passed is True
    assert result_empty.violations == []

    handoff_dir = _handoff_dir(tmp_path)
    assert not handoff_dir.exists() or list(handoff_dir.iterdir()) == [], (
        "Gate 2 violation: missing/empty change_context must produce ZERO writes"
    )


# ---------------------------------------------------------------------------
# Action — env-flag ON + populated change_context → envelope written
# ---------------------------------------------------------------------------


def test_env_flag_on_with_change_context_writes_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both gates open → envelope materialised at the canonical path.

    Verifies the headline G-005 closure: ``HandoffStore.write_envelope``
    runs from the auto-write handler with the dispatch payload's
    ``change_context`` block, producing an envelope at the v8.2.4
    canonical filename pattern
    ``<from>__<to>__<change-id>__<seq>.yaml``.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload()
    result = auto_write_handoff(payload)

    assert result.passed is True
    assert result.violations == []

    expected = _handoff_dir(tmp_path) / f"L0__L2__{_CHANGE_ID}__0001.yaml"
    handoff_dir = _handoff_dir(tmp_path)
    observed = list(handoff_dir.iterdir()) if handoff_dir.exists() else "no handoff dir"
    assert expected.is_file(), (
        f"Action gate violation: envelope MUST be written at {expected!s} (observed: {observed})"
    )
    body = expected.read_text(encoding="utf-8")
    assert "schema_version: 2" in body
    assert "envelope_kind: TaskDispatch" in body
    assert f"change_id: {_CHANGE_ID}" in body
    assert "seq: 1" in body
    assert "from_layer: L0" in body
    assert "to_layer: L2" in body
    assert "L3" not in body


def test_seq_monotonically_increases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """3 successive auto-write calls produce seq=1, seq=2, seq=3.

    Pins Rule S-9 (append-only ledger) at the auto-write boundary —
    each call must consult :meth:`HandoffStore.next_seq` to find the
    next available slot, never overwriting a committed envelope.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    for expected_seq in (1, 2, 3):
        payload = _make_payload()
        result = auto_write_handoff(payload)
        assert result.passed is True, (
            f"call {expected_seq} should have produced seq={expected_seq} cleanly; "
            f"got violations={result.violations}"
        )
        target = _handoff_dir(tmp_path) / f"L0__L2__{_CHANGE_ID}__{expected_seq:04d}.yaml"
        assert target.is_file(), f"seq={expected_seq} envelope MUST exist on disk"

    files = sorted(_handoff_dir(tmp_path).iterdir())
    assert len(files) == 3
    assert all(p.is_file() for p in files)


# ---------------------------------------------------------------------------
# AWH002 — EnvelopeImmutableError surfaces as warning in permissive mode
# ---------------------------------------------------------------------------


def test_envelope_immutable_error_surfaces_as_warning_in_permissive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing seq=1 envelope → AWH002 warning, NOTHING raised.

    Sets up a manual collision by writing seq=1 directly through
    :class:`HandoffStore`, then forces the auto-write handler into the
    same seq slot via a stub ``next_seq`` that returns 1. Permissive
    mode (the default) MUST catch :class:`EnvelopeImmutableError`,
    surface it as a single ``HookViolation(code="AWH002",
    severity="warning")``, and return without raising.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    _handoff_dir(tmp_path).mkdir(parents=True)
    pre_existing = make_envelope(
        seq=1,
        from_layer="L0",
        to_layer="L2",
        change_id=_CHANGE_ID,
        envelope_kind="TaskDispatch",
        payload={
            "task_id": "PRE-EXISTING",
            "type": "implement",
            "acceptance_criteria_ref": f".local/.agent/active/{_CHANGE_ID}/acceptance.md",
            "owned_files_ref": f".local/.agent/active/{_CHANGE_ID}/owned_files.txt",
        },
        created="2026-04-30T00:00:00Z",
    )
    pre_existing_path = HandoffStore().write_envelope(pre_existing)
    original_body = pre_existing_path.read_bytes()

    monkeypatch.setattr(HandoffStore, "next_seq", lambda self, change_id: 1)

    payload = _make_payload()
    result = auto_write_handoff(payload)

    assert result.passed is False
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.code == "AWH002"
    assert v.severity == "warning"
    assert _CHANGE_ID in v.message
    assert pre_existing_path.read_bytes() == original_body


def test_envelope_immutable_error_raises_in_strict_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Strict mode propagates the original :class:`EnvelopeImmutableError`.

    The cycle plan §PV-03 requires that strict-mode callers receive the
    original Rule S-9 recovery hint verbatim (the writer's exception
    message advises ``seq+1``); wrapping it in a HookViolation would
    swallow that advice. Pins the ``raise`` flow.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    _handoff_dir(tmp_path).mkdir(parents=True)
    pre_existing = make_envelope(
        seq=1,
        from_layer="L0",
        to_layer="L2",
        change_id=_CHANGE_ID,
        envelope_kind="TaskDispatch",
        payload={
            "task_id": "PRE-EXISTING",
            "type": "implement",
            "acceptance_criteria_ref": f".local/.agent/active/{_CHANGE_ID}/acceptance.md",
            "owned_files_ref": f".local/.agent/active/{_CHANGE_ID}/owned_files.txt",
        },
        created="2026-04-30T00:00:00Z",
    )
    pre_existing_path = HandoffStore().write_envelope(pre_existing)
    original_body = pre_existing_path.read_bytes()

    monkeypatch.setattr(HandoffStore, "next_seq", lambda self, change_id: 1)

    with pytest.raises(EnvelopeImmutableError) as exc_info:
        auto_write_handoff(_make_payload(), strict=True)
    assert "seq+1" in str(exc_info.value) or "seq=2" in str(exc_info.value)
    assert pre_existing_path.read_bytes() == original_body


# ---------------------------------------------------------------------------
# AWH001 — malformed payload (missing layers / change_id)
# ---------------------------------------------------------------------------


def test_malformed_payload_surfaces_as_error_in_permissive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing ``change_id`` → ``HookViolation(code="AWH001", severity="error")``.

    Permissive mode (default) MUST aggregate the violation onto the
    returned :class:`HookResult`; nothing is raised. Verified across
    three malformations (missing change_id / missing from_layer /
    missing to_layer) so the AWH001 surface is robust to incomplete
    dispatcher metadata.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload()
    payload["change_context"]["change_id"] = ""
    result = auto_write_handoff(payload)
    assert result.passed is False
    assert any(v.code == "AWH001" and v.severity == "error" for v in result.violations)

    payload2 = _make_payload()
    payload2["change_context"]["from_layer"] = ""
    result2 = auto_write_handoff(payload2)
    assert result2.passed is False
    assert any(v.code == "AWH001" for v in result2.violations)

    payload3 = _make_payload()
    payload3["change_context"]["to_layer"] = ""
    result3 = auto_write_handoff(payload3)
    assert result3.passed is False
    assert any(v.code == "AWH001" for v in result3.violations)

    payload4 = _make_payload(to_layer="L3")
    result4 = auto_write_handoff(payload4)
    assert result4.passed is False
    assert any(
        v.code == "AWH001" and "unknown current layer token 'L3'" in v.message
        for v in result4.violations
    )

    handoff_dir = _handoff_dir(tmp_path)
    assert not handoff_dir.exists() or list(handoff_dir.iterdir()) == [], (
        "AWH001 path must NOT write a partial envelope to disk"
    )


def test_malformed_payload_raises_in_strict_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Strict mode → ``finalize`` re-raises the AWH001 :class:`HookViolation`.

    The handler relies on ``dispatcher.finalize`` to escalate strict
    violations; this test pins that contract end-to-end.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload()
    payload["change_context"]["change_id"] = ""

    with pytest.raises(HookViolation) as exc_info:
        auto_write_handoff(payload, strict=True)
    assert exc_info.value.code == "AWH001"
    assert exc_info.value.severity == "error"


# ---------------------------------------------------------------------------
# Defensive layer extraction — lookup falls through to header / top-level
# ---------------------------------------------------------------------------


def test_layer_lookup_falls_through_to_lean_hdr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``hdr.from_layer`` / ``hdr.to_layer`` are picked up when ``change_context`` lacks them.

    Mirrors the cycle plan §PV-03 "be defensive" requirement —
    dispatchers may attach layer metadata to the lean ``hdr`` block
    (the lean dispatch envelope shape) instead of nesting under
    ``change_context``. The auto-write handler MUST find them either
    way.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload(from_layer="L0", to_layer="L2")
    del payload["change_context"]["from_layer"]
    del payload["change_context"]["to_layer"]
    payload["hdr"] = {"id": "d-001", "from_layer": "L1", "to_layer": "L2"}

    result = auto_write_handoff(payload)
    assert result.passed is True

    expected = _handoff_dir(tmp_path) / f"L1__L2__{_CHANGE_ID}__0001.yaml"
    assert expected.is_file()


def test_layer_lookup_falls_through_to_verbose_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``header.from_layer`` / ``header.to_layer`` (verbose) is the next fallback."""
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload(from_layer="L0", to_layer="L2")
    del payload["change_context"]["from_layer"]
    del payload["change_context"]["to_layer"]
    payload["header"] = {"from_layer": "L2", "to_layer": "L0"}

    result = auto_write_handoff(payload)
    assert result.passed is True

    expected = _handoff_dir(tmp_path) / f"L2__L0__{_CHANGE_ID}__0001.yaml"
    assert expected.is_file()


def test_layer_lookup_falls_through_to_top_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Top-level ``payload["from_layer"]`` / ``payload["to_layer"]`` is the final fallback."""
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload()
    del payload["change_context"]["from_layer"]
    del payload["change_context"]["to_layer"]
    payload["from_layer"] = "L0"
    payload["to_layer"] = "L1"

    result = auto_write_handoff(payload)
    assert result.passed is True

    expected = _handoff_dir(tmp_path) / f"L0__L1__{_CHANGE_ID}__0001.yaml"
    assert expected.is_file()


def test_dispatch_block_falls_back_to_top_level_task_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dispatch block extraction handles the verbose / non-lean shapes.

    When ``payload["task"]`` is absent, the handler falls back to
    top-level ``task_id`` / ``task_type``. Pins the
    ``_build_dispatch_block`` else-branch so the envelope stays
    well-formed under varied dispatcher metadata.
    """
    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    payload = _make_payload()
    del payload["task"]
    payload["task_id"] = "T-VERBOSE"
    payload["task_type"] = "review"

    result = auto_write_handoff(payload)
    assert result.passed is True

    expected = _handoff_dir(tmp_path) / f"L0__L2__{_CHANGE_ID}__0001.yaml"
    body = expected.read_text(encoding="utf-8")
    assert "task_id: T-VERBOSE" in body
    assert "type: review" in body


# ---------------------------------------------------------------------------
# S-5 unexpected exceptions are logged at WARNING and re-raised
# ---------------------------------------------------------------------------


def test_unexpected_exception_re_raises_with_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown exception (e.g. ``OSError``) → WARNING log + re-raise (S-5).

    The handler MUST NOT swallow truly unexpected exceptions; per
    Soul Rule S-5 (no silent failures) the failure is logged at
    WARNING via ``devolaflow.lifecycle.auto_write_handoff`` AND the
    original exception propagates to the caller. The ``_emit_dispatch``
    wrapper in feedback.py then catches it via its own try/except, so
    the dispatch path does not crash — but the audit trail stays loud.
    """
    import logging as _logging

    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    def boom(self, change_id: str) -> int:
        raise OSError("simulated disk full")

    monkeypatch.setattr(HandoffStore, "next_seq", boom)

    payload = _make_payload()
    with (
        caplog.at_level(_logging.WARNING, logger="devolaflow.lifecycle.auto_write_handoff"),
        pytest.raises(OSError, match="simulated disk full"),
    ):
        auto_write_handoff(payload)
    warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert any("auto_write_handoff" in rec.message for rec in warnings), (
        "S-5 violation: unexpected exception MUST emit a WARNING log before re-raising"
    )
