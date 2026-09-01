"""W-18 ghost audit for v24.2.0.

Existence-and-contract checks for every claim the v24.2.0 CHANGELOG entry
makes. These are deliberately shallow: behaviour is pinned by the suites
named in each docstring. What this file prevents is a CHANGELOG entry
outliving the code it describes (S-4).
"""

from __future__ import annotations


def test_a_compact_result_separates_digest_problems_from_refusal() -> None:
    """RISK-002. Behaviour: tests/test_workspace_compact.py."""

    from devolaflow.workspace_compact.models import CompactResult

    clean = CompactResult(applied=(), findings=(), refused=False)
    assert clean.success is True
    assert clean.digest_current is True

    stale_index = CompactResult(
        applied=(),
        findings=(),
        refused=False,
        digest_findings=("BROKEN_ANCHOR: x#L1: gone",),
    )
    assert stale_index.success is True, "a durable move must not read as refused"
    assert stale_index.digest_current is False

    real_refusal = CompactResult(findings=("APPLY_ERROR: a.md: disk full",), refused=True)
    assert real_refusal.success is False


def test_apply_reports_the_two_outcomes_on_separate_fields() -> None:
    """The CLI contract, not just the dataclass."""

    from dataclasses import fields

    from devolaflow.workspace_compact.models import CompactResult

    names = {field.name for field in fields(CompactResult)}
    assert {"findings", "digest_findings"} <= names


def test_the_retired_gate_reader_path_is_covered_by_a_ledger_test() -> None:
    """RISK-004: the F-00 fix was to the reader, so a test must read."""

    from pathlib import Path

    source = Path("tests/harness/test_aggregator.py").read_text(encoding="utf-8")
    assert "def test_a_retired_gate_row_loads_from_a_real_ledger" in source
    assert "def test_an_unknown_gate_name_still_aborts_a_strict_read" in source


def test_digest_rendering_is_not_gated_on_narration_validity() -> None:
    """The ledger table must survive a narration the anchors reject."""

    import inspect

    from devolaflow.workspace_compact.digest import write_digest

    body = inspect.getsource(write_digest)
    assert "if findings:\n        return tuple(findings)" not in body, (
        "an early return here withholds the ledger-derived table over agent prose"
    )
