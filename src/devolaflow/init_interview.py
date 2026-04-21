"""Interactive interview module for repo-init ``mode=full``.

Provides detection and suggestion logic for the 8-phase interview that
runs during the ``interview`` stage of the repo-init workflow. The actual
user interaction is driven by the L3 task agent via AskQuestion; this
module supplies the analysis and generation functions.

Phase mapping:
  P1 — ask intent (handled by L3 prompt)
  P2 — explore codebase (reuse analyze stage output)
  P3 — fill gaps (handled by L3 prompt)
  P4 — generate .rules/ source (handled by L3 + RuleCompiler)
  P5 — generate .local/memory/prefs.md (handled by L3 + this module)
  P6 — suggest and create skills (this module)
  P7 — suggest and configure hooks (this module)
  P8 — summary (handled by L3 prompt)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillSuggestion:
    """A suggested skill to create for the project."""

    name: str
    description: str
    commands: list[str]
    trigger: str
    tools: list[str] = field(default_factory=list)


@dataclass
class HookSuggestion:
    """A suggested hook to configure for the project."""

    name: str
    description: str
    event: str
    command: str
    matcher: str = ""
    tool: str = ""


_TEST_FRAMEWORKS: dict[str, dict[str, str]] = {
    "pytest": {
        "detect": "pyproject.toml,setup.cfg,pytest.ini,conftest.py",
        "cmd": "python -m pytest",
    },
    "jest": {"detect": "jest.config.js,jest.config.ts,jest.config.mjs", "cmd": "npx jest"},
    "vitest": {"detect": "vitest.config.ts,vitest.config.js", "cmd": "npx vitest run"},
    "mocha": {"detect": ".mocharc.yml,.mocharc.json,.mocharc.js", "cmd": "npx mocha"},
    "go_test": {"detect": "go.mod", "cmd": "go test ./..."},
    "cargo_test": {"detect": "Cargo.toml", "cmd": "cargo test"},
}

_LINT_TOOLS: dict[str, dict[str, str]] = {
    "ruff": {"detect": "ruff.toml,pyproject.toml", "cmd": "ruff check ."},
    "eslint": {
        "detect": ".eslintrc,.eslintrc.js,.eslintrc.json,"
        ".eslintrc.yml,eslint.config.js,eslint.config.mjs",
        "cmd": "npx eslint .",
    },
    "biome": {"detect": "biome.json,biome.jsonc", "cmd": "npx biome check ."},
    "golangci-lint": {"detect": ".golangci.yml,.golangci.yaml", "cmd": "golangci-lint run"},
    "clippy": {"detect": "Cargo.toml", "cmd": "cargo clippy"},
}

_FORMATTERS: dict[str, dict[str, str]] = {
    "ruff_format": {"detect": "ruff.toml,pyproject.toml", "cmd": "ruff format", "lang": "python"},
    "black": {"detect": "pyproject.toml", "cmd": "black .", "lang": "python"},
    "prettier": {
        "detect": ".prettierrc,.prettierrc.json,.prettierrc.js,"
        ".prettierrc.yml,prettier.config.js,prettier.config.mjs",
        "cmd": "npx prettier --write",
        "lang": "javascript",
    },
    "biome_format": {
        "detect": "biome.json,biome.jsonc",
        "cmd": "npx biome format --write",
        "lang": "javascript",
    },
    "gofmt": {"detect": "go.mod", "cmd": "gofmt -w .", "lang": "go"},
    "rustfmt": {"detect": "rustfmt.toml,Cargo.toml", "cmd": "cargo fmt", "lang": "rust"},
}


def _files_exist(cwd: Path, detect_str: str) -> bool:
    """Check if any of the comma-separated filenames exist in cwd."""
    return any((cwd / f.strip()).exists() for f in detect_str.split(","))


def detect_project_tools(cwd: str | Path) -> dict[str, Any]:
    """Detect test frameworks, linters, and formatters in the project.

    Returns a dict with keys: test_frameworks, lint_tools, formatters,
    each mapping to a list of detected tool dicts.
    """
    cwd = Path(cwd)
    result: dict[str, list[dict[str, str]]] = {
        "test_frameworks": [],
        "lint_tools": [],
        "formatters": [],
    }

    for name, info in _TEST_FRAMEWORKS.items():
        if _files_exist(cwd, info["detect"]):
            result["test_frameworks"].append({"name": name, "cmd": info["cmd"]})

    for name, info in _LINT_TOOLS.items():
        if _files_exist(cwd, info["detect"]):
            result["lint_tools"].append({"name": name, "cmd": info["cmd"]})

    for name, info in _FORMATTERS.items():
        if _files_exist(cwd, info["detect"]):
            result["formatters"].append(
                {
                    "name": name,
                    "cmd": info["cmd"],
                    "lang": info["lang"],
                }
            )

    return result


def suggest_skills(detected: dict[str, Any]) -> list[SkillSuggestion]:
    """Generate skill suggestions based on detected project tools."""
    suggestions: list[SkillSuggestion] = []

    test_cmds = [t["cmd"] for t in detected.get("test_frameworks", [])]
    lint_cmds = [t["cmd"] for t in detected.get("lint_tools", [])]

    if test_cmds or lint_cmds:
        commands = lint_cmds + test_cmds
        suggestions.append(
            SkillSuggestion(
                name="verify",
                description="Run full verification: lint + test",
                commands=commands,
                trigger="verify changes before commit",
                tools=["claude", "cursor"],
            )
        )

    if test_cmds:
        suggestions.append(
            SkillSuggestion(
                name="test",
                description="Run test suite",
                commands=test_cmds,
                trigger="run tests",
                tools=["claude", "cursor"],
            )
        )

    return suggestions


def suggest_hooks(detected: dict[str, Any]) -> list[HookSuggestion]:
    """Generate hook suggestions based on detected formatters."""
    suggestions: list[HookSuggestion] = []

    for fmt in detected.get("formatters", []):
        suggestions.append(
            HookSuggestion(
                name=f"format-on-edit-{fmt['lang']}",
                description=f"Auto-format {fmt['lang']} files after edit using {fmt['name']}",
                event="PostToolUse",
                command=f"{fmt['cmd']} $FILE",
                matcher="Write|Edit",
                tool="claude",
            )
        )

    return suggestions


def generate_skill_file(skill: SkillSuggestion) -> str:
    """Generate SKILL.md content for a skill suggestion."""
    lines = [
        "---",
        f'name: "{skill.name}"',
        f'description: "{skill.description}"',
        "---",
        "",
        f"# {skill.name}",
        "",
        f"{skill.description}.",
        "",
        "Run the following commands in sequence, stop on first failure:",
        "",
    ]
    for i, cmd in enumerate(skill.commands, 1):
        lines.append(f"{i}. `{cmd}`")

    return "\n".join(lines) + "\n"


def write_skill(
    skill: SkillSuggestion,
    cwd: Path,
    tool: str = "claude",
) -> Path:
    """Write a skill SKILL.md file to the appropriate tool directory."""
    if tool == "cursor":
        skill_dir = cwd / ".cursor" / "skills" / skill.name
    else:
        skill_dir = cwd / ".claude" / "skills" / skill.name

    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(generate_skill_file(skill), encoding="utf-8")
    return path


def generate_claude_hook_config(hooks: list[HookSuggestion]) -> dict[str, Any]:
    """Generate Claude Code hooks configuration for .claude/settings.json."""
    hook_entries = []
    for hook in hooks:
        hook_entries.append(
            {
                "type": "command",
                "event": hook.event,
                "matcher": hook.matcher,
                "command": hook.command,
            }
        )
    return {"hooks": hook_entries}


__all__ = [
    "HookSuggestion",
    "SkillSuggestion",
    "detect_project_tools",
    "generate_claude_hook_config",
    "generate_skill_file",
    "suggest_hooks",
    "suggest_skills",
    "write_skill",
]
