"""Tests for devolaflow.local.workspace module."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.local.workspace import (
    ON_DEMAND_DIRS,
    REQUIRED_DIRS,
    generate_index,
    scaffold_local,
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
