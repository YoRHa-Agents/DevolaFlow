"""Focused implementation slice for plugin refresh operations."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


@dataclass(frozen=True)
class RefreshOutcome:
    """Outcome of a single plugin refresh attempt during :func:`refresh_all`."""

    plugin_id: str
    action: str  # "upgraded" | "skipped_fresh" | "skipped_no_upgrade_cmd" | "failed"
    version: str | None = None
    reason: str | None = None
    error: str | None = None


def refresh_all(
    *,
    registry_path: Path | str | None = None,
    log_path: Path | str | None = None,
    force: bool = False,
    only: list[str] | None = None,
    now: datetime | None = None,
) -> list[RefreshOutcome]:
    """Walk the registry and upgrade stale plugins.

    Parameters
    ----------
    registry_path:
        Override for the registry YAML.
    log_path:
        Override for the install log used by the staleness probe.
    force:
        When ``True``, bypass the staleness check and upgrade every
        plugin regardless of ``last_checked``.
    only:
        Restrict the refresh to a list of plugin IDs. When ``None``,
        ALL plugins in the registry are considered.
    now:
        Override the staleness reference time (test seam).

    Returns
    -------
    list[RefreshOutcome]
        One outcome per plugin considered (not per registry entry —
        when ``only=[...]`` plugins outside the filter are NOT
        included in the returned list). The CLI in
        :mod:`devolaflow.cli` consumes this directly to render a
        per-plugin status table.

    CI-safe per gap analysis §6 AC-7: a network failure on one plugin
    is captured as ``RefreshOutcome(action="failed", error=...)`` and
    the function continues with the next plugin instead of aborting.
    """
    registry = load_registry(registry_path)
    defaults = _load_defaults(registry)
    effective_log = Path(log_path) if log_path is not None else Path(defaults.install_log_path)
    threshold_hours = defaults.upgrade_check_frequency_hours

    target_filter: frozenset[str] | None = frozenset(only) if only is not None else None
    outcomes: list[RefreshOutcome] = []

    for entry in registry.get("plugins", []):
        if not isinstance(entry, dict):
            continue
        plugin_id_raw = entry.get("id")
        if not isinstance(plugin_id_raw, str) or not plugin_id_raw:
            continue
        plugin_id = plugin_id_raw

        if target_filter is not None and plugin_id not in target_filter:
            continue

        if not force and not is_plugin_stale(
            plugin_id,
            threshold_hours=threshold_hours,
            log_path=effective_log,
            now=now,
        ):
            outcomes.append(
                RefreshOutcome(
                    plugin_id=plugin_id,
                    action="skipped_fresh",
                    reason=f"checked within last {threshold_hours}h",
                )
            )
            continue

        try:
            version = upgrade_plugin(plugin_id, registry_path=registry_path, log_path=effective_log)
            outcomes.append(RefreshOutcome(plugin_id=plugin_id, action="upgraded", version=version))
        except (
            PluginNotFoundError,
            PluginInstallError,
            PluginVersionMismatch,
            PluginBackendUnsupported,
        ) as exc:
            logger.warning("refresh_all: upgrade failed for %s — %s", plugin_id, exc)
            outcomes.append(
                RefreshOutcome(
                    plugin_id=plugin_id,
                    action="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    return outcomes


def list_plugins(
    *,
    registry_path: Path | str | None = None,
    log_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return a per-plugin status dict suitable for ``devolaflow plugins list``.

    Each dict carries: ``id``, ``backend``, ``package``, ``min_version``,
    ``installed_version`` (probed at call time; ``None`` when missing),
    ``last_checked`` (ISO-8601 string OR ``None``), ``invoked_by_workflows``.

    No installs / upgrades are triggered — pure inspection surface.
    """
    registry = load_registry(registry_path)
    defaults = _load_defaults(registry)
    effective_log = Path(log_path) if log_path is not None else Path(defaults.install_log_path)
    timeout = defaults.network_timeout_seconds

    rows: list[dict[str, Any]] = []
    for entry in registry.get("plugins", []):
        if not isinstance(entry, dict):
            continue
        plugin_id = entry.get("id")
        if not isinstance(plugin_id, str) or not plugin_id:
            continue
        try:
            spec = resolve_plugin(plugin_id, registry)
        except (PluginInstallError, PluginBackendUnsupported, PluginNotFoundError) as exc:
            logger.warning("list_plugins: resolve_plugin failed for %s — %s", plugin_id, exc)
            continue
        last = read_last_checked(plugin_id, log_path=effective_log)
        rows.append(
            {
                "id": spec.id,
                "backend": spec.backend,
                "package": spec.package,
                "min_version": spec.min_version,
                "installed_version": _probe_version(spec, timeout=timeout),
                "last_checked": last.isoformat() if last is not None else None,
                "invoked_by_workflows": list(spec.invoked_by_workflows),
                "upgrade_cmd": spec.upgrade_cmd or spec.install_cmd,
                "has_explicit_upgrade_cmd": spec.upgrade_cmd is not None,
            }
        )
    return rows


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
