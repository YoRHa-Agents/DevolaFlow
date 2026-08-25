#!/usr/bin/env python3
"""Realign ``context_profiles.yaml`` section-anchor line ranges against SKILL.md.

v12.4.0 PV-02 — closes the v12.3.0 retrospective §4.3 learning. The
``workflow-system/agent/context_profiles.yaml`` ``sections:`` block records
``lines: "X-Y"`` ranges for each SKILL.md section so the runtime's legacy
line-based ``_resolve_section_text`` path can slice the right content. Every
PV that restructures SKILL.md (e.g. inserting / collapsing a subsection)
shifts these line ranges and the YAML must be re-anchored, otherwise the
fallback path either returns truncated text (silent S-5 violation if the
DeprecationWarning is filtered) or pulls in adjacent sections' content (the
v12.3.0 retro §4.3 captured ~15 min/cycle of manual edits to absorb this).

This script automates the realignment:

1. Parse SKILL.md to extract every ``^##|^###`` header with its line number.
2. Parse ``context_profiles.yaml``'s ``sections:`` block to list each anchor's
   current ``lines: "X-Y"`` range.
3. For each anchor whose current START line is a SKILL.md header, recompute
   the range as ``start_header_line .. (next_header_line - 1)``. Anchors
   whose START line is content (operator-defined sub-ranges like
   ``wave_task_constraints: "193-197"``) are LEFT ALONE — the script
   never overwrites a hand-crafted sub-range.
4. Anchors whose ``lines: "N/A"`` value (external or retired compatibility
   sections) or whose START is line 1 (frontmatter — pre-first-header) are
   also left untouched.
5. Idempotent: running the script twice on the same SKILL.md produces no
   change on the second run.

CLI usage::

    python scripts/realign_section_anchors.py --dry-run   # print proposed changes
    python scripts/realign_section_anchors.py --apply     # write changes to YAML

The script intentionally avoids ``ruamel.yaml`` to stay dependency-light;
``ruff format`` + ``pyyaml`` (already a project dependency) cover the
round-trip needs because we only mutate ``lines: "X-Y"`` LITERALS — we
never re-emit the YAML tree wholesale (which would churn comments).

S-2 — all paths in this module are relative to the repo root.
S-5 — missing input files raise ``FileNotFoundError`` (no silent fallback).
W-20 — no new env flag introduced.

Source: ``.local/research/v12.3.0_retrospective.md`` §4.3 +
``.local/research/v12.4.0_gap_analysis.md`` §2 D-1 (item 2).
Repository: https://github.com/YoRHa-Agents/DevolaFlow

"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_MD: Path = REPO_ROOT / "workflow-system" / "agent" / "SKILL.md"
DEFAULT_PROFILES_YAML: Path = REPO_ROOT / "workflow-system" / "agent" / "context_profiles.yaml"

# Match a SKILL.md heading line. Captures the leading ``##`` / ``###`` so the
# caller can read the heading depth; we don't currently use the depth for
# realignment (next-header-at-any-depth is the boundary), but keeping it makes
# the script easier to extend.
_HEADER_RE = re.compile(r"^(?P<hashes>#{2,3})\s+(?P<title>.+?)\s*$")

# Match an anchor block in the ``sections:`` YAML block. Anchored keys live at
# 2-space indent under the ``sections:`` top-level key; ``lines:`` values sit
# at 4-space indent immediately under the key.
#
# We use multiline regex so the script can locate-and-rewrite a SPECIFIC
# anchor's ``lines: "..."`` line without disturbing surrounding comments /
# whitespace / sibling anchors.
_SECTIONS_BLOCK_RE = re.compile(
    r"^sections:\s*$\n"
    r"(?P<body>(?:.|\n)*?)"
    r"^(?:[A-Za-z_][A-Za-z0-9_]*:|# Context profiles per task type)",
    re.MULTILINE,
)
_ANCHOR_LINES_RE = re.compile(
    r"^  (?P<anchor>[A-Za-z_][A-Za-z0-9_]*):\s*\n"
    r"    lines:\s*\"(?P<lines>[^\"]+)\"\s*\n",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Header:
    """A SKILL.md heading."""

    line: int
    depth: int
    title: str


@dataclass(frozen=True)
class AnchorChange:
    """A proposed realignment for one anchor."""

    anchor: str
    old_range: str
    new_range: str

    @property
    def changed(self) -> bool:
        return self.old_range != self.new_range


def parse_skill_md_headers(skill_md_path: Path) -> list[Header]:
    """Return every ``##``/``###`` header in SKILL.md as ``(line, depth, title)``.

    Lines are 1-indexed to match the convention used in
    ``context_profiles.yaml`` (``lines: "X-Y"`` is 1-indexed inclusive).
    """
    if not skill_md_path.is_file():
        # S-5 — surface missing input loudly. Caller decides whether to
        # recover; we don't fabricate an empty header list.
        raise FileNotFoundError(
            f"SKILL.md not found at {skill_md_path}. Pass --skill-md if the file lives elsewhere."
        )
    headers: list[Header] = []
    with skill_md_path.open("r", encoding="utf-8") as f:
        for idx, raw in enumerate(f, start=1):
            match = _HEADER_RE.match(raw.rstrip("\n"))
            if match is None:
                continue
            depth = len(match.group("hashes"))
            title = match.group("title").strip()
            headers.append(Header(line=idx, depth=depth, title=title))
    return headers


def parse_section_anchors(profiles_yaml_path: Path) -> dict[str, str]:
    """Return ``{anchor_name: "X-Y"}`` for every anchor in the ``sections:`` block.

    Anchors with ``lines: "N/A"`` (external or retired compatibility
    sections) are included so the caller can skip them deliberately rather
    than silently dropping them.
    """
    if not profiles_yaml_path.is_file():
        raise FileNotFoundError(
            f"context_profiles.yaml not found at {profiles_yaml_path}. "
            "Pass --profiles-yaml if the file lives elsewhere."
        )
    text = profiles_yaml_path.read_text(encoding="utf-8")
    block_match = _SECTIONS_BLOCK_RE.search(text)
    if block_match is None:
        # S-5 — surface a malformed input loudly rather than silently
        # returning an empty mapping (which would make every anchor
        # appear "unchanged" and the operator would never notice the
        # realignment never happened).
        raise ValueError(
            f"Could not locate the `sections:` block in {profiles_yaml_path}. "
            "The expected layout is `^sections:` at column 0 followed by "
            "indented anchor blocks. Has the YAML been restructured?"
        )
    body = block_match.group("body")
    anchors: dict[str, str] = {}
    for anchor_match in _ANCHOR_LINES_RE.finditer(body):
        anchors[anchor_match.group("anchor")] = anchor_match.group("lines")
    return anchors


def _next_header_after(headers: list[Header], current_line: int) -> int | None:
    """Return the line of the first header strictly after ``current_line``."""
    for h in headers:
        if h.line > current_line:
            return h.line
    return None


def _is_header_line(headers: list[Header], line: int) -> bool:
    """Return True iff ``line`` is a SKILL.md ``##``/``###`` heading."""
    return any(h.line == line for h in headers)


def compute_realignment(
    headers: list[Header],
    anchors: dict[str, str],
) -> list[AnchorChange]:
    """Compute realignment proposals for each anchor.

    Anchors whose START line is a SKILL.md header → range recomputed as
    ``start..(next_header_line - 1)``. If no further header exists (the
    anchor is at the last section), the range extends to the LAST header
    line (a conservative single-line fallback — operators should hand-edit
    the trailing range if a multi-line tail is desired).

    Anchors whose START line is NOT a header (operator-defined sub-ranges
    like ``wave_task_constraints: "193-197"``), or whose lines value is
    ``"N/A"`` (external sections), or whose START is line 1 (frontmatter —
    pre-first-header), are SKIPPED — the proposal is the unchanged range.
    """
    changes: list[AnchorChange] = []
    for anchor, current_range in anchors.items():
        unchanged = AnchorChange(anchor=anchor, old_range=current_range, new_range=current_range)
        if current_range == "N/A":
            changes.append(unchanged)
            continue
        try:
            start_str, _ = current_range.split("-", 1)
            start_line = int(start_str)
        except ValueError:
            # Malformed range (no "-" or non-integer start): surface as
            # unchanged so the operator can spot the entry without the
            # script silently rewriting it (S-5 — never overwrite
            # malformed input). Hand-edit the YAML first, then re-run.
            changes.append(unchanged)
            continue

        if start_line <= 1 or not _is_header_line(headers, start_line):
            changes.append(unchanged)
            continue

        next_line = _next_header_after(headers, start_line)
        if next_line is None:
            new_end = headers[-1].line if headers else start_line
        else:
            new_end = next_line - 1
        new_range = f"{start_line}-{new_end}"
        changes.append(AnchorChange(anchor=anchor, old_range=current_range, new_range=new_range))
    return changes


def _rewrite_yaml_in_place(
    profiles_yaml_path: Path,
    changes: list[AnchorChange],
) -> int:
    """Apply ``changes`` to ``profiles_yaml_path`` in place. Returns # rewritten lines.

    Only the ``lines: "X-Y"`` literal under each anchor is touched. Comments,
    whitespace, and sibling fields (``tokens_est:`` / ``content_type:``) are
    preserved byte-identically.
    """
    text = profiles_yaml_path.read_text(encoding="utf-8")
    rewritten = 0
    for change in changes:
        if not change.changed:
            continue
        # Build a targeted pattern: match the specific anchor's lines line.
        # Use a multiline anchor to ensure we hit the right block (anchors are
        # unique within `sections:`, so this is safe).
        pattern = re.compile(
            r"(^  "
            + re.escape(change.anchor)
            + r":\s*\n    lines:\s*\")"
            + re.escape(change.old_range)
            + r"(\"\s*\n)",
            re.MULTILINE,
        )
        new_text, n = pattern.subn(r"\g<1>" + change.new_range + r"\g<2>", text, count=1)
        if n != 1:
            # S-5 — if the regex unexpectedly fails to match (e.g. because the
            # YAML formatting was edited by hand to a non-standard layout),
            # raise instead of silently leaving the file half-updated.
            raise RuntimeError(
                f'Failed to locate `{change.anchor}: lines: "{change.old_range}"` '
                f"in {profiles_yaml_path}. The YAML formatting may have drifted "
                "from the expected 2-space indent / quoted-string convention. "
                "Re-run with --dry-run to inspect the proposed changes, then "
                "fix the formatting manually before re-applying."
            )
        text = new_text
        rewritten += 1
    profiles_yaml_path.write_text(text, encoding="utf-8")
    return rewritten


def realign_anchors(
    skill_md_path: Path | str = DEFAULT_SKILL_MD,
    profiles_yaml_path: Path | str = DEFAULT_PROFILES_YAML,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """Realign ``context_profiles.yaml`` ``sections:`` ranges to current SKILL.md.

    Parameters
    ----------
    skill_md_path:
        Path to the SKILL.md whose headers define the canonical line ranges.
    profiles_yaml_path:
        Path to ``context_profiles.yaml``. The ``sections:`` block is the
        rewrite target; the surrounding YAML is preserved byte-identically.
    dry_run:
        If True, compute proposals and return them without writing the YAML.
        Use this for CI smoke tests / manual review before applying.

    Returns
    -------
    dict with keys:
        ``changes``        — list[AnchorChange] for every anchor inspected.
        ``changed_count``  — # of anchors whose range was rewritten (or
                             would be rewritten in dry-run mode).
        ``skipped_count``  — # of anchors left untouched (sub-ranges, N/A,
                             frontmatter at line 1).
        ``rewritten``      — # of lines actually written to disk (0 in
                             dry-run mode; equal to ``changed_count`` after
                             a successful apply).

    Raises
    ------
    FileNotFoundError:
        If ``skill_md_path`` or ``profiles_yaml_path`` is missing (S-5).
    ValueError:
        If the YAML's ``sections:`` block cannot be located (S-5).
    RuntimeError:
        If an anchor's ``lines:`` line cannot be regex-matched during the
        write phase (S-5 — never half-update the file).
    """
    skill_md_path = Path(skill_md_path)
    profiles_yaml_path = Path(profiles_yaml_path)

    headers = parse_skill_md_headers(skill_md_path)
    anchors = parse_section_anchors(profiles_yaml_path)
    changes = compute_realignment(headers, anchors)

    changed = [c for c in changes if c.changed]
    skipped = [c for c in changes if not c.changed]

    rewritten = 0
    if not dry_run and changed:
        rewritten = _rewrite_yaml_in_place(profiles_yaml_path, changes)

    return {
        "changes": changes,
        "changed_count": len(changed),
        "skipped_count": len(skipped),
        "rewritten": rewritten,
        "dry_run": dry_run,
    }


def _format_report(result: dict[str, object]) -> str:
    """Render a human-readable summary of ``realign_anchors`` output."""
    changes: list[AnchorChange] = result["changes"]  # type: ignore[assignment]
    changed = [c for c in changes if c.changed]
    lines = []
    mode = "dry-run" if result["dry_run"] else "apply"
    if not changed:
        lines.append(
            f"realign_section_anchors: no changes (mode={mode}; "
            f"{result['changed_count']} changed, {result['skipped_count']} skipped)."
        )
    else:
        verb = "would change" if result["dry_run"] else "changed"
        lines.append(
            f"realign_section_anchors: {verb} {len(changed)} anchor(s) "
            f"(mode={mode}; {result['skipped_count']} skipped)."
        )
        for c in changed:
            lines.append(f"  - {c.anchor}: {c.old_range!r} -> {c.new_range!r}")
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Realign context_profiles.yaml `sections:` line ranges against the "
            "current SKILL.md headers. Closes v12.3.0 retro §4.3."
        )
    )
    parser.add_argument(
        "--skill-md",
        type=Path,
        default=DEFAULT_SKILL_MD,
        help=f"Path to SKILL.md (default: {DEFAULT_SKILL_MD.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--profiles-yaml",
        type=Path,
        default=DEFAULT_PROFILES_YAML,
        help=(
            "Path to context_profiles.yaml "
            f"(default: {DEFAULT_PROFILES_YAML.relative_to(REPO_ROOT)})"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed changes without writing the YAML (default).",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write the realigned ranges to context_profiles.yaml in place.",
    )
    args = parser.parse_args(argv)

    # Default is dry-run (operator must opt-in to mutate the YAML).
    dry_run = not args.apply
    try:
        result = realign_anchors(
            skill_md_path=args.skill_md,
            profiles_yaml_path=args.profiles_yaml,
            dry_run=dry_run,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        # S-5 — surface friendly error message + non-zero exit.
        sys.stderr.write(f"realign_section_anchors: ERROR: {exc}\n")
        return 1
    print(_format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
