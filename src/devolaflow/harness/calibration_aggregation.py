"""Aggregation and uncertainty calculations for CLI calibration results."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from devolaflow.harness.calibration_matrix import CALIBRATION_SCHEMA_VERSION
from devolaflow.harness.cli_probe import SUPPORTED_CHANNELS, TASK_CLASSES, ProbeSpec

PERCENTILE_MINIMUM_N = 2


def _values_for_latency(results: Sequence[Mapping[str, Any]]) -> list[float]:
    values: list[float] = []
    for result in results:
        execution = result.get("execution")
        if not isinstance(execution, Mapping):
            continue
        if execution.get("reason") not in {"completed", "nonzero_exit", "timeout"}:
            continue
        value = execution.get("wall_time_seconds")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            values.append(float(value))
    return values


def _percentiles(values: Sequence[float]) -> dict[str, Any]:
    if len(values) < PERCENTILE_MINIMUM_N:
        return {
            "status": "INSUFFICIENT",
            "observed_n": len(values),
            "p50": None,
            "p95": None,
        }
    ordered = sorted(values)
    return {
        "status": "AVAILABLE",
        "observed_n": len(values),
        "p50": ordered[math.ceil(0.50 * len(ordered)) - 1],
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1],
    }


def _wilson_interval(successes: int, total: int) -> list[float] | None:
    if total <= 0:
        return None
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return [centre - margin, centre + margin]


def _cell_summary(
    task_class: str,
    channel: str,
    arm: str,
    results: Sequence[Mapping[str, Any]],
    expected_n: int,
) -> dict[str, Any]:
    counts = {
        "n": len(results),
        "pass": sum(result.get("status") == "PASS" for result in results),
        "fail": sum(result.get("status") == "FAIL" for result in results),
        "insufficient": sum(result.get("status") == "INSUFFICIENT" for result in results),
    }
    complete = counts["n"] == expected_n and counts["insufficient"] == 0
    completed_n = counts["pass"] + counts["fail"]
    pass_rate = {
        "status": "AVAILABLE" if complete else "INSUFFICIENT",
        "value": counts["pass"] / completed_n if complete and completed_n else None,
        "ci95": _wilson_interval(counts["pass"], completed_n) if complete else None,
    }
    token_values = [
        usage["total_tokens"]
        for result in results
        if isinstance((usage := result.get("token_usage")), Mapping)
        and usage.get("status") == "AVAILABLE"
        and type(usage.get("total_tokens")) is int
    ]
    token_cost = {
        "status": "AVAILABLE" if complete and len(token_values) == expected_n else "INSUFFICIENT",
        "observed_n": len(token_values),
        "missing_n": expected_n - len(token_values),
        "mean": sum(token_values) / len(token_values) if token_values else None,
        "p50": _percentiles([float(value) for value in token_values])["p50"]
        if len(token_values) >= PERCENTILE_MINIMUM_N
        else None,
        "p95": _percentiles([float(value) for value in token_values])["p95"]
        if len(token_values) >= PERCENTILE_MINIMUM_N
        else None,
    }
    skill_values = [
        skill["value"]
        for result in results
        if isinstance((skill := result.get("skill_loaded")), Mapping)
        and skill.get("status") == "AVAILABLE"
        and type(skill.get("value")) is bool
    ]
    skill_loaded = {
        "status": "AVAILABLE" if complete and len(skill_values) == expected_n else "INSUFFICIENT",
        "observed_n": len(skill_values),
        "missing_n": expected_n - len(skill_values),
        "true": sum(skill_values),
        "false": len(skill_values) - sum(skill_values),
    }
    return {
        "task_class": task_class,
        "channel": channel,
        "arm": arm,
        "expected_n": expected_n,
        "counts": counts,
        "completeness_status": "AVAILABLE" if complete else "INSUFFICIENT",
        "pass_rate": pass_rate,
        "wall_time_seconds": _percentiles(_values_for_latency(results)),
        "token_cost": token_cost,
        "skill_loaded": skill_loaded,
        "artifact_paths": [
            result["metadata"]["artifact_path"]
            for result in results
            if isinstance(result.get("metadata"), Mapping)
            and isinstance(result["metadata"].get("artifact_path"), str)
        ],
    }


def _difference_ci(
    left_successes: int,
    left_n: int,
    right_successes: int,
    right_n: int,
) -> list[float] | None:
    if left_n <= 0 or right_n <= 0:
        return None
    left = left_successes / left_n
    right = right_successes / right_n
    standard_error = math.sqrt(left * (1 - left) / left_n + right * (1 - right) / right_n)
    margin = 1.959963984540054 * standard_error
    return [left - right - margin, left - right + margin]


def _arm_comparison(
    task_class: str,
    channel: str,
    on: Mapping[str, Any],
    off: Mapping[str, Any],
) -> dict[str, Any]:
    on_counts = on["counts"]
    off_counts = off["counts"]
    complete = (
        on["completeness_status"] == "AVAILABLE" and off["completeness_status"] == "AVAILABLE"
    )
    difference = {
        "status": "AVAILABLE" if complete else "INSUFFICIENT",
        "skill_on_minus_skill_off": (
            on["pass_rate"]["value"] - off["pass_rate"]["value"] if complete else None
        ),
        "ci95": (
            _difference_ci(
                on_counts["pass"],
                on_counts["pass"] + on_counts["fail"],
                off_counts["pass"],
                off_counts["pass"] + off_counts["fail"],
            )
            if complete
            else None
        ),
    }
    on_latency = on["wall_time_seconds"]
    off_latency = off["wall_time_seconds"]
    latency_available = on_latency["status"] == "AVAILABLE" and off_latency["status"] == "AVAILABLE"
    on_tokens = on["token_cost"]
    off_tokens = off["token_cost"]
    token_available = on_tokens["status"] == "AVAILABLE" and off_tokens["status"] == "AVAILABLE"
    return {
        "task_class": task_class,
        "channel": channel,
        "arms": ["skill-on", "skill-off"],
        "pass_rate_difference": difference,
        "wall_time_p50_difference_seconds": {
            "status": "AVAILABLE" if latency_available else "INSUFFICIENT",
            "skill_on_minus_skill_off": (
                on_latency["p50"] - off_latency["p50"] if latency_available else None
            ),
            "uncertainty": "p50 only; no CI computed",
        },
        "token_cost_difference": {
            "status": "AVAILABLE" if token_available else "INSUFFICIENT",
            "skill_on_minus_skill_off": (
                on_tokens["mean"] - off_tokens["mean"] if token_available else None
            ),
            "uncertainty": "observed usage only; no estimate for missing tokens",
        },
    }


def aggregate_calibration_results(
    results: Sequence[Mapping[str, Any]],
    *,
    planned_specs: Sequence[ProbeSpec],
    run_id: str,
) -> dict[str, Any]:
    """Aggregate one result per planned spec into ordered cell summaries."""

    expected_by_cell: dict[tuple[str, str, str], int] = defaultdict(int)
    for spec in planned_specs:
        expected_by_cell[(spec.task_class, spec.channel, spec.arm)] += 1
    result_by_cell: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for result in results:
        key = (str(result.get("task_class")), str(result.get("channel")), str(result.get("arm")))
        result_by_cell[key].append(result)

    cells: list[dict[str, Any]] = []
    for spec in planned_specs:
        key = (spec.task_class, spec.channel, spec.arm)
        if any(
            cell["task_class"] == spec.task_class
            and cell["channel"] == spec.channel
            and cell["arm"] == spec.arm
            for cell in cells
        ):
            continue
        cells.append(
            _cell_summary(
                *key,
                result_by_cell[key],
                expected_by_cell[key],
            )
        )
    by_key = {(cell["task_class"], cell["channel"], cell["arm"]): cell for cell in cells}
    comparisons = [
        _arm_comparison(
            task_class,
            channel,
            by_key[(task_class, channel, "skill-on")],
            by_key[(task_class, channel, "skill-off")],
        )
        for task_class in TASK_CLASSES
        for channel in SUPPORTED_CHANNELS
        if (task_class, channel, "skill-on") in by_key
        and (task_class, channel, "skill-off") in by_key
    ]
    counts = {
        "planned": len(planned_specs),
        "observed": len(results),
        "completed": sum(result.get("status") in {"PASS", "FAIL"} for result in results),
        "pass": sum(result.get("status") == "PASS" for result in results),
        "fail": sum(result.get("status") == "FAIL" for result in results),
        "insufficient": sum(result.get("status") == "INSUFFICIENT" for result in results),
        "unrecorded": len(planned_specs) - len(results),
    }
    all_cells_complete = all(cell["completeness_status"] == "AVAILABLE" for cell in cells) and len(
        cells
    ) == len(expected_by_cell)
    token_observable = all(cell["token_cost"]["status"] == "AVAILABLE" for cell in cells)
    skill_observable = all(cell["skill_loaded"]["status"] == "AVAILABLE" for cell in cells)
    roi_status = (
        "AVAILABLE"
        if all_cells_complete and token_observable and skill_observable
        else "INSUFFICIENT"
    )
    roi = {
        "status": roi_status,
        "conclusion": (
            "Observed arm differences are eligible for ROI interpretation only when "
            "all cells are complete and token/skill telemetry is available."
            if roi_status == "AVAILABLE"
            else "INSUFFICIENT: incomplete cells or missing token/skill telemetry prevent a "
            "reproducible ROI claim. No causal quality improvement is established."
        ),
        "quality_causality": "NOT_ESTABLISHED",
        "uncertainty": (
            "95% Wilson intervals for complete pass-rate cells; normal-approximation "
            "difference intervals; latency and token differences retain explicit limitations."
        ),
        "token_cost": "AVAILABLE" if token_observable else "INSUFFICIENT",
        "skill_loaded": "AVAILABLE" if skill_observable else "INSUFFICIENT",
    }
    return {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "run_id": run_id,
        "counts": counts,
        "cells": cells,
        "comparisons": comparisons,
        "roi": roi,
    }


__all__ = ["aggregate_calibration_results"]
