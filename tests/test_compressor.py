"""Tests for the runtime lean format validator/compressor."""

from __future__ import annotations

import pytest

from devolaflow.compressor import (
    DROP_LIST,
    INTENSITY_TIERS,
    DispatchLayoutError,
    ToolUseTruncation,
    assert_dispatch_layout,
    clear_old_tool_uses,
    compress_message,
    compute_dispatch_lcp_pct,
    detect_drop_violations,
    truncate_tool_output,
    validate_lean_format,
    validate_preserve_list,
)
from devolaflow.task_adaptive_selector import apply_round_escalation


class TestPreserveValidation:
    def test_file_paths_detected(self):
        msg = "Modified src/auth.py and tests/test_auth.py"
        result = validate_preserve_list(msg)
        assert "file_paths" in [p[0] for p in result["present"]]

    def test_version_strings_detected(self):
        msg = "Updated to version 4.1.0"
        result = validate_preserve_list(msg)
        assert "version_strings" in [p[0] for p in result["present"]]

    def test_commit_hashes_detected(self):
        msg = "Reverted commit abc1234 due to regression"
        result = validate_preserve_list(msg)
        assert "commit_hashes" in [p[0] for p in result["present"]]

    def test_task_ids_detected(self):
        msg = "Completed T04 and S02 tasks"
        result = validate_preserve_list(msg)
        assert "task_ids" in [p[0] for p in result["present"]]

    def test_error_messages_detected(self):
        msg = "Traceback: Error in module auth"
        result = validate_preserve_list(msg)
        assert "error_messages_verbatim" in [p[0] for p in result["present"]]

    def test_empty_message(self):
        result = validate_preserve_list("")
        assert result["integrity_score"] == 0.0
        assert result["present"] == []

    def test_integrity_score_range(self):
        msg = "src/auth.py version 4.1.0 commit abc1234 T04 Error cov 92%"
        result = validate_preserve_list(msg)
        assert 0.0 <= result["integrity_score"] <= 1.0

    def test_counts_are_positive(self):
        msg = "src/a.py and src/b.py both changed"
        result = validate_preserve_list(msg)
        for _, count in result["present"]:
            assert count > 0


class TestDropDetection:
    def test_filler_detected(self):
        msg = "Basically the code is essentially correct"
        result = detect_drop_violations(msg, "standard")
        assert result["violation_count"] > 0

    def test_clean_message(self):
        msg = "src/auth.py: added JWT validation, coverage 92%"
        result = detect_drop_violations(msg, "standard")
        assert result["compliance_score"] == 1.0

    def test_minimal_allows_hedging(self):
        msg = "This might cause issues"
        result = detect_drop_violations(msg, "minimal")
        assert result["violation_count"] == 0

    def test_aggressive_catches_all(self):
        msg = "Let me move on to the next section"
        result = detect_drop_violations(msg, "aggressive")
        assert result["violation_count"] > 0

    def test_pleasantries_caught_at_minimal(self):
        msg = "Thank you for the great question"
        result = detect_drop_violations(msg, "minimal")
        assert result["violation_count"] > 0

    def test_apologies_caught_at_minimal(self):
        msg = "Sorry for the confusion, I apologize"
        result = detect_drop_violations(msg, "minimal")
        assert result["violation_count"] > 0

    def test_meta_commentary_only_aggressive(self):
        msg = "I will now move on to the implementation"
        result_std = detect_drop_violations(msg, "standard")
        result_agg = detect_drop_violations(msg, "aggressive")
        assert result_agg["violation_count"] >= result_std["violation_count"]

    def test_invalid_intensity_falls_back_to_standard(self):
        msg = "Basically correct"
        result = detect_drop_violations(msg, "nonexistent_tier")
        assert result["violation_count"] > 0

    def test_tool_call_echoing_aggressive(self):
        msg = "I just ran the grep tool and found results"
        result = detect_drop_violations(msg, "aggressive")
        assert result["violation_count"] > 0


class TestCompression:
    def test_compress_removes_filler(self):
        msg = "Basically, the code is essentially working. Obviously it passes tests."
        result = compress_message(msg, "standard")
        assert result["compression_ratio"] > 0
        assert "basically" not in result["compressed_text"].lower()

    def test_compress_preserves_paths(self):
        msg = "Basically, modified src/auth.py with version 4.1.0 changes"
        result = compress_message(msg, "standard")
        assert "src/auth.py" in result["compressed_text"]
        assert "4.1.0" in result["compressed_text"]

    def test_compress_minimal_less_aggressive(self):
        msg = "Perhaps the code might need refactoring. Basically it works."
        r_min = compress_message(msg, "minimal")
        r_agg = compress_message(msg, "aggressive")
        assert r_agg["compression_ratio"] >= r_min["compression_ratio"]

    def test_compress_returns_token_counts(self):
        msg = "This is a test message with some filler content basically."
        result = compress_message(msg, "standard")
        assert result["original_tokens"] > 0
        assert result["compressed_tokens"] > 0
        assert result["compressed_tokens"] <= result["original_tokens"]

    def test_compress_collapses_whitespace(self):
        msg = "Basically   lots   of   spaces   here"
        result = compress_message(msg, "standard")
        assert "   " not in result["compressed_text"]

    def test_compress_strips_trailing_whitespace(self):
        msg = "Basically line one   \nBasically line two   "
        result = compress_message(msg, "standard")
        for line in result["compressed_text"].splitlines():
            assert line == line.rstrip()

    def test_compress_empty_message(self):
        result = compress_message("", "standard")
        assert result["compressed_text"] == ""
        assert result["compression_ratio"] == 0.0

    def test_compress_no_filler_message_unchanged(self):
        msg = "src/auth.py: added JWT validation"
        result = compress_message(msg, "standard")
        assert result["transformations_applied"] == []

    def test_compress_invalid_intensity_falls_back(self):
        msg = "Basically a test"
        result = compress_message(msg, "bogus")
        assert result["compression_ratio"] > 0


class TestValidation:
    def test_clean_lean_message_passes(self):
        msg = (
            "task_id: T01\n"
            "state: DONE\n"
            "artifacts:\n"
            "  - path: src/auth.py\n"
            "    delta: added JWT validation\n"
            "metrics:\n"
            "  tests_passed: 12\n"
            "  coverage_pct: 92"
        )
        result = validate_lean_format(msg, "standard")
        assert result["score"] > 70

    def test_verbose_message_low_score(self):
        msg = (
            "I think I've basically completed the task. "
            "Let me move on to explaining what I did. "
            "Obviously, the code works. "
            "Thank you for the opportunity."
        )
        result = validate_lean_format(msg, "standard")
        assert result["score"] < 50

    def test_intensity_affects_validation(self):
        msg = "Perhaps this approach might work. Let me explain."
        r_min = validate_lean_format(msg, "minimal")
        r_agg = validate_lean_format(msg, "aggressive")
        assert r_agg["score"] <= r_min["score"]

    def test_valid_flag_consistent_with_score(self):
        lean = "T01 src/auth.py: JWT validation, coverage 92%, version 4.1.0"
        result = validate_lean_format(lean, "standard")
        assert result["valid"] == (result["score"] >= 70)

    def test_details_populated(self):
        msg = "Basically a test with src/foo.py"
        result = validate_lean_format(msg, "standard")
        assert len(result["details"]) > 0

    def test_invalid_intensity_falls_back(self):
        msg = "Test message"
        result = validate_lean_format(msg, "nonexistent")
        assert result["intensity"] == "standard"

    def test_drops_remaining_lists_categories(self):
        msg = "Basically, I think this is essentially correct. Thank you."
        result = validate_lean_format(msg, "standard")
        assert len(result["drops_remaining"]) > 0


class TestEdgeCases:
    """Edge cases: unicode, whitespace-only, very long text, pattern coverage."""

    def test_unicode_cjk_preserved(self):
        msg = "修改了 src/auth.py 版本 4.1.0"
        result = validate_preserve_list(msg)
        assert "file_paths" in [p[0] for p in result["present"]]
        assert "version_strings" in [p[0] for p in result["present"]]

    def test_unicode_emoji_in_message(self):
        msg = "✅ src/auth.py passes — coverage 92%"
        result = compress_message(msg, "standard")
        assert "src/auth.py" in result["compressed_text"]
        assert "92%" in result["compressed_text"]

    def test_whitespace_only_input(self):
        result_preserve = validate_preserve_list("   \t\n  ")
        assert result_preserve["present"] == []
        assert result_preserve["integrity_score"] == 0.0

        result_compress = compress_message("   \t\n  ", "standard")
        assert result_compress["compressed_text"] == ""

        result_validate = validate_lean_format("   \t\n  ", "standard")
        assert result_validate["score"] <= 100

    def test_very_long_message(self):
        msg = ("src/auth.py changed. " * 500) + "Basically filler at the end."
        result = compress_message(msg, "standard")
        assert result["compression_ratio"] > 0
        assert "src/auth.py" in result["compressed_text"]

    def test_preserve_list_items_without_patterns(self):
        """Document that some PRESERVE_LIST items have no pattern and are skipped."""
        from devolaflow.compressor import PRESERVE_LIST, PRESERVE_PATTERNS

        items_without_patterns = [i for i in PRESERVE_LIST if i not in PRESERVE_PATTERNS]
        assert len(items_without_patterns) > 0, "Expected some items without patterns"
        expected_unmatched = {
            "acceptance_criteria",
            "artifact_references",
            "environment_identifiers",
            "dependency_versions",
            "line_numbers",
            "timing_values",
        }
        assert set(items_without_patterns) == expected_unmatched

    def test_compress_multiline_preserves_structure(self):
        msg = (
            "task_id: T01\n"
            "Basically the code works.\n"
            "artifacts:\n"
            "  - path: src/auth.py\n"
            "Obviously it passes tests.\n"
        )
        result = compress_message(msg, "standard")
        assert "src/auth.py" in result["compressed_text"]
        assert "task_id: T01" in result["compressed_text"]

    def test_compress_collapses_excessive_blank_lines(self):
        msg = "line one\n\n\n\n\nline two"
        result = compress_message(msg, "standard")
        assert "\n\n\n" not in result["compressed_text"]
        assert "line one" in result["compressed_text"]
        assert "line two" in result["compressed_text"]

    def test_detect_violations_empty_string(self):
        result = detect_drop_violations("", "aggressive")
        assert result["violation_count"] == 0
        assert result["compliance_score"] == 1.0

    def test_validate_lean_format_empty_string(self):
        result = validate_lean_format("", "standard")
        assert result["score"] >= 0
        assert isinstance(result["valid"], bool)


class TestIntensityTiers:
    def test_all_tiers_valid(self):
        for tier in ["minimal", "standard", "aggressive"]:
            assert tier in INTENSITY_TIERS

    def test_aggressive_includes_all(self):
        assert set(INTENSITY_TIERS["aggressive"]["active_drops"]) == set(DROP_LIST)

    def test_minimal_subset_of_standard(self):
        min_drops = set(INTENSITY_TIERS["minimal"]["active_drops"])
        std_drops = set(INTENSITY_TIERS["standard"]["active_drops"])
        assert min_drops.issubset(std_drops)

    def test_standard_subset_of_aggressive(self):
        std_drops = set(INTENSITY_TIERS["standard"]["active_drops"])
        agg_drops = set(INTENSITY_TIERS["aggressive"]["active_drops"])
        assert std_drops.issubset(agg_drops)

    def test_tier_values_are_in_drop_list(self):
        for tier_name, tier in INTENSITY_TIERS.items():
            for drop in tier["active_drops"]:
                assert drop in DROP_LIST, f"{drop} in {tier_name} not in DROP_LIST"


class TestDispatchLayoutInvariant:
    """v7.0.0 cache-layout-invariant tests (per ADR-001 §6).

    Verifies the canonical dispatch order, the round-over-round LCP SLO
    (>= 80% round 1->2, >= 70% round 1->3), and the additive rule for new
    top-level keys.
    """

    @staticmethod
    def _canonical_round_dispatch(round_num: int) -> dict:
        """Lean dispatch in canonical order. Round 1 omits ``reinforce``;
        rounds 2+ add it at canonical position 10."""
        payload: dict = {
            "hdr": {"id": "d-cache-001", "parent": "stage-cache", "layer": "wave"},
            "task": {"id": "T-CACHE-001", "type": "code", "title": "cache layout probe"},
            "goal": "demonstrate round-stable cached prefix",
            "assumptions": ["dispatch renderer preserves insertion order"],
            "pred": [{"ref": "ADR-001", "key_facts": ["LCP >= 80% r1->r2", "LCP >= 70% r1->r3"]}],
            "files": ["src/devolaflow/compressor.py", "schemas/lean-dispatch.yaml"],
            "rules": {"strategy": "standard", "lang": "python"},
            "shared": "Python 3.11+, ruff, pytest",
            "accept": ["assert_dispatch_layout accepts canonical", "LCP r1->r2 >= 80%"],
        }
        if round_num >= 2:
            rule = {"id": f"F-{round_num:03d}", "sev": "blocker", "mandate": "honour invariant"}
            payload["reinforce"] = {
                "round": round_num,
                "prior": 72.3 if round_num == 2 else 78.5,
                "target": 85,
                "rules": [rule],
            }
        payload["verify_cfg"] = {"visual": False, "accept": True}
        payload["gate"] = {"coverage": 85, "quality": 85, "blockers": 0, "retries": 2}
        return payload

    def test_assert_dispatch_layout_accepts_canonical(self):
        assert assert_dispatch_layout(self._canonical_round_dispatch(round_num=1)) is None

    def test_assert_dispatch_layout_rejects_reordered(self):
        payload = self._canonical_round_dispatch(round_num=2)
        keys = list(payload.keys())
        i_pred, i_reinforce = keys.index("pred"), keys.index("reinforce")
        keys[i_pred], keys[i_reinforce] = keys[i_reinforce], keys[i_pred]
        reordered = {k: payload[k] for k in keys}
        with pytest.raises(DispatchLayoutError) as exc_info:
            assert_dispatch_layout(reordered)
        assert "pred" in str(exc_info.value) and "reinforce" in str(exc_info.value)

    def test_dispatch_prefix_is_stable_across_rounds(self):
        r1 = self._canonical_round_dispatch(round_num=1)
        r2 = self._canonical_round_dispatch(round_num=2)
        r3 = self._canonical_round_dispatch(round_num=3)
        for payload in (r1, r2, r3):
            assert_dispatch_layout(payload)
        baseline = {"token_budget": 4800, "section_priorities": {}, "model_hint": "balanced"}
        round2_profile = apply_round_escalation(baseline, round_num=2)
        round3_profile = apply_round_escalation(baseline, round_num=3)
        assert round2_profile["token_budget"] >= baseline["token_budget"]
        assert round3_profile["token_budget"] >= round2_profile["token_budget"]
        lcp_12 = compute_dispatch_lcp_pct(r1, r2)
        lcp_13 = compute_dispatch_lcp_pct(r1, r3)
        assert lcp_12 >= 0.80, f"r1->r2 LCP {lcp_12:.4f} violates lcp_threshold_round_1_to_2"
        assert lcp_13 >= 0.70, f"r1->r3 LCP {lcp_13:.4f} violates lcp_threshold_round_1_to_3"

    def test_new_field_appended_not_inserted(self):
        payload = self._canonical_round_dispatch(round_num=1)
        appended = dict(payload, cache_hint={"prefix_pct": 0.83})
        assert assert_dispatch_layout(appended) is None
        keys = list(payload.keys())
        keys.insert(keys.index("gate"), "cache_hint")
        inserted = {k: ({"prefix_pct": 0.83} if k == "cache_hint" else payload[k]) for k in keys}
        with pytest.raises(DispatchLayoutError) as exc_info:
            assert_dispatch_layout(inserted)
        assert "gate" in str(exc_info.value)

    def test_assert_dispatch_layout_unknown_keys_after_spec(self):
        payload = self._canonical_round_dispatch(round_num=1)
        trailing = dict(payload, cache_hint={"prefix_pct": 0.83}, telemetry={"lcp": 0.83})
        assert assert_dispatch_layout(trailing) is None
        leading = {"telemetry": {"foo": "bar"}, **payload}
        with pytest.raises(DispatchLayoutError):
            assert_dispatch_layout(leading)


class TestToolOutputTruncation:
    """v7.0.1 tool-output truncation primitive (per ADR-002 §6).

    Verifies the head/tail/placeholder behaviour of ``truncate_tool_output``
    plus the most-recent-N + exclude-by-name policy of
    ``clear_old_tool_uses``. Together these primitives shrink convergence-
    round dispatches by replacing the bulky middle of older tool outputs
    with a short placeholder, while preserving authoritative ``Read`` output
    and the most recent N entries verbatim.
    """

    def test_truncate_tool_output_below_threshold(self):
        text = "x" * 999  # head_chars + tail_chars defaults sum to 1000
        result, removed = truncate_tool_output(text)
        assert result == text
        assert removed == 0

    def test_truncate_tool_output_above_threshold(self):
        head = "H" * 500
        middle = "M" * 1234
        tail = "T" * 500
        text = head + middle + tail
        result, removed = truncate_tool_output(text)
        assert removed == 1234
        assert result.startswith(head)
        assert result.endswith(tail)
        assert "[truncated 1234 chars]" in result
        assert len(result) == 500 + len("[truncated 1234 chars]") + 500

    def test_truncate_tool_output_placeholder_format(self):
        text = "a" * 100 + "X" * 50 + "b" * 100
        result, removed = truncate_tool_output(
            text,
            head_chars=100,
            tail_chars=100,
            placeholder_template="<<<{removed}>>>",
        )
        assert removed == 50
        assert "<<<50>>>" in result
        assert result == "a" * 100 + "<<<50>>>" + "b" * 100

    def test_truncate_tool_output_unicode_safe(self):
        head = "你" * 500
        middle = "好" * 200
        tail = "界" * 500
        text = head + middle + tail
        result, removed = truncate_tool_output(text)
        assert removed == 200
        assert result.startswith("你" * 500)
        assert result.endswith("界" * 500)
        assert "[truncated 200 chars]" in result
        assert len(text) == 1200
        assert len(head) == 500 and len(tail) == 500

    def test_clear_old_tool_uses_keeps_recent_n(self):
        long_output = "L" * 2000
        tool_uses = [{"name": "Shell", "output": long_output} for _ in range(8)]
        modified, summary = clear_old_tool_uses(tool_uses, keep=3)
        assert len(modified) == 8
        assert summary.kept_count == 3
        assert summary.cleared_count == 5
        for record in modified[-3:]:
            assert record["output"] == long_output
        for record in modified[:5]:
            assert record["output"] != long_output
            assert "[truncated" in record["output"]

    def test_clear_old_tool_uses_excludes_named_tools(self):
        long_output = "L" * 2000
        tool_uses = [
            {"name": "Read", "output": long_output},
            {"name": "Read", "output": long_output},
            {"name": "Shell", "output": long_output},
            {"name": "Read", "output": long_output},
            {"name": "Shell", "output": long_output},
            {"name": "Shell", "output": long_output},
        ]
        modified, summary = clear_old_tool_uses(tool_uses, keep=2)
        assert summary.cleared_count == 1
        assert summary.kept_count == 5
        for original, after in zip(tool_uses, modified, strict=True):
            if original["name"] == "Read":
                assert after["output"] == long_output
        for record in modified[-2:]:
            assert record["output"] == long_output
        assert modified[2]["output"] != long_output
        assert "[truncated" in modified[2]["output"]
        assert "Read" in summary.excluded_tool_names

    def test_clear_old_tool_uses_returns_summary(self):
        long_output = "L" * 2000
        tool_uses = [
            {"name": "Shell", "output": long_output},
            {"name": "Grep", "output": long_output},
            {"name": "Shell", "output": long_output},
            {"name": "Shell", "output": long_output},
            {"name": "Shell", "output": long_output},
            {"name": "Shell", "output": long_output},
        ]
        modified, summary = clear_old_tool_uses(
            tool_uses,
            keep=3,
            exclude_tool_names=("Read",),
            head_chars=200,
            tail_chars=200,
            placeholder_template="<{removed}>",
        )
        assert isinstance(summary, ToolUseTruncation)
        assert summary.kept_count + summary.cleared_count == len(tool_uses)
        assert summary.kept_count == 3
        assert summary.cleared_count == 3
        assert summary.head_chars == 200
        assert summary.tail_chars == 200
        assert summary.placeholder == "<{removed}>"
        assert summary.excluded_tool_names == ("Read",)
        for record in modified[:3]:
            assert "<1600>" in record["output"]
        for record, original in zip(modified[-3:], tool_uses[-3:], strict=True):
            assert record["output"] == original["output"]

    def test_clear_old_tool_uses_empty_list(self):
        modified, summary = clear_old_tool_uses([])
        assert modified == []
        assert isinstance(summary, ToolUseTruncation)
        assert summary.kept_count == 0
        assert summary.cleared_count == 0
        assert summary.head_chars == 500
        assert summary.tail_chars == 500
        assert summary.excluded_tool_names == ("Read",)
        assert summary.placeholder == "[truncated {removed} chars]"
