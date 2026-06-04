"""REQ-ID → evidence traceability checker for the ``.local/human/`` surface.

Implements the per-REQ-row producer described in
``.local/research/v14.0.0_design.md`` §6c (finding F-2): the convergence
render consumes TWO distinct producers — this module supplies the per-REQ
``Result``/``Evidence`` rows (REQ-ID → acceptance evidence), while the
composite SI-3 gate supplies ONLY the ``Blocking``/``Advisory`` finding
sections via ``findings_by_severity``. The two surfaces are deliberately
separate because the gate does NOT key its evidence by REQ-ID.

This Wave-3 slice is the PURE, file-only half of F-2: it joins
``requirements.md``'s ``## Traceability`` matrix (REQ-ID → acceptance
criterion + status, per design ADR-4) with the per-REQ ``Acceptance`` text
from the ``### REQ-<DOMAIN>-NN`` blocks, yielding
``{REQ-ID → RequirementTraceResult(result, evidence)}``. The future
test-run-artifact join (pytest node-id + PASS/FAIL + commit hash) layers on
top of this map in a later cycle (§9 roadmap) and is intentionally out of
scope here.

Design invariants honoured:

* **C-3 verbatim extraction.** Evidence strings are taken verbatim from the
  source ``Acceptance`` text (or the matrix criterion cell); never
  paraphrased.
* **S-5 no silent failure.** A REQ block with NO matching ``## Traceability``
  row is mapped to ``result="unmet", evidence="no evidence"`` — it is NEVER
  silently dropped from the returned mapping. A missing requirements file
  raises :class:`FileNotFoundError`; an invalid path type raises the typed
  :class:`RequirementsTraceError`.
* The ``Lifecycle`` / ``Status`` distinction (design §3c, finding F-1) is
  respected: this trace keys ``result`` off the *matrix Status*, never off a
  block's ``Lifecycle`` field (which governs append-only immutability, not
  satisfaction progress — see :mod:`devolaflow.lifecycle.check_human_input_append_only`).

Public API:

* :class:`RequirementTraceResult` — frozen per-REQ trace row.
* :exc:`RequirementsTraceError` — raised on structurally-invalid input.
* :func:`trace_requirements` — ``requirements.md`` path → ``{REQ-ID → result}``.
* :data:`TRACE_RESULTS` — the canonical ``("met", "partial", "unmet")`` tuple.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "NO_EVIDENCE",
    "TRACE_RESULTS",
    "RequirementTraceResult",
    "RequirementsTraceError",
    "trace_requirements",
]


TRACE_RESULTS: Final[tuple[str, ...]] = ("met", "partial", "unmet")
"""Canonical trace-result vocabulary (matches the §4a convergence report)."""

NO_EVIDENCE: Final[str] = "no evidence"
"""S-5 sentinel: a REQ with no ``## Traceability`` row gets this evidence."""

_NO_ACCEPTANCE: Final[str] = "no acceptance criterion"
"""Fallback evidence when a matrixed REQ carries neither block nor matrix text."""

# Matrix Status (requirements.md uses Pending/Satisfied/Blocked) — and the
# convergence-report vocabulary (met/partial/unmet) — both normalise into the
# canonical TRACE_RESULTS. Unknown statuses fall back to ``unmet`` (conservative
# — design principle 5 "a report cannot over-claim"; see ``_map_status``).
_STATUS_TO_RESULT: Final[dict[str, str]] = {
    "satisfied": "met",
    "met": "met",
    "pending": "partial",
    "partial": "partial",
    "blocked": "unmet",
    "unmet": "unmet",
}

_REQ_ID_RE: Final[re.Pattern[str]] = re.compile(r"REQ-[A-Z0-9]+-\d+")
_REQ_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^###\s+(REQ-[A-Z0-9]+-\d+)\s*:\s*(.*?)\s*$")
_ACCEPTANCE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*-\s*\*\*Acceptance:\*\*\s*(.*?)\s*$")
_H2_BOUNDARY_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+.+$")
_TRACEABILITY_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Traceability\s*$")
_TABLE_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


class RequirementsTraceError(ValueError):
    """Raised when the ``requirements.md`` input is structurally unusable.

    Distinct from :class:`FileNotFoundError` (missing file): this error
    flags a caller bug such as a ``None`` / non-path-like argument. Both
    are loud per S-5 — the trace NEVER returns a partial result on a
    malformed request.
    """


@dataclass(frozen=True)
class RequirementTraceResult:
    """One REQ-ID → (result, evidence) trace row (immutable per C-3/P5).

    ``result`` is one of :data:`TRACE_RESULTS` (``"met"`` / ``"partial"`` /
    ``"unmet"``). ``evidence`` is a verbatim acceptance string (the REQ
    block's ``Acceptance`` text, falling back to the matrix criterion cell)
    or the :data:`NO_EVIDENCE` sentinel when the REQ has no matrix row.
    """

    req_id: str
    result: str
    evidence: str


def _is_continuation(line: str) -> bool:
    """True if *line* continues the previous ``- **Field:**`` bullet value.

    A continuation is a non-blank, indented line that does not itself start
    a new list bullet — e.g. the wrapped second line of a long ``Acceptance``
    value in the design §8a worked example.
    """
    if not line.strip():
        return False
    if not line[:1].isspace():
        return False
    return not line.lstrip().startswith("- ")


def _parse_req_blocks(lines: list[str]) -> dict[str, str]:
    """Return ``{REQ-ID: acceptance_text}`` for every ``### REQ-*`` block.

    Acceptance values that wrap across indented continuation lines are
    re-joined with a single space (verbatim text preserved per C-3). A REQ
    block with no ``Acceptance`` field maps to an empty string.
    """
    acceptance: dict[str, str] = {}
    cursor = 0
    n = len(lines)

    while cursor < n:
        heading = _REQ_HEADING_RE.match(lines[cursor])
        if not heading:
            cursor += 1
            continue

        req_id = heading.group(1)
        cursor += 1
        value = ""
        while (
            cursor < n
            and not _REQ_HEADING_RE.match(lines[cursor])
            and not _H2_BOUNDARY_RE.match(lines[cursor])
        ):
            field = _ACCEPTANCE_RE.match(lines[cursor])
            if field:
                parts = [field.group(1).strip()]
                cursor += 1
                while cursor < n and _is_continuation(lines[cursor]):
                    parts.append(lines[cursor].strip())
                    cursor += 1
                value = " ".join(part for part in parts if part)
                continue
            cursor += 1

        acceptance[req_id] = value

    return acceptance


def _split_row(row: str) -> list[str]:
    """Split a markdown table row on ``|`` into trimmed cells (no edge pipes)."""
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _clean_cell(cell: str) -> str:
    """Strip markdown bold markers and surrounding whitespace from a cell."""
    return cell.replace("**", "").strip()


def _find_col(header_cells: list[str], name: str) -> int | None:
    """Return the index of the header cell equal to *name* (case-insensitive)."""
    for idx, cell in enumerate(header_cells):
        if _clean_cell(cell).lower() == name:
            return idx
    return None


def _parse_traceability_matrix(lines: list[str]) -> dict[str, tuple[str, str]]:
    """Return ``{REQ-ID: (status, criterion)}`` from the ``## Traceability`` matrix.

    Rows whose first REQ-shaped cell does not match the ``REQ-<DOMAIN>-NN``
    pattern (e.g. the ``**Unmapped**`` scope-reduction sentinel row) are
    skipped. Returns an empty mapping when no ``## Traceability`` section or
    no table is present (S-5: the caller then maps every REQ to ``unmet``).
    """
    start: int | None = None
    for idx, line in enumerate(lines):
        if _TRACEABILITY_RE.match(line):
            start = idx + 1
            break
    if start is None:
        return {}

    end = start
    while end < len(lines) and not _H2_BOUNDARY_RE.match(lines[end]):
        end += 1

    table_lines = [line for line in lines[start:end] if _TABLE_ROW_RE.match(line)]
    if len(table_lines) < 2:
        return {}

    header = _split_row(table_lines[0])
    status_idx = _find_col(header, "status")
    criterion_idx = _find_col(header, "acceptance criterion")

    matrix: dict[str, tuple[str, str]] = {}
    for row in table_lines[1:]:
        if _TABLE_SEP_RE.match(row):
            continue
        cells = _split_row(row)
        req_id: str | None = None
        for cell in cells:
            hit = _REQ_ID_RE.search(cell)
            if hit:
                req_id = hit.group(0)
                break
        if req_id is None:
            continue
        status = ""
        if status_idx is not None and status_idx < len(cells):
            status = _clean_cell(cells[status_idx])
        elif cells:
            status = _clean_cell(cells[-1])
        criterion = ""
        if criterion_idx is not None and criterion_idx < len(cells):
            criterion = _clean_cell(cells[criterion_idx])
        matrix[req_id] = (status, criterion)

    return matrix


def _map_status(status: str) -> str:
    """Normalise a matrix Status string into a :data:`TRACE_RESULTS` value.

    Unknown / unrecognised statuses fall back to ``"unmet"`` — the
    conservative choice so a derived convergence report can never over-claim
    a REQ as ``met`` on an ambiguous status.
    """
    return _STATUS_TO_RESULT.get(status.strip().lower(), "unmet")


def trace_requirements(requirements_path: Path) -> dict[str, RequirementTraceResult]:
    """Trace every ``### REQ-<DOMAIN>-NN`` in *requirements_path* to evidence.

    Parses the ``### REQ-*`` blocks and the ``## Traceability`` matrix of a
    ``.local/human/input/requirements.md`` file (design §3b) and maps each
    REQ-ID to a :class:`RequirementTraceResult`:

    * The ``result`` is derived from the REQ's ``## Traceability`` row
      ``Status`` cell (``Satisfied → met``, ``Pending → partial``,
      ``Blocked → unmet``; unknown → ``unmet``).
    * The ``evidence`` is the REQ block's ``Acceptance`` text (verbatim per
      C-3), falling back to the matrix's ``Acceptance criterion`` cell.
    * A REQ block with NO matrix row maps to ``result="unmet"``,
      ``evidence="no evidence"`` (S-5: never silently dropped).

    Args:
      requirements_path: Path to a ``requirements.md`` (or per-domain shard).

    Returns:
      ``{REQ-ID: RequirementTraceResult}`` keyed by every ``### REQ-*`` block
      found in the file (insertion order preserved).

    Raises:
      FileNotFoundError: when *requirements_path* does not exist (no silent
        failure per S-5).
      RequirementsTraceError: when *requirements_path* is ``None`` or not a
        path-like value.
    """
    if requirements_path is None:
        raise RequirementsTraceError("requirements_path must not be None")
    try:
        path = Path(requirements_path)
    except TypeError as exc:
        raise RequirementsTraceError(
            f"requirements_path must be path-like, got {type(requirements_path).__name__}"
        ) from exc

    if not path.exists():
        raise FileNotFoundError(f"requirements file not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    acceptance = _parse_req_blocks(lines)
    matrix = _parse_traceability_matrix(lines)

    results: dict[str, RequirementTraceResult] = {}
    for req_id, accept_text in acceptance.items():
        if req_id not in matrix:
            results[req_id] = RequirementTraceResult(
                req_id=req_id, result="unmet", evidence=NO_EVIDENCE
            )
            continue
        status, criterion = matrix[req_id]
        evidence = accept_text.strip() or criterion.strip() or _NO_ACCEPTANCE
        results[req_id] = RequirementTraceResult(
            req_id=req_id, result=_map_status(status), evidence=evidence
        )

    return results
