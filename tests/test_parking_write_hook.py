"""v24.0.0 — the tool-owned-surface write hook and its zero-cost off path."""

from __future__ import annotations

import pytest

from devolaflow.lifecycle import list_handlers, register_hook, run_hooks
from devolaflow.lifecycle.check_parking_write import check_parking_write
from devolaflow.lifecycle.dispatcher import HookViolation

FILE_WRITE_EVENT = "file_write"


@pytest.fixture
def hook_registered():
    """Re-register if a sibling module's ``clear_hooks()`` stripped extras.

    This mirrors the v12.2.0 wiring-fixture convention: the hook is
    default-wired at import time, but ``clear_hooks()`` removes all extras
    process-wide, so a wiring assertion has to be order-independent.
    """

    if check_parking_write not in list_handlers(FILE_WRITE_EVENT):
        register_hook(FILE_WRITE_EVENT, check_parking_write)
    yield


@pytest.mark.parametrize(
    "path",
    [
        "src/devolaflow/cli.py",
        ".local/tasks/demo/goal.md",
        ".local/tasks/demo/evidence/run.txt",
        ".local/.agent/active/demo/checklist.md",
        "docs/parking-lot-notes.md",
    ],
)
def test_unrelated_paths_are_a_clean_no_op(path):
    result = check_parking_write({"path": path, "owned_files": [path]})
    assert result.passed
    assert result.violations == []


@pytest.mark.parametrize(
    "path",
    [
        ".local/tasks/demo/parking/judgments.yaml",
        ".local/tasks/demo/parking/events.yaml",
        ".local/tasks/demo/parking/INDEX.md",
        ".local/tasks/demo/parking/judge.md",
        ".local/tasks/demo/parking/risks/RISK-001.md",
        ".local/.agent/active/demo/compact/mappings.yaml",
        ".local/.agent/active/demo/compact/DIGEST.md",
        ".local/.agent/active/demo/compact/archived/0001/x.md",
    ],
)
def test_hand_writes_to_tool_owned_surfaces_are_rejected(path):
    result = check_parking_write({"path": path})
    assert not result.passed
    assert [item.code for item in result.violations] == ["CPW001"]
    assert result.violations[0].severity == "blocker"


@pytest.mark.parametrize("tool", ["devola-parking", "devola-compact"])
def test_tool_writes_pass(tool):
    result = check_parking_write({"path": ".local/tasks/d/parking/judgments.yaml", "tool": tool})
    assert result.passed


def test_strict_mode_raises(tmp_path):
    with pytest.raises(HookViolation):
        check_parking_write({"path": ".local/tasks/d/parking/judge.md"}, strict=True)


def test_hook_is_wired_onto_the_file_write_event(hook_registered):
    assert check_parking_write in list_handlers(FILE_WRITE_EVENT)


def test_malformed_payloads_do_not_crash():
    assert check_parking_write({}).passed
    assert check_parking_write({"path": 7}).passed


def test_run_hooks_stays_permissive_for_an_unrelated_write():
    result = run_hooks("file_write", {"path": "src/x.py", "owned_files": ["src/x.py"]})
    assert result.passed
