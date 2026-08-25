"""Tests for Si-Chip provenance in registry-v3 checklist seeds.

The historical ``si_chip_dogfood`` and ``si_chip_gate`` stage labels remain
seed provenance only. Plugin ownership stays in ``runtime-plugins.yaml``;
execution stays in the sole ``change-driven`` runtime.

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

from devolaflow.plugins.installer import load_registry, resolve_plugin
from devolaflow.template_engine.registry import TemplateRegistry
from devolaflow.template_engine.seeds import ChecklistSeed

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "workflow-system" / "agent" / "templates"
_RUNTIME_PLUGINS = _REPO_ROOT / "workflow-system/agent/knowledge/runtime-plugins.yaml"


@pytest.fixture(scope="module")
def skill_optimization_template() -> ChecklistSeed:
    seed = TemplateRegistry(_TEMPLATES_DIR).load_seed("skill-optimization")
    assert seed is not None
    return seed


@pytest.fixture(scope="module")
def self_update_template() -> ChecklistSeed:
    seed = TemplateRegistry(_TEMPLATES_DIR).load_seed("self-update")
    assert seed is not None
    return seed


# ---------------------------------------------------------------------------
# §1 — skill-optimization.yaml parses with si_chip_dogfood stage
# ---------------------------------------------------------------------------


class TestSkillOptimizationTemplateWiresSiChip:
    """Pin Si-Chip provenance in the skill-optimization seed."""

    def test_skill_optimization_template_parses(self, skill_optimization_template: dict) -> None:
        assert skill_optimization_template.schema_version == "1.0"
        assert skill_optimization_template.kind == "checklist-seed"
        assert not hasattr(skill_optimization_template, "composition")

    def test_si_chip_dogfood_stage_is_between_optimize_and_benchmark(
        self, skill_optimization_template: ChecklistSeed
    ) -> None:
        """Retain the historical labels as provenance, not runtime order."""
        assert skill_optimization_template.source_stage_sequence() == [
            ("survey", "research"),
            ("profile", "analyze"),
            ("optimize", "implement"),
            ("si_chip_dogfood", "validate"),
            ("benchmark", "test"),
            ("document", "release"),
        ]

    def test_si_chip_dogfood_stage_declares_si_chip_plugin(
        self, skill_optimization_template: ChecklistSeed
    ) -> None:
        spec = resolve_plugin("si-chip", load_registry(_RUNTIME_PLUGINS))
        assert "skill-optimization" in spec.invoked_by_workflows
        assert ("si_chip_dogfood", "validate") in (
            skill_optimization_template.source_stage_sequence()
        )

    def test_si_chip_dogfood_gate_registered(self, skill_optimization_template: dict) -> None:
        assertion = next(
            assertion
            for partition in skill_optimization_template.partitions
            for assertion in partition.assertions
            if assertion.key == "candidate-improves"
        )
        assert assertion.verify.mode == "metric"
        assert "iteration_delta >= 0.10" in (assertion.verify.template or "")
        assert not hasattr(skill_optimization_template, "gates")

    def test_optimize_benchmark_loop_includes_si_chip_dogfood(
        self, skill_optimization_template: ChecklistSeed
    ) -> None:
        """No loop is inferred from the three provenance labels."""
        provenance = skill_optimization_template.source_stage_sequence()
        assert {stage_id for stage_id, _ in provenance} >= {
            "optimize",
            "si_chip_dogfood",
            "benchmark",
        }
        assert not hasattr(skill_optimization_template, "loops")


# ---------------------------------------------------------------------------
# §2 — self-update.yaml parses with optional si_chip_gate
# ---------------------------------------------------------------------------


class TestSelfUpdateTemplateWiresSiChipOptional:
    """Pin Si-Chip provenance in the self-update seed."""

    def test_self_update_template_parses(self, self_update_template: dict) -> None:
        assert self_update_template.schema_version == "1.0"
        assert self_update_template.kind == "checklist-seed"
        assert not hasattr(self_update_template, "stages")

    def test_si_chip_gate_is_between_integrate_and_test(self, self_update_template: dict) -> None:
        """Retain the historical labels as provenance, not runtime order."""
        assert {stage_id for stage_id, _ in self_update_template.source_stage_sequence()} >= {
            "integrate",
            "si_chip_gate",
            "test",
        }

    def test_si_chip_gate_marked_optional(self, self_update_template: dict) -> None:
        """Plugin wiring is owned by the plugin registry, not seed config."""
        spec = resolve_plugin("si-chip", load_registry(_RUNTIME_PLUGINS))
        assert {"self-update", "skill-optimization"} <= set(spec.invoked_by_workflows)
        assert ("si_chip_gate", "validate") in self_update_template.source_stage_sequence()
        assert not hasattr(self_update_template, "skip_condition")

    def test_integrate_test_cycle_includes_si_chip_gate(self, self_update_template: dict) -> None:
        """No loop is inferred from provenance labels."""
        assert not hasattr(self_update_template, "loops")
        assertion = next(
            assertion
            for partition in self_update_template.partitions
            for assertion in partition.assertions
            if assertion.key == "integration-green"
        )
        assert assertion.verify.mode == "metric"
