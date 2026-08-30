"""Pre-plugin-invocation UPGRADE lifecycle hook — ``pre_plugin_invocation_upgrade``.

Closes D-C-3 from `.local/research/v11.0.0_patches/D-C-3.md` (v10.8.0
cycle). Extracts the UPGRADE responsibility from the existing
``pre_plugin_invocation`` hook (position 8) into a dedicated handler at
DEFAULT_EVENTS position 10 after v22 re-numbering.

Responsibility (exactly one): for each plugin candidate, check
:func:`devolaflow.plugins.installer.is_plugin_stale`; when stale, fire
:func:`devolaflow.plugins.installer.upgrade_plugin` best-effort.
Surface domain exceptions as :class:`HookViolation` ``PPI003`` (severity
``warning``); dispatch continues in BOTH modes — the v10.2.1 PV-02 D-P-2
contract declared upgrade failures MUST NOT block dispatch.

This handler DOES NOT fire ``ensure_plugin`` — that responsibility lives
in :mod:`pre_plugin_invocation_install` at DEFAULT_EVENTS position 9.
The alias handler at position 8 sequences install → upgrade to preserve
v10.3.0 byte-identical behaviour for operators.

Activation gate: REUSES ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` per
Workflow Rule W-20 (1-cycle backward compat for v10.8.0; the
``DEVOLAFLOW_AUTO_UPGRADE_PLUGINS`` flag is TELEGRAPHED for v12.0.0+
cycles per D-C-3 §2 patch_design step 4 and §9 R3 mitigation).

Source: v10.8.0 D-C-3 §2 patch_design step 3.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT: str = "pre_plugin_invocation_upgrade"
ENV_FLAG: str = "DEVOLAFLOW_AUTO_INSTALL_PLUGINS"
"""Activation env-flag. v10.8.0 REUSES the install-flag per W-20 (same
activation surface during the 1-cycle alias window). A future
``DEVOLAFLOW_AUTO_UPGRADE_PLUGINS`` flag is telegraphed but NOT
introduced in this PV."""

ENV_FLAG_TRUTHY: str = "1"

logger = logging.getLogger(__name__)


def is_auto_upgrade_active() -> bool:
    """Return ``True`` iff ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS`` is exactly ``"1"``.

    v10.8.0 REUSE: the install and upgrade handlers share activation
    semantics during the 1-cycle alias window. When the v12.0.0+ SI-1
    gap analysis admits ``DEVOLAFLOW_AUTO_UPGRADE_PLUGINS`` (per D-C-3
    §2 step 4 telegraph), this function becomes the sole read site for
    the orthogonal flag; no other handler in the tree needs updating.
    """
    return os.environ.get(ENV_FLAG, "") == ENV_FLAG_TRUTHY


def _resolve_upgrade_threshold_hours(default: int) -> int:
    """Read ``defaults.upgrade_check_frequency_hours`` from the plugin registry.

    Mirrors
    :func:`devolaflow.lifecycle.pre_plugin_invocation._resolve_upgrade_threshold_hours`
    byte-identically to preserve the alias path's observable behaviour
    (per D-C-3 §2 G-7 backward-compat contract).

    Per S-5: registry read errors log at WARNING and fall back to
    ``default``; NEVER raises.
    """
    from devolaflow.plugins.installer import load_registry

    try:
        registry = load_registry()
    except (FileNotFoundError, OSError) as exc:
        logger.warning(
            "pre_plugin_invocation_upgrade: cannot read registry defaults for "
            "daily-upgrade threshold (%s); falling back to %d-hour default",
            exc,
            default,
        )
        return default
    except Exception as exc:  # noqa: BLE001 — best-effort registry read
        logger.warning(
            "pre_plugin_invocation_upgrade: registry parse failed for "
            "daily-upgrade threshold (%s: %s); falling back to %d-hour default",
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


def _run_upgrade_for_plugin(
    plugin_id: str,
    *,
    threshold_hours: int,
) -> list[HookViolation]:
    """Run ``is_plugin_stale`` + optionally ``upgrade_plugin`` for a single plugin.

    Extracted from :func:`_run_install_then_upgrade_for_plugin` in the
    original :mod:`pre_plugin_invocation` module. The install branch is
    EXCISED — that responsibility lives in :mod:`pre_plugin_invocation_install`.

    Per S-5: domain exceptions from ``upgrade_plugin`` become PPI003
    warnings (upgrade failures DO NOT block dispatch per v10.2.1
    contract); any OTHER exception logs at WARNING and is RE-RAISED.
    """
    from devolaflow.plugins.exceptions import (
        PluginBackendUnsupported,
        PluginInstallError,
        PluginNotFoundError,
        PluginVersionMismatch,
    )
    from devolaflow.plugins.installer import is_plugin_stale, upgrade_plugin

    violations: list[HookViolation] = []

    try:
        stale = is_plugin_stale(plugin_id, threshold_hours=threshold_hours)
    except Exception as exc:  # noqa: BLE001 — best-effort staleness probe
        logger.warning(
            "pre_plugin_invocation_upgrade: is_plugin_stale(%r) raised %s: %s; "
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
            "pre_plugin_invocation_upgrade: upgrade_plugin(%r) raised %s: %s "
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
            "pre_plugin_invocation_upgrade: unexpected exception while upgrading "
            "stale plugin %r (re-raising per S-5 no-silent-failure)",
            plugin_id,
            exc_info=True,
        )
        raise
    logger.info(
        "pre_plugin_invocation_upgrade: stale plugin %r upgraded to %s (daily-upgrade integration)",
        plugin_id,
        upgraded_version,
    )
    return violations


def pre_plugin_invocation_upgrade(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Check plugin staleness and run ``upgrade_plugin`` for stale candidates.

    Separated from the v9.4.0 PV-02 ``pre_plugin_invocation`` hook in
    v10.8.0 D-C-3 so the UPGRADE responsibility (PPI003 surface) lives
    in one focused handler; the INSTALL responsibility (PPI001) lives
    in :mod:`pre_plugin_invocation_install`.

    Activation: REUSES ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` for v10.8.0
    (1-cycle alias window; ``DEVOLAFLOW_AUTO_UPGRADE_PLUGINS`` telegraphed
    for v12.0.0+). When the env-flag is OFF, the handler returns an
    empty :class:`HookResult` with zero filesystem IO AND zero subprocess
    work (R5 strict).

    Payload schema: same as :mod:`pre_plugin_invocation_install`.

    Violation surface: PPI003 only. PPI001 belongs to the install
    handler — disjoint per D-C-3 §2 AC bullet "PPI001 stays in
    install-handler ONLY; PPI003 stays in upgrade-handler ONLY".
    """
    if not is_auto_upgrade_active():
        return finalize(EVENT, [], strict=strict)

    if not isinstance(payload, dict):
        return finalize(EVENT, [], strict=strict)

    raw_ids = payload.get("plugin_ids")
    if not isinstance(raw_ids, list):
        single = payload.get("plugin_id")
        if isinstance(single, str) and single:
            raw_ids = [single]
        else:
            return finalize(EVENT, [], strict=strict)

    ids: list[str] = [entry for entry in raw_ids if isinstance(entry, str) and entry]
    if not ids:
        return finalize(EVENT, [], strict=strict)

    from devolaflow.plugins.installer import _DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS

    threshold_hours = _resolve_upgrade_threshold_hours(_DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS)

    upgrade_violations: list[HookViolation] = []
    for plugin_id in ids:
        upgrade_violations.extend(
            _run_upgrade_for_plugin(plugin_id, threshold_hours=threshold_hours)
        )

    return finalize(EVENT, upgrade_violations, strict=strict)


__all__ = [
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "EVENT",
    "is_auto_upgrade_active",
    "pre_plugin_invocation_upgrade",
]
