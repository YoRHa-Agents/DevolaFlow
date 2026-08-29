"""Safe, explicit archiving for registered ``.local`` surfaces.

This module is intentionally independent from the active-change archive and
the research archive.  Inventory and planning are read-only.  Physical moves
require an explicit subset of a previously produced :class:`ArchivePlan`,
strict safety evidence, and a destination that is still exactly the one in
the plan.

The public surface is deliberately small:

``inventory_tasks``
    Read task folders in canonical and flat layouts.
``build_archive_plan``
    Produce a deterministic, report-only plan.
``apply_archive_plan``
    Apply an explicitly approved subset of plan entries.
``inspect_safety``
    Run the strict pre-action safety inspection.
``render_index`` and ``append_mapping_record``
    Manage the generated navigation view and the dedicated append-only ledger.

All paths carried by public records are repository-relative POSIX strings.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from devolaflow._durability import _same_device
from devolaflow.local.archive_kernel import (
    _finding,
    _has_symlink_component,
    _load_mapping_records,  # noqa: F401
    _relative_path,
    _relative_posix,
    _run_git,
    append_mapping_record,
    render_index,
)
from devolaflow.local.archive_kernel import (
    apply_archive_plan as _kernel_apply_archive_plan,
)
from devolaflow.local.archive_kernel import (
    inspect_safety as _kernel_inspect_safety,
)
from devolaflow.local.archive_models import (
    ArchiveApproval,
    ArchiveError,
    ArchivePlan,
    ArchiveRecord,
    ArchiveResult,
    Finding,
    Lifecycle,
    MappingRecord,
    PlanEntry,
    ProtectionVerdict,
    SafetyInspection,
    TaskRecord,
)

logger = logging.getLogger(__name__)

TASK_ROOT = Path(".local") / "tasks"
INDEX_PATH = Path(".local") / "tasks" / "INDEX.md"
MAPPING_PATH = Path(".local") / "tasks" / "archive-mappings.yaml"
INDEX_MARKER = "<!-- devolaflow: generated task archive index -->"
LIFECYCLE_VALUES = ("active", "done", "stale", "unknown")
_STATUS_RE = re.compile(r"\bstatus\s*:\s*([A-Za-z_-]+)", re.IGNORECASE)
_ID_RE = re.compile(r"\b(?:id|task[_ -]?id)\s*:\s*([^\s|]+)", re.IGNORECASE)
_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9._-]+")
_KNOWN_METADATA_NAMES = (
    "task.yaml",
    "task.yml",
    "metadata.yaml",
    "metadata.yml",
    "STATUS.yaml",
    "STATUS.yml",
    "status.yaml",
    "status.yml",
    "task.md",
    "TASK.md",
    "README.md",
)


def _slug(value: object, fallback: str) -> tuple[str, Finding | None]:
    if not isinstance(value, str) or not value.strip():
        return fallback, None
    cleaned = _SAFE_KEY_RE.sub("-", value.strip()).strip("-._")
    if not cleaned:
        return fallback, _finding("INVALID_CLUSTER", f"cluster value is not usable: {value!r}")
    if cleaned != value.strip():
        return cleaned.lower(), _finding(
            "NORMALIZED_CLUSTER", f"cluster value normalized to stable key {cleaned.lower()!r}"
        )
    return cleaned.lower(), None


def _metadata_documents(task_path: Path) -> tuple[dict[str, Any], list[Finding]]:
    """Read only conventional task metadata files; never guess from mtime."""

    documents: list[dict[str, Any]] = []
    findings: list[Finding] = []
    for name in _KNOWN_METADATA_NAMES:
        path = task_path / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(_finding("UNREADABLE_METADATA", f"{name}: {exc}"))
            continue
        parsed: object = None
        if path.suffix.lower() in {".yaml", ".yml"}:
            try:
                parsed = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                findings.append(_finding("MALFORMED_METADATA", f"{name}: {exc}"))
                continue
        elif text.startswith("---"):
            pieces = text.split("---", 2)
            if len(pieces) == 3:
                try:
                    parsed = yaml.safe_load(pieces[1])
                except yaml.YAMLError as exc:
                    findings.append(_finding("MALFORMED_METADATA", f"{name}: {exc}"))
                    continue
        if isinstance(parsed, dict):
            documents.append(parsed)
            continue
        if path.suffix.lower() in {".yaml", ".yml"} and parsed is not None:
            findings.append(_finding("MALFORMED_METADATA", f"{name}: metadata must be a mapping"))
        status_match = _STATUS_RE.search(text)
        id_match = _ID_RE.search(text)
        if status_match or id_match:
            documents.append(
                {
                    **({"status": status_match.group(1)} if status_match else {}),
                    **({"id": id_match.group(1)} if id_match else {}),
                }
            )
    if not documents and not findings:
        findings.append(_finding("MISSING_METADATA", "no recognized task metadata was found"))
    merged: dict[str, Any] = {}
    for document in documents:
        for key, value in document.items():
            if key in merged and merged[key] != value:
                findings.append(
                    _finding("CONFLICTING_METADATA", f"metadata key has conflicting values: {key}")
                )
            else:
                merged[key] = value
    return merged, findings


def _metadata_value(metadata: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata:
            return metadata[key]
    nested = metadata.get("metadata")
    if isinstance(nested, Mapping):
        for key in keys:
            if key in nested:
                return nested[key]
    return None


def _classify_metadata(metadata: Mapping[str, Any], findings: list[Finding]) -> Lifecycle:
    raw = _metadata_value(metadata, "lifecycle", "status", "state")
    if not isinstance(raw, str):
        findings.append(_finding("UNKNOWN_LIFECYCLE", "lifecycle requires explicit metadata"))
        return Lifecycle.UNKNOWN
    value = raw.strip().lower()
    if value not in LIFECYCLE_VALUES:
        findings.append(_finding("UNKNOWN_LIFECYCLE", f"unsupported lifecycle value: {raw!r}"))
        return Lifecycle.UNKNOWN
    return Lifecycle(value)


def _task_id(task_path: Path, metadata: Mapping[str, Any], findings: list[Finding]) -> str:
    raw = _metadata_value(metadata, "task_id", "id", "name")
    value = raw if isinstance(raw, str) and raw.strip() else task_path.name
    if "/" in value or "\\" in value or value in {".", ".."}:
        findings.append(_finding("INVALID_TASK_ID", f"task id cannot be a path: {value!r}"))
        return task_path.name
    return value.strip()


def _layout_and_cluster(
    tasks_root: Path, task_path: Path, metadata: Mapping[str, Any]
) -> tuple[str, str]:
    relative = task_path.relative_to(tasks_root)
    if len(relative.parts) >= 3 and relative.parts[1] == "active":
        return "canonical-active", relative.parts[0]
    if len(relative.parts) >= 4 and relative.parts[1] == "archive":
        return "canonical-archive", relative.parts[0]
    cluster, _ = _slug(
        _metadata_value(metadata, "cluster", "domain", "category"),
        "unclassified",
    )
    return "flat", cluster


def _protected_verdict(
    repo_root: Path, tasks_root: Path, task_path: Path
) -> tuple[ProtectionVerdict, str, list[Finding]]:
    findings: list[Finding] = []
    has_symlink = _has_symlink_component(repo_root, task_path)
    try:
        relative = task_path.relative_to(repo_root)
        resolved = task_path.resolve(strict=False)
        resolved.relative_to(repo_root.resolve())
        resolved.relative_to(tasks_root.resolve())
    except (ValueError, OSError):
        if has_symlink:
            findings.append(_finding("SYMLINK_PATH", "source or a descendant is a symlink"))
        return (
            ProtectionVerdict.UNSAFE if has_symlink else ProtectionVerdict.PROTECTED,
            "outside .local/tasks source boundary",
            [
                _finding("PROTECTED_PATH", "source is outside the .local/tasks boundary"),
                *findings,
            ],
        )
    if any(
        str(relative).replace("\\", "/") == prefix
        or str(relative).replace("\\", "/").startswith(prefix + "/")
        for prefix in (
            ".local/.agent",
            ".local/memory/specs",
            ".local/research",
            ".local/human/input",
            ".rules",
            "src",
            "schemas",
            "scripts",
            "workflow-system",
        )
    ):
        return (
            ProtectionVerdict.PROTECTED,
            "protected runtime or source/config surface",
            [_finding("PROTECTED_PATH", "path belongs to a protected source/config surface")],
        )
    if has_symlink:
        return (
            ProtectionVerdict.UNSAFE,
            "symlink component requires explicit human review",
            [_finding("SYMLINK_PATH", "source or a descendant is a symlink")],
        )
    if not task_path.is_dir():
        return (
            ProtectionVerdict.AMBIGUOUS,
            "source is not a readable directory",
            [_finding("UNREADABLE_SOURCE", "task source is missing or not a directory")],
        )
    return ProtectionVerdict.ALLOWED, "", findings


def inventory_tasks(repo_root: str | Path) -> tuple[TaskRecord, ...]:
    """Inventory canonical and flat task folders without writing anything.

    Canonical folders are ``<cluster>/active/<id>`` and
    ``<cluster>/archive/<period>/<id>``.  Direct child directories are treated
    as brownfield flat tasks.  Names, mtimes, and sizes never determine
    lifecycle.
    """

    root = Path(repo_root)
    if not root.is_dir():
        logger.warning("local archive inventory refused: repository root is missing: %s", root)
        return ()
    tasks_root = root / TASK_ROOT
    if not tasks_root.exists():
        return ()
    if tasks_root.is_symlink() or not tasks_root.is_dir():
        logger.warning("local archive inventory found unsafe .local/tasks path: %s", tasks_root)
        return ()

    candidates: list[Path] = []
    seen: set[Path] = set()
    canonical_clusters: set[Path] = set()
    for cluster in sorted(tasks_root.iterdir(), key=lambda p: p.name):
        if not cluster.is_dir() and not cluster.is_symlink():
            continue
        active = cluster / "active"
        if active.is_dir() and not active.is_symlink():
            canonical_clusters.add(cluster)
            for child in sorted(active.iterdir(), key=lambda p: p.name):
                if child.is_dir() or child.is_symlink():
                    candidates.append(child)
                    seen.add(child)
        archive = cluster / "archive"
        if archive.is_dir() and not archive.is_symlink():
            canonical_clusters.add(cluster)
            for period in sorted(archive.iterdir(), key=lambda p: p.name):
                if not period.is_dir() or period.is_symlink():
                    continue
                for child in sorted(period.iterdir(), key=lambda p: p.name):
                    if child.is_dir() or child.is_symlink():
                        candidates.append(child)
                        seen.add(child)
        if cluster not in canonical_clusters:
            candidates.append(cluster)
            seen.add(cluster)

    records: list[TaskRecord] = []
    for task_path in sorted(candidates, key=lambda p: p.relative_to(tasks_root).as_posix()):
        metadata, metadata_findings = _metadata_documents(task_path)
        findings = list(metadata_findings)
        lifecycle = _classify_metadata(metadata, findings)
        task_id = _task_id(task_path, metadata, findings)
        layout, cluster = _layout_and_cluster(tasks_root, task_path, metadata)
        normalized_cluster, cluster_finding = _slug(cluster, "unclassified")
        if cluster_finding:
            findings.append(cluster_finding)
        protection, reason, protection_findings = _protected_verdict(root, tasks_root, task_path)
        findings.extend(protection_findings)
        records.append(
            TaskRecord(
                source=_relative_posix(root, task_path),
                task_id=task_id,
                cluster_key=normalized_cluster,
                layout=layout,
                lifecycle=lifecycle,
                protection=protection,
                protection_reason=reason,
                metadata=dict(metadata),
                findings=tuple(findings),
            )
        )
    return tuple(records)


def _period_for(record: TaskRecord) -> str:
    raw = _metadata_value(record.metadata, "completed_at", "archived_at", "date", "period")
    if isinstance(raw, str):
        match = re.match(r"^(\d{4}(?:-\d{2})?(?:-\d{2})?)", raw.strip())
        if match:
            return match.group(1)
    path_parts = PurePosixPath(record.source).parts
    if record.layout == "canonical-archive" and len(path_parts) >= 2:
        return path_parts[-2]
    return "undated"


def _destination_for(root: Path, record: TaskRecord) -> str:
    if record.lifecycle is Lifecycle.ACTIVE:
        destination = TASK_ROOT / record.cluster_key / "active" / record.task_id
    elif record.lifecycle in {Lifecycle.DONE, Lifecycle.STALE}:
        destination = (
            TASK_ROOT / record.cluster_key / "archive" / _period_for(record) / record.task_id
        )
    else:
        destination = TASK_ROOT / record.cluster_key / "review" / record.task_id
    return destination.as_posix()


def build_archive_plan(
    repo_root: str | Path,
    *,
    records: Iterable[TaskRecord] | None = None,
    surface: str = "tasks",
) -> ArchivePlan:
    """Build a deterministic report-only plan for a registered surface.

    The default task path intentionally retains its historical implementation
    and byte-level output.  Other surfaces are delegated to their adapter.
    """

    if surface != "tasks":
        from devolaflow.local.archive_adapters import build_surface_archive_plan

        if records is not None:
            raise ArchiveError("custom records are supported only for the tasks surface")
        return build_surface_archive_plan(repo_root, surface)

    root = Path(repo_root)
    inventory = tuple(records) if records is not None else inventory_tasks(root)
    entries: list[PlanEntry] = []
    findings: list[Finding] = []
    for record in inventory:
        destination = _destination_for(root, record)
        source = record.source
        protection = record.protection
        protection_reason = record.protection_reason
        source_path, source_error = _relative_path(root, source)
        if source_error:
            protection = ProtectionVerdict.PROTECTED
            protection_reason = source_error.message
            record_findings = record.findings + (source_error,)
        else:
            assert source_path is not None
            try:
                (root / source_path).resolve(strict=False).relative_to((root / TASK_ROOT).resolve())
            except (OSError, ValueError):
                protection = ProtectionVerdict.PROTECTED
                protection_reason = "outside .local/tasks source boundary"
                record_findings = record.findings + (
                    _finding("PROTECTED_PATH", "source is outside the .local/tasks boundary"),
                )
            else:
                record_findings = record.findings
        if protection is not ProtectionVerdict.ALLOWED:
            action = "refuse"
        elif record.lifecycle is Lifecycle.UNKNOWN:
            action = "review"
        elif source == destination:
            action = "retain"
        else:
            action = "move"
        entries.append(
            PlanEntry(
                source=source,
                destination=destination,
                cluster_key=record.cluster_key,
                classification=record.lifecycle.value,
                action=action,
                protection=protection,
                protection_reason=protection_reason,
                findings=record_findings,
            )
        )
    by_destination: dict[str, list[PlanEntry]] = {}
    for entry in entries:
        by_destination.setdefault(entry.destination, []).append(entry)
    duplicate_destinations = {
        destination for destination, matches in by_destination.items() if len(matches) > 1
    }
    if duplicate_destinations:
        for destination in sorted(duplicate_destinations):
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
    return ArchivePlan(entries=tuple(entries), findings=tuple(findings))


def inspect_safety(
    repo_root: str | Path,
    source: str | Path,
    destination: str | Path | None = None,
    *,
    source_boundary: str | Path = TASK_ROOT,
    destination_boundary: str | Path | None = None,
    requires_directory: bool = True,
) -> SafetyInspection:
    return _kernel_inspect_safety(
        repo_root,
        source,
        destination,
        source_boundary=source_boundary,
        destination_boundary=destination_boundary,
        requires_directory=requires_directory,
        run_git=_run_git,
        same_device=_same_device,
    )


def apply_archive_plan(
    repo_root: str | Path,
    plan: ArchivePlan,
    approved: ArchiveApproval | ArchivePlan | Sequence[PlanEntry] | Sequence[str] | None = None,
    *,
    mapping_path: str | Path = MAPPING_PATH,
    index_path: str | Path = INDEX_PATH,
) -> ArchiveResult:
    """Apply an explicitly approved subset through the shared archive kernel.

    There is intentionally no deletion action.
    """

    return _kernel_apply_archive_plan(
        repo_root,
        plan,
        approved,
        mapping_path=mapping_path,
        index_path=index_path,
        build_plan=build_archive_plan,
        append_mapping=append_mapping_record,
        run_git=_run_git,
        same_device=_same_device,
    )


from devolaflow.local.archive_adapters import (  # noqa: E402
    ARCHIVE_ADAPTERS,
    ArchiveAdapter,
    build_surface_archive_plan,
    get_archive_adapter,
    inventory_surface,
)

__all__ = [
    "ARCHIVE_ADAPTERS",
    "ArchiveError",
    "ArchiveApproval",
    "ArchiveAdapter",
    "ArchivePlan",
    "ArchiveRecord",
    "ArchiveResult",
    "Finding",
    "INDEX_PATH",
    "Lifecycle",
    "MAPPING_PATH",
    "MappingRecord",
    "PlanEntry",
    "ProtectionVerdict",
    "SafetyInspection",
    "TaskRecord",
    "append_mapping_record",
    "apply_archive_plan",
    "build_archive_plan",
    "build_surface_archive_plan",
    "get_archive_adapter",
    "inspect_safety",
    "inventory_tasks",
    "inventory_surface",
    "render_index",
]
