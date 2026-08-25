"""Cycle-detection middleware for convergence-loop tool-call / edit history.

v8.0.0 (P-06) — implements primitive 4.4 from
``.local/research/tweet_analysis_harness_engineering_v7.8.md`` §4.4 and
``.local/research/v8.0.0_patch_plan.md`` §3 P-06.

Three detection paths (see :class:`devolaflow.gate.models.CycleType`):

- ``exact_match``      — ≥ 2 consecutive snapshots with identical signature
                         (perfect repetition). Fires fastest because it is
                         the cheapest signal — Karpathy "fail fast on cheap
                         signals" per upstream tweet analysis ``v7.8`` §4.4.
- ``fuzzy_match``      — ≥ ``window_size`` consecutive snapshots whose
                         pairwise Jaccard similarity is ≥
                         ``similarity_threshold`` (default 0.8). Catches
                         near-duplicates the agent failed to recognise as
                         the same edit (whitespace, comment churn, etc.).
- ``edit_oscillation`` — alternating A→B→A pattern over the last 3+
                         snapshots that touch the same file set (the
                         classic agent flip-flop on a single file).

Pure semantics: :meth:`CycleDetector.detect` is a pure function of the
``round_history`` argument. The optional :meth:`record` /
:pyattr:`history` / :meth:`detect_cycle` helpers offer round-level state
tracking for callers that want it (see ``patch_plan §3 P-06`` —
``record(sig)`` + ``detect_cycle()``).

Honors S-5 (No Silent Failures): every invalid input raises
:class:`ValueError` or :class:`TypeError`; an empty / single-snapshot
history returns a ``CycleReport(detected=False, cycle_type='none')`` with
an explicit rationale rather than ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from devolaflow.gate.models import (
    CYCLE_DEFAULT_SEVERITY,
    CycleReport,
    StateSnapshot,
)

if TYPE_CHECKING:
    from devolaflow.gate.models import Severity


# Threshold constants — see ``patch_plan §3 P-06 AC #1/#2/#3``:
# - ``exact_match`` requires at least 2 consecutive identical snapshots.
# - ``fuzzy_match``  requires at least ``window_size`` consecutive snapshots
#                    with pairwise Jaccard ≥ ``similarity_threshold``.
# - ``edit_oscillation`` requires at least 3 snapshots forming an A→B→A
#                    pattern over an overlapping file set.
EXACT_MATCH_MIN_RUN: int = 2
FUZZY_MATCH_MIN_WINDOW: int = 3
EDIT_OSCILLATION_MIN_LEN: int = 3

# Default escalation: ≥ 4 consecutive identical signatures escalates the
# severity from ``major`` to ``critical`` because the agent has clearly
# exhausted its retry budget on the same exact action.
EXACT_MATCH_CRITICAL_RUN: int = 4

# Snapshot count below which detection is a no-op (per S-5: never
# silently report a verdict on insufficient evidence).
MIN_HISTORY_FOR_DETECTION: int = 2


def _no_cycle(rationale: str, window_size: int, threshold: float) -> CycleReport:
    """Build the canonical ``no-cycle`` :class:`CycleReport`.

    Used both for empty / single-snapshot histories and for the steady-state
    "we looked, nothing fired" case. The non-default ``window_size`` /
    ``threshold`` echo back the detector's configuration so callers can
    reproduce the verdict without re-reading the detector state.
    """
    return CycleReport(
        detected=False,
        cycle_type="none",
        severity=CYCLE_DEFAULT_SEVERITY["none"],
        evidence=(),
        repeated_signatures=(),
        similarity=0.0,
        rationale=rationale,
        window_size=window_size,
        threshold=threshold,
        rounds=(),
        files=(),
    )


def _jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Compute the Jaccard similarity of two token tuples.

    Treats both inputs as sets. Returns ``0.0`` for two empty tuples
    (rather than ``1.0``) so an absence of token signal never silently
    looks like a perfect match (S-5).
    """
    if not a and not b:
        return 0.0
    sa, sb = set(a), set(b)
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _detect_exact_match(
    history: list[StateSnapshot],
    window_size: int,
    threshold: float,
) -> CycleReport | None:
    """Detect ≥ ``EXACT_MATCH_MIN_RUN`` consecutive identical signatures.

    Walks the trailing window and returns the longest run found at the
    end of the history. ``None`` means no run met the minimum length;
    callers fall through to fuzzy / oscillation detection.
    """
    if len(history) < EXACT_MATCH_MIN_RUN:
        return None

    last_sig = history[-1].signature
    run = 1
    for snapshot in reversed(history[:-1]):
        if snapshot.signature == last_sig:
            run += 1
        else:
            break

    if run < EXACT_MATCH_MIN_RUN:
        return None

    severity: Severity = (
        "critical" if run >= EXACT_MATCH_CRITICAL_RUN else CYCLE_DEFAULT_SEVERITY["exact_match"]
    )
    repeated = (last_sig,)
    matched_snapshots = history[-run:]
    rounds = tuple(s.round_num for s in matched_snapshots)
    files = tuple(sorted({f for s in matched_snapshots for f in s.files}))
    evidence = tuple(f"round {s.round_num}: signature={s.signature!r}" for s in matched_snapshots)
    rationale = (
        f"Exact-match cycle detected: {run} consecutive rounds with identical signature "
        f"(rounds {list(rounds)})."
    )
    return CycleReport(
        detected=True,
        cycle_type="exact_match",
        severity=severity,
        evidence=evidence,
        repeated_signatures=repeated,
        similarity=1.0,
        rationale=rationale,
        window_size=window_size,
        threshold=threshold,
        rounds=rounds,
        files=files,
    )


def _detect_fuzzy_match(
    history: list[StateSnapshot],
    window_size: int,
    threshold: float,
) -> CycleReport | None:
    """Detect ≥ ``window_size`` consecutive near-duplicate snapshots.

    "Near-duplicate" = pairwise Jaccard similarity over the snapshots'
    ``tokens`` is ≥ ``threshold`` for every adjacent pair in the trailing
    window. Snapshots without ``tokens`` are skipped (Jaccard collapses to
    ``0.0`` and the run breaks naturally).
    """
    min_window = max(window_size, FUZZY_MATCH_MIN_WINDOW)
    if len(history) < min_window:
        return None

    window = history[-min_window:]
    pairwise: list[float] = []
    # ``window[1:]`` is intentionally one element shorter than ``window`` —
    # pairwise iteration over (previous, current) tuples — so strict=False
    # is the correct setting (ruff B905 wants the explicit declaration).
    for previous, current in zip(window, window[1:], strict=False):
        sim = _jaccard(previous.tokens, current.tokens)
        if sim < threshold:
            return None
        pairwise.append(sim)

    if not pairwise:
        return None

    avg_similarity = round(sum(pairwise) / len(pairwise), 4)
    repeated = tuple(s.signature for s in window)
    rounds = tuple(s.round_num for s in window)
    files = tuple(sorted({f for s in window for f in s.files}))
    evidence = tuple(
        f"round {s.round_num}: signature={s.signature!r} tokens={list(s.tokens)}" for s in window
    )
    rationale = (
        f"Fuzzy-match cycle detected: {len(window)} consecutive rounds with "
        f"pairwise Jaccard similarity ≥ {threshold:.2f} "
        f"(avg={avg_similarity:.2f}, rounds {list(rounds)})."
    )
    return CycleReport(
        detected=True,
        cycle_type="fuzzy_match",
        severity=CYCLE_DEFAULT_SEVERITY["fuzzy_match"],
        evidence=evidence,
        repeated_signatures=repeated,
        similarity=avg_similarity,
        rationale=rationale,
        window_size=window_size,
        threshold=threshold,
        rounds=rounds,
        files=files,
    )


def _detect_edit_oscillation(
    history: list[StateSnapshot],
    window_size: int,
    threshold: float,
) -> CycleReport | None:
    """Detect an A→B→A oscillation over the trailing 3+ snapshots.

    Requires the alternating snapshots to share at least one file path
    (the classic flip-flop pattern). Snapshots without ``files`` cannot
    fire this path — the detector falls through to ``no_cycle``.
    """
    if len(history) < EDIT_OSCILLATION_MIN_LEN:
        return None

    *_, prev2, prev1, current = history
    if prev2.signature != current.signature:
        return None
    if prev1.signature == current.signature:
        # Three identical signatures form an exact_match, handled earlier.
        return None
    overlap = set(prev2.files) & set(prev1.files) & set(current.files)
    if not overlap:
        return None

    repeated = (current.signature, prev1.signature)
    rounds = (prev2.round_num, prev1.round_num, current.round_num)
    files = tuple(sorted(overlap))
    evidence = (
        f"round {prev2.round_num}: signature={prev2.signature!r}",
        f"round {prev1.round_num}: signature={prev1.signature!r} (alternate)",
        f"round {current.round_num}: signature={current.signature!r} (returned)",
    )
    rationale = (
        f"Edit-oscillation cycle detected: A→B→A over rounds {list(rounds)} "
        f"on shared file(s) {sorted(overlap)}."
    )
    return CycleReport(
        detected=True,
        cycle_type="edit_oscillation",
        severity=CYCLE_DEFAULT_SEVERITY["edit_oscillation"],
        evidence=evidence,
        repeated_signatures=repeated,
        similarity=0.0,
        rationale=rationale,
        window_size=window_size,
        threshold=threshold,
        rounds=rounds,
        files=files,
    )


@dataclass
class CycleDetector:
    """Detect convergence-loop pathology in a sequence of round snapshots.

    Wraps three detection paths (``exact_match`` / ``fuzzy_match`` /
    ``edit_oscillation``) behind a single :meth:`detect` entry-point.
    Use :meth:`record` for stateful round-level tracking, or pass a
    pre-built ``round_history`` list directly into :meth:`detect`.

    Parameters
    ----------
    window_size:
        Number of trailing snapshots inspected for ``fuzzy_match``.
        Defaults to ``3`` (per ``patch_plan §3 P-06 AC #2``). Must be
        ≥ :data:`FUZZY_MATCH_MIN_WINDOW`.
    similarity_threshold:
        Minimum pairwise Jaccard similarity required for ``fuzzy_match``
        to fire. Defaults to ``0.8`` (per the L2 task contract). Must be
        in the inclusive range ``[0.0, 1.0]``.

    Examples
    --------
    >>> from devolaflow.gate.models import StateSnapshot
    >>> d = CycleDetector(window_size=3, similarity_threshold=0.8)
    >>> d.record(StateSnapshot(round_num=1, signature="edit:a.py:add print"))
    >>> d.record(StateSnapshot(round_num=2, signature="edit:a.py:add print"))
    >>> report = d.detect_cycle()
    >>> report.detected, report.cycle_type
    (True, 'exact_match')
    """

    window_size: int = 3
    similarity_threshold: float = 0.8
    history: list[StateSnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.window_size < FUZZY_MATCH_MIN_WINDOW:
            raise ValueError(
                f"window_size must be >= {FUZZY_MATCH_MIN_WINDOW} (got {self.window_size})"
            )
        if not (0.0 <= self.similarity_threshold <= 1.0):
            raise ValueError(
                f"similarity_threshold must be in [0.0, 1.0] (got {self.similarity_threshold})"
            )

    def record(self, snapshot: StateSnapshot) -> None:
        """Append ``snapshot`` to the rolling history (S-5 — typed input)."""
        if not isinstance(snapshot, StateSnapshot):
            raise TypeError(f"snapshot must be a StateSnapshot (got {type(snapshot).__name__})")
        self.history.append(snapshot)

    def record_tool_call(
        self,
        round_num: int,
        *,
        tool: str,
        payload: object,
        files: list[str] | tuple[str, ...] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StateSnapshot:
        """Build a :class:`StateSnapshot` and :meth:`record` it in one shot.

        Convenience wrapper around :func:`_make_snapshot` for L2 task
        agents that want a single-call API instead of constructing the
        snapshot manually. Returns the constructed snapshot so callers
        can introspect or re-use it.
        """
        snapshot = _make_snapshot(
            round_num,
            tool=tool,
            payload=payload,
            files=files,
            metadata=metadata,
        )
        self.history.append(snapshot)
        return snapshot

    def reset(self) -> None:
        """Clear the rolling history. Reuse for a new convergence cycle."""
        self.history.clear()

    def detect_cycle(self) -> CycleReport:
        """Convenience: run :meth:`detect` against the recorded history."""
        return self.detect(self.history)

    def detect(self, round_history: list[StateSnapshot] | None = None) -> CycleReport:
        """Inspect ``round_history`` (or the recorded one) for cycles.

        Detection order is fixed (per ``patch_plan §3 P-06``):

        1. ``exact_match`` — cheapest signal, fires first.
        2. ``fuzzy_match`` — Jaccard over the trailing ``window_size``.
        3. ``edit_oscillation`` — A→B→A over a shared file set.

        The first path that fires returns a :class:`CycleReport` with
        ``detected=True``; the remainder are not consulted (S-5 — single
        verdict per call). When no path fires, the report is the canonical
        ``CycleReport(detected=False, cycle_type='none')`` so callers can
        log every measurement uniformly.
        """
        history = self.history if round_history is None else list(round_history)
        if not isinstance(history, list):
            raise TypeError(
                f"round_history must be a list[StateSnapshot] (got {type(history).__name__})"
            )
        for index, snapshot in enumerate(history):
            if not isinstance(snapshot, StateSnapshot):
                raise TypeError(
                    f"round_history[{index}] must be a StateSnapshot "
                    f"(got {type(snapshot).__name__})"
                )

        if len(history) < MIN_HISTORY_FOR_DETECTION:
            return _no_cycle(
                rationale=(
                    f"insufficient history (have {len(history)}, "
                    f"need >= {MIN_HISTORY_FOR_DETECTION})"
                ),
                window_size=self.window_size,
                threshold=self.similarity_threshold,
            )

        report = _detect_exact_match(history, self.window_size, self.similarity_threshold)
        if report is not None:
            return report

        report = _detect_fuzzy_match(history, self.window_size, self.similarity_threshold)
        if report is not None:
            return report

        report = _detect_edit_oscillation(history, self.window_size, self.similarity_threshold)
        if report is not None:
            return report

        return _no_cycle(
            rationale=(
                f"no cycle detected over {len(history)} round(s) "
                f"(window={self.window_size}, threshold={self.similarity_threshold:.2f})"
            ),
            window_size=self.window_size,
            threshold=self.similarity_threshold,
        )


def _stringify(value: object) -> str:
    """Render an arbitrary payload value into a stable token string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ",".join(_stringify(v) for v in value)
    if isinstance(value, dict):
        return ",".join(f"{k}={_stringify(v)}" for k, v in sorted(value.items()))
    return str(value)


def _make_snapshot(
    round_num: int,
    *,
    tool: str,
    payload: object,
    files: list[str] | tuple[str, ...] | None = None,
    metadata: dict[str, str] | None = None,
) -> StateSnapshot:
    """Build a :class:`StateSnapshot` from a (tool, payload, files) tuple.

    Module-private convenience helper used by
    :meth:`CycleDetector.record_tool_call` (and by the test suite to
    exercise the deterministic-signature contract). External callers
    should use :class:`StateSnapshot` directly.

    The ``signature`` is rendered deterministically from ``tool`` + sorted
    payload key=value pairs so two structurally identical tool calls
    always hash equal — the contract that drives ``exact_match``.
    The ``tokens`` tuple is the lower-cased, whitespace-split form of
    the rendered payload (used for ``fuzzy_match`` Jaccard similarity).
    """
    if round_num < 1:
        raise ValueError(f"round_num must be >= 1 (got {round_num})")
    if not tool:
        raise ValueError("tool must be a non-empty string")

    rendered_payload = _stringify(payload)
    signature = f"{tool}:{rendered_payload}"
    tokens = tuple(sorted({tok for tok in rendered_payload.lower().split() if tok}))
    file_tuple: tuple[str, ...] = tuple(files or ())
    metadata_pairs: tuple[tuple[str, str], ...] = tuple(
        sorted((str(k), str(v)) for k, v in (metadata or {}).items())
    )
    return StateSnapshot(
        round_num=int(round_num),
        signature=signature,
        tokens=tokens,
        files=file_tuple,
        metadata=metadata_pairs,
    )


__all__ = [
    "CycleDetector",
    "EDIT_OSCILLATION_MIN_LEN",
    "EXACT_MATCH_CRITICAL_RUN",
    "EXACT_MATCH_MIN_RUN",
    "FUZZY_MATCH_MIN_WINDOW",
    "MIN_HISTORY_FOR_DETECTION",
]
