"""Focused implementation slice for plugin lifecycle operations."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def ensure_plugin(
    plugin_id: str,
    *,
    registry_path: Path | str | None = None,
    auto_install: bool | None = None,
    log_path: Path | str | None = None,
) -> str:
    """Ensure ``plugin_id`` is installed at >= its declared ``min_version``.

    Resolution chain (matches design.md §6.5 failure-mode catalog):

    1. Load + resolve registry entry.
    2. Probe current version via ``version_check_cmd``; if present AND
       ``>= min_version`` → return version (INFO
       ``plugin_already_installed``).
    3. If ``auto_install`` is ``False`` → raise :class:`PluginVersionMismatch`
       loudly per S-5.
    4. Invoke backend-specific install routine (``pip`` or ``npm_then_init``);
       honour ``prefer_local_fallback`` when
       ``local_fallback_path`` is set.
    5. Re-probe version; raise :class:`PluginVersionMismatch` if still below
       floor, or :class:`PluginInstallError` when the version command now
       returns nothing parseable.
    6. Run SHA-256 verification (best-effort; see :func:`_verify_sha256`).
    7. Append a JSONL install event to ``log_path`` (defaulted from registry).

    Parameters
    ----------
    plugin_id:
        Identifier matching a ``plugins[].id`` row in ``runtime-plugins.yaml``.
    registry_path:
        Override path to the registry YAML. Defaults to
        ``workflow-system/agent/knowledge/runtime-plugins.yaml``.
    auto_install:
        When ``None`` (the common case), registry ``defaults.auto_install`` is
        honoured. When ``False``, a missing / outdated plugin raises
        :class:`PluginVersionMismatch` instead of installing.
    log_path:
        JSONL install-event log. Defaults to registry ``defaults.install_log_path``.

    Returns
    -------
    str
        The installed version string (as parsed from ``version_check_cmd``).

    Raises
    ------
    PluginNotFoundError
        ``plugin_id`` missing from the registry.
    PluginBackendUnsupported
        Registry row declares an unsupported backend.
    PluginVersionMismatch
        Installed version < ``min_version`` (pre- or post-install) OR
        ``auto_install=False`` and plugin is missing / outdated.
    PluginInstallError
        Install attempt failed (network unreachable, subprocess non-zero,
        timeout, version still unparseable post-install, sha mismatch).

    Implementation note: per the v10.6.0 PV-01 cyclomatic-complexity
    reduction (historical analysis row #1), the cache-hit arm
    lives in :func:`_handle_already_installed_path` and the
    network-fetch arm lives in :func:`_handle_install_path`. All 8
    named log events (``plugin_already_installed``, ``plugin_installed``,
    ``plugin_install_blocked_by_config``, ``plugin_install_failed``,
    ``plugin_install_post_version_unparseable``,
    ``plugin_install_version_mismatch``, ``plugin_install_sha_mismatch``,
    and the two distinguish-failed variants) are PRESERVED VERBATIM
    per the §9 risk register row #3 contract — downstream operator
    tooling grep-pinned to these event names continues to see
    byte-identical JSONL output.
    """
    registry = load_registry(registry_path)
    defaults = _load_defaults(registry)
    effective_auto_install = defaults.auto_install if auto_install is None else bool(auto_install)
    effective_log = Path(log_path) if log_path is not None else Path(defaults.install_log_path)
    timeout = defaults.network_timeout_seconds
    spec = resolve_plugin(plugin_id, registry)

    t_start = time.monotonic()
    preinstall_version = _probe_version(spec, timeout=timeout)
    if preinstall_version and _meets_min(preinstall_version, spec.min_version):
        return _handle_already_installed_path(
            spec,
            preinstall_version,
            log_path=effective_log,
            timeout=timeout,
            t_start=t_start,
        )

    if not effective_auto_install:
        _append_log(
            effective_log,
            "plugin_install_blocked_by_config",
            spec.id,
            {
                "preinstall_version": preinstall_version,
                "min_version": spec.min_version,
                "backend": spec.backend,
            },
        )
        raise PluginVersionMismatch(
            f"Plugin {spec.id!r} missing or below min_version={spec.min_version} "
            f"(observed={preinstall_version!r}) and auto_install=False.",
            details={
                "plugin_id": spec.id,
                "preinstall_version": preinstall_version,
                "min_version": spec.min_version,
            },
        )

    return _handle_install_path(
        spec,
        defaults,
        log_path=effective_log,
        timeout=timeout,
        t_start=t_start,
    )


def _handle_already_installed_path(
    spec: RuntimePluginSpec,
    preinstall_version: str,
    *,
    log_path: Path | None,
    timeout: int,
    t_start: float,
) -> str:
    """Cache-hit arm of :func:`ensure_plugin`: log + return.

    Extracted from :func:`ensure_plugin` in v10.6.0 PV-01 (D-Q-1 row
    #5). Only invoked when ``preinstall_version`` is non-empty AND
    meets ``spec.min_version`` — at that point the binary on PATH is
    accepted as the install. The distinguish-check still runs (for
    Success surfaces ``plugin_already_installed`` plus the same INFO log line
    as the v10.5.x baseline.
    """
    logger.info(
        "plugin_already_installed: %s at version %s (>= %s)",
        spec.id,
        preinstall_version,
        spec.min_version,
    )
    _append_log(
        log_path,
        "plugin_already_installed",
        spec.id,
        {
            "version": preinstall_version,
            "min_version": spec.min_version,
            "backend": spec.backend,
            "elapsed_s": round(time.monotonic() - t_start, 3),
        },
    )
    return preinstall_version


def _handle_install_path(
    spec: RuntimePluginSpec,
    defaults: RegistryDefaults,
    *,
    log_path: Path | None,
    timeout: int,
    t_start: float,
) -> str:
    """Network-fetch arm of :func:`ensure_plugin`: backend + verify + log.

    Extracted from :func:`ensure_plugin` in v10.6.0 PV-01 (D-Q-1 row
    #5). Sequence:

    1. Backend dispatch (``pip`` / ``npm_then_init`` /
       ``curl_install_script``); failure logs
       ``plugin_install_failed`` and re-raises.
    2. Re-probe version; ``None`` logs
       ``plugin_install_post_version_unparseable`` and raises
       :class:`PluginInstallError`. Below-floor logs
       ``plugin_install_version_mismatch`` and raises
       :class:`PluginVersionMismatch`.
    3. Run SHA-256 verify; failure (currently best-effort heuristic)
       on a pip-backend triggers a best-effort pip uninstall, logs
       ``plugin_install_sha_mismatch``, and re-raises.
    5. Log ``plugin_installed`` + INFO line + return version.

    All 8 named log events are PRESERVED VERBATIM per the D-Q-1 §9
    risk register row #3 contract — downstream operator tooling
    grep-pinned to these event names continues to see byte-identical
    JSONL output.
    """
    try:
        if spec.backend == "pip":
            _install_via_pip(
                spec,
                timeout=timeout,
                prefer_local_fallback=defaults.prefer_local_fallback,
            )
        elif spec.backend == "npm_then_init":
            _install_via_npm_then_init(spec, timeout=timeout)
        else:
            raise PluginBackendUnsupported(
                f"Plugin {spec.id!r} backend {spec.backend!r} not supported.",
                details={"plugin_id": spec.id, "backend": spec.backend},
            )
    except PluginInstallError as exc:
        _append_log(
            log_path,
            "plugin_install_failed",
            spec.id,
            {"backend": spec.backend, "details": exc.details},
        )
        raise

    postinstall_version = _probe_version(spec, timeout=timeout)
    if postinstall_version is None:
        _append_log(
            log_path,
            "plugin_install_post_version_unparseable",
            spec.id,
            {"backend": spec.backend, "min_version": spec.min_version},
        )
        raise PluginInstallError(
            f"Plugin {spec.id!r} installed but version_check_cmd "
            f"({spec.version_check_cmd!r}) did not return a parseable version.",
            details={"plugin_id": spec.id, "backend": spec.backend},
        )

    if not _meets_min(postinstall_version, spec.min_version):
        _append_log(
            log_path,
            "plugin_install_version_mismatch",
            spec.id,
            {
                "postinstall_version": postinstall_version,
                "min_version": spec.min_version,
                "backend": spec.backend,
            },
        )
        raise PluginVersionMismatch(
            f"Plugin {spec.id!r} installed at {postinstall_version} but "
            f"min_version is {spec.min_version}.",
            details={
                "plugin_id": spec.id,
                "postinstall_version": postinstall_version,
                "min_version": spec.min_version,
            },
        )

    try:
        _verify_sha256(spec)
    except PluginInstallError:
        if spec.backend == "pip":
            _attempt_pip_uninstall(spec, timeout=timeout)
        _append_log(
            log_path,
            "plugin_install_sha_mismatch",
            spec.id,
            {
                "postinstall_version": postinstall_version,
                "expected_sha256": spec.expected_sha256,
            },
        )
        raise

    _append_log(
        log_path,
        "plugin_installed",
        spec.id,
        {
            "version": postinstall_version,
            "min_version": spec.min_version,
            "backend": spec.backend,
            "elapsed_s": round(time.monotonic() - t_start, 3),
        },
    )
    logger.info(
        "plugin_installed: %s at version %s (backend=%s)",
        spec.id,
        postinstall_version,
        spec.backend,
    )
    return postinstall_version


def _attempt_pip_uninstall(spec: RuntimePluginSpec, *, timeout: int) -> None:
    """Best-effort uninstall on sha mismatch (design.md §6.5 row 7).

    Logged explicitly on failure — per S-5 we do not silently eat the error,
    but we also do not mask the caller's :class:`PluginInstallError`.
    """
    if not shutil.which("pip"):
        logger.warning("pip not on PATH; cannot uninstall %s after sha mismatch", spec.id)
        return
    cmd = f"pip uninstall -y {spec.package}"
    try:
        proc = _run_cmd(cmd, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("pip uninstall failed for %s: %s", spec.id, exc)
        return
    if proc.returncode != 0:
        logger.warning(
            "pip uninstall returned %d for %s: %s",
            proc.returncode,
            spec.id,
            proc.stderr[:200],
        )


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
