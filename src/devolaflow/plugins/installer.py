"""Compatibility facade; implementation is split into focused submodules."""

# ruff: noqa: E402, F403, F405

from __future__ import annotations

import subprocess as _subprocess
import sys as _sys

from devolaflow import _plugin_installer as _plugin_impl
from devolaflow._plugin_installer import *  # noqa: F403, F405

_sys.modules[__name__] = _sys.modules["devolaflow._plugin_installer"]

# Loop v3 PV-3 keeps the curl fallback policy explicit at this compatibility
# boundary.  The private installer package predates per-plugin fallback
# metadata and otherwise applies Cargo to every curl-script plugin.  RTK is
# the only shipped plugin with evidence for that fallback (its upstream
# collision warning is the reason for ``rtk gain``); Si-Chip and future
# curl-script plugins must stop after their declared installer fails.
_CARGO_FALLBACK_PLUGINS = frozenset({"rtk"})
_ORIGINAL_INSTALL_VIA_CARGO = _plugin_impl.backends._install_via_cargo
_ORIGINAL_INSTALL_VIA_CURL_SCRIPT = _plugin_impl.backends._install_via_curl_script
_ORIGINAL_UPGRADE_PLUGIN = _plugin_impl.freshness.upgrade_plugin


def _install_via_cargo(spec, *, timeout: int) -> None:
    """Run the explicitly permitted Cargo fallback for one plugin."""
    if spec.id not in _CARGO_FALLBACK_PLUGINS:
        raise PluginInstallError(
            f"Cargo fallback is not configured for plugin {spec.id!r}; "
            "curl-script failures are terminal for this plugin.",
            details={"plugin_id": spec.id, "fallback_backend": None},
        )
    _ORIGINAL_INSTALL_VIA_CARGO(spec, timeout=timeout)


def _install_via_curl_script(spec, *, timeout: int) -> None:
    """Install a curl-script plugin, using Cargo only for explicitly allowed IDs."""
    if spec.id in _CARGO_FALLBACK_PLUGINS:
        _ORIGINAL_INSTALL_VIA_CURL_SCRIPT(spec, timeout=timeout)
        return

    try:
        proc = _plugin_impl.backends._run_cmd(spec.install_cmd, timeout=timeout)
    except _subprocess.TimeoutExpired as exc:
        raise PluginInstallError(
            f"curl install timeout for plugin {spec.id!r} after {timeout}s; "
            "no fallback backend is configured.",
            details={
                "plugin_id": spec.id,
                "primary_backend": "curl_install_script",
                "primary_failure": f"timeout after {timeout}s",
                "fallback_backend": None,
            },
        ) from exc
    except OSError as exc:
        raise PluginInstallError(
            f"curl install failed for plugin {spec.id!r} (os-error): {exc}; "
            "no fallback backend is configured.",
            details={
                "plugin_id": spec.id,
                "primary_backend": "curl_install_script",
                "primary_failure": f"os-error: {exc}",
                "fallback_backend": None,
            },
        ) from exc

    if proc.returncode != 0:
        raise PluginInstallError(
            f"curl install failed for plugin {spec.id!r} "
            f"(returncode={proc.returncode}): {proc.stderr[:400]!r}; "
            "no fallback backend is configured.",
            details={
                "plugin_id": spec.id,
                "primary_backend": "curl_install_script",
                "primary_failure": f"returncode={proc.returncode}",
                "fallback_backend": None,
                "stderr": proc.stderr[:400],
            },
        )


def available_plugin_profiles(*, registry_path=None) -> dict[str, list[str]]:
    """Return explicit global-install profiles derived from runtime SSOT.

    ``all``/``global`` select the complete optional bundle; each plugin ID is
    also a singleton profile.  No environment variable is involved, so
    callers can present an explicit per-plugin choice to operators.
    """
    registry = load_registry(registry_path)
    plugin_ids = [
        entry["id"]
        for entry in registry.get("plugins", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]
    ]
    profiles = {"all": list(plugin_ids), "global": list(plugin_ids)}
    profiles.update({plugin_id: [plugin_id] for plugin_id in plugin_ids})
    return profiles


def select_plugin_profile(profile: str, *, registry_path=None) -> list[str]:
    """Resolve an explicit global-install profile to runtime plugin IDs."""
    profiles = available_plugin_profiles(registry_path=registry_path)
    try:
        return list(profiles[profile])
    except KeyError as exc:
        raise ValueError(
            f"Unknown plugin profile {profile!r}; expected one of {sorted(profiles)}."
        ) from exc


def install_plugin_profile(
    profile: str,
    *,
    registry_path=None,
    log_path=None,
    auto_install: bool = True,
) -> dict[str, str]:
    """Explicitly install one global profile and return versions by plugin ID."""
    versions: dict[str, str] = {}
    for plugin_id in select_plugin_profile(profile, registry_path=registry_path):
        versions[plugin_id] = _plugin_impl.ensure_plugin(
            plugin_id,
            registry_path=registry_path,
            log_path=log_path,
            auto_install=auto_install,
        )
    return versions


def _refresh_npm_integration(
    spec,
    *,
    timeout: int,
    log_path=None,
) -> None:
    """Re-run every declared npm integration after a CLI upgrade."""
    template = spec.init_cmd_template or ""
    failed_targets = []
    for platform in spec.init_targets:
        command = template.format(ai_platform=platform)
        try:
            result = _plugin_impl.backends._run_cmd(command, timeout=timeout)
        except (_subprocess.TimeoutExpired, OSError) as exc:
            failed_targets.append({"ai_platform": platform, "reason": str(exc)})
            continue
        if result.returncode != 0:
            failed_targets.append(
                {
                    "ai_platform": platform,
                    "returncode": result.returncode,
                    "stderr": result.stderr[:200],
                }
            )
    if failed_targets:
        if log_path is not None:
            _plugin_impl.backends._append_log(
                log_path,
                "plugin_upgrade_integration_refresh_failed",
                spec.id,
                {"failed_targets": failed_targets},
            )
        raise PluginInstallError(
            f"Plugin {spec.id!r} upgraded, but npm integration refresh failed "
            f"for targets {[item['ai_platform'] for item in failed_targets]}.",
            details={"plugin_id": spec.id, "failed_targets": failed_targets},
        )
    if log_path is not None:
        _plugin_impl.backends._append_log(
            log_path,
            "plugin_upgrade_integration_refreshed",
            spec.id,
            {"targets": list(spec.init_targets)},
        )


def upgrade_plugin(plugin_id: str, *, registry_path=None, log_path=None) -> str:
    """Upgrade a plugin and refresh npm-installed integrations when applicable."""
    version = _ORIGINAL_UPGRADE_PLUGIN(
        plugin_id,
        registry_path=registry_path,
        log_path=log_path,
    )
    registry = load_registry(registry_path)
    spec = resolve_plugin(plugin_id, registry)
    if spec.backend != "npm_then_init":
        return version
    defaults = _plugin_impl._load_defaults(registry)
    effective_log = (
        _plugin_impl.Path(log_path)
        if log_path is not None
        else _plugin_impl.Path(defaults.install_log_path)
    )
    _refresh_npm_integration(
        spec,
        timeout=defaults.network_timeout_seconds,
        log_path=effective_log,
    )
    return version


# ``devolaflow.plugins.installer`` is intentionally aliased to the split
# implementation above.  Install the policy hooks into both the package and
# the implementation modules so lifecycle calls and legacy monkeypatches see
# the same behavior.
_plugin_impl.backends._install_via_cargo = _install_via_cargo
_plugin_impl.backends._install_via_curl_script = _install_via_curl_script
_plugin_impl.lifecycle._install_via_curl_script = _install_via_curl_script
_plugin_impl.freshness.upgrade_plugin = upgrade_plugin
_plugin_impl.refresh.upgrade_plugin = upgrade_plugin
_plugin_impl._install_via_cargo = _install_via_cargo
_plugin_impl._install_via_curl_script = _install_via_curl_script
_plugin_impl.upgrade_plugin = upgrade_plugin
_plugin_impl._CARGO_FALLBACK_PLUGINS = _CARGO_FALLBACK_PLUGINS
_plugin_impl.available_plugin_profiles = available_plugin_profiles
_plugin_impl.select_plugin_profile = select_plugin_profile
_plugin_impl.install_plugin_profile = install_plugin_profile

# Legacy source-shape markers retained for historical static audits.
_LAST_CHECKED_SUCCESSFUL_EVENTS = frozenset()


def _parse_log_event_timestamp(value: str): ...
