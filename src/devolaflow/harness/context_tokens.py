"""Context-token accounting and append-only report telemetry."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml

from devolaflow.harness.metadata import attach_run_metadata
from devolaflow.harness.telemetry_storage import append_harness_record
from devolaflow.task_adaptive_selector import estimate_tokens

CONTEXT_TOKEN_FIELDS: Final[tuple[str, ...]] = (
    "skill_tokens",
    "rule_tokens",
    "report_tokens",
)
CONTEXT_TOKEN_EVENT: Final[str] = "context_token_accounting"
_BASE_LEDGER_NAME = "harness.jsonl"


class TelemetryGateError(ValueError):
    """A required SI-10 telemetry record is absent or unsuccessful."""


def stable_yaml(payload: dict[str, Any]) -> str:
    """Render deterministic measurement input independent of mapping order."""
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    )


def estimate_text_tokens(text: str | None, *, field: str = "text") -> int | None:
    """Estimate supplied text locally, not observe provider usage."""
    if text is None:
        return None
    if not isinstance(text, str):
        raise TypeError(f"{field} must be a string or None")
    return 0 if text == "" else estimate_tokens(text)


def _report_measurement_text(report_envelope: Mapping[str, Any] | str | None) -> str | None:
    if report_envelope is None:
        return None
    if isinstance(report_envelope, str):
        return report_envelope
    if isinstance(report_envelope, Mapping):
        if not report_envelope:
            return ""
        return stable_yaml(dict(report_envelope))
    raise TypeError("report_envelope must be a mapping, string, or None")


def measure_context_tokens(
    *,
    skill_text: str | None = None,
    rule_text: str | None = None,
    report_envelope: Mapping[str, Any] | str | None = None,
) -> dict[str, int | None]:
    """Return independent token counts for supplied context components.

    ``None`` means the caller did not provide that component; empty supplied
    text/structures are measured as zero. This function performs no implicit
    file reads.
    """
    return {
        "skill_tokens": estimate_text_tokens(skill_text, field="skill_text"),
        "rule_tokens": estimate_text_tokens(rule_text, field="rule_text"),
        "report_tokens": estimate_text_tokens(
            _report_measurement_text(report_envelope),
            field="report_envelope",
        ),
    }


def _normalize_context_tokens(value: Mapping[str, object]) -> dict[str, int | None]:
    if not isinstance(value, Mapping):
        raise TelemetryGateError("context_tokens must be a mapping")
    unknown = sorted(set(value) - set(CONTEXT_TOKEN_FIELDS))
    if unknown:
        raise TelemetryGateError(f"unsupported context token field(s): {', '.join(unknown)}")
    normalized: dict[str, int | None] = {}
    for field in CONTEXT_TOKEN_FIELDS:
        token_count = value.get(field)
        if token_count is None:
            normalized[field] = None
        elif type(token_count) is int and token_count >= 0:
            normalized[field] = token_count
        else:
            raise TelemetryGateError(f"{field} must be a non-negative integer or null")
    return normalized


def _build_context_token_accounting(
    *,
    skill_text: str | None = None,
    rule_text: str | None = None,
    report_envelope: Mapping[str, Any] | str | None = None,
) -> dict[str, int | None]:
    """Build accounting from caller-provided context components."""
    return measure_context_tokens(
        skill_text=skill_text,
        rule_text=rule_text,
        report_envelope=report_envelope,
    )


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    return value if isinstance(value, dict) else None


def _payload_context_tokens(payload: dict[str, Any]) -> Mapping[str, object] | None:
    """Read explicitly supplied nested accounting without performing I/O."""
    direct = payload.get("context_tokens")
    if isinstance(direct, Mapping):
        return direct
    for parent_key in ("context", "telemetry"):
        parent = _mapping(payload, parent_key)
        if parent is None:
            continue
        for key in ("context_tokens", "token_accounting"):
            candidate = parent.get(key)
            if isinstance(candidate, Mapping):
                return candidate
    return None


def _payload_context_sources(
    payload: dict[str, Any],
) -> tuple[str | None, str | None, Mapping[str, Any] | str | None, int | None] | None:
    """Measure selector-shaped context without reading files.

    ``select_context`` returns ``assembled_text`` plus an AGENTS.md slice
    summary rather than the sliced corpus itself.  The summary's
    ``total_tokens`` is an explicitly supplied selector estimate, not a
    provider observation; absent components remain ``None`` rather than being
    inferred from the dispatch payload.
    """
    containers: list[Mapping[str, Any]] = [payload]
    for parent_key in ("context", "telemetry"):
        parent = payload.get(parent_key)
        if isinstance(parent, Mapping):
            containers.append(parent)

    skill_text: str | None = None
    rule_text: str | None = None
    report_envelope: Mapping[str, Any] | str | None = None
    selector_rule_tokens: int | None = None
    source_found = False
    for container in containers:
        for key in ("skill_text", "skill_context", "assembled_text"):
            value = container.get(key)
            if isinstance(value, str):
                skill_text = value
                source_found = True
                break
        for key in ("rule_text", "rules_text", "agents_md_text", "agents_md"):
            value = container.get(key)
            if isinstance(value, str):
                rule_text = value
                source_found = True
                break
        for key in ("report_envelope", "report", "status_report"):
            value = container.get(key)
            if isinstance(value, (str, Mapping)):
                report_envelope = value
                source_found = True
                break
        slice_summary = container.get("agents_md_slice")
        if isinstance(slice_summary, Mapping):
            value = slice_summary.get("total_tokens")
            if type(value) is int and value >= 0:
                selector_rule_tokens = value
                source_found = True

    if not source_found:
        return None
    return skill_text, rule_text, report_envelope, selector_rule_tokens


def context_tokens_from_payload(payload: dict[str, Any]) -> dict[str, int | None] | None:
    """Return explicit or selector-provided accounting from a dispatch.

    This is intentionally a zero-IO adapter.  It recognizes only context
    values that the caller supplied, including the selector's explicit
    ``agents_md_slice.total_tokens`` estimate.
    """
    explicit = _payload_context_tokens(payload)
    if explicit is not None:
        return _normalize_context_tokens(explicit)
    sources = _payload_context_sources(payload)
    if sources is None:
        return None
    skill_text, rule_text, report_envelope, selector_rule_tokens = sources
    accounting = measure_context_tokens(
        skill_text=skill_text,
        rule_text=rule_text,
        report_envelope=report_envelope,
    )
    if selector_rule_tokens is not None:
        accounting["rule_tokens"] = selector_rule_tokens
    return accounting


def _resolve_context_tokens(
    payload: dict[str, Any],
    context_tokens: Mapping[str, object] | None,
    *,
    skill_text: str | None,
    rule_text: str | None,
    report_envelope: Mapping[str, Any] | str | None,
) -> dict[str, int | None] | None:
    text_supplied = any(value is not None for value in (skill_text, rule_text, report_envelope))
    if context_tokens is not None and text_supplied:
        raise TelemetryGateError("provide context_tokens or source text, not both")
    if context_tokens is not None:
        return _normalize_context_tokens(context_tokens)
    if text_supplied:
        return measure_context_tokens(
            skill_text=skill_text,
            rule_text=rule_text,
            report_envelope=report_envelope,
        )
    return context_tokens_from_payload(payload)


def build_context_token_record(
    report_envelope: Mapping[str, Any] | str | None = None,
    *,
    skill_text: str | None = None,
    rule_text: str | None = None,
    context_tokens: Mapping[str, object] | None = None,
    timestamp: str | None = None,
    event_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an append-only report/status context-token telemetry event."""
    if context_tokens is not None and any(
        value is not None for value in (skill_text, rule_text, report_envelope)
    ):
        raise TelemetryGateError("provide context_tokens or source text, not both")
    accounting = (
        _normalize_context_tokens(context_tokens)
        if context_tokens is not None
        else measure_context_tokens(
            skill_text=skill_text,
            rule_text=rule_text,
            report_envelope=report_envelope,
        )
    )
    record_timestamp = timestamp or datetime.now(UTC).isoformat()
    resolved_event_id = event_id or f"{CONTEXT_TOKEN_EVENT}:{record_timestamp}"
    if not isinstance(resolved_event_id, str) or not resolved_event_id.strip():
        raise TelemetryGateError("event_id must be a non-empty string")
    record = {
        "schema_version": 1,
        "event": CONTEXT_TOKEN_EVENT,
        "event_id": resolved_event_id,
        "ts": record_timestamp,
        "context_tokens": accounting,
    }
    return attach_run_metadata(record, metadata)


def _build_report_telemetry_record(
    report_envelope: Mapping[str, Any] | str | None = None,
    *,
    skill_text: str | None = None,
    rule_text: str | None = None,
    context_tokens: Mapping[str, object] | None = None,
    timestamp: str | None = None,
    event_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the explicit report/status telemetry record surface."""
    return build_context_token_record(
        report_envelope,
        skill_text=skill_text,
        rule_text=rule_text,
        context_tokens=context_tokens,
        timestamp=timestamp,
        event_id=event_id,
        metadata=metadata,
    )


def _append_context_token_record(
    ledger: str | Path,
    report_envelope: Mapping[str, Any] | str | None,
    *,
    skill_text: str | None = None,
    rule_text: str | None = None,
    context_tokens: Mapping[str, object] | None = None,
    timestamp: str | None = None,
    event_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    """Append one report/status context-token event to a telemetry ledger."""
    path = Path(ledger)
    if path.exists() and not path.is_file():
        raise TelemetryGateError(f"telemetry ledger must be a file: {path}")
    record = build_context_token_record(
        report_envelope,
        skill_text=skill_text,
        rule_text=rule_text,
        context_tokens=context_tokens,
        timestamp=timestamp,
        event_id=event_id,
        metadata=metadata,
    )
    if path.name == _BASE_LEDGER_NAME:
        path.parent.mkdir(parents=True, exist_ok=True)
        written = append_harness_record(path.parent, record)
        if written is None:
            raise TelemetryGateError(f"cannot append context token record to {path}")
        return written
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        with path.open("ab") as stream:
            stream.write(encoded)
    except (OSError, TypeError, ValueError) as exc:
        raise TelemetryGateError(f"cannot append context token record to {path}: {exc}") from exc
    return path


def _append_dispatch_context_token_record(
    ledger: str | Path,
    *,
    dispatch_id: str,
    timestamp: str,
    accounting: Mapping[str, int | None] | None,
    metadata: Mapping[str, Any] | None,
    append_record: Any,
) -> dict[str, int | None]:
    """Emit the context-token event paired with one dispatch record."""
    resolved = accounting or {
        "skill_tokens": None,
        "rule_tokens": None,
        "report_tokens": None,
    }
    append_record(
        ledger,
        None,
        context_tokens=resolved,
        timestamp=timestamp,
        event_id=f"{CONTEXT_TOKEN_EVENT}:{dispatch_id}:{timestamp}",
        metadata=metadata,
    )
    return resolved


__all__ = [
    "CONTEXT_TOKEN_EVENT",
    "CONTEXT_TOKEN_FIELDS",
    "TelemetryGateError",
    "build_context_token_record",
    "context_tokens_from_payload",
    "estimate_text_tokens",
    "measure_context_tokens",
    "stable_yaml",
]
