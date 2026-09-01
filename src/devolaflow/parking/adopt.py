"""Report-only adoption of a legacy risk-parking document (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §9.

The real-world artifact this domain replaces
(`.local/tasks/add_compact_and_new_files/sample-risk-parking.md`) mixes four
concerns in one file: a head blockquote restating every prior update, a
pending-decision zone, live risk rows, and closed rows. Adoption splits those
into the structured surfaces **additively** — the source file is never
modified or removed here, so adoption itself cannot lose anything. Compact
later relocates the original with a content hash.

Adoption is always previewed first: :func:`plan_adoption` reads and reports,
:func:`apply_adoption` writes only what an operator approved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from devolaflow.parking.models import ParkingError, RiskState, Severity
from devolaflow.parking.store import ParkingStore
from devolaflow.workspace_ledger import sha256_bytes

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|\s*$")
_LEGACY_ID_RE = re.compile(r"([A-Z]{1,4}-?[A-Za-z]?\d+[a-z′']?)")

#: Heading keyword → lifecycle state. The sample's four-zone layout is the
#: canonical case; English fallbacks cover documents that used the same
#: structure with translated headings.
_STATE_KEYWORDS: tuple[tuple[tuple[str, ...], RiskState], ...] = (
    (("§d", "归档", "archived"), RiskState.ARCHIVED),
    (("§c", "已闭合", "closed", "resolved"), RiskState.CLOSED),
    (("§b", "活跃", "active", "monitor"), RiskState.ACTIVE),
    (("§a", "未决", "pending", "open"), RiskState.OPEN),
)


@dataclass(frozen=True)
class AdoptionCandidate:
    """One legacy row proposed for adoption as a structured risk."""

    legacy_id: str
    title: str
    state: RiskState
    severity: Severity
    trigger: str
    disposition: str
    body: str
    section: str
    source_line: int


@dataclass(frozen=True)
class AdoptionPlan:
    """Report-only adoption proposal for one legacy document."""

    source: str
    source_sha256: str
    source_lines: int
    candidates: tuple[AdoptionCandidate, ...]
    preamble_lines: int
    unmapped_lines: int

    @property
    def short_sha(self) -> str:
        """Return the source digest prefix carried into each adopted risk."""

        return self.source_sha256[:12]

    @property
    def fingerprint(self) -> str:
        """Return a digest binding an approval to this exact proposal."""

        payload = "\n".join(
            f"{item.legacy_id}\x1f{item.state.value}\x1f{item.title}" for item in self.candidates
        )
        return sha256_bytes(f"{self.source_sha256}\x1e{payload}".encode())


def _state_for_heading(heading: str) -> RiskState | None:
    lowered = heading.lower()
    for keywords, state in _STATE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return state
    return None


def _split_row(line: str) -> list[str]:
    match = _TABLE_ROW_RE.match(line)
    if match is None:
        return []
    return [cell.strip() for cell in match.group(1).split("|")]


def _infer_severity(text: str) -> Severity:
    lowered = text.lower()
    if "blocker" in lowered or "阻断" in text or "🔴" in text:
        return Severity.BLOCKER
    if "critical" in lowered or "p0" in lowered:
        return Severity.CRITICAL
    if "minor" in lowered:
        return Severity.MINOR
    return Severity.MAJOR


def _legacy_id_from(cell: str, fallback: str) -> str:
    """Preserve the source identifier verbatim after stripping decoration.

    Verbatim matters: the sample keeps superseded rows as `~~PV-29-原文~~`
    beside the corrected `PV-29`. Reducing both to `PV-29` would fabricate a
    collision that the source does not have, and would lose the operator's
    own distinction between a row and its retained original.
    """

    stripped = re.sub(r"^[~*`\s]+|[~*`\s]+$", "", cell)
    if not stripped:
        return fallback
    if len(stripped) <= 40 and _LEGACY_ID_RE.search(stripped):
        return stripped
    match = _LEGACY_ID_RE.search(stripped)
    return match.group(1) if match else fallback


def _title_from(cells: list[str]) -> str:
    for cell in cells[1:]:
        text = re.sub(r"[*_`]", "", cell).strip()
        if text:
            # The first bolded clause is the risk statement; the rest is
            # evidence prose that belongs in the body, not the index line.
            first = re.split(r"[（(]|——|:|：", text, maxsplit=1)[0].strip()
            return first or text[:120]
    return "untitled risk"


def plan_adoption(source: str | Path, *, provenance: str | None = None) -> AdoptionPlan:
    """Parse a legacy document and report what adoption would create.

    ``provenance`` overrides the path recorded in each adopted risk. Callers
    that stage a copy (the trial replay, for instance) pass the original
    repository-relative path, because S-2 prohibits an absolute path leaking
    into an agent-facing artifact.
    """

    path = Path(source)
    if not path.is_file():
        raise ParkingError(f"adoption source is not a file: {source}")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines()

    candidates: list[AdoptionCandidate] = []
    section = ""
    state = RiskState.OPEN
    seen_heading = False
    preamble_lines = 0
    unmapped = 0
    in_table = False
    header_cells: list[str] = []

    for number, line in enumerate(lines, 1):
        heading = _HEADING_RE.match(line)
        if heading is not None:
            section = heading.group(2).strip()
            mapped = _state_for_heading(section)
            if mapped is not None:
                state = mapped
            seen_heading = True
            in_table = False
            continue
        if not seen_heading:
            preamble_lines += 1
            continue
        if _SEPARATOR_RE.match(line):
            in_table = True
            continue
        cells = _split_row(line)
        if not cells:
            in_table = False
            if line.strip():
                unmapped += 1
            continue
        if not in_table:
            header_cells = cells
            continue
        legacy_id = _legacy_id_from(cells[0], f"ROW-{number}")
        trigger = cells[2] if len(cells) > 2 else ""
        disposition = cells[3] if len(cells) > 3 else (cells[2] if len(cells) > 2 else "")
        title = _title_from(cells)
        # Only carry cells the frontmatter does not already hold. Duplicating
        # trigger and disposition into the body roughly doubled every adopted
        # file for no added information — measured in the v24 trial replay.
        promoted = {legacy_id, title, trigger, disposition}
        detail_cells = [
            f"**{header_cells[index] if index < len(header_cells) else f'col{index}'}**: {cell}"
            for index, cell in enumerate(cells)
            if cell and cell not in promoted
        ]
        candidates.append(
            AdoptionCandidate(
                legacy_id=legacy_id,
                title=title,
                state=state,
                severity=_infer_severity(" ".join(cells)),
                trigger=trigger,
                disposition=disposition,
                body="\n\n".join(detail_cells),
                section=section,
                source_line=number,
            )
        )

    return AdoptionPlan(
        source=provenance or _repo_relative(path),
        source_sha256=sha256_bytes(raw),
        source_lines=len(lines),
        candidates=tuple(candidates),
        preamble_lines=preamble_lines,
        unmapped_lines=unmapped,
    )


def apply_adoption(
    folder: str | Path,
    plan: AdoptionPlan,
    *,
    approval_fingerprint: str,
) -> tuple[str, ...]:
    """Create one structured risk per approved candidate; never delete input.

    Returns the created risk ids. Duplicate ``legacy_id`` values are refused
    rather than merged, because two rows carrying the same legacy identifier
    in the source means the source itself was ambiguous and a human has to
    say which one survives.
    """

    if approval_fingerprint != plan.fingerprint:
        raise ParkingError("approval fingerprint does not match the current adoption plan")
    store = ParkingStore(folder)
    store.scaffold()
    known = {risk.legacy_id for risk in store.list_risks() if risk.legacy_id}
    duplicates = [
        item.legacy_id
        for item in plan.candidates
        if item.legacy_id in known or _count(plan, item.legacy_id) > 1
    ]
    if duplicates:
        raise ParkingError(
            "adoption refuses ambiguous legacy ids: " + ", ".join(sorted(set(duplicates)))
        )
    created: list[str] = []
    for item in plan.candidates:
        provenance = f"_Adopted from `{plan.source}` L{item.source_line} (`{plan.short_sha}`)._\n"
        body = f"{item.body}\n\n{provenance}" if item.body else provenance
        risk = store.open_risk(
            item.title,
            severity=item.severity,
            trigger=item.trigger,
            disposition=item.disposition,
            body=body,
            legacy_id=item.legacy_id,
        )
        if item.state is not RiskState.OPEN:
            store.transition_risk(risk.id, item.state, reason="adopted at this state")
        created.append(risk.id)
    return tuple(created)


def _repo_relative(path: Path) -> str:
    """Render a path relative to the working directory when it lives inside."""

    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def _count(plan: AdoptionPlan, legacy_id: str) -> int:
    return sum(1 for item in plan.candidates if item.legacy_id == legacy_id)


__all__ = ["AdoptionCandidate", "AdoptionPlan", "apply_adoption", "plan_adoption"]
