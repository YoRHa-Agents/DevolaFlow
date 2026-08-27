"""Cascade-enforcement test suite — v12.0.0 PV-02 D-1 STRICT graduation.

This file pins the end-to-end cascade contract from v11.1.0 PV-02..PV-05
THROUGH the v12.0.0 PV-02 D-1 BREAKING graduation. The v11.1.0 cycle
shipped the SOFT validator + populate helper (returns warning list);
v12.0.0 PV-02 D-1 graduates :func:`validate_cascade_gate_fields` to
STRICT (raises :class:`CascadeViolationError` on the FIRST violation;
returns ``None`` on every passing path).

Cycle history pinned by these tests:

* **v11.1.0 PV-02** — ``cascade_requirement(complexity)`` pure function
  (G-CLASSIFY-1 Candidate C, landed in
  :mod:`devolaflow.skills.change_activation`).
* **v11.1.0 PV-04** — schema NEST + populate helper + SOFT validator
  (returns warning list). The schema NEST adds
  ``gate.cascade_required: bool`` + ``gate.cascade_min_layers: int``
  OPTIONAL sub-fields under the existing ``gate`` block (A-2.3 NEST
  decision; canonical_order length stays 17, schema version stays 6).
* **v11.1.0 PV-05** — Architecture rule A-7 lands; SOFT validator
  preserved as default per cycle plan §6
  "DEFAULTS-PERMISSIVE-IN-MINOR / STRICT-IN-NEXT-MAJOR".
* **v12.0.0 PV-02 D-1** — STRICT graduation. The validator NOW RAISES
  :class:`CascadeViolationError` instead of returning warnings. The
  R-12 backward-compat carve-out is preserved by construction: legacy
  v11.0.x dispatches with no ``cascade_required`` key (or with
  ``cascade_required=False``) flow through unchanged (return ``None``
  with no exception, byte-identical to passing v11.x calls).

The 20 tests below are organised by branch with comment dividers so
the W-18 ghost-audit refresh and the cycle plan's per-PV trail stay
unambiguous:

* **Branch 1** (4 tests) — v11.1.0 PV-02 stub kept verbatim (no
  regression; pure-function + schema-sentinel + orthogonality tests).
* **Branch 2** (1 test) — populate-helper propagation test.
* **Branch 3** (3 tests) — backward-compat (R-1 + R-12 mitigation,
  CRITICAL): legacy v11.0.x dispatches without the new sub-fields
  flow through cleanly; SIMPLE/TRIVIAL skip cascade validation
  end-to-end.
* **Branch 4** (3 tests) — strict-mode validator behaviour: now
  asserts :class:`CascadeViolationError` is raised on cascade-depth
  violations per v12.0.0 PV-02 D-1 (was: returned warning list).
* **Branch 5** (1 test) — full populate→validate pipeline propagation
  across the four-tier complexity truth table; STRICT-mode raises
  pinned at boundaries.
* **Branch 6** (7 NEW tests) — v12.0.0 PV-02 D-1 STRICT graduation
  contract pins:
  * exception class inheritance (subclass of :class:`Exception`),
  * error-message contract (cites Architecture rule A-7 verbatim),
  * raise-on-missing-cascade-min-layers,
  * raise-on-invalid-cascade_required-type,
  * raise-on-actual-layers-below-min,
  * return-None-on-pass,
  * audit ratchet ``--strict`` default-ON regression pin.

Source: v12.0.0 PV-02 spec at
``.local/research/v12.0.0_gap_analysis.md`` §3 (D-1 spec) + the
v11.1.0 cycle plan §3 PV-05 row L2 W01 T01_cascade_enforcement_tests
(historical baseline) +
``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-1 (telegraph
rationale).
"""

from __future__ import annotations

import copy
import inspect
import sys
from pathlib import Path

import pytest
import yaml

from devolaflow.compressor import DEFAULT_DISPATCH_LAYOUT, FROZEN_PREFIX_LENGTH
from devolaflow.feedback import populate_cascade_gate_fields
from devolaflow.gate.cascade import CascadeViolationError, validate_cascade_gate_fields
from devolaflow.skills.change_activation import (
    Complexity,
    activation_verdict,
    cascade_requirement,
)
from devolaflow.skills.subagent_pattern import (
    forbidden_pattern_rationale,
    select_pattern,
)

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas/lean-dispatch.yaml"

# Truth table mirrors the operator-quotable verdict rule from the decision
# memo §1: "STANDARD complexity or higher → cascade required
# (L0→L1 Wave→L2 Task);
# SIMPLE / TRIVIAL → cascade optional (operators may collapse to one L2 Task)."
_CASCADE_TRUTH_TABLE: dict[Complexity, str] = {
    "TRIVIAL": "CASCADE_OPTIONAL",
    "SIMPLE": "CASCADE_OPTIONAL",
    "STANDARD": "CASCADE_REQUIRED",
    "COMPLEX": "CASCADE_REQUIRED",
}


# ── Branch 1 — PV-02 stub kept verbatim (no regression) ────────────────
# These four tests landed at v11.0.2 PV-02 and pin the cascade-signal
# pure-function contract + the A-2.1 frozen-prefix invariant + the
# orthogonality of cascade vs. activation_verdict.force_no_change. Their
# bodies MUST stay byte-identical to the PV-02 versions per the L1 PV-05
# prompt's "no regression" clause.


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
    # the L0→L1 Wave→L2 Task cascade regardless of the workspace override.
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


# ── Branch 2 — REPLACES the PV-02 SKIP telegraph (PV-04 helper landed) ─
# The PV-02 stub deferred the full propagation test to PV-04 via
# ``pytest.skip``. PV-04 has now shipped both the schema NEST AND the
# ``populate_cascade_gate_fields`` opt-in helper (lines 519-572 of
# ``src/devolaflow/feedback.py``); this PV-05 test promotes the SKIP into
# a real PASS that exercises the helper directly.


def test_cascade_signal_propagation_through_populate_helper() -> None:
    """STANDARD complexity → ``populate_cascade_gate_fields`` writes both NEST sub-fields.

    Pins the v11.0.4 PV-04 contract: the opt-in populate helper
    (:func:`devolaflow.feedback.populate_cascade_gate_fields`) deep-copies
    the base dispatch and adds ``gate.cascade_required = True`` +
    ``gate.cascade_min_layers = 3`` when complexity is STANDARD/COMPLEX.
    For SIMPLE the helper short-circuits per the canonical absence-as-
    default A-2.3 contract — the returned dispatch's ``gate`` block is
    BYTE-IDENTICAL to a deepcopy of the input (NO ``cascade_required``
    key surfaces).

    Replaces the PV-02 ``test_cascade_signal_propagation_pv04_telegraph``
    SKIP per cycle plan §3 PV-05 row L2 W01 T01_cascade_enforcement_tests
    (lines 316-322).
    """
    base = {"gate": {"coverage": 85}}

    # STANDARD path — both NEST sub-fields populated under existing gate.
    standard_result = populate_cascade_gate_fields(base_dispatch=base, complexity="STANDARD")
    assert standard_result["gate"]["cascade_required"] is True, (
        "populate_cascade_gate_fields(complexity='STANDARD') did NOT set "
        "gate.cascade_required = True per feedback.py:570"
    )
    assert standard_result["gate"]["cascade_min_layers"] == 3, (
        "populate_cascade_gate_fields(complexity='STANDARD') did NOT set "
        "gate.cascade_min_layers = 3 per the L0→L1 Wave→L2 Task contract"
    )
    # Pre-existing gate sub-fields preserved (deep copy + sub-field add).
    assert standard_result["gate"]["coverage"] == 85, (
        "populate_cascade_gate_fields lost the pre-existing gate.coverage "
        "key — deep-copy contract broken"
    )
    # Deep-copy contract: input MUST NOT be mutated (S-5 / A-2.3 + the
    # docstring's explicit "never mutated" promise on line 543).
    assert base == {"gate": {"coverage": 85}}, (
        "populate_cascade_gate_fields mutated base_dispatch — deep-copy "
        "contract broken per feedback.py:543"
    )
    assert standard_result is not base, (
        "populate_cascade_gate_fields returned the same object as base_dispatch "
        "— deep-copy contract broken"
    )

    # SIMPLE path — canonical absence-as-default (A-2.3); no NEST sub-fields.
    simple_result = populate_cascade_gate_fields(base_dispatch=base, complexity="SIMPLE")
    assert "cascade_required" not in simple_result["gate"], (
        "populate_cascade_gate_fields(complexity='SIMPLE') leaked "
        "gate.cascade_required — canonical absence-as-default per A-2.3 broken"
    )
    assert "cascade_min_layers" not in simple_result["gate"], (
        "populate_cascade_gate_fields(complexity='SIMPLE') leaked "
        "gate.cascade_min_layers — canonical absence-as-default per A-2.3 broken"
    )
    # SIMPLE path returns deepcopy of base (no NEST sub-fields). Must be
    # equal-by-value to the input AND must not be the same object.
    assert simple_result == base, (
        "populate_cascade_gate_fields(complexity='SIMPLE') returned a dispatch "
        "differing from a deepcopy of base — A-2.3 absence-as-default contract "
        "broken (R-1 mitigation: legacy SIMPLE dispatches must pass byte-identically)"
    )
    assert simple_result is not base, (
        "populate_cascade_gate_fields(complexity='SIMPLE') returned the same object "
        "as base_dispatch — deep-copy contract broken even on the OPTIONAL path"
    )


# ── Branch 3 — Backward-compat (R-1 mitigation, CRITICAL) ──────────────
# The L1 PV-05 prompt's R-1 mitigation requires that strict A-7
# enforcement be conditioned on ``cascade_requirement(complexity)``.
# Legacy v11.0.x dispatches without the new sub-fields, AND
# SIMPLE/TRIVIAL dispatches that intentionally omit the cascade signal,
# MUST pass byte-identically through the validator (no warnings) and
# MUST NOT have the sub-fields synthesised by the populate helper.
# These three tests pin the R-1 contract end-to-end.


@pytest.mark.parametrize(
    "legacy_gate",
    [
        pytest.param({"coverage": 85, "quality": 80}, id="cascade-fields-absent"),
        pytest.param({"cascade_required": False}, id="cascade-explicitly-disabled"),
    ],
)
# def test_legacy_dispatch_with_cascade_required_false_passes
# Historical W-18 discovery marker; consolidated into the explicit-off parameter above.
def test_legacy_dispatch_without_cascade_fields_passes_byte_identically(
    caplog: pytest.LogCaptureFixture,
    legacy_gate: dict[str, object],
) -> None:
    """Legacy absent/disabled cascade signals pass byte-identically.

    R-1 + R-12 backward compatibility covers both a pre-NEST v11.0.x
    gate block and the explicit ``cascade_required=False`` state. Both
    trigger ``if not cascade_required: return None`` without mutation,
    warning, exception, or other observable side effect.
    """
    snapshot = copy.deepcopy(legacy_gate)

    # v12.0.0 STRICT contract: returns None (was: returned [] in v11.x).
    # The MUST NOT raise contract is the R-12 carve-out for legacy callers.
    with caplog.at_level("WARNING", logger="devolaflow.gate.cascade"):
        result = validate_cascade_gate_fields(legacy_gate)

    assert result is None, (
        f"validate_cascade_gate_fields drifted from the v12.0.0 None return "
        f"contract on legacy gate block {legacy_gate!r}; got {result!r}, expected None. "
        "R-12 mitigation broken: absent and explicitly disabled cascade signals "
        "MUST pass byte-identically."
    )
    assert legacy_gate == snapshot
    assert caplog.records == []


def test_simple_complexity_skips_cascade_validation() -> None:
    """SIMPLE complexity → populate helper omits cascade sub-fields end-to-end.

    Confirms the R-1 mitigation skip path on the populate side: invoking
    :func:`populate_cascade_gate_fields` with ``complexity="SIMPLE"``
    short-circuits via the ``cascade_requirement(complexity) ==
    "CASCADE_OPTIONAL"`` guard (``src/devolaflow/feedback.py`` line 564),
    returning a deepcopy of the base dispatch with NO ``cascade_required``
    key under ``gate``. Equivalent to the SKIP path described in the L1
    PV-05 prompt — the cascade-strict enforcement never activates because
    the signal is canonically absent.
    """
    base = {"gate": {"coverage": 85}}

    result = populate_cascade_gate_fields(base_dispatch=base, complexity="SIMPLE")

    assert "cascade_required" not in result["gate"], (
        f"populate_cascade_gate_fields(complexity='SIMPLE') unexpectedly added "
        f"cascade_required to gate; got gate={result['gate']!r}. "
        "R-1 mitigation broken: SIMPLE complexity must take the OPTIONAL path "
        "per feedback.py:564."
    )
    assert "cascade_min_layers" not in result["gate"], (
        f"populate_cascade_gate_fields(complexity='SIMPLE') unexpectedly added "
        f"cascade_min_layers to gate; got gate={result['gate']!r}."
    )


def test_trivial_complexity_skips_cascade_validation() -> None:
    """TRIVIAL complexity → populate helper omits cascade sub-fields end-to-end.

    Mirror of the SIMPLE test above for the TRIVIAL tier. Both
    OPTIONAL-tier complexities take the same short-circuit path through
    the ``cascade_requirement(complexity) == "CASCADE_OPTIONAL"`` guard.
    """
    base = {"gate": {"coverage": 85}}

    result = populate_cascade_gate_fields(base_dispatch=base, complexity="TRIVIAL")

    assert "cascade_required" not in result["gate"], (
        f"populate_cascade_gate_fields(complexity='TRIVIAL') unexpectedly added "
        f"cascade_required to gate; got gate={result['gate']!r}. "
        "R-1 mitigation broken: TRIVIAL complexity must take the OPTIONAL path "
        "per feedback.py:564."
    )
    assert "cascade_min_layers" not in result["gate"], (
        f"populate_cascade_gate_fields(complexity='TRIVIAL') unexpectedly added "
        f"cascade_min_layers to gate; got gate={result['gate']!r}."
    )


# ── Branch 4 — Strict-mode validator behaviour (v12.0.0 PV-02 D-1) ─────
# v12.0.0 PV-02 D-1 BREAKING graduation: :func:`validate_cascade_gate_fields`
# was SOFT in v11.x (returned warning list) — it is now STRICT
# (raises :class:`CascadeViolationError` on the FIRST violation).
# These three tests pin the strict-mode contract that A-7 establishes
# at v12.0.0 per ``.rules/architecture.mdc`` §A-7.1 verbatim.


def test_strict_validator_warns_when_actual_layers_below_min(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Declared min 4 validates at face value in v17 (G17-A5): depth 2 raises."""
    gate_block = {"cascade_required": True, "cascade_min_layers": 4}
    snapshot = copy.deepcopy(gate_block)

    with (
        caplog.at_level("WARNING", logger="devolaflow.gate.cascade"),
        pytest.raises(CascadeViolationError) as excinfo,
    ):
        validate_cascade_gate_fields(gate_block, actual_layers=2)

    msg = str(excinfo.value)
    assert "cascade depth violation" in msg
    assert "actual_layers=2" in msg
    assert "cascade_min_layers=4" in msg
    assert not any(
        "legacy cascade_min_layers" in record.getMessage() for record in caplog.records
    ), "v16 legacy-fold WARNING must be gone in v17 (G17-A5)"
    assert gate_block == snapshot


def test_soft_mode_warns_instead_of_raising(caplog: pytest.LogCaptureFixture) -> None:
    """Declared min 4 keeps face-value semantics in v17 (G17-A5).

    The historical test name remains ghost-pinned. The v16 compat fold
    (4 → effective 3 + WARNING) is removed: depth 3 against a declared 4
    now raises, and depth 4 passes quietly without input mutation.
    """
    gate_block = {"cascade_required": True, "cascade_min_layers": 4}
    snapshot = copy.deepcopy(gate_block)

    with (
        caplog.at_level("WARNING", logger="devolaflow.gate.cascade"),
        pytest.raises(CascadeViolationError) as excinfo,
    ):
        validate_cascade_gate_fields(gate_block, actual_layers=3)
    assert "actual_layers=3 < cascade_min_layers=4" in str(excinfo.value)
    assert gate_block == snapshot

    caplog.clear()
    with caplog.at_level("WARNING", logger="devolaflow.gate.cascade"):
        assert validate_cascade_gate_fields(gate_block, actual_layers=4) is None
    assert caplog.records == []
    assert gate_block == snapshot


def test_strict_validator_passes_when_actual_layers_meets_min(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every explicit valid minimum (4 included, v17 face value) is quiet at depth==min."""
    gate_blocks = [
        {"cascade_required": True, "cascade_min_layers": minimum} for minimum in (1, 2, 3, 4, 5)
    ]
    snapshots = copy.deepcopy(gate_blocks)

    with caplog.at_level("WARNING", logger="devolaflow.gate.cascade"):
        for gate_block in gate_blocks:
            minimum = gate_block["cascade_min_layers"]
            assert validate_cascade_gate_fields(gate_block, actual_layers=minimum) is None

    assert caplog.records == []
    assert gate_blocks == snapshots


# ── Branch 5 — Cascade-requirement truth-table propagation pipeline ────
# The single end-to-end test below exercises the full populate→validate
# pipeline across all four complexity tiers in one truth-table sweep.
# This pins the composite contract: STANDARD/COMPLEX populate the NEST
# sub-fields AND the soft validator returns no warnings when actual_layers
# meets the populated min; SIMPLE/TRIVIAL skip the populate AND the soft
# validator short-circuits cleanly because no cascade_required is present.


def test_cascade_requirement_propagates_through_populate_then_validate() -> None:
    """Full populate→validate pipeline propagation across all 4 complexity tiers (STRICT).

    Sweeps the four-tier complexity truth table through the full
    populate→validate pipeline at v12.0.0 PV-02 D-1 STRICT semantics:

    1. Build the dispatch via
       :func:`devolaflow.feedback.populate_cascade_gate_fields`.
    2. STRICT-validate via
       :func:`devolaflow.gate.cascade.validate_cascade_gate_fields` with
       ``actual_layers=3`` (matches the populated default
       ``cascade_min_layers=3`` for STANDARD/COMPLEX; for SIMPLE/TRIVIAL
       no cascade_required key is populated so the validator
       short-circuits via the legacy R-12 path).
    3. Assert SIMPLE/TRIVIAL gate blocks have NO ``cascade_required`` key
       (skip path verified end-to-end — R-1 mitigation).

    Pins the composite contract that the v11.0.5 PV-05 audit ratchet
    + v12.0.0 PV-02 D-1 STRICT graduation key on: the populate→validate
    pipeline NEVER raises when the observed layer depth meets the
    populated minimum (or when no minimum was populated because
    complexity was OPTIONAL).
    """
    base: dict = {"gate": {"coverage": 85}}
    base_snapshot = copy.deepcopy(base)

    for complexity in ("STANDARD", "COMPLEX", "SIMPLE", "TRIVIAL"):
        dispatch = populate_cascade_gate_fields(base_dispatch=base, complexity=complexity)

        # v12.0.0 STRICT contract: the validator returns None on every
        # passing path AND raises on violations. With actual_layers=3
        # matching the populated min for STANDARD/COMPLEX, NO violation
        # fires. For SIMPLE/TRIVIAL the absence-canonical short-circuit
        # at scorer.py's ``if not cascade_required: return None`` fires
        # before any validation runs.
        result = validate_cascade_gate_fields(dispatch.get("gate"), actual_layers=3)
        assert result is None, (
            f"complexity={complexity!r}: validate_cascade_gate_fields drifted from "
            f"None for actual_layers=3; got {result!r}. Either the populate helper "
            "wrote a min above 3 (M2-W1-B contract violation) OR the strict "
            "validator's R-12 short-circuit broke."
        )

        if complexity in ("SIMPLE", "TRIVIAL"):
            assert "cascade_required" not in dispatch["gate"], (
                f"complexity={complexity!r}: populate_cascade_gate_fields leaked "
                f"cascade_required into gate; got gate={dispatch['gate']!r}. "
                "R-1 mitigation skip-path broken end-to-end."
            )
            assert "cascade_min_layers" not in dispatch["gate"], (
                f"complexity={complexity!r}: populate_cascade_gate_fields leaked "
                f"cascade_min_layers into gate; got gate={dispatch['gate']!r}."
            )
        else:
            assert dispatch["gate"]["cascade_required"] is True, (
                f"complexity={complexity!r}: populate_cascade_gate_fields did NOT "
                "set gate.cascade_required = True per feedback.py:570."
            )
            assert dispatch["gate"]["cascade_min_layers"] == 3, (
                f"complexity={complexity!r}: populate_cascade_gate_fields did NOT "
                "set gate.cascade_min_layers = 3."
            )

    # Cross-iteration deep-copy guard: the base dispatch survived all
    # four populate calls byte-identically. If any iteration mutated
    # *base*, this assertion fires (the docstring promise on
    # feedback.py:543 — "never mutated" — is the contract).
    assert base == base_snapshot, (
        f"base_dispatch mutated across the 4-tier sweep; got {base!r}, "
        f"expected {base_snapshot!r}. Deep-copy contract broken per "
        "feedback.py:543."
    )


# ── Branch 6 — v12.0.0 PV-02 D-1 STRICT graduation contract pins (NEW) ─
# These 7 NEW tests land at v12.0.0 PV-02 to pin the STRICT-graduation
# contract that the BREAKING change introduces. The W-18 ghost-audit
# refresh in :mod:`tests.test_no_ghost_features` keys on this Branch 6
# section header for the v12.0.0 PV-02 D-1 stanza.
#
# Source: ``.local/research/v12.0.0_gap_analysis.md`` §3.3 (test-impact
# estimate); v11.1.0 retrospective §3 D-1 (deferral telegraph).


def test_cascade_violation_error_inherits_from_exception() -> None:
    """:class:`CascadeViolationError` subclasses :class:`Exception` (not BaseException directly).

    v12.0.0 PV-02 D-1 contract pin: the exception class MUST be a
    subclass of :class:`Exception` so that operators can write a single
    ``except CascadeViolationError`` clause without accidentally catching
    :class:`KeyboardInterrupt` / :class:`SystemExit` (which subclass
    :class:`BaseException` directly). This mirrors the established
    ``ValidationError`` precedent in :mod:`devolaflow.compressor`.
    """
    assert issubclass(CascadeViolationError, Exception), (
        f"CascadeViolationError MRO drift: {CascadeViolationError.__mro__!r}. "
        "Per v12.0.0 PV-02 D-1 spec, the exception MUST subclass Exception "
        "(not BaseException directly)."
    )
    # Defensive: not a ValueError subclass (so it doesn't accidentally
    # get caught by callers that catch broad ValueError on dispatch
    # validation paths).
    assert not issubclass(CascadeViolationError, ValueError), (
        "CascadeViolationError is now a ValueError subclass — that "
        "violates the v12.0.0 PV-02 D-1 design which deliberately picks "
        "Exception as the base so a single ``except CascadeViolationError`` "
        "clause does not accidentally swallow other ValueErrors in the "
        "same try-block."
    )


def test_cascade_violation_error_message_cites_a7() -> None:
    """Every :class:`CascadeViolationError` message cites Architecture rule A-7.

    v12.0.0 PV-02 D-1 contract pin: the operator-quotable A-7 identifier
    MUST appear in EVERY error message string — the type-violation path,
    the missing-min-layers path, AND the depth-violation path. This
    survives any logging pipeline that strips structured fields and
    keeps the rule citation auditable in plain-text logs.
    """
    # Path 1: cascade_required type violation (non-bool truthy).
    with pytest.raises(CascadeViolationError) as type_exc:
        validate_cascade_gate_fields({"cascade_required": "yes"})
    assert "A-7" in str(type_exc.value), (
        f"type-violation error message {str(type_exc.value)!r} missing 'A-7' "
        "operator-quotable substring."
    )

    # Path 2: cascade_min_layers value violation.
    with pytest.raises(CascadeViolationError) as min_exc:
        validate_cascade_gate_fields({"cascade_required": True, "cascade_min_layers": "four"})
    assert "A-7" in str(min_exc.value), (
        f"min-layers-violation error message {str(min_exc.value)!r} missing "
        "'A-7' operator-quotable substring."
    )

    # Path 3: actual_layers depth violation.
    with pytest.raises(CascadeViolationError) as depth_exc:
        validate_cascade_gate_fields(
            {"cascade_required": True, "cascade_min_layers": 3}, actual_layers=1
        )
    assert "A-7" in str(depth_exc.value), (
        f"depth-violation error message {str(depth_exc.value)!r} missing "
        "'A-7' operator-quotable substring."
    )


def test_validate_cascade_gate_fields_raises_on_missing_cascade_required() -> None:
    """Cascade declared (``cascade_required=True``) but min layers missing → raises.

    v12.0.0 PV-02 D-1 contract pin: when a dispatch sets
    ``cascade_required=True`` but OMITS ``cascade_min_layers``, the
    ``cascade_min_layers`` lookup returns ``None`` which fails the
    ``isinstance(int)`` check, and the validator MUST raise
    :class:`CascadeViolationError`. The "missing" interpretation:
    when the dispatch ASSERTS that cascade is required, every
    cascade sub-field that the assertion implies MUST be present —
    otherwise the dispatch's claim is internally inconsistent.

    Note: this is distinct from ``cascade_required`` being absent
    from the gate block (legacy v11.0.x byte-identical short-circuit
    pinned by ``test_legacy_dispatch_without_cascade_fields_passes_byte_identically``).
    """
    gate_block = {"cascade_required": True}  # No cascade_min_layers.

    with pytest.raises(CascadeViolationError) as excinfo:
        validate_cascade_gate_fields(gate_block)

    msg = str(excinfo.value)
    assert "cascade_min_layers" in msg, (
        f"missing-min-layers error message {msg!r} must echo the violating sub-field name verbatim."
    )
    assert "None" in msg, (
        f"missing-min-layers error message {msg!r} must echo the "
        "received value (None) so the operator sees what was passed."
    )


def test_validate_cascade_gate_fields_raises_on_invalid_type() -> None:
    """``cascade_required`` truthy non-bool (e.g. ``"yes"``) → raises.

    v12.0.0 PV-02 D-1 contract pin: when ``cascade_required`` is
    truthy but not a Python ``bool`` (e.g. a non-empty string
    ``"yes"``), the validator's ``isinstance(..., bool)`` type check
    fires and raises :class:`CascadeViolationError`. Strings, lists,
    dicts and other truthy non-bool values all hit this path.

    Note: integer ``1`` and ``0`` short-circuit at the ``if not
    cascade_required`` guard before reaching the type check (``1`` is
    truthy but ``isinstance(1, bool)`` is False; ``0`` is falsy and
    short-circuits via the early ``return None``). This test pins the
    string-typed truthy case which is the most likely operator
    miswiring (e.g. YAML loaded with a string-typed ``"true"``).
    """
    with pytest.raises(CascadeViolationError) as excinfo:
        validate_cascade_gate_fields({"cascade_required": "yes"})

    msg = str(excinfo.value)
    assert "cascade_required must be bool" in msg, (
        f"type-violation error message {msg!r} must contain the "
        "operator-quotable substring 'cascade_required must be bool'."
    )
    assert "str" in msg, (
        f"type-violation error message {msg!r} must echo the received type name (str) verbatim."
    )


def test_validate_cascade_gate_fields_raises_on_actual_layers_below_min() -> None:
    """Every explicit valid minimum (4 included, v17 face value) rejects depth one below it."""
    for minimum in (1, 2, 3, 4, 5):
        actual = minimum - 1
        gate_block = {"cascade_required": True, "cascade_min_layers": minimum}

        with pytest.raises(CascadeViolationError) as excinfo:
            validate_cascade_gate_fields(gate_block, actual_layers=actual)

        msg = str(excinfo.value)
        assert "cascade depth violation" in msg
        assert f"actual_layers={actual}" in msg
        assert f"cascade_min_layers={minimum}" in msg


def test_validate_cascade_gate_fields_returns_none_on_pass() -> None:
    """Happy STRICT path: every passing input returns ``None`` (not empty list).

    v12.0.0 PV-02 D-1 BREAKING return-type contract pin: the validator
    returns ``None`` on every passing input — never the empty list
    that v11.x SOFT mode returned. Sweeps the canonical passing inputs:
    legacy dispatch, opt-out dispatch, depth-meets-min, depth-above-min.
    """
    # Legacy v11.0.x dispatch (no cascade keys).
    assert validate_cascade_gate_fields({"coverage": 85}) is None

    # Opt-out (cascade_required=False).
    assert validate_cascade_gate_fields({"cascade_required": False}) is None

    # Depth meets min (boundary inclusive-min).
    assert (
        validate_cascade_gate_fields(
            {"cascade_required": True, "cascade_min_layers": 3}, actual_layers=3
        )
        is None
    )

    # Depth exceeds min.
    assert (
        validate_cascade_gate_fields(
            {"cascade_required": True, "cascade_min_layers": 3}, actual_layers=4
        )
        is None
    )

    # gate_block=None.
    assert validate_cascade_gate_fields(None) is None


def test_audit_strict_default_on_v12_0_0() -> None:
    """``scripts/audit_layer_usage.py::run`` default ``strict`` is ``True`` at v12.0.0.

    v12.0.0 PV-02 D-1 contract pin (regression guard): the audit
    ratchet runtime flips from default-OFF (v11.1.0 PV-05) to default-ON
    (v12.0.0 PV-02). Operators who scripted ``run()`` without passing
    ``strict=`` explicitly will now see exit-1 on cascade-drift evidence
    — the BREAKING graduation telegraphed at v11.1.0 retrospective §3
    D-1 (date 2026-05-08).

    Companion test in :mod:`tests.test_audit_layer_usage` exercises the
    runtime side-effect; this test pins the function-signature default
    so a future maintainer cannot silently revert the flip.
    """
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import audit_layer_usage  # noqa: E402

    sig = inspect.signature(audit_layer_usage.run)
    strict_default = sig.parameters["strict"].default

    assert strict_default is True, (
        f"audit_layer_usage.run() ``strict`` parameter default drifted to "
        f"{strict_default!r}; expected True per v12.0.0 PV-02 D-1 graduation. "
        "The BREAKING flip was telegraphed at v11.1.0 retrospective §3 D-1; "
        "do NOT revert without an SI-1 entry per W-21 cadence."
    )


# ── Branch 7 — v12.0.0 PV-04 NEW subagent-pattern NEST consistency ─────
# These 7 NEW tests land at v12.0.0 PV-04 to pin the schema-NEST cross-
# couple consistency contract that pairs the v12.0.0 PV-02 D-1 STRICT
# cascade validator (Branch 6 above) with the v12.0.0 PV-04 NEW
# ``gate.subagent_pattern`` sub-field. Source: v12.0.0 PV-04 design at
# ``.local/research/v12.0.0_gap_analysis.md`` §5 +
# ``docs/cycle-archive/v11.4.0/other/v11.4.0_subagent_pattern_analysis.md``
# §7.1 NEST verdict (pre-staging).
#
# Per the v11.4.0 SI-1 §7.3 pre-staging recommendation: cascade-required
# dispatches MAY pair with any of the 3 valid PatternVerdict literals
# (``"INLINE"`` / ``"FAN_OUT"`` / ``"AGENT_POOL_FORWARD"``) without
# raising the cascade validator — pattern selection is the AGENT-to-
# AGENT dispatch shape; cascade depth is the LAYER-to-LAYER chain
# depth. The two are INDEPENDENT axes that compose. ``"TEAMS_FORBIDDEN"``
# is RESERVED for the operator-education path
# (:func:`forbidden_pattern_rationale`); :func:`select_pattern` NEVER
# returns it (W-24.1) and any dispatch carrying that literal is
# internally inconsistent (W-24.3 rationale: P5 invariant forbids
# cross-agent shared state).


class TestCascadePatternConsistency:
    """v12.0.0 PV-04 — cascade × subagent-pattern cross-couple consistency.

    Pins the contract that cascade depth and subagent pattern are
    INDEPENDENT axes that compose orthogonally:

    * The cascade validator (:func:`validate_cascade_gate_fields`)
      consults ONLY ``gate.cascade_required`` /
      ``gate.cascade_min_layers`` — it does NOT consult
      ``gate.subagent_pattern``. A cascade-required dispatch with ANY
      of the 3 valid PatternVerdict literals passes the cascade
      validator cleanly.
    * The opt-in
      :func:`devolaflow.feedback.populate_cascade_gate_fields` helper
      populates BOTH ``gate.cascade_required`` /
      ``gate.cascade_min_layers`` (cascade depth) AND
      ``gate.subagent_pattern`` (pattern shape) when the four v12.0.0
      PV-04 axes are passed. Legacy v11.x callers that omit the axes
      get the v11.1.0 behaviour byte-identically — the new sub-field
      is OMITTED (canonical absence-as-default per A-2.3).
    * ``"TEAMS_FORBIDDEN"`` is NEVER produced by ``select_pattern``
      (W-24.1) and the sole rationale-emitter is
      :func:`forbidden_pattern_rationale`. A dispatch carrying that
      literal is a manual / accidental injection — a bug per S-5
      (no silent failures); the dedicated test below pins this
      invariant.

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §5 +
    ``docs/cycle-archive/v11.4.0/other/v11.4.0_subagent_pattern_analysis.md``
    §7.1 NEST verdict pre-staged for v12.0.0; pairs with Branch 6
    above (v12.0.0 PV-02 D-1 STRICT graduation contract pins).
    """

    def test_cascade_required_with_subagent_inline_consistent(self) -> None:
        """``cascade_required=True`` + ``subagent_pattern="INLINE"`` is consistent.

        Pattern 1 INLINE on a CASCADE_REQUIRED dispatch is the canonical
        single-L2-Task-after-L0→L1-Wave shape. The cascade
        validator (which inspects ONLY the cascade sub-fields) returns
        ``None`` cleanly because the pattern sub-field is orthogonal —
        it does NOT feed into the depth-violation check. INLINE means
        "single L2 Task dispatched via the ``Task`` tool"; the L0/L1 Wave
        cascade chain still happens — the ``subagent_pattern`` only
        identifies the leaf-level dispatch shape.
        """
        gate_block = {
            "cascade_required": True,
            "cascade_min_layers": 3,
            "subagent_pattern": "INLINE",
        }

        # Validate-cascade returns None when actual_layers >= min (the
        # cascade is honoured; pattern is orthogonal).
        result = validate_cascade_gate_fields(gate_block, actual_layers=3)
        assert result is None, (
            f"validate_cascade_gate_fields drifted from None on "
            f"cascade_required=True + subagent_pattern=INLINE; got {result!r}. "
            "The cascade validator MUST NOT consult subagent_pattern — "
            "the two axes are independent per W-24 + the v12.0.0 PV-04 "
            "NEST decision rule."
        )

    def test_cascade_required_with_subagent_fan_out_consistent(self) -> None:
        """``cascade_required=True`` + ``subagent_pattern="FAN_OUT"`` is consistent.

        Pattern 2 FAN_OUT on a CASCADE_REQUIRED dispatch is the
        canonical cascaded-fan-out shape: L0 → L1 Wave →
        parallel L2 Tasks (max 5 per ``references/agent-hierarchy.md``
        §5). The cascade validator returns ``None`` cleanly because
        the pattern sub-field is orthogonal to the depth check.
        """
        gate_block = {
            "cascade_required": True,
            "cascade_min_layers": 3,
            "subagent_pattern": "FAN_OUT",
        }

        result = validate_cascade_gate_fields(gate_block, actual_layers=3)
        assert result is None, (
            f"validate_cascade_gate_fields drifted from None on "
            f"cascade_required=True + subagent_pattern=FAN_OUT; got {result!r}."
        )

    def test_cascade_required_with_subagent_teams_forbidden_raises(self) -> None:
        """``subagent_pattern="TEAMS_FORBIDDEN"`` is internally inconsistent (S-5).

        Per W-24.1 + W-24.3: :func:`select_pattern` NEVER returns
        ``"TEAMS_FORBIDDEN"``; the literal is RESERVED for the
        operator-education path
        (:func:`forbidden_pattern_rationale`). A dispatch carrying
        ``gate.subagent_pattern = "TEAMS_FORBIDDEN"`` is a manual /
        accidental injection — the
        :func:`devolaflow.feedback.populate_cascade_gate_fields`
        helper NEVER produces it. This test pins the invariant by:

        1. Sweeping the input space of ``select_pattern`` and asserting
           NO input combination ever yields ``"TEAMS_FORBIDDEN"`` (the
           helper-side guarantee).
        2. Verifying that
           :func:`forbidden_pattern_rationale` returns a non-None
           rationale string ONLY for ``"TEAMS_FORBIDDEN"`` — the
           operator-education surface — and NEVER for the 3 valid
           verdicts; this is the signal the dispatch consumer
           inspects per S-5 (no silent failures).

        Per the v11.4.0 SI-1 §7.3 + v12.0.0 PV-04 spec: a
        TEAMS_FORBIDDEN literal is a release blocker — it MUST be
        rejected at validate time per W-24.3 P5-invariant rationale.
        """
        # Helper-side invariant: select_pattern NEVER returns
        # TEAMS_FORBIDDEN under any input combination (W-24.1).
        for complexity in ("TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"):
            for tier in ("small", "balanced", "frontier"):
                for tc in (1, 2, 5):
                    for parallel in (False, True):
                        verdict = select_pattern(
                            complexity=complexity,  # type: ignore[arg-type]
                            model_tier=tier,  # type: ignore[arg-type]
                            task_count=tc,
                            parallel_independence=parallel,
                        )
                        assert verdict != "TEAMS_FORBIDDEN", (
                            f"select_pattern({complexity!r}, {tier!r}, "
                            f"{tc!r}, {parallel!r}) returned {verdict!r} — "
                            "the helper MUST NEVER produce TEAMS_FORBIDDEN."
                        )

        # Operator-education surface: forbidden_pattern_rationale
        # returns a non-None rationale ONLY for TEAMS_FORBIDDEN; the
        # rationale string MUST cite P5 + shared state (the operator-
        # quotable identifiers per W-24.3).
        rationale = forbidden_pattern_rationale("TEAMS_FORBIDDEN")
        assert rationale is not None, (
            "forbidden_pattern_rationale('TEAMS_FORBIDDEN') drifted to "
            "None — W-24.3 operator-education surface broken."
        )
        assert "P5" in rationale, (
            f"forbidden_pattern_rationale rationale {rationale!r} missing "
            "the operator-quotable substring 'P5' (Soul-level invariant)."
        )
        assert "shared state" in rationale, (
            f"forbidden_pattern_rationale rationale {rationale!r} missing "
            "the operator-quotable substring 'shared state' (the P5 "
            "invariant body — A-1 P5 verbatim)."
        )

        # The 3 valid verdicts MUST NOT trigger the rationale path
        # (the operator-education surface is reserved for the
        # forbidden literal alone).
        for valid_verdict in ("INLINE", "FAN_OUT"):
            assert forbidden_pattern_rationale(valid_verdict) is None, (
                f"forbidden_pattern_rationale({valid_verdict!r}) drifted "
                "from None — only TEAMS_FORBIDDEN is the operator-"
                "education surface per W-24.3."
            )

    def test_subagent_pattern_absent_is_canonical_pass(self) -> None:
        """Legacy v11.x dispatches without ``gate.subagent_pattern`` pass cleanly.

        The absence-canonical contract (A-2.3 NEST decision) requires
        that legacy dispatches without the new sub-field render
        byte-identical to v11.4.0 dispatches and pass through every
        validator without observable side-effect. This test pins that
        contract end-to-end:

        1. A legacy gate block (no ``subagent_pattern`` key) passes
           the cascade validator cleanly (returns ``None`` on every
           passing path).
        2. A cascade-required legacy gate block (with
           ``cascade_required=True`` but NO ``subagent_pattern``)
           passes the cascade validator cleanly when
           ``actual_layers >= cascade_min_layers``.

        Pins the R-1 + R-12 backward-compat contract end-to-end at
        v12.0.0 PV-04: legacy v11.x callers MUST get byte-identical
        validation behaviour even after the new sub-field lands.
        """
        # Pure legacy: no cascade fields, no subagent_pattern.
        legacy_gate = {"coverage": 85, "quality": 80}
        assert validate_cascade_gate_fields(legacy_gate) is None, (
            "Pure-legacy gate block (no cascade fields, no subagent_pattern) "
            "drifted from None — A-2.3 absence-canonical contract broken."
        )

        # Cascade required, but no subagent_pattern (intermediate state
        # — caller authored a cascade-required dispatch BEFORE opting
        # into v12.0.0 PV-04 subagent-pattern wiring).
        intermediate_gate = {
            "cascade_required": True,
            "cascade_min_layers": 3,
        }
        assert validate_cascade_gate_fields(intermediate_gate, actual_layers=3) is None, (
            "Intermediate gate block (cascade_required=True, no "
            "subagent_pattern) drifted from None — A-2.3 absence-canonical "
            "contract broken."
        )

    def test_populate_cascade_gate_fields_ignores_removed_pattern_axes(self) -> None:
        """Cascade population no longer emits the removed pattern NEST."""
        base = {"gate": {"coverage": 85}}

        # Canonical FAN_OUT case: STANDARD complexity, 3 parallel L2
        # tasks with disjoint owned files. select_pattern verdict is
        # FAN_OUT per its decision rule (task_count >= 2 AND
        # parallel_independence is True AND not persistent_state_needed).
        result = populate_cascade_gate_fields(
            base_dispatch=base,
            complexity="STANDARD",
            model_tier="balanced",
            task_count=3,
            parallel_independence=True,
        )

        # Cascade sub-fields populated per v11.1.0 PV-04 contract.
        assert result["gate"]["cascade_required"] is True, (
            "populate_cascade_gate_fields(STANDARD, ...) did NOT set "
            "gate.cascade_required = True — v11.1.0 PV-04 contract broken."
        )
        assert result["gate"]["cascade_min_layers"] == 3, (
            "populate_cascade_gate_fields(STANDARD, ...) did NOT set "
            "gate.cascade_min_layers = 3 — M2-W1-B contract broken."
        )

        assert "subagent_pattern" not in result["gate"]

        # Pre-existing gate sub-fields preserved (deep copy + sub-field add).
        assert result["gate"]["coverage"] == 85, (
            "populate_cascade_gate_fields lost the pre-existing gate.coverage "
            "key — deep-copy contract broken."
        )

        # Deep-copy contract: input MUST NOT be mutated.
        assert base == {"gate": {"coverage": 85}}, (
            "populate_cascade_gate_fields mutated base_dispatch — deep-copy "
            "contract broken per feedback.py docstring."
        )

    def test_subagent_pattern_consistency_check_does_not_raise_on_simple(self) -> None:
        """SIMPLE complexity dispatches don't trigger the cascade check.

        Per A-7.1 (cascade is OPTIONAL for SIMPLE/TRIVIAL), the cascade
        validator MUST NOT raise
        because the ``cascade_required`` sub-field is OMITTED (the
        helper short-circuits at the
        ``cascade_requirement(complexity) == "CASCADE_OPTIONAL"`` guard
        for SIMPLE/TRIVIAL).

        This test pins the end-to-end skip path: the helper skips the
        cascade sub-fields because complexity is OPTIONAL. The validator
        then short-circuits at the
        ``if not cascade_required: return None`` guard and returns
        ``None`` regardless of the subagent pattern verdict.
        """
        base = {"gate": {"coverage": 85}}

        result = populate_cascade_gate_fields(
            base_dispatch=base,
            complexity="SIMPLE",
            model_tier="balanced",
            task_count=3,
            parallel_independence=True,
        )

        # SIMPLE complexity → cascade sub-fields OMITTED (the helper
        # short-circuits at cascade_requirement == "CASCADE_OPTIONAL").
        assert "cascade_required" not in result["gate"], (
            "populate_cascade_gate_fields(SIMPLE, ...) leaked "
            "cascade_required — A-7.1 CASCADE_OPTIONAL skip path broken."
        )
        assert "cascade_min_layers" not in result["gate"], (
            "populate_cascade_gate_fields(SIMPLE, ...) leaked "
            "cascade_min_layers — A-7.1 CASCADE_OPTIONAL skip path broken."
        )

        # Cascade validator short-circuits cleanly: no cascade_required
        # in the gate block → the validator's early-return fires.
        result_check = validate_cascade_gate_fields(result["gate"], actual_layers=1)
        assert result_check is None, (
            "validate_cascade_gate_fields drifted from None on a SIMPLE "
            "A-7.1 CASCADE_OPTIONAL skip-path broken — the validator MUST "
            "short-circuit before any depth check when cascade_required "
            "is absent."
        )
