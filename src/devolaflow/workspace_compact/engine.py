"""Plan, apply, locate, and restore for workspace compaction (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §2, §6.

The engine's whole contract is that `plan` never touches the filesystem's
contents and `apply` never runs without an approval fingerprint matching the
plan the operator actually read. During unattended runs an agent may plan
freely and must queue the result; there is deliberately no standing
authorization, because the guarantee "nothing moved that you had not seen" is
worth more than the convenience of skipping one round trip.
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Sequence
from pathlib import Path

from devolaflow._durability import fsync_directory as _fsync_directory
from devolaflow.parking.models import RiskState
from devolaflow.parking.store import PARKING_DIRNAME, ParkingStore
from devolaflow.workspace_compact.metering import (
    largest_resident_tokens,
    measure_file,
    resident_tokens,
)
from devolaflow.workspace_compact.models import (
    ARCHIVED_DIRNAME,
    COMPACT_DIRNAME,
    DIGEST_FILENAME,
    HISTORICAL_DIRS,
    MAPPINGS_FILENAME,
    PROTECTED_NAMES,
    Action,
    Category,
    CompactEntry,
    CompactError,
    CompactPlan,
    CompactResult,
    LocateHit,
)
from devolaflow.workspace_compact.telemetry import OUTCOME_APPLIED, append_event, build_event
from devolaflow.workspace_ledger import (
    LedgerError,
    append_ledger_row,
    has_symlink_component,
    load_ledger_rows,
    sha256_path,
    utc_now,
)

logger = logging.getLogger(__name__)


def compact_root(folder: Path) -> Path:
    """Return the compaction surface directory for one folder."""

    return folder / COMPACT_DIRNAME


def mappings_path(folder: Path) -> Path:
    """Return the append-only before/after mapping ledger path."""

    return compact_root(folder) / MAPPINGS_FILENAME


def archived_root(folder: Path) -> Path:
    """Return the directory that receives relocated originals."""

    return compact_root(folder) / ARCHIVED_DIRNAME


def digest_path(folder: Path) -> Path:
    """Return the generated digest path."""

    return compact_root(folder) / DIGEST_FILENAME


def load_mappings(folder: Path) -> tuple[dict[str, object], ...]:
    """Load every mapping row in sequence order."""

    return tuple(
        sorted(
            load_ledger_rows(
                mappings_path(folder),
                required_fields=("sequence", "source", "destination", "reason", "timestamp"),
            ),
            key=lambda row: int(row["sequence"]),
        )
    )


def pending_moves(folder: str | Path) -> dict[str, dict[str, object]]:
    """Return mapping rows describing a move that was journalled but not made.

    A row qualifies only when all three hold: the destination is absent, the
    source is still in place, and the source still hashes to the value the row
    recorded. That combination can only be produced by an interrupted apply,
    and it is recoverable precisely because the original is untouched. Any
    other missing destination is a real loss, not a pending move, and is left
    to report itself as one.
    """

    root = Path(folder)
    pending: dict[str, dict[str, object]] = {}
    for row in load_mappings(root):
        destination = root / str(row["destination"])
        if destination.exists():
            continue
        source = root / str(row["source"])
        if not source.is_file():
            continue
        recorded = str(row.get("sha256", ""))
        if recorded and sha256_path(source) == recorded:
            pending[str(row["source"])] = row
    return pending


def _is_within(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
    except ValueError:
        return False
    return True


def _closed_risk_ids(folder: Path) -> dict[str, str]:
    store = ParkingStore(folder)
    if not store.exists:
        return {}
    try:
        risks = store.list_risks()
    except Exception as exc:  # noqa: BLE001 - a malformed risk must not crash planning
        logger.warning("compact planning could not read the parking surface: %s", exc)
        return {}
    return {
        store.risk_path(risk.id).as_posix(): risk.id
        for risk in risks
        if risk.state is RiskState.CLOSED
    }


def _classify(
    folder: Path,
    path: Path,
    *,
    closed_risks: dict[str, str],
    operator_named: set[Path],
) -> tuple[Category, Action, str, str | None]:
    relative = path.relative_to(folder)
    if _is_within(path, compact_root(folder)):
        return Category.PROTECTED, Action.RETAIN, "already inside the compaction surface", None
    if path in operator_named:
        return Category.OPERATOR_NAMED, Action.MOVE, "explicitly named by the operator", None
    risk_id = closed_risks.get(path.as_posix())
    if risk_id is not None:
        return Category.CLOSED_RISK, Action.MOVE, f"risk {risk_id} is closed", risk_id
    if path.name in PROTECTED_NAMES:
        return Category.PROTECTED, Action.RETAIN, "canonical or never-compacted artifact", None
    if _is_within(path, folder / PARKING_DIRNAME / "risks"):
        return Category.LIVE, Action.RETAIN, "risk is still live", None
    if any(part in HISTORICAL_DIRS for part in relative.parts[:-1]):
        return Category.HISTORICAL_OUTPUT, Action.MOVE, "accumulated historical output", None
    return (
        Category.LIVE,
        Action.RETAIN,
        "not eligible without an explicit operator instruction",
        None,
    )


def build_plan(
    folder: str | Path,
    *,
    include: Sequence[str | Path] = (),
) -> CompactPlan:
    """Classify a folder's contents; read-only, writes nothing.

    ``include`` names paths the operator explicitly wants relocated even
    though automatic classification would retain them — the channel for
    hand-written artifacts such as a superseded design document.
    """

    root = Path(folder)
    if not root.is_dir():
        raise CompactError(f"compaction target is not a directory: {folder}")
    operator_named: set[Path] = set()
    findings: list[str] = []
    for item in include:
        candidate = Path(item)
        resolved = candidate if candidate.is_absolute() else root / candidate
        if not resolved.exists():
            findings.append(f"MISSING_INCLUDE: {item}")
            continue
        if not _is_within(resolved.resolve(), root.resolve()):
            findings.append(f"OUTSIDE_FOLDER: {item}")
            continue
        operator_named.add(resolved)

    closed_risks = _closed_risk_ids(root)
    pending = pending_moves(root)
    next_sequence = len(load_mappings(root)) + 1
    entries: list[CompactEntry] = []
    retained_tokens = 0
    movable_tokens = 0

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if has_symlink_component(root, path) or path.is_symlink():
            findings.append(f"SYMLINK_SKIPPED: {path.relative_to(root).as_posix()}")
            continue
        category, action, reason, subject = _classify(
            root, path, closed_risks=closed_risks, operator_named=operator_named
        )
        measurement = measure_file(path)
        relative = path.relative_to(root)
        pending_row = pending.get(relative.as_posix())
        is_pending = pending_row is not None
        if is_pending:
            # The ledger already committed to relocating this file, and its row
            # cannot be revised, so the journal overrides classification: the
            # destination and the decision to move both come from the row.
            assert pending_row is not None
            action = Action.MOVE
            destination = Path(str(pending_row["destination"]))
            reason = f"completing the move journalled at sequence {pending_row['sequence']}"
            movable_tokens += measurement.tokens
            findings.append(f"PENDING_MOVE: {relative.as_posix()}")
        elif action is Action.MOVE:
            destination = (
                Path(COMPACT_DIRNAME) / ARCHIVED_DIRNAME / f"{next_sequence:04d}" / relative
            )
            next_sequence += 1
            movable_tokens += measurement.tokens
        else:
            destination = relative
            retained_tokens += measurement.tokens
        entries.append(
            CompactEntry(
                source=relative.as_posix(),
                destination=destination.as_posix(),
                category=category,
                action=action,
                reason=reason,
                bytes=measurement.bytes,
                tokens_estimated=measurement.tokens,
                sha256=sha256_path(path),
                subject=subject,
                pending=is_pending,
                # Retained `live` entries are summarised too: they are the
                # `--include` candidate list, and a path alone does not tell
                # an operator whether the file is still worth keeping resident.
                summary=(
                    _summarize(path) if action is Action.MOVE or category is Category.LIVE else ""
                ),
            )
        )

    return CompactPlan(
        folder=root.as_posix(),
        entries=tuple(entries),
        retained_tokens=retained_tokens,
        movable_tokens=movable_tokens,
        findings=tuple(findings),
    )


def apply_plan(
    folder: str | Path,
    plan: CompactPlan,
    *,
    approval_fingerprint: str,
    sources: Sequence[str] | None = None,
    telemetry_ledger: str | Path | None = None,
) -> CompactResult:
    """Relocate an approved subset, appending one mapping row per move.

    Refuses outright when the plan no longer matches the folder: a source
    whose hash changed since the plan was read is a different file, and
    approving one file is not approving another.
    """

    root = Path(folder)
    if approval_fingerprint != plan.fingerprint:
        return CompactResult(
            findings=("APPROVAL_MISMATCH: approval does not match the current plan",),
            refused=True,
        )
    # Re-derive from the folder with the same operator-named set the plan was
    # built from, otherwise an explicitly included path re-classifies as
    # retained and the approval appears to cover something it does not.
    named = [entry.source for entry in plan.entries if entry.category is Category.OPERATOR_NAMED]
    current = build_plan(root, include=named)
    current_by_source = {entry.source: entry for entry in current.entries}
    selected = [entry for entry in plan.movable if sources is None or entry.source in set(sources)]
    if not selected:
        return CompactResult(findings=("EMPTY_APPROVAL: no entries were approved",), refused=True)

    findings: list[str] = []
    for entry in selected:
        live = current_by_source.get(entry.source)
        if live is None:
            findings.append(f"PLAN_CHANGED: source is gone: {entry.source}")
        elif live.sha256 != entry.sha256:
            findings.append(f"CONTENT_CHANGED: {entry.source}")
        elif live.action is not Action.MOVE:
            findings.append(f"NOT_MOVABLE: {entry.source}")
    if findings:
        return CompactResult(findings=tuple(findings), refused=True)

    prior = load_mappings(root)
    known = {str(row["source"]) for row in prior}
    for entry in selected:
        # A pending entry is *expected* to have a row: that row is what makes
        # it pending. Only an unjournalled source colliding with an existing
        # row is a duplicate.
        if entry.source in known and not entry.pending:
            findings.append(f"MAPPING_DUPLICATE: {entry.source}")
    if findings:
        return CompactResult(findings=tuple(findings), refused=True)

    tokens_before = resident_tokens(root, exclude=(archived_root(root),))
    applied: list[CompactEntry] = []
    for entry in selected:
        source_path = root / entry.source
        destination_path = root / entry.destination
        try:
            # The ledger row goes first, so the worst outcome of a failure is a
            # recorded move that has not happened yet — visible to `verify` and
            # completable by a re-run — instead of a moved file no row mentions.
            # A pending entry already has its row and must not append a second.
            if not entry.pending:
                append_ledger_row(
                    mappings_path(root),
                    {
                        "source": entry.source,
                        "destination": entry.destination,
                        "reason": f"{entry.category.value}: {entry.reason}",
                        "timestamp": utc_now(),
                        "sha256": entry.sha256,
                        "bytes": entry.bytes,
                        "tokens_estimated": entry.tokens_estimated,
                        "summary": entry.summary,
                    },
                    required_fields=("source", "destination", "reason", "timestamp", "sha256"),
                    unique_fields=("source", "destination"),
                )
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(os.fspath(source_path), os.fspath(destination_path))
            _fsync_directory(source_path.parent)
            _fsync_directory(destination_path.parent)
            if sha256_path(destination_path) != entry.sha256:
                findings.append(f"HASH_MISMATCH_AFTER_MOVE: {entry.source}")
        except (OSError, LedgerError) as exc:
            logger.warning("compact apply refused after partial progress: %s", exc)
            findings.append(f"APPLY_ERROR: {entry.source}: {exc}")
            return CompactResult(
                applied=tuple(applied),
                findings=tuple(findings),
                refused=True,
                tokens_before=tokens_before,
                tokens_after=resident_tokens(root, exclude=(archived_root(root),)),
            )
        applied.append(entry)
        if entry.category is Category.CLOSED_RISK and entry.subject:
            _record_risk_archived(root, entry.subject, entry.destination)

    from devolaflow.workspace_compact.digest import write_digest

    working_set_before = largest_resident_tokens(root, exclude=(archived_root(root),))
    digest_findings = write_digest(root)
    result = CompactResult(
        applied=tuple(applied),
        findings=tuple(findings),
        refused=bool(findings),
        digest_path=digest_path(root).relative_to(root).as_posix(),
        tokens_before=tokens_before,
        tokens_after=resident_tokens(root, exclude=(archived_root(root),)),
        digest_findings=tuple(digest_findings),
    )
    _record_telemetry(root, result, telemetry_ledger, working_set_before=working_set_before)
    return result


def _record_telemetry(
    root: Path,
    result: CompactResult,
    ledger: str | Path | None,
    *,
    working_set_before: int,
) -> None:
    """Record one applied-compaction event; never let telemetry fail the move."""

    if ledger is None:
        return
    excluded = (archived_root(root),)
    digest_tokens = measure_file(digest_path(root)).tokens
    append_event(
        ledger,
        build_event(
            root.as_posix(),
            OUTCOME_APPLIED,
            tokens_before=result.tokens_before,
            tokens_after=result.tokens_after,
            entries=len(result.applied),
            reason="; ".join(result.findings),
            digest_tokens=digest_tokens,
            working_set_before=working_set_before,
            # The digest is part of the reading path now, so it is charged to
            # the after-figure even though it is not the heaviest file.
            working_set_after=digest_tokens
            + largest_resident_tokens(root, exclude=(*excluded, digest_path(root))),
        ),
    )


def _summarize(path: Path) -> str:
    """Extract a one-line subject: frontmatter title, first heading, or name.

    Best-effort by design. An unreadable or binary file still relocates; it
    simply carries its filename as the subject rather than blocking the move
    over a cosmetic field.
    """

    if path.is_dir():
        return path.name
    try:
        head = path.read_text(encoding="utf-8")[:4096]
    except (OSError, UnicodeError):
        return path.name
    for line in head.splitlines():
        stripped = line.strip()
        if stripped.startswith("title:"):
            return stripped.removeprefix("title:").strip().strip("\"'") or path.name
        if stripped.startswith("# "):
            return stripped[2:].strip() or path.name
    return path.name


def _record_risk_archived(root: Path, risk_id: str, destination: str) -> None:
    store = ParkingStore(root)
    try:
        store.record_archival(risk_id, destination)
    except Exception as exc:  # noqa: BLE001 - provenance must not abort a completed move
        logger.warning("could not record risk archival for %s: %s", risk_id, exc)


def locate(folder: str | Path, query: str, *, limit: int = 20) -> tuple[LocateHit, ...]:
    """Find where an archived original now lives and what it says.

    This is the restore-cost metric in practice: an agent answers a question
    about relocated history by reading a few matched lines instead of
    re-reading the whole original.
    """

    root = Path(folder)
    if not query.strip():
        raise CompactError("locate requires a non-empty query")
    needle = query.lower()
    hits: list[LocateHit] = []
    by_destination = {str(row["destination"]): str(row["source"]) for row in load_mappings(root)}
    archive = archived_root(root)
    if not archive.is_dir():
        return ()
    for path in sorted(p for p in archive.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        original = by_destination.get(relative, relative)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if needle in line.lower():
                hits.append(
                    LocateHit(
                        archived_path=relative,
                        original_source=original,
                        line=number,
                        excerpt=line.strip()[:240],
                    )
                )
                if len(hits) >= limit:
                    return tuple(hits)
    return tuple(hits)


def restore(folder: str | Path, source: str) -> Path:
    """Copy one archived original back to its original path.

    A copy, not a move: the archive stays complete so the mapping ledger's
    hash remains verifiable after a restore.
    """

    root = Path(folder)
    rows = {str(row["source"]): str(row["destination"]) for row in load_mappings(root)}
    destination = rows.get(source)
    if destination is None:
        raise CompactError(f"no mapping records {source}")
    archived = root / destination
    if not archived.exists():
        raise CompactError(f"archived original is missing: {destination}")
    target = root / source
    if target.exists():
        raise CompactError(f"refusing to overwrite an existing path: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if archived.is_dir():
        shutil.copytree(archived, target)
    else:
        shutil.copy2(archived, target)
    _fsync_directory(target.parent)
    return target


def verify_integrity(folder: str | Path) -> tuple[str, ...]:
    """Re-hash every archived original and report any mismatch.

    This is what makes the zero-loss claim auditable rather than asserted.
    A journalled move that never happened reports as ``PENDING_MOVE`` rather
    than as a loss, because the original is still where the row says it came
    from and a re-run finishes the job.
    """

    root = Path(folder)
    problems: list[str] = []
    pending = pending_moves(root)
    for row in load_mappings(root):
        destination = root / str(row["destination"])
        if not destination.exists():
            source = str(row["source"])
            if source in pending:
                problems.append(f"PENDING_MOVE: {source} -> {row['destination']}")
            else:
                problems.append(f"MISSING_ARCHIVED: {row['destination']}")
            continue
        recorded = str(row.get("sha256", ""))
        if not recorded:
            problems.append(f"NO_HASH_RECORDED: {row['destination']}")
            continue
        if sha256_path(destination) != recorded:
            problems.append(f"HASH_MISMATCH: {row['destination']}")
    return tuple(problems)


__all__ = [
    "apply_plan",
    "archived_root",
    "build_plan",
    "compact_root",
    "digest_path",
    "load_mappings",
    "locate",
    "mappings_path",
    "pending_moves",
    "restore",
    "verify_integrity",
]
