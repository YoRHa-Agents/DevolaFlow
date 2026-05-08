"""Cascade-enforcement test suite — v11.0.5 PV-05 full surface (S01.W01 T01).

This file is the **full ≥ 10-test surface** mandated by v11.1.0 cycle
plan §3 PV-05 row L2 W01 T01_cascade_enforcement_tests
(lines 316-322). It pins the end-to-end cascade contract that the
v11.1.0 cascade-restoration cycle delivers across PV-02..PV-05:

* **PV-02** — ``cascade_requirement(complexity)`` pure function
  (G-CLASSIFY-1 Candidate C, landed in
  :mod:`devolaflow.skills.change_activation`).
* **PV-04** — schema NEST + populate helper + soft validator:
   * ``schemas/lean-dispatch.yaml`` adds the
     ``gate.cascade_required: bool`` and ``gate.cascade_min_layers: int``
     OPTIONAL sub-fields under the existing ``gate`` block (A-2.3
     NEST decision; canonical_order length stays 17, schema version
     stays 6).
   * :func:`devolaflow.feedback.populate_cascade_gate_fields` —
     opt-in dispatch-payload populator (deep-copy + conditional
     write under STANDARD/COMPLEX).
   * :func:`devolaflow.gate.scorer.validate_cascade_gate_fields` —
     SOFT validator returning a list of warning strings (no
     exceptions); promotion to STRICT lands with Architecture rule
     A-7 in this PV (PV-05).
* **PV-05** — strict-mode promotion + this test surface. The strict
  enforcement is CONDITIONED on ``cascade_requirement(complexity)``
  per the L1 PV-05 prompt's R-1 mitigation: SIMPLE/TRIVIAL legacy
  dispatches with no L1/L2 trace MUST pass byte-identically (Branch
  3 below).

The 13 tests below are organised by branch with comment dividers so
the W-18 ghost-audit refresh and the cycle plan's per-PV trail stay
unambiguous:

* **Branch 1** (4 tests) — PV-02 stub kept verbatim (no regression).
* **Branch 2** (1 test) — REPLACES the PV-02 SKIP telegraph with a
  real propagation test through the PV-04 ``populate_cascade_gate_fields``
  helper.
* **Branch 3** (4 tests) — backward-compat (R-1 mitigation, CRITICAL):
  legacy v11.0.x dispatches without the new sub-fields pass through
  cleanly; SIMPLE/TRIVIAL skip cascade validation end-to-end.
* **Branch 4** (3 tests) — strict-mode validator behaviour: the
  PV-04 SOFT validator surfaces "cascade depth violation" warnings
  WITHOUT raising; A-7 strict promotion preserves the same return-
  list contract for the soft-mode alternative.
* **Branch 5** (1 test) — full populate→validate pipeline propagation
  across the four-tier complexity truth table.

Source: ``.local/research/v11.1.0_cycle_plan.md`` §3 PV-05 row L2 W01
T01_cascade_enforcement_tests (lines 316-322); §3 PV-04 row for the
schema NEST + helper landings; ``.local/research/v11.1.0_gap_analysis.md``
§G-TEST-1 (lines 313-362) for the branch coverage rationale.
"""

from __future__ import annotations

import copy
import inspect
from pathlib import Path

import yaml

from devolaflow.compressor import DEFAULT_DISPATCH_LAYOUT, FROZEN_PREFIX_LENGTH
from devolaflow.feedback import populate_cascade_gate_fields
from devolaflow.gate.scorer import validate_cascade_gate_fields
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
    ``gate.cascade_min_layers = 4`` when complexity is STANDARD/COMPLEX.
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
    assert standard_result["gate"]["cascade_min_layers"] == 4, (
        "populate_cascade_gate_fields(complexity='STANDARD') did NOT set "
        "gate.cascade_min_layers = 4 per feedback.py:571"
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
# These four tests pin the R-1 contract end-to-end.


def test_legacy_dispatch_without_cascade_fields_passes_byte_identically() -> None:
    """Legacy v11.0.x gate block (no cascade_* keys) → validator returns ``[]``.

    Per the L1 PV-05 prompt R-1 mitigation: a v11.0.x dispatch authored
    BEFORE the PV-04 schema NEST landed has no ``cascade_required`` key
    in its ``gate`` block. The :func:`validate_cascade_gate_fields`
    soft validator MUST return an empty list for such dispatches —
    legacy callers see byte-identical behaviour, no warnings surface,
    and the dispatch flows through cleanly.

    This is the precondition for A-7 STRICT promotion: strict mode
    inherits the same short-circuit per the validator's
    ``if not cascade_required: return warnings`` guard
    (``src/devolaflow/gate/scorer.py`` lines 179-181).
    """
    legacy_gate = {"coverage": 85, "quality": 80}

    warnings = validate_cascade_gate_fields(legacy_gate)

    assert warnings == [], (
        f"validate_cascade_gate_fields surfaced warnings on a legacy v11.0.x "
        f"gate block (no cascade_required key); got {warnings!r}, expected []. "
        "R-1 mitigation broken: legacy dispatches MUST pass byte-identically "
        "per the L1 PV-05 prompt."
    )


def test_legacy_dispatch_with_cascade_required_false_passes() -> None:
    """``gate.cascade_required = False`` → validator short-circuits.

    The PV-04 soft validator's ``if not cascade_required: return warnings``
    guard (``src/devolaflow/gate/scorer.py`` line 180) treats an explicit
    ``False`` value identically to absence — both are falsy and trigger
    the short-circuit return. This pins the R-1 mitigation for the
    intermediate state where a dispatch carries the schema NEST sub-field
    but with the default-OFF value.
    """
    legacy_gate = {"cascade_required": False}

    warnings = validate_cascade_gate_fields(legacy_gate)

    assert warnings == [], (
        f"validate_cascade_gate_fields surfaced warnings on cascade_required=False; "
        f"got {warnings!r}, expected []. The soft validator MUST short-circuit on "
        "any falsy cascade_required per scorer.py:180."
    )


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
    the ``cascade_requirement(complexity) == "CASCADE_OPTIONAL"`` guard;
    splitting the test functions per tier (rather than parametrizing)
    keeps the W-17 NEW-test-function trail unambiguous and lets a future
    failure point at the EXACT tier that regressed.
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


# ── Branch 4 — Strict-mode validator behaviour (PV-05 A-7 contract) ────
# The PV-04 :func:`validate_cascade_gate_fields` is SOFT — it RETURNS a
# list of warning strings, never raises. PV-05's Architecture rule A-7
# promotes strict enforcement, but per the R-1 mitigation the soft-mode
# return-list contract is preserved as the alternative path that callers
# may still invoke (for dispatch-time inspection without aborting). These
# three tests pin the soft-mode contract that A-7 must respect.


def test_strict_validator_warns_when_actual_layers_below_min() -> None:
    """``actual_layers < cascade_min_layers`` → cascade-depth violation warning.

    Pins the warning shape that A-7 strict enforcement consumes: when
    ``cascade_required is True`` AND the observed ``actual_layers`` falls
    below the ``cascade_min_layers`` threshold, the validator surfaces a
    warning containing the substring ``"cascade depth violation"``
    (verbatim from ``src/devolaflow/gate/scorer.py`` line 209). The
    substring is the operator-quotable identifier A-7's strict promotion
    will pattern-match on.
    """
    gate_block = {"cascade_required": True, "cascade_min_layers": 4}

    warnings = validate_cascade_gate_fields(gate_block, actual_layers=2)

    assert warnings, (
        "validate_cascade_gate_fields returned no warnings for "
        "actual_layers=2 < cascade_min_layers=4 — soft-check contract broken "
        "per scorer.py:208-214."
    )
    assert any("cascade depth violation" in w for w in warnings), (
        f"warnings={warnings!r} missing the operator-quotable substring "
        "'cascade depth violation' that scorer.py:209 emits and that A-7 strict "
        "promotion will pattern-match on."
    )


def test_soft_mode_warns_instead_of_raising() -> None:
    """SOFT mode RETURNS a list — never raises an exception.

    Pins the v11.0.4 PV-04 SOFT-mode contract that the L1 PV-05 prompt
    cites verbatim: ``validate_cascade_gate_fields`` returns warnings
    (a ``list``) rather than raising on a cascade-depth violation. This
    is the soft-mode alternative A-7 strict promotion preserves —
    callers that opt into the soft check can still inspect violations
    without aborting the gate flow.

    Rationale: the L1 PV-05 R-1 mitigation requires that strict
    enforcement be conditioned on ``cascade_requirement(complexity)``;
    the soft-mode return-list contract is the universal fallback that
    works regardless of complexity tier.
    """
    gate_block = {"cascade_required": True, "cascade_min_layers": 4}

    result = validate_cascade_gate_fields(gate_block, actual_layers=2)

    assert isinstance(result, list), (
        f"validate_cascade_gate_fields returned {type(result).__name__}, "
        "expected list — SOFT-mode contract broken per scorer.py:174 "
        "('warnings: list[str] = []' return shape)."
    )


def test_strict_validator_passes_when_actual_layers_meets_min() -> None:
    """``actual_layers == cascade_min_layers`` → no warnings (boundary PASS).

    Pins the boundary case that A-7 strict enforcement also passes:
    when the observed layer depth EXACTLY meets the minimum threshold,
    the validator's strict comparison ``actual_layers <
    cascade_min_layers`` (scorer.py:206) evaluates False, no warning
    appears, and the dispatch flows through cleanly. Confirms the
    inclusive-min semantics A-7 will inherit.
    """
    gate_block = {"cascade_required": True, "cascade_min_layers": 4}

    warnings = validate_cascade_gate_fields(gate_block, actual_layers=4)

    assert warnings == [], (
        f"validate_cascade_gate_fields surfaced warnings at the boundary "
        f"actual_layers=4 == cascade_min_layers=4; got {warnings!r}, expected []. "
        "Inclusive-min semantics broken per scorer.py:206 "
        "('< cascade_min_layers' is exclusive of the boundary)."
    )


# ── Branch 5 — Cascade-requirement truth-table propagation pipeline ────
# The single end-to-end test below exercises the full populate→validate
# pipeline across all four complexity tiers in one truth-table sweep.
# This pins the composite contract: STANDARD/COMPLEX populate the NEST
# sub-fields AND the soft validator returns no warnings when actual_layers
# meets the populated min; SIMPLE/TRIVIAL skip the populate AND the soft
# validator short-circuits cleanly because no cascade_required is present.


def test_cascade_requirement_propagates_through_populate_then_validate() -> None:
    """Full populate→validate pipeline propagation across all 4 complexity tiers.

    Sweeps the four-tier complexity truth table through the full PV-04
    payload pipeline:

    1. Build the dispatch via
       :func:`devolaflow.feedback.populate_cascade_gate_fields`.
    2. Soft-validate via
       :func:`devolaflow.gate.scorer.validate_cascade_gate_fields` with
       ``actual_layers=4`` (matches the populated default
       ``cascade_min_layers=4`` for STANDARD/COMPLEX, exceeds the absent
       sub-field default for SIMPLE/TRIVIAL).
    3. Assert SIMPLE/TRIVIAL gate blocks have NO ``cascade_required`` key
       (skip path verified end-to-end — R-1 mitigation).

    Pins the composite contract that the v11.0.5 PV-05 audit ratchet
    will key on: the populate→validate pipeline is byte-stable across
    every complexity tier, and the validator surfaces ZERO warnings
    when the observed layer depth meets the populated minimum (or when
    no minimum was populated because complexity was OPTIONAL).
    """
    base: dict = {"gate": {"coverage": 85}}
    base_snapshot = copy.deepcopy(base)

    for complexity in ("STANDARD", "COMPLEX", "SIMPLE", "TRIVIAL"):
        dispatch = populate_cascade_gate_fields(base_dispatch=base, complexity=complexity)

        warnings = validate_cascade_gate_fields(dispatch.get("gate"), actual_layers=4)
        assert warnings == [], (
            f"complexity={complexity!r}: validate_cascade_gate_fields surfaced "
            f"warnings={warnings!r} for actual_layers=4. Either the populate helper "
            "wrote a min above 4 (PV-04 contract violation — feedback.py:571 hard-codes "
            "4) OR the soft validator short-circuit broke (scorer.py:180)."
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
            assert dispatch["gate"]["cascade_min_layers"] == 4, (
                f"complexity={complexity!r}: populate_cascade_gate_fields did NOT "
                "set gate.cascade_min_layers = 4 per feedback.py:571."
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
