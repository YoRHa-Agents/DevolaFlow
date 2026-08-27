"""Tests for devolaflow.skills_doctor (`devola-init-doctor --skills`, Track B-2)."""

from __future__ import annotations

from pathlib import Path

from devolaflow.skills_doctor import STAMP_FILENAME, scan_installed_skills

CURRENT = "15.0.0"


def _mk_skill_dir(base: Path, stamp: str | None = None) -> Path:
    skill_dir = base / "skills" / "devola-flow"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# devola-flow\n", encoding="utf-8")
    if stamp is not None:
        (skill_dir / STAMP_FILENAME).write_text(f"{stamp}\n", encoding="utf-8")
    return skill_dir


def _scan(tmp_path: Path) -> list:
    cwd = tmp_path / "project"
    home = tmp_path / "home"
    cwd.mkdir(exist_ok=True)
    home.mkdir(exist_ok=True)
    return scan_installed_skills(
        cwd=cwd,
        home=home,
        codex_home=home / ".codex",
        dsh_home=home / ".dsh",
        current_version=CURRENT,
    )


def test_no_installs_returns_empty(tmp_path: Path) -> None:
    assert _scan(tmp_path) == []


def test_current_install_reports_current(tmp_path: Path) -> None:
    (tmp_path / "project").mkdir()
    (tmp_path / "home").mkdir()
    _mk_skill_dir(tmp_path / "project" / ".cursor", stamp=CURRENT)
    (found,) = _scan(tmp_path)
    assert (found.tool, found.scope, found.status) == ("cursor", "project", "current")
    assert found.installed_version == CURRENT


def test_stale_install_reports_stale(tmp_path: Path) -> None:
    (tmp_path / "project").mkdir()
    (tmp_path / "home").mkdir()
    _mk_skill_dir(tmp_path / "home" / ".claude", stamp="14.0.0")
    (found,) = _scan(tmp_path)
    assert (found.tool, found.scope, found.status) == ("claude", "global", "stale")


def test_missing_or_date_stamp_reports_unknown_version(tmp_path: Path) -> None:
    (tmp_path / "project").mkdir()
    (tmp_path / "home").mkdir()
    # No stamp at all.
    _mk_skill_dir(tmp_path / "project" / ".claude", stamp=None)
    # Date-fallback stamp (written when the install-time version fetch failed).
    _mk_skill_dir(tmp_path / "home" / ".kimi", stamp="2026-08-20T00:00:00Z")
    statuses = {(i.tool, i.scope): i.status for i in _scan(tmp_path)}
    assert statuses[("claude", "project")] == "unknown-version"
    assert statuses[("kimicode", "global")] == "unknown-version"


def test_dsh_install_reports_current(tmp_path: Path) -> None:
    _mk_skill_dir(tmp_path / "home" / ".dsh", stamp=CURRENT)
    (found,) = _scan(tmp_path)
    assert (found.tool, found.scope, found.status) == ("dsh", "global", "current")


def test_copilot_version_derives_from_frontmatter(tmp_path: Path) -> None:
    cwd = tmp_path / "project"
    (cwd / ".github").mkdir(parents=True)
    (tmp_path / "home").mkdir()
    (cwd / ".github" / "copilot-instructions.md").write_text(
        f"---\nid: devola-flow\nversion: {CURRENT}\n---\n# body\n", encoding="utf-8"
    )
    (found,) = _scan(tmp_path)
    assert (found.tool, found.installed_version, found.status) == (
        "copilot",
        CURRENT,
        "current",
    )


def test_copilot_non_devola_file_is_ignored(tmp_path: Path) -> None:
    cwd = tmp_path / "project"
    (cwd / ".github").mkdir(parents=True)
    (tmp_path / "home").mkdir()
    (cwd / ".github" / "copilot-instructions.md").write_text(
        "# User's own copilot instructions\n", encoding="utf-8"
    )
    assert _scan(tmp_path) == []


def test_rule_tree_install_detected_with_stamp(tmp_path: Path) -> None:
    cwd = tmp_path / "project"
    rules = cwd / ".rules"
    rules.mkdir(parents=True)
    (tmp_path / "home").mkdir()
    (rules / "devola-flow.md").write_text("# devola-flow rules\n", encoding="utf-8")
    (rules / STAMP_FILENAME).write_text(f"{CURRENT}\n", encoding="utf-8")
    (found,) = _scan(tmp_path)
    assert (found.tool, found.scope, found.status) == ("zed", "project", "current")
