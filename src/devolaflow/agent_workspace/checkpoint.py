"""Durable, no-clobber workflow checkpoints under ``.local/checkpoints``."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import tempfile
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

__all__ = [
    "CheckpointError",
    "RoundCheckpointResult",
    "checkpoint_round_pass",
    "goal_content_hash",
    "load_checkpoint",
    "write_checkpoint",
]


CHECKPOINT_ROOT: Final[Path] = Path(".local") / "checkpoints"
LATEST_NAME: Final[str] = "checkpoint_latest.yaml"
_REQUIRED_BLOCK_TYPES: Final[tuple[tuple[str, type], ...]] = (
    ("metadata", dict),
    ("project_state", dict),
    ("stage_progress", dict),
    ("wave_state", dict),
    ("quality_snapshot", dict),
    ("deferred_items", list),
    ("active_escalations", list),
)
_CHECKPOINT_ID_RE: Final[re.Pattern[str]] = re.compile(r"^cp_[A-Za-z0-9][A-Za-z0-9_-]*$")
_CHECKLIST_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"^C-G(?P<goal>[1-9][0-9]*)\.(?P<item>[1-9][0-9]*)$"
)
_ACTIVE_ROOT: Final[Path] = Path(".local") / ".agent" / "active"
_PROJECT_CONFIG: Final[Path] = Path(".local") / "project_config.yaml"
# Mirrors ``schemas/agent-workspace/change-status.yaml#fields.change_id.pattern``.
_CHANGE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


class CheckpointError(RuntimeError):
    """Raised when a checkpoint cannot be validated or persisted safely."""


def _checkpoint_id(value: object) -> str:
    if not isinstance(value, str) or len(value) > 240 or _CHECKPOINT_ID_RE.fullmatch(value) is None:
        raise CheckpointError(
            "metadata.checkpoint_id must start with 'cp_' and contain only "
            "ASCII letters, digits, underscores, or hyphens"
        )
    return value


def _validate_checked_ids(value: object) -> None:
    if not isinstance(value, list):
        raise CheckpointError(
            "the latest convergence round_history row requires checked_ids as a list"
        )

    order: list[tuple[int, int]] = []
    seen: set[str] = set()
    for checked_id in value:
        if not isinstance(checked_id, str):
            raise CheckpointError("checked_ids entries must be C-Gn.m strings")
        match = _CHECKLIST_ID_RE.fullmatch(checked_id)
        if match is None:
            raise CheckpointError(f"invalid checked_ids entry {checked_id!r}; expected C-Gn.m")
        if checked_id in seen:
            raise CheckpointError(f"checked_ids contains duplicate entry {checked_id!r}")
        seen.add(checked_id)
        order.append((int(match.group("goal")), int(match.group("item"))))

    if order != sorted(order):
        raise CheckpointError("checked_ids must be in ascending C-Gn.m order")


def _validate_checkpoint(checkpoint: object) -> tuple[dict[str, object], str]:
    if not isinstance(checkpoint, Mapping):
        raise CheckpointError("checkpoint must be a YAML mapping")

    copied = deepcopy(dict(checkpoint))
    missing = [name for name, _ in _REQUIRED_BLOCK_TYPES if name not in copied]
    if missing:
        raise CheckpointError(f"checkpoint is missing required blocks: {', '.join(missing)}")

    for name, expected_type in _REQUIRED_BLOCK_TYPES:
        if not isinstance(copied[name], expected_type):
            raise CheckpointError(f"checkpoint block {name!r} must be a {expected_type.__name__}")

    metadata = copied["metadata"]
    assert isinstance(metadata, dict)
    checkpoint_id = _checkpoint_id(metadata.get("checkpoint_id"))

    if metadata.get("trigger") == "convergence_round_complete":
        convergence_state = copied.get("convergence_state")
        if not isinstance(convergence_state, dict):
            raise CheckpointError("convergence_round_complete requires a convergence_state mapping")
        round_history = convergence_state.get("round_history")
        if not isinstance(round_history, list) or not round_history:
            raise CheckpointError(
                "convergence_round_complete requires a non-empty round_history list"
            )
        latest_row = round_history[-1]
        if not isinstance(latest_row, dict):
            raise CheckpointError("the latest convergence round_history row must be a mapping")
        _validate_checked_ids(latest_row.get("checked_ids"))

    return copied, checkpoint_id


def _checkpoint_folder(repo_root: Path, *, create: bool) -> Path:
    root = Path(repo_root)
    if not root.is_dir():
        raise CheckpointError(f"repo root is missing or not a directory: {root}")
    resolved_root = root.resolve()
    folder = root / CHECKPOINT_ROOT
    try:
        resolved_before = folder.resolve(strict=False)
        resolved_before.relative_to(resolved_root)
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        resolved_after = folder.resolve(strict=False)
        resolved_after.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise CheckpointError(
            f"checkpoint directory escapes the repository or is unusable: {folder}"
        ) from exc
    if not folder.is_dir():
        raise CheckpointError(f"checkpoint directory is missing or not a directory: {folder}")
    return folder


def _target_path(folder: Path, checkpoint_id: str) -> Path:
    target = folder / f"{_checkpoint_id(checkpoint_id)}.yaml"
    try:
        target.resolve(strict=False).relative_to(folder.resolve())
    except (OSError, ValueError) as exc:
        raise CheckpointError(f"checkpoint path escapes {folder}: {target}") from exc
    return target


def _canonical_yaml(checkpoint: dict[str, object]) -> bytes:
    try:
        rendered = yaml.safe_dump(
            checkpoint,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).replace("\r\n", "\n")
        reparsed = yaml.safe_load(rendered)
    except (TypeError, ValueError, yaml.YAMLError) as exc:
        raise CheckpointError("checkpoint cannot be represented as canonical safe YAML") from exc
    if reparsed != checkpoint:
        raise CheckpointError("checkpoint would change during a safe YAML round trip")
    return rendered.encode("utf-8")


def _install_no_clobber(target: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise CheckpointError(
                f"checkpoint already exists; refusing overwrite: {target}"
            ) from exc
        except OSError as exc:
            raise CheckpointError(f"checkpoint atomic install failed: {target}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _replace_latest(folder: Path, target: Path) -> None:
    latest = folder / LATEST_NAME
    temporary: Path | None = None
    try:
        for _ in range(10):
            candidate = folder / f".{LATEST_NAME}.{secrets.token_hex(8)}.tmp"
            try:
                os.symlink(target.name, candidate)
            except FileExistsError:
                continue
            temporary = candidate
            break
        if temporary is None:  # pragma: no cover - requires repeated random-name collisions
            raise CheckpointError("could not allocate a temporary latest-checkpoint symlink")
        os.replace(temporary, latest)
        temporary = None
    except CheckpointError:
        raise
    except OSError as exc:
        raise CheckpointError(f"latest-checkpoint symlink update failed: {latest}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_checkpoint(repo_root: Path, checkpoint: Mapping[str, object]) -> Path:
    """Validate and atomically write one immutable checkpoint.

    The checkpoint id becomes ``.local/checkpoints/<checkpoint_id>.yaml``.
    Existing checkpoint files are never overwritten. After the checkpoint is
    durable, ``checkpoint_latest.yaml`` is atomically replaced with a relative
    symlink to the new file.
    """

    validated, checkpoint_id = _validate_checkpoint(checkpoint)
    folder = _checkpoint_folder(repo_root, create=True)
    target = _target_path(folder, checkpoint_id)
    content = _canonical_yaml(validated)
    _install_no_clobber(target, content)
    _replace_latest(folder, target)
    return target


def _latest_target(folder: Path) -> tuple[Path, str]:
    latest = folder / LATEST_NAME
    try:
        if not latest.is_symlink():
            raise CheckpointError(f"latest checkpoint is missing or is not a symlink: {latest}")
        link_value = os.readlink(latest)
    except CheckpointError:
        raise
    except OSError as exc:
        raise CheckpointError(f"latest checkpoint symlink is unreadable: {latest}") from exc

    link_path = Path(link_value)
    if link_path.is_absolute() or link_value != link_path.name or link_path.suffix != ".yaml":
        raise CheckpointError(
            f"latest checkpoint symlink must use a relative in-directory target: {link_value!r}"
        )
    checkpoint_id = _checkpoint_id(link_path.stem)
    return _target_path(folder, checkpoint_id), checkpoint_id


def _read_checkpoint(target: Path, *, expected_id: str) -> dict[str, object]:
    try:
        if target.is_symlink() or not target.is_file():
            raise CheckpointError(
                f"checkpoint is missing, not a regular file, or is an unsafe symlink: {target}"
            )
        text = target.read_text(encoding="utf-8")
    except CheckpointError:
        raise
    except (OSError, UnicodeError) as exc:
        raise CheckpointError(f"checkpoint is unreadable: {target}") from exc

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CheckpointError(f"checkpoint contains malformed YAML: {target}") from exc
    validated, actual_id = _validate_checkpoint(parsed)
    if actual_id != expected_id:
        raise CheckpointError(
            f"checkpoint metadata id {actual_id!r} does not match filename id {expected_id!r}"
        )
    return validated


def load_checkpoint(
    repo_root: Path,
    checkpoint_id: str | None = None,
) -> dict[str, object]:
    """Load an explicit checkpoint id, or the atomic latest symlink by default."""

    folder = _checkpoint_folder(repo_root, create=False)
    if checkpoint_id is None:
        target, expected_id = _latest_target(folder)
    else:
        expected_id = _checkpoint_id(checkpoint_id)
        target = _target_path(folder, expected_id)
    return _read_checkpoint(target, expected_id=expected_id)


# ── v17.0.0 R4 — round PASS → auto checkpoint (composition API) ────────


def goal_content_hash(repo_root: Path, change_id: str) -> str:
    """Hash the active change's ``goal.md`` for goal-drift detection.

    Returns ``sha256:<64 lowercase hex>`` over the goal bytes after
    newline normalization (``\\r\\n`` and lone ``\\r`` both become
    ``\\n``), mirroring the ``project_state.config_hash`` format. A
    missing ``goal.md`` returns ``""`` (no goal on record → no drift
    check possible); an unreadable one raises loudly per S-5.
    """

    if not isinstance(change_id, str) or _CHANGE_ID_RE.fullmatch(change_id) is None:
        raise CheckpointError(f"invalid change_id {change_id!r}")
    goal_path = Path(repo_root) / _ACTIVE_ROOT / change_id / "goal.md"
    try:
        raw = goal_path.read_bytes()
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise CheckpointError(f"goal.md is unreadable: {goal_path}") from exc
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return f"sha256:{hashlib.sha256(normalized).hexdigest()}"


@dataclass(frozen=True)
class RoundCheckpointResult:
    """Durable references produced by :func:`checkpoint_round_pass`.

    ``stage_reference`` is the repo-relative checkpoint path
    (``.local/checkpoints/<id>.yaml``) the caller MUST cite in the
    corresponding ``stage.md`` round-history row so that
    :func:`devolaflow.agent_workspace.resume.plan_checklist_resume`
    can cross-validate the round later.
    """

    checkpoint_id: str
    path: Path
    stage_reference: str
    goal_hash: str


def _config_hash(repo_root: Path) -> str:
    config_path = Path(repo_root) / _PROJECT_CONFIG
    try:
        config_bytes = config_path.read_bytes()
    except OSError as exc:
        raise CheckpointError(
            f"project config is missing or unreadable (resume requires it): {config_path}"
        ) from exc
    return f"sha256:{hashlib.sha256(config_bytes).hexdigest()}"


def _ordered_checked_ids(checked_ids: Sequence[str]) -> list[str]:
    """Dedupe and canonically order ids ascending by (goal, item)."""

    keyed: dict[str, tuple[int, int]] = {}
    for checked_id in checked_ids:
        if not isinstance(checked_id, str):
            raise CheckpointError("checked_ids entries must be C-Gn.m strings")
        match = _CHECKLIST_ID_RE.fullmatch(checked_id)
        if match is None:
            raise CheckpointError(f"invalid checked_ids entry {checked_id!r}; expected C-Gn.m")
        keyed.setdefault(checked_id, (int(match.group("goal")), int(match.group("item"))))
    return sorted(keyed, key=keyed.__getitem__)


def checkpoint_round_pass(
    repo_root: Path,
    change_id: str,
    pass_result: object,
    checked_ids: Sequence[str],
    *,
    stage_view: object,
    score: float | None = None,
    workflow_run_id: str | None = None,
    prior_round_history: Sequence[Mapping[str, object]] = (),
) -> RoundCheckpointResult:
    """Assemble and persist the ``convergence_round_complete`` checkpoint for one round PASS.

    One-step composition API for L0 after
    :func:`devolaflow.agent_workspace.round_engine.evaluate_round_pass`
    returns a PASS — replaces hand-assembling the checkpoint payload.

    Args:
      repo_root: Repository root containing ``.local/``.
      change_id: Active change whose round just passed.
      pass_result: The round-gate verdict; anything exposing a
        ``passed`` attribute (e.g. ``RoundPassResult``). MUST be a
        PASS — checkpointing a failed round raises.
      checked_ids: Checklist ids checked in this round, in any order;
        deduped and canonically ordered (ascending C-Gn.m) here.
      stage_view: Structural stage snapshot exposing ``current_round``
        (the round that just passed) and ``max_rounds`` — e.g. a
        parsed ``StageDocument``.
      score: Optional round score recorded in the history row.
      workflow_run_id: Optional run id (defaults to ``run-<change_id>``).
      prior_round_history: Closed earlier-round rows to carry forward
        so the checkpoint's ``round_history`` stays cumulative.

    Returns:
      :class:`RoundCheckpointResult` with the checkpoint id, path, the
      ``stage.md`` cross-reference string, and the recorded goal hash.

    Raises:
      CheckpointError: failed round, invalid inputs, missing project
        config, or any persistence failure (all loud per S-5).
    """

    if getattr(pass_result, "passed", None) is not True:
        raise CheckpointError(
            "checkpoint_round_pass requires a PASS verdict; refusing to checkpoint "
            f"a non-passing round (pass_result={pass_result!r})"
        )
    if not isinstance(change_id, str) or _CHANGE_ID_RE.fullmatch(change_id) is None:
        raise CheckpointError(f"invalid change_id {change_id!r}")

    round_num = getattr(stage_view, "current_round", None)
    max_rounds = getattr(stage_view, "max_rounds", None)
    for field_name, value in (("current_round", round_num), ("max_rounds", max_rounds)):
        if type(value) is not int or value < 1:
            raise CheckpointError(f"stage_view.{field_name} must be a positive integer")
    assert isinstance(round_num, int) and isinstance(max_rounds, int)
    if round_num > max_rounds:
        raise CheckpointError(
            f"round {round_num} exceeds max_rounds {max_rounds}; a passing round "
            "cannot close beyond the bounded-retry ceiling"
        )

    checkpoint_id = f"cp_{change_id.replace('.', '-')}_round_{round_num}"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    goal_hash = goal_content_hash(repo_root, change_id)

    latest_row: dict[str, object] = {
        "round": round_num,
        "timestamp": timestamp,
        "checked_ids": _ordered_checked_ids(checked_ids),
    }
    if score is not None:
        latest_row["score"] = score

    checkpoint: dict[str, object] = {
        "metadata": {
            "checkpoint_id": checkpoint_id,
            "timestamp": timestamp,
            "trigger": "convergence_round_complete",
            "workflow_run_id": workflow_run_id or f"run-{change_id}",
            "schema_version": "1.0",
        },
        "project_state": {
            "workflow_type": "checklist_rounds",
            "project_name": change_id,
            "config_hash": _config_hash(repo_root),
            "goal_hash": goal_hash,
        },
        "stage_progress": {},
        "wave_state": {},
        "convergence_state": {
            "current_round": round_num,
            "max_rounds": max_rounds,
            "round_history": [*(deepcopy(dict(row)) for row in prior_round_history), latest_row],
        },
        "quality_snapshot": {},
        "deferred_items": [],
        "active_escalations": [],
    }
    path = write_checkpoint(repo_root, checkpoint)
    return RoundCheckpointResult(
        checkpoint_id=checkpoint_id,
        path=path,
        stage_reference=f".local/checkpoints/{checkpoint_id}.yaml",
        goal_hash=goal_hash,
    )
