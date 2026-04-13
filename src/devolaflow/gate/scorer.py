"""Gate composite scorer and quality scorer.

Design ref: design_decomposition_gate.md §5.3, §5.7
NineS integration: §nines-integration
"""

from __future__ import annotations

import warnings
from collections import Counter
from collections.abc import Sequence

from devolaflow.gate.convergence import compute_trend, detect_stagnation
from devolaflow.gate.models import (
    GATE_TYPE_ALIASES,
    AcceptanceCriterionResult,
    ConvergenceRound,
    Finding,
    GateInput,
    GateProfile,
    GateVerdict,
)

SEVERITY_WEIGHTS: dict[str, int] = {
    "blocker": 25,
    "critical": 15,
    "major": 5,
    "minor": 1,
    "info": 0,
}

DEFAULT_DIMENSION_WEIGHTS: dict[str, float] = {
    "test_quality": 0.30,
    "code_review": 0.30,
    "architecture": 0.20,
    "benchmark": 0.20,
}

ARS_DIMENSION_WEIGHTS: dict[str, float] = {
    "testability": 0.30,
    "completeness": 0.25,
    "measurability": 0.20,
    "clarity": 0.15,
    "independence": 0.10,
}

ARS_DIMENSION_SUGGESTIONS: dict[str, str] = {
    "testability": (
        "Rewrite criteria with verifiable conditions (e.g., 'All tests pass' not 'works correctly')"
    ),
    "completeness": "Add criteria to cover all expected outputs and edge cases",
    "measurability": "Include quantitative thresholds (e.g., 'latency < 200ms', 'coverage >= 80%')",
    "clarity": "Remove ambiguous terms; use precise, unambiguous language",
    "independence": (
        "Ensure each criterion can be verified independently without coupling to others"
    ),
}


def quality_score(findings: list[Finding]) -> float:
    """Compute the quality score from review findings.

    Formula (§5.3): ``max(0, 100 - sum(severity_weight * count))``
    """
    counts: Counter[str] = Counter(f.severity for f in findings)
    penalty = sum(SEVERITY_WEIGHTS[sev] * cnt for sev, cnt in counts.items())
    return max(0.0, 100.0 - penalty)


def composite_score(
    dimensions: dict[str, float],
    weights: dict[str, float] | None = None,
) -> float:
    """Compute the weighted composite score across quality dimensions.

    ``score = sum(dimension_value * weight)`` for all dimensions present
    in both *dimensions* and *weights*.  Weights default to
    ``DEFAULT_DIMENSION_WEIGHTS`` when not supplied.
    """
    if weights is None:
        weights = DEFAULT_DIMENSION_WEIGHTS
    total = 0.0
    for dim, weight in weights.items():
        total += dimensions.get(dim, 0.0) * weight
    return round(total, 4)


def score_acceptance_readiness(
    criteria_results: list[AcceptanceCriterionResult],
    profile: GateProfile,
) -> GateVerdict:
    """Score acceptance criteria quality and return a gate verdict.

    Evaluates criteria on five dimensions (Testability, Completeness,
    Measurability, Clarity, Independence), computes a weighted Acceptance
    Readiness Score (ARS), and compares against the profile threshold.
    """
    if not criteria_results:
        return GateVerdict(
            decision="FAIL",
            rationale="No acceptance criteria provided. Cannot assess readiness.",
            composite_score=0.0,
            meets_threshold=False,
            details={
                "failing_dimensions": list(ARS_DIMENSION_WEIGHTS),
                "suggestions": ["Define acceptance criteria before proceeding."],
            },
        )

    n = len(criteria_results)
    dim_avgs: dict[str, float] = {
        "testability": sum(c.testability for c in criteria_results) / n,
        "completeness": sum(c.completeness for c in criteria_results) / n,
        "measurability": sum(c.measurability for c in criteria_results) / n,
        "clarity": sum(c.clarity for c in criteria_results) / n,
        "independence": sum(c.independence for c in criteria_results) / n,
    }

    ars = round(
        sum(dim_avgs[d] * w for d, w in ARS_DIMENSION_WEIGHTS.items()),
        2,
    )

    threshold = profile.acceptance_readiness_threshold

    if ars >= threshold:
        return GateVerdict(
            decision="PASS",
            rationale=f"Acceptance Readiness Score {ars:.1f} >= threshold {threshold}.",
            composite_score=ars,
            meets_threshold=True,
            details={"dimension_scores": dim_avgs},
        )

    failing = {d: v for d, v in dim_avgs.items() if v < threshold}
    failing_dims = sorted(failing, key=lambda d: failing[d])
    suggestions = [
        f"{d}: {ARS_DIMENSION_SUGGESTIONS[d]} (scored {failing[d]:.1f})" for d in failing_dims
    ]

    return GateVerdict(
        decision="FAIL",
        rationale=(
            f"Acceptance Readiness Score {ars:.1f} below threshold {threshold}. "
            f"Failing dimensions: {', '.join(failing_dims)}."
        ),
        composite_score=ars,
        meets_threshold=False,
        details={
            "dimension_scores": dim_avgs,
            "failing_dimensions": failing_dims,
            "suggestions": suggestions,
        },
    )


def _count_severity(findings: list[Finding], severity: str) -> int:
    return sum(1 for f in findings if f.severity == severity)


def _resolve_gate_type(gate_type: str) -> str:
    """Map legacy gate type aliases to canonical names."""
    return GATE_TYPE_ALIASES.get(gate_type, gate_type)


def _evaluate_preflight(gate_input: GateInput, profile: GateProfile) -> GateVerdict:
    """Preflight gate: block if any finding belongs to an abort category."""
    abort_findings = [
        f for f in gate_input.review_findings if f.category in profile.abort_categories
    ]

    if abort_findings:
        categories = sorted({f.category for f in abort_findings})
        return GateVerdict(
            decision="FAIL",
            rationale=(
                f"Preflight blocked: abort-category findings detected: {', '.join(categories)}."
            ),
            composite_score=None,
            meets_threshold=False,
            escalation_context=(
                f"Abort categories found in preflight: {', '.join(categories)}. "
                "Immediate escalation required."
            ),
        )

    failures: list[str] = []
    if gate_input.build_status.status == "fail":
        failures.append("build")
    if gate_input.test_results.status == "fail":
        failures.append("test")
    if gate_input.lint_status.status == "fail":
        failures.append("lint")

    if failures:
        return GateVerdict(
            decision="FAIL",
            rationale=f"Preflight checks failed: {', '.join(failures)}.",
            composite_score=None,
            meets_threshold=False,
        )

    return GateVerdict(
        decision="PASS",
        rationale="All preflight checks passed.",
        composite_score=None,
        meets_threshold=True,
    )


def _evaluate_abort(gate_input: GateInput, profile: GateProfile) -> GateVerdict:
    """Abort gate: escalate if any finding belongs to an abort category."""
    abort_findings = [
        f for f in gate_input.review_findings if f.category in profile.abort_categories
    ]

    if abort_findings:
        categories = sorted({f.category for f in abort_findings})
        return GateVerdict(
            decision="ESCALATE",
            rationale=f"Abort triggered: findings in abort categories: {', '.join(categories)}.",
            composite_score=None,
            meets_threshold=False,
            post_mortem={
                "abort_categories_found": categories,
                "finding_count": len(abort_findings),
                "findings": [f.finding_id for f in abort_findings],
            },
        )

    return GateVerdict(
        decision="PASS",
        rationale="No abort-category findings detected.",
        composite_score=None,
        meets_threshold=True,
    )


def evaluate_gate(
    gate_input: GateInput,
    profile: GateProfile,
    round_num: int = 1,
    history: list[ConvergenceRound] | None = None,
    gate_type: str = "standard",
) -> GateVerdict:
    """Evaluate a gate according to the §5.7 flowchart.

    Parameters
    ----------
    gate_input:
        Aggregated check results for this round.
    profile:
        The active gate profile (strict/standard/relaxed/audit).
    round_num:
        Current convergence round (1-based).
    history:
        Prior convergence rounds (empty list or ``None`` for first round).
    gate_type:
        One of ``"standard"``, ``"convergence"``, ``"passthrough"``,
        ``"acceptance_readiness"``, ``"preflight"``, ``"revision"``,
        ``"escalation"``, ``"abort"``.
    """
    if history is None:
        history = []

    resolved = _resolve_gate_type(gate_type)

    if resolved == "passthrough":
        verdict = GateVerdict(
            decision="PASS",
            rationale="Passthrough gate — forwarding stage results.",
            composite_score=None,
            meets_threshold=True,
        )
    elif resolved == "acceptance_readiness":
        verdict = score_acceptance_readiness(
            gate_input.acceptance_readiness_criteria,
            profile,
        )
    elif resolved == "preflight":
        verdict = _evaluate_preflight(gate_input, profile)
    elif resolved == "abort":
        verdict = _evaluate_abort(gate_input, profile)
    elif resolved == "escalation":
        verdict = _evaluate_standard(gate_input, profile)
        if verdict.decision == "FAIL":
            verdict.escalation_context = f"Escalation gate failed. {verdict.rationale}"
    elif history:
        verdict = _evaluate_convergence(gate_input, profile, round_num, history)
    else:
        verdict = _evaluate_standard(gate_input, profile)

    # Borderline detection for advisor tool
    if profile.advisor_margin > 0 and verdict.composite_score is not None:
        margin = abs(verdict.composite_score - profile.composite_threshold)
        if margin <= profile.advisor_margin:
            verdict.advisor_recommended = True
            verdict.advisor_context = (
                f"Score {verdict.composite_score:.1f} is within "
                f"±{profile.advisor_margin} of threshold "
                f"{profile.composite_threshold}. Human review recommended."
            )

    return verdict


def _evaluate_standard(gate_input: GateInput, profile: GateProfile) -> GateVerdict:
    """Single-shot gate: all checks must pass."""
    failures: list[str] = []

    if gate_input.build_status.status == "fail":
        failures.append("build")
    if gate_input.test_results.status == "fail":
        failures.append("test")
    if gate_input.lint_status.status == "fail":
        failures.append("lint")

    blocker_count = _count_severity(gate_input.review_findings, "blocker")
    if blocker_count > profile.max_blocker:
        failures.append(f"blockers({blocker_count})")

    critical_count = _count_severity(gate_input.review_findings, "critical")
    if critical_count > profile.max_critical:
        failures.append(f"criticals({critical_count})")

    ac = gate_input.acceptance_criteria_results
    if ac and ac.status == "fail":
        failures.append("acceptance_criteria")

    if not failures:
        return GateVerdict(
            decision="PASS",
            rationale="All standard gate checks passed.",
            composite_score=None,
            meets_threshold=True,
        )

    return GateVerdict(
        decision="FAIL",
        rationale=f"Standard gate failed checks: {', '.join(failures)}.",
        composite_score=None,
        meets_threshold=False,
    )


def _evaluate_convergence(
    gate_input: GateInput,
    profile: GateProfile,
    round_num: int,
    history: list[ConvergenceRound],
) -> GateVerdict:
    """Multi-round convergence gate (§5.7 flowchart)."""
    q_score = quality_score(gate_input.review_findings)

    dims: dict[str, float] = {}
    test_detail = gate_input.test_results.details
    if "coverage_pct" in test_detail:
        dims["test_quality"] = float(test_detail["coverage_pct"])
    elif "tests_passed" in test_detail and "tests_total" in test_detail:
        total = int(test_detail["tests_total"])
        passed = int(test_detail["tests_passed"])
        dims["test_quality"] = (passed / total * 100) if total else 100.0
    else:
        dims["test_quality"] = 100.0 if gate_input.test_results.status == "pass" else 0.0

    dims["code_review"] = q_score

    arch_score = gate_input.lint_status.details.get("architecture_score")
    dims["architecture"] = float(arch_score) if arch_score is not None else q_score

    bench_detail = gate_input.build_status.details.get("benchmark_score")
    dims["benchmark"] = float(bench_detail) if bench_detail is not None else 100.0

    score = composite_score(dims)

    blocker_count = _count_severity(gate_input.review_findings, "blocker")
    meets = (
        score >= profile.composite_threshold
        and round_num >= profile.min_rounds
        and blocker_count <= profile.max_blocker
    )

    if meets:
        return GateVerdict(
            decision="PASS",
            rationale=(
                f"Composite score {score:.1f} >= {profile.composite_threshold}, "
                f"round {round_num} >= min {profile.min_rounds}, "
                f"0 blockers."
            ),
            composite_score=score,
            meets_threshold=True,
        )

    if round_num >= profile.max_rounds:
        return GateVerdict(
            decision="ESCALATE",
            rationale=(
                f"Max rounds ({profile.max_rounds}) reached. "
                f"Composite score {score:.1f} vs threshold {profile.composite_threshold}."
            ),
            composite_score=score,
            meets_threshold=False,
        )

    if detect_stagnation(history):
        trend = compute_trend(history)
        if trend != "improving" and round_num > 2:
            return GateVerdict(
                decision="ESCALATE",
                rationale=(
                    f"Score stagnant for 2 rounds (trend={trend}). "
                    f"Composite {score:.1f} vs threshold {profile.composite_threshold}."
                ),
                composite_score=score,
                meets_threshold=False,
            )

    return GateVerdict(
        decision="FAIL",
        rationale=(
            f"Composite score {score:.1f} below threshold {profile.composite_threshold} "
            f"(round {round_num}/{profile.max_rounds}). Retry."
        ),
        composite_score=score,
        meets_threshold=False,
    )


def evaluate_gate_with_nines(
    gate_input: GateInput,
    profile: GateProfile,
    round_num: int = 1,
    history: list[ConvergenceRound] | None = None,
    gate_type: str = "standard",
    nines_config: object | None = None,
    advisor_config: object | None = None,
    artifact_path: str = "",
) -> GateVerdict:
    """Evaluate a gate with optional NineS-backed scoring and advisor.

    .. deprecated::
        NineS is a research/iteration tool, not a gate scorer.  Use
        :func:`evaluate_gate` for quality gates.  See
        ``devolaflow.nines.researcher`` for NineS research capabilities.

    Delegates to :func:`evaluate_gate` first, then — when NineS is
    installed and *nines_config* is provided — enriches the verdict with
    NineS dimension scores and advisor analysis.

    All NineS imports are lazy so the gate package has no hard dependency
    on the ``devolaflow.nines`` module.  When NineS is unavailable the
    original verdict is returned unchanged.

    Parameters
    ----------
    nines_config:
        A ``NinesScorerConfig`` instance (from ``devolaflow.nines.scorer``).
        ``None`` disables NineS scoring entirely.
    advisor_config:
        A ``NinesAdvisorConfig`` instance (from ``devolaflow.nines.advisor``).
        ``None`` disables advisor enrichment.
    artifact_path:
        Filesystem path forwarded to NineS CLI commands.
    """
    warnings.warn(
        "evaluate_gate_with_nines is deprecated. NineS is a research/iteration tool, "
        "not a gate scorer. Use the standard evaluate_gate() for quality gates. "
        "See devolaflow.nines.researcher for NineS research capabilities.",
        DeprecationWarning,
        stacklevel=2,
    )
    verdict = evaluate_gate(gate_input, profile, round_num, history, gate_type)

    if nines_config is None:
        return verdict

    try:
        from devolaflow.nines.detector import detect_nines
        from devolaflow.nines.scorer import nines_dimension_scores
    except ImportError:
        return verdict

    status = detect_nines()
    if not status.available:
        return verdict

    nines_scores = nines_dimension_scores(nines_config, artifact_path)

    if verdict.composite_score is not None:
        merged = composite_score(nines_scores)
        verdict.composite_score = merged
        verdict.meets_threshold = (
            merged >= profile.composite_threshold and round_num >= profile.min_rounds
        )
        verdict.details["nines_dimension_scores"] = nines_scores

    if verdict.advisor_recommended and advisor_config is not None:
        try:
            from devolaflow.nines.advisor import run_nines_advisor
        except ImportError:
            return verdict
        verdict = run_nines_advisor(verdict, advisor_config, artifact_path)

    return verdict


def run_gate_cli(args: Sequence[str]) -> None:
    """CLI entry point for gate validation."""
    print("gate: pass (stub)")
