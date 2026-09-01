"""Compaction telemetry and digest-subject coverage (v24.0.0).

The dedicated ledger exists because of this cycle's F-00 finding: a strict
shared ledger that aborts on one bad row takes every downstream reading with
it. These tests pin the degradation behaviour that makes the separation
worthwhile, not merely the happy path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devolaflow.harness.telemetry import (
    RETIRED_SI10_GATE_NAMES,
    TelemetryGateError,
    build_gate_record,
)
from devolaflow.parking.store import ParkingStore
from devolaflow.workspace_compact.engine import apply_plan, build_plan, load_mappings
from devolaflow.workspace_compact.telemetry import (
    COMPACT_EVENT,
    OUTCOME_APPLIED,
    OUTCOME_BYPASSED,
    OUTCOME_PLANNED,
    append_event,
    build_event,
    read_events,
    summarize,
)


def test_build_event_computes_reduction_and_rejects_unknown_outcome() -> None:
    record = build_event("t", OUTCOME_APPLIED, tokens_before=1000, tokens_after=250, entries=3)
    assert record["event"] == COMPACT_EVENT
    assert record["reduction"] == pytest.approx(0.75)
    with pytest.raises(ValueError, match="outcome must be one of"):
        build_event("t", "invented", tokens_before=1, tokens_after=0, entries=0)


def test_zero_before_tokens_does_not_divide_by_zero() -> None:
    record = build_event("t", OUTCOME_BYPASSED, tokens_before=0, tokens_after=0, entries=0)
    assert record["reduction"] == 0.0


def test_reader_skips_a_malformed_row_instead_of_losing_the_ledger(tmp_path: Path) -> None:
    """One damaged row must cost one row of evidence, not all of it."""

    ledger = tmp_path / "compact.jsonl"
    append_event(
        ledger, build_event("a", OUTCOME_APPLIED, tokens_before=100, tokens_after=40, entries=1)
    )
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write("{ this is not json\n")
    append_event(
        ledger, build_event("b", OUTCOME_PLANNED, tokens_before=200, tokens_after=200, entries=2)
    )

    rows = read_events(ledger)
    assert [row["folder"] for row in rows] == ["a", "b"]


def test_reader_ignores_foreign_events_sharing_the_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "compact.jsonl"
    ledger.write_text(json.dumps({"event": "something_else"}) + "\n", encoding="utf-8")
    append_event(
        ledger, build_event("a", OUTCOME_APPLIED, tokens_before=10, tokens_after=5, entries=1)
    )
    assert [row["folder"] for row in read_events(ledger)] == ["a"]


def test_missing_ledger_reads_as_no_evidence_not_an_error(tmp_path: Path) -> None:
    assert read_events(tmp_path / "absent.jsonl") == ()
    assert summarize(tmp_path / "absent.jsonl")["events"] == 0


def test_append_degrades_to_a_warning_when_the_path_is_unusable(tmp_path: Path) -> None:
    """A failed observability write must not be reported as a successful one."""

    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    result = append_event(
        blocker / "nested" / "compact.jsonl",
        build_event("a", OUTCOME_APPLIED, tokens_before=10, tokens_after=1, entries=1),
    )
    assert result is None


def test_summarize_counts_each_outcome_separately(tmp_path: Path) -> None:
    ledger = tmp_path / "compact.jsonl"
    append_event(
        ledger, build_event("a", OUTCOME_APPLIED, tokens_before=1000, tokens_after=500, entries=2)
    )
    append_event(
        ledger, build_event("a", OUTCOME_PLANNED, tokens_before=400, tokens_after=400, entries=1)
    )
    append_event(
        ledger, build_event("b", OUTCOME_BYPASSED, tokens_before=0, tokens_after=0, entries=0)
    )

    summary = summarize(ledger)
    assert (summary["applied"], summary["planned"], summary["bypassed"]) == (1, 1, 1)
    assert summary["tokens_saved"] == 500
    assert summary["folders"] == ["a", "b"]


def test_apply_records_one_telemetry_event(tmp_path: Path) -> None:
    store = ParkingStore(tmp_path)
    store.scaffold()
    risk = store.open_risk("Settled item", severity="minor", trigger="t", disposition="d")
    store.transition_risk(risk.id, "closed", reason="done")

    ledger = tmp_path / "telemetry.jsonl"
    plan = build_plan(tmp_path)
    result = apply_plan(
        tmp_path,
        plan,
        approval_fingerprint=plan.fingerprint,
        telemetry_ledger=ledger,
    )

    assert result.success
    rows = read_events(ledger)
    assert len(rows) == 1
    assert rows[0]["outcome"] == OUTCOME_APPLIED
    assert rows[0]["entries"] == len(result.applied)


def test_apply_without_a_ledger_writes_no_telemetry(tmp_path: Path) -> None:
    """Telemetry is opt-in; the default path must stay byte-identical."""

    store = ParkingStore(tmp_path)
    store.scaffold()
    risk = store.open_risk("Settled item", severity="minor", trigger="t", disposition="d")
    store.transition_risk(risk.id, "closed", reason="done")

    plan = build_plan(tmp_path)
    result = apply_plan(tmp_path, plan, approval_fingerprint=plan.fingerprint)
    assert result.success
    assert not list(tmp_path.glob("*.jsonl"))


def test_mapping_row_carries_a_readable_subject(tmp_path: Path) -> None:
    """The digest must be answerable without running `locate` on every row."""

    store = ParkingStore(tmp_path)
    store.scaffold()
    risk = store.open_risk(
        "Ledger aborts on a retired gate name",
        severity="blocker",
        trigger="retired name",
        disposition="fixed",
    )
    store.transition_risk(risk.id, "closed", reason="fixed")

    plan = build_plan(tmp_path)
    moved = next(entry for entry in plan.movable if entry.subject == risk.id)
    assert moved.summary == "Ledger aborts on a retired gate name"

    apply_plan(tmp_path, plan, approval_fingerprint=plan.fingerprint)
    row = next(row for row in load_mappings(tmp_path) if row["source"] == moved.source)
    assert row["summary"] == "Ledger aborts on a retired gate name"
    digest = (tmp_path / "compact" / "DIGEST.md").read_text(encoding="utf-8")
    assert "Ledger aborts on a retired gate name" in digest


def test_retired_gate_name_is_readable_but_not_writable() -> None:
    """F-00: history stays parsable while the live vocabulary stays closed."""

    retired = next(iter(RETIRED_SI10_GATE_NAMES))
    with pytest.raises(TelemetryGateError, match="gate must be one of"):
        build_gate_record("pv1", retired, "PASS")


def test_plan_records_bypassed_when_nothing_is_eligible(tmp_path, capsys):
    """`bypassed` was declared in v24 and written by nothing.

    A vocabulary term no code path emits cannot answer the question it exists
    for — whether compaction is worth suggesting — because the ledger cannot
    tell "no plan was made" from "a plan declined itself".
    """
    from devolaflow.workspace_compact.console import main as compact_main

    folder = tmp_path / "task"
    folder.mkdir()
    (folder / "goal.md").write_text("# goal\n", encoding="utf-8")
    ledger = tmp_path / "compact.jsonl"

    assert compact_main(["plan", "--folder", str(folder), "--telemetry", str(ledger)]) == 0
    capsys.readouterr()

    rows = read_events(ledger)
    assert [row["outcome"] for row in rows] == [OUTCOME_BYPASSED]
    assert rows[0]["reason"] == "nothing is automatically eligible"


def test_plan_records_bypassed_when_the_digest_costs_more_than_the_move(tmp_path, capsys):
    """A move that would make the folder more expensive to read is a bypass."""
    from devolaflow.workspace_compact.console import main as compact_main

    folder = tmp_path / "task"
    (folder / "loops").mkdir(parents=True)
    (folder / "loops" / "tiny.md").write_text("ok\n", encoding="utf-8")
    ledger = tmp_path / "compact.jsonl"

    assert compact_main(["plan", "--folder", str(folder), "--telemetry", str(ledger)]) == 0
    capsys.readouterr()

    rows = read_events(ledger)
    assert rows[0]["outcome"] == OUTCOME_BYPASSED
    assert "digest costs" in rows[0]["reason"]


def test_plan_records_planned_when_the_move_pays_for_itself(tmp_path, capsys):
    """The paying case must still record `planned`, or the guard hides real work."""
    from devolaflow.workspace_compact.console import main as compact_main

    folder = tmp_path / "task"
    (folder / "loops").mkdir(parents=True)
    (folder / "loops" / "big.md").write_text("word " * 4000, encoding="utf-8")
    ledger = tmp_path / "compact.jsonl"

    assert compact_main(["plan", "--folder", str(folder), "--telemetry", str(ledger)]) == 0
    capsys.readouterr()

    rows = read_events(ledger)
    assert rows[0]["outcome"] == OUTCOME_PLANNED
