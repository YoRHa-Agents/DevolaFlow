"""Tests for compile_prefs in local/compiler."""

from __future__ import annotations

from pathlib import Path

from devolaflow.local.compiler import compile_prefs


def test_compile_prefs_creates_output(tmp_path: Path) -> None:
    prefs = tmp_path / "prefs.md"
    prefs.write_text("# Personal Preferences\n- Role: engineer\n- Familiarity: high\n")
    output = tmp_path / "CLAUDE.local.md"
    result = compile_prefs(prefs, output)
    assert result is not None
    assert output.exists()
    assert "Personal Preferences" in output.read_text()
    assert result.target == "claude_local"
    assert result.tokens_used > 0


def test_compile_prefs_missing_file(tmp_path: Path) -> None:
    prefs = tmp_path / "prefs.md"
    output = tmp_path / "CLAUDE.local.md"
    result = compile_prefs(prefs, output)
    assert result is None
    assert not output.exists()


def test_compile_prefs_empty_file(tmp_path: Path) -> None:
    prefs = tmp_path / "prefs.md"
    prefs.write_text("")
    output = tmp_path / "CLAUDE.local.md"
    result = compile_prefs(prefs, output)
    assert result is None
