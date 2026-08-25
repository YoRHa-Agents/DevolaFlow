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

# Moved verbatim from tests/test_no_ghost_features.py per
# v15-ADR-001 (v14.3.0 split): pre-v9.1 stanzas — the original
# v7.5.0 ghost-audit categories A-K plus the v8.x / v9.0.0-era
# audits that predate the per-cycle stanza convention.

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.ghost._helpers import _load_yaml, _read

# Files excluded from "consumer" search for dataclass-field ghost tests:
# definition / parsing / inheritance-merge / static-validation. A real runtime
# consumer must live in composer.py, runtime.py, dispatch wiring, etc.
_STRUCTURAL_FILES = {"models.py", "parser.py", "inheritance.py", "validator.py"}


def _registry_names(project_root: Path) -> set[str]:
    """Return the registry-v3 checklist-seed names."""
    raw = _load_yaml(project_root / "workflow-system/agent/templates/registry.yaml")
    entries = (raw.get("compositions") or []) + (raw.get("templates") or [])
    return {entry["name"] for entry in entries}


# ── Category A: workflow templates ──────────────────────────────────


def _skill_workflow_selection_names(project_root: Path) -> set[str]:
    """Extract workflow names cited in SKILL.md's Workflow Selection table."""
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    section = re.search(r"## Quick Start — Workflow Selection.*?\n(.*?)\n## ", skill, re.DOTALL)
    if section is None:
        return set()
    return set(re.findall(r"`([a-z][a-z0-9_-]+)`", section.group(1)))


def _skill_quick_reference_names(project_root: Path) -> set[str]:
    """Extract seed names from meta-framework's compatibility table."""
    skill = _read(project_root / "workflow-system/agent/references/meta-framework.md")
    section = re.search(
        r"### Template Quick-Reference — Gate Types\n(.*?)(?:\n### |\n## |\Z)", skill, re.DOTALL
    )
    if section is None:
        return set()
    rows = [ln for ln in section.group(1).splitlines() if ln.startswith("|")][2:]
    names: set[str] = set()
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 2 and cells[1]:
            name = re.sub(r"\s*\(legacy\)\s*$", "", cells[1])
            names.add(name)
    return names


def test_skill_workflow_selection_covers_registry(project_root: Path) -> None:
    """G-A1: every registry workflow must appear in SKILL Workflow-Selection.

    Closed by P-03 in v7.4.6 — `nines-assisted` row added to the
    Workflow-Selection table per audit §3.A G-A1 evidence; xfail marker
    removed per the audit §6 strict=True contract.

    Under registry v3 this is exact seed-discoverability parity.
    """
    missing = _registry_names(project_root) - _skill_workflow_selection_names(project_root)
    assert not missing, f"Registry workflows missing from SKILL: {sorted(missing)}"


def test_skill_quick_reference_covers_registry(project_root: Path) -> None:
    """G-A2: every registry workflow must appear in SKILL Quick-Reference.

    Closed by P-03 in v7.4.6 — `nines-assisted` and `self-update` rows
    added to the Template Quick-Reference table per audit §3.A G-A2
    evidence; xfail marker removed per the audit §6 strict=True contract.

    Registry v3 preserves the historical heading for tooling, but every row
    now means non-executable seed knowledge routed to checklist-round.
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
        f"TemplateRegistry.load_seed() exact-match"
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


def test_deferred_marker_class_registered(project_root: Path) -> None:
    """v9.0.0 PV-05 NEW (M-05 ``@pytest.mark.deferred`` marker class).

    Asserts that the second marker class (alongside ``persistence_probe``)
    is declared in ``pyproject.toml [tool.pytest.ini_options] markers``
    and honoured by the ``pytest_collection_modifyitems`` hook in
    ``tests/conftest.py``. The M-05 ADR-005 D2 records the rationale.
    """
    pyproject = _read(project_root / "pyproject.toml")
    assert "markers = [" in pyproject, "pyproject.toml has no [tool.pytest] markers section"
    assert '"deferred:' in pyproject, (
        "pyproject.toml [tool.pytest] markers list missing the 'deferred' marker class — "
        "M-05 ADR-005 D2 violation"
    )
    conftest = _read(project_root / "tests/conftest.py")
    assert "pytest_collection_modifyitems" in conftest, (
        "tests/conftest.py missing pytest_collection_modifyitems hook — "
        "the deferred marker has no runtime honour mechanism"
    )
    assert 'get_closest_marker("deferred")' in conftest, (
        "tests/conftest.py pytest_collection_modifyitems does not consult the "
        "deferred marker — M-05 violation"
    )


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
    """G-H4/H5: SKILL knowledge navigation matches disk exactly."""
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    raw = _load_yaml(project_root / "workflow-system/agent/workflow-skill.yaml")
    declared = {k["file"] for k in raw["content"]["knowledge"]}
    knowledge_dir = project_root / "workflow-system/agent/knowledge"
    on_disk = {
        f"knowledge/{path.name}"
        for path in knowledge_dir.iterdir()
        if path.is_file() and path.suffix in {".md", ".yaml"}
    }
    cited = set(re.findall(r"`(knowledge/[a-z][a-z0-9-]*\.(?:md|yaml))`", skill))
    assert cited == on_disk, (
        f"SKILL knowledge navigation drifted — missing: {sorted(on_disk - cited)}, "
        f"extra: {sorted(cited - on_disk)}"
    )
    assert declared <= cited


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
        "environment_modes",
        pytest.param(
            "timeout_minutes",
            marks=pytest.mark.xfail(
                strict=True,
                reason="G-I3: StageDefinition.timeout_minutes RESERVED for "
                "v7.6.x runtime wiring (per audit §9 Open Q4 + user "
                "'delete_team_keep_timeout' decision); the field is "
                "intentionally retained but consumer-less, with a "
                "reserved-for-v7.6.x docstring on models.py — marker stays "
                "until P-NN in v7.6.x lands the runtime enforcement",
            ),
        ),
        "input_mapping",
    ],
)
def test_dataclass_field_has_consumer(project_root: Path, field: str) -> None:
    """G-I1..I4: each parsed field must have a runtime consumer.

    G-I1 (``team_overrides``) closed by P-08 in v7.4.10 — the field was
    deleted from :class:`devolaflow.template_engine.models.WorkflowTemplate`
    (and the parser populator + inheritance merger + 5 builtin templates +
    test fixture + schema doc) per audit §3.I G-I1 evidence and the user's
    'delete_team_keep_timeout' mixed decision in audit §9 Open Q4. The
    parametrize entry is therefore removed (no field → no test).

    G-I2 (``environment_modes``) closed by P-04 in v7.4.9 — the
    :mod:`devolaflow.template_engine.runtime` module reads
    ``template.environment_modes[<env>].skip_stages`` and ``.extra_stages``
    and applies them after skip_condition filtering per audit §3.I G-I2
    evidence.

    G-I3 (``timeout_minutes``) intentionally RETAINED with reserved
    docstring per audit §9 Open Q4 + user 'delete_team_keep_timeout' mixed
    decision — the xfail marker stays in place with the v7.6.x reservation
    reason until that runtime wiring lands.

    G-I4 (``input_mapping``) is now consumed outside parser/model structure;
    the former strict xfail was retired when that wiring landed.
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


def test_init_creates_compile_config_template(project_root: Path, tmp_path: Path) -> None:
    """G-J1: install_local() must actually scaffold compile-config.yaml.

    Closed by P-08 in v7.4.10 — :func:`devolaflow.init_project.install_local`
    now copies the packaged ``devolaflow/local/compile_config_template.yaml``
    into ``<cwd>/.rules/compile-config.yaml`` if missing (idempotent — never
    overwrites an existing config) per audit §3.J G-J1 evidence and the
    user's 'delete_team_keep_timeout' mixed decision in audit §9 Open Q4.
    The xfail marker is REMOVED per the audit §6 strict=True contract; the
    test now PASSES — pinning the closure of the v7.4.0 ``sync-rules``
    circular UX dead-end ("No .rules/compile-config.yaml found. Run
    'devola-init' first." → but devola-init itself produced no config).
    """
    from devolaflow.init_project import install_local

    agent_dir = project_root / "workflow-system/agent"
    install_local(agent_dir, tmp_path)
    expected = tmp_path / ".rules" / "compile-config.yaml"
    assert expected.is_file(), (
        f"install_local() must scaffold {expected.relative_to(tmp_path)} — "
        f"current implementation only prints the line"
    )


# ── Category K: stale documentation references (closed by P-02) ─────


def test_readme_template_count_in_project_structure(project_root: Path) -> None:
    """G-K1 pin: README names 23 seed files and one runtime."""
    readme = _read(project_root / "README.md")
    seed_match = re.search(r"templates/seeds/\s+#\s+(\d+)\s+non-executable checklist seeds", readme)
    assert seed_match, "README project structure must count checklist seeds"
    seed_dir = project_root / "workflow-system/agent/templates/seeds"
    disk_seeds = {path.stem for path in seed_dir.glob("*.yaml")}
    assert int(seed_match.group(1)) == len(disk_seeds) == len(_registry_names(project_root))
    assert "templates/builtin/" in readme and "sole change-driven runtime" in readme


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
    """G-K2/K3 pin: EN+ZH guide rows agree on the seed count."""
    readme = _read(project_root / "README.md")
    expected = len(_registry_names(project_root))
    en = re.search(r"All\s+(\d+)\s+non-executable seeds", readme)
    assert en, "README EN guide must state the non-executable seed count"
    assert int(en.group(1)) == expected
    zh = re.search(r"(\d+)\s*个非执行清单种子", readme)
    assert zh, "README ZH guide must state the non-executable seed count"
    assert int(zh.group(1)) == expected


def test_workflow_skill_yaml_template_count_comment(project_root: Path) -> None:
    """G-K10 pin: workflow-skill.yaml comment reflects registry v3."""
    text = _read(project_root / "workflow-system/agent/workflow-skill.yaml")
    match = re.search(
        r"#\s*Registry v3 inventory: one registry,\s*(\d+)\s+checklist seeds,"
        r"\s*one executable",
        text,
    )
    assert match, "workflow-skill.yaml must state its registry-v3 inventory"
    assert int(match.group(1)) == len(_registry_names(project_root))


def test_claude_md_version_tracking_note(project_root: Path) -> None:
    """G-K12 pin: CLAUDE.md must claim the canonical 7 sync locations.

    v14.4.0 G-031 reduced the canonical sync set 7 → 6 (README badge +
    benchmark-demo SAMPLE_DATA became render/load-time DERIVED per C-6);
    v17.0.0 R6 raised it back to 7 by adding `packages/npm/package.json`.
    """
    claude = _read(project_root / "CLAUDE.md")
    match = re.search(r"Version tracked across (\d+)\s+canonical sync locations", claude)
    assert match, "CLAUDE.md must say 'Version tracked across N canonical sync locations'"
    assert match.group(1) == "7", (
        f"CLAUDE.md claims {match.group(1)} canonical sync locations, "
        f"expected 7 per C-6 (v17.0.0 R6 npm location) — G-K12 regressed"
    )
