"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


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
        loader=FileSystemLoader(str(Path(__file__).parents[1] / "agent_workspace" / "templates")),
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


def _human_convergence_path(version: str) -> Path:
    """Return the per-cycle convergence report path (relative to repo root)."""
    return HUMAN_OUTPUT_DIR_DEFAULT / "convergence" / f"{version}-convergence.md"


def _check_digest_budget(digest_text: str) -> None:
    """Apply REQ-OUT-01 to the rendered digest (BLOCKING since v14.2.0).

    Hard-ceiling violations propagate as :class:`HumanBudgetExceededError`
    (the emission is refused); the soft tier stays advisory — logged at
    WARNING per S-5 and the write proceeds.
    """
    warning = enforce_digest_budget(digest_text)
    if warning is not None:
        logger.warning(
            "REQ-OUT-01: %s is %d tokens — over the C-9 soft budget of %d "
            "(hard %d); advisory soft tier, digest still emitted",
            warning.filename,
            warning.observed_tokens,
            warning.soft_budget,
            warning.hard_budget,
        )


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


def _extract_task_groups(checklist_md: str) -> list[str]:
    """Return the list of ``## G<n>: <title>`` goal headings from checklist.md."""
    if not checklist_md:
        return []
    groups: list[str] = []
    for line in checklist_md.splitlines():
        m = _TASK_GROUP_RE.match(line)
        if m:
            groups.append(m.group(1).strip())
    return groups


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
