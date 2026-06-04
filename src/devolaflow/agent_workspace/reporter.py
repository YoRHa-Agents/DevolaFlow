"""Auto-generated REPORT.md surface for the agent workspace (v8.2.7).

Closes H-005 from ``.local/research/v8.3.0_gap_analysis.md`` per the patch
plan in ``.local/research/v8.3.0_patch_plan.md`` §"v8.2.7 — Auto-Generated
REPORT.md Surface". Renders four flavours of human-readable Markdown
report from the v8.2.5 ``agent_workspace`` substrate + the v7.0.3 learnings
JSONL substrate + the v8.2.2 layered ``.rules/`` directory:

1. **Per-change** ``REPORT.md`` (``render_change_report`` → archived
   ``<archive>/<date>-<id>/REPORT.md``) — auto-generated at ``/devola:
   archive`` time.
2. **Aggregate workspace** ``REPORT.md`` (``render_workspace_report`` →
   ``.local/.agent/REPORT.md``) — auto-regen on every state transition.
3. **Memory** ``REPORT.md`` (``render_memory_report`` →
   ``.local/memory/REPORT.md``) — auto-regen on learnings consolidate.
4. **Rules** ``REPORT.md`` (``render_rules_report`` →
   ``.rules/REPORT.md``) — auto-regen on rule compile.

Per Rule I-PV07-A in the patch plan, all four renderers are *opt-in*:
existing workflows do NOT auto-trigger them. Callers (the v8.2.5
:class:`devolaflow.agent_workspace.archive.ArchiveManager`, the v8.2.6
``change-driven`` template, the v8.2.2 ``.rules/`` compiler — *if* they
choose to wire it in subsequent patches) explicitly invoke
:func:`regenerate_all` (or the per-flavour functions, or the CLI:
``python -m devolaflow.agent_workspace.reporter --all``).

Idempotency contract (AC-5): with a fixed ``now`` injection (or any pinned
clock), two consecutive ``regenerate_all(repo_root, now=...)`` invocations
produce byte-identical output. The CLI defaults ``now`` to
``datetime.now(UTC)``; pin it from tests via the keyword argument.

R5 backward-compat: this module adds NO public symbol to
``devolaflow.__init__`` and makes NO edits to ``learnings.py`` or any other
v8.2.5 module — the per-flavour renderers consume the public APIs of
:class:`devolaflow.agent_workspace.change.Change`,
:class:`devolaflow.agent_workspace.change.ChangeStore`, and
:func:`devolaflow.learnings.resolve_learnings_path` only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from devolaflow.agent_workspace.change import (
    ACTIVE_DIR_DEFAULT,
    ARCHIVE_DIR_DEFAULT,
    Change,
    ChangeNotFoundError,
    ChangeStore,
)
from devolaflow.agent_workspace.delta_parser import (
    DELTA_SECTION_KINDS,
    DeltaSpecParseError,
    parse_delta_spec,
)
from devolaflow.agent_workspace.handoff import (
    HANDOFF_DIR_DEFAULT,
    HandoffEnvelope,
    HandoffStore,
    HandoffStoreError,
)
from devolaflow.agent_workspace.requirements_trace import (
    RequirementTraceResult,
    trace_requirements,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_ARCHIVE_WINDOW_DAYS",
    "DEFAULT_MEMORY_WINDOW_DAYS",
    "HUMAN_DIGEST_PATH_DEFAULT",
    "RULES_LAYERS",
    "regenerate_all",
    "render_change_report",
    "render_human_digest",
    "render_human_report",
    "render_memory_report",
    "render_rules_report",
    "render_workspace_report",
]


# Canonical output destinations — all relative to the repo root. Pinned here
# (and not in :func:`regenerate_all` only) so callers writing reports
# elsewhere can still mirror the canonical layout.
WORKSPACE_REPORT_PATH_DEFAULT: Final[Path] = Path(".local") / ".agent" / "REPORT.md"
MEMORY_REPORT_PATH_DEFAULT: Final[Path] = Path(".local") / "memory" / "REPORT.md"
RULES_REPORT_PATH_DEFAULT: Final[Path] = Path(".rules") / "REPORT.md"

# Human-facing OUTPUT surface (v14.0.0 design §4 — the FIFTH reporter
# flavour). The convergence report is per-cycle (``<version>-convergence.md``)
# under ``output/convergence/``; the DIGEST is a single overwritten
# read-first surface under ``output/``. INPUT (``input/``) is human-owned
# and is NEVER written by the reporter (write-owner = human per §2).
HUMAN_OUTPUT_DIR_DEFAULT: Final[Path] = Path(".local") / "human" / "output"
HUMAN_DIGEST_PATH_DEFAULT: Final[Path] = HUMAN_OUTPUT_DIR_DEFAULT / "DIGEST.md"

# Convergence-report status enum (design §4a) — line-1 conclusion.
HUMAN_STATUS_PASSED: Final[str] = "passed"
HUMAN_STATUS_GAPS_FOUND: Final[str] = "gaps_found"
HUMAN_STATUS_HUMAN_NEEDED: Final[str] = "human_needed"

# Severity split (mirrors ``gate/scorer.py`` SEVERITY_WEIGHTS handling):
# blocker/critical MUST resolve before human approval; major/minor/info are
# advisory (do NOT block). See design §4a + §6c.
_BLOCKING_SEVERITIES: Final[frozenset[str]] = frozenset({"blocker", "critical"})
_ADVISORY_SEVERITIES: Final[frozenset[str]] = frozenset({"major", "minor", "info"})

# Knobs surfaced on both the public API and the CLI.
DEFAULT_ARCHIVE_WINDOW_DAYS: Final[int] = 7
DEFAULT_MEMORY_WINDOW_DAYS: Final[int] = 30
DEFAULT_TOP_LEARNINGS: Final[int] = 10

# Per Rule SI-1 / .rules/index.md: 5 layers, in priority order.
RULES_LAYERS: Final[tuple[tuple[str, str], ...]] = (
    ("Soul (P0)", "soul.mdc"),
    ("Architecture (P1)", "architecture.mdc"),
    ("Conventions (P2)", "conventions.mdc"),
    ("Workflow (P3)", "workflow.mdc"),
    ("Style (P4)", "style.mdc"),
)

# Heading pattern for individual rules — matches `## S-1 ...`, `### ST-12 ...`, etc.
_RULE_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^#+ [A-Z]{1,3}-\d+\b")
# `## Why` block extractor for goal.md.
_WHY_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Why\s*$")
# `## N. <title>` task group extractor for tasks.md.
_TASK_GROUP_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+(\d+\.\s+.+)$")
# Archive folder date prefix.
_ARCHIVE_DATE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


# ---------------------------------------------------------------------------
# Public render functions
# ---------------------------------------------------------------------------


def render_change_report(
    change_id: str,
    *,
    repo_root: Path | None = None,
    archive_root: Path | None = None,
    active_root: Path | None = None,
    now: datetime | None = None,
) -> str:
    """Render the per-change ``REPORT.md`` for ``change_id``.

    Searches ``archive_root`` (default ``.local/.agent/archive/``) first,
    then falls back to ``active_root`` so the same renderer works for
    not-yet-archived changes (useful for previewing). The rendered text
    is returned; callers (typically :func:`regenerate_all` or
    :class:`ArchiveManager`) decide whether to write it to disk.

    Args:
      change_id: lowercase-kebab-case change id.
      repo_root: repo root directory (default: ``Path.cwd()``).
      archive_root: override the archive folder (relative to ``repo_root``).
      active_root: override the active folder (relative to ``repo_root``).
      now: pinned clock for deterministic testing (default
        ``datetime.now(UTC)``).

    Raises:
      ChangeNotFoundError: when ``change_id`` is in neither archive nor active.
    """
    root = _resolve_repo_root(repo_root)
    archive_dir = _resolve_under_root(root, archive_root, ARCHIVE_DIR_DEFAULT)
    active_dir = _resolve_under_root(root, active_root, ACTIVE_DIR_DEFAULT)

    change_folder = _find_change_folder(change_id, archive_dir, active_dir)
    change = Change.from_active_folder(change_folder)

    archive_date = _archive_date_from_folder(change_folder)
    duration = _compute_duration(change.goal_md, change.status)
    author = str(change.status.get("owner_session_id") or "<unknown>")

    delta_sections = _extract_delta_sections(change.spec_md)
    goal_why = _extract_goal_why(change.goal_md) or "_Not stated._"
    purpose = _extract_purpose(change.spec_md)
    task_groups = _extract_task_groups(change.tasks_md)
    learnings = _parse_learnings_jsonl(change.learnings_jsonl)
    handoff_chain = _summarise_handoff_chain(change_id, change_folder, root)

    verification = _verification_block(change.status)

    template = _env().get_template("change_report.md.j2")
    return template.render(
        change_id=change_id,
        archive_date=archive_date,
        author=author,
        duration=duration,
        delta_sections=delta_sections,
        goal_why=goal_why,
        purpose=purpose,
        task_groups=task_groups,
        owned_files=list(change.owned_files),
        learnings=learnings,
        handoff_chain=handoff_chain,
        ac_pass_rate=verification["ac_pass_rate"],
        tests_passed=verification["tests_passed"],
        coverage=verification["coverage"],
        lint=verification["lint"],
        format_status=verification["format"],
        gate_score=verification["gate_score"],
        now=_format_iso(_normalise_now(now)),
    )


def render_workspace_report(
    *,
    repo_root: Path | None = None,
    workspace_root: Path | None = None,
    active_root: Path | None = None,
    archive_root: Path | None = None,
    archive_window_days: int = DEFAULT_ARCHIVE_WINDOW_DAYS,
    now: datetime | None = None,
) -> str:
    """Render the aggregate ``.local/.agent/REPORT.md`` text.

    Enumerates active changes via :class:`ChangeStore.list_active` and the
    last ``archive_window_days`` of archived changes via
    :class:`ChangeStore.list_archive`. For each change, loads the
    :class:`Change` to surface state, percent-complete, and gate score.

    The ``workspace_root`` argument is accepted for API symmetry with the
    other renderers but is currently unused (the active/archive layout
    lives at fixed offsets under ``repo_root``).
    """
    del workspace_root  # accepted for API symmetry; layout is canonical.
    root = _resolve_repo_root(repo_root)
    store = _make_store(root, active_root, archive_root)
    pinned_now = _normalise_now(now)

    active_changes = _collect_active_changes(store)
    archived_changes = _collect_archived_changes(
        store,
        window_days=archive_window_days,
        now=pinned_now,
    )

    template = _env().get_template("workspace_report.md.j2")
    return template.render(
        last_updated=_format_iso(pinned_now),
        active_count=len(active_changes),
        archive_count=len(archived_changes),
        archive_window_days=archive_window_days,
        active_changes=active_changes,
        archived_changes=archived_changes,
    )


def render_memory_report(
    *,
    repo_root: Path | None = None,
    memory_root: Path | None = None,
    operational_jsonl: Path | None = None,
    external_jsonl: Path | None = None,
    window_days: int = DEFAULT_MEMORY_WINDOW_DAYS,
    top_n: int = DEFAULT_TOP_LEARNINGS,
    now: datetime | None = None,
) -> str:
    """Render the ``.local/memory/REPORT.md`` text.

    Reads JSONL directly (NOT via :mod:`devolaflow.learnings` writes — Rule
    R5 forbids edits to that module) from
    ``.local/memory/operational.jsonl`` (project-local) falling back to
    ``workflow-system/agent/knowledge/learnings/operational.jsonl``
    (canonical). External-source reviews are read from
    ``.local/memory/external-sources.jsonl`` falling back to
    ``workflow-system/agent/knowledge/learnings/external-sources.jsonl``.

    Args:
      repo_root: repo root (default: ``Path.cwd()``).
      memory_root: override the ``.local/memory`` folder.
      operational_jsonl: explicit path to the operational JSONL.
      external_jsonl: explicit path to the external-source-reviews JSONL.
      window_days: filter for "Top 10 high-confidence learnings (last N
        days)" — pass 0 for "no time filter" (returns all).
      top_n: top-N cap for the high-confidence section (default 10).
      now: pinned clock for deterministic testing.
    """
    del memory_root  # accepted for API symmetry; layout is canonical.
    root = _resolve_repo_root(repo_root)
    pinned_now = _normalise_now(now)

    operational_path = _resolve_operational_jsonl(root, operational_jsonl)
    external_path = _resolve_external_jsonl(root, external_jsonl)

    entries = _load_jsonl_entries(operational_path)
    external_reviews = _load_jsonl_entries(external_path)

    by_task_type = _aggregate_by_task_type(entries)
    top_learnings = _select_top_learnings(
        entries,
        window_days=window_days,
        top_n=top_n,
        now=pinned_now,
    )
    pinned = sum(1 for e in entries if str(e.get("pinned_for_session", "")).strip())

    template = _env().get_template("memory_report.md.j2")
    return template.render(
        last_updated=_format_iso(pinned_now),
        total=len(entries),
        pinned=pinned,
        window_days=window_days,
        by_task_type=by_task_type,
        top_learnings=top_learnings,
        external_reviews=external_reviews[:10],
    )


def render_rules_report(
    *,
    repo_root: Path | None = None,
    rules_root: Path | None = None,
    now: datetime | None = None,
) -> str:
    """Render the ``.rules/REPORT.md`` text.

    Counts rule headings per layer (matching ``^#+ [A-Z]{1,3}-\\d+`` —
    ``## S-1``, ``### ST-12``, etc.) across the canonical 5 layers, parses
    each layer's ``alwaysApply:`` frontmatter, estimates token cost via the
    same ``len(text) // 4`` heuristic the lint module uses (Rule C-9), and
    reads ``.rules/.compile-hashes.json`` for compile-target status.
    """
    root = _resolve_repo_root(repo_root)
    rules_dir = _resolve_under_root(root, rules_root, Path(".rules"))
    pinned_now = _normalise_now(now)

    layers, total_rules = _enumerate_rule_layers(rules_dir)
    targets, drift_status = _enumerate_compile_targets(root, rules_dir)

    template = _env().get_template("rules_report.md.j2")
    return template.render(
        last_updated=_format_iso(pinned_now),
        layer_count=len(layers),
        total_rules=total_rules,
        drift_status=drift_status,
        layers=layers,
        targets=targets,
    )


def render_human_report(
    version: str,
    trace: Mapping[str, RequirementTraceResult] | None = None,
    *,
    repo_root: Path | None = None,
    requirements_path: Path | None = None,
    test_results: Mapping[str, object] | None = None,
    findings: Iterable[object] | None = None,
    verdict: str | None = None,
    next_step: str | None = None,
    author_layer: str = "L0",
    stagnation: bool = False,
    now: datetime | None = None,
) -> str:
    """Render the FIFTH flavour — the human convergence report (design §4a).

    This is the OUTPUT-side counterpart to the INPUT-side plan-mode
    ingestion: a conclusion-first, budget-capped Markdown report whose
    line-1 ``Status`` enum is DERIVED from two distinct producers (design
    §6c / finding F-2):

    1. **Per-REQ evidence rows** come from :func:`trace_requirements`
       (Wave-3) — REQ-ID → ``(result, evidence)`` joined from
       ``requirements.md``'s ``## Traceability`` matrix. This module does
       NOT reimplement that trace; it consumes it.
    2. **Blocking / Advisory finding sections** come from ``findings`` (the
       composite gate's ``findings_by_severity``): ``blocker`` / ``critical``
       → Blocking; ``major`` / ``minor`` / ``info`` → Advisory.

    The ``Status`` enum is then derived (design §4a):

    * ``passed`` — every traced REQ is ``met`` AND there are no blocking
      findings.
    * ``gaps_found`` — at least one REQ is ``partial`` / ``unmet`` and there
      are no blocking findings (advisory-resolvable).
    * ``human_needed`` — at least one blocking finding (maps to P4
      escalation).

    Args:
      version: the cycle version (e.g. ``v14.1.0``) — both the report H1 and
        the per-cycle output filename derive from it.
      trace: a pre-computed ``{REQ-ID -> RequirementTraceResult}`` map (the
        :func:`trace_requirements` output). When supplied it is consumed
        directly and ``requirements_path`` is ignored; when ``None`` the map
        is derived from ``requirements_path``.
      repo_root: repo root (default: ``Path.cwd()``); a relative
        ``requirements_path`` resolves against it.
      requirements_path: path to ``input/requirements.md`` (or a per-domain
        shard), used only when ``trace`` is ``None``. ``None`` → no REQ rows
        (an empty-trace report). A provided path that does NOT exist raises
        :class:`FileNotFoundError` (loud per S-5 — never a silent empty
        trace).
      test_results: optional ``{node-id -> TestOutcome}`` map (the
        :func:`parse_pytest_report` output) threaded into the §6c
        :func:`trace_requirements` join; used only when ``trace`` is ``None``
        (a pre-computed ``trace`` is already joined). When supplied, a REQ
        whose ``Acceptance`` names a known pytest node-id is keyed off the
        actual PASS/FAIL outcome.
      findings: an iterable of gate findings — each either a mapping or an
        object carrying a ``severity`` plus a description/suggestion. ``None``
        → no findings.
      verdict: optional override for the ``## Verdict`` prose; a conclusion-
        first default is derived from the status when omitted.
      next_step: optional override for the ``## Next step`` line; an
        owner+action default is derived from the status when omitted.
      author_layer: author layer stamp for the header (default ``L0``).
      stagnation: when ``True`` the status is forced to ``human_needed`` (the
        W-8/SI-9 score-stagnation → P4 escalation path; design §4a).
      now: pinned clock for deterministic testing (AC-5 idempotency).

    Returns:
      The convergence report Markdown text (callers — typically
      :func:`regenerate_all` — decide whether to write it to disk).

    Raises:
      FileNotFoundError: when ``requirements_path`` is given but absent.
      RequirementsTraceError: when ``requirements_path`` is not path-like.
    """
    root = _resolve_repo_root(repo_root)
    pinned_now = _normalise_now(now)

    trace_results = _resolve_human_trace(root, trace, requirements_path, test_results)
    blocking, advisory = _split_findings(findings)
    status = _derive_human_status(trace_results, blocking, stagnation=stagnation)

    req_rows = [
        {
            "req_id": r.req_id,
            "criterion": r.criterion,
            "result": r.result,
            "evidence": r.evidence,
        }
        for r in trace_results.values()
    ]
    total = len(trace_results)
    satisfied = sum(1 for r in trace_results.values() if r.result == "met")

    if verdict is None:
        verdict = _default_verdict(status, satisfied, total, blocking, advisory)
    if next_step is None:
        next_step = _default_next_step(status, blocking, trace_results)

    template = _env().get_template("human_report.md.j2")
    return template.render(
        version=version,
        status=status,
        date=_format_date(pinned_now),
        author_layer=author_layer,
        verdict=verdict,
        req_rows=req_rows,
        blocking=blocking,
        advisory=advisory,
        next_step=next_step,
    )


def render_human_digest(
    version: str,
    trace: Mapping[str, RequirementTraceResult] | None = None,
    *,
    repo_root: Path | None = None,
    requirements_path: Path | None = None,
    test_results: Mapping[str, object] | None = None,
    findings: Iterable[object] | None = None,
    where_we_are: str | None = None,
    stagnation: bool = False,
    now: datetime | None = None,
) -> str:
    """Render the read-first human DIGEST (design §4b — ≤100-line surface).

    The digest is the "read-once, know where we are" surface. It lists only
    THIS-cycle REQ deltas (≤1 line each) — a REQ delta is "this-cycle" when
    its matrix ``Cycle`` cell equals ``version`` (finding F-3; the matrix
    ``Cycle`` column is parsed by :func:`trace_requirements`). A REQ with a
    blank/absent ``Cycle`` is treated as this-cycle so pre-v14.1.0 matrices
    (no ``Cycle`` column) keep listing every delta (backward compatible). The
    rollup count line (``N total · M satisfied · K blocked``) always counts
    the FULL durable REQ set so it stays a stable "where are we overall"
    signal; the full REQ→status matrix lives in ``input/requirements.md``.
    "Open asks" surfaces BLOCKING findings ONLY (advisory lives in the
    convergence report).

    Shares the §6c two-producer derivation with :func:`render_human_report`
    so the digest ``Status`` line agrees with the convergence report's.

    Args:
      version: the latest cycle version.
      trace: a pre-computed ``{REQ-ID -> RequirementTraceResult}`` map; when
        supplied it is consumed directly and ``requirements_path`` is ignored.
      repo_root: repo root (default: ``Path.cwd()``).
      requirements_path: path to ``input/requirements.md`` (or shard), used
        only when ``trace`` is ``None``; same S-5 semantics as
        :func:`render_human_report`.
      test_results: optional ``{node-id -> TestOutcome}`` map threaded into
        the §6c join (used only when ``trace`` is ``None``).
      findings: gate findings (same shape as :func:`render_human_report`).
      where_we_are: optional override for the ``## Where we are`` block.
      stagnation: when ``True`` the status is forced to ``human_needed``
        (W-8/SI-9 escalation; agrees with :func:`render_human_report`).
      now: pinned clock for deterministic testing (AC-5 idempotency).

    Returns:
      The DIGEST Markdown text.
    """
    root = _resolve_repo_root(repo_root)
    pinned_now = _normalise_now(now)

    trace_results = _resolve_human_trace(root, trace, requirements_path, test_results)
    blocking, _advisory = _split_findings(findings)
    status = _derive_human_status(trace_results, blocking, stagnation=stagnation)

    # §4b/F-3: the digest lists only THIS-cycle REQ deltas (matrix Cycle ==
    # version); a blank Cycle is this-cycle (back-compat with pre-v14.1.0
    # matrices that carry no Cycle column).
    req_deltas = [
        {"req_id": r.req_id, "result": r.result}
        for r in trace_results.values()
        if not r.cycle or r.cycle == version
    ]
    # The rollup counts the FULL durable REQ set (not the cycle-filtered view).
    total = len(trace_results)
    satisfied = sum(1 for r in trace_results.values() if r.result == "met")
    blocked = sum(1 for r in trace_results.values() if r.result == "unmet")
    open_asks = [b["text"] for b in blocking]

    if where_we_are is None:
        where_we_are = _default_where_we_are(status, version, satisfied, total)

    template = _env().get_template("human_digest.md.j2")
    return template.render(
        version=version,
        status=status,
        updated=_format_date(pinned_now),
        where_we_are=where_we_are,
        open_asks=open_asks,
        req_deltas=req_deltas,
        rollup_total=total,
        rollup_satisfied=satisfied,
        rollup_blocked=blocked,
        convergence_rel=f"output/convergence/{version}-convergence.md",
    )


# ---------------------------------------------------------------------------
# Public orchestrator + canonical write paths
# ---------------------------------------------------------------------------


def regenerate_all(
    repo_root: Path | None = None,
    *,
    now: datetime | None = None,
    archive_window_days: int = DEFAULT_ARCHIVE_WINDOW_DAYS,
    memory_window_days: int = DEFAULT_MEMORY_WINDOW_DAYS,
    human_version: str | None = None,
    human_requirements_path: Path | None = None,
    human_test_results: Mapping[str, object] | None = None,
    human_findings: Iterable[object] | None = None,
    human_stagnation: bool = False,
) -> dict[str, object]:
    """Regenerate the REPORT.md files at the canonical paths.

    Always regenerates the four agent-facing flavours (workspace / memory /
    rules / per-change). The FIFTH human flavour (design §4 / §6c) is opt-in:
    it renders ONLY when ``human_version`` is supplied, because the
    convergence report path is per-cycle (``<version>-convergence.md``) and
    the digest derives from the same cycle.

    Args:
      repo_root: repo root (default: ``Path.cwd()``).
      now: pinned clock — passed to every renderer so a fixed value yields
        byte-identical outputs across calls (AC-5 idempotency).
      archive_window_days: window for the workspace report's archived
        changes table (default 7 days per design.md §5.2).
      memory_window_days: window for the memory report's "Top 10
        high-confidence learnings" section (default 30 days per
        design.md §5.3).
      human_version: when supplied, also render + write the human
        convergence report (``output/convergence/<version>-convergence.md``)
        and refresh the digest (``output/DIGEST.md``).
      human_requirements_path: path to ``input/requirements.md`` for the
        per-REQ evidence rows (consumed via :func:`trace_requirements`).
      human_test_results: optional ``{node-id -> TestOutcome}`` map threaded
        into the §6c test-run join (typically :func:`parse_pytest_report`).
      human_findings: gate findings feeding the blocking/advisory split.
      human_stagnation: when ``True`` the human status is forced to
        ``human_needed`` (W-8/SI-9 escalation).

    Returns:
      Dict with keys ``"workspace"``, ``"memory"``, ``"rules"`` (each
      mapped to a single :class:`Path`) plus ``"changes"`` (list of
      :class:`Path` for every per-archive REPORT) and ``"human"`` (a
      ``{"convergence": Path, "digest": Path}`` mapping when
      ``human_version`` was supplied, else ``None``). The plural
      ``changes`` key was chosen over the singular ``change`` so callers can
      tell "one report for the change folder" from "many reports across all
      archives" at a glance.

    Idempotency: with a pinned ``now``, two successive invocations
    produce byte-identical files for every output path.
    """
    root = _resolve_repo_root(repo_root)
    pinned_now = _normalise_now(now)

    workspace_text = render_workspace_report(
        repo_root=root,
        archive_window_days=archive_window_days,
        now=pinned_now,
    )
    memory_text = render_memory_report(
        repo_root=root,
        window_days=memory_window_days,
        now=pinned_now,
    )
    rules_text = render_rules_report(repo_root=root, now=pinned_now)

    workspace_path = _write_report(root / WORKSPACE_REPORT_PATH_DEFAULT, workspace_text)
    memory_path = _write_report(root / MEMORY_REPORT_PATH_DEFAULT, memory_text)
    rules_path = _write_report(root / RULES_REPORT_PATH_DEFAULT, rules_text)

    change_paths: list[Path] = []
    store = _make_store(root)
    for date_prefix, change_id in store.list_archive():
        archive_folder = store.archive_root / f"{date_prefix}-{change_id}"
        try:
            text = render_change_report(
                change_id,
                repo_root=root,
                now=pinned_now,
            )
        except (ChangeNotFoundError, DeltaSpecParseError) as exc:
            logger.warning(
                "regenerate_all: skipping %s (%s)",
                change_id,
                exc,
            )
            continue
        change_paths.append(_write_report(archive_folder / "REPORT.md", text))

    human_result: dict[str, Path] | None = None
    if human_version is not None:
        convergence_text = render_human_report(
            human_version,
            repo_root=root,
            requirements_path=human_requirements_path,
            test_results=human_test_results,
            findings=human_findings,
            stagnation=human_stagnation,
            now=pinned_now,
        )
        digest_text = render_human_digest(
            human_version,
            repo_root=root,
            requirements_path=human_requirements_path,
            test_results=human_test_results,
            findings=human_findings,
            stagnation=human_stagnation,
            now=pinned_now,
        )
        convergence_path = _write_report(
            root / _human_convergence_path(human_version), convergence_text
        )
        digest_path = _write_report(root / HUMAN_DIGEST_PATH_DEFAULT, digest_text)
        human_result = {"convergence": convergence_path, "digest": digest_path}

    return {
        "workspace": workspace_path,
        "memory": memory_path,
        "rules": rules_path,
        "changes": change_paths,
        "human": human_result,
    }


# ---------------------------------------------------------------------------
# Helpers — Jinja2 environment, path resolution, deterministic formatting
# ---------------------------------------------------------------------------


def _env() -> Environment:
    """Return the module-level Jinja2 :class:`Environment`.

    Constructed lazily on first call; cached on the function for
    subsequent invocations. ``StrictUndefined`` so any template variable
    typo surfaces loudly (Rule S-5: no silent failures).
    """
    cached = getattr(_env, "_cached", None)
    if cached is not None:
        return cached
    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701 — we render Markdown, not HTML.
    )
    _env._cached = env  # type: ignore[attr-defined]
    return env


def _resolve_repo_root(repo_root: Path | None) -> Path:
    return Path(repo_root) if repo_root is not None else Path.cwd()


def _resolve_under_root(root: Path, override: Path | None, default: Path) -> Path:
    """Resolve ``override`` (or ``default``) against ``root`` if relative."""
    target = Path(override) if override is not None else Path(default)
    return target if target.is_absolute() else root / target


def _make_store(
    root: Path,
    active_root: Path | None = None,
    archive_root: Path | None = None,
) -> ChangeStore:
    """Build a :class:`ChangeStore` rooted at ``root`` with optional overrides."""
    store = ChangeStore(repo_root=root)
    if active_root is not None:
        store.active_dir = (
            Path(active_root) if Path(active_root).is_absolute() else Path(active_root)
        )
    if archive_root is not None:
        store.archive_dir = (
            Path(archive_root) if Path(archive_root).is_absolute() else Path(archive_root)
        )
    return store


def _normalise_now(now: datetime | None) -> datetime:
    """Return ``now`` (or :func:`datetime.now` if absent), forced to UTC tz."""
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _format_iso(dt: datetime) -> str:
    """Format ``dt`` as ``YYYY-MM-DDTHH:MM:SSZ`` (matches handoff schema)."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_date(dt: datetime) -> str:
    """Format ``dt`` as ``YYYY-MM-DD`` (the human-surface date granularity)."""
    return dt.astimezone(UTC).strftime("%Y-%m-%d")


def _write_report(path: Path, text: str) -> Path:
    """Write ``text`` to ``path`` with a trailing newline; return ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text = text + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


# ---------------------------------------------------------------------------
# Helpers — human convergence report + digest (design §4 / §6c)
# ---------------------------------------------------------------------------


def _human_convergence_path(version: str) -> Path:
    """Return the per-cycle convergence report path (relative to repo root)."""
    return HUMAN_OUTPUT_DIR_DEFAULT / "convergence" / f"{version}-convergence.md"


def _resolve_requirements_path(root: Path, requirements_path: Path | None) -> Path | None:
    """Resolve ``requirements_path`` against ``root`` if relative; ``None`` passthrough."""
    if requirements_path is None:
        return None
    path = Path(requirements_path)
    return path if path.is_absolute() else root / path


def _trace_human_requirements(
    root: Path,
    requirements_path: Path | None,
    test_results: Mapping[str, object] | None = None,
) -> dict[str, RequirementTraceResult]:
    """Consume the Wave-3 :func:`trace_requirements` producer (design §6c).

    Returns an empty mapping when no requirements path is supplied. A
    supplied-but-absent path is NOT swallowed — :func:`trace_requirements`
    raises :class:`FileNotFoundError` (S-5: no silent empty trace). When
    ``test_results`` is supplied it is threaded into the §6c test-run join.
    """
    resolved = _resolve_requirements_path(root, requirements_path)
    if resolved is None:
        return {}
    return trace_requirements(resolved, test_results=test_results)


def _resolve_human_trace(
    root: Path,
    trace: Mapping[str, RequirementTraceResult] | None,
    requirements_path: Path | None,
    test_results: Mapping[str, object] | None = None,
) -> dict[str, RequirementTraceResult]:
    """Resolve the per-REQ trace map the render consumes (design §6c).

    A caller-supplied ``trace`` map wins (the explicit "accept a trace map"
    contract — the render NEVER recomputes when handed one, so ``test_results``
    is ignored in that case: a pre-computed trace is already joined);
    otherwise the map is produced from ``requirements_path`` via the Wave-3
    :func:`trace_requirements` producer, threading ``test_results`` into the
    §6c join. A non-mapping ``trace`` is rejected loudly (S-5: no silent
    failure, no silent empty trace).
    """
    if trace is not None:
        if not isinstance(trace, Mapping):
            raise TypeError(
                "render_human_report: trace must be a "
                "Mapping[str, RequirementTraceResult], got "
                f"{type(trace).__name__}"
            )
        return dict(trace)
    return _trace_human_requirements(root, requirements_path, test_results)


def _finding_field(finding: object, *names: str) -> str:
    """Return the first present mapping-key / attribute among ``names``.

    Accepts both mapping findings (``finding_by_severity`` dicts) and object
    findings (e.g. :class:`devolaflow.gate.models.Finding`). The value is
    stringified and stripped; absent / ``None`` fields are skipped.
    """
    for name in names:
        value = finding.get(name) if isinstance(finding, Mapping) else getattr(finding, name, None)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _split_findings(
    findings: Iterable[object] | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split ``findings`` into ``(blocking, advisory)`` rows by severity.

    Mirrors ``gate/scorer.py`` severity handling: ``blocker`` / ``critical``
    → blocking (each carries the required action); ``major`` / ``minor`` /
    ``info`` → advisory. A finding with an UNRECOGNISED severity is NOT
    dropped (S-5: no silent failure) — it is logged at WARNING and routed to
    advisory so a derived ``Status`` can never silently over-claim ``passed``
    on a malformed finding while still surfacing it in the report.
    """
    blocking: list[dict[str, str]] = []
    advisory: list[dict[str, str]] = []
    for finding in findings or []:
        severity = _finding_field(finding, "severity").lower()
        text = (
            _finding_field(finding, "description", "text", "summary", "message")
            or "<unspecified finding>"
        )
        if severity in _BLOCKING_SEVERITIES:
            action = (
                _finding_field(finding, "suggestion", "action", "required_action")
                or "resolve before human approval"
            )
            blocking.append({"text": text, "action": action})
        elif severity in _ADVISORY_SEVERITIES:
            advisory.append({"text": text})
        else:
            logger.warning(
                "render_human_report: finding %r has unrecognised severity %r; "
                "routing to advisory (not dropped)",
                text,
                severity,
            )
            advisory.append({"text": text})
    return blocking, advisory


def _derive_human_status(
    trace_results: dict[str, RequirementTraceResult],
    blocking: list[dict[str, str]],
    *,
    stagnation: bool = False,
) -> str:
    """Derive the line-1 ``Status`` enum from the trace + blocking findings.

    Per design §4a: ``human_needed`` when any blocking finding exists OR when
    ``stagnation`` is set (the W-8/SI-9 "score stagnated 2+ rounds" → P4
    escalation path); else ``gaps_found`` when any REQ is ``partial`` /
    ``unmet``; else ``passed`` (all REQ ``met``, no blockers — vacuously true
    for an empty trace).
    """
    if blocking or stagnation:
        return HUMAN_STATUS_HUMAN_NEEDED
    if any(r.result in ("partial", "unmet") for r in trace_results.values()):
        return HUMAN_STATUS_GAPS_FOUND
    return HUMAN_STATUS_PASSED


def _default_verdict(
    status: str,
    satisfied: int,
    total: int,
    blocking: list[dict[str, str]],
    advisory: list[dict[str, str]],
) -> str:
    """Build a conclusion-first ``## Verdict`` line when none is supplied."""
    phrase = {
        HUMAN_STATUS_PASSED: "Converged",
        HUMAN_STATUS_GAPS_FOUND: "Gaps remain",
        HUMAN_STATUS_HUMAN_NEEDED: "Human decision required",
    }[status]
    return (
        f"{phrase}: {satisfied}/{total} traced requirement(s) met; "
        f"{len(blocking)} blocking, {len(advisory)} advisory finding(s)."
    )


def _default_next_step(
    status: str,
    blocking: list[dict[str, str]],
    trace_results: dict[str, RequirementTraceResult],
) -> str:
    """Build an owner+action ``## Next step`` line when none is supplied."""
    if status == HUMAN_STATUS_HUMAN_NEEDED:
        return (
            f"Human → resolve {len(blocking)} blocking finding(s) before approval (owner: human)."
        )
    if status == HUMAN_STATUS_GAPS_FOUND:
        gaps = sum(1 for r in trace_results.values() if r.result in ("partial", "unmet"))
        return (
            f"L0 → close {gaps} unmet/partial requirement(s); advisory-resolvable, "
            f"no human gate (owner: L0)."
        )
    return "L0 → none required; all traced requirements met with no blocking findings (owner: L0)."


def _default_where_we_are(status: str, version: str, satisfied: int, total: int) -> str:
    """Build the ``## Where we are`` digest line when none is supplied."""
    return f"Cycle {version}: status {status} — {satisfied}/{total} traced requirement(s) met."


# ---------------------------------------------------------------------------
# Helpers — change folder lookup + per-change extractors
# ---------------------------------------------------------------------------


def _find_change_folder(change_id: str, archive_dir: Path, active_dir: Path) -> Path:
    """Find ``change_id`` in archive first, then fall back to active.

    The archive scan is linear because the date prefix is unknown; the
    active lookup is direct (``active_dir / change_id``).
    """
    if archive_dir.is_dir():
        for child in sorted(archive_dir.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            stripped = name
            m = _ARCHIVE_DATE_PREFIX_RE.match(name)
            if m:
                stripped = name[len(m.group(0)) :]
            if stripped == change_id:
                return child
    active_path = active_dir / change_id
    if active_path.is_dir():
        return active_path
    raise ChangeNotFoundError(
        f"render_change_report: change {change_id!r} not found under "
        f"{archive_dir!s} or {active_dir!s}"
    )


def _archive_date_from_folder(folder: Path) -> str:
    """Extract the ``YYYY-MM-DD`` prefix from an archive folder; ``"<active>"`` if absent."""
    m = _ARCHIVE_DATE_PREFIX_RE.match(folder.name)
    if m:
        return m.group(1)
    return "<active>"


def _compute_duration(goal_md: str, status: dict) -> str:
    """Compute archive duration as ``hh:mm:ss`` from goal.created → status.last_updated.

    Returns ``"<unknown>"`` when either timestamp is missing or unparseable.
    """
    created_str = _extract_goal_created(goal_md)
    last_updated = str(status.get("last_updated", "")).strip()
    if not (created_str and last_updated):
        return "<unknown>"
    try:
        created = _parse_iso8601(created_str)
        finished = _parse_iso8601(last_updated)
    except ValueError:
        return "<unknown>"
    delta = finished - created
    if delta.total_seconds() < 0:
        return "<unknown>"
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _extract_goal_created(goal_md: str) -> str:
    """Return the ``created`` field from goal.md frontmatter (``""`` if absent)."""
    fm = _parse_frontmatter(goal_md)
    return str(fm.get("created", "")).strip()


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a markdown string; ``{}`` if absent or malformed."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    close_idx = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break
    if close_idx < 0:
        return {}
    fm_text = "\n".join(lines[1:close_idx])
    try:
        parsed = yaml.safe_load(fm_text) if fm_text.strip() else {}
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_iso8601(text: str) -> datetime:
    """Parse an ISO-8601 timestamp; trailing ``Z`` is treated as UTC."""
    cleaned = text.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _extract_delta_sections(spec_md: str) -> list[dict]:
    """Return ``[{kind, heading}, ...]`` for every Requirement in spec.md."""
    if not spec_md.strip():
        return []
    try:
        delta = parse_delta_spec(spec_md)
    except DeltaSpecParseError as exc:
        logger.info("change_report: skipping spec.md delta extraction: %s", exc)
        return []
    rows: list[dict] = []
    for kind in DELTA_SECTION_KINDS:
        for req in delta.section(kind):
            rows.append({"kind": kind, "heading": req.heading})
    return rows


def _extract_goal_why(goal_md: str) -> str:
    """Return the verbatim text under goal.md's ``## Why`` heading; ``""`` if absent."""
    if not goal_md:
        return ""
    lines = goal_md.splitlines()
    why_buffer: list[str] = []
    in_why = False
    for line in lines:
        if _WHY_HEADING_RE.match(line):
            in_why = True
            continue
        if in_why:
            if line.startswith("## "):
                break
            why_buffer.append(line)
    text = "\n".join(why_buffer).strip()
    return text


def _extract_purpose(spec_md: str) -> str:
    """Return the verbatim text under spec.md's ``## Purpose`` heading."""
    if not spec_md.strip():
        return ""
    try:
        delta = parse_delta_spec(spec_md)
    except DeltaSpecParseError:
        return ""
    return delta.purpose.strip()


def _extract_task_groups(tasks_md: str) -> list[str]:
    """Return the list of ``## N. <group title>`` headings from tasks.md."""
    if not tasks_md:
        return []
    groups: list[str] = []
    for line in tasks_md.splitlines():
        m = _TASK_GROUP_RE.match(line)
        if m:
            groups.append(m.group(1).strip())
    return groups


def _parse_learnings_jsonl(jsonl: str | None) -> list[dict]:
    """Parse a per-change ``learnings.jsonl`` blob into a list of dicts."""
    if not jsonl:
        return []
    entries: list[dict] = []
    for raw in jsonl.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.info("change_report: skipping malformed learnings.jsonl line: %s", exc)
            continue
        if not isinstance(obj, dict):
            continue
        entries.append(obj)
    entries.sort(key=lambda e: float(e.get("confidence", 0.0)), reverse=True)
    return entries


def _summarise_handoff_chain(change_id: str, change_folder: Path, root: Path) -> list[str]:
    """Return a one-line-per-hop summary of every handoff envelope for ``change_id``.

    Reads the frozen ``handoff_chain.yaml`` from the archive folder when
    present (per design.md §1.1 — archive folder ships the compacted
    ledger); otherwise falls back to live envelopes under
    ``.local/.agent/handoff/``.
    """
    frozen = change_folder / "handoff_chain.yaml"
    hops: list[str] = []
    if frozen.exists():
        try:
            data = yaml.safe_load(frozen.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            data = None
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                hops.append(_format_handoff_hop(item))
            return hops
        if isinstance(data, dict) and isinstance(data.get("envelopes"), list):
            for item in data["envelopes"]:
                hops.append(_format_handoff_hop(item))
            return hops

    live = HandoffStore(repo_root=root, handoff_dir=Path(HANDOFF_DIR_DEFAULT))
    if not live.handoff_root.is_dir():
        return []
    for path in sorted(live.list_envelope_files_for(change_id)):
        try:
            envelope = HandoffEnvelope.from_yaml(path.read_text(encoding="utf-8"))
        except HandoffStoreError as exc:
            logger.info("change_report: skipping malformed envelope %s: %s", path.name, exc)
            continue
        hops.append(
            f"seq {envelope.seq:04d}: {envelope.from_layer} → {envelope.to_layer} "
            f"({envelope.envelope_kind})"
        )
    return hops


def _format_handoff_hop(item: dict) -> str:
    """Format one envelope dict as a one-line summary."""
    seq = int(item.get("seq", 0))
    src = str(item.get("from_layer", "?"))
    dst = str(item.get("to_layer", "?"))
    kind = str(item.get("envelope_kind", "?"))
    return f"seq {seq:04d}: {src} → {dst} ({kind})"


def _verification_block(status: dict) -> dict[str, str]:
    """Pull verification metrics from STATUS.yaml; fall back to ``"<unknown>"``.

    The schema declares ``verify_pass`` (bool) and ``gate_score`` (float)
    as the only required verification fields; ``ac_pass_rate`` /
    ``tests_passed`` / ``coverage`` / ``lint`` / ``format`` are optional
    extension fields populated by the v8.2.6 verify stage when present.
    """
    verification = status.get("verification") or {}
    if not isinstance(verification, dict):
        verification = {}

    def _get(key: str, default: str = "<unknown>") -> str:
        if key in verification:
            return _stringify(verification[key])
        if key in status:
            return _stringify(status[key])
        return default

    gate_score_raw = status.get("gate_score")
    if gate_score_raw is None:
        gate_score = "<unknown>"
    else:
        try:
            gate_score = f"{float(gate_score_raw):.2f}/10"
        except (TypeError, ValueError):
            gate_score = "<unknown>"

    coverage_raw = _get("coverage_pct", default="")
    if not coverage_raw or coverage_raw == "<unknown>":
        coverage = "<unknown>"
    else:
        try:
            coverage = f"{float(coverage_raw):.1f}%"
        except (TypeError, ValueError):
            coverage = coverage_raw

    return {
        "ac_pass_rate": _get("ac_pass_rate"),
        "tests_passed": _get("tests_passed"),
        "coverage": coverage,
        "lint": _get("lint"),
        "format": _get("format"),
        "gate_score": gate_score,
    }


def _stringify(value: object) -> str:
    """Render ``value`` for table-cell use (``True`` → ``"pass"``, ``False`` → ``"fail"``)."""
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    if value is None:
        return "<unknown>"
    return str(value)


# ---------------------------------------------------------------------------
# Helpers — workspace report
# ---------------------------------------------------------------------------


def _collect_active_changes(store: ChangeStore) -> list[dict]:
    """Build the rows for the workspace report's "Active changes" table."""
    rows: list[dict] = []
    for change_id in store.list_active():
        try:
            change = store.get(change_id)
        except (ChangeNotFoundError, KeyError) as exc:
            logger.info("workspace_report: skipping active change %s: %s", change_id, exc)
            continue
        rows.append(
            {
                "id": change_id,
                "state": _stringify(change.status.get("state", "<unknown>")),
                "percent": int(change.status.get("percent_complete", 0)),
                "owner": _stringify(change.status.get("owner_layer", "<unknown>")),
                "last_touch": _stringify(change.status.get("last_updated", "<unknown>")),
            }
        )
    return rows


def _collect_archived_changes(
    store: ChangeStore,
    *,
    window_days: int,
    now: datetime,
) -> list[dict]:
    """Build the rows for the workspace report's "Recently archived" table.

    Filters out archives whose date prefix is more than ``window_days``
    days older than ``now``. The filter window is inclusive (an archive
    dated exactly ``now - window_days`` IS included).
    """
    cutoff = (now - timedelta(days=window_days)).date()
    rows: list[dict] = []
    for date_prefix, change_id in store.list_archive():
        archive_date = _safe_parse_date(date_prefix)
        if archive_date is None:
            logger.info("workspace_report: skipping archive with bad date %r", date_prefix)
            continue
        if archive_date < cutoff:
            continue
        try:
            change = store.get(change_id)
        except (ChangeNotFoundError, KeyError) as exc:
            logger.info("workspace_report: skipping archived %s: %s", change_id, exc)
            continue
        duration = _compute_duration(change.goal_md, change.status)
        gate_score_raw = change.status.get("gate_score")
        if gate_score_raw is None:
            gate_score = "<unknown>"
        else:
            try:
                gate_score = f"{float(gate_score_raw):.2f}/10"
            except (TypeError, ValueError):
                gate_score = "<unknown>"
        rows.append(
            {
                "id": change_id,
                "archived_date": date_prefix,
                "duration": duration,
                "gate_score": gate_score,
            }
        )
    return rows


def _safe_parse_date(prefix: str) -> date | None:
    try:
        return datetime.strptime(prefix, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Helpers — memory report
# ---------------------------------------------------------------------------


def _resolve_operational_jsonl(root: Path, override: Path | None) -> Path:
    """Return the path to the operational learnings JSONL.

    Mirrors :func:`devolaflow.learnings.resolve_learnings_path` but does
    not call it (avoids any chance of an accidental import-time side
    effect on the JSONL file). Strict precedence:

    1. explicit ``override`` argument (if not absolute, resolved against
       ``root``).
    2. ``.local/memory/operational.jsonl`` if it exists.
    3. ``workflow-system/agent/knowledge/learnings/operational.jsonl``
       (canonical, ships under version control even when empty).
    """
    if override is not None:
        return override if override.is_absolute() else root / override
    project_local = root / ".local" / "memory" / "operational.jsonl"
    if project_local.exists():
        return project_local
    return root / "workflow-system" / "agent" / "knowledge" / "learnings" / "operational.jsonl"


def _resolve_external_jsonl(root: Path, override: Path | None) -> Path:
    if override is not None:
        return override if override.is_absolute() else root / override
    project_local = root / ".local" / "memory" / "external-sources.jsonl"
    if project_local.exists():
        return project_local
    return root / "workflow-system" / "agent" / "knowledge" / "learnings" / "external-sources.jsonl"


def _load_jsonl_entries(path: Path) -> list[dict]:
    """Load ``path`` line-by-line; skip malformed JSON entries."""
    if not path.exists():
        return []
    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.info("memory_report: skipping malformed JSONL row: %s", exc)
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _aggregate_by_task_type(entries: Iterable[dict]) -> list[dict]:
    """Aggregate entries into ``[{task_type, count, avg_confidence, pinned}, ...]`` rows."""
    buckets: dict[str, dict] = {}
    for entry in entries:
        task_type = str(entry.get("task_type", "unknown"))
        bucket = buckets.setdefault(
            task_type,
            {"task_type": task_type, "count": 0, "_conf_sum": 0.0, "pinned": 0},
        )
        bucket["count"] += 1
        with contextlib.suppress(TypeError, ValueError):
            bucket["_conf_sum"] += float(entry.get("confidence", 0.0))
        if str(entry.get("pinned_for_session", "")).strip():
            bucket["pinned"] += 1
    rows = []
    for bucket in buckets.values():
        count = bucket["count"]
        avg = bucket["_conf_sum"] / count if count else 0.0
        rows.append(
            {
                "task_type": bucket["task_type"],
                "count": count,
                "avg_confidence": avg,
                "pinned": bucket["pinned"],
            }
        )
    rows.sort(key=lambda r: r["task_type"])
    return rows


def _select_top_learnings(
    entries: Iterable[dict],
    *,
    window_days: int,
    top_n: int,
    now: datetime,
) -> list[dict]:
    """Return the top-``top_n`` entries ranked by confidence × promotion_count.

    Filters out entries whose ``timestamp`` (or, fallback,
    ``last_accessed``) is older than ``window_days`` days. ``window_days
    <= 0`` disables the filter (returns all entries that have an insight).
    """
    cutoff = now - timedelta(days=window_days) if window_days > 0 else None
    scored: list[tuple[float, dict]] = []
    for entry in entries:
        insight = str(entry.get("insight", "")).strip()
        if not insight:
            continue
        ts_str = str(entry.get("timestamp") or entry.get("last_accessed") or "").strip()
        if cutoff is not None and ts_str:
            try:
                ts = _parse_iso8601(ts_str)
            except ValueError:
                ts = None
            if ts is not None and ts < cutoff:
                continue
        try:
            confidence = float(entry.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        promotion = int(entry.get("promotion_count", 0) or 0)
        score = confidence * (1 + promotion)
        scored.append((score, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    rows: list[dict] = []
    for _, entry in scored[:top_n]:
        rows.append(
            {
                "insight": str(entry.get("insight", "")).strip(),
                "confidence": float(entry.get("confidence", 0.0)),
                "promotion_count": int(entry.get("promotion_count", 0) or 0),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Helpers — rules report
# ---------------------------------------------------------------------------


def _enumerate_rule_layers(rules_dir: Path) -> tuple[list[dict], int]:
    """Return ``(layer_rows, total_rules)`` for the rules report."""
    layers: list[dict] = []
    total = 0
    for label, filename in RULES_LAYERS:
        path = rules_dir / filename
        if not path.exists():
            layers.append(
                {
                    "label": label,
                    "file": filename,
                    "rule_count": 0,
                    "always_apply": "<missing>",
                    "token_est": 0,
                }
            )
            continue
        text = path.read_text(encoding="utf-8")
        rule_count = sum(1 for line in text.splitlines() if _RULE_HEADING_RE.match(line))
        total += rule_count
        fm = _parse_frontmatter(text)
        always = fm.get("alwaysApply")
        if always is True:
            always_str = "yes"
        elif always is False:
            always_str = "no"
        else:
            always_str = "<unknown>"
        token_est = len(text) // 4
        layers.append(
            {
                "label": label,
                "file": filename,
                "rule_count": rule_count,
                "always_apply": always_str,
                "token_est": token_est,
            }
        )
    return layers, total


def _enumerate_compile_targets(root: Path, rules_dir: Path) -> tuple[list[dict], str]:
    """Read ``.rules/.compile-hashes.json`` and the compile-config to build target rows.

    Returns ``(target_rows, drift_status)``. ``drift_status`` is ``"OK"``
    when the hash file exists with at least one target entry; ``"stale"``
    when the hash file is empty; ``"missing"`` when absent.
    """
    config_path = rules_dir / "compile-config.yaml"
    config: dict = {}
    if config_path.exists():
        try:
            parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                config = parsed
        except yaml.YAMLError:
            config = {}

    hashes_path = rules_dir / ".compile-hashes.json"
    hashes: dict = {}
    if hashes_path.exists():
        try:
            hashes_data = json.loads(hashes_path.read_text(encoding="utf-8"))
            if isinstance(hashes_data, dict):
                hashes = hashes_data
        except json.JSONDecodeError:
            hashes = {}

    rows: list[dict] = []
    targets_section = config.get("targets") or {}
    if isinstance(targets_section, dict):
        for name, meta in sorted(targets_section.items()):
            if not isinstance(meta, dict):
                continue
            output = str(meta.get("output", "<unknown>"))
            output_path = root / output if not Path(output).is_absolute() else Path(output)
            status = _compile_target_status(name, hashes, output_path)
            rows.append({"name": name, "output": output, "status": status})

    if not hashes_path.exists():
        drift_status = "missing"
    elif not hashes:
        drift_status = "stale"
    else:
        drift_status = "OK"
    return rows, drift_status


def _compile_target_status(name: str, hashes: dict, output_path: Path) -> str:
    """Compute the per-target status string for the rules report table.

    The recorded hash (if any) is always surfaced verbatim; an absent
    output file is appended as a parenthetical so the audit trail keeps
    the hash visible even when the file got moved/cleaned externally.
    """
    recorded_hash = hashes.get(name)
    if not recorded_hash:
        return "no recorded hash"
    if not output_path.exists():
        return f"hash {recorded_hash} (output missing)"
    return f"hash {recorded_hash} on file"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI for ``python -m devolaflow.agent_workspace.reporter``.

    Flags:
      ``--all``          regenerate every report at the canonical paths.
      ``--workspace``    write only ``.local/.agent/REPORT.md``.
      ``--memory``       write only ``.local/memory/REPORT.md``.
      ``--rules``        write only ``.rules/REPORT.md``.
      ``--change <id>``  write only the per-change report (to the change's
                         archive folder, falling back to the active folder
                         when the change is not yet archived).
      ``--human <ver>``  write the human convergence report for ``<ver>`` and
                         refresh the digest (pair with ``--requirements``).
      ``--requirements`` path to ``requirements.md`` for ``--human``.
      ``--repo-root``    pin the repo root (default: cwd).
      ``--print``        write to stdout instead of disk (only valid with
                         a single ``--workspace`` / ``--memory`` /
                         ``--rules`` / ``--change`` flag).

    Returns 0 on success, 2 on usage error, 1 on render failure.
    """
    parser = argparse.ArgumentParser(
        prog="python -m devolaflow.agent_workspace.reporter",
        description="Render REPORT.md files from the v8.2.5 agent workspace tree.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root (default: current working directory)",
    )
    parser.add_argument("--all", action="store_true", help="Regenerate every report.")
    parser.add_argument(
        "--workspace", action="store_true", help="Render only the workspace report."
    )
    parser.add_argument("--memory", action="store_true", help="Render only the memory report.")
    parser.add_argument("--rules", action="store_true", help="Render only the rules report.")
    parser.add_argument(
        "--change",
        type=str,
        default=None,
        help="Render only the per-change report for <change-id>.",
    )
    parser.add_argument(
        "--human",
        type=str,
        default=None,
        metavar="VERSION",
        help="Render the human convergence report for <version> + refresh the digest.",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=None,
        help="Path to requirements.md for --human (REQ-ID -> evidence trace).",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_to_stdout",
        help="Print rendered text to stdout instead of writing to disk "
        "(only valid with a single non-`--all` flavour).",
    )
    parser.add_argument(
        "--archive-window-days",
        type=int,
        default=DEFAULT_ARCHIVE_WINDOW_DAYS,
        help=f"Archive lookback window for the workspace report "
        f"(default: {DEFAULT_ARCHIVE_WINDOW_DAYS} days).",
    )
    parser.add_argument(
        "--memory-window-days",
        type=int,
        default=DEFAULT_MEMORY_WINDOW_DAYS,
        help=f"Memory lookback window for the top-N section "
        f"(default: {DEFAULT_MEMORY_WINDOW_DAYS} days).",
    )
    args = parser.parse_args(argv)

    flavours = sum(
        1
        for flag in (
            args.all,
            args.workspace,
            args.memory,
            args.rules,
            bool(args.change),
            bool(args.human),
        )
        if flag
    )
    if flavours == 0:
        parser.error(
            "specify --all, --workspace, --memory, --rules, --change <id>, or --human <ver>"
        )
    if args.print_to_stdout and (args.all or flavours > 1):
        parser.error("--print is only valid with a single non-`--all` flavour")

    root = _resolve_repo_root(args.repo_root)

    try:
        if args.all:
            results = regenerate_all(
                repo_root=root,
                archive_window_days=args.archive_window_days,
                memory_window_days=args.memory_window_days,
            )
            _print_results(results)
            return 0
        if args.workspace:
            return _emit_one(
                render_workspace_report(
                    repo_root=root,
                    archive_window_days=args.archive_window_days,
                ),
                root / WORKSPACE_REPORT_PATH_DEFAULT,
                to_stdout=args.print_to_stdout,
            )
        if args.memory:
            return _emit_one(
                render_memory_report(
                    repo_root=root,
                    window_days=args.memory_window_days,
                ),
                root / MEMORY_REPORT_PATH_DEFAULT,
                to_stdout=args.print_to_stdout,
            )
        if args.rules:
            return _emit_one(
                render_rules_report(repo_root=root),
                root / RULES_REPORT_PATH_DEFAULT,
                to_stdout=args.print_to_stdout,
            )
        if args.change:
            text = render_change_report(args.change, repo_root=root)
            target = _change_report_target(root, args.change)
            return _emit_one(text, target, to_stdout=args.print_to_stdout)
        if args.human:
            convergence_text = render_human_report(
                args.human,
                repo_root=root,
                requirements_path=args.requirements,
            )
            if args.print_to_stdout:
                return _emit_one(
                    convergence_text,
                    root / _human_convergence_path(args.human),
                    to_stdout=True,
                )
            convergence_path = _write_report(
                root / _human_convergence_path(args.human), convergence_text
            )
            digest_text = render_human_digest(
                args.human,
                repo_root=root,
                requirements_path=args.requirements,
            )
            digest_path = _write_report(root / HUMAN_DIGEST_PATH_DEFAULT, digest_text)
            print(f"wrote {convergence_path}", file=sys.stderr)
            print(f"wrote {digest_path}", file=sys.stderr)
            return 0
    except (ChangeNotFoundError, FileNotFoundError) as exc:
        print(f"reporter: {exc}", file=sys.stderr)
        return 2
    except (DeltaSpecParseError, HandoffStoreError) as exc:
        print(f"reporter: render failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _emit_one(text: str, target: Path, *, to_stdout: bool) -> int:
    if to_stdout:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    written = _write_report(target, text)
    print(f"wrote {written}", file=sys.stderr)
    return 0


def _change_report_target(root: Path, change_id: str) -> Path:
    """Resolve the on-disk REPORT.md path for ``change_id`` (archive then active)."""
    archive_dir = root / ARCHIVE_DIR_DEFAULT
    if archive_dir.is_dir():
        for child in sorted(archive_dir.iterdir()):
            if not child.is_dir():
                continue
            stripped = child.name
            m = _ARCHIVE_DATE_PREFIX_RE.match(child.name)
            if m:
                stripped = child.name[len(m.group(0)) :]
            if stripped == change_id:
                return child / "REPORT.md"
    return root / ACTIVE_DIR_DEFAULT / change_id / "REPORT.md"


def _print_results(results: dict[str, object]) -> None:
    for key in ("workspace", "memory", "rules"):
        path = results.get(key)
        if isinstance(path, Path):
            print(f"wrote {path}", file=sys.stderr)
    changes = results.get("changes") or []
    if isinstance(changes, list):
        for path in changes:
            if isinstance(path, Path):
                print(f"wrote {path}", file=sys.stderr)
    human = results.get("human")
    if isinstance(human, dict):
        for path in human.values():
            if isinstance(path, Path):
                print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover - CLI entry only
    raise SystemExit(main())
