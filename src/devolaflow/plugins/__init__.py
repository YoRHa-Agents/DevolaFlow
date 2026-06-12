"""DevolaFlow plugin system — detection, registry, and v8.2.1 auto-install.

Two public surfaces live here (single registration owner per A-5 / G-021):

1. **Runtime auto-install** (v8.2.1, design.md §6) — :func:`ensure_plugin`
   consumes ``workflow-system/agent/knowledge/runtime-plugins.yaml``, the
   A-5 SSOT owner of plugin registration data (v15.0.0 G-021). Every
   failure raises loudly per S-5 (no silent failures).

2. **PluginRegistry capability view** (pre-v8.2.1 callers) —
   :class:`PluginRegistry` loads ``workflow-system/agent/plugins.yaml``,
   the DERIVED capability/role/stage_mapping view of the owner, and
   supports CLI detection / ensure / upgrade via :class:`PluginSpec` /
   :class:`PluginStatus`. See :mod:`devolaflow.plugins.registry`.
"""

from devolaflow.plugins.exceptions import (
    PluginBackendUnsupported,
    PluginInstallError,
    PluginNotFoundError,
    PluginRuntimeError,
    PluginVersionMismatch,
)
from devolaflow.plugins.installer import (
    RefreshOutcome,
    RuntimePluginSpec,
    ensure_plugin,
    is_plugin_stale,
    list_plugins,
    load_registry,
    plugins_for_workflow,
    read_last_checked,
    refresh_all,
    resolve_plugin,
    upgrade_plugin,
)
from devolaflow.plugins.loader import create_default_registry, load_plugin_specs
from devolaflow.plugins.models import PluginSpec, PluginStatus
from devolaflow.plugins.registry import PluginRegistry

__all__ = [
    "PluginBackendUnsupported",
    "PluginInstallError",
    "PluginNotFoundError",
    "PluginRegistry",
    "PluginRuntimeError",
    "PluginSpec",
    "PluginStatus",
    "PluginVersionMismatch",
    "RefreshOutcome",
    "RuntimePluginSpec",
    "create_default_registry",
    "ensure_plugin",
    "is_plugin_stale",
    "list_plugins",
    "load_plugin_specs",
    "load_registry",
    "plugins_for_workflow",
    "read_last_checked",
    "refresh_all",
    "resolve_plugin",
    "upgrade_plugin",
]
