"""Shim contract for the v14.5.0 ADR-006 module split (gap G-025) — v17 form.

Per ``docs/cycle-archive/adr/v15-ADR-006-scorer-selector-module-split.md`` the
v14.5.0 split extracts ``gate/cascade.py`` + ``gate/ladder.py`` +
``gate/acceptance_v2.py`` out of ``gate/scorer.py``, ``agents_md_slice.py``
+ ``selector_cli.py`` out of ``task_adaptive_selector.py``, and the
cascade populators + dispatch wrappers out of ``feedback.py`` — originally
with re-export shims at every historical public import path.

v17.0.0 shim retirement (the ADR's "revisit at v16.0.0+" clause discharged):
every in-repo call site migrated to the owner modules and the shims were
DELETED — EXCEPT the S-10/schema-named path, which is PERMANENT because
S-10 and ``schemas/lean-dispatch.yaml`` line ~683 cite
``feedback.py::populate_cascade_gate_fields`` /
``feedback.py::ProposalGenerator.generate_round_dispatch`` BY PATH.

This file is the executable contract in BOTH directions: retired old-path
imports MUST NOT resolve (a reappearing re-export fails here), and the
S-10-named keeper MUST resolve AND be the IDENTICAL object (``is``) as the
owner-module symbol.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

# (old_module, symbol) — every ADR-006 shim retired in v17.0.0. Importing
# the old module must succeed (the modules themselves live on); the retired
# re-export attribute must be GONE.
_RETIRED_SHIMS: tuple[tuple[str, str], ...] = (
    # gate/scorer.py → gate/cascade.py (cascade + intra-task validators)
    ("devolaflow.gate.scorer", "CascadeViolationError"),
    ("devolaflow.gate.scorer", "validate_cascade_gate_fields"),
    ("devolaflow.gate.scorer", "IntraTaskConvergenceViolationError"),
    ("devolaflow.gate.scorer", "validate_intra_task_convergence_fields"),
    # gate/scorer.py → gate/ladder.py (the 6-rung verification ladder)
    ("devolaflow.gate.scorer", "VERIFICATION_LADDER_ENV_FLAG"),
    ("devolaflow.gate.scorer", "RungChecker"),
    ("devolaflow.gate.scorer", "is_verification_ladder_active"),
    ("devolaflow.gate.scorer", "evaluate_ladder"),
    # gate/scorer.py → gate/acceptance_v2.py (AC-v2 + v14.4.0 metric runners)
    ("devolaflow.gate.scorer", "METRIC_KIND_COVERAGE"),
    ("devolaflow.gate.scorer", "METRIC_KIND_LINT"),
    ("devolaflow.gate.scorer", "METRIC_KIND_NUMBER"),
    ("devolaflow.gate.scorer", "CommandRunner"),
    ("devolaflow.gate.scorer", "CommandRunResult"),
    ("devolaflow.gate.scorer", "evaluate_acceptance_criteria_v2"),
    ("devolaflow.gate.scorer", "aggregate_criterion_verdicts"),
    # feedback.py → gate/cascade.py (intra-task populate helper + constants;
    # populate_cascade_gate_fields is NOT here — it is the S-10 keeper)
    ("devolaflow.feedback", "populate_intra_task_convergence"),
    ("devolaflow.feedback", "INTRA_TASK_CONVERGENCE_TASK_TYPES"),
    ("devolaflow.feedback", "INTRA_TASK_MAX_ROUNDS_DEFAULT"),
    # feedback.py → dispatch.py (wave-execution wrapper)
    ("devolaflow.feedback", "dispatch_wave_tasks"),
    # task_adaptive_selector.py → agents_md_slice.py (AGENTS.md slicing)
    ("devolaflow.task_adaptive_selector", "select_agents_md_slice"),
    ("devolaflow.task_adaptive_selector", "count_agents_md_rules"),
    # task_adaptive_selector.py → selector_cli.py (the CLI block)
    ("devolaflow.task_adaptive_selector", "main"),
)

_DIRECT_IMPLEMENTATION_FACADES: tuple[str, ...] = (
    "devolaflow._compressor_transforms",
    "devolaflow._plugin_installer",
    "devolaflow._workspace_lint",
    "devolaflow._workspace_reporter",
)

_MARKER_FREE_IMPLEMENTATION_FACADES: tuple[str, ...] = (
    "devolaflow._compressor_transforms",
    "devolaflow._workspace_lint",
    "devolaflow._workspace_reporter",
)

_PUBLIC_COMPATIBILITY_FACADES: tuple[
    tuple[str, str, tuple[str, ...]],
    ...,
] = (
    (
        "devolaflow.compressor.transforms",
        "src/devolaflow/compressor/transforms.py",
        (
            "_validate_summary_args",
            "_select_sections_for_summary",
            "_assemble_summary_body",
            "summarise_predecessor",
        ),
    ),
    (
        "devolaflow.agent_workspace.lint",
        "src/devolaflow/agent_workspace/lint.py",
        ("HumanBudgetExceededError", "enforce_digest_budget"),
    ),
)


@pytest.mark.parametrize("module_name", _DIRECT_IMPLEMENTATION_FACADES)
def test_internal_implementation_facade_direct_import(module_name: str) -> None:
    """Each split implementation facade imports in a fresh interpreter."""
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib; "
                f"module = importlib.import_module({module_name!r}); "
                "assert module.__all__"
            ),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"direct import failed for {module_name}:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.parametrize("module_name", _MARKER_FREE_IMPLEMENTATION_FACADES)
def test_internal_facade_drops_historical_monkeypatch_marker(
    module_name: str, project_root: Path
) -> None:
    """Private non-aliased facades do not carry obsolete patch forwarding."""
    package_path = project_root / "src" / Path(*module_name.split("."))
    source = (package_path / "__init__.py").read_text(encoding="utf-8")
    assert "class _CompatModule" not in source
    assert "Forward legacy monkeypatches" not in source


def test_public_compatibility_facades_are_marker_free_and_retain_exports(
    project_root: Path,
) -> None:
    """Historical source-shape pins do not replace public facade exports."""
    for module_name, relative_path, symbols in _PUBLIC_COMPATIBILITY_FACADES:
        source = (project_root / relative_path).read_text(encoding="utf-8")
        assert "if False:" not in source
        assert "PFR_BLOCKER_SIGNAL" not in source

        facade = importlib.import_module(module_name)
        for symbol in symbols:
            assert hasattr(facade, symbol), f"{module_name}.{symbol} was not re-exported"


def test_compressor_facade_wrappers_delegate_to_owner() -> None:
    """The public compressor facade keeps its callable compatibility wrappers."""
    facade = importlib.import_module("devolaflow.compressor.transforms")

    compressed = facade.compress_message("plain text", bypass_conditions=[])
    assert compressed["compressed_text"] == "plain text"
    assert facade.validate_lean_format("plain text")["intensity"] == "standard"


@pytest.mark.parametrize(
    ("old_module", "symbol"),
    _RETIRED_SHIMS,
    ids=[f"{old}::{sym}" for old, sym in _RETIRED_SHIMS],
)
def test_retired_shim_absent_from_old_path(old_module: str, symbol: str) -> None:
    """Every v17.0.0-retired shim is GONE from its historical module."""
    old = importlib.import_module(old_module)
    assert not hasattr(old, symbol), (
        f"v17.0.0 shim-retirement violation: {old_module}.{symbol} resolves "
        f"again — the ADR-006 re-export was retired in v17.0.0 after "
        f"call-site migration; import it from the owner module instead."
    )


def test_s10_named_paths_verbatim_functional() -> None:
    """The S-10 / schema-named ``feedback.py`` paths work verbatim.

    Soul rule S-10 names ``feedback.py::ProposalGenerator.generate_round_dispatch``
    and ``schemas/lean-dispatch.yaml`` line ~683 names
    ``feedback.py::populate_cascade_gate_fields`` BY PATH — both MUST stay
    importable from ``devolaflow.feedback`` and behave (smoke-level)
    exactly as before the split. PERMANENT — this keeper survives the v17
    shim retirement and must stay an identity-preserving re-export.
    """
    from devolaflow.feedback import ProposalGenerator, populate_cascade_gate_fields
    from devolaflow.gate.cascade import (
        populate_cascade_gate_fields as owner_populate_cascade_gate_fields,
    )

    assert populate_cascade_gate_fields is owner_populate_cascade_gate_fields, (
        "S-10 keeper violation: feedback.populate_cascade_gate_fields is not "
        "the IDENTICAL object as gate.cascade.populate_cascade_gate_fields — "
        "the permanent shim must stay an identity-preserving re-export."
    )
    assert callable(populate_cascade_gate_fields)
    assert callable(ProposalGenerator.generate_round_dispatch)

    # Smoke: STANDARD complexity populates the cascade NEST sub-fields on a
    # deep copy (input never mutated) — the v11.1.0 PV-04 W02 contract.
    # v15.0.0 strict graduation (G-038): the pre_dispatch chain now BLOCKS
    # dispatches without a testable acceptance criterion (VD002), so the
    # smoke payload carries one like real dispatches do.
    base: dict = {"task": {"id": "T-1"}, "accept": ["smoke dispatch passes the hook chain"]}
    out = populate_cascade_gate_fields(base, "STANDARD")
    assert out["gate"] == {"cascade_required": True, "cascade_min_layers": 3}
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
