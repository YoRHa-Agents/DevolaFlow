"""Pre-plugin-invocation lifecycle hook — ``pre_plugin_invocation``.

Closes D-P-1 + D-P-3 from `.local/research/v9.4.0_gap_analysis.md` §3.1
(v9.4.0 PV-02; second MINOR of the v10.0.0 MAJOR rollup cycle).

Bound to the ``pre_plugin_invocation`` event by
:mod:`devolaflow.lifecycle.__init__`. Fires AFTER the v9.1.3 PV-03
``pre_handoff`` slot in :func:`devolaflow.feedback.ProposalGenerator._emit_dispatch`
(PV-03 wiring lands in the next commit). The contract: when the
dispatcher knows a stage needs a plugin (resolved via
``runtime-plugins.yaml#plugins[*].invoked_by_workflows``), this hook
auto-invokes :func:`devolaflow.plugins.installer.ensure_plugin` so the
plugin is installed before the L3 Task Agent attempts to call its
binary.

Behaviour contract (R5 strict):

1. **Gate 1 (env-flag OFF)** — if ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS`` is
   unset or anything other than the literal string ``"1"``, the handler
   returns an empty :class:`HookResult` with zero filesystem I/O AND
   zero subprocess work. This is the byte-identical no-op invariant:
   every dispatch path that does NOT opt-in MUST produce identical
   bytes to v9.3.0 behaviour.

   Per Workflow Rule W-20 (env-flag reuse-first analysed in
   :file:`.local/research/v9.4.0_gap_analysis.md` §3.1 D-P-3), this
   flag is a NEW flag (orthogonal to existing
   ``DEVOLAFLOW_AUTO_INSTALL`` / ``DEVOLAFLOW_AGENT_WORKSPACE``) — see
   :file:`workflow-system/agent/references/env-flags.md` §2.13 for the
   full orthogonality argument.

2. **Gate 2 (no plugin candidates)** — if the payload contains neither
   ``plugin_id`` (str) nor ``plugin_ids`` (list[str]), the handler
   returns an empty :class:`HookResult`. A dispatch without plugin
   candidates has nothing to install; silent no-op is the correct
   behaviour (NOT an error — most workflow stages legitimately do not
   require an external plugin).

3. **Action (both gates open)** — for each candidate ``plugin_id``,
   call :func:`ensure_plugin`. The function delegates the install logic
   wholesale per Soul Rule A-5.1 single-owner — this hook is a thin
   wiring layer, NOT a re-implementation of install machinery.

S-5 compliance (no silent failures): every failure mode is surfaced
through a typed :class:`HookViolation`:

* ``PPI001`` (severity ``error``) — ``ensure_plugin`` raised any of the
  domain exceptions (``PluginNotFoundError``, ``PluginInstallError``,
  ``PluginVersionMismatch``, ``PluginBackendUnsupported``). The
  exception text is captured verbatim in the violation context.
* ``PPI002`` (severity ``warning``) — payload schema malformed
  (``plugin_id`` not a string OR ``plugin_ids`` not a list of strings).
  Permissive default surfaces this as a WARNING; strict mode re-raises.

In permissive mode the handler NEVER crashes the dispatch — install
failures are aggregated into the result envelope and emitted via
WARNING-level logs by :func:`finalize`. The dispatcher (in v9.4.0
PV-03 wiring) receives the populated :class:`HookResult` and may
inspect ``result.violations`` to decide whether to abort the L3
dispatch or proceed in best-effort mode.

A genuinely unexpected exception (e.g. ``OSError`` on disk full,
``ImportError`` on a missing optional dep) is logged at WARNING via
the lifecycle logger AND re-raised — the handler never silently
swallows non-domain exceptions.

Lazy import of :mod:`devolaflow.plugins.installer` keeps this module
import-light: the lifecycle package import path does NOT pull in the
1030-LOC installer module unless the env-flag is ON AND the payload
carries plugin candidates. Codified in
``tests/test_pre_plugin_invocation.py::test_disabled_is_noop_byte_identical``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT: str = "pre_plugin_invocation"
ENV_FLAG: str = "DEVOLAFLOW_AUTO_INSTALL_PLUGINS"
ENV_FLAG_TRUTHY: str = "1"

logger = logging.getLogger(__name__)


def is_auto_install_active() -> bool:
    """Return ``True`` iff ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS`` is exactly ``"1"``.

    R5 strict — rejects ``"true"`` / ``"yes"`` / ``"on"`` / ``"01"`` /
    ``"1\\n"`` / ``""`` / unset. Pure ``os.environ.get`` comparison; no
    file IO, no subprocess, no ``shutil.which`` lookup. Codified by
    :func:`tests.test_pre_plugin_invocation.test_disabled_is_noop_byte_identical`.

    The strict literal-only matching mirrors the v8.3.2 PV-02 RTK
    proxy contract (``DEVOLAFLOW_RTK_PROXY``), the v8.3.3 PV-03 memory
    router contract (``DEVOLAFLOW_MEMORY_ROUTER``), and the v9.3.0
    PV-06 simple-shortcut contract (``DEVOLAFLOW_SIMPLE_SHORTCUT``).
    """
    return os.environ.get(ENV_FLAG, "") == ENV_FLAG_TRUTHY


def _extract_plugin_ids(payload: dict[str, Any]) -> tuple[list[str], list[HookViolation]]:
    """Extract plugin IDs from ``payload``; return ``(ids, violations)``.

    Lookup order (results are merged + de-duplicated; insertion order
    preserved):

    1. ``payload["plugin_ids"]`` — list[str] of plugin IDs (the
       multi-plugin batch path).
    2. ``payload["plugin_id"]`` — single str plugin ID (convenience
       single-plugin path).
    3. ``payload["workflow"]`` — workflow / template name (str). The
       workflow → plugin mapping is resolved via
       :func:`devolaflow.plugins.installer.plugins_for_workflow` which
       reads ``runtime-plugins.yaml#plugins[*].invoked_by_workflows``.
       This is the canonical v9.4.0 PV-03 path used by
       :mod:`devolaflow.feedback._emit_dispatch` — the dispatcher
       passes the workflow name from the dispatch payload and the
       hook handles the registry lookup.

    Returns
    -------
    tuple[list[str], list[HookViolation]]
        ``(ids, [])`` on a well-formed payload OR
        ``([], [violation])`` when the payload schema is malformed
        (PPI002 warning surface).

    Notes
    -----
    The workflow → plugin resolution path is best-effort: if the
    registry can't be read (FileNotFoundError, parse error, etc.) the
    helper logs a WARNING and returns the IDs accumulated from
    sources #1 and #2. The dispatcher remains uninterrupted (per S-5
    + the PPI permissive-default contract). A later call to
    :func:`ensure_plugin` would surface the registry error loudly.
    """
    ids: list[str] = []
    violations: list[HookViolation] = []

    raw_list = payload.get("plugin_ids")
    if raw_list is not None:
        if not isinstance(raw_list, list):
            violations.append(
                HookViolation(
                    code="PPI002",
                    message=(
                        "pre_plugin_invocation: 'plugin_ids' must be a list "
                        f"(got {type(raw_list).__name__})"
                    ),
                    severity="warning",
                    context={"plugin_ids_type": type(raw_list).__name__},
                )
            )
            return [], violations
        for entry in raw_list:
            if not isinstance(entry, str) or not entry:
                violations.append(
                    HookViolation(
                        code="PPI002",
                        message=(
                            "pre_plugin_invocation: 'plugin_ids' entries must be "
                            f"non-empty strings (got {entry!r})"
                        ),
                        severity="warning",
                        context={"bad_entry": repr(entry)},
                    )
                )
                continue
            ids.append(entry)

    raw_single = payload.get("plugin_id")
    if raw_single is not None:
        if not isinstance(raw_single, str) or not raw_single:
            violations.append(
                HookViolation(
                    code="PPI002",
                    message=(
                        "pre_plugin_invocation: 'plugin_id' must be a non-empty "
                        f"string (got {raw_single!r})"
                    ),
                    severity="warning",
                    context={"plugin_id_value": repr(raw_single)},
                )
            )
        elif raw_single not in ids:
            ids.append(raw_single)

    workflow = payload.get("workflow")
    if isinstance(workflow, str) and workflow:
        try:
            from devolaflow.plugins.installer import plugins_for_workflow

            resolved = plugins_for_workflow(workflow)
        except FileNotFoundError as exc:
            logger.warning(
                "pre_plugin_invocation: registry not available for workflow "
                "%r resolution (%s); skipping workflow-based plugin lookup",
                workflow,
                exc,
            )
            resolved = []
        except Exception as exc:  # noqa: BLE001 — best-effort registry lookup
            logger.warning(
                "pre_plugin_invocation: registry lookup for workflow %r "
                "failed (%s: %s); skipping workflow-based plugin lookup",
                workflow,
                type(exc).__name__,
                exc,
            )
            resolved = []
        for plugin_id in resolved:
            if plugin_id not in ids:
                ids.append(plugin_id)

    # Preserve insertion order while de-duplicating; dict-fromkeys is the
    # canonical Python idiom and is byte-stable across runs.
    return list(dict.fromkeys(ids)), violations


def pre_plugin_invocation(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Auto-install plugins cited in ``payload`` before the L3 dispatch fires.

    See module docstring for the full contract. Returns a
    :class:`HookResult` in both modes. Strict mode re-raises the
    top-severity :class:`HookViolation` aggregated across all install
    attempts; permissive mode aggregates them on the result envelope and
    emits WARNING logs via :func:`finalize` without raising.

    The payload schema is intentionally minimal — the dispatcher
    (`feedback.py::_emit_dispatch` in PV-03) is responsible for
    populating ``plugin_ids`` from the workflow → plugin mapping
    (`runtime-plugins.yaml#plugins[*].invoked_by_workflows`). Tests can
    invoke the hook directly with either ``{"plugin_id": "<id>"}`` or
    ``{"plugin_ids": ["<id1>", "<id2>"]}``.
    """
    if not is_auto_install_active():
        return finalize(EVENT, [], strict=strict)

    if not isinstance(payload, dict):
        return finalize(EVENT, [], strict=strict)

    ids, schema_violations = _extract_plugin_ids(payload)

    if not ids and not schema_violations:
        # Gate 2: no candidates, no schema problems → silent no-op.
        return finalize(EVENT, [], strict=strict)

    # Lazy-import — keep the lifecycle package import-light when env flag is
    # off OR the payload has no plugin candidates (the common dispatch shape).
    from devolaflow.plugins.exceptions import (
        PluginBackendUnsupported,
        PluginInstallError,
        PluginNotFoundError,
        PluginVersionMismatch,
    )
    from devolaflow.plugins.installer import ensure_plugin

    install_violations: list[HookViolation] = []
    for plugin_id in ids:
        try:
            version = ensure_plugin(plugin_id)
        except (
            PluginNotFoundError,
            PluginInstallError,
            PluginVersionMismatch,
            PluginBackendUnsupported,
        ) as exc:
            logger.warning(
                "pre_plugin_invocation: ensure_plugin(%r) raised %s: %s",
                plugin_id,
                type(exc).__name__,
                exc,
            )
            install_violations.append(
                HookViolation(
                    code="PPI001",
                    message=(
                        f"pre_plugin_invocation: ensure_plugin({plugin_id!r}) "
                        f"failed — {type(exc).__name__}: {exc}"
                    ),
                    severity="error",
                    context={
                        "plugin_id": plugin_id,
                        "exception_type": type(exc).__name__,
                        "exception_args": list(exc.args),
                        "details": getattr(exc, "details", {}),
                    },
                )
            )
            continue
        except Exception:
            # S-5: non-domain exceptions are logged loudly and re-raised.
            logger.warning(
                "pre_plugin_invocation: unexpected exception while installing "
                "plugin %r (re-raising per S-5 no-silent-failure)",
                plugin_id,
                exc_info=True,
            )
            raise
        else:
            logger.info(
                "pre_plugin_invocation: plugin %r installed at version %s",
                plugin_id,
                version,
            )

    return finalize(EVENT, schema_violations + install_violations, strict=strict)


__all__ = [
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "EVENT",
    "is_auto_install_active",
    "pre_plugin_invocation",
]
