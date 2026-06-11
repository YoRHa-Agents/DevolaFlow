"""Tests for ``devolaflow.lifecycle.validate_surgical_scope`` (v14.4.0 T2).

Pins the BG-003 mechanical-verifier contract:

* ``collect_diff_stats`` — bounded ``git diff --numstat`` measurement;
  git failures RAISE (S-5), never silent-empty.
* ``check_module_scope`` — changed-filename set ⊆ owned_files, with the
  S-8 §2/§3 directory exemptions (change folder + handoff outbox).
* ``check_function_scope`` — ``git diff -U0`` hunks vs the
  forward-defined ``{path: [(start, end), ...]}`` line_ranges shape.
* ``evaluate_surgical_scope`` — tier auto-selection (ranges → function;
  manifest only → module; neither → stats_only).
* ``validate_surgical_scope`` / ``register_surgical_scope_hook`` —
  OPT-IN extra on ``task_stop``; the default chain stays byte-stable at
  ``(test_on_complete,)`` (default wiring is a v15.0.0 decision).

Fixture discipline: real ``git`` subprocesses against tmp_path repos
(per-repo user config; no global git state touched; 30s bound).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devolaflow.lifecycle import TASK_STOP_EVENT, clear_hooks, list_handlers
from devolaflow.lifecycle.test_on_complete import test_on_complete
from devolaflow.lifecycle.validate_surgical_scope import (
    SurgicalScopeError,
    check_function_scope,
    check_module_scope,
    collect_diff_stats,
    evaluate_surgical_scope,
    register_surgical_scope_hook,
    validate_surgical_scope,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """tmp git repo with a committed baseline: src/alpha.py + src/beta.py."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t2@devolaflow.test")
    _git(repo, "config", "user.name", "T2 Fixture")
    (repo / "src" / "alpha.py").write_text("a1\na2\na3\na4\na5\n")
    (repo / "src" / "beta.py").write_text("b1\nb2\nb3\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


# ---------------------------------------------------------------------------
# collect_diff_stats
# ---------------------------------------------------------------------------


def test_collect_diff_stats_counts_files_insertions_deletions(git_repo: Path) -> None:
    """numstat parse: per-file + total counts for edits and staged adds."""
    # Edit: replace a2 with two lines (+2/-1); add a new staged file (+1/-0).
    (git_repo / "src" / "alpha.py").write_text("a1\nx1\nx2\na3\na4\na5\n")
    (git_repo / "src" / "gamma.py").write_text("g1\n")
    _git(git_repo, "add", "src/gamma.py")

    stats = collect_diff_stats(git_repo)

    assert stats.base_ref == "HEAD"
    assert set(stats.changed_paths) == {"src/alpha.py", "src/gamma.py"}
    by_path = {f.path: f for f in stats.files}
    assert by_path["src/alpha.py"].insertions == 2
    assert by_path["src/alpha.py"].deletions == 1
    assert by_path["src/gamma.py"].insertions == 1
    assert stats.insertions == 3
    assert stats.deletions == 1


def test_collect_diff_stats_bad_ref_and_missing_repo_raise(git_repo: Path, tmp_path: Path) -> None:
    """S-5: git failures raise SurgicalScopeError — never silent-empty."""
    with pytest.raises(SurgicalScopeError, match="git exited"):
        collect_diff_stats(git_repo, base_ref="no-such-ref")
    with pytest.raises(SurgicalScopeError, match="not a directory"):
        collect_diff_stats(tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# check_module_scope
# ---------------------------------------------------------------------------


def test_module_scope_flags_out_of_manifest_file(git_repo: Path) -> None:
    (git_repo / "src" / "alpha.py").write_text("a1\nEDIT\na3\na4\na5\n")
    (git_repo / "src" / "beta.py").write_text("b1\nEDIT\nb3\n")
    stats = collect_diff_stats(git_repo)

    violations = check_module_scope(stats, ["src/alpha.py"])
    assert [v.code for v in violations] == ["SSV001"]
    assert violations[0].tier == "module"
    assert violations[0].path == "src/beta.py"

    # Full manifest → clean pass.
    assert check_module_scope(stats, ["src/alpha.py", "src/beta.py"]) == []


def test_module_scope_s8_exemptions_pass(git_repo: Path) -> None:
    """S-8 §2 (change folder) + §3 (handoff outbox) writes are exempt."""
    change_dir = git_repo / ".local" / ".agent" / "active" / "t2-scope"
    handoff_dir = git_repo / ".local" / ".agent" / "handoff"
    change_dir.mkdir(parents=True)
    handoff_dir.mkdir(parents=True)
    (change_dir / "STATUS.yaml").write_text("state: IN_PROGRESS\n")
    (handoff_dir / "L3__L2__t2-scope__1.yaml").write_text("kind: StatusReport\n")
    (git_repo / "src" / "alpha.py").write_text("a1\nEDIT\na3\na4\na5\n")
    _git(git_repo, "add", "-A")
    stats = collect_diff_stats(git_repo)

    violations = check_module_scope(
        stats,
        ["src/alpha.py"],
        change_folder=".local/.agent/active/t2-scope",
    )
    assert violations == []


# ---------------------------------------------------------------------------
# check_function_scope
# ---------------------------------------------------------------------------


def test_function_scope_flags_hunk_outside_declared_range(git_repo: Path) -> None:
    (git_repo / "src" / "alpha.py").write_text("a1\na2\na3\na4\nEDIT\n")

    violations = check_function_scope(git_repo, {"src/alpha.py": [(1, 2)]})
    assert [v.code for v in violations] == ["SSV002"]
    assert violations[0].tier == "function"
    assert violations[0].path == "src/alpha.py"
    assert "5-5" in violations[0].message


def test_function_scope_in_range_pass(git_repo: Path) -> None:
    (git_repo / "src" / "alpha.py").write_text("a1\nEDIT\na3\na4\na5\n")

    assert check_function_scope(git_repo, {"src/alpha.py": [(1, 3)]}) == []


# ---------------------------------------------------------------------------
# evaluate_surgical_scope — tier auto-selection + composition
# ---------------------------------------------------------------------------


def test_evaluate_tier_auto_selection(git_repo: Path) -> None:
    """ranges → function; manifest only → module; neither → stats_only."""
    (git_repo / "src" / "alpha.py").write_text("a1\nEDIT\na3\na4\na5\n")

    by_ranges = evaluate_surgical_scope(git_repo, line_ranges={"src/alpha.py": [(1, 3)]})
    assert by_ranges["tier_checked"] == "function"
    assert by_ranges["violations"] == []

    by_manifest = evaluate_surgical_scope(git_repo, owned_files=["src/alpha.py"])
    assert by_manifest["tier_checked"] == "module"
    assert by_manifest["violations"] == []

    stats_only = evaluate_surgical_scope(git_repo)
    assert stats_only["tier_checked"] == "stats_only"
    assert stats_only["violations"] == []
    assert stats_only["diff_stats"].changed_paths == ("src/alpha.py",)


def test_evaluate_function_tier_includes_module_containment(git_repo: Path) -> None:
    """Function tier is module-bounded: undeclared changed files → SSV001."""
    (git_repo / "src" / "alpha.py").write_text("a1\nEDIT\na3\na4\na5\n")
    (git_repo / "src" / "beta.py").write_text("b1\nEDIT\nb3\n")

    verdict = evaluate_surgical_scope(
        git_repo,
        owned_files=["src/alpha.py"],
        line_ranges={"src/alpha.py": [(1, 3)]},
    )
    assert verdict["tier_checked"] == "function"
    assert [(v.code, v.path) for v in verdict["violations"]] == [("SSV001", "src/beta.py")]


# ---------------------------------------------------------------------------
# Hook surface — opt-in registration, default chain byte-stable
# ---------------------------------------------------------------------------


def test_hook_opt_in_registration_default_chain_unchanged() -> None:
    """AC-2: default task_stop chain is (test_on_complete,); opt-in appends."""
    clear_hooks(TASK_STOP_EVENT)
    try:
        # Importing the module / package must NOT have registered anything.
        assert list_handlers(TASK_STOP_EVENT) == (test_on_complete,)

        register_surgical_scope_hook()
        assert list_handlers(TASK_STOP_EVENT) == (
            test_on_complete,
            validate_surgical_scope,
        )
    finally:
        clear_hooks(TASK_STOP_EVENT)
    assert list_handlers(TASK_STOP_EVENT) == (test_on_complete,)


def test_hook_payload_gates_and_violation_paths(git_repo: Path) -> None:
    """No block → clean no-op; breach → blocker; malformed block → SSV003."""
    # Gate: existing StatusReport payloads (no surgical_scope block) pass.
    clean = validate_surgical_scope({"task_id": "T-1", "metrics": {}})
    assert clean.passed is True
    assert "no surgical_scope block" in clean.metadata["reason"]

    # Out-of-manifest diff → blocker SSV001 (BG-003 severity).
    (git_repo / "src" / "beta.py").write_text("b1\nEDIT\nb3\n")
    breach = validate_surgical_scope(
        {
            "surgical_scope": {
                "repo_root": str(git_repo),
                "owned_files": ["src/alpha.py"],
            }
        }
    )
    assert breach.passed is False
    assert breach.violations[0].code == "SSV001"
    assert breach.violations[0].severity == "blocker"

    # Malformed block → explicit SSV003 error state (S-5).
    malformed = validate_surgical_scope({"surgical_scope": 42})
    assert malformed.passed is False
    assert malformed.violations[0].code == "SSV003"
    assert malformed.violations[0].severity == "error"
