"""NineS CLI v2 command templates — single source of truth.

All NineS CLI commands used by DevolaFlow are defined here.
YAML configs and templates should reference these instead of
defining their own command strings. Eliminates Gap 7 (triple
source of commands across _BUILTIN_SPECS, plugins.yaml, and
context_profiles.yaml).
"""

from __future__ import annotations

NINES_GLOBAL_FLAGS = "-f json"

_BASE = f"nines {NINES_GLOBAL_FLAGS}"

COMMANDS: dict[str, str] = {
    "collect": (
        f'{_BASE} collect --source {{source}} --query "{{query}}" --max-results {{max_results}}'
    ),
    "analyze": (
        f"{_BASE} analyze --target-path {{target}} --depth {{depth}} --agent-impact --keypoints"
    ),
    "self_eval": f"{_BASE} self-eval --project-root {{root}}",
    "self_eval_compare": (f"{_BASE} self-eval --project-root {{root}} --compare --report"),
    "iterate": (f"{_BASE} iterate --threshold {{threshold}} --project-root {{root}}"),
    "benchmark": f"{_BASE} benchmark --project-root {{root}}",
    "update": f"{_BASE} update",
}

STAGE_MAPPING: dict[str, str] = {
    "research": COMMANDS["collect"],
    "analyze": COMMANDS["analyze"],
    "validate": COMMANDS["self_eval_compare"],
    "monitor": COMMANDS["iterate"],
}

DEFAULT_PARAMS: dict[str, str | int] = {
    "source": "github",
    "max_results": 20,
    "depth": "deep",
    "threshold": "0.05",
    "root": ".",
}


def build_command(cmd_key: str, **kwargs: str | int) -> str:
    """Build a NineS CLI command string with parameter substitution.

    Uses DEFAULT_PARAMS for any missing kwargs.
    """
    template = COMMANDS.get(cmd_key)
    if template is None:
        raise ValueError(f"Unknown command key: {cmd_key!r}. Valid keys: {sorted(COMMANDS)}")
    params = {**DEFAULT_PARAMS, **kwargs}
    return template.format(**params)


def build_stage_command(stage: str, **kwargs: str | int) -> str:
    """Build the NineS command for a DevolaFlow stage primitive."""
    template = STAGE_MAPPING.get(stage)
    if template is None:
        raise ValueError(
            f"No NineS command for stage: {stage!r}. Valid stages: {sorted(STAGE_MAPPING)}"
        )
    params = {**DEFAULT_PARAMS, **kwargs}
    return template.format(**params)
