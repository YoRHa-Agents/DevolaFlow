"""Checklist-round dispatch NEST population and validation tests."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from devolaflow.agent_workspace import populate_round_change_context
from devolaflow.compressor import assert_dispatch_layout

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "lean-dispatch.yaml"


@dataclass(frozen=True)
class Item:
    item_id: str
    assertion: str
    verify: str


@dataclass(frozen=True)
class Checklist:
    items: object


@dataclass(frozen=True)
class Selected:
    item_id: str
    priority: object = "P1"
    reverted: object = False


@dataclass(frozen=True)
class Selection:
    selected: object


def _base_dispatch() -> dict[str, Any]:
    return {
        "hdr": {"id": "dispatch-round-2", "layer": "wave"},
        "task": {"id": "T1", "type": "code", "title": "Execute selected assertions"},
        "goal": "Close the selected checklist assertions",
        "change_context": {
            "change_id": "round-dispatch",
            "state": "IN_PROGRESS",
            "metadata": {"owner": "L0", "tags": ["preserve"]},
        },
    }


def _checklist(*items: Item) -> Checklist:
    return Checklist(items)


def _selection(*items: Selected) -> Selection:
    return Selection(items)


def test_absent_round_inputs_return_byte_identical_deep_copy() -> None:
    base = _base_dispatch()
    control = yaml.safe_dump(copy.deepcopy(base), sort_keys=False)

    result = populate_round_change_context(base)

    assert yaml.safe_dump(result, sort_keys=False) == control
    assert result == base
    assert result is not base
    assert result["change_context"] is not base["change_context"]
    assert "checklist_items" not in result["change_context"]
    assert "round_context" not in result["change_context"]


def test_populate_round_change_context_emits_selected_items_verbatim() -> None:
    assertion_one = 'Keep  "quoted spacing" -> exactly'
    verify_one = "`python -m pytest tests/test_one.py -q`"
    assertion_two = "Metric stays >= 99.5%"
    verify_two = "metric: coverage >= 99.5"
    checklist = _checklist(
        Item("C-G1.1", assertion_one, verify_one),
        Item("C-G1.2", assertion_two, verify_two),
    )
    selection = _selection(
        Selected("C-G1.2", priority="P0", reverted=True),
        Selected("C-G1.1", priority="P2"),
    )
    base = _base_dispatch()
    before = copy.deepcopy(base)
    top_level_order = list(base)
    change_context_order = list(base["change_context"])

    result = populate_round_change_context(base, checklist, selection, round_n=3)

    assert result["change_context"]["checklist_items"] == [
        {
            "id": "C-G1.2",
            "assert": assertion_two,
            "verify": verify_two,
            "priority": "P0",
        },
        {
            "id": "C-G1.1",
            "assert": assertion_one,
            "verify": verify_one,
            "priority": "P2",
        },
    ]
    assert result["change_context"]["round_context"] == {
        "round_n": 3,
        "reverted_ids": ["C-G1.2"],
    }
    assert list(result) == top_level_order
    assert list(result["change_context"])[: len(change_context_order)] == change_context_order
    assert base == before
    assert_dispatch_layout(result)

    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    fields = schema["lean_format_spec"]["change_context"]["fields"]
    assert fields["checklist_items"]["min_items"] == 1
    assert fields["checklist_items"]["max_items"] == 5
    assert fields["checklist_items"]["required_with"] == "round_context"
    assert fields["round_context"]["required_with"] == "checklist_items"
    assert fields["round_context"]["fields"]["round_n"]["minimum"] == 1
    assert fields["round_context"]["fields"]["reverted_ids"]["unique_items"] is True
    assert schema["layout_invariant"]["version"] == 6
    assert len(schema["layout_invariant"]["canonical_order"]) == 17


@pytest.mark.parametrize(
    ("checklist", "selection", "round_n"),
    [
        (_checklist(Item("C-G1.1", "assertion", "verify")), None, None),
        (None, _selection(Selected("C-G1.1")), None),
        (None, None, 1),
        (_checklist(Item("C-G1.1", "assertion", "verify")), _selection(Selected("C-G1.1")), None),
    ],
)
def test_partial_round_inputs_are_rejected(
    checklist: Checklist | None,
    selection: Selection | None,
    round_n: int | None,
) -> None:
    with pytest.raises(ValueError, match="must be provided together"):
        populate_round_change_context(
            _base_dispatch(),
            checklist,  # type: ignore[arg-type]
            selection,  # type: ignore[arg-type]
            round_n=round_n,
        )


@pytest.mark.parametrize("round_n", [0, -1, True, 1.5, "1"])
def test_invalid_round_or_change_context_is_rejected(round_n: object) -> None:
    checklist = _checklist(Item("C-G1.1", "assertion", "verify"))
    selection = _selection(Selected("C-G1.1"))
    with pytest.raises(ValueError, match="round_n must be an integer >= 1"):
        populate_round_change_context(
            _base_dispatch(),
            checklist,  # type: ignore[arg-type]
            selection,  # type: ignore[arg-type]
            round_n=round_n,  # type: ignore[arg-type]
        )

    if round_n == 0:
        for base in ({}, {"change_context": []}):
            with pytest.raises(ValueError, match="existing mapping"):
                populate_round_change_context(
                    base,
                    checklist,  # type: ignore[arg-type]
                    selection,  # type: ignore[arg-type]
                    round_n=1,
                )
        with pytest.raises(ValueError, match="base_dispatch must be a dict"):
            populate_round_change_context(  # type: ignore[arg-type]
                [],
                checklist,
                selection,
                round_n=1,
            )


@pytest.mark.parametrize(
    "selected",
    [
        (),
        tuple(Selected(f"C-G1.{index}") for index in range(1, 7)),
    ],
)
def test_selected_cardinality_must_be_one_through_five(
    selected: tuple[Selected, ...],
) -> None:
    checklist = _checklist(
        *(Item(f"C-G1.{index}", f"assertion {index}", "verify") for index in range(1, 7))
    )
    with pytest.raises(ValueError, match="must contain 1 through 5 items"):
        populate_round_change_context(
            _base_dispatch(),
            checklist,  # type: ignore[arg-type]
            Selection(selected),  # type: ignore[arg-type]
            round_n=1,
        )


@pytest.mark.parametrize(
    ("checklist", "selection", "message"),
    [
        (Checklist(None), _selection(Selected("C-G1.1")), "checklist.items must be a sequence"),
        (
            _checklist(Item("C-G1.1", "assertion", "verify")),
            Selection(None),
            "selection.selected must be a sequence",
        ),
        (
            _checklist(
                Item("C-G1.1", "assertion", "verify"),
                Item("C-G1.1", "duplicate", "verify"),
            ),
            _selection(Selected("C-G1.1")),
            "duplicate checklist item id",
        ),
        (
            _checklist(Item("C-G1.1", "assertion", "verify")),
            _selection(Selected("C-G1.1"), Selected("C-G1.1")),
            "duplicate selected checklist item id",
        ),
        (
            _checklist(Item("C-G1.1", "assertion", "verify")),
            _selection(Selected("C-G1.2")),
            "is unknown",
        ),
        (
            _checklist(Item("C-G1.1", " ", "verify")),
            _selection(Selected("C-G1.1")),
            "empty assertion",
        ),
        (
            _checklist(Item("C-G1.1", "assertion", " ")),
            _selection(Selected("C-G1.1")),
            "empty verify",
        ),
        (
            _checklist(Item("C-G1.1", "assertion", "verify")),
            _selection(Selected("C-G1.1", priority="P9")),
            "invalid effective priority",
        ),
        (
            _checklist(Item("C-G1.1", "assertion", "verify")),
            _selection(Selected("C-G1.1", reverted=1)),
            "boolean reverted flag",
        ),
        (
            _checklist(Item("", "assertion", "verify")),
            _selection(Selected("C-G1.1")),
            "non-empty string item_id",
        ),
    ],
)
def test_invalid_duplicate_unknown_and_empty_item_data_is_rejected(
    checklist: Checklist,
    selection: Selection,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        populate_round_change_context(
            _base_dispatch(),
            checklist,  # type: ignore[arg-type]
            selection,  # type: ignore[arg-type]
            round_n=1,
        )
