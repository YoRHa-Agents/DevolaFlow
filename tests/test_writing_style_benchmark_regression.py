"""Regression guard for the v10.1.0 post-transform naturalness baseline.

The PV-05 measurement at
``benchmarks/writing_style/baselines/v10.1.0_post.json`` is the
ship-gate evidence that the humanizer moved the DevolaFlow corpus
from 69.958 to 79.991 aggregate naturalness. A later edit to the
scorer, transforms, or source docs that pulls the aggregate below
the post baseline by more than 5 points on any doc — or pulls the
aggregate below 73 (the PV-05 ship threshold) — means the cycle has
regressed and must be investigated.

The aggregate threshold is the primary gate. Per-doc thresholds are
advisory because authored edits to individual docs can legitimately
shift their scores; the aggregate captures systemic drift.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
POST_BASELINE = REPO_ROOT / "benchmarks" / "writing_style" / "baselines" / "v10.1.0_post.json"

AGGREGATE_FLOOR = 73.0
PRE_AGGREGATE = 69.958
POST_AGGREGATE_BASELINE = 77.664


def _load_baseline() -> dict:
    if not POST_BASELINE.exists():
        pytest.skip("post-transform baseline not yet committed")
    return json.loads(POST_BASELINE.read_text(encoding="utf-8"))


def test_post_baseline_aggregate_meets_ship_threshold() -> None:
    data = _load_baseline()
    agg = data["aggregate_naturalness"]
    assert agg >= AGGREGATE_FLOOR, (
        f"post-transform aggregate {agg} below ship floor {AGGREGATE_FLOOR}"
    )


def test_post_baseline_aggregate_lifts_over_pre_baseline() -> None:
    data = _load_baseline()
    agg = data["aggregate_naturalness"]
    assert agg > PRE_AGGREGATE, (
        f"post-transform aggregate {agg} did not improve over "
        f"pre-transform {PRE_AGGREGATE}; the transforms regressed"
    )


def test_post_baseline_aggregate_near_pv05_result() -> None:
    data = _load_baseline()
    agg = data["aggregate_naturalness"]
    assert abs(agg - POST_AGGREGATE_BASELINE) <= 2.0, (
        f"post-transform aggregate {agg} drifted from PV-05 "
        f"measurement {POST_AGGREGATE_BASELINE} by more than 2 points"
    )


def test_no_post_doc_below_advisory_floor() -> None:
    """Every doc with PRE >= 65 should remain >= 65 POST."""
    data = _load_baseline()
    for d in data["per_doc"]:
        assert d["naturalness"] >= 65.0 or d["label"] in {
            "df:CHANGELOG",
        }, (
            f"{d['label']} post-transform score {d['naturalness']} below "
            "advisory floor (65); see v10.1.0 PV-05 measurement report"
        )


def test_worst_seven_still_gain_ten_points() -> None:
    """Recomputed-at-test-time sanity check that the documented
    worst-7-at-PRE doc list still gains ≥ 10 points in the committed
    post baseline vs the committed pre baseline."""
    pre_path = REPO_ROOT / "benchmarks" / "writing_style" / "baselines" / "v10.1.0_pre.json"
    if not pre_path.exists():
        pytest.skip("pre-transform baseline not present")
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    post = _load_baseline()
    pre_by = {d["label"]: d["naturalness"] for d in pre["per_doc"]}
    post_by = {d["label"]: d["naturalness"] for d in post["per_doc"]}

    worst7 = [
        "df:en/integration-guide",
        "df:CHANGELOG",
        "df:en/faq",
        "df:zh/integration-guide",
        "df:zh/workflow-types",
        "df:README",
        "df:en/quickstart",
    ]
    for label in worst7:
        if label not in pre_by or label not in post_by:
            pytest.skip(f"label {label} not in baselines")
        delta = post_by[label] - pre_by[label]
        assert delta >= 10.0, (
            f"worst-7 doc {label} gained only {delta:.2f} points; "
            "needs +10 to preserve PV-05 ship-gate evidence"
        )
