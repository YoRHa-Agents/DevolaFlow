"""Append-only per-dispatch telemetry for the built-in harness.

The post-dispatch lifecycle integration is deliberately observational:
payloads are rendered to stable YAML for measurement, never mutated, and any
attribution or persistence failure is reduced to a WARNING plus a clean
``HookResult``.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from devolaflow.agent_workspace.layers import LAYER_ATTRIBUTION_ALIASES
from devolaflow.agents_md_slice import cached_slice_summary
from devolaflow.harness.capacity import CapacityProfile, capacity_profile
from devolaflow.harness.context_tokens import (
    CONTEXT_TOKEN_EVENT,
    CONTEXT_TOKEN_FIELDS,
    TelemetryGateError,
    _append_context_token_record,
    _append_dispatch_context_token_record,
    _build_context_token_accounting,
    _build_report_telemetry_record,
    _resolve_context_tokens,
    build_context_token_record,
    estimate_text_tokens,
    measure_context_tokens,
    stable_yaml,
)
from devolaflow.harness.dispatch_context import (
    _AttributionError,
    _dispatch_id,
    _dispatch_layer,
    _dispatch_profile,
    _mapping,
    _non_empty_string,
    _resolve_active_change,
    _round_number,
    current_dispatch_context,
    dispatch_context,
)
from devolaflow.harness.metadata import attach_run_metadata
from devolaflow.harness.telemetry_storage import (
    HARNESS_SEGMENT_MAX_BYTES,
    MAX_HARNESS_SEGMENT_BYTES,
    append_harness_record,
)
from devolaflow.harness.tiers import annotate_rule_surfaces, summarize_constraints
from devolaflow.harness.token_injection import (
    TOKEN_COMPONENTS,
    TOKEN_INJECTION_EVENT,
    TOKEN_INJECTION_FIELDS,
    TOKEN_INJECTION_SCHEMA_VERSION,
    TOKEN_INJECTION_SOURCES,
    TokenInjectionError,
    append_token_injection_measurement,
    build_token_injection_measurement,
    ingest_captured_transcript,
    ingest_cli_probe_artifact,
    ingest_measurement_artifact,
    validate_token_injection_measurement,
)
from devolaflow.task_adaptive_selector import estimate_tokens

if TYPE_CHECKING:
    from devolaflow.lifecycle.dispatcher import HookResult

EVENT: Final[str] = "post_dispatch"
CONSOLIDATION_METRICS_EVENT: Final[str] = "consolidation_metrics"
CONSOLIDATION_METRIC_NAMES: Final[tuple[str, ...]] = (
    "estimated_agents_md_tokens",
    "suite_wall_seconds",
    "cjk_violations",
    "ghost_loc",
)
LEGACY_DISPATCH_TOKEN_FIELD: Final[str] = "tokens_injected_measured"
DISPATCH_TOKEN_FIELD: Final[str] = "tokens_injected_estimated"
LEGACY_HOST_RULE_TOKEN_FIELD: Final[str] = "host_rule_tokens"
HOST_RULE_TOKEN_FIELD: Final[str] = "estimated_host_rule_tokens"
LEGACY_AGENTS_MD_TOKEN_FIELD: Final[str] = "agents_md_tokens"
AGENTS_MD_TOKEN_FIELD: Final[str] = "estimated_agents_md_tokens"
TOKEN_ESTIMATOR_FIELD: Final[str] = "token_estimator"
_LEGACY_CONSOLIDATION_METRIC_ALIASES: Final[dict[str, str]] = {
    LEGACY_AGENTS_MD_TOKEN_FIELD: AGENTS_MD_TOKEN_FIELD,
}
_TOKEN_ESTIMATOR_SOURCE: Final[str] = "devolaflow.task_adaptive_selector.estimate_tokens"
_TOKEN_ESTIMATOR_FALLBACK: Final[str] = (
    "when tiktoken is unavailable or fails, use max(1, len(text)//4)"
)
METRIC_OBSERVATION_EVENT: Final[str] = "metric_observation"
METRIC_OBSERVATION_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "cycle",
    "pv",
    "item_id",
    "metric",
    "statistic",
    "value",
    "unit",
    "direction",
    "sample_count",
    "warmup_count",
    "captured_at",
    "source_revision",
    "command",
    "environment",
    "measurement",
)
METRIC_OBSERVATION_MATCH_FIELDS: Final[tuple[str, ...]] = tuple(
    field
    for field in METRIC_OBSERVATION_FIELDS
    if field
    not in {
        "schema_version",
        "cycle",
        "pv",
        "value",
        "captured_at",
        "source_revision",
    }
)
SI10_GATE_EVENT: Final[str] = "si10_gate"
SI10_GATE_NAMES: Final[tuple[str, ...]] = (
    "test-core",
    "lint",
    "test-version",
    "test-harness",
    "check-cursor-skill",
)
SI10_GATE_STATUSES: Final[frozenset[str]] = frozenset({"PASS", "FAIL"})
LAYER_TOKEN_BUDGETS: Final[dict[str, int]] = {
    "L0": 5_000,
    "L1": 5_000,
    "L2": 8_000,
}

_BASE_LEDGER_NAME = "harness.jsonl"
_BEHAVIORAL_GUIDELINES_REF = "workflow-system/agent/references/behavioral-guidelines.md"
# Alias table owned by agent_workspace.layers (A-5 single-owner; merged v17).
_LAYER_ALIASES: Final[dict[str, str]] = LAYER_ATTRIBUTION_ALIASES

logger = logging.getLogger(__name__)

append_context_token_record = _append_context_token_record
build_context_token_accounting = _build_context_token_accounting
build_report_telemetry_record = _build_report_telemetry_record


class MetricObservationError(ValueError):
    """A metric observation is malformed or cannot be compared safely."""


def _capacity_view() -> CapacityProfile:
    """Resolve the capacity profile without ever blocking a dispatch.

    v17.0.0 R5 (D-R5-1): telemetry mirrors the configured round capacity
    (checklist-slice bound) and records the resolved profile in each ledger
    record. Any resolution failure — including a loudly-invalid
    ``meta.capacity`` block, which the DISPATCH path surfaces as a raise —
    degrades here to the hardcoded defaults with a WARNING per S-5, because
    telemetry is observational and must never block.
    """

    try:
        return capacity_profile()
    except Exception as exc:  # noqa: BLE001 - telemetry stays nonblocking
        logger.warning(
            "harness telemetry capacity profile resolution failed: %s; using hardcoded defaults",
            exc,
        )
        return CapacityProfile()


def _checklist_constraint_count(payload: dict[str, Any], *, round_capacity: int) -> int:
    change_context = _mapping(payload, "change_context")
    if change_context is None or "checklist_items" not in change_context:
        return 0
    checklist_items = change_context["checklist_items"]
    if not isinstance(checklist_items, list):
        raise _AttributionError("change_context.checklist_items must be a list")
    if not 1 <= len(checklist_items) <= round_capacity:
        raise _AttributionError(
            f"change_context.checklist_items must contain 1 through {round_capacity} items"
        )
    return len(checklist_items)


def _model_hint(payload: dict[str, Any]) -> str:
    hdr = _mapping(payload, "hdr")
    context = _mapping(payload, "context")
    candidates = (
        payload.get("model_hint"),
        hdr.get("model_hint") if hdr else None,
        context.get("model_hint") if context else None,
    )
    for candidate in candidates:
        if candidate is None:
            continue
        return _non_empty_string(candidate, field="model_hint")
    return "inherit"


def _token_estimator_provenance() -> dict[str, Any]:
    """Describe the local estimator used by dispatch token accounting.

    This metadata deliberately says that the value is not provider usage.
    Import/encoding failures are expected estimator routing conditions; the
    estimator itself logs failures and applies the same fallback semantics.
    """

    try:
        import tiktoken
    except ImportError:
        return {
            "source": _TOKEN_ESTIMATOR_SOURCE,
            "tokenizer": "character_heuristic",
            "model": None,
            "encoding": None,
            "fallback_semantics": _TOKEN_ESTIMATOR_FALLBACK,
            "provider_usage": False,
        }
    try:
        encoder = tiktoken.encoding_for_model("gpt-4o")
    except Exception as exc:  # noqa: BLE001 - provenance must not block telemetry
        logger.warning("token estimator provenance probe failed; recording fallback: %s", exc)
        return {
            "source": _TOKEN_ESTIMATOR_SOURCE,
            "tokenizer": "character_heuristic",
            "model": "gpt-4o",
            "encoding": None,
            "fallback_semantics": _TOKEN_ESTIMATOR_FALLBACK,
            "provider_usage": False,
        }
    return {
        "source": _TOKEN_ESTIMATOR_SOURCE,
        "tokenizer": "tiktoken",
        "model": "gpt-4o",
        "encoding": getattr(encoder, "name", "o200k_base"),
        "fallback_semantics": _TOKEN_ESTIMATOR_FALLBACK,
        "provider_usage": False,
    }


def _dispatch_task_type(payload: dict[str, Any]) -> str:
    """Resolve the dispatch task type for AGENTS.md-slice accounting.

    Resolution order (first non-empty string wins):
      1. ``task.type`` — the canonical work-unit type of BOTH dispatch
         formats (lean ``task: { id, type, title }`` at canonical position
         2 and the verbose original format's ``task.type``; see
         ``schemas/lean-dispatch.yaml#lean_format_spec.task``).
      2. ``context.applicable_rules.task_type`` — the verbose format's
         rule-loading hint (``schemas/lean-dispatch.yaml`` original
         example; mirrored in ``task-dispatch.schema.yaml``).

    Returns ``""`` when unresolvable — the slice module's ``fallback:
    full`` semantics then yield ``slice_savings_pct == 0.0`` with
    ``estimated_host_rule_tokens`` still carrying the full AGENTS.md estimate.
    """

    task = _mapping(payload, "task")
    if task is not None:
        value = task.get("type")
        if isinstance(value, str) and value.strip():
            return value
    context = _mapping(payload, "context")
    if context is not None:
        applicable = context.get("applicable_rules")
        if isinstance(applicable, dict):
            value = applicable.get("task_type")
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _slice_injection_metrics(payload: dict[str, Any]) -> tuple[int, float]:
    """Return ``(estimated_host_rule_tokens, slice_savings_pct)`` for one dispatch.

    v17.0.0 R3 (G17-B3 / D-R3-2) — host injection accounting:

      * ``estimated_host_rule_tokens`` is the FULL AGENTS.md corpus estimate
        (``full_tokens``), because hosts inject the unsliced corpus today;
        the slice is configured but unwired on the host side.
      * ``slice_savings_pct`` is the YAML-CONFIGURED slice's available
        saving for this dispatch's task type. The computation passes
        ``env={}`` so the R5 process-env opt-out
        (``DEVOLAFLOW_AGENTS_MD_SLICE=0``) does NOT zero the ledger — the
        account measures what the configuration offers, deterministically,
        which also keeps the owner module's mtime-keyed cache valid
        without an env component per record.

    The summary comes from the module-level cache in
    ``devolaflow.agents_md_slice`` (keyed on AGENTS.md path + mtime_ns +
    task_type), so appending records never re-reads AGENTS.md. Any
    failure degrades to ``(0, 0.0)`` with a WARNING per S-5 — telemetry
    must never block a dispatch.
    """

    try:
        summary = cached_slice_summary(_dispatch_task_type(payload), env={})
        return summary["full_tokens"], float(summary["slice_savings_pct"])
    except Exception as exc:  # noqa: BLE001 - telemetry stays nonblocking
        logger.warning(
            "harness telemetry AGENTS.md slice accounting failed: %s; "
            "estimated_host_rule_tokens/slice_savings_pct zeroed",
            exc,
        )
        return 0, 0.0


def _constraint_summary_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Return an annotated copy without advisory-fold metadata."""

    view = dict(payload)
    behavioral = _mapping(payload, "behavioral_guidelines")
    if behavioral is not None and "advisory_folded" in behavioral:
        view["behavioral_guidelines"] = {
            name: value for name, value in behavioral.items() if name != "advisory_folded"
        }
    return annotate_rule_surfaces(view)


def _behavioral_advisory_count(summary_view: dict[str, Any]) -> int:
    """Count active advisory constraints from behavioral guidelines only."""

    behavioral = _mapping(summary_view, "behavioral_guidelines")
    if behavioral is None:
        return 0
    _, breakdown, _ = summarize_constraints({"behavioral_guidelines": behavioral})
    return breakdown["advisory"]


def build_dispatch_record(
    payload: dict[str, Any],
    *,
    change_id: str,
    timestamp: str | None = None,
    measurements: Mapping[str, object] | None = None,
    context_tokens: Mapping[str, object] | None = None,
    skill_text: str | None = None,
    rule_text: str | None = None,
    report_envelope: Mapping[str, Any] | str | None = None,
    profile: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one exact-schema harness record from a dispatch payload.

    v17.0.0 R3 (G17-B3 / D-R3-2) appended two host-injection accounting
    fields: ``estimated_host_rule_tokens`` (full AGENTS.md corpus estimate — hosts
    inject the unsliced corpus) and ``slice_savings_pct`` (the configured
    slice's available saving for this dispatch's task type, resolved per
    :func:`_dispatch_task_type` / :func:`_slice_injection_metrics`).
    v17.0.0 R5 (G17-B6 / D-R5-1) appended ``capacity_profile`` — the
    resolved round capacity + executor concurrency with aggregate
    provenance (``"config"`` when any ``meta.capacity`` field is declared,
    else ``"default"``). All three are OPTIONAL for the aggregator — old
    ledgers keep aggregating.
    """

    if not isinstance(payload, dict):
        raise _AttributionError("payload must be a dict")
    if measurements is not None and not isinstance(measurements, Mapping):
        raise _AttributionError("measurements must be a mapping")
    if measurements is not None:
        unknown = sorted(set(measurements) - set(CONSOLIDATION_METRIC_NAMES))
        if unknown:
            raise _AttributionError(f"unsupported consolidation metric(s): {', '.join(unknown)}")
    attributed_change_id = _non_empty_string(change_id, field="change_id")
    if Path(attributed_change_id).name != attributed_change_id:
        raise _AttributionError("change_id must be one active-folder basename")

    capacity_view = _capacity_view()
    layer = _dispatch_layer(payload)
    _checklist_constraint_count(payload, round_capacity=capacity_view.round_capacity)
    summary_view = _constraint_summary_view(payload)
    constraint_count, tier_breakdown, quantifiable_ratio = summarize_constraints(summary_view)
    behavioral = _mapping(payload, "behavioral_guidelines")
    advisory_folded = behavioral is not None and behavioral.get("advisory_folded") is True
    model_hint = _model_hint(payload)
    estimated = estimate_tokens(stable_yaml(payload))
    estimated_host_rule_tokens, slice_savings_pct = _slice_injection_metrics(payload)
    estimator_provenance = _token_estimator_provenance()
    resolved_context_tokens = _resolve_context_tokens(
        payload,
        context_tokens,
        skill_text=skill_text,
        rule_text=rule_text,
        report_envelope=report_envelope,
    )
    if profile is not None:
        profile = _non_empty_string(profile, field="profile")
    record_timestamp = timestamp or datetime.now(UTC).isoformat()

    record = {
        "ts": record_timestamp,
        "change_id": attributed_change_id,
        "round": _round_number(payload),
        "layer": layer,
        "dispatch_id": _dispatch_id(payload),
        DISPATCH_TOKEN_FIELD: estimated,
        "tokens_budget": LAYER_TOKEN_BUDGETS[layer],
        "constraint_count": constraint_count,
        "quantifiable_ratio": quantifiable_ratio,
        "tier_breakdown": tier_breakdown,
        "advisory_folded": advisory_folded,
        "model_hint": model_hint,
        HOST_RULE_TOKEN_FIELD: estimated_host_rule_tokens,
        "slice_savings_pct": slice_savings_pct,
        "capacity_profile": {
            "round_capacity": capacity_view.round_capacity,
            "max_concurrency": capacity_view.max_concurrency,
            "source": capacity_view.source,
        },
        # v18.0.0 — explicit full AGENTS.md token metric for rule-slimming.
        AGENTS_MD_TOKEN_FIELD: estimated_host_rule_tokens,
        TOKEN_ESTIMATOR_FIELD: estimator_provenance,
    }
    if profile is not None:
        record["profile"] = profile
    if measurements:
        for name in CONSOLIDATION_METRIC_NAMES:
            if name == AGENTS_MD_TOKEN_FIELD:
                continue
            if name in measurements:
                record[name] = _validate_measurement_value(name, measurements[name])
    if advisory_folded:
        record["fold_trace"] = {
            "folded_count": _behavioral_advisory_count(summary_view),
            "ref": _BEHAVIORAL_GUIDELINES_REF,
            "model_hint": model_hint,
        }
    if resolved_context_tokens is not None:
        record["context_tokens"] = resolved_context_tokens
    return attach_run_metadata(record, metadata)


def _validate_measurement_value(name: str, value: object) -> int | float | None:
    if value is None:
        return None
    if name in {AGENTS_MD_TOKEN_FIELD, "cjk_violations", "ghost_loc"}:
        if type(value) is not int or value < 0:
            raise TelemetryGateError(f"{name} must be a non-negative integer or null")
        return value
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise TelemetryGateError(f"{name} must be a non-negative number or null")
    return float(value)


def _validate_observation_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MetricObservationError("captured_at must be a non-empty string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MetricObservationError("captured_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise MetricObservationError("captured_at must include a timezone")
    return value


def _validate_observation_command(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"argv", "cwd", "timeout_seconds"}:
        raise MetricObservationError("command must contain exactly argv, cwd, and timeout_seconds")
    argv = value["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(argument, str) or not argument for argument in argv)
    ):
        raise MetricObservationError("command.argv must be a non-empty string list")
    cwd = value["cwd"]
    if (
        not isinstance(cwd, str)
        or not cwd.strip()
        or Path(cwd).is_absolute()
        or cwd.startswith("~")
        or ".." in Path(cwd).parts
    ):
        raise MetricObservationError("command.cwd must be a repository-relative path")
    timeout = value["timeout_seconds"]
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or float(timeout) <= 0
    ):
        raise MetricObservationError("command.timeout_seconds must be a positive finite number")
    return {
        "argv": list(argv),
        "cwd": cwd,
        "timeout_seconds": timeout,
    }


def _validate_observation_environment(value: object) -> dict[str, Any]:
    required = {
        "os",
        "architecture",
        "python",
        "implementation",
        "dependencies",
        "relevant_variables",
        "config_files",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise MetricObservationError(
            "environment must contain complete OS, Python, dependency, variable, and config data"
        )
    for field in ("os", "architecture", "python", "implementation", "dependencies"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise MetricObservationError(f"environment.{field} must be a non-empty string")
    relevant_variables = value["relevant_variables"]
    if not isinstance(relevant_variables, Mapping) or any(
        not isinstance(key, str) or not isinstance(variable, str)
        for key, variable in relevant_variables.items()
    ):
        raise MetricObservationError(
            "environment.relevant_variables must map string names to string values"
        )
    config_files = value["config_files"]
    if not isinstance(config_files, list):
        raise MetricObservationError("environment.config_files must be a list")
    normalized_files: list[dict[str, str]] = []
    for index, config_file in enumerate(config_files):
        if not isinstance(config_file, Mapping) or set(config_file) != {"path", "sha256"}:
            raise MetricObservationError(
                f"environment.config_files[{index}] must contain path and sha256"
            )
        path = config_file["path"]
        digest = config_file["sha256"]
        if (
            not isinstance(path, str)
            or not path.strip()
            or Path(path).is_absolute()
            or path.startswith("~")
            or ".." in Path(path).parts
        ):
            raise MetricObservationError(
                f"environment.config_files[{index}].path must be repository-relative"
            )
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise MetricObservationError(
                f"environment.config_files[{index}].sha256 must be lowercase SHA-256"
            )
        normalized_files.append({"path": path, "sha256": digest})
    return {
        "os": value["os"],
        "architecture": value["architecture"],
        "python": value["python"],
        "implementation": value["implementation"],
        "dependencies": value["dependencies"],
        "relevant_variables": dict(relevant_variables),
        "config_files": normalized_files,
    }


def _validate_observation_measurement(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {
        "cache_state",
        "extraction_definition",
        "provenance",
    }:
        raise MetricObservationError(
            "measurement must contain exactly cache_state, extraction_definition, and provenance"
        )
    normalized: dict[str, str] = {}
    for field in ("cache_state", "extraction_definition", "provenance"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise MetricObservationError(f"measurement.{field} must be a non-empty string")
        normalized[field] = value[field]
    return normalized


def validate_metric_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one complete PV-2 metric observation.

    Validation is intentionally strict for new observations. Legacy scalar
    dispatch and consolidation records are validated by their historical
    schemas and never receive fabricated provenance fields.
    """

    if not isinstance(observation, Mapping):
        raise MetricObservationError("metric observation must be a mapping")
    if set(observation) != set(METRIC_OBSERVATION_FIELDS):
        missing = sorted(set(METRIC_OBSERVATION_FIELDS) - set(observation))
        extra = sorted(set(observation) - set(METRIC_OBSERVATION_FIELDS))
        raise MetricObservationError(
            f"metric observation keys mismatch; missing={missing}, extra={extra}"
        )
    if observation["schema_version"] != 1:
        raise MetricObservationError("metric observation schema_version must equal 1")
    for field in (
        "cycle",
        "pv",
        "item_id",
        "metric",
        "statistic",
        "unit",
        "direction",
        "source_revision",
    ):
        if not isinstance(observation[field], str) or not observation[field].strip():
            raise MetricObservationError(f"{field} must be a non-empty string")
    if observation["direction"] not in {"increase", "decrease"}:
        raise MetricObservationError("direction must be increase or decrease")
    value = observation["value"]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise MetricObservationError("value must be a finite non-negative number")
    for field in ("sample_count", "warmup_count"):
        count = observation[field]
        if type(count) is not int or count < 0:
            raise MetricObservationError(f"{field} must be a non-negative integer")
    if observation["sample_count"] < 1:
        raise MetricObservationError("sample_count must be at least 1")
    _validate_observation_timestamp(observation["captured_at"])
    return {
        "schema_version": 1,
        "cycle": observation["cycle"],
        "pv": observation["pv"],
        "item_id": observation["item_id"],
        "metric": observation["metric"],
        "statistic": observation["statistic"],
        "value": value,
        "unit": observation["unit"],
        "direction": observation["direction"],
        "sample_count": observation["sample_count"],
        "warmup_count": observation["warmup_count"],
        "captured_at": observation["captured_at"],
        "source_revision": observation["source_revision"],
        "command": _validate_observation_command(observation["command"]),
        "environment": _validate_observation_environment(observation["environment"]),
        "measurement": _validate_observation_measurement(observation["measurement"]),
    }


def build_metric_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Build one validated observation without adding unavailable metadata."""

    return validate_metric_observation(observation)


def build_metric_observation_record(
    observation: Mapping[str, Any],
    *,
    event_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap one validated observation as an append-only JSONL ledger event."""

    normalized = build_metric_observation(observation)
    resolved_event_id = event_id or (
        f"{METRIC_OBSERVATION_EVENT}:{normalized['item_id']}:"
        f"{normalized['metric']}:{normalized['captured_at']}"
    )
    if not isinstance(resolved_event_id, str) or not resolved_event_id.strip():
        raise MetricObservationError("event_id must be a non-empty string")
    record = {
        "schema_version": 1,
        "event": METRIC_OBSERVATION_EVENT,
        "event_id": resolved_event_id,
        **{
            field: normalized[field]
            for field in METRIC_OBSERVATION_FIELDS
            if field != "schema_version"
        },
    }
    return attach_run_metadata(record, metadata)


def append_metric_observation(
    ledger: str | Path,
    observation: Mapping[str, Any],
    *,
    event_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    """Append one validated structured observation, preserving prior bytes."""

    path = Path(ledger)
    if path.exists() and not path.is_file():
        raise MetricObservationError(f"telemetry ledger must be a file: {path}")
    record = build_metric_observation_record(observation, event_id=event_id, metadata=metadata)
    if path.name == _BASE_LEDGER_NAME:
        path.parent.mkdir(parents=True, exist_ok=True)
        written = append_harness_record(path.parent, record)
        if written is None:
            raise MetricObservationError(f"cannot append metric observation to {path}")
        return written
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        with path.open("ab") as stream:
            stream.write(encoded)
    except (OSError, TypeError, ValueError) as exc:
        raise MetricObservationError(f"cannot append metric observation to {path}: {exc}") from exc
    return path


def _comparison_provenance(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_revision": observation["source_revision"],
        "command": observation["command"],
        "environment": observation["environment"],
        "measurement": observation["measurement"],
    }


def _observation_payload(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
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


def build_consolidation_metrics_record(
    measurements: Mapping[str, object],
    *,
    timestamp: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one append-only record for the v18 consolidation measurements.

    Every metric is present in the event envelope. ``None`` is intentional:
    it records that a source was unavailable rather than estimating a value.
    """

    if not isinstance(measurements, Mapping):
        raise TelemetryGateError("measurements must be a mapping")
    normalized_measurements: dict[str, object] = {}
    unknown: list[str] = []
    for name, value in measurements.items():
        canonical_name = _LEGACY_CONSOLIDATION_METRIC_ALIASES.get(name, name)
        if canonical_name not in CONSOLIDATION_METRIC_NAMES:
            unknown.append(str(name))
            continue
        if canonical_name in normalized_measurements:
            raise TelemetryGateError(
                f"duplicate consolidation metric aliases for {canonical_name}: {name}"
            )
        normalized_measurements[canonical_name] = value
    if unknown:
        raise TelemetryGateError(f"unsupported consolidation metric(s): {', '.join(unknown)}")
    record = {
        "schema_version": 1,
        "event": CONSOLIDATION_METRICS_EVENT,
        "event_id": f"{CONSOLIDATION_METRICS_EVENT}:{timestamp or 'generated'}",
        "ts": timestamp or datetime.now(UTC).isoformat(),
        **{
            name: _validate_measurement_value(name, normalized_measurements.get(name))
            for name in CONSOLIDATION_METRIC_NAMES
        },
        TOKEN_ESTIMATOR_FIELD: _token_estimator_provenance(),
    }
    return attach_run_metadata(record, metadata)


def append_consolidation_metrics(
    ledger: str | Path,
    measurements: Mapping[str, object],
    *,
    timestamp: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    """Append one complete v18 measurement envelope without rewriting history."""

    path = Path(ledger)
    if path.exists() and not path.is_file():
        raise TelemetryGateError(f"telemetry ledger must be a file: {path}")
    record = build_consolidation_metrics_record(
        measurements,
        timestamp=timestamp,
        metadata=metadata,
    )
    if path.name == _BASE_LEDGER_NAME:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            written = append_harness_record(path.parent, record)
        except OSError as exc:
            raise TelemetryGateError(f"cannot append telemetry ledger {path}: {exc}") from exc
        if written is None:
            raise TelemetryGateError(f"cannot append telemetry ledger {path}: record rejected")
        return written
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        with path.open("ab") as stream:
            stream.write(encoded)
    except (OSError, TypeError, ValueError) as exc:
        raise TelemetryGateError(f"cannot append telemetry ledger {path}: {exc}") from exc
    return path


def build_gate_record(
    pv: str,
    gate: str,
    status: str,
    *,
    timestamp: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one schema-versioned SI-10 gate event.

    Gate events are additive records. Existing dispatch and proposal event
    bytes remain untouched, while the event envelope lets the aggregator
    validate and retain the new evidence without treating it as a dispatch
    record.
    """

    if not isinstance(pv, str) or not pv.strip():
        raise TelemetryGateError("pv must be a non-empty string")
    if not isinstance(gate, str) or gate not in SI10_GATE_NAMES:
        raise TelemetryGateError(f"gate must be one of {SI10_GATE_NAMES!r}")
    if not isinstance(status, str) or status not in SI10_GATE_STATUSES:
        raise TelemetryGateError("status must be PASS or FAIL")
    event_id = f"{SI10_GATE_EVENT}:{pv}:{gate}:{status}"
    record = {
        "schema_version": 1,
        "event": SI10_GATE_EVENT,
        "event_id": event_id,
        "ts": timestamp or datetime.now(UTC).isoformat(),
        "pv": pv,
        "gate": gate,
        "status": status,
    }
    return attach_run_metadata(record, metadata)


def append_gate_telemetry(
    ledger: str | Path,
    pv: str,
    gate: str,
    status: str,
    *,
    timestamp: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    """Append one SI-10 gate event to a repository telemetry ledger.

    The parent directory is created for the first gate record. Appending is
    deliberately compact JSONL so existing ledger records and their bytes are
    never rewritten.
    """

    path = Path(ledger)
    if path.exists() and not path.is_file():
        raise TelemetryGateError(f"telemetry ledger must be a file: {path}")
    record = build_gate_record(pv, gate, status, timestamp=timestamp, metadata=metadata)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        with path.open("ab") as stream:
            stream.write(encoded)
    except (OSError, TypeError, ValueError) as exc:
        raise TelemetryGateError(f"cannot append telemetry ledger {path}: {exc}") from exc
    return path


def check_gate_telemetry(
    ledger: str | Path,
    pv: str,
    *,
    required_gates: tuple[str, ...] = SI10_GATE_NAMES,
    historical: bool = False,
) -> dict[str, object]:
    """Verify PASS evidence for every SI-10 gate in one PV.

    A current-PV check fails closed when no matching record exists. Historical
    absence is explicit ``INSUFFICIENT`` evidence so missing old data is not
    misreported as a current gate failure.
    """

    if not isinstance(pv, str) or not pv.strip():
        raise TelemetryGateError("pv must be a non-empty string")
    if not required_gates or any(gate not in SI10_GATE_NAMES for gate in required_gates):
        raise TelemetryGateError("required_gates contains an unsupported SI-10 gate")

    try:
        from devolaflow.harness.aggregator import AggregationError, load_ledger_records

        records = load_ledger_records(ledger)
    except AggregationError as exc:
        if historical:
            return {
                "schema_version": 1,
                "pv": pv,
                "verdict": "INSUFFICIENT",
                "reason": f"historical telemetry unavailable: {exc}",
            }
        if "ledger path does not exist" in str(exc):
            raise TelemetryGateError(f"no telemetry record for PV {pv!r}") from exc
        raise TelemetryGateError(f"current PV telemetry unavailable: {exc}") from exc
    except OSError as exc:
        if historical:
            return {
                "schema_version": 1,
                "pv": pv,
                "verdict": "INSUFFICIENT",
                "reason": f"historical telemetry unavailable: {exc}",
            }
        raise TelemetryGateError(f"current PV telemetry unavailable: {exc}") from exc

    matching = [
        record
        for record in records
        if record.get("event") == SI10_GATE_EVENT and record.get("pv") == pv
    ]
    if not matching:
        if historical:
            return {
                "schema_version": 1,
                "pv": pv,
                "verdict": "INSUFFICIENT",
                "reason": "historical telemetry has no record for PV",
            }
        raise TelemetryGateError(f"no telemetry record for PV {pv!r}")

    statuses = {
        gate: next(
            (
                record["status"] == "PASS"
                for record in reversed(matching)
                if record.get("gate") == gate
            ),
            False,
        )
        for gate in required_gates
    }
    missing = [gate for gate, passed in statuses.items() if not passed]
    if missing:
        raise TelemetryGateError(
            f"PV {pv!r} lacks PASS telemetry for gate(s): {', '.join(missing)}"
        )
    return {
        "schema_version": 1,
        "pv": pv,
        "verdict": "PASS",
        "gates": list(required_gates),
    }


def record_dispatch_telemetry(
    payload: dict[str, Any],
    *,
    strict: bool = False,
    repo_root: str | Path | None = None,
    context_tokens: Mapping[str, object] | None = None,
    skill_text: str | None = None,
    rule_text: str | None = None,
    report_envelope: Mapping[str, Any] | str | None = None,
    profile: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> HookResult:
    """Nonblocking ``post_dispatch`` extra that records harness telemetry."""

    from devolaflow.lifecycle.dispatcher import HookResult

    del strict  # Telemetry is observational and never raises in strict mode.
    result = HookResult(event=EVENT)
    try:
        if not isinstance(payload, dict):
            raise _AttributionError("payload must be a dict")
        root = Path.cwd() if repo_root is None else Path(repo_root)
        change_folder = _resolve_active_change(payload, repo_root=root, log=logger)
        if change_folder is None:
            result.metadata["reason"] = "no unambiguous active change"
            return result

        emission_context = current_dispatch_context()
        if emission_context is not None:
            context_tokens = (
                context_tokens if context_tokens is not None else emission_context["context_tokens"]
            )
            skill_text = skill_text if skill_text is not None else emission_context["skill_text"]
            rule_text = rule_text if rule_text is not None else emission_context["rule_text"]
            report_envelope = (
                report_envelope
                if report_envelope is not None
                else emission_context["report_envelope"]
            )
            profile = profile if profile is not None else emission_context["profile"]
            metadata = metadata if metadata is not None else emission_context["metadata"]
        requested = emission_context is not None
        if profile is None:
            profile = _dispatch_profile(payload)

        record = build_dispatch_record(
            payload,
            change_id=change_folder.name,
            context_tokens=context_tokens,
            skill_text=skill_text,
            rule_text=rule_text,
            report_envelope=report_envelope,
            profile=profile,
            metadata=metadata,
        )
        written_path = append_harness_record(change_folder, record)
        if written_path is None:
            result.metadata["reason"] = "telemetry record not written"
        else:
            result.metadata["path"] = str(written_path)
            accounting = record.get("context_tokens")
            if accounting is not None or requested:
                result.metadata["context_tokens"] = _append_dispatch_context_token_record(
                    change_folder / _BASE_LEDGER_NAME,
                    dispatch_id=record["dispatch_id"],
                    timestamp=record["ts"],
                    accounting=accounting,
                    metadata=metadata,
                    append_record=append_context_token_record,
                )
        return result
    except Exception as exc:  # noqa: BLE001 - hook boundary must remain nonblocking
        logger.warning(
            "harness telemetry attribution failed: %s; dispatch continues unchanged",
            exc,
        )
        result.metadata["reason"] = "telemetry attribution failed"
        return result


__all__ = [
    "AGENTS_MD_TOKEN_FIELD",
    "HARNESS_SEGMENT_MAX_BYTES",
    "LAYER_TOKEN_BUDGETS",
    "MAX_HARNESS_SEGMENT_BYTES",
    "CONSOLIDATION_METRIC_NAMES",
    "CONSOLIDATION_METRICS_EVENT",
    "DISPATCH_TOKEN_FIELD",
    "CONTEXT_TOKEN_EVENT",
    "CONTEXT_TOKEN_FIELDS",
    "current_dispatch_context",
    "dispatch_context",
    "METRIC_OBSERVATION_EVENT",
    "METRIC_OBSERVATION_FIELDS",
    "METRIC_OBSERVATION_MATCH_FIELDS",
    "TOKEN_COMPONENTS",
    "TOKEN_INJECTION_EVENT",
    "TOKEN_INJECTION_FIELDS",
    "TOKEN_INJECTION_SCHEMA_VERSION",
    "TOKEN_INJECTION_SOURCES",
    "TOKEN_ESTIMATOR_FIELD",
    "HOST_RULE_TOKEN_FIELD",
    "LEGACY_AGENTS_MD_TOKEN_FIELD",
    "LEGACY_DISPATCH_TOKEN_FIELD",
    "LEGACY_HOST_RULE_TOKEN_FIELD",
    "SI10_GATE_EVENT",
    "SI10_GATE_NAMES",
    "SI10_GATE_STATUSES",
    "append_harness_record",
    "append_consolidation_metrics",
    "append_context_token_record",
    "append_metric_observation",
    "append_token_injection_measurement",
    "append_gate_telemetry",
    "build_gate_record",
    "build_dispatch_record",
    "build_context_token_accounting",
    "build_context_token_record",
    "build_consolidation_metrics_record",
    "build_metric_observation",
    "build_metric_observation_record",
    "build_token_injection_measurement",
    "build_report_telemetry_record",
    "compare_metric_observations",
    "compare_metric_observation_sets",
    "check_gate_telemetry",
    "record_dispatch_telemetry",
    "ingest_captured_transcript",
    "ingest_cli_probe_artifact",
    "ingest_measurement_artifact",
    "estimate_text_tokens",
    "measure_context_tokens",
    "stable_yaml",
    "TelemetryGateError",
    "MetricObservationError",
    "TokenInjectionError",
    "validate_metric_observation",
    "validate_token_injection_measurement",
]
