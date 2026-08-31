#!/usr/bin/env python3
"""Snapshot deterministic local health metrics for ``src/devolaflow/compressor/``.

The audit answers a bounded quantitative question: across the Python modules
currently present in ``src/devolaflow/compressor/``, what are the line-count,
function-count, and cyclomatic-complexity distributions, and how many
warning-class findings (CC > 10) does the surface carry?

The script is observability-only and performs no source mutations. It emits
Markdown by default or JSON with ``--json``. All primary measurements come
from the checked-out repository. The optional historical v9.3.0 pre-split
comparison is retained only as labeled legacy context.

Algorithm:

1. Glob ``src/devolaflow/compressor/*.py`` and record per-file LOC,
   including the additive ``context.py`` and ``evidence.py`` modules.
2. Invoke ``radon cc -nB`` once. If radon is unavailable or fails, emit an
   explicit degraded LOC/function-count-only report.
3. Parse local radon output and compute per-file and aggregate rank metrics.
4. Render a stable six-section report suitable for current research and
   harness evidence archives.

Public API:

* :func:`scan_compressor_files(repo_root)` -> list[Path]
* :func:`run_radon_cc(files)` -> tuple[str, bool]   # (raw_output, used_radon)
* :func:`parse_radon_cc(raw_output)` -> dict[str, list[FunctionMetric]]
* :func:`compute_health_summary(per_file)` -> CompressorHealth
* :func:`render_markdown_report(health, repo_root)` -> str
* :func:`run(repo_root, *, json_out, verbose, output)` -> int

Entry point: ``python scripts/snapshot_compressor_health.py
[--repo-root .] [--json] [--verbose] [--output PATH]``

External tool reference (S-7): https://radon.readthedocs.io/
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

__all__ = [
    "DEFAULT_COMPRESSOR_PACKAGE",
    "FunctionMetric",
    "CompressorHealth",
    "compute_health_summary",
    "parse_radon_cc",
    "render_markdown_report",
    "run",
    "run_radon_cc",
    "scan_compressor_files",
]

DEFAULT_COMPRESSOR_PACKAGE: str = "src/devolaflow/compressor"

# radon CC rank thresholds (per https://radon.readthedocs.io/en/latest/intro.html):
#   A: 1-5    (low risk)
#   B: 6-10   (low risk)
#   C: 11-20  (moderate — radon's `--no-assert` warning floor)
#   D: 21-30  (more than moderate)
#   E: 31-40  (high risk)
#   F: >40    (very high risk)
#
# The legacy v9.3.0 baseline used CC=11 (rank C) as "warning-class";
# retain that threshold so historical comparisons remain meaningful.
_RANK_TO_BUCKET: dict[str, str] = {
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D",
    "E": "E",
    "F": "F",
}
_WARNING_RANKS: frozenset[str] = frozenset({"C", "D", "E", "F"})

# radon CC output line shape (one per function):
#   "    F 851:0 ensure_plugin - C"
# The leading whitespace is consistent across radon versions; we
# capture line / function / rank and tolerate the "M" (method) /
# "C" (class) sigils (the audit doesn't distinguish them).
_RADON_LINE_RE = re.compile(
    r"^\s*(?P<sigil>F|M|C)\s+(?P<line>\d+):\d+\s+(?P<name>\S+)\s+-\s+(?P<rank>[A-F])\s*$"
)
_RADON_FILE_HEADER_RE = re.compile(
    r"^(?P<path>[^\s]+\.py)$",
    re.MULTILINE,
)

# Legacy v9.3.0 pre-split metrics retained for historical comparison only.
# Current health is always measured from the checked-out repository.
V9_3_0_BASELINE_AVG_COMPLEXITY: float = 4.98
V9_3_0_BASELINE_WARNING_COUNT: int = 2


@dataclasses.dataclass(frozen=True)
class FunctionMetric:
    """One function's CC datum extracted from a radon output line."""

    file: str  # relative to repo root
    line: int
    name: str
    rank: str  # one of A..F
    sigil: str  # F (function) / M (method) / C (class)


@dataclasses.dataclass(frozen=True)
class CompressorHealth:
    """Aggregated CC distribution + per-file metrics for ``compressor/``."""

    file_count: int
    total_loc: int
    total_function_count: int
    rank_histogram: dict[str, int]  # A..F → count
    warning_count: int  # functions at rank C or worse
    avg_complexity_estimate: float  # rough rank-average (A=2.5, B=8, C=15, D=25, E=35, F=45)
    per_file_loc: dict[str, int]
    per_file_function_count: dict[str, int]
    per_file_warning_findings: dict[str, list[FunctionMetric]]
    used_radon: bool  # False when the explicit degraded LOC-only path was used


# Conservative midpoint estimates per radon's documented thresholds —
# used to compute an avg_complexity estimate that's directly comparable
# to the v9.3.0 baseline avg=4.98. These are not exact CC values
# (radon's -nB output suppresses the integer CC); they are midpoints
# of each rank's documented range.
_RANK_MIDPOINT: dict[str, float] = {
    "A": 2.5,  # midpoint of [1, 5]
    "B": 8.0,  # midpoint of [6, 10]
    "C": 15.0,  # midpoint of [11, 20]
    "D": 25.0,  # midpoint of [21, 30]
    "E": 35.0,  # midpoint of [31, 40]
    "F": 45.0,  # conservative; radon reports >40 as F
}


def scan_compressor_files(
    repo_root: Path,
    package: str = DEFAULT_COMPRESSOR_PACKAGE,
) -> list[Path]:
    """Return sorted list of ``*.py`` files under ``<repo_root>/<package>``.

    Args:
      repo_root: Repository root (the package path is read relative).
      package: Package directory under repo_root (default
        ``src/devolaflow/compressor``).

    Returns:
      Sorted list of absolute paths. Empty list when the package
      directory does not exist (operator-friendly: the script exits 0
      with a "no inputs" report so a fresh clone or an `__init__.py`-
      only package doesn't break the W-19 cycle-archive run).
    """
    pkg_dir = repo_root / package
    if not pkg_dir.is_dir():
        return []
    return sorted(pkg_dir.glob("*.py"))


def run_radon_cc(
    files: list[Path],
    *,
    repo_root: Path | None = None,
) -> tuple[str, bool]:
    """Run ``radon cc -nB <files>`` and return ``(raw_output, used_radon)``.

    Args:
      files: List of Python files to analyse. Empty list returns
        ``("", True)`` (the audit-on-empty case).
      repo_root: Optional repository root. When supplied, file paths
        are passed to radon RELATIVE to ``repo_root`` (with
        ``cwd=repo_root``) so the parsed output carries relative
        file paths — required by Soul Rule S-2 ("No Absolute Paths
        in Agent Files"). When ``None``, files are passed verbatim
        (legacy / direct-call path).

    Returns:
      Tuple of:

      * ``raw_output``: stdout of ``radon cc -nB``. Empty string when
        ``radon`` is unavailable OR when ``files`` is empty.
      * ``used_radon``: ``True`` when radon was successfully invoked,
        ``False`` when ``shutil.which("radon")`` returned ``None`` or
        the subprocess failed (the explicit degraded path).

    Per S-5 (no-silent-failures), a subprocess failure logs to stderr and
    returns ``used_radon=False`` so the report marks missing complexity
    measurements explicitly.
    """
    if not files:
        return "", True
    if shutil.which("radon") is None:
        print(
            "[snapshot_compressor_health] radon unavailable on PATH; "
            "emitting degraded LOC-only measurements",
            file=sys.stderr,
        )
        return "", False
    if repo_root is not None:
        file_args = [str(f.relative_to(repo_root)) for f in files]
        cwd: Path | None = repo_root
    else:
        file_args = [str(f) for f in files]
        cwd = None
    cmd = ["radon", "cc", "-nB", *file_args]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(cwd) if cwd is not None else None,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(
            f"[snapshot_compressor_health] radon invocation failed ({exc}); "
            "emitting degraded LOC-only measurements",
            file=sys.stderr,
        )
        return "", False
    if proc.returncode != 0:
        print(
            f"[snapshot_compressor_health] radon exited {proc.returncode} "
            f"(stderr={proc.stderr[:200]!r}); emitting degraded LOC-only measurements",
            file=sys.stderr,
        )
        return "", False
    return proc.stdout, True


def parse_radon_cc(raw_output: str) -> dict[str, list[FunctionMetric]]:
    """Parse ``radon cc -nB`` output into per-file function metric lists.

    Args:
      raw_output: stdout of ``radon cc -nB`` (multi-file output).

    Returns:
      Mapping ``file_path_str -> list[FunctionMetric]``. The dict is
      ordered by file appearance (so the first key is the first file
      radon enumerated). Files with zero qualifying functions are
      INCLUDED (with empty list value) so per-file LOC + function
      counts can still be computed downstream. Returns ``{}`` on an
      empty input.

    The ``-nB`` flag tells radon to only print functions at rank B or
    worse (suppressing rank A). For the audit this is the right floor
    — A-rated functions are noise in a complexity health report. The
    parser still records the rank verbatim so downstream consumers
    can see the distribution.
    """
    if not raw_output.strip():
        return {}

    per_file: OrderedDict[str, list[FunctionMetric]] = OrderedDict()
    current_file: str | None = None
    for raw_line in raw_output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        # File header (no leading whitespace, ends with .py)
        header_match = _RADON_FILE_HEADER_RE.match(line)
        if header_match and not line.startswith(" ") and not line.startswith("\t"):
            current_file = header_match.group("path")
            per_file.setdefault(current_file, [])
            continue
        # Function/Method/Class metric line
        if current_file is None:
            continue
        metric_match = _RADON_LINE_RE.match(line)
        if metric_match is None:
            continue
        per_file[current_file].append(
            FunctionMetric(
                file=current_file,
                line=int(metric_match.group("line")),
                name=metric_match.group("name"),
                rank=metric_match.group("rank"),
                sigil=metric_match.group("sigil"),
            )
        )
    return per_file


def _count_lines(path: Path) -> int:
    """Return the line count for *path*. Returns 0 on read failure."""
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return 0


def _count_functions(path: Path) -> int:
    """Cheap LOC-only function count via ``def `` + ``async def `` regex.

    Used when radon is unavailable. Conservatively over-counts by 0
    (won't catch lambdas, but compresses to ``def `` line literal so
    nested functions ARE included). Good enough for the degraded path;
    precise complexity ranks come from radon when available.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    return len(re.findall(r"^\s*(?:async\s+)?def\s+\w+\s*\(", text, re.MULTILINE))


def compute_health_summary(
    files: list[Path],
    per_file_metrics: dict[str, list[FunctionMetric]],
    *,
    used_radon: bool,
    repo_root: Path,
) -> CompressorHealth:
    """Aggregate per-file metrics into a :class:`CompressorHealth` struct.

    Args:
      files: Sorted list of Python files in the package.
      per_file_metrics: Output of :func:`parse_radon_cc`. Empty when
        radon was unavailable (degraded local measurement).
      used_radon: ``True`` when radon was successfully invoked. When
        ``False``, the rank histogram + warning count + avg complexity
        are all ZERO (the LOC-only path emits ``[degraded measurement]``
        markers in the rendered markdown).
      repo_root: Repository root (used to relativize file paths in the
        per_file_loc dict).

    Returns:
      :class:`CompressorHealth` with per-file + aggregate metrics.
    """
    rank_histogram: dict[str, int] = {label: 0 for label in _RANK_TO_BUCKET}
    per_file_loc: OrderedDict[str, int] = OrderedDict()
    per_file_fn_count: OrderedDict[str, int] = OrderedDict()
    per_file_warnings: OrderedDict[str, list[FunctionMetric]] = OrderedDict()
    total_loc = 0
    warning_count = 0
    weighted_complexity_sum = 0.0
    total_function_count = 0

    for file_path in files:
        rel = str(file_path.relative_to(repo_root))
        loc = _count_lines(file_path)
        per_file_loc[rel] = loc
        total_loc += loc

        # Resolve metrics for this file. radon emits the path as it was
        # passed on argv — typically the relative form.
        file_metrics: list[FunctionMetric] = []
        for radon_path, metrics in per_file_metrics.items():
            if radon_path == rel or radon_path.endswith(file_path.name):
                file_metrics = metrics
                break

        if used_radon:
            per_file_fn_count[rel] = len(file_metrics)
            total_function_count += len(file_metrics)
            file_warnings: list[FunctionMetric] = []
            for metric in file_metrics:
                bucket = _RANK_TO_BUCKET.get(metric.rank, "A")
                rank_histogram[bucket] += 1
                weighted_complexity_sum += _RANK_MIDPOINT.get(bucket, 2.5)
                if metric.rank in _WARNING_RANKS:
                    file_warnings.append(metric)
                    warning_count += 1
            per_file_warnings[rel] = file_warnings
        else:
            per_file_fn_count[rel] = _count_functions(file_path)
            total_function_count += per_file_fn_count[rel]
            per_file_warnings[rel] = []

    avg_complexity = (
        weighted_complexity_sum / total_function_count if total_function_count > 0 else 0.0
    )

    return CompressorHealth(
        file_count=len(files),
        total_loc=total_loc,
        total_function_count=total_function_count,
        rank_histogram=rank_histogram,
        warning_count=warning_count,
        avg_complexity_estimate=round(avg_complexity, 2),
        per_file_loc=dict(per_file_loc),
        per_file_function_count=dict(per_file_fn_count),
        per_file_warning_findings=dict(per_file_warnings),
        used_radon=used_radon,
    )


def render_markdown_report(health: CompressorHealth) -> str:
    """Render :class:`CompressorHealth` as a stable local-measurement report.

    The six-section shape is retained for historical readers, while current
    artifacts route with built-in harness and local research evidence.

    Args:
      health: Aggregated metrics from
        :func:`compute_health_summary`.

    Returns:
      Markdown string ready to write to
      ``.local/research/v<cycle>_compressor_health.md``.
    """
    fallback_note = (
        " *(degraded local measurement — radon unavailable; rank histogram"
        " and warning count omitted, LOC + function-count stats only)*"
        if not health.used_radon
        else ""
    )
    delta_avg_str = (
        f"{health.avg_complexity_estimate - V9_3_0_BASELINE_AVG_COMPLEXITY:+.2f}"
        if health.used_radon
        else "n/a"
    )
    delta_warn_str = (
        f"{health.warning_count - V9_3_0_BASELINE_WARNING_COUNT:+d}" if health.used_radon else "n/a"
    )

    lines: list[str] = [
        "# Compressor Health Snapshot",
        "",
        "> Generated from deterministic repository-local measurements by",
        "> `scripts/snapshot_compressor_health.py`.",
        f">{fallback_note}" if fallback_note else "",
        "",
        "## §1 — Per-package summary",
        "",
        (
            "| Package | Files | Total LOC | Functions | Avg complexity (est.) | "
            "Warning-class (CC > 10) | Top severity |"
        ),
        "|---|---:|---:|---:|---:|---:|---|",
        (
            f"| `src/devolaflow/compressor/` | {health.file_count} | "
            f"{health.total_loc} | {health.total_function_count} | "
            f"{health.avg_complexity_estimate} | {health.warning_count} | "
            f"{_max_severity(health)} |"
        ),
        "",
        "Legacy comparison vs v9.3.0 PV-04 pre-split baseline "
        "(`.local/research/v9.3.0_nines_compressor.json`, historical only):",
        "",
        f"- Avg complexity: v9.3.0 = {V9_3_0_BASELINE_AVG_COMPLEXITY} → "
        f"current = {health.avg_complexity_estimate} (Δ {delta_avg_str})",
        f"- Warning-class count: v9.3.0 = {V9_3_0_BASELINE_WARNING_COUNT} → "
        f"current = {health.warning_count} (Δ {delta_warn_str})",
        "",
        "## §2 — Top findings (severity-sorted, warning-class only)",
        "",
    ]

    # Flatten warning findings across files, sort by rank desc.
    all_warnings: list[FunctionMetric] = []
    for warnings in health.per_file_warning_findings.values():
        all_warnings.extend(warnings)
    all_warnings.sort(key=lambda m: (-_RANK_MIDPOINT[m.rank], m.file, m.line))

    if not all_warnings:
        lines.append(
            "_No warning-class CC findings (CC > 10) in the post-split "
            "compressor package — the v9.3.0 PV-04 4-way decomposition "
            "remains structurally healthy._"
        )
    else:
        lines.append("| File | Line | Function | Rank | Severity bucket |")
        lines.append("|---|---:|---|:---:|---|")
        for metric in all_warnings:
            lines.append(
                f"| `{metric.file}` | {metric.line} | "
                f"`{metric.name}` | {metric.rank} | "
                f"{_severity_label(metric.rank)} |"
            )

    lines.extend(
        [
            "",
            "## §3 — Keypoints (per-file)",
            "",
        ]
    )
    for rel_path, loc in health.per_file_loc.items():
        fn_count = health.per_file_function_count.get(rel_path, 0)
        warning_total = len(health.per_file_warning_findings.get(rel_path, []))
        warn_str = (
            f"{warning_total} warning-class finding(s)"
            if health.used_radon and warning_total > 0
            else (
                "no warning-class findings" if health.used_radon else "n/a (degraded measurement)"
            )
        )
        lines.append(f"- **`{rel_path}`** — {loc} LOC, {fn_count} functions; {warn_str}.")

    lines.extend(
        [
            "",
            "## §4 — Deterministic health summary",
            "",
            "| Package | Warning ratio | Avg CC (est.) | Synthesis score (informal) |",
            "|---|---:|---:|---:|",
        ]
    )
    if health.total_function_count > 0:
        warn_ratio = (
            f"{(health.warning_count / health.total_function_count) * 100:.1f}%"
            if health.used_radon
            else "n/a"
        )
        synth = _informal_synthesis_score(health)
        lines.append(f"| compressor | {warn_ratio} | {health.avg_complexity_estimate} | {synth} |")

    lines.extend(
        [
            "",
            "## §5 — Findings flagged for follow-up",
            "",
        ]
    )
    if not all_warnings:
        lines.append("_No follow-up candidates surfaced from the current local measurements._")
    else:
        for metric in all_warnings[:10]:
            lines.append(
                f"- PV candidate — `{metric.file}:{metric.line}` "
                f"`{metric.name}` rank {metric.rank} → propose helper "
                "extraction and verify it with focused tests."
            )

    lines.extend(
        [
            "",
            "## §6 — References",
            "",
            "- Current source: `src/devolaflow/compressor/`",
            "- Current verification: `tests/test_compressor.py`",
            "- Legacy baseline: `.local/research/v9.3.0_nines_compressor.json`",
            "- External tools (S-7): radon https://radon.readthedocs.io/",
            "",
        ]
    )
    return "\n".join(lines)


def _max_severity(health: CompressorHealth) -> str:
    """Return the highest-severity bucket present (or "info" when empty)."""
    if not health.used_radon:
        return "n/a (degraded measurement)"
    for rank in ("F", "E", "D", "C"):
        if health.rank_histogram.get(rank, 0) > 0:
            return f"warning ×{health.rank_histogram[rank]} ({rank})"
    return "info (no warnings)"


def _severity_label(rank: str) -> str:
    """Map radon rank → human-readable severity label."""
    return {
        "C": "warning",
        "D": "warning+",
        "E": "high",
        "F": "very high",
    }.get(rank, "low")


def _informal_synthesis_score(health: CompressorHealth) -> str:
    """Compute a deterministic local summary score from warning count.

    This is a quick-glance heuristic, not an SI-3 verdict. Ten means no
    warnings; subtract 0.5 per warning, capped at 5.0. The degraded path
    returns ``"n/a"``.
    """
    if not health.used_radon:
        return "n/a"
    score = max(5.0, 10.0 - (health.warning_count * 0.5))
    return f"{score:.1f}/10 (local heuristic)"


def run(
    repo_root: Path,
    *,
    package: str = DEFAULT_COMPRESSOR_PACKAGE,
    json_out: bool = False,
    verbose: bool = False,
    output: Path | None = None,
) -> int:
    """Entry-point — scan compressor package, run radon, emit health snapshot.

    Args:
      repo_root: Repository root (defaults to ``Path.cwd()`` from CLI).
      package: Package directory to analyse (default
        ``src/devolaflow/compressor``).
      json_out: When True, emit JSON to stdout instead of markdown.
      verbose: When True, prints each file as it scans.
      output: When set, write markdown / JSON to this file.

    Returns:
      ``0`` on success (always 0 — the audit is observability-only;
      a missing package directory is reported as an empty audit, not
      an error).
    """
    files = scan_compressor_files(repo_root, package)
    if verbose:
        print(f"[snapshot_compressor_health] scanned {len(files)} files", file=sys.stderr)
        for path in files:
            print(f"  - {path}", file=sys.stderr)

    raw, used_radon = run_radon_cc(files, repo_root=repo_root)
    per_file_metrics = parse_radon_cc(raw)
    health = compute_health_summary(
        files, per_file_metrics, used_radon=used_radon, repo_root=repo_root
    )

    if json_out:
        body = json.dumps(
            {
                "file_count": health.file_count,
                "total_loc": health.total_loc,
                "total_function_count": health.total_function_count,
                "rank_histogram": health.rank_histogram,
                "warning_count": health.warning_count,
                "avg_complexity_estimate": health.avg_complexity_estimate,
                "per_file_loc": health.per_file_loc,
                "per_file_function_count": health.per_file_function_count,
                "per_file_warning_findings": {
                    rel: [
                        {
                            "line": m.line,
                            "name": m.name,
                            "rank": m.rank,
                            "sigil": m.sigil,
                        }
                        for m in metrics
                    ]
                    for rel, metrics in health.per_file_warning_findings.items()
                },
                "used_radon": health.used_radon,
                "v9_3_0_baseline": {
                    "avg_complexity": V9_3_0_BASELINE_AVG_COMPLEXITY,
                    "warning_count": V9_3_0_BASELINE_WARNING_COUNT,
                },
            },
            indent=2,
            sort_keys=True,
        )
    else:
        body = render_markdown_report(health)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")
        if verbose:
            print(f"[snapshot_compressor_health] wrote {output}", file=sys.stderr)
    else:
        print(body)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — parse args, dispatch to :func:`run`."""
    parser = argparse.ArgumentParser(
        description="Snapshot deterministic local health metrics for the compressor package.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current working directory).",
    )
    parser.add_argument(
        "--package",
        type=str,
        default=DEFAULT_COMPRESSOR_PACKAGE,
        help=f"Package to analyse (default: {DEFAULT_COMPRESSOR_PACKAGE}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of markdown.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=("Write the report to this file instead of stdout (parents auto-created)."),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print scan progress to stderr.",
    )
    args = parser.parse_args(argv)
    return run(
        args.repo_root,
        package=args.package,
        json_out=args.json,
        verbose=args.verbose,
        output=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
