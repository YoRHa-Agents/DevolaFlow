"""NineS advisor — research guidance.

Primary API:  :func:`get_research_advice` — interprets NineS analysis
output and recommends next research / skill-iteration steps.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from devolaflow.nines._cli import run_nines_cli

logger = logging.getLogger(__name__)

_DEFAULT_COMMANDS: dict[str, str] = {
    "self-eval": "nines -f json self-eval",
    "review": "nines -f json analyze --target-path {path}",
    "iterate": "nines -f json iterate --max-rounds 1",
}


@dataclass
class NinesAdvisorConfig:
    """Configuration for the NineS advisor integration."""

    enabled: bool = False
    commands: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_COMMANDS))
    triggers: list[str] = field(default_factory=lambda: ["self-eval"])
    max_retries: int = 2


def _run_nines_command(cmd: str | list[str], retries: int) -> dict[str, object] | None:
    """Execute a NineS CLI command with retries, returning parsed JSON or *None*.

    Delegates to :func:`~devolaflow.nines._cli.run_nines_cli` which uses
    :func:`shlex.split` for string commands, correctly handling quoted arguments.
    """
    for _attempt in range(retries):
        data = run_nines_cli(cmd, timeout=120)
        if data:
            return data
    return None


def get_research_advice(
    config: NinesAdvisorConfig,
    target_path: str,
) -> dict[str, object]:
    """Use NineS to produce research guidance for a target artifact.

    Runs configured NineS commands against *target_path* and returns a
    structured recommendation dict::

        {
            "status": "ok" | "no_result",
            "recommendations": [...],
            "raw_outputs": {<trigger>: <nines_json>, ...},
        }

    Parameters
    ----------
    config:
        Advisor configuration (``commands`` and ``triggers`` are used).
    target_path:
        Filesystem path forwarded to NineS CLI commands.
    """
    recommendations: list[str] = []
    raw_outputs: dict[str, object] = {}

    for trigger in config.triggers:
        cmd_template = config.commands.get(trigger)
        if not cmd_template:
            logger.warning("No command configured for trigger %r, skipping", trigger)
            continue

        cmd = cmd_template.format(path=target_path)
        data = _run_nines_command(cmd, config.max_retries)
        if data is None:
            continue

        raw_outputs[trigger] = data

        summary = data.get("reasoning") or data.get("summary") or data.get("details")
        if summary:
            recommendations.append(f"{trigger}: {summary}")

        next_steps = data.get("next_steps") or data.get("suggestions")
        if isinstance(next_steps, list):
            recommendations.extend(str(s) for s in next_steps)

    if not raw_outputs:
        return {"status": "no_result", "recommendations": [], "raw_outputs": {}}

    return {
        "status": "ok",
        "recommendations": recommendations,
        "raw_outputs": raw_outputs,
    }
