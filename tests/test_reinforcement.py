"""Tests for devolaflow.gate.reinforcement."""

from __future__ import annotations

import pytest

from devolaflow.gate.models import Finding
from devolaflow.gate.reinforcement import (
    FENCE_DEFAULT_SEVERITY,
    MAX_REINFORCEMENT_RULES,
    ReinforcementBlock,
    ReinforcementRule,
    fence_to_instruction,
    findings_to_reinforcement,
    merge_reinforcement_into_dispatch,
    reinforcement_to_dict,
)
from devolaflow.harness.tiers import SOURCE_TIERS, summarize_constraints


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
        assert reinforcement_to_dict(block)["rules"][0]["tier"] == "guard"

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
        rule = d["rules"][0]
        assert rule["file"] == "a.py"
        assert rule["tier"] == SOURCE_TIERS["reinforcement_rule"] == "guard"
        assert list(rule) == ["id", "severity", "mandate", "file", "tier"]
        assert summarize_constraints({"reinforce": d}) == (
            1,
            {"invariant": 0, "guard": 1, "advisory": 0},
            1.0,
        )
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
        assert d["rules"][0]["tier"] == "guard"
        assert list(d["rules"][0]) == ["id", "severity", "mandate", "tier"]

    def test_empty_serialization_preserves_shape(self) -> None:
        block = ReinforcementBlock(
            round=1,
            prior_score=0.0,
            target_score=85.0,
            severity_floor="major",
        )
        assert reinforcement_to_dict(block) == {
            "round": 1,
            "prior_score": 0.0,
            "target_score": 85.0,
            "severity_floor": "major",
            "rules": [],
            "escalation_note": "",
        }


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
            rules=(ReinforcementRule(id="F-1", severity="major", mandate="fix"),),
        )
        result = merge_reinforcement_into_dispatch(dispatch, block)
        assert result is dispatch
        applicable_rules = result["context"]["applicable_rules"]
        assert applicable_rules["reinforcement"]["rules"][0]["tier"] == "guard"
        assert applicable_rules["loading_strategy"] == "standard"

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


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-04) — fence_to_instruction tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFenceToInstructionDeterministicId:
    """Per ``patch_plan §3 P-04 AC #1`` the rule id MUST be deterministic."""

    def test_lint_default_id_is_f_lint_001(self) -> None:
        rule = fence_to_instruction("lint", {"file": "x.py", "msg": "oops"})
        assert rule.id == "F-lint-001"

    def test_id_increments_with_sequence(self) -> None:
        ids = [
            fence_to_instruction("lint", {"msg": "a"}, sequence=n).id for n in (1, 2, 3, 17, 999)
        ]
        assert ids == ["F-lint-001", "F-lint-002", "F-lint-003", "F-lint-017", "F-lint-999"]

    def test_id_format_zero_pads_to_three_digits(self) -> None:
        rule = fence_to_instruction("typecheck", {"msg": "type mismatch"}, sequence=7)
        assert rule.id == "F-typecheck-007"

    def test_pure_function_same_input_same_output(self) -> None:
        a = fence_to_instruction("build", {"file": "Makefile", "msg": "exit=2"}, sequence=4)
        b = fence_to_instruction("build", {"file": "Makefile", "msg": "exit=2"}, sequence=4)
        assert a == b


class TestFenceToInstructionAllFenceTypes:
    """Coverage across all 5 documented fence types (lint/format/typecheck/test/build)."""

    @pytest.mark.parametrize(
        ("fence_type", "expected_severity"),
        [
            ("lint", "major"),
            ("format", "major"),
            ("typecheck", "critical"),
            ("test", "critical"),
            ("build", "critical"),
        ],
    )
    def test_default_severity_matches_table(self, fence_type: str, expected_severity: str) -> None:
        rule = fence_to_instruction(fence_type, {"msg": "boom"})
        assert rule.severity == expected_severity
        assert FENCE_DEFAULT_SEVERITY[fence_type] == expected_severity

    @pytest.mark.parametrize(
        "fence_type",
        ["lint", "format", "typecheck", "test", "build"],
    )
    def test_severity_at_or_above_major_for_all_known_types(self, fence_type: str) -> None:
        """AC #1: severity ≥ major for every known fence type."""
        rule = fence_to_instruction(fence_type, {"msg": "x"})
        assert rule.severity in ("major", "critical", "blocker")

    @pytest.mark.parametrize(
        "fence_type",
        ["lint", "format", "typecheck", "test", "build"],
    )
    def test_id_prefix_matches_fence_type(self, fence_type: str) -> None:
        rule = fence_to_instruction(fence_type, {"msg": "x"})
        assert rule.id.startswith(f"F-{fence_type}-")

    def test_unknown_fence_type_falls_back_to_major(self) -> None:
        rule = fence_to_instruction("custom_check", {"msg": "boom"})
        assert rule.id == "F-custom_check-001"
        assert rule.severity == "major"

    def test_severity_override_is_honoured(self) -> None:
        rule = fence_to_instruction("lint", {"msg": "x"}, severity="blocker")
        assert rule.severity == "blocker"


class TestFenceToInstructionMandate:
    """The MUST-fix wording is the contract surfaced to the next-round L3."""

    def test_must_fix_prefix_present(self) -> None:
        rule = fence_to_instruction("lint", {"file": "x.py", "msg": "oops"})
        assert rule.mandate.startswith("MUST fix lint error")

    def test_mandate_includes_file_and_line(self) -> None:
        rule = fence_to_instruction(
            "lint",
            {"file": "src/foo.py", "line": 42, "msg": "E501 line too long (123 > 79)"},
        )
        assert "src/foo.py:42" in rule.mandate
        assert "E501 line too long (123 > 79)" in rule.mandate

    def test_mandate_omits_location_when_file_missing(self) -> None:
        rule = fence_to_instruction("typecheck", {"msg": "global type error"})
        assert rule.mandate == "MUST fix typecheck error: global type error"

    def test_mandate_omits_line_when_only_file_present(self) -> None:
        rule = fence_to_instruction("build", {"file": "Makefile", "msg": "exit=2"})
        # No file:line: prefix when line is absent — the only colon is the
        # one that separates "at <file>" from the message body.
        assert rule.mandate == "MUST fix build error at Makefile: exit=2"

    def test_mandate_handles_string_payload(self) -> None:
        rule = fence_to_instruction("test", "5 tests failed")
        assert rule.mandate == "MUST fix test error: 5 tests failed"
        assert rule.file == ""

    def test_mandate_handles_empty_msg_with_placeholder(self) -> None:
        rule = fence_to_instruction("lint", {})
        assert "(no details provided)" in rule.mandate


class TestFenceToInstructionTokenBudget:
    """``max_tokens`` truncates the rendered mandate (≈ 4 chars/token)."""

    def test_long_mandate_is_truncated(self) -> None:
        long_msg = "X" * 5_000
        rule = fence_to_instruction("lint", {"msg": long_msg}, max_tokens=50)
        assert rule.mandate.endswith("…")
        assert len(rule.mandate) <= 50 * 4

    def test_short_mandate_not_truncated(self) -> None:
        rule = fence_to_instruction("lint", {"msg": "tiny"}, max_tokens=200)
        assert "…" not in rule.mandate
        assert "tiny" in rule.mandate

    def test_max_tokens_zero_disables_truncation(self) -> None:
        long_msg = "X" * 5_000
        rule = fence_to_instruction("lint", {"msg": long_msg}, max_tokens=0)
        assert "…" not in rule.mandate
        assert rule.mandate.endswith("X")

    def test_max_tokens_one_yields_4_char_budget(self) -> None:
        """``max_tokens=1`` ⇒ 4-char budget (the chars-per-token constant)."""
        rule = fence_to_instruction("lint", {"msg": "long enough to overflow"}, max_tokens=1)
        assert rule.mandate.endswith("…")
        assert len(rule.mandate) == 4


class TestFenceToInstructionFile:
    """The originating file is preserved on the rule for downstream targeting."""

    def test_file_field_populated_from_payload(self) -> None:
        rule = fence_to_instruction("lint", {"file": "src/foo.py", "msg": "x"})
        assert rule.file == "src/foo.py"

    def test_file_field_empty_when_string_payload(self) -> None:
        rule = fence_to_instruction("test", "global failure")
        assert rule.file == ""

    def test_file_field_empty_when_omitted(self) -> None:
        rule = fence_to_instruction("typecheck", {"msg": "x"})
        assert rule.file == ""


class TestFenceToInstructionValidation:
    """S-5: invalid inputs raise instead of silently producing bad rules."""

    def test_empty_fence_type_raises(self) -> None:
        with pytest.raises(ValueError, match="fence_type"):
            fence_to_instruction("", {"msg": "x"})

    def test_zero_sequence_raises(self) -> None:
        with pytest.raises(ValueError, match="sequence"):
            fence_to_instruction("lint", {"msg": "x"}, sequence=0)

    def test_negative_sequence_raises(self) -> None:
        with pytest.raises(ValueError, match="sequence"):
            fence_to_instruction("lint", {"msg": "x"}, sequence=-1)

    def test_non_dict_non_str_payload_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="fence_payload"):
            fence_to_instruction("lint", 12345)  # type: ignore[arg-type]


class TestFenceToInstructionReturnType:
    """The result is a vanilla :class:`ReinforcementRule` so existing
    serialisation (``reinforcement_to_dict``) works without special-casing."""

    def test_returns_reinforcement_rule(self) -> None:
        rule = fence_to_instruction("lint", {"file": "x.py", "msg": "x"})
        assert isinstance(rule, ReinforcementRule)

    def test_serialises_through_reinforcement_to_dict(self) -> None:
        block = ReinforcementBlock(
            round=2,
            prior_score=70.0,
            target_score=85.0,
            severity_floor="major",
            rules=(
                fence_to_instruction("lint", {"file": "a.py", "msg": "x"}),
                fence_to_instruction("test", {"msg": "5 failed"}),
            ),
        )
        data = reinforcement_to_dict(block)
        ids = [r["id"] for r in data["rules"]]
        assert ids == ["F-lint-001", "F-test-001"]
        assert [r["tier"] for r in data["rules"]] == ["guard", "guard"]
        assert data["rules"][0]["file"] == "a.py"
        assert "file" not in data["rules"][1]
