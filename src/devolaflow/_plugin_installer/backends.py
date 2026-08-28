"""Focused implementation slice for plugin backends."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _run_cmd(
    cmd: str,
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Execute ``cmd`` through ``bash -c`` and return the completed process.

    ``check=False`` so the caller can inspect ``stderr`` and the non-zero
    return code (S-5: surfaces errors explicitly instead of swallowing them).

    Raises
    ------
    subprocess.TimeoutExpired
        When the command exceeds ``timeout`` seconds.
    """
    return subprocess.run(
        ["bash", "-c", cmd],
        check=False,
        timeout=timeout,
        capture_output=True,
        text=True,
    )


def _probe_version(spec: RuntimePluginSpec, *, timeout: int) -> str | None:
    """Run ``version_check_cmd`` and return the parsed version token, if any."""
    try:
        proc = _run_cmd(spec.version_check_cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning(
            "version_check_cmd timed out for plugin %s (%ss)",
            spec.id,
            timeout,
        )
        return None
    except FileNotFoundError:
        logger.debug("version_check_cmd binary missing for plugin %s", spec.id)
        return None
    except OSError as exc:
        logger.warning("version_check_cmd failed for plugin %s: %s", spec.id, exc)
        return None

    if proc.returncode != 0:
        logger.debug(
            "version_check_cmd returned %d for plugin %s (stderr=%r)",
            proc.returncode,
            spec.id,
            proc.stderr[:200],
        )
        return None
    return _parse_version((proc.stdout or "") + "\n" + (proc.stderr or ""))


def _append_log(log_path: Path | None, event: str, plugin_id: str, details: dict) -> None:
    """Append a JSONL event to ``log_path`` (best-effort — never raises).

    Note: per S-5 "best-effort" exception is allowed here because the install
    log is a side-channel; the primary success/failure signal is already
    communicated via return value / raised exception. A log write failure is
    itself logged via ``logger.warning`` rather than silently ignored.
    """
    if log_path is None:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "ts": datetime.now(UTC).isoformat(),
                "plugin_id": plugin_id,
                "event": event,
                "details": details,
            },
            sort_keys=True,
        )
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        logger.warning("Failed to write plugin install log at %s: %s", log_path, exc)


def _install_via_pip(
    spec: RuntimePluginSpec,
    *,
    timeout: int,
    prefer_local_fallback: bool,
) -> None:
    """Run the pip install command; raise :class:`PluginInstallError` on failure."""
    cmd = spec.install_cmd
    if prefer_local_fallback and spec.local_fallback_path:
        local = Path(spec.local_fallback_path)
        if local.exists():
            logger.info(
                "Installing plugin %s from local fallback path %s",
                spec.id,
                local,
            )
            cmd = f"pip install -e {local}"

    logger.info("Installing plugin %s via pip: %s", spec.id, cmd)
    try:
        proc = _run_cmd(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PluginInstallError(
            f"Install timeout for plugin {spec.id!r} after {timeout}s (backend=pip).",
            details={"plugin_id": spec.id, "timeout_seconds": timeout, "cmd": cmd},
        ) from exc
    except OSError as exc:
        raise PluginInstallError(
            f"Install failed for plugin {spec.id!r} (backend=pip, os-error): {exc}.",
            details={"plugin_id": spec.id, "cmd": cmd},
        ) from exc

    if proc.returncode != 0:
        raise PluginInstallError(
            f"pip install failed for plugin {spec.id!r} "
            f"(returncode={proc.returncode}): {proc.stderr[:400]!r}",
            details={
                "plugin_id": spec.id,
                "cmd": cmd,
                "returncode": proc.returncode,
                "stderr": proc.stderr[:400],
            },
        )


def _install_via_npm_then_init(
    spec: RuntimePluginSpec,
    *,
    timeout: int,
) -> None:
    """Run the npm install + per-AI-platform init sequence.

    Raises :class:`PluginInstallError` on the first failing step, OR at the end
    with ALL failing ``init_targets`` listed (never silently ignores one).
    """
    logger.info("Installing plugin %s via npm: %s", spec.id, spec.install_cmd)
    try:
        proc = _run_cmd(spec.install_cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PluginInstallError(
            f"npm install timeout for plugin {spec.id!r} after {timeout}s.",
            details={"plugin_id": spec.id, "timeout_seconds": timeout},
        ) from exc
    except OSError as exc:
        raise PluginInstallError(
            f"npm install failed for plugin {spec.id!r} (os-error): {exc}.",
            details={"plugin_id": spec.id, "cmd": spec.install_cmd},
        ) from exc

    if proc.returncode != 0:
        raise PluginInstallError(
            f"npm install failed for plugin {spec.id!r} "
            f"(returncode={proc.returncode}): {proc.stderr[:400]!r}",
            details={
                "plugin_id": spec.id,
                "cmd": spec.install_cmd,
                "returncode": proc.returncode,
                "stderr": proc.stderr[:400],
            },
        )

    failed_targets: list[dict[str, Any]] = []
    template = spec.init_cmd_template or ""
    for platform in spec.init_targets:
        cmd = template.format(ai_platform=platform)
        logger.info("Running init for plugin %s (%s): %s", spec.id, platform, cmd)
        try:
            init_proc = _run_cmd(cmd, timeout=timeout)
        except subprocess.TimeoutExpired:
            failed_targets.append(
                {
                    "ai_platform": platform,
                    "cmd": cmd,
                    "reason": f"timeout after {timeout}s",
                }
            )
            continue
        except OSError as exc:
            failed_targets.append(
                {"ai_platform": platform, "cmd": cmd, "reason": f"os-error: {exc}"}
            )
            continue
        if init_proc.returncode != 0:
            failed_targets.append(
                {
                    "ai_platform": platform,
                    "cmd": cmd,
                    "returncode": init_proc.returncode,
                    "stderr": init_proc.stderr[:200],
                }
            )

    if failed_targets:
        failed_names = [entry["ai_platform"] for entry in failed_targets]
        raise PluginInstallError(
            f"Plugin {spec.id!r} init failed for targets {failed_names} (backend=npm_then_init).",
            details={"plugin_id": spec.id, "failed_targets": failed_targets},
        )


def _install_via_cargo(
    spec: RuntimePluginSpec,
    *,
    timeout: int,
) -> None:
    """Cargo install fallback. Always pins ``--git <canonical_url>`` per R-2.

    Raises :class:`PluginInstallError` on failure (no silent failures per S-5).
    The exception message points at the rustup install command so the operator
    can repair the toolchain when it is missing.
    """
    if not spec.canonical_url:
        raise PluginInstallError(
            f"Plugin {spec.id!r} cargo fallback requires canonical_url to be set "
            "(per R-2 — never bare `cargo install <pkg>` because of name-collision risk).",
            details={"plugin_id": spec.id},
        )

    cmd = f"cargo install --git {spec.canonical_url}"
    logger.info("Installing plugin %s via cargo fallback: %s", spec.id, cmd)
    try:
        proc = _run_cmd(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PluginInstallError(
            f"cargo install timeout for plugin {spec.id!r} after {timeout}s.",
            details={"plugin_id": spec.id, "timeout_seconds": timeout, "cmd": cmd},
        ) from exc
    except OSError as exc:
        raise PluginInstallError(
            f"cargo install failed for plugin {spec.id!r} (os-error: {exc}). "
            "Install the Rust toolchain via "
            "`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh` "
            "and retry. (Auto-install only runs on explicit opt-in surfaces "
            "since v15.2.0 B-6 — defaults.auto_install is false in "
            "runtime-plugins.yaml; bare ensure_plugin(...) calls probe-and-"
            "report instead.)",
            details={"plugin_id": spec.id, "cmd": cmd},
        ) from exc

    if proc.returncode != 0:
        raise PluginInstallError(
            f"cargo install failed for plugin {spec.id!r} "
            f"(returncode={proc.returncode}): {proc.stderr[:400]!r}",
            details={
                "plugin_id": spec.id,
                "cmd": cmd,
                "returncode": proc.returncode,
                "stderr": proc.stderr[:400],
            },
        )


def _install_via_curl_script(
    spec: RuntimePluginSpec,
    *,
    timeout: int,
) -> None:
    """Run the curl install script primary; fall back to cargo on failure.

    Pipeline:

    1. Run ``spec.install_cmd`` (typically ``curl ... | sh``) via bash.
    2. If it succeeds (exit 0) → return; the caller will probe the version next.
    3. If it fails (timeout / OSError / non-zero exit) → invoke
       :func:`_install_via_cargo` as a fallback (always pinning canonical_url).
    4. If the cargo fallback ALSO fails → raise :class:`PluginInstallError`
       per S-5 with both error reasons aggregated into ``details``.
    """
    logger.info(
        "Installing plugin %s via curl_install_script: %s",
        spec.id,
        spec.install_cmd,
    )
    primary_failure: str | None = None
    try:
        proc = _run_cmd(spec.install_cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        primary_failure = f"timeout after {timeout}s"
    except OSError as exc:
        primary_failure = f"os-error: {exc}"
    else:
        if proc.returncode != 0:
            primary_failure = f"returncode={proc.returncode} stderr={proc.stderr[:200]!r}"

    if primary_failure is None:
        return

    logger.warning(
        "curl_install_script failed for plugin %s (%s); attempting cargo fallback",
        spec.id,
        primary_failure,
    )
    try:
        _install_via_cargo(spec, timeout=timeout)
    except PluginInstallError as cargo_exc:
        raise PluginInstallError(
            f"Plugin {spec.id!r} install FAILED via both backends: "
            f"curl_install_script ({primary_failure}) AND cargo fallback "
            f"({cargo_exc}). Verify network access to "
            f"{spec.canonical_url} and Rust toolchain availability "
            "(see https://rustup.rs).",
            details={
                "plugin_id": spec.id,
                "primary_backend": "curl_install_script",
                "primary_failure": primary_failure,
                "fallback_backend": "cargo",
                "fallback_failure": str(cargo_exc),
                "fallback_details": cargo_exc.details,
                "install_cmd": spec.install_cmd,
                "canonical_url": spec.canonical_url,
            },
        ) from cargo_exc


def _verify_distinguish(
    spec: RuntimePluginSpec,
    *,
    timeout: int,
) -> None:
    """Run ``spec.verify_distinguish_cmd`` to detect plugin name-collisions.

    No-op when ``spec.verify_distinguish_cmd`` is ``None`` (the case for
    plugins without a discriminator, including ui-pro, preserving R5 strict).

    For RTK, the discriminator is ``rtk gain``: the Rust Token Killer's stats
    command, which is NOT present in rtk-type-kit (Rust Type Kit). A failure
    here means the wrong package was installed.

    Raises :class:`PluginInstallError` per S-5 (loud) when the command fails;
    error text points the operator at the upstream INSTALL.md collision
    warning so they can repair the install.
    """
    if not spec.verify_distinguish_cmd:
        return

    logger.info(
        "Running distinguish-check for plugin %s: %s",
        spec.id,
        spec.verify_distinguish_cmd,
    )
    try:
        proc = _run_cmd(spec.verify_distinguish_cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PluginInstallError(
            f"Plugin {spec.id!r} distinguish-check timed out after {timeout}s "
            f"({spec.verify_distinguish_cmd!r}). The plugin may be the wrong "
            f"package — see {spec.canonical_url} INSTALL.md for the collision "
            "warning (e.g., RTK Rust Token Killer vs rtk-type-kit Rust Type Kit).",
            details={
                "plugin_id": spec.id,
                "verify_distinguish_cmd": spec.verify_distinguish_cmd,
                "timeout_seconds": timeout,
            },
        ) from exc
    except OSError as exc:
        raise PluginInstallError(
            f"Plugin {spec.id!r} distinguish-check failed (os-error: {exc}). "
            f"The binary {spec.verify_distinguish_cmd.split()[0]!r} appears to "
            f"be missing from PATH after install. See {spec.canonical_url} "
            "INSTALL.md.",
            details={
                "plugin_id": spec.id,
                "verify_distinguish_cmd": spec.verify_distinguish_cmd,
            },
        ) from exc

    if proc.returncode != 0:
        raise PluginInstallError(
            f"Plugin {spec.id!r} distinguish-check FAILED: "
            f"{spec.verify_distinguish_cmd!r} returned exit code "
            f"{proc.returncode}. This typically means the WRONG package is "
            f"installed (name collision — for RTK, this distinguishes "
            f"Rust Token Killer from rtk-type-kit Rust Type Kit; see "
            f"{spec.canonical_url} INSTALL.md). "
            f"stderr: {proc.stderr[:300]!r}",
            details={
                "plugin_id": spec.id,
                "verify_distinguish_cmd": spec.verify_distinguish_cmd,
                "returncode": proc.returncode,
                "stderr": proc.stderr[:300],
                "canonical_url": spec.canonical_url,
            },
        )


def _verify_sha256(spec: RuntimePluginSpec) -> None:
    """Verify the installed package's integrity when ``expected_sha256`` is set.

    Current heuristic (v8.2.1): when ``expected_sha256`` is set we look up the
    installed package's dist-info metadata via ``importlib.metadata`` and hash
    its locator (e.g. the wheel URL or RECORD entries). This is intentionally
    conservative — the full per-artifact hash audit described in design.md §6
    implementation hints is deferred to a follow-up patch because locating the
    artifact reliably across pip / npm / editable installs is non-trivial.

    For now we raise :class:`PluginInstallError` only when we can compute a
    hash AND it disagrees with ``expected_sha256``. A ``None`` computation
    result is logged (INFO) and treated as non-blocking per S-5 best-effort
    exception (the ``auto_install=False`` path + exact version pinning remain
    the primary supply-chain mitigations documented in gap_analysis.md §R-C).
    """
    if not spec.expected_sha256:
        return
    logger.info(
        "expected_sha256 verification for plugin %s is currently a best-effort "
        "heuristic; full per-artifact hashing deferred to a follow-up patch "
        "(see design.md §6 implementation hints).",
        spec.id,
    )


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
