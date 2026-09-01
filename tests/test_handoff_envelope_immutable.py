"""Soul Rule S-9 enforcement: handoff envelopes are append-only.

Quoting ``.rules/soul.mdc`` §"S-9 — Handoff Envelopes Are Append-Only" verbatim:

    Once a ``<from>__<to>__<change-id>__<seq>.yaml`` envelope exists in
    ``.local/.agent/handoff/``, it MUST NOT be modified or deleted by any
    agent.

    To convey new information, the agent MUST author a new envelope with
    ``seq+1``.

Since v24.1.0 the rule carries the signed **S-9.1** amendment, which permits
one motion and no other: relocation of an already-archived change's envelopes
by the workspace-compact tool, under a matching approval fingerprint, with a
hashed mapping row. The relocation cases at the end of this file pin both
halves of that — what it allows and what it still refuses — because an
amendment tested only on its permitted path is indistinguishable from a
repeal.

    Rationale: append-only ledger prevents silent overwrites between agents
    operating in parallel. Mirrors P5 (Artifacts as Contracts).

    Enforcement: ``tests/test_handoff_envelope_immutable.py`` lints CI runs
    (lands in v8.2.4 with the schema package);
    ``lifecycle/check_envelope_append_only`` hook blocks at write time in
    STRICT mode.

    Source: v8.3.0 design.md §3.2 — closes gap H-002 from
    ``v8.3.0_gap_analysis.md``.

This file is the named enforcement surface that S-9 itself cites. It pins the
three invariants that keep the rule true at runtime:

1. ``write_envelope`` refuses seq-collisions AND leaves the existing on-disk
   file byte-for-byte unchanged (no silent overwrite per S-5).
2. ``HandoffStore``'s public surface exposes NO ``delete`` / ``remove`` /
   ``unlink`` API — the only mutation path is ``write_envelope``, and that
   method only accepts not-yet-existing seqs.
3. Sequence numbers MUST monotonically increase: ``seq=N+1`` succeeds after a
   committed ``seq=N``; reusing any earlier committed seq raises
   :exc:`EnvelopeImmutableError`.

The writer implementation under test lives at
``src/devolaflow/agent_workspace/handoff.py``. See also
``tests/test_agent_workspace.py::TestHandoffStore`` for broader store
coverage (write semantics, chronological reads, filename-vs-body
consistency); this file deliberately focuses on the IMMUTABILITY slice so
that a ``grep`` / docs search for "S-9" lands on the rule-quoted filename.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.agent_workspace.handoff import (
    EnvelopeImmutableError,
    HandoffEnvelope,
    HandoffStore,
    make_envelope,
)

_CHANGE_ID = "immut-demo"


def _make_handoff_store(tmp_path: Path) -> HandoffStore:
    """Return a ``HandoffStore`` rooted at ``tmp_path`` (no real repo writes).

    The handoff folder is pre-created so the first write does not race with
    directory creation inside ``write_envelope`` itself.
    """
    (tmp_path / ".local" / ".agent" / "handoff").mkdir(parents=True)
    return HandoffStore(repo_root=tmp_path)


def _make_dispatch(seq: int, change_id: str = _CHANGE_ID) -> HandoffEnvelope:
    """Build a minimal valid ``TaskDispatch`` envelope at ``seq``."""
    return make_envelope(
        seq=seq,
        from_layer="L0",
        to_layer="L2",
        change_id=change_id,
        envelope_kind="TaskDispatch",
        payload={
            "task_id": f"T-{seq:02d}",
            "type": "implement",
            "acceptance_criteria_ref": f".local/.agent/active/{change_id}/acceptance.md",
            "owned_files_ref": f".local/.agent/active/{change_id}/owned_files.txt",
        },
        created="2026-04-29T03:21:00Z",
    )


def test_envelope_file_cannot_be_overwritten_via_write_envelope(tmp_path: Path) -> None:
    """A second ``write_envelope`` at an existing seq MUST raise AND leave bytes intact.

    Pins S-9 clause 1 ("MUST NOT be modified") together with S-5 ("no silent
    failures"): the store is forbidden from silently dropping the second
    write, AND forbidden from silently replacing the first. The rejected
    second call uses a deliberately DIFFERENT payload so that any silent
    overwrite would be detectable as a byte-level diff on disk.
    """
    store = _make_handoff_store(tmp_path)
    path = store.write_envelope(_make_dispatch(seq=1))
    original_bytes = path.read_bytes()
    assert original_bytes, "precondition: first write must produce non-empty bytes"

    colliding = make_envelope(
        seq=1,
        from_layer="L0",
        to_layer="L2",
        change_id=_CHANGE_ID,
        envelope_kind="TaskDispatch",
        payload={
            "task_id": "T-99-OVERWRITE-ATTEMPT",
            "type": "review",
            "acceptance_criteria_ref": f".local/.agent/active/{_CHANGE_ID}/acceptance.md",
            "owned_files_ref": f".local/.agent/active/{_CHANGE_ID}/owned_files.txt",
        },
        created="2026-04-29T03:22:00Z",
    )

    with pytest.raises(EnvelopeImmutableError) as exc_info:
        store.write_envelope(colliding)

    assert "seq=2" in str(exc_info.value), (
        "S-9 enforcement contract: EnvelopeImmutableError MUST advise seq+1 so "
        "the calling agent knows how to recover (the rule body literally says "
        "'the agent MUST author a new envelope with seq+1')"
    )
    assert path.read_bytes() == original_bytes, (
        "S-9 VIOLATED: on-disk envelope bytes mutated after a rejected "
        "collision write; the append-only ledger must preserve committed bytes"
    )


def test_envelope_file_cannot_be_deleted_via_handoff_store_api(tmp_path: Path) -> None:
    """``HandoffStore``'s public surface MUST expose no delete/remove/unlink API.

    Pins S-9 clause 2 ("MUST NOT be ... deleted by any agent") at the API
    boundary: the only sanctioned way to mutate the ledger is
    ``write_envelope`` (append-only). If a future refactor adds a public
    ``delete_envelope`` / ``remove`` / ``unlink`` method, this test fails
    loudly so the rule is re-evaluated before the API ships.
    """
    store = _make_handoff_store(tmp_path)
    forbidden = {
        "delete",
        "delete_envelope",
        "remove",
        "remove_envelope",
        "unlink",
        "unlink_envelope",
        "pop",
        "clear",
        "purge",
    }
    exposed_callables = {
        name
        for name in dir(store)
        if not name.startswith("_") and callable(getattr(store, name, None))
    }

    overlap = exposed_callables & forbidden
    assert overlap == set(), (
        f"S-9 VIOLATED: HandoffStore exposes mutation API {sorted(overlap)!r}; "
        "the append-only contract forbids any delete/remove/unlink surface. "
        "Route writes through write_envelope (which refuses seq-collisions) "
        "and leave archival/rotation to ArchiveManager.archive instead."
    )
    for expected in ("write_envelope", "read_envelopes", "next_seq"):
        assert expected in exposed_callables, (
            f"HandoffStore is missing expected append-only API {expected!r}; "
            f"the immutability tests cannot run without it"
        )


def test_envelope_seq_must_monotonically_increase(tmp_path: Path) -> None:
    """``seq=N+1`` is accepted after committed ``seq=N``; reusing any earlier seq raises.

    Pins S-9's recovery clause ("the agent MUST author a new envelope with
    seq+1") AND the append-only invariant end-to-end: the store accepts
    strictly-increasing seq values, rejects every prior seq with
    :exc:`EnvelopeImmutableError`, and preserves all committed envelopes
    across rejected writes so the audit trail stays complete.
    """
    store = _make_handoff_store(tmp_path)

    first_path = store.write_envelope(_make_dispatch(seq=1))
    assert first_path.exists(), "precondition: seq=1 write must commit"

    second_path = store.write_envelope(_make_dispatch(seq=2))
    assert second_path.exists(), "monotonic seq=2 write must succeed"
    assert second_path != first_path, "distinct seqs must land in distinct files"

    assert store.next_seq(_CHANGE_ID) == 3, (
        "next_seq must reflect the max committed seq + 1 per handoff.py contract"
    )

    with pytest.raises(EnvelopeImmutableError):
        store.write_envelope(_make_dispatch(seq=1))
    with pytest.raises(EnvelopeImmutableError):
        store.write_envelope(_make_dispatch(seq=2))

    survivors = store.read_envelopes(_CHANGE_ID)
    assert [e.seq for e in survivors] == [1, 2], (
        "S-9 VIOLATED: rejected collision writes corrupted the committed ledger; "
        "the append-only audit trail must survive every rejected reuse attempt"
    )


# --------------------------------------------------------------------------
# S-9.1 — tool-mediated relocation of archived-change envelopes (v24.1.0)
# --------------------------------------------------------------------------


def _archive_change(tmp_path: Path, change_id: str = _CHANGE_ID) -> None:
    """Create the whole-change archive folder S-9.1 condition 1 requires."""
    (tmp_path / ".local" / ".agent" / "archive" / f"2026-09-01-{change_id}").mkdir(parents=True)


def test_relocation_moves_an_archived_change_envelope_without_changing_content(
    tmp_path: Path,
) -> None:
    """S-9.1 permits the move and the content survives it byte for byte.

    The amendment's whole claim is that relocation changes location and
    nothing else, so this asserts on the bytes rather than on the tool's own
    report of success.
    """
    from devolaflow.workspace_compact.handoff_relocate import (
        apply_relocation,
        plan_relocation,
        verify_relocations,
    )

    store = _make_handoff_store(tmp_path)
    source_path = store.write_envelope(_make_dispatch(seq=1))
    original_bytes = source_path.read_bytes()
    _archive_change(tmp_path)

    plan = plan_relocation(tmp_path)
    assert [item.seq for item in plan.candidates] == [1], (
        f"an archived change's envelope must be eligible; refused={plan.refused}"
    )

    result = apply_relocation(tmp_path, plan, approval_fingerprint=plan.fingerprint)
    assert result.success, result.findings
    assert not source_path.exists(), "relocation must vacate the handoff directory"

    destination = tmp_path / plan.candidates[0].destination
    assert destination.read_bytes() == original_bytes, (
        "S-9.1 VIOLATED: relocation altered envelope content; the amendment "
        "permits a change of location only"
    )
    assert verify_relocations(tmp_path) == (), "the relocation ledger must verify clean"


def test_relocation_refuses_an_active_change_envelope(tmp_path: Path) -> None:
    """Without the whole-change archive folder, nothing is eligible.

    Pins S-9.1 condition 1. The append-only sequence is most valuable while
    parallel agents are still appending to it, which is exactly when this
    refusal applies.
    """
    from devolaflow.workspace_compact.handoff_relocate import plan_relocation

    store = _make_handoff_store(tmp_path)
    store.write_envelope(_make_dispatch(seq=1))

    plan = plan_relocation(tmp_path)
    assert plan.candidates == (), "an active change's envelope must never be a candidate"
    assert any("CHANGE_STILL_ACTIVE" in item for item in plan.refused), (
        f"the refusal must be explicit rather than a silent omission (S-5): {plan.refused}"
    )


def test_relocation_refuses_a_mismatched_approval(tmp_path: Path) -> None:
    """Pins S-9.1 condition 3: the fingerprint must match the plan that was read."""
    from devolaflow.workspace_compact.handoff_relocate import apply_relocation, plan_relocation

    store = _make_handoff_store(tmp_path)
    source_path = store.write_envelope(_make_dispatch(seq=1))
    _archive_change(tmp_path)
    plan = plan_relocation(tmp_path)

    result = apply_relocation(tmp_path, plan, approval_fingerprint="not-the-fingerprint")
    assert result.refused, "a mismatched approval must refuse the whole relocation"
    assert source_path.exists(), "a refused relocation must leave the envelope in place"


def test_relocation_ledger_detects_post_move_tampering(tmp_path: Path) -> None:
    """`verify_relocations` makes the zero-change claim falsifiable after the fact."""
    from devolaflow.workspace_compact.handoff_relocate import (
        apply_relocation,
        plan_relocation,
        verify_relocations,
    )

    store = _make_handoff_store(tmp_path)
    store.write_envelope(_make_dispatch(seq=1))
    _archive_change(tmp_path)
    plan = plan_relocation(tmp_path)
    result = apply_relocation(tmp_path, plan, approval_fingerprint=plan.fingerprint)
    assert result.success, result.findings

    relocated = tmp_path / plan.candidates[0].destination
    relocated.write_text(relocated.read_text(encoding="utf-8") + "\ntampered: true\n")

    problems = verify_relocations(tmp_path)
    assert any("HASH_MISMATCH" in item for item in problems), (
        f"tampering after relocation must be detectable from the ledger: {problems}"
    )


def test_hook_permits_a_fully_conditioned_relocation() -> None:
    """All four S-9.1 conditions met: the hook returns clean."""
    from devolaflow.lifecycle.check_envelope_append_only import (
        RELOCATION_TOOL,
        check_envelope_append_only,
    )

    result = check_envelope_append_only(
        {
            "operation": "relocate",
            "path": ".local/.agent/handoff/L0__L2__demo__0001.yaml",
            "existing_paths": [],
            "change_archived": True,
            "approval_fingerprint": "abc123",
            "tool": RELOCATION_TOOL,
        },
        strict=True,
    )
    assert not result.violations, result.violations


def test_hook_blocks_relocation_of_an_unarchived_change() -> None:
    """A missing condition reads as unmet, never as presumably fine."""
    from devolaflow.lifecycle.check_envelope_append_only import (
        RELOCATION_TOOL,
        check_envelope_append_only,
    )
    from devolaflow.lifecycle.dispatcher import HookViolation

    with pytest.raises(HookViolation) as exc_info:
        check_envelope_append_only(
            {
                "operation": "relocate",
                "path": ".local/.agent/handoff/L0__L2__demo__0001.yaml",
                "existing_paths": [],
                "approval_fingerprint": "abc123",
                "tool": RELOCATION_TOOL,
            },
            strict=True,
        )
    assert exc_info.value.code == "CEA004"
    assert exc_info.value.severity == "blocker"


def test_hook_blocks_a_hand_rolled_relocation() -> None:
    """S-9.1 condition 2: only the workspace-compact tool may move an envelope."""
    from devolaflow.lifecycle.check_envelope_append_only import check_envelope_append_only
    from devolaflow.lifecycle.dispatcher import HookViolation

    with pytest.raises(HookViolation) as exc_info:
        check_envelope_append_only(
            {
                "operation": "relocate",
                "path": ".local/.agent/handoff/L0__L2__demo__0001.yaml",
                "existing_paths": [],
                "change_archived": True,
                "approval_fingerprint": "abc123",
                "tool": "shutil.move",
            },
            strict=True,
        )
    assert "not the sanctioned" in str(exc_info.value)


def test_hook_still_blocks_overwrite_when_operation_is_absent() -> None:
    """The amendment is additive: the original S-9 branch is unchanged.

    An amendment that quietly relaxes the rule it amends is the failure mode
    worth pinning, so this re-asserts the pre-v24.1.0 behaviour explicitly.
    """
    from devolaflow.lifecycle.check_envelope_append_only import check_envelope_append_only
    from devolaflow.lifecycle.dispatcher import HookViolation

    path = ".local/.agent/handoff/L0__L2__demo__0001.yaml"
    with pytest.raises(HookViolation) as exc_info:
        check_envelope_append_only({"path": path, "existing_paths": [path]}, strict=True)
    assert exc_info.value.code == "CEA001"
