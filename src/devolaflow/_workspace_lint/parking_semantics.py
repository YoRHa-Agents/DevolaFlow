"""Drift and budget lint for the parking and compaction surfaces (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §5 layer 2.

Layer 1 (tool-only writes) and layer 3 (the lifecycle hook) both act at write
time. This is the layer that acts after the fact: it re-renders each generated
view from its authoritative ledger and compares, so an edit that bypassed both
earlier layers still surfaces before a commit rather than in six weeks when
someone notices the index and the ledger disagree.
"""

from __future__ import annotations

import logging
from pathlib import Path

from devolaflow._workspace_lint.budget import (
    BudgetReport,
    BudgetViolation,
    SemanticViolation,
)

logger = logging.getLogger(__name__)


def lint_parking_surface(folder: Path, report: BudgetReport) -> None:
    """Append parking drift and budget findings for one folder."""

    from devolaflow.parking.models import PARKING_ARTIFACT_BUDGETS
    from devolaflow.parking.store import PARKING_DIRNAME, ParkingStore

    store = ParkingStore(folder)
    if not store.exists:
        return
    for item in store.audit():
        report.violations.append(
            SemanticViolation(f"{PARKING_DIRNAME}/{item.code.lower()}", item.code, item.message)
        )
    for name, key in (("INDEX.md", "INDEX.md"), ("judge.md", "judge.md")):
        path = store.root / name
        if path.exists():
            _budget(path, f"{PARKING_DIRNAME}/{name}", PARKING_ARTIFACT_BUDGETS[key], report)
    if store.risks_dir.is_dir():
        for path in sorted(store.risks_dir.glob("RISK-*.md")):
            _budget(
                path,
                f"{PARKING_DIRNAME}/risks/{path.name}",
                PARKING_ARTIFACT_BUDGETS["risk"],
                report,
            )


def lint_compact_surface(folder: Path, report: BudgetReport) -> None:
    """Append compaction digest drift and integrity findings for one folder."""

    from devolaflow.workspace_compact.digest import audit_digest
    from devolaflow.workspace_compact.engine import compact_root, verify_integrity
    from devolaflow.workspace_compact.models import COMPACT_DIRNAME
    from devolaflow.workspace_ledger import LedgerError

    if not compact_root(folder).is_dir():
        return
    try:
        for item in audit_digest(folder):
            report.violations.append(
                SemanticViolation(f"{COMPACT_DIRNAME}/DIGEST.md", item.code, item.message)
            )
        for problem in verify_integrity(folder):
            code, _, detail = problem.partition(": ")
            report.violations.append(
                SemanticViolation(f"{COMPACT_DIRNAME}/mappings.yaml", code, detail or problem)
            )
    except LedgerError as exc:
        report.violations.append(
            SemanticViolation(f"{COMPACT_DIRNAME}/mappings.yaml", "MALFORMED_MAPPING", str(exc))
        )


def _budget(path: Path, label: str, budget: tuple[int, int], report: BudgetReport) -> None:
    # Deferred: `devolaflow.harness` transitively imports `agent_workspace`,
    # which imports this package, so a module-level import would cycle.
    from devolaflow.harness.context_tokens import estimate_tokens

    soft, hard = budget
    try:
        tokens = estimate_tokens(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        logger.warning("parking lint could not read %s: %s", path, exc)
        return
    report.checked_files.append(label)
    if tokens > hard:
        report.violations.append(BudgetViolation(label, tokens, soft, hard, "FAIL"))
    elif tokens > soft:
        report.violations.append(BudgetViolation(label, tokens, soft, hard, "WARN"))


__all__ = ["lint_compact_surface", "lint_parking_surface"]
