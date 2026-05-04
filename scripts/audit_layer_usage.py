#!/usr/bin/env python3
"""Audit L0/L1/L2/L3 dispatcher layer usage across DevolaFlow cycle docs.

This script implements the v10.5.0 PV-01 D-A-1 deliverable per
`.local/research/v11.0.0_patches/D-A-1.md` §2. The audit answers a
single quantitative question: **across all v9.x and v10.x cycle plans
and retrospectives, how often is each agent layer (L0 / L1 / L2 / L3)
mentioned, and how often does a "Dispatch type" line bind to the L1
Stage Agent vs the L2 Wave Agent vs an L0->L3 collapse?**

The output is a markdown report (default) or JSON (`--json`) that
operators can read alongside the v11.0.0 SI-1 gap analysis to decide
whether to:

1. Keep the SKILL.md 4-Layer Agent Hierarchy table as-is (L1 + L2 are
   actively dispatched), OR
2. Annotate the table with "only-when-needed" markers for the L1 +
   L2 rows at the Standard tier (the v11.0.0 hypothesis).

The patch ships ONLY the audit + advisory annotation; behaviour
changes are deferred to v12.0+ pending operator review.

Algorithm (per PDS §2):

1. Glob `.local/research/v9.*.0_cycle_plan.md` +
   `v10.*.0_cycle_plan.md` + retrospectives.
2. For each doc, regex-extract:
   - `Dispatch type:` lines (Wave / Stage / Task) — precise dispatch
     pattern signal.
   - `L0 dispatch` / `L1 Stage` / `L2 Wave` / `L3 Task` mentions —
     generic role-mention signal.
   - `Single-Task shortcut` or `L0->L3` shortcut markers — collapse
     evidence.
3. Compute per-cycle counts; aggregate to a 4-row matrix.
4. Emit markdown with:
   - Per-doc ratio table.
   - Aggregate cycle-wide ratio.
   - Recommendation (advisory text for SKILL.md update).

Public API:

* :func:`scan_cycle_docs(repo_root, cycle_glob)` -> list[Path]
* :func:`extract_layer_signals(text)` -> dict[str, int]
* :func:`compute_layer_ratios(per_doc)` -> dict[str, float]
* :func:`render_markdown_report(per_doc, ratios)` -> str
* :func:`run(repo_root, *, cycle_glob, json_out)` -> int

Entry point: ``python scripts/audit_layer_usage.py [--repo-root .]
[--cycle-glob 'v10.*'] [--json] [--verbose] [--output PATH]``

Source: v10.5.0 PV-01 — codified per
`.local/research/v11.0.0_patches/D-A-1.md` §2.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

__all__ = [
    "DEFAULT_CYCLE_GLOBS",
    "LAYER_LABELS",
    "compute_layer_ratios",
    "extract_layer_signals",
    "render_markdown_report",
    "run",
    "scan_cycle_docs",
]

# Default doc patterns matched in `.local/research/`.
DEFAULT_CYCLE_GLOBS: tuple[str, ...] = (
    "v9.*.0_cycle_plan.md",
    "v9.*.0_retrospective.md",
    "v10.*.0_cycle_plan.md",
    "v10.*.0_retrospective.md",
)

# Stable display order; do NOT reorder (downstream JSON consumers key on this).
LAYER_LABELS: tuple[str, ...] = ("L0", "L1", "L2", "L3")

# Regex patterns. Each is conservative — we count "Dispatch type:" lines
# as the precise signal because they bind a PV to a layer; the role
# mentions (e.g. "L1 Stage Agent") are the loose signal for cross-check.
_DISPATCH_TYPE_RE = re.compile(
    r"Dispatch\s+type\s*[:=]\s*(Wave|Stage|Task)\b",
    re.IGNORECASE,
)
_LAYER_MENTION_RE: dict[str, re.Pattern[str]] = {
    "L0": re.compile(r"\bL0\b"),
    "L1": re.compile(r"\bL1\b"),
    "L2": re.compile(r"\bL2\b"),
    "L3": re.compile(r"\bL3\b"),
}
_COLLAPSE_RE = re.compile(
    r"L0\s*[\u2192>\-]+\s*L3|Single-Task\s+shortcut|SHORTCUT_SIMPLE",
    re.IGNORECASE,
)


def scan_cycle_docs(
    repo_root: Path,
    cycle_globs: tuple[str, ...] = DEFAULT_CYCLE_GLOBS,
) -> list[Path]:
    """Return sorted list of cycle docs under ``repo_root/.local/research/``.

    Args:
      repo_root: Repository root (the ``.local/research/`` subdir is read
        relative to this).
      cycle_globs: Glob patterns to match. Defaults to the v9.x +
        v10.x cycle plan + retrospective doc patterns.

    Returns:
      Sorted list of matched paths. Empty list when ``.local/research/``
      does not exist (operator-friendly: the script exits 0 with a
      "no inputs" report when run on a fresh clone).
    """
    research_dir = repo_root / ".local" / "research"
    if not research_dir.is_dir():
        return []
    matches: list[Path] = []
    for pattern in cycle_globs:
        matches.extend(research_dir.glob(pattern))
    return sorted(set(matches))


def extract_layer_signals(text: str) -> dict[str, int]:
    """Extract per-layer mention + dispatch-type + collapse counts from ``text``.

    Args:
      text: Body of one cycle plan / retrospective doc.

    Returns:
      Dict with keys:

      * ``L0`` / ``L1`` / ``L2`` / ``L3`` — generic role mention count
        (regex \\bL{n}\\b — conservative; loose signal).
      * ``dispatch_wave`` / ``dispatch_stage`` / ``dispatch_task`` —
        precise count of ``Dispatch type: Wave/Stage/Task`` lines.
      * ``collapse_l0_l3`` — count of ``L0->L3`` / "Single-Task
        shortcut" / "SHORTCUT_SIMPLE" markers (collapse evidence).
    """
    signals: dict[str, int] = {label: 0 for label in LAYER_LABELS}
    for label, pattern in _LAYER_MENTION_RE.items():
        signals[label] = len(pattern.findall(text))

    dispatch_counts = {"dispatch_wave": 0, "dispatch_stage": 0, "dispatch_task": 0}
    for match in _DISPATCH_TYPE_RE.findall(text):
        kind = match.lower()
        dispatch_counts[f"dispatch_{kind}"] += 1
    signals.update(dispatch_counts)

    signals["collapse_l0_l3"] = len(_COLLAPSE_RE.findall(text))
    return signals


def compute_layer_ratios(per_doc: dict[str, dict[str, int]]) -> dict[str, float]:
    """Aggregate per-doc signals into cycle-wide ratios.

    Args:
      per_doc: Mapping of doc path string -> signal dict
        (output of :func:`extract_layer_signals`).

    Returns:
      Dict with the cycle-wide aggregate ratios:

      * ``standalone_l1_ratio`` — fraction of dispatch-type lines that
        bind to ``Stage`` (signals dispatching to L1 Stage Agent).
      * ``standalone_l2_ratio`` — fraction of dispatch-type lines that
        bind to ``Wave`` (signals dispatching to L2 Wave Agent).
      * ``standalone_l3_ratio`` — fraction of dispatch-type lines that
        bind to ``Task`` (signals dispatching directly to L3).
      * ``collapse_ratio`` — collapses per total dispatch lines
        (collapse evidence ratio).
      * ``total_dispatch_lines`` — denominator (total
        ``Dispatch type:`` lines across all docs).
    """
    total_wave = sum(s.get("dispatch_wave", 0) for s in per_doc.values())
    total_stage = sum(s.get("dispatch_stage", 0) for s in per_doc.values())
    total_task = sum(s.get("dispatch_task", 0) for s in per_doc.values())
    total_collapse = sum(s.get("collapse_l0_l3", 0) for s in per_doc.values())
    total_dispatch = total_wave + total_stage + total_task

    if total_dispatch == 0:
        return {
            "standalone_l1_ratio": 0.0,
            "standalone_l2_ratio": 0.0,
            "standalone_l3_ratio": 0.0,
            "collapse_ratio": 0.0,
            "total_dispatch_lines": 0.0,
        }

    return {
        "standalone_l1_ratio": total_stage / total_dispatch,
        "standalone_l2_ratio": total_wave / total_dispatch,
        "standalone_l3_ratio": total_task / total_dispatch,
        "collapse_ratio": total_collapse / total_dispatch,
        "total_dispatch_lines": float(total_dispatch),
    }


def render_markdown_report(
    per_doc: dict[str, dict[str, int]],
    ratios: dict[str, float],
) -> str:
    """Render the audit results as a markdown report.

    Args:
      per_doc: Mapping doc path -> signal dict.
      ratios: Cycle-wide aggregate ratios.

    Returns:
      Markdown string ready to write to
      ``.local/research/v10.5.X_layer_usage_audit.md``.
    """
    lines: list[str] = [
        "# v10.5.0 PV-01 D-A-1 Layer Usage Audit",
        "",
        "> Generated by `scripts/audit_layer_usage.py` per",
        "> `.local/research/v11.0.0_patches/D-A-1.md` §2.",
        "",
        "## Summary",
        "",
        f"- Cycle docs scanned: **{len(per_doc)}**",
        f"- Total `Dispatch type:` lines: **{int(ratios['total_dispatch_lines'])}**",
        f"- Standalone L1 Stage dispatch ratio: **{ratios['standalone_l1_ratio']:.2%}**",
        f"- Standalone L2 Wave dispatch ratio: **{ratios['standalone_l2_ratio']:.2%}**",
        f"- Standalone L3 Task dispatch ratio: **{ratios['standalone_l3_ratio']:.2%}**",
        f"- L0->L3 collapse evidence ratio: **{ratios['collapse_ratio']:.2%}**",
        "",
        "## Per-Doc Layer Mentions",
        "",
        "| Doc | L0 | L1 | L2 | L3 | Wave | Stage | Task | L0->L3 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for doc_path in sorted(per_doc.keys()):
        signals = per_doc[doc_path]
        lines.append(
            f"| `{doc_path}` | {signals['L0']} | {signals['L1']} | "
            f"{signals['L2']} | {signals['L3']} | "
            f"{signals.get('dispatch_wave', 0)} | "
            f"{signals.get('dispatch_stage', 0)} | "
            f"{signals.get('dispatch_task', 0)} | "
            f"{signals.get('collapse_l0_l3', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "The audit's `standalone_l1_ratio` + `standalone_l2_ratio` measure how",
            "frequently the L1 Stage Agent or L2 Wave Agent is bound as the",
            "primary dispatch target across cycle docs. When both ratios are",
            "below ~10%, the SKILL.md §\"Quick Action Decision\" table SHOULD",
            "annotate L1 + L2 as **\"only-when-needed\"** at the Standard tier.",
            "",
            "v10.5.0 ships the audit + advisory annotation only; behaviour is",
            "preserved (L1 + L2 remain part of the 4-Layer hierarchy). The",
            "advisory wording short-circuits operator decision time on Simple",
            "tasks without altering the P1 invariant.",
            "",
            "See `examples/multi-stage-trace.md` for the worked counter-example",
            "showing WHEN L1 + L2 ARE necessary (cross-stage artifact merging).",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    repo_root: Path,
    *,
    cycle_globs: tuple[str, ...] = DEFAULT_CYCLE_GLOBS,
    json_out: bool = False,
    verbose: bool = False,
    output: Path | None = None,
) -> int:
    """Entry-point — scan cycle docs, compute ratios, emit report.

    Args:
      repo_root: Repository root (defaults to ``Path.cwd()`` from CLI).
      cycle_globs: Glob patterns; falls back to
        :data:`DEFAULT_CYCLE_GLOBS`.
      json_out: When True, emit JSON to stdout instead of markdown.
      verbose: When True, prints the path of each doc as it scans.
      output: When set, write markdown / JSON to this file in
        addition to (or instead of) stdout.

    Returns:
      ``0`` on success (always 0 — the audit is observability-only;
      no docs found is reported as an empty audit, not an error).
    """
    docs = scan_cycle_docs(repo_root, cycle_globs)
    per_doc: dict[str, dict[str, int]] = OrderedDict()
    for doc in docs:
        if verbose:
            print(f"  scan {doc.relative_to(repo_root)}", file=sys.stderr)
        rel = doc.relative_to(repo_root).as_posix()
        per_doc[rel] = extract_layer_signals(doc.read_text(encoding="utf-8"))
    ratios = compute_layer_ratios(per_doc)

    payload: str
    if json_out:
        payload = json.dumps(
            {"per_doc": per_doc, "ratios": ratios},
            indent=2,
            sort_keys=True,
        )
    else:
        payload = render_markdown_report(per_doc, ratios)

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
        "--cycle-glob",
        action="append",
        dest="cycle_globs",
        default=None,
        help="Override cycle-doc glob (repeatable; default scans v9.* + v10.*)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Emit JSON instead of markdown",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print scanned doc paths to stderr",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to this path instead of (or in addition to) stdout",
    )
    args = parser.parse_args(argv)
    cycle_globs = tuple(args.cycle_globs) if args.cycle_globs else DEFAULT_CYCLE_GLOBS
    return run(
        args.repo_root,
        cycle_globs=cycle_globs,
        json_out=args.json_out,
        verbose=args.verbose,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
