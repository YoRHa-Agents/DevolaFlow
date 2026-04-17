"""Tests for the Cline YAML-driven adapter (v6.1.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.adapters.base import _find_project_root, load_workflow_skill
from devolaflow.adapters.data_driven import DataDrivenAdapter


@pytest.fixture
def cline_config() -> dict:
    root = _find_project_root()
    return yaml.safe_load((root / "adapter_configs" / "cline.yaml").read_text())


@pytest.fixture
def build_result(tmp_path: Path, cline_config: dict):
    source, agent_dir = load_workflow_skill()
    adapter = DataDrivenAdapter(cline_config)
    out_dir = tmp_path / "cline"
    return adapter.build(source, agent_dir, out_dir), out_dir


def test_cline_config_metadata(cline_config: dict):
    assert cline_config["name"] == "cline"
    assert cline_config["display_name"] == "Cline"
    assert cline_config["tier"] == "tier_1"
    assert cline_config["version_added"] == "6.1.3"


def test_cline_builds_main_file(build_result):
    _, out_dir = build_result
    rules = out_dir / ".clinerules" / "devola-flow.md"
    assert rules.exists()
    assert rules.is_file()
    assert rules.read_text().strip()


def test_cline_strips_frontmatter(build_result):
    _, out_dir = build_result
    rules = out_dir / ".clinerules" / "devola-flow.md"
    text = rules.read_text()
    assert not text.startswith("---")
    assert "token_estimate:" not in text.split("\n", 1)[0]


def test_cline_copies_references_tree(build_result):
    _, out_dir = build_result
    refs = out_dir / ".clinerules" / "references"
    assert refs.is_dir()
    ref_files = list(refs.glob("*.md"))
    assert len(ref_files) >= 6
    names = {p.name for p in ref_files}
    assert "agent-hierarchy.md" in names
    assert "meta-framework.md" in names


def test_cline_budget_under_limit(build_result):
    result, _ = build_result
    assert result.budget_ok, f"Cline over budget: {result.budget_details}"
    assert "lines" in result.budget_details
    actual = int(result.budget_details.split(":")[1].strip().split("/")[0])
    max_val = int(result.budget_details.split("/")[1].strip().split()[0])
    assert max_val == 800
    assert actual <= 800


def test_cline_result_tool_name(build_result):
    result, _ = build_result
    assert result.tool == "cline"


def test_cline_output_base_dir_is_dot_clinerules(build_result):
    """Top-level Cline output must live under ``.clinerules/``."""
    _, out_dir = build_result
    base = out_dir / ".clinerules"
    assert base.is_dir()
    assert (base / "devola-flow.md").exists()
    assert (base / "references").is_dir()
