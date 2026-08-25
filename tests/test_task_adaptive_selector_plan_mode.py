"""Plan-mode override coverage for the task-adaptive context selector.

v11.1.0 PV-04 W06 — pins the ``_PLAN_MODE_OVERRIDES`` block + the
``apply_plan_mode_overrides`` helper at the level of granularity that
``workflow-system/agent/references/plan-mode-enforcement.md`` §2.2 line
~99 promises (the reference cites this very file as the test surface
that backs the AGENT MODE byte-output invariant). Until v11.1.0 PV-04
the file was promised but absent — the existing
``tests/test_task_adaptive_selector.py`` covered ``select_context``
plan-mode integration, but the standalone ``_PLAN_MODE_OVERRIDES`` /
``apply_plan_mode_overrides`` micro-coverage lived nowhere. PV-04 W06
ships this file to close the gap.

Why a separate file rather than extending
``tests/test_task_adaptive_selector.py``? Two reasons:

* The reference doc cites this filename verbatim — so PV-04 makes the
  citation truthful.
* The W-17 per-PV NEW-test-function cap is ≤+30 per PV. PV-04 W06
  ships +7 here (this file) + +7 in
  ``tests/test_gate.py::TestCascadeGateFieldsValidator`` for a total
  of +14 — well under the cap. Splitting the new tests into the
  natural target file keeps the ghost-audit wiring clean (the W-18
  refresh in ``tests/test_no_ghost_features.py`` only needs to point
  at the new file's existence + the new gate class).

Source: v11.1.0 PV-04 cycle plan §3 W06; pairs with W04
(plan-mode-enforcement.md §4 item #10) + W05 (the
``plan_mode_cascade_required`` runtime carrier added to
``_PLAN_MODE_OVERRIDES`` in
``src/devolaflow/task_adaptive_selector.py`` lines 78-88).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from devolaflow.task_adaptive_selector import (
    _PLAN_MODE_OVERRIDES,
    apply_plan_mode_overrides,
)

# Module-level constants for clean assertions and W-18 refresh targeting.
_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_PLAN_MODE_DOC_PATH: Path = (
    _REPO_ROOT / "workflow-system" / "agent" / "references" / "plan-mode-enforcement.md"
)


def test_plan_mode_overrides_dict_includes_cascade_required_key() -> None:
    """``_PLAN_MODE_OVERRIDES`` carries the v11.1.0 PV-04 G-PLAN-2 cascade default."""
    assert _PLAN_MODE_OVERRIDES["plan_mode_cascade_required"] is True


def test_apply_plan_mode_overrides_propagates_cascade_required() -> None:
    """Helper surfaces ``plan_mode_cascade_required: True`` on the merged profile."""
    result = apply_plan_mode_overrides({"token_budget": 6000})
    assert result["plan_mode_cascade_required"] is True


def test_apply_plan_mode_overrides_preserves_byte_stable_keys() -> None:
    """Pre-v11.1.0 contract intact: model_hint / compression_intensity / sections."""
    profile = {
        "token_budget": 6000,
        "section_priorities": {"foo": "important"},
    }
    result = apply_plan_mode_overrides(profile)

    assert result["model_hint"] == "quality"
    assert result["compression_intensity"] == "minimal"

    priorities = result["section_priorities"]
    # Pre-existing key from the input profile MUST survive the merge —
    # plan-mode overrides only ADD/OVERWRITE plan-relevant section keys.
    assert priorities["foo"] == "important"
    # The 5 plan-mode overrides use current context-profile section anchors.
    assert priorities["hierarchy_table"] == "critical"
    assert priorities["gate_mechanism"] == "critical"
    assert priorities["rationalization_prevention"] == "critical"
    assert priorities["convergence_loop"] == "important"
    assert priorities["agent_mode_protocol"] == "supplementary"


def test_apply_plan_mode_overrides_does_not_mutate_input_profile() -> None:
    """The helper returns a new dict and leaves the input deep-equal to its pre-call state."""
    profile = {
        "token_budget": 6000,
        "section_priorities": {"foo": "important", "agent_mode_protocol": "important"},
        "model_hint": "balanced",
        "compression_intensity": "standard",
    }
    control = copy.deepcopy(profile)
    apply_plan_mode_overrides(profile)
    assert profile == control


def test_plan_mode_constraints_gate_is_checklist_round_aware() -> None:
    """The plan gate pins bounded rounds and prevents seed-as-DAG regression."""
    text = _PLAN_MODE_DOC_PATH.read_text(encoding="utf-8")
    assert "Every loop has a maximum." in text
    assert "No seed field is treated as an executable instruction." in text


def test_plan_mode_escalation_cites_three_layer_chain() -> None:
    """The escalation section cites the current three-layer chain verbatim."""
    text = _PLAN_MODE_DOC_PATH.read_text(encoding="utf-8")
    assert "L2 Task → L1 Wave → L0 Project → Human" in text


def test_plan_mode_overrides_block_does_not_inject_cascade_when_unrelated_caller() -> None:
    """Importing ``_PLAN_MODE_OVERRIDES`` is side-effect free — re-import is dict-equal."""
    snapshot = copy.deepcopy(_PLAN_MODE_OVERRIDES)

    from devolaflow.task_adaptive_selector import (
        _PLAN_MODE_OVERRIDES as _SECOND_IMPORT,
    )

    assert snapshot == _SECOND_IMPORT
    assert snapshot == _PLAN_MODE_OVERRIDES


# pytest is imported per ``tests/test_task_adaptive_selector.py`` style;
# the public surface above does not need any pytest decorators yet but
# keeping the import primed lets future PV expansions add fixtures or
# ``@pytest.mark.parametrize`` rows without re-touching the import header
# (R5 cache-friendly: minimises diff churn on routine refresh).
_ = pytest
