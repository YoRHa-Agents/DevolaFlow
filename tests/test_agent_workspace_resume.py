"""Focused read-only recovery tests for checklist resume planning."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from devolaflow.agent_workspace import (
    ResumeDisposition,
    ResumePlanningError,
    plan_checklist_resume,
    write_checkpoint,
)

_REVERTED_REASON = 'Restore "quoted" output -> exactly as approved.'


def _workspace_snapshot(root: Path) -> dict[str, tuple[str, bytes | str]]:
    """Capture files, directories, and links to prove resume planning is read-only."""
    snapshot: dict[str, tuple[str, bytes | str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", path.readlink().as_posix())
        elif path.is_file():
            snapshot[relative] = ("file", path.read_bytes())
        elif path.is_dir():
            snapshot[relative] = ("directory", "")
    return snapshot


def _arrange_resume(
    root: Path,
    *,
    item_states: tuple[str, ...],
    checkpoint_checked_ids: tuple[str, ...],
    stage_current: int,
    checkpoint_round: int = 1,
    checkpoint_max: int = 3,
    stage_max: int | None = None,
    trigger: str = "convergence_round_complete",
    active_escalations: list[object] | None = None,
    config_hash: str | None = None,
    stage_reference: str | None = None,
    stage_picked_ids: tuple[str, ...] | None = None,
    stage_history_round: int | None = None,
    goal_text: str | None = None,
    checkpoint_goal_hash: str | None = None,
) -> tuple[str, tuple[Path, ...]]:
    config_path = root / ".local" / "project_config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(b"quality:\n  max_rounds: 3\n")
    digest = hashlib.sha256(config_path.read_bytes()).hexdigest()

    item_ids = tuple(f"C-G1.{index}" for index in range(1, len(item_states) + 1))
    checklist_lines = [
        "---",
        "parent: resume-test",
        "schema_version: 1",
        f"total_items: {len(item_states)}",
        f"checked: {sum(state == 'checked' for state in item_states)}",
        f"priority_dist: {{P0: {len(item_states)}, P1: 0, P2: 0}}",
        f"reverted_open: {sum(state == 'reverted' for state in item_states)}",
        "---",
        "",
        "# Checklist",
        "",
        "## G1: Resume deterministic checklist work",
    ]
    for item_id, state in zip(item_ids, item_states, strict=True):
        marker = "x" if state == "checked" else " "
        checklist_lines.extend(
            [
                f"- [{marker}] {item_id} (P0) {item_id} has deterministic resume state",
                "      verify: manual",
            ]
        )
        if state == "checked":
            checklist_lines.append(
                f"      evidence: evidence/{item_id}.txt | checked_by: user | "
                f"round: {checkpoint_round} | at: 2026-08-24T10:00:00Z"
            )
        elif state == "reverted":
            checklist_lines.append(f"      reverted: {_REVERTED_REASON} | at: 2026-08-24T10:30:00Z")

    checkpoint_id = f"cp_resume_round_{checkpoint_round}"
    picked_ids = checkpoint_checked_ids if stage_picked_ids is None else stage_picked_ids
    picked = ", ".join(f"{item_id}(P0)" for item_id in picked_ids)
    stage_path = root / ".local" / ".agent" / "active" / "resume-test" / "stage.md"
    stage_path.parent.mkdir(parents=True)
    if goal_text is not None:
        stage_path.with_name("goal.md").write_text(goal_text, encoding="utf-8")
    checklist_path = stage_path.with_name("checklist.md")
    checklist_path.write_text("\n".join(checklist_lines) + "\n", encoding="utf-8")
    stage_path.write_text(
        "\n".join(
            [
                "---",
                "parent: resume-test",
                "schema_version: 1",
                f"current_round: {stage_current}",
                f"max_rounds: {checkpoint_max if stage_max is None else stage_max}",
                "capacity_per_round: 5",
                "---",
                "",
                "# Stage — Round Control",
                "",
                "## Priority Settings",
                f"- 2026-08-24T09:00:00Z initial: P0=[{', '.join(item_ids)}] P1=[] P2=[]",
                "",
                "## Round History",
                "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |",
                "|---|---|---|---|---|---|---|",
                f"| {checkpoint_round if stage_history_round is None else stage_history_round} | "
                f"{picked} | W1 | "
                f"{len(checkpoint_checked_ids)}/{len(picked_ids)} | 0 | "
                f"{stage_reference or f'.local/checkpoints/{checkpoint_id}.yaml'} | 90.0 |",
                "",
                "## Next Round Plan",
                "- Candidates: []",
                "- Estimated remaining rounds: 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    checkpoint = {
        "metadata": {
            "checkpoint_id": checkpoint_id,
            "timestamp": "2026-08-24T10:15:00Z",
            "trigger": trigger,
            "workflow_run_id": "run-resume-test",
            "schema_version": "1.0",
        },
        "project_state": {
            "workflow_type": "checklist_rounds",
            "project_name": "resume-test",
            "config_hash": config_hash or f"sha256:{digest}",
            # v17 R4: goal_hash is ADDITIVE — omitted entirely unless the
            # arranging test opts in (legacy checkpoints have no field).
            **({"goal_hash": checkpoint_goal_hash} if checkpoint_goal_hash is not None else {}),
        },
        "stage_progress": {},
        "wave_state": {},
        "convergence_state": {
            "current_round": checkpoint_round,
            "max_rounds": checkpoint_max,
            "round_history": [
                {
                    "round": checkpoint_round,
                    "score": 90.0,
                    "timestamp": "2026-08-24T10:15:00Z",
                    "checked_ids": list(checkpoint_checked_ids),
                }
            ],
        },
        "quality_snapshot": {},
        "deferred_items": [],
        "active_escalations": active_escalations or [],
    }
    checkpoint_path = write_checkpoint(root, checkpoint)
    return checkpoint_id, (config_path, checklist_path, stage_path, checkpoint_path)


def test_mid_round_interruption_resumes_without_rechecking_completed_items(
    tmp_path: Path,
) -> None:
    checkpoint_id, artifacts = _arrange_resume(
        tmp_path,
        item_states=("reverted", "checked", "open"),
        checkpoint_checked_ids=("C-G1.1",),
        stage_current=2,
    )
    before = _workspace_snapshot(tmp_path)

    plan = plan_checklist_resume(tmp_path, "resume-test", checkpoint_id)

    assert plan.disposition is ResumeDisposition.READY
    assert plan.checkpoint_round == 1
    assert plan.resume_round == 2
    assert plan.already_checked_ids == ("C-G1.2",)
    assert plan.selection is not None
    assert tuple(item.item_id for item in plan.selection.selected) == (
        "C-G1.1",
        "C-G1.3",
    )
    assert _REVERTED_REASON.encode() in artifacts[1].read_bytes()
    assert set(plan.already_checked_ids).isdisjoint(
        item.item_id for item in plan.selection.selected
    )
    assert _workspace_snapshot(tmp_path) == before


@pytest.mark.parametrize("complete", [False, True])
def test_between_round_resume_returns_ready_or_complete(
    tmp_path: Path,
    complete: bool,
) -> None:
    states = ("checked", "checked" if complete else "open")
    checked_ids = ("C-G1.1", "C-G1.2") if complete else ("C-G1.1",)
    checkpoint_id, _artifacts = _arrange_resume(
        tmp_path,
        item_states=states,
        checkpoint_checked_ids=checked_ids,
        stage_current=1,
    )
    before = _workspace_snapshot(tmp_path)

    plan = plan_checklist_resume(
        tmp_path,
        "resume-test",
        checkpoint_id if complete else None,
    )

    expected = ResumeDisposition.COMPLETE if complete else ResumeDisposition.READY
    assert plan.disposition is expected
    assert plan.resume_round == 2
    assert plan.already_checked_ids == checked_ids
    assert (plan.selection is None) is complete
    if plan.selection is not None:
        assert tuple(item.item_id for item in plan.selection.selected) == ("C-G1.2",)
        assert set(plan.already_checked_ids).isdisjoint(
            item.item_id for item in plan.selection.selected
        )
    assert _workspace_snapshot(tmp_path) == before
    with pytest.raises(FrozenInstanceError):
        plan.resume_round = 99  # type: ignore[misc]


@pytest.mark.parametrize("blocked_by", ["config", "escalation"])
def test_resume_blocks_config_drift_or_active_escalations(
    tmp_path: Path,
    blocked_by: str,
) -> None:
    escalation = {"id": "ESC-1", "severity": "HUMAN_INTERVENE"}
    checkpoint_id, _ = _arrange_resume(
        tmp_path,
        item_states=("checked", "open"),
        checkpoint_checked_ids=("C-G1.1",),
        stage_current=1,
        config_hash="sha256:" + "0" * 64 if blocked_by == "config" else None,
        active_escalations=[escalation] if blocked_by == "escalation" else None,
    )

    plan = plan_checklist_resume(tmp_path, "resume-test", checkpoint_id)

    expected = (
        ResumeDisposition.CONFIG_DRIFT
        if blocked_by == "config"
        else ResumeDisposition.ACTIVE_ESCALATIONS
    )
    assert plan.disposition is expected
    assert plan.selection is None
    assert plan.active_escalations == ((escalation,) if blocked_by == "escalation" else ())


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("trigger", "convergence_round_complete"),
        ("round", "latest stage round"),
        ("checked_ids", "checked_ids"),
        ("max_rounds", "max_rounds"),
        ("reference", "reference"),
        ("missing_revert", "verbatim reverted reason"),
    ],
)
def test_resume_rejects_inconsistent_checkpoint_stage_state(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    options: dict[str, object] = {
        "item_states": ("checked", "open"),
        "checkpoint_checked_ids": ("C-G1.1",),
        "stage_current": 1,
    }
    if case == "trigger":
        options["trigger"] = "manual"
    elif case == "round":
        options["checkpoint_round"] = 2
        options["stage_history_round"] = 1
    elif case == "checked_ids":
        options["checkpoint_checked_ids"] = ("C-G1.2",)
        options["stage_picked_ids"] = ("C-G1.1",)
    elif case == "max_rounds":
        options["stage_max"] = 4
    elif case == "reference":
        options["stage_reference"] = ".local/checkpoints/cp_other.yaml"
    elif case == "missing_revert":
        options["item_states"] = ("open", "open")

    checkpoint_id, _ = _arrange_resume(tmp_path, **options)  # type: ignore[arg-type]

    with pytest.raises(ResumePlanningError, match=message):
        plan_checklist_resume(tmp_path, "resume-test", checkpoint_id)


# ── v17.0.0 R4 — goal_loop ↔ goal.md hash binding (D-R4-3) ─────────────


@pytest.mark.parametrize("case", ["drift", "match", "legacy_no_field"])
def test_goal_drift_between_checkpoint_and_resume(tmp_path: Path, case: str) -> None:
    """goal.md edits after the checkpoint flip the plan to GOAL_DRIFT.

    Legacy checkpoints without ``project_state.goal_hash`` skip the check
    entirely (full backward compatibility); a matching hash resumes READY.
    """
    goal_text = "# Goal\nShip the v17 R4 focus/loop surface.\n"
    goal_hash = f"sha256:{hashlib.sha256(goal_text.encode('utf-8')).hexdigest()}"
    checkpoint_id, _ = _arrange_resume(
        tmp_path,
        item_states=("checked", "open"),
        checkpoint_checked_ids=("C-G1.1",),
        stage_current=1,
        goal_text=goal_text,
        checkpoint_goal_hash=None if case == "legacy_no_field" else goal_hash,
    )
    goal_path = tmp_path / ".local" / ".agent" / "active" / "resume-test" / "goal.md"
    if case != "match":
        goal_path.write_text("# Goal\nPivoted mid-flight to a NEW objective.\n", encoding="utf-8")
    before = _workspace_snapshot(tmp_path)

    plan = plan_checklist_resume(tmp_path, "resume-test", checkpoint_id)

    if case == "drift":
        assert plan.disposition is ResumeDisposition.GOAL_DRIFT
        assert plan.selection is None
    else:
        assert plan.disposition is ResumeDisposition.READY
        assert plan.selection is not None
    assert plan.resume_round == 2
    assert _workspace_snapshot(tmp_path) == before
