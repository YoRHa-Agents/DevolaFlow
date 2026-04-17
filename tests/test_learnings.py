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
    consolidate_session,
    decay_confidence,
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
