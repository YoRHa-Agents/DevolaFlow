"""Pinned effort-weighted progress header for ``checklist.md``.

The header is the always-visible work-progress record pinned directly
under the ``# Checklist`` H1:

::

    ## Progress

    `[████▓▓░░░░░░░░░░░░░░] 20%` — done 2 | doing 1 | todo 7 | total 10 (effort-weighted)

Derivation contract (deterministic, body-derived — never trusted from
the rendered line itself):

* ``done``  — checked items.
* ``doing`` — unchecked items picked by the stage.md history row whose
  round number equals ``current_round`` (the in-flight round).
* ``todo``  — every remaining item.
* bar cells and the percentage are weighted by each item's ``effort:``
  metadata (integer 1..8, default 1) so the ratio tracks estimated
  workload rather than raw item counts.

Alignment is enforced twice: the C-9 linter fails a checklist whose
rendered header differs byte-for-byte from the derived one
(``PROGRESS_HEADER`` findings), and the round-boundary /
revert / refresh write paths in :mod:`devolaflow.agent_workspace.change`
re-render the header so canonical mutations can never leave it stale.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from devolaflow.agent_workspace.round_parser import (
    ChecklistItem,
    RoundArtifactParseError,
    StageDocument,
    parse_checklist,
    parse_stage,
)

logger = logging.getLogger(__name__)

__all__ = [
    "PROGRESS_BAR_CELLS",
    "PROGRESS_HEADING",
    "ProgressHeader",
    "ProgressHeaderError",
    "compute_progress_header",
    "extract_progress_line",
    "refresh_progress_header",
    "render_progress_block",
    "render_progress_line",
]

PROGRESS_HEADING: Final[str] = "## Progress"
PROGRESS_BAR_CELLS: Final[int] = 20

_CHECKLIST_H1: Final[str] = "# Checklist"
_DONE_CELL: Final[str] = "█"
_DOING_CELL: Final[str] = "▓"
_TODO_CELL: Final[str] = "░"

_PROGRESS_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^`\[([█▓░]{20})\] (\d{1,3})%` — "
    r"done (\d+) \| doing (\d+) \| todo (\d+) \| total (\d+) \(effort-weighted\)$"
)


class ProgressHeaderError(ValueError):
    """A deterministic progress-header failure with a stable ``kind``."""

    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        self.message = message
        super().__init__(f"[{kind}] {message}")


@dataclass(frozen=True)
class ProgressHeader:
    """Derived done/doing/todo counters plus their effort-weighted bar."""

    done: int
    doing: int
    todo: int
    total: int
    done_effort: int
    doing_effort: int
    total_effort: int

    @property
    def percent(self) -> int:
        """Effort-weighted completion percentage (integer floor)."""
        if not self.total_effort:
            return 0
        return self.done_effort * 100 // self.total_effort

    @property
    def bar(self) -> str:
        """20-cell bar: done ``█``, doing ``▓``, todo ``░`` (effort-weighted)."""
        if not self.total_effort:
            return _TODO_CELL * PROGRESS_BAR_CELLS
        done_cells = self.done_effort * PROGRESS_BAR_CELLS // self.total_effort
        doing_cells = (
            self.done_effort + self.doing_effort
        ) * PROGRESS_BAR_CELLS // self.total_effort - done_cells
        todo_cells = PROGRESS_BAR_CELLS - done_cells - doing_cells
        return _DONE_CELL * done_cells + _DOING_CELL * doing_cells + _TODO_CELL * todo_cells


def _doing_item_ids(
    items: Sequence[ChecklistItem],
    stage: StageDocument | None,
) -> frozenset[str]:
    """Unchecked items picked by the stage history row for ``current_round``."""
    if stage is None:
        return frozenset()
    unchecked = {item.item_id for item in items if not item.checked}
    picked: set[str] = set()
    for row in stage.history:
        if row.round_num == stage.current_round:
            picked.update(pick.item_id for pick in row.picked)
    return frozenset(picked & unchecked)


def compute_progress_header(
    items: Sequence[ChecklistItem],
    stage: StageDocument | None = None,
) -> ProgressHeader:
    """Derive the pinned header from parsed checklist items and round state."""
    doing_ids = _doing_item_ids(items, stage)
    done = sum(item.checked for item in items)
    doing = len(doing_ids)
    return ProgressHeader(
        done=done,
        doing=doing,
        todo=len(items) - done - doing,
        total=len(items),
        done_effort=sum(item.effort for item in items if item.checked),
        doing_effort=sum(item.effort for item in items if item.item_id in doing_ids),
        total_effort=sum(item.effort for item in items),
    )


def render_progress_line(header: ProgressHeader) -> str:
    """Render the single canonical progress line (byte-stable)."""
    return (
        f"`[{header.bar}] {header.percent}%` — "
        f"done {header.done} | doing {header.doing} | todo {header.todo} | "
        f"total {header.total} (effort-weighted)"
    )


def render_progress_block(header: ProgressHeader) -> str:
    """Render the full pinned ``## Progress`` block."""
    return f"{PROGRESS_HEADING}\n\n{render_progress_line(header)}"


def extract_progress_line(body: str) -> str | None:
    """Return the first non-blank line of the ``## Progress`` section.

    ``None`` when the section heading is absent. A present-but-empty
    section returns ``""`` so callers can distinguish it from absence.
    """
    lines = body.splitlines()
    try:
        start = lines.index(PROGRESS_HEADING) + 1
    except ValueError:
        return None
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            return line
    return ""


def _lenient_stage(stage_text: str | None) -> StageDocument | None:
    """Parse stage text, degrading to no-round-state on malformed input.

    S-5: the degradation is logged at WARNING, never silent — a malformed
    stage.md fails loudly on its own strict runtime paths; here it only
    means no item can be attributed to an in-flight round.
    """
    if stage_text is None or not stage_text.strip():
        return None
    try:
        return parse_stage(stage_text)
    except RoundArtifactParseError as exc:
        logger.warning(
            "stage.md failed to parse while deriving the progress header; "
            "treating the in-flight round as empty (doing=0): %s",
            exc,
        )
        return None


def refresh_progress_header(
    checklist_text: str,
    stage_text: str | None = None,
) -> str:
    """Return checklist text with its pinned progress header re-aligned.

    Inserts the ``## Progress`` block directly after the ``# Checklist``
    H1 when absent, otherwise replaces the existing block in place. The
    operation is idempotent: refreshing an already-aligned checklist
    returns byte-identical text.

    Raises:
      RoundArtifactParseError: when the checklist itself is malformed.
      ProgressHeaderError: when the H1 is missing or the ``## Progress``
        heading appears more than once.
    """
    document = parse_checklist(checklist_text)
    header = compute_progress_header(document.items, _lenient_stage(stage_text))
    block_lines = [*render_progress_block(header).split("\n"), ""]

    had_trailing_newline = checklist_text.endswith("\n")
    lines = checklist_text.splitlines()

    heading_indices = [index for index, line in enumerate(lines) if line == PROGRESS_HEADING]
    if len(heading_indices) > 1:
        raise ProgressHeaderError(
            "PROGRESS_HEADER",
            "checklist.md must contain at most one '## Progress' heading",
        )

    if heading_indices:
        start = heading_indices[0]
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if lines[index].startswith("## "):
                end = index
                break
        if end == len(lines):
            block_lines = block_lines[:-1]
        lines[start:end] = block_lines
    else:
        try:
            h1_index = lines.index(_CHECKLIST_H1)
        except ValueError as exc:
            raise ProgressHeaderError(
                "PROGRESS_HEADER",
                "checklist.md body must contain the exact '# Checklist' H1",
            ) from exc
        insert_at = h1_index + 1
        if insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
        else:
            block_lines = ["", *block_lines[:-1], ""]
        lines[insert_at:insert_at] = block_lines

    return "\n".join(lines) + ("\n" if had_trailing_newline else "")
