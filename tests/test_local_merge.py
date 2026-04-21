"""Tests for the local/merge module."""

from __future__ import annotations

from pathlib import Path

from devolaflow.local.merge import apply_merge, format_diff_for_review, propose_merge


def test_propose_merge_new_file(tmp_path: Path) -> None:
    path = tmp_path / "new.md"
    proposal = propose_merge(path, "hello\n")
    assert not proposal.exists
    assert proposal.action == "create"
    assert proposal.proposed_content == "hello\n"
    assert proposal.has_changes


def test_propose_merge_identical(tmp_path: Path) -> None:
    path = tmp_path / "existing.md"
    path.write_text("same\n")
    proposal = propose_merge(path, "same\n")
    assert proposal.exists
    assert proposal.action == "skip"
    assert not proposal.has_changes


def test_propose_merge_different(tmp_path: Path) -> None:
    path = tmp_path / "existing.md"
    path.write_text("old\n")
    proposal = propose_merge(path, "new\n")
    assert proposal.exists
    assert proposal.has_changes
    assert len(proposal.diff_lines) > 0
    assert proposal.action == "pending"


def test_apply_merge_creates(tmp_path: Path) -> None:
    path = tmp_path / "new.md"
    proposal = propose_merge(path, "content\n")
    result = apply_merge(proposal, action="merge")
    assert result is True
    assert path.read_text() == "content\n"


def test_apply_merge_skip(tmp_path: Path) -> None:
    path = tmp_path / "existing.md"
    path.write_text("original\n")
    proposal = propose_merge(path, "modified\n")
    result = apply_merge(proposal, action="skip")
    assert result is False
    assert path.read_text() == "original\n"


def test_format_diff_new_file(tmp_path: Path) -> None:
    path = tmp_path / "new.md"
    proposal = propose_merge(path, "hello\n")
    text = format_diff_for_review(proposal)
    assert "CREATE" in text


def test_format_diff_no_changes(tmp_path: Path) -> None:
    path = tmp_path / "same.md"
    path.write_text("x\n")
    proposal = propose_merge(path, "x\n")
    text = format_diff_for_review(proposal)
    assert "SKIP" in text


def test_format_diff_with_changes(tmp_path: Path) -> None:
    path = tmp_path / "mod.md"
    path.write_text("old\n")
    proposal = propose_merge(path, "new\n")
    text = format_diff_for_review(proposal)
    assert "MODIFY" in text
    assert "+new" in text or "-old" in text
