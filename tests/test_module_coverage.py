"""Tests for the per-module coverage gate."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.check_module_coverage import find_violations, main


def _report(tmp_path: Path, percent: float) -> Path:
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "files": {
                    "src/example.py": {
                        "summary": {"num_statements": 10, "percent_covered": percent}
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_find_violations_ignores_empty_modules_and_sorts() -> None:
    data = {
        "files": {
            "b.py": {"summary": {"num_statements": 2, "percent_covered": 60}},
            "empty.py": {"summary": {"num_statements": 0, "percent_covered": 0}},
            "a.py": {"summary": {"num_statements": 3, "percent_covered": 69}},
        }
    }

    assert find_violations(data, 70) == [("a.py", 69.0), ("b.py", 60.0)]


def test_main_passes_for_report_above_floor(tmp_path: Path, capsys) -> None:
    assert main([str(_report(tmp_path, 70)), "--minimum", "70"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_for_report_below_floor(tmp_path: Path, capsys) -> None:
    assert main([str(_report(tmp_path, 69)), "--minimum", "70"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_fails_for_missing_report(tmp_path: Path, capsys) -> None:
    assert main([str(tmp_path / "missing.json")]) == 1
    assert "cannot read coverage report" in capsys.readouterr().err
