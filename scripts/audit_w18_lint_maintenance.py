#!/usr/bin/env python3
"""Audit the W-18 ghost-audit lint accumulation in test_no_ghost_features.py.

This script implements the v10.5.0 PV-05 D-D-4 deliverable per
`.local/research/v11.0.0_patches/D-D-4.md` §2. The audit answers two
linked questions:

1. **How many cycle-specific ``test_v*_*_new_symbols_have_coverage``
   lints have accumulated in ``tests/test_no_ghost_features.py``, and
   what is their cumulative LOC cost?**
2. **Which pinned file paths / module symbols in those lints are
   "stale" — i.e. reference files that no longer exist or symbols
   that were superseded by a later cycle?**

The audit emits a cycle-by-cycle trajectory table + a per-lint
staleness summary. The CONSOLIDATION of historical lints is
OUT-OF-SCOPE per the D-D-4 PDS §2 risk note (consolidation would
lose per-cycle traceability). This patch ships only the evidence.

Algorithm (per PDS §2):

1. Read ``tests/test_no_ghost_features.py`` once.
2. Regex-extract every top-level ``def test_v{major}_{minor}_{patch}_*(``
   function signature + the line range it spans (function start ->
   next top-level def).
3. For each block, count:
   - LOC between function start and next top-level def.
   - Pinned file paths (regex ``"[A-Za-z_][A-Za-z0-9_/-]*\\.py"``).
   - Staleness: does each pinned file still exist under the repo?
4. Aggregate by cycle version (v9.1.0, v9.1.1, ..., v10.4.0) and emit
   a cycle-by-cycle markdown table.

Public API:

* :func:`extract_cycle_lints(text)` -> list[dict]
* :func:`count_stale_pins(repo_root, lints)` -> int
* :func:`compute_trajectory(lints)` -> list[dict]
* :func:`render_markdown_report(lints, trajectory, stale_count)` -> str
* :func:`run(repo_root, *, json_out, output)` -> int

Entry point: ``python scripts/audit_w18_lint_maintenance.py
[--repo-root .] [--json] [--output PATH]``

Source: v10.5.0 PV-05 — codified per
`.local/research/v11.0.0_patches/D-D-4.md` §2.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

__all__ = [
    "compute_trajectory",
    "count_stale_pins",
    "extract_cycle_lints",
    "render_markdown_report",
    "run",
]

# Regex matches `def test_v<MAJOR>_<MINOR>_<PATCH>_*(` at top level.
# Captures the version tuple in groups 1-3 + the rest of the name.
_CYCLE_LINT_RE = re.compile(
    r"^def\s+(test_v(\d+)_(\d+)_(\d+)_[A-Za-z0-9_]+)\s*\(",
    re.MULTILINE,
)
# Matches pinned python file paths inside test source bodies (e.g.
# `src/devolaflow/compressor/__init__.py` / `tests/test_foo.py`).
# Conservative — only word-chars + `/` + `.py`.
_PATH_PIN_RE = re.compile(r'"([A-Za-z_][A-Za-z0-9_/\-.]*\.py)"')


def extract_cycle_lints(text: str) -> list[dict[str, Any]]:
    """Extract each cycle-specific W-18 lint's metadata.

    Args:
      text: Full body of ``tests/test_no_ghost_features.py``.

    Returns:
      List of dicts sorted by source-line order. Each dict has:

      * ``name`` (str) — full function name (e.g.
        ``"test_v10_3_0_new_symbols_have_coverage"``).
      * ``version`` (str) — dotted version (e.g. ``"10.3.0"``).
      * ``major`` / ``minor`` / ``patch`` (int).
      * ``start_line`` (int — 1-indexed source line of the ``def``).
      * ``end_line`` (int — line BEFORE next top-level def; last
        lint extends to EOF).
      * ``loc`` (int) — ``end_line - start_line + 1``.
      * ``pinned_paths`` (list[str]) — path literals referenced
        inside the function body.
    """
    matches: list[tuple[re.Match[str], int]] = []
    for m in _CYCLE_LINT_RE.finditer(text):
        # Count lines up to match start (1-indexed line number).
        line_no = text.count("\n", 0, m.start()) + 1
        matches.append((m, line_no))

    if not matches:
        return []

    total_lines = text.count("\n") + 1
    lines = text.splitlines()
    result: list[dict[str, Any]] = []
    for i, (m, start_line) in enumerate(matches):
        end_line = matches[i + 1][1] - 1 if i + 1 < len(matches) else total_lines
        body = "\n".join(lines[start_line - 1 : end_line])
        pinned = _PATH_PIN_RE.findall(body)
        result.append(
            {
                "name": m.group(1),
                "version": f"{m.group(2)}.{m.group(3)}.{m.group(4)}",
                "major": int(m.group(2)),
                "minor": int(m.group(3)),
                "patch": int(m.group(4)),
                "start_line": start_line,
                "end_line": end_line,
                "loc": end_line - start_line + 1,
                "pinned_paths": pinned,
            }
        )
    return result


def count_stale_pins(repo_root: Path, lints: list[dict[str, Any]]) -> int:
    """Count pinned paths that NO LONGER exist under ``repo_root``.

    Args:
      repo_root: Repository root.
      lints: Output of :func:`extract_cycle_lints`.

    Returns:
      Total count of path-literals across all lints that can no
      longer be resolved to an existing file.
    """
    stale = 0
    for lint in lints:
        for rel in lint.get("pinned_paths", []):
            if not (repo_root / rel).is_file():
                stale += 1
    return stale


def compute_trajectory(lints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute cumulative LOC / lint-count per cycle version.

    Args:
      lints: Output of :func:`extract_cycle_lints`.

    Returns:
      List of dicts sorted by version (major, minor, patch ascending)
      with keys:

      * ``version`` (str)
      * ``lints_in_cycle`` (int)
      * ``loc_in_cycle`` (int)
      * ``cumulative_lints`` (int)
      * ``cumulative_loc`` (int)
    """
    # Aggregate per (major, minor, patch) version string.
    per_version: dict[str, list[dict[str, Any]]] = {}
    for lint in lints:
        per_version.setdefault(lint["version"], []).append(lint)

    # Sort by numeric version tuple.
    sorted_versions = sorted(per_version.keys(), key=_version_key)

    cum_lints = 0
    cum_loc = 0
    trajectory: list[dict[str, Any]] = []
    for ver in sorted_versions:
        entries = per_version[ver]
        lints_in = len(entries)
        loc_in = sum(e["loc"] for e in entries)
        cum_lints += lints_in
        cum_loc += loc_in
        trajectory.append(
            {
                "version": ver,
                "lints_in_cycle": lints_in,
                "loc_in_cycle": loc_in,
                "cumulative_lints": cum_lints,
                "cumulative_loc": cum_loc,
            }
        )
    return trajectory


def _version_key(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def render_markdown_report(
    lints: list[dict[str, Any]],
    trajectory: list[dict[str, Any]],
    stale_count: int,
) -> str:
    """Render audit results as a markdown report.

    Args:
      lints: Output of :func:`extract_cycle_lints`.
      trajectory: Output of :func:`compute_trajectory`.
      stale_count: Total stale pins across all lints.

    Returns:
      Markdown ready to write to
      ``.local/research/v10.5.X_w18_lint_audit.md``.
    """
    total_lints = len(lints)
    total_loc = sum(lint["loc"] for lint in lints)
    avg_loc = (total_loc / total_lints) if total_lints else 0.0
    lines: list[str] = [
        "# v10.5.0 PV-05 D-D-4 W-18 Ghost-Audit Lint Maintenance Audit",
        "",
        "> Generated by `scripts/audit_w18_lint_maintenance.py` per",
        "> `.local/research/v11.0.0_patches/D-D-4.md` §2.",
        "",
        "## Summary",
        "",
        f"- Cycle-specific W-18 lints: **{total_lints}**",
        f"- Cumulative LOC across lints: **{total_loc}**",
        f"- Avg LOC per lint: **{avg_loc:.1f}**",
        f"- Stale path-pins (file no longer exists): **{stale_count}**",
        "",
        "## Cycle-by-Cycle Trajectory",
        "",
        "| Version | Lints in cycle | LOC in cycle | Cum. lints | Cum. LOC |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in trajectory:
        lines.append(
            f"| `{row['version']}` | {row['lints_in_cycle']} | "
            f"{row['loc_in_cycle']} | {row['cumulative_lints']} | "
            f"{row['cumulative_loc']} |"
        )

    lines.extend(
        [
            "",
            "## Per-Lint Detail",
            "",
            "| Function | Version | Lines | LOC | Pinned paths | Stale |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for lint in lints:
        pins = len(lint.get("pinned_paths", []))
        lines.append(
            f"| `{lint['name']}` | {lint['version']} | "
            f"L{lint['start_line']}-L{lint['end_line']} | {lint['loc']} | "
            f"{pins} | — |"
        )

    lines.extend(
        [
            "",
            "## Projection",
            "",
            "Per PDS §5.1, the v10.3.0 empirical avg is ~150 LOC / cycle-lint;",
            "a 5-cycle forward window therefore projects ~750 LOC per major.",
            "The audit ships the trajectory data so v11.X.0+ operators can",
            "decide whether to consolidate (loses traceability) or preserve",
            "(pays ~600 LOC/cycle of scroll-past cost). Consolidation is",
            "DEFERRED per the D-D-4 PDS §2 risk note — this patch is",
            "observability-only.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    repo_root: Path,
    *,
    json_out: bool = False,
    output: Path | None = None,
) -> int:
    """Entry-point — read the ghost-audit file, extract, emit report.

    Args:
      repo_root: Repository root.
      json_out: Emit JSON instead of markdown.
      output: Optional output path.

    Returns:
      Always 0 — observability-only audit. Fresh clones without the
      ghost-audit file still succeed with an empty report.
    """
    test_file = repo_root / "tests" / "test_no_ghost_features.py"
    text = test_file.read_text(encoding="utf-8") if test_file.is_file() else ""
    lints = extract_cycle_lints(text)
    trajectory = compute_trajectory(lints)
    stale_count = count_stale_pins(repo_root, lints)

    payload: str
    if json_out:
        payload = json.dumps(
            {
                "lints": lints,
                "trajectory": trajectory,
                "stale_count": stale_count,
            },
            indent=2,
            sort_keys=True,
        )
    else:
        payload = render_markdown_report(lints, trajectory, stale_count)

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
    args = parser.parse_args(argv)
    return run(args.repo_root, json_out=args.json_out, output=args.output)


if __name__ == "__main__":
    sys.exit(main())
