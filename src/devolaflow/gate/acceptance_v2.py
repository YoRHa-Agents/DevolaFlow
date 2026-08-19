"""AC-v2 evaluation — subprocess runner + v14.4.0 metric runners + aggregation.

v14.5.0 (ADR-006 / gap G-025 module split) — code extracted VERBATIM from
``gate/scorer.py`` lines ~1606-1820 (the v8.0.0 P-10 automatic
acceptance-criteria evaluation: ``CommandRunResult`` +
``_default_command_runner`` + ``evaluate_acceptance_criteria_v2`` +
``aggregate_criterion_verdicts``) including the v14.4.0 metric runners
(``METRIC_KIND_*`` + ``_evaluate_metric_criterion``) that extend the same
concern, per
``docs/cycle-archive/adr/v15-ADR-006-scorer-selector-module-split.md`` decision
item 1 ("the module the v14.4.0 metric runners then extend in place").

PERMANENT identity-preserving re-export shims live at the old
``devolaflow.gate.scorer`` path per the ADR's shim clause. Pinned by
``tests/test_module_split_shims.py``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from devolaflow.gate.models import (
    AcceptanceCriterion,
    AcceptanceCriterionVerdict,
    CheckResult,
)

# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-10) — Automatic Acceptance Criteria evaluation
#
# ``evaluate_acceptance_criteria_v2`` runs each
# :class:`AcceptanceCriterion` in a list (typically sourced from the
# dispatch payload's ``acceptance_criteria_v2`` field — canonical_order
# position 15, schema version 4) and emits a list of
# :class:`AcceptanceCriterionVerdict`. Three verdict paths follow
# ``patch_plan §3 P-10``:
#
#     test    — invoke ``verification_cmd`` via the supplied runner
#               (default :mod:`subprocess`); exit 0 → pass, else → fail.
#     metric  — v14.4.0: entries WITH a ``verification_cmd`` are executed
#               by the metric runner (coverage / lint / number kinds —
#               see the v14.4.0 comment block above
#               ``_evaluate_metric_criterion``); entries WITHOUT one keep
#               the legacy skip-with-reason verdict (the metric runner is
#               external; the verdict surfaces the metric + threshold
#               so a downstream analytics pass can ratify).
#     manual  — skip with a deterministic message ("manual review
#               required"); never silently treated as PASS (S-5).
#
# When the dispatch supplies no ``acceptance_criteria_v2`` (legacy
# v7.x payloads), the gate falls back to the existing
# ``GateInput.acceptance_criteria_results: CheckResult`` path —
# byte-identical to pre-P-10 behaviour (``patch_plan §3 P-10 AC #5``).
#
# ``aggregate_criterion_verdicts`` folds a verdict list into a single
# :class:`CheckResult` so callers can stuff it into
# :pyattr:`GateInput.acceptance_criteria_results` and reuse the existing
# ``_evaluate_standard`` failure branch without a separate dispatch
# table.
# ─────────────────────────────────────────────────────────────────────────────


CommandRunner = Callable[[AcceptanceCriterion], "CommandRunResult"]


@dataclass(frozen=True)
class CommandRunResult:
    """Result of running a single ``verification_cmd`` (test path).

    Wraps the subset of :class:`subprocess.CompletedProcess` semantics
    we actually need so unit tests can inject a pure-Python mock without
    spawning processes. ``stdout`` / ``stderr`` are best-effort — empty
    strings are acceptable when the runner does not capture output.
    """

    returncode: int
    stdout: str = ""
    stderr: str = ""


def _default_command_runner(criterion: AcceptanceCriterion) -> CommandRunResult:
    """Default :data:`CommandRunner` — invoke
    ``criterion.verification_cmd`` via :mod:`subprocess` with shell=True.

    S-5 No Silent Failures — exceptions from :class:`subprocess.SubprocessError`
    are caught and rendered as a non-zero CommandRunResult with the
    exception class name in ``stderr`` so the verdict shows ``fail``
    rather than crashing the gate. Other exceptions propagate.
    """
    import subprocess

    if not criterion.verification_cmd:
        # Defensive — should be filtered by evaluate_acceptance_criteria_v2.
        return CommandRunResult(
            returncode=2,
            stderr="verification_cmd is empty",
        )
    try:
        completed = subprocess.run(  # noqa: S602 - shell=True is intentional
            criterion.verification_cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            timeout=900,
        )
    except subprocess.SubprocessError as exc:
        return CommandRunResult(
            returncode=2,
            stderr=f"{type(exc).__name__}: {exc}",
        )
    return CommandRunResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


# ─────────────────────────────────────────────────────────────────────────────
# v14.4.0 — AC-v2 metric runners (gap register §4.1 v14.4.0 row)
#
# ``verification_type='metric'`` criteria that carry a ``verification_cmd``
# are now EXECUTED rather than skipped. Two prescribed metric kinds plus a
# generic fallback (the kind is derived from ``AcceptanceCriterion.metric``;
# the dispatch-payload ``metric_kind`` field documented in
# ``schemas/lean-dispatch.yaml`` maps onto the same three literals):
#
#     coverage — run the cmd (e.g. ``pytest --cov`` / ``coverage report``),
#                parse the LAST percentage in the output (the TOTAL line is
#                last in both tools), compare against the threshold.
#     lint     — run the cmd (e.g. ``ruff check path``), pass on exit 0.
#     number   — run the cmd, parse the LAST number in the output, compare
#                against the threshold (any metric name other than
#                'coverage'/'lint' selects this kind).
#
# Threshold expressions embed the comparison operator (``">= 80"``,
# ``"<= 100"``, ``"== 0"``); a bare number defaults to ``>=``. Bounded
# subprocess execution reuses the SAME injected :data:`CommandRunner` as
# the test path (default :func:`_default_command_runner`, timeout 900s).
# S-5: runner errors / unparsable output / unparsable thresholds produce
# explicit ``fail`` verdicts with the cause in the message — NEVER a
# silent skip. Metric criteria WITHOUT a ``verification_cmd`` keep the
# legacy v8.0.0 P-10 skip-with-reason verdict byte-identically;
# ``manual`` criteria stay skip-with-reason.
# ─────────────────────────────────────────────────────────────────────────────

METRIC_KIND_COVERAGE = "coverage"
METRIC_KIND_LINT = "lint"
METRIC_KIND_NUMBER = "number"

# "<op> <value>" with optional trailing '%' (coverage thresholds are often
# written ">= 80%"). Bare numbers parse with op=None → defaults to ">=".
_THRESHOLD_EXPR_RE = re.compile(r"^\s*(>=|<=|==|>|<)?\s*([-+]?\d+(?:\.\d+)?)\s*%?\s*$")
_PERCENT_RE = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*%")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _metric_kind_for(criterion: AcceptanceCriterion) -> str:
    """Derive the metric kind from ``criterion.metric`` (case-insensitive).

    ``'coverage'`` / ``'lint'`` select the two prescribed kinds; any other
    metric name (``'latency_p95_ms'``, ``'number'``, empty, …) selects the
    generic ``number`` kind. Mirrors the ``metric_kind`` per-entry doc in
    ``schemas/lean-dispatch.yaml#lean_format_spec.acceptance_criteria_v2``.
    """
    name = (criterion.metric or "").strip().lower()
    if name in (METRIC_KIND_COVERAGE, METRIC_KIND_LINT):
        return name
    return METRIC_KIND_NUMBER


def _parse_threshold_expression(threshold: str) -> tuple[str, float] | None:
    """Parse ``threshold`` into ``(comparison_op, target)`` or ``None``.

    Accepts ``">= 80"``, ``"<=100"``, ``"== 0"``, ``"> 1.5"``, ``"< 200"``
    and bare numbers (``"80"`` → ``(">=", 80.0)``). Unparsable input
    returns ``None`` — the caller converts that into an explicit ``fail``
    verdict per S-5 (never a silent skip).
    """
    match = _THRESHOLD_EXPR_RE.match(threshold or "")
    if match is None:
        return None
    op = match.group(1) or ">="
    return op, float(match.group(2))


def _compare_measured(measured: float, op: str, target: float) -> bool:
    """Apply the parsed comparison operator. Exhaustive over the 5-op set."""
    if op == ">=":
        return measured >= target
    if op == "<=":
        return measured <= target
    if op == ">":
        return measured > target
    if op == "<":
        return measured < target
    return measured == target  # "=="


def _evaluate_metric_criterion(
    criterion: AcceptanceCriterion,
    runner: CommandRunner,
) -> AcceptanceCriterionVerdict:
    """Run one ``verification_type='metric'`` criterion (v14.4.0).

    No ``verification_cmd`` → legacy v8.0.0 P-10 skip-with-reason verdict
    (byte-identical message — preserves the pre-v14.4.0 contract for
    caller-driven metric evaluation). With a cmd, the kind from
    :func:`_metric_kind_for` selects the runner semantics documented on
    the module-level v14.4.0 comment block above.
    """
    if not criterion.verification_cmd:
        # Legacy caller-driven path — byte-identical to the pre-v14.4.0
        # skip verdict so existing dispatchers see no behaviour change.
        return AcceptanceCriterionVerdict(
            criterion_id=criterion.id,
            status="skip",
            message=(
                f"metric '{criterion.metric}' requires external evaluator "
                f"(threshold='{criterion.threshold}')"
            ),
            details={
                "verification_type": "metric",
                "metric": criterion.metric,
                "threshold": criterion.threshold,
            },
        )

    kind = _metric_kind_for(criterion)
    result = runner(criterion)
    details: dict[str, object] = {
        "verification_type": "metric",
        "metric": criterion.metric,
        "metric_kind": kind,
        "threshold": criterion.threshold,
        "verification_cmd": criterion.verification_cmd,
        "returncode": result.returncode,
        "stdout": result.stdout[-500:],
        "stderr": result.stderr[-500:],
    }

    if kind == METRIC_KIND_LINT:
        if result.returncode == 0:
            return AcceptanceCriterionVerdict(
                criterion_id=criterion.id,
                status="pass",
                message=f"lint metric cmd exited 0: {criterion.verification_cmd}",
                details=details,
            )
        return AcceptanceCriterionVerdict(
            criterion_id=criterion.id,
            status="fail",
            message=(f"lint metric cmd exit={result.returncode}: {criterion.verification_cmd}"),
            details=details,
        )

    # coverage / number kinds — parse the measured value from the output
    # (stdout first, stderr fallback), then compare against the threshold.
    pattern = _PERCENT_RE if kind == METRIC_KIND_COVERAGE else _NUMBER_RE
    matches = pattern.findall(result.stdout) or pattern.findall(result.stderr)
    if not matches:
        # S-5: explicit fail — never silently skip a runner error.
        return AcceptanceCriterionVerdict(
            criterion_id=criterion.id,
            status="fail",
            message=(
                f"{kind} metric cmd produced no parsable "
                f"{'percentage' if kind == METRIC_KIND_COVERAGE else 'number'} "
                f"(exit={result.returncode}): {criterion.verification_cmd}"
            ),
            details=details,
        )
    measured = float(matches[-1])
    details["measured"] = measured

    parsed = _parse_threshold_expression(criterion.threshold)
    if parsed is None:
        return AcceptanceCriterionVerdict(
            criterion_id=criterion.id,
            status="fail",
            message=(
                f"{kind} metric threshold {criterion.threshold!r} is not a parsable "
                "comparison expression (expected e.g. '>= 80')"
            ),
            details=details,
        )
    op, target = parsed
    details["comparison"] = op
    details["target"] = target

    if _compare_measured(measured, op, target):
        return AcceptanceCriterionVerdict(
            criterion_id=criterion.id,
            status="pass",
            message=f"{kind} metric measured {measured} {op} {target}",
            details=details,
        )
    return AcceptanceCriterionVerdict(
        criterion_id=criterion.id,
        status="fail",
        message=f"{kind} metric measured {measured} violates threshold {op} {target}",
        details=details,
    )


def evaluate_acceptance_criteria_v2(
    criteria: list[AcceptanceCriterion],
    *,
    runner: CommandRunner | None = None,
) -> list[AcceptanceCriterionVerdict]:
    """Auto-evaluate a list of :class:`AcceptanceCriterion`.

    Per ``patch_plan §3 P-10`` (metric path extended at v14.4.0):

    - ``verification_type='test'`` → invoke ``verification_cmd`` via
      *runner* (default :func:`_default_command_runner`); exit 0 →
      ``pass``, else → ``fail``.
    - ``verification_type='metric'`` WITH a ``verification_cmd`` →
      executed by the v14.4.0 metric runner
      (:func:`_evaluate_metric_criterion`): ``coverage`` kind parses the
      last percentage from the cmd output and compares it against the
      threshold expression; ``lint`` kind passes on exit 0; any other
      metric name selects the generic ``number`` kind (parse last
      number, compare). Runner errors → explicit ``fail`` per S-5.
    - ``verification_type='metric'`` WITHOUT a ``verification_cmd`` →
      ``skip`` with the metric + threshold echoed in details
      (caller-driven evaluation — byte-identical pre-v14.4.0 path).
    - ``verification_type='manual'`` → ``skip`` with the message
      ``"manual review required"`` (S-5 — never silently treat as PASS).

    Duplicate ``criterion.id`` entries raise :class:`ValueError` because
    the dispatch payload's ``acceptance_criteria_v2`` field MUST carry
    unique ids (the verdicts are keyed by id downstream).

    When *criteria* is empty, an empty verdict list is returned — the
    legacy ``acceptance_criteria_results`` fallback path remains
    byte-identical to pre-P-10 behaviour (``AC #5``).
    """
    if not criteria:
        return []

    seen_ids: set[str] = set()
    for c in criteria:
        if c.id in seen_ids:
            raise ValueError(
                f"duplicate AcceptanceCriterion.id {c.id!r} in evaluate_acceptance_criteria_v2 "
                "(ids MUST be unique per dispatch payload)"
            )
        seen_ids.add(c.id)

    actual_runner = runner if runner is not None else _default_command_runner
    verdicts: list[AcceptanceCriterionVerdict] = []
    for c in criteria:
        if c.verification_type == "test":
            if not c.verification_cmd:
                verdicts.append(
                    AcceptanceCriterionVerdict(
                        criterion_id=c.id,
                        status="skip",
                        message="test criterion has no verification_cmd",
                        details={"verification_type": "test"},
                    )
                )
                continue
            result = actual_runner(c)
            if result.returncode == 0:
                status = "pass"
                message = f"verification_cmd exited 0: {c.verification_cmd}"
            else:
                status = "fail"
                message = f"verification_cmd exit={result.returncode}: {c.verification_cmd}"
            verdicts.append(
                AcceptanceCriterionVerdict(
                    criterion_id=c.id,
                    status=status,  # type: ignore[arg-type]
                    message=message,
                    details={
                        "verification_type": "test",
                        "verification_cmd": c.verification_cmd,
                        "returncode": result.returncode,
                        "stdout": result.stdout[-500:],
                        "stderr": result.stderr[-500:],
                    },
                )
            )
        elif c.verification_type == "metric":
            verdicts.append(_evaluate_metric_criterion(c, actual_runner))
        else:  # manual
            verdicts.append(
                AcceptanceCriterionVerdict(
                    criterion_id=c.id,
                    status="skip",
                    message="manual review required",
                    details={"verification_type": "manual"},
                )
            )
    return verdicts


def aggregate_criterion_verdicts(
    verdicts: list[AcceptanceCriterionVerdict],
) -> CheckResult:
    """Fold per-criterion verdicts into a single :class:`CheckResult`.

    Per ``patch_plan §3 P-10``: the gate's existing
    ``GateInput.acceptance_criteria_results`` slot expects a
    :class:`CheckResult`. This helper aggregates the structured verdicts
    so callers can route them into the legacy code path without changing
    :func:`_evaluate_standard`.

    Status rules (S-5 — never silently downgrade a fail):

    - empty list → ``status='skip'`` with message ``"no criteria"``.
    - any verdict ``status='fail'`` → ``status='fail'``.
    - all verdicts ``status='pass'`` → ``status='pass'``.
    - mix of ``pass`` and ``skip`` (no failures) → ``status='pass'``.
    - all verdicts ``status='skip'`` → ``status='skip'`` (the gate
      treats this as advisory; downstream consumers decide whether to
      escalate).
    """
    if not verdicts:
        return CheckResult(
            status="skip",
            details={"acceptance_criteria_v2": "no criteria"},
        )

    status_counts: Counter[str] = Counter(v.status for v in verdicts)
    failing = [v for v in verdicts if v.status == "fail"]
    passing = [v for v in verdicts if v.status == "pass"]
    skipping = [v for v in verdicts if v.status == "skip"]

    if failing:
        status: str = "fail"
        message = (
            f"{len(failing)}/{len(verdicts)} criteria FAILED: "
            f"{', '.join(v.criterion_id for v in failing[:5])}"
        )
    elif passing:
        status = "pass"
        message = f"{len(passing)}/{len(verdicts)} criteria PASSED"
    else:
        status = "skip"
        message = (
            f"{len(skipping)}/{len(verdicts)} criteria SKIPPED (no auto-runnable verifications)"
        )

    return CheckResult(
        status=status,  # type: ignore[arg-type]
        details={
            "acceptance_criteria_v2": True,
            "criteria_total": len(verdicts),
            "criteria_passing": len(passing),
            "criteria_failing": len(failing),
            "criteria_skipped": len(skipping),
            "status_counts": dict(status_counts),
            "message": message,
            "failing_ids": [v.criterion_id for v in failing],
            "skipping_ids": [v.criterion_id for v in skipping],
        },
    )
