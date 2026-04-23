"""RTK shell-proxy package — R-002 (PV-02) + M-002 (PV-04) closures.

PV-02 (v8.3.2) introduced the shell-proxy + registry + lifecycle hook;
PV-04 (v8.3.4) layered RTK-pattern command-output mappings on top of
the proxy via :mod:`devolaflow.shell_proxy.commands`.

Public surface:

* :class:`ShellProxy` — main wrapper class (PV-02)
* :class:`ShellProxyConfig` — frozen activation snapshot (PV-02)
* :func:`proxy_command` — module-level convenience wrapper (PV-02)
* :func:`is_proxy_enabled` — pure env-flag read (R5 strict hot path)
* :data:`WHITELIST` — Tier 1 + Tier 2 single-source-of-truth registry
* :class:`CommandMapping` — frozen recipe dataclass (PV-04)
* :class:`CommandMappingError` — recipe schema-break exception (PV-04)
* :class:`FilterRule` — frozen pre/post-filter rule (PV-04)
* :func:`load_command_mappings` — discover + parse local recipes (PV-04)
* :func:`apply_local_recipe` — apply matching recipe to ``(cmd, output)`` (PV-04)
* :func:`is_command_mapping_active` — pure env-flag read (mirror of
  :func:`is_proxy_enabled`; reuses the same env-flag — NO new flag)

Activation (default OFF — R5 strict):

* Set ``DEVOLAFLOW_RTK_PROXY=1`` to enable Tier 1 commands AND the
  PV-04 local-recipe layer (BOTH PV-02 + PV-04 share this single flag —
  per the v8.3.4 task spec, no NEW env-flag was introduced).
* Additionally set ``DEVOLAFLOW_RTK_PROXY_TIER2=1`` to enable Tier 2
  commands (``git add``, ``git commit``, ``git show``, ``cargo test``,
  ``npm test``, ``make``).
* The ``rtk`` binary must be on PATH AND ``rtk gain`` must succeed
  (distinguish probe per RTK ``INSTALL.md`` collision warning vs
  rtk-type-kit). On failure, the proxy logs a WARNING per S-5 and
  passthroughs gracefully — no exception is raised.

Precedence chain (per gap analysis §2.1 M-002 verbatim):

1. local recipe (:func:`apply_local_recipe`) wins
2. falls back to RTK's ``rtk rewrite`` (PV-02 wrap_command default)
3. falls back to passthrough (no rewrite — original command stands)

Companion lifecycle hook: :mod:`devolaflow.lifecycle.pre_shell_call`.

Forward-declared workflow id ``shell-proxy`` was registered in PV-01
(v8.3.1) under ``runtime-plugins.yaml::plugins[rtk].invoked_by_workflows``;
this package is the activation surface (env-flag), not a workflow template
(see ``.local/research/v8.4.0_gap_analysis.md`` §4.2 design constraint).

External canonical URL (per S-7): https://github.com/rtk-ai/rtk
"""

from __future__ import annotations

from devolaflow.shell_proxy.commands import (
    DEFAULT_COMMANDS_DIR,
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    MIN_TTL_DAYS,
    CommandMapping,
    CommandMappingError,
    FilterRule,
    apply_local_recipe,
    build_mapping_from_dict,
    is_command_mapping_active,
    load_command_mappings,
)
from devolaflow.shell_proxy.proxy import (
    ShellProxy,
    ShellProxyConfig,
    is_proxy_enabled,
    proxy_command,
)
from devolaflow.shell_proxy.registry import WHITELIST

__all__ = [
    "CommandMapping",
    "CommandMappingError",
    "DEFAULT_COMMANDS_DIR",
    "DEFAULT_TTL_DAYS",
    "FilterRule",
    "MAX_TTL_DAYS",
    "MIN_TTL_DAYS",
    "ShellProxy",
    "ShellProxyConfig",
    "WHITELIST",
    "apply_local_recipe",
    "build_mapping_from_dict",
    "is_command_mapping_active",
    "is_proxy_enabled",
    "load_command_mappings",
    "proxy_command",
]
