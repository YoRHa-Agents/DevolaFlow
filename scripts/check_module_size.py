#!/usr/bin/env python3
"""Enforce an 800-line ceiling for new Python source modules."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def check_line_counts(
    current: dict[str, int], baseline: dict[str, int], maximum: int = 800
) -> list[str]:
    """Return new-module and grandfather-ratchet violations."""
    violations = []
    for path, lines in sorted(current.items()):
        if path not in baseline and lines > maximum:
            violations.append(f"{path}: new module has {lines} lines (limit {maximum})")
        elif path in baseline and baseline[path] > maximum and lines > baseline[path]:
            violations.append(f"{path}: grew from {baseline[path]} to {lines} lines")
    return violations


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return result.stdout


def _changed_modules(root: Path, baseline_ref: str) -> list[Path]:
    changed = set(
        _git(root, "diff", "--name-only", baseline_ref, "--", "src/devolaflow").splitlines()
    )
    changed.update(
        _git(
            root, "ls-files", "--others", "--exclude-standard", "--", "src/devolaflow"
        ).splitlines()
    )
    return [
        root / path for path in sorted(changed) if path.endswith(".py") and (root / path).is_file()
    ]


def main(argv: list[str] | None = None) -> int:
    """Check changed source modules against the baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="origin/main")
    parser.add_argument("--maximum", type=int, default=800)
    args = parser.parse_args(argv)
    root = Path.cwd()

    try:
        modules = _changed_modules(root, args.baseline_ref)
        current = {
            str(path.relative_to(root)): len(path.read_text().splitlines()) for path in modules
        }
        baseline = {}
        for path in current:
            try:
                baseline_text = _git(root, "show", f"{args.baseline_ref}:{path}")
                baseline[path] = len(baseline_text.splitlines())
            except subprocess.CalledProcessError:
                continue
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: module-size baseline check failed: {exc}", file=sys.stderr)
        return 1

    violations = check_line_counts(current, baseline, args.maximum)
    if violations:
        print("FAIL: module-size gate")
        print("\n".join(f"  {violation}" for violation in violations))
        return 1
    print(f"PASS: module-size gate ({len(modules)} changed source module(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
