"""Tests for the KimiCode YAML-driven adapter (v6.0.4 A1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.adapters.base import _find_project_root, load_workflow_skill
from devolaflow.adapters.data_driven import DataDrivenAdapter


@pytest.fixture
def kimicode_config() -> dict:
    root = _find_project_root()
    return yaml.safe_load((root / "adapter_configs" / "kimicode.yaml").read_text())


@pytest.fixture
def build_result(tmp_path: Path, kimicode_config: dict):
    source, agent_dir = load_workflow_skill()
    adapter = DataDrivenAdapter(kimicode_config)
    out_dir = tmp_path / "kimicode"
    return adapter.build(source, agent_dir, out_dir), out_dir


def test_kimicode_config_metadata(kimicode_config: dict):
    assert kimicode_config["name"] == "kimicode"
    assert kimicode_config["display_name"] == "KimiCode"
    assert kimicode_config["tier"] == "high_priority"
    assert kimicode_config["version_added"] == "6.0.4"


def test_kimicode_builds_skill_md(build_result):
    _, out_dir = build_result
    skill = out_dir / ".kimi" / "skills" / "devola-flow" / "SKILL.md"
    assert skill.exists()
    assert skill.is_file()
    assert skill.read_text().strip()


def test_kimicode_frontmatter_injected(build_result):
    _, out_dir = build_result
    skill = out_dir / ".kimi" / "skills" / "devola-flow" / "SKILL.md"
    text = skill.read_text()
    assert "platform: kimicode" in text
    assert "compatible_with: [cursor, codex, claude]" in text
    # Existing frontmatter fields must still be present.
    assert text.startswith("---")


def test_kimicode_budget_under_500(build_result):
    result, _ = build_result
    assert result.budget_ok, f"KimiCode over budget: {result.budget_details}"
    # Format: "SKILL.md: <actual>/<max> lines"
    assert "lines" in result.budget_details
    actual = int(result.budget_details.split(":")[1].strip().split("/")[0])
    assert actual <= 500


def test_kimicode_copies_references_tree(build_result):
    _, out_dir = build_result
    refs = out_dir / ".kimi" / "skills" / "devola-flow" / "references"
    assert refs.is_dir()
    ref_files = list(refs.glob("*.md"))
    assert len(ref_files) >= 6
    # Spot-check a canonical reference that the core adapters also ship.
    names = {p.name for p in ref_files}
    assert "agent-hierarchy.md" in names
    assert "meta-framework.md" in names


def test_kimicode_copies_examples_tree(build_result):
    _, out_dir = build_result
    examples = out_dir / ".kimi" / "skills" / "devola-flow" / "examples"
    assert examples.is_dir()
    assert list(examples.glob("*.md"))


def test_kimicode_result_tool_name(build_result):
    result, _ = build_result
    assert result.tool == "kimicode"
