"""Central registry for DevolaFlow plugins.

Plugins are registered via PluginSpec objects.  The registry supports
detection, auto-install, upgrade, and capability queries.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess

from devolaflow.plugins.models import PluginSpec, PluginStatus

log = logging.getLogger(__name__)

_TIMEOUT = 30
_INSTALL_TIMEOUT = 120


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    """Convert a dotted version string to an int tuple for comparison."""
    parts: list[int] = []
    for segment in version.split("."):
        digits = re.match(r"(\d+)", segment)
        if digits:
            parts.append(int(digits.group(1)))
    return tuple(parts)


def _meets_minimum(current: str, minimum: str) -> bool:
    """Return True when *current* >= *minimum* using numeric tuple comparison."""
    try:
        return _parse_version_tuple(current) >= _parse_version_tuple(minimum)
    except (ValueError, TypeError):
        log.debug("Version comparison fallback: %r vs %r", current, minimum)
        return current >= minimum


class PluginRegistry:
    """Central registry for DevolaFlow plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginSpec] = {}

    # ── registration ────────────────────────────────────────────────

    def register(self, spec: PluginSpec) -> None:
        """Register a plugin specification."""
        if spec.name in self._plugins:
            log.warning("Overwriting existing plugin spec: %s", spec.name)
        self._plugins[spec.name] = spec

    def unregister(self, name: str) -> None:
        """Remove a plugin from the registry."""
        removed = self._plugins.pop(name, None)
        if removed is None:
            log.debug("unregister called for unknown plugin: %s", name)

    # ── lookup ──────────────────────────────────────────────────────

    def get(self, name: str) -> PluginSpec | None:
        """Get a plugin spec by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginSpec]:
        """Return all registered plugin specs."""
        return list(self._plugins.values())

    def get_by_role(self, role: str) -> list[PluginSpec]:
        """Return all plugins matching a role (e.g. 'research')."""
        return [s for s in self._plugins.values() if s.role == role]

    def get_by_capability(self, capability: str) -> list[PluginSpec]:
        """Return all plugins that provide a specific capability."""
        return [s for s in self._plugins.values() if capability in s.capabilities]

    # ── detection ───────────────────────────────────────────────────

    def detect(self, name: str) -> PluginStatus:
        """Detect whether a specific plugin is installed and available."""
        spec = self._plugins.get(name)
        if spec is None:
            log.debug("detect called for unregistered plugin: %s", name)
            return PluginStatus(name=name)

        path = shutil.which(spec.cli_binary)
        if path is None:
            log.debug("%s binary not found on PATH", spec.cli_binary)
            return PluginStatus(name=name)

        version = self._probe_version(spec)
        meets = True
        if spec.min_version and version:
            meets = _meets_minimum(version, spec.min_version)

        return PluginStatus(
            name=name,
            available=True,
            version=version,
            path=path,
            meets_min_version=meets,
            capabilities=list(spec.capabilities),
        )

    def detect_all(self) -> dict[str, PluginStatus]:
        """Detect status of all registered plugins."""
        return {name: self.detect(name) for name in self._plugins}

    # ── install / upgrade ───────────────────────────────────────────

    def ensure(
        self,
        name: str,
        *,
        auto_install: bool = False,
        method: str = "pip",
    ) -> PluginStatus:
        """Ensure a plugin is available, optionally auto-installing."""
        status = self.detect(name)
        if status.available:
            return status

        spec = self._plugins.get(name)
        if spec is None:
            log.warning("ensure called for unregistered plugin: %s", name)
            return status

        if not auto_install:
            log.info("%s not found; auto_install=False — skipping", name)
            return status

        command = spec.install_methods.get(method)
        if command is None:
            log.error("No install method '%s' for plugin %s", method, name)
            return status

        log.info("Installing %s via %s", name, method)
        self._run_shell(command)
        return self.detect(name)

    def upgrade(self, name: str, method: str = "pip") -> PluginStatus:
        """Attempt to upgrade a plugin to the latest version."""
        spec = self._plugins.get(name)
        if spec is None:
            log.warning("upgrade called for unregistered plugin: %s", name)
            return PluginStatus(name=name)

        command = spec.install_methods.get(method)
        if command is None:
            log.error("No install method '%s' for plugin %s", method, name)
            return self.detect(name)

        if method == "pip":
            command = command.replace("pip install", "pip install --upgrade")

        log.info("Upgrading %s via %s", name, method)
        self._run_shell(command)
        return self.detect(name)

    # ── private helpers ─────────────────────────────────────────────

    def _probe_version(self, spec: PluginSpec) -> str | None:
        try:
            proc = subprocess.run(
                spec.version_command.split(),
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("%s version probe failed: %s", spec.name, exc)
            return None

        if proc.returncode != 0:
            return None

        m = re.search(spec.version_regex, proc.stdout + proc.stderr)
        return m.group(1) if m else None

    @staticmethod
    def _run_shell(command: str) -> bool:
        try:
            proc = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=_INSTALL_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.error("Shell command failed: %s", exc)
            return False

        if proc.returncode != 0:
            log.error("Command exited %d: %s", proc.returncode, proc.stderr[:200])
            return False
        return True
