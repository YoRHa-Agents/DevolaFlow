"""Host-bridge audit ledger — append-only JSONL under ``.local/telemetry/``.

v17.0.0 R2 (design §D-R2-1 step 4): every enforced bridge decision
(``DEVOLAFLOW_HOST_ENFORCE=1``) appends one JSON line to
``.local/telemetry/hostbridge.jsonl`` so the R7 evidence round has a
real per-event ledger. The ledger is best-effort by contract: an audit
write failure is logged at WARNING level (S-5 — never silent) and MUST
NOT break the bridge verdict (the bridge stays fail-open).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AUDIT_LEDGER_RELPATH = Path(".local") / "telemetry" / "hostbridge.jsonl"

# Shell commands are summarised, never stored verbatim (ledger hygiene).
CMD_SUMMARY_MAX_CHARS = 120


def build_audit_record(
    *,
    host: str,
    kind: str,
    path: str | None,
    command: str | None,
    verdict: str,
    reason: str,
    elapsed_ms: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose one ledger record (schema documented in host-bridges.md §6)."""
    record: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "host": host,
        "kind": kind,
    }
    if path is not None:
        record["path"] = path
    if command is not None:
        record["cmd"] = command[:CMD_SUMMARY_MAX_CHARS]
    record["verdict"] = verdict
    record["reason"] = reason
    record["elapsed_ms"] = round(elapsed_ms, 3)
    if extra:
        record.update(extra)
    return record


def append_audit(repo_root: Path, record: dict[str, Any]) -> bool:
    """Append *record* as one JSONL line; create parent dirs as needed.

    Returns ``True`` on success. On ANY failure the error is logged at
    WARNING level (S-5) and ``False`` is returned — the caller's
    verdict is never affected by ledger availability.
    """
    try:
        ledger = repo_root / AUDIT_LEDGER_RELPATH
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return True
    except Exception:
        logger.warning(
            "hostbridge audit append failed for %s (verdict preserved)",
            repo_root / AUDIT_LEDGER_RELPATH,
            exc_info=True,
        )
        return False


__all__ = [
    "AUDIT_LEDGER_RELPATH",
    "CMD_SUMMARY_MAX_CHARS",
    "append_audit",
    "build_audit_record",
]
