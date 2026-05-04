#!/usr/bin/env python3
"""Emit the canonical 6 × 9 evaluator rosetta as machine-consumable CSV / markdown.

Implements the v10.7.0 D-O-1 companion deliverable per
`.local/research/v11.0.0_patches/D-O-1.md`. The script is the
machine-readable counterpart to
``workflow-system/agent/references/evaluator-rosetta.md`` §3:

* The reference (markdown, human-facing) is the **source of truth** for
  per-cell justification prose + verbatim citations.
* This script (CSV, machine-facing) is the **sanity-check artifact** —
  operators run it during cycle close to confirm the rosetta cells
  haven't drifted relative to the reference (e.g., a future PR that
  edits §3 without refreshing the script would surface a diff).

Algorithm (per PDS §2 + §6 admission verdict):

1. Encode the 6 × 9 cell table as a Python data structure (rows = SI-3
   dims; columns = NineS hygiene + capability sub-bundles + Si-Chip).
2. Render as CSV (``--csv``, default), markdown table (``--markdown``),
   or JSON (``--json``).
3. The output may be written to ``--output PATH`` or stdout.
4. The script is **DERIVATIVE-ONLY**: the reference is canonical. If the
   reference is updated, this script's data structure MUST be updated in
   the same PR — enforced by the W-18 ghost-audit refresh
   (``tests/test_no_ghost_features.py::test_v10_7_0_new_symbols_have_coverage``).

Public API:

* :data:`SI3_DIMENSIONS` -- the 6 dimension names + weights.
* :data:`COLUMNS` -- the 9 column labels.
* :data:`CELLS` -- a 6 × 9 list-of-lists with cell codes ('C', 'O', '·').
* :func:`render_csv()` -> str
* :func:`render_markdown()` -> str
* :func:`render_json()` -> str
* :func:`run(format, output)` -> int

Entry point: ``python scripts/generate_evaluator_rosetta.py
[--csv | --markdown | --json] [--output PATH]``

Source: v10.7.0 D-O-1 — codified per
`.local/research/v11.0.0_patches/D-O-1.md` §2.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "CELLS",
    "COLUMNS",
    "CellCode",
    "RosettaCell",
    "SI3_DIMENSIONS",
    "render_csv",
    "render_json",
    "render_markdown",
    "run",
]

# Cell codes per evaluator-rosetta.md §3 legend.
#   C = canonical authority for the row dim's quantitative sub-component
#   O = overlaps (related but not authoritative)
#   . = orthogonal (not cited under this row)
CellCode = str  # one of {"C", "O", "."}

# 6 SI-3 dimensions (rows) — per W-3 weighted composite.
SI3_DIMENSIONS: tuple[tuple[str, float], ...] = (
    ("Code quality", 0.20),
    ("Architecture rationality", 0.20),
    ("Test adequacy", 0.20),
    ("Maintainability", 0.15),
    ("Compatibility", 0.10),
    ("Performance impact", 0.15),
)

# 9 columns: 5 NineS hygiene + 3 NineS capability sub-bundles + Si-Chip.
COLUMNS: tuple[str, ...] = (
    "NineS code_coverage",
    "NineS lint_cleanliness",
    "NineS docstring_coverage",
    "NineS test_count",
    "NineS module_count",
    "NineS cap.scoring/eval",
    "NineS cap.decomp/abstract",
    "NineS cap.infra/sandbox",
    "Si-Chip iteration_delta",
)

# 6 × 9 cell matrix — must mirror evaluator-rosetta.md §3 verbatim.
# Edit this table only when you also edit the reference's §3 in the
# same PR (W-18 ghost-audit precondition).
CELLS: tuple[tuple[CellCode, ...], ...] = (
    # Code quality
    ("O", "C", "O", ".", ".", ".", "O", ".", "O"),
    # Architecture rationality
    (".", ".", ".", ".", "O", ".", "C", "O", "O"),
    # Test adequacy
    ("C", ".", ".", "C", ".", "O", ".", "O", "."),
    # Maintainability
    (".", "O", "C", ".", "O", ".", "O", ".", "."),
    # Compatibility
    (".", ".", ".", ".", ".", ".", ".", "C", "."),
    # Performance impact
    (".", ".", ".", ".", ".", "O", ".", "O", "C"),
)


@dataclass(frozen=True)
class RosettaCell:
    """One cell in the 6 × 9 rosetta table."""

    si3_dim: str
    si3_weight: float
    column: str
    code: CellCode  # 'C' | 'O' | '.'

    @property
    def is_canonical(self) -> bool:
        return self.code == "C"

    @property
    def is_orthogonal(self) -> bool:
        return self.code == "."


def _flatten_cells() -> list[RosettaCell]:
    """Flatten the 6 × 9 matrix into a list of :class:`RosettaCell`."""
    out: list[RosettaCell] = []
    for (dim_name, weight), row in zip(SI3_DIMENSIONS, CELLS, strict=True):
        for col_name, code in zip(COLUMNS, row, strict=True):
            out.append(
                RosettaCell(
                    si3_dim=dim_name,
                    si3_weight=weight,
                    column=col_name,
                    code=code,
                )
            )
    return out


def _validate_table_shape() -> None:
    """Pin the 6 × 9 invariant + raise on any drift."""
    assert len(SI3_DIMENSIONS) == 6, (
        f"SI-3 dimensions must be exactly 6 (W-3 weighted formula); got {len(SI3_DIMENSIONS)}"
    )
    assert len(COLUMNS) == 9, f"rosetta columns must be exactly 9 (D-O-1 §3); got {len(COLUMNS)}"
    assert len(CELLS) == len(SI3_DIMENSIONS), (
        f"CELLS row count {len(CELLS)} != SI-3 dim count {len(SI3_DIMENSIONS)}"
    )
    for idx, row in enumerate(CELLS):
        assert len(row) == len(COLUMNS), (
            f"CELLS row {idx} has {len(row)} cells; expected {len(COLUMNS)}"
        )
        for cell_idx, code in enumerate(row):
            assert code in {"C", "O", "."}, (
                f"CELLS[{idx}][{cell_idx}] = {code!r}; expected one of C / O / ."
            )
    weight_sum = sum(weight for _, weight in SI3_DIMENSIONS)
    assert abs(weight_sum - 1.0) < 1e-6, (
        f"SI-3 dimension weights must sum to 1.0; got {weight_sum}"
    )


def render_csv() -> str:
    """Render the rosetta as CSV (one row per cell)."""
    _validate_table_shape()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["si3_dim", "si3_weight", "column", "code", "is_canonical"])
    for cell in _flatten_cells():
        writer.writerow(
            [
                cell.si3_dim,
                f"{cell.si3_weight:.2f}",
                cell.column,
                cell.code,
                "true" if cell.is_canonical else "false",
            ]
        )
    return buf.getvalue()


def render_markdown() -> str:
    """Render the rosetta as a markdown table mirroring `evaluator-rosetta.md` §3."""
    _validate_table_shape()
    lines: list[str] = []
    lines.append("# Evaluator Rosetta — 6 × 9 Cell Table (machine-rendered sanity check)")
    lines.append("")
    lines.append(
        "This table is the machine-rendered counterpart of "
        "`workflow-system/agent/references/evaluator-rosetta.md` §3. "
        "If this output drifts from the reference, refresh BOTH in the "
        "same PR (W-18 ghost-audit precondition)."
    )
    lines.append("")
    header = "| SI-3 dim ↓ | " + " | ".join(COLUMNS) + " |"
    lines.append(header)
    lines.append("|---|" + "|".join([":---:"] * len(COLUMNS)) + "|")
    for (dim_name, weight), row in zip(SI3_DIMENSIONS, CELLS, strict=True):
        cells = " | ".join(
            "**C**" if c == "C" else c if c == "O" else "·" for c in row
        )
        lines.append(f"| **{dim_name} ({weight:.2f})** | {cells} |")
    lines.append("")
    lines.append("**Cell legend:**")
    lines.append("")
    lines.append("- **C** = canonical authority for the row dim (use verbatim).")
    lines.append("- O = overlaps (related but not authoritative).")
    lines.append("- · = orthogonal (do not cite).")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_json() -> str:
    """Render the rosetta as JSON (the most machine-consumable form)."""
    _validate_table_shape()
    payload = {
        "si3_dimensions": [
            {"name": name, "weight": weight} for name, weight in SI3_DIMENSIONS
        ],
        "columns": list(COLUMNS),
        "cells": [list(row) for row in CELLS],
        "summary": {
            "row_count": len(SI3_DIMENSIONS),
            "column_count": len(COLUMNS),
            "canonical_cell_count": sum(
                1 for row in CELLS for code in row if code == "C"
            ),
            "overlap_cell_count": sum(
                1 for row in CELLS for code in row if code == "O"
            ),
            "orthogonal_cell_count": sum(
                1 for row in CELLS for code in row if code == "."
            ),
        },
    }
    return json.dumps(payload, indent=2)


def run(*, format: str, output: Path | None) -> int:
    """Top-level driver — emit the rosetta in the requested format."""
    renderers = {
        "csv": render_csv,
        "markdown": render_markdown,
        "json": render_json,
    }
    body = renderers[format]()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"[rosetta] wrote {output}")
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--csv", action="store_const", dest="format", const="csv")
    fmt.add_argument(
        "--markdown",
        action="store_const",
        dest="format",
        const="markdown",
    )
    fmt.add_argument("--json", action="store_const", dest="format", const="json")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    fmt_choice = args.format or "csv"
    return run(format=fmt_choice, output=args.output)


if __name__ == "__main__":
    sys.exit(main())
