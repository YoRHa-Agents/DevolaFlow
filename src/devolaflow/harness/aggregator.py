"""Strict, deterministic aggregation of segmented harness ledgers."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Final

_BASE_LEDGER_NAME: Final[str] = "harness.jsonl"
_SEGMENT_RE: Final[re.Pattern[str]] = re.compile(r"^harness\.([1-9]\d*)\.jsonl$")
_LAYER_ORDER: Final[tuple[str, ...]] = ("L0", "L1", "L2")
_TIER_ORDER: Final[tuple[str, ...]] = ("invariant", "guard", "advisory")
_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "ts",
    "change_id",
    "round",
    "layer",
    "dispatch_id",
    "tokens_injected_measured",
    "tokens_budget",
    "constraint_count",
    "quantifiable_ratio",
    "tier_breakdown",
    "advisory_folded",
    "model_hint",
)


class AggregationError(ValueError):
    """A ledger path, segment, line, or telemetry record is invalid."""


def _error(path: Path, line_number: int | None, message: str) -> AggregationError:
    location = f"{path}:{line_number}" if line_number is not None else str(path)
    return AggregationError(f"{location}: {message}")


def _segment_paths(source: str | Path) -> list[Path]:
    path = Path(source)
    if path.is_file():
        return [path]
    if not path.exists():
        raise AggregationError(f"{path}: ledger path does not exist")
    if not path.is_dir():
        raise AggregationError(f"{path}: ledger path must be a file or directory")

    candidates = sorted(
        child
        for child in path.iterdir()
        if child.is_file() and child.name.startswith("harness") and child.suffix == ".jsonl"
    )
    malformed = [
        child.name
        for child in candidates
        if child.name != _BASE_LEDGER_NAME and _SEGMENT_RE.fullmatch(child.name) is None
    ]
    if malformed:
        raise AggregationError(
            f"{path}: invalid harness segment name(s): {', '.join(sorted(malformed))}"
        )

    base = path / _BASE_LEDGER_NAME
    if not base.is_file():
        raise AggregationError(f"{path}: {_BASE_LEDGER_NAME} is required")
    indexed = sorted(
        (
            int(match.group(1)),
            child,
        )
        for child in candidates
        if (match := _SEGMENT_RE.fullmatch(child.name)) is not None
    )
    indexes = [index for index, _ in indexed]
    expected = list(range(1, len(indexes) + 1))
    if indexes != expected:
        raise AggregationError(
            f"{path}: harness segments must be contiguous from 1; found {indexes}"
        )
    return [base, *(child for _, child in indexed)]


def _non_empty_string(value: object, *, path: Path, line: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(path, line, f"{field} must be a non-empty string")
    return value


def _integer(
    value: object,
    *,
    path: Path,
    line: int,
    field: str,
    minimum: int,
) -> int:
    if type(value) is not int or value < minimum:
        raise _error(path, line, f"{field} must be an integer >= {minimum}")
    return value


def _ratio(value: object, *, path: Path, line: int, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise _error(path, line, f"{field} must be a finite number in [0, 1]")
    return float(value)


def _validate_timestamp(value: object, *, path: Path, line: int) -> str:
    timestamp = _non_empty_string(value, path=path, line=line, field="ts")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error(path, line, "ts must be an ISO-8601 timestamp") from exc
    return timestamp


def _validate_record(record: object, *, path: Path, line: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise _error(path, line, "record must be a JSON object")
    missing = [field for field in _REQUIRED_FIELDS if field not in record]
    if missing:
        raise _error(path, line, f"missing required field(s): {', '.join(missing)}")

    _validate_timestamp(record["ts"], path=path, line=line)
    _non_empty_string(record["change_id"], path=path, line=line, field="change_id")
    _integer(record["round"], path=path, line=line, field="round", minimum=1)
    layer = _non_empty_string(record["layer"], path=path, line=line, field="layer")
    if layer not in _LAYER_ORDER:
        raise _error(path, line, f"layer must be one of {', '.join(_LAYER_ORDER)}")
    _non_empty_string(record["dispatch_id"], path=path, line=line, field="dispatch_id")
    _integer(
        record["tokens_injected_measured"],
        path=path,
        line=line,
        field="tokens_injected_measured",
        minimum=0,
    )
    _integer(
        record["tokens_budget"],
        path=path,
        line=line,
        field="tokens_budget",
        minimum=1,
    )
    constraint_count = _integer(
        record["constraint_count"],
        path=path,
        line=line,
        field="constraint_count",
        minimum=0,
    )
    quantifiable_ratio = _ratio(
        record["quantifiable_ratio"],
        path=path,
        line=line,
        field="quantifiable_ratio",
    )
    breakdown = record["tier_breakdown"]
    if not isinstance(breakdown, dict) or set(breakdown) != set(_TIER_ORDER):
        raise _error(
            path,
            line,
            "tier_breakdown must contain exactly invariant, guard, advisory",
        )
    for tier in _TIER_ORDER:
        _integer(
            breakdown[tier],
            path=path,
            line=line,
            field=f"tier_breakdown.{tier}",
            minimum=0,
        )
    if sum(breakdown.values()) != constraint_count:
        raise _error(path, line, "tier_breakdown sum must equal constraint_count")
    expected_ratio = (
        (breakdown["invariant"] + breakdown["guard"]) / constraint_count
        if constraint_count
        else 0.0
    )
    if not math.isclose(quantifiable_ratio, expected_ratio, rel_tol=0.0, abs_tol=1e-12):
        raise _error(
            path,
            line,
            "quantifiable_ratio must equal (invariant + guard) / constraint_count",
        )
    if type(record["advisory_folded"]) is not bool:
        raise _error(path, line, "advisory_folded must be a boolean")
    _non_empty_string(record["model_hint"], path=path, line=line, field="model_hint")
    return record


def load_ledger_records(source: str | Path) -> list[dict[str, Any]]:
    """Load and strictly validate records in base-then-numeric segment order."""

    records: list[dict[str, Any]] = []
    for path in _segment_paths(source):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise _error(path, None, f"cannot read ledger segment: {exc}") from exc
        if not text:
            raise _error(path, None, "ledger segment is empty")
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            if not raw_line.strip():
                raise _error(path, line_number, "blank JSONL line is not allowed")
            try:
                parsed = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise _error(path, line_number, f"invalid JSON: {exc.msg}") from exc
            records.append(_validate_record(parsed, path=path, line=line_number))
    if not records:
        raise AggregationError(f"{source}: ledger contains no records")
    return records


def nearest_rank(values: list[float | int], percentile: float) -> float | int:
    """Return ``sorted(values)[ceil(percentile * n) - 1]``."""

    if not values:
        raise AggregationError("nearest-rank requires at least one value")
    if not 0.0 < percentile <= 1.0:
        raise AggregationError("percentile must be in (0, 1]")
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _token_metrics(records: list[dict[str, Any]]) -> dict[str, float | int]:
    measured = [record["tokens_injected_measured"] for record in records]
    utilizations = [
        record["tokens_injected_measured"] / record["tokens_budget"] for record in records
    ]
    compliant = sum(
        record["tokens_injected_measured"] <= record["tokens_budget"] for record in records
    )
    return {
        "total": sum(measured),
        "mean": sum(measured) / len(measured),
        "p50": nearest_rank(measured, 0.50),
        "p95": nearest_rank(measured, 0.95),
        "budget_compliance_ratio": compliant / len(records),
        "p95_budget_utilization": nearest_rank(utilizations, 0.95),
    }


def aggregate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate already-validated records with deterministic mapping order."""

    if not records:
        raise AggregationError("cannot aggregate an empty ledger")
    rounds = [record["round"] for record in records]
    token_metrics = _token_metrics(records)
    token_metrics["by_layer"] = {
        layer: {
            "records": sum(record["layer"] == layer for record in records),
            **_token_metrics([record for record in records if record["layer"] == layer]),
        }
        for layer in _LAYER_ORDER
        if any(record["layer"] == layer for record in records)
    }

    tier_breakdown = {
        tier: sum(record["tier_breakdown"][tier] for record in records) for tier in _TIER_ORDER
    }
    constraint_count = sum(tier_breakdown.values())
    quantifiable = tier_breakdown["invariant"] + tier_breakdown["guard"]
    models: dict[str, int] = {}
    for model_hint in sorted({record["model_hint"] for record in records}):
        models[model_hint] = sum(record["model_hint"] == model_hint for record in records)

    return {
        "schema_version": 1,
        "records": len(records),
        "changes": sorted({record["change_id"] for record in records}),
        "rounds": {
            "min": min(rounds),
            "max": max(rounds),
            "distinct": len(set(rounds)),
        },
        "tokens": token_metrics,
        "constraints": {
            "count": constraint_count,
            "tier_breakdown": tier_breakdown,
            "quantifiable_ratio": quantifiable / constraint_count if constraint_count else 0.0,
            "advisory_folded_ratio": (
                sum(record["advisory_folded"] for record in records) / len(records)
            ),
        },
        "models": models,
    }


def aggregate_ledger(source: str | Path) -> dict[str, Any]:
    """Load and aggregate one harness ledger file or segmented change directory."""

    return aggregate_records(load_ledger_records(source))


__all__ = [
    "AggregationError",
    "aggregate_ledger",
    "aggregate_records",
    "load_ledger_records",
    "nearest_rank",
]
