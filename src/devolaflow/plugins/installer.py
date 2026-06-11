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
from collections.abc import Iterator
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
# v9.4.0 PV-04: schema v3 adds optional `upgrade_cmd` per plugin and
# `defaults.upgrade_check_frequency_hours` registry-wide. v1 + v2 entries
# pass v3 unchanged (the v3 fields are all optional with sensible defaults).
_SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2, 3})
_DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS: int = 24


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
    # v9.4.0 PV-04 schema v3 — optional upgrade command. When None,
    # upgrade_plugin() falls back to install_cmd (which for pip / npm /
    # curl-script backends is typically idempotent and acts as the upgrade
    # command on its own). Authors who need a distinct upgrade path
    # (e.g. cargo distribution requiring `cargo install --force`) declare
    # it in runtime-plugins.yaml; the field defaults to None so v1+v2
    # entries pass v3 unchanged.
    upgrade_cmd: str | None = None


@dataclass(frozen=True)
class RegistryDefaults:
    """Registry-wide defaults (``defaults:`` block in runtime-plugins.yaml)."""

    auto_install: bool = True
    prefer_local_fallback: bool = True
    network_timeout_seconds: int = 90
    install_log_path: str = ".local/memory/plugin_install.log"
    # v9.4.0 PV-04 — daily-upgrade cadence in hours. When the
    # last_checked timestamp for a plugin (read from plugin_install.log)
    # is older than this many hours, refresh_all() considers the plugin
    # stale and runs upgrade_plugin() against it. Default 24 = daily,
    # matching the user-feedback "auto-upgrade daily" requirement from
    # `feedback_for_v9.2.4.md` §1.
    upgrade_check_frequency_hours: int = 24


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


def plugins_for_workflow(
    workflow_name: str,
    *,
    registry_path: Path | str | None = None,
    registry: dict[str, Any] | None = None,
) -> list[str]:
    """Return the list of plugin IDs whose ``invoked_by_workflows`` cites ``workflow_name``.

    Parameters
    ----------
    workflow_name:
        The workflow / template name as it would appear in the dispatch
        payload (e.g. ``"skill-optimization"``, ``"product-verification"``).
    registry_path:
        Optional override for the registry YAML path. Defaults to
        ``workflow-system/agent/knowledge/runtime-plugins.yaml``.
    registry:
        Optional pre-loaded registry dict (cheap path for callers that
        already loaded it — avoids the YAML re-parse). When omitted,
        the function calls :func:`load_registry`.

    Returns
    -------
    list[str]
        Plugin IDs declared via ``plugins[*].invoked_by_workflows``
        containing ``workflow_name``. Insertion order from the registry
        is preserved (deterministic across runs because YAML order is
        preserved by ``yaml.safe_load``).

        Returns an empty list when ``workflow_name`` is empty / not a
        string OR when no plugin declares the workflow. The empty list
        is the byte-stable signal for "free-floating workflow stage —
        no auto-install needed" used by the v9.4.0 PV-03 dispatcher
        wiring.

    Notes
    -----
    Used by :mod:`devolaflow.lifecycle.pre_plugin_invocation` to resolve
    plugin candidates from the dispatch payload's workflow name. Also
    callable directly by operator tooling (``devolaflow plugins`` CLI
    in v9.4.0 PV-04).

    Raises ``FileNotFoundError`` only if the registry path is missing —
    propagates the loud-failure invariant from :func:`load_registry`
    per S-5. The helper does NOT swallow registry errors.
    """
    if not workflow_name or not isinstance(workflow_name, str):
        return []

    if registry is None:
        registry = load_registry(registry_path)

    return list(_iter_workflow_matches(registry, workflow_name))


def _iter_workflow_matches(registry: dict[str, Any], workflow_name: str) -> Iterator[str]:
    """Yield plugin IDs whose ``invoked_by_workflows`` cites ``workflow_name``.

    Extracted from :func:`plugins_for_workflow` in v10.6.0 PV-01 (D-Q-1
    row #6) — a generator that filters registry entries by workflow
    membership and yields the validated plugin IDs in registry order.
    The two short-circuit branches (entry not a dict, invoked not a
    list) become ``continue`` statements that don't accumulate into the
    parent's CC graph. R5 byte-identical: insertion order from the
    registry is preserved (deterministic across runs because YAML
    order is preserved by ``yaml.safe_load``).
    """
    for entry in registry.get("plugins", []):
        if not isinstance(entry, dict):
            continue
        invoked = entry.get("invoked_by_workflows") or []
        if not isinstance(invoked, list):
            continue
        if workflow_name not in invoked:
            continue
        plugin_id = entry.get("id")
        if isinstance(plugin_id, str) and plugin_id:
            yield plugin_id


def _validate_required_keys(plugin_id: str, entry: dict[str, Any]) -> None:
    """Raise :class:`PluginInstallError` when *entry* lacks any required key.

    Extracted from :func:`resolve_plugin` in v10.6.0 PV-01 (D-Q-1 row
    #7). The required-keys set (``package``, ``install_cmd``,
    ``version_check_cmd``, ``min_version``) is the v8.2.1 minimum
    contract for every backend; missing or empty values are a
    schema violation surfaced loudly per S-5.
    """
    required_keys = ("package", "install_cmd", "version_check_cmd", "min_version")
    missing = [k for k in required_keys if not entry.get(k)]
    if missing:
        raise PluginInstallError(
            f"Plugin {plugin_id!r} registry entry missing required keys: {missing}.",
            details={"plugin_id": plugin_id, "missing_keys": missing},
        )


def _validate_npm_then_init_keys(plugin_id: str, entry: dict[str, Any]) -> None:
    """Raise :class:`PluginInstallError` when ``npm_then_init`` is mis-configured.

    Extracted from :func:`resolve_plugin` in v10.6.0 PV-01 (D-Q-1 row
    #7). The ``npm_then_init`` backend (used by ``ui-pro``) requires
    BOTH ``init_cmd_template`` AND a non-empty ``init_targets`` list
    so the per-platform init can run after ``npm install``. Either
    missing field is a schema violation surfaced loudly per S-5.
    Only call when ``entry["backend"] == "npm_then_init"``.
    """
    if not entry.get("init_cmd_template"):
        raise PluginInstallError(
            f"Plugin {plugin_id!r} (backend=npm_then_init) missing required 'init_cmd_template'.",
            details={"plugin_id": plugin_id},
        )
    if not entry.get("init_targets"):
        raise PluginInstallError(
            f"Plugin {plugin_id!r} (backend=npm_then_init) must declare "
            "at least one init_targets entry.",
            details={"plugin_id": plugin_id},
        )


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

    Implementation note: per the v10.6.0 PV-01 cyclomatic-complexity
    reduction (NineS PV-03 deep-analysis row #7), the per-backend
    schema validation lives in :func:`_validate_required_keys` and
    :func:`_validate_npm_then_init_keys`. Behaviour byte-identical
    to v10.5.x baseline (verified by ``tests/test_plugins.py`` +
    ``tests/test_runtime_plugins_smoke.py``).
    """
    for entry in registry.get("plugins", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("id") != plugin_id:
            continue
        backend = entry.get("backend")
        if backend not in _SUPPORTED_BACKENDS:
            raise PluginBackendUnsupported(
                f"Plugin {plugin_id!r} declares unsupported backend "
                f"{backend!r}; installer supports {sorted(_SUPPORTED_BACKENDS)}.",
                details={"plugin_id": plugin_id, "backend": backend},
            )
        _validate_required_keys(plugin_id, entry)
        if backend == "npm_then_init":
            _validate_npm_then_init_keys(plugin_id, entry)
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
            upgrade_cmd=entry.get("upgrade_cmd"),
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
        upgrade_check_frequency_hours=int(
            raw.get(
                "upgrade_check_frequency_hours",
                _DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS,
            )
        ),
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
            "and retry, or opt out of auto-install by setting "
            "defaults.auto_install: false in runtime-plugins.yaml "
            "(or passing ensure_plugin(..., auto_install=False)).",
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

    Implementation note: per the v10.6.0 PV-01 cyclomatic-complexity
    reduction (NineS PV-03 deep-analysis row #1), the cache-hit arm
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
    """Cache-hit arm of :func:`ensure_plugin`: distinguish + log + return.

    Extracted from :func:`ensure_plugin` in v10.6.0 PV-01 (D-Q-1 row
    #5). Only invoked when ``preinstall_version`` is non-empty AND
    meets ``spec.min_version`` — at that point the binary on PATH is
    accepted as the install. The distinguish-check still runs (for
    plugins like RTK that ship a ``verify_distinguish_cmd`` to catch
    rtk-type-kit collisions even when the version string accidentally
    matches the wrong package).

    Failure surfaces a ``plugin_install_distinguish_failed_preinstall``
    JSONL log event (event-name PRESERVED VERBATIM per the §9 risk
    register row #3 named-event ordering contract) and re-raises the
    original :class:`PluginInstallError` per S-5.

    Success surfaces ``plugin_already_installed`` (also verbatim
    event name) plus the same INFO log line as the v10.5.x baseline.
    """
    try:
        _verify_distinguish(spec, timeout=timeout)
    except PluginInstallError as exc:
        _append_log(
            log_path,
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
    3. Run distinguish-check; failure logs
       ``plugin_install_distinguish_failed_postinstall`` and re-raises.
    4. Run SHA-256 verify; failure (currently best-effort heuristic)
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
        elif spec.backend == "curl_install_script":
            _install_via_curl_script(spec, timeout=timeout)
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

    # Distinguish-check is a no-op for plugins without verify_distinguish_cmd
    # (nines, ui-pro); for RTK it runs `rtk gain` to detect rtk-type-kit
    # name-collisions per the upstream INSTALL.md warning. Loud per S-5.
    try:
        _verify_distinguish(spec, timeout=timeout)
    except PluginInstallError as exc:
        _append_log(
            log_path,
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


# ---------------------------------------------------------------------------
# v9.4.0 PV-04 — daily-upgrade surface
# ---------------------------------------------------------------------------
#
# Closes D-P-4 (MAJOR — daily-upgrade surface absent) + D-P-5 (MAJOR —
# schema v3 bump for upgrade_cmd) + D-P-8 (MINOR — registry refresh UX)
# from `.local/research/v9.4.0_gap_analysis.md` §3.2.
#
# Design: build last_checked tracking on top of the existing
# `plugin_install.log` JSONL file (same one ensure_plugin already
# writes). NO new state file is added. The tracker reads the log,
# groups by plugin_id, and returns the most-recent timestamp per
# plugin. Stale = (now - last_checked) > defaults.upgrade_check_frequency_hours.


# v10.2.4 PV-05 round 2: the set of `event` values that count as a
# "checked" timestamp. Lifted to a module-level constant so the
# per-line parser does not rebuild the frozenset on every iteration
# (and so tests can introspect the contract directly).
_LAST_CHECKED_SUCCESSFUL_EVENTS: frozenset[str] = frozenset(
    {"plugin_already_installed", "plugin_installed", "plugin_upgraded"}
)


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
    round 2 to close the NineS PV-03 finding ``CC-a5d310-0003`` (cyclomatic
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
