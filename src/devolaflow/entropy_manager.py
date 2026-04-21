"""Entropy Manager — documentation freshness + drift detection + GC.

v8.0.0 (P-11) — implements the Entropy Management / GC Agent candidate
(tweet_analysis_harness_engineering_v7.8.md §4.5, patch plan §3 P-11).

Three responsibilities wrapped in one module:

* :class:`DocFreshness` — scans a directory tree for documents whose
  ``last_modified`` timestamp lags behind a configurable ``staleness_threshold``
  (days). Emits a per-file staleness score (0.0 fresh ... 1.0 maximally stale)
  plus the raw age in days.
* :class:`DeviationScanner` — detects documentation-vs-code drift by comparing
  the ``source_version`` frontmatter on every human document against the
  ``version`` frontmatter on its declared ``source_files`` under the agent
  tree. Supersedes the stand-alone :mod:`devolaflow.check_drift` routine
  which now delegates here.
* :func:`cleanup` — GC dispatcher. Applies retention rules (delete / archive
  / touch) based on a :class:`DocFreshnessReport` + :class:`DeviationReport`.
  Supports ``dry_run=True`` (default) which produces a :class:`DryRunReport`
  without touching the filesystem, and ``dry_run=False`` which applies the
  rules and returns an :class:`ApplyReport`.

All three responsibilities honour repository rule S-5 (no silent failures):
every exception path logs and either re-raises or returns an explicit
error record. I/O is confined to the public entrypoints — helpers are pure.

Design notes:

* Frontmatter parsing mirrors :func:`devolaflow.check_drift._parse_frontmatter`
  so existing ``source_version`` / ``source_files`` contracts keep working.
* :func:`cleanup`'s ``retention_rules`` is a list of dataclass records so
  callers can inject project-specific retention without subclassing.
* The module adds **zero** new agent-dispatch schema keys — it only surfaces
  scan/cleanup APIs that the ``entropy-cleanup`` workflow template calls
  into. P6 cache-layout invariant is preserved.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml

logger = logging.getLogger(__name__)


__all__ = [
    "ApplyReport",
    "CleanupAction",
    "DeviationReport",
    "DeviationRecord",
    "DeviationScanner",
    "DocFreshness",
    "DocFreshnessReport",
    "DocFreshnessRecord",
    "DryRunReport",
    "RetentionRule",
    "cleanup",
    "iter_documents",
]


SECONDS_PER_DAY: float = 86400.0
DEFAULT_STALENESS_THRESHOLD_DAYS: int = 30
DEFAULT_MAX_AGE_DAYS: int = 365


# ── I/O helpers (pure, re-usable) ────────────────────────────────────────


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file.

    Returns an empty dict when the file is missing a ``---`` fence or when
    the fenced block is not valid YAML. Never raises — callers expect a
    best-effort parse (matches :func:`devolaflow.check_drift._parse_frontmatter`).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read frontmatter from %s: %s", path, exc)
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        parsed = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        logger.warning("Malformed YAML frontmatter in %s: %s", path, exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def iter_documents(root: Path, suffixes: tuple[str, ...] = (".md", ".yaml", ".yml")) -> list[Path]:
    """Recursively enumerate document files under ``root``.

    Skips dot-directories (``.git``, ``.local``, ``__pycache__`` etc.) so we
    don't pick up generated artefacts. Sorted for deterministic output.
    """
    if not root.is_dir():
        return []
    out: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in suffixes:
            continue
        if any(part.startswith(".") and part not in {".", ".."} for part in candidate.parts):
            continue
        out.append(candidate)
    return out


# ── DocFreshness ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DocFreshnessRecord:
    """Per-document freshness measurement."""

    path: Path
    age_days: float
    staleness_score: float
    is_stale: bool


@dataclass(frozen=True)
class DocFreshnessReport:
    """Aggregate freshness report."""

    scanned_at: str
    threshold_days: int
    records: tuple[DocFreshnessRecord, ...]

    @property
    def stale_count(self) -> int:
        """Number of records flagged ``is_stale``."""
        return sum(1 for r in self.records if r.is_stale)

    @property
    def fresh_count(self) -> int:
        """Records below the staleness threshold."""
        return len(self.records) - self.stale_count


class DocFreshness:
    """Scan documents for staleness signals.

    A document is considered *stale* when ``(now - last_modified)`` exceeds
    the configured ``staleness_threshold`` (days). The ``staleness_score``
    is the age clamped to ``[0, max_age_days]`` and normalised into the
    ``[0.0, 1.0]`` range so downstream consumers can rank candidates.
    """

    def __init__(
        self,
        staleness_threshold_days: int = DEFAULT_STALENESS_THRESHOLD_DAYS,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> None:
        """Configure the freshness thresholds."""
        if staleness_threshold_days < 0:
            raise ValueError("staleness_threshold_days must be >= 0")
        if max_age_days <= 0:
            raise ValueError("max_age_days must be > 0")
        self.staleness_threshold_days = staleness_threshold_days
        self.max_age_days = max_age_days

    def _age_days(self, path: Path, now: datetime) -> float:
        """Return ``now - mtime`` in days (0.0 if the file is missing)."""
        try:
            mtime = path.stat().st_mtime
        except OSError as exc:
            logger.warning("Cannot stat %s for freshness: %s", path, exc)
            return 0.0
        last_modified = datetime.fromtimestamp(mtime, tz=UTC)
        delta_seconds = (now - last_modified).total_seconds()
        return max(0.0, delta_seconds / SECONDS_PER_DAY)

    def score(self, age_days: float) -> float:
        """Map raw age into ``[0.0, 1.0]`` staleness score."""
        if age_days <= 0:
            return 0.0
        return min(1.0, age_days / float(self.max_age_days))

    def scan(self, root: Path | str) -> DocFreshnessReport:
        """Walk ``root`` and return a report of per-file freshness."""
        root_path = Path(root)
        now = datetime.now(UTC)
        records: list[DocFreshnessRecord] = []
        for doc in iter_documents(root_path):
            age_days = self._age_days(doc, now)
            records.append(
                DocFreshnessRecord(
                    path=doc,
                    age_days=age_days,
                    staleness_score=self.score(age_days),
                    is_stale=age_days >= float(self.staleness_threshold_days),
                )
            )
        return DocFreshnessReport(
            scanned_at=now.isoformat(),
            threshold_days=self.staleness_threshold_days,
            records=tuple(records),
        )


# ── DeviationScanner ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeviationRecord:
    """A single human-doc / agent-source version mismatch."""

    human_doc: Path
    source_ref: str
    expected_version: str
    declared_version: str


@dataclass(frozen=True)
class DeviationReport:
    """Aggregate deviation report.

    ``stale_docs`` are human documents whose ``source_version`` frontmatter
    lags behind at least one of their declared ``source_files``. This is the
    same class of finding produced by :mod:`devolaflow.check_drift` today.
    """

    scanned_at: str
    stale_docs: tuple[DeviationRecord, ...]

    @property
    def drift_detected(self) -> bool:
        """True when at least one deviation was recorded."""
        return len(self.stale_docs) > 0


class DeviationScanner:
    """Compare human-doc versions with agent-source versions.

    The scanner reads the YAML frontmatter of every ``*.md`` file beneath the
    configured human-doc directories and, for each declared ``source_files``
    entry, compares the ``source_version`` against the frontmatter
    ``version`` of the referenced agent file. Mismatches are collected as
    :class:`DeviationRecord` entries.

    Intentionally delegate-friendly: ``check_drift`` wraps a single call to
    :meth:`scan` / :meth:`print_report`.
    """

    def __init__(
        self,
        project_root: Path | str,
        human_subdirs: tuple[str, ...] = ("workflow-system/human/en", "workflow-system/human/zh"),
        agent_subdir: str = "workflow-system/agent",
    ) -> None:
        """Store the project root and relative layout."""
        self.project_root = Path(project_root)
        self.human_subdirs = human_subdirs
        self.agent_subdir = agent_subdir

    def _iter_human_docs(self) -> list[Path]:
        """Return every human-facing markdown doc under the configured dirs."""
        out: list[Path] = []
        for rel in self.human_subdirs:
            candidate_dir = self.project_root / rel
            if not candidate_dir.is_dir():
                continue
            out.extend(sorted(candidate_dir.glob("*.md")))
        return out

    def _check_one_doc(
        self,
        doc: Path,
        agent_dir: Path,
    ) -> list[DeviationRecord]:
        """Return drift records for a single human document."""
        fm = _parse_frontmatter(doc)
        declared = str(fm.get("source_version", "0.0.0"))
        refs = fm.get("source_files", []) or []
        out: list[DeviationRecord] = []
        for src_ref in refs:
            src_path = agent_dir / str(src_ref)
            if not src_path.exists():
                continue
            src_fm = _parse_frontmatter(src_path)
            expected = str(src_fm.get("version", "0.0.0"))
            if expected != declared:
                out.append(
                    DeviationRecord(
                        human_doc=doc.relative_to(self.project_root),
                        source_ref=str(src_ref),
                        expected_version=expected,
                        declared_version=declared,
                    )
                )
        return out

    def scan(self) -> DeviationReport:
        """Walk the human-doc directories and produce a drift report."""
        now_iso = datetime.now(UTC).isoformat()
        agent_dir = self.project_root / self.agent_subdir
        stale: list[DeviationRecord] = []
        for doc in self._iter_human_docs():
            stale.extend(self._check_one_doc(doc, agent_dir))
        return DeviationReport(scanned_at=now_iso, stale_docs=tuple(stale))

    def print_report(self, report: DeviationReport | None = None) -> bool:
        """Print a human-readable summary. Mirrors legacy ``check_drift()``.

        Returns ``True`` when drift is present (matches the
        ``devolaflow.check_drift.check_drift()`` contract).
        """
        if report is None:
            report = self.scan()
        if not report.drift_detected:
            print("No drift detected. All human docs are in sync.")
            return False
        print("Drift detected:")
        for rec in report.stale_docs:
            print(
                f"  {rec.human_doc}: source={rec.expected_version}, doc has={rec.declared_version}"
            )
        print(f"\n{len(report.stale_docs)} stale file(s). Run 'make sync-human-docs' to update.")
        return True


# ── Cleanup / GC ─────────────────────────────────────────────────────────


CleanupAction = Literal["delete", "archive", "touch", "flag"]


@dataclass(frozen=True)
class RetentionRule:
    """A single retention policy entry consumed by :func:`cleanup`."""

    min_staleness_score: float
    action: CleanupAction
    reason: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_staleness_score <= 1.0:
            raise ValueError("min_staleness_score must be within [0.0, 1.0]")
        if self.action not in ("delete", "archive", "touch", "flag"):
            raise ValueError(f"Unknown cleanup action: {self.action}")


@dataclass(frozen=True)
class DryRunReport:
    """What :func:`cleanup` *would* do if ``dry_run=False``."""

    planned_actions: tuple[tuple[Path, CleanupAction, str], ...]
    freshness_report: DocFreshnessReport | None = None
    deviation_report: DeviationReport | None = None


@dataclass(frozen=True)
class ApplyReport:
    """What :func:`cleanup` actually performed."""

    applied_actions: tuple[tuple[Path, CleanupAction, str], ...] = ()
    errors: tuple[tuple[Path, str], ...] = field(default_factory=tuple)
    freshness_report: DocFreshnessReport | None = None
    deviation_report: DeviationReport | None = None


def _match_rule(score: float, rules: list[RetentionRule]) -> RetentionRule | None:
    """Return the rule with the highest ``min_staleness_score`` <= score."""
    candidates = [r for r in rules if score >= r.min_staleness_score]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.min_staleness_score)


def _plan_actions(
    freshness: DocFreshnessReport,
    rules: list[RetentionRule],
) -> list[tuple[Path, CleanupAction, str]]:
    """Build the planned-action list without touching the filesystem."""
    planned: list[tuple[Path, CleanupAction, str]] = []
    for rec in freshness.records:
        rule = _match_rule(rec.staleness_score, rules)
        if rule is None:
            continue
        planned.append((rec.path, rule.action, rule.reason or rule.action))
    return planned


def _apply_action(path: Path, action: CleanupAction) -> None:
    """Execute a single retention action on-disk."""
    if action == "delete":
        path.unlink()
        return
    if action == "archive":
        archive_dir = path.parent / "_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / path.name
        path.replace(target)
        return
    if action == "touch":
        now_ts = datetime.now(UTC).timestamp()
        path.touch(exist_ok=True)
        import os

        os.utime(path, (now_ts, now_ts))
        return
    # "flag" — no-op on disk; the record lives in the report only.


def cleanup(
    root: Path | str,
    retention_rules: list[RetentionRule] | None = None,
    *,
    freshness: DocFreshness | None = None,
    deviation: DeviationScanner | None = None,
    dry_run: bool = True,
) -> DryRunReport | ApplyReport:
    """Run the entropy-cleanup GC pass over ``root``.

    Produces a :class:`DryRunReport` when ``dry_run=True`` (default) — safe
    to run in CI without side-effects — and an :class:`ApplyReport` when
    ``dry_run=False``, in which case the planned retention actions are
    performed. Both reports carry the underlying freshness and deviation
    reports so callers can correlate signals.

    When ``retention_rules`` is ``None`` a conservative default is used:
    ``staleness_score >= 0.5`` → ``flag`` (report-only, no FS change). Callers
    requesting destructive actions must pass explicit rules.
    """
    root_path = Path(root)
    freshness_tracker = freshness or DocFreshness()
    freshness_report = freshness_tracker.scan(root_path)

    deviation_report: DeviationReport | None = None
    if deviation is not None:
        deviation_report = deviation.scan()

    rules = retention_rules or [
        RetentionRule(min_staleness_score=0.5, action="flag", reason="default-policy"),
    ]
    planned = _plan_actions(freshness_report, rules)

    if dry_run:
        return DryRunReport(
            planned_actions=tuple(planned),
            freshness_report=freshness_report,
            deviation_report=deviation_report,
        )

    applied: list[tuple[Path, CleanupAction, str]] = []
    errors: list[tuple[Path, str]] = []
    for path, action, reason in planned:
        try:
            _apply_action(path, action)
        except OSError as exc:
            logger.exception("Cleanup action %s failed for %s", action, path)
            errors.append((path, f"{action}: {exc}"))
            continue
        applied.append((path, action, reason))
    return ApplyReport(
        applied_actions=tuple(applied),
        errors=tuple(errors),
        freshness_report=freshness_report,
        deviation_report=deviation_report,
    )
