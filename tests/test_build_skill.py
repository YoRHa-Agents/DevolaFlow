"""Tests for build-skill adapter pipeline.

Design ref: design_delivery_architecture.md section 4.3-4.5
"""

from pathlib import Path

import pytest

from devolaflow.build_skill import _find_project_root, build_all


@pytest.fixture
def project_root():
    return _find_project_root()


def test_build_all_creates_outputs(
    project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(project_root)
    results = build_all(["--all"])
    assert len(results) == 4
    tools = {r.tool for r in results}
    assert tools == {"cursor", "codex", "claude", "copilot"}


def test_cursor_output_under_budget(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(project_root)
    results = build_all(["--all"])
    cursor = next(r for r in results if r.tool == "cursor")
    assert cursor.budget_ok, f"Cursor over budget: {cursor.budget_details}"


def test_claude_output_under_budget(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(project_root)
    results = build_all(["--all"])
    claude = next(r for r in results if r.tool == "claude")
    assert claude.budget_ok, f"Claude over budget: {claude.budget_details}"


def test_copilot_output_under_budget(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(project_root)
    results = build_all(["--all"])
    copilot = next(r for r in results if r.tool == "copilot")
    assert copilot.budget_ok, f"Copilot over budget: {copilot.budget_details}"


def test_codex_has_openai_yaml(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(project_root)
    build_all(["--all"])
    codex_yaml = project_root / "dist" / "codex" / "agents" / "openai.yaml"
    assert codex_yaml.exists()
