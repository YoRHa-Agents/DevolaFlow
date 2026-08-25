"""v12.1.0 D-1 + D-2: subagent output restrictions + hang prevention pins.

Pins the SKILL.md normative content added in v12.1.0 to close the two
BLOCKER deficiencies surfaced in ``.local/feedbacks/feedback_for_v12.0.0.md``:

* **D-1** — Task Quality Score scope is now explicitly L0-ONLY in
  ``workflow-system/agent/SKILL.md`` §"Task Quality Score (L0 ONLY)".
  L2 StatusReport and L1 WaveReport DO NOT carry a ``quality_score``
  field. See also §"Dispatch & Report Protocol".

* **D-2** — A new SKILL.md §"Subagent Hang Prevention" subsection
  surfaces the L0 timeout contract (per task-type budget),
  the L2 Task leaf contract (no human questions or child-agent spawning),
  bounded ``Shell`` / Web calls, loops with ``max_iterations``, the L2
  progress-heartbeat contract, and the L0 hang-detection escalation per P4.

These tests are positive-substring pins: failing means the SKILL.md
content drifted away from the contract surfaced by v12.1.0. Source:
``.local/research/v12.1.0_gap_analysis.md`` §2 D-1 + §2 D-2.

The companion W-18 ghost-audit refresh stanza
(``test_v12_1_0_subagent_output_restrictions``) lives in
``tests/test_no_ghost_features.py`` and cross-pins the same surfaces
from the no-ghost-features audit lens; this file pins the SKILL.md
contract per se.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SKILL_PATH: Path = Path("workflow-system/agent/SKILL.md")
_SKILL_LINE_CEILING: int = 500
_HANG_PREVENTION_HEADING_PATTERN: re.Pattern[str] = re.compile(
    r"^#{2,3}\s+.*Hang Prevention",
    re.MULTILINE,
)
_TASK_QUALITY_HEADING_PATTERN: re.Pattern[str] = re.compile(
    r"^#{2}\s+Task Quality Score.*$",
    re.MULTILINE,
)
_DISPATCH_REPORT_HEADING_PATTERN: re.Pattern[str] = re.compile(
    r"^##\s+Dispatch & Report Protocol$",
    re.MULTILINE,
)


@pytest.fixture(scope="module")
def project_root() -> Path:
    """Return the repository root (parent of the ``tests/`` directory)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def skill_md_text(project_root: Path) -> str:
    """Read SKILL.md as text once per test module."""
    return (project_root / _SKILL_PATH).read_text(encoding="utf-8")


def _section_body(text: str, heading_pattern: re.Pattern[str]) -> str:
    """Return the body of the section matched by ``heading_pattern``.

    The body runs from the matched heading line through (but not
    including) the next ``#``-prefixed heading at any depth, OR end of
    file. Per S-5 (no silent failure) raises ``LookupError`` when the
    heading is absent — this prevents tests from passing on a vacuous
    empty body when the section was removed.
    """
    match = heading_pattern.search(text)
    if match is None:
        msg = f"Heading not found for pattern: {heading_pattern.pattern!r}"
        raise LookupError(msg)
    body_start = match.end()
    next_heading = re.search(r"^#{1,6}\s+", text[body_start:], re.MULTILINE)
    body_end = body_start + next_heading.start() if next_heading else len(text)
    return text[body_start:body_end]


def test_skill_md_task_quality_score_marked_l0_only(skill_md_text: str) -> None:
    """v12.1.0 D-1: §"Task Quality Score" header carries the L0-only marker.

    Asserts BOTH:
    * the section body contains the literal ``L0 ONLY`` marker;
    * the body explicitly forbids subagent rubric loading/scoring/emission.

    Failure mode: SKILL.md edit drifted; either the marker was dropped
    from the heading or the body lost the explicit prohibition.
    """
    heading_match = _TASK_QUALITY_HEADING_PATTERN.search(skill_md_text)
    assert heading_match is not None, (
        "v12.1.0 D-1 violation: SKILL.md missing the §'Task Quality Score' "
        "heading. The heading MUST be a level-2 ## heading per the "
        "v12.1.0 acceptance criteria."
    )
    body = _section_body(skill_md_text, _TASK_QUALITY_HEADING_PATTERN)
    assert "L0 ONLY" in body, (
        "v12.1.0 D-1 violation: SKILL.md §'Task Quality Score' body "
        "must carry the literal L0-only scope marker."
    )
    assert "subagents MUST NOT load, score, or emit this rubric" in body, (
        "v12.1.0 D-1 violation: SKILL.md §'Task Quality Score' body "
        "must prohibit lower layers from loading, scoring, or emitting "
        "the workflow-close rubric."
    )
    assert "DevolaFlow vX.Y.Z" in body, (
        "v12.3.0 banner-contract violation: the L0 score footer must "
        "carry the orchestrator version."
    )


def test_skill_md_reporting_completion_excludes_quality_score(skill_md_text: str) -> None:
    """v12.1.0 D-1: report protocol excludes quality_score.

    Asserts §"Dispatch & Report Protocol" states that subagent reports
    never include a ``quality_score`` field. This closes the StatusReport
    contract gap surfaced in gap analysis §2 D-1.

    Failure mode: SKILL.md edit dropped the exclusion bullet; subagents
    reading the dispatch protocol section without seeing §"Task
    Quality Score (L0 ONLY)" might still infer they should emit a
    score.
    """
    body = _section_body(skill_md_text, _DISPATCH_REPORT_HEADING_PATTERN)
    assert "quality_score" in body, (
        "v12.1.0 D-1 violation: SKILL.md §'Dispatch & Report Protocol' body "
        "missing any mention of 'quality_score'. The exclusion bullet "
        "MUST cite the field name verbatim so a grep over the report "
        "schema's allowed-fields surface picks it up."
    )
    assert "Subagents DO NOT include `quality_score`" in body, (
        "v12.1.0 D-1 violation: SKILL.md §'Dispatch & Report Protocol' "
        "must explicitly prohibit quality_score in L1/L2 reports."
    )
    assert "L2 emits falsifiable evidence" in body and "numeric score" in body, (
        "Evidence-only doctrine violation: L2 reports must carry "
        "falsifiable evidence rather than self-awarded scores."
    )


def test_skill_md_hang_prevention_section_present(skill_md_text: str) -> None:
    """v12.1.0 D-2: §'Subagent Hang Prevention' preserves the L2 leaf contract.

    Pins no human questions, no child-agent spawning, bounded tool calls,
    bounded loops, heartbeat reporting, and four-hop escalation.

    Failure mode: SKILL.md edit dropped the section or the forbidden-
    patterns list shrank below the canonical 5.
    """
    heading_match = _HANG_PREVENTION_HEADING_PATTERN.search(skill_md_text)
    assert heading_match is not None, (
        "v12.1.0 D-2 violation: SKILL.md missing a heading containing "
        "'Hang Prevention'. The new subsection MUST land per gap "
        "analysis §2 D-2 (recommended placement: between §'Context "
        "Isolation' and §'Dispatch & Report Protocol', OR as a "
        "subsection under §'Dispatch & Report Protocol')."
    )

    body = _section_body(skill_md_text, _HANG_PREVENTION_HEADING_PATTERN)

    expected_substrings = (
        "L2 `AskQuestion` is forbidden",
        "Recursive `Task` re-entry is forbidden",
        "Unbounded `Shell` is forbidden",
        "Unbounded `WebFetch` and `WebSearch` are forbidden",
        "max_iterations",
        "every five minutes",
        "Task → Wave → Project → Human",
    )
    missing = [s for s in expected_substrings if s not in body]
    assert not missing, (
        f"v12.1.0 D-2 violation: SKILL.md §'Subagent Hang Prevention' "
        f"body missing expected leaf/bounded-execution substrings {missing!r}."
    )


def test_skill_md_under_500_lines(project_root: Path) -> None:
    """v12.1.0 C-4 defence in depth: SKILL.md stays below 500 lines.

    Mirrors the canonical ``test_skill_md_under_500_lines`` check that
    lives in ``tests/test_integration.py`` (Default tier ceiling per
    rule C-4). v12.1.0 adds a new section + a few exclusion lines —
    this test is the local belt to ``test_integration.py``'s
    suspenders, ensuring the v12.1.0 PV cannot land if the additive
    edits accidentally cross the ceiling.

    Failure mode: SKILL.md crossed the C-4 default-tier ceiling.
    """
    skill_path = project_root / _SKILL_PATH
    line_count = sum(1 for _ in skill_path.read_text(encoding="utf-8").splitlines())
    assert line_count < _SKILL_LINE_CEILING, (
        f"C-4 default-tier violation: {_SKILL_PATH} has {line_count} lines "
        f"(ceiling: {_SKILL_LINE_CEILING - 1} = strictly less than "
        f"{_SKILL_LINE_CEILING}). The v12.1.0 additive edits MUST stay "
        "under the ceiling; if you exceed it, trim other sections to "
        "absorb the delta rather than raise the ceiling."
    )


def test_skill_md_l3_forbidden_patterns_complete(skill_md_text: str) -> None:
    """v12.1.0 D-2 details: L2 Task remains a bounded leaf agent.

    Retains evidence/quality isolation, no child spawning, bounded retry,
    heartbeat reporting, and Task → Wave → Project → Human escalation.
    """
    body = _section_body(skill_md_text, _HANG_PREVENTION_HEADING_PATTERN)

    required_pairs = (
        ("L2 `AskQuestion` is forbidden", "no direct human channel"),
        ("Recursive `Task` re-entry is forbidden", "no child-agent spawning"),
        ("block_until_ms", "bounded Shell execution"),
        ("Unbounded `WebFetch` and `WebSearch` are forbidden", "bounded Web execution"),
        ("timeout", "upstream timeout discipline"),
        ("max_iterations", "internal-loop ceiling primitive"),
        ("every five minutes", "progress-heartbeat contract"),
        ("Task → Wave → Project → Human", "four-hop escalation chain"),
    )

    for needle, description in required_pairs:
        assert needle in body, (
            f"v12.1.0 D-2 violation: SKILL.md §'Subagent Hang Prevention' "
            f"body missing required substring {needle!r} ({description}). "
            "The compact contract must preserve every leaf/bounded-retry "
            "primitive after the 3-layer migration."
        )

    assert "| **L2 Task**" in skill_md_text, (
        "3-layer migration violation: SKILL.md must identify L2 Task as "
        "the sole implementation leaf."
    )
    assert "self-verify; report evidence" in skill_md_text, (
        "Evidence-only doctrine violation: L2 Task must self-verify and "
        "report evidence rather than self-score."
    )
