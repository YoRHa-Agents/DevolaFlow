"""Tests for feedback → reinforcement bridge (P4) and round escalation (P8)."""

from __future__ import annotations

from devolaflow.feedback import ProposalGenerator
from devolaflow.gate.models import Finding, GateVerdict
from devolaflow.task_adaptive_selector import apply_round_escalation


class TestFeedbackReinforcementBridge:
    def _verdict_with_findings(self, findings: list, score: float = 72.0) -> GateVerdict:
        return GateVerdict(
            decision="FAIL",
            rationale="test",
            composite_score=score,
            details={"findings": findings},
        )

    def test_generate_reinforcement_basic(self) -> None:
        gen = ProposalGenerator()
        findings = [
            Finding(
                finding_id="F-1",
                severity="blocker",
                category="test",
                location="src/foo.py",
                description="missing error handling",
            )
        ]
        verdict = self._verdict_with_findings(findings)
        block = gen.generate_reinforcement(verdict, round_num=2)
        assert block is not None
        assert block.round == 2
        assert len(block.rules) == 1
        assert "MUST fix" in block.rules[0].mandate

    def test_generate_reinforcement_from_dicts(self) -> None:
        gen = ProposalGenerator()
        raw = [
            {
                "finding_id": "F-99",
                "severity": "critical",
                "category": "quality",
                "location": "src/bar.py",
                "description": "low coverage",
            }
        ]
        verdict = self._verdict_with_findings(raw)
        block = gen.generate_reinforcement(verdict, round_num=3)
        assert block is not None
        assert block.rules[0].id == "F-99"

    def test_generate_reinforcement_empty_findings(self) -> None:
        gen = ProposalGenerator()
        verdict = self._verdict_with_findings([])
        block = gen.generate_reinforcement(verdict, round_num=2)
        assert block is None

    def test_generate_reinforcement_no_details(self) -> None:
        gen = ProposalGenerator()
        verdict = GateVerdict(decision="FAIL", rationale="test", details={})
        block = gen.generate_reinforcement(verdict, round_num=2)
        assert block is None

    def test_custom_target_score(self) -> None:
        gen = ProposalGenerator()
        findings = [
            Finding(
                finding_id="F-1",
                severity="major",
                category="test",
                location="",
                description="issue",
            )
        ]
        verdict = self._verdict_with_findings(findings, score=60.0)
        block = gen.generate_reinforcement(verdict, round_num=2, target_score=90.0)
        assert block is not None
        assert block.target_score == 90.0
        assert "60.0/90.0" in block.escalation_note


class TestRoundEscalation:
    def test_round_1_no_change(self) -> None:
        profile = {"section_priorities": {"foo": "supplementary"}, "token_budget": 6000}
        result = apply_round_escalation(profile, round_num=1)
        assert result is profile

    def test_round_2_overrides(self) -> None:
        profile = {
            "section_priorities": {"foo": "supplementary"},
            "token_budget": 6000,
        }
        result = apply_round_escalation(profile, round_num=2)
        assert result is not profile
        assert result["section_priorities"]["rationalization_prevention"] == "critical"
        assert result["compression_intensity"] == "minimal"
        assert result["token_budget"] == 6000

    def test_round_3_model_and_budget(self) -> None:
        profile = {"section_priorities": {}, "token_budget": 6000}
        result = apply_round_escalation(profile, round_num=3)
        assert result["model_hint"] == "quality"
        assert result["token_budget"] == 7200

    def test_round_beyond_max_uses_highest(self) -> None:
        profile = {"section_priorities": {}, "token_budget": 5000}
        result = apply_round_escalation(profile, round_num=5)
        assert result["token_budget"] == 6000

    def test_does_not_mutate_original(self) -> None:
        profile = {"section_priorities": {"a": "important"}, "token_budget": 6000}
        apply_round_escalation(profile, round_num=2)
        assert "rationalization_prevention" not in profile["section_priorities"]

    def test_custom_escalation_config(self) -> None:
        config = {2: {"model_hint_override": "balanced", "token_budget_increase_pct": 50}}
        profile = {"section_priorities": {}, "token_budget": 4000}
        result = apply_round_escalation(profile, round_num=2, escalation_config=config)
        assert result["model_hint"] == "balanced"
        assert result["token_budget"] == 6000
