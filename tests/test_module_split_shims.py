"""Shim contract for the v14.5.0 ADR-006 module split (gap G-025).

Per ``.local/research/adr/v15-ADR-006-scorer-selector-module-split.md`` the
v14.5.0 split extracts ``gate/cascade.py`` + ``gate/ladder.py`` +
``gate/acceptance_v2.py`` out of ``gate/scorer.py``, ``agents_md_slice.py``
+ ``selector_cli.py`` out of ``task_adaptive_selector.py``, and the
cascade populators + dispatch wrappers out of ``feedback.py`` — with
PERMANENT re-export shims at every historical public import path (the ADR's
shim clause; S-10 and ``schemas/lean-dispatch.yaml`` line 683 cite
``feedback.py::populate_cascade_gate_fields`` /
``feedback.py::ProposalGenerator.generate_round_dispatch`` BY PATH, so those
paths never expire).

This file is the executable contract: every old-path import MUST resolve
AND be the IDENTICAL object (``is``) as the new-owner-module symbol. A
shim that wraps, copies, or re-implements a moved symbol fails here.
"""

from __future__ import annotations

import importlib

import pytest

# (old_module, new_owner_module, symbol) — the full public moved-symbol set.
_SHIMMED_SYMBOLS: tuple[tuple[str, str, str], ...] = (
    # gate/scorer.py → gate/cascade.py (cascade + intra-task validators)
    ("devolaflow.gate.scorer", "devolaflow.gate.cascade", "CascadeViolationError"),
    ("devolaflow.gate.scorer", "devolaflow.gate.cascade", "validate_cascade_gate_fields"),
    ("devolaflow.gate.scorer", "devolaflow.gate.cascade", "IntraTaskConvergenceViolationError"),
    (
        "devolaflow.gate.scorer",
        "devolaflow.gate.cascade",
        "validate_intra_task_convergence_fields",
    ),
    # gate/scorer.py → gate/ladder.py (the 6-rung verification ladder)
    ("devolaflow.gate.scorer", "devolaflow.gate.ladder", "VERIFICATION_LADDER_ENV_FLAG"),
    ("devolaflow.gate.scorer", "devolaflow.gate.ladder", "RungChecker"),
    ("devolaflow.gate.scorer", "devolaflow.gate.ladder", "is_verification_ladder_active"),
    ("devolaflow.gate.scorer", "devolaflow.gate.ladder", "evaluate_ladder"),
    # gate/scorer.py → gate/acceptance_v2.py (AC-v2 + v14.4.0 metric runners)
    ("devolaflow.gate.scorer", "devolaflow.gate.acceptance_v2", "METRIC_KIND_COVERAGE"),
    ("devolaflow.gate.scorer", "devolaflow.gate.acceptance_v2", "METRIC_KIND_LINT"),
    ("devolaflow.gate.scorer", "devolaflow.gate.acceptance_v2", "METRIC_KIND_NUMBER"),
    ("devolaflow.gate.scorer", "devolaflow.gate.acceptance_v2", "CommandRunner"),
    ("devolaflow.gate.scorer", "devolaflow.gate.acceptance_v2", "CommandRunResult"),
    ("devolaflow.gate.scorer", "devolaflow.gate.acceptance_v2", "evaluate_acceptance_criteria_v2"),
    ("devolaflow.gate.scorer", "devolaflow.gate.acceptance_v2", "aggregate_criterion_verdicts"),
    # feedback.py → gate/cascade.py (populators beside their validators)
    ("devolaflow.feedback", "devolaflow.gate.cascade", "populate_cascade_gate_fields"),
    ("devolaflow.feedback", "devolaflow.gate.cascade", "populate_intra_task_convergence"),
    ("devolaflow.feedback", "devolaflow.gate.cascade", "INTRA_TASK_CONVERGENCE_TASK_TYPES"),
    ("devolaflow.feedback", "devolaflow.gate.cascade", "INTRA_TASK_MAX_ROUNDS_DEFAULT"),
    # feedback.py → dispatch.py (wave-execution / dogfood dispatch wrappers)
    ("devolaflow.feedback", "devolaflow.dispatch", "dispatch_wave_tasks"),
    ("devolaflow.feedback", "devolaflow.dispatch", "dispatch_dogfood_cycle"),
    # task_adaptive_selector.py → agents_md_slice.py (AGENTS.md slicing)
    ("devolaflow.task_adaptive_selector", "devolaflow.agents_md_slice", "select_agents_md_slice"),
    ("devolaflow.task_adaptive_selector", "devolaflow.agents_md_slice", "count_agents_md_rules"),
    # task_adaptive_selector.py → selector_cli.py (the CLI block)
    ("devolaflow.task_adaptive_selector", "devolaflow.selector_cli", "main"),
)


@pytest.mark.parametrize(
    ("old_module", "new_module", "symbol"),
    _SHIMMED_SYMBOLS,
    ids=[f"{old}::{sym}" for old, _new, sym in _SHIMMED_SYMBOLS],
)
def test_old_path_resolves_and_is_new_path_symbol(
    old_module: str, new_module: str, symbol: str
) -> None:
    """Every old-path import resolves AND ``is`` the new-owner-module symbol."""
    old = importlib.import_module(old_module)
    new = importlib.import_module(new_module)
    assert hasattr(old, symbol), (
        f"ADR-006 shim violation: {old_module}.{symbol} no longer resolves — "
        f"the permanent re-export shim was dropped."
    )
    assert getattr(old, symbol) is getattr(new, symbol), (
        f"ADR-006 shim violation: {old_module}.{symbol} is not the IDENTICAL "
        f"object as {new_module}.{symbol} — shims must be identity-preserving "
        f"re-exports, never wrappers or copies."
    )


def test_s10_named_paths_verbatim_functional() -> None:
    """The S-10 / schema-named ``feedback.py`` paths work verbatim.

    Soul rule S-10 names ``feedback.py::ProposalGenerator.generate_round_dispatch``
    and ``schemas/lean-dispatch.yaml`` line 683 names
    ``feedback.py::populate_cascade_gate_fields`` BY PATH — both MUST stay
    importable from ``devolaflow.feedback`` and behave (smoke-level)
    exactly as before the split.
    """
    from devolaflow.feedback import ProposalGenerator, populate_cascade_gate_fields

    assert callable(populate_cascade_gate_fields)
    assert callable(ProposalGenerator.generate_round_dispatch)

    # Smoke: STANDARD complexity populates the cascade NEST sub-fields on a
    # deep copy (input never mutated) — the v11.1.0 PV-04 W02 contract.
    # v15.0.0 strict graduation (G-038): the pre_dispatch chain now BLOCKS
    # dispatches without a testable acceptance criterion (VD002), so the
    # smoke payload carries one like real dispatches do.
    base: dict = {"task": {"id": "T-1"}, "accept": ["smoke dispatch passes the hook chain"]}
    out = populate_cascade_gate_fields(base, "STANDARD")
    assert out["gate"] == {"cascade_required": True, "cascade_min_layers": 4}
    assert "gate" not in base

    # Smoke: round-1 dispatch emission still runs (S-10 hook chain inside).
    dispatch = ProposalGenerator().generate_round_dispatch(base, verdict=None, round_num=1)
    assert dispatch == base
    assert dispatch is not base


def test_gate_package_facade_reexports_moved_symbols() -> None:
    """``devolaflow.gate`` keeps exporting the moved symbols identity-preserved."""
    import devolaflow.gate as gate
    from devolaflow.gate.acceptance_v2 import (
        CommandRunResult,
        aggregate_criterion_verdicts,
        evaluate_acceptance_criteria_v2,
    )
    from devolaflow.gate.ladder import evaluate_ladder

    assert gate.evaluate_ladder is evaluate_ladder
    assert gate.evaluate_acceptance_criteria_v2 is evaluate_acceptance_criteria_v2
    assert gate.aggregate_criterion_verdicts is aggregate_criterion_verdicts
    assert gate.CommandRunResult is CommandRunResult
    for name in (
        "evaluate_ladder",
        "evaluate_acceptance_criteria_v2",
        "aggregate_criterion_verdicts",
        "CommandRunResult",
    ):
        assert name in gate.__all__
