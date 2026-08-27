"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _parse_log_event_timestamp(
    raw_line: str,
    plugin_id: str,
    successful_events: frozenset[str],
) -> datetime | None:
    """Parse one JSONL audit-log line and return its timestamp if applicable.

    Returns the parsed UTC datetime when ``raw_line`` is a successful-event
    record for ``plugin_id`` (i.e. ``record["event"] in successful_events``
    AND ``record["plugin_id"] == plugin_id`` AND ``record["ts"]`` is a
    parseable ISO-8601 string). Returns ``None`` for ANY of: empty line,
    malformed JSON, non-dict payload, mismatched plugin_id, non-success
    event, missing/non-string/empty ``ts`` field, or unparseable timestamp.

    The function never raises — every defensive branch returns ``None`` so
    the caller's iteration over a corrupt log does not abort scanning.
    Loud failures (S-5) are reserved for OS-level read errors which the
    caller (:func:`read_last_checked`) handles via ``OSError`` catch.

    Extracted from :func:`read_last_checked` in v10.2.4 PV-05 self-iteration
    round 2 to close a historical complexity finding (cyclomatic
    complexity 15 in ``read_last_checked``). Behaviour byte-identical to
    the inline pre-extraction body; preserved by the existing
    ``TestReadLastChecked`` suite (5 prior tests) plus the NEW direct-helper
    tests in ``TestParseLogEventTimestamp``.
    """
    line = raw_line.strip()
    if not line:
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None
    if record.get("plugin_id") != plugin_id:
        return None
    if record.get("event") not in successful_events:
        return None
    ts_str = record.get("ts")
    if not isinstance(ts_str, str) or not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None


def read_last_checked(
    plugin_id: str,
    *,
    log_path: Path | str | None = None,
) -> datetime | None:
    """Return the most-recent install/upgrade timestamp for ``plugin_id``.

    Reconstructs ``last_checked`` from the canonical
    ``.local/memory/plugin_install.log`` (the JSONL audit trail
    written by :func:`ensure_plugin` / :func:`upgrade_plugin`). The
    tracker considers ANY successful event for the plugin as a
    "checked" timestamp — `plugin_already_installed`,
    `plugin_installed`, `plugin_upgraded` all count.

    Parameters
    ----------
    plugin_id:
        Identifier matching ``plugins[].id`` in the registry.
    log_path:
        Override path to the install log. Defaults to
        ``.local/memory/plugin_install.log``.

    Returns
    -------
    datetime | None
        Most-recent UTC timestamp from the log for this plugin, OR
        ``None`` when the log is missing OR no events for this plugin
        have ever been recorded. ``None`` MUST be treated as "stale —
        check immediately" by the staleness predicate.
    """
    effective_log = (
        Path(log_path) if log_path is not None else Path(".local/memory/plugin_install.log")
    )
    if not effective_log.is_file():
        return None

    most_recent: datetime | None = None
    try:
        with effective_log.open(encoding="utf-8") as fh:
            for raw_line in fh:
                ts = _parse_log_event_timestamp(
                    raw_line, plugin_id, _LAST_CHECKED_SUCCESSFUL_EVENTS
                )
                if ts is None:
                    continue
                if most_recent is None or ts > most_recent:
                    most_recent = ts
    except OSError as exc:
        logger.warning("Failed to read plugin install log at %s: %s", effective_log, exc)
        return None
    return most_recent


def is_plugin_stale(
    plugin_id: str,
    *,
    threshold_hours: int,
    log_path: Path | str | None = None,
    now: datetime | None = None,
) -> bool:
    """Return ``True`` when the plugin has not been checked in ``threshold_hours``.

    A plugin with NO recorded events is considered stale (never been
    installed / verified). The reference time defaults to ``datetime.now(UTC)``
    — tests pin it via the ``now`` argument.
    """
    last_checked = read_last_checked(plugin_id, log_path=log_path)
    if last_checked is None:
        return True
    reference = now if now is not None else datetime.now(UTC)
    if last_checked.tzinfo is None:
        # Defensive: treat naive timestamps as UTC.
        last_checked = last_checked.replace(tzinfo=UTC)
    delta = reference - last_checked
    return delta.total_seconds() >= threshold_hours * 3600


def upgrade_plugin(
    plugin_id: str,
    *,
    registry_path: Path | str | None = None,
    log_path: Path | str | None = None,
) -> str:
    """Upgrade ``plugin_id`` by running its ``upgrade_cmd`` (or ``install_cmd``).

    Resolution chain:

    1. Load + resolve the registry entry.
    2. Run ``spec.upgrade_cmd`` (when set) OR fall back to
       ``spec.install_cmd`` (which for pip / npm / curl-script backends
       is typically idempotent — running it again upgrades to the
       latest published version per the v8.3.0 PV-01 backend contract).
    3. Re-probe version via ``spec.version_check_cmd``.
    4. Append a ``plugin_upgraded`` JSONL event to the install log so
       :func:`read_last_checked` sees the upgrade as a fresh checkpoint.

    Parameters
    ----------
    plugin_id:
        Identifier matching ``plugins[].id``.
    registry_path:
        Override for the registry YAML; defaults to
        ``workflow-system/agent/knowledge/runtime-plugins.yaml``.
    log_path:
        Override for the install log; defaults to
        ``defaults.install_log_path``.

    Returns
    -------
    str
        The post-upgrade version string parsed from
        ``version_check_cmd`` output.

    Raises
    ------
    PluginNotFoundError, PluginBackendUnsupported, PluginInstallError,
    PluginVersionMismatch — same loud-failure contract as
    :func:`ensure_plugin` per S-5.
    """
    registry = load_registry(registry_path)
    defaults = _load_defaults(registry)
    effective_log = Path(log_path) if log_path is not None else Path(defaults.install_log_path)
    timeout = defaults.network_timeout_seconds
    spec = resolve_plugin(plugin_id, registry)

    cmd = spec.upgrade_cmd or spec.install_cmd
    logger.info("upgrade_plugin: %s — running upgrade command %r", spec.id, cmd)
    t_start = time.monotonic()
    try:
        proc = _run_cmd(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _append_log(
            effective_log,
            "plugin_upgrade_failed",
            spec.id,
            {"backend": spec.backend, "reason": f"timeout after {timeout}s", "cmd": cmd},
        )
        raise PluginInstallError(
            f"upgrade timeout for plugin {spec.id!r} after {timeout}s.",
            details={"plugin_id": spec.id, "timeout_seconds": timeout, "cmd": cmd},
        ) from exc
    except OSError as exc:
        _append_log(
            effective_log,
            "plugin_upgrade_failed",
            spec.id,
            {"backend": spec.backend, "reason": f"os-error: {exc}", "cmd": cmd},
        )
        raise PluginInstallError(
            f"upgrade failed for plugin {spec.id!r} (os-error): {exc}.",
            details={"plugin_id": spec.id, "cmd": cmd},
        ) from exc

    if proc.returncode != 0:
        _append_log(
            effective_log,
            "plugin_upgrade_failed",
            spec.id,
            {
                "backend": spec.backend,
                "returncode": proc.returncode,
                "stderr": proc.stderr[:400],
                "cmd": cmd,
            },
        )
        raise PluginInstallError(
            f"upgrade failed for plugin {spec.id!r} "
            f"(returncode={proc.returncode}): {proc.stderr[:400]!r}",
            details={
                "plugin_id": spec.id,
                "cmd": cmd,
                "returncode": proc.returncode,
                "stderr": proc.stderr[:400],
            },
        )

    postupgrade_version = _probe_version(spec, timeout=timeout)
    if postupgrade_version is None:
        _append_log(
            effective_log,
            "plugin_upgrade_post_version_unparseable",
            spec.id,
            {"backend": spec.backend, "min_version": spec.min_version},
        )
        raise PluginInstallError(
            f"Plugin {spec.id!r} upgraded but version_check_cmd "
            f"({spec.version_check_cmd!r}) did not return a parseable version.",
            details={"plugin_id": spec.id, "backend": spec.backend},
        )

    if not _meets_min(postupgrade_version, spec.min_version):
        _append_log(
            effective_log,
            "plugin_upgrade_version_mismatch",
            spec.id,
            {
                "postupgrade_version": postupgrade_version,
                "min_version": spec.min_version,
                "backend": spec.backend,
            },
        )
        raise PluginVersionMismatch(
            f"Plugin {spec.id!r} upgraded to {postupgrade_version} but "
            f"min_version is {spec.min_version}.",
            details={
                "plugin_id": spec.id,
                "postupgrade_version": postupgrade_version,
                "min_version": spec.min_version,
            },
        )

    _append_log(
        effective_log,
        "plugin_upgraded",
        spec.id,
        {
            "version": postupgrade_version,
            "min_version": spec.min_version,
            "backend": spec.backend,
            "elapsed_s": round(time.monotonic() - t_start, 3),
        },
    )
    logger.info(
        "plugin_upgraded: %s at version %s (backend=%s)",
        spec.id,
        postupgrade_version,
        spec.backend,
    )
    return postupgrade_version


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
