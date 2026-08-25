"""Read-only checklist resume planning from immutable round checkpoints."""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from devolaflow.agent_workspace.checkpoint import CheckpointError, load_checkpoint
from devolaflow.agent_workspace.round_engine import (
    RoundEngineError,
    RoundSelection,
    select_round,
)
from devolaflow.agent_workspace.round_parser import (
    ChecklistDocument,
    RoundArtifactParseError,
    StageDocument,
    parse_checklist,
    parse_stage,
)

__all__ = [
    "ChecklistResumePlan",
    "ResumeDisposition",
    "ResumePlanningError",
    "plan_checklist_resume",
]


_ACTIVE_ROOT: Final[Path] = Path(".local") / ".agent" / "active"
_PROJECT_CONFIG: Final[Path] = Path(".local") / "project_config.yaml"
_CHANGE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_CONFIG_HASH_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")


class ResumeDisposition(StrEnum):
    """Possible outcomes of read-only checklist resume planning."""

    READY = "READY"
    COMPLETE = "COMPLETE"
    CONFIG_DRIFT = "CONFIG_DRIFT"
    ACTIVE_ESCALATIONS = "ACTIVE_ESCALATIONS"


class ResumePlanningError(RuntimeError):
    """Stable, machine-readable failure to construct a trustworthy plan."""

    __slots__ = ("code", "message")

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class ChecklistResumePlan:
    """Immutable resume verdict and, when ready, bounded round selection."""

    disposition: ResumeDisposition
    checkpoint_id: str
    checkpoint_round: int
    resume_round: int
    already_checked_ids: tuple[str, ...]
    selection: RoundSelection | None
    active_escalations: tuple[object, ...]


@dataclass(frozen=True)
class _CheckpointRound:
    checkpoint_id: str
    round_num: int
    max_rounds: int
    checked_ids: tuple[str, ...]
    all_checkpoint_checked_ids: tuple[str, ...]
    expected_config_hash: str
    active_escalations: tuple[object, ...]


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ResumePlanningError("INVALID_CHECKPOINT_STATE", f"{field} must be a mapping")
    return value


def _positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ResumePlanningError(
            "INVALID_CHECKPOINT_STATE",
            f"{field} must be a positive integer",
        )
    return value


def _checkpoint_round(checkpoint: dict[str, object]) -> _CheckpointRound:
    metadata = _mapping(checkpoint.get("metadata"), field="metadata")
    if metadata.get("trigger") != "convergence_round_complete":
        raise ResumePlanningError(
            "INVALID_CHECKPOINT_TRIGGER",
            "resume requires a convergence_round_complete checkpoint",
        )
    checkpoint_id = metadata.get("checkpoint_id")
    if not isinstance(checkpoint_id, str):
        raise ResumePlanningError(
            "INVALID_CHECKPOINT_STATE",
            "metadata.checkpoint_id must be a string",
        )

    convergence = _mapping(
        checkpoint.get("convergence_state"),
        field="convergence_state",
    )
    max_rounds = _positive_int(
        convergence.get("max_rounds"),
        field="convergence_state.max_rounds",
    )
    history = convergence.get("round_history")
    if not isinstance(history, list) or not history:
        raise ResumePlanningError(
            "INVALID_CHECKPOINT_STATE",
            "convergence_state.round_history must be a non-empty list",
        )
    latest = _mapping(history[-1], field="convergence_state.round_history[-1]")
    round_num = _positive_int(
        latest.get("round"),
        field="latest checkpoint round",
    )
    if convergence.get("current_round") != round_num:
        raise ResumePlanningError(
            "CHECKPOINT_ROUND_MISMATCH",
            "convergence_state.current_round must equal the latest history round",
        )
    if round_num > max_rounds:
        raise ResumePlanningError(
            "CHECKPOINT_ROUND_MISMATCH",
            "latest checkpoint round exceeds convergence_state.max_rounds",
        )

    latest_checked = latest.get("checked_ids")
    if not isinstance(latest_checked, list) or any(
        not isinstance(item_id, str) for item_id in latest_checked
    ):
        raise ResumePlanningError(
            "INVALID_CHECKPOINT_STATE",
            "latest checkpoint checked_ids must be a list of strings",
        )
    all_checked: list[str] = []
    seen_checked: set[str] = set()
    for row in history:
        if not isinstance(row, dict):
            continue
        row_checked = row.get("checked_ids")
        if isinstance(row_checked, list):
            for item_id in row_checked:
                if isinstance(item_id, str) and item_id not in seen_checked:
                    all_checked.append(item_id)
                    seen_checked.add(item_id)

    project_state = _mapping(checkpoint.get("project_state"), field="project_state")
    expected_hash = project_state.get("config_hash")
    if not isinstance(expected_hash, str) or _CONFIG_HASH_RE.fullmatch(expected_hash) is None:
        raise ResumePlanningError(
            "INVALID_CONFIG_HASH",
            "project_state.config_hash must use sha256:<64 lowercase hex>",
        )
    escalations = checkpoint.get("active_escalations")
    if not isinstance(escalations, list):
        raise ResumePlanningError(
            "INVALID_CHECKPOINT_STATE",
            "active_escalations must be a list",
        )
    return _CheckpointRound(
        checkpoint_id=checkpoint_id,
        round_num=round_num,
        max_rounds=max_rounds,
        checked_ids=tuple(latest_checked),
        all_checkpoint_checked_ids=tuple(all_checked),
        expected_config_hash=expected_hash,
        active_escalations=tuple(deepcopy(escalations)),
    )


def _read_round_artifacts(
    repo_root: Path,
    change_id: str,
) -> tuple[ChecklistDocument, StageDocument]:
    if not isinstance(change_id, str) or _CHANGE_ID_RE.fullmatch(change_id) is None:
        raise ResumePlanningError("INVALID_CHANGE_ID", f"invalid change_id {change_id!r}")
    folder = repo_root / _ACTIVE_ROOT / change_id
    try:
        checklist_text = (folder / "checklist.md").read_text(encoding="utf-8")
        stage_text = (folder / "stage.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ResumePlanningError(
            "ARTIFACT_READ_FAILED",
            f"active change {change_id!r} checklist.md or stage.md is unreadable",
        ) from exc
    try:
        checklist = parse_checklist(checklist_text)
        stage = parse_stage(stage_text)
    except RoundArtifactParseError as exc:
        raise ResumePlanningError("ARTIFACT_PARSE_FAILED", str(exc)) from exc
    for filename, parent in (
        ("checklist.md", checklist.artifact.frontmatter.get("parent")),
        ("stage.md", stage.artifact.frontmatter.get("parent")),
    ):
        if parent != change_id:
            raise ResumePlanningError(
                "ARTIFACT_PARENT_MISMATCH",
                f"{filename} parent {parent!r} does not equal change_id {change_id!r}",
            )
    return checklist, stage


def _validate_round_alignment(
    state: _CheckpointRound,
    checklist: ChecklistDocument,
    stage: StageDocument,
) -> int:
    if stage.max_rounds != state.max_rounds:
        raise ResumePlanningError(
            "MAX_ROUNDS_MISMATCH",
            "stage.md max_rounds does not equal checkpoint max_rounds",
        )
    if not stage.history:
        raise ResumePlanningError(
            "STAGE_CHECKPOINT_MISMATCH",
            "stage.md has no closed round referencing the checkpoint",
        )
    latest_stage = stage.history[-1]
    expected_reference = f".local/checkpoints/{state.checkpoint_id}.yaml"
    if latest_stage.round_num != state.round_num or latest_stage.checkpoint != expected_reference:
        raise ResumePlanningError(
            "STAGE_CHECKPOINT_MISMATCH",
            "latest stage round must reference the loaded checkpoint",
        )
    if (
        latest_stage.checked_count != len(state.checked_ids)
        or latest_stage.picked_count != len(latest_stage.picked)
        or not set(state.checked_ids).issubset({picked.item_id for picked in latest_stage.picked})
    ):
        raise ResumePlanningError(
            "CHECKED_IDS_MISMATCH",
            "checkpoint checked_ids do not match the latest stage round result",
        )

    if stage.current_round == state.round_num:
        resume_round = state.round_num + 1
    elif stage.current_round == state.round_num + 1:
        resume_round = stage.current_round
    else:
        raise ResumePlanningError(
            "STAGE_ROUND_MISMATCH",
            "stage current_round must equal checkpoint round or checkpoint round + 1",
        )

    items_by_id = {item.item_id: item for item in checklist.items}
    for item_id in state.all_checkpoint_checked_ids:
        item = items_by_id.get(item_id)
        if item is None:
            raise ResumePlanningError(
                "CHECKED_IDS_MISMATCH",
                f"checkpoint checked item {item_id!r} is absent from checklist.md",
            )
        if not item.checked and item.reverted_reason is None:
            raise ResumePlanningError(
                "REOPEN_REASON_REQUIRED",
                f"checkpoint checked item {item_id!r} is open without a verbatim reverted reason",
            )
    return resume_round


def _config_matches(repo_root: Path, expected_hash: str) -> bool:
    try:
        config_bytes = (repo_root / _PROJECT_CONFIG).read_bytes()
    except OSError as exc:
        raise ResumePlanningError(
            "PROJECT_CONFIG_UNREADABLE",
            ".local/project_config.yaml is missing or unreadable",
        ) from exc
    actual_hash = f"sha256:{hashlib.sha256(config_bytes).hexdigest()}"
    return actual_hash == expected_hash


def plan_checklist_resume(
    repo_root: Path,
    change_id: str,
    checkpoint_id: str | None = None,
) -> ChecklistResumePlan:
    """Build a zero-write plan from the latest closed checklist round."""

    root = Path(repo_root)
    try:
        checkpoint = load_checkpoint(root, checkpoint_id)
    except CheckpointError as exc:
        raise ResumePlanningError("CHECKPOINT_LOAD_FAILED", str(exc)) from exc

    state = _checkpoint_round(checkpoint)
    checklist, stage = _read_round_artifacts(root, change_id)
    resume_round = _validate_round_alignment(state, checklist, stage)
    already_checked = tuple(item.item_id for item in checklist.items if item.checked)

    base = {
        "checkpoint_id": state.checkpoint_id,
        "checkpoint_round": state.round_num,
        "resume_round": resume_round,
        "already_checked_ids": already_checked,
        "selection": None,
        "active_escalations": state.active_escalations,
    }
    if not _config_matches(root, state.expected_config_hash):
        return ChecklistResumePlan(
            disposition=ResumeDisposition.CONFIG_DRIFT,
            **base,
        )
    if state.active_escalations:
        return ChecklistResumePlan(
            disposition=ResumeDisposition.ACTIVE_ESCALATIONS,
            **base,
        )
    if len(already_checked) == len(checklist.items):
        return ChecklistResumePlan(
            disposition=ResumeDisposition.COMPLETE,
            **base,
        )
    if resume_round > state.max_rounds:
        raise ResumePlanningError(
            "MAX_ROUNDS_REACHED",
            "open checklist items remain but the next resume round exceeds max_rounds",
        )

    try:
        selection = select_round(
            checklist,
            stage,
            capacity=stage.capacity_per_round,
        )
    except RoundEngineError as exc:
        raise ResumePlanningError("ROUND_SELECTION_FAILED", str(exc)) from exc
    return ChecklistResumePlan(
        disposition=ResumeDisposition.READY,
        **{**base, "selection": selection},
    )
