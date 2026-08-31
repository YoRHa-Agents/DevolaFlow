"""Scaffold direct ``.local/tasks/<task-name>/`` workspace folders.

Task folders use the same checklist-era artifact contract as active changes,
but are intentionally independent of the active/archive lifecycle.  The
entrance router remains owned by :mod:`agent_workspace.entrance`; this module
only composes the other scaffold artifacts and delegates all file writes to
``Change.to_active_folder``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from devolaflow.agent_workspace.change import Change, ChangeLayout
from devolaflow.agent_workspace.entrance import render_entrance_md
from devolaflow.agent_workspace.preflight import (
    PreflightDraftError,
    draft_preflight_section0,
)
from devolaflow.agent_workspace.progress import refresh_progress_header

__all__ = [
    "TASKS_DIR_DEFAULT",
    "TaskFolderError",
    "scaffold_task_folder",
]

TASKS_DIR_DEFAULT: Final[Path] = Path(".local") / "tasks"
_TASK_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_TASK_OWNER_SESSION_ID: Final[str] = "00000000-0000-4000-8000-000000000000"


class TaskFolderError(ValueError):
    """Raised when a task folder cannot be safely scaffolded."""


def _validate_task_name(task_name: str) -> str:
    if not isinstance(task_name, str) or not task_name:
        raise TaskFolderError("task name must be a non-empty repository-relative name")
    candidate = Path(task_name)
    if (
        candidate.is_absolute()
        or candidate.name != task_name
        or _TASK_NAME_RE.fullmatch(task_name) is None
    ):
        raise TaskFolderError(
            f"task name {task_name!r} is invalid; expected a single lowercase-kebab-case "
            "repository-relative name"
        )
    return task_name


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _goal_markdown(task_name: str, title: str, now: str) -> str:
    return (
        "---\n"
        f"id: {task_name}\n"
        f'created: "{now}"\n'
        "priority: P2\n"
        "intent_class: feature\n"
        "goals_count: 1\n"
        "---\n\n"
        f"# Goal: {title}\n\n"
        "## Why\n"
        f"The `{task_name}` task is tracked as an evidence-backed workspace unit.\n\n"
        "## Goals\n"
        f"- G1: {title} → checklist.md ## G1\n\n"
        "## Out of scope\n"
    )


def _checklist_markdown(task_name: str, title: str) -> str:
    raw = (
        "---\n"
        f"parent: {task_name}\n"
        "schema_version: 1\n"
        "total_items: 1\n"
        "checked: 0\n"
        "priority_dist: {P0: 0, P1: 1, P2: 0}\n"
        "reverted_open: 0\n"
        "---\n\n"
        "# Checklist\n\n"
        "## G1: "
        f"{title}\n"
        f"- [ ] C-G1.1 (P1) The `{task_name}` task is completed with evidence\n"
        "      verify: manual\n"
    )
    return raw


def _stage_markdown(task_name: str, now: str) -> str:
    return (
        "---\n"
        f"parent: {task_name}\n"
        "schema_version: 1\n"
        "current_round: 0\n"
        "max_rounds: 3\n"
        "capacity_per_round: 5\n"
        "---\n\n"
        "# Stage — Round Control\n\n"
        "## Priority Settings\n"
        f"- {now} initial: P0=[] P1=[C-G1.1] P2=[]\n\n"
        "## Round History\n"
        "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |\n"
        "|---|---|---|---|---|---|---|\n\n"
        "## Next Round Plan\n"
        "- Candidates: [C-G1.1]\n"
        "- Estimated remaining rounds: 1\n"
    )


def _preflight_markdown(
    task_name: str,
    draft_markdown: str,
) -> str:
    return (
        "---\n"
        f"parent: {task_name}\n"
        "schema_version: 1\n"
        "authorized_at: null\n"
        "snapshot_round: 0\n"
        "config_inherited_from: null\n"
        "project_config_hash: null\n"
        "authorization_hash: null\n"
        "---\n\n"
        "# Preflight\n\n"
        "## 0. Project Configuration\n"
        f"{draft_markdown}\n\n"
        "## 1. Stop Cards\n"
        "| ID | Category | Description | Checklist Items | Disposition |\n"
        "|---|---|---|---|---|\n"
        "| PF-A1 | human_touch | User confirms the task is complete. | "
        "C-G1.1 | reserved_stop |\n\n"
        "## 2. Authorization Record\n"
        "- Pending user signature; `authorized_at` remains null.\n\n"
        "## 3. Permitted Stops\n"
        "1. STOP-1: A Section 1 card with disposition=reserved_stop is reached.\n"
        "2. STOP-2: The two-round stagnation rule fires or max_rounds is reached.\n"
        "3. STOP-3: A FULL_ROLLBACK exception reports state corruption or data loss.\n"
        "4. STOP-4: The user reopens an item and the verbatim reverted reason "
        "explicitly instructs a stop.\n\n"
        "## 4. Progress Snapshot\n"
        "- Checked: 0/1 (P0: 0/0, P1: 0/1, P2: 0/0)\n"
        "- Remaining stop cards: [PF-A1] | Reached this round: []\n"
        "- Estimated remaining rounds: 1\n"
        "- Current blockers: PF-A1; preflight authorization pending\n"
    )


def scaffold_task_folder(
    task_name: str,
    repo_root: Path | str,
    *,
    title: str | None = None,
) -> Path:
    """Create a complete direct task folder under ``.local/tasks/``.

    The operation is create-only: an existing target is never overwritten.
    All generated paths are rooted beneath the resolved repository root and
    ``task_name`` must be one path component matching the workspace id
    contract.  The returned folder contains the required planning artifacts,
    ``STATUS.yaml``, ``owned_files.txt``, an empty ``evidence/`` directory,
    and the canonical ``entrance.md`` router.
    """
    task_name = _validate_task_name(task_name)
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"repository root {root!s} does not exist or is not a directory")

    tasks_root = root / TASKS_DIR_DEFAULT
    if tasks_root.exists() and (tasks_root.is_symlink() or not tasks_root.is_dir()):
        raise TaskFolderError(f"task root {tasks_root!s} is not a real directory")
    target = tasks_root / task_name
    if target.exists():
        raise TaskFolderError(f"task folder {target!s} already exists; refusing to overwrite")

    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(root)
    except ValueError as exc:
        raise TaskFolderError("task folder resolved outside the repository root") from exc

    goal_title = title if title is not None else f"Complete {task_name}"
    if (
        not isinstance(goal_title, str)
        or not goal_title.strip()
        or "\n" in goal_title
        or "\r" in goal_title
    ):
        raise TaskFolderError("task title must be a non-empty single-line string")
    if len(goal_title) > 120:
        raise TaskFolderError("task title must be at most 120 characters")

    now = _now_iso()
    try:
        preflight = draft_preflight_section0(
            root,
            project_name=task_name,
            project_purpose=goal_title,
            seed_mode="feature-enhancement",
        )
    except PreflightDraftError as exc:
        raise TaskFolderError(f"could not draft task preflight: {exc}") from exc

    tasks_root.mkdir(parents=True, exist_ok=True)
    checklist = refresh_progress_header(
        _checklist_markdown(task_name, goal_title),
        _stage_markdown(task_name, now),
    )
    change = Change(
        change_id=task_name,
        goal_md=_goal_markdown(task_name, goal_title, now),
        checklist_md=checklist,
        stage_md=_stage_markdown(task_name, now),
        preflight_md=_preflight_markdown(task_name, preflight.markdown),
        spec_md=(
            "---\n"
            f"parent: {task_name}\n"
            "delta_target: task_workspace\n"
            "delta_kind: lite\n"
            "---\n\n"
            f"# Operation Spec for {task_name}\n\n"
            "## Purpose\n"
            f"Track the observable requirements for `{task_name}`.\n\n"
            "## ADDED Requirements\n\n"
            "### Requirement: Task evidence is recorded\n"
            "The system MUST record a verifiable result for the task.\n\n"
            "#### Scenario: Task reaches verification\n"
            "- GIVEN the task work is complete\n"
            "- WHEN verification runs\n"
            "- THEN evidence/C-G1.1.txt records the result.\n"
        ),
        status={
            "schema_version": 2,
            "change_id": task_name,
            "state": "PROPOSED",
            "percent_complete": 0,
            "owner_layer": "L0",
            "owner_session_id": _TASK_OWNER_SESSION_ID,
            "last_updated": now,
            "last_handoff_seq": 0,
            "gate_score": None,
            "verify_pass": None,
            "checklist_checked": 0,
            "checklist_total": 1,
            "current_round": 0,
            "next_blockers": ["PF-A1", "preflight authorization pending"],
        },
        owned_files=[],
        layout=ChangeLayout.CHECKLIST,
        entrance_md=render_entrance_md(task_name, goal_title),
    )
    change.to_active_folder(target)
    return target
