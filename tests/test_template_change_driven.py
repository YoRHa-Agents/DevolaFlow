"""Tests for the `change-driven` workflow template (v8.2.6).

Covers:
  - Template file existence and parse-without-error
  - Schema validation (zero errors)
  - Stage identity and ordering (4 stages: propose, apply, verify, archive)
  - Stage primitives, teams, and `apply`/`verify`/`archive` config wiring
  - Composition shape (sequence: StageRef → LoopRef → StageRef)
  - `apply_verify_loop` definition (body_stages, max_iterations, on_exhaustion)
  - `archive_gate` definition (criteria, position, require_human_override)
  - `parameters.mode` enum (lite/full, default=lite)
  - Registry registration (count = 22, path correct, opsx tag present)
  - TemplateRegistry-driven load by name

References:
  - `.local/research/v8.3.0_design.md` §7.1 (template YAML), §7.2 (registry row)
  - `.local/research/v8.3.0_patch_plan.md` §"v8.2.6"
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.models import (
    LoopRef,
    Sequence,
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
    assert tpl.metadata.version == "1.0.0"


def test_template_validates_clean(template: WorkflowTemplate) -> None:
    """Template parses with zero errors and zero non-soft warnings.

    The change-driven loop compresses the canonical implement→test→verify
    chain into a single `verify` stage that subsumes both, producing one
    dependency-lattice warning ('apply'(implement) → 'verify'(verify)). The
    lattice check is documented as warning-only in
    ``validator.py::check_dependency_lattice`` and 8 of the 21 pre-existing
    builtin templates carry analogous transitions (feature-enhancement,
    full-pipeline, migration, nines-assisted, product-verification,
    research-design-review-refine, security-audit, plus this one). We pin
    "no errors" and "no NON-lattice warnings" to catch real validation drift
    without flagging the intentional lattice compression.
    """
    result = validate_template(template)
    assert result.valid, f"Validation errors: {result.errors}"
    assert len(result.errors) == 0
    non_lattice = [w for w in result.warnings if "dependency lattice" not in w]
    assert len(non_lattice) == 0, f"Unexpected non-lattice warnings: {non_lattice}"


# ── 2. Stage identity, primitives, and teams ─────────────────────────


def test_template_has_four_stages(template: WorkflowTemplate) -> None:
    """Stage IDs in order: propose -> apply -> verify -> archive."""
    stage_ids = [s.id for s in template.stages]
    assert stage_ids == ["propose", "apply", "verify", "archive"], (
        f"Expected 4 stages in order, got {stage_ids}"
    )

    teams = {s.id: s.team for s in template.stages}
    assert teams == {
        "propose": "design",
        "apply": "implement",
        "verify": "test",
        "archive": "implement",
    }, f"Stage team mapping mismatch: {teams}"


def test_template_metadata_category_and_tags(template: WorkflowTemplate) -> None:
    assert template.metadata.category == "composite"
    required_tags = {"change", "propose", "apply", "archive", "lifecycle", "agent-workspace"}
    actual_tags = set(template.metadata.tags)
    missing = required_tags - actual_tags
    assert not missing, f"Missing required tags: {missing}"


# ── 3. Composition shape ─────────────────────────────────────────────


def test_template_composition_is_sequence(template: WorkflowTemplate) -> None:
    """Composition is a Sequence with 3 children:
    StageRef(propose), LoopRef(apply_verify_loop), StageRef(archive)."""
    assert isinstance(template.composition, Sequence)
    assert len(template.composition.stages) == 3, (
        f"Expected 3 composition children, got {len(template.composition.stages)}"
    )

    first, second, third = template.composition.stages

    assert isinstance(first, StageRef), f"Expected StageRef, got {type(first).__name__}"
    assert first.stage == "propose"

    assert isinstance(second, LoopRef), f"Expected LoopRef, got {type(second).__name__}"
    assert second.ref == "apply_verify_loop"

    assert isinstance(third, StageRef), f"Expected StageRef, got {type(third).__name__}"
    assert third.stage == "archive"


# ── 4. Loop definition ───────────────────────────────────────────────


def test_template_has_apply_verify_loop(template: WorkflowTemplate) -> None:
    """Loops list has exactly 1 entry: apply_verify_loop with body=[apply, verify]."""
    assert len(template.loops) == 1, f"Expected 1 loop, got {len(template.loops)}"
    loop = template.loops[0]
    assert loop.name == "apply_verify_loop"
    assert loop.body_stages == ["apply", "verify"]
    assert loop.max_iterations == 5
    assert loop.on_exhaustion == "escalate"


# ── 5. Gate definition ───────────────────────────────────────────────


def test_template_has_archive_gate(template: WorkflowTemplate) -> None:
    """Gates list has exactly 1 entry: archive_gate with composite>=8.5 + human override."""
    assert len(template.gates) == 1, f"Expected 1 gate, got {len(template.gates)}"
    gate = template.gates[0]
    assert gate.name == "archive_gate"
    assert gate.position == "before:archive"
    assert gate.require_human_override is True
    assert gate.on_fail.action == "escalate"

    criteria_pairs = [(c.field, c.operator, c.value) for c in gate.criteria]
    assert ("verify.gate_score", ">=", 8.5) in criteria_pairs, (
        f"archive_gate must enforce composite ≥ 8.5; got criteria: {criteria_pairs}"
    )


def test_archive_gate_blocks_until_pass_rate_one(template: WorkflowTemplate) -> None:
    """archive_gate criteria includes verify.pass_rate == 1.0."""
    gate = template.gates[0]
    pairs = [(c.field, c.operator, c.value) for c in gate.criteria]
    assert ("verify.pass_rate", "==", 1.0) in pairs, (
        f"archive_gate must require verify.pass_rate == 1.0; got: {pairs}"
    )


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
    """apply stage carries config.max_iterations==5 and config.on_stagnation==escalate."""
    apply_stage = template.stage_by_id("apply")
    assert apply_stage is not None
    assert apply_stage.config.get("max_iterations") == 5
    assert apply_stage.config.get("on_stagnation") == "escalate"


def test_verify_stage_gate_profile_template(template: WorkflowTemplate) -> None:
    """verify stage config.gate_profile uses a Jinja-style template that references config.mode."""
    verify_stage = template.stage_by_id("verify")
    assert verify_stage is not None
    gate_profile = verify_stage.config.get("gate_profile", "")
    assert "{{" in gate_profile and "}}" in gate_profile, (
        f"verify.config.gate_profile must be a Jinja-style template; got: {gate_profile!r}"
    )
    assert "config.mode" in gate_profile or "mode" in gate_profile, (
        f"verify.config.gate_profile must reference config.mode; got: {gate_profile!r}"
    )


# ── 8. Registry registration ─────────────────────────────────────────


def test_template_registered_in_registry() -> None:
    """Registry now has 22 entries including the change-driven row."""
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    templates = data["templates"]
    assert len(templates) == 22, f"Expected 22 registry entries, got {len(templates)}"

    cd = next((e for e in templates if e["name"] == "change-driven"), None)
    assert cd is not None, "change-driven missing from registry.yaml"
    assert cd["path"] == "builtin/change-driven.yaml"
    assert cd["source"] == "builtin"
    assert cd["version"] == "1.0.0"
    assert cd["category"] == "composite"
    for tag in ("change", "propose", "apply", "archive", "lifecycle", "agent-workspace", "opsx"):
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
