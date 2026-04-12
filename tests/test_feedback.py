"""Tests for the self-improving feedback loop module.

Covers: FeedbackCollector, FeedbackAnalyzer, ProposalGenerator,
promote_learning, get_learnings_stats, and safeguard enforcement.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from devolaflow.feedback import (
    CONFIDENCE_FLOOR,
    MAX_PROPOSALS_PER_WORKFLOW,
    FeedbackAnalyzer,
    FeedbackCollector,
    ProposalGenerator,
    _inside_devolaflow,
    _is_locked,
)
from devolaflow.gate.models import GateVerdict
from devolaflow.learnings import (
    Learning,
    capture_learning,
    get_learnings_stats,
    promote_learning,
)


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
        "insight": "some insight",
        "confidence": confidence,
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "ttl_days": ttl_days,
        **extra,
    }


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


# ---------------------------------------------------------------------------
# FeedbackCollector
# ---------------------------------------------------------------------------


class TestFeedbackCollector:
    def test_collect_from_gate_basic(self) -> None:
        verdict = GateVerdict(
            decision="PASS",
            rationale="All checks passed",
            composite_score=85.0,
            details={"findings": [{"id": "f1"}, {"id": "f2"}]},
        )
        result = FeedbackCollector().collect_from_gate(verdict)
        assert result["composite_score"] == 85.0
        assert result["decision"] == "PASS"
        assert result["findings_count"] == 2

    def test_collect_from_gate_no_findings(self) -> None:
        verdict = GateVerdict(decision="PASS", rationale="ok")
        result = FeedbackCollector().collect_from_gate(verdict)
        assert result["findings_count"] == 0
        assert result["composite_score"] is None

    def test_collect_from_gate_findings_as_int(self) -> None:
        verdict = GateVerdict(
            decision="FAIL",
            rationale="issues",
            details={"findings": 5},
        )
        result = FeedbackCollector().collect_from_gate(verdict)
        assert result["findings_count"] == 5

    def test_collect_from_report(self) -> None:
        report = {
            "metrics": {"coverage": 0.82},
            "issues": ["lint-error-1"],
            "elapsed_seconds": 120,
        }
        result = FeedbackCollector().collect_from_report(report)
        assert result["metrics"] == {"coverage": 0.82}
        assert result["issues"] == ["lint-error-1"]
        assert result["elapsed_seconds"] == 120

    def test_collect_from_report_missing_keys(self) -> None:
        result = FeedbackCollector().collect_from_report({})
        assert result["metrics"] == {}
        assert result["issues"] == []
        assert result["elapsed_seconds"] == 0

    def test_collect_workflow_metrics(self) -> None:
        stages = [
            {"name": "S01", "rounds": 2, "composite_score": 80.0},
            {"name": "S02", "rounds": 5, "composite_score": 70.0},
            {"name": "S03", "rounds": 1, "composite_score": 90.0},
        ]
        result = FeedbackCollector().collect_workflow_metrics(stages)
        assert result["total_rounds"] == 8
        assert result["avg_composite"] == 80.0
        assert result["bottleneck_stage"] == "S02"

    def test_collect_workflow_metrics_empty(self) -> None:
        result = FeedbackCollector().collect_workflow_metrics([])
        assert result["total_rounds"] == 0
        assert result["avg_composite"] == 0.0
        assert result["bottleneck_stage"] == ""


# ---------------------------------------------------------------------------
# FeedbackAnalyzer
# ---------------------------------------------------------------------------


class TestFeedbackAnalyzerRecurringViolations:
    def test_detects_recurring(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        entries = [_entry(key=f"k{i}", rule_id="CP-2") for i in range(4)]
        _write_jsonl(p, entries)

        results = FeedbackAnalyzer().detect_recurring_violations(p, min_occurrences=3)
        assert len(results) == 1
        assert results[0]["rule_id"] == "CP-2"
        assert results[0]["count"] == 4

    def test_ignores_below_threshold(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        entries = [_entry(key=f"k{i}", rule_id="CP-1") for i in range(2)]
        _write_jsonl(p, entries)

        results = FeedbackAnalyzer().detect_recurring_violations(p, min_occurrences=3)
        assert results == []

    def test_ignores_empty_rule_id(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        entries = [_entry(key=f"k{i}", rule_id="") for i in range(5)]
        _write_jsonl(p, entries)

        results = FeedbackAnalyzer().detect_recurring_violations(p)
        assert results == []

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.jsonl"
        results = FeedbackAnalyzer().detect_recurring_violations(p)
        assert results == []

    def test_examples_capped_at_three(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        entries = [_entry(key=f"k{i}", rule_id="CO-1", insight=f"insight-{i}") for i in range(6)]
        _write_jsonl(p, entries)

        results = FeedbackAnalyzer().detect_recurring_violations(p, min_occurrences=3)
        assert len(results[0]["examples"]) == 3


class TestFeedbackAnalyzerStagnation:
    def test_detects_stagnation(self) -> None:
        rounds = [
            {"composite_score": 60.0},
            {"composite_score": 60.5},
            {"composite_score": 61.0},
        ]
        assert FeedbackAnalyzer().detect_convergence_stagnation(rounds, threshold=2.0) is True

    def test_no_stagnation_with_improvement(self) -> None:
        rounds = [
            {"composite_score": 60.0},
            {"composite_score": 65.0},
            {"composite_score": 70.0},
        ]
        assert FeedbackAnalyzer().detect_convergence_stagnation(rounds, threshold=2.0) is False

    def test_needs_at_least_three_rounds(self) -> None:
        rounds = [
            {"composite_score": 60.0},
            {"composite_score": 60.1},
        ]
        assert FeedbackAnalyzer().detect_convergence_stagnation(rounds) is False

    def test_stagnation_not_at_start(self) -> None:
        rounds = [
            {"composite_score": 50.0},
            {"composite_score": 60.0},
            {"composite_score": 60.5},
            {"composite_score": 60.8},
        ]
        assert FeedbackAnalyzer().detect_convergence_stagnation(rounds, threshold=2.0) is True

    def test_recovery_resets_counter(self) -> None:
        rounds = [
            {"composite_score": 60.0},
            {"composite_score": 60.1},
            {"composite_score": 70.0},
            {"composite_score": 70.1},
        ]
        assert FeedbackAnalyzer().detect_convergence_stagnation(rounds, threshold=2.0) is False


class TestFeedbackAnalyzerProfileMismatch:
    def test_detects_mismatch(self) -> None:
        mismatches = FeedbackAnalyzer().detect_profile_mismatch(
            "feature",
            {"coverage": 0.60, "lint_score": 0.95},
            {"coverage": 0.80, "lint_score": 0.90},
        )
        assert len(mismatches) == 1
        assert "coverage" in mismatches[0]

    def test_no_mismatch(self) -> None:
        mismatches = FeedbackAnalyzer().detect_profile_mismatch(
            "feature",
            {"coverage": 0.85},
            {"coverage": 0.80},
        )
        assert mismatches == []

    def test_missing_metric(self) -> None:
        mismatches = FeedbackAnalyzer().detect_profile_mismatch(
            "feature",
            {},
            {"coverage": 0.80},
        )
        assert len(mismatches) == 1
        assert "missing" in mismatches[0]


# ---------------------------------------------------------------------------
# ProposalGenerator
# ---------------------------------------------------------------------------


class TestProposalGenerator:
    def test_generates_proposal_from_violations(self) -> None:
        analysis = {
            "confidence": 0.85,
            "recurring_violations": [
                {"rule_id": "CP-2", "count": 4, "examples": ["a", "b"]},
            ],
        }
        proposals = ProposalGenerator().generate_proposals(analysis)
        assert len(proposals) == 1
        p = proposals[0]
        assert p["type"] == "rule_update"
        assert "CP-2" in p["description"]
        assert p["confidence"] == 0.85
        assert p["target_file"].endswith(".mdc")

    def test_generates_stagnation_proposal(self) -> None:
        analysis = {
            "confidence": 0.8,
            "stagnation_detected": True,
            "recurring_violations": [],
        }
        proposals = ProposalGenerator().generate_proposals(analysis)
        assert len(proposals) == 1
        assert proposals[0]["type"] == "profile_tune"

    def test_generates_mismatch_proposal(self) -> None:
        analysis = {
            "confidence": 0.75,
            "recurring_violations": [],
            "profile_mismatches": ["feature: 'coverage' is 0.6, expected >= 0.8"],
        }
        proposals = ProposalGenerator().generate_proposals(analysis)
        assert len(proposals) == 1
        assert proposals[0]["type"] == "profile_tune"

    def test_max_proposals_enforced(self) -> None:
        analysis = {
            "confidence": 0.9,
            "recurring_violations": [{"rule_id": f"CP-{i}", "count": 5} for i in range(10)],
        }
        proposals = ProposalGenerator().generate_proposals(analysis)
        assert len(proposals) <= MAX_PROPOSALS_PER_WORKFLOW

    def test_confidence_floor_enforced(self) -> None:
        analysis = {
            "confidence": 0.5,
            "recurring_violations": [{"rule_id": "CP-1", "count": 10}],
        }
        proposals = ProposalGenerator().generate_proposals(analysis)
        assert proposals == []

    def test_confidence_at_floor_passes(self) -> None:
        analysis = {
            "confidence": CONFIDENCE_FLOOR,
            "recurring_violations": [{"rule_id": "CP-1", "count": 5}],
        }
        proposals = ProposalGenerator().generate_proposals(analysis)
        assert len(proposals) == 1

    def test_locked_files_rejected(self) -> None:
        assert _is_locked("__init__.py") is True
        assert _is_locked("pyproject.toml") is True
        assert _is_locked("feedback.py") is True
        assert _is_locked("test_something.py") is True
        assert _is_locked("scorer.py") is False

    def test_outside_devolaflow_rejected(self) -> None:
        assert _inside_devolaflow("src/devolaflow/gate/scorer.py") is True
        assert _inside_devolaflow("workflow-system/agent/SKILL.md") is True
        assert _inside_devolaflow("schemas/gate-report.schema.yaml") is True
        assert _inside_devolaflow(".cursor/rules/change-process-rules.mdc") is True
        assert _inside_devolaflow("/etc/passwd") is False
        assert _inside_devolaflow("random/outside/file.py") is False

    def test_empty_analysis(self) -> None:
        proposals = ProposalGenerator().generate_proposals({})
        assert proposals == []

    def test_all_proposal_fields_present(self) -> None:
        analysis = {
            "confidence": 0.9,
            "recurring_violations": [{"rule_id": "CO-1", "count": 3}],
        }
        proposals = ProposalGenerator().generate_proposals(analysis)
        required_keys = {
            "id",
            "type",
            "description",
            "confidence",
            "target_file",
            "suggested_change",
        }
        for p in proposals:
            assert required_keys.issubset(p.keys())


# ---------------------------------------------------------------------------
# learnings.py extensions: promote_learning & get_learnings_stats
# ---------------------------------------------------------------------------


class TestPromoteLearning:
    def test_increases_confidence(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        learning = Learning(
            stage="s1",
            task_type="feature",
            key="k1",
            insight="original",
            confidence=0.7,
            timestamp=datetime.now(UTC).isoformat(),
        )
        capture_learning(learning, p)

        promote_learning(learning, p)

        entries = [json.loads(line) for line in p.read_text().strip().splitlines()]
        assert len(entries) == 1
        assert entries[0]["confidence"] == 0.8

    def test_confidence_clamped_at_one(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        learning = Learning(
            stage="s1",
            task_type="feature",
            key="k1",
            insight="max",
            confidence=0.95,
            timestamp=datetime.now(UTC).isoformat(),
        )
        capture_learning(learning, p)
        promote_learning(learning, p)

        entries = [json.loads(line) for line in p.read_text().strip().splitlines()]
        assert entries[0]["confidence"] == 1.0

    def test_appends_when_no_match(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        existing = Learning(
            stage="s1",
            task_type="feature",
            key="existing",
            insight="i",
            confidence=0.8,
            timestamp=datetime.now(UTC).isoformat(),
        )
        capture_learning(existing, p)

        new_learning = Learning(
            stage="s2",
            task_type="hotfix",
            key="new_key",
            insight="new insight",
            confidence=0.6,
        )
        promote_learning(new_learning, p)

        lines = p.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_refreshes_timestamp(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        learning = Learning(
            stage="s1",
            task_type="feature",
            key="k1",
            insight="i",
            confidence=0.7,
            timestamp=old_ts,
        )
        capture_learning(learning, p)
        promote_learning(learning, p)

        entries = [json.loads(line) for line in p.read_text().strip().splitlines()]
        new_ts = datetime.fromisoformat(entries[0]["timestamp"])
        orig_ts = datetime.fromisoformat(old_ts)
        assert new_ts > orig_ts


class TestGetLearningsStats:
    def test_basic_stats(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        _write_jsonl(
            p,
            [
                _entry(key="k1", task_type="feature", confidence=0.8),
                _entry(key="k2", task_type="feature", confidence=0.6),
                _entry(key="k3", task_type="hotfix", confidence=0.9),
            ],
        )
        stats = get_learnings_stats(p)
        assert stats["total"] == 3
        assert stats["by_task_type"] == {"feature": 2, "hotfix": 1}
        assert 0.76 < stats["avg_confidence"] < 0.77
        assert stats["expired_count"] == 0

    def test_counts_expired(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        old = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        _write_jsonl(
            p,
            [
                _entry(key="k1", timestamp=old, ttl_days=30),
                _entry(key="k2"),
            ],
        )
        stats = get_learnings_stats(p)
        assert stats["expired_count"] == 1
        assert stats["total"] == 2

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "learn.jsonl"
        p.write_text("")
        stats = get_learnings_stats(p)
        assert stats["total"] == 0
        assert stats["avg_confidence"] == 0.0

    def test_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.jsonl"
        stats = get_learnings_stats(p)
        assert stats["total"] == 0
