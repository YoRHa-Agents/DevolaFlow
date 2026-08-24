"""Tests for the ``repo-init`` checklist seed.

Covers:
  - registry-v3 seed loading and metadata
  - five historical stage pairs as provenance only
  - the eight-path canonical-manifest assertion
  - sole executable ``change-driven`` runtime registration
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.models import WorkflowTemplate
from devolaflow.template_engine.registry import TemplateRegistry
from devolaflow.template_engine.seeds import ChecklistSeed

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = REPO_ROOT / "workflow-system" / "agent" / "templates"
TEMPLATE_PATH = TEMPLATES_ROOT / "seeds" / "repo-init.yaml"
REGISTRY_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "registry.yaml"


@pytest.fixture()
def template() -> ChecklistSeed:
    """Load and strictly validate the repo-init seed once per test."""
    seed = TemplateRegistry(TEMPLATES_ROOT).load_seed("repo-init")
    assert seed is not None
    return seed


def test_template_file_exists() -> None:
    assert TEMPLATE_PATH.is_file(), f"Template not found at {TEMPLATE_PATH}"
    assert TEMPLATE_PATH.suffix == ".yaml"


def test_template_parses_without_error() -> None:
    seed = TemplateRegistry(TEMPLATES_ROOT).load_seed("repo-init")
    assert isinstance(seed, ChecklistSeed)
    assert seed.metadata.name == "repo-init"
    assert seed.metadata.version == "1.0.0"


def test_template_validates_clean(template: WorkflowTemplate) -> None:
    assert template.schema_version == "1.0"
    assert template.kind == "checklist-seed"
    assert template.partitions
    assert all(partition.assertions for partition in template.partitions)


def test_template_has_five_stages(template: WorkflowTemplate) -> None:
    """Retain five historical id/primitive pairs as provenance only."""
    assert template.source_stage_sequence() == [
        ("analyze", "analyze"),
        ("scaffold", "implement"),
        ("compile", "implement"),
        ("interview", "analyze"),
        ("verify", "verify"),
    ]
    assert not hasattr(template, "team")


def test_template_metadata_category_and_tags(template: WorkflowTemplate) -> None:
    assert template.metadata.category == "discover"
    required_tags = {"init", "scaffold", "bootstrap", "repo", "workspace", "rules"}
    actual_tags = set(template.metadata.intent_keywords)
    missing = required_tags - actual_tags
    assert not missing, f"Missing required tags: {missing}"


def test_template_composition_is_sequence(template: WorkflowTemplate) -> None:
    """Registry-v3 seeds contain no executable DAG fields."""
    assert not hasattr(template, "composition")
    assert not hasattr(template, "loops")
    assert not hasattr(template, "gates")


def test_template_registered_in_registry() -> None:
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    entries = data["compositions"] + data["templates"]
    assert len(entries) == 23
    repo_init = next((e for e in entries if e["name"] == "repo-init"), None)
    assert repo_init is not None, "repo-init missing from registry.yaml"
    assert repo_init["seed"] == "seeds/repo-init.yaml"
    assert "path" not in repo_init
    assert repo_init["category"] == "discover"
    for tag in ("init", "scaffold", "bootstrap", "repo", "workspace", "rules"):
        assert tag in repo_init["tags"], f"Registry entry missing tag '{tag}'"
    assert [entry["name"] for entry in entries if "path" in entry] == ["change-driven"]


def test_template_has_depth_mode_parameter(template: WorkflowTemplate) -> None:
    """Depth is chosen during checklist materialization, not by seed execution."""
    assert template.placeholders == {}
    assert not hasattr(template, "parameters")


def test_verify_stage_documented_as_opt_in(template: WorkflowTemplate) -> None:
    assertion = next(
        assertion
        for partition in template.partitions
        for assertion in partition.assertions
        if assertion.key == "initialization-verified"
    )
    assert "requested initialization depth" in assertion.statement_template.lower()
    assert "degraded optional tooling" in assertion.statement_template.lower()


def test_template_loads_via_registry_scan() -> None:
    reg = TemplateRegistry(templates_root=TEMPLATES_ROOT)
    seed = reg.load_seed("repo-init")
    assert seed is not None, "TemplateRegistry failed to load repo-init seed"
    assert seed.metadata.name == "repo-init"

    metas = reg.discover(name="repo-init")
    assert len(metas) == 1
    assert metas[0].category == "discover"


# ── Mode-driven runtime stage filtering ──────────────────────────────


def test_repo_init_verify_has_skip_condition(template: WorkflowTemplate) -> None:
    """Verify is retained as provenance without a runtime skip condition."""
    assert ("verify", "verify") in template.source_stage_sequence()
    assert not hasattr(template, "skip_condition")


def test_repo_init_compile_has_skip_condition(template: WorkflowTemplate) -> None:
    """Compile is retained as provenance without executable gating."""
    assert ("compile", "implement") in template.source_stage_sequence()
    assert not hasattr(template, "skip_condition")


def test_repo_init_interview_has_skip_condition(template: WorkflowTemplate) -> None:
    """Interview is retained as provenance without executable gating."""
    assert ("interview", "analyze") in template.source_stage_sequence()
    assert not hasattr(template, "skip_condition")


def test_select_stages_for_runtime_default_uses_core(template: WorkflowTemplate) -> None:
    """Seed selection does not select executable stages."""
    runtime = TemplateRegistry(TEMPLATES_ROOT).load_template("change-driven")
    assert runtime is not None
    assert runtime.metadata.name == "change-driven"
    assert template.source_stage_sequence()


def test_select_stages_for_runtime_core(template: WorkflowTemplate) -> None:
    """Core remains an operator materialization choice, not seed execution."""
    runtime = TemplateRegistry(TEMPLATES_ROOT).load_template("change-driven")
    assert runtime is not None
    assert "mode" not in template.placeholders


def test_select_stages_for_runtime_standard(template: WorkflowTemplate) -> None:
    """Standard remains an operator materialization choice, not seed execution."""
    runtime = TemplateRegistry(TEMPLATES_ROOT).load_template("change-driven")
    assert runtime is not None
    assert not hasattr(template, "stages")


def test_select_stages_for_runtime_full(template: WorkflowTemplate) -> None:
    """Full remains an operator materialization choice, not seed execution."""
    runtime = TemplateRegistry(TEMPLATES_ROOT).load_template("change-driven")
    assert runtime is not None
    assert len(template.source_stage_sequence()) == 5


def test_select_stages_for_runtime_environment_modes_noop(template: WorkflowTemplate) -> None:
    """Seeds carry no environment-dependent execution mode."""
    assert not hasattr(template, "environment_modes")
    assert TemplateRegistry(TEMPLATES_ROOT).load_template("change-driven") is not None
