"""Deterministic, report-only digestion of retrospective artifacts.

The runtime deliberately separates source extraction from operational learning
storage.  Discovery and extraction are read-only; persistence is available
only through the explicitly named :func:`capture_digest_entries` helper.
Natural-language activation is pure and does not inspect process state.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from devolaflow.learnings import DEFAULT_DECAY_HALF_LIFE_DAYS, Learning, capture_learning

__all__ = [
    "DigestCategory",
    "DigestCuration",
    "DigestRecord",
    "DigestResult",
    "DigestStatus",
    "DigestVerdict",
    "RetroDigestVerdict",
    "RetrospectiveSource",
    "build_digest",
    "capture_digest_entries",
    "classify_retro_digest_intent",
    "discover_evaluations",
    "discover_retrospectives",
    "extract_digest_records",
    "extract_evaluation_findings",
    "extract_retrospective_records",
    "render_digest_report",
    "to_learning_entries",
]


RetroDigestVerdict = Literal["DIGEST_REQUESTED", "DIGEST_SUGGESTED", "NO_DIGEST"]
DigestVerdict = RetroDigestVerdict
DigestCategory = Literal["lesson", "benefit"]
DigestStatus = Literal["OK", "INSUFFICIENT"]
SourceKind = Literal["retrospective", "evaluation"]


_REQUESTED_TRIGGERS: Final[tuple[str, ...]] = (
    "retro digest",
    "retrospective digest",
    "digest the retrospectives",
    "digest retrospectives",
    "summarize retrospectives",
    "summarise retrospectives",
    "review the retrospectives",
    "review retrospectives",
    "extract lessons from retrospectives",
    "extract learnings from retrospectives",
)
_SUGGESTED_TRIGGERS: Final[tuple[str, ...]] = (
    "retrospective",
    "retrospectives",
    "cycle learnings",
    "cycle lessons",
    "what did we learn",
    "lessons learned",
    "lessons learnt",
    "historical learnings",
    "historical lessons",
)

_CYCLE_RE: Final[re.Pattern[str]] = re.compile(r"v\d+(?:\.\d+){1,2}", re.IGNORECASE)
_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_BULLET_RE: Final[re.Pattern[str]] = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+(.*)$")
_TABLE_SEPARATOR_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$"
)


@dataclass(frozen=True, slots=True)
class RetrospectiveSource:
    """A discovered repository-relative retrospective or evaluation source."""

    cycle: str
    path: str
    kind: SourceKind = "retrospective"

    @property
    def relative_path(self) -> str:
        """Compatibility alias for callers that name the path explicitly."""
        return self.path

    @property
    def source_path(self) -> str:
        """Compatibility alias used by provenance consumers."""
        return self.path


@dataclass(frozen=True, slots=True)
class DigestRecord:
    """One verbatim passage extracted from a named markdown section."""

    record_id: str
    cycle: str
    category: DigestCategory
    text: str
    source_path: str
    start_line: int
    end_line: int
    source_kind: SourceKind
    section: str
    raw_text: str = ""

    @property
    def source_span(self) -> tuple[int, int]:
        """Return the inclusive source line span."""
        return (self.start_line, self.end_line)

    @property
    def insight(self) -> str:
        """Expose the exact extracted passage for learning consumers."""
        return self.text


@dataclass(frozen=True, slots=True)
class DigestCuration:
    """L0 selection metadata; it cannot replace source record text."""

    record_ids: tuple[str, ...]
    labels: tuple[tuple[str, str], ...] = ()

    @classmethod
    def select(
        cls,
        record_ids: Iterable[str],
        labels: Iterable[tuple[str, str]] = (),
    ) -> DigestCuration:
        return cls(tuple(record_ids), tuple(labels))


@dataclass(frozen=True, slots=True)
class DigestResult:
    """The deterministic digest result and its explicit evidence status."""

    lessons: tuple[DigestRecord, ...] = ()
    benefits: tuple[DigestRecord, ...] = ()
    status: DigestStatus = "INSUFFICIENT"
    reason: str = ""

    @property
    def records(self) -> tuple[DigestRecord, ...]:
        """Return lessons followed by report-only benefits."""
        return self.lessons + self.benefits

    @property
    def insufficient(self) -> bool:
        return self.status == "INSUFFICIENT"


def classify_retro_digest_intent(message: str) -> RetroDigestVerdict:
    """Classify digest intent with requested > suggested > no-op priority."""
    if not message or not message.strip():
        return "NO_DIGEST"
    lowered = message.casefold()
    if any(trigger in lowered for trigger in _REQUESTED_TRIGGERS):
        return "DIGEST_REQUESTED"
    if any(trigger in lowered for trigger in _SUGGESTED_TRIGGERS):
        return "DIGEST_SUGGESTED"
    return "NO_DIGEST"


def _relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _cycle_for(path: str | Path) -> str:
    match = _CYCLE_RE.search(Path(path).name)
    if match is None:
        match = _CYCLE_RE.search(Path(path).as_posix())
    return match.group(0) if match else "unknown-cycle"


def _source_priority(source: RetrospectiveSource) -> tuple[int, str]:
    return (0 if source.path.startswith(".local/research/") else 1, source.path)


def _discover_sources(repo_root: Path, *, kind: SourceKind) -> tuple[RetrospectiveSource, ...]:
    if not repo_root.exists() or not repo_root.is_dir():
        raise FileNotFoundError(f"retro_digest: repo_root does not exist: {repo_root!s}")

    candidates: list[RetrospectiveSource] = []
    for base in (repo_root / ".local" / "research", repo_root / "docs" / "cycle-archive"):
        if not base.is_dir():
            continue
        marker = "evaluation" if kind == "evaluation" else "retrospective"
        for path in sorted(base.rglob("*.md")):
            if not path.is_file():
                continue
            if marker not in path.name.casefold():
                continue
            relative = _relative_path(repo_root, path)
            candidates.append(
                RetrospectiveSource(
                    cycle=_cycle_for(relative),
                    path=relative,
                    kind=kind,
                )
            )

    by_cycle: dict[str, RetrospectiveSource] = {}
    without_cycle: list[RetrospectiveSource] = []
    for source in candidates:
        if source.cycle == "unknown-cycle":
            without_cycle.append(source)
            continue
        previous = by_cycle.get(source.cycle)
        if previous is None or _source_priority(source) < _source_priority(previous):
            by_cycle[source.cycle] = source

    return tuple(sorted((*by_cycle.values(), *without_cycle), key=lambda source: source.path))


def discover_retrospectives(repo_root: Path) -> tuple[RetrospectiveSource, ...]:
    """Discover retrospective markdown with stable relative ordering.

    When both ``.local/research/<cycle>_retrospective.md`` and an archived
    copy exist, the current research source wins and only one record remains.
    """
    return _discover_sources(repo_root, kind="retrospective")


def discover_evaluations(repo_root: Path) -> tuple[RetrospectiveSource, ...]:
    """Discover evaluation markdown using the same current-source precedence."""
    return _discover_sources(repo_root, kind="evaluation")


def _normalise_heading(heading: str) -> str:
    return re.sub(r"[\s`*_:#—–-]+", " ", heading).strip().casefold()


def _is_section_heading(heading: str, *, category: DigestCategory) -> bool:
    normalised = _normalise_heading(heading)
    compact = normalised.replace(" ", "")
    if category == "lesson":
        return "key learnings" in normalised or "\u5173\u952e\u5b66\u4e60" in compact
    return (
        "findings closure" in normalised
        or normalised.startswith("findings")
        or "evaluation findings" in normalised
        or "\u8bc4\u4ef7\u53d1\u73b0" in compact
        or "\u53d1\u73b0\u95ed\u73af" in compact
    )


def _section_lines(markdown: str, *, category: DigestCategory) -> tuple[str, int, list[str]] | None:
    lines = markdown.splitlines()
    start = -1
    section_name = ""
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match and _is_section_heading(match.group(2), category=category):
            start = index
            section_name = match.group(2)
            break
    if start < 0:
        return None

    end = len(lines)
    heading_level = len(_HEADING_RE.match(lines[start]).group(1))  # type: ignore[union-attr]
    for index in range(start + 1, len(lines)):
        match = _HEADING_RE.match(lines[index])
        if match and len(match.group(1)) <= heading_level:
            end = index
            break
    return section_name, start + 1, lines[start + 1 : end]


def _extract_section(
    markdown: str,
    *,
    source_path: str,
    cycle: str | None,
    source_kind: SourceKind,
    category: DigestCategory,
) -> tuple[DigestRecord, ...]:
    located = _section_lines(markdown, category=category)
    if located is None:
        return ()
    section_name, first_line, lines = located
    resolved_path = Path(source_path).as_posix() if source_path else "<memory>"
    if resolved_path.startswith("/"):
        resolved_path = Path(resolved_path).name
    resolved_cycle = cycle or _cycle_for(resolved_path)
    records: list[DigestRecord] = []
    for offset, line in enumerate(lines):
        bullet = _BULLET_RE.match(line)
        is_table = line.strip().startswith("|") and line.strip().endswith("|")
        if bullet:
            text = bullet.group(1)
        elif is_table and not _TABLE_SEPARATOR_RE.match(line):
            text = line
        else:
            continue
        line_number = first_line + offset
        records.append(
            DigestRecord(
                record_id=f"{resolved_path}#L{line_number}",
                cycle=resolved_cycle,
                category=category,
                text=text,
                source_path=resolved_path,
                start_line=line_number,
                end_line=line_number,
                source_kind=source_kind,
                section=section_name,
                raw_text=line,
            )
        )
    return tuple(records)


def extract_retrospective_records(
    markdown: str,
    *,
    source_path: str = "",
    cycle: str | None = None,
) -> tuple[DigestRecord, ...]:
    """Extract exact bullet text from an English or Chinese learning section."""
    return _extract_section(
        markdown,
        source_path=source_path,
        cycle=cycle,
        source_kind="retrospective",
        category="lesson",
    )


def extract_evaluation_findings(
    markdown: str,
    *,
    source_path: str = "",
    cycle: str | None = None,
) -> tuple[DigestRecord, ...]:
    """Extract exact bullets/table rows from an evaluation findings section."""
    return _extract_section(
        markdown,
        source_path=source_path,
        cycle=cycle,
        source_kind="evaluation",
        category="benefit",
    )


def extract_digest_records(
    source: str | Path,
    *,
    source_path: str = "",
    cycle: str | None = None,
) -> tuple[DigestRecord, ...]:
    """Extract records from markdown text, a file, or a repository directory."""
    if isinstance(source, Path) and source.is_dir():
        return build_digest(source).records
    if isinstance(source, str) and not source_path and Path(source).is_dir():
        return build_digest(Path(source)).records
    if isinstance(source, Path):
        markdown = source.read_text(encoding="utf-8")
        source_path = source_path or source.name
    elif source_path or "\n" in source or source.lstrip().startswith("#"):
        markdown = source
    else:
        candidate = Path(source)
        if candidate.is_file():
            markdown = candidate.read_text(encoding="utf-8")
            source_path = source_path or candidate.name
        else:
            markdown = source

    if "evaluation" in source_path.casefold():
        return extract_evaluation_findings(markdown, source_path=source_path, cycle=cycle)
    return extract_retrospective_records(markdown, source_path=source_path, cycle=cycle)


def build_digest(repo_root: Path | str) -> DigestResult:
    """Read discovered sources and return a deterministic report-only result."""
    repo_root = Path(repo_root)
    retrospectives = discover_retrospectives(repo_root)
    evaluations = discover_evaluations(repo_root)
    lessons: list[DigestRecord] = []
    benefits: list[DigestRecord] = []
    for source in retrospectives:
        lessons.extend(
            extract_retrospective_records(
                (repo_root / source.path).read_text(encoding="utf-8"),
                source_path=source.path,
                cycle=source.cycle,
            )
        )
    for source in evaluations:
        benefits.extend(
            extract_evaluation_findings(
                (repo_root / source.path).read_text(encoding="utf-8"),
                source_path=source.path,
                cycle=source.cycle,
            )
        )
    ordered_lessons = tuple(sorted(lessons, key=lambda record: record.record_id))
    ordered_benefits = tuple(sorted(benefits, key=lambda record: record.record_id))
    records = ordered_lessons + ordered_benefits
    return DigestResult(
        lessons=ordered_lessons,
        benefits=ordered_benefits,
        status="OK" if records else "INSUFFICIENT",
        reason="" if records else "No supported retrospective or evaluation sections were found.",
    )


def _records_from(value: DigestResult | Iterable[DigestRecord]) -> tuple[DigestRecord, ...]:
    if isinstance(value, DigestResult):
        return value.records
    return tuple(value)


def _curated_records(
    records: tuple[DigestRecord, ...],
    curation: DigestCuration | Iterable[DigestRecord] | None,
) -> tuple[DigestRecord, ...]:
    if curation is None:
        return tuple(sorted(records, key=lambda record: record.record_id))
    if isinstance(curation, DigestCuration):
        selected_ids = curation.record_ids
    else:
        selected_ids = tuple(record.record_id for record in curation)
    by_id = {record.record_id: record for record in records}
    return tuple(by_id[record_id] for record_id in selected_ids if record_id in by_id)


def _stable_slug(text: str) -> str:
    slug = re.sub(r"[^\w]+", "-", text.casefold(), flags=re.UNICODE).strip("-")
    return slug[:80] or "record"


def to_learning_entries(
    digest: DigestResult | Iterable[DigestRecord],
    curation: DigestCuration | Iterable[DigestRecord] | None = None,
) -> tuple[Learning, ...]:
    """Convert selected lessons to immutable-at-source Learning payloads.

    Evaluation benefits are intentionally excluded: they are report-only
    evidence and must not become operational learnings.
    """
    records = _curated_records(_records_from(digest), curation)
    lessons = tuple(record for record in records if record.category == "lesson")
    seen_slugs: dict[tuple[str, str], int] = {}
    entries: list[Learning] = []
    curated_source = "retro-digest-curated" if curation is not None else "retro-digest"
    for record in lessons:
        base_slug = _stable_slug(record.text)
        slug_key = (record.cycle, base_slug)
        occurrence = seen_slugs.get(slug_key, 0) + 1
        seen_slugs[slug_key] = occurrence
        stable_slug = base_slug if occurrence == 1 else f"{base_slug}-{occurrence}"
        entries.append(
            Learning(
                stage="retro-digest",
                task_type="retro-digest",
                key=f"{record.cycle}:{stable_slug}",
                insight=record.text,
                confidence=0.9,
                ttl_days=90,
                confidence_half_life_days=DEFAULT_DECAY_HALF_LIFE_DAYS,
                source_task_id=record.record_id,
                files=[record.source_path],
                source=curated_source,
            )
        )
    return tuple(entries)


def render_digest_report(
    digest: DigestResult | Iterable[DigestRecord],
    curation: DigestCuration | Iterable[DigestRecord] | None = None,
) -> str:
    """Render stable markdown with separate lessons and report-only benefits."""
    records = _curated_records(_records_from(digest), curation)
    lessons = tuple(record for record in records if record.category == "lesson")
    benefits = tuple(record for record in records if record.category == "benefit")
    lines = ["# Retro-Digest", "", "## Lessons", ""]
    if lessons:
        for record in lessons:
            lines.append(f"- [{record.cycle}] {record.text}")
            lines.append(
                f"  - Source: `{record.source_path}#L{record.start_line}-L{record.end_line}`"
            )
    else:
        lines.append("INSUFFICIENT: no retrospective key-learning records found.")
    lines.extend(["", "## Benefits", ""])
    if benefits:
        for record in benefits:
            lines.append(f"- [{record.cycle}] {record.text}")
            lines.append(
                f"  - Source: `{record.source_path}#L{record.start_line}-L{record.end_line}`"
            )
    else:
        lines.append("INSUFFICIENT: no evaluation findings records found.")
    return "\n".join(lines) + "\n"


def capture_digest_entries(entries: Iterable[Learning], jsonl_path: Path) -> tuple[bool, ...]:
    """Explicitly persist digest entries through the existing capture API."""
    return tuple(capture_learning(entry, jsonl_path) for entry in entries)
