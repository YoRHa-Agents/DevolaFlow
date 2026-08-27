"""Tests for the new-module size and grandfather ratchet."""

from __future__ import annotations

from scripts.check_module_size import check_line_counts


def test_new_module_must_fit_ceiling() -> None:
    assert check_line_counts({"src/new.py": 801}, {}) == [
        "src/new.py: new module has 801 lines (limit 800)"
    ]


def test_existing_module_must_not_grow() -> None:
    assert check_line_counts({"src/old.py": 901}, {"src/old.py": 900}) == [
        "src/old.py: grew from 900 to 901 lines"
    ]


def test_unchanged_and_shrunk_modules_pass() -> None:
    assert (
        check_line_counts(
            {"src/same.py": 10, "src/smaller.py": 8},
            {"src/same.py": 10, "src/smaller.py": 900},
        )
        == []
    )
