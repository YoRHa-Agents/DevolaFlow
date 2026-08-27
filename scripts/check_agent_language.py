#!/usr/bin/env python3
"""Hard-fail CJK lint for agent-facing prompt surfaces."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
DEFAULT_TARGETS = (
    "AGENTS.md",
    ".rules",
    "workflow-system/agent",
    "src/devolaflow/task_adaptive_selector.py",
)
Q6_EXEMPT_PREFIXES = ("workflow-system/human/zh/", "docs/cycle-archive/")


def find_cjk(root: Path, targets: tuple[str, ...] = DEFAULT_TARGETS) -> list[str]:
    """Return relative locations containing CJK characters."""
    findings = []
    for target in targets:
        path = root / target
        paths = [path] if path.is_file() else sorted(path.rglob("*"))
        for file_path in paths:
            if not file_path.is_file() or any(
                file_path.relative_to(root).as_posix().startswith(prefix)
                for prefix in Q6_EXEMPT_PREFIXES
            ):
                continue
            for line_number, line in enumerate(
                file_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if CJK_RE.search(line):
                    findings.append(f"{file_path.relative_to(root)}:{line_number}")
    return findings


def main(argv: list[str] | None = None) -> int:
    """Run the agent-facing language lint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    findings = find_cjk(args.root)
    if findings:
        print("FAIL: CJK characters found in agent-facing files")
        print("\n".join(f"  {finding}" for finding in findings))
        return 1
    print("PASS: agent-facing files are English-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
