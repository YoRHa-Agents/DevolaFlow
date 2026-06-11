"""Ghost audit — per-cycle W-18 feature stanzas for the v12.3 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v12.3.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

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
    assert 'lines: "479-481"' in profiles_text, (
        f"W-18 v12.3.0 PV-03 violation: {_V12_3_0_PV03_CONTEXT_PROFILES} missing "
        f'the post-collapse `lines: "479-481"` anchor for task_quality_score '
        f"(v12.3.0 PV-03 landed 480-482; re-anchored -1 by the v14.2.2 "
        f"G-017/G-020 SKILL.md line shifts). The line-anchor update MUST land "
        f"in the same PR as the SKILL.md restructure."
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
