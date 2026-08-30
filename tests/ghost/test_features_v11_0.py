"""Ghost audit — per-cycle W-18 feature stanzas for the v11.0 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v11.0.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.ghost._helpers import _w18_research_artifact_path

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
#  2. D-P-4 — `references/plan-mode-enforcement.md`; registry-v3 now pins
#     its checklist contract and non-executable seed boundary.
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


_V11_0_0_PV01_DP4_SECTION_HEADING: str = "### 3.2 Checklist contract"


_V11_0_0_PV01_DP4_EXPLORE_CONVENTION: str = "Each item needs:"


_V11_0_0_PV01_DP4_REVISABLE_CONVENTION: str = "MUST NOT become an execution sequence"


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
    * D-P-4: the current `references/plan-mode-enforcement.md` §3.2
      preserves checklist fields while rejecting executable seed order.
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

    # D-P-4 lineage: current §3.2 checklist contract stays discoverable.
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
        f"W-18 current-contract violation: plan-mode §3.2 missing "
        f"{_V11_0_0_PV01_DP4_EXPLORE_CONVENTION!r}."
    )
    assert _V11_0_0_PV01_DP4_REVISABLE_CONVENTION in dp4_text, (
        f"W-18 current-contract violation: plan-mode §3.2 missing "
        f"{_V11_0_0_PV01_DP4_REVISABLE_CONVENTION!r}."
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
#     D-Q-3.md` §2). The current tuple retains the four canonical aliases
#     at positions 11-14 after v22 removed the retired events.
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
# the current DEFAULT_EVENTS shape and alias positions").
_V11_0_0_PV02_DQ3_ALIAS_TEST_NAMES: tuple[str, ...] = (
    "test_v11_0_0_pv02_dq3_alias_emits_byte_identical_to_canonical",
    "test_v11_0_0_pv02_dq3_both_names_accept_register_hook",
    "test_v11_0_0_pv02_dq3_both_names_propagate_to_run_hooks",
    "test_v22_default_events_length_is_15",
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
    * D-Q-3: 4-row PURE-ALIAS rename retaining 4 NEW canonical event
      names at positions 11-14 after v22 re-numbering;
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

    # v22 removes pre_shell_call and post_skill_edit; the current tuple
    # has 15 entries, with the four canonical aliases at positions 11-14.
    from devolaflow.lifecycle import DEFAULT_EVENTS

    assert len(DEFAULT_EVENTS) == 15, (
        f"W-18 v11.0.0 PV-02 violation: D-Q-3 §2 ships DEFAULT_EVENTS "
        f"with the retired events removed and the four canonical aliases "
        f"at positions 11-14; "
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
            f"{old_name!r} must be PRESERVED in DEFAULT_EVENTS "
            f"(PURE-ALIAS for 1-cycle deprecation)."
        )

    assert DEFAULT_EVENTS[10:14] == _V11_0_0_PV02_DQ3_NEW_CANONICAL_NAMES, (
        "v22 lifecycle re-numbering must keep the canonical aliases in positions 11-14"
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
_V11_0_2_PV02_BASELINE: Path = Path(
    "docs/cycle-archive/v15.2.0/evobench-baselines/v11.1.0_baseline.json"
)


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
    * Archived `v11.1.0_baseline.json` evidence from the W-16 wholesale
      regen at v11.1.0 cycle-start.
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
    # Historical schema sanity: top-level keys are scenario names and each
    # entry retains the retired baseline record fields.
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
            f"missing archived record field {required_field!r}."
        )

    # SKILL.md must cite the current CASCADE_REQUIRED/default-3 contract.
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
    assert "L0 Project → L1 Wave → L2 Task" in sub_table, (
        "W-18 v11.0.2 PV-02 violation: SKILL.md Quick Action Decision "
        "section must cite the current three-layer cascade chain per the "
        "operator-quotable verdict rule."
    )
    assert "default 3" in sub_table

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
    "CASCADE_REQUIRED",
    "default 3",
    "L0 Project → L1 Wave → L2 Task",
)


# SKILL.md negative surface — Layer collapse pattern wording REMOVED (G-CASCADE-1).
_V11_0_3_PV03_SKILL_NEGATIVE_SUBSTRING: str = "L0→L1→L2→L3 cascade"


def test_v11_0_3_pv03_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.0.3 PV-03: G-CASCADE-1 + G-CASCADE-2 new surfaces are pinned.

    Discharges the W-18 precondition for the v11.0.3 PV-03 CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Current pin: SKILL publishes `CASCADE_REQUIRED`, default 3, and the
    three-layer chain. The historical trace remains discoverable as a Tier-3
    provenance example but no longer defines the active cascade.
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

    assert (project_root / _V11_0_3_PV03_MULTI_STAGE_TRACE).is_file()
    assert "examples/multi-stage-trace.md" in skill_text


# G-PLAN-1 + G-PLAN-2 + schema NEST surfaces (v11.0.4 PV-04).
_V11_0_4_PV04_PLAN_MODE_DOC: Path = Path(
    "workflow-system/agent/references/plan-mode-enforcement.md"
)


_V11_0_4_PV04_SCHEMA: Path = Path("schemas/lean-dispatch.yaml")


_V11_0_4_PV04_TASK_ADAPTIVE: Path = Path("src/devolaflow/task_adaptive_selector.py")


# v14.5.0 (ADR-006 G-025) ghost-pin update: the W02 populate helper
# (formerly feedback.py) and the W03 soft validator (formerly
# gate/scorer.py) both moved VERBATIM to the new owner module
# src/devolaflow/gate/cascade.py; the historical import paths keep working
# via permanent identity-preserving re-export shims (pinned by
# tests/test_module_split_shims.py). The two source-text pins below follow
# the re-export truth's owner module.
_V11_0_4_PV04_FEEDBACK: Path = Path("src/devolaflow/gate/cascade.py")


_V11_0_4_PV04_GATE_SCORER: Path = Path("src/devolaflow/gate/cascade.py")


# plan-mode-enforcement.md positive surfaces — must appear post-edit.
_V11_0_4_PV04_PLAN_MODE_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "`CASCADE_REQUIRED` three-layer contract",
    "`gate.cascade_min_layers: 3` (default 3)",
    "L0 Project → L1 Wave → L2 Task",
)

# PV-04 bumped plan-mode-enforcement.md's frontmatter to 2026-05-08. The
# witness is MONOTONIC (>=), not a literal pin: the file is under the F-09
# 90-day freshness window (tests/test_reference_frontmatter_freshness.py),
# so its last_updated legitimately moves forward at every refresh; a
# literal date pin would break at each refresh (first hit: the 2026-08-19
# post-clean_repo refresh). A date BEFORE the floor would mean the PV-04
# bump was reverted — that is what this witness guards against.
_V11_0_4_PV04_PLAN_MODE_LAST_UPDATED_FLOOR = "2026-05-08"
_LAST_UPDATED_RE = re.compile(r'^last_updated:\s*"(\d{4}-\d{2}-\d{2})"\s*$', re.MULTILINE)


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

    * ``workflow-system/agent/references/plan-mode-enforcement.md`` publishes
      the current `CASCADE_REQUIRED`, default-3, three-layer contract.
    * Same file frontmatter ``last_updated`` is at or after the PV-04
      bump date ``"2026-05-08"`` (monotonic floor — see
      ``_V11_0_4_PV04_PLAN_MODE_LAST_UPDATED_FLOOR``; the literal pin
      was relaxed 2026-08-19 because the file sits inside the F-09
      90-day freshness window and refreshes forward by design).
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
    last_updated_match = _LAST_UPDATED_RE.search(plan_mode_text)
    assert last_updated_match is not None, (
        "W-18 v11.0.4 PV-04 violation: plan-mode-enforcement.md frontmatter "
        'is missing its `last_updated: "YYYY-MM-DD"` line.'
    )
    assert last_updated_match.group(1) >= _V11_0_4_PV04_PLAN_MODE_LAST_UPDATED_FLOOR, (
        f"W-18 v11.0.4 PV-04 violation: plan-mode-enforcement.md frontmatter "
        f"last_updated={last_updated_match.group(1)!r} is BEFORE the PV-04 bump "
        f"floor {_V11_0_4_PV04_PLAN_MODE_LAST_UPDATED_FLOOR!r} — the PV-04 "
        f"frontmatter bump appears to have been reverted."
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
        "W-18 v11.0.4 PV-04 violation: gate/cascade.py (owner module since "
        "v14.5.0 ADR-006; shimmed at feedback.py) must export the "
        "`populate_cascade_gate_fields` helper per W02."
    )

    gate_scorer_text = (project_root / _V11_0_4_PV04_GATE_SCORER).read_text(encoding="utf-8")
    assert "def validate_cascade_gate_fields(" in gate_scorer_text, (
        "W-18 v11.0.4 PV-04 violation: gate/cascade.py (owner module since "
        "v14.5.0 ADR-006; shimmed at gate/scorer.py) must export the "
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


# The built-in harness preserves the four retired cascade/collapse scenario
# identities as explicit historical provenance.
_V11_0_5_PV05_HARNESS_FIXTURES: tuple[tuple[Path, tuple[str, ...]], ...] = (
    (
        Path("tests/fixtures/harness/hierarchy_complex_cascade.yaml"),
        (
            "legacy-evobench:cascade_l0_l1_l2_l3_standard",
            "legacy-evobench:cascade_l0_l1_l2_l3_complex",
        ),
    ),
    (
        Path("tests/fixtures/harness/hierarchy_trivial_collapse.yaml"),
        (
            "legacy-evobench:collapse_l0_l3_simple",
            "legacy-evobench:collapse_l0_l3_trivial",
        ),
    ),
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
# v14.5.0 (ADR-006 G-025) ghost-pin update: both symbols' DEFINITIONS moved
# to src/devolaflow/gate/cascade.py, so the dead-API detector (which keys
# the allowlist on the DEFINING module) tracks them at the new paths; the
# historical import paths remain shimmed.
_V11_0_5_PV05_NEW_ALLOWLIST_ENTRIES: tuple[str, ...] = (
    '"devolaflow.gate.cascade:populate_cascade_gate_fields"',
    '"devolaflow.gate.cascade:validate_cascade_gate_fields"',
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
    * Two built-in harness fixtures preserve the four retired G-BENCH-1
      cascade-vs-collapse scenario identities as ``legacy-evobench:``
      provenance; W-17 adds no test function.
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
      * Historical EvoBench evidence is retained in the cycle archive;
        live cascade/collapse contracts are carried by harness fixtures.
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

    for fixture_path, provenance in _V11_0_5_PV05_HARNESS_FIXTURES:
        full_path = project_root / fixture_path
        assert full_path.is_file(), (
            f"W-18 v11.0.5 PV-05 violation: harness fixture {fixture_path} "
            f"missing for the retired G-BENCH-1 contract."
        )
        fixture_text = full_path.read_text(encoding="utf-8")
        for source in provenance:
            assert source in fixture_text, (
                f"W-18 v11.0.5 PV-05 violation: {fixture_path} lost "
                f"historical provenance {source!r}."
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
