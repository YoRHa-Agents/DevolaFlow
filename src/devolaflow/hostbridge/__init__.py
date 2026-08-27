"""Host-bridge core — routes host-agent tool events into lifecycle hooks.

v17.0.0 R2 (G17-B1 closure per ``.local/research/v17.0.0_r2_design.md``
§D-R2-1..§D-R2-4). Five hosts (Cursor, Claude Code, Codex, KimiCode,
DSH) deliver pre-tool-use events (file writes, shell commands) to
``python -m devolaflow.hostbridge --host <host>`` via per-host hook
configs; the bridge normalizes each event, evaluates it against the
S-8 owned-files contract through ``lifecycle.run_hooks``, and answers
in the host's own block protocol.

Contracts:

* **R5 strict** — everything is a zero-filesystem-IO allow unless
  ``DEVOLAFLOW_HOST_ENFORCE`` is EXACTLY ``"1"`` (a NEW flag, W-20
  §3-justified in ``references/env-flags.md`` §2.18: host tool-event
  interception is a different runtime surface than the
  ``DEVOLAFLOW_AGENT_WORKSPACE`` scaffolding + framework adapters).
* **Fail-open** — internal errors always allow (verdict
  ``error_allow``) and are recorded in the audit ledger (S-5).
* **Audit** — enforced decisions append JSONL lines to
  ``.local/telemetry/hostbridge.jsonl``.

Operator docs: ``workflow-system/agent/references/host-bridges.md``.
"""

from __future__ import annotations

from devolaflow.hostbridge.audit import (
    AUDIT_LEDGER_RELPATH,
    append_audit,
    build_audit_record,
)
from devolaflow.hostbridge.decision import (
    ENV_FLAG,
    ENV_FLAG_TRUTHY,
    VERDICT_ALLOW,
    VERDICT_DENY,
    VERDICT_ERROR_ALLOW,
    BridgeDecision,
    decide,
    is_host_enforce_active,
)
from devolaflow.hostbridge.install import (
    INSTALL_HOSTS,
    install_claude,
    install_codex,
    install_copilot,
    install_cursor,
    kimi_snippet,
)
from devolaflow.hostbridge.normalize import (
    KIND_FILE_WRITE,
    KIND_SHELL,
    KIND_UNKNOWN,
    KNOWN_HOSTS,
    BridgeEvent,
    normalize_event,
)

__all__ = [
    "AUDIT_LEDGER_RELPATH",
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "INSTALL_HOSTS",
    "KIND_FILE_WRITE",
    "KIND_SHELL",
    "KIND_UNKNOWN",
    "KNOWN_HOSTS",
    "VERDICT_ALLOW",
    "VERDICT_DENY",
    "VERDICT_ERROR_ALLOW",
    "BridgeDecision",
    "BridgeEvent",
    "append_audit",
    "build_audit_record",
    "decide",
    "install_claude",
    "install_codex",
    "install_copilot",
    "install_cursor",
    "is_host_enforce_active",
    "kimi_snippet",
    "normalize_event",
]
