"""Measured token-injection records and offline artifact ingestion.

This module is deliberately separate from CLI execution.  It consumes
already-produced probe/capture artifacts and writes only append-only harness
events.  A missing observation is represented by ``null`` and
``INSUFFICIENT``; no value is inferred from AGENTS.md or another estimate.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import yaml
from jsonschema import Draft202012Validator

from devolaflow.harness.telemetry_storage import append_harness_record

TOKEN_INJECTION_EVENT: Final[str] = "token_injection_measurement"
TOKEN_INJECTION_SCHEMA_VERSION: Final[int] = 1
TOKEN_INJECTION_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "event",
    "event_id",
    "ts",
    "host",
    "channel",
    "layer",
    "profile",
    "run_id",
    "run_id_status",
    "salt",
    "salt_status",
    "repo_ref",
    "repo_ref_status",
    "repo_sha",
    "repo_sha_status",
    "source",
    "provenance",
    "skill_tokens",
    "skill_status",
    "rule_tokens",
    "rule_status",
    "report_tokens",
    "report_status",
    "context_tokens",
    "context_status",
    "uncertainty",
    "status",
)
TOKEN_COMPONENTS: Final[tuple[str, ...]] = ("skill", "rule", "report", "context")
TOKEN_INJECTION_SOURCES: Final[frozenset[str]] = frozenset({"cli_probe", "captured", "replay"})
TOKEN_STATUSES: Final[frozenset[str]] = frozenset({"AVAILABLE", "INSUFFICIENT"})
_LAYERS: Final[dict[str, str]] = {
    "L0": "L0",
    "L1": "L1",
    "L2": "L2",
    "project": "L0",
    "wave": "L1",
    "task": "L2",
}
_BASE_LEDGER_NAME = "harness.jsonl"
_SHA256 = set("0123456789abcdef")
_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "token-injection-measurement.yaml"


class TokenInjectionError(ValueError):
    """A token measurement or import artifact is malformed."""


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    try:
        schema = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return Draft202012Validator(schema)
    except (OSError, UnicodeError, yaml.YAMLError, TypeError) as exc:
        raise TokenInjectionError(f"cannot load token injection schema: {exc}") from exc


def _validate_schema(record: Mapping[str, Any]) -> None:
    errors = sorted(_schema_validator().iter_errors(record), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise TokenInjectionError(f"schema violation at {location}: {error.message}")


def _string(value: object, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TokenInjectionError(f"{field} must be a non-empty string")
    return value.strip()


def _status(value: object, field: str) -> str:
    if value not in TOKEN_STATUSES:
        raise TokenInjectionError(f"{field} must be AVAILABLE or INSUFFICIENT")
    return str(value)


def _non_negative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise TokenInjectionError(f"{field} must be a non-negative integer")
    return value


def _safe_sha(value: object, field: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256 for character in value)
    ):
        raise TokenInjectionError(f"{field} must be a lowercase SHA-256 value or null")
    return value


def _safe_repo_sha(value: object, field: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not 7 <= len(value) <= 64
        or any(character not in _SHA256 for character in value)
    ):
        raise TokenInjectionError(f"{field} must be a lowercase git SHA or null")
    return value


def _safe_relative(value: object, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TokenInjectionError(f"{field} must be a repository-relative path")
    path = Path(value)
    if path.is_absolute() or value.startswith("~") or ".." in path.parts:
        raise TokenInjectionError(f"{field} must be a repository-relative path")
    return path.as_posix()


def _timestamp(value: object, field: str = "ts") -> str:
    rendered = _string(value, field)
    assert rendered is not None
    try:
        datetime.fromisoformat(rendered.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TokenInjectionError(f"{field} must be an ISO-8601 timestamp") from exc
    return rendered


def _observation(value: object, field: str) -> tuple[int | None, str]:
    """Normalize a scalar or ``{tokens/status}`` component observation."""

    raw_value = value
    supplied_status: object | None = None
    if isinstance(value, Mapping):
        raw_value = value.get("tokens", value.get("value"))
        supplied_status = value.get("status")
        unknown = set(value) - {"tokens", "value", "status"}
        if unknown:
            raise TokenInjectionError(f"{field} has unsupported keys: {sorted(unknown)}")
    if raw_value is None:
        if supplied_status is not None and supplied_status != "INSUFFICIENT":
            raise TokenInjectionError(f"{field} null value requires INSUFFICIENT status")
        return None, "INSUFFICIENT"
    tokens = _non_negative_int(raw_value, f"{field}.tokens")
    if supplied_status is not None and supplied_status != "AVAILABLE":
        raise TokenInjectionError(f"{field} observed value requires AVAILABLE status")
    return tokens, "AVAILABLE"


def _uncertainty(value: object) -> dict[str, Any]:
    if value is None:
        return {
            "sample_count": None,
            "variance": None,
            "interval": None,
            "status": "INSUFFICIENT",
        }
    if not isinstance(value, Mapping):
        raise TokenInjectionError("uncertainty must be a mapping or null")
    sample_count = value.get("sample_count")
    if sample_count is not None:
        _non_negative_int(sample_count, "uncertainty.sample_count")
    variance = value.get("variance")
    if variance is not None and (
        isinstance(variance, bool)
        or not isinstance(variance, (int, float))
        or not math.isfinite(float(variance))
        or float(variance) < 0
    ):
        raise TokenInjectionError("uncertainty.variance must be a finite non-negative number")
    interval_value = value.get("interval")
    interval: dict[str, float] | None = None
    if interval_value is not None:
        if not isinstance(interval_value, Mapping) or set(interval_value) != {"low", "high"}:
            raise TokenInjectionError("uncertainty.interval must contain low and high")
        low, high = interval_value["low"], interval_value["high"]
        if any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            for item in (low, high)
        ) or float(low) > float(high):
            raise TokenInjectionError("uncertainty.interval must be finite with low <= high")
        interval = {"low": float(low), "high": float(high)}
    supplied_status = value.get("status")
    available = (
        (variance is not None or interval is not None)
        and sample_count is not None
        and sample_count > 0
    )
    expected_status = "AVAILABLE" if available else "INSUFFICIENT"
    if supplied_status is not None and supplied_status != expected_status:
        raise TokenInjectionError(
            "uncertainty.status does not match available variance/interval evidence"
        )
    return {
        "sample_count": sample_count,
        "variance": float(variance) if variance is not None else None,
        "interval": interval,
        "status": expected_status,
    }


def _component_value(source: Mapping[str, Any], component: str) -> object:
    direct = f"{component}_tokens"
    if direct in source:
        return source[direct]
    for container_name in ("observations", "token_observations", "token_measurements"):
        container = source.get(container_name)
        if isinstance(container, Mapping) and component in container:
            return container[component]
    return None


def _provenance(
    source: str,
    *,
    artifact_path: str | None,
    artifact_sha256: str,
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    kind = {
        "cli_probe": "cli-probe-artifact",
        "captured": "cursor-ide-captured",
        "replay": "fixture-replay",
    }[source]
    if value is not None:
        supplied_kind = value.get("kind")
        if supplied_kind is not None:
            kind = _string(supplied_kind, "provenance.kind") or kind
    return {
        "kind": kind,
        "artifact_path": artifact_path,
        "artifact_sha256": artifact_sha256,
    }


def _metadata_value(
    item: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
    field: str,
) -> object:
    if field in item:
        return item[field]
    if metadata is not None:
        return metadata.get(field)
    return None


def build_token_injection_measurement(
    item: Mapping[str, Any],
    *,
    source: str,
    artifact_sha256: str,
    artifact_path: str | None = None,
    host: str | None = None,
    channel: str | None = None,
    layer: str | None = None,
    profile: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build one strict, append-only token injection measurement event."""

    if not isinstance(item, Mapping):
        raise TokenInjectionError("measurement artifact entry must be a mapping")
    if source not in TOKEN_INJECTION_SOURCES:
        raise TokenInjectionError(f"source must be one of {sorted(TOKEN_INJECTION_SOURCES)}")
    artifact_digest = _safe_sha(artifact_sha256, "provenance.artifact_sha256")
    assert artifact_digest is not None
    resolved_metadata = metadata
    resolved_host = host or item.get("host") or item.get("provider")
    resolved_channel = channel or item.get("channel")
    resolved_layer = layer or item.get("layer")
    resolved_profile = profile or item.get("profile") or item.get("profile_name")
    resolved_channel = _string(resolved_channel, "channel")
    if resolved_host is None and resolved_channel is not None:
        from devolaflow.harness.cli_probe import PROBE_HOSTS

        resolved_host = PROBE_HOSTS.get(resolved_channel)
    resolved_host = _string(resolved_host, "host")
    resolved_layer = _string(resolved_layer, "layer")
    resolved_profile = _string(resolved_profile, "profile")
    assert resolved_host is not None
    assert resolved_channel is not None
    assert resolved_layer is not None
    assert resolved_profile is not None
    resolved_layer = _LAYERS.get(resolved_layer, "")
    if not resolved_layer:
        raise TokenInjectionError("layer must be L0, L1, L2, project, wave, or task")
    relative_artifact = _safe_relative(
        artifact_path,
        "provenance.artifact_path",
        nullable=True,
    )
    run_id = _metadata_value(item, resolved_metadata, "run_id")
    salt = _metadata_value(item, resolved_metadata, "salt")
    repo_ref = _metadata_value(item, resolved_metadata, "repo_ref")
    repo_sha = _metadata_value(item, resolved_metadata, "repo_sha")
    run_id = _string(run_id, "run_id", nullable=True)
    if salt is not None and (
        isinstance(salt, bool)
        or not isinstance(salt, (int, float, str))
        or not str(salt).strip()
        or (isinstance(salt, float) and not math.isfinite(salt))
    ):
        raise TokenInjectionError("salt must be a non-empty scalar or null")
    repo_ref = _string(repo_ref, "repo_ref", nullable=True)
    repo_sha = _safe_repo_sha(repo_sha, "repo_sha")
    observations: dict[str, tuple[int | None, str]] = {
        component: _observation(_component_value(item, component), f"{component}_tokens")
        for component in TOKEN_COMPONENTS
    }
    uncertainty = _uncertainty(item.get("uncertainty"))
    status = (
        "AVAILABLE"
        if (
            run_id is not None
            and salt is not None
            and repo_ref is not None
            and repo_sha is not None
            and uncertainty["status"] == "AVAILABLE"
            and all(
                observation_status == "AVAILABLE" for _, observation_status in observations.values()
            )
        )
        else "INSUFFICIENT"
    )
    item_metadata = item.get("metadata")
    metadata_timestamp = (
        item_metadata.get("generated_at") if isinstance(item_metadata, Mapping) else None
    )
    timestamp_value = _timestamp(
        timestamp
        or item.get("ts")
        or item.get("captured_at")
        or metadata_timestamp
        or datetime.now(UTC).isoformat()
    )
    identity = {
        "artifact_sha256": artifact_digest,
        "source": source,
        "host": resolved_host,
        "channel": resolved_channel,
        "layer": resolved_layer,
        "profile": resolved_profile,
        "run_id": run_id,
        "item_id": item.get("item_id"),
    }
    identity_json = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    event_id = f"{TOKEN_INJECTION_EVENT}:{hashlib.sha256(identity_json).hexdigest()}"
    record: dict[str, Any] = {
        "schema_version": TOKEN_INJECTION_SCHEMA_VERSION,
        "event": TOKEN_INJECTION_EVENT,
        "event_id": event_id,
        "ts": timestamp_value,
        "host": resolved_host,
        "channel": resolved_channel,
        "layer": resolved_layer,
        "profile": resolved_profile,
        "run_id": run_id,
        "run_id_status": "AVAILABLE" if run_id is not None else "INSUFFICIENT",
        "salt": salt,
        "salt_status": "AVAILABLE" if salt is not None else "INSUFFICIENT",
        "repo_ref": repo_ref,
        "repo_ref_status": "AVAILABLE" if repo_ref is not None else "INSUFFICIENT",
        "repo_sha": repo_sha,
        "repo_sha_status": "AVAILABLE" if repo_sha is not None else "INSUFFICIENT",
        "source": source,
        "provenance": _provenance(
            source,
            artifact_path=relative_artifact,
            artifact_sha256=artifact_digest,
            value=item.get("provenance") if isinstance(item.get("provenance"), Mapping) else None,
        ),
        "skill_tokens": observations["skill"][0],
        "skill_status": observations["skill"][1],
        "rule_tokens": observations["rule"][0],
        "rule_status": observations["rule"][1],
        "report_tokens": observations["report"][0],
        "report_status": observations["report"][1],
        "context_tokens": observations["context"][0],
        "context_status": observations["context"][1],
        "uncertainty": uncertainty,
        "status": status,
    }
    return validate_token_injection_measurement(record)


def validate_token_injection_measurement(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy a token injection event without fabricating facts."""

    fields = set(TOKEN_INJECTION_FIELDS)
    if not isinstance(record, Mapping):
        raise TokenInjectionError("token injection record must be a mapping")
    if set(record) != fields:
        missing = sorted(fields - set(record))
        extra = sorted(set(record) - fields)
        raise TokenInjectionError(
            f"token injection keys mismatch; missing={missing}, extra={extra}"
        )
    if record["schema_version"] != TOKEN_INJECTION_SCHEMA_VERSION:
        raise TokenInjectionError("token injection schema_version must equal 1")
    normalized = dict(record)
    _timestamp(record["ts"])
    for field in ("host", "channel", "profile", "event_id"):
        _string(record[field], field)
    layer = _string(record["layer"], "layer")
    if layer not in {"L0", "L1", "L2"}:
        raise TokenInjectionError("layer must be L0, L1, or L2")
    if record["source"] not in TOKEN_INJECTION_SOURCES:
        raise TokenInjectionError("source is unsupported")
    for field in ("run_id", "repo_ref"):
        _string(record[field], field, nullable=True)
    for value_field, status_field in (
        ("run_id", "run_id_status"),
        ("salt", "salt_status"),
        ("repo_ref", "repo_ref_status"),
        ("repo_sha", "repo_sha_status"),
    ):
        value = record[value_field]
        status = _status(record[status_field], status_field)
        if (value is None) != (status == "INSUFFICIENT"):
            raise TokenInjectionError(f"{value_field} and {status_field} disagree")
    if record["salt"] is not None and (
        isinstance(record["salt"], bool)
        or not isinstance(record["salt"], (int, float, str))
        or not str(record["salt"]).strip()
        or (isinstance(record["salt"], float) and not math.isfinite(record["salt"]))
    ):
        raise TokenInjectionError("salt must be a non-empty scalar or null")
    _safe_repo_sha(record["repo_sha"], "repo_sha")
    provenance = record["provenance"]
    if not isinstance(provenance, Mapping) or set(provenance) != {
        "kind",
        "artifact_path",
        "artifact_sha256",
    }:
        raise TokenInjectionError("provenance must contain kind, artifact_path, artifact_sha256")
    _string(provenance["kind"], "provenance.kind")
    _safe_relative(provenance["artifact_path"], "provenance.artifact_path", nullable=True)
    _safe_sha(provenance["artifact_sha256"], "provenance.artifact_sha256")
    for component in TOKEN_COMPONENTS:
        value = record[f"{component}_tokens"]
        status = _status(record[f"{component}_status"], f"{component}_status")
        if value is not None:
            _non_negative_int(value, f"{component}_tokens")
        if (value is None) != (status == "INSUFFICIENT"):
            raise TokenInjectionError(f"{component}_tokens and {component}_status disagree")
    normalized["uncertainty"] = _uncertainty(record["uncertainty"])
    _status(record["status"], "status")
    _validate_schema(normalized)
    return normalized


def _existing_event(ledger: Path, event_id: str) -> dict[str, Any] | None:
    if not ledger.exists():
        return None
    if ledger.is_file() and ledger.stat().st_size == 0:
        return None
    from devolaflow.harness.aggregator import load_ledger_records

    source = ledger.parent if ledger.name == _BASE_LEDGER_NAME else ledger
    if source.is_dir():
        base = source / _BASE_LEDGER_NAME
        if base.is_file() and base.stat().st_size == 0:
            return None
    for record in load_ledger_records(source):
        if record.get("event_id") == event_id:
            return record
    return None


def append_token_injection_measurement(
    ledger: str | Path,
    record: Mapping[str, Any],
) -> Path:
    """Append one event, idempotently accepting an identical prior event."""

    path = Path(ledger)
    normalized = validate_token_injection_measurement(record)
    existing = _existing_event(path, normalized["event_id"])
    if existing is not None:
        if existing != normalized:
            raise TokenInjectionError(
                f"event_id collision with different measurement: {normalized['event_id']}"
            )
        return path if path.name != _BASE_LEDGER_NAME else path
    if path.name == _BASE_LEDGER_NAME:
        path.parent.mkdir(parents=True, exist_ok=True)
        written = append_harness_record(path.parent, normalized)
        if written is None:
            raise TokenInjectionError(f"cannot append token injection measurement to {path}")
        return written
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("ab") as stream:
            stream.write(
                (json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            )
    except OSError as exc:
        raise TokenInjectionError(f"cannot append token injection measurement to {path}") from exc
    return path


def _read_artifact(path: Path) -> tuple[list[Mapping[str, Any]], bytes]:
    try:
        raw = path.read_bytes()
    except (OSError, UnicodeError) as exc:
        raise TokenInjectionError(f"cannot read artifact {path}: {exc}") from exc
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        entries: list[Mapping[str, Any]] = []
        for line_number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TokenInjectionError(
                    f"{path}:{line_number}: invalid JSONL: {exc.msg}"
                ) from exc
            if not isinstance(value, Mapping):
                raise TokenInjectionError(
                    f"{path}:{line_number}: entry must be a mapping"
                ) from None
            entries.append(value)
        if not entries:
            raise TokenInjectionError(f"{path}: artifact contains no JSON entries") from None
        return entries, raw
    if isinstance(decoded, Mapping):
        return [decoded], raw
    if isinstance(decoded, list) and all(isinstance(item, Mapping) for item in decoded):
        return decoded, raw
    raise TokenInjectionError(f"{path}: artifact must be a JSON object or JSONL mappings")


def ingest_measurement_artifact(
    artifact: str | Path,
    ledger: str | Path,
    *,
    source: str,
    repo_root: str | Path = ".",
    host: str | None = None,
    channel: str | None = None,
    layer: str | None = None,
    profile: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Read CLI/captured/replay JSON and append normalized events.

    The input is never rewritten.  Its repository-relative path and SHA-256
    are carried as provenance, making replay and captured evidence distinct.
    """

    path = Path(artifact)
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise TokenInjectionError(f"repo_root is not a directory: {repo_root}")
    try:
        relative = path.resolve().relative_to(root)
    except (OSError, ValueError) as exc:
        raise TokenInjectionError("artifact must be inside repo_root") from exc
    entries, raw = _read_artifact(path)
    digest = hashlib.sha256(raw).hexdigest()
    results: list[dict[str, Any]] = []
    for entry in entries:
        effective_metadata = metadata
        entry_metadata = entry.get("metadata")
        if effective_metadata is None and isinstance(entry_metadata, Mapping):
            effective_metadata = entry_metadata
        record = build_token_injection_measurement(
            entry,
            source=source,
            artifact_sha256=digest,
            artifact_path=relative.as_posix(),
            host=host,
            channel=channel,
            layer=layer,
            profile=profile,
            metadata=effective_metadata,
        )
        append_token_injection_measurement(ledger, record)
        results.append(record)
    return results


def ingest_cli_probe_artifact(
    artifact: str | Path,
    ledger: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Import exactly one existing ``cli_probe`` JSON artifact."""

    records = ingest_measurement_artifact(artifact, ledger, source="cli_probe", **kwargs)
    if len(records) != 1:
        raise TokenInjectionError("CLI probe artifact must contain exactly one JSON object")
    return records[0]


def ingest_captured_transcript(
    artifact: str | Path,
    ledger: str | Path,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Import a cursor-IDE captured JSON/JSONL transcript without execution."""

    return ingest_measurement_artifact(artifact, ledger, source="captured", **kwargs)


__all__ = [
    "TOKEN_COMPONENTS",
    "TOKEN_INJECTION_EVENT",
    "TOKEN_INJECTION_FIELDS",
    "TOKEN_INJECTION_SCHEMA_VERSION",
    "TOKEN_INJECTION_SOURCES",
    "TokenInjectionError",
    "append_token_injection_measurement",
    "build_token_injection_measurement",
    "ingest_captured_transcript",
    "ingest_cli_probe_artifact",
    "ingest_measurement_artifact",
    "validate_token_injection_measurement",
]
