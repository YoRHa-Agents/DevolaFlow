"""Pure-function activation heuristic for the Pathfinder L2 role.

Pathfinder is a read-only, look-ahead reconnaissance task. The classifier is
pure; the scheduling helper performs one explicit artifact-presence check.
The literal verdicts are intentionally small so callers can keep activation
separate from task dispatch and report handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

from devolaflow.agent_workspace.archive import HARNESS_PREFLIGHT_FILENAME

__all__ = [
    "PathfindVerdict",
    "classify_pathfind_intent",
    "should_schedule_pathfind",
]

PathfindVerdict = Literal["PATHFIND_REQUESTED", "PATHFIND_SUGGESTED", "NO_PATHFIND"]

_REQUESTED_TRIGGERS: Final[tuple[str, ...]] = (
    "pathfinder",
    "path finder",
    "look-ahead",
    "look ahead",
    "scan ahead",
    "find missing harness",
    "find the missing harness",
    "harness reconnaissance",
)

_SUGGESTED_TRIGGERS: Final[tuple[str, ...]] = (
    "infrastructure gap",
    "harness gap",
    "missing fixture",
    "missing golden",
    "what will block next",
    "ahead of the next",
    "next wave",
    "future harness",
    "capability gap",
)


def classify_pathfind_intent(message: str) -> PathfindVerdict:
    """Classify look-ahead language into requested, suggested, or no activation.

    Matching is case-insensitive and requested signals take precedence over
    suggested signals. Empty or whitespace-only input returns ``NO_PATHFIND``.

    >>> classify_pathfind_intent("Run a Pathfinder scan before the next wave")
    'PATHFIND_REQUESTED'
    >>> classify_pathfind_intent("Check for an infrastructure gap")
    'PATHFIND_SUGGESTED'
    >>> classify_pathfind_intent("Implement the endpoint")
    'NO_PATHFIND'
    """
    if not message or not message.strip():
        return "NO_PATHFIND"
    lowered = message.lower()
    if any(trigger in lowered for trigger in _REQUESTED_TRIGGERS):
        return "PATHFIND_REQUESTED"
    if any(trigger in lowered for trigger in _SUGGESTED_TRIGGERS):
        return "PATHFIND_SUGGESTED"
    return "NO_PATHFIND"


def should_schedule_pathfind(change_folder: Path) -> bool:
    """Return whether the artifact-as-flag enables automatic Pathfinder scheduling.

    A missing change folder is an invalid caller state and raises explicitly.
    Existing folders are scheduled only when their harness preflight artifact
    exists as a regular file.
    """
    if not change_folder.is_dir():
        raise FileNotFoundError(f"Pathfinder change folder does not exist: {change_folder}")
    return (change_folder / HARNESS_PREFLIGHT_FILENAME).is_file()


# Keep the public heuristic visible to the dead-API audit until an operator
# adapter wires activation into the host command surface.
_pathfinder_dead_api_pins = (classify_pathfind_intent, should_schedule_pathfind)
