"""Tests for the Roo Code YAML-driven adapter (v6.1.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.adapters.base import _find_project_root, load_workflow_skill
from devolaflow.adapters.data_driven import DataDrivenAdapter


@pytest.fixture
def roo_config() -> dict:
    root = _find_project_root()
    return yaml.safe_load((root / "adapter_configs" / "roo.yaml").read_text())


@pytest.fixture
def build_result(tmp_path: Path, roo_config: dict):
    source, agent_dir = load_workflow_skill()
    adapter = DataDrivenAdapter(roo_config)
    out_dir = tmp_path / "roo"
    return adapter.build(source, agent_dir, out_dir), out_dir


def test_roo_config_metadata(roo_config: dict):
    assert roo_config["name"] == "roo"
    assert roo_config["display_name"] == "Roo Code"
    assert roo_config["tier"] == "tier_1"
    assert roo_config["version_added"] == "6.1.3"


def test_roo_builds_main_file(build_result):
    _, out_dir = build_result
    rules = out_dir / ".roo" / "rules" / "devola-flow.md"
    assert rules.exists()
    assert rules.is_file()
    assert rules.read_text().strip()


def test_roo_strips_frontmatter(build_result):
    _, out_dir = build_result
    rules = out_dir / ".roo" / "rules" / "devola-flow.md"
    text = rules.read_text()
    assert not text.startswith("---")
    assert "token_estimate:" not in text.split("\n", 1)[0]


def test_roo_copies_references_tree(build_result):
    _, out_dir = build_result
    refs = out_dir / ".roo" / "rules" / "references"
    assert refs.is_dir()
    ref_files = list(refs.glob("*.md"))
    assert len(ref_files) >= 6
    names = {p.name for p in ref_files}
    assert "agent-hierarchy.md" in names
    assert "meta-framework.md" in names


def test_roo_budget_under_limit(build_result):
    result, _ = build_result
    assert result.budget_ok, f"Roo over budget: {result.budget_details}"
    assert "lines" in result.budget_details
    actual = int(result.budget_details.split(":")[1].strip().split("/")[0])
    max_val = int(result.budget_details.split("/")[1].strip().split()[0])
    assert max_val == 800
    assert actual <= 800


def test_roo_result_tool_name(build_result):
    result, _ = build_result
    assert result.tool == "roo"


def test_roo_output_base_dir_is_dot_roo_rules(build_result):
    """Top-level Roo Code output must live under ``.roo/rules/``."""
    _, out_dir = build_result
    base = out_dir / ".roo" / "rules"
    assert base.is_dir()
    assert (base / "devola-flow.md").exists()
    assert (base / "references").is_dir()
