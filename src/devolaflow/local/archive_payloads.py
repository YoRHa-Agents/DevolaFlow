"""JSON/YAML payload codec for the explicit local-task archive CLI.

Split out of `devolaflow.cli` at v20.0.0 to honour the W-9 module-size
ratchet. `devolaflow.cli` imports every name back into its own namespace, so
`devolaflow.cli._local_archive_load_plan` and friends remain patchable and
the CLI surface is unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

_LOCAL_ARCHIVE_SCHEMA_VERSION = 1
_LOCAL_ARCHIVE_ACTIONS = {"move", "retain", "review", "refuse"}
_LOCAL_ARCHIVE_LIFECYCLES = {"active", "done", "stale", "unknown"}
_LOCAL_ARCHIVE_PROTECTIONS = {"allowed", "protected", "unsafe", "ambiguous"}
_LOCAL_ARCHIVE_INDEX_LINE = re.compile(r"- `([^`]+)` ← `([^`]+)`")


class _LocalArchiveInputError(ValueError):
    """Raised when a plan file is not a valid local-archive artifact."""


def _local_archive_finding(finding: object) -> dict[str, str]:
    return {"code": finding.code, "message": finding.message}


def _local_archive_entry_payload(entry: object) -> dict[str, object]:
    return {
        "source": entry.source,
        "destination": entry.destination,
        "cluster_key": entry.cluster_key,
        "classification": entry.classification,
        "action": entry.action,
        "protection": entry.protection.value,
        "protection_reason": entry.protection_reason,
        "findings": [_local_archive_finding(finding) for finding in entry.findings],
    }


def _local_archive_plan_payload(plan: object) -> dict[str, object]:
    return {
        "artifact_type": "task-archive-plan",
        "schema_version": _LOCAL_ARCHIVE_SCHEMA_VERSION,
        "source_boundary": plan.source_boundary,
        "fingerprint": plan.fingerprint,
        "entries": [_local_archive_entry_payload(entry) for entry in plan.entries],
        "findings": [_local_archive_finding(finding) for finding in plan.findings],
    }


def _local_archive_result_payload(result: object) -> dict[str, object]:
    return {
        "artifact_type": "task-archive-result",
        "schema_version": _LOCAL_ARCHIVE_SCHEMA_VERSION,
        "applied": [_local_archive_entry_payload(entry) for entry in result.applied],
        "mappings": [
            {
                "sequence": mapping.sequence,
                "source": mapping.source,
                "destination": mapping.destination,
                "reason": mapping.reason,
                "timestamp": mapping.timestamp,
            }
            for mapping in result.mappings
        ],
        "findings": [_local_archive_finding(finding) for finding in result.findings],
        "refused": result.refused,
        "success": result.success,
        "index_path": result.index_path,
        "recovery_required": result.recovery_required,
        "recovery_hint": result.recovery_hint,
    }


def _local_archive_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _local_archive_require_text(
    value: object, *, field: str, entry_number: int | None = None
) -> str:
    if not isinstance(value, str) or not value:
        prefix = f"entry {entry_number}: " if entry_number is not None else ""
        raise _LocalArchiveInputError(f"{prefix}{field} must be a non-empty string")
    return value


def _local_archive_validate_path(value: str, *, field: str, entry_number: int) -> None:
    path = PurePosixPath(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts:
        raise _LocalArchiveInputError(
            f"entry {entry_number}: {field} must be repository-relative POSIX"
        )
    if not value.startswith(".local/tasks/"):
        raise _LocalArchiveInputError(f"entry {entry_number}: {field} is outside .local/tasks")


def _local_archive_findings(
    payload: object, *, entry_number: int | None = None
) -> tuple[object, ...]:
    from devolaflow.local.archive import Finding

    if payload is None:
        return ()
    if not isinstance(payload, list):
        prefix = f"entry {entry_number}: " if entry_number is not None else ""
        raise _LocalArchiveInputError(f"{prefix}findings must be a list")
    findings: list[Finding] = []
    for finding_number, item in enumerate(payload):
        if not isinstance(item, dict):
            raise _LocalArchiveInputError(
                f"finding {finding_number} in entry {entry_number} must be a mapping"
            )
        code = _local_archive_require_text(item.get("code"), field="finding code")
        message = _local_archive_require_text(item.get("message"), field="finding message")
        findings.append(Finding(code=code, message=message))
    return tuple(findings)


def _local_archive_plan_from_payload(payload: object) -> object:
    from devolaflow.local.archive import (
        ArchivePlan,
        PlanEntry,
        ProtectionVerdict,
    )

    if not isinstance(payload, dict):
        raise _LocalArchiveInputError("plan must be a mapping")
    if payload.get("artifact_type") != "task-archive-plan":
        raise _LocalArchiveInputError("artifact_type must be task-archive-plan")
    if payload.get("schema_version") != _LOCAL_ARCHIVE_SCHEMA_VERSION:
        raise _LocalArchiveInputError("schema_version must be 1")
    if payload.get("source_boundary") != ".local/tasks":
        raise _LocalArchiveInputError("source_boundary must be .local/tasks")
    entries_payload = payload.get("entries")
    if not isinstance(entries_payload, list):
        raise _LocalArchiveInputError("entries must be a list")

    entries: list[PlanEntry] = []
    for entry_number, item in enumerate(entries_payload):
        if not isinstance(item, dict):
            raise _LocalArchiveInputError(f"entry {entry_number} must be a mapping")
        source = _local_archive_require_text(
            item.get("source"), field="source", entry_number=entry_number
        )
        destination = _local_archive_require_text(
            item.get("destination"), field="destination", entry_number=entry_number
        )
        _local_archive_validate_path(source, field="source", entry_number=entry_number)
        _local_archive_validate_path(destination, field="destination", entry_number=entry_number)
        cluster_key = _local_archive_require_text(
            item.get("cluster_key"), field="cluster_key", entry_number=entry_number
        )
        classification = _local_archive_require_text(
            item.get("classification"), field="classification", entry_number=entry_number
        )
        action = _local_archive_require_text(
            item.get("action"), field="action", entry_number=entry_number
        )
        protection = _local_archive_require_text(
            item.get("protection"), field="protection", entry_number=entry_number
        )
        protection_reason = item.get("protection_reason")
        if not isinstance(protection_reason, str):
            raise _LocalArchiveInputError(
                f"entry {entry_number}: protection_reason must be a string"
            )
        if classification not in _LOCAL_ARCHIVE_LIFECYCLES:
            raise _LocalArchiveInputError(f"entry {entry_number}: invalid classification")
        if action not in _LOCAL_ARCHIVE_ACTIONS:
            raise _LocalArchiveInputError(f"entry {entry_number}: invalid action")
        if protection not in _LOCAL_ARCHIVE_PROTECTIONS:
            raise _LocalArchiveInputError(f"entry {entry_number}: invalid protection")
        entries.append(
            PlanEntry(
                source=source,
                destination=destination,
                cluster_key=cluster_key,
                classification=classification,
                action=action,
                protection=ProtectionVerdict(protection),
                protection_reason=protection_reason,
                findings=_local_archive_findings(item.get("findings"), entry_number=entry_number),
            )
        )

    findings = _local_archive_findings(payload.get("findings"))
    plan = ArchivePlan(
        entries=tuple(entries),
        findings=findings,
        source_boundary=".local/tasks",
    )
    fingerprint = payload.get("fingerprint")
    if fingerprint is not None and (
        not isinstance(fingerprint, str) or fingerprint != plan.fingerprint
    ):
        raise _LocalArchiveInputError("fingerprint does not match plan contents")
    return plan


def _local_archive_approval_from_payload(payload: object) -> object:
    from devolaflow.local.archive import ArchiveApproval

    if not isinstance(payload, dict):
        raise _LocalArchiveInputError("approval must be a mapping")
    if payload.get("artifact_type") != "task-archive-approval":
        raise _LocalArchiveInputError("artifact_type must be task-archive-approval")
    if payload.get("schema_version") != _LOCAL_ARCHIVE_SCHEMA_VERSION:
        raise _LocalArchiveInputError("schema_version must be 1")
    fingerprint = _local_archive_require_text(
        payload.get("plan_fingerprint"), field="plan_fingerprint"
    )
    entries_payload = payload.get("entries")
    if not isinstance(entries_payload, list) or not entries_payload:
        raise _LocalArchiveInputError("approved entries must be a non-empty list")
    entries: list[tuple[str, str]] = []
    for entry_number, item in enumerate(entries_payload):
        if not isinstance(item, dict):
            raise _LocalArchiveInputError(f"approved entry {entry_number} must be a mapping")
        source = _local_archive_require_text(
            item.get("source"), field="source", entry_number=entry_number
        )
        destination = _local_archive_require_text(
            item.get("destination"), field="destination", entry_number=entry_number
        )
        _local_archive_validate_path(source, field="source", entry_number=entry_number)
        _local_archive_validate_path(destination, field="destination", entry_number=entry_number)
        key = (source, destination)
        if key in entries:
            raise _LocalArchiveInputError(f"approved entry {entry_number} is duplicated")
        entries.append(key)
    return ArchiveApproval(plan_fingerprint=fingerprint, entries=tuple(entries))


def _local_archive_load_plan(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _LocalArchiveInputError(f"cannot read plan: {path}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise _LocalArchiveInputError(f"cannot parse plan: {path}: {exc}") from exc
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise _LocalArchiveInputError(f"cannot parse plan: {path}: {exc}") from exc
    if isinstance(payload, dict) and payload.get("artifact_type") == "task-archive-approval":
        return _local_archive_approval_from_payload(payload)
    return _local_archive_plan_from_payload(payload)
