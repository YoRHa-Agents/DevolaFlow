"""Session-start resume adapter — ``python -m devolaflow.hostbridge resume``.

v17.0.0 R4 (design §D-R4-1): when a host session starts (Cursor
``sessionStart`` / Claude Code ``SessionStart``), print a compact
checklist-resume summary on stdout for the host to inject as context.

Contract:

* Activation gate REUSES ``DEVOLAFLOW_AGENT_WORKSPACE`` per W-20 —
  session-start resume is the same workspace-engagement activation
  surface as A-6.2 / SKILL.md §"Workspace Engagement (Read at Session
  Start)". R5 strict: any value other than the literal ``"1"`` →
  empty stdout, exit 0, ZERO filesystem IO. NO new env flag.
* Gate on → ``scan_workspace(repo_root).active_changes``:
  0 changes → silent; exactly 1 → ``plan_checklist_resume`` summary
  (change-id, disposition, resume round, checked count, next-round
  selection, GOAL_DRIFT warning when applicable); >1 → only the list
  of change-ids for the operator to pick (never auto-picked).
* Read-only throughout (resume planning is zero-write). Any exception
  degrades to empty stdout + exit 0 AND appends an ``error_allow``
  record to the hostbridge audit ledger (S-5: logged, not silent).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from devolaflow.agent_workspace.resume import (
    ChecklistResumePlan,
    ResumeDisposition,
    plan_checklist_resume,
)
from devolaflow.hostbridge.audit import append_audit, build_audit_record
from devolaflow.hostbridge.decision import VERDICT_ERROR_ALLOW
from devolaflow.skills.change_activation import from_env as workspace_flag_active
from devolaflow.workspace_context import scan_workspace

__all__ = [
    "KIND_SESSION_RESUME",
    "SESSION_HOSTS",
    "build_resume_summary",
    "format_resume_summary",
    "main",
]

logger = logging.getLogger(__name__)

# Only Cursor + Claude Code get a session hook this round; Codex / Kimi /
# DSH are deliberately NOT wired (see references/host-bridges.md §8).
SESSION_HOSTS: tuple[str, ...] = ("cursor", "claude")

KIND_SESSION_RESUME = "session_resume"

_GOAL_DRIFT_WARNING = (
    "  WARNING: GOAL_DRIFT — goal.md changed since the last checkpoint; "
    "human review required before continuing."
)


def format_resume_summary(change_id: str, plan: ChecklistResumePlan) -> str:
    """Render one change's resume plan as a compact context block."""

    lines = [
        f"[devolaflow] workspace resume — change '{change_id}'",
        f"  disposition: {plan.disposition.value}",
        f"  resume round: {plan.resume_round} "
        f"(checkpoint {plan.checkpoint_id}, round {plan.checkpoint_round})",
        f"  checked items: {len(plan.already_checked_ids)}",
    ]
    if plan.selection is not None:
        picked = ", ".join(item.item_id for item in plan.selection.selected)
        lines.append(f"  next-round selection: {picked}")
    if plan.disposition is ResumeDisposition.GOAL_DRIFT:
        lines.append(_GOAL_DRIFT_WARNING)
    return "\n".join(lines) + "\n"


def build_resume_summary(repo_root: Path) -> str:
    """Read-only summary text for the session hook (empty string = silent)."""

    active_changes = scan_workspace(repo_root).active_changes
    if not active_changes:
        return ""
    if len(active_changes) > 1:
        lines = [
            f"[devolaflow] {len(active_changes)} active changes — "
            "pick one to resume (never auto-picked):"
        ]
        lines.extend(f"  - {change_id}" for change_id in active_changes)
        return "\n".join(lines) + "\n"
    change_id = active_changes[0]
    return format_resume_summary(change_id, plan_checklist_resume(repo_root, change_id))


def _audit_session_error(repo_root: Path, host: str, exc: Exception, started: float) -> None:
    record = build_audit_record(
        host=host,
        kind=KIND_SESSION_RESUME,
        path=None,
        command=None,
        verdict=VERDICT_ERROR_ALLOW,
        reason=f"{type(exc).__name__}: {exc}",
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
    )
    append_audit(repo_root, record)


def main(argv: list[str] | None = None) -> int:
    """Session-hook entry: ALWAYS exits 0; empty stdout means no context."""

    argv = list(sys.argv[1:]) if argv is None else list(argv)
    parser = argparse.ArgumentParser(
        prog="python -m devolaflow.hostbridge resume",
        description="DevolaFlow session-start resume summary (stdout context injection).",
    )
    parser.add_argument("--host", choices=SESSION_HOSTS, default="cursor")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repo root to scan for active changes (default: current directory)",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # Bad argv must never break the host session start.
        return 0

    # R5 strict gate FIRST: flag off → zero filesystem IO, empty stdout.
    if not workspace_flag_active():
        return 0

    started = time.perf_counter()
    repo_root: Path | None = None
    try:
        repo_root = args.repo_root if args.repo_root is not None else Path.cwd()
        summary = build_resume_summary(repo_root)
        if summary:
            sys.stdout.write(summary)
        return 0
    except Exception as exc:
        try:
            _audit_session_error(repo_root or Path.cwd(), args.host, exc, started)
        except Exception:  # pragma: no cover - audit itself is best-effort
            logger.warning("hostbridge session-resume audit failed", exc_info=True)
        return 0
