"""Focused implementation slice for report rendering."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


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
    task_groups = _extract_task_groups(change.checklist_md)
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

    ``workspace_root`` is a retained compatibility keyword. It is intentionally
    ignored because the active/archive layout lives at fixed offsets under
    ``repo_root``; supplying it must not change the rendered report.
    """
    del workspace_root  # retained compatibility keyword; layout is canonical.
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


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
