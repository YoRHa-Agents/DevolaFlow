"""Pure priority-driven round selection for checklist workspaces.

The engine deliberately depends on structural views instead of the Markdown
parser.  Callers may pass parser records, test doubles, or other immutable
snapshots as long as they expose the protocol attributes below.

v17.0.0 R5 (D-R5-1): the round-capacity default and the stop-guard window
widths resolve through :func:`devolaflow.harness.capacity.capacity_profile`
(the A-5 owner of ``context_profiles.yaml#meta.capacity``) when the caller
omits them. Explicit arguments keep every function pure; omitted arguments
pay one cached YAML lookup. The module literals below (``_CAPACITY_MIN`` /
``_CAPACITY_MAX`` and the 2/3 window defaults inside the capacity module)
remain the pinned fallback — with the config key absent (the shipped
default) behaviour is byte-identical to the pre-R5 hardcoded values.
``_CAPACITY_MIN``/``_CAPACITY_MAX`` stay the HARD validation bounds
regardless of config: ``meta.capacity.round_capacity`` moves the default,
never the stage-schema cap.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

__all__ = [
    "BlockedItem",
    "ChecklistItemView",
    "ChecklistView",
    "ITEM_UNSUCCESSFUL_THREE_ROUNDS",
    "MAX_ROUNDS_REACHED",
    "NET_STAGNATION_TWO_ROUNDS",
    "PriorityChangeView",
    "RankedItem",
    "ROUND_BLOCKERS_PRESENT",
    "ROUND_PICKED_ITEMS_OPEN",
    "ROUND_REVERTED_REINFORCEMENT_OPEN",
    "RoundEngineError",
    "RoundPassResult",
    "RoundProgress",
    "RoundSelection",
    "RoundStopResult",
    "StageView",
    "effective_priority",
    "evaluate_round_pass",
    "evaluate_stop_guard",
    "revert_checklist_item",
    "round_pass",
    "select_round",
    "stop_guard",
]

_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
_CAPACITY_MIN = 1
_CAPACITY_MAX = 5
# Sentinel meaning "caller did not pass capacity — resolve the default via
# meta.capacity.round_capacity". Deliberately NOT ``None``: ``None`` stays a
# pinned INVALID_CAPACITY input (S-5 — no silent coercion of caller bugs).
_CAPACITY_FROM_CONFIG: Final[Any] = object()
_ISO_UTC_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_COMPLETION_PREFIX: Final[str] = "      evidence:"

ROUND_PICKED_ITEMS_OPEN: Final[str] = "ROUND_PICKED_ITEMS_OPEN"
ROUND_BLOCKERS_PRESENT: Final[str] = "ROUND_BLOCKERS_PRESENT"
ROUND_REVERTED_REINFORCEMENT_OPEN: Final[str] = "ROUND_REVERTED_REINFORCEMENT_OPEN"
MAX_ROUNDS_REACHED: Final[str] = "MAX_ROUNDS_REACHED"
NET_STAGNATION_TWO_ROUNDS: Final[str] = "NET_STAGNATION_TWO_ROUNDS"
ITEM_UNSUCCESSFUL_THREE_ROUNDS: Final[str] = "ITEM_UNSUCCESSFUL_THREE_ROUNDS"


class ChecklistItemView(Protocol):
    """Structural checklist item consumed by :func:`select_round`."""

    item_id: str
    checked: bool
    priority: str
    depends: Sequence[str]
    reverted_reason: str | None


class ChecklistView(Protocol):
    """Structural checklist snapshot consumed by :func:`select_round`."""

    items: Sequence[ChecklistItemView]


class PriorityChangeView(Protocol):
    """One append-only priority adjustment from ``stage.md``."""

    item_id: str
    to_priority: str


class StageView(Protocol):
    """Structural stage snapshot carrying append-only priority changes."""

    priority_changes: Sequence[PriorityChangeView]


class RoundEngineError(ValueError):
    """Stable, machine-readable selector failure."""

    __slots__ = ("code", "message")

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class RankedItem:
    """Immutable eligible-item snapshot in effective priority order."""

    item_id: str
    priority: str
    reverted: bool
    source_index: int


@dataclass(frozen=True)
class BlockedItem:
    """Immutable blocked-item snapshot with unsatisfied dependencies."""

    item_id: str
    dependencies: tuple[str, ...]
    source_index: int


@dataclass(frozen=True)
class RoundSelection:
    """Immutable result of selecting one bounded round."""

    selected: tuple[RankedItem, ...]
    remaining: tuple[RankedItem, ...]
    blocked: tuple[BlockedItem, ...]


@dataclass(frozen=True)
class RoundPassResult:
    """Pure round-gate verdict with stable machine-readable reasons."""

    passed: bool
    reasons: tuple[str, ...] = ()
    unchecked_item_ids: tuple[str, ...] = ()
    open_reinforcement_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoundProgress:
    """One closed round's minimal progress record for bounded-stop guards."""

    round_num: int
    picked_item_ids: tuple[str, ...]
    checked_item_ids: tuple[str, ...] = ()
    reverted_item_ids: tuple[str, ...] = ()

    @property
    def net_delta(self) -> int:
        """Return newly checked minus newly reverted for this round."""

        return len(self.checked_item_ids) - len(self.reverted_item_ids)


@dataclass(frozen=True)
class RoundStopResult:
    """Pure bounded-execution verdict with stable machine-readable reasons."""

    should_stop: bool
    reasons: tuple[str, ...] = ()
    item_ids: tuple[str, ...] = ()


def _validate_priority(priority: str, *, context: str) -> None:
    if priority not in _PRIORITY_RANK:
        raise RoundEngineError(
            "INVALID_PRIORITY",
            f"{context} has invalid priority {priority!r}; expected P0, P1, or P2",
        )


def effective_priority(
    item: ChecklistItemView,
    priority_changes: Sequence[PriorityChangeView],
) -> str:
    """Return an item's latest valid adjusted priority, or its base priority."""

    priority = item.priority
    _validate_priority(priority, context=f"checklist item {item.item_id!r}")
    for change in priority_changes:
        if change.item_id != item.item_id:
            continue
        changed_priority = _changed_priority(change)
        _validate_priority(
            changed_priority,
            context=f"priority adjustment for checklist item {item.item_id!r}",
        )
        priority = changed_priority
    return priority


def _changed_priority(change: PriorityChangeView) -> str:
    """Read parser ``to_priority`` with a legacy structural fallback."""

    if hasattr(change, "to_priority"):
        return change.to_priority
    return str(change.priority)  # type: ignore[attr-defined]


def _validate_inputs(
    items: tuple[ChecklistItemView, ...],
    changes: tuple[PriorityChangeView, ...],
    capacity: int,
) -> dict[str, ChecklistItemView]:
    if type(capacity) is not int or not _CAPACITY_MIN <= capacity <= _CAPACITY_MAX:
        raise RoundEngineError(
            "INVALID_CAPACITY",
            f"capacity must be an integer from 1 through 5; got {capacity!r}",
        )

    items_by_id: dict[str, ChecklistItemView] = {}
    for item in items:
        if item.item_id in items_by_id:
            raise RoundEngineError(
                "DUPLICATE_ITEM_ID",
                f"duplicate checklist item id {item.item_id!r}",
            )
        items_by_id[item.item_id] = item
        _validate_priority(item.priority, context=f"checklist item {item.item_id!r}")

    for change in changes:
        if change.item_id not in items_by_id:
            raise RoundEngineError(
                "UNKNOWN_PRIORITY_ADJUSTMENT",
                f"priority adjustment references unknown checklist item {change.item_id!r}",
            )
        _validate_priority(
            _changed_priority(change),
            context=f"priority adjustment for checklist item {change.item_id!r}",
        )
    return items_by_id


def _capacity_defaults():
    """Resolve configured capacity/window defaults (import at call boundary).

    The lazy import avoids the agent_workspace ↔ harness module-init cycle
    (``harness.telemetry`` imports ``agent_workspace.layers``). A declared
    but invalid ``meta.capacity`` block raises ``CapacityConfigError``
    loudly per S-5; an absent key or unreadable profiles file yields the
    byte-identical hardcoded defaults (5 / 2 / 3).
    """

    from devolaflow.harness.capacity import capacity_profile

    return capacity_profile()


def _is_reverted(item: ChecklistItemView) -> bool:
    """Derive open-revert state directly from parser-compatible records.

    ``ChecklistItem`` exposes ``reverted_reason`` rather than a synthetic
    boolean. The fallback preserves structural compatibility with legacy test
    doubles and callers that predate the parser.
    """

    if hasattr(item, "reverted_reason"):
        return item.reverted_reason is not None
    return bool(getattr(item, "reverted", False))


def select_round(
    checklist: ChecklistView,
    stage: StageView,
    capacity: int = _CAPACITY_FROM_CONFIG,
) -> RoundSelection:
    """Select up to ``capacity`` open, dependency-ready checklist items.

    Checked items are excluded. Unknown and currently unchecked dependencies
    block an item for this round. Reverted open items rank ahead of every
    non-reverted item; all other ordering is P0, P1, P2 with checklist source
    order as the stable tie-breaker.

    An omitted ``capacity`` resolves through
    ``meta.capacity.round_capacity`` per D-R5-1 — 5 when the config key is
    absent (byte-identical pre-R5 default). Every explicitly passed value —
    including ``None`` — is validated against the unchanged 1..5
    stage-schema hard cap.
    """

    if capacity is _CAPACITY_FROM_CONFIG:
        capacity = _capacity_defaults().round_capacity
    items = tuple(checklist.items)
    changes = tuple(stage.priority_changes)
    items_by_id = _validate_inputs(items, changes, capacity)

    eligible: list[RankedItem] = []
    blocked: list[BlockedItem] = []
    for source_index, item in enumerate(items):
        if item.checked:
            continue
        unsatisfied = tuple(
            dependency
            for dependency in item.depends
            if dependency not in items_by_id or not items_by_id[dependency].checked
        )
        if unsatisfied:
            blocked.append(
                BlockedItem(
                    item_id=item.item_id,
                    dependencies=unsatisfied,
                    source_index=source_index,
                )
            )
            continue
        eligible.append(
            RankedItem(
                item_id=item.item_id,
                priority=effective_priority(item, changes),
                reverted=_is_reverted(item),
                source_index=source_index,
            )
        )

    ranked = sorted(
        eligible,
        key=lambda item: (
            not item.reverted,
            _PRIORITY_RANK[item.priority],
            item.source_index,
        ),
    )
    return RoundSelection(
        selected=tuple(ranked[:capacity]),
        remaining=tuple(ranked[capacity:]),
        blocked=tuple(blocked),
    )


def _replace_frontmatter_field(
    lines: list[str],
    closing_index: int,
    field_name: str,
    rendered_value: str,
) -> None:
    matches = [
        index for index in range(1, closing_index) if lines[index].startswith(f"{field_name}:")
    ]
    if len(matches) != 1:
        raise RoundEngineError(
            "INVALID_CHECKLIST_FRONTMATTER",
            f"checklist frontmatter must contain exactly one {field_name!r} field",
        )
    lines[matches[0]] = f"{field_name}: {rendered_value}"


def revert_checklist_item(
    checklist_text: str,
    item_id: str,
    reason: str,
    *,
    actor: str,
    at: str,
) -> str:
    """Return checklist text with one checked item reopened by the user.

    This is a pure text transformation: it performs no file I/O, does not
    touch stage history or evidence files, and preserves the reason verbatim.
    """

    if actor != "user":
        raise RoundEngineError(
            "REVERT_ACTOR_FORBIDDEN",
            f"only actor 'user' may reopen a checked item; got {actor!r}",
        )
    if not reason or "\n" in reason or "\r" in reason:
        raise RoundEngineError(
            "INVALID_REVERT_REASON",
            "revert reason must be a non-empty single line",
        )
    if _ISO_UTC_RE.fullmatch(at) is None:
        raise RoundEngineError(
            "INVALID_REVERT_TIMESTAMP",
            f"revert timestamp must use YYYY-MM-DDTHH:MM:SSZ; got {at!r}",
        )

    from devolaflow.agent_workspace.round_parser import parse_checklist

    document = parse_checklist(checklist_text)
    matches = [item for item in document.items if item.item_id == item_id]
    if not matches:
        raise RoundEngineError("UNKNOWN_ITEM_ID", f"unknown checklist item id {item_id!r}")
    if not matches[0].checked:
        raise RoundEngineError(
            "ITEM_NOT_CHECKED",
            f"checklist item {item_id!r} is already open",
        )

    had_trailing_newline = checklist_text.endswith("\n")
    lines = checklist_text.splitlines()
    closing_index = lines.index("---", 1)
    item_prefix = f"- [x] {item_id} "
    item_indices = [
        index
        for index in range(closing_index + 1, len(lines))
        if lines[index].startswith(item_prefix)
    ]
    if len(item_indices) != 1:
        raise RoundEngineError(
            "ITEM_STRUCTURE_MISMATCH",
            f"checked checklist item {item_id!r} does not have one canonical source line",
        )

    item_index = item_indices[0]
    item_end = len(lines)
    for index in range(item_index + 1, len(lines)):
        if lines[index].startswith("- ") or lines[index].startswith("## "):
            item_end = index
            break

    lines[item_index] = lines[item_index].replace("- [x]", "- [ ]", 1)
    metadata = [
        line for line in lines[item_index + 1 : item_end] if not line.startswith(_COMPLETION_PREFIX)
    ]
    insertion_index = len(metadata)
    while insertion_index and not metadata[insertion_index - 1].strip():
        insertion_index -= 1
    metadata.insert(insertion_index, f"      reverted: {reason} | at: {at}")
    lines[item_index + 1 : item_end] = metadata

    intermediate = "\n".join(lines) + ("\n" if had_trailing_newline else "")
    updated = parse_checklist(intermediate)
    total_items = len(updated.items)
    checked = sum(item.checked for item in updated.items)
    reverted_open = sum(
        not item.checked and item.reverted_reason is not None for item in updated.items
    )
    priority_dist = {
        priority: sum(item.priority == priority for item in updated.items)
        for priority in ("P0", "P1", "P2")
    }

    _replace_frontmatter_field(lines, closing_index, "total_items", str(total_items))
    _replace_frontmatter_field(lines, closing_index, "checked", str(checked))
    _replace_frontmatter_field(
        lines,
        closing_index,
        "priority_dist",
        f"{{P0: {priority_dist['P0']}, P1: {priority_dist['P1']}, P2: {priority_dist['P2']}}}",
    )
    _replace_frontmatter_field(lines, closing_index, "reverted_open", str(reverted_open))
    return "\n".join(lines) + ("\n" if had_trailing_newline else "")


def evaluate_round_pass(
    picked_item_ids: Sequence[str],
    checked_item_ids: Sequence[str],
    blocker_count: int,
    reverted_item_ids: Sequence[str] = (),
    closed_reinforcement_ids: Sequence[str] = (),
    entrance_finding: object | None = None,
) -> RoundPassResult:
    """Evaluate the checklist-first round PASS contract without side effects.

    ``entrance_finding`` accepts the same ``ENTRANCE_*`` finding surfaced by
    the task-stop workspace gate. A blocking finding contributes one blocker;
    a lite-mode warning remains observable to its caller but does not turn a
    round into a false failure. Omitting it preserves the legacy contract.
    """

    if type(blocker_count) is not int or blocker_count < 0:
        raise RoundEngineError(
            "INVALID_BLOCKER_COUNT",
            f"blocker_count must be a non-negative integer; got {blocker_count!r}",
        )

    if entrance_finding is not None:
        code = getattr(entrance_finding, "kind", getattr(entrance_finding, "code", None))
        severity = getattr(entrance_finding, "severity", None)
        if not isinstance(code, str) or not code.startswith("ENTRANCE_"):
            raise RoundEngineError(
                "INVALID_ENTRANCE_FINDING",
                "entrance_finding must expose an ENTRANCE_* code or kind",
            )
        if severity not in {"FAIL", "blocker", "error", "warning", "WARN"}:
            raise RoundEngineError(
                "INVALID_ENTRANCE_FINDING",
                "entrance_finding severity must be FAIL, blocker, error, WARN, or warning",
            )
        if severity in {"FAIL", "blocker", "error"}:
            blocker_count += 1

    picked = tuple(dict.fromkeys(picked_item_ids))
    checked = frozenset(checked_item_ids)
    unchecked = tuple(item_id for item_id in picked if item_id not in checked)
    picked_reverted = tuple(
        item_id for item_id in picked if item_id in frozenset(reverted_item_ids)
    )
    closed = frozenset(closed_reinforcement_ids)
    open_reinforcement = tuple(item_id for item_id in picked_reverted if item_id not in closed)

    reasons: list[str] = []
    if unchecked:
        reasons.append(ROUND_PICKED_ITEMS_OPEN)
    if blocker_count:
        reasons.append(ROUND_BLOCKERS_PRESENT)
    if open_reinforcement:
        reasons.append(ROUND_REVERTED_REINFORCEMENT_OPEN)
    return RoundPassResult(
        passed=not reasons,
        reasons=tuple(reasons),
        unchecked_item_ids=unchecked,
        open_reinforcement_ids=open_reinforcement,
    )


def _consecutive(rounds: Sequence[RoundProgress]) -> bool:
    return all(
        rounds[index].round_num == rounds[index - 1].round_num + 1
        for index in range(1, len(rounds))
    )


def _validate_window(value: int, *, name: str) -> None:
    if type(value) is not int or value < 1:
        raise RoundEngineError(
            "INVALID_STOP_GUARD_WINDOW",
            f"{name} must be a positive integer; got {value!r}",
        )


def evaluate_stop_guard(
    history: Sequence[RoundProgress],
    *,
    current_round: int,
    max_rounds: int,
    open_item_ids: Sequence[str],
    stagnation_rounds: int | None = None,
    unsuccessful_item_rounds: int | None = None,
) -> RoundStopResult:
    """Evaluate all independent P4 stop guards from immutable round history.

    The two window widths default through ``meta.capacity.stop_guard`` per
    D-R5-1 (2 and 3 when the config key is absent — byte-identical to the
    pre-R5 hardcoded windows). The reason literals stay frozen regardless of
    the configured widths: they are stable machine-readable codes, not
    numeral mirrors.
    """

    if type(current_round) is not int or current_round < 0:
        raise RoundEngineError(
            "INVALID_CURRENT_ROUND",
            f"current_round must be a non-negative integer; got {current_round!r}",
        )
    if type(max_rounds) is not int or max_rounds < 1:
        raise RoundEngineError(
            "INVALID_MAX_ROUNDS",
            f"max_rounds must be a positive integer; got {max_rounds!r}",
        )
    if stagnation_rounds is None or unsuccessful_item_rounds is None:
        defaults = _capacity_defaults()
        if stagnation_rounds is None:
            stagnation_rounds = defaults.stagnation_rounds
        if unsuccessful_item_rounds is None:
            unsuccessful_item_rounds = defaults.unsuccessful_item_rounds
    _validate_window(stagnation_rounds, name="stagnation_rounds")
    _validate_window(unsuccessful_item_rounds, name="unsuccessful_item_rounds")

    rounds = tuple(history)
    open_items = frozenset(open_item_ids)
    reasons: list[str] = []
    if open_items and current_round >= max_rounds:
        reasons.append(MAX_ROUNDS_REACHED)

    if len(rounds) >= stagnation_rounds:
        recent = rounds[-stagnation_rounds:]
        if _consecutive(recent) and all(progress.net_delta <= 0 for progress in recent):
            reasons.append(NET_STAGNATION_TWO_ROUNDS)

    unsuccessful_items: tuple[str, ...] = ()
    if len(rounds) >= unsuccessful_item_rounds:
        recent = rounds[-unsuccessful_item_rounds:]
        if _consecutive(recent):
            unsuccessful_sets = [
                set(progress.picked_item_ids) - set(progress.checked_item_ids)
                for progress in recent
            ]
            candidates = set.intersection(*unsuccessful_sets) & open_items
            unsuccessful_items = tuple(
                item_id for item_id in recent[0].picked_item_ids if item_id in candidates
            )
            if unsuccessful_items:
                reasons.append(ITEM_UNSUCCESSFUL_THREE_ROUNDS)

    return RoundStopResult(
        should_stop=bool(reasons),
        reasons=tuple(reasons),
        item_ids=unsuccessful_items,
    )


round_pass = evaluate_round_pass
stop_guard = evaluate_stop_guard
