#!/usr/bin/env python3
"""Reference doc utilization-rate audit.

Per `.local/research/v11.0.0_patches/D-D-1.md` §2 algorithm. Replays the
selector matrix `(task_type × round_num)` and aggregates how many cells
load each canonical reference via `extra_context`. Output is a markdown
report (or JSON via `--json`) consumed by D-A-2 / D-D-3 follow-on work.

Usage:
    python scripts/audit_reference_utilization.py
    python scripts/audit_reference_utilization.py --output report.md
    python scripts/audit_reference_utilization.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROUND_NUMS: tuple[int, ...] = (1, 2, 3, 4, 5)
REFERENCE_PATTERN = re.compile(r"references/([a-z0-9-]+)\.md")


@dataclass(frozen=True)
class CellResult:
    task_type: str
    round_num: int
    references: tuple[str, ...]


@dataclass(frozen=True)
class AuditReport:
    cells: tuple[CellResult, ...]
    cells_loaded: dict[str, int]
    cross_refs: dict[str, int]
    total_cells: int
    references_dir: Path

    @property
    def long_tail(self) -> list[str]:
        threshold = max(1, self.total_cells // 5)
        return sorted(r for r, n in self.cells_loaded.items() if n < threshold)


def _import_selector(repo_root: Path):
    sys.path.insert(0, str(repo_root / "src"))
    try:
        from devolaflow import task_adaptive_selector as tas
    finally:
        sys.path.pop(0)
    return tas


def list_task_types(profiles_path: Path) -> list[str]:
    """Use the YAML's profile keys as the canonical task-type set."""
    import yaml

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    profiles = raw.get("profiles", {})
    return sorted(profiles.keys())


def list_canonical_references(references_dir: Path) -> list[str]:
    return sorted(p.name for p in references_dir.glob("*.md"))


def replay_matrix(
    task_types: list[str],
    round_nums: tuple[int, ...],
    *,
    profiles_path: Path,
    selector,
) -> list[CellResult]:
    cells: list[CellResult] = []
    for task_type in task_types:
        for round_num in round_nums:
            try:
                ctx = selector.select_context(
                    task_type, profiles_path=profiles_path, round_num=round_num
                )
            except Exception as exc:  # pragma: no cover — explicit failure surface (S-5)
                print(
                    f"[audit] FAIL select_context({task_type!r}, round={round_num}): {exc}",
                    file=sys.stderr,
                )
                cells.append(CellResult(task_type, round_num, ()))
                continue
            extras = ctx.get("extra_context", []) or []
            refs = tuple(
                m.group(1) + ".md"
                for entry in extras
                for m in [REFERENCE_PATTERN.search(entry)]
                if m is not None
            )
            cells.append(CellResult(task_type, round_num, refs))
    return cells


def aggregate(cells: list[CellResult]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for cell in cells:
        for ref in cell.references:
            counter[ref] += 1
    return dict(counter)


def measure_cross_refs(references_dir: Path) -> dict[str, int]:
    """Count inbound `references/<x>.md` mentions per file."""
    counter: Counter[str] = Counter()
    files = list(references_dir.glob("*.md"))
    for ref_file in files:
        text = ref_file.read_text(encoding="utf-8")
        for match in REFERENCE_PATTERN.finditer(text):
            target = match.group(1) + ".md"
            if target == ref_file.name:
                continue
            counter[target] += 1
    return dict(counter)


def build_report(
    *,
    repo_root: Path,
    profiles_path: Path | None = None,
    round_nums: tuple[int, ...] = DEFAULT_ROUND_NUMS,
    selector_module=None,
) -> AuditReport:
    profiles_path = profiles_path or (repo_root / "workflow-system/agent/context_profiles.yaml")
    references_dir = repo_root / "workflow-system/agent/references"
    if selector_module is None:
        selector_module = _import_selector(repo_root)
    task_types = list_task_types(profiles_path)
    cells = replay_matrix(
        task_types, round_nums, profiles_path=profiles_path, selector=selector_module
    )
    canonical = list_canonical_references(references_dir)
    cells_loaded = {ref: 0 for ref in canonical}
    cells_loaded.update(aggregate(cells))
    cross_refs = measure_cross_refs(references_dir)
    return AuditReport(
        cells=tuple(cells),
        cells_loaded=cells_loaded,
        cross_refs=cross_refs,
        total_cells=len(cells),
        references_dir=references_dir,
    )


def render_markdown(report: AuditReport) -> str:
    lines: list[str] = []
    lines.append("# Reference Doc Utilization Audit")
    lines.append("")
    lines.append(
        f"- Total cells replayed: **{report.total_cells}** "
        f"({report.total_cells // len(DEFAULT_ROUND_NUMS) if DEFAULT_ROUND_NUMS else 0} "
        f"task types × {len(DEFAULT_ROUND_NUMS)} rounds)"
    )
    refs_scanned = len(list_canonical_references(report.references_dir))
    lines.append(f"- References scanned: **{refs_scanned}**")
    lines.append(f"- Long-tail (utilization < 20%): **{len(report.long_tail)}** references")
    lines.append("")
    lines.append("## Per-reference utilization")
    lines.append("")
    lines.append("| # | Reference | Cells loaded | % of cells | Inbound cross-refs | Disposition |")
    lines.append("|---|---|---:|---:|---:|---|")
    canonical = list_canonical_references(report.references_dir)
    rows = []
    for ref in canonical:
        loaded = report.cells_loaded.get(ref, 0)
        pct = (loaded / report.total_cells * 100) if report.total_cells else 0.0
        x_refs = report.cross_refs.get(ref, 0)
        if pct >= 50.0:
            disp = "KEEP — universal"
        elif pct >= 25.0:
            disp = "KEEP — moderate"
        elif pct >= 10.0:
            disp = "REVIEW — opt-in"
        else:
            disp = "CANDIDATE — long tail"
        rows.append((loaded, ref, pct, x_refs, disp))
    rows.sort(key=lambda r: (-r[0], r[1]))
    total = report.total_cells
    for i, (loaded, ref, pct, x_refs, disp) in enumerate(rows, 1):
        lines.append(
            f"| {i} | `references/{ref}` | {loaded}/{total} | {pct:.1f}% | {x_refs} | {disp} |"
        )
    lines.append("")
    lines.append("## Skipped sections by profile")
    lines.append("")
    skipped: Counter[str] = Counter()
    for cell in report.cells:
        if cell.round_num != 1:
            continue
        skipped[cell.task_type] += 0
    lines.append(
        "_Per-cell skipped-section detail surfaced via the verbose selector run; "
        "this audit pins reference-level utilization only._"
    )
    lines.append("")
    return "\n".join(lines)


def render_json(report: AuditReport) -> str:
    return json.dumps(
        {
            "total_cells": report.total_cells,
            "cells_loaded": report.cells_loaded,
            "cross_refs": report.cross_refs,
            "long_tail": report.long_tail,
            "matrix": [
                {
                    "task_type": c.task_type,
                    "round_num": c.round_num,
                    "references": list(c.references),
                }
                for c in report.cells
            ],
        },
        indent=2,
    )


def resolve_repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise SystemExit("could not locate repo root (no pyproject.toml)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args(argv)

    repo_root = args.repo_root or resolve_repo_root()
    report = build_report(repo_root=repo_root, profiles_path=args.profiles_path)
    body = render_json(report) if args.json else render_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
        print(f"[audit] wrote {args.output}")
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
