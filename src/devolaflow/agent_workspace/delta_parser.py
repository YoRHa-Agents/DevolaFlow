"""Delta-spec parser for ``.local/.agent/active/<id>/spec.md`` (OpenSpec format).

Closes M-003 (Python half) per ``.local/research/v8.3.0_gap_analysis.md`` §2.3.
The schema is declared verbatim in ``schemas/agent-workspace/change-spec.yaml``
(landed v8.2.4 PV-04); this module is the runtime parser that consumes it.

OpenSpec delta sections — at least ONE of the three MUST be present:

* ``## ADDED Requirements``    — new requirements introduced by this change
* ``## MODIFIED Requirements`` — existing requirements whose body changes
* ``## REMOVED Requirements``  — requirements deprecated/removed by this change

Each section contains zero or more ``### Requirement: <Stable heading>`` items.
The body of a Requirement runs from its ``### Requirement:`` line to either
the next ``### Requirement:`` or the next ``## `` H2 boundary.

Round-trip semantics (``parse_delta_spec`` → ``serialize_delta_spec``):

* Stable-heading-keyed; matching headings round-trip byte-identically modulo
  trailing whitespace normalisation.
* Body text is preserved verbatim within each Requirement block.
* Sections are emitted in the canonical order ADDED / MODIFIED / REMOVED
  (matching ``schemas/agent-workspace/change-spec.yaml#delta_sections.canonical_order``).

Public API:

* :class:`DeltaSpec` — parsed delta-spec dataclass (frontmatter + sections).
* :class:`DeltaRequirement` — one ``### Requirement:`` block within a section.
* :exc:`DeltaSpecParseError` — raised when the spec violates the schema
  (no delta sections / malformed frontmatter / illegal heading).
* :func:`parse_delta_spec` — text → :class:`DeltaSpec`.
* :func:`serialize_delta_spec` — :class:`DeltaSpec` → text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

import yaml

__all__ = [
    "DELTA_SECTION_KINDS",
    "DeltaRequirement",
    "DeltaSpec",
    "DeltaSpecParseError",
    "parse_delta_spec",
    "serialize_delta_spec",
]


DELTA_SECTION_KINDS: Final[tuple[str, ...]] = ("ADDED", "MODIFIED", "REMOVED")
"""Canonical order — matches ``schemas/agent-workspace/change-spec.yaml``."""


_FRONTMATTER_DELIM: Final[str] = "---"
_DELTA_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^## (ADDED|MODIFIED|REMOVED) Requirements\s*$"
)
_REQUIREMENT_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^### Requirement: (.+?)\s*$")
_H1_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^# .+$")
_H2_BOUNDARY_RE: Final[re.Pattern[str]] = re.compile(r"^## .+$")
_PURPOSE_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^## Purpose\s*$")


class DeltaSpecParseError(ValueError):
    """Raised when a ``spec.md`` violates the v8.2.4 change-spec schema.

    The error message identifies the offending line / section so the caller
    can surface it to the L3 task agent (loud per S-5; never silent).
    """


@dataclass
class DeltaRequirement:
    """One ``### Requirement: <Stable heading>`` block inside a delta section.

    ``heading`` is the stable identity used for delta merging at archive
    time (per A-4 ADR — MODIFIED/REMOVED match against the source-of-truth
    by exact heading text). ``body`` is the verbatim block content from the
    line AFTER ``### Requirement: <heading>`` up to the next requirement /
    section boundary; trailing blank lines are stripped.
    """

    heading: str
    body: str = ""

    def render(self) -> str:
        """Render this Requirement as Markdown (matches the parser's input)."""
        line = f"### Requirement: {self.heading}"
        if not self.body:
            return line + "\n"
        return f"{line}\n{self.body}\n"


@dataclass
class DeltaSpec:
    """Parsed ``spec.md`` representation.

    Mirrors the ``schemas/agent-workspace/change-spec.yaml`` body contract:
    YAML frontmatter (``parent`` / ``delta_target`` / ``delta_kind``) +
    H1 title + ``## Purpose`` + at least one of the three delta sections
    (ADDED / MODIFIED / REMOVED).

    Attributes carry the parsed values verbatim (no normalisation beyond
    whitespace trimming on headings).
    """

    frontmatter: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    title: str = ""
    purpose: str = ""
    added: list[DeltaRequirement] = field(default_factory=list)
    modified: list[DeltaRequirement] = field(default_factory=list)
    removed: list[DeltaRequirement] = field(default_factory=list)

    def section(self, kind: str) -> list[DeltaRequirement]:
        """Return the section list for ``kind`` (``"ADDED"`` etc.).

        Raises :class:`KeyError` for unknown kinds (caller bug, not a
        spec error — bare exception is intentional per S-5).
        """
        kind_upper = kind.upper()
        if kind_upper == "ADDED":
            return self.added
        if kind_upper == "MODIFIED":
            return self.modified
        if kind_upper == "REMOVED":
            return self.removed
        raise KeyError(
            f"unknown delta section kind {kind!r}; expected one of {DELTA_SECTION_KINDS}"
        )

    def has_any_delta(self) -> bool:
        """True if at least one of ADDED / MODIFIED / REMOVED is non-empty.

        The schema mandates ``at_least_one_required: true``; the parser
        enforces this as a hard error, but downstream consumers (e.g.
        ``ArchiveManager.propose_merge``) may want to re-check.
        """
        return bool(self.added or self.modified or self.removed)

    def all_requirements(self) -> list[tuple[str, DeltaRequirement]]:
        """Flatten every Requirement across all three sections.

        Returns a list of ``(kind, requirement)`` tuples in canonical
        ADDED → MODIFIED → REMOVED order. Useful for round-trip and
        merge-conflict reporting.
        """
        flat: list[tuple[str, DeltaRequirement]] = []
        for kind in DELTA_SECTION_KINDS:
            for req in self.section(kind):
                flat.append((kind, req))
        return flat


def _split_frontmatter(text: str) -> tuple[dict, list[str]]:
    """Strip the YAML frontmatter and return ``(frontmatter_dict, body_lines)``.

    Frontmatter MUST be delimited by exactly two ``---`` lines at the very
    top of the file (lines 1 and N). The first line is ``---``; everything
    up to (and excluding) the next ``---`` line is YAML body. Lines after
    the closing ``---`` form the markdown body.

    Returns ``({}, lines)`` if the file does NOT start with a frontmatter
    delimiter — frontmatter is REQUIRED by the schema, but we surface
    that via a separate validation step rather than crashing here so the
    caller gets a structured error.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return {}, lines

    try:
        close_idx = next(
            i for i, line in enumerate(lines[1:], start=1) if line.strip() == _FRONTMATTER_DELIM
        )
    except StopIteration as exc:
        raise DeltaSpecParseError(
            "frontmatter opens with `---` but never closes; "
            "every spec.md MUST have a closing `---` line "
            "(see schemas/agent-workspace/change-spec.yaml)"
        ) from exc

    fm_text = "\n".join(lines[1:close_idx])
    parsed = yaml.safe_load(fm_text) if fm_text.strip() else {}
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise DeltaSpecParseError(
            f"frontmatter must parse as a YAML mapping; got {type(parsed).__name__}"
        )
    body = lines[close_idx + 1 :]
    # Drop a single leading blank line if present (cosmetic).
    if body and body[0].strip() == "":
        body = body[1:]
    return parsed, body


def _slice_section_bodies(
    body_lines: list[str],
) -> tuple[
    str,
    str,
    dict[str, list[str]],
]:
    """Return ``(title, purpose, sections)`` from the markdown body.

    ``sections`` maps each delta-section kind found in the body to the
    raw line list between its ``## <KIND> Requirements`` heading and the
    next ``## `` H2 boundary (or EOF). Intermediate blank lines are
    preserved so the per-Requirement parser can re-establish boundaries.
    """
    title = ""
    purpose_lines: list[str] = []
    sections: dict[str, list[str]] = {}

    cursor = 0
    n = len(body_lines)

    # H1 title — first non-blank line MUST be `# Operation Spec for <change-id>`
    while cursor < n and not body_lines[cursor].strip():
        cursor += 1
    if cursor < n and _H1_HEADING_RE.match(body_lines[cursor]):
        title = body_lines[cursor].lstrip("# ").strip()
        cursor += 1

    while cursor < n:
        line = body_lines[cursor]
        stripped = line.strip()

        if _PURPOSE_HEADING_RE.match(line):
            cursor += 1
            collected: list[str] = []
            while cursor < n and not _H2_BOUNDARY_RE.match(body_lines[cursor]):
                collected.append(body_lines[cursor])
                cursor += 1
            purpose_lines = collected
            continue

        match = _DELTA_HEADING_RE.match(line)
        if match:
            kind = match.group(1)
            cursor += 1
            collected = []
            while cursor < n and not _H2_BOUNDARY_RE.match(body_lines[cursor]):
                collected.append(body_lines[cursor])
                cursor += 1
            sections[kind] = collected
            continue

        if not stripped:
            cursor += 1
            continue

        # Unknown H2 — skip its body so we keep advancing.
        if _H2_BOUNDARY_RE.match(line):
            cursor += 1
            while cursor < n and not _H2_BOUNDARY_RE.match(body_lines[cursor]):
                cursor += 1
            continue

        cursor += 1

    purpose_text = _strip_trailing_blank_lines(purpose_lines)
    return title, purpose_text, sections


def _parse_section_requirements(section_lines: list[str]) -> list[DeltaRequirement]:
    """Parse a list of lines from inside one delta section into Requirements."""
    requirements: list[DeltaRequirement] = []
    cursor = 0
    n = len(section_lines)

    while cursor < n and not _REQUIREMENT_HEADING_RE.match(section_lines[cursor]):
        # Tolerate (and ignore) free-floating prose between the H2 heading
        # and the first ### Requirement: line — typically a "(None — this
        # PV is purely additive.)" note. The schema declares the section
        # as a list of `### Requirement:` items; non-Requirement prose is
        # preserved through round-trip but not surfaced via the API.
        cursor += 1

    while cursor < n:
        match = _REQUIREMENT_HEADING_RE.match(section_lines[cursor])
        if not match:
            cursor += 1
            continue

        heading = match.group(1).strip()
        cursor += 1
        body_lines: list[str] = []
        while cursor < n and not _REQUIREMENT_HEADING_RE.match(section_lines[cursor]):
            body_lines.append(section_lines[cursor])
            cursor += 1
        requirements.append(
            DeltaRequirement(heading=heading, body=_strip_trailing_blank_lines(body_lines))
        )

    return requirements


def _strip_trailing_blank_lines(lines: list[str]) -> str:
    """Join ``lines`` with newlines and strip trailing blank lines."""
    text = "\n".join(lines)
    return text.rstrip("\n").rstrip()


def parse_delta_spec(spec_md_text: str) -> DeltaSpec:
    """Parse an OpenSpec-style ``spec.md`` into a :class:`DeltaSpec`.

    Per ``schemas/agent-workspace/change-spec.yaml``:

    * Frontmatter is REQUIRED; missing or malformed frontmatter raises
      :class:`DeltaSpecParseError`.
    * At least one of ``## ADDED Requirements`` / ``## MODIFIED
      Requirements`` / ``## REMOVED Requirements`` MUST be present
      with at least one ``### Requirement:`` block.
    * Headings are matched against the verbatim patterns in the schema
      (capitalisation MUST match; trailing punctuation forbidden).

    Args:
      spec_md_text: Raw markdown text (with frontmatter) of a per-change
        ``spec.md`` instance.

    Returns:
      :class:`DeltaSpec` with ``frontmatter`` / ``title`` / ``purpose`` /
      ``added`` / ``modified`` / ``removed`` populated.

    Raises:
      DeltaSpecParseError: when the spec violates the schema. The error
        message identifies the offending construct.
    """
    if not isinstance(spec_md_text, str):
        raise DeltaSpecParseError(f"spec_md_text must be a str, got {type(spec_md_text).__name__}")

    frontmatter, body_lines = _split_frontmatter(spec_md_text)
    title, purpose, raw_sections = _slice_section_bodies(body_lines)

    spec = DeltaSpec(frontmatter=frontmatter, title=title, purpose=purpose)
    for kind in DELTA_SECTION_KINDS:
        if kind in raw_sections:
            requirements = _parse_section_requirements(raw_sections[kind])
            spec.section(kind).extend(requirements)

    if not spec.has_any_delta():
        raise DeltaSpecParseError(
            "spec.md MUST contain at least one of `## ADDED Requirements`, "
            "`## MODIFIED Requirements`, or `## REMOVED Requirements` with "
            "at least one `### Requirement:` block "
            "(see schemas/agent-workspace/change-spec.yaml#delta_sections)"
        )

    return spec


def serialize_delta_spec(spec: DeltaSpec) -> str:
    """Serialise a :class:`DeltaSpec` back to Markdown text.

    The output ROUND-TRIPS through :func:`parse_delta_spec` byte-identically
    modulo whitespace normalisation (trailing blanks stripped from
    Requirement bodies and from the ``Purpose`` block, single newline at
    EOF). Sections are emitted in the canonical ADDED / MODIFIED / REMOVED
    order; only sections with at least one Requirement are emitted.
    """
    parts: list[str] = []

    if spec.frontmatter:
        # ``yaml.safe_dump`` defaults sort keys alphabetically; pin to the
        # insertion order from the source dataclass for round-trip stability.
        fm_text = yaml.safe_dump(spec.frontmatter, sort_keys=False).strip()
        parts.append(_FRONTMATTER_DELIM)
        parts.append(fm_text)
        parts.append(_FRONTMATTER_DELIM)
        parts.append("")

    if spec.title:
        parts.append(f"# {spec.title}")
        parts.append("")

    if spec.purpose:
        parts.append("## Purpose")
        parts.append(spec.purpose)
        parts.append("")

    for kind in DELTA_SECTION_KINDS:
        section = spec.section(kind)
        if not section:
            continue
        parts.append(f"## {kind} Requirements")
        parts.append("")
        for req in section:
            parts.append(f"### Requirement: {req.heading}")
            if req.body:
                parts.append(req.body)
            parts.append("")

    text = "\n".join(parts).rstrip("\n") + "\n"
    return text
