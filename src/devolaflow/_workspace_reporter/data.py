"""Focused implementation slice for report data."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


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


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
