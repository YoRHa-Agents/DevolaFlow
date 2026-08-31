"""Structured metric comparison helpers for harness telemetry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _observation_payload(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    from devolaflow.harness.telemetry import METRIC_OBSERVATION_EVENT, METRIC_OBSERVATION_FIELDS

    if candidate.get("event") == METRIC_OBSERVATION_EVENT:
        return {
            field: candidate[field] for field in METRIC_OBSERVATION_FIELDS if field in candidate
        }
    return candidate


def compare_metric_observations(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare one matched item using the approved reduction formula."""

    from devolaflow.harness.telemetry import (
        METRIC_OBSERVATION_MATCH_FIELDS,
        MetricObservationError,
        validate_metric_observation,
    )

    baseline_payload = _observation_payload(baseline) if isinstance(baseline, Mapping) else baseline
    current_payload = _observation_payload(current) if isinstance(current, Mapping) else current
    baseline_id = baseline_payload.get("item_id") if isinstance(baseline_payload, Mapping) else None
    current_id = current_payload.get("item_id") if isinstance(current_payload, Mapping) else None
    result: dict[str, Any] = {
        "item_id": baseline_id if baseline_id == current_id else baseline_id or current_id,
        "metric": baseline_payload.get("metric") if isinstance(baseline_payload, Mapping) else None,
        "baseline": (
            {"value": baseline_payload.get("value")}
            if isinstance(baseline_payload, Mapping)
            else None
        ),
        "current": (
            {"value": current_payload.get("value")}
            if isinstance(current_payload, Mapping)
            else None
        ),
        "matched": False,
        "status": "INSUFFICIENT",
    }
    try:
        baseline_record = validate_metric_observation(baseline_payload)
        current_record = validate_metric_observation(current_payload)
    except (MetricObservationError, AttributeError, TypeError) as exc:
        result["reason"] = f"invalid observation: {exc}"
        return result

    result["item_id"] = baseline_record["item_id"]
    result["metric"] = baseline_record["metric"]
    result["statistic"] = baseline_record["statistic"]
    result["baseline"] = {
        "value": baseline_record["value"],
        "unit": baseline_record["unit"],
        "provenance": _comparison_provenance(baseline_record),
    }
    result["current"] = {
        "value": current_record["value"],
        "unit": current_record["unit"],
        "provenance": _comparison_provenance(current_record),
    }
    mismatches = [
        field
        for field in METRIC_OBSERVATION_MATCH_FIELDS
        if baseline_record[field] != current_record[field]
    ]
    if mismatches:
        result["reason"] = f"measurement identity mismatch: {', '.join(mismatches)}"
        result["mismatched_fields"] = mismatches
        return result
    if baseline_record["value"] <= 0:
        result["reason"] = "baseline value must be positive"
        return result
    result["matched"] = True
    result["status"] = "AVAILABLE"
    result["relative_improvement_pct"] = (
        (baseline_record["value"] - current_record["value"]) / baseline_record["value"] * 100
    )
    return result


def _comparison_provenance(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_revision": observation["source_revision"],
        "command": observation["command"],
        "environment": observation["environment"],
        "measurement": observation["measurement"],
    }


def compare_metric_observation_sets(
    baseline: list[Mapping[str, Any]],
    current: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Pair observations by item and metric, marking absent pairs insufficient."""

    def keyed(records: list[Mapping[str, Any]]) -> dict[tuple[object, object], Mapping[str, Any]]:
        result: dict[tuple[object, object], Mapping[str, Any]] = {}
        for record in records:
            payload = _observation_payload(record) if isinstance(record, Mapping) else record
            key = (
                payload.get("item_id") if isinstance(payload, Mapping) else None,
                payload.get("metric") if isinstance(payload, Mapping) else None,
            )
            if key in result:
                from devolaflow.harness.telemetry import MetricObservationError

                raise MetricObservationError(f"duplicate metric observation pair: {key!r}")
            result[key] = record
        return result

    baseline_by_key = keyed(baseline)
    current_by_key = keyed(current)
    comparisons: list[dict[str, Any]] = []
    for key in sorted(set(baseline_by_key) | set(current_by_key), key=str):
        if key not in baseline_by_key or key not in current_by_key:
            present = baseline_by_key.get(key) or current_by_key.get(key)
            comparisons.append(
                {
                    "item_id": key[0],
                    "metric": key[1],
                    "matched": False,
                    "status": "INSUFFICIENT",
                    "reason": "baseline or current observation is absent",
                    "baseline": ({"value": present["value"]} if key in baseline_by_key else None),
                    "current": {"value": present["value"]} if key in current_by_key else None,
                }
            )
            continue
        comparisons.append(compare_metric_observations(baseline_by_key[key], current_by_key[key]))
    return comparisons
