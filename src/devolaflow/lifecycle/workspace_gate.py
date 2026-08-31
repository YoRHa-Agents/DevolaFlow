"""Read-only workspace resolution and entrance inspection for lifecycle gates."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devolaflow._workspace_lint import SemanticViolation, lint_change
from devolaflow.agent_workspace.change import ACTIVE_DIR_DEFAULT

__all__ = [
    "ResolvedWorkspace",
    "WorkspaceContextError",
    "WorkspaceEntranceCheck",
    "inspect_workspace_entrance",
    "resolve_workspace",
]

_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
TASK_DIR_DEFAULT = Path(".local") / "tasks"
_ACTIVE_SURFACES = frozenset({"active", "active_change", "change", "change_workspace"})
_TASK_SURFACES = frozenset({"task", "tasks", "task_workspace"})


class WorkspaceContextError(ValueError):
    """Raised when an explicitly supplied workspace context is malformed."""


@dataclass(frozen=True)
class ResolvedWorkspace:
    """An existing, safe workspace folder selected by an explicit context."""

    surface: str
    identifier: str
    repo_root: Path
    folder: Path


@dataclass(frozen=True)
class WorkspaceEntranceCheck:
    """Entrance findings and their resolved workspace provenance."""

    workspace: ResolvedWorkspace
    findings: tuple[SemanticViolation, ...]


def _root_from_payload(payload: Mapping[str, Any], repo_root: Path | str | None) -> Path:
    value = repo_root
    if value is None:
        value = payload.get("_workspace_repo_root", payload.get("repo_root"))
    return Path(value or Path.cwd()).resolve()


def _context_mapping(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("workspace_context", "workspace", "change_context"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, Mapping):
                raise WorkspaceContextError(f"{key} must be a mapping")
            return value
    if payload.get("change_id") is not None:
        return {"surface": "active_change", "change_id": payload["change_id"]}
    if payload.get("task_name") is not None:
        return {"surface": "task", "name": payload["task_name"]}
    return None


def _context_surface_and_identifier(context: Mapping[str, Any]) -> tuple[str, str] | None:
    surface_value = context.get("surface", context.get("type", context.get("kind")))
    change_id = context.get("change_id")
    task_name = context.get("task_name", context.get("name"))

    if surface_value is None:
        if change_id is not None:
            surface_value = "active_change"
        elif task_name is not None:
            surface_value = "task"
        else:
            return None
    if not isinstance(surface_value, str):
        raise WorkspaceContextError("workspace surface must be a string")
    surface = surface_value.strip().lower()
    if surface in _ACTIVE_SURFACES:
        identifier = change_id
        canonical_surface = "active_change"
    elif surface in _TASK_SURFACES:
        identifier = task_name
        canonical_surface = "task"
    else:
        raise WorkspaceContextError(f"unsupported workspace surface {surface_value!r}")

    if not isinstance(identifier, str) or _IDENTIFIER_RE.fullmatch(identifier) is None:
        raise WorkspaceContextError(
            f"{canonical_surface} workspace identifier must be a safe kebab-case name"
        )
    return canonical_surface, identifier


def resolve_workspace(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | str | None = None,
) -> ResolvedWorkspace | None:
    """Resolve an existing active-change or future task workspace.

    No workspace context, or a well-formed context whose folder is absent,
    returns ``None``. The latter preserves ordinary StatusReport behaviour:
    a task id alone is never treated as a workspace name. Malformed explicit
    context raises :class:`WorkspaceContextError` so callers can surface an
    explicit lifecycle warning instead of silently skipping it.
    """

    if not isinstance(payload, Mapping):
        return None
    context = _context_mapping(payload)
    if context is None:
        return None
    selected = _context_surface_and_identifier(context)
    if selected is None:
        return None
    surface, identifier = selected
    root = _root_from_payload(payload, repo_root)
    relative_root = ACTIVE_DIR_DEFAULT if surface == "active_change" else TASK_DIR_DEFAULT
    folder = root / relative_root / identifier
    try:
        if folder.is_symlink():
            raise WorkspaceContextError(f"workspace folder must not be a symlink: {folder}")
        if not folder.is_dir():
            return None
    except OSError as exc:
        raise WorkspaceContextError(
            f"workspace folder cannot be inspected: {folder}: {exc}"
        ) from exc
    return ResolvedWorkspace(
        surface=surface,
        identifier=identifier,
        repo_root=root,
        folder=folder,
    )


def _task_entrance_finding(workspace: ResolvedWorkspace) -> tuple[SemanticViolation, ...]:
    entrance = workspace.folder / "entrance.md"
    try:
        present = entrance.is_file() and not entrance.is_symlink()
    except OSError as exc:
        raise WorkspaceContextError(f"entrance.md cannot be inspected: {entrance}: {exc}") from exc
    if present:
        return ()
    return (
        SemanticViolation(
            "entrance.md",
            "ENTRANCE_MISSING",
            "agent onboarding entry point is absent; materialize entrance.md",
        ),
    )


def inspect_workspace_entrance(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | str | None = None,
) -> WorkspaceEntranceCheck | None:
    """Inspect entrance findings for the explicitly selected workspace.

    Active changes reuse the complete :func:`lint_change` implementation and
    retain its exact ``SemanticViolation`` object. The future task surface
    currently has only the stable resolver and the entrance presence check;
    its full task lint can be added without changing lifecycle consumers.
    """

    workspace = resolve_workspace(payload, repo_root=repo_root)
    if workspace is None:
        return None
    if workspace.surface == "task":
        findings = _task_entrance_finding(workspace)
    else:
        report = lint_change(workspace.identifier, repo_root=workspace.repo_root)
        findings = tuple(
            violation
            for violation in report.violations
            if isinstance(violation, SemanticViolation) and violation.kind.startswith("ENTRANCE_")
        )
    return WorkspaceEntranceCheck(workspace=workspace, findings=findings)
