"""Strict, deterministic aggregation of segmented harness ledgers."""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from devolaflow.harness.metadata import MetadataError, validate_run_metadata
from devolaflow.harness.telemetry import (
    AGENTS_MD_TOKEN_FIELD,
    CONSOLIDATION_METRIC_NAMES,
    CONSOLIDATION_METRICS_EVENT,
    CONTEXT_TOKEN_EVENT,
    CONTEXT_TOKEN_FIELDS,
    DISPATCH_TOKEN_FIELD,
    HOST_RULE_TOKEN_FIELD,
    LEGACY_AGENTS_MD_TOKEN_FIELD,
    LEGACY_DISPATCH_TOKEN_FIELD,
    LEGACY_HOST_RULE_TOKEN_FIELD,
    METRIC_OBSERVATION_EVENT,
    METRIC_OBSERVATION_FIELDS,
    RETIRED_SI10_GATE_NAMES,
    SI10_GATE_EVENT,
    SI10_GATE_NAMES,
    TOKEN_ESTIMATOR_FIELD,
    compare_metric_observation_sets,
    validate_metric_observation,
)
from devolaflow.harness.token_injection import (
    TOKEN_COMPONENTS,
    TOKEN_INJECTION_EVENT,
    TokenInjectionError,
    validate_token_injection_measurement,
)

_logger = logging.getLogger(__name__)

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
    DISPATCH_TOKEN_FIELD,
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


def _compat_value(record: Mapping[str, Any], canonical: str, legacy: str) -> Any:
    """Read a canonical field while accepting one historical spelling."""

    return record[canonical] if canonical in record else record.get(legacy)


def _validate_token_estimator(
    value: object,
    *,
    path: Path,
    line: int,
) -> None:
    if not isinstance(value, dict) or set(value) != {
        "source",
        "tokenizer",
        "model",
        "encoding",
        "fallback_semantics",
        "provider_usage",
    }:
        raise _error(
            path,
            line,
            "token_estimator must contain source, tokenizer, model, encoding, "
            "fallback_semantics, provider_usage",
        )
    for field in ("source", "tokenizer", "fallback_semantics"):
        _non_empty_string(value[field], path=path, line=line, field=f"token_estimator.{field}")
    for field in ("model", "encoding"):
        if value[field] is not None:
            _non_empty_string(value[field], path=path, line=line, field=f"token_estimator.{field}")
    if value["provider_usage"] is not False:
        raise _error(path, line, "token_estimator.provider_usage must be false")


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
    if gate not in SI10_GATE_NAMES and gate not in RETIRED_SI10_GATE_NAMES:
        raise _error(path, line, f"SI-10 gate must be one of {', '.join(SI10_GATE_NAMES)}")
    if gate in RETIRED_SI10_GATE_NAMES:
        _logger.warning(
            "%s:%d: retaining retired SI-10 gate %r as historical evidence", path, line, gate
        )
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
    compatibility_record = record
    if LEGACY_AGENTS_MD_TOKEN_FIELD in record and AGENTS_MD_TOKEN_FIELD not in record:
        compatibility_record = {
            **{key: value for key, value in record.items() if key != LEGACY_AGENTS_MD_TOKEN_FIELD},
            AGENTS_MD_TOKEN_FIELD: record[LEGACY_AGENTS_MD_TOKEN_FIELD],
        }
    _check_event_fields(
        {key: value for key, value in compatibility_record.items() if key != TOKEN_ESTIMATOR_FIELD},
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
        value = compatibility_record[field]
        if value is None:
            continue
        if field in {AGENTS_MD_TOKEN_FIELD, "cjk_violations", "ghost_loc"}:
            _integer(value, path=path, line=line, field=field, minimum=0)
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise _error(path, line, f"{field} must be a finite non-negative number or null")
    if TOKEN_ESTIMATOR_FIELD in record:
        _validate_token_estimator(record[TOKEN_ESTIMATOR_FIELD], path=path, line=line)
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


def _validate_token_injection_event(
    record: dict[str, Any],
    *,
    path: Path,
    line: int,
) -> dict[str, Any]:
    try:
        return validate_token_injection_measurement(record)
    except TokenInjectionError as exc:
        raise _error(path, line, str(exc)) from exc


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
    if record.get("event") == TOKEN_INJECTION_EVENT:
        return _validate_token_injection_event(record, path=path, line=line)
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
    missing = [
        field
        for field in _REQUIRED_FIELDS
        if field not in record
        and not (field == DISPATCH_TOKEN_FIELD and LEGACY_DISPATCH_TOKEN_FIELD in record)
    ]
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
        _compat_value(record, DISPATCH_TOKEN_FIELD, LEGACY_DISPATCH_TOKEN_FIELD),
        path=path,
        line=line,
        field=DISPATCH_TOKEN_FIELD,
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
    if HOST_RULE_TOKEN_FIELD in record or LEGACY_HOST_RULE_TOKEN_FIELD in record:
        _integer(
            _compat_value(record, HOST_RULE_TOKEN_FIELD, LEGACY_HOST_RULE_TOKEN_FIELD),
            path=path,
            line=line,
            field=HOST_RULE_TOKEN_FIELD,
            minimum=0,
        )
    if AGENTS_MD_TOKEN_FIELD in record or LEGACY_AGENTS_MD_TOKEN_FIELD in record:
        _integer(
            _compat_value(record, AGENTS_MD_TOKEN_FIELD, LEGACY_AGENTS_MD_TOKEN_FIELD),
            path=path,
            line=line,
            field=AGENTS_MD_TOKEN_FIELD,
            minimum=0,
        )
    if TOKEN_ESTIMATOR_FIELD in record:
        _validate_token_estimator(record[TOKEN_ESTIMATOR_FIELD], path=path, line=line)
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


@dataclass(frozen=True)
class QuarantinedRow:
    """One ledger row the reader rejected and skipped instead of aborting."""

    path: str
    line: int
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.reason}"


def load_ledger_records(
    source: str | Path,
    *,
    quarantine: list[QuarantinedRow] | None = None,
) -> list[dict[str, Any]]:
    """Load and strictly validate records in base-then-numeric segment order.

    Strict by default: one malformed row raises and no records are returned.

    Pass a list as ``quarantine`` to opt into row-level isolation instead. A
    rejected row is appended to that list and skipped; the rest of the ledger
    still loads. This exists because of the v24 F-00 incident, where a single
    row carrying a retired gate name made the whole ledger unreadable and took
    every downstream evaluation with it. Naming the retired gate fixed that one
    row; isolation fixes the shape of the failure, so the next unforeseen row
    costs one record rather than the entire evidence base.

    Isolation is never silent (S-5): every quarantined row is logged at WARNING
    and returned to the caller, which is expected to surface the count.
    """

    records: list[dict[str, Any]] = []
    for path in _segment_paths(source):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise _error(path, None, f"cannot read ledger segment: {exc}") from exc
        if not text:
            raise _error(path, None, "ledger segment is empty")
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            try:
                if not raw_line.strip():
                    raise _error(path, line_number, "blank JSONL line is not allowed")
                try:
                    parsed = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise _error(path, line_number, f"invalid JSON: {exc.msg}") from exc
                records.append(_validate_record(parsed, path=path, line=line_number))
            except AggregationError as exc:
                if quarantine is None:
                    raise
                row = QuarantinedRow(str(path), line_number, str(exc))
                _logger.warning("quarantined unreadable ledger row: %s", row)
                quarantine.append(row)
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

    v17.0.0 R3 (D-R3-2): ``estimated_host_rule_tokens`` /
    ``slice_savings_pct`` are optional record fields, so their means are
    computed only over carrying records. The ``None``-when-absent convention
    mirrors the existing ``rounds.min`` / ``rounds.max`` absent-metric style.
    """

    values = [record[field] for record in records if field in record]
    if not values:
        return None
    return sum(values) / len(values)


def _optional_compat_mean(
    records: list[dict[str, Any]],
    canonical: str,
    legacy: str,
) -> float | None:
    values = [
        _compat_value(record, canonical, legacy)
        for record in records
        if canonical in record or legacy in record
    ]
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


def _token_injection_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("event") == TOKEN_INJECTION_EVENT]


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


def _coverage(observed: int, total: int) -> dict[str, Any]:
    return {
        "observed_records": observed,
        "total_records": total,
        "ratio": observed / total if total else 0.0,
        "status": "AVAILABLE" if observed else "INSUFFICIENT",
    }


def _token_injection_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    components: dict[str, dict[str, Any]] = {}
    for component in TOKEN_COMPONENTS:
        values = [
            record[f"{component}_tokens"]
            for record in records
            if record[f"{component}_tokens"] is not None
        ]
        mean = sum(values) / len(values) if values else None
        variance = sum((value - mean) ** 2 for value in values) / len(values) if values else None
        components[component] = {
            "mean": mean,
            "variance": variance,
            "interval": {"low": min(values), "high": max(values)} if values else None,
            "coverage": _coverage(len(values), total),
            "status": "AVAILABLE" if values else "INSUFFICIENT",
        }
    complete = sum(record["status"] == "AVAILABLE" for record in records)
    provider_usage: dict[str, dict[str, Any]] = {}
    for component in ("input", "output", "total"):
        field = f"provider_{component}_tokens"
        values = [record[field] for record in records if record.get(field) is not None]
        provider_usage[component] = {
            "mean": sum(values) / len(values) if values else None,
            "observed_records": len(values),
            "coverage": _coverage(len(values), total),
            "status": "AVAILABLE" if values else "INSUFFICIENT",
        }
    return {
        "records": total,
        "complete_records": complete,
        "coverage": _coverage(complete, total),
        "components": components,
        "provider_usage": provider_usage,
        "status": "AVAILABLE" if total and complete == total else "INSUFFICIENT",
    }


def _token_injection_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate measured injection components by host/channel and dimensions."""

    measurements = _token_injection_records(records)
    by_host_channel: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_host: dict[str, list[dict[str, Any]]] = {}
    by_channel: dict[str, list[dict[str, Any]]] = {}
    for record in measurements:
        key = (record["host"], record["channel"])
        by_host_channel.setdefault(key, []).append(record)
        by_host.setdefault(record["host"], []).append(record)
        by_channel.setdefault(record["channel"], []).append(record)

    def render_groups(
        groups: Mapping[object, list[dict[str, Any]]],
    ) -> dict[str, dict[str, Any]]:
        rendered: dict[str, dict[str, Any]] = {}
        for key in sorted(groups, key=str):
            rendered_key = "/".join(key) if isinstance(key, tuple) else str(key)
            rendered[rendered_key] = _token_injection_group(groups[key])
        return rendered

    complete = sum(record["status"] == "AVAILABLE" for record in measurements)
    return {
        "records": len(measurements),
        "coverage": _coverage(complete, len(measurements)),
        "status": "AVAILABLE" if measurements and complete == len(measurements) else "INSUFFICIENT",
        "by_host_channel": render_groups(by_host_channel),
        "by_host": render_groups(by_host),
        "by_channel": render_groups(by_channel),
    }


def _measurement_summary(
    dispatch_records: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Summarize optional measurements without filling historical gaps.

    Dedicated measurement events take precedence over dispatch fields. This
    prevents ``estimated_agents_md_tokens`` from being counted twice when a
    current run emits both legacy-compatible dispatch records and one
    measurement event.
    """

    events = _measurement_records(records)
    observations = _metric_observation_records(records)
    summary: dict[str, dict[str, Any]] = {}
    for field in CONSOLIDATION_METRIC_NAMES:
        if observations:
            matching = [
                record
                for record in observations
                if record["metric"]
                == (LEGACY_AGENTS_MD_TOKEN_FIELD if field == AGENTS_MD_TOKEN_FIELD else field)
                or record["metric"] == field
            ]
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
            [
                _compat_value(event, field, LEGACY_AGENTS_MD_TOKEN_FIELD)
                for event in events
                if (field in event or LEGACY_AGENTS_MD_TOKEN_FIELD in event)
                and _compat_value(event, field, LEGACY_AGENTS_MD_TOKEN_FIELD) is not None
            ]
            if events
            else [
                _compat_value(record, field, LEGACY_AGENTS_MD_TOKEN_FIELD)
                for record in dispatch_records
                if (field in record or LEGACY_AGENTS_MD_TOKEN_FIELD in record)
            ]
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
    estimated = [
        _compat_value(record, DISPATCH_TOKEN_FIELD, LEGACY_DISPATCH_TOKEN_FIELD)
        for record in records
    ]
    utilizations = [
        _compat_value(record, DISPATCH_TOKEN_FIELD, LEGACY_DISPATCH_TOKEN_FIELD)
        / record["tokens_budget"]
        for record in records
    ]
    compliant = sum(
        _compat_value(record, DISPATCH_TOKEN_FIELD, LEGACY_DISPATCH_TOKEN_FIELD)
        <= record["tokens_budget"]
        for record in records
    )
    return {
        "total": sum(estimated),
        "mean": sum(estimated) / len(estimated),
        "p50": nearest_rank(estimated, 0.50),
        "p95": nearest_rank(estimated, 0.95),
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
        token_metrics[f"{HOST_RULE_TOKEN_FIELD}_mean"] = _optional_compat_mean(
            dispatch_records,
            HOST_RULE_TOKEN_FIELD,
            LEGACY_HOST_RULE_TOKEN_FIELD,
        )
        token_metrics[f"{AGENTS_MD_TOKEN_FIELD}_mean"] = _optional_compat_mean(
            dispatch_records,
            AGENTS_MD_TOKEN_FIELD,
            LEGACY_AGENTS_MD_TOKEN_FIELD,
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
            f"{HOST_RULE_TOKEN_FIELD}_mean": None,
            f"{AGENTS_MD_TOKEN_FIELD}_mean": None,
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
        distinct_metadata: list[dict[str, Any]] = []
        seen_metadata: set[str] = set()
        for metadata in metadata_records:
            encoded = json.dumps(
                metadata,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if encoded not in seen_metadata:
                seen_metadata.add(encoded)
                distinct_metadata.append(metadata)
        if len(distinct_metadata) == 1:
            # Preserve the historical singleton envelope for callers that
            # expect ``summary["metadata"]``.
            result["metadata"] = distinct_metadata[0]
        else:
            # Append-only ledgers may contain several valid run envelopes.
            # Keep each repository-relative envelope intact; never merge
            # facts from separate runs into a synthetic singleton.
            result["metadata_records"] = distinct_metadata
    if context_token_records:
        result["context_token_records"] = context_token_records
    observations = _metric_observation_records(records)
    if observations:
        result["metric_observations"] = observations
    token_injection = _token_injection_records(records)
    if token_injection:
        result["token_injection"] = _token_injection_summary(records)
    return result


def aggregate_ledger(source: str | Path) -> dict[str, Any]:
    """Load and aggregate one harness ledger file or segmented change directory."""

    return aggregate_records(load_ledger_records(source))


__all__ = [
    "AggregationError",
    "QuarantinedRow",
    "aggregate_ledger",
    "aggregate_metric_observations",
    "aggregate_records",
    "load_ledger_records",
    "nearest_rank",
]
