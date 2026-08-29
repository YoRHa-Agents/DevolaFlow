"""Frozen record types for the explicit local archive runtime.

Split out of `devolaflow.local.archive` at v20.0.0 to honour the W-9
module-size ratchet; `devolaflow.local.archive` remains the public owner
surface and re-exports every name here, so external callers and the W-26..28
rule citations stay valid.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


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
class ArchiveRecord:
    """One discovered archival candidate and its conservative classification."""

    source: str
    identity: str
    classification: str
    protection: ProtectionVerdict
    protection_reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    findings: tuple[Finding, ...] = ()

    @property
    def protected(self) -> bool:
        """Return whether this record cannot be moved."""

        return self.protection is not ProtectionVerdict.ALLOWED


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
    surface: str = "tasks"

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
    recovery_required: bool = False
    recovery_hint: str | None = None
    surface: str = "tasks"

    @property
    def success(self) -> bool:
        """Return true only when the requested operation completed."""

        return not self.refused and not self.findings and not self.recovery_required


@dataclass(frozen=True)
class ArchiveApproval:
    """An operator-approved, exact subset of one archive plan.

    The approval is intentionally separate from :class:`ArchivePlan`: a plan
    is report output, while this record freezes both the plan fingerprint and
    the exact source/destination pairs the operator selected.
    """

    plan_fingerprint: str
    entries: tuple[tuple[str, str], ...]
