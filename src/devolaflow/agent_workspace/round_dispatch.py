"""Pure dispatch-context population for one checklist execution round."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any

from devolaflow.agent_workspace.round_engine import RoundSelection
from devolaflow.agent_workspace.round_parser import ChecklistDocument

__all__ = ["populate_round_change_context"]

_EFFECTIVE_PRIORITIES = frozenset({"P0", "P1", "P2"})
_ROUND_ITEM_MIN = 1
_ROUND_ITEM_MAX = 5


def _require_sequence(value: object, *, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    return value


def _require_item_id(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must have a non-empty string item_id")
    return value


def populate_round_change_context(
    base_dispatch: dict[str, Any],
    checklist: ChecklistDocument | None = None,
    selection: RoundSelection | None = None,
    *,
    round_n: int | None = None,
) -> dict[str, Any]:
    """Return a deep-copied dispatch carrying one selected checklist round.

    ``checklist``, ``selection``, and ``round_n`` form one opt-in group. When
    all are absent, the deep copy is returned unchanged (canonical absence).
    When present, ``checklist_items`` and ``round_context`` are emitted
    together inside the existing ``change_context`` mapping.
    """

    if not isinstance(base_dispatch, dict):
        raise ValueError("base_dispatch must be a dict")

    supplied = (checklist is not None, selection is not None, round_n is not None)
    if not any(supplied):
        return copy.deepcopy(base_dispatch)
    if not all(supplied):
        raise ValueError("checklist, selection, and round_n must be provided together")
    if type(round_n) is not int or round_n < 1:
        raise ValueError(f"round_n must be an integer >= 1; got {round_n!r}")

    dispatch = copy.deepcopy(base_dispatch)
    change_context = dispatch.get("change_context")
    if not isinstance(change_context, dict):
        raise ValueError("base_dispatch.change_context must be an existing mapping")

    checklist_items = _require_sequence(getattr(checklist, "items", None), name="checklist.items")
    selected_items = _require_sequence(
        getattr(selection, "selected", None),
        name="selection.selected",
    )
    if not _ROUND_ITEM_MIN <= len(selected_items) <= _ROUND_ITEM_MAX:
        raise ValueError(
            f"selection.selected must contain 1 through 5 items; got {len(selected_items)}"
        )

    checklist_by_id: dict[str, object] = {}
    for item in checklist_items:
        item_id = _require_item_id(
            getattr(item, "item_id", None),
            context="checklist item",
        )
        if item_id in checklist_by_id:
            raise ValueError(f"duplicate checklist item id {item_id!r}")
        checklist_by_id[item_id] = item

    selected_ids: set[str] = set()
    emitted_items: list[dict[str, str]] = []
    reverted_ids: list[str] = []
    for ranked_item in selected_items:
        item_id = _require_item_id(
            getattr(ranked_item, "item_id", None),
            context="selected item",
        )
        if item_id in selected_ids:
            raise ValueError(f"duplicate selected checklist item id {item_id!r}")
        selected_ids.add(item_id)

        item = checklist_by_id.get(item_id)
        if item is None:
            raise ValueError(f"selected checklist item {item_id!r} is unknown")

        assertion = getattr(item, "assertion", None)
        if not isinstance(assertion, str) or not assertion.strip():
            raise ValueError(f"selected checklist item {item_id!r} has an empty assertion")
        verify = getattr(item, "verify", None)
        if not isinstance(verify, str) or not verify.strip():
            raise ValueError(f"selected checklist item {item_id!r} has an empty verify")

        priority = getattr(ranked_item, "priority", None)
        if priority not in _EFFECTIVE_PRIORITIES:
            raise ValueError(
                f"selected checklist item {item_id!r} has invalid effective priority {priority!r}"
            )
        reverted = getattr(ranked_item, "reverted", None)
        if type(reverted) is not bool:
            raise ValueError(
                f"selected checklist item {item_id!r} must have a boolean reverted flag"
            )

        emitted_items.append(
            {
                "id": item_id,
                "assert": assertion,
                "verify": verify,
                "priority": priority,
            }
        )
        if reverted:
            reverted_ids.append(item_id)

    change_context["checklist_items"] = emitted_items
    change_context["round_context"] = {
        "round_n": round_n,
        "reverted_ids": reverted_ids,
    }
    return dispatch
