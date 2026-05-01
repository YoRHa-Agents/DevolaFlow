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

import ast
import re
from pathlib import Path

import pytest
import yaml

# v8.3.0 PV-06 (v8.2.6) added the `change-driven` workflow template to the
# registry + Python API surface. v8.2.9 closure: change-driven row added to
# README + SKILL + workflow-skill.yaml + EN/ZH workflow-types guides in this
# PV; the deferral set is now empty. Kept as a typed sentinel so future
# deferrals can re-populate it without changing call-site shapes.
_DEFERRED_DOC_TEMPLATES_V8_2_9: frozenset[str] = frozenset()


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

    Names in ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` are excluded — their
    SKILL.md row is intentionally deferred to v8.2.9 per the v8.3.0 patch plan.
    """
    missing = (
        _registry_names(project_root)
        - _skill_workflow_selection_names(project_root)
        - _DEFERRED_DOC_TEMPLATES_V8_2_9
    )
    assert not missing, f"Registry workflows missing from SKILL: {sorted(missing)}"


def test_skill_quick_reference_covers_registry(project_root: Path) -> None:
    """G-A2: every registry workflow must appear in SKILL Quick-Reference.

    Closed by P-03 in v7.4.6 — `nines-assisted` and `self-update` rows
    added to the Template Quick-Reference table per audit §3.A G-A2
    evidence; xfail marker removed per the audit §6 strict=True contract.

    Names in ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` are excluded — their
    Quick-Reference row is intentionally deferred to v8.2.9 per the v8.3.0
    patch plan.
    """
    missing = (
        _registry_names(project_root)
        - _skill_quick_reference_names(project_root)
        - _DEFERRED_DOC_TEMPLATES_V8_2_9
    )
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
        # v8.0.0 P-08 — L3 behavioral guidelines reference (BG-001..BG-004),
        # wired through the new top-level ``behavioral_guidelines`` dispatch
        # field at canonical_order position 14 (schema version 3).
        "behavioral-guidelines.md",
        # v8.3.0 PV-09 — agent workspace reference (Change folders, handoff
        # envelopes, archive, source-of-truth specs). Documents the
        # .local/.agent/ tree, append-only handoff envelopes (Rule S-9),
        # file-ownership constraints (Rule S-8), per-artifact token budgets
        # (Rule C-9), and the source-of-truth ADR (Rule A-4). Pairs with
        # the change-driven workflow template (v8.2.6) and the
        # devolaflow.agent_workspace Python API (v8.2.5+).
        "agent-workspace.md",
        # v8.4.0 rollup — RTK + memory-router stack reference. Documents the
        # rtk runtime plugin (workflow-system/agent/knowledge/runtime-plugins.yaml),
        # the shell_proxy/ package (registry + proxy + commands), the
        # pre_shell_call lifecycle hook (5th canonical event), the
        # memory_router/ planning fast-path, and the .local/memory/{cases,commands}/
        # recipe layers. Pairs with the v8.3.1 PV-01 + v8.3.2 PV-02 +
        # v8.3.3 PV-03 + v8.3.4 PV-04 surface area (R-001 + R-002 + M-001 + M-002).
        "shell-proxy.md",
        # v9.0.0 PV-01 (v8.4.1) — Plan-mode L0 operating contract reference.
        # Absorbs SKILL.md §"Mode Awareness" PLAN MODE detail + §"Reinforcement
        # Rules" mechanism into a single Tier-2 reference, freeing ~57 lines of
        # SKILL.md headroom (closes B-01 + R7 carry-forward). Documents the
        # plan output template, Constraints Checklist, P1-P5 invariants,
        # _PLAN_MODE_OVERRIDES runtime hook, reinforcement payload shape,
        # convergence loop mechanics, and stagnation-escalation protocol.
        # Pairs with src/devolaflow/gate/reinforcement.py (W-8 / SI-9).
        "plan-mode-enforcement.md",
        # v9.0.0 PV-05 (v8.5.0) — DEVOLAFLOW_* env-flag inventory reference.
        # Single source of truth for the 8 active runtime flags
        # (PLAN_MODE, RTK_PROXY, RTK_PROXY_TIER2, MEMORY_ROUTER, AUTO_INSTALL,
        # NINES_EDITABLE_PATH, PROBE_SCENARIO, MOCK_KEY) + the 6 forward-
        # declared gate-primitive flags scheduled for v8.5.1 PV-06 flip
        # (TOKEN_BUDGET_BREAKER, CYCLE_DETECTOR, GATE_RATCHET,
        # COMPLEXITY_DETECTOR, AC_GEN, LEGIBILITY_CHECK) + the 4 Karpathy
        # default-on behavioral primitives (BG-001..BG-004). Pairs with
        # Workflow Rule W-20 (env-flag reuse vs new-flag policy) so the
        # rule has an actionable inventory to enforce against.
        "env-flags.md",
        # v9.0.0 PV-06 (v8.5.1) — CompressionPipeline protocol + 6-transform
        # unification + multi-pass filter chain (T3 #5). Documents the
        # CompressionStage ABC, the CompressionPipeline orchestrator (with
        # R5 strict byte-identical bypass invariant), the three canonical
        # compositions (predecessor extractive / predecessor + Stage B LLM /
        # command-mapping + directed_compact + truncate), and the
        # compose: list[str] field semantics for command-mapping recipes
        # schema_version 2. Pairs with src/devolaflow/compression_pipeline.py
        # and schemas/compression-pipeline.yaml.
        "compression-pipeline.md",
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


def _skill_tier2_reference_names(project_root: Path) -> set[str]:
    """Extract `references/<name>.md` paths from SKILL.md's Tier-2 sub-table.

    Parses the ``## Reference Navigation Guide`` section, finds the
    ``**Tier 2 — Domain references**`` sub-table, and harvests every
    ``references/<name>.md`` cell value. Used by the parity test below
    to detect drift between SKILL.md's Tier-2 nav and the canonical
    ``_SF4_REFERENCE_SET`` declared above.
    """
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    nav = re.search(r"## Reference Navigation Guide\n(.*?)(?:\n## |\Z)", skill, re.DOTALL)
    if nav is None:
        return set()
    body = nav.group(1)
    tier2 = re.search(r"\*\*Tier 2.*?\n(.*?)(?:\n\*\*Tier 3|\Z)", body, re.DOTALL)
    if tier2 is None:
        return set()
    return set(re.findall(r"`references/([a-z][a-z0-9-]*\.md)`", tier2.group(1)))


def test_reference_skill_md_tier2_parity(project_root: Path) -> None:
    """v9.0.0 PV-01 NEW (closes F-04 SKILL.md ↔ SF-4 parity gap permanently).

    Asserts that the set of `references/<name>.md` rows in SKILL.md's
    ``## Reference Navigation Guide`` Tier-2 sub-table EXACTLY equals
    ``_SF4_REFERENCE_SET``. Drift in either direction (SKILL adds a row
    not in SF-4, or SF-4 adds an entry not surfaced in SKILL) is a
    blocker — this is the F-04 root-cause prevention test.

    F-04 history: ``behavioral-guidelines.md`` was added to ``_SF4_REFERENCE_SET``
    in v8.0.0 P-08 but the SKILL.md Tier-2 nav table was never updated until
    v8.4.1 (this PV); operators discovered the orphaned reference only via
    the dispatch payload's ``behavioral_guidelines`` field schema. PV-01
    inserted the missing row + adds this CI test so the gap cannot reopen.
    """
    nav_set = _skill_tier2_reference_names(project_root)
    canonical_set = set(_SF4_REFERENCE_SET)
    missing_in_nav = canonical_set - nav_set
    extra_in_nav = nav_set - canonical_set
    assert nav_set == canonical_set, (
        f"SKILL.md Reference Navigation Guide Tier-2 sub-table drifted from "
        f"_SF4_REFERENCE_SET — missing rows: {sorted(missing_in_nav)}, "
        f"extra rows: {sorted(extra_in_nav)}. Canonical SF-4 set has "
        f"{len(canonical_set)} entries; SKILL.md Tier-2 nav has {len(nav_set)}."
    )


def test_ghost_audit_refresh_present(project_root: Path) -> None:
    """v9.0.0 PV-05 NEW (Workflow Rule W-18 enforcement).

    Asserts that the latest CHANGELOG `## [vX.Y.Z]` entry references at
    least one identifier that surfaces in this ghost-audit module — the
    W-18 contract: every CHANGELOG entry mentioning a feature MUST have
    a corresponding ghost-audit lint somewhere in this file (per S-4
    "no ghost features" + the W-18 sharpening that adds the SEQUENCING
    requirement: refresh the audit BEFORE landing the CHANGELOG entry).

    Mechanism (intentionally lightweight to avoid regex / NLP coupling):

    1. Read the current `__version__` from ``src/devolaflow/__init__.py``.
    2. Find the corresponding ``## [<version>]`` block in CHANGELOG.md
       (or fall back to the most recent ``## [vX.Y.Z]`` block if the
       block for the current version has not yet been authored).
    3. Confirm the block is NON-EMPTY and has at least one bullet that
       cites a feature (rough heuristic: at least one bullet contains a
       backticked code identifier or a CamelCase symbol).
    4. Confirm THIS module (test_no_ghost_features.py) is non-empty —
       the existence + structure of this file is the W-18 audit
       artifact.

    The test is intentionally LENIENT — its purpose is to catch the
    case where a future PV silently empties the audit module or skips
    the CHANGELOG entry entirely. It is NOT a substitute for the per-
    feature lint tests above; those carry the strict pass/fail
    semantics. This test is the meta-guarantee that the audit-as-a-set
    stays alive at every PV.
    """
    init_text = _read(project_root / "src/devolaflow/__init__.py")
    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert version_match, "Cannot find __version__ in src/devolaflow/__init__.py"
    current_version = version_match.group(1)

    changelog = _read(project_root / "CHANGELOG.md")
    block_re = re.compile(rf"## \[{re.escape(current_version)}\](.*?)(?=\n## \[|\Z)", re.DOTALL)
    m = block_re.search(changelog)
    if m is None:
        any_block_re = re.compile(r"## \[\d+\.\d+\.\d+[^\]]*\](.*?)(?=\n## \[|\Z)", re.DOTALL)
        m = any_block_re.search(changelog)
    assert m is not None, "CHANGELOG.md has no ## [vX.Y.Z] block at all"

    block = m.group(1)
    has_feature_citation = bool(
        re.search(r"`[A-Za-z_][A-Za-z0-9_./-]+`", block)
        or re.search(r"\b[A-Z][a-zA-Z0-9]+[A-Z][a-zA-Z0-9]+\b", block)
    )
    assert has_feature_citation, (
        f"CHANGELOG block for {current_version!r} (or most-recent fallback) "
        f"has no feature citation (backticked identifier or CamelCase symbol). "
        f"W-18: every CHANGELOG entry mentioning a feature MUST have a "
        f"ghost-audit lint backing it."
    )

    audit_path = Path(__file__)
    audit_text = audit_path.read_text(encoding="utf-8")
    assert len(audit_text) > 0, "ghost-audit module is empty — W-18 violation"
    assert "_SF4_REFERENCE_SET" in audit_text, (
        "ghost-audit module is missing the _SF4_REFERENCE_SET pin — W-18 violation"
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

    G-I4 (``input_mapping``) explicitly carries the v7.6.x deferral reason
    per the user's 'mode_only' scope decision recorded in audit §9 Open Q1.
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
    """G-K1 pin: README project-structure template count matches disk
    (modulo templates whose README integration is deferred to v8.2.9 —
    see ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` at the top of this module)."""
    readme = _read(project_root / "README.md")
    actual = len(_builtin_template_files(project_root))
    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_names(project_root)
    expected = actual - len(deferred_present)
    stale = re.findall(r"#\s*(\d+)\s+workflow template YAMLs", readme)
    assert stale, "README must contain the 'N workflow template YAMLs' line"
    for s in stale:
        assert int(s) == expected, (
            f"README claims {s} templates, disk has {actual}, expected claim "
            f"{expected} (= disk - {len(deferred_present)} deferred to v8.2.9) — "
            f"G-K1 regressed"
        )


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
    """G-K2/K3 pin: EN+ZH workflow-type guide rows agree with disk
    (modulo templates whose bilingual guide row is deferred to v8.2.9 —
    see ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` at the top of this module)."""
    readme = _read(project_root / "README.md")
    actual = len(_builtin_template_files(project_root))
    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_names(project_root)
    expected = actual - len(deferred_present)
    en = re.search(r"All\s+(\d+)\s+workflow types", readme)
    assert en, "README EN guide must say 'All N workflow types'"
    assert int(en.group(1)) == expected, (
        f"README EN claims {en.group(1)} types, disk has {actual}, expected "
        f"claim {expected} (= disk - {len(deferred_present)} deferred to v8.2.9) — "
        f"G-K2 regressed"
    )
    zh = re.search(r"全部\s*(\d+)\s*种工作流类型", readme)
    assert zh, "README ZH guide must say '全部 N 种工作流类型'"
    assert int(zh.group(1)) == expected, (
        f"README ZH claims {zh.group(1)} types, disk has {actual}, expected "
        f"claim {expected} (= disk - {len(deferred_present)} deferred to v8.2.9) — "
        f"G-K3 regressed (DS-3 bilingual drift)"
    )


def test_workflow_skill_yaml_template_count_comment(project_root: Path) -> None:
    """G-K10 pin: workflow-skill.yaml templates comment matches disk
    (modulo templates whose workflow-skill.yaml entry is deferred to v8.2.9 —
    see ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` at the top of this module)."""
    text = _read(project_root / "workflow-system/agent/workflow-skill.yaml")
    actual = len(_builtin_template_files(project_root))
    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_names(project_root)
    expected = actual - len(deferred_present)
    match = re.search(r"#\s*Registry\s*\+\s*(\d+)\s+builtin\s+templates", text)
    assert match, "workflow-skill.yaml must contain 'Registry + N builtin templates'"
    assert int(match.group(1)) == expected, (
        f"workflow-skill.yaml claims {match.group(1)} templates, disk has "
        f"{actual}, expected claim {expected} (= disk - {len(deferred_present)} "
        f"deferred to v8.2.9) — G-K10 regressed"
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


# ── Architecture Rule A-5 — Single-Source-of-Truth Registry Pattern ──────
# v8.4.3 PV-03 of v9.0.0 cycle. Codifies the "every domain registry surface
# has exactly ONE owner module" invariant. The 5 baseline registries are
# pinned by name + canonical owner path; the parity test fails when an AST
# walk finds more than one module-level definition for the same registry
# name (the M-002 / M-001 anti-pattern: half a whitelist in one file + half
# in another). YAML-backed registries are guarded by file-path uniqueness.

# Python-backed SSOT registries: symbol_name -> canonical owner relpath.
_SSOT_PYTHON_REGISTRIES: dict[str, str] = {
    "WHITELIST": "src/devolaflow/shell_proxy/registry.py",
    "MemoryCase": "src/devolaflow/memory_router/cache.py",
    "CommandMapping": "src/devolaflow/shell_proxy/commands.py",
}

# YAML-backed SSOT registries: registry display name -> canonical relpath.
_SSOT_YAML_REGISTRIES: dict[str, str] = {
    "plugins.yaml": "workflow-system/agent/plugins.yaml",
    "runtime-plugins.yaml": "workflow-system/agent/knowledge/runtime-plugins.yaml",
}


def _module_level_definers(symbol_name: str, src_root: Path) -> list[Path]:
    """Return every ``.py`` file under *src_root* with a module-level definition of *symbol_name*.

    A "module-level definition" is one of:

    * ``class <symbol_name>:`` — covers ``MemoryCase`` / ``CommandMapping``.
    * ``def <symbol_name>(...):`` / ``async def <symbol_name>(...):`` —
      defensive coverage for callables ever promoted to SSOT status.
    * ``<symbol_name> = ...`` (``ast.Assign`` with ``ast.Name`` target) —
      covers ``WHITELIST = {...}``.
    * ``<symbol_name>: <Annotation> = ...`` (``ast.AnnAssign``) — defensive
      coverage for annotated module-level constants.

    Files that fail to parse are skipped (not silently ignored — the parse
    failure surfaces in the linter / unit tests for that file).
    """
    definers: list[Path] = []
    for f in sorted(src_root.rglob("*.py")):
        if any(part == "__pycache__" for part in f.parts):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in tree.body:
            if _node_defines_symbol(node, symbol_name):
                definers.append(f)
                break
    return definers


def _node_defines_symbol(node: ast.AST, symbol_name: str) -> bool:
    """Return True iff *node* is a module-level definition of *symbol_name*.

    Recognises ``class`` / ``def`` / ``async def`` (named definitions) and
    ``Name = ...`` / ``Name: T = ...`` (constant assignments). Anything
    else (imports, expression statements, conditional re-exports) is not
    a definition and returns False.
    """
    if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
        return node.name == symbol_name
    if isinstance(node, ast.Assign):
        return any(
            isinstance(target, ast.Name) and target.id == symbol_name for target in node.targets
        )
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == symbol_name
    return False


def test_registry_single_owner(project_root: Path) -> None:
    """A-5: each domain-SSOT registry must have exactly one owner module.

    Per Architecture Rule A-5 (`.rules/architecture.mdc` §A-5.1), splitting
    registration data across two modules invalidates cache reasoning and is
    a release blocker. This test AST-walks ``src/devolaflow/`` and asserts:

    1. Each Python-backed registry symbol (`WHITELIST`, `MemoryCase`,
       `CommandMapping`) has exactly ONE module-level definer.
    2. The single definer matches the canonical owner path declared above.
    3. Each YAML-backed registry (`plugins.yaml`, `runtime-plugins.yaml`)
       lives at exactly its canonical path (file-path uniqueness — there
       is no `find` step because the registry-loading helpers in
       ``devolaflow.plugins.{loader,installer}`` import these via verbatim
       paths, not glob patterns).

    Failure means a NEW module shadowed an SSOT registration without
    routing through the owner module — the M-001 / M-002 anti-pattern
    that A-5 forbids.
    """
    src_root = project_root / "src" / "devolaflow"
    assert src_root.is_dir(), f"src/devolaflow/ missing — cannot audit (looked under {src_root})"

    for symbol_name, expected_relpath in _SSOT_PYTHON_REGISTRIES.items():
        definers = _module_level_definers(symbol_name, src_root)
        rel_definers = sorted(d.relative_to(project_root).as_posix() for d in definers)
        assert len(definers) == 1, (
            f"A-5 violation: registry symbol {symbol_name!r} has {len(definers)} "
            f"module-level owners {rel_definers}; expected exactly 1 "
            f"({expected_relpath})"
        )
        actual_relpath = definers[0].relative_to(project_root).as_posix()
        assert actual_relpath == expected_relpath, (
            f"A-5 violation: registry {symbol_name!r} owner is {actual_relpath} "
            f"but the canonical owner per .rules/architecture.mdc::A-5 is "
            f"{expected_relpath}"
        )

    for yaml_name, expected_relpath in _SSOT_YAML_REGISTRIES.items():
        yaml_path = project_root / expected_relpath
        assert yaml_path.is_file(), (
            f"A-5 violation: YAML SSOT registry {yaml_name!r} expected at "
            f"{expected_relpath} but file is missing"
        )


# ── v9.0.0 PV-07 — Rule Taxonomy Rebalancing (ADR-007) ─────────────────
# Two new lints enforce the PV-07 governance contract:
#
#   * test_rule_count_under_cap — total compiled-AGENTS.md rule count ≤ 60
#     (HARD per ADR-007 D5). Rule count = sum of `^## ([SACW]|ST)-\d+`
#     headings in AGENTS.md (the operator-facing canonical compile output).
#   * test_rule_surfaces_compile_only — `.cursor/rules/repo-governance.mdc`
#     SHA-256 matches the value stored in `.rules/.compile-hashes.json`
#     (drift detection); the 2 deprecated `.cursor/rules/{devola-flow,workflow}-
#     rules.mdc` stubs match expected stub-template fingerprints (preventing
#     hand-edits). Failure means the canonical-vs-compiled invariant is broken
#     OR a stub was hand-edited to drift from the deprecation scaffold.

# v9.0.0 PV-07 (ADR-007 D5) — HARD cap on the total rule count surfaced by
# the compiled AGENTS.md. The 60 cap derives from improvements_zh.md
# §"Rule cap" + the cumulative additions across the v9.0.0 cycle (PV-03
# A-5 + PV-04 S-10 + PV-05 W-16..W-20 + PV-07 W-21 = 7 net additions on top
# of the v8.4.0 baseline of 50). Post-PV-07 rule census: Soul 10 + Arch 5 +
# Conv 9 + Workflow 21 = 45 rules in AGENTS.md (Style is excluded from
# AGENTS.md per `compile-config.yaml#agents_md.include_layers`); the
# repo-governance.mdc target additionally surfaces Style 13 → 58 total
# in the cursor target. The cap is enforced on the AGENTS.md surface (the
# operator-facing canonical compile output).
_RULE_COUNT_CAP_HARD: int = 60
_SOUL_FREEZE_COUNT: int = 10  # post-W-21 Soul-set freeze (ADR-007 D4)


def test_rule_count_under_cap(project_root: Path) -> None:
    """ADR-007 D5: AGENTS.md compiled rule count ≤ 60 HARD.

    Counts every ``^## ([SACW]|ST)-\\d+`` heading in the compiled AGENTS.md
    file and asserts the total stays at or below the 60-rule HARD cap from
    `improvements_zh.md` §"Rule cap" + ADR-007 D5. Also pins:

    1. The Soul-set count at exactly 10 (S-1..S-10, frozen by W-21 Soul-set
       freeze governance per ADR-007 D4).
    2. The Architecture count at exactly 5 (A-1..A-5).
    3. The total stays ≤ 60.

    Future cycles proposing a new rule MUST first confirm `total + 1 ≤ 60`
    before authoring; if the projection exceeds 60, the proposing PV must
    either (a) defer an existing rule, OR (b) explicitly raise the cap via
    a new ADR. Soul additions further require the W-21 2-cycle telegraph
    protocol (deferral note in cycle N retrospective → SI-1 in cycle N+2 →
    SI-3 §3.2 ≥ 9.5/10 in cycle N+2) before bumping past 10.
    """
    from devolaflow.task_adaptive_selector import count_agents_md_rules

    agents_md = project_root / "AGENTS.md"
    assert agents_md.is_file(), (
        f"AGENTS.md missing at {agents_md.relative_to(project_root)} — "
        f"run `python -c 'from devolaflow.local.compiler import RuleCompiler; "
        f'RuleCompiler(".rules/compile-config.yaml").compile_all()\'` to regenerate'
    )

    census = count_agents_md_rules(agents_md_path=agents_md)
    total = census["total"]
    by_layer = census["by_layer"]

    assert total <= _RULE_COUNT_CAP_HARD, (
        f"ADR-007 D5 violation: AGENTS.md rule count {total} exceeds "
        f"the 60 HARD cap. Per-layer breakdown: {by_layer}. "
        f"Future PVs adding rules MUST either defer an existing rule OR "
        f"explicitly raise the cap via a new ADR."
    )

    soul_count = by_layer.get("soul", 0)
    assert soul_count == _SOUL_FREEZE_COUNT, (
        f"ADR-007 D4 violation: Soul-set count {soul_count} != frozen count "
        f"{_SOUL_FREEZE_COUNT} (S-1..S-10). Soul additions require the W-21 "
        f"2-cycle telegraph protocol (cycle N retrospective deferral → cycle "
        f"N+2 SI-1 gap analysis → cycle N+2 SI-3 §3.2 ≥ 9.5/10) before landing."
    )


def test_rule_surfaces_compile_only(project_root: Path) -> None:
    """ADR-007 D2 + D5: `.cursor/rules/*.mdc` files must be compile-only.

    Two-part invariant per ADR-007:

    1. **D5** — `.cursor/rules/repo-governance.mdc` (the compiled full corpus)
       SHA-256 matches the `cursor` entry in `.rules/.compile-hashes.json`.
       A hand-edit to the compiled file shifts the SHA-256 and fails this
       assertion — operators MUST regenerate via
       `RuleCompiler('.rules/compile-config.yaml').compile_all()` instead
       of editing the compiled output directly.

    2. **D2** — the 2 deprecated stubs
       (`.cursor/rules/devola-flow-rules.mdc` + `.cursor/rules/workflow-rules.mdc`)
       must match the stub-template fingerprints stored under
       `stub_devola_flow_rules` / `stub_workflow_rules` in
       `.rules/.compile-hashes.json`. The stubs are pinned cross-reference
       scaffolds per ADR-007 D2 — a hand-edit either drifts the SHA-256 OR
       grows the stub past the ≤ 50-line ceiling enforced by the inline
       length check below.

    Failure modes:
      * "compiled file SHA-256 mismatch" → operator hand-edited
        `repo-governance.mdc`; re-run `RuleCompiler.compile_all()`.
      * "stub SHA-256 mismatch" → operator hand-edited a deprecated stub;
        the stubs are intentionally frozen as cross-reference scaffolds.
      * "stub line count > 50" → a stub grew past the deprecation ceiling;
        either compress back or re-evaluate the deprecation decision.
      * "compile-hashes.json missing key" → drift store wasn't regenerated
        with the v9.0.0 PV-07 stub fingerprints; re-run
        `RuleCompiler.compile_all()` after the v9.0.0 update.
    """
    from devolaflow.local.drift import (
        DEPRECATED_STUB_FILES,
        check_rules_drift,
        check_stub_drift,
    )

    rules_dir = project_root / ".rules"
    hash_file = rules_dir / ".compile-hashes.json"
    assert hash_file.is_file(), (
        f"compile hash store missing at {hash_file.relative_to(project_root)} — "
        f"run RuleCompiler('.rules/compile-config.yaml').compile_all() to populate it"
    )

    compiled_results = check_rules_drift(rules_dir=rules_dir)
    drifted = [r for r in compiled_results if r.status == "drifted"]
    assert not drifted, (
        f"ADR-007 D5 violation: compiled .cursor/rules/* targets drifted from "
        f"the .rules/ source: {[(r.target, r.expected_hash, r.actual_hash) for r in drifted]}. "
        f"Re-run RuleCompiler.compile_all() to regenerate."
    )

    missing_compiled = [r for r in compiled_results if r.status == "missing"]
    assert not missing_compiled, (
        f"ADR-007 D5 violation: compiled .cursor/rules/* targets missing on "
        f"disk: {[r.target for r in missing_compiled]}. Re-run "
        f"RuleCompiler.compile_all() to regenerate."
    )

    stub_results = check_stub_drift(repo_root=project_root, hash_file=hash_file)
    drifted_stubs = [r for r in stub_results if r.status == "drifted"]
    assert not drifted_stubs, (
        f"ADR-007 D2 violation: deprecated stub fingerprints drifted from "
        f".rules/.compile-hashes.json: "
        f"{[(r.target, r.expected_hash, r.actual_hash) for r in drifted_stubs]}. "
        f"The stubs at .cursor/rules/{{devola-flow,workflow}}-rules.mdc are "
        f"PINNED cross-reference scaffolds — re-run "
        f"RuleCompiler.compile_all() after re-applying the canonical stub "
        f"template, OR investigate why the stubs were hand-edited."
    )

    missing_stubs = [r for r in stub_results if r.status == "missing"]
    assert not missing_stubs, (
        f"ADR-007 D2 violation: deprecated stub or fingerprint missing: "
        f"{[r.target for r in missing_stubs]}. Re-run RuleCompiler.compile_all() "
        f"after restoring the deprecated stub files."
    )

    for _key, relpath in DEPRECATED_STUB_FILES:
        stub_path = project_root / relpath
        assert stub_path.is_file(), f"Deprecated stub missing: {relpath}"
        line_count = stub_path.read_text(encoding="utf-8").count("\n") + 1
        assert line_count <= 50, (
            f"ADR-007 D2 violation: deprecated stub {relpath} has {line_count} "
            f"lines — must be ≤ 50 (cross-reference scaffold ceiling). The stub "
            f"is intentionally minimal; expand canonical content under .rules/ "
            f"instead and let the compiler re-emit the full corpus."
        )


# ── v9.1.0 W3-04 — W-18 ghost-audit refresh for v9.1.0 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.0 introduces
# the surfaces below; this block adds presence + import-smoke + signature
# coverage for all of them as the W-18 PRECONDITION discharge:
#
#   * src/devolaflow/lifecycle/check_envelope_append_only.py — new module
#     binding the S-9 invariant (handoff envelopes are append-only) to
#     the `envelope_write` lifecycle event.
#   * lifecycle/ENVELOPE_WRITE_EVENT — new exported event constant
#     (canonical name `"envelope_write"`).
#   * lifecycle/DEFAULT_EVENTS length 6 → 7 (envelope_write APPENDED at
#     position 7 to preserve the A-2.4 cache-prefix invariant — existing
#     event positions 1-6 stay byte-stable per the lifecycle/__init__.py
#     v9.1.0 W1-02 changelog comment).
#   * tests/test_handoff_envelope_immutable.py — new test file pinning
#     the S-9 invariant against the envelope writer.
#   * tests/test_lifecycle_envelope_append_only.py — new test file
#     covering the envelope-write hook unit semantics.
#   * tests/test_rules_index_accuracy.py — new test file covering the
#     G-013 lint (rules index accuracy).
#   * tests/test_local_layer_completeness.py — new test file covering
#     the G-014 lint (local-layer completeness audit).
#   * init_project.install_local(compile_rules=True) — new keyword-only
#     parameter wired to the `--no-compile` CLI flag (closes G-007 +
#     G-016: `devola-init local` now auto-compiles `.rules/` →
#     `.cursor/rules/repo-governance.mdc` + `AGENTS.md` immediately).

_V9_1_0_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/lifecycle/check_envelope_append_only.py",
    "tests/test_handoff_envelope_immutable.py",
    "tests/test_lifecycle_envelope_append_only.py",
    "tests/test_rules_index_accuracy.py",
    "tests/test_local_layer_completeness.py",
)

# Minimum byte size for a v9.1.0 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_0_FILE_MIN_BYTES: int = 50

# Expected DEFAULT_EVENTS tuple length floor after the v9.1.0 W1-02 bump.
# Before W1-02: 6 (pre_dispatch, post_dispatch, file_write, task_stop,
# format_on_edit, pre_shell_call). After W1-02: 7 (above + envelope_write
# APPENDED at position 7 per A-2.4 cache-prefix invariant). Future PVs
# may append additional events at the tail (e.g. v9.1.3 PV-03 appended
# `pre_handoff` at position 8); the v9.1.0 invariant is that
# envelope_write STAYS at position 7 — this lint asserts the floor +
# the position pin, NOT exact equality on length.
_V9_1_0_DEFAULT_EVENTS_COUNT: int = 7


def test_v9_1_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.0: every NEW v9.1.0 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.0 introduces the surfaces
    enumerated in the comment block above this test; this lint asserts
    each one as a cheap presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_0_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_0_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``ENVELOPE_WRITE_EVENT`` and
       ``check_envelope_append_only`` are importable from
       :mod:`devolaflow.lifecycle` and the event constant equals
       ``"envelope_write"`` (the canonical name re-exported from
       :mod:`devolaflow.lifecycle.check_envelope_append_only`).
    3. **DEFAULT_EVENTS** tuple length is exactly
       ``_V9_1_0_DEFAULT_EVENTS_COUNT`` (7 — the v9.1.0 W1-02 bump from
       6 → 7 with ``envelope_write`` APPENDED at position 7 per the
       A-2.4 cache-prefix invariant) and contains
       ``ENVELOPE_WRITE_EVENT``.

    Failure modes:
      * "missing on disk" → a v9.1.0 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_0_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "DEFAULT_EVENTS length != 7" → the lifecycle event tuple was
        edited in violation of the A-2.4 append-only contract; verify
        ``envelope_write`` is still appended at position 7.
    """
    for relpath in _V9_1_0_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.0 violation: NEW v9.1.0 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_0_FILE_MIN_BYTES, (
            f"W-18 v9.1.0 violation: NEW v9.1.0 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_0_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.lifecycle import (
        DEFAULT_EVENTS,
        ENVELOPE_WRITE_EVENT,
        check_envelope_append_only,
    )

    assert ENVELOPE_WRITE_EVENT == "envelope_write", (
        f"W-18 v9.1.0 violation: ENVELOPE_WRITE_EVENT exported value "
        f"{ENVELOPE_WRITE_EVENT!r} != 'envelope_write' (the canonical event "
        f"name from check_envelope_append_only.EVENT)"
    )
    assert callable(check_envelope_append_only), (
        "W-18 v9.1.0 violation: check_envelope_append_only is not callable — "
        "the export from devolaflow.lifecycle must be the hook function itself"
    )
    assert len(DEFAULT_EVENTS) >= _V9_1_0_DEFAULT_EVENTS_COUNT, (
        f"W-18 v9.1.0 violation: lifecycle.DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected ≥ {_V9_1_0_DEFAULT_EVENTS_COUNT} "
        f"(v9.1.0 W1-02 bumped 6 → 7 with envelope_write APPENDED at "
        f"position 7 per A-2.4 cache-prefix invariant). Current events: "
        f"{DEFAULT_EVENTS!r}"
    )
    assert ENVELOPE_WRITE_EVENT in DEFAULT_EVENTS, (
        f"W-18 v9.1.0 violation: ENVELOPE_WRITE_EVENT not registered in "
        f"DEFAULT_EVENTS tuple {DEFAULT_EVENTS!r} — the W1-02 append step "
        f"was incomplete"
    )
    # A-2.4 position pin: envelope_write MUST stay at position 7 (the
    # v9.1.0 W1-02 contract). Future appends extend the tuple to
    # position 8+ but never disturb earlier positions.
    assert DEFAULT_EVENTS[6] == ENVELOPE_WRITE_EVENT, (
        f"A-2.4 violation: envelope_write must STAY at position 7 of "
        f"DEFAULT_EVENTS (the v9.1.0 W1-02 invariant). Got "
        f"DEFAULT_EVENTS[6]={DEFAULT_EVENTS[6]!r}; full tuple: {DEFAULT_EVENTS!r}"
    )


def test_install_local_has_compile_rules_kwarg() -> None:
    """W-18 v9.1.0: install_local() exposes the compile_rules keyword.

    Asserts the v9.1.0 W2-02 (G-007 + G-016 closure) signature change:
    :func:`devolaflow.init_project.install_local` MUST accept a
    ``compile_rules`` parameter that:

    * is present in :func:`inspect.signature(install_local).parameters`,
    * defaults to ``True`` (auto-compile on by default — fresh repos
      receive their compiled ``.cursor/rules/repo-governance.mdc`` +
      ``AGENTS.md`` on the first ``devola-init local`` run instead of
      requiring a separate ``devola-init sync-rules`` invocation),
    * is ``KEYWORD_ONLY`` (the function signature uses ``*`` as the
      separator so positional callers are forbidden — keeps the call
      site explicit and prevents the kwarg from drifting into the
      positional-argument cache prefix per A-2.4 reasoning).

    The kwarg is wired to the ``--no-compile`` CLI flag in
    :func:`devolaflow.init_project.main` so operators can disable
    auto-compile without mocking ``sys.argv`` in tests.
    """
    import inspect

    from devolaflow.init_project import install_local

    sig = inspect.signature(install_local)
    params = sig.parameters

    assert "compile_rules" in params, (
        f"W-18 v9.1.0 violation: install_local() signature missing "
        f"compile_rules parameter — present parameters: {sorted(params)}. "
        f"v9.1.0 W2-02 (G-007 + G-016) requires the kwarg to wire "
        f"`devola-init local --no-compile`."
    )

    cr = params["compile_rules"]
    assert cr.default is True, (
        f"W-18 v9.1.0 violation: install_local(compile_rules=...) default is "
        f"{cr.default!r}, expected True (auto-compile is the v9.1.0 W2-02 "
        f"default — fresh repos receive their compiled rules immediately; "
        f"--no-compile is the explicit opt-out)"
    )
    assert cr.kind == inspect.Parameter.KEYWORD_ONLY, (
        f"W-18 v9.1.0 violation: install_local(compile_rules=...) kind is "
        f"{cr.kind.name}, expected KEYWORD_ONLY (the function signature uses "
        f"`*` as the separator so positional callers are forbidden — keeps "
        f"the call site explicit per A-2.4 cache-prefix reasoning)"
    )


# ── v9.1.1 PV-01 — W-18 ghost-audit refresh for v9.1.1 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.1 PV-01
# (cycle v9.2.0 start) introduces the surfaces below; this block adds
# presence + import-smoke + signature coverage for all of them as the
# W-18 PRECONDITION discharge:
#
#   * src/devolaflow/workspace_context.py — new module exposing
#     scan_workspace() + WorkspaceContext frozen dataclass (the
#     discovery API for `.local/` + `.rules/` + `.local/.agent/`
#     surfaces in a consumer repo).
#   * tests/test_workspace_context_scan.py — new test file pinning
#     the scan_workspace() detection contract (6 tests).
#   * benchmarks/devolaflow_context/baselines/v9.2.0_baseline.json —
#     W-16 wholesale baseline regen (cycle-start MINOR per W-16).

_V9_1_1_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/workspace_context.py",
    "tests/test_workspace_context_scan.py",
    "benchmarks/devolaflow_context/baselines/v9.2.0_baseline.json",
)

# Minimum byte size for a v9.1.1 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_1_FILE_MIN_BYTES: int = 50


def test_v9_1_1_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.1: every NEW v9.1.1 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.1 PV-01 (the v9.2.0 cycle
    start) introduces the surfaces enumerated in the comment block above
    this test; this lint asserts each one as a cheap presence +
    import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_1_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_1_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``scan_workspace`` and ``WorkspaceContext``
       are importable from :mod:`devolaflow.workspace_context`,
       ``scan_workspace`` is callable, and ``WorkspaceContext`` is a
       :func:`dataclasses.is_dataclass`-true frozen dataclass.
    3. **Public summary surface** — :data:`MAX_FEEDBACKS_RETURNED` is
       importable and equals ``3`` (matching
       ``references/plan-mode-enforcement.md`` §"Feedback Ingestion"),
       AND :meth:`WorkspaceContext.to_summary_dict` exists and is
       callable (the JSON-serialisable rendering used by dispatch
       context injection).

    Failure modes:
      * "missing on disk" → a v9.1.1 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_1_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "WorkspaceContext is not frozen" → the dataclass dropped
        ``frozen=True`` (the design contract — consumers cannot mutate
        a snapshot in flight); restore the freeze.
    """
    import dataclasses

    for relpath in _V9_1_1_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.1 violation: NEW v9.1.1 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_1_FILE_MIN_BYTES, (
            f"W-18 v9.1.1 violation: NEW v9.1.1 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_1_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.workspace_context import (
        MAX_FEEDBACKS_RETURNED,
        WorkspaceContext,
        scan_workspace,
    )

    assert scan_workspace is not None, "W-18 v9.1.1 violation: scan_workspace import yielded None"
    assert callable(scan_workspace), (
        "W-18 v9.1.1 violation: scan_workspace is not callable — the export "
        "from devolaflow.workspace_context must be the function itself"
    )
    assert WorkspaceContext is not None, (
        "W-18 v9.1.1 violation: WorkspaceContext import yielded None"
    )
    assert dataclasses.is_dataclass(WorkspaceContext), (
        "W-18 v9.1.1 violation: WorkspaceContext is not a dataclass — the "
        "discovery API contract requires a structured frozen dataclass"
    )
    assert MAX_FEEDBACKS_RETURNED == 3, (
        f"W-18 v9.1.1 violation: MAX_FEEDBACKS_RETURNED is "
        f"{MAX_FEEDBACKS_RETURNED!r} (expected 3) — the public constant pins "
        f"the plan-mode feedback ingestion default per "
        f"references/plan-mode-enforcement.md §'Feedback Ingestion'"
    )
    assert hasattr(WorkspaceContext, "to_summary_dict"), (
        "W-18 v9.1.1 violation: WorkspaceContext is missing the "
        "to_summary_dict() method — the JSON-serialisable summary contract "
        "is part of the v9.1.1 PV-01 public surface"
    )
    assert callable(WorkspaceContext.to_summary_dict), (
        "W-18 v9.1.1 violation: WorkspaceContext.to_summary_dict is not callable"
    )

    # Frozen invariant: instantiating + attempting to mutate raises
    # FrozenInstanceError. Pins the design contract that consumers cannot
    # mutate a snapshot in flight (the snapshot is a value type — derive
    # a new one via dataclasses.replace if you need a modified copy).
    sample = WorkspaceContext(
        repo_root=project_root,
        has_local=False,
        has_rules=False,
        has_agent_dir=False,
    )
    try:
        sample.has_local = True  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover — the assert below catches the regression
        raise AssertionError(
            "W-18 v9.1.1 violation: WorkspaceContext is not frozen — "
            "attribute assignment did not raise FrozenInstanceError. "
            "The dataclass MUST be declared with frozen=True so consumers "
            "cannot mutate a snapshot in flight."
        )


# ── v9.1.2 PV-02 — W-18 ghost-audit refresh for v9.1.2 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.2 PV-02
# (cycle v9.2.0 second PV) introduces the surfaces below; this block
# adds presence + import-smoke + signature coverage for all of them as
# the W-18 PRECONDITION discharge:
#
#   * src/devolaflow/skills/__init__.py — new package marker.
#   * src/devolaflow/skills/change_activation.py — pure-function
#     classifier + activation verdict (the heuristic codified by
#     Architecture rule A-6 "Workspace Engagement Auto-Activation"
#     per `.rules/architecture.mdc`).
#   * src/devolaflow/skills/slash_commands.py — `/devola:propose` /
#     `/devola:apply` / `/devola:verify` / `/devola:archive` thin
#     wrappers around `agent_workspace.ChangeStore` +
#     `ArchiveManager` (closes M-007 from v9.0.0 retro §3.3).
#   * tests/test_change_activation_heuristic.py — heuristic contract
#     pin (5+ tests covering the 3 verdict cases + opt-out + R5
#     strict env-flag parsing).
#   * tests/test_slash_commands.py — CLI happy-path pin (6+ tests
#     covering propose / apply / verify / archive + main entry).

_V9_1_2_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/skills/__init__.py",
    "src/devolaflow/skills/change_activation.py",
    "src/devolaflow/skills/slash_commands.py",
    "tests/test_change_activation_heuristic.py",
    "tests/test_slash_commands.py",
)

# Minimum byte size for a v9.1.2 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_2_FILE_MIN_BYTES: int = 50


def test_v9_1_2_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.2: every NEW v9.1.2 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.2 PV-02 (the second PV of
    the v9.2.0 cycle) introduces the surfaces enumerated in the comment
    block above this test; this lint asserts each one as a cheap
    presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_2_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_2_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Heuristic import-smoke** — ``classify_complexity`` and
       ``activation_verdict`` are importable from
       :mod:`devolaflow.skills.change_activation`, both are callable,
       and the ``ENV_FLAG_NAME`` constant equals
       ``"DEVOLAFLOW_AGENT_WORKSPACE"`` (W-20 reuse — same surface as
       v9.1.1 PV-01 SKILL.md §"Workspace Engagement").
    3. **Slash-command import-smoke** — ``main`` and ``slugify`` and
       ``scaffold_change_folder`` are importable from
       :mod:`devolaflow.skills.slash_commands`, ``main`` is callable
       (the ``python -m devolaflow.skills.slash_commands`` entry
       point), and ``REQUIRE_VERIFY_STATE == "VERIFYING"`` (the
       canonical FSM state name per
       ``schemas/agent-workspace/change-status.yaml#fsm_states``).

    Failure modes:
      * "missing on disk" → a v9.1.2 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_2_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "ENV_FLAG_NAME mismatch" → a NEW env flag was authored,
        violating W-20 reuse-first; either restore the REUSE or
        document the orthogonality argument per W-20 §3.
      * "REQUIRE_VERIFY_STATE mismatch" → the slash command drifted
        from the canonical FSM state; restore the contract.
    """
    for relpath in _V9_1_2_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.2 violation: NEW v9.1.2 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_2_FILE_MIN_BYTES, (
            f"W-18 v9.1.2 violation: NEW v9.1.2 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_2_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.skills.change_activation import (
        ENV_FLAG_NAME,
        ENV_FLAG_TRUTHY,
        activation_verdict,
        classify_complexity,
        from_env,
    )

    assert callable(classify_complexity), (
        "W-18 v9.1.2 violation: classify_complexity is not callable — the "
        "heuristic export from devolaflow.skills.change_activation must be "
        "the function itself"
    )
    assert callable(activation_verdict), "W-18 v9.1.2 violation: activation_verdict is not callable"
    assert callable(from_env), "W-18 v9.1.2 violation: from_env is not callable"
    assert ENV_FLAG_NAME == "DEVOLAFLOW_AGENT_WORKSPACE", (
        f"W-18 v9.1.2 violation: ENV_FLAG_NAME is {ENV_FLAG_NAME!r} (expected "
        f"'DEVOLAFLOW_AGENT_WORKSPACE') — W-20 reuse-first MUST hold; the "
        f"v9.1.2 PV-02 activation surface MUST REUSE the v9.1.1 PV-01 flag, "
        f"not author a new one"
    )
    assert ENV_FLAG_TRUTHY == "1", (
        f"W-18 v9.1.2 violation: ENV_FLAG_TRUTHY is {ENV_FLAG_TRUTHY!r} "
        f"(expected '1') — R5 strict opt-in REQUIRES the literal '1' string"
    )

    from devolaflow.skills.slash_commands import (
        ARCHIVE_GATE_THRESHOLD,
        REQUIRE_VERIFY_STATE,
        main,
        scaffold_change_folder,
        slugify,
    )

    assert callable(main), (
        "W-18 v9.1.2 violation: slash_commands.main is not callable — the "
        "`python -m devolaflow.skills.slash_commands` entry point requires it"
    )
    assert callable(slugify), "W-18 v9.1.2 violation: slugify is not callable"
    assert callable(scaffold_change_folder), (
        "W-18 v9.1.2 violation: scaffold_change_folder is not callable"
    )
    assert REQUIRE_VERIFY_STATE == "VERIFYING", (
        f"W-18 v9.1.2 violation: REQUIRE_VERIFY_STATE is "
        f"{REQUIRE_VERIFY_STATE!r} (expected 'VERIFYING') — the canonical "
        f"FSM state name per schemas/agent-workspace/change-status.yaml"
    )
    assert ARCHIVE_GATE_THRESHOLD == 8.5, (
        f"W-18 v9.1.2 violation: ARCHIVE_GATE_THRESHOLD is "
        f"{ARCHIVE_GATE_THRESHOLD!r} (expected 8.5) — the W-3 / SI-3 "
        f"PATCH/MINOR composite floor per Rule A-4"
    )


# ── v9.1.3 PV-03 — W-18 ghost-audit refresh for v9.1.3 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.3 PV-03
# (cycle v9.2.0 third PV) closes G-005 deferred from v9.1.0 by creating
# the FIRST production caller of `HandoffStore.write_envelope` outside
# the module itself; this block adds presence + import-smoke + signature
# coverage for all new surfaces as the W-18 PRECONDITION discharge:
#
#   * src/devolaflow/lifecycle/auto_write_handoff.py — new module
#     binding the auto-write decision to the new `pre_handoff` lifecycle
#     event. Permissive no-op when `DEVOLAFLOW_AGENT_WORKSPACE` is unset
#     (R5 strict byte-identical); writes a handoff envelope when the
#     env-flag is set AND the dispatch payload carries a populated
#     `change_context` block. Honours Rule S-9 append-only ledger via
#     EnvelopeImmutableError surfacing (AWH002 warning in permissive,
#     re-raise in strict).
#   * lifecycle/PRE_HANDOFF_EVENT — new exported event constant
#     (canonical name `"pre_handoff"`).
#   * lifecycle/DEFAULT_EVENTS length 7 → 8 (pre_handoff APPENDED at
#     position 8 to preserve the A-2.4 cache-prefix invariant — existing
#     event positions 1-7 stay byte-stable per the lifecycle/__init__.py
#     v9.1.3 PV-03 changelog comment).
#   * tests/test_handoff_auto_write.py — new test file pinning the
#     auto-write hook contract (env-flag OFF noop, AWH001/AWH002 codes,
#     seq monotonic, strict-mode raise propagation).

_V9_1_3_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/lifecycle/auto_write_handoff.py",
    "tests/test_handoff_auto_write.py",
)

# Minimum byte size for a v9.1.3 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_3_FILE_MIN_BYTES: int = 50

# Expected DEFAULT_EVENTS tuple length after the v9.1.3 PV-03 bump.
# Before PV-03: 7 (pre_dispatch, post_dispatch, file_write, task_stop,
# format_on_edit, pre_shell_call, envelope_write). After PV-03: 8 (above
# + pre_handoff APPENDED at position 8 per A-2.4 cache-prefix invariant).
_V9_1_3_DEFAULT_EVENTS_COUNT: int = 8


def test_v9_1_3_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.3: every NEW v9.1.3 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.3 PV-03 (the third PV of the
    v9.2.0 cycle) introduces the surfaces enumerated in the comment
    block above this test; this lint asserts each one as a cheap
    presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_3_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_3_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``auto_write_handoff``, ``PRE_HANDOFF_EVENT``
       are importable from :mod:`devolaflow.lifecycle`,
       ``auto_write_handoff`` is callable, and the event constant
       equals ``"pre_handoff"`` (the canonical name re-exported from
       :mod:`devolaflow.lifecycle.auto_write_handoff`).
    3. **DEFAULT_EVENTS** tuple length is exactly
       ``_V9_1_3_DEFAULT_EVENTS_COUNT`` (8 — the v9.1.3 PV-03 bump from
       7 → 8 with ``pre_handoff`` APPENDED at position 8 per the
       A-2.4 cache-prefix invariant) and contains
       ``PRE_HANDOFF_EVENT`` AT THE TAIL.
    4. **W-20 reuse-first** — the auto-write module's ``ENV_FLAG``
       constant equals ``"DEVOLAFLOW_AGENT_WORKSPACE"`` (REUSED from
       v9.1.1 PV-01 + v9.1.2 PV-02; no new flag) AND
       ``ENV_FLAG_TRUTHY == "1"`` (R5 strict literal-only opt-in).

    Failure modes:
      * "missing on disk" → a v9.1.3 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_3_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "DEFAULT_EVENTS length != 8" → the lifecycle event tuple was
        edited in violation of the A-2.4 append-only contract; verify
        ``pre_handoff`` is still appended at position 8.
      * "ENV_FLAG mismatch" → a NEW env flag was authored, violating
        W-20 reuse-first; either restore the REUSE or document the
        orthogonality argument per W-20 §3.
    """
    for relpath in _V9_1_3_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.3 violation: NEW v9.1.3 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_3_FILE_MIN_BYTES, (
            f"W-18 v9.1.3 violation: NEW v9.1.3 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_3_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.lifecycle import (
        DEFAULT_EVENTS,
        PRE_HANDOFF_EVENT,
        auto_write_handoff,
    )
    from devolaflow.lifecycle.auto_write_handoff import (
        ENV_FLAG,
        ENV_FLAG_TRUTHY,
    )

    assert PRE_HANDOFF_EVENT == "pre_handoff", (
        f"W-18 v9.1.3 violation: PRE_HANDOFF_EVENT exported value "
        f"{PRE_HANDOFF_EVENT!r} != 'pre_handoff' (the canonical event "
        f"name from auto_write_handoff.EVENT)"
    )
    assert callable(auto_write_handoff), (
        "W-18 v9.1.3 violation: auto_write_handoff is not callable — "
        "the export from devolaflow.lifecycle must be the hook function itself"
    )
    assert len(DEFAULT_EVENTS) == _V9_1_3_DEFAULT_EVENTS_COUNT, (
        f"W-18 v9.1.3 violation: lifecycle.DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected {_V9_1_3_DEFAULT_EVENTS_COUNT} "
        f"(v9.1.3 PV-03 bumped 7 → 8 with pre_handoff APPENDED at "
        f"position 8 per A-2.4 cache-prefix invariant). Current events: "
        f"{DEFAULT_EVENTS!r}"
    )
    assert PRE_HANDOFF_EVENT in DEFAULT_EVENTS, (
        f"W-18 v9.1.3 violation: PRE_HANDOFF_EVENT not registered in "
        f"DEFAULT_EVENTS tuple {DEFAULT_EVENTS!r} — the PV-03 append step "
        f"was incomplete"
    )
    assert DEFAULT_EVENTS[-1] == PRE_HANDOFF_EVENT, (
        f"W-18 v9.1.3 violation: DEFAULT_EVENTS[-1] is {DEFAULT_EVENTS[-1]!r}, "
        f"expected {PRE_HANDOFF_EVENT!r}; pre_handoff MUST be appended at "
        f"the tail per A-2.4 (positions 1-7 byte-stable)"
    )

    # W-20 reuse-first lint: same activation surface as v9.1.1 PV-01 +
    # v9.1.2 PV-02. Authoring a new env flag here would violate W-20.
    assert ENV_FLAG == "DEVOLAFLOW_AGENT_WORKSPACE", (
        f"W-20 violation: auto_write_handoff.ENV_FLAG is {ENV_FLAG!r}, "
        f"expected 'DEVOLAFLOW_AGENT_WORKSPACE' (REUSE per Workflow Rule "
        f"W-20 — same activation surface as v9.1.1 PV-01 SKILL.md "
        f"§'Workspace Engagement' and v9.1.2 PV-02 Architecture rule A-6)"
    )
    assert ENV_FLAG_TRUTHY == "1", (
        f"R5 strict violation: auto_write_handoff.ENV_FLAG_TRUTHY is "
        f"{ENV_FLAG_TRUTHY!r}, expected '1' (R5 strict opt-in REQUIRES "
        f"the literal '1' string — every other variant treated as OFF)"
    )


def test_v9_1_3_handoff_production_caller_exists(project_root: Path) -> None:
    """G-005 closure proof: ``HandoffStore.write_envelope`` has ≥ 2 callers.

    The headline acceptance criterion of v9.1.3 PV-03 (cycle plan
    §PV-03 AC #1): ``rg "write_envelope\\(" src/devolaflow/`` MUST
    return at least 2 hits — the definition site at
    ``src/devolaflow/agent_workspace/handoff.py:281`` AND the new
    production caller in
    ``src/devolaflow/lifecycle/auto_write_handoff.py``.

    Through v9.1.2, the audit returned exactly 1 hit (the definition
    site only) — ``HandoffStore`` and ``ChangeStore`` were both
    "registered but never engaged" surfaces, which is the smoking-gun
    diagnosis from the v9.2.0 cycle plan §"Diagnosis — capability is
    taught but never engaged". v9.1.3 PV-03 closes that gap by
    materialising the FIRST production caller. This lint pins the
    closure so a future regression that deletes the auto-write module
    fails CI immediately.

    Implementation: AST-walks every Python file under
    ``src/devolaflow/`` and counts module-level + nested attribute
    accesses of the form ``write_envelope(`` (any expression containing
    that substring). The 2-hit floor catches both the definition (a
    method ``def write_envelope(...)``) and the call site (a function
    invocation like ``store.write_envelope(envelope)``). The single
    file ``handoff.py`` carries the definition; ``auto_write_handoff.py``
    carries the call.
    """
    src_root = project_root / "src" / "devolaflow"
    assert src_root.is_dir(), f"src/devolaflow/ missing — cannot audit (looked under {src_root})"

    callers: list[tuple[str, int]] = []
    for py_file in sorted(src_root.rglob("*.py")):
        if any(part == "__pycache__" for part in py_file.parts):
            continue
        text = _read(py_file)
        for line_num, line in enumerate(text.splitlines(), start=1):
            if "write_envelope(" in line:
                callers.append((py_file.relative_to(project_root).as_posix(), line_num))

    assert len(callers) >= 2, (
        f"G-005 NOT closed: rg 'write_envelope\\(' src/devolaflow/ found "
        f"only {len(callers)} hit(s) — expected ≥ 2 (1 definition + ≥ 1 caller). "
        f"Hits: {callers!r}. The v9.1.3 PV-03 production caller must live in "
        f"src/devolaflow/lifecycle/auto_write_handoff.py."
    )
    relpaths = {relpath for relpath, _line in callers}
    assert "src/devolaflow/agent_workspace/handoff.py" in relpaths, (
        "Definition site missing: src/devolaflow/agent_workspace/handoff.py "
        "MUST contain the canonical write_envelope definition"
    )
    assert "src/devolaflow/lifecycle/auto_write_handoff.py" in relpaths, (
        f"v9.1.3 PV-03 production caller missing: "
        f"src/devolaflow/lifecycle/auto_write_handoff.py MUST contain the "
        f"FIRST production caller of HandoffStore.write_envelope (G-005 "
        f"closure). Found callers in: {sorted(relpaths)}"
    )


# ── v9.1.4 PV-04 — W-18 ghost-audit refresh for v9.1.4 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.4 PV-04
# (the fourth PV of the v9.2.0 cycle) introduces the surfaces enumerated
# in the comment block above this test; this lint asserts each one as a
# cheap presence + import-smoke check.
#
#   * src/devolaflow/memory_router/cache.py — EXTENDED with the new
#     consult_for_dispatch() pure function. The advisory companion to
#     MemoryRouter.lookup_case (which is the planner-replacement
#     fast-path); consult_for_dispatch is keyword-scored and surfaces
#     the top-3 MemoryCase hits in the dispatch payload's
#     `change_context.memory_case_hits` NEST sub-field.
#   * tests/test_memory_consult_for_dispatch.py — new test file pinning
#     the consult_for_dispatch contract (5 tests covering env-flag OFF
#     zero-IO, missing index, malformed YAML WARNING, keyword overlap
#     ranking, TTL+version-stamp filtering).
#   * tests/test_feedback_ingestion_plan_mode.py — new test file pinning
#     the plan-mode feedback ingestion contract (4 tests covering empty
#     dir, S-2 repo-relative paths, 3-feedback cap, plan-mode doc cite).
#   * benchmarks/devolaflow_context/baselines/layout_invariant_v9.2.0.yaml
#     — NEW witness baseline (byte-identical to v8.4.0); proves the
#     v9.1.4 PV-04 NEST extension preserved canonical_order length 16
#     and version 5 (the headline I-8 invariant for PV-04).
#   * schemas/lean-dispatch.yaml — EXTENDED change_context.fields with
#     3 NEW OPTIONAL sub-fields: prior_feedback_themes / memory_case_hits
#     / source_of_truth_excerpt (NEST per A-2.3 — canonical_order length
#     STAYS at 16, version STAYS at 5).

_V9_1_4_NEW_FILES: tuple[str, ...] = (
    "tests/test_memory_consult_for_dispatch.py",
    "tests/test_feedback_ingestion_plan_mode.py",
    "benchmarks/devolaflow_context/baselines/layout_invariant_v9.2.0.yaml",
)

# Minimum byte size for a v9.1.4 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_4_FILE_MIN_BYTES: int = 50

# Expected length / version of `schemas/lean-dispatch.yaml#layout_invariant`
# AFTER the v9.1.4 PV-04 NEST extension. The headline I-8 invariant for
# PV-04 — the NEST extension MUST preserve canonical_order at 16 keys and
# the schema version at 5 (positions 1-16 byte-stable; v9-ADR-002 D2
# append-only contract preserved; v8.3.0 PV-05 + v8.4.0 multi-baseline
# byte tests continue to PASS without modification).
_V9_1_4_CANONICAL_ORDER_LENGTH: int = 16
_V9_1_4_LAYOUT_VERSION: int = 5

# The 3 NEW change_context sub-fields added in v9.1.4 PV-04 per the
# A-2.3 nest-vs-append decision rule. Each is OPTIONAL (so absence is
# canonical and the v8.3.0 PV-05 + v8.4.0 + v9.2.0 baseline byte tests
# continue to PASS). The schema documents per-field caps (≤ 5 / ≤ 30 /
# ≤ 3 / ≤ 200) but those caps are NOT runtime-enforced in PV-04 — they
# are normative for L0 agents per references/plan-mode-enforcement.md
# §5.5 + the v9.2.0 PV-06 e2e test that will exercise them.
_V9_1_4_NEW_CHANGE_CONTEXT_FIELDS: tuple[str, ...] = (
    "prior_feedback_themes",
    "memory_case_hits",
    "source_of_truth_excerpt",
)


def test_v9_1_4_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.4: every NEW v9.1.4 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.4 PV-04 (the fourth PV of the
    v9.2.0 cycle) introduces the surfaces enumerated in the comment
    block above this test; this lint asserts each one as a cheap
    presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_4_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_4_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``consult_for_dispatch`` is importable from
       :mod:`devolaflow.memory_router` AND from
       :mod:`devolaflow.memory_router.cache`, and is callable.
    3. **W-20 reuse-first** — ``consult_for_dispatch`` is gated by the
       SAME env-flag the existing :class:`MemoryRouter` consults
       (``DEVOLAFLOW_MEMORY_ROUTER``); no new env-flag was introduced.
       This is the headline W-20 lint for PV-04: the v9.2.0 cycle plan
       §"Self-iteration constraint compliance matrix" pins "0 new flags
       across the entire 7-PV cycle".
    4. **change_context schema NEST extension** — the 3 NEW OPTIONAL
       sub-fields (``prior_feedback_themes`` / ``memory_case_hits`` /
       ``source_of_truth_excerpt``) are documented in
       ``schemas/lean-dispatch.yaml#lean_format_spec.change_context.fields``.
       Their presence in the schema documents the contract surfaced by
       :func:`consult_for_dispatch` (memory_case_hits) and by the
       plan-mode feedback ingestion (prior_feedback_themes).

    Failure modes:
      * "missing on disk" → a v9.1.4 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_4_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "consult_for_dispatch not callable" → the cache.py module
        broke its public surface contract.
      * "env-flag mismatch" → a NEW env-flag was authored in violation
        of W-20; either restore the REUSE or document the
        orthogonality argument per W-20 §3.
      * "missing schema sub-field" → the lean-dispatch.yaml NEST
        extension was reverted; restore the 3 sub-fields OR document
        the de-NEST decision.
    """
    for relpath in _V9_1_4_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.4 violation: NEW v9.1.4 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_4_FILE_MIN_BYTES, (
            f"W-18 v9.1.4 violation: NEW v9.1.4 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_4_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    # Import-smoke from BOTH the package facade and the owning module —
    # catches a regression where one re-export path is dropped.
    from devolaflow.memory_router import consult_for_dispatch as facade_consult
    from devolaflow.memory_router.cache import (
        consult_for_dispatch as module_consult,
    )

    assert callable(facade_consult), (
        "W-18 v9.1.4 violation: devolaflow.memory_router.consult_for_dispatch "
        "is not callable — the export from devolaflow.memory_router/__init__.py "
        "must be the function itself"
    )
    assert callable(module_consult), (
        "W-18 v9.1.4 violation: devolaflow.memory_router.cache.consult_for_dispatch "
        "is not callable — the function definition is missing or shadowed"
    )
    assert facade_consult is module_consult, (
        "W-18 v9.1.4 violation: facade vs module export of consult_for_dispatch "
        "diverge — the package __init__.py must re-export the cache.py symbol "
        "directly without wrapping"
    )

    # W-20 reuse-first lint: PV-04 MUST reuse DEVOLAFLOW_MEMORY_ROUTER (the
    # existing MemoryRouter activation surface) per the v9.2.0 cycle plan
    # §"Self-iteration constraint compliance matrix". Authoring a new env
    # flag here would violate W-20.
    from devolaflow.memory_router.cache import (
        _CONSULT_ENV_FLAG,
        _CONSULT_ENV_TRUTHY,
    )

    assert _CONSULT_ENV_FLAG == "DEVOLAFLOW_MEMORY_ROUTER", (
        f"W-20 violation: consult_for_dispatch._CONSULT_ENV_FLAG is "
        f"{_CONSULT_ENV_FLAG!r}, expected 'DEVOLAFLOW_MEMORY_ROUTER' (REUSE per "
        f"Workflow Rule W-20 — same activation surface as the existing "
        f"MemoryRouter.lookup_case fast-path; no new env-flag introduced "
        f"in the entire v9.2.0 7-PV cycle)"
    )
    assert _CONSULT_ENV_TRUTHY == "1", (
        f"R5 strict violation: consult_for_dispatch._CONSULT_ENV_TRUTHY is "
        f"{_CONSULT_ENV_TRUTHY!r}, expected '1' (R5 strict opt-in REQUIRES "
        f"the literal '1' string — every other variant treated as OFF)"
    )

    # Schema NEST extension lint — the 3 NEW change_context sub-fields
    # MUST be documented in `schemas/lean-dispatch.yaml`.
    schema_path = project_root / "schemas" / "lean-dispatch.yaml"
    assert schema_path.is_file(), f"missing schemas/lean-dispatch.yaml at {schema_path}"
    schema = _load_yaml(schema_path)
    change_context_fields = (
        schema.get("lean_format_spec", {}).get("change_context", {}).get("fields", {})
    )
    for new_field in _V9_1_4_NEW_CHANGE_CONTEXT_FIELDS:
        assert new_field in change_context_fields, (
            f"W-18 v9.1.4 violation: NEST sub-field {new_field!r} missing from "
            f"`schemas/lean-dispatch.yaml#lean_format_spec.change_context.fields`. "
            f"The v9.1.4 PV-04 NEST extension (per A-2.3 nest-vs-append rule) "
            f"requires all 3 sub-fields (prior_feedback_themes / memory_case_hits "
            f"/ source_of_truth_excerpt). Present sub-fields: "
            f"{sorted(change_context_fields)}"
        )


def test_v9_1_4_nest_preserves_canonical_order_length(project_root: Path) -> None:
    """W-18 v9.1.4: NEST extension preserved canonical_order at 16 / version 5.

    The headline I-8 invariant proof for PV-04 — the v9.1.4 PV-04 NEST
    extension (3 NEW OPTIONAL sub-fields under ``change_context``) MUST
    NOT bump the canonical_order length nor the schema version. Per
    A-2.3 nest-vs-append decision rule, NEST is byte-stable wrt the
    LLM cache prefix (the historical baselines from v7.0.0 through
    v8.4.0 continue to render byte-identically because the new
    sub-fields are OPTIONAL and absent from those baselines).

    A future PV that wants to add a TRULY orthogonal new payload
    (cannot be expressed as a sub-field of an existing block) would
    APPEND a new top-level key — that PV would update both this
    expected length AND the
    ``tests/test_layout_invariant_multi_baseline.py`` golden YAML.
    """
    schema_path = project_root / "schemas" / "lean-dispatch.yaml"
    assert schema_path.is_file(), f"missing schemas/lean-dispatch.yaml at {schema_path}"
    schema = _load_yaml(schema_path)

    layout_invariant = schema.get("layout_invariant", {})
    canonical_order = layout_invariant.get("canonical_order", [])
    layout_version = layout_invariant.get("version")

    assert isinstance(canonical_order, list), (
        f"layout_invariant.canonical_order must be a list; got {type(canonical_order).__name__}"
    )
    assert len(canonical_order) == _V9_1_4_CANONICAL_ORDER_LENGTH, (
        f"v9.1.4 PV-04 I-8 invariant violation: "
        f"`schemas/lean-dispatch.yaml#layout_invariant.canonical_order` length is "
        f"{len(canonical_order)}, expected {_V9_1_4_CANONICAL_ORDER_LENGTH} "
        f"(NEST extension MUST preserve canonical_order length per A-2.3 +  "
        f"v9-ADR-002 D2). Current order: {canonical_order!r}"
    )
    assert layout_version == _V9_1_4_LAYOUT_VERSION, (
        f"v9.1.4 PV-04 I-8 invariant violation: "
        f"`schemas/lean-dispatch.yaml#layout_invariant.version` is "
        f"{layout_version!r}, expected {_V9_1_4_LAYOUT_VERSION} (NEST "
        f"extension MUST NOT bump schema version per A-2.3 + v9-ADR-002 D2)"
    )

    # The NEW v9.2.0 baseline witness MUST exist + be byte-identical to
    # v8.4.0. This couples the I-8 invariant proof to the on-disk
    # fixture so a renamed/moved baseline file fails CI immediately.
    baselines_dir = project_root / "benchmarks" / "devolaflow_context" / "baselines"
    v9_2_0_path = baselines_dir / "layout_invariant_v9.2.0.yaml"
    v8_4_0_path = baselines_dir / "layout_invariant_v8.4.0.yaml"
    assert v9_2_0_path.is_file(), (
        f"v9.1.4 PV-04 missing baseline witness at {v9_2_0_path}. "
        f"NEST extension proof requires this file to be byte-identical "
        f"to {v8_4_0_path}."
    )
    assert v8_4_0_path.is_file(), f"v8.4.0 baseline missing at {v8_4_0_path}"
    assert v9_2_0_path.read_text() == v8_4_0_path.read_text(), (
        "v9.1.4 PV-04 I-8 invariant violation: the v9.2.0 baseline witness "
        "diverged from the v8.4.0 baseline. The NEST extension was supposed "
        "to be byte-identical (the new sub-fields are OPTIONAL — their "
        "absence is canonical). See "
        "tests/test_layout_invariant_multi_baseline.py::"
        "test_v9_2_0_baseline_byte_identical_to_v8_4_0 for the wider context."
    )


# ---------------------------------------------------------------------------
# v9.1.5 PV-05 — spec_bootstrap + agents_md_slice default-ON ghost-audit
# ---------------------------------------------------------------------------

# v9.1.5 PV-05 introduces TWO operator-visible deliverables that the W-18
# precondition pins BEFORE the CHANGELOG entry mentioning them:
#
# 1. NEW src/devolaflow/agent_workspace/spec_bootstrap.py with
#    seed_initial_spec() + SpecBootstrapError — closes M-004 deferred
#    from v9.0.0 retrospective §3.3 (source-of-truth first-time seed).
# 2. context_profiles.yaml#meta.agents_md_slice.enabled flips false → true
#    (operator-visible default-ON; opt-out via DEVOLAFLOW_AGENTS_MD_SLICE=0
#    per W-20 reuse — telegraphed v9.0.0 PV-07 ADR-007 D3, runtime read
#    landed v9.1.5 PV-05).
_V9_1_5_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/agent_workspace/spec_bootstrap.py",
    "tests/test_spec_bootstrap.py",
)

# Minimum byte size for a v9.1.5 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_5_FILE_MIN_BYTES: int = 50


def test_v9_1_5_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.5: every NEW v9.1.5 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.5 PV-05 (the fifth PV of the
    v9.2.0 cycle, the most behaviour-flipping one) introduces:

    1. ``src/devolaflow/agent_workspace/spec_bootstrap.py`` — closes
       M-004 deferred from v9.0.0 retrospective §3.3 (source-of-truth
       first-time seed via :func:`seed_initial_spec`).
    2. ``tests/test_spec_bootstrap.py`` — 6 NEW tests pinning the
       seed contract.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_5_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_5_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — :func:`seed_initial_spec` and
       :exc:`SpecBootstrapError` are importable from BOTH the package
       facade :mod:`devolaflow.agent_workspace` AND the owning module
       :mod:`devolaflow.agent_workspace.spec_bootstrap`; ``facade is
       module`` (catches the regression where one re-export path is
       dropped) and the function is callable.
    3. **W-20 reuse-first** — :data:`_AGENTS_MD_SLICE_ENV_FLAG` equals
       ``"DEVOLAFLOW_AGENTS_MD_SLICE"`` (NO new env-flag introduced in
       PV-05; the flag was telegraphed in v9.0.0 PV-07 ADR-007 D3).
    4. **A-4 invariant signature** — :func:`seed_initial_spec` accepts
       ``force=False`` as the canonical default (the A-4 first-time
       seed gate); operator overrides via ``force=True`` only.

    Failure modes:
      * "missing on disk" → a v9.1.5 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_5_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "seed_initial_spec not callable" → the spec_bootstrap module
        broke its public surface contract.
      * "env-flag mismatch" → a NEW env-flag was authored in violation
        of W-20; either restore the REUSE or document the
        orthogonality argument per W-20 §3.
      * "force kwarg default mismatch" → the A-4 first-time-seed gate
        was relaxed; restore ``force=False`` or document the override
        with an ADR.
    """
    import inspect

    for relpath in _V9_1_5_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.5 violation: NEW v9.1.5 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_5_FILE_MIN_BYTES, (
            f"W-18 v9.1.5 violation: NEW v9.1.5 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_5_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    # Import-smoke from BOTH the package facade and the owning module —
    # catches a regression where one re-export path is dropped. The
    # `as facade_*` / `as module_*` rebinds intentionally use lowercase
    # because they are not used as types — they are used as identity
    # comparison handles for the `facade is module` invariant. ruff N813
    # is suppressed at the import-block level.
    from devolaflow.agent_workspace import (  # noqa: N813
        SpecBootstrapError as facade_error,
    )
    from devolaflow.agent_workspace import (
        seed_initial_spec as facade_seed,
    )
    from devolaflow.agent_workspace.spec_bootstrap import (  # noqa: N813
        SpecBootstrapError as module_error,
    )
    from devolaflow.agent_workspace.spec_bootstrap import (
        seed_initial_spec as module_seed,
    )

    assert callable(facade_seed), (
        "W-18 v9.1.5 violation: devolaflow.agent_workspace.seed_initial_spec "
        "is not callable — the export from devolaflow.agent_workspace/__init__.py "
        "must be the function itself"
    )
    assert callable(module_seed), (
        "W-18 v9.1.5 violation: devolaflow.agent_workspace.spec_bootstrap."
        "seed_initial_spec is not callable — the function definition is "
        "missing or shadowed"
    )
    assert facade_seed is module_seed, (
        "W-18 v9.1.5 violation: facade vs module export of seed_initial_spec "
        "diverge — the package __init__.py must re-export the spec_bootstrap.py "
        "symbol directly without wrapping"
    )
    assert facade_error is module_error, (
        "W-18 v9.1.5 violation: facade vs module export of SpecBootstrapError "
        "diverge — the package __init__.py must re-export the spec_bootstrap.py "
        "exception directly without aliasing"
    )
    assert issubclass(facade_error, RuntimeError), (
        "W-18 v9.1.5 violation: SpecBootstrapError must subclass RuntimeError "
        "(per S-5 explicit error states; allows callers to catch RuntimeError "
        "without importing the agent_workspace package)"
    )

    # A-4 invariant signature lint — `force` defaults to False so the
    # first-time-seed gate is the canonical entry path.
    sig = inspect.signature(module_seed)
    force_param = sig.parameters.get("force")
    assert force_param is not None, (
        "W-18 v9.1.5 violation: seed_initial_spec must accept a `force` kwarg "
        "(the A-4 first-time-seed override hatch documented in the cycle plan §PV-05)"
    )
    assert force_param.default is False, (
        f"W-18 v9.1.5 violation: seed_initial_spec(force=...) default is "
        f"{force_param.default!r}, expected False (A-4 first-time-seed gate "
        f"defaults to refuse-overwrite — operators opt into wholesale "
        f"replacement explicitly via force=True)"
    )

    # W-20 reuse-first lint — PV-05 MUST reuse DEVOLAFLOW_AGENTS_MD_SLICE
    # (the v9.0.0 PV-07 ADR-007 D3 telegraphed flag) per the v9.2.0 cycle
    # plan §"Self-iteration constraint compliance matrix" "0 new flags
    # across the entire 7-PV cycle".
    from devolaflow.task_adaptive_selector import (
        _AGENTS_MD_SLICE_ENV_FLAG,
        _agents_md_slice_env_override,
    )

    assert _AGENTS_MD_SLICE_ENV_FLAG == "DEVOLAFLOW_AGENTS_MD_SLICE", (
        f"W-20 violation: _AGENTS_MD_SLICE_ENV_FLAG is "
        f"{_AGENTS_MD_SLICE_ENV_FLAG!r}, expected 'DEVOLAFLOW_AGENTS_MD_SLICE' "
        f"(REUSE per Workflow Rule W-20 — the flag was telegraphed in v9.0.0 "
        f"PV-07 ADR-007 D3; v9.1.5 PV-05 is the runtime-wiring landing PV; "
        f"NO new env-flag introduced in the entire v9.2.0 7-PV cycle)"
    )
    assert _agents_md_slice_env_override({"DEVOLAFLOW_AGENTS_MD_SLICE": "0"}) is False, (
        "R5 strict violation: env-flag value '0' must force opt-out (return False); "
        "this is the headline v9.1.5 PV-05 escape hatch for the default-ON flip"
    )
    assert _agents_md_slice_env_override({"DEVOLAFLOW_AGENTS_MD_SLICE": "1"}) is True, (
        "R5 strict violation: env-flag value '1' must force opt-in (return True)"
    )


def test_v9_1_5_agents_md_slice_default_on(project_root: Path) -> None:
    """W-18 v9.1.5: context_profiles.yaml#agents_md_slice.enabled is True.

    Pins the headline operator-visible behaviour change of v9.1.5 PV-05.
    Pre-v9.1.5 the canonical YAML default was ``enabled: false`` (the
    v9.0.0 MAJOR-cycle telegraphed flip with a 2-cycle lead time per
    W-21 governance precedent applied to operator-visible defaults).
    v9.1.5 PV-05 flips the canonical default to ``true``, so dispatchers
    on the unmodified YAML receive sliced AGENTS.md content automatically.

    This lint catches a regression where the canonical YAML is
    accidentally reverted to ``enabled: false`` (would silently revert
    the operator-visible behaviour change without bumping the
    CHANGELOG). It is paired with
    ``tests/test_pv07_agents_md_slice.py::test_agents_md_slice_default_on_in_v9_1_5``
    which loads the YAML directly + with
    ``test_agents_md_slice_env_flag_0_opts_out`` which proves the R5
    strict opt-out is byte-stable.
    """
    import yaml as yaml_module

    profiles_path = project_root / "workflow-system" / "agent" / "context_profiles.yaml"
    assert profiles_path.is_file(), (
        f"W-18 v9.1.5 violation: context_profiles.yaml missing at {profiles_path}"
    )
    config = yaml_module.safe_load(profiles_path.read_text(encoding="utf-8"))
    slice_cfg = config.get("meta", {}).get("agents_md_slice", {})

    assert slice_cfg.get("enabled") is True, (
        f"W-18 v9.1.5 violation: context_profiles.yaml#meta.agents_md_slice."
        f"enabled is {slice_cfg.get('enabled')!r}, expected True (v9.1.5 PV-05 "
        f"default-ON flip — the headline operator-visible behaviour change). "
        f"If the flip was rolled back, also remove the [9.1.5] CHANGELOG "
        f"entry citing the flip."
    )
    # The fallback strategy must remain "full" so unmatched task types
    # still see byte-identical AGENTS.md (W-20 R5 strict — the slice is
    # additive opt-in for matched profiles; unmatched falls through).
    assert slice_cfg.get("fallback") == "full", (
        f"W-18 v9.1.5 violation: agents_md_slice.fallback must be 'full' "
        f"(unmatched task types fall through to byte-identical AGENTS.md per "
        f"R5 strict); got {slice_cfg.get('fallback')!r}"
    )
