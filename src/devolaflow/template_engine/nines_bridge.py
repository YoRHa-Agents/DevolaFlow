"""Bridge between template nines_commands and task dispatch context.

Extracts NineS command hints from stage config and formats them for
inclusion in task agent context.  Addresses Gap 1: template nines_commands
were previously declaration-only, not consumed by any code path.
"""

from __future__ import annotations

from typing import Any


def extract_nines_commands(stage_config: dict[str, Any] | None) -> list[str]:
    """Extract ``nines_commands`` from a stage's config block."""
    if not stage_config:
        return []
    commands = stage_config.get("nines_commands", [])
    if isinstance(commands, str):
        return [commands]
    if isinstance(commands, list):
        return [str(c) for c in commands]
    return []


def format_nines_context(commands: list[str], stage_name: str = "") -> str:
    """Format NineS commands for injection into task dispatch shared_context."""
    if not commands:
        return ""
    header = f"NineS commands for stage '{stage_name}':" if stage_name else "NineS commands:"
    lines = [header]
    for i, cmd in enumerate(commands, 1):
        lines.append(f"  {i}. {cmd}")
    lines.append("Execute these NineS commands as part of this task's workflow.")
    return "\n".join(lines)


def nines_commands_to_dispatch_context(
    stage_config: dict[str, Any] | None,
    stage_name: str = "",
) -> dict[str, str]:
    """Extract and format NineS commands for dispatch injection.

    Returns a dict with ``nines_context`` key suitable for merging
    into ``dispatch['context']['shared_context']``.
    """
    commands = extract_nines_commands(stage_config)
    context = format_nines_context(commands, stage_name)
    return {"nines_context": context}
