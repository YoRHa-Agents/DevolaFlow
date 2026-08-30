"""Strict, deterministic aggregation of segmented harness ledgers."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from devolaflow.harness.metadata import MetadataError, validate_run_metadata
from devolaflow.harness.telemetry import (
    CONSOLIDATION_METRIC_NAMES,
    CONSOLIDATION_METRICS_EVENT,
    CONTEXT_TOKEN_EVENT,
    CONTEXT_TOKEN_FIELDS,
    METRIC_OBSERVATION_EVENT,
    METRIC_OBSERVATION_FIELDS,
    SI10_GATE_EVENT,
    SI10_GATE_NAMES,
    compare_metric_observation_sets,
    validate_metric_observation,
)

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
_EVENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "event",
        "event_id",
        "ts",
        "proposal_id",
        "proposal_ref",
        "approval_ref",
        "proposal_sha256",
        "target_digest",
    }
)
_SI10_EVENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "event",
        "event_id",
        "ts",
        "pv",
        "gate",
        "status",
    }
)
_CONSOLIDATION_EVENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "event",
        "event_id",
        "ts",
        *CONSOLIDATION_METRIC_NAMES,
    }
)
_CONTEXT_TOKEN_EVENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "event",
        "event_id",
        "ts",
        "context_tokens",
    }
)
_METRIC_OBSERVATION_EVENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "event",
        "event_id",
        *METRIC_OBSERVATION_FIELDS[1:],
    }
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


def _validate_optional_metadata(record: dict[str, Any], *, path: Path, line: int) -> None:
    if "metadata" not in record:
        return
    try:
        validate_run_metadata(record["metadata"])
    except MetadataError as exc:
        raise _error(path, line, str(exc)) from exc


def _check_event_fields(
    record: dict[str, Any],
    expected: frozenset[str],
    *,
    path: Path,
    line: int,
    label: str,
) -> None:
    actual = set(record) - {"metadata"}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise _error(path, line, f"{label} keys mismatch; missing={missing}, extra={extra}")
    _validate_optional_metadata(record, path=path, line=line)


def _validate_si10_event(record: dict[str, Any], *, path: Path, line: int) -> dict[str, Any]:
    _check_event_fields(record, _SI10_EVENT_FIELDS, path=path, line=line, label="SI-10 event")
    if record["schema_version"] != 1:
        raise _error(path, line, "SI-10 event schema_version must equal 1")
    _validate_timestamp(record["ts"], path=path, line=line)
    pv = _non_empty_string(record["pv"], path=path, line=line, field="pv")
    gate = _non_empty_string(record["gate"], path=path, line=line, field="gate")
    if gate not in SI10_GATE_NAMES:
        raise _error(path, line, f"SI-10 gate must be one of {', '.join(SI10_GATE_NAMES)}")
    status = _non_empty_string(record["status"], path=path, line=line, field="status")
    if status not in {"PASS", "FAIL"}:
        raise _error(path, line, "SI-10 status must be PASS or FAIL")
    event_id = _non_empty_string(record["event_id"], path=path, line=line, field="event_id")
    expected_event_id = f"{SI10_GATE_EVENT}:{pv}:{gate}:{status}"
    if event_id != expected_event_id:
        raise _error(path, line, "SI-10 event_id must identify pv, gate, and status")
    return record


def _validate_consolidation_metrics_event(
    record: dict[str, Any],
    *,
    path: Path,
    line: int,
) -> dict[str, Any]:
    _check_event_fields(
        record,
        _CONSOLIDATION_EVENT_FIELDS,
        path=path,
        line=line,
        label="consolidation event",
    )
    if record["schema_version"] != 1:
        raise _error(path, line, "consolidation event schema_version must equal 1")
    _validate_timestamp(record["ts"], path=path, line=line)
    _non_empty_string(record["event_id"], path=path, line=line, field="event_id")
    for field in CONSOLIDATION_METRIC_NAMES:
        value = record[field]
        if value is None:
            continue
        if field in {"agents_md_tokens", "cjk_violations", "ghost_loc"}:
            _integer(value, path=path, line=line, field=field, minimum=0)
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise _error(path, line, f"{field} must be a finite non-negative number or null")
    return record


def _validate_context_token_event(
    record: dict[str, Any],
    *,
    path: Path,
    line: int,
) -> dict[str, Any]:
    _check_event_fields(
        record,
        _CONTEXT_TOKEN_EVENT_FIELDS,
        path=path,
        line=line,
        label="context token event",
    )
    if record["schema_version"] != 1:
        raise _error(path, line, "context token event schema_version must equal 1")
    _validate_timestamp(record["ts"], path=path, line=line)
    _non_empty_string(record["event_id"], path=path, line=line, field="event_id")
    accounting = record["context_tokens"]
    if not isinstance(accounting, dict) or set(accounting) != set(CONTEXT_TOKEN_FIELDS):
        raise _error(
            path,
            line,
            "context_tokens must contain exactly skill_tokens, rule_tokens, report_tokens",
        )
    for field in CONTEXT_TOKEN_FIELDS:
        value = accounting[field]
        if value is not None:
            _integer(value, path=path, line=line, field=f"context_tokens.{field}", minimum=0)
    return record


def _validate_metric_observation_event(
    record: dict[str, Any],
    *,
    path: Path,
    line: int,
) -> dict[str, Any]:
    _check_event_fields(
        record,
        _METRIC_OBSERVATION_EVENT_FIELDS,
        path=path,
        line=line,
        label="metric observation event",
    )
    if record["event"] != METRIC_OBSERVATION_EVENT:
        raise _error(path, line, "metric observation event has an unsupported event name")
    if not isinstance(record["event_id"], str) or not record["event_id"].strip():
        raise _error(path, line, "metric observation event_id must be a non-empty string")
    observation = {field: record[field] for field in METRIC_OBSERVATION_FIELDS}
    try:
        validate_metric_observation(observation)
    except ValueError as exc:
        raise _error(path, line, str(exc)) from exc
    return record


def _validate_record(record: object, *, path: Path, line: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise _error(path, line, "record must be a JSON object")
    if record.get("event") == SI10_GATE_EVENT:
        return _validate_si10_event(record, path=path, line=line)
    if record.get("event") == CONSOLIDATION_METRICS_EVENT:
        return _validate_consolidation_metrics_event(record, path=path, line=line)
    if record.get("event") == CONTEXT_TOKEN_EVENT:
        return _validate_context_token_event(record, path=path, line=line)
    if record.get("event") == METRIC_OBSERVATION_EVENT:
        return _validate_metric_observation_event(record, path=path, line=line)
    if "event" in record:
        _check_event_fields(record, _EVENT_FIELDS, path=path, line=line, label="proposal event")
        if record["schema_version"] != 1:
            raise _error(path, line, "proposal event schema_version must equal 1")
        if record["event"] != "proposal_applied":
            raise _error(path, line, "event must equal proposal_applied")
        _validate_timestamp(record["ts"], path=path, line=line)
        proposal_id = _non_empty_string(
            record["proposal_id"],
            path=path,
            line=line,
            field="proposal_id",
        )
        if not re.fullmatch(r"[0-9a-f]{64}", proposal_id):
            raise _error(path, line, "proposal_id must be a lowercase SHA-256 value")
        if record["event_id"] != f"proposal_applied:{proposal_id}":
            raise _error(path, line, "event_id must equal proposal_applied:<proposal_id>")
        for field in ("proposal_ref", "approval_ref"):
            reference = _non_empty_string(record[field], path=path, line=line, field=field)
            reference_path = Path(reference)
            if (
                reference_path.is_absolute()
                or reference.startswith("~")
                or ".." in reference_path.parts
            ):
                raise _error(path, line, f"{field} must be repository-relative")
        for field in ("proposal_sha256", "target_digest"):
            digest = _non_empty_string(record[field], path=path, line=line, field=field)
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise _error(path, line, f"{field} must be a lowercase SHA-256 value")
        return record
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
    # v17.0.0 R3 (G17-B3 / D-R3-2) — OPTIONAL host-injection accounting
    # fields. Deliberately NOT in _REQUIRED_FIELDS: pre-v17 ledgers keep
    # aggregating. When present they are validated strictly like every
    # other telemetry value.
    if "host_rule_tokens" in record:
        _integer(
            record["host_rule_tokens"],
            path=path,
            line=line,
            field="host_rule_tokens",
            minimum=0,
        )
    if "agents_md_tokens" in record:
        _integer(
            record["agents_md_tokens"],
            path=path,
            line=line,
            field="agents_md_tokens",
            minimum=0,
        )
    for field in ("suite_wall_seconds", "cjk_violations", "ghost_loc"):
        if field not in record:
            continue
        value = record[field]
        if value is None:
            continue
        if field in {"cjk_violations", "ghost_loc"}:
            _integer(value, path=path, line=line, field=field, minimum=0)
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise _error(path, line, f"{field} must be a finite non-negative number")
    if "slice_savings_pct" in record:
        savings = record["slice_savings_pct"]
        if (
            isinstance(savings, bool)
            or not isinstance(savings, (int, float))
            or not math.isfinite(float(savings))
            or not 0.0 <= float(savings) <= 100.0
        ):
            raise _error(path, line, "slice_savings_pct must be a finite number in [0, 100]")
    _validate_optional_metadata(record, path=path, line=line)
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


def _optional_mean(records: list[dict[str, Any]], field: str) -> float | None:
    """Mean of ``field`` over the records that carry it; ``None`` when none do.

    v17.0.0 R3 (D-R3-2): ``host_rule_tokens`` / ``slice_savings_pct`` are
    optional record fields, so their means are computed only over carrying
    records. The ``None``-when-absent convention mirrors the existing
    ``rounds.min`` / ``rounds.max`` absent-metric style.
    """

    values = [record[field] for record in records if field in record]
    if not values:
        return None
    return sum(values) / len(values)


def _context_token_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Summarize explicit component counts without turning missing into zero."""
    events = [record for record in records if record.get("event") == CONTEXT_TOKEN_EVENT]
    dispatch_records = [record for record in records if "event" not in record]
    sources = [*events, *dispatch_records]
    result: dict[str, dict[str, Any]] = {}
    for field in CONTEXT_TOKEN_FIELDS:
        values = []
        for record in sources:
            accounting = record.get("context_tokens")
            if isinstance(accounting, dict) and accounting.get(field) is not None:
                values.append(accounting[field])
        entry: dict[str, Any] = {
            "mean": sum(values) / len(values) if values else None,
            "observed_records": len(values),
            "status": "AVAILABLE" if values else "INSUFFICIENT",
        }
        provenance = [
            {"source": "telemetry", "metadata": record["metadata"]}
            for record in sources
            if "metadata" in record
        ]
        if provenance:
            entry["provenance"] = provenance
        result[field] = entry
    return result


def _measurement_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("event") == CONSOLIDATION_METRICS_EVENT]


def _metric_observation_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("event") == METRIC_OBSERVATION_EVENT]


def _measurement_provenance(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"source": "telemetry", "metadata": record["metadata"]}
        for record in records
        if "metadata" in record
    ]


def _observation_provenance(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "item_id": record["item_id"],
        "source_revision": record["source_revision"],
        "command": record["command"],
        "environment": record["environment"],
        "measurement": record["measurement"],
    }


def _measurement_summary(
    dispatch_records: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Summarize optional measurements without filling historical gaps.

    Dedicated measurement events take precedence over dispatch fields. This
    prevents ``agents_md_tokens`` from being counted twice when a current run
    emits both legacy-compatible dispatch records and one measurement event.
    """

    events = _measurement_records(records)
    observations = _metric_observation_records(records)
    summary: dict[str, dict[str, Any]] = {}
    for field in CONSOLIDATION_METRIC_NAMES:
        if observations:
            matching = [record for record in observations if record["metric"] == field]
            values = [record["value"] for record in matching]
            entry = {
                "mean": sum(values) / len(values) if values else None,
                "observed_records": len(values),
                "status": "AVAILABLE" if values else "INSUFFICIENT",
                "provenance": [_observation_provenance(record) for record in matching],
            }
            if not matching:
                entry.pop("provenance")
            summary[field] = entry
            continue
        values = (
            [event[field] for event in events if event[field] is not None]
            if events
            else [record[field] for record in dispatch_records if field in record]
        )
        entry = {
            "mean": sum(values) / len(values) if values else None,
            "observed_records": len(values),
            "status": "AVAILABLE" if values else "INSUFFICIENT",
        }
        provenance = _measurement_provenance(events)
        if provenance:
            entry["provenance"] = provenance
        summary[field] = entry
    return summary


def aggregate_metric_observations(
    baseline: list[Mapping[str, Any]],
    current: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate matched baseline/current observations by item and metric."""

    comparisons = compare_metric_observation_sets(baseline, current)
    return {
        "schema_version": 1,
        "status": (
            "AVAILABLE"
            if comparisons and all(comparison["matched"] for comparison in comparisons)
            else "INSUFFICIENT"
        ),
        "comparisons": comparisons,
    }


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
    events = [record for record in records if record.get("event") == "proposal_applied"]
    dispatch_records = [record for record in records if "event" not in record]
    context_token_records = [
        record for record in records if record.get("event") == CONTEXT_TOKEN_EVENT
    ]
    rounds = [record["round"] for record in dispatch_records]
    if dispatch_records:
        token_metrics = _token_metrics(dispatch_records)
        token_metrics["host_rule_tokens_mean"] = _optional_mean(
            dispatch_records, "host_rule_tokens"
        )
        token_metrics["agents_md_tokens_mean"] = _optional_mean(
            dispatch_records, "agents_md_tokens"
        )
        token_metrics["slice_savings_pct_mean"] = _optional_mean(
            dispatch_records, "slice_savings_pct"
        )
        token_metrics["context_tokens"] = _context_token_summary(records)
        token_metrics["by_layer"] = {
            layer: {
                "records": sum(record["layer"] == layer for record in dispatch_records),
                **_token_metrics(
                    [record for record in dispatch_records if record["layer"] == layer]
                ),
            }
            for layer in _LAYER_ORDER
            if any(record["layer"] == layer for record in dispatch_records)
        }
    else:
        token_metrics = {
            "total": 0,
            "mean": 0.0,
            "p50": 0,
            "p95": 0,
            "budget_compliance_ratio": 0.0,
            "p95_budget_utilization": 0.0,
            "host_rule_tokens_mean": None,
            "agents_md_tokens_mean": None,
            "slice_savings_pct_mean": None,
            "context_tokens": _context_token_summary(records),
            "by_layer": {},
        }

    tier_breakdown = {
        tier: sum(record["tier_breakdown"][tier] for record in dispatch_records)
        for tier in _TIER_ORDER
    }
    constraint_count = sum(tier_breakdown.values())
    quantifiable = tier_breakdown["invariant"] + tier_breakdown["guard"]
    models: dict[str, int] = {}
    for model_hint in sorted({record["model_hint"] for record in dispatch_records}):
        models[model_hint] = sum(record["model_hint"] == model_hint for record in dispatch_records)

    result = {
        "schema_version": 1,
        "records": len(dispatch_records),
        "events": events,
        "changes": sorted({record["change_id"] for record in dispatch_records}),
        "rounds": {
            "min": min(rounds) if rounds else None,
            "max": max(rounds) if rounds else None,
            "distinct": len(set(rounds)),
        },
        "tokens": token_metrics,
        "constraints": {
            "count": constraint_count,
            "tier_breakdown": tier_breakdown,
            "quantifiable_ratio": quantifiable / constraint_count if constraint_count else 0.0,
            "advisory_folded_ratio": (
                sum(record["advisory_folded"] for record in dispatch_records)
                / len(dispatch_records)
                if dispatch_records
                else 0.0
            ),
        },
        "models": models,
        "measurements": _measurement_summary(dispatch_records, records),
    }
    metadata_records = [record["metadata"] for record in records if "metadata" in record]
    if metadata_records:
        encoded = {
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for metadata in metadata_records
        }
        if len(encoded) != 1:
            raise AggregationError("ledger contains inconsistent run metadata")
        result["metadata"] = metadata_records[0]
    if context_token_records:
        result["context_token_records"] = context_token_records
    observations = _metric_observation_records(records)
    if observations:
        result["metric_observations"] = observations
    return result


def aggregate_ledger(source: str | Path) -> dict[str, Any]:
    """Load and aggregate one harness ledger file or segmented change directory."""

    return aggregate_records(load_ledger_records(source))


__all__ = [
    "AggregationError",
    "aggregate_ledger",
    "aggregate_metric_observations",
    "aggregate_records",
    "load_ledger_records",
    "nearest_rank",
]
