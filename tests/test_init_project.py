"""Tests for devola-init project initialization."""

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
