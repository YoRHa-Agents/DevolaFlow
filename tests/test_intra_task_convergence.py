"""v14.4.0 gate-domain suite — intra-task convergence + metric runners + legibility opt-in.

Pins the three v14.4.0-T1 gate-domain deliverables (task source:
``.local/research/v14.2.0_gap_analysis.md`` §2.1 G-005 + §4.1 v14.4.0
row + §6 R-1):

* **Item 1 — ``gate.intra_task_convergence`` NEST (G-005)**: two new
  OPTIONAL sub-fields under the existing ``gate`` block per A-2.3
  (``intra_task_convergence: bool`` + ``intra_task_max_rounds: int``,
  default 2 per execution-protocol §15.4). Mirrors the v11.1.0 cascade
  NEST precedent EXACTLY: opt-in populate helper
  (:func:`devolaflow.feedback.populate_intra_task_convergence`,
  deep-copy, absence-canonical) + permissive-by-default validator
  (:func:`devolaflow.gate.scorer.validate_intra_task_convergence_fields`,
  warning list; ``strict=True`` raises
  :class:`IntraTaskConvergenceViolationError`). canonical_order LENGTH
  STAYS 17 and schema version STAYS 6 — the R-1 sentinel test below
  fires BEFORE the multi-baseline byte suite if this PV accidentally
  mutates the schema (same fast-failure pattern as
  ``tests/test_cascade_enforcement.py``).

* **Item 2 — AC-v2 metric runners**:
  ``evaluate_acceptance_criteria_v2`` now EXECUTES
  ``verification_type='metric'`` criteria that carry a
  ``verification_cmd`` (coverage / lint / number kinds); entries WITHOUT
  a cmd keep the legacy skip-with-reason verdict byte-identically and
  ``manual`` stays skip. Runner errors → explicit ``fail`` per S-5.

* **Item 3 — legibility opt-in weight**: ``GateProfile.legibility_weight``
  override via :func:`dataclasses.replace` shifts the gate composite by
  ``weight × (mean_score − 50)``. v15.0.0 G-038 flip 6 landed the
  telegraphed default flip: STANDARD is now ``0.05`` (matching
  STRICT/AUDIT; RELAXED stays ``0.0``); the ``replace(...,
  legibility_weight=0.0)`` override doubles as the documented opt-out.

W-17 note: this module adds 14 NEW test functions (at the per-PV cap
prescribed for this task: ≤ 14).
"""

from __future__ import annotations

import copy
import textwrap
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from devolaflow.compressor import DEFAULT_DISPATCH_LAYOUT, assert_dispatch_layout
from devolaflow.feedback import (
    INTRA_TASK_CONVERGENCE_TASK_TYPES,
    INTRA_TASK_MAX_ROUNDS_DEFAULT,
    populate_intra_task_convergence,
)
from devolaflow.gate.models import (
    AcceptanceCriterion,
    CheckResult,
    ConvergenceRound,
    GateInput,
)
from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT
from devolaflow.gate.scorer import (
    CommandRunResult,
    IntraTaskConvergenceViolationError,
    evaluate_acceptance_criteria_v2,
    evaluate_gate,
    validate_intra_task_convergence_fields,
)
from devolaflow.legibility import LegibilityScorer

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas/lean-dispatch.yaml"

_AC_V2_BLOCK = [
    {
        "id": "AC-001",
        "description": "tests pass",
        "verification_type": "test",
        "verification_cmd": "pytest tests/ -q",
    }
]


def _base_dispatch(*, with_ac_v2: bool = True) -> dict:
    base: dict = {"gate": {"coverage": 85, "quality": 85}}
    if with_ac_v2:
        base["acceptance_criteria_v2"] = copy.deepcopy(_AC_V2_BLOCK)
    return base


def _pass_gate_input() -> GateInput:
    """All-PASS :class:`GateInput` (mirrors tests/test_legibility.py)."""
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(
            status="pass",
            details={"coverage_pct": 90.0, "tests_total": 10, "tests_passed": 10},
        ),
        lint_status=CheckResult(status="pass", details={"architecture_score": 90.0}),
        review_findings=[],
        acceptance_criteria_results=CheckResult(status="pass"),
    )


def _round(num: int, score: float = 90.0) -> ConvergenceRound:
    return ConvergenceRound(
        round_num=num,
        composite_score=score,
        blocker_count=0,
        critical_count=0,
        timestamp="2026-06-12T00:00:00Z",
    )


# ── Item 1 — populate helper (cascade-precedent mirror) ────────────────


def test_populate_warranted_code_task_with_ac_v2_sets_both_sub_fields() -> None:
    """code task + non-empty acceptance_criteria_v2 → both NEST sub-fields populated.

    Mirrors the cascade populate contract
    (``tests/test_cascade_enforcement.py`` Branch 2): deep copy, base
    never mutated, pre-existing gate keys preserved, sub-fields NESTed
    under ``gate`` — never top-level.
    """
    base = _base_dispatch(with_ac_v2=True)
    base_snapshot = copy.deepcopy(base)

    result = populate_intra_task_convergence(base, task_type="code")

    assert result["gate"]["intra_task_convergence"] is True
    assert result["gate"]["intra_task_max_rounds"] == INTRA_TASK_MAX_ROUNDS_DEFAULT == 2
    # NEST, not APPEND (A-2.3): no top-level leak.
    assert "intra_task_convergence" not in result
    assert "intra_task_max_rounds" not in result
    # Pre-existing gate sub-fields preserved.
    assert result["gate"]["coverage"] == 85
    # Deep-copy contract.
    assert base == base_snapshot, "populate_intra_task_convergence mutated base_dispatch"
    assert result is not base

    # The warrant set itself is pinned: implementation-class only.
    assert frozenset({"code", "test", "config"}) == INTRA_TASK_CONVERGENCE_TASK_TYPES


def test_populate_impl_task_without_ac_v2_is_absence_canonical() -> None:
    """code task WITHOUT acceptance_criteria_v2 → deep copy returned unchanged.

    The §15 gen→verify loop needs structured criteria to verify against;
    without them the warrant rule does not fire and the rendering stays
    byte-identical to v14.3.0 (A-2.3 absence-as-default).
    """
    base = _base_dispatch(with_ac_v2=False)

    result = populate_intra_task_convergence(base, task_type="code")

    assert "intra_task_convergence" not in result["gate"]
    assert "intra_task_max_rounds" not in result["gate"]
    assert result == base
    assert result is not base

    # Empty AC-v2 list is NOT a warrant either (non-empty required).
    empty_ac = {"gate": {}, "acceptance_criteria_v2": []}
    result_empty = populate_intra_task_convergence(empty_ac, task_type="code")
    assert "intra_task_convergence" not in result_empty["gate"]


def test_populate_non_impl_task_with_ac_v2_is_absence_canonical() -> None:
    """review/research/design/benchmark (and unknown) types never populate.

    The warrant rule is implementation-class ONLY — every other
    ``task.type`` value (including unknown types from open workflow
    templates) takes the absence-canonical path.
    """
    base = _base_dispatch(with_ac_v2=True)

    for task_type in ("review", "research", "design", "benchmark", "release", "mystery"):
        result = populate_intra_task_convergence(base, task_type=task_type)
        assert "intra_task_convergence" not in result["gate"], (
            f"task_type={task_type!r} unexpectedly warranted intra_task_convergence"
        )
        assert "intra_task_max_rounds" not in result["gate"]
        assert result == base


# ── Item 1 — validator slice (permissive default / strict raises) ──────


def test_validate_absence_paths_return_no_warnings() -> None:
    """None gate / legacy gate / helper-populated gate → no violations.

    Absence-canonical short-circuits per A-2.3 — legacy v14.3.0
    dispatches flow through byte-identically in BOTH permissive and
    strict modes (the same R-12-style carve-out the cascade validator
    preserves).
    """
    assert validate_intra_task_convergence_fields(None) == []
    assert validate_intra_task_convergence_fields({"coverage": 85}) == []
    assert validate_intra_task_convergence_fields(None, strict=True) == []
    assert validate_intra_task_convergence_fields({"coverage": 85}, strict=True) == []

    # Helper-populated gate block passes cleanly end-to-end.
    populated = populate_intra_task_convergence(_base_dispatch(), task_type="code")
    assert validate_intra_task_convergence_fields(populated["gate"]) == []
    assert validate_intra_task_convergence_fields(populated["gate"], strict=True) == []


def test_validate_type_violations_warn_permissive_and_raise_strict() -> None:
    """Type violations → warning list (permissive) / raise (strict).

    DEFAULTS-PERMISSIVE-IN-MINOR per the v11.1.0 cascade SOFT-mode
    precedent. Every message carries the operator-quotable ``G-005``
    identifier (the same discipline ``A-7`` uses on cascade messages).
    """
    # Non-bool intra_task_convergence (string-typed truthy — the most
    # likely YAML miswiring, mirroring the cascade "yes" case).
    warnings = validate_intra_task_convergence_fields({"intra_task_convergence": "yes"})
    assert len(warnings) == 1
    assert "G-005" in warnings[0]
    assert "intra_task_convergence must be bool" in warnings[0]

    # Bad max_rounds variants: non-int / zero / bool (bool is an int
    # subclass — excluded explicitly, mirroring cascade_min_layers).
    for bad in ("two", 0, -1, True, None):
        warnings = validate_intra_task_convergence_fields({"intra_task_max_rounds": bad})
        assert len(warnings) == 1, f"intra_task_max_rounds={bad!r} did not warn"
        assert "G-005" in warnings[0]
        assert "intra_task_max_rounds must be int >= 1" in warnings[0]

    # Both fields bad → both warnings accumulate in permissive mode.
    both = validate_intra_task_convergence_fields(
        {"intra_task_convergence": 1, "intra_task_max_rounds": "two"}
    )
    assert len(both) == 2

    # Strict mode raises on the FIRST violation.
    with pytest.raises(IntraTaskConvergenceViolationError) as excinfo:
        validate_intra_task_convergence_fields({"intra_task_convergence": "yes"}, strict=True)
    assert "G-005" in str(excinfo.value)
    with pytest.raises(IntraTaskConvergenceViolationError):
        validate_intra_task_convergence_fields({"intra_task_max_rounds": 0}, strict=True)
    # Exception-class contract mirrors CascadeViolationError: a plain
    # Exception subclass, NOT ValueError.
    assert issubclass(IntraTaskConvergenceViolationError, Exception)
    assert not issubclass(IntraTaskConvergenceViolationError, ValueError)


# ── Item 1 — A-2 / R-1 layout invariants ────────────────────────────────


def test_intra_task_nest_preserves_canonical_layout_and_absence_bytes() -> None:
    """Populated NEST passes layout validation; absence renders byte-identically.

    The headline R-1 proof at the payload level: (a) a populated
    dispatch's TOP-LEVEL key sequence is unchanged (the sub-fields live
    under ``gate``) and passes ``assert_dispatch_layout``; (b) the
    non-warranted path renders byte-identical YAML to a deepcopy of the
    base — canonical absence-as-default per A-2.3.
    """
    base = _base_dispatch(with_ac_v2=True)
    populated = populate_intra_task_convergence(base, task_type="code")

    # Top-level key sequence unchanged — NEST never adds a top-level key.
    assert list(populated.keys()) == list(base.keys())
    assert_dispatch_layout(populated)

    # Absence path: byte-identical rendering vs a plain deepcopy.
    not_warranted = populate_intra_task_convergence(base, task_type="review")
    render = yaml.safe_dump(not_warranted, sort_keys=False, default_flow_style=False)
    control = yaml.safe_dump(copy.deepcopy(base), sort_keys=False, default_flow_style=False)
    assert render == control, (
        "non-warranted populate_intra_task_convergence output is NOT byte-identical "
        "to the base dispatch — A-2.3 absence-as-default contract broken"
    )


def test_schema_canonical_order_stays_17_and_version_stays_6() -> None:
    """Sentinel: the v14.4.0 NEST makes ZERO canonical_order / version edits.

    Mirrors ``tests/test_cascade_enforcement.py::
    test_cascade_required_does_not_invalidate_layout_invariant`` — a
    faster failure signal scoped to this PV that fires BEFORE the
    multi-baseline byte suite. Any change to canonical_order LENGTH is
    a release blocker per A-2 (task constraint R-1).
    """
    schema_data = yaml.safe_load(_SCHEMA_PATH.read_text())
    canonical_order = schema_data["layout_invariant"]["canonical_order"]

    assert len(canonical_order) == 17, (
        f"canonical_order length drifted to {len(canonical_order)} — the v14.4.0 "
        "G-005 slice is a NEST (A-2.3); LENGTH MUST stay 17 (release blocker per R-1)"
    )
    assert schema_data["layout_invariant"]["version"] == 6
    assert tuple(canonical_order) == tuple(DEFAULT_DISPATCH_LAYOUT)

    # The NEST sub-fields are documented under lean_format_spec.gate —
    # NOT as new canonical keys.
    gate_spec = schema_data["lean_format_spec"]["gate"]
    assert "intra_task_convergence" in gate_spec
    assert "intra_task_max_rounds" in gate_spec
    assert "intra_task_convergence" not in canonical_order
    assert "intra_task_max_rounds" not in canonical_order


# ── Item 2 — AC-v2 metric runners ───────────────────────────────────────


def test_metric_lint_kind_pass_on_exit_zero_fail_otherwise() -> None:
    """lint kind: exit 0 → pass; non-zero → fail (explicit verdicts, S-5)."""
    crit = AcceptanceCriterion(
        id="AC-1",
        description="ruff clean",
        verification_type="metric",
        verification_cmd="ruff check src/",
        metric="lint",
    )

    ok = evaluate_acceptance_criteria_v2(
        [crit], runner=lambda c: CommandRunResult(returncode=0, stdout="All checks passed!")
    )
    assert ok[0].status == "pass"
    assert ok[0].details["metric_kind"] == "lint"
    assert ok[0].details["returncode"] == 0

    bad = evaluate_acceptance_criteria_v2(
        [crit], runner=lambda c: CommandRunResult(returncode=1, stdout="E501 found")
    )
    assert bad[0].status == "fail"
    assert bad[0].details["returncode"] == 1


def test_metric_coverage_kind_parses_total_percentage_and_compares() -> None:
    """coverage kind: parse the LAST percentage (the TOTAL line) and compare."""
    cov_output = textwrap.dedent(
        """\
        Name                 Stmts   Miss  Cover
        ----------------------------------------
        src/pkg/a.py            80      2    97%
        src/pkg/b.py            40      8    80%
        ----------------------------------------
        TOTAL                  120     10    92%
        """
    )

    def runner(c: AcceptanceCriterion) -> CommandRunResult:
        return CommandRunResult(returncode=0, stdout=cov_output)

    base = {
        "id": "AC-1",
        "description": "coverage floor",
        "verification_type": "metric",
        "verification_cmd": "pytest --cov=pkg tests/ -q",
        "metric": "coverage",
    }
    passing = AcceptanceCriterion(**base, threshold=">= 90")
    verdicts = evaluate_acceptance_criteria_v2([passing], runner=runner)
    assert verdicts[0].status == "pass"
    assert verdicts[0].details["measured"] == 92.0
    assert verdicts[0].details["comparison"] == ">="
    assert verdicts[0].details["target"] == 90.0

    failing = AcceptanceCriterion(**{**base, "id": "AC-2"}, threshold=">= 95")
    verdicts = evaluate_acceptance_criteria_v2([failing], runner=runner)
    assert verdicts[0].status == "fail"
    assert verdicts[0].details["measured"] == 92.0
    assert "92.0" in verdicts[0].message


def test_metric_number_kind_parses_last_number_generic() -> None:
    """number kind (any non-coverage/lint metric name): parse last number, compare."""
    base = {
        "id": "AC-1",
        "description": "latency goal",
        "verification_type": "metric",
        "verification_cmd": "python bench.py",
        "metric": "latency_p95_ms",
    }

    def runner(c: AcceptanceCriterion) -> CommandRunResult:
        return CommandRunResult(returncode=0, stdout="p95 latency: 123.4")

    passing = AcceptanceCriterion(**base, threshold="<= 200")
    verdicts = evaluate_acceptance_criteria_v2([passing], runner=runner)
    assert verdicts[0].status == "pass"
    assert verdicts[0].details["metric_kind"] == "number"
    assert verdicts[0].details["measured"] == 123.4

    failing = AcceptanceCriterion(**{**base, "id": "AC-2"}, threshold="<= 100")
    verdicts = evaluate_acceptance_criteria_v2([failing], runner=runner)
    assert verdicts[0].status == "fail"

    # Bare-number threshold defaults to ">=" (documented in the schema).
    bare = AcceptanceCriterion(**{**base, "id": "AC-3"}, threshold="100")
    verdicts = evaluate_acceptance_criteria_v2([bare], runner=runner)
    assert verdicts[0].status == "pass"
    assert verdicts[0].details["comparison"] == ">="


def test_metric_runner_errors_produce_explicit_fail_never_skip() -> None:
    """S-5: unparsable output / unparsable threshold / runner error → fail, never skip."""
    base = {
        "id": "AC-1",
        "description": "coverage floor",
        "verification_type": "metric",
        "verification_cmd": "pytest --cov",
        "metric": "coverage",
        "threshold": ">= 80",
    }

    # (a) No parsable percentage in the output.
    no_pct = evaluate_acceptance_criteria_v2(
        [AcceptanceCriterion(**base)],
        runner=lambda c: CommandRunResult(returncode=0, stdout="no totals here"),
    )
    assert no_pct[0].status == "fail"
    assert "no parsable percentage" in no_pct[0].message

    # (b) Runner-level error (the SubprocessError path renders as
    # returncode=2 with empty stdout per _default_command_runner).
    runner_err = evaluate_acceptance_criteria_v2(
        [AcceptanceCriterion(**base)],
        runner=lambda c: CommandRunResult(returncode=2, stderr="TimeoutExpired: 900s"),
    )
    assert runner_err[0].status == "fail"
    assert runner_err[0].details["returncode"] == 2

    # (c) Unparsable threshold expression.
    bad_threshold = evaluate_acceptance_criteria_v2(
        [AcceptanceCriterion(**{**base, "threshold": "at least eighty"})],
        runner=lambda c: CommandRunResult(returncode=0, stdout="TOTAL 10 1 90%"),
    )
    assert bad_threshold[0].status == "fail"
    assert "not a parsable" in bad_threshold[0].message


def test_metric_without_cmd_keeps_legacy_skip_and_manual_stays_skip() -> None:
    """Backward-compat boundary: cmd-less metric → legacy skip verdict; manual → skip.

    The pre-v14.4.0 skip message/details are preserved byte-identically
    for metric entries WITHOUT a verification_cmd (caller-driven
    evaluation), and ``manual`` keeps "manual review required".
    """
    legacy_metric = AcceptanceCriterion(
        id="AC-1",
        description="latency goal",
        verification_type="metric",
        metric="latency_p95_ms",
        threshold="<= 100",
    )
    verdicts = evaluate_acceptance_criteria_v2([legacy_metric])
    assert verdicts[0].status == "skip"
    assert verdicts[0].message == (
        "metric 'latency_p95_ms' requires external evaluator (threshold='<= 100')"
    )
    assert verdicts[0].details == {
        "verification_type": "metric",
        "metric": "latency_p95_ms",
        "threshold": "<= 100",
    }

    manual = AcceptanceCriterion(id="AC-2", description="human review", verification_type="manual")
    verdicts = evaluate_acceptance_criteria_v2([manual])
    assert verdicts[0].status == "skip"
    assert verdicts[0].message == "manual review required"


def test_metric_default_runner_executes_real_command() -> None:
    """Real subprocess execution path (acceptance criterion 2: real commands).

    Bounded by the existing ``_default_command_runner`` 900s timeout
    pattern; uses POSIX-safe echo / exit builtins so the test stays fast.
    """
    coverage = AcceptanceCriterion(
        id="AC-1",
        description="coverage floor",
        verification_type="metric",
        verification_cmd='echo "TOTAL 120 10 92%"',
        metric="coverage",
        threshold=">= 90",
    )
    lint_fail = AcceptanceCriterion(
        id="AC-2",
        description="lint clean",
        verification_type="metric",
        verification_cmd="exit 3",
        metric="lint",
    )
    verdicts = evaluate_acceptance_criteria_v2([coverage, lint_fail])
    assert verdicts[0].status == "pass"
    assert verdicts[0].details["measured"] == 92.0
    assert verdicts[1].status == "fail"
    assert verdicts[1].details["returncode"] == 3


# ── Item 3 — legibility opt-in weight ───────────────────────────────────


@pytest.fixture
def legible_file(tmp_path: Path) -> Path:
    path = tmp_path / "wellnamed.py"
    path.write_text(
        textwrap.dedent(
            '''\
            """Small, well-named module used by the legibility opt-in test."""


            def compute_total_price(unit_price: float, quantity: int) -> float:
                """Multiply unit price by quantity — kept trivially simple."""
                return unit_price * quantity
            '''
        ),
        encoding="utf-8",
    )
    return path


def test_legibility_weight_override_shifts_composite_as_expected(legible_file: Path) -> None:
    """``replace(STANDARD, legibility_weight=0.1)`` shifts the composite by 0.1×(mean−50).

    The composite scorer already supports nonzero weight — the override
    knob is a frozen-dataclass ``dataclasses.replace`` per
    ``references/decomposition-gate.md`` §5.6 (v14.4.0 opt-in surface).
    Also pins the v15.0.0 G-038 flip-6 profile DEFAULTS: STANDARD
    graduated 0.0 → 0.05 (matching STRICT/AUDIT); RELAXED stays 0.0.
    The weight-0.0 baseline below doubles as the documented flip-6
    opt-out path (``replace(STANDARD, legibility_weight=0.0)``).
    """
    # v15.0.0 default pins — STANDARD now scores legibility in by default.
    assert STANDARD.legibility_weight == pytest.approx(0.05)
    assert RELAXED.legibility_weight == 0.0
    assert STRICT.legibility_weight == pytest.approx(0.05)
    assert AUDIT.legibility_weight == pytest.approx(0.05)

    scorer = LegibilityScorer()
    gi = _pass_gate_input()
    history = [_round(1, 88.0)]

    # Flip-6 OPT-OUT: weight 0.0 via replace → reported but never scored in.
    baseline = evaluate_gate(
        gi,
        replace(STANDARD, legibility_weight=0.0),
        round_num=2,
        history=history,
        legibility_scorer=scorer,
        legibility_files=[str(legible_file)],
    )
    assert baseline.details["legibility"]["weight"] == 0.0
    assert baseline.details["legibility"]["composite_delta"] == 0.0

    override_profile = replace(STANDARD, legibility_weight=0.1)
    overridden = evaluate_gate(
        gi,
        override_profile,
        round_num=2,
        history=history,
        legibility_scorer=scorer,
        legibility_files=[str(legible_file)],
    )
    leg = overridden.details["legibility"]
    assert leg["weight"] == pytest.approx(0.1)
    mean_score = leg["mean_score"]
    expected_delta = round(0.1 * (mean_score - 50.0), 4)
    assert leg["composite_delta"] == pytest.approx(expected_delta)
    expected_composite = max(0.0, min(100.0, round(baseline.composite_score + expected_delta, 4)))
    assert overridden.composite_score == pytest.approx(expected_composite), (
        "legibility_weight=0.1 override did not shift the composite by "
        "weight × (mean_score − 50) relative to the weight-0 baseline"
    )
