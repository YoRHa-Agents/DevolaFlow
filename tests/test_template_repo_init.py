"""Tests for the `repo-init` workflow template.

Covers:
  - Template file existence and parse-without-error
  - Schema validation (zero errors)
  - Stage identity and ordering (5 stages: analyze, scaffold, compile, interview, verify)
  - Registry registration (count = 20, path correct)
  - Depth-mode parameter (`parameters.mode` enum: core/standard/full, default=core)
  - Composition shape (sequence, 5 stages)
  - Mode-driven runtime stage filtering via skip_condition
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.models import Sequence, StageRef, WorkflowTemplate
from devolaflow.template_engine.parser import parse_template
from devolaflow.template_engine.runtime import select_stages_for_runtime
from devolaflow.template_engine.validator import validate_template

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin" / "repo-init.yaml"
REGISTRY_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "registry.yaml"


@pytest.fixture()
def template() -> WorkflowTemplate:
    """Parse the repo-init template once per test."""
    return parse_template(TEMPLATE_PATH)


def test_template_file_exists() -> None:
    assert TEMPLATE_PATH.is_file(), f"Template not found at {TEMPLATE_PATH}"
    assert TEMPLATE_PATH.suffix == ".yaml"


def test_template_parses_without_error() -> None:
    tpl = parse_template(TEMPLATE_PATH)
    assert isinstance(tpl, WorkflowTemplate)
    assert tpl.metadata.name == "repo-init"
    assert tpl.metadata.version == "1.0.0"


def test_template_validates_clean(template: WorkflowTemplate) -> None:
    result = validate_template(template)
    assert result.valid, f"Validation errors: {result.errors}"
    assert len(result.errors) == 0
    assert len(result.warnings) == 0, f"Unexpected warnings: {result.warnings}"


def test_template_has_five_stages(template: WorkflowTemplate) -> None:
    """Stage IDs are analyze -> scaffold -> compile -> interview -> verify."""
    stage_ids = [s.id for s in template.stages]
    assert stage_ids == ["analyze", "scaffold", "compile", "interview", "verify"], (
        f"Expected 5 stages in order, got {stage_ids}"
    )

    teams = {s.id: s.team for s in template.stages}
    assert teams == {
        "analyze": "research",
        "scaffold": "implement",
        "compile": "implement",
        "interview": "research",
        "verify": "test",
    }, f"Stage team mapping mismatch: {teams}"


def test_template_metadata_category_and_tags(template: WorkflowTemplate) -> None:
    assert template.metadata.category == "discover"
    required_tags = {"init", "scaffold", "bootstrap", "repo", "workspace", "rules"}
    actual_tags = set(template.metadata.tags)
    missing = required_tags - actual_tags
    assert not missing, f"Missing required tags: {missing}"


def test_template_composition_is_sequence(template: WorkflowTemplate) -> None:
    """Composition is a sequence of 5 StageRef children."""
    assert isinstance(template.composition, Sequence)
    assert len(template.composition.stages) == 5
    seq_ids = []
    for child in template.composition.stages:
        assert isinstance(child, StageRef), f"Expected StageRef, got {type(child).__name__}"
        seq_ids.append(child.stage)
    assert seq_ids == ["analyze", "scaffold", "compile", "interview", "verify"]


def test_template_registered_in_registry() -> None:
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    templates = data["templates"]
    assert len(templates) == 21, f"Expected 21 registry entries, got {len(templates)}"

    repo_init = next((e for e in templates if e["name"] == "repo-init"), None)
    assert repo_init is not None, "repo-init missing from registry.yaml"
    assert repo_init["path"] == "builtin/repo-init.yaml"
    assert repo_init["source"] == "builtin"
    assert repo_init["version"] == "1.0.0"
    assert repo_init["category"] == "discover"
    for tag in ("init", "scaffold", "bootstrap", "repo", "workspace", "rules"):
        assert tag in repo_init["tags"], f"Registry entry missing tag '{tag}'"


def test_template_has_depth_mode_parameter(template: WorkflowTemplate) -> None:
    """parameters.mode enum with default=core, choices={core, standard, full}."""
    assert "mode" in template.parameters, (
        f"parameters.mode missing; got keys: {list(template.parameters.keys())}"
    )
    mode = template.parameters["mode"]
    assert mode["default"] == "core"
    assert set(mode["choices"]) == {"core", "standard", "full"}
    assert mode["type"] == "enum"


def test_verify_stage_documented_as_opt_in(template: WorkflowTemplate) -> None:
    verify_stage = template.stage_by_id("verify")
    assert verify_stage is not None
    desc = (verify_stage.description or "").lower()
    assert "opt-in" in desc, f"verify.description should flag opt-in semantics; got: {desc!r}"
    assert "full" in desc, f"verify.description should reference mode=full; got: {desc!r}"


def test_template_loads_via_registry_scan() -> None:
    from devolaflow.template_engine.registry import TemplateRegistry

    templates_root = REPO_ROOT / "workflow-system" / "agent" / "templates"
    reg = TemplateRegistry(templates_root=templates_root)
    tpl = reg.load_template("repo-init")
    assert tpl is not None, "TemplateRegistry failed to load repo-init"
    assert tpl.metadata.name == "repo-init"

    metas = reg.discover(name="repo-init")
    assert len(metas) == 1
    assert metas[0].category == "discover"


# ── Mode-driven runtime stage filtering ──────────────────────────────


def test_repo_init_verify_has_skip_condition(template: WorkflowTemplate) -> None:
    """verify stage carries `mode != 'full'` skip_condition."""
    verify_stage = template.stage_by_id("verify")
    assert verify_stage is not None
    assert verify_stage.skip_condition == "mode != 'full'", (
        f"Expected skip_condition \"mode != 'full'\", got: {verify_stage.skip_condition!r}"
    )


def test_repo_init_compile_has_skip_condition(template: WorkflowTemplate) -> None:
    """compile stage carries `mode == 'core'` skip_condition."""
    compile_stage = template.stage_by_id("compile")
    assert compile_stage is not None
    assert compile_stage.skip_condition == "mode == 'core'", (
        f"Expected skip_condition \"mode == 'core'\", got: {compile_stage.skip_condition!r}"
    )


def test_repo_init_interview_has_skip_condition(template: WorkflowTemplate) -> None:
    """interview stage carries `mode != 'full'` skip_condition (v7.7 placeholder)."""
    interview_stage = template.stage_by_id("interview")
    assert interview_stage is not None
    assert interview_stage.skip_condition == "mode != 'full'"


def test_select_stages_for_runtime_default_uses_core(template: WorkflowTemplate) -> None:
    """Default mode is core (per parameters.mode.default), yielding 2 stages."""
    refs = select_stages_for_runtime(template)
    ids = [r.stage for r in refs]
    assert ids == ["analyze", "scaffold"], f"Default mode (core) should yield 2 stages; got {ids}"


def test_select_stages_for_runtime_core(template: WorkflowTemplate) -> None:
    """mode='core' returns 2 stages (analyze + scaffold)."""
    refs = select_stages_for_runtime(template, mode="core")
    ids = [r.stage for r in refs]
    assert ids == ["analyze", "scaffold"], f"mode='core' should yield 2 stages; got {ids}"


def test_select_stages_for_runtime_standard(template: WorkflowTemplate) -> None:
    """mode='standard' returns 3 stages (analyze + scaffold + compile)."""
    refs = select_stages_for_runtime(template, mode="standard")
    ids = [r.stage for r in refs]
    assert ids == ["analyze", "scaffold", "compile"], (
        f"mode='standard' should yield 3 stages; got {ids}"
    )


def test_select_stages_for_runtime_full(template: WorkflowTemplate) -> None:
    """mode='full' returns all 5 stages."""
    refs = select_stages_for_runtime(template, mode="full")
    ids = [r.stage for r in refs]
    assert ids == ["analyze", "scaffold", "compile", "interview", "verify"], (
        f"mode='full' should yield all 5 stages; got {ids}"
    )


def test_select_stages_for_runtime_environment_modes_noop(template: WorkflowTemplate) -> None:
    """Empty environment_modes blocks are no-op."""
    local = [r.stage for r in select_stages_for_runtime(template, environment="local")]
    github = [r.stage for r in select_stages_for_runtime(template, environment="github")]
    assert local == github == ["analyze", "scaffold"], (
        f"Empty environment_modes must be no-op; local={local}, github={github}"
    )
