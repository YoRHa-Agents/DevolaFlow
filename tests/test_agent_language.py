"""Tests for the English-only agent-facing language gate."""

from __future__ import annotations

from pathlib import Path

from scripts.check_agent_language import find_cjk


def test_agent_targets_are_cjk_free() -> None:
    root = Path(__file__).resolve().parents[1]
    assert find_cjk(root) == []


def test_q6_human_and_archive_paths_are_exempt(tmp_path: Path) -> None:
    (tmp_path / "workflow-system" / "human" / "zh").mkdir(parents=True)
    (tmp_path / "docs" / "cycle-archive").mkdir(parents=True)
    (tmp_path / "workflow-system" / "human" / "zh" / "guide.md").write_text(
        "中文 is allowed here\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "cycle-archive" / "old.md").write_text(
        "中文 is historical evidence\n", encoding="utf-8"
    )

    assert find_cjk(tmp_path, ("workflow-system", "docs")) == []
