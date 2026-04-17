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


class TestGenerateRoundDispatch:
    """V6-01: ProposalGenerator.generate_round_dispatch wiring."""

    def _verdict(self, findings: list, score: float = 72.0) -> GateVerdict:
        return GateVerdict(
            decision="FAIL",
            rationale="test",
            composite_score=score,
            details={"findings": findings},
        )

    def _base_dispatch(self) -> dict:
        return {
            "task_id": "T-001",
            "task_type": "refactor",
            "context": {
                "applicable_rules": {"loading_strategy": "standard"},
                "target_files": ["src/foo.py"],
            },
        }

    def test_generate_round_dispatch_round1_passthrough(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        findings = [
            Finding(
                finding_id="F-1",
                severity="critical",
                category="quality",
                location="src/foo.py",
                description="bad",
            )
        ]
        result = gen.generate_round_dispatch(base, self._verdict(findings), round_num=1)
        assert "reinforcement" not in result["context"]["applicable_rules"]
        assert result["task_id"] == base["task_id"]
        assert result["context"]["applicable_rules"]["loading_strategy"] == "standard"

    def test_generate_round_dispatch_round2_injects_reinforcement(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        findings = [
            Finding(
                finding_id="F-1",
                severity="blocker",
                category="security",
                location="src/foo.py",
                description="SQL injection",
                suggestion="use parameterized queries",
            ),
            Finding(
                finding_id="F-2",
                severity="critical",
                category="quality",
                location="src/bar.py",
                description="missing error handling",
            ),
        ]
        verdict = self._verdict(findings, score=65.0)
        result = gen.generate_round_dispatch(base, verdict, round_num=2, target_score=90.0)

        reinforcement = result["context"]["applicable_rules"]["reinforcement"]
        assert reinforcement["round"] == 2
        assert reinforcement["prior_score"] == 65.0
        assert reinforcement["target_score"] == 90.0
        assert len(reinforcement["rules"]) == 2
        ids = [r["id"] for r in reinforcement["rules"]]
        assert "F-1" in ids and "F-2" in ids
        assert result["context"]["applicable_rules"]["loading_strategy"] == "standard"

    def test_generate_round_dispatch_empty_verdict(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        result = gen.generate_round_dispatch(base, self._verdict([]), round_num=2)
        assert "reinforcement" not in result["context"]["applicable_rules"]
        assert result == base

    def test_generate_round_dispatch_none_verdict(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        result = gen.generate_round_dispatch(base, None, round_num=3)
        assert "reinforcement" not in result["context"]["applicable_rules"]
        assert result == base

    def test_generate_round_dispatch_does_not_mutate_input(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        base_snapshot = {
            "task_id": base["task_id"],
            "rules_keys": list(base["context"]["applicable_rules"].keys()),
            "target_files": list(base["context"]["target_files"]),
        }
        findings = [
            Finding(
                finding_id="F-1",
                severity="critical",
                category="quality",
                location="src/foo.py",
                description="issue",
            )
        ]
        result = gen.generate_round_dispatch(base, self._verdict(findings), round_num=2)

        assert "reinforcement" not in base["context"]["applicable_rules"]
        assert base["task_id"] == base_snapshot["task_id"]
        assert list(base["context"]["applicable_rules"].keys()) == base_snapshot["rules_keys"]
        assert base["context"]["target_files"] == base_snapshot["target_files"]
        assert result is not base
        assert result["context"] is not base["context"]

    def test_generate_round_dispatch_severity_floor(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        findings = [
            Finding(
                finding_id="F-BL",
                severity="blocker",
                category="q",
                location="",
                description="a",
            ),
            Finding(
                finding_id="F-CR",
                severity="critical",
                category="q",
                location="",
                description="b",
            ),
            Finding(
                finding_id="F-MA",
                severity="major",
                category="q",
                location="",
                description="c",
            ),
            Finding(
                finding_id="F-MI",
                severity="minor",
                category="q",
                location="",
                description="d",
            ),
        ]
        verdict = self._verdict(findings, score=70.0)
        result = gen.generate_round_dispatch(base, verdict, round_num=2, severity_floor="critical")
        reinforcement = result["context"]["applicable_rules"]["reinforcement"]
        ids = [r["id"] for r in reinforcement["rules"]]
        assert "F-BL" in ids
        assert "F-CR" in ids
        assert "F-MA" not in ids
        assert "F-MI" not in ids


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
