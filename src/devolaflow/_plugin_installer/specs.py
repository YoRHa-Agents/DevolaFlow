"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


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
    # v15.2.0 B-6 schema v4 — dependency tier. ``suggest`` (default; absent
    # key on v1..v3 entries parses to this) = probe-and-degrade: consuming
    # surfaces MUST NOT hard-fail when the plugin is missing. ``require`` =
    # absence is a hard error at the consuming surface (mechanism kept; no
    # shipped occupant as of v15.2.0). Validated against _SUPPORTED_TIERS
    # in resolve_plugin.
    tier: str = "suggest"


@dataclass(frozen=True)
class RegistryDefaults:
    """Registry-wide defaults (``defaults:`` block in runtime-plugins.yaml).

    v15.2.0 B-6 (dependency suggestion-ization, 04 §8) flipped the
    ``auto_install`` default ``True`` → ``False``: a bare
    ``ensure_plugin(pid)`` call now PROBES and raises
    :class:`PluginVersionMismatch` on a missing plugin instead of
    network-installing. Every explicit opt-in surface passes
    ``auto_install=True`` at the call site (the
    ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` lifecycle hooks and the
    ``devola-init --global`` plugin bundling — the operator opted in at
    those surfaces already).
    """

    auto_install: bool = False
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
    reduction (historical analysis row #7), the per-backend
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
        tier = entry.get("tier", "suggest")
        if tier not in _SUPPORTED_TIERS:
            raise PluginInstallError(
                f"Plugin {plugin_id!r} declares invalid tier {tier!r}; "
                f"expected one of {sorted(_SUPPORTED_TIERS)}.",
                details={"plugin_id": plugin_id, "tier": tier},
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
            upgrade_cmd=entry.get("upgrade_cmd"),
            tier=str(tier),
        )

    raise PluginNotFoundError(
        f"Plugin {plugin_id!r} not found in runtime-plugins registry.",
        details={"plugin_id": plugin_id},
    )


def plugin_tier(plugin_id: str, *, registry_path: Path | str | None = None) -> str:
    """Return the declared tier for ``plugin_id`` (``require`` | ``suggest``).

    v15.2.0 B-6 — the tier lookup consumed by the lifecycle hooks to decide
    PPI001 severity (suggest-tier install failure degrades to a warning +
    one-time hint; require-tier stays an error). Raises exactly like
    :func:`load_registry` / :func:`resolve_plugin` on a missing registry or
    unknown plugin — callers on a failure path catch and fall back to
    ``require`` semantics (conservative).
    """
    return resolve_plugin(plugin_id, load_registry(registry_path)).tier


def _load_defaults(registry: dict[str, Any]) -> RegistryDefaults:
    raw = registry.get("defaults") or {}
    if not isinstance(raw, dict):
        raw = {}
    return RegistryDefaults(
        # v15.2.0 B-6 — absent key parses to False (probe-not-install); the
        # shipped registry declares the value explicitly either way.
        auto_install=bool(raw.get("auto_install", False)),
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


def _parse_version(output: str) -> str | None:
    """Extract a dotted version token (e.g. ``3.3.0``) from CLI output.

    Handles both ``tool, version 3.3.0`` and ``uipro-cli/2.1.0`` formats.
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


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
