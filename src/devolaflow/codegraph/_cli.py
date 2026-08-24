"""Thin subprocess wrapper for the codegraph CLI (v12.5.0 PV-03).

Single owner of every ``codegraph`` subprocess invocation. All
:mod:`devolaflow.codegraph.researcher` helpers delegate to
:func:`run_codegraph_cli` so the degraded-mode + structured-error
contract is centralized.

Design constraints (per :mod:`devolaflow.codegraph` package docstring):

* S-5 (no silent failures) — every CLI failure path logs a WARNING and
  raises :exc:`CodegraphUnavailableError` with a structured ``cause``
  (one of ``"path_missing"``, ``"timeout"``, ``"nonzero_exit"``,
  ``"json_parse_error"``).
* S-7 (external resource URLs) — npm + GitHub URL only.
* W-20 (env-flag reuse) — codegraph reuses
  ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1``; NO new env flag.

The module follows the project's established thin-CLI-wrapper pattern.
Codegraph's CLI exit code is the source-of-truth for availability +
per-invocation success, and the wrapper distinguishes
``"path_missing"`` (CLI not on ``$PATH``) from ``"nonzero_exit"`` (CLI
present but the specific subcommand failed).
"""

from __future__ import annotations

import json
import logging
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "CodegraphError",
    "CodegraphInvocationResult",
    "CodegraphUnavailableError",
    "is_codegraph_available",
    "run_codegraph_cli",
]


DEFAULT_TIMEOUT_SECONDS: Final[int] = 60
"""Default subprocess timeout for codegraph CLI invocations.

Codegraph queries are typically sub-second on indexed repos; 60s gives
ample headroom for cold-cache `codegraph context` + `codegraph impact`
queries on monorepos.
"""

_CodegraphCauses = (
    "path_missing",
    "timeout",
    "nonzero_exit",
    "json_parse_error",
)


class CodegraphError(RuntimeError):
    """Base exception for codegraph CLI invocation failures."""


class CodegraphUnavailableError(CodegraphError):
    """Codegraph CLI is unavailable / failed.

    The ``cause`` attribute carries one of the structured causes
    enumerated in :data:`_CodegraphCauses`:

    * ``"path_missing"`` — the ``codegraph`` binary is not on ``$PATH``
    * ``"timeout"`` — subprocess exceeded the timeout window
    * ``"nonzero_exit"`` — CLI present but the subcommand returned non-zero
    * ``"json_parse_error"`` — CLI returned non-JSON output where JSON expected

    Callers (researcher.py helpers) catch this exception and degrade to
    Read/Glob/Grep fallback per the degraded-mode contract documented at
    :mod:`devolaflow.codegraph` package docstring.
    """

    def __init__(self, message: str, *, cause: str) -> None:
        super().__init__(message)
        if cause not in _CodegraphCauses:  # pragma: no cover (defensive)
            raise ValueError(
                f"CodegraphUnavailableError cause must be one of {_CodegraphCauses}; got {cause!r}"
            )
        self.cause: str = cause


@dataclass(frozen=True)
class CodegraphInvocationResult:
    """Structured result from a codegraph CLI invocation.

    Attributes:
        stdout: Captured stdout (UTF-8 decoded, never ``None``).
        stderr: Captured stderr (UTF-8 decoded, never ``None``).
        returncode: Exit code from the subprocess.
        args: The argv list as actually invoked (post-:func:`shlex.split`
            normalisation).
    """

    stdout: str
    stderr: str
    returncode: int
    args: tuple[str, ...]


def is_codegraph_available() -> bool:
    """Return True iff the ``codegraph`` binary is on ``$PATH``.

    Pure availability probe — does NOT invoke the CLI, does NOT touch any
    project state. Suitable for the hot path; matches the
    :func:`devolaflow.shell_proxy.commands.is_command_mapping_active`
    pattern.
    """
    return shutil.which("codegraph") is not None


def run_codegraph_cli(
    cmd: str | list[str],
    *,
    cwd: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    parse_json: bool = False,
) -> CodegraphInvocationResult | dict | list:
    """Run a ``codegraph`` CLI invocation and return the result.

    Args:
        cmd: Either a shell-style command string (parsed via
            :func:`shlex.split`) or a pre-split list. The leading
            ``codegraph`` token is REQUIRED — callers pass e.g.
            ``"codegraph context 'foo' --max-nodes 20"`` rather than
            ``"context 'foo' --max-nodes 20"``. This keeps argv validation
            explicit at the wrapper boundary.
        cwd: Working directory for the subprocess. When ``None``, runs
            from the current process cwd. Tests pass ``tmp_path`` for
            isolation.
        timeout: Hard timeout in seconds (default
            :data:`DEFAULT_TIMEOUT_SECONDS`).
        parse_json: When True, parse stdout as JSON and return the
            parsed object (dict or list). When False (default), return
            a :class:`CodegraphInvocationResult` instance.

    Returns:
        Either a parsed JSON object (when ``parse_json=True``) or a
        :class:`CodegraphInvocationResult` carrying stdout / stderr /
        returncode / argv.

    Raises:
        CodegraphUnavailableError: When the CLI is unavailable. The
            ``cause`` attribute distinguishes the failure mode (see
            class docstring).
    """
    args = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    if not args or args[0] != "codegraph":
        raise CodegraphError(
            f"run_codegraph_cli expects argv to start with 'codegraph'; got {args!r}"
        )

    if not is_codegraph_available():
        msg = (
            "codegraph CLI not found on $PATH; install via "
            "`npm install -g @colbymchenry/codegraph` and re-run, or set "
            "DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1 to opt into the runtime "
            "installer (see workflow-system/agent/references/env-flags.md)"
        )
        logger.warning("[devolaflow.codegraph] %s", msg)
        raise CodegraphUnavailableError(msg, cause="path_missing")

    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"codegraph CLI timed out after {timeout}s: {args!r}"
        logger.warning("[devolaflow.codegraph] %s", msg)
        raise CodegraphUnavailableError(msg, cause="timeout") from exc

    if completed.returncode != 0:
        msg = (
            f"codegraph CLI returned non-zero exit {completed.returncode}: "
            f"args={args!r} stderr={completed.stderr.strip()!r}"
        )
        logger.warning("[devolaflow.codegraph] %s", msg)
        raise CodegraphUnavailableError(msg, cause="nonzero_exit")

    result = CodegraphInvocationResult(
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
        args=tuple(args),
    )

    if not parse_json:
        return result

    if not result.stdout.strip():
        # Empty stdout when JSON expected — operator likely passed a
        # subcommand that returned an empty list/dict; surface as a
        # parse error so the researcher.py wrapper can return a sentinel.
        msg = f"codegraph CLI produced empty stdout when JSON expected: args={args!r}"
        logger.warning("[devolaflow.codegraph] %s", msg)
        raise CodegraphUnavailableError(msg, cause="json_parse_error")

    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        msg = f"codegraph CLI produced non-JSON stdout: args={args!r} error={exc}"
        logger.warning("[devolaflow.codegraph] %s", msg)
        raise CodegraphUnavailableError(msg, cause="json_parse_error") from exc
