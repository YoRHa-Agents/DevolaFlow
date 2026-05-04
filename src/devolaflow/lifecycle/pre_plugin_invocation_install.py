"""Pre-plugin-invocation INSTALL lifecycle hook — ``pre_plugin_invocation_install``.

Closes D-C-3 from `.local/research/v11.0.0_patches/D-C-3.md` (v10.8.0
cycle). Extracts the INSTALL responsibility from the existing
``pre_plugin_invocation`` hook (position 9) into a dedicated handler at
DEFAULT_EVENTS position 11 (A-2.2 append-only).

Responsibility (exactly one): for each plugin candidate cited in the
dispatch payload, call :func:`devolaflow.plugins.installer.ensure_plugin`.
Surface domain exceptions as :class:`HookViolation` ``PPI001`` (severity
``error``); permissive mode continues; strict mode re-raises.

This handler DOES NOT fire ``upgrade_plugin`` / ``is_plugin_stale`` —
that responsibility lives in :mod:`pre_plugin_invocation_upgrade` at
DEFAULT_EVENTS position 12.

Activation gate: REUSES ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` per
Workflow Rule W-20 (same activation surface as the v9.4.0 baseline alias
at position 9). NO new env flag introduced in v10.8.0 — the
``DEVOLAFLOW_AUTO_UPGRADE_PLUGINS`` flag is TELEGRAPHED for v12.0.0+
pending the split's 1-cycle observation period.

Backward-compat: the existing ``pre_plugin_invocation`` alias at position
9 delegates to THIS handler (install) + the upgrade handler (in
sequence) so operators registering extras on the alias event see
byte-identical behaviour.

Source: v10.8.0 D-C-3 §2 patch_design step 3.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT: str = "pre_plugin_invocation_install"
ENV_FLAG: str = "DEVOLAFLOW_AUTO_INSTALL_PLUGINS"
ENV_FLAG_TRUTHY: str = "1"

logger = logging.getLogger(__name__)


def is_auto_install_active() -> bool:
    """Return ``True`` iff ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS`` is exactly ``"1"``.

    R5 strict — rejects ``"true"`` / ``"yes"`` / ``"on"`` / ``"01"`` /
    ``"1\\n"`` / ``""`` / unset. Pure ``os.environ.get`` comparison; no
    file IO, no subprocess, no ``shutil.which`` lookup.

    Mirrors :func:`devolaflow.lifecycle.pre_plugin_invocation.is_auto_install_active`
    byte-for-byte — the two handlers share activation semantics per the
    1-cycle alias contract.
    """
    return os.environ.get(ENV_FLAG, "") == ENV_FLAG_TRUTHY


def _run_install_for_plugin(plugin_id: str) -> list[HookViolation]:
    """Run ``ensure_plugin`` for a single plugin; return accumulated violations.

    Extracted from :func:`_run_install_then_upgrade_for_plugin` in the
    original :mod:`pre_plugin_invocation` module (v10.2.3 PV-04 baseline).
    The upgrade / staleness branches are EXCISED — that responsibility
    lives in :mod:`pre_plugin_invocation_upgrade`.

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
    from devolaflow.plugins.installer import ensure_plugin

    violations: list[HookViolation] = []

    try:
        version = ensure_plugin(plugin_id)
    except (
        PluginNotFoundError,
        PluginInstallError,
        PluginVersionMismatch,
        PluginBackendUnsupported,
    ) as exc:
        logger.warning(
            "pre_plugin_invocation_install: ensure_plugin(%r) raised %s: %s",
            plugin_id,
            type(exc).__name__,
            exc,
        )
        violations.append(
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
        return violations
    except Exception:
        logger.warning(
            "pre_plugin_invocation_install: unexpected exception while "
            "installing plugin %r (re-raising per S-5 no-silent-failure)",
            plugin_id,
            exc_info=True,
        )
        raise
    logger.info(
        "pre_plugin_invocation_install: plugin %r installed at version %s",
        plugin_id,
        version,
    )
    return violations


def pre_plugin_invocation_install(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Auto-install plugins cited in ``payload`` BEFORE the L3 dispatch fires.

    Separated from the v9.4.0 PV-02 ``pre_plugin_invocation`` hook in
    v10.8.0 D-C-3 so the INSTALL responsibility (PPI001 surface) lives
    in one focused handler; the UPGRADE responsibility (PPI003) lives
    in :mod:`pre_plugin_invocation_upgrade`.

    Activation: ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` (REUSED per W-20
    orthogonality — no new env flag). When the env-flag is OFF, the
    handler returns an empty :class:`HookResult` with zero filesystem IO
    AND zero subprocess work (R5 strict).

    Payload schema: same as the alias hook —
        {"plugin_id": str} OR {"plugin_ids": list[str]} OR
        {"workflow": str}  (resolved via runtime-plugins.yaml).

    Violation surface: PPI001 only. PPI002 (payload schema malformed) is
    owned by the alias / router path; this handler trusts its
    ``payload["plugin_ids"]`` input is already validated.
    """
    if not is_auto_install_active():
        return finalize(EVENT, [], strict=strict)

    if not isinstance(payload, dict):
        return finalize(EVENT, [], strict=strict)

    raw_ids = payload.get("plugin_ids")
    if not isinstance(raw_ids, list):
        # The alias router normalises the payload before delegation; a
        # bare {"plugin_id": ...} arrives here flattened. If the caller
        # skipped the router and passed a raw payload, we still accept
        # the single-string shape defensively.
        single = payload.get("plugin_id")
        if isinstance(single, str) and single:
            raw_ids = [single]
        else:
            return finalize(EVENT, [], strict=strict)

    ids: list[str] = [entry for entry in raw_ids if isinstance(entry, str) and entry]
    if not ids:
        return finalize(EVENT, [], strict=strict)

    install_violations: list[HookViolation] = []
    for plugin_id in ids:
        install_violations.extend(_run_install_for_plugin(plugin_id))

    return finalize(EVENT, install_violations, strict=strict)


__all__ = [
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "EVENT",
    "is_auto_install_active",
    "pre_plugin_invocation_install",
]
