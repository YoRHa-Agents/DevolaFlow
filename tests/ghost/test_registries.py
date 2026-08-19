"""Ghost audit — A-5 SSOT single-owner + SF-4 reference-set pins.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). Owns the shared pins ``_SF4_REFERENCE_SET`` /
``_SSOT_PYTHON_REGISTRIES`` / ``_SSOT_YAML_REGISTRIES`` re-exported
by the deprecation aggregator (external citations per C-7 / A-5.1).

Since clean_repo Phase C1-3 (D4 hybrid design) this module also owns
the baselines-directory listing lint: the immutable Tier-A witness pin
(``_TIER_A_WITNESSES``, moved verbatim from
``tests/ghost/test_features_v14_5.py``) and the DERIVED Tier-B JSON
expectation (``_tier_b_window`` + ``_TEST_LOADED_KEEPS``).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from benchmarks.devolaflow_context.runner import _BASELINE_PATTERN, _newest_baseline_path
from devolaflow import __version__
from tests.ghost._helpers import _read

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
        # v14.0.0 — human-surface reference (24th SF-4 canonical). Tier 2
        # Large-tier reference documenting the new `.local/human/` surface:
        # the two-zone INPUT (immutable constitution + stable REQ-ID
        # requirements + append-only amendments ledger; Lifecycle:RATIFIED
        # append-only per Rule S-9) / OUTPUT (conclusion-first convergence
        # report + read-first DIGEST) layout, the per-artifact C-9 token
        # budgets, the INPUT-only git-tracking + sichip-deferred relocation
        # de-pollution, the `scan_workspace` discovery fields
        # (has_human_dir / human_constitution / human_requirements /
        # human_digest) + When-to-Engage routing, and the
        # `trace_requirements` / `lint_human` / `render_human_report`
        # Python APIs + the `check_human_input_append_only` lifecycle hook.
        # NO new env flag (W-20 reuse-first preservation). Pairs with
        # src/devolaflow/agent_workspace/requirements_trace.py,
        # src/devolaflow/lifecycle/check_human_input_append_only.py, and
        # tests/test_no_ghost_features.py::test_v14_0_0_human_surface_symbols.
        "human-surface.md",
        # v14.3.0 — artifact-quality evidence rubric (25th SF-4 canonical).
        # Tier 2 Large-tier reference: the EVIDENCE-ONLY rubric for the L3
        # task artifact itself per v15-ADR-007 (closes G-004 / F-P1-2 from
        # the v14.2.0 SI-1 gap analysis §2.1). §1 doctrine (L3 MUST NOT
        # compute or report numeric quality scores — evidence only; the
        # reject_subagent_quality_score hook stays the runtime guard),
        # §2 four excellence dimensions (correctness / minimal diff / test
        # evidence / convention adherence, citing S-3, S-5, S-8, BG-002,
        # BG-003, C-3), §3 dimension → lean-report transport map
        # (self_check / ac_results / diff_stats / metrics.*), §4 ordered
        # self-verify checklist, §5 failure honesty. Pairs with
        # references/execution-protocol.md §15 "L3 Self-Verify" (G-005
        # protocol slice) and references/task-quality-score.md (the L0-only
        # OPERATOR-REQUEST rubric — the two never overlap). Numeric scoring
        # stays L0-side and lands v15.0.0 per the v15-ADR-007 phase split.
        "artifact-quality.md",
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
    # v15.0.x (full_review_and_improve Track B-1, D-5): the install manifest —
    # single owner of the per-tool install file lists consumed by
    # scripts/install.sh, scripts/sync_cursor_skill.py::MIRRORED_FILES, and
    # devola-init (src/devolaflow/init_project.py). Three-way parity with the
    # on-disk files + _SF4_REFERENCE_SET is linted by
    # tests/test_install_manifest.py.
    "manifest.yaml": "workflow-system/agent/manifest.yaml",
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


@pytest.mark.parametrize(
    ("symbol_name", "expected_relpath"),
    sorted(_SSOT_PYTHON_REGISTRIES.items()),
)
def test_registry_single_owner(project_root: Path, symbol_name: str, expected_relpath: str) -> None:
    """A-5: each domain-SSOT registry must have exactly one owner module.

    Per Architecture Rule A-5 (`.rules/architecture.mdc` §A-5.1), splitting
    registration data across two modules invalidates cache reasoning and is
    a release blocker. This test AST-walks ``src/devolaflow/`` and asserts:

    1. Each Python-backed registry symbol (`WHITELIST`, `MemoryCase`,
       `CommandMapping`) has exactly ONE module-level definer.
    2. The single definer matches the canonical owner path declared above.

    (YAML-backed registries are covered by the parametrized companion
    ``test_registry_yaml_at_canonical_path`` below — per-item parametrize
    split per the G-029 inventory-suite conversion, v14.3.0.)

    Failure means a NEW module shadowed an SSOT registration without
    routing through the owner module — the M-001 / M-002 anti-pattern
    that A-5 forbids.
    """
    src_root = project_root / "src" / "devolaflow"
    assert src_root.is_dir(), f"src/devolaflow/ missing — cannot audit (looked under {src_root})"

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


@pytest.mark.parametrize(
    ("yaml_name", "expected_relpath"),
    sorted(_SSOT_YAML_REGISTRIES.items()),
)
def test_registry_yaml_at_canonical_path(
    project_root: Path, yaml_name: str, expected_relpath: str
) -> None:
    """A-5: each YAML-backed SSOT registry lives at exactly its canonical path.

    File-path uniqueness — there is no `find` step because the
    registry-loading helpers in ``devolaflow.plugins.{loader,installer}``
    import these via verbatim paths, not glob patterns. Split out of
    ``test_registry_single_owner`` as a mechanical per-item parametrize
    conversion (G-029, v14.3.0) — assertion semantics unchanged.
    """
    yaml_path = project_root / expected_relpath
    assert yaml_path.is_file(), (
        f"A-5 violation: YAML SSOT registry {yaml_name!r} expected at "
        f"{expected_relpath} but file is missing"
    )


# ── A-2.4 baseline tiering — Tier-A pin + DERIVED Tier-B window ─────────
# clean_repo Phase C1-3 (decision D4, hybrid design). The baselines-
# directory listing lint migrated here from the frozen v14.5 cycle stanza
# (tests/ghost/test_features_v14_5.py::test_v14_5_0_baseline_tiering_registered
# part (a)) per v15-ADR-001 domain-lint placement. Split of authority:
#
# * Tier-A (the 10 layout_invariant_v*.yaml byte-witnesses) stays a
#   HAND-FROZEN strict pin — per A-2.4 the pin IS the governance body;
#   deriving or weakening it is a release blocker.
# * Tier-B (the v*_baseline.json rolling window) is DERIVED from
#   ``devolaflow.__version__`` + the on-disk filename version ordering,
#   UNIONed with the ``_TEST_LOADED_KEEPS`` reader registry and the
#   ``_newest_baseline_path`` pin. The set assertion stays STRICT
#   EQUALITY (never ⊇) so the lint keeps its anti-bloat teeth.
#
# Net effect: future W-16 wholesale regens and A-2.4 Tier-C archival
# sweeps (git mv to docs/cycle-archive/<cycle>/baselines/) require ZERO
# test edits; only rewiring a historical JSON's reader requires dropping
# its _TEST_LOADED_KEEPS entry.

# The 10 Tier-A byte-witnesses (IMMUTABLE per A-2.4 tiered retention /
# v15-ADR-005 G-014) — moved VERBATIM from tests/ghost/test_features_v14_5.py
# at clean_repo Phase C1-3; pruning or relocating ANY of these is a
# release blocker. NOT derived — do not fold into _tier_b_window.
_TIER_A_WITNESSES: frozenset[str] = frozenset(
    {
        "layout_invariant_v7.0.0.yaml",
        "layout_invariant_v7.3.0.yaml",
        "layout_invariant_v8.0.0.yaml",
        "layout_invariant_v8.3.0.yaml",
        "layout_invariant_v8.4.0.yaml",
        "layout_invariant_v9.2.0.yaml",
        "layout_invariant_v9.3.0.yaml",
        "layout_invariant_v9.7.0.yaml",
        "layout_invariant_v10.2.0.yaml",
        "layout_invariant_v12.0.0.yaml",
    }
)


# Historical baseline JSONs still LOADED (or existence-pinned) by in-repo
# tests/tooling — kept outside the Tier-B window for as long as their
# readers stand. Each entry maps to its verified reader files (located
# via `rg --fixed-strings <name>` at authoring time); the lint below
# asserts every listed reader still cites the file, so a rewired reader
# surfaces as a stale entry to delete rather than silent dead weight.
_TEST_LOADED_KEEPS: dict[str, tuple[str, ...]] = {
    # Legacy fallback baseline: runner.py::FALLBACK_BASELINE_NAME + 4
    # direct loads in the benchmark suite (generate_baseline.py cites it
    # only as provenance prose — not a reader).
    "v2.1.0_baseline.json": (
        "tests/test_benchmarks.py",
        "benchmarks/devolaflow_context/runner.py",
    ),
    # v9.1.x W-16 regen artifact, existence-pinned by the v9.1 stanza.
    "v9.2.0_baseline.json": ("tests/ghost/test_features_v9_1.py",),
    # v9.3.0 PV artifacts: baseline existence-pinned by the v9.3 stanza;
    # the latency JSON is schema-validated by the dispatch-latency suite.
    "v9.3.0_baseline.json": ("tests/ghost/test_features_v9_3.py",),
    "v9.3.0_latency.json": (
        "tests/test_dispatch_latency.py",
        "tests/ghost/test_features_v9_3.py",
    ),
    # v9.7.0 PV artifacts: same split as v9.3.0.
    "v9.7.0_baseline.json": ("tests/ghost/test_features_v9_7.py",),
    "v9.7.0_latency.json": (
        "tests/test_dispatch_latency.py",
        "tests/ghost/test_features_v9_7.py",
    ),
    "v9.7.0_latency_intermediate.json": ("tests/ghost/test_features_v9_7.py",),
    # W-16 regen artifacts existence-pinned by their cycle stanzas.
    "v10.2.0_baseline.json": ("tests/ghost/test_features_v10_2.py",),
    "v11.1.0_baseline.json": ("tests/ghost/test_features_v11_0.py",),
}


# A-2.4 Tier B: "current + previous 2 cycles" (W-16's comparison window).
_TIER_B_CYCLE_COUNT = 3


def _baseline_cycle(name: str) -> tuple[int, int] | None:
    """Return the (MAJOR, MINOR) cycle of a ``v*_baseline.json`` name, else None.

    Delegates filename recognition to the benchmark runner's
    ``_BASELINE_PATTERN`` (the convention owner per A-5 spirit) so the
    window can never disagree with what ``_newest_baseline_path`` /
    ``load_baseline`` consider a baseline file. Non-baseline JSONs
    (e.g. ``v9.3.0_latency.json``) return None and never enter the window.
    """
    m = _BASELINE_PATTERN.match(name)
    if m is None:
        return None
    parts = tuple(int(p) for p in m.group("ver").split("."))
    padded = parts + (0, 0)
    return (padded[0], padded[1])


def _tier_b_window(current_version: str, json_names: Iterable[str]) -> frozenset[str]:
    """Derive the A-2.4 Tier-B rolling window from ``__version__`` + on-disk names.

    Returns the ``v*_baseline.json`` names whose (MAJOR, MINOR) cycle is
    among the ``_TIER_B_CYCLE_COUNT`` most recent DISTINCT cycles present
    in *json_names* and not newer than the cycle of *current_version* —
    i.e. "current + previous 2 MINOR/MAJOR cycles AS PRESENT ON DISK"
    (the cycle sequence is derived by version-sorting the on-disk
    filenames, so gaps between cycles slide over naturally and a cycle
    whose W-16 regen has not landed yet simply is not counted).

    Names that post-date the current cycle are EXCLUDED so a stray
    future-dated file is flagged by the strict-equality assertion
    instead of silently widening the window.
    """
    version_parts = current_version.split(".")
    current_cycle = (int(version_parts[0]), int(version_parts[1]))
    by_cycle: dict[tuple[int, int], set[str]] = {}
    for name in json_names:
        cycle = _baseline_cycle(name)
        if cycle is None or cycle > current_cycle:
            continue
        by_cycle.setdefault(cycle, set()).add(name)
    window_cycles = sorted(by_cycle)[-_TIER_B_CYCLE_COUNT:]
    return frozenset(name for cycle in window_cycles for name in by_cycle[cycle])


def test_baselines_dir_matches_tier_a_pin_and_derived_tier_b(project_root: Path) -> None:
    """A-2.4: baselines/ holds EXACTLY the Tier-A pin + the derived Tier-B set.

    The living successor of the v14.5 stanza's part (a) — see the module-
    section comment above for the D4 hybrid design. Three legs:

    1. Tier-A yaml witnesses: strict equality against the hand-frozen
       ``_TIER_A_WITNESSES`` (IMMUTABLE — never derived).
    2. ``_TEST_LOADED_KEEPS`` liveness: every registered reader file must
       still cite its JSON; a rewired reader means the keeps entry (and,
       once out-of-window, the file) is due for Tier-C archival.
    3. JSON strict equality: on-disk == window(__version__) ∪ keeps ∪
       {newest per ``_newest_baseline_path``} — never a superset check.
    """
    baselines_dir = project_root / "benchmarks/devolaflow_context/baselines"
    yaml_names = {p.name for p in baselines_dir.glob("*.yaml")}
    json_names = {p.name for p in baselines_dir.glob("*.json")}

    # --- (1) Tier-A strict pin (hand-frozen, NOT derived) -------------------
    assert yaml_names == set(_TIER_A_WITNESSES), (
        f"A-2.4 violation: Tier-A witness set drifted — "
        f"missing {sorted(set(_TIER_A_WITNESSES) - yaml_names)}, "
        f"unexpected {sorted(yaml_names - set(_TIER_A_WITNESSES))}. "
        "Tier-A goldens are IMMUTABLE per A-2.4 (v15-ADR-005)."
    )

    # --- (2) keeps-registry liveness ----------------------------------------
    for name, readers in sorted(_TEST_LOADED_KEEPS.items()):
        for reader in readers:
            reader_path = project_root / reader
            assert reader_path.is_file(), (
                f"_TEST_LOADED_KEEPS stale: registered reader {reader!r} for "
                f"{name!r} no longer exists — update the registry entry."
            )
            assert name in reader_path.read_text(encoding="utf-8"), (
                f"_TEST_LOADED_KEEPS stale: {reader!r} no longer cites {name!r} "
                f"— the reader was rewired; drop the entry (and archive the "
                f"JSON via git mv to docs/cycle-archive/<cycle>/baselines/ if "
                f"it is also out of the Tier-B window)."
            )

    # --- (3) derived Tier-B expectation, strict equality ---------------------
    window = _tier_b_window(__version__, json_names)
    newest = _newest_baseline_path(baselines_dir)
    expected = set(window) | set(_TEST_LOADED_KEEPS) | ({newest.name} if newest else set())
    assert json_names == expected, (
        f"A-2.4 violation: kept baseline-JSON set drifted — "
        f"missing {sorted(expected - json_names)}, "
        f"unexpected {sorted(json_names - expected)}. "
        f"Expected = Tier-B window {sorted(window)} (derived from "
        f"__version__={__version__!r} + on-disk cycle ordering) ∪ "
        f"_TEST_LOADED_KEEPS ∪ newest. W-16 regen artifacts enter the window "
        f"automatically; Tier-C archival goes through git mv to "
        f"docs/cycle-archive/<cycle>/baselines/; a JSON a test still loads "
        f"must be registered in _TEST_LOADED_KEEPS with its reader."
    )


# On-disk shape at authoring time (clean_repo PR-6, __version__ == 15.0.0):
# used by the comparison cases below as the realistic fixture.
_C1_3_ON_DISK_JSONS: tuple[str, ...] = (
    "v2.1.0_baseline.json",
    "v9.2.0_baseline.json",
    "v9.3.0_baseline.json",
    "v9.3.0_latency.json",
    "v9.7.0_baseline.json",
    "v9.7.0_latency.json",
    "v9.7.0_latency_intermediate.json",
    "v10.2.0_baseline.json",
    "v11.1.0_baseline.json",
    "v14.3.0_baseline.json",
    "v14.5.0_baseline.json",
    "v15.0.0_baseline.json",
)


@pytest.mark.parametrize(
    ("current_version", "on_disk", "expected"),
    [
        pytest.param(
            "15.0.0",
            _C1_3_ON_DISK_JSONS,
            {"v15.0.0_baseline.json", "v14.5.0_baseline.json", "v14.3.0_baseline.json"},
            id="live-shape-v15.0.0-window-is-current-plus-2",
        ),
        pytest.param(
            "16.0.0",
            _C1_3_ON_DISK_JSONS,
            {"v15.0.0_baseline.json", "v14.5.0_baseline.json", "v14.3.0_baseline.json"},
            id="major-bump-before-w16-regen-window-holds",
        ),
        pytest.param(
            "15.0.0",
            ("v15.0.0_baseline.json", "v14.5.0_baseline.json"),
            {"v15.0.0_baseline.json", "v14.5.0_baseline.json"},
            id="fewer-than-3-cycles-on-disk-returns-all",
        ),
        pytest.param(
            "15.0.0",
            ("v15.0.0_baseline.json", "v9.3.0_latency.json", "notes.json"),
            {"v15.0.0_baseline.json"},
            id="non-baseline-json-names-never-enter-window",
        ),
        pytest.param(
            "15.0.0",
            ("v15.0.0_baseline.json", "v14.5.0_baseline.json", "v99.9.9_baseline.json"),
            {"v15.0.0_baseline.json", "v14.5.0_baseline.json"},
            id="future-dated-baseline-excluded-from-window",
        ),
        pytest.param(
            "15.0.0",
            ("v15.0.0_baseline.json", "v14.5.0_baseline.json", "v14.5.1_baseline.json"),
            {"v15.0.0_baseline.json", "v14.5.0_baseline.json", "v14.5.1_baseline.json"},
            id="same-minor-cycle-patch-siblings-share-one-window-slot",
        ),
    ],
)
def test_tier_b_window_derivation(
    current_version: str, on_disk: tuple[str, ...], expected: set[str]
) -> None:
    """D4 comparison unit tests: window math across MINOR/MAJOR boundaries.

    Pure-function cases against ``_tier_b_window`` (no disk IO) — the
    anti-"lint 放空" control demanded by the C1-3 spec: the window
    derivation itself is pinned by hand-computed expectations so a bug
    in the derivation cannot silently hollow out the strict-equality lint.
    """
    assert _tier_b_window(current_version, on_disk) == frozenset(expected)


def test_tier_b_window_slides_at_v16_without_frozenset_edit() -> None:
    """Simulated future sweep: the window slides at v16.0.0 with ZERO test edits.

    Scenario: v16.0.0 becomes current, hypothetical v15.x W-16 regen
    JSONs exist on disk. The derived window must slide to the 3 newest
    on-disk cycles (16.0 / 15.4 / 15.0) — v14.5.0 / v14.3.0 fall out and
    become exactly the Tier-C sweep candidates — while no frozenset in
    this repository needs editing (the whole point of D4).
    """
    future_disk = _C1_3_ON_DISK_JSONS + ("v15.4.0_baseline.json", "v16.0.0_baseline.json")
    window = _tier_b_window("16.0.0", future_disk)
    assert window == frozenset(
        {"v16.0.0_baseline.json", "v15.4.0_baseline.json", "v15.0.0_baseline.json"}
    )
    # The names that just slid out are exactly the next Tier-C archival set.
    assert {"v14.5.0_baseline.json", "v14.3.0_baseline.json"}.isdisjoint(window)
