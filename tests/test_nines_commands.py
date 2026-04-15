"""Tests for devolaflow.nines.commands — NineS CLI command templates."""

from __future__ import annotations

import pytest

from devolaflow.nines.commands import (
    COMMANDS,
    DEFAULT_PARAMS,
    NINES_GLOBAL_FLAGS,
    STAGE_MAPPING,
    build_command,
    build_stage_command,
)

VALID_DEVOLAFLOW_STAGE_PRIMITIVES = frozenset(
    {
        "research",
        "analyze",
        "design",
        "plan",
        "implement",
        "refine",
        "review",
        "test",
        "validate",
        "release",
        "deploy",
        "monitor",
        "gate",
    }
)


class TestBuildCommand:
    """Tests for build_command()."""

    @pytest.mark.parametrize("key", sorted(COMMANDS))
    def test_each_command_key_produces_string(self, key: str) -> None:
        result = build_command(key, query="test", target="/tmp")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.parametrize("key", sorted(COMMANDS))
    def test_all_commands_start_with_nines_json(self, key: str) -> None:
        result = build_command(key, query="test", target="/tmp")
        assert result.startswith(f"nines {NINES_GLOBAL_FLAGS} ")

    def test_unknown_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown command key"):
            build_command("nonexistent_command")

    def test_custom_kwargs_override_defaults(self) -> None:
        result = build_command("collect", source="arxiv", max_results=5, query="LLM")
        assert "--source arxiv" in result
        assert "--max-results 5" in result

    def test_defaults_applied_when_no_kwargs(self) -> None:
        result = build_command("self_eval")
        assert f"--project-root {DEFAULT_PARAMS['root']}" in result

    def test_collect_contains_query(self) -> None:
        result = build_command("collect", query="agent orchestration")
        assert '--query "agent orchestration"' in result

    def test_analyze_contains_target(self) -> None:
        result = build_command("analyze", target="/my/repo")
        assert "--target-path /my/repo" in result
        assert "--agent-impact" in result
        assert "--keypoints" in result

    def test_iterate_contains_threshold(self) -> None:
        result = build_command("iterate", threshold="0.10")
        assert "--threshold 0.10" in result

    def test_update_minimal(self) -> None:
        result = build_command("update")
        assert result == f"nines {NINES_GLOBAL_FLAGS} update"


class TestBuildStageCommand:
    """Tests for build_stage_command()."""

    @pytest.mark.parametrize("stage", sorted(STAGE_MAPPING))
    def test_each_stage_produces_string(self, stage: str) -> None:
        result = build_stage_command(stage, query="test", target="/tmp")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.parametrize("stage", sorted(STAGE_MAPPING))
    def test_stage_commands_start_with_nines_json(self, stage: str) -> None:
        result = build_stage_command(stage, query="test", target="/tmp")
        assert result.startswith(f"nines {NINES_GLOBAL_FLAGS} ")

    def test_unknown_stage_raises(self) -> None:
        with pytest.raises(ValueError, match="No NineS command for stage"):
            build_stage_command("nonexistent_stage")

    def test_custom_kwargs_override_defaults(self) -> None:
        result = build_stage_command("research", source="arxiv", query="test")
        assert "--source arxiv" in result

    def test_research_maps_to_collect(self) -> None:
        r1 = build_stage_command("research", query="q", source="s", max_results=10)
        r2 = build_command("collect", query="q", source="s", max_results=10)
        assert r1 == r2

    def test_analyze_maps_to_analyze(self) -> None:
        r1 = build_stage_command("analyze", target="/t", depth="shallow")
        r2 = build_command("analyze", target="/t", depth="shallow")
        assert r1 == r2

    def test_validate_maps_to_self_eval_compare(self) -> None:
        r1 = build_stage_command("validate", root="/r")
        r2 = build_command("self_eval_compare", root="/r")
        assert r1 == r2

    def test_monitor_maps_to_iterate(self) -> None:
        r1 = build_stage_command("monitor", threshold="0.02", root="/r")
        r2 = build_command("iterate", threshold="0.02", root="/r")
        assert r1 == r2


class TestStageMappingValidity:
    """Verify STAGE_MAPPING keys are valid DevolaFlow stage primitives."""

    @pytest.mark.parametrize("stage", sorted(STAGE_MAPPING))
    def test_stage_is_valid_primitive(self, stage: str) -> None:
        assert stage in VALID_DEVOLAFLOW_STAGE_PRIMITIVES, (
            f"{stage!r} is not a valid DevolaFlow stage primitive"
        )


class TestCommandsCompleteness:
    """Structural assertions on the COMMANDS dict."""

    def test_seven_commands_defined(self) -> None:
        assert len(COMMANDS) == 7

    def test_expected_keys_present(self) -> None:
        expected = {
            "collect",
            "analyze",
            "self_eval",
            "self_eval_compare",
            "iterate",
            "benchmark",
            "update",
        }
        assert set(COMMANDS) == expected

    def test_four_stages_mapped(self) -> None:
        assert len(STAGE_MAPPING) == 4

    def test_stage_mapping_keys(self) -> None:
        assert set(STAGE_MAPPING) == {"research", "analyze", "validate", "monitor"}
