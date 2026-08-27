"""Scan known DevolaFlow skill install locations and report version status.

Backs ``devola-init-doctor --skills`` (full_review_and_improve Track B-2).
The location table mirrors the detection matrix of ``scripts/install.sh``
``do_update`` / ``do_uninstall`` — same tools, same paths, same
content-sniff guards for the single-file installs (copilot / windsurf)
that could otherwise false-positive on user-owned files.

Status semantics (per install):

* ``current``          — stamp first line equals the running package
  ``__version__``.
* ``stale``            — stamp holds a parseable semver that differs.
* ``unknown-version``  — stamp absent or holds the date-fallback written
  when the install-time version fetch failed; conservatively treated as
  needing an update (mirrors ``install.sh``'s ``is_up_to_date``).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

STAMP_FILENAME = ".devola-flow-version"

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_FRONTMATTER_VERSION_RE = re.compile(r"^version:\s*[\"']?(\d+\.\d+\.\d+)", re.MULTILINE)


@dataclass(frozen=True)
class SkillInstall:
    """One detected DevolaFlow skill install."""

    tool: str
    scope: str  # "project" | "global"
    path: Path  # the marker file / skill directory that identified the install
    installed_version: str | None
    status: str  # "current" | "stale" | "unknown-version"


def _stamp_first_line(stamp_dir: Path) -> str | None:
    stamp = stamp_dir / STAMP_FILENAME
    if not stamp.is_file():
        return None
    lines = stamp.read_text(encoding="utf-8").splitlines()
    first = lines[0].strip() if lines else ""
    return first or None


def _frontmatter_version(marker: Path) -> str | None:
    """Extract ``version:`` from a full-SKILL.md copy's YAML frontmatter."""
    try:
        head = marker.read_text(encoding="utf-8")[:2000]
    except OSError:
        return None
    m = _FRONTMATTER_VERSION_RE.search(head)
    return m.group(1) if m else None


def _status_for(installed: str | None, current: str) -> str:
    if installed is None or not _SEMVER_RE.match(installed):
        return "unknown-version"
    return "current" if installed == current else "stale"


def _mentions_devola(marker: Path, head_lines: int) -> bool:
    """Content-sniff guard for single-file installs that share user paths."""
    try:
        with marker.open(encoding="utf-8") as fh:
            for _ in range(head_lines):
                line = fh.readline()
                if not line:
                    break
                if "devola-flow" in line:
                    return True
    except OSError:
        return False
    return False


def scan_installed_skills(
    cwd: Path | None = None,
    home: Path | None = None,
    codex_home: Path | None = None,
    dsh_home: Path | None = None,
    current_version: str | None = None,
) -> list[SkillInstall]:
    """Return every detected DevolaFlow skill install with its version status.

    Only FOUND installs are returned — a missing location is not a finding.
    All parameters default to the real environment; tests inject temp dirs.
    """
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    codex_home = codex_home or Path(os.environ.get("CODEX_HOME", str(home / ".codex")))
    dsh_home = dsh_home or Path(os.environ.get("DSH_HOME", str(home / ".dsh")))
    if current_version is None:
        from devolaflow import __version__ as current_version

    found: list[SkillInstall] = []

    def add(tool: str, scope: str, path: Path, installed: str | None) -> None:
        found.append(
            SkillInstall(
                tool=tool,
                scope=scope,
                path=path,
                installed_version=installed,
                status=_status_for(installed, current_version),
            )
        )

    # kind: skill-dir — SKILL.md marker, stamp in the same directory.
    skill_dirs: list[tuple[str, str, Path]] = [
        ("cursor", "project", cwd / ".cursor" / "skills" / "devola-flow"),
        ("cursor", "global", home / ".cursor" / "skills" / "devola-flow"),
        ("claude", "project", cwd / ".claude" / "skills" / "devola-flow"),
        ("claude", "global", home / ".claude" / "skills" / "devola-flow"),
        ("codex", "global", codex_home / "skills" / "devola-flow"),
        ("kimicode", "project", cwd / ".kimi" / "skills" / "devola-flow"),
        ("kimicode", "global", home / ".kimi" / "skills" / "devola-flow"),
        ("dsh", "project", cwd / ".dsh" / "skills" / "devola-flow"),
        ("dsh", "global", dsh_home / "skills" / "devola-flow"),
    ]
    for tool, scope, skill_dir in skill_dirs:
        if (skill_dir / "SKILL.md").is_file():
            add(tool, scope, skill_dir, _stamp_first_line(skill_dir))

    # copilot — full SKILL.md copy (frontmatter intact, no stamp);
    # version derives from the frontmatter itself.
    copilot = cwd / ".github" / "copilot-instructions.md"
    if copilot.is_file() and _mentions_devola(copilot, head_lines=5):
        add("copilot", "project", copilot, _frontmatter_version(copilot))

    # windsurf — frontmatter-stripped rules file; stamp lands in cwd.
    windsurf = cwd / ".windsurfrules"
    if windsurf.is_file() and _mentions_devola(windsurf, head_lines=20):
        add("windsurf", "project", windsurf, _stamp_first_line(cwd))

    # kind: rule-tree — devola-flow.md marker, stamp in the same directory.
    rule_trees: list[tuple[str, str, Path]] = [
        ("zed", "project", cwd / ".rules"),
        ("zed", "global", home / ".config" / "zed" / "rules"),
        ("cline", "project", cwd / ".clinerules"),
        ("roo", "project", cwd / ".roo" / "rules"),
    ]
    for tool, scope, tree_dir in rule_trees:
        if (tree_dir / "devola-flow.md").is_file():
            add(tool, scope, tree_dir, _stamp_first_line(tree_dir))

    return found
