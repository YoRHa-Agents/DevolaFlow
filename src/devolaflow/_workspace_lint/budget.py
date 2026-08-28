"""Focused implementation slice for artifact budgets."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


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
class SemanticViolation:
    """One deterministic checklist-layout semantic failure."""

    filename: str
    kind: str
    message: str
    severity: str = "FAIL"

    def render(self, change_id: str) -> str:
        """Render a one-line semantic failure for stderr / CLI output."""
        return f"{change_id}/{self.filename:18s} {self.severity:4s} [{self.kind}] {self.message}"


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
    violations: list[BudgetViolation | SemanticViolation] = field(default_factory=list)
    checked_files: list[str] = field(default_factory=list)

    @property
    def hard_failures(self) -> list[BudgetViolation | SemanticViolation]:
        """Subset of ``violations`` with severity ``"FAIL"``."""
        return [v for v in self.violations if v.severity == "FAIL"]

    @property
    def soft_warnings(self) -> list[BudgetViolation | SemanticViolation]:
        """Subset of ``violations`` with severity ``"WARN"``."""
        return [v for v in self.violations if v.severity == "WARN"]

    @property
    def exit_code(self) -> int:
        """``1`` for any hard/semantic failure; ``0`` otherwise."""
        return 1 if self.hard_failures else 0


@dataclass(frozen=True)
class _ReadResult:
    """Cached artifact read outcome used by budgets and semantic checks."""

    text: str | None
    state: str


def estimate_tokens(text: str) -> int:
    """Rough token-count heuristic: ``len(text) // 4``.

    Matches OpenAI's tokenizer rule of thumb (1 token ≈ 4 chars of
    English text). Conservative enough for budget enforcement; the
    schemas size their soft / hard ceilings around this same heuristic.
    """
    if not text:
        return 0
    return len(text) // 4


def _record_checked(report: BudgetReport, filename: str) -> None:
    """Record *filename* once while preserving deterministic order."""
    if filename not in report.checked_files:
        report.checked_files.append(filename)


def _read_artifact(
    change_folder: Path,
    filename: str,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> _ReadResult:
    """Read one UTF-8 artifact once and convert I/O failures into findings."""
    cached = cache.get(filename)
    if cached is not None:
        return cached

    target = change_folder / filename
    if not target.exists():
        result = _ReadResult(text=None, state="missing")
    elif not target.is_file():
        report.violations.append(
            SemanticViolation(
                filename,
                "READ_ERROR",
                "artifact exists but is not a regular file",
            )
        )
        result = _ReadResult(text=None, state="error")
    else:
        try:
            result = _ReadResult(text=target.read_text(encoding="utf-8"), state="ok")
        except (OSError, UnicodeError):
            report.violations.append(
                SemanticViolation(
                    filename,
                    "READ_ERROR",
                    "artifact could not be read as UTF-8",
                )
            )
            result = _ReadResult(text=None, state="error")

    cache[filename] = result
    return result


def _lint_token_budgets(
    change_folder: Path,
    budgets: dict[str, tuple[int, int]],
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Apply the selected layout's token budgets."""
    for filename, (soft, hard) in budgets.items():
        _record_checked(report, filename)
        result = _read_artifact(change_folder, filename, report, cache)
        if result.text is None:
            continue
        tokens = estimate_tokens(result.text)
        if tokens > hard:
            severity = "FAIL"
        elif tokens > soft:
            severity = "WARN"
        else:
            continue
        report.violations.append(
            BudgetViolation(
                filename=filename,
                observed_tokens=tokens,
                soft_budget=soft,
                hard_budget=hard,
                severity=severity,
            )
        )


def _lint_learnings_size(change_folder: Path, report: BudgetReport) -> None:
    """Apply the layout-independent ``learnings.jsonl`` byte ceiling."""
    learnings = change_folder / "learnings.jsonl"
    if not learnings.exists():
        return
    _record_checked(report, "learnings.jsonl")
    try:
        size = learnings.stat().st_size
    except OSError:
        report.violations.append(
            SemanticViolation(
                "learnings.jsonl",
                "READ_ERROR",
                "artifact size could not be read",
            )
        )
        return
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


def _lint_evidence_sizes(change_folder: Path, report: BudgetReport) -> None:
    """Enforce the v16 evidence per-file and aggregate byte ceilings."""
    evidence_dir = change_folder / "evidence"
    if not evidence_dir.exists():
        return
    if evidence_dir.is_symlink() or not evidence_dir.is_dir():
        report.violations.append(
            SemanticViolation(
                "evidence/",
                "EVIDENCE_DIRECTORY",
                "evidence must be a real directory inside the change folder",
            )
        )
        return

    try:
        candidates = sorted(evidence_dir.rglob("*"))
    except OSError:
        report.violations.append(
            SemanticViolation(
                "evidence/",
                "READ_ERROR",
                "evidence directory could not be enumerated",
            )
        )
        return

    total_bytes = 0
    for path in candidates:
        try:
            if path.is_symlink() or not path.is_file():
                continue
            size = path.stat().st_size
        except OSError:
            relative = path.relative_to(change_folder).as_posix()
            report.violations.append(
                SemanticViolation(
                    relative,
                    "READ_ERROR",
                    "evidence file size could not be read",
                )
            )
            continue
        relative = path.relative_to(change_folder).as_posix()
        _record_checked(report, relative)
        total_bytes += size
        if size > EVIDENCE_FILE_MAX_BYTES:
            report.violations.append(
                SemanticViolation(
                    relative,
                    "EVIDENCE_FILE_SIZE",
                    f"{size} bytes exceeds {EVIDENCE_FILE_MAX_BYTES}-byte ceiling",
                )
            )

    if total_bytes > EVIDENCE_DIRECTORY_MAX_BYTES:
        report.violations.append(
            SemanticViolation(
                "evidence/",
                "EVIDENCE_DIRECTORY_SIZE",
                f"{total_bytes} bytes exceeds {EVIDENCE_DIRECTORY_MAX_BYTES}-byte ceiling",
            )
        )


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
