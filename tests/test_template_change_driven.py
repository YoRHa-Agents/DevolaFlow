"""Tests for the sole executable checklist-round workflow template.

Covers:
  - Template file existence and parse-without-error
  - Schema validation (zero errors)
  - Stage identity and ordering (propose, preflight, round, archive)
  - Signed-preflight and archive gate guards
  - Bounded checklist-round loop
  - `parameters.mode` enum (lite/full, default=lite)
  - Registry registration (count = 22, path correct, opsx tag present)
  - TemplateRegistry-driven load by name

References:
  - `.local/research/v8.3.0_design.md` §7.1 (template YAML), §7.2 (registry row)
  - `.local/research/v8.3.0_patch_plan.md` §"v8.2.6"
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.models import (
    Choice,
    GateRef,
    LoopRef,
    Parallel,
    Sequence,
    StageDefinition,
    StageRef,
    WorkflowTemplate,
)
from devolaflow.template_engine.parser import parse_template
from devolaflow.template_engine.validator import validate_template

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = (
    REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin" / "change-driven.yaml"
)
REGISTRY_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "registry.yaml"


@pytest.fixture()
def template() -> WorkflowTemplate:
    """Parse the change-driven template once per test."""
    return parse_template(TEMPLATE_PATH)


# ── 1. Existence + parse + validation ────────────────────────────────


def test_template_file_exists() -> None:
    assert TEMPLATE_PATH.is_file(), f"Template not found at {TEMPLATE_PATH}"
    assert TEMPLATE_PATH.suffix == ".yaml"


def test_template_parses_without_error() -> None:
    tpl = parse_template(TEMPLATE_PATH)
    assert isinstance(tpl, WorkflowTemplate)
    assert tpl.metadata.name == "change-driven"
    assert tpl.metadata.version == "2.0.0"


def test_template_validates_clean(template: WorkflowTemplate) -> None:
    """The canonical runtime is clean and validator failure paths stay classified."""
    result = validate_template(template)
    assert result.valid, f"Validation errors: {result.errors}"
    assert len(result.errors) == 0
    non_lattice = [w for w in result.warnings if "dependency lattice" not in w]
    assert len(non_lattice) == 0, f"Unexpected non-lattice warnings: {non_lattice}"

    missing = copy.deepcopy(template)
    missing.schema_version = ""
    missing.metadata.name = ""
    missing.metadata.version = ""
    missing.stages = []
    missing_result = validate_template(missing)
    assert {"Missing schema_version", "Missing metadata.name", "Missing metadata.version"} <= set(
        missing_result.errors
    )
    assert "Template defines no stages" in missing_result.errors

    malformed = copy.deepcopy(template)
    malformed.stages[0].id = ""
    malformed.stages[0].primitive = ""
    malformed.stages[1].id = "round"
    malformed.stages[2].primitive = "execute"
    malformed.loops[0].until = ""
    malformed.loops[0].max_iterations = 0
    malformed.loops[0].escalation_target = "ghost"
    malformed.gates[0].on_pass = ""
    malformed.gates[0].on_fail.action = ""
    malformed.composition = Sequence(stages=[StageRef(stage="ghost")])
    malformed.stages.append(StageDefinition(id="orphan", primitive="review"))
    malformed_result = validate_template(malformed)
    assert any("Duplicate stage ids" in error for error in malformed_result.errors)
    assert any("invalid primitive" in error for error in malformed_result.errors)
    assert any("missing 'until'" in error for error in malformed_result.errors)
    assert any("missing 'on_pass'" in error for error in malformed_result.errors)
    assert any("unreachable" in error for error in malformed_result.errors)
    assert any("orphan" in warning for warning in malformed_result.warnings)

    lattice = copy.deepcopy(template)
    lattice.loops[0].body_stages = ["propose", "archive"]
    assert any("dependency lattice" in warning for warning in validate_template(lattice).warnings)

    nested = copy.deepcopy(template)
    nested.gates[0].on_pass = "archive"
    nested.composition = Sequence(
        stages=[
            Choice(
                condition="mode",
                if_true=StageRef(stage="propose"),
                if_false=StageRef(stage="preflight"),
            ),
            Parallel(
                stages=[
                    StageRef(stage="round"),
                    GateRef(ref="preflight_gate"),
                    GateRef(ref="missing_gate"),
                    LoopRef(ref="missing_loop"),
                ]
            ),
        ]
    )
    validate_template(nested)


# ── 2. Stage identity, primitives, and teams ─────────────────────────


def test_template_has_four_stages(template: WorkflowTemplate) -> None:
    """Stage IDs in order: propose -> preflight -> round -> archive."""
    stage_ids = [s.id for s in template.stages]
    assert stage_ids == ["propose", "preflight", "round", "archive"], (
        f"Expected 4 stages in order, got {stage_ids}"
    )

    teams = {s.id: s.team for s in template.stages}
    assert teams == {
        "propose": "design",
        "preflight": "review",
        "round": "implement",
        "archive": "implement",
    }, f"Stage team mapping mismatch: {teams}"


def test_template_metadata_category_and_tags(template: WorkflowTemplate) -> None:
    assert template.metadata.category == "composite"
    required_tags = {
        "change",
        "propose",
        "preflight",
        "round",
        "archive",
        "lifecycle",
        "agent-workspace",
    }
    actual_tags = set(template.metadata.tags)
    missing = required_tags - actual_tags
    assert not missing, f"Missing required tags: {missing}"


# ── 3. Composition shape ─────────────────────────────────────────────


def test_template_composition_is_sequence(template: WorkflowTemplate) -> None:
    """Composition sequences proposal, preflight, bounded rounds, and archive."""
    assert isinstance(template.composition, Sequence)
    assert len(template.composition.stages) == 4, (
        f"Expected 4 composition children, got {len(template.composition.stages)}"
    )

    first, second, third, fourth = template.composition.stages

    assert isinstance(first, StageRef), f"Expected StageRef, got {type(first).__name__}"
    assert first.stage == "propose"

    assert isinstance(second, StageRef), f"Expected StageRef, got {type(second).__name__}"
    assert second.stage == "preflight"

    assert isinstance(third, LoopRef), f"Expected LoopRef, got {type(third).__name__}"
    assert third.ref == "checklist_round_loop"

    assert isinstance(fourth, StageRef), f"Expected StageRef, got {type(fourth).__name__}"
    assert fourth.stage == "archive"


# ── 4. Loop definition ───────────────────────────────────────────────


def test_template_has_apply_verify_loop(template: WorkflowTemplate) -> None:
    """The only loop runs one checklist round with an absolute hard ceiling."""
    assert len(template.loops) == 1, f"Expected 1 loop, got {len(template.loops)}"
    loop = template.loops[0]
    assert loop.name == "checklist_round_loop"
    assert loop.body_stages == ["round"]
    assert loop.until == (
        "checklist.checked == checklist.total_items AND checklist.reverted_open == 0"
    )
    assert loop.max_iterations == 62
    assert loop.on_exhaustion == "escalate"


# ── 5. Gate definition ───────────────────────────────────────────────


def test_template_has_archive_gate(template: WorkflowTemplate) -> None:
    """Archive gate requires checklist completion, evidence, and mode threshold."""
    assert len(template.gates) == 2, f"Expected 2 gates, got {len(template.gates)}"
    gate = next(item for item in template.gates if item.name == "archive_gate")
    assert gate.name == "archive_gate"
    assert gate.position == "before:archive"
    assert gate.require_human_override is True
    assert gate.on_fail.action == "escalate"

    criteria_pairs = [(c.field, c.operator, c.value) for c in gate.criteria]
    assert (
        "archive.composite_score",
        ">=",
        "{{ .config.mode == 'full' ? 9.0 : 8.5 }}",
    ) in criteria_pairs, (
        f"archive_gate must enforce the mode-specific composite threshold: {criteria_pairs}"
    )


def test_archive_gate_blocks_until_pass_rate_one(template: WorkflowTemplate) -> None:
    """Archive stays blocked until checklist and evidence contracts are complete."""
    gate = next(item for item in template.gates if item.name == "archive_gate")
    pairs = [(c.field, c.operator, c.value) for c in gate.criteria]
    assert ("checklist.checked", "==", "checklist.total_items") in pairs
    assert ("checklist.reverted_open", "==", 0) in pairs
    assert ("archive.evidence_references_valid", "==", True) in pairs


# ── 6. Parameters ────────────────────────────────────────────────────


def test_template_mode_parameter(template: WorkflowTemplate) -> None:
    """parameters.mode enum default=lite, choices={lite, full}."""
    assert "mode" in template.parameters, (
        f"parameters.mode missing; got keys: {list(template.parameters.keys())}"
    )
    mode = template.parameters["mode"]
    assert mode["type"] == "enum"
    assert mode["default"] == "lite"
    assert set(mode["choices"]) == {"lite", "full"}


# ── 7. Stage-specific config ─────────────────────────────────────────


def test_apply_stage_max_iterations_config(template: WorkflowTemplate) -> None:
    """Round limits come from stage.md under an absolute safety ceiling."""
    round_stage = template.stage_by_id("round")
    assert round_stage is not None
    assert round_stage.config.get("runtime_limit_source") == "stage.md.max_rounds"
    assert round_stage.config.get("absolute_max_iterations") == 62
    assert round_stage.config.get("on_stagnation") == "escalate"


def test_verify_stage_gate_profile_template(template: WorkflowTemplate) -> None:
    """Signed preflight blocks loop entry until all three guards pass."""
    gate = next(item for item in template.gates if item.name == "preflight_gate")
    assert gate.position == "after:preflight"
    assert gate.require_human_override is True
    assert gate.on_fail.action == "escalate"
    assert gate.on_fail.target == "preflight"
    assert [
        (criterion.field, criterion.operator, criterion.value) for criterion in gate.criteria
    ] == [
        ("preflight.authorized_at", "!=", None),
        ("preflight.authorization_hash_valid", "==", True),
        ("preflight.project_config_hash_matches", "==", True),
    ]


# ── 8. Registry registration ─────────────────────────────────────────


def test_template_registered_in_registry() -> None:
    """Registry v3 keeps 23 seeds and exactly one executable path."""
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    templates = data["templates"]
    assert data["schema_version"] == "3.0"
    assert len(templates) == 7
    assert len(templates) + len(data["compositions"]) == 23
    assert sum("path" in entry for entry in templates + data["compositions"]) == 1

    cd = next((e for e in templates if e["name"] == "change-driven"), None)
    assert cd is not None, "change-driven missing from registry.yaml"
    assert cd["path"] == "builtin/change-driven.yaml"
    assert cd["seed"] == "seeds/change-driven.yaml"
    assert cd["category"] == "composite"
    for tag in (
        "change",
        "propose",
        "preflight",
        "round",
        "archive",
        "lifecycle",
        "agent-workspace",
        "opsx",
    ):
        assert tag in cd["tags"], f"Registry entry missing tag '{tag}'"


def test_template_loads_via_registry_scan() -> None:
    """TemplateRegistry can discover and load change-driven by name."""
    from devolaflow.template_engine.registry import TemplateRegistry

    templates_root = REPO_ROOT / "workflow-system" / "agent" / "templates"
    reg = TemplateRegistry(templates_root=templates_root)
    tpl = reg.load_template("change-driven")
    assert tpl is not None, "TemplateRegistry failed to load change-driven"
    assert tpl.metadata.name == "change-driven"

    metas = reg.discover(name="change-driven")
    assert len(metas) == 1
    assert metas[0].category == "composite"
