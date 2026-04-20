"""Anti-ghost meta-tests — declared <-> implemented symmetry.

Each ghost in `.local/research/v7.5.0_ghost_audit.md` (§3.A through §3.K) has
a test below. Tests for ghosts already closed (e.g. Category K stale-doc
ghosts, closed by P-02 in v7.4.3) carry NO xfail and PASS — pinning the
closure. Tests for ghosts NOT yet closed carry
``@pytest.mark.xfail(strict=True, reason="<G-ID>: <one-line> — closes in P-NN")``.
``strict=True`` turns an unexpected pass into a hard failure, forcing every
subsequent patch (P-02..P-08) to delete its xfail marker as part of the patch
that closes the ghost. Verified-working features (Category D reinforcement,
Category F SF-4 reference compliance) are pinned with NO xfail.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


@pytest.fixture(scope="module")
def project_root() -> Path:
    """Return the repository root (parent of the ``tests/`` directory)."""
    return Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(_read(path))


# Files excluded from "consumer" search for dataclass-field ghost tests:
# definition / parsing / inheritance-merge / static-validation. A real runtime
# consumer must live in composer.py, runtime.py, dispatch wiring, etc.
_STRUCTURAL_FILES = {"models.py", "parser.py", "inheritance.py", "validator.py"}


def _registry_names(project_root: Path) -> set[str]:
    """Return the canonical workflow template names from the registry."""
    raw = _load_yaml(project_root / "workflow-system/agent/templates/registry.yaml")
    return {entry["name"] for entry in raw["templates"]}


def _builtin_template_files(project_root: Path) -> list[Path]:
    return sorted((project_root / "workflow-system/agent/templates/builtin").glob("*.yaml"))


# ── Category A: workflow templates ──────────────────────────────────


def _skill_workflow_selection_names(project_root: Path) -> set[str]:
    """Extract workflow names cited in SKILL.md's Workflow Selection table."""
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    section = re.search(r"## Quick Start — Workflow Selection.*?\n(.*?)\n## ", skill, re.DOTALL)
    if section is None:
        return set()
    return set(re.findall(r"`([a-z][a-z0-9_-]+)`", section.group(1)))


def _skill_quick_reference_names(project_root: Path) -> set[str]:
    """Extract template names from SKILL.md's Template Quick-Reference table."""
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    section = re.search(r"## Template Quick-Reference\n(.*?)(?:\n## |\Z)", skill, re.DOTALL)
    if section is None:
        return set()
    rows = [ln for ln in section.splitlines() if ln.startswith("|")][2:]
    names: set[str] = set()
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 2 and cells[1]:
            names.add(cells[1])
    return names


@pytest.mark.xfail(
    strict=True,
    reason="G-A1: nines-assisted in registry but not in SKILL — closes in P-03",
)
def test_skill_workflow_selection_covers_registry(project_root: Path) -> None:
    """G-A1: every registry workflow must appear in SKILL Workflow-Selection."""
    missing = _registry_names(project_root) - _skill_workflow_selection_names(project_root)
    assert not missing, f"Registry workflows missing from SKILL: {sorted(missing)}"


@pytest.mark.xfail(
    strict=True,
    reason="G-A2: self-update missing from QuickRef table — closes in P-03",
)
def test_skill_quick_reference_covers_registry(project_root: Path) -> None:
    """G-A2: every registry workflow must appear in SKILL Quick-Reference."""
    missing = _registry_names(project_root) - _skill_quick_reference_names(project_root)
    assert not missing, f"Registry workflows missing from QuickRef: {sorted(missing)}"


@pytest.mark.xfail(
    strict=True,
    reason="G-A3: SKILL uses short names (`documentation`, `RDRR`) where "
    "registry uses canonical long names — closes in P-03",
)
def test_skill_workflow_names_match_registry_canonical_names(
    project_root: Path,
) -> None:
    """G-A3: SKILL surface names must be exact canonical registry names."""
    skill_names = _skill_workflow_selection_names(project_root)
    drift = {"documentation", "RDRR"} & skill_names
    assert not drift, (
        f"SKILL uses non-canonical names {sorted(drift)} that fail "
        f"TemplateRegistry.load_template() exact-match"
    )


@pytest.mark.xfail(
    strict=True,
    reason="G-A4: 4 context profiles (verify_visual, verify_acceptance, "
    "verify_interaction, feedback) have no matching template — closes in P-03",
)
def test_context_profiles_match_registry_templates(project_root: Path) -> None:
    """G-A4: certain task-typed context profiles must have matching templates."""
    template_normalised = {n.replace("-", "_") for n in _registry_names(project_root)}
    missing = {
        p
        for p in {"verify_visual", "verify_acceptance", "verify_interaction", "feedback"}
        if p not in template_normalised
    }
    assert not missing, (
        f"context_profiles.yaml profiles {sorted(missing)} have no matching "
        f"workflow template — dispatcher routing fails at instantiation"
    )


# ── Category B: CLI commands ────────────────────────────────────────


@pytest.mark.xfail(strict=True, reason="G-B1: validate-gate is a print-stub — closes in P-06")
def test_validate_gate_cli_is_not_stub(project_root: Path) -> None:
    """G-B1: validate-gate must not be the print('gate: pass (stub)') stub."""
    src = _read(project_root / "src/devolaflow/gate/scorer.py")
    assert 'print("gate: pass (stub)")' not in src, (
        "validate-gate CLI is still a print-stub — see scorer.py::run_gate_cli"
    )


def test_check_drift_has_adversarial_test(project_root: Path) -> None:
    """G-B2 sanity: check_drift wrapper exists and is exercised in tests."""
    cli = _read(project_root / "src/devolaflow/cli.py")
    assert "check_drift" in cli, "check_drift_cmd must exist in cli.py"
    exercise = _read(project_root / "tests/test_exercise_modules.py")
    assert "check_drift" in exercise, (
        "check_drift must have at least the smoke test (G-B2 minor: needs adversarial coverage)"
    )


# ── Category C: lifecycle hooks ─────────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="G-C1: 3 lifecycle hooks (validate_dispatch, check_file_ownership, "
    "test_on_complete) are documentation-only — closes in P-05",
)
@pytest.mark.parametrize("hook", ["validate_dispatch", "check_file_ownership", "test_on_complete"])
def test_lifecycle_hook_implemented(project_root: Path, hook: str) -> None:
    """G-C1: each documented lifecycle hook must have a code identifier."""
    src_dir = project_root / "src" / "devolaflow"
    found = any(hook in _read(p) for p in src_dir.rglob("*.py"))
    assert found, (
        f"Lifecycle hook '{hook}' is documented in SKILL.md §Lifecycle Hooks "
        f"but has no implementation under src/devolaflow/"
    )


# ── Category D: reinforcement (already implemented — pin) ───────────


def test_reinforcement_findings_function_exists() -> None:
    """G-D pin: findings_to_reinforcement() must exist and be callable."""
    from devolaflow.gate.reinforcement import findings_to_reinforcement

    assert callable(findings_to_reinforcement)


def test_round_aware_dispatch_escalation_exists(project_root: Path) -> None:
    """G-D pin: round-aware dispatch escalation must be wired end-to-end."""
    selector = _read(project_root / "src/devolaflow/task_adaptive_selector.py")
    assert "_ROUND_ESCALATION_DEFAULTS" in selector, (
        "Round-aware escalation table missing from task_adaptive_selector.py"
    )
    feedback = _read(project_root / "src/devolaflow/feedback.py")
    assert "generate_round_dispatch" in feedback, (
        "ProposalGenerator.generate_round_dispatch() missing from feedback.py"
    )


# ── Category E: schemas ─────────────────────────────────────────────


def _skill_schema_paths(project_root: Path) -> set[str]:
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    return set(re.findall(r"`(schemas/[a-zA-Z0-9._/-]+\.yaml)`", skill))


@pytest.mark.xfail(
    strict=True,
    reason="G-E1/G-E2/G-E3: SKILL Tier-3 cites 3 schema paths missing on disk "
    "(task-dispatch.yaml, status-report.yaml, handoff-deliverable.yaml) — "
    "closes in P-07",
)
def test_skill_schema_references_exist_on_disk(project_root: Path) -> None:
    """G-E1/E2/E3: every schema path SKILL.md cites must exist on disk."""
    refs = _skill_schema_paths(project_root)
    missing = sorted(r for r in refs if not (project_root / r).exists())
    assert not missing, f"SKILL.md cites schema files that don't exist: {missing}"


@pytest.mark.xfail(
    strict=True,
    reason="G-E4: workflow-skill.yaml manifest cites 4 schemas missing on disk "
    "(stage-definition, wave-definition, task-definition, dependency-matrix) "
    "— closes in P-07",
)
def test_workflow_skill_yaml_manifest_schemas_exist(project_root: Path) -> None:
    """G-E4: every schema file declared in workflow-skill.yaml must exist."""
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    base = project_root / "workflow-system/agent"
    missing = [
        e["file"] for e in raw["content"]["schemas"] if not (base / e["file"]).resolve().exists()
    ]
    assert not missing, f"Manifest schemas missing on disk: {missing}"


@pytest.mark.xfail(
    strict=True,
    reason="G-E5/G-E6: 2 schemas exist on disk (feedback-report.schema.yaml, "
    "workflow-template.schema.yaml) but are NEITHER cited in SKILL.md NOR "
    "registered in workflow-skill.yaml schemas section — closes in P-07",
)
def test_existing_schemas_are_declared_in_manifest(project_root: Path) -> None:
    """G-E5/E6 (inverse): on-disk schemas must be declared in the manifest."""
    on_disk = {p.name for p in (project_root / "schemas").glob("*.schema.yaml")}
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    declared = {Path(e["file"]).name for e in raw["content"]["schemas"]}
    undeclared = sorted(on_disk - declared)
    assert not undeclared, (
        f"Schemas exist on disk but unregistered in workflow-skill.yaml "
        f"content.schemas: {undeclared}"
    )


# ── Category F: reference links (already SF-4 compliant — pin) ─────


_SF4_REFERENCE_SET = frozenset(
    {
        "agent-hierarchy.md",
        "context-isolation.md",
        "decomposition-gate.md",
        "execution-protocol.md",
        "message-schemas.md",
        "meta-framework.md",
        "repo-modes.md",
        "team-roles.md",
    }
)


def test_skill_reference_links_match_sf4_set(project_root: Path) -> None:
    """G-F pin: SKILL references and on-disk references match the SF-4 set."""
    on_disk = {p.name for p in (project_root / "workflow-system/agent/references").glob("*.md")}
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    cited = set(re.findall(r"references/([a-z-]+\.md)", skill))
    assert on_disk == set(_SF4_REFERENCE_SET), (
        f"references/ drifted from SF-4 set: "
        f"missing={sorted(set(_SF4_REFERENCE_SET) - on_disk)}, "
        f"extra={sorted(on_disk - set(_SF4_REFERENCE_SET))}"
    )
    extra = cited - set(_SF4_REFERENCE_SET)
    assert not extra, f"SKILL cites non-SF-4 references: {sorted(extra)}"


def test_skill_examples_paths_exist(project_root: Path) -> None:
    """G-F pin: every `examples/...` path SKILL.md cites must exist."""
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    cited = set(re.findall(r"`(examples/[a-zA-Z0-9._/-]+\.md)`", skill))
    base = project_root / "workflow-system/agent"
    missing = sorted(p for p in cited if not (base / p).exists())
    assert not missing, f"SKILL Tier-3 examples missing on disk: {missing}"


# ── Category G: composer / parameters wiring ────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="G-G1: composer.py never reads template.parameters; the "
    "parameters.mode enum on repo-init.yaml is parsed but never honoured at "
    "runtime — closes in P-04",
)
def test_composer_consumes_template_parameters(project_root: Path) -> None:
    """G-G1: composer (or runtime.py) must consume template.parameters."""
    composer = _read(project_root / "src/devolaflow/template_engine/composer.py")
    runtime = project_root / "src/devolaflow/template_engine/runtime.py"
    assert "parameters" in composer or runtime.exists(), (
        "Neither composer.py nor runtime.py consumes template.parameters"
    )


@pytest.mark.xfail(
    strict=True,
    reason="G-G2: StageDefinition.skip_condition is parsed but never causes "
    "runtime stage skipping (only validator exempts it from unreachability "
    "warnings) — closes in P-04",
)
def test_skip_condition_field_has_runtime_consumer(project_root: Path) -> None:
    """G-G2: skip_condition must drive actual runtime stage skipping."""
    composer = _read(project_root / "src/devolaflow/template_engine/composer.py")
    runtime = project_root / "src/devolaflow/template_engine/runtime.py"
    in_runtime = runtime.exists() and "skip_condition" in _read(runtime)
    assert "skip_condition" in composer or in_runtime, (
        "StageDefinition.skip_condition has no execution-time consumer "
        "(composer/runtime); validator exempts it from warnings only"
    )


# ── Category H: templates / knowledge artifacts ─────────────────────


def _skill_tier3_section(project_root: Path) -> str:
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    match = re.search(r"\*\*Tier 3.*?\n(.*?)(?:\n## |\Z)", skill, re.DOTALL)
    return match.group(1) if match else ""


@pytest.mark.xfail(
    strict=True,
    reason="G-H1/G-H2/G-H3: SKILL Tier-3 cites 3 template paths missing on "
    "disk (project-status.yaml, stage-readme.md, wave-plan.md) — closes in P-07",
)
def test_skill_template_tier3_paths_exist(project_root: Path) -> None:
    """G-H1/H2/H3: every `templates/...` path in SKILL Tier-3 must exist."""
    paths = re.findall(r"`(templates/[a-zA-Z0-9._/-]+)`", _skill_tier3_section(project_root))
    base = project_root / "workflow-system/agent"
    missing = sorted(p for p in paths if not (base / p).exists())
    assert not missing, f"SKILL Tier-3 template paths missing: {missing}"


@pytest.mark.xfail(
    strict=True,
    reason="G-H4/G-H5: code-rules-mapping.md and principle-mapping.md are "
    "registered in workflow-skill.yaml manifest but absent from SKILL.md — "
    "closes in P-03",
)
def test_skill_knowledge_paths_exist(project_root: Path) -> None:
    """G-H4/H5 (inverse): manifest-registered knowledge files must be in SKILL."""
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    declared = {Path(k["file"]).name for k in raw["content"]["knowledge"]}
    undiscovered = sorted(n for n in declared if n not in skill and Path(n).stem not in skill)
    assert not undiscovered, (
        f"Knowledge files declared in manifest but not in SKILL.md: {undiscovered}"
    )


@pytest.mark.xfail(
    strict=True,
    reason="G-H6: SKILL Tier-3 cites knowledge/index.md but the manifest "
    "knowledge block omits it — closes in P-07",
)
def test_skill_knowledge_index_in_manifest(project_root: Path) -> None:
    """G-H6: knowledge/index.md cited by SKILL must appear in manifest."""
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    assert "knowledge/index.md" in skill, "G-H6 precondition: SKILL must cite knowledge/index.md"
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    files = {Path(k["file"]).name for k in raw["content"]["knowledge"]}
    assert "index.md" in files, (
        "knowledge/index.md cited by SKILL.md but missing from "
        "workflow-skill.yaml content.knowledge manifest"
    )


# ── Category I: WorkflowTemplate dataclass fields ──────────────────


@pytest.mark.xfail(
    strict=True,
    reason="G-I1/G-I2/G-I3/G-I4: 4 dataclass fields (team_overrides, "
    "environment_modes, timeout_minutes, input_mapping) parsed but no runtime "
    "consumer outside structural files (models/parser/inheritance/validator) "
    "— closes in P-04 (G-I2/G-I4) and P-08 (G-I1/G-I3)",
)
@pytest.mark.parametrize(
    "field",
    ["team_overrides", "environment_modes", "timeout_minutes", "input_mapping"],
)
def test_dataclass_field_has_consumer(project_root: Path, field: str) -> None:
    """G-I1..I4: each parsed field must have a runtime consumer."""
    src_dir = project_root / "src" / "devolaflow"
    py_files = [p for p in src_dir.rglob("*.py") if p.name not in _STRUCTURAL_FILES]
    consumers = sorted(
        p.relative_to(project_root).as_posix() for p in py_files if field in _read(p)
    )
    assert consumers, (
        f"Dataclass field '{field}' has no consumer outside "
        f"{sorted(_STRUCTURAL_FILES)} — parsed but never used"
    )


# ── Category J: CHANGELOG <-> code ──────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="G-J1: install_local() prints 'compile-config.yaml (template "
    "created)' but never writes the file; sync-rules then exits 1 demanding "
    "it — closes in P-08",
)
def test_init_creates_compile_config_template(project_root: Path, tmp_path: Path) -> None:
    """G-J1: install_local() must actually scaffold compile-config.yaml.

    The ghost is detected by EXECUTING install_local() against a fresh
    tmp_path: a non-ghost implementation creates the file, while the
    current ghost only prints a misleading line.
    """
    from devolaflow.init_project import install_local

    agent_dir = project_root / "workflow-system/agent"
    install_local(agent_dir, tmp_path)
    expected = tmp_path / ".rules" / "compile-config.yaml"
    assert expected.is_file(), (
        f"install_local() must scaffold {expected.relative_to(tmp_path)} — "
        f"current implementation only prints the line"
    )


def test_rules_source_directory_exists(project_root: Path) -> None:
    """G-J2 sanity: .rules/ source directory must be present and tracked.

    Audit flagged this as conditional ("if absent, the auto-gen chain is
    broken"). Verified PRESENT in this working tree at v7.4.3 — pin closure.
    """
    rules_dir = project_root / ".rules"
    assert rules_dir.is_dir(), ".rules/ source rule directory must exist"
    assert sorted(rules_dir.glob("*.mdc")), (
        f"{rules_dir} must contain at least one *.mdc source rule file"
    )


# ── Category K: stale documentation references (closed by P-02) ─────


def test_readme_template_count_in_project_structure(project_root: Path) -> None:
    """G-K1 pin: README project-structure template count matches disk."""
    readme = _read(project_root / "README.md")
    actual = len(_builtin_template_files(project_root))
    stale = re.findall(r"#\s*(\d+)\s+workflow template YAMLs", readme)
    assert stale, "README must contain the 'N workflow template YAMLs' line"
    for s in stale:
        assert int(s) == actual, f"README claims {s} templates, disk has {actual} — G-K1 regressed"


def test_readme_test_count_and_coverage_current(project_root: Path) -> None:
    """G-K5 pin: README test-suite numerics aren't egregiously stale."""
    readme = _read(project_root / "README.md")
    matches = re.findall(
        r"tests/\s+#\s*pytest suite \((\d+)[+]?\s+tests,\s+([0-9.]+)%\s+coverage\)",
        readme,
    )
    assert matches, "README must include 'pytest suite (N tests, X% coverage)'"
    test_count, coverage = int(matches[0][0]), float(matches[0][1])
    assert test_count >= 1300, (
        f"README claims {test_count} tests, expected >= 1300 — G-K5 regressed"
    )
    assert coverage >= 90.0, f"README claims {coverage}% coverage, expected >= 90 — G-K5 regressed"


def test_readme_workflow_type_count_bilingual(project_root: Path) -> None:
    """G-K2/K3 pin: EN+ZH workflow-type guide rows agree with disk."""
    readme = _read(project_root / "README.md")
    actual = len(_builtin_template_files(project_root))
    en = re.search(r"All\s+(\d+)\s+workflow types", readme)
    assert en, "README EN guide must say 'All N workflow types'"
    assert int(en.group(1)) == actual, (
        f"README EN claims {en.group(1)} types, disk has {actual} — G-K2 regressed"
    )
    zh = re.search(r"全部\s*(\d+)\s*种工作流类型", readme)
    assert zh, "README ZH guide must say '全部 N 种工作流类型'"
    assert int(zh.group(1)) == actual, (
        f"README ZH claims {zh.group(1)} types, disk has {actual} — "
        f"G-K3 regressed (DS-3 bilingual drift)"
    )


def test_workflow_skill_yaml_template_count_comment(project_root: Path) -> None:
    """G-K10 pin: workflow-skill.yaml templates comment matches disk."""
    text = _read(project_root / "workflow-system/agent/workflow-skill.yaml")
    actual = len(_builtin_template_files(project_root))
    match = re.search(r"#\s*Registry\s*\+\s*(\d+)\s+builtin\s+templates", text)
    assert match, "workflow-skill.yaml must contain 'Registry + N builtin templates'"
    assert int(match.group(1)) == actual, (
        f"workflow-skill.yaml claims {match.group(1)} templates, disk has "
        f"{actual} — G-K10 regressed"
    )


def test_claude_md_version_tracking_note(project_root: Path) -> None:
    """G-K12 pin: CLAUDE.md must claim the canonical 7 sync locations."""
    claude = _read(project_root / "CLAUDE.md")
    match = re.search(r"Version tracked across (\d+)\s+canonical sync locations", claude)
    assert match, "CLAUDE.md must say 'Version tracked across N canonical sync locations'"
    assert match.group(1) == "7", (
        f"CLAUDE.md claims {match.group(1)} canonical sync locations, "
        f"expected 7 per CP-3 / SF-3 — G-K12 regressed"
    )
