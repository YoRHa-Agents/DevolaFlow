"""Load plugin specifications from YAML and build default registries."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from devolaflow.plugins.models import PluginSpec
from devolaflow.plugins.registry import PluginRegistry

log = logging.getLogger(__name__)

_REPO_PLUGINS_YAML = "workflow-system/agent/plugins.yaml"

_BUILTIN_SPECS: list[dict[str, Any]] = [
    {
        "name": "nines",
        "description": "Multi-vertex evaluation and research system",
        "cli_binary": "nines",
        "version_command": "nines --version",
        "version_regex": r"version\s+(\d+\.\d+\.\d+\S*)",
        "install_methods": {
            "script": (
                "curl -fsSL"
                " https://raw.githubusercontent.com/YoRHa-Agents/NineS"
                "/main/scripts/install.sh | bash"
            ),
            "pip": "pip install nines-cli",
        },
        "capabilities": ["eval", "collect", "analyze", "self-eval", "iterate", "install"],
        "role": "research",
        "repo_url": "https://github.com/YoRHa-Agents/NineS",
        "skill_install_command": "nines install --target cursor",
    },
    {
        "name": "ui-ux-pro-max",
        "description": (
            "AI-powered design intelligence for professional UI/UX across 15 frameworks"
        ),
        "cli_binary": "uipro",
        "version_command": "uipro versions",
        "version_regex": r"v?(\d+\.\d+\.\d+)",
        "install_methods": {
            "npm": "npm install -g uipro-cli",
        },
        "capabilities": [
            "design_system_generation",
            "ui_style_recommendation",
            "color_palette_selection",
            "typography_pairing",
            "landing_page_patterns",
            "chart_recommendations",
            "ux_guidelines",
            "multi_stack_support",
        ],
        "role": "ui_tooling",
        "repo_url": "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill",
        "min_version": "2.0.0",
        "skill_install_command": "uipro init --ai cursor",
    },
]


def _dict_to_spec(data: dict[str, Any]) -> PluginSpec:
    """Build a ``PluginSpec`` from a normalized plugin definition mapping."""
    return PluginSpec(
        name=data["name"],
        description=data["description"],
        cli_binary=data["cli_binary"],
        version_command=data["version_command"],
        version_regex=data["version_regex"],
        install_methods=data.get("install_methods", {}),
        capabilities=data.get("capabilities", []),
        role=data.get("role", ""),
        repo_url=data.get("repo_url", ""),
        min_version=data.get("min_version"),
        skill_install_command=data.get("skill_install_command"),
    )


def load_plugin_specs(yaml_path: str | Path) -> list[PluginSpec]:
    """Load plugin specs from a YAML file."""
    import yaml  # deferred so the module works without PyYAML at import time

    path = Path(yaml_path)
    if not path.exists():
        log.warning("Plugin spec file not found: %s", path)
        return []

    raw = yaml.safe_load(path.read_text()) or {}
    plugins_section = raw.get("plugins", {})

    if isinstance(plugins_section, list):
        return [_dict_to_spec(e) for e in plugins_section]

    specs: list[PluginSpec] = []
    for name, entry in plugins_section.items():
        entry_with_name = {"name": name, **entry}
        specs.append(_dict_to_spec(entry_with_name))
    return specs


def create_default_registry(plugins_yaml: str | Path | None = None) -> PluginRegistry:
    """Create a registry pre-loaded with built-in plugin definitions.

    If *plugins_yaml* is ``None``, the function looks for
    ``workflow-system/agent/plugins.yaml`` relative to the repo root.
    When that file is absent it falls back to hard-coded defaults
    (NineS, ui-ux-pro-max).
    """
    registry = PluginRegistry()

    for entry in _BUILTIN_SPECS:
        registry.register(_dict_to_spec(entry))

    yaml_path: Path | None = None
    if plugins_yaml is not None:
        yaml_path = Path(plugins_yaml)
    else:
        candidate = Path(_REPO_PLUGINS_YAML)
        if candidate.exists():
            yaml_path = candidate

    if yaml_path is not None:
        for spec in load_plugin_specs(yaml_path):
            registry.register(spec)

    return registry
