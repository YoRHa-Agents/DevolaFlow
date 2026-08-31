"""Aggregation and uncertainty calculations for CLI calibration results."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from devolaflow.harness.calibration_matrix import CALIBRATION_SCHEMA_VERSION
from devolaflow.harness.cli_probe import SUPPORTED_CHANNELS, TASK_CLASSES, ProbeSpec

PERCENTILE_MINIMUM_N = 2
PAIRED_BOOTSTRAP_SEED = 20260901
PAIRED_BOOTSTRAP_REPLICATES = 2_000


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


def _partial_numeric_summary(
    values: Sequence[float],
    summary: Mapping[str, Any],
    *,
    include_mean: bool,
) -> dict[str, Any]:
    partial: dict[str, Any] = {
        "status": "PARTIAL",
        "observed_n": len(values),
        "p50": summary["p50"],
        "p95": summary["p95"],
        "label": "observed partial summary; not a complete cell metric",
    }
    if include_mean:
        partial["mean"] = sum(values) / len(values) if values else None
    return partial


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
        "ci95_method": "Wilson score",
        "ci95_interpretation": "descriptive success-rate interval only; not causal",
    }
    token_values = [
        usage["total_tokens"]
        for result in results
        if isinstance((usage := result.get("token_usage")), Mapping)
        and usage.get("status") == "AVAILABLE"
        and type(usage.get("total_tokens")) is int
    ]
    token_percentiles = _percentiles([float(value) for value in token_values])
    token_cost = {
        "status": "AVAILABLE" if complete and len(token_values) == expected_n else "INSUFFICIENT",
        "observed_n": len(token_values),
        "missing_n": expected_n - len(token_values),
        "mean": sum(token_values) / len(token_values)
        if complete and len(token_values) == expected_n and token_values
        else None,
        "p50": token_percentiles["p50"] if complete and len(token_values) == expected_n else None,
        "p95": token_percentiles["p95"] if complete and len(token_values) == expected_n else None,
        "p95_note": "descriptive order statistic; with n=5, p95 is the maximum observed value",
    }
    if token_values and token_cost["status"] != "AVAILABLE":
        token_cost["observed_partial"] = _partial_numeric_summary(
            [float(value) for value in token_values],
            token_percentiles,
            include_mean=True,
        )
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
    latency_values = _values_for_latency(results)
    latency_percentiles = _percentiles(latency_values)
    wall_time = {
        **latency_percentiles,
        "p95_note": "descriptive order statistic; with n=5, p95 is the maximum observed value",
    }
    if not (complete and len(latency_values) == expected_n):
        wall_time.update(
            {
                "status": "INSUFFICIENT",
                "p50": None,
                "p95": None,
            }
        )
        if latency_values:
            wall_time["observed_partial"] = _partial_numeric_summary(
                latency_values,
                latency_percentiles,
                include_mean=True,
            )
    return {
        "task_class": task_class,
        "channel": channel,
        "arm": arm,
        "expected_n": expected_n,
        "counts": counts,
        "completeness_status": "AVAILABLE" if complete else "INSUFFICIENT",
        "pass_rate": pass_rate,
        "wall_time_seconds": wall_time,
        "token_cost": token_cost,
        "skill_loaded": skill_loaded,
        "artifact_paths": [
            result["metadata"]["artifact_path"]
            for result in results
            if isinstance(result.get("metadata"), Mapping)
            and isinstance(result["metadata"].get("artifact_path"), str)
        ],
    }


def _replicate_id(result: Mapping[str, Any]) -> int | None:
    metadata = result.get("metadata")
    value = metadata.get("replicate") if isinstance(metadata, Mapping) else None
    if value is None:
        value = result.get("replicate")
    return value if type(value) is int and value >= 1 else None


def _unique_results_by_replicate(
    results: Sequence[Mapping[str, Any]],
) -> dict[int, Mapping[str, Any]]:
    indexed: dict[int, Mapping[str, Any]] = {}
    duplicates: set[int] = set()
    for result in results:
        replicate = _replicate_id(result)
        if replicate is None:
            continue
        if replicate in indexed:
            duplicates.add(replicate)
        else:
            indexed[replicate] = result
    for replicate in duplicates:
        indexed.pop(replicate, None)
    return indexed


def _matched_replicates(
    on_results: Sequence[Mapping[str, Any]],
    off_results: Sequence[Mapping[str, Any]],
) -> list[tuple[int, Mapping[str, Any], Mapping[str, Any]]]:
    on_by_replicate = _unique_results_by_replicate(on_results)
    off_by_replicate = _unique_results_by_replicate(off_results)
    return [
        (replicate, on_by_replicate[replicate], off_by_replicate[replicate])
        for replicate in sorted(on_by_replicate.keys() & off_by_replicate.keys())
    ]


def _pass_value(result: Mapping[str, Any]) -> float | None:
    status = result.get("status")
    if status == "PASS":
        return 1.0
    if status == "FAIL":
        return 0.0
    return None


def _latency_value(result: Mapping[str, Any]) -> float | None:
    execution = result.get("execution")
    if not isinstance(execution, Mapping):
        return None
    if execution.get("reason") not in {"completed", "nonzero_exit", "timeout"}:
        return None
    value = execution.get("wall_time_seconds")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _token_value(result: Mapping[str, Any]) -> float | None:
    usage = result.get("token_usage")
    if not isinstance(usage, Mapping) or usage.get("status") != "AVAILABLE":
        return None
    value = usage.get("total_tokens")
    if type(value) is int:
        return float(value)
    return None


def _bootstrap_ci(values: Sequence[float], *, seed: int) -> list[float] | None:
    if not values:
        return None
    generator = random.Random(seed)
    samples: list[float] = []
    for _ in range(PAIRED_BOOTSTRAP_REPLICATES):
        samples.append(
            sum(values[generator.randrange(len(values))] for _ in range(len(values))) / len(values)
        )
    ordered = sorted(samples)
    return [
        ordered[math.ceil(0.025 * len(ordered)) - 1],
        ordered[math.ceil(0.975 * len(ordered)) - 1],
    ]


def _paired_metric(
    pairs: Sequence[tuple[int, Mapping[str, Any], Mapping[str, Any]]],
    value_for: Any,
    *,
    expected_n: int,
) -> dict[str, Any]:
    observed: list[tuple[int, float]] = []
    for replicate, on_result, off_result in pairs:
        on_value = value_for(on_result)
        off_value = value_for(off_result)
        if on_value is not None and off_value is not None:
            observed.append((replicate, on_value - off_value))
    values = [value for _, value in observed]
    interval = _bootstrap_ci(values, seed=PAIRED_BOOTSTRAP_SEED)
    available = bool(values) and len(values) == expected_n
    metric: dict[str, Any] = {
        "status": "AVAILABLE" if available else "INSUFFICIENT",
        "observed_n": len(values),
        "expected_n": expected_n,
        "skill_on_minus_skill_off": sum(values) / len(values) if available else None,
        "ci95": interval if available else None,
        "uncertainty": "paired percentile bootstrap 95% CI; descriptive, not causal",
        "replicate_ids": [replicate for replicate, _ in observed],
    }
    if values and not available:
        metric["observed_partial"] = {
            "status": "PARTIAL",
            "observed_n": len(values),
            "skill_on_minus_skill_off": sum(values) / len(values),
            "ci95": interval,
            "label": "observed partial paired summary; not a complete cell metric",
        }
    return metric


def _paired_differences(
    on_results: Sequence[Mapping[str, Any]],
    off_results: Sequence[Mapping[str, Any]],
    *,
    task_class: str,
    channel: str,
    expected_n: int,
) -> dict[str, Any]:
    pairs = _matched_replicates(on_results, off_results)
    replicate_metadata = []
    for replicate, on_result, off_result in pairs:
        on_metadata = on_result.get("metadata")
        off_metadata = off_result.get("metadata")
        on_run_id = on_metadata.get("run_id") if isinstance(on_metadata, Mapping) else None
        off_run_id = off_metadata.get("run_id") if isinstance(off_metadata, Mapping) else None
        replicate_metadata.append(
            {
                "replicate": replicate,
                "skill_on_run_id": on_run_id,
                "skill_off_run_id": off_run_id,
            }
        )
    cell_complete = (
        len(on_results) == expected_n
        and len(off_results) == expected_n
        and all(result.get("status") != "INSUFFICIENT" for result in (*on_results, *off_results))
    )
    metrics = {
        "pass_rate": _paired_metric(pairs, _pass_value, expected_n=expected_n),
        "wall_time_seconds": _paired_metric(pairs, _latency_value, expected_n=expected_n),
        "token_cost": _paired_metric(pairs, _token_value, expected_n=expected_n),
    }
    return {
        "status": (
            "AVAILABLE"
            if cell_complete and all(metric["status"] == "AVAILABLE" for metric in metrics.values())
            else "INSUFFICIENT"
        ),
        "pairing": {
            "key": "task_class/channel/replicate",
            "unit": "matched skill-on/skill-off replicate pair",
            "cluster": f"{task_class}/{channel} cell",
            "observed_pairs": len(pairs),
            "expected_pairs": expected_n,
            "replicate_ids": [replicate for replicate, _, _ in pairs],
            "replicate_metadata": replicate_metadata,
        },
        "bootstrap": {
            "method": "paired percentile bootstrap",
            "seed": PAIRED_BOOTSTRAP_SEED,
            "replicates": PAIRED_BOOTSTRAP_REPLICATES,
            "resample_unit": "matched replicate pair",
            "cluster": f"{task_class}/{channel} cell",
            "interval": "percentile 95%",
        },
        **metrics,
        "causal_interpretation": (
            "Associational paired differences only; causal effect not established."
        ),
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
    on_results: Sequence[Mapping[str, Any]],
    off_results: Sequence[Mapping[str, Any]],
    expected_n: int,
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
    paired = _paired_differences(
        on_results,
        off_results,
        task_class=task_class,
        channel=channel,
        expected_n=expected_n,
    )
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
        "paired_differences": paired,
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
            result_by_cell[(task_class, channel, "skill-on")],
            result_by_cell[(task_class, channel, "skill-off")],
            expected_by_cell[(task_class, channel, "skill-on")],
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
            "difference intervals retained for compatibility; paired differences use a "
            "fixed-seed percentile bootstrap and remain descriptive."
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
