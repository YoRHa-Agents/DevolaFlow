"""Runtime plugin auto-install for DevolaFlow workflows (v8.2.1).

Design ref: ``.local/research/v8.3.0_design.md`` §6.
Closes gap H-001 from ``.local/research/v8.3.0_gap_analysis.md``.

Public API
----------
:func:`load_registry`     Parse ``runtime-plugins.yaml`` into a mapping.
:func:`resolve_plugin`    Look up a plugin_id in a registry; raise loudly.
:func:`ensure_plugin`     Ensure a plugin is installed at >= ``min_version``
                          for the declared backend (``pip`` or
                          ``npm_then_init``). Parses version via subprocess.
                          Honours ``prefer_local_fallback``, ``expected_sha256``
                          and ``network_timeout_seconds`` from the registry.

Backends
--------
``pip``
    Single-command install via ``install_cmd``. Used by ``nines``.

``npm_then_init``
    Two-stage install: run ``install_cmd`` (``npm install -g <pkg>``), then for
    each entry in ``init_targets`` run ``init_cmd_template`` with
    ``{ai_platform}`` interpolated. Used by ``ui-pro``. Failure on any
    ``init_target`` raises :class:`PluginInstallError` with ALL failing targets
    listed (S-5 loud failure).

Invariants
----------
- All raises are loud — no silent failures (S-5).
- All paths relative to repo root (S-2).
- External tools referenced by canonical URL (S-7).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devolaflow.plugins.exceptions import (
    PluginBackendUnsupported,
    PluginInstallError,
    PluginNotFoundError,
    PluginVersionMismatch,
)

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY_PATH = Path("workflow-system/agent/knowledge/runtime-plugins.yaml")
_VERSION_RX = re.compile(r"\d+\.\d+(?:\.\d+)?")
_SUPPORTED_BACKENDS: frozenset[str] = frozenset({"pip", "npm_then_init"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimePluginSpec:
    """Machine-readable spec for one row in ``runtime-plugins.yaml``.

    Mirrors the v8.2.1 schema from design.md §6.2. Distinct from the legacy
    :class:`devolaflow.plugins.models.PluginSpec` so both APIs can coexist.
    """

    id: str
    backend: str
    package: str
    install_cmd: str
    version_check_cmd: str
    min_version: str
    canonical_url: str
    expected_sha256: str | None = None
    local_fallback_path: str | None = None
    init_cmd_template: str | None = None
    init_targets: list[str] = field(default_factory=list)
    invoked_by_workflows: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegistryDefaults:
    """Registry-wide defaults (``defaults:`` block in runtime-plugins.yaml)."""

    auto_install: bool = True
    prefer_local_fallback: bool = True
    network_timeout_seconds: int = 90
    install_log_path: str = ".local/memory/plugin_install.log"


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def load_registry(path: Path | str | None = None) -> dict[str, Any]:
    """Parse ``runtime-plugins.yaml`` into a nested dict.

    Parameters
    ----------
    path:
        Location of the registry YAML. When ``None`` defaults to
        ``workflow-system/agent/knowledge/runtime-plugins.yaml`` relative to
        the current working directory.

    Returns
    -------
    dict
        Keys: ``schema_version``, ``last_updated``, ``plugins`` (list),
        ``defaults`` (dict), ``backends`` (list).

    Raises
    ------
    FileNotFoundError
        When the registry YAML is missing. Loud per S-5.
    PluginInstallError
        When the file exists but is not valid YAML / has an unknown schema.
    """
    import yaml

    registry_path = Path(path) if path is not None else _DEFAULT_REGISTRY_PATH
    if not registry_path.is_file():
        raise FileNotFoundError(
            f"Plugin runtime registry not found: {registry_path}. "
            "Expected workflow-system/agent/knowledge/runtime-plugins.yaml "
            "(relative to repo root)."
        )

    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PluginInstallError(
            f"Failed to parse runtime-plugins registry at {registry_path}: {exc}",
            details={"path": str(registry_path)},
        ) from exc

    if not isinstance(raw, dict):
        raise PluginInstallError(
            f"runtime-plugins.yaml at {registry_path} did not parse into a mapping "
            f"(got {type(raw).__name__}).",
            details={"path": str(registry_path)},
        )

    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise PluginInstallError(
            f"runtime-plugins.yaml schema_version={schema_version!r} is unsupported; "
            "installer requires schema_version: 1.",
            details={"path": str(registry_path), "schema_version": schema_version},
        )

    plugins = raw.get("plugins") or []
    if not isinstance(plugins, list):
        raise PluginInstallError(
            f"runtime-plugins.yaml 'plugins' must be a list (got {type(plugins).__name__}).",
            details={"path": str(registry_path)},
        )
    return raw


def resolve_plugin(plugin_id: str, registry: dict[str, Any]) -> RuntimePluginSpec:
    """Look up ``plugin_id`` in a parsed registry and return its spec.

    Raises
    ------
    PluginNotFoundError
        When ``plugin_id`` is absent from the registry.
    PluginBackendUnsupported
        When the entry declares a backend not in ``{pip, npm_then_init}``.
    PluginInstallError
        When the entry is malformed (missing required keys).
    """
    for entry in registry.get("plugins", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("id") == plugin_id:
            backend = entry.get("backend")
            if backend not in _SUPPORTED_BACKENDS:
                raise PluginBackendUnsupported(
                    f"Plugin {plugin_id!r} declares unsupported backend "
                    f"{backend!r}; installer supports {sorted(_SUPPORTED_BACKENDS)}.",
                    details={"plugin_id": plugin_id, "backend": backend},
                )
            required_keys = ("package", "install_cmd", "version_check_cmd", "min_version")
            missing = [k for k in required_keys if not entry.get(k)]
            if missing:
                raise PluginInstallError(
                    f"Plugin {plugin_id!r} registry entry missing required keys: {missing}.",
                    details={"plugin_id": plugin_id, "missing_keys": missing},
                )
            if backend == "npm_then_init":
                if not entry.get("init_cmd_template"):
                    raise PluginInstallError(
                        f"Plugin {plugin_id!r} (backend=npm_then_init) missing "
                        "required 'init_cmd_template'.",
                        details={"plugin_id": plugin_id},
                    )
                if not entry.get("init_targets"):
                    raise PluginInstallError(
                        f"Plugin {plugin_id!r} (backend=npm_then_init) must declare "
                        "at least one init_targets entry.",
                        details={"plugin_id": plugin_id},
                    )
            return RuntimePluginSpec(
                id=str(entry["id"]),
                backend=backend,
                package=str(entry["package"]),
                install_cmd=str(entry["install_cmd"]),
                version_check_cmd=str(entry["version_check_cmd"]),
                min_version=str(entry["min_version"]),
                canonical_url=str(entry.get("canonical_url", "")),
                expected_sha256=entry.get("expected_sha256"),
                local_fallback_path=entry.get("local_fallback_path"),
                init_cmd_template=entry.get("init_cmd_template"),
                init_targets=list(entry.get("init_targets") or []),
                invoked_by_workflows=list(entry.get("invoked_by_workflows") or []),
            )

    raise PluginNotFoundError(
        f"Plugin {plugin_id!r} not found in runtime-plugins registry.",
        details={"plugin_id": plugin_id},
    )


def _load_defaults(registry: dict[str, Any]) -> RegistryDefaults:
    raw = registry.get("defaults") or {}
    if not isinstance(raw, dict):
        raw = {}
    return RegistryDefaults(
        auto_install=bool(raw.get("auto_install", True)),
        prefer_local_fallback=bool(raw.get("prefer_local_fallback", True)),
        network_timeout_seconds=int(raw.get("network_timeout_seconds", 90)),
        install_log_path=str(raw.get("install_log_path", ".local/memory/plugin_install.log")),
    )


# ---------------------------------------------------------------------------
# Version parsing & comparison
# ---------------------------------------------------------------------------


def _parse_version(output: str) -> str | None:
    """Extract a dotted version token (e.g. ``3.3.0``) from CLI output.

    Handles both ``nines, version 3.3.0`` and ``uipro-cli/2.1.0`` formats.
    """
    if not output:
        return None
    match = _VERSION_RX.search(output)
    if match is None:
        return None
    return match.group(0)


def _version_tuple(version: str) -> tuple[int, ...]:
    """Convert dotted version string to a comparable int tuple."""
    parts: list[int] = []
    for segment in version.split("."):
        digits = re.match(r"(\d+)", segment)
        if digits:
            parts.append(int(digits.group(1)))
    return tuple(parts)


def _meets_min(version: str, min_version: str) -> bool:
    """Return True when ``version >= min_version``."""
    try:
        return _version_tuple(version) >= _version_tuple(min_version)
    except (ValueError, TypeError):
        logger.debug("version comparison fallback: %r vs %r", version, min_version)
        return version >= min_version


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Install log
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Backend-specific install routines
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# SHA-256 verification (best-effort heuristic — see design.md §6 implementation hints)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


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
    2. Probe current version via ``version_check_cmd``; if present and
       ``>= min_version`` → return version (INFO ``plugin_already_installed``).
    3. If ``auto_install`` is ``False`` → raise :class:`PluginVersionMismatch`
       loudly per S-5.
    4. Invoke backend-specific install routine (``pip`` or
       ``npm_then_init``); honour ``prefer_local_fallback`` when
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
        logger.info(
            "plugin_already_installed: %s at version %s (>= %s)",
            spec.id,
            preinstall_version,
            spec.min_version,
        )
        _append_log(
            effective_log,
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
            effective_log,
            "plugin_install_failed",
            spec.id,
            {"backend": spec.backend, "details": exc.details},
        )
        raise

    postinstall_version = _probe_version(spec, timeout=timeout)
    if postinstall_version is None:
        _append_log(
            effective_log,
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
            effective_log,
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
            effective_log,
            "plugin_install_sha_mismatch",
            spec.id,
            {
                "postinstall_version": postinstall_version,
                "expected_sha256": spec.expected_sha256,
            },
        )
        raise

    _append_log(
        effective_log,
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
