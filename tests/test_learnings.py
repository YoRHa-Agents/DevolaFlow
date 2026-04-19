"""Tests for the operational learnings module.

Covers: capture_learning, load_relevant_learnings, prune_learnings,
format_learnings_section, and edge cases (missing files, malformed JSON).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from devolaflow.learnings import (
    DECAY_FLOOR,
    DEFAULT_DECAY_HALF_LIFE_DAYS,
    ExternalSourceReview,
    Learning,
    capture_learning,
    capture_session_reflection,
    consolidate_session,
    decay_confidence,
    dedup_learnings,
    format_learnings_section,
    load_relevant_learnings,
    log_external_source_review,
    pin_learning_for_session,
    prune_learnings,
)


def _make_learning(**overrides) -> Learning:
    defaults = {
        "stage": "implement",
        "task_type": "feature",
        "key": "test-key",
        "insight": "Tests should be written first",
        "confidence": 0.8,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    defaults.update(overrides)
    return Learning(**defaults)


def _entry(
    key: str = "k1",
    task_type: str = "feature",
    confidence: float = 0.9,
    timestamp: str | None = None,
    ttl_days: int = 90,
    **extra,
) -> dict:
    return {
        "stage": "s",
        "task_type": task_type,
        "key": key,
        "insight": "i",
        "confidence": confidence,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "ttl_days": ttl_days,
        **extra,
    }


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


class TestCaptureLearning:
    def test_writes_valid_jsonl(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        learning = _make_learning()
        result = capture_learning(learning, p)

        assert result is True
        assert p.exists()
        lines = p.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["key"] == "test-key"
        assert data["stage"] == "implement"
        assert data["task_type"] == "feature"

    def test_skips_duplicate(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        l1 = _make_learning(key="dup", stage="s1", task_type="t1")
        l2 = _make_learning(key="dup", stage="s1", task_type="t1", insight="different")

        assert capture_learning(l1, p) is True
        assert capture_learning(l2, p) is False
        assert len(p.read_text().strip().splitlines()) == 1

    def test_allows_different_key_combo(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        l1 = _make_learning(key="k1", stage="s1", task_type="t1")
        l2 = _make_learning(key="k1", stage="s2", task_type="t1")

        assert capture_learning(l1, p) is True
        assert capture_learning(l2, p) is True
        assert len(p.read_text().strip().splitlines()) == 2

    def test_auto_sets_timestamp(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        learning = _make_learning(timestamp="")

        capture_learning(learning, p)
        data = json.loads(p.read_text().strip())
        assert data["timestamp"] != ""
        datetime.fromisoformat(data["timestamp"])

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "sub" / "dir" / "learn.jsonl"
        capture_learning(_make_learning(), p)
        assert p.exists()

    def test_missing_file_on_first_write(self, tmp_path: Path) -> None:
        p = tmp_path / "new.jsonl"
        assert not p.exists()
        assert capture_learning(_make_learning(), p) is True
        assert p.exists()


class TestLoadRelevantLearnings:
    def test_filters_by_task_type(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="k1", task_type="feature"),
                _entry(key="k2", task_type="hotfix"),
            ],
        )
        results = load_relevant_learnings("feature", p)
        assert len(results) == 1
        assert results[0].key == "k1"

    def test_filters_by_confidence(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="low", confidence=0.3),
                _entry(key="high", confidence=0.8),
            ],
        )
        results = load_relevant_learnings("feature", p, min_confidence=0.5)
        assert len(results) == 1
        assert results[0].key == "high"

    def test_filters_expired_by_ttl(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        fresh = datetime.now(UTC).isoformat()
        _write_jsonl(
            p,
            [
                _entry(key="expired", timestamp=old, ttl_days=30),
                _entry(key="fresh", timestamp=fresh),
            ],
        )
        results = load_relevant_learnings("feature", p)
        assert len(results) == 1
        assert results[0].key == "fresh"

    def test_sorts_by_confidence_desc(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="k1", task_type="t", confidence=0.6),
                _entry(key="k2", task_type="t", confidence=0.9),
                _entry(key="k3", task_type="t", confidence=0.7),
            ],
        )
        results = load_relevant_learnings("t", p)
        assert [r.confidence for r in results] == [0.9, 0.7, 0.6]

    def test_respects_max_entries(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        entries = [_entry(key=f"k{i}", task_type="t") for i in range(20)]
        _write_jsonl(p, entries)
        results = load_relevant_learnings("t", p, max_entries=5)
        assert len(results) == 5

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.jsonl"
        results = load_relevant_learnings("feature", p)
        assert results == []


class TestPruneLearnings:
    def test_removes_expired(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        fresh = datetime.now(UTC).isoformat()
        _write_jsonl(
            p,
            [
                _entry(
                    key="expired",
                    task_type="t",
                    timestamp=old,
                    ttl_days=30,
                ),
                _entry(
                    key="valid",
                    task_type="t",
                    timestamp=fresh,
                ),
            ],
        )
        removed = prune_learnings(p)
        assert removed == 1
        remaining = json.loads(p.read_text().strip())
        assert remaining["key"] == "valid"

    def test_keeps_all_valid(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="k1", task_type="t"),
                _entry(key="k2", task_type="t", confidence=0.7),
            ],
        )
        removed = prune_learnings(p)
        assert removed == 0
        assert len(p.read_text().strip().splitlines()) == 2

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        p.write_text("")
        assert prune_learnings(p) == 0

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.jsonl"
        assert prune_learnings(p) == 0


class TestFormatLearningsSection:
    def test_formats_entries(self) -> None:
        learnings = [
            _make_learning(
                stage="plan",
                insight="Plan before coding",
                confidence=0.9,
                rule_id="R1",
            ),
            _make_learning(
                stage="impl",
                insight="Write tests",
                confidence=0.8,
            ),
        ]
        result = format_learnings_section(learnings)
        assert "## Operational Learnings" in result
        assert "Plan before coding" in result
        assert "Write tests" in result
        assert "rule: R1" in result

    def test_respects_max_tokens(self) -> None:
        learnings = [
            _make_learning(insight="A " * 200, confidence=0.9),
            _make_learning(key="k2", insight="B " * 200, confidence=0.8),
        ]
        result = format_learnings_section(learnings, max_tokens=100)
        assert "B " * 200 not in result

    def test_empty_list_returns_empty(self) -> None:
        assert format_learnings_section([]) == ""


class TestExternalSourceReview:
    def test_default_values(self) -> None:
        r = ExternalSourceReview(
            source_id="test-dep",
            review_date="2026-04-13",
            findings_summary="No changes",
            relevance_delta=0.0,
        )
        assert r.source_id == "test-dep"
        assert r.relevance_delta == 0.0
        assert r.timestamp == ""

    def test_relevance_delta_clamped(self) -> None:
        r = ExternalSourceReview(
            source_id="x",
            review_date="d",
            findings_summary="s",
            relevance_delta=10.0,
        )
        assert r.relevance_delta == 5.0
        r2 = ExternalSourceReview(
            source_id="x",
            review_date="d",
            findings_summary="s",
            relevance_delta=-10.0,
        )
        assert r2.relevance_delta == -5.0


class TestLogExternalSourceReview:
    def test_writes_jsonl(self, tmp_path: Path) -> None:
        p = tmp_path / "ext.jsonl"
        result = log_external_source_review(
            source_id="superpowers",
            review_date="2026-04-13",
            findings_summary="New enforcement patterns added",
            relevance_delta=0.5,
            jsonl_path=p,
        )
        assert result is True
        assert p.exists()
        data = json.loads(p.read_text().strip())
        assert data["source_id"] == "superpowers"
        assert data["review_date"] == "2026-04-13"
        assert data["findings_summary"] == "New enforcement patterns added"
        assert data["relevance_delta"] == 0.5
        assert data["timestamp"] != ""

    def test_append_only(self, tmp_path: Path) -> None:
        p = tmp_path / "ext.jsonl"
        log_external_source_review("dep1", "2026-01-01", "first", 0.0, p)
        log_external_source_review("dep2", "2026-01-02", "second", 1.0, p)
        lines = p.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["source_id"] == "dep1"
        assert json.loads(lines[1])["source_id"] == "dep2"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "sub" / "dir" / "ext.jsonl"
        log_external_source_review("dep", "d", "s", 0.0, p)
        assert p.exists()

    def test_clamps_relevance_delta(self, tmp_path: Path) -> None:
        p = tmp_path / "ext.jsonl"
        log_external_source_review("dep", "d", "s", 99.0, p)
        data = json.loads(p.read_text().strip())
        assert data["relevance_delta"] == 5.0


class TestEdgeCases:
    def test_malformed_json_line_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        valid = json.dumps(_entry(key="k1", task_type="t"))
        p.write_text(f"{valid}\n{{bad json\n{valid.replace('k1', 'k2')}\n")
        results = load_relevant_learnings("t", p)
        assert len(results) == 2

    def test_confidence_clamped(self) -> None:
        l_high = Learning(
            stage="s",
            task_type="t",
            key="k",
            insight="i",
            confidence=1.5,
        )
        assert l_high.confidence == 1.0
        l_low = Learning(
            stage="s",
            task_type="t",
            key="k",
            insight="i",
            confidence=-0.5,
        )
        assert l_low.confidence == 0.0

    def test_prune_with_malformed_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        valid = json.dumps(_entry(key="k1", task_type="t"))
        p.write_text(f"not json\n{valid}\n")

        removed = prune_learnings(p)
        assert removed == 0
        lines = p.read_text().strip().splitlines()
        assert len(lines) == 1


class TestLearningsV2Schema:
    """ADR-005 §6 tests — confidence decay, session pinning, consolidation.

    The eight tests below guard the v2 schema migration. Failure of
    ``test_decay_confidence_linear`` or ``test_legacy_entry_parses`` blocks
    the release per the ADR's test plan.
    """

    def test_decay_confidence_linear(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        fifteen_days_ago = (datetime.now(UTC) - timedelta(days=15)).isoformat()
        _write_jsonl(
            p,
            [
                _entry(
                    key="decay-k",
                    task_type="t",
                    confidence=0.8,
                    timestamp=fifteen_days_ago,
                    last_accessed=fifteen_days_ago,
                    confidence_half_life_days=30,
                )
            ],
        )
        summary = decay_confidence(p)
        assert summary["decayed_count"] == 1
        assert summary["dropped_below_floor_count"] == 0
        data = json.loads(p.read_text().strip())
        # 15 days / 30 day half-life = 0.5 decay_factor → 0.8 - 0.5*0.5 = 0.55
        assert abs(data["confidence"] - 0.55) < 1e-6, (
            f"expected confidence ~0.55 after linear decay, got {data['confidence']}"
        )

    def test_decay_confidence_floor(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        # Use a tiny half-life so a very small delta still forces a large decay
        # factor; with 1-day half-life and 365-day delta, decay_factor=1.0 and
        # new_confidence = 0.1 - 0.5 = -0.4, clamped to 0.0 and pruned.
        long_ago = (datetime.now(UTC) - timedelta(days=365)).isoformat()
        _write_jsonl(
            p,
            [
                _entry(
                    key="floor-k",
                    task_type="t",
                    confidence=0.12,
                    timestamp=long_ago,
                    last_accessed=long_ago,
                    confidence_half_life_days=1,
                )
            ],
        )
        summary = decay_confidence(p)
        assert summary["decayed_count"] == 1
        assert summary["dropped_below_floor_count"] == 1, (
            f"expected entry below {DECAY_FLOOR} to be dropped, "
            f"summary={summary}, remaining={p.read_text()!r}"
        )
        remaining = p.read_text().strip()
        assert remaining == "", f"expected empty JSONL after floor-prune, got: {remaining!r}"

    def test_consolidate_session_promotes_matched(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(
                    key="shared",
                    task_type="t",
                    confidence=0.7,
                    promotion_count=2,
                )
            ],
        )
        session_learning = Learning(
            stage="s",
            task_type="t",
            key="shared",
            insight="i",
            confidence=0.7,
        )
        summary = consolidate_session("sess-1", [session_learning], p)
        assert summary == {"promoted": 1, "captured": 0, "skipped": 0}
        data = json.loads(p.read_text().strip())
        assert abs(data["confidence"] - 0.75) < 1e-6
        assert data["promotion_count"] == 3
        assert data["last_accessed"], "last_accessed must be refreshed on promotion"

    def test_consolidate_session_captures_new(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(p, [])
        new_learning = Learning(
            stage="s",
            task_type="t",
            key="fresh",
            insight="first time captured",
            confidence=0.6,
        )
        summary = consolidate_session("sess-2", [new_learning], p)
        assert summary == {"promoted": 0, "captured": 1, "skipped": 0}
        data = json.loads(p.read_text().strip())
        assert data["key"] == "fresh"
        assert data["promotion_count"] == 1
        assert data["last_accessed"]
        assert data["timestamp"], "timestamp must auto-populate on new captures"

    def test_pin_for_session(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="low-but-important", task_type="t", confidence=0.2),
                _entry(key="high-conf", task_type="t", confidence=0.9),
            ],
        )
        # Without pinning, the low-confidence entry is filtered by min_confidence=0.5.
        unpinned = load_relevant_learnings("t", p, min_confidence=0.5)
        assert {r.key for r in unpinned} == {"high-conf"}

        # Pin the low-confidence entry for a session and re-query.
        assert pin_learning_for_session("low-but-important", "s", "t", "sess-99", p) is True
        pinned_results = load_relevant_learnings("t", p, min_confidence=0.5, session_id="sess-99")
        keys = {r.key for r in pinned_results}
        assert keys == {"low-but-important", "high-conf"}, (
            f"expected both pinned + high-conf, got {keys}"
        )
        # Different session_id must NOT surface the pinned entry.
        other_session = load_relevant_learnings("t", p, min_confidence=0.5, session_id="sess-other")
        assert {r.key for r in other_session} == {"high-conf"}

    def test_legacy_entry_parses(self, tmp_path: Path) -> None:
        """v1-shaped entries without any v2 fields must load identically
        to pre-v7 behaviour.
        """
        p = tmp_path / "learn.jsonl"
        legacy = {
            "stage": "s",
            "task_type": "t",
            "key": "legacy",
            "insight": "i",
            "confidence": 0.75,
            "rule_id": "",
            "timestamp": datetime.now(UTC).isoformat(),
            "ttl_days": 90,
            "source_task_id": "",
        }
        p.write_text(json.dumps(legacy) + "\n")
        results = load_relevant_learnings("t", p, min_confidence=0.5)
        assert len(results) == 1
        learning = results[0]
        assert learning.key == "legacy"
        assert learning.confidence == 0.75
        # v2 fields default safely on load.
        assert learning.confidence_half_life_days == DEFAULT_DECAY_HALF_LIFE_DAYS
        assert learning.last_accessed == ""
        assert learning.pinned_for_session == ""
        assert learning.promotion_count == 0

    def test_migration_last_accessed_shim(self, tmp_path: Path) -> None:
        """Legacy entry without ``last_accessed`` gets ``timestamp`` backfilled
        on first ``decay_confidence`` call (ADR-005 §2.4)."""
        p = tmp_path / "learn.jsonl"
        five_days_ago_ts = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        legacy = {
            "stage": "s",
            "task_type": "t",
            "key": "legacy-shim",
            "insight": "i",
            "confidence": 0.9,
            "rule_id": "",
            "timestamp": five_days_ago_ts,
            "ttl_days": 90,
            "source_task_id": "",
        }
        p.write_text(json.dumps(legacy) + "\n")
        # 5 days / 30 day half-life = decay_factor 0.1667 → confidence 0.9 - 0.0833
        decay_confidence(p, half_life_days=30)
        data = json.loads(p.read_text().strip())
        assert data["last_accessed"] == five_days_ago_ts, (
            "migration shim must backfill last_accessed from timestamp"
        )
        # Confidence must have decayed from 0.9, not stayed at 0.9 (shim must
        # seed last_accessed BEFORE the decay calculation, not after).
        assert data["confidence"] < 0.9

    def test_consolidate_session_idempotent(self, tmp_path: Path) -> None:
        """Calling ``consolidate_session`` with the same payload twice in one
        call promotes only once. Calling it twice across two invocations
        bumps twice — that's intended — but a single invocation with a
        duplicated learning in the payload must skip the dup."""
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(
                    key="shared-k",
                    task_type="t",
                    confidence=0.6,
                    promotion_count=0,
                )
            ],
        )
        session_learning = Learning(
            stage="s",
            task_type="t",
            key="shared-k",
            insight="i",
            confidence=0.6,
        )
        # Duplicate the same learning twice in a single session payload.
        summary = consolidate_session("sess-dup", [session_learning, session_learning], p)
        assert summary == {"promoted": 1, "captured": 0, "skipped": 1}
        data = json.loads(p.read_text().strip())
        assert abs(data["confidence"] - 0.65) < 1e-6, "dup payload must only promote once"
        assert data["promotion_count"] == 1

    def test_consolidate_session_empty_payload_noop(self, tmp_path: Path) -> None:
        """Empty ``session_learnings`` list must not touch the JSONL file
        and must return a zero-valued summary dict. Protects the session-end
        hook from accidentally rewriting the file when no learnings were
        surfaced during the session."""
        p = tmp_path / "learn.jsonl"
        original_content = json.dumps(_entry(key="preserved", task_type="t")) + "\n"
        p.write_text(original_content)
        summary = consolidate_session("sess-empty", [], p)
        assert summary == {"promoted": 0, "captured": 0, "skipped": 0}
        # Byte-for-byte preservation of the JSONL file (no rewrite).
        assert p.read_text() == original_content

    def test_decay_confidence_missing_file_returns_zero_summary(self, tmp_path: Path) -> None:
        """``decay_confidence`` on a missing JSONL file must return a
        zero-valued summary dict and NOT raise — the session-end hook
        needs to be safe on brand-new workspaces where the learnings file
        has never been created."""
        nonexistent = tmp_path / "never_created.jsonl"
        assert not nonexistent.exists()
        summary = decay_confidence(nonexistent)
        assert summary == {"decayed_count": 0, "dropped_below_floor_count": 0}
        assert not nonexistent.exists()


class TestLearningsV2Coverage:
    """Additional coverage tests for the v2-era code paths plus the
    pre-existing functions whose branches were not previously exercised.
    These close the ``devolaflow.learnings`` ≥90 % coverage floor
    (CP-2 / roadmap v7.0.3 post-condition).
    """

    def test_promote_learning_matched_bumps_confidence(self, tmp_path: Path) -> None:
        from devolaflow.learnings import promote_learning

        p = tmp_path / "learn.jsonl"
        _write_jsonl(p, [_entry(key="match-me", task_type="t", confidence=0.5)])
        learning = Learning(
            stage="s",
            task_type="t",
            key="match-me",
            insight="i",
            confidence=0.5,
        )
        promote_learning(learning, p)
        data = json.loads(p.read_text().strip())
        assert abs(data["confidence"] - 0.6) < 1e-6
        assert data["timestamp"]

    def test_promote_learning_no_match_appends(self, tmp_path: Path) -> None:
        from devolaflow.learnings import promote_learning

        p = tmp_path / "learn.jsonl"
        promote_learning(
            Learning(
                stage="s",
                task_type="t",
                key="brand-new",
                insight="i",
                confidence=0.7,
            ),
            p,
        )
        assert p.exists()
        data = json.loads(p.read_text().strip())
        assert data["key"] == "brand-new"
        assert data["confidence"] == 0.7

    def test_get_learnings_stats_nonempty(self, tmp_path: Path) -> None:
        from devolaflow.learnings import get_learnings_stats

        p = tmp_path / "learn.jsonl"
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        fresh = datetime.now(UTC).isoformat()
        _write_jsonl(
            p,
            [
                _entry(key="k1", task_type="feature", confidence=0.8, timestamp=fresh),
                _entry(key="k2", task_type="feature", confidence=0.6, timestamp=fresh),
                _entry(
                    key="k3",
                    task_type="hotfix",
                    confidence=0.9,
                    timestamp=old,
                    ttl_days=30,
                ),
            ],
        )
        stats = get_learnings_stats(p)
        assert stats["total"] == 3
        assert stats["by_task_type"]["feature"] == 2
        assert stats["by_task_type"]["hotfix"] == 1
        assert stats["expired_count"] == 1
        assert 0.7 < stats["avg_confidence"] <= 0.8

    def test_get_learnings_stats_empty_file(self, tmp_path: Path) -> None:
        from devolaflow.learnings import get_learnings_stats

        p = tmp_path / "learn.jsonl"
        p.write_text("")
        stats = get_learnings_stats(p)
        assert stats == {
            "total": 0,
            "by_task_type": {},
            "avg_confidence": 0.0,
            "expired_count": 0,
        }

    def test_load_relevant_skips_invalid_timestamp(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="bad-ts", task_type="t", timestamp="not-a-date"),
                _entry(key="good-ts", task_type="t"),
            ],
        )
        results = load_relevant_learnings("t", p)
        assert {r.key for r in results} == {"good-ts"}

    def test_load_relevant_skips_missing_required_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        broken = {
            "task_type": "t",
            "key": "missing-stage",
            "insight": "i",
            "confidence": 0.9,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        valid = _entry(key="ok", task_type="t")
        p.write_text(json.dumps(broken) + "\n" + json.dumps(valid) + "\n")
        results = load_relevant_learnings("t", p)
        assert {r.key for r in results} == {"ok"}

    def test_prune_with_invalid_timestamp_keeps_entry(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="bad-ts", task_type="t", timestamp="not-a-date"),
                _entry(key="good", task_type="t"),
            ],
        )
        removed = prune_learnings(p)
        assert removed == 0
        assert len(p.read_text().strip().splitlines()) == 2

    def test_decay_confidence_zero_half_life_keeps_entry(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(
                    key="nondecay",
                    task_type="t",
                    confidence=0.5,
                    last_accessed=(datetime.now(UTC) - timedelta(days=30)).isoformat(),
                )
            ],
        )
        summary = decay_confidence(p, half_life_days=0)
        # Zero half-life means we skip decay on that entry without pruning.
        assert summary == {"decayed_count": 0, "dropped_below_floor_count": 0}
        data = json.loads(p.read_text().strip())
        assert data["confidence"] == 0.5

    def test_decay_confidence_invalid_last_accessed_keeps_entry(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(
                    key="bad-anchor",
                    task_type="t",
                    confidence=0.5,
                    last_accessed="not-a-date",
                    timestamp="also-not-a-date",
                )
            ],
        )
        summary = decay_confidence(p)
        assert summary == {"decayed_count": 0, "dropped_below_floor_count": 0}
        data = json.loads(p.read_text().strip())
        assert data["confidence"] == 0.5

    def test_pin_missing_key_returns_false(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(p, [_entry(key="existing", task_type="t")])
        result = pin_learning_for_session("nonexistent", "s", "t", "sess-99", p)
        assert result is False

    def test_decay_empty_file_returns_zero_summary(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        p.write_text("")
        summary = decay_confidence(p)
        assert summary == {"decayed_count": 0, "dropped_below_floor_count": 0}

    def test_log_external_source_review_default_path(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert log_external_source_review("dep", "d", "s", 0.0) is True
        default = (
            tmp_path
            / "workflow-system"
            / "agent"
            / "knowledge"
            / "learnings"
            / "external-sources.jsonl"
        )
        assert default.exists()


# ---------------------------------------------------------------------------
# v7.2.0 C-007 (CCT-3) — dedup_learnings helper + v3 schema backward compat
# ---------------------------------------------------------------------------
# Lifted verbatim from .local/sandbox/v7.2.0/V07/test_dedup.py (10 cases) and
# .local/sandbox/v7.2.0/V07/test_backward_compat.py (5 cases). Sandbox imports
# from sandbox_learnings; production imports from devolaflow.learnings.
# Validation report: .local/research/v7.2.0_validations/V07.md.


def _make_dedup_learning(
    *,
    stage: str = "s",
    task_type: str = "feature",
    key: str = "k1",
    insight: str = "i",
    confidence: float = 0.5,
    timestamp: str = "",
) -> Learning:
    return Learning(
        stage=stage,
        task_type=task_type,
        key=key,
        insight=insight,
        confidence=confidence,
        timestamp=timestamp,
    )


class TestDedupLearningsBasic:
    def test_empty_input_returns_empty_list(self) -> None:
        assert dedup_learnings([]) == []

    def test_single_entry_passthrough(self) -> None:
        only = _make_dedup_learning(timestamp="2026-04-18T00:00:00+00:00")
        result = dedup_learnings([only])
        assert len(result) == 1
        assert result[0] is only

    def test_no_duplicates_passthrough(self) -> None:
        a = _make_dedup_learning(task_type="t1", key="k1", timestamp="2026-01-01T00:00:00+00:00")
        b = _make_dedup_learning(task_type="t2", key="k1", timestamp="2026-02-01T00:00:00+00:00")
        c = _make_dedup_learning(task_type="t1", key="k2", timestamp="2026-03-01T00:00:00+00:00")
        result = dedup_learnings([a, b, c])
        assert len(result) == 3
        assert {(e.task_type, e.key) for e in result} == {
            ("t1", "k1"),
            ("t2", "k1"),
            ("t1", "k2"),
        }


class TestDedupLearningsDuplicates:
    def test_latest_timestamp_wins_ordered_input(self) -> None:
        """Older entry first, newer second — newer wins."""
        older = _make_dedup_learning(
            task_type="feature",
            key="dup-key",
            insight="OLD",
            confidence=0.5,
            timestamp="2026-01-01T00:00:00+00:00",
        )
        newer = _make_dedup_learning(
            task_type="feature",
            key="dup-key",
            insight="NEW",
            confidence=0.9,
            timestamp="2026-04-18T00:00:00+00:00",
        )
        result = dedup_learnings([older, newer])
        assert len(result) == 1
        assert result[0].insight == "NEW"
        assert result[0].confidence == 0.9
        assert result[0].timestamp == "2026-04-18T00:00:00+00:00"

    def test_latest_timestamp_wins_reversed_input(self) -> None:
        """Order independence: newer first, older second — newer still wins."""
        newer = _make_dedup_learning(
            task_type="feature",
            key="dup-key",
            insight="NEW",
            confidence=0.9,
            timestamp="2026-04-18T00:00:00+00:00",
        )
        older = _make_dedup_learning(
            task_type="feature",
            key="dup-key",
            insight="OLD",
            confidence=0.5,
            timestamp="2026-01-01T00:00:00+00:00",
        )
        result = dedup_learnings([newer, older])
        assert len(result) == 1
        assert result[0].insight == "NEW"
        assert result[0].timestamp == "2026-04-18T00:00:00+00:00"

    def test_dedup_groups_by_task_type_and_key_only(self) -> None:
        """Two entries with same (task_type, key) but different stages collapse
        to one — proves the dedup criterion is (task_type, key), NOT
        (stage, task_type, key) like capture_learning's skip-dup."""
        s1 = _make_dedup_learning(
            stage="implement",
            task_type="t",
            key="k",
            insight="from implement",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        s2 = _make_dedup_learning(
            stage="review",
            task_type="t",
            key="k",
            insight="from review",
            timestamp="2026-04-18T00:00:00+00:00",
        )
        result = dedup_learnings([s1, s2])
        assert len(result) == 1, (
            "Different stages should NOT prevent dedup — "
            "criterion is (task_type, key) per C-007 spec"
        )
        assert result[0].insight == "from review"

    def test_overlapping_pairs_at_different_timestamps(self) -> None:
        """Three (task_type, key) tuples, each with 2-3 timestamped entries.
        After dedup: exactly 3 entries, one per tuple, latest each.

        Canonical fixture called out in the dispatch:
            "Fixture with overlapping (task_type, key) pairs at different
             timestamps. Assert dedup returns latest only."
        """
        entries = [
            _make_dedup_learning(
                task_type="feature",
                key="k1",
                insight="f-k1-old",
                timestamp="2026-01-01T00:00:00+00:00",
            ),
            _make_dedup_learning(
                task_type="feature",
                key="k1",
                insight="f-k1-mid",
                timestamp="2026-02-15T00:00:00+00:00",
            ),
            _make_dedup_learning(
                task_type="feature",
                key="k1",
                insight="f-k1-new",
                timestamp="2026-04-18T00:00:00+00:00",
            ),
            _make_dedup_learning(
                task_type="hotfix",
                key="k1",
                insight="h-k1-old",
                timestamp="2026-01-01T00:00:00+00:00",
            ),
            _make_dedup_learning(
                task_type="hotfix",
                key="k1",
                insight="h-k1-new",
                timestamp="2026-04-15T00:00:00+00:00",
            ),
            _make_dedup_learning(
                task_type="feature",
                key="k2",
                insight="f-k2-only",
                timestamp="2026-03-01T00:00:00+00:00",
            ),
        ]
        result = dedup_learnings(entries)
        assert len(result) == 3

        by_tuple = {(e.task_type, e.key): e for e in result}
        assert by_tuple[("feature", "k1")].insight == "f-k1-new"
        assert by_tuple[("hotfix", "k1")].insight == "h-k1-new"
        assert by_tuple[("feature", "k2")].insight == "f-k2-only"


class TestDedupLearningsEdgeCases:
    def test_empty_timestamp_loses_to_populated(self) -> None:
        """Lexicographic comparison: '' < any non-empty string, so the
        populated-timestamp entry wins regardless of input order."""
        no_ts = _make_dedup_learning(task_type="t", key="k", insight="no-ts", timestamp="")
        with_ts = _make_dedup_learning(
            task_type="t",
            key="k",
            insight="with-ts",
            timestamp="2026-04-18T00:00:00+00:00",
        )
        assert dedup_learnings([no_ts, with_ts])[0].insight == "with-ts"
        assert dedup_learnings([with_ts, no_ts])[0].insight == "with-ts"

    def test_both_empty_timestamps_first_wins(self) -> None:
        """When both timestamps are empty (equal), dedup keeps the FIRST
        encountered entry. Not specified by C-007 but documented behaviour."""
        first = _make_dedup_learning(task_type="t", key="k", insight="first", timestamp="")
        second = _make_dedup_learning(task_type="t", key="k", insight="second", timestamp="")
        result = dedup_learnings([first, second])
        assert len(result) == 1
        assert result[0].insight == "first"

    def test_preserves_v3_files_and_source_fields_on_winner(self) -> None:
        """Dedup winner should carry its own files/source — the helper does
        not merge fields, it just picks the latest."""
        loser = _make_dedup_learning(
            task_type="t",
            key="k",
            insight="loser",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        loser.files = ["a.py", "b.py"]
        loser.source = "manual"
        winner = _make_dedup_learning(
            task_type="t",
            key="k",
            insight="winner",
            timestamp="2026-04-18T00:00:00+00:00",
        )
        winner.files = ["c.py"]
        winner.source = "observed"
        result = dedup_learnings([loser, winner])
        assert len(result) == 1
        assert result[0].insight == "winner"
        assert result[0].files == ["c.py"], "winner.files must NOT be merged with loser"
        assert result[0].source == "observed"


class TestV1EntryLoadsWithoutNewFields:
    def test_v1_jsonl_loads_with_v3_defaults(self, tmp_path: Path) -> None:
        """Hand-crafted v1 JSONL line without `files` or `source` parses
        cleanly via load_relevant_learnings(). No exception. Both v2 and v3
        defaults applied automatically.

        Primary backward-compat guard for C-007. Failure here blocks the
        v7.2.0 release.
        """
        p = tmp_path / "v1.jsonl"
        v1_line = {
            "stage": "implement",
            "task_type": "feature",
            "key": "v1-legacy-key",
            "insight": "captured under pre-v7.0.3 schema",
            "confidence": 0.8,
            "rule_id": "",
            "timestamp": datetime.now(UTC).isoformat(),
            "ttl_days": 90,
            "source_task_id": "",
        }
        p.write_text(json.dumps(v1_line) + "\n")

        results = load_relevant_learnings("feature", p, min_confidence=0.5)
        assert len(results) == 1, f"v1 entry failed to load, got {results}"

        learning = results[0]
        assert learning.key == "v1-legacy-key"
        assert learning.confidence == 0.8
        assert learning.insight == "captured under pre-v7.0.3 schema"

        assert learning.confidence_half_life_days == DEFAULT_DECAY_HALF_LIFE_DAYS
        assert learning.last_accessed == ""
        assert learning.pinned_for_session == ""
        assert learning.promotion_count == 0

        assert learning.files == [], (
            f"v3 `files` default broken: expected [], got {learning.files!r}"
        )
        assert learning.source == "", (
            f"v3 `source` default broken: expected '', got {learning.source!r}"
        )

    def test_v1_jsonl_files_default_is_distinct_list_per_instance(self, tmp_path: Path) -> None:
        """field(default_factory=list) must produce a DISTINCT list per
        Learning — not a shared mutable default. Guards the classic Python
        mutable-default-arg trap."""
        p = tmp_path / "v1-multi.jsonl"
        ts = datetime.now(UTC).isoformat()
        line_template = {
            "stage": "s",
            "task_type": "t",
            "insight": "i",
            "confidence": 0.9,
            "timestamp": ts,
        }
        l1 = {**line_template, "key": "k1"}
        l2 = {**line_template, "key": "k2"}
        p.write_text(json.dumps(l1) + "\n" + json.dumps(l2) + "\n")

        results = load_relevant_learnings("t", p, min_confidence=0.5)
        assert len(results) == 2

        results[0].files.append("touched-by-r0.py")
        assert results[1].files == [], (
            "files default_factory must give DISTINCT lists per instance — "
            f"shared-default trap detected: r1.files={results[1].files}"
        )


class TestV2EntryLoadsWithoutV3Fields:
    def test_v2_jsonl_loads_with_v3_defaults(self, tmp_path: Path) -> None:
        """v2-shaped JSONL entries (post-v7.0.3, pre-v7.2.0) load cleanly
        with v3 defaults applied. Existing v2 fields are preserved
        untouched. Required to honour the lazy-migration contract from
        ADR-005 §2.4 — v3 must not undo v2's compatibility."""
        p = tmp_path / "v2.jsonl"
        ts = datetime.now(UTC).isoformat()
        v2_line = {
            "stage": "implement",
            "task_type": "feature",
            "key": "v2-key",
            "insight": "captured under v7.0.3 schema",
            "confidence": 0.85,
            "rule_id": "",
            "timestamp": ts,
            "ttl_days": 90,
            "source_task_id": "",
            "confidence_half_life_days": 45,
            "last_accessed": ts,
            "pinned_for_session": "sess-active",
            "promotion_count": 3,
        }
        p.write_text(json.dumps(v2_line) + "\n")

        results = load_relevant_learnings("feature", p, min_confidence=0.5)
        assert len(results) == 1

        learning = results[0]
        assert learning.confidence == 0.85
        assert learning.confidence_half_life_days == 45
        assert learning.pinned_for_session == "sess-active"
        assert learning.promotion_count == 3
        assert learning.files == []
        assert learning.source == ""


class TestV3EntryRoundTrip:
    def test_capture_then_load_preserves_files_and_source(self, tmp_path: Path) -> None:
        """Full v3 round-trip: write a Learning with non-default files +
        source through capture_learning, load it back through
        load_relevant_learnings, both fields preserved bit-for-bit."""
        p = tmp_path / "v3.jsonl"
        original = Learning(
            stage="implement",
            task_type="feature",
            key="v3-roundtrip",
            insight="captured with files+source",
            confidence=0.9,
            files=[
                "src/devolaflow/learnings.py",
                "tests/test_learnings.py",
            ],
            source="observed",
        )
        wrote = capture_learning(original, p)
        assert wrote is True

        results = load_relevant_learnings("feature", p, min_confidence=0.5)
        assert len(results) == 1
        loaded = results[0]
        assert loaded.files == [
            "src/devolaflow/learnings.py",
            "tests/test_learnings.py",
        ], f"v3 files round-trip broken: got {loaded.files!r}"
        assert loaded.source == "observed", f"v3 source round-trip broken: got {loaded.source!r}"

    def test_v3_jsonl_with_null_files_field_coerces_to_empty_list(self, tmp_path: Path) -> None:
        """Defensive: a malformed v3 entry that has files: null on disk
        should coerce to [] via __post_init__ rather than raise on access.
        Protects against hand-edited or partially-migrated JSONL files."""
        p = tmp_path / "v3-null.jsonl"
        ts = datetime.now(UTC).isoformat()
        bad_line = {
            "stage": "s",
            "task_type": "t",
            "key": "null-files",
            "insight": "i",
            "confidence": 0.9,
            "timestamp": ts,
            "files": None,
            "source": "manual",
        }
        p.write_text(json.dumps(bad_line) + "\n")

        results = load_relevant_learnings("t", p, min_confidence=0.5)
        assert len(results) == 1
        learning = results[0]
        assert learning.files == [], f"null files must coerce to []; got {learning.files!r}"
        assert learning.source == "manual"


# ---------------------------------------------------------------------------
# v7.2.3 P-03 (C-009 promotion) — capture_session_reflection writer
# ---------------------------------------------------------------------------
# Activates the dormant operational.jsonl substrate that v7.2.0 PR-C shipped
# (C-007 schema additions). Six cases per the v7.3.0 patch plan §P-03:
#   - happy path
#   - auto-derived key from files[0]
#   - session_id passes through to persisted entry
#   - dedup against existing same-(task_type, key) pre-populated entry
#   - round-trip through load_relevant_learnings
#   - empty files list → key auto-derives to f"{task_type}:session"


class TestCaptureSessionReflection:
    """v7.2.3 P-03 — capture_session_reflection() writer.

    See ``.local/research/v7.3.0_patch_plan.md`` §P-03 and the dispatch's
    Step 2 test plan. Six cases mirror the spec list verbatim.
    """

    def test_capture_creates_learning_entry(self, tmp_path: Path) -> None:
        p = tmp_path / "operational.jsonl"
        learning = capture_session_reflection(
            session_id="sess-1",
            task_type="feature",
            files=["src/devolaflow/learnings.py"],
            insight="Dedup must run against existing entries before persistence",
            source="observed",
            jsonl_path=p,
        )
        assert isinstance(learning, Learning)
        assert learning.task_type == "feature"
        assert learning.key == "feature:src/devolaflow/learnings.py"
        assert learning.insight == "Dedup must run against existing entries before persistence"
        assert learning.source == "observed"
        assert learning.confidence == 0.7, "spec defaults confidence to 0.7"
        assert learning.stage == "reflection", "spec hardcodes stage to 'reflection'"
        assert learning.files == ["src/devolaflow/learnings.py"]
        assert learning.timestamp, "timestamp must be auto-set to now"

        assert p.exists()
        data = json.loads(p.read_text().strip())
        assert data["task_type"] == "feature"
        assert data["key"] == "feature:src/devolaflow/learnings.py"
        assert data["source"] == "observed"

    def test_capture_auto_derives_key(self, tmp_path: Path) -> None:
        """key=None → derived key matches f"{task_type}:{files[0]}"."""
        p = tmp_path / "operational.jsonl"
        learning = capture_session_reflection(
            session_id="sess-2",
            task_type="hotfix",
            files=["src/auth.py", "tests/test_auth.py"],
            insight="JWT path needs explicit nil guard",
            source="reasoning",
            jsonl_path=p,
        )
        assert learning.key == "hotfix:src/auth.py", (
            f"expected key to derive from task_type:files[0]; got {learning.key!r}"
        )
        data = json.loads(p.read_text().strip())
        assert data["key"] == "hotfix:src/auth.py"

    def test_capture_session_passes_through_session_id(self, tmp_path: Path) -> None:
        """session_id reaches the persisted entry (via source_task_id)."""
        p = tmp_path / "operational.jsonl"
        capture_session_reflection(
            session_id="sess-trace-99",
            task_type="feature",
            files=["x.py"],
            insight="i",
            source="observed",
            jsonl_path=p,
        )
        data = json.loads(p.read_text().strip())
        assert data["source_task_id"] == "sess-trace-99", (
            f"session_id must round-trip via source_task_id; got {data.get('source_task_id')!r}"
        )

    def test_capture_dedups_against_existing(self, tmp_path: Path) -> None:
        """Pre-populate JSONL with same (task_type, key) older entry; new wins by ts."""
        p = tmp_path / "operational.jsonl"
        old_ts = "2026-01-01T00:00:00+00:00"
        old_entry = {
            "stage": "implement",
            "task_type": "feature",
            "key": "feature:x.py",
            "insight": "OLD",
            "confidence": 0.6,
            "timestamp": old_ts,
            "ttl_days": 90,
            "source_task_id": "sess-old",
        }
        p.write_text(json.dumps(old_entry) + "\n")

        new_learning = capture_session_reflection(
            session_id="sess-new",
            task_type="feature",
            files=["x.py"],
            insight="NEW",
            source="observed",
            jsonl_path=p,
        )

        lines = p.read_text().strip().splitlines()
        assert len(lines) == 1, f"expected exactly 1 entry after dedup, got {len(lines)}: {lines}"
        data = json.loads(lines[0])
        assert data["insight"] == "NEW", (
            f"latest timestamp must win per (task_type, key); got insight={data['insight']!r}"
        )
        assert data["source_task_id"] == "sess-new"
        assert new_learning.timestamp > old_ts, (
            "new entry timestamp must be strictly later than old (now > 2026-01-01)"
        )

    def test_capture_round_trip_through_load_relevant_learnings(self, tmp_path: Path) -> None:
        """capture → load_relevant_learnings → fields preserved bit-for-bit."""
        p = tmp_path / "operational.jsonl"
        capture_session_reflection(
            session_id="sess-round-trip",
            task_type="feature",
            files=["src/api.py"],
            insight="Always validate input at boundary",
            source="observed",
            jsonl_path=p,
        )
        results = load_relevant_learnings("feature", p, min_confidence=0.5)
        assert len(results) == 1
        loaded = results[0]
        assert loaded.insight == "Always validate input at boundary"
        assert loaded.source == "observed"
        assert loaded.files == ["src/api.py"]
        assert loaded.key == "feature:src/api.py"
        assert loaded.source_task_id == "sess-round-trip"
        assert loaded.confidence == 0.7

    def test_capture_handles_empty_files_list(self, tmp_path: Path) -> None:
        """files=[] → key auto-derives to f"{task_type}:session"."""
        p = tmp_path / "operational.jsonl"
        learning = capture_session_reflection(
            session_id="sess-no-files",
            task_type="research",
            files=[],
            insight="Survey complete; no source files touched",
            source="reasoning",
            jsonl_path=p,
        )
        assert learning.key == "research:session", (
            f"empty files must derive key='<task_type>:session'; got {learning.key!r}"
        )
        data = json.loads(p.read_text().strip())
        assert data["key"] == "research:session"
        assert data["files"] == []
