"""Focused implementation slice for the workspace-lint API."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def lint_change(
    change_id: str,
    *,
    repo_root: Path | None = None,
    active_dir: Path | None = None,
    archive_dir: Path | None = None,
) -> BudgetReport:
    """Lint one active or archived change using its detected layout contract.

    Checklist folders use the v16 budgets, evidence byte ceilings, strict
    frontmatter parsing, and four semantic check families. Mixed folders
    (checklist.md alongside legacy markers) get the checklist budgets plus
    an ``INVALID_MIXED`` hard violation.

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
      LegacyChangeLayoutError: when the folder still uses the removed
        pre-v16 tasks.md/acceptance.md layout.
    """
    root = repo_root or Path.cwd()
    active_root = active_dir if active_dir is not None else Path(ACTIVE_DIR_DEFAULT)
    archive_root = archive_dir if archive_dir is not None else Path(ARCHIVE_DIR_DEFAULT)
    if not active_root.is_absolute():
        active_root = root / active_root
    if not archive_root.is_absolute():
        archive_root = root / archive_root

    change_folder = active_root / change_id
    archived = False
    if not change_folder.is_dir():
        # Fall back to archive lookup (linear scan; date prefix unknown).
        change_folder = _find_archived_folder(archive_root, change_id)
        if change_folder is None:
            raise FileNotFoundError(
                f"lint_change: no folder for {change_id!r} found under "
                f"{active_root!s} or {archive_root!s}"
            )
        archived = True

    report = BudgetReport(change_id=change_id, change_folder=change_folder)
    cache: dict[str, _ReadResult] = {}
    layout = detect_change_layout(change_folder)
    budgets = CHECKLIST_ARTIFACT_BUDGETS
    if layout is ChangeLayout.INVALID_MIXED:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "INVALID_MIXED",
                "checklist.md cannot coexist with tasks.md or acceptance.md",
            )
        )

    _lint_token_budgets(change_folder, budgets, report, cache)
    _lint_learnings_size(change_folder, report)
    _lint_evidence_sizes(change_folder, report)
    _check_harness_preflight(change_folder, repo_root=root, report=report, cache=cache)
    _check_pathfinder_report(change_folder, repo_root=root, report=report, cache=cache)
    if layout is ChangeLayout.CHECKLIST:
        _lint_checklist_semantics(
            change_folder,
            repo_root=root,
            archived=archived,
            report=report,
            cache=cache,
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


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
