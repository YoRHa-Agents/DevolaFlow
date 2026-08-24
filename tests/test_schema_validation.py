"""Schema validation tests — verify YAML command strings and dispatch schema structure."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_TASK_DISPATCH = _ROOT / "schemas" / "task-dispatch.schema.yaml"
_LEAN_DISPATCH = _ROOT / "schemas" / "lean-dispatch.yaml"


@pytest.fixture(scope="module")
def task_dispatch_schema() -> dict:
    return yaml.safe_load(_TASK_DISPATCH.read_text()) or {}


@pytest.fixture(scope="module")
def lean_dispatch() -> dict:
    return yaml.safe_load(_LEAN_DISPATCH.read_text()) or {}


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
        assert "reinforce" in spec, "lean_format_spec must have top-level 'reinforce' field"
        assert "reinforce" not in spec.get("rules", {})

    def test_compression_rules_structure(self, lean_dispatch: dict) -> None:
        comp = lean_dispatch.get("compression_rules", {})
        assert "preserve_list" in comp
        assert "drop_list" in comp
        assert "intensity_tiers" in comp
