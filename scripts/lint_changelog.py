#!/usr/bin/env python3
"""CHANGELOG.md single-application CI lint (D-5 / G-036).

Telegraphed since the v11.1.0 retrospective (docs/cycle-archive/v11.1.0/
retrospective.md §3 D-5), re-telegraphed in the v12.5.0 retrospective §6
item 12, and slotted at v14.5.0 by the v14.2.0 gap analysis §2.7 G-036.
Supersedes/complements the in-test partial mitigation from v11.1.1
(``tests/test_changelog_no_duplicate_versions.py`` — duplicate-header
check only): this script adds the structural ordering checks and the
per-commit IMMUTABILITY diff walk that the in-test lint cannot perform.

Rule set
========

R1 — structure
    Every ``## [<token>]`` header must be well-formed: ``[X.Y.Z]`` or
    ``[X.Y.Z-<prerelease>]`` (or ``[Unreleased]``, which must be the
    first block), followed by an ISO ``YYYY-MM-DD`` date. Three
    historical separator eras are accepted between token and date:
    ``" - "`` (Keep-a-Changelog), ``" — "`` (em dash, v10.x era), and
    ``", "`` (v9.1.x and older). Versions must be strictly descending
    top-down (compared on the numeric ``X.Y.Z`` core; a prerelease
    sorts below the release of the same core), dates must be
    non-increasing top-down, and no version token may appear twice.

R2 — single-application / immutability
    Given ``--base-ref`` (default ``origin/main``), every version block
    that exists at the base ref must exist in the working-tree
    CHANGELOG byte-identically (modification or deletion of a
    previously-released block FAILS). Additions are allowed ONLY above
    the newest base-ref block (the new release entry) or in an
    ``[Unreleased]`` section. Entries are applied exactly once.

R3 — version match (laxer "release-in-flight" rule, documented here)
    The top released block's version must EITHER equal
    ``src/devolaflow/__init__.py::__version__`` OR be exactly one
    release step newer (``X.Y.Z+1``, ``X.Y+1.0``, or ``X+1.0.0``).
    The laxer rule is chosen deliberately: the repo's PV-close ordering
    routinely authors the ``## [X.Y.Z]`` CHANGELOG block in the same PR
    BEFORE ``scripts/bump_version.py`` runs, so a strict equality rule
    would fail every release-in-flight commit between the two steps.

Exit codes: 0 = clean, 1 = violations (or unresolvable base ref without
``--allow-missing-base``). Every finding is printed with a line number;
skips are explicit, never silent (S-5).

Stdlib-only by design (CI runs it before project install completes).
"""

from __future__ import annotations

import argparse
import datetime
import itertools
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_REF = "origin/main"
UNRELEASED_TOKEN = "unreleased"
VERSION_FILE = Path("src") / "devolaflow" / "__init__.py"

HEADER_RE = re.compile(r"^## \[(?P<token>[^\]]+)\](?P<rest>.*)$")
VERSION_TOKEN_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<pre>[0-9A-Za-z][0-9A-Za-z.\-]*))?$"
)
DATE_REST_RE = re.compile(r"^\s*[-\u2014,]\s*(?P<date>\d{4}-\d{2}-\d{2})(?:\b|$)")
VERSION_DECL_RE = re.compile(r'^__version__\s*=\s*"(?P<version>[^"]+)"', re.MULTILINE)


class BaseRefError(RuntimeError):
    """Raised when the base-ref CHANGELOG content cannot be read via git."""


@dataclass
class LintIssue:
    """One lint finding. ``line`` is 1-indexed into the HEAD changelog."""

    code: str
    message: str
    line: int | None = None

    def render(self, filename: str) -> str:
        location = filename if self.line is None else f"{filename}:{self.line}"
        return f"{location}: [{self.code}] {self.message}"


@dataclass
class Block:
    """One ``## [...]`` version block (header line through the line before the next header)."""

    token: str
    start_line: int
    text: str
    core: tuple[int, int, int] | None = None
    prerelease: str | None = None
    date: datetime.date | None = None

    @property
    def is_unreleased(self) -> bool:
        return self.token.lower() == UNRELEASED_TOKEN

    @property
    def key(self) -> str:
        return self.token.lower()


def parse_blocks(text: str) -> tuple[list[Block], list[LintIssue]]:
    """Split changelog text into version blocks; collect R1 header-shape issues.

    Malformed blocks are still returned (with ``core=None``) so the
    immutability walk can track them by token; ordering checks skip them.
    """
    lines = text.splitlines()
    header_rows = [(i, m) for i, m in ((i, HEADER_RE.match(ln)) for i, ln in enumerate(lines)) if m]
    blocks: list[Block] = []
    issues: list[LintIssue] = []
    for pos, (i, match) in enumerate(header_rows):
        end = header_rows[pos + 1][0] if pos + 1 < len(header_rows) else len(lines)
        block = Block(
            token=match.group("token").strip(),
            start_line=i + 1,
            text="\n".join(lines[i:end]),
        )
        blocks.append(block)
        if block.is_unreleased:
            continue
        version_match = VERSION_TOKEN_RE.match(block.token)
        if version_match is None:
            issues.append(
                LintIssue(
                    "R1",
                    f"malformed version token '[{block.token}]' — expected '[X.Y.Z]', "
                    "'[X.Y.Z-<prerelease>]', or '[Unreleased]'",
                    block.start_line,
                )
            )
            continue
        block.core = (
            int(version_match.group("major")),
            int(version_match.group("minor")),
            int(version_match.group("patch")),
        )
        block.prerelease = version_match.group("pre")
        date_match = DATE_REST_RE.match(match.group("rest"))
        if date_match is None:
            issues.append(
                LintIssue(
                    "R1",
                    f"block '[{block.token}]' is missing a parseable "
                    "' - YYYY-MM-DD' release date after the version token",
                    block.start_line,
                )
            )
            continue
        try:
            block.date = datetime.date.fromisoformat(date_match.group("date"))
        except ValueError:
            issues.append(
                LintIssue(
                    "R1",
                    f"block '[{block.token}]' has an invalid calendar date "
                    f"'{date_match.group('date')}'",
                    block.start_line,
                )
            )
    return blocks, issues


def _order_key(block: Block) -> tuple[tuple[int, int, int], int]:
    """Descending-order comparison key: numeric core, release > prerelease of the same core."""
    assert block.core is not None
    return (block.core, 0 if block.prerelease else 1)


def check_structure(blocks: list[Block]) -> list[LintIssue]:
    """R1: Unreleased placement, duplicate tokens, version descent, date non-increase."""
    issues: list[LintIssue] = []
    for index, block in enumerate(blocks):
        if block.is_unreleased and index != 0:
            issues.append(
                LintIssue(
                    "R1",
                    "'[Unreleased]' block must be the first block in the changelog",
                    block.start_line,
                )
            )
    first_seen: dict[str, int] = {}
    for block in blocks:
        if block.key in first_seen:
            issues.append(
                LintIssue(
                    "R1",
                    f"duplicate version block '[{block.token}]' — first seen at line "
                    f"{first_seen[block.key]}; every version entry must be applied exactly once",
                    block.start_line,
                )
            )
        else:
            first_seen[block.key] = block.start_line
    released = [b for b in blocks if b.core is not None]
    for upper, lower in itertools.pairwise(released):
        if _order_key(upper) <= _order_key(lower):
            issues.append(
                LintIssue(
                    "R1",
                    f"version order violation: '[{lower.token}]' must be strictly older than "
                    f"'[{upper.token}]' above it (new blocks are appended at the top)",
                    lower.start_line,
                )
            )
        if upper.date is not None and lower.date is not None and lower.date > upper.date:
            issues.append(
                LintIssue(
                    "R1",
                    f"date order violation: '[{lower.token}]' ({lower.date}) is dated after "
                    f"'[{upper.token}]' ({upper.date}) above it; dates must be "
                    "non-increasing top-down",
                    lower.start_line,
                )
            )
    return issues


def check_version_match(blocks: list[Block], declared_version: str) -> list[LintIssue]:
    """R3: top released block equals ``__version__`` or is one release step newer."""
    released = [b for b in blocks if b.core is not None]
    if not released:
        return [LintIssue("R3", "no well-formed released version block found in the changelog")]
    declared_match = VERSION_TOKEN_RE.match(declared_version.strip())
    if declared_match is None:
        return [
            LintIssue(
                "R3",
                f"declared __version__ '{declared_version}' is not of the form X.Y.Z[-prerelease]",
            )
        ]
    major = int(declared_match.group("major"))
    minor = int(declared_match.group("minor"))
    patch = int(declared_match.group("patch"))
    allowed_cores = {
        (major, minor, patch),  # released state: top block == __version__
        (major, minor, patch + 1),  # release-in-flight: patch bump
        (major, minor + 1, 0),  # release-in-flight: minor bump
        (major + 1, 0, 0),  # release-in-flight: major bump
    }
    top = released[0]
    if top.core not in allowed_cores:
        return [
            LintIssue(
                "R3",
                f"top block '[{top.token}]' must equal __version__ ({declared_version}) or be "
                "exactly one release step newer (X.Y.Z+1 / X.Y+1.0 / X+1.0.0 — the documented "
                "release-in-flight rule)",
                top.start_line,
            )
        ]
    return []


def _first_divergent_line_offset(base_block_text: str, head_block_text: str) -> int:
    """0-based offset (from the block header) of the first differing line."""
    base_lines = base_block_text.splitlines()
    head_lines = head_block_text.splitlines()
    for offset, (base_line, head_line) in enumerate(zip(base_lines, head_lines, strict=False)):
        if base_line != head_line:
            return offset
    return min(len(base_lines), len(head_lines))


def check_immutability(base_text: str, head_text: str) -> list[LintIssue]:
    """R2: previously-released blocks are byte-immutable; additions go above them only."""
    base_blocks, _ = parse_blocks(base_text)
    head_blocks, _ = parse_blocks(head_text)
    issues: list[LintIssue] = []
    base_released = [b for b in base_blocks if not b.is_unreleased]
    if not base_released:
        return issues
    head_pos: dict[str, int] = {}
    for index, block in enumerate(head_blocks):
        head_pos.setdefault(block.key, index)
    for base_block in base_released:
        if base_block.key not in head_pos:
            issues.append(
                LintIssue(
                    "R2",
                    f"released block '[{base_block.token}]' (base line {base_block.start_line}) "
                    "was deleted; previously-released version blocks are immutable",
                )
            )
            continue
        head_block = head_blocks[head_pos[base_block.key]]
        if head_block.text != base_block.text:
            offset = _first_divergent_line_offset(base_block.text, head_block.text)
            issues.append(
                LintIssue(
                    "R2",
                    f"released block '[{base_block.token}]' was modified relative to the base "
                    "ref; previously-released version blocks are immutable (first divergence "
                    "at this line)",
                    head_block.start_line + offset,
                )
            )
    surviving = [b for b in base_released if b.key in head_pos]
    for previous, current in itertools.pairwise(surviving):
        if head_pos[current.key] < head_pos[previous.key]:
            issues.append(
                LintIssue(
                    "R2",
                    f"released blocks '[{previous.token}]' and '[{current.token}]' were "
                    "reordered relative to the base ref",
                    head_blocks[head_pos[current.key]].start_line,
                )
            )
    if not surviving:
        return issues
    anchor_index = min(head_pos[b.key] for b in surviving)
    anchor_token = head_blocks[anchor_index].token
    base_keys = {b.key for b in base_blocks}
    for index, head_block in enumerate(head_blocks):
        if head_block.key in base_keys:
            continue
        if index > anchor_index:
            issues.append(
                LintIssue(
                    "R2",
                    f"new block '[{head_block.token}]' was inserted below the newest released "
                    f"base-ref block '[{anchor_token}]'; new entries may only be appended above "
                    "it (or live in an '[Unreleased]' section)",
                    head_block.start_line,
                )
            )
    return issues


def read_base_changelog(repo_root: Path, base_ref: str, rel_path: str) -> str:
    """Return the changelog content at ``base_ref`` via ``git show``; raise BaseRefError."""
    cmd = ["git", "-C", str(repo_root), "show", f"{base_ref}:{rel_path}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BaseRefError(f"git invocation failed: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git show exited {result.returncode}"
        raise BaseRefError(detail)
    return result.stdout


def read_declared_version(repo_root: Path) -> str | None:
    """Parse ``__version__`` out of ``src/devolaflow/__init__.py``; None when unreadable."""
    version_path = repo_root / VERSION_FILE
    if not version_path.is_file():
        return None
    match = VERSION_DECL_RE.search(version_path.read_text(encoding="utf-8"))
    return match.group("version") if match else None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-ref",
        default=DEFAULT_BASE_REF,
        help=f"git ref to diff the changelog against for R2 (default: {DEFAULT_BASE_REF})",
    )
    parser.add_argument(
        "--changelog",
        default=None,
        help="path to the changelog file (default: <repo-root>/CHANGELOG.md)",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="repository root for git + version-file lookup (default: this script's repo)",
    )
    parser.add_argument(
        "--allow-missing-base",
        action="store_true",
        help="degrade to a structure-only run (explicit NOTICE, exit 0 if R1+R3 pass) "
        "when --base-ref cannot be resolved; without this flag that is a failure",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    changelog = Path(args.changelog).resolve() if args.changelog else repo_root / "CHANGELOG.md"
    try:
        rel_path = changelog.relative_to(repo_root).as_posix()
    except ValueError:
        rel_path = changelog.name
    if not changelog.is_file():
        print(f"{rel_path}: [R1] changelog file not found at {changelog}", file=sys.stderr)
        return 1

    head_text = changelog.read_text(encoding="utf-8")
    blocks, issues = parse_blocks(head_text)
    issues.extend(check_structure(blocks))

    declared_version = read_declared_version(repo_root)
    if declared_version is None:
        issues.append(LintIssue("R3", f"cannot read __version__ from {VERSION_FILE.as_posix()}"))
    else:
        issues.extend(check_version_match(blocks, declared_version))

    immutability_ran = False
    try:
        base_text = read_base_changelog(repo_root, args.base_ref, rel_path)
    except BaseRefError as exc:
        if args.allow_missing_base:
            print(
                f"NOTICE: base ref '{args.base_ref}' unavailable ({exc}); "
                "skipping the R2 immutability check (structure-only run).",
                file=sys.stderr,
            )
        else:
            issues.append(
                LintIssue(
                    "R2",
                    f"cannot resolve base ref '{args.base_ref}': {exc} "
                    "(pass --allow-missing-base to degrade to structure-only)",
                )
            )
    else:
        immutability_ran = True
        issues.extend(check_immutability(base_text, head_text))

    if issues:
        for issue in issues:
            print(issue.render(rel_path), file=sys.stderr)
        print(f"lint_changelog: FAIL — {len(issues)} issue(s).", file=sys.stderr)
        return 1
    checks = "R1 structure + R3 version-match"
    if immutability_ran:
        checks += f" + R2 immutability (base: {args.base_ref})"
    print(f"lint_changelog: OK — {len(blocks)} version blocks; {checks} clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
