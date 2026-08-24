"""Operator-facing ``/devola:*`` slash commands (v9.1.2 PV-02).

Closes M-007 from the v9.0.0 retrospective §3.3 (operator-facing slash
command surface was telegraphed). Four commands ship in this PV:

* ``/devola:propose <topic>`` — scaffolds the v16 checklist layout at
  ``.local/.agent/active/<slug>/``. The canonical storage API writes
  ``goal.md``, ``checklist.md``, ``stage.md``, ``preflight.md``,
  ``spec.md``, ``STATUS.yaml``, ``owned_files.txt``, and ``evidence/``;
  this module adds an operator-facing ``README.md``.
* ``/devola:apply <change-id>`` — flips the change's STATUS.yaml
  ``state`` from ``PROPOSED`` to ``IN_PROGRESS`` via
  :meth:`devolaflow.agent_workspace.ChangeStore.transition_state`
  (legal transition per
  ``schemas/agent-workspace/change-status.yaml#state_transitions``).
* ``/devola:verify <change-id>`` — runs ``pytest`` against the test
  files listed in ``owned_files.txt`` and, on success, transitions
  ``IN_PROGRESS`` → ``VERIFYING`` (the canonical FSM state name; the
  cycle plan §PV-02 verdict-string ``VERIFIED`` is treated as a
  prose alias of ``VERIFYING`` per ``schemas/agent-workspace/change-
  status.yaml#fsm_states`` — keeping the in-repo FSM untouched
  preserves R5 byte-stability for the 5-state FSM contract).
* ``/devola:archive <change-id>`` — gates on ``state == VERIFYING``
  AND ``status['gate_score'] >= 8.5`` (the W-3 / SI-3 PATCH/MINOR
  composite floor per Rule A-4) before delegating to
  :meth:`devolaflow.agent_workspace.ArchiveManager.archive`.

Every command exits ``0`` on the happy path and a non-zero code on
failure (the codes are ``argparse``-friendly and logged to stderr per
S-5; never silently swallowed). The CLI is invokable as a Python
module:

::

    $ python -m devolaflow.skills.slash_commands propose "Add Dark Mode"
    /devola:propose: created .local/.agent/active/add-dark-mode/

The four commands are thin wrappers around the existing
:class:`devolaflow.agent_workspace.ChangeStore` /
:class:`devolaflow.agent_workspace.ArchiveManager` APIs — no schema
mutation, no new top-level dispatch key (A-2 invariant intact).

Source: v9.2.0 cycle plan §PV-02 — ``.cursor/plans/workspace-
capability-activation_ec560bc8.plan.md``.
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml

from devolaflow.agent_workspace import (
    ArchiveError,
    ArchiveManager,
    Change,
    ChangeLayout,
    ChangeNotFoundError,
    ChangeStore,
    ChangeStoreError,
)

__all__ = [
    "ARCHIVE_GATE_THRESHOLD",
    "REQUIRE_VERIFY_STATE",
    "ProposeError",
    "VerifyFailed",
    "build_parser",
    "main",
    "run_apply",
    "run_archive",
    "run_propose",
    "run_verify",
    "scaffold_change_folder",
    "slugify",
]

logger = logging.getLogger(__name__)

# ── Slash command exit codes ───────────────────────────────────────────
# Stable contract; documented in this module's docstring + SKILL.md
# §"When to engage change-driven". Exit codes follow standard CLI
# conventions: 0 happy path, 2 invocation error, 1 runtime failure.
_EXIT_OK: int = 0
_EXIT_FAILURE: int = 1
_EXIT_INVOCATION: int = 2

# ── Gate threshold for /devola:archive ─────────────────────────────────
# Mirrors the W-3 / SI-3 PATCH/MINOR composite floor (≥ 8.5) and
# matches `devolaflow.agent_workspace.archive.GATE_THRESHOLD_DEFAULT`.
# The slash command checks BOTH state == VERIFYING AND gate_score >=
# this threshold per the cycle plan §PV-02:
#
#     "archive" — require gate PASS (STATUS.yaml `state == VERIFIED`
#     AND SI-3 composite >= 8.5 cited)
#
# Re-stating the constant locally rather than re-importing from
# archive.py keeps the slash-command CLI self-contained and avoids a
# circular import while the gate-threshold value is a stable contract
# (A-4 + W-3).
ARCHIVE_GATE_THRESHOLD: float = 8.5

# Per `schemas/agent-workspace/change-status.yaml#fsm_states`, the FSM
# state immediately preceding ARCHIVED is ``VERIFYING`` (NOT
# ``VERIFIED``). The cycle plan §PV-02 prose uses ``VERIFIED`` as a
# human-readable alias; this constant pins the canonical FSM name so
# the slash command stays in lockstep with `Change.with_state` and
# `ArchiveManager.archive(require_state="VERIFYING")`.
REQUIRE_VERIFY_STATE: str = "VERIFYING"

# Slug pattern: lowercase kebab-case per
# `schemas/agent-workspace/change-status.yaml#fields.change_id.pattern`
# (mirrors `devolaflow.agent_workspace.change._CHANGE_ID_RE`). Authored
# locally rather than imported from the private module symbol to keep
# the slash-command CLI's dependency surface explicit.
_SLUGIFY_REPLACE_RE = re.compile(r"[^a-z0-9]+")
_SLUGIFY_TRIM_RE = re.compile(r"^-+|-+$")
_VALID_CHANGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_PROPOSE_OWNER_SESSION_ID = "00000000-0000-4000-8000-000000000000"


# ── Custom error types (S-5 explicit error states) ─────────────────────


class ProposeError(RuntimeError):
    """Raised by :func:`run_propose` when scaffolding fails.

    Loud per S-5 — propose failures never silently fall through; the
    CLI catches the error in :func:`main` and converts it to exit
    code ``1`` with a stderr message naming the cause.
    """


class VerifyFailed(RuntimeError):  # noqa: N818 — public API name pinned by the v9.2.0 cycle plan §PV-02 verbatim contract; the suffix-less name parallels the existing ProposeError above and the agent_workspace.GateThresholdNotMet / MergeConflict precedents which carry the same N818 waiver per the v8.4.4 PV-04 design.md naming convention.
    """Raised by :func:`run_verify` when the pytest invocation exits non-zero.

    The CLI converts this to exit code ``1`` with a stderr message
    citing the pytest exit code so the operator can rerun verbatim.
    """


# ── Helpers ────────────────────────────────────────────────────────────


def slugify(topic: str) -> str:
    """Convert a free-form topic string into a valid change-id slug.

    Args:
      topic: Free-form string from the operator
        (e.g. ``"Add Dark Mode"``, ``"v9.1.2 PV-02"``).

    Returns:
      A lowercase-kebab-case slug matching
      ``schemas/agent-workspace/change-status.yaml#fields.change_id.pattern``
      (``^[a-z0-9][a-z0-9.-]*[a-z0-9]$``). Examples:

      * ``"Add Dark Mode"`` → ``"add-dark-mode"``
      * ``"v9.1.2 PV-02"`` → ``"v9-1-2-pv-02"``
      * ``"  trim  me  "`` → ``"trim-me"``

    Raises:
      ProposeError: when the resulting slug is empty (e.g. topic was
        all whitespace or all special characters) — S-5 explicit error
        rather than silently coercing to a default.
    """
    lowered = topic.lower().strip()
    replaced = _SLUGIFY_REPLACE_RE.sub("-", lowered)
    trimmed = _SLUGIFY_TRIM_RE.sub("", replaced)
    if not trimmed:
        raise ProposeError(
            f"slugify: topic {topic!r} reduces to an empty slug; pass a topic "
            f"with at least one alphanumeric character"
        )
    if not _VALID_CHANGE_ID_RE.match(trimmed):
        # Defensive — the slugify rules should always produce a valid
        # change-id, but if a future edit breaks the invariant we want
        # to fail loudly per S-5 rather than write a malformed folder.
        raise ProposeError(
            f"slugify: derived slug {trimmed!r} (from {topic!r}) does not match "
            f"the change-id pattern {_VALID_CHANGE_ID_RE.pattern!r}"
        )
    return trimmed


def _now_iso() -> str:
    """Current UTC timestamp matching the schema's ISO-8601 pattern."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def scaffold_change_folder(
    topic: str,
    repo_root: Path,
    *,
    change_id: str | None = None,
) -> Path:
    """Create ``.local/.agent/active/<slug>/`` with the v16 checklist layout.

    Args:
      topic: Free-form topic string (passed through :func:`slugify`).
      repo_root: Path to the consumer repo root. The change folder is
        created at ``<repo_root>/.local/.agent/active/<slug>/``.
      change_id: Optional explicit change-id (skips :func:`slugify`).
        Used by tests that need a specific id; CLI never sets this.

    Returns:
      The absolute path to the freshly-created change folder.

    Raises:
      ProposeError: when the folder already exists (idempotency is
        the operator's contract — re-propose by passing a fresh
        topic), or when the topic slug is invalid.

    New proposals use :class:`ChangeLayout.CHECKLIST`: one initial goal
    (G1) maps to one unchecked item (C-G1.1), round control starts at
    zero with capacity five, and preflight remains unsigned. Legacy
    ``acceptance.md`` and ``tasks.md`` are intentionally absent, as is
    the optional ``learnings.jsonl``.
    """
    slug = change_id if change_id is not None else slugify(topic)
    if not _VALID_CHANGE_ID_RE.match(slug):
        raise ProposeError(
            f"scaffold_change_folder: change_id {slug!r} does not match the "
            f"required pattern {_VALID_CHANGE_ID_RE.pattern!r}"
        )

    target = repo_root / ".local" / ".agent" / "active" / slug
    if target.exists():
        raise ProposeError(
            f"/devola:propose: change folder {target!s} already exists; pass a "
            f"fresh topic or remove the existing folder before re-proposing"
        )

    now = _now_iso()
    goal_title = f"Complete {slug}"
    status = {
        "schema_version": 2,
        "change_id": slug,
        "state": "PROPOSED",
        "percent_complete": 0,
        "owner_layer": "L0",
        "owner_session_id": _PROPOSE_OWNER_SESSION_ID,
        "last_updated": now,
        "last_handoff_seq": 0,
        "gate_score": None,
        "verify_pass": None,
        "checklist_checked": 0,
        "checklist_total": 1,
        "current_round": 0,
        "next_blockers": ["PF-A1", "preflight authorization pending"],
    }

    change = Change(
        change_id=slug,
        goal_md=(
            "---\n"
            f"id: {slug}\n"
            f'created: "{now}"\n'
            "priority: P2\n"
            "intent_class: feature\n"
            "goals_count: 1\n"
            "---\n\n"
            f"# Goal: {goal_title}\n\n"
            "## Why\n"
            f"The operator proposed `{slug}` as a tracked, evidence-backed change.\n\n"
            "## Goals\n"
            f"- G1: {goal_title} → checklist.md ## G1\n\n"
            "## Out of scope\n"
        ),
        spec_md=(
            "---\n"
            "schema_version: 1\n"
            f"change_id: {slug}\n"
            "delta_target: TBD\n"
            "---\n\n"
            f"# Spec — {slug}\n\n"
            "<!-- ADDED / MODIFIED / REMOVED Requirements per A-4. -->\n"
        ),
        status=status,
        owned_files=[],
        learnings_jsonl=None,
        layout=ChangeLayout.CHECKLIST,
        checklist_md=(
            "---\n"
            f"parent: {slug}\n"
            "schema_version: 1\n"
            "total_items: 1\n"
            "checked: 0\n"
            "priority_dist: {P0: 0, P1: 1, P2: 0}\n"
            "reverted_open: 0\n"
            "---\n\n"
            "# Checklist\n\n"
            f"## G1: {goal_title}\n"
            f"- [ ] C-G1.1 (P1) User confirms the `{slug}` goal is satisfied by "
            "evidence-backed results\n"
            "      verify: manual\n"
        ),
        stage_md=(
            "---\n"
            f"parent: {slug}\n"
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
        ),
        preflight_md=(
            "---\n"
            f"parent: {slug}\n"
            "schema_version: 1\n"
            "authorized_at: null\n"
            "snapshot_round: 0\n"
            "config_inherited_from: null\n"
            "project_config_hash: null\n"
            "---\n\n"
            "# Preflight\n\n"
            "## 0. Project Configuration\n"
            "### 0.1 Project\n"
            f'- name: {slug} | decision: MANDATORY | source: "propose topic"\n'
            f'- purpose: {goal_title} | decision: MANDATORY | source: "goal.md"\n'
            f"- scope_keywords: [{slug}] | decision: DEFAULTED | source: "
            '"propose topic"\n'
            "- existing_codebase: true | decision: CONFIRM | source: "
            '"repository root; confirm before signing"\n\n'
            "### 0.2 Tech Stack\n"
            "- primary_language: pending | decision: CONFIRM | source: "
            '"detect before signing"\n'
            "- runtime_version: pending | decision: CONFIRM | source: "
            '"detect before signing"\n'
            "- dependency_manifest: pending | decision: CONFIRM | source: "
            '"detect before signing"\n\n'
            "### 0.3 Repository\n"
            "- mode: local | decision: CONFIRM | source: "
            '"safe draft default; detect before signing"\n'
            "- default_branch: pending | decision: CONFIRM | source: "
            '"detect before signing"\n'
            "- branching_strategy: pending | decision: CONFIRM | source: "
            '"confirm before signing"\n\n'
            "### 0.4 Localization\n"
            "- primary_language: en | decision: CONFIRM | source: "
            '"safe draft default; confirm before signing"\n'
            "- bilingual_output: false | decision: CONFIRM | source: "
            '"safe draft default; confirm before signing"\n'
            "- doc_language: en | decision: CONFIRM | source: "
            '"safe draft default; confirm before signing"\n'
            "- code_comments_language: en | decision: DEFAULTED | source: "
            '"safe draft default; confirm before signing"\n\n'
            "### 0.5 Platforms\n"
            "- os: [pending] | decision: CONFIRM | source: "
            '"detect before signing"\n'
            "- architectures: [pending] | decision: CONFIRM | source: "
            '"detect before signing"\n\n'
            "### 0.6 Quality\n"
            "- coverage_target_pct: 80 | decision: CONFIRM | source: "
            '"default; confirm before signing"\n'
            "- gate_profile: standard | decision: CONFIRM | source: "
            '"default; confirm before signing"\n'
            '- max_rounds: 3 | decision: CONFIRM | source: "stage.md"\n\n'
            "### 0.7 Release\n"
            "- versioning: semver | decision: CONFIRM | source: "
            '"default; confirm before signing"\n'
            "- channels: [] | decision: CONFIRM | source: "
            '"confirm before signing"\n\n'
            "### 0.8 Workflow\n"
            "- seed_mode: feature-enhancement | decision: CONFIRM | source: "
            '"propose scaffold"\n'
            "- runtime_loop: checklist_rounds | decision: DEFAULTED | source: "
            '"schema default"\n\n'
            "## 1. Stop Cards\n"
            "| ID | Category | Description | Checklist Items | Disposition |\n"
            "|---|---|---|---|---|\n"
            "| PF-A1 | human_touch | User confirms the goal is satisfied. | "
            "C-G1.1 | reserved_stop |\n\n"
            "## 2. Authorization Record\n"
            "- Pending user signature; `authorized_at` remains null.\n\n"
            "## 3. Permitted Stops\n"
            "1. STOP-1: A Section 1 card with disposition=reserved_stop is reached.\n"
            "2. STOP-2: The two-round stagnation rule fires or max_rounds is reached.\n"
            "3. STOP-3: A FULL_ROLLBACK exception reports state corruption or data loss.\n"
            "4. STOP-4: The user reopens an item and explicitly instructs a stop.\n\n"
            "## 4. Progress Snapshot\n"
            "- Checked: 0/1 (P0: 0/0, P1: 0/1, P2: 0/0)\n"
            "- Remaining stop cards: [PF-A1] | Reached this round: []\n"
            "- Estimated remaining rounds: 1\n"
            "- Current blockers: PF-A1; preflight authorization pending\n"
        ),
        evidence_files={},
    )

    change.to_active_folder(target)

    readme_path = target / "README.md"
    readme_path.write_text(
        (
            f"# Change — {slug}\n\n"
            "Authored via `/devola:propose` using the v16 checklist layout.\n\n"
            "## Checklist and preflight lifecycle\n"
            "1. Review `goal.md` and refine the assertions in `checklist.md` before work starts.\n"
            "2. Complete `preflight.md`; it remains unsigned while `authorized_at` and "
            "`project_config_hash` are null.\n"
            "3. Use `stage.md` to select at most five checklist items per round.\n"
            "4. Store verification output under `evidence/`, then check only the matching "
            "evidence-backed item.\n"
            "5. Keep `STATUS.yaml` counters and current round aligned with the Markdown "
            "artifacts.\n"
            "6. Continue through the existing apply, verify, and archive lifecycle when "
            "the artifacts are ready.\n\n"
            "This scaffold documents the artifact lifecycle only; it does not assert "
            "automatic authorization or checklist-completion enforcement.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )

    return target


# ── Command implementations ────────────────────────────────────────────


def run_propose(
    topic: str,
    repo_root: Path,
    *,
    no_change: bool = False,
) -> Path:
    """Implement ``/devola:propose <topic>`` — scaffold a new change folder.

    Args:
      topic: Free-form topic from the operator.
      repo_root: Consumer repo root.
      no_change: When ``True``, the operator passed ``--no-change`` —
        the propose is a no-op (returns ``repo_root`` unchanged) per
        Rule A-6.3 (the only opt-out channel).

    Returns:
      The absolute path of the freshly-scaffolded change folder, or
      the repo root when ``no_change=True``.
    """
    if no_change:
        logger.info("/devola:propose: --no-change set; skipping scaffold (A-6.3 opt-out)")
        return repo_root
    return scaffold_change_folder(topic, repo_root)


def run_apply(change_id: str, repo_root: Path) -> Change:
    """Implement ``/devola:apply <change-id>`` — flip state to ``IN_PROGRESS``.

    Args:
      change_id: The active change-id to apply.
      repo_root: Consumer repo root.

    Returns:
      The updated :class:`devolaflow.agent_workspace.Change` snapshot.

    Raises:
      ChangeNotFoundError: when ``change_id`` is not active.
      ChangeStoreError: when the FSM transition is illegal (e.g. the
        change is already past PROPOSED — operator should
        ``/devola:verify`` instead).
    """
    store = ChangeStore(repo_root=repo_root)
    return store.transition_state(change_id, "IN_PROGRESS")


def run_verify(
    change_id: str,
    repo_root: Path,
    *,
    pytest_runner: object | None = None,
) -> Change:
    """Implement ``/devola:verify <change-id>`` — run pytest then flip to ``VERIFYING``.

    Args:
      change_id: The active change-id to verify.
      repo_root: Consumer repo root.
      pytest_runner: Optional callable replacing
        :func:`subprocess.run` for the pytest invocation. Tests inject
        a stub via this hook so verify can be exercised without a
        live pytest session. Signature must mirror
        :func:`subprocess.run` — ``(cmd: list[str], cwd: Path,
        check: bool) -> subprocess.CompletedProcess``.

    Returns:
      The updated :class:`devolaflow.agent_workspace.Change` snapshot
      with ``state == "VERIFYING"``.

    Raises:
      VerifyFailed: when the pytest invocation exits non-zero.
      ChangeNotFoundError: when ``change_id`` is not active.
      ChangeStoreError: when the FSM transition is illegal (the
        change must be in ``IN_PROGRESS`` state per
        ``STATE_TRANSITIONS["IN_PROGRESS"] == {"VERIFYING",
        "ESCALATED"}``).

    Behaviour:

    * Filters ``owned_files.txt`` to keep only ``tests/*.py`` paths.
      Production source files are not pytest targets directly; the
      operator is responsible for authoring ``tests/test_<feature>.py``
      and listing it in ``owned_files.txt``.
    * If the filtered list is empty, verify still runs ``pytest -q``
      against the repo root so the operator gets a baseline.
    * On pytest exit code 0 → flip to ``VERIFYING``. Non-zero →
      raise :class:`VerifyFailed`; FSM stays in ``IN_PROGRESS``.
    """
    store = ChangeStore(repo_root=repo_root)
    change = store.get(change_id)
    test_targets = [f for f in change.owned_files if f.startswith("tests/") and f.endswith(".py")]

    cmd: list[str] = [sys.executable, "-m", "pytest", "-q", *test_targets]
    runner = pytest_runner if pytest_runner is not None else subprocess.run

    try:
        result = runner(cmd, cwd=repo_root, check=False)
    except FileNotFoundError as exc:
        # pytest binary missing — explicit per S-5 rather than silent
        # success.
        raise VerifyFailed(
            f"/devola:verify: pytest invocation failed (FileNotFoundError): {exc}"
        ) from exc

    returncode = getattr(result, "returncode", None)
    if returncode is None or returncode != 0:
        raise VerifyFailed(
            f"/devola:verify: pytest exited with returncode={returncode!r} "
            f"on {len(test_targets)} owned test file(s); FSM stays in IN_PROGRESS"
        )

    return store.transition_state(change_id, REQUIRE_VERIFY_STATE)


def run_archive(
    change_id: str,
    repo_root: Path,
    *,
    archive_date: str | None = None,
    require_gate_score: float = ARCHIVE_GATE_THRESHOLD,
) -> Path:
    """Implement ``/devola:archive <change-id>`` — gated move to archive/.

    Args:
      change_id: The active change-id to archive.
      repo_root: Consumer repo root.
      archive_date: Optional ``YYYY-MM-DD`` prefix override (test
        determinism). Defaults to today's UTC date.
      require_gate_score: Minimum ``status['gate_score']`` floor for
        the move (defaults to :data:`ARCHIVE_GATE_THRESHOLD` = 8.5,
        matching W-3 / SI-3 PATCH/MINOR threshold per A-4).

    Returns:
      The absolute path of the archived folder
      (``.local/.agent/archive/<YYYY-MM-DD>-<id>/``).

    Raises:
      ChangeNotFoundError: when ``change_id`` is not active.
      ArchiveError: when the gate fails — verbatim message names the
        bad state OR the missing/below-threshold gate_score per S-5.
    """
    store = ChangeStore(repo_root=repo_root)
    change = store.get(change_id)
    if change.state != REQUIRE_VERIFY_STATE:
        raise ArchiveError(
            f"/devola:archive: change {change_id!r} is in state {change.state!r}; "
            f"archive requires state == {REQUIRE_VERIFY_STATE!r} "
            f"(run /devola:verify first)"
        )
    gate_score_raw = change.status.get("gate_score")
    if gate_score_raw is None:
        raise ArchiveError(
            f"/devola:archive: change {change_id!r} has no gate_score in "
            f"STATUS.yaml; the W-3 / SI-3 composite (>= {require_gate_score}) "
            f"MUST be cited per Rule A-4"
        )
    try:
        gate_score = float(gate_score_raw)
    except (TypeError, ValueError) as exc:
        raise ArchiveError(
            f"/devola:archive: change {change_id!r} has invalid gate_score "
            f"{gate_score_raw!r} (must be float)"
        ) from exc
    if gate_score < require_gate_score:
        raise ArchiveError(
            f"/devola:archive: change {change_id!r} gate_score {gate_score:.2f} "
            f"is below the W-3 / SI-3 floor {require_gate_score:.2f}; "
            f"converge or escalate per P4"
        )

    manager = ArchiveManager(store=store)
    result = manager.archive(
        change_id,
        archive_date=archive_date,
        require_state=REQUIRE_VERIFY_STATE,
        # Tests run with a tmp_path repo where reporter rendering can
        # emit benign warnings; keep auto-regen ON in production but
        # the helpers stay opt-out via parameter override.
        auto_regenerate_reports=True,
    )
    return result.archive_path


# ── argparse glue ──────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with one sub-command per slash CLI."""
    parser = argparse.ArgumentParser(
        prog="devola",
        description=(
            "DevolaFlow operator slash commands — propose / apply / verify / "
            "archive a change folder under .local/.agent/. See "
            "workflow-system/agent/SKILL.md §'When to engage change-driven' "
            "and Architecture rule A-6 in .rules/architecture.mdc."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (defaults to current working directory).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_propose = sub.add_parser(
        "propose",
        help="Scaffold .local/.agent/active/<slug>/ with the v16 checklist layout.",
    )
    p_propose.add_argument("topic", type=str, help="Free-form change topic.")
    p_propose.add_argument(
        "--no-change",
        action="store_true",
        help="A-6.3 opt-out: skip scaffolding even when DEVOLAFLOW_AGENT_WORKSPACE=1.",
    )

    p_apply = sub.add_parser(
        "apply",
        help="Flip the change's STATUS.yaml `state` from PROPOSED to IN_PROGRESS.",
    )
    p_apply.add_argument("change_id", type=str)

    p_verify = sub.add_parser(
        "verify",
        help="Run pytest against owned tests; flip to VERIFYING on PASS.",
    )
    p_verify.add_argument("change_id", type=str)

    p_archive = sub.add_parser(
        "archive",
        help="Move active/<id>/ -> archive/<date>-<id>/ after gate PASS.",
    )
    p_archive.add_argument("change_id", type=str)
    p_archive.add_argument(
        "--archive-date",
        type=str,
        default=None,
        help="Override YYYY-MM-DD archive prefix (test determinism).",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: ``python -m devolaflow.skills.slash_commands ...``.

    Args:
      argv: Optional argv slice (defaults to :data:`sys.argv` ``[1:]``
        when ``None``).

    Returns:
      Exit code: ``0`` on success, ``1`` on runtime failure (e.g.
      gate failed, pytest non-zero, change-id not found), ``2`` on
      invocation error (``argparse`` calls :func:`sys.exit` directly
      for that case so this code path is rarely hit).

    Per S-5: every error path is logged + reported on stderr; nothing
    is silently swallowed.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()

    try:
        if args.command == "propose":
            target = run_propose(args.topic, repo_root, no_change=args.no_change)
            if args.no_change:
                _emit("/devola:propose: --no-change opt-out; no folder created.")
            else:
                rel = _safe_relative(target, repo_root)
                _emit(f"/devola:propose: created {rel}/")
            return _EXIT_OK

        if args.command == "apply":
            change = run_apply(args.change_id, repo_root)
            _emit(f"/devola:apply: {args.change_id} -> state={change.state}")
            return _EXIT_OK

        if args.command == "verify":
            change = run_verify(args.change_id, repo_root)
            _emit(f"/devola:verify: {args.change_id} -> state={change.state}")
            return _EXIT_OK

        if args.command == "archive":
            archive_path = run_archive(
                args.change_id,
                repo_root,
                archive_date=args.archive_date,
            )
            rel = _safe_relative(archive_path, repo_root)
            _emit(f"/devola:archive: {args.change_id} -> {rel}/")
            return _EXIT_OK

    except (ProposeError, VerifyFailed, ArchiveError) as exc:
        _emit_error(str(exc))
        return _EXIT_FAILURE
    except (ChangeStoreError, ChangeNotFoundError) as exc:
        _emit_error(f"change-store error: {exc}")
        return _EXIT_FAILURE

    # Defensive: argparse with required=True should prevent reaching here.
    _emit_error(f"slash_commands: unknown command {args.command!r}")
    return _EXIT_INVOCATION


# ── Internal helpers (stderr-friendly + path safety) ────────────────────


def _emit(line: str) -> None:
    """Write a CLI-style success line to stdout (newline-terminated)."""
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _emit_error(line: str) -> None:
    """Write an error line to stderr + log at ERROR level (S-5)."""
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
    logger.error(line)


def _safe_relative(path: Path, base: Path) -> str:
    """Return ``path`` relative to ``base`` or absolute string if outside.

    Uses ``os.path.relpath``-style fallback so the CLI does not crash
    on edge cases (e.g. archive folder symlinked outside the repo).
    """
    try:
        return str(path.relative_to(base))
    except ValueError:
        # `shutil.os` would also work; importing shutil keeps the
        # dependency surface visible for the linter to catch unused
        # imports if this branch is removed.
        _ = shutil
        return str(path)


# ── Module-level YAML helpers (re-export for tests) ────────────────────
# These reuse PyYAML's safe APIs; defined locally so the module's
# import surface stays minimal and tests can monkeypatch yaml.safe_dump
# without reaching into a sibling module.
_yaml_safe_dump = yaml.safe_dump
_yaml_safe_load = yaml.safe_load


if __name__ == "__main__":  # pragma: no cover - executed via `python -m`
    sys.exit(main())
