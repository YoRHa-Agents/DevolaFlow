"""Ghost audit for the v12.5.0 Codegraph integration surfaces.

The historical v12.5 cycle also contained unrelated optimizer and command
mapping audits. Those retired integrations are intentionally not recreated
here; this file preserves the Codegraph W-18 evidence that remains live.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def test_v12_5_0_codegraph_plugin_registered(project_root: Path) -> None:
    """W-18 PV-03: Codegraph remains registered across live surfaces."""
    plugins_path = project_root / "workflow-system/agent/plugins.yaml"
    plugins = yaml.safe_load(plugins_path.read_text(encoding="utf-8"))["plugins"]
    codegraph = plugins["codegraph"]
    assert codegraph["role"] == "code_intelligence"
    assert codegraph["min_version"] == "0.9.3"
    assert codegraph["repo_url"] == "https://github.com/colbymchenry/codegraph"

    runtime_path = project_root / "workflow-system/agent/knowledge/runtime-plugins.yaml"
    runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    entry = next(item for item in runtime["plugins"] if item["id"] == "codegraph")
    assert entry["tier"] == "suggest"
    assert entry["default_install"] is True

    references_path = project_root / "workflow-system/agent/knowledge/reference-dependencies.yaml"
    references = yaml.safe_load(references_path.read_text(encoding="utf-8"))
    assert any(item["id"] == "codegraph" for item in references["active_tracking"])

    package_dir = project_root / "src/devolaflow/codegraph"
    assert all(
        (package_dir / name).is_file() for name in ("__init__.py", "_cli.py", "researcher.py")
    )
    tests_dir = project_root / "tests"
    assert (tests_dir / "test_codegraph.py").is_file()
    assert (tests_dir / "test_codegraph_workflow_wiring.py").is_file()


def test_v12_5_0_codegraph_workflow_wired(project_root: Path) -> None:
    """W-18 PV-04: all four seeds retain Codegraph-aware assertions."""
    seed_paths = (
        "repo-init.yaml",
        "onboarding.yaml",
        "security-audit.yaml",
        "product-verification.yaml",
    )
    for filename in seed_paths:
        text = (project_root / "workflow-system/agent/templates/seeds" / filename).read_text(
            encoding="utf-8"
        )
        assert "codegraph" in text.lower()

    profiles = yaml.safe_load(
        (project_root / "workflow-system/agent/context_profiles.yaml").read_text(encoding="utf-8")
    )
    integration = profiles["meta"]["codegraph_integration"]
    assert integration["auto_detect"] is True
    assert set(integration["commands"]) == {
        "repo_init",
        "analyze",
        "research",
        "impact",
        "affected",
    }


def test_v12_5_0_codegraph_docs_landed(project_root: Path) -> None:
    """W-18 PV-05: Codegraph reference, fallback, and manifest surfaces exist."""
    reference = (project_root / "workflow-system/agent/references/codegraph.md").read_text(
        encoding="utf-8"
    )
    for anchor in (
        "## §1 — What codegraph is",
        "## §2 — The 9 MCP tools",
        "## §3 — CLI surface",
        "## §4 — DevolaFlow integration map",
        "## §5 — Degraded-mode contract",
        "## §6 — Cache management",
    ):
        assert anchor in reference

    degraded = (project_root / "workflow-system/agent/references/degraded-mode.md").read_text(
        encoding="utf-8"
    )
    assert "| codegraph |" in degraded
    assert "### Section 5 — codegraph" in degraded

    manifest = (project_root / "workflow-system/agent/manifest.yaml").read_text(encoding="utf-8")
    skill = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert "references/codegraph.md" in manifest
    assert "references/codegraph.md" in skill
