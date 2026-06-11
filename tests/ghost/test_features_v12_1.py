"""Ghost audit — per-cycle W-18 feature stanzas for the v12.1 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v12.1.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

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
