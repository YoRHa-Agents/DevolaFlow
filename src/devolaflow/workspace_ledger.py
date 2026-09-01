"""Shared append-only ledger and generated-view primitives (v24.0.0).

The risk-parking domain (`devolaflow.parking`) and the workspace-compact
domain (`devolaflow.workspace_compact`) both need the same four guarantees
that `devolaflow.local.archive_kernel` established for cross-surface local
archiving:

1. repository-relative path validation that refuses traversal and symlinks;
2. append-only YAML ledgers whose rows are never edited in place;
3. generated views that carry a surface marker, refuse to clobber a
   human-maintained file, and detect drift from their authoritative ledger;
4. atomic writes that flush both the file and its directory entry.

`archive_kernel` is deliberately left untouched — it owns the
`tasks`/`feedbacks`/`research` surfaces and carries a large pinned test
surface. This module owns the primitives the v24 domains share, which keeps
each registry under exactly one owner per A-5.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devolaflow._durability import fsync_directory as _fsync_directory

logger = logging.getLogger(__name__)

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class LedgerError(RuntimeError):
    """Raised for malformed ledger input or an unsafe persistence request."""


@dataclass(frozen=True)
class Finding:
    """A deterministic, machine-readable refusal or drift finding."""

    code: str
    message: str


def finding(code: str, message: str) -> Finding:
    """Build a :class:`Finding` without importing the dataclass everywhere."""

    return Finding(code=code, message=message)


def utc_now() -> str:
    """Return the current UTC time in the repository's canonical format."""

    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def relative_path(repo_root: Path, value: str | Path) -> tuple[Path | None, Finding | None]:
    """Resolve a caller-supplied path while refusing absolute/traversal input."""

    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, finding("PATH_TRAVERSAL", f"path is not repository-relative: {value}")
    parts = [part for part in candidate.parts if part not in {"", "."}]
    candidate = Path(*parts) if parts else Path()
    resolved_root = repo_root.resolve()
    try:
        (repo_root / candidate).resolve(strict=False).relative_to(resolved_root)
    except (OSError, ValueError):
        return None, finding("OUTSIDE_ROOT", f"path escapes the root: {value}")
    return candidate, None


def has_symlink_component(root: Path, path: Path) -> bool:
    """Return true when any component beneath ``root`` is a symlink."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def sha256_bytes(payload: bytes) -> str:
    """Return the hex digest used by mapping rows to prove zero content loss."""

    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    """Return a digest covering one file, or a whole directory's contents.

    Directory digests fold each contained file's repository-relative path and
    content into one stable hash so a relocated folder can be proven byte
    identical after the move.
    """

    if path.is_file():
        return sha256_bytes(path.read_bytes())
    digest = hashlib.sha256()
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    """Write text through a temporary file and flush the directory entry."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def load_ledger_rows(
    path: Path,
    *,
    required_fields: Sequence[str] = ("sequence",),
) -> tuple[dict[str, Any], ...]:
    """Load every append-only row, refusing malformed or duplicated sequences."""

    if not path.exists():
        return ()
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise LedgerError(f"ledger is unreadable or malformed: {path}: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for document in documents:
        if document is None:
            continue
        if not isinstance(document, dict):
            raise LedgerError(f"ledger row is not a mapping: {path}")
        missing = [key for key in required_fields if key not in document]
        if missing:
            raise LedgerError(f"ledger row is missing {', '.join(missing)}: {path}")
        sequence = document.get("sequence")
        if type(sequence) is not int or sequence < 1:
            raise LedgerError(f"ledger sequence is not a positive integer: {path}")
        rows.append(document)
    if len({row["sequence"] for row in rows}) != len(rows):
        raise LedgerError(f"ledger contains duplicate sequence values: {path}")
    return tuple(rows)


def append_ledger_row(
    path: Path,
    row: Mapping[str, Any],
    *,
    required_fields: Sequence[str] = (),
    unique_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Append exactly one immutable row and return it with its sequence.

    The sequence is assigned by the ledger, never by the caller, so two
    concurrent writers cannot silently agree on the same number. Rows whose
    ``unique_fields`` collide with an existing row are refused rather than
    overwritten, mirroring the W-27 duplicate-source contract.
    """

    missing = [key for key in required_fields if key not in row]
    if missing:
        raise LedgerError(f"row is missing required fields: {', '.join(missing)}")
    existing = load_ledger_rows(path, required_fields=("sequence",))
    for field_name in unique_fields:
        value = row.get(field_name)
        if value is None:
            continue
        if any(prior.get(field_name) == value for prior in existing):
            raise LedgerError(f"ledger already records {field_name}={value!r}; refusing duplicate")
    record: dict[str, Any] = {
        "sequence": max((int(prior["sequence"]) for prior in existing), default=0) + 1
    }
    record.update({key: value for key, value in row.items() if key != "sequence"})
    rendered = yaml.safe_dump(
        record,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "ab") as stream:
            if existing:
                stream.write(b"---\n")
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_directory(path.parent)
    except OSError as exc:
        logger.warning("ledger append failed: %s", exc)
        raise LedgerError(f"could not append ledger row: {path}: {exc}") from exc
    return record


def inspect_generated_target(
    root: Path,
    path: Path,
    *,
    marker: str,
    expected: str | None = None,
) -> tuple[Finding, ...]:
    """Refuse symlinked, unreadable, human-maintained, or drifted views."""

    if path.is_symlink() or has_symlink_component(root, path):
        return (finding("SYMLINK_VIEW", f"generated view path is a symlink: {path.name}"),)
    if not path.exists():
        return ()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return (finding("UNREADABLE_VIEW", f"generated view cannot be read: {exc}"),)
    if not text.startswith(marker):
        return (
            finding(
                "HUMAN_VIEW",
                f"refusing to overwrite a human-maintained file: {path.name}",
            ),
        )
    if expected is not None and text != expected:
        return (
            finding(
                "VIEW_DRIFT",
                f"generated view does not match its authoritative ledger: {path.name}",
            ),
        )
    return ()


def write_generated_view(
    root: Path,
    path: Path,
    content: str,
    *,
    marker: str,
) -> tuple[Finding, ...]:
    """Persist a generated view, refusing to clobber a human-authored file."""

    if not content.startswith(marker):
        raise LedgerError("generated content must begin with its surface marker")
    findings = inspect_generated_target(root, path, marker=marker)
    if findings:
        return findings
    try:
        atomic_write_text(path, content)
    except OSError as exc:
        logger.warning("generated view persistence failed: %s", exc)
        return (finding("VIEW_WRITE_ERROR", f"could not persist generated view: {exc}"),)
    return ()


def detect_view_drift(
    root: Path,
    path: Path,
    expected: str,
    *,
    marker: str,
) -> tuple[Finding, ...]:
    """Report drift for a view that should already match its ledger."""

    if not path.exists():
        return (finding("VIEW_MISSING", f"generated view is absent: {path.name}"),)
    return inspect_generated_target(root, path, marker=marker, expected=expected)


def render_rows_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    """Render a deterministic Markdown table body for a generated view."""

    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


__all__ = [
    "TIMESTAMP_FORMAT",
    "Finding",
    "LedgerError",
    "append_ledger_row",
    "atomic_write_text",
    "detect_view_drift",
    "finding",
    "has_symlink_component",
    "inspect_generated_target",
    "load_ledger_rows",
    "relative_path",
    "render_rows_table",
    "sha256_bytes",
    "sha256_path",
    "utc_now",
    "write_generated_view",
]
