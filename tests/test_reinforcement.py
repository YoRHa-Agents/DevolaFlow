"""Tests for devolaflow.gate.reinforcement."""

from __future__ import annotations

from devolaflow.gate.models import Finding
from devolaflow.gate.reinforcement import (
    MAX_REINFORCEMENT_RULES,
    ReinforcementBlock,
    ReinforcementRule,
    findings_to_reinforcement,
    merge_reinforcement_into_dispatch,
    reinforcement_to_dict,
)


def _make_finding(
    fid: str = "F-001",
    severity: str = "major",
    description: str = "test issue",
    suggestion: str = "",
    location: str = "src/foo.py",
) -> Finding:
    return Finding(
        finding_id=fid,
        severity=severity,  # type: ignore[arg-type]
        category="test",
        location=location,
        description=description,
        suggestion=suggestion,
    )


class TestFindingsToReinforcement:
    def test_basic_conversion(self) -> None:
        findings = [_make_finding()]
        block = findings_to_reinforcement(
            findings, round_num=2, prior_score=72.0, target_score=85.0
        )

        assert block.round == 2
        assert block.prior_score == 72.0
        assert block.target_score == 85.0
        assert block.severity_floor == "major"
        assert len(block.rules) == 1
        assert block.rules[0].id == "F-001"
        assert "MUST fix" in block.rules[0].mandate

    def test_severity_floor_filters(self) -> None:
        findings = [
            _make_finding("F-1", "blocker"),
            _make_finding("F-2", "critical"),
            _make_finding("F-3", "major"),
            _make_finding("F-4", "minor"),
            _make_finding("F-5", "info"),
        ]
        block = findings_to_reinforcement(
            findings, round_num=2, prior_score=70.0, target_score=85.0, severity_floor="critical"
        )
        ids = [r.id for r in block.rules]
        assert "F-1" in ids
        assert "F-2" in ids
        assert "F-3" not in ids
        assert "F-4" not in ids

    def test_max_rules_limit(self) -> None:
        findings = [_make_finding(f"F-{i}", "major") for i in range(10)]
        block = findings_to_reinforcement(
            findings, round_num=3, prior_score=60.0, target_score=85.0
        )
        assert len(block.rules) == MAX_REINFORCEMENT_RULES

    def test_empty_findings(self) -> None:
        block = findings_to_reinforcement([], round_num=2, prior_score=80.0, target_score=85.0)
        assert len(block.rules) == 0
        assert "0 violation(s)" in block.escalation_note

    def test_sort_by_severity(self) -> None:
        findings = [
            _make_finding("F-minor", "minor"),
            _make_finding("F-blocker", "blocker"),
            _make_finding("F-major", "major"),
            _make_finding("F-critical", "critical"),
        ]
        block = findings_to_reinforcement(
            findings, round_num=2, prior_score=65.0, target_score=85.0, severity_floor="minor"
        )
        severities = [r.severity for r in block.rules]
        assert severities == ["blocker", "critical", "major", "minor"]

    def test_suggestion_appended(self) -> None:
        findings = [_make_finding(suggestion="add try-catch")]
        block = findings_to_reinforcement(
            findings, round_num=2, prior_score=70.0, target_score=85.0
        )
        assert "add try-catch" in block.rules[0].mandate

    def test_escalation_note_format(self) -> None:
        findings = [_make_finding()]
        block = findings_to_reinforcement(
            findings, round_num=3, prior_score=78.5, target_score=85.0
        )
        assert "Round 2 score: 78.5/85.0" in block.escalation_note
        assert "1 violation(s)" in block.escalation_note


class TestReinforcementToDict:
    def test_serialization(self) -> None:
        block = ReinforcementBlock(
            round=2,
            prior_score=72.0,
            target_score=85.0,
            severity_floor="major",
            rules=(ReinforcementRule(id="F-1", severity="blocker", mandate="fix it", file="a.py"),),
            escalation_note="test note",
        )
        d = reinforcement_to_dict(block)
        assert d["round"] == 2
        assert d["prior_score"] == 72.0
        assert len(d["rules"]) == 1
        assert d["rules"][0]["file"] == "a.py"
        assert d["escalation_note"] == "test note"

    def test_omits_empty_file(self) -> None:
        block = ReinforcementBlock(
            round=1,
            prior_score=60.0,
            target_score=85.0,
            severity_floor="major",
            rules=(ReinforcementRule(id="F-1", severity="major", mandate="fix"),),
        )
        d = reinforcement_to_dict(block)
        assert "file" not in d["rules"][0]


class TestMergeIntoDispatch:
    def test_merge_into_existing(self) -> None:
        dispatch: dict = {
            "context": {
                "applicable_rules": {"loading_strategy": "standard"},
            }
        }
        block = ReinforcementBlock(
            round=2,
            prior_score=72.0,
            target_score=85.0,
            severity_floor="major",
        )
        result = merge_reinforcement_into_dispatch(dispatch, block)
        assert result is dispatch
        assert "reinforcement" in result["context"]["applicable_rules"]
        assert result["context"]["applicable_rules"]["loading_strategy"] == "standard"

    def test_creates_missing_context(self) -> None:
        dispatch: dict = {}
        block = ReinforcementBlock(
            round=2,
            prior_score=72.0,
            target_score=85.0,
            severity_floor="major",
        )
        result = merge_reinforcement_into_dispatch(dispatch, block)
        assert "context" in result
        assert "applicable_rules" in result["context"]
        assert "reinforcement" in result["context"]["applicable_rules"]
