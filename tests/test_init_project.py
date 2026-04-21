"""Tests for devola-init project initialization."""

import sys
from pathlib import Path

from devolaflow.init_project import _auto_detect, _find_agent_dir, _parse_scope


def test_find_agent_dir():
    agent_dir = _find_agent_dir()
    assert (agent_dir / "SKILL.md").exists() or not agent_dir.exists()


def test_auto_detect_empty(tmp_path: Path):
    result = _auto_detect(tmp_path)
    assert isinstance(result, list)


def test_auto_detect_cursor(tmp_path: Path):
    (tmp_path / ".cursor").mkdir()
    result = _auto_detect(tmp_path)
    assert "cursor" in result


def test_auto_detect_github(tmp_path: Path):
    (tmp_path / ".github").mkdir()
    result = _auto_detect(tmp_path)
    assert "copilot" in result


def test_auto_detect_claude(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    result = _auto_detect(tmp_path)
    assert "claude" in result


def test_parse_scope_defaults_to_project():
    assert _parse_scope([]) == "project"


def test_parse_scope_uses_last_flag():
    assert _parse_scope(["--global"]) == "global"
    assert _parse_scope(["--global", "--project"]) == "project"
    assert _parse_scope(["--project", "--global"]) == "global"


def test_install_cursor(tmp_path: Path, monkeypatch: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_cursor

    install_cursor(agent_dir, tmp_path)
    assert (tmp_path / ".cursor" / "skills" / "devola-flow" / "SKILL.md").exists()
    refs = list((tmp_path / ".cursor" / "skills" / "devola-flow" / "references").glob("*.md"))
    assert len(refs) >= 7


def test_install_cursor_global(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_cursor

    monkeypatch.setenv("HOME", str(tmp_path))
    install_cursor(agent_dir, tmp_path / "project", scope="global")
    assert (tmp_path / ".cursor" / "skills" / "devola-flow" / "SKILL.md").exists()
    assert (tmp_path / ".cursor" / "rules" / "devola-flow-rules.mdc").exists()


def test_install_claude(tmp_path: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_claude

    install_claude(agent_dir, tmp_path)
    skill = tmp_path / ".claude" / "skills" / "devola-flow" / "SKILL.md"
    assert skill.exists()
    refs = list((tmp_path / ".claude" / "skills" / "devola-flow" / "references").glob("*.md"))
    assert len(refs) >= 7


def test_install_claude_global(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_claude

    monkeypatch.setenv("HOME", str(tmp_path))
    install_claude(agent_dir, tmp_path / "project", scope="global")
    skill = tmp_path / ".claude" / "skills" / "devola-flow" / "SKILL.md"
    assert skill.exists()
    content = skill.read_text()
    assert "DevolaFlow" in content


def test_install_copilot(tmp_path: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_copilot

    install_copilot(agent_dir, tmp_path)
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()


def test_auto_detect_local_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = _auto_detect(tmp_path)
    assert "local" in result


def test_auto_detect_no_local_when_present(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".local").mkdir()
    result = _auto_detect(tmp_path)
    assert "local" not in result


def test_auto_detect_local_idempotent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    first = _auto_detect(tmp_path)
    assert "local" in first

    from devolaflow.init_project import install_local

    install_local(_find_agent_dir(), tmp_path)
    second = _auto_detect(tmp_path)
    assert "local" not in second


def test_main_with_no_local_scaffolds_workspace(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    (tmp_path / ".cursor").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(sys, "argv", ["devola-init"])

    from devolaflow.init_project import main

    main()

    assert (tmp_path / ".local" / "feedbacks").is_dir()
    assert (tmp_path / ".local" / "tasks").is_dir()
    assert (tmp_path / ".local" / "index.md").is_file()
    assert (tmp_path / ".cursor" / "skills" / "devola-flow" / "SKILL.md").exists()


def test_install_codex(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_codex

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    install_codex(agent_dir, tmp_path)
    skill = tmp_path / ".codex" / "skills" / "devola-flow" / "SKILL.md"
    assert skill.exists()


def test_install_local_with_existing_rules_dir(tmp_path: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_local

    (tmp_path / ".rules").mkdir()
    install_local(agent_dir, tmp_path)
    assert (tmp_path / ".local" / "feedbacks").is_dir()
    assert (tmp_path / ".rules").is_dir()


def test_main_list_flag(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(sys, "argv", ["devola-init", "--list"])

    from devolaflow.init_project import main

    main()
    out = capsys.readouterr().out
    assert "Detected tools:" in out
    assert "local" in out
    assert "Available targets:" in out
