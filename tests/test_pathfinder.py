"""Contract tests for Pathfinder natural-language activation."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.skills import classify_pathfind_intent, should_schedule_pathfind


@pytest.mark.parametrize(
    "message",
    [
        "Run Pathfinder before the next wave",
        "Please do a path finder scan",
        "Start a look-ahead harness reconnaissance",
        "Find the missing harness before implementation",
    ],
)
def test_requested_pathfinder_signals(message: str) -> None:
    assert classify_pathfind_intent(message) == "PATHFIND_REQUESTED"


@pytest.mark.parametrize(
    "message",
    [
        "Check for an infrastructure gap",
        "There may be a missing fixture",
        "What will block next?",
        "Review the capability gap ahead of the next gate",
    ],
)
def test_suggested_pathfinder_signals(message: str) -> None:
    assert classify_pathfind_intent(message) == "PATHFIND_SUGGESTED"


@pytest.mark.parametrize("message", ["", "   ", "Implement the endpoint", "Run the unit tests"])
def test_unrelated_messages_do_not_activate_pathfinder(message: str) -> None:
    assert classify_pathfind_intent(message) == "NO_PATHFIND"


def test_requested_signal_takes_precedence() -> None:
    assert classify_pathfind_intent("Pathfinder: check the infrastructure gap") == (
        "PATHFIND_REQUESTED"
    )


@pytest.mark.parametrize("flag_present", [False, True])
def test_harness_flag_controls_automatic_pathfinder_schedule(
    tmp_path: Path, flag_present: bool
) -> None:
    change_folder = tmp_path / "change"
    change_folder.mkdir()
    if flag_present:
        (change_folder / "harness_preflight.md").write_text("", encoding="utf-8")
    assert should_schedule_pathfind(change_folder) is flag_present


def test_automatic_pathfinder_schedule_rejects_missing_change_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        should_schedule_pathfind(tmp_path / "missing")
