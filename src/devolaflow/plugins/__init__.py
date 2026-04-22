"""DevolaFlow plugin system — detection, registry, and v8.2.1 auto-install.

Two public surfaces live here:

1. **Legacy PluginRegistry** (pre-v8.2.1) — :class:`PluginRegistry` loads
   ``workflow-system/agent/plugins.yaml`` and supports CLI detection / ensure /
   upgrade via :class:`PluginSpec` / :class:`PluginStatus`. Kept untouched for
   backward compatibility; see :mod:`devolaflow.plugins.registry`.

2. **Runtime auto-install** (v8.2.1, design.md §6) — :func:`ensure_plugin`
   consumes ``workflow-system/agent/knowledge/runtime-plugins.yaml`` and
   supports two backends: ``pip`` (for ``nines``) and ``npm_then_init`` (for
   ``ui-pro``). Every failure raises loudly per S-5 (no silent failures).
"""

from devolaflow.plugins.exceptions import (
    PluginBackendUnsupported,
    PluginInstallError,
    PluginNotFoundError,
    PluginRuntimeError,
    PluginVersionMismatch,
)
from devolaflow.plugins.installer import (
    RuntimePluginSpec,
    ensure_plugin,
    load_registry,
    resolve_plugin,
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
    "RuntimePluginSpec",
    "create_default_registry",
    "ensure_plugin",
    "load_plugin_specs",
    "load_registry",
    "resolve_plugin",
]
