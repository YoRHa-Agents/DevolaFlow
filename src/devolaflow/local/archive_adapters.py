"""Registered adapters for the surface-neutral local archive kernel.

The registry in this module is the sole owner of local-archive surface
membership.  Adapters only discover and classify candidates; the safety and
apply machinery remains in :mod:`devolaflow.local.archive_kernel`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from devolaflow.local.archive_kernel import _has_symlink_component
from devolaflow.local.archive_models import (
    ArchivePlan,
    ArchiveRecord,
    Finding,
    PlanEntry,
    ProtectionVerdict,
)

_VERSIONED_FEEDBACK = re.compile(r"^feedback_for_v(?P<version>[0-9]+(?:\.[0-9]+){0,2})\.md$")
_VERSIONED_RESEARCH = re.compile(r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)_.+")
_RELEASE_HEADING = re.compile(r"^##\s+\[v?(?P<version>[0-9]+(?:\.[0-9]+){0,2})\]", re.MULTILINE)


@dataclass(frozen=True)
class ArchiveAdapter:
    """Configuration and discovery entry for one archival surface."""

    name: str
    source_root: str
    archive_root: str
    mapping_path: str
    index_path: str
    index_marker: str
    requires_directory: bool
    inventory: Callable[[Path], tuple[ArchiveRecord, ...]]


def _finding(code: str, message: str) -> Finding:
    return Finding(code=code, message=message)


def _source_protection(
    root: Path, source_root: str, path: Path, *, requires_directory: bool
) -> tuple[ProtectionVerdict, str, list[Finding]]:
    """Apply the common repository-relative and filesystem checks."""

    findings: list[Finding] = []
    boundary = root / source_root
    if _has_symlink_component(root, path):
        return (
            ProtectionVerdict.UNSAFE,
            "symlink component requires explicit human review",
            [_finding("SYMLINK_PATH", "source or a descendant is a symlink")],
        )
    try:
        path.resolve(strict=False).relative_to(boundary.resolve())
    except (OSError, ValueError):
        return (
            ProtectionVerdict.PROTECTED,
            f"outside {source_root} source boundary",
            [_finding("PROTECTED_PATH", f"source is outside {source_root}")],
        )
    try:
        relative = path.relative_to(root)
    except ValueError:
        return (
            ProtectionVerdict.PROTECTED,
            "source is outside the repository",
            [_finding("PROTECTED_PATH", "source is outside the repository")],
        )
    if any(part in {".agent", "human"} for part in relative.parts):
        return (
            ProtectionVerdict.PROTECTED,
            "protected local workspace surface",
            [_finding("PROTECTED_PATH", "source belongs to a protected local surface")],
        )
    if not path.exists():
        return (
            ProtectionVerdict.AMBIGUOUS,
            "source is missing",
            [_finding("UNREADABLE_SOURCE", "source is missing")],
        )
    if requires_directory and not path.is_dir():
        return (
            ProtectionVerdict.AMBIGUOUS,
            "source is not a directory",
            [_finding("UNREADABLE_SOURCE", "source is not a directory")],
        )
    if not requires_directory and not path.is_file():
        return (
            ProtectionVerdict.AMBIGUOUS,
            "source is not a readable file",
            [_finding("UNREADABLE_SOURCE", "source is not a regular file")],
        )
    try:
        if requires_directory:
            next(path.iterdir(), None)
        else:
            path.read_bytes()
    except (OSError, UnicodeError) as exc:
        return (
            ProtectionVerdict.AMBIGUOUS,
            "source is unreadable",
            [_finding("UNREADABLE_SOURCE", f"source cannot be read: {exc}")],
        )
    return ProtectionVerdict.ALLOWED, "", findings


def _feedback_version_released(root: Path, version: str) -> bool:
    changelog = root / "CHANGELOG.md"
    try:
        text = changelog.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return any(match.group("version") == version for match in _RELEASE_HEADING.finditer(text))


def _feedback_version_resolved(root: Path, filename: str, version: str) -> bool:
    tracker = root / ".local" / "feedbacks" / "TRACKER.md"
    try:
        text = tracker.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    match = re.search(r"^##\s+Resolved\s*$([\s\S]*?)(?=^##\s+|\Z)", text, re.MULTILINE)
    if match is None:
        return False
    section = match.group(1)
    return filename in section or re.search(rf"\bv?{re.escape(version)}\b", section) is not None


def _feedback_inventory(root: Path) -> tuple[ArchiveRecord, ...]:
    source_root = root / ".local" / "feedbacks"
    if not source_root.is_dir() or source_root.is_symlink():
        return ()
    records: list[ArchiveRecord] = []
    for path in sorted(source_root.iterdir(), key=lambda item: item.name):
        if not path.is_file() and not path.is_symlink():
            continue
        match = _VERSIONED_FEEDBACK.fullmatch(path.name)
        if match is None:
            continue
        version = match.group("version")
        protection, reason, findings = _source_protection(
            root, ".local/feedbacks", path, requires_directory=False
        )
        if not _feedback_version_released(root, version):
            findings.append(
                _finding("FEEDBACK_VERSION_NOT_RELEASED", f"release {version} is not released")
            )
        if not _feedback_version_resolved(root, path.name, version):
            findings.append(
                _finding("FEEDBACK_NOT_RESOLVED", f"{path.name} is not resolved in TRACKER.md")
            )
        records.append(
            ArchiveRecord(
                source=path.relative_to(root).as_posix(),
                identity=path.name,
                classification="done" if not findings else "unknown",
                protection=protection,
                protection_reason=reason,
                metadata={"version": version},
                findings=tuple(findings),
            )
        )
    return tuple(records)


def _research_inventory(root: Path) -> tuple[ArchiveRecord, ...]:
    source_root = root / ".local" / "research"
    if not source_root.is_dir() or source_root.is_symlink():
        return ()
    records: list[ArchiveRecord] = []
    for path in sorted(source_root.iterdir(), key=lambda item: item.name):
        if not path.is_file() and not path.is_symlink():
            continue
        match = _VERSIONED_RESEARCH.match(path.name)
        if match is None:
            continue
        version = match.group("version")
        protection, reason, findings = _source_protection(
            root, ".local/research", path, requires_directory=False
        )
        cycle_archive = root / "docs" / "cycle-archive" / f"v{version}"
        if not cycle_archive.is_dir():
            findings.append(
                _finding(
                    "RESEARCH_CYCLE_ARCHIVE_MISSING",
                    f"corresponding cycle archive is missing: docs/cycle-archive/v{version}",
                )
            )
        records.append(
            ArchiveRecord(
                source=path.relative_to(root).as_posix(),
                identity=path.name,
                classification="done" if not findings else "unknown",
                protection=protection,
                protection_reason=reason,
                metadata={"version": version},
                findings=tuple(findings),
            )
        )
    return tuple(records)


def _task_inventory(root: Path) -> tuple[ArchiveRecord, ...]:
    from devolaflow.local.archive import inventory_tasks

    return tuple(
        ArchiveRecord(
            source=record.source,
            identity=record.task_id,
            classification=record.lifecycle.value,
            protection=record.protection,
            protection_reason=record.protection_reason,
            metadata=record.metadata,
            findings=record.findings,
        )
        for record in inventory_tasks(root)
    )


ARCHIVE_ADAPTERS: dict[str, ArchiveAdapter] = {
    "tasks": ArchiveAdapter(
        name="tasks",
        source_root=".local/tasks",
        archive_root=".local/tasks",
        mapping_path=".local/tasks/archive-mappings.yaml",
        index_path=".local/tasks/INDEX.md",
        index_marker="<!-- devolaflow: generated task archive index -->",
        requires_directory=True,
        inventory=_task_inventory,
    ),
    "feedbacks": ArchiveAdapter(
        name="feedbacks",
        source_root=".local/feedbacks",
        archive_root=".local/feedbacks/archive",
        mapping_path=".local/feedbacks/archive/archive-mappings.yaml",
        index_path=".local/feedbacks/archive/INDEX.md",
        index_marker="<!-- devolaflow: generated feedback archive index -->",
        requires_directory=False,
        inventory=_feedback_inventory,
    ),
    "research": ArchiveAdapter(
        name="research",
        source_root=".local/research",
        archive_root=".local/research/archive",
        mapping_path=".local/research/archive/archive-mappings.yaml",
        index_path=".local/research/archive/INDEX.md",
        index_marker="<!-- devolaflow: generated research archive index -->",
        requires_directory=False,
        inventory=_research_inventory,
    ),
}


def get_archive_adapter(surface: str) -> ArchiveAdapter:
    """Return the registered adapter, rejecting unregistered surfaces."""

    try:
        return ARCHIVE_ADAPTERS[surface]
    except KeyError as exc:
        raise ValueError(f"unknown local archive surface: {surface!r}") from exc


def inventory_surface(repo_root: str | Path, surface: str) -> tuple[ArchiveRecord, ...]:
    """Inventory one registered surface without writing."""

    return get_archive_adapter(surface).inventory(Path(repo_root))


def build_surface_archive_plan(repo_root: str | Path, surface: str) -> ArchivePlan:
    """Build a deterministic report-only plan for a registered surface."""

    root = Path(repo_root)
    adapter = get_archive_adapter(surface)
    if surface == "tasks":
        from devolaflow.local.archive import build_archive_plan

        return build_archive_plan(root)
    entries: list[PlanEntry] = []
    findings: list[Finding] = []
    for record in inventory_surface(root, surface):
        version = str(record.metadata.get("version", "undated"))
        destination = (
            f"{adapter.archive_root}/{record.identity}"
            if surface == "feedbacks"
            else f"{adapter.archive_root}/{version}/{record.identity}"
        )
        action = (
            "move"
            if not record.findings and record.protection is ProtectionVerdict.ALLOWED
            else "refuse"
        )
        entry = PlanEntry(
            source=record.source,
            destination=destination,
            cluster_key=surface,
            classification=record.classification,
            action=action,
            protection=record.protection,
            protection_reason=record.protection_reason,
            findings=record.findings,
        )
        entries.append(entry)
    by_destination: dict[str, list[PlanEntry]] = {}
    for entry in entries:
        by_destination.setdefault(entry.destination, []).append(entry)
    for destination, matches in by_destination.items():
        if len(matches) < 2:
            continue
        finding = _finding("DUPLICATE_DESTINATION", f"multiple entries target {destination}")
        findings.append(finding)
        entries = [
            PlanEntry(
                **{
                    **entry.__dict__,
                    "action": "refuse" if entry.destination == destination else entry.action,
                    "findings": entry.findings
                    + ((finding,) if entry.destination == destination else ()),
                }
            )
            for entry in entries
        ]
    entries.sort(key=lambda entry: (entry.destination, entry.source))
    return ArchivePlan(
        entries=tuple(entries),
        findings=tuple(findings),
        source_boundary=adapter.source_root,
        surface=surface,
    )


__all__ = [
    "ARCHIVE_ADAPTERS",
    "ArchiveAdapter",
    "build_surface_archive_plan",
    "get_archive_adapter",
    "inventory_surface",
]
