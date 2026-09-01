"""Tool-mediated relocation of archived-change handoff envelopes (v24.1.0).

Rule ref: `.rules/soul.mdc` §S-9.1, signed in the v24 judgment ledger.

S-9 forbids modifying or deleting an envelope. S-9.1 carves out exactly one
motion — relocation, which changes location and nothing else — behind four
conditions, and this module is the only sanctioned mover. Every guarantee the
amendment makes is checkable here rather than asserted:

* the owning change must already be archived, so no parallel writer is
  still appending to the sequence;
* the approval fingerprint must match the plan the operator actually read;
* a mapping row carries the content hash across the move, so "not one byte
  changed" survives as an audit question rather than a promise;
* the generated index is refreshed, so relocation never costs navigability.

`handoff_index` remains the read-only companion and is unchanged: the two
modules are additive, not alternatives.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from devolaflow._durability import fsync_directory as _fsync_directory
from devolaflow.workspace_compact.handoff_index import (
    HANDOFF_DIR,
    write_handoff_index,
)
from devolaflow.workspace_compact.models import CompactError
from devolaflow.workspace_ledger import (
    LedgerError,
    append_ledger_row,
    has_symlink_component,
    sha256_bytes,
    sha256_path,
    utc_now,
)

logger = logging.getLogger(__name__)

ARCHIVE_DIR = Path(".local") / ".agent" / "archive"
RELOCATED_DIR = ARCHIVE_DIR / "handoff"
MAPPINGS_RELATIVE = RELOCATED_DIR / "relocation-mappings.yaml"

_ENVELOPE_RE = re.compile(
    r"^(?P<from>L[0-3])__(?P<to>L[0-3])__(?P<change_id>[a-z0-9][a-z0-9.-]*[a-z0-9])"
    r"__(?P<seq>\d{4})\.yaml$"
)

#: `.local/.agent/archive/<date>-<change-id>/` is the whole-change archive
#: marker S-9.1 condition 1 requires. The date prefix is free-form by
#: convention, so the change id is matched as a suffix.
_ARCHIVED_CHANGE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(?P<change_id>.+)$")


@dataclass(frozen=True)
class RelocationCandidate:
    """One envelope the plan proposes to move, with its S-9.1 evidence."""

    source: str
    destination: str
    change_id: str
    seq: int
    bytes: int
    sha256: str


@dataclass(frozen=True)
class RelocationPlan:
    """Report-only relocation proposal; writes nothing."""

    repo_root: str
    candidates: tuple[RelocationCandidate, ...]
    refused: tuple[str, ...] = ()
    archived_changes: tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        """Return the digest an approval must cite to authorise this plan."""

        payload = "\n".join(
            f"{item.source}\x1f{item.destination}\x1f{item.sha256}" for item in self.candidates
        )
        return sha256_bytes(f"{self.repo_root}\x1e{payload}".encode())


@dataclass(frozen=True)
class RelocationResult:
    """Outcome of an approved relocation attempt."""

    moved: tuple[RelocationCandidate, ...] = ()
    findings: tuple[str, ...] = ()
    refused: bool = False
    index_path: str | None = None

    @property
    def success(self) -> bool:
        """Return true only when every approved envelope relocated cleanly."""

        return not self.refused and not self.findings


def archived_change_ids(repo_root: str | Path) -> frozenset[str]:
    """Return every change id whose whole-change archive folder exists.

    This is S-9.1 condition 1 in code. An envelope whose change is still
    active is not a candidate at any size, because the append-only sequence
    is precisely most valuable while parallel agents are still writing it.
    """

    directory = Path(repo_root) / ARCHIVE_DIR
    if not directory.is_dir():
        return frozenset()
    found = set()
    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            continue
        match = _ARCHIVED_CHANGE_RE.match(child.name)
        if match is not None:
            found.add(match.group("change_id"))
    return frozenset(found)


def plan_relocation(
    repo_root: str | Path,
    *,
    change_id: str | None = None,
) -> RelocationPlan:
    """Classify handoff envelopes against S-9.1; read-only, writes nothing.

    An envelope belonging to an active change is reported in ``refused``
    rather than dropped silently, so the operator can see that the tool
    considered it and why it declined (S-5).
    """

    root = Path(repo_root)
    directory = root / HANDOFF_DIR
    archived = archived_change_ids(root)
    if not directory.is_dir():
        return RelocationPlan(
            repo_root=root.as_posix(),
            candidates=(),
            refused=("NO_HANDOFF_DIR: nothing to relocate",),
            archived_changes=tuple(sorted(archived)),
        )

    candidates: list[RelocationCandidate] = []
    refused: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        match = _ENVELOPE_RE.match(path.name)
        if match is None:
            refused.append(f"NOT_AN_ENVELOPE: {path.name}")
            continue
        if path.is_symlink() or has_symlink_component(root, path):
            refused.append(f"SYMLINK_SKIPPED: {path.name}")
            continue
        envelope_change = match.group("change_id")
        if change_id is not None and envelope_change != change_id:
            continue
        if envelope_change not in archived:
            refused.append(f"CHANGE_STILL_ACTIVE: {path.name}")
            continue
        destination = RELOCATED_DIR / envelope_change / path.name
        if (root / destination).exists():
            refused.append(f"DESTINATION_EXISTS: {path.name}")
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            refused.append(f"UNREADABLE: {path.name}: {exc}")
            continue
        candidates.append(
            RelocationCandidate(
                source=(HANDOFF_DIR / path.name).as_posix(),
                destination=destination.as_posix(),
                change_id=envelope_change,
                seq=int(match.group("seq")),
                bytes=size,
                sha256=sha256_path(path),
            )
        )

    return RelocationPlan(
        repo_root=root.as_posix(),
        candidates=tuple(candidates),
        refused=tuple(refused),
        archived_changes=tuple(sorted(archived)),
    )


def apply_relocation(
    repo_root: str | Path,
    plan: RelocationPlan,
    *,
    approval_fingerprint: str,
) -> RelocationResult:
    """Move an approved envelope set, appending one mapping row per move.

    Refuses outright when the plan no longer describes the tree. An envelope
    whose hash moved is a different envelope, and approving one is not
    approving the other.
    """

    root = Path(repo_root)
    if approval_fingerprint != plan.fingerprint:
        return RelocationResult(
            findings=("APPROVAL_MISMATCH: approval does not match the current plan",),
            refused=True,
        )
    if not plan.candidates:
        return RelocationResult(
            findings=("EMPTY_APPROVAL: no envelopes were approved",), refused=True
        )

    current = plan_relocation(root)
    live = {item.source: item for item in current.candidates}
    findings: list[str] = []
    for item in plan.candidates:
        present = live.get(item.source)
        if present is None:
            findings.append(f"PLAN_CHANGED: no longer eligible: {item.source}")
        elif present.sha256 != item.sha256:
            findings.append(f"CONTENT_CHANGED: {item.source}")
    if findings:
        return RelocationResult(findings=tuple(findings), refused=True)

    moved: list[RelocationCandidate] = []
    for item in plan.candidates:
        source_path = root / item.source
        destination_path = root / item.destination
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(os.fspath(source_path), os.fspath(destination_path))
            _fsync_directory(source_path.parent)
            _fsync_directory(destination_path.parent)
            after = sha256_path(destination_path)
            if after != item.sha256:
                findings.append(f"HASH_MISMATCH_AFTER_MOVE: {item.source}")
            append_ledger_row(
                root / MAPPINGS_RELATIVE,
                {
                    "source": item.source,
                    "destination": item.destination,
                    "reason": f"S-9.1 relocation: change {item.change_id} is archived",
                    "timestamp": utc_now(),
                    "sha256": after,
                    "bytes": item.bytes,
                    "change_id": item.change_id,
                    "seq": item.seq,
                },
                required_fields=("source", "destination", "reason", "timestamp", "sha256"),
                unique_fields=("source", "destination"),
            )
        except (OSError, LedgerError) as exc:
            logger.warning("envelope relocation refused after partial progress: %s", exc)
            findings.append(f"RELOCATE_ERROR: {item.source}: {exc}")
            return RelocationResult(moved=tuple(moved), findings=tuple(findings), refused=True)
        moved.append(item)

    index_path, index_findings = write_handoff_index(root)
    findings.extend(index_findings)
    return RelocationResult(
        moved=tuple(moved),
        findings=tuple(findings),
        refused=bool(findings),
        index_path=None if index_path is None else index_path.as_posix(),
    )


def verify_relocations(repo_root: str | Path) -> tuple[str, ...]:
    """Re-hash every relocated envelope and report any mismatch.

    Relocation's whole claim is "content unchanged". This makes that claim
    falsifiable after the fact, the same way `verify_integrity` does for
    folder compaction.
    """

    from devolaflow.workspace_ledger import load_ledger_rows

    root = Path(repo_root)
    problems: list[str] = []
    try:
        rows = load_ledger_rows(
            root / MAPPINGS_RELATIVE,
            required_fields=("sequence", "source", "destination", "sha256"),
        )
    except LedgerError as exc:
        raise CompactError(f"relocation ledger is unreadable: {exc}") from exc
    for row in rows:
        destination = root / str(row["destination"])
        if not destination.exists():
            problems.append(f"MISSING_RELOCATED: {row['destination']}")
            continue
        if sha256_path(destination) != str(row["sha256"]):
            problems.append(f"HASH_MISMATCH: {row['destination']}")
    return tuple(problems)


__all__ = [
    "ARCHIVE_DIR",
    "MAPPINGS_RELATIVE",
    "RELOCATED_DIR",
    "RelocationCandidate",
    "RelocationPlan",
    "RelocationResult",
    "apply_relocation",
    "archived_change_ids",
    "plan_relocation",
    "verify_relocations",
]
