#!/usr/bin/env python3
"""Sync .cursor/skills/devola-flow/ to the canonical workflow-system/agent/ skill.

This is the repo-local project-skill mirror that Cursor picks up when the user
opens the DevolaFlow repo itself. It mirrors EXACTLY the 12 files that
scripts/install.sh::install_cursor downloads (SKILL.md + 8 references + 3
examples), plus a single-line .devola-flow-version stamp equal to
src/devolaflow/__init__.py __version__.

Run manually:
    python scripts/sync_cursor_skill.py           # sync in place
    python scripts/sync_cursor_skill.py --check   # exit 1 if mirror is stale

scripts/bump_version.py invokes this at the end of every version bump so the
mirror cannot drift.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# Set must match scripts/install.sh::install_cursor (SKILL + 8 refs + 3 examples).
# Edit BOTH files in lockstep if you ever change what Cursor users receive.
CANONICAL_DIR = Path("workflow-system/agent")
MIRROR_DIR = Path(".cursor/skills/devola-flow")
MIRRORED_FILES = [
    "SKILL.md",
    "references/agent-hierarchy.md",
    "references/meta-framework.md",
    "references/decomposition-gate.md",
    "references/repo-modes.md",
    "references/execution-protocol.md",
    "references/message-schemas.md",
    "references/team-roles.md",
    "references/context-isolation.md",
    "examples/full-pipeline-trace.md",
    "examples/hotfix-trace.md",
    "examples/convergence-loop-trace.md",
]
STAMP_FILE = MIRROR_DIR / ".devola-flow-version"
VERSION_FILE = Path("src/devolaflow/__init__.py")
VERSION_PATTERN = re.compile(r'__version__\s*=\s*"([^"]+)"')


def read_canonical_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    m = VERSION_PATTERN.search(text)
    if not m:
        raise SystemExit(f"{VERSION_FILE}: __version__ not found")
    return m.group(1)


def iter_pairs() -> list[tuple[Path, Path]]:
    return [(CANONICAL_DIR / rel, MIRROR_DIR / rel) for rel in MIRRORED_FILES]


def check() -> int:
    """Exit 1 if any mirrored file differs or the stamp is wrong; else 0."""
    version = read_canonical_version()
    problems: list[str] = []
    for src, dst in iter_pairs():
        if not src.is_file():
            problems.append(f"MISSING CANONICAL: {src}")
            continue
        if not dst.is_file():
            problems.append(f"MISSING MIRROR:    {dst}")
            continue
        if src.read_bytes() != dst.read_bytes():
            problems.append(f"OUT OF SYNC:       {dst} differs from {src}")
    if not STAMP_FILE.is_file():
        problems.append(f"MISSING STAMP:     {STAMP_FILE}")
    else:
        stamp_lines = STAMP_FILE.read_text(encoding="utf-8").splitlines()
        first = stamp_lines[0] if stamp_lines else ""
        if first != version:
            problems.append(
                f"STAMP MISMATCH:    {STAMP_FILE} first-line={first!r} vs __version__={version!r}"
            )
    if problems:
        print(
            "[.cursor mirror] out of sync — run: python scripts/sync_cursor_skill.py",
            file=sys.stderr,
        )
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"[.cursor mirror] ok (12 files, stamp {version})")
    return 0


def sync() -> int:
    version = read_canonical_version()
    changed = 0
    for src, dst in iter_pairs():
        if not src.is_file():
            raise SystemExit(f"canonical missing: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file() or src.read_bytes() != dst.read_bytes():
            shutil.copyfile(src, dst)
            changed += 1
            print(f"  sync  {dst}")
    stamp_body = f"{version}\n"
    if (
        not STAMP_FILE.is_file()
        or STAMP_FILE.read_text(encoding="utf-8") != stamp_body
    ):
        STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        STAMP_FILE.write_text(stamp_body, encoding="utf-8")
        print(f"  stamp {STAMP_FILE} -> {version}")
        changed += 1
    if changed == 0:
        print(f"[.cursor mirror] already in sync (12 files, stamp {version})")
    else:
        print(f"[.cursor mirror] synced {changed} file(s) to v{version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if mirror is stale (no writes)",
    )
    args = ap.parse_args(argv)
    if args.check:
        return check()
    return sync()


if __name__ == "__main__":
    raise SystemExit(main())
