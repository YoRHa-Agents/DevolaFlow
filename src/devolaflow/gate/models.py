"""Gate quality mechanism data models.

Design ref: design_decomposition_gate.md §5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

Severity = Literal["blocker", "critical", "major", "minor", "info"]
GateDecision = Literal["PASS", "FAIL", "ESCALATE"]


class BudgetAction(StrEnum):
    """Outcome of a :class:`devolaflow.gate.budget.TokenBudgetBreaker` check.

    Three paths follow the v8.0.0 P-03 patch plan §3:

    - ``CONTINUE`` — utilization below the warning threshold (default 75 %).
    - ``WARN`` — utilization within the warning band but below 100 %.
    - ``BREAK`` — utilization at or above 100 %; circuit broken.
    """

    CONTINUE = "CONTINUE"
    WARN = "WARN"
    BREAK = "BREAK"


class BudgetRecommendation(StrEnum):
    """Suggested follow-up action paired with a :class:`BudgetAction`.

    The recommendation depends on both action and profile severity:
    STRICT/AUDIT escalate immediately on BREAK, STANDARD/RELAXED first
    iterate with a throttled budget. See ``patch_plan §3 P-03 AC #6``.
    """

    NONE = "NONE"
    THROTTLE = "THROTTLE"
    ITERATE = "ITERATE"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class BudgetDecision:
    """Result of a :class:`devolaflow.gate.budget.TokenBudgetBreaker` check.

    All fields are populated even on the ``CONTINUE`` path so callers can log
    every measurement uniformly without conditional branches. ``utilization``
    is rounded to 4 decimal places and is ``0.0`` whenever ``max_tokens == 0``
    (the unlimited / disabled state).
    """

    action: BudgetAction
    cumulative_tokens: int
    max_tokens: int
    utilization: float
    rationale: str
    recommendation: BudgetRecommendation


GateType = Literal[
    "standard",
    "convergence",
    "passthrough",
    "acceptance_readiness",
    "preflight",
    "revision",
    "escalation",
    "abort",
]

GATE_TYPE_ALIASES: dict[str, str] = {
    "standard": "revision",
    "convergence": "revision",
}
ProfileName = Literal["strict", "standard", "relaxed", "audit"]
LintPolicy = Literal["zero_warnings", "zero_errors", "advisory"]
BenchmarkPolicy = Literal["required", "optional", "disabled", "required_with_regression_check"]


@dataclass(frozen=True)
class AcceptanceCriterionResult:
    """Quality scores for a single acceptance criterion.

    Each dimension is scored 0–100. Used by the acceptance_readiness gate
    to evaluate criteria quality before work begins.
    """

    criterion_id: str
    text: str
    testability: float
    completeness: float
    measurability: float
    independence: float
    clarity: float


@dataclass(frozen=True)
class Finding:
    """A single review finding produced by code/architecture review."""

    finding_id: str
    severity: Severity
    category: str
    location: str
    description: str
    suggestion: str = ""
    rule_id: str = ""


@dataclass
class CheckResult:
    """Result of a single gate check (build/test/lint/review)."""

    status: Literal["pass", "fail", "skip"]
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class GateInput:
    """Aggregated inputs fed into gate evaluation."""

    build_status: CheckResult
    test_results: CheckResult
    lint_status: CheckResult
    review_findings: list[Finding] = field(default_factory=list)
    acceptance_criteria_results: CheckResult | None = None
    acceptance_readiness_criteria: list[AcceptanceCriterionResult] = field(
        default_factory=list,
    )
    # v5.4.0: User-facing verification inputs
    visual_test_results: CheckResult | None = None
    interaction_test_results: CheckResult | None = None
    accessibility_results: CheckResult | None = None
    acceptance_verification_results: CheckResult | None = None
    # v8.0.0 (P-10) — Structured acceptance-criterion verdicts (one per
    # :class:`AcceptanceCriterion` in the dispatch payload's
    # ``acceptance_criteria_v2`` field). Default ``None`` keeps
    # behaviour byte-identical to pre-P-10 — :func:`evaluate_gate` does
    # NOT consult this field unless callers explicitly aggregate it into
    # ``acceptance_criteria_results`` via
    # :func:`devolaflow.gate.scorer.aggregate_criterion_verdicts`. The
    # field is exposed so downstream consumers (Project / Stage agents,
    # StatusReport renderers) can surface per-criterion outcomes without
    # re-running ``verification_cmd``.
    acceptance_criterion_verdicts: list[AcceptanceCriterionVerdict] | None = None


@dataclass
class GateVerdict:
    """The output of a gate evaluation."""

    decision: GateDecision
    rationale: str
    composite_score: float | None = None
    meets_threshold: bool = False
    details: dict[str, object] = field(default_factory=dict)
    escalation_context: str = ""
    post_mortem: dict[str, object] = field(default_factory=dict)
    advisor_recommended: bool = False
    advisor_verdict: str = ""
    advisor_context: str = ""


@dataclass(frozen=True)
class GateProfile:
    """Configurable quality profile controlling gate strictness.

    See §5.4 for the four predefined profiles.
    """

    name: ProfileName
    composite_threshold: float
    coverage_threshold: float
    max_blocker: int
    max_critical: int
    max_rounds: int
    min_rounds: int
    lint_policy: LintPolicy
    benchmark_policy: BenchmarkPolicy
    acceptance_readiness_threshold: float = 80.0
    # v5.4.0: User-facing verification thresholds
    visual_fidelity_threshold: float = 0.0
    interaction_quality_threshold: float = 0.0
    accessibility_threshold: float = 0.0
    acceptance_verification_threshold: float = 0.0
    advisor_margin: float = 5.0
    # v7.2.2: Convergence-loop noise filter (P-01).
    # Fraction of the 0-100 composite-score scale to treat as the noise band
    # when calling :func:`devolaflow.gate.convergence.detect_stagnation` and
    # :func:`devolaflow.gate.convergence.compute_smoothed_trend`. Default 0.0
    # preserves bytewise pre-v7.2.2 behavior (single non-improving round =
    # stagnation, pairwise trend). Values > 0 require >= 2 consecutive rounds
    # of within-band deltas before declaring stagnation, and switch the
    # trend classifier to a window-3 moving average.
    noise_tolerance_pct: float = 0.0
    # v8.0.0 (P-03) — token-budget circuit breaker ceiling per task. ``0``
    # (the default) means *unlimited* and renders the breaker a no-op,
    # preserving byte-identical pre-P-03 behaviour for any caller that does
    # not opt in via ``devolaflow.gate.budget.TokenBudgetBreaker``.
    # Profile-specific defaults (per patch_plan §3 P-03):
    #   STRICT   80_000   STANDARD 50_000
    #   RELAXED       0   AUDIT   100_000
    max_tokens: int = 0
    # v8.0.0 (P-05) — verification-ladder opt-in flag. ``False`` (the
    # default) makes :func:`devolaflow.gate.scorer.evaluate_ladder`
    # delegate to :func:`devolaflow.gate.scorer.evaluate_gate` for
    # byte-identical pre-P-05 behaviour. ``True`` activates the 6-rung
    # short-circuit ladder per ``patch_plan §3 P-05 AC #1/#2/#3``.
    # Profile-specific defaults: STRICT/AUDIT enable, STANDARD/RELAXED
    # remain disabled until the orchestrator opts in.
    ladder_enabled: bool = False
    # v8.0.0 (P-09) — overcomplexity-detector dimension weight. ``0.0``
    # (the default) means the optional
    # :class:`devolaflow.gate.complexity_detector.ComplexityDetector`
    # contributes nothing to the gate composite — supplying
    # ``complexity_detector=None`` to
    # :func:`devolaflow.gate.scorer.evaluate_gate` then keeps the
    # behaviour byte-identical to pre-P-09 (per ``patch_plan §3 P-09``).
    # Profile-specific defaults: STRICT/AUDIT 0.10 (Karpathy "Simplicity
    # First" enforced); STANDARD/RELAXED 0.0 (opt-in only).
    complexity_weight: float = 0.0
    # v8.2.0 (PV-02) — agent legibility dimension weight. ``0.0`` (the
    # default) means the optional
    # :class:`devolaflow.legibility.LegibilityScorer` contributes
    # nothing to the gate composite — supplying ``legibility_scorer=None``
    # to :func:`devolaflow.gate.scorer.evaluate_gate` then keeps the
    # behaviour byte-identical to v8.1.0-rc.1 (per
    # ``.local/research/v8.2.0_patch_plan.md`` §3 PV-02 AC-5).
    # Profile-specific defaults: STRICT/AUDIT 0.05 (legibility-aware
    # quality work); STANDARD/RELAXED 0.0 (opt-in only).
    legibility_weight: float = 0.0
    abort_categories: list[str] = field(
        default_factory=lambda: ["security", "data_loss"],
    )
    preflight_checks: list[str] = field(default_factory=list)


@dataclass
class ConvergenceRound:
    """Snapshot of a single convergence round for trend tracking."""

    round_num: int
    composite_score: float
    blocker_count: int
    critical_count: int
    timestamp: str


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-05) — Verification Ladder Formalization
#
# Formalizes a 6-rung verification ladder R1..R6 with deterministic
# short-circuit semantics. When an earlier rung FAILs, all later rungs are
# marked ``skip`` and not executed (per ``patch_plan §3 P-05 AC #1``).
#
# ``LadderRung`` (R1..R6) maps to the canonical ordering:
#
#     R1 = lint        (cheap, run first)
#     R2 = typecheck   (compile-time guarantees)
#     R3 = unit_test   (deterministic, fast)
#     R4 = integration (slower, may need fixtures)
#     R5 = benchmark   (perf budget enforcement)
#     R6 = convergence (composite-score / quality-gate evaluation)
#
# Earlier rungs are intentionally cheaper so failures abort before LLM /
# review cycles spend tokens — Karpathy "fail fast on cheap signals" per
# upstream tweet analysis ``v7.8`` §4.10.
# ─────────────────────────────────────────────────────────────────────────────


class LadderRung(StrEnum):
    """One of the 6 rungs in the v8.0.0 P-05 verification ladder.

    Order matters — :func:`devolaflow.gate.scorer.evaluate_ladder` walks
    R1 → R6 and short-circuits on the first ``fail`` (later rungs are
    marked ``skip``).
    """

    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"
    R6 = "R6"


# Stable mapping from each :class:`LadderRung` to its canonical name. Used
# by :class:`LadderEvaluation` consumers for human-facing reports and by
# the test suite for naming assertions. Pinned to satisfy S-4 (no ghost
# features — the rung names appear in CHANGELOG / docs verbatim).
LADDER_RUNG_NAMES: dict[LadderRung, str] = {
    LadderRung.R1: "lint",
    LadderRung.R2: "typecheck",
    LadderRung.R3: "unit_test",
    LadderRung.R4: "integration_test",
    LadderRung.R5: "benchmark",
    LadderRung.R6: "convergence",
}


# Canonical iteration order for the ladder — R1 → R6 (used by the scorer).
# Wrapped in a tuple so it is immutable from the caller's perspective.
LADDER_RUNG_ORDER: tuple[LadderRung, ...] = (
    LadderRung.R1,
    LadderRung.R2,
    LadderRung.R3,
    LadderRung.R4,
    LadderRung.R5,
    LadderRung.R6,
)


LadderRungStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class LadderEvaluation:
    """Outcome of evaluating one rung in the verification ladder.

    Three :pyattr:`status` paths follow ``patch_plan §3 P-05 AC #5``
    (S-5 No Silent Failures — the enum is exhaustive):

    - ``pass`` — rung executed and succeeded.
    - ``fail`` — rung executed and failed; later rungs short-circuit to ``skip``.
    - ``skip`` — rung not applicable (no input) OR short-circuited by an
      earlier failing rung. The :pyattr:`message` distinguishes the two.

    All fields are populated even on the ``skip`` path so callers can log
    every rung uniformly without conditional branches.
    """

    rung: LadderRung
    status: LadderRungStatus
    message: str
    name: str = ""
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Auto-fill the human-facing name from the canonical mapping. The
        # ``object.__setattr__`` dance is needed because the dataclass is
        # frozen — we still want a stable default without forcing every
        # caller to repeat ``LADDER_RUNG_NAMES[rung]``.
        if not self.name:
            object.__setattr__(self, "name", LADDER_RUNG_NAMES[self.rung])


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-06) — Cycle Detection Middleware
#
# Detects three classes of convergence-loop pathology in the per-round
# tool-call / edit history (per ``patch_plan §3 P-06``):
#
#     exact_match       — two or more consecutive rounds with identical
#                         signature (perfect repetition).
#     fuzzy_match       — three or more consecutive rounds whose token-bag
#                         Jaccard similarity is ≥ ``similarity_threshold``
#                         (default 0.8 — Karpathy "fail fast on near-dup").
#     edit_oscillation  — alternating A→B→A pattern over the last 3+
#                         snapshots that touch the same files (the classic
#                         agent flip-flop on a single file).
#
# ``StateSnapshot`` is the round-level capture (signature + tokens + files)
# fed into :class:`devolaflow.gate.cycle_detector.CycleDetector`. Both
# dataclasses are frozen so the detector can hash and compare them safely
# without defensive copies (S-5 — no silent mutation across rounds).
# ─────────────────────────────────────────────────────────────────────────────


CycleType = Literal[
    "none",
    "exact_match",
    "fuzzy_match",
    "edit_oscillation",
]


# Canonical default severities per cycle type. Mirrors ``patch_plan §3
# P-06 AC #1`` (exact_match → ``major``) and extends consistently to the
# other two paths so ``cycle_to_instruction`` always emits a rule at or
# above the default ``severity_floor='major'`` of
# :func:`devolaflow.gate.reinforcement.findings_to_reinforcement`.
CYCLE_DEFAULT_SEVERITY: dict[str, Severity] = {
    "exact_match": "major",
    "fuzzy_match": "major",
    "edit_oscillation": "major",
    "none": "info",
}


@dataclass(frozen=True)
class StateSnapshot:
    """A single convergence round captured for cycle detection.

    Frozen + hashable so :class:`devolaflow.gate.cycle_detector.CycleDetector`
    can safely compare signatures across rounds without defensive copies.

    Attributes
    ----------
    round_num:
        1-based round ordinal. Drives the deterministic id format used by
        :func:`devolaflow.gate.reinforcement.cycle_to_instruction`.
    signature:
        Canonical, hashable string representation of this round's tool-call
        / edit. Two snapshots compare ``equal`` for ``exact_match`` iff
        their signatures are byte-equal.
    tokens:
        Optional normalised token bag (whitespace-split, lower-cased) used
        for ``fuzzy_match`` Jaccard similarity. Empty tuple disables fuzzy
        matching for this snapshot.
    files:
        Optional tuple of file paths edited in this round. Used by
        ``edit_oscillation`` to detect alternating same-file edits.
    metadata:
        Free-form ``{str: str}`` mapping for caller-side annotations
        (e.g. tool name, dispatch id). Not consulted by the detector but
        forwarded into :class:`CycleReport.evidence` for downstream
        ReinforcementRule rendering.
    """

    round_num: int
    signature: str
    tokens: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CycleReport:
    """Outcome of running :meth:`devolaflow.gate.cycle_detector.CycleDetector.detect`.

    Three detection paths follow ``patch_plan §3 P-06 AC #1/#2/#3``:

    - ``cycle_type='exact_match'`` — ≥ 2 consecutive snapshots with
      identical ``signature``.
    - ``cycle_type='fuzzy_match'`` — ≥ ``window_size`` consecutive
      snapshots with pairwise Jaccard similarity ≥ ``similarity``.
    - ``cycle_type='edit_oscillation'`` — alternating A→B→A pattern over
      the last 3+ snapshots touching the same file set.
    - ``cycle_type='none'`` — no cycle detected.

    All fields are populated even on the ``none`` path so callers can log
    every measurement uniformly without conditional branches (S-5).

    Attributes
    ----------
    detected:
        ``True`` iff a cycle of any type was identified.
    cycle_type:
        Path that fired (``exact_match`` / ``fuzzy_match`` /
        ``edit_oscillation`` / ``none``).
    severity:
        Default per :data:`CYCLE_DEFAULT_SEVERITY`. May be overridden by
        the detector when a particularly egregious cycle is found (e.g. ≥ 4
        consecutive identical signatures escalates to ``critical``).
    evidence:
        Human-readable, verbatim list of snapshot signatures (and pairwise
        similarity ratios for ``fuzzy_match``) that triggered the verdict.
        Exactly the strings :func:`devolaflow.gate.reinforcement.cycle_to_instruction`
        renders into the ``MUST NOT repeat`` mandate.
    repeated_signatures:
        Tuple of the distinct repeated signatures (length ≥ 1 when
        ``detected``). For ``edit_oscillation`` this carries the two
        alternating signatures in their first-seen order.
    similarity:
        Pairwise Jaccard similarity that caused ``fuzzy_match`` to fire,
        or ``1.0`` for ``exact_match``, or ``0.0`` for ``none``.
    rationale:
        Single-line summary suitable for ``GateVerdict.rationale``.
    window_size:
        ``CycleDetector.window_size`` at the time of detection. Echoed
        back so callers can reproduce the verdict without re-reading the
        detector's state.
    threshold:
        ``CycleDetector.similarity_threshold`` at the time of detection.
    """

    detected: bool
    cycle_type: CycleType
    severity: Severity
    evidence: tuple[str, ...] = ()
    repeated_signatures: tuple[str, ...] = ()
    similarity: float = 0.0
    rationale: str = ""
    window_size: int = 0
    threshold: float = 0.0
    rounds: tuple[int, ...] = ()
    files: tuple[str, ...] = ()

    @property
    def detection_type(self) -> CycleType:
        """Backward-compatible alias for :pyattr:`cycle_type`.

        ``patch_plan §3 P-06`` originally specified the field name
        ``detection_type``; the public surface uses ``cycle_type`` per the
        L3 task contract. This alias keeps existing call sites that read
        the patch plan name compiling without a rename.
        """
        return self.cycle_type


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-07) — Monotonic Ratchet Guarantee (G13 closure)
#
# The ratchet records per-round oracle scores in an append-only log and
# emits one of four verdicts on each new round (per ``patch_plan §3 P-07
# AC #1-#4``):
#
#     ADVANCE   — strict score lift over the recorded best; rotate best.
#     TOLERATE  — score equal-or-near-best within ``regression_tolerance``;
#                 keep best, no escalation.
#     ROLLBACK  — score below best by more than the tolerance for the
#                 ``max_regressions``-th consecutive round; restore the
#                 saved ``ArtifactSnapshot``.
#     ESCALATE  — a round AFTER a ROLLBACK still cannot beat best; the
#                 loop is stuck and must escalate per P4 bounded retry.
#
# The deterministic oracle score (test+lint+build only — review_findings
# excluded) lives in :func:`devolaflow.gate.scorer.compute_deterministic_oracle_score`
# so the ratchet is unaffected by S/O/R-style review-finding gaming
# (Karpathy "non-gameable success criteria" per upstream tweet analysis
# ``v7.8`` §4.11).
# ─────────────────────────────────────────────────────────────────────────────


class RatchetAction(StrEnum):
    """One of the 4 verdict paths emitted by :class:`MonotonicRatchet`.

    Ordered by escalation severity — ``ADVANCE`` is the happy path,
    ``ESCALATE`` aborts the convergence loop. The enum is exhaustive
    (S-5 — every ``record_round`` invocation MUST return one of these
    four values, never ``None``).
    """

    ADVANCE = "ADVANCE"
    TOLERATE = "TOLERATE"
    ROLLBACK = "ROLLBACK"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class ArtifactSnapshot:
    """Immutable per-round capture used for ratchet rollback.

    Stored on the :class:`devolaflow.gate.ratchet.MonotonicRatchet` whenever
    a round produces a new best deterministic oracle score. On a
    ``ROLLBACK`` verdict the consumer reinstates the saved
    :pyattr:`payload` so the convergence loop resumes from the last
    known-good state instead of letting the loop drift downward.

    Attributes
    ----------
    round_num:
        1-based round ordinal that produced the snapshot.
    score:
        Deterministic oracle score that justified saving this snapshot.
        Computed via
        :func:`devolaflow.gate.scorer.compute_deterministic_oracle_score`.
    payload_hash:
        Stable digest of :pyattr:`payload` (e.g. ``hashlib.sha256``
        hex-digest of a canonicalised JSON dump). Lets downstream
        verifiers prove the rollback target is byte-identical to the
        original snapshot without re-loading the full payload.
    payload:
        Free-form mapping carrying whatever artifact state the consumer
        needs to restore on rollback (file diffs, dispatch payload,
        intermediate gate verdict, etc.). Intentionally permissive —
        the ratchet never inspects the contents.
    """

    round_num: int
    score: float
    payload_hash: str = ""
    payload: dict[str, object] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-09) — Overcomplexity Detector
#
# Wraps a NineS subprocess (https://github.com/YoRHa-Agents/NineS) plus a
# tier-aware verdict matrix to flag changes that exceed the complexity
# budget for the declared ``task_complexity`` (Karpathy "Simplicity First"
# per upstream tweet analysis ``v7.8`` §4.13).
#
# Three verdict paths (per ``patch_plan §3 P-09 AC #1-#3``):
#
#     OK        — every signal sits inside the tier's headroom; ratify.
#     WARNING   — at least one signal crossed the tier's *soft* ceiling
#                 (lines_changed, ratio_to_minimal, files_touched,
#                 nesting_depth, new_abstractions, OR cyclomatic
#                 complexity > 10). Inject a "may be overcomplicated"
#                 ReinforcementRule but do NOT block.
#     CRITICAL  — at least one *hard* invariant broken: cyclomatic
#                 complexity > 15, OR NineS surfaces an ERROR-severity
#                 finding. Decreases composite_score and flips the
#                 verdict to ITERATE per ``patch_plan §3 P-09``.
#
# ``ComplexitySignals`` is the immutable per-task capture fed into
# :meth:`devolaflow.gate.complexity_detector.ComplexityDetector.evaluate`
# — frozen so it can be hashed / compared across rounds without
# defensive copies (S-5 — no silent mutation).
# ─────────────────────────────────────────────────────────────────────────────


TaskComplexityTier = Literal["trivial", "simple", "standard", "complex"]


VALID_TASK_COMPLEXITY_TIERS: frozenset[str] = frozenset(
    {"trivial", "simple", "standard", "complex"},
)


class ComplexityVerdict(StrEnum):
    """One of the 3 verdict paths emitted by :class:`ComplexityDetector`.

    Ordered by escalation severity — ``OK`` is the happy path,
    ``CRITICAL`` blocks the gate. The enum is exhaustive (S-5 — every
    ``evaluate`` call MUST return one of these three values, never
    ``None``). Per ``patch_plan §3 P-09``:

    - ``OK`` — all signals within tier headroom.
    - ``WARNING`` — at least one *soft* ceiling crossed; reinforcement
      injected, gate stays ``PASS``.
    - ``CRITICAL`` — at least one *hard* invariant broken (cc > 15 OR
      NineS ERROR finding); composite_score reduced + ITERATE.
    """

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ComplexitySignals:
    """Per-task signal bundle consumed by :class:`ComplexityDetector`.

    Frozen + hashable so the detector can compare signals across rounds
    without defensive copies (S-5 — no silent mutation across rounds).
    All fields are non-negative; the constructor raises
    :class:`ValueError` when invariants are broken.

    Attributes
    ----------
    lines_changed:
        Net lines of code touched in this change set (added + modified).
        Compared against the tier's line budget ceiling.
    files_touched:
        Number of distinct source files modified.
    new_abstractions:
        Newly introduced classes, modules, or interfaces. Counted
        separately from method additions because abstractions carry a
        higher long-term complexity tax (Karpathy "minimal abstraction
        budget" per upstream tweet analysis ``v7.8`` §4.13).
    nesting_depth_max:
        Worst-case block nesting depth observed in any new function.
        Compared against the tier's nesting ceiling.
    cyclomatic_complexity:
        Maximum cyclomatic complexity across all new / modified
        functions. ``> 10`` triggers WARNING, ``> 15`` triggers CRITICAL
        (per ``patch_plan §3 P-09``).
    ratio_to_minimal:
        Ratio of the change-set complexity to the minimal-viable
        solution. ``5.0`` for a ``complex`` tier task triggers WARNING
        (per ``patch_plan §3 P-09 AC #3``). ``0.0`` is treated as
        "unknown / not measured" and skipped from the ratio check.
    nines_error_findings:
        Count of ERROR-severity findings surfaced by NineS deep
        analysis. Any value ``> 0`` triggers CRITICAL.
    nines_warn_findings:
        Count of WARN-severity findings surfaced by NineS. Used to
        elevate WARNING evidence but does NOT trigger CRITICAL on its
        own (the ``cc > 15`` / ERROR finding paths handle that).
    """

    lines_changed: int = 0
    files_touched: int = 0
    new_abstractions: int = 0
    nesting_depth_max: int = 0
    cyclomatic_complexity: int = 0
    ratio_to_minimal: float = 0.0
    nines_error_findings: int = 0
    nines_warn_findings: int = 0

    def __post_init__(self) -> None:
        if self.lines_changed < 0:
            raise ValueError(f"lines_changed must be >= 0 (got {self.lines_changed})")
        if self.files_touched < 0:
            raise ValueError(f"files_touched must be >= 0 (got {self.files_touched})")
        if self.new_abstractions < 0:
            raise ValueError(f"new_abstractions must be >= 0 (got {self.new_abstractions})")
        if self.nesting_depth_max < 0:
            raise ValueError(f"nesting_depth_max must be >= 0 (got {self.nesting_depth_max})")
        if self.cyclomatic_complexity < 0:
            raise ValueError(
                f"cyclomatic_complexity must be >= 0 (got {self.cyclomatic_complexity})"
            )
        if self.ratio_to_minimal < 0.0:
            raise ValueError(f"ratio_to_minimal must be >= 0.0 (got {self.ratio_to_minimal})")
        if self.nines_error_findings < 0:
            raise ValueError(f"nines_error_findings must be >= 0 (got {self.nines_error_findings})")
        if self.nines_warn_findings < 0:
            raise ValueError(f"nines_warn_findings must be >= 0 (got {self.nines_warn_findings})")


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-10) — Automatic Acceptance Criteria generation
#
# Structured successor to the legacy ``acceptance_criteria: list[str]``
# alias (R5 backward compatibility — the legacy alias is PRESERVED and
# continues to validate via ``src/devolaflow/lifecycle/validate_dispatch.py``).
# The new ``AcceptanceCriterion`` dataclass mirrors the dispatch field
# shape declared in ``schemas/lean-dispatch.yaml#lean_format_spec.
# acceptance_criteria_v2`` (canonical_order position 15, schema version 4
# — additive per ADR-001 §2).
#
# Three :pyattr:`verification_type` paths follow ``patch_plan §3 P-10
# AC #1/#2``:
#
#     test    — ``verification_cmd`` is a shell command whose exit code
#               determines pass/fail (``ACGenerator.generate("fix bug X")``
#               returns this path by default).
#     metric  — ``metric`` + ``threshold`` define a numeric assertion the
#               caller evaluates externally (``ACGenerator.generate
#               ("improve performance")`` returns this path; the gate
#               surfaces it as ``skip`` until a metric runner ratifies).
#     manual  — Human-only verification; the gate marks it ``skip`` and
#               surfaces it for advisor review (S-5 — never silently
#               treat manual checks as PASS).
#
# ``AcceptanceCriterionVerdict`` captures the per-criterion outcome
# emitted by :func:`devolaflow.gate.scorer.evaluate_acceptance_criteria_v2`.
# The verdict list lives on :pyattr:`GateInput.acceptance_criterion_verdicts`
# (default ``None`` — byte-identical to pre-P-10 fallback).
# ─────────────────────────────────────────────────────────────────────────────


VerificationType = Literal["test", "metric", "manual"]


VALID_VERIFICATION_TYPES: frozenset[str] = frozenset({"test", "metric", "manual"})


CriterionVerdictStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class AcceptanceCriterion:
    """One structured acceptance criterion (v8.0.0 P-10).

    Frozen + hashable so the gate can compare criterion identity across
    rounds without defensive copies (S-5 — no silent mutation across
    rounds). ``id`` is the stable handle the verdict refers back to.

    Attributes
    ----------
    id:
        Short stable identifier (e.g. ``"AC-001"``). MUST be unique per
        dispatch payload — duplicate ids cause
        :func:`devolaflow.gate.scorer.evaluate_acceptance_criteria_v2`
        to raise :class:`ValueError`.
    description:
        Human-readable criterion text (≤ 200 chars recommended).
    verification_type:
        One of ``test`` / ``metric`` / ``manual``.
    verification_cmd:
        Shell command consulted when ``verification_type='test'``. Empty
        string is allowed for the other two types.
    metric:
        Metric name consulted when ``verification_type='metric'``
        (e.g. ``"latency_p95_ms"``). Empty for the other two types.
    threshold:
        Threshold expression consulted when
        ``verification_type='metric'`` (e.g. ``"<= baseline * 0.9"``).
        Empty for the other two types.
    """

    id: str
    description: str
    verification_type: VerificationType
    verification_cmd: str = ""
    metric: str = ""
    threshold: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("AcceptanceCriterion.id must be a non-empty string")
        if not self.description:
            raise ValueError("AcceptanceCriterion.description must be a non-empty string")
        if self.verification_type not in VALID_VERIFICATION_TYPES:
            raise ValueError(
                "AcceptanceCriterion.verification_type must be one of "
                f"{sorted(VALID_VERIFICATION_TYPES)} (got {self.verification_type!r})"
            )


@dataclass(frozen=True)
class AcceptanceCriterionVerdict:
    """Per-criterion outcome emitted by ``evaluate_acceptance_criteria_v2``.

    Three :pyattr:`status` paths (S-5 No Silent Failures — the enum is
    exhaustive):

    - ``pass`` — verification succeeded (test exit 0, metric satisfied,
      or manual review approved).
    - ``fail`` — verification failed (test non-zero exit, metric breach,
      or manual review rejected).
    - ``skip`` — verification deferred (no runner provided for the type,
      or manual review pending). NEVER silently treated as ``pass``.

    All fields are populated even on the ``skip`` path so callers can
    log every measurement uniformly without conditional branches.
    """

    criterion_id: str
    status: CriterionVerdictStatus
    message: str = ""
    details: dict[str, object] = field(default_factory=dict)
