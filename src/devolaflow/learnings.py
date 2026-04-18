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
    "capture_learning",
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
]


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


def load_relevant_learnings(
    task_type: str,
    jsonl_path: Path,
    min_confidence: float = 0.5,
    max_entries: int = 10,
    session_id: str | None = None,
) -> list[Learning]:
    """Load learnings filtered by task_type, confidence, and TTL expiry.

    Returns up to ``max_entries`` sorted by confidence descending. When
    ``session_id`` is provided, entries whose ``pinned_for_session`` matches
    are surfaced *in addition* to the confidence-sorted top-N (they bypass
    ``min_confidence`` but still honour TTL and ``task_type``). Pinned entries
    are emitted first, preserving their relative ordering by confidence.

    See ADR-005 §2.3 for the filter contract.
    """
    entries = _read_lines(jsonl_path)
    now = datetime.now(UTC)
    pinned: list[Learning] = []
    unpinned: list[Learning] = []

    for entry in entries:
        if entry.get("task_type") != task_type:
            continue

        ts_str = entry.get("timestamp", "")
        ttl = int(entry.get("ttl_days", 90))
        if ts_str:
            try:
                ts = _parse_timestamp(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts + timedelta(days=ttl) <= now:
                    continue
            except (ValueError, TypeError):
                logger.warning("Invalid timestamp in learning: %s", ts_str)
                continue

        fields = {k: entry[k] for k in Learning.__dataclass_fields__ if k in entry}
        try:
            learning = Learning(**fields)
        except (TypeError, KeyError):
            logger.warning("Skipping learning with missing required fields")
            continue

        is_pinned = bool(
            session_id is not None
            and learning.pinned_for_session
            and learning.pinned_for_session == session_id
        )
        if is_pinned:
            pinned.append(learning)
        elif learning.confidence >= min_confidence:
            unpinned.append(learning)

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
        # Migration shim: legacy v1 entries lack ``last_accessed``.
        last_accessed_str = entry.get("last_accessed") or ""
        if not last_accessed_str and entry.get("timestamp"):
            last_accessed_str = entry["timestamp"]
            entry["last_accessed"] = last_accessed_str

        try:
            last_accessed_dt = _parse_timestamp(last_accessed_str) if last_accessed_str else None
        except (ValueError, TypeError):
            last_accessed_dt = None

        if last_accessed_dt is None:
            kept.append(entry)
            continue

        if last_accessed_dt.tzinfo is None:
            last_accessed_dt = last_accessed_dt.replace(tzinfo=UTC)
        delta_seconds = (now - last_accessed_dt).total_seconds()
        delta_days = max(0.0, delta_seconds / 86400.0)

        per_entry_half_life = int(
            entry.get("confidence_half_life_days", DEFAULT_DECAY_HALF_LIFE_DAYS)
        )
        effective_half_life = (
            int(half_life_days) if half_life_days is not None else per_entry_half_life
        )
        if effective_half_life <= 0:
            kept.append(entry)
            continue

        decay_factor = min(1.0, delta_days / effective_half_life)
        prior_confidence = float(entry.get("confidence", 0.0))
        new_confidence = max(0.0, min(1.0, prior_confidence - 0.5 * decay_factor))
        # Round to 4 decimals to match promote_learning's precision contract.
        new_confidence = round(new_confidence, 4)
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
