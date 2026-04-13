"""Operational Learnings Module for DevolaFlow.

Captures, persists, and retrieves operational learnings across workflow
executions. Learnings are stored as JSONL (one JSON object per line) and
filtered by task type, confidence, and TTL before injection into agent context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Learning:
    """A single operational learning captured from a workflow execution."""

    stage: str
    task_type: str
    key: str
    insight: str
    confidence: float
    rule_id: str = ""
    timestamp: str = ""
    ttl_days: int = 90
    source_task_id: str = ""

    def __post_init__(self) -> None:
        """Clamp confidence to the [0.0, 1.0] range."""
        self.confidence = max(0.0, min(1.0, float(self.confidence)))


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
) -> list[Learning]:
    """Load learnings filtered by task_type, confidence, and TTL expiry.

    Returns up to max_entries sorted by confidence descending.
    """
    entries = _read_lines(jsonl_path)
    now = datetime.now(UTC)
    results: list[Learning] = []

    for entry in entries:
        if entry.get("task_type") != task_type:
            continue
        confidence = float(entry.get("confidence", 0))
        if confidence < min_confidence:
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
            results.append(Learning(**fields))
        except (TypeError, KeyError):
            logger.warning("Skipping learning with missing required fields")
            continue

    results.sort(key=lambda item: item.confidence, reverse=True)
    return results[:max_entries]


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
