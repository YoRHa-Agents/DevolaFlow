"""Reproducible metadata for harness runs and telemetry records."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Final

RunMetadata = dict[str, Any]
MetadataRunner = Any

METADATA_FIELDS: Final[tuple[str, ...]] = (
    "run_id",
    "sampled_at",
    "generated_at",
    "salt",
    "salt_status",
    "ledger_path",
    "ledger_status",
    "repo_ref",
    "repo_sha",
    "base_ref",
    "base_ref_status",
    "repo_status",
    "status",
)
_STATUSES: Final[frozenset[str]] = frozenset({"AVAILABLE", "INSUFFICIENT"})
_SHA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{7,64}$")


class MetadataError(ValueError):
    """Run metadata is malformed or cannot be rendered safely."""


def _timestamp(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MetadataError(f"{field} must be a non-empty string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MetadataError(f"{field} must be an ISO-8601 timestamp") from exc
    return value


def _relative_path(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or Path(value).is_absolute()
        or value.startswith("~")
        or ".." in Path(value).parts
    ):
        raise MetadataError(f"{field} must be a repository-relative path or null")
    return value


def _status(value: object, *, field: str) -> str:
    if not isinstance(value, str) or value not in _STATUSES:
        raise MetadataError(f"{field} must be AVAILABLE or INSUFFICIENT")
    return value


def validate_run_metadata(metadata: Mapping[str, Any]) -> RunMetadata:
    """Validate and copy the stable metadata envelope.

    Missing evidence is represented by ``null`` plus an ``INSUFFICIENT``
    status.  Validation never fills in a missing salt or repository fact.
    """

    if not isinstance(metadata, Mapping):
        raise MetadataError("metadata must be a mapping")
    if set(metadata) != set(METADATA_FIELDS):
        missing = sorted(set(METADATA_FIELDS) - set(metadata))
        extra = sorted(set(metadata) - set(METADATA_FIELDS))
        raise MetadataError(f"metadata keys mismatch; missing={missing}, extra={extra}")
    run_id = metadata["run_id"]
    if not isinstance(run_id, str) or not run_id.strip():
        raise MetadataError("metadata.run_id must be a non-empty string")
    sampled_at = _timestamp(metadata["sampled_at"], field="metadata.sampled_at")
    generated_at = _timestamp(metadata["generated_at"], field="metadata.generated_at")
    salt = metadata["salt"]
    if salt is not None and (
        isinstance(salt, bool)
        or not isinstance(salt, (int, float, str))
        or not str(salt).strip()
        or (isinstance(salt, float) and not math.isfinite(salt))
    ):
        raise MetadataError("metadata.salt must be a non-empty scalar or null")
    salt_status = _status(metadata["salt_status"], field="metadata.salt_status")
    if (salt is None) != (salt_status == "INSUFFICIENT"):
        raise MetadataError("metadata.salt and metadata.salt_status disagree")
    ledger_path = _relative_path(metadata["ledger_path"], field="metadata.ledger_path")
    ledger_status = _status(metadata["ledger_status"], field="metadata.ledger_status")
    if (ledger_path is None) != (ledger_status == "INSUFFICIENT"):
        raise MetadataError("metadata.ledger_path and metadata.ledger_status disagree")
    repo_ref = metadata["repo_ref"]
    if repo_ref is not None and (not isinstance(repo_ref, str) or not repo_ref.strip()):
        raise MetadataError("metadata.repo_ref must be a non-empty string or null")
    repo_sha = metadata["repo_sha"]
    if repo_sha is not None and (
        not isinstance(repo_sha, str) or _SHA_RE.fullmatch(repo_sha) is None
    ):
        raise MetadataError("metadata.repo_sha must be a git SHA or null")
    base_ref = metadata["base_ref"]
    if base_ref is not None and (not isinstance(base_ref, str) or not base_ref.strip()):
        raise MetadataError("metadata.base_ref must be a non-empty string or null")
    base_ref_status = _status(metadata["base_ref_status"], field="metadata.base_ref_status")
    if (base_ref is None) != (base_ref_status == "INSUFFICIENT"):
        raise MetadataError("metadata.base_ref and metadata.base_ref_status disagree")
    repo_status = _status(metadata["repo_status"], field="metadata.repo_status")
    status = _status(metadata["status"], field="metadata.status")
    if repo_status == "AVAILABLE" and (
        repo_ref is None or repo_sha is None or base_ref_status != "AVAILABLE"
    ):
        raise MetadataError(
            "metadata.repo_status cannot be AVAILABLE with missing repository facts"
        )
    if status == "AVAILABLE" and (
        salt_status != "AVAILABLE" or ledger_status != "AVAILABLE" or repo_status != "AVAILABLE"
    ):
        raise MetadataError("metadata.status cannot be AVAILABLE with insufficient evidence")
    return {
        "run_id": run_id,
        "sampled_at": sampled_at,
        "generated_at": generated_at,
        "salt": salt,
        "salt_status": salt_status,
        "ledger_path": ledger_path,
        "ledger_status": ledger_status,
        "repo_ref": repo_ref,
        "repo_sha": repo_sha,
        "base_ref": base_ref,
        "base_ref_status": base_ref_status,
        "repo_status": repo_status,
        "status": status,
    }


def _git_value(
    repo_root: Path,
    args: list[str],
    *,
    runner: MetadataRunner,
) -> str | None:
    try:
        completed = runner(
            ["git", *args],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    value = (completed.stdout or "").strip()
    return value or None


def _ledger_relative_path(ledger: str | Path, repo_root: Path) -> str | None:
    raw = Path(ledger)
    if not raw.is_absolute():
        if raw == Path(".") or ".." in raw.parts:
            return None
        return raw.as_posix()
    try:
        resolved = raw.resolve()
        relative = resolved.relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return None
    return relative.as_posix()


def _ledger_digest(ledger: str | Path) -> str | None:
    try:
        path = Path(ledger)
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, UnicodeError):
        return None


def build_run_metadata(
    ledger: str | Path,
    *,
    repo_root: str | Path = ".",
    sampled_at: str,
    base_ref: str | None = "HEAD~1",
    salt: int | float | str | None = None,
    run_id: str | None = None,
    generated_at: str | None = None,
    runner: MetadataRunner | None = None,
) -> RunMetadata:
    """Build a serializable, repository-relative metadata envelope.

    The default run ID is a content-derived identifier, so repeated rendering
    of the same ledger and inputs is byte-stable while distinct inputs receive
    distinct IDs.  No salt is inferred: omitted salt is explicit insufficient
    evidence.
    """

    sampled = _timestamp(sampled_at, field="sampled_at")
    generated = _timestamp(generated_at or sampled, field="generated_at")
    if salt is not None and (
        isinstance(salt, bool)
        or not isinstance(salt, (int, float, str))
        or not str(salt).strip()
        or (isinstance(salt, float) and not math.isfinite(salt))
    ):
        raise MetadataError("salt must be a non-empty scalar or null")
    root = Path(repo_root)
    ledger_path = _ledger_relative_path(ledger, root)
    ledger_status = "AVAILABLE" if ledger_path is not None else "INSUFFICIENT"
    resolved_runner = runner or subprocess.run
    repo_ref = _git_value(root, ["rev-parse", "--abbrev-ref", "HEAD"], runner=resolved_runner)
    repo_sha = _git_value(root, ["rev-parse", "HEAD"], runner=resolved_runner)
    if repo_sha is not None and _SHA_RE.fullmatch(repo_sha) is None:
        repo_sha = None
    resolved_base_ref = base_ref.strip() if isinstance(base_ref, str) and base_ref.strip() else None
    base_ref_available = (
        resolved_base_ref is not None
        and _git_value(
            root,
            ["rev-parse", "--verify", f"{resolved_base_ref}^{{commit}}"],
            runner=resolved_runner,
        )
        is not None
    )
    base_ref_status = "AVAILABLE" if base_ref_available else "INSUFFICIENT"
    base_ref_value = resolved_base_ref if base_ref_available else None
    repo_status = (
        "AVAILABLE"
        if repo_ref is not None and repo_sha is not None and base_ref_available
        else "INSUFFICIENT"
    )
    salt_status = "AVAILABLE" if salt is not None else "INSUFFICIENT"
    identity = {
        "sampled_at": sampled,
        "generated_at": generated,
        "salt": salt,
        "ledger_path": ledger_path,
        "ledger_sha256": _ledger_digest(ledger),
        "repo_ref": repo_ref,
        "repo_sha": repo_sha,
        "base_ref": base_ref_value,
        "base_ref_requested": resolved_base_ref,
    }
    if run_id is None:
        encoded = json.dumps(
            identity,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        resolved_run_id = f"run-{hashlib.sha256(encoded).hexdigest()}"
    elif isinstance(run_id, str) and run_id.strip():
        resolved_run_id = run_id
    else:
        raise MetadataError("run_id must be a non-empty string or null")
    metadata_status = (
        "AVAILABLE"
        if (
            salt_status == "AVAILABLE"
            and ledger_status == "AVAILABLE"
            and repo_status == "AVAILABLE"
        )
        else "INSUFFICIENT"
    )
    return validate_run_metadata(
        {
            "run_id": resolved_run_id,
            "sampled_at": sampled,
            "generated_at": generated,
            "salt": salt,
            "salt_status": salt_status,
            "ledger_path": ledger_path,
            "ledger_status": ledger_status,
            "repo_ref": repo_ref,
            "repo_sha": repo_sha,
            "base_ref": base_ref_value,
            "base_ref_status": base_ref_status,
            "repo_status": repo_status,
            "status": metadata_status,
        }
    )


def attach_run_metadata(
    record: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a copy with optional validated metadata appended at the end."""

    rendered = dict(record)
    if metadata is not None:
        rendered["metadata"] = validate_run_metadata(metadata)
    return rendered


__all__ = [
    "METADATA_FIELDS",
    "MetadataError",
    "RunMetadata",
    "attach_run_metadata",
    "build_run_metadata",
    "validate_run_metadata",
]
