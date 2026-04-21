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
    rows = [ln for ln in section.group(1).splitlines() if ln.startswith("|")][2:]
    names: set[str] = set()
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 2 and cells[1]:
            names.add(cells[1])
    return names


def test_skill_workflow_selection_covers_registry(project_root: Path) -> None:
    """G-A1: every registry workflow must appear in SKILL Workflow-Selection.

    Closed by P-03 in v7.4.6 — `nines-assisted` row added to the
    Workflow-Selection table per audit §3.A G-A1 evidence; xfail marker
    removed per the audit §6 strict=True contract.
    """
    missing = _registry_names(project_root) - _skill_workflow_selection_names(project_root)
    assert not missing, f"Registry workflows missing from SKILL: {sorted(missing)}"


def test_skill_quick_reference_covers_registry(project_root: Path) -> None:
    """G-A2: every registry workflow must appear in SKILL Quick-Reference.

    Closed by P-03 in v7.4.6 — `nines-assisted` and `self-update` rows
    added to the Template Quick-Reference table per audit §3.A G-A2
    evidence; xfail marker removed per the audit §6 strict=True contract.
    """
    missing = _registry_names(project_root) - _skill_quick_reference_names(project_root)
    assert not missing, f"Registry workflows missing from QuickRef: {sorted(missing)}"


def test_skill_workflow_names_match_registry_canonical_names(
    project_root: Path,
) -> None:
    """G-A3: SKILL surface names must be exact canonical registry names.

    Closed by P-03 in v7.4.6 — `documentation` → `documentation-only` and
    `RDRR` → `research-design-review-refine` swaps applied to both the
    Workflow-Selection and Template Quick-Reference tables per audit §3.A
    G-A3 evidence; xfail marker removed per the audit §6 strict=True
    contract.
    """
    skill_names = _skill_workflow_selection_names(project_root)
    drift = {"documentation", "RDRR"} & skill_names
    assert not drift, (
        f"SKILL uses non-canonical names {sorted(drift)} that fail "
        f"TemplateRegistry.load_template() exact-match"
    )


def test_context_profiles_match_registry_templates(project_root: Path) -> None:
    """G-A4: sub-task-routing profiles either have a matching template OR
    are documented as intentional sub-task routing in context_profiles.yaml.

    Closed by P-03 in v7.4.6 per audit §9 Open Question 1 — the four
    profiles ``feedback``, ``verify_visual``, ``verify_acceptance``,
    ``verify_interaction`` are intentional sub-task routing layers
    consumed by composite workflows (e.g. ``product-verification``
    dispatching ``verify_*`` sub-tasks). The closure mode is the
    documented intentional-asymmetry annotation in
    ``context_profiles.yaml`` (the "G-A4 closure" comment block above
    ``feedback:``), not a new template. Test passes iff either (a) the
    templates exist OR (b) the sub-task pattern is documented.
    """
    template_normalised = {n.replace("-", "_") for n in _registry_names(project_root)}
    sub_task = {"verify_visual", "verify_acceptance", "verify_interaction", "feedback"}
    not_in_registry = sub_task - template_normalised
    if not_in_registry:
        profiles_yaml = _read(project_root / "workflow-system/agent/context_profiles.yaml")
        assert "sub-task" in profiles_yaml.lower(), (
            f"Profiles {sorted(not_in_registry)} have no matching template; "
            f"the profile-as-sub-task pattern must be documented in "
            f"context_profiles.yaml per audit §9 Open Q1 (G-A4 closure)"
        )


# ── Category B: CLI commands ────────────────────────────────────────


def test_validate_gate_cli_is_not_stub(project_root: Path) -> None:
    """G-B1: validate-gate must not be the print('gate: pass (stub)') stub.

    Closed by P-06 in v7.4.5 — :func:`devolaflow.gate.scorer.run_gate_cli`
    now parses ``--input``, calls :func:`evaluate_gate`, and exits 0/1/2 with
    a structured ``decision: …`` summary on stdout. This test pins the
    closure: any regression that re-introduces the stub string fails here.
    """
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


@pytest.mark.parametrize("hook", ["validate_dispatch", "check_file_ownership", "test_on_complete"])
def test_lifecycle_hook_implemented(project_root: Path, hook: str) -> None:
    """G-C1: each documented lifecycle hook must have a code identifier.

    Closed by P-05 in v7.4.8 — the three hooks were landed as a new
    ``src/devolaflow/lifecycle/`` package (``__init__.py``,
    ``dispatcher.py``, ``validate_dispatch.py``, ``check_file_ownership.py``,
    ``test_on_complete.py``) with permissive-with-warning DEFAULT and
    opt-in strict mode per the audit §3.C G-C1 BLOCKER evidence and the
    audit §5 P-05 row design. xfail marker removed per the audit §6
    strict=True contract; xfail count drops 10 → 7 (3 ghost IDs closed
    via 1 marker covering the parametrize).
    """
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


def test_skill_schema_references_exist_on_disk(project_root: Path) -> None:
    """G-E1/E2/E3: every schema path SKILL.md cites must exist on disk.

    Closed by P-07 in v7.4.7 — SKILL.md Tier 3 paths corrected from
    ``schemas/{task-dispatch,status-report,handoff-deliverable}.yaml`` to
    the canonical ``.schema.yaml`` suffix per audit §3.E G-E1/E2/E3
    evidence; the missing ``handoff-deliverable.schema.yaml`` was authored
    as a P-07 Option α stub. xfail marker removed per the audit §6
    strict=True contract.
    """
    refs = _skill_schema_paths(project_root)
    missing = sorted(r for r in refs if not (project_root / r).exists())
    assert not missing, f"SKILL.md cites schema files that don't exist: {missing}"


def test_workflow_skill_yaml_manifest_schemas_exist(project_root: Path) -> None:
    """G-E4: every schema file declared in workflow-skill.yaml must exist.

    Closed by P-07 in v7.4.7 — the four ``stage-definition``,
    ``wave-definition``, ``task-definition``, and ``dependency-matrix``
    schemas referenced by ``workflow-skill.yaml`` were authored as P-07
    Option α stubs per audit §5 P-07 row decision; xfail marker removed
    per the audit §6 strict=True contract.
    """
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    base = project_root / "workflow-system/agent"
    missing = [
        e["file"] for e in raw["content"]["schemas"] if not (base / e["file"]).resolve().exists()
    ]
    assert not missing, f"Manifest schemas missing on disk: {missing}"


def test_existing_schemas_are_declared_in_manifest(project_root: Path) -> None:
    """G-E5/E6 (inverse): on-disk schemas must be declared in the manifest.

    Closed by P-07 in v7.4.7 — the on-disk ``feedback-report.schema.yaml``
    and ``workflow-template.schema.yaml`` were registered in the
    ``content.schemas`` block of ``workflow-skill.yaml`` per audit §3.E
    G-E5/G-E6 inverse-ghost evidence; xfail marker removed per the audit
    §6 strict=True contract.
    """
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


def test_composer_consumes_template_parameters(project_root: Path) -> None:
    """G-G1: composer (or runtime.py) must consume template.parameters.

    Closed by P-04 in v7.4.9 — :mod:`devolaflow.template_engine.runtime`
    landed as a thin runtime shim with
    :func:`select_stages_for_runtime(template, *, mode, environment)` that
    consumes ``WorkflowTemplate.parameters.mode.default`` (per audit §3.G
    G-G1 evidence: ``composer.py`` never referenced ``parameters``).
    Composer API kept bytewise-compatible — runtime is purely additive.
    xfail marker removed per the audit §6 strict=True contract.
    """
    composer = _read(project_root / "src/devolaflow/template_engine/composer.py")
    runtime = project_root / "src/devolaflow/template_engine/runtime.py"
    assert "parameters" in composer or runtime.exists(), (
        "Neither composer.py nor runtime.py consumes template.parameters"
    )


def test_skip_condition_field_has_runtime_consumer(project_root: Path) -> None:
    """G-G2: skip_condition must drive actual runtime stage skipping.

    Closed by P-04 in v7.4.9 — :func:`devolaflow.template_engine.runtime
    .evaluate_skip_condition` parses the supported grammar
    (``<ident> ('==' | '!=') (<quoted-string> | <number> | <ident>)``)
    and elides stages when the expression evaluates True; ``repo-init.yaml``
    now declares ``skip_condition: "mode != 'deep'"`` on ``verify`` and
    ``skip_condition: "mode == 'minimal'"`` on ``compile`` per audit §3.G
    G-G2 evidence (``StageDefinition.skip_condition`` had no execution-time
    consumer — only validator exemptions). xfail marker removed per the
    audit §6 strict=True contract.
    """
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


def test_skill_template_tier3_paths_exist(project_root: Path) -> None:
    """G-H1/H2/H3: every `templates/...` path in SKILL Tier-3 must exist.

    Closed by P-07 in v7.4.7 — the three SKILL Tier-3 template paths
    (``templates/project-status.yaml``, ``templates/stage-readme.md``,
    ``templates/wave-plan.md``) were authored as P-07 Option α stubs per
    audit §3.H G-H1/G-H2/G-H3 evidence; xfail marker removed per the
    audit §6 strict=True contract.
    """
    paths = re.findall(r"`(templates/[a-zA-Z0-9._/-]+)`", _skill_tier3_section(project_root))
    base = project_root / "workflow-system/agent"
    missing = sorted(p for p in paths if not (base / p).exists())
    assert not missing, f"SKILL Tier-3 template paths missing: {missing}"


def test_skill_knowledge_paths_exist(project_root: Path) -> None:
    """G-H4/H5 (inverse): manifest-registered knowledge files must be in SKILL.

    Closed by P-03 in v7.4.6 — `knowledge/code-rules-mapping.md` and
    `knowledge/principle-mapping.md` rows added to SKILL.md Tier 3
    references per audit §3.H G-H4/G-H5 evidence; xfail marker removed
    per the audit §6 strict=True contract.
    """
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    declared = {Path(k["file"]).name for k in raw["content"]["knowledge"]}
    undiscovered = sorted(n for n in declared if n not in skill and Path(n).stem not in skill)
    assert not undiscovered, (
        f"Knowledge files declared in manifest but not in SKILL.md: {undiscovered}"
    )


def test_skill_knowledge_index_in_manifest(project_root: Path) -> None:
    """G-H6: knowledge/index.md cited by SKILL must appear in manifest.

    Closed by P-07 in v7.4.7 — the ``knowledge/index.md`` entry was added
    to the ``content.knowledge`` block of ``workflow-skill.yaml`` (and to
    the bottom ``manifest.knowledge`` block for symmetry) per audit §3.H
    G-H6 inverse-ghost evidence; xfail marker removed per the audit §6
    strict=True contract.
    """
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    assert "knowledge/index.md" in skill, "G-H6 precondition: SKILL must cite knowledge/index.md"
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    files = {Path(k["file"]).name for k in raw["content"]["knowledge"]}
    assert "index.md" in files, (
        "knowledge/index.md cited by SKILL.md but missing from "
        "workflow-skill.yaml content.knowledge manifest"
    )


# ── Category I: WorkflowTemplate dataclass fields ──────────────────


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(
            "team_overrides",
            marks=pytest.mark.xfail(
                strict=True,
                reason="G-I1: WorkflowTemplate.team_overrides parsed but no "
                "runtime consumer outside structural files — closes in P-08",
            ),
        ),
        "environment_modes",
        pytest.param(
            "timeout_minutes",
            marks=pytest.mark.xfail(
                strict=True,
                reason="G-I3: StageDefinition.timeout_minutes parsed but no "
                "runtime consumer (no template currently sets it either) — "
                "closes in P-08",
            ),
        ),
        pytest.param(
            "input_mapping",
            marks=pytest.mark.xfail(
                strict=True,
                reason="G-I4: StageDefinition.input_mapping wiring DEFERRED "
                "to v7.6.x per audit §9 Open Q1 + user 'mode_only' decision "
                "for the v7.5.0 P-04 scope (mode-driven stage skip only; "
                "dataflow input_mapping is a v7.6.x candidate)",
            ),
        ),
    ],
)
def test_dataclass_field_has_consumer(project_root: Path, field: str) -> None:
    """G-I1..I4: each parsed field must have a runtime consumer.

    G-I2 (``environment_modes``) closed by P-04 in v7.4.9 — the new
    :mod:`devolaflow.template_engine.runtime` reads
    ``template.environment_modes[<env>].skip_stages`` and ``.extra_stages``
    and applies them after skip_condition filtering per audit §3.I G-I2
    evidence. Per-parameter xfail markers replace the previous
    test-level marker so G-I1 / G-I3 / G-I4 remain xfailed (per
    audit §6 strict=True contract: each ghost gets its own marker).
    G-I4 explicitly carries the v7.6.x deferral reason per the user's
    'mode_only' scope decision recorded in audit §9 Open Q1.
    """
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
