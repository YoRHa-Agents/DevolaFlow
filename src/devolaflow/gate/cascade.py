"""Cascade + intra-task-convergence dispatch-shape validation and population.

v14.5.0 (ADR-006 / gap G-025 module split) — code extracted VERBATIM from
``gate/scorer.py`` (``CascadeViolationError``, ``validate_cascade_gate_fields``,
``IntraTaskConvergenceViolationError``,
``validate_intra_task_convergence_fields``) and from ``feedback.py``
(``populate_cascade_gate_fields``, ``populate_intra_task_convergence`` plus
their constants) per
``docs/cycle-archive/adr/v15-ADR-006-scorer-selector-module-split.md`` decision
items 1 + 3 ("cascade — the v15.0.0 strict-flip surface — becomes a small
reviewable module"; "``populate_cascade_gate_fields`` moves beside
``gate/cascade.py``").

Path-contract note (S-10 + ``schemas/lean-dispatch.yaml`` line 683): rule and
schema text name ``feedback.py::populate_cascade_gate_fields`` and the
``gate.scorer`` validator paths BY PATH. PERMANENT identity-preserving
re-export shims live at the old paths (``devolaflow.feedback`` and
``devolaflow.gate.scorer``) — neither text changes; symbols imported from
either path are the SAME objects. Pinned by
``tests/test_module_split_shims.py``.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

# v11.1.0 PV-04 (W03) — module-level logger for the cascade validator
# (and any future scorer-side WARN-level emission). Per S-5 (no silent
# failures) the v12.0.0 PV-02 STRICT validator emits the violation via
# this logger AT WARNING level immediately BEFORE raising
# :class:`CascadeViolationError`, so observability tooling that scrapes
# WARNING-level lines retains the detection signal even when the caller
# catches the exception (R-12 mitigation per
# ``.local/research/v12.0.0_gap_analysis.md`` §9 R-12).
logger = logging.getLogger(__name__)


class CascadeViolationError(Exception):
    """Raised by :func:`validate_cascade_gate_fields` on cascade-depth violations.

    v12.0.0 PV-02 D-1 — Architecture rule A-7 STRICT-promotion exception.
    Signals that a dispatch payload's ``gate.cascade_required`` /
    ``gate.cascade_min_layers`` sub-fields are inconsistent or that the
    observed dispatch chain depth (``actual_layers``) falls below the
    declared ``cascade_min_layers``. Per the v12.0.0 cycle plan §3.2.1
    the STRICT validator raises on the FIRST violation it detects (it
    does NOT accumulate warnings — that was the v11.1.0 SOFT contract
    that this graduation BREAKS).

    Subclasses :class:`Exception` rather than :class:`ValueError` so
    callers can write a single ``except CascadeViolationError`` clause
    without accidentally catching unrelated argument-validation errors
    in the same try-block; the chosen base mirrors the established
    ``ValidationError`` precedent in
    :mod:`devolaflow.compressor` (also a plain ``Exception`` subclass).

    The string form of the error always cites Architecture rule A-7
    verbatim so the operator-quotable identifier survives any logging
    pipeline that strips structured fields.

    Source: v12.0.0 PV-02 design — closes the D-1 graduation telegraph
    documented at ``docs/cycle-archive/v11.1.0/retrospective.md`` §3
    D-1; gap analysis at ``.local/research/v12.0.0_gap_analysis.md``
    §3 (D-1 spec); implementation per ADR-007 §"Soul-vs-Architecture"
    decision-rule (A-7 stays at Architecture; W-21 Soul-set freeze
    locked at 10).
    """


# ─────────────────────────────────────────────────────────────────────────────
# v12.0.0 PV-02 D-1 — Cascade-required STRICT validator (graduated from SOFT)
#
# Pairs with the v11.1.0 PV-04 W01 schema NEST extension (the
# ``gate.cascade_required`` + ``gate.cascade_min_layers`` sub-fields under
# the existing ``gate`` block — see ``schemas/lean-dispatch.yaml`` lines
# 177-210) and the W02 ``feedback.py::populate_cascade_gate_fields``
# helper. v11.1.0 PV-04 shipped this as the SOFT validator (returns warning
# list); v12.0.0 PV-02 D-1 graduates it to STRICT (raises
# :class:`CascadeViolationError` on the first violation) per the W-21
# 2-cycle deliberation cadence telegraphed at
# ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-1.
#
# Backward-compat preserved by construction (R-12 mitigation per
# ``.local/research/v12.0.0_gap_analysis.md`` §9): the early-return paths
# for ``gate_block is None`` and falsy ``cascade_required`` keep legacy
# v11.0.x dispatches without the cascade sub-fields byte-identical
# (no raise, no observable side-effect — just a return-no-op).
#
# The validator does NOT modify ``evaluate_gate`` or any existing scorer
# function — the wiring into the gate flow is left to v12.0.x+ follow-up
# work to preserve the 10/10 R5 byte-identical contract in
# ``tests/test_dispatch_emission_runs_hooks.py``.
# ─────────────────────────────────────────────────────────────────────────────


def validate_cascade_gate_fields(
    gate_block: dict[str, Any] | None,
    *,
    actual_layers: int | None = None,
) -> None:
    """Strict validator for gate.cascade_required + gate.cascade_min_layers.

    .. versionchanged:: 12.0.0
       **BREAKING**: v12.0.0 PV-02 D-1 — Architecture rule A-7 STRICT
       graduation. The validator NOW RAISES :class:`CascadeViolationError`
       on the first violation it detects; the v11.1.0 SOFT-mode return-
       list-of-warning-strings contract is REMOVED. Operator-visible
       impact: any caller that previously consumed the warning list and
       treated empty list as "PASS" / non-empty as "WARN-not-FAIL" must
       now wrap the call in a ``try / except CascadeViolationError``
       block. The W-21 2-cycle deliberation cadence telegraphed this
       breaking change at v11.1.0 retrospective §3 D-1 (date 2026-05-08);
       v12.0.0 cycle plan §3.2.1 specifies the strict-raise semantics.
       Source: ``.local/research/v12.0.0_gap_analysis.md`` §3 (D-1).

    Inspects the dispatch's ``gate`` block for the cascade sub-fields
    (added by v11.1.0 PV-04 W01 schema NEST + W02
    :func:`devolaflow.feedback.populate_cascade_gate_fields` helper):

    * ``cascade_required: bool`` — when True, the dispatch was authored
      under STANDARD/COMPLEX complexity and the L3 receiver knows the
      chain MUST traverse L0 → L1 → L2 → L3 per Architecture rule A-7.
    * ``cascade_min_layers: int`` — minimum layer depth (default 4).

    Validation order (FIRST violation raises; the validator does NOT
    accumulate violations per v12.0.0 PV-02 spec):

    1. ``gate_block is None`` → no-op, returns ``None``
       (legacy v11.0.x byte-identical short-circuit; preserved per
       cycle plan §9 R-12 mitigation).
    2. ``cascade_required`` falsy / missing → no-op, returns ``None``
       (canonical absence-as-default per A-2.3 NEST contract; SIMPLE
       / TRIVIAL legacy dispatches pass through cleanly per A-7.1
       CASCADE_OPTIONAL branch).
    3. ``cascade_required`` truthy non-bool (e.g. ``"yes"``) →
       raises :class:`CascadeViolationError` ("cascade_required must
       be bool, got <type>").
    4. ``cascade_min_layers`` not ``int >= 1`` (None / str / float /
       bool / 0 / negative) → raises :class:`CascadeViolationError`
       ("cascade_min_layers must be int >= 1, got <repr>").
    5. ``actual_layers is not None`` AND ``actual_layers <
       cascade_min_layers`` → raises :class:`CascadeViolationError`
       ("cascade depth violation: actual_layers=<n> <
       cascade_min_layers=<n>").

    Args:
      gate_block: the dispatch's ``gate`` sub-dict, or ``None`` when
        absent. ``None`` and missing ``cascade_required`` short-circuit
        to return-no-op (R-12 backward-compat — legacy v11.0.x
        dispatches without the cascade sub-fields render byte-identical).
      actual_layers: optional observed layer depth in the dispatch
        chain. When ``None``, the validator checks schema correctness
        only (sub-field types) without verifying actual depth. When
        an int, the depth check (rule 5 above) fires.

    Returns:
      ``None`` on every passing path. The return-type change from
      ``list[str]`` (v11.x) to ``None`` (v12.0.0+) is part of the
      D-1 BREAKING graduation.

    Raises:
      CascadeViolationError: on the FIRST violation detected per the
        validation order above. Per S-5 (no silent failures) the
        violation is logged at WARNING level via this module's
        :data:`logger` IMMEDIATELY BEFORE the raise so observability
        pipelines that scrape WARNING-level output still see the
        detection signal even when the caller catches the exception.
        Every error message cites Architecture rule A-7 verbatim per
        the operator-quotable-identifier discipline (the 'A-7'
        substring survives any logging pipeline that strips structured
        fields).
    """
    if gate_block is None:
        return None

    cascade_required = gate_block.get("cascade_required")
    if not cascade_required:
        return None

    if not isinstance(cascade_required, bool):
        msg = f"A-7 cascade_required must be bool, got {type(cascade_required).__name__}"
        logger.warning(msg)
        raise CascadeViolationError(msg)

    cascade_min_layers = gate_block.get("cascade_min_layers")
    # bool is a subclass of int in Python — exclude it explicitly so
    # ``cascade_min_layers: True`` does NOT silently satisfy the int >= 1
    # check (semantics: cascade_min_layers is a layer depth like 1/2/3/4,
    # never a boolean). Order: type checks BEFORE the value comparison so
    # a non-int value (None / str / etc.) short-circuits before the
    # ``< 1`` compare which would TypeError on None.
    if (
        not isinstance(cascade_min_layers, int)
        or isinstance(cascade_min_layers, bool)
        or cascade_min_layers < 1
    ):
        msg = f"A-7 cascade_min_layers must be int >= 1, got {cascade_min_layers!r}"
        logger.warning(msg)
        raise CascadeViolationError(msg)

    if actual_layers is not None and actual_layers < cascade_min_layers:
        msg = (
            f"A-7 cascade depth violation: actual_layers={actual_layers} "
            f"< cascade_min_layers={cascade_min_layers}"
        )
        logger.warning(msg)
        raise CascadeViolationError(msg)

    return None


# v12.0.0 PV-02 D-1 — Architecture rule A-7 STRICT graduation LANDED.
# ``validate_cascade_gate_fields`` is now the canonical STRICT validator:
# raises :class:`CascadeViolationError` on the first violation, returns
# ``None`` on every passing path. The v11.1.0 SOFT-mode return-list
# contract is REMOVED (BREAKING change disclosed in CHANGELOG
# ``## [12.0.0]`` per the W-21 2-cycle deliberation cadence telegraphed
# at ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-1).
# The dead-API detector still tracks this helper via the explicit
# allowlist entry
# ``"devolaflow.gate.cascade:validate_cascade_gate_fields"`` in
# ``scripts/detect_dead_apis.py::DEFAULT_ALLOWLIST`` because the
# in-repo production-call wiring (an L0/L1/L2 dispatcher build path
# that invokes the validator) is itself a v12.0.0+ deliverable. NOT a
# domain-SSOT registry symbol per A-5.2 — pure function with zero
# module-level state. Source: ``.rules/architecture.mdc`` §A-7.1
# (STRICT graduation language) + ``.local/research/v12.0.0_gap_analysis.md``
# §3 (D-1 spec).


# ─────────────────────────────────────────────────────────────────────────────
# v14.4.0 (G-005 NEST slice) — Intra-task-convergence gate-field validator
#
# Pairs with the v14.4.0 schema NEST extension (the
# ``gate.intra_task_convergence`` + ``gate.intra_task_max_rounds``
# sub-fields under the existing ``gate`` block — see
# ``schemas/lean-dispatch.yaml``) and the
# ``feedback.py::populate_intra_task_convergence`` opt-in helper.
# Ships PERMISSIVE-by-default (returns a warning list; ``strict=True``
# raises :class:`IntraTaskConvergenceViolationError`) — the same
# DEFAULTS-PERMISSIVE-IN-MINOR / STRICT-IN-NEXT-MAJOR shape the
# v11.1.0 PV-04 cascade SOFT validator used before its v12.0.0 D-1
# graduation. Legacy dispatches without the new sub-fields flow through
# byte-identically (absence-canonical per A-2.3 NEST contract).
# ─────────────────────────────────────────────────────────────────────────────


class IntraTaskConvergenceViolationError(Exception):
    """Raised by :func:`validate_intra_task_convergence_fields` in strict mode.

    v14.4.0 (G-005 NEST slice) — signals that a dispatch payload's
    ``gate.intra_task_convergence`` / ``gate.intra_task_max_rounds``
    sub-fields carry the wrong types or out-of-range values. Mirrors
    :class:`CascadeViolationError` (plain :class:`Exception` subclass —
    NOT :class:`ValueError` — so a single ``except`` clause does not
    accidentally swallow unrelated argument-validation errors).

    The string form always cites the ``G-005`` gap identifier so the
    operator-quotable substring survives any logging pipeline that
    strips structured fields (the same discipline ``A-7`` uses on the
    cascade messages).
    """


def validate_intra_task_convergence_fields(
    gate_block: dict[str, Any] | None,
    *,
    strict: bool = False,
) -> list[str]:
    """Validate gate.intra_task_convergence + gate.intra_task_max_rounds.

    v14.4.0 (G-005 NEST slice) — type checks for the two NEST sub-fields
    populated by :func:`devolaflow.feedback.populate_intra_task_convergence`:

    * ``intra_task_convergence: bool`` — when True, the L3 receiver MUST
      run the ``references/execution-protocol.md`` §15 self-verify
      gen→verify→refine loop before its first StatusReport.
    * ``intra_task_max_rounds: int >= 1`` — the §15.4 bounded self-fix
      ceiling (default 2 when populated by the helper).

    Validation paths (each sub-field is independently OPTIONAL per the
    A-2.3 NEST contract — absence is canonical and short-circuits):

    1. ``gate_block is None`` → no violations (legacy short-circuit).
    2. Neither sub-field present → no violations (absence-canonical;
       v14.3.0 dispatches flow through byte-identically).
    3. ``intra_task_convergence`` present but not a ``bool`` → violation.
    4. ``intra_task_max_rounds`` present but not ``int >= 1`` (``bool``
       excluded explicitly — a layer/round count is never a boolean,
       mirroring the cascade_min_layers check) → violation.

    Args:
      gate_block: the dispatch's ``gate`` sub-dict, or ``None`` when
        absent.
      strict: ``False`` (default — DEFAULTS-PERMISSIVE-IN-MINOR) returns
        the violation messages as a warning list; ``True`` raises
        :class:`IntraTaskConvergenceViolationError` on the FIRST
        violation (the v15.0.0 strict-graduation preview, mirroring the
        cascade SOFT → STRICT ladder).

    Returns:
      List of violation messages (empty on every passing path). Each
      message is ALSO logged at WARNING level per S-5 (no silent
      failures) so observability pipelines see the detection signal in
      permissive mode too.

    Raises:
      IntraTaskConvergenceViolationError: in ``strict=True`` mode, on
        the first violation detected. The message cites the ``G-005``
        gap identifier verbatim.
    """
    warnings: list[str] = []
    if gate_block is None:
        return warnings

    if "intra_task_convergence" in gate_block:
        value = gate_block["intra_task_convergence"]
        if not isinstance(value, bool):
            msg = f"G-005 gate.intra_task_convergence must be bool, got {type(value).__name__}"
            logger.warning(msg)
            if strict:
                raise IntraTaskConvergenceViolationError(msg)
            warnings.append(msg)

    if "intra_task_max_rounds" in gate_block:
        value = gate_block["intra_task_max_rounds"]
        # bool is a subclass of int in Python — exclude it explicitly so
        # ``intra_task_max_rounds: True`` does NOT silently satisfy the
        # int >= 1 check (same discipline as cascade_min_layers).
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            msg = f"G-005 gate.intra_task_max_rounds must be int >= 1, got {value!r}"
            logger.warning(msg)
            if strict:
                raise IntraTaskConvergenceViolationError(msg)
            warnings.append(msg)

    return warnings


# ---------------------------------------------------------------------------
# v11.1.0 (PV-04 / W02) — Cascade-gate field population helper
#
# Module-level helper that L0/L1/L2 dispatchers may call BEFORE handing
# a base dispatch to ``ProposalGenerator.generate_round_dispatch``. The
# helper conditionally populates the v11.1.0 PV-04 W01 NEST sub-fields
# under the existing ``gate`` block (per the schema-side wiring in
# ``schemas/lean-dispatch.yaml`` lines 177-210):
#
# * ``gate.cascade_required: bool`` — true when complexity is
#   STANDARD/COMPLEX per ``cascade_requirement(complexity)``;
# * ``gate.cascade_min_layers: int`` — defaults to 4 (the canonical
#   L0 → L1 → L2 → L3 minimum) when cascade is required.
#
# Per Soul Rule S-10: this helper is OPT-IN. Callers that do NOT pass
# the base dispatch through this helper produce dispatches byte-identical
# to the v11.0.3 control — the existing
# ``tests/test_dispatch_emission_runs_hooks.py`` 10/10 R5 strict
# byte-identical contract is preserved BY CONSTRUCTION (the helper
# operates on the BASE dispatch BEFORE ``generate_round_dispatch`` runs;
# the round-N+1 emission path is unchanged).
#
# Per A-2.3 (NEST contract): SIMPLE/TRIVIAL complexity returns the deep
# copy AS-IS — canonical absence-as-default preserves the v9.7.0 layout
# byte-baseline + the 10 historical multi-baseline byte-tests in
# ``tests/test_layout_invariant_multi_baseline.py``.
#
# Source: v11.1.0 PV-04 spec — closes the W02 owned-files manifest;
# pairs with W03 (`gate/scorer.py::validate_cascade_gate_fields` soft
# validator). Strict A-7 enforcement lands at PV-05.
#
# v12.0.0 PV-04 EXTENSION — Subagent-pattern NEST wiring
#
# The same helper now ALSO populates ``gate.subagent_pattern`` per the
# v12.0.0 PV-04 NEST extension (sources: ``.local/research/v12.0.0_
# gap_analysis.md`` §5 + ``docs/cycle-archive/v11.4.0/other/v11.4.0_
# subagent_pattern_analysis.md`` §7.1 NEST verdict). The four input
# axes (``model_tier`` / ``task_count`` / ``parallel_independence``
# / ``persistent_state_needed``) are kw-only and OPTIONAL — when ANY
# of the three required axes is omitted (``None``), the helper defaults
# to ``"INLINE"`` (Pattern 1 — single L3 dispatch via the ``Task``
# tool) per the L1 PV-04 prompt §6 graceful-degradation contract.
# When ALL three are supplied, the helper invokes
# :func:`devolaflow.skills.subagent_pattern.select_pattern` and writes
# the verdict (one of ``"INLINE"`` / ``"FAN_OUT"`` /
# ``"AGENT_POOL_FORWARD"``) to ``gate.subagent_pattern``. The verdict
# ``"TEAMS_FORBIDDEN"`` is NEVER produced (``select_pattern`` is
# guarded; it raises :class:`ValueError` for invalid inputs per S-5).
#
# Backward-compat: legacy v11.x callers that do NOT pass any of the
# four axes get the original v11.1.0 behaviour byte-identically — the
# new sub-field is OMITTED (canonical absence-as-default per A-2.3).
# This preserves the 14 historical multi-baseline byte tests and the
# S-10 hook-chain 10/10 byte-identical contract.
# ---------------------------------------------------------------------------


def populate_cascade_gate_fields(
    base_dispatch: dict[str, Any],
    complexity: str,
    *,
    model_tier: str | None = None,
    task_count: int | None = None,
    parallel_independence: bool | None = None,
    persistent_state_needed: bool = False,
) -> dict[str, Any]:
    """Conditionally populate gate cascade + subagent-pattern NEST sub-fields.

    v11.1.0 PV-04 — opt-in helper for L0/L1/L2 dispatchers building a
    dispatch payload with explicit complexity. Returns a new dict
    (deep copy of *base_dispatch*) with the cascade sub-fields populated
    under the existing ``gate`` block when complexity is STANDARD/COMPLEX
    (per :func:`devolaflow.skills.change_activation.cascade_requirement`).
    For SIMPLE/TRIVIAL the cascade sub-fields are OMITTED (canonical
    absence-as-default per A-2.3 NEST contract).

    .. versionchanged:: 12.0.0
       v12.0.0 PV-04 — when the four optional kw-only axes
       (``model_tier`` / ``task_count`` / ``parallel_independence`` /
       ``persistent_state_needed``) are supplied, the helper ALSO
       populates ``gate.subagent_pattern`` via
       :func:`devolaflow.skills.subagent_pattern.select_pattern`.
       Legacy callers that omit the axes get the v11.1.0 behaviour
       byte-identically — the new sub-field is OMITTED (absence-
       canonical per A-2.3 NEST contract). Per the L1 PV-04 prompt
       graceful-degradation rule: when ANY of the three required
       axes (``model_tier`` / ``task_count`` / ``parallel_independence``)
       is ``None`` while at least one OTHER axis is supplied, the
       helper defaults to ``"INLINE"`` (Pattern 1) rather than
       raising. The verdict ``"TEAMS_FORBIDDEN"`` is NEVER produced
       (W-24.3: Pattern 4 PERMANENTLY NOT_SUPPORTED).

    Per S-10: this helper is OPT-IN.
    :meth:`ProposalGenerator.generate_round_dispatch` callers that do
    NOT pass through this helper produce dispatches byte-identical to
    the v11.0.3 control (the existing
    ``tests/test_dispatch_emission_runs_hooks.py`` 10/10 R5 strict
    byte-identical contract is preserved BY CONSTRUCTION — the helper
    operates on the BASE dispatch BEFORE the round-N+1 emission path).

    Args:
      base_dispatch: dispatch payload dict; never mutated.
      complexity: one of TRIVIAL/SIMPLE/STANDARD/COMPLEX.
      model_tier: optional Literal ``"small"`` / ``"balanced"`` /
        ``"frontier"`` per
        :data:`devolaflow.skills.subagent_pattern.ModelTier`. When
        supplied along with ``task_count`` and ``parallel_independence``,
        ``select_pattern`` is invoked to derive
        ``gate.subagent_pattern``. ``None`` (default) → caller did not
        opt in; subagent_pattern sub-field is OMITTED.
      task_count: optional positive int — number of L3 tasks the wave
        will dispatch. Required (with ``model_tier`` and
        ``parallel_independence``) for ``select_pattern``. Must be
        ``>= 1`` per :func:`devolaflow.skills.subagent_pattern.validate_inputs`.
      parallel_independence: optional bool — true when the L3 tasks
        own DISJOINT files and can run in parallel without
        cross-coordination. Required (with ``model_tier`` and
        ``task_count``) for ``select_pattern``.
      persistent_state_needed: bool, default ``False``. When ``True``
        AND ``model_tier == "frontier"`` AND complexity is
        STANDARD/COMPLEX, the verdict is ``"AGENT_POOL_FORWARD"``
        (Pattern 3 forward-compat). Otherwise the persistent-state
        flag has no effect on the verdict.

    Returns:
      Deep copy of *base_dispatch* with ``gate.cascade_required`` and
      ``gate.cascade_min_layers`` populated when cascade is required,
      AND ``gate.subagent_pattern`` populated when the four
      v12.0.0 PV-04 axes are passed (or any subset when the
      graceful-degradation INLINE default applies). When the input has
      no ``gate`` block AND any sub-field is required, an empty
      ``gate: {}`` dict is created and the sub-fields are added to it.

    Raises:
      ValueError: when ``complexity`` is not a recognised
        :data:`devolaflow.skills.change_activation.Complexity` literal —
        re-raised verbatim from :func:`cascade_requirement` per S-5
        (no silent coercion of unknown complexity tiers). When
        ``select_pattern`` is invoked with invalid inputs (e.g.
        ``model_tier`` not in ``("small", "balanced", "frontier")``),
        ``ValueError`` is re-raised verbatim per S-5.
    """
    from devolaflow.skills.change_activation import cascade_requirement

    dispatch = copy.deepcopy(base_dispatch)

    cascade_verdict = cascade_requirement(complexity)
    if cascade_verdict == "CASCADE_REQUIRED":
        gate_block = dispatch.get("gate")
        if not isinstance(gate_block, dict):
            dispatch["gate"] = {}
        dispatch["gate"]["cascade_required"] = True
        dispatch["gate"]["cascade_min_layers"] = 4

    # v12.0.0 PV-04 — subagent_pattern NEST population.
    #
    # Caller opt-in is detected by ANY of the four axes being supplied
    # (i.e. NOT all of model_tier / task_count / parallel_independence
    # are None and persistent_state_needed is False — the v11.x default
    # call signature). When opt-in is detected:
    #
    # * If all three REQUIRED axes are non-None → invoke select_pattern.
    # * If any required axis is None → default to INLINE (graceful
    #   degradation per the L1 PV-04 prompt §6 contract; mirrors the
    #   "default to INLINE if any axis is unknown" requirement).
    #
    # When NO axes are supplied (the legacy v11.x call path), the new
    # sub-field is OMITTED — canonical absence-as-default per A-2.3
    # preserves the 14 historical multi-baseline byte-tests and the
    # S-10 hook-chain 10/10 byte-identical contract.
    caller_opted_in = (
        model_tier is not None
        or task_count is not None
        or parallel_independence is not None
        or persistent_state_needed
    )
    if caller_opted_in:
        if model_tier is not None and task_count is not None and parallel_independence is not None:
            from devolaflow.skills.subagent_pattern import select_pattern

            subagent_verdict = select_pattern(
                complexity=complexity,  # type: ignore[arg-type]
                model_tier=model_tier,  # type: ignore[arg-type]
                task_count=task_count,
                parallel_independence=parallel_independence,
                persistent_state_needed=persistent_state_needed,
            )
        else:
            # Graceful-degradation: any required axis is None → INLINE
            # (Pattern 1, single L3 via Task tool). Per the L1 PV-04
            # prompt §6: "default to INLINE if any axis is unknown".
            subagent_verdict = "INLINE"

        gate_block = dispatch.get("gate")
        if not isinstance(gate_block, dict):
            dispatch["gate"] = {}
        dispatch["gate"]["subagent_pattern"] = subagent_verdict

    return dispatch


# v11.1.0 PV-05 — Architecture rule A-7 ("Cascade-Depth Invariant for
# Standard+ Dispatches") establishes ``populate_cascade_gate_fields`` as
# the canonical OPT-IN dispatch-payload populator for the cascade NEST
# sub-fields. The v11.1.0 PV-04 placeholder pin tuple
# ``_populate_cascade_gate_fields_dead_api_pins`` was REMOVED in v11.0.5
# PV-05 per cycle plan §3 PV-05 W03 ("dead-API pin cleanup now that A-7
# wires the symbols"); the dead-API detector tracks this helper via the
# explicit allowlist entry
# ``"devolaflow.gate.cascade:populate_cascade_gate_fields"`` in
# ``scripts/detect_dead_apis.py::DEFAULT_ALLOWLIST`` (with the v12.0.0
# STRICT-promotion deferral comment per cycle plan §6). The full
# production wiring lands at v12.0.0 STRICT promotion alongside
# ``validate_cascade_gate_fields`` per W-21 2-cycle deliberation cadence.
# Source: ``.rules/architecture.mdc`` §A-7 + cycle plan §6.


# ---------------------------------------------------------------------------
# v14.4.0 (G-005 NEST slice) — Intra-task-convergence gate field population
#
# Module-level helper mirroring the v11.1.0 PV-04 cascade precedent
# (``populate_cascade_gate_fields`` above): L0/L1/L2 dispatchers MAY call
# it BEFORE handing a base dispatch to
# ``ProposalGenerator.generate_round_dispatch``. The helper conditionally
# populates the v14.4.0 NEST sub-fields under the existing ``gate`` block
# (schema-side wiring in ``schemas/lean-dispatch.yaml``):
#
# * ``gate.intra_task_convergence: bool`` — true when the warrant rule
#   fires; the L3 receiver MUST run the execution-protocol §15
#   self-verify gen→verify→refine loop before its first StatusReport;
# * ``gate.intra_task_max_rounds: int`` — defaults to
#   :data:`INTRA_TASK_MAX_ROUNDS_DEFAULT` (2 — mirrors §15.4's max-2
#   bounded self-fix ceiling per P4 Bounded Retry).
#
# Warrant rule (per the v14.2.0 gap register §2.1 G-005 intent):
# implementation-class task types (:data:`INTRA_TASK_CONVERGENCE_TASK_TYPES`)
# WITH a non-empty ``acceptance_criteria_v2`` block present → populate.
# Everything else (review/research/design/benchmark tasks, or impl tasks
# without structured AC to verify against) → the deep copy is returned
# AS-IS — canonical absence-as-default per A-2.3 preserves ALL historical
# multi-baseline byte-tests in
# ``tests/test_layout_invariant_multi_baseline.py``.
#
# Source: ``.local/research/v14.2.0_gap_analysis.md`` §2.1 G-005 +
# §4.1 v14.4.0 row + §6 R-1.
# ---------------------------------------------------------------------------


# Implementation-class task types per the dispatch ``task.type`` enum
# (``schemas/lean-dispatch.yaml#lean_format_spec.task`` +
# ``references/decomposition-gate.md`` §4 task schema): the types whose
# artifact is executable/verifiable work product. Review / research /
# design / benchmark / release tasks are NOT implementation-class — the
# §15 gen→verify loop targets artifacts with runnable verification.
INTRA_TASK_CONVERGENCE_TASK_TYPES: frozenset[str] = frozenset({"code", "test", "config"})

# Mirrors execution-protocol §15.4: "max 2 self-fix iterations, then
# report honestly" (P4 Bounded Retry — every loop has a ceiling).
INTRA_TASK_MAX_ROUNDS_DEFAULT: int = 2


def populate_intra_task_convergence(
    base_dispatch: dict[str, Any],
    task_type: str,
) -> dict[str, Any]:
    """Conditionally populate the gate intra-task-convergence NEST sub-fields.

    v14.4.0 (G-005 NEST slice) — opt-in helper for L0/L1/L2 dispatchers,
    mirroring :func:`populate_cascade_gate_fields` (the v11.1.0 PV-04
    cascade precedent): deep-copy, never mutates *base_dispatch*,
    returns the copy unchanged when the warrant rule does not fire.

    Warrant rule: *task_type* is implementation-class
    (:data:`INTRA_TASK_CONVERGENCE_TASK_TYPES` — ``code`` / ``test`` /
    ``config``) AND *base_dispatch* carries a non-empty
    ``acceptance_criteria_v2`` list. When warranted, the helper writes
    ``gate.intra_task_convergence = True`` and
    ``gate.intra_task_max_rounds = 2``
    (:data:`INTRA_TASK_MAX_ROUNDS_DEFAULT`) under the existing ``gate``
    block (created as ``{}`` when absent). Otherwise the sub-fields are
    OMITTED — canonical absence-as-default per A-2.3 NEST contract, so
    non-warranted dispatches render byte-identical to v14.3.0.

    Args:
      base_dispatch: dispatch payload dict; never mutated.
      task_type: the dispatch's ``task.type`` value (e.g. ``"code"`` /
        ``"review"`` / ``"research"``). Matching is case-insensitive;
        non-implementation-class and unknown types take the
        absence-canonical path (the task-type enum is open across
        workflow templates — unknown is a legitimate non-impl verdict,
        not an error).

    Returns:
      Deep copy of *base_dispatch*, with the two NEST sub-fields
      populated under ``gate`` iff the warrant rule fires.
    """
    dispatch = copy.deepcopy(base_dispatch)

    ac_v2 = dispatch.get("acceptance_criteria_v2")
    warranted = (
        isinstance(task_type, str)
        and task_type.strip().lower() in INTRA_TASK_CONVERGENCE_TASK_TYPES
        and isinstance(ac_v2, list)
        and len(ac_v2) > 0
    )
    if not warranted:
        return dispatch

    gate_block = dispatch.get("gate")
    if not isinstance(gate_block, dict):
        dispatch["gate"] = {}
    dispatch["gate"]["intra_task_convergence"] = True
    dispatch["gate"]["intra_task_max_rounds"] = INTRA_TASK_MAX_ROUNDS_DEFAULT
    return dispatch
