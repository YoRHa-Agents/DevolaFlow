"""Doctrine pins for schemas/lean-report.yaml metrics (v14.2.1 G-013).

Closes G-013 from `.local/research/v14.2.0_gap_analysis.md` §2.3 (source
finding F-P4-3): the lean StatusReport spec used to define
``metrics.quality``, contradicting the SKILL.md / task-quality-score.md
doctrine "Subagent reports DO NOT include `quality_score` (L0-only)".

Pinned contract:

* The metrics field is named ``gate_input_score`` — gate-dimension input
  evidence — in the lean spec, the lean example, AND the verbose
  original example. Neither ``quality`` nor ``quality_score`` may
  reappear in any report-metrics block of this file.
* The schema carries the doctrine note distinguishing the field from the
  L0-only Task Quality Score (``references/task-quality-score.md``).

The ``reject_subagent_quality_score`` pre_dispatch hook keeps checking
only the TOP-LEVEL ``quality_score`` key (strict graduation is a later
rung); these pins are schema-side only.
"""

from __future__ import annotations

from pathlib import Path

import yaml

LEAN_REPORT_PATH = Path(__file__).resolve().parent.parent / "schemas" / "lean-report.yaml"


def test_report_metrics_use_gate_input_score_not_quality() -> None:
    """All three metrics blocks carry gate_input_score; quality* is gone."""
    doc = yaml.safe_load(LEAN_REPORT_PATH.read_text(encoding="utf-8"))

    spec_fields = doc["lean_format_spec"]["metrics"]["fields"]
    lean_metrics = doc["lean_example"]["metrics"]
    original_metrics = doc["original_example"]["result"]["metrics"]

    for label, block in (
        ("lean_format_spec.metrics.fields", spec_fields),
        ("lean_example.metrics", lean_metrics),
        ("original_example.result.metrics", original_metrics),
    ):
        assert "gate_input_score" in block, (
            f"G-013 regression: {label} is missing `gate_input_score` "
            f"(the v14.2.1 rename of the doctrine-violating `quality` field)."
        )
        assert "quality" not in block and "quality_score" not in block, (
            f"G-013 regression: {label} carries a quality/quality_score key — "
            f"subagent reports DO NOT include a quality score "
            f"(L0-only per references/task-quality-score.md)."
        )


def test_report_metrics_doctrine_note_present() -> None:
    """The inline 'NOT the Task Quality Score' note ships with the rename."""
    text = LEAN_REPORT_PATH.read_text(encoding="utf-8")
    assert "NOT the Task Quality" in text, (
        "G-013 regression: lean-report.yaml lost the doctrine note "
        "'gate-dimension input evidence — NOT the Task Quality Score'."
    )
    assert "references/task-quality-score.md" in text, (
        "G-013 regression: the doctrine note must cite "
        "references/task-quality-score.md (the L0-only scoring rubric)."
    )
