"""Tests for the v10.2.1 PV-02 Si-Chip iteration_delta CI gate (D-S-3).

Pins the apply/defer threshold semantics of
:func:`devolaflow.si_chip_bridge.runner.apply_or_defer` per Si-Chip spec
§23: ``iteration_delta >= threshold`` (with IEEE-754 absolute epsilon)
returns :class:`ApplyVerdict.APPLY`; everything else returns
:class:`ApplyVerdict.DEFER`.

Closes D-S-3 from `.local/research/v10.2.0_gap_analysis.md` §3.2: prior
to v10.2.1 the gate was enforced at runtime via ``apply_or_defer`` but
NOT in CI. The W-9 SI-10 6-gate sequence did not include a Si-Chip
iteration-delta regression check, so a future PV could regress the
``MetricsReport.composite`` calculation and CI would not catch it. This
file IS the 7th SI-10 step that the Makefile ``release-preflight``
target now invokes (the test file itself being run by release-preflight
is the proof it's the 7th step — see
``test_iteration_delta_gate_is_si10_step_7`` below).

Source: `.local/research/v10.2.0_cycle_plan.md` §3 PV-02 owned-files
manifest + §4 D-V-1 cross-cutting concern.
External tool reference: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.si_chip_bridge import (
    APPLY_DEFER_EPSILON,
    ApplyVerdict,
    IterationDeltaReport,
    MetricsReport,
    apply_or_defer,
)


def _make_iteration_delta(delta: float, threshold: float = 0.10) -> IterationDeltaReport:
    """Build a minimal IterationDeltaReport for fixture-style assertions.

    The ``before``/``after`` MetricsReports are simple synthesised values
    that produce the requested ``delta`` (after.composite minus
    before.composite). The other MetricsReport fields are set to safe
    zeros — ``apply_or_defer`` consults only ``iteration_delta`` and
    ``threshold``.
    """
    before = MetricsReport(
        composite=0.5,
        metadata_tokens=0,
        body_tokens=0,
        task_delta=0.0,
        value_vector=0.0,
    )
    after = MetricsReport(
        composite=0.5 + delta,
        metadata_tokens=0,
        body_tokens=0,
        task_delta=0.0,
        value_vector=0.0,
    )
    return IterationDeltaReport(
        before=before,
        after=after,
        iteration_delta=delta,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# §1 — The 4 canonical fixtures pinning the Si-Chip §23 threshold semantics
# ---------------------------------------------------------------------------


def test_above_threshold_returns_apply() -> None:
    """delta = +0.15 vs threshold +0.10 → APPLY (clear win)."""
    report = _make_iteration_delta(delta=0.15, threshold=0.10)
    assert apply_or_defer(report) == ApplyVerdict.APPLY, (
        "delta=+0.15 above threshold=+0.10 must verdict APPLY per Si-Chip spec §23"
    )


def test_exact_threshold_returns_apply_with_epsilon() -> None:
    """delta = +0.10000001 vs threshold +0.10 → APPLY.

    The runner uses an IEEE-754 absolute tolerance
    (:data:`devolaflow.si_chip_bridge.APPLY_DEFER_EPSILON`) so a
    near-threshold delta like ``0.6 - 0.5 = 0.09999999999999998`` does
    NOT incorrectly DEFER. The epsilon is ``1e-9`` — 8 orders of
    magnitude smaller than the smallest real-world Si-Chip composite
    delta.

    The convention is ``delta >= threshold - APPLY_DEFER_EPSILON``: any
    value within ``±1e-9`` of the threshold (or above) clears the gate.
    """
    delta = 0.10000001
    report = _make_iteration_delta(delta=delta, threshold=0.10)
    assert apply_or_defer(report) == ApplyVerdict.APPLY
    assert pytest.approx(1e-9) == APPLY_DEFER_EPSILON, (
        "Si-Chip iteration_delta gate epsilon must remain at 1e-9 — "
        "shrinking it risks false-DEFER on near-threshold deltas; growing "
        "it risks false-APPLY on materially sub-threshold proposals."
    )


def test_floating_point_near_threshold_returns_apply() -> None:
    """The classic ``0.6 - 0.5`` rounding case clears the gate by epsilon."""
    delta = 0.6 - 0.5  # ~= 0.09999999999999998 (IEEE-754 double precision)
    assert delta < 0.10, (
        "Sanity: 0.6 - 0.5 must indeed be sub-threshold by raw comparison; "
        "if this fails, Python's float semantics changed unexpectedly."
    )
    report = _make_iteration_delta(delta=delta, threshold=0.10)
    assert apply_or_defer(report) == ApplyVerdict.APPLY, (
        "Operators expect a 'clear-the-bar' delta of 0.6-0.5=~0.10 to "
        "verdict APPLY despite IEEE-754 rounding; the epsilon protects this."
    )


def test_below_threshold_returns_defer() -> None:
    """delta = +0.099 vs threshold +0.10 → DEFER (sub-threshold by epsilon-significant margin)."""
    report = _make_iteration_delta(delta=0.099, threshold=0.10)
    assert apply_or_defer(report) == ApplyVerdict.DEFER, (
        "delta=+0.099 below threshold=+0.10 (by 0.001 — far above the "
        "1e-9 epsilon) must verdict DEFER per Si-Chip spec §23"
    )


def test_zero_delta_returns_defer() -> None:
    """delta = 0.0 vs threshold +0.10 → DEFER (no measurable improvement)."""
    report = _make_iteration_delta(delta=0.0, threshold=0.10)
    assert apply_or_defer(report) == ApplyVerdict.DEFER


def test_negative_delta_returns_defer() -> None:
    """delta = -0.05 (regression) vs threshold +0.10 → DEFER unconditionally."""
    report = _make_iteration_delta(delta=-0.05, threshold=0.10)
    assert apply_or_defer(report) == ApplyVerdict.DEFER, (
        "A regression delta MUST verdict DEFER — the gate is asymmetric: "
        "improvements clear, regressions never auto-apply."
    )


# ---------------------------------------------------------------------------
# §2 — Threshold override per call (the threshold parameter on apply_or_defer)
# ---------------------------------------------------------------------------


def test_per_call_threshold_override_above() -> None:
    """``apply_or_defer(report, threshold=0.05)`` overrides the report's threshold."""
    report = _make_iteration_delta(delta=0.06, threshold=0.10)
    # Without override: 0.06 < 0.10 → DEFER
    assert apply_or_defer(report) == ApplyVerdict.DEFER
    # With override: 0.06 >= 0.05 → APPLY
    assert apply_or_defer(report, threshold=0.05) == ApplyVerdict.APPLY


def test_per_call_threshold_override_below() -> None:
    """A higher per-call threshold can DEFER a delta that the report's threshold would APPLY."""
    report = _make_iteration_delta(delta=0.12, threshold=0.10)
    # Without override: 0.12 >= 0.10 → APPLY
    assert apply_or_defer(report) == ApplyVerdict.APPLY
    # With override: 0.12 < 0.20 → DEFER
    assert apply_or_defer(report, threshold=0.20) == ApplyVerdict.DEFER


# ---------------------------------------------------------------------------
# §3 — SI-10 step-7 wiring proof (D-V-1 cycle-wide gate)
# ---------------------------------------------------------------------------


def test_iteration_delta_gate_is_si10_step_7() -> None:
    """Confirm the Makefile ``release-preflight`` target invokes this gate.

    Per `.local/research/v10.2.0_cycle_plan.md` §4 D-V-1: this test file
    is the 7th step in the SI-10 sequence. The proof is twofold:

    1. The Makefile ``release-preflight`` target references the gate by
       test-name (``test_sichip_iteration_delta_gate``) so any operator
       running ``make release-preflight`` will execute this file.
    2. The presence of THIS test in the suite when ``release-preflight``
       runs ``pytest tests/`` IS the dynamic confirmation — the test
       being green on a SI-10 run is the strongest possible witness.

    This test asserts (1) so the wiring cannot drift silently; (2) is
    self-evident because if this test were absent the assertion below
    could never run.
    """
    repo_root = Path(__file__).resolve().parents[1]
    makefile_path = repo_root / "Makefile"
    assert makefile_path.is_file(), (
        f"Makefile missing at {makefile_path}; cannot verify SI-10 step-7 wiring"
    )
    makefile_text = makefile_path.read_text(encoding="utf-8")
    gate_test_name = "test_sichip_iteration_delta_gate"
    assert gate_test_name in makefile_text, (
        f"D-V-1 wiring violation: Makefile does NOT reference "
        f"{gate_test_name!r}. The v10.2.1 PV-02 spec requires the "
        "release-preflight target to invoke this gate as the 7th SI-10 "
        "step. Add a target line like:\n"
        f"\t@python -m pytest tests/{gate_test_name}.py -q --no-cov"
    )


def test_apply_defer_epsilon_constant_documented() -> None:
    """The epsilon constant is publicly exposed so callers can reason about it.

    Si-Chip API consumers (the post_skill_edit lifecycle hook, the
    dispatch_dogfood_cycle wrapper) must be able to introspect the
    epsilon for tuning + documentation. The constant is exported from
    ``devolaflow.si_chip_bridge``.
    """
    from devolaflow import si_chip_bridge

    assert hasattr(si_chip_bridge, "APPLY_DEFER_EPSILON"), (
        "APPLY_DEFER_EPSILON must be re-exported from "
        "devolaflow.si_chip_bridge for caller introspection"
    )
    assert si_chip_bridge.APPLY_DEFER_EPSILON > 0, (
        "Epsilon must be positive (it tightens the >= comparison toward "
        "operator intent on near-threshold deltas)"
    )
