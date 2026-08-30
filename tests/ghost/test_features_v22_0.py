"""Current-cycle ghost audit for the v22 external-tool retirement."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_v22_retired_rtk_sichip_and_lifecycle_surfaces_are_absent(
    project_root: Path,
) -> None:
    """RTK, Si-Chip, shell-proxy, and retired lifecycle hooks stay removed."""
    retired_packages = (
        "src/devolaflow/si_chip_bridge",
        "src/devolaflow/shell_proxy",
    )
    retired_files = (
        "src/devolaflow/lifecycle/pre_shell_call.py",
        "src/devolaflow/lifecycle/post_skill_edit.py",
    )
    assert all(not any((project_root / path).rglob("*.py")) for path in retired_packages)
    assert all(not (project_root / path).is_file() for path in retired_files)

    runtime = yaml.safe_load(
        (project_root / "workflow-system/agent/knowledge/runtime-plugins.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert {entry["id"] for entry in runtime["plugins"]} == {
        "ui-pro",
        "codegraph",
        "impeccable",
    }

    from devolaflow.lifecycle import DEFAULT_EVENTS

    assert "pre_shell_call" not in DEFAULT_EVENTS
    assert "post_skill_edit" not in DEFAULT_EVENTS


def test_v22_codegraph_remains_suggest_default_installed_with_fallback(
    project_root: Path,
) -> None:
    """Codegraph remains default-installed, auto-used when available, and degradable."""
    runtime = yaml.safe_load(
        (project_root / "workflow-system/agent/knowledge/runtime-plugins.yaml").read_text(
            encoding="utf-8"
        )
    )
    codegraph = next(entry for entry in runtime["plugins"] if entry["id"] == "codegraph")
    assert codegraph["tier"] == "suggest"
    assert codegraph["default_install"] is True
    assert "product-verification" in codegraph["invoked_by_workflows"]
    from devolaflow.plugins.installer import available_plugin_profiles

    assert "codegraph" in available_plugin_profiles(registry_path=None)["all"]
    assert runtime["defaults"]["auto_install"] is False
    assert runtime["defaults"]["prefer_local_fallback"] is True

    profile = yaml.safe_load(
        (project_root / "workflow-system/agent/context_profiles.yaml").read_text(encoding="utf-8")
    )
    assert profile["meta"]["codegraph_integration"]["auto_detect"] is True

    reference = (project_root / "workflow-system/agent/references/codegraph.md").read_text(
        encoding="utf-8"
    )
    assert "fallback" in reference.lower()
    assert "SUGGEST-tier" in reference
