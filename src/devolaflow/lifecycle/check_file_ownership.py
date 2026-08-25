"""File-write lifecycle hook — ``check_file_ownership``.

Documented in ``workflow-system/agent/SKILL.md`` §"Lifecycle Hooks".
Bound to the ``file_write`` event by :mod:`devolaflow.lifecycle.__init__`.

Contract: when an L2 task agent attempts to write a file, the target
``path`` MUST be in the dispatch payload's ``owned_files`` list. This
elevates Invariant **P1** (Dispatcher-Not-Implementer / disjoint-scope
ownership) from a prompt-only constraint to a deterministic check when
``strict=True``.

Permissive default — emits a WARNING via the lifecycle logger. Strict
mode re-raises the top-severity :class:`HookViolation` (severity
``blocker`` for ownership breaches).
"""

from __future__ import annotations

import os
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "file_write"


def _normalise(path: str) -> str:
    """Normalise a path for owned-set comparison.

    Uses :func:`os.path.normpath` to collapse ``./``, redundant
    separators, and ``..`` segments. Trailing separators are stripped.
    Comparison is case-sensitive (DevolaFlow targets POSIX-like
    repos; case-insensitive matching can be layered on by callers if
    needed by passing a pre-normalised owned set).
    """
    normalised = os.path.normpath(path)
    return normalised.rstrip(os.sep)


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Collect all :class:`HookViolation` instances for *payload*."""
    if not isinstance(payload, dict):
        return [
            HookViolation(
                code="CFO001",
                message="file-write payload is not a mapping",
                severity="error",
                context={"payload_type": type(payload).__name__},
            )
        ]

    path = payload.get("path")
    owned = payload.get("owned_files")
    if owned is None:
        owned = payload.get("files")

    if path is None or path == "":
        return [
            HookViolation(
                code="CFO002",
                message="file-write payload missing required field: 'path'",
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    if not isinstance(path, str):
        return [
            HookViolation(
                code="CFO003",
                message="'path' must be a string",
                severity="error",
                context={"path_type": type(path).__name__},
            )
        ]

    if owned is None:
        return [
            HookViolation(
                code="CFO004",
                message=("file-write payload missing required field: 'owned_files' (or 'files')"),
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    if not isinstance(owned, list):
        return [
            HookViolation(
                code="CFO005",
                message="'owned_files' must be a list",
                severity="error",
                context={"owned_type": type(owned).__name__},
            )
        ]

    normalised_path = _normalise(path)
    normalised_owned = {_normalise(p) for p in owned if isinstance(p, str)}

    if normalised_path not in normalised_owned:
        return [
            HookViolation(
                code="CFO006",
                message=(
                    f"P1 ownership breach: write to '{path}' rejected — path not in owned_files"
                ),
                severity="blocker",
                context={
                    "path": path,
                    "normalised_path": normalised_path,
                    "owned_files": list(owned),
                },
            )
        ]

    return []


def check_file_ownership(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Verify *payload['path']* is in *payload['owned_files']*.

    Permissive default emits a WARNING and returns a populated
    :class:`HookResult`. Strict mode raises the top-severity
    :class:`HookViolation` (always ``blocker`` for ownership breaches).
    """
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "check_file_ownership"]
