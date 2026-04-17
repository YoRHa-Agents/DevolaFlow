"""Tests for the Windsurf YAML-driven adapter (v6.0.4 A2)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.adapters.base import _find_project_root, load_workflow_skill
from devolaflow.adapters.data_driven import DataDrivenAdapter


@pytest.fixture
def windsurf_config() -> dict:
    root = _find_project_root()
    return yaml.safe_load((root / "adapter_configs" / "windsurf.yaml").read_text())


@pytest.fixture
def build_result(tmp_path: Path, windsurf_config: dict):
    source, agent_dir = load_workflow_skill()
    adapter = DataDrivenAdapter(windsurf_config)
    out_dir = tmp_path / "windsurf"
    return adapter.build(source, agent_dir, out_dir), out_dir


def test_windsurf_config_metadata(windsurf_config: dict):
    assert windsurf_config["name"] == "windsurf"
    assert windsurf_config["display_name"] == "Windsurf"
    assert windsurf_config["tier"] == "tier_1"
    assert windsurf_config["version_added"] == "6.0.4"


def test_windsurf_builds_windsurfrules(build_result):
    _, out_dir = build_result
    rules = out_dir / ".windsurfrules"
    assert rules.exists()
    assert rules.is_file()
    assert rules.read_text().strip()


def test_windsurf_strips_frontmatter(build_result):
    _, out_dir = build_result
    rules = out_dir / ".windsurfrules"
    text = rules.read_text()
    # v6.1.2: switched to ``keep_sections`` with ``include_frontmatter: false``.
    # Output must NOT start with ``---`` (frontmatter) — same invariant as
    # the previous ``strip_frontmatter`` behaviour.
    assert not text.startswith("---")
    # Frontmatter keys must not leak into the body.
    assert "token_estimate:" not in text
    assert "last_updated:" not in text


def test_windsurf_budget_chars_under_8000(build_result):
    result, _ = build_result
    # Budget check must run correctly and report a ``chars`` measurement.
    assert "chars" in result.budget_details
    # Format: "<target>: <actual>/<max> chars"
    actual = int(result.budget_details.split(":")[1].strip().split("/")[0])
    max_val = int(result.budget_details.split("/")[1].strip().split()[0])
    assert max_val == 8000
    # v6.1.2: the ``keep_sections`` compression step brings Windsurf output
    # under the 8000-char budget, so the adapter now reports budget_ok=True.
    assert actual <= 8000, f"Windsurf output {actual} chars exceeds 8000 budget"
    assert result.budget_ok is True


def test_windsurf_result_tool_name(build_result):
    result, _ = build_result
    assert result.tool == "windsurf"


def test_windsurf_output_is_single_file(build_result):
    _, out_dir = build_result
    produced = [p for p in out_dir.rglob("*") if p.is_file()]
    assert len(produced) == 1
    assert produced[0].name == ".windsurfrules"


def test_windsurf_under_8000_chars(build_result):
    """The real ``.windsurfrules`` built from the real SKILL.md MUST be ≤ 8000 chars.

    This is the contract that v6.1.2 introduces — replaces the known-broken
    [WARN] status from v6.0.4–v6.1.1 (24,625 chars).
    """
    _, out_dir = build_result
    rules = out_dir / ".windsurfrules"
    text = rules.read_text()
    assert len(text) <= 8000, (
        f".windsurfrules is {len(text)} chars, exceeds Windsurf 8000-char budget"
    )


def test_windsurf_contains_quick_action(build_result):
    """High-value section ``Quick Action Decision`` must survive compression."""
    _, out_dir = build_result
    text = (out_dir / ".windsurfrules").read_text()
    assert "Quick Action Decision" in text


def test_windsurf_contains_hierarchy(build_result):
    """High-value section ``4-Layer Agent Hierarchy`` must survive compression."""
    _, out_dir = build_result
    text = (out_dir / ".windsurfrules").read_text()
    assert "4-Layer Agent Hierarchy" in text


def test_windsurf_has_header_prefix(build_result, windsurf_config: dict):
    """Output must start with the configured ``header_prefix`` string."""
    _, out_dir = build_result
    text = (out_dir / ".windsurfrules").read_text()
    spec = windsurf_config["output"]["files"][0]
    prefix = spec["header_prefix"].rstrip("\n")
    assert text.startswith(prefix), (
        f"Expected output to start with:\n{prefix!r}\nGot:\n{text[: len(prefix) + 20]!r}"
    )
    assert "github.com/YoRHa-Agents/DevolaFlow" in text.splitlines()[1]
