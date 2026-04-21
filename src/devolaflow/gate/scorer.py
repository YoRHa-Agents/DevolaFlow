"""Gate composite scorer and quality scorer.

Design ref: design_decomposition_gate.md §5.3, §5.7
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import yaml

from devolaflow.gate.budget import TokenBudgetBreaker
from devolaflow.gate.convergence import (
    compute_smoothed_trend,
    compute_trend,
    detect_stagnation,
)
from devolaflow.gate.cycle_detector import CycleDetector
from devolaflow.gate.models import (
    GATE_TYPE_ALIASES,
    LADDER_RUNG_NAMES,
    LADDER_RUNG_ORDER,
    AcceptanceCriterionResult,
    BudgetAction,
    BudgetDecision,
    CheckResult,
    ConvergenceRound,
    CycleReport,
    Finding,
    GateInput,
    GateProfile,
    GateVerdict,
    LadderEvaluation,
    LadderRung,
    RatchetAction,
    Severity,
)
from devolaflow.gate.profiles import PROFILES, STANDARD
from devolaflow.gate.ratchet import (
    MonotonicRatchet,
    compute_deterministic_oracle_score,
)
from devolaflow.gate.reinforcement import (
    MAX_REINFORCEMENT_RULES,
    ReinforcementBlock,
    ReinforcementRule,
    cycle_to_instruction,
    fence_to_instruction,
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

EXTENDED_DIMENSION_WEIGHTS: dict[str, float] = {
    "test_quality": 0.20,
    "code_review": 0.20,
    "architecture": 0.15,
    "benchmark": 0.15,
    "visual_fidelity": 0.10,
    "interaction_quality": 0.10,
    "acceptance_verification": 0.10,
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


def visual_fidelity_score(results: CheckResult | None) -> float:
    """Compute visual fidelity score from screenshot test results."""
    if results is None or results.status == "skip":
        return 100.0
    if results.status == "fail":
        details = results.details
        total = int(details.get("screenshots_total", 1))
        passing = int(details.get("screenshots_passing", 0))
        return max(0.0, (passing / total) * 100) if total > 0 else 0.0
    return 100.0


def interaction_quality_score(
    interaction_results: CheckResult | None,
    accessibility_results: CheckResult | None,
) -> float:
    """Compute interaction quality from E2E flow results and accessibility scores."""
    e2e_score = 100.0
    if interaction_results is not None and interaction_results.status == "fail":
        details = interaction_results.details
        total = int(details.get("flows_total", 1))
        passing = int(details.get("flows_passing", 0))
        e2e_score = max(0.0, (passing / total) * 100) if total > 0 else 0.0

    a11y_score = 100.0
    if accessibility_results is not None and accessibility_results.status == "fail":
        details = accessibility_results.details
        critical = int(details.get("critical_violations", 0))
        serious = int(details.get("serious_violations", 0))
        moderate = int(details.get("moderate_violations", 0))
        minor_v = int(details.get("minor_violations", 0))
        a11y_score = max(0.0, 100.0 - (critical * 25 + serious * 15 + moderate * 5 + minor_v * 1))

    return round(e2e_score * 0.60 + a11y_score * 0.40, 2)


def acceptance_verification_score(results: CheckResult | None) -> float:
    """Compute acceptance verification score from AC test results."""
    if results is None or results.status == "skip":
        return 100.0
    if results.status == "fail":
        details = results.details
        total = int(details.get("criteria_total", 1))
        passing = int(details.get("criteria_passing", 0))
        return max(0.0, (passing / total) * 100) if total > 0 else 0.0
    return 100.0


def _has_user_facing_inputs(gate_input: GateInput) -> bool:
    """Check if gate input includes any user-facing verification results."""
    return any(
        [
            gate_input.visual_test_results is not None,
            gate_input.interaction_test_results is not None,
            gate_input.accessibility_results is not None,
            gate_input.acceptance_verification_results is not None,
        ]
    )


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
    """Count findings matching the given severity level."""
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


_PASSTHROUGH_VERDICT = GateVerdict(
    decision="PASS",
    rationale="Passthrough gate — forwarding stage results.",
    composite_score=None,
    meets_threshold=True,
)


def _evaluate_escalation(gate_input: GateInput, profile: GateProfile) -> GateVerdict:
    verdict = _evaluate_standard(gate_input, profile)
    if verdict.decision == "FAIL":
        verdict.escalation_context = f"Escalation gate failed. {verdict.rationale}"
    return verdict


_GATE_DISPATCH: dict[str, object] = {
    "passthrough": lambda gi, p: _PASSTHROUGH_VERDICT,
    "acceptance_readiness": lambda gi, p: score_acceptance_readiness(
        gi.acceptance_readiness_criteria, p
    ),
    "preflight": _evaluate_preflight,
    "abort": _evaluate_abort,
    "escalation": _evaluate_escalation,
}


def _apply_advisor_detection(verdict: GateVerdict, profile: GateProfile) -> None:
    if profile.advisor_margin <= 0 or verdict.composite_score is None:
        return
    margin = abs(verdict.composite_score - profile.composite_threshold)
    if margin <= profile.advisor_margin:
        verdict.advisor_recommended = True
        verdict.advisor_context = (
            f"Score {verdict.composite_score:.1f} is within "
            f"±{profile.advisor_margin} of threshold "
            f"{profile.composite_threshold}. Human review recommended."
        )


def _build_budget_break_verdict(decision: BudgetDecision) -> GateVerdict:
    """Render a :class:`GateVerdict` from a ``BREAK`` :class:`BudgetDecision`.

    The decision shape is fully embedded in ``details`` for downstream
    consumers (Project / Stage agents) to surface in StatusReport and
    reinforcement injection. ESCALATE on STRICT/AUDIT, FAIL on
    STANDARD/RELAXED — see ``patch_plan §3 P-03 AC #6``.
    """
    rec = decision.recommendation
    is_escalate = rec.value == "ESCALATE"
    return GateVerdict(
        decision="ESCALATE" if is_escalate else "FAIL",
        rationale=(f"Token-budget circuit broken: {decision.rationale} recommendation={rec.value}"),
        composite_score=None,
        meets_threshold=False,
        escalation_context=(
            f"Token budget exhausted: {decision.cumulative_tokens}/"
            f"{decision.max_tokens} tokens "
            f"({decision.utilization * 100:.1f}%). "
            f"Profile recommendation: {rec.value}."
        )
        if is_escalate
        else "",
        details={
            "budget_break": True,
            "budget_action": decision.action.value,
            "budget_recommendation": rec.value,
            "cumulative_tokens": decision.cumulative_tokens,
            "max_tokens": decision.max_tokens,
            "utilization": decision.utilization,
        },
    )


def _attach_budget_warning(verdict: GateVerdict, decision: BudgetDecision) -> GateVerdict:
    """Attach a non-fatal WARN ``BudgetDecision`` to an existing verdict.

    Mutates ``verdict.details`` in place to surface utilization metrics
    without changing the underlying decision (PASS / FAIL / ESCALATE).
    """
    verdict.details.setdefault("budget_warning", True)
    verdict.details.setdefault("budget_action", decision.action.value)
    verdict.details.setdefault("budget_recommendation", decision.recommendation.value)
    verdict.details.setdefault("cumulative_tokens", decision.cumulative_tokens)
    verdict.details.setdefault("max_tokens", decision.max_tokens)
    verdict.details.setdefault("utilization", decision.utilization)
    return verdict


def _resolve_breaker_decision(
    breaker: TokenBudgetBreaker,
    cumulative_tokens: int | None,
) -> BudgetDecision:
    """Choose between an explicit cumulative count and the breaker's state.

    When ``cumulative_tokens`` is ``None`` the breaker's internal
    ``cumulative_tokens`` (populated via :meth:`record`) is used; otherwise
    the explicit value wins. This lets callers either drive the breaker
    statefully across rounds or keep it pure per-round.
    """
    if cumulative_tokens is None:
        return breaker.check_recorded()
    return breaker.check(cumulative_tokens)


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-04) — Deterministic Fence Expansion integration
#
# ``_evaluate_checks`` inspects the fence-style check results in a
# :class:`GateInput` (build / test / lint, plus optional caller-supplied
# extras like ``format`` / ``typecheck``) and converts each ``status='fail'``
# into a deterministic :class:`ReinforcementRule` via
# :func:`devolaflow.gate.reinforcement.fence_to_instruction`. The helper
# returns ``None`` whenever no checks are declared OR all declared checks
# pass, preserving byte-identical pre-P-04 behaviour for callers that do
# not opt in (per ``patch_plan §3 P-04``).
# ─────────────────────────────────────────────────────────────────────────────


# Built-in fence checks pulled from :class:`GateInput`. The order is
# semantic — build failures gate everything else, so they win the first
# rule slot when MAX_REINFORCEMENT_RULES truncation kicks in.
_BUILTIN_FENCE_ATTRS: tuple[tuple[str, str], ...] = (
    ("build", "build_status"),
    ("test", "test_results"),
    ("lint", "lint_status"),
)


def _payload_from_check(check: CheckResult, file_hint: str = "") -> dict[str, str]:
    """Render a fence payload from a failing :class:`CheckResult`.

    Looks for the conventional ``file`` / ``line`` / ``msg`` keys in
    ``check.details``, falling back to ``message`` then a short status
    summary so every fence rule has a non-empty mandate (S-5 — never
    silently emit an empty MUST-fix). The optional ``file_hint`` lets
    callers seed a default file path when the check itself doesn't
    carry one (e.g. global lint runs).
    """
    details = check.details or {}
    file_value = str(details.get("file") or file_hint or "")
    line_value = "" if details.get("line") is None else str(details.get("line"))
    msg_value = str(
        details.get("msg")
        or details.get("message")
        or details.get("error")
        or f"check status={check.status}"
    )
    return {"file": file_value, "line": line_value, "msg": msg_value}


def _collect_fence_failures(
    gate_input: GateInput,
    extra_checks: dict[str, CheckResult] | None,
) -> list[tuple[str, dict[str, str]]]:
    """Gather ``(fence_type, payload)`` pairs for every failing check.

    Built-in checks (build / test / lint) are inspected first, then any
    caller-supplied extras (e.g. ``format`` / ``typecheck``). Order is
    deterministic so the resulting :class:`ReinforcementRule` ids are
    stable across runs.
    """
    failures: list[tuple[str, dict[str, str]]] = []
    for fence_type, attr in _BUILTIN_FENCE_ATTRS:
        check = getattr(gate_input, attr)
        if check.status == "fail":
            failures.append((fence_type, _payload_from_check(check)))
    if extra_checks:
        for fence_type, check in extra_checks.items():
            if check.status == "fail":
                failures.append((fence_type, _payload_from_check(check)))
    return failures


def _evaluate_checks(
    gate_input: GateInput,
    *,
    round_num: int = 2,
    prior_score: float = 0.0,
    target_score: float = 85.0,
    severity_floor: Severity = "major",
    extra_checks: dict[str, CheckResult] | None = None,
    max_tokens_per_rule: int = 200,
) -> ReinforcementBlock | None:
    """Convert failing fence checks into a :class:`ReinforcementBlock`.

    Inspects ``gate_input.build_status`` / ``test_results`` / ``lint_status``
    plus any caller-supplied ``extra_checks`` mapping (e.g.
    ``{"format": CheckResult(...), "typecheck": CheckResult(...)}``).
    Each ``status == 'fail'`` entry becomes a deterministic
    ``F-{fence_type}-{seq:03d}`` rule via
    :func:`devolaflow.gate.reinforcement.fence_to_instruction`.

    Returns ``None`` when no failures are detected (byte-identical
    pre-P-04 behaviour per ``patch_plan §3 P-04``). The rule list is
    capped at :data:`MAX_REINFORCEMENT_RULES` to honour W-8 / SI-9
    (≤ 5 reinforcement rules per round).
    """
    failures = _collect_fence_failures(gate_input, extra_checks)
    if not failures:
        return None

    rules: list[ReinforcementRule] = []
    type_counters: dict[str, int] = {}
    for fence_type, payload in failures[:MAX_REINFORCEMENT_RULES]:
        type_counters[fence_type] = type_counters.get(fence_type, 0) + 1
        rules.append(
            fence_to_instruction(
                fence_type,
                payload,
                sequence=type_counters[fence_type],
                max_tokens=max_tokens_per_rule,
            )
        )

    failure_types = [t for t, _ in failures]
    escalation = (
        f"Round {round_num - 1} fence checks failed: {failure_types}. "
        f"{len(rules)} fence-derived rule(s) injected for round {round_num} "
        f"(target_score={target_score:.1f})."
    )

    return ReinforcementBlock(
        round=round_num,
        prior_score=prior_score,
        target_score=target_score,
        severity_floor=severity_floor,
        rules=tuple(rules),
        escalation_note=escalation,
    )


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-05) — Verification Ladder Formalization
#
# ``evaluate_ladder`` formalizes a 6-rung short-circuit ladder R1..R6 over
# the existing :class:`GateInput` surface. Earlier rungs are intentionally
# cheaper (``lint`` < ``typecheck`` < ``unit_test`` < ``integration_test``
# < ``benchmark`` < ``convergence``) so a failing rung aborts the rest of
# the ladder before LLM / review cycles spend tokens (Karpathy "fail fast
# on cheap signals" per upstream tweet analysis ``v7.8`` §4.10).
#
# Two opt-in mechanisms:
#
# 1. ``profile.ladder_enabled`` flag (defaults False on STANDARD/RELAXED,
#    True on STRICT/AUDIT — see ``profiles.py``). When False, the ladder
#    delegates to :func:`evaluate_gate` unchanged → byte-identical
#    pre-P-05 behaviour (``patch_plan §3 P-05 AC #3``).
# 2. ``rung_overrides`` parameter — a mapping of
#    ``LadderRung → Callable[..., LadderEvaluation | CheckResult]`` for
#    test mocks and custom checkers. Built-in rungs are used when no
#    override is supplied.
# ─────────────────────────────────────────────────────────────────────────────


# Rung-checker callables receive (gate_input, profile) plus the same
# ``round_num`` / ``history`` / ``gate_type`` / ``breaker`` /
# ``cumulative_tokens`` / ``extra_checks`` keyword args as
# :func:`evaluate_gate`. They MUST return either a :class:`LadderEvaluation`
# (preferred — full control over message / details) OR a plain
# :class:`CheckResult` which is then wrapped via :func:`_wrap_check_result`.
RungChecker = Callable[..., "LadderEvaluation | CheckResult"]


def _wrap_check_result(rung: LadderRung, result: CheckResult) -> LadderEvaluation:
    """Convert a plain :class:`CheckResult` into a :class:`LadderEvaluation`.

    Used when a caller-supplied :class:`RungChecker` returns a bare
    :class:`CheckResult` instead of the richer :class:`LadderEvaluation`.
    The status enum is normalised (``pass``/``fail``/``skip``) and the
    rung name is auto-filled by :class:`LadderEvaluation.__post_init__`.
    """
    rung_name = LADDER_RUNG_NAMES[rung]
    message = (
        str(result.details.get("message"))
        if result.details and "message" in result.details
        else f"{rung_name} {result.status}"
    )
    return LadderEvaluation(
        rung=rung,
        status=result.status,
        message=message,
        details=dict(result.details or {}),
    )


def _ladder_skip(rung: LadderRung, reason: str) -> LadderEvaluation:
    """Build a ``skip`` :class:`LadderEvaluation` carrying ``reason``."""
    return LadderEvaluation(
        rung=rung,
        status="skip",
        message=reason,
    )


def _check_lint(gate_input: GateInput, profile: GateProfile, **_: object) -> LadderEvaluation:
    """R1 default checker — inspect ``gate_input.lint_status``."""
    check = gate_input.lint_status
    if check.status == "skip":
        return _ladder_skip(LadderRung.R1, "lint check skipped (status=skip)")
    if check.status == "fail":
        return LadderEvaluation(
            rung=LadderRung.R1,
            status="fail",
            message=f"lint failed: {check.details or {}}",
            details=dict(check.details or {}),
        )
    return LadderEvaluation(
        rung=LadderRung.R1,
        status="pass",
        message="lint passed",
        details=dict(check.details or {}),
    )


def _check_typecheck(
    gate_input: GateInput,
    profile: GateProfile,
    *,
    extra_checks: Mapping[str, CheckResult] | None = None,
    **_: object,
) -> LadderEvaluation:
    """R2 default checker — read ``extra_checks['typecheck']`` or skip.

    Typechecking is not part of the canonical :class:`GateInput` surface;
    callers opt in by supplying ``extra_checks={'typecheck': CheckResult(...)}``.
    """
    check = (extra_checks or {}).get("typecheck")
    if check is None:
        return _ladder_skip(LadderRung.R2, "typecheck not provided")
    if check.status == "skip":
        return _ladder_skip(LadderRung.R2, "typecheck skipped (status=skip)")
    if check.status == "fail":
        return LadderEvaluation(
            rung=LadderRung.R2,
            status="fail",
            message=f"typecheck failed: {check.details or {}}",
            details=dict(check.details or {}),
        )
    return LadderEvaluation(
        rung=LadderRung.R2,
        status="pass",
        message="typecheck passed",
        details=dict(check.details or {}),
    )


def _check_unit_test(gate_input: GateInput, profile: GateProfile, **_: object) -> LadderEvaluation:
    """R3 default checker — inspect ``gate_input.test_results``."""
    check = gate_input.test_results
    if check.status == "skip":
        return _ladder_skip(LadderRung.R3, "unit tests skipped (status=skip)")
    if check.status == "fail":
        return LadderEvaluation(
            rung=LadderRung.R3,
            status="fail",
            message=f"unit tests failed: {check.details or {}}",
            details=dict(check.details or {}),
        )
    return LadderEvaluation(
        rung=LadderRung.R3,
        status="pass",
        message="unit tests passed",
        details=dict(check.details or {}),
    )


def _check_integration(
    gate_input: GateInput,
    profile: GateProfile,
    *,
    extra_checks: Mapping[str, CheckResult] | None = None,
    **_: object,
) -> LadderEvaluation:
    """R4 default checker — ``extra_checks['integration_test']`` or
    fall back to ``gate_input.acceptance_criteria_results``.
    """
    check = (extra_checks or {}).get("integration_test")
    if check is None:
        check = gate_input.acceptance_criteria_results
    if check is None:
        return _ladder_skip(LadderRung.R4, "integration test not provided")
    if check.status == "skip":
        return _ladder_skip(LadderRung.R4, "integration test skipped (status=skip)")
    if check.status == "fail":
        return LadderEvaluation(
            rung=LadderRung.R4,
            status="fail",
            message=f"integration test failed: {check.details or {}}",
            details=dict(check.details or {}),
        )
    return LadderEvaluation(
        rung=LadderRung.R4,
        status="pass",
        message="integration test passed",
        details=dict(check.details or {}),
    )


def _check_benchmark(
    gate_input: GateInput,
    profile: GateProfile,
    *,
    extra_checks: Mapping[str, CheckResult] | None = None,
    **_: object,
) -> LadderEvaluation:
    """R5 default checker — explicit ``extra_checks['benchmark']`` first,
    otherwise read ``build_status.details['benchmark_score']``.

    When no benchmark signal is supplied at all the rung is a ``skip``
    (S-5 — never silently treat absence as success).
    """
    check = (extra_checks or {}).get("benchmark")
    if check is not None:
        if check.status == "skip":
            return _ladder_skip(LadderRung.R5, "benchmark skipped (status=skip)")
        if check.status == "fail":
            return LadderEvaluation(
                rung=LadderRung.R5,
                status="fail",
                message=f"benchmark failed: {check.details or {}}",
                details=dict(check.details or {}),
            )
        return LadderEvaluation(
            rung=LadderRung.R5,
            status="pass",
            message="benchmark passed",
            details=dict(check.details or {}),
        )

    bench_score = gate_input.build_status.details.get("benchmark_score")
    if bench_score is None:
        return _ladder_skip(LadderRung.R5, "benchmark score not provided")
    score = float(bench_score)
    threshold = float(profile.composite_threshold)
    if score < threshold:
        return LadderEvaluation(
            rung=LadderRung.R5,
            status="fail",
            message=(f"benchmark score {score:.1f} below threshold {threshold:.1f}"),
            details={"benchmark_score": score, "threshold": threshold},
        )
    return LadderEvaluation(
        rung=LadderRung.R5,
        status="pass",
        message=(f"benchmark score {score:.1f} >= threshold {threshold:.1f}"),
        details={"benchmark_score": score, "threshold": threshold},
    )


def _check_convergence(
    gate_input: GateInput,
    profile: GateProfile,
    *,
    round_num: int = 1,
    history: list[ConvergenceRound] | None = None,
    gate_type: str = "standard",
    breaker: TokenBudgetBreaker | None = None,
    cumulative_tokens: int | None = None,
    ratchet: MonotonicRatchet | None = None,
    ratchet_artifact: dict[str, object] | None = None,
    **_: object,
) -> LadderEvaluation:
    """R6 default checker — delegate to :func:`evaluate_gate` and translate
    its :class:`GateVerdict` into a :class:`LadderEvaluation`.

    The full verdict is preserved in ``details['verdict']`` so callers can
    still recover composite_score, escalation_context, etc.
    """
    verdict = evaluate_gate(
        gate_input,
        profile,
        round_num=round_num,
        history=history,
        gate_type=gate_type,
        breaker=breaker,
        cumulative_tokens=cumulative_tokens,
        ratchet=ratchet,
        ratchet_artifact=ratchet_artifact,
    )
    status = "pass" if verdict.decision == "PASS" else "fail"
    return LadderEvaluation(
        rung=LadderRung.R6,
        status=status,
        message=f"convergence: {verdict.decision} — {verdict.rationale}",
        details={
            "verdict_decision": verdict.decision,
            "composite_score": verdict.composite_score,
            "meets_threshold": verdict.meets_threshold,
            "escalation_context": verdict.escalation_context,
        },
    )


_DEFAULT_RUNG_CHECKERS: dict[LadderRung, RungChecker] = {
    LadderRung.R1: _check_lint,
    LadderRung.R2: _check_typecheck,
    LadderRung.R3: _check_unit_test,
    LadderRung.R4: _check_integration,
    LadderRung.R5: _check_benchmark,
    LadderRung.R6: _check_convergence,
}


def _resolve_rung_checker(
    rung: LadderRung,
    overrides: Mapping[LadderRung, RungChecker] | None,
) -> RungChecker:
    """Pick the override for ``rung`` if present, else the built-in default."""
    if overrides is not None and rung in overrides:
        return overrides[rung]
    return _DEFAULT_RUNG_CHECKERS[rung]


def _normalise_rung_result(
    rung: LadderRung,
    result: LadderEvaluation | CheckResult,
) -> LadderEvaluation:
    """Coerce a :class:`RungChecker` return value into :class:`LadderEvaluation`.

    Accepts either the rich :class:`LadderEvaluation` (preferred) or a
    plain :class:`CheckResult` for terse mocks (S-5 — every rung MUST
    surface a status, message, and rung tag).
    """
    if isinstance(result, LadderEvaluation):
        if result.rung is not rung:
            raise ValueError(
                f"rung_overrides[{rung.value}] returned LadderEvaluation for "
                f"rung {result.rung.value}; rung tag must match the slot"
            )
        return result
    if isinstance(result, CheckResult):
        return _wrap_check_result(rung, result)
    raise TypeError(
        f"rung_overrides[{rung.value}] must return LadderEvaluation or CheckResult "
        f"(got {type(result).__name__})"
    )


def _build_ladder_verdict(
    results: list[LadderEvaluation],
    profile: GateProfile,
) -> GateVerdict:
    """Aggregate per-rung evaluations into a single :class:`GateVerdict`.

    Decision rules (per ``patch_plan §3 P-05 AC #1/#5``):

    - any ``fail`` → ``decision='FAIL'``;
    - all ``pass``/``skip`` and R6 ran → ``decision='PASS'`` with
      composite_score copied from R6's verdict details.
    - ``ESCALATE`` decisions on R6 propagate as ``decision='ESCALATE'``
      (S-5 — never silently downgrade an escalation).
    """
    failing = [r for r in results if r.status == "fail"]

    r6 = next((r for r in results if r.rung is LadderRung.R6), None)
    r6_verdict_decision: str | None = None
    composite: float | None = None
    escalation_context = ""
    if r6 is not None:
        r6_verdict_decision = str(r6.details.get("verdict_decision")) if r6.details else None
        raw_score = r6.details.get("composite_score") if r6.details else None
        composite = float(raw_score) if raw_score is not None else None
        escalation_context = str(r6.details.get("escalation_context") or "")

    if r6_verdict_decision == "ESCALATE":
        decision = "ESCALATE"
    elif failing:
        decision = "FAIL"
    else:
        decision = "PASS"

    summary = ", ".join(f"{r.rung.value}={r.status}" for r in results)
    if decision == "PASS":
        rationale = f"Verification ladder PASS — {summary}."
    elif decision == "ESCALATE":
        rationale = (
            f"Verification ladder ESCALATE — {summary}; R6 convergence requested escalation."
        )
    else:
        first_fail = failing[0]
        rationale = (
            f"Verification ladder FAIL — {summary}; first failure at "
            f"{first_fail.rung.value} ({first_fail.name}): {first_fail.message}"
        )

    details: dict[str, object] = {
        "ladder": [
            {
                "rung": r.rung.value,
                "name": r.name,
                "status": r.status,
                "message": r.message,
                "details": dict(r.details),
            }
            for r in results
        ],
        "ladder_enabled": True,
        "ladder_short_circuit": bool(failing),
        "first_failing_rung": failing[0].rung.value if failing else None,
        "ladder_profile": profile.name,
    }

    verdict = GateVerdict(
        decision=decision,  # type: ignore[arg-type]
        rationale=rationale,
        composite_score=composite,
        meets_threshold=(decision == "PASS"),
        details=details,
        escalation_context=escalation_context if decision == "ESCALATE" else "",
    )
    return verdict


def evaluate_ladder(
    gate_input: GateInput,
    profile: GateProfile,
    *,
    round_num: int = 1,
    history: list[ConvergenceRound] | None = None,
    gate_type: str = "standard",
    breaker: TokenBudgetBreaker | None = None,
    cumulative_tokens: int | None = None,
    extra_checks: Mapping[str, CheckResult] | None = None,
    rung_overrides: Mapping[LadderRung, RungChecker] | None = None,
    cycle_detector: CycleDetector | None = None,
    ratchet: MonotonicRatchet | None = None,
    ratchet_artifact: dict[str, object] | None = None,
) -> GateVerdict:
    """Evaluate a 6-rung verification ladder R1..R6 with short-circuit semantics.

    Per ``patch_plan §3 P-05``:

    - When ``profile.ladder_enabled is False`` (default for STANDARD /
      RELAXED), this delegates to :func:`evaluate_gate` and returns its
      verdict unchanged (AC #3 — byte-identical pre-P-05 behaviour).
    - When ``profile.ladder_enabled is True`` (default for STRICT /
      AUDIT), rungs run in canonical order R1 → R6 (per
      :data:`devolaflow.gate.models.LADDER_RUNG_ORDER`). The first
      ``fail`` short-circuits later rungs to ``skip`` (AC #1) — the
      ``rung_overrides`` callable for those rungs is **not invoked**
      (AC #2, verified by mock-based tests).

    Parameters
    ----------
    gate_input, profile, round_num, history, gate_type, breaker,
    cumulative_tokens:
        Same semantics as :func:`evaluate_gate`. ``round_num`` /
        ``history`` / ``gate_type`` / ``breaker`` / ``cumulative_tokens``
        are forwarded to the R6 convergence checker (default behaviour).
    extra_checks:
        Optional ``{name: CheckResult}`` mapping consulted by the
        built-in R2 (``typecheck``), R4 (``integration_test``), and R5
        (``benchmark``) rung checkers.
    rung_overrides:
        Optional ``{LadderRung: RungChecker}`` mapping. When a rung is
        present, the override callable is used in place of the built-in.
        Each override may return either a :class:`LadderEvaluation` or a
        :class:`CheckResult`. Used primarily for test mocks; production
        callers should rely on the built-in rungs and ``extra_checks``.

    Returns
    -------
    GateVerdict
        ``decision='PASS'`` when no rung failed; ``'FAIL'`` on any rung
        failure; ``'ESCALATE'`` when R6 propagated an ESCALATE verdict.
        ``details['ladder']`` carries one entry per rung with rung tag,
        name, status, message, and per-rung details.
    """
    if not profile.ladder_enabled:
        return evaluate_gate(
            gate_input,
            profile,
            round_num=round_num,
            history=history,
            gate_type=gate_type,
            breaker=breaker,
            cumulative_tokens=cumulative_tokens,
            cycle_detector=cycle_detector,
            ratchet=ratchet,
            ratchet_artifact=ratchet_artifact,
        )

    results: list[LadderEvaluation] = []
    short_circuited = False
    failing_rung: LadderRung | None = None

    for rung in LADDER_RUNG_ORDER:
        if short_circuited:
            assert failing_rung is not None  # narrowed by short_circuited
            results.append(
                _ladder_skip(
                    rung,
                    f"short-circuited by failing rung {failing_rung.value} "
                    f"({LADDER_RUNG_NAMES[failing_rung]})",
                )
            )
            continue

        checker = _resolve_rung_checker(rung, rung_overrides)
        raw = checker(
            gate_input,
            profile,
            round_num=round_num,
            history=history,
            gate_type=gate_type,
            breaker=breaker,
            cumulative_tokens=cumulative_tokens,
            extra_checks=extra_checks,
            ratchet=ratchet,
            ratchet_artifact=ratchet_artifact,
        )
        evaluation = _normalise_rung_result(rung, raw)
        results.append(evaluation)
        if evaluation.status == "fail":
            short_circuited = True
            failing_rung = rung

    verdict = _build_ladder_verdict(results, profile)
    if cycle_detector is not None:
        cycle_report = cycle_detector.detect_cycle()
        if cycle_report.detected:
            _attach_cycle_report(verdict, cycle_report)
    return verdict


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-07) — Monotonic Ratchet integration
#
# ``_attach_ratchet_action`` consults the optional :class:`MonotonicRatchet`,
# computes the deterministic oracle score from the same :class:`GateInput`
# the gate verdict was built from, records the round, and surfaces the
# resulting :class:`RatchetAction` in ``verdict.details``. ``ratchet=None``
# is byte-identical to pre-P-07 behaviour (per ``patch_plan §3 P-07
# AC #4`` — ratchet=None scorer round-trip equals v7.8.0).
# ─────────────────────────────────────────────────────────────────────────────


def _attach_ratchet_action(
    verdict: GateVerdict,
    gate_input: GateInput,
    ratchet: MonotonicRatchet,
    round_num: int,
    artifact: dict[str, object] | None = None,
) -> GateVerdict:
    """Record this round on the ratchet and surface the verdict on ``details``.

    The oracle score is computed via
    :func:`devolaflow.gate.ratchet.compute_deterministic_oracle_score`
    (test + lint + build only — review_findings excluded per the S/O/R
    non-gameable principle, ``patch_plan §3 P-07 AC #5``). The action
    plus the new best-score / best-round metadata are appended to
    ``verdict.details['ratchet']`` in place; the verdict's ``decision``
    is NOT mutated by default (consumers translate ``ROLLBACK`` /
    ``ESCALATE`` into the appropriate convergence response).

    However, when the ratchet emits ``ESCALATE`` AND the underlying
    verdict is currently ``PASS`` / ``FAIL``, we upgrade the decision to
    ``ESCALATE`` because the loop is provably stuck (S-5 — never
    silently swallow an ESCALATE signal). ``ROLLBACK`` is surfaced via
    ``verdict.details`` only — the convergence orchestrator decides
    whether to restore the snapshot and re-dispatch the round.
    """
    oracle_score = compute_deterministic_oracle_score(gate_input)
    action = ratchet.record_round(round_num, oracle_score, artifact=artifact)
    snapshot_meta: dict[str, object] = {}
    if ratchet.best_artifact_snapshot is not None:
        snap = ratchet.best_artifact_snapshot
        snapshot_meta = {
            "round_num": snap.round_num,
            "score": snap.score,
            "payload_hash": snap.payload_hash,
        }
    verdict.details.setdefault("ratchet", {})
    verdict.details["ratchet"] = {
        "action": action.value,
        "oracle_score": oracle_score,
        "best_score": ratchet.best_score,
        "best_round": ratchet.best_round,
        "consecutive_regressions": ratchet.consecutive_regressions,
        "regression_tolerance": ratchet.regression_tolerance,
        "max_regressions": ratchet.max_regressions,
        "best_artifact_snapshot": snapshot_meta,
    }
    if action is RatchetAction.ESCALATE and verdict.decision != "ESCALATE":
        verdict.decision = "ESCALATE"
        verdict.meets_threshold = False
        verdict.escalation_context = verdict.escalation_context or (
            f"Ratchet escalation: post-rollback round {round_num} "
            f"oracle_score={oracle_score:.2f} cannot exceed best="
            f"{ratchet.best_score:.2f} (round {ratchet.best_round})."
        )
    return verdict


def _attach_cycle_report(verdict: GateVerdict, report: CycleReport) -> GateVerdict:
    """Attach a detected :class:`CycleReport` to ``verdict.details``.

    Mutates ``verdict.details`` in place to surface the cycle metadata
    without changing the underlying decision (per ``patch_plan §3 P-06
    AC #6`` — ``cycle_detector=None`` is byte-identical, supplying one
    must never silently change a PASS into a FAIL). The companion
    ``MUST NOT repeat`` :class:`ReinforcementRule` is pre-computed via
    :func:`devolaflow.gate.reinforcement.cycle_to_instruction` and
    embedded under ``cycle_details.suggested_rule`` so L2 Wave agents
    can inject it into the next round's dispatch verbatim.
    """
    suggested = cycle_to_instruction(report)
    verdict.details.setdefault("cycle_detected", True)
    verdict.details.setdefault(
        "cycle_details",
        {
            "cycle_type": report.cycle_type,
            "severity": report.severity,
            "similarity": report.similarity,
            "rationale": report.rationale,
            "evidence": list(report.evidence),
            "repeated_signatures": list(report.repeated_signatures),
            "rounds": list(report.rounds),
            "files": list(report.files),
            "window_size": report.window_size,
            "threshold": report.threshold,
            "suggested_rule": {
                "id": suggested.id,
                "severity": suggested.severity,
                "mandate": suggested.mandate,
                "file": suggested.file,
            },
        },
    )
    return verdict


def evaluate_gate(
    gate_input: GateInput,
    profile: GateProfile,
    round_num: int = 1,
    history: list[ConvergenceRound] | None = None,
    gate_type: str = "standard",
    breaker: TokenBudgetBreaker | None = None,
    cumulative_tokens: int | None = None,
    cycle_detector: CycleDetector | None = None,
    ratchet: MonotonicRatchet | None = None,
    ratchet_artifact: dict[str, object] | None = None,
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
    breaker:
        Optional :class:`devolaflow.gate.budget.TokenBudgetBreaker`. When
        ``None`` (the default), behaviour is byte-identical to v7.8.0 —
        no token-budget evaluation is performed (per ``patch_plan §3 P-03
        AC #2``). When supplied, the breaker is checked first; a
        ``BREAK`` decision returns early with FAIL or ESCALATE depending
        on the profile severity (STRICT / AUDIT escalate).
    cumulative_tokens:
        Optional explicit cumulative-token count for the breaker check.
        When ``None``, the breaker's internal counter (from
        :meth:`TokenBudgetBreaker.record`) is used. Ignored when
        ``breaker is None``.
    cycle_detector:
        Optional :class:`devolaflow.gate.cycle_detector.CycleDetector`.
        When ``None`` (the default), behaviour is byte-identical to
        pre-P-06 — no cycle inspection (``patch_plan §3 P-06 AC #6``).
        When supplied, the detector is consulted *after* the standard
        verdict is computed; a detected cycle is appended to
        ``verdict.details`` as ``cycle_detected=True`` plus a structured
        ``cycle_details`` mapping. The verdict's ``decision`` is NOT
        mutated — callers translate the report into a reinforcement rule
        via :func:`devolaflow.gate.reinforcement.cycle_to_instruction`
        and decide how to escalate.
    ratchet:
        Optional :class:`devolaflow.gate.ratchet.MonotonicRatchet`. When
        ``None`` (the default), behaviour is byte-identical to pre-P-07
        (``patch_plan §3 P-07 AC #4``). When supplied, the deterministic
        oracle subset (test + lint + build, review_findings EXCLUDED) is
        computed via
        :func:`devolaflow.gate.ratchet.compute_deterministic_oracle_score`
        and recorded on the ratchet, surfacing the resulting
        :class:`RatchetAction` in ``verdict.details['ratchet']``. The
        verdict's ``decision`` is upgraded to ``ESCALATE`` only when the
        ratchet emits ``ESCALATE`` (S-5 — never silently downgrade an
        escalation signal).
    ratchet_artifact:
        Optional ``{str: object}`` payload snapshot recorded into
        :pyattr:`MonotonicRatchet.best_artifact_snapshot` whenever the
        round becomes the new best. Ignored when ``ratchet is None``.
    """
    if history is None:
        history = []

    if breaker is not None:
        decision = _resolve_breaker_decision(breaker, cumulative_tokens)
        if decision.action is BudgetAction.BREAK:
            verdict = _build_budget_break_verdict(decision)
            if cycle_detector is not None:
                cycle_report = cycle_detector.detect_cycle()
                if cycle_report.detected:
                    _attach_cycle_report(verdict, cycle_report)
            if ratchet is not None:
                _attach_ratchet_action(verdict, gate_input, ratchet, round_num, ratchet_artifact)
            return verdict
    else:
        decision = None

    resolved = _resolve_gate_type(gate_type)
    handler = _GATE_DISPATCH.get(resolved)

    if handler is not None:
        verdict = handler(gate_input, profile)
    elif history:
        verdict = _evaluate_convergence(gate_input, profile, round_num, history)
    else:
        verdict = _evaluate_standard(gate_input, profile)

    _apply_advisor_detection(verdict, profile)

    if decision is not None and decision.action is BudgetAction.WARN:
        _attach_budget_warning(verdict, decision)

    if cycle_detector is not None:
        cycle_report = cycle_detector.detect_cycle()
        if cycle_report.detected:
            _attach_cycle_report(verdict, cycle_report)

    if ratchet is not None:
        _attach_ratchet_action(verdict, gate_input, ratchet, round_num, ratchet_artifact)

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


def _compute_convergence_dimensions(gate_input: GateInput, q_score: float) -> dict[str, float]:
    """Derive dimension scores from gate input for convergence evaluation."""
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

    # v5.4.0: User-facing verification dimensions
    dims["visual_fidelity"] = visual_fidelity_score(gate_input.visual_test_results)
    dims["interaction_quality"] = interaction_quality_score(
        gate_input.interaction_test_results, gate_input.accessibility_results
    )
    dims["acceptance_verification"] = acceptance_verification_score(
        gate_input.acceptance_verification_results
    )
    return dims


def _evaluate_convergence(
    gate_input: GateInput,
    profile: GateProfile,
    round_num: int,
    history: list[ConvergenceRound],
) -> GateVerdict:
    """Multi-round convergence gate (§5.7 flowchart)."""
    q_score = quality_score(gate_input.review_findings)
    dims = _compute_convergence_dimensions(gate_input, q_score)
    weights = EXTENDED_DIMENSION_WEIGHTS if _has_user_facing_inputs(gate_input) else None
    score = composite_score(dims, weights)
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

    tolerance = profile.noise_tolerance_pct
    if detect_stagnation(history, noise_tolerance_pct=tolerance):
        trend = compute_smoothed_trend(history) if tolerance > 0.0 else compute_trend(history)
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


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point — closes G-B1 (audit §3.B). The previous v7.4.4 implementation
# was a one-line print stub that silently masked real failures
# (S-5 No-Silent-Failures violation).
# ─────────────────────────────────────────────────────────────────────────────


_EXIT_PASS = 0
_EXIT_FAIL = 1
_EXIT_USAGE = 2

_GATE_TYPE_CHOICES: tuple[str, ...] = (
    "standard",
    "convergence",
    "passthrough",
    "acceptance_readiness",
    "preflight",
    "revision",
    "escalation",
    "abort",
)


def _check_result_from_dict(data: object) -> CheckResult | None:
    """Convert an optional YAML mapping into a :class:`CheckResult`."""
    if data is None:
        return None
    if not isinstance(data, dict):
        raise TypeError(f"check result must be a mapping (got {type(data).__name__})")
    status = data.get("status")
    if status not in ("pass", "fail", "skip"):
        raise ValueError(f"check result status must be one of pass/fail/skip (got {status!r})")
    details = data.get("details") or {}
    if not isinstance(details, dict):
        raise TypeError(f"check result details must be a mapping (got {type(details).__name__})")
    return CheckResult(status=status, details=dict(details))


def _finding_from_dict(data: object) -> Finding:
    """Convert one YAML mapping into a :class:`Finding`."""
    if not isinstance(data, dict):
        raise TypeError(f"finding must be a mapping (got {type(data).__name__})")
    severity = data.get("severity")
    if severity not in SEVERITY_WEIGHTS:
        raise ValueError(
            f"finding severity must be one of {sorted(SEVERITY_WEIGHTS)} (got {severity!r})"
        )
    return Finding(
        finding_id=str(data.get("finding_id", "")),
        severity=severity,  # type: ignore[arg-type]
        category=str(data.get("category", "")),
        location=str(data.get("location", "")),
        description=str(data.get("description", "")),
        suggestion=str(data.get("suggestion", "")),
        rule_id=str(data.get("rule_id", "")),
    )


def _build_gate_input(raw: dict) -> GateInput:
    """Build a :class:`GateInput` from a parsed YAML mapping.

    Required top-level keys: ``build_status``, ``test_results``, ``lint_status``.
    Optional: ``review_findings``, ``acceptance_criteria_results``, plus the
    four user-facing verification check results (visual / interaction /
    accessibility / acceptance_verification).
    """
    required = ("build_status", "test_results", "lint_status")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(
            f"gate input missing required keys: {missing} (expected: {list(required)})"
        )

    raw_findings = raw.get("review_findings") or []
    if not isinstance(raw_findings, list):
        raise TypeError(f"review_findings must be a list (got {type(raw_findings).__name__})")
    review_findings = [_finding_from_dict(f) for f in raw_findings]

    build = _check_result_from_dict(raw["build_status"])
    test = _check_result_from_dict(raw["test_results"])
    lint = _check_result_from_dict(raw["lint_status"])
    if build is None or test is None or lint is None:
        # required keys cannot be null — _check_result_from_dict only returns
        # None for explicit YAML null
        raise ValueError("build_status, test_results, lint_status must not be null")

    return GateInput(
        build_status=build,
        test_results=test,
        lint_status=lint,
        review_findings=review_findings,
        acceptance_criteria_results=_check_result_from_dict(raw.get("acceptance_criteria_results")),
        visual_test_results=_check_result_from_dict(raw.get("visual_test_results")),
        interaction_test_results=_check_result_from_dict(raw.get("interaction_test_results")),
        accessibility_results=_check_result_from_dict(raw.get("accessibility_results")),
        acceptance_verification_results=_check_result_from_dict(
            raw.get("acceptance_verification_results")
        ),
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for ``validate-gate``."""
    parser = argparse.ArgumentParser(
        prog="validate-gate",
        description=(
            "Evaluate a DevolaFlow gate checkpoint. Loads a YAML gate-input "
            "file, calls evaluate_gate(), and prints decision / composite / "
            "findings to stdout. Exit code 0 = PASS, 1 = FAIL or ESCALATE, "
            "2 = usage / IO / parse error."
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to a YAML gate-input file (build_status, test_results, "
        "lint_status, review_findings, ...)",
    )
    parser.add_argument(
        "--profile",
        "-p",
        default="standard",
        choices=sorted(PROFILES),
        help="Gate profile (default: standard)",
    )
    parser.add_argument(
        "--gate-type",
        default="standard",
        choices=list(_GATE_TYPE_CHOICES),
        help="Gate type (default: standard)",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=1,
        dest="round_num",
        help="Convergence round number (default: 1)",
    )
    return parser


def _format_findings(findings: list[Finding]) -> str:
    """Render a single-line ``blocker=N critical=N major=N minor=N info=N`` summary."""
    counts: Counter[str] = Counter(f.severity for f in findings)
    return (
        f"blocker={counts.get('blocker', 0)} "
        f"critical={counts.get('critical', 0)} "
        f"major={counts.get('major', 0)} "
        f"minor={counts.get('minor', 0)} "
        f"info={counts.get('info', 0)}"
    )


def run_gate_cli(args: Sequence[str]) -> None:
    """CLI entry point for the ``validate-gate`` console script.

    Behaviour
    ---------
    * Empty ``args`` — print usage to stdout and **return** without raising.
      This preserves the smoke-test contract used by
      ``tests/test_exercise_modules.py::test_stub_helpers``.
    * ``--help`` / ``-h`` — argparse prints usage and exits 0.
    * Otherwise:
        1. parse ``--input``/``--profile``/``--gate-type``/``--round``;
        2. read the input YAML, build a :class:`GateInput`;
        3. dispatch to :func:`evaluate_gate` (unmodified — wrap-not-modify);
        4. print ``decision: …``, optional ``composite: …``,
           ``findings: blocker=… critical=… …``, ``profile: …``,
           ``gate_type: …``, ``rationale: …`` to stdout;
        5. exit 0 (PASS) / 1 (FAIL or ESCALATE) / 2 (usage / IO / parse error).

    Closes ghost G-B1 (`.local/research/v7.5.0_ghost_audit.md` §3.B): the
    previous body was a one-line print stub — an S-4 / CP-1 No-Ghost-Features
    + S-5 No-Silent-Failures violation.
    """
    parser = _build_arg_parser()

    if not args:
        parser.print_help()
        return

    parsed = parser.parse_args(list(args))

    if parsed.input is None:
        parser.print_help()
        sys.exit(_EXIT_USAGE)

    input_path = Path(parsed.input)
    if not input_path.is_file():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(_EXIT_USAGE)

    try:
        raw = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"error: malformed YAML in {input_path}: {exc}", file=sys.stderr)
        sys.exit(_EXIT_USAGE)

    if not isinstance(raw, dict):
        print(
            f"error: gate input must be a YAML mapping (got {type(raw).__name__})",
            file=sys.stderr,
        )
        sys.exit(_EXIT_USAGE)

    try:
        gate_input = _build_gate_input(raw)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"error: invalid gate input: {exc}", file=sys.stderr)
        sys.exit(_EXIT_USAGE)

    profile = PROFILES.get(parsed.profile, STANDARD)

    verdict = evaluate_gate(
        gate_input,
        profile,
        round_num=parsed.round_num,
        gate_type=parsed.gate_type,
    )

    print(f"decision: {verdict.decision}")
    if verdict.composite_score is not None:
        print(f"composite: {verdict.composite_score:.2f}")
    print(f"findings: {_format_findings(gate_input.review_findings)}")
    print(f"profile: {profile.name}")
    print(f"gate_type: {parsed.gate_type}")
    print(f"rationale: {verdict.rationale}")

    sys.exit(_EXIT_PASS if verdict.decision == "PASS" else _EXIT_FAIL)
