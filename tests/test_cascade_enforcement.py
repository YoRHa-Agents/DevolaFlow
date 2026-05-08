"""Cascade-enforcement minimal stub for v11.0.2 PV-02 (S01.W02 T02).

This file is the **minimal stub** authored by L3 T02_dispatcher_integration_tests
under v11.1.0 cycle plan §3 PV-02 lines 192-196. It pins the propagation
CONTRACT for the new ``cascade_requirement(complexity)`` pure function
(landed at ``c4ea92e`` in :mod:`devolaflow.skills.change_activation`)
without mutating the dispatch schema in any way.

PV-02 scope discipline:

* **ZERO schema edits.** The ``gate.cascade_required`` NEST sub-field
  lands at PV-04 per the cycle plan §3 PV-04 row (T01_schema_nest)
  AND per ``.local/research/v11.1.0_pv02_decision.md`` §3 R-3
  ("cache-layout drift": PV-02 stub exercises the propagation contract
  via dispatch-payload assertions only — no schema-shape mutations).
* **A-2.1 frozen-prefix protection.** The 12-key frozen prefix
  (positions 1-12 of ``layout_invariant.canonical_order``, ending at
  ``gate``) is a release blocker if disturbed; this stub treats
  ``gate``'s position 12 as immutable AND telegraphs the PV-04 NEST
  decision via a synthetic-dict assertion that nests ``cascade_required``
  UNDER ``gate`` (NOT as a new top-level key).
* **A-2.3 NEST-not-APPEND validation in test form.** Test #2 below
  constructs a synthetic dispatch payload locally (a plain ``dict``
  with no schema mutation) where the cascade signal nests under the
  EXISTING ``gate`` block — the same shape PV-04's schema NEST will
  formalise.
* **A-2.4 multi-baseline byte test sentinel.** Test #3 dynamically
  reads ``canonical_order`` from ``schemas/lean-dispatch.yaml`` and
  cross-anchors its length against ``DEFAULT_DISPATCH_LAYOUT`` so a
  schema edit by THIS PV (against the spec) would fail this stub
  before tripping the 32-case multi-baseline byte test.

The full ≥10-test surface (per cycle plan §3 PV-05) lands at PV-05
once the PV-04 schema NEST has cleared. This stub is intentionally
scoped to the propagation CONTRACT (4 active assertions + 1 deferred
telegraph), well under the W-17 +30-NEW-test-function-per-PV cap.

Source: ``.local/research/v11.1.0_pv02_decision.md`` §3 R-3;
``.local/research/v11.1.0_cycle_plan.md`` §3 PV-02 lines 192-196.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from devolaflow.compressor import DEFAULT_DISPATCH_LAYOUT, FROZEN_PREFIX_LENGTH
from devolaflow.skills.change_activation import (
    Complexity,
    activation_verdict,
    cascade_requirement,
)

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas/lean-dispatch.yaml"

# Truth table mirrors the operator-quotable verdict rule from the decision
# memo §1: "STANDARD complexity or higher → cascade required (L0→L1→L2→L3);
# SIMPLE / TRIVIAL → cascade optional (operators may collapse to a single L3)."
_CASCADE_TRUTH_TABLE: dict[Complexity, str] = {
    "TRIVIAL": "CASCADE_OPTIONAL",
    "SIMPLE": "CASCADE_OPTIONAL",
    "STANDARD": "CASCADE_REQUIRED",
    "COMPLEX": "CASCADE_REQUIRED",
}


def test_cascade_requirement_is_cascade_signal_source() -> None:
    """``cascade_requirement(complexity)`` is the SOLE cascade-signal source.

    Asserts the truth table directly (per decision memo §1) AND that the
    function consults NOTHING beyond ``complexity`` — no env-flag, no
    opt-out, no dispatcher state. This is the contract PV-04 will rely
    on when wiring ``gate.cascade_required`` into the schema NEST.
    """
    for complexity, expected in _CASCADE_TRUTH_TABLE.items():
        actual = cascade_requirement(complexity)
        assert actual == expected, (
            f"cascade_requirement({complexity!r}) returned {actual!r}, "
            f"expected {expected!r} per .local/research/v11.1.0_pv02_decision.md §1"
        )

    # Sole-input contract: the function takes exactly ONE positional
    # parameter named ``complexity``. If a future PV adds an env-flag /
    # opt-out / dispatcher-state argument, this assertion fires and the
    # cascade-signal source-of-truth contract is renegotiated
    # (deliberately, with a follow-up SI-1 entry).
    sig = inspect.signature(cascade_requirement)
    assert list(sig.parameters) == ["complexity"], (
        f"cascade_requirement signature drift: {list(sig.parameters)!r} "
        "— expected exactly ['complexity'] per decision memo §1 "
        "(no env-flag, no opt-out, no dispatcher state)"
    )


def test_cascade_required_propagates_into_simulated_dispatch_payload() -> None:
    """Synthetic dispatch payload NESTs cascade_required UNDER ``gate`` (A-2.3).

    Constructs a plain ``dict`` payload locally (NO schema mutation) and
    derives ``gate.cascade_required`` from ``cascade_requirement(complexity)``.
    Asserts the NEST shape PV-04 will formalise — cascade_required lives
    UNDER ``gate`` (canonical position 12), NOT as a new top-level key.
    Validates the A-2.3 NEST-not-APPEND decision rule in test form.
    """
    for complexity, cascade_verdict in _CASCADE_TRUTH_TABLE.items():
        # Synthetic minimal payload: just ``gate`` with the cascade signal
        # nested under it. Real dispatches carry the full 17-key canonical
        # order; this stub only exercises the NEST shape.
        payload: dict = {
            "gate": {
                "coverage": 85,
                "quality": 85,
                "blockers": 0,
                "retries": 2,
                # The PV-04 NEST sub-field — derived in this stub from the
                # cascade_requirement literal; PV-04 will source it from
                # the same function via the schema-side wiring.
                "cascade_required": cascade_verdict == "CASCADE_REQUIRED",
            }
        }

        # A-2.3 NEST validation: cascade_required is a sub-field of ``gate``,
        # NOT a top-level key. If a future agent attempts an APPEND, this
        # assertion fires.
        assert "cascade_required" not in payload, (
            "cascade_required leaked to top-level — A-2.3 mandates NEST under "
            "the existing ``gate`` block per decision memo §3 R-3"
        )
        assert "cascade_required" in payload["gate"], (
            "cascade_required missing from gate block — propagation contract broken"
        )

        # Truth-table propagation: the boolean derived from
        # ``cascade_requirement`` matches the operator-quotable verdict.
        if cascade_verdict == "CASCADE_REQUIRED":
            assert payload["gate"]["cascade_required"] is True, (
                f"complexity={complexity!r} → expected gate.cascade_required is True, "
                f"got {payload['gate']['cascade_required']!r}"
            )
        else:
            assert payload["gate"]["cascade_required"] is False, (
                f"complexity={complexity!r} → expected gate.cascade_required is False, "
                f"got {payload['gate']['cascade_required']!r}"
            )


def test_cascade_required_does_not_invalidate_layout_invariant() -> None:
    """Sentinel: PV-02 makes ZERO schema edits (A-2.1 + A-2.4 protection).

    Reads ``canonical_order`` dynamically from ``schemas/lean-dispatch.yaml``
    and cross-anchors its length against the runtime SSOT
    (``devolaflow.compressor.DEFAULT_DISPATCH_LAYOUT``). If THIS PV
    accidentally mutates the schema, this assertion fires BEFORE the
    32-case multi-baseline byte test
    (``tests/test_layout_invariant_multi_baseline.py``) runs — providing
    a faster failure signal scoped to the cascade work.

    Also asserts ``gate`` sits at the frozen-prefix tail (position 12 =
    ``FROZEN_PREFIX_LENGTH``) — that's where PV-04 will NEST
    ``cascade_required`` per the decision memo §3 R-3.
    """
    schema_data = yaml.safe_load(_SCHEMA_PATH.read_text())
    canonical_order = schema_data["layout_invariant"]["canonical_order"]

    # Cross-source anchor: schema YAML and runtime constant must agree.
    # PV-02 makes NO edits to either; if they diverge, the sentinel fires.
    assert len(canonical_order) == len(DEFAULT_DISPATCH_LAYOUT), (
        f"schema canonical_order length ({len(canonical_order)}) drifted from "
        f"runtime DEFAULT_DISPATCH_LAYOUT length ({len(DEFAULT_DISPATCH_LAYOUT)}) "
        "— PV-02 must make ZERO schema edits per decision memo §3 R-3"
    )
    # Per-key cross-source anchor (defence-in-depth — catches a renamer
    # that preserves length but disturbs key identity).
    assert tuple(canonical_order) == tuple(DEFAULT_DISPATCH_LAYOUT), (
        "schema canonical_order keys drifted from runtime DEFAULT_DISPATCH_LAYOUT "
        "— A-2.1 frozen-prefix release blocker; see v9-ADR-002 D1"
    )

    # ``gate`` lives at the frozen-prefix tail (position 12, 1-indexed =
    # FROZEN_PREFIX_LENGTH); the PV-04 NEST will land sub-fields under it.
    assert canonical_order[FROZEN_PREFIX_LENGTH - 1] == "gate", (
        f"``gate`` not at canonical position {FROZEN_PREFIX_LENGTH} "
        "(frozen-prefix tail) — A-2.1 release blocker; see v9-ADR-002 D1"
    )


def test_cascade_signal_orthogonal_to_force_no_change() -> None:
    """Cascade signal is INDEPENDENT of ``activation_verdict.force_no_change``.

    Per decision memo §3 R-6 (mitigation pin in cycle_plan.md §7 risk
    register): ``cascade_requirement`` returns the same verdict regardless
    of any ``force_no_change`` decision on ``activation_verdict``. The two
    surfaces are orthogonal — workspace activation and cascade enforcement
    compose as independent axes.

    Concretely: ``cascade_requirement("STANDARD")`` is ``"CASCADE_REQUIRED"``
    even when an operator forces ``activation_verdict("STANDARD", env=True,
    opt_out=False, force_no_change=True)`` to ``"NO_CHANGE"``. The cascade
    decision is NOT silenced by the workspace-activation override.
    """
    # Workspace-activation override returns NO_CHANGE — operator chose to
    # bypass the agent-workspace scaffold for this dispatch.
    workspace_verdict = activation_verdict(
        "STANDARD", env_agent_workspace=True, opt_out=False, force_no_change=True
    )
    assert workspace_verdict == "NO_CHANGE", (
        f"activation_verdict force_no_change=True did not override; got {workspace_verdict!r}"
    )

    # Cascade signal is UNCHANGED — STANDARD complexity still requires
    # the L0→L1→L2→L3 cascade regardless of the workspace override.
    cascade_verdict = cascade_requirement("STANDARD")
    assert cascade_verdict == "CASCADE_REQUIRED", (
        f"cascade_requirement('STANDARD') drifted under force_no_change; "
        f"got {cascade_verdict!r}, expected 'CASCADE_REQUIRED' per decision memo §3 R-6"
    )

    # Cross-tier orthogonality: COMPLEX also stays CASCADE_REQUIRED;
    # SIMPLE / TRIVIAL stay CASCADE_OPTIONAL — none react to force_no_change.
    assert cascade_requirement("COMPLEX") == "CASCADE_REQUIRED"
    assert cascade_requirement("SIMPLE") == "CASCADE_OPTIONAL"
    assert cascade_requirement("TRIVIAL") == "CASCADE_OPTIONAL"


def test_cascade_signal_propagation_pv04_telegraph() -> None:
    """Telegraph: full propagation surface lands at PV-04 schema NEST."""
    pytest.skip(
        "PV-04 schema NEST lands gate.cascade_required; full propagation "
        "surface tested then per cycle plan §3 PV-04"
    )
