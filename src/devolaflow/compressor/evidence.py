"""StatusReport evidence transport with bounded inline payloads.

Evidence is normally kept inline because that is the smallest and most
backward-compatible representation.  Once a block exceeds the byte budget it
is written to a deterministic file in the active change's ``evidence/``
directory and the report carries only an ``evidence_ref`` descriptor.

The helper is deliberately report-specific rather than a generic file loader:
it prevents a report from referring to arbitrary repository files and never
hydrates referenced evidence back into the report.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

DEFAULT_EVIDENCE_INLINE_MAX_BYTES = 1024
EVIDENCE_TYPE = "status-report-evidence"
EVIDENCE_BLOCKS = ("self_check", "ac_results", "diff_stats")

_CHANGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_EVIDENCE_ROOT_PARTS = (".local", ".agent", "active")

__all__ = [
    "DEFAULT_EVIDENCE_INLINE_MAX_BYTES",
    "EVIDENCE_BLOCKS",
    "EVIDENCE_TYPE",
    "EvidenceReferenceError",
    "EvidenceReferenceRequired",
    "EvidenceReferenceRequiredError",
    "prepare_status_report_evidence",
    "serialize_status_report_evidence",
    "validate_evidence_ref",
    "validate_status_report_evidence",
]


class EvidenceReferenceError(ValueError):
    """Raised when a report evidence reference is malformed or unsafe."""


class EvidenceReferenceRequiredError(EvidenceReferenceError):
    """Raised when oversized evidence cannot be represented inline."""


EvidenceReferenceRequired = EvidenceReferenceRequiredError


def _canonical_bytes(value: Any) -> bytes:
    """Render evidence deterministically for sizing, hashing, and storage."""

    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceReferenceError(
            f"evidence must be JSON-serializable; got {type(value).__name__}"
        ) from exc
    return rendered.encode("utf-8")


def _validate_change_id(change_id: str) -> None:
    if not isinstance(change_id, str) or not _CHANGE_ID_RE.fullmatch(change_id):
        raise EvidenceReferenceError("change_id must match ^[a-z0-9][a-z0-9.-]*[a-z0-9]$")


def _repo_root(repo_root: str | Path) -> Path:
    root = Path(repo_root)
    if not root.is_dir():
        raise EvidenceReferenceError(f"repo_root is not an existing directory: {root}")
    return root.resolve()


def _evidence_root(repo_root: str | Path, change_id: str) -> Path:
    _validate_change_id(change_id)
    root = _repo_root(repo_root)
    relative_parts = (*_EVIDENCE_ROOT_PARTS, change_id, "evidence")
    current = root
    for part in relative_parts:
        current /= part
        if current.is_symlink():
            raise EvidenceReferenceError(
                f"evidence directory component must not be a symlink: {current}"
            )
    return current


def _path_from_reference(path: Any) -> PurePosixPath:
    if not isinstance(path, str) or not path:
        raise EvidenceReferenceError("evidence_ref.path must be a non-empty string")
    if path.startswith("~") or "\\" in path:
        raise EvidenceReferenceError("evidence_ref.path must be a repository-relative POSIX path")
    if Path(path).is_absolute() or PureWindowsPath(path).is_absolute():
        raise EvidenceReferenceError("evidence_ref.path must not be absolute")
    parsed = PurePosixPath(path)
    if any(part in {"", ".", ".."} for part in parsed.parts):
        raise EvidenceReferenceError("evidence_ref.path contains unsafe path components")
    return parsed


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _reference_target(
    reference: Mapping[str, Any],
    *,
    repo_root: str | Path,
    change_id: str,
) -> tuple[Path, bytes]:
    path = _path_from_reference(reference.get("path"))
    expected_prefix = PurePosixPath(*_EVIDENCE_ROOT_PARTS, change_id, "evidence")
    if path.parts[: len(expected_prefix.parts)] != expected_prefix.parts:
        raise EvidenceReferenceError(
            f"evidence_ref.path must point under {expected_prefix.as_posix()}/"
        )
    root = _evidence_root(repo_root, change_id)
    lexical_target = _repo_root(repo_root) / Path(*path.parts)
    if lexical_target.is_symlink():
        raise EvidenceReferenceError("evidence_ref.path must not reference a symlink")
    target = lexical_target.resolve(strict=False)
    if not _is_relative_to(target, root.resolve(strict=False)):
        raise EvidenceReferenceError("evidence_ref.path escapes the evidence directory")
    if not target.is_file():
        raise EvidenceReferenceError(f"evidence artifact does not exist: {path.as_posix()}")
    resolved = target.resolve(strict=True)
    if not _is_relative_to(resolved, root.resolve(strict=True)):
        raise EvidenceReferenceError("evidence artifact resolves outside the evidence directory")
    return resolved, resolved.read_bytes()


def validate_evidence_ref(
    reference: Mapping[str, Any],
    *,
    repo_root: str | Path,
    change_id: str,
) -> dict[str, Any]:
    """Validate and return a copy of one safe, content-addressed reference.

    The descriptor is metadata only.  This function validates the referenced
    file and digest but intentionally does not return its contents.
    """

    if not isinstance(reference, Mapping):
        raise EvidenceReferenceError("evidence_ref must be a mapping")
    required = ("path", "artifact_id", "type", "digest", "size_bytes")
    missing = [key for key in required if key not in reference]
    if missing:
        raise EvidenceReferenceError(f"evidence_ref missing required field(s): {missing}")
    artifact_id = reference["artifact_id"]
    if not isinstance(artifact_id, str) or not _ARTIFACT_ID_RE.fullmatch(artifact_id):
        raise EvidenceReferenceError("evidence_ref.artifact_id must be a stable identifier")
    if reference["type"] != EVIDENCE_TYPE:
        raise EvidenceReferenceError(f"evidence_ref.type must be {EVIDENCE_TYPE!r}")
    digest = reference["digest"]
    if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
        raise EvidenceReferenceError("evidence_ref.digest must be sha256:<64 hex chars>")
    size_bytes = reference["size_bytes"]
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise EvidenceReferenceError("evidence_ref.size_bytes must be a non-negative int")

    target, content = _reference_target(reference, repo_root=repo_root, change_id=change_id)
    actual_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
    if actual_digest != digest:
        raise EvidenceReferenceError(
            f"evidence_ref.digest does not match {target.name}: "
            f"expected {actual_digest}, got {digest}"
        )
    if len(content) != size_bytes:
        raise EvidenceReferenceError(
            f"evidence_ref.size_bytes does not match {target.name}: "
            f"expected {len(content)}, got {size_bytes}"
        )
    return dict(reference)


def _build_reference(
    block_name: str,
    value: Any,
    *,
    repo_root: str | Path,
    change_id: str,
) -> dict[str, Any]:
    content = _canonical_bytes(value)
    digest_hex = hashlib.sha256(content).hexdigest()
    artifact_id = f"sr-{block_name}-{digest_hex[:16]}"
    relative_path = (
        PurePosixPath(*_EVIDENCE_ROOT_PARTS, change_id, "evidence") / f"{artifact_id}.json"
    )
    root = _evidence_root(repo_root, change_id)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{artifact_id}.json"
    if target.exists():
        if target.is_symlink() or not target.is_file() or target.read_bytes() != content:
            raise EvidenceReferenceError(
                f"stable evidence artifact collision at {relative_path.as_posix()}"
            )
    else:
        try:
            with target.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            if target.is_symlink() or target.read_bytes() != content:
                raise EvidenceReferenceError(
                    f"stable evidence artifact collision at {relative_path.as_posix()}"
                ) from None
    reference = {
        "path": relative_path.as_posix(),
        "artifact_id": artifact_id,
        "type": EVIDENCE_TYPE,
        "digest": f"sha256:{digest_hex}",
        "size_bytes": len(content),
    }
    return validate_evidence_ref(reference, repo_root=repo_root, change_id=change_id)


def _prepare_block(
    block_name: str,
    value: Any,
    *,
    repo_root: str | Path,
    change_id: str,
    inline_max_bytes: int,
) -> Any:
    if isinstance(value, Mapping) and "evidence_ref" in value:
        if set(value) != {"evidence_ref"}:
            raise EvidenceReferenceError(
                f"{block_name} evidence_ref is mutually exclusive with inline fields"
            )
        return {
            "evidence_ref": validate_evidence_ref(
                value["evidence_ref"], repo_root=repo_root, change_id=change_id
            )
        }
    content = _canonical_bytes(value)
    if len(content) <= inline_max_bytes:
        return deepcopy(value)
    reference = _build_reference(
        block_name,
        value,
        repo_root=repo_root,
        change_id=change_id,
    )
    return {"evidence_ref": reference}


def validate_status_report_evidence(
    report: Mapping[str, Any],
    *,
    repo_root: str | Path,
    change_id: str,
    inline_max_bytes: int = DEFAULT_EVIDENCE_INLINE_MAX_BYTES,
) -> None:
    """Validate report evidence without hydrating any referenced artifact."""

    if not isinstance(report, Mapping):
        raise EvidenceReferenceError("status report must be a mapping")
    if isinstance(inline_max_bytes, bool) or not isinstance(inline_max_bytes, int):
        raise EvidenceReferenceError("inline_max_bytes must be an int")
    if inline_max_bytes < 0:
        raise EvidenceReferenceError("inline_max_bytes must be non-negative")
    for block_name in EVIDENCE_BLOCKS:
        if block_name not in report:
            continue
        value = report[block_name]
        if isinstance(value, Mapping) and "evidence_ref" in value:
            if set(value) != {"evidence_ref"}:
                raise EvidenceReferenceError(
                    f"{block_name} evidence_ref is mutually exclusive with inline fields"
                )
            validate_evidence_ref(value["evidence_ref"], repo_root=repo_root, change_id=change_id)
            continue
        if len(_canonical_bytes(value)) > inline_max_bytes:
            raise EvidenceReferenceRequired(
                f"{block_name} exceeds inline evidence budget "
                f"({inline_max_bytes} bytes); provide evidence_ref"
            )


def prepare_status_report_evidence(
    report: Mapping[str, Any],
    *,
    repo_root: str | Path,
    change_id: str,
    inline_max_bytes: int = DEFAULT_EVIDENCE_INLINE_MAX_BYTES,
) -> dict[str, Any]:
    """Return a report copy using inline-or-reference evidence transport.

    Blocks at or below ``inline_max_bytes`` remain byte-compatible inline.
    Larger blocks are materialized once under the active change evidence
    directory and replaced by a reference.  No truncation is performed.
    Existing references are validated and never read into the returned report.
    """

    if not isinstance(report, Mapping):
        raise EvidenceReferenceError("status report must be a mapping")
    if isinstance(inline_max_bytes, bool) or not isinstance(inline_max_bytes, int):
        raise EvidenceReferenceError("inline_max_bytes must be an int")
    if inline_max_bytes < 0:
        raise EvidenceReferenceError("inline_max_bytes must be non-negative")
    prepared = deepcopy(dict(report))
    for block_name in EVIDENCE_BLOCKS:
        if block_name in prepared:
            prepared[block_name] = _prepare_block(
                block_name,
                prepared[block_name],
                repo_root=repo_root,
                change_id=change_id,
                inline_max_bytes=inline_max_bytes,
            )
    return prepared


def serialize_status_report_evidence(
    report: Mapping[str, Any],
    *,
    repo_root: str | Path,
    change_id: str,
    inline_max_bytes: int = DEFAULT_EVIDENCE_INLINE_MAX_BYTES,
) -> dict[str, Any]:
    """Serializer-facing alias for :func:`prepare_status_report_evidence`."""

    return prepare_status_report_evidence(
        report,
        repo_root=repo_root,
        change_id=change_id,
        inline_max_bytes=inline_max_bytes,
    )
