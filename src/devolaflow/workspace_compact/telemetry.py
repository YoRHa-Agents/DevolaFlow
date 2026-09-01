"""Compaction telemetry on a dedicated ledger (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §6.

These events live in `.local/telemetry/compact.jsonl` rather than the shared
harness ledger. That separation is a direct lesson from this cycle's F-00
finding: one row the strict reader disliked made the *entire* harness ledger
unreadable, and every downstream evaluation with it. A compaction event is
useful evidence but it is not worth coupling to that blast radius.

Three outcomes are recorded, because the interesting question is not "how much
did compaction save" but "how often did it decline to run and why":

* ``applied`` — a plan was approved and relocation completed;
* ``planned`` — a plan was produced and left waiting for consent, which is the
  expected unattended outcome, not a failure;
* ``bypassed`` — compaction was reachable but declined, with a reason.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

COMPACT_EVENT: Final[str] = "workspace_compact"
DEFAULT_LEDGER: Final[str] = ".local/telemetry/compact.jsonl"

OUTCOME_APPLIED: Final[str] = "applied"
OUTCOME_PLANNED: Final[str] = "planned"
OUTCOME_BYPASSED: Final[str] = "bypassed"

OUTCOMES: Final[frozenset[str]] = frozenset({OUTCOME_APPLIED, OUTCOME_PLANNED, OUTCOME_BYPASSED})

_SCHEMA_VERSION: Final[int] = 1

logger = logging.getLogger(__name__)


def build_event(
    folder: str,
    outcome: str,
    *,
    tokens_before: int,
    tokens_after: int,
    entries: int,
    reason: str = "",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build one compaction telemetry record."""

    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
    reduction = 0.0
    if tokens_before > 0:
        reduction = round((tokens_before - tokens_after) / tokens_before, 4)
    return {
        "schema_version": _SCHEMA_VERSION,
        "event": COMPACT_EVENT,
        "ts": timestamp or datetime.now(UTC).isoformat(),
        "folder": folder,
        "outcome": outcome,
        "tokens_before": tokens_before,
        "tokens_after": tokens_after,
        "reduction": reduction,
        "entries": entries,
        "reason": reason,
    }


def append_event(ledger: str | Path, record: Mapping[str, Any]) -> Path | None:
    """Append one record, degrading to a warning rather than aborting a move.

    Telemetry is evidence about work, not the work itself. A relocation that
    already completed and already recorded its mapping row must not be
    reported as failed because an observability write did not land (S-5: the
    failure is logged, never swallowed silently).
    """

    path = Path(ledger)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(encoded)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("compact telemetry append failed for %s: %s", path, exc)
        return None
    return path


def read_events(ledger: str | Path) -> tuple[dict[str, Any], ...]:
    """Read every well-formed compaction event, skipping unreadable rows.

    A malformed row is reported and stepped over. The reader deliberately does
    not abort: the whole point of the dedicated ledger is that damaged
    evidence degrades to less evidence, never to no evidence.
    """

    path = Path(ledger)
    if not path.exists():
        return ()
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        logger.warning("compact telemetry ledger unreadable: %s: %s", path, exc)
        return ()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("%s:%d: skipping malformed compact telemetry row: %s", path, number, exc)
            continue
        if isinstance(row, dict) and row.get("event") == COMPACT_EVENT:
            rows.append(row)
    return tuple(rows)


def summarize(ledger: str | Path) -> dict[str, Any]:
    """Summarise compaction history for a harness or retrospective reading."""

    rows = read_events(ledger)
    applied = [row for row in rows if row.get("outcome") == OUTCOME_APPLIED]
    tokens_saved = sum(
        int(row.get("tokens_before", 0)) - int(row.get("tokens_after", 0)) for row in applied
    )
    reductions = [float(row.get("reduction", 0.0)) for row in applied]
    return {
        "events": len(rows),
        "applied": len(applied),
        "planned": sum(1 for row in rows if row.get("outcome") == OUTCOME_PLANNED),
        "bypassed": sum(1 for row in rows if row.get("outcome") == OUTCOME_BYPASSED),
        "tokens_saved": tokens_saved,
        "mean_reduction": round(sum(reductions) / len(reductions), 4) if reductions else 0.0,
        "folders": sorted({str(row.get("folder", "")) for row in rows if row.get("folder")}),
    }


__all__ = [
    "COMPACT_EVENT",
    "DEFAULT_LEDGER",
    "OUTCOMES",
    "OUTCOME_APPLIED",
    "OUTCOME_BYPASSED",
    "OUTCOME_PLANNED",
    "append_event",
    "build_event",
    "read_events",
    "summarize",
]
