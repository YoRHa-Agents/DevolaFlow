"""Tests for devolaflow.local.workspace module."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.local.workspace import (
    MEMORY_SUBDIRS,
    ON_DEMAND_DIRS,
    REQUIRED_DIRS,
    SCAFFOLD_GITIGNORE_ENTRIES,
    ScaffoldVerificationError,
    ensure_gitignore_entries,
    generate_dir_readme,
    generate_index,
    generate_memory_index,
    generate_tracker,
    scaffold_local,
    verify_scaffold_gitignore,
)


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary directory acting as a repo root."""
    return tmp_path


class TestScaffoldLocal:
    def test_creates_required_directories(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo)
        assert local_dir == tmp_repo / ".local"
        for d in REQUIRED_DIRS:
            assert (local_dir / d).is_dir()

    def test_creates_on_demand_directories(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo, dirs=["research", "logs"])
        assert (local_dir / "research").is_dir()
        assert (local_dir / "logs").is_dir()

    def test_ignores_unknown_dirs(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo, dirs=["unknown_dir"])
        assert not (local_dir / "unknown_dir").exists()

    def test_idempotency(self, tmp_repo: Path) -> None:
        local_dir1 = scaffold_local(tmp_repo, dirs=["research"])
        marker = local_dir1 / "research" / "marker.txt"
        marker.write_text("keep")

        local_dir2 = scaffold_local(tmp_repo, dirs=["research"])
        assert local_dir2 == local_dir1
        assert marker.read_text() == "keep"

    def test_generates_index_md(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo)
        index = local_dir / "index.md"
        assert index.exists()
        content = index.read_text()
        assert "# .local/ workspace index" in content

    def test_on_demand_dirs_constant(self) -> None:
        assert "research" in ON_DEMAND_DIRS
        assert "design" in ON_DEMAND_DIRS
        assert "benchmarks" in ON_DEMAND_DIRS
        assert "logs" in ON_DEMAND_DIRS
        assert "scratch" in ON_DEMAND_DIRS

    def test_no_dirs_param(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo)
        for d in ON_DEMAND_DIRS:
            assert not (local_dir / d).exists()


class TestGenerateIndex:
    def test_produces_valid_markdown(self, tmp_repo: Path) -> None:
        local_dir = tmp_repo / ".local"
        local_dir.mkdir()
        (local_dir / "feedbacks").mkdir()
        (local_dir / "tasks").mkdir()

        index_path = generate_index(local_dir)
        assert index_path.exists()
        content = index_path.read_text()
        assert "- `feedbacks/`" in content
        assert "- `tasks/`" in content

    def test_empty_directory(self, tmp_repo: Path) -> None:
        local_dir = tmp_repo / ".local"
        local_dir.mkdir()

        index_path = generate_index(local_dir)
        content = index_path.read_text()
        assert "# .local/ workspace index" in content

    def test_index_updates_on_rerun(self, tmp_repo: Path) -> None:
        local_dir = tmp_repo / ".local"
        local_dir.mkdir()

        generate_index(local_dir)
        (local_dir / "new_dir").mkdir()
        index_path = generate_index(local_dir)

        content = index_path.read_text()
        assert "- `new_dir/`" in content


# ── v8.2.3: .local/.agent/ scaffold + G-1/G-2 repair ────────────────────
#
# Test cases enforcing the v8.2.3 patch contract per
# .local/research/v8.3.0_design.md §1.1 and v8.3.0_patch_plan.md §v8.2.3.
# These extend (not replace) the pre-v8.2.3 cases above.


class TestAgentWorkspaceScaffold:
    """v8.2.3 — A1 .agent/* substrate creation (additive to REQUIRED_DIRS)."""

    def test_scaffold_creates_agent_active_dir(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo)
        d = local_dir / ".agent" / "active"
        assert d.is_dir(), f"Expected directory: {d}"
        assert (d / "README.md").is_file(), "Expected README.md placeholder"

    def test_scaffold_creates_agent_handoff_dir(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo)
        d = local_dir / ".agent" / "handoff"
        assert d.is_dir(), f"Expected directory: {d}"
        assert (d / "README.md").is_file()

    def test_scaffold_creates_agent_archive_dir(self, tmp_repo: Path) -> None:
        local_dir = scaffold_local(tmp_repo)
        d = local_dir / ".agent" / "archive"
        assert d.is_dir(), f"Expected directory: {d}"
        assert (d / "README.md").is_file()

    def test_scaffold_creates_memory_specs_dir(self, tmp_repo: Path) -> None:
        """memory/specs/ is the source-of-truth contract location per Rule A-4."""
        local_dir = scaffold_local(tmp_repo)
        d = local_dir / "memory" / "specs"
        assert d.is_dir(), f"Expected directory: {d}"
        assert (d / "README.md").is_file()

    def test_required_dirs_count_is_12(self) -> None:
        """REQUIRED_DIRS: 3 (pre-v8.2.3) -> 6 (v8.2.3) -> 12 (v14.0.0 human surface)."""
        assert len(REQUIRED_DIRS) == 12
        assert REQUIRED_DIRS[:3] == ["feedbacks", "tasks", "memory"], (
            "Existing 3 entries MUST stay byte-identical (I-PV03-A)"
        )
        assert ".agent/active" in REQUIRED_DIRS
        assert ".agent/handoff" in REQUIRED_DIRS
        assert ".agent/archive" in REQUIRED_DIRS
        # v14.0.0 — `.local/human/` surface dirs (INPUT tracked; OUTPUT/archive private).
        for human_dir in (
            "human",
            "human/input",
            "human/input/amendments",
            "human/output",
            "human/output/convergence",
            "human/archive",
        ):
            assert human_dir in REQUIRED_DIRS, f"missing v14.0.0 human dir {human_dir!r}"

    def test_memory_subdirs_constant(self) -> None:
        """MEMORY_SUBDIRS captures memory/specs (M-004 source-of-truth)."""
        assert "memory/specs" in MEMORY_SUBDIRS

    def test_agent_dirs_have_descriptive_readmes(self, tmp_repo: Path) -> None:
        """README placeholders explain each .agent/* dir's purpose."""
        local_dir = scaffold_local(tmp_repo)
        active_readme = (local_dir / ".agent/active/README.md").read_text(encoding="utf-8")
        assert "in-flight" in active_readme.lower() or "change-driven" in active_readme.lower()
        handoff_readme = (local_dir / ".agent/handoff/README.md").read_text(encoding="utf-8")
        assert "append-only" in handoff_readme.lower()
        assert "S-9" in handoff_readme
        archive_readme = (local_dir / ".agent/archive/README.md").read_text(encoding="utf-8")
        assert "completed" in archive_readme.lower() or "frozen" in archive_readme.lower()

    def test_memory_specs_readme_mentions_a4(self, tmp_repo: Path) -> None:
        """memory/specs/ README must cite Rule A-4 (source-of-truth contract)."""
        local_dir = scaffold_local(tmp_repo)
        readme = (local_dir / "memory/specs/README.md").read_text(encoding="utf-8")
        assert "A-4" in readme or "source-of-truth" in readme.lower()


class TestScaffoldIdempotency:
    """v8.2.3 — strict idempotency for repeat scaffold_local() calls."""

    def test_scaffold_idempotent_2nd_run_no_op(self, tmp_repo: Path) -> None:
        """2nd scaffold_local() call MUST NOT mutate any existing file content."""
        local_dir1 = scaffold_local(tmp_repo)

        # Snapshot ALL file contents (recursive) AND mtimes
        snapshot: dict[Path, tuple[bytes, float]] = {}
        for p in sorted(local_dir1.rglob("*")):
            if p.is_file():
                snapshot[p] = (p.read_bytes(), p.stat().st_mtime)

        local_dir2 = scaffold_local(tmp_repo)

        assert local_dir2 == local_dir1

        # Content MUST be byte-identical
        for p, (expected_bytes, expected_mtime) in snapshot.items():
            assert p.is_file(), f"File disappeared on 2nd run: {p}"
            assert p.read_bytes() == expected_bytes, f"File content changed on 2nd run: {p}"
            # generate_index() short-circuits when content matches → mtime stable
            assert p.stat().st_mtime == expected_mtime, (
                f"File mtime changed on 2nd run (idempotency violation): {p}"
            )

    def test_scaffold_repairs_missing_tracker_md(self, tmp_repo: Path) -> None:
        """G-2 repair: scaffold_local() writes TRACKER.md unconditionally on every call."""
        local_dir = tmp_repo / ".local"
        (local_dir / "feedbacks").mkdir(parents=True)

        # Simulate older repo with feedbacks/ but no TRACKER.md
        tracker = local_dir / "feedbacks" / "TRACKER.md"
        assert not tracker.exists(), "Sanity: precondition for G-2 scenario"

        scaffold_local(tmp_repo)

        assert tracker.is_file(), "scaffold_local() MUST repair G-2 by writing TRACKER.md"
        content = tracker.read_text(encoding="utf-8")
        assert "# Feedback Tracker" in content

    def test_scaffold_repairs_missing_memory_md(self, tmp_repo: Path) -> None:
        """G-2 repair: scaffold_local() writes MEMORY.md unconditionally on every call."""
        local_dir = tmp_repo / ".local"
        (local_dir / "memory").mkdir(parents=True)

        memory_md = local_dir / "memory" / "MEMORY.md"
        assert not memory_md.exists(), "Sanity: precondition for G-2 scenario"

        scaffold_local(tmp_repo)

        assert memory_md.is_file(), "scaffold_local() MUST repair G-2 by writing MEMORY.md"
        content = memory_md.read_text(encoding="utf-8")
        assert "# Memory Index" in content

    def test_scaffold_does_not_overwrite_existing_tracker(self, tmp_repo: Path) -> None:
        """If TRACKER.md exists with user content, idempotency MUST preserve it."""
        local_dir = tmp_repo / ".local"
        feedbacks = local_dir / "feedbacks"
        feedbacks.mkdir(parents=True)
        custom = "# Custom Tracker\n\nUser-edited content; do not overwrite.\n"
        (feedbacks / "TRACKER.md").write_text(custom, encoding="utf-8")

        scaffold_local(tmp_repo)

        assert (feedbacks / "TRACKER.md").read_text(encoding="utf-8") == custom


class TestIndexAndG1Repair:
    """v8.2.3 — index.md drift repair (closes G-1)."""

    def test_index_md_lists_all_subdirs_after_scaffold(self, tmp_repo: Path) -> None:
        """index.md MUST list every actual top-level subdir of .local/."""
        local_dir = scaffold_local(tmp_repo)
        content = (local_dir / "index.md").read_text(encoding="utf-8")

        actual_subdirs = sorted(p.name for p in local_dir.iterdir() if p.is_dir())
        for name in actual_subdirs:
            assert f"- `{name}/`" in content, (
                f"index.md missing entry for actual subdir '{name}/' (G-1 drift detection)"
            )

        # The 8-path manifest implies these 4 top-level entries:
        assert "- `feedbacks/`" in content
        assert "- `tasks/`" in content
        assert "- `memory/`" in content
        assert "- `.agent/`" in content

    def test_index_md_repaired_when_drifted(self, tmp_repo: Path) -> None:
        """G-1 repair: a stale index.md is regenerated to match actual subdirs."""
        local_dir = tmp_repo / ".local"
        local_dir.mkdir()
        # Plant a deliberately-out-of-date index.md (the v8.3.0 G-1 scenario).
        stale = "# .local/ workspace index\n\nAuto-generated directory listing.\n\n- `oldonly/`\n"
        (local_dir / "index.md").write_text(stale, encoding="utf-8")

        scaffold_local(tmp_repo)

        content = (local_dir / "index.md").read_text(encoding="utf-8")
        assert "- `oldonly/`" not in content, "Stale entry must be replaced"
        assert "- `feedbacks/`" in content
        assert "- `.agent/`" in content


class TestGenerateHelpers:
    """Direct unit tests for the generate_* helpers (improve coverage)."""

    def test_generate_tracker_skips_when_file_exists(self, tmp_repo: Path) -> None:
        feedbacks = tmp_repo / "feedbacks"
        feedbacks.mkdir()
        custom = "user content"
        (feedbacks / "TRACKER.md").write_text(custom, encoding="utf-8")

        out = generate_tracker(feedbacks)

        assert out == feedbacks / "TRACKER.md"
        assert out.read_text(encoding="utf-8") == custom

    def test_generate_memory_index_skips_when_file_exists(self, tmp_repo: Path) -> None:
        memory = tmp_repo / "memory"
        memory.mkdir()
        custom = "user content"
        (memory / "MEMORY.md").write_text(custom, encoding="utf-8")

        out = generate_memory_index(memory)

        assert out == memory / "MEMORY.md"
        assert out.read_text(encoding="utf-8") == custom

    def test_generate_dir_readme_unknown_name_writes_nothing(self, tmp_repo: Path) -> None:
        """Unknown dir_name → no README written (silent skip per existing contract)."""
        d = tmp_repo / "unknown"
        d.mkdir()

        out = generate_dir_readme(d, "unknown_kind_with_no_template")

        assert out == d / "README.md"
        assert not out.exists()


class TestEnsureGitignoreEntries:
    """full_review_and_improve Track C-1 — deterministic gitignore entries.

    R5 F1-H1: `.codegraph/` historically depended on the prompt-side
    `add_to_gitignore` template semantic and was lost whenever `codegraph
    init` failed. These tests pin the code-path replacement.
    """

    def test_creates_file_when_absent(self, tmp_repo: Path) -> None:
        added = ensure_gitignore_entries(tmp_repo, (".codegraph/",))

        assert added == [".codegraph/"]
        text = (tmp_repo / ".gitignore").read_text(encoding="utf-8")
        assert ".codegraph/" in text.splitlines()

    def test_appends_missing_and_preserves_user_content(self, tmp_repo: Path) -> None:
        gi = tmp_repo / ".gitignore"
        user_content = "# my rules\nnode_modules/\n*.pyc\n"
        gi.write_text(user_content, encoding="utf-8")

        added = ensure_gitignore_entries(tmp_repo, (".codegraph/", "dist/"))

        assert added == [".codegraph/", "dist/"]
        text = gi.read_text(encoding="utf-8")
        assert text.startswith(user_content.rstrip("\n") + "\n") or "# my rules" in text
        lines = text.splitlines()
        assert "node_modules/" in lines
        assert "*.pyc" in lines
        assert ".codegraph/" in lines
        assert "dist/" in lines

    def test_idempotent_across_three_runs(self, tmp_repo: Path) -> None:
        ensure_gitignore_entries(tmp_repo, SCAFFOLD_GITIGNORE_ENTRIES)
        after_first = (tmp_repo / ".gitignore").read_text(encoding="utf-8")

        for _ in range(2):
            added = ensure_gitignore_entries(tmp_repo, SCAFFOLD_GITIGNORE_ENTRIES)
            assert added == []

        after_third = (tmp_repo / ".gitignore").read_text(encoding="utf-8")
        assert after_third == after_first
        assert after_third.splitlines().count(".codegraph/") == 1


class TestScaffoldGitignoreSelfCheck:
    """Track C-1 — scaffold writes .codegraph/ deterministically + verifies."""

    def test_scaffold_writes_codegraph_entry_without_codegraph_cli(self, tmp_repo: Path) -> None:
        # No codegraph CLI exists in the test environment — the entry must
        # land anyway (decoupled from `codegraph init` outcome; R5 F1-H1).
        scaffold_local(tmp_repo)

        rules = (tmp_repo / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert ".codegraph/" in rules
        assert verify_scaffold_gitignore(tmp_repo) == []

    def test_verify_reports_missing_rules(self, tmp_repo: Path) -> None:
        missing = verify_scaffold_gitignore(tmp_repo)

        assert ".codegraph/" in missing
        assert ".local/*" in missing

    def test_scaffold_raises_when_gitignore_unwritable(self, tmp_repo: Path) -> None:
        # A directory named `.gitignore` defeats both read and write paths;
        # the scaffold must fail LOUDLY (S-5) instead of reporting success.
        (tmp_repo / ".gitignore").mkdir()

        with pytest.raises(ScaffoldVerificationError) as excinfo:
            scaffold_local(tmp_repo)

        assert ".codegraph/" in excinfo.value.missing_rules
        # verify=False restores the old advisory-only behaviour.
        local_dir = scaffold_local(tmp_repo, verify=False)
        assert local_dir.is_dir()

    def test_python_dash_m_module_scaffolds(self, tmp_repo: Path) -> None:
        # R5 F1-H2: `python3 -m devolaflow.local.workspace` was a silent
        # no-op import (no __main__ path) that install.sh reported as
        # success. Pin the healed behaviour end-to-end via subprocess.
        import os
        import subprocess
        import sys

        repo_root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")

        result = subprocess.run(
            [sys.executable, "-m", "devolaflow.local.workspace"],
            cwd=tmp_repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, result.stderr
        assert (tmp_repo / ".local").is_dir()
        assert ".codegraph/" in (tmp_repo / ".gitignore").read_text(encoding="utf-8")
