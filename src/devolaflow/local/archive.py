"""Safe, explicit archiving of task folders under ``.local/tasks``.

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

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

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


class Lifecycle(StrEnum):
    """The only lifecycle values understood by local-task archiving."""

    ACTIVE = "active"
    DONE = "done"
    STALE = "stale"
    UNKNOWN = "unknown"


class ProtectionVerdict(StrEnum):
    """Protection is independent from :class:`Lifecycle`."""

    ALLOWED = "allowed"
    PROTECTED = "protected"
    UNSAFE = "unsafe"
    AMBIGUOUS = "ambiguous"


class ArchiveError(RuntimeError):
    """Raised for malformed API input or an unsafe persistence request."""


@dataclass(frozen=True)
class Finding:
    """A deterministic, machine-readable plan or safety finding."""

    code: str
    message: str


@dataclass(frozen=True)
class TaskRecord:
    """One discovered task folder and its conservative classification."""

    source: str
    task_id: str
    cluster_key: str
    layout: str
    lifecycle: Lifecycle
    protection: ProtectionVerdict
    protection_reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    findings: tuple[Finding, ...] = ()

    @property
    def protected(self) -> bool:
        """Return whether this record cannot be moved."""

        return self.protection is not ProtectionVerdict.ALLOWED

    @property
    def classification(self) -> str:
        """Return the lifecycle value as a schema-friendly string."""

        return self.lifecycle.value


@dataclass(frozen=True)
class PlanEntry:
    """A single explicit disposition in an archive plan."""

    source: str
    destination: str
    cluster_key: str
    classification: str
    action: str
    protection: ProtectionVerdict = ProtectionVerdict.ALLOWED
    protection_reason: str = ""
    findings: tuple[Finding, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        """Return the immutable source/destination approval identity."""

        return self.source, self.destination

    @property
    def protected(self) -> bool:
        """Return whether the planned source is independently protected."""

        return self.protection is not ProtectionVerdict.ALLOWED

    @property
    def lifecycle(self) -> Lifecycle:
        """Return the plan classification as the lifecycle enum."""

        return Lifecycle(self.classification)


@dataclass(frozen=True)
class ArchivePlan:
    """Deterministic report-only output from :func:`build_archive_plan`."""

    entries: tuple[PlanEntry, ...]
    findings: tuple[Finding, ...] = ()
    source_boundary: str = ".local/tasks"

    @property
    def fingerprint(self) -> str:
        """Return a stable digest for audit logs and approval UIs."""

        payload = [
            {
                "source": entry.source,
                "destination": entry.destination,
                "cluster_key": entry.cluster_key,
                "classification": entry.classification,
                "action": entry.action,
                "findings": [(f.code, f.message) for f in entry.findings],
            }
            for entry in self.entries
        ]
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()


@dataclass(frozen=True)
class SafetyInspection:
    """Evidence collected before a migration-sensitive action."""

    safe: bool
    findings: tuple[Finding, ...] = ()
    git_status: str = ""
    staged_diff: str = ""
    unstaged_diff: str = ""
    worktree_registry: str = ""
    ignored_status: str = ""


@dataclass(frozen=True)
class MappingRecord:
    """One immutable source-to-destination archive ledger row."""

    sequence: int
    source: str
    destination: str
    reason: str
    timestamp: str


@dataclass(frozen=True)
class ArchiveResult:
    """Structured result for an approved apply attempt."""

    applied: tuple[PlanEntry, ...] = ()
    mappings: tuple[MappingRecord, ...] = ()
    findings: tuple[Finding, ...] = ()
    refused: bool = False
    index_path: str | None = None

    @property
    def success(self) -> bool:
        """Return true only when the requested operation completed."""

        return not self.refused and not self.findings


def _finding(code: str, message: str) -> Finding:
    return Finding(code=code, message=message)


def _relative_path(repo_root: Path, value: str | Path) -> tuple[Path | None, Finding | None]:
    """Resolve a caller-supplied path while refusing absolute/traversal input."""

    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, _finding("PATH_TRAVERSAL", "path is not repository-relative")
    if any(part in {"", "."} for part in candidate.parts):
        candidate = Path(*[part for part in candidate.parts if part not in {"", "."}])
    resolved_root = repo_root.resolve()
    lexical = repo_root / candidate
    try:
        lexical.resolve(strict=False).relative_to(resolved_root)
    except (OSError, ValueError):
        return None, _finding("OUTSIDE_REPOSITORY", f"path escapes repository: {value}")
    return candidate, None


def _relative_posix(repo_root: Path, path: Path) -> str:
    """Convert an internal path to the public relative POSIX representation."""

    return path.relative_to(repo_root).as_posix()


def _has_symlink_component(repo_root: Path, path: Path) -> bool:
    """Return true when any existing component beneath root is a symlink."""

    try:
        relative = path.relative_to(repo_root)
    except ValueError:
        return True
    current = repo_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    if path.is_dir():
        for current_dir, dir_names, file_names in os.walk(path, followlinks=False):
            if any((Path(current_dir) / name).is_symlink() for name in (*dir_names, *file_names)):
                return True
    return False


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
    repo_root: str | Path, *, records: Iterable[TaskRecord] | None = None
) -> ArchivePlan:
    """Build a deterministic report-only plan from the current task inventory."""

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


def _run_git(root: Path, args: Sequence[str]) -> tuple[str | None, Finding | None]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("local archive git inspection failed: %s", exc)
        return None, _finding("GIT_INSPECTION_ERROR", f"could not run git {' '.join(args)}: {exc}")
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"git exited {completed.returncode}"
        try:
            message = message.replace(str(root.resolve()), ".")
        except OSError:
            logger.warning("could not normalize git inspection error path")
        return None, _finding("GIT_INSPECTION_ERROR", f"git {' '.join(args)}: {message}")
    return completed.stdout, None


def inspect_safety(
    repo_root: str | Path, source: str | Path, destination: str | Path | None = None
) -> SafetyInspection:
    """Run strict boundary, symlink, git, nested-repository, and worktree checks."""

    root = Path(repo_root)
    findings: list[Finding] = []
    source_rel, source_error = _relative_path(root, source)
    if source_error:
        findings.append(source_error)
        return SafetyInspection(False, tuple(findings))
    assert source_rel is not None
    source_path = root / source_rel
    destination_path: Path | None = None
    if destination is not None:
        destination_rel, destination_error = _relative_path(root, destination)
        if destination_error:
            findings.append(destination_error)
        else:
            assert destination_rel is not None
            destination_path = root / destination_rel
    tasks_root = root / TASK_ROOT
    for label, path in (("source", source_path), ("destination", destination_path)):
        if path is None:
            continue
        try:
            path.resolve(strict=False).relative_to(tasks_root.resolve())
        except (OSError, ValueError):
            findings.append(_finding("PROTECTED_PATH", f"{label} is outside .local/tasks"))
        if _has_symlink_component(root, path):
            findings.append(_finding("SYMLINK_PATH", f"{label} contains a symlink component"))
    if not source_path.exists() or not source_path.is_dir():
        findings.append(_finding("MISSING_SOURCE", f"source is not a directory: {source}"))
    if (
        destination_path is not None
        and destination_path.exists()
        and destination_path != source_path
    ):
        findings.append(
            _finding("DESTINATION_EXISTS", f"destination already exists: {destination}")
        )

    git_root, git_root_error = _run_git(root, ["rev-parse", "--show-toplevel"])
    if git_root_error:
        findings.append(git_root_error)
    elif git_root is not None:
        try:
            if Path(git_root.strip()).resolve() != root.resolve():
                findings.append(
                    _finding("REPOSITORY_BOUNDARY", "provided root is not the git repository root")
                )
        except OSError as exc:
            findings.append(
                _finding("REPOSITORY_BOUNDARY", f"git repository root is ambiguous: {exc}")
            )
    git_status, status_error = _run_git(root, ["status", "--short", "--untracked-files=all"])
    if status_error:
        findings.append(status_error)
    elif git_status:
        findings.append(
            _finding("DIRTY_TREE", "git status contains staged, unstaged, or untracked paths")
        )
        if any(
            "review" in line.lower() or "note" in line.lower() for line in git_status.splitlines()
        ):
            findings.append(
                _finding("UNTRACKED_REVIEW_NOTE", "git status contains a review/note path")
            )
    staged_diff, staged_error = _run_git(root, ["diff", "--cached", "--"])
    if staged_error:
        findings.append(staged_error)
    elif staged_diff:
        findings.append(_finding("STAGED_DIFF", "staged diff is non-empty"))
    unstaged_diff, unstaged_error = _run_git(root, ["diff", "--"])
    if unstaged_error:
        findings.append(unstaged_error)
    elif unstaged_diff:
        findings.append(_finding("UNSTAGED_DIFF", "unstaged diff is non-empty"))
    ignored_status, ignored_error = _run_git(
        root, ["status", "--ignored", "--short", "--untracked-files=all"]
    )
    if ignored_error:
        findings.append(ignored_error)
    elif ignored_status and any(
        line.startswith("!!") and ("review" in line.lower() or "note" in line.lower())
        for line in ignored_status.splitlines()
    ):
        findings.append(
            _finding("UNTRACKED_REVIEW_NOTE", "ignored review/note path requires review")
        )
    worktrees, worktree_error = _run_git(root, ["worktree", "list", "--porcelain"])
    if worktree_error:
        findings.append(worktree_error)
    elif worktrees:
        try:
            source_resolved = source_path.resolve()
            for line in worktrees.splitlines():
                if line.startswith("worktree "):
                    registered = Path(line[9:]).resolve()
                    try:
                        source_resolved.relative_to(registered)
                    except ValueError:
                        continue
                    if registered != root.resolve():
                        try:
                            registered_label = _relative_posix(root, registered)
                        except ValueError:
                            registered_label = "external worktree"
                        findings.append(
                            _finding(
                                "WORKTREE_REGISTRY",
                                f"source is inside registered worktree: {registered_label}",
                            )
                        )
        except OSError as exc:
            findings.append(_finding("WORKTREE_REGISTRY", f"worktree registry is ambiguous: {exc}"))
    if source_path.is_dir():
        walk_errors: list[OSError] = []
        for current_dir, dir_names, _file_names in os.walk(
            source_path, followlinks=False, onerror=walk_errors.append
        ):
            if ".git" in dir_names or (Path(current_dir) / ".git").is_file():
                findings.append(
                    _finding("NESTED_REPOSITORY", "source contains a nested repository")
                )
                break
        for error in walk_errors:
            findings.append(
                _finding("UNREADABLE_SOURCE", f"source traversal is ambiguous: {error}")
            )
    return SafetyInspection(
        safe=not findings,
        findings=tuple(findings),
        git_status=git_status or "",
        staged_diff=staged_diff or "",
        unstaged_diff=unstaged_diff or "",
        worktree_registry=worktrees or "",
        ignored_status=ignored_status or "",
    )


def _entry_from_approval(
    plan: ArchivePlan, approved: ArchivePlan | Sequence[PlanEntry] | Sequence[str]
) -> tuple[PlanEntry, ...] | tuple[Finding, ...]:
    approved_items: Sequence[PlanEntry | str] = (
        approved.entries if isinstance(approved, ArchivePlan) else approved
    )
    selected: list[PlanEntry] = []
    by_key = {entry.key: entry for entry in plan.entries}
    by_source = {entry.source: entry for entry in plan.entries}
    for item in approved_items:
        if isinstance(item, PlanEntry):
            candidate = by_key.get(item.key)
            if candidate is None or candidate != item:
                return (), (
                    _finding(
                        "APPROVAL_MISMATCH",
                        f"approved entry is not in the current plan: {item.source}",
                    ),
                )
        elif isinstance(item, str):
            candidate = by_source.get(item)
            if candidate is None:
                return (), (
                    _finding(
                        "APPROVAL_MISMATCH", f"approved source is not in the current plan: {item}"
                    ),
                )
        else:
            return (), (
                _finding("MALFORMED_APPROVAL", "approved entries must be plan entries or sources"),
            )
        if candidate in selected:
            return (), (
                _finding("DUPLICATE_APPROVAL", f"approved entry repeated: {candidate.source}"),
            )
        selected.append(candidate)
    return tuple(selected), ()


def _validate_index_target(root: Path, index_path: Path) -> tuple[Finding, ...]:
    if _has_symlink_component(root, index_path):
        return (_finding("SYMLINK_INDEX", "index path contains a symlink component"),)
    if index_path.is_symlink():
        return (_finding("SYMLINK_INDEX", "index target is a symlink"),)
    if not index_path.exists():
        return ()
    try:
        text = index_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return (_finding("UNREADABLE_INDEX", f"index cannot be read: {exc}"),)
    if not text.startswith(INDEX_MARKER):
        return (_finding("HUMAN_INDEX", "refusing to overwrite a human-maintained index"),)
    return ()


def render_index(plan: ArchivePlan | Iterable[PlanEntry]) -> str:
    """Render a deterministic generated navigation view without writing it."""

    entries = plan.entries if isinstance(plan, ArchivePlan) else tuple(plan)
    lines = [
        INDEX_MARKER,
        "# Local task archive index",
        "",
        "Generated navigation view; the append-only mapping ledger is authoritative.",
        "",
    ]
    for entry in sorted(entries, key=lambda item: (item.destination, item.source)):
        finding_suffix = ""
        if entry.findings:
            finding_suffix = " (" + ", ".join(f.code for f in entry.findings) + ")"
        lines.append(
            f"- `{entry.destination}` ← `{entry.source}` — "
            f"{entry.classification}; {entry.action}{finding_suffix}"
        )
    return "\n".join(lines) + "\n"


def _write_generated_index(root: Path, index_path: Path, content: str) -> tuple[Finding, ...]:
    findings = _validate_index_target(root, index_path)
    if findings:
        return findings
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{index_path.name}.", dir=index_path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, index_path)
    except OSError as exc:
        logger.warning("local archive index persistence failed: %s", exc)
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)
        return (_finding("INDEX_WRITE_ERROR", f"could not persist generated index: {exc}"),)
    return ()


def _load_mapping_records(path: Path) -> tuple[MappingRecord, ...]:
    if not path.exists():
        return ()
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ArchiveError(f"mapping ledger is unreadable or malformed: {path}: {exc}") from exc
    rows: list[MappingRecord] = []
    for document in documents:
        if document is None:
            continue
        if not isinstance(document, dict):
            raise ArchiveError(f"mapping ledger row is not a mapping: {path}")
        required = ("sequence", "source", "destination", "reason", "timestamp")
        if any(key not in document for key in required):
            raise ArchiveError(f"mapping ledger row is missing required fields: {path}")
        sequence = document["sequence"]
        source = document["source"]
        destination = document["destination"]
        if type(sequence) is not int or sequence < 1:
            raise ArchiveError(f"mapping ledger sequence is not a positive integer: {path}")
        if not _is_public_relative_path(source) or not _is_public_relative_path(destination):
            raise ArchiveError(f"mapping ledger contains an unsafe path: {path}")
        try:
            rows.append(
                MappingRecord(
                    sequence=sequence,
                    source=source,
                    destination=destination,
                    reason=str(document["reason"]),
                    timestamp=str(document["timestamp"]),
                )
            )
        except (TypeError, ValueError) as exc:
            raise ArchiveError(f"mapping ledger row has invalid fields: {path}") from exc
    if len({row.sequence for row in rows}) != len(rows):
        raise ArchiveError(f"mapping ledger contains duplicate sequence values: {path}")
    if len({row.source for row in rows}) != len(rows) or len(
        {row.destination for row in rows}
    ) != len(rows):
        raise ArchiveError(f"mapping ledger contains duplicate paths: {path}")
    return tuple(rows)


def _is_public_relative_path(value: object) -> bool:
    """Validate a persisted path without needing a repository root."""

    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def append_mapping_record(
    repo_root: str | Path,
    source: str,
    destination: str,
    reason: str,
    *,
    timestamp: str | None = None,
    mapping_path: str | Path = MAPPING_PATH,
) -> MappingRecord:
    """Append one no-overwrite mapping row and return the assigned sequence."""

    root = Path(repo_root)
    target_rel, target_error = _relative_path(root, mapping_path)
    if target_error:
        raise ArchiveError(target_error.message)
    assert target_rel is not None
    target = root / target_rel
    if _has_symlink_component(root, target):
        raise ArchiveError("mapping path contains a symlink component")
    source_rel, source_error = _relative_path(root, source)
    destination_rel, destination_error = _relative_path(root, destination)
    if source_error or destination_error:
        raise ArchiveError((source_error or destination_error).message)
    assert source_rel is not None and destination_rel is not None
    normalized_source = source_rel.as_posix()
    normalized_destination = destination_rel.as_posix()
    existing = _load_mapping_records(target)
    if any(
        row.source == normalized_source or row.destination == normalized_destination
        for row in existing
    ):
        raise ArchiveError("mapping source or destination already exists; refusing duplicate row")
    record = MappingRecord(
        sequence=max((row.sequence for row in existing), default=0) + 1,
        source=normalized_source,
        destination=normalized_destination,
        reason=reason,
        timestamp=timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(
        {
            "sequence": record.sequence,
            "source": record.source,
            "destination": record.destination,
            "reason": record.reason,
            "timestamp": record.timestamp,
        },
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).encode("utf-8")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "ab") as stream:
            if existing:
                stream.write(b"---\n")
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        logger.warning("local archive mapping persistence failed: %s", exc)
        raise ArchiveError(f"could not append mapping record: {target}") from exc
    return record


def apply_archive_plan(
    repo_root: str | Path,
    plan: ArchivePlan,
    approved: ArchivePlan | Sequence[PlanEntry] | Sequence[str] | None = None,
    *,
    mapping_path: str | Path = MAPPING_PATH,
    index_path: str | Path = INDEX_PATH,
) -> ArchiveResult:
    """Apply only an explicit approved subset of a still-current plan.

    There is intentionally no deletion action.  Refusals are returned as
    structured findings, while malformed persistence/API input is raised as
    :class:`ArchiveError` so callers cannot mistake it for success.
    """

    if not isinstance(plan, ArchivePlan):
        raise ArchiveError("apply requires an ArchivePlan produced by build_archive_plan")
    if approved is None:
        return ArchiveResult(
            findings=(_finding("APPROVAL_REQUIRED", "explicit plan approval is required"),),
            refused=True,
        )
    selected, approval_findings = _entry_from_approval(plan, approved)
    if approval_findings:
        return ArchiveResult(findings=approval_findings, refused=True)
    assert isinstance(selected, tuple)
    if not selected:
        return ArchiveResult(
            findings=(_finding("EMPTY_APPROVAL", "approved subset is empty"),), refused=True
        )
    root = Path(repo_root)
    current = build_archive_plan(root)
    current_by_source = {entry.source: entry for entry in current.entries}
    findings: list[Finding] = list(plan.findings)
    for entry in selected:
        current_entry = current_by_source.get(entry.source)
        if current_entry is None or current_entry.key != entry.key:
            findings.append(
                _finding(
                    "PLAN_CHANGED", f"source/destination no longer matches plan: {entry.source}"
                )
            )
        elif current_entry != entry:
            findings.append(
                _finding("PLAN_CHANGED", f"classification or findings changed: {entry.source}")
            )
        if entry.action != "move":
            findings.append(_finding("NOT_MOVABLE", f"entry action is not move: {entry.source}"))
    if findings:
        return ArchiveResult(findings=tuple(findings), refused=True)
    index_rel, index_error = _relative_path(root, index_path)
    mapping_rel, mapping_error = _relative_path(root, mapping_path)
    if index_error or mapping_error:
        return ArchiveResult(
            findings=tuple(error for error in (index_error, mapping_error) if error is not None),
            refused=True,
        )
    assert index_rel is not None and mapping_rel is not None
    index_findings = _validate_index_target(root, root / index_rel)
    if index_findings:
        return ArchiveResult(findings=index_findings, refused=True)
    mapping_target = root / mapping_rel
    try:
        prior_mappings = _load_mapping_records(mapping_target)
    except ArchiveError as exc:
        return ArchiveResult(findings=(_finding("MALFORMED_MAPPING", str(exc)),), refused=True)
    for entry in selected:
        if any(
            row.source == entry.source or row.destination == entry.destination
            for row in prior_mappings
        ):
            findings.append(
                _finding("MAPPING_DUPLICATE", f"mapping already records {entry.source}")
            )
    if findings:
        return ArchiveResult(findings=tuple(findings), refused=True)
    inspections = [inspect_safety(root, entry.source, entry.destination) for entry in selected]
    for inspection in inspections:
        findings.extend(inspection.findings)
    if findings:
        return ArchiveResult(findings=tuple(findings), refused=True)

    applied: list[PlanEntry] = []
    mappings: list[MappingRecord] = []
    for entry in selected:
        source_path = root / entry.source
        destination_path = root / entry.destination
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_path), str(destination_path))
            mapping = append_mapping_record(
                root,
                entry.source,
                entry.destination,
                f"{entry.classification} task archive",
                mapping_path=mapping_rel,
            )
        except (OSError, ArchiveError) as exc:
            logger.warning("local archive apply refused after partial progress: %s", exc)
            findings.append(_finding("APPLY_ERROR", str(exc)))
            return ArchiveResult(
                applied=tuple(applied),
                mappings=tuple(mappings),
                findings=tuple(findings),
                refused=True,
            )
        applied.append(entry)
        mappings.append(mapping)
    index_findings = _write_generated_index(
        root,
        root / index_rel,
        render_index(plan),
    )
    if index_findings:
        return ArchiveResult(
            applied=tuple(applied),
            mappings=tuple(mappings),
            findings=index_findings,
            refused=True,
        )
    return ArchiveResult(
        applied=tuple(applied),
        mappings=tuple(mappings),
        index_path=index_rel.as_posix(),
    )


__all__ = [
    "ArchiveError",
    "ArchivePlan",
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
    "inspect_safety",
    "inventory_tasks",
    "render_index",
]
