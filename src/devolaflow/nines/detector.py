"""Detect NineS CLI availability, version, and capabilities.

NineS is an optional dependency. All functions in this module return
structured results and never raise on a missing binary.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"version\s+(\d+\.\d+\.\d+\S*)")
_INSTALL_URL = "https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh"
_INSTALL_CMD = f"curl -fsSL {_INSTALL_URL} | bash"
_KNOWN_SUBCOMMANDS = (
    "eval",
    "collect",
    "analyze",
    "self-eval",
    "iterate",
    "install",
    "benchmark",
    "update",
)
_TIMEOUT = 30


@dataclass(frozen=True)
class NinesStatus:
    """Result of a NineS CLI probe."""

    available: bool = False
    version: str | None = None
    path: str | None = None
    capabilities: list[str] = field(default_factory=list)


def detect_nines() -> NinesStatus:
    """Check whether the *nines* CLI is on ``$PATH`` and return its status.

    Never raises — returns ``NinesStatus(available=False)`` on any failure.
    """
    path = shutil.which("nines")
    if path is None:
        log.debug("nines binary not found on PATH")
        return NinesStatus()

    try:
        proc = subprocess.run(
            ["nines", "--version"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("nines --version failed: %s", exc)
        return NinesStatus(path=path)

    version: str | None = None
    if proc.returncode == 0:
        m = _VERSION_RE.search(proc.stdout)
        if m:
            version = m.group(1)

    return NinesStatus(available=True, version=version, path=path)


def ensure_nines(*, auto_install: bool = False) -> NinesStatus:
    """Return NineS status, optionally auto-installing if absent."""
    status = detect_nines()
    if status.available:
        return status

    if not auto_install:
        log.info("nines not found; auto_install=False — skipping install")
        return status

    log.info("nines not found — attempting auto-install")
    try:
        subprocess.run(
            ["bash", "-c", _INSTALL_CMD],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.error("auto-install failed: %s", exc)
        return NinesStatus()

    return detect_nines()


def get_nines_capabilities() -> list[str]:
    """Return the list of subcommands the installed *nines* binary supports.

    Falls back to the known built-in list when the binary is absent or
    ``nines --help`` cannot be parsed.
    """
    path = shutil.which("nines")
    if path is None:
        return []

    try:
        proc = subprocess.run(
            ["nines", "--help"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return list(_KNOWN_SUBCOMMANDS)

    if proc.returncode != 0:
        return list(_KNOWN_SUBCOMMANDS)

    found: list[str] = []
    for cmd in _KNOWN_SUBCOMMANDS:
        if cmd in proc.stdout:
            found.append(cmd)
    return found or list(_KNOWN_SUBCOMMANDS)
