"""Codegraph researcher API — public helpers for L0/L1/L2/L3 invocation.

Five public researcher helpers that mirror the upstream MCP tool surface
(see :mod:`devolaflow.codegraph` package docstring for the full 9-tool
catalog). Each helper is a thin wrapper around
:func:`devolaflow.codegraph._cli.run_codegraph_cli` with degraded-mode
fallback per the v12.5.0 PV-03 D-1.1 design:

* :func:`build_context` → ``codegraph context "<query>"`` (markdown by default)
* :func:`search_symbols` → ``codegraph search "<query>" --kind <kind>``
* :func:`get_impact` → ``codegraph impact <symbol> --depth N --json``
* :func:`get_callers` → ``codegraph callers <symbol> --limit N --json``
* :func:`get_affected_tests` → ``codegraph affected --files file1 file2 ...``

When :class:`devolaflow.codegraph.CodegraphUnavailableError` fires, each
helper:

1. Logs a one-time WARNING per session (deduplicated via
   module-level ``_DEGRADED_MODE_NOTIFIED`` sentinel)
2. Returns an empty / sentinel result (``""`` for build_context, ``[]``
   for the list-returning helpers, ``{}`` for get_impact)

The empty result is the SIGNAL to the caller that codegraph is degraded
— the caller MUST then fall back to Read/Glob/Grep planning per the
documented degraded-mode contract at
``workflow-system/agent/references/degraded-mode.md`` (PV-05). Per S-5
(no silent failures): the WARNING log makes the degraded path auditable
through the standard logging channel.
"""

from __future__ import annotations

import logging
import shlex
from pathlib import Path
from typing import Any

from devolaflow.codegraph._cli import (
    DEFAULT_TIMEOUT_SECONDS,
    CodegraphInvocationResult,
    CodegraphUnavailableError,
    run_codegraph_cli,
)

logger = logging.getLogger(__name__)


__all__ = [
    "build_context",
    "get_affected_tests",
    "get_callers",
    "get_impact",
    "search_symbols",
]


# Module-level sentinel: tracks whether we have already emitted the
# "codegraph degraded — falling back" warning in this Python process.
# Reset by tests via direct attribute write (not a public API).
_DEGRADED_MODE_NOTIFIED: bool = False


def _notify_degraded_once(error: CodegraphUnavailableError, fn_name: str) -> None:
    """Emit the degraded-mode WARNING exactly once per process.

    Subsequent invocations within the same process suppress the WARNING
    to avoid log-spam (a degraded codegraph install will fail every
    helper call; flooding the log adds no operator value beyond the
    first notification).

    Per S-5 (no silent failures) we log via ``logger.warning`` so the
    degraded path is visible through the standard logging chain. The
    DEBUG-level log on subsequent calls preserves auditability without
    spam.
    """
    global _DEGRADED_MODE_NOTIFIED
    if not _DEGRADED_MODE_NOTIFIED:
        logger.warning(
            "[devolaflow.codegraph] %s degraded — codegraph CLI unavailable "
            "(cause=%s). Falling back to Read/Glob/Grep per "
            "references/degraded-mode.md. Subsequent codegraph helpers "
            "in this process will silently fall back without re-warning. "
            "Original error: %s",
            fn_name,
            error.cause,
            error,
        )
        _DEGRADED_MODE_NOTIFIED = True
    else:
        logger.debug(
            "[devolaflow.codegraph] %s degraded (cause=%s); fallback engaged",
            fn_name,
            error.cause,
        )


def build_context(
    query: str,
    *,
    max_nodes: int = 20,
    fmt: str = "markdown",
    cwd: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Build a context bundle for *query* via ``codegraph context``.

    Wraps the upstream ``codegraph context "<query>" --format <fmt>
    --max-nodes <max_nodes>`` invocation. The upstream tool returns
    related symbols + entry points + snippets bundled into a single
    response — DevolaFlow surfaces this as the canonical replacement
    for L0/L1/L2 multi-Read planning patterns.

    Args:
        query: The natural-language query string.
        max_nodes: Maximum nodes to include in the bundle (default 20
            mirrors the cycle plan §PV-03 stage_mapping recipe).
        fmt: Output format. ``"markdown"`` (default) returns prose
            suitable for embedding into agent context; ``"json"``
            returns a structured payload (use
            :func:`run_codegraph_cli` directly with ``parse_json=True``
            for that surface).
        cwd: Working directory for the subprocess.
        timeout: Hard timeout in seconds.

    Returns:
        The markdown context string on success, or ``""`` (empty
        string) when codegraph is degraded — the caller MUST treat the
        empty result as the degraded-mode signal and fall back.
    """
    quoted_query = shlex.quote(query)
    cmd = f"codegraph context {quoted_query} --format {fmt} --max-nodes {max_nodes}"
    try:
        result = run_codegraph_cli(cmd, cwd=cwd, timeout=timeout, parse_json=False)
    except CodegraphUnavailableError as exc:
        _notify_degraded_once(exc, "build_context")
        return ""
    assert isinstance(result, CodegraphInvocationResult)
    return result.stdout


def search_symbols(
    query: str,
    *,
    kind: str | None = None,
    limit: int = 10,
    cwd: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Search the codegraph FTS5 index for symbols matching *query*.

    Wraps ``codegraph search "<query>" --json [--kind <kind>] --limit N``.
    Returns a list of structured symbol records when the index is
    available, ``[]`` (empty list) on degraded mode.

    Args:
        query: The FTS5 query string.
        kind: Optional symbol-kind filter (e.g. ``"function"``,
            ``"class"``, ``"variable"``); when ``None`` the upstream
            default (all kinds) applies.
        limit: Maximum result count (default 10 — the cycle plan §PV-03
            researcher API contract).
        cwd: Working directory for the subprocess.
        timeout: Hard timeout in seconds.

    Returns:
        A list of dicts (symbol records) on success; ``[]`` on degraded
        mode.
    """
    quoted_query = shlex.quote(query)
    parts = [f"codegraph search {quoted_query} --json --limit {limit}"]
    if kind is not None:
        parts.append(f"--kind {shlex.quote(kind)}")
    cmd = " ".join(parts)
    try:
        result = run_codegraph_cli(cmd, cwd=cwd, timeout=timeout, parse_json=True)
    except CodegraphUnavailableError as exc:
        _notify_degraded_once(exc, "search_symbols")
        return []
    if isinstance(result, list):
        return result
    # Upstream may wrap the list under a {"results": [...]} envelope —
    # normalise to a flat list for caller-side simplicity.
    if isinstance(result, dict):
        wrapped = result.get("results")
        if isinstance(wrapped, list):
            return wrapped
    return []


def get_impact(
    symbol: str,
    *,
    depth: int = 3,
    cwd: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Compute blast-radius impact for *symbol* via ``codegraph impact``.

    Wraps ``codegraph impact <symbol> --depth N --json``. Returns the
    upstream-published structured impact payload on success, ``{}`` on
    degraded mode. The empty-dict sentinel is the degraded-mode signal;
    callers (gate scoring, L3 review) MUST fall back to a manual
    blast-radius probe when empty.

    Args:
        symbol: The symbol identifier (function/class/method name).
        depth: Traversal depth for the impact graph (default 3 per the
            cycle plan §PV-03 recipe).
        cwd: Working directory for the subprocess.
        timeout: Hard timeout in seconds.
    """
    quoted_symbol = shlex.quote(symbol)
    cmd = f"codegraph impact {quoted_symbol} --depth {depth} --json"
    try:
        result = run_codegraph_cli(cmd, cwd=cwd, timeout=timeout, parse_json=True)
    except CodegraphUnavailableError as exc:
        _notify_degraded_once(exc, "get_impact")
        return {}
    if isinstance(result, dict):
        return result
    return {}


def get_callers(
    symbol: str,
    *,
    limit: int = 20,
    cwd: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Trace reverse-call edges for *symbol* via ``codegraph callers``.

    Wraps ``codegraph callers <symbol> --limit N --json``. Returns a
    list of caller records on success, ``[]`` on degraded mode.

    Args:
        symbol: The symbol identifier.
        limit: Maximum caller count (default 20).
        cwd: Working directory for the subprocess.
        timeout: Hard timeout in seconds.
    """
    quoted_symbol = shlex.quote(symbol)
    cmd = f"codegraph callers {quoted_symbol} --limit {limit} --json"
    try:
        result = run_codegraph_cli(cmd, cwd=cwd, timeout=timeout, parse_json=True)
    except CodegraphUnavailableError as exc:
        _notify_degraded_once(exc, "get_callers")
        return []
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        wrapped = result.get("callers")
        if isinstance(wrapped, list):
            return wrapped
    return []


def get_affected_tests(
    changed_files: list[str],
    *,
    cwd: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[str]:
    """Compute affected tests for *changed_files* via ``codegraph affected``.

    Wraps ``codegraph affected --files <f1> <f2> ... --json``. Returns
    a list of repo-relative test file paths on success, ``[]`` on
    degraded mode.

    The W-4 EvoBench harness can opt into running ONLY the affected
    tests on CI for selective-test-run optimisation (telegraphed for
    v12.6.0+ ADR per the cycle plan §5 open-question parking).

    Args:
        changed_files: A list of repo-relative paths to changed files.
        cwd: Working directory for the subprocess.
        timeout: Hard timeout in seconds.

    Returns:
        A list of repo-relative test file paths on success; ``[]`` on
        degraded mode OR when *changed_files* is empty (early-return
        without invoking the CLI — defensive zero-IO).
    """
    if not changed_files:
        return []
    quoted_files = " ".join(shlex.quote(p) for p in changed_files)
    cmd = f"codegraph affected --files {quoted_files} --json"
    try:
        result = run_codegraph_cli(cmd, cwd=cwd, timeout=timeout, parse_json=True)
    except CodegraphUnavailableError as exc:
        _notify_degraded_once(exc, "get_affected_tests")
        return []
    if isinstance(result, list):
        return [str(p) for p in result]
    if isinstance(result, dict):
        wrapped = result.get("affected") or result.get("tests")
        if isinstance(wrapped, list):
            return [str(p) for p in wrapped]
    return []
