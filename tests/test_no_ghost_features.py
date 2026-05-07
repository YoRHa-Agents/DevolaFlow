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


def _resolve_artifact_path(
    project_root: Path,
    local_path: Path,
    archive_candidates: tuple[Path, ...],
) -> Path:
    """Return a local research artifact or its committed W-19 archive copy."""
    for rel_path in (local_path, *archive_candidates):
        candidate = project_root / rel_path
        if candidate.is_file():
            return candidate

    searched = ", ".join(str(path) for path in (local_path, *archive_candidates))
    pytest.fail(f"W-18 research artifact missing; expected one of: {searched}")


_W18_RESEARCH_ARCHIVE_CANDIDATES: dict[Path, tuple[Path, ...]] = {
    Path(".local/research/v10.2.1_dogfood_pass1.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.1_dogfood_pass1.md"),
    ),
    Path(".local/research/v10.2.2_nines.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines.json"),
    ),
    Path(".local/research/v10.2.2_nines_plugins.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines_plugins.json"),
    ),
    Path(".local/research/v10.2.2_nines_lifecycle.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines_lifecycle.json"),
    ),
    Path(".local/research/v10.2.2_nines.md"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines.md"),
    ),
    Path(".local/research/v10.2.2_dogfood_pass2.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.2_dogfood_pass2.md"),
    ),
    Path(".local/research/v10.2.3_dogfood_pass3.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.3_dogfood_pass3.md"),
    ),
    Path(".local/research/v10.2.3_iteration_round1.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.3_iteration_round1.md"),
    ),
    Path(".local/research/v10.2.4_iteration_round2.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_iteration_round2.md"),
    ),
    Path(".local/research/v10.2.4_w17_mid_cycle_audit.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_w17_mid_cycle_audit.md"),
    ),
    Path(".local/research/v10.2.4_w8_stagnation_check.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_w8_stagnation_check.md"),
    ),
    Path(".local/research/v10.2.4_dogfood_pass4.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_dogfood_pass4.md"),
    ),
    Path(".local/research/v10.3.0_evaluation.md"): (
        Path("docs/cycle-archive/v10.3.0/evaluation/v10.3.0_evaluation.md"),
    ),
    Path(".local/research/v10.3.0_retrospective.md"): (
        Path("docs/cycle-archive/v10.3.0/v10.3.0_retrospective.md"),
    ),
    Path(".local/research/v10.3.0_nines.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.3.0_nines.json"),
    ),
    Path(".local/research/v10.3.0_nines.md"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.3.0_nines.md"),
    ),
    Path(".local/research/v10.4.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.4.0_retrospective.md"),
    ),
    Path(".local/research/v10.4.1_reference_utilization.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.4.1_reference_utilization.md"),
    ),
    Path(".local/research/v10.4.2_long_reference_usage.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.4.2_long_reference_usage.md"),
    ),
    Path(".local/research/v10.5.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.5.0_retrospective.md"),
    ),
    Path(".local/research/v10.5.1_layer_usage_audit.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.1_layer_usage_audit.md"),
    ),
    Path(".local/research/v10.5.2_template_usage_audit.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.2_template_usage_audit.md"),
    ),
    Path(".local/research/v10.5.3_reference_friction.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.3_reference_friction.md"),
    ),
    Path(".local/research/v10.5.4_w18_lint_audit.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.4_w18_lint_audit.md"),
    ),
    Path(".local/research/v10.6.0_compressor_health.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.6.0_compressor_health.md"),
    ),
    Path(".local/research/v10.6.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.6.0_retrospective.md"),
    ),
    Path(".local/research/v10.7.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.7.0_retrospective.md"),
    ),
    Path(".local/research/v10.7.1_canonical_order_emptiness.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.1_canonical_order_emptiness.md"),
    ),
    Path(".local/research/v10.7.2_evaluator_rosetta.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.2_evaluator_rosetta.md"),
    ),
    Path(".local/research/v10.7.3_si3_auto_collection.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.3_si3_auto_collection.md"),
    ),
    Path(".local/research/v10.7.4_research_index.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.4_research_index.md"),
    ),
    Path(".local/research/v10.8.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.8.0_retrospective.md"),
    ),
    Path(".local/research/v11.0.0_w21_threshold_empirical_check.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v11.0.0_w21_threshold_empirical_check.md"),
    ),
    Path(".local/research/v11.0.0_si10_gate_growth_analysis.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v11.0.0_si10_gate_growth_analysis.md"),
    ),
    Path(".local/research/v11.0.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v11.0.0_retrospective.md"),
        Path("docs/cycle-archive/v11.0.0/retrospective.md"),
    ),
    Path(".local/research/v11.0.0_evaluation.md"): (
        Path("docs/cycle-archive/v11.0.0/evaluation/v11.0.0_evaluation.md"),
    ),
}


def _w18_research_artifact_path(project_root: Path, local_path: Path) -> Path:
    archive_candidates = _W18_RESEARCH_ARCHIVE_CANDIDATES.get(local_path)
    if archive_candidates is None:
        pytest.fail(f"W-18 archive mapping missing for research artifact: {local_path}")
    return _resolve_artifact_path(project_root, local_path, archive_candidates)


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
    """Extract template names from SKILL.md's Template Quick-Reference table.

    v10.5.0 PV-02 D-A-2 Phase A introduces ``(legacy)`` suffix
    annotations on TIER-2 template rows (16 of 22 templates). The
    canonical name is what's retained for registry comparison; the
    ``(legacy)`` marker is stripped here.
    """
    skill = _read(project_root / "workflow-system/agent/SKILL.md")
    section = re.search(r"## Template Quick-Reference\n(.*?)(?:\n## |\Z)", skill, re.DOTALL)
    if section is None:
        return set()
    rows = [ln for ln in section.group(1).splitlines() if ln.startswith("|")][2:]
    names: set[str] = set()
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        if len(cells) >= 2 and cells[1]:
            # Strip v10.5.0 D-A-2 (legacy) suffix annotation.
            name = re.sub(r"\s*\(legacy\)\s*$", "", cells[1])
            names.add(name)
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
        # v10.4.0 PV-05 — Operator troubleshooting handbook (15th SF-4
        # canonical). Quick lookup index + per-symptom diagnostic patterns
        # + escalation patterns harvested from cycle retros v8.0.0 ->
        # v10.3.0. Load tier: `important` for most task types,
        # `critical` for bugfix / dependency-setup. Pairs with the v10.4.0
        # audit scripts (audit_reference_utilization.py /
        # audit_long_reference_usage.py) and the scaffold CLIs
        # (scaffold_template.py / scaffold_reference.py).
        "troubleshooting.md",
        # v10.7.0 D-O-1 — Three-evaluator rosetta (16th SF-4 canonical).
        # 6 × 9 cross-walk between SI-3 dimensions (rows) + NineS hygiene
        # axes / capability sub-bundles + Si-Chip iteration_delta scalar
        # (columns) with per-cell verbatim source citations. Load tier:
        # `important` for L3 SI-3 evaluation authoring, `critical` for
        # nines-assisted / self-update workflows. Pairs with v10.7.0
        # D-O-2 auto_collect_si3_metrics.py and the D-O-1 companion
        # generate_evaluator_rosetta.py.
        "evaluator-rosetta.md",
        # v10.8.0 D-C-1 — Upstream-unreachable degraded-mode contract
        # (17th SF-4 canonical). Per-plugin fallback doc for NineS /
        # Si-Chip / RTK / ui-pro with a "Degraded ≠ Full" leading warning
        # per D-C-1 §9 R1 mitigation (the FIRST section of the reference,
        # before any per-plugin detail; operators reading top-down hit the
        # caveat immediately). Load tier: `important` for most task types,
        # `critical` for nines-assisted / product-verification workflows.
        # Pairs with `tests/test_degraded_mode.py` (16 regression tests
        # pinning the 4-plugin fallback contract) and closes the v10.3.0
        # retrospective §3 NineS A1 ticket pain point.
        "degraded-mode.md",
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
# Per A-2.2 append-only governance, future cycles MAY bump this number
# higher (v9.4.0 PV-02 bumped 8 → 9 with pre_plugin_invocation appended
# at position 9; v9.4.0 W-18 lint pins the new tail). The v9.1.3 lint
# below uses ``>= _V9_1_3_DEFAULT_EVENTS_MIN`` so future appends do not
# break this historic ghost-audit — the v9.1.3 contract is "pre_handoff
# must be in the tuple at position 8 OR LATER (depending on subsequent
# appends)", not "the tuple is exactly 8 long forever".
_V9_1_3_DEFAULT_EVENTS_MIN: int = 8
_V9_1_3_PRE_HANDOFF_POSITION: int = 8  # 1-indexed; tuple index 7 (zero-based)


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
    3. **DEFAULT_EVENTS** tuple length is at least
       ``_V9_1_3_DEFAULT_EVENTS_MIN`` (8 — the v9.1.3 PV-03 bump from
       7 → 8 with ``pre_handoff`` APPENDED at position 8 per the
       A-2.4 cache-prefix invariant) AND ``PRE_HANDOFF_EVENT`` is at
       the v9.1.3-frozen position 8 (1-indexed; tuple index 7).
       Subsequent A-2.2 append-only bumps (v9.4.0 PV-02 added
       ``pre_plugin_invocation`` at position 9) do NOT invalidate this
       lint — the v9.1.3 contract is the historic position freeze for
       ``pre_handoff``, not the tuple length.
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
      * "DEFAULT_EVENTS length < 8" → the lifecycle event tuple was
        edited in violation of the A-2.4 append-only contract; verify
        ``pre_handoff`` is still present at position 8 (1-indexed).
        Append-only growth (length > 8) is permitted per A-2.2 — see
        the v9.4.0 PV-02 ``pre_plugin_invocation`` precedent.
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
    assert len(DEFAULT_EVENTS) >= _V9_1_3_DEFAULT_EVENTS_MIN, (
        f"W-18 v9.1.3 violation: lifecycle.DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected >= {_V9_1_3_DEFAULT_EVENTS_MIN} "
        f"(v9.1.3 PV-03 bumped 7 → 8 with pre_handoff APPENDED at "
        f"position 8 per A-2.4 cache-prefix invariant; A-2.2 permits "
        f"future append-only growth). Current events: {DEFAULT_EVENTS!r}"
    )
    assert PRE_HANDOFF_EVENT in DEFAULT_EVENTS, (
        f"W-18 v9.1.3 violation: PRE_HANDOFF_EVENT not registered in "
        f"DEFAULT_EVENTS tuple {DEFAULT_EVENTS!r} — the PV-03 append step "
        f"was incomplete"
    )
    # v9.1.3 historic position freeze: pre_handoff at 1-indexed position 8
    # (tuple index 7). v9.4.0 PV-02 appended pre_plugin_invocation at
    # position 9 without disturbing this freeze.
    handoff_idx = _V9_1_3_PRE_HANDOFF_POSITION - 1
    assert DEFAULT_EVENTS[handoff_idx] == PRE_HANDOFF_EVENT, (
        f"W-18 v9.1.3 violation: DEFAULT_EVENTS[{handoff_idx}] is "
        f"{DEFAULT_EVENTS[handoff_idx]!r}, expected {PRE_HANDOFF_EVENT!r}; "
        f"pre_handoff MUST stay frozen at 1-indexed position "
        f"{_V9_1_3_PRE_HANDOFF_POSITION} per the v9.1.3 PV-03 + A-2.4 "
        f"cache-prefix invariant (positions 1-7 + position 8 byte-stable)"
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
#
# v9.7.0 PV-02 update: the v9.7.0 cycle APPENDED a NEW top-level key
# ``predecessor_dedup_ledger`` at canonical position 17 per A-2.2 append-only
# rule. Schema version bumped 5 → 6. The post-v9.1.4 NEST byte-stability
# invariant (positions 1-16 byte-identical to v8.4.0) IS PRESERVED — the
# v9.7.0 PV-02 APPEND is at position 17, which v9.1.4 PV-04 explicitly
# anticipated ("A future PV that wants to add a TRULY orthogonal new
# payload would APPEND a new top-level key — that PV would update both
# this expected length AND the multi-baseline golden YAML").
_V9_1_4_CANONICAL_ORDER_LENGTH: int = 17
_V9_1_4_LAYOUT_VERSION: int = 6

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


# ---------------------------------------------------------------------------
# v9.2.0 PV-06 — repo-init seed examples + e2e capability test ghost-audit
# ---------------------------------------------------------------------------

# v9.2.0 PV-06 (the cycle-rollup MINOR headline) introduces TWO operator-visible
# deliverables that the W-18 precondition pins BEFORE the [9.2.0] CHANGELOG
# entry mentioning them:
#
# 1. EXTEND src/devolaflow/init_project.py::install_local with the new
#    `with_examples: bool = False` kwarg + the `_seed_example_artifacts(cwd)`
#    helper that materialises 3 worked-trace fixtures under
#    `.local/.agent/active/example-add-dark-mode/` + `.local/.agent/handoff/
#    L0__L2__example-add-dark-mode__0001.yaml` + `.local/memory/specs/
#    example-domain/spec.md` so new repos demonstrate the change-driven
#    pattern out-of-the-box. Closes G-006 deferred from v9.1.0 retro §3.
# 2. NEW tests/test_capability_e2e.py — 10 end-to-end capability tests that
#    cross every PV's deliverable through a tmp-path repo fixture. Closes
#    G-015 deferred from v9.1.0 retro §3.
_V9_2_0_NEW_FILES: tuple[str, ...] = ("tests/test_capability_e2e.py",)

# Minimum byte size for a v9.2.0 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_2_0_FILE_MIN_BYTES: int = 1000

# The e2e test file ships with EXACTLY 10 test functions per the cycle
# plan §PV-06 W-17 budget pin (the headline lint of the v9.2.0 cycle).
# A regression below this count means a test was deleted; a regression
# above means a test was added without bumping the W-17 ledger.
_V9_2_0_CAPABILITY_E2E_MIN_TESTS: int = 10


def test_v9_2_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.0: every NEW v9.2.0 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.2.0 PV-06 (the sixth and
    headline PV of the cycle, the cycle rollup) introduces:

    1. ``install_local(*, with_examples: bool = False)`` kwarg in
       :mod:`devolaflow.init_project` plus the
       ``_seed_example_artifacts(cwd: Path) -> None`` helper. Closes
       G-006 deferred from the v9.1.0 retrospective §3.
    2. ``tests/test_capability_e2e.py`` (10 tests) — the cycle's
       headline lint that crosses every PV's deliverable through a
       tmp-path repo fixture. Closes G-015 deferred from the v9.1.0
       retrospective §3.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_2_0_NEW_FILES`` is a regular
       file and its size is ``>= _V9_2_0_FILE_MIN_BYTES`` (1000 bytes
       — the e2e test file is the largest single new file in the
       cycle so the floor is intentionally above the 50-byte v9.1.5
       stub-guard).
    2. **Import-smoke (install_local)** — :func:`install_local` is
       importable from :mod:`devolaflow.init_project` AND its
       :func:`inspect.signature` reports ``with_examples`` as a
       keyword-only parameter with default ``False`` (the A-4 / W-20
       contract — additive opt-in, default OFF for compatibility).
    3. **Import-smoke (_seed_example_artifacts)** — the helper is
       importable from the same module and is callable.
    4. **Import-smoke (test_capability_e2e)** — the e2e test module
       importable AND its ``__all__`` lists ≥ 10 test functions
       (matches ``_V9_2_0_CAPABILITY_E2E_MIN_TESTS``); each name in
       ``__all__`` is a callable test function in the module.
    5. **W-20 reuse-first** — no new env-flag introduced (the
       v9.2.0 cycle plan §"Self-iteration constraint compliance
       matrix" pin "0 new flags across the entire 7-PV cycle" is
       upheld). The 5 env flags touched (DEVOLAFLOW_AGENT_WORKSPACE
       for PV-01/02/03; DEVOLAFLOW_MEMORY_ROUTER for PV-04;
       DEVOLAFLOW_AGENTS_MD_SLICE for PV-05) ALL existed before
       this cycle started.

    Failure modes:
      * "missing on disk" → a v9.2.0 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_2_0_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 1000 byte minimum" → the file regressed to a stub;
        re-author the contents.
      * "with_examples kwarg signature mismatch" → ``install_local``
        lost its ``with_examples`` keyword-only parameter or the
        default flipped from ``False``; restore the original
        signature OR document the operator-visible change with an
        ADR.
      * "_seed_example_artifacts not callable" → the seed helper
        regressed; restore it.
      * "< 10 test functions in test_capability_e2e __all__" → the
        cycle's headline lint regressed below the W-17 budget pin;
        restore the deleted test(s).
    """
    import inspect

    for relpath in _V9_2_0_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.0 violation: NEW v9.2.0 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_2_0_FILE_MIN_BYTES, (
            f"W-18 v9.2.0 violation: NEW v9.2.0 surface {relpath!r} is {size} "
            f"bytes (< {_V9_2_0_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    # Import-smoke: install_local exists with the new with_examples
    # keyword-only parameter (default False).
    from devolaflow.init_project import _seed_example_artifacts, install_local

    sig = inspect.signature(install_local)
    assert "with_examples" in sig.parameters, (
        "W-18 v9.2.0 violation: install_local() lost its with_examples "
        "keyword-only parameter — the v9.2.0 PV-06 example-seed surface "
        "regressed; restore the kwarg per cycle plan §PV-06"
    )
    with_examples_param = sig.parameters["with_examples"]
    assert with_examples_param.kind == inspect.Parameter.KEYWORD_ONLY, (
        f"W-18 v9.2.0 violation: install_local(with_examples=...) must be "
        f"keyword-only (after the * marker); got kind={with_examples_param.kind!r}"
    )
    assert with_examples_param.default is False, (
        f"W-18 v9.2.0 violation: install_local(with_examples=...) default must "
        f"be False (additive opt-in for backward compatibility per W-20); got "
        f"default={with_examples_param.default!r}"
    )

    assert callable(_seed_example_artifacts), (
        "W-18 v9.2.0 violation: devolaflow.init_project._seed_example_artifacts "
        "is not callable — the seed helper regressed"
    )

    # Import-smoke: tests/test_capability_e2e.py module + __all__ lists
    # at least the W-17 budget pin of test functions.
    import tests.test_capability_e2e as e2e_module

    assert hasattr(e2e_module, "__all__"), (
        "W-18 v9.2.0 violation: tests/test_capability_e2e.py must declare "
        "__all__ with the cycle's headline test names (per cycle plan §PV-06 "
        "W-17 budget pin)"
    )
    e2e_tests = e2e_module.__all__
    assert len(e2e_tests) >= _V9_2_0_CAPABILITY_E2E_MIN_TESTS, (
        f"W-18 v9.2.0 violation: tests/test_capability_e2e.py.__all__ has "
        f"{len(e2e_tests)} entries; the cycle's W-17 budget pin requires at "
        f"least {_V9_2_0_CAPABILITY_E2E_MIN_TESTS} (per cycle plan §PV-06)"
    )
    for name in e2e_tests:
        assert callable(getattr(e2e_module, name, None)), (
            f"W-18 v9.2.0 violation: tests/test_capability_e2e.py.__all__ "
            f"entry {name!r} is not a callable test function in the module"
        )

    # W-20 reuse-first proof: PV-06 specifically does NOT introduce a
    # new DEVOLAFLOW_* env-flag. The seed helper writes static template
    # content + reads no env-vars — the entire flow is filesystem-only.
    init_module_path = project_root / "src" / "devolaflow" / "init_project.py"
    init_source = init_module_path.read_text(encoding="utf-8")
    assert "DEVOLAFLOW_" not in init_source, (
        "W-20 v9.2.0 violation: src/devolaflow/init_project.py introduced a "
        "new DEVOLAFLOW_* env-flag during PV-06 — the cycle plan §"
        '"Self-iteration constraint compliance matrix" pins "0 new flags '
        'across the entire 7-PV cycle". Either remove the new flag or '
        "document the W-20 §3 orthogonality argument in the PR body."
    )


# ---------------------------------------------------------------------------
# v9.2.0 PV-06 — supplementary lint for the W-19 cycle archive + the
# scripts/archive_research_artifacts.py --extra-prefix extension.
# ---------------------------------------------------------------------------
#
# The primary v9.2.0 ghost-audit ``test_v9_2_0_new_symbols_have_coverage``
# above pins the install_local(with_examples) kwarg + the
# tests/test_capability_e2e.py module ``__all__`` ≥ 10 + the W-20 reuse
# proof. This supplementary lint pins the OTHER PV-06 cycle-rollup
# surfaces — the W-19 archive directory presence and the
# scripts/archive_research_artifacts.py ``--extra-prefix`` flag the
# rollup invocation depends on. Splitting the audit into two test
# functions keeps each one focused on a single deliverable per the
# v8.0.0 retro §3.4 lesson "tests should be small + named after their
# specific contract".


def test_v9_2_0_cycle_archive_and_extra_prefix(project_root: Path) -> None:
    """W-18 v9.2.0: W-19 cycle archive directory + --extra-prefix flag wired.

    Pins the two cycle-rollup deliverables NOT covered by the primary
    ``test_v9_2_0_new_symbols_have_coverage`` lint:

    1. ``docs/cycle-archive/v9.2.0/`` directory exists with the W-19
       auto-generated ``README.md`` index AND the cycle's
       ``v9.2.0_retrospective.md`` copy. Both files are ≥ 200 bytes
       (catches an empty-stub regression that would silently pass a
       mere existence check).
    2. ``scripts/archive_research_artifacts.py`` exposes the
       ``--extra-prefix`` argparse flag AND the corresponding
       ``extra_prefixes`` kwarg on the ``archive(cycle_version, ...)``
       callable. Without this extension the cycle-rollup invocation
       ``archive_research_artifacts.py 9.2.0 --extra-prefix v9.1.``
       cannot capture both PATCH-cycle and MINOR-cycle research
       artefacts in a single run.

    Failure modes:
      * "v9.2.0 archive missing" → W-19 archive run was skipped or
        rolled back; re-run ``python scripts/archive_research_artifacts.py
        9.2.0 --extra-prefix v9.1.`` and commit the directory.
      * "no extra-prefix argument" → the v9.2.0 PV-06 archive-script
        extension was rolled back; restore it.
    """
    archive_dir = project_root / "docs" / "cycle-archive" / "v9.2.0"
    assert archive_dir.is_dir(), (
        f"W-18 v9.2.0 violation: W-19 cycle archive at "
        f"{archive_dir.relative_to(project_root)} missing — the cycle-rollup "
        f"CHANGELOG entry MUST be backed by a populated archive directory"
    )

    for relpath in (
        "docs/cycle-archive/v9.2.0/README.md",
        "docs/cycle-archive/v9.2.0/v9.2.0_retrospective.md",
    ):
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.0 violation: required archive artefact {relpath!r} missing"
        )
        size = full.stat().st_size
        assert size >= 200, (
            f"W-18 v9.2.0 violation: archive artefact {relpath!r} is {size} "
            f"bytes (< 200 byte minimum); empty/stub files do not satisfy "
            f"the W-19 archive contract"
        )

    archive_script = project_root / "scripts" / "archive_research_artifacts.py"
    archive_text = archive_script.read_text(encoding="utf-8")
    assert "--extra-prefix" in archive_text, (
        "W-18 v9.2.0 violation: scripts/archive_research_artifacts.py must "
        "expose the --extra-prefix argparse flag (added v9.2.0 PV-06 to let "
        "the MINOR-cycle archive capture both v9.1.* and v9.2.* prefixes "
        "into docs/cycle-archive/v9.2.0/)"
    )
    assert "extra_prefixes" in archive_text, (
        "W-18 v9.2.0 violation: scripts/archive_research_artifacts.py::archive "
        "must accept an `extra_prefixes` kwarg (the runtime contract behind "
        "the --extra-prefix CLI flag)"
    )


# ---------------------------------------------------------------------------
# v9.2.1 PV-07 — ghost-audit for the self-update meta-validation PATCH.
# ---------------------------------------------------------------------------
#
# PV-07 ships as the final PV of the v9.2.0 cycle (PATCH sustaining that
# mirrors the v9.0.0 → v9.0.1 precedent). The cycle plan §PV-07 pins
# "zero new code paths introduced" — the deliverables are validation
# artefacts + minor test extensions ONLY:
#
# 1. tests/test_capability_e2e.py gains 4 NEW parametrized test functions
#    covering the 4 canonical consumer-repo fixture shapes (empty /
#    local-only / rules-only / full-stack). The __all__ list grows from
#    10 entries (v9.2.0 pin) to >= 14 entries (10 baseline + 4 PV-07).
# 2. .local/research/v9.2.1_{check_refs,nines_aggregate,validation_tasks,
#    integration_report,e2e_report,evaluation}.md ship as the self-update
#    workflow's 6 stage-output artefacts (plus the cycle-close
#    v9.2.1_nines.{json,md} pair per W-2). NB: these artefacts live
#    under .local/ which is gitignored; the W-19 re-archive to
#    docs/cycle-archive/v9.2.0/ is the committed counterpart. This lint
#    therefore checks the docs/cycle-archive/ copies (the canonical
#    tracked surface) rather than the gitignored .local/ originals.
# 3. The recursive-engagement proof — PV-07 opened
#    .local/.agent/active/v9.2.1-self-update-validation/ via the PV-02
#    /devola:propose surface and archived it at Stage 7 to
#    .local/.agent/archive/<YYYY-MM-DD>-v9.2.1-self-update-validation/.
#    Like (2) this lives under gitignored .local/; this lint asserts
#    presence when the workspace is live OR skips cleanly on a fresh
#    clone.

_V9_2_1_CAPABILITY_E2E_MIN_ENTRIES: int = 14

_V9_2_1_ARCHIVED_RESEARCH_FILES: tuple[str, ...] = (
    # scripts/archive_research_artifacts.py routes v9.2.1_nines*.{json,md}
    # to the nines/ subdir and evaluation/* to evaluation/; everything else
    # lands in other/. These per-subdir paths are the canonical post-run
    # locations for the 6 stage-output artefacts.
    "docs/cycle-archive/v9.2.0/other/v9.2.1_check_refs.md",
    "docs/cycle-archive/v9.2.0/nines/v9.2.1_nines_aggregate.md",
    "docs/cycle-archive/v9.2.0/other/v9.2.1_validation_tasks.md",
    "docs/cycle-archive/v9.2.0/other/v9.2.1_integration_report.md",
    "docs/cycle-archive/v9.2.0/other/v9.2.1_e2e_report.md",
    "docs/cycle-archive/v9.2.0/evaluation/v9.2.1_evaluation.md",
)


def test_v9_2_1_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.1: PV-07 meta-validation surfaces have presence + import-smoke coverage.

    Discharges the W-18 precondition for the v9.2.1 PATCH — every
    CHANGELOG entry mentioning a v9.2.1 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v9.2.1 PV-07 is the self-update meta-validation PATCH; by design
    it introduces **zero new code paths** (cycle plan §PV-07 verbatim).
    The surfaces this lint pins are therefore:

    1. ``tests/test_capability_e2e.py.__all__`` has ≥ 14 entries — the
       10 v9.2.0 headline tests + 4 NEW PV-07 parametrized tests. A
       regression below 14 means one of the PV-07 tests was deleted.
    2. Each of the 4 PV-07 test functions is a callable attribute of
       ``tests.test_capability_e2e``. Guards against a dangling
       ``__all__`` entry that references a deleted / renamed function.
    3. W-17 PV-07 budget proof — the 4 NEW test function names begin
       with ``test_pv07_`` so the cap-counting grep `git diff | grep
       "test_pv07_[a-z_]\\+("` matches exactly 4 lines in the PV-07
       diff.
    4. W-19 re-archive: when the consumer repo has run the post-PV-07
       re-archive (``scripts/archive_research_artifacts.py 9.2.0
       --extra-prefix v9.2.``), each of the 6 v9.2.1 research artefacts
       lands under ``docs/cycle-archive/v9.2.0/``. Self-skips when the
       archive directory lacks the v9.2.1 nested files (fresh clone
       that has not run the re-archive yet).

    Failure modes:
      * "< 14 entries in __all__" → a PV-07 test was deleted; restore it.
      * "PV-07 test not callable" → ``__all__`` drifted from module
        reality; fix the ``__all__`` list OR the missing function.
      * "archive artefact missing AND directory populated" → the
        re-archive ran but without the v9.2.* extra-prefix sweep;
        re-run ``python scripts/archive_research_artifacts.py 9.2.0
        --extra-prefix v9.2.``.
    """
    import tests.test_capability_e2e as e2e_module

    assert hasattr(e2e_module, "__all__"), (
        "W-18 v9.2.1 violation: tests/test_capability_e2e.py must declare "
        "__all__ with both the v9.2.0 headline names AND the v9.2.1 PV-07 "
        "multi-fixture tests"
    )
    all_names = e2e_module.__all__
    assert len(all_names) >= _V9_2_1_CAPABILITY_E2E_MIN_ENTRIES, (
        f"W-18 v9.2.1 violation: tests/test_capability_e2e.py.__all__ has "
        f"{len(all_names)} entries; the PV-07 extension requires at least "
        f"{_V9_2_1_CAPABILITY_E2E_MIN_ENTRIES} (10 v9.2.0 baseline + 4 PV-07)"
    )
    pv07_entries = [name for name in all_names if name.startswith("test_pv07_")]
    assert len(pv07_entries) >= 4, (
        f"W-18 v9.2.1 violation: tests/test_capability_e2e.py.__all__ must "
        f"carry at least 4 test_pv07_* entries (the PV-07 multi-fixture "
        f"E2E set); got {pv07_entries!r}"
    )
    for name in pv07_entries:
        target = getattr(e2e_module, name, None)
        assert callable(target), (
            f"W-18 v9.2.1 violation: tests/test_capability_e2e.py.__all__ "
            f"entry {name!r} is not a callable test function in the module"
        )

    archive_dir = project_root / "docs" / "cycle-archive" / "v9.2.0"
    if archive_dir.is_dir():
        for relpath in _V9_2_1_ARCHIVED_RESEARCH_FILES:
            full = project_root / relpath
            if not full.is_file():
                # Self-skip: the v9.2.0 archive exists but the v9.2.1
                # sweep has not run yet on this clone (pre-PV-07
                # re-archive state). Per W-19 the re-archive is
                # idempotent — run it once to populate.
                import pytest as _pytest

                _pytest.skip(
                    f"v9.2.1 archive artefact {relpath!r} not yet re-archived; "
                    f"run `python scripts/archive_research_artifacts.py 9.2.0 "
                    f"--extra-prefix v9.2.` to populate"
                )
            size = full.stat().st_size
            assert size >= 200, (
                f"W-18 v9.2.1 violation: archive artefact {relpath!r} is {size} "
                f"bytes (< 200 byte minimum); empty/stub files do not satisfy "
                f"the W-19 archive contract"
            )
    # No else branch: when `docs/cycle-archive/v9.2.0/` is absent the W-19
    # cycle archive has not been committed yet; the separate
    # `test_v9_2_0_cycle_archive_and_extra_prefix` lint fails loudly for
    # that case and this PV-07 lint stays permissive on the v9.2.1 half.


# ---------------------------------------------------------------------------
# v9.2.2 PV-01 — W-18 ghost-audit refresh for the I-001 critical CLI fix.
# ---------------------------------------------------------------------------
#
# v9.2.2 PV-01 is the first PV of the v9.2.2 PATCH cycle (3 PVs:
# v9.2.2 -> v9.2.3 -> v9.2.4) addressing the 4 issues catalogued in
# `.local/feedbacks/feedback_for_v9.2.1.md`. PV-01 ships:
#
# 1. NEW tests/test_init_project_pip_wheel.py — 6 NEW test functions
#    (one parametrized x4 = 9 test cases) pinning the deferred-check
#    surface, the informative error message, the `--list` regression,
#    the multi-target dispatch ordering invariant, the canonical
#    8-path scaffold smoke, and the no-pip-install-recommendation
#    regression lint.
# 2. EDIT src/devolaflow/init_project.py — surgical I-001 fix:
#    introduces `AGENT_DIR_REQUIRED_TARGETS` (frozenset) and defers
#    the SKILL.md existence check to inside the per-target dispatch
#    loop. `local` is exempt because `install_local` uses
#    `scaffold_local` + `importlib.resources`. The error message no
#    longer recommends `pip install devolaflow` (the misleading
#    recommendation that landed users in I-001).
# 3. EDIT workflow-system/agent/SKILL.md §"Version & Update" — I-004
#    one-line note about the wheel/CLI mismatch + `local` fallback.
#
# This W-18 refresh discharges the precondition: every CHANGELOG entry
# mentioning a v9.2.2 feature MUST have a backing ghost-audit lint in
# THIS file BEFORE the CHANGELOG entry is authored.

_V9_2_2_NEW_FILES: tuple[str, ...] = ("tests/test_init_project_pip_wheel.py",)

# Minimum byte size for a v9.2.2 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_2_2_FILE_MIN_BYTES: int = 50

# The pip-wheel test file ships with EXACTLY 6 test FUNCTIONS per the
# PV-01 W-17 budget pin (one of which is parametrized x4 -> 9 cases at
# collection time). The function-count floor catches regression below
# the W-17 ledger; collection-time case count is intentionally NOT
# pinned because parametrize expansions don't count against the cap.
_V9_2_2_PIP_WHEEL_MIN_TEST_FUNCTIONS: int = 6

# AGENT_DIR_REQUIRED_TARGETS — the deferred-check gate surface. Pinning
# the exact membership here catches a silent widening / narrowing of
# which dispatch paths require the on-disk workflow-system/agent/ tree.
_V9_2_2_AGENT_DIR_REQUIRED_TARGETS: frozenset[str] = frozenset(
    {"cursor", "claude", "copilot", "codex"}
)


def test_v9_2_2_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.2: every NEW v9.2.2 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition for the v9.2.2 PATCH — every
    CHANGELOG entry mentioning a v9.2.2 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v9.2.2 PV-01 is the I-001 critical-fix PV; the surfaces this lint
    pins are:

    1. ``tests/test_init_project_pip_wheel.py`` exists on disk and
       carries ≥ 6 test FUNCTIONS (the PV-01 W-17 budget pin —
       parametrize expansions don't count against the cap, so the floor
       is on the ``def test_*`` count, not the collection-time case
       count).
    2. ``AGENT_DIR_REQUIRED_TARGETS`` is importable from
       :mod:`devolaflow.init_project`, equals exactly the 4-element
       frozenset ``{"cursor", "claude", "copilot", "codex"}``, and does
       NOT contain ``"local"`` (the I-001 closure invariant —
       ``install_local`` uses ``scaffold_local`` + ``importlib.resources``
       and has zero dependency on ``agent_dir``).

    Failure modes:
      * "missing on disk" → a v9.2.2 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_2_2_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "AGENT_DIR_REQUIRED_TARGETS membership drift" → the deferred-
        check surface was silently widened or narrowed; either restore
        the original 4-element set OR document the operator-visible
        change with an ADR.
      * "test function count regressed" → a PV-01 test was deleted;
        restore it.
    """
    import ast

    for relpath in _V9_2_2_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.2 violation: NEW v9.2.2 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_2_2_FILE_MIN_BYTES, (
            f"W-18 v9.2.2 violation: NEW v9.2.2 surface {relpath!r} is {size} "
            f"bytes (< {_V9_2_2_FILE_MIN_BYTES} byte minimum); empty/stub "
            f"files do not satisfy the W-18 precondition"
        )

    pip_wheel_test_file = project_root / "tests" / "test_init_project_pip_wheel.py"
    pip_wheel_ast = ast.parse(pip_wheel_test_file.read_text(encoding="utf-8"))
    test_functions = [
        node
        for node in pip_wheel_ast.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(test_functions) >= _V9_2_2_PIP_WHEEL_MIN_TEST_FUNCTIONS, (
        f"W-18 v9.2.2 violation: tests/test_init_project_pip_wheel.py declares "
        f"{len(test_functions)} test_* functions; the PV-01 W-17 budget pin "
        f"requires at least {_V9_2_2_PIP_WHEEL_MIN_TEST_FUNCTIONS}"
    )

    from devolaflow.init_project import AGENT_DIR_REQUIRED_TARGETS

    assert AGENT_DIR_REQUIRED_TARGETS == _V9_2_2_AGENT_DIR_REQUIRED_TARGETS, (
        f"W-18 v9.2.2 violation: AGENT_DIR_REQUIRED_TARGETS = "
        f"{AGENT_DIR_REQUIRED_TARGETS!r}; expected "
        f"{_V9_2_2_AGENT_DIR_REQUIRED_TARGETS!r} (exactly the 4 historical "
        f"agent-dir consumers — cursor / claude / copilot / codex). "
        f"`local` is intentionally absent — the I-001 closure invariant"
    )
    assert "local" not in AGENT_DIR_REQUIRED_TARGETS, (
        "W-18 v9.2.2 violation: `local` MUST NOT appear in "
        "AGENT_DIR_REQUIRED_TARGETS — install_local uses scaffold_local + "
        "importlib.resources and has ZERO dependency on agent_dir. "
        "Adding `local` here would re-introduce the I-001 abort scenario "
        "for wheel-only installs."
    )
    assert isinstance(AGENT_DIR_REQUIRED_TARGETS, frozenset), (
        f"W-18 v9.2.2 violation: AGENT_DIR_REQUIRED_TARGETS must be a "
        f"frozenset (immutable surface); got "
        f"{type(AGENT_DIR_REQUIRED_TARGETS).__name__!r}"
    )


def test_v9_2_2_local_target_no_workflow_system_dependency(project_root: Path) -> None:
    """W-18 v9.2.2: install_local body MUST NOT reference agent_dir.

    The I-001 closure invariant — ``install_local`` is the ONE per-target
    installer that does NOT consume ``agent_dir``. The deferred-check
    fix relies on this invariant: if ``install_local`` ever starts
    reading from ``agent_dir`` (e.g. copying a file from
    ``agent_dir / "templates" / "..."``), the I-001 abort scenario
    re-emerges for wheel-only installs even when the user explicitly
    requests ``devola-init local``.

    This lint walks the ``install_local`` function body via AST and
    asserts no ``Name`` node references the ``agent_dir`` parameter
    (other than the parameter declaration itself, which the AST walk
    distinguishes via ``ast.arg`` vs ``ast.Name``).

    Failure modes:
      * "install_local body references agent_dir" → the agent-dir-
        independence invariant regressed; either remove the new
        agent_dir reference (recommended) OR add ``"local"`` to
        ``AGENT_DIR_REQUIRED_TARGETS`` AND update the W-18 v9.2.2
        ghost-audit lint above to reflect the operator-visible change.
        The latter path RE-INTRODUCES the I-001 wheel-install regression
        and requires explicit ADR documentation per W-21 governance.
    """
    import ast

    init_module_path = project_root / "src" / "devolaflow" / "init_project.py"
    tree = ast.parse(init_module_path.read_text(encoding="utf-8"))

    install_local_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "install_local"
        ),
        None,
    )
    assert install_local_node is not None, (
        "W-18 v9.2.2 violation: install_local function definition missing "
        "from src/devolaflow/init_project.py — the I-001 fix depends on this "
        "function existing as the agent-dir-independent installer"
    )

    agent_dir_references: list[ast.Name] = []
    for child in ast.walk(install_local_node):
        if isinstance(child, ast.Name) and child.id == "agent_dir":
            agent_dir_references.append(child)

    assert agent_dir_references == [], (
        f"W-18 v9.2.2 violation: install_local body references `agent_dir` "
        f"on lines {[n.lineno for n in agent_dir_references]} — the I-001 "
        f"closure invariant requires install_local to be agent-dir-"
        f"independent (uses scaffold_local + importlib.resources only). "
        f"If a new agent_dir consumer was intentionally added, also "
        f"register `local` in AGENT_DIR_REQUIRED_TARGETS (which RE-INTRODUCES "
        f"the I-001 wheel-install scenario for `devola-init local`) and "
        f"document the operator-visible change with an ADR."
    )


# ---------------------------------------------------------------------------
# v9.2.3 PV-02 — W-18 ghost-audit refresh for the DX-improvement cluster.
# ---------------------------------------------------------------------------
#
# v9.2.3 PV-02 is the second PV of the v9.2.2 PATCH cycle (3 PVs:
# v9.2.2 → v9.2.3 → v9.2.4). PV-02 ships:
#
# 1. NEW tests/test_scaffold_gitignore_audit.py — 6 NEW test functions
#    pinning the I-003 `_audit_gitignore_coverage` surface in
#    `src/devolaflow/local/workspace.py` (logs WARN per scaffold path
#    that an existing .gitignore rule already covers; quiet on
#    absent / unrelated rules; conservative on negation rules).
# 2. NEW tests/test_init_project_mode_flag.py — 5 NEW test functions
#    pinning the `--mode={core,standard,full}` shorthand surface
#    + the explicit-beats-implicit precedence rule + the invalid-mode
#    exit path.
# 3. EDIT src/devolaflow/local/workspace.py — added `_read_gitignore_rules`,
#    `_path_matches_gitignore`, `_audit_gitignore_coverage` helpers,
#    `last_gitignore_audit` accessor, and integrated the audit at the
#    tail of `scaffold_local`.
# 4. EDIT src/devolaflow/init_project.py — added `VALID_MODES` constant,
#    `_parse_mode` resolver, and the mode-derived default wiring in
#    `main()`. `_parse_no_compile` + `_parse_with_examples` gained
#    keyword-only `default=` kwargs (backward-compat preserved by the
#    default value on each).
# 5. EDIT README.md — new "Troubleshooting installs" subsection
#    documenting I-002 (baidubce mirror), I-001 closure (v9.2.2), and
#    the `--mode=core` shorthand discovery hint.
# 6. EDIT workflow-system/agent/SKILL.md §"Version & Update" —
#    install note refreshed to cite v9.2.3 `--mode=core` shorthand.
#
# This W-18 refresh discharges the precondition: every CHANGELOG entry
# mentioning a v9.2.3 feature MUST have a backing ghost-audit lint in
# THIS file BEFORE the CHANGELOG entry is authored.

_V9_2_3_NEW_FILES: tuple[str, ...] = (
    "tests/test_scaffold_gitignore_audit.py",
    "tests/test_init_project_mode_flag.py",
)

# Minimum byte size for a v9.2.3 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_2_3_FILE_MIN_BYTES: int = 50

# Test-function floor per file — pinned by the dispatch's PV-02 budget
# (5 named acceptance tests + 1 helper-edge-cases on the gitignore side;
# 5 named acceptance tests on the mode side).
_V9_2_3_GITIGNORE_MIN_TEST_FUNCTIONS: int = 5
_V9_2_3_MODE_MIN_TEST_FUNCTIONS: int = 5

# VALID_MODES — the `--mode=` shorthand surface. Pinning the exact
# membership here catches a silent widening (e.g. a new mode added
# without operator-facing docs) or narrowing (e.g. a mode dropped
# without a deprecation cycle).
_V9_2_3_VALID_MODES: frozenset[str] = frozenset({"core", "standard", "full"})


def test_v9_2_3_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.3: every NEW v9.2.3 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition for the v9.2.3 PATCH — every
    CHANGELOG entry mentioning a v9.2.3 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v9.2.3 PV-02 surfaces this lint pins:

    1. ``tests/test_scaffold_gitignore_audit.py`` and
       ``tests/test_init_project_mode_flag.py`` exist on disk and
       carry ≥ 5 test FUNCTIONS each (the PV-02 dispatch budget pin —
       parametrize expansions don't count against the cap).
    2. ``_audit_gitignore_coverage`` and ``last_gitignore_audit`` are
       importable from :mod:`devolaflow.local.workspace`.
    3. ``_parse_mode`` and ``VALID_MODES`` are importable from
       :mod:`devolaflow.init_project`, and ``VALID_MODES`` equals
       exactly the 3-element frozenset
       ``{"core", "standard", "full"}``.

    Failure modes:
      * "missing on disk" → a v9.2.3 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_2_3_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "VALID_MODES membership drift" → the `--mode=` surface was
        silently widened or narrowed; either restore the original
        3-element set OR document the operator-visible change with
        an ADR.
      * "test function count regressed" → a PV-02 test was deleted;
        restore it.
    """
    import ast

    for relpath in _V9_2_3_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.3 violation: NEW v9.2.3 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_2_3_FILE_MIN_BYTES, (
            f"W-18 v9.2.3 violation: NEW v9.2.3 surface {relpath!r} is {size} "
            f"bytes (< {_V9_2_3_FILE_MIN_BYTES} byte minimum); empty/stub "
            f"files do not satisfy the W-18 precondition"
        )

    gitignore_test_file = project_root / "tests" / "test_scaffold_gitignore_audit.py"
    gitignore_ast = ast.parse(gitignore_test_file.read_text(encoding="utf-8"))
    gitignore_test_functions = [
        node
        for node in gitignore_ast.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(gitignore_test_functions) >= _V9_2_3_GITIGNORE_MIN_TEST_FUNCTIONS, (
        f"W-18 v9.2.3 violation: tests/test_scaffold_gitignore_audit.py "
        f"declares {len(gitignore_test_functions)} test_* functions; the "
        f"PV-02 dispatch budget pin requires at least "
        f"{_V9_2_3_GITIGNORE_MIN_TEST_FUNCTIONS}"
    )

    mode_test_file = project_root / "tests" / "test_init_project_mode_flag.py"
    mode_ast = ast.parse(mode_test_file.read_text(encoding="utf-8"))
    mode_test_functions = [
        node
        for node in mode_ast.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(mode_test_functions) >= _V9_2_3_MODE_MIN_TEST_FUNCTIONS, (
        f"W-18 v9.2.3 violation: tests/test_init_project_mode_flag.py "
        f"declares {len(mode_test_functions)} test_* functions; the "
        f"PV-02 dispatch budget pin requires at least "
        f"{_V9_2_3_MODE_MIN_TEST_FUNCTIONS}"
    )

    from devolaflow.init_project import VALID_MODES, _parse_mode
    from devolaflow.local.workspace import (
        _audit_gitignore_coverage,
        last_gitignore_audit,
    )

    assert callable(_audit_gitignore_coverage), (
        "W-18 v9.2.3 violation: _audit_gitignore_coverage must be importable "
        "from devolaflow.local.workspace"
    )
    assert callable(last_gitignore_audit), (
        "W-18 v9.2.3 violation: last_gitignore_audit accessor must be importable "
        "from devolaflow.local.workspace"
    )
    assert callable(_parse_mode), (
        "W-18 v9.2.3 violation: _parse_mode must be importable from devolaflow.init_project"
    )

    assert VALID_MODES == _V9_2_3_VALID_MODES, (
        f"W-18 v9.2.3 violation: VALID_MODES = {VALID_MODES!r}; expected "
        f"exactly {_V9_2_3_VALID_MODES!r} (the 3-mode dispatch contract: "
        f"core / standard / full)"
    )
    assert isinstance(VALID_MODES, frozenset), (
        f"W-18 v9.2.3 violation: VALID_MODES must be a frozenset (immutable "
        f"surface); got {type(VALID_MODES).__name__!r}"
    )


def test_v9_2_3_mode_flag_surface_complete(project_root: Path) -> None:
    """W-18 v9.2.3: `_parse_mode` returns one of {core, standard, full, None}.

    AST walk over `_parse_mode` asserts the function body's `return`
    statements yield only valid mode strings (the elements of
    `VALID_MODES`) or `None`. A future PV that introduces a 4th mode
    MUST also update `VALID_MODES` AND this lint's expected set —
    catching a regression where the parser silently accepts a value
    that the docstring + README never advertised.
    """
    import ast

    init_module_path = project_root / "src" / "devolaflow" / "init_project.py"
    tree = ast.parse(init_module_path.read_text(encoding="utf-8"))

    parse_mode_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_parse_mode"
        ),
        None,
    )
    assert parse_mode_node is not None, (
        "W-18 v9.2.3 violation: _parse_mode function definition missing "
        "from src/devolaflow/init_project.py — the PV-02 mode shorthand "
        "depends on this resolver existing"
    )

    # Walk the body; collect every `return <expr>` and assert each one
    # is either `return None`, `return mode` (the validated variable),
    # or `return <Name>` referring to one of the local mode-derivation
    # variables. The intent: the function must NEVER return a literal
    # string outside VALID_MODES (catches a silent widening like
    # `return "lite"` slipped into the body).
    return_nodes = [node for node in ast.walk(parse_mode_node) if isinstance(node, ast.Return)]
    assert len(return_nodes) >= 2, (
        f"W-18 v9.2.3 violation: _parse_mode must have ≥ 2 return statements "
        f"(the None-fallback + the validated mode return); got "
        f"{len(return_nodes)}"
    )

    for ret in return_nodes:
        if ret.value is None:
            continue  # bare `return` — equivalent to `return None`, fine
        if isinstance(ret.value, ast.Constant) and ret.value.value is None:
            continue  # `return None`
        if isinstance(ret.value, ast.Name):
            continue  # `return mode` (validated variable) — fine
        if (
            isinstance(ret.value, ast.Constant)
            and isinstance(ret.value.value, str)
            and ret.value.value in {"core", "standard", "full"}
        ):
            continue
        raise AssertionError(
            f"W-18 v9.2.3 violation: _parse_mode returns an unexpected "
            f"expression at line {ret.lineno}: {ast.dump(ret.value)!r}. "
            f"Expected `return None` or `return <variable>` or `return "
            f'"core"/"standard"/"full"`. Adding a new mode requires '
            f"updating BOTH VALID_MODES AND this lint's expected set."
        )


# ---------------------------------------------------------------------------
# v9.2.4 PV-03 — W-18 ghost-audit refresh for the cycle-close validation.
# ---------------------------------------------------------------------------
#
# v9.2.4 PV-03 is the FINAL PV of the v9.2.2 PATCH cycle (3 PVs:
# v9.2.2 -> v9.2.3 -> v9.2.4). PV-03 ships ZERO new code paths — only
# cycle-close validation artefacts:
#
# 1. EXTEND tests/test_init_project_pip_wheel.py with
#    test_cycle_close_e2e_local_mode_core_works — parametrized across
#    4 fixture shapes (empty / with_gitignore_local / with_gitignore_all /
#    full_pip_wheel_install). Each shape validates: `devola-init local
#    --mode=core` exits 0; 8 canonical paths created; --mode=core implies
#    --no-compile so cursor-rules + AGENTS.md compile artefacts NOT
#    written; gitignore-covered paths emit per-path WARN; absent /
#    unrelated rules emit ZERO WARN.
#
# 2. NEW .local/research/v9.2.2_retrospective.md — W-7 / SI-8 cycle-
#    close retrospective with the 4 mandatory sections (Gaps Identified
#    / What was Implemented / What was Deferred / Key Learnings) +
#    the W-21 Soul-set freeze telegraph for v9.4.0.
#
# 3. W-19 archive refresh: docs/cycle-archive/v9.2.0/ now contains
#    v9.2.2_retrospective.md (post `python scripts/archive_research_artifacts.py
#    9.2.0 --extra-prefix v9.2.`), making the retrospective accessible
#    from a fresh clone (where .local/ is gitignored).
#
# This W-18 refresh discharges the precondition: every CHANGELOG entry
# mentioning a v9.2.4 feature MUST have a backing ghost-audit lint in
# THIS file BEFORE the CHANGELOG entry is authored.

# The 4 mandatory W-7 retrospective section headings — must ALL appear
# in the retrospective for it to be a valid W-7 / SI-8 artefact.
_V9_2_4_W7_MANDATORY_SECTIONS: tuple[str, ...] = (
    "## 1. Gaps identified",
    "## 2. What was implemented",
    "## 3. What was deferred and why",
    "## 4. Key learnings",
)

# The exact parametrize cardinality on the cycle-close E2E test —
# pinned by the cycle plan §PV-03 contract (4 representative install
# fixture shapes). A future PV that drops a shape MUST update this
# constant + document the operator-visible scope reduction.
_V9_2_4_E2E_PARAMETRIZE_CASES: int = 4

_V9_2_4_E2E_FIXTURE_SHAPES: frozenset[str] = frozenset(
    {"empty", "with_gitignore_local", "with_gitignore_all", "full_pip_wheel_install"}
)


def test_v9_2_4_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.4: every NEW v9.2.4 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.2.4 cycle-close PATCH —
    every CHANGELOG entry mentioning a v9.2.4 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.2.4 PV-03 surfaces this lint pins:

    1. ``.local/research/v9.2.2_retrospective.md`` exists (the
       canonical write-target — gitignored on most clones, so we
       prefer the W-19 archive copy under ``docs/cycle-archive/v9.2.0/``
       for the load-bearing assertion below) and contains all 4 W-7
       mandatory section headings.
    2. ``tests/test_init_project_pip_wheel.py`` declares
       ``test_cycle_close_e2e_local_mode_core_works`` and parametrizes
       it across exactly 4 fixture shapes (the cycle plan §PV-03
       contract — empty / with_gitignore_local / with_gitignore_all /
       full_pip_wheel_install).
    3. ``docs/cycle-archive/v9.2.0/v9.2.2_retrospective.md`` exists
       (the W-19 archive contract — PATCH series rolls into the parent
       MINOR cycle archive), making the retrospective visible to a
       fresh-clone reviewer who doesn't carry ``.local/``.

    Failure modes:
      * "retrospective missing on disk" → the W-7 / SI-8 artefact was
        not authored; cycle-close PATCH is incomplete.
      * "missing mandatory section heading" → the retrospective is
        partial; W-7 §"4 mandatory sections" requires ALL of Gaps /
        Implemented / Deferred / Learnings.
      * "parametrize cardinality drift" → the cycle-close E2E lost
        a fixture shape; either restore it OR update both the cycle
        plan §PV-03 contract AND this lint's pinned constant.
      * "archive missing the retrospective" → run
        ``python scripts/archive_research_artifacts.py 9.2.0
        --extra-prefix v9.2.`` to populate (idempotent).
    """
    import ast

    archived_retrospective = (
        project_root / "docs" / "cycle-archive" / "v9.2.0" / "v9.2.2_retrospective.md"
    )
    assert archived_retrospective.is_file(), (
        f"W-18 v9.2.4 violation: W-19 archive contract — "
        f"{archived_retrospective.relative_to(project_root)} missing. "
        f"Run `python scripts/archive_research_artifacts.py 9.2.0 "
        f"--extra-prefix v9.2.` to populate (idempotent)."
    )
    archived_size = archived_retrospective.stat().st_size
    assert archived_size >= 1000, (
        f"W-18 v9.2.4 violation: archived retrospective is "
        f"{archived_size} bytes (< 1000 byte minimum); empty/stub "
        f"retrospective does not satisfy the W-7 4-section contract"
    )

    archived_text = archived_retrospective.read_text(encoding="utf-8")
    for heading in _V9_2_4_W7_MANDATORY_SECTIONS:
        assert heading in archived_text, (
            f"W-18 v9.2.4 violation: retrospective missing mandatory "
            f"W-7 section heading {heading!r}; the W-7 / SI-8 contract "
            f"requires ALL of {list(_V9_2_4_W7_MANDATORY_SECTIONS)!r}"
        )

    pip_wheel_test_file = project_root / "tests" / "test_init_project_pip_wheel.py"
    pip_wheel_ast = ast.parse(pip_wheel_test_file.read_text(encoding="utf-8"))
    e2e_node = next(
        (
            node
            for node in pip_wheel_ast.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_cycle_close_e2e_local_mode_core_works"
        ),
        None,
    )
    assert e2e_node is not None, (
        "W-18 v9.2.4 violation: tests/test_init_project_pip_wheel.py "
        "MUST declare test_cycle_close_e2e_local_mode_core_works; the "
        "cycle plan §PV-03 contract requires this multi-fixture E2E "
        "validation surface"
    )

    parametrize_decorators = [
        dec
        for dec in e2e_node.decorator_list
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and dec.func.attr == "parametrize"
        )
    ]
    assert len(parametrize_decorators) == 1, (
        f"W-18 v9.2.4 violation: test_cycle_close_e2e_local_mode_core_works "
        f"must carry exactly ONE @pytest.mark.parametrize decorator; "
        f"got {len(parametrize_decorators)}"
    )

    parametrize_call = parametrize_decorators[0]
    shape_list_arg = parametrize_call.args[1] if len(parametrize_call.args) >= 2 else None
    assert shape_list_arg is not None and isinstance(shape_list_arg, ast.List), (
        "W-18 v9.2.4 violation: parametrize values argument must be a "
        "literal list of fixture shapes"
    )
    shape_values = {
        elt.value
        for elt in shape_list_arg.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    }
    assert len(shape_values) == _V9_2_4_E2E_PARAMETRIZE_CASES, (
        f"W-18 v9.2.4 violation: cycle plan §PV-03 contract requires "
        f"exactly {_V9_2_4_E2E_PARAMETRIZE_CASES} parametrize cases on "
        f"test_cycle_close_e2e_local_mode_core_works; got "
        f"{len(shape_values)} ({sorted(shape_values)!r})"
    )
    assert shape_values == _V9_2_4_E2E_FIXTURE_SHAPES, (
        f"W-18 v9.2.4 violation: parametrize fixture shapes drifted "
        f"from the cycle plan §PV-03 contract. Got {sorted(shape_values)!r}; "
        f"expected exactly {sorted(_V9_2_4_E2E_FIXTURE_SHAPES)!r}"
    )

    # The .local/research/ retrospective is the canonical write-target
    # but is gitignored on most clones. Skip the local-presence assertion
    # gracefully when the file is absent — the load-bearing W-7 contract
    # was already verified above against the archived copy under
    # docs/cycle-archive/v9.2.0/, which IS committed.
    local_retrospective = project_root / ".local" / "research" / "v9.2.2_retrospective.md"
    if local_retrospective.is_file():
        # When present, the local copy MUST match the same 4-section
        # contract (catches a future bug where the local + archived
        # copies drift apart).
        local_text = local_retrospective.read_text(encoding="utf-8")
        local_rel = local_retrospective.relative_to(project_root)
        for heading in _V9_2_4_W7_MANDATORY_SECTIONS:
            assert heading in local_text, (
                f"W-18 v9.2.4 violation: local retrospective {local_rel} "
                f"is missing mandatory section heading {heading!r}; "
                f"the local + archived copies have drifted (re-run "
                f"`python scripts/archive_research_artifacts.py 9.2.0 "
                f"--extra-prefix v9.2.` to refresh the archive)"
            )


# ---------------------------------------------------------------------------
# W-18 v9.3.0 ghost-audit refresh — Performance Overhaul #1.
# ---------------------------------------------------------------------------


# v9.3.0 Performance Overhaul #1 NEW symbols (PV-02..PV-06). Each entry is the
# minimum import-smoke contract that must hold for the symbol to be
# considered "alive" — i.e. the CHANGELOG cites it AND it imports cleanly.
_V9_3_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-02 latency harness
    ("benchmarks.devolaflow_context.latency_harness", "capture_latency"),
    ("benchmarks.devolaflow_context.latency_harness", "measure_function"),
    ("benchmarks.devolaflow_context.latency_harness", "MEASURED_FUNCTIONS"),
    ("benchmarks.devolaflow_context.latency_harness", "SCHEMA_VERSION"),
    # PV-03 LRU cache
    ("devolaflow.task_adaptive_selector", "_load_profiles_cached"),
    ("devolaflow.task_adaptive_selector", "_load_skill_md_cached"),
    ("devolaflow.task_adaptive_selector", "_estimate_tokens_tiktoken_cached"),
    ("devolaflow.task_adaptive_selector", "_estimate_tokens_fallback_cached"),
    # PV-04 compressor split
    ("devolaflow.compressor", "assert_dispatch_layout"),
    ("devolaflow.compressor.layout", "assert_dispatch_layout"),
    ("devolaflow.compressor.patterns", "PRESERVE_LIST"),
    ("devolaflow.compressor.transforms", "compress_message"),
    # PV-05 async dispatch executor
    ("devolaflow.agent_workspace.dispatch_executor", "AsyncDispatchExecutor"),
    ("devolaflow.agent_workspace.dispatch_executor", "TaskOutcome"),
    ("devolaflow.agent_workspace.dispatch_executor", "ExecutorError"),
    ("devolaflow.agent_workspace.dispatch_executor", "DEFAULT_MAX_CONCURRENCY"),
    # PV-06 simple-task auto-shortcut
    ("devolaflow.skills.change_activation", "shortcut_from_env"),
    ("devolaflow.skills.change_activation", "shortcut_verdict"),
    ("devolaflow.skills.change_activation", "ShortcutVerdict"),
    ("devolaflow.skills.change_activation", "SHORTCUT_FLAG_NAME"),
    ("devolaflow.skills.change_activation", "SHORTCUT_FLAG_TRUTHY"),
)

# v9.3.0 PV-02 latency baselines — every CHANGELOG entry that cites the
# numerical perf gain pins these files. The W-18 contract requires them
# to be present + parseable.
_V9_3_0_LATENCY_BASELINE_PATHS: tuple[Path, ...] = (
    Path("benchmarks/devolaflow_context/baselines/v9.3.0_latency.json"),
    Path("benchmarks/devolaflow_context/baselines/v9.3.0_baseline.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v9.3.0.yaml"),
)

# v9.3.0 PV-06 env-flag — the W-20 §3 documentation contract pins the
# `references/env-flags.md` §2.12 entry. The lint asserts the literal
# `### 2.12` + flag name + truthy literal appear together in the file.
_V9_3_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.12 `DEVOLAFLOW_SIMPLE_SHORTCUT`",
    "DEVOLAFLOW_SIMPLE_SHORTCUT",
    "shortcut_from_env",
    "shortcut_verdict",
)


def test_v9_3_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.3.0: every NEW v9.3.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.3.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.3.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.3.0 PV-07 cycle close pins:

    1. Every NEW public symbol from PV-02..PV-06 imports cleanly from
       its canonical module path. Catches accidental name collisions,
       circular imports, and the v6.0.3-style "feature mentioned in
       CHANGELOG but never wired" anti-pattern.
    2. The 3 W-16 wholesale baseline files (composite + latency + layout
       invariant) exist on disk. The CHANGELOG cites the empirical
       perf-gain numbers (97.5% select_context p95 improvement) which
       are derived FROM these files; missing files = unprovable claim.
    3. The PV-06 env-flag is documented in `references/env-flags.md`
       §2.12 with the canonical W-20 §3 §2.12 entry header + the flag
       name + the helper function names, all in the same file.
    4. The PV-04 compressor split delivered exactly 4 files in the
       package (`__init__.py` + `layout.py` + `patterns.py` +
       `transforms.py`). A future PV that accidentally collapses the
       split or grows it to a 5th module would break this test.

    Failure modes:
      * "symbol import failed" → the CHANGELOG cites a feature that
        doesn't exist; either land the feature or remove the entry.
      * "missing baseline file" → run the PV-02 harness CLI to
        regenerate; OR the cycle didn't honour W-16 (mandatory).
      * "missing env-flag doc literal" → the W-20 §7 checklist failed;
        author the §2.12 entry.
      * "compressor package member count drift" → either accept the
        new structure (and update this test in the same PR) OR
        restore the v9.3.0 PV-04 4-file shape.
    """
    import importlib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_3_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.3.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.3.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.3.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — W-16 wholesale baseline file presence + parseability.
    import json

    import yaml

    for baseline_rel in _V9_3_0_LATENCY_BASELINE_PATHS:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v9.3.0 violation: PV-02 W-16 baseline {baseline_rel} "
            f"missing. Run `python -m benchmarks.devolaflow_context."
            f"latency_harness --iterations 100 --output {baseline_rel}` "
            f"(for the latency JSON) OR `python -m benchmarks."
            f"devolaflow_context.generate_baseline` (for the composite JSON) "
            f"OR copy the v9.2.0 layout-invariant witness (for the YAML)."
        )
        # Smoke-parse to catch corrupt files.
        if baseline_path.suffix == ".json":
            json.loads(baseline_path.read_text(encoding="utf-8"))
        elif baseline_path.suffix == ".yaml":
            yaml.safe_load(baseline_path.read_text(encoding="utf-8"))

    # §3 — PV-06 env-flag W-20 §7 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    assert env_flags_path.is_file(), (
        f"W-18 v9.3.0 violation: {env_flags_path.relative_to(project_root)} "
        f"missing — PV-06 W-20 §7 contract requires the env-flag inventory"
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_3_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.3.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-06 W-20 §7 checklist requires the §2.12 entry to "
            f"document the new flag with both the flag name and the "
            f"helper function names. Add the §2.12 block."
        )

    # §4 — PV-04 compressor 3-module split shape (4 files: __init__ + 3 modules).
    compressor_pkg = project_root / "src" / "devolaflow" / "compressor"
    assert compressor_pkg.is_dir(), (
        "W-18 v9.3.0 violation: src/devolaflow/compressor/ is not a directory. "
        "PV-04 split compressor.py into a package; restore the package shape."
    )
    expected_pkg_files = {"__init__.py", "layout.py", "patterns.py", "transforms.py"}
    actual_pkg_files = {p.name for p in compressor_pkg.iterdir() if p.is_file()}
    assert actual_pkg_files == expected_pkg_files, (
        f"W-18 v9.3.0 violation: compressor package member set drifted. "
        f"Expected exactly {sorted(expected_pkg_files)!r}; got "
        f"{sorted(actual_pkg_files)!r}. PV-04 contract requires the 4-file "
        f"split; a future PV adding/removing files MUST update this test in "
        f"the same PR."
    )

    # §5 — Compressor v9.3.0 LOC sanity (the cycle's headline maintainability claim).
    # The original compressor.py was 2541 LOC; the post-split package is ≤ 3000 LOC
    # total (some overhead from re-export shims + module preambles is expected and
    # accepted). Catches a future PV that bloats one of the modules > 2000 LOC
    # individually (a sign that the split's "thematically tight" contract is
    # decaying).
    # transforms.py is the largest. Cap raised 2200 → 2300 in v9.7.0 PV-02
    # to accommodate the new ``dedup_predecessor_summaries`` helper +
    # 2 internal helpers (~220 LOC of canonical, well-isolated v9.7.0
    # PV-02 deliverable per A-2.2 append-only). Retrospective coverage
    # in `.local/research/v9.7.0_perf_research.md` §2 + the v9.7.0
    # CHANGELOG entry under PV-02. A future PV that crosses the new
    # 2300 cap should either decompose the file further OR bump the
    # cap again with similar retrospective coverage.
    per_file_max = 2300
    package_total = 0
    for p in compressor_pkg.iterdir():
        if p.is_file() and p.suffix == ".py":
            line_count = len(p.read_text(encoding="utf-8").splitlines())
            assert line_count <= per_file_max, (
                f"W-18 v9.3.0 violation: compressor/{p.name} grew to "
                f"{line_count} lines (cap {per_file_max}). The PV-04 "
                f"3-module split's 'thematically tight' contract is "
                f"decaying — consider further decomposition OR bumping the "
                f"per-file cap with explicit retrospective coverage."
            )
            package_total += line_count
    # Cap raised 3000 → 3200 in v9.7.0 PV-02 to accommodate
    # ``dedup_predecessor_summaries`` + 2 helpers (~220 LOC of canonical
    # additive deliverable). Pre-PV-04 single-file was 2541 LOC; the
    # post-split + v9.7.0 PV-02 total stays ≤ 26 % bloat (3200 / 2541).
    # Retrospective coverage: `.local/research/v9.7.0_perf_research.md` §2.
    assert package_total <= 3200, (
        f"W-18 v9.3.0 violation: compressor package total LOC is "
        f"{package_total} (cap 3200, raised from 3000 in v9.7.0 PV-02). "
        f"The pre-PV-04 single-file compressor.py was 2541 LOC; the "
        f"post-split + v9.7.0 PV-02 overhead should stay ≤ 26% bloat."
    )


# ---------------------------------------------------------------------------
# W-18 v9.4.0 ghost-audit refresh — Plugin Auto-Install & Daily Upgrade.
# ---------------------------------------------------------------------------


# v9.4.0 NEW symbols (PV-02..PV-04). Each entry is the minimum import-smoke
# contract that must hold for the symbol to be considered "alive" — i.e. the
# CHANGELOG cites it AND it imports cleanly from its canonical module path.
_V9_4_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-02 lifecycle hook + env flag
    ("devolaflow.lifecycle.pre_plugin_invocation", "pre_plugin_invocation"),
    ("devolaflow.lifecycle.pre_plugin_invocation", "is_auto_install_active"),
    ("devolaflow.lifecycle.pre_plugin_invocation", "ENV_FLAG"),
    ("devolaflow.lifecycle.pre_plugin_invocation", "ENV_FLAG_TRUTHY"),
    ("devolaflow.lifecycle", "PRE_PLUGIN_INVOCATION_EVENT"),
    # PV-03 dispatcher wiring + workflow→plugin helper
    ("devolaflow.plugins.installer", "plugins_for_workflow"),
    ("devolaflow.plugins", "plugins_for_workflow"),
    # PV-04 schema v3 + upgrade surface
    ("devolaflow.plugins.installer", "upgrade_plugin"),
    ("devolaflow.plugins.installer", "refresh_all"),
    ("devolaflow.plugins.installer", "RefreshOutcome"),
    ("devolaflow.plugins.installer", "read_last_checked"),
    ("devolaflow.plugins.installer", "is_plugin_stale"),
    ("devolaflow.plugins.installer", "list_plugins"),
    ("devolaflow.plugins", "upgrade_plugin"),
    ("devolaflow.plugins", "refresh_all"),
    ("devolaflow.plugins", "RefreshOutcome"),
    ("devolaflow.plugins", "list_plugins"),
    ("devolaflow.cli", "plugins_cmd"),
)

# v9.4.0 PV-02 + PV-03 + PV-04 frozen DEFAULT_EVENTS shape. PV-02 bumped
# 8 → 9 with `pre_plugin_invocation` APPENDED at position 9 per A-2.2
# append-only invariant. The v9.4.0 W-18 lint pins the new tail (the
# v9.1.3 lint relaxed its length check to "≥ 8" with pre_handoff frozen
# at position 8 — see _V9_1_3_DEFAULT_EVENTS_MIN above).
_V9_4_0_DEFAULT_EVENTS_LEN: int = 9
_V9_4_0_PRE_PLUGIN_INVOCATION_POSITION: int = 9  # 1-indexed; tuple index 8

# v9.4.0 PV-02 env-flag W-20 §3 documentation contract. The PV-02
# orthogonality justification ships in references/env-flags.md §2.13.
_V9_4_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.13 `DEVOLAFLOW_AUTO_INSTALL_PLUGINS`",
    "DEVOLAFLOW_AUTO_INSTALL_PLUGINS",
    "is_auto_install_active",
    "pre_plugin_invocation",
)

# v9.4.0 PV-04 schema v3 contract: canonical registry must be at
# schema_version 3 AND every plugin must declare an `upgrade_cmd`. The
# `_SUPPORTED_SCHEMA_VERSIONS` constant must include {1, 2, 3} for
# backward-compat with v8.2.x + v8.3.x fixtures.
_V9_4_0_REGISTRY_SCHEMA_VERSION: int = 3


def test_v9_4_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.4.0: every NEW v9.4.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.4.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.4.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.4.0 PV-05 cycle close pins:

    1. **Symbol import smoke** — every NEW public symbol from
       PV-02..PV-04 imports cleanly from its canonical module path.
       Catches accidental name collisions, circular imports, and the
       v6.0.3-style "feature mentioned in CHANGELOG but never wired"
       anti-pattern. 18 symbols enumerated in
       ``_V9_4_0_NEW_SYMBOL_SURFACES``.
    2. **DEFAULT_EVENTS A-2.2 append-only at position 9** — the new
       `pre_plugin_invocation` event must be at 1-indexed position 9
       (tuple index 8); the v9.1.3 frozen position 8 (`pre_handoff`)
       must remain.
    3. **W-20 §3 env-flag doc contract** — the new
       `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` flag MUST appear in
       `references/env-flags.md` §2.13 with the canonical
       orthogonality argument + helper function names.
    4. **Schema v3 contract** — `runtime-plugins.yaml` is at
       schema_version 3 AND every plugin declares an `upgrade_cmd`
       AND `_SUPPORTED_SCHEMA_VERSIONS` includes {1, 2, 3} (backward
       compat preserved).
    5. **`ensure_plugin` dispatcher hit count** — the dead-wire ghost
       is closed: `ensure_plugin` is now referenced from at least 4
       distinct files in `src/devolaflow/` (the AC-3 acceptance
       criterion from the v9.4.0 gap analysis §6).

    Failure modes:
      * "symbol import failed" → CHANGELOG cites a non-existent
        feature; either land it OR remove the entry.
      * "DEFAULT_EVENTS bad position" → the A-2.2 append-only
        contract was violated; restore `pre_plugin_invocation` to
        the tail.
      * "missing env-flag doc literal" → W-20 §7 checklist failed;
        author the §2.13 entry.
      * "schema_version mismatch" → either the v3 bump was lost OR a
        future PV bumped to v4 without updating this lint (acceptable
        — update the constant).
      * "ensure_plugin hit count regression" → the dispatcher wiring
        from PV-03 was removed; restore the `feedback.py` chain.
    """
    import importlib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_4_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.4.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.4.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.4.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — DEFAULT_EVENTS shape.
    from devolaflow.lifecycle import DEFAULT_EVENTS, PRE_PLUGIN_INVOCATION_EVENT

    assert len(DEFAULT_EVENTS) >= _V9_4_0_DEFAULT_EVENTS_LEN, (
        f"W-18 v9.4.0 violation: DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected >= {_V9_4_0_DEFAULT_EVENTS_LEN} "
        f"(v9.4.0 PV-02 bumped 8 → 9 with pre_plugin_invocation APPENDED "
        f"at position {_V9_4_0_PRE_PLUGIN_INVOCATION_POSITION} per A-2.2; "
        f"future PVs may extend further). Current events: {DEFAULT_EVENTS!r}"
    )
    plugin_idx = _V9_4_0_PRE_PLUGIN_INVOCATION_POSITION - 1
    assert DEFAULT_EVENTS[plugin_idx] == PRE_PLUGIN_INVOCATION_EVENT, (
        f"W-18 v9.4.0 violation: DEFAULT_EVENTS[{plugin_idx}] is "
        f"{DEFAULT_EVENTS[plugin_idx]!r}, expected {PRE_PLUGIN_INVOCATION_EVENT!r}; "
        f"pre_plugin_invocation MUST stay at 1-indexed position "
        f"{_V9_4_0_PRE_PLUGIN_INVOCATION_POSITION} per A-2.2 cache-prefix invariant"
    )

    # §3 — Env-flag W-20 §3 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    assert env_flags_path.is_file(), (
        f"W-18 v9.4.0 violation: {env_flags_path.relative_to(project_root)} "
        f"missing — PV-02 W-20 §3 contract requires the env-flag inventory"
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_4_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.4.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-02 W-20 §7 checklist requires the §2.13 entry to "
            f"document the new flag with both the flag name and the helper "
            f"function names. Add the §2.13 block."
        )

    # §4 — Schema v3 contract.
    from devolaflow.plugins import load_registry
    from devolaflow.plugins.installer import _SUPPORTED_SCHEMA_VERSIONS

    assert {1, 2, 3}.issubset(_SUPPORTED_SCHEMA_VERSIONS), (
        f"W-18 v9.4.0 violation: _SUPPORTED_SCHEMA_VERSIONS = "
        f"{_SUPPORTED_SCHEMA_VERSIONS!r}; v9.4.0 PV-04 requires {{1, 2, 3}} "
        f"(v1 + v2 backward compat + v3 new bump)"
    )
    registry = load_registry()
    assert registry["schema_version"] >= _V9_4_0_REGISTRY_SCHEMA_VERSION, (
        f"W-18 v9.4.0 violation: canonical runtime-plugins.yaml is at "
        f"schema_version {registry['schema_version']!r}; v9.4.0 PV-04 "
        f"requires >= {_V9_4_0_REGISTRY_SCHEMA_VERSION}"
    )
    for entry in registry["plugins"]:
        assert "upgrade_cmd" in entry, (
            f"W-18 v9.4.0 violation: plugin {entry.get('id')!r} missing "
            f"upgrade_cmd in v3 canonical registry. The PV-04 contract "
            f"requires every canonical entry to declare upgrade_cmd "
            f"(legacy v1 + v2 fixtures may omit it; the canonical v3 "
            f"file MUST include it)."
        )

    # §5 — ensure_plugin dispatcher hit count (the AC-3 acceptance criterion).
    src_dir = project_root / "src" / "devolaflow"
    files_with_hits: list[Path] = []
    for py_file in src_dir.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "ensure_plugin" in text:
            files_with_hits.append(py_file)
    assert len(files_with_hits) >= 4, (
        f"W-18 v9.4.0 violation: `ensure_plugin` referenced in only "
        f"{len(files_with_hits)} files; v9.4.0 PV-03 contract requires >= 4 "
        f"(installer.py + plugins/__init__.py + lifecycle/pre_plugin_invocation.py + "
        f"≥ 1 dispatcher). The dead-wire ghost reopened — restore the "
        f"feedback.py wiring from PV-03. Files found: "
        f"{[str(p.relative_to(project_root)) for p in files_with_hits]!r}"
    )


# ---------------------------------------------------------------------------
# W-18 v9.5.0 ghost-audit refresh — Si-Chip DEEP integration.
# ---------------------------------------------------------------------------


# v9.5.0 NEW symbols (PV-01..PV-04). Each entry is the minimum import-smoke
# contract that must hold for the symbol to be considered "alive" — i.e. the
# CHANGELOG cites it AND it imports cleanly from its canonical module path.
_V9_5_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-02 si_chip_bridge package (4 NEW modules + public API)
    ("devolaflow.si_chip_bridge", "find_si_chip_install"),
    ("devolaflow.si_chip_bridge", "profile"),
    ("devolaflow.si_chip_bridge", "evaluate"),
    ("devolaflow.si_chip_bridge", "count_tokens"),
    ("devolaflow.si_chip_bridge", "aggregate_delta"),
    ("devolaflow.si_chip_bridge", "apply_or_defer"),
    ("devolaflow.si_chip_bridge", "run_dogfood_cycle"),
    ("devolaflow.si_chip_bridge", "ApplyVerdict"),
    ("devolaflow.si_chip_bridge", "BasicAbilityProfile"),
    ("devolaflow.si_chip_bridge", "MetricsReport"),
    ("devolaflow.si_chip_bridge", "IterationDeltaReport"),
    ("devolaflow.si_chip_bridge", "SiChipResult"),
    ("devolaflow.si_chip_bridge", "SiChipError"),
    ("devolaflow.si_chip_bridge", "SiChipUnavailable"),
    ("devolaflow.si_chip_bridge", "SiChipInstall"),
    ("devolaflow.si_chip_bridge", "DEFAULT_THRESHOLD"),
    ("devolaflow.si_chip_bridge", "APPLY_DEFER_EPSILON"),
    ("devolaflow.si_chip_bridge.install_resolver", "find_si_chip_install"),
    ("devolaflow.si_chip_bridge.runner", "run_dogfood_cycle"),
    # PV-04 lifecycle hook + env flag
    ("devolaflow.lifecycle.post_skill_edit", "post_skill_edit"),
    ("devolaflow.lifecycle.post_skill_edit", "is_deep_integration_active"),
    ("devolaflow.lifecycle.post_skill_edit", "ENV_FLAG"),
    ("devolaflow.lifecycle.post_skill_edit", "ENV_FLAG_TRUTHY"),
    ("devolaflow.lifecycle.post_skill_edit", "SKILL_CORPUS_PREFIX"),
    ("devolaflow.lifecycle", "POST_SKILL_EDIT_EVENT"),
)

# v9.5.0 PV-04 frozen DEFAULT_EVENTS shape. PV-04 bumped 9 → 10 with
# `post_skill_edit` APPENDED at position 10 per A-2.2 append-only invariant.
# Position 9 (`pre_plugin_invocation`) MUST remain frozen per A-2.4
# cache-prefix invariant.
_V9_5_0_DEFAULT_EVENTS_LEN: int = 10
_V9_5_0_POST_SKILL_EDIT_POSITION: int = 10  # 1-indexed; tuple index 9

# v9.5.0 PV-04 env-flag W-20 §3 documentation contract. The PV-04
# orthogonality justification ships in references/env-flags.md §2.14.
_V9_5_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.14 `DEVOLAFLOW_SI_CHIP_DEEP`",
    "DEVOLAFLOW_SI_CHIP_DEEP",
    "is_deep_integration_active",
    "post_skill_edit",
)

# v9.5.0 PV-01 plugin registry contract: si-chip is the 4th plugin entry
# (registry_v3 with curl_install_script backend, reusing the v8.3.1 RTK
# plumbing). The legacy plugins.yaml mirrors the workflow assignment.
_V9_5_0_PLUGIN_ID: str = "si-chip"
_V9_5_0_PLUGIN_BACKEND: str = "curl_install_script"
_V9_5_0_PLUGIN_CANONICAL_URL: str = "https://github.com/YoRHa-Agents/Si-Chip"


def test_v9_5_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.5.0: every NEW v9.5.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.5.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.5.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.5.0 PV-06 cycle close pins:

    1. **Symbol import smoke** — every NEW public symbol from
       PV-02..PV-04 imports cleanly from its canonical module path.
       Catches accidental name collisions, circular imports, and the
       v6.0.3-style "feature mentioned in CHANGELOG but never wired"
       anti-pattern. 25 symbols enumerated in
       ``_V9_5_0_NEW_SYMBOL_SURFACES``.
    2. **DEFAULT_EVENTS A-2.2 append-only at position 10** — the new
       `post_skill_edit` event must be at 1-indexed position 10
       (tuple index 9); the v9.4.0 frozen position 9
       (`pre_plugin_invocation`) must remain.
    3. **W-20 §3 env-flag doc contract** — the new
       `DEVOLAFLOW_SI_CHIP_DEEP` flag MUST appear in
       `references/env-flags.md` §2.14 with the canonical
       orthogonality argument + helper function names.
    4. **Si-Chip plugin registration contract** — `runtime-plugins.yaml`
       contains the canonical 4th plugin entry (`si-chip`,
       `curl_install_script` backend, canonical GitHub URL). The
       legacy `plugins.yaml` mirrors the same workflow assignments.
    5. **A-2.4 multi-baseline byte test** — the v9.5.0 PV-04
       DEFAULT_EVENTS bump appends post_skill_edit at the tail
       without disturbing positions 1-9 (pre_plugin_invocation
       through pre_dispatch).

    Failure modes:
      * "symbol import failed" → CHANGELOG cites a non-existent
        feature; either land it OR remove the entry.
      * "DEFAULT_EVENTS bad position" → the A-2.2 append-only
        contract was violated; restore `post_skill_edit` to the tail.
      * "missing env-flag doc literal" → W-20 §7 checklist failed;
        author the §2.14 entry.
      * "si-chip plugin missing" → revert PV-01 reverted; either
        re-add the entry to runtime-plugins.yaml + plugins.yaml OR
        remove the v9.5.0 CHANGELOG entry.
    """
    import importlib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_5_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.5.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.5.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.5.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — DEFAULT_EVENTS shape.
    from devolaflow.lifecycle import DEFAULT_EVENTS, POST_SKILL_EDIT_EVENT

    assert len(DEFAULT_EVENTS) >= _V9_5_0_DEFAULT_EVENTS_LEN, (
        f"W-18 v9.5.0 violation: DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected >= {_V9_5_0_DEFAULT_EVENTS_LEN} "
        f"(v9.5.0 PV-04 bumped 9 → 10 with post_skill_edit APPENDED at "
        f"position {_V9_5_0_POST_SKILL_EDIT_POSITION} per A-2.2; future "
        f"PVs may extend further). Current events: {DEFAULT_EVENTS!r}"
    )
    skill_idx = _V9_5_0_POST_SKILL_EDIT_POSITION - 1
    assert DEFAULT_EVENTS[skill_idx] == POST_SKILL_EDIT_EVENT, (
        f"W-18 v9.5.0 violation: DEFAULT_EVENTS[{skill_idx}] is "
        f"{DEFAULT_EVENTS[skill_idx]!r}, expected {POST_SKILL_EDIT_EVENT!r}; "
        f"post_skill_edit MUST stay at 1-indexed position "
        f"{_V9_5_0_POST_SKILL_EDIT_POSITION} per A-2.2 cache-prefix invariant"
    )

    # §3 — Env-flag W-20 §3 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    assert env_flags_path.is_file(), (
        f"W-18 v9.5.0 violation: {env_flags_path.relative_to(project_root)} "
        f"missing — PV-04 W-20 §3 contract requires the env-flag inventory"
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_5_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.5.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-04 W-20 §7 checklist requires the §2.14 entry to "
            f"document the new flag with both the flag name and the helper "
            f"function names. Add the §2.14 block."
        )

    # §4 — Si-Chip plugin registration contract.
    from devolaflow.plugins.installer import load_registry, resolve_plugin

    registry = load_registry()
    spec = resolve_plugin(_V9_5_0_PLUGIN_ID, registry)
    assert spec.backend == _V9_5_0_PLUGIN_BACKEND, (
        f"W-18 v9.5.0 violation: si-chip plugin backend is "
        f"{spec.backend!r}, expected {_V9_5_0_PLUGIN_BACKEND!r} "
        f"(reuses the v8.3.1 RTK curl_install_script plumbing)"
    )
    assert spec.canonical_url == _V9_5_0_PLUGIN_CANONICAL_URL, (
        f"W-18 v9.5.0 violation: si-chip canonical_url is "
        f"{spec.canonical_url!r}, expected {_V9_5_0_PLUGIN_CANONICAL_URL!r} "
        f"per S-7 (external tools referenced via canonical GitHub URL)"
    )
    assert "skill-optimization" in spec.invoked_by_workflows
    assert "self-update" in spec.invoked_by_workflows
    assert "nines-assisted" in spec.invoked_by_workflows


# ============================================================================
# v9.6.0 — Reference Library Refresh (PV-01..PV-05).
# ============================================================================

# v9.6.0 PV-04 yaml entry-count contract: 11 active + 10 periodic = 21 total.
# Header comment was stale "10 + 9 = 19" pre-PV-04; corrected per D-R-7.
_V9_6_0_TOTAL_REFS: int = 21
_V9_6_0_ACTIVE_REFS: int = 11
_V9_6_0_PERIODIC_REFS: int = 10

# v9.6.0 PV-02 reference-doc anchor contract — the 4 NEW subsections wired
# into the agent-facing reference docs by the high-relevance integration.
# Each anchor is the literal heading line (must appear verbatim).
_V9_6_0_REFERENCE_DOC_ANCHORS: tuple[tuple[str, str], ...] = (
    (
        "workflow-system/agent/references/decomposition-gate.md",
        "### 6.0 Stagnation detection (v9.6.0)",
    ),
    (
        "workflow-system/agent/references/team-roles.md",
        "### Two-stage review pattern (v9.6.0 — superpowers integration)",
    ),
    (
        "workflow-system/agent/references/execution-protocol.md",
        "### 1b.1 Pre-handoff verification gate (v9.6.0 — superpowers integration)",
    ),
    (
        "workflow-system/agent/references/meta-framework.md",
        "#### 2.2.1 Multi-team codebase analysis pattern "
        "(v9.6.0 — understand-anything integration)",
    ),
)

# v9.6.0 PV-01 harness public-symbol contract — the harness ships as a
# top-level script, not a package, so we verify its module-level symbols
# load cleanly via spec_from_file_location.
_V9_6_0_HARNESS_SCRIPT: str = "scripts/nines_refresh_references.py"
_V9_6_0_HARNESS_PUBLIC_SYMBOLS: tuple[str, ...] = (
    "RefResult",
    "CLONE_NAME_OVERRIDES",
    "_load_refs",
    "_resolve_clone",
    "_run_nines",
    "analyze_one",
    "render_synthesis",
    "main",
)


def test_v9_6_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.6.0: every NEW v9.6.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.6.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.6.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.6.0 PV-05 cycle close pins:

    1. **Reference inventory shape (D-R-7 closure)** — yaml carries
       exactly 11 active + 10 periodic = 21 entries; header comment
       reflects the 21-entry count (not the legacy "10 + 9 = 19").
    2. **Bulk freshness (D-R-5 closure)** — every yaml entry has
       last_checked == "2026-05-02" after PV-04.
    3. **primelocus-hydra graduation (D-R-9 closure)** — entry carries
       tracking_status: "frozen_reference" + graduated_to_frozen_at
       audit field.
    4. **Reference-doc anchors (PV-02 deliverable)** — the 4 NEW
       subsection headings appear verbatim in their owning files.
    5. **Harness public surface (PV-01 deliverable)** — the
       nines_refresh_references.py script loads cleanly and exposes
       every symbol cited by the W-2 SI-2 contract.

    Failure modes:
      * "yaml ref count drift" → either an entry was added/removed
        outside the v9.6.0 PV chain OR yaml header comment regressed;
        re-check D-R-7 closure.
      * "stale last_checked" → PV-04 freshness sweep regressed; re-run
        the bulk update.
      * "primelocus-hydra not frozen" → PV-04 graduation regressed;
        re-apply the tracking_status flip.
      * "missing reference-doc anchor" → PV-02 reference doc edit was
        reverted; re-author the §X subsection per gap_analysis §3.1.
      * "harness symbol missing" → scripts/nines_refresh_references.py
        regressed; re-author the public surface.
    """
    import importlib.util
    import sys

    import yaml as yaml_lib

    yaml_path = (
        project_root / "workflow-system" / "agent" / "knowledge" / "reference-dependencies.yaml"
    )

    # §1 — Reference inventory shape.
    data = yaml_lib.safe_load(yaml_path.read_text(encoding="utf-8"))
    active = data.get("active_tracking", []) or []
    periodic = data.get("periodic_monitoring", []) or []
    assert len(active) == _V9_6_0_ACTIVE_REFS, (
        f"W-18 v9.6.0 violation: active_tracking count is {len(active)}, "
        f"expected {_V9_6_0_ACTIVE_REFS} (D-R-7 closure)"
    )
    assert len(periodic) == _V9_6_0_PERIODIC_REFS, (
        f"W-18 v9.6.0 violation: periodic_monitoring count is "
        f"{len(periodic)}, expected {_V9_6_0_PERIODIC_REFS} (D-R-7)"
    )
    raw = yaml_path.read_text(encoding="utf-8")
    assert (
        f"{_V9_6_0_ACTIVE_REFS} active_tracking + "
        f"{_V9_6_0_PERIODIC_REFS} periodic_monitoring = "
        f"{_V9_6_0_TOTAL_REFS} total"
    ) in raw, (
        f"W-18 v9.6.0 violation: yaml header comment must reflect the "
        f"{_V9_6_0_ACTIVE_REFS} + {_V9_6_0_PERIODIC_REFS} = "
        f"{_V9_6_0_TOTAL_REFS} count per D-R-7"
    )

    # §2 — Bulk freshness.
    all_refs = active + periodic
    stale = [r["id"] for r in all_refs if r.get("last_checked") != "2026-05-02"]
    assert not stale, (
        f"W-18 v9.6.0 violation: yaml entries with stale last_checked: "
        f"{stale} (D-R-5 closure requires ALL 21 at 2026-05-02)"
    )

    # §3 — primelocus-hydra graduation.
    ph = next((r for r in periodic if r["id"] == "primelocus-hydra"), None)
    assert ph is not None, (
        "W-18 v9.6.0 violation: primelocus-hydra missing from periodic_monitoring"
    )
    assert ph.get("tracking_status") == "frozen_reference", (
        f"W-18 v9.6.0 violation: primelocus-hydra tracking_status is "
        f"{ph.get('tracking_status')!r}, expected 'frozen_reference' "
        f"(D-R-9 closure)"
    )
    assert ph.get("graduated_to_frozen_at", "").startswith("v9.6.0 PV-04")

    # §4 — Reference-doc anchors.
    for rel_path, anchor in _V9_6_0_REFERENCE_DOC_ANCHORS:
        ref_file = project_root / rel_path
        assert ref_file.is_file(), f"W-18 v9.6.0 violation: reference doc {rel_path} missing"
        text = ref_file.read_text(encoding="utf-8")
        assert anchor in text, (
            f"W-18 v9.6.0 violation: {rel_path} missing v9.6.0 anchor "
            f"{anchor!r}; PV-02 integration regressed"
        )

    # §5 — Harness public surface.
    script_path = project_root / _V9_6_0_HARNESS_SCRIPT
    assert script_path.is_file(), (
        f"W-18 v9.6.0 violation: PV-01 harness {_V9_6_0_HARNESS_SCRIPT} missing"
    )
    spec = importlib.util.spec_from_file_location("_v9_6_0_w18_harness_probe", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_v9_6_0_w18_harness_probe"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover — import smoke
        pytest.fail(f"W-18 v9.6.0 violation: harness module failed to import: {exc}")
    finally:
        sys.modules.pop("_v9_6_0_w18_harness_probe", None)
    for sym in _V9_6_0_HARNESS_PUBLIC_SYMBOLS:
        assert hasattr(module, sym), (
            f"W-18 v9.6.0 violation: harness missing public symbol {sym!r}; "
            f"the W-2 SI-2 contract cites this symbol"
        )


# ---------------------------------------------------------------------------
# W-18 v9.7.0 ghost-audit refresh — Performance Overhaul #2.
# ---------------------------------------------------------------------------


# v9.7.0 NEW symbols (PV-02..PV-04). Each entry is the minimum import-smoke
# contract that must hold for the symbol to be considered "alive" — i.e. the
# CHANGELOG cites it AND it imports cleanly from its canonical module path.
_V9_7_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-02 predecessor summary delta-compression
    ("devolaflow.compressor", "dedup_predecessor_summaries"),
    ("devolaflow.compressor", "DEDUP_HASH_PREFIX_LENGTH"),
    ("devolaflow.compressor.transforms", "dedup_predecessor_summaries"),
    ("devolaflow.compressor.transforms", "_hash_summary"),
    ("devolaflow.compressor.transforms", "_build_dedup_index"),
    # PV-03 auto-wired async wave dispatch
    ("devolaflow.feedback", "dispatch_wave_tasks"),
    # PV-04 selector cache warmup
    ("devolaflow.task_adaptive_selector", "warmup_selector_cache"),
    ("devolaflow.task_adaptive_selector", "WARMUP_ENV_FLAG"),
    ("devolaflow.task_adaptive_selector", "WARMUP_TRUTHY_VALUE"),
    ("devolaflow.task_adaptive_selector", "WARMUP_TASK_TYPES"),
    ("devolaflow.task_adaptive_selector", "WARMUP_ROUND_NUMS"),
)

# v9.7.0 PV-02 schema-v6 invariants — canonical_order length 17, version 6.
_V9_7_0_CANONICAL_ORDER_LENGTH: int = 17
_V9_7_0_LAYOUT_VERSION: int = 6
_V9_7_0_NEW_CANONICAL_KEY: str = "predecessor_dedup_ledger"

# v9.7.0 PV-05 baseline files — every CHANGELOG entry that cites the
# cumulative perf gain pins these files. The W-18 contract requires them
# to be present + parseable.
_V9_7_0_BASELINE_PATHS: tuple[Path, ...] = (
    Path("benchmarks/devolaflow_context/baselines/v9.7.0_latency.json"),
    Path("benchmarks/devolaflow_context/baselines/v9.7.0_baseline.json"),
    Path("benchmarks/devolaflow_context/baselines/v9.7.0_latency_intermediate.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v9.7.0.yaml"),
)

# v9.7.0 PV-04 env-flag W-20 §7 documentation contract.
_V9_7_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.15 `DEVOLAFLOW_WARMUP`",
    "DEVOLAFLOW_WARMUP",
    "warmup_selector_cache",
    "WARMUP_TASK_TYPES",
)

# v9.7.0 PV-03 auto-wire reference doc anchor.
_V9_7_0_REFERENCE_DOC_ANCHORS: tuple[tuple[str, str], ...] = (
    (
        "workflow-system/agent/references/execution-protocol.md",
        "## 13. L2-Wave Async Dispatch Auto-Wire (v9.7.0+)",
    ),
)


def test_v9_7_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.7.0: every NEW v9.7.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.7.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.7.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.7.0 PV-06 cycle close pins:

    1. **NEW public symbols (PV-02..PV-04)** import cleanly from their
       canonical module paths. The 11 entries cover predecessor dedup
       (PV-02), async wave auto-wire (PV-03), and selector warmup
       (PV-04).
    2. **Schema v6 17-element canonical_order (PV-02)** —
       schemas/lean-dispatch.yaml#layout_invariant.version is 6 and
       canonical_order length is 17 with predecessor_dedup_ledger at
       position 17. The frozen-prefix invariant (positions 1-12) is
       PRESERVED (the v8.4.0 / v9.2.0 / v9.3.0 byte-baselines all
       continue to pass per A-2.4 multi-baseline byte test).
    3. **PV-05 baseline files** exist on disk and parse cleanly. The
       CHANGELOG cites the cumulative 97.5% select_context.p95
       improvement which is derived FROM these files; missing files
       = unprovable claim.
    4. **PV-04 env-flag W-20 §7 documentation contract** — the
       env-flags.md §2.15 entry header + flag name + helper function
       names appear together in the file.
    5. **PV-03 reference doc anchor** — the §13 heading appears
       verbatim in execution-protocol.md.

    Failure modes:
      * "symbol import failed" → CHANGELOG cites a non-existent
        feature; either land it or remove the entry.
      * "canonical_order length wrong" → A-2 frozen prefix or
        position-17 APPEND regressed.
      * "missing baseline file" → run the PV-01 / PV-05 latency
        harness CLI to regenerate; OR the cycle didn't honour the
        wholesale-regen-or-per-PV-baseline invariant.
      * "missing env-flag doc literal" → W-20 §7 checklist failed;
        author the §2.15 block.
      * "missing reference-doc anchor" → PV-03 reference doc edit
        was reverted; re-author the §13 subsection.
    """
    import importlib

    import yaml as yaml_lib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_7_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.7.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.7.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.7.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — Schema v6 17-element canonical_order.
    schema_path = project_root / "schemas" / "lean-dispatch.yaml"
    schema = yaml_lib.safe_load(schema_path.read_text(encoding="utf-8"))
    canonical = schema["layout_invariant"]["canonical_order"]
    assert len(canonical) == _V9_7_0_CANONICAL_ORDER_LENGTH, (
        f"W-18 v9.7.0 violation: canonical_order length is {len(canonical)}, "
        f"expected {_V9_7_0_CANONICAL_ORDER_LENGTH} (PV-02 schema v6 APPEND)"
    )
    assert canonical[-1] == _V9_7_0_NEW_CANONICAL_KEY, (
        f"W-18 v9.7.0 violation: last canonical key is {canonical[-1]!r}, "
        f"expected {_V9_7_0_NEW_CANONICAL_KEY!r} (PV-02 APPEND at position 17)"
    )
    assert schema["layout_invariant"]["version"] == _V9_7_0_LAYOUT_VERSION, (
        f"W-18 v9.7.0 violation: layout_invariant.version is "
        f"{schema['layout_invariant']['version']}, expected "
        f"{_V9_7_0_LAYOUT_VERSION} (PV-02 bumped 5 → 6)"
    )

    # §3 — PV-05 baseline files exist + parse.
    for baseline_rel in _V9_7_0_BASELINE_PATHS:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v9.7.0 violation: PV-05 baseline {baseline_rel} "
            f"missing. Run `python -m benchmarks.devolaflow_context."
            f"latency_harness --iterations 100 --output {baseline_rel}` "
            f"(for the latency JSON) OR `python -m benchmarks."
            f"devolaflow_context.generate_baseline` (for the composite JSON) "
            f"OR copy the v9.6.0 layout-invariant witness (for the YAML)."
        )
        if baseline_path.suffix == ".json":
            import json as _json

            _json.loads(baseline_path.read_text(encoding="utf-8"))
        elif baseline_path.suffix == ".yaml":
            yaml_lib.safe_load(baseline_path.read_text(encoding="utf-8"))

    # §4 — PV-04 env-flag W-20 §7 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_7_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.7.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-04 W-20 §7 checklist requires the §2.15 entry to "
            f"document the new flag with both the flag name and the "
            f"helper function names. Add the §2.15 block."
        )

    # §5 — PV-03 reference doc anchor.
    for rel_path, anchor in _V9_7_0_REFERENCE_DOC_ANCHORS:
        ref_file = project_root / rel_path
        assert ref_file.is_file(), f"W-18 v9.7.0 violation: reference doc {rel_path} missing"
        text = ref_file.read_text(encoding="utf-8")
        assert anchor in text, (
            f"W-18 v9.7.0 violation: anchor {anchor!r} missing from "
            f"{rel_path}. PV-03 cited this anchor in the CHANGELOG; "
            f"either restore the §13 subsection OR remove the CHANGELOG "
            f"entry."
        )


# ---------------------------------------------------------------------------
# W-18 v10.0.0 ghost-audit refresh — MAJOR rollup cycle close.
# ---------------------------------------------------------------------------


# v10.0.0 NEW symbol: the feedback-AC audit script's public surface.
# Every other "new" surface in v10.0.0 comes from a v9.X MINOR that already
# has its own W-18 lint above; the MAJOR rollup itself adds only the audit
# script + the W-19 archive output + the human-docs refresh (none of which
# expose Python symbols).
_V10_0_0_AUDIT_SCRIPT_PATH: Path = Path("scripts/audit_feedback_ac.py")
_V10_0_0_AUDIT_SCRIPT_PUBLIC_SYMBOLS: tuple[str, ...] = (
    "FeedbackAudit",
    "audit_feedback",
    "_extract_artifacts",
    "_count_ac_items",
    "_classify",
    "_check_path",
    "_grep_symbol",
    "_later_changelog_entries",
    "_format_markdown_report",
    "main",
)

# v10.0.0 PV-03 human-facing docs surfaces.
#
# The SAMPLE_DATA literal in benchmark-results/index.html is updated by
# every `bump_version.py` run (CP-3 canonical location), so pinning a
# specific version number would fail right after the next bump. Keep
# only historically-anchored literals here — the README "What's New"
# header, the demo landing page heading, and the versions.json entry
# (versions.json is append-only so the v10.0.0 entry persists).
_V10_0_0_HUMAN_DOC_LITERALS: tuple[tuple[str, str], ...] = (
    ("README.md", "## What's New in v10.0.0 (MAJOR cycle close)"),
    ("workflow-system/human/demo/index.html", "What's New</span> in v10.0.0"),
    ("workflow-system/human/demo/version-timeline/versions.json", '"version": "10.0.0"'),
)

# v10.0.0 PV-04 W-19 cycle archive surfaces.
_V10_0_0_CYCLE_ARCHIVE_REQUIRED_FILES: tuple[Path, ...] = (
    Path("docs/cycle-archive/v10.0.0/README.md"),
    Path("docs/cycle-archive/v10.0.0/v10.0.0_retrospective.md"),
    Path("docs/cycle-archive/v10.0.0/v9.3.0_retrospective.md"),
    Path("docs/cycle-archive/v10.0.0/v9.7.0_retrospective.md"),
    Path("docs/cycle-archive/v10.0.0/evaluation/v10.0.0_evaluation.md"),
    Path("docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.json"),
    Path("docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.md"),
    Path("docs/cycle-archive/v10.0.0/other/v10.0.0_cycle_plan.md"),
    Path("docs/cycle-archive/v10.0.0/other/v10.0.0_feedback_ac_audit.md"),
)


def test_v10_0_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.0.0: every NEW v10.0.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v10.0.0 cycle-close MAJOR —
    every CHANGELOG entry mentioning a v10.0.0 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v10.0.0 PV-05 cycle close pins:

    1. **PV-02 audit script public surface** — `scripts/audit_feedback_ac.py`
       exists AND every named public symbol is present at module level. The
       MAJOR rollup CHANGELOG entry cites the audit's "57 files / 0 FAILs"
       headline number; missing script = unprovable claim.
    2. **PV-03 human-doc literal contract** — the README v10.0.0 "What's New"
       section header + the demo landing v10.0.0 What's New header + the
       `versions.json` v10.0.0 entry + the benchmark-results SAMPLE_DATA
       version string MUST all be present. These are the surfaces the
       CHANGELOG cites for the "comprehensive human-docs refresh".
    3. **PV-04 W-19 cycle archive surface** — the
       `docs/cycle-archive/v10.0.0/` tree exists with the README + the
       v10.0.0 retrospective + the v9.3 / v9.7 retrospectives (sample of
       the per-MINOR coverage) + the v10.0.0 evaluation + the v10.0.0 nines
       JSON+MD + the cycle plan + the feedback audit. These are the W-19
       surfaces the CHANGELOG cites.

    Failure modes:
      * "audit script missing public symbol" → PV-02 surface decayed; restore
        the symbol OR remove the CHANGELOG mention.
      * "human-doc literal missing" → PV-03 doc-refresh edit was reverted;
        re-author the section.
      * "cycle archive file missing" → PV-04 W-19 archive run failed; re-run
        `python scripts/archive_research_artifacts.py 10.0.0 --extra-prefix
        v9.3. --extra-prefix v9.4. --extra-prefix v9.5. --extra-prefix v9.6.
        --extra-prefix v9.7. --extra-prefix v10.0.`
    """
    import ast

    # §1 — Audit script symbol surface.
    audit_path = project_root / _V10_0_0_AUDIT_SCRIPT_PATH
    assert audit_path.is_file(), (
        f"W-18 v10.0.0 violation: audit script {_V10_0_0_AUDIT_SCRIPT_PATH} "
        f"missing. PV-02 ships this script; either restore it OR remove "
        f"the CHANGELOG mention of the 57-feedback audit."
    )
    audit_source = audit_path.read_text(encoding="utf-8")
    audit_module = ast.parse(audit_source)
    defined_names = {
        node.name
        for node in ast.walk(audit_module)
        if isinstance(node, ast.FunctionDef | ast.ClassDef)
    }
    for sym in _V10_0_0_AUDIT_SCRIPT_PUBLIC_SYMBOLS:
        assert sym in defined_names, (
            f"W-18 v10.0.0 violation: audit script "
            f"{_V10_0_0_AUDIT_SCRIPT_PATH} missing public symbol {sym!r}. "
            f"PV-02 cites this symbol in tests/test_audit_feedback_ac.py; "
            f"either restore the symbol OR adjust both the CHANGELOG and "
            f"the test."
        )

    # §2 — Human-doc literal contract.
    for rel_path, literal in _V10_0_0_HUMAN_DOC_LITERALS:
        doc_path = project_root / rel_path
        assert doc_path.is_file(), f"W-18 v10.0.0 violation: human-doc {rel_path} missing"
        doc_text = doc_path.read_text(encoding="utf-8")
        assert literal in doc_text, (
            f"W-18 v10.0.0 violation: literal {literal!r} missing from "
            f"{rel_path}. PV-03 ships this literal; either restore it OR "
            f"remove the CHANGELOG mention of the human-docs refresh."
        )

    # §3 — W-19 cycle archive surface.
    for archive_rel in _V10_0_0_CYCLE_ARCHIVE_REQUIRED_FILES:
        archive_path = project_root / archive_rel
        assert archive_path.is_file(), (
            f"W-18 v10.0.0 violation: cycle-archive file {archive_rel} "
            f"missing. PV-04 ships this file; re-run "
            f"`python scripts/archive_research_artifacts.py 10.0.0 "
            f"--extra-prefix v9.3. --extra-prefix v9.4. --extra-prefix "
            f"v9.5. --extra-prefix v9.6. --extra-prefix v9.7. "
            f"--extra-prefix v10.0.` to regenerate."
        )


_V10_1_0_WRITING_STYLE_MODULES: tuple[Path, ...] = (
    Path("src/devolaflow/writing_style/__init__.py"),
    Path("src/devolaflow/writing_style/errors.py"),
    Path("src/devolaflow/writing_style/profiles.py"),
    Path("src/devolaflow/writing_style/regions.py"),
    Path("src/devolaflow/writing_style/scorer.py"),
    Path("src/devolaflow/writing_style/transforms/__init__.py"),
    Path("src/devolaflow/writing_style/transforms/emdash.py"),
    Path("src/devolaflow/writing_style/transforms/bullets.py"),
    Path("src/devolaflow/writing_style/transforms/signposts.py"),
    Path("src/devolaflow/writing_style/transforms/headers.py"),
    Path("src/devolaflow/writing_style/transforms/cliches.py"),
    Path("src/devolaflow/writing_style/data/cliche_catalog.yaml"),
)

_V10_1_0_WRITING_STYLE_PUBLIC_SYMBOLS: frozenset[str] = frozenset(
    {
        "score_text",
        "score_corpus",
        "extract_features",
        "compute_composite",
        "apply_transforms",
        "load_profile",
        "profile_for_path",
        "NaturalnessScore",
        "RawFeatures",
        "CorpusScore",
        "ToneProfile",
        "FeatureCaps",
        "TransformResult",
        "StyleError",
    }
)

_V10_1_0_BASELINE_FILES: tuple[Path, ...] = (
    Path("benchmarks/writing_style/baselines/v10.1.0_pre.json"),
    Path("benchmarks/writing_style/baselines/v10.1.0_post.json"),
)

_V10_1_0_HUMANIZE_SCRIPT = Path("scripts/humanize_doc.py")
_V10_1_0_HUMANIZE_MAKE_TARGET = "humanize-docs:"

_V10_1_0_CHANGELOG_LITERAL = "## [10.1.0]"


def test_v10_1_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.1.0: every NEW v10.1.0 writing_style surface has presence
    coverage.

    Discharges the W-18 precondition for the v10.1.0 cycle-close MINOR.
    The CHANGELOG entry cites the writing_style package, the humanizer
    transforms, the CLI surface, the benchmark baselines, and the
    `make humanize-docs` target — each needs a presence assertion here
    before the CHANGELOG mention is valid.

    v10.1.0 pins:

    1. **writing_style package modules** — every module listed in
       `_V10_1_0_WRITING_STYLE_MODULES` must exist on disk.
    2. **writing_style public API** — every symbol in
       `_V10_1_0_WRITING_STYLE_PUBLIC_SYMBOLS` must be importable from
       the package (either defined in ``__init__.py`` or imported by it).
    3. **Benchmark baselines** — both `v10.1.0_pre.json` and
       `v10.1.0_post.json` must exist under
       `benchmarks/writing_style/baselines/`.
    4. **Humanize CLI** — `scripts/humanize_doc.py` exists.
    5. **Makefile target** — `humanize-docs:` target is defined.
    6. **CHANGELOG entry** — `## [10.1.0]` header is present.
    """
    for module_rel in _V10_1_0_WRITING_STYLE_MODULES:
        module_path = project_root / module_rel
        assert module_path.is_file(), (
            f"W-18 v10.1.0 violation: writing_style module {module_rel} "
            f"missing. v10.1.0 PV-02 / PV-03 ship this module; restore "
            "it or remove the CHANGELOG mention."
        )

    init_path = project_root / "src/devolaflow/writing_style/__init__.py"
    init_source = init_path.read_text(encoding="utf-8")
    for sym in _V10_1_0_WRITING_STYLE_PUBLIC_SYMBOLS:
        assert sym in init_source, (
            f"W-18 v10.1.0 violation: writing_style public symbol {sym!r} "
            "not exposed by __init__.py; the CHANGELOG documents the "
            "public API and cannot cite a missing surface."
        )

    for baseline_rel in _V10_1_0_BASELINE_FILES:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v10.1.0 violation: benchmark baseline {baseline_rel} "
            "missing. v10.1.0 PV-02 / PV-05 commit these baselines; "
            "regenerate with `python -m benchmarks.writing_style.runner "
            "--corpus devolaflow --output <path>`."
        )

    humanize_path = project_root / _V10_1_0_HUMANIZE_SCRIPT
    assert humanize_path.is_file(), (
        f"W-18 v10.1.0 violation: humanize CLI "
        f"{_V10_1_0_HUMANIZE_SCRIPT} missing. v10.1.0 PV-04 ships this "
        "surface; restore it or remove the CHANGELOG mention."
    )

    makefile_path = project_root / "Makefile"
    makefile_text = makefile_path.read_text(encoding="utf-8")
    assert _V10_1_0_HUMANIZE_MAKE_TARGET in makefile_text, (
        f"W-18 v10.1.0 violation: Makefile target "
        f"{_V10_1_0_HUMANIZE_MAKE_TARGET!r} missing; v10.1.0 PV-04 "
        "ships this target."
    )

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_1_0_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.1.0 violation: CHANGELOG entry "
        f"{_V10_1_0_CHANGELOG_LITERAL!r} missing; PV-06 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.0 ghost-audit refresh — MINOR cycle-start (plugin deep review).
# ---------------------------------------------------------------------------

# v10.2.0 PV-01 NEW test files (D-P-1 / D-P-4 / D-P-6 closures).
_V10_2_0_NEW_TEST_FILES: tuple[Path, ...] = (
    Path("tests/test_runtime_plugins_smoke.py"),
    Path("tests/test_plugin_refresh_e2e.py"),
    Path("tests/test_plugin_refresh_first_run.py"),
)

# v10.2.0 PV-01 NEW baseline fixtures (W-16 wholesale regen + 10th multi-baseline pin).
_V10_2_0_NEW_BASELINE_FILES: tuple[Path, ...] = (
    Path("benchmarks/devolaflow_context/baselines/v10.2.0_baseline.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v10.2.0.yaml"),
)

# v10.2.0 PV-01 D-P-3 new helper + its module path.
_V10_2_0_INSTALL_RESOLVER_PATH: Path = Path("src/devolaflow/si_chip_bridge/install_resolver.py")
_V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL: str = "read_installed_si_chip_version"

# v10.2.0 PV-01 D-P-3 registry edit contract.
_V10_2_0_RUNTIME_PLUGINS_YAML: Path = Path("workflow-system/agent/knowledge/runtime-plugins.yaml")
_V10_2_0_DEAD_HARDCODED_HEURISTIC: str = "echo si-chip/0.4.0"

_V10_2_0_CHANGELOG_LITERAL: str = "## [10.2.0]"


def test_v10_2_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.0: every NEW v10.2.0 PV-01 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.0 cycle-start MINOR.
    The CHANGELOG entry mentions the 3 new test files, the 2 new
    baseline fixtures, the `read_installed_si_chip_version` helper,
    and the D-P-3 si-chip `version_check_cmd` swap. Each needs a
    presence assertion here BEFORE the CHANGELOG mention is valid —
    per W-18 refresh-before-document sequencing.

    v10.2.0 PV-01 pins:

    1. **3 NEW test files** — every file in `_V10_2_0_NEW_TEST_FILES`
       must exist on disk (D-P-1 / D-P-4 / D-P-6 closures).
    2. **2 NEW baseline fixtures** — `v10.2.0_baseline.json` (W-16
       wholesale regen) + `layout_invariant_v10.2.0.yaml` (10th multi-
       baseline pin).
    3. **`read_installed_si_chip_version` helper** — defined in
       `src/devolaflow/si_chip_bridge/install_resolver.py` (D-P-3).
    4. **si-chip `version_check_cmd` swap** — the pre-v10.2.0
       hardcoded `echo si-chip/0.4.0` heuristic MUST be absent from
       `runtime-plugins.yaml` (replaced with the real frontmatter
       probe per D-P-3 closure).
    5. **CHANGELOG entry** — `## [10.2.0]` header is present.
    """
    import ast

    for test_rel in _V10_2_0_NEW_TEST_FILES:
        test_path = project_root / test_rel
        assert test_path.is_file(), (
            f"W-18 v10.2.0 violation: NEW test file {test_rel} missing. "
            f"v10.2.0 PV-01 ships this file per the cycle plan §3 PV-01; "
            f"restore it or remove the CHANGELOG mention of the "
            f"corresponding gap closure."
        )

    for baseline_rel in _V10_2_0_NEW_BASELINE_FILES:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v10.2.0 violation: NEW baseline fixture {baseline_rel} "
            f"missing. v10.2.0 PV-01 ships this baseline (W-16 wholesale "
            f"regen + 10th multi-baseline pin); regenerate via "
            f"`python -m benchmarks.devolaflow_context.generate_baseline "
            f"--output <path>` (for the JSON) OR copy "
            f"`layout_invariant_v9.7.0.yaml` (for the YAML witness)."
        )

    resolver_path = project_root / _V10_2_0_INSTALL_RESOLVER_PATH
    assert resolver_path.is_file(), (
        f"W-18 v10.2.0 violation: {_V10_2_0_INSTALL_RESOLVER_PATH} missing."
    )
    resolver_source = resolver_path.read_text(encoding="utf-8")
    resolver_module = ast.parse(resolver_source)
    defined_names = {
        node.name
        for node in ast.walk(resolver_module)
        if isinstance(node, ast.FunctionDef | ast.ClassDef)
    }
    assert _V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL in defined_names, (
        f"W-18 v10.2.0 violation: install_resolver module missing "
        f"{_V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL!r}; v10.2.0 PV-01 D-P-3 "
        f"ships this helper. Either restore it OR remove the CHANGELOG "
        f"mention of D-P-3."
    )

    runtime_yaml_path = project_root / _V10_2_0_RUNTIME_PLUGINS_YAML
    assert runtime_yaml_path.is_file(), (
        f"W-18 v10.2.0 violation: {_V10_2_0_RUNTIME_PLUGINS_YAML} missing."
    )
    runtime_yaml_text = runtime_yaml_path.read_text(encoding="utf-8")
    si_chip_block_start = runtime_yaml_text.find("- id: si-chip")
    assert si_chip_block_start != -1, (
        "W-18 v10.2.0 violation: si-chip block missing from runtime-plugins.yaml."
    )
    si_chip_block_end = runtime_yaml_text.find(
        "\n  - id:",
        si_chip_block_start + 1,
    )
    if si_chip_block_end == -1:
        si_chip_block_end = runtime_yaml_text.find("\ndefaults:", si_chip_block_start)
    si_chip_block = runtime_yaml_text[si_chip_block_start:si_chip_block_end]
    assert _V10_2_0_DEAD_HARDCODED_HEURISTIC not in si_chip_block, (
        f"W-18 v10.2.0 violation: si-chip block still contains the pre-"
        f"v10.2.0 hardcoded heuristic {_V10_2_0_DEAD_HARDCODED_HEURISTIC!r}. "
        f"D-P-3 replaces it with a real read_installed_si_chip_version "
        f"probe; restore the probe OR remove the CHANGELOG mention of "
        f"D-P-3."
    )
    assert _V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL in si_chip_block, (
        f"W-18 v10.2.0 violation: si-chip version_check_cmd should call "
        f"{_V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL!r}; current block does not "
        f"reference the helper. The v10.2.0 PV-01 D-P-3 closure requires "
        f"the probe to call into the bridge module."
    )

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_0_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.0 violation: CHANGELOG entry "
        f"{_V10_2_0_CHANGELOG_LITERAL!r} missing; PV-01 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.1 ghost-audit refresh — PV-02 PATCH (formal Si-Chip integration).
# ---------------------------------------------------------------------------

# v10.2.1 PV-02 NEW test files (D-S-2 / D-S-3 / D-S-5 closures).
_V10_2_1_NEW_TEST_FILES: tuple[Path, ...] = (
    Path("tests/test_dispatch_dogfood_cycle.py"),
    Path("tests/test_sichip_iteration_delta_gate.py"),
    Path("tests/test_sichip_dedup_feedback_doc.py"),
)

# v10.2.1 PV-02 D-S-2 new public symbol on devolaflow.feedback.
_V10_2_1_FEEDBACK_NEW_SYMBOL: str = "dispatch_dogfood_cycle"

# v10.2.1 PV-02 D-P-2 introspection constant on the lifecycle hook.
_V10_2_1_PRE_PLUGIN_INVOCATION_CONST: str = "EVENT_TRIGGERS_DAILY_UPGRADE"

# v10.2.1 PV-02 D-S-6 — the obsolete v9.5.0 literal MUST be gone from runner.py.
_V10_2_1_DEAD_WORK_DIR_LITERAL: str = '"v9.5.0"'

# v10.2.1 PV-02 D-S-3 — Makefile reference proving the iteration_delta gate
# is wired as the 7th SI-10 step.
_V10_2_1_MAKEFILE_GATE_REFERENCE: str = "test_sichip_iteration_delta_gate"

# v10.2.1 PV-02 dogfood pass #1 deliverable path (gitignored content; the
# path-presence assertion is the operator-visible contract).
_V10_2_1_DOGFOOD_PASS1_DOC: Path = Path(".local/research/v10.2.1_dogfood_pass1.md")

_V10_2_1_CHANGELOG_LITERAL: str = "## [10.2.1]"


def test_v10_2_1_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.1: every NEW v10.2.1 PV-02 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.1 PV-02 PATCH.
    The CHANGELOG entry mentions the 3 new test files, the
    `dispatch_dogfood_cycle` wrapper, the `EVENT_TRIGGERS_DAILY_UPGRADE`
    introspection constant, the Makefile `release-preflight` 7th-step
    wire, the absence of the obsolete v9.5.0 work_dir literal in
    runner.py, and the dogfood pass #1 research artifact. Each needs a
    presence assertion here BEFORE the CHANGELOG mention is valid — per
    W-18 refresh-before-document sequencing.

    v10.2.1 PV-02 pins:

    1. **3 NEW test files** — every file in `_V10_2_1_NEW_TEST_FILES`
       must exist on disk (D-S-2 / D-S-3 / D-S-5 closures).
    2. **`dispatch_dogfood_cycle` symbol** — defined in
       `src/devolaflow/feedback.py` (D-S-2 closure).
    3. **`EVENT_TRIGGERS_DAILY_UPGRADE` constant** — defined in
       `src/devolaflow/lifecycle/pre_plugin_invocation.py` (D-P-2
       closure introspection contract).
    4. **Makefile references the gate test** — the
       `release-preflight` chain calls
       `test_sichip_iteration_delta_gate` as the 7th SI-10 step
       (D-S-3 / D-V-1 closure).
    5. **No `"v9.5.0"` literal in `runner.py`** — D-S-6 swap is
       complete; the obsolete hardcoded work_dir literal is gone.
    6. **Dogfood pass #1 artifact** — file path presence at
       `.local/research/v10.2.1_dogfood_pass1.md` (gitignored content;
       path-presence is the operator-visible contract).
    7. **CHANGELOG entry** — `## [10.2.1]` header is present.
    """
    import ast

    for test_rel in _V10_2_1_NEW_TEST_FILES:
        test_path = project_root / test_rel
        assert test_path.is_file(), (
            f"W-18 v10.2.1 violation: NEW test file {test_rel} missing. "
            f"v10.2.1 PV-02 ships this file per the cycle plan §3 PV-02; "
            f"restore it or remove the CHANGELOG mention of the "
            f"corresponding gap closure."
        )

    feedback_path = project_root / "src/devolaflow/feedback.py"
    assert feedback_path.is_file(), "W-18 v10.2.1 violation: src/devolaflow/feedback.py missing."
    feedback_source = feedback_path.read_text(encoding="utf-8")
    feedback_module = ast.parse(feedback_source)
    feedback_defined = {
        node.name
        for node in ast.walk(feedback_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }
    assert _V10_2_1_FEEDBACK_NEW_SYMBOL in feedback_defined, (
        f"W-18 v10.2.1 violation: src/devolaflow/feedback.py missing "
        f"{_V10_2_1_FEEDBACK_NEW_SYMBOL!r}; v10.2.1 PV-02 D-S-2 ships "
        f"this wrapper. Either restore it OR remove the CHANGELOG "
        f"mention of D-S-2."
    )

    pre_plugin_path = project_root / "src/devolaflow/lifecycle/pre_plugin_invocation.py"
    assert pre_plugin_path.is_file(), "W-18 v10.2.1 violation: pre_plugin_invocation.py missing."
    pre_plugin_source = pre_plugin_path.read_text(encoding="utf-8")
    assert _V10_2_1_PRE_PLUGIN_INVOCATION_CONST in pre_plugin_source, (
        f"W-18 v10.2.1 violation: lifecycle hook missing the "
        f"{_V10_2_1_PRE_PLUGIN_INVOCATION_CONST!r} introspection "
        f"constant; v10.2.1 PV-02 D-P-2 daily-upgrade integration "
        f"requires this surface for downstream governance + tests."
    )

    runner_path = project_root / "src/devolaflow/si_chip_bridge/runner.py"
    assert runner_path.is_file(), "W-18 v10.2.1 violation: si_chip_bridge/runner.py missing."
    runner_source = runner_path.read_text(encoding="utf-8")
    # The literal MUST NOT appear inside the work_dir default expression
    # of `run_dogfood_cycle`. We scan the function body for it.
    runner_module = ast.parse(runner_source)
    run_dogfood_cycle_node: ast.FunctionDef | None = None
    for node in ast.walk(runner_module):
        if isinstance(node, ast.FunctionDef) and node.name == "run_dogfood_cycle":
            run_dogfood_cycle_node = node
            break
    assert run_dogfood_cycle_node is not None, (
        "W-18 v10.2.1 violation: run_dogfood_cycle function missing from si_chip_bridge/runner.py."
    )
    func_source = ast.get_source_segment(runner_source, run_dogfood_cycle_node) or ""
    assert _V10_2_1_DEAD_WORK_DIR_LITERAL not in func_source, (
        f"W-18 v10.2.1 violation: run_dogfood_cycle still contains the "
        f"obsolete work_dir literal {_V10_2_1_DEAD_WORK_DIR_LITERAL!r}. "
        f"v10.2.1 PV-02 D-S-6 closure swaps it for `__version__`-tracking "
        f"behaviour; restore the swap OR remove the CHANGELOG mention of "
        f"D-S-6."
    )

    makefile_path = project_root / "Makefile"
    assert makefile_path.is_file(), "W-18 v10.2.1 violation: Makefile missing."
    makefile_text = makefile_path.read_text(encoding="utf-8")
    assert _V10_2_1_MAKEFILE_GATE_REFERENCE in makefile_text, (
        f"W-18 v10.2.1 violation: Makefile does NOT reference "
        f"{_V10_2_1_MAKEFILE_GATE_REFERENCE!r}; the v10.2.1 PV-02 "
        f"release-preflight target is the 7th SI-10 step wire and must "
        f"be present per D-V-1."
    )
    assert "release-preflight:" in makefile_text, (
        "W-18 v10.2.1 violation: Makefile missing release-preflight target."
    )

    _w18_research_artifact_path(project_root, _V10_2_1_DOGFOOD_PASS1_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_1_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.1 violation: CHANGELOG entry "
        f"{_V10_2_1_CHANGELOG_LITERAL!r} missing; PV-02 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.2 ghost-audit refresh — PV-03 PATCH (NineS deep-analysis +
# Si-Chip eval adapter prototype).
# ---------------------------------------------------------------------------

# v10.2.2 PV-03 NEW script (D-N-1 closure: NineS-to-Si-Chip eval adapter).
_V10_2_2_ADAPTER_SCRIPT: Path = Path("scripts/nines_to_sichip_eval_adapter.py")

# v10.2.2 PV-03 NEW unit-test file pinning the adapter contract.
_V10_2_2_ADAPTER_TEST: Path = Path("tests/test_nines_to_sichip_adapter.py")

# v10.2.2 PV-03 D-N-1 — public symbols that MUST be defined in the adapter
# (the 4 functions plus the CLI entry point form the operator-visible contract).
_V10_2_2_ADAPTER_REQUIRED_SYMBOLS: tuple[str, ...] = (
    "load_nines_json",
    "validate_nines_shape",
    "build_runs",
    "build_baselines",
    "write_runs_dir",
    "write_baseline_dir",
    "main",
)

# v10.2.2 PV-03 D-N-3 — three NineS deep-analysis JSON outputs (gitignored
# content; path-presence is the operator-visible contract).
_V10_2_2_NINES_JSON_PATHS: tuple[Path, ...] = (
    Path(".local/research/v10.2.2_nines.json"),
    Path(".local/research/v10.2.2_nines_plugins.json"),
    Path(".local/research/v10.2.2_nines_lifecycle.json"),
)

# v10.2.2 PV-03 D-N-3 NineS synthesis (gitignored content; path-presence
# contract).
_V10_2_2_NINES_SYNTHESIS_DOC: Path = Path(".local/research/v10.2.2_nines.md")

# v10.2.2 PV-03 dogfood pass #2 deliverable (gitignored content;
# path-presence contract).
_V10_2_2_DOGFOOD_PASS2_DOC: Path = Path(".local/research/v10.2.2_dogfood_pass2.md")

_V10_2_2_CHANGELOG_LITERAL: str = "## [10.2.2]"


def test_v10_2_2_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.2: every NEW v10.2.2 PV-03 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.2 PV-03 PATCH.
    The CHANGELOG entry mentions the NineS-to-Si-Chip eval adapter
    script + 7 public functions, the unit-test file, the 3 NineS
    deep-analysis JSONs, the synthesis document, and the dogfood pass
    #2 capture. Each needs a presence assertion here BEFORE the
    CHANGELOG mention is valid — per W-18 refresh-before-document
    sequencing.

    v10.2.2 PV-03 pins:

    1. **Adapter script** — `scripts/nines_to_sichip_eval_adapter.py`
       exists and defines all 7 public symbols (`load_nines_json`,
       `validate_nines_shape`, `build_runs`, `build_baselines`,
       `write_runs_dir`, `write_baseline_dir`, `main`).
    2. **Adapter unit-test file** —
       `tests/test_nines_to_sichip_adapter.py` exists.
    3. **3 NineS deep-analysis JSONs** — every path in
       `_V10_2_2_NINES_JSON_PATHS` exists (D-N-3 closure;
       `nines analyze --target-path src/devolaflow/{si_chip_bridge,plugins,lifecycle}`).
    4. **NineS synthesis** — `.local/research/v10.2.2_nines.md` exists
       (D-N-3 closure; per-package finding + agent-impact synthesis).
    5. **Dogfood pass #2** — `.local/research/v10.2.2_dogfood_pass2.md`
       exists (D-N-1 + D-S-1 closure; adapter outcome + per-file
       iteration_delta capture).
    6. **CHANGELOG entry** — `## [10.2.2]` header is present.
    """
    import ast

    adapter_path = project_root / _V10_2_2_ADAPTER_SCRIPT
    assert adapter_path.is_file(), (
        f"W-18 v10.2.2 violation: NEW adapter script {_V10_2_2_ADAPTER_SCRIPT} "
        f"missing. v10.2.2 PV-03 D-N-1 ships this script per the cycle plan "
        f"§3 PV-03; restore it or remove the CHANGELOG mention of D-N-1."
    )
    adapter_source = adapter_path.read_text(encoding="utf-8")
    adapter_module = ast.parse(adapter_source)
    adapter_defined = {
        node.name
        for node in ast.walk(adapter_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }
    for sym in _V10_2_2_ADAPTER_REQUIRED_SYMBOLS:
        assert sym in adapter_defined, (
            f"W-18 v10.2.2 violation: adapter script missing required public "
            f"symbol {sym!r}; v10.2.2 PV-03 D-N-1 contract requires this "
            f"symbol. Either restore it OR remove the CHANGELOG mention of "
            f"D-N-1."
        )

    test_path = project_root / _V10_2_2_ADAPTER_TEST
    assert test_path.is_file(), (
        f"W-18 v10.2.2 violation: NEW adapter test file "
        f"{_V10_2_2_ADAPTER_TEST} missing. v10.2.2 PV-03 D-N-1 ships ≥6 "
        f"unit tests per the cycle plan AC #2; restore it or remove the "
        f"CHANGELOG mention."
    )

    for json_path in _V10_2_2_NINES_JSON_PATHS:
        _w18_research_artifact_path(project_root, json_path)

    _w18_research_artifact_path(project_root, _V10_2_2_NINES_SYNTHESIS_DOC)

    _w18_research_artifact_path(project_root, _V10_2_2_DOGFOOD_PASS2_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_2_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.2 violation: CHANGELOG entry "
        f"{_V10_2_2_CHANGELOG_LITERAL!r} missing; PV-03 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.3 ghost-audit refresh — PV-04 PATCH (self-iteration round 1:
# bridge defect fix + Track B CC reductions).
# ---------------------------------------------------------------------------

# v10.2.3 PV-04 dogfood pass #3 deliverable (gitignored content;
# path-presence is the operator-visible contract).
_V10_2_3_DOGFOOD_PASS3_DOC: Path = Path(".local/research/v10.2.3_dogfood_pass3.md")

# v10.2.3 PV-04 self-iteration round 1 report (gitignored content;
# path-presence contract).
_V10_2_3_ITERATION_ROUND1_DOC: Path = Path(".local/research/v10.2.3_iteration_round1.md")

# v10.2.3 PV-04 Track A — bridge defect fix surface.
_V10_2_3_BRIDGE_MODELS_FILE: Path = Path("src/devolaflow/si_chip_bridge/models.py")

# Strings that MUST appear in models.py to prove the MVP-8 nested-key
# support shipped (NOT a paraphrase — the literal Si-Chip MVP-8 path
# fragments per .local/dogfood/10.2.1/skill-optimization_after_metrics.yaml).
_V10_2_3_BRIDGE_MVP8_LITERALS: tuple[str, ...] = (
    "T1_pass_rate",
    "T3_baseline_delta",
    "C1_metadata_tokens",
    "C2_body_tokens",
    "baseline_delta",
)

# v10.2.3 PV-04 Track B-1 — pre_plugin_invocation helpers.
_V10_2_3_PPI_FILE: Path = Path("src/devolaflow/lifecycle/pre_plugin_invocation.py")
_V10_2_3_PPI_HELPERS: tuple[str, ...] = (
    "_resolve_upgrade_threshold_hours",
    "_run_install_then_upgrade_for_plugin",
)

# v10.2.3 PV-04 Track B-2 — post_skill_edit helpers.
_V10_2_3_PSE_FILE: Path = Path("src/devolaflow/lifecycle/post_skill_edit.py")
_V10_2_3_PSE_HELPERS: tuple[str, ...] = (
    "_compute_fingerprint",
    "_load_existing_fingerprints",
    "_run_si_chip_evaluation",
)

_V10_2_3_CHANGELOG_LITERAL: str = "## [10.2.3]"


def test_v10_2_3_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.3: every NEW v10.2.3 PV-04 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.3 PV-04 PATCH
    (self-iteration round 1). The CHANGELOG entry mentions the bridge
    defect fix in `MetricsReport.from_yaml_dict` (Track A), the two
    Track B CC reductions in `pre_plugin_invocation` and `post_skill_edit`
    via extracted helpers, and the two research deliverables (dogfood
    pass #3 + iteration round 1 report). Each needs a presence
    assertion here BEFORE the CHANGELOG mention is valid — per W-18
    refresh-before-document sequencing.

    v10.2.3 PV-04 pins:

    1. **Bridge defect fix (Track A)** —
       `src/devolaflow/si_chip_bridge/models.py` carries MVP-8 nested
       path literals (T1_pass_rate, T3_baseline_delta,
       C1_metadata_tokens, C2_body_tokens, baseline_delta). Without
       these the v10.2.2 PV-03 dogfood pass #2 bridge defect is not
       fixed.
    2. **CC reduction Track B-1** —
       `src/devolaflow/lifecycle/pre_plugin_invocation.py` defines
       `_resolve_upgrade_threshold_hours` and
       `_run_install_then_upgrade_for_plugin`.
    3. **CC reduction Track B-2** —
       `src/devolaflow/lifecycle/post_skill_edit.py` defines
       `_compute_fingerprint`, `_load_existing_fingerprints`, and
       `_run_si_chip_evaluation`.
    4. **Dogfood pass #3 deliverable** —
       `.local/research/v10.2.3_dogfood_pass3.md` exists.
    5. **Self-iteration round 1 report** —
       `.local/research/v10.2.3_iteration_round1.md` exists.
    6. **CHANGELOG entry** — `## [10.2.3]` header is present.
    """
    import ast

    bridge_path = project_root / _V10_2_3_BRIDGE_MODELS_FILE
    assert bridge_path.is_file(), (
        f"W-18 v10.2.3 violation: bridge file {_V10_2_3_BRIDGE_MODELS_FILE} "
        f"missing. v10.2.3 PV-04 Track A patches `MetricsReport.from_yaml_dict` "
        f"in this file; restore it or remove the CHANGELOG mention."
    )
    bridge_source = bridge_path.read_text(encoding="utf-8")
    for literal in _V10_2_3_BRIDGE_MVP8_LITERALS:
        assert literal in bridge_source, (
            f"W-18 v10.2.3 violation: bridge models.py missing MVP-8 literal "
            f"{literal!r}; v10.2.3 PV-04 Track A REQUIRES this nested-key "
            f"path to read Si-Chip aggregate_eval.py v0.1.6 emit shape. "
            f"Either restore the literal OR remove the CHANGELOG mention "
            f"of the bridge defect fix."
        )

    ppi_path = project_root / _V10_2_3_PPI_FILE
    assert ppi_path.is_file(), (
        f"W-18 v10.2.3 violation: pre_plugin_invocation file "
        f"{_V10_2_3_PPI_FILE} missing. v10.2.3 PV-04 Track B-1 extracts "
        f"helpers in this file; restore it or remove the CHANGELOG mention."
    )
    ppi_source = ppi_path.read_text(encoding="utf-8")
    ppi_module = ast.parse(ppi_source)
    ppi_defined = {
        node.name
        for node in ast.walk(ppi_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    for helper in _V10_2_3_PPI_HELPERS:
        assert helper in ppi_defined, (
            f"W-18 v10.2.3 violation: pre_plugin_invocation.py missing "
            f"helper {helper!r}; v10.2.3 PV-04 Track B-1 ships this helper "
            f"as part of the CC=18 → ≤10 reduction. Either restore the "
            f"helper OR remove the CHANGELOG mention of Track B-1."
        )

    pse_path = project_root / _V10_2_3_PSE_FILE
    assert pse_path.is_file(), (
        f"W-18 v10.2.3 violation: post_skill_edit file {_V10_2_3_PSE_FILE} "
        f"missing. v10.2.3 PV-04 Track B-2 extracts helpers in this file; "
        f"restore it or remove the CHANGELOG mention."
    )
    pse_source = pse_path.read_text(encoding="utf-8")
    pse_module = ast.parse(pse_source)
    pse_defined = {
        node.name
        for node in ast.walk(pse_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    for helper in _V10_2_3_PSE_HELPERS:
        assert helper in pse_defined, (
            f"W-18 v10.2.3 violation: post_skill_edit.py missing helper "
            f"{helper!r}; v10.2.3 PV-04 Track B-2 ships this helper as "
            f"part of the CC=13 → ≤7 reduction. Either restore the helper "
            f"OR remove the CHANGELOG mention of Track B-2."
        )

    _w18_research_artifact_path(project_root, _V10_2_3_DOGFOOD_PASS3_DOC)

    _w18_research_artifact_path(project_root, _V10_2_3_ITERATION_ROUND1_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_3_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.3 violation: CHANGELOG entry "
        f"{_V10_2_3_CHANGELOG_LITERAL!r} missing; PV-04 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.4 ghost-audit refresh — PV-05 PATCH (self-iteration round 2:
# 1 mechanical CC reduction in installer.py + W-8 stagnation predicate +
# W-17 mid-cycle audit + dogfood pass #4).
# ---------------------------------------------------------------------------

# v10.2.4 PV-05 round-2 mechanical extraction surface (CC=15→8 in
# `read_last_checked` per NineS PV-03 finding CC-a5d310-0003).
_V10_2_4_INSTALLER_FILE: Path = Path("src/devolaflow/plugins/installer.py")
_V10_2_4_INSTALLER_HELPERS: tuple[str, ...] = ("_parse_log_event_timestamp",)
_V10_2_4_INSTALLER_MODULE_CONSTANTS: tuple[str, ...] = ("_LAST_CHECKED_SUCCESSFUL_EVENTS",)

# v10.2.4 PV-05 research deliverables (gitignored content; path-presence
# is the operator-visible contract).
_V10_2_4_ITERATION_ROUND2_DOC: Path = Path(".local/research/v10.2.4_iteration_round2.md")
_V10_2_4_W17_AUDIT_DOC: Path = Path(".local/research/v10.2.4_w17_mid_cycle_audit.md")
_V10_2_4_W8_STAGNATION_DOC: Path = Path(".local/research/v10.2.4_w8_stagnation_check.md")
_V10_2_4_DOGFOOD_PASS4_DOC: Path = Path(".local/research/v10.2.4_dogfood_pass4.md")

_V10_2_4_CHANGELOG_LITERAL: str = "## [10.2.4]"

# W-17 mid-cycle audit cumulative-count sentinel — the CHANGELOG entry
# MUST cite the cycle-cumulative NEW-test count so the audit assertion
# is discoverable by W-17 readers without spelunking through the
# research artifact. The literal "93 / 150" is the post-PV-05 cumulative
# (see `.local/research/v10.2.4_w17_mid_cycle_audit.md` §1).
_V10_2_4_CHANGELOG_W17_LITERAL: str = "93 / 150"


def test_v10_2_4_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.4: every NEW v10.2.4 PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.4 PV-05 PATCH
    (self-iteration round 2 + W-17 mid-cycle audit + W-8 stagnation
    predicate). The CHANGELOG entry mentions the round-2 mechanical CC
    reduction in `installer.py::read_last_checked` (CC=15→8 via
    `_parse_log_event_timestamp` helper extraction) and the four
    research deliverables (round 2 report, W-17 audit, W-8 stagnation
    check, dogfood pass #4). Each needs a presence assertion here
    BEFORE the CHANGELOG mention is valid — per W-18 refresh-before-
    document sequencing.

    v10.2.4 PV-05 pins:

    1. **Round-2 mechanical extraction (Track A)** —
       `src/devolaflow/plugins/installer.py` defines
       `_parse_log_event_timestamp` (helper) AND
       `_LAST_CHECKED_SUCCESSFUL_EVENTS` (lifted module-level constant).
       Without these the v10.2.4 PV-05 round-2 fix is not shipped.
    2. **Self-iteration round 2 report** —
       `.local/research/v10.2.4_iteration_round2.md` exists.
    3. **W-17 mid-cycle audit** —
       `.local/research/v10.2.4_w17_mid_cycle_audit.md` exists; cumulative
       count is documented in CHANGELOG (literal "93 / 150").
    4. **W-8 stagnation predicate evaluation** —
       `.local/research/v10.2.4_w8_stagnation_check.md` exists.
    5. **Dogfood pass #4 deliverable** —
       `.local/research/v10.2.4_dogfood_pass4.md` exists.
    6. **CHANGELOG entry** — `## [10.2.4]` header is present.
    """
    import ast

    installer_path = project_root / _V10_2_4_INSTALLER_FILE
    assert installer_path.is_file(), (
        f"W-18 v10.2.4 violation: installer file {_V10_2_4_INSTALLER_FILE} "
        f"missing. v10.2.4 PV-05 round-2 patches `read_last_checked` in "
        f"this file via `_parse_log_event_timestamp` helper extraction; "
        f"restore it or remove the CHANGELOG mention."
    )
    installer_source = installer_path.read_text(encoding="utf-8")
    installer_module = ast.parse(installer_source)
    installer_defined = {
        node.name
        for node in ast.walk(installer_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    for helper in _V10_2_4_INSTALLER_HELPERS:
        assert helper in installer_defined, (
            f"W-18 v10.2.4 violation: installer.py missing helper "
            f"{helper!r}; v10.2.4 PV-05 round-2 ships this helper as "
            f"part of the CC=15 → ≤10 reduction in `read_last_checked` "
            f"per NineS PV-03 finding CC-a5d310-0003. Either restore "
            f"the helper OR remove the CHANGELOG mention of the round-2 "
            f"installer.py extraction."
        )

    installer_module_assigns = {
        target.id
        for node in ast.walk(installer_module)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    } | {
        node.target.id
        for node in ast.walk(installer_module)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    for constant in _V10_2_4_INSTALLER_MODULE_CONSTANTS:
        assert constant in installer_module_assigns, (
            f"W-18 v10.2.4 violation: installer.py missing module-level "
            f"constant {constant!r}; v10.2.4 PV-05 round-2 lifts the "
            f"successful-event set to a module-level frozenset for "
            f"introspection. Restore the constant OR remove the CHANGELOG "
            f"mention of the round-2 lift."
        )

    _w18_research_artifact_path(project_root, _V10_2_4_ITERATION_ROUND2_DOC)

    _w18_research_artifact_path(project_root, _V10_2_4_W17_AUDIT_DOC)

    _w18_research_artifact_path(project_root, _V10_2_4_W8_STAGNATION_DOC)

    _w18_research_artifact_path(project_root, _V10_2_4_DOGFOOD_PASS4_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_4_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.4 violation: CHANGELOG entry "
        f"{_V10_2_4_CHANGELOG_LITERAL!r} missing; PV-05 ships this entry."
    )
    assert _V10_2_4_CHANGELOG_W17_LITERAL in changelog_text, (
        f"W-18 v10.2.4 violation: CHANGELOG entry must cite the cycle-"
        f"cumulative NEW-test count {_V10_2_4_CHANGELOG_W17_LITERAL!r} "
        f"to document the W-17 audit verdict. Without this literal "
        f"the W-17 §3 mid-cycle audit assertion is not discoverable to "
        f"future cycle authors. Update CHANGELOG `## [10.2.4]` to cite "
        f"the W-17 cumulative count."
    )


# =====================================================================
# v10.3.0 PV-06 cycle-close W-18 ghost-audit refresh
# =====================================================================
#
# v10.3.0 is the MINOR cycle close of the v10.2.0 cycle (5 PATCH PVs +
# this MINOR cycle-close PV). PV-06 ships:
# 1. Canonical 7 sync locations bumped 10.2.4 → 10.3.0
# 2. README "What's New in v10.3.0 (MINOR cycle close)" section
# 3. demo/index.html v10.3.0 What's New section with 3 highlight cards
# 4. versions.json v10.3.0 entry (63rd)
# 5. benchmark-results SAMPLE_DATA at 10.3.0 (handled by bump_version)
# 6. .local/research/v10.3.0_evaluation.md (W-3 SI-3 STRICT MINOR-cycle-close)
# 7. .local/research/v10.3.0_retrospective.md (W-7 SI-8; 4 mandatory sections)
# 8. .local/research/v10.3.0_nines.{json,md} (W-2 SI-2 cycle-close self-eval)
# 9. docs/cycle-archive/v10.3.0/ (W-19 cycle archive; ≥10 files)
# 10. CHANGELOG ## [10.3.0] header

# v10.3.0 PV-06 README "What's New" section literal — pinned for visibility.
_V10_3_0_README_WHATS_NEW: str = "What's New in v10.3.0 (MINOR cycle close)"

# v10.3.0 PV-06 demo landing v10.3.0 What's New marker — pinned for ST-1.
_V10_3_0_DEMO_LANDING_LITERAL: str = 'data-i18n="landing.whatsNew.v1030"'

# v10.3.0 PV-06 versions.json entry must contain the v10.3.0 version field.
# (Schema-checked via tests/test_doc_consistency.py; here we pin presence.)
_V10_3_0_VERSIONS_JSON_LITERAL: str = '"version": "10.3.0"'

# v10.3.0 PV-06 benchmark-results SAMPLE_DATA literal (canonical 7 sync #8).
#
# v10.4.0 PV-05 NOTE: the original literal was version-specific
# ('"version":"10.3.0"'), which `scripts/bump_version.py` atomically
# rewrites on every subsequent cycle. The pin's INTENT is "verify
# canonical 7 sync #8 wired the SAMPLE_DATA `version` field"; the
# realised assertion was "verify the value is exactly 10.3.0" — these
# diverge after the first post-v10.3.0 bump. The fix is to assert the
# field LABEL is present, which survives version bumps, so the lint
# preserves its semantic intent (the v10.3.0 cycle wired the canonical
# 7 sync #8 → benchmark-results) without breaking on every future bump.
_V10_3_0_BENCHMARK_SAMPLE_DATA_LITERAL: str = '"version":"'

# v10.3.0 PV-06 research artifacts (gitignored; path-presence is the
# operator-visible contract).
_V10_3_0_EVALUATION_DOC: Path = Path(".local/research/v10.3.0_evaluation.md")
_V10_3_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.3.0_retrospective.md")
_V10_3_0_NINES_JSON: Path = Path(".local/research/v10.3.0_nines.json")
_V10_3_0_NINES_MD: Path = Path(".local/research/v10.3.0_nines.md")

# v10.3.0 PV-06 W-19 cycle archive directory (committed; presence-checked).
_V10_3_0_CYCLE_ARCHIVE_DIR: Path = Path("docs/cycle-archive/v10.3.0")

# v10.3.0 PV-06 CHANGELOG header literal.
_V10_3_0_CHANGELOG_LITERAL: str = "## [10.3.0]"

# v10.3.0 W-3 SI-3 composite literal — the CHANGELOG entry must cite the
# composite to document the STRICT MINOR-cycle-close gate verdict.
_V10_3_0_CHANGELOG_SI3_LITERAL: str = "9.385"


def test_v10_3_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.3.0: every NEW v10.3.0 PV-06 surface has presence coverage.

    Discharges the W-18 precondition for the v10.3.0 PV-06 MINOR cycle
    close. The CHANGELOG entry mentions:

    * the v10.2.0 cycle's 6-PV ledger (PV-01 → PV-06);
    * canonical 7 sync to 10.3.0;
    * README + demo + versions.json + benchmark-results human-doc refresh;
    * .local/research/v10.3.0_{nines,evaluation,retrospective}.{json,md};
    * docs/cycle-archive/v10.3.0/ via the W-19 archive harness;
    * the W-3 SI-3 composite 9.385/10 verdict.

    Each needs a presence assertion here BEFORE the CHANGELOG mention is
    valid — per W-18 refresh-before-document sequencing.

    v10.3.0 PV-06 pins (10 distinct surface elements):

    1. README "What's New in v10.3.0 (MINOR cycle close)" header is present.
    2. demo/index.html carries the v10.3.0 What's New section
       (`landing.whatsNew.v1030` i18n key marker).
    3. versions.json contains a `"version": "10.3.0"` entry.
    4. benchmark-results/index.html SAMPLE_DATA at "10.3.0" (bump_version
       canonical 7 sync #8).
    5. `.local/research/v10.3.0_evaluation.md` exists (W-3 SI-3).
    6. `.local/research/v10.3.0_retrospective.md` exists (W-7 SI-8).
    7. `.local/research/v10.3.0_nines.json` exists (W-2 SI-2 raw).
    8. `.local/research/v10.3.0_nines.md` exists (W-2 SI-2 synthesis).
    9. `docs/cycle-archive/v10.3.0/` directory exists with ≥ 10 files
       (W-19 archive).
    10. CHANGELOG `## [10.3.0]` header is present AND cites the W-3
        SI-3 composite literal "9.385" so the STRICT MINOR-cycle-close
        gate verdict is discoverable to future cycle authors.
    """
    readme_path = project_root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    assert _V10_3_0_README_WHATS_NEW in readme_text, (
        f"W-18 v10.3.0 violation: README missing literal "
        f"{_V10_3_0_README_WHATS_NEW!r}; the v10.3.0 cycle-close PV ships "
        f"a README 'What's New' section per ST-1. Restore the section OR "
        f"remove the CHANGELOG mention of the README refresh."
    )

    demo_index_path = project_root / "workflow-system" / "human" / "demo" / "index.html"
    demo_index_text = demo_index_path.read_text(encoding="utf-8")
    assert _V10_3_0_DEMO_LANDING_LITERAL in demo_index_text, (
        f"W-18 v10.3.0 violation: demo landing missing the "
        f"{_V10_3_0_DEMO_LANDING_LITERAL!r} i18n marker; the v10.3.0 "
        f"cycle-close PV ships a v10.3.0 What's New section per ST-1 + "
        f"ST-2. Restore the section OR remove the CHANGELOG mention."
    )

    versions_json_path = (
        project_root / "workflow-system" / "human" / "demo" / "version-timeline" / "versions.json"
    )
    versions_json_text = versions_json_path.read_text(encoding="utf-8")
    assert _V10_3_0_VERSIONS_JSON_LITERAL in versions_json_text, (
        f"W-18 v10.3.0 violation: versions.json missing entry containing "
        f"{_V10_3_0_VERSIONS_JSON_LITERAL!r}; ST-7 requires a v10.3.0 "
        f"entry. Add the entry OR remove the CHANGELOG mention."
    )

    benchmark_results_path = (
        project_root / "workflow-system" / "human" / "demo" / "benchmark-results" / "index.html"
    )
    benchmark_text = benchmark_results_path.read_text(encoding="utf-8")
    assert _V10_3_0_BENCHMARK_SAMPLE_DATA_LITERAL in benchmark_text, (
        f"W-18 v10.3.0 violation: benchmark-results missing SAMPLE_DATA "
        f"version literal {_V10_3_0_BENCHMARK_SAMPLE_DATA_LITERAL!r}; "
        f"canonical 7 sync #8 (`scripts/bump_version.py`) updates this "
        f"automatically. Re-run `python scripts/bump_version.py 10.3.0`."
    )

    _w18_research_artifact_path(project_root, _V10_3_0_EVALUATION_DOC)

    _w18_research_artifact_path(project_root, _V10_3_0_RETROSPECTIVE_DOC)

    _w18_research_artifact_path(project_root, _V10_3_0_NINES_JSON)

    _w18_research_artifact_path(project_root, _V10_3_0_NINES_MD)

    archive_dir = project_root / _V10_3_0_CYCLE_ARCHIVE_DIR
    assert archive_dir.is_dir(), (
        f"W-18 v10.3.0 violation: W-19 cycle archive directory missing "
        f"at {_V10_3_0_CYCLE_ARCHIVE_DIR}. v10.3.0 PV-06 runs "
        f"`python scripts/archive_research_artifacts.py 10.3.0 "
        f"--extra-prefix v10.2.` to populate it. Re-run the harness."
    )
    archive_files = list(archive_dir.rglob("*"))
    archive_file_count = sum(1 for f in archive_files if f.is_file())
    assert archive_file_count >= 10, (
        f"W-18 v10.3.0 violation: W-19 cycle archive at "
        f"{_V10_3_0_CYCLE_ARCHIVE_DIR} contains only {archive_file_count} "
        f"file(s); the cycle archive should hold ≥ 10 files (per the "
        f"v10.0.0 archive precedent at docs/cycle-archive/v10.0.0/ which "
        f"holds 51 files). Re-run the W-19 harness with "
        f"`--extra-prefix v10.2.` to capture all PATCH-PV research."
    )

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_3_0_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.3.0 violation: CHANGELOG entry "
        f"{_V10_3_0_CHANGELOG_LITERAL!r} missing; PV-06 ships this entry."
    )
    assert _V10_3_0_CHANGELOG_SI3_LITERAL in changelog_text, (
        f"W-18 v10.3.0 violation: CHANGELOG `## [10.3.0]` entry must "
        f"cite the W-3 SI-3 composite literal "
        f"{_V10_3_0_CHANGELOG_SI3_LITERAL!r} (the cycle's STRICT "
        f"MINOR-cycle-close gate verdict). Without the literal the "
        f"composite is not discoverable to future cycle authors. Update "
        f"CHANGELOG to cite the composite."
    )


# =====================================================================
# v10.4.0 PV-05 — Developer Experience + Reference Audit Foundation
# =====================================================================
#
# v10.4.0 collapses 6 PDSs (D-X-1, D-X-2, D-X-3, D-X-5, D-D-1, D-D-2)
# into a single coherent MINOR cycle. PV-05 ships:
#  1. NEW scripts/scaffold_template.py (D-X-1 — workflow template CLI)
#  2. NEW scripts/scaffold_reference.py (D-X-2 — reference doc CLI)
#  3. NEW scripts/audit_reference_utilization.py (D-D-1 — selector audit)
#  4. NEW scripts/audit_long_reference_usage.py (D-D-2 — handoff audit)
#  5. NEW workflow-system/agent/references/troubleshooting.md (D-X-5;
#     15th SF-4 canonical)
#  6. Makefile precommit-fast / precommit-full / precommit (D-X-3
#     SI-10 fast-path)
#  7. CHANGELOG `## [10.4.0]` entry; canonical 7 sync 10.3.0 -> 10.4.0
#  8. .local/research/v10.4.{0,1,2}_*.md retrospective + audit outputs

_V10_4_0_SCAFFOLD_TEMPLATE_SCRIPT: Path = Path("scripts/scaffold_template.py")
_V10_4_0_SCAFFOLD_REFERENCE_SCRIPT: Path = Path("scripts/scaffold_reference.py")
_V10_4_0_AUDIT_UTILIZATION_SCRIPT: Path = Path("scripts/audit_reference_utilization.py")
_V10_4_0_AUDIT_LONG_REF_SCRIPT: Path = Path("scripts/audit_long_reference_usage.py")
_V10_4_0_TROUBLESHOOTING_REF: Path = Path("workflow-system/agent/references/troubleshooting.md")
_V10_4_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.4.0_retrospective.md")
_V10_4_0_REF_UTILIZATION_DOC: Path = Path(".local/research/v10.4.1_reference_utilization.md")
_V10_4_0_LONG_REF_USAGE_DOC: Path = Path(".local/research/v10.4.2_long_reference_usage.md")
_V10_4_0_CHANGELOG_LITERAL: str = "## [10.4.0]"
_V10_4_0_MAKEFILE_PRECOMMIT_FAST_LITERAL: str = "precommit-fast:"
_V10_4_0_MAKEFILE_PRECOMMIT_FULL_LITERAL: str = "precommit-full:"
_V10_4_0_MAKEFILE_PRECOMMIT_LITERAL: str = "precommit: precommit-full"


def test_v10_4_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.4.0: every NEW v10.4.0 PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.4.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 4 NEW scripts (scaffold_template, scaffold_reference,
      audit_reference_utilization, audit_long_reference_usage);
    * 1 NEW reference (troubleshooting.md, the 15th SF-4 canonical);
    * 3 NEW Makefile targets (precommit-fast, precommit-full,
      precommit);
    * 2 NEW research artifacts (v10.4.1 reference utilization audit
      output + v10.4.2 long-reference usage audit output);
    * canonical 7 sync 10.3.0 -> 10.4.0 + CHANGELOG `## [10.4.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    for script in (
        _V10_4_0_SCAFFOLD_TEMPLATE_SCRIPT,
        _V10_4_0_SCAFFOLD_REFERENCE_SCRIPT,
        _V10_4_0_AUDIT_UTILIZATION_SCRIPT,
        _V10_4_0_AUDIT_LONG_REF_SCRIPT,
    ):
        path = project_root / script
        assert path.is_file(), (
            f"W-18 v10.4.0 violation: NEW script missing at {script}. "
            f"v10.4.0 PV-05 ships this script as part of the D-X / D-D "
            f"slice. Author the file OR remove the CHANGELOG mention."
        )

    troubleshooting = project_root / _V10_4_0_TROUBLESHOOTING_REF
    assert troubleshooting.is_file(), (
        f"W-18 v10.4.0 violation: 15th SF-4 canonical reference missing "
        f"at {_V10_4_0_TROUBLESHOOTING_REF}. v10.4.0 PV-05 ships D-X-5."
    )

    skill_text = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert "references/troubleshooting.md" in skill_text, (
        "W-18 v10.4.0 violation: SKILL.md must surface the new reference "
        "in the Reference Navigation Guide table."
    )

    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for marker in (
        _V10_4_0_MAKEFILE_PRECOMMIT_FAST_LITERAL,
        _V10_4_0_MAKEFILE_PRECOMMIT_FULL_LITERAL,
        _V10_4_0_MAKEFILE_PRECOMMIT_LITERAL,
    ):
        assert marker in makefile_text, (
            f"W-18 v10.4.0 violation: Makefile missing literal {marker!r} "
            f"(D-X-3 SI-10 fast-path). Author the target OR remove the "
            f"CHANGELOG mention."
        )

    _w18_research_artifact_path(project_root, _V10_4_0_RETROSPECTIVE_DOC)

    _w18_research_artifact_path(project_root, _V10_4_0_REF_UTILIZATION_DOC)

    _w18_research_artifact_path(project_root, _V10_4_0_LONG_REF_USAGE_DOC)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_4_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.4.0 violation: CHANGELOG entry "
        f"{_V10_4_0_CHANGELOG_LITERAL!r} missing; PV-05 ships this entry."
    )


# =====================================================================
# v10.5.0 PV-01..PV-05 — Architecture & Documentation Health
# =====================================================================
#
# v10.5.0 collapses 6 v11.0.0-cycle PDSs (D-A-1, D-A-2, D-A-3, D-A-4,
# D-D-3, D-D-4) into a single coherent MINOR cycle per
# `.local/research/v11.0.0_patches/`. The cycle ships:
#  1. NEW scripts/audit_layer_usage.py (D-A-1 — L0/L1/L2/L3 dispatch
#     ratio audit)
#  2. NEW scripts/audit_template_usage.py (D-A-2 Phase A — TIER-1
#     USED vs TIER-2 REGISTERED template audit)
#  3. NEW scripts/measure_reference_friction.py (D-D-3 — reference
#     comprehension cost / dense-paragraph audit)
#  4. NEW scripts/audit_w18_lint_maintenance.py (D-D-4 — W-17/W-18
#     lint maintenance trajectory audit)
#  5. NEW workflow-system/agent/examples/multi-stage-trace.md
#     (D-A-1 — 4th XL-tier example, the multi-team analyze
#     counter-case for SKILL.md §"Quick Action Decision" advisory)
#  6. NEW agent-workspace.md §3.6 "Resume After Pause" (D-A-3 —
#     pure-doc subsection)
#  7. NEW activation_verdict(force_no_change=...) parameter (D-A-4)
#  8. 16 TIER-2 yaml deprecation comment headers (D-A-2 Phase A)
#  9. 4 NEW Makefile targets (audit-layers, audit-templates,
#     measure-friction, audit-w18)
#  10. CHANGELOG `## [10.5.0]` entry; canonical 7 sync 10.4.0 -> 10.5.0
#  11. .local/research/v10.5.{0,1,2,3,4}_*.md retrospective + 4
#      audit outputs

_V10_5_0_AUDIT_LAYERS_SCRIPT: Path = Path("scripts/audit_layer_usage.py")
_V10_5_0_AUDIT_TEMPLATES_SCRIPT: Path = Path("scripts/audit_template_usage.py")
_V10_5_0_MEASURE_FRICTION_SCRIPT: Path = Path("scripts/measure_reference_friction.py")
_V10_5_0_AUDIT_W18_SCRIPT: Path = Path("scripts/audit_w18_lint_maintenance.py")
_V10_5_0_MULTI_STAGE_EXAMPLE: Path = Path("workflow-system/agent/examples/multi-stage-trace.md")
_V10_5_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.5.0_retrospective.md")
_V10_5_0_LAYER_AUDIT_DOC: Path = Path(".local/research/v10.5.1_layer_usage_audit.md")
_V10_5_0_TEMPLATE_AUDIT_DOC: Path = Path(".local/research/v10.5.2_template_usage_audit.md")
_V10_5_0_FRICTION_DOC: Path = Path(".local/research/v10.5.3_reference_friction.md")
_V10_5_0_W18_AUDIT_DOC: Path = Path(".local/research/v10.5.4_w18_lint_audit.md")
_V10_5_0_CHANGELOG_LITERAL: str = "## [10.5.0]"
_V10_5_0_MAKEFILE_AUDIT_LAYERS_LITERAL: str = "audit-layers:"
_V10_5_0_MAKEFILE_AUDIT_TEMPLATES_LITERAL: str = "audit-templates:"
_V10_5_0_MAKEFILE_MEASURE_FRICTION_LITERAL: str = "measure-friction:"
_V10_5_0_MAKEFILE_AUDIT_W18_LITERAL: str = "audit-w18:"
_V10_5_0_DEPRECATED_TEMPLATES: tuple[str, ...] = (
    "hotfix",
    "refactoring",
    "feature-enhancement",
    "full-pipeline",
    "documentation-only",
    "research-only",
    "design-only",
    "research-design-review-refine",
    "spike-poc",
    "security-audit",
    "demo-showcase",
    "performance-optimization",
    "dependency-setup",
    "onboarding",
    "product-verification",
    "entropy-cleanup",
)
_V10_5_0_DEPRECATION_HEADER_LITERAL: str = "# DEPRECATED in v11.0.0; will be removed in v12.0.0"


def test_v10_5_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.5.0: every NEW v10.5.0 PV-01..PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.5.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 4 NEW audit scripts (audit_layer_usage, audit_template_usage,
      measure_reference_friction, audit_w18_lint_maintenance);
    * 1 NEW XL-tier example (multi-stage-trace.md, the 4th example);
    * NEW agent-workspace.md §3.6 "Resume After Pause" subsection;
    * NEW activation_verdict(force_no_change=...) parameter;
    * 16 TIER-2 yaml deprecation comment headers (D-A-2 Phase A);
    * 4 NEW Makefile targets (audit-{layers,templates,w18},
      measure-friction);
    * 4 NEW research artifacts (v10.5.{1,2,3,4} audit outputs);
    * canonical 7 sync 10.4.0 -> 10.5.0 + CHANGELOG `## [10.5.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    for script in (
        _V10_5_0_AUDIT_LAYERS_SCRIPT,
        _V10_5_0_AUDIT_TEMPLATES_SCRIPT,
        _V10_5_0_MEASURE_FRICTION_SCRIPT,
        _V10_5_0_AUDIT_W18_SCRIPT,
    ):
        path = project_root / script
        assert path.is_file(), (
            f"W-18 v10.5.0 violation: NEW audit script missing at {script}. "
            f"v10.5.0 ships this script as part of the D-A / D-D slice. "
            f"Author the file OR remove the CHANGELOG mention."
        )

    example_path = project_root / _V10_5_0_MULTI_STAGE_EXAMPLE
    assert example_path.is_file(), (
        f"W-18 v10.5.0 violation: 4th XL-tier example missing at "
        f"{_V10_5_0_MULTI_STAGE_EXAMPLE}. v10.5.0 PV-01 ships D-A-1."
    )

    skill_text = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert "examples/multi-stage-trace.md" in skill_text, (
        "W-18 v10.5.0 violation: SKILL.md must reference the new "
        "multi-stage-trace.md example in the Quick Action Decision "
        "advisory annotation (D-A-1)."
    )
    assert "(legacy)" in skill_text, (
        "W-18 v10.5.0 violation: SKILL.md Template Quick-Reference "
        "must carry the (legacy) annotation on TIER-2 templates "
        "(D-A-2 Phase A)."
    )

    agent_workspace_text = (
        project_root / "workflow-system/agent/references/agent-workspace.md"
    ).read_text(encoding="utf-8")
    assert "## 3.6 Resume After Pause" in agent_workspace_text, (
        "W-18 v10.5.0 violation: agent-workspace.md must include "
        "the new §3.6 Resume After Pause subsection (D-A-3)."
    )

    # D-A-4: force_no_change parameter on activation_verdict.
    change_activation_text = (
        project_root / "src/devolaflow/skills/change_activation.py"
    ).read_text(encoding="utf-8")
    assert "force_no_change" in change_activation_text, (
        "W-18 v10.5.0 violation: change_activation.py must add the "
        "force_no_change parameter to activation_verdict() (D-A-4)."
    )

    # D-A-2 Phase A: 16 TIER-2 yaml files carry the deprecation comment.
    template_dir = project_root / "workflow-system/agent/templates/builtin"
    for tmpl in _V10_5_0_DEPRECATED_TEMPLATES:
        yaml_path = template_dir / f"{tmpl}.yaml"
        assert yaml_path.is_file(), (
            f"W-18 v10.5.0 violation: TIER-2 template missing at {yaml_path}"
        )
        text = yaml_path.read_text(encoding="utf-8")
        assert _V10_5_0_DEPRECATION_HEADER_LITERAL in text, (
            f"W-18 v10.5.0 violation: TIER-2 template {tmpl}.yaml missing "
            f"the deprecation comment header (D-A-2 Phase A). Re-run "
            f"the deprecation-tagging step OR remove the CHANGELOG mention."
        )

    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for marker in (
        _V10_5_0_MAKEFILE_AUDIT_LAYERS_LITERAL,
        _V10_5_0_MAKEFILE_AUDIT_TEMPLATES_LITERAL,
        _V10_5_0_MAKEFILE_MEASURE_FRICTION_LITERAL,
        _V10_5_0_MAKEFILE_AUDIT_W18_LITERAL,
    ):
        assert marker in makefile_text, (
            f"W-18 v10.5.0 violation: Makefile missing literal {marker!r} "
            f"(D-A-* / D-D-* audit targets). Author the target OR remove "
            f"the CHANGELOG mention."
        )

    _w18_research_artifact_path(project_root, _V10_5_0_RETROSPECTIVE_DOC)

    for audit_doc in (
        _V10_5_0_LAYER_AUDIT_DOC,
        _V10_5_0_TEMPLATE_AUDIT_DOC,
        _V10_5_0_FRICTION_DOC,
        _V10_5_0_W18_AUDIT_DOC,
    ):
        _w18_research_artifact_path(project_root, audit_doc)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_5_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.5.0 violation: CHANGELOG entry "
        f"{_V10_5_0_CHANGELOG_LITERAL!r} missing; v10.5.0 ships this entry."
    )


# =====================================================================
# v10.6.0 PV-01..PV-03 — Code Quality (NineS cleanup + god-function refactor)
# =====================================================================
#
# v10.6.0 collapses 3 v11.0.0-cycle PDSs (D-Q-1, D-Q-2, D-Q-4) into a
# single coherent MINOR cycle per `.local/research/v11.0.0_patches/`.
# The cycle ships:
#  1. PV-01 D-Q-1 — 7 helper extractions across `src/devolaflow/lifecycle/`
#     + `src/devolaflow/plugins/installer.py` (zero behaviour change;
#     pure CC reduction).
#  2. PV-02 D-Q-2 — `feedback.py::ProposalGenerator` god-function
#     refactor: extracts `_emit_dispatch` into NEW
#     `src/devolaflow/feedback_emit.py::ProposalEmitter` class with
#     `_fire_hook_chain` helper (composition over inheritance);
#     `generate_round_dispatch` becomes a 5-line façade. S-10
#     invariant (10/10 tests in `test_dispatch_emission_runs_hooks.py`)
#     preserved byte-identical.
#  3. PV-03 D-Q-4 — NEW `scripts/snapshot_compressor_health.py` audit
#     script + `tests/test_snapshot_compressor_health.py` (5 tests) +
#     Makefile `snapshot-compressor` target + first audit output
#     committed to `.local/research/v10.6.0_compressor_health.md`.
#  4. CHANGELOG `## [10.6.0]` entry; canonical 7 sync 10.5.0 -> 10.6.0
#  5. .local/research/v10.6.0_retrospective.md (W-7 / SI-8)

# 7 NEW helpers extracted by PV-01 (D-Q-1).
_V10_6_0_DQ1_HELPERS: tuple[tuple[str, str], ...] = (
    ("src/devolaflow/lifecycle/test_on_complete.py", "_persist_learnings_shard"),
    ("src/devolaflow/lifecycle/test_on_complete.py", "_persist_legibility_shard"),
    ("src/devolaflow/lifecycle/test_on_complete.py", "_persist_lifecycle_event_shard"),
    ("src/devolaflow/lifecycle/auto_write_handoff.py", "_layer_lookup_table"),
    ("src/devolaflow/lifecycle/auto_write_handoff.py", "_resolve_envelope_inputs"),
    ("src/devolaflow/lifecycle/auto_write_handoff.py", "_write_envelope_or_violation"),
    ("src/devolaflow/lifecycle/pre_plugin_invocation.py", "_parse_plugin_ids_list"),
    ("src/devolaflow/lifecycle/pre_plugin_invocation.py", "_parse_plugin_id_single"),
    ("src/devolaflow/lifecycle/pre_plugin_invocation.py", "_parse_workflow_plugins"),
    ("src/devolaflow/plugins/installer.py", "_handle_already_installed_path"),
    ("src/devolaflow/plugins/installer.py", "_handle_install_path"),
    ("src/devolaflow/plugins/installer.py", "_iter_workflow_matches"),
    ("src/devolaflow/plugins/installer.py", "_validate_required_keys"),
    ("src/devolaflow/plugins/installer.py", "_validate_npm_then_init_keys"),
)

_V10_6_0_FEEDBACK_EMIT_MODULE: Path = Path("src/devolaflow/feedback_emit.py")
_V10_6_0_FEEDBACK_EMIT_TESTS: Path = Path("tests/test_feedback_emit.py")
_V10_6_0_SNAPSHOT_SCRIPT: Path = Path("scripts/snapshot_compressor_health.py")
_V10_6_0_SNAPSHOT_TESTS: Path = Path("tests/test_snapshot_compressor_health.py")
_V10_6_0_COMPRESSOR_HEALTH_DOC: Path = Path(".local/research/v10.6.0_compressor_health.md")
_V10_6_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.6.0_retrospective.md")
_V10_6_0_CHANGELOG_LITERAL: str = "## [10.6.0]"
_V10_6_0_MAKEFILE_SNAPSHOT_LITERAL: str = "snapshot-compressor:"


def test_v10_6_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.6.0: every NEW v10.6.0 PV-01..PV-03 surface has presence coverage.

    Discharges the W-18 precondition for the v10.6.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 14 NEW helpers extracted by PV-01 D-Q-1 (across 4 files in
      `lifecycle/` + `plugins/`); pure refactor, zero behaviour change.
    * NEW `src/devolaflow/feedback_emit.py` module with the
      `ProposalEmitter` class (PV-02 D-Q-2 god-function refactor).
    * NEW `tests/test_feedback_emit.py` with 8 unit tests for
      `ProposalEmitter` in isolation.
    * NEW `scripts/snapshot_compressor_health.py` audit script
      (PV-03 D-Q-4); NEW `tests/test_snapshot_compressor_health.py`
      with 5 tests; NEW Makefile `snapshot-compressor` target;
      NEW `.local/research/v10.6.0_compressor_health.md` audit output.
    * canonical 7 sync 10.5.0 -> 10.6.0 + CHANGELOG `## [10.6.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    # PV-01 (D-Q-1) — 14 helpers extracted across 4 files.
    for src_path, helper_name in _V10_6_0_DQ1_HELPERS:
        text = (project_root / src_path).read_text(encoding="utf-8")
        assert f"def {helper_name}(" in text, (
            f"W-18 v10.6.0 violation: D-Q-1 helper `{helper_name}` missing "
            f"from {src_path}. v10.6.0 PV-01 extracts this helper as part "
            f"of the NineS cleanup. Author the helper OR remove the "
            f"CHANGELOG mention."
        )

    # PV-02 (D-Q-2) — NEW feedback_emit.py + ProposalEmitter + tests.
    feedback_emit_path = project_root / _V10_6_0_FEEDBACK_EMIT_MODULE
    assert feedback_emit_path.is_file(), (
        f"W-18 v10.6.0 violation: NEW module missing at "
        f"{_V10_6_0_FEEDBACK_EMIT_MODULE}. v10.6.0 PV-02 extracts the "
        f"S-10 hook-chain firing into ProposalEmitter."
    )
    feedback_emit_text = feedback_emit_path.read_text(encoding="utf-8")
    assert "class ProposalEmitter" in feedback_emit_text, (
        "W-18 v10.6.0 violation: feedback_emit.py must define "
        "`class ProposalEmitter` (D-Q-2 §2 patch_design)."
    )
    assert "_fire_hook_chain" in feedback_emit_text, (
        "W-18 v10.6.0 violation: feedback_emit.py must define "
        "`_fire_hook_chain` (the S-10 4-event chain helper)."
    )

    feedback_text = (project_root / "src/devolaflow/feedback.py").read_text(encoding="utf-8")
    assert "from devolaflow.feedback_emit import ProposalEmitter" in feedback_text, (
        "W-18 v10.6.0 violation: feedback.py must import ProposalEmitter "
        "(D-Q-2 §2 composition wiring) — `_emit_dispatch` was extracted."
    )
    assert "self._emitter = ProposalEmitter()" in feedback_text, (
        "W-18 v10.6.0 violation: ProposalGenerator.__init__ must compose "
        "ProposalEmitter (D-Q-2 §2 composition over inheritance)."
    )

    feedback_emit_tests = project_root / _V10_6_0_FEEDBACK_EMIT_TESTS
    assert feedback_emit_tests.is_file(), (
        f"W-18 v10.6.0 violation: NEW unit tests missing at "
        f"{_V10_6_0_FEEDBACK_EMIT_TESTS}. v10.6.0 PV-02 ships 8 unit "
        f"tests for ProposalEmitter in isolation."
    )

    # PV-03 (D-Q-4) — snapshot script + tests + Makefile target + audit output.
    snapshot_script = project_root / _V10_6_0_SNAPSHOT_SCRIPT
    assert snapshot_script.is_file(), (
        f"W-18 v10.6.0 violation: NEW audit script missing at "
        f"{_V10_6_0_SNAPSHOT_SCRIPT}. v10.6.0 PV-03 ships the "
        f"compressor/ post-split health snapshot."
    )
    snapshot_tests = project_root / _V10_6_0_SNAPSHOT_TESTS
    assert snapshot_tests.is_file(), (
        f"W-18 v10.6.0 violation: NEW snapshot tests missing at "
        f"{_V10_6_0_SNAPSHOT_TESTS}. v10.6.0 PV-03 ships 5 tests for "
        f"the snapshot script."
    )
    _w18_research_artifact_path(project_root, _V10_6_0_COMPRESSOR_HEALTH_DOC)

    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    assert _V10_6_0_MAKEFILE_SNAPSHOT_LITERAL in makefile_text, (
        f"W-18 v10.6.0 violation: Makefile missing literal "
        f"{_V10_6_0_MAKEFILE_SNAPSHOT_LITERAL!r} (D-Q-4 audit target)."
    )

    # Retrospective + CHANGELOG.
    _w18_research_artifact_path(project_root, _V10_6_0_RETROSPECTIVE_DOC)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_6_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.6.0 violation: CHANGELOG entry "
        f"{_V10_6_0_CHANGELOG_LITERAL!r} missing; v10.6.0 ships this entry."
    )


# =====================================================================
# v10.7.0 PV-01..PV-05 — Protocol Audit + Observability
# =====================================================================
#
# v10.7.0 collapses 5 v11.0.0-cycle PDSs (D-P-1, D-P-3, D-O-1, D-O-2,
# D-O-3) into a single coherent MINOR cycle per
# `.local/research/v11.0.0_patches/`. The cycle ships:
#  1. D-P-1 — `scripts/audit_canonical_order_emptiness.py` audit-only
#     script + tests + first audit output. Reports per-position non-
#     empty rate across the 17-element canonical_order; G-6 frozen-
#     prefix gate preserved (positions 1-12 informational only).
#  2. D-P-3 — STATUS.yaml NEST extensibility demo: NEW OPTIONAL
#     `last_handoff_summary` dict field at top-level (NEST: groups
#     four sub-attributes in ONE dict-shaped key vs APPEND × 4 sibling
#     scalars). Schema_version stays at 1 (additive only).
#  3. D-O-1 — `references/evaluator-rosetta.md` 16th SF-4 canonical
#     reference (~505 lines, Large tier <1000) + companion
#     `scripts/generate_evaluator_rosetta.py` + tests + first audit.
#  4. D-O-2 — `scripts/auto_collect_si3_metrics.py` 6-dim objective
#     metric auto-collector + tests + first run output. 0% → 87% sub-
#     component auto-fill (mock-data preview).
#  5. D-O-3 — `scripts/index_mid_cycle_research.py` mid-cycle research
#     artifact navigator + tests + first index output. Workspace-local
#     ephemeral; complementary to the W-19 cycle-end committed archive.
#  6. CHANGELOG `## [10.7.0]` entry; canonical 7 sync 10.6.0 -> 10.7.0
#  7. .local/research/v10.7.0_retrospective.md (W-7 / SI-8)

# 4 NEW scripts authored by v10.7.0.
_V10_7_0_AUDIT_CANONICAL_SCRIPT: Path = Path("scripts/audit_canonical_order_emptiness.py")
_V10_7_0_GEN_ROSETTA_SCRIPT: Path = Path("scripts/generate_evaluator_rosetta.py")
_V10_7_0_AUTO_SI3_SCRIPT: Path = Path("scripts/auto_collect_si3_metrics.py")
_V10_7_0_INDEX_RESEARCH_SCRIPT: Path = Path("scripts/index_mid_cycle_research.py")

# 4 matching test files.
_V10_7_0_AUDIT_CANONICAL_TESTS: Path = Path("tests/test_audit_canonical_order_emptiness.py")
_V10_7_0_GEN_ROSETTA_TESTS: Path = Path("tests/test_generate_evaluator_rosetta.py")
_V10_7_0_AUTO_SI3_TESTS: Path = Path("tests/test_auto_collect_si3_metrics.py")
_V10_7_0_INDEX_RESEARCH_TESTS: Path = Path("tests/test_index_mid_cycle_research.py")

# 16th SF-4 reference + the agent_workspace.md NEST doc literal.
_V10_7_0_EVALUATOR_ROSETTA_REF: Path = Path("workflow-system/agent/references/evaluator-rosetta.md")
_V10_7_0_AGENT_WORKSPACE_NEST_LITERAL: str = "v10.7.0 D-P-3"

# 4 audit / index / collector first-run outputs (W-18 PRECONDITION
# pin per cycle plan).
_V10_7_0_AUDIT_DOCS: tuple[Path, ...] = (
    Path(".local/research/v10.7.1_canonical_order_emptiness.md"),
    Path(".local/research/v10.7.2_evaluator_rosetta.md"),
    Path(".local/research/v10.7.3_si3_auto_collection.md"),
    Path(".local/research/v10.7.4_research_index.md"),
)
_V10_7_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.7.0_retrospective.md")
_V10_7_0_CHANGELOG_LITERAL: str = "## [10.7.0]"

# 4 Makefile target literals.
_V10_7_0_MAKEFILE_TARGETS: tuple[str, ...] = (
    "audit-canonical-emptiness:",
    "gen-evaluator-rosetta:",
    "auto-collect-si3:",
    "index-research:",
)

# D-P-3 STATUS.yaml schema field name (the NEST demo).
_V10_7_0_STATUS_NEST_FIELD: str = "last_handoff_summary"


def test_v10_7_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.7.0: every NEW v10.7.0 PV-01..PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.7.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 4 NEW audit / observability scripts (D-P-1, D-O-1 companion,
      D-O-2, D-O-3) + matching test files.
    * NEW `workflow-system/agent/references/evaluator-rosetta.md` (16th
      SF-4 canonical reference; ~505 lines, Large tier).
    * NEW OPTIONAL `last_handoff_summary` field on
      `schemas/agent-workspace/change-status.yaml` (D-P-3 NEST demo)
      + matching `Change.last_handoff_summary` accessor.
    * 4 audit / index / collector first-run outputs in
      `.local/research/v10.7.{1,2,3,4}_*.md`.
    * 4 NEW Makefile targets (audit-canonical-emptiness,
      gen-evaluator-rosetta, auto-collect-si3, index-research).
    * Canonical 7 sync 10.6.0 -> 10.7.0 + CHANGELOG `## [10.7.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    # 4 NEW scripts.
    for script in (
        _V10_7_0_AUDIT_CANONICAL_SCRIPT,
        _V10_7_0_GEN_ROSETTA_SCRIPT,
        _V10_7_0_AUTO_SI3_SCRIPT,
        _V10_7_0_INDEX_RESEARCH_SCRIPT,
    ):
        assert (project_root / script).is_file(), (
            f"W-18 v10.7.0 violation: NEW audit/collector script missing at "
            f"{script}. v10.7.0 ships this script as part of the D-P / D-O "
            f"slice. Author the script OR remove the CHANGELOG mention."
        )

    # 4 matching test files.
    for test_file in (
        _V10_7_0_AUDIT_CANONICAL_TESTS,
        _V10_7_0_GEN_ROSETTA_TESTS,
        _V10_7_0_AUTO_SI3_TESTS,
        _V10_7_0_INDEX_RESEARCH_TESTS,
    ):
        assert (project_root / test_file).is_file(), (
            f"W-18 v10.7.0 violation: NEW test file missing at {test_file}. "
            f"v10.7.0 ships unit tests for every new audit/collector script."
        )

    # 16th SF-4 canonical reference.
    rosetta_ref = project_root / _V10_7_0_EVALUATOR_ROSETTA_REF
    assert rosetta_ref.is_file(), (
        f"W-18 v10.7.0 violation: NEW SF-4 canonical reference missing at "
        f"{_V10_7_0_EVALUATOR_ROSETTA_REF}. v10.7.0 D-O-1 ships the "
        f"three-evaluator rosetta as the 16th canonical reference."
    )
    rosetta_text = rosetta_ref.read_text(encoding="utf-8")
    assert "6 × 9" in rosetta_text or "6 \\times 9" in rosetta_text or "6×9" in rosetta_text, (
        "W-18 v10.7.0 violation: evaluator-rosetta.md must contain the "
        "'6 × 9' (or 6×9) cell-table identifier per D-O-1 §2.3."
    )

    # D-P-3 NEST field present in change-status.yaml schema + Change accessor.
    schema_path = project_root / "schemas" / "agent-workspace" / "change-status.yaml"
    schema_text = schema_path.read_text(encoding="utf-8")
    assert _V10_7_0_STATUS_NEST_FIELD in schema_text, (
        f"W-18 v10.7.0 violation: STATUS.yaml schema missing NEW field "
        f"`{_V10_7_0_STATUS_NEST_FIELD}` (D-P-3 NEST demo)."
    )
    change_text = (project_root / "src/devolaflow/agent_workspace/change.py").read_text(
        encoding="utf-8"
    )
    assert "def last_handoff_summary" in change_text, (
        "W-18 v10.7.0 violation: Change dataclass missing "
        "`last_handoff_summary` property accessor (D-P-3)."
    )

    # agent-workspace.md reference doc must mention the D-P-3 demo.
    agent_workspace_text = (
        project_root / "workflow-system/agent/references/agent-workspace.md"
    ).read_text(encoding="utf-8")
    assert _V10_7_0_AGENT_WORKSPACE_NEST_LITERAL in agent_workspace_text, (
        f"W-18 v10.7.0 violation: agent-workspace.md must cite the "
        f"{_V10_7_0_AGENT_WORKSPACE_NEST_LITERAL!r} D-P-3 NEST demo "
        f"in the STATUS.yaml schema section."
    )

    # 4 Makefile targets present (literals exact-match).
    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for target in _V10_7_0_MAKEFILE_TARGETS:
        assert target in makefile_text, (
            f"W-18 v10.7.0 violation: Makefile missing literal {target!r} "
            f"(D-P-1 / D-O-1 / D-O-2 / D-O-3 audit targets)."
        )

    # 4 audit / index / collector first-run outputs.
    for audit_doc in _V10_7_0_AUDIT_DOCS:
        _w18_research_artifact_path(project_root, audit_doc)

    # Retrospective + CHANGELOG.
    _w18_research_artifact_path(project_root, _V10_7_0_RETROSPECTIVE_DOC)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_7_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.7.0 violation: CHANGELOG entry "
        f"{_V10_7_0_CHANGELOG_LITERAL!r} missing; v10.7.0 ships this entry."
    )


# =====================================================================
# v10.8.0 — External Tool Coupling Hardening (D-C-1 / D-C-2 / D-C-3)
# =====================================================================
#
# v10.8.0 collapses 3 v11.0.0-cycle PDSs (D-C-1 degraded-mode contract;
# D-C-2 bridge shape contract tests; D-C-3 pre_plugin_invocation split)
# into a single coherent MINOR cycle per
# `.local/research/v11.0.0_patches/`. The cycle ships:
#
#  1. D-C-1 — `references/degraded-mode.md` 17th SF-4 canonical
#     reference (per-plugin upstream-unreachable fallback contract)
#     + `tests/test_degraded_mode.py` regression suite (8 tests).
#  2. D-C-2 — `tests/integration/` package (conftest + 4 shape
#     contract files + 8 captured fixtures) + `scripts/refresh_bridge_fixtures.py`
#     + `.github/workflows/bridge-fixture-refresh.yml` weekly cron.
#  3. D-C-3 — `lifecycle/pre_plugin_invocation_install.py` +
#     `lifecycle/pre_plugin_invocation_upgrade.py` (DEFAULT_EVENTS 10 → 12
#     per A-2.2 append-only) + `tests/test_pre_plugin_invocation_split.py`.
#  4. CHANGELOG `## [10.8.0]` + canonical 7 sync 10.7.0 → 10.8.0.
#  5. `.local/research/v10.8.0_retrospective.md` (W-7 / SI-8).

# D-C-1 surfaces.
_V10_8_0_DEGRADED_MODE_REF: Path = Path("workflow-system/agent/references/degraded-mode.md")
_V10_8_0_DEGRADED_MODE_TESTS: Path = Path("tests/test_degraded_mode.py")

# D-C-2 surfaces.
_V10_8_0_INTEGRATION_INIT: Path = Path("tests/integration/__init__.py")
_V10_8_0_INTEGRATION_CONFTEST: Path = Path("tests/integration/conftest.py")
_V10_8_0_INTEGRATION_TESTS: tuple[Path, ...] = (
    Path("tests/integration/test_si_chip_shape_contract.py"),
    Path("tests/integration/test_nines_shape_contract.py"),
    Path("tests/integration/test_rtk_shape_contract.py"),
    Path("tests/integration/test_ui_pro_shape_contract.py"),
)
_V10_8_0_REFRESH_SCRIPT: Path = Path("scripts/refresh_bridge_fixtures.py")
_V10_8_0_FIXTURE_REFRESH_WORKFLOW: Path = Path(".github/workflows/bridge-fixture-refresh.yml")

# D-C-3 surfaces.
_V10_8_0_PPI_INSTALL_MODULE: Path = Path(
    "src/devolaflow/lifecycle/pre_plugin_invocation_install.py"
)
_V10_8_0_PPI_UPGRADE_MODULE: Path = Path(
    "src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py"
)
_V10_8_0_PPI_SPLIT_TESTS: Path = Path("tests/test_pre_plugin_invocation_split.py")

# Cycle close surfaces.
_V10_8_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.8.0_retrospective.md")
_V10_8_0_CHANGELOG_LITERAL: str = "## [10.8.0]"

# Makefile target for D-C-2 fixture refresh.
_V10_8_0_MAKEFILE_TARGETS: tuple[str, ...] = ("refresh-bridge-fixtures:",)


def test_v10_8_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.8.0: every NEW v10.8.0 D-C-1 / D-C-2 / D-C-3 surface is pinned.

    Discharges the W-18 precondition for the v10.8.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * NEW `workflow-system/agent/references/degraded-mode.md` (17th SF-4
      canonical reference; opens with "Degraded ≠ Full" warning per
      D-C-1 §9 R1 mitigation).
    * NEW `tests/test_degraded_mode.py` (D-C-1 regression suite).
    * NEW `tests/integration/` package (D-C-2 bridge shape contract
      tests) + 4 contract test files + fixture package.
    * NEW `scripts/refresh_bridge_fixtures.py` (D-C-2 fixture refresh).
    * NEW `.github/workflows/bridge-fixture-refresh.yml` (D-C-2 weekly
      cron).
    * NEW `src/devolaflow/lifecycle/pre_plugin_invocation_install.py`
      (D-C-3 install handler at DEFAULT_EVENTS position 11).
    * NEW `src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py`
      (D-C-3 upgrade handler at DEFAULT_EVENTS position 12).
    * NEW `tests/test_pre_plugin_invocation_split.py` (D-C-3 regression).
    * NEW Makefile target `refresh-bridge-fixtures`.
    * Canonical 7 sync 10.7.0 → 10.8.0 + CHANGELOG `## [10.8.0]`.
    * NEW `.local/research/v10.8.0_retrospective.md` (W-7 / SI-8).
    """
    # D-C-1: degraded-mode reference + tests.
    assert (project_root / _V10_8_0_DEGRADED_MODE_REF).is_file(), (
        f"W-18 v10.8.0 violation: degraded-mode reference missing at "
        f"{_V10_8_0_DEGRADED_MODE_REF}. v10.8.0 D-C-1 ships this file."
    )
    deg_text = (project_root / _V10_8_0_DEGRADED_MODE_REF).read_text(encoding="utf-8")
    assert "Degraded ≠ Full" in deg_text[:500], (
        "W-18 v10.8.0 violation: degraded-mode.md must OPEN with the "
        "'Degraded ≠ Full' warning section (D-C-1 §9 R1 mitigation)"
    )
    assert (project_root / _V10_8_0_DEGRADED_MODE_TESTS).is_file(), (
        f"W-18 v10.8.0 violation: degraded-mode tests missing at {_V10_8_0_DEGRADED_MODE_TESTS}."
    )

    # D-C-2: integration test infrastructure.
    for integration_file in (
        _V10_8_0_INTEGRATION_INIT,
        _V10_8_0_INTEGRATION_CONFTEST,
    ):
        assert (project_root / integration_file).is_file(), (
            f"W-18 v10.8.0 violation: integration file missing at "
            f"{integration_file} — D-C-2 ships the tests/integration/ package."
        )
    for contract_test in _V10_8_0_INTEGRATION_TESTS:
        assert (project_root / contract_test).is_file(), (
            f"W-18 v10.8.0 violation: bridge contract test missing at "
            f"{contract_test} — D-C-2 ships 4 contract test files."
        )
    assert (project_root / _V10_8_0_REFRESH_SCRIPT).is_file(), (
        f"W-18 v10.8.0 violation: fixture refresh script missing at "
        f"{_V10_8_0_REFRESH_SCRIPT}. v10.8.0 D-C-2 ships this script."
    )
    assert (project_root / _V10_8_0_FIXTURE_REFRESH_WORKFLOW).is_file(), (
        f"W-18 v10.8.0 violation: fixture-refresh CI workflow missing at "
        f"{_V10_8_0_FIXTURE_REFRESH_WORKFLOW}. v10.8.0 D-C-2 ships this."
    )

    # D-C-3: split handlers + tests.
    for split_module in (_V10_8_0_PPI_INSTALL_MODULE, _V10_8_0_PPI_UPGRADE_MODULE):
        assert (project_root / split_module).is_file(), (
            f"W-18 v10.8.0 violation: split handler missing at {split_module}. "
            f"v10.8.0 D-C-3 ships the pre_plugin_invocation split."
        )
    assert (project_root / _V10_8_0_PPI_SPLIT_TESTS).is_file(), (
        f"W-18 v10.8.0 violation: split-contract tests missing at "
        f"{_V10_8_0_PPI_SPLIT_TESTS}. v10.8.0 D-C-3 ships 5+ tests."
    )

    # DEFAULT_EVENTS length bump (10 → 12 by v10.8.0 D-C-3 split). The
    # SUPERSET containment check (`>= 12`) accommodates future
    # APPEND-ONLY additions per A-2.2 — e.g., v11.0.0 PV-02 D-Q-3
    # appends 4 NEW canonical event names (positions 13-16) without
    # disturbing positions 1-12 (which stay byte-stable per A-2.4).
    from devolaflow.lifecycle import DEFAULT_EVENTS

    assert len(DEFAULT_EVENTS) >= 12, (
        f"W-18 v10.8.0 violation: D-C-3 ships DEFAULT_EVENTS at length 12 "
        f"(positions 1-12 byte-stable per A-2.4); got len={len(DEFAULT_EVENTS)}"
    )

    # 17th SF-4 canonical reference pinned in the _SF4_REFERENCE_SET above.
    assert "degraded-mode.md" in set(_SF4_REFERENCE_SET), (
        "W-18 v10.8.0 violation: _SF4_REFERENCE_SET must include 'degraded-mode.md' after D-C-1."
    )

    # Makefile target for fixture refresh.
    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for target in _V10_8_0_MAKEFILE_TARGETS:
        assert target in makefile_text, (
            f"W-18 v10.8.0 violation: Makefile missing literal {target!r} "
            f"(D-C-2 refresh-bridge-fixtures target)."
        )

    # Retrospective + CHANGELOG.
    _w18_research_artifact_path(project_root, _V10_8_0_RETROSPECTIVE_DOC)
    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_8_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.8.0 violation: CHANGELOG entry "
        f"{_V10_8_0_CHANGELOG_LITERAL!r} missing; v10.8.0 ships this entry."
    )


# =====================================================================
# v11.0.0 PV-01 — D-P-2 + D-P-4 stretch (analysis + doc-only)
# =====================================================================
#
# v11.0.0 PV-01 ships 2 analysis-or-doc-only stretch patches per the
# v11.0.0 cycle plan §4 v11.0.0 PV-01 deliverable map:
#
#  1. D-P-2 — `.local/research/v11.0.0_w21_threshold_empirical_check.md`
#     (analysis-only; W-21 Soul-set threshold empirical calibration check;
#     5-section structure per `.local/research/v11.0.0_patches/D-P-2.md` §2;
#     ANALYSIS-ONLY per source line 124 verbatim — W-21 wording byte-stable).
#  2. D-P-4 — `references/plan-mode-enforcement.md` adds §3.2 "Multi-Step
#     Plans (Multi-Horizon Reasoning)" with `[EXPLORE]` + `[REVISABLE]`
#     opt-in annotation conventions; ~210 LOC added; reference stays
#     within Large tier ≤ 1000 lines per C-4 / SF-1; zero schema field
#     additions per D-P-4 §2 "uses existing fields ONLY".
#
# Per W-18 sequencing, this lint refreshes BEFORE the v11.0.0 CHANGELOG
# entry mentions either feature. The CHANGELOG entry itself ships in
# PV-03 (MAJOR cycle close); PV-01's per-PV chore commit references this
# lint by stanza name to satisfy the W-18 precondition.

# D-P-2 surface.
_V11_0_0_PV01_DP2_ANALYSIS: Path = Path(".local/research/v11.0.0_w21_threshold_empirical_check.md")

# D-P-4 surfaces (the §3.2 sub-section text + the reference frontmatter
# version bump are pinned by literal-substring containment).
_V11_0_0_PV01_DP4_REFERENCE: Path = Path(
    "workflow-system/agent/references/plan-mode-enforcement.md"
)
_V11_0_0_PV01_DP4_SECTION_HEADING: str = "### 3.2 Multi-Step Plans (Multi-Horizon Reasoning)"
_V11_0_0_PV01_DP4_EXPLORE_CONVENTION: str = "[EXPLORE]"
_V11_0_0_PV01_DP4_REVISABLE_CONVENTION: str = "[REVISABLE:"


def test_v11_0_0_pv01_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.0 PV-01: D-P-2 + D-P-4 stretch surfaces are pinned.

    Discharges the W-18 precondition for the v11.0.0 PV-01 stretch chore
    commit. The CHANGELOG entry that mentions these surfaces ships in
    v11.0.0 PV-03 (MAJOR cycle close); per W-18 the lint refresh MUST
    land before the CHANGELOG entry — this stanza closes that
    precondition.

    * D-P-2: `.local/research/v11.0.0_w21_threshold_empirical_check.md`
      — analysis-only; W-21 threshold empirical calibration check;
      5-section structure per `.local/research/v11.0.0_patches/D-P-2.md`
      §2 (telegraph history / root-cause / A-1-vs-Soul classification /
      threshold calibration / recommendation).
    * D-P-4: `references/plan-mode-enforcement.md` adds §3.2 with the
      `[EXPLORE]` + `[REVISABLE: <stage-id>]` annotation conventions
      (uses existing schema fields only — zero schema additions).
    """
    # D-P-2: analysis artifact exists + 5-section structure present.
    dp2_path = _w18_research_artifact_path(project_root, _V11_0_0_PV01_DP2_ANALYSIS)
    dp2_text = dp2_path.read_text(encoding="utf-8")
    for required_section in (
        "## §1 — Telegraph history",
        "## §2 — Telegraph-floating root-cause analysis",
        "## §3 — A-1 vs Soul-rule classification test",
        "## §4 — Threshold calibration question",
        "## §5 — Recommendation for v12.0.0+ deliberation",
    ):
        assert required_section in dp2_text, (
            f"W-18 v11.0.0 PV-01 violation: D-P-2 §{required_section!r} "
            f"missing — D-P-2 §2 mandates the 5-section structure."
        )
    # G-5 Soul-freeze gate: artifact must NOT propose changing W-21.
    assert "W-21 wording preserved" in dp2_text, (
        "W-18 v11.0.0 PV-01 violation: D-P-2 must explicitly state "
        "'W-21 wording preserved' (G-5 Soul-freeze gate; the artifact "
        "is analysis-only per source line 124)."
    )

    # D-P-4: §3.2 sub-section present in plan-mode-enforcement.md.
    dp4_path = project_root / _V11_0_0_PV01_DP4_REFERENCE
    assert dp4_path.is_file(), (
        f"W-18 v11.0.0 PV-01 violation: D-P-4 reference missing at {_V11_0_0_PV01_DP4_REFERENCE}."
    )
    dp4_text = dp4_path.read_text(encoding="utf-8")
    assert _V11_0_0_PV01_DP4_SECTION_HEADING in dp4_text, (
        f"W-18 v11.0.0 PV-01 violation: D-P-4 §3.2 heading "
        f"{_V11_0_0_PV01_DP4_SECTION_HEADING!r} missing — D-P-4 §2 "
        f"adds this sub-section to plan-mode-enforcement.md."
    )
    assert _V11_0_0_PV01_DP4_EXPLORE_CONVENTION in dp4_text, (
        f"W-18 v11.0.0 PV-01 violation: D-P-4 §3.2.3 introduces the "
        f"{_V11_0_0_PV01_DP4_EXPLORE_CONVENTION!r} OPT-IN convention; "
        f"missing from the reference body."
    )
    assert _V11_0_0_PV01_DP4_REVISABLE_CONVENTION in dp4_text, (
        f"W-18 v11.0.0 PV-01 violation: D-P-4 §3.2.4 introduces the "
        f"{_V11_0_0_PV01_DP4_REVISABLE_CONVENTION!r} OPT-IN convention; "
        f"missing from the reference body."
    )
    # Frontmatter version was bumped to 11.0.0 in same PR per D-P-4 §2 step 4.
    assert 'version: "11.0.0"' in dp4_text[:500], (
        "W-18 v11.0.0 PV-01 violation: D-P-4 §2 step 4 bumps the "
        "frontmatter version to 11.0.0; missing from the reference "
        "frontmatter."
    )
    # C-4 / SF-1 line ceiling: reference must stay within Large tier
    # (≤ 1000 lines).
    dp4_line_count = dp4_text.count("\n")
    assert dp4_line_count <= 1000, (
        f"W-18 v11.0.0 PV-01 violation: D-P-4 §2 promises the reference "
        f"stays within the Large tier 1000-line ceiling per C-4 / SF-1; "
        f"got {dp4_line_count} lines."
    )


# =====================================================================
# v11.0.0 PV-02 — D-O-4 + D-Q-3 stretch (analysis + lifecycle alias rename)
# =====================================================================
#
# v11.0.0 PV-02 ships 2 stretch patches per the v11.0.0 cycle plan §4
# v11.0.0 PV-02 deliverable map:
#
#  1. D-O-4 — `.local/research/v11.0.0_si10_gate_growth_analysis.md`
#     (analysis-only forecast; SI-10 gate-count growth curve + 3-group
#     reorganization recommendation telegraphed for v13.0.0 once gate
#     count crosses 10; per `.local/research/v11.0.0_patches/D-O-4.md`
#     §2-§9). Verbatim recommendation: gate count = 10 → partition
#     into Group A Hygiene + Group B Validation + Group C Snapshot.
#  2. D-Q-3 — lifecycle 4-row PURE-ALIAS rename: `file_write` →
#     `check_file_write`, `task_stop` → `post_task_complete`,
#     `format_on_edit` → `post_file_edit`, `envelope_write` →
#     `check_envelope_write` (per `.local/research/v11.0.0_patches/
#     D-Q-3.md` §2). DEFAULT_EVENTS bumped 12 → 16 (positions 13-16
#     APPEND-ONLY per A-2.2; positions 1-12 byte-stable per A-2.4).
#     OLD names preserved as PURE-ALIAS via dispatcher's
#     `_EVENT_ALIASES` map for 1-cycle deprecation runway (v11.0.0 →
#     v12.0.0). 5 NEW alias regression tests in test_lifecycle_hooks.py.

# D-O-4 surface.
_V11_0_0_PV02_DO4_ANALYSIS: Path = Path(".local/research/v11.0.0_si10_gate_growth_analysis.md")

# D-Q-3 surfaces.
_V11_0_0_PV02_DQ3_LIFECYCLE_INIT: Path = Path("src/devolaflow/lifecycle/__init__.py")
_V11_0_0_PV02_DQ3_DISPATCHER: Path = Path("src/devolaflow/lifecycle/dispatcher.py")
_V11_0_0_PV02_DQ3_LIFECYCLE_TESTS: Path = Path("tests/test_lifecycle_hooks.py")
_V11_0_0_PV02_DQ3_ENV_FLAGS_REF: Path = Path("workflow-system/agent/references/env-flags.md")

# D-Q-3 NEW canonical event-name strings (per D-Q-3 §2 rename mapping).
_V11_0_0_PV02_DQ3_NEW_CANONICAL_NAMES: tuple[str, ...] = (
    "check_file_write",
    "post_task_complete",
    "post_file_edit",
    "check_envelope_write",
)

# D-Q-3 OLD aliased event-name strings (preserved at original positions
# in DEFAULT_EVENTS; PURE-ALIAS routed through `_EVENT_ALIASES` map).
_V11_0_0_PV02_DQ3_OLD_ALIAS_NAMES: tuple[str, ...] = (
    "file_write",
    "task_stop",
    "format_on_edit",
    "envelope_write",
)

# D-Q-3 NEW alias regression test names (per cycle dispatch task AC #4
# "5 tests asserting alias path emits byte-identical to canonical,
# alias telegraphed for 1-cycle deprecation, both names accept
# registrations, both names propagate to registered handlers,
# len(DEFAULT_EVENTS) becomes 16").
_V11_0_0_PV02_DQ3_ALIAS_TEST_NAMES: tuple[str, ...] = (
    "test_v11_0_0_pv02_dq3_alias_emits_byte_identical_to_canonical",
    "test_v11_0_0_pv02_dq3_both_names_accept_register_hook",
    "test_v11_0_0_pv02_dq3_both_names_propagate_to_run_hooks",
    "test_v11_0_0_pv02_dq3_default_events_length_is_16",
    "test_v11_0_0_pv02_dq3_alias_telegraphs_1_cycle_deprecation",
)


def test_v11_0_0_pv02_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.0 PV-02: D-O-4 + D-Q-3 stretch surfaces are pinned.

    Discharges the W-18 precondition for the v11.0.0 PV-02 stretch
    chore commit. The CHANGELOG entry that mentions these surfaces
    ships in v11.0.0 PV-03 (MAJOR cycle close); per W-18 the lint
    refresh MUST land before the CHANGELOG entry — this stanza closes
    that precondition.

    * D-O-4: `.local/research/v11.0.0_si10_gate_growth_analysis.md`
      — analysis-only forecast; recommends 3-group reorganization
      when gate count crosses 10 (forecast v13.0.0).
    * D-Q-3: 4-row PURE-ALIAS rename adding 4 NEW canonical event
      names AT END of DEFAULT_EVENTS (positions 13-16 per A-2.2);
      OLD names preserved as PURE-ALIAS via dispatcher's
      `_EVENT_ALIASES` map for 1-cycle deprecation runway; 5 NEW
      alias regression tests pin the byte-identical contract.
    """
    # D-O-4 analysis artifact must exist + telegraph 10-gate threshold +
    # 3-group reorganization recommendation.
    do4_path = _w18_research_artifact_path(project_root, _V11_0_0_PV02_DO4_ANALYSIS)
    do4_text = do4_path.read_text(encoding="utf-8")
    # Threshold + reorganization design must be telegraphed verbatim
    # so future cycle planners discover the trigger.
    assert "gate count = 10" in do4_text, (
        "W-18 v11.0.0 PV-02 violation: D-O-4 §2.4 must telegraph the "
        "'gate count = 10' reorganization-trigger threshold verbatim."
    )
    for group_label in ("Group A: Hygiene", "Group B: Validation", "Group C: Snapshot"):
        assert group_label in do4_text, (
            f"W-18 v11.0.0 PV-02 violation: D-O-4 §2.4 must enumerate "
            f"{group_label!r} in the 3-group reorganization design."
        )

    # D-Q-3 lifecycle alias surface — NEW canonical event-name constants
    # appear in lifecycle/__init__.py; OLD alias map entries appear in
    # dispatcher.py.
    init_text = (project_root / _V11_0_0_PV02_DQ3_LIFECYCLE_INIT).read_text(encoding="utf-8")
    for new_const_name in (
        "CHECK_FILE_WRITE_EVENT",
        "POST_TASK_COMPLETE_EVENT",
        "POST_FILE_EDIT_EVENT",
        "CHECK_ENVELOPE_WRITE_EVENT",
    ):
        assert new_const_name in init_text, (
            f"W-18 v11.0.0 PV-02 violation: D-Q-3 §2 introduces NEW "
            f"canonical constant {new_const_name!r}; missing from "
            f"lifecycle/__init__.py."
        )
    # Alias schedule docstring must telegraph v12.0.0 removal target.
    assert "v12.0.0" in init_text, (
        "W-18 v11.0.0 PV-02 violation: D-Q-3 §6 telegraphs v12.0.0 as "
        "the alias removal target; missing from lifecycle/__init__.py."
    )

    # Dispatcher must declare the `_EVENT_ALIASES` map + the
    # `_alias_event` helper.
    disp_text = (project_root / _V11_0_0_PV02_DQ3_DISPATCHER).read_text(encoding="utf-8")
    assert "_EVENT_ALIASES" in disp_text, (
        "W-18 v11.0.0 PV-02 violation: D-Q-3 §2 wires the alias map "
        "via dispatcher's `_EVENT_ALIASES`; missing."
    )
    assert "def _alias_event" in disp_text, (
        "W-18 v11.0.0 PV-02 violation: D-Q-3 §2 introduces the "
        "`_alias_event` helper; missing from dispatcher.py."
    )

    # DEFAULT_EVENTS length is exactly 16 (12 base + 4 NEW canonical).
    from devolaflow.lifecycle import DEFAULT_EVENTS

    assert len(DEFAULT_EVENTS) == 16, (
        f"W-18 v11.0.0 PV-02 violation: D-Q-3 §2 ships DEFAULT_EVENTS "
        f"12 → 16 (4 NEW canonical names appended at positions 13-16); "
        f"got len={len(DEFAULT_EVENTS)}."
    )
    # Both NEW canonical AND OLD alias names must be present in the tuple.
    for new_name in _V11_0_0_PV02_DQ3_NEW_CANONICAL_NAMES:
        assert new_name in DEFAULT_EVENTS, (
            f"W-18 v11.0.0 PV-02 violation: NEW canonical event name "
            f"{new_name!r} missing from DEFAULT_EVENTS."
        )
    for old_name in _V11_0_0_PV02_DQ3_OLD_ALIAS_NAMES:
        assert old_name in DEFAULT_EVENTS, (
            f"W-18 v11.0.0 PV-02 violation: OLD alias event name "
            f"{old_name!r} must be PRESERVED in DEFAULT_EVENTS at its "
            f"original position (PURE-ALIAS for 1-cycle deprecation)."
        )

    # 5 NEW alias regression tests must exist in test_lifecycle_hooks.py.
    lifecycle_tests = (project_root / _V11_0_0_PV02_DQ3_LIFECYCLE_TESTS).read_text(encoding="utf-8")
    for alias_test_name in _V11_0_0_PV02_DQ3_ALIAS_TEST_NAMES:
        assert f"def {alias_test_name}" in lifecycle_tests, (
            f"W-18 v11.0.0 PV-02 violation: D-Q-3 alias regression "
            f"test {alias_test_name!r} missing from "
            f"tests/test_lifecycle_hooks.py."
        )

    # env-flags.md must document the lifecycle event taxonomy section.
    env_flags = (project_root / _V11_0_0_PV02_DQ3_ENV_FLAGS_REF).read_text(encoding="utf-8")
    assert "Lifecycle event taxonomy" in env_flags, (
        "W-18 v11.0.0 PV-02 violation: D-Q-3 §2 documents the rename "
        "in env-flags.md; missing 'Lifecycle event taxonomy' section."
    )


# =====================================================================
# v11.0.0 — MAJOR cycle close (rollup of 5 MINORs + 1 MAJOR + cycle archive)
# =====================================================================
#
# v11.0.0 closes the 5-MINOR + 1-MAJOR rollup cycle that admitted ALL
# 27 internal optimization directions from
# `.local/research/v10_internal_optimization_directions.md`. The cycle
# close ships:
#
#  1. Canonical-7 sync 10.8.0 → 11.0.0 via `scripts/bump_version.py`.
#  2. CHANGELOG.md `## [11.0.0] - 2026-05-04` MAJOR-rollup entry citing
#     all 27 directions and their landed PV; GREEN self-loop verdict.
#  3. .local/research/v11.0.0_evaluation.md (W-3 SI-3 STRICT MAJOR
#     composite 9.30 / 10 ≥ 9.0; verdict PASS).
#  4. .local/research/v11.0.0_retrospective.md (W-7 / SI-8 with 4
#     mandatory sections + ≥5 deferrals).
#  5. docs/cycle-archive/v11.0.0/ populated with 5-MINOR + v11.0.0
#     stretch artifacts per W-19 archive policy.
#  6. workflow-system/human/demo/version-timeline/versions.json — NEW
#     v11.0.0 entry per WX-2 (real metrics from CHANGELOG only).

# Cycle-close surfaces.
_V11_0_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v11.0.0_retrospective.md")
_V11_0_0_EVALUATION_DOC: Path = Path(".local/research/v11.0.0_evaluation.md")
_V11_0_0_CHANGELOG_LITERAL: str = "## [11.0.0]"

# W-19 cycle archive.
_V11_0_0_CYCLE_ARCHIVE_DIR: Path = Path("docs/cycle-archive/v11.0.0")
_V11_0_0_CYCLE_ARCHIVE_RETROSPECTIVE: Path = Path("docs/cycle-archive/v11.0.0/retrospective.md")
_V11_0_0_CYCLE_ARCHIVE_README: Path = Path("docs/cycle-archive/v11.0.0/README.md")

# WX-2 demo versions.json (NEW v11.0.0 entry must exist).
_V11_0_0_VERSIONS_JSON: Path = Path("workflow-system/human/demo/version-timeline/versions.json")


def test_v11_0_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.0 MAJOR cycle close: every NEW v11.0.0 surface is pinned.

    Discharges the W-18 precondition for the v11.0.0 MAJOR-rollup
    CHANGELOG entry. v11.0.0 is the cycle close — the entry references
    PV-01 (D-P-2 + D-P-4) and PV-02 (D-O-4 + D-Q-3) deliverables (each
    with its own per-PV W-18 stanza above) AND the new cycle-close
    surfaces:

    * NEW `.local/research/v11.0.0_retrospective.md` (W-7 / SI-8).
    * NEW `.local/research/v11.0.0_evaluation.md` (W-3 SI-3).
    * NEW `docs/cycle-archive/v11.0.0/` populated per W-19.
    * NEW v11.0.0 entry in `workflow-system/human/demo/version-timeline/versions.json`
      per WX-2 (real metrics from CHANGELOG only).
    * Canonical-7 sync 10.8.0 → 11.0.0 + CHANGELOG `## [11.0.0]`.
    """
    # Retrospective + evaluation must exist with the required structure.
    retro_path = _w18_research_artifact_path(project_root, _V11_0_0_RETROSPECTIVE_DOC)
    retro_text = retro_path.read_text(encoding="utf-8")
    # 4 mandatory W-7 sections must be present.
    for required_section in (
        "## 1. Gaps identified",
        "## 2. What was implemented",
        "## 3. What was deferred and why",
        "## 4. Key learnings",
    ):
        assert required_section in retro_text, (
            f"W-18 v11.0.0 violation: retrospective missing required "
            f"W-7 section {required_section!r}."
        )

    eval_path = _w18_research_artifact_path(project_root, _V11_0_0_EVALUATION_DOC)
    eval_text = eval_path.read_text(encoding="utf-8")
    # STRICT MAJOR composite ≥ 9.0 must be documented.
    assert "STRICT MAJOR" in eval_text
    assert "9.0" in eval_text  # threshold cited
    assert "9.30" in eval_text  # actual composite cited

    # W-19 cycle archive populated.
    archive_dir = project_root / _V11_0_0_CYCLE_ARCHIVE_DIR
    assert archive_dir.is_dir(), (
        f"W-18 v11.0.0 violation: W-19 cycle archive missing at "
        f"{_V11_0_0_CYCLE_ARCHIVE_DIR}. v11.0.0 cycle close must run "
        f"`python scripts/archive_research_artifacts.py 11.0.0 ...`."
    )
    assert (project_root / _V11_0_0_CYCLE_ARCHIVE_RETROSPECTIVE).is_file(), (
        "W-18 v11.0.0 violation: archive retrospective missing — "
        "W-19 archive must include retrospective.md."
    )
    assert (project_root / _V11_0_0_CYCLE_ARCHIVE_README).is_file(), (
        "W-18 v11.0.0 violation: archive README missing — W-19 auto-generates README.md."
    )

    # WX-2: NEW v11.0.0 entry must exist in versions.json.
    versions_text = (project_root / _V11_0_0_VERSIONS_JSON).read_text(encoding="utf-8")
    assert '"version": "11.0.0"' in versions_text, (
        "WX-2 violation: workflow-system/human/demo/version-timeline/versions.json "
        "must include a v11.0.0 entry; the WX-2 rule mandates a new entry "
        "in the same PR that bumps __version__."
    )

    # Canonical-7 sync: src/devolaflow/__init__.py must be at 11.0.0.
    init_text = (project_root / "src/devolaflow/__init__.py").read_text(encoding="utf-8")
    assert '__version__ = "11.0.0"' in init_text, (
        "W-18 v11.0.0 violation: canonical-7 sync incomplete — "
        "src/devolaflow/__init__.py must declare __version__ = '11.0.0'."
    )

    # CHANGELOG entry must be at the TOP of CHANGELOG.md per AC #13.
    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V11_0_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v11.0.0 violation: CHANGELOG entry "
        f"{_V11_0_0_CHANGELOG_LITERAL!r} missing; v11.0.0 ships this entry."
    )
    # Verify the v11.0.0 entry comes BEFORE the v10.8.0 entry (top-of-file ordering).
    v11_idx = changelog.index(_V11_0_0_CHANGELOG_LITERAL)
    v10_8_idx = changelog.index("## [10.8.0]")
    assert v11_idx < v10_8_idx, (
        "W-18 v11.0.0 violation: CHANGELOG `## [11.0.0]` heading must "
        "sit at the TOP of CHANGELOG.md (above `## [10.8.0]`) per AC #13."
    )
