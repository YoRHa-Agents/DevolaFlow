"""Tests for the v8.2.5 ``devolaflow.agent_workspace`` package.

Covers AC-1 through AC-9 from ``.local/research/v8.3.0_patch_plan.md`` §v8.2.5:

* AC-1: public-API import surface (Change, ChangeStore, HandoffEnvelope,
  HandoffStore, ArchiveManager, parse_delta_spec, lint_change, plus the
  exception classes).
* AC-2: ``Change.from_active_folder(p).to_active_folder(p2)`` round-trip
  byte-identity across multiple realistic fixtures.
* AC-3: ``HandoffStore.write_envelope`` raises EnvelopeImmutableError on
  seq collision; ``read_envelopes`` returns chronological order.
* AC-4: ``ArchiveManager.archive`` moves folder, sets state=ARCHIVED,
  preserves all artifacts, idempotent.
* AC-5: ``ArchiveManager.propose_merge`` produces proposed merged content
  + target path; does NOT write to disk.
* AC-6: ``python -m devolaflow.agent_workspace.lint <id>`` enforces
  budgets — non-zero exit on hard ceiling, warn on soft.
* AC-7: ``parse_delta_spec`` extracts ADDED / MODIFIED / REMOVED with
  stable headings.
* AC-9: ≥ 80 % coverage on ``src/devolaflow/agent_workspace/`` (verified
  by ``--cov`` invocation in v8.2.5 Final Verification step).

Tests use ``tmp_path`` exclusively — no dependency on a real
``.local/.agent/`` tree on disk.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace import (
    AppliedMerge,
    ArchiveError,
    ArchiveManager,
    BudgetReport,
    Change,
    ChangeNotFoundError,
    ChangeStore,
    ChangeStoreError,
    DeltaSpecParseError,
    EnvelopeImmutableError,
    GateThresholdNotMet,
    HandoffEnvelope,
    HandoffStore,
    HandoffStoreError,
    MergeConflict,
    estimate_tokens,
    lint_change,
    parse_delta_spec,
    serialize_delta_spec,
)
from devolaflow.agent_workspace.handoff import make_envelope
from devolaflow.agent_workspace.lint import main as lint_main

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Return ``tmp_path`` configured as a DevolaFlow repo root with empty subdirs."""
    (tmp_path / ".local" / ".agent" / "active").mkdir(parents=True)
    (tmp_path / ".local" / ".agent" / "handoff").mkdir(parents=True)
    (tmp_path / ".local" / ".agent" / "archive").mkdir(parents=True)
    (tmp_path / ".local" / "memory" / "specs").mkdir(parents=True)
    return tmp_path


def _scaffold_active(workspace: Path, change_id: str, **overrides) -> Path:
    """Create a minimal valid active change folder under ``workspace``.

    ``overrides`` lets a test pin specific artifact contents (e.g.
    ``status=...`` to test FSM transitions).
    """
    folder = workspace / ".local" / ".agent" / "active" / change_id
    folder.mkdir(parents=True, exist_ok=True)

    goal = overrides.get(
        "goal_md",
        textwrap.dedent(
            f"""\
            ---
            id: {change_id}
            created: "2026-04-22T10:14:33Z"
            priority: P2
            intent_class: feature
            ---

            # Goal: Sample change for {change_id}

            ## Why
            Testing.

            ## In scope
            - Tests pass

            ## Out of scope
            - Real users
            """
        ),
    )
    acceptance = overrides.get(
        "acceptance_md",
        textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            ac_count: 4
            ---

            # Acceptance Criteria

            ## Functional
            - [ ] AC-1: It works

            ## Quality
            - [ ] AC-2: tests pass — `pytest tests/test_x.py`
            - [ ] AC-3: ruff check
            - [ ] AC-4: ruff format --check
            """
        ),
    )
    spec = overrides.get(
        "spec_md",
        textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            delta_target: agent_workspace
            delta_kind: lite
            ---

            # Operation Spec for {change_id}

            ## Purpose
            Sample purpose for {change_id}.

            ## ADDED Requirements

            ### Requirement: Sample requirement
            The system MUST do something testable.

            #### Scenario: A test runs
            - GIVEN the test fixture
            - WHEN we run pytest
            - THEN it passes
            """
        ),
    )
    tasks = overrides.get(
        "tasks_md",
        textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            total_tasks: 2
            checked: 0
            ---

            # Tasks

            ## 1. Implementation
            - [ ] 1.1 Write code
            - [ ] 1.2 Write tests
            """
        ),
    )
    status = overrides.get(
        "status",
        {
            "schema_version": 1,
            "change_id": change_id,
            "state": "IN_PROGRESS",
            "percent_complete": 50,
            "owner_layer": "L3",
            "owner_session_id": "test-session",
            "last_updated": "2026-04-22T11:02:18Z",
            "last_handoff_seq": 0,
            "gate_score": None,
            "verify_pass": None,
        },
    )
    owned_files = overrides.get(
        "owned_files",
        ["src/devolaflow/agent_workspace/change.py", "tests/test_agent_workspace.py"],
    )
    learnings_jsonl = overrides.get("learnings_jsonl")

    (folder / "goal.md").write_text(goal, encoding="utf-8")
    (folder / "acceptance.md").write_text(acceptance, encoding="utf-8")
    (folder / "spec.md").write_text(spec, encoding="utf-8")
    (folder / "tasks.md").write_text(tasks, encoding="utf-8")
    (folder / "STATUS.yaml").write_text(
        yaml.safe_dump(status, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    (folder / "owned_files.txt").write_text(
        "\n".join(owned_files) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if learnings_jsonl is not None:
        (folder / "learnings.jsonl").write_text(learnings_jsonl, encoding="utf-8", newline="\n")

    return folder


# ---------------------------------------------------------------------------
# AC-1 — public API surface
# ---------------------------------------------------------------------------


class TestPublicApiSurface:
    def test_required_symbols_exported(self):
        from devolaflow import agent_workspace

        for name in (
            "Change",
            "ChangeStore",
            "HandoffEnvelope",
            "HandoffStore",
            "ArchiveManager",
            "parse_delta_spec",
            "lint_change",
            "EnvelopeImmutableError",
        ):
            assert hasattr(agent_workspace, name), f"missing public symbol {name!r}"
            assert name in agent_workspace.__all__, f"{name!r} not in __all__"

    def test_exception_hierarchy(self):
        # EnvelopeImmutableError is a HandoffStoreError subclass (callers can
        # catch the parent if they don't care about the specific reason).
        assert issubclass(EnvelopeImmutableError, HandoffStoreError)
        assert issubclass(MergeConflict, ArchiveError)
        assert issubclass(ChangeNotFoundError, ChangeStoreError)


# ---------------------------------------------------------------------------
# AC-2 — Change round-trip byte-identity
# ---------------------------------------------------------------------------


class TestChangeRoundTrip:
    def test_round_trip_byte_identical_minimal(self, workspace: Path):
        folder = _scaffold_active(workspace, "round-trip-min")
        loaded = Change.from_active_folder(folder)
        target = workspace / "out" / "round-trip-min"
        loaded.to_active_folder(target)

        for filename in (
            "goal.md",
            "acceptance.md",
            "spec.md",
            "tasks.md",
            "owned_files.txt",
        ):
            src = (folder / filename).read_text(encoding="utf-8")
            dst = (target / filename).read_text(encoding="utf-8")
            assert src == dst, f"{filename} not byte-identical after round-trip"

        # STATUS.yaml is re-rendered via yaml.safe_dump; verify semantically equal.
        src_status = yaml.safe_load((folder / "STATUS.yaml").read_text(encoding="utf-8"))
        dst_status = yaml.safe_load((target / "STATUS.yaml").read_text(encoding="utf-8"))
        assert src_status == dst_status

    def test_round_trip_with_learnings_jsonl(self, workspace: Path):
        learnings = '{"key":"k1","stage":"impl","task_type":"test","confidence":0.9}\n'
        folder = _scaffold_active(workspace, "rt-learn", learnings_jsonl=learnings)
        loaded = Change.from_active_folder(folder)
        target = workspace / "out" / "rt-learn"
        loaded.to_active_folder(target)
        assert (target / "learnings.jsonl").read_text(encoding="utf-8") == learnings

    def test_round_trip_double_hop_stable(self, workspace: Path):
        """Loading + writing + re-loading + re-writing produces identical bytes."""
        folder = _scaffold_active(workspace, "rt-double")
        change = Change.from_active_folder(folder)
        out1 = workspace / "out1" / "rt-double"
        change.to_active_folder(out1)
        change2 = Change.from_active_folder(out1)
        out2 = workspace / "out2" / "rt-double"
        change2.to_active_folder(out2)
        # Compare every artifact byte-by-byte between out1 and out2.
        for artifact in (
            "goal.md",
            "acceptance.md",
            "spec.md",
            "tasks.md",
            "STATUS.yaml",
            "owned_files.txt",
        ):
            assert (out1 / artifact).read_bytes() == (out2 / artifact).read_bytes(), (
                f"{artifact} drift between hop 1 and hop 2"
            )

    def test_load_missing_status_raises(self, workspace: Path):
        folder = workspace / ".local" / ".agent" / "active" / "no-status"
        folder.mkdir(parents=True)
        (folder / "goal.md").write_text("# stub", encoding="utf-8")
        with pytest.raises(ChangeStoreError) as exc_info:
            Change.from_active_folder(folder)
        assert "STATUS.yaml" in str(exc_info.value)

    def test_load_missing_folder_raises(self, workspace: Path):
        with pytest.raises(ChangeNotFoundError):
            Change.from_active_folder(workspace / ".local" / ".agent" / "active" / "missing")

    def test_change_state_property_accessors(self, workspace: Path):
        folder = _scaffold_active(workspace, "props")
        change = Change.from_active_folder(folder)
        assert change.state == "IN_PROGRESS"
        assert change.percent_complete == 50
        assert change.last_handoff_seq == 0
        assert change.change_id == "props"

    def test_with_state_legal_transition(self, workspace: Path):
        folder = _scaffold_active(workspace, "trans")
        change = Change.from_active_folder(folder)
        verified = change.with_state("VERIFYING")
        assert verified.state == "VERIFYING"
        # Original is not mutated.
        assert change.state == "IN_PROGRESS"

    def test_with_state_illegal_transition_raises(self, workspace: Path):
        folder = _scaffold_active(workspace, "illegal")
        change = Change.from_active_folder(folder)
        # IN_PROGRESS → ARCHIVED is NOT in the FSM.
        with pytest.raises(ChangeStoreError) as exc_info:
            change.with_state("ARCHIVED")
        assert "illegal state transition" in str(exc_info.value)

    def test_with_state_unknown_state_raises(self, workspace: Path):
        folder = _scaffold_active(workspace, "unknown")
        change = Change.from_active_folder(folder)
        with pytest.raises(ChangeStoreError):
            change.with_state("BOGUS")


# ---------------------------------------------------------------------------
# v10.7.0 D-P-3 — STATUS.yaml NEST extensibility demo
# ---------------------------------------------------------------------------


class TestStatusYamlNestExtensibility:
    """v10.7.0 D-P-3 — A-2.3 NEST-vs-APPEND demonstration.

    The new ``last_handoff_summary`` optional field is a dict-shaped
    NEST (``{from_layer, to_layer, ts, seq}``) at the top of the
    STATUS.yaml mapping. We exercise three contracts:

    1. Absence is the canonical default — v8.3.0..v10.6.x STATUS.yaml
       files (those without the field) load + round-trip cleanly and
       the accessor returns ``None``.
    2. Presence round-trips byte-stable through
       ``Change.from_active_folder().to_active_folder()``.
    3. The accessor returns the dict verbatim (keys preserved); when the
       field is explicitly ``null`` (the schema's nullable contract),
       the accessor coerces to ``None``.
    """

    def test_absent_field_returns_none_and_round_trips(self, workspace: Path) -> None:
        # Default fixture omits last_handoff_summary entirely.
        folder = _scaffold_active(workspace, "nest-absent")
        change = Change.from_active_folder(folder)
        assert change.last_handoff_summary is None

        target = workspace / "out" / "nest-absent"
        change.to_active_folder(target)
        re_read = Change.from_active_folder(target)
        assert re_read.last_handoff_summary is None
        # The absent field MUST NOT be injected on round-trip (schema
        # contract: absence is canonical default; refusing to inject a
        # default would otherwise force schema_version bump).
        assert "last_handoff_summary" not in re_read.status

    def test_present_field_round_trips_byte_stable(self, workspace: Path) -> None:
        summary = {
            "from_layer": "L2",
            "to_layer": "L3",
            "ts": "2026-05-04T12:34:56Z",
            "seq": 4,
        }
        status = {
            "schema_version": 1,
            "change_id": "nest-present",
            "state": "IN_PROGRESS",
            "percent_complete": 60,
            "owner_layer": "L3",
            "owner_session_id": "test-nest-present",
            "last_updated": "2026-05-04T12:34:56Z",
            "last_handoff_seq": 4,
            "gate_score": None,
            "verify_pass": None,
            "last_handoff_summary": summary,
        }
        folder = _scaffold_active(workspace, "nest-present", status=status)
        change = Change.from_active_folder(folder)
        assert change.last_handoff_summary == summary
        # Schema invariant: last_handoff_summary.seq MUST equal last_handoff_seq.
        assert change.last_handoff_summary["seq"] == change.last_handoff_seq

        target = workspace / "out" / "nest-present"
        change.to_active_folder(target)
        re_read = Change.from_active_folder(target)
        assert re_read.last_handoff_summary == summary
        # Byte-stable double-hop (out1 STATUS.yaml == out2 STATUS.yaml).
        out1 = workspace / "out1" / "nest-present"
        change.to_active_folder(out1)
        re_read.to_active_folder(target)
        assert (target / "STATUS.yaml").read_bytes() == (out1 / "STATUS.yaml").read_bytes()

    def test_explicit_null_returns_none_per_nullable_contract(self, workspace: Path) -> None:
        status = {
            "schema_version": 1,
            "change_id": "nest-null",
            "state": "IN_PROGRESS",
            "percent_complete": 10,
            "owner_layer": "L3",
            "owner_session_id": "test-nest-null",
            "last_updated": "2026-05-04T01:02:03Z",
            "last_handoff_seq": 0,
            "gate_score": None,
            "verify_pass": None,
            "last_handoff_summary": None,  # explicit null per schema's nullable contract
        }
        folder = _scaffold_active(workspace, "nest-null", status=status)
        change = Change.from_active_folder(folder)
        # Explicit null must coerce to None (matches the absent-field path).
        assert change.last_handoff_summary is None


# ---------------------------------------------------------------------------
# ChangeStore tests
# ---------------------------------------------------------------------------


class TestChangeStore:
    def test_list_active_returns_sorted_ids(self, workspace: Path):
        for cid in ("c-second", "a-first", "b-middle"):
            _scaffold_active(workspace, cid)
        store = ChangeStore(repo_root=workspace)
        assert store.list_active() == ["a-first", "b-middle", "c-second"]

    def test_list_active_skips_non_directories(self, workspace: Path):
        _scaffold_active(workspace, "real-one")
        # Drop a stray file at active root.
        (workspace / ".local" / ".agent" / "active" / ".gitkeep").write_text("")
        store = ChangeStore(repo_root=workspace)
        assert store.list_active() == ["real-one"]

    def test_get_active_change(self, workspace: Path):
        _scaffold_active(workspace, "lookup-a")
        store = ChangeStore(repo_root=workspace)
        change = store.get("lookup-a")
        assert change.change_id == "lookup-a"

    def test_get_unknown_raises(self, workspace: Path):
        store = ChangeStore(repo_root=workspace)
        with pytest.raises(ChangeNotFoundError):
            store.get("missing-id")

    def test_transition_state_writes_status(self, workspace: Path):
        _scaffold_active(workspace, "trans-write")
        store = ChangeStore(repo_root=workspace)
        store.transition_state("trans-write", "VERIFYING")
        change = store.get("trans-write")
        assert change.state == "VERIFYING"

    def test_move_to_archive_relocates_folder(self, workspace: Path):
        _scaffold_active(workspace, "to-archive")
        store = ChangeStore(repo_root=workspace)
        archive_path = store.move_to_archive("to-archive", archive_date="2026-04-22")
        assert archive_path.is_dir()
        assert archive_path.name == "2026-04-22-to-archive"
        assert not (workspace / ".local" / ".agent" / "active" / "to-archive").exists()

    def test_move_to_archive_collision_raises(self, workspace: Path):
        _scaffold_active(workspace, "collide")
        store = ChangeStore(repo_root=workspace)
        store.move_to_archive("collide", archive_date="2026-04-22")
        # Re-create active folder with same id, attempt second archive at same date.
        _scaffold_active(workspace, "collide")
        with pytest.raises(ChangeStoreError) as exc_info:
            store.move_to_archive("collide", archive_date="2026-04-22")
        assert "already exists" in str(exc_info.value)

    def test_list_archive_returns_date_pairs(self, workspace: Path):
        _scaffold_active(workspace, "arch-1")
        _scaffold_active(workspace, "arch-2")
        store = ChangeStore(repo_root=workspace)
        store.move_to_archive("arch-1", archive_date="2026-04-22")
        store.move_to_archive("arch-2", archive_date="2026-04-21")
        rows = store.list_archive()
        assert ("2026-04-21", "arch-2") in rows
        assert ("2026-04-22", "arch-1") in rows
        # Sorted: 2026-04-21 first.
        assert rows[0][0] == "2026-04-21"

    def test_has_active_and_has_archived(self, workspace: Path):
        _scaffold_active(workspace, "a-only")
        _scaffold_active(workspace, "to-arch")
        store = ChangeStore(repo_root=workspace)
        store.move_to_archive("to-arch", archive_date="2026-04-22")
        assert store.has_active("a-only")
        assert not store.has_active("to-arch")
        assert store.has_archived("to-arch")
        assert not store.has_archived("a-only")


# ---------------------------------------------------------------------------
# AC-3 + handoff envelope tests
# ---------------------------------------------------------------------------


class TestHandoffEnvelope:
    def test_make_envelope_dispatch_validates(self):
        env = make_envelope(
            seq=1,
            from_layer="L0",
            to_layer="L2",
            change_id="add-foo",
            envelope_kind="TaskDispatch",
            payload={
                "task_id": "T01",
                "type": "implement",
                "acceptance_criteria_ref": ".local/.agent/active/add-foo/acceptance.md",
                "owned_files_ref": ".local/.agent/active/add-foo/owned_files.txt",
            },
            created="2026-04-22T10:14:33Z",
        )
        assert env.envelope_kind == "TaskDispatch"
        assert env.dispatch is not None
        assert env.report is None
        assert env.escalation is None

    def test_make_envelope_status_report(self):
        env = make_envelope(
            seq=2,
            from_layer="L3",
            to_layer="L2",
            change_id="add-foo",
            envelope_kind="StatusReport",
            payload={"task_id": "T01", "state": "completed"},
            created="2026-04-22T10:14:34Z",
        )
        assert env.envelope_kind == "StatusReport"
        assert env.report is not None
        assert env.dispatch is None

    def test_validate_self_handoff_rejected(self):
        with pytest.raises(HandoffStoreError) as exc_info:
            make_envelope(
                seq=1,
                from_layer="L2",
                to_layer="L2",
                change_id="add-foo",
                envelope_kind="TaskDispatch",
                payload={
                    "task_id": "T01",
                    "type": "implement",
                    "acceptance_criteria_ref": ".local/.agent/active/add-foo/acceptance.md",
                    "owned_files_ref": ".local/.agent/active/add-foo/owned_files.txt",
                },
                created="2026-04-22T10:14:33Z",
            )
        assert "self-handoff" in str(exc_info.value)

    def test_validate_unknown_envelope_kind(self):
        with pytest.raises(HandoffStoreError):
            make_envelope(
                seq=1,
                from_layer="L0",
                to_layer="L2",
                change_id="add-foo",
                envelope_kind="Bogus",
                payload={},
            )

    def test_validate_seq_out_of_range(self):
        env = HandoffEnvelope(
            seq=0,
            from_layer="L0",
            to_layer="L2",
            change_id="add-foo",
            created="2026-04-22T10:14:33Z",
            envelope_kind="TaskDispatch",
            dispatch={"task_id": "T01"},
        )
        with pytest.raises(HandoffStoreError):
            env.validate()

    def test_filename_pattern_round_trip(self):
        env = make_envelope(
            seq=42,
            from_layer="L0",
            to_layer="L3",
            change_id="add-foo",
            envelope_kind="StatusReport",
            payload={"task_id": "T-42", "state": "completed"},
            created="2026-04-22T10:14:33Z",
        )
        assert env.filename == "L0__L3__add-foo__0042.yaml"

    def test_yaml_serialise_deserialise(self):
        env = make_envelope(
            seq=7,
            from_layer="L3",
            to_layer="L0",
            change_id="add-foo",
            envelope_kind="EscalationEvent",
            payload={
                "severity": "HUMAN_INTERVENE",
                "trigger": "P4 retry exhausted",
                "proposed_action": "Pause for human input",
            },
            created="2026-04-22T10:14:33Z",
        )
        text = env.to_yaml()
        roundtripped = HandoffEnvelope.from_yaml(text)
        assert roundtripped.seq == env.seq
        assert roundtripped.envelope_kind == env.envelope_kind
        assert roundtripped.escalation == env.escalation


class TestHandoffStore:
    def _make(self, seq: int, change_id: str = "add-foo") -> HandoffEnvelope:
        return make_envelope(
            seq=seq,
            from_layer="L0",
            to_layer="L2",
            change_id=change_id,
            envelope_kind="TaskDispatch",
            payload={
                "task_id": f"T{seq:02d}",
                "type": "implement",
                "acceptance_criteria_ref": f".local/.agent/active/{change_id}/acceptance.md",
                "owned_files_ref": f".local/.agent/active/{change_id}/owned_files.txt",
            },
            created="2026-04-22T10:14:33Z",
        )

    def test_write_envelope_creates_file(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        path = store.write_envelope(self._make(1))
        assert path.exists()
        assert path.name == "L0__L2__add-foo__0001.yaml"

    def test_write_envelope_collision_raises(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        store.write_envelope(self._make(1))
        with pytest.raises(EnvelopeImmutableError) as exc_info:
            store.write_envelope(self._make(1))
        assert "seq=2" in str(exc_info.value), (
            "EnvelopeImmutableError MUST suggest seq+1 in its message"
        )

    def test_next_seq_starts_at_one(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        assert store.next_seq("add-foo") == 1

    def test_next_seq_increments(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        store.write_envelope(self._make(1))
        store.write_envelope(self._make(2))
        assert store.next_seq("add-foo") == 3

    def test_read_envelopes_chronological_order(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        # Write in REVERSE order to prove the reader sorts.
        store.write_envelope(self._make(3))
        store.write_envelope(self._make(1))
        store.write_envelope(self._make(2))
        envelopes = store.read_envelopes("add-foo")
        assert [e.seq for e in envelopes] == [1, 2, 3]

    def test_read_envelopes_filters_by_change_id(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        store.write_envelope(self._make(1, change_id="add-foo"))
        store.write_envelope(self._make(1, change_id="add-bar"))
        foo = store.read_envelopes("add-foo")
        bar = store.read_envelopes("add-bar")
        assert len(foo) == 1 and foo[0].change_id == "add-foo"
        assert len(bar) == 1 and bar[0].change_id == "add-bar"

    def test_read_envelopes_detects_filename_seq_mismatch(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        store.write_envelope(self._make(1))
        # Hand-corrupt the file so seq inside YAML disagrees with filename.
        corrupted = store.handoff_root / "L0__L2__add-foo__0001.yaml"
        text = corrupted.read_text(encoding="utf-8").replace("seq: 1", "seq: 99")
        corrupted.write_text(text, encoding="utf-8")
        with pytest.raises(HandoffStoreError) as exc_info:
            store.read_envelopes("add-foo")
        assert "filename seq" in str(exc_info.value)

    def test_read_envelopes_empty_returns_empty_list(self, workspace: Path):
        store = HandoffStore(repo_root=workspace)
        assert store.read_envelopes("nonexistent") == []


# ---------------------------------------------------------------------------
# AC-7 — delta-spec parser
# ---------------------------------------------------------------------------


class TestDeltaParser:
    SPEC_VALID = textwrap.dedent(
        """\
        ---
        parent: add-dark-mode
        delta_target: agent_workspace
        delta_kind: lite
        ---

        # Operation Spec for add-dark-mode

        ## Purpose
        Add dark-mode toggle to demo dashboard.

        ## ADDED Requirements

        ### Requirement: Dark palette
        The system MUST expose --devola-bg-dark / --devola-fg-dark CSS variables.

        #### Scenario: Toggle dark mode
        - GIVEN a user clicks the toggle
        - WHEN dark mode is enabled
        - THEN the page applies the dark palette within 100 ms.

        ### Requirement: Persisted choice
        The system MUST persist the choice via localStorage key `devola.theme`.

        ## MODIFIED Requirements

        ### Requirement: Existing palette token
        The system uses a single light palette only.
        (Previously: two-palette light-only.)

        ## REMOVED Requirements

        ### Requirement: Auto-detect system theme
        (Defer to v8.4.0 — out of scope for this change.)
        """
    )

    def test_parse_valid_spec_returns_three_sections(self):
        spec = parse_delta_spec(self.SPEC_VALID)
        assert len(spec.added) == 2
        assert len(spec.modified) == 1
        assert len(spec.removed) == 1

    def test_parse_extracts_stable_headings(self):
        spec = parse_delta_spec(self.SPEC_VALID)
        added_headings = [r.heading for r in spec.added]
        assert "Dark palette" in added_headings
        assert "Persisted choice" in added_headings

    def test_parse_preserves_purpose_text(self):
        spec = parse_delta_spec(self.SPEC_VALID)
        assert "dark-mode toggle" in spec.purpose

    def test_parse_extracts_frontmatter(self):
        spec = parse_delta_spec(self.SPEC_VALID)
        assert spec.frontmatter["parent"] == "add-dark-mode"
        assert spec.frontmatter["delta_target"] == "agent_workspace"
        assert spec.frontmatter["delta_kind"] == "lite"

    def test_parse_no_delta_sections_raises(self):
        bad = textwrap.dedent(
            """\
            ---
            parent: foo
            delta_target: x
            delta_kind: lite
            ---

            # Operation Spec for foo

            ## Purpose
            No delta sections present.
            """
        )
        with pytest.raises(DeltaSpecParseError) as exc_info:
            parse_delta_spec(bad)
        assert "ADDED" in str(exc_info.value) or "delta" in str(exc_info.value).lower()

    def test_parse_unclosed_frontmatter_raises(self):
        with pytest.raises(DeltaSpecParseError):
            parse_delta_spec("---\nparent: foo\n# no closing")

    def test_parse_non_string_raises(self):
        with pytest.raises(DeltaSpecParseError):
            parse_delta_spec(None)  # type: ignore[arg-type]

    def test_section_accessor_unknown_kind(self):
        spec = parse_delta_spec(self.SPEC_VALID)
        with pytest.raises(KeyError):
            spec.section("BOGUS")

    def test_round_trip_serialize_then_parse(self):
        spec = parse_delta_spec(self.SPEC_VALID)
        rendered = serialize_delta_spec(spec)
        re_parsed = parse_delta_spec(rendered)
        assert len(re_parsed.added) == len(spec.added)
        assert len(re_parsed.modified) == len(spec.modified)
        assert len(re_parsed.removed) == len(spec.removed)
        # Headings preserved verbatim.
        for orig, again in zip(spec.added, re_parsed.added, strict=True):
            assert orig.heading == again.heading

    def test_added_only_spec_parses(self):
        spec_text = textwrap.dedent(
            """\
            ---
            parent: minimal
            delta_target: foo
            delta_kind: lite
            ---

            # Operation Spec for minimal

            ## Purpose
            Just one ADDED.

            ## ADDED Requirements

            ### Requirement: Only one
            The system MUST do this.
            """
        )
        spec = parse_delta_spec(spec_text)
        assert len(spec.added) == 1
        assert len(spec.modified) == 0
        assert len(spec.removed) == 0
        assert spec.has_any_delta()

    def test_all_requirements_canonical_order(self):
        spec = parse_delta_spec(self.SPEC_VALID)
        flat = spec.all_requirements()
        kinds = [k for k, _ in flat]
        # Order: ADDED items first, then MODIFIED, then REMOVED.
        assert kinds == ["ADDED", "ADDED", "MODIFIED", "REMOVED"]


# ---------------------------------------------------------------------------
# AC-4 + AC-5 — ArchiveManager
# ---------------------------------------------------------------------------


class TestArchiveManager:
    def test_archive_moves_folder(self, workspace: Path):
        _scaffold_active(
            workspace,
            "to-archive",
            status={
                "schema_version": 1,
                "change_id": "to-archive",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.archive("to-archive", archive_date="2026-04-22")
        assert result.archive_path.is_dir()
        assert result.archive_path.name == "2026-04-22-to-archive"
        # State recorded as ARCHIVED in the moved STATUS.yaml.
        archived_status = yaml.safe_load(
            (result.archive_path / "STATUS.yaml").read_text(encoding="utf-8")
        )
        assert archived_status["state"] == "ARCHIVED"

    def test_archive_preserves_artifacts_byte_identical(self, workspace: Path):
        scaffold = _scaffold_active(
            workspace,
            "preserve",
            status={
                "schema_version": 1,
                "change_id": "preserve",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        # Snapshot artifacts (excluding STATUS.yaml which mutates state).
        snapshot = {
            name: (scaffold / name).read_bytes()
            for name in ("goal.md", "acceptance.md", "spec.md", "tasks.md", "owned_files.txt")
        }
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.archive("preserve", archive_date="2026-04-22")
        for name, before in snapshot.items():
            assert (result.archive_path / name).read_bytes() == before, (
                f"{name} drift after archive"
            )

    def test_archive_idempotent(self, workspace: Path):
        _scaffold_active(
            workspace,
            "idem",
            status={
                "schema_version": 1,
                "change_id": "idem",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        first = manager.archive("idem", archive_date="2026-04-22")
        second = manager.archive("idem", archive_date="2026-04-22")
        assert first.archive_path == second.archive_path
        # Second call yields zero new consolidations.
        assert second.consolidated_counts == {"promoted": 0, "captured": 0, "skipped": 0}

    def test_archive_state_guard(self, workspace: Path):
        # Default state IN_PROGRESS — must FAIL the require_state="VERIFYING" guard.
        _scaffold_active(workspace, "wrong-state")
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        with pytest.raises(ArchiveError) as exc_info:
            manager.archive("wrong-state")
        assert "VERIFYING" in str(exc_info.value)

    def test_archive_with_learnings_consolidates(self, workspace: Path):
        learnings = textwrap.dedent(
            """\
            {"key":"k1","stage":"impl","task_type":"test","confidence":0.9,"ttl_days":90,"timestamp":"2026-04-22T10:14:33Z"}
            {"key":"k2","stage":"impl","task_type":"test","confidence":0.85,"ttl_days":90,"timestamp":"2026-04-22T10:14:34Z"}
            """
        )
        _scaffold_active(
            workspace,
            "with-learn",
            learnings_jsonl=learnings,
            status={
                "schema_version": 1,
                "change_id": "with-learn",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.archive("with-learn", archive_date="2026-04-22")
        # Two new entries — no pre-existing global JSONL → 2 captured, 0 promoted.
        assert result.consolidated_counts["captured"] == 2
        assert result.consolidated_counts["promoted"] == 0

    def test_archive_with_corrupt_learnings_raises(self, workspace: Path):
        _scaffold_active(
            workspace,
            "corrupt",
            learnings_jsonl="not-json\n",
            status={
                "schema_version": 1,
                "change_id": "corrupt",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        with pytest.raises(ArchiveError) as exc_info:
            manager.archive("corrupt", archive_date="2026-04-22")
        assert "malformed" in str(exc_info.value).lower() or "json" in str(exc_info.value).lower()

    def test_archive_unknown_change_raises(self, workspace: Path):
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        with pytest.raises(ChangeNotFoundError):
            manager.archive("nonexistent")


class TestProposeMerge:
    def _setup_archived_with_spec(self, workspace: Path, change_id: str = "merge-1") -> Path:
        spec = textwrap.dedent(
            """\
            ---
            parent: merge-1
            delta_target: agent_workspace
            delta_kind: lite
            ---

            # Operation Spec for merge-1

            ## Purpose
            Add a brand-new requirement.

            ## ADDED Requirements

            ### Requirement: Brand-new feature
            The system MUST do brand-new things.
            """
        )
        _scaffold_active(
            workspace,
            change_id,
            spec_md=spec,
            status={
                "schema_version": 1,
                "change_id": change_id,
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.archive(change_id, archive_date="2026-04-22")
        return result.archive_path

    def test_propose_merge_returns_string_content(self, workspace: Path):
        self._setup_archived_with_spec(workspace)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        proposal = manager.propose_merge("merge-1")
        assert isinstance(proposal.content, str)
        assert "Brand-new feature" in proposal.content
        assert proposal.delta_target == "agent_workspace"

    def test_propose_merge_does_not_write_to_disk(self, workspace: Path):
        self._setup_archived_with_spec(workspace)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        target_path = workspace / ".local" / "memory" / "specs" / "agent_workspace" / "spec.md"
        assert not target_path.exists(), "test pre-condition: target spec MUST be absent"
        proposal = manager.propose_merge("merge-1")
        # Crucial AC-5 invariant — propose does NOT write.
        assert not target_path.exists(), (
            "AC-5 VIOLATED: propose_merge wrote to disk; write-side ships in v8.2.7"
        )
        # But the proposed target_path matches the would-be write location.
        assert proposal.target_path == target_path

    def test_propose_merge_appends_added_to_existing(self, workspace: Path):
        # Pre-seed an existing source-of-truth.
        sot_dir = workspace / ".local" / "memory" / "specs" / "agent_workspace"
        sot_dir.mkdir(parents=True)
        (sot_dir / "spec.md").write_text(
            textwrap.dedent(
                """\
                ---
                domain: agent_workspace
                schema_version: 1
                last_merged_change: null
                last_merged_at: null
                ---

                # Spec: agent_workspace \u2014 Source-of-Truth

                ## Requirement: Pre-existing thing
                The system MUST do the pre-existing thing.
                """
            ),
            encoding="utf-8",
        )
        self._setup_archived_with_spec(workspace)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        proposal = manager.propose_merge("merge-1")
        assert "Pre-existing thing" in proposal.content
        assert "Brand-new feature" in proposal.content

    def test_propose_merge_added_collision_raises(self, workspace: Path):
        # Pre-seed source-of-truth that already has the same heading.
        sot_dir = workspace / ".local" / "memory" / "specs" / "agent_workspace"
        sot_dir.mkdir(parents=True)
        (sot_dir / "spec.md").write_text(
            textwrap.dedent(
                """\
                ---
                domain: agent_workspace
                schema_version: 1
                last_merged_change: null
                last_merged_at: null
                ---

                # Spec: agent_workspace \u2014 Source-of-Truth

                ## Requirement: Brand-new feature
                The system already had this.
                """
            ),
            encoding="utf-8",
        )
        self._setup_archived_with_spec(workspace)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        with pytest.raises(MergeConflict) as exc_info:
            manager.propose_merge("merge-1")
        assert "Brand-new feature" in str(exc_info.value)

    def test_propose_merge_modified_match_required(self, workspace: Path):
        # No pre-existing SoT; MODIFIED has nothing to match.
        spec = textwrap.dedent(
            """\
            ---
            parent: mod-only
            delta_target: agent_workspace
            delta_kind: lite
            ---

            # Operation Spec for mod-only

            ## Purpose
            Modify a requirement that does not exist.

            ## MODIFIED Requirements

            ### Requirement: Nonexistent
            The system MUST do something different.
            (Previously: did nothing.)
            """
        )
        _scaffold_active(
            workspace,
            "mod-only",
            spec_md=spec,
            status={
                "schema_version": 1,
                "change_id": "mod-only",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        manager.archive("mod-only", archive_date="2026-04-22")
        with pytest.raises(MergeConflict) as exc_info:
            manager.propose_merge("mod-only")
        assert "Nonexistent" in str(exc_info.value)

    def test_propose_merge_missing_delta_target_raises(self, workspace: Path):
        # Spec WITHOUT delta_target frontmatter (invalid per schema).
        spec = textwrap.dedent(
            """\
            ---
            parent: no-target
            delta_kind: lite
            ---

            # Operation Spec for no-target

            ## Purpose
            Spec missing delta_target.

            ## ADDED Requirements

            ### Requirement: Hello
            The system MUST greet.
            """
        )
        _scaffold_active(
            workspace,
            "no-target",
            spec_md=spec,
            status={
                "schema_version": 1,
                "change_id": "no-target",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-22T10:14:33Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        manager.archive("no-target", archive_date="2026-04-22")
        with pytest.raises(ArchiveError) as exc_info:
            manager.propose_merge("no-target")
        assert "delta_target" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-6 — lint_change CLI + programmatic
# ---------------------------------------------------------------------------


class TestLintChange:
    def test_clean_change_passes(self, workspace: Path):
        _scaffold_active(workspace, "clean")
        report = lint_change("clean", repo_root=workspace)
        assert isinstance(report, BudgetReport)
        assert report.exit_code == 0
        assert report.hard_failures == []

    def test_oversize_spec_fails_hard(self, workspace: Path):
        oversize = "x" * 13000  # 13000 / 4 ≈ 3250 tokens > 3000 hard
        _scaffold_active(workspace, "oversize", spec_md=oversize)
        report = lint_change("oversize", repo_root=workspace)
        assert report.exit_code == 1
        assert any(v.severity == "FAIL" and v.filename == "spec.md" for v in report.violations)

    def test_soft_breach_warns_but_zero_exit(self, workspace: Path):
        soft = "x" * 6500  # 6500 / 4 ≈ 1625 tokens > 1500 soft, < 3000 hard
        _scaffold_active(workspace, "softie", spec_md=soft)
        report = lint_change("softie", repo_root=workspace)
        assert report.exit_code == 0
        assert any(v.severity == "WARN" and v.filename == "spec.md" for v in report.violations)
        assert report.hard_failures == []

    def test_missing_change_raises_file_not_found(self, workspace: Path):
        with pytest.raises(FileNotFoundError):
            lint_change("nonexistent", repo_root=workspace)

    def test_estimate_tokens_helper(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens("a" * 4) == 1
        assert estimate_tokens("a" * 16) == 4

    def test_cli_main_returns_zero_on_clean(self, workspace: Path, monkeypatch):
        _scaffold_active(workspace, "cli-clean")
        monkeypatch.chdir(workspace)
        rc = lint_main(["cli-clean"])
        assert rc == 0

    def test_cli_main_returns_one_on_hard_failure(self, workspace: Path, monkeypatch):
        oversize = "y" * 13000
        _scaffold_active(workspace, "cli-fail", spec_md=oversize)
        monkeypatch.chdir(workspace)
        rc = lint_main(["cli-fail"])
        assert rc == 1

    def test_cli_main_returns_two_on_missing_change(self, workspace: Path, monkeypatch):
        monkeypatch.chdir(workspace)
        rc = lint_main(["never-existed"])
        assert rc == 2


# ---------------------------------------------------------------------------
# Misc — ArchiveManager.propose_merge against an active (un-archived) change
# ---------------------------------------------------------------------------


class TestProposeMergeAgainstActiveChange:
    def test_propose_merge_reads_active_folder(self, workspace: Path):
        spec = textwrap.dedent(
            """\
            ---
            parent: active-merge
            delta_target: my_domain
            delta_kind: lite
            ---

            # Operation Spec for active-merge

            ## Purpose
            Active not yet archived.

            ## ADDED Requirements

            ### Requirement: Live one
            The system MUST be live.
            """
        )
        _scaffold_active(workspace, "active-merge", spec_md=spec)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        proposal = manager.propose_merge("active-merge")
        assert proposal.delta_target == "my_domain"
        assert "Live one" in proposal.content


# ---------------------------------------------------------------------------
# v8.4.4 PV-04 — TestApplyMerge (M-004 / A-4 ADR full closure)
# ---------------------------------------------------------------------------


class TestApplyMerge:
    """``ArchiveManager.apply_merge`` — write side of the source-of-truth merge.

    Per Rule A-4 (`.cursor/rules/repo-governance.mdc` §"A-4 — Source-of-
    Truth Spec Location"), source-of-truth files are mutated ONLY at
    archive time AFTER the gate has PASSED. These tests pin the
    PATCH/MINOR threshold (≥ 8.5), the MAJOR threshold (≥ 9.0), the
    explicit-override path, and the atomic-write contract.
    """

    def _scaffold_archived_with_score(
        self,
        workspace: Path,
        change_id: str,
        gate_score: float,
        *,
        delta_target: str = "agent_workspace",
    ) -> Path:
        """Scaffold an archived change with a controllable gate_score."""
        spec = textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            delta_target: {delta_target}
            delta_kind: lite
            ---

            # Operation Spec for {change_id}

            ## Purpose
            Apply-merge fixture.

            ## ADDED Requirements

            ### Requirement: Apply-merge feature
            The system MUST support apply_merge writes.
            """
        )
        _scaffold_active(
            workspace,
            change_id,
            spec_md=spec,
            status={
                "schema_version": 1,
                "change_id": change_id,
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-24T12:00:00Z",
                "last_handoff_seq": 0,
                "gate_score": gate_score,
                "verify_pass": True,
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.archive(
            change_id, archive_date="2026-04-24", auto_regenerate_reports=False
        )
        return result.archive_path

    def test_apply_merge_happy_path_patch_threshold(self, workspace: Path):
        self._scaffold_archived_with_score(workspace, "apply-1", gate_score=8.5)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        target_path = workspace / ".local" / "memory" / "specs" / "agent_workspace" / "spec.md"
        assert not target_path.exists(), "test pre-condition: target spec MUST be absent"
        result = manager.apply_merge("apply-1")
        assert isinstance(result, AppliedMerge)
        assert target_path.exists(), "apply_merge MUST write the source-of-truth spec"
        assert result.gate_score == 8.5
        assert result.threshold == 8.5
        assert result.delta_target == "agent_workspace"
        assert result.bytes_written > 0
        text = target_path.read_text(encoding="utf-8")
        assert "Apply-merge feature" in text

    def test_apply_merge_below_patch_threshold_raises(self, workspace: Path):
        self._scaffold_archived_with_score(workspace, "apply-low", gate_score=8.4)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        with pytest.raises(GateThresholdNotMet) as exc_info:
            manager.apply_merge("apply-low")
        assert "8.40" in str(exc_info.value)
        assert "8.50" in str(exc_info.value)
        assert "PATCH/MINOR" in str(exc_info.value)
        target_path = workspace / ".local" / "memory" / "specs" / "agent_workspace" / "spec.md"
        assert not target_path.exists(), (
            "A-4 VIOLATED: apply_merge wrote despite gate score below threshold"
        )

    def test_apply_merge_major_threshold_path(self, workspace: Path):
        self._scaffold_archived_with_score(workspace, "apply-major", gate_score=8.7)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        # 8.7 < 9.0 (MAJOR threshold) → must raise.
        with pytest.raises(GateThresholdNotMet) as exc_info:
            manager.apply_merge("apply-major", is_major_change=True)
        assert "MAJOR" in str(exc_info.value)
        assert "9.00" in str(exc_info.value)
        # But 8.7 >= 8.5 (PATCH/MINOR threshold) → succeeds without the flag.
        result = manager.apply_merge("apply-major")
        assert result.gate_score == 8.7
        assert result.threshold == 8.5

    def test_apply_merge_explicit_threshold_override(self, workspace: Path):
        self._scaffold_archived_with_score(workspace, "apply-override", gate_score=7.0)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.apply_merge("apply-override", require_gate_score=6.0)
        assert result.threshold == 6.0
        assert result.gate_score == 7.0

    def test_apply_merge_missing_gate_score_raises(self, workspace: Path):
        spec = textwrap.dedent(
            """\
            ---
            parent: no-score
            delta_target: agent_workspace
            delta_kind: lite
            ---

            # Operation Spec for no-score

            ## Purpose
            No gate score recorded.

            ## ADDED Requirements

            ### Requirement: A thing
            The system MUST do a thing.
            """
        )
        _scaffold_active(
            workspace,
            "no-score",
            spec_md=spec,
            status={
                "schema_version": 1,
                "change_id": "no-score",
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-24T12:00:00Z",
                "last_handoff_seq": 0,
                "verify_pass": True,
                # gate_score intentionally absent.
            },
        )
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        manager.archive("no-score", archive_date="2026-04-24", auto_regenerate_reports=False)
        with pytest.raises(ArchiveError) as exc_info:
            manager.apply_merge("no-score")
        msg = str(exc_info.value)
        assert "gate_score" in msg
        assert "A-4" in msg

    def test_apply_merge_atomic_via_tmp(self, workspace: Path):
        """Confirm the .tmp sibling is cleaned up after a successful write."""
        self._scaffold_archived_with_score(workspace, "apply-atomic", gate_score=9.5)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        manager.apply_merge("apply-atomic")
        target_path = workspace / ".local" / "memory" / "specs" / "agent_workspace" / "spec.md"
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        assert target_path.exists(), "applied path must exist"
        assert not tmp_path.exists(), (
            "atomic-rename contract: .tmp sibling MUST be gone after successful apply"
        )

    def test_apply_merge_re_apply_raises_merge_conflict(self, workspace: Path):
        """Re-applying the same ADDED Requirement MUST raise MergeConflict.

        Per ``schemas/agent-workspace/source-of-truth-spec.yaml#mutation_contract``
        ADDED Requirements MUST be unique by stable heading. A successful
        first ``apply_merge`` writes the section; a second ``apply_merge``
        for the same change would try to ADD the same heading and is
        correctly rejected as a conflict (use a separate MODIFIED change
        for follow-up edits).
        """
        self._scaffold_archived_with_score(workspace, "apply-reapply", gate_score=9.5)
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result1 = manager.apply_merge("apply-reapply")
        assert result1.applied_path.exists()
        with pytest.raises(MergeConflict) as exc_info:
            manager.apply_merge("apply-reapply")
        assert "Apply-merge feature" in str(exc_info.value)


# ---------------------------------------------------------------------------
# v8.4.4 PV-04 — REPORT.md auto-trigger (I-PV07-A closure)
# ---------------------------------------------------------------------------


class TestArchiveAutoRegenerateReports:
    """``archive(auto_regenerate_reports=True)`` MUST write per-change + workspace REPORT.md.

    Per I-PV07-A from the v9.0.0 gap analysis §3.1, archive() now opts
    into REPORT.md regeneration by default. The opt-out flag
    ``auto_regenerate_reports=False`` exists for tests that need
    byte-pinned filesystem state.
    """

    def _scaffold(self, workspace: Path, change_id: str = "report-1") -> None:
        spec = textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            delta_target: agent_workspace
            delta_kind: lite
            ---

            # Operation Spec for {change_id}

            ## Purpose
            REPORT.md auto-trigger fixture.

            ## ADDED Requirements

            ### Requirement: A trigger
            The system MUST auto-regenerate.
            """
        )
        _scaffold_active(
            workspace,
            change_id,
            spec_md=spec,
            status={
                "schema_version": 1,
                "change_id": change_id,
                "state": "VERIFYING",
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-24T12:00:00Z",
                "last_handoff_seq": 0,
                "gate_score": 9.0,
                "verify_pass": True,
            },
        )

    def test_archive_auto_regenerates_per_change_report(self, workspace: Path):
        self._scaffold(workspace, "report-perchange")
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.archive("report-perchange", archive_date="2026-04-24")
        per_change_report = result.archive_path / "REPORT.md"
        assert per_change_report.exists(), (
            "I-PV07-A VIOLATED: archive must auto-regenerate per-change REPORT.md by default"
        )
        text = per_change_report.read_text(encoding="utf-8")
        assert "report-perchange" in text

    def test_archive_auto_regenerates_workspace_report(self, workspace: Path):
        self._scaffold(workspace, "report-workspace")
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        manager.archive("report-workspace", archive_date="2026-04-24")
        workspace_report = workspace / ".local" / ".agent" / "REPORT.md"
        assert workspace_report.exists(), (
            "I-PV07-A VIOLATED: archive must auto-regenerate workspace-wide REPORT.md"
        )

    def test_archive_opt_out_skips_report_regen(self, workspace: Path):
        self._scaffold(workspace, "report-optout")
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))
        result = manager.archive(
            "report-optout",
            archive_date="2026-04-24",
            auto_regenerate_reports=False,
        )
        per_change_report = result.archive_path / "REPORT.md"
        assert not per_change_report.exists(), (
            "auto_regenerate_reports=False MUST skip per-change REPORT.md write"
        )
        workspace_report = workspace / ".local" / ".agent" / "REPORT.md"
        assert not workspace_report.exists(), (
            "auto_regenerate_reports=False MUST skip workspace REPORT.md write"
        )

    def test_archive_render_failure_does_not_raise(self, workspace: Path, monkeypatch) -> None:
        """A render failure inside auto_regenerate_reports MUST be logged not raised."""
        self._scaffold(workspace, "report-failboom")
        manager = ArchiveManager(store=ChangeStore(repo_root=workspace))

        def boom(*args, **kwargs):
            raise RuntimeError("synthetic Jinja render failure")

        # Patch the symbol where it's imported (inside the helper).
        monkeypatch.setattr(
            "devolaflow.agent_workspace.reporter.render_change_report",
            boom,
        )
        # Must NOT raise — REPORT.md is presentation, not integrity.
        result = manager.archive("report-failboom", archive_date="2026-04-24")
        assert result.archive_path.exists()
