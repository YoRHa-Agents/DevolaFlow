"""Schema validation tests — verify YAML command strings and dispatch schema structure."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_CONTEXT_PROFILES = _ROOT / "workflow-system" / "agent" / "context_profiles.yaml"
_PLUGINS_YAML = _ROOT / "workflow-system" / "agent" / "plugins.yaml"
_TASK_DISPATCH = _ROOT / "schemas" / "task-dispatch.schema.yaml"
_LEAN_DISPATCH = _ROOT / "schemas" / "lean-dispatch.yaml"

V1_FORBIDDEN = ["--format json", "--limit ", "--decompose", "--index", "--dimensions"]
VALID_STAGES = {
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


@pytest.fixture(scope="module")
def context_profiles() -> dict:
    return yaml.safe_load(_CONTEXT_PROFILES.read_text()) or {}


@pytest.fixture(scope="module")
def plugins_yaml() -> dict:
    return yaml.safe_load(_PLUGINS_YAML.read_text()) or {}


@pytest.fixture(scope="module")
def task_dispatch_schema() -> dict:
    return yaml.safe_load(_TASK_DISPATCH.read_text()) or {}


@pytest.fixture(scope="module")
def lean_dispatch() -> dict:
    return yaml.safe_load(_LEAN_DISPATCH.read_text()) or {}


class TestNinesCommandV2Compliance:
    def test_context_profiles_commands_use_v2(self, context_profiles: dict) -> None:
        nines = context_profiles.get("nines_integration", {})
        commands = nines.get("commands", {})
        for key, cmd in commands.items():
            assert cmd.startswith("nines -f json"), (
                f"context_profiles nines_integration.commands.{key} "
                f"must start with 'nines -f json', got: {cmd!r}"
            )

    def test_context_profiles_no_v1_patterns(self, context_profiles: dict) -> None:
        nines = context_profiles.get("nines_integration", {})
        commands = nines.get("commands", {})
        for key, cmd in commands.items():
            for pat in V1_FORBIDDEN:
                assert pat not in cmd, (
                    f"context_profiles {key} contains v1 pattern {pat!r}: {cmd!r}"
                )

    def test_plugins_stage_mapping_v2(self, plugins_yaml: dict) -> None:
        nines_plugin = plugins_yaml.get("plugins", {}).get("nines", {})
        stage_map = nines_plugin.get("stage_mapping", {})
        for stage, cmd in stage_map.items():
            assert cmd.startswith("nines -f json"), (
                f"plugins.yaml nines.stage_mapping.{stage} "
                f"must start with 'nines -f json', got: {cmd!r}"
            )

    def test_plugins_stage_mapping_valid_stages(self, plugins_yaml: dict) -> None:
        nines_plugin = plugins_yaml.get("plugins", {}).get("nines", {})
        stage_map = nines_plugin.get("stage_mapping", {})
        for stage in stage_map:
            assert stage in VALID_STAGES, (
                f"plugins.yaml stage_mapping key '{stage}' "
                f"is not a valid DevolaFlow stage primitive"
            )


class TestTaskDispatchSchema:
    def test_required_top_level_fields(self, task_dispatch_schema: dict) -> None:
        required = task_dispatch_schema.get("instance_top_level_required", [])
        for field in ("header", "task", "context", "acceptance"):
            assert field in required, f"Missing required field: {field}"

    def test_applicable_rules_has_reinforcement(self, task_dispatch_schema: dict) -> None:
        fields = task_dispatch_schema.get("fields", {})
        context = fields.get("context", {}).get("children", {})
        rules = context.get("applicable_rules", {}).get("children", {})
        assert "reinforcement" in rules, (
            "applicable_rules must have 'reinforcement' child (v5.1+ addition)"
        )

    def test_header_has_model_hint(self, task_dispatch_schema: dict) -> None:
        header = task_dispatch_schema.get("fields", {}).get("header", {}).get("children", {})
        assert "model_hint" in header
        assert "decomposition_mode" in header
        assert "compression_intensity" in header


class TestLeanDispatch:
    def test_has_lean_format_spec(self, lean_dispatch: dict) -> None:
        assert "lean_format_spec" in lean_dispatch

    def test_lean_spec_has_reinforce(self, lean_dispatch: dict) -> None:
        spec = lean_dispatch.get("lean_format_spec", {})
        rules = spec.get("rules", {})
        assert "reinforce" in rules, (
            "lean_format_spec.rules must have 'reinforce' field (v5.1+ addition)"
        )

    def test_compression_rules_structure(self, lean_dispatch: dict) -> None:
        comp = lean_dispatch.get("compression_rules", {})
        assert "preserve_list" in comp
        assert "drop_list" in comp
        assert "intensity_tiers" in comp
