"""Historical companion comparison for the deterministic harness evaluator."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from devolaflow.harness.evaluation_contract import (
    DIMENSION_WEIGHTS,
    HISTORICAL_COMPANION_METHOD,
    EvaluationError,
)


def _score_vector(payload: Mapping[str, Any], *, label: str) -> dict[str, float]:
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, list):
        raise EvaluationError(f"{label}.scores must be a list")

    scores: dict[str, float] = {}
    for index, entry in enumerate(raw_scores):
        if not isinstance(entry, Mapping):
            raise EvaluationError(f"{label}.scores[{index}] must be an object")
        dimension = entry.get("id")
        if not isinstance(dimension, str) or not dimension:
            raise EvaluationError(f"{label}.scores[{index}].id must be a non-empty string")
        if dimension in scores:
            raise EvaluationError(f"{label}.scores contains duplicate id {dimension!r}")
        raw_score = entry.get("score")
        if (
            isinstance(raw_score, bool)
            or not isinstance(raw_score, (int, float))
            or not math.isfinite(float(raw_score))
            or not 0.0 <= float(raw_score) <= 10.0
        ):
            raise EvaluationError(
                f"{label}.scores[{index}].score must be a finite number in [0, 10]"
            )
        scores[dimension] = float(raw_score)

    expected = set(DIMENSION_WEIGHTS)
    actual = set(scores)
    if actual != expected:
        raise EvaluationError(
            f"{label}.scores ids must exactly match {list(DIMENSION_WEIGHTS)}; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    return scores


def _historical_provenance(companion: Mapping[str, Any]) -> dict[str, Any]:
    sampled_at = companion.get("sampled_at")
    if not isinstance(sampled_at, str) or not sampled_at.strip():
        raise EvaluationError("historical companion sampled_at must be a non-empty string")
    if companion.get("metric_count") != len(DIMENSION_WEIGHTS):
        raise EvaluationError(
            f"historical companion metric_count must equal {len(DIMENSION_WEIGHTS)}"
        )
    methodology = companion.get("methodology")
    if not isinstance(methodology, str) or not methodology.strip():
        raise EvaluationError("historical companion methodology must be a non-empty string")
    limitation = companion.get("limitation")
    if (
        not isinstance(limitation, str)
        or "not a raw NineS six-dimensional output" not in limitation
    ):
        raise EvaluationError(
            "historical companion limitation must state that it is "
            "not a raw NineS six-dimensional output"
        )

    raw_sources = companion.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise EvaluationError("historical companion sources must be a non-empty list")
    sources: list[dict[str, str]] = []
    for index, source in enumerate(raw_sources):
        if not isinstance(source, Mapping):
            raise EvaluationError(f"historical companion sources[{index}] must be an object")
        path = source.get("path")
        digest = source.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or path.startswith("~")
        ):
            raise EvaluationError(
                f"historical companion sources[{index}].path must be repository-relative"
            )
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise EvaluationError(
                f"historical companion sources[{index}].sha256 must be lowercase SHA-256"
            )
        sources.append({"path": path, "sha256": digest})

    source_context = companion.get("source_context")
    if source_context is not None and not isinstance(source_context, Mapping):
        raise EvaluationError("historical companion source_context must be an object")
    return {
        "sampled_at": sampled_at,
        "metric_count": len(DIMENSION_WEIGHTS),
        "methodology": methodology,
        "limitation": limitation,
        "sources": sources,
        "source_context": dict(source_context or {}),
    }


def compare_historical_companion(
    current: Mapping[str, Any],
    historical: Mapping[str, Any],
    *,
    max_abs_delta: float = 1.0,
) -> dict[str, Any]:
    """Compare a complete current W-3 result with a historical companion."""
    if not isinstance(current, Mapping):
        raise EvaluationError("current evaluation must be an object")
    if not isinstance(historical, Mapping):
        raise EvaluationError("historical companion must be an object")
    if (
        isinstance(max_abs_delta, bool)
        or not isinstance(max_abs_delta, (int, float))
        or not math.isfinite(float(max_abs_delta))
        or not 0.0 <= float(max_abs_delta) <= 10.0
    ):
        raise EvaluationError("max_abs_delta must be a finite number in [0, 10]")
    auto_fill_rate = current.get("auto_fill_rate")
    if (
        isinstance(auto_fill_rate, bool)
        or not isinstance(auto_fill_rate, (int, float))
        or float(auto_fill_rate) != 1.0
    ):
        raise EvaluationError("current evaluation auto_fill_rate must equal 1.0")
    if current.get("verdict") not in {"READY", "NOT_READY"}:
        raise EvaluationError("current evaluation verdict must be READY or NOT_READY")
    if historical.get("method") != HISTORICAL_COMPANION_METHOD:
        raise EvaluationError(
            f"historical companion method must equal {HISTORICAL_COMPANION_METHOD!r}"
        )

    current_scores = _score_vector(current, label="current evaluation")
    historical_scores = _score_vector(historical, label="historical companion")
    historical_provenance = _historical_provenance(historical)
    limit = float(max_abs_delta)
    comparisons: list[dict[str, Any]] = []
    for dimension in DIMENSION_WEIGHTS:
        current_score = current_scores[dimension]
        historical_score = historical_scores[dimension]
        delta = abs(current_score - historical_score)
        comparisons.append(
            {
                "id": dimension,
                "current_score": current_score,
                "historical_score": historical_score,
                "abs_delta": round(delta, 2),
                "within_limit": delta <= limit,
            }
        )

    current_provenance = current.get("provenance")
    if current_provenance is not None and not isinstance(current_provenance, Mapping):
        raise EvaluationError("current evaluation provenance must be an object when present")
    verdict = "PASS" if all(comparison["within_limit"] for comparison in comparisons) else "FAIL"
    return {
        "schema_version": 1,
        "method": "historical_w3_hybrid_cross_validation",
        "criterion": {"max_abs_delta_per_dimension": limit},
        "current": {
            "sampled_at": current.get("sampled_at"),
            "auto_fill_rate": 1.0,
            "verdict": current["verdict"],
            "provenance": dict(current_provenance or {}),
        },
        "historical": {
            "method": HISTORICAL_COMPANION_METHOD,
            **historical_provenance,
        },
        "comparisons": comparisons,
        "max_abs_delta": max(comparison["abs_delta"] for comparison in comparisons),
        "verdict": verdict,
    }


__all__ = ["compare_historical_companion"]
