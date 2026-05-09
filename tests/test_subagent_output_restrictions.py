"""v12.1.0 D-1 + D-2: subagent output restrictions + hang prevention pins.

Pins the SKILL.md normative content added in v12.1.0 to close the two
BLOCKER deficiencies surfaced in ``.local/feedbacks/feedback_for_v12.0.0.md``:

* **D-1** — Task Quality Score scope is now explicitly L0-ONLY in
  ``workflow-system/agent/SKILL.md`` §"Task Quality Score (L0 ONLY)".
  Subagent reports (TaskReport / WaveReport / StageReport) DO NOT
  carry a ``quality_score`` field. See also §"Reporting completion"
  exclusion bullet.

* **D-2** — A new SKILL.md §"Subagent Hang Prevention" subsection
  surfaces the L0 timeout contract (per task-type budget),
  the L3 forbidden-pattern set (5 canonical hang vectors:
  ``AskQuestion``, recursive ``Task`` tool re-entry, unbounded
  ``Shell``, unbounded ``WebFetch`` / ``WebSearch``, internal loops
  without ``max_iterations``), the L3 progress-heartbeat contract,
  and the L0 hang-detection escalation per P4.

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
_REPORTING_COMPLETION_HEADING_PATTERN: re.Pattern[str] = re.compile(
    r"^\*\*Reporting completion:\*\*$",
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
    * the section heading line contains the literal ``(L0 ONLY)`` token
      (operator-visible scoping marker per gap analysis §2 D-1 fix #1)
    * the section body contains BOTH literal substrings ``L0 ONLY``
      AND ``Subagents MUST NOT`` (the explicit prohibition per fix #1).

    Failure mode: SKILL.md edit drifted; either the marker was dropped
    from the heading or the body lost the explicit prohibition.
    """
    heading_match = _TASK_QUALITY_HEADING_PATTERN.search(skill_md_text)
    assert heading_match is not None, (
        "v12.1.0 D-1 violation: SKILL.md missing the §'Task Quality Score' "
        "heading. The heading MUST be a level-2 ## heading per the "
        "v12.1.0 acceptance criteria."
    )
    heading_line = heading_match.group(0)
    assert "(L0 ONLY)" in heading_line, (
        f"v12.1.0 D-1 violation: SKILL.md §'Task Quality Score' heading "
        f"missing '(L0 ONLY)' marker. Got: {heading_line!r}. The marker "
        "MUST sit on the heading line so subagents reading the section "
        "in isolation see the scoping marker before the body."
    )

    body = _section_body(skill_md_text, _TASK_QUALITY_HEADING_PATTERN)
    assert "L0 ONLY" in body, (
        "v12.1.0 D-1 violation: SKILL.md §'Task Quality Score' body "
        "missing literal 'L0 ONLY'. The literal MUST appear at least "
        "once in the body so a substring grep against the section "
        "(e.g. via task_adaptive_selector when the section is included "
        "without surrounding chrome) still catches the marker."
    )
    assert "Subagents MUST NOT" in body, (
        "v12.1.0 D-1 violation: SKILL.md §'Task Quality Score' body "
        "missing literal 'Subagents MUST NOT'. The explicit prohibition "
        "is the canonical anti-rationalization line — if a subagent "
        "reads only this section it MUST see 'Subagents MUST NOT score' "
        "verbatim."
    )


def test_skill_md_reporting_completion_excludes_quality_score(skill_md_text: str) -> None:
    """v12.1.0 D-1: §'Reporting completion' bullet excludes quality_score.

    Asserts the §"Dispatch & Report Protocol" → "Reporting completion"
    bullet list contains a line stating subagent reports DO NOT
    include a ``quality_score`` field. This closes the StatusReport
    contract gap surfaced in gap analysis §2 D-1 (fix #2).

    Failure mode: SKILL.md edit dropped the exclusion bullet; subagents
    reading the dispatch protocol section without seeing §"Task
    Quality Score (L0 ONLY)" might still infer they should emit a
    score.
    """
    body = _section_body(skill_md_text, _REPORTING_COMPLETION_HEADING_PATTERN)
    assert "quality_score" in body.lower() or "quality_score" in body, (
        "v12.1.0 D-1 violation: SKILL.md §'Reporting completion' body "
        "missing any mention of 'quality_score'. The exclusion bullet "
        "MUST cite the field name verbatim so a grep over the report "
        "schema's allowed-fields surface picks it up."
    )
    has_exclusion = any(
        marker in body
        for marker in (
            "DO NOT include `quality_score`",
            "DO NOT include quality_score",
            "do NOT include `quality_score`",
            "do NOT include quality_score",
        )
    )
    assert has_exclusion, (
        "v12.1.0 D-1 violation: SKILL.md §'Reporting completion' body "
        "does not state subagent reports DO NOT include a "
        "'quality_score' field. The exclusion line MUST be explicit "
        "(case-insensitive 'DO NOT include quality_score' phrasing) so "
        "a subagent reading just the dispatch protocol cannot rationalize "
        "score-emission."
    )


def test_skill_md_hang_prevention_section_present(skill_md_text: str) -> None:
    """v12.1.0 D-2: §'Subagent Hang Prevention' section + 5 forbidden patterns.

    Asserts SKILL.md contains a section whose heading contains the
    literal ``Hang Prevention`` substring AND whose body lists the 5
    canonical forbidden hang vectors enumerated in gap analysis §2 D-2:

    1. ``AskQuestion`` (no human channel)
    2. recursive ``Task`` tool re-entry (P5 invariant)
    3. unbounded ``Shell`` calls (every call needs ``block_until_ms``)
    4. unbounded ``WebFetch`` / ``WebSearch`` (verify upstream timeouts)
    5. internal loops without ``max_iterations``

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
        "AskQuestion",
        "Task",
        "Shell",
        "WebFetch",
        "WebSearch",
        "max_iterations",
    )
    missing = [s for s in expected_substrings if s not in body]
    assert not missing, (
        f"v12.1.0 D-2 violation: SKILL.md §'Subagent Hang Prevention' "
        f"body missing expected forbidden-pattern substrings {missing!r}. "
        "The 5 canonical hang vectors enumerated in gap analysis §2 D-2 "
        "MUST all surface in the body so a subagent reading the section "
        "sees the complete forbidden set, not a subset."
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
    """v12.1.0 D-2 details: forbidden-patterns list enumerates all 5 vectors.

    Tighter than ``test_skill_md_hang_prevention_section_present`` —
    this asserts the body specifically mentions the operationalized
    hang-prevention primitives (NOT just the bare tool/keyword names):

    * ``AskQuestion`` — no human channel below L0
    * recursive ``Task`` tool re-entry — the P5 leaf invariant phrasing
    * ``Shell`` + ``block_until_ms`` — every call carries a deadline
    * ``WebFetch`` / ``WebSearch`` + ``timeout`` — upstream timeout
      coverage required
    * ``max_iterations`` — every loop has a ceiling

    Failure mode: SKILL.md edit kept the section heading but reduced
    the forbidden-pattern bullets to a generic prose paragraph that
    drops the operational primitives.
    """
    body = _section_body(skill_md_text, _HANG_PREVENTION_HEADING_PATTERN)

    required_pairs = (
        ("AskQuestion", "AskQuestion verbatim (no human channel below L0)"),
        ("Task", "recursive `Task` tool re-entry (P5 invariant)"),
        ("Shell", "unbounded Shell forbidden"),
        ("block_until_ms", "Shell call deadline primitive"),
        ("WebFetch", "WebFetch upstream-timeout coverage"),
        ("WebSearch", "WebSearch upstream-timeout coverage"),
        ("timeout", "timeout discipline phrasing"),
        ("max_iterations", "internal-loop ceiling primitive"),
    )

    for needle, description in required_pairs:
        assert needle in body, (
            f"v12.1.0 D-2 violation: SKILL.md §'Subagent Hang Prevention' "
            f"body missing required substring {needle!r} ({description}). "
            "Each of the 5 forbidden-pattern vectors MUST cite its "
            "canonical operational primitive verbatim — the bare "
            "category name without the primitive lets subagents skip "
            "the actual prevention mechanic."
        )
