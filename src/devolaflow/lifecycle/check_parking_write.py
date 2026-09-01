"""File-write lifecycle hook — ``check_parking_write`` (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §5 layer 3.

The parking and compaction surfaces are tool-owned: `devola-parking` and
`devola-compact` write the artifact, append the ledger row, and re-render the
generated views as one operation. A hand-written edit does none of those
things, so it silently produces a view that disagrees with its own ledger —
which is exactly how the document this domain replaces stopped being
trustworthy.

This hook makes that failure loud. It mirrors the S-8 severity split: a
warning in permissive mode, a blocker in STRICT. Writes performed *by* the
tools set ``tool`` in the payload and pass unimpeded.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "file_write"

#: Tool identifiers permitted to write the surfaces below.
TOOL_WRITERS: frozenset[str] = frozenset({"devola-parking", "devola-compact"})

#: Filenames that only a tool may author inside a parking or compact surface.
GENERATED_NAMES: frozenset[str] = frozenset(
    {"INDEX.md", "judge.md", "DIGEST.md", "judgments.yaml", "events.yaml", "mappings.yaml"}
)

_PARKING_DIR = "parking"
_COMPACT_DIR = "compact"


def _guarded_surface(path: str) -> str | None:
    """Return the guarded surface a path belongs to, or ``None``."""

    parts = PurePosixPath(path.replace("\\", "/")).parts
    if _PARKING_DIR in parts:
        index = parts.index(_PARKING_DIR)
        tail = parts[index + 1 :]
        if tail and (tail[0] in GENERATED_NAMES or tail[0] == "risks"):
            return _PARKING_DIR
        return None
    if _COMPACT_DIR in parts:
        index = parts.index(_COMPACT_DIR)
        tail = parts[index + 1 :]
        if tail and (tail[0] in GENERATED_NAMES or tail[0] == "archived"):
            return _COMPACT_DIR
        return None
    return None


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    if not isinstance(payload, dict):
        return []
    path = payload.get("path")
    if not isinstance(path, str) or not path:
        return []
    surface = _guarded_surface(path)
    if surface is None:
        return []
    tool = payload.get("tool")
    if isinstance(tool, str) and tool in TOOL_WRITERS:
        return []
    command = "devola-parking" if surface == _PARKING_DIR else "devola-compact"
    return [
        HookViolation(
            code="CPW001",
            message=(
                f"hand write to the tool-owned {surface} surface rejected: '{path}'. "
                f"Use `{command}` so the artifact, its ledger row, and the generated "
                "views stay in agreement."
            ),
            severity="blocker",
            context={"path": path, "surface": surface, "required_tool": command},
        )
    ]


def check_parking_write(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Reject hand writes to the parking and compaction surfaces.

    Permissive default warns; strict mode raises the blocker violation.
    """

    return finalize(EVENT, _collect_violations(payload), strict=strict)


__all__ = ["EVENT", "GENERATED_NAMES", "TOOL_WRITERS", "check_parking_write"]
