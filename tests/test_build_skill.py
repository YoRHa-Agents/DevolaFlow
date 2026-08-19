"""Tests for build-skill adapter pipeline.

Design ref: design_delivery_architecture.md section 4.3-4.5
"""

from pathlib import Path

import pytest

from devolaflow.build_skill import _find_project_root, build_all

CORE_ADAPTERS = {"cursor", "codex", "claude", "copilot"}


@pytest.fixture
def project_root():
    return _find_project_root()


def test_build_all_creates_outputs(
    project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    # build_all's load_workflow_skill() discovers the agent dir from the package
    # location, so the chdir above only redirects the dist/ output under tmp_path.
    results = build_all(["--all"])
    tools = {r.tool for r in results}
    # The 4 core adapters must always be present. YAML-driven adapters may add more.
    assert CORE_ADAPTERS.issubset(tools), f"missing core adapters: {CORE_ADAPTERS - tools}"
    assert len(results) >= 4


def test_cursor_output_under_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    results = build_all(["--tools", "cursor"])
    cursor = next(r for r in results if r.tool == "cursor")
    assert cursor.budget_ok, f"Cursor over budget: {cursor.budget_details}"


def test_claude_output_under_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    results = build_all(["--tools", "claude"])
    claude = next(r for r in results if r.tool == "claude")
    assert claude.budget_ok, f"Claude over budget: {claude.budget_details}"


def test_copilot_output_under_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    results = build_all(["--tools", "copilot"])
    copilot = next(r for r in results if r.tool == "copilot")
    assert copilot.budget_ok, f"Copilot over budget: {copilot.budget_details}"


def test_codex_has_openai_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    build_all(["--tools", "codex"])
    codex_yaml = tmp_path / "dist" / "codex" / "agents" / "openai.yaml"
    assert codex_yaml.exists()


def test_codex_output_under_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Codex budget parity with the cursor/claude/copilot siblings (G7)."""
    monkeypatch.chdir(tmp_path)
    results = build_all(["--tools", "codex"])
    codex = next(r for r in results if r.tool == "codex")
    assert codex.budget_ok, f"Codex over budget: {codex.budget_details}"
