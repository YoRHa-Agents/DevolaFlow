"""Cascade-compliance tests (v11.1.0 PV-02 minimal stub).

The full ≥10-test surface lands at PV-05 G-TEST-1; PV-02 ships only the
minimal stub that pins:
1. cascade_requirement() integrates with the classifier output;
2. the Literal CascadeRequirement type is exported from
   devolaflow.skills.change_activation;
3. the cascade-required signal is propagatable into a dict shaped like
   a dispatch payload (the actual dispatch-payload integration lands
   at PV-04 G-PLAN-1 NEST gate.cascade_required).

Source: .local/research/v11.1.0_cycle_plan.md §3 PV-02 W02.T02.
"""

from __future__ import annotations

from devolaflow.skills.change_activation import (
    CascadeRequirement,
    cascade_requirement,
    classify_complexity,
)


def test_cascade_requirement_propagates_from_classifier_complex() -> None:
    """COMPLEX classifier output → cascade_requirement → CASCADE_REQUIRED."""
    complexity = classify_complexity(files_count=15, loc_estimate=500)
    assert complexity == "COMPLEX"
    assert cascade_requirement(complexity) == "CASCADE_REQUIRED"


def test_cascade_requirement_propagates_from_classifier_simple() -> None:
    """SIMPLE classifier output → cascade_requirement → CASCADE_OPTIONAL."""
    complexity = classify_complexity(files_count=2, loc_estimate=50)
    assert complexity == "SIMPLE"
    assert cascade_requirement(complexity) == "CASCADE_OPTIONAL"


def test_cascade_required_signal_fits_in_dispatch_payload_shape() -> None:
    """PV-04 NEST hook stub: gate.cascade_required is a dict-shapeable signal.

    The actual schema NEST under existing `gate` block lands at PV-04
    G-PLAN-1; this test pins that the v11.0.2 surface IS a string we can
    embed in a dict literal (no Enum encoding traps).
    """
    requirement: CascadeRequirement = cascade_requirement("STANDARD")
    payload = {"gate": {"cascade_required": requirement == "CASCADE_REQUIRED"}}
    assert payload["gate"]["cascade_required"] is True
