#!/usr/bin/env python3
"""Sync .cursor/skills/devola-flow/ to the canonical workflow-system/agent/ skill.

This is the repo-local project-skill mirror that Cursor picks up when the user
opens the DevolaFlow repo itself. It mirrors EXACTLY what the `cursor` install
profile of the install manifest (workflow-system/agent/manifest.yaml — the A-5
single source of truth shared with scripts/install.sh and devola-init)
declares, plus a single-line .devola-flow-version stamp equal to
src/devolaflow/__init__.py __version__.

The mirror is **opt-in** (gitignored as of chore/cursor-skill-mirror-untrack).
Default sync and --check are no-ops when the mirror directory is absent so
fresh clones, CI runners, and bump_version.py all pass without it. To opt in,
run --init once; subsequent default-sync runs will keep the mirror fresh.

Run manually:
    python scripts/sync_cursor_skill.py           # sync if mirror present; no-op otherwise
    python scripts/sync_cursor_skill.py --init    # bytewise-create the mirror (opt-in)
    python scripts/sync_cursor_skill.py --check   # exit 1 only on present-and-stale; 0 if absent

scripts/bump_version.py invokes this at the end of every version bump; when
the mirror is absent the hook prints a "skipped" line and exits 0.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

CANONICAL_DIR = Path("workflow-system/agent")
MIRROR_DIR = Path(".cursor/skills/devola-flow")
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_mirrored_files() -> list[str]:
    """Derive the mirror set from the install-manifest SSOT (`cursor` profile).

    workflow-system/agent/manifest.yaml is the single owner (Rule A-5) of
    the per-tool install file lists, shared with scripts/install.sh and
    devola-init. Pre-manifest this module carried its own hardcoded list
    that had to be edited in lockstep with install.sh — the G1 drift this
    derivation retires. Growth history for the set lives in the manifest /
    CHANGELOG; new references land via scripts/scaffold_reference.py.
    """
    import yaml

    manifest_path = _REPO_ROOT / CANONICAL_DIR / "manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    profile = data["install_profiles"]["cursor"]
    files: list[str] = []
    for set_name in profile["sets"]:
        files.extend(data[set_name])
    return files


MIRRORED_FILES = _load_mirrored_files()
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
    """Exit 1 if any mirrored file differs or the stamp is wrong; else 0.

    Returns 0 (no-op) when MIRROR_DIR is absent — the mirror is opt-in and
    CI / fresh clones must pass without it.
    """
    if not MIRROR_DIR.exists():
        print(f"[.cursor mirror] not present at {MIRROR_DIR} — opt-in (see Rule SF-3)")
        return 0
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
    print(f"[.cursor mirror] ok ({len(MIRRORED_FILES)} files, stamp {version})")
    return 0


def sync(*, allow_init: bool = False) -> int:
    """Sync the mirror in place.

    When MIRROR_DIR is absent and ``allow_init`` is False, exits 0 with an
    info line — does NOT create the mirror out of nothing. Only --init
    (allow_init=True) materialises the mirror from canonical, so accidental
    `bump_version.py` / `make all` runs cannot resurrect it for users who
    deliberately opted out.
    """
    if not MIRROR_DIR.exists() and not allow_init:
        print(f"[.cursor mirror] not present at {MIRROR_DIR} — opt-in via `--init` (see Rule SF-3)")
        return 0
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
    if not STAMP_FILE.is_file() or STAMP_FILE.read_text(encoding="utf-8") != stamp_body:
        STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        STAMP_FILE.write_text(stamp_body, encoding="utf-8")
        print(f"  stamp {STAMP_FILE} -> {version}")
        changed += 1
    if changed == 0:
        print(f"[.cursor mirror] already in sync ({len(MIRRORED_FILES)} files, stamp {version})")
    else:
        print(f"[.cursor mirror] synced {changed} file(s) to v{version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 only if mirror is present-and-stale (no writes); exit 0 if absent",
    )
    ap.add_argument(
        "--init",
        action="store_true",
        help="create the mirror from canonical (opt-in to project-local skill)",
    )
    args = ap.parse_args(argv)
    if args.check:
        return check()
    return sync(allow_init=args.init)


if __name__ == "__main__":
    raise SystemExit(main())
