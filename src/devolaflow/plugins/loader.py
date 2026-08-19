"""Load plugin specifications from YAML and build default registries.

Registry-read contract (v15.0.0 G-021): ``workflow-system/agent/plugins.yaml``
— the file this loader reads — is the DERIVED capability/role/stage_mapping
view of the single A-5 SSOT owner,
``workflow-system/agent/knowledge/runtime-plugins.yaml`` (read by
:func:`devolaflow.plugins.installer.load_registry`). Plugin membership and
IDs are registered in the owner first; the view mirrors them 1:1 (pinned by
``tests/test_plugins.py::TestV15PluginRegistryUnification``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from devolaflow.plugins.models import PluginSpec
from devolaflow.plugins.registry import PluginRegistry

log = logging.getLogger(__name__)

_REPO_PLUGINS_YAML = "workflow-system/agent/plugins.yaml"

# v15.2.0 B-6 (04 §8.3) — session-scoped one-time-suggestion cache. The
# probe/suggestion surface is centralised HERE (single owner per A-5): a
# suggest-tier plugin that is missing yields exactly ONE hint per plugin per
# Python session, then goes quiet ("一次性建议提示，同会话不重复骚扰").
# Module-level set = zero IO; process lifetime = session lifetime.
_SESSION_SUGGESTED: set[str] = set()


def suggest_plugin_once(plugin_id: str) -> str | None:
    """Return the install hint for ``plugin_id`` once per session, else ``None``.

    First call for a given ``plugin_id`` returns the operator-facing hint
    text (the caller decides the channel — log line, hook-violation message,
    stdout); every subsequent call in the same Python session returns
    ``None`` so degraded paths do not repeat the nag. Zero IO — no registry
    read, no subprocess, no ``shutil.which``.
    """
    if plugin_id in _SESSION_SUGGESTED:
        return None
    _SESSION_SUGGESTED.add(plugin_id)
    return (
        f"plugin {plugin_id!r} is not installed — continuing on the degraded "
        f"path. Install it manually (see its install_cmd in "
        f"workflow-system/agent/knowledge/runtime-plugins.yaml) or opt in to "
        f"auto-install with DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1."
    )


# Emergency-only fallback used when ``plugins.yaml`` cannot be located.
# The derived capability view lives at ``workflow-system/agent/plugins.yaml``
# (registration SSOT: ``knowledge/runtime-plugins.yaml`` per A-5 / G-021);
# this stub exists solely so NineS detection remains functional in degraded
# installs that are missing the YAML file. Keep it intentionally minimal.
_EMERGENCY_NINES_STUB: dict[str, Any] = {
    "name": "nines",
    "description": "Multi-vertex evaluation and research system (emergency stub)",
    "cli_binary": "nines",
    "version_command": "nines --version",
    "version_regex": r"version\s+(\d+\.\d+\.\d+\S*)",
    "install_methods": {
        "pip": "uv pip install git+https://github.com/YoRHa-Agents/NineS.git",
    },
    "role": "research_and_iteration",
    "repo_url": "https://github.com/YoRHa-Agents/NineS",
    "min_version": "1.0.0",
}


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
        stage_mapping=data.get("stage_mapping", {}),
        workflows=data.get("workflows", []),
        update_command=data.get("update_command"),
        uninstall_command=data.get("uninstall_command"),
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


def _find_repo_plugins_yaml() -> Path | None:
    """Locate ``workflow-system/agent/plugins.yaml`` near the installed package.

    Looks at the package's repo-root ancestor, the current working directory,
    and each ancestor of the package directory so the YAML resolves whether
    DevolaFlow is used from a source checkout or an installed wheel.
    """
    pkg_dir = Path(__file__).resolve().parent
    candidates = [
        pkg_dir.parent.parent / _REPO_PLUGINS_YAML,
        Path.cwd() / _REPO_PLUGINS_YAML,
    ]
    for parent in pkg_dir.parents:
        candidates.append(parent / _REPO_PLUGINS_YAML)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def create_default_registry(plugins_yaml: str | Path | None = None) -> PluginRegistry:
    """Create a registry populated from the derived capability view ``plugins.yaml``.

    When *plugins_yaml* is ``None`` (the common case), the function looks for
    ``workflow-system/agent/plugins.yaml`` relative to the installed package
    and the current working directory. That file is the DERIVED view of the
    A-5 SSOT owner ``knowledge/runtime-plugins.yaml`` (G-021) — membership
    and IDs mirror the owner. If the YAML is absent, the registry is
    populated with a minimal NineS emergency stub and a warning is logged —
    this keeps NineS detection functional in degraded installs but makes the
    missing YAML visible in logs.
    """
    registry = PluginRegistry()

    yaml_path: Path | None = None
    if plugins_yaml is not None:
        candidate = Path(plugins_yaml)
        if candidate.exists():
            yaml_path = candidate
    else:
        yaml_path = _find_repo_plugins_yaml()

    if yaml_path is not None:
        for spec in load_plugin_specs(yaml_path):
            registry.register(spec)
    else:
        log.warning(
            "plugins.yaml not found; falling back to emergency NineS stub. "
            "Ship workflow-system/agent/plugins.yaml alongside the package "
            "to restore the full plugin catalog."
        )
        registry.register(_dict_to_spec(_EMERGENCY_NINES_STUB))

    return registry
