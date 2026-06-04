"""REQ-ID → evidence traceability checker for the ``.local/human/`` surface.

Implements the per-REQ-row producer described in
``.local/research/v14.0.0_design.md`` §6c (finding F-2): the convergence
render consumes TWO distinct producers — this module supplies the per-REQ
``Result``/``Evidence`` rows (REQ-ID → acceptance evidence), while the
composite SI-3 gate supplies ONLY the ``Blocking``/``Advisory`` finding
sections via ``findings_by_severity``. The two surfaces are deliberately
separate because the gate does NOT key its evidence by REQ-ID.

This module joins ``requirements.md``'s ``## Traceability`` matrix (REQ-ID →
acceptance criterion + cycle + status, per design ADR-4) with the per-REQ
``Acceptance`` text from the ``### REQ-<DOMAIN>-NN`` blocks, yielding
``{REQ-ID → RequirementTraceResult(result, evidence, criterion, cycle)}``.

As of v14.1.0 the §9-roadmap **test-run-artifact join** is IMPLEMENTED: when
the caller supplies a ``test_results`` map (produced from a pytest
``--report-log`` JSONL via :func:`parse_pytest_report` plus the workflow's
HEAD commit), each REQ whose ``Acceptance`` text names a pytest node-id is
keyed off the *actual* PASS/FAIL outcome (``passed → met`` / ``failed →
unmet``) with verbatim evidence ``"<node_id> <PASS|FAIL> @ <commit>"`` (C-3).
When ``test_results`` is absent — or a REQ names no resolvable node-id — the
trace falls back to the matrix-``Status`` derivation (fully backward
compatible; the v14.0.0 callers stay byte-identical).

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
* :class:`TestOutcome` — frozen per-node-id pytest outcome (the §6c join input).
* :exc:`RequirementsTraceError` — raised on structurally-invalid input.
* :func:`trace_requirements` — ``requirements.md`` path → ``{REQ-ID → result}``.
* :func:`parse_pytest_report` — pytest ``--report-log`` JSONL → ``{node-id → TestOutcome}``.
* :data:`TRACE_RESULTS` — the canonical ``("met", "partial", "unmet")`` tuple.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "NO_EVIDENCE",
    "TRACE_RESULTS",
    "RequirementTraceResult",
    "RequirementsTraceError",
    "TestOutcome",
    "parse_pytest_report",
    "trace_requirements",
]


TRACE_RESULTS: Final[tuple[str, ...]] = ("met", "partial", "unmet")
"""Canonical trace-result vocabulary (matches the §4a convergence report)."""

NO_EVIDENCE: Final[str] = "no evidence"
"""S-5 sentinel: a REQ with no ``## Traceability`` row gets this evidence."""

_NO_ACCEPTANCE: Final[str] = "no acceptance criterion"
"""Fallback evidence when a matrixed REQ carries neither block nor matrix text."""

_MATRIX_ONLY_NOTE: Final[str] = "matrix row without REQ block"
"""S-5 (inverse) sentinel: a ``## Traceability`` row with NO ``### REQ-*`` block.

Such a row is structurally unbacked — there is no ``Acceptance`` criterion
block to confirm it — so it is mapped to ``result="unmet"`` (conservative,
never over-claiming) and surfaced with this note rather than silently
dropped. The matrix ``criterion`` / ``cycle`` cells are still preserved on
the row so the human report can show what the unbacked REQ was meant to be.
"""

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
# A pytest node-id named inside an ``Acceptance`` line — ``path/to/test.py``
# followed by ``::test_name`` (optionally parametrised ``[...]`` / nested
# ``::Class::method``). Character classes deliberately exclude the backtick
# and whitespace so a Markdown-quoted ``\`tests/foo.py::test_bar\``` matches
# exactly the node-id, stopping at the closing backtick.
_NODE_ID_RE: Final[re.Pattern[str]] = re.compile(r"[\w./-]+\.py::[\w\[\].:-]+")
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
    block's ``Acceptance`` text, falling back to the matrix criterion cell),
    the :data:`NO_EVIDENCE` sentinel when the REQ has no matrix row, or — when
    a §6c test-run join applies — the verbatim ``"<node_id> <PASS|FAIL> @
    <commit>"`` outcome string.

    ``criterion`` is the matrix ``Acceptance criterion`` cell (verbatim) and
    ``cycle`` is the matrix ``Cycle`` cell; both default to ``""`` so existing
    positional constructors stay valid (the two fields are appended last).
    """

    req_id: str
    result: str
    evidence: str
    criterion: str = ""
    cycle: str = ""


@dataclass(frozen=True)
class TestOutcome:
    """One pytest node-id → outcome record (the §6c test-run join input).

    ``node_id`` is the pytest node-id (e.g.
    ``tests/test_foo.py::test_bar``); ``outcome`` is the verbatim pytest
    outcome string (``"passed"`` / ``"failed"`` / ``"skipped"`` / ...);
    ``commit`` is the workflow HEAD commit hash captured by the caller (may
    be ``""`` when unavailable — the evidence string then omits the
    ``@ <commit>`` suffix).
    """

    # Tell pytest this is NOT a test class despite the ``Test`` name prefix
    # (it is a data record). Not a dataclass field (no annotation).
    __test__ = False

    node_id: str
    outcome: str
    commit: str = ""


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


def _parse_traceability_matrix(lines: list[str]) -> dict[str, tuple[str, str, str]]:
    """Return ``{REQ-ID: (status, criterion, cycle)}`` from the ``## Traceability`` matrix.

    Rows whose first REQ-shaped cell does not match the ``REQ-<DOMAIN>-NN``
    pattern (e.g. the ``**Unmapped**`` scope-reduction sentinel row) are
    skipped. Returns an empty mapping when no ``## Traceability`` section or
    no table is present (S-5: the caller then maps every REQ to ``unmet``).

    The ``Cycle`` column (when present) is captured so the §4b DIGEST can
    filter REQ deltas to the current cycle (finding F-3); an absent ``Cycle``
    column yields ``""`` per row (back-compat with pre-v14.1.0 matrices).
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
    cycle_idx = _find_col(header, "cycle")

    matrix: dict[str, tuple[str, str, str]] = {}
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
        cycle = ""
        if cycle_idx is not None and cycle_idx < len(cells):
            cycle = _clean_cell(cells[cycle_idx])
        matrix[req_id] = (status, criterion, cycle)

    return matrix


def _map_status(status: str) -> str:
    """Normalise a matrix Status string into a :data:`TRACE_RESULTS` value.

    Unknown / unrecognised statuses fall back to ``"unmet"`` — the
    conservative choice so a derived convergence report can never over-claim
    a REQ as ``met`` on an ambiguous status.
    """
    return _STATUS_TO_RESULT.get(status.strip().lower(), "unmet")


def _extract_node_id(text: str) -> str | None:
    """Return the first pytest node-id named in *text* (``None`` when absent).

    Matches a ``path/to/test.py::test_name`` token (see :data:`_NODE_ID_RE`).
    A bare file reference (no ``::``) is intentionally NOT a node-id and
    yields ``None`` — the §6c join then falls back to the matrix Status.
    """
    hit = _NODE_ID_RE.search(text or "")
    return hit.group(0) if hit else None


def _join_test_outcome(node_id: str, outcome: TestOutcome) -> tuple[str, str]:
    """Map a pytest :class:`TestOutcome` to a ``(result, evidence)`` pair.

    ``passed → met`` / anything-else → ``unmet`` (conservative; only an
    explicit pass confirms the REQ). Evidence is the verbatim C-3 string
    ``"<node_id> <LABEL> @ <commit>"`` where ``LABEL`` is ``PASS`` /
    ``FAIL`` for the two canonical outcomes (else the uppercased outcome).
    The ``@ <commit>`` suffix is omitted when no commit was captured.
    """
    label = {"passed": "PASS", "failed": "FAIL"}.get(outcome.outcome, outcome.outcome.upper())
    result = "met" if outcome.outcome == "passed" else "unmet"
    commit = outcome.commit.strip()
    suffix = f" @ {commit}" if commit else ""
    return result, f"{node_id} {label}{suffix}"


def parse_pytest_report(
    report_path: Path | str,
    *,
    commit: str = "",
) -> dict[str, TestOutcome]:
    """Parse a pytest ``--report-log`` JSONL into ``{node-id: TestOutcome}``.

    The pytest ``--report-log`` plugin emits one JSON object per line; this
    reader keeps the ``TestReport`` records of the ``call`` phase (the phase
    that carries the real pass/fail outcome — ``setup`` / ``teardown`` phases
    are skipped) and records ``{nodeid: TestOutcome(nodeid, outcome, commit)}``.
    The optional ``commit`` is the workflow HEAD hash the caller captured; it
    is stamped onto every outcome so the downstream evidence string can quote
    it verbatim (C-3).

    Args:
      report_path: path to the ``--report-log`` JSONL file.
      commit: HEAD commit hash to stamp on every outcome (default ``""``).

    Returns:
      ``{node-id: TestOutcome}`` for every ``call``-phase ``TestReport``.

    Raises:
      FileNotFoundError: when *report_path* does not exist (S-5: loud).
      RequirementsTraceError: when *report_path* is not path-like, or a line
        is not valid JSON (S-5: a malformed report is never silently
        partially-parsed).
    """
    if report_path is None:
        raise RequirementsTraceError("report_path must not be None")
    try:
        path = Path(report_path)
    except TypeError as exc:
        raise RequirementsTraceError(
            f"report_path must be path-like, got {type(report_path).__name__}"
        ) from exc
    if not path.exists():
        raise FileNotFoundError(f"pytest report-log not found: {path}")

    outcomes: dict[str, TestOutcome] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RequirementsTraceError(
                f"malformed report-log JSON at line {lineno} of {path}: {exc}"
            ) from exc
        if not isinstance(obj, dict):
            continue
        if obj.get("$report_type") != "TestReport" or obj.get("when") != "call":
            continue
        node_id = obj.get("nodeid")
        outcome = obj.get("outcome")
        if not node_id or not outcome:
            continue
        outcomes[str(node_id)] = TestOutcome(
            node_id=str(node_id), outcome=str(outcome), commit=commit
        )
    return outcomes


def trace_requirements(
    requirements_path: Path | str,
    *,
    test_results: Mapping[str, TestOutcome] | None = None,
) -> dict[str, RequirementTraceResult]:
    """Trace every REQ in *requirements_path* to evidence (design §6c).

    Parses the ``### REQ-*`` blocks and the ``## Traceability`` matrix of a
    ``.local/human/input/requirements.md`` file (design §3b). The returned
    mapping is keyed by the **union** of every ``### REQ-*`` block AND every
    ``## Traceability`` matrix row — so no REQ is ever silently dropped in
    EITHER direction (S-5, both ways):

    * **block + matrix row** — ``result`` derives from the matrix ``Status``
      cell (``Satisfied → met``, ``Pending → partial``, ``Blocked → unmet``;
      unknown → ``unmet``); ``evidence`` is the block ``Acceptance`` text
      (verbatim C-3), falling back to the matrix criterion. When
      ``test_results`` is supplied AND the ``Acceptance`` text names a pytest
      node-id present in the map, the §6c test-run join overrides both:
      ``passed → met`` / else ``unmet`` with verbatim ``"<node_id> <PASS|
      FAIL> @ <commit>"`` evidence.
    * **block, NO matrix row** — ``result="unmet"``, ``evidence="no
      evidence"`` (the forward S-5 case; unchanged from v14.0.0).
    * **matrix row, NO block** — ``result="unmet"``, evidence
      :data:`_MATRIX_ONLY_NOTE` (the inverse S-5 case, NEW in v14.1.0: a
      structurally-unbacked matrix row is surfaced, never dropped). The
      matrix ``criterion`` / ``cycle`` cells are preserved on the row.

    Args:
      requirements_path: Path to a ``requirements.md`` (or per-domain shard).
      test_results: optional ``{node-id: TestOutcome}`` map (typically the
        :func:`parse_pytest_report` output). When ``None`` the trace is
        purely matrix-derived (backward compatible).

    Returns:
      ``{REQ-ID: RequirementTraceResult}`` keyed by the block ∪ matrix REQ
      set (block order first, then matrix-only rows in matrix order).

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

    # Union the two producers (block order first, then matrix-only rows) so a
    # REQ present in EITHER surface emits exactly one row.
    ordered_ids = list(acceptance.keys())
    ordered_ids.extend(req_id for req_id in matrix if req_id not in acceptance)

    results: dict[str, RequirementTraceResult] = {}
    for req_id in ordered_ids:
        status, criterion, cycle = matrix.get(req_id, ("", "", ""))
        criterion = criterion.strip()
        cycle = cycle.strip()

        if req_id not in matrix:
            # block, no matrix row — forward S-5 (unchanged).
            results[req_id] = RequirementTraceResult(
                req_id=req_id, result="unmet", evidence=NO_EVIDENCE
            )
            continue
        if req_id not in acceptance:
            # matrix row, no block — inverse S-5 (NEW): conservative unmet.
            results[req_id] = RequirementTraceResult(
                req_id=req_id,
                result="unmet",
                evidence=_MATRIX_ONLY_NOTE,
                criterion=criterion,
                cycle=cycle,
            )
            continue

        accept_text = acceptance[req_id]
        result = _map_status(status)
        evidence = accept_text.strip() or criterion or _NO_ACCEPTANCE

        if test_results:
            node_id = _extract_node_id(accept_text)
            if node_id and node_id in test_results:
                result, evidence = _join_test_outcome(node_id, test_results[node_id])

        results[req_id] = RequirementTraceResult(
            req_id=req_id,
            result=result,
            evidence=evidence,
            criterion=criterion,
            cycle=cycle,
        )

    return results
