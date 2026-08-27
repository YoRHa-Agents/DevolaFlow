#!/usr/bin/env python3
"""Fail when any measured source module falls below the coverage floor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def find_violations(data: dict[str, Any], minimum: float) -> list[tuple[str, float]]:
    """Return measured files with executable statements below *minimum*."""
    violations = []
    for filename, details in data.get("files", {}).items():
        summary = details.get("summary", {})
        statements = summary.get("num_statements", 0)
        percent = float(summary.get("percent_covered", 100.0))
        if statements and percent < minimum:
            violations.append((filename, percent))
    return sorted(violations)


def main(argv: list[str] | None = None) -> int:
    """Validate a coverage.py JSON report and return a process status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="coverage.py JSON report")
    parser.add_argument("--minimum", type=float, default=70.0)
    args = parser.parse_args(argv)

    try:
        data = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read coverage report {args.report}: {exc}", file=sys.stderr)
        return 1

    violations = find_violations(data, args.minimum)
    if violations:
        print(f"FAIL: {len(violations)} module(s) below {args.minimum:.1f}% coverage")
        for filename, percent in violations:
            print(f"  {filename}: {percent:.1f}%")
        return 1

    measured = sum(
        1
        for details in data.get("files", {}).values()
        if details.get("summary", {}).get("num_statements", 0)
    )
    print(f"PASS: {measured} measured modules meet {args.minimum:.1f}% coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
