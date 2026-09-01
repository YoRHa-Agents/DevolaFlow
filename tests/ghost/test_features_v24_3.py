"""W-18 ghost audit for v24.3.0.

Existence-and-contract checks for every claim the v24.3.0 CHANGELOG entry
makes. These are deliberately shallow: behaviour is pinned by the suites named
in each docstring. What this file prevents is a CHANGELOG entry outliving the
code it describes (S-4).
"""

from __future__ import annotations

from pathlib import Path


def test_the_mapping_row_precedes_the_move() -> None:
    """RISK-001. Behaviour: tests/test_workspace_compact.py."""

    import inspect

    from devolaflow.workspace_compact.engine import apply_plan

    body = inspect.getsource(apply_plan)
    append_at = body.index("append_ledger_row(")
    move_at = body.index("shutil.move(")
    assert append_at < move_at, (
        "record-then-move is the whole guarantee: the other order can leave a "
        "moved file that no ledger row names"
    )


def test_a_pending_move_is_a_first_class_state() -> None:
    """RISK-001: recovery has to be visible, not inferred."""

    from dataclasses import fields

    from devolaflow.workspace_compact.engine import pending_moves, verify_integrity
    from devolaflow.workspace_compact.models import CompactEntry, CompactPlan

    assert "pending" in {field.name for field in fields(CompactEntry)}
    assert isinstance(CompactPlan.pending, property)
    assert callable(pending_moves)
    assert "PENDING_MOVE" in verify_integrity.__doc__ or "PENDING_MOVE" in Path(
        "src/devolaflow/workspace_compact/engine.py"
    ).read_text(encoding="utf-8")


def test_telemetry_records_the_cost_it_had_to_pay() -> None:
    """RISK-003. Behaviour: tests/test_workspace_compact_telemetry.py."""

    from devolaflow.workspace_compact.telemetry import OUTCOME_APPLIED, build_event, summarize

    event = build_event(
        "f",
        OUTCOME_APPLIED,
        tokens_before=100,
        tokens_after=40,
        entries=1,
        digest_tokens=25,
        working_set_before=90,
        working_set_after=50,
    )
    assert {"digest_tokens", "net_tokens", "working_set_before", "working_set_after"} <= set(event)
    assert event["net_tokens"] == 35

    empty = summarize(Path("does/not/exist.jsonl"))
    assert {
        "digest_cost",
        "net_tokens_saved",
        "working_set_saved",
        "pays_for_itself",
        "rows_without_net_accounting",
    } <= set(empty)


def test_the_ledger_is_authoritative_for_an_archived_risk() -> None:
    """RISK-002: the design is stated, and the code still does not rewrite."""

    import inspect

    from devolaflow.parking.store import ParkingStore

    reference = Path("workflow-system/agent/references/risk-parking.md").read_text(encoding="utf-8")
    assert "lives in the ledger, not in the file" in reference
    assert "events.yaml` is authoritative" in reference

    body = inspect.getsource(ParkingStore.record_archival)
    assert "mark_archived" not in body.split('"""')[-1], (
        "the relocated original must stay byte-identical; the approval chain is "
        "bound to its content hash"
    )


def test_both_clis_answer_a_bad_invocation_in_json() -> None:
    """RISK-004. Behaviour: tests/test_workspace_compact.py, tests/test_parking.py."""

    from devolaflow.cli_envelope import (
        KIND_DOMAIN,
        KIND_USAGE,
        JsonUsageParser,
        UsageError,
        domain_envelope,
        usage_envelope,
    )

    assert issubclass(UsageError, Exception)
    envelope = usage_envelope("x", UsageError("bad", "usage: x"), schema_version=1)
    assert envelope["error_kind"] == KIND_USAGE
    assert domain_envelope("x", "C", "m", schema_version=1)["error_kind"] == KIND_DOMAIN

    for module in (
        "src/devolaflow/workspace_compact/console.py",
        "src/devolaflow/parking/console.py",
    ):
        source = Path(module).read_text(encoding="utf-8")
        assert "JsonUsageParser" in source, module
        assert "usage_envelope" in source, module
    assert JsonUsageParser is not None


def test_the_digest_spends_its_column_on_the_reason() -> None:
    """RISK-005. Behaviour: tests/test_workspace_compact.py."""

    from devolaflow.workspace_compact.digest import render_digest_rows

    rendered = render_digest_rows(
        [
            {
                "sequence": 1,
                "source": "loops/a.md",
                "destination": "compact/archived/0001/loops/a.md",
                "reason": "historical_output: accumulated historical output",
                "timestamp": "2026-09-01T00:00:00Z",
                "sha256": "a" * 64,
                "tokens_estimated": 12,
                "summary": "a round",
            }
        ]
    )
    assert "Category" in rendered
    assert "sha256" not in rendered
    assert "`historical_output`" in rendered
    assert "a" * 12 not in rendered, "a hash too short to verify with is not worth a column"
