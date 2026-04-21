"""Tests for the init_interview module."""

from __future__ import annotations

from pathlib import Path

from devolaflow.init_interview import (
    SkillSuggestion,
    detect_project_tools,
    generate_claude_hook_config,
    generate_skill_file,
    suggest_hooks,
    suggest_skills,
    write_skill,
)


def test_detect_project_tools_empty(tmp_path: Path) -> None:
    result = detect_project_tools(tmp_path)
    assert result["test_frameworks"] == []
    assert result["lint_tools"] == []
    assert result["formatters"] == []


def test_detect_project_tools_python(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    (tmp_path / "ruff.toml").write_text("")
    result = detect_project_tools(tmp_path)
    names = [t["name"] for t in result["test_frameworks"]]
    assert "pytest" in names
    lint_names = [t["name"] for t in result["lint_tools"]]
    assert "ruff" in lint_names
    fmt_names = [t["name"] for t in result["formatters"]]
    assert "ruff_format" in fmt_names


def test_detect_project_tools_node(tmp_path: Path) -> None:
    (tmp_path / "jest.config.js").write_text("")
    (tmp_path / ".prettierrc").write_text("{}")
    result = detect_project_tools(tmp_path)
    test_names = [t["name"] for t in result["test_frameworks"]]
    assert "jest" in test_names
    fmt_names = [t["name"] for t in result["formatters"]]
    assert "prettier" in fmt_names


def test_suggest_skills_with_tests() -> None:
    detected = {
        "test_frameworks": [{"name": "pytest", "cmd": "python -m pytest"}],
        "lint_tools": [{"name": "ruff", "cmd": "ruff check ."}],
        "formatters": [],
    }
    skills = suggest_skills(detected)
    assert len(skills) >= 1
    verify = next(s for s in skills if s.name == "verify")
    assert "ruff check ." in verify.commands
    assert "python -m pytest" in verify.commands


def test_suggest_skills_empty() -> None:
    detected = {"test_frameworks": [], "lint_tools": [], "formatters": []}
    skills = suggest_skills(detected)
    assert skills == []


def test_suggest_hooks_with_formatter() -> None:
    detected = {
        "test_frameworks": [],
        "lint_tools": [],
        "formatters": [{"name": "ruff_format", "cmd": "ruff format", "lang": "python"}],
    }
    hooks = suggest_hooks(detected)
    assert len(hooks) == 1
    assert hooks[0].event == "PostToolUse"
    assert "python" in hooks[0].name


def test_generate_skill_file() -> None:
    skill = SkillSuggestion(
        name="verify",
        description="Run verification",
        commands=["ruff check .", "python -m pytest"],
        trigger="verify",
    )
    content = generate_skill_file(skill)
    assert "name:" in content
    assert "ruff check ." in content
    assert "python -m pytest" in content


def test_write_skill(tmp_path: Path) -> None:
    skill = SkillSuggestion(
        name="test-skill",
        description="Test",
        commands=["echo ok"],
        trigger="test",
    )
    path = write_skill(skill, tmp_path, tool="claude")
    assert path.exists()
    assert ".claude/skills/test-skill/SKILL.md" in str(path)


def test_generate_claude_hook_config() -> None:
    from devolaflow.init_interview import HookSuggestion

    hooks = [
        HookSuggestion(
            name="fmt",
            description="format",
            event="PostToolUse",
            command="ruff format $FILE",
            matcher="Write|Edit",
        )
    ]
    config = generate_claude_hook_config(hooks)
    assert "hooks" in config
    assert len(config["hooks"]) == 1
    assert config["hooks"][0]["event"] == "PostToolUse"
