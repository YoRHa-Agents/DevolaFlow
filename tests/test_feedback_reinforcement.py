"""Tests for feedback → reinforcement bridge (P4) and round escalation (P8)."""

from __future__ import annotations

import copy
from types import SimpleNamespace

from devolaflow.feedback import ProposalGenerator
from devolaflow.gate.models import Finding, GateVerdict
from devolaflow.gate.reinforcement import merge_reinforcement_into_dispatch
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
            # v15.0.0 strict graduation (G-038): the pre_dispatch chain now
            # BLOCKS dispatches without a testable acceptance criterion
            # (VD002), so the fixture carries one like real dispatches do.
            "accept": ["refactor preserves behaviour and the suite stays green"],
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

    def test_round_inputs_prepend_selected_reverts_with_one_stable_cap(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        base["change_context"] = {"change_id": "round-reinforcement"}
        before = copy.deepcopy(base)
        checklist = SimpleNamespace(
            items=(
                SimpleNamespace(
                    item_id="C-G1.1",
                    assertion="first assertion",
                    verify="pytest first",
                    checked=False,
                    reverted_reason='Keep  "first reason" verbatim',
                ),
                SimpleNamespace(
                    item_id="C-G1.2",
                    assertion="second assertion",
                    verify="pytest second",
                    checked=False,
                    reverted_reason="second reason -> exact",
                ),
            )
        )
        selection = SimpleNamespace(
            selected=(
                SimpleNamespace(item_id="C-G1.1", priority="P0", reverted=True),
                SimpleNamespace(item_id="C-G1.2", priority="P1", reverted=True),
            )
        )
        findings = [
            Finding(
                finding_id="R-C-G1.1-002",
                severity="blocker",
                category="duplicate",
                location="",
                description="gate duplicate must lose to selected revert",
            ),
            *[
                Finding(
                    finding_id=f"F-G{index}",
                    severity="critical",
                    category="quality",
                    location=f"src/{index}.py",
                    description=f"gate issue {index}",
                )
                for index in range(1, 5)
            ],
        ]

        result = gen.generate_round_dispatch(
            base,
            self._verdict(findings, score=65.0),
            2,
            90.0,
            "major",
            checklist=checklist,
            selection=selection,
            round_n=2,
        )

        reinforcement = result["context"]["applicable_rules"]["reinforcement"]
        assert [rule["id"] for rule in reinforcement["rules"]] == [
            "R-C-G1.1-002",
            "R-C-G1.2-002",
            "F-G1",
            "F-G2",
            "F-G3",
        ]
        assert [rule["mandate"] for rule in reinforcement["rules"][:2]] == [
            'Keep  "first reason" verbatim',
            "second reason -> exact",
        ]
        assert all(rule["severity"] == "blocker" for rule in reinforcement["rules"][:2])
        assert reinforcement["prior_score"] == 65.0
        assert reinforcement["target_score"] == 90.0
        assert result["change_context"]["round_context"] == {
            "round_n": 2,
            "reverted_ids": ["C-G1.1", "C-G1.2"],
        }
        assert base == before

    def test_legacy_positional_gate_only_serialization_is_unchanged(self) -> None:
        gen = ProposalGenerator()
        base = self._base_dispatch()
        verdict = self._verdict(
            [
                Finding(
                    finding_id="F-POS",
                    severity="critical",
                    category="quality",
                    location="src/foo.py",
                    description="preserve positional API",
                )
            ],
            score=66.0,
        )
        block = gen.generate_reinforcement(verdict, 2, 91.0, "critical")
        assert block is not None
        expected = merge_reinforcement_into_dispatch(copy.deepcopy(base), block)

        result = gen.generate_round_dispatch(base, verdict, 2, 91.0, "critical")

        assert result == expected


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
