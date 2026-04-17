"""Tests for the Zed YAML-driven adapter (v6.1.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.adapters.base import _find_project_root, load_workflow_skill
from devolaflow.adapters.data_driven import DataDrivenAdapter


@pytest.fixture
def zed_config() -> dict:
    root = _find_project_root()
    return yaml.safe_load((root / "adapter_configs" / "zed.yaml").read_text())


@pytest.fixture
def build_result(tmp_path: Path, zed_config: dict):
    source, agent_dir = load_workflow_skill()
    adapter = DataDrivenAdapter(zed_config)
    out_dir = tmp_path / "zed"
    return adapter.build(source, agent_dir, out_dir), out_dir


def test_zed_config_metadata(zed_config: dict):
    assert zed_config["name"] == "zed"
    assert zed_config["display_name"] == "Zed"
    assert zed_config["tier"] == "tier_1"
    assert zed_config["version_added"] == "6.1.3"


def test_zed_builds_main_file(build_result):
    _, out_dir = build_result
    rules = out_dir / ".rules" / "devola-flow.md"
    assert rules.exists()
    assert rules.is_file()
    assert rules.read_text().strip()


def test_zed_strips_frontmatter(build_result):
    _, out_dir = build_result
    rules = out_dir / ".rules" / "devola-flow.md"
    text = rules.read_text()
    assert not text.startswith("---")
    assert "token_estimate:" not in text.split("\n", 1)[0]


def test_zed_copies_references_tree(build_result):
    _, out_dir = build_result
    refs = out_dir / ".rules" / "references"
    assert refs.is_dir()
    ref_files = list(refs.glob("*.md"))
    assert len(ref_files) >= 6
    names = {p.name for p in ref_files}
    assert "agent-hierarchy.md" in names
    assert "meta-framework.md" in names


def test_zed_budget_under_limit(build_result):
    result, _ = build_result
    assert result.budget_ok, f"Zed over budget: {result.budget_details}"
    assert "lines" in result.budget_details
    actual = int(result.budget_details.split(":")[1].strip().split("/")[0])
    max_val = int(result.budget_details.split("/")[1].strip().split()[0])
    assert max_val == 600
    assert actual <= 600


def test_zed_result_tool_name(build_result):
    result, _ = build_result
    assert result.tool == "zed"


def test_zed_output_base_dir_is_dot_rules(build_result):
    """Top-level Zed output must live under ``.rules/``."""
    _, out_dir = build_result
    base = out_dir / ".rules"
    assert base.is_dir()
    assert (base / "devola-flow.md").exists()
    assert (base / "references").is_dir()
