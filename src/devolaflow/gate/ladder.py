"""The 6-rung verification ladder (R1..R6) — extracted from ``gate/scorer.py``.

v14.5.0 (ADR-006 / gap G-025 module split) — code extracted VERBATIM from
``gate/scorer.py`` lines ~863-1352 (the v8.0.0 P-05 ladder formalization:
``evaluate_ladder`` + the per-rung checkers) plus the v9.0.0 PV-06
``is_verification_ladder_active`` helper + ``VERIFICATION_LADDER_ENV_FLAG``
env-flag constant, per
``docs/cycle-archive/adr/v15-ADR-006-scorer-selector-module-split.md`` decision
item 1. Mechanical import fixes only: the two call sites of
``evaluate_gate`` / ``_attach_cycle_report`` (which stay in
``gate/scorer.py``) import them at function level to keep this module free
of module-level cycles.

PERMANENT identity-preserving re-export shims live at the old
``devolaflow.gate.scorer`` path per the ADR's shim clause. Pinned by
``tests/test_module_split_shims.py``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from devolaflow.gate.budget import TokenBudgetBreaker
from devolaflow.gate.complexity_detector import ComplexityDetector
from devolaflow.gate.cycle_detector import CycleDetector
from devolaflow.gate.models import (
    LADDER_RUNG_NAMES,
    LADDER_RUNG_ORDER,
    CheckResult,
    ComplexitySignals,
    ConvergenceRound,
    GateInput,
    GateProfile,
    GateVerdict,
    LadderEvaluation,
    LadderRung,
)
from devolaflow.gate.ratchet import MonotonicRatchet

# v9.0.0 PV-06 (v8.5.1) — Theme T5 #2 env-flag (R5 strict).
VERIFICATION_LADDER_ENV_FLAG: str = "DEVOLAFLOW_VERIFICATION_LADDER"
"""Env-flag controlling the v9.0.0 PV-06 default-on flip override.

R5 strict per ``workflow-system/agent/references/env-flags.md`` §2 parsing:

* env value EXACTLY ``"1"`` → force the ladder active regardless of profile
* env value EXACTLY ``"0"`` → force the ladder inactive regardless of profile
* env value unset / any other → respect ``profile.ladder_enabled``
"""


def is_verification_ladder_active(
    profile: GateProfile,
    env: dict[str, str] | None = None,
) -> bool:
    """Return True iff the 6-rung verification ladder should run for *profile*.

    Combines the v9.0.0 PV-06 default-on profile flag
    (:pyattr:`GateProfile.ladder_enabled` — True for STRICT/AUDIT) with the
    :data:`VERIFICATION_LADDER_ENV_FLAG` per-process override (R5 strict).
    Operators who want to disable the ladder on a flipped profile set
    ``DEVOLAFLOW_VERIFICATION_LADDER=0`` per env-flags.md §2.7.
    """
    source = env if env is not None else os.environ
    raw = source.get(VERIFICATION_LADDER_ENV_FLAG, "")
    if raw == "0":
        return False
    if raw == "1":
        return True
    return bool(profile.ladder_enabled)


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
    complexity_detector: ComplexityDetector | None = None,
    complexity_signals: ComplexitySignals | None = None,
    complexity_task_complexity: str = "standard",
    **_: object,
) -> LadderEvaluation:
    """R6 default checker — delegate to :func:`evaluate_gate` and translate
    its :class:`GateVerdict` into a :class:`LadderEvaluation`.

    The full verdict is preserved in ``details['verdict']`` so callers can
    still recover composite_score, escalation_context, etc.
    """
    from devolaflow.gate.scorer import evaluate_gate

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
        complexity_detector=complexity_detector,
        complexity_signals=complexity_signals,
        complexity_task_complexity=complexity_task_complexity,
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
    complexity_detector: ComplexityDetector | None = None,
    complexity_signals: ComplexitySignals | None = None,
    complexity_task_complexity: str = "standard",
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
    from devolaflow.gate.scorer import _attach_cycle_report, evaluate_gate

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
            complexity_detector=complexity_detector,
            complexity_signals=complexity_signals,
            complexity_task_complexity=complexity_task_complexity,
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
            complexity_detector=complexity_detector,
            complexity_signals=complexity_signals,
            complexity_task_complexity=complexity_task_complexity,
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
