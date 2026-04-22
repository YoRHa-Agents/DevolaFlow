"""Unified session state model (v8.2.0 PV-03).

PV-03 closes the v8.0.0 patch_plan §1 row 8 deferral of "session schema +
migration path" / Karpathy 4.8 "Unified session state model". Until this
patch, three independent state holders coexisted:

* :mod:`devolaflow.learnings` — JSONL persistence for session-derived
  learning entries (capture / consolidate / decay / pin).
* :mod:`devolaflow.lifecycle` — task_stop hook that opportunistically
  invokes :func:`devolaflow.learnings.consolidate_session` from a flat
  payload dict.
* :mod:`devolaflow.legibility` — per-file legibility reports (PV-02)
  which previously had no per-session aggregation surface.

PV-03 introduces the :class:`SessionState` dataclass as the canonical
in-memory aggregate plus :class:`SessionStore` for JSON round-trip
persistence at ``.local/memory/session_state.json``. Both are
**additive** — every existing public API in ``learnings`` and
``lifecycle`` keeps its byte-stable behaviour. Adoption is opt-in: a
caller migrates by reading/writing through :class:`SessionState`
instead of the lower-level helpers, while legacy callers still see
the same JSONL substrate.

Design notes
------------

* **R5 backward compatibility**: ``learnings.py`` and ``lifecycle/``
  are unchanged behaviourally. SessionState reads from / writes to
  the same JSONL substrate via the existing learning helpers, so
  legacy callers and SessionState-aware callers can coexist on one
  store. Nothing in this module raises on legacy data shapes.
* **3-domain unification**: SessionState aggregates learnings,
  lifecycle hook history, and a :class:`LegibilitySnapshot` (PV-02
  hook) so any future session-aware feature has a single canonical
  read/write surface.
* **Deterministic JSON**: :meth:`SessionStore.save` writes with
  ``sort_keys=True`` + ``indent=2`` so the artifact is diffable and
  hash-comparable across runs (important for the SI-10 6/6 stability
  invariant and for cycle telemetry).
* **No silent failures (S-5)**: load / save raise on filesystem errors
  beyond ``FileNotFoundError`` (which returns an empty state). Schema
  version mismatches log a WARNING and accept the payload via the
  forward-compatible loader; truly malformed payloads raise
  :class:`SessionStateError` so callers can decide retry / abort.
* **No P6 schema bumps**: SessionState is an in-memory aggregation +
  JSON file; ``schemas/lean-dispatch.yaml`` is untouched, so the
  canonical_order length stays 15 and version stays 4 throughout
  PV-03 (per ``.local/research/v8.2.0_patch_plan.md`` §1.1
  invariant 1).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devolaflow.learnings import (
    Learning,
    capture_learning,
    consolidate_session,
    load_relevant_learnings,
    resolve_learnings_path,
)

logger = logging.getLogger(__name__)


__all__ = [
    "DEFAULT_SESSION_STATE_PATH",
    "LegibilitySnapshot",
    "LifecycleEvent",
    "SCHEMA_VERSION",
    "SessionState",
    "SessionStateError",
    "SessionStore",
    "default_session_state_path",
]


SCHEMA_VERSION: int = 1
"""Internal schema version of the JSON payload written by
:meth:`SessionStore.save`. Forward-compatible: future versions add new
fields with safe defaults so older :meth:`SessionStore.load` calls keep
working. A version bump must update this constant *and* the loader's
upgrade matrix below."""


DEFAULT_SESSION_STATE_PATH: str = ".local/memory/session_state.json"
"""Repo-relative default JSON file under the gitignored ``.local`` tree."""


class SessionStateError(RuntimeError):
    """Raised when SessionState load/save encounters an unrecoverable error.

    Distinct from :class:`FileNotFoundError` (which is treated as "fresh
    state") and from :class:`PermissionError` / :class:`OSError` (which
    are re-raised verbatim so callers can distinguish IO failures from
    payload corruption per S-5 No Silent Failures).
    """


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string (with ``+00:00`` suffix)."""
    return datetime.now(UTC).isoformat()


def default_session_state_path(cwd: str | Path | None = None) -> Path:
    """Resolve the canonical session-state JSON path.

    Mirrors :func:`devolaflow.learnings.resolve_learnings_path` style:
    project-relative ``.local/memory/session_state.json`` under the
    supplied ``cwd`` (defaults to :func:`Path.cwd`). The parent directory
    is *not* created here — :meth:`SessionStore.save` creates it lazily
    so read-only callers never accidentally materialise the directory.
    """
    base = Path(cwd) if cwd else Path.cwd()
    return base / DEFAULT_SESSION_STATE_PATH


# ── Domain-specific blocks ───────────────────────────────────────────────


@dataclass
class LegibilitySnapshot:
    """Per-session aggregation of PV-02 legibility verdicts.

    Records the most recent :class:`devolaflow.legibility.LegibilityReport`
    score per file plus a session-level mean. Designed so PV-02 callers
    can write the snapshot without instantiating a :class:`SessionState`
    directly — :meth:`SessionState.attach_legibility` does the wiring.

    Attributes
    ----------
    mean_score:
        Mean composite score (0-100) across :attr:`per_file_scores`.
        Zero when the snapshot is empty (rather than raising) so callers
        can compare snapshots without branching on emptiness.
    per_file_scores:
        ``{path: score}`` mapping for every file scored in this session.
        Latest write wins per path (the snapshot is intentionally not
        append-only — a single session repeatedly scoring the same file
        keeps only the freshest verdict).
    findings:
        Aggregated finding strings from the PV-02 reports. Truncated to
        :data:`_MAX_LEGIBILITY_FINDINGS` to bound the JSON payload size
        (a noisy session can otherwise emit thousands of lines).
    last_updated:
        ISO 8601 UTC timestamp of the last :meth:`update` call. Empty
        when no updates have occurred.
    """

    mean_score: float = 0.0
    per_file_scores: dict[str, float] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    last_updated: str = ""

    def update(
        self,
        file_path: str,
        score: float,
        findings: list[str] | None = None,
    ) -> None:
        """Record / overwrite a per-file score and refresh derived state."""
        if not file_path:
            raise ValueError("LegibilitySnapshot.update requires a non-empty file_path")
        self.per_file_scores[file_path] = float(score)
        if findings:
            for finding in findings:
                if finding not in self.findings:
                    self.findings.append(finding)
            if len(self.findings) > _MAX_LEGIBILITY_FINDINGS:
                self.findings = self.findings[-_MAX_LEGIBILITY_FINDINGS:]
        if self.per_file_scores:
            self.mean_score = round(
                sum(self.per_file_scores.values()) / len(self.per_file_scores),
                2,
            )
        else:
            self.mean_score = 0.0
        self.last_updated = _now_iso()

    def merge(self, other: LegibilitySnapshot) -> None:
        """Merge ``other`` in-place using last-write-wins per file path.

        ``last_updated`` is set to the maximum of the two snapshots'
        timestamps (empty timestamps lose to populated timestamps).
        Findings are deduplicated while preserving insertion order so
        replay yields a stable list.
        """
        for path, score in other.per_file_scores.items():
            self.per_file_scores[path] = float(score)
        for finding in other.findings:
            if finding not in self.findings:
                self.findings.append(finding)
        if len(self.findings) > _MAX_LEGIBILITY_FINDINGS:
            self.findings = self.findings[-_MAX_LEGIBILITY_FINDINGS:]
        if self.per_file_scores:
            self.mean_score = round(
                sum(self.per_file_scores.values()) / len(self.per_file_scores),
                2,
            )
        else:
            self.mean_score = 0.0
        candidate_timestamps = [self.last_updated, other.last_updated]
        populated = [t for t in candidate_timestamps if t]
        if populated:
            self.last_updated = max(populated)


_MAX_LEGIBILITY_FINDINGS: int = 256


@dataclass
class LifecycleEvent:
    """Single lifecycle-hook event recorded against a session.

    Captures the minimal envelope needed to replay or audit the
    sequence of hooks fired during a session. Hooks themselves remain
    stateless — SessionState is the optional aggregation layer.
    """

    event: str
    passed: bool
    severity: str | None = None
    violation_codes: list[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if self.violation_codes is None:
            self.violation_codes = []
        else:
            self.violation_codes = [str(code) for code in self.violation_codes]
        if not self.timestamp:
            self.timestamp = _now_iso()


# ── Session aggregate ────────────────────────────────────────────────────


@dataclass
class SessionState:
    """Unified session state aggregating learnings + lifecycle + legibility.

    Created either fresh via :meth:`SessionState.empty` or loaded via
    :meth:`SessionStore.load`. Construction never touches the filesystem
    so SessionState is cheap to instantiate per dispatch.

    Attributes
    ----------
    session_id:
        Stable identifier for the session — usually a task UUID or a
        ``YYYYMMDD-HHMMSS-<random>`` slug. Empty string is allowed and
        signals "ad-hoc / unnamed" but consumers SHOULD set a real id
        when persistence is intended.
    schema_version:
        Schema version of the in-memory representation. Defaults to
        :data:`SCHEMA_VERSION`. Loaded states preserve their original
        version so callers can branch on legacy payloads.
    started_at / updated_at:
        ISO 8601 UTC timestamps. ``started_at`` is set on construction
        when empty; ``updated_at`` refreshes on every mutation helper.
    learnings:
        Read-through cache of session-relevant :class:`Learning` entries
        as loaded by :func:`devolaflow.learnings.load_relevant_learnings`
        for the most recent ``hydrate_learnings`` call. Empty by default;
        populated lazily.
    pending_learnings:
        :class:`Learning` instances captured during the session that have
        NOT yet been persisted via :meth:`flush_learnings`. The lifecycle
        ``task_stop`` hook flushes this list when the task completes
        cleanly (R5: existing flat-payload flow keeps working too).
    lifecycle_events:
        Append-only list of :class:`LifecycleEvent` records as the hooks
        fire. Bounded by :data:`_MAX_LIFECYCLE_EVENTS` so a long-running
        session doesn't unbound the JSON payload.
    legibility:
        :class:`LegibilitySnapshot` aggregating PV-02 verdicts for the
        session. Always non-None — a fresh state has an empty snapshot.
    metadata:
        Free-form ``str -> Any`` dict for caller-specific extras.
        SessionState itself never reads this dict, it is round-tripped
        through JSON unchanged so callers can stash routing hints,
        replay markers, etc.
    """

    session_id: str = ""
    schema_version: int = SCHEMA_VERSION
    started_at: str = ""
    updated_at: str = ""
    learnings: list[Learning] = field(default_factory=list)
    pending_learnings: list[Learning] = field(default_factory=list)
    lifecycle_events: list[LifecycleEvent] = field(default_factory=list)
    legibility: LegibilitySnapshot = field(default_factory=LegibilitySnapshot)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = _now_iso()
        if not self.updated_at:
            self.updated_at = self.started_at

    # ── factory + conversion helpers ────────────────────────────────────

    @classmethod
    def empty(cls, session_id: str = "") -> SessionState:
        """Return a fresh SessionState with empty blocks."""
        return cls(session_id=session_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the state to a JSON-compatible dict.

        Uses :func:`dataclasses.asdict` so nested dataclasses
        (:class:`LegibilitySnapshot`, :class:`Learning`,
        :class:`LifecycleEvent`) are converted recursively. The result
        is sorted-key safe — :meth:`SessionStore.save` adds
        ``sort_keys=True`` for deterministic output.
        """
        return {
            "session_id": self.session_id,
            "schema_version": self.schema_version,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "learnings": [asdict(item) for item in self.learnings],
            "pending_learnings": [asdict(item) for item in self.pending_learnings],
            "lifecycle_events": [asdict(item) for item in self.lifecycle_events],
            "legibility": asdict(self.legibility),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionState:
        """Deserialise a dict produced by :meth:`to_dict`.

        Forward-compatible: missing keys fall back to dataclass defaults.
        Unknown keys are ignored (logged at DEBUG so future schema
        additions don't break older readers). Mismatched
        ``schema_version`` is accepted but logged at WARNING per S-5.
        """
        if not isinstance(payload, dict):
            raise SessionStateError(
                f"SessionState.from_dict expects a dict, got {type(payload).__name__}"
            )

        version = int(payload.get("schema_version", SCHEMA_VERSION))
        if version > SCHEMA_VERSION:
            logger.warning(
                "SessionState payload schema_version=%d > current %d (forward read)",
                version,
                SCHEMA_VERSION,
            )

        learnings_raw = payload.get("learnings") or []
        learnings = [_learning_from_payload(entry) for entry in learnings_raw]
        pending_raw = payload.get("pending_learnings") or []
        pending = [_learning_from_payload(entry) for entry in pending_raw]

        lifecycle_raw = payload.get("lifecycle_events") or []
        lifecycle: list[LifecycleEvent] = []
        for entry in lifecycle_raw:
            if not isinstance(entry, dict):
                logger.warning("Skipping non-dict lifecycle_events entry: %r", entry)
                continue
            try:
                lifecycle.append(
                    LifecycleEvent(
                        event=str(entry.get("event", "")),
                        passed=bool(entry.get("passed", True)),
                        severity=entry.get("severity"),
                        violation_codes=list(entry.get("violation_codes", []) or []),
                        timestamp=str(entry.get("timestamp", "")),
                    )
                )
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping malformed lifecycle event %r: %s", entry, exc)

        legibility_raw = payload.get("legibility") or {}
        if not isinstance(legibility_raw, dict):
            legibility_raw = {}
        legibility = LegibilitySnapshot(
            mean_score=float(legibility_raw.get("mean_score", 0.0)),
            per_file_scores={
                str(k): float(v) for k, v in (legibility_raw.get("per_file_scores") or {}).items()
            },
            findings=list(legibility_raw.get("findings", []) or []),
            last_updated=str(legibility_raw.get("last_updated", "")),
        )

        metadata_raw = payload.get("metadata") or {}
        if not isinstance(metadata_raw, dict):
            logger.warning(
                "Coercing non-dict metadata payload to empty dict (got %s)",
                type(metadata_raw).__name__,
            )
            metadata_raw = {}

        return cls(
            session_id=str(payload.get("session_id", "")),
            schema_version=version,
            started_at=str(payload.get("started_at", "")) or _now_iso(),
            updated_at=str(payload.get("updated_at", "")) or _now_iso(),
            learnings=learnings,
            pending_learnings=pending,
            lifecycle_events=lifecycle,
            legibility=legibility,
            metadata=dict(metadata_raw),
        )

    # ── learning helpers (R5 wrappers around learnings.py) ──────────────

    def hydrate_learnings(
        self,
        task_type: str,
        jsonl_path: Path | None = None,
        *,
        min_confidence: float = 0.5,
        max_entries: int = 10,
    ) -> list[Learning]:
        """Refresh :attr:`learnings` from the canonical JSONL substrate.

        Thin pass-through to :func:`devolaflow.learnings.load_relevant_learnings`
        — preserves R5 backward-compat (the substrate is unchanged) while
        giving SessionState callers a single attachment point.
        """
        path = jsonl_path or resolve_learnings_path()
        loaded = load_relevant_learnings(
            task_type=task_type,
            jsonl_path=path,
            min_confidence=min_confidence,
            max_entries=max_entries,
            session_id=self.session_id or None,
        )
        self.learnings = list(loaded)
        self._touch()
        return list(self.learnings)

    def queue_learning(self, learning: Learning) -> None:
        """Stage a new learning for flush at session-end.

        Does NOT touch the JSONL substrate. The lifecycle ``task_stop``
        hook (or an explicit :meth:`flush_learnings` call) is what
        moves the entry from in-memory to persisted state.
        """
        if not isinstance(learning, Learning):
            raise TypeError(
                f"queue_learning expects a Learning instance, got {type(learning).__name__}"
            )
        self.pending_learnings.append(learning)
        self._touch()

    def flush_learnings(self, jsonl_path: Path | None = None) -> dict[str, int]:
        """Persist :attr:`pending_learnings` via consolidate_session.

        Returns the verbatim ``{promoted, captured, skipped}`` summary
        from :func:`devolaflow.learnings.consolidate_session` so callers
        can log the same metrics they would get from the legacy flow.
        Resets :attr:`pending_learnings` to ``[]`` regardless of summary.
        """
        if not self.pending_learnings:
            return {"promoted": 0, "captured": 0, "skipped": 0}
        path = jsonl_path or resolve_learnings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        summary = consolidate_session(
            session_id=self.session_id or "session",
            session_learnings=list(self.pending_learnings),
            jsonl_path=path,
        )
        self.pending_learnings.clear()
        self._touch()
        return summary

    def capture_learning(
        self,
        learning: Learning,
        jsonl_path: Path | None = None,
    ) -> bool:
        """Persist a single learning immediately (R5 alias of capture_learning).

        Convenience wrapper for callers that have a
        :class:`Learning` ready to write without batching. Returns the
        verbatim boolean from :func:`devolaflow.learnings.capture_learning`.
        """
        path = jsonl_path or resolve_learnings_path()
        result = capture_learning(learning, path)
        if result:
            self._touch()
        return result

    # ── lifecycle helpers ───────────────────────────────────────────────

    def record_lifecycle_event(
        self,
        event: str,
        *,
        passed: bool,
        severity: str | None = None,
        violation_codes: list[str] | None = None,
    ) -> LifecycleEvent:
        """Append a :class:`LifecycleEvent` to the session log."""
        record = LifecycleEvent(
            event=event,
            passed=passed,
            severity=severity,
            violation_codes=list(violation_codes or []),
        )
        self.lifecycle_events.append(record)
        if len(self.lifecycle_events) > _MAX_LIFECYCLE_EVENTS:
            self.lifecycle_events = self.lifecycle_events[-_MAX_LIFECYCLE_EVENTS:]
        self._touch()
        return record

    # ── legibility helpers ──────────────────────────────────────────────

    def attach_legibility(
        self,
        file_path: str,
        score: float,
        findings: list[str] | None = None,
    ) -> LegibilitySnapshot:
        """Update the embedded :class:`LegibilitySnapshot` and return it."""
        self.legibility.update(file_path, score, findings)
        self._touch()
        return self.legibility

    # ── merging + housekeeping ──────────────────────────────────────────

    def merge(self, other: SessionState) -> None:
        """Merge ``other`` into ``self`` in-place.

        Designed for handoff scenarios where a wave-level orchestrator
        absorbs the trailing state of a child task. Conflict policy:

        * ``session_id`` — kept from ``self`` (the receiver wins so
          merging never silently overwrites the orchestrator's id).
        * ``schema_version`` — taken from the maximum of both.
        * Timestamps — ``started_at`` keeps the earlier of the two
          (when both are populated); ``updated_at`` keeps the later.
        * ``learnings`` and ``pending_learnings`` — concatenated with
          duplicate ``(task_type, key, stage)`` triples filtered out
          (last write wins via the deduper helper).
        * ``lifecycle_events`` — concatenated; the bound is reapplied.
        * ``legibility`` — delegated to :meth:`LegibilitySnapshot.merge`.
        * ``metadata`` — merged shallowly; ``other``'s keys override.
        """
        if not isinstance(other, SessionState):
            raise TypeError(
                f"SessionState.merge expects another SessionState, got {type(other).__name__}"
            )
        self.schema_version = max(self.schema_version, other.schema_version)

        if self.started_at and other.started_at:
            self.started_at = min(self.started_at, other.started_at)
        elif other.started_at and not self.started_at:
            self.started_at = other.started_at

        if self.updated_at and other.updated_at:
            self.updated_at = max(self.updated_at, other.updated_at)
        elif other.updated_at and not self.updated_at:
            self.updated_at = other.updated_at

        self.learnings = _dedup_learning_list(self.learnings + other.learnings)
        self.pending_learnings = _dedup_learning_list(
            self.pending_learnings + other.pending_learnings
        )
        self.lifecycle_events.extend(other.lifecycle_events)
        if len(self.lifecycle_events) > _MAX_LIFECYCLE_EVENTS:
            self.lifecycle_events = self.lifecycle_events[-_MAX_LIFECYCLE_EVENTS:]
        self.legibility.merge(other.legibility)
        for key, value in other.metadata.items():
            self.metadata[key] = value
        self._touch()

    def _touch(self) -> None:
        """Refresh :attr:`updated_at`."""
        self.updated_at = _now_iso()


_MAX_LIFECYCLE_EVENTS: int = 512


# ── Persistence layer ────────────────────────────────────────────────────


@dataclass
class SessionStore:
    """JSON-backed persistence for :class:`SessionState`.

    Wraps a single file path. ``save`` writes deterministically (sorted
    keys, two-space indent); ``load`` returns either the parsed state
    or :meth:`SessionState.empty` when the file is missing. IO errors
    other than :class:`FileNotFoundError` propagate (S-5 No Silent
    Failures).
    """

    path: Path

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_session_state_path()

    def exists(self) -> bool:
        """Return ``True`` if the backing JSON file is present."""
        return self.path.exists()

    def load(self, *, default_session_id: str = "") -> SessionState:
        """Load and return the persisted state.

        Returns :meth:`SessionState.empty` (with the supplied
        ``default_session_id``) when the file is missing. Raises
        :class:`SessionStateError` when the file is present but its
        contents cannot be parsed as JSON or do not deserialise into a
        :class:`SessionState` (per S-5: corruption is loud).
        """
        if not self.path.exists():
            return SessionState.empty(session_id=default_session_id)
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            raise
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            raise SessionStateError(
                f"SessionStore.load: invalid JSON at {self.path}: {exc.msg}"
            ) from exc
        if not isinstance(payload, dict):
            raise SessionStateError(
                f"SessionStore.load: expected dict payload at {self.path}, "
                f"got {type(payload).__name__}"
            )
        return SessionState.from_dict(payload)

    def save(self, state: SessionState) -> Path:
        """Persist *state* to :attr:`path` and return the path.

        Creates the parent directory lazily. Writes via the standard
        :func:`json.dumps` with ``sort_keys=True`` + ``indent=2`` so
        the output is reproducible byte-for-byte across runs that
        produce equivalent state. Returns the path so callers can
        chain ``log.info(... store.save(state))``.
        """
        if not isinstance(state, SessionState):
            raise TypeError(f"SessionStore.save expects a SessionState, got {type(state).__name__}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = state.to_dict()
        serialised = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
        self.path.write_text(serialised + "\n", encoding="utf-8")
        return self.path

    def delete(self) -> bool:
        """Remove the backing file. Returns True if a file was removed."""
        if self.path.exists():
            self.path.unlink()
            return True
        return False


# ── private helpers ──────────────────────────────────────────────────────


def _learning_from_payload(payload: Any) -> Learning:
    """Hydrate a Learning from a JSON dict, dropping unknown keys.

    Unknown keys are skipped (mirrors :func:`devolaflow.learnings._entry_to_learning`)
    so legacy v1/v2 payloads parse unchanged. Truly malformed payloads
    raise :class:`SessionStateError` per S-5 — silent drops would
    accumulate corruption invisibly.
    """
    if not isinstance(payload, dict):
        raise SessionStateError(
            f"SessionState learnings entry must be a dict, got {type(payload).__name__}"
        )
    fields = {k: payload[k] for k in Learning.__dataclass_fields__ if k in payload}
    try:
        return Learning(**fields)
    except (TypeError, ValueError) as exc:
        raise SessionStateError(f"SessionState could not hydrate Learning payload: {exc}") from exc


def _dedup_learning_list(items: list[Learning]) -> list[Learning]:
    """Deduplicate by ``(task_type, key, stage)`` keeping the LAST entry.

    Mirrors :func:`devolaflow.learnings.dedup_learnings` semantics but
    keys on the full triple (rather than the 2-tuple) so SessionState
    can carry multiple stages of the same key without collapsing them.
    Iteration order is preserved by the dict so the returned list is
    deterministic for a given input.
    """
    seen: dict[tuple[str, str, str], Learning] = {}
    for item in items:
        seen[(item.task_type, item.key, item.stage)] = item
    return list(seen.values())
