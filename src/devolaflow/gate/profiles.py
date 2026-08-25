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
(legibility-aware quality work); RELAXED defaults to ``0.0``
(opt-in only — supplying ``legibility_scorer=None`` keeps
:func:`devolaflow.gate.scorer.evaluate_gate` byte-identical to
pre-PV-02 behaviour). See
``.local/research/v8.2.0_patch_plan.md`` §3 PV-02 AC-4 / AC-5.

v15.0.0 (G-038 flip 6) — STANDARD's ``legibility_weight`` graduates
``0.0`` → ``0.05``, matching the STRICT/AUDIT value (the default flip
telegraphed as "a v15.0.0 ladder item" by the v14.4.0 opt-in landing /
v14.2.0 gap register §4.1). RELAXED stays ``0.0``. Opt-out: profiles
are frozen dataclasses — ``dataclasses.replace(STANDARD,
legibility_weight=0.0)`` restores the pre-v15.0.0 composite
byte-for-byte (the same `references/decomposition-gate.md` §5.6
override knob, pointed the other way). NOTE: the weight only engages
when a caller supplies a ``legibility_scorer`` to ``evaluate_gate`` —
STANDARD's ``legibility_enabled`` auto-wire flag remains ``False``.

v15.0.0 (R1 gate wiring per v15-ADR-007) — each profile carries an
``artifact_evidence_weight`` factor controlling how much the L0-side
:func:`devolaflow.gate.artifact_score.score_artifact_evidence`
composite (computed from L2 evidence blocks) steers the gate
composite. Mirrors the legibility precedent exactly:
STRICT/STANDARD/AUDIT default to ``0.05``; RELAXED defaults to
``0.0`` (opt-in only — supplying ``artifact_evidence=None`` keeps
:func:`devolaflow.gate.scorer.evaluate_gate` byte-identical to the
pre-wiring T4 phase).

v8.2.0 (PV-05) — each profile carries two opt-in primitive auto-wire
flags (``legibility_enabled`` + ``cycle_detector_enabled``) flipped to
``True`` on STRICT only (B3 partial closure per
``.local/research/v8.1.0_gap_analysis.md`` §3.2). The flags signal
to downstream orchestrators that the primitive SHOULD be auto-wired
(default scorer / detector instantiated when an explicit one is not
supplied). STANDARD / RELAXED / AUDIT keep the v8.1.0-rc.1 defaults
(``False``) — only STRICT flips this cycle. The other 5 v8.0.0 opt-in
primitives (complexity_detector, acceptance_criteria_v2,
fence-instruction injection, entropy-cleanup workflow, ratchet) stay
opt-in and are queued for the v8.2.x bench. See
``.local/research/v8.2.0_patch_plan.md`` §3 PV-05 AC-5.

v9.0.0 PV-06 (v8.5.1) — Theme T5 5-primitive default-on flip closure.
The 5 v8.0.0 gate primitives (``budget_breaker_enabled`` +
``ladder_enabled`` + ``ratchet_enabled`` + ``complexity_detector_enabled``
+ ``ac_generator_enabled``) flip from opt-in to default-ON for STRICT
AND AUDIT decomposition profiles. Per env-flags.md §4 the flip moves
the 5 forward-declared flags from §4 (forward-declared) to §2 (active
runtime flags) — operators opt OUT per-primitive via the env-flag
listed in env-flags.md §2.6..§2.10 (each set EXACTLY to ``"0"`` per R5
strict parsing). The retired benchmark scenario evidence is documented in
``docs/cycle-archive/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md``;
the live contracts are unit-tested directly.
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
    # v15.0.0 R1 — artifact-evidence gate dimension (v15-ADR-007 wiring;
    # mirrors the legibility default).
    artifact_evidence_weight=0.05,
    legibility_enabled=True,
    cycle_detector_enabled=True,
    # v9.0.0 PV-06 (v8.5.1) Theme T5 — 5 primitives default-ON for STRICT.
    # Operators opt OUT per env-flags.md §2 (each EXACTLY "0" per R5 strict).
    budget_breaker_enabled=True,
    ratchet_enabled=True,
    complexity_detector_enabled=True,
    ac_generator_enabled=True,
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
    # v15.0.0 G-038 flip 6 — 0.0 → 0.05 (matches STRICT/AUDIT; RELAXED
    # stays 0.0). Opt-out: replace(STANDARD, legibility_weight=0.0).
    legibility_weight=0.05,
    # v15.0.0 R1 — artifact-evidence gate dimension (v15-ADR-007 wiring).
    artifact_evidence_weight=0.05,
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
    # v15.0.0 R1 — artifact-evidence gate dimension (v15-ADR-007 wiring;
    # mirrors the legibility default).
    artifact_evidence_weight=0.05,
    # v9.0.0 PV-06 (v8.5.1) Theme T5 — 5 primitives default-ON for AUDIT.
    # AUDIT inherits the same legibility / cycle_detector defaults as STRICT
    # (B3 partial closure surface — no behaviour drift between the two
    # high-rigour profiles). Operators opt OUT per env-flags.md §2.
    legibility_enabled=True,
    cycle_detector_enabled=True,
    budget_breaker_enabled=True,
    ratchet_enabled=True,
    complexity_detector_enabled=True,
    ac_generator_enabled=True,
)

PROFILES: dict[str, GateProfile] = {
    "strict": STRICT,
    "standard": STANDARD,
    "relaxed": RELAXED,
    "audit": AUDIT,
}
