"""Tests for ``devolaflow.agent_workspace.requirements_trace`` (v14.0.0 Wave-3).

Covers the pure REQ-ID → evidence trace described in
``.local/research/v14.0.0_design.md`` §6c (finding F-2):

* Matrix ``Status`` maps to the convergence ``result`` vocabulary
  (``Satisfied → met`` / ``Pending → partial`` / ``Blocked → unmet``;
  unknown → ``unmet``).
* Evidence is the REQ block's ``Acceptance`` text, verbatim per C-3.
* A REQ block with NO ``## Traceability`` row maps to
  ``result="unmet", evidence="no evidence"`` (S-5 — never silently dropped).
* A missing file raises :class:`FileNotFoundError`; a ``None`` path raises
  the typed :class:`RequirementsTraceError`.
* :class:`RequirementTraceResult` is frozen (immutable trace row).

The sample requirements.md mirrors the design §8a worked example (a
``Lifecycle: RATIFIED`` REQ with ``Status: Pending`` exercises the F-1
Lifecycle-vs-Status distinction — the trace keys off the matrix Status,
never the block Lifecycle).
"""

from __future__ import annotations

import dataclasses
import json
import textwrap
from pathlib import Path

import pytest

from devolaflow.agent_workspace import (
    RequirementsTraceError,
    RequirementTraceResult,
    TestOutcome,
    parse_pytest_report,
    trace_requirements,
)

_REQUIREMENTS_MD = textwrap.dedent(
    """\
    # Requirements (`artifact: human-requirements`)

    ## Requirements

    ### REQ-INPUT-01: Ratified requirements are append-only
    - **Constraint:** A `Lifecycle: RATIFIED` `### REQ-*` block MUST NOT be edited in place.
    - **Acceptance:** `tests/test_human_input_immutability.py` PASSES — a git diff that mutates a
      `RATIFIED` REQ block without a paired amendment file fails the lint.
    - **Lifecycle:** RATIFIED 2026-06-03
    - **Status:** Pending
    - **Amendments:** none

    ### REQ-INPUT-02: Constitution carries a per-file version stamp
    - **Constraint:** The constitution MUST carry its own `**Version**` footer stamp.
    - **Acceptance:** `tests/test_constitution_stamp.py` checks the footer stamp.
    - **Lifecycle:** RATIFIED 2026-06-03
    - **Status:** Pending
    - **Amendments:** none

    ### REQ-OUT-01: Digest token budget enforced
    - **Constraint:** `DIGEST.md` MUST stay within its C-9 token ceiling.
    - **Acceptance:** `python -m devolaflow.agent_workspace.lint` flags an over-budget digest.
    - **Lifecycle:** DRAFT
    - **Status:** Blocked
    - **Amendments:** none

    ### REQ-TEST-99: Unmapped requirements remain visible
    - **Constraint:** A requirement without a traceability row MUST remain explicit.
    - **Acceptance:** The trace reports `unmet` with `no evidence`.
    - **Lifecycle:** DRAFT
    - **Status:** Pending
    - **Amendments:** none

    ## Traceability
    | REQ-ID | Acceptance criterion | Cycle | Status |
    |---|---|---|---|
    | REQ-INPUT-01 | append-only lint passes | v14.1.0 | Satisfied |
    | REQ-INPUT-02 | constitution stamp present | v14.1.0 | Pending |
    | REQ-OUT-01 | digest budget enforced | v14.1.0 | Blocked |
    | **Unmapped** | — | — | **0** ✓ |

    ## Out of Scope
    | Item | Reason |
    |---|---|
    | auto-updater for TRACKER | optional later enhancement |

    **Version**: 1.0.0 | **Last Amended**: 2026-06-03
    """
)


def _write_requirements(tmp_path: Path, body: str = _REQUIREMENTS_MD) -> Path:
    path = tmp_path / "requirements.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_trace_enumerates_every_req_block(tmp_path: Path) -> None:
    """Every ``### REQ-*`` block is keyed in the result (none silently dropped)."""
    results = trace_requirements(_write_requirements(tmp_path))
    assert set(results) == {
        "REQ-INPUT-01",
        "REQ-INPUT-02",
        "REQ-OUT-01",
        "REQ-TEST-99",
    }


def test_trace_satisfied_status_maps_to_met_with_verbatim_evidence(tmp_path: Path) -> None:
    """Matrix ``Satisfied`` → ``met``; evidence is the verbatim Acceptance text (C-3).

    REQ-INPUT-01's block ``Status`` is ``Pending`` yet its matrix Status is
    ``Satisfied`` — the trace keys off the MATRIX Status, never the block's
    own ``Status`` field. The evidence joins the wrapped Acceptance lines
    verbatim (continuation handling).
    """
    results = trace_requirements(_write_requirements(tmp_path))
    row = results["REQ-INPUT-01"]
    assert isinstance(row, RequirementTraceResult)
    assert row.result == "met"
    assert "tests/test_human_input_immutability.py" in row.evidence
    assert "fails the lint." in row.evidence


def test_trace_pending_status_maps_to_partial(tmp_path: Path) -> None:
    """Matrix ``Pending`` → ``partial``."""
    results = trace_requirements(_write_requirements(tmp_path))
    assert results["REQ-INPUT-02"].result == "partial"


def test_trace_blocked_status_maps_to_unmet(tmp_path: Path) -> None:
    """Matrix ``Blocked`` → ``unmet``."""
    results = trace_requirements(_write_requirements(tmp_path))
    assert results["REQ-OUT-01"].result == "unmet"


def test_trace_missing_matrix_row_is_unmet_no_evidence(tmp_path: Path) -> None:
    """A REQ block with NO ``## Traceability`` row → unmet + 'no evidence' (S-5).

    REQ-TEST-99 has a ``### REQ-*`` block but is absent from the matrix, so it
    must surface as an explicit unmet row — never silently dropped.
    """
    results = trace_requirements(_write_requirements(tmp_path))
    assert "REQ-TEST-99" in results
    row = results["REQ-TEST-99"]
    assert row.result == "unmet"
    assert row.evidence == "no evidence"


def test_trace_unknown_status_defaults_to_unmet(tmp_path: Path) -> None:
    """An unrecognised matrix Status falls back to ``unmet`` (never over-claims)."""
    weird = _REQUIREMENTS_MD.replace(
        "| REQ-OUT-01 | digest budget enforced | v14.1.0 | Blocked |",
        "| REQ-OUT-01 | digest budget enforced | v14.1.0 | Deferred?! |",
    )
    results = trace_requirements(_write_requirements(tmp_path, weird))
    assert results["REQ-OUT-01"].result == "unmet"


def test_trace_missing_file_raises_filenotfound(tmp_path: Path) -> None:
    """A non-existent requirements file raises FileNotFoundError (no silent failure)."""
    with pytest.raises(FileNotFoundError):
        trace_requirements(tmp_path / "does-not-exist.md")


def test_trace_none_path_raises_typed_error() -> None:
    """A ``None`` path raises the typed RequirementsTraceError (caller-bug guard)."""
    with pytest.raises(RequirementsTraceError):
        trace_requirements(None)  # type: ignore[arg-type]


def test_trace_result_is_frozen(tmp_path: Path) -> None:
    """RequirementTraceResult is an immutable (frozen) dataclass."""
    row = trace_requirements(_write_requirements(tmp_path))["REQ-INPUT-01"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.result = "met"  # type: ignore[misc]


def test_trace_captures_criterion_and_cycle(tmp_path: Path) -> None:
    """The matrix ``Acceptance criterion`` + ``Cycle`` cells populate the row (v14.1.0)."""
    row = trace_requirements(_write_requirements(tmp_path))["REQ-INPUT-01"]
    assert row.criterion == "append-only lint passes"
    assert row.cycle == "v14.1.0"


# ---------------------------------------------------------------------------
# v14.1.0 §6c — inverse-S-5: a matrix row with NO ``### REQ-*`` block.
# ---------------------------------------------------------------------------

_MATRIX_ONLY_MD = textwrap.dedent(
    """\
    # Requirements

    ## Requirements

    ### REQ-A-01: has a block
    - **Acceptance:** `tests/test_a.py::test_a` PASSES.
    - **Status:** Satisfied

    ## Traceability
    | REQ-ID | Acceptance criterion | Cycle | Status |
    |---|---|---|---|
    | REQ-A-01 | a criterion | v14.1.0 | Satisfied |
    | REQ-GHOST-99 | unbacked matrix row | v14.1.0 | Satisfied |
    """
)


def test_trace_matrix_only_req_emits_unmet_inverse_s5(tmp_path: Path) -> None:
    """A matrix row with NO REQ block emits ``unmet`` + note — never dropped (inverse S-5).

    Before v14.1.0 ``trace_requirements`` iterated block keys only, so a
    matrix-only REQ was silently dropped (the inverse of the forward
    block-without-matrix S-5 case). The union fix surfaces it.
    """
    results = trace_requirements(_write_requirements(tmp_path, _MATRIX_ONLY_MD))
    assert "REQ-GHOST-99" in results
    row = results["REQ-GHOST-99"]
    assert row.result == "unmet"
    assert row.evidence == "matrix row without REQ block"
    # matrix criterion / cycle are still preserved on the inverse-S-5 row.
    assert row.criterion == "unbacked matrix row"
    assert row.cycle == "v14.1.0"


# ---------------------------------------------------------------------------
# v14.1.0 §6c — parse_pytest_report (pytest --report-log JSONL reader).
# ---------------------------------------------------------------------------


def _write_report_log(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "report.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def test_parse_pytest_report_keeps_call_phase_outcomes(tmp_path: Path) -> None:
    """Only ``TestReport`` records of the ``call`` phase are kept; commit stamped."""
    log = _write_report_log(
        tmp_path,
        [
            {"$report_type": "SessionStart"},
            {"$report_type": "TestReport", "when": "setup", "nodeid": "t.py::a", "outcome": "p"},
            {
                "$report_type": "TestReport",
                "when": "call",
                "nodeid": "t.py::a",
                "outcome": "passed",
            },
            {
                "$report_type": "TestReport",
                "when": "call",
                "nodeid": "t.py::b",
                "outcome": "failed",
            },
            {"$report_type": "CollectReport", "nodeid": "t.py"},
        ],
    )
    outcomes = parse_pytest_report(log, commit="deadbee")
    assert set(outcomes) == {"t.py::a", "t.py::b"}
    assert outcomes["t.py::a"] == TestOutcome("t.py::a", "passed", "deadbee")
    assert outcomes["t.py::b"].outcome == "failed"


def test_parse_pytest_report_missing_file_raises(tmp_path: Path) -> None:
    """A non-existent report-log raises FileNotFoundError (S-5: loud)."""
    with pytest.raises(FileNotFoundError):
        parse_pytest_report(tmp_path / "absent.jsonl")


def test_parse_pytest_report_malformed_line_raises(tmp_path: Path) -> None:
    """A non-JSON line raises RequirementsTraceError (S-5: never partial-parse)."""
    path = tmp_path / "bad.jsonl"
    path.write_text('{"$report_type": "TestReport"}\nNOT JSON\n', encoding="utf-8")
    with pytest.raises(RequirementsTraceError):
        parse_pytest_report(path)


def test_parse_pytest_report_none_path_raises() -> None:
    """A ``None`` report path raises the typed RequirementsTraceError."""
    with pytest.raises(RequirementsTraceError):
        parse_pytest_report(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# v14.1.0 §6c — the test-run-artifact join (trace_requirements test_results=).
# ---------------------------------------------------------------------------

_JOIN_MD = textwrap.dedent(
    """\
    # Requirements

    ## Requirements

    ### REQ-J-01: pass path
    - **Acceptance:** `tests/test_join.py::test_pass` PASSES.
    - **Status:** Pending

    ### REQ-J-02: fail path (matrix optimistic)
    - **Acceptance:** `tests/test_join.py::test_fail` should pass.
    - **Status:** Satisfied

    ### REQ-J-03: no node-id named
    - **Acceptance:** verified manually by review.
    - **Status:** Satisfied

    ## Traceability
    | REQ-ID | Acceptance criterion | Cycle | Status |
    |---|---|---|---|
    | REQ-J-01 | pass | v14.1.0 | Pending |
    | REQ-J-02 | fail | v14.1.0 | Satisfied |
    | REQ-J-03 | manual | v14.1.0 | Satisfied |
    """
)


def test_join_passed_node_overrides_matrix_to_met(tmp_path: Path) -> None:
    """A passing pytest node → ``met`` with verbatim ``<node> PASS @ <commit>`` evidence."""
    tr = {
        "tests/test_join.py::test_pass": TestOutcome(
            "tests/test_join.py::test_pass", "passed", "abc1234"
        )
    }
    row = trace_requirements(_write_requirements(tmp_path, _JOIN_MD), test_results=tr)["REQ-J-01"]
    assert row.result == "met"
    assert row.evidence == "tests/test_join.py::test_pass PASS @ abc1234"


def test_join_failed_node_overrides_optimistic_matrix_to_unmet(tmp_path: Path) -> None:
    """A failing pytest node → ``unmet`` even when the matrix Status is ``Satisfied``.

    This is the core §6c value: real test evidence overrides an optimistic
    matrix cell so the convergence report can never over-claim.
    """
    tr = {
        "tests/test_join.py::test_fail": TestOutcome(
            "tests/test_join.py::test_fail", "failed", "abc1234"
        )
    }
    row = trace_requirements(_write_requirements(tmp_path, _JOIN_MD), test_results=tr)["REQ-J-02"]
    assert row.result == "unmet"
    assert row.evidence == "tests/test_join.py::test_fail FAIL @ abc1234"


def test_join_missing_node_falls_back_to_matrix(tmp_path: Path) -> None:
    """A REQ whose node-id is absent from test_results keeps the matrix derivation."""
    tr = {"tests/other.py::test_x": TestOutcome("tests/other.py::test_x", "passed")}
    results = trace_requirements(_write_requirements(tmp_path, _JOIN_MD), test_results=tr)
    # REQ-J-01 (Pending, node not in map) → matrix fallback ``partial``.
    assert results["REQ-J-01"].result == "partial"
    # REQ-J-03 names no node-id at all → matrix fallback (Satisfied → met).
    assert results["REQ-J-03"].result == "met"


def test_join_absent_is_backward_compatible(tmp_path: Path) -> None:
    """No ``test_results`` → pure matrix derivation (v14.0.0 byte-identical behaviour)."""
    no_join = trace_requirements(_write_requirements(tmp_path, _JOIN_MD))
    assert no_join["REQ-J-01"].result == "partial"  # Pending
    assert no_join["REQ-J-02"].result == "met"  # Satisfied (optimistic, no test evidence)


def test_parse_then_join_end_to_end(tmp_path: Path) -> None:
    """``parse_pytest_report`` output threads straight into ``trace_requirements``."""
    log = _write_report_log(
        tmp_path,
        [
            {
                "$report_type": "TestReport",
                "when": "call",
                "nodeid": "tests/test_join.py::test_pass",
                "outcome": "passed",
            },
            {
                "$report_type": "TestReport",
                "when": "call",
                "nodeid": "tests/test_join.py::test_fail",
                "outcome": "failed",
            },
        ],
    )
    tr = parse_pytest_report(log, commit="cafe123")
    results = trace_requirements(_write_requirements(tmp_path, _JOIN_MD), test_results=tr)
    assert results["REQ-J-01"].result == "met"
    assert results["REQ-J-02"].result == "unmet"
    assert "cafe123" in results["REQ-J-01"].evidence
