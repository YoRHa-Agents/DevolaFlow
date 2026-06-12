"""L0-side artifact-quality scoring computed FROM L3 evidence blocks.

v15.0.0 SCORING PHASE of the evidence-vs-scoring doctrine split ratified
in `.local/research/adr/v15-ADR-007-artifact-evidence-vs-scoring-doctrine.md`:
the L3 Task Agent emits EVIDENCE ONLY (the v14.3.0 ``self_check`` /
``ac_results`` / ``diff_stats`` blocks per ``schemas/lean-report.yaml``
and the 4-dimension rubric in
``workflow-system/agent/references/artifact-quality.md``); the **L0
Project Agent** computes the artifact quality score FROM that evidence
at workflow close / stage-gate time. The doctrine is never inverted —
**L3 never scores** (W-21-adjacent L0-only framing; enforced at runtime
by the strict ``lifecycle/reject_subagent_quality_score.py`` hook as of
v15.0.0 G-038). This module is the L0-ONLY consumer of the evidence
channel and mirrors the hook's forbidden-key scan: a report that
smuggles a subagent-authored score raises :class:`EvidenceDoctrineError`
(S-5 — never silently accept a doctrine violation).

Pure functions only — no IO beyond the report dict passed in; stdlib +
dataclasses. Gate-consumable since the v15.0.0 R1 reinforcement slice:
:func:`devolaflow.gate.scorer.evaluate_gate` accepts an optional
``artifact_evidence`` report list and runs this scorer per report,
shifting the gate composite by ``profile.artifact_evidence_weight *
(mean_composite - 50)`` (legibility-precedent weight gating; absence is
byte-identical). The wiring direction is gate→scorer — this module
never imports the gate orchestrator. :meth:`ArtifactScore.to_gate_input`
remains the standalone adapter for callers that feed
:func:`devolaflow.gate.scorer.composite_score` directly.

Honesty contract: a dimension whose evidence block is absent is
``unscored`` — EXCLUDED from the composite with the remaining weights
renormalized. Evidence is never fabricated; ``evidence_coverage``
(fraction of dimensions scored) is the honesty signal that travels with
every composite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UNSCORED = "unscored"
"""Rendered value for a dimension whose evidence block is absent."""

COVERAGE_FLOOR_PCT = 80.0
"""S-3 test-coverage floor — ``metrics.cov`` at/above this scores 100."""

LINE_BUDGET = 300
"""Upper bound of the SKILL.md task-sizing contract (~50-300 lines changed)."""

FILE_BUDGET = 6
"""Default writable-file ceiling per the task-sizing contract (max 6 files)."""

SKIP_DISCOUNT = 0.5
"""Credit for skip-tier AC verdicts (``skip`` / ``not_run`` / unknown)."""

DIMENSION_WEIGHTS: dict[str, float] = {
    "correctness": 0.25,
    "minimal_diff": 0.25,
    "test_evidence": 0.25,
    "convention_adherence": 0.25,
}
"""Uniform v15.0.0 starting weights over the artifact-quality.md §2 dimensions.

Uniform because no scoring telemetry exists yet to justify differential
weighting; future cycles may tune via SI-1 gap analysis. Renormalized
over the SCORED subset when dimensions are ``unscored``.
"""

_FORBIDDEN_SCORE_KEYS: tuple[str, ...] = ("quality_score", "quality")
"""Keys that signal an L3-authored score — mirrors the runtime hook.

``gate_input_score`` (the v14.2.1 G-013 rename) is deliberately ABSENT:
it is gate-dimension input EVIDENCE, not a holistic score.
"""

_NESTED_SCAN_BLOCKS: tuple[str, ...] = ("metrics", "self_check")
"""Evidence blocks scanned in addition to the top level (hook parity).

``predecessor_artifacts`` / ``pred`` stay exempt — historical L0 scoring
carried forward as read-only predecessor evidence is legitimate.
"""


class EvidenceDoctrineError(ValueError):
    """Report input carries a forbidden L3-authored quality score.

    Coherent with the strict ``reject_subagent_quality_score`` lifecycle
    hook (v15.0.0 G-038): the same forbidden keys at the same locations
    raise here at scoring time, so a report that bypassed the hook chain
    can never silently feed a smuggled score into the L0 composite.
    """


def _assert_evidence_only(report: dict) -> None:
    """Raise :class:`EvidenceDoctrineError` on any forbidden score field."""
    locations: list[tuple[str, str]] = []
    for key in _FORBIDDEN_SCORE_KEYS:
        if key in report:
            locations.append((key, "top level"))
    for block in _NESTED_SCAN_BLOCKS:
        nested = report.get(block)
        if not isinstance(nested, dict):
            continue
        for key in _FORBIDDEN_SCORE_KEYS:
            if key in nested:
                locations.append((key, f"'{block}' block"))
    if locations:
        rendered = ", ".join(f"{key!r} at {loc}" for key, loc in locations)
        raise EvidenceDoctrineError(
            f"report carries forbidden subagent score field(s): {rendered}. "
            "Per v15-ADR-007, L3 emits evidence only — scoring is L0-side. "
            "Strip the field upstream (gate-dimension input evidence "
            "belongs in 'metrics.gate_input_score')."
        )


@dataclass(frozen=True)
class DimensionScore:
    """Per-dimension result: a 0-100 score or ``unscored``, plus evidence refs.

    ``score is None`` means UNSCORED — the evidence block backing the
    dimension was absent from the report. ``evidence_refs`` are verbatim
    extractions (C-3) naming the transport fields consumed.
    """

    score: float | None
    evidence_refs: tuple[str, ...] = ()

    @property
    def is_scored(self) -> bool:
        return self.score is not None

    def render(self) -> float | str:
        """Return the score, or the :data:`UNSCORED` literal when absent."""
        return self.score if self.score is not None else UNSCORED


@dataclass(frozen=True)
class ArtifactScore:
    """L0-computed artifact quality score derived from L3 evidence blocks.

    ``composite`` is the weighted mean over SCORED dimensions only
    (weights renormalized per the ADR-007 never-fabricate rule); ``None``
    when no dimension had evidence. ``evidence_coverage`` is the scored
    fraction of dimensions (0.0-1.0) — the honesty signal an L0 MUST
    surface alongside the composite.
    """

    dimensions: dict[str, DimensionScore] = field(default_factory=dict)
    composite: float | None = None
    evidence_coverage: float = 0.0

    def to_gate_input(self) -> dict[str, dict[str, float]]:
        """Adapt to the shape the gate composite consumes.

        Returns ``{"dimensions": {...}, "weights": {...}}`` over the
        SCORED dimensions only, with weights renormalized to sum to 1.0,
        such that ``devolaflow.gate.scorer.composite_score(**adapter)``
        reproduces :attr:`composite`. Keeps this module gate-agnostic —
        the gate orchestrator consumes this scorer (via its
        ``artifact_evidence`` parameter since the v15.0.0 R1 wiring);
        this module never invokes the gate.
        """
        scored = {name: dim.score for name, dim in self.dimensions.items() if dim.score is not None}
        if not scored:
            return {"dimensions": {}, "weights": {}}
        total_weight = sum(DIMENSION_WEIGHTS[name] for name in scored)
        # Weights stay unrounded so they renormalize to exactly 1.0;
        # composite_score rounds its own total.
        weights = {name: DIMENSION_WEIGHTS[name] / total_weight for name in scored}
        return {"dimensions": scored, "weights": weights}


def _score_correctness(report: dict) -> DimensionScore:
    """Correctness from ``ac_results`` verdict ratios.

    ``pass`` = full credit (100 basis), ``fail`` = zero credit weighted
    by count, skip-tier verdicts (``skip`` / ``not_run`` / anything not
    pass/fail, per artifact-quality.md §5) earn :data:`SKIP_DISCOUNT`
    credit. Missing or empty ``ac_results`` → unscored.
    """
    rows = report.get("ac_results")
    if not isinstance(rows, list) or not rows:
        return DimensionScore(score=None)
    credit = 0.0
    refs: list[str] = []
    for index, row in enumerate(rows):
        entry = row if isinstance(row, dict) else {}
        verdict = str(entry.get("verdict", "")).lower()
        if verdict == "pass":
            credit += 1.0
        elif verdict != "fail":
            credit += SKIP_DISCOUNT
        ac_id = entry.get("id", f"#{index}")
        refs.append(f"ac_results[{ac_id}]={verdict or 'missing'}")
    score = round(100.0 * credit / len(rows), 2)
    return DimensionScore(score=score, evidence_refs=tuple(refs))


def _score_minimal_diff(report: dict, owned_files_count: int | None) -> DimensionScore:
    """Minimal diff from ``diff_stats`` proportionality.

    Heuristic per artifact-quality.md §2.2: full credit while the diff
    stays inside the file budget (the dispatch's owned-files count when
    provided, else the :data:`FILE_BUDGET` sizing contract) AND the
    :data:`LINE_BUDGET` changed-lines contract; each overshoot scales
    the score by ``budget / actual``. Missing ``diff_stats`` → unscored.
    """
    stats = report.get("diff_stats")
    if not isinstance(stats, dict) or not stats:
        return DimensionScore(score=None)
    files = int(stats.get("files", 0) or 0)
    insertions = int(stats.get("insertions", 0) or 0)
    deletions = int(stats.get("deletions", 0) or 0)
    lines_changed = insertions + deletions
    if owned_files_count is not None and owned_files_count > 0:
        file_budget = owned_files_count
    else:
        file_budget = FILE_BUDGET
    file_factor = 1.0 if files <= file_budget else file_budget / files
    line_factor = 1.0 if lines_changed <= LINE_BUDGET else LINE_BUDGET / lines_changed
    score = round(100.0 * file_factor * line_factor, 2)
    refs = (
        f"diff_stats=files:{files},insertions:{insertions},deletions:{deletions}",
        f"file_budget={file_budget}",
        f"line_budget={LINE_BUDGET}",
    )
    return DimensionScore(score=score, evidence_refs=refs)


def _first_number(metrics: dict, *keys: str) -> float | None:
    """Return the first present numeric value among lean/verbose key spellings."""
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _score_test_evidence(report: dict) -> DimensionScore:
    """Test evidence from ``metrics`` pass/fail counts + coverage vs the floor.

    Two sub-signals, averaged over those present: the pass ratio
    (``pass``/``fail`` lean keys, ``tests_passed``/``tests_failed``
    verbose fallback) and coverage scaled against the
    :data:`COVERAGE_FLOOR_PCT` S-3 floor (capped at 100 — coverage above
    the floor earns no bonus). Missing ``metrics`` or neither sub-signal
    present → unscored.
    """
    metrics = report.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        return DimensionScore(score=None)
    components: list[float] = []
    refs: list[str] = []
    passed = _first_number(metrics, "pass", "tests_passed")
    failed = _first_number(metrics, "fail", "tests_failed")
    total = (passed or 0.0) + (failed or 0.0)
    if (passed is not None or failed is not None) and total > 0:
        components.append(100.0 * (passed or 0.0) / total)
        refs.append(f"metrics pass={int(passed or 0)} fail={int(failed or 0)}")
    coverage = _first_number(metrics, "cov", "coverage_pct")
    if coverage is not None:
        components.append(min(100.0, 100.0 * coverage / COVERAGE_FLOOR_PCT))
        refs.append(f"metrics cov={coverage} (floor {COVERAGE_FLOOR_PCT})")
    if not components:
        return DimensionScore(score=None)
    score = round(sum(components) / len(components), 2)
    return DimensionScore(score=score, evidence_refs=tuple(refs))


def _score_convention_adherence(report: dict) -> DimensionScore:
    """Convention adherence from ``self_check`` completeness.

    Four 25-point gradations per the §2.4 checkable forms: plan anchored
    (``plan_artifact`` non-empty), goal anchored (``goal_anchor``
    non-empty), simplicity declared (BG-002 count or ``"none"`` —
    presence of the declaration, including ``0``), and conflicts +
    conventions surfaced honestly (BOTH BG-006/BG-007 lists present —
    empty lists are an honest "none found"). Missing ``self_check`` →
    unscored.
    """
    self_check = report.get("self_check")
    if not isinstance(self_check, dict) or not self_check:
        return DimensionScore(score=None)
    checks = (
        ("plan_artifact", bool(self_check.get("plan_artifact"))),
        ("goal_anchor", bool(self_check.get("goal_anchor"))),
        ("simplicity", self_check.get("simplicity") is not None),
        (
            "conflicts+conventions",
            isinstance(self_check.get("conflicts"), list)
            and isinstance(self_check.get("conventions"), list),
        ),
    )
    earned = sum(1 for _, present in checks if present)
    refs = tuple(
        f"self_check.{name}={'present' if present else 'missing'}" for name, present in checks
    )
    score = round(100.0 * earned / len(checks), 2)
    return DimensionScore(score=score, evidence_refs=refs)


def score_artifact_evidence(
    report: dict,
    *,
    owned_files_count: int | None = None,
) -> ArtifactScore:
    """Compute the L0-side artifact quality score from a lean StatusReport.

    Consumes the v14.3.0 evidence blocks (``ac_results`` / ``diff_stats``
    / ``metrics`` / ``self_check``) of a lean StatusReport dict per
    ``schemas/lean-report.yaml`` and scores the four
    artifact-quality.md §2 dimensions. ``owned_files_count`` is the
    originating dispatch's owned-files count, used as the minimal-diff
    file budget when provided.

    A dimension whose evidence block is absent is UNSCORED and excluded
    from the composite (remaining weights renormalize — never
    fabricate). No evidence at all → ``composite=None``,
    ``evidence_coverage=0.0``.

    Raises:
      EvidenceDoctrineError: the report carries a forbidden
        ``quality_score`` / ``quality`` field (top level or inside the
        ``metrics`` / ``self_check`` blocks) — doctrine guard coherent
        with the strict ``reject_subagent_quality_score`` hook.
      TypeError: ``report`` is not a dict.
    """
    if not isinstance(report, dict):
        raise TypeError(f"report must be a dict (got {type(report).__name__})")
    _assert_evidence_only(report)

    dimensions: dict[str, DimensionScore] = {
        "correctness": _score_correctness(report),
        "minimal_diff": _score_minimal_diff(report, owned_files_count),
        "test_evidence": _score_test_evidence(report),
        "convention_adherence": _score_convention_adherence(report),
    }

    scored = {name: dim for name, dim in dimensions.items() if dim.score is not None}
    evidence_coverage = round(len(scored) / len(dimensions), 2)

    composite: float | None = None
    if scored:
        total_weight = sum(DIMENSION_WEIGHTS[name] for name in scored)
        weighted = sum(
            dim.score * (DIMENSION_WEIGHTS[name] / total_weight) for name, dim in scored.items()
        )
        composite = round(weighted, 2)

    return ArtifactScore(
        dimensions=dimensions,
        composite=composite,
        evidence_coverage=evidence_coverage,
    )


__all__ = [
    "COVERAGE_FLOOR_PCT",
    "DIMENSION_WEIGHTS",
    "FILE_BUDGET",
    "LINE_BUDGET",
    "SKIP_DISCOUNT",
    "UNSCORED",
    "ArtifactScore",
    "DimensionScore",
    "EvidenceDoctrineError",
    "score_artifact_evidence",
]
