#!/usr/bin/env python3
"""Bump DevolaFlow version across all files that contain version references.

Usage:
    python scripts/bump_version.py 0.3.0
    python scripts/bump_version.py 0.3.0 --dry-run
    python scripts/bump_version.py 0.3.0 --tag          # bump + create git tag
    python scripts/bump_version.py 0.3.0 --tag --dry-run

Single source of truth: src/devolaflow/__init__.py (__version__).
This script synchronizes all other locations to match.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

VERSION_LOCATIONS = [
    {
        "path": "src/devolaflow/__init__.py",
        "pattern": r'__version__\s*=\s*"[^"]+"',
        "replacement": '__version__ = "{version}"',
    },
    {
        "path": "pyproject.toml",
        "pattern": r'^version\s*=\s*"[^"]+"',
        "replacement": 'version = "{version}"',
    },
    {
        "path": "workflow-system/agent/SKILL.md",
        "pattern": r'^version:\s*"[^"]+"',
        "replacement": 'version: "{version}"',
    },
    {
        "path": "workflow-system/agent/SKILL.md",
        "pattern": r"> \*\*Now Using DevolaFlow v[^*]+\*\*",
        "replacement": "> **Now Using DevolaFlow v{version}**",
    },
    {
        "path": "workflow-system/agent/MVP-SKILL.md",
        "pattern": r'^version:\s*"[^"]+"',
        "replacement": 'version: "{version}"',
    },
    {
        "path": "workflow-system/agent/MVP-SKILL.md",
        "pattern": r"> \*\*Now Using DevolaFlow v[^*]+\*\*",
        "replacement": "> **Now Using DevolaFlow v{version}**",
    },
    {
        "path": "workflow-system/agent/workflow-skill.yaml",
        "pattern": r'version:\s*"[^"]+"',
        "replacement": 'version: "{version}"',
    },
    {
        "path": "scripts/generate_human_docs.py",
        "pattern": r'SOURCE_VERSION\s*=\s*"[^"]+"',
        "replacement": 'SOURCE_VERSION = "{version}"',
    },
    {
        "path": "tests/test_smoke.py",
        "pattern": r'assert devolaflow\.__version__\s*==\s*"[^"]+"',
        "replacement": 'assert devolaflow.__version__ == "{version}"',
    },
]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[\w.]+)?$")


def _find_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def _get_current_version(root: Path) -> str:
    init = root / "src" / "devolaflow" / "__init__.py"
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text())
    if not match:
        raise RuntimeError(f"Cannot read version from {init}")
    return match.group(1)


def bump(new_version: str, *, dry_run: bool = False, tag: bool = False) -> list[str]:
    root = _find_root()
    current = _get_current_version(root)
    updated: list[str] = []

    print(f"Bumping version: {current} -> {new_version}")
    if dry_run:
        print("(dry run — no files will be modified)\n")

    for loc in VERSION_LOCATIONS:
        fpath = root / loc["path"]
        if not fpath.exists():
            print(f"  SKIP  {loc['path']} (not found)")
            continue

        text = fpath.read_text()
        pattern = re.compile(loc["pattern"], re.MULTILINE)
        replacement = loc["replacement"].format(version=new_version)

        new_text, count = pattern.subn(replacement, text, count=1)
        if count > 0:
            if not dry_run:
                fpath.write_text(new_text)
            status = "OK" if not dry_run else "WOULD"
            print(f"  {status:6s} {loc['path']}")
            updated.append(loc["path"])
        else:
            print(f"  SKIP  {loc['path']} (pattern not found)")

    print(f"\n{len(updated)} locations {'would be ' if dry_run else ''}updated.")

    if tag:
        tag_name = f"v{new_version}"
        if dry_run:
            print(f"\n  WOULD  create git tag: {tag_name}")
        else:
            try:
                subprocess.run(
                    ["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
                    cwd=str(root),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print(f"\n  TAG    {tag_name} created")
                print(f"  Push with: git push origin {tag_name}")
            except subprocess.CalledProcessError as e:
                print(f"\n  FAIL   git tag: {e.stderr.strip()}")

    return updated


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry_run = "--dry-run" in sys.argv
    create_tag = "--tag" in sys.argv

    if not args:
        root = _find_root()
        current = _get_current_version(root)
        print(f"Current version: {current}")
        print(f"\nUsage: {sys.argv[0]} <new-version> [--dry-run] [--tag]")
        print(f"Example: {sys.argv[0]} 0.3.0")
        print(f"         {sys.argv[0]} 0.3.0 --tag  # also create git tag")
        sys.exit(0)

    new_version = args[0]
    if not SEMVER_RE.match(new_version):
        print(f"Error: '{new_version}' is not a valid semver (expected X.Y.Z)")
        sys.exit(1)

    bump(new_version, dry_run=dry_run, tag=create_tag)


if __name__ == "__main__":
    main()
