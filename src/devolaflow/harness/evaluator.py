"""Deterministic W-3 six-dimension evaluation over harness telemetry."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devolaflow.harness.aggregator import (
    QuarantinedRow,
    aggregate_metric_observations,
    aggregate_records,
    load_ledger_records,
)
from devolaflow.harness.evaluation_comparison import compare_historical_companion
from devolaflow.harness.evaluation_contract import (
    DEFAULT_CROSS_VALIDATION_DELTA,
    DEFAULT_THRESHOLD,
    DIMENSION_WEIGHTS,
    HISTORICAL_COMPANION_METHOD,
    EvaluationError,
)
from devolaflow.harness.evaluator_signals import (
    _LEGACY_SIGNAL_ALIASES,
    MEASUREMENT_KEYS,
    SIGNAL_KEYS,
    Runner,
    SignalResult,
    _coerce_number,
    _unavailable,
    collect_signals,
    load_signals,
    normalize_signals,
)
from devolaflow.harness.metadata import (
    MetadataError,
    RunMetadata,
    build_run_metadata,
    validate_run_metadata,
)
from devolaflow.harness.telemetry import (
    AGENTS_MD_TOKEN_FIELD,
    LEGACY_AGENTS_MD_TOKEN_FIELD,
    MetricObservationError,
    TelemetryGateError,
    append_consolidation_metrics,
    validate_metric_observation,
)


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _binary_score(signal: SignalResult) -> float:
    return 10.0 if signal.available and signal.value is True else 0.0


def _coverage_score(signal: SignalResult) -> float:
    if not signal.available:
        return 0.0
    return 10.0 * _clamp((float(signal.value) - 60.0) / 20.0)


def _docstrings_score(signal: SignalResult) -> float:
    if not signal.available:
        return 0.0
    return 10.0 * _clamp(float(signal.value) / 100.0)


def _ratio_score(value: float) -> float:
    return 10.0 * _clamp(value)


def _w17_score(signal: SignalResult) -> float:
    return 10.0 if signal.available and float(signal.value) <= 30.0 else 0.0


def _p95_headroom_score(utilization: float) -> float:
    if utilization <= 1.0:
        return 10.0
    if utilization >= 1.2:
        return 0.0
    return 10.0 * (1.2 - utilization) / 0.2


def _latest_timestamp(records: list[dict[str, Any]]) -> str:
    def parsed(record: dict[str, Any]) -> tuple[datetime, str]:
        value = record.get("ts") or record.get("captured_at")
        if not isinstance(value, str):
            raise EvaluationError("record has no evaluation timestamp")
        return datetime.fromisoformat(value.replace("Z", "+00:00")), value

    latest = max(records, key=parsed)
    return latest.get("ts") or latest["captured_at"]


def _signal_component(signal: SignalResult, score: float) -> dict[str, Any]:
    return signal.as_subcomponent(score)


def _metric_component(value: float, score: float) -> dict[str, Any]:
    return {
        "score": round(score, 2),
        "available": True,
        "value": value,
    }


def _coerce_measurement(value: object, *, key: str) -> float | int:
    if isinstance(value, SignalResult):
        if not value.available:
            raise EvaluationError(value.error or f"measurement {key} unavailable")
        value = value.value
    coerced = _coerce_number(value, key=key)
    if float(coerced) < 0:
        raise EvaluationError(f"measurement {key} must be non-negative")
    return coerced


def _telemetry_measurements(summary: Mapping[str, Any]) -> dict[str, SignalResult]:
    raw_measurements = summary.get("measurements")
    if not isinstance(raw_measurements, Mapping):
        return {
            key: _unavailable(f"historical telemetry missing measurement: {key}")
            for key in MEASUREMENT_KEYS
        }
    resolved: dict[str, SignalResult] = {}
    for key in MEASUREMENT_KEYS:
        entry = raw_measurements.get(key)
        if not isinstance(entry, Mapping) or entry.get("mean") is None:
            resolved[key] = _unavailable(f"historical telemetry missing measurement: {key}")
        else:
            resolved[key] = SignalResult(
                available=True,
                value=_coerce_measurement(entry["mean"], key=key),
                provenance=(
                    entry.get("provenance")
                    if isinstance(entry.get("provenance"), Mapping)
                    else None
                ),
            )
    return resolved


def _resolve_measurements(
    summary: Mapping[str, Any],
    *,
    injected: Mapping[str, object] | None,
    collected: Mapping[str, SignalResult] | None,
) -> tuple[dict[str, SignalResult], dict[str, str]]:
    telemetry = _telemetry_measurements(summary)
    normalized_injected = dict(injected) if injected is not None else None
    if normalized_injected is not None:
        for legacy, canonical in _LEGACY_SIGNAL_ALIASES.items():
            if canonical not in normalized_injected and legacy in normalized_injected:
                normalized_injected[canonical] = normalized_injected[legacy]
    resolved: dict[str, SignalResult] = {}
    sources: dict[str, str] = {}
    for key in MEASUREMENT_KEYS:
        if telemetry[key].available:
            resolved[key] = telemetry[key]
            sources[key] = "telemetry"
            continue
        if normalized_injected is not None and key in normalized_injected:
            raw = normalized_injected[key]
            if isinstance(raw, SignalResult):
                resolved[key] = raw
                sources[key] = "injected"
                continue
            if isinstance(raw, Mapping):
                if "observation" in raw:
                    try:
                        observation = validate_metric_observation(raw["observation"])
                    except MetricObservationError as exc:
                        raise EvaluationError(
                            f"measurement {key} observation is invalid: {exc}"
                        ) from exc
                    if (
                        observation["metric"] == LEGACY_AGENTS_MD_TOKEN_FIELD
                        and key == AGENTS_MD_TOKEN_FIELD
                    ):
                        observation = {**observation, "metric": key}
                    if observation["metric"] != key:
                        raise EvaluationError(
                            f"measurement {key} observation metric must equal {key!r}"
                        )
                    resolved[key] = SignalResult(
                        available=True,
                        value=observation["value"],
                        provenance=observation,
                    )
                    sources[key] = "injected"
                    continue
                available = raw.get("available")
                if type(available) is not bool:
                    raise EvaluationError(f"measurement {key}.available must be a boolean")
                if not available:
                    error = raw.get("error")
                    if not isinstance(error, str) or not error.strip():
                        raise EvaluationError(
                            f"unavailable measurement {key} must include a non-empty error"
                        )
                    resolved[key] = _unavailable(error)
                else:
                    if "value" not in raw:
                        raise EvaluationError(f"available measurement {key} must include value")
                    resolved[key] = SignalResult(
                        available=True,
                        value=_coerce_measurement(raw["value"], key=key),
                    )
            else:
                resolved[key] = SignalResult(
                    available=True,
                    value=_coerce_measurement(raw, key=key),
                )
            sources[key] = "injected"
            continue
        if collected is not None and key in collected:
            resolved[key] = collected[key]
            sources[key] = "evaluator" if collected[key].available else "unavailable"
            continue
        resolved[key] = telemetry[key]
        sources[key] = "unavailable"
    return resolved, sources


def _render_measurements(
    measurements: Mapping[str, SignalResult],
    sources: Mapping[str, str],
    summary: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    rendered: dict[str, dict[str, Any]] = {}
    for key in MEASUREMENT_KEYS:
        signal = measurements[key]
        entry: dict[str, Any] = {
            "available": signal.available,
            "value": signal.value if signal.available else None,
            "status": "AVAILABLE" if signal.available else "INSUFFICIENT",
            "source": sources[key],
        }
        if signal.error:
            entry["error"] = signal.error
        provenance = signal.provenance
        if provenance is None and isinstance(summary, Mapping):
            raw_entry = summary.get(key)
            if isinstance(raw_entry, Mapping) and isinstance(raw_entry.get("provenance"), list):
                provenance = {"observations": raw_entry["provenance"]}
        if provenance is not None:
            entry["provenance"] = provenance
        rendered[key] = entry
    return rendered


def _persist_collected_measurements(
    ledger: str | Path,
    collected: Mapping[str, SignalResult],
    *,
    metadata: RunMetadata,
) -> None:
    """Append one complete current-run measurement envelope.

    ``None`` is retained for an unavailable probe.  The event is written only
    for evaluator-owned collection, never for injected or historical values.
    """

    measurements = {
        key: (collected[key].value if collected[key].available else None)
        for key in MEASUREMENT_KEYS
    }
    try:
        append_consolidation_metrics(
            ledger,
            measurements,
            timestamp=metadata["generated_at"],
            metadata=metadata,
        )
    except TelemetryGateError as exc:
        raise EvaluationError(f"cannot persist evaluator measurements: {exc}") from exc


def _ledger_aggregation_source(ledger: str | Path) -> str | Path:
    path = Path(ledger)
    return path.parent if path.name == "harness.jsonl" else ledger


def _mean_available(subcomponents: Mapping[str, Mapping[str, Any]]) -> float:
    scores = [
        float(component["score"])
        for component in subcomponents.values()
        if component["available"] is True
    ]
    return sum(scores) / len(scores) if scores else 0.0


def evaluate_harness(
    ledger: str | Path,
    *,
    signals: Mapping[str, object] | Mapping[str, SignalResult] | None = None,
    repo_root: str | Path = ".",
    base_ref: str = "HEAD~1",
    threshold: float = DEFAULT_THRESHOLD,
    sampled_at: str | None = None,
    runner: Runner | None = None,
    baseline: Sequence[Mapping[str, Any]] | None = None,
    run_metadata: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    salt: int | float | str | None = None,
    run_id: str | None = None,
    metadata_runner: Runner | None = None,
) -> dict[str, Any]:
    """Aggregate a ledger and evaluate the exact deterministic W-3 rubric."""

    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or not 0.0 <= float(threshold) <= 10.0
    ):
        raise EvaluationError("threshold must be a finite number in [0, 10]")

    aggregation_source = _ledger_aggregation_source(ledger)
    # Row-level isolation, not strictness relief: a row the reader cannot
    # parse is dropped and counted rather than aborting the evaluation. F-00
    # showed that the alternative is losing every reading over one bad line.
    quarantined: list[QuarantinedRow] = []
    records = load_ledger_records(aggregation_source, quarantine=quarantined)
    resolved_sampled_at = sampled_at or (
        _latest_timestamp(records) if signals is not None else datetime.now(UTC).isoformat()
    )
    try:
        metadata: RunMetadata = (
            validate_run_metadata(run_metadata)
            if run_metadata is not None
            else build_run_metadata(
                ledger,
                repo_root=repo_root,
                sampled_at=resolved_sampled_at,
                base_ref=base_ref,
                salt=salt,
                run_id=run_id,
                generated_at=generated_at,
                runner=metadata_runner,
            )
        )
    except MetadataError as exc:
        raise EvaluationError(str(exc)) from exc
    summary = aggregate_records(records)
    summary = {**summary, "metadata": metadata}
    collected_signals: dict[str, SignalResult] | None = None
    if signals is None:
        collected_signals = collect_signals(repo_root, base_ref=base_ref, runner=runner)
        resolved_signals = {key: collected_signals[key] for key in SIGNAL_KEYS}
    else:
        normalized_signal_input = dict(signals)
        for legacy, canonical in _LEGACY_SIGNAL_ALIASES.items():
            if canonical not in normalized_signal_input and legacy in normalized_signal_input:
                normalized_signal_input[canonical] = normalized_signal_input[legacy]
    if signals is not None and all(
        isinstance(value, SignalResult) for value in normalized_signal_input.values()
    ):
        resolved_signals = {
            key: (
                normalized_signal_input[key]
                if key in normalized_signal_input
                else _unavailable(f"missing injected signal: {key}")
            )
            for key in SIGNAL_KEYS
        }
    elif signals is not None:
        resolved_signals = normalize_signals(normalized_signal_input)
    if collected_signals is not None:
        _persist_collected_measurements(ledger, collected_signals, metadata=metadata)
        quarantined = []
        records = load_ledger_records(aggregation_source, quarantine=quarantined)
        summary = aggregate_records(records)
        summary = {**summary, "metadata": metadata}
    measurement_signals, measurement_sources = _resolve_measurements(
        summary,
        injected=signals,
        collected=collected_signals,
    )

    quantifiable_ratio = float(summary["constraints"]["quantifiable_ratio"])
    budget_compliance = float(summary["tokens"]["budget_compliance_ratio"])
    p95_utilization = float(summary["tokens"]["p95_budget_utilization"])
    components: dict[str, dict[str, dict[str, Any]]] = {
        "code_quality": {
            "ruff_lint": _signal_component(
                resolved_signals["ruff_lint"],
                _binary_score(resolved_signals["ruff_lint"]),
            ),
            "ruff_format": _signal_component(
                resolved_signals["ruff_format"],
                _binary_score(resolved_signals["ruff_format"]),
            ),
            "coverage": _signal_component(
                resolved_signals["coverage_pct"],
                _coverage_score(resolved_signals["coverage_pct"]),
            ),
        },
        "architecture_rationality": {
            "layout_invariant": _signal_component(
                resolved_signals["layout_invariant"],
                _binary_score(resolved_signals["layout_invariant"]),
            ),
            "quantifiable_ratio": _metric_component(
                quantifiable_ratio,
                _ratio_score(quantifiable_ratio),
            ),
        },
        "test_adequacy": {
            "test_suite": _signal_component(
                resolved_signals["test_suite"],
                _binary_score(resolved_signals["test_suite"]),
            ),
            "coverage": _signal_component(
                resolved_signals["coverage_pct"],
                _coverage_score(resolved_signals["coverage_pct"]),
            ),
            "w17": _signal_component(
                resolved_signals["w17_new_tests"],
                _w17_score(resolved_signals["w17_new_tests"]),
            ),
        },
        "maintainability": {
            "ruff_format": _signal_component(
                resolved_signals["ruff_format"],
                _binary_score(resolved_signals["ruff_format"]),
            ),
            "docstrings": _signal_component(
                resolved_signals["docstring_coverage_pct"],
                _docstrings_score(resolved_signals["docstring_coverage_pct"]),
            ),
        },
        "compatibility": {
            "layout_invariant": _signal_component(
                resolved_signals["layout_invariant"],
                _binary_score(resolved_signals["layout_invariant"]),
            ),
            "compatibility_suite": _signal_component(
                resolved_signals["compatibility_suite"],
                _binary_score(resolved_signals["compatibility_suite"]),
            ),
        },
        "performance_impact": {
            "budget_compliance_ratio": _metric_component(
                budget_compliance,
                _ratio_score(budget_compliance),
            ),
            "p95_headroom": _metric_component(
                p95_utilization,
                _p95_headroom_score(p95_utilization),
            ),
        },
    }

    scores: list[dict[str, Any]] = []
    available_slots = 0
    total_slots = 0
    for dimension, weight in DIMENSION_WEIGHTS.items():
        subcomponents = components[dimension]
        available_slots += sum(
            component["available"] is True for component in subcomponents.values()
        )
        total_slots += len(subcomponents)
        scores.append(
            {
                "id": dimension,
                "score": round(_mean_available(subcomponents), 2),
                "weight": weight,
                "metadata": {"subcomponents": subcomponents},
            }
        )

    composite = round(sum(item["score"] * item["weight"] for item in scores), 2)
    complete = available_slots == total_slots
    verdict = (
        "INSUFFICIENT"
        if not complete
        else "READY"
        if composite >= float(threshold)
        else "NOT_READY"
    )
    suggestions: list[dict[str, str]] = []
    for item in scores:
        unavailable = [
            name
            for name, component in item["metadata"]["subcomponents"].items()
            if component["available"] is False
        ]
        if unavailable:
            reason = f"unavailable inputs: {', '.join(unavailable)}"
        elif item["score"] < float(threshold):
            reason = f"score {item['score']:.2f} below threshold {float(threshold):.2f}"
        else:
            continue
        suggestions.append({"dimension": item["id"], "reason": reason})

    result = {
        "schema_version": 1,
        "sampled_at": resolved_sampled_at,
        "threshold": float(threshold),
        "scores": scores,
        "composite": composite,
        "auto_fill_rate": round(available_slots / total_slots, 4),
        "verdict": verdict,
        "harness_summary": summary,
        "measurements": _render_measurements(
            measurement_signals,
            measurement_sources,
            summary["measurements"],
        ),
        "suggestions": suggestions,
        # Appended at the tail, never inserted: the envelope's key order is
        # pinned. Surfaced rather than only logged because a reading taken
        # over a ledger the reader could not fully parse must say so in the
        # artifact, or row isolation becomes a way to lose evidence quietly
        # (S-5).
        "quarantined_rows": [
            {"path": row.path, "line": row.line, "reason": row.reason} for row in quarantined
        ],
    }
    if (
        run_metadata is not None
        or generated_at is not None
        or salt is not None
        or run_id is not None
    ):
        result["metadata"] = metadata
    if baseline is not None:
        if isinstance(baseline, (str, bytes)) or not isinstance(baseline, Sequence):
            raise EvaluationError("baseline must be a sequence of metric observations")
        current = summary.get("metric_observations", [])
        if not isinstance(current, list):
            current = []
        result["metric_comparison"] = aggregate_metric_observations(list(baseline), current)
    return result


def render_evaluation(result: Mapping[str, Any]) -> str:
    """Render stable, byte-identical JSON for a deterministic result."""

    return json.dumps(result, ensure_ascii=False, indent=2, separators=(",", ": ")) + "\n"


__all__ = [
    "DEFAULT_CROSS_VALIDATION_DELTA",
    "DEFAULT_THRESHOLD",
    "DIMENSION_WEIGHTS",
    "HISTORICAL_COMPANION_METHOD",
    "MEASUREMENT_KEYS",
    "SIGNAL_KEYS",
    "EvaluationError",
    "MetadataError",
    "RunMetadata",
    "SignalResult",
    "build_run_metadata",
    "collect_signals",
    "compare_historical_companion",
    "evaluate_harness",
    "load_signals",
    "normalize_signals",
    "render_evaluation",
    "validate_run_metadata",
]
