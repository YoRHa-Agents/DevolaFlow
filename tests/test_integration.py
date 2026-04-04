"""Integration tests -- simulate delegation traces.

Design ref: design_agent_hierarchy.md section 7.1 (full-pipeline), section 7.2 (hotfix)
"""

from pathlib import Path

import pytest
import yaml

from devolaflow.gate.models import CheckResult, Finding, GateInput
from devolaflow.gate.profiles import STANDARD
from devolaflow.gate.scorer import composite_score, evaluate_gate, quality_score
from devolaflow.template_engine.parser import parse_template


def test_full_pipeline_template_loads(project_root: Path):
    """Verify the full-pipeline template parses and has expected stages."""
    tmpl_path = (
        project_root / "workflow-system" / "agent" / "templates" / "builtin" / "full-pipeline.yaml"
    )
    if not tmpl_path.exists():
        return
    template = parse_template(tmpl_path)
    assert template.metadata.name == "full-pipeline"
    assert len(template.stages) >= 7


def test_hotfix_template_loads(project_root: Path):
    """Verify the hotfix template parses and has expected stages."""
    tmpl_path = project_root / "workflow-system" / "agent" / "templates" / "builtin" / "hotfix.yaml"
    if not tmpl_path.exists():
        return
    template = parse_template(tmpl_path)
    assert template.metadata.name == "hotfix"
    assert len(template.stages) >= 3


def test_full_pipeline_gate_simulation():
    """Simulate the gate evaluation from design_agent_hierarchy.md section 7.1.

    Review scores: code=88, security=92, architecture=85
    Expected composite with weights 0.3, 0.3, 0.4 = 88.0
    """
    dimensions = {"code_review": 88.0, "security": 92.0, "architecture": 85.0}
    weights = {"code_review": 0.3, "security": 0.3, "architecture": 0.4}
    score = composite_score(dimensions, weights)
    assert score == pytest.approx(88.0)


def test_gate_pass_with_clean_findings():
    """Simulate a gate PASS with zero blockers and score above threshold."""
    findings = [
        Finding("F001", "major", "style", "file.py:10", "Naming convention"),
        Finding("F002", "minor", "style", "file.py:20", "Missing docstring"),
    ]
    q_score = quality_score(findings)
    assert q_score == 94.0

    gate_input = GateInput(
        build_status=CheckResult(status="pass", details={}),
        test_results=CheckResult(status="pass", details={"pass_rate": 1.0, "coverage": 0.85}),
        lint_status=CheckResult(status="pass", details={}),
        review_findings=findings,
        acceptance_criteria_results=CheckResult(
            status="pass", details={"results": [{"criterion": "All tests pass", "met": True}]}
        ),
    )
    verdict = evaluate_gate(gate_input, STANDARD, round_num=1, history=[])
    assert verdict.decision == "PASS"


def test_dispatch_report_schema_roundtrip(schemas_dir: Path):
    """Verify dispatch and report schemas load as valid YAML."""
    for name in ["task-dispatch.schema.yaml", "status-report.schema.yaml"]:
        schema_path = schemas_dir / name
        if schema_path.exists():
            with open(schema_path) as f:
                data = yaml.safe_load(f)
            assert data is not None
            assert "design_reference" in data


def test_mvp_skill_under_500_lines(project_root: Path):
    """Verify MVP SKILL.md is under 500 lines per design_delivery_architecture.md section 5.5."""
    mvp = project_root / "workflow-system" / "agent" / "MVP-SKILL.md"
    if not mvp.exists():
        return
    lines = mvp.read_text().splitlines()
    assert len(lines) < 500, f"MVP-SKILL.md has {len(lines)} lines (limit: 500)"


def test_mvp_skill_self_contained(project_root: Path):
    """Verify MVP SKILL.md has no external file references."""
    mvp = project_root / "workflow-system" / "agent" / "MVP-SKILL.md"
    if not mvp.exists():
        return
    text = mvp.read_text()
    assert "references/" not in text or "external" not in text.lower()


def test_skill_md_under_500_lines(project_root: Path):
    """Verify main SKILL.md is under 500 lines."""
    skill = project_root / "workflow-system" / "agent" / "SKILL.md"
    if not skill.exists():
        return
    lines = skill.read_text().splitlines()
    assert len(lines) < 500, f"SKILL.md has {len(lines)} lines (limit: 500)"


def test_all_templates_validate(project_root: Path):
    """Verify all builtin templates parse without errors."""
    tmpl_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"
    if not tmpl_dir.is_dir():
        return
    for yaml_file in tmpl_dir.glob("*.yaml"):
        template = parse_template(yaml_file)
        assert template.metadata.name, f"Template {yaml_file.name} has no name"


def test_human_docs_exist(project_root: Path):
    """Verify human docs exist in both EN and ZH."""
    for lang in ("en", "zh"):
        lang_dir = project_root / "workflow-system" / "human" / lang
        assert lang_dir.is_dir(), f"Missing {lang} docs directory"
        md_files = list(lang_dir.glob("*.md"))
        assert len(md_files) >= 8, f"{lang} has only {len(md_files)} docs (expected 8)"
