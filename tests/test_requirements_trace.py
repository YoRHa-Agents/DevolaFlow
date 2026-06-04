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
import textwrap
from pathlib import Path

import pytest

from devolaflow.agent_workspace import (
    RequirementsTraceError,
    RequirementTraceResult,
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

    ### REQ-SEP-09: Sichip docs leave feedbacks
    - **Constraint:** Agent-authored DEFER docs MUST NOT live under `.local/feedbacks/`.
    - **Acceptance:** `tests/test_post_skill_edit_hook.py::test_defer_dir` PASS.
    - **Lifecycle:** RATIFIED 2026-06-03
    - **Status:** Satisfied
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
    assert set(results) == {"REQ-INPUT-01", "REQ-INPUT-02", "REQ-OUT-01", "REQ-SEP-09"}


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

    REQ-SEP-09 has a ``### REQ-*`` block but is absent from the matrix, so it
    must surface as an explicit unmet row — never silently dropped.
    """
    results = trace_requirements(_write_requirements(tmp_path))
    assert "REQ-SEP-09" in results
    row = results["REQ-SEP-09"]
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
