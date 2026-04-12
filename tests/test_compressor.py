"""Tests for the runtime lean format validator/compressor."""

from __future__ import annotations

from devolaflow.compressor import (
    DROP_LIST,
    INTENSITY_TIERS,
    compress_message,
    detect_drop_violations,
    validate_lean_format,
    validate_preserve_list,
)


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
