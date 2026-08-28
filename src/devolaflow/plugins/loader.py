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
import shlex
from pathlib import Path
from typing import Any

from devolaflow.plugins.models import PluginSpec
from devolaflow.plugins.registry import PluginRegistry

log = logging.getLogger(__name__)

_REPO_PLUGINS_YAML = "workflow-system/agent/plugins.yaml"
_RUNTIME_PLUGINS_YAML = "workflow-system/agent/knowledge/runtime-plugins.yaml"

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


def _runtime_registry_for_view(view_path: Path) -> Path | None:
    """Find the runtime SSOT paired with a legacy capability view."""
    candidates = [view_path.parent / "knowledge" / "runtime-plugins.yaml"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _runtime_entries(path: Path) -> dict[str, dict[str, Any]]:
    """Load runtime registration rows without making the view an owner."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("plugins", [])
    return {
        entry["id"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]
    }


def _overlay_runtime_registration(
    view_data: dict[str, Any],
    *,
    runtime_path: Path | None,
) -> dict[str, Any]:
    """Overlay operational fields from runtime SSOT onto view metadata.

    The legacy view remains useful to callers that need capabilities, roles,
    and stage recipes.  Detection, version floors, workflow wiring, and
    installer commands are always taken from ``runtime-plugins.yaml`` when
    the paired SSOT is available, so stale view values cannot affect runtime
    behavior.
    """
    if runtime_path is None:
        return view_data

    runtime = _runtime_entries(runtime_path)
    normalized: dict[str, Any] = {}
    for plugin_id, presentation in view_data.get("plugins", {}).items():
        if not isinstance(presentation, dict):
            continue
        entry = runtime.get(plugin_id)
        if entry is None:
            log.warning("Plugin %s exists only in the presentation view", plugin_id)
            continue
        data = {"name": plugin_id, **presentation}
        version_command = str(entry["version_check_cmd"])
        command_words = shlex.split(version_command)
        data["cli_binary"] = command_words[0] if command_words else data.get("cli_binary", "")
        data["version_command"] = version_command
        data["repo_url"] = entry.get("canonical_url", "")
        data["min_version"] = entry["min_version"]
        data["workflows"] = list(entry.get("invoked_by_workflows") or [])
        data["update_command"] = entry.get("upgrade_cmd")

        backend = entry.get("backend")
        install_key = {"pip": "pip", "npm_then_init": "npm", "curl_install_script": "script"}.get(
            backend
        )
        if install_key:
            methods = dict(data.get("install_methods") or {})
            methods[install_key] = entry["install_cmd"]
            data["install_methods"] = methods

        init_template = entry.get("init_cmd_template")
        if init_template and not data.get("skill_install_command"):
            targets = entry.get("init_targets") or []
            target = targets[0] if targets else "auto"
            data["skill_install_command"] = init_template.format(ai_platform=target)
        normalized[plugin_id] = data

    merged = dict(view_data)
    merged["plugins"] = normalized
    return merged


def load_plugin_specs(yaml_path: str | Path) -> list[PluginSpec]:
    """Load plugin specs from a YAML file."""
    import yaml  # deferred so the module works without PyYAML at import time

    path = Path(yaml_path)
    if not path.exists():
        log.warning("Plugin spec file not found: %s", path)
        return []

    raw = yaml.safe_load(path.read_text()) or {}
    if path.name == "plugins.yaml":
        raw = _overlay_runtime_registration(
            raw,
            runtime_path=_runtime_registry_for_view(path),
        )
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


def create_default_registry(
    plugins_yaml: str | Path | None = None,
    *,
    profile: str | None = None,
) -> PluginRegistry:
    """Create a registry populated from the derived capability view ``plugins.yaml``.

    When *plugins_yaml* is ``None`` (the common case), the function looks for
    ``workflow-system/agent/plugins.yaml`` relative to the installed package
    and the current working directory. That file is the DERIVED view of the
    A-5 SSOT owner ``knowledge/runtime-plugins.yaml`` (G-021) — membership
    and IDs mirror the owner. If the YAML is absent, a warning is logged and
    an empty registry is returned; missing metadata must never invent a
    partially registered plugin.

    When *profile* is supplied, only the explicitly selected runtime plugin
    profile is registered (``all``/``global`` or a singleton plugin ID).
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
        specs_data: list[dict[str, Any]]
        runtime_path: Path | None = None
        if yaml_path.name == "plugins.yaml":
            import yaml

            view = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            runtime_path = _runtime_registry_for_view(yaml_path)
            view = _overlay_runtime_registration(view, runtime_path=runtime_path)
            specs_data = [
                {"name": name, **entry}
                for name, entry in (view.get("plugins") or {}).items()
                if isinstance(entry, dict)
            ]
        else:
            specs_data = [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "cli_binary": spec.cli_binary,
                    "version_command": spec.version_command,
                    "version_regex": spec.version_regex,
                    "install_methods": spec.install_methods,
                    "capabilities": spec.capabilities,
                    "role": spec.role,
                    "repo_url": spec.repo_url,
                    "min_version": spec.min_version,
                    "skill_install_command": spec.skill_install_command,
                    "stage_mapping": spec.stage_mapping,
                    "workflows": spec.workflows,
                    "update_command": spec.update_command,
                    "uninstall_command": spec.uninstall_command,
                }
                for spec in load_plugin_specs(yaml_path)
            ]
        selected = None
        if profile is not None:
            from devolaflow.plugins.installer import select_plugin_profile

            selected = set(
                select_plugin_profile(profile, registry_path=runtime_path)
                if runtime_path is not None
                else [data["name"] for data in specs_data]
            )
        for data in specs_data:
            if selected is None or data["name"] in selected:
                registry.register(_dict_to_spec(data))
    else:
        log.warning(
            "plugins.yaml not found; returning an empty plugin registry. "
            "Ship workflow-system/agent/plugins.yaml alongside the package "
            "to restore the full plugin catalog."
        )

    return registry
