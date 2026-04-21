"""Workflow-level owned_files completeness hook — ``validate_owned_files``.

Checks that dispatch payloads for workflows with canonical file manifests
include all required paths in owned_files. Prevents the recurring bug where
repo-init dispatches miss .local/ and .rules/ paths (v7.4.1/v7.5.0 feedback).

Registered as an extra handler on the ``pre_dispatch`` event (runs after the
default :func:`validate_dispatch` handler).
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "pre_dispatch"

WORKFLOW_MANIFESTS: dict[str, list[str]] = {
    "repo-init": [
        ".local/feedbacks/",
        ".local/tasks/",
        ".local/memory/",
        ".local/index.md",
        ".rules/compile-config.yaml",
    ],
}


def _path_covered(required: str, owned: set[str]) -> bool:
    """Return True if *required* is represented in the *owned* set."""
    norm = required.rstrip("/")
    return any(o in (required, norm) or o.startswith(norm) for o in owned)


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    if not isinstance(payload, dict):
        return []

    workflow = payload.get("workflow") or payload.get("workflow_id") or ""
    if workflow not in WORKFLOW_MANIFESTS:
        return []

    manifest = WORKFLOW_MANIFESTS[workflow]
    owned = payload.get("owned_files") or payload.get("files") or []
    if not isinstance(owned, list):
        return []

    owned_set = set(owned)
    missing = [p for p in manifest if not _path_covered(p, owned_set)]

    if not missing:
        return []

    return [
        HookViolation(
            code="VOF001",
            message=(
                f"owned_files missing {len(missing)} canonical path(s) "
                f"for workflow '{workflow}': {missing}"
            ),
            severity="blocker",
            context={
                "workflow": workflow,
                "missing_paths": missing,
                "owned_files": list(owned),
            },
        )
    ]


def validate_owned_files(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Validate owned_files completeness for workflows with canonical manifests."""
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


__all__ = ["EVENT", "WORKFLOW_MANIFESTS", "validate_owned_files"]
