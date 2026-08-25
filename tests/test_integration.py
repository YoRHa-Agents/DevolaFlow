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
from devolaflow.template_engine.registry import TemplateRegistry


def test_full_pipeline_template_loads(project_root: Path):
    """Verify full-pipeline loads as a checklist seed.

    Registry v3 keeps historical stages as provenance only. Execution uses
    the sole ``change-driven`` runtime.
    """
    registry = TemplateRegistry(project_root / "workflow-system" / "agent" / "templates")
    seed = registry.load_seed("full-pipeline")
    runtime = registry.load_template("change-driven")
    assert seed is not None
    assert seed.metadata.name == "full-pipeline"
    assert seed.kind == "checklist-seed"
    assert runtime is not None
    assert runtime.metadata.name == "change-driven"


def test_hotfix_template_loads(project_root: Path):
    """Verify hotfix loads as a checklist seed.

    ``source_stages`` retain historical provenance and do not select runtime
    execution order.
    """
    registry = TemplateRegistry(project_root / "workflow-system" / "agent" / "templates")
    seed = registry.load_seed("hotfix")
    runtime = registry.load_template("change-driven")
    assert seed is not None
    assert seed.metadata.name == "hotfix"
    assert seed.source_stage_sequence()
    assert runtime is not None
    assert runtime.metadata.name == "change-driven"


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


def test_claude_md_exists(project_root: Path):
    """Verify root CLAUDE.md exists as project context."""
    claude = project_root / "CLAUDE.md"
    assert claude.exists(), "CLAUDE.md not found at project root"
    lines = claude.read_text().splitlines()
    assert len(lines) < 100, (
        f"CLAUDE.md should be lightweight project context, has {len(lines)} lines"
    )


def test_claude_md_is_project_context(project_root: Path):
    """Verify root CLAUDE.md is lightweight project context (not a SKILL copy)."""
    claude = project_root / "CLAUDE.md"
    if not claude.exists():
        return
    text = claude.read_text()
    assert "## Build & Test" in text or "## Project Structure" in text
    assert len(text.splitlines()) < 100


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
