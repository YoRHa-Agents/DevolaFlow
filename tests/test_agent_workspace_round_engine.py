"""Pure structural-typing tests for the checklist round selector."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, replace

import pytest

from devolaflow.agent_workspace.round_engine import (
    ITEM_UNSUCCESSFUL_THREE_ROUNDS,
    MAX_ROUNDS_REACHED,
    NET_STAGNATION_TWO_ROUNDS,
    ROUND_BLOCKERS_PRESENT,
    ROUND_PICKED_ITEMS_OPEN,
    ROUND_REVERTED_REINFORCEMENT_OPEN,
    BlockedItem,
    RankedItem,
    RoundEngineError,
    RoundProgress,
    effective_priority,
    evaluate_round_pass,
    evaluate_stop_guard,
    revert_checklist_item,
    select_round,
)
from devolaflow.agent_workspace.round_parser import parse_checklist, parse_stage
from devolaflow.gate.reinforcement import (
    MAX_REINFORCEMENT_RULES,
    reverted_items_to_reinforcement,
)


@dataclass(frozen=True)
class Item:
    item_id: str
    priority: str = "P1"
    checked: bool = False
    depends: tuple[str, ...] = ()
    reverted: bool = False


@dataclass(frozen=True)
class Checklist:
    items: tuple[Item, ...]


@dataclass(frozen=True)
class PriorityChange:
    item_id: str
    priority: str


@dataclass(frozen=True)
class Stage:
    priority_changes: tuple[PriorityChange, ...] = ()


def _ids(items: tuple[RankedItem, ...]) -> tuple[str, ...]:
    return tuple(item.item_id for item in items)


def _checklist_text() -> str:
    return """\
---
parent: round-engine
schema_version: 1
total_items: 2
checked: 1
priority_dist: {P0: 1, P1: 0, P2: 1}
reverted_open: 0
---

# Checklist

## G1: Exercise parser and engine together
- [ ] C-G1.1 (P0) The normal item remains open
      verify: manual
- [x] C-G1.2 (P2) The user may reopen this checked item
      verify: manual
      evidence: evidence/C-G1.2.txt | checked_by: user | round: 1 | at: 2026-08-24T10:00:00Z
"""


def _stage_text() -> str:
    return """\
---
parent: round-engine
schema_version: 1
current_round: 1
max_rounds: 4
capacity_per_round: 5
---

# Stage — Round Control

## Priority Settings
- 2026-08-24T09:00:00Z initial: P0=[C-G1.1] P1=[] P2=[C-G1.2]
- 2026-08-24T10:30:00Z adjustment: C-G1.2 P2 -> P1 | user: raise reopened work

## Round History
| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |
|---|---|---|---|---|---|---|

## Next Round Plan
- Candidates: [C-G1.1, C-G1.2]
- Estimated remaining rounds: 1
"""


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ((), "P1"),
        ((PriorityChange("C-1", "P0"),), "P0"),
        (
            (
                PriorityChange("other", "P0"),
                PriorityChange("C-1", "P2"),
                PriorityChange("C-1", "P0"),
            ),
            "P0",
        ),
    ],
)
def test_effective_priority_uses_latest_matching_change(
    changes: tuple[PriorityChange, ...],
    expected: str,
) -> None:
    assert effective_priority(Item("C-1"), changes) == expected


def test_selection_excludes_checked_and_ranks_stably() -> None:
    checklist = Checklist(
        (
            Item("p1-first"),
            Item("done", priority="P0", checked=True),
            Item("p0-first", priority="P0"),
            Item("p0-second", priority="P0"),
            Item("p2", priority="P2"),
            Item("p1-second"),
        )
    )

    result = select_round(checklist, Stage(), capacity=5)

    assert _ids(result.selected) == (
        "p0-first",
        "p0-second",
        "p1-first",
        "p1-second",
        "p2",
    )
    assert result.remaining == ()
    assert all(item.item_id != "done" for item in result.selected)


def test_open_reverted_items_rank_before_non_reverted_p0() -> None:
    checklist = Checklist(
        (
            Item("normal-p0", priority="P0"),
            Item("reverted-p2", priority="P2", reverted=True),
            Item("reverted-p1", priority="P1", reverted=True),
            Item("checked-reverted", priority="P0", checked=True, reverted=True),
        )
    )

    result = select_round(checklist, Stage(), capacity=3)

    assert _ids(result.selected) == ("reverted-p1", "reverted-p2", "normal-p0")
    assert tuple(item.priority for item in result.selected) == ("P1", "P2", "P0")


@pytest.mark.parametrize(
    ("dependency", "dependency_item", "blocked"),
    [
        ("unknown", None, True),
        ("open", Item("open"), True),
        ("done", Item("done", checked=True), False),
    ],
)
def test_unknown_and_unchecked_dependencies_block(
    dependency: str,
    dependency_item: Item | None,
    blocked: bool,
) -> None:
    items = [Item("target", priority="P0", depends=(dependency,))]
    if dependency_item is not None:
        items.append(dependency_item)

    result = select_round(Checklist(tuple(items)), Stage(), capacity=2)

    target_is_blocked = any(item.item_id == "target" for item in result.blocked)
    assert target_is_blocked is blocked
    assert ("target" in _ids(result.selected)) is not blocked


@pytest.mark.parametrize("capacity", [1, 2, 3, 4, 5])
def test_capacity_bounds_selection_and_preserves_ranked_remaining(capacity: int) -> None:
    checklist = Checklist(tuple(Item(f"C-{index}", priority="P0") for index in range(7)))

    result = select_round(checklist, Stage(), capacity=capacity)

    assert _ids(result.selected) == tuple(f"C-{index}" for index in range(capacity))
    assert _ids(result.remaining) == tuple(f"C-{index}" for index in range(capacity, 7))


def test_blocked_items_preserve_source_and_dependency_order() -> None:
    checklist = Checklist(
        (
            Item("later-source", depends=("z", "a", "z")),
            Item("eligible", priority="P0"),
            Item("last-source", depends=("missing-2", "missing-1")),
        )
    )

    result = select_round(checklist, Stage(), capacity=1)

    assert result.blocked == (
        BlockedItem("later-source", ("z", "a", "z"), 0),
        BlockedItem("last-source", ("missing-2", "missing-1"), 2),
    )


@pytest.mark.parametrize("capacity", [0, 6, -1, True, 1.0, "2", None])
def test_invalid_capacity_has_stable_error(capacity: object) -> None:
    with pytest.raises(RoundEngineError) as exc_info:
        select_round(Checklist(()), Stage(), capacity=capacity)  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_CAPACITY"
    assert exc_info.value.message == (
        f"capacity must be an integer from 1 through 5; got {capacity!r}"
    )
    assert str(exc_info.value) == f"INVALID_CAPACITY: {exc_info.value.message}"


def test_duplicate_ids_have_stable_error() -> None:
    checklist = Checklist((Item("duplicate"), Item("duplicate", priority="P0")))

    with pytest.raises(RoundEngineError) as exc_info:
        select_round(checklist, Stage(), capacity=1)

    assert exc_info.value.code == "DUPLICATE_ITEM_ID"
    assert exc_info.value.message == "duplicate checklist item id 'duplicate'"


@pytest.mark.parametrize("location", ["item", "adjustment"])
def test_invalid_priorities_have_stable_error(location: str) -> None:
    checklist = Checklist((Item("C-1", priority="PX" if location == "item" else "P1"),))
    stage = Stage((PriorityChange("C-1", "PX"),) if location == "adjustment" else ())

    with pytest.raises(RoundEngineError) as exc_info:
        select_round(checklist, stage, capacity=1)

    assert exc_info.value.code == "INVALID_PRIORITY"
    assert exc_info.value.message.endswith("has invalid priority 'PX'; expected P0, P1, or P2")


def test_unknown_priority_adjustment_has_stable_error() -> None:
    with pytest.raises(RoundEngineError) as exc_info:
        select_round(
            Checklist((Item("known"),)),
            Stage((PriorityChange("unknown", "P0"),)),
            capacity=1,
        )

    assert exc_info.value.code == "UNKNOWN_PRIORITY_ADJUSTMENT"
    assert exc_info.value.message == (
        "priority adjustment references unknown checklist item 'unknown'"
    )


def test_selection_does_not_mutate_inputs_and_results_are_frozen() -> None:
    checklist = Checklist((Item("C-1"), Item("C-2", priority="P2")))
    stage = Stage((PriorityChange("C-2", "P0"),))
    before = (checklist.items, stage.priority_changes)

    result = select_round(checklist, stage, capacity=1)

    assert (checklist.items, stage.priority_changes) == before
    assert _ids(result.selected) == ("C-2",)
    assert _ids(result.remaining) == ("C-1",)
    with pytest.raises(FrozenInstanceError):
        result.selected = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.selected[0].priority = "P2"  # type: ignore[misc]


def test_user_revert_is_verbatim_counter_synced_and_dispatcher_rejected() -> None:
    original = _checklist_text()
    with pytest.raises(RoundEngineError, match="REVERT_ACTOR_FORBIDDEN"):
        revert_checklist_item(
            original,
            "C-G1.2",
            "user reason",
            actor="L0",
            at="2026-08-24T11:00:00Z",
        )

    reason = 'Keep "quotes", arrows ->, and spaces exactly'
    updated = revert_checklist_item(
        original,
        "C-G1.2",
        reason,
        actor="user",
        at="2026-08-24T11:00:00Z",
    )
    parsed = parse_checklist(updated)

    assert parsed.artifact.frontmatter["checked"] == 0
    assert parsed.artifact.frontmatter["reverted_open"] == 1
    assert parsed.artifact.frontmatter["priority_dist"] == {"P0": 1, "P1": 0, "P2": 1}
    assert parsed.items[1].reverted_reason == reason
    assert "      evidence:" not in updated
    assert original == _checklist_text()


def test_parser_documents_feed_selector_and_revert_reinforcement_directly() -> None:
    updated = revert_checklist_item(
        _checklist_text(),
        "C-G1.2",
        "Restore the user-visible behavior exactly.",
        actor="user",
        at="2026-08-24T11:00:00Z",
    )
    checklist = parse_checklist(updated)
    stage = parse_stage(_stage_text())

    selected = select_round(checklist, stage, capacity=2)
    assert _ids(selected.selected) == ("C-G1.2", "C-G1.1")
    assert selected.selected[0].priority == "P1"

    reverted_items = tuple(
        replace(checklist.items[1], item_id=f"C-G1.{index}")
        for index in range(1, MAX_REINFORCEMENT_RULES + 2)
    )
    block = reverted_items_to_reinforcement(reverted_items, round_num=2)
    assert len(block.rules) == MAX_REINFORCEMENT_RULES
    assert block.round == 2
    assert block.severity_floor == "blocker"
    assert block.rules[0].id == "R-C-G1.1-002"
    assert block.rules[0].severity == "blocker"
    assert block.rules[0].mandate == "Restore the user-visible behavior exactly."


@pytest.mark.parametrize(
    ("checked", "blockers", "reverted", "closed", "passed", "reasons"),
    [
        (("C-1",), 0, (), (), True, ()),
        ((), 0, (), (), False, (ROUND_PICKED_ITEMS_OPEN,)),
        (
            ("C-1",),
            1,
            ("C-1",),
            (),
            False,
            (ROUND_BLOCKERS_PRESENT, ROUND_REVERTED_REINFORCEMENT_OPEN),
        ),
        (("C-1",), 0, ("C-1",), ("C-1",), True, ()),
    ],
)
def test_round_pass_contract(
    checked: tuple[str, ...],
    blockers: int,
    reverted: tuple[str, ...],
    closed: tuple[str, ...],
    passed: bool,
    reasons: tuple[str, ...],
) -> None:
    result = evaluate_round_pass(("C-1",), checked, blockers, reverted, closed)
    assert result.passed is passed
    assert result.reasons == reasons


def test_stop_guard_enforces_all_three_bounded_reasons() -> None:
    history = (
        RoundProgress(1, ("C-1",), (), ()),
        RoundProgress(2, ("C-1",), (), ("C-2",)),
        RoundProgress(3, ("C-1",), (), ()),
    )

    result = evaluate_stop_guard(
        history,
        current_round=3,
        max_rounds=3,
        open_item_ids=("C-1",),
    )

    assert result.should_stop
    assert result.reasons == (
        MAX_ROUNDS_REACHED,
        NET_STAGNATION_TWO_ROUNDS,
        ITEM_UNSUCCESSFUL_THREE_ROUNDS,
    )
    assert result.item_ids == ("C-1",)
