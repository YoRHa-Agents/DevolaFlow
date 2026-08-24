"""Tests for the v13.0.0 ``web-design`` checklist seed.

Covers:
  - registry-v3 seed loading and metadata
  - historical ``source_stages`` provenance
  - ui-pro/impeccable plugin registration
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
TEMPLATE_PATH = TEMPLATES_ROOT / "seeds" / "web-design.yaml"
REGISTRY_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "registry.yaml"


@pytest.fixture()
def template() -> ChecklistSeed:
    seed = TemplateRegistry(TEMPLATES_ROOT).load_seed("web-design")
    assert seed is not None
    return seed


def test_template_file_exists() -> None:
    assert TEMPLATE_PATH.is_file(), f"Template not found at {TEMPLATE_PATH}"


def test_template_parses_and_validates_clean(template: WorkflowTemplate) -> None:
    assert template.metadata.name == "web-design"
    assert template.schema_version == "1.0"
    assert template.kind == "checklist-seed"
    assert template.partitions


def test_template_has_four_stages_in_order(template: WorkflowTemplate) -> None:
    """Retain four historical id/primitive pairs as provenance only."""
    assert template.source_stage_sequence() == [
        ("design", "design"),
        ("implement", "implement"),
        ("refine", "refine"),
        ("verify", "verify"),
    ]
    assert not hasattr(template, "composition")


def test_suggest_plugins_wiring(template: WorkflowTemplate) -> None:
    """Plugin ownership stays in the runtime registry, not executable seed config."""
    runtime_plugins = yaml.safe_load(
        (REPO_ROOT / "workflow-system/agent/knowledge/runtime-plugins.yaml").read_text(
            encoding="utf-8"
        )
    )
    by_id = {entry["id"]: entry for entry in runtime_plugins["plugins"]}
    assert "web-design" in by_id["ui-pro"]["invoked_by_workflows"]
    assert "web-design" in by_id["impeccable"]["invoked_by_workflows"]
    assert {"ui-pro", "impeccable"} <= set(template.metadata.intent_keywords)


def test_verify_carries_antipattern_gate(template: WorkflowTemplate) -> None:
    """The materializable assertion retains deterministic antipattern evidence."""
    assertion = next(
        assertion
        for partition in template.partitions
        for assertion in partition.assertions
        if assertion.key == "antipatterns-clear"
    )
    assert "Impeccable" in assertion.statement_template
    assert assertion.verify.mode == "metric"
    assert assertion.verify.template == "antipattern_count == 0"


def test_composition_is_sequence_with_convergence_loop(template: WorkflowTemplate) -> None:
    """Seeds carry no execution order, loops, gates, or teams."""
    assert not hasattr(template, "composition")
    assert not hasattr(template, "loops")
    assert not hasattr(template, "gates")
    assert not hasattr(template, "team")


def test_template_registered_in_registry() -> None:
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    web_design = next((e for e in data["templates"] if e["name"] == "web-design"), None)
    assert web_design is not None, "web-design missing from registry.yaml"
    assert web_design["seed"] == "seeds/web-design.yaml"
    assert "path" not in web_design
    assert web_design["category"] == "composite"
    for tag in ("web-design", "ui-pro", "impeccable"):
        assert tag in web_design["tags"], f"registry entry missing tag {tag!r}"
    executable = [entry for entry in data["compositions"] + data["templates"] if "path" in entry]
    assert [entry["name"] for entry in executable] == ["change-driven"]
