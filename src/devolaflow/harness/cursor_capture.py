"""Offline Cursor IDE transcript parsing and capture procedure.

Cursor IDE has no stable runtime probe channel in the HSC.  Operators may
therefore capture a JSON object or JSONL session transcript after a manual or
semi-automated run, recording explicit component counters when the UI exposes
them.  The parser accepts only those explicit counters; message text,
character counts, and the ``skill-on`` arm are never converted into tokens.

Capture procedure
-----------------
1. Run the bounded task in Cursor IDE and export the transcript or copy the
   session evidence to a repository-relative JSON/JSONL file.
2. Add ``layer`` and ``profile`` plus reproducibility metadata
   (``run_id``, ``salt``, ``repo_ref``, and ``repo_sha``) when available.
3. Record explicit ``skill_tokens``, ``rule_tokens``, ``report_tokens``, and
   ``context_tokens`` values, or leave the values absent when Cursor does not
   expose them.  Missing values remain ``null``/``INSUFFICIENT``.
4. Ingest with :func:`ingest_cursor_ide_capture`; the source is ``captured``
   and the artifact digest/path are retained.  This is evidence collection,
   not an automatic Cursor runtime probe.

The accepted input can be one measurement object, a JSON array, a JSON object
with an ``events`` array, or JSONL.  A JSONL session may contain metadata-only
lines followed by measurement lines; the latest metadata is inherited by the
measurement.  The output is suitable for the existing token-injection
measurement ingest and does not change its ledger schema.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devolaflow.harness.token_injection import (
    TokenInjectionError,
    append_token_injection_measurement,
    build_token_injection_measurement,
)

CAPTURED_HOST = "cursor"
CAPTURED_CHANNEL = "cursor-ide"
CAPTURED_LAYER = "L1"
CAPTURED_PROFILE = "captured"
_COMPONENT_KEYS = frozenset(
    {
        "skill_tokens",
        "rule_tokens",
        "report_tokens",
        "context_tokens",
        "observations",
        "token_observations",
        "token_measurements",
        "token_injection",
    }
)
_METADATA_KEYS = frozenset(
    {
        "host",
        "channel",
        "layer",
        "profile",
        "profile_name",
        "run_id",
        "salt",
        "repo_ref",
        "repo_sha",
        "captured_at",
        "ts",
        "uncertainty",
    }
)


def _read_entries(path: Path) -> list[Mapping[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TokenInjectionError(f"cannot read Cursor IDE capture {path}: {exc}") from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        entries: list[Mapping[str, Any]] = []
        for line_number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TokenInjectionError(
                    f"{path}:{line_number}: invalid Cursor capture JSONL: {exc.msg}"
                ) from exc
            if not isinstance(value, Mapping):
                raise TokenInjectionError(
                    f"{path}:{line_number}: capture entry must be a mapping"
                ) from None
            entries.append(value)
        if not entries:
            raise TokenInjectionError(f"{path}: Cursor capture contains no JSON entries") from None
        return entries
    if isinstance(document, Mapping):
        events = document.get("events")
        if isinstance(events, list):
            if not all(isinstance(event, Mapping) for event in events):
                raise TokenInjectionError(f"{path}: Cursor capture events must be mappings")
            inherited = {key: value for key, value in document.items() if key != "events"}
            return [{**inherited, **event} for event in events]
        return [document]
    if isinstance(document, list) and all(isinstance(item, Mapping) for item in document):
        return document
    raise TokenInjectionError(f"{path}: Cursor capture must be an object, array, or JSONL")


def _has_measurement(entry: Mapping[str, Any]) -> bool:
    return bool(_COMPONENT_KEYS.intersection(entry)) or isinstance(
        entry.get("measurement"), Mapping
    )


def _merge_nested_measurement(entry: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    nested = normalized.pop("measurement", None)
    if isinstance(nested, Mapping):
        normalized.update(nested)
    token_container = normalized.get("token_injection")
    if isinstance(token_container, Mapping):
        normalized.update(token_container)
    normalized.pop("token_injection", None)
    normalized["host"] = normalized.get("host") or CAPTURED_HOST
    if normalized["host"] == "cursor-ide":
        normalized["host"] = CAPTURED_HOST
    normalized["channel"] = normalized.get("channel") or CAPTURED_CHANNEL
    normalized["layer"] = normalized.get("layer") or CAPTURED_LAYER
    normalized["profile"] = (
        normalized.get("profile") or normalized.get("profile_name") or CAPTURED_PROFILE
    )
    normalized["provenance"] = {"kind": "captured"}
    return normalized


def parse_cursor_ide_transcript(artifact: str | Path) -> list[dict[str, Any]]:
    """Parse a Cursor capture into explicit token-observation input records.

    Transcript metadata lines are inherited by later measurement lines.  When
    a capture contains no explicit component observation, one record is still
    returned so ingest can preserve the resulting ``INSUFFICIENT`` evidence.
    """

    path = Path(artifact)
    entries = _read_entries(path)
    inherited: dict[str, Any] = {}
    measurements: list[dict[str, Any]] = []
    for entry in entries:
        if _has_measurement(entry):
            merged = {**inherited, **entry}
            measurements.append(_merge_nested_measurement(merged))
        elif any(key in entry for key in _METADATA_KEYS):
            inherited.update(entry)
    if not measurements:
        measurements.append(_merge_nested_measurement(inherited))
    return measurements


def ingest_cursor_ide_capture(
    artifact: str | Path,
    ledger: str | Path,
    *,
    repo_root: str | Path = ".",
    metadata: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Append a parsed Cursor IDE capture as ``source=captured`` evidence."""

    path = Path(artifact)
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise TokenInjectionError(f"repo_root is not a directory: {repo_root}")
    try:
        relative = path.resolve().relative_to(root)
        raw = path.read_bytes()
    except (OSError, ValueError) as exc:
        raise TokenInjectionError("Cursor capture must be inside repo_root") from exc
    digest = hashlib.sha256(raw).hexdigest()
    results: list[dict[str, Any]] = []
    for item in parse_cursor_ide_transcript(path):
        effective_metadata = metadata
        item_metadata = item.get("metadata")
        if effective_metadata is None and isinstance(item_metadata, Mapping):
            effective_metadata = item_metadata
        record = build_token_injection_measurement(
            item,
            source="captured",
            artifact_sha256=digest,
            artifact_path=relative.as_posix(),
            metadata=effective_metadata,
            timestamp=(item.get("captured_at") or item.get("ts") or datetime.now(UTC).isoformat()),
        )
        append_token_injection_measurement(ledger, record)
        results.append(record)
    return results


parse_cursor_ide_capture = parse_cursor_ide_transcript
ingest_cursor_ide_transcript = ingest_cursor_ide_capture

__all__ = [
    "CAPTURED_CHANNEL",
    "CAPTURED_HOST",
    "CAPTURED_LAYER",
    "CAPTURED_PROFILE",
    "ingest_cursor_ide_capture",
    "ingest_cursor_ide_transcript",
    "parse_cursor_ide_capture",
    "parse_cursor_ide_transcript",
]
