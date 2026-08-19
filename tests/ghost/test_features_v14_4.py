"""Ghost audit — per-cycle W-18 feature stanzas for the v14.4 cycle.

Per v15-ADR-001 (v14.3.0 split): new W-18 stanzas for a v14.4.x release
append HERE; the next MINOR cycle rotates to a fresh
``test_features_v<MAJ>_<MIN>.py``. Every symbol pinned below was
verified against the working tree at authoring time (v14.4.0 T4) —
NOT blind-trusted from sibling-task descriptions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


def test_v14_4_0_intra_task_convergence_registered(project_root: Path) -> None:
    """W-18 v14.4.0: the T1 intra-task-convergence gate slice (G-005) has coverage.

    Discharges the W-18 precondition for the v14.4.0 CHANGELOG entry on the
    T1 slice (gate-domain NEST sub-fields + SOFT validator + AC-v2 metric
    runners). The stanza pins:

    (a) devolaflow.feedback: populate_intra_task_convergence + the
        INTRA_TASK_CONVERGENCE_TASK_TYPES / INTRA_TASK_MAX_ROUNDS_DEFAULT
        constants, including the warrant-rule behaviour (impl-class +
        non-empty acceptance_criteria_v2 → populate; else absence-canonical).
    (b) devolaflow.gate.scorer: validate_intra_task_convergence_fields
        (SOFT default, strict=True raises) + IntraTaskConvergenceViolationError.
    (c) The AC-v2 metric-runner path: METRIC_KIND_{COVERAGE,LINT,NUMBER}
        constants + the schema per-entry fields metric_kind / comparison.
    (d) schemas/lean-dispatch.yaml NEST sub-fields gate.intra_task_convergence
        + gate.intra_task_max_rounds.
    (e) references/decomposition-gate.md §6.2 (intra-task convergence) +
        §5.6 (legibility opt-in weight) doc surfaces.

    Source: .local/research/v14.2.0_gap_analysis.md §2.1 G-005 (NEST slice).
    """
    # --- (a) feedback helper + constants + warrant rule -----------------
    from devolaflow.feedback import (
        INTRA_TASK_CONVERGENCE_TASK_TYPES,
        INTRA_TASK_MAX_ROUNDS_DEFAULT,
        populate_intra_task_convergence,
    )

    assert frozenset({"code", "test", "config"}) == INTRA_TASK_CONVERGENCE_TASK_TYPES, (
        "W-18 v14.4.0 violation: INTRA_TASK_CONVERGENCE_TASK_TYPES drifted "
        "from the impl-class set {code, test, config}."
    )
    assert INTRA_TASK_MAX_ROUNDS_DEFAULT == 2, (
        "W-18 v14.4.0 violation: INTRA_TASK_MAX_ROUNDS_DEFAULT must stay 2 "
        "(mirrors execution-protocol §15.4 max-2 bounded self-fix ceiling)."
    )

    base = {"acceptance_criteria_v2": [{"id": "AC-1"}]}
    warranted = populate_intra_task_convergence(base, "code")
    assert warranted["gate"]["intra_task_convergence"] is True
    assert warranted["gate"]["intra_task_max_rounds"] == 2
    assert "gate" not in base, (
        "W-18 v14.4.0 violation: populate_intra_task_convergence mutated its input."
    )
    unwarranted = populate_intra_task_convergence(base, "review")
    assert "gate" not in unwarranted, (
        "W-18 v14.4.0 violation: non-impl task types must take the "
        "absence-canonical path (A-2.3 NEST contract)."
    )

    # --- (b) SOFT validator + strict-mode error --------------------------
    from devolaflow.gate.scorer import (
        IntraTaskConvergenceViolationError,
        validate_intra_task_convergence_fields,
    )

    assert validate_intra_task_convergence_fields(None) == []
    assert validate_intra_task_convergence_fields(warranted["gate"]) == []
    soft = validate_intra_task_convergence_fields({"intra_task_convergence": "yes"})
    assert len(soft) == 1 and "G-005" in soft[0], (
        "W-18 v14.4.0 violation: SOFT validator must return a G-005-citing "
        "warning for a non-bool intra_task_convergence."
    )
    with pytest.raises(IntraTaskConvergenceViolationError):
        validate_intra_task_convergence_fields({"intra_task_max_rounds": 0}, strict=True)

    # --- (c) AC-v2 metric-runner kinds + schema fields --------------------
    from devolaflow.gate.scorer import (
        METRIC_KIND_COVERAGE,
        METRIC_KIND_LINT,
        METRIC_KIND_NUMBER,
    )

    assert {METRIC_KIND_COVERAGE, METRIC_KIND_LINT, METRIC_KIND_NUMBER} == {
        "coverage",
        "lint",
        "number",
    }, "W-18 v14.4.0 violation: metric-runner kind literals drifted."

    schema_text = (project_root / "schemas/lean-dispatch.yaml").read_text(encoding="utf-8")
    for field in ("metric_kind:", "comparison:"):
        assert field in schema_text, (
            f"W-18 v14.4.0 violation: lean-dispatch.yaml missing the AC-v2 "
            f"per-entry field {field!r} (v14.4.0 metric runners)."
        )

    # --- (d) NEST sub-fields under gate -----------------------------------
    for sub_field in ("intra_task_convergence:", "intra_task_max_rounds:"):
        assert sub_field in schema_text, (
            f"W-18 v14.4.0 violation: lean-dispatch.yaml gate block missing "
            f"the NEST sub-field {sub_field!r} (G-005)."
        )

    # --- (e) decomposition-gate doc surfaces -------------------------------
    dg_text = (project_root / "workflow-system/agent/references/decomposition-gate.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "### 6.2 Intra-Task Convergence (v14.4.0",
        "### 5.6 Legibility Opt-In Weight (v14.4.0)",
    ):
        assert heading in dg_text, (
            f"W-18 v14.4.0 violation: decomposition-gate.md missing the "
            f"section heading starting {heading!r}."
        )


def test_v14_4_0_surgical_scope_registered(project_root: Path) -> None:
    """W-18 v14.4.0: the T2 surgical-scope mechanical verifier (F-P1) has coverage.

    Discharges the W-18 precondition for the v14.4.0 CHANGELOG entry on the
    T2 slice (BG-003 tier checks land as a Python module). The stanza pins:

    (a) lifecycle/validate_surgical_scope.py module + the 4 entry points
        (collect_diff_stats / check_module_scope / check_function_scope /
        evaluate_surgical_scope).
    (b) validate_surgical_scope + register_surgical_scope_hook re-exported
        via devolaflow.lifecycle.__all__.
    (c) The opt-in invariant: the handler is NOT in the default task_stop
        chain — default wiring is a v15.0.0 decision (ADR-003 cluster).
    (d) behavioral-guidelines.md BG-003 carries the "Enforcement:" line
        citing the module.

    Source: v15-cycle product review F-P1; tests/test_surgical_scope.py
    is the dedicated unit suite.
    """
    # --- (a) module + 4 entry points ------------------------------------
    from devolaflow.lifecycle.validate_surgical_scope import (
        check_function_scope,
        check_module_scope,
        collect_diff_stats,
        evaluate_surgical_scope,
    )

    for fn in (
        collect_diff_stats,
        check_module_scope,
        check_function_scope,
        evaluate_surgical_scope,
    ):
        assert callable(fn), f"W-18 v14.4.0 violation: {fn!r} is not callable."

    # --- (b) lifecycle package re-exports --------------------------------
    import devolaflow.lifecycle as lifecycle

    for symbol in ("validate_surgical_scope", "register_surgical_scope_hook"):
        assert symbol in lifecycle.__all__, (
            f"W-18 v14.4.0 violation: devolaflow.lifecycle.__all__ missing {symbol!r}."
        )

    # --- (c) opt-in invariant: NOT in the default task_stop chain ---------
    # clear_hooks clears EXTRAS only (defaults are immutable), so after the
    # clear the visible chain IS the default chain — the same mechanism
    # tests/test_surgical_scope.py AC-2 uses.
    from devolaflow.lifecycle import TASK_STOP_EVENT, clear_hooks, list_handlers
    from devolaflow.lifecycle.test_on_complete import test_on_complete

    clear_hooks(TASK_STOP_EVENT)
    assert list_handlers(TASK_STOP_EVENT) == (test_on_complete,), (
        "W-18 v14.4.0 violation: the default task_stop chain drifted from "
        "(test_on_complete,) — surgical-scope default wiring is a v15.0.0 "
        "decision and MUST stay opt-in at v14.4.x."
    )

    # --- (d) BG-003 Enforcement line --------------------------------------
    bg_text = (
        project_root / "workflow-system/agent/references/behavioral-guidelines.md"
    ).read_text(encoding="utf-8")
    assert "**Enforcement**: `src/devolaflow/lifecycle/validate_surgical_scope.py`" in bg_text, (
        "W-18 v14.4.0 violation: behavioral-guidelines.md BG-003 missing the "
        "Enforcement line citing lifecycle/validate_surgical_scope.py."
    )


def test_v14_4_0_context_profile_consolidation_registered(project_root: Path) -> None:
    """W-18 v14.4.0: the T3 context-profiles consolidation (G-006/G-026) has coverage.

    Discharges the W-18 precondition for the v14.4.0 CHANGELOG entry on the
    T3 slice. The stanza pins:

    (a) context_profiles.yaml `defaults.ac_generation` anchor aliased on
        exactly 17 implementation-class profiles, with the 7-profile exempt
        partition (verification/analysis classes) — 24 profiles total.
    (b) ac_generator.py _PATTERN_MIGRATION / _PATTERN_SETUP / _PATTERN_DESIGN.
    (c) Top-level `defaults:` + `summary_modes:` blocks; the relocated
        orphan opt-in blocks living under meta.legibility_audit +
        meta.session_state; and the 4 EOF back-compat aliases that keep
        raw top-level-key consumers working.

    Source: .local/research/v14.2.0_gap_analysis.md §2 G-006 + G-026.
    """
    profiles_path = project_root / "workflow-system/agent/context_profiles.yaml"
    parsed = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))

    # --- (a) 17-aliased / 7-exempt partition ----------------------------
    defaults_ac = parsed["defaults"]["ac_generation"]
    assert isinstance(defaults_ac, dict), (
        "W-18 v14.4.0 violation: defaults.ac_generation block missing from context_profiles.yaml."
    )
    profiles = parsed["profiles"]
    aliased = sorted(
        name
        for name, body in profiles.items()
        if isinstance(body, dict) and body.get("ac_generation") is defaults_ac
    )
    exempt = sorted(set(profiles) - set(aliased))
    assert len(aliased) == 17, (
        f"W-18 v14.4.0 violation: expected 17 impl-class profiles aliasing "
        f"defaults.ac_generation, found {len(aliased)}: {aliased}."
    )
    assert exempt == [
        "feedback",
        "product_verification",
        "research",
        "review",
        "verify_acceptance",
        "verify_interaction",
        "verify_visual",
    ], f"W-18 v14.4.0 violation: the 7-profile ac_generation exempt partition drifted: {exempt}."

    # --- (b) ac_generator description patterns ---------------------------
    from devolaflow import ac_generator

    for pattern_name in ("_PATTERN_MIGRATION", "_PATTERN_SETUP", "_PATTERN_DESIGN"):
        pattern = getattr(ac_generator, pattern_name, None)
        assert isinstance(pattern, re.Pattern), (
            f"W-18 v14.4.0 violation: ac_generator.{pattern_name} missing or not a compiled regex."
        )

    # --- (c) consolidation homes + back-compat aliases --------------------
    assert "defaults" in parsed and "summary_modes" in parsed, (
        "W-18 v14.4.0 violation: context_profiles.yaml lost the top-level "
        "defaults:/summary_modes: consolidation blocks."
    )
    for meta_home in ("legibility_audit", "session_state"):
        assert meta_home in parsed["meta"], (
            f"W-18 v14.4.0 violation: relocated opt-in block meta.{meta_home} missing."
        )
    # The 4 EOF aliases share content BY REFERENCE with their canonical
    # blocks (G-026 keeps raw top-level-key consumers working).
    assert parsed["legibility_audit"] is parsed["meta"]["legibility_audit"]
    assert parsed["session_state"] is parsed["meta"]["session_state"]
    assert parsed["complex_feature"] is parsed["summary_modes"]["complex_feature"]
    assert parsed["abstractive_llm"] is parsed["summary_modes"]["abstractive_llm"]


def test_v14_4_0_env_flag_taxonomy_registered(project_root: Path) -> None:
    """W-18 v14.4.0: the T4 env-flag taxonomy + AUTO_INSTALL honesty (G-023) has coverage.

    Discharges the W-18 precondition for the v14.4.0 CHANGELOG entry on the
    T4 slice. The stanza pins:

    (a) references/env-flags.md §6.A activation-pattern taxonomy (3 coexisting
        patterns per F-P5-4) + the normative "new flags MUST be pattern 1"
        guidance + the §7 W-20 checklist cross-link.
    (b) The §2.5 AUTO_INSTALL row stays `unwired` but carries the v14.4.0
        resolution (docs fixed; wiring-or-removal deferred to v15.0.0 G-021).
    (c) references/shell-proxy.md no longer advertises DEVOLAFLOW_AUTO_INSTALL
        as a working toggle — the honesty paragraph points at
        runtime-plugins.yaml#defaults.auto_install instead.
    (d) plugins/installer.py cargo-failure hint points at the yaml knob,
        never at the dead env var (S-5: advice must be actionable).

    Source: .local/research/v14.2.0_gap_analysis.md §2.4 G-023 remainder.
    """
    refs = project_root / "workflow-system/agent/references"

    # --- (a) §6.A taxonomy + normative guidance ---------------------------
    env_text = (refs / "env-flags.md").read_text(encoding="utf-8")
    assert "## 6.A Activation-pattern taxonomy (G-023, v14.4.0)" in env_text, (
        "W-18 v14.4.0 violation: env-flags.md missing the §6.A activation-pattern taxonomy section."
    )
    for fragment in (
        '**R5-strict literal-`"1"`**',
        "**Legacy truthy (loose match)**",
        "**Config-file-driven**",
        "**Normative guidance — new flags MUST be pattern 1 (R5 strict).**",
        "Pattern 2 is grandfathered for `DEVOLAFLOW_PLAN_MODE` only",
        "§7 W-20 enforcement",
    ):
        assert fragment in env_text, (
            f"W-18 v14.4.0 violation: env-flags.md §6.A missing {fragment!r}."
        )

    # --- (b) §2.5 unwired row → v15.2.0 B-6 RETIRED tombstone ----------------
    # v15.2.0 B-6 amendment: the wiring-or-removal decision the v14.4.0
    # G-023 row telegraphed ("DEFERRED to v15.0.0") RESOLVED to removal at
    # v15.2.0 — the §2.5 row is now a RETIRED tombstone that keeps the
    # unwired marker and the §-numbering. The v14.4.0 honesty contract
    # (name documented, never env-read, yaml knob is the control) is
    # preserved by the tombstone; the deferral-telegraph text was
    # discharged and therefore no longer pinned.
    assert "**Read surface** | unwired" in env_text, (
        "W-18 v14.4.0 violation: env-flags.md §2.5 must keep the unwired "
        "Read-surface marker (tombstoned at v15.2.0 B-6, still unwired)."
    )
    assert "### 2.5 `DEVOLAFLOW_AUTO_INSTALL` — RETIRED" in env_text, (
        "W-18 v14.4.0/v15.2.0 violation: env-flags.md §2.5 must carry the "
        "B-6 RETIRED tombstone (the G-023 deferral's resolution)."
    )
    assert "v14.4.0 (G-023)" in env_text, (
        "W-18 v14.4.0 violation: the §2.5 tombstone must cite the G-023 deferral it resolves."
    )

    # --- (c) shell-proxy.md honesty fix -------------------------------------
    shell_text = (refs / "shell-proxy.md").read_text(encoding="utf-8")
    assert "Plugin auto-install is NOT env-flag controlled" in shell_text, (
        "W-18 v14.4.0 violation: shell-proxy.md missing the §2 auto-install honesty paragraph."
    )
    assert "runtime-plugins.yaml#defaults.auto_install" in shell_text, (
        "W-18 v14.4.0 violation: shell-proxy.md must point at the live yaml knob."
    )
    # The bare flag may appear ONLY inside the honesty paragraph (negative
    # lookahead excludes the distinct DEVOLAFLOW_AUTO_INSTALL_PLUGINS flag).
    bare_mentions = re.findall(r"DEVOLAFLOW_AUTO_INSTALL(?!_)", shell_text)
    assert len(bare_mentions) == 1, (
        f"W-18 v14.4.0 violation: shell-proxy.md has {len(bare_mentions)} "
        "bare DEVOLAFLOW_AUTO_INSTALL mentions — expected exactly 1 (the "
        "honesty paragraph); stale working-toggle advertisements regressed."
    )

    # --- (d) installer.py actionable error text -----------------------------
    installer_text = (project_root / "src/devolaflow/plugins/installer.py").read_text(
        encoding="utf-8"
    )
    # v15.2.0 B-6 amendment: the negative lookahead excludes the LIVE
    # DEVOLAFLOW_AUTO_INSTALL_PLUGINS flag, which installer.py legitimately
    # cites since the B-6 default flip (RegistryDefaults docstring names the
    # explicit opt-in surfaces). Only the DEAD bare name stays banned.
    assert not re.search(r"DEVOLAFLOW_AUTO_INSTALL(?!_PLUGINS)", installer_text), (
        "W-18 v14.4.0 violation: installer.py still advises the dead "
        "DEVOLAFLOW_AUTO_INSTALL env var (S-5: advice must be actionable)."
    )
    assert "defaults.auto_install is false" in installer_text, (
        "W-18 v14.4.0/v15.2.0 violation: installer.py cargo-failure hint must "
        "state the runtime-plugins.yaml#defaults.auto_install knob's B-6 "
        "default (false) so the advice stays actionable."
    )


def test_v14_4_0_version_sync_fanout_reduction_registered(project_root: Path) -> None:
    """W-18 v14.4.0: the T6 version-sync fan-out reduction (G-031) has coverage.

    Discharges the W-18 precondition for the v14.4.0 CHANGELOG entry on the
    G-031 slice. Two former pattern-managed version surfaces become DERIVED
    (mechanism pins, not value pins — the per-bump value checks moved out of
    tests/test_version.py in the same change). The stanza pins:

    (a) README.md carries the shields.io dynamic TOML badge form (reads
        ``$.project.version`` from the main-branch raw pyproject.toml at
        render time) and NO static ``version-X.Y.Z-green`` badge literal.
    (b) benchmark-results/index.html derives its displayed version at load
        time via ``fetch('../version-timeline/versions.json'`` (newest
        entry); the in-file SAMPLE_DATA literal stays a clearly-marked
        static fallback that MAY lag.
    (c) .rules/conventions.mdc C-6 carries the "DERIVED, not pattern-managed
        (v14.4.0 G-031)" paragraph (canonical source; compiled into both
        corpus targets).
    (d) scripts/bump_version.py VERSION_LOCATIONS shrinks to 9 patterns
        across 7 unique files — neither derived surface is pattern-managed.

    Source: .local/research/v14.2.0_gap_analysis.md §2 G-031.
    """
    # --- (a) README dynamic badge, no static badge -----------------------
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    badge = re.search(r"https://img\.shields\.io/badge/dynamic/toml\?(\S+?)\)", readme)
    assert badge, (
        "W-18 v14.4.0 violation: README.md missing the shields.io dynamic "
        "TOML version badge (G-031)."
    )
    for fragment in (
        "query=%24.project.version",
        "url=https%3A%2F%2Fraw.githubusercontent.com%2FYoRHa-Agents%2FDevolaFlow"
        "%2Fmain%2Fpyproject.toml",
    ):
        assert fragment in badge.group(1), (
            f"W-18 v14.4.0 violation: README dynamic badge query missing {fragment!r}."
        )
    assert not re.search(r"badge/version-\d+\.\d+\.\d+-green", readme), (
        "W-18 v14.4.0 violation: README.md regrew a static version badge — "
        "no longer pattern-managed; it would silently go stale (C-6 / G-031)."
    )

    # --- (b) benchmark-demo load-time derivation ---------------------------
    bench_text = (
        project_root / "workflow-system/human/demo/benchmark-results/index.html"
    ).read_text(encoding="utf-8")
    assert "fetch('../version-timeline/versions.json'" in bench_text, (
        "W-18 v14.4.0 violation: benchmark-results/index.html lost the "
        "load-time versions.json derivation (G-031)."
    )
    assert "STATIC FALLBACK" in bench_text, (
        "W-18 v14.4.0 violation: the SAMPLE_DATA literal must stay clearly "
        "marked as a static file:// fallback that MAY lag."
    )

    # --- (c) C-6 DERIVED paragraph in the canonical rule source ------------
    conventions = (project_root / ".rules/conventions.mdc").read_text(encoding="utf-8")
    assert "DERIVED, not pattern-managed (v14.4.0 G-031)" in conventions, (
        "W-18 v14.4.0 violation: .rules/conventions.mdc C-6 missing the "
        "DERIVED-surfaces paragraph (G-031)."
    )

    # --- (d) VERSION_LOCATIONS shrunk to 9 patterns / 7 files --------------
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "bump_version_g031", project_root / "scripts/bump_version.py"
    )
    assert spec and spec.loader
    bump_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bump_mod)
    locations = bump_mod.VERSION_LOCATIONS
    paths = [loc["path"] for loc in locations]
    assert len(locations) == 9, (
        f"W-18 v14.4.0 violation: VERSION_LOCATIONS has {len(locations)} "
        "patterns, expected 9 (G-031 fan-out reduction)."
    )
    assert len(set(paths)) == 7, (
        f"W-18 v14.4.0 violation: VERSION_LOCATIONS spans {len(set(paths))} "
        "files, expected 7 (1 source-of-truth + 6 canonical sync per C-6)."
    )
    assert "workflow-system/human/demo/benchmark-results/index.html" not in paths, (
        "W-18 v14.4.0 violation: the benchmark-demo page regressed into "
        "VERSION_LOCATIONS — its version is load-time DERIVED (G-031)."
    )
    assert not any("green" in loc["pattern"] for loc in locations), (
        "W-18 v14.4.0 violation: a README static-badge pattern regressed "
        "into VERSION_LOCATIONS — the badge is render-time DERIVED (G-031)."
    )
