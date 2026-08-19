"""Tests for the v9.5.0 PV-03 template wiring of the Si-Chip dogfood stage.

Pins the contract for the ``si_chip_dogfood`` stage in
``skill-optimization.yaml`` and the optional ``si_chip_gate`` stage in
``self-update.yaml``.

Test surfaces (kept tight per W-17 +30/PV cap):

1. ``skill-optimization.yaml`` parses cleanly with new stage in correct
   slot (between optimize and benchmark).
2. ``self-update.yaml`` parses cleanly with optional new stage (between
   integrate and test).
3. The new gate ``si_chip_dogfood_gate`` is registered in
   ``skill-optimization.yaml`` after the new stage.
4. Both stages declare ``suggest_plugins: ["si-chip"]`` (v15.2.0 B-6
   rename; probe semantics) so the v9.4.0 dispatcher pre-flight
   (`pre_plugin_invocation` hook) installs Si-Chip when the operator
   opted in via DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1.
5. The ``self-update.yaml`` ``si_chip_gate`` stage is marked optional
   so v9.4.x callers without skill-corpus-touch get byte-identical
   behaviour.

Source: `.local/research/v9.5.0_gap_analysis.md` §3.1 D-S-3 + §6 AC-8.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin"


@pytest.fixture(scope="module")
def skill_optimization_template() -> dict:
    return yaml.safe_load((_TEMPLATES_DIR / "skill-optimization.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def self_update_template() -> dict:
    return yaml.safe_load((_TEMPLATES_DIR / "self-update.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# §1 — skill-optimization.yaml parses with si_chip_dogfood stage
# ---------------------------------------------------------------------------


class TestSkillOptimizationTemplateWiresSiChip:
    """Pin the new stage in ``skill-optimization.yaml``."""

    def test_skill_optimization_template_parses(self, skill_optimization_template: dict) -> None:
        """Template loads as valid YAML + has expected top-level keys."""
        assert skill_optimization_template["schema_version"] == "1.0"
        assert "stages" in skill_optimization_template
        assert "composition" in skill_optimization_template
        assert "gates" in skill_optimization_template

    def test_si_chip_dogfood_stage_is_between_optimize_and_benchmark(
        self, skill_optimization_template: dict
    ) -> None:
        """Stage order: survey → profile → optimize → si_chip_dogfood → benchmark → document."""
        stage_ids = [s["id"] for s in skill_optimization_template["stages"]]
        assert stage_ids == [
            "survey",
            "profile",
            "optimize",
            "si_chip_dogfood",
            "benchmark",
            "document",
        ], (
            f"v9.5.0 PV-03 contract: si_chip_dogfood MUST be between "
            f"optimize and benchmark (the +0.10 iteration_delta gate "
            f"runs BEFORE the slower EvoBench benchmark). Actual: {stage_ids!r}"
        )

    def test_si_chip_dogfood_stage_declares_si_chip_plugin(
        self, skill_optimization_template: dict
    ) -> None:
        """Stage MUST cite si-chip in suggest_plugins for the dispatcher pre-flight."""
        stage = next(
            s for s in skill_optimization_template["stages"] if s["id"] == "si_chip_dogfood"
        )
        assert stage["primitive"] == "validate"
        assert stage["team"] == "test"
        assert stage["config"]["suggest_plugins"] == ["si-chip"], (
            "si_chip_dogfood stage MUST cite ['si-chip'] in suggest_plugins "
            "so v9.4.0 PV-02's pre_plugin_invocation hook auto-installs "
            "Si-Chip before the L3 Task Agent attempts to call its scripts."
        )
        assert stage["config"]["threshold"] == 0.10, (
            "Threshold MUST be the Si-Chip spec §23 default of +0.10"
        )
        assert stage["config"]["bridge_module"] == "devolaflow.si_chip_bridge"
        assert stage["config"]["bridge_entry_point"] == "run_dogfood_cycle"

    def test_si_chip_dogfood_gate_registered(self, skill_optimization_template: dict) -> None:
        """A new gate `si_chip_dogfood_gate` MUST follow the new stage."""
        gate_names = [g["name"] for g in skill_optimization_template["gates"]]
        assert "si_chip_dogfood_gate" in gate_names, (
            f"v9.5.0 PV-03 contract: a new gate `si_chip_dogfood_gate` MUST "
            f"be registered after the si_chip_dogfood stage to enforce the "
            f"APPLY/DEFER verdict. Actual gates: {gate_names!r}"
        )
        gate = next(
            g for g in skill_optimization_template["gates"] if g["name"] == "si_chip_dogfood_gate"
        )
        assert gate["position"] == "after:si_chip_dogfood"
        # APPLY → next; DEFER → loop back to optimize for another candidate
        assert gate["on_fail"]["action"] == "loop_back"
        assert gate["on_fail"]["target"] == "optimize"

    def test_optimize_benchmark_loop_includes_si_chip_dogfood(
        self, skill_optimization_template: dict
    ) -> None:
        """The optimize→benchmark loop body MUST include the new stage."""
        loop = next(
            entry
            for entry in skill_optimization_template["loops"]
            if entry["name"] == "optimize_benchmark_loop"
        )
        assert loop["body_stages"] == ["optimize", "si_chip_dogfood", "benchmark"], (
            f"Loop body MUST be [optimize, si_chip_dogfood, benchmark] so "
            f"the iteration_delta gate runs in every loop iteration "
            f"BEFORE the heavier benchmark gate. Actual: {loop['body_stages']!r}"
        )


# ---------------------------------------------------------------------------
# §2 — self-update.yaml parses with optional si_chip_gate
# ---------------------------------------------------------------------------


class TestSelfUpdateTemplateWiresSiChipOptional:
    """Pin the optional `si_chip_gate` in ``self-update.yaml``."""

    def test_self_update_template_parses(self, self_update_template: dict) -> None:
        assert self_update_template["schema_version"] == "1.0"
        assert "stages" in self_update_template

    def test_si_chip_gate_is_between_integrate_and_test(self, self_update_template: dict) -> None:
        """Stage order: ... integrate → si_chip_gate → test → ...."""
        stage_ids = [s["id"] for s in self_update_template["stages"]]
        try:
            i_integrate = stage_ids.index("integrate")
            i_gate = stage_ids.index("si_chip_gate")
            i_test = stage_ids.index("test")
        except ValueError as exc:
            pytest.fail(f"missing expected stage in self-update.yaml: {exc}")
        assert i_integrate < i_gate < i_test, (
            f"v9.5.0 PV-03 contract: si_chip_gate MUST be between integrate "
            f"and test. Actual stage order: {stage_ids!r}"
        )

    def test_si_chip_gate_marked_optional(self, self_update_template: dict) -> None:
        """Skip-when honoured: preserves v9.4.x byte-stable when skill-corpus untouched."""
        stage = next(s for s in self_update_template["stages"] if s["id"] == "si_chip_gate")
        assert stage.get("optional") is True, (
            "si_chip_gate MUST be marked optional (optional: true) so "
            "self-update workflows that don't touch workflow-system/agent/ "
            "skip it entirely — preserves v9.4.x byte-stable behaviour."
        )
        # Skip-when condition references _context.requires_skill_corpus_touch
        skip_when = stage["config"].get("skip_when", "")
        assert "requires_skill_corpus_touch" in skip_when, (
            f"si_chip_gate skip_when MUST reference requires_skill_corpus_touch "
            f"context flag; got {skip_when!r}"
        )
        assert stage["config"]["suggest_plugins"] == ["si-chip"]
        assert stage["config"]["bridge_module"] == "devolaflow.si_chip_bridge"

    def test_integrate_test_cycle_includes_si_chip_gate(self, self_update_template: dict) -> None:
        """The integrate→test loop body MUST include the optional gate."""
        loop = next(
            entry
            for entry in self_update_template["loops"]
            if entry["name"] == "integrate_test_cycle"
        )
        assert loop["body_stages"] == ["integrate", "si_chip_gate", "test"], (
            f"v9.5.0 PV-03 contract: integrate_test_cycle body MUST be "
            f"[integrate, si_chip_gate, test]. Actual: {loop['body_stages']!r}"
        )
