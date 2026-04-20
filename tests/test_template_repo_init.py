"""Tests for the `repo-init` workflow template (v7.4.2 — D-1/D-2/D-3/D-5/D-8 fix unit).

Covers:
  - Template file existence and parse-without-error
  - Schema validation (zero errors)
  - Stage identity and ordering
  - Registry registration (count = 20, path correct)
  - Depth-mode parameter (Option α — `parameters.mode` enum)
  - Composition shape (sequence, 4 stages)

Predecessor artifact: `.local/research/v7.4.2_gap_analysis.md` Part E §E.1-E.5.
Acceptance criteria source: S02-W1-T01 task spec, AC-1 through AC-5.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.models import Sequence, StageRef, WorkflowTemplate
from devolaflow.template_engine.parser import parse_template
from devolaflow.template_engine.validator import validate_template

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin" / "repo-init.yaml"
REGISTRY_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "registry.yaml"


@pytest.fixture()
def template() -> WorkflowTemplate:
    """Parse the repo-init template once per test."""
    return parse_template(TEMPLATE_PATH)


def test_template_file_exists() -> None:
    """AC-1: repo-init.yaml lives at the canonical path."""
    assert TEMPLATE_PATH.is_file(), f"Template not found at {TEMPLATE_PATH}"
    assert TEMPLATE_PATH.suffix == ".yaml"


def test_template_parses_without_error() -> None:
    """AC-1: parse_template returns a WorkflowTemplate (no TemplateParseError)."""
    tpl = parse_template(TEMPLATE_PATH)
    assert isinstance(tpl, WorkflowTemplate)
    assert tpl.metadata.name == "repo-init"
    assert tpl.metadata.version == "1.0.0"


def test_template_validates_clean(template: WorkflowTemplate) -> None:
    """AC-1: validate_template returns valid=True with zero errors."""
    result = validate_template(template)
    assert result.valid, f"Validation errors: {result.errors}"
    assert len(result.errors) == 0
    assert len(result.warnings) == 0, f"Unexpected warnings: {result.warnings}"


def test_template_has_four_stages(template: WorkflowTemplate) -> None:
    """AC-1: stage IDs are exactly analyze → scaffold → compile → verify (in order)."""
    stage_ids = [s.id for s in template.stages]
    assert stage_ids == ["analyze", "scaffold", "compile", "verify"], (
        f"Expected ordered [analyze, scaffold, compile, verify], got {stage_ids}"
    )

    teams = {s.id: s.team for s in template.stages}
    assert teams == {
        "analyze": "research",
        "scaffold": "implement",
        "compile": "implement",
        "verify": "test",
    }, f"Stage team mapping mismatch: {teams}"


def test_template_metadata_category_and_tags(template: WorkflowTemplate) -> None:
    """AC-1: metadata.category=='discover' and required tags present."""
    assert template.metadata.category == "discover"
    required_tags = {"init", "scaffold", "bootstrap", "repo", "workspace", "rules"}
    actual_tags = set(template.metadata.tags)
    missing = required_tags - actual_tags
    assert not missing, f"Missing required tags: {missing}"


def test_template_composition_is_sequence(template: WorkflowTemplate) -> None:
    """AC-1: composition.compose=='sequence' with 4 StageRef children in canonical order."""
    assert isinstance(template.composition, Sequence)
    assert len(template.composition.stages) == 4
    seq_ids = []
    for child in template.composition.stages:
        assert isinstance(child, StageRef), f"Expected StageRef, got {type(child).__name__}"
        seq_ids.append(child.stage)
    assert seq_ids == ["analyze", "scaffold", "compile", "verify"]


def test_template_registered_in_registry() -> None:
    """AC-2: registry.yaml lists repo-init pointing at builtin/repo-init.yaml; count == 20."""
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    templates = data["templates"]
    assert len(templates) == 20, f"Expected 20 registry entries, got {len(templates)}"

    repo_init = next((e for e in templates if e["name"] == "repo-init"), None)
    assert repo_init is not None, "repo-init missing from registry.yaml"
    assert repo_init["path"] == "builtin/repo-init.yaml"
    assert repo_init["source"] == "builtin"
    assert repo_init["version"] == "1.0.0"
    assert repo_init["category"] == "discover"
    for tag in ("init", "scaffold", "bootstrap", "repo", "workspace", "rules"):
        assert tag in repo_init["tags"], f"Registry entry missing tag '{tag}'"


def test_template_has_depth_mode_parameter(template: WorkflowTemplate) -> None:
    """AC-5 Mechanism A: parameters.mode enum (default=standard, {minimal,standard,deep})."""
    assert "mode" in template.parameters, (
        f"parameters.mode missing; got keys: {list(template.parameters.keys())}"
    )
    mode = template.parameters["mode"]
    assert mode["default"] == "standard"
    assert set(mode["choices"]) == {"minimal", "standard", "deep"}
    assert mode["type"] == "enum"


def test_verify_stage_documented_as_opt_in(template: WorkflowTemplate) -> None:
    """AC-5: the verify stage's description marks it opt-in under mode=deep."""
    verify_stage = template.stage_by_id("verify")
    assert verify_stage is not None
    desc = (verify_stage.description or "").lower()
    assert "opt-in" in desc, f"verify.description should flag opt-in semantics; got: {desc!r}"
    assert "deep" in desc, f"verify.description should reference mode=deep; got: {desc!r}"


def test_template_loads_via_registry_scan() -> None:
    """AC-2: TemplateRegistry filesystem scan picks up repo-init from builtin/."""
    from devolaflow.template_engine.registry import TemplateRegistry

    templates_root = REPO_ROOT / "workflow-system" / "agent" / "templates"
    reg = TemplateRegistry(templates_root=templates_root)
    tpl = reg.load_template("repo-init")
    assert tpl is not None, "TemplateRegistry failed to load repo-init"
    assert tpl.metadata.name == "repo-init"

    metas = reg.discover(name="repo-init")
    assert len(metas) == 1
    assert metas[0].category == "discover"
