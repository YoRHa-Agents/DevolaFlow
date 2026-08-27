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
    add-dark-mode/checklist.md      FAIL  2500/1200 tokens (soft) 2500/2400 tokens (hard)
    Exit: 1 (1 hard violation in checklist.md)

Exit codes:

* ``0`` — all artifacts under their HARD ceilings (any soft violation
  emits a WARN line to stderr but does NOT fail the run).
* ``1`` — one or more HARD ceiling violations.
* ``2`` — invocation error (missing change-id, change folder absent).

Public API (importable for use by ArchiveManager / lifecycle hooks):

* :class:`BudgetReport` — full per-file budget report.
* :class:`BudgetViolation` — one violation row (FILE / OBSERVED / SOFT / HARD / KIND).
* :class:`SemanticViolation` — one deterministic v16 semantic failure.
* :func:`lint_change` — programmatic entry point.
* :func:`estimate_tokens` — the shared 4-char heuristic.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from devolaflow.agent_workspace import progress as progress_header
from devolaflow.agent_workspace import round_parser
from devolaflow.agent_workspace.change import (
    ACTIVE_DIR_DEFAULT,
    ARCHIVE_DIR_DEFAULT,
    ChangeLayout,
    LegacyChangeLayoutError,
    detect_change_layout,
)
from devolaflow.agent_workspace.preflight import (
    PreflightAuthorizationError,
    _authorization_digest,
    _deterministic_mirror_bytes,
    _extract_preflight_sections,
    _frontmatter_shape,
    _parse_authorization_records,
    _parse_stop_cards,
    _validate_permitted_stops,
    _validate_section0,
    _validate_timestamp,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CHECKLIST_ARTIFACT_BUDGETS",
    "EVIDENCE_DIRECTORY_MAX_BYTES",
    "EVIDENCE_FILE_MAX_BYTES",
    "HUMAN_ARTIFACT_BUDGETS",
    "PATHFINDER_REPORT_FILENAME",
    "BudgetReport",
    "BudgetViolation",
    "HumanBudgetExceededError",
    "SemanticViolation",
    "enforce_digest_budget",
    "estimate_tokens",
    "lint_change",
    "lint_human",
    "main",
]


# Per Rule C-9 — verbatim from
# ``.cursor/rules/repo-governance.mdc#C-9`` +
# ``schemas/agent-workspace/*.yaml#token_budget``.
# Per design.md §1.1: handoff envelopes are 600/1200; per-change
# learnings.jsonl is bounded by file size (50 KB), not token count.
CHECKLIST_ARTIFACT_BUDGETS: Final[dict[str, tuple[int, int]]] = {
    "goal.md": (200, 400),
    "checklist.md": (1200, 2400),
    "stage.md": (400, 800),
    "preflight.md": (600, 1200),
    "spec.md": (1500, 3000),
    "STATUS.yaml": (150, 300),
    "owned_files.txt": (50, 100),
    # OPTIONAL harness pre-analysis artifact per the harness-construction
    # design (.local/tasks/add_harness_design/design.md §3.3): its presence
    # flags the change as harness-flagged; absence is a valid state that
    # yields zero findings and zero budget violations.
    "harness_preflight.md": (800, 1600),
    # Agent onboarding entry point (.local/research/v17.2.0_change_entrance_design.md
    # §4): scaffolded for every new change. Absence in a pre-v17.2 folder is a
    # WARN (ENTRANCE_MISSING) until backfilled on first resume — see
    # _check_entrance for the semantic checks.
    "entrance.md": (400, 800),
    # Optional read-only look-ahead artifact per the Pathfinder role contract.
    "pathfinder_report.md": (800, 1600),
}

# learnings.jsonl: enforced as a file-size ceiling rather than tokens.
LEARNINGS_JSONL_MAX_BYTES: Final[int] = 50 * 1024
EVIDENCE_FILE_MAX_BYTES: Final[int] = 10_240
EVIDENCE_DIRECTORY_MAX_BYTES: Final[int] = 51_200

_UTC_TIMESTAMP_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_GOAL_ENTRY_RE: Final[re.Pattern[str]] = re.compile(
    r"^- (G(?:[1-9]|10)): (.+) → checklist\.md ## (G(?:[1-9]|10))\s*$"
)
_CHECKLIST_GOAL_RE: Final[re.Pattern[str]] = re.compile(r"^## (G(?:[1-9]|1[0-5])): (.+)$")
_EVIDENCE_METADATA_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s{6}evidence:\s*([^|\s]+)(?:\s*\|.*)?$"
)

# OPTIONAL harness pre-analysis artifact — schemas/agent-workspace/
# harness-preflight.yaml. HPF_* finding kinds are the register for
# :func:`_check_harness_preflight`.
HARNESS_PREFLIGHT_FILENAME: Final[str] = "harness_preflight.md"
_HARNESS_PREFLIGHT_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "parent",
    "schema_version",
    "gap_report",
    "axes_config",
)
_HARNESS_PREFLIGHT_HEADINGS: Final[tuple[str, ...]] = (
    "## 1. Target Observation Surface",
    "## 2. Capability Mapping",
    "## 3. Gap Inventory",
    "## 4. Coverage Commitments",
    "## 5. Build Order",
)
_HARNESS_NUMBERED_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^## \d+\. ")

# OPTIONAL Pathfinder look-ahead artifact — schemas/agent-workspace/
# pathfinder-report.yaml. PFR_* finding kinds are the register for
# :func:`_check_pathfinder_report`.
PATHFINDER_REPORT_FILENAME: Final[str] = "pathfinder_report.md"
_PATHFINDER_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "change_id",
    "scan_mode",
    "scan_round",
    "horizon",
    "gap_report",
)
_PATHFINDER_SCAN_MODES: Final[frozenset[str]] = frozenset({"initial", "incremental"})
_PATHFINDER_HEADINGS: Final[tuple[str, ...]] = (
    "## Scan Scope",
    "## Findings",
    "## Handoff",
)


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


def _parse_markdown_frontmatter(
    filename: str,
    result: _ReadResult,
    report: BudgetReport,
) -> round_parser.MarkdownArtifact | None:
    """Strictly parse a required fenced YAML mapping without raising."""
    if result.state == "missing":
        report.violations.append(
            SemanticViolation(filename, "MISSING_ARTIFACT", "required v16 artifact is missing")
        )
        return None
    if result.text is None:
        return None

    try:
        return round_parser.parse_frontmatter(result.text, filename=filename)
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(SemanticViolation(filename, exc.kind, exc.message))
        return None


def _goal_entries(
    body: str,
    report: BudgetReport,
) -> list[tuple[str, str]] | None:
    """Extract exact ordered goal ids/titles and validate their links."""
    lines = body.splitlines()
    try:
        start = lines.index("## Goals") + 1
    except ValueError:
        report.violations.append(
            SemanticViolation("goal.md", "GOAL_ALIGNMENT", "body is missing '## Goals'")
        )
        return None

    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            section.append(line)

    entries: list[tuple[str, str]] = []
    for line in section:
        match = _GOAL_ENTRY_RE.fullmatch(line)
        if match is None or match.group(1) != match.group(3):
            report.violations.append(
                SemanticViolation(
                    "goal.md",
                    "GOAL_ALIGNMENT",
                    "goal entries must use '- Gn: title → checklist.md ## Gn' with equal ids",
                )
            )
            return None
        entries.append((match.group(1), match.group(2)))

    expected_ids = [f"G{index}" for index in range(1, len(entries) + 1)]
    if not entries or [entry[0] for entry in entries] != expected_ids:
        report.violations.append(
            SemanticViolation(
                "goal.md",
                "GOAL_ALIGNMENT",
                "goal ids must be contiguous and ordered from G1",
            )
        )
        return None
    return entries


def _checklist_goal_headings(
    body: str,
    report: BudgetReport,
) -> list[tuple[str, str]] | None:
    """Extract exact ordered ``## Gn: title`` checklist headings."""
    headings: list[tuple[str, str]] = []
    for line in body.splitlines():
        if not line.startswith("## G"):
            continue
        match = _CHECKLIST_GOAL_RE.fullmatch(line)
        if match is None:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "GOAL_ALIGNMENT",
                    "goal headings must use exact '## Gn: title' syntax",
                )
            )
            return None
        headings.append((match.group(1), match.group(2)))
    return headings


def _checklist_items(
    body: str,
    report: BudgetReport,
) -> list[round_parser.ChecklistItem] | None:
    """Adapt the shared item parser to deterministic lint findings."""
    try:
        items = round_parser._parse_checklist_items(  # noqa: SLF001
            body,
            "checklist.md",
            strict_metadata=False,
        )
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(SemanticViolation("checklist.md", exc.kind, exc.message))
        return None
    return list(items)


def _strict_frontmatter_equal(actual: object, expected: object) -> bool:
    """Compare derived frontmatter values without bool/int coercion."""
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            return False
        return all(_strict_frontmatter_equal(actual[key], value) for key, value in expected.items())
    return type(actual) is type(expected) and actual == expected


def _check_derived_field(
    filename: str,
    frontmatter: dict[str, object],
    field_name: str,
    expected: object,
    report: BudgetReport,
) -> None:
    """Compare one stored derived field with its body-derived value."""
    actual = frontmatter.get(field_name)
    if _strict_frontmatter_equal(actual, expected):
        return
    report.violations.append(
        SemanticViolation(
            filename,
            "DERIVED_FIELD",
            f"{field_name}={actual!r}; derived value is {expected!r}",
        )
    )


def _check_evidence_paths(
    change_folder: Path,
    items: list[round_parser.ChecklistItem],
    report: BudgetReport,
) -> None:
    """Require one exact, safe, regular evidence file per checked item."""
    for item in items:
        if not item.checked:
            continue
        evidence_lines = [line for line in item.metadata if line.lstrip().startswith("evidence:")]
        if len(evidence_lines) != 1:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "EVIDENCE_PATH",
                    f"{item.item_id} must declare exactly one evidence path",
                )
            )
            continue
        match = _EVIDENCE_METADATA_RE.fullmatch(evidence_lines[0])
        if match is None:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "EVIDENCE_PATH",
                    f"{item.item_id} evidence metadata is malformed",
                )
            )
            continue
        declared = match.group(1)
        expected = f"evidence/{item.item_id}.txt"
        if declared != expected:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "EVIDENCE_PATH",
                    f"{item.item_id} evidence path must be exactly {expected!r}",
                )
            )
            continue
        target = change_folder / expected
        try:
            regular_file = not target.is_symlink() and target.is_file()
        except OSError:
            regular_file = False
        if not regular_file:
            report.violations.append(
                SemanticViolation(
                    expected,
                    "EVIDENCE_PATH",
                    f"{item.item_id} evidence path is not an existing regular file",
                )
            )


def _check_progress_header(
    body: str,
    items: list[round_parser.ChecklistItem],
    stage_text: str | None,
    report: BudgetReport,
) -> None:
    """Require one pinned, byte-aligned effort-weighted ``## Progress`` header."""
    for item in items:
        for line in item.metadata:
            if (
                line.lstrip().startswith("effort:")
                and round_parser._EFFORT_RE.fullmatch(line) is None  # noqa: SLF001
            ):
                report.violations.append(
                    SemanticViolation(
                        "checklist.md",
                        "PROGRESS_HEADER",
                        f"{item.item_id} effort metadata must be an integer between 1 and 8",
                    )
                )

    lines = body.splitlines()
    heading_indices = [
        index for index, line in enumerate(lines) if line == progress_header.PROGRESS_HEADING
    ]
    if not heading_indices:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                "checklist.md must pin a '## Progress' section directly after '# Checklist'",
            )
        )
        return
    if len(heading_indices) > 1:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                "checklist.md must contain exactly one '## Progress' heading",
            )
        )
        return
    first_goal = next(
        (index for index, line in enumerate(lines) if line.startswith("## G")),
        None,
    )
    if first_goal is not None and heading_indices[0] > first_goal:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                "the '## Progress' section must precede the first goal partition",
            )
        )

    expected = progress_header.render_progress_line(
        progress_header.compute_progress_header(
            items,
            progress_header._lenient_stage(stage_text),  # noqa: SLF001
        )
    )
    actual = progress_header.extract_progress_line(body)
    if actual != expected:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                f"progress line is stale or malformed; the derived line is {expected!r}",
            )
        )


def _check_preflight(
    text: str,
    *,
    change_id: str,
    checklist_ids: set[str] | None,
    repo_root: Path,
    archived: bool,
    report: BudgetReport,
) -> None:
    """Validate canonical Sections 0–3, mirror bytes, and authorization seal."""
    try:
        frontmatter, sections = _extract_preflight_sections(text)
    except PreflightAuthorizationError as exc:
        report.violations.append(
            SemanticViolation("preflight.md", "PREFLIGHT_SECTION_ORDER", str(exc))
        )
        return

    try:
        _frontmatter_shape(frontmatter, change_id=change_id)
    except PreflightAuthorizationError as exc:
        report.violations.append(
            SemanticViolation("preflight.md", "PREFLIGHT_AUTHORIZATION", str(exc))
        )

    authorized_at = frontmatter.get("authorized_at")
    config_hash = frontmatter.get("project_config_hash")
    authorization_hash = frontmatter.get("authorization_hash")

    authorization_valid = authorized_at is None
    if authorized_at is not None:
        try:
            _validate_timestamp(authorized_at, field_name="authorized_at")
            authorization_valid = True
        except PreflightAuthorizationError:
            authorization_valid = False
    hash_valid = config_hash is None or (
        isinstance(config_hash, str) and _SHA256_RE.fullmatch(config_hash)
    )
    seal_valid = authorization_hash is None or (
        isinstance(authorization_hash, str) and _SHA256_RE.fullmatch(authorization_hash)
    )
    if not authorization_valid:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_AUTHORIZATION",
                "authorized_at must be null or an ISO-8601 UTC timestamp",
            )
        )
    if not hash_valid:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_HASH",
                "project_config_hash must be null or 64 lowercase hexadecimal characters",
            )
        )
    if not seal_valid:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_SEAL",
                "authorization_hash must be null or 64 lowercase hexadecimal characters",
            )
        )
    if authorized_at is not None and authorization_valid and config_hash is None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_AUTHORIZATION",
                "a signed preflight requires project_config_hash",
            )
        )
    if authorized_at is not None and authorization_valid and authorization_hash is None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_SEAL",
                "a signed preflight requires authorization_hash",
            )
        )
    if authorized_at is None and config_hash is not None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_HASH",
                "an unsigned preflight must not retain project_config_hash",
            )
        )
    if authorized_at is None and authorization_hash is not None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_SEAL",
                "an unsigned preflight must not retain authorization_hash",
            )
        )

    section0_state = None
    try:
        section0_state = _validate_section0(sections.contents[0], frontmatter)
    except PreflightAuthorizationError as exc:
        report.violations.append(SemanticViolation("preflight.md", "PREFLIGHT_SECTION_0", str(exc)))

    cards = None
    try:
        cards = _parse_stop_cards(
            sections.contents[1],
            checklist_ids=checklist_ids,
        )
    except PreflightAuthorizationError as exc:
        report.violations.append(SemanticViolation("preflight.md", "PREFLIGHT_STOP_CARD", str(exc)))

    if cards is not None and authorization_valid:
        try:
            _parse_authorization_records(
                sections.contents[2],
                cards=cards,
                authorized_at=authorized_at,
            )
        except PreflightAuthorizationError as exc:
            report.violations.append(
                SemanticViolation("preflight.md", "PREFLIGHT_AUTHORIZATION", str(exc))
            )

    try:
        _validate_permitted_stops(sections.contents[3])
    except PreflightAuthorizationError as exc:
        report.violations.append(
            SemanticViolation("preflight.md", "PREFLIGHT_PERMITTED_STOPS", str(exc))
        )

    expected_mirror_hash = config_hash
    if section0_state is not None and section0_state.inherited_hash is not None:
        expected_mirror_hash = section0_state.inherited_hash
    if (
        section0_state is not None
        and section0_state.config is not None
        and config_hash is not None
        and hash_valid
    ):
        compiled_hash = hashlib.sha256(
            _deterministic_mirror_bytes(section0_state.config)
        ).hexdigest()
        if compiled_hash != config_hash:
            report.violations.append(
                SemanticViolation(
                    "preflight.md",
                    "PREFLIGHT_HASH",
                    "project_config_hash does not match deterministic full Section 0 YAML",
                )
            )

    if (
        not archived
        and isinstance(expected_mirror_hash, str)
        and _SHA256_RE.fullmatch(expected_mirror_hash)
    ):
        mirror = repo_root / ".local" / "project_config.yaml"
        try:
            mirror_digest = hashlib.sha256(mirror.read_bytes()).hexdigest()
        except OSError:
            report.violations.append(
                SemanticViolation(
                    "preflight.md",
                    "PREFLIGHT_HASH",
                    "active project configuration mirror is missing or unreadable",
                )
            )
        else:
            if mirror_digest != expected_mirror_hash:
                report.violations.append(
                    SemanticViolation(
                        "preflight.md",
                        "PREFLIGHT_HASH",
                        "project_config_hash does not match raw .local/project_config.yaml bytes",
                    )
                )

    if (
        authorized_at is not None
        and authorization_valid
        and config_hash is not None
        and hash_valid
        and authorization_hash is not None
        and seal_valid
    ):
        expected_seal = _authorization_digest(frontmatter, sections)
        if authorization_hash != expected_seal:
            report.violations.append(
                SemanticViolation(
                    "preflight.md",
                    "PREFLIGHT_SEAL",
                    "authorization_hash does not match signed Sections 0 through 3",
                )
            )


def _resolve_harness_reference(
    reference: str,
    *,
    change_folder: Path,
    repo_root: Path,
) -> Path | None:
    """Resolve a change- or repo-relative reference to an existing regular file."""
    for base in (change_folder, repo_root):
        candidate = base / reference
        if candidate.is_file():
            return candidate
    return None


def _check_harness_reference(
    frontmatter: dict[str, object],
    field_name: str,
    kind: str,
    *,
    nullable: bool,
    change_folder: Path,
    repo_root: Path,
    report: BudgetReport,
    filename: str = HARNESS_PREFLIGHT_FILENAME,
) -> None:
    """Validate one frontmatter path reference of a harness artifact."""
    if field_name not in frontmatter:
        return  # Missing key already reported as HPF_FRONTMATTER.
    value = frontmatter[field_name]
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value:
        report.violations.append(
            SemanticViolation(
                filename,
                kind,
                f"{field_name} must be a non-empty change- or repo-relative path"
                + (" or null" if nullable else ""),
            )
        )
        return
    if Path(value).is_absolute():
        report.violations.append(
            SemanticViolation(
                filename,
                kind,
                f"{field_name} must be a relative path (S-2), got {value!r}",
            )
        )
        return
    if _resolve_harness_reference(value, change_folder=change_folder, repo_root=repo_root) is None:
        report.violations.append(
            SemanticViolation(
                filename,
                kind,
                f"{field_name} {value!r} does not exist relative to the change "
                "folder or the repo root",
            )
        )


def _check_harness_preflight(
    change_folder: Path,
    *,
    repo_root: Path,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Validate the OPTIONAL ``harness_preflight.md`` artifact when present.

    Absence produces zero findings — the change is simply not
    harness-flagged (artifact-as-contract per
    ``schemas/agent-workspace/harness-preflight.yaml#presence_semantics``).
    """
    result = _read_artifact(change_folder, HARNESS_PREFLIGHT_FILENAME, report, cache)
    if result.state == "missing":
        return
    if result.text is None:
        return  # READ_ERROR already recorded by _read_artifact (S-5).

    try:
        artifact = round_parser.parse_frontmatter(result.text, filename=HARNESS_PREFLIGHT_FILENAME)
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(
            SemanticViolation(HARNESS_PREFLIGHT_FILENAME, "HPF_FRONTMATTER", exc.message)
        )
        return

    frontmatter = artifact.frontmatter
    missing = [key for key in _HARNESS_PREFLIGHT_REQUIRED_KEYS if key not in frontmatter]
    if missing:
        report.violations.append(
            SemanticViolation(
                HARNESS_PREFLIGHT_FILENAME,
                "HPF_FRONTMATTER",
                f"frontmatter is missing required key(s): {', '.join(missing)}",
            )
        )

    if "schema_version" in frontmatter and not _strict_frontmatter_equal(
        frontmatter["schema_version"], 1
    ):
        report.violations.append(
            SemanticViolation(
                HARNESS_PREFLIGHT_FILENAME,
                "HPF_SCHEMA_VERSION",
                f"schema_version={frontmatter['schema_version']!r}; the only "
                "supported version is 1",
            )
        )

    headings = [
        line.rstrip()
        for line in artifact.body.splitlines()
        if _HARNESS_NUMBERED_HEADING_RE.match(line)
    ]
    if headings != list(_HARNESS_PREFLIGHT_HEADINGS):
        report.violations.append(
            SemanticViolation(
                HARNESS_PREFLIGHT_FILENAME,
                "HPF_SECTION_ORDER",
                "numbered '## N.' headings must be exactly "
                f"{list(_HARNESS_PREFLIGHT_HEADINGS)} in order; got {headings}",
            )
        )

    _check_harness_reference(
        frontmatter,
        "gap_report",
        "HPF_GAP_REPORT",
        nullable=False,
        change_folder=change_folder,
        repo_root=repo_root,
        report=report,
    )
    _check_harness_reference(
        frontmatter,
        "axes_config",
        "HPF_AXES_CONFIG",
        nullable=True,
        change_folder=change_folder,
        repo_root=repo_root,
        report=report,
    )


_PATHFINDER_ABSOLUTE_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9:])/(?!/)[^\s`'\",)\]]*"
)
_PATHFINDER_FINDING_START_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*-\s+gap_id\s*:", re.MULTILINE
)
_PATHFINDER_SEVERITY_BLOCKER_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*severity\s*:\s*BLOCKER\s*$", re.MULTILINE
)
_PATHFINDER_ACCEPTANCE_SIGNAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^[ \t]*acceptance_signal[ \t]*:[ \t]*([^\r\n]*)$", re.MULTILINE
)


def _pathfinder_value_is_empty(value: str) -> bool:
    """Return whether a scalar Pathfinder field has no meaningful value."""
    return value.strip().strip("\"'") in {"", "null", "None", "[]", "{}"}


def _check_pathfinder_report(
    change_folder: Path,
    *,
    repo_root: Path,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Validate the OPTIONAL Pathfinder report when present.

    Absence is a clean no-op: only a dispatched Pathfinder task creates this
    artifact.  A present report is fail-closed because its contract is the
    evidence consumed by later waves.
    """
    result = _read_artifact(change_folder, PATHFINDER_REPORT_FILENAME, report, cache)
    if result.state == "missing":
        return
    if result.text is None:
        return  # READ_ERROR already recorded by _read_artifact (S-5).

    try:
        artifact = round_parser.parse_frontmatter(result.text, filename=PATHFINDER_REPORT_FILENAME)
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(
            SemanticViolation(PATHFINDER_REPORT_FILENAME, "PFR_FRONTMATTER", exc.message)
        )
        return

    frontmatter = artifact.frontmatter
    missing = [key for key in _PATHFINDER_REQUIRED_KEYS if key not in frontmatter]
    if missing:
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_FRONTMATTER",
                f"frontmatter is missing required key(s): {', '.join(missing)}",
            )
        )

    schema_version = frontmatter.get("schema_version")
    if not _strict_frontmatter_equal(schema_version, 1):
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_SCHEMA_VERSION",
                f"schema_version={schema_version!r}; the only supported version is 1",
            )
        )

    scan_mode = frontmatter.get("scan_mode")
    scan_round = frontmatter.get("scan_round")
    if (
        not isinstance(scan_mode, str)
        or scan_mode not in _PATHFINDER_SCAN_MODES
        or not isinstance(scan_round, int)
        or isinstance(scan_round, bool)
        or scan_round < 1
    ):
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_FRONTMATTER",
                "scan_mode must be initial/incremental and scan_round must be "
                "an integer greater than or equal to 1",
            )
        )

    body_lines = artifact.body.splitlines()
    heading_positions = [
        next((index for index, line in enumerate(body_lines) if line == heading), -1)
        for heading in _PATHFINDER_HEADINGS
    ]
    if (
        any(position < 0 for position in heading_positions)
        or len(set(heading_positions)) != len(_PATHFINDER_HEADINGS)
        or heading_positions != sorted(heading_positions)
    ):
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_SECTION_ORDER",
                f"required headings must appear once in order: {list(_PATHFINDER_HEADINGS)}",
            )
        )

    _check_harness_reference(
        frontmatter,
        "gap_report",
        "PFR_GAP_REPORT",
        nullable=False,
        change_folder=change_folder,
        repo_root=repo_root,
        report=report,
        filename=PATHFINDER_REPORT_FILENAME,
    )

    in_findings_or_handoff = False
    for line in body_lines:
        if line.startswith("## "):
            in_findings_or_handoff = line in {"## Findings", "## Handoff"}
        if in_findings_or_handoff and re.search(r"\b(?:evidence|artifact_path)\s*:", line):
            field_value = line.split(":", 1)[1]
            if _PATHFINDER_ABSOLUTE_PATH_RE.search(field_value):
                report.violations.append(
                    SemanticViolation(
                        PATHFINDER_REPORT_FILENAME,
                        "PFR_ABSOLUTE_PATH",
                        "evidence and handoff paths must be relative (S-2)",
                    )
                )
                break

    for block in _PATHFINDER_FINDING_START_RE.split(artifact.body)[1:]:
        if not _PATHFINDER_SEVERITY_BLOCKER_RE.search(block):
            continue
        signal = _PATHFINDER_ACCEPTANCE_SIGNAL_RE.search(block)
        if signal is None or _pathfinder_value_is_empty(signal.group(1)):
            report.violations.append(
                SemanticViolation(
                    PATHFINDER_REPORT_FILENAME,
                    "PFR_BLOCKER_SIGNAL",
                    "every BLOCKER finding must include a non-empty acceptance_signal",
                )
            )


# entrance.md Section 3 inventory row — backtick-quoted filename in the first cell.
_ENTRANCE_INVENTORY_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\|\s*`([^`]+)`\s*\|")

_ENTRANCE_INVENTORY_HEADING: Final[str] = "## 3. Artifact Inventory"

_ENTRANCE_REQUIRED_HEADINGS: Final[tuple[str, ...]] = (
    "## 1. What This Change Is",
    "## 2. Scenario Routing",
    _ENTRANCE_INVENTORY_HEADING,
    "## 4. Discipline Pointers",
)


def _entrance_expected_inventory() -> set[str]:
    """Section 3 parity target (design D-7).

    The budget registry keys minus the router itself, plus the ``evidence/``
    directory (byte-limited rather than token-budgeted, but still part of the
    artifact set an onboarding agent must know about).
    """
    return (set(CHECKLIST_ARTIFACT_BUDGETS) - {"entrance.md"}) | {"evidence/"}


def _check_entrance(
    change_folder: Path,
    *,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Validate the entrance.md onboarding router (change-entrance schema).

    A missing file yields ``ENTRANCE_MISSING`` at WARN severity — pre-v17.2
    folders are backfilled on first resume (design D-4), so absence must not
    flip the lint exit code. A present-but-malformed file fails loud (S-5).
    """
    result = _read_artifact(change_folder, "entrance.md", report, cache)
    if result.state == "missing":
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_MISSING",
                "agent onboarding entry point is absent; backfill from the "
                "scaffold template (schemas/agent-workspace/change-entrance.yaml)",
                severity="WARN",
            )
        )
        return
    if result.text is None:
        return  # READ_ERROR already recorded by _read_artifact.

    try:
        artifact = round_parser.parse_frontmatter(result.text, filename="entrance.md")
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(SemanticViolation("entrance.md", exc.kind, exc.message))
        return

    frontmatter = artifact.frontmatter or {}
    if frontmatter.get("parent") != report.change_id:
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_PARENT",
                f"frontmatter parent {frontmatter.get('parent')!r} must equal "
                f"the change-id {report.change_id!r}",
            )
        )
    if frontmatter.get("schema_version") != 1:
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_SCHEMA_VERSION",
                f"schema_version must be 1 (got {frontmatter.get('schema_version')!r})",
            )
        )

    lines = artifact.body.splitlines()
    for heading in _ENTRANCE_REQUIRED_HEADINGS:
        if heading not in lines:
            report.violations.append(
                SemanticViolation(
                    "entrance.md",
                    "ENTRANCE_SECTION",
                    f"required section heading {heading!r} is absent",
                )
            )

    if _ENTRANCE_INVENTORY_HEADING not in lines:
        return  # ENTRANCE_SECTION already recorded; parity has no anchor.

    listed: set[str] = set()
    in_inventory = False
    for line in lines:
        if line.startswith("## "):
            in_inventory = line == _ENTRANCE_INVENTORY_HEADING
            continue
        if in_inventory:
            match = _ENTRANCE_INVENTORY_ROW_RE.match(line)
            if match is not None:
                listed.add(match.group(1))
    expected = _entrance_expected_inventory()
    if listed != expected:
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_PARITY",
                "Section 3 inventory drifted from the budget registry — "
                f"missing {sorted(expected - listed)!r}, "
                f"surplus {sorted(listed - expected)!r}",
            )
        )


def _lint_checklist_semantics(
    change_folder: Path,
    *,
    repo_root: Path,
    archived: bool,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Run the four v16 semantic check families with dependency gating."""
    goal = _parse_markdown_frontmatter(
        "goal.md",
        _read_artifact(change_folder, "goal.md", report, cache),
        report,
    )
    checklist = _parse_markdown_frontmatter(
        "checklist.md",
        _read_artifact(change_folder, "checklist.md", report, cache),
        report,
    )
    preflight_result = _read_artifact(change_folder, "preflight.md", report, cache)
    preflight = _parse_markdown_frontmatter("preflight.md", preflight_result, report)

    goal_entries = _goal_entries(goal.body, report) if goal is not None else None
    checklist_headings = (
        _checklist_goal_headings(checklist.body, report) if checklist is not None else None
    )
    if (
        goal_entries is not None
        and checklist_headings is not None
        and goal_entries != checklist_headings
    ):
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "GOAL_ALIGNMENT",
                f"goal entries {goal_entries!r} do not equal checklist headings "
                f"{checklist_headings!r}",
            )
        )

    if goal is not None and goal.frontmatter is not None and goal_entries is not None:
        _check_derived_field(
            "goal.md",
            goal.frontmatter,
            "goals_count",
            len(goal_entries),
            report,
        )

    items = _checklist_items(checklist.body, report) if checklist is not None else None
    if items is not None:
        if checklist is not None and checklist.frontmatter is not None:
            priority_dist = {
                priority: sum(item.priority == priority for item in items)
                for priority in ("P0", "P1", "P2")
            }
            reverted_open = sum(
                not item.checked
                and any(line.startswith("      reverted:") for line in item.metadata)
                for item in items
            )
            for field_name, expected in (
                ("total_items", len(items)),
                ("checked", sum(item.checked for item in items)),
                ("priority_dist", priority_dist),
                ("reverted_open", reverted_open),
            ):
                _check_derived_field(
                    "checklist.md",
                    checklist.frontmatter,
                    field_name,
                    expected,
                    report,
                )
        _check_evidence_paths(change_folder, items, report)
        if checklist is not None:
            stage_result = _read_artifact(change_folder, "stage.md", report, cache)
            _check_progress_header(checklist.body, items, stage_result.text, report)

    if preflight is not None and preflight_result.text is not None:
        _check_preflight(
            preflight_result.text,
            change_id=report.change_id,
            checklist_ids={item.item_id for item in items} if items is not None else None,
            repo_root=repo_root,
            archived=archived,
            report=report,
        )

    _check_entrance(change_folder, report=report, cache=cache)


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
        except (FileNotFoundError, LegacyChangeLayoutError) as exc:
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
        failure_label = (
            "hard/semantic"
            if any(isinstance(v, SemanticViolation) for v in report.hard_failures)
            else "hard ceiling"
        )
        print(
            f"lint: FAIL — {len(report.hard_failures)} {failure_label} violation(s) in "
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
