"""Surface-neutral kernel for the explicit local archive runtime.

Task, feedback, and research adapters provide discovery and classification.
This module owns the shared path validation, safety evidence, append-only
ledger, generated-index, approval, and physical-move machinery.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml

from devolaflow._durability import _same_device
from devolaflow._durability import fsync_directory as _fsync_directory
from devolaflow.local.archive_models import (
    ArchiveApproval,
    ArchiveError,
    ArchivePlan,
    ArchiveResult,
    Finding,
    MappingRecord,
    PlanEntry,
    SafetyInspection,
)

logger = logging.getLogger(__name__)
INDEX_MARKER = "<!-- devolaflow: generated task archive index -->"
_INDEX_LINE_RE = re.compile(r"- `([^`]+)` ← `([^`]+)`")


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
            logger.warning(
                "could not normalize git inspection error path",
                exc_info=True,
            )
        return None, _finding("GIT_INSPECTION_ERROR", f"git {' '.join(args)}: {message}")
    return completed.stdout, None


def _review_note_overlaps_scope(
    status_output: str,
    scope_paths: Sequence[str],
    *,
    marker: str | None = None,
) -> bool:
    """Return True when a review/note status path overlaps the operation scope.

    ``git status --short`` lines carry a two-character code, a space, then a
    repository-relative path. Only paths inside (or containing) the current
    operation's source/destination subtrees can be endangered by the move;
    review/note paths elsewhere in the repository must not block unrelated
    operations, otherwise conventional artifact names (``*-review`` change
    folders, ``v*_review_*`` research files) deadlock every apply. The
    approved subject is exempt: the operator saw the full source/destination
    path at approval time, so review/note is matched only against the path
    remainder beneath a scope — content the approval did not spell out.
    """

    for line in status_output.splitlines():
        if marker is not None and not line.startswith(marker):
            continue
        path = line[3:].strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        candidate = path.rstrip("/")
        for scope in scope_paths:
            if not candidate.startswith(scope + "/"):
                continue
            remainder = candidate[len(scope) + 1 :].lower()
            if "review" in remainder or "note" in remainder:
                return True
    return False


def inspect_safety(
    repo_root: str | Path,
    source: str | Path,
    destination: str | Path | None = None,
    *,
    source_boundary: str | Path = ".local/tasks",
    destination_boundary: str | Path | None = None,
    requires_directory: bool = True,
    run_git: Callable[[Path, Sequence[str]], tuple[str | None, Finding | None]] = _run_git,
    same_device: Callable[[Path, Path], bool] = _same_device,
) -> SafetyInspection:
    """Run strict boundary, symlink, git, and worktree checks for one surface."""

    root = Path(repo_root)
    findings: list[Finding] = []
    source_rel, source_error = _relative_path(root, source)
    if source_error:
        findings.append(source_error)
        return SafetyInspection(False, tuple(findings))
    assert source_rel is not None
    source_path = root / source_rel
    scope_paths: list[str] = [source_rel.as_posix()]
    destination_path: Path | None = None
    if destination is not None:
        destination_rel, destination_error = _relative_path(root, destination)
        if destination_error:
            findings.append(destination_error)
        else:
            assert destination_rel is not None
            destination_path = root / destination_rel
            scope_paths.append(destination_rel.as_posix())
    source_root = root / source_boundary
    destination_root = root / (destination_boundary or source_boundary)
    for label, path in (("source", source_path), ("destination", destination_path)):
        if path is None:
            continue
        try:
            path.resolve(strict=False).relative_to(
                (source_root if label == "source" else destination_root).resolve()
            )
        except (OSError, ValueError):
            boundary = source_boundary if label == "source" else destination_boundary
            findings.append(_finding("PROTECTED_PATH", f"{label} is outside {boundary}"))
        if _has_symlink_component(root, path):
            findings.append(_finding("SYMLINK_PATH", f"{label} contains a symlink component"))
    if not source_path.exists() or (requires_directory and not source_path.is_dir()):
        findings.append(_finding("MISSING_SOURCE", f"source is not a directory: {source}"))
    elif not requires_directory and not source_path.is_file():
        findings.append(_finding("MISSING_SOURCE", f"source is not a regular file: {source}"))
    if (
        destination_path is not None
        and destination_path.exists()
        and destination_path != source_path
    ):
        findings.append(
            _finding("DESTINATION_EXISTS", f"destination already exists: {destination}")
        )
    if (
        source_path.is_dir()
        and destination_path is not None
        and not destination_path.exists()
        and not same_device(source_path, destination_path)
    ):
        findings.append(
            _finding(
                "CROSS_DEVICE",
                "source and destination are on different devices; atomic rename is unavailable",
            )
        )

    git_root, git_root_error = run_git(root, ["rev-parse", "--show-toplevel"])
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
    git_status, status_error = run_git(root, ["status", "--short", "--untracked-files=all"])
    if status_error:
        findings.append(status_error)
    elif git_status:
        findings.append(
            _finding("DIRTY_TREE", "git status contains staged, unstaged, or untracked paths")
        )
        if _review_note_overlaps_scope(git_status, scope_paths):
            findings.append(
                _finding("UNTRACKED_REVIEW_NOTE", "git status contains a review/note path")
            )
    staged_diff, staged_error = run_git(root, ["diff", "--cached", "--"])
    if staged_error:
        findings.append(staged_error)
    elif staged_diff:
        findings.append(_finding("STAGED_DIFF", "staged diff is non-empty"))
    unstaged_diff, unstaged_error = run_git(root, ["diff", "--"])
    if unstaged_error:
        findings.append(unstaged_error)
    elif unstaged_diff:
        findings.append(_finding("UNSTAGED_DIFF", "unstaged diff is non-empty"))
    ignored_status, ignored_error = run_git(
        root, ["status", "--ignored", "--short", "--untracked-files=all"]
    )
    if ignored_error:
        findings.append(ignored_error)
    elif ignored_status and _review_note_overlaps_scope(ignored_status, scope_paths, marker="!!"):
        findings.append(
            _finding("UNTRACKED_REVIEW_NOTE", "ignored review/note path requires review")
        )
    worktrees, worktree_error = run_git(root, ["worktree", "list", "--porcelain"])
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
                        # Expected containment probe: this worktree does not
                        # contain the source; continue checking other entries.
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
    plan: ArchivePlan,
    approved: ArchiveApproval | ArchivePlan | Sequence[PlanEntry] | Sequence[str],
) -> tuple[PlanEntry, ...] | tuple[Finding, ...]:
    if isinstance(approved, ArchiveApproval):
        if approved.plan_fingerprint != plan.fingerprint:
            return (), (
                _finding(
                    "APPROVAL_MISMATCH",
                    "approved artifact does not match the current plan fingerprint",
                ),
            )
        approved_items: Sequence[PlanEntry | str | tuple[str, str]] = approved.entries
    else:
        approved_items = approved.entries if isinstance(approved, ArchivePlan) else approved
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
        elif (
            isinstance(item, tuple)
            and len(item) == 2
            and all(isinstance(value, str) for value in item)
        ):
            candidate = by_key.get(item)
            if candidate is None:
                return (), (
                    _finding(
                        "APPROVAL_MISMATCH",
                        f"approved entry is not in the current plan: {item[0]}",
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


def _validate_index_target(
    root: Path,
    index_path: Path,
    *,
    expected_mappings: Sequence[MappingRecord] = (),
    index_marker: str = INDEX_MARKER,
) -> tuple[Finding, ...]:
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
    if not text.startswith(index_marker):
        return (_finding("HUMAN_INDEX", "refusing to overwrite a human-maintained index"),)
    actual_pairs = set(_INDEX_LINE_RE.findall(text))
    expected_pairs = {(row.destination, row.source) for row in expected_mappings}
    if actual_pairs != expected_pairs:
        return (
            _finding(
                "INDEX_DRIFT",
                "generated index does not match authoritative mapping records",
            ),
        )
    return ()


def render_index(
    plan: ArchivePlan | Iterable[PlanEntry] | Iterable[MappingRecord],
    *,
    index_marker: str = INDEX_MARKER,
    title: str = "Local task archive index",
) -> str:
    """Render a deterministic generated navigation view without writing it."""

    entries = plan.entries if isinstance(plan, ArchivePlan) else tuple(plan)
    lines = [
        index_marker,
        f"# {title}",
        "",
        "Generated navigation view; the append-only mapping ledger is authoritative.",
        "",
    ]
    for entry in sorted(entries, key=lambda item: (item.destination, item.source)):
        if isinstance(entry, MappingRecord):
            lines.append(f"- `{entry.destination}` ← `{entry.source}` — {entry.reason}")
            continue
        finding_suffix = ""
        if entry.findings:
            finding_suffix = " (" + ", ".join(f.code for f in entry.findings) + ")"
        lines.append(
            f"- `{entry.destination}` ← `{entry.source}` — "
            f"{entry.classification}; {entry.action}{finding_suffix}"
        )
    return "\n".join(lines) + "\n"


def _write_generated_index(
    root: Path,
    index_path: Path,
    content: str,
    *,
    expected_mappings: Sequence[MappingRecord] = (),
    index_marker: str = INDEX_MARKER,
) -> tuple[Finding, ...]:
    findings = _validate_index_target(
        root,
        index_path,
        expected_mappings=expected_mappings,
        index_marker=index_marker,
    )
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
        _fsync_directory(index_path.parent)
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
    mapping_path: str | Path = ".local/tasks/archive-mappings.yaml",
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
        _fsync_directory(target.parent)
    except OSError as exc:
        logger.warning("local archive mapping persistence failed: %s", exc)
        raise ArchiveError(f"could not append mapping record: {target}") from exc
    return record


def apply_archive_plan(
    repo_root: str | Path,
    plan: ArchivePlan,
    approved: ArchiveApproval | ArchivePlan | Sequence[PlanEntry] | Sequence[str] | None = None,
    *,
    mapping_path: str | Path = ".local/tasks/archive-mappings.yaml",
    index_path: str | Path = ".local/tasks/INDEX.md",
    build_plan: Callable[[Path], ArchivePlan],
    append_mapping: Callable[..., MappingRecord] = append_mapping_record,
    run_git: Callable[[Path, Sequence[str]], tuple[str | None, Finding | None]] = _run_git,
    same_device: Callable[[Path, Path], bool] = _same_device,
) -> ArchiveResult:
    """Apply only an explicit approved subset of a still-current plan."""

    if not isinstance(plan, ArchivePlan):
        raise ArchiveError("apply requires an ArchivePlan produced by build_archive_plan")
    surface = getattr(plan, "surface", "tasks")
    try:
        from devolaflow.local.archive_adapters import get_archive_adapter

        adapter = get_archive_adapter(surface)
    except ValueError as exc:
        raise ArchiveError(str(exc)) from exc
    if Path(mapping_path).as_posix() == ".local/tasks/archive-mappings.yaml" and surface != "tasks":
        mapping_path = adapter.mapping_path
    if Path(index_path).as_posix() == ".local/tasks/INDEX.md" and surface != "tasks":
        index_path = adapter.index_path
    if approved is None:
        return ArchiveResult(
            findings=(_finding("APPROVAL_REQUIRED", "explicit plan approval is required"),),
            refused=True,
            surface=surface,
        )
    selected, approval_findings = _entry_from_approval(plan, approved)
    if approval_findings:
        return ArchiveResult(findings=approval_findings, refused=True, surface=surface)
    assert isinstance(selected, tuple)
    if not selected:
        return ArchiveResult(
            findings=(_finding("EMPTY_APPROVAL", "approved subset is empty"),),
            refused=True,
            surface=surface,
        )
    root = Path(repo_root)
    current = build_plan(root) if surface == "tasks" else _build_surface_plan(root, surface)
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
        return ArchiveResult(findings=tuple(findings), refused=True, surface=surface)
    index_rel, index_error = _relative_path(root, index_path)
    mapping_rel, mapping_error = _relative_path(root, mapping_path)
    if index_error or mapping_error:
        return ArchiveResult(
            findings=tuple(error for error in (index_error, mapping_error) if error is not None),
            refused=True,
            surface=surface,
        )
    assert index_rel is not None and mapping_rel is not None
    mapping_target = root / mapping_rel
    try:
        prior_mappings = _load_mapping_records(mapping_target)
    except ArchiveError as exc:
        return ArchiveResult(
            findings=(_finding("MALFORMED_MAPPING", str(exc)),),
            refused=True,
            surface=surface,
        )
    index_findings = _validate_index_target(
        root,
        root / index_rel,
        expected_mappings=prior_mappings,
        index_marker=adapter.index_marker,
    )
    if index_findings:
        return ArchiveResult(findings=index_findings, refused=True, surface=surface)
    for entry in selected:
        if any(
            row.source == entry.source or row.destination == entry.destination
            for row in prior_mappings
        ):
            findings.append(
                _finding("MAPPING_DUPLICATE", f"mapping already records {entry.source}")
            )
    if findings:
        return ArchiveResult(findings=tuple(findings), refused=True, surface=surface)
    inspections = [
        inspect_safety(
            root,
            entry.source,
            entry.destination,
            source_boundary=adapter.source_root,
            destination_boundary=adapter.archive_root,
            requires_directory=adapter.requires_directory,
            run_git=run_git,
            same_device=same_device,
        )
        for entry in selected
    ]
    for inspection in inspections:
        findings.extend(inspection.findings)
    if findings:
        return ArchiveResult(findings=tuple(findings), refused=True, surface=surface)

    applied: list[PlanEntry] = []
    mappings: list[MappingRecord] = []
    moved_without_mapping: PlanEntry | None = None
    for entry in selected:
        source_path = root / entry.source
        destination_path = root / entry.destination
        try:
            if not same_device(source_path, destination_path):
                raise OSError(
                    "source and destination are on different devices; atomic rename is unavailable"
                )
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if not same_device(source_path, destination_path):
                raise OSError(
                    "source and destination changed devices; atomic rename is unavailable"
                )
            os.replace(source_path, destination_path)
            _fsync_directory(source_path.parent)
            _fsync_directory(destination_path.parent)
            moved_without_mapping = entry
            mapping = append_mapping(
                root,
                entry.source,
                entry.destination,
                (
                    f"{entry.classification} task archive"
                    if surface == "tasks"
                    else f"{entry.classification} {surface} archive"
                ),
                mapping_path=mapping_rel,
            )
        except (OSError, ArchiveError) as exc:
            partial = bool(applied or mappings or moved_without_mapping)
            logger.warning("local archive apply refused after partial progress: %s", exc)
            findings.append(_finding("APPLY_ERROR", str(exc)))
            if partial:
                findings.append(
                    _finding(
                        "PARTIAL_APPLY",
                        "some approved entries were moved or mapped; inspect the returned "
                        "mappings and reconcile before retrying",
                    )
                )
            return ArchiveResult(
                applied=tuple(applied),
                mappings=tuple(mappings),
                findings=tuple(findings),
                refused=True,
                recovery_required=partial,
                recovery_hint=(
                    "Do not retry blindly: verify each mapping source is absent and "
                    "destination exists before approving a new subset."
                    if partial
                    else None
                ),
                surface=surface,
            )
        moved_without_mapping = None
        applied.append(entry)
        mappings.append(mapping)
    index_findings = _write_generated_index(
        root,
        root / index_rel,
        render_index(
            (*prior_mappings, *mappings),
            index_marker=adapter.index_marker,
            title=f"Local {surface} archive index",
        ),
        expected_mappings=prior_mappings,
        index_marker=adapter.index_marker,
    )
    if index_findings:
        return ArchiveResult(
            applied=tuple(applied),
            mappings=tuple(mappings),
            findings=index_findings,
            refused=True,
            recovery_required=True,
            recovery_hint=(
                "Moves and mappings are durable; repair the generated index from "
                "the mapping ledger before retrying."
            ),
            surface=surface,
        )
    return ArchiveResult(
        applied=tuple(applied),
        mappings=tuple(mappings),
        index_path=index_rel.as_posix(),
        surface=surface,
    )


def _build_surface_plan(root: Path, surface: str) -> ArchivePlan:
    from devolaflow.local.archive_adapters import build_surface_archive_plan

    return build_surface_archive_plan(root, surface)


__all__ = [
    "INDEX_MARKER",
    "_entry_from_approval",
    "_finding",
    "_has_symlink_component",
    "_is_public_relative_path",
    "_load_mapping_records",
    "_relative_path",
    "_relative_posix",
    "_run_git",
    "_validate_index_target",
    "_write_generated_index",
    "append_mapping_record",
    "apply_archive_plan",
    "inspect_safety",
    "render_index",
]
