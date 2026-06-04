"""Tests for ``lint_human`` — the ``.local/human/`` surface budget lint.

v14.0.0 Wave-2 (design §4c). ``lint_human`` is a sibling entry point to
``lint_change`` (which is change-folder-only and deliberately NOT overloaded);
it walks the ``.local/human/`` INPUT + OUTPUT zones and enforces the NEW C-9
TOKEN budgets via the shared :func:`estimate_tokens` heuristic (finding F-4:
TOKENS are the sole enforced unit — the line/word figures in the design are
authoring guidance only). The dated ``archive/`` zone and any unbudgeted file
(e.g. ``README.md``) are intentionally skipped, never flagged.

These tests pin the §4c contract: the canonical budget rows, the
under-soft / over-soft / over-hard severities, the PER-FILE shard cap on
``input/requirements/<domain>.md``, the opt-in empty-report behaviour when the
surface is not scaffolded, and the ``--human`` CLI flag. They reuse the public
:class:`BudgetReport` / :class:`BudgetViolation` / :func:`estimate_tokens`
machinery so no second measurement axis is introduced.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.agent_workspace import (
    HUMAN_ARTIFACT_BUDGETS,
    BudgetReport,
    estimate_tokens,
    lint_human,
)
from devolaflow.agent_workspace.lint import main as lint_main


def _scaffold_human(repo_root: Path, files: dict[str, str]) -> Path:
    """Write ``files`` (relative to ``.local/human/``) under ``repo_root``.

    Returns the ``.local/human`` base directory. Parent directories are
    created as needed so callers can place INPUT-zone shards / OUTPUT-zone
    convergence reports / amendment ledger files in one call.
    """
    base = repo_root / ".local" / "human"
    for rel, content in files.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    return base


# A char count whose ``len // 4`` token estimate lands in a known band, given
# a per-file (soft, hard) budget. Keeps the size arithmetic explicit per test.
def _chars_for_tokens(tokens: int) -> str:
    return "x" * (tokens * 4)


class TestHumanBudgetTable:
    """The §4c budget map carries every canonical artifact row, verbatim."""

    def test_canonical_rows_present(self):
        for key in (
            "input/constitution.md",
            "input/requirements.md",
            "input/requirements/<domain>.md",
            "input/amendments/<date>-<slug>.md",
            "output/DIGEST.md",
            "output/convergence/<version>-convergence.md",
        ):
            assert key in HUMAN_ARTIFACT_BUDGETS, f"missing budget row {key!r}"

    def test_canonical_values_match_design(self):
        assert HUMAN_ARTIFACT_BUDGETS["input/constitution.md"] == (800, 1500)
        assert HUMAN_ARTIFACT_BUDGETS["input/requirements.md"] == (1200, 2500)
        assert HUMAN_ARTIFACT_BUDGETS["input/requirements/<domain>.md"] == (1200, 2500)
        assert HUMAN_ARTIFACT_BUDGETS["input/amendments/<date>-<slug>.md"] == (400, 800)
        assert HUMAN_ARTIFACT_BUDGETS["output/DIGEST.md"] == (600, 1000)
        assert HUMAN_ARTIFACT_BUDGETS["output/convergence/<version>-convergence.md"] == (700, 1000)


class TestLintHumanSeverities:
    """under-soft → OK · over-soft → WARN · over-hard → FAIL (token-only)."""

    def test_under_soft_is_clean(self, tmp_path: Path):
        _scaffold_human(
            tmp_path,
            {
                "input/constitution.md": "# Constitution\nterse principles\n",
                "input/requirements.md": "# Requirements\nshort\n",
                "output/DIGEST.md": "# Digest\nshort\n",
                "output/convergence/v14.1.0-convergence.md": "# Conv\nshort\n",
            },
        )
        report = lint_human(repo_root=tmp_path)
        assert isinstance(report, BudgetReport)
        assert report.exit_code == 0
        assert report.violations == []
        # Every budgeted file is recorded as checked (diagnostic coverage).
        assert "input/constitution.md" in report.checked_files
        assert "output/DIGEST.md" in report.checked_files

    def test_over_soft_warns_but_zero_exit(self, tmp_path: Path):
        # DIGEST soft=600, hard=1000 ⇒ 700 tokens is WARN (over soft, under hard).
        _scaffold_human(tmp_path, {"output/DIGEST.md": _chars_for_tokens(700)})
        report = lint_human(repo_root=tmp_path)
        assert report.exit_code == 0
        assert report.hard_failures == []
        warn = report.soft_warnings
        assert len(warn) == 1
        assert warn[0].filename == "output/DIGEST.md"
        assert warn[0].severity == "WARN"
        assert estimate_tokens(_chars_for_tokens(700)) == 700

    def test_over_hard_fails(self, tmp_path: Path):
        # convergence soft=700, hard=1000 ⇒ 1100 tokens is FAIL (over hard).
        rel = "output/convergence/v14.1.0-convergence.md"
        _scaffold_human(tmp_path, {rel: _chars_for_tokens(1100)})
        report = lint_human(repo_root=tmp_path)
        assert report.exit_code == 1
        assert len(report.hard_failures) == 1
        assert report.hard_failures[0].filename == rel
        assert report.hard_failures[0].severity == "FAIL"


class TestLintHumanShardCap:
    """The ``input/requirements/<domain>.md`` shard cap applies PER FILE."""

    def test_one_oversized_shard_fails_sibling_ok(self, tmp_path: Path):
        # shard hard=2500 ⇒ 2600 tokens fails; the small sibling shard passes.
        _scaffold_human(
            tmp_path,
            {
                "input/requirements/input.md": _chars_for_tokens(2600),
                "input/requirements/separation.md": "# Sep\nshort\n",
            },
        )
        report = lint_human(repo_root=tmp_path)
        assert report.exit_code == 1
        assert any(
            v.filename == "input/requirements/input.md" and v.severity == "FAIL"
            for v in report.violations
        )
        # The under-budget sibling shard contributes NO violation (per-file cap).
        assert all(v.filename != "input/requirements/separation.md" for v in report.violations)
        assert "input/requirements/separation.md" in report.checked_files

    def test_amendment_ledger_file_capped_per_file(self, tmp_path: Path):
        # amendments soft=400, hard=800 ⇒ 900 tokens fails per-file.
        rel = "input/amendments/2026-06-03-add-req.md"
        _scaffold_human(tmp_path, {rel: _chars_for_tokens(900)})
        report = lint_human(repo_root=tmp_path)
        assert report.exit_code == 1
        assert any(v.filename == rel and v.severity == "FAIL" for v in report.violations)


class TestLintHumanScope:
    """Only budgeted INPUT/OUTPUT files are linted; archive + README skipped."""

    def test_unbudgeted_and_archive_files_skipped(self, tmp_path: Path):
        _scaffold_human(
            tmp_path,
            {
                # README has no C-9 row — must be skipped, never flagged.
                "README.md": "z" * 100_000,
                "output/README.md": "z" * 100_000,
                # archive/ holds frozen snapshots — excluded even if huge.
                "archive/2026-06-03-old/requirements.md": "z" * 100_000,
                "output/DIGEST.md": "# Digest\nshort\n",
            },
        )
        report = lint_human(repo_root=tmp_path)
        assert report.exit_code == 0
        assert report.violations == []
        assert "README.md" not in report.checked_files
        assert "output/README.md" not in report.checked_files
        assert all("archive/" not in f for f in report.checked_files)
        assert "output/DIGEST.md" in report.checked_files

    def test_missing_human_dir_is_opt_in_empty(self, tmp_path: Path):
        # No .local/human/ scaffolded at all — opt-in surface, NOT an error.
        report = lint_human(repo_root=tmp_path)
        assert isinstance(report, BudgetReport)
        assert report.exit_code == 0
        assert report.checked_files == []
        assert report.violations == []

    def test_human_root_override(self, tmp_path: Path):
        # The explicit human_root override walks an arbitrary directory.
        custom = tmp_path / "elsewhere" / "human"
        (custom / "output").mkdir(parents=True)
        (custom / "output" / "DIGEST.md").write_text("# D\nshort\n", encoding="utf-8")
        report = lint_human(repo_root=tmp_path, human_root=custom)
        assert report.exit_code == 0
        assert "output/DIGEST.md" in report.checked_files


class TestLintHumanCli:
    """The ``python -m devolaflow.agent_workspace.lint --human`` CLI path."""

    def test_cli_human_clean_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _scaffold_human(tmp_path, {"output/DIGEST.md": "short\n"})
        monkeypatch.chdir(tmp_path)
        assert lint_main(["--human"]) == 0

    def test_cli_human_hard_violation_returns_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _scaffold_human(
            tmp_path,
            {"output/convergence/v14.1.0-convergence.md": _chars_for_tokens(1100)},
        )
        monkeypatch.chdir(tmp_path)
        assert lint_main(["--human"]) == 1

    def test_cli_human_respects_repo_root_flag(self, tmp_path: Path):
        _scaffold_human(tmp_path, {"output/DIGEST.md": "short\n"})
        assert lint_main(["--human", "--repo-root", str(tmp_path)]) == 0
