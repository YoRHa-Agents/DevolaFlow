"""v15.0.0 T4 — L0-side artifact scoring from L2 evidence blocks.

Pins ``src/devolaflow/gate/artifact_score.py`` — the SCORING PHASE of
the v15-ADR-007 evidence-vs-scoring doctrine split: L2 emits evidence
only (v14.3.0 ``self_check`` / ``ac_results`` / ``diff_stats`` blocks
per ``schemas/lean-report.yaml``); L0 computes the artifact quality
score FROM the evidence per the ``references/artifact-quality.md`` §2
rubric. The doctrine guards (forbidden ``quality_score`` /``quality``
input keys → :class:`EvidenceDoctrineError`) and the unscored-
renormalization honesty rule (absent evidence is EXCLUDED, never
fabricated) are the release-critical contracts.

W-17 note: this module adds 10 NEW test functions (at the per-task cap
prescribed for v15.0.0-T4: ≤ 10), plus 3 R1 gate-wiring tests
(v15.0.0-R2-T1) pinning the ``evaluate_gate(artifact_evidence=...)``
opt-in dimension: absence-safety, weight-gated composite shift, and
S-5 ``EvidenceDoctrineError`` propagation.
"""

from __future__ import annotations

import pytest

from devolaflow.gate.artifact_score import (
    UNSCORED,
    ArtifactScore,
    EvidenceDoctrineError,
    score_artifact_evidence,
)
from devolaflow.gate.models import CheckResult, ConvergenceRound, GateInput
from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT
from devolaflow.gate.scorer import composite_score, evaluate_gate


def _full_report() -> dict:
    """A lean StatusReport with all four evidence blocks (lean_example shape)."""
    return {
        "hdr": {"id": "r-1", "dispatch": "d-1", "task": "T04", "layer": "task"},
        "state": {"s": "completed", "pct": 100, "elapsed": 2700},
        "metrics": {"pass": 12, "fail": 0, "cov": 94.2, "gate_input_score": 92},
        "self_check": {
            "plan_artifact": "inline: auth.ts middleware → index.ts export → tests",
            "goal_anchor": "JWT auth middleware — validate token, attach req.user",
            "simplicity": "none",
            "conflicts": [],
            "conventions": [],
        },
        "ac_results": [
            {"id": "AC-1", "verdict": "pass", "cmd_digest": "jest 12 passed, 0 failed → exit 0"},
            {"id": "AC-2", "verdict": "pass", "cmd_digest": "coverage 94.2% ≥ 90% threshold"},
        ],
        "diff_stats": {"files": 3, "insertions": 184, "deletions": 6},
    }


def test_full_evidence_report_scores_all_four_dimensions() -> None:
    result = score_artifact_evidence(_full_report(), owned_files_count=4)
    assert set(result.dimensions) == {
        "correctness",
        "minimal_diff",
        "test_evidence",
        "convention_adherence",
    }
    for name, dim in result.dimensions.items():
        assert dim.is_scored, f"{name} should be scored on full evidence"
        assert dim.evidence_refs, f"{name} must carry verbatim evidence refs"
        assert dim.score == pytest.approx(100.0)
    assert result.composite == pytest.approx(100.0)
    assert result.evidence_coverage == pytest.approx(1.0)


def test_partial_evidence_renormalizes_composite_over_scored_dimensions() -> None:
    report = {
        "ac_results": [
            {"id": "AC-1", "verdict": "pass", "cmd_digest": "ok"},
            {"id": "AC-2", "verdict": "fail", "cmd_digest": "AssertionError"},
        ],
        "metrics": {"pass": 8, "fail": 2, "cov": 80.0},
    }
    result = score_artifact_evidence(report)
    assert result.dimensions["correctness"].score == pytest.approx(50.0)
    # mean of pass-ratio 80.0 and coverage-at-floor 100.0
    assert result.dimensions["test_evidence"].score == pytest.approx(90.0)
    assert result.dimensions["minimal_diff"].score is None
    assert result.dimensions["minimal_diff"].render() == UNSCORED
    assert result.dimensions["convention_adherence"].score is None
    # equal weights renormalized over the 2 scored dimensions: (50 + 90) / 2
    assert result.composite == pytest.approx(70.0)
    assert result.evidence_coverage == pytest.approx(0.5)


def test_empty_evidence_is_all_unscored_with_none_composite() -> None:
    result = score_artifact_evidence({})
    assert all(dim.score is None for dim in result.dimensions.values())
    assert all(dim.render() == UNSCORED for dim in result.dimensions.values())
    assert result.composite is None
    assert result.evidence_coverage == pytest.approx(0.0)
    assert result.to_gate_input() == {"dimensions": {}, "weights": {}}
    # metrics present but with no usable sub-signal is still unscored
    no_signal = score_artifact_evidence({"metrics": {"findings": {"B": 0, "m": 2}}})
    assert no_signal.dimensions["test_evidence"].score is None
    # non-dict input is a type error, not a silent zero (S-5)
    with pytest.raises(TypeError):
        score_artifact_evidence(["not", "a", "report"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "report",
    [
        {"quality_score": 92},
        {"quality": 92},
        {"metrics": {"quality_score": 92, "cov": 90.0}},
        {"metrics": {"quality": 92}},
        {"self_check": {"quality_score": 9, "plan_artifact": "x"}},
        {"self_check": {"quality": "9/10"}},
    ],
    ids=[
        "top-quality_score",
        "top-quality",
        "metrics-quality_score",
        "metrics-quality",
        "self_check-quality_score",
        "self_check-quality",
    ],
)
def test_forbidden_quality_score_in_input_raises_doctrine_error(report: dict) -> None:
    with pytest.raises(EvidenceDoctrineError):
        score_artifact_evidence(report)


def test_legitimate_evidence_keys_do_not_trip_the_doctrine_guard() -> None:
    """``metrics.gate_input_score`` (G-013 rename) and predecessor-carried
    historical scores are legitimate — hook-parity exemptions."""
    report = {
        "metrics": {"gate_input_score": 92, "cov": 90.0},
        "pred": [{"quality_score": 88}],
    }
    result = score_artifact_evidence(report)
    assert result.dimensions["test_evidence"].is_scored


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        (["pass", "pass", "pass", "pass"], 100.0),
        (["pass", "pass", "pass", "fail"], 75.0),
        (["pass", "pass", "fail", "fail"], 50.0),
        (["pass", "pass", "skip", "skip"], 75.0),  # skip discounted at 0.5
        (["pass", "not_run"], 75.0),  # NOT_RUN is skip-tier per §5
    ],
)
def test_correctness_verdict_ratio_rules(verdicts: list[str], expected: float) -> None:
    rows = [{"id": f"AC-{i}", "verdict": v, "cmd_digest": "d"} for i, v in enumerate(verdicts)]
    result = score_artifact_evidence({"ac_results": rows})
    assert result.dimensions["correctness"].score == pytest.approx(expected)


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        ({"cov": 80.0}, 100.0),  # exactly at the S-3 floor
        ({"cov": 40.0}, 50.0),  # below floor scales proportionally
        ({"cov": 95.0}, 100.0),  # above floor capped — no bonus
        ({"pass": 9, "fail": 1}, 90.0),  # pass-ratio only
        ({"tests_passed": 9, "tests_failed": 1, "coverage_pct": 40.0}, 70.0),  # verbose keys
    ],
)
def test_test_evidence_coverage_floor_and_pass_ratio(metrics: dict, expected: float) -> None:
    result = score_artifact_evidence({"metrics": metrics})
    assert result.dimensions["test_evidence"].score == pytest.approx(expected)


@pytest.mark.parametrize(
    ("stats", "owned", "expected"),
    [
        ({"files": 3, "insertions": 294, "deletions": 6}, None, 100.0),  # at 300-line boundary
        ({"files": 3, "insertions": 500, "deletions": 100}, None, 50.0),  # 600 lines → 300/600
        ({"files": 12, "insertions": 100, "deletions": 0}, None, 50.0),  # 12 files vs budget 6
        ({"files": 4, "insertions": 100, "deletions": 0}, 2, 50.0),  # owned_files budget wins
        ({"files": 4, "insertions": 100, "deletions": 0}, 4, 100.0),
    ],
)
def test_minimal_diff_proportionality_boundaries(
    stats: dict, owned: int | None, expected: float
) -> None:
    result = score_artifact_evidence({"diff_stats": stats}, owned_files_count=owned)
    assert result.dimensions["minimal_diff"].score == pytest.approx(expected)


def test_self_check_completeness_gradations() -> None:
    full = {
        "plan_artifact": "tasks.md#T04",
        "goal_anchor": "goal restated",
        "simplicity": 0,  # declared-zero counts as declared
        "conflicts": [],
        "conventions": [],
    }

    def score_of(self_check: dict):
        return score_artifact_evidence({"self_check": self_check}).dimensions[
            "convention_adherence"
        ]

    assert score_of(full).score == pytest.approx(100.0)
    missing_goal = {k: v for k, v in full.items() if k != "goal_anchor"}
    assert score_of(missing_goal).score == pytest.approx(75.0)
    plan_only = {"plan_artifact": "tasks.md#T04"}
    assert score_of(plan_only).score == pytest.approx(25.0)
    assert score_artifact_evidence({}).dimensions["convention_adherence"].score is None


def test_to_gate_input_shape_feeds_gate_composite() -> None:
    report = {
        "ac_results": [{"id": "AC-1", "verdict": "fail", "cmd_digest": "boom"}],
        "metrics": {"pass": 10, "fail": 0, "cov": 90.0},
        "diff_stats": {"files": 2, "insertions": 50, "deletions": 5},
    }
    result = score_artifact_evidence(report, owned_files_count=2)
    assert isinstance(result, ArtifactScore)
    adapter = result.to_gate_input()
    assert set(adapter) == {"dimensions", "weights"}
    assert set(adapter["dimensions"]) == {"correctness", "test_evidence", "minimal_diff"}
    assert sum(adapter["weights"].values()) == pytest.approx(1.0)
    # the adapter reproduces the composite through the gate's own scorer
    # (abs tolerance covers the adapter's 4-decimal weight rounding)
    assert composite_score(**adapter) == pytest.approx(result.composite, abs=0.05)


# ─────────────────────────────────────────────────────────────────────────────
# v15.0.0 R1 (reinforcement round) — evaluate_gate artifact-evidence wiring.
# Mirrors the legibility opt-in precedent: weight-gated, absence-safe,
# EvidenceDoctrineError propagates (S-5).
# ─────────────────────────────────────────────────────────────────────────────


def _convergence_gate_args() -> dict:
    """A convergence-gate call that yields a numeric composite to shift."""
    gate_input = GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass", details={"coverage_pct": 90}),
        lint_status=CheckResult(status="pass"),
    )
    history = [
        ConvergenceRound(
            round_num=1,
            composite_score=80.0,
            blocker_count=0,
            critical_count=0,
            timestamp="t0",
        )
    ]
    return {
        "gate_input": gate_input,
        "round_num": 2,
        "history": history,
        "gate_type": "convergence",
    }


def test_evaluate_gate_without_artifact_evidence_is_byte_identical() -> None:
    """Absence-safe: ``artifact_evidence=None`` / ``[]`` reproduce the control verdict."""
    control = evaluate_gate(profile=STANDARD, **_convergence_gate_args())
    for absent in (None, []):
        verdict = evaluate_gate(
            profile=STANDARD, artifact_evidence=absent, **_convergence_gate_args()
        )
        assert verdict == control, (
            f"artifact_evidence={absent!r} must be byte-identical to the "
            "pre-wiring control (legibility-precedent absence safety)"
        )
        assert "artifact_evidence" not in verdict.details


def test_evaluate_gate_artifact_evidence_shifts_composite_by_profile_weight() -> None:
    """The evidence mean shifts the composite by ``weight * (mean - 50)``;
    weight 0.0 (RELAXED) reports without scoring; unscored reports are
    surfaced but excluded from the mean (never fabricated)."""
    full_pass = {
        "ac_results": [{"id": "AC-1", "verdict": "pass", "cmd_digest": "12 passed"}],
        "metrics": {"pass": 12, "fail": 0, "cov": 94.0},
    }
    no_evidence = {"hdr": {"id": "r-2"}}

    control = evaluate_gate(profile=STANDARD, **_convergence_gate_args())
    wired = evaluate_gate(
        profile=STANDARD,
        artifact_evidence=[full_pass, no_evidence],
        **_convergence_gate_args(),
    )
    block = wired.details["artifact_evidence"]
    # mean over the SCORED report only: 100.0 → delta = 0.05 * (100 - 50) = +2.5
    assert block["report_count"] == 2
    assert block["scored_count"] == 1
    assert block["mean_composite"] == pytest.approx(100.0)
    assert block["composite_delta"] == pytest.approx(2.5)
    assert wired.composite_score == pytest.approx(control.composite_score + 2.5)
    assert block["reports"][1]["composite"] is None  # surfaced, not fabricated

    # RELAXED weight 0.0: details attach, composite stays byte-stable.
    relaxed_control = evaluate_gate(profile=RELAXED, **_convergence_gate_args())
    relaxed = evaluate_gate(
        profile=RELAXED, artifact_evidence=[full_pass], **_convergence_gate_args()
    )
    assert relaxed.composite_score == pytest.approx(relaxed_control.composite_score)
    assert relaxed.details["artifact_evidence"]["composite_delta"] == 0.0

    # Profile defaults mirror the legibility precedent exactly.
    assert STRICT.artifact_evidence_weight == pytest.approx(0.05)
    assert STANDARD.artifact_evidence_weight == pytest.approx(0.05)
    assert AUDIT.artifact_evidence_weight == pytest.approx(0.05)
    assert RELAXED.artifact_evidence_weight == pytest.approx(0.0)


def test_evaluate_gate_propagates_evidence_doctrine_error() -> None:
    """A doctrine-violating report aborts the gate call (S-5 — no silent scoring)."""
    with pytest.raises(EvidenceDoctrineError):
        evaluate_gate(
            profile=STANDARD,
            artifact_evidence=[{"quality_score": 9.5}],
            **_convergence_gate_args(),
        )
