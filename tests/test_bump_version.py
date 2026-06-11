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

The fixtures build a minimal repo in tmp_path and pass it via the
``root=`` kwarg, so the real repository is never touched.
"""

from __future__ import annotations

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
