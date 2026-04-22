"""Tests for the unified session state model (v8.2.0 PV-03).

Closes Karpathy 4.8 deferral: validates :class:`devolaflow.session.SessionState`
and :class:`devolaflow.session.SessionStore` aggregate learnings +
lifecycle + legibility shared state and round-trip cleanly through JSON.

Acceptance criteria covered (per
``.local/research/v8.2.0_patch_plan.md`` §3 PV-03):

* AC-1 — SessionState aggregates 5 blocks
* AC-2 — Round-trip persistence via JSON (byte-identical state)
* AC-3 — Verbatim merge (no paraphrasing of learnings text)
* AC-4 — R5 backward-compat (legacy learnings.py path unchanged)
* AC-5 — Migration path tolerates legacy / forward payloads
* AC-6 — Lifecycle hook routes through SessionState when opt-in
* AC-8 — P6 invariant preserved (no schema bumps verified by other tests)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devolaflow.learnings import (
    Learning,
    build_session_state_for,
    capture_learning,
    consolidate_session,
    load_relevant_learnings,
    resolve_learnings_path,
)
from devolaflow.lifecycle.test_on_complete import (
    _try_persist_session_state,
    test_on_complete,
)
from devolaflow.session import (
    DEFAULT_SESSION_STATE_PATH,
    SCHEMA_VERSION,
    LegibilitySnapshot,
    LifecycleEvent,
    SessionState,
    SessionStateError,
    SessionStore,
    default_session_state_path,
)


def _make_learning(**overrides) -> Learning:
    defaults = {
        "stage": "implement",
        "task_type": "feature",
        "key": "k1",
        "insight": "Tests should be written first",
        "confidence": 0.8,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    defaults.update(overrides)
    return Learning(**defaults)


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


# ---------------------------------------------------------------------------
# TestSessionStateConstruction — empty / __post_init__ defaults
# ---------------------------------------------------------------------------


class TestSessionStateConstruction:
    def test_empty_state_has_default_session_id_blank(self) -> None:
        state = SessionState.empty()
        assert state.session_id == ""
        assert state.schema_version == SCHEMA_VERSION
        assert state.learnings == []
        assert state.pending_learnings == []
        assert state.lifecycle_events == []
        assert state.metadata == {}

    def test_empty_state_with_session_id(self) -> None:
        state = SessionState.empty("sess-001")
        assert state.session_id == "sess-001"

    def test_post_init_sets_started_at_when_blank(self) -> None:
        state = SessionState.empty()
        assert state.started_at != ""
        # ISO 8601 with +00:00 suffix
        assert state.started_at.endswith("+00:00")

    def test_post_init_sets_updated_at_to_started_at_when_blank(self) -> None:
        state = SessionState.empty()
        assert state.updated_at == state.started_at

    def test_legibility_block_is_empty_snapshot(self) -> None:
        state = SessionState.empty()
        assert isinstance(state.legibility, LegibilitySnapshot)
        assert state.legibility.mean_score == 0.0
        assert state.legibility.per_file_scores == {}

    def test_default_path_resolves_under_local_memory(self, tmp_path: Path) -> None:
        path = default_session_state_path(tmp_path)
        assert path == tmp_path / DEFAULT_SESSION_STATE_PATH
        assert ".local/memory" in str(path)


# ---------------------------------------------------------------------------
# TestSessionStateSerialization — to_dict / from_dict
# ---------------------------------------------------------------------------


class TestSessionStateSerialization:
    def test_to_dict_contains_canonical_keys(self) -> None:
        state = SessionState.empty("sess-001")
        d = state.to_dict()
        expected = {
            "session_id",
            "schema_version",
            "started_at",
            "updated_at",
            "learnings",
            "pending_learnings",
            "lifecycle_events",
            "legibility",
            "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_contains_nested_learning_dataclass_fields(self) -> None:
        state = SessionState.empty("sess-001")
        state.queue_learning(_make_learning(key="x", insight="lesson"))
        d = state.to_dict()
        pending = d["pending_learnings"]
        assert len(pending) == 1
        assert pending[0]["key"] == "x"
        assert pending[0]["insight"] == "lesson"
        # v3 additive fields default-safe
        assert "files" in pending[0]
        assert "source" in pending[0]

    def test_from_dict_round_trips_session_id_and_metadata(self) -> None:
        original = SessionState.empty("sess-002")
        original.metadata["routing_hint"] = "fast"
        rehydrated = SessionState.from_dict(original.to_dict())
        assert rehydrated.session_id == "sess-002"
        assert rehydrated.metadata == {"routing_hint": "fast"}

    def test_from_dict_accepts_missing_keys_with_defaults(self) -> None:
        rehydrated = SessionState.from_dict({"session_id": "x"})
        assert rehydrated.session_id == "x"
        assert rehydrated.schema_version == SCHEMA_VERSION
        assert rehydrated.learnings == []
        assert rehydrated.legibility.per_file_scores == {}

    def test_from_dict_logs_warning_on_higher_schema_version(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="devolaflow.session.state"):
            SessionState.from_dict({"schema_version": SCHEMA_VERSION + 99})
        assert any("forward read" in rec.message for rec in caplog.records)

    def test_from_dict_rejects_non_dict_payload(self) -> None:
        with pytest.raises(SessionStateError):
            SessionState.from_dict("not-a-dict")  # type: ignore[arg-type]

    def test_from_dict_drops_malformed_lifecycle_events(self, caplog) -> None:
        payload = {
            "session_id": "x",
            "lifecycle_events": [
                {"event": "task_stop", "passed": True},
                "not-a-dict-skip-me",
            ],
        }
        with caplog.at_level(logging.WARNING, logger="devolaflow.session.state"):
            state = SessionState.from_dict(payload)
        assert len(state.lifecycle_events) == 1
        assert state.lifecycle_events[0].event == "task_stop"

    def test_from_dict_coerces_non_dict_metadata_to_empty(self) -> None:
        state = SessionState.from_dict({"session_id": "x", "metadata": "junk"})
        assert state.metadata == {}


# ---------------------------------------------------------------------------
# TestSessionStorePersistence — save / load round-trip via JSON
# ---------------------------------------------------------------------------


class TestSessionStorePersistence:
    def test_save_creates_parent_directory(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "nested" / "memory" / "session_state.json")
        state = SessionState.empty("sess-001")
        result_path = store.save(state)
        assert result_path.exists()
        assert result_path.parent.is_dir()

    def test_save_writes_deterministic_sorted_json(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "session_state.json")
        state = SessionState.empty("sess-001")
        state.metadata["beta"] = 2
        state.metadata["alpha"] = 1
        store.save(state)
        text = (tmp_path / "session_state.json").read_text()
        # sorted keys -> session_id appears before "started_at" alphabetically
        assert text.index("session_id") < text.index("started_at")
        assert text.endswith("\n")

    def test_round_trip_preserves_session_id_and_timestamps(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "session_state.json")
        state = SessionState.empty("sess-001")
        store.save(state)
        loaded = store.load()
        assert loaded.session_id == "sess-001"
        assert loaded.started_at == state.started_at
        assert loaded.updated_at == state.updated_at

    def test_round_trip_preserves_learnings_blocks(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "session_state.json")
        state = SessionState.empty("sess-001")
        state.queue_learning(_make_learning(key="k1", insight="lesson 1"))
        state.queue_learning(_make_learning(key="k2", insight="lesson 2"))
        store.save(state)
        loaded = store.load()
        assert len(loaded.pending_learnings) == 2
        assert loaded.pending_learnings[0].key == "k1"
        assert loaded.pending_learnings[0].insight == "lesson 1"
        assert loaded.pending_learnings[1].key == "k2"

    def test_load_missing_file_returns_empty_state(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "missing.json")
        loaded = store.load(default_session_id="default-sess")
        assert loaded.session_id == "default-sess"
        assert loaded.learnings == []

    def test_load_invalid_json_raises_session_state_error(self, tmp_path: Path) -> None:
        path = tmp_path / "session_state.json"
        path.write_text("not-valid-json")
        store = SessionStore(path)
        with pytest.raises(SessionStateError):
            store.load()

    def test_load_non_dict_payload_raises_session_state_error(self, tmp_path: Path) -> None:
        path = tmp_path / "session_state.json"
        path.write_text(json.dumps([1, 2, 3]))
        store = SessionStore(path)
        with pytest.raises(SessionStateError):
            store.load()

    def test_save_rejects_non_session_state(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "session_state.json")
        with pytest.raises(TypeError):
            store.save({"session_id": "x"})  # type: ignore[arg-type]

    def test_delete_removes_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "session_state.json"
        path.write_text("{}")
        store = SessionStore(path)
        assert store.delete() is True
        assert not path.exists()

    def test_delete_missing_file_returns_false(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "missing.json")
        assert store.delete() is False

    def test_exists_reflects_file_state(self, tmp_path: Path) -> None:
        store = SessionStore(tmp_path / "session_state.json")
        assert store.exists() is False
        store.save(SessionState.empty("x"))
        assert store.exists() is True

    def test_default_store_path_when_unspecified(self) -> None:
        store = SessionStore()
        assert str(store.path).endswith("session_state.json")


# ---------------------------------------------------------------------------
# TestLegibilitySnapshot — PV-02 integration
# ---------------------------------------------------------------------------


class TestLegibilitySnapshot:
    def test_update_records_per_file_score_and_mean(self) -> None:
        snap = LegibilitySnapshot()
        snap.update("src/a.py", 90.0)
        snap.update("src/b.py", 80.0)
        assert snap.per_file_scores == {"src/a.py": 90.0, "src/b.py": 80.0}
        assert snap.mean_score == 85.0

    def test_update_dedups_findings(self) -> None:
        snap = LegibilitySnapshot()
        snap.update("src/a.py", 90.0, findings=["finding-1", "finding-2"])
        snap.update("src/a.py", 92.0, findings=["finding-1", "finding-3"])
        assert snap.findings == ["finding-1", "finding-2", "finding-3"]

    def test_update_rejects_empty_file_path(self) -> None:
        snap = LegibilitySnapshot()
        with pytest.raises(ValueError):
            snap.update("", 90.0)

    def test_merge_combines_per_file_scores_last_write_wins(self) -> None:
        a = LegibilitySnapshot()
        a.update("src/x.py", 70.0)
        b = LegibilitySnapshot()
        b.update("src/x.py", 90.0)
        b.update("src/y.py", 80.0)
        a.merge(b)
        assert a.per_file_scores == {"src/x.py": 90.0, "src/y.py": 80.0}
        assert a.mean_score == 85.0

    def test_merge_keeps_max_last_updated(self) -> None:
        a = LegibilitySnapshot(last_updated="2026-04-22T10:00:00+00:00")
        b = LegibilitySnapshot(last_updated="2026-04-22T11:00:00+00:00")
        a.merge(b)
        assert a.last_updated == "2026-04-22T11:00:00+00:00"

    def test_attach_legibility_via_session_state(self) -> None:
        state = SessionState.empty("sess-001")
        snap = state.attach_legibility("src/a.py", 95.0, findings=["finding-1"])
        assert snap.per_file_scores == {"src/a.py": 95.0}
        assert snap.findings == ["finding-1"]
        assert state.legibility is snap


# ---------------------------------------------------------------------------
# TestLifecycleEvent
# ---------------------------------------------------------------------------


class TestLifecycleEvent:
    def test_event_post_init_sets_timestamp(self) -> None:
        ev = LifecycleEvent(event="task_stop", passed=True)
        assert ev.timestamp != ""
        assert ev.violation_codes == []

    def test_event_coerces_violation_codes_to_strings(self) -> None:
        ev = LifecycleEvent(event="task_stop", passed=False, violation_codes=["TOC004", 42])
        assert ev.violation_codes == ["TOC004", "42"]

    def test_record_lifecycle_event_appends(self) -> None:
        state = SessionState.empty("sess-001")
        state.record_lifecycle_event("task_stop", passed=True)
        state.record_lifecycle_event(
            "task_stop", passed=False, severity="blocker", violation_codes=["TOC004"]
        )
        assert len(state.lifecycle_events) == 2
        assert state.lifecycle_events[1].severity == "blocker"
        assert state.lifecycle_events[1].violation_codes == ["TOC004"]


# ---------------------------------------------------------------------------
# TestLearningsIntegration — R5 preservation + bridge helpers
# ---------------------------------------------------------------------------


class TestLearningsIntegration:
    def test_hydrate_learnings_round_trip_via_jsonl(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "operational.jsonl"
        capture_learning(_make_learning(key="r1", task_type="feature", confidence=0.9), jsonl)
        state = SessionState.empty("sess-001")
        loaded = state.hydrate_learnings("feature", jsonl_path=jsonl)
        assert len(loaded) == 1
        assert loaded[0].key == "r1"
        assert state.learnings[0].key == "r1"

    def test_queue_and_flush_routes_through_consolidate_session(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "operational.jsonl"
        state = SessionState.empty("sess-001")
        state.queue_learning(_make_learning(key="q1", insight="queued lesson"))
        state.queue_learning(_make_learning(key="q2", insight="queued lesson 2"))
        summary = state.flush_learnings(jsonl_path=jsonl)
        assert summary == {"promoted": 0, "captured": 2, "skipped": 0}
        # Verify substrate updated
        loaded = load_relevant_learnings("feature", jsonl_path=jsonl, min_confidence=0.5)
        keys = {entry.key for entry in loaded}
        assert {"q1", "q2"}.issubset(keys)
        # Pending list cleared
        assert state.pending_learnings == []

    def test_flush_learnings_no_pending_returns_zero_summary(self, tmp_path: Path) -> None:
        state = SessionState.empty("sess-001")
        summary = state.flush_learnings(jsonl_path=tmp_path / "x.jsonl")
        assert summary == {"promoted": 0, "captured": 0, "skipped": 0}

    def test_capture_learning_immediate_persists(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "operational.jsonl"
        state = SessionState.empty("sess-001")
        ok = state.capture_learning(_make_learning(key="cap1"), jsonl_path=jsonl)
        assert ok is True
        # Round-trip via load
        loaded = load_relevant_learnings("feature", jsonl_path=jsonl)
        assert any(entry.key == "cap1" for entry in loaded)

    def test_queue_learning_rejects_non_learning_objects(self) -> None:
        state = SessionState.empty()
        with pytest.raises(TypeError):
            state.queue_learning({"key": "x"})  # type: ignore[arg-type]

    def test_build_session_state_for_bridge_returns_session_state(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "operational.jsonl"
        capture_learning(_make_learning(key="b1", task_type="feature", confidence=0.95), jsonl)
        bridged = build_session_state_for("sess-bridge-1", "feature", jsonl_path=jsonl)
        assert isinstance(bridged, SessionState)
        assert bridged.session_id == "sess-bridge-1"
        assert any(entry.key == "b1" for entry in bridged.learnings)


# ---------------------------------------------------------------------------
# TestR5BackwardCompat — verify learnings + lifecycle public APIs unchanged
# ---------------------------------------------------------------------------


class TestR5BackwardCompat:
    def test_learnings_module_public_api_still_exports_capture_learning(self) -> None:
        from devolaflow import learnings as learnings_mod

        assert "capture_learning" in learnings_mod.__all__
        assert "consolidate_session" in learnings_mod.__all__
        assert "load_relevant_learnings" in learnings_mod.__all__
        assert "load_prefs" in learnings_mod.__all__
        assert "decay_confidence" in learnings_mod.__all__

    def test_resolve_learnings_path_unchanged_default(self, tmp_path: Path) -> None:
        # Same callsite signature pre/post PV-03
        path = resolve_learnings_path(tmp_path)
        assert path.name == "operational.jsonl"

    def test_consolidate_session_byte_identical_round_trip(self, tmp_path: Path) -> None:
        # Run the LEGACY path (no SessionState involvement) and verify the
        # JSONL substrate looks the same as the v8.1.0-rc.1 baseline format.
        jsonl = tmp_path / "operational.jsonl"
        learnings = [_make_learning(key="r5-1"), _make_learning(key="r5-2")]
        summary = consolidate_session("sess-r5", learnings, jsonl)
        assert summary["captured"] == 2
        # Read raw and confirm no extra wrapping was added by PV-03
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert "key" in entry
            assert "insight" in entry
            assert "confidence" in entry


# ---------------------------------------------------------------------------
# TestLifecycleIntegration — PV-03 opt-in routing through test_on_complete
# ---------------------------------------------------------------------------


class TestLifecycleIntegration:
    def test_test_on_complete_no_op_without_session_state_path(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = test_on_complete(
            {
                "task_id": "t1",
                "tests_passed": 1,
                "tests_failed": 0,
                "lint_status": "clean",
            }
        )
        assert result.passed is True
        # No session state file should be created when payload lacks the key
        assert not (tmp_path / DEFAULT_SESSION_STATE_PATH).exists()

    def test_test_on_complete_persists_session_state_when_opt_in(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        # Isolate ``resolve_learnings_path()`` to tmp_path so the legacy
        # ``_try_consolidate_learnings`` helper (which fires for clean
        # task_stop payloads carrying ``learnings.entries``) does NOT
        # pollute the repo's canonical operational.jsonl substrate.
        monkeypatch.chdir(tmp_path)
        state_path = tmp_path / "session_state.json"
        result = test_on_complete(
            {
                "task_id": "t-opt-in",
                "tests_passed": 1,
                "tests_failed": 0,
                "lint_status": "clean",
                "session_state_path": str(state_path),
                "learnings": {
                    "entries": [
                        {
                            "task_type": "feature",
                            "stage": "task",
                            "insight": "opt-in lesson",
                            "confidence": 0.85,
                        }
                    ]
                },
            }
        )
        assert result.passed is True
        assert state_path.exists()
        loaded = SessionStore(state_path).load()
        assert loaded.session_id == "t-opt-in"
        # task_stop event was recorded with passed=True
        assert any(ev.event == "task_stop" and ev.passed for ev in loaded.lifecycle_events)
        # opt-in learning queued in pending block
        assert any(item.insight == "opt-in lesson" for item in loaded.pending_learnings)

    def test_test_on_complete_records_failure_event_when_violation(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        state_path = tmp_path / "session_state.json"
        result = test_on_complete(
            {
                "task_id": "t-fail",
                "tests_passed": 1,
                "tests_failed": 5,
                "lint_status": "clean",
                "session_state_path": str(state_path),
            }
        )
        assert result.passed is False
        loaded = SessionStore(state_path).load()
        # Even on failure, lifecycle event should be recorded
        ts_events = [ev for ev in loaded.lifecycle_events if ev.event == "task_stop"]
        assert ts_events
        assert ts_events[-1].passed is False

    def test_persist_session_state_attaches_legibility(self, tmp_path: Path) -> None:
        state_path = tmp_path / "session_state.json"
        _try_persist_session_state(
            {
                "task_id": "t-leg",
                "session_state_path": str(state_path),
                "legibility": {
                    "files": [
                        {"path": "src/a.py", "score": 90.0, "findings": ["good"]},
                        {"path": "src/b.py", "score": 70.0, "findings": ["bad"]},
                    ]
                },
            },
            hook_passed=True,
        )
        loaded = SessionStore(state_path).load()
        assert loaded.legibility.per_file_scores == {
            "src/a.py": 90.0,
            "src/b.py": 70.0,
        }
        assert loaded.legibility.mean_score == 80.0

    def test_persist_session_state_swallows_errors_per_s5(self, tmp_path: Path, caplog) -> None:
        # An invalid path that cannot be created (use null byte) — the helper
        # must NOT raise per S-5 best-effort contract.
        with caplog.at_level(logging.DEBUG, logger="devolaflow.lifecycle.test_on_complete"):
            _try_persist_session_state(
                {"task_id": "t1", "session_state_path": "\x00invalid\x00"},
                hook_passed=True,
            )
        # Did not raise -> success.

    def test_persist_session_state_no_op_for_non_dict_payload(self, tmp_path: Path) -> None:
        # Should not raise when payload is not a dict
        _try_persist_session_state([], hook_passed=True)  # type: ignore[arg-type]
        assert not (tmp_path / DEFAULT_SESSION_STATE_PATH).exists()

    def test_persist_session_state_skips_malformed_learning_entries(self, tmp_path: Path) -> None:
        state_path = tmp_path / "session_state.json"
        _try_persist_session_state(
            {
                "task_id": "t-malformed",
                "session_state_path": str(state_path),
                "learnings": {
                    "entries": [
                        {"insight": "good"},
                        "not-a-dict-skip",
                        {"missing_insight_key": "skip"},
                    ]
                },
            },
            hook_passed=True,
        )
        loaded = SessionStore(state_path).load()
        # Only the well-formed entry should be queued
        assert len(loaded.pending_learnings) == 1
        assert loaded.pending_learnings[0].insight == "good"


# ---------------------------------------------------------------------------
# TestSessionStateMerge — handoff scenarios
# ---------------------------------------------------------------------------


class TestSessionStateMerge:
    def test_merge_preserves_receiver_session_id(self) -> None:
        a = SessionState.empty("recv")
        b = SessionState.empty("child")
        a.merge(b)
        assert a.session_id == "recv"

    def test_merge_dedups_learnings_by_triple_keeping_latest(self) -> None:
        a = SessionState.empty("recv")
        a.queue_learning(_make_learning(key="k", insight="old"))
        b = SessionState.empty("child")
        b.queue_learning(_make_learning(key="k", insight="new"))
        a.merge(b)
        # Same (task_type, key, stage) triple → last write wins
        assert len(a.pending_learnings) == 1
        assert a.pending_learnings[0].insight == "new"

    def test_merge_concatenates_lifecycle_events(self) -> None:
        a = SessionState.empty("recv")
        a.record_lifecycle_event("task_stop", passed=True)
        b = SessionState.empty("child")
        b.record_lifecycle_event("task_stop", passed=False)
        a.merge(b)
        assert len(a.lifecycle_events) == 2

    def test_merge_combines_legibility_snapshots(self) -> None:
        a = SessionState.empty("recv")
        a.attach_legibility("src/x.py", 70.0)
        b = SessionState.empty("child")
        b.attach_legibility("src/y.py", 90.0)
        a.merge(b)
        assert a.legibility.per_file_scores == {"src/x.py": 70.0, "src/y.py": 90.0}
        assert a.legibility.mean_score == 80.0

    def test_merge_rejects_non_session_state(self) -> None:
        a = SessionState.empty()
        with pytest.raises(TypeError):
            a.merge({"not_a_state": True})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestContextProfilesIntegration — opt-in declaration in YAML config
# ---------------------------------------------------------------------------


class TestContextProfilesIntegration:
    def test_yaml_declares_session_state_section(self) -> None:
        import yaml

        path = Path("workflow-system/agent/context_profiles.yaml")
        if not path.exists():
            pytest.skip("context_profiles.yaml not present in this checkout")
        data = yaml.safe_load(path.read_text())
        assert "session_state" in data, "PV-03 requires a top-level session_state block"
        block = data["session_state"]
        assert block["enabled"] is False, "default opt-in OFF"
        assert block["default_path"] == DEFAULT_SESSION_STATE_PATH
        assert block["schema_version"] == SCHEMA_VERSION
        # STRICT/AUDIT default to enabled per PV-03 spec
        assert block["profile_default_strict_enabled"] is True
        assert block["profile_default_audit_enabled"] is True
        # STANDARD/RELAXED default to disabled
        assert block["profile_default_standard_enabled"] is False
        assert block["profile_default_relaxed_enabled"] is False
