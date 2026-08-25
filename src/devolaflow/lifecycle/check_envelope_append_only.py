"""Envelope-write lifecycle hook — ``check_envelope_append_only``.

Documented in ``workflow-system/agent/SKILL.md`` §"Lifecycle Hooks" and
``.rules/soul.mdc`` §S-9. Bound to the ``envelope_write`` event by
:mod:`devolaflow.lifecycle.__init__`.

Contract: when an L2 task agent attempts to author a handoff envelope
under ``.local/.agent/handoff/`` (paths of the form
``<from>__<to>__<change-id>__<seq>.yaml``), the target ``path`` MUST NOT
already exist in the directory. To convey new information, the agent
MUST author a NEW envelope with ``seq+1`` rather than overwriting the
existing one. This elevates Soul Rule **S-9** (Handoff Envelopes Are
Append-Only) from a prompt-only constraint to a deterministic check
when ``strict=True``.

Mirrors the design shape of
:mod:`devolaflow.lifecycle.check_file_ownership` (S-8 enforcement) so
the two append-only / disjoint-scope hooks share normalisation
semantics and a uniform ``(payload, *, strict=False) -> HookResult``
signature.

Permissive default — emits a WARNING via the lifecycle logger. Strict
mode re-raises the top-severity :class:`HookViolation` (severity
``blocker`` for append-only breaches, ``error`` for shape violations).
"""

from __future__ import annotations

import os
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "envelope_write"


def _normalise(path: str) -> str:
    """Normalise a path for existing-set comparison.

    Mirrors :func:`devolaflow.lifecycle.check_file_ownership._normalise`
    so the two hooks agree on path-equivalence semantics. Uses
    :func:`os.path.normpath` to collapse ``./``, redundant separators,
    and ``..`` segments. Trailing separators are stripped. Comparison
    is case-sensitive (DevolaFlow targets POSIX-like repos).
    """
    normalised = os.path.normpath(path)
    return normalised.rstrip(os.sep)


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Collect all :class:`HookViolation` instances for *payload*."""
    if not isinstance(payload, dict):
        return [
            HookViolation(
                code="CEA002",
                message="envelope-write payload is not a mapping",
                severity="error",
                context={"payload_type": type(payload).__name__},
            )
        ]

    path = payload.get("path")
    existing = payload.get("existing_paths")

    if path is None or path == "":
        return [
            HookViolation(
                code="CEA002",
                message="envelope-write payload missing required field: 'path'",
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    if not isinstance(path, str):
        return [
            HookViolation(
                code="CEA002",
                message="'path' must be a string",
                severity="error",
                context={"path_type": type(path).__name__},
            )
        ]

    if existing is None:
        return [
            HookViolation(
                code="CEA003",
                message="envelope-write payload missing required field: 'existing_paths'",
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    if not isinstance(existing, list):
        return [
            HookViolation(
                code="CEA003",
                message="'existing_paths' must be a list",
                severity="error",
                context={"existing_paths_type": type(existing).__name__},
            )
        ]

    normalised_path = _normalise(path)
    normalised_existing = {_normalise(p) for p in existing if isinstance(p, str)}

    if normalised_path in normalised_existing:
        return [
            HookViolation(
                code="CEA001",
                message=(
                    f"S-9 append-only breach: write to '{path}' rejected — "
                    "envelope already exists; author a new envelope with seq+1"
                ),
                severity="blocker",
                context={
                    "path": path,
                    "normalised_path": normalised_path,
                    "existing_paths": list(existing),
                },
            )
        ]

    return []


def check_envelope_append_only(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Verify *payload['path']* is NOT already in *payload['existing_paths']*.

    Permissive default emits a WARNING and returns a populated
    :class:`HookResult`. Strict mode raises the top-severity
    :class:`HookViolation` (``blocker`` for append-only breaches,
    ``error`` for payload-shape violations).

    Enforces Soul Rule **S-9** — handoff envelopes are append-only;
    existing envelopes must NEVER be overwritten or deleted. Agents
    that need to convey new information MUST author a fresh envelope
    with ``seq+1``.
    """
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "check_envelope_append_only"]
