"""Tests for the built-in harness evaluator rosetta generator.

Pins the 6 × 9 rosetta invariants:

* The cell matrix is exactly 6 rows × 9 columns.
* The columns are the nine built-in harness signal bundles.
* Every dimension has at least one canonical C-cell.
* SI-3 dimension weights sum to 1.0.
* The CSV / markdown / JSON renderers all produce non-empty,
  parseable output that round-trips to the same shape.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
from pathlib import Path


def _load_rosetta_module() -> object:
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "generate_evaluator_rosetta.py"
    name = "generate_evaluator_rosetta"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_ROSETTA = _load_rosetta_module()


def test_table_shape_is_6_by_9() -> None:
    """The rosetta is six SI-3 dimensions by nine harness bundles."""
    assert len(_ROSETTA.SI3_DIMENSIONS) == 6
    assert _ROSETTA.COLUMNS == (
        "Harness code hygiene",
        "Harness test execution",
        "Harness coverage",
        "Harness layout invariant",
        "Harness compatibility",
        "Harness W-17 test growth",
        "Harness docstring coverage",
        "Harness constraint quantifiability",
        "Harness token budget",
    )
    assert len(_ROSETTA.CELLS) == 6
    for idx, row in enumerate(_ROSETTA.CELLS):
        assert len(row) == 9, f"row {idx} has {len(row)} cells"


def test_si3_weights_sum_to_one() -> None:
    """SI-3 weighted composite formula requires sum-to-one."""
    weight_sum = sum(weight for _, weight in _ROSETTA.SI3_DIMENSIONS)
    assert abs(weight_sum - 1.0) < 1e-6, f"weights sum {weight_sum} != 1.0"


def test_every_dim_has_at_least_one_canonical_cell() -> None:
    """Every SI-3 dim MUST have ≥ 1 C-cell (a canonical authority).

    The rosetta is a reading aid; a dimension without a C-cell has no
    documented built-in signal authority.
    """
    for (dim_name, _), row in zip(_ROSETTA.SI3_DIMENSIONS, _ROSETTA.CELLS, strict=True):
        canonical_count = sum(1 for c in row if c == "C")
        assert canonical_count >= 1, (
            f"SI-3 dim {dim_name!r} has 0 C-cells — missing canonical authority"
        )


def test_render_csv_round_trips_through_csv_reader() -> None:
    """CSV output must be parseable + carry exactly one row per cell."""
    body = _ROSETTA.render_csv()
    reader = csv.reader(io.StringIO(body))
    rows = list(reader)
    # Header + 54 cells (6 dims × 9 columns).
    assert len(rows) == 1 + 54
    header = rows[0]
    assert header == ["si3_dim", "si3_weight", "column", "code", "is_canonical"]
    canonical_marked = sum(1 for r in rows[1:] if r[4] == "true")
    canonical_in_cells = sum(1 for row in _ROSETTA.CELLS for c in row if c == "C")
    assert canonical_marked == canonical_in_cells


def test_render_json_carries_summary_block() -> None:
    """JSON output carries a summary block + the C / O / . counts agree."""
    body = _ROSETTA.render_json()
    payload = json.loads(body)
    summary = payload["summary"]
    expected_canonical = sum(1 for row in _ROSETTA.CELLS for c in row if c == "C")
    expected_overlap = sum(1 for row in _ROSETTA.CELLS for c in row if c == "O")
    expected_orthogonal = sum(1 for row in _ROSETTA.CELLS for c in row if c == ".")
    assert summary["canonical_cell_count"] == expected_canonical
    assert summary["overlap_cell_count"] == expected_overlap
    assert summary["orthogonal_cell_count"] == expected_orthogonal
    assert summary["row_count"] == 6
    assert summary["column_count"] == 9
    assert payload["columns"] == list(_ROSETTA.COLUMNS)
    # Sanity: total cells equals 54.
    assert (
        summary["canonical_cell_count"]
        + summary["overlap_cell_count"]
        + summary["orthogonal_cell_count"]
        == 54
    )
