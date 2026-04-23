"""Operational Learnings Module for DevolaFlow.

Captures, persists, and retrieves operational learnings across workflow
executions. Learnings are stored as JSONL (one JSON object per line) and
filtered by task type, confidence, and TTL before injection into agent context.

v7.0.3 (ADR-005) adds four additive schema fields to :class:`Learning`
(`confidence_half_life_days`, `last_accessed`, `pinned_for_session`,
`promotion_count`) plus three helper functions (:func:`consolidate_session`,
:func:`decay_confidence`, :func:`pin_learning_for_session`). Legacy v1
JSONL entries parse unchanged; the migration is lazy per entry.

v7.2.0 (C-007 / CCT-3) adds two further additive schema fields
(`files: list[str]`, `source: str`) plus one helper :func:`dedup_learnings`.
No migration shim is needed — both fields default to safe zero-equivalents
so legacy v1 / v2 JSONL entries parse unchanged.

v7.2.3 (P-03 / C-009) adds :func:`capture_session_reflection` — the writer
that activates the dormant ``operational.jsonl`` substrate v7.2.0 PR-C
shipped. Called at L3 task completion to persist a "pre-completion
reflection" Learning entry that the next session can load via
:func:`load_relevant_learnings`. Read-side already wired via v7.0.3
ADR-005 (the ``session_id`` argument is recorded in ``source_task_id``
so consumers can correlate reflections back to their originating session).

v8.2.0 (PV-03 — Karpathy 4.8 Unified session state) introduces
:mod:`devolaflow.session` as the canonical aggregation surface for
session-derived state (learnings + lifecycle + legibility). This module's
public API is **byte-identical** to v8.1.0-rc.1 — every existing function
remains the source-of-truth for the JSONL substrate and is preserved as a
**deprecated alias** in the sense of R5 (call sites keep working
unchanged; new code SHOULD prefer :class:`devolaflow.session.SessionState`
for cross-domain aggregation). PV-03 adds zero behavioural change here:
SessionState reads from / writes to the same JSONL substrate via the
helpers below, so legacy callers and SessionState-aware callers coexist
on one store. Migration helper: :func:`build_session_state_for` lazily
constructs a populated SessionState without forcing the import (avoids
the obvious circular import risk between `learnings.py` and
`session/state.py`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


__all__ = [
    "ExternalSourceReview",
    "Learning",
    "build_session_state_for",
    "capture_learning",
    "capture_session_reflection",
    "consolidate_session",
    "decay_confidence",
    "dedup_learnings",
    "format_learnings_section",
    "get_learnings_stats",
    "load_relevant_learnings",
    "log_external_source_review",
    "pin_learning_for_session",
    "promote_learning",
    "prune_learnings",
    "load_prefs",
    "resolve_learnings_path",
]


def resolve_learnings_path(cwd: str | Path | None = None) -> Path:
    """Resolve the operational learnings JSONL path.

    Checks ``.local/memory/operational.jsonl`` first (project-local,
    gitignored), then falls back to the canonical repo path under
    ``workflow-system/agent/knowledge/learnings/``.
    """
    base = Path(cwd) if cwd else Path.cwd()
    local_path = base / ".local" / "memory" / "operational.jsonl"
    if local_path.exists():
        return local_path
    canonical = base / "workflow-system" / "agent" / "knowledge" / "learnings" / "operational.jsonl"
    if canonical.exists():
        return canonical
    return local_path


def load_prefs(cwd: str | Path | None = None) -> dict[str, str]:
    """Load personal preferences from ``.local/memory/prefs.md``.

    Returns a dict of key-value pairs parsed from the markdown bullet list.
    Empty dict if the file doesn't exist or has no parseable entries.
    """
    base = Path(cwd) if cwd else Path.cwd()
    prefs_path = base / ".local" / "memory" / "prefs.md"
    if not prefs_path.exists():
        return {}
    prefs: dict[str, str] = {}
    for line in prefs_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and ":" in stripped:
            key, _, value = stripped[2:].partition(":")
            prefs[key.strip().lower()] = value.strip()
    return prefs


DEFAULT_DECAY_HALF_LIFE_DAYS: int = 30
"""Default confidence half-life applied by :func:`decay_confidence` when a
``Learning.confidence_half_life_days`` field is unset or when the caller does
not pass an override. Matches ADR-005 §2.1."""

DECAY_FLOOR: float = 0.1
"""Minimum confidence below which a decayed entry is pruned (ADR-005 §2.2).
Floor is inclusive: values strictly ``< DECAY_FLOOR`` are dropped."""


@dataclass
class Learning:
    """A single operational learning captured from a workflow execution.

    The first nine fields are the pre-v7 schema. The next four are additive
    v2 fields introduced by ADR-005 §2.1. The last two are additive v3 fields
    introduced by C-007 (CCT-3 cluster) and default to safe zero-equivalents
    so legacy JSONL entries parse unchanged.
    """

    stage: str
    task_type: str
    key: str
    insight: str
    confidence: float
    rule_id: str = ""
    timestamp: str = ""
    ttl_days: int = 90
    source_task_id: str = ""
    # v2 additive fields (ADR-005 §2.1) — default-safe for legacy entries.
    confidence_half_life_days: int = DEFAULT_DECAY_HALF_LIFE_DAYS
    last_accessed: str = ""
    pinned_for_session: str = ""
    promotion_count: int = 0
    # v3 additive fields (C-007 / CCT-3) — default-safe for legacy entries.
    files: list[str] = field(default_factory=list)
    source: str = ""

    def __post_init__(self) -> None:
        """Clamp confidence and coerce v2/v3 typed fields."""
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        self.confidence_half_life_days = int(self.confidence_half_life_days)
        self.promotion_count = int(self.promotion_count)
        self.last_accessed = str(self.last_accessed)
        self.pinned_for_session = str(self.pinned_for_session)
        # v3 coercions: tolerate JSONL load with missing/null payloads.
        if self.files is None:
            self.files = []
        else:
            self.files = [str(f) for f in self.files]
        self.source = str(self.source)


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a datetime object."""
    return datetime.fromisoformat(ts)


def _read_lines(jsonl_path: Path) -> list[dict]:
    """Read all valid JSON objects from a JSONL file, skipping malformed lines."""
    if not jsonl_path.exists():
        return []
    entries: list[dict] = []
    for lineno, line in enumerate(jsonl_path.read_text().splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entries.append(json.loads(stripped))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed JSON at %s:%d", jsonl_path, lineno)
    return entries


def capture_learning(learning: Learning, jsonl_path: Path) -> bool:
    """Append a Learning as a JSON line. Skip if duplicate key+stage+task_type exists.

    Returns True if the learning was written, False if skipped as duplicate.
    """
    if not learning.timestamp:
        learning.timestamp = _now_iso()

    existing = _read_lines(jsonl_path)
    for entry in existing:
        if (
            entry.get("key") == learning.key
            and entry.get("stage") == learning.stage
            and entry.get("task_type") == learning.task_type
        ):
            logger.info(
                "Duplicate learning skipped: key=%s stage=%s task_type=%s",
                learning.key,
                learning.stage,
                learning.task_type,
            )
            return False

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(asdict(learning), ensure_ascii=False) + "\n")
    return True


def _entry_ttl_valid(entry: dict, now: datetime) -> bool:
    """Return ``True`` when the entry is within its TTL window.

    Entries without a parseable ``timestamp`` are treated as valid (legacy
    schema tolerance). A malformed timestamp logs a warning and excludes the
    entry — mirrors the pre-refactor behaviour of
    :func:`load_relevant_learnings`.
    """
    ts_str = entry.get("timestamp", "")
    if not ts_str:
        return True
    ttl = int(entry.get("ttl_days", 90))
    try:
        ts = _parse_timestamp(ts_str)
    except (ValueError, TypeError):
        logger.warning("Invalid timestamp in learning: %s", ts_str)
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts + timedelta(days=ttl) > now


def _entry_to_learning(entry: dict) -> Learning | None:
    """Hydrate a JSONL dict into a :class:`Learning`, or ``None`` on failure.

    Drops entries whose payload is missing required dataclass fields. Logs
    a single warning per drop so operators can triage malformed JSONL.
    """
    fields = {k: entry[k] for k in Learning.__dataclass_fields__ if k in entry}
    try:
        return Learning(**fields)
    except (TypeError, KeyError):
        logger.warning("Skipping learning with missing required fields")
        return None


def _is_pinned_for_session(learning: Learning, session_id: str | None) -> bool:
    """Return ``True`` when ``learning`` is pinned for the given session."""
    return bool(
        session_id is not None
        and learning.pinned_for_session
        and learning.pinned_for_session == session_id
    )


def _merge_ranked_learnings(
    pinned: list[Learning],
    unpinned: list[Learning],
    max_entries: int,
) -> list[Learning]:
    """Sort pinned+unpinned by confidence desc and merge without duplicates."""
    pinned.sort(key=lambda item: item.confidence, reverse=True)
    unpinned.sort(key=lambda item: item.confidence, reverse=True)
    seen_keys: set[tuple[str, str, str]] = {(p.stage, p.task_type, p.key) for p in pinned}
    merged: list[Learning] = list(pinned)
    for item in unpinned:
        ident = (item.stage, item.task_type, item.key)
        if ident in seen_keys:
            continue
        merged.append(item)
        seen_keys.add(ident)
    return merged[:max_entries]


def load_relevant_learnings(
    task_type: str,
    jsonl_path: Path,
    min_confidence: float = 0.5,
    max_entries: int = 10,
    session_id: str | None = None,
    change_id: str | None = None,
) -> list[Learning]:
    """Load learnings filtered by task_type, confidence, and TTL expiry.

    Returns up to ``max_entries`` sorted by confidence descending. When
    ``session_id`` is provided, entries whose ``pinned_for_session`` matches
    are surfaced *in addition* to the confidence-sorted top-N (they bypass
    ``min_confidence`` but still honour TTL and ``task_type``). Pinned entries
    are emitted first, preserving their relative ordering by confidence.

    See ADR-005 §2.3 for the filter contract.

    v8.2.8 (additive — R5 backward-compat): when ``change_id`` is provided,
    ALSO load per-change learnings from
    ``.local/.agent/active/<change_id>/learnings.jsonl`` and merge them
    with the global ``jsonl_path`` entries. In-change entries surface
    first (highest priority — they are the most recent / scoped context),
    then global entries fill the remainder, deduplicated by
    ``(stage, task_type, key)``, capped at ``max_entries``. Within each
    scope the same pinned-first / confidence-sort ordering applies.

    When ``change_id`` is ``None`` the behaviour is byte-identical to
    v8.1.0 — the original code path runs unchanged.
    """
    if change_id is not None:
        return _load_relevant_learnings_change_aware(
            task_type=task_type,
            jsonl_path=jsonl_path,
            min_confidence=min_confidence,
            max_entries=max_entries,
            session_id=session_id,
            change_id=change_id,
        )

    entries = _read_lines(jsonl_path)
    now = datetime.now(UTC)
    pinned: list[Learning] = []
    unpinned: list[Learning] = []

    for entry in entries:
        if entry.get("task_type") != task_type:
            continue
        if not _entry_ttl_valid(entry, now):
            continue
        learning = _entry_to_learning(entry)
        if learning is None:
            continue
        if _is_pinned_for_session(learning, session_id):
            pinned.append(learning)
        elif learning.confidence >= min_confidence:
            unpinned.append(learning)

    return _merge_ranked_learnings(pinned, unpinned, max_entries)


def _filter_learnings_for_task(
    jsonl_path: Path,
    task_type: str,
    min_confidence: float,
    max_entries: int,
    session_id: str | None,
) -> list[Learning]:
    """Run the v8.1.0 filter pipeline on ``jsonl_path`` for ``task_type``.

    Internal helper extracted in v8.2.8 so the change-aware merge code can
    apply the same TTL / confidence / pinned-first ordering on each scope
    independently before merging. The original public
    :func:`load_relevant_learnings` path does NOT call this helper — its
    body is preserved byte-identical to honour invariant I-PV08-A.
    """
    entries = _read_lines(jsonl_path)
    now = datetime.now(UTC)
    pinned: list[Learning] = []
    unpinned: list[Learning] = []

    for entry in entries:
        if entry.get("task_type") != task_type:
            continue
        if not _entry_ttl_valid(entry, now):
            continue
        learning = _entry_to_learning(entry)
        if learning is None:
            continue
        if _is_pinned_for_session(learning, session_id):
            pinned.append(learning)
        elif learning.confidence >= min_confidence:
            unpinned.append(learning)

    return _merge_ranked_learnings(pinned, unpinned, max_entries)


def _per_change_learnings_path(change_id: str) -> Path:
    """Return the canonical per-change JSONL path under ``.local/.agent/active/``.

    Repo-relative per Rule S-2; resolved against ``Path.cwd()`` at call
    time so callers can override via ``os.chdir`` in tests / sandboxes
    (the ``.local/.agent/active/<id>/`` layout is the v8.2.6 contract).
    """
    return Path(".local") / ".agent" / "active" / change_id / "learnings.jsonl"


def _load_relevant_learnings_change_aware(
    *,
    task_type: str,
    jsonl_path: Path,
    min_confidence: float,
    max_entries: int,
    session_id: str | None,
    change_id: str,
) -> list[Learning]:
    """Merge per-change + global learnings; in-change entries surface first.

    Both scopes are filtered through the v8.1.0 pipeline, then concatenated
    in the order ``in_change → global`` and deduplicated by
    ``(stage, task_type, key)`` so the highest-priority (in-change) entry
    survives any cross-scope collision. The merged list is capped at
    ``max_entries``.

    Helper for :func:`load_relevant_learnings` (v8.2.8 — closes H-006).
    """
    per_change_path = _per_change_learnings_path(change_id)
    in_change = _filter_learnings_for_task(
        jsonl_path=per_change_path,
        task_type=task_type,
        min_confidence=min_confidence,
        max_entries=max_entries,
        session_id=session_id,
    )
    global_entries = _filter_learnings_for_task(
        jsonl_path=jsonl_path,
        task_type=task_type,
        min_confidence=min_confidence,
        max_entries=max_entries,
        session_id=session_id,
    )

    seen: set[tuple[str, str, str]] = set()
    merged: list[Learning] = []
    for learning in in_change:
        triple = (learning.stage, learning.task_type, learning.key)
        if triple in seen:
            continue
        merged.append(learning)
        seen.add(triple)
        if len(merged) >= max_entries:
            return merged
    for learning in global_entries:
        triple = (learning.stage, learning.task_type, learning.key)
        if triple in seen:
            continue
        merged.append(learning)
        seen.add(triple)
        if len(merged) >= max_entries:
            return merged
    return merged


def dedup_learnings(entries: list[Learning]) -> list[Learning]:
    """Return latest-timestamp entry per ``(task_type, key)`` pair.

    Mirrors the gstack ``/learn`` JSONL ``{type, key}`` last-write-wins
    contract (see C-007 description and ``.local/research/v7.2.0_refs/``
    delta-T02 §D2.1 for verbatim source). When two entries share the same
    ``(task_type, key)``, the one with the lexicographically-greater
    ``timestamp`` wins (ISO 8601 sorts correctly under string comparison).

    Empty timestamps lose to populated timestamps. Insertion order is
    preserved across distinct ``(task_type, key)`` tuples — the returned
    list contains entries in the order their key was first encountered.

    Pure / no I/O. Intended consumers: pre-write dedup at session-end
    (C-009 reflective reflex) and post-read dedup at filter time.
    """
    seen: dict[tuple[str, str], Learning] = {}
    for entry in entries:
        key = (entry.task_type, entry.key)
        prev = seen.get(key)
        if prev is None:
            seen[key] = entry
            continue
        if entry.timestamp > prev.timestamp:
            seen[key] = entry
    return list(seen.values())


def capture_session_reflection(
    session_id: str,
    task_type: str,
    files: list[str],
    insight: str,
    source: str,
    jsonl_path: Path | None = None,
    key: str | None = None,
    change_id: str | None = None,
) -> Learning:
    """Capture an L3-session reflective reflex into ``jsonl_path``.

    Activates the dormant ``operational.jsonl`` substrate that v7.2.0 PR-C
    shipped (C-007 schema additions to :class:`Learning`: ``files``,
    ``source``, plus :func:`dedup_learnings`). Called at L3 task completion
    to persist a "pre-completion reflection" Learning entry that the next
    session can load via :func:`load_relevant_learnings`.

    Auto-derives ``key`` as ``f"{task_type}:{files[0] if files else 'session'}"``
    when not provided. The new entry is constructed with ``stage='reflection'``,
    ``confidence=0.7``, ``source_task_id=session_id``, and ``timestamp`` set
    to :func:`_now_iso` so it always wins against any prior entry sharing the
    same ``(task_type, key)`` pair.

    Loads existing entries from ``jsonl_path`` and runs :func:`dedup_learnings`
    against ``existing + [new]`` to enforce the C-007 last-write-wins contract.
    Rewrites the JSONL with the surviving non-new entries (dropping any
    ``(task_type, key)`` collision), then persists the new entry via
    :func:`capture_learning` so the existing skip-dup guard on
    ``(key, stage, task_type)`` still applies to other reflective writers.

    Returns the newly constructed :class:`Learning` object.

    v8.2.8 (additive — R5 backward-compat): when ``change_id`` is provided,
    the per-change JSONL at ``.local/.agent/active/<change_id>/learnings.jsonl``
    becomes the destination — UNLESS ``jsonl_path`` is also explicitly
    provided, in which case ``jsonl_path`` wins (back-compat for callers
    that pre-date v8.2.8). Routing precedence:

    1. ``change_id`` set, ``jsonl_path`` is ``None`` → write to per-change path.
    2. ``change_id`` set, ``jsonl_path`` is explicit → use ``jsonl_path``
       (back-compat — caller's explicit choice wins).
    3. ``change_id`` is ``None``, ``jsonl_path`` set → original v7.2.3 path.
    4. Both ``None`` → ``ValueError`` (no destination — S-5 loud).

    Source: v7.3.0 plan §P-03 — ``.local/research/v7.3.0_patch_plan.md``;
    v8.3.0 design §4.1 — ``.local/research/v8.3.0_design.md``.
    """
    target_path: Path
    if jsonl_path is not None:
        target_path = jsonl_path
    elif change_id is not None:
        target_path = _per_change_learnings_path(change_id)
    else:
        raise ValueError(
            "capture_session_reflection: at least one of jsonl_path or "
            "change_id must be provided (no destination otherwise)"
        )

    if key is None:
        key = f"{task_type}:{files[0] if files else 'session'}"

    new_learning = Learning(
        stage="reflection",
        task_type=task_type,
        key=key,
        insight=insight,
        confidence=0.7,
        timestamp=_now_iso(),
        source_task_id=session_id,
        files=list(files),
        source=source,
    )

    existing_entries = _read_lines(target_path)
    existing_learnings: list[Learning] = []
    for entry in existing_entries:
        fields = {k: entry[k] for k in Learning.__dataclass_fields__ if k in entry}
        try:
            existing_learnings.append(Learning(**fields))
        except (TypeError, KeyError):
            logger.warning("Skipping malformed entry at session-reflection dedup time")
            continue

    combined = existing_learnings + [new_learning]
    deduped = dedup_learnings(combined)

    surviving_others = [item for item in deduped if item is not new_learning]
    _write_entries(target_path, [asdict(item) for item in surviving_others])

    capture_learning(new_learning, target_path)

    logger.info(
        "Captured session reflection: session=%s task_type=%s key=%s",
        session_id,
        task_type,
        key,
    )
    return new_learning


def prune_learnings(jsonl_path: Path) -> int:
    """Remove expired entries from the JSONL file. Returns count removed."""
    if not jsonl_path.exists():
        logger.warning("Learnings file not found: %s", jsonl_path)
        return 0

    entries = _read_lines(jsonl_path)
    if not entries:
        return 0

    now = datetime.now(UTC)
    kept: list[dict] = []
    removed = 0

    for entry in entries:
        ts_str = entry.get("timestamp", "")
        ttl = int(entry.get("ttl_days", 90))
        expired = False
        if ts_str:
            try:
                ts = _parse_timestamp(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts + timedelta(days=ttl) <= now:
                    expired = True
            except (ValueError, TypeError):
                pass
        if expired:
            removed += 1
        else:
            kept.append(entry)

    jsonl_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in kept))
    return removed


def promote_learning(learning: Learning, jsonl_path: Path) -> None:
    """Increase the confidence of an existing learning that matches by key+stage+task_type.

    If a matching entry exists, its confidence is bumped by 0.1 (clamped to 1.0)
    and its timestamp is refreshed. If no match is found, the learning is
    appended as-is.
    """
    entries = _read_lines(jsonl_path)
    matched = False

    for entry in entries:
        if (
            entry.get("key") == learning.key
            and entry.get("stage") == learning.stage
            and entry.get("task_type") == learning.task_type
        ):
            entry["confidence"] = round(min(1.0, float(entry.get("confidence", 0)) + 0.1), 4)
            entry["timestamp"] = _now_iso()
            matched = True
            break

    if matched:
        jsonl_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    else:
        capture_learning(learning, jsonl_path)


def _write_entries(jsonl_path: Path, entries: list[dict]) -> None:
    """Rewrite a JSONL file in place from a list of dict entries."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))


def consolidate_session(
    session_id: str,
    session_learnings: list[Learning],
    jsonl_path: Path,
) -> dict:
    """At session end, promote learnings that were USED during the session.

    For every entry in ``session_learnings``:

    * If a persisted entry with the same ``(key, stage, task_type)`` triple
      exists, bump its ``confidence`` by ``0.05`` (clamped to ``1.0``),
      increment ``promotion_count`` by one, and refresh ``last_accessed`` to
      now. Counts as *promoted*.
    * Otherwise, append the session learning as a new JSONL record with
      ``promotion_count=1`` and ``last_accessed=now``. Counts as *captured*.
    * Items whose session payload is malformed (duplicated within the same
      call) are skipped — each ``(key, stage, task_type)`` triple may be
      promoted at most **once** per invocation (the idempotency contract of
      ADR-005 §6 test #8).

    Returns ``{promoted, captured, skipped}`` with integer counts.
    """
    if not session_learnings:
        return {"promoted": 0, "captured": 0, "skipped": 0}

    entries = _read_lines(jsonl_path)
    now_iso = _now_iso()
    promoted = 0
    captured = 0
    skipped = 0
    seen_triples: set[tuple[str, str, str]] = set()

    for learning in session_learnings:
        triple = (learning.key, learning.stage, learning.task_type)
        if triple in seen_triples:
            skipped += 1
            continue
        seen_triples.add(triple)

        matched_index = -1
        for idx, entry in enumerate(entries):
            if (
                entry.get("key") == learning.key
                and entry.get("stage") == learning.stage
                and entry.get("task_type") == learning.task_type
            ):
                matched_index = idx
                break

        if matched_index >= 0:
            entry = entries[matched_index]
            new_conf = round(min(1.0, float(entry.get("confidence", 0.0)) + 0.05), 4)
            entry["confidence"] = new_conf
            entry["promotion_count"] = int(entry.get("promotion_count", 0)) + 1
            entry["last_accessed"] = now_iso
            entry["pinned_for_session"] = entry.get("pinned_for_session", "")
            entries[matched_index] = entry
            promoted += 1
        else:
            new_entry = asdict(learning)
            new_entry["promotion_count"] = 1
            new_entry["last_accessed"] = now_iso
            if not new_entry.get("timestamp"):
                new_entry["timestamp"] = now_iso
            entries.append(new_entry)
            captured += 1

    _write_entries(jsonl_path, entries)
    logger.info(
        "Consolidated session %s: promoted=%d captured=%d skipped=%d",
        session_id,
        promoted,
        captured,
        skipped,
    )
    return {"promoted": promoted, "captured": captured, "skipped": skipped}


def _resolve_last_accessed(entry: dict) -> datetime | None:
    """Return the parsed ``last_accessed`` timestamp, migrating if needed.

    Migration shim (ADR-005 §2.4): legacy v1 entries without ``last_accessed``
    inherit their ``timestamp`` value on first touch so subsequent decay
    calls measure from a stable anchor. Malformed timestamps and entries
    with neither field return ``None`` so the caller can skip decay for
    that record.
    """
    last_accessed_str = entry.get("last_accessed") or ""
    if not last_accessed_str and entry.get("timestamp"):
        last_accessed_str = entry["timestamp"]
        entry["last_accessed"] = last_accessed_str
    if not last_accessed_str:
        return None
    try:
        dt = _parse_timestamp(last_accessed_str)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _effective_half_life(entry: dict, override: int | None) -> int:
    """Return the half-life to apply for ``entry`` (override > per-entry)."""
    per_entry = int(entry.get("confidence_half_life_days", DEFAULT_DECAY_HALF_LIFE_DAYS))
    return int(override) if override is not None else per_entry


def _decay_formula(
    prior_confidence: float,
    delta_days: float,
    half_life_days: int,
) -> float:
    """Return the post-decay confidence, clamped to ``[0.0, 1.0]``."""
    decay_factor = min(1.0, delta_days / half_life_days)
    new_confidence = max(0.0, min(1.0, prior_confidence - 0.5 * decay_factor))
    return round(new_confidence, 4)


def decay_confidence(
    jsonl_path: Path,
    half_life_days: int | None = None,
) -> dict:
    """Apply linear confidence decay to every persisted entry.

    For each entry, compute ``delta_days = (now - last_accessed)`` and
    ``decay_factor = min(1.0, delta_days / half_life)`` where ``half_life``
    is the per-entry ``confidence_half_life_days`` (falling back to the
    module-level :data:`DEFAULT_DECAY_HALF_LIFE_DAYS` when the override
    argument is ``None``). The new confidence is
    ``confidence - 0.5 * decay_factor`` clamped to ``[0.0, 1.0]``; entries
    whose new confidence falls strictly below :data:`DECAY_FLOOR` are pruned.

    Migration shim (ADR-005 §2.4): legacy entries without ``last_accessed``
    have that field set to ``timestamp`` on first touch so subsequent calls
    decay from a stable anchor. ``last_accessed`` is not refreshed during
    decay itself — decay measures distance since last access, not distance
    since last decay.

    Returns ``{decayed_count, dropped_below_floor_count}``.
    """
    if not jsonl_path.exists():
        return {"decayed_count": 0, "dropped_below_floor_count": 0}

    entries = _read_lines(jsonl_path)
    if not entries:
        return {"decayed_count": 0, "dropped_below_floor_count": 0}

    now = datetime.now(UTC)
    kept: list[dict] = []
    decayed_count = 0
    dropped_below_floor_count = 0

    for entry in entries:
        last_accessed_dt = _resolve_last_accessed(entry)
        if last_accessed_dt is None:
            kept.append(entry)
            continue

        effective_half_life = _effective_half_life(entry, half_life_days)
        if effective_half_life <= 0:
            kept.append(entry)
            continue

        delta_seconds = (now - last_accessed_dt).total_seconds()
        delta_days = max(0.0, delta_seconds / 86400.0)

        new_confidence = _decay_formula(
            prior_confidence=float(entry.get("confidence", 0.0)),
            delta_days=delta_days,
            half_life_days=effective_half_life,
        )
        entry["confidence"] = new_confidence
        decayed_count += 1

        if new_confidence < DECAY_FLOOR:
            dropped_below_floor_count += 1
            continue
        kept.append(entry)

    _write_entries(jsonl_path, kept)
    logger.info(
        "Decayed %d entries; dropped %d below floor %.2f",
        decayed_count,
        dropped_below_floor_count,
        DECAY_FLOOR,
    )
    return {
        "decayed_count": decayed_count,
        "dropped_below_floor_count": dropped_below_floor_count,
    }


def pin_learning_for_session(
    key: str,
    stage: str,
    task_type: str,
    session_id: str,
    jsonl_path: Path,
) -> bool:
    """Mark a specific learning as pinned for ``session_id``.

    Pinned entries are surfaced by :func:`load_relevant_learnings` regardless
    of ``min_confidence`` whenever the filter's ``session_id`` matches. An
    empty ``session_id`` clears any existing pin on the matched entry.

    Returns ``True`` if a matching entry was found and the pin was written,
    ``False`` otherwise.
    """
    entries = _read_lines(jsonl_path)
    matched = False

    for entry in entries:
        if (
            entry.get("key") == key
            and entry.get("stage") == stage
            and entry.get("task_type") == task_type
        ):
            entry["pinned_for_session"] = session_id
            matched = True
            break

    if matched:
        _write_entries(jsonl_path, entries)
    return matched


def get_learnings_stats(jsonl_path: Path) -> dict:
    """Return summary statistics for all learnings in *jsonl_path*.

    Returns dict with keys: total, by_task_type, avg_confidence, expired_count.
    """
    entries = _read_lines(jsonl_path)
    if not entries:
        return {
            "total": 0,
            "by_task_type": {},
            "avg_confidence": 0.0,
            "expired_count": 0,
        }

    now = datetime.now(UTC)
    by_task_type: dict[str, int] = {}
    confidences: list[float] = []
    expired_count = 0

    for entry in entries:
        tt = entry.get("task_type", "unknown")
        by_task_type[tt] = by_task_type.get(tt, 0) + 1
        confidences.append(float(entry.get("confidence", 0)))

        ts_str = entry.get("timestamp", "")
        ttl = int(entry.get("ttl_days", 90))
        if ts_str:
            try:
                ts = _parse_timestamp(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts + timedelta(days=ttl) <= now:
                    expired_count += 1
            except (ValueError, TypeError):
                pass

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "total": len(entries),
        "by_task_type": by_task_type,
        "avg_confidence": round(avg_confidence, 3),
        "expired_count": expired_count,
    }


@dataclass
class ExternalSourceReview:
    """A review record for an external tracked source."""

    source_id: str
    review_date: str
    findings_summary: str
    relevance_delta: float
    timestamp: str = ""

    def __post_init__(self) -> None:
        self.relevance_delta = max(-5.0, min(5.0, float(self.relevance_delta)))


def log_external_source_review(
    source_id: str,
    review_date: str,
    findings_summary: str,
    relevance_delta: float,
    jsonl_path: Path | None = None,
) -> bool:
    """Append an external source review record to a JSONL file.

    Writes to *jsonl_path* (defaults to
    ``workflow-system/agent/knowledge/learnings/external-sources.jsonl``
    under the current working directory).

    Returns *True* if the record was written.
    """
    if jsonl_path is None:
        jsonl_path = Path("workflow-system/agent/knowledge/learnings/external-sources.jsonl")

    review = ExternalSourceReview(
        source_id=source_id,
        review_date=review_date,
        findings_summary=findings_summary,
        relevance_delta=relevance_delta,
        timestamp=_now_iso(),
    )

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(asdict(review), ensure_ascii=False) + "\n")
    logger.info("Logged external source review: %s", source_id)
    return True


def format_learnings_section(
    learnings: list[Learning],
    max_tokens: int = 500,
) -> str:
    """Format learnings as a markdown section for context injection.

    Estimates ~4 tokens per word. Truncates if over budget.
    """
    if not learnings:
        return ""

    header = "## Operational Learnings\n\n"
    header_tokens = len(header.split()) * 4

    lines: list[str] = [header]
    used_tokens = header_tokens

    for learning in learnings:
        entry = (
            f"- **[{learning.stage}]** {learning.insight} _(confidence: {learning.confidence:.1f}"
        )
        if learning.rule_id:
            entry += f", rule: {learning.rule_id}"
        entry += ")_\n"

        entry_tokens = len(entry.split()) * 4
        if used_tokens + entry_tokens > max_tokens:
            break
        lines.append(entry)
        used_tokens += entry_tokens

    return "".join(lines)


def build_session_state_for(
    session_id: str,
    task_type: str,
    *,
    jsonl_path: Path | None = None,
    min_confidence: float = 0.5,
    max_entries: int = 10,
):
    """Lazily build a populated :class:`devolaflow.session.SessionState`.

    Bridges the v8.2.0 PV-03 unified session model with this module's
    JSONL substrate without forcing an eager import (which would create a
    circular dependency between :mod:`devolaflow.learnings` and
    :mod:`devolaflow.session.state` at module-import time). Callers that
    are still on the legacy direct-call path (``load_relevant_learnings``,
    ``consolidate_session``) keep working unchanged — ``build_session_state_for``
    is purely additive and does not alter the JSONL substrate.

    Returns a :class:`SessionState` whose :pyattr:`SessionState.learnings`
    block is hydrated via :func:`load_relevant_learnings` for the supplied
    ``task_type`` (the same query the legacy callers use). The state is
    in-memory only — call :class:`devolaflow.session.SessionStore.save`
    to persist the JSON snapshot to disk.

    Parameters
    ----------
    session_id:
        Session identifier (typically a task UUID). Becomes
        :pyattr:`SessionState.session_id`; also forwarded to
        :func:`load_relevant_learnings` so pinned-for-session entries
        surface in the hydrated learnings list.
    task_type:
        Task type filter for :func:`load_relevant_learnings`.
    jsonl_path:
        Optional override path to the JSONL substrate. Defaults to
        :func:`resolve_learnings_path`.
    min_confidence:
        Forwarded to :func:`load_relevant_learnings`.
    max_entries:
        Forwarded to :func:`load_relevant_learnings`.

    Notes
    -----
    The lazy import below is intentional — see module docstring for the
    PV-03 design rationale.
    """
    from devolaflow.session import SessionState  # noqa: PLC0415  (lazy: avoid cycle)

    state = SessionState.empty(session_id=session_id)
    state.hydrate_learnings(
        task_type=task_type,
        jsonl_path=jsonl_path,
        min_confidence=min_confidence,
        max_entries=max_entries,
    )
    return state
