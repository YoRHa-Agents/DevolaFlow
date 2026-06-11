"""Token-budget linter for ``.local/.agent/active/<change-id>/`` artifacts.

Closes Rule C-9 enforcement per
``.cursor/rules/repo-governance.mdc#C-9`` +
``schemas/agent-workspace/*.yaml#token_budget``.

Token-count heuristic: ``len(text) // 4`` (matches OpenAI's tokenizer
rule of thumb — 1 token ≈ 4 characters of English text). The schemas
declare both a ``soft`` budget (warn) and a ``hard`` ceiling (fail).

CLI:

::

    $ python -m devolaflow.agent_workspace.lint <change-id>
    add-dark-mode/goal.md           OK    34/200 tokens (soft)  68/400 tokens (hard)
    add-dark-mode/spec.md           WARN  1620/1500 tokens (soft) 1620/3000 tokens (hard)
    add-dark-mode/tasks.md          FAIL  1700/800 tokens (soft) 1700/1500 tokens (hard)
    Exit: 1 (1 hard violation in tasks.md)

Exit codes:

* ``0`` — all artifacts under their HARD ceilings (any soft violation
  emits a WARN line to stderr but does NOT fail the run).
* ``1`` — one or more HARD ceiling violations.
* ``2`` — invocation error (missing change-id, change folder absent).

Public API (importable for use by ArchiveManager / lifecycle hooks):

* :class:`BudgetReport` — full per-file budget report.
* :class:`BudgetViolation` — one violation row (FILE / OBSERVED / SOFT / HARD / KIND).
* :func:`lint_change` — programmatic entry point.
* :func:`estimate_tokens` — the shared 4-char heuristic.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from devolaflow.agent_workspace.change import (
    ACTIVE_DIR_DEFAULT,
    ARCHIVE_DIR_DEFAULT,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ARTIFACT_BUDGETS",
    "HUMAN_ARTIFACT_BUDGETS",
    "BudgetReport",
    "BudgetViolation",
    "HumanBudgetExceededError",
    "enforce_digest_budget",
    "estimate_tokens",
    "lint_change",
    "lint_human",
    "main",
]


# Per Rule C-9 — verbatim from
# ``.cursor/rules/repo-governance.mdc#C-9`` +
# ``schemas/agent-workspace/*.yaml#token_budget``.
ARTIFACT_BUDGETS: Final[dict[str, tuple[int, int]]] = {
    "goal.md": (200, 400),
    "acceptance.md": (400, 800),
    "spec.md": (1500, 3000),
    "tasks.md": (800, 1500),
    "STATUS.yaml": (100, 200),
    "owned_files.txt": (50, 100),
    # Per design.md §1.1: handoff envelopes are 600/1200; per-change
    # learnings.jsonl is bounded by file size (50 KB), not token count.
}

# learnings.jsonl: enforced as a file-size ceiling rather than tokens.
LEARNINGS_JSONL_MAX_BYTES: Final[int] = 50 * 1024


# Per the v14.0.0 design §4c — NEW C-9 rows for the ``.local/human/`` surface.
# TOKENS are the sole enforced unit (finding F-4): the line/word figures in
# the design are authoring guidance only, NOT a second linted axis — so these
# reuse the existing :func:`estimate_tokens` heuristic with NO new measurement
# machinery. Keys are the canonical artifact patterns relative to
# ``.local/human/``; the per-file ``input/requirements/<domain>.md`` shard cap
# (finding F-3) and the ``input/amendments/`` ledger files each apply PER FILE.
HUMAN_ARTIFACT_BUDGETS: Final[dict[str, tuple[int, int]]] = {
    "input/constitution.md": (800, 1500),
    "input/requirements.md": (1200, 2500),
    "input/requirements/<domain>.md": (1200, 2500),
    "input/amendments/<date>-<slug>.md": (400, 800),
    "output/DIGEST.md": (600, 1000),
    "output/convergence/<version>-convergence.md": (700, 1000),
}

# Root of the human surface (relative to the repo root); INPUT + OUTPUT zones
# are both linted, the dated ``archive/`` is not (frozen snapshots — design §2).
HUMAN_DIR_DEFAULT: Final[Path] = Path(".local") / "human"

# The REQ-OUT-01 artifact — the digest's :data:`HUMAN_ARTIFACT_BUDGETS` key.
DIGEST_BUDGET_KEY: Final[str] = "output/DIGEST.md"


@dataclass
class BudgetViolation:
    """One per-artifact violation row.

    Attributes:
      filename: artifact filename (e.g. ``goal.md``).
      observed_tokens: estimated token count from :func:`estimate_tokens`.
      soft_budget: the schema's ``token_budget.soft``.
      hard_budget: the schema's ``token_budget.hard``.
      severity: ``"WARN"`` (soft over) or ``"FAIL"`` (hard over).
    """

    filename: str
    observed_tokens: int
    soft_budget: int
    hard_budget: int
    severity: str

    def render(self, change_id: str) -> str:
        """Render a one-line summary for stderr / CLI output."""
        return (
            f"{change_id}/{self.filename:18s} {self.severity:4s} "
            f"{self.observed_tokens}/{self.soft_budget} tokens (soft) "
            f"{self.observed_tokens}/{self.hard_budget} tokens (hard)"
        )


@dataclass
class BudgetReport:
    """Aggregate budget report for a single change folder.

    Attributes:
      change_id: id of the change being linted.
      change_folder: filesystem path of the change folder.
      violations: list of all violations (both WARN and FAIL severities).
      checked_files: list of every file actually examined (for diagnostics).
    """

    change_id: str
    change_folder: Path
    violations: list[BudgetViolation] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)

    @property
    def hard_failures(self) -> list[BudgetViolation]:
        """Subset of ``violations`` with severity ``"FAIL"``."""
        return [v for v in self.violations if v.severity == "FAIL"]

    @property
    def soft_warnings(self) -> list[BudgetViolation]:
        """Subset of ``violations`` with severity ``"WARN"``."""
        return [v for v in self.violations if v.severity == "WARN"]

    @property
    def exit_code(self) -> int:
        """``1`` when any HARD violations exist; ``0`` otherwise (WARN-only OK)."""
        return 1 if self.hard_failures else 0


def estimate_tokens(text: str) -> int:
    """Rough token-count heuristic: ``len(text) // 4``.

    Matches OpenAI's tokenizer rule of thumb (1 token ≈ 4 chars of
    English text). Conservative enough for budget enforcement; the
    schemas size their soft / hard ceilings around this same heuristic.
    """
    if not text:
        return 0
    return len(text) // 4


def lint_change(
    change_id: str,
    *,
    repo_root: Path | None = None,
    active_dir: Path | None = None,
    archive_dir: Path | None = None,
) -> BudgetReport:
    """Lint a single active change folder against its per-artifact budgets.

    The lint inspects each filename in :data:`ARTIFACT_BUDGETS` plus the
    learnings.jsonl byte-size cap. Files that do not exist contribute
    zero violations (treated as ``0/budget`` — under-budget is the goal).

    Args:
      change_id: id of the active change to lint.
      repo_root: repo root (defaults to ``Path.cwd()``).
      active_dir: override for the active root (relative to ``repo_root``).
      archive_dir: override for the archive root (used as a fallback
        when the change is no longer active).

    Returns:
      :class:`BudgetReport` with all violations + checked files.

    Raises:
      FileNotFoundError: when the change folder does not exist in either
        active or archive roots.
    """
    root = repo_root or Path.cwd()
    active_root = active_dir if active_dir is not None else Path(ACTIVE_DIR_DEFAULT)
    archive_root = archive_dir if archive_dir is not None else Path(ARCHIVE_DIR_DEFAULT)
    if not active_root.is_absolute():
        active_root = root / active_root
    if not archive_root.is_absolute():
        archive_root = root / archive_root

    change_folder = active_root / change_id
    if not change_folder.is_dir():
        # Fall back to archive lookup (linear scan; date prefix unknown).
        change_folder = _find_archived_folder(archive_root, change_id)
        if change_folder is None:
            raise FileNotFoundError(
                f"lint_change: no folder for {change_id!r} found under "
                f"{active_root!s} or {archive_root!s}"
            )

    report = BudgetReport(change_id=change_id, change_folder=change_folder)

    for filename, (soft, hard) in ARTIFACT_BUDGETS.items():
        target = change_folder / filename
        if not target.exists():
            report.checked_files.append(filename)
            continue
        text = target.read_text(encoding="utf-8")
        tokens = estimate_tokens(text)
        report.checked_files.append(filename)
        if tokens > hard:
            report.violations.append(
                BudgetViolation(
                    filename=filename,
                    observed_tokens=tokens,
                    soft_budget=soft,
                    hard_budget=hard,
                    severity="FAIL",
                )
            )
        elif tokens > soft:
            report.violations.append(
                BudgetViolation(
                    filename=filename,
                    observed_tokens=tokens,
                    soft_budget=soft,
                    hard_budget=hard,
                    severity="WARN",
                )
            )

    # learnings.jsonl: enforced by file-size ceiling rather than tokens.
    learnings = change_folder / "learnings.jsonl"
    if learnings.exists():
        size = learnings.stat().st_size
        report.checked_files.append("learnings.jsonl")
        if size > LEARNINGS_JSONL_MAX_BYTES:
            report.violations.append(
                BudgetViolation(
                    filename="learnings.jsonl",
                    observed_tokens=size,
                    soft_budget=LEARNINGS_JSONL_MAX_BYTES,
                    hard_budget=LEARNINGS_JSONL_MAX_BYTES,
                    severity="FAIL",
                )
            )

    return report


def _find_archived_folder(archive_root: Path, change_id: str) -> Path | None:
    """Linear scan for an archived folder matching ``change_id`` (any date prefix)."""
    if not archive_root.is_dir():
        return None
    for child in archive_root.iterdir():
        if not child.is_dir():
            continue
        suffix = child.name.split("-", 3)
        if len(suffix) >= 4 and "-".join(suffix[3:]) == change_id:
            return child
        if child.name == change_id:
            return child
    return None


def _human_budget_for(rel: str) -> tuple[int, int] | None:
    """Return the C-9 budget for a path relative to ``.local/human/``.

    ``rel`` uses forward slashes. Returns ``None`` for files not governed by
    a :data:`HUMAN_ARTIFACT_BUDGETS` row (e.g. ``README.md`` or anything under
    the frozen ``archive/`` zone) — those are intentionally unbudgeted, not a
    silent drop.
    """
    fixed = {
        "input/constitution.md": "input/constitution.md",
        "input/requirements.md": "input/requirements.md",
        "output/DIGEST.md": "output/DIGEST.md",
    }
    if rel in fixed:
        return HUMAN_ARTIFACT_BUDGETS[fixed[rel]]

    parts = rel.split("/")
    if len(parts) == 3 and rel.endswith(".md"):
        zone, family, _name = parts
        if zone == "input" and family == "requirements":
            return HUMAN_ARTIFACT_BUDGETS["input/requirements/<domain>.md"]
        if zone == "input" and family == "amendments":
            return HUMAN_ARTIFACT_BUDGETS["input/amendments/<date>-<slug>.md"]
        if zone == "output" and family == "convergence":
            return HUMAN_ARTIFACT_BUDGETS["output/convergence/<version>-convergence.md"]
    return None


def lint_human(
    repo_root: Path | None = None,
    *,
    human_root: Path | None = None,
) -> BudgetReport:
    """Lint the ``.local/human/`` INPUT + OUTPUT zones against the §4c budgets.

    A sibling entry point to :func:`lint_change` (which is change-folder-only
    and is deliberately NOT overloaded). Walks ``input/**`` + ``output/**``,
    maps each file to its :data:`HUMAN_ARTIFACT_BUDGETS` row via
    :func:`_human_budget_for`, and applies the TOKEN budget with the shared
    :func:`estimate_tokens` heuristic. The per-file ``input/requirements/
    <domain>.md`` shard cap and the ``input/amendments/`` ledger files each
    apply PER FILE. The dated ``archive/`` zone is excluded (frozen
    snapshots).

    Args:
      repo_root: repo root (default: ``Path.cwd()``).
      human_root: override the ``.local/human`` root (relative to
        ``repo_root`` when not absolute) — mainly for tests.

    Returns:
      :class:`BudgetReport` with ``change_id="human"``, all budget
      violations, and the relative path of every budget-governed file
      checked. An absent ``.local/human/`` directory yields an empty report
      (the surface is opt-in / may not be scaffolded yet — that is a valid
      state, NOT an error).
    """
    root = repo_root or Path.cwd()
    base = human_root if human_root is not None else Path(HUMAN_DIR_DEFAULT)
    if not base.is_absolute():
        base = root / base

    report = BudgetReport(change_id="human", change_folder=base)
    if not base.is_dir():
        return report

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        budget = _human_budget_for(rel)
        if budget is None:
            continue
        soft, hard = budget
        text = path.read_text(encoding="utf-8")
        tokens = estimate_tokens(text)
        report.checked_files.append(rel)
        if tokens > hard:
            report.violations.append(
                BudgetViolation(
                    filename=rel,
                    observed_tokens=tokens,
                    soft_budget=soft,
                    hard_budget=hard,
                    severity="FAIL",
                )
            )
        elif tokens > soft:
            report.violations.append(
                BudgetViolation(
                    filename=rel,
                    observed_tokens=tokens,
                    soft_budget=soft,
                    hard_budget=hard,
                    severity="WARN",
                )
            )

    return report


class HumanBudgetExceededError(ValueError):
    """A rendered human OUTPUT artifact exceeds its C-9 hard ceiling.

    REQ-OUT-01 enforcement — BLOCKING since v14.2.0 per the v14.0.0 design
    telegraph (``.local/research/v14.0.0_design.md`` §8b: "REQ-OUT-01 lint is
    advisory this cycle; promote to blocking in v14.2.0"). Raised by
    :func:`enforce_digest_budget` so the reporter emission path refuses to
    write an over-ceiling digest (S-5 explicit error state — never a silent
    over-budget write). The offending :class:`BudgetViolation` is carried on
    ``violation`` for programmatic consumers.
    """

    def __init__(self, violation: BudgetViolation) -> None:
        self.violation = violation
        super().__init__(
            f"REQ-OUT-01: {violation.filename} is {violation.observed_tokens} tokens — "
            f"over the C-9 hard ceiling of {violation.hard_budget} "
            f"(soft {violation.soft_budget}); trim the digest before emission"
        )


def enforce_digest_budget(text: str) -> BudgetViolation | None:
    """Enforce ``output/DIGEST.md``'s C-9 token budget on rendered *text*.

    REQ-OUT-01 — BLOCKING since v14.2.0. The v14.1.0 state was advisory:
    :func:`lint_human` flagged an over-budget digest only when separately
    invoked, while the reporter emission path silently wrote it. This helper
    is the promotion: the emission path calls it on the rendered digest text
    BEFORE writing, and a hard-ceiling violation raises instead of warning.

    The soft tier stays advisory (the documented C-9 escape hatch — "Soft
    budget over → warn. Hard ceiling over → fail"): an over-soft digest is
    returned as a ``WARN`` :class:`BudgetViolation` for the caller to log,
    and the write proceeds. No env flag gates this check (W-20 reuse-first;
    zero new flags).

    Returns:
      ``None`` when under the soft budget; the ``WARN``
      :class:`BudgetViolation` when over soft but under hard.

    Raises:
      HumanBudgetExceededError: when *text* exceeds the hard ceiling.
    """
    soft, hard = HUMAN_ARTIFACT_BUDGETS[DIGEST_BUDGET_KEY]
    tokens = estimate_tokens(text)
    if tokens > hard:
        raise HumanBudgetExceededError(
            BudgetViolation(
                filename=DIGEST_BUDGET_KEY,
                observed_tokens=tokens,
                soft_budget=soft,
                hard_budget=hard,
                severity="FAIL",
            )
        )
    if tokens > soft:
        return BudgetViolation(
            filename=DIGEST_BUDGET_KEY,
            observed_tokens=tokens,
            soft_budget=soft,
            hard_budget=hard,
            severity="WARN",
        )
    return None


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — ``python -m devolaflow.agent_workspace.lint <id>``.

    Returns the exit code (``0`` / ``1`` / ``2``). All output is written
    to stderr so the call site can pipe stdout into another tool.
    """
    parser = argparse.ArgumentParser(
        prog="python -m devolaflow.agent_workspace.lint",
        description=(
            "Lint a .local/.agent/active/<change-id>/ folder against C-9 budgets, "
            "or the .local/human/ surface with --human."
        ),
    )
    parser.add_argument(
        "change_id",
        nargs="?",
        default=None,
        help="lowercase-kebab-case change id (e.g. add-dark-mode, v8.3.0-pv05); "
        "omit when using --human",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="lint the .local/human/ INPUT + OUTPUT zones instead of a change folder",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repo root directory (default: cwd)",
    )
    parser.add_argument(
        "--active-dir",
        type=Path,
        default=None,
        help="override active dir (default: .local/.agent/active)",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=None,
        help="override archive dir (default: .local/.agent/archive)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-file PASS lines (still print WARN/FAIL)",
    )
    args = parser.parse_args(argv)

    if args.human:
        report = lint_human(repo_root=args.repo_root)
    else:
        if not args.change_id:
            parser.error("change_id is required unless --human is given")
        try:
            report = lint_change(
                args.change_id,
                repo_root=args.repo_root,
                active_dir=args.active_dir,
                archive_dir=args.archive_dir,
            )
        except FileNotFoundError as exc:
            print(f"lint: {exc}", file=sys.stderr)
            return 2

    if not args.quiet:
        # PASS rows for every checked file (so the operator sees coverage).
        for filename in report.checked_files:
            if any(v.filename == filename for v in report.violations):
                continue
            print(f"{report.change_id}/{filename:18s} OK", file=sys.stderr)
    for v in report.violations:
        print(v.render(report.change_id), file=sys.stderr)

    if report.hard_failures:
        print(
            f"lint: FAIL — {len(report.hard_failures)} hard ceiling violation(s) in "
            f"{report.change_id!r}",
            file=sys.stderr,
        )
    elif report.soft_warnings:
        print(
            f"lint: WARN — {len(report.soft_warnings)} soft budget warning(s) in "
            f"{report.change_id!r} (no hard violations)",
            file=sys.stderr,
        )

    return report.exit_code


if __name__ == "__main__":  # pragma: no cover - CLI entry only
    raise SystemExit(main())
