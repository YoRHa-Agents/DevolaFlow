"""RTK shell-proxy package — closes R-002 from v8.4.0 SI-1 gap analysis (PV-02).

Public surface:

* :class:`ShellProxy` — main wrapper class
* :class:`ShellProxyConfig` — frozen activation snapshot
* :func:`proxy_command` — module-level convenience wrapper
* :func:`is_proxy_enabled` — pure env-flag read (R5 strict hot path)
* :data:`WHITELIST` — Tier 1 + Tier 2 single-source-of-truth registry

Activation (default OFF — R5 strict):

* Set ``DEVOLAFLOW_RTK_PROXY=1`` to enable Tier 1 commands
  (``pytest``, ``ruff check``, ``git diff``, ``git log``, ``git status``).
* Additionally set ``DEVOLAFLOW_RTK_PROXY_TIER2=1`` to enable Tier 2
  commands (``git add``, ``git commit``, ``git show``, ``cargo test``,
  ``npm test``, ``make``).
* The ``rtk`` binary must be on PATH AND ``rtk gain`` must succeed
  (distinguish probe per RTK ``INSTALL.md`` collision warning vs
  rtk-type-kit). On failure, the proxy logs a WARNING per S-5 and
  passthroughs gracefully — no exception is raised.

Companion lifecycle hook: :mod:`devolaflow.lifecycle.pre_shell_call`.

Forward-declared workflow id ``shell-proxy`` was registered in PV-01
(v8.3.1) under ``runtime-plugins.yaml::plugins[rtk].invoked_by_workflows``;
this PV is the activation surface (env-flag), not a workflow template
(see ``.local/research/v8.4.0_gap_analysis.md`` §4.2 design constraint).

External canonical URL (per S-7): https://github.com/rtk-ai/rtk
"""

from __future__ import annotations

from devolaflow.shell_proxy.proxy import (
    ShellProxy,
    ShellProxyConfig,
    is_proxy_enabled,
    proxy_command,
)
from devolaflow.shell_proxy.registry import WHITELIST

__all__ = [
    "WHITELIST",
    "ShellProxy",
    "ShellProxyConfig",
    "is_proxy_enabled",
    "proxy_command",
]
