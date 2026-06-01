"""Tests for the v13.0.0 `web-design` workflow template.

Covers:
  - Template file existence + parse-without-error
  - Schema validation (zero errors, zero warnings)
  - Stage identity + ordering (design → implement → refine → verify)
  - ensure_plugins wiring: ui-pro on design, impeccable on refine + verify
  - Composition shape (sequence with refine↔verify convergence loop + gate)
  - Registry registration
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.models import Sequence, WorkflowTemplate
from devolaflow.template_engine.parser import parse_template
from devolaflow.template_engine.validator import validate_template

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = (
    REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin" / "web-design.yaml"
)
REGISTRY_PATH = REPO_ROOT / "workflow-system" / "agent" / "templates" / "registry.yaml"


@pytest.fixture()
def template() -> WorkflowTemplate:
    return parse_template(TEMPLATE_PATH)


def test_template_file_exists() -> None:
    assert TEMPLATE_PATH.is_file(), f"Template not found at {TEMPLATE_PATH}"


def test_template_parses_and_validates_clean(template: WorkflowTemplate) -> None:
    assert template.metadata.name == "web-design"
    result = validate_template(template)
    assert result.valid, f"Validation errors: {result.errors}"
    assert len(result.errors) == 0
    assert len(result.warnings) == 0, f"Unexpected warnings: {result.warnings}"


def test_template_has_four_stages_in_order(template: WorkflowTemplate) -> None:
    stage_ids = [s.id for s in template.stages]
    assert stage_ids == ["design", "implement", "refine", "verify"], (
        f"Expected design→implement→refine→verify, got {stage_ids}"
    )
    primitives = {s.id: s.primitive for s in template.stages}
    assert primitives == {
        "design": "design",
        "implement": "implement",
        "refine": "refine",
        "verify": "verify",
    }, f"primitive mapping mismatch: {primitives}"


def test_ensure_plugins_wiring(template: WorkflowTemplate) -> None:
    """ui-pro DESIGNS (design stage); impeccable REFINES + VERIFIES."""
    by_id = {s.id: s for s in template.stages}
    assert by_id["design"].config.get("ensure_plugins") == ["ui-pro"]
    assert by_id["refine"].config.get("ensure_plugins") == ["impeccable"]
    assert by_id["verify"].config.get("ensure_plugins") == ["impeccable"]


def test_verify_carries_antipattern_gate(template: WorkflowTemplate) -> None:
    """verify stage gates on `impeccable detect` exit codes (0=pass, 2=fail)."""
    verify = next(s for s in template.stages if s.id == "verify")
    gate = verify.config.get("antipattern_gate") or {}
    assert gate.get("enabled") is True
    assert "impeccable detect" in gate.get("command", "")
    assert gate.get("pass_exit_code") == 0
    assert gate.get("fail_exit_code") == 2


def test_composition_is_sequence_with_convergence_loop(template: WorkflowTemplate) -> None:
    assert isinstance(template.composition, Sequence)
    loop = next((lp for lp in template.loops if lp.name == "refine_verify_loop"), None)
    assert loop is not None, "refine_verify_loop missing"
    assert loop.body_stages == ["refine", "verify"]
    assert loop.max_iterations and loop.max_iterations > 0
    assert loop.until, "convergence loop must declare an `until` condition"


def test_template_registered_in_registry() -> None:
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    web_design = next((e for e in data["templates"] if e["name"] == "web-design"), None)
    assert web_design is not None, "web-design missing from registry.yaml"
    assert web_design["path"] == "builtin/web-design.yaml"
    assert web_design["source"] == "builtin"
    assert web_design["category"] == "composite"
    for tag in ("web-design", "ui-pro", "impeccable"):
        assert tag in web_design["tags"], f"registry entry missing tag {tag!r}"
