"""Ghost audit — per-cycle W-18 feature stanzas for the v14.5 cycle.

Per v15-ADR-001 (v14.3.0 split): new W-18 stanzas for a v14.5.x release
append HERE; the next MINOR cycle rotates to a fresh
``test_features_v<MAJ>_<MIN>.py``. Every symbol pinned below was
verified against the working tree at authoring time (v14.5.0 T7
release close) — NOT blind-trusted from sibling-task descriptions.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_script_module(project_root: Path, rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, project_root / rel_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_v14_5_0_adr006_module_split_registered(project_root: Path) -> None:
    """W-18 v14.5.0: the T1 ADR-006 module split (G-025) has coverage.

    Discharges the W-18 precondition for the v14.5.0 CHANGELOG entry on
    the T1 slice. The stanza pins:

    (a) The 6 NEW owner modules exist and import: gate/cascade.py,
        gate/ladder.py, gate/acceptance_v2.py, dispatch.py,
        agents_md_slice.py, selector_cli.py.
    (b) Shim identity — ``old_path.symbol is new_path.symbol`` for the
        gate.scorer re-exports AND the feedback.py S-10-named path
        (``feedback.populate_cascade_gate_fields`` keeps working).
    (c) Post-split line ceilings stay honest: scorer < 1700,
        task_adaptive_selector < 1600.
    (d) tests/test_module_split_shims.py (the dedicated identity suite)
        exists.

    Source: ADR-006 (G-025); shims are PERMANENT (lifetime >= v16.0.0).
    """
    # --- (a) the 6 new owner modules import -------------------------------
    import devolaflow.agents_md_slice  # noqa: F401
    import devolaflow.dispatch as dispatch
    import devolaflow.feedback as feedback
    import devolaflow.gate.acceptance_v2 as acceptance_v2
    import devolaflow.gate.cascade as cascade
    import devolaflow.gate.ladder as ladder
    import devolaflow.gate.scorer as scorer
    import devolaflow.selector_cli  # noqa: F401

    # --- (b) identity-preserving shims ------------------------------------
    assert scorer.validate_cascade_gate_fields is cascade.validate_cascade_gate_fields, (
        "W-18 v14.5.0 violation: gate.scorer cascade shim lost identity (ADR-006)."
    )
    assert scorer.evaluate_ladder is ladder.evaluate_ladder, (
        "W-18 v14.5.0 violation: gate.scorer ladder shim lost identity (ADR-006)."
    )
    assert (
        scorer.evaluate_acceptance_criteria_v2 is acceptance_v2.evaluate_acceptance_criteria_v2
    ), "W-18 v14.5.0 violation: gate.scorer acceptance_v2 shim lost identity (ADR-006)."
    assert feedback.populate_cascade_gate_fields is cascade.populate_cascade_gate_fields, (
        "W-18 v14.5.0 violation: feedback.py shim lost identity — S-10 and "
        "schemas/lean-dispatch.yaml name feedback.py::populate_cascade_gate_fields verbatim."
    )
    assert feedback.dispatch_wave_tasks is dispatch.dispatch_wave_tasks, (
        "W-18 v14.5.0 violation: feedback.py dispatch shim lost identity (ADR-006)."
    )
    # The S-10-named path stays FUNCTIONAL, not just importable.
    populated = feedback.populate_cascade_gate_fields({}, "STANDARD")
    assert populated["gate"]["cascade_required"] is True
    assert populated["gate"]["cascade_min_layers"] == 4

    # --- (c) post-split line ceilings --------------------------------------
    scorer_lines = len(
        (project_root / "src/devolaflow/gate/scorer.py").read_text(encoding="utf-8").splitlines()
    )
    selector_lines = len(
        (project_root / "src/devolaflow/task_adaptive_selector.py")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert scorer_lines < 1700, (
        f"W-18 v14.5.0 violation: gate/scorer.py regrew to {scorer_lines} lines "
        "(ADR-006 split landed it at 1579; ceiling 1700)."
    )
    assert selector_lines < 1600, (
        f"W-18 v14.5.0 violation: task_adaptive_selector.py regrew to "
        f"{selector_lines} lines (ADR-006 ceiling 1600)."
    )

    # --- (d) dedicated identity suite ---------------------------------------
    assert (project_root / "tests/test_module_split_shims.py").is_file(), (
        "W-18 v14.5.0 violation: tests/test_module_split_shims.py missing — "
        "the ADR-006 shim-identity suite is the strict enforcement surface."
    )


def test_v14_5_0_changelog_lint_registered(project_root: Path) -> None:
    """W-18 v14.5.0: the T2 D-5 CHANGELOG single-application lint (G-036) has coverage.

    Discharges the W-18 precondition for the v14.5.0 CHANGELOG entry on
    the T2 slice (telegraphed since v11.1.0). The stanza pins:

    (a) scripts/lint_changelog.py with the 5 public entry points
        (parse_blocks / check_structure / check_immutability /
        check_version_match / main).
    (b) tests/test_changelog_lint.py (the dedicated unit suite) exists.
    (c) Makefile ``lint-changelog`` target.
    (d) [MIGRATED — clean_repo PR-12, decision D7/OPT-1] the CI step named
        "CHANGELOG lint (D-5 single-application)" moved VERBATIM from
        ci.yml into the reusable .github/workflows/ci-checks.yml
        (``on: workflow_call``), which both ci.yml and release.yml now
        consume — the release path inherits the lint it previously
        lacked. The pin follows the step to its single owner file.
    """
    # --- (a) script module + entry points ----------------------------------
    mod = _load_script_module(project_root, "scripts/lint_changelog.py", "lint_changelog_w18")
    for fn_name in (
        "parse_blocks",
        "check_structure",
        "check_immutability",
        "check_version_match",
        "main",
    ):
        assert callable(getattr(mod, fn_name, None)), (
            f"W-18 v14.5.0 violation: scripts/lint_changelog.py missing entry point {fn_name!r}."
        )

    # --- (b) dedicated unit suite -------------------------------------------
    assert (project_root / "tests/test_changelog_lint.py").is_file(), (
        "W-18 v14.5.0 violation: tests/test_changelog_lint.py missing (D-5 / G-036)."
    )

    # --- (c) + (d) Makefile target + CI step --------------------------------
    makefile = (project_root / "Makefile").read_text(encoding="utf-8")
    assert "\nlint-changelog:" in makefile, (
        "W-18 v14.5.0 violation: Makefile missing the lint-changelog target (D-5)."
    )
    ci_text = (project_root / ".github/workflows/ci-checks.yml").read_text(encoding="utf-8")
    assert "CHANGELOG lint (D-5 single-application)" in ci_text, (
        "W-18 v14.5.0 violation: ci-checks.yml missing the named D-5 CHANGELOG lint step."
    )


def test_v14_5_0_baseline_tiering_registered(project_root: Path) -> None:
    """W-18 v14.5.0: the T3 baseline tiering sweep (G-014 / v15-ADR-005) has coverage.

    Discharges the W-18 precondition for the v14.5.0 CHANGELOG entry on
    the T3 slice. The stanza pins:

    (a) [MIGRATED — clean_repo Phase C1-3, decision D4] the exact
        baselines/ listing lint moved to tests/ghost/test_registries.py::
        test_baselines_dir_matches_tier_a_pin_and_derived_tier_b — the
        Tier-A witness pin moved there VERBATIM (still hand-frozen per
        A-2.4) and the hand-pinned ``_KEPT_BASELINE_JSONS`` frozenset was
        retired in favour of the derived Tier-B window
        (``_tier_b_window`` ∪ ``_TEST_LOADED_KEEPS`` ∪ newest). Single
        authority per A-5 — no listing assertion remains here.
    (b) The write-only ``backward_compat`` boolean block is GONE from
        schemas/lean-dispatch.yaml#layout_invariant.enforcement.
    (c) The compiled A-2.4 rule text carries the Tier-A/B/C tiered
        retention wording in BOTH corpus targets.
    """
    # --- (b) backward_compat block removed (parsed, not text — the schema
    # keeps an explanatory comment) -----------------------------------------
    schema = yaml.safe_load(
        (project_root / "schemas/lean-dispatch.yaml").read_text(encoding="utf-8")
    )
    assert "backward_compat" not in schema["layout_invariant"]["enforcement"], (
        "W-18 v14.5.0 violation: the backward_compat boolean block regressed "
        "into lean-dispatch.yaml — it was removed at v14.5.0 (G-014); the "
        "executable witness is tests/test_layout_invariant_multi_baseline.py."
    )

    # --- (c) A-2.4 tiered-retention wording in both corpus targets ---------
    for corpus in (".cursor/rules/repo-governance.mdc", "AGENTS.md"):
        corpus_text = (project_root / corpus).read_text(encoding="utf-8")
        for fragment in (
            "Tiered Retention per v15-ADR-005",
            "**Tier A — permanent byte-witnesses**",
            "**Tier B — rolling window (in CI)**",
            "**Tier C — archived (out of CI)**",
        ):
            assert fragment in corpus_text, (
                f"W-18 v14.5.0 violation: {corpus} A-2.4 missing the tiered-"
                f"retention fragment {fragment!r} (G-014 recompile)."
            )


def test_v14_5_0_timeout_defaults_registered(project_root: Path) -> None:
    """W-18 v14.5.0: the T4 per-task-type timeout defaults (G-037) has coverage.

    Discharges the W-18 precondition for the v14.5.0 CHANGELOG entry on
    the T4 slice. The stanza pins:

    (a) task_adaptive_selector: resolve_timeout_seconds +
        DEFAULT_TIMEOUT_CLASS ("impl"), absence-safe (empty config never
        raises — falls back to the library-constant mirror).
    (b) context_profiles.yaml ``defaults.timeout_class_map`` SSOT with
        the canonical class values.
    (c) ``select_context()`` returns a ``timeout_seconds`` key resolved
        from the profile's timeout class.
    (d) execution-protocol.md §14 graduated to the select_context
        auto-population contract.
    """
    from devolaflow.task_adaptive_selector import (
        DEFAULT_TIMEOUT_CLASS,
        resolve_timeout_seconds,
        select_context,
    )

    # --- (a) resolver + default class + absence safety ---------------------
    assert DEFAULT_TIMEOUT_CLASS == "impl", (
        "W-18 v14.5.0 violation: DEFAULT_TIMEOUT_CLASS drifted from 'impl' "
        "(the delta-only overlay default per G-037/G-026)."
    )
    assert resolve_timeout_seconds({}, {}) == 1800, (
        "W-18 v14.5.0 violation: resolve_timeout_seconds must stay absence-"
        "safe — empty config resolves via the default_timeout_for mirror (1800s impl)."
    )

    # --- (b) SSOT map -------------------------------------------------------
    parsed = yaml.safe_load(
        (project_root / "workflow-system/agent/context_profiles.yaml").read_text(encoding="utf-8")
    )
    assert parsed["defaults"]["timeout_class_map"] == {
        "research": 2700,
        "impl": 1800,
        "test": 900,
        "review": 1200,
        "hotfix": 600,
        "fallback": 7200,
    }, "W-18 v14.5.0 violation: defaults.timeout_class_map SSOT values drifted (G-037)."

    # --- (c) select_context auto-population --------------------------------
    assert select_context("research")["timeout_seconds"] == 2700
    assert select_context("hotfix")["timeout_seconds"] == 600

    # --- (d) execution-protocol §14 graduation ------------------------------
    ep_text = (project_root / "workflow-system/agent/references/execution-protocol.md").read_text(
        encoding="utf-8"
    )
    section_14 = ep_text.split("## 14. Per-Task-Type Timeout Defaults", 1)
    assert len(section_14) == 2, (
        "W-18 v14.5.0 violation: execution-protocol.md lost the §14 "
        "per-task-type timeout defaults section."
    )
    for fragment in ("resolve_timeout_seconds", "defaults.timeout_class_map"):
        assert fragment in section_14[1].split("\n## ", 1)[0], (
            f"W-18 v14.5.0 violation: execution-protocol.md §14 missing the "
            f"graduated {fragment!r} contract (G-037)."
        )


def test_v14_5_0_si10_chain_reorg_registered(project_root: Path) -> None:
    """W-18 v14.5.0: the T5 SI-10 gate-chain reorg (G-033) has coverage.

    Discharges the W-18 precondition for the v14.5.0 CHANGELOG entry on
    the T5 slice. The stanza pins:

    (a) Makefile ``test-core`` target with EXACTLY the 3 ``--ignore``
        lines (the standalone gate-4/5/7 files — single-execution design).
    (b) ``release-preflight`` orders the 6 SI-10 core targets BEFORE the
        6 release-only extras.
    (c) Compiled W-9 step-1 text cites ``make test-core``.
    (d) The G-035 verified-no-op comment cites AdapterRegistry.list_names().
    (e) The inverted backward_compat test
        (test_backward_compat_block_removed) is present per ADR-005.
    """
    makefile = (project_root / "Makefile").read_text(encoding="utf-8")

    # --- (a) test-core target + exactly 3 ignores ---------------------------
    assert "\ntest-core:" in makefile, (
        "W-18 v14.5.0 violation: Makefile missing the test-core target (G-033)."
    )
    core_body = makefile.split("\ntest-core:", 1)[1].split("\n\n", 1)[0]
    ignores = [ln.strip().rstrip(" \\") for ln in core_body.splitlines() if "--ignore=" in ln]
    assert sorted(ignores) == [
        "--ignore=tests/test_benchmarks.py",
        "--ignore=tests/test_sichip_iteration_delta_gate.py",
        "--ignore=tests/test_version.py",
    ], (
        f"W-18 v14.5.0 violation: test-core --ignore set drifted ({ignores}) — "
        "single-execution requires exactly the 3 standalone gate-4/5/7 files."
    )

    # --- (b) core-before-extras ordering ------------------------------------
    preflight_line = next(ln for ln in makefile.splitlines() if ln.startswith("release-preflight:"))
    deps = preflight_line.split(":", 1)[1].split()
    core = [
        "test-core",
        "lint",
        "test-version",
        "test-benchmarks",
        "check-cursor-skill",
        "iteration-delta-gate",
    ]
    extras = [
        "validate-templates",
        "build-skill",
        "sync-human-docs",
        "compile-rules",
        "check-drift",
        "check-rules-drift",
    ]
    assert deps == core + extras, (
        f"W-18 v14.5.0 violation: release-preflight prerequisite order drifted "
        f"({deps}) — the 6 SI-10 core gates must run BEFORE the 6 release-only extras."
    )

    # --- (c) compiled W-9 step-1 text ----------------------------------------
    corpus_text = (project_root / ".cursor/rules/repo-governance.mdc").read_text(encoding="utf-8")
    assert "1. `make test-core` — all tests pass" in corpus_text, (
        "W-18 v14.5.0 violation: compiled W-9 step 1 no longer cites make "
        "test-core (G-033 recompile)."
    )

    # --- (d) G-035 verified-no-op comment ------------------------------------
    assert "AdapterRegistry.list_names()" in makefile, (
        "W-18 v14.5.0 violation: Makefile lost the G-035 comment citing "
        "AdapterRegistry.list_names() (build-skill is registry-driven)."
    )

    # --- (e) inverted backward_compat test ------------------------------------
    layout_test = (project_root / "tests/test_dispatch_layout_v5.py").read_text(encoding="utf-8")
    assert "def test_backward_compat_block_removed" in layout_test, (
        "W-18 v14.5.0 violation: the inverted backward_compat test "
        "(ADR-005) is missing from tests/test_dispatch_layout_v5.py."
    )


def test_v14_5_0_skill_ia_pass_registered(project_root: Path) -> None:
    """W-18 v14.5.0: the T6 SKILL.md IA pass (G-019) has coverage.

    Discharges the W-18 precondition for the v14.5.0 CHANGELOG entry on
    the T6 slice. The stanza pins:

    (a) SKILL.md <= 430 lines (492 -> 429 at the IA pass).
    (b) The 5 surviving critical surfaces whose demotion was REFUSED /
        deferred-with-tightening: Rationalization Prevention, AgentTeam
        Quick Reference (team tables), Repo Mode Detection, Lifecycle
        Hooks, Stage Primitives Index (tightened 49 -> 20, NOT removed).
    (c) The Template Quick-Reference demotion: gate-type table now owned
        by meta-framework.md §4; the SKILL.md section is GONE.
    (d) troubleshooting.md absorbed the install note (§2.17) + the
        working-tree anecdote (§2.18).
    (e) ``template_quick_ref`` is fully retired from the section
        registry + context_profiles.yaml (comments excepted).
    """
    skill_path = project_root / "workflow-system/agent/SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8")

    # --- (a) line ceiling ---------------------------------------------------
    skill_lines = len(skill_text.splitlines())
    assert skill_lines <= 430, (
        f"W-18 v14.5.0 violation: SKILL.md regrew to {skill_lines} lines "
        "(G-019 IA pass landed it at 429; C-4 hard ceiling stays < 500)."
    )

    # --- (b) the 5 surviving surfaces ----------------------------------------
    for heading in (
        "### Rationalization Prevention",
        "## AgentTeam Quick Reference",
        "## Repo Mode Detection",
        "## Lifecycle Hooks",
        "## Stage Primitives Index",
    ):
        assert heading in skill_text, (
            f"W-18 v14.5.0 violation: SKILL.md lost the surviving critical "
            f"surface {heading!r} — its demotion was REFUSED at the G-019 IA pass."
        )

    # --- (c) Template Quick-Reference demotion -------------------------------
    assert "## Template Quick-Reference" not in skill_text, (
        "W-18 v14.5.0 violation: SKILL.md regrew the Template Quick-Reference "
        "section — meta-framework.md §4 is the single owner surface (G-019)."
    )
    mf_text = (project_root / "workflow-system/agent/references/meta-framework.md").read_text(
        encoding="utf-8"
    )
    assert "### Template Quick-Reference — Gate Types" in mf_text, (
        "W-18 v14.5.0 violation: meta-framework.md missing the absorbed "
        "Template Quick-Reference — Gate Types table (G-019)."
    )

    # --- (d) troubleshooting absorptions --------------------------------------
    ts_text = (project_root / "workflow-system/agent/references/troubleshooting.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "#### 2.17 `devola-init` on a pip-wheel-only install (I-001 / I-004)",
        "#### 2.18 Pre-existing working-tree corruption at cycle entry",
    ):
        assert heading in ts_text, (
            f"W-18 v14.5.0 violation: troubleshooting.md missing the absorbed "
            f"section {heading!r} (G-019)."
        )

    # --- (e) template_quick_ref retired from registry + profiles -------------
    registry_text = (project_root / "src/devolaflow/section_registry.py").read_text(
        encoding="utf-8"
    )
    assert "template_quick_ref" not in registry_text, (
        "W-18 v14.5.0 violation: section_registry.py still registers "
        "template_quick_ref — the section was removed at G-019."
    )
    import json as _json

    profiles_parsed = yaml.safe_load(
        (project_root / "workflow-system/agent/context_profiles.yaml").read_text(encoding="utf-8")
    )
    assert "template_quick_ref" not in _json.dumps(profiles_parsed), (
        "W-18 v14.5.0 violation: context_profiles.yaml still carries a "
        "template_quick_ref key (comments excepted — this checks parsed YAML)."
    )
