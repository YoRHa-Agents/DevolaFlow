"""Tri-state marker files for backgrounded ``codegraph init`` (Track C-3).

R5 F2 root cause (full_review_and_improve): repo-init forced
``codegraph init`` SYNCHRONOUSLY in all modes (the 2026-05-23 locked
operator decision) — the npm cold install and large-repo indexing block
the foreground for minutes. Decision D-11 overturns that: codegraph drops
to SUGGEST tier (probe → use when present; install only under the
existing ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` opt-in per W-20) and the
init runs as a BACKGROUND task. This module is the coordination surface
between the backgrounded init and downstream analyze consumers:

* ``.codegraph/.indexing`` — init started (payload: pid + started_at)
* ``.codegraph/.ready`` — init finished (payload: completed_at +
  duration_seconds, verbatim per C-3 rule)
* ``.codegraph/.failed`` — init failed (payload: error summary — S-5,
  never silent)

Downstream rule (``references/codegraph.md`` §4.6): ready → use the
index; indexing → bounded wait or degrade to Read/Glob/Grep; failed /
absent → degrade immediately.

The suggest-tier probe is the EXISTING
:func:`devolaflow.codegraph.is_codegraph_available` (A-5 single owner —
this module deliberately does NOT define a second ``shutil.which``
wrapper).

Stdlib-only by design (Track C-4 dependency-minimisation principle).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

MARKER_DIR = ".codegraph"
INDEXING_MARKER = ".indexing"
READY_MARKER = ".ready"
FAILED_MARKER = ".failed"

# Crash-leftover precedence: a normal transition removes its predecessor
# marker first, so coexistence only happens when a writer died mid-swap.
# ``ready`` wins (an index that finished IS usable), then ``failed``,
# then ``indexing``.
_STATE_PRECEDENCE: tuple[str, ...] = (READY_MARKER, FAILED_MARKER, INDEXING_MARKER)
_MARKER_STATES: dict[str, str] = {
    READY_MARKER: "ready",
    FAILED_MARKER: "failed",
    INDEXING_MARKER: "indexing",
}


@dataclass
class MarkerState:
    """Resolved marker state for a project root."""

    state: str  # one of: "absent" | "indexing" | "ready" | "failed"
    payload: dict = field(default_factory=dict)


def _marker_path(root: str | Path, name: str) -> Path:
    return Path(root) / MARKER_DIR / name


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _write_marker(root: str | Path, name: str, payload: dict) -> Path:
    """Write ``payload`` as JSON to the marker, clearing sibling markers first."""
    marker_dir = Path(root) / MARKER_DIR
    marker_dir.mkdir(parents=True, exist_ok=True)
    for sibling in _STATE_PRECEDENCE:
        if sibling != name:
            sibling_path = marker_dir / sibling
            try:
                sibling_path.unlink(missing_ok=True)
            except OSError as exc:
                _LOGGER.warning(
                    "codegraph markers: could not remove stale marker %s: %s",
                    sibling_path,
                    exc,
                )
    path = marker_dir / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def mark_indexing(root: str | Path, *, pid: int | None = None) -> Path:
    """Record that a backgrounded ``codegraph init`` has started."""
    return _write_marker(
        root,
        INDEXING_MARKER,
        {"pid": pid if pid is not None else os.getpid(), "started_at": _utcnow()},
    )


def mark_ready(root: str | Path, *, duration_seconds: float) -> Path:
    """Record successful init completion (duration recorded verbatim, C-3)."""
    return _write_marker(
        root,
        READY_MARKER,
        {"completed_at": _utcnow(), "duration_seconds": duration_seconds},
    )


def mark_failed(root: str | Path, *, error_summary: str) -> Path:
    """Record init failure with an explicit error summary (S-5, never silent)."""
    return _write_marker(
        root,
        FAILED_MARKER,
        {"failed_at": _utcnow(), "error_summary": error_summary},
    )


def read_marker_state(root: str | Path) -> MarkerState:
    """Resolve the current marker state for ``root``.

    Returns ``MarkerState("absent")`` when no marker exists (init never
    started — downstream consumers degrade to Read/Glob/Grep immediately).
    Unreadable / malformed marker payloads degrade to an empty payload
    with a WARNING (S-5) — the STATE is still reported so consumers can
    make the wait-vs-degrade decision.
    """
    for name in _STATE_PRECEDENCE:
        path = _marker_path(root, name)
        if not path.is_file():
            continue
        payload: dict = {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            _LOGGER.warning(
                "codegraph markers: could not parse %s: %s; state kept, payload dropped",
                path,
                exc,
            )
        return MarkerState(state=_MARKER_STATES[name], payload=payload)
    return MarkerState(state="absent")


__all__ = [
    "FAILED_MARKER",
    "INDEXING_MARKER",
    "MARKER_DIR",
    "READY_MARKER",
    "MarkerState",
    "mark_failed",
    "mark_indexing",
    "mark_ready",
    "read_marker_state",
]
