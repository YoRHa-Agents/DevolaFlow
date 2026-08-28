"""``entrance.md`` onboarding-router template (v17.2.0 design D-8).

Single source of truth for the entrance router bytes. Two consumers:

* ``devolaflow.skills.slash_commands.scaffold_change_folder`` renders it
  for every fresh ``/devola:propose`` scaffold.
* ``devolaflow.agent_workspace.change.Change.to_active_folder`` backfills
  it whenever a change folder is written without one, so the router is
  ALWAYS materialised alongside the goal/checklist/stage/preflight
  planning artifacts (v20.0.x fix — the design D-4 "backfill" promise
  previously had no runtime owner).

Only Section 1 is per-change personalized; Sections 2-4 are template
verbatim and match ``schemas/agent-workspace/change-entrance.yaml``'s
worked example. Section 3's inventory MUST stay in parity with
``agent_workspace.lint.CHECKLIST_ARTIFACT_BUDGETS`` (ENTRANCE_PARITY).
"""

from __future__ import annotations

import re
from typing import Final

__all__ = [
    "derive_goal_title",
    "render_entrance_md",
]

_GOAL_TITLE_RE: Final[re.Pattern[str]] = re.compile(r"^# Goal: (.+)$", re.MULTILINE)


def derive_goal_title(goal_md: str, change_id: str) -> str:
    """Extract the ``# Goal: <title>`` heading from ``goal.md`` text.

    Falls back to the scaffold default ``Complete <change_id>`` when the
    goal artifact is absent or does not carry the canonical heading
    (``schemas/agent-workspace/change-goal.yaml``), so backfill callers
    always obtain a non-empty Section 1 title.
    """
    match = _GOAL_TITLE_RE.search(goal_md)
    if match is not None:
        title = match.group(1).strip()
        if title:
            return title
    return f"Complete {change_id}"


def render_entrance_md(change_id: str, goal_title: str) -> str:
    """Render the ``entrance.md`` onboarding router (v17.2.0 design D-8).

    Only Section 1 is per-change personalized; Sections 2-4 are template
    verbatim and match ``schemas/agent-workspace/change-entrance.yaml``'s
    worked example. Section 3's inventory MUST stay in parity with
    ``agent_workspace.lint.CHECKLIST_ARTIFACT_BUDGETS`` (ENTRANCE_PARITY).
    """
    return (
        "---\n"
        f"parent: {change_id}\n"
        "schema_version: 1\n"
        "---\n\n"
        f"# Entrance — {change_id}\n\n"
        "> Onboarding entry point: read this first, then load only what your\n"
        "> scenario needs (Section 2). Do not read every file in order.\n\n"
        "## 1. What This Change Is\n"
        f"{goal_title} — see [goal.md](goal.md).\n\n"
        "## 2. Scenario Routing\n"
        "| Scenario | Read order |\n"
        "|---|---|\n"
        "| Session resume | STATUS.yaml → stage.md current round → "
        "checklist.md unchecked items |\n"
        "| New L2 task | checklist_items in your dispatch → owned_files.txt → spec.md |\n"
        "| Review / verify | checklist.md `evidence:` lines → evidence/ files |\n"
        "| Human audit | preflight.md Section 4 snapshot → stage.md round history "
        "→ goal.md |\n\n"
        "## 3. Artifact Inventory\n"
        "| File | Role |\n"
        "|---|---|\n"
        "| `goal.md` | Numbered goal ledger |\n"
        "| `checklist.md` | Tracking table; checked = evidence-backed DONE |\n"
        "| `stage.md` | Round control: selection, waves, history |\n"
        "| `preflight.md` | Pre-execution confirmation + progress snapshot |\n"
        "| `spec.md` | Behaviour delta (Rule A-4) |\n"
        "| `STATUS.yaml` | Machine state — current truth, read first |\n"
        "| `owned_files.txt` | Legal write surface (Rule S-8) |\n"
        "| `harness_preflight.md` | OPTIONAL harness-flag + gap pre-analysis |\n"
        "| `pathfinder_report.md` | OPTIONAL read-only look-ahead gap report |\n"
        "| `evidence/` | Per-item verification evidence |\n\n"
        "## 4. Discipline Pointers\n"
        "- Progress lives in STATUS.yaml + stage.md.\n"
        "- Writes: owned_files.txt per Rule S-8; only the user reverts [x] to [ ].\n"
        "- Handoff envelopes are append-only per Rule S-9.\n"
        "- Budgets and lint: `python -m devolaflow.agent_workspace.lint <change-id>`.\n"
    )
