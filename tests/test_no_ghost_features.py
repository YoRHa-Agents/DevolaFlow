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
        # v11.3.0 — grill-with-docs integration (18th SF-4 canonical).
        # Domain-awareness reference covering CONTEXT.md authoring rules
        # (lazy-creation discipline + opinionated-term discipline +
        # project-specific scope), CONTEXT-MAP.md multi-context layout
        # inference, ADR format, and the 3-condition ADR gate (Hard to
        # reverse + Surprising without context + Real trade-off). The
        # vocabulary-vs-spec.md separation per A-4 keeps CONTEXT.md
        # disjoint from `.local/memory/specs/<domain>/spec.md`. Pairs
        # with `grill-mode.md` (companion 19th SF-4 canonical) and
        # Workflow rule W-23 (Domain Glossary Maintenance).
        "domain-awareness.md",
        # v11.3.0 — grill-with-docs integration (19th SF-4 canonical).
        # Grill-mode operating contract — one-question-at-a-time interview
        # discipline, codebase-first exploration, fuzzy-term sharpening,
        # concrete scenario probing, ADR offer evaluation via the 3-
        # condition gate, and parallel-orthogonal composition with PLAN
        # MODE (both can run concurrently). Activation is purely natural-
        # language via `classify_grill_intent` — NO new env flag (W-20
        # reuse-first preservation). Pairs with `domain-awareness.md`
        # (companion 18th SF-4 canonical), `src/devolaflow/skills/grill_mode.py`
        # (5 pure functions + 3 frozen dataclasses), and Workflow rule
        # W-22 (Grill Mode Activation Contract).
        "grill-mode.md",
        # v11.4.0 — subagent-patterns-2026 integration prep (20th SF-4
        # canonical). Subagent-pattern operating contract — 4-pattern
        # taxonomy (Inline Tool / Fan-Out / Agent Pool / Teams) verbatim
        # from the philschmid May 2026 article, 5-axis selection decision
        # tree, DevolaFlow current coverage matrix, Pattern 3 forward-
        # compat plan (NO API in v11.4.0; v12.0.0+ landing surface),
        # Pattern 4 PERMANENTLY NOT_SUPPORTED rationale (P5 invariant
        # cited verbatim from `repo-governance.mdc` §A-1 P5), v12.0.0
        # NEST schema roadmap (`gate.subagent_pattern` per A-2.3), and
        # explicit R-11 disambiguation from `grill-mode.md` (HUMAN-facing
        # interview pattern; orthogonal axis). NO new env flag (W-20
        # reuse-first preservation; activation via `select_pattern()`
        # helper invocation). Pairs with `src/devolaflow/skills/subagent_pattern.py`
        # (3 pure functions + 2 Literal aliases) and Workflow rule
        # W-24 (Subagent Pattern Selection).
        "subagent-patterns.md",
        # v12.3.0 PV-03 — Task Quality Score extraction (21st SF-4
        # canonical). Tier 3 on-demand reference loaded only at workflow
        # CLOSE (after the last stage gate PASSES); full extracted rubric
        # (4-dimension scoring matrix + 📊 output template + v12.3.0
        # PV-02 version-literal footer) moved here from SKILL.md to free
        # ~120 tokens of per-dispatch execution-loop context per
        # `.local/feedbacks/feedback_for_v12.1.1.md` #2 ("可以拆解一个
        # 单独的 skill，在运行完成最后一个阶段后再进行加载，以优化上下文
        # 表现形式"). SKILL.md §"Task Quality Score (L0 ONLY)" collapsed
        # to a 1-paragraph stub that preserves the v12.1.0 D-1 literals
        # (`L0 ONLY` + `Subagents MUST NOT`) and cross-links here. Pairs
        # with the v12.3.0 PV-02 §"Session Banner Contract" (the version
        # literal flows into the footer line via SKILL.md cross-link).
        "task-quality-score.md",
        # v12.5.0 PV-05 D-1.3 — codegraph plugin reference (22nd SF-4
        # canonical). Tier 2 Large-tier reference (~248 lines under the
        # ≤1000 ceiling). Documents the upstream `colbymchenry/codegraph`
        # MCP-first pre-indexed code knowledge graph, the 9 MCP tools
        # (search/context/callers/callees/impact/node/explore/files/
        # status), the CLI surface, the DevolaFlow integration map
        # (3 SSOT registries + 4 workflow templates + context profile +
        # Python wrapper package), the structured-cause degraded-mode
        # contract (CodegraphUnavailableError with cause: path_missing /
        # timeout / nonzero_exit / json_parse_error), and cache
        # management discipline. NO new env flag (W-20 reuse-first
        # preservation: codegraph reuses DEVOLAFLOW_AUTO_INSTALL_PLUGINS
        # for opt-in runtime install). Pairs with
        # `src/devolaflow/codegraph/` (the Python wrapper package),
        # `tests/test_codegraph.py` (39 tests at 98% coverage), and
        # `tests/test_codegraph_workflow_wiring.py` (12 structural
        # assertions across 4 workflow templates + context profile).
        "codegraph.md",
        # v13.0.0 — impeccable plugin reference (23rd SF-4 canonical).
        # Tier 2 Large-tier reference (~179 lines under the ≤1000 ceiling).
        # Documents the upstream `pbakaus/impeccable` design language system
        # (1 agent skill + 23 /impeccable steering commands) + the no-LLM
        # deterministic anti-pattern detector (`impeccable detect`; exit
        # 0=clean / 2=anti-patterns), the npm_then_init backend (auto-detect
        # harness; no --ai flag), the ui-pro → impeccable composition on the
        # new web-design workflow, the DevolaFlow integration map (3 SSOT
        # registries + web-design template + context profile), and the
        # PPI001 permissive-continue degraded-mode contract. NO new env flag
        # (W-20 reuse-first: reuses DEVOLAFLOW_AUTO_INSTALL_PLUGINS). Pairs
        # with `tests/test_impeccable_reference_doc.py`,
        # `tests/test_no_ghost_features.py::test_v13_0_0_impeccable_registered`,
        # and the web-design workflow wiring.
        "impeccable.md",
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
    # PV-06 simple-task auto-shortcut — RETIRED at v12.0.0 PV-03 D-2 per
    # ``.local/research/v12.0.0_gap_analysis.md`` §4 + the v11.1.0
    # retrospective §3 D-2 telegraph. The 5 PV-06 symbols
    # (``shortcut_from_env`` / ``shortcut_verdict`` / ``ShortcutVerdict`` /
    # ``SHORTCUT_FLAG_NAME`` / ``SHORTCUT_FLAG_TRUTHY``) were removed from
    # the import-smoke set in the same PV that deleted them; the v12.0.0
    # PV-03 retirement lint
    # ``test_v12_0_0_pv03_d2_shortcut_simple_retirement`` carries the
    # NEGATIVE pins (asserts the symbols do NOT appear at module scope).
)

# v9.3.0 PV-02 latency baselines — every CHANGELOG entry that cites the
# numerical perf gain pins these files. The W-18 contract requires them
# to be present + parseable.
_V9_3_0_LATENCY_BASELINE_PATHS: tuple[Path, ...] = (
    Path("benchmarks/devolaflow_context/baselines/v9.3.0_latency.json"),
    Path("benchmarks/devolaflow_context/baselines/v9.3.0_baseline.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v9.3.0.yaml"),
)

# v9.3.0 PV-06 env-flag documentation pins — RETIRED at v12.0.0 PV-03 D-2
# alongside the source-side surface deletion. The §2.12 entry in
# ``references/env-flags.md`` was removed (subsequent §2.13/§2.14/§2.15
# subsections renumbered to §2.12/§2.13/§2.14 to close the gap); the
# v12.0.0 PV-03 retirement lint
# ``test_v12_0_0_pv03_d2_shortcut_simple_retirement`` carries the NEGATIVE
# pin (asserts the literal ``DEVOLAFLOW_SIMPLE_SHORTCUT`` does NOT appear
# in the env-flag inventory). The empty tuple here keeps the §3 loop a
# zero-iteration no-op so the v9.3.0 ghost-audit lint stays GREEN
# post-retirement.
_V9_3_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = ()


def test_v9_3_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.3.0: every NEW v9.3.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.3.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.3.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.3.0 PV-07 cycle close pins:

    1. Every NEW public symbol from PV-02..PV-05 imports cleanly from
       its canonical module path (the PV-06 simple-task auto-shortcut
       symbols are RETIRED at v12.0.0 PV-03 D-2 per the v11.1.0
       retrospective §3 D-2 telegraph; the negative-pin lives in the
       sister test ``test_v12_0_0_pv03_d2_shortcut_simple_retirement``).
       Catches accidental name collisions, circular imports, and the
       v6.0.3-style "feature mentioned in CHANGELOG but never wired"
       anti-pattern.
    2. The 3 W-16 wholesale baseline files (composite + latency + layout
       invariant) exist on disk. The CHANGELOG cites the empirical
       perf-gain numbers (97.5% select_context p95 improvement) which
       are derived FROM these files; missing files = unprovable claim.
    3. The v9.3.0 PV-06 env-flag documentation lint is RETIRED at
       v12.0.0 PV-03 D-2 alongside the source-side retirement. The §3
       loop is a no-op (the literals tuple is empty); the canonical
       inventory check moved to the sister negative-pin lint
       ``test_v12_0_0_pv03_d2_shortcut_simple_retirement``.
    4. The PV-04 compressor split delivered exactly 4 files in the
       package (`__init__.py` + `layout.py` + `patterns.py` +
       `transforms.py`). A future PV that accidentally collapses the
       split or grows it to a 5th module would break this test.

    Failure modes:
      * "symbol import failed" → the CHANGELOG cites a feature that
        doesn't exist; either land the feature or remove the entry.
      * "missing baseline file" → run the PV-02 harness CLI to
        regenerate; OR the cycle didn't honour W-16 (mandatory).
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
# orthogonality justification ships in references/env-flags.md §2.12
# (was §2.13 at v9.4.0 close; renumbered to §2.12 at v12.0.0 PV-03 D-2
# alongside the SHORTCUT_SIMPLE retirement that emptied the former
# §2.12 slot per `.local/research/v12.0.0_gap_analysis.md` §4).
_V9_4_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.12 `DEVOLAFLOW_AUTO_INSTALL_PLUGINS`",
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
# orthogonality justification ships in references/env-flags.md §2.13
# (was §2.14 at v9.5.0 close; renumbered to §2.13 at v12.0.0 PV-03 D-2
# alongside the SHORTCUT_SIMPLE retirement that emptied the former
# §2.12 slot per `.local/research/v12.0.0_gap_analysis.md` §4).
_V9_5_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.13 `DEVOLAFLOW_SI_CHIP_DEEP`",
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
# v12.5.0 PV-05 D-1.1 grew active_tracking 11 → 12 by appending the codegraph
# entry (12th of 12); header comment refreshed to "12 + 10 = 22 total".
_V9_6_0_TOTAL_REFS: int = 22
_V9_6_0_ACTIVE_REFS: int = 12
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

    # §2 — Bulk freshness. v9.6.0 PV-04 D-R-5 closure pinned all 21 entries
    # at 2026-05-02. v12.5.0 PV-05 D-1.1 added codegraph (12th active entry)
    # at 2026-05-23 — that newer date is explicitly permitted per D-R-5
    # which requires entries to be ≥ 2026-05-02 (the floor; not equality).
    # The carve-out preserves the no-stale-entries invariant while allowing
    # legitimately fresher additions to land per cycle.
    all_refs = active + periodic
    stale = [r["id"] for r in all_refs if (r.get("last_checked") or "") < "2026-05-02"]
    assert not stale, (
        f"W-18 v9.6.0 violation: yaml entries with stale last_checked "
        f"(< 2026-05-02 floor): {stale} (D-R-5 closure requires ALL "
        f"entries at 2026-05-02 or later)"
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

# v9.7.0 PV-04 env-flag W-20 §7 documentation contract. The §2.14 anchor
# was §2.15 at v9.7.0 close; renumbered to §2.14 at v12.0.0 PV-03 D-2
# alongside the SHORTCUT_SIMPLE retirement that emptied the former §2.12
# slot per `.local/research/v12.0.0_gap_analysis.md` §4.
_V9_7_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.14 `DEVOLAFLOW_WARMUP`",
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

    # CHANGELOG entry must remain ordered above the v10.8.0 cycle it closes.
    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V11_0_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v11.0.0 violation: CHANGELOG entry "
        f"{_V11_0_0_CHANGELOG_LITERAL!r} missing; v11.0.0 ships this entry."
    )
    assert "canonical-7 sync 10.8.0 → 11.0.0" in changelog, (
        "W-18 v11.0.0 violation: CHANGELOG must preserve the v11.0.0 "
        "canonical-7 sync evidence even after later patch releases bump "
        "src/devolaflow/__init__.py."
    )
    # Verify the v11.0.0 entry comes BEFORE the v10.8.0 entry (top-of-file ordering).
    v11_idx = changelog.index(_V11_0_0_CHANGELOG_LITERAL)
    v10_8_idx = changelog.index("## [10.8.0]")
    assert v11_idx < v10_8_idx, (
        "W-18 v11.0.0 violation: CHANGELOG `## [11.0.0]` heading must "
        "remain above `## [10.8.0]` per AC #13."
    )


# =====================================================================
# v11.0.2 (PV-02 of v11.1.0 cycle) — G-CLASSIFY-1 cascade-decision
# pure function + W-16 wholesale baseline regen
# =====================================================================
#
# v11.0.2 is the FIRST impl PV of the v11.1.0 cascade-restoration MINOR
# cycle. Per the v11.1.0 cycle plan §3 PV-02 + L0 DEC-002, PV-02 ships
# Candidate C of G-CLASSIFY-1: preserve the existing 4-tier
# `Complexity` Literal byte-stable AND add a NEW sibling pure function
# `cascade_requirement(complexity) -> CascadeRequirement` whose verdict
# matrix (STANDARD/COMPLEX → CASCADE_REQUIRED; SIMPLE/TRIVIAL →
# CASCADE_OPTIONAL) encodes the operator-quotable rule the v11.0.0
# retrospective F-2 finding telegraphed. The dispatch-payload
# integration (NEST `gate.cascade_required`) lands at PV-04; PV-02
# ships only the prompt-side surface and the W-16 cycle anchor
# baseline.
#
# Per W-18 sequencing this lint refresh lands BEFORE the CHANGELOG
# `## [11.0.2]` entry that mentions any of the symbols below.

# G-CLASSIFY-1 surfaces.
_V11_0_2_PV02_CHANGE_ACTIVATION: Path = Path("src/devolaflow/skills/change_activation.py")
_V11_0_2_PV02_HEURISTIC_TESTS: Path = Path("tests/test_change_activation_heuristic.py")
_V11_0_2_PV02_CASCADE_TESTS: Path = Path("tests/test_cascade_enforcement.py")

# W-16 wholesale baseline regen (cycle-anchor for PV-03..PV-07).
_V11_0_2_PV02_BASELINE: Path = Path("benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json")

# Decision memo (gitignored under .local/; presence-checked when local).
_V11_0_2_PV02_DECISION_MEMO: Path = Path(".local/research/v11.1.0_pv02_decision.md")

# SKILL.md sub-table cells must cite the new verdict literal verbatim.
_V11_0_2_PV02_SKILL: Path = Path("workflow-system/agent/SKILL.md")

# 9 NEW cascade_requirement truth-table tests (T02 of PV-02 closeout +
# abf9785's orthogonal-to-force_no_change pin).
_V11_0_2_PV02_HEURISTIC_TEST_NAMES: tuple[str, ...] = (
    "test_cascade_requirement_complex_returns_required",
    "test_cascade_requirement_standard_returns_required",
    "test_cascade_requirement_simple_returns_optional",
    "test_cascade_requirement_trivial_returns_optional",
    "test_cascade_requirement_invalid_raises_value_error",
    "test_cascade_requirement_empty_string_raises_value_error",
    "test_cascade_requirement_is_pure_function",
    "test_cascade_requirement_string_values_are_stable",
    "test_cascade_requirement_orthogonal_to_force_no_change",
)

# NEW minimal-stub tests in tests/test_cascade_enforcement.py (T03);
# names track the L3-authored stub at c4ea92e/d* which integrates with the
# PV-04 NEST `gate.cascade_required` decision per decision memo §3 R-3.
_V11_0_2_PV02_CASCADE_TEST_NAMES: tuple[str, ...] = (
    "test_cascade_requirement_is_cascade_signal_source",
    "test_cascade_required_propagates_into_simulated_dispatch_payload",
    "test_cascade_required_does_not_invalidate_layout_invariant",
    "test_cascade_signal_orthogonal_to_force_no_change",
    # v11.0.5 PV-05 W08 — the v11.0.2 PV-02 minimal stub's 5th test
    # (``test_cascade_signal_propagation_pv04_telegraph``) was a SKIP
    # placeholder telegraphing PV-04's schema NEST. PV-04 (PR #128)
    # shipped that NEST + opt-in helper + soft validator, and PV-05
    # REPLACED the SKIP with a real PASS test
    # (``test_cascade_signal_propagation_through_populate_helper``)
    # exercising the populate helper end-to-end. The W-18 lint moves
    # to the PV-05 successor name; the PV-02 stub's 4 active tests
    # remain pinned by name above.
    "test_cascade_signal_propagation_through_populate_helper",
)


def test_v11_0_2_pv02_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.2 PV-02: G-CLASSIFY-1 new surfaces are pinned.

    Discharges the W-18 precondition for the v11.0.2 PV-02 CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land before the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned:

    * NEW `CascadeRequirement` Literal type and `cascade_requirement`
      pure function in `src/devolaflow/skills/change_activation.py`.
    * 9 NEW truth-table tests in
      `tests/test_change_activation_heuristic.py` (8 from T02 of the
      PV-02 closeout + 1 orthogonal-to-`force_no_change` pin from
      `abf9785`).
    * 5 NEW minimal-stub tests in `tests/test_cascade_enforcement.py`
      (4 active + 1 `pytest.skip` PV-04 telegraph; the full ≥10-test
      surface lands at PV-05 G-TEST-1).
    * NEW `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json`
      (W-16 wholesale baseline regen at v11.1.0 cycle-start).
    * SKILL.md Quick Action Decision sub-table cites the
      `CASCADE_REQUIRED` verdict literal in the Standard + Complex rows.
    * Decision memo at `.local/research/v11.1.0_pv02_decision.md`
      (gitignored — presence checked when locally available; no
      archive mapping required since `.local/` is git-private).
    """
    # NEW symbol — `CascadeRequirement` Literal type — must be importable.
    from typing import get_args as _get_args

    from devolaflow.skills.change_activation import (
        CascadeRequirement,
        cascade_requirement,
    )

    assert callable(cascade_requirement), (
        "W-18 v11.0.2 PV-02 violation: `cascade_requirement` must be a "
        "callable pure function in `devolaflow.skills.change_activation`."
    )
    assert set(_get_args(CascadeRequirement)) == {"CASCADE_REQUIRED", "CASCADE_OPTIONAL"}, (
        "W-18 v11.0.2 PV-02 violation: CascadeRequirement Literal must "
        "contain exactly the two operator-quotable string values "
        "{'CASCADE_REQUIRED', 'CASCADE_OPTIONAL'}; reordering or renaming "
        "either is a release blocker per the decision memo §1."
    )
    # The pure function's verdict matrix must match the operator-quotable rule.
    assert cascade_requirement("STANDARD") == "CASCADE_REQUIRED"
    assert cascade_requirement("COMPLEX") == "CASCADE_REQUIRED"
    assert cascade_requirement("SIMPLE") == "CASCADE_OPTIONAL"
    assert cascade_requirement("TRIVIAL") == "CASCADE_OPTIONAL"

    # AST-level pin on the source module: both new symbols defined in the
    # canonical owner file (A-5 single-source-of-truth pattern).
    ca_text = (project_root / _V11_0_2_PV02_CHANGE_ACTIVATION).read_text(encoding="utf-8")
    ca_tree = ast.parse(ca_text)
    function_names = {n.name for n in ast.walk(ca_tree) if isinstance(n, ast.FunctionDef)}
    assert "cascade_requirement" in function_names, (
        "W-18 v11.0.2 PV-02 violation: `cascade_requirement` must be "
        "defined as a top-level function in "
        "src/devolaflow/skills/change_activation.py per A-5 SSOT."
    )
    assert "CascadeRequirement" in ca_text, (
        "W-18 v11.0.2 PV-02 violation: `CascadeRequirement` Literal "
        "type must be declared in src/devolaflow/skills/change_activation.py."
    )
    # Operator-quotable verdict rule must appear verbatim in the docstring.
    assert "STANDARD complexity or higher → cascade required" in ca_text, (
        "W-18 v11.0.2 PV-02 violation: the operator-quotable verdict "
        "rule from `.local/research/v11.1.0_pv02_decision.md` §1 must "
        "appear verbatim in cascade_requirement's docstring."
    )

    # 9 NEW truth-table tests in test_change_activation_heuristic.py.
    heuristic_text = (project_root / _V11_0_2_PV02_HEURISTIC_TESTS).read_text(encoding="utf-8")
    for new_test in _V11_0_2_PV02_HEURISTIC_TEST_NAMES:
        assert f"def {new_test}" in heuristic_text, (
            f"W-18 v11.0.2 PV-02 violation: NEW truth-table test "
            f"{new_test!r} missing from "
            f"tests/test_change_activation_heuristic.py."
        )

    # 5 NEW minimal-stub tests in test_cascade_enforcement.py (NEW file;
    # 4 active + 1 `pytest.skip` PV-04 telegraph).
    cascade_path = project_root / _V11_0_2_PV02_CASCADE_TESTS
    assert cascade_path.is_file(), (
        f"W-18 v11.0.2 PV-02 violation: NEW test stub "
        f"{_V11_0_2_PV02_CASCADE_TESTS} missing — full ≥10-test "
        f"surface lands at PV-05; PV-02 ships the 5-test minimal stub."
    )
    cascade_text = cascade_path.read_text(encoding="utf-8")
    for new_test in _V11_0_2_PV02_CASCADE_TEST_NAMES:
        assert f"def {new_test}" in cascade_text, (
            f"W-18 v11.0.2 PV-02 violation: NEW minimal-stub test "
            f"{new_test!r} missing from tests/test_cascade_enforcement.py."
        )

    # W-16 wholesale baseline regen — cycle anchor for PV-03..PV-07.
    baseline_path = project_root / _V11_0_2_PV02_BASELINE
    assert baseline_path.is_file(), (
        f"W-18 v11.0.2 PV-02 violation: W-16 cycle-anchor baseline "
        f"missing at {_V11_0_2_PV02_BASELINE}. v11.1.0 cycle-start "
        f"MUST regenerate the wholesale baseline per W-16."
    )
    # Schema sanity: top-level keys are scenario names, each entry has
    # the canonical fields per BASELINE_FIELDS in
    # benchmarks/devolaflow_context/generate_baseline.py.
    import json as _json

    baseline_data = _json.loads(baseline_path.read_text(encoding="utf-8"))
    assert isinstance(baseline_data, dict) and len(baseline_data) > 0, (
        "W-18 v11.0.2 PV-02 violation: v11.1.0_baseline.json must be a "
        "non-empty dict keyed by scenario name."
    )
    sample_entry = next(iter(baseline_data.values()))
    for required_field in (
        "composite",
        "information_density",
        "section_relevance",
        "budget_utilization",
        "noise_ratio",
        "total_tokens",
        "budget",
        "selected_count",
    ):
        assert required_field in sample_entry, (
            f"W-18 v11.0.2 PV-02 violation: v11.1.0_baseline.json entry "
            f"missing required field {required_field!r} per "
            f"benchmarks/devolaflow_context/generate_baseline.py "
            f"BASELINE_FIELDS."
        )

    # SKILL.md Quick Action Decision sub-table must cite CASCADE_REQUIRED
    # in the Standard + Complex rows (T05 deliverable).
    skill_text = (project_root / _V11_0_2_PV02_SKILL).read_text(encoding="utf-8")
    sub_table_match = re.search(
        r"## Quick Action Decision\n(.*?)(?:\n## |\Z)",
        skill_text,
        re.DOTALL,
    )
    assert sub_table_match is not None, (
        "W-18 v11.0.2 PV-02 violation: SKILL.md missing `## Quick Action Decision` section."
    )
    sub_table = sub_table_match.group(1)
    assert "CASCADE_REQUIRED" in sub_table, (
        "W-18 v11.0.2 PV-02 violation: SKILL.md Quick Action Decision "
        "sub-table must cite the `CASCADE_REQUIRED` verdict literal in "
        "the Standard / Complex rows per T05 of the PV-02 closeout."
    )
    assert "L0→L1→L2→L3 cascade" in sub_table, (
        "W-18 v11.0.2 PV-02 violation: SKILL.md Quick Action Decision "
        "sub-table must cite the `L0→L1→L2→L3 cascade` chain per the "
        "operator-quotable verdict rule."
    )

    # Decision memo — best-effort presence check (gitignored .local/;
    # the memo is required for the closeout but is not committed, so we
    # check presence ONLY when locally available rather than failing CI
    # on the missing file alone). This satisfies the W-18 spirit: when
    # the lint runs locally during the PV close-out, it pins the memo's
    # operator-quotable verdict rule; when CI runs without the gitignored
    # memo, the lint passes the symbol/test/baseline/SKILL.md checks
    # which are the hard pins.
    memo_path = project_root / _V11_0_2_PV02_DECISION_MEMO
    if memo_path.is_file():
        memo_text = memo_path.read_text(encoding="utf-8")
        assert "STANDARD complexity or higher → cascade required" in memo_text, (
            f"W-18 v11.0.2 PV-02 violation: decision memo "
            f"{_V11_0_2_PV02_DECISION_MEMO} present but missing the "
            f"operator-quotable verdict rule §1; the verbatim sentence "
            f"is the public contract anchor."
        )
        assert "Candidate" in memo_text and " C " in memo_text, (
            f"W-18 v11.0.2 PV-02 violation: decision memo "
            f"{_V11_0_2_PV02_DECISION_MEMO} present but missing the "
            f"Candidate-C selection rationale."
        )


# G-CASCADE-1 + G-CASCADE-2 surfaces (v11.0.3 PV-03 SKILL + multi-stage-trace).
_V11_0_3_PV03_SKILL: Path = Path("workflow-system/agent/SKILL.md")
_V11_0_3_PV03_MULTI_STAGE_TRACE: Path = Path("workflow-system/agent/examples/multi-stage-trace.md")
_V11_0_3_PV03_CHANGELOG: Path = Path("CHANGELOG.md")

# SKILL.md positive surfaces — must appear post-edit.
_V11_0_3_PV03_SKILL_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "Cascade requirement (v11.1.0):",
    "(SIMPLE/TRIVIAL, < 1 hour)",
    "STANDARD+ MUST cascade per `cascade_requirement()`",
)

# SKILL.md negative surface — Layer collapse pattern wording REMOVED (G-CASCADE-1).
_V11_0_3_PV03_SKILL_NEGATIVE_SUBSTRING: str = "Layer collapse pattern"

# multi-stage-trace.md positive surfaces — must appear post-edit.
_V11_0_3_PV03_MST_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "WORKED CANONICAL pattern",
    "v11.1.0 cascade-restoration cycle",
    "**Cascade L0→L1→L2→L3**",
)

# multi-stage-trace.md negative surface — old "no L1 stage needed" wording REMOVED.
_V11_0_3_PV03_MST_NEGATIVE_SUBSTRING: str = (
    "L0 -> L3 with a per-task wave partition (no L1 stage needed)"
)


def test_v11_0_3_pv03_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.3 PV-03: G-CASCADE-1 + G-CASCADE-2 new surfaces are pinned.

    Discharges the W-18 precondition for the v11.0.3 PV-03 CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned:

    * `workflow-system/agent/SKILL.md` line ~180 contains the literal
      text ``Cascade requirement (v11.1.0):`` and the substring
      ``Layer collapse pattern`` is ABSENT (G-CASCADE-1 negative lint
      per cycle plan §3 PV-03 AC #1).
    * SKILL.md lines ~105-107 (Simple task shortcut block) bind to
      ``(SIMPLE/TRIVIAL, < 1 hour)`` and contain the explicit
      ``STANDARD+ MUST cascade per `cascade_requirement()``` sentence
      (G-CASCADE-1 positive lint per cycle plan §3 PV-03 AC #3).
    * `workflow-system/agent/examples/multi-stage-trace.md`
      §"Why this example exists" frames the example as the WORKED
      CANONICAL pattern (G-CASCADE-2 positive lint).
    * multi-stage-trace.md §"When NOT to use" rows 2 + 4 mandate
      cascade for STANDARD+ via the substring
      ``**Cascade L0→L1→L2→L3**`` and the verbatim
      ``L0 -> L3 with a per-task wave partition (no L1 stage needed)``
      is ABSENT (G-CASCADE-2 negative lint per cycle plan §3 PV-03
      AC #4).
    """
    skill_text = (project_root / _V11_0_3_PV03_SKILL).read_text(encoding="utf-8")
    for sub in _V11_0_3_PV03_SKILL_POSITIVE_SUBSTRINGS:
        assert sub in skill_text, (
            f"W-18 v11.0.3 PV-03 violation: SKILL.md missing positive "
            f"substring {sub!r} per G-CASCADE-1; cycle plan §3 PV-03 AC."
        )
    assert _V11_0_3_PV03_SKILL_NEGATIVE_SUBSTRING not in skill_text, (
        f"W-18 v11.0.3 PV-03 violation: SKILL.md still contains the "
        f"deprecated wording {_V11_0_3_PV03_SKILL_NEGATIVE_SUBSTRING!r}; "
        f"G-CASCADE-1 line 180 replacement is incomplete."
    )

    mst_text = (project_root / _V11_0_3_PV03_MULTI_STAGE_TRACE).read_text(encoding="utf-8")
    for sub in _V11_0_3_PV03_MST_POSITIVE_SUBSTRINGS:
        assert sub in mst_text, (
            f"W-18 v11.0.3 PV-03 violation: multi-stage-trace.md missing "
            f"positive substring {sub!r} per G-CASCADE-2."
        )
    assert _V11_0_3_PV03_MST_NEGATIVE_SUBSTRING not in mst_text, (
        f"W-18 v11.0.3 PV-03 violation: multi-stage-trace.md still "
        f"contains the deprecated wording "
        f"{_V11_0_3_PV03_MST_NEGATIVE_SUBSTRING!r}; G-CASCADE-2 row 2 "
        f"revision is incomplete."
    )
    # Frontmatter last_updated freshness pin (PV-03 dated 2026-05-08).
    assert 'last_updated: "2026-05-08"' in mst_text, (
        "W-18 v11.0.3 PV-03 violation: multi-stage-trace.md frontmatter "
        '`last_updated` must be `"2026-05-08"` per PV-03 close.'
    )


# G-PLAN-1 + G-PLAN-2 + schema NEST surfaces (v11.0.4 PV-04).
_V11_0_4_PV04_PLAN_MODE_DOC: Path = Path(
    "workflow-system/agent/references/plan-mode-enforcement.md"
)
_V11_0_4_PV04_SCHEMA: Path = Path("schemas/lean-dispatch.yaml")
_V11_0_4_PV04_TASK_ADAPTIVE: Path = Path("src/devolaflow/task_adaptive_selector.py")
_V11_0_4_PV04_FEEDBACK: Path = Path("src/devolaflow/feedback.py")
_V11_0_4_PV04_GATE_SCORER: Path = Path("src/devolaflow/gate/scorer.py")

# plan-mode-enforcement.md positive surfaces — must appear post-edit.
_V11_0_4_PV04_PLAN_MODE_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "Cascade depth (STANDARD+)",
    "Use the cascade chain L0 → L1 → L2 → L3 for STANDARD+ plans",
    'last_updated: "2026-05-08"',
)

# schemas/lean-dispatch.yaml positive surfaces — gate NEST sub-fields.
_V11_0_4_PV04_SCHEMA_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "cascade_required:",
    "cascade_min_layers:",
)


def test_v11_0_4_pv04_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.4 PV-04: G-PLAN-1 + G-PLAN-2 + schema NEST surfaces are pinned.

    Discharges the W-18 precondition for the v11.0.4 PV-04 CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned:

    * ``workflow-system/agent/references/plan-mode-enforcement.md`` §4
      gains item #10 with the literal text ``Cascade depth (STANDARD+)``
      (G-PLAN-1 prompt-side enforcement per cycle plan §3 PV-04 W04).
    * Same file §5.1 DO list gains the bullet
      ``Use the cascade chain L0 → L1 → L2 → L3 for STANDARD+ plans``
      (G-PLAN-1 §5.1 DO bullet).
    * Same file frontmatter ``last_updated`` is bumped to ``"2026-05-08"``.
    * ``schemas/lean-dispatch.yaml`` ``lean_format_spec.gate`` block
      gains the NEST sub-fields ``cascade_required`` + ``cascade_min_layers``
      per A-2.3 (W01 schema NEST). canonical_order length stays at 17;
      the v9.7.0 baseline byte-tests continue to PASS unchanged.
    * ``src/devolaflow/task_adaptive_selector.py`` ``_PLAN_MODE_OVERRIDES``
      gains the ``plan_mode_cascade_required: True`` runtime carrier
      (W05 G-PLAN-2). ``apply_plan_mode_overrides`` propagates it to
      the returned profile dict.
    * ``src/devolaflow/feedback.py`` exports a NEW module-level helper
      ``populate_cascade_gate_fields(base_dispatch, complexity)``
      (W02 — the OPT-IN dispatch-payload populator).
    * ``src/devolaflow/gate/scorer.py`` exports a NEW module-level
      helper ``validate_cascade_gate_fields(gate_block, *, actual_layers)``
      (W03 — the soft cascade validator; PV-05 A-7 will promote to
      strict).
    """
    plan_mode_text = (project_root / _V11_0_4_PV04_PLAN_MODE_DOC).read_text(encoding="utf-8")
    for sub in _V11_0_4_PV04_PLAN_MODE_POSITIVE_SUBSTRINGS:
        assert sub in plan_mode_text, (
            f"W-18 v11.0.4 PV-04 violation: plan-mode-enforcement.md "
            f"missing positive substring {sub!r} per G-PLAN-1; cycle plan "
            f"§3 PV-04 W04."
        )

    schema_text = (project_root / _V11_0_4_PV04_SCHEMA).read_text(encoding="utf-8")
    for sub in _V11_0_4_PV04_SCHEMA_POSITIVE_SUBSTRINGS:
        assert sub in schema_text, (
            f"W-18 v11.0.4 PV-04 violation: schemas/lean-dispatch.yaml "
            f"missing positive substring {sub!r} per W01 schema NEST; "
            f"cycle plan §3 PV-04 W01."
        )

    task_adaptive_text = (project_root / _V11_0_4_PV04_TASK_ADAPTIVE).read_text(encoding="utf-8")
    assert "plan_mode_cascade_required" in task_adaptive_text, (
        "W-18 v11.0.4 PV-04 violation: task_adaptive_selector.py "
        "_PLAN_MODE_OVERRIDES must carry the `plan_mode_cascade_required` "
        "key per W05 G-PLAN-2."
    )

    feedback_text = (project_root / _V11_0_4_PV04_FEEDBACK).read_text(encoding="utf-8")
    assert "def populate_cascade_gate_fields(" in feedback_text, (
        "W-18 v11.0.4 PV-04 violation: feedback.py must export the "
        "`populate_cascade_gate_fields` helper per W02."
    )

    gate_scorer_text = (project_root / _V11_0_4_PV04_GATE_SCORER).read_text(encoding="utf-8")
    assert "def validate_cascade_gate_fields(" in gate_scorer_text, (
        "W-18 v11.0.4 PV-04 violation: gate/scorer.py must export the "
        "`validate_cascade_gate_fields` helper per W03."
    )


# G-TEST-1 + G-AUDIT-1 + G-BENCH-1 + Architecture rule A-7 surfaces
# (v11.0.5 PV-05 — closes the v11.1.0 cascade-restoration cycle's
# functional implementation surface; PV-06 = NineS self-eval analysis-only,
# PV-07 = MINOR rollup canonical-7 sync).
_V11_0_5_PV05_CASCADE_TESTS: Path = Path("tests/test_cascade_enforcement.py")
_V11_0_5_PV05_AUDIT_SCRIPT: Path = Path("scripts/audit_layer_usage.py")
_V11_0_5_PV05_AUDIT_TESTS: Path = Path("tests/test_audit_layer_usage.py")
_V11_0_5_PV05_ARCHITECTURE_RULES: Path = Path(".rules/architecture.mdc")
_V11_0_5_PV05_AGENTS_MD: Path = Path("AGENTS.md")
_V11_0_5_PV05_REPO_GOVERNANCE: Path = Path(".cursor/rules/repo-governance.mdc")
_V11_0_5_PV05_DEAD_API_SCRIPT: Path = Path("scripts/detect_dead_apis.py")
_V11_0_5_PV05_FEEDBACK: Path = Path("src/devolaflow/feedback.py")
_V11_0_5_PV05_GATE_SCORER: Path = Path("src/devolaflow/gate/scorer.py")
_V11_0_5_PV05_CHANGE_ACTIVATION: Path = Path("src/devolaflow/skills/change_activation.py")
_V11_0_5_PV05_CHANGELOG: Path = Path("CHANGELOG.md")

# tests/test_cascade_enforcement.py NEW positive surfaces — must appear post-edit
# (the PV-02 5-test stub grows to ≥10 tests covering strict + soft +
# backward-compat + skip-path + truth-table propagation per cycle plan §3 PV-05).
_V11_0_5_PV05_CASCADE_TEST_NAMES: tuple[str, ...] = (
    # Branch 2 — replace the PV-02 SKIP with a real PV-04 propagation test
    "test_cascade_signal_propagation_through_populate_helper",
    # Branch 3 — backward-compat (R-1 mitigation per cycle plan §3 PV-05 +
    # the L1 prompt's CRITICAL INVARIANT R-1 mitigation language)
    "test_legacy_dispatch_without_cascade_fields_passes_byte_identically",
    "test_legacy_dispatch_with_cascade_required_false_passes",
    "test_simple_complexity_skips_cascade_validation",
    "test_trivial_complexity_skips_cascade_validation",
    # Branch 4 — strict-mode validator behavior (PV-04 SOFT validator
    # contract preview of the v12.0.0 STRICT promotion)
    "test_strict_validator_warns_when_actual_layers_below_min",
    "test_soft_mode_warns_instead_of_raising",
    "test_strict_validator_passes_when_actual_layers_meets_min",
    # Branch 5 — full populate→validate truth-table propagation
    "test_cascade_requirement_propagates_through_populate_then_validate",
)

# tests/test_audit_layer_usage.py NEW positive surfaces (G-AUDIT-1 ratchet).
# v12.0.0 PV-02 D-1 renamed the byte-identical opt-out test from
# `test_strict_flag_default_off_preserves_byte_identical_v11_0x` (the
# v11.0.5 default-OFF semantics) to
# `test_no_strict_flag_preserves_byte_identical_v11_0x` (the v12.0.0
# default-ON semantics; the operator now passes ``strict=False`` /
# ``--no-strict`` to recover the v11.0.x observability-only behaviour).
# The W-18 lint here tracks the renamed surface so the v11.0.5 PV-05
# coverage stays GREEN across the v12.0.0 PV-02 D-1 STRICT graduation.
_V11_0_5_PV05_AUDIT_TEST_NAMES: tuple[str, ...] = (
    "test_strict_flag_returns_zero_when_above_threshold",
    "test_strict_flag_returns_one_when_below_threshold",
    "test_no_strict_flag_preserves_byte_identical_v11_0x",
    "test_cascade_ratio_field_present_in_output",
)

# scripts/audit_layer_usage.py positive surfaces — --strict + cascade_ratio.
_V11_0_5_PV05_AUDIT_SCRIPT_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "cascade_ratio",
    "--strict",
    "--threshold",
)

# 4 NEW EvoBench scenarios under benchmarks/devolaflow_context/scenarios/.
_V11_0_5_PV05_EVOBENCH_SCENARIOS: tuple[Path, ...] = (
    Path("benchmarks/devolaflow_context/scenarios/cascade_l0_l1_l2_l3_standard.yaml"),
    Path("benchmarks/devolaflow_context/scenarios/cascade_l0_l1_l2_l3_complex.yaml"),
    Path("benchmarks/devolaflow_context/scenarios/collapse_l0_l3_simple.yaml"),
    Path("benchmarks/devolaflow_context/scenarios/collapse_l0_l3_trivial.yaml"),
)

# .rules/architecture.mdc must carry the new §A-7 body + 4 sub-rules.
_V11_0_5_PV05_ARCHITECTURE_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## A-7 — Cascade-Depth Invariant for Standard+ Dispatches",
    "### A-7.1 — Conditional strict enforcement",
    "### A-7.2 — Trivial waiver",
    "### A-7.3 — Operator override",
    "### A-7.4 — Enforcement surface",
)

# Dead-API pin cleanup negative surfaces — pin tuples REMOVED from src/.
_V11_0_5_PV05_REMOVED_PIN_NAMES: tuple[tuple[Path, str], ...] = (
    (
        Path("src/devolaflow/skills/change_activation.py"),
        "_cascade_requirement_dead_api_pins",
    ),
    (Path("src/devolaflow/feedback.py"), "_populate_cascade_gate_fields_dead_api_pins"),
    (Path("src/devolaflow/gate/scorer.py"), "_validate_cascade_gate_fields_dead_api_pins"),
)

# DEFAULT_ALLOWLIST replacement entries that take over from the removed pin tuples.
_V11_0_5_PV05_NEW_ALLOWLIST_ENTRIES: tuple[str, ...] = (
    '"devolaflow.feedback:populate_cascade_gate_fields"',
    '"devolaflow.gate.scorer:validate_cascade_gate_fields"',
)


def test_v11_0_5_pv05_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.5 PV-05: G-TEST-1 + G-AUDIT-1 + G-BENCH-1 + A-7 surfaces are pinned.

    Discharges the W-18 precondition for the v11.0.5 PV-05 CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition for the
    LAST functional implementation PV of the v11.1.0 cycle.

    Surfaces pinned (cycle plan §3 PV-05 + L1 prompt CRITICAL INVARIANTS):

    * ``tests/test_cascade_enforcement.py`` extended from 5-test stub to
      ≥10 PASS tests covering Branch 2 (replace SKIP with real propagation
      test) + Branch 3 (4 backward-compat tests — R-1 mitigation) +
      Branch 4 (3 SOFT/strict-mode validator tests) + Branch 5 (1 full
      populate→validate truth-table propagation test). All 9 NEW test
      names pinned via ``_V11_0_5_PV05_CASCADE_TEST_NAMES``.
    * ``scripts/audit_layer_usage.py`` G-AUDIT-1 ratchet: ``--strict``
      CLI flag + ``--threshold`` CLI flag (default 0.30) + ``cascade_ratio``
      field on ``compute_layer_ratios()`` output. Default-OFF preserves
      byte-identical v11.0.x behavior; ``run(strict=True, threshold=N)``
      returns 1 when ``total_dispatch > 0`` AND ``cascade_ratio < N``.
    * ``tests/test_audit_layer_usage.py`` 4 NEW tests pinning the strict
      flag + cascade_ratio field per G-AUDIT-1 acceptance criteria.
    * ``benchmarks/devolaflow_context/scenarios/`` gains 4 NEW G-BENCH-1
      cascade-vs-collapse scenario YAMLs (cascade_l0_l1_l2_l3_standard,
      cascade_l0_l1_l2_l3_complex, collapse_l0_l3_simple,
      collapse_l0_l3_trivial). Auto-discovered by ``discover_scenarios()``;
      W-17 +0 NEW test functions (parametrize expansion over data per
      W-17 carve-out).
    * ``.rules/architecture.mdc`` gains §A-7 ("Cascade-Depth Invariant
      for Standard+ Dispatches") with 4 sub-rules (A-7.1 Conditional
      strict enforcement / A-7.2 Trivial waiver / A-7.3 Operator override
      / A-7.4 Enforcement surface). W-21 Soul-set freeze preserved at
      10 entries; A-7 lands at Architecture per ADR-007 §"Soul-vs-
      Architecture" decision-rule on conditional + implementation-coupled
      invariants.
    * ``AGENTS.md`` + ``.cursor/rules/repo-governance.mdc`` auto-recompiled
      via ``make compile-rules`` carry the same §A-7 body verbatim per
      .rules/compile-config.yaml; drift detection via
      .rules/.compile-hashes.json regenerated cleanly.
    * Dead-API pin cleanup: 3 forward-looking pin tuples REMOVED from
      ``change_activation.py`` + ``feedback.py`` + ``gate/scorer.py``
      now that A-7 wires the symbols. The 2 helpers without production
      callers (``populate_cascade_gate_fields`` + ``validate_cascade_gate_fields``)
      are tracked via explicit ``DEFAULT_ALLOWLIST`` entries in
      ``scripts/detect_dead_apis.py`` (canonical pattern for forward-
      looking helpers, mirroring 30+ existing entries). The
      ``cascade_requirement`` pin is removed unconditionally because
      ``feedback.py::populate_cascade_gate_fields`` line 564 has a real
      ``ast.Call`` reference inside the function body (verified by the
      dead-API detector AST walk).

    Coupled invariants verified GREEN at PV-05 close:
      * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      * S-10 hook-chain byte-id: 10/10 PASS unchanged
      * CP-4 gate suite: 108/108 PASS unchanged
      * EvoBench: 36/36 PASS, max scenario drift 0.09pp (well under 5pp
        W-4 SI-4 envelope)
    """
    cascade_path = project_root / _V11_0_5_PV05_CASCADE_TESTS
    assert cascade_path.is_file(), (
        f"W-18 v11.0.5 PV-05 violation: extended test surface "
        f"{_V11_0_5_PV05_CASCADE_TESTS} missing — full ≥10-test surface "
        "lands at PV-05 per cycle plan §3 PV-05 W01."
    )
    cascade_text = cascade_path.read_text(encoding="utf-8")
    for new_test in _V11_0_5_PV05_CASCADE_TEST_NAMES:
        assert f"def {new_test}" in cascade_text, (
            f"W-18 v11.0.5 PV-05 violation: NEW cascade-enforcement test "
            f"{new_test!r} missing from tests/test_cascade_enforcement.py "
            f"per Branch 2/3/4/5 coverage."
        )

    audit_script_text = (project_root / _V11_0_5_PV05_AUDIT_SCRIPT).read_text(encoding="utf-8")
    for sub in _V11_0_5_PV05_AUDIT_SCRIPT_POSITIVE_SUBSTRINGS:
        assert sub in audit_script_text, (
            f"W-18 v11.0.5 PV-05 violation: scripts/audit_layer_usage.py "
            f"missing positive substring {sub!r} per G-AUDIT-1; cycle plan "
            f"§3 PV-05 W01 T02_audit_ratchet."
        )

    audit_test_text = (project_root / _V11_0_5_PV05_AUDIT_TESTS).read_text(encoding="utf-8")
    for new_test in _V11_0_5_PV05_AUDIT_TEST_NAMES:
        assert f"def {new_test}" in audit_test_text, (
            f"W-18 v11.0.5 PV-05 violation: NEW audit-ratchet test "
            f"{new_test!r} missing from tests/test_audit_layer_usage.py."
        )

    for scenario_path in _V11_0_5_PV05_EVOBENCH_SCENARIOS:
        full_path = project_root / scenario_path
        assert full_path.is_file(), (
            f"W-18 v11.0.5 PV-05 violation: NEW EvoBench scenario "
            f"{scenario_path} missing per G-BENCH-1; cycle plan §3 "
            f"PV-05 W02 T01_evobench_fixtures."
        )

    architecture_text = (project_root / _V11_0_5_PV05_ARCHITECTURE_RULES).read_text(
        encoding="utf-8"
    )
    for sub in _V11_0_5_PV05_ARCHITECTURE_POSITIVE_SUBSTRINGS:
        assert sub in architecture_text, (
            f"W-18 v11.0.5 PV-05 violation: .rules/architecture.mdc "
            f"missing §A-7 substring {sub!r}; cycle plan §3 PV-05 W05."
        )

    # Auto-recompiled targets must carry §A-7 verbatim per
    # .rules/compile-config.yaml (drift detection via
    # .rules/.compile-hashes.json regenerated by `make compile-rules`).
    agents_md_text = (project_root / _V11_0_5_PV05_AGENTS_MD).read_text(encoding="utf-8")
    assert "## A-7 — Cascade-Depth Invariant for Standard+ Dispatches" in agents_md_text, (
        "W-18 v11.0.5 PV-05 violation: AGENTS.md missing §A-7 "
        "(auto-recompile via `make compile-rules` did not run, or "
        ".rules/compile-config.yaml ceased to include the architecture layer)."
    )
    repo_governance_text = (project_root / _V11_0_5_PV05_REPO_GOVERNANCE).read_text(
        encoding="utf-8"
    )
    assert "## A-7 — Cascade-Depth Invariant for Standard+ Dispatches" in repo_governance_text, (
        "W-18 v11.0.5 PV-05 violation: .cursor/rules/repo-governance.mdc "
        "missing §A-7 (auto-recompile via `make compile-rules` did not run, "
        "or compile-config ceased to include the architecture layer for "
        "the cursor target)."
    )

    # Dead-API pin cleanup negative lints — the 3 placeholder pin tuples
    # from PV-02 / PV-04 must be GONE from src/ post-PV-05.
    for src_path, removed_pin_name in _V11_0_5_PV05_REMOVED_PIN_NAMES:
        src_text = (project_root / src_path).read_text(encoding="utf-8")
        assert f"{removed_pin_name} = (" not in src_text, (
            f"W-18 v11.0.5 PV-05 violation: forward-looking pin tuple "
            f"{removed_pin_name!r} still present in {src_path}; cycle "
            f"plan §3 PV-05 W03 ('dead-API pin cleanup now that A-7 wires "
            f"the symbols') was not completed."
        )

    # DEFAULT_ALLOWLIST positive lints — the 2 replacement entries must be
    # present in detect_dead_apis.py.
    dead_api_script_text = (project_root / _V11_0_5_PV05_DEAD_API_SCRIPT).read_text(
        encoding="utf-8"
    )
    for allowlist_entry in _V11_0_5_PV05_NEW_ALLOWLIST_ENTRIES:
        assert allowlist_entry in dead_api_script_text, (
            f"W-18 v11.0.5 PV-05 violation: scripts/detect_dead_apis.py "
            f"DEFAULT_ALLOWLIST missing entry {allowlist_entry!r} that "
            "replaces the removed pin tuple per cycle plan §3 PV-05 W03."
        )


# v11.0.6 PV-06 — W-18 ghost-audit refresh stanza.
# G-NINES-1 NineS self-eval + W-3 SI-3 6-dim composite evaluation report.
# PV-06 is analysis-only — owned files are .local/research/ artifacts
# (gitignored per repo convention) plus the CHANGELOG entry + canonical 7
# bump. The W-18 stanza pins the analysis-artifact set with the
# skip-when-absent pattern so the test PASSES in CI (where .local/ is absent)
# AND in local dev (where the PV-06 author's artifacts ARE present). This
# mirrors the SF-3 mirror-parity self-skip pattern and the
# _W18_RESEARCH_ARCHIVE_CANDIDATES fallback convention used elsewhere in
# this file.
_V11_0_6_PV06_NINES_RAW: Path = Path(".local/research/v11.1.0_pv06_nines.json")
_V11_0_6_PV06_NINES_MD: Path = Path(".local/research/v11.1.0_pv06_nines.md")
_V11_0_6_PV06_EVALUATION: Path = Path(".local/research/v11.1.0_evaluation.md")
_V11_0_6_PV06_STAGE_REPORT: Path = Path(".local/research/v11.1.0_pv06_stage_report.md")
_V11_0_6_PV06_CHANGELOG: Path = Path("CHANGELOG.md")

_V11_0_6_PV06_LOCAL_RESEARCH_FILES: tuple[Path, ...] = (
    _V11_0_6_PV06_NINES_RAW,
    _V11_0_6_PV06_NINES_MD,
    _V11_0_6_PV06_EVALUATION,
    _V11_0_6_PV06_STAGE_REPORT,
)

# CHANGELOG body must carry the v11.0.6 PV-06 entry verbatim.
_V11_0_6_PV06_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.0.6] - 2026-05-08",
    "G-NINES-1 NineS self-eval",
    "W-3 SI-3",
)


def test_v11_0_6_pv06_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.6 PV-06: G-NINES-1 NineS self-eval + W-3 SI-3 evaluation pinned.

    Discharges the W-18 precondition for the v11.0.6 PV-06 CHANGELOG entry.
    Per W-18 sequencing the lint refresh MUST land BEFORE the CHANGELOG entry
    — this stanza closes that precondition for the cycle's MINOR-close
    convergence verdict PV.

    Surfaces pinned (cycle plan §3 PV-06 + §5 MINOR-close criteria + the
    L1 PV-06 prompt's owned-files manifest):

    * ``.local/research/v11.1.0_pv06_nines.json`` (raw NineS evaluator
      output; 25 dimensions = 20 capability + 5 hygiene per NineS v3.3.0).
    * ``.local/research/v11.1.0_pv06_nines.md`` (rendered NineS analysis
      with W-2 / SI-2 hybrid-mode dimension-by-dimension scoring + delta
      vs D2 baseline).
    * ``.local/research/v11.1.0_evaluation.md`` (W-3 / SI-3 6-dim weighted
      composite; the cycle's MINOR-close gate verdict report — composite
      9.02/10, ≥ 8.5 MINOR threshold, +0.52 margin).
    * ``.local/research/v11.1.0_pv06_stage_report.md`` (L1 → L0 stage
      report covering the PV-06 wave/task decomposition + W-9 SI-10 7-step
      verification + GO recommendation for PV-07 MINOR rollup).
    * ``CHANGELOG.md`` carries the ``## [11.0.6] - 2026-05-08`` PATCH entry
      mentioning ``G-NINES-1 NineS self-eval`` + ``W-3 SI-3`` per W-18
      sequencing (this stanza lands BEFORE the CHANGELOG entry per W-18).

    Coupled invariants verified GREEN at PV-06 close (analysis-only PV
    preserves all PV-05 invariants by construction):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * cascade enforcement strict: 13/13 PASS unchanged
    * audit ratchet: 15/15 PASS unchanged
    * EvoBench: 36/36 PASS, max scenario drift 0.09pp (well under 5pp
      W-4 SI-4 envelope)
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags

    Skip-when-absent rationale: the .local/ research artifacts are
    gitignored per repo convention (CHECK ``.gitignore`` line 49 ``.local/``).
    In CI / fresh clones the directory does not exist; this stanza skips
    the .local lints in that environment and validates only the tracked
    CHANGELOG entry. In local dev (where the PV-06 author wrote the
    artifacts) ALL 4 .local files MUST exist together (partial sets are
    a violation — the author cannot ship with NineS JSON but no rendered
    analysis, etc.). This pattern mirrors the SF-3 mirror-parity self-skip
    convention.
    """
    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked; W-18
    # precondition that the entry land in this PV's commit).
    changelog_text = (project_root / _V11_0_6_PV06_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_0_6_PV06_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.0.6 PV-06 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per cycle plan §3 PV-06 + §5 MINOR-close. "
            "The W-18 stanza lands BEFORE the CHANGELOG entry per W-18 "
            "sequencing — if this lint fails the entry must be authored."
        )
    # Single-application discipline (PV-03 N-2 mitigation): a section header
    # ## [11.0.6] appears EXACTLY once in CHANGELOG.md. Use line-anchored
    # match (mirrors `grep -c '^## \\[11\\.0\\.6\\]'` semantics) so the
    # in-prose substring mention inside the entry body does not double-count.
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.0.6]")
    )
    assert section_header_count == 1, (
        "W-18 v11.0.6 PV-06 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.0.6]' section headers — "
        "exactly 1 expected (PV-03 N-2 single-application discipline)."
    )

    # .local/research/ artifacts — skip-when-absent for CI; assert all-or-none
    # for local dev (the PV-06 author's working tree).
    present = [p for p in _V11_0_6_PV06_LOCAL_RESEARCH_FILES if (project_root / p).is_file()]
    if not present:
        pytest.skip(
            "W-18 v11.0.6 PV-06: .local/research/ artifacts absent (CI / fresh "
            "clone — .local/ is gitignored per repo convention at .gitignore:49). "
            "Local dev dispatches verified the 4-artifact presence at PV-06 close. "
            "Future PV-07 W-19 archive at docs/cycle-archive/v11.1.0/ will pin a "
            "tracked copy."
        )
    missing = [p for p in _V11_0_6_PV06_LOCAL_RESEARCH_FILES if not (project_root / p).is_file()]
    assert not missing, (
        f"W-18 v11.0.6 PV-06 violation: partial .local/research/ artifact set — "
        f"some present ({[str(p) for p in present]}) but others missing "
        f"({[str(p) for p in missing]}); the PV-06 author MUST produce ALL 4 "
        f"artifacts (NineS raw + rendered + W-3 SI-3 evaluation + stage report) "
        f"per cycle plan §3 PV-06 owned-files manifest."
    )


# v11.1.0 PV-07 — W-18 final ghost-audit stanza for the MINOR cycle close.
# Discharges the W-18 precondition for the CHANGELOG `## [11.1.0]` MINOR-close
# entry. Per W-18 sequencing the lint refresh MUST land BEFORE the CHANGELOG
# entry — this stanza closes that precondition for the cycle's rollup PV.
#
# PV-07 owned-files include canonical 7 (handled by `bump_version.py`),
# WX-2 versions.json + DS-1 demo index.html, ST-3 bilingual EN/ZH refresh
# (via `make sync-human-docs`), W-19 cycle archive at
# `docs/cycle-archive/v11.1.0/` (committed per W-19), and the W-7 SI-8
# retrospective at `.local/research/v11.1.0_retrospective.md`.
#
# The W-19 archive at `docs/cycle-archive/v11.1.0/retrospective.md` is the
# TRACKED copy of the retrospective. The `.local/research/v11.1.0_retrospective.md`
# original is gitignored per repo convention; this stanza pins the archive
# (always tracked) AND optionally the .local original (skip-when-absent).
_V11_1_0_VERSIONS_JSON: Path = Path("workflow-system/human/demo/version-timeline/versions.json")
_V11_1_0_DEMO_INDEX_HTML: Path = Path("workflow-system/human/demo/index.html")
_V11_1_0_CYCLE_ARCHIVE_DIR: Path = Path("docs/cycle-archive/v11.1.0")
_V11_1_0_CYCLE_ARCHIVE_RETROSPECTIVE: Path = _V11_1_0_CYCLE_ARCHIVE_DIR / "retrospective.md"
_V11_1_0_CYCLE_ARCHIVE_README: Path = _V11_1_0_CYCLE_ARCHIVE_DIR / "README.md"
_V11_1_0_LOCAL_RETROSPECTIVE: Path = Path(".local/research/v11.1.0_retrospective.md")
_V11_1_0_LOCAL_PV07_STAGE_REPORT: Path = Path(".local/research/v11.1.0_pv07_stage_report.md")
_V11_1_0_CHANGELOG: Path = Path("CHANGELOG.md")

# Mandatory section headers in the W-7 / SI-8 retrospective (4-section
# completeness check per W-7 spec).
_V11_1_0_RETROSPECTIVE_REQUIRED_SECTIONS: tuple[str, ...] = (
    "## §1 — Gaps identified",
    "## §2 — What was implemented",
    "## §3 — What was deferred and why",
    "## §4 — Key learnings",
)

# CHANGELOG body must carry the v11.1.0 MINOR-close entry verbatim.
_V11_1_0_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.0] - 2026-05-08",
    "MINOR",
    "cascade-restoration",
)


def test_v11_1_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.0 PV-07: cycle-close MINOR rollup pinned.

    Discharges the W-18 precondition for the v11.1.0 MINOR-close CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (cycle plan §2 PV-07 + §5 MINOR-close criteria):

    * ``workflow-system/human/demo/version-timeline/versions.json`` carries
      a v11.1.0 entry per WX-2 (real metrics from CHANGELOG only).
    * ``workflow-system/human/demo/index.html`` carries a v11.1.0
      "What's New" section per DS-1 demo "What's New".
    * ``docs/cycle-archive/v11.1.0/`` exists with the auto-generated
      ``README.md`` index + ``retrospective.md`` per W-19 archive contract
      (the archive IS committed; not gitignored).
    * ``CHANGELOG.md`` carries the ``## [11.1.0] - 2026-05-08`` MINOR-close
      entry mentioning ``MINOR`` + ``cascade-restoration``.
    * W-7 / SI-8 retrospective 4-section completeness — the archive copy at
      ``docs/cycle-archive/v11.1.0/retrospective.md`` MUST contain the 4
      mandatory section headers ("Gaps identified", "What was implemented",
      "What was deferred and why", "Key learnings").

    The .local/research/v11.1.0_retrospective.md original is gitignored
    per repo convention (`.gitignore:49` `.local/`); the W-19 archive copy
    at `docs/cycle-archive/v11.1.0/retrospective.md` is the tracked
    canonical pin. The .local original (if present) is also asserted via
    skip-when-absent for local-dev consistency.

    Coupled invariants verified GREEN at PV-07 close:

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * cascade enforcement strict: 13/13 PASS unchanged
    * audit ratchet: 15/15 PASS unchanged
    * EvoBench: 36/36 PASS unchanged
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags

    Skip-when-absent rationale: the W-19 archive at
    ``docs/cycle-archive/v11.1.0/`` is the SOURCE OF TRUTH for this lint
    once committed. Before the PV-07 commit lands the archive may be
    absent (e.g., during in-progress dispatching); the lint then falls
    back to the .local original (skip-when-absent for the .local file
    follows v11.0.6 PV-06 stanza pattern).
    """
    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked; W-18
    # precondition that the entry land in this PV's commit).
    changelog_text = (project_root / _V11_1_0_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_0_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.0 PV-07 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per cycle plan §5 MINOR-close criteria. "
            "The W-18 stanza lands BEFORE the CHANGELOG entry per W-18 "
            "sequencing — if this lint fails the entry must be authored."
        )

    # Single-application discipline (PV-03 N-2 mitigation): a section
    # header ## [11.1.0] appears EXACTLY once in CHANGELOG.md. Use
    # line-anchored match (mirrors `grep -c '^## \\[11\\.1\\.0\\]'`
    # semantics) so any in-prose `## [11.1.0]` mention inside another
    # entry's body does not double-count.
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.0]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.0 PV-07 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.0]' section "
        "headers — exactly 1 expected (PV-03 N-2 single-application "
        "discipline)."
    )

    # WX-2 versions.json v11.1.0 entry — ALWAYS pinned (tracked per ST-1).
    versions_json_text = (project_root / _V11_1_0_VERSIONS_JSON).read_text(encoding="utf-8")
    assert '"version": "11.1.0"' in versions_json_text, (
        "W-18 v11.1.0 PV-07 violation: versions.json missing v11.1.0 "
        "entry per WX-2; cycle plan §5.6 mandates demo "
        "versions.json refreshed at MINOR close."
    )

    # DS-1 demo index.html v11.1.0 "What's New" — ALWAYS pinned.
    demo_index_text = (project_root / _V11_1_0_DEMO_INDEX_HTML).read_text(encoding="utf-8")
    assert "v11.1.0" in demo_index_text, (
        "W-18 v11.1.0 PV-07 violation: demo/index.html does not mention "
        "v11.1.0 per DS-1 'What's New'; cycle plan §5.6 mandates "
        "demo index.html refreshed at MINOR close."
    )

    # W-19 cycle archive at docs/cycle-archive/v11.1.0/ — ALWAYS pinned
    # (committed per W-19; not gitignored).
    assert (project_root / _V11_1_0_CYCLE_ARCHIVE_DIR).is_dir(), (
        "W-18 v11.1.0 PV-07 violation: docs/cycle-archive/v11.1.0/ "
        "directory missing per W-19; "
        "cycle plan §5.3 mandates archive committed at MINOR close. "
        "Run: python scripts/archive_research_artifacts.py 11.1.0"
    )
    assert (project_root / _V11_1_0_CYCLE_ARCHIVE_README).is_file(), (
        "W-18 v11.1.0 PV-07 violation: docs/cycle-archive/v11.1.0/README.md "
        "missing — auto-generated by archive_research_artifacts.py."
    )
    assert (project_root / _V11_1_0_CYCLE_ARCHIVE_RETROSPECTIVE).is_file(), (
        "W-18 v11.1.0 PV-07 violation: docs/cycle-archive/v11.1.0/"
        "retrospective.md missing — copy of "
        ".local/research/v11.1.0_retrospective.md per W-19 archive contract."
    )

    # W-7 SI-8 retrospective 4-section completeness — verified against
    # the TRACKED archive copy (always-on).
    archived_retro_text = (project_root / _V11_1_0_CYCLE_ARCHIVE_RETROSPECTIVE).read_text(
        encoding="utf-8"
    )
    for required_section in _V11_1_0_RETROSPECTIVE_REQUIRED_SECTIONS:
        assert required_section in archived_retro_text, (
            f"W-18 v11.1.0 PV-07 violation: archived retrospective missing "
            f"required section header {required_section!r} per W-7 / SI-8 "
            "4-section completeness mandate. Sections required: "
            f"{list(_V11_1_0_RETROSPECTIVE_REQUIRED_SECTIONS)!r}."
        )

    # .local/research/ retrospective + stage report — skip-when-absent for
    # CI / fresh clones (the .local/ directory is gitignored per
    # `.gitignore:49`).
    local_artifacts = (
        _V11_1_0_LOCAL_RETROSPECTIVE,
        _V11_1_0_LOCAL_PV07_STAGE_REPORT,
    )
    present = [p for p in local_artifacts if (project_root / p).is_file()]
    if not present:
        # CI / fresh clone path — the W-19 archive provides the canonical
        # tracked source-of-truth; the .local originals are an artifact
        # of the PV-07 author's local working tree only.
        return
    missing = [p for p in local_artifacts if not (project_root / p).is_file()]
    assert not missing, (
        f"W-18 v11.1.0 PV-07 violation: partial .local/research/ artifact "
        f"set — some present ({[str(p) for p in present]}) but others "
        f"missing ({[str(p) for p in missing]}); the PV-07 author MUST "
        f"produce BOTH the retrospective (W-7 / SI-8) AND the stage report "
        f"(L1 → L0 handoff) per cycle plan §2 PV-07 owned-files manifest."
    )


# v11.1.1 PATCH (D-1 in the v11.1.x stability-patch series; deferral D-5 in
# the v11.1.0 retrospective §3): CHANGELOG no-duplicate-version-header CI
# lint. First of 3 staged stability patches (v11.1.1 / v11.1.2 / v11.1.3)
# closing the cycle-observed risks documented in
# `docs/cycle-archive/v11.1.0/retrospective.md` §3.
#
# The lint detects the PV-03 N-2 class-of-bug at CI time so a future
# double-application (commit `da1c489` historical reference) fails the
# standard `pytest tests/ -q` sweep rather than requiring in-PV
# reconciliation. The L1-per-PV invariant (PV-03 N-2 process-side mitigation;
# v11.1.0 retrospective §4 L-2) remains the primary enforcement; this CI lint
# is the secondary belt-and-braces machinery.
_V11_1_1_LINT_FILE: Path = Path("tests/test_changelog_no_duplicate_versions.py")
_V11_1_1_CHANGELOG: Path = Path("CHANGELOG.md")

# Required public symbols in the lint module — pinned via AST so refactor
# of the function body is OK but rename / removal fails fast.
_V11_1_1_LINT_REQUIRED_SYMBOLS: tuple[str, ...] = (
    "find_duplicate_version_headers",
    "test_changelog_has_no_duplicate_version_headers",
    "test_changelog_lint_detects_synthetic_duplicate",
    "test_changelog_lint_passes_on_unique_versions",
)

# CHANGELOG body must carry the v11.1.1 PATCH entry verbatim.
_V11_1_1_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.1] - 2026-05-08",
    "PATCH",
    "CHANGELOG double-application",
)


def test_v11_1_1_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.1 PATCH: D-1 CHANGELOG no-duplicate-version-header lint.

    Discharges the W-18 precondition for the v11.1.1 PATCH CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (v11.1.1 D-1 patch scope; first of 3 staged
    v11.1.x stability patches):

    * ``tests/test_changelog_no_duplicate_versions.py`` (NEW file)
      defines the four required public symbols:

      - ``find_duplicate_version_headers`` (helper; reusable by
        future tooling such as a pre-commit hook).
      - ``test_changelog_has_no_duplicate_version_headers`` (the
        main load-bearing lint; reads the actual CHANGELOG.md).
      - ``test_changelog_lint_detects_synthetic_duplicate``
        (positive control; feeds a synthetic duplicate to the
        helper).
      - ``test_changelog_lint_passes_on_unique_versions``
        (negative control; feeds a synthetic CHANGELOG with all
        unique versions to the helper).

    * ``CHANGELOG.md`` carries the ``## [11.1.1] - 2026-05-08``
      PATCH entry mentioning ``PATCH`` + ``CHANGELOG
      double-application`` (the v11.1.0 retrospective §3 D-5
      deferral citation; the dispatcher's D-1 in-series label).

    * ``CHANGELOG.md`` ``## [11.1.1]`` section header appears
      EXACTLY once (the PV-03 N-2 single-application discipline;
      this lint runs against the new entry — proving the fix
      works on the reference CHANGELOG).

    Coupled invariants verified GREEN at PATCH close (no source
    edits to gate / schema / SKILL):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags

    Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-5
    (deferral) + §5 P-5 (next-cycle proposal).
    """
    lint_path = project_root / _V11_1_1_LINT_FILE
    assert lint_path.is_file(), (
        f"W-18 v11.1.1 violation: NEW lint file {_V11_1_1_LINT_FILE} "
        "missing. The lint MUST land in the same commit as the CHANGELOG "
        "entry per W-18 sequencing (lint BEFORE entry)."
    )

    # AST symbol pin — robust against function-body refactor; only fails
    # on rename / removal of the four contracted public symbols.
    module = ast.parse(lint_path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = [s for s in _V11_1_1_LINT_REQUIRED_SYMBOLS if s not in defined]
    assert not missing, (
        f"W-18 v11.1.1 violation: {_V11_1_1_LINT_FILE} missing required "
        f"public symbols {missing!r}. Required set: "
        f"{list(_V11_1_1_LINT_REQUIRED_SYMBOLS)!r}; defined: "
        f"{sorted(defined)!r}."
    )

    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked).
    changelog_text = (project_root / _V11_1_1_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_1_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.1 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.1.1 PATCH scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored."
        )

    # Single-application discipline (PV-03 N-2 mitigation; the bug we're
    # fixing — do NOT trip it while writing the fix). Use line-anchored
    # match (mirrors `grep -c '^## \\[11\\.1\\.1\\]'` semantics).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.1]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.1 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.1]' section "
        "headers — exactly 1 expected (PV-03 N-2 single-application "
        "discipline; the v11.1.1 D-1 patch is THIS class-of-bug fix, "
        "do not trip it while writing the fix)."
    )


# v11.1.2 PATCH (D-2 in the v11.1.x stability-patch series; deferral D-4 in
# the v11.1.0 retrospective §3): `audit_layer_usage.py` regex bold-markdown
# coverage. Second of 3 staged stability patches (v11.1.1 / v11.1.2 / v11.1.3)
# closing the cycle-observed risks documented in
# `docs/cycle-archive/v11.1.0/retrospective.md` §3.
#
# The legacy v10.5.0 regex matched only plain `Dispatch type:` text, missing
# the v11.x markdown-bold convention `**Dispatch type:** Wave` used in cycle
# plans, retrospectives, and stage reports. As a consequence, the v11.1.0
# PV-05 audit ratchet `cascade_ratio` reported 0 for v11.x cycle docs even
# though L1/L2 dispatches actually happened (the v11.1.0 cycle-archive
# retrospective + per-PV stage reports + NineS analyses contain ≥7 bold-style
# `**Dispatch type:** Wave` mentions; the OLD regex caught 0 of them).
#
# v11.1.2 D-2 widens `_DISPATCH_TYPE_RE` via the `\*{0,2}` quantifier to
# admit 0/1/2 asterisks before AND after the label and value uniformly,
# covering plain / italic / bold styles. The dual `\*{0,2}\s*\*{0,2}` slot
# between `[:=]` and the value group is intentional — it admits the
# full-bold case `**Dispatch type:** **Wave**` where the closing-label `**`
# and opening-value `**` are separated by whitespace. Capture group 1 (the
# layer name) and the `\b` word boundary + `re.IGNORECASE` flag are
# preserved so plain-text inputs match byte-identically (W-20 backward-
# compat; the existing 15 tests in `tests/test_audit_layer_usage.py` are
# preserved byte-stable).
_V11_1_2_TEST_FILE: Path = Path("tests/test_audit_layer_usage.py")
_V11_1_2_SCRIPT_FILE: Path = Path("scripts/audit_layer_usage.py")
_V11_1_2_CHANGELOG: Path = Path("CHANGELOG.md")

# Required NEW test functions in tests/test_audit_layer_usage.py — pinned
# via AST so refactor of the function body is OK but rename / removal
# fails fast. Note: only the NEW v11.1.2 tests are pinned here; the
# pre-existing 15 tests are byte-stable per W-20 backward-compat.
_V11_1_2_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_dispatch_type_regex_matches_plain_style",
    "test_dispatch_type_regex_matches_bold_markdown_style",
    "test_dispatch_type_regex_matches_bold_value_only",
    "test_dispatch_type_regex_matches_full_bold",
)

# Substrings required in scripts/audit_layer_usage.py to evidence the
# regex broadening. The source must contain `\*{0,2}` — the canonical
# marker — AND the citation back to the cycle archive.
_V11_1_2_SCRIPT_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    r"\*{0,2}",
    "v11.1.2 D-2",
    "docs/cycle-archive/v11.1.0/retrospective.md",
)

# CHANGELOG body must carry the v11.1.2 PATCH entry verbatim.
_V11_1_2_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.2] - 2026-05-08",
    "PATCH",
    "audit_layer_usage.py",
    "bold-markdown",
)


# v11.1.3 PATCH (D-3 in the v11.1.x stability-patch series; the third v11.1.x
# cycle-observed risk telegraphed at v11.1.0 cycle close): tiktoken determinism
# documentation. Third and final of 3 staged stability patches (v11.1.1 +
# v11.1.2 + v11.1.3) closing the cycle-observed risks documented in
# `docs/cycle-archive/v11.1.0/retrospective.md`.
#
# This is a PURE-DOCUMENTATION patch — zero code/test logic change. The
# `tests/conftest.py::_force_fallback_token_estimator` autouse fixture forces
# `sys.modules["tiktoken"] = None` for every `test_benchmarks.py` test so the
# fallback `len(text) // 4` token estimator runs uniformly across CI / dev /
# fresh-clone environments. This is INTENTIONAL — pinning to fallback keeps
# pytest-side composites comparable across machines. The bug it surfaces is
# operator-side: regen scripts that import `devolaflow.benchmarks` OUTSIDE
# the pytest harness do NOT see the fixture fire, so the resulting baselines
# diverge from pytest scoring by ~7pp on the composite axis.
#
# v11.1.3 D-3 closes the documentation gap on three surfaces:
#
#   1. tests/conftest.py::_force_fallback_token_estimator — docstring
#      expanded with WHY (deterministic scoring), EFFECT (~7pp divergence
#      between pytest and raw scoring), and 3 fallback options for
#      reproducing pytest scoring outside pytest (Option A: invoke under
#      pytest; Option B: pre-set sys.modules["tiktoken"] = None; Option C:
#      uninstall tiktoken). Body of the fixture preserved BYTE-IDENTICAL
#      (W-20 contract preservation — no runtime surface change).
#   2. workflow-system/agent/references/troubleshooting.md — NEW §2.16
#      "Token-estimation determinism (W-16 baseline regen)" subsection
#      with the same 3-option fallback summary, plus a §1 Quick Lookup
#      Index row and `last_updated` bump to "2026-05-08".
#   3. CHANGELOG.md ## [11.1.3] entry citing the PATCH scope, the
#      v11.1.0 retrospective source, and the v11.1.x stability-patch
#      series close.
_V11_1_3_CONFTEST_FILE: Path = Path("tests/conftest.py")
_V11_1_3_REFERENCE_FILE: Path = Path("workflow-system/agent/references/troubleshooting.md")
_V11_1_3_CHANGELOG: Path = Path("CHANGELOG.md")

# Substrings required in tests/conftest.py to evidence the docstring
# expansion. The docstring MUST cite tiktoken + W-16 + deterministic
# (the three load-bearing concepts) AND the cycle-archive citation.
_V11_1_3_CONFTEST_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "tiktoken",
    "W-16 baseline regen",
    "deterministic",
    'sys.modules["tiktoken"] = None',
    "Option A",
    "Option B",
    "Option C",
    "v11.1.3 D-3",
    "docs/cycle-archive/v11.1.0/retrospective.md",
)

# Substrings required in references/troubleshooting.md to evidence the
# new §2.16 section. The reference MUST carry the section header AND the
# same 3-option fallback summary.
_V11_1_3_REFERENCE_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "#### 2.16 Token-estimation determinism (W-16 baseline regen)",
    "_force_fallback_token_estimator",
    "Option A",
    "Option B",
    "Option C",
    'sys.modules["tiktoken"] = None',
    "v11.1.3 D-3",
)

# CHANGELOG body must carry the v11.1.3 PATCH entry verbatim.
_V11_1_3_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.3] - 2026-05-08",
    "PATCH",
    "tiktoken",
    "W-16",
    "_force_fallback_token_estimator",
)

# ---------------------------------------------------------------------------
# v11.3.0 W-18 ghost-audit pinning surface (grill-with-docs integration MINOR)
# ---------------------------------------------------------------------------
# Per W-18 sequencing the lint refresh MUST land BEFORE the v11.3.0 CHANGELOG
# entry — see ``test_v11_3_0_new_surfaces_have_coverage`` below for the full
# rationale. Constants are clustered alongside the existing v11.1.x cluster
# so future cycle-N+1 contributors find them in one place.
_V11_3_0_GRILL_MODULE_FILE: Path = Path("src/devolaflow/skills/grill_mode.py")
_V11_3_0_GRILL_TEST_FILE: Path = Path("tests/test_grill_mode.py")
_V11_3_0_DOMAIN_TEST_FILE: Path = Path("tests/test_domain_awareness.py")
_V11_3_0_GRILL_REF_FILE: Path = Path("workflow-system/agent/references/grill-mode.md")
_V11_3_0_DOMAIN_REF_FILE: Path = Path("workflow-system/agent/references/domain-awareness.md")
_V11_3_0_CHANGELOG: Path = Path("CHANGELOG.md")

# 5 public pure-function APIs on grill_mode (AST FunctionDef pin — robust
# against function-body refactor; only fails on rename / removal of the
# five contracted public symbols enumerated in gap analysis §4 P1.3).
_V11_3_0_GRILL_REQUIRED_FUNCTIONS: tuple[str, ...] = (
    "classify_grill_intent",
    "detect_fuzzy_terms",
    "qualifies_as_adr",
    "propose_canonical_term",
    "infer_context_layout",
)

# 3 public Literal type aliases on grill_mode (AST AnnAssign pin — the
# Literal verdict strings ARE the public contract per W-22 / W-23).
_V11_3_0_GRILL_REQUIRED_ALIASES: tuple[str, ...] = (
    "GrillVerdict",
    "ContextLayout",
    "AdrConditionName",
)

# 3 public frozen dataclasses on grill_mode (AST ClassDef pin — frozen
# instances flow across L0 → L3 boundaries per W-22.3 / W-23.4).
_V11_3_0_GRILL_REQUIRED_DATACLASSES: tuple[str, ...] = (
    "FuzzyTerm",
    "CanonicalTermSuggestion",
    "DecisionDescriptor",
)

# Required NEW test functions in tests/test_grill_mode.py — the canonical
# 9-name subset that the gap analysis §4 P1.6 enumerates. The L3 author
# may have authored additional tests beyond this set; we DO NOT pin those
# so the audit remains robust against later test-suite refactors that
# consolidate or expand coverage without touching the contract surface
# (over-pinning would make the audit brittle per the v11.1.2 pattern).
_V11_3_0_GRILL_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_classify_grill_intent_grill_requested",
    "test_classify_grill_intent_grill_suggested",
    "test_classify_grill_intent_no_grill",
    "test_qualifies_as_adr_all_three_conditions_pass",
    "test_qualifies_as_adr_returns_missing_when_one_fails",
    "test_propose_canonical_term_returns_none_for_canonical_input",
    "test_infer_context_layout_single_context",
    "test_infer_context_layout_multi_context",
    "test_infer_context_layout_no_context_yet",
)

# Required NEW test functions in tests/test_domain_awareness.py — the
# canonical 6-name subset enumerated in gap analysis §4 P1.6.
_V11_3_0_DOMAIN_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_context_md_required_sections_documented",
    "test_context_md_be_opinionated_rule_documented",
    "test_context_md_only_project_specific_rule_documented",
    "test_adr_format_3_condition_gate_documented",
    "test_adr_format_sequential_numbering_documented",
    "test_adr_format_minimum_body_documented",
)

# Positive substrings for grill-mode.md — the load-bearing concepts from
# the upstream grill-with-docs SKILL (one-question-at-a-time / explore
# codebase / stress-test scenarios / 3-condition gate verbatim), the 5
# public function citations, and the explicit R-11 distinction from
# interview-protocol.md (gap analysis §5 R-11 mitigation).
_V11_3_0_GRILL_REF_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "id: grill-mode",
    "tier: 2",
    "# Grill Mode",
    "Ask the questions one at a time",
    "explore the codebase instead",
    "stress-test them with specific scenarios",
    "Hard to reverse",
    "Surprising without context",
    "real trade-off",
    "classify_grill_intent",
    "qualifies_as_adr",
    "propose_canonical_term",
    "infer_context_layout",
    "detect_fuzzy_terms",
    "interview-protocol.md",
)

# Positive substrings for domain-awareness.md — the CONTEXT.md authoring
# rules, the ADR format, the historical .local/research/adr/ distinction,
# and the A-4 source-of-truth spec cross-reference.
_V11_3_0_DOMAIN_REF_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "id: domain-awareness",
    "tier: 2",
    "# Domain Awareness",
    "## Language",
    "## Relationships",
    "## Example dialogue",
    "## Flagged ambiguities",
    "When multiple words exist for the same concept",
    "list the others as aliases to avoid",
    "General programming concepts",
    "0001-slug.md",
    "An ADR can be a single paragraph",
    "Hard to reverse",
    "Surprising without context",
    ".local/research/adr/",
    "A-4",
)

# CHANGELOG.md entry positive substrings — cited but the lint allows this
# stanza to FAIL until Stage 3 authors the entry (see test docstring for
# the W-18 sequencing detail). The 6 substrings pin: the section header,
# the load-bearing scope name (grill-with-docs), the new module file, the
# two new workflow rules (W-22 + W-23), and the predecessor version
# citation (11.1.3 → 11.3.0 minor jump).
_V11_3_0_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.3.0]",
    "grill-with-docs",
    "grill_mode.py",
    "W-22",
    "W-23",
    "11.1.3",
)

# ---------------------------------------------------------------------------
# v11.4.0 W-18 ghost-audit pinning surface (subagent-patterns-2026 prep MINOR)
# ---------------------------------------------------------------------------
# Per W-18 sequencing the lint refresh MUST land BEFORE the v11.4.0 CHANGELOG
# entry — see ``test_v11_4_0_new_surfaces_have_coverage`` below for the full
# rationale. Constants are clustered alongside the v11.3.0 cluster so future
# cycle-N+1 contributors find them in one place. v11.4.0 is the deliberate
# analysis-and-lightweight-foundation prep cycle that codifies the philschmid
# 4-pattern subagent taxonomy (Inline Tool / Fan-Out / Agent Pool / Teams) as
# a Tier-2 reference (`workflow-system/agent/references/subagent-patterns.md`)
# + a pure-function selection helper (`src/devolaflow/skills/subagent_pattern.py`)
# + a NEW workflow rule W-24 — leaving the schema NEST + helper wiring for the
# v12.0.0 cycle per the PV-01 cycle plan.
_V11_4_0_SUBAGENT_MODULE_FILE: Path = Path("src/devolaflow/skills/subagent_pattern.py")
_V11_4_0_SUBAGENT_TEST_FILE: Path = Path("tests/test_subagent_patterns.py")
_V11_4_0_SUBAGENT_REF_FILE: Path = Path("workflow-system/agent/references/subagent-patterns.md")
_V11_4_0_CHANGELOG: Path = Path("CHANGELOG.md")

# 3 public pure-function APIs on subagent_pattern (AST FunctionDef pin —
# robust against function-body refactor; only fails on rename / removal of
# the three contracted public symbols enumerated in gap analysis §6 P1.6).
_V11_4_0_SUBAGENT_REQUIRED_FUNCTIONS: tuple[str, ...] = (
    "select_pattern",
    "validate_inputs",
    "forbidden_pattern_rationale",
)

# 2 public Literal type aliases on subagent_pattern (AST Assign pin — the
# Literal verdict / model-tier strings ARE the public contract per W-24;
# the module declares them via plain ``X = Literal[...]`` assignment, not
# annotated assignment, mirroring the v11.3.0 W2.T5 grill_mode precedent).
_V11_4_0_SUBAGENT_REQUIRED_ALIASES: tuple[str, ...] = (
    "PatternVerdict",
    "ModelTier",
)

# Required NEW test functions in tests/test_subagent_patterns.py — the
# canonical 12-name subset the gap analysis §6 P1.3 enumerates. The L3
# author may have added tests beyond this set; we DO NOT pin those so the
# audit remains robust against later test-suite refactors that consolidate
# or expand coverage without touching the contract surface (over-pinning
# would make the audit brittle per the v11.1.2 + v11.3.0 pattern).
_V11_4_0_SUBAGENT_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_select_pattern_inline_for_simple_single_task",
    "test_select_pattern_fan_out_for_parallel_independent_tasks",
    "test_select_pattern_agent_pool_forward_for_frontier_persistent",
    "test_select_pattern_downgrades_to_inline_when_under_resourced",
    "test_select_pattern_inline_for_sequential_dependent_tasks",
    "test_select_pattern_never_returns_teams_forbidden",
    "test_validate_inputs_raises_on_invalid_complexity",
    "test_validate_inputs_raises_on_invalid_model_tier",
    "test_validate_inputs_raises_on_zero_or_negative_task_count",
    "test_forbidden_pattern_rationale_explains_p5_for_teams",
    "test_subagent_pattern_module_zero_io_at_import",
    "test_subagent_pattern_literal_string_values_are_stable",
)

# Positive substrings for subagent-patterns.md — the load-bearing concepts
# from the upstream philschmid article (4 pattern names verbatim), the P5
# invariant citation + ``shared state`` keyword (the Pattern 4 forbidden
# anchor), the 5 public symbol citations from the Python helper, and the
# explicit R-11 disambiguation from grill-mode.md (gap analysis §8) +
# the v7.x baseline cross-reference to execution-protocol.md.
_V11_4_0_SUBAGENT_REF_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "id: subagent-patterns",
    "tier: 2",
    "# Subagent Patterns",
    "Inline Tool",
    "Fan-Out",
    "Agent Pool",
    "Teams",
    "P5",
    "shared state",
    "AGENT_POOL_FORWARD",
    "TEAMS_FORBIDDEN",
    "select_pattern",
    "validate_inputs",
    "forbidden_pattern_rationale",
    "grill-mode",
    "execution-protocol.md",
)

# CHANGELOG.md entry positive substrings — cited but the lint allows this
# stanza to FAIL until Stage 3 authors the entry (see test docstring for
# the W-18 sequencing detail). The 5 substrings pin: the section header,
# the load-bearing scope name (subagent-patterns), the new module file,
# the new workflow rule (W-24), and the predecessor version citation
# (11.3.0 → 11.4.0 minor jump).
_V11_4_0_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.4.0]",
    "subagent-patterns",
    "subagent_pattern.py",
    "W-24",
    "11.3.0",
)


def test_v11_1_3_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.3 PATCH: D-3 tiktoken determinism documentation.

    Discharges the W-18 precondition for the v11.1.3 PATCH CHANGELOG
    entry. Per W-18 sequencing the documentation refresh MUST land
    BEFORE the CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (v11.1.3 D-3 patch scope; THIRD AND FINAL of 3
    staged v11.1.x stability patches — sister patches v11.1.1 + v11.1.2):

    * ``tests/conftest.py::_force_fallback_token_estimator`` carries
      the expanded docstring covering WHY (deterministic benchmark
      scoring across environments), EFFECT (~7pp divergence between
      pytest scoring and raw subprocess scoring), and 3 OPTIONS for
      reproducing pytest scoring outside pytest:

      - Option A (preferred): invoke regen under the pytest harness so
        the autouse fixture fires automatically.
      - Option B: pre-set ``sys.modules["tiktoken"] = None`` BEFORE
        importing any devolaflow modules in the regen script.
      - Option C: uninstall tiktoken from the venv (heavy-handed —
        affects every workflow in the env).

      The fixture BODY is preserved byte-identically — only the
      docstring changed (W-20 contract preservation; no runtime
      surface delta).

    * ``workflow-system/agent/references/troubleshooting.md`` carries
      a NEW §2.16 "Token-estimation determinism (W-16 baseline regen)"
      subsection with the same 3-option fallback summary, a
      cross-reference to the conftest fixture, and a §1 Quick Lookup
      Index row pointing at §2.16. The file's frontmatter
      ``last_updated`` field is bumped to "2026-05-08".

    * ``CHANGELOG.md`` carries the ``## [11.1.3] - 2026-05-08`` PATCH
      entry mentioning ``PATCH`` + ``tiktoken`` + ``W-16`` +
      ``_force_fallback_token_estimator`` (the v11.1.0 retrospective
      cycle-close source citation).

    * ``CHANGELOG.md`` ``## [11.1.3]`` section header appears EXACTLY
      once (the v11.1.1 D-1 single-application lint pre-condition;
      this stanza independently asserts the line-anchored count via
      splitlines + line.startswith).

    Coupled invariants verified GREEN at PATCH close (no source edits
    to gate / schema / SKILL / runtime):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application — proving v11.1.1 D-1 catches its
      own next test; sister-patch chain holds across 3 patches)
    * v11.1.2 D-2 audit_layer_usage regex: 19/19 PASS unchanged
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags
    * conftest fixture body preserved BYTE-IDENTICAL (only docstring
      changed; the ``monkeypatch.setitem(sys.modules, "tiktoken",
      None)`` body is untouched)

    Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` cycle-
    close summary (the v11.1.0 PV-02 W-16 wholesale baseline regen
    was the first cycle where this divergence surfaced empirically;
    v11.1.3 D-3 closes the documentation gap and the v11.1.x
    stability-patch series).
    """
    conftest_path = project_root / _V11_1_3_CONFTEST_FILE
    assert conftest_path.is_file(), (
        f"W-18 v11.1.3 violation: conftest file {_V11_1_3_CONFTEST_FILE} missing. "
        "The docstring expansion MUST land in the same commit as "
        "the CHANGELOG entry per W-18 sequencing."
    )

    conftest_text = conftest_path.read_text(encoding="utf-8")
    for sub in _V11_1_3_CONFTEST_POSITIVE_SUBSTRINGS:
        assert sub in conftest_text, (
            f"W-18 v11.1.3 violation: {_V11_1_3_CONFTEST_FILE} missing "
            f"positive substring {sub!r} — the v11.1.3 D-3 docstring "
            "expansion MUST cite the load-bearing concepts (tiktoken + "
            "W-16 + deterministic + the 3 fallback options + the "
            "cycle-archive retrospective citation)."
        )

    reference_path = project_root / _V11_1_3_REFERENCE_FILE
    assert reference_path.is_file(), (
        f"W-18 v11.1.3 violation: reference file {_V11_1_3_REFERENCE_FILE} missing. "
        "The new §2.16 subsection MUST land in the same commit as "
        "the CHANGELOG entry per W-18 sequencing."
    )

    reference_text = reference_path.read_text(encoding="utf-8")
    for sub in _V11_1_3_REFERENCE_POSITIVE_SUBSTRINGS:
        assert sub in reference_text, (
            f"W-18 v11.1.3 violation: {_V11_1_3_REFERENCE_FILE} missing "
            f"positive substring {sub!r} — the v11.1.3 D-3 §2.16 "
            "subsection MUST carry the section header + the 3-option "
            "fallback summary + the conftest cross-reference."
        )

    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked).
    changelog_text = (project_root / _V11_1_3_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_3_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.3 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.1.3 PATCH scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface
    # any drift before the cross-test runs).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.3]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.3 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.3]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.1.3 D-3 patch INHERITS the v11.1.1 "
        "discipline cleanly across 3 patches — do not trip the "
        "predecessor's lint while writing the successor's fix)."
    )


def test_v11_3_0_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.3.0 MINOR: grill-with-docs integration cycle.

    Discharges the W-18 precondition for the v11.3.0 MINOR CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition. Until
    Stage 3 lands the entry the CHANGELOG portion of this test FAILS
    intentionally; that failure IS the W-18 lint gate working as
    designed and is the signal Stage 3 needs to author the entry.

    Surfaces pinned (v11.3.0 grill-with-docs integration cycle):

    * ``src/devolaflow/skills/grill_mode.py`` carries 5 public
      pure-function APIs (AST symbol pin):

      - ``classify_grill_intent`` — natural-language activation
        classifier returning
        ``Literal["GRILL_REQUESTED", "GRILL_SUGGESTED", "NO_GRILL"]``.
      - ``detect_fuzzy_terms`` — scans a plan text against a
        CONTEXT.md glossary, returning ``FuzzyTerm`` entries for each
        ``Avoid:`` alias match.
      - ``qualifies_as_adr`` — applies the 3-condition ADR gate
        (Hard to reverse + Surprising without context + Real
        trade-off); returns ``(qualifies, missing_conditions)``.
      - ``propose_canonical_term`` — suggests the canonical
        replacement for a fuzzy candidate term.
      - ``infer_context_layout`` — filesystem probe returning
        ``Literal["SINGLE_CONTEXT", "MULTI_CONTEXT", "NO_CONTEXT_YET"]``.

      3 public ``Literal`` type aliases (AST AnnAssign pin):
      ``GrillVerdict``, ``ContextLayout``, ``AdrConditionName``.

      3 public frozen dataclasses (AST ClassDef pin):
      ``FuzzyTerm``, ``CanonicalTermSuggestion``, ``DecisionDescriptor``.

    * ``tests/test_grill_mode.py`` carries the 9 canonical NEW test
      functions enumerated in ``.local/research/v11.3.0_gap_analysis.md``
      §4 P1.6. The L3 author may have added tests beyond this set —
      we pin only the canonical 9 so the audit remains robust against
      test-suite expansion (over-pinning would make the audit brittle).

    * ``tests/test_domain_awareness.py`` carries the 6 canonical NEW
      test functions enumerated in §4 P1.6.

    * ``workflow-system/agent/references/grill-mode.md`` (Tier-2
      reference, ≤ 1000 lines per C-4 Large tier) carries the
      operating contract — frontmatter (``id: grill-mode`` /
      ``tier: 2``), the load-bearing verbatim quotes from upstream
      SKILL.md (one-question-at-a-time / explore codebase /
      stress-test scenarios / 3-condition gate), all 5 public
      function citations, and the explicit R-11 distinction from
      ``interview-protocol.md`` (gap analysis §5 risk R-11).

    * ``workflow-system/agent/references/domain-awareness.md``
      (Tier-2, ≤ 1000 lines) carries the CONTEXT.md authoring rules
      (Language / Relationships / Example dialogue / Flagged
      ambiguities sections) + ADR format (``0001-slug.md`` numbering,
      single-paragraph minimum body) + the historical
      ``.local/research/adr/`` distinction + the A-4 source-of-truth
      spec cross-reference.

    * ``CHANGELOG.md`` carries the ``## [11.3.0]`` MINOR entry
      mentioning ``grill-with-docs`` + ``grill_mode.py`` + ``W-22`` +
      ``W-23`` + ``11.1.3`` (predecessor version citation). NOTE:
      per W-18 sequencing this stanza is authored BEFORE the
      CHANGELOG entry; until Stage 3 lands the entry, this portion
      of the test FAILS — that is INTENTIONAL and is the W-18 lint
      gate working as designed.

    * ``CHANGELOG.md`` ``## [11.3.0]`` section header appears EXACTLY
      once (v11.1.1 D-1 single-application lint inheritance — this
      stanza preserves the line-anchored count discipline across the
      v11.1.x → v11.3.0 MINOR boundary).

    Coupled invariants verified GREEN at MINOR close (no source edits
    to gate / schema / S-10 hooks):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; no new dispatch keys per gap
      analysis §5 risk R-5).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * CP-4 gate suite: 108/108 PASS unchanged (no
      ``src/devolaflow/gate/`` edits).
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application — proving v11.1.1 D-1 catches its
      own next test; sister-patch-pattern inheritance preserved
      across the v11.1.x → v11.3.0 MINOR boundary).
    * v11.1.2 D-2 audit_layer_usage regex: 19/19 PASS unchanged.
    * v11.1.3 D-3 conftest fixture: byte-stable; the W-16 baseline
      regen for v11.3.0 cycle start MUST run under the pytest
      harness for tiktoken determinism.
    * W-21 Soul-set freeze preserved at 10 entries (no S-11
      proposed; W-22 + W-23 land at Workflow layer, architecturally
      correct per ADR-007 §"Soul-vs-Architecture decision-rule").
    * W-20 reuse-first preserved at 8 env flags (NO new
      ``DEVOLAFLOW_*`` env flag introduced; grill-mode activation is
      natural-language-only per W-22.4).

    Source: ``.local/research/v11.3.0_gap_analysis.md`` §4 P1.7
    (W-18 ghost-audit refresh BEFORE CHANGELOG entry sequencing).
    """
    # ----- 1. grill_mode.py public API surface (AST pin) -----
    grill_module_path = project_root / _V11_3_0_GRILL_MODULE_FILE
    assert grill_module_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing. "
        "The grill_mode module MUST land in the same MINOR cycle as the "
        "CHANGELOG entry per W-18 sequencing."
    )
    grill_module = ast.parse(grill_module_path.read_text(encoding="utf-8"))

    defined_funcs = {
        node.name
        for node in grill_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_funcs = [f for f in _V11_3_0_GRILL_REQUIRED_FUNCTIONS if f not in defined_funcs]
    assert not missing_funcs, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing "
        f"required public functions {missing_funcs!r}. Required set: "
        f"{list(_V11_3_0_GRILL_REQUIRED_FUNCTIONS)!r}; "
        f"defined: {sorted(defined_funcs)!r}."
    )

    # Literal type aliases in grill_mode.py use plain Assign (e.g.,
    # ``GrillVerdict = Literal[...]``) per the existing v11.3.0 module
    # style; private constants (``_REQUESTED_TRIGGERS: Final = ...``)
    # use AnnAssign. Both node forms are walked so the public Literal
    # aliases surface regardless of which annotation style the L3 author
    # picked. Extras in ``defined_aliases`` are harmless — the missing
    # check only fails if a REQUIRED name is absent.
    defined_aliases: set[str] = set()
    for node in grill_module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_aliases.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_aliases.add(node.target.id)
    missing_aliases = [a for a in _V11_3_0_GRILL_REQUIRED_ALIASES if a not in defined_aliases]
    assert not missing_aliases, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing "
        f"required Literal aliases {missing_aliases!r}. Required set: "
        f"{list(_V11_3_0_GRILL_REQUIRED_ALIASES)!r}; "
        f"defined: {sorted(defined_aliases)!r}."
    )

    defined_classes = {node.name for node in grill_module.body if isinstance(node, ast.ClassDef)}
    missing_classes = [c for c in _V11_3_0_GRILL_REQUIRED_DATACLASSES if c not in defined_classes]
    assert not missing_classes, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing "
        f"required frozen dataclasses {missing_classes!r}. Required set: "
        f"{list(_V11_3_0_GRILL_REQUIRED_DATACLASSES)!r}; "
        f"defined: {sorted(defined_classes)!r}."
    )

    # ----- 2. test_grill_mode.py NEW test surface (AST pin; canonical subset) -----
    grill_test_path = project_root / _V11_3_0_GRILL_TEST_FILE
    assert grill_test_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_TEST_FILE} missing. "
        "The grill_mode test surface MUST land in the same MINOR cycle "
        "as the CHANGELOG entry per W-18 sequencing."
    )
    grill_test_module = ast.parse(grill_test_path.read_text(encoding="utf-8"))
    grill_defined_tests = {
        node.name
        for node in grill_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_grill_tests = [
        t for t in _V11_3_0_GRILL_REQUIRED_NEW_TESTS if t not in grill_defined_tests
    ]
    assert not missing_grill_tests, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_TEST_FILE} missing "
        f"required NEW test functions {missing_grill_tests!r}. Required "
        f"canonical subset (gap analysis §4 P1.6): "
        f"{list(_V11_3_0_GRILL_REQUIRED_NEW_TESTS)!r}."
    )

    # ----- 3. test_domain_awareness.py NEW test surface (AST pin) -----
    domain_test_path = project_root / _V11_3_0_DOMAIN_TEST_FILE
    assert domain_test_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_TEST_FILE} missing. "
        "The domain_awareness test surface MUST land in the same MINOR "
        "cycle as the CHANGELOG entry per W-18 sequencing."
    )
    domain_test_module = ast.parse(domain_test_path.read_text(encoding="utf-8"))
    domain_defined_tests = {
        node.name
        for node in domain_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_domain_tests = [
        t for t in _V11_3_0_DOMAIN_REQUIRED_NEW_TESTS if t not in domain_defined_tests
    ]
    assert not missing_domain_tests, (
        f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_TEST_FILE} missing "
        f"required NEW test functions {missing_domain_tests!r}. Required "
        f"canonical subset (gap analysis §4 P1.6): "
        f"{list(_V11_3_0_DOMAIN_REQUIRED_NEW_TESTS)!r}."
    )

    # ----- 4. grill-mode.md content surface (positive-substring pin) -----
    grill_ref_path = project_root / _V11_3_0_GRILL_REF_FILE
    assert grill_ref_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_REF_FILE} missing. "
        "The grill-mode operating-contract reference MUST land in the "
        "same MINOR cycle as the CHANGELOG entry per W-18 sequencing."
    )
    grill_ref_text = grill_ref_path.read_text(encoding="utf-8")
    for sub in _V11_3_0_GRILL_REF_POSITIVE_SUBSTRINGS:
        assert sub in grill_ref_text, (
            f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_REF_FILE} missing "
            f"positive substring {sub!r} — the grill-mode reference MUST "
            "carry the load-bearing verbatim quotes (one-question-at-a-time "
            "/ explore codebase / stress-test scenarios / 3-condition gate), "
            "all 5 public function citations, and the explicit R-11 "
            "distinction from interview-protocol.md."
        )

    # ----- 5. domain-awareness.md content surface (positive-substring pin) -----
    domain_ref_path = project_root / _V11_3_0_DOMAIN_REF_FILE
    assert domain_ref_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_REF_FILE} missing. "
        "The domain-awareness reference MUST land in the same MINOR "
        "cycle as the CHANGELOG entry per W-18 sequencing."
    )
    domain_ref_text = domain_ref_path.read_text(encoding="utf-8")
    for sub in _V11_3_0_DOMAIN_REF_POSITIVE_SUBSTRINGS:
        assert sub in domain_ref_text, (
            f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_REF_FILE} missing "
            f"positive substring {sub!r} — the domain-awareness reference "
            "MUST carry the CONTEXT.md authoring rules + ADR format + the "
            "historical .local/research/adr/ distinction + the A-4 "
            "source-of-truth spec cross-reference."
        )

    # ----- 6. CHANGELOG.md entry (positive-substring + line-anchored count) -----
    # Per W-18 sequencing this stanza is authored BEFORE the CHANGELOG entry;
    # until Stage 3 lands the entry, the assertions below FAIL — that is the
    # W-18 lint gate working as designed (the failure IS the signal).
    changelog_path = project_root / _V11_3_0_CHANGELOG
    assert changelog_path.is_file(), (
        "W-18 v11.3.0 violation: CHANGELOG.md missing — release-blocker."
    )
    changelog_text = changelog_path.read_text(encoding="utf-8")
    for sub in _V11_3_0_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.3.0 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.3.0 MINOR scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored mentioning the "
            "load-bearing concepts (grill-with-docs + grill_mode.py + "
            "W-22 + W-23 + 11.1.3 predecessor)."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface any
    # drift before the cross-test runs across the MINOR boundary).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.3.0]")
    )
    assert section_header_count == 1, (
        "W-18 v11.3.0 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.3.0]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.3.0 MINOR INHERITS the v11.1.x "
        "discipline cleanly across the MINOR boundary — do not trip the "
        "predecessor's lint while writing the successor's entry)."
    )


def test_v11_4_0_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.4.0 MINOR: subagent-patterns-2026 prep cycle.

    Discharges the W-18 precondition for the v11.4.0 MINOR CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition. Until
    Stage 3 lands the entry the CHANGELOG portion of this test FAILS
    intentionally; that failure IS the W-18 lint gate working as
    designed and is the signal Stage 3 needs to author the entry.

    Surfaces pinned (v11.4.0 subagent-patterns prep cycle):

    * ``src/devolaflow/skills/subagent_pattern.py`` carries 3 public
      pure-function APIs (AST symbol pin):

      - ``select_pattern`` — 5-axis decision rule mapping
        ``(complexity, model_tier, task_count, parallel_independence,
        persistent_state_needed)`` to a
        ``Literal["INLINE", "FAN_OUT", "AGENT_POOL_FORWARD",
        "TEAMS_FORBIDDEN"]`` verdict; never returns TEAMS_FORBIDDEN
        from the operator-facing happy path (TEAMS_FORBIDDEN is the
        forbidden-pattern sentinel surfaced only by
        ``forbidden_pattern_rationale``).
      - ``validate_inputs`` — S-5 explicit-error contract; raises
        :class:`ValueError` on invalid complexity / model_tier /
        task_count (no silent coercion).
      - ``forbidden_pattern_rationale`` — operator-education path
        returning the structured P5 + Soul-level + W-21 reversal-
        pathway rationale for ``TEAMS_FORBIDDEN``; ``None`` for the
        other three verdicts.

      2 public ``Literal`` type aliases (AST Assign pin — the module
      declares them via plain ``X = Literal[...]`` assignment per the
      v11.3.0 W2.T5 grill_mode precedent):
      ``PatternVerdict``, ``ModelTier``.

    * ``tests/test_subagent_patterns.py`` carries the 12 canonical NEW
      test functions enumerated in
      ``.local/research/v11.4.0_subagent_pattern_analysis.md`` §6 P1.3
      (the L3 author may have ADDED tests beyond this set — we pin
      only the canonical set so the audit remains robust against
      test-suite expansion).

    * ``workflow-system/agent/references/subagent-patterns.md``
      (Tier-2 reference, ≤ 1000 lines per C-4 Large tier) carries
      the operating contract — frontmatter (``id: subagent-patterns``
      / ``tier: 2``), all 4 pattern names verbatim (Inline Tool /
      Fan-Out / Agent Pool / Teams), the P5 invariant citation and
      ``shared state`` keyword (the Pattern 4 forbidden anchor), all
      5 public symbol citations (``PatternVerdict``, ``ModelTier``,
      ``select_pattern``, ``validate_inputs``,
      ``forbidden_pattern_rationale``), and the explicit
      disambiguation from ``grill-mode.md`` (R-11 mitigation per gap
      analysis §8) + the v7.x baseline cross-reference to
      ``execution-protocol.md``.

    * ``CHANGELOG.md`` carries the ``## [11.4.0]`` MINOR entry
      mentioning ``subagent-patterns`` + ``subagent_pattern.py`` +
      ``W-24`` + ``11.3.0`` (predecessor version citation). NOTE:
      per W-18 sequencing this stanza is authored BEFORE the
      CHANGELOG entry; until Stage 3 lands the entry, this portion
      of the test FAILS — that is INTENTIONAL and is the W-18 lint
      gate working as designed.

    * ``CHANGELOG.md`` ``## [11.4.0]`` section header appears EXACTLY
      once (v11.1.1 D-1 single-application lint inheritance — this
      stanza preserves the line-anchored count discipline across the
      v11.3.0 → v11.4.0 MINOR boundary).

    Coupled invariants verified GREEN at MINOR close (no source edits
    to gate / schema / S-10 hooks):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; no new dispatch keys per gap
      analysis §8 risk R-5).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * CP-4 gate suite: 108/108 PASS unchanged (no
      ``src/devolaflow/gate/`` edits).
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11
      proposed; W-24 lands at Workflow layer, mirroring W-22's
      placement rationale per ADR-007 §"Soul-vs-Architecture
      decision-rule").
    * W-20 reuse-first preserved at 8 env flags (NO new
      ``DEVOLAFLOW_*`` env flag introduced; subagent-pattern
      activation is natural-language-only per W-24.4).

    Source: ``.local/research/v11.4.0_subagent_pattern_analysis.md``
    §6 P1.6 (W-18 ghost-audit refresh BEFORE CHANGELOG entry sequencing).
    """
    # ----- 1. subagent_pattern.py public API surface (AST pin) -----
    subagent_module_path = project_root / _V11_4_0_SUBAGENT_MODULE_FILE
    assert subagent_module_path.is_file(), (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_MODULE_FILE} missing. "
        "The subagent_pattern module MUST land in the same MINOR cycle as the "
        "CHANGELOG entry per W-18 sequencing."
    )
    subagent_module = ast.parse(subagent_module_path.read_text(encoding="utf-8"))

    defined_funcs = {
        node.name
        for node in subagent_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_funcs = [f for f in _V11_4_0_SUBAGENT_REQUIRED_FUNCTIONS if f not in defined_funcs]
    assert not missing_funcs, (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_MODULE_FILE} missing "
        f"required public functions {missing_funcs!r}. Required set: "
        f"{list(_V11_4_0_SUBAGENT_REQUIRED_FUNCTIONS)!r}; "
        f"defined: {sorted(defined_funcs)!r}."
    )

    # Literal aliases — handle both ``ast.Assign`` and ``ast.AnnAssign`` per
    # the v11.3.0 W2.T5 precedent: ``subagent_pattern.py`` declares the
    # Literal aliases via plain ``X = Literal[...]`` assignment (not
    # annotated assignment), so the AST walker MUST cover both node forms
    # for the pin to remain robust. Extras in ``defined_aliases`` are
    # harmless — the missing check only fails if a REQUIRED name is absent.
    defined_aliases: set[str] = set()
    for node in subagent_module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_aliases.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_aliases.add(node.target.id)
    missing_aliases = [a for a in _V11_4_0_SUBAGENT_REQUIRED_ALIASES if a not in defined_aliases]
    assert not missing_aliases, (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_MODULE_FILE} missing "
        f"required Literal aliases {missing_aliases!r}. Required set: "
        f"{list(_V11_4_0_SUBAGENT_REQUIRED_ALIASES)!r}; "
        f"defined: {sorted(defined_aliases)!r}."
    )

    # ----- 2. test_subagent_patterns.py NEW test surface (AST pin; subset) -----
    subagent_test_path = project_root / _V11_4_0_SUBAGENT_TEST_FILE
    assert subagent_test_path.is_file(), (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_TEST_FILE} missing. "
        "The subagent_pattern test surface MUST land in the same MINOR cycle "
        "as the CHANGELOG entry per W-18 sequencing."
    )
    subagent_test_module = ast.parse(subagent_test_path.read_text(encoding="utf-8"))
    subagent_defined_tests = {
        node.name
        for node in subagent_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_subagent_tests = [
        t for t in _V11_4_0_SUBAGENT_REQUIRED_NEW_TESTS if t not in subagent_defined_tests
    ]
    assert not missing_subagent_tests, (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_TEST_FILE} missing "
        f"required NEW test functions {missing_subagent_tests!r}. Required "
        f"canonical subset (gap analysis §6 P1.3): "
        f"{list(_V11_4_0_SUBAGENT_REQUIRED_NEW_TESTS)!r}."
    )

    # ----- 3. subagent-patterns.md content surface (positive-substring pin) -----
    subagent_ref_path = project_root / _V11_4_0_SUBAGENT_REF_FILE
    assert subagent_ref_path.is_file(), (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_REF_FILE} missing. "
        "The subagent-patterns operating-contract reference MUST land in the "
        "same MINOR cycle as the CHANGELOG entry per W-18 sequencing."
    )
    subagent_ref_text = subagent_ref_path.read_text(encoding="utf-8")
    for sub in _V11_4_0_SUBAGENT_REF_POSITIVE_SUBSTRINGS:
        assert sub in subagent_ref_text, (
            f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_REF_FILE} missing "
            f"positive substring {sub!r} — the subagent-patterns reference "
            "MUST carry the 4 pattern names verbatim (Inline Tool / Fan-Out / "
            "Agent Pool / Teams), the P5 invariant citation + shared-state "
            "keyword (Pattern 4 forbidden anchor), all 5 public symbol "
            "citations, and the explicit R-11 disambiguation from "
            "grill-mode.md."
        )

    # ----- 4. CHANGELOG.md entry (positive-substring + line-anchored count) -----
    # Per W-18 sequencing this stanza is authored BEFORE the CHANGELOG entry;
    # until Stage 3 lands the entry, the assertions below FAIL — that is the
    # W-18 lint gate working as designed (the failure IS the signal).
    changelog_path = project_root / _V11_4_0_CHANGELOG
    assert changelog_path.is_file(), (
        "W-18 v11.4.0 violation: CHANGELOG.md missing — release-blocker."
    )
    changelog_text = changelog_path.read_text(encoding="utf-8")
    for sub in _V11_4_0_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.4.0 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.4.0 MINOR scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored mentioning the "
            "load-bearing concepts (subagent-patterns + subagent_pattern.py + "
            "W-24 + 11.3.0 predecessor)."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface any
    # drift before the cross-test runs across the MINOR boundary).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.4.0]")
    )
    assert section_header_count == 1, (
        "W-18 v11.4.0 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.4.0]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.4.0 MINOR INHERITS the v11.3.0 "
        "discipline cleanly across the MINOR boundary — do not trip the "
        "predecessor's lint while writing the successor's entry)."
    )


# ---------------------------------------------------------------------------
# v12.0.0 PV-02 D-1 — A-7 STRICT graduation lint
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.0.0
# CHANGELOG entry (which PV-07 owns). This stanza closes that precondition
# at the source of the BREAKING graduation: scorer.py + audit_layer_usage.py
# + the cascade-enforcement test suite. The CHANGELOG positive-substring pin
# is intentionally OMITTED here — PV-07 owns the rollup CHANGELOG, and per
# the v12.0.0 cycle plan §8.4 the version bump + CHANGELOG entry are
# deferred to the cycle-rollup commit. PV-02 only ships the source-side
# pins. The L0 cycle-lead refreshes this stanza at PV-07 to add the
# ``## [12.0.0]`` substring assertions once the rollup CHANGELOG lands.
# Source: ``.local/research/v12.0.0_gap_analysis.md`` §3 (D-1 spec) + §8.4
# (PV-07 owns the bump).
_V12_0_0_PV02_SCORER_FILE: Path = Path("src/devolaflow/gate/scorer.py")
_V12_0_0_PV02_AUDIT_FILE: Path = Path("scripts/audit_layer_usage.py")
_V12_0_0_PV02_TEST_FILE: Path = Path("tests/test_cascade_enforcement.py")

# Required NEW test functions in tests/test_cascade_enforcement.py — the
# canonical 7-name Branch 6 subset enumerated in
# ``.local/research/v12.0.0_gap_analysis.md`` §3.3 PV-02 NEW tests row.
# The L3 author may have ADDED tests beyond this set; we DO NOT pin those
# so the audit remains robust against later test-suite refactors that
# consolidate or expand coverage.
_V12_0_0_PV02_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_cascade_violation_error_inherits_from_exception",
    "test_cascade_violation_error_message_cites_a7",
    "test_validate_cascade_gate_fields_raises_on_missing_cascade_required",
    "test_validate_cascade_gate_fields_raises_on_invalid_type",
    "test_validate_cascade_gate_fields_raises_on_actual_layers_below_min",
    "test_validate_cascade_gate_fields_returns_none_on_pass",
    "test_audit_strict_default_on_v12_0_0",
)

# Positive substrings for ``scripts/audit_layer_usage.py`` source — pin
# the v12.0.0 default-ON marker (``strict: bool = True``) AND the new
# ``--no-strict`` opt-out flag AND the v12.0.0 PV-02 D-1 citation in
# the source comment. The substring pinning ensures a future maintainer
# cannot silently revert the BREAKING flip without tripping this lint.
_V12_0_0_PV02_AUDIT_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "strict: bool = True",
    "--no-strict",
    "v12.0.0 PV-02 D-1",
)


def test_v12_0_0_pv02_d1_strict_promotion(project_root: Path) -> None:
    """W-18 v12.0.0 PV-02 D-1: A-7 STRICT graduation source-side pins.

    Discharges the W-18 precondition for the BREAKING D-1 graduation.
    Per the v12.0.0 cycle plan §8.4 the version bump + CHANGELOG
    rollup are deferred to PV-07; this stanza only pins the source-side
    surfaces that PV-02 owns. PV-07's W-18 stanza will extend this with
    the ``## [12.0.0]`` CHANGELOG positive-substring assertion.

    Surfaces pinned (v12.0.0 PV-02 D-1 STRICT-graduation scope; first of
    4 v12.0.0 graduation commitments — sister PVs PV-03 D-2 SHORTCUT
    retirement, PV-04 NEW subagent NEST, PV-05 D-5 CONDITIONAL):

    * ``src/devolaflow/gate/scorer.py`` carries the NEW
      ``CascadeViolationError`` exception class (AST ``ClassDef`` pin —
      robust against body refactor; only fails on rename / removal).
      The exception MUST subclass :class:`Exception` directly (not
      :class:`ValueError`) per v12.0.0 PV-02 D-1 design rationale —
      callers writing ``except CascadeViolationError`` should not
      accidentally catch unrelated ValueErrors raised in the same
      try-block.

    * ``src/devolaflow/gate/scorer.py::validate_cascade_gate_fields``
      return annotation is ``None`` (NOT ``list[str]`` — the v11.x
      SOFT contract is REMOVED at v12.0.0 per the BREAKING graduation).
      AST ``FunctionDef.returns`` pin — robust against body refactor.

    * ``scripts/audit_layer_usage.py`` carries the v12.0.0 PV-02 D-1
      default-ON marker — the source MUST contain the substring
      ``strict: bool = True`` (the new default in ``run()`` signature)
      AND ``--no-strict`` (the new CLI opt-out flag) AND
      ``v12.0.0 PV-02 D-1`` (the citation comment that anchors the
      graduation trail in source).

    * ``tests/test_cascade_enforcement.py`` carries the 7 canonical NEW
      test functions enumerated in
      ``.local/research/v12.0.0_gap_analysis.md`` §3.3 PV-02 row (the
      L3 author may have ADDED tests beyond this set — we pin only the
      canonical subset so the audit stays robust against test-suite
      expansion).

    Coupled invariants verified GREEN at PV-02 close (no source edits
    to schemas / .rules / SKILL / CHANGELOG per cycle plan §8.4):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; PV-04 owns the schema NEST that
      adds the 33rd baseline).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * CP-4 gate suite: byte-stable EXCEPT for the
      ``TestCascadeGateFieldsValidator`` class which carries the
      v11.x SOFT-mode tests; those tests are EXPECTED to FAIL post-
      PV-02 as the soft contract is the BREAKING-removed surface.
      The L0 cycle-lead lands the ``TestCascadeGateFieldsValidator``
      refresh at PV-02 stage close OR via a follow-up PV inside the
      cycle.
    * v11.1.1 D-1 CHANGELOG lint: PASS (PV-02 makes ZERO CHANGELOG
      edits per cycle plan §8.4 PV-07-owns-rollup).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11 proposed;
      A-7 stays at Architecture per ADR-007 §"Soul-vs-Architecture"
      decision-rule).
    * W-20 reuse-first preserved at 8 env flags (NO new
      ``DEVOLAFLOW_*`` env flag introduced — the audit ratchet's
      default-ON is a runtime flip, not a new env-flag surface).

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §3 (D-1 spec)
    + §8.4 (PV-07-owns-bump separation rationale) +
    ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-1 (telegraph).
    """
    # ----- 1. scorer.py — CascadeViolationError class + return-None pin -----
    scorer_path = project_root / _V12_0_0_PV02_SCORER_FILE
    assert scorer_path.is_file(), (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} missing — "
        "release-blocker. The STRICT graduation lands AT this file."
    )
    scorer_module = ast.parse(scorer_path.read_text(encoding="utf-8"))

    # CascadeViolationError class pin (AST ClassDef walk — robust against
    # body refactor; only fails on rename / removal).
    cascade_err_class = next(
        (
            node
            for node in scorer_module.body
            if isinstance(node, ast.ClassDef) and node.name == "CascadeViolationError"
        ),
        None,
    )
    assert cascade_err_class is not None, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} missing "
        "``CascadeViolationError`` class definition. Per the v12.0.0 PV-02 "
        "D-1 STRICT graduation, the exception class MUST be defined at "
        "module scope so callers can ``from devolaflow.gate.scorer import "
        "CascadeViolationError``."
    )

    # The class MUST subclass Exception (not ValueError) per the design
    # rationale documented in CascadeViolationError.__doc__. AST base
    # walk — accept either ``Exception`` (bare ``ast.Name``) or any
    # qualified name ending in ``.Exception``.
    base_names: list[str] = []
    for base in cascade_err_class.bases:
        if isinstance(base, ast.Name):
            base_names.append(base.id)
        elif isinstance(base, ast.Attribute):
            base_names.append(base.attr)
    assert "Exception" in base_names, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} "
        f"``CascadeViolationError`` bases drift to {base_names!r}; expected "
        "``Exception`` directly per v12.0.0 PV-02 D-1 design (callers writing "
        "``except CascadeViolationError`` must not accidentally catch "
        "unrelated ValueErrors)."
    )

    # validate_cascade_gate_fields return annotation pin: AST
    # ``FunctionDef.returns`` MUST be ``None`` (a ``Constant(value=None)``
    # node), NOT a ``Subscript`` like ``list[str]``. The v11.x SOFT
    # contract returned ``list[str]``; v12.0.0 STRICT returns ``None``.
    validator_func = next(
        (
            node
            for node in scorer_module.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == "validate_cascade_gate_fields"
        ),
        None,
    )
    assert validator_func is not None, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} missing "
        "``validate_cascade_gate_fields`` function definition."
    )
    returns = validator_func.returns
    assert returns is not None, (
        "W-18 v12.0.0 PV-02 violation: ``validate_cascade_gate_fields`` "
        "return annotation is missing — the BREAKING graduation requires "
        "an explicit ``-> None`` annotation so static type checkers catch "
        "v11.x callers consuming the (now-removed) warning list."
    )
    is_none_constant = isinstance(returns, ast.Constant) and returns.value is None
    assert is_none_constant, (
        f"W-18 v12.0.0 PV-02 violation: ``validate_cascade_gate_fields`` "
        f"return annotation is {ast.unparse(returns)!r}; expected ``None`` "
        "per v12.0.0 PV-02 D-1 BREAKING graduation. The v11.x ``list[str]`` "
        "SOFT-mode return contract is REMOVED — STRICT mode raises on "
        "violations and returns ``None`` on every passing path."
    )

    # ----- 2. audit_layer_usage.py — default-ON marker + --no-strict + citation -----
    audit_path = project_root / _V12_0_0_PV02_AUDIT_FILE
    assert audit_path.is_file(), (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_AUDIT_FILE} missing — "
        "release-blocker. The audit ratchet default-ON flip lands AT this file."
    )
    audit_text = audit_path.read_text(encoding="utf-8")
    for sub in _V12_0_0_PV02_AUDIT_POSITIVE_SUBSTRINGS:
        assert sub in audit_text, (
            f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_AUDIT_FILE} "
            f"missing positive substring {sub!r}. The v12.0.0 PV-02 D-1 "
            "default-ON graduation MUST surface the new ``strict: bool = True`` "
            "default on ``run()``, the ``--no-strict`` CLI opt-out, and the "
            "``v12.0.0 PV-02 D-1`` citation comment that anchors the trail."
        )

    # ----- 3. test_cascade_enforcement.py — 7 NEW tests AST pin -----
    test_path = project_root / _V12_0_0_PV02_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_TEST_FILE} missing — release-blocker."
    )
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined_tests = {
        node.name
        for node in test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = [t for t in _V12_0_0_PV02_REQUIRED_NEW_TESTS if t not in defined_tests]
    assert not missing, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_TEST_FILE} missing "
        f"required NEW test functions {missing!r}. Required canonical "
        f"7-name set (gap analysis §3.3): "
        f"{list(_V12_0_0_PV02_REQUIRED_NEW_TESTS)!r}."
    )


# ---------------------------------------------------------------------------
# v12.0.0 PV-03 D-2 — SHORTCUT_SIMPLE retirement lint
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.0.0
# CHANGELOG entry (which PV-07 owns). This stanza closes that precondition
# at the source of the BREAKING retirement: the v9.3.0 PV-06 SHORTCUT_SIMPLE
# verdict + shortcut_verdict / shortcut_from_env helpers + SHORTCUT_FLAG_NAME
# constant + DEVOLAFLOW_SIMPLE_SHORTCUT env flag are all DELETED at v12.0.0
# PV-03. The CHANGELOG positive-substring pin is intentionally OMITTED here —
# PV-07 owns the rollup CHANGELOG, and per the v12.0.0 cycle plan §8.4 the
# version bump + CHANGELOG entry are deferred to the cycle-rollup commit.
# PV-03 only ships the source-side / inventory-side / test-deletion pins.
# Source: ``.local/research/v12.0.0_gap_analysis.md`` §4 (D-2 spec) + §8.4
# (PV-07 owns the bump) + ``docs/cycle-archive/v11.1.0/retrospective.md``
# §3 D-2 (telegraph rationale; env-flag count 8 → 7).
_V12_0_0_PV03_CHANGE_ACTIVATION_FILE: Path = Path("src/devolaflow/skills/change_activation.py")
_V12_0_0_PV03_ENV_FLAGS_FILE: Path = Path("workflow-system/agent/references/env-flags.md")
_V12_0_0_PV03_DELETED_TEST_FILE: Path = Path("tests/test_simple_shortcut.py")

# Symbols deleted from ``change_activation.py`` per v12.0.0 PV-03 D-2.
# The AST walk below proves NONE of these names appear at module scope as
# either a top-level ``ast.FunctionDef`` / ``ast.AsyncFunctionDef`` (for the
# two function entries) or as a top-level ``ast.AnnAssign`` / ``ast.Assign``
# target (for ``ShortcutVerdict`` / ``SHORTCUT_FLAG_NAME`` /
# ``SHORTCUT_FLAG_TRUTHY``). The ``_VALID_SHORTCUT_VERDICTS`` private cache
# is also covered because it derived from the public ``ShortcutVerdict``
# Literal alias and was deleted alongside it.
_V12_0_0_PV03_DELETED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "shortcut_verdict",
        "shortcut_from_env",
    }
)
_V12_0_0_PV03_DELETED_NAMES: frozenset[str] = frozenset(
    {
        "ShortcutVerdict",
        "SHORTCUT_FLAG_NAME",
        "SHORTCUT_FLAG_TRUTHY",
        "_VALID_SHORTCUT_VERDICTS",
    }
)

# Negative substrings — the literal env-flag name MUST NOT appear in the
# canonical inventory after the v12.0.0 PV-03 retirement. The retirement
# note in env-flags.md DOES NOT contain the literal name (it paraphrases
# via "the simple-task auto-shortcut env flag" + the source-side symbol
# names) so the literal-string negative pin remains clean.
_V12_0_0_PV03_ENV_FLAGS_NEGATIVE_SUBSTRINGS: tuple[str, ...] = ("DEVOLAFLOW_SIMPLE_SHORTCUT",)

# Symbols that MUST remain in change_activation.py — these are the
# preserved-API surface that PV-03 explicitly does NOT touch (only the
# v9.3.0 PV-06 shortcut helpers retire). A regression that accidentally
# removes any of these names is a release blocker; pinning them keeps
# the audit honest about what stays vs what goes.
_V12_0_0_PV03_PRESERVED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "classify_complexity",
        "activation_verdict",
        "from_env",
        "cascade_requirement",
    }
)
_V12_0_0_PV03_PRESERVED_NAMES: frozenset[str] = frozenset(
    {
        "Complexity",
        "ActivationVerdict",
        "CascadeRequirement",
        "ENV_FLAG_NAME",
        "ENV_FLAG_TRUTHY",
    }
)


def test_v12_0_0_pv03_d2_shortcut_simple_retirement(project_root: Path) -> None:
    """W-18 v12.0.0 PV-03 D-2: SHORTCUT_SIMPLE retirement source-side pins.

    Discharges the W-18 precondition for the BREAKING D-2 retirement.
    Per the v12.0.0 cycle plan §8.4 the version bump + CHANGELOG
    rollup are deferred to PV-07; this stanza only pins the source-side
    surfaces that PV-03 owns. PV-07's W-18 stanza will extend this with
    the ``## [12.0.0]`` CHANGELOG positive-substring assertion (the
    retirement migration table + env-flag count 8 → 7 line).

    Surfaces pinned (v12.0.0 PV-03 D-2 retirement scope; second of 4
    v12.0.0 graduation commitments — sister PVs PV-02 D-1 STRICT
    promotion, PV-04 NEW subagent NEST, PV-05 D-5 CONDITIONAL):

    * ``src/devolaflow/skills/change_activation.py`` does NOT define the
      retired ``shortcut_verdict`` / ``shortcut_from_env`` functions
      anywhere in the AST (top-level ``FunctionDef`` walk).

    * ``src/devolaflow/skills/change_activation.py`` does NOT define
      the retired ``ShortcutVerdict`` Literal alias / the
      ``SHORTCUT_FLAG_NAME`` + ``SHORTCUT_FLAG_TRUTHY`` constants /
      the ``_VALID_SHORTCUT_VERDICTS`` private cache (top-level
      ``Assign`` / ``AnnAssign`` walk).

    * ``src/devolaflow/skills/change_activation.py`` PRESERVES the
      v11.x public API surface: ``classify_complexity`` /
      ``activation_verdict`` / ``from_env`` / ``cascade_requirement``
      functions plus ``Complexity`` / ``ActivationVerdict`` /
      ``CascadeRequirement`` / ``ENV_FLAG_NAME`` / ``ENV_FLAG_TRUTHY``
      constants. PV-03 retirement is surgical — only the v9.3.0 PV-06
      shortcut surface goes; the activation + cascade contracts stay
      byte-stable.

    * ``workflow-system/agent/references/env-flags.md`` does NOT
      contain the literal ``DEVOLAFLOW_SIMPLE_SHORTCUT`` env-flag name
      anywhere (negative substring pin; the retirement note paraphrases
      via "the simple-task auto-shortcut env flag" so the literal
      string is fully retired from the canonical inventory). Env-flag
      count goes 8 → 7 per W-20 reuse-first preservation (no new flag
      introduced; one retired).

    * ``tests/test_simple_shortcut.py`` is DELETED (negative file pin).
      The 9-test verdict-matrix coverage is no longer needed because
      the underlying surface no longer exists.

    Coupled invariants verified GREEN at PV-03 close (no source edits
    to schemas / .rules / SKILL / CHANGELOG per cycle plan §8.4):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; PV-04 owns the schema NEST that
      adds the 33rd baseline).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * v11.1.1 D-1 CHANGELOG lint: PASS (PV-03 makes ZERO CHANGELOG
      edits per cycle plan §8.4 PV-07-owns-rollup).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11 proposed;
      this is a Workflow / Convention edit, not a Soul invariant).
    * W-20 reuse-first preserved — env-flag count moves 8 → 7 (one
      retired, zero introduced; orthogonality test is moot for a pure
      retirement).
    * A-7 cascade-depth invariant preserved — the cascade contract
      lives at ``cascade_requirement`` which is the v11.1.0 PV-02
      surface and is INTACT at PV-03 close.

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §4 (D-2 spec)
    + §8.4 (PV-07-owns-bump separation rationale) +
    ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-2 (telegraph
    rationale; env-flag count 8 → 7).
    """
    # ----- 1. change_activation.py — deleted-functions AST negative pin -----
    src_path = project_root / _V12_0_0_PV03_CHANGE_ACTIVATION_FILE
    assert src_path.is_file(), (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        "missing — release-blocker. The retirement deletes 5 surfaces FROM "
        "this file but the file itself MUST remain (it owns the preserved "
        "activation + cascade API)."
    )
    src_module = ast.parse(src_path.read_text(encoding="utf-8"))

    defined_function_names = {
        node.name
        for node in src_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    leaked_functions = sorted(_V12_0_0_PV03_DELETED_FUNCTIONS & defined_function_names)
    assert not leaked_functions, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"still defines retired functions {leaked_functions!r}. The v12.0.0 "
        "PV-03 D-2 retirement deletes the v9.3.0 PV-06 shortcut surface "
        "ENTIRELY — re-introducing any of these symbols breaks the "
        "BREAKING-graduation contract documented in the v11.1.0 "
        "retrospective §3 D-2 telegraph and the v12.0.0 CHANGELOG "
        "migration table."
    )

    # ----- 2. change_activation.py — deleted-constants AST negative pin -----
    defined_assign_names: set[str] = set()
    for node in src_module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_assign_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_assign_names.add(node.target.id)
    leaked_names = sorted(_V12_0_0_PV03_DELETED_NAMES & defined_assign_names)
    assert not leaked_names, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"still defines retired top-level names {leaked_names!r}. Per the "
        "PV-03 D-2 retirement these are companion surfaces to the deleted "
        "shortcut helpers and MUST be removed alongside the functions."
    )

    # ----- 3. change_activation.py — preserved API positive pin -----
    missing_functions = sorted(_V12_0_0_PV03_PRESERVED_FUNCTIONS - defined_function_names)
    assert not missing_functions, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"removed preserved-API functions {missing_functions!r}. PV-03 D-2 "
        "is a SURGICAL retirement of the v9.3.0 PV-06 shortcut surface "
        "ONLY — the v11.x activation + cascade contracts MUST stay intact."
    )
    missing_names = sorted(_V12_0_0_PV03_PRESERVED_NAMES - defined_assign_names)
    assert not missing_names, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"removed preserved-API top-level names {missing_names!r}. PV-03 D-2 "
        "is a SURGICAL retirement — the activation env-flag constants and "
        "Literal type aliases MUST stay intact."
    )

    # ----- 4. env-flags.md — DEVOLAFLOW_SIMPLE_SHORTCUT literal negative pin -----
    env_flags_path = project_root / _V12_0_0_PV03_ENV_FLAGS_FILE
    assert env_flags_path.is_file(), (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_ENV_FLAGS_FILE} "
        "missing — release-blocker. The retirement edits this file's §2.12 "
        "subsection but the file itself MUST remain (it owns the canonical "
        "env-flag inventory across cycles)."
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for sub in _V12_0_0_PV03_ENV_FLAGS_NEGATIVE_SUBSTRINGS:
        assert sub not in env_flags_text, (
            f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_ENV_FLAGS_FILE} "
            f"still contains the retired env-flag literal {sub!r}. Per the "
            "PV-03 D-2 retirement the env-flag inventory MUST drop the "
            "v9.3.0 PV-06 entry entirely; the retirement note paraphrases "
            "via 'the simple-task auto-shortcut env flag' so the literal "
            "name is fully retired."
        )

    # ----- 5. test_simple_shortcut.py — file-deletion negative pin -----
    deleted_test_path = project_root / _V12_0_0_PV03_DELETED_TEST_FILE
    assert not deleted_test_path.exists(), (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_DELETED_TEST_FILE} "
        "still exists. Per the PV-03 D-2 retirement this 9-test file pinned "
        "the v9.3.0 PV-06 shortcut verdict matrix — with the surface gone, "
        "the tests have no remaining contract to enforce and MUST be "
        "deleted."
    )


# ---------------------------------------------------------------------------
# v12.0.0 PV-04 NEW — Subagent-pattern NEST schema lint
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.0.0
# CHANGELOG entry (which PV-07 owns). This stanza closes that precondition
# at the source of the NEW NEST landing: schemas/lean-dispatch.yaml +
# src/devolaflow/feedback.py (helper wiring) + the v12.0.0 baseline
# fixture + the new TestCascadePatternConsistency test class. The
# CHANGELOG positive-substring pin is intentionally OMITTED here —
# PV-07 owns the rollup CHANGELOG, and per the v12.0.0 cycle plan §8.4
# the version bump + CHANGELOG entry are deferred to the cycle-rollup
# commit. PV-04 only ships the source-side / fixture-side / test-side
# pins. Source: ``.local/research/v12.0.0_gap_analysis.md`` §5 (NEST
# schema spec) + §8.4 (PV-07 owns the bump) +
# ``docs/cycle-archive/v11.4.0/other/v11.4.0_subagent_pattern_analysis.md``
# §7.1 (NEST verdict pre-staged).
_V12_0_0_PV04_SCHEMA_FILE: Path = Path("schemas/lean-dispatch.yaml")
_V12_0_0_PV04_FEEDBACK_FILE: Path = Path("src/devolaflow/feedback.py")
_V12_0_0_PV04_BASELINE_FILE: Path = Path(
    "benchmarks/devolaflow_context/baselines/layout_invariant_v12.0.0.yaml"
)
_V12_0_0_PV04_CASCADE_TEST_FILE: Path = Path("tests/test_cascade_enforcement.py")
_V12_0_0_PV04_MULTI_BASELINE_TEST_FILE: Path = Path("tests/test_layout_invariant_multi_baseline.py")


def test_v12_0_0_pv04_subagent_nest_schema(project_root: Path) -> None:
    """W-18 v12.0.0 PV-04 NEW: Subagent-pattern NEST schema source-side pins.

    Discharges the W-18 precondition for the NEW v12.0.0 PV-04 NEST
    landing. Per the v12.0.0 cycle plan §8.4 the version bump +
    CHANGELOG rollup are deferred to PV-07; this stanza only pins the
    source-side surfaces that PV-04 owns. PV-07's W-18 stanza will
    extend this with the ``## [12.0.0]`` CHANGELOG positive-substring
    assertion.

    Surfaces pinned (v12.0.0 PV-04 NEW NEST scope; third of 4 v12.0.0
    graduation commitments — sister PVs PV-02 D-1 STRICT promotion,
    PV-03 D-2 SHORTCUT_SIMPLE retirement, PV-05 D-5 CONDITIONAL):

    * ``schemas/lean-dispatch.yaml`` contains the literal substring
      ``subagent_pattern`` (positive substring pin) — the new NEST
      sub-field is declared under the existing ``gate`` block per
      A-2.3 NEST decision rule. canonical_order length stays at 17,
      schema version stays at 6 (no top-level dispatch key added).

    * ``src/devolaflow/feedback.py`` contains a CALL to
      ``select_pattern`` (AST FunctionCall pin) — the dispatcher-side
      wiring that populates ``gate.subagent_pattern`` from the four
      v12.0.0 PV-04 input axes (model_tier / task_count /
      parallel_independence / persistent_state_needed) per the helper
      extension to ``populate_cascade_gate_fields``.

    * ``benchmarks/devolaflow_context/baselines/layout_invariant_v12.0.0.yaml``
      EXISTS on disk (file pin) — the 15th multi-baseline byte-test
      pin per A-2.4 (32/32 → 33/33 GREEN).

    * ``tests/test_cascade_enforcement.py`` contains the
      ``TestCascadePatternConsistency`` class (AST ClassDef pin) —
      the v12.0.0 PV-04 cross-couple consistency contract pins (7
      NEW tests pinning cascade × subagent-pattern orthogonality).

    * ``tests/test_layout_invariant_multi_baseline.py`` references the
      literal substring ``v12.0.0`` (positive substring pin) — the
      new multi-baseline pin is wired into the test registry. The
      multi-baseline byte-test count moves 32 → 33; the new entry is
      ``test_v12_0_0_baseline_byte_identical``.

    Coupled invariants verified GREEN at PV-04 close (no source edits
    to .rules / SKILL / CHANGELOG / version per cycle plan §8.4):

    * A-2.4 multi-baseline byte test: 32/32 → 33/33 GREEN (the new
      v12.0.0 baseline pins the NEST shape; absence is canonical so
      all 32 prior baselines pass byte-identically).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged (the NEST
      sub-field is OPTIONAL; legacy v11.x dispatches without
      ``gate.subagent_pattern`` flow through byte-identically).
    * v11.1.1 D-1 CHANGELOG lint: PASS (PV-04 makes ZERO CHANGELOG
      edits per cycle plan §8.4 PV-07-owns-rollup).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11 proposed;
      this is a Convention / Architecture edit, not a Soul invariant).
    * W-20 reuse-first preserved — no NEW ``DEVOLAFLOW_*`` env flag
      introduced (the new sub-field is purely a dispatch payload field;
      activation is via the four kw-only axes, not an env flag).
    * A-7 cascade-depth invariant preserved — the cascade contract
      lives at ``gate.cascade_required`` + ``gate.cascade_min_layers``
      which PV-04 leaves byte-stable; the new ``gate.subagent_pattern``
      is orthogonal to cascade depth per W-24.
    * Frozen prefix (positions 1-12) preserved per A-2.1; the new
      sub-field NESTs UNDER position 12 (``gate``), preserving the
      cache-prefix length every L0/L1/L2/L3 dispatcher keys on.

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §5 (NEST schema
    spec) + §8.4 (PV-07 owns the bump) +
    ``docs/cycle-archive/v11.4.0/other/v11.4.0_subagent_pattern_analysis.md``
    §7.1 (NEST verdict pre-staged + canonical_order=17 invariant).
    """
    # ----- 1. schemas/lean-dispatch.yaml — subagent_pattern positive pin -----
    schema_path = project_root / _V12_0_0_PV04_SCHEMA_FILE
    assert schema_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_SCHEMA_FILE} missing — "
        "release-blocker. The NEST schema lands AT this file."
    )
    schema_text = schema_path.read_text(encoding="utf-8")
    assert "subagent_pattern" in schema_text, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_SCHEMA_FILE} missing "
        "the literal substring 'subagent_pattern'. The v12.0.0 PV-04 NEST "
        "extension MUST declare the new sub-field under the ``gate`` block "
        "per A-2.3 NEST decision rule. See "
        ".local/research/v12.0.0_gap_analysis.md §5 for the canonical NEST "
        "verdict + schema sub-field shape."
    )

    # Cross-anchor: the schema's canonical_order length stays at 17 +
    # version stays at 6 (NEST, not APPEND). Drift here would be a
    # release-blocker per A-2.4.
    schema_data = yaml.safe_load(schema_text)
    canonical_order = schema_data["layout_invariant"]["canonical_order"]
    schema_version = schema_data["layout_invariant"]["version"]
    assert len(canonical_order) == 17, (
        f"W-18 v12.0.0 PV-04 violation: canonical_order length is "
        f"{len(canonical_order)}; expected 17 per A-2.4 + NEST decision "
        "(no top-level key added at v12.0.0 PV-04)."
    )
    assert schema_version == 6, (
        f"W-18 v12.0.0 PV-04 violation: schema version is {schema_version}; "
        "expected 6 per A-2.3 NEST contract (sub-field addition, no version "
        "bump)."
    )

    # ----- 2. src/devolaflow/feedback.py — select_pattern call AST pin -----
    feedback_path = project_root / _V12_0_0_PV04_FEEDBACK_FILE
    assert feedback_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_FEEDBACK_FILE} missing — "
        "release-blocker. The dispatcher-side helper wiring lands AT this file."
    )
    feedback_module = ast.parse(feedback_path.read_text(encoding="utf-8"))

    # AST walk: find the ``select_pattern(...)`` call inside any
    # function body. The call MUST appear in
    # ``populate_cascade_gate_fields`` (the helper extension), but we
    # do not pin the enclosing function name here — only that
    # ``select_pattern`` IS called somewhere in feedback.py.
    select_pattern_calls: list[ast.Call] = []
    for node in ast.walk(feedback_module):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select_pattern"
        ):
            select_pattern_calls.append(node)
    assert select_pattern_calls, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_FEEDBACK_FILE} contains "
        "no AST call to ``select_pattern``. The v12.0.0 PV-04 NEST extension "
        "wires the dispatcher-side helper to invoke "
        "``devolaflow.skills.subagent_pattern.select_pattern`` to derive "
        "``gate.subagent_pattern`` from the four input axes; this lint "
        "verifies the wiring landed."
    )

    # ----- 3. v12.0.0 baseline file — fixture existence pin -----
    baseline_path = project_root / _V12_0_0_PV04_BASELINE_FILE
    assert baseline_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_BASELINE_FILE} missing — "
        "release-blocker. The 15th multi-baseline byte-test pin (A-2.4) MUST "
        "exist as a checked-in fixture; see "
        ".local/research/v12.0.0_gap_analysis.md §5.3 for the regen recipe."
    )

    # ----- 4. tests/test_cascade_enforcement.py — TestCascadePatternConsistency class pin -----
    cascade_test_path = project_root / _V12_0_0_PV04_CASCADE_TEST_FILE
    assert cascade_test_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_CASCADE_TEST_FILE} "
        "missing — release-blocker."
    )
    cascade_test_module = ast.parse(cascade_test_path.read_text(encoding="utf-8"))
    consistency_class = next(
        (
            node
            for node in cascade_test_module.body
            if isinstance(node, ast.ClassDef) and node.name == "TestCascadePatternConsistency"
        ),
        None,
    )
    assert consistency_class is not None, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_CASCADE_TEST_FILE} "
        "missing the ``TestCascadePatternConsistency`` class. The v12.0.0 "
        "PV-04 cross-couple consistency contract (cascade × subagent-pattern "
        "orthogonality) lands as a NEW test class with 5-7 NEW test "
        "methods; see .local/research/v12.0.0_gap_analysis.md §5.5 for "
        "the canonical 7 test names."
    )

    # ----- 5. tests/test_layout_invariant_multi_baseline.py — v12.0.0 substring pin -----
    multi_baseline_test_path = project_root / _V12_0_0_PV04_MULTI_BASELINE_TEST_FILE
    assert multi_baseline_test_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_MULTI_BASELINE_TEST_FILE} "
        "missing — release-blocker."
    )
    multi_baseline_test_text = multi_baseline_test_path.read_text(encoding="utf-8")
    assert "v12.0.0" in multi_baseline_test_text, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_MULTI_BASELINE_TEST_FILE} "
        "missing the literal substring 'v12.0.0'. The new baseline pin (the "
        "33rd multi-baseline byte test) MUST register the v12.0.0 fixture; "
        "see .local/research/v12.0.0_gap_analysis.md §5.3 for the wiring "
        "recipe (PV-04 step 2 — add the v12.0.0 baseline to the "
        "parametrized fixture list)."
    )


# ---------------------------------------------------------------------------
# v12.0.0 PV-05 — cleanup-absorption stanza (compiler.py post-truncation fix)
# ---------------------------------------------------------------------------
# Per the v12.0.0 gap analysis §6 verdict, the originally-telegraphed D-5
# CHANGELOG single-application CI lint is DEFERRED to v13.0.0 SI-1
# evaluation (5/5 audit clean across v11.1.1..v11.4.0 — no recurrence; the
# existing W-18 PV-close stanza + v11.1.1 D-1 in-test lint are sufficient).
# PV-05 instead absorbs the v11.4.0 retrospective §3 deferred bug: the
# `compiler.py::_truncate_to_budget` post-truncation `layers_included`
# accounting bug, which silently masked the v11.4.0 cursor 11979/12000
# saturation pre-bump (the Style Rules layer was dropped by the truncation
# loop but `RuleCompiler.compile` reported all 5 layers in
# `layers_included`). PV-05 ships a 1-function source fix (tuple return
# from `_truncate_to_budget`) + a regression test in
# `tests/test_local_compiler.py`. The CHANGELOG positive-substring pin is
# intentionally OMITTED here — PV-07 owns the rollup CHANGELOG, and per
# the v12.0.0 gap analysis §8.4 the version bump + CHANGELOG entry are
# deferred to the cycle-rollup commit. PV-05 only ships the source-side
# + test-side pins. Source: ``.local/research/v12.0.0_gap_analysis.md``
# §6 (D-5 DEFER verdict + cleanup absorption rationale) +
# ``docs/cycle-archive/v11.4.0/v11.4.0_retrospective.md`` §3 deferred-
# bugs inventory line "compiler.py post-truncation layers_included
# accounting bug" + §4 key learning 3.
_V12_0_0_PV05_COMPILER_FILE: Path = Path("src/devolaflow/local/compiler.py")
_V12_0_0_PV05_COMPILER_TEST_FILE: Path = Path("tests/test_local_compiler.py")
_V12_0_0_PV05_REQUIRED_NEW_TEST: str = "test_compile_layers_included_reflects_post_truncation_state"


def test_v12_0_0_pv05_compiler_layers_included_post_truncation(
    project_root: Path,
) -> None:
    """W-18 v12.0.0 PV-05 NEW: compiler.py post-truncation accounting fix.

    Discharges the W-18 precondition for the v12.0.0 PV-05 cleanup-
    absorption landing. Per the v12.0.0 gap analysis §6 D-5 is DEFERRED
    to v13.0.0 SI-1 (5/5 audit clean = no recurrence; W-18 + v11.1.1
    D-1 lint sufficient). PV-05 absorbs the v11.4.0 retrospective §3
    deferred bug instead: the ``compiler.py::_truncate_to_budget``
    post-truncation ``layers_included`` accounting bug, which silently
    masked the v11.4.0 cursor 11979/12000 saturation pre-bump (the
    Style Rules layer was dropped by the truncation loop but
    ``RuleCompiler.compile`` reported ``layers_included=['soul',
    'architecture', 'conventions', 'workflow', 'style']`` because the
    list reflected pre-truncation state).

    Surfaces pinned (v12.0.0 PV-05 NEW cleanup scope; fourth and final
    of the 4 v12.0.0 graduation commitments — sister PVs PV-02 D-1
    STRICT promotion, PV-03 D-2 SHORTCUT_SIMPLE retirement, PV-04 NEW
    NEST schema; D-5 CHANGELOG CI lint is DEFERRED per gap analysis §6):

    * ``src/devolaflow/local/compiler.py`` — the ``_truncate_to_budget``
      function returns a TUPLE (AST positive pin: at least one
      ``return`` statement inside the function body has an
      ``ast.Tuple`` value node). Pre-fix the function returned a single
      string (the rendered content); the v12.0.0 PV-05 fix changes the
      signature to ``tuple[str, list[RuleLayer]]`` so the dispatcher-
      side caller (``_compile_target``) can use the post-truncation
      retained list to populate ``CompileResult.layers_included``.

    * ``tests/test_local_compiler.py`` contains the regression test
      ``test_compile_layers_included_reflects_post_truncation_state``
      (AST FunctionDef pin) — pins the post-truncation accounting
      contract against a tight-budget scenario that forces the lowest-
      priority layer to be dropped. The test asserts the dropped layer
      is ABSENT from ``layers_included`` (the bug-positive pin) and
      that ``soul`` (always_include=True) survives (the contract pin).

    Coupled invariants verified GREEN at PV-05 close (no source edits
    to .rules / SKILL / CHANGELOG / version per cycle plan):

    * ``test_rule_surfaces_compile_only`` (ADR-007 D5 drift detection):
      PASS — the fix only edits ``_truncate_to_budget`` + the truncation
      branch of ``_compile_target``; the rendered output for the cursor
      + agents_md targets is byte-identical because the current 14000-
      token budget does NOT trigger truncation on either target. The
      compiled .cursor/rules/repo-governance.mdc + AGENTS.md SHA-256
      values stay byte-stable.
    * Happy-path behaviour preserved: when ``tokens <= tc.token_budget``,
      ``layers_included`` continues to reflect the ``selected`` list
      (no truncation runs, so ``retained`` stays None and the report
      falls back to ``selected``).
    * W-21 Soul-set freeze preserved at 10 entries (cleanup edit; not
      a Soul invariant addition).
    * W-20 reuse-first preserved — no NEW ``DEVOLAFLOW_*`` env flag
      introduced (pure code-correctness fix; no behavioural axis).

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §6 (D-5 DEFER
    verdict + cleanup absorption rationale) +
    ``docs/cycle-archive/v11.4.0/v11.4.0_retrospective.md`` §3 deferred
    bug "compiler.py post-truncation layers_included accounting bug"
    + §4 key learning 3.
    """
    # ----- 1. compiler.py — _truncate_to_budget tuple-return AST pin -----
    compiler_path = project_root / _V12_0_0_PV05_COMPILER_FILE
    assert compiler_path.is_file(), (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} "
        "missing — release-blocker. The post-truncation accounting fix "
        "lands AT this file."
    )
    compiler_module = ast.parse(compiler_path.read_text(encoding="utf-8"))

    truncate_func: ast.FunctionDef | None = None
    for node in ast.walk(compiler_module):
        if isinstance(node, ast.FunctionDef) and node.name == "_truncate_to_budget":
            truncate_func = node
            break
    assert truncate_func is not None, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} missing "
        "the ``_truncate_to_budget`` function. The fix MUST preserve the "
        "function name (``_compile_target`` calls it). See v11.4.0 "
        "retrospective §3 deferred bug + §4 key learning 3."
    )

    return_nodes = [n for n in ast.walk(truncate_func) if isinstance(n, ast.Return)]
    assert return_nodes, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} "
        "``_truncate_to_budget`` has no ``return`` statement — the "
        "function must return ``(content, retained_layers)`` per the "
        "v12.0.0 PV-05 contract."
    )
    tuple_returns = [n for n in return_nodes if isinstance(n.value, ast.Tuple)]
    assert tuple_returns, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} "
        "``_truncate_to_budget`` does NOT return a tuple. Pre-fix the "
        "function returned a single string (the rendered content); the "
        "v12.0.0 PV-05 fix changes the signature to return "
        "``(content, retained_layers)`` so callers can report the "
        "post-truncation layer set in ``layers_included``. See "
        ".local/research/v12.0.0_gap_analysis.md §6 + v11.4.0 "
        "retrospective §3 deferred bug + §4 key learning 3 for the "
        "rationale."
    )

    # ----- 2. tests/test_local_compiler.py — regression test AST pin -----
    test_path = project_root / _V12_0_0_PV05_COMPILER_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_TEST_FILE} "
        "missing — release-blocker."
    )
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined_tests: set[str] = {
        node.name
        for node in ast.walk(test_module)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    assert _V12_0_0_PV05_REQUIRED_NEW_TEST in defined_tests, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_TEST_FILE} "
        f"missing the regression test ``{_V12_0_0_PV05_REQUIRED_NEW_TEST}``. "
        "The v12.0.0 PV-05 cleanup absorption MUST add a regression test "
        "that pins the post-truncation accounting contract; see "
        ".local/research/v12.0.0_gap_analysis.md §6 + v11.4.0 "
        "retrospective §3 deferred bug + §4 key learning 3."
    )


def test_v11_1_2_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.2 PATCH: D-2 audit_layer_usage.py regex bold-markdown coverage.

    Discharges the W-18 precondition for the v11.1.2 PATCH CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (v11.1.2 D-2 patch scope; second of 3 staged
    v11.1.x stability patches — sister patches v11.1.1 + v11.1.3):

    * ``tests/test_audit_layer_usage.py`` carries the 4 NEW regex
      coverage tests (AST symbol pin):

      - ``test_dispatch_type_regex_matches_plain_style``
        (negative-control — plain `Dispatch type:` matches; W-20
        backward-compat preserved).
      - ``test_dispatch_type_regex_matches_bold_markdown_style``
        (the D-2 fix — `**Dispatch type:** Wave` matches).
      - ``test_dispatch_type_regex_matches_bold_value_only``
        (defensive — bold value `Dispatch type: **Wave**` matches).
      - ``test_dispatch_type_regex_matches_full_bold``
        (defensive — full-bold `**Dispatch type:** **Wave**` matches;
        pins the dual ``\\*{0,2}\\s*\\*{0,2}`` slot design).

    * ``scripts/audit_layer_usage.py`` carries the broadened regex —
      the source MUST contain ``\\*{0,2}`` (the canonical broadening
      marker) AND the citation back to ``docs/cycle-archive/v11.1.0/
      retrospective.md``.

    * ``CHANGELOG.md`` carries the ``## [11.1.2] - 2026-05-08``
      PATCH entry mentioning ``PATCH`` + ``audit_layer_usage.py`` +
      ``bold-markdown`` (the v11.1.0 retrospective §3 D-4 deferral
      citation; the dispatcher's D-2 in-series label).

    * ``CHANGELOG.md`` ``## [11.1.2]`` section header appears
      EXACTLY once (the v11.1.1 D-1 single-application lint
      pre-condition; this stanza independently asserts the
      line-anchored count via splitlines + line.startswith).

    Coupled invariants verified GREEN at PATCH close (no source
    edits to gate / schema / SKILL):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application — proving v11.1.1 D-1 catches
      its own next test)
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags
    * Existing 15 tests in ``tests/test_audit_layer_usage.py``
      preserved byte-stable (W-20 backward-compat — the regex
      BROADENING admits new inputs without changing the v10.5.0
      plain-text contract)

    Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-4
    (cycle-deferral inventory; the dispatcher's D-2 in-series label).
    """
    test_path = project_root / _V11_1_2_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v11.1.2 violation: test file {_V11_1_2_TEST_FILE} missing. "
        "The 4 NEW regex coverage tests MUST land in the same commit as "
        "the CHANGELOG entry per W-18 sequencing."
    )

    # AST symbol pin — robust against function-body refactor; only fails
    # on rename / removal of the four contracted public symbols.
    module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = [s for s in _V11_1_2_REQUIRED_NEW_TESTS if s not in defined]
    assert not missing, (
        f"W-18 v11.1.2 violation: {_V11_1_2_TEST_FILE} missing required "
        f"NEW test functions {missing!r}. Required set: "
        f"{list(_V11_1_2_REQUIRED_NEW_TESTS)!r}; defined: "
        f"{sorted(defined)!r}."
    )

    # Audit script source MUST evidence the regex broadening — the
    # `\*{0,2}` quantifier is the canonical marker; the citation
    # anchors the deferral trail.
    script_path = project_root / _V11_1_2_SCRIPT_FILE
    assert script_path.is_file(), f"W-18 v11.1.2 violation: script {_V11_1_2_SCRIPT_FILE} missing."
    script_text = script_path.read_text(encoding="utf-8")
    for sub in _V11_1_2_SCRIPT_POSITIVE_SUBSTRINGS:
        assert sub in script_text, (
            f"W-18 v11.1.2 violation: {_V11_1_2_SCRIPT_FILE} missing "
            f"positive substring {sub!r} — the v11.1.2 D-2 regex "
            "broadening MUST cite both the `\\*{0,2}` quantifier (the "
            "canonical marker) AND the cycle-archive retrospective "
            "citation in the source comment."
        )

    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked).
    changelog_text = (project_root / _V11_1_2_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_2_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.2 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.1.2 PATCH scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface
    # any drift before the cross-test runs).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.2]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.2 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.2]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.1.2 D-2 patch INHERITS the v11.1.1 "
        "discipline cleanly — do not trip the predecessor's lint while "
        "writing the successor's fix)."
    )


# ---------------------------------------------------------------------------
# v12.1.0 D-1 + D-2 — subagent output restrictions + hang prevention
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.1.0
# CHANGELOG entry that mentions the two BLOCKER fixes (D-1 Task Quality Score
# scope is L0-only; D-2 Subagent Hang Prevention guidance). This stanza
# closes the precondition by pinning the two SKILL.md surfaces:
#
# * SKILL.md contains literal "L0 ONLY" — D-1 closure marker.
# * SKILL.md contains literal "Hang Prevention" — D-2 closure marker.
#
# A companion test file ``tests/test_subagent_output_restrictions.py`` carries
# the richer positive-substring assertions; this stanza is the cross-pin from
# the no-ghost-features audit lens. Both surfaces must be GREEN before the
# CHANGELOG ``## [12.1.0]`` entry is authored.
#
# Source: ``.local/research/v12.1.0_gap_analysis.md`` §2 D-1 + §2 D-2 +
# §5 W-18 row + §8 acceptance criteria 1+2.
# ---------------------------------------------------------------------------
_V12_1_0_SKILL_FILE: Path = Path("workflow-system/agent/SKILL.md")
_V12_1_0_TEST_FILE: Path = Path("tests/test_subagent_output_restrictions.py")
_V12_1_0_CHANGELOG: Path = Path("CHANGELOG.md")

# D-1 closure marker — literal substring required in SKILL.md to prove the
# §"Task Quality Score (L0 ONLY)" scoping marker landed.
_V12_1_0_D1_LITERAL: str = "L0 ONLY"

# D-1 explicit prohibition — paired with D1 marker; literal substring proves
# the Subagents-MUST-NOT-score line landed in the SKILL.md body.
_V12_1_0_D1_PROHIBITION: str = "Subagents MUST NOT"

# D-2 closure marker — literal substring required in SKILL.md to prove the
# new §"Subagent Hang Prevention" subsection landed.
_V12_1_0_D2_LITERAL: str = "Hang Prevention"

# Companion test file — the 5 canonical NEW test functions that
# tests/test_subagent_output_restrictions.py MUST define. AST FunctionDef
# pin — robust against function-body refactor; fails only on rename /
# removal of the contracted public symbols.
_V12_1_0_REQUIRED_NEW_TESTS: frozenset[str] = frozenset(
    {
        "test_skill_md_task_quality_score_marked_l0_only",
        "test_skill_md_reporting_completion_excludes_quality_score",
        "test_skill_md_hang_prevention_section_present",
        "test_skill_md_under_500_lines",
        "test_skill_md_l3_forbidden_patterns_complete",
    }
)


def test_v12_1_0_subagent_output_restrictions(project_root: Path) -> None:
    """W-18 v12.1.0 D-1 + D-2: subagent output restrictions + hang prevention.

    Discharges the W-18 precondition for the v12.1.0 MINOR CHANGELOG
    entry that mentions the two BLOCKER fixes. Per W-18 sequencing this
    stanza MUST land BEFORE the ``## [12.1.0]`` CHANGELOG entry — the
    L3 dispatched author authors the W-18 stanza first, runs the
    ghost-audit, and only then authors the CHANGELOG entry. This is
    codified in the test docstring rather than at runtime because the
    sequencing is a workflow contract enforced by L0 review at commit
    time, not by the lint itself.

    Surfaces pinned (v12.1.0 single-PV scope; both D-1 + D-2 close
    in this single PV per gap analysis §3):

    * **D-1 closure** — SKILL.md contains the literal ``L0 ONLY``
      string, proving the §"Task Quality Score (L0 ONLY)" scoping
      marker landed. SKILL.md contains the literal ``Subagents MUST
      NOT`` string, proving the explicit prohibition line landed.
      Both literals MUST be present so a substring grep against the
      section catches the marker even if the section is included in
      isolation by a context-profile selection.

    * **D-2 closure** — SKILL.md contains the literal ``Hang
      Prevention`` string, proving the new subsection heading landed.
      The richer 5-forbidden-patterns assertion lives in
      ``tests/test_subagent_output_restrictions.py::
      test_skill_md_l3_forbidden_patterns_complete``; this stanza
      pins only the section presence.

    * **Companion test file** — ``tests/test_subagent_output_
      restrictions.py`` is present and defines the 5 canonical NEW
      test functions enumerated in the v12.1.0 dispatch
      acceptance criteria AC-5. AST ``FunctionDef`` pin — robust
      against body refactor; fails only on rename / removal.

    Coupled invariants verified GREEN at v12.1.0 close (no source
    edits to gate / schema / .rules per gap analysis §2 — additive
    documentation only):

    * A-2.4 multi-baseline byte test: 33/33 PASS unchanged
      (canonical_order stays at 17; no schema NEST in this PV).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * CP-4 gate suite: 101/101 PASS unchanged (no gate edits).
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application — the ``## [12.1.0]`` line-anchored
      count must equal 1 to clear the predecessor's discipline).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11 proposed;
      D-1 + D-2 fix at SKILL.md not at the rule corpus per gap
      analysis §5).
    * W-20 reuse-first preserved at 7 env flags (NO new
      ``DEVOLAFLOW_*`` env flag introduced — pure normative
      documentation; no behavioural axis).
    * C-4 default-tier ceiling: SKILL.md remains < 500 lines per
      ``test_skill_md_under_500_lines`` (defence-in-depth).

    Source: ``.local/research/v12.1.0_gap_analysis.md`` §2 D-1 + §2
    D-2 + §5 W-18 row + §8 acceptance criteria 1+2 +
    ``.local/feedbacks/feedback_for_v12.0.0.md`` (the 2 user feedback
    lines that motivated this MINOR cycle).
    """
    skill_path = project_root / _V12_1_0_SKILL_FILE
    assert skill_path.is_file(), (
        f"W-18 v12.1.0 violation: {_V12_1_0_SKILL_FILE} missing — release "
        "blocker. The D-1 + D-2 fixes land AT this file."
    )
    skill_text = skill_path.read_text(encoding="utf-8")

    assert _V12_1_0_D1_LITERAL in skill_text, (
        f"W-18 v12.1.0 D-1 violation: {_V12_1_0_SKILL_FILE} missing literal "
        f"{_V12_1_0_D1_LITERAL!r}. The §'Task Quality Score (L0 ONLY)' "
        "scoping marker MUST land before the CHANGELOG entry per W-18 "
        "sequencing. See gap analysis §2 D-1 fix #1."
    )
    assert _V12_1_0_D1_PROHIBITION in skill_text, (
        f"W-18 v12.1.0 D-1 violation: {_V12_1_0_SKILL_FILE} missing literal "
        f"{_V12_1_0_D1_PROHIBITION!r}. The explicit prohibition line "
        "('Subagents MUST NOT score') MUST land alongside the L0-only "
        "marker so the section text alone (without surrounding chrome) "
        "carries the prohibition. See gap analysis §2 D-1 fix #1."
    )
    assert _V12_1_0_D2_LITERAL in skill_text, (
        f"W-18 v12.1.0 D-2 violation: {_V12_1_0_SKILL_FILE} missing literal "
        f"{_V12_1_0_D2_LITERAL!r}. The new §'Subagent Hang Prevention' "
        "subsection MUST land before the CHANGELOG entry per W-18 "
        "sequencing. See gap analysis §2 D-2 fix proposed."
    )

    test_path = project_root / _V12_1_0_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v12.1.0 violation: {_V12_1_0_TEST_FILE} missing — release "
        "blocker. The 5 NEW test functions enumerated in dispatch AC-5 "
        "MUST land in the same commit as the SKILL.md edits per W-18 "
        "sequencing."
    )

    test_module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = sorted(_V12_1_0_REQUIRED_NEW_TESTS - defined)
    assert not missing, (
        f"W-18 v12.1.0 violation: {_V12_1_0_TEST_FILE} missing required "
        f"NEW test functions {missing!r}. Required canonical 5-name set "
        f"per dispatch AC-5: {sorted(_V12_1_0_REQUIRED_NEW_TESTS)!r}; "
        f"defined: {sorted(defined)!r}."
    )


# ---------------------------------------------------------------------------
# v12.2.0 W-18 ghost-audit refresh — PV-02 gitignore selective whitelist.
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.2.0
# CHANGELOG entry that mentions the gitignore selective whitelist fix.
# This stanza pins the v12.2.0 PV-02 surface:
#
# * src/devolaflow/local/workspace.py contains the 3 required positive
#   whitelist rules (.local/* + !.local/memory/specs/ + !.local/research/)
#   in `_LOCAL_WHITELIST_BLOCK_LINES` and `_LOCAL_WHITELIST_REQUIRED_RULES`.
# * The repo-root .gitignore self-fix carries the same 3 rules — so the
#   DevolaFlow source repo demonstrates the same pattern it teaches.
# * `_has_correct_local_whitelist` is importable from workspace.
# * `_V92_LOCAL_BROAD_RULE = ".local/"` is present (the rule v12.2.0
#   supersedes).
#
# Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-1 +
# ``.local/feedbacks/feedback_for_v12.1.0.md`` (the user feedback line
# that motivated this PV).
# ---------------------------------------------------------------------------
_V12_2_0_WORKSPACE_FILE: Path = Path("src/devolaflow/local/workspace.py")
_V12_2_0_REPO_GITIGNORE: Path = Path(".gitignore")
_V12_2_0_TEST_FILE: Path = Path("tests/test_scaffold_gitignore_audit.py")
_V12_2_0_WHITELIST_REQUIRED_RULES: frozenset[str] = frozenset(
    {
        ".local/*",
        "!.local/memory/specs/",
        "!.local/research/",
    }
)
_V12_2_0_SUPERSEDED_RULE: str = ".local/"
_V12_2_0_REQUIRED_GITIGNORE_FN_NAMES: frozenset[str] = frozenset(
    {
        "test_no_gitignore_writes_v12_2_0_whitelist_block",
        "test_gitignore_without_local_rule_appends_v12_2_0_block",
        "test_v9_2_3_broad_local_rule_is_repaired_to_whitelist",
        "test_legacy_local_whitelist_block_is_graduated_to_v12_2_0",
        "test_v12_2_0_whitelist_is_idempotent_no_op_second_run",
        "test_narrow_pre_existing_rule_triggers_warning_alongside_whitelist",
    }
)


def test_v12_2_0_gitignore_whitelist_repair(project_root: Path) -> None:
    """W-18 v12.2.0 D-1: gitignore selective whitelist + repair surface.

    Discharges the W-18 precondition for the v12.2.0 MINOR CHANGELOG
    entry mentioning the gitignore fix. Pins:

    * src/devolaflow/local/workspace.py declares the 3 required positive
      whitelist rules in both `_LOCAL_WHITELIST_BLOCK_LINES` AND
      `_LOCAL_WHITELIST_REQUIRED_RULES`. Substring presence — robust
      against block-comment refactor; fails only on rule rename / removal.
    * src/devolaflow/local/workspace.py preserves `_V92_LOCAL_BROAD_RULE`
      so the repair path knows which v9.2.3 rule to graduate.
    * src/devolaflow/local/workspace.py exports `_has_correct_local_whitelist`
      (the detection helper used by `_audit_gitignore_coverage` and
      `ensure_local_gitignore`).
    * The repo-root `.gitignore` carries the 3 required positive rules
      (DevolaFlow source repo demonstrates the pattern it teaches).
    * The companion test file defines the 6 canonical PV-02 test functions.

    Coupled invariants verified GREEN at v12.2.0 PV-02 close:
    * Existing test suite (101 init + scaffold tests) PASS unchanged
      against the new whitelist semantics.
    * W-18 v9.2.3 ghost-audit stanza still GREEN (the v9.2.3 public
      symbols `_audit_gitignore_coverage` + `last_gitignore_audit`
      remain importable; `VALID_MODES` unchanged).
    * W-21 Soul-set freeze preserved at 10 entries (gitignore fix at
      runtime not at rule corpus).
    * W-20 reuse-first preserved at 7 env flags (no new
      `DEVOLAFLOW_*` flag — fix is operator-facing, not env-gated).

    Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-1 +
    ``.local/feedbacks/feedback_for_v12.1.0.md``.
    """
    workspace_path = project_root / _V12_2_0_WORKSPACE_FILE
    assert workspace_path.is_file(), (
        f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing — release blocker."
    )
    workspace_text = workspace_path.read_text(encoding="utf-8")

    for required_rule in sorted(_V12_2_0_WHITELIST_REQUIRED_RULES):
        assert required_rule in workspace_text, (
            f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing required "
            f"whitelist rule literal {required_rule!r}. The v12.2.0 whitelist "
            f"block MUST declare all 3 positive rules so consumer repos get "
            f"the team-collab subdirs (.local/memory/specs/ + .local/research/) "
            f"tracked by default. See gap analysis §2 D-1."
        )

    assert "_V92_LOCAL_BROAD_RULE" in workspace_text, (
        f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing "
        f"`_V92_LOCAL_BROAD_RULE` constant. The repair path MUST preserve "
        f"the v9.2.3 broad rule literal so it can detect and graduate "
        f"existing repos to the v12.2.0 whitelist."
    )

    assert "_has_correct_local_whitelist" in workspace_text, (
        f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing "
        f"`_has_correct_local_whitelist` helper. The detection helper is the "
        f"keystone for both `_audit_gitignore_coverage` suppression and "
        f"`ensure_local_gitignore` idempotency."
    )

    from devolaflow.local.workspace import (
        _LOCAL_WHITELIST_BLOCK_LINES,
        _LOCAL_WHITELIST_REQUIRED_RULES,
        _has_correct_local_whitelist,
    )

    assert callable(_has_correct_local_whitelist), (
        "W-18 v12.2.0 violation: _has_correct_local_whitelist must be importable + callable"
    )
    assert _LOCAL_WHITELIST_REQUIRED_RULES == _V12_2_0_WHITELIST_REQUIRED_RULES, (
        f"W-18 v12.2.0 violation: workspace._LOCAL_WHITELIST_REQUIRED_RULES = "
        f"{_LOCAL_WHITELIST_REQUIRED_RULES!r}; expected {_V12_2_0_WHITELIST_REQUIRED_RULES!r}. "
        f"The 3-element membership is the contract surface the test pins."
    )
    for required in _V12_2_0_WHITELIST_REQUIRED_RULES:
        assert required in _LOCAL_WHITELIST_BLOCK_LINES, (
            f"W-18 v12.2.0 violation: _LOCAL_WHITELIST_BLOCK_LINES missing "
            f"required rule {required!r}; the block + the required-rules set "
            f"MUST agree on the 3 positive rules."
        )

    repo_gitignore = project_root / _V12_2_0_REPO_GITIGNORE
    assert repo_gitignore.is_file(), (
        f"W-18 v12.2.0 violation: {_V12_2_0_REPO_GITIGNORE} missing — release blocker."
    )
    repo_gitignore_lines = repo_gitignore.read_text(encoding="utf-8").splitlines()
    for required_rule in sorted(_V12_2_0_WHITELIST_REQUIRED_RULES):
        assert required_rule in repo_gitignore_lines, (
            f"W-18 v12.2.0 violation: DevolaFlow source repo {_V12_2_0_REPO_GITIGNORE} "
            f"missing required v12.2.0 whitelist rule {required_rule!r}. The source "
            f"repo MUST demonstrate the same pattern it teaches consumer repos."
        )
    assert _V12_2_0_SUPERSEDED_RULE not in repo_gitignore_lines, (
        f"W-18 v12.2.0 violation: DevolaFlow source repo {_V12_2_0_REPO_GITIGNORE} "
        f"still carries the v9.2.3 broad `{_V12_2_0_SUPERSEDED_RULE}` rule that "
        f"v12.2.0 PV-02 supersedes. The source repo MUST be graduated to the "
        f"v12.2.0 whitelist alongside the helper-code change."
    )

    test_path = project_root / _V12_2_0_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v12.2.0 violation: {_V12_2_0_TEST_FILE} missing — release blocker."
    )
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = sorted(_V12_2_0_REQUIRED_GITIGNORE_FN_NAMES - defined)
    assert not missing, (
        f"W-18 v12.2.0 violation: {_V12_2_0_TEST_FILE} missing required NEW test "
        f"functions {missing!r}. Required canonical 6-name set per PV-02 dispatch: "
        f"{sorted(_V12_2_0_REQUIRED_GITIGNORE_FN_NAMES)!r}; defined: {sorted(defined)!r}."
    )


# ---------------------------------------------------------------------------
# v12.2.0 PV-03 W-18 ghost-audit refresh — Mnimiy 3-rule behavioral extension.
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.2.0
# CHANGELOG entry mentioning the BG-005..BG-007 behavioral primitive
# additions. This stanza pins the v12.2.0 PV-03 surface:
#
# * workflow-system/agent/references/behavioral-guidelines.md documents
#   all 3 NEW rule sections (BG-005, BG-006, BG-007) with their literal
#   IDs and dispatch field names (no_llm_for_deterministic,
#   surface_conflicts, convention_first).
# * src/devolaflow/task_adaptive_selector.py::_compose_behavioral_block
#   renders the 3 NEW rule bullets when active (substring presence pin).
# * schemas/lean-dispatch.yaml#lean_format_spec.behavioral_guidelines.fields
#   declares the 3 NEW sub-fields with severity classification.
# * workflow-system/agent/context_profiles.yaml#meta.behavioral_guidelines_defaults
#   carries per-tier defaults for the 3 NEW keys.
# * tests/test_behavioral_guidelines.py declares the canonical 7 PV-03
#   test functions (TestMnimiyBehavioralExtensions class).
#
# Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-2.
# ---------------------------------------------------------------------------
_V12_2_0_PV03_REF_FILE: Path = Path("workflow-system/agent/references/behavioral-guidelines.md")
_V12_2_0_PV03_SELECTOR_FILE: Path = Path("src/devolaflow/task_adaptive_selector.py")
_V12_2_0_PV03_SCHEMA_FILE: Path = Path("schemas/lean-dispatch.yaml")
_V12_2_0_PV03_PROFILES_FILE: Path = Path("workflow-system/agent/context_profiles.yaml")
_V12_2_0_PV03_TEST_FILE: Path = Path("tests/test_behavioral_guidelines.py")
_V12_2_0_PV03_NEW_RULE_IDS: tuple[str, ...] = ("BG-005", "BG-006", "BG-007")
_V12_2_0_PV03_NEW_FIELD_KEYS: tuple[str, ...] = (
    "no_llm_for_deterministic",
    "surface_conflicts",
    "convention_first",
)
_V12_2_0_PV03_REQUIRED_TEST_FN_NAMES: frozenset[str] = frozenset(
    {
        "test_active_no_llm_for_deterministic_emits_bg005",
        "test_active_surface_conflicts_emits_bg006",
        "test_active_convention_first_emits_bg007",
        "test_inactive_v12_2_0_rules_omit_their_bullets",
        "test_select_behavioral_sections_resolves_v12_2_0_keys_from_tier",
        "test_per_key_override_works_for_v12_2_0_keys",
        "test_pre_v12_2_0_profile_without_new_keys_resolves_falsy",
        "test_canonical_yaml_carries_v12_2_0_defaults",
    }
)


def test_v12_2_0_mnimiy_behavioral_extensions(project_root: Path) -> None:
    """W-18 v12.2.0 PV-03 D-2: Mnimiy 3-rule behavioral extension.

    Discharges the W-18 precondition for the v12.2.0 CHANGELOG entry
    that mentions the BG-005..BG-007 additions. Pins:

    * References doc declares all 3 NEW rule sections + field names.
    * `_compose_behavioral_block` renders the 3 NEW rule bullets.
    * Schema declares the 3 NEW sub-fields under `behavioral_guidelines`.
    * Per-tier defaults in `context_profiles.yaml` carry the 3 NEW keys.
    * Companion test class `TestMnimiyBehavioralExtensions` defines all
      8 canonical PV-03 test functions.

    Coupled invariants verified GREEN at v12.2.0 PV-03 close:
    * A-2.3 NEST extension — canonical_order length stays at 17 and
      schema version stays at 6 (no top-level field added).
    * A-2.4 multi-baseline 33/33 PASS unchanged.
    * C-4 SKILL.md line ceiling preserved (PV-03 added 0 SKILL.md lines).
    * C-4 references-tier ceiling: behavioral-guidelines.md stays
      ≤ 1000 lines (Large tier per SF-1).
    * W-21 Soul-set freeze preserved at 10 entries (behavioral primitives
      are NOT Soul rules; they live in the behavioral_guidelines block).
    * W-20 reuse-first preserved at 7 env flags (no new flag — the 3
      new BGs are dispatch-payload fields, not env-gated behaviour).
    * S-10 hook-chain byte-id contract preserved (no lifecycle hook
      changes; this PV is documentation + dispatcher rendering only).

    Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-2.
    """
    ref_path = project_root / _V12_2_0_PV03_REF_FILE
    assert ref_path.is_file(), (
        f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_REF_FILE} missing — release blocker."
    )
    ref_text = ref_path.read_text(encoding="utf-8")
    for rule_id in _V12_2_0_PV03_NEW_RULE_IDS:
        assert rule_id in ref_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_REF_FILE} missing rule "
            f"section for {rule_id}. The 3 NEW rule sections MUST land before "
            f"the CHANGELOG entry per W-18 sequencing. See gap analysis §2 D-2."
        )
    for field_key in _V12_2_0_PV03_NEW_FIELD_KEYS:
        assert field_key in ref_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_REF_FILE} missing field "
            f"name {field_key!r}. The reference doc MUST document the dispatch "
            f"sub-key for each NEW rule."
        )

    selector_path = project_root / _V12_2_0_PV03_SELECTOR_FILE
    assert selector_path.is_file(), (
        f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_SELECTOR_FILE} missing."
    )
    selector_text = selector_path.read_text(encoding="utf-8")
    for rule_id in _V12_2_0_PV03_NEW_RULE_IDS:
        rule_marker = f"{rule_id} "
        assert rule_marker in selector_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_SELECTOR_FILE} missing "
            f"`{rule_marker}` rendering literal. `_compose_behavioral_block` MUST "
            f"emit the rule id when the corresponding flag is active."
        )

    schema_path = project_root / _V12_2_0_PV03_SCHEMA_FILE
    schema_text = schema_path.read_text(encoding="utf-8")
    for field_key in _V12_2_0_PV03_NEW_FIELD_KEYS:
        assert field_key in schema_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_SCHEMA_FILE} missing "
            f"field shape declaration for {field_key!r}. The NEST sub-field MUST "
            f"land in `lean_format_spec.behavioral_guidelines.fields`."
        )

    profiles_path = project_root / _V12_2_0_PV03_PROFILES_FILE
    profiles_text = profiles_path.read_text(encoding="utf-8")
    for field_key in _V12_2_0_PV03_NEW_FIELD_KEYS:
        assert field_key in profiles_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_PROFILES_FILE} missing "
            f"per-tier default for {field_key!r} in `meta.behavioral_guidelines_defaults`."
        )

    test_path = project_root / _V12_2_0_PV03_TEST_FILE
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))

    def _collect_test_fn_names(node: ast.AST) -> set[str]:
        """Recursively collect test function names from module + class bodies."""
        names: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name.startswith(
                "test_"
            ):
                names.add(child.name)
        return names

    defined = _collect_test_fn_names(test_module)
    missing = sorted(_V12_2_0_PV03_REQUIRED_TEST_FN_NAMES - defined)
    assert not missing, (
        f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_TEST_FILE} missing required "
        f"NEW test functions {missing!r}. Required canonical 8-name set per PV-03 "
        f"dispatch: {sorted(_V12_2_0_PV03_REQUIRED_TEST_FN_NAMES)!r}."
    )


# ---------------------------------------------------------------------------
# v12.2.0 PV-04 W-18 ghost-audit refresh — telegraphed runtime enforcement.
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.2.0
# CHANGELOG entry mentioning the v12.0.0+v12.1.0 telegraphed runtime
# enforcement. This stanza pins the v12.2.0 PV-04 surface:
#
# * src/devolaflow/lifecycle/reject_subagent_quality_score.py — NEW
#   pre_dispatch extra hook (D-1 runtime closure).
# * src/devolaflow/lifecycle/__init__.py wires the new hook via
#   `register_hook(_PRE_DISPATCH_EVENT, reject_subagent_quality_score)`.
# * src/devolaflow/agent_workspace/dispatch_executor.py adds the optional
#   `timeouts={task_id: seconds}` kwarg to both dispatch_sequential and
#   dispatch_parallel (D-2 runtime closure — `asyncio.wait_for`).
# * src/devolaflow/task_adaptive_selector.py declares
#   TASK_TYPE_TIMEOUT_DEFAULTS + default_timeout_for() per the SKILL.md
#   §"Subagent Hang Prevention" L0 contract.
# * tests/test_async_dispatch_executor_timeout.py defines >= 13 canonical
#   PV-04 timeout test functions.
# * tests/test_lifecycle_reject_subagent_quality_score.py defines >= 8
#   canonical PV-04 hook test functions.
#
# Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-4 +
# CHANGELOG.md §[12.0.0] + §[12.1.0] telegraph.
# ---------------------------------------------------------------------------
_V12_2_0_PV04_HOOK_FILE: Path = Path("src/devolaflow/lifecycle/reject_subagent_quality_score.py")
_V12_2_0_PV04_EXECUTOR_FILE: Path = Path("src/devolaflow/agent_workspace/dispatch_executor.py")
_V12_2_0_PV04_SELECTOR_FILE: Path = Path("src/devolaflow/task_adaptive_selector.py")
_V12_2_0_PV04_LIFECYCLE_INIT_FILE: Path = Path("src/devolaflow/lifecycle/__init__.py")
_V12_2_0_PV04_TIMEOUT_TEST_FILE: Path = Path("tests/test_async_dispatch_executor_timeout.py")
_V12_2_0_PV04_HOOK_TEST_FILE: Path = Path("tests/test_lifecycle_reject_subagent_quality_score.py")
_V12_2_0_PV04_TASK_TYPES: tuple[str, ...] = (
    "research",
    "impl",
    "test",
    "review",
    "hotfix",
)
_V12_2_0_PV04_TIMEOUT_MIN_TESTS: int = 13
_V12_2_0_PV04_HOOK_MIN_TESTS: int = 8


def test_v12_2_0_telegraphed_runtime_enforcement(project_root: Path) -> None:
    """W-18 v12.2.0 PV-04 D-4: runtime enforcement of v12.0.0+v12.1.0 telegraph.

    Pins the v12.2.0 PV-04 surface so the CHANGELOG entry mentioning
    runtime enforcement is backed by working code + tests per W-18.

    Coupled invariants verified GREEN at v12.2.0 PV-04 close:
    * S-10 hook-chain byte-id contract preserved — the new hook is
      registered as an extra (NOT a default replacement) so callers
      registering their own extras on `pre_dispatch` see the same
      validate_dispatch + validate_owned_files defaults first.
    * Backward-compat: callers that do NOT pass the `timeouts=` kwarg
      to AsyncDispatchExecutor see v9.3.0 byte-identical behaviour.
    * A-2.4 multi-baseline 33/33 PASS unchanged (no schema NEST).
    * W-20 reuse-first preserved at 7 env flags (no new flag — the
      v12.2.0 PV-04 surfaces are pure library-level + lifecycle wiring;
      no env-gated activation needed).

    Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-4.
    """
    # 1. The hook module exists and declares the canonical event name.
    hook_path = project_root / _V12_2_0_PV04_HOOK_FILE
    assert hook_path.is_file(), (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_FILE} missing — release blocker."
    )
    hook_text = hook_path.read_text(encoding="utf-8")
    assert 'EVENT = "pre_dispatch"' in hook_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_FILE} missing the "
        f'canonical `EVENT = "pre_dispatch"` constant.'
    )
    assert "def reject_subagent_quality_score(" in hook_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_FILE} missing the "
        f"canonical `reject_subagent_quality_score` function definition."
    )

    # 2. The lifecycle init wires the hook via register_hook.
    init_path = project_root / _V12_2_0_PV04_LIFECYCLE_INIT_FILE
    init_text = init_path.read_text(encoding="utf-8")
    assert "reject_subagent_quality_score" in init_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_LIFECYCLE_INIT_FILE} "
        f"missing `reject_subagent_quality_score` import / wiring."
    )
    assert "register_hook(_PRE_DISPATCH_EVENT, reject_subagent_quality_score)" in init_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_LIFECYCLE_INIT_FILE} "
        f"missing the canonical `register_hook` call for the new hook."
    )

    # 3. The executor accepts the `timeouts` kwarg on both dispatch methods.
    executor_text = (project_root / _V12_2_0_PV04_EXECUTOR_FILE).read_text(encoding="utf-8")
    assert "timeouts: dict[str, float] | None = None" in executor_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_EXECUTOR_FILE} missing the "
        f"canonical `timeouts: dict[str, float] | None = None` kwarg signature."
    )
    assert "asyncio.wait_for" in executor_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_EXECUTOR_FILE} missing "
        f"the `asyncio.wait_for` timeout primitive."
    )

    # 4. The selector declares the per-task-type defaults.
    selector_text = (project_root / _V12_2_0_PV04_SELECTOR_FILE).read_text(encoding="utf-8")
    assert "TASK_TYPE_TIMEOUT_DEFAULTS" in selector_text
    assert "def default_timeout_for(" in selector_text
    for task_type in _V12_2_0_PV04_TASK_TYPES:
        assert f'"{task_type}"' in selector_text, (
            f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_SELECTOR_FILE} missing "
            f"per-task-type default for {task_type!r}. The SKILL.md §'Subagent Hang "
            f"Prevention' L0 contract pins all 5 task types."
        )

    # 5. The two NEW test files exist with the minimum test-function count.
    timeout_test_path = project_root / _V12_2_0_PV04_TIMEOUT_TEST_FILE
    assert timeout_test_path.is_file(), (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_TIMEOUT_TEST_FILE} missing."
    )
    timeout_module = ast.parse(timeout_test_path.read_text(encoding="utf-8"))
    timeout_test_count = sum(
        1
        for node in timeout_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    )
    assert timeout_test_count >= _V12_2_0_PV04_TIMEOUT_MIN_TESTS, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_TIMEOUT_TEST_FILE} declares "
        f"{timeout_test_count} test functions; PV-04 dispatch requires "
        f">= {_V12_2_0_PV04_TIMEOUT_MIN_TESTS}."
    )

    hook_test_path = project_root / _V12_2_0_PV04_HOOK_TEST_FILE
    assert hook_test_path.is_file(), (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_TEST_FILE} missing."
    )
    hook_module = ast.parse(hook_test_path.read_text(encoding="utf-8"))
    hook_test_count = sum(
        1
        for node in hook_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    )
    assert hook_test_count >= _V12_2_0_PV04_HOOK_MIN_TESTS, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_TEST_FILE} declares "
        f"{hook_test_count} test functions; PV-04 dispatch requires "
        f">= {_V12_2_0_PV04_HOOK_MIN_TESTS}."
    )


# ---------------------------------------------------------------------------
# v12.3.0 PV-02 W-18 ghost-audit refresh — Session Banner Contract (D-1).
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.3.0
# CHANGELOG entry mentioning the Session Banner Contract addition. This
# stanza pins the v12.3.0 PV-02 surface:
#
# * workflow-system/agent/SKILL.md §"Version & Update" carries the
#   NEW "Session Banner Contract" subsection with 3 normative L0
#   obligations (workflow-start banner, workflow-end banner, footer
#   line in Task Quality Score output).
# * The 3 literal banner strings are present so a substring grep
#   catches their presence even if the surrounding chrome shifts.
#
# Source: ``.local/research/v12.3.0_gap_analysis.md`` §2 D-1 +
# ``.local/feedbacks/feedback_for_v12.1.1.md`` #1.
# ---------------------------------------------------------------------------
_V12_3_0_SKILL_FILE: Path = Path("workflow-system/agent/SKILL.md")
_V12_3_0_PV02_REQUIRED_LITERALS: tuple[str, ...] = (
    "Session Banner Contract",
    "🌸 DevolaFlow",
    "workflow: <type> · mode:",
    "complete · <stages> stages",
    "feedback_for_v12.1.1.md",
)


def test_v12_3_0_session_banner_contract(project_root: Path) -> None:
    """W-18 v12.3.0 PV-02 D-1: Session Banner Contract for version printing.

    Discharges the W-18 precondition for the v12.3.0 CHANGELOG entry
    mentioning the Session Banner Contract addition. Pins the 5 canonical
    literals so a substring grep catches their presence even if the
    surrounding chrome shifts.

    Coupled invariants:
    * SKILL.md line count stays ≤ 500 (C-4 default-tier ceiling) —
      verified by ``tests/test_subagent_output_restrictions.py::
      test_skill_md_under_500_lines``.
    * v12.1.0 D-1 literals (``L0 ONLY`` + ``Subagents MUST NOT``)
      stay GREEN in the SKILL.md stub even after the PV-03 collapse
      (verified by the v12.1.0 stanza above).

    Source: ``.local/research/v12.3.0_gap_analysis.md`` §2 D-1.
    """
    skill_path = project_root / _V12_3_0_SKILL_FILE
    assert skill_path.is_file(), (
        f"W-18 v12.3.0 violation: {_V12_3_0_SKILL_FILE} missing — release blocker."
    )
    skill_text = skill_path.read_text(encoding="utf-8")
    for literal in _V12_3_0_PV02_REQUIRED_LITERALS:
        assert literal in skill_text, (
            f"W-18 v12.3.0 PV-02 violation: {_V12_3_0_SKILL_FILE} missing literal "
            f"{literal!r}. The Session Banner Contract subsection MUST land "
            f"before the CHANGELOG entry per W-18 sequencing. See gap analysis "
            f"§2 D-1."
        )


# ---------------------------------------------------------------------------
# v12.3.0 PV-03 W-18 ghost-audit refresh — Task Quality Score extraction (D-2).
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.3.0
# CHANGELOG entry mentioning the Task Quality Score extraction. This stanza
# pins the v12.3.0 PV-03 surface:
#
# * workflow-system/agent/references/task-quality-score.md is the NEW
#   Tier 3 on-demand reference with the full extracted rubric.
# * workflow-system/agent/SKILL.md §"Task Quality Score (L0 ONLY)" is
#   collapsed to a stub that preserves the v12.1.0 D-1 literals
#   (``L0 ONLY`` + ``Subagents MUST NOT``) AND cross-links the new
#   reference file.
# * The Reference Navigation Guide Tier 3 table lists the new
#   reference with the "Load at workflow CLOSE only" hint.
# * context_profiles.yaml task_quality_score anchor block carries the
#   v12.3.0 PV-03 absorption comment so future PVs understand the
#   line-anchor shift.
#
# Source: ``.local/research/v12.3.0_gap_analysis.md`` §2 D-2 +
# ``.local/feedbacks/feedback_for_v12.1.1.md`` #2.
# ---------------------------------------------------------------------------
_V12_3_0_PV03_NEW_REFERENCE: Path = Path("workflow-system/agent/references/task-quality-score.md")
_V12_3_0_PV03_CONTEXT_PROFILES: Path = Path("workflow-system/agent/context_profiles.yaml")
_V12_3_0_PV03_REQUIRED_REF_LITERALS: tuple[str, ...] = (
    "Task Quality Score (L0 ONLY)",
    "L0 ONLY",
    "Subagents MUST NOT",
    "📊 Task Quality Score:",
    "🌸 DevolaFlow",
    "feedback_for_v12.1.1.md",
)
_V12_3_0_PV03_REQUIRED_SKILL_LITERALS: tuple[str, ...] = (
    "L0 ONLY",
    "Subagents MUST NOT",
    "references/task-quality-score.md",
    "loads on-demand",
    "v12.3.0 PV-03",
)


def test_v12_3_0_quality_score_extracted_to_reference(project_root: Path) -> None:
    """W-18 v12.3.0 PV-03 D-2: Task Quality Score extraction + SKILL.md stub.

    Discharges the W-18 precondition for the v12.3.0 CHANGELOG entry
    mentioning the Task Quality Score extraction. Pins:

    * The NEW reference file exists with the full extracted rubric +
      canonical literals (Dimensions table + 📊 output template +
      version-literal footer per v12.3.0 PV-02).
    * The SKILL.md stub preserves both v12.1.0 D-1 literals (`L0 ONLY`
      + `Subagents MUST NOT`) so the v12.1.0 W-18 stanza stays GREEN.
    * The SKILL.md stub cross-links the new reference + cites the
      v12.3.0 PV-03 closure rationale.
    * context_profiles.yaml `task_quality_score` anchor block declares
      the post-collapse line range (478-480 stub region).

    Coupled invariants:
    * SKILL.md stays ≤ 500 lines (C-4) — PV-03 nets ~-22 lines from
      the section collapse.
    * v12.1.0 W-18 stanza ``test_v12_1_0_subagent_output_restrictions``
      stays GREEN (the literal substrings ``L0 ONLY`` + ``Subagents MUST NOT``
      survive in the stub).

    Source: ``.local/research/v12.3.0_gap_analysis.md`` §2 D-2.
    """
    ref_path = project_root / _V12_3_0_PV03_NEW_REFERENCE
    assert ref_path.is_file(), (
        f"W-18 v12.3.0 PV-03 violation: {_V12_3_0_PV03_NEW_REFERENCE} missing — "
        f"release blocker. The extracted Task Quality Score rubric MUST land at "
        f"this path so it can be loaded on-demand at workflow CLOSE per the "
        f"v12.1.1 feedback closure."
    )
    ref_text = ref_path.read_text(encoding="utf-8")
    for literal in _V12_3_0_PV03_REQUIRED_REF_LITERALS:
        assert literal in ref_text, (
            f"W-18 v12.3.0 PV-03 violation: {_V12_3_0_PV03_NEW_REFERENCE} missing "
            f"literal {literal!r}. The extracted rubric MUST preserve the canonical "
            f"surfaces (section heading + L0-only marker + output template + "
            f"v12.3.0 PV-02 version-literal footer + feedback citation)."
        )

    skill_path = project_root / _V12_3_0_SKILL_FILE
    skill_text = skill_path.read_text(encoding="utf-8")
    for literal in _V12_3_0_PV03_REQUIRED_SKILL_LITERALS:
        assert literal in skill_text, (
            f"W-18 v12.3.0 PV-03 violation: {_V12_3_0_SKILL_FILE} stub missing "
            f"literal {literal!r}. The stub MUST preserve both v12.1.0 D-1 "
            f"literals AND cross-link the new reference AND cite the v12.3.0 "
            f"PV-03 closure rationale."
        )

    profiles_path = project_root / _V12_3_0_PV03_CONTEXT_PROFILES
    profiles_text = profiles_path.read_text(encoding="utf-8")
    assert "v12.3.0 PV-03" in profiles_text, (
        f"W-18 v12.3.0 PV-03 violation: {_V12_3_0_PV03_CONTEXT_PROFILES} missing "
        f"the v12.3.0 PV-03 absorption comment in the `task_quality_score` "
        f"anchor block. The line-anchor shift MUST be documented so future "
        f"PVs understand the post-collapse coordinates."
    )
    assert 'lines: "480-482"' in profiles_text, (
        f"W-18 v12.3.0 PV-03 violation: {_V12_3_0_PV03_CONTEXT_PROFILES} missing "
        f'the post-collapse `lines: "480-482"` anchor for task_quality_score. '
        f"The v12.3.0 PV-03 line-anchor update MUST land in the same PR as the "
        f"SKILL.md section collapse."
    )


# ---------------------------------------------------------------------------
# v12.3.0 PV-04 W-18 ghost-audit refresh — v12.2.0 retro telegraph pickup (D-3).
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.3.0
# CHANGELOG entry mentioning the telegraph pickup items. This stanza pins
# the v12.3.0 PV-04 surface:
#
# * .rules/workflow.mdc W-16 paragraph carries the new
#   "MAY land at cycle start OR cycle close" clarification + cites
#   v12.2.0 retrospective §4.2 + v12.3.0 gap analysis §2 D-3.
# * The compiled `AGENTS.md` + `.cursor/rules/repo-governance.mdc`
#   reflect the W-16 edit (CI lint test_rule_surfaces_compile_only
#   catches drift if the compile step is skipped).
# * workflow-system/agent/SKILL.md §"Repo-Init Pre-Dispatch Contract"
#   carries the NEW "Working-tree sanity check (v12.3.0 PV-04)" bullet
#   per v12.2.0 retro §4.3 learning.
# * workflow-system/agent/references/execution-protocol.md carries the
#   NEW §14 "Per-Task-Type Timeout Defaults Helper" discovery hint
#   citing v12.2.0 PV-04 default_timeout_for() + per-task-type defaults.
#
# Source: ``.local/research/v12.3.0_gap_analysis.md`` §2 D-3 +
# ``.local/research/v12.2.0_retrospective.md`` §§4.2 + 4.3 + 6.
# ---------------------------------------------------------------------------
_V12_3_0_PV04_RULES_FILE: Path = Path(".rules/workflow.mdc")
_V12_3_0_PV04_AGENTS_MD: Path = Path("AGENTS.md")
_V12_3_0_PV04_EXEC_PROTOCOL: Path = Path("workflow-system/agent/references/execution-protocol.md")
_V12_3_0_PV04_W16_LITERAL: str = "v12.3.0 PV-04 clarification"
_V12_3_0_PV04_GIT_STATUS_LITERAL: str = "Working-tree sanity check (v12.3.0 PV-04"
_V12_3_0_PV04_EXEC_PROTOCOL_LITERAL: str = "Per-Task-Type Timeout Defaults Helper"


def test_v12_3_0_telegraph_pickup(project_root: Path) -> None:
    """W-18 v12.3.0 PV-04 D-3: v12.2.0 retrospective telegraph item pickup.

    Discharges the W-18 precondition for the v12.3.0 CHANGELOG entry
    mentioning the 3 telegraph items picked up from v12.2.0 retrospective
    §6. Pins:

    * .rules/workflow.mdc W-16 paragraph contains the v12.3.0 PV-04
      clarification literal + the "MAY land at cycle start OR close"
      semantic.
    * AGENTS.md (compiled output of `make compile-rules`) also contains
      the v12.3.0 PV-04 W-16 clarification — verifies the compile
      pipeline ran post-edit.
    * SKILL.md §"Repo-Init Pre-Dispatch Contract" contains the new
      working-tree sanity check bullet.
    * references/execution-protocol.md contains the new §14
      "Per-Task-Type Timeout Defaults Helper" discovery-hint section
      cross-linking the v12.2.0 PV-04 `default_timeout_for()` helper.

    Source: ``.local/research/v12.3.0_gap_analysis.md`` §2 D-3.
    """
    rules_path = project_root / _V12_3_0_PV04_RULES_FILE
    assert rules_path.is_file(), (
        f"W-18 v12.3.0 PV-04 violation: {_V12_3_0_PV04_RULES_FILE} missing — release blocker."
    )
    rules_text = rules_path.read_text(encoding="utf-8")
    assert _V12_3_0_PV04_W16_LITERAL in rules_text, (
        f"W-18 v12.3.0 PV-04 violation: {_V12_3_0_PV04_RULES_FILE} missing literal "
        f"{_V12_3_0_PV04_W16_LITERAL!r}. The W-16 wording clarification MUST land "
        f"before the CHANGELOG entry per W-18 sequencing."
    )

    agents_md_path = project_root / _V12_3_0_PV04_AGENTS_MD
    if agents_md_path.is_file():
        agents_md_text = agents_md_path.read_text(encoding="utf-8")
        assert _V12_3_0_PV04_W16_LITERAL in agents_md_text, (
            f"W-18 v12.3.0 PV-04 violation: compiled {_V12_3_0_PV04_AGENTS_MD} "
            f"missing literal {_V12_3_0_PV04_W16_LITERAL!r}. Run "
            f"`make compile-rules` after editing .rules/workflow.mdc — the "
            f"compile step propagates rule edits into AGENTS.md + "
            f".cursor/rules/repo-governance.mdc."
        )

    skill_path = project_root / _V12_3_0_SKILL_FILE
    skill_text = skill_path.read_text(encoding="utf-8")
    assert _V12_3_0_PV04_GIT_STATUS_LITERAL in skill_text, (
        f"W-18 v12.3.0 PV-04 violation: {_V12_3_0_SKILL_FILE} missing literal "
        f"{_V12_3_0_PV04_GIT_STATUS_LITERAL!r}. The Working-tree sanity check "
        f"bullet MUST land in §'Repo-Init Pre-Dispatch Contract' per the "
        f"v12.2.0 retrospective §4.3 learning."
    )

    exec_path = project_root / _V12_3_0_PV04_EXEC_PROTOCOL
    exec_text = exec_path.read_text(encoding="utf-8")
    assert _V12_3_0_PV04_EXEC_PROTOCOL_LITERAL in exec_text, (
        f"W-18 v12.3.0 PV-04 violation: {_V12_3_0_PV04_EXEC_PROTOCOL} missing "
        f"literal {_V12_3_0_PV04_EXEC_PROTOCOL_LITERAL!r}. The discovery-hint "
        f"section MUST surface the v12.2.0 PV-04 default_timeout_for() helper "
        f"for operators."
    )
    assert "default_timeout_for(" in exec_text, (
        f"W-18 v12.3.0 PV-04 violation: {_V12_3_0_PV04_EXEC_PROTOCOL} discovery-hint "
        f"section MUST cite the canonical helper symbol `default_timeout_for(...)` so "
        f"operators can grep for it."
    )


# ---------------------------------------------------------------------------
# v12.4.0 PV-02 W-18 ghost-audit refresh — tooling fixes (D-1).
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the tooling fix items. This stanza pins
# the v12.4.0 PV-02 surface (closes v12.3.0 retrospective §6 items 2 + 3):
#
# * benchmarks/devolaflow_context/generate_baseline.py carries the literal
#   ``sys.modules["tiktoken"] = None`` at module-import scope (Option B
#   from tests/conftest.py docstring). Without this pin, standalone
#   baseline regens diverge from pytest scoring by ~7pp on composite
#   — see v12.3.0 retrospective §4.2 for the 3-attempt regen story.
# * scripts/realign_section_anchors.py exists with the documented
#   ``def realign_anchors(skill_md_path, profiles_yaml_path, *, dry_run=False)``
#   signature + CLI ``--dry-run`` / ``--apply`` flags. Closes v12.3.0
#   retrospective §4.3 (the ~15 min/cycle of manual context_profiles.yaml
#   section_anchors edits).
# * tests/test_generate_baseline_tiktoken_disabled.py exists and pins the
#   tiktoken-pin contract.
# * tests/test_realign_section_anchors.py exists and pins the realign
#   tool's idempotency + drift-detection + dry-run + S-5 contracts.
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-1 +
# ``.local/research/v12.3.0_retrospective.md`` §§4.2 + 4.3 + 6.
# ---------------------------------------------------------------------------
_V12_4_0_GENERATE_BASELINE_FILE: Path = Path("benchmarks/devolaflow_context/generate_baseline.py")
_V12_4_0_TIKTOKEN_PIN_LITERAL: str = 'sys.modules["tiktoken"] = None'
_V12_4_0_REALIGN_SCRIPT: Path = Path("scripts/realign_section_anchors.py")
_V12_4_0_REALIGN_SIGNATURE_LITERAL: str = "def realign_anchors("
_V12_4_0_TIKTOKEN_TEST_FILE: Path = Path("tests/test_generate_baseline_tiktoken_disabled.py")
_V12_4_0_REALIGN_TEST_FILE: Path = Path("tests/test_realign_section_anchors.py")


def test_v12_4_0_tooling_fixes(project_root: Path) -> None:
    """W-18 v12.4.0 PV-02 D-1: tooling fixes from v12.3.0 retro §6 items 2 + 3.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the two tooling fixes:

    * ``benchmarks/devolaflow_context/generate_baseline.py`` pins
      ``sys.modules["tiktoken"] = None`` at module top so standalone
      regens match pytest scoring (closes v12.3.0 retro §4.2).
    * ``scripts/realign_section_anchors.py`` exists and exposes the
      documented ``realign_anchors(...)`` signature so per-cycle
      section-anchor edits become a 1-command operation (closes
      v12.3.0 retro §4.3).

    Plus the two NEW test files MUST exist:

    * ``tests/test_generate_baseline_tiktoken_disabled.py`` pins the
      tiktoken-pin contract (PV-02 owned-files manifest item 3).
    * ``tests/test_realign_section_anchors.py`` pins the realign tool
      idempotency + drift-detection contracts (PV-02 owned-files
      manifest item 4).

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-1.
    """
    generate_baseline_path = project_root / _V12_4_0_GENERATE_BASELINE_FILE
    assert generate_baseline_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_GENERATE_BASELINE_FILE} "
        "missing — release blocker. The tiktoken pin lives at module top of "
        "this file per the PV-02 owned-files manifest item 1."
    )
    generate_baseline_text = generate_baseline_path.read_text(encoding="utf-8")
    assert _V12_4_0_TIKTOKEN_PIN_LITERAL in generate_baseline_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_GENERATE_BASELINE_FILE} "
        f"missing literal {_V12_4_0_TIKTOKEN_PIN_LITERAL!r}. The pin MUST land "
        "at module-import scope before any devolaflow/benchmarks import — "
        "without it, standalone regens diverge from pytest scoring by ~7pp on "
        "composite per v12.3.0 retrospective §4.2."
    )
    # Cross-check: docstring credits the v12.3.0 retro learning so future
    # readers can trace the design rationale.
    assert "v12.3.0 retro" in generate_baseline_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_GENERATE_BASELINE_FILE} "
        "must credit ``v12.3.0 retro`` in its docstring per the PV-02 "
        "owned-files manifest. The docstring is the source-of-truth "
        "explanation for the Option B pin."
    )

    realign_script_path = project_root / _V12_4_0_REALIGN_SCRIPT
    assert realign_script_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing — "
        "release blocker. The realign tool MUST exist with the documented "
        "signature per the PV-02 owned-files manifest item 2."
    )
    realign_text = realign_script_path.read_text(encoding="utf-8")
    assert _V12_4_0_REALIGN_SIGNATURE_LITERAL in realign_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing "
        f"literal {_V12_4_0_REALIGN_SIGNATURE_LITERAL!r}. The documented public "
        "signature is ``realign_anchors(skill_md_path, profiles_yaml_path, "
        "*, dry_run=False)``."
    )
    # CLI flags MUST be present per the PV-02 spec (--dry-run / --apply).
    assert "--dry-run" in realign_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing "
        "``--dry-run`` CLI flag. The CLI smoke test (PV-02 acceptance criterion 6) "
        "depends on this flag."
    )
    assert "--apply" in realign_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing "
        "``--apply`` CLI flag. The operator opts-in to mutation via --apply; "
        "default-OFF dry-run is the safety contract."
    )

    tiktoken_test_path = project_root / _V12_4_0_TIKTOKEN_TEST_FILE
    assert tiktoken_test_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_TIKTOKEN_TEST_FILE} missing — "
        "release blocker. The 3-test contract for the generate_baseline "
        "tiktoken pin MUST exist per PV-02 owned-files manifest item 3."
    )
    tiktoken_test_text = tiktoken_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_tiktoken_disabled_at_import",
        "test_baseline_regen_deterministic",
        "test_no_regression_vs_pytest",
    ):
        assert f"def {expected_test}" in tiktoken_test_text, (
            f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_TIKTOKEN_TEST_FILE} "
            f"missing test function ``{expected_test}``. The 3-test contract "
            "is documented in the PV-02 owned-files manifest item 3."
        )

    realign_test_path = project_root / _V12_4_0_REALIGN_TEST_FILE
    assert realign_test_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_TEST_FILE} missing — "
        "release blocker. The 5-test contract for the realign tool MUST exist "
        "per PV-02 owned-files manifest item 4."
    )
    realign_test_text = realign_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_header_parse_correctness",
        "test_idempotent_apply",
        "test_drift_detection_proposes_correct_realignment",
        "test_dry_run_does_not_modify_file",
        "test_missing_input_raises_friendly_error",
    ):
        assert f"def {expected_test}" in realign_test_text, (
            f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_TEST_FILE} "
            f"missing test function ``{expected_test}``. The 5-test contract "
            "is documented in the PV-02 owned-files manifest item 4."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.4.0 PV-03 D-2 — ``evaluate_gate`` helper extraction
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the PV-03 cc-spike refactor. This stanza pins
# the v12.4.0 PV-03 surface (closes v12.3.0 retrospective §3 D-4 item 1):
#
# * src/devolaflow/gate/scorer.py declares all four ``_apply_*`` helpers
#   extracted from the original ``evaluate_gate`` body (cc=22 → cc=7):
#   ``_apply_breaker_check`` (cc=3), ``_apply_cycle_detection`` (cc=3),
#   ``_apply_ratchet`` (cc=2), ``_apply_complexity_and_legibility`` (cc=5).
#   Each helper is module-scope (``def`` prefixed) so static AST walkers
#   like the cc-pin test file can locate them.
# * src/devolaflow/gate/scorer.py keeps the ``evaluate_gate`` public
#   signature byte-identical to the pre-refactor form documented at
#   ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2. The CO-2 / C-3
#   no-API-break invariant is what allows the 101 ``tests/test_gate.py``
#   callers + the 36 ``tests/test_benchmarks.py`` scenarios + downstream
#   consumers (W-3 SI-3 harness, PV-06 self-eval) to keep working without
#   modification.
# * tests/test_evaluate_gate_complexity.py exists and pins the per-symbol
#   cc ceilings via stdlib ``ast`` walker (no ``radon`` dev-dep added).
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2 +
# ``.cursor/plans/v12.4.0_expansion_refactor_cycle_240b72f0.plan.md``
# §3 PV-03 + ``.local/research/v12.4.0_nines_deep_evaluate_gate.json``
# finding ``CC-67079a-0000``.
# ---------------------------------------------------------------------------
_V12_4_0_SCORER_FILE: Path = Path("src/devolaflow/gate/scorer.py")
_V12_4_0_COMPLEXITY_TEST_FILE: Path = Path("tests/test_evaluate_gate_complexity.py")
_V12_4_0_EVALUATE_GATE_HELPERS: tuple[str, ...] = (
    "_apply_breaker_check",
    "_apply_cycle_detection",
    "_apply_ratchet",
    "_apply_complexity_and_legibility",
)
# The CO-2 / C-3 byte-identical public signature for ``evaluate_gate``.
# Must match the literal string in
# ``tests/test_evaluate_gate_complexity.py::_EVALUATE_GATE_SIGNATURE``
# verbatim — the two pins reference the same source-of-truth surface.
_V12_4_0_EVALUATE_GATE_SIGNATURE_LITERAL: str = (
    "def evaluate_gate(\n"
    "    gate_input: GateInput,\n"
    "    profile: GateProfile,\n"
    "    round_num: int = 1,\n"
    "    history: list[ConvergenceRound] | None = None,\n"
    '    gate_type: str = "standard",\n'
    "    breaker: TokenBudgetBreaker | None = None,\n"
    "    cumulative_tokens: int | None = None,\n"
    "    cycle_detector: CycleDetector | None = None,\n"
    "    ratchet: MonotonicRatchet | None = None,\n"
    "    ratchet_artifact: dict[str, object] | None = None,\n"
    "    complexity_detector: ComplexityDetector | None = None,\n"
    "    complexity_signals: ComplexitySignals | None = None,\n"
    '    complexity_task_complexity: str = "standard",\n'
    "    legibility_scorer: LegibilityScorer | None = None,\n"
    "    legibility_files: Sequence[str] | None = None,\n"
    ") -> GateVerdict:"
)


def test_v12_4_0_evaluate_gate_refactor(project_root: Path) -> None:
    """W-18 v12.4.0 PV-03 D-2: ``evaluate_gate`` cc=22 → cc=7 helper extraction.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the PV-03 cc-spike refactor of ``evaluate_gate``. The
    stanza asserts three load-bearing surfaces:

    (a) Every ``_apply_*`` helper symbol is present in
    ``src/devolaflow/gate/scorer.py`` at module scope (one ``def`` per
    helper). Without these four symbols the cc reduction did NOT happen
    and the CHANGELOG entry would be a ghost feature per S-4.

    (b) The public signature of ``evaluate_gate`` is byte-identical to
    the pre-refactor form. The CO-2 / C-3 no-API-break invariant pins
    the entire 16-line parameter list verbatim (whitespace included).
    Any reorder / rename / default-change is a release blocker that
    would break all 101 ``tests/test_gate.py`` callers + the 36
    ``tests/test_benchmarks.py`` scenarios + downstream W-3 SI-3 harness.

    (c) The companion test file ``tests/test_evaluate_gate_complexity.py``
    exists with the three cc-pin tests (the orchestrator cc ≤ 10 pin,
    the per-helper cc ≤ 8 parametrize, and the signature byte-identical
    literal match). The companion file is what catches a future PV
    re-bloating the orchestrator body — without it the W-18 / W-4 / SI-4
    safety net has a hole.

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2 +
    ``.cursor/plans/v12.4.0_expansion_refactor_cycle_240b72f0.plan.md``
    §3 PV-03; the W-18 sequencing rule is at
    ``.cursor/rules/repo-governance.mdc`` §W-18.
    """
    scorer_path = project_root / _V12_4_0_SCORER_FILE
    assert scorer_path.is_file(), (
        f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_SCORER_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical scorer "
        "module per the PV-03 owned-files manifest item 1."
    )
    scorer_text = scorer_path.read_text(encoding="utf-8")

    # (a) — each ``_apply_*`` helper must be present at module scope.
    for helper_name in _V12_4_0_EVALUATE_GATE_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in scorer_text, (
            f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_SCORER_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``evaluate_gate`` cc from 22 to 7; if this "
            "assertion fires, the refactor was either reverted or never "
            "applied. The expected helper signatures are documented at "
            "``.local/research/v12.4.0_gap_analysis.md`` §2 D-2."
        )

    # (b) — public signature of ``evaluate_gate`` must be byte-identical.
    assert _V12_4_0_EVALUATE_GATE_SIGNATURE_LITERAL in scorer_text, (
        f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_SCORER_FILE} has drifted "
        "the public ``evaluate_gate`` signature from the pre-refactor form. "
        "The CO-2 / C-3 no-API-break invariant requires byte-identical "
        "preservation of the entire 16-line parameter list. Expected "
        f"literal:\n\n{_V12_4_0_EVALUATE_GATE_SIGNATURE_LITERAL}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``legibility_files`` with a default value (additive change) — "
        "do NOT reorder existing parameters or change defaults."
    )

    # (c) — companion cc-pin test file MUST exist.
    complexity_test_path = project_root / _V12_4_0_COMPLEXITY_TEST_FILE
    assert complexity_test_path.is_file(), (
        f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_COMPLEXITY_TEST_FILE} "
        "missing — release blocker. The companion cc-pin test file "
        "guards against future re-bloat of ``evaluate_gate`` per the "
        "PV-03 owned-files manifest item 3."
    )
    complexity_test_text = complexity_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_evaluate_gate_cc_under_ceiling",
        "test_evaluate_gate_helpers_cc_under_ceiling",
        "test_evaluate_gate_signature_byte_identical",
    ):
        assert f"def {expected_test}" in complexity_test_text, (
            f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_COMPLEXITY_TEST_FILE} "
            f"missing test function ``{expected_test}``. The 3-test contract "
            "is documented in the PV-03 owned-files manifest item 3."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.4.0 PV-04 D-3 — cc-spike refactor pair
# (``build_mapping_from_dict`` cc=21 + ``_collapse_block`` cc=25)
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the PV-04 cc-spike refactor pair. This stanza
# pins the v12.4.0 PV-04 surface (closes v12.3.0 retrospective §3 D-4
# items 2 + 3 paired):
#
# * src/devolaflow/shell_proxy/commands.py declares all four ``_validate_*``
#   / ``_build_*`` helpers extracted from the original
#   ``build_mapping_from_dict`` body (cc=21 → cc=9):
#   ``_validate_schema_version`` (cc=4), ``_validate_scalar_fields`` (cc=6),
#   ``_validate_tags`` (cc=2), ``_build_filter_lists`` (cc=5). Each helper
#   is module-scope so the static AST walker in the cc-pin test file can
#   locate them.
# * src/devolaflow/shell_proxy/commands.py keeps the
#   ``build_mapping_from_dict`` public signature byte-identical to the
#   pre-refactor form. The CO-2 / C-3 no-API-break invariant is what
#   allows the 68 ``tests/test_shell_proxy_commands.py`` callers + the
#   loader + the apply_local_recipe layer to keep working without
#   modification.
# * src/devolaflow/writing_style/transforms/bullets.py declares all four
#   helpers extracted from the original ``_collapse_block`` body (cc=25 →
#   cc=6): ``_classify_block_lines`` (cc=7), ``_validate_bullet_constraints``
#   (cc=6), ``_collapse_no_intro`` (cc=2), ``_collapse_with_intro`` (cc=4).
# * src/devolaflow/writing_style/transforms/bullets.py keeps the
#   ``_collapse_block`` private signature byte-identical to the
#   pre-refactor form so the 27 ``tests/test_writing_style_*`` fixture
#   corpus tests keep working without modification.
# * tests/test_v12_4_0_complexity_targets.py exists and pins both
#   per-symbol cc ceilings via stdlib ``ast`` walker (no ``radon``
#   dev-dep added) AND carries a cross-PV regression guard for the
#   PV-03 ``evaluate_gate`` cc=7 invariant.
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3 +
# ``.local/research/v12.4.0_nines_deep_commands.json`` (finding for
# ``build_mapping_from_dict`` cc=21) +
# ``.local/research/v12.4.0_nines_deep_bullets.json`` (finding for
# ``_collapse_block`` cc=25).
# ---------------------------------------------------------------------------
_V12_4_0_COMMANDS_FILE: Path = Path("src/devolaflow/shell_proxy/commands.py")
_V12_4_0_BULLETS_FILE: Path = Path("src/devolaflow/writing_style/transforms/bullets.py")
_V12_4_0_BUILD_MAPPING_HELPERS: tuple[str, ...] = (
    "_validate_schema_version",
    "_validate_scalar_fields",
    "_validate_tags",
    "_build_filter_lists",
)
_V12_4_0_COLLAPSE_BLOCK_HELPERS: tuple[str, ...] = (
    "_classify_block_lines",
    "_validate_bullet_constraints",
    "_collapse_no_intro",
    "_collapse_with_intro",
)
# Byte-identical public signature of ``build_mapping_from_dict`` per
# the v12.4.0 PV-04 D-3 acceptance criterion (4) — must match the
# literal in ``tests/test_v12_4_0_complexity_targets.py::_BUILD_MAPPING_SIGNATURE``
# verbatim. The two pins reference the same source-of-truth surface.
_V12_4_0_BUILD_MAPPING_SIGNATURE_LITERAL: str = (
    "def build_mapping_from_dict(\n"
    "    payload: Any,\n"
    "    *,\n"
    '    source_path: str = "<command-mapping.yaml>",\n'
    '    recipe_id: str = "",\n'
    ") -> CommandMapping:"
)
# Byte-identical private signature of ``_collapse_block`` — the
# orchestrator inside ``bullets.py`` is module-private but stable.
_V12_4_0_COLLAPSE_BLOCK_SIGNATURE_LITERAL: str = (
    "def _collapse_block(lines: list[str]) -> list[str]:"
)


def test_v12_4_0_complexity_sweep_complete(project_root: Path) -> None:
    """W-18 v12.4.0 PV-04 D-3: ``build_mapping_from_dict`` cc=21 + ``_collapse_block`` cc=25 → ≤ 10.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the PV-04 cc-spike refactor pair. The stanza asserts
    three load-bearing surfaces (mirroring the PV-03 stanza pattern):

    (a) Every helper symbol is present at module scope in
    ``src/devolaflow/shell_proxy/commands.py`` (4 ``_validate_*`` /
    ``_build_*`` helpers) and
    ``src/devolaflow/writing_style/transforms/bullets.py`` (4 helpers).
    Without these 8 symbols the cc reduction did NOT happen and the
    CHANGELOG entry would be a ghost feature per S-4.

    (b) Both public signatures are byte-identical to the pre-refactor
    forms. The CO-2 / C-3 no-API-break invariant pins:
      * ``def build_mapping_from_dict(payload, *, source_path, recipe_id) -> CommandMapping:``
        (consumed by the loader + 68 commands tests + apply_local_recipe)
      * ``def _collapse_block(lines: list[str]) -> list[str]:``
        (consumed by ``_transform_prose`` + the 27 writing_style fixture tests)
    Any reorder / rename / default-change is a release blocker.

    (c) The companion test file
    ``tests/test_v12_4_0_complexity_targets.py`` exists with the cc-pin
    tests (orchestrator ≤ cc=10 per target, per-helper ≤ cc=8
    parametrize, signature byte-identical literal match for both
    targets, and the cross-PV regression guard for ``evaluate_gate``).
    The companion file is what catches a future PV re-bloating any of
    the 3 targeted orchestrators — without it the W-18 / W-4 / SI-4
    safety net has a hole.

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3 +
    ``.local/research/v12.4.0_nines_deep_commands.json`` (finding for
    ``build_mapping_from_dict`` cc=21) +
    ``.local/research/v12.4.0_nines_deep_bullets.json`` (finding for
    ``_collapse_block`` cc=25); the W-18 sequencing rule is at
    ``.cursor/rules/repo-governance.mdc`` §W-18.
    """
    # --- (a.1) build_mapping_from_dict helpers in commands.py ----------
    commands_path = project_root / _V12_4_0_COMMANDS_FILE
    assert commands_path.is_file(), (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_COMMANDS_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical commands "
        "module per the PV-04 owned-files manifest item 1."
    )
    commands_text = commands_path.read_text(encoding="utf-8")
    for helper_name in _V12_4_0_BUILD_MAPPING_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in commands_text, (
            f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_COMMANDS_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``build_mapping_from_dict`` cc from 21 to 9; "
            "if this assertion fires, the refactor was either reverted or "
            "never applied. Expected helper signatures are documented at "
            "``.local/research/v12.4.0_gap_analysis.md`` §2 D-3."
        )

    # --- (a.2) _collapse_block helpers in bullets.py -------------------
    bullets_path = project_root / _V12_4_0_BULLETS_FILE
    assert bullets_path.is_file(), (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_BULLETS_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical bullets "
        "transform module per the PV-04 owned-files manifest item 2."
    )
    bullets_text = bullets_path.read_text(encoding="utf-8")
    for helper_name in _V12_4_0_COLLAPSE_BLOCK_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in bullets_text, (
            f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_BULLETS_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``_collapse_block`` cc from 25 to 6; if this "
            "assertion fires, the refactor was either reverted or never "
            "applied. Expected helper signatures are documented at "
            "``.local/research/v12.4.0_gap_analysis.md`` §2 D-3."
        )

    # --- (b.1) build_mapping_from_dict public signature byte-identical -
    assert _V12_4_0_BUILD_MAPPING_SIGNATURE_LITERAL in commands_text, (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_COMMANDS_FILE} has drifted "
        "the public ``build_mapping_from_dict`` signature from the "
        "pre-refactor form. The CO-2 / C-3 no-API-break invariant requires "
        "byte-identical preservation of the entire signature. Expected "
        f"literal:\n\n{_V12_4_0_BUILD_MAPPING_SIGNATURE_LITERAL}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``recipe_id`` with a default value (additive change) — do NOT "
        "reorder existing parameters or change defaults."
    )

    # --- (b.2) _collapse_block private signature byte-identical --------
    assert _V12_4_0_COLLAPSE_BLOCK_SIGNATURE_LITERAL in bullets_text, (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_BULLETS_FILE} has drifted "
        "the ``_collapse_block`` signature from the pre-refactor form. "
        "Per CO-2 / C-3 the in-module orchestrator's signature MUST stay "
        "byte-identical so ``_transform_prose`` + the 27 fixture-corpus "
        f"tests keep working. Expected literal:\n\n"
        f"{_V12_4_0_COLLAPSE_BLOCK_SIGNATURE_LITERAL}"
    )

    # --- (c) companion cc-pin test file -------------------------------
    pv04_complexity_test_path = project_root / Path("tests/test_v12_4_0_complexity_targets.py")
    assert pv04_complexity_test_path.is_file(), (
        "W-18 v12.4.0 PV-04 violation: tests/test_v12_4_0_complexity_targets.py "
        "missing — release blocker. The companion cc-pin test file guards "
        "against future re-bloat of ``build_mapping_from_dict``, "
        "``_collapse_block``, AND ``evaluate_gate`` (cross-PV regression "
        "guard) per the PV-04 owned-files manifest item 5."
    )
    pv04_complexity_test_text = pv04_complexity_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_build_mapping_from_dict_cc_under_ceiling",
        "test_build_mapping_helpers_cc_under_ceiling",
        "test_build_mapping_from_dict_signature_byte_identical",
        "test_collapse_block_cc_under_ceiling",
        "test_collapse_block_helpers_cc_under_ceiling",
        "test_collapse_block_signature_byte_identical",
        "test_evaluate_gate_cc_under_ceiling_v12_4_0_pv04_regression_guard",
    ):
        assert f"def {expected_test}" in pv04_complexity_test_text, (
            f"W-18 v12.4.0 PV-04 violation: "
            f"tests/test_v12_4_0_complexity_targets.py missing test function "
            f"``{expected_test}``. The 7-function contract (3 for "
            "build_mapping_from_dict + 3 for _collapse_block + 1 cross-PV "
            "regression guard for evaluate_gate) is documented in the PV-04 "
            "owned-files manifest item 5."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.4.0 PV-05 D-4 — L0-only surfaces hardening
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the PV-05 L0-only surfaces leak cluster. This
# stanza pins the v12.4.0 PV-05 surface (closes the 派发分层 user-feedback
# theme from .local/feedbacks/feedback_for_v12.1.1.md):
#
# * NEW lifecycle hook ``src/devolaflow/lifecycle/reject_subagent_banner_emission.py``
#   exists with the canonical EVENT constant + the
#   ``reject_subagent_banner_emission`` handler symbol + the opt-in
#   ``register_pre_dispatch_extra`` helper. The hook is OPT-IN only — NOT
#   auto-wired in lifecycle/__init__.py — preserving the S-10 byte-id
#   contract for v12.3.0 callers.
# * SKILL.md §"Session Banner Contract (v12.3.0+)" carries the NEW PV-05
#   prohibition line citing ``reject_subagent_banner_emission`` (verbatim
#   substring).
# * references/agent-workspace.md carries the NEW §"Handoff Envelope L0-only
#   Metadata Stripping" subsection documenting the 4 literal classes the
#   handoff writer MUST strip (banner workflow-start + banner workflow-end
#   + 📊 footer + operational_learnings session-pinned literals).
# * tests/test_l0_only_section_priorities.py exists pinning the 3-section ×
#   24-profile audit verdict (task_quality_score: skip everywhere,
#   operational_learnings: skip everywhere, version_update: skip everywhere
#   except self_update: critical).
# * tests/test_lifecycle_reject_subagent_banner_emission.py exists with the
#   ≥ 8 hook tests covering permissive default + strict mode + non-target-
#   layer skip + opt-in registration + literal detection + defensive
#   non-dict + nested-banner-exclusion + S-10 default-events preservation.
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-4 +
# ``.local/research/v12.4.0_l0_only_audit.md`` §§A-C (per-profile audit
# table + literal enumeration + token-savings estimate) +
# ``.local/feedbacks/feedback_for_v12.1.1.md`` themes 打分体系 + 版本模块 +
# 派发分层.
# ---------------------------------------------------------------------------
_V12_4_0_PV05_HOOK_FILE: Path = Path("src/devolaflow/lifecycle/reject_subagent_banner_emission.py")
_V12_4_0_PV05_HOOK_TEST_FILE: Path = Path("tests/test_lifecycle_reject_subagent_banner_emission.py")
_V12_4_0_PV05_PRIORITIES_TEST_FILE: Path = Path("tests/test_l0_only_section_priorities.py")
_V12_4_0_PV05_SKILL_FILE: Path = Path("workflow-system/agent/SKILL.md")
_V12_4_0_PV05_AGENT_WORKSPACE_FILE: Path = Path(
    "workflow-system/agent/references/agent-workspace.md"
)
_V12_4_0_PV05_CONTEXT_PROFILES_FILE: Path = Path("workflow-system/agent/context_profiles.yaml")
_V12_4_0_PV05_SKILL_PROHIBITION_LITERAL: str = (
    "Subagent (L1/L2/L3) reports MUST NOT include banner lines — see "
    "PV-05 runtime hook `reject_subagent_banner_emission`. Banners are "
    "L0-only operator chat output."
)
_V12_4_0_PV05_AGENT_WORKSPACE_HEADING: str = (
    "### Handoff Envelope L0-only Metadata Stripping (v12.4.0 PV-05)"
)
_V12_4_0_PV05_AGENT_WORKSPACE_CROSS_LINK: str = "`reject_subagent_banner_emission`"
_V12_4_0_PV05_HOOK_MIN_TESTS: int = 8


def test_v12_4_0_l0_only_surfaces_hardened(project_root: Path) -> None:
    """W-18 v12.4.0 PV-05 D-4: L0-only surfaces leak cluster hardening.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the PV-05 L0-only surfaces hardening. The stanza
    asserts four load-bearing surfaces:

    (a) NEW lifecycle hook module
    ``src/devolaflow/lifecycle/reject_subagent_banner_emission.py``
    exists with the canonical EVENT constant + the
    ``reject_subagent_banner_emission`` handler symbol + the opt-in
    ``register_pre_dispatch_extra`` helper. Without these symbols
    the CHANGELOG entry would be a ghost feature per S-4.

    (b) SKILL.md §"Session Banner Contract" carries the NEW PV-05
    prohibition line citing the runtime hook by name (verbatim
    substring match). Without this line, the CHANGELOG entry's
    operator-facing reinforcement is unbacked.

    (c) references/agent-workspace.md carries the NEW
    §"Handoff Envelope L0-only Metadata Stripping" subsection +
    cross-link to the runtime hook. Without this subsection, the
    handoff-writer normative obligation is undocumented.

    (d) The companion test files
    ``tests/test_l0_only_section_priorities.py`` (5 tests pinning
    the 3-section × 24-profile audit verdict) and
    ``tests/test_lifecycle_reject_subagent_banner_emission.py`` (≥ 8
    tests covering hook permissive/strict + wiring + edge cases)
    BOTH exist with the required test-function counts. Without these
    files the W-18 / W-9 SI-10 safety net has a hole.

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-4 +
    ``.local/research/v12.4.0_l0_only_audit.md`` §§A-C +
    ``.local/feedbacks/feedback_for_v12.1.1.md`` (派发分层 theme).
    """
    # --- (a.1) Lifecycle hook module exists --------------------------
    hook_path = project_root / _V12_4_0_PV05_HOOK_FILE
    assert hook_path.is_file(), (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        "missing — release blocker. The PV-05 hook implementation MUST "
        "land per the PV-05 owned-files manifest Surface 5.2."
    )
    hook_text = hook_path.read_text(encoding="utf-8")
    assert 'EVENT = "pre_dispatch"' in hook_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        'missing the canonical `EVENT = "pre_dispatch"` constant.'
    )
    assert "def reject_subagent_banner_emission(" in hook_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        "missing the canonical `reject_subagent_banner_emission` "
        "function definition."
    )
    assert "def register_pre_dispatch_extra(" in hook_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        "missing the opt-in `register_pre_dispatch_extra` helper. The "
        "PV-05 contract is OPT-IN registration to preserve the S-10 "
        "byte-id contract for v12.3.0 callers — without this helper "
        "operators have no way to wire the hook at runtime."
    )

    # --- (a.2) S-10 byte-id contract preservation --------------------
    init_path = project_root / Path("src/devolaflow/lifecycle/__init__.py")
    init_text = init_path.read_text(encoding="utf-8")
    assert "register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)" not in init_text, (
        "W-18 v12.4.0 PV-05 S-10 violation: "
        "`reject_subagent_banner_emission` MUST NOT be auto-wired in "
        "lifecycle/__init__.py — the hook is OPT-IN only via "
        "`register_pre_dispatch_extra()` per the PV-05 S-10 byte-id "
        "contract preservation discipline. Auto-wiring would break "
        "byte-identical default-handler behaviour for v12.3.0 callers."
    )

    # --- (b) SKILL.md prohibition line -------------------------------
    skill_path = project_root / _V12_4_0_PV05_SKILL_FILE
    skill_text = skill_path.read_text(encoding="utf-8")
    assert _V12_4_0_PV05_SKILL_PROHIBITION_LITERAL in skill_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_SKILL_FILE} "
        "missing the §'Session Banner Contract' prohibition line. "
        f"Expected verbatim substring:\n\n"
        f"{_V12_4_0_PV05_SKILL_PROHIBITION_LITERAL}\n\n"
        "Without this line the operator-facing reinforcement of the "
        "PV-05 runtime hook is unbacked."
    )

    # --- (c.1) agent-workspace.md new subsection heading -------------
    agent_workspace_path = project_root / _V12_4_0_PV05_AGENT_WORKSPACE_FILE
    agent_workspace_text = agent_workspace_path.read_text(encoding="utf-8")
    assert _V12_4_0_PV05_AGENT_WORKSPACE_HEADING in agent_workspace_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_AGENT_WORKSPACE_FILE} "
        "missing the §'Handoff Envelope L0-only Metadata Stripping' "
        "subsection heading. Expected verbatim heading:\n\n"
        f"{_V12_4_0_PV05_AGENT_WORKSPACE_HEADING}\n\n"
        "Without this subsection the handoff-writer normative "
        "obligation is undocumented."
    )

    # --- (c.2) agent-workspace.md cross-link to runtime hook ---------
    assert _V12_4_0_PV05_AGENT_WORKSPACE_CROSS_LINK in agent_workspace_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_AGENT_WORKSPACE_FILE} "
        "missing the cross-link to the runtime hook "
        f"({_V12_4_0_PV05_AGENT_WORKSPACE_CROSS_LINK}). The new subsection "
        "MUST cross-reference the implementation surface."
    )

    # --- (d.1) section-priorities test file exists -------------------
    priorities_test_path = project_root / _V12_4_0_PV05_PRIORITIES_TEST_FILE
    assert priorities_test_path.is_file(), (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_PRIORITIES_TEST_FILE} "
        "missing — release blocker. The PV-05 section-priority audit "
        "pin MUST land per the PV-05 owned-files manifest T2."
    )
    priorities_test_text = priorities_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_version_update_skip_for_all_subagent_profiles",
        "test_task_quality_score_skip_for_all_subagent_profiles",
        "test_operational_learnings_explicit_skip_for_all_profiles",
        "test_operational_learnings_registered_in_sections_block",
        "test_all_24_profiles_have_l0_only_skip_discipline",
    ):
        assert f"def {expected_test}" in priorities_test_text, (
            f"W-18 v12.4.0 PV-05 violation: "
            f"{_V12_4_0_PV05_PRIORITIES_TEST_FILE} missing test function "
            f"``{expected_test}``. The 5-function contract pinning the "
            "audit §A.1 + §A.2 + §A.3 + sections-block registration + "
            "cross-profile composite is documented in the PV-05 "
            "owned-files manifest T2."
        )

    # --- (d.2) hook test file exists with the required test count ---
    hook_test_path = project_root / _V12_4_0_PV05_HOOK_TEST_FILE
    assert hook_test_path.is_file(), (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_TEST_FILE} "
        "missing — release blocker. The PV-05 hook test suite MUST "
        "land per the PV-05 owned-files manifest T1."
    )
    hook_test_module = ast.parse(hook_test_path.read_text(encoding="utf-8"))
    hook_test_count = sum(
        1
        for node in hook_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    )
    assert hook_test_count >= _V12_4_0_PV05_HOOK_MIN_TESTS, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_TEST_FILE} "
        f"declares {hook_test_count} test functions; PV-05 dispatch "
        f"requires >= {_V12_4_0_PV05_HOOK_MIN_TESTS} (permissive + "
        "strict + non-target-layer skip + opt-in wiring + literal "
        "detection + defensive non-dict + nested-banner-exclusion + "
        "S-10 default-events preservation)."
    )

    # --- (d.3) context_profiles.yaml carries the registration -------
    profiles_path = project_root / _V12_4_0_PV05_CONTEXT_PROFILES_FILE
    profiles_text = profiles_path.read_text(encoding="utf-8")
    assert "operational_learnings:" in profiles_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_CONTEXT_PROFILES_FILE} "
        "missing the `operational_learnings:` registration in the "
        "`sections:` block. Per audit §A.3, the registration is what "
        "closes the silent-fallback S-5 violation; without it the "
        "DeprecationWarning storm persists."
    )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-02 D-2 — cc-spike sweep carry-over
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the PV-02 cc-spike sweep. This stanza pins the
# v12.5.0 PV-02 surface (closes the v12.4.0 retro §6 telegraph item 1):
#
# * 4 helpers extracted from ``load_command_mappings`` (was cc=18 per
#   ``.local/research/v12.4.0_nines_deep_commands.json`` warning-tier
#   finding) into ``_resolve_commands_root`` + ``_load_recipe_payload`` +
#   ``_filter_recipe_freshness`` + ``_should_keep_recipe``.
# * 2 helpers extracted from ``apply_local_recipe`` (was cc=17 per the
#   same NineS finding) into ``_resolve_apply_inputs`` (folding the 5
#   early-return decisions) + ``_apply_recipe_transform`` (folding the
#   strip-ansi → pre/post filter → truncate → on-empty pipeline).
# * Both public signatures byte-identical to the pre-refactor forms.
# * Companion cc-pin file ``tests/test_v12_5_0_complexity_targets.py``
#   exists with the 7 cc-pin tests (orchestrator ≤ cc=10 per target,
#   per-helper ≤ cc=8 parametrize, signature byte-identical literal
#   match for both targets, all-helpers-present sentinel).
#
# Source: ``.local/research/v12.5.0_gap_analysis.md`` §2 D-2 +
# ``.local/research/v12.4.0_retrospective.md`` §6 telegraph item 1 +
# ``tests/test_v12_5_0_complexity_targets.py`` (the companion cc-pin
# file). The W-18 sequencing rule is at
# ``.cursor/rules/repo-governance.mdc`` §W-18.
# ---------------------------------------------------------------------------
_V12_5_0_COMMANDS_FILE: Path = Path("src/devolaflow/shell_proxy/commands.py")
_V12_5_0_LOAD_MAPPINGS_HELPERS: tuple[str, ...] = (
    "_resolve_commands_root",
    "_load_recipe_payload",
    "_filter_recipe_freshness",
    "_should_keep_recipe",
)
_V12_5_0_APPLY_RECIPE_HELPERS: tuple[str, ...] = (
    "_resolve_apply_inputs",
    "_apply_recipe_transform",
)
_V12_5_0_LOAD_MAPPINGS_SIGNATURE_LITERAL: str = (
    "def load_command_mappings(\n"
    "    *,\n"
    "    commands_dir: Path | str | None = None,\n"
    "    repo_signal: str | None = None,\n"
    "    env: dict[str, str] | None = None,\n"
    "    current_version: str | None = None,\n"
    ") -> dict[str, CommandMapping]:"
)
_V12_5_0_APPLY_RECIPE_SIGNATURE_LITERAL: str = (
    "def apply_local_recipe(\n"
    "    cmd: str,\n"
    "    output: str,\n"
    "    *,\n"
    "    mappings: dict[str, CommandMapping] | None = None,\n"
    "    env: dict[str, str] | None = None,\n"
    "    commands_dir: Path | str | None = None,\n"
    "    repo_signal: str | None = None,\n"
    ") -> tuple[str, bool]:"
)


def test_v12_5_0_cc_spike_sweep_complete(project_root: Path) -> None:
    """W-18 v12.5.0 PV-02 D-2: ``load_command_mappings`` + ``apply_local_recipe`` cc-spike sweep.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the PV-02 cc-spike sweep. The stanza asserts three
    load-bearing surfaces (mirroring the v12.4.0 PV-04 stanza pattern):

    (a) Every helper symbol is present at module scope in
    ``src/devolaflow/shell_proxy/commands.py`` — 4 ``_resolve_*`` /
    ``_load_*`` / ``_filter_*`` / ``_should_*`` helpers for
    ``load_command_mappings`` AND 2 helpers for ``apply_local_recipe``
    (``_resolve_apply_inputs`` + ``_apply_recipe_transform``). Without
    these 6 symbols the cc reduction did NOT happen and the CHANGELOG
    entry would be a ghost feature per S-4.

    (b) Both public signatures are byte-identical to the pre-refactor
    forms. The CO-2 / C-3 no-API-break invariant pins:
      * ``def load_command_mappings(*, commands_dir, repo_signal, env,
        current_version) -> dict[str, CommandMapping]:`` (consumed by
        ``apply_local_recipe`` + the proxy + the compression-pipeline
        stage + every ``tests/test_shell_proxy_*`` fixture)
      * ``def apply_local_recipe(cmd, output, *, mappings, env,
        commands_dir, repo_signal) -> tuple[str, bool]:`` (the public
        API consumed by the proxy + the compression-pipeline stage)
    Any reorder / rename / default-change is a release blocker.

    (c) The companion test file
    ``tests/test_v12_5_0_complexity_targets.py`` exists with the cc-pin
    tests (orchestrator ≤ cc=10 per target, per-helper ≤ cc=8
    parametrize, signature byte-identical literal match for both
    targets, all-helpers-present sentinel).

    Source: ``.local/research/v12.5.0_gap_analysis.md`` §2 D-2 +
    ``.local/research/v12.4.0_nines_deep_commands.json`` (NineS deep
    finding for ``load_command_mappings`` cc=16 + ``apply_local_recipe``
    cc=16 — both warning-tier deferred from v12.4.0 to v12.5.0); the
    W-18 sequencing rule is at
    ``.cursor/rules/repo-governance.mdc`` §W-18.
    """
    # --- (a.1) load_command_mappings helpers in commands.py ------------
    commands_path = project_root / _V12_5_0_COMMANDS_FILE
    assert commands_path.is_file(), (
        f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical commands "
        "module per the PV-02 owned-files manifest item 1."
    )
    commands_text = commands_path.read_text(encoding="utf-8")
    for helper_name in _V12_5_0_LOAD_MAPPINGS_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in commands_text, (
            f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``load_command_mappings`` cc from 18 to 9; if "
            "this assertion fires, the refactor was either reverted or never "
            "applied. Expected helper signatures are documented at "
            "``.local/research/v12.5.0_gap_analysis.md`` §2 D-2."
        )

    # --- (a.2) apply_local_recipe helpers in commands.py --------------
    for helper_name in _V12_5_0_APPLY_RECIPE_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in commands_text, (
            f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} missing "
            f"helper function ``{helper_name}``. The 2-helper decomposition "
            "is what brings ``apply_local_recipe`` cc from 17 to 4; if this "
            "assertion fires, the refactor was either reverted or never "
            "applied."
        )

    # --- (b.1) load_command_mappings signature byte-identical ---------
    assert _V12_5_0_LOAD_MAPPINGS_SIGNATURE_LITERAL in commands_text, (
        f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} has drifted "
        "the public ``load_command_mappings`` signature. The CO-2 / C-3 "
        "no-API-break invariant requires byte-identical preservation. "
        f"Expected literal:\n\n{_V12_5_0_LOAD_MAPPINGS_SIGNATURE_LITERAL}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``current_version`` with a default value (additive change)."
    )

    # --- (b.2) apply_local_recipe signature byte-identical ------------
    assert _V12_5_0_APPLY_RECIPE_SIGNATURE_LITERAL in commands_text, (
        f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} has drifted "
        "the public ``apply_local_recipe`` signature. Per CO-2 / C-3 the "
        "API surface MUST stay byte-identical so the proxy + the "
        "compression-pipeline stage + every fixture test keeps working. "
        f"Expected literal:\n\n{_V12_5_0_APPLY_RECIPE_SIGNATURE_LITERAL}"
    )

    # --- (c) companion cc-pin test file -------------------------------
    pv02_complexity_test_path = project_root / Path("tests/test_v12_5_0_complexity_targets.py")
    assert pv02_complexity_test_path.is_file(), (
        "W-18 v12.5.0 PV-02 violation: tests/test_v12_5_0_complexity_targets.py "
        "missing — release blocker. The companion cc-pin test file guards "
        "against future re-bloat of ``load_command_mappings`` AND "
        "``apply_local_recipe`` per the PV-02 owned-files manifest item 4."
    )
    pv02_complexity_test_text = pv02_complexity_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_load_command_mappings_cc_under_ceiling",
        "test_load_command_mappings_helpers_cc_under_ceiling",
        "test_load_command_mappings_signature_byte_identical",
        "test_apply_local_recipe_cc_under_ceiling",
        "test_apply_local_recipe_helpers_cc_under_ceiling",
        "test_apply_local_recipe_signature_byte_identical",
        "test_v12_5_0_pv02_helpers_all_present",
    ):
        assert f"def {expected_test}" in pv02_complexity_test_text, (
            f"W-18 v12.5.0 PV-02 violation: "
            f"tests/test_v12_5_0_complexity_targets.py missing test function "
            f"``{expected_test}``. The 7-function contract (3 for "
            "load_command_mappings + 3 for apply_local_recipe + 1 sentinel) "
            "is documented in the PV-02 owned-files manifest item 4."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-03 D-1.1 — codegraph plugin landing
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the codegraph plugin. This stanza pins the
# v12.5.0 PV-03 D-1.1 surface (closes the v12.4.0 retro §3 BLOCKER feedback
# item: "codegraph integration is the primary deliverable for v12.5.0"):
#
# * workflow-system/agent/plugins.yaml carries the `codegraph:` block
#   under `plugins:` with the 8 capabilities + `code_intelligence` role +
#   the 4 stage_mapping recipes (analyze/scaffold/research/impact).
# * workflow-system/agent/plugins.yaml `plugin_roles:` carries the NEW
#   `code_intelligence:` block (5th role) with provider=codegraph.
# * workflow-system/agent/knowledge/runtime-plugins.yaml `plugins:` list
#   carries the `id: codegraph` entry with backend=npm_then_init.
# * workflow-system/agent/knowledge/reference-dependencies.yaml
#   `active_tracking:` list (12th entry) carries the codegraph reference
#   pin for the W-2 / SI-2 reference review cycle.
# * src/devolaflow/codegraph/ package exists with __init__.py + _cli.py
#   (run_codegraph_cli + CodegraphUnavailableError) + researcher.py (5
#   public helpers: build_context, search_symbols, get_impact,
#   get_callers, get_affected_tests).
# * Companion test files tests/test_codegraph.py + the 6 new
#   TestV1250CodegraphRegistration tests in tests/test_plugins.py + the
#   codegraph entry in tests/test_runtime_plugins_smoke.py exist.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-1 +
# .local/research/v12.5.0_codegraph_benefit_analysis.md §3 (5-surface
# architecture) + §6.1 PV-03 acceptance criteria. The W-18 sequencing
# rule is at .cursor/rules/repo-governance.mdc §W-18.
# ---------------------------------------------------------------------------
_V12_5_0_PV03_PLUGINS_FILE: Path = Path("workflow-system/agent/plugins.yaml")
_V12_5_0_PV03_RUNTIME_FILE: Path = Path("workflow-system/agent/knowledge/runtime-plugins.yaml")
_V12_5_0_PV03_REFERENCES_FILE: Path = Path(
    "workflow-system/agent/knowledge/reference-dependencies.yaml"
)
_V12_5_0_PV03_PACKAGE_DIR: Path = Path("src/devolaflow/codegraph")
_V12_5_0_PV03_PACKAGE_FILES: tuple[str, ...] = (
    "__init__.py",
    "_cli.py",
    "researcher.py",
)
_V12_5_0_PV03_RESEARCHER_PUBLIC_HELPERS: tuple[str, ...] = (
    "build_context",
    "search_symbols",
    "get_impact",
    "get_callers",
    "get_affected_tests",
)


def test_v12_5_0_codegraph_plugin_registered(project_root: Path) -> None:
    """W-18 v12.5.0 PV-03 D-1.1: codegraph plugin landed across 3 registries + Python wrapper.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the codegraph plugin. The stanza asserts five
    load-bearing surfaces:

    (a) plugins.yaml carries the codegraph block + code_intelligence role.
    (b) runtime-plugins.yaml carries the codegraph entry under `plugins:`.
    (c) reference-dependencies.yaml carries the 12th active_tracking entry.
    (d) src/devolaflow/codegraph/ package exists with the 3 expected files.
    (e) Companion test files tests/test_codegraph.py +
        tests/test_plugins.py::TestV1250CodegraphRegistration +
        tests/test_runtime_plugins_smoke.py::test_codegraph_runtime_entry_smoke
        exist.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.
    """
    import yaml

    # --- (a) plugins.yaml: codegraph block + code_intelligence role ---
    plugins_path = project_root / _V12_5_0_PV03_PLUGINS_FILE
    assert plugins_path.is_file(), (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_PLUGINS_FILE} missing — release blocker."
    )
    plugins_payload = yaml.safe_load(plugins_path.read_text(encoding="utf-8"))
    plugins = plugins_payload.get("plugins") or {}
    assert "codegraph" in plugins, (
        "W-18 v12.5.0 PV-03 violation: plugins.yaml missing top-level "
        "`codegraph` block under `plugins:`. The block is the canonical "
        "plugin catalog declaration per A-5 SSOT registry pattern."
    )
    codegraph = plugins["codegraph"]
    assert codegraph.get("role") == "code_intelligence"
    assert codegraph.get("min_version") == "0.9.3"
    assert codegraph.get("repo_url") == "https://github.com/colbymchenry/codegraph"
    plugin_roles = plugins_payload.get("plugin_roles") or {}
    assert "code_intelligence" in plugin_roles, (
        "W-18 v12.5.0 PV-03 violation: plugins.yaml missing "
        "`plugin_roles.code_intelligence` block. The 5th role MUST exist."
    )

    # --- (b) runtime-plugins.yaml: codegraph entry --------------------
    runtime_path = project_root / _V12_5_0_PV03_RUNTIME_FILE
    runtime_payload = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    runtime_plugins = runtime_payload.get("plugins") or []
    runtime_ids = {p.get("id") for p in runtime_plugins if isinstance(p, dict)}
    assert "codegraph" in runtime_ids, (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_RUNTIME_FILE} missing "
        "the `id: codegraph` entry under `plugins:` list."
    )

    # --- (c) reference-dependencies.yaml: 12th active_tracking entry --
    refs_path = project_root / _V12_5_0_PV03_REFERENCES_FILE
    refs_payload = yaml.safe_load(refs_path.read_text(encoding="utf-8"))
    active = refs_payload.get("active_tracking") or []
    active_ids = {entry.get("id") for entry in active if isinstance(entry, dict)}
    assert "codegraph" in active_ids, (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_REFERENCES_FILE} "
        "missing the `id: codegraph` entry under `active_tracking:` list. "
        "The reference pin enables the W-2 / SI-2 reference review cycle "
        "to track upstream codegraph version drift."
    )

    # --- (d) Python wrapper package files -----------------------------
    package_dir = project_root / _V12_5_0_PV03_PACKAGE_DIR
    assert package_dir.is_dir(), (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_PACKAGE_DIR} missing — "
        "release blocker. The Python wrapper package is the canonical "
        "consumer-facing surface for codegraph CLI invocations."
    )
    for fname in _V12_5_0_PV03_PACKAGE_FILES:
        assert (package_dir / fname).is_file(), (
            f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_PACKAGE_DIR}/{fname} "
            "missing — release blocker per the package skeleton contract."
        )
    init_text = (package_dir / "__init__.py").read_text(encoding="utf-8")
    for helper in _V12_5_0_PV03_RESEARCHER_PUBLIC_HELPERS:
        assert f'"{helper}"' in init_text, (
            f"W-18 v12.5.0 PV-03 violation: __init__.py __all__ missing "
            f"public helper {helper!r}. The 5 researcher helpers are the "
            "v12.5.0 PV-03 D-1.1 contract surface."
        )

    # --- (e) Companion test files -------------------------------------
    codegraph_tests = project_root / Path("tests/test_codegraph.py")
    assert codegraph_tests.is_file(), (
        "W-18 v12.5.0 PV-03 violation: tests/test_codegraph.py missing — "
        "release blocker. The companion test file pins the wrapper "
        "package contract (subprocess mocking + degraded-mode + "
        "structured-error)."
    )
    plugins_tests = project_root / Path("tests/test_plugins.py")
    plugins_text = plugins_tests.read_text(encoding="utf-8")
    assert "TestV1250CodegraphRegistration" in plugins_text, (
        "W-18 v12.5.0 PV-03 violation: tests/test_plugins.py missing the "
        "TestV1250CodegraphRegistration class with the 6 plugin-registry "
        "pin tests."
    )
    runtime_tests = project_root / Path("tests/test_runtime_plugins_smoke.py")
    runtime_text = runtime_tests.read_text(encoding="utf-8")
    assert "test_codegraph_runtime_entry_smoke" in runtime_text, (
        "W-18 v12.5.0 PV-03 violation: tests/test_runtime_plugins_smoke.py "
        "missing the test_codegraph_runtime_entry_smoke test pinning the "
        "runtime plugin entry."
    )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-04 D-1.2 — codegraph workflow wiring
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the codegraph workflow wiring. This stanza
# pins the v12.5.0 PV-04 D-1.2 surface (closes the codegraph integration's
# template-side surface):
#
# * repo-init.yaml: analyze.config.codegraph_commands + scaffold.config.
#   codegraph_init (with on_failure: warn + add_to_gitignore: [.codegraph/])
#   + verify.config.codegraph_smoke (mode=full only).
# * onboarding.yaml: analyze.config.codegraph_commands.
# * security-audit.yaml: analyze.config.codegraph_commands (callers + impact).
# * product-verification.yaml: analyze.config.codegraph_commands (explore + impact).
# * context_profiles.yaml: meta.codegraph_integration block (parallel to
#   meta.nines_integration) with 5 commands recipes + 6 triggers.
# * Companion test file tests/test_codegraph_workflow_wiring.py with the
#   12 structural assertion tests.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.2 +
# .local/research/v12.5.0_codegraph_benefit_analysis.md §3 surface 5 +
# §6.2 PV-04 acceptance criteria.
# ---------------------------------------------------------------------------
_V12_5_0_PV04_REPO_INIT_FILE: Path = Path("workflow-system/agent/templates/builtin/repo-init.yaml")
_V12_5_0_PV04_ONBOARDING_FILE: Path = Path(
    "workflow-system/agent/templates/builtin/onboarding.yaml"
)
_V12_5_0_PV04_SECURITY_FILE: Path = Path(
    "workflow-system/agent/templates/builtin/security-audit.yaml"
)
_V12_5_0_PV04_PROD_VERIF_FILE: Path = Path(
    "workflow-system/agent/templates/builtin/product-verification.yaml"
)
_V12_5_0_PV04_CONTEXT_PROFILES_FILE: Path = Path("workflow-system/agent/context_profiles.yaml")


def test_v12_5_0_codegraph_workflow_wired(project_root: Path) -> None:
    """W-18 v12.5.0 PV-04 D-1.2: codegraph wired across 4 templates + context profile.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the codegraph workflow wiring. The stanza asserts six
    load-bearing surfaces:

    (a) repo-init.yaml carries 3 codegraph surfaces (analyze hint +
        scaffold init sub-step + verify smoke check).
    (b) onboarding.yaml analyze stage carries codegraph_commands.
    (c) security-audit.yaml analyze stage carries codegraph_commands.
    (d) product-verification.yaml analyze stage carries codegraph_commands.
    (e) context_profiles.yaml carries meta.codegraph_integration block.
    (f) Companion test file tests/test_codegraph_workflow_wiring.py exists
        with the 12 structural assertion tests.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.2.
    """
    import yaml

    # --- (a) repo-init.yaml — 3 codegraph surfaces -------------------
    repo_init_text = (project_root / _V12_5_0_PV04_REPO_INIT_FILE).read_text(encoding="utf-8")
    for literal in (
        "codegraph_commands:",
        "codegraph_init:",
        "codegraph init {project_root}",
        ".codegraph/",
        "codegraph_smoke:",
    ):
        assert literal in repo_init_text, (
            f"W-18 v12.5.0 PV-04 violation: {_V12_5_0_PV04_REPO_INIT_FILE} "
            f"missing required literal {literal!r}. The 3 codegraph "
            "surfaces (analyze hint + scaffold init + verify smoke) MUST "
            "be present per the cycle plan §PV-04 deliverable list."
        )

    # --- (b)-(d) sister templates — analyze.codegraph_commands -------
    for path in (
        _V12_5_0_PV04_ONBOARDING_FILE,
        _V12_5_0_PV04_SECURITY_FILE,
        _V12_5_0_PV04_PROD_VERIF_FILE,
    ):
        text = (project_root / path).read_text(encoding="utf-8")
        assert "codegraph_commands:" in text, (
            f"W-18 v12.5.0 PV-04 violation: {path} missing "
            "`codegraph_commands:` literal under the analyze stage's "
            "config block. The 3 sister templates MUST gain codegraph "
            "wiring per the cycle plan §PV-04 deliverable list."
        )

    # --- (e) context_profiles.yaml — meta.codegraph_integration block
    cp_path = project_root / _V12_5_0_PV04_CONTEXT_PROFILES_FILE
    cp_payload = yaml.safe_load(cp_path.read_text(encoding="utf-8"))
    meta = cp_payload.get("meta") or {}
    cg_integration = meta.get("codegraph_integration")
    assert cg_integration is not None, (
        f"W-18 v12.5.0 PV-04 violation: {_V12_5_0_PV04_CONTEXT_PROFILES_FILE} "
        "missing `meta.codegraph_integration` block. The block parallels "
        "meta.nines_integration above and is a release blocker."
    )
    assert "commands" in cg_integration
    assert "triggers" in cg_integration

    # --- (f) companion test file -------------------------------------
    wiring_test_path = project_root / Path("tests/test_codegraph_workflow_wiring.py")
    assert wiring_test_path.is_file(), (
        "W-18 v12.5.0 PV-04 violation: "
        "tests/test_codegraph_workflow_wiring.py missing — release blocker. "
        "The companion test file pins the workflow + context-profile "
        "wiring contract (12 structural assertion tests)."
    )
    wiring_text = wiring_test_path.read_text(encoding="utf-8")
    for class_or_test in (
        "TestRepoInitCodegraphWiring",
        "test_sister_template_analyze_has_codegraph_commands",
        "TestContextProfilesCodegraphIntegration",
    ):
        assert class_or_test in wiring_text, (
            f"W-18 v12.5.0 PV-04 violation: "
            "tests/test_codegraph_workflow_wiring.py missing "
            f"{class_or_test!r}. The 12-test contract is documented in "
            "the cycle plan §PV-04 deliverable list."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-05 D-1.3 — codegraph docs landed
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the codegraph reference doc + degraded-mode +
# env-flags + SKILL.md updates. This stanza pins the v12.5.0 PV-05 D-1.3
# documentation surface:
#
# * workflow-system/agent/references/codegraph.md exists with the
#   6 canonical anchor sections (§1..§6) under the C-4 Large-tier
#   ceiling.
# * workflow-system/agent/references/degraded-mode.md carries the
#   codegraph row in §"Plugin Matrix" + the §"Section 5 — codegraph"
#   detailed treatment.
# * workflow-system/agent/references/env-flags.md §7 W-20 checklist
#   carries the v12.5.0 PV-05 reuse-first reference case note (codegraph
#   reuses DEVOLAFLOW_AUTO_INSTALL_PLUGINS).
# * workflow-system/agent/SKILL.md carries the §"Workspace Engagement"
#   .codegraph/ row + §"Reference Navigation Guide" Tier-2 codegraph
#   row + §"Quick Start" repo-init "auto-installs codegraph index" note.
# * SF-4 reference set updated: 21 → 22 entries
#   (_SF4_REFERENCE_SET in tests/test_no_ghost_features.py).
# * Companion test file tests/test_codegraph_reference_doc.py exists
#   with the 6 structural assertion tests.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.3 +
# .local/research/v12.5.0_codegraph_benefit_analysis.md §6.3
# PV-05 acceptance criteria.
# ---------------------------------------------------------------------------
_V12_5_0_PV05_REFERENCE_FILE: Path = Path("workflow-system/agent/references/codegraph.md")
_V12_5_0_PV05_DEGRADED_FILE: Path = Path("workflow-system/agent/references/degraded-mode.md")
_V12_5_0_PV05_ENVFLAGS_FILE: Path = Path("workflow-system/agent/references/env-flags.md")
_V12_5_0_PV05_SKILL_FILE: Path = Path("workflow-system/agent/SKILL.md")


def test_v12_5_0_codegraph_docs_landed(project_root: Path) -> None:
    """W-18 v12.5.0 PV-05 D-1.3: codegraph docs surface landed.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the codegraph documentation. The stanza asserts five
    load-bearing surfaces:

    (a) references/codegraph.md exists with the 6 canonical anchors.
    (b) references/degraded-mode.md mentions codegraph in §Plugin Matrix
        + §Section 5.
    (c) references/env-flags.md §7 carries the W-20 reuse-first note.
    (d) SKILL.md carries the .codegraph/ row + Tier-2 row + repo-init note.
    (e) Companion test file tests/test_codegraph_reference_doc.py exists.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.3.
    """
    # --- (a) references/codegraph.md ---------------------------------
    ref_path = project_root / _V12_5_0_PV05_REFERENCE_FILE
    assert ref_path.is_file(), (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_REFERENCE_FILE} missing — release blocker."
    )
    ref_text = ref_path.read_text(encoding="utf-8")
    for anchor in (
        "## §1 — What codegraph is",
        "## §2 — The 9 MCP tools",
        "## §3 — CLI surface",
        "## §4 — DevolaFlow integration map",
        "## §5 — Degraded-mode contract",
        "## §6 — Cache management",
    ):
        assert anchor in ref_text, (
            f"W-18 v12.5.0 PV-05 violation: "
            f"{_V12_5_0_PV05_REFERENCE_FILE} missing anchor {anchor!r}. "
            "The 6 canonical sections are the PV-05 acceptance criterion."
        )

    # --- (b) references/degraded-mode.md — codegraph row + Section 5
    degraded_text = (project_root / _V12_5_0_PV05_DEGRADED_FILE).read_text(encoding="utf-8")
    assert "| codegraph |" in degraded_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_DEGRADED_FILE} "
        "missing the `| codegraph |` row in §Plugin Matrix."
    )
    assert "### Section 5 — codegraph" in degraded_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_DEGRADED_FILE} "
        "missing the `### Section 5 — codegraph` detailed treatment."
    )

    # --- (c) references/env-flags.md — W-20 reuse-first note ---------
    envflags_text = (project_root / _V12_5_0_PV05_ENVFLAGS_FILE).read_text(encoding="utf-8")
    assert "v12.5.0 PV-05 reuse-first" in envflags_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_ENVFLAGS_FILE} "
        "§7 missing the v12.5.0 PV-05 reuse-first reference case note. "
        "The note documents that codegraph REUSED "
        "DEVOLAFLOW_AUTO_INSTALL_PLUGINS rather than authoring a new flag."
    )

    # --- (d) SKILL.md — 3 codegraph mentions -------------------------
    skill_text = (project_root / _V12_5_0_PV05_SKILL_FILE).read_text(encoding="utf-8")
    assert ".codegraph/codegraph.db" in skill_text or ".codegraph/" in skill_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_SKILL_FILE} "
        "§Workspace Engagement missing the .codegraph/ row."
    )
    assert "references/codegraph.md" in skill_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_SKILL_FILE} "
        "§Reference Navigation Guide Tier-2 missing the codegraph row."
    )
    assert "auto-installs codegraph index" in skill_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_SKILL_FILE} "
        "§Quick Start repo-init row missing the "
        "'auto-installs codegraph index' note."
    )

    # --- (e) companion test file -------------------------------------
    doc_test_path = project_root / Path("tests/test_codegraph_reference_doc.py")
    assert doc_test_path.is_file(), (
        "W-18 v12.5.0 PV-05 violation: "
        "tests/test_codegraph_reference_doc.py missing — release blocker."
    )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-05 D-3 — handoff envelope auto-strip helper
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the strip_l0_only_metadata helper. This stanza
# pins the v12.5.0 PV-05 D-3 surface (closes the v12.4.0 retro §6 telegraph
# item 2 — handoff envelope auto-strip helper):
#
# * src/devolaflow/agent_workspace/handoff.py exports the
#   strip_l0_only_metadata public function symbol.
# * The helper signature matches the documented contract
#   (envelope: dict -> dict; pure / idempotent / permissive on absent /
#   permissive on empty / S-5 explicit warn on non-dict).
# * Companion test file tests/test_handoff_strip_metadata.py exists with
#   the 11 contract-pin tests covering happy-path + idempotency +
#   pure-function-invariant + degraded paths.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-3 +
# .local/research/v12.4.0_retrospective.md §6 telegraph item 2.
# ---------------------------------------------------------------------------
_V12_5_0_PV05_HANDOFF_FILE: Path = Path("src/devolaflow/agent_workspace/handoff.py")


def test_v12_5_0_handoff_strip_helper(project_root: Path) -> None:
    """W-18 v12.5.0 PV-05 D-3: strip_l0_only_metadata helper landed.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the handoff envelope auto-strip helper. The stanza
    asserts three load-bearing surfaces:

    (a) src/devolaflow/agent_workspace/handoff.py declares the public
        strip_l0_only_metadata symbol with the documented signature.
    (b) The helper is exported in __all__ so callers can import it.
    (c) Companion test file tests/test_handoff_strip_metadata.py exists
        with the 11 contract-pin tests.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-3.
    """
    # --- (a) handoff.py declares the helper --------------------------
    handoff_text = (project_root / _V12_5_0_PV05_HANDOFF_FILE).read_text(encoding="utf-8")
    assert "def strip_l0_only_metadata(envelope: dict) -> dict:" in handoff_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_HANDOFF_FILE} "
        "missing `def strip_l0_only_metadata(envelope: dict) -> dict:` "
        "definition. The signature is part of the v12.5.0 PV-05 D-3 "
        "contract surface."
    )

    # --- (b) __all__ export ------------------------------------------
    assert '__all__.append("strip_l0_only_metadata")' in handoff_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_HANDOFF_FILE} "
        'missing `__all__.append("strip_l0_only_metadata")` — the '
        "public-API export is part of the contract."
    )

    # --- (c) companion test file -------------------------------------
    test_path = project_root / Path("tests/test_handoff_strip_metadata.py")
    assert test_path.is_file(), (
        "W-18 v12.5.0 PV-05 violation: "
        "tests/test_handoff_strip_metadata.py missing — release blocker."
    )
    test_text = test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_happy_path_strips_banner_literal_from_string_field",
        "test_happy_path_strips_quality_score_key",
        "test_idempotency",
        "test_input_dict_not_mutated",
        "test_non_dict_input_warns_and_returns_unchanged",
        "test_companion_to_banner_hook_zero_violations_post_strip",
    ):
        assert f"def {expected_test}" in test_text, (
            f"W-18 v12.5.0 PV-05 violation: "
            "tests/test_handoff_strip_metadata.py missing test "
            f"{expected_test!r}."
        )
