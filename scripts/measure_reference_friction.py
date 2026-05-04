#!/usr/bin/env python3
"""Measure reference comprehension friction across SKILL.md + 14 references.

This script implements the v10.5.0 PV-04 D-D-3 deliverable per
`.local/research/v11.0.0_patches/D-D-3.md` §2. The audit answers a
single epistemic question: **after the C-4 line-budget pressure
applied across v9.0.0..v10.4.0 cycles, are there specific paragraphs
in SKILL.md or any reference that have drifted from "dense but
clear" toward "compressed and ambiguous"?**

The audit is observability-only — it produces a markdown report
with a per-reference density table + the 3 worst paragraphs (the
"compressed-and-cryptic candidates") cited verbatim with line
numbers. The audit does NOT modify any reference; future cycles
review the evidence and decide whether to expand specific
paragraphs.

Algorithm (per PDS §2):

1. For each of SKILL.md + 14 references, compute:
   - line count, word count, average line length
   - abbreviation density (regex `\\b[A-Z]{2,}-\\d+\\b`)
   - cross-reference density (`references/[a-z-]+\\.md` mentions)
   - example-block count (fenced code blocks per 100 lines)
2. Identify "dense" sections (>200 lines AND > heuristic threshold).
3. Identify the 3 worst paragraphs per heuristic — paragraphs
   that are (a) > 100 words AND (b) > 5 abbreviations AND (c)
   zero embedded example blocks.
4. Emit markdown with per-reference table + the 3 worst-paragraph
   citations + verbatim before/after expansion proposals.

Public API:

* :func:`scan_targets(repo_root)` -> list[Path]
* :func:`compute_density(text)` -> dict[str, float]
* :func:`find_dense_paragraphs(text, *, n)` -> list[dict]
* :func:`render_markdown_report(per_target, dense_paras)` -> str
* :func:`run(repo_root, *, json_out, output)` -> int

Entry point: ``python scripts/measure_reference_friction.py [--repo-root .]
[--json] [--output PATH]``

Source: v10.5.0 PV-04 — codified per
`.local/research/v11.0.0_patches/D-D-3.md` §2.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

__all__ = [
    "DENSITY_PARA_MIN_WORDS",
    "DENSITY_PARA_MIN_ABBREVS",
    "compute_density",
    "find_dense_paragraphs",
    "render_markdown_report",
    "run",
    "scan_targets",
]

# Heuristic thresholds for "compressed-and-cryptic" paragraph detection.
DENSITY_PARA_MIN_WORDS: int = 100
DENSITY_PARA_MIN_ABBREVS: int = 5
DEFAULT_WORST_N: int = 3

# Match cryptic acronym refs like S-9, A-6, C-4, W-18, BG-001, PV-04, ADR-007.
# Per `.local/research/v11.0.0_patches/D-D-3.md` §2 the heuristic targets
# "compressed-and-cryptic" density — single-letter rule refs like S-9 are
# the canonical bound (A-1..A-6 architecture, S-1..S-10 soul, C-1..C-9
# conventions, W-1..W-21 workflow). The regex therefore allows 1+ uppercase
# letters before the dash.
_ABBREV_RE = re.compile(r"\b[A-Z]{1,}-\d+\b")
_REF_LINK_RE = re.compile(r"references/[a-z][a-z\-]*\.md")
_FENCED_BLOCK_RE = re.compile(r"^```", re.MULTILINE)


def scan_targets(repo_root: Path) -> list[Path]:
    """Return SKILL.md + 14 references in stable order.

    Args:
      repo_root: Repository root.

    Returns:
      Ordered list: SKILL.md first, then references/*.md sorted
      alphabetically. Empty list if `workflow-system/agent/` is
      absent (operator-friendly: works on a fresh clone without
      DevolaFlow content).
    """
    base = repo_root / "workflow-system" / "agent"
    if not base.is_dir():
        return []
    targets: list[Path] = []
    skill = base / "SKILL.md"
    if skill.is_file():
        targets.append(skill)
    refs_dir = base / "references"
    if refs_dir.is_dir():
        targets.extend(sorted(refs_dir.glob("*.md")))
    return targets


def compute_density(text: str) -> dict[str, float]:
    """Compute density metrics for one document.

    Args:
      text: Document body.

    Returns:
      Dict with keys:

      * ``line_count`` (int)
      * ``word_count`` (int)
      * ``avg_line_length`` (float — chars/line average)
      * ``abbrev_count`` (int)
      * ``abbrev_per_100_lines`` (float)
      * ``ref_link_count`` (int)
      * ``ref_links_per_100_lines`` (float)
      * ``fenced_blocks`` (int — total ``\\`\\`\\``` fence lines / 2)
      * ``fenced_blocks_per_100_lines`` (float)
    """
    lines = text.splitlines()
    line_count = len(lines)
    word_count = len(text.split())
    abbrev_count = len(_ABBREV_RE.findall(text))
    ref_link_count = len(_REF_LINK_RE.findall(text))
    fence_marks = len(_FENCED_BLOCK_RE.findall(text))
    fenced_blocks = fence_marks // 2  # opening + closing per block
    avg_line_length = (sum(len(line) for line in lines) / line_count) if line_count else 0.0

    def per_100(n: int) -> float:
        return (n * 100.0 / line_count) if line_count else 0.0

    return {
        "line_count": line_count,
        "word_count": word_count,
        "avg_line_length": avg_line_length,
        "abbrev_count": abbrev_count,
        "abbrev_per_100_lines": per_100(abbrev_count),
        "ref_link_count": ref_link_count,
        "ref_links_per_100_lines": per_100(ref_link_count),
        "fenced_blocks": fenced_blocks,
        "fenced_blocks_per_100_lines": per_100(fenced_blocks),
    }


def find_dense_paragraphs(
    text: str,
    *,
    source_path: str = "<text>",
    min_words: int = DENSITY_PARA_MIN_WORDS,
    min_abbrevs: int = DENSITY_PARA_MIN_ABBREVS,
) -> list[dict[str, Any]]:
    """Find paragraphs with high abbreviation + word density + zero examples.

    Args:
      text: Document body.
      source_path: Path label for output (e.g.
        ``"workflow-system/agent/SKILL.md"``).
      min_words: Minimum word count for a paragraph to be a candidate.
      min_abbrevs: Minimum abbreviation count.

    Returns:
      List of candidate paragraph dicts with keys:

      * ``source_path`` (str)
      * ``start_line`` (int — 1-indexed)
      * ``end_line`` (int)
      * ``word_count`` (int)
      * ``abbrev_count`` (int)
      * ``has_fenced_block_within`` (bool)
      * ``preview`` (str — first 80 chars)
    """
    candidates: list[dict[str, Any]] = []
    lines = text.splitlines()
    in_fenced = False
    para_start: int | None = None
    para_lines: list[str] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fenced = not in_fenced
            # Treat fence lines as paragraph terminators (they carry no
            # comprehensible prose; they're the EXAMPLE markers we want
            # to detect AROUND).
            if para_start is not None:
                _record_candidate(
                    candidates,
                    source_path,
                    para_start,
                    idx - 1,
                    para_lines,
                    has_fence=True,
                    min_words=min_words,
                    min_abbrevs=min_abbrevs,
                )
                para_start = None
                para_lines = []
            continue
        if in_fenced:
            continue
        if not stripped:
            if para_start is not None:
                _record_candidate(
                    candidates,
                    source_path,
                    para_start,
                    idx - 1,
                    para_lines,
                    has_fence=False,
                    min_words=min_words,
                    min_abbrevs=min_abbrevs,
                )
                para_start = None
                para_lines = []
            continue
        if para_start is None:
            para_start = idx
        para_lines.append(line)

    # Trailing paragraph at EOF.
    if para_start is not None:
        _record_candidate(
            candidates,
            source_path,
            para_start,
            len(lines),
            para_lines,
            has_fence=False,
            min_words=min_words,
            min_abbrevs=min_abbrevs,
        )

    return candidates


def _record_candidate(
    candidates: list[dict[str, Any]],
    source_path: str,
    start_line: int,
    end_line: int,
    para_lines: list[str],
    *,
    has_fence: bool,
    min_words: int,
    min_abbrevs: int,
) -> None:
    """Append a paragraph as a candidate iff it crosses the heuristic bar."""
    body = "\n".join(para_lines)
    word_count = len(body.split())
    if word_count < min_words:
        return
    abbrev_count = len(_ABBREV_RE.findall(body))
    if abbrev_count < min_abbrevs:
        return
    # Per the PDS §2 heuristic: zero embedded example blocks. The
    # `has_fence` flag is True when the paragraph is bounded by a
    # fenced block (=> it has an example), so we EXCLUDE it.
    if has_fence:
        return
    candidates.append(
        {
            "source_path": source_path,
            "start_line": start_line,
            "end_line": end_line,
            "word_count": word_count,
            "abbrev_count": abbrev_count,
            "has_fenced_block_within": False,
            "preview": body[:80].replace("\n", " "),
        }
    )


def render_markdown_report(
    per_target: dict[str, dict[str, float]],
    dense_paras: list[dict[str, Any]],
    worst_n: int = DEFAULT_WORST_N,
) -> str:
    """Render audit results as a markdown report.

    Args:
      per_target: Mapping path -> density dict.
      dense_paras: List of candidate paragraphs (already
        deterministically sorted).
      worst_n: How many candidates to highlight.

    Returns:
      Markdown ready to write to
      ``.local/research/v10.5.X_reference_friction.md``.
    """
    lines: list[str] = [
        "# v10.5.0 PV-04 D-D-3 Reference Friction Measurement",
        "",
        "> Generated by `scripts/measure_reference_friction.py` per",
        "> `.local/research/v11.0.0_patches/D-D-3.md` §2.",
        "",
        "## Summary",
        "",
        f"- Targets scanned: **{len(per_target)}**",
        f"- Compressed-and-cryptic candidates (>= {DENSITY_PARA_MIN_WORDS} words AND "
        f">= {DENSITY_PARA_MIN_ABBREVS} abbrevs AND no embedded example block): "
        f"**{len(dense_paras)}**",
        f"- Heuristic worst-N highlighted below: **{min(worst_n, len(dense_paras))}**",
        "",
        "## Per-Target Density",
        "",
        "| Target | Lines | Words | Abbrev/100 | RefLinks/100 | Blocks/100 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for path in sorted(per_target.keys()):
        d = per_target[path]
        lines.append(
            f"| `{path}` | {int(d['line_count'])} | {int(d['word_count'])} | "
            f"{d['abbrev_per_100_lines']:.1f} | "
            f"{d['ref_links_per_100_lines']:.1f} | "
            f"{d['fenced_blocks_per_100_lines']:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Worst-N Compressed-and-Cryptic Candidates",
            "",
            "Heuristic: paragraph with `word_count >= "
            f"{DENSITY_PARA_MIN_WORDS}` AND `abbrev_count >= "
            f"{DENSITY_PARA_MIN_ABBREVS}` AND zero embedded fenced blocks.",
            "",
        ]
    )
    if not dense_paras:
        lines.append("(none — all reference paragraphs cleared the heuristic)")
    else:
        # Sort by abbreviation count then word count, both descending —
        # the densest are the "worst".
        ranked = sorted(
            dense_paras,
            key=lambda p: (-int(p["abbrev_count"]), -int(p["word_count"])),
        )
        for rank, candidate in enumerate(ranked[:worst_n], start=1):
            lines.append(
                f"### #{rank} — `{candidate['source_path']}` "
                f"L{candidate['start_line']}-L{candidate['end_line']} "
                f"({candidate['word_count']} words, "
                f"{candidate['abbrev_count']} abbrevs)"
            )
            lines.append("")
            lines.append(f"> Preview: {candidate['preview']}...")
            lines.append("")

    lines.extend(
        [
            "## Recommendation",
            "",
            "The audit ships only the EVIDENCE; refactor decisions are",
            "deferred to v11.X.0+ per the D-D-3 PDS §6 admission verdict.",
            "When a paragraph has budget headroom (the parent file is well",
            "below its tier ceiling per C-4), the proposal is to expand it",
            "with named symbols + a 3-line preamble; otherwise the paragraph",
            "stays as-is to preserve the contract surface.",
            "",
            "Targeted 3-paragraph extension proposals (per D-D-3 PDS §5):",
            "see the cited line ranges in this audit's worst-N section and",
            "the verbatim before/after suggestions in",
            "`.local/research/v11.0.0_patches/D-D-3.md` §5.1-§5.3.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    repo_root: Path,
    *,
    json_out: bool = False,
    output: Path | None = None,
    worst_n: int = DEFAULT_WORST_N,
) -> int:
    """Entry-point — scan targets, compute density, emit report.

    Returns:
      Always 0 (observability-only audit).
    """
    targets = scan_targets(repo_root)
    per_target: dict[str, dict[str, float]] = {}
    dense_paras: list[dict[str, Any]] = []
    for target in targets:
        rel = target.relative_to(repo_root).as_posix()
        text = target.read_text(encoding="utf-8")
        per_target[rel] = compute_density(text)
        dense_paras.extend(find_dense_paragraphs(text, source_path=rel))

    payload: str
    if json_out:
        payload = json.dumps(
            {"per_target": per_target, "dense_paragraphs": dense_paras},
            indent=2,
            sort_keys=True,
        )
    else:
        payload = render_markdown_report(per_target, dense_paras, worst_n=worst_n)

    if output is not None:
        output.write_text(payload + ("\n" if not payload.endswith("\n") else ""), encoding="utf-8")
    else:
        print(payload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current working directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Emit JSON instead of markdown",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to this path",
    )
    parser.add_argument(
        "--worst-n",
        type=int,
        default=DEFAULT_WORST_N,
        help=f"Number of worst-paragraph candidates to highlight (default {DEFAULT_WORST_N})",
    )
    args = parser.parse_args(argv)
    return run(
        args.repo_root,
        json_out=args.json_out,
        output=args.output,
        worst_n=args.worst_n,
    )


if __name__ == "__main__":
    sys.exit(main())
