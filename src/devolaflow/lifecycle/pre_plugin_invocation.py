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

Daily-upgrade integration (v10.2.1 PV-02 — closes D-P-2)
-------------------------------------------------------

Closes D-P-2 from `.local/research/v10.2.0_gap_analysis.md` §3.1
(BLOCKER): the 24h staleness gate (`defaults.upgrade_check_frequency_hours`)
was computed at v9.4.0 but no scheduler fired ``refresh_all`` automatically
on session start or per-dispatch. Operators had to invoke
``devolaflow plugins refresh`` manually — the user mandate "天级别自动更新"
(daily auto-update) was delivered only as a CLI verb, not as runtime
automation.

v10.2.1 PV-02 extends the existing :func:`pre_plugin_invocation` hook so
that AFTER ``ensure_plugin`` succeeds for a plugin candidate, the hook
ALSO checks ``is_plugin_stale(plugin_id, threshold_hours=...)``. When
stale, ``upgrade_plugin(plugin_id)`` fires best-effort. Failures surface
as :class:`HookViolation` ``PPI003`` (severity warning) but do NOT block
the dispatch — the dispatcher still proceeds with the install-or-confirmed
plugin per the v9.4.0 PV-02 contract.

Activation gate: REUSES the existing ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1``
env flag per Workflow Rule W-20 §3 reuse-first. The activation surface
is the same — "auto-manage plugin lifecycle" — so a NEW env flag would
violate the orthogonality test. Operators who had ``ensure_plugin`` ON
under v10.0.x get the daily-upgrade behaviour automatically with the
v10.2.1 bump; operators who never set the flag see byte-identical no-op.

R5 strict invariant preserved: when the env flag is OFF, the
:func:`is_plugin_stale` / :func:`upgrade_plugin` functions are NEVER
imported (lazy-import), no install log is read, no subprocess runs.
Codified in
``tests/test_pre_plugin_invocation.py::test_d_p_2_disabled_when_env_flag_off``.

Activation introspection: the module-level constant
:data:`EVENT_TRIGGERS_DAILY_UPGRADE` is provided so tests + downstream
governance can confirm the daily-upgrade behaviour is wired without
parsing source code.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT: str = "pre_plugin_invocation"
ENV_FLAG: str = "DEVOLAFLOW_AUTO_INSTALL_PLUGINS"
ENV_FLAG_TRUTHY: str = "1"

# v10.2.1 PV-02 D-P-2 — public introspection constant. ``True`` means
# this hook fires ``upgrade_plugin`` after ``ensure_plugin`` for stale
# plugins per the daily-upgrade integration. Tests + downstream
# governance can read this attribute to confirm the behaviour without
# parsing source code. The constant flips to ``False`` only if a future
# PV explicitly disables the daily-upgrade integration (which would
# require its own gap analysis + W-21-grade deliberation).
EVENT_TRIGGERS_DAILY_UPGRADE: bool = True

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


def _parse_plugin_ids_list(
    payload: dict[str, Any],
) -> tuple[list[str] | None, list[HookViolation]]:
    """Parse ``payload['plugin_ids']`` into ``(ids, violations)``.

    Extracted from :func:`_extract_plugin_ids` in v10.6.0 PV-01 (D-Q-1
    row #5). Result conventions:

    * ``(None, [violation])`` — fatal type error: ``plugin_ids`` is
      present but not a list. Caller MUST abort the merge and surface
      the violation; the rest of the payload is NOT consulted (mirrors
      the pre-extraction early-return behaviour).
    * ``([], [])`` — ``plugin_ids`` absent. Caller continues to the
      next source.
    * ``(ids, [])`` — well-formed list of strings.
    * ``(ids, [violations...])`` — list with some malformed entries
      surfaced as PPI002 warnings; valid entries still returned.
    """
    raw_list = payload.get("plugin_ids")
    if raw_list is None:
        return [], []

    if not isinstance(raw_list, list):
        return None, [
            HookViolation(
                code="PPI002",
                message=(
                    "pre_plugin_invocation: 'plugin_ids' must be a list "
                    f"(got {type(raw_list).__name__})"
                ),
                severity="warning",
                context={"plugin_ids_type": type(raw_list).__name__},
            )
        ]

    ids: list[str] = []
    violations: list[HookViolation] = []
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
    return ids, violations


def _parse_plugin_id_single(
    payload: dict[str, Any],
) -> tuple[list[str], list[HookViolation]]:
    """Parse ``payload['plugin_id']`` into ``(ids, violations)``.

    Extracted from :func:`_extract_plugin_ids` in v10.6.0 PV-01 (D-Q-1
    row #5). Returns at most one ID. A bad value (non-string or empty)
    surfaces a PPI002 warning and yields ``([], [violation])``.
    Absent field → ``([], [])``.
    """
    raw_single = payload.get("plugin_id")
    if raw_single is None:
        return [], []
    if not isinstance(raw_single, str) or not raw_single:
        return [], [
            HookViolation(
                code="PPI002",
                message=(
                    "pre_plugin_invocation: 'plugin_id' must be a non-empty "
                    f"string (got {raw_single!r})"
                ),
                severity="warning",
                context={"plugin_id_value": repr(raw_single)},
            )
        ]
    return [raw_single], []


def _parse_workflow_plugins(payload: dict[str, Any]) -> list[str]:
    """Resolve plugin IDs from ``payload['workflow']`` via the registry.

    Extracted from :func:`_extract_plugin_ids` in v10.6.0 PV-01 (D-Q-1
    row #5). Best-effort lookup via
    :func:`devolaflow.plugins.installer.plugins_for_workflow`. Registry
    read errors (``FileNotFoundError`` / arbitrary exception) log at
    WARNING and yield ``[]`` — the dispatcher remains uninterrupted
    per S-5 + the PPI permissive-default contract. A later call to
    :func:`ensure_plugin` would surface the registry error loudly.
    """
    workflow = payload.get("workflow")
    if not isinstance(workflow, str) or not workflow:
        return []
    try:
        from devolaflow.plugins.installer import plugins_for_workflow

        return plugins_for_workflow(workflow)
    except FileNotFoundError as exc:
        logger.warning(
            "pre_plugin_invocation: registry not available for workflow "
            "%r resolution (%s); skipping workflow-based plugin lookup",
            workflow,
            exc,
        )
        return []
    except Exception as exc:  # noqa: BLE001 — best-effort registry lookup
        logger.warning(
            "pre_plugin_invocation: registry lookup for workflow %r "
            "failed (%s: %s); skipping workflow-based plugin lookup",
            workflow,
            type(exc).__name__,
            exc,
        )
        return []


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

    Implementation note: per the v10.6.0 PV-01 cyclomatic-complexity
    reduction (NineS PV-03 deep-analysis row #5), the per-source parsers
    live in :func:`_parse_plugin_ids_list`, :func:`_parse_plugin_id_single`,
    and :func:`_parse_workflow_plugins`. Behaviour is byte-identical
    to v10.5.x baseline (verified by ``tests/test_pre_plugin_invocation.py``).
    """
    ids: list[str] = []
    violations: list[HookViolation] = []

    list_ids, list_violations = _parse_plugin_ids_list(payload)
    violations.extend(list_violations)
    if list_ids is None:
        # Fatal type error on payload["plugin_ids"] — preserve the
        # pre-extraction early-return contract: do NOT merge other sources.
        return [], violations
    ids.extend(list_ids)

    single_ids, single_violations = _parse_plugin_id_single(payload)
    violations.extend(single_violations)
    ids.extend(single_ids)

    ids.extend(_parse_workflow_plugins(payload))

    # Preserve insertion order while de-duplicating; dict-fromkeys is the
    # canonical Python idiom and is byte-stable across runs.
    return list(dict.fromkeys(ids)), violations


def _resolve_upgrade_threshold_hours(default: int) -> int:
    """Read ``defaults.upgrade_check_frequency_hours`` from the plugin registry.

    Defensive helper extracted in v10.2.3 PV-04 so the parent
    :func:`pre_plugin_invocation` does not own the registry-read
    branching (NineS PV-03 deep-analysis flagged the parent at CC=18;
    splitting this off + the per-plugin install/upgrade helper drops it
    below the warn threshold).

    Per S-5: registry read errors log at WARNING and fall back to
    ``default`` — the daily-upgrade gate still fires on the 24h cadence
    even when the registry is corrupt / missing. NEVER raises.
    """
    from devolaflow.plugins.installer import load_registry

    try:
        registry = load_registry()
    except (FileNotFoundError, OSError) as exc:
        logger.warning(
            "pre_plugin_invocation: cannot read registry defaults for "
            "daily-upgrade threshold (%s); falling back to %d-hour default",
            exc,
            default,
        )
        return default
    except Exception as exc:  # noqa: BLE001 — best-effort registry read
        logger.warning(
            "pre_plugin_invocation: registry parse failed for daily-upgrade "
            "threshold (%s: %s); falling back to %d-hour default",
            type(exc).__name__,
            exc,
            default,
        )
        return default

    defaults_section = registry.get("defaults") or {}
    if not isinstance(defaults_section, dict):
        return default
    raw_threshold = defaults_section.get("upgrade_check_frequency_hours")
    if isinstance(raw_threshold, int) and raw_threshold > 0:
        return raw_threshold
    return default


def _run_install_then_upgrade_for_plugin(
    plugin_id: str,
    *,
    threshold_hours: int,
) -> list[HookViolation]:
    """Run ``ensure_plugin`` then optionally ``upgrade_plugin`` for one plugin.

    Helper extracted in v10.2.3 PV-04 to address the NineS PV-03 deep-
    analysis finding at
    `.local/research/v10.2.2_nines.md` §2 row #2 (CC=18 in
    :func:`pre_plugin_invocation`). The parent function's loop body
    here was the dominant complexity contributor: 4 distinct exception
    sinks + the staleness branch + the upgrade branch all stacked into
    one cyclomatic graph.

    Returns a list of :class:`HookViolation` accumulated for this plugin
    (empty when the install + upgrade both succeed). The PPI001 / PPI003
    code surface is preserved verbatim — the public contract is
    byte-identical to the v10.2.1 baseline.

    Per S-5: domain exceptions (``PluginNotFoundError``,
    ``PluginInstallError``, ``PluginVersionMismatch``,
    ``PluginBackendUnsupported``) become typed violations; any OTHER
    exception logs at WARNING and is RE-RAISED — the helper never
    silently swallows non-domain failures.
    """
    from devolaflow.plugins.exceptions import (
        PluginBackendUnsupported,
        PluginInstallError,
        PluginNotFoundError,
        PluginVersionMismatch,
    )
    from devolaflow.plugins.installer import (
        ensure_plugin,
        is_plugin_stale,
        upgrade_plugin,
    )

    violations: list[HookViolation] = []

    try:
        # v15.2.0 B-6 — auto_install=True is EXPLICIT: this path only runs
        # when DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1 (operator opt-in), so the
        # flag's install semantics survive the registry
        # defaults.auto_install true → false flip. Mirrors the split
        # install handler byte-for-byte per the alias contract.
        version = ensure_plugin(plugin_id, auto_install=True)
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
        # v15.2.0 B-6 — tier-aware PPI001 severity shared with the split
        # install handler (single owner for the violation shape).
        from devolaflow.lifecycle.pre_plugin_invocation_install import (
            _ppi001_violation,
        )

        violations.append(_ppi001_violation(plugin_id, exc))
        return violations
    except Exception:
        logger.warning(
            "pre_plugin_invocation: unexpected exception while installing "
            "plugin %r (re-raising per S-5 no-silent-failure)",
            plugin_id,
            exc_info=True,
        )
        raise
    logger.info(
        "pre_plugin_invocation: plugin %r installed at version %s",
        plugin_id,
        version,
    )

    try:
        stale = is_plugin_stale(plugin_id, threshold_hours=threshold_hours)
    except Exception as exc:  # noqa: BLE001 — best-effort staleness probe
        logger.warning(
            "pre_plugin_invocation: is_plugin_stale(%r) raised %s: %s; "
            "skipping daily-upgrade probe for this plugin",
            plugin_id,
            type(exc).__name__,
            exc,
        )
        return violations

    if not stale:
        return violations

    try:
        upgraded_version = upgrade_plugin(plugin_id)
    except (
        PluginNotFoundError,
        PluginInstallError,
        PluginVersionMismatch,
        PluginBackendUnsupported,
    ) as exc:
        logger.warning(
            "pre_plugin_invocation: upgrade_plugin(%r) raised %s: %s "
            "(stale plugin daily-upgrade); recording PPI003 warning "
            "but NOT blocking dispatch",
            plugin_id,
            type(exc).__name__,
            exc,
        )
        violations.append(
            HookViolation(
                code="PPI003",
                message=(
                    f"pre_plugin_invocation: upgrade_plugin({plugin_id!r}) "
                    f"failed during daily-upgrade probe — "
                    f"{type(exc).__name__}: {exc}"
                ),
                severity="warning",
                context={
                    "plugin_id": plugin_id,
                    "exception_type": type(exc).__name__,
                    "exception_args": list(exc.args),
                    "details": getattr(exc, "details", {}),
                    "stage": "daily_upgrade",
                },
            )
        )
        return violations
    except Exception:
        logger.warning(
            "pre_plugin_invocation: unexpected exception while upgrading "
            "stale plugin %r (re-raising per S-5 no-silent-failure)",
            plugin_id,
            exc_info=True,
        )
        raise
    logger.info(
        "pre_plugin_invocation: stale plugin %r upgraded to %s (daily-upgrade integration)",
        plugin_id,
        upgraded_version,
    )
    return violations


def pre_plugin_invocation(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Auto-install + upgrade plugins cited in ``payload`` (v10.8.0 alias).

    v10.8.0 D-C-3 split the install + upgrade responsibilities into two
    dedicated handlers at ``DEFAULT_EVENTS`` positions 11 + 12
    (``pre_plugin_invocation_install`` / ``pre_plugin_invocation_upgrade``).
    This handler REMAINS at position 9 as a 1-cycle backward-compat
    alias whose body delegates to the two split handlers in sequence,
    preserving byte-identical observable behaviour for operators who
    registered extra handlers on ``PRE_PLUGIN_INVOCATION_EVENT``.

    Per D-C-3 §2 G-7 backward-compat contract:
    ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` activates install + upgrade
    IDENTICALLY to v10.7.x. The alias deprecation is TELEGRAPHED for
    v12.0.0+ per the W-21-class 2-cycle migration cadence; operators
    should migrate handler registrations to the new event names before
    v12.0.0 cuts over.

    See module docstring for the full contract. Returns a
    :class:`HookResult` in both modes. Strict mode re-raises the
    top-severity :class:`HookViolation` aggregated across install +
    upgrade attempts; permissive mode aggregates them on the result
    envelope and emits WARNING logs via :func:`finalize` without
    raising.

    Implementation note: per the v10.2.3 PV-04 CC-reduction + v10.8.0
    D-C-3 split, the per-plugin install body lives in
    :func:`_run_install_then_upgrade_for_plugin` (retained for
    backward-compat callers); the new split handlers use their own
    focused helpers. Behaviour is byte-identical to v10.2.1+ baseline.
    """
    if not is_auto_install_active():
        return finalize(EVENT, [], strict=strict)

    if not isinstance(payload, dict):
        return finalize(EVENT, [], strict=strict)

    ids, schema_violations = _extract_plugin_ids(payload)

    if not ids and not schema_violations:
        # Gate 2: no candidates, no schema problems → silent no-op.
        return finalize(EVENT, [], strict=strict)

    from devolaflow.plugins.installer import _DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS

    threshold_hours = _resolve_upgrade_threshold_hours(_DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS)

    install_violations: list[HookViolation] = []
    for plugin_id in ids:
        install_violations.extend(
            _run_install_then_upgrade_for_plugin(
                plugin_id,
                threshold_hours=threshold_hours,
            )
        )

    return finalize(EVENT, schema_violations + install_violations, strict=strict)


__all__ = [
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "EVENT",
    "EVENT_TRIGGERS_DAILY_UPGRADE",
    "is_auto_install_active",
    "pre_plugin_invocation",
]
