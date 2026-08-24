"""Pure parsers for v16 checklist and round-control Markdown artifacts.

The parser accepts text only and returns frozen read models.  Filesystem
validation and lifecycle mutation deliberately remain in their owning modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

import yaml

__all__ = [
    "ChecklistDocument",
    "ChecklistItem",
    "MarkdownArtifact",
    "Priority",
    "PriorityChange",
    "RoundArtifactParseError",
    "RoundHistoryRow",
    "RoundPick",
    "StageDocument",
    "parse_checklist",
    "parse_frontmatter",
    "parse_stage",
]

Priority = Literal["P0", "P1", "P2"]

_PARSE_ERROR_KINDS: Final[frozenset[str]] = frozenset(
    {"FRONTMATTER_PARSE", "CHECKLIST_ITEM_PARSE", "STAGE_PARSE"}
)
_CHECKLIST_GOAL_RE: Final[re.Pattern[str]] = re.compile(r"^## (G(?:[1-9]|1[0-5])): (.+)$")
_CHECKLIST_ITEM_RE: Final[re.Pattern[str]] = re.compile(
    r"^- \[([ x])\] (C-(G(?:[1-9]|1[0-5]))\.[1-9][0-9]*) \((P[012])\) (.+)$"
)
_VERIFY_RE: Final[re.Pattern[str]] = re.compile(r"^\s{6}verify: (.+)$")
_DEPENDS_RE: Final[re.Pattern[str]] = re.compile(r"^\s{6}depends: \[(.*)\]\s*$")
_ITEM_ID_RE: Final[re.Pattern[str]] = re.compile(r"^C-G(?:[1-9]|1[0-5])\.[1-9][0-9]*$")
_REVERTED_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s{6}reverted: (.+) \| at: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)
_INITIAL_PRIORITIES_RE: Final[re.Pattern[str]] = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) initial: "
    r"P0=\[(.*)\] P1=\[(.*)\] P2=\[(.*)\]$"
)
_PRIORITY_CHANGE_RE: Final[re.Pattern[str]] = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) adjustment: "
    r"(C-G(?:[1-9]|1[0-5])\.[1-9][0-9]*) (P[012]) -> (P[012]) \| user: (.+)$"
)
_ROUND_PICK_RE: Final[re.Pattern[str]] = re.compile(
    r"^(C-G(?:[1-9]|1[0-5])\.[1-9][0-9]*)\((P[012])\)$"
)
_WAVE_RE: Final[re.Pattern[str]] = re.compile(r"^W[1-7]$")
_ROUND_RESULT_RE: Final[re.Pattern[str]] = re.compile(r"^(\d+)/(\d+)$")

_STAGE_H1: Final[str] = "# Stage — Round Control"
_PRIORITY_HEADING: Final[str] = "## Priority Settings"
_HISTORY_HEADING: Final[str] = "## Round History"
_NEXT_ROUND_HEADING: Final[str] = "## Next Round Plan"
_HISTORY_HEADER: Final[str] = (
    "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |"
)
_HISTORY_SEPARATOR: Final[str] = "|---|---|---|---|---|---|---|"


class RoundArtifactParseError(ValueError):
    """A deterministic artifact parse failure with a stable ``kind`` value."""

    def __init__(self, filename: str, kind: str, message: str) -> None:
        if kind not in _PARSE_ERROR_KINDS:
            raise ValueError(f"unsupported round artifact parse kind: {kind!r}")
        self.filename = filename
        self.kind = kind
        self.message = message
        super().__init__(f"{filename}: [{kind}] {message}")

    @property
    def code(self) -> str:
        """Alias for callers that use error-code terminology."""
        return self.kind


@dataclass(frozen=True)
class MarkdownArtifact:
    """Markdown body paired with its parsed YAML frontmatter mapping."""

    frontmatter: dict[str, object]
    body: str


@dataclass(frozen=True)
class ChecklistItem:
    """One checklist assertion and its verbatim metadata."""

    item_id: str
    goal_id: str
    checked: bool
    priority: Priority
    assertion: str
    verify: str
    depends: tuple[str, ...]
    metadata: tuple[str, ...]
    reverted_reason: str | None
    source_index: int


@dataclass(frozen=True)
class ChecklistDocument:
    """Parsed checklist artifact in deterministic source order."""

    artifact: MarkdownArtifact
    goal_headings: tuple[tuple[str, str], ...]
    items: tuple[ChecklistItem, ...]


@dataclass(frozen=True)
class PriorityChange:
    """One append-only user priority adjustment."""

    timestamp: str
    item_id: str
    from_priority: Priority
    to_priority: Priority
    user_text: str


@dataclass(frozen=True)
class RoundPick:
    """An item and its effective priority when selected."""

    item_id: str
    priority: Priority


@dataclass(frozen=True)
class RoundHistoryRow:
    """One closed round from the canonical stage history table."""

    round_num: int
    picked: tuple[RoundPick, ...]
    waves: tuple[str, ...]
    checked_count: int
    picked_count: int
    blockers: int
    checkpoint: str
    gate_trend: float | None


@dataclass(frozen=True)
class StageDocument:
    """Parsed round controller, including empty or populated history."""

    artifact: MarkdownArtifact
    current_round: int
    max_rounds: int
    capacity_per_round: int
    initial_priorities: tuple[RoundPick, ...]
    priority_changes: tuple[PriorityChange, ...]
    history: tuple[RoundHistoryRow, ...]


def parse_frontmatter(text: str, *, filename: str) -> MarkdownArtifact:
    """Parse an exact fenced YAML mapping from Markdown *text*."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise RoundArtifactParseError(
            filename,
            "FRONTMATTER_PARSE",
            "frontmatter must start with an exact '---' line",
        )
    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise RoundArtifactParseError(
            filename,
            "FRONTMATTER_PARSE",
            "frontmatter is missing its closing '---' line",
        ) from exc

    yaml_text = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :])
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise RoundArtifactParseError(
            filename,
            "FRONTMATTER_PARSE",
            "frontmatter is not valid YAML",
        ) from exc
    if not isinstance(parsed, dict):
        raise RoundArtifactParseError(
            filename,
            "FRONTMATTER_PARSE",
            "frontmatter YAML must decode to a mapping",
        )
    return MarkdownArtifact(frontmatter=dict(parsed), body=body)


def _parse_checklist_goal_headings(
    body: str,
    filename: str,
) -> tuple[tuple[str, str], ...]:
    headings: list[tuple[str, str]] = []
    for line in body.splitlines():
        if not line.startswith("## G"):
            continue
        match = _CHECKLIST_GOAL_RE.fullmatch(line)
        if match is None:
            raise RoundArtifactParseError(
                filename,
                "CHECKLIST_ITEM_PARSE",
                "goal headings must use exact '## Gn: title' syntax",
            )
        headings.append((match.group(1), match.group(2)))
    return tuple(headings)


def _parse_depends(line: str, filename: str) -> tuple[str, ...]:
    match = _DEPENDS_RE.fullmatch(line)
    if match is None:
        raise RoundArtifactParseError(
            filename,
            "CHECKLIST_ITEM_PARSE",
            "depends metadata does not match the canonical syntax",
        )
    raw_items = match.group(1)
    if not raw_items:
        return ()
    item_ids = tuple(raw_items.split(", "))
    if any(_ITEM_ID_RE.fullmatch(item_id) is None for item_id in item_ids):
        raise RoundArtifactParseError(
            filename,
            "CHECKLIST_ITEM_PARSE",
            "depends metadata contains an invalid checklist item id",
        )
    return item_ids


def _parse_item_metadata(
    metadata: tuple[str, ...],
    filename: str,
    *,
    strict_metadata: bool,
) -> tuple[str, tuple[str, ...], str | None]:
    verify = ""
    depends: tuple[str, ...] = ()
    reverted_reason: str | None = None
    for line in metadata:
        if match := _VERIFY_RE.fullmatch(line):
            verify = match.group(1)
        elif line.lstrip().startswith("depends:"):
            if strict_metadata:
                depends = _parse_depends(line, filename)
            else:
                match = _DEPENDS_RE.fullmatch(line)
                if match is not None:
                    raw_items = match.group(1)
                    candidate_ids = tuple(raw_items.split(", ")) if raw_items else ()
                    if all(_ITEM_ID_RE.fullmatch(item_id) for item_id in candidate_ids):
                        depends = candidate_ids
        elif line.lstrip().startswith("reverted:"):
            match = _REVERTED_RE.fullmatch(line)
            if match is not None:
                reverted_reason = match.group(1)
            elif strict_metadata:
                raise RoundArtifactParseError(
                    filename,
                    "CHECKLIST_ITEM_PARSE",
                    "reverted metadata does not match the canonical syntax",
                )
    return verify, depends, reverted_reason


def _parse_checklist_items(
    body: str,
    filename: str,
    *,
    strict_metadata: bool = True,
) -> tuple[ChecklistItem, ...]:
    """Parse items; the relaxed mode is reserved for legacy lint compatibility."""
    items: list[ChecklistItem] = []
    current_goal = ""
    pending: tuple[str, str, bool, Priority, str, int] | None = None
    metadata: list[str] = []

    def flush() -> None:
        nonlocal pending, metadata
        if pending is not None:
            item_id, goal_id, checked, priority, assertion, source_index = pending
            parsed_metadata = tuple(metadata)
            verify, depends, reverted_reason = _parse_item_metadata(
                parsed_metadata,
                filename,
                strict_metadata=strict_metadata,
            )
            items.append(
                ChecklistItem(
                    item_id=item_id,
                    goal_id=goal_id,
                    checked=checked,
                    priority=priority,
                    assertion=assertion,
                    verify=verify,
                    depends=depends,
                    metadata=parsed_metadata,
                    reverted_reason=reverted_reason,
                    source_index=source_index,
                )
            )
        pending = None
        metadata = []

    for line in body.splitlines():
        heading = _CHECKLIST_GOAL_RE.fullmatch(line)
        if heading is not None:
            flush()
            current_goal = heading.group(1)
        elif line.startswith("- ["):
            flush()
            match = _CHECKLIST_ITEM_RE.fullmatch(line)
            if match is None:
                raise RoundArtifactParseError(
                    filename,
                    "CHECKLIST_ITEM_PARSE",
                    "checklist item does not match the canonical checkbox syntax",
                )
            embedded_goal = match.group(3)
            if strict_metadata and current_goal and current_goal != embedded_goal:
                raise RoundArtifactParseError(
                    filename,
                    "CHECKLIST_ITEM_PARSE",
                    f"{match.group(2)} does not belong to goal partition {current_goal}",
                )
            pending = (
                match.group(2),
                current_goal or embedded_goal,
                match.group(1) == "x",
                match.group(4),  # type: ignore[arg-type]
                match.group(5),
                len(items),
            )
        elif line.startswith("## "):
            flush()
            current_goal = ""
        elif pending is not None and line.startswith("      "):
            metadata.append(line)
    flush()
    return tuple(items)


def parse_checklist(
    text: str,
    *,
    filename: str = "checklist.md",
) -> ChecklistDocument:
    """Parse one canonical v16 checklist from text."""
    artifact = parse_frontmatter(text, filename=filename)
    goal_headings = _parse_checklist_goal_headings(artifact.body, filename)
    items = _parse_checklist_items(artifact.body, filename)
    return ChecklistDocument(
        artifact=artifact,
        goal_headings=goal_headings,
        items=items,
    )


def _stage_error(filename: str, message: str) -> RoundArtifactParseError:
    return RoundArtifactParseError(filename, "STAGE_PARSE", message)


def _required_int(frontmatter: dict[str, object], field_name: str, filename: str) -> int:
    value = frontmatter.get(field_name)
    if type(value) is not int:
        raise _stage_error(filename, f"{field_name} must be an integer")
    return value


def _parse_id_list(raw: str, filename: str) -> tuple[str, ...]:
    if not raw:
        return ()
    item_ids = tuple(raw.split(", "))
    if any(_ITEM_ID_RE.fullmatch(item_id) is None for item_id in item_ids):
        raise _stage_error(filename, "initial priority list contains an invalid item id")
    return item_ids


def _parse_priority_settings(
    lines: list[str],
    filename: str,
) -> tuple[tuple[RoundPick, ...], tuple[PriorityChange, ...]]:
    entries = [line for line in lines if line.strip()]
    if not entries:
        raise _stage_error(filename, "Priority Settings must contain an initial entry")
    initial_match = _INITIAL_PRIORITIES_RE.fullmatch(entries[0])
    if initial_match is None:
        raise _stage_error(filename, "Priority Settings must start with a canonical initial entry")

    initial: list[RoundPick] = []
    priorities: tuple[Priority, ...] = ("P0", "P1", "P2")
    for priority, raw_items in zip(priorities, initial_match.groups()[1:], strict=True):
        initial.extend(
            RoundPick(item_id, priority) for item_id in _parse_id_list(raw_items, filename)
        )

    changes: list[PriorityChange] = []
    for line in entries[1:]:
        match = _PRIORITY_CHANGE_RE.fullmatch(line)
        if match is None:
            raise _stage_error(filename, "priority adjustment does not match canonical syntax")
        changes.append(
            PriorityChange(
                timestamp=match.group(1),
                item_id=match.group(2),
                from_priority=match.group(3),  # type: ignore[arg-type]
                to_priority=match.group(4),  # type: ignore[arg-type]
                user_text=match.group(5),
            )
        )
    return tuple(initial), tuple(changes)


def _split_list_cell(cell: str) -> tuple[str, ...]:
    if cell in {"", "[]"}:
        return ()
    return tuple(part.strip() for part in cell.split(","))


def _parse_round_picks(cell: str, filename: str) -> tuple[RoundPick, ...]:
    picks: list[RoundPick] = []
    for raw_pick in _split_list_cell(cell):
        match = _ROUND_PICK_RE.fullmatch(raw_pick)
        if match is None:
            raise _stage_error(filename, "round history Picked cell is malformed")
        picks.append(RoundPick(match.group(1), match.group(2)))  # type: ignore[arg-type]
    return tuple(picks)


def _parse_waves(cell: str, filename: str) -> tuple[str, ...]:
    waves = _split_list_cell(cell)
    if any(_WAVE_RE.fullmatch(wave) is None for wave in waves):
        raise _stage_error(filename, "round history Waves cell is malformed")
    return waves


def _parse_nonnegative_int(raw: str, field_name: str, filename: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise _stage_error(filename, f"round history {field_name} must be an integer") from exc
    if value < 0:
        raise _stage_error(filename, f"round history {field_name} must be non-negative")
    return value


def _parse_gate_trend(raw: str, filename: str) -> float | None:
    if raw in {"", "-", "—", "null"}:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise _stage_error(filename, "round history Gate trend must be numeric or null") from exc


def _parse_history(lines: list[str], filename: str) -> tuple[RoundHistoryRow, ...]:
    entries = [line for line in lines if line.strip()]
    if len(entries) < 2 or entries[0] != _HISTORY_HEADER or entries[1] != _HISTORY_SEPARATOR:
        raise _stage_error(filename, "Round History must use the canonical table header")

    history: list[RoundHistoryRow] = []
    for line in entries[2:]:
        if not line.startswith("|") or not line.endswith("|"):
            raise _stage_error(filename, "round history row must be a Markdown table row")
        cells = tuple(cell.strip() for cell in line[1:-1].split("|"))
        if len(cells) != 7:
            raise _stage_error(filename, "round history row must contain exactly seven cells")
        round_num = _parse_nonnegative_int(cells[0], "Round", filename)
        result = _ROUND_RESULT_RE.fullmatch(cells[3])
        if result is None:
            raise _stage_error(filename, "round history Result must use checked/picked syntax")
        history.append(
            RoundHistoryRow(
                round_num=round_num,
                picked=_parse_round_picks(cells[1], filename),
                waves=_parse_waves(cells[2], filename),
                checked_count=int(result.group(1)),
                picked_count=int(result.group(2)),
                blockers=_parse_nonnegative_int(cells[4], "Blockers", filename),
                checkpoint=cells[5],
                gate_trend=_parse_gate_trend(cells[6], filename),
            )
        )
    return tuple(history)


def parse_stage(text: str, *, filename: str = "stage.md") -> StageDocument:
    """Parse one canonical v16 stage controller from text."""
    artifact = parse_frontmatter(text, filename=filename)
    lines = artifact.body.splitlines()
    required = (_STAGE_H1, _PRIORITY_HEADING, _HISTORY_HEADING, _NEXT_ROUND_HEADING)
    try:
        indices = tuple(lines.index(heading) for heading in required)
    except ValueError as exc:
        raise _stage_error(filename, "stage body is missing a required canonical section") from exc
    if indices != tuple(sorted(indices)):
        raise _stage_error(filename, "stage sections are not in canonical order")

    initial, changes = _parse_priority_settings(
        lines[indices[1] + 1 : indices[2]],
        filename,
    )
    history = _parse_history(lines[indices[2] + 1 : indices[3]], filename)
    return StageDocument(
        artifact=artifact,
        current_round=_required_int(artifact.frontmatter, "current_round", filename),
        max_rounds=_required_int(artifact.frontmatter, "max_rounds", filename),
        capacity_per_round=_required_int(artifact.frontmatter, "capacity_per_round", filename),
        initial_priorities=initial,
        priority_changes=changes,
        history=history,
    )
