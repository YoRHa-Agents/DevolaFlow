"""Tests for scripts/bump_version.py miss-handling (v14.2.1 G-032).

Closes G-032 from `.local/research/v14.2.0_gap_analysis.md` §2.7 (source
finding F-R26): a canonical-location regex that matched nothing used to
SKIP-and-continue with exit 0 — a silent partial bump (S-5 violation).

Contract pinned here:

* **Pattern miss on an existing canonical file → HARD FAIL** — non-zero
  exit, stderr message naming both the file and the pattern.
* **File-not-found → soft SKIP** — absent files are the legitimately
  missing case (opt-in mirror / partial checkout), so the bump proceeds.
* Dry-run honours the same hard-fail so CI dry-runs catch drift without
  writing anything.
* **Tagging is phase two** — the requested version must already be committed
  at a clean current HEAD, and an existing tag is never replaced.

The fixtures build a minimal repo in tmp_path and pass it via the
``root=`` kwarg, so the real repository is never touched.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.bump_version import VERSION_LOCATIONS, bump


def _make_minimal_repo(tmp_path: Path) -> Path:
    """Repo with only the two root canonical files, both pattern-matching."""
    (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\n', encoding="utf-8")
    pkg = tmp_path / "src" / "devolaflow"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
    return tmp_path


def _make_complete_repo(tmp_path: Path) -> Path:
    """Build a fixture containing one match for every canonical location."""
    root = _make_minimal_repo(tmp_path)
    by_path: dict[str, list[str]] = {}
    for location in VERSION_LOCATIONS:
        marker = location["replacement"].format(version="1.0.0")
        by_path.setdefault(location["path"], []).append(marker)
    for path, markers in by_path.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(markers) + "\n", encoding="utf-8")
    return root


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_git_repo(tmp_path: Path) -> Path:
    root = _make_minimal_repo(tmp_path)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Version Test")
    _git(root, "config", "user.email", "version-test@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial version")
    _git(root, "update-ref", "refs/remotes/origin/main", _git(root, "rev-parse", "HEAD"))
    return root


def test_missing_files_skip_soft_and_matches_update(tmp_path: Path, capsys) -> None:
    """Absent canonical files SKIP softly; present+matching files update."""
    root = _make_minimal_repo(tmp_path)

    updated = bump("1.1.0", root=root)

    assert sorted(updated) == ["pyproject.toml", "src/devolaflow/__init__.py"]
    assert '__version__ = "1.1.0"' in (root / "src/devolaflow/__init__.py").read_text()
    assert 'version = "1.1.0"' in (root / "pyproject.toml").read_text()
    out = capsys.readouterr().out
    # Every other canonical location is absent → soft SKIP, no failure.
    assert out.count("SKIP") == len(VERSION_LOCATIONS) - 2
    assert "MISS" not in out

    skill = root / "workflow-system" / "agent" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        'version: "1.1.0"\n> **Now Using DevolaFlow v1.1.0**\n**Current version:** 1.1.0\n',
        encoding="utf-8",
    )
    readme = root / "README.md"
    readme.write_text('example prints "DevolaFlow v1.1.0"\n', encoding="utf-8")

    for requested in ("1.1.0-rc.1", "1.1.0-rc.2", "1.2.0"):
        updated = bump(requested, root=root)
        assert updated.count("workflow-system/agent/SKILL.md") == 3
        assert "README.md" in updated
        assert requested in skill.read_text(encoding="utf-8")
        assert f'prints "DevolaFlow v{requested}"' in readme.read_text(encoding="utf-8")

    assert "rc.2" not in skill.read_text(encoding="utf-8")
    assert "rc.2" not in readme.read_text(encoding="utf-8")


def test_pattern_miss_on_existing_file_hard_fails(tmp_path: Path, capsys) -> None:
    """An existing canonical file whose pattern matches nothing → exit 1,
    with the file path AND the pattern named in the error output (G-032)."""
    root = _make_minimal_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("no version badge in here\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        bump("1.1.0", root=root)

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "README.md" in captured.err
    readme_patterns = [loc["pattern"] for loc in VERSION_LOCATIONS if loc["path"] == "README.md"]
    assert readme_patterns, "README.md must remain a canonical VERSION_LOCATIONS path"
    for pat in readme_patterns:
        assert repr(pat) in captured.err, f"miss message must name the pattern {pat!r}"
    assert '__version__ = "1.0.0"' in (root / "src/devolaflow/__init__.py").read_text()
    assert 'version = "1.0.0"' in (root / "pyproject.toml").read_text()


def test_dry_run_pattern_miss_also_hard_fails_without_writing(tmp_path: Path) -> None:
    """Dry-run reports the same hard failure and leaves all files untouched."""
    root = _make_minimal_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text("no version badge in here\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        bump("1.1.0", dry_run=True, root=root)

    assert excinfo.value.code == 1
    # Nothing was modified — dry-run + failure are both non-destructive.
    assert '__version__ = "1.0.0"' in (root / "src/devolaflow/__init__.py").read_text()
    assert 'version = "1.0.0"' in (root / "pyproject.toml").read_text()
    assert readme.read_text() == "no version badge in here\n"


def test_complete_fixture_dry_run_matches_all_canonical_patterns(tmp_path: Path) -> None:
    """A full fixture proves every canonical pattern is matched exactly once."""
    root = _make_complete_repo(tmp_path)
    before = {
        path: (root / path).read_bytes()
        for path in {location["path"] for location in VERSION_LOCATIONS}
    }

    updated = bump("1.1.0", dry_run=True, root=root)

    assert len(updated) == len(VERSION_LOCATIONS)
    assert updated.count("workflow-system/agent/SKILL.md") == 3
    assert {
        path: (root / path).read_bytes()
        for path in {location["path"] for location in VERSION_LOCATIONS}
    } == before


def test_duplicate_canonical_pattern_hard_fails(tmp_path: Path, capsys) -> None:
    """A duplicated canonical marker cannot be silently partially bumped."""
    root = _make_minimal_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        'example prints "DevolaFlow v1.0.0"\nanother prints "DevolaFlow v1.0.0"\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as excinfo:
        bump("1.1.0", root=root)

    assert excinfo.value.code == 1
    assert "expected exactly one match, found 2" in capsys.readouterr().out


def test_tag_refuses_pre_bump_before_any_file_write(tmp_path: Path, capsys) -> None:
    root = _make_minimal_repo(tmp_path)
    before = {
        path: (root / path).read_bytes()
        for path in ("src/devolaflow/__init__.py", "pyproject.toml")
    }

    with pytest.raises(SystemExit) as excinfo:
        bump("1.1.0", tag=True, root=root)

    assert excinfo.value.code == 1
    assert {
        path: (root / path).read_bytes()
        for path in ("src/devolaflow/__init__.py", "pyproject.toml")
    } == before
    error = capsys.readouterr().err
    assert "--tag is a finalization step" in error
    assert "without --tag" in error
    assert "release-preflight" in error
    assert "commit" in error


def test_tag_dry_run_previews_exactly_one_release_phase(tmp_path: Path, capsys) -> None:
    bump_root = _make_minimal_repo(tmp_path)
    before = (bump_root / "src/devolaflow/__init__.py").read_bytes()

    updated = bump("1.1.0", dry_run=True, tag=True, root=bump_root)

    assert sorted(updated) == ["pyproject.toml", "src/devolaflow/__init__.py"]
    assert (bump_root / "src/devolaflow/__init__.py").read_bytes() == before
    bump_preview = capsys.readouterr().out
    assert "version-file updates only" in bump_preview
    assert "create annotated git tag" not in bump_preview

    tag_root = tmp_path / "tag-preview"
    tag_root.mkdir()
    _make_git_repo(tag_root)
    updated = bump("1.0.0", dry_run=True, tag=True, root=tag_root)

    assert updated == []
    tag_preview = capsys.readouterr().out
    assert "create annotated git tag v1.0.0 at current HEAD" in tag_preview
    assert "READY  verified main" in tag_preview
    assert _git(tag_root, "tag", "--list", "v1.0.0") == ""


def test_tag_creates_annotated_ref_at_clean_head_while_ignoring_untracked(
    tmp_path: Path,
    capsys,
) -> None:
    root = _make_git_repo(tmp_path)
    (root / "untracked.txt").write_text("allowed\n", encoding="utf-8")
    head_before = _git(root, "rev-parse", "HEAD")

    updated = bump("1.0.0", tag=True, root=root)

    assert updated == []
    assert _git(root, "cat-file", "-t", "v1.0.0") == "tag"
    assert _git(root, "rev-list", "-n", "1", "v1.0.0") == head_before
    assert _git(root, "rev-parse", "HEAD") == head_before
    assert f"created at current HEAD {head_before}" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("failure_mode", "expected_error"),
    [
        ("unstaged", "tracked worktree is not clean"),
        ("staged", "tracked worktree is not clean"),
        ("uncommitted-version", "not committed at current HEAD"),
        ("existing-tag", "already exists"),
        ("feature-branch", "must be created from main"),
        ("unmerged-main", "does not match origin/main"),
        ("dry-run-unmerged-main", "does not match origin/main"),
        ("git-error", "git command failed"),
    ],
)
def test_tag_readiness_failures_are_loud(
    tmp_path: Path,
    capsys,
    failure_mode: str,
    expected_error: str,
) -> None:
    root = _make_minimal_repo(tmp_path) if failure_mode == "git-error" else _make_git_repo(tmp_path)

    requested = "1.0.0"
    if failure_mode == "unstaged":
        (root / "pyproject.toml").write_text('version = "dirty"\n', encoding="utf-8")
    elif failure_mode == "staged":
        (root / "pyproject.toml").write_text('version = "dirty"\n', encoding="utf-8")
        _git(root, "add", "pyproject.toml")
    elif failure_mode == "uncommitted-version":
        requested = "1.1.0"
        (root / "src/devolaflow/__init__.py").write_text(
            '__version__ = "1.1.0"\n',
            encoding="utf-8",
        )
    elif failure_mode == "existing-tag":
        _git(root, "tag", "-a", "-m", "existing", "v1.0.0")
    elif failure_mode == "feature-branch":
        _git(root, "checkout", "-b", "release-test")
    elif failure_mode in {"unmerged-main", "dry-run-unmerged-main"}:
        (root / "pyproject.toml").write_text(
            'version = "1.0.0"\n# local-only commit\n',
            encoding="utf-8",
        )
        _git(root, "add", "pyproject.toml")
        _git(root, "commit", "-m", "local-only release commit")

    with pytest.raises(SystemExit) as excinfo:
        bump(
            requested,
            dry_run=failure_mode == "dry-run-unmerged-main",
            tag=True,
            root=root,
        )

    assert excinfo.value.code == 1
    assert expected_error in capsys.readouterr().err
