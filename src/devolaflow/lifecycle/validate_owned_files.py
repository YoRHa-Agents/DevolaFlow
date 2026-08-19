"""Workflow-level owned_files completeness hook — ``validate_owned_files``.

Checks that dispatch payloads for workflows with canonical file manifests
include all required paths in owned_files. Prevents the recurring bug where
repo-init dispatches miss .local/ and .rules/ paths (v7.4.1/v7.5.0 feedback).

Registered as an extra handler on the ``pre_dispatch`` event (runs after the
default :func:`validate_dispatch` handler).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT = "pre_dispatch"

WORKFLOW_MANIFESTS: dict[str, list[str]] = {
    "repo-init": [
        ".local/feedbacks/",
        ".local/tasks/",
        ".local/memory/",
        ".local/index.md",
        ".rules/compile-config.yaml",
        # v8.2.3 — A1 .agent/* substrate per .local/research/v8.3.0_design.md §1.1.
        # Order MUST stay parity-locked with workflow-system/agent/templates/
        # builtin/repo-init.yaml::scaffold.config.canonical_manifest and the
        # Repo-Init Pre-Dispatch Contract table in workflow-system/agent/SKILL.md
        # (see tests/test_canonical_manifest_parity.py for the regression gate).
        ".local/.agent/active/",
        ".local/.agent/handoff/",
        ".local/.agent/archive/",
    ],
}


def _path_covered(required: str, owned: set[str]) -> bool:
    """Return True if *required* is represented in the *owned* set."""
    norm = required.rstrip("/")
    return any(o in (required, norm) or o.startswith(norm) for o in owned)


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    if not isinstance(payload, dict):
        return []

    workflow = payload.get("workflow") or payload.get("workflow_id") or ""
    if workflow not in WORKFLOW_MANIFESTS:
        return []

    manifest = WORKFLOW_MANIFESTS[workflow]
    owned = payload.get("owned_files") or payload.get("files") or []
    if not isinstance(owned, list):
        return []

    owned_set = set(owned)
    missing = [p for p in manifest if not _path_covered(p, owned_set)]

    if not missing:
        return []

    return [
        HookViolation(
            code="VOF001",
            message=(
                f"owned_files missing {len(missing)} canonical path(s) "
                f"for workflow '{workflow}': {missing}"
            ),
            severity="blocker",
            context={
                "workflow": workflow,
                "missing_paths": missing,
                "owned_files": list(owned),
            },
        )
    ]


def validate_owned_files(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Validate owned_files completeness for workflows with canonical manifests."""
    violations = _collect_violations(payload)
    return finalize(EVENT, violations, strict=strict)


def get_canonical_manifest(workflow: str) -> list[str]:
    """Return the canonical manifest paths for a workflow, or empty list."""
    return list(WORKFLOW_MANIFESTS.get(workflow, []))


@dataclass
class DoctorFinding:
    """A single finding from ``check_init_health``.

    ``advisory=True`` findings (Track C-2: stub first-line skeleton drift)
    never affect :attr:`DoctorReport.healthy` — stubs are user-editable and
    survive re-scaffolds by design, so drift is surfaced but non-fatal.
    """

    path: str
    expected: bool
    found: bool
    detail: str
    advisory: bool = False

    @property
    def ok(self) -> bool:
        return self.expected == self.found


@dataclass
class DoctorReport:
    """Aggregate result of ``check_init_health``."""

    findings: list[DoctorFinding]

    @property
    def healthy(self) -> bool:
        return all(f.ok for f in self.findings if not f.advisory)

    @property
    def missing(self) -> list[str]:
        return [f.path for f in self.findings if f.expected and not f.found and not f.advisory]

    @property
    def advisories(self) -> list[str]:
        """Paths with non-blocking advisory findings (skeleton drift)."""
        return [f.path for f in self.findings if f.advisory and not f.ok]

    def summary(self) -> str:
        total = len(self.findings)
        ok = sum(1 for f in self.findings if f.ok)
        text = f"{ok}/{total} checks passed"
        if not self.healthy:
            text += f"; missing: {self.missing}"
        if self.advisories:
            text += f"; advisory: {self.advisories}"
        return text


def check_init_health(cwd: str | Path) -> DoctorReport:
    """Check a directory against the repo-init canonical manifest + contract.

    Inspects ``cwd`` for ALL paths declared in
    ``WORKFLOW_MANIFESTS["repo-init"]``, then for the FULL scaffold
    structure contract derived from the scaffold's own constants
    (``devolaflow.local.workspace.expected_scaffold_paths`` — Track C-2,
    A-5 single owner; the pre-C-2 hand-maintained ``extras`` list is gone,
    it had already drifted from the v14.0.0 human-surface additions).
    Stub first-line skeleton drift is reported as ADVISORY findings that
    never flip :attr:`DoctorReport.healthy`.
    """
    from pathlib import Path as _Path

    from devolaflow.local.workspace import (
        expected_scaffold_paths,
        expected_stub_first_lines,
        verify_scaffold_structure,
    )

    root = _Path(cwd)
    findings: list[DoctorFinding] = []
    seen: set[str] = set()

    manifest = get_canonical_manifest("repo-init")
    for p in manifest:
        full = root / p
        if p.endswith("/"):
            found = full.is_dir()
            detail = "directory" if found else "missing directory"
        else:
            found = full.is_file()
            detail = "file" if found else "missing file"
        findings.append(DoctorFinding(path=p, expected=True, found=found, detail=detail))
        seen.add(p)

    for rel, desc in expected_scaffold_paths():
        if rel in seen:
            continue
        seen.add(rel)
        full = root / rel
        found = full.is_dir() if rel.endswith("/") else full.is_file()
        findings.append(
            DoctorFinding(
                path=rel,
                expected=True,
                found=found,
                detail=desc if found else f"missing {desc}",
            )
        )

    # Advisory skeleton check (first-line drift only; same derivation the
    # scaffold's own self-check uses).
    _missing, drifted = verify_scaffold_structure(root)
    expected_lines = expected_stub_first_lines()
    for rel, _expected_first, actual_first in drifted:
        findings.append(
            DoctorFinding(
                path=rel,
                expected=True,
                found=False,
                detail=(
                    f"skeleton drifted: first line {actual_first!r} != template "
                    f"{expected_lines[rel]!r} (advisory — fine if intentionally customised)"
                ),
                advisory=True,
            )
        )

    return DoctorReport(findings=findings)


__all__ = [
    "EVENT",
    "WORKFLOW_MANIFESTS",
    "DoctorFinding",
    "DoctorReport",
    "check_init_health",
    "get_canonical_manifest",
    "validate_owned_files",
]
