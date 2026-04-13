"""Tests for the operational learnings module.

Covers: capture_learning, load_relevant_learnings, prune_learnings,
format_learnings_section, and edge cases (missing files, malformed JSON).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from devolaflow.learnings import (
    ExternalSourceReview,
    Learning,
    capture_learning,
    format_learnings_section,
    load_relevant_learnings,
    log_external_source_review,
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
            source_id="x", review_date="d", findings_summary="s",
            relevance_delta=10.0,
        )
        assert r.relevance_delta == 5.0
        r2 = ExternalSourceReview(
            source_id="x", review_date="d", findings_summary="s",
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
