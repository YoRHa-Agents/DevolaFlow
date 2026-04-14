"""Shared NineS CLI execution helper.

Provides :func:`run_nines_cli`, the single place where NineS CLI
commands are invoked via ``subprocess``.  All other modules in the
``nines`` package delegate to this helper instead of calling
``subprocess.run`` directly.
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess

logger = logging.getLogger(__name__)


def find_nines_config(search_dir: str = ".") -> str | None:
    """Search upward from *search_dir* for a ``nines.toml`` file."""
    from pathlib import Path

    p = Path(search_dir).resolve()
    while p != p.parent:
        candidate = p / "nines.toml"
        if candidate.exists():
            return str(candidate)
        p = p.parent
    return None


def run_nines_cli(
    cmd: str | list[str],
    timeout: int = 120,
    config_path: str | None = None,
) -> dict:
    """Run a NineS CLI command and return parsed JSON.

    Parameters
    ----------
    cmd:
        Either a shell-style command string (parsed via :func:`shlex.split`)
        or a pre-split list of arguments.
    timeout:
        Maximum seconds to wait for the process.
    config_path:
        Optional path to a ``nines.toml`` config file.  When set,
        ``-c <config_path>`` is inserted after the ``nines`` binary.

    Returns
    -------
    dict
        Parsed JSON output on success, or ``{}`` on any failure.
    """
    args = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    if config_path and len(args) >= 1:
        args[1:1] = ["-c", config_path]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("NineS CLI timed out (%ds): %s", timeout, args)
        return {}
    except OSError as exc:
        logger.warning("NineS CLI failed to start: %s — %s", args, exc)
        return {}

    if result.returncode != 0:
        logger.warning(
            "NineS CLI exited %d: %s stderr=%s",
            result.returncode,
            args,
            result.stderr.strip(),
        )
        return {}

    if not result.stdout.strip():
        return {}

    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse NineS JSON: %s — %s", exc, args)
        return {}
