"""Focused tests for the pure v16 checklist and stage parser."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from devolaflow.agent_workspace.round_parser import (
    PriorityChange,
    RoundArtifactParseError,
    RoundPick,
    parse_checklist,
    parse_frontmatter,
    parse_stage,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent-workspace" / "v16"


def _checklist_text(*, item_line: str, metadata: str) -> str:
    return f"""\
---
parent: parser-test
schema_version: 1
total_items: 1
checked: 0
priority_dist: {{P0: 1, P1: 0, P2: 0}}
reverted_open: 0
---

# Checklist

## G1: Preserve exact parser inputs
{item_line}
{metadata}
"""


def _stage_text(*, priority_lines: str, history_lines: str) -> str:
    return f"""\
---
parent: parser-test
schema_version: 1
current_round: 2
max_rounds: 4
capacity_per_round: 5
---

# Stage — Round Control

## Priority Settings
{priority_lines}

## Round History
{history_lines}

## Next Round Plan
- Candidates: []
- Estimated remaining rounds: 0
"""


def test_parse_frontmatter_returns_frozen_artifact() -> None:
    artifact = parse_frontmatter("---\ncount: 2\n---\n\n# Body\n", filename="sample.md")

    assert artifact.frontmatter == {"count": 2}
    assert artifact.body == "\n# Body"
    with pytest.raises(FrozenInstanceError):
        artifact.body = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("# Body\n", "must start"),
        ("---\nkey: value\n", "missing its closing"),
        ("---\nkey: [\n---\n", "not valid YAML"),
        ("---\n- one\n---\n", "must decode to a mapping"),
    ],
)
def test_parse_frontmatter_reports_stable_errors(text: str, message: str) -> None:
    with pytest.raises(RoundArtifactParseError) as raised:
        parse_frontmatter(text, filename="broken.md")

    assert raised.value.filename == "broken.md"
    assert raised.value.kind == raised.value.code == "FRONTMATTER_PARSE"
    assert message in raised.value.message


def test_parse_checklist_preserves_order_metadata_and_reversion_text() -> None:
    fixture = parse_checklist((FIXTURE_DIR / "checklist.md").read_text(encoding="utf-8"))
    reverted = parse_checklist(
        _checklist_text(
            item_line="- [ ] C-G1.1 (P0) The parser preserves the user's exact reason",
            metadata=(
                "      verify: metric: parser.verbatim == true\n"
                "      depends: [C-G2.1, C-G3.2]\n"
                '      reverted: Keep "quotes", arrows ->, and spaces exactly'
                " | at: 2026-08-24T10:30:00Z"
            ),
        )
    )

    assert [item.source_index for item in fixture.items] == [0, 1, 2]
    assert fixture.goal_headings[0] == (
        "G1",
        "Keep v16 workspace state internally consistent",
    )
    item = reverted.items[0]
    assert item.item_id == "C-G1.1"
    assert item.goal_id == "G1"
    assert item.priority == "P0"
    assert item.assertion == "The parser preserves the user's exact reason"
    assert item.verify == "metric: parser.verbatim == true"
    assert item.depends == ("C-G2.1", "C-G3.2")
    assert item.reverted_reason == 'Keep "quotes", arrows ->, and spaces exactly'
    assert item.metadata[-1].startswith('      reverted: Keep "quotes"')


@pytest.mark.parametrize(
    ("item_line", "metadata", "message"),
    [
        ("- [ ] malformed", "      verify: manual", "canonical checkbox"),
        (
            "- [ ] C-G1.1 (P0) Assertion",
            "      verify: manual\n      depends: [not-an-id]",
            "invalid checklist item id",
        ),
        (
            "- [ ] C-G1.1 (P0) Assertion",
            "      verify: manual\n      reverted: missing timestamp",
            "reverted metadata",
        ),
    ],
)
def test_parse_checklist_rejects_malformed_canonical_syntax(
    item_line: str,
    metadata: str,
    message: str,
) -> None:
    with pytest.raises(RoundArtifactParseError) as raised:
        parse_checklist(_checklist_text(item_line=item_line, metadata=metadata))

    assert raised.value.kind == "CHECKLIST_ITEM_PARSE"
    assert message in raised.value.message


def test_parse_stage_supports_empty_history_fixture() -> None:
    stage = parse_stage((FIXTURE_DIR / "stage.md").read_text(encoding="utf-8"))

    assert stage.current_round == 0
    assert stage.max_rounds == 3
    assert stage.capacity_per_round == 5
    assert stage.initial_priorities == (
        RoundPick("C-G1.1", "P0"),
        RoundPick("C-G1.2", "P1"),
        RoundPick("C-G2.1", "P2"),
    )
    assert stage.priority_changes == ()
    assert stage.history == ()


def test_parse_stage_preserves_changes_and_populated_history() -> None:
    stage = parse_stage(
        _stage_text(
            priority_lines=(
                "- 2026-08-24T09:00:00Z initial: "
                "P0=[C-G1.1] P1=[C-G1.2] P2=[]\n"
                "- 2026-08-24T10:30:00Z adjustment: "
                'C-G1.2 P1 -> P0 | user: "Run this -> next, exactly."'
            ),
            history_lines=(
                "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |\n"
                "|---|---|---|---|---|---|---|\n"
                "| 1 | C-G1.1(P0) | W1 | 1/1 | 0 | "
                ".local/checkpoints/cp_round_1.yaml | 87.2 |\n"
                "| 2 | C-G1.2(P0) | W1, W2 | 0/1 | 1 | "
                ".local/checkpoints/cp_round_2.yaml | null |"
            ),
        )
    )

    assert stage.priority_changes == (
        PriorityChange(
            timestamp="2026-08-24T10:30:00Z",
            item_id="C-G1.2",
            from_priority="P1",
            to_priority="P0",
            user_text='"Run this -> next, exactly."',
        ),
    )
    assert stage.history[0].picked == (RoundPick("C-G1.1", "P0"),)
    assert stage.history[0].gate_trend == 87.2
    assert stage.history[1].waves == ("W1", "W2")
    assert stage.history[1].checked_count == 0
    assert stage.history[1].picked_count == 1
    assert stage.history[1].blockers == 1
    assert stage.history[1].gate_trend is None


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            _stage_text(
                priority_lines="- invalid initial priorities",
                history_lines=(
                    "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |\n"
                    "|---|---|---|---|---|---|---|"
                ),
            ),
            "canonical initial",
        ),
        (
            _stage_text(
                priority_lines=("- 2026-08-24T09:00:00Z initial: P0=[C-G1.1] P1=[] P2=[]"),
                history_lines="| wrong header |\n|---|",
            ),
            "canonical table header",
        ),
        (
            _stage_text(
                priority_lines=("- 2026-08-24T09:00:00Z initial: P0=[C-G1.1] P1=[] P2=[]"),
                history_lines=(
                    "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |\n"
                    "|---|---|---|---|---|---|---|\n"
                    "| 1 | C-G1.1(P0) | W1 | bad | 0 | cp.yaml | 80 |"
                ),
            ),
            "checked/picked",
        ),
    ],
)
def test_parse_stage_reports_stable_syntax_errors(text: str, message: str) -> None:
    with pytest.raises(RoundArtifactParseError) as raised:
        parse_stage(text)

    assert raised.value.kind == "STAGE_PARSE"
    assert message in raised.value.message
