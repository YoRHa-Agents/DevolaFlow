"""Tests for the English-only agent-facing language gate."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts.check_agent_language import (
    DEFAULT_TARGETS,
    FIXTURE_EXEMPTION_MARKER,
    TRIGGER_EXEMPTION_LINES,
    find_cjk,
    main,
)

EXPECTED_TARGETS = (
    "AGENTS.md",
    ".rules",
    ".cursor/skills",
    ".cursor/rules",
    "workflow-system/agent",
    "schemas",
    ".github/copilot-instructions.md",
    "src/devolaflow/task_adaptive_selector.py",
    "src/devolaflow/harness",
    "tests/fixtures/harness",
)


def test_agent_target_inventory_is_complete_and_relative() -> None:
    assert DEFAULT_TARGETS == EXPECTED_TARGETS
    assert all(not Path(target).is_absolute() for target in DEFAULT_TARGETS)
    assert all(".." not in Path(target).parts for target in DEFAULT_TARGETS)


def test_unknown_inventory_target_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="language inventory target is missing"):
        find_cjk(tmp_path, ("unapproved/surface",))


def test_absolute_or_parent_inventory_target_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be repository-relative"):
        find_cjk(tmp_path, (str(tmp_path / "absolute.md"),))
    with pytest.raises(ValueError, match="must be repository-relative"):
        find_cjk(tmp_path, ("../outside",))


def test_agent_targets_are_cjk_free() -> None:
    root = Path(__file__).resolve().parents[1]
    assert find_cjk(root) == []


def test_q6_human_archive_and_local_paths_are_exempt(tmp_path: Path) -> None:
    (tmp_path / "workflow-system" / "human" / "en").mkdir(parents=True)
    (tmp_path / "docs" / "cycle-archive").mkdir(parents=True)
    (tmp_path / ".local" / "research").mkdir(parents=True)
    (tmp_path / "workflow-system" / "human" / "en" / "guide.md").write_text(
        "中文 is allowed here\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "cycle-archive" / "old.md").write_text(
        "中文 is historical evidence\n", encoding="utf-8"
    )
    (tmp_path / ".local" / "research" / "notes.md").write_text(
        "中文 is local evidence\n", encoding="utf-8"
    )

    assert find_cjk(tmp_path, ("workflow-system", "docs", ".local")) == []


def test_install_trigger_exemption_covers_exactly_nine_lines(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    relative = ".cursor/skills/install-devola-flow/SKILL.md"
    source = root / relative
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert len(TRIGGER_EXEMPTION_LINES[relative]) == 9
    assert find_cjk(tmp_path, (relative,)) == []

    original_lines = target.read_text(encoding="utf-8").splitlines()
    target.write_text(
        "\n".join(original_lines + ["未批准的 agent-facing text"]) + "\n",
        encoding="utf-8",
    )
    assert find_cjk(tmp_path, (relative,)) == [f"{relative}:{len(original_lines) + 1}"]


def test_unapproved_cjk_in_agent_surface_hard_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for relative in DEFAULT_TARGETS:
        if relative == ".github/copilot-instructions.md":
            continue
        target = tmp_path / relative
        if target.suffix:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")
        else:
            target.mkdir(parents=True)
    target = tmp_path / "workflow-system" / "agent" / "SKILL.md"
    target.write_text("# agent prompt\n未批准\n", encoding="utf-8")

    assert main(["--root", str(tmp_path)]) == 1
    assert "workflow-system/agent/SKILL.md:2" in capsys.readouterr().out
    target.write_text("# agent prompt\n", encoding="utf-8")
    assert main(["--root", str(tmp_path)]) == 0


def test_untracked_copilot_target_is_scanned_outside_a_git_repo(tmp_path: Path) -> None:
    target = tmp_path / ".github" / "copilot-instructions.md"
    target.parent.mkdir(parents=True)
    target.write_text("unapproved 中文\n", encoding="utf-8")

    assert find_cjk(tmp_path, (".github/copilot-instructions.md",)) == [
        ".github/copilot-instructions.md:1"
    ]


def test_tracked_copilot_target_is_scanned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / ".github" / "copilot-instructions.md"
    target.parent.mkdir(parents=True)
    target.write_text("tracked 中文\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.check_agent_language.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0),
    )

    assert find_cjk(tmp_path, (".github/copilot-instructions.md",)) == [
        ".github/copilot-instructions.md:1"
    ]


def test_only_marked_test_fixtures_are_exempt(tmp_path: Path) -> None:
    fixture_root = tmp_path / "tests" / "fixtures" / "harness"
    fixture_root.mkdir(parents=True)
    (fixture_root / "marked.yaml").write_text(
        f"# {FIXTURE_EXEMPTION_MARKER}\n中文 fixture payload\n",
        encoding="utf-8",
    )
    (fixture_root / "unmarked.yaml").write_text("中文 fixture payload\n", encoding="utf-8")

    assert find_cjk(tmp_path, ("tests/fixtures/harness",)) == [
        "tests/fixtures/harness/unmarked.yaml:1"
    ]
