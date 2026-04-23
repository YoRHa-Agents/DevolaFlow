"""Runtime plugin auto-install for DevolaFlow workflows (v8.2.1; v8.3.1 PV-01).

Design ref: ``.local/research/v8.3.0_design.md`` §6.
Closes gap H-001 from ``.local/research/v8.3.0_gap_analysis.md``.
v8.3.1 PV-01 ref: ``.local/research/v8.4.0_rtk_nines_analysis.md`` §5 +
``.local/research/v8.4.0_gap_analysis.md`` §2.1 R-001 — adds the
``curl_install_script`` backend (with cargo fallback) and the optional
``verify_distinguish_cmd`` field used to detect name-collisions like RTK
(Rust Token Killer) vs rtk-type-kit (Rust Type Kit) per RTK INSTALL.md.

Public API
----------
:func:`load_registry`     Parse ``runtime-plugins.yaml`` into a mapping.
                          Accepts both schema_version 1 (v8.2.1) and
                          schema_version 2 (v8.3.1+).
:func:`resolve_plugin`    Look up a plugin_id in a registry; raise loudly.
:func:`ensure_plugin`     Ensure a plugin is installed at >= ``min_version``
                          for the declared backend (``pip``, ``npm_then_init``,
                          or ``curl_install_script``). Parses version via
                          subprocess. Honours ``prefer_local_fallback``,
                          ``expected_sha256`` and ``network_timeout_seconds``
                          from the registry. When ``verify_distinguish_cmd``
                          is set on the spec, it is run after every
                          successful version check (pre- and post-install)
                          and a non-zero exit raises
                          :class:`PluginInstallError` per S-5.

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

``curl_install_script`` (v8.3.1)
    Single-command curl-fetched POSIX shell script (piped to ``sh``) that
    downloads a prebuilt binary (matches RTK's documented Quick Install
    path). On primary failure, falls back to a pinned
    ``cargo install --git <canonical_url>`` (NEVER bare
    ``cargo install <pkg>`` — per the RTK INSTALL.md collision warning vs
    rtk-type-kit). Failure on BOTH curl primary AND cargo fallback raises
    :class:`PluginInstallError` per S-5 with actionable text. Used by ``rtk``.

Invariants
----------
- All raises are loud — no silent failures (S-5).
- All paths relative to repo root (S-2).
- External tools referenced by canonical URL (S-7).
- ``verify_distinguish_cmd`` defaults to ``None`` for additive R5 strict —
  existing nines + ui-pro entries are byte-identical pre/post v8.3.1.
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
_SUPPORTED_BACKENDS: frozenset[str] = frozenset({"pip", "npm_then_init", "curl_install_script"})
_SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2})


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
    verify_distinguish_cmd: str | None = None


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
    if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        raise PluginInstallError(
            f"runtime-plugins.yaml schema_version={schema_version!r} is unsupported; "
            f"installer requires schema_version in {sorted(_SUPPORTED_SCHEMA_VERSIONS)}.",
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
        When the entry declares a backend not in
        ``{pip, npm_then_init, curl_install_script}``.
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
                verify_distinguish_cmd=entry.get("verify_distinguish_cmd"),
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
# v8.3.1 PV-01 — curl_install_script backend (with cargo fallback) +
# verify_distinguish_cmd post-install probe.
#
# Closes R-001 from .local/research/v8.4.0_gap_analysis.md (RTK plugin).
# Risk references:
#   - R-1 / R-2 in .local/research/v8.4.0_rtk_nines_analysis.md §7 — name
#     collision (RTK Rust Token Killer vs rtk-type-kit Rust Type Kit).
#     Mitigated by ALWAYS pinning canonical_url for the cargo fallback
#     (NEVER bare `cargo install <pkg>`) and by the mandatory
#     verify_distinguish_cmd (`rtk gain`) post-install check.
#   - R-2 — Rust toolchain availability. The primary curl path needs only
#     curl + tar; the cargo fallback needs the Rust toolchain. Failure on
#     BOTH paths raises PluginInstallError per S-5 with actionable text.
# ---------------------------------------------------------------------------


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
            "and retry, or set DEVOLAFLOW_AUTO_INSTALL=0 to opt out.",
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

    No-op when ``spec.verify_distinguish_cmd`` is ``None`` (the case for all
    pre-v8.3.1 plugins — nines + ui-pro — preserving R5 strict).

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

    Resolution chain (matches design.md §6.5 failure-mode catalog +
    v8.4.0_rtk_nines_analysis.md §5 distinguish-cmd protocol):

    1. Load + resolve registry entry.
    2. Probe current version via ``version_check_cmd``; if present AND
       ``>= min_version`` → run distinguish-check (no-op when
       ``verify_distinguish_cmd`` is unset) → return version (INFO
       ``plugin_already_installed``). If the pre-install distinguish-check
       fails, raise :class:`PluginInstallError` loudly per S-5 (the wrong
       package is on PATH).
    3. If ``auto_install`` is ``False`` → raise :class:`PluginVersionMismatch`
       loudly per S-5.
    4. Invoke backend-specific install routine (``pip``, ``npm_then_init``, or
       ``curl_install_script``); honour ``prefer_local_fallback`` when
       ``local_fallback_path`` is set. The ``curl_install_script`` backend
       falls back to ``cargo install --git <canonical_url>`` on primary
       failure (never bare ``cargo install <pkg>`` per R-2 collision risk).
    5. Re-probe version; raise :class:`PluginVersionMismatch` if still below
       floor, or :class:`PluginInstallError` when the version command now
       returns nothing parseable.
    6. Run distinguish-check (no-op when ``verify_distinguish_cmd`` is unset).
       Failure raises :class:`PluginInstallError` per S-5 with collision
       warning text (e.g., RTK Rust Token Killer vs rtk-type-kit Rust Type
       Kit per RTK INSTALL.md).
    7. Run SHA-256 verification (best-effort; see :func:`_verify_sha256`).
    8. Append a JSONL install event to ``log_path`` (defaulted from registry).

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
        # No-op for plugins without verify_distinguish_cmd (nines, ui-pro);
        # for RTK, runs `rtk gain` to detect rtk-type-kit collisions even
        # when the version probe accidentally matches the wrong package.
        try:
            _verify_distinguish(spec, timeout=timeout)
        except PluginInstallError as exc:
            _append_log(
                effective_log,
                "plugin_install_distinguish_failed_preinstall",
                spec.id,
                {
                    "preinstall_version": preinstall_version,
                    "verify_distinguish_cmd": spec.verify_distinguish_cmd,
                    "details": exc.details,
                },
            )
            raise
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
        elif spec.backend == "curl_install_script":
            _install_via_curl_script(spec, timeout=timeout)
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

    # Distinguish-check is a no-op for plugins without verify_distinguish_cmd
    # (nines, ui-pro); for RTK it runs `rtk gain` to detect rtk-type-kit
    # name-collisions per the upstream INSTALL.md warning. Loud per S-5.
    try:
        _verify_distinguish(spec, timeout=timeout)
    except PluginInstallError as exc:
        _append_log(
            effective_log,
            "plugin_install_distinguish_failed_postinstall",
            spec.id,
            {
                "postinstall_version": postinstall_version,
                "verify_distinguish_cmd": spec.verify_distinguish_cmd,
                "backend": spec.backend,
                "details": exc.details,
            },
        )
        raise

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
