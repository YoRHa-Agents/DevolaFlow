"""Tests for ``scripts/lint_changelog.py`` — the D-5 / G-036 CHANGELOG CI lint.

Fixture-driven: pure checks take injected head/base text; the CLI path is
exercised end-to-end against a temp git repo. Complements (does not
duplicate) the v11.1.1 in-test lint at
``tests/test_changelog_no_duplicate_versions.py`` — that file owns the
duplicate-header assertion against the REAL repo CHANGELOG; this file
pins the script's structural-ordering, immutability-diff, and
version-match rules that the in-test lint cannot perform.

Source: docs/cycle-archive/v11.1.0/retrospective.md §3 D-5;
.local/research/v12.5.0_retrospective.md §6 #12;
.local/research/v14.2.0_gap_analysis.md §2.7 G-036.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "lint_changelog.py"


def _load_lint_module() -> Any:
    """Import ``scripts/lint_changelog.py`` as a module without polluting sys.path."""
    mod_name = "_lint_changelog"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


lint = _load_lint_module()

# Synthetic base fixture covering all 3 historical separator eras
# (" - " / " — " / ", ") plus a prerelease token, mirroring the shapes
# present in the real CHANGELOG.md.
BASE_CHANGELOG = """# Changelog

Intro prose — mutable preamble.

## [1.2.0] - 2026-06-10 — MINOR — Some Title

### Added
- a thing

## [1.1.1] \u2014 2026-06-01

### Fixed
- a fix

## [1.1.0-rc.1], 2026-05-20

- prerelease-era entry

## [1.0.0] - 2026-05-01

- first release
"""

NEW_TOP_BLOCK = """## [1.3.0] - 2026-06-12 — MINOR — Release In Flight

### Added
- new entry

"""


def _all_pure_issues(module: Any, head_text: str, base_text: str, version: str) -> list[Any]:
    blocks, issues = module.parse_blocks(head_text)
    issues.extend(module.check_structure(blocks))
    issues.extend(module.check_version_match(blocks, version))
    issues.extend(module.check_immutability(base_text, head_text))
    return issues


def test_real_repo_changelog_is_self_clean() -> None:
    """The checked-in CHANGELOG.md passes R1 + R3 against the live __version__ (no git)."""
    head_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    blocks, issues = lint.parse_blocks(head_text)
    issues.extend(lint.check_structure(blocks))
    declared = lint.read_declared_version(REPO_ROOT)
    assert declared is not None
    issues.extend(lint.check_version_match(blocks, declared))
    assert issues == [], [i.render("CHANGELOG.md") for i in issues]


@pytest.mark.parametrize(
    ("header", "fragment"),
    [
        ("## [v1.2] - 2026-06-10", "malformed version token"),
        ("## [1.2.0] - 2026-13-99", "invalid calendar date"),
        ("## [1.2.0]", "missing a parseable"),
    ],
)
def test_malformed_header_or_date_fails(header: str, fragment: str) -> None:
    """R1: bad version token / invalid date / missing date each yield a line-numbered issue."""
    text = f"# Changelog\n\n{header}\n\n- body\n"
    blocks, issues = lint.parse_blocks(text)
    issues.extend(lint.check_structure(blocks))
    assert len(issues) == 1
    assert fragment in issues[0].message
    assert issues[0].line == 3


@pytest.mark.parametrize(
    ("upper", "lower", "fragment"),
    [
        ("## [1.1.0] - 2026-06-01", "## [1.2.0] - 2026-05-01", "version order violation"),
        ("## [1.2.0] - 2026-05-01", "## [1.1.0] - 2026-06-01", "date order violation"),
    ],
)
def test_order_violations_fail(upper: str, lower: str, fragment: str) -> None:
    """R1: ascending versions or increasing dates (top-down) are rejected."""
    text = f"# Changelog\n\n{upper}\n\n- a\n\n{lower}\n\n- b\n"
    blocks, issues = lint.parse_blocks(text)
    assert issues == []
    issues = lint.check_structure(blocks)
    assert any(fragment in i.message and i.line == 7 for i in issues), [
        i.render("CHANGELOG.md") for i in issues
    ]


def test_duplicate_version_block_fails() -> None:
    """R1: the PV-03 N-2 double-application class-of-bug is caught with both line numbers."""
    text = "# Changelog\n\n## [1.0.0] - 2026-06-01\n\n- a\n\n## [1.0.0] - 2026-06-01\n\n- a\n"
    blocks, issues = lint.parse_blocks(text)
    assert issues == []
    issues = lint.check_structure(blocks)
    duplicate = [i for i in issues if "duplicate version block" in i.message]
    assert len(duplicate) == 1
    assert duplicate[0].line == 7
    assert "first seen at line 3" in duplicate[0].message


def test_retro_edit_of_released_block_fails_with_line_message() -> None:
    """R2: editing a line inside a previously-released block fails, pointing at the edit.

    Doubles as the well-formed baseline check: the unmodified fixture
    (3 separator eras + a prerelease token) is clean on every rule first.
    """
    baseline = _all_pure_issues(lint, BASE_CHANGELOG, BASE_CHANGELOG, "1.2.0")
    assert baseline == [], [i.render("CHANGELOG.md") for i in baseline]

    head = BASE_CHANGELOG.replace("- a fix", "- a fix (reworded retroactively)")
    issues = lint.check_immutability(BASE_CHANGELOG, head)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.code == "R2"
    assert "'[1.1.1]' was modified" in issue.message
    assert "immutable" in issue.message
    # "- a fix" is line 13 of the fixture; the divergence is pinpointed there.
    assert issue.line == 13


def test_deletion_and_history_insertion_fail() -> None:
    """R2: deleting a released block fails; inserting a new block below the newest fails."""
    deleted = BASE_CHANGELOG.replace("## [1.1.1] \u2014 2026-06-01\n\n### Fixed\n- a fix\n\n", "")
    issues = lint.check_immutability(BASE_CHANGELOG, deleted)
    assert any("'[1.1.1]'" in i.message and "deleted" in i.message for i in issues)

    inserted = BASE_CHANGELOG.replace(
        "## [1.1.1]", "## [1.1.2] - 2026-06-11\n\n- sneaky insertion\n\n## [1.1.1]"
    )
    issues = lint.check_immutability(BASE_CHANGELOG, inserted)
    assert any(
        "'[1.1.2]' was inserted below the newest released base-ref block" in i.message
        for i in issues
    ), [i.render("CHANGELOG.md") for i in issues]


@pytest.mark.parametrize(
    ("top_version", "declared", "ok"),
    [
        ("1.2.0", "1.2.0", True),  # released state: equality
        ("1.2.1", "1.2.0", True),  # release-in-flight: patch bump
        ("1.3.0", "1.2.0", True),  # release-in-flight: minor bump
        ("2.0.0", "1.2.0", True),  # release-in-flight: major bump
        ("1.4.0", "1.2.0", False),  # two minor steps ahead
        ("1.1.0", "1.2.0", False),  # top block older than __version__
    ],
)
def test_version_match_release_in_flight_rule(top_version: str, declared: str, ok: bool) -> None:
    """R3: top block equals __version__ or is exactly one release step newer (laxer rule)."""
    text = f"# Changelog\n\n## [{top_version}] - 2026-06-12\n\n- entry\n"
    blocks, parse_issues = lint.parse_blocks(text)
    assert parse_issues == []
    issues = lint.check_version_match(blocks, declared)
    if ok:
        assert issues == [], [i.render("CHANGELOG.md") for i in issues]
    else:
        assert len(issues) == 1
        assert issues[0].code == "R3"
        assert "release-in-flight" in issues[0].message


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=30
    )


def test_cli_temp_git_repo_append_passes_retro_edit_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End-to-end ``main()`` against a temp git repo: append at top OK, retro-edit FAIL."""
    repo = tmp_path / "repo"
    version_file = repo / "src" / "devolaflow" / "__init__.py"
    version_file.parent.mkdir(parents=True)
    version_file.write_text('__version__ = "1.2.0"\n', encoding="utf-8")
    (repo / "CHANGELOG.md").write_text(BASE_CHANGELOG, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    # New release block appended at the top (release-in-flight 1.3.0 vs __version__ 1.2.0).
    appended = BASE_CHANGELOG.replace("## [1.2.0]", NEW_TOP_BLOCK + "## [1.2.0]", 1)
    (repo / "CHANGELOG.md").write_text(appended, encoding="utf-8")
    args = ["--base-ref", "HEAD", "--repo-root", str(repo)]
    assert lint.main(args) == 0
    assert "lint_changelog: OK" in capsys.readouterr().out

    # Retro-edit of a released block on top of the append.
    head = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    (repo / "CHANGELOG.md").write_text(
        head.replace("- first release", "- rewritten history"), encoding="utf-8"
    )
    assert lint.main(args) == 1
    captured = capsys.readouterr()
    assert "'[1.0.0]' was modified" in captured.err
    assert "lint_changelog: FAIL" in captured.err
