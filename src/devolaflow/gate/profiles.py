"""Predefined gate profiles.

Design ref: design_decomposition_gate.md §5.4

v8.0.0 (P-03) — each profile carries an explicit ``max_tokens`` ceiling
consumed by :class:`devolaflow.gate.budget.TokenBudgetBreaker`. Defaults
per patch_plan §3 P-03:

    STRICT   80_000   tokens / task — most aggressive guard, BREAK ⇒ ESCALATE
    STANDARD 50_000   tokens / task — default for most code work
    RELAXED       0   tokens / task — *unlimited*; breaker disabled
    AUDIT   100_000   tokens / task — long-form review allowance, BREAK ⇒ ESCALATE

v8.0.0 (P-05) — each profile carries a ``ladder_enabled`` opt-in flag
controlling :func:`devolaflow.gate.scorer.evaluate_ladder`. STRICT/AUDIT
default to ``True`` (high-quality work benefits from short-circuited
fail-fast); STANDARD/RELAXED default to ``False`` (byte-identical
pre-P-05 behaviour). See ``patch_plan §3 P-05`` AC #2/#3.

v8.0.0 (P-09) — each profile carries a ``complexity_weight`` factor
controlling how much an :class:`devolaflow.gate.complexity_detector.ComplexityDetector`
WARNING / CRITICAL verdict steers the gate composite. STRICT/AUDIT
default to ``0.10`` (Karpathy "Simplicity First" enforced when quality
matters); STANDARD/RELAXED default to ``0.0`` (opt-in only — supplying
``complexity_detector=None`` keeps :func:`devolaflow.gate.scorer.evaluate_gate`
byte-identical to pre-P-09 behaviour). See ``patch_plan §3 P-09``.

v8.2.0 (PV-02) — each profile carries a ``legibility_weight`` factor
controlling how much an
:class:`devolaflow.legibility.LegibilityScorer` per-file legibility
score steers the gate composite. STRICT/AUDIT default to ``0.05``
(legibility-aware quality work); STANDARD/RELAXED default to ``0.0``
(opt-in only — supplying ``legibility_scorer=None`` keeps
:func:`devolaflow.gate.scorer.evaluate_gate` byte-identical to
pre-PV-02 behaviour). See
``.local/research/v8.2.0_patch_plan.md`` §3 PV-02 AC-4 / AC-5.
"""

from devolaflow.gate.models import GateProfile

STRICT = GateProfile(
    name="strict",
    composite_threshold=90,
    coverage_threshold=85,
    max_blocker=0,
    max_critical=0,
    max_rounds=4,
    min_rounds=2,
    lint_policy="zero_warnings",
    benchmark_policy="required",
    acceptance_readiness_threshold=90,
    visual_fidelity_threshold=95,
    interaction_quality_threshold=95,
    accessibility_threshold=95,
    acceptance_verification_threshold=95,
    max_tokens=80_000,
    ladder_enabled=True,
    complexity_weight=0.10,
    legibility_weight=0.05,
)

STANDARD = GateProfile(
    name="standard",
    composite_threshold=85,
    coverage_threshold=80,
    max_blocker=0,
    max_critical=2,
    max_rounds=3,
    min_rounds=1,
    lint_policy="zero_errors",
    benchmark_policy="optional",
    acceptance_readiness_threshold=80,
    visual_fidelity_threshold=90,
    interaction_quality_threshold=90,
    accessibility_threshold=90,
    acceptance_verification_threshold=90,
    max_tokens=50_000,
    ladder_enabled=False,
)

RELAXED = GateProfile(
    name="relaxed",
    composite_threshold=70,
    coverage_threshold=60,
    max_blocker=0,
    max_critical=5,
    max_rounds=2,
    min_rounds=1,
    lint_policy="zero_errors",
    benchmark_policy="disabled",
    acceptance_readiness_threshold=70,
    visual_fidelity_threshold=80,
    interaction_quality_threshold=80,
    accessibility_threshold=80,
    acceptance_verification_threshold=80,
    max_tokens=0,
    ladder_enabled=False,
)

AUDIT = GateProfile(
    name="audit",
    composite_threshold=95,
    coverage_threshold=90,
    max_blocker=0,
    max_critical=0,
    max_rounds=6,
    min_rounds=3,
    lint_policy="zero_warnings",
    benchmark_policy="required_with_regression_check",
    acceptance_readiness_threshold=95,
    visual_fidelity_threshold=98,
    interaction_quality_threshold=98,
    accessibility_threshold=95,
    acceptance_verification_threshold=98,
    max_tokens=100_000,
    ladder_enabled=True,
    complexity_weight=0.10,
    legibility_weight=0.05,
)

PROFILES: dict[str, GateProfile] = {
    "strict": STRICT,
    "standard": STANDARD,
    "relaxed": RELAXED,
    "audit": AUDIT,
}
