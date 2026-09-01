"""v24.0.0 — risk parking, judgment ledger, and generated views."""

from __future__ import annotations

import json

import pytest

from devolaflow.parking import (
    ParkingError,
    ParkingStore,
    RiskState,
    Severity,
    plan_adoption,
)
from devolaflow.parking.adopt import apply_adoption
from devolaflow.parking.console import main as parking_main


@pytest.fixture
def store(tmp_path):
    folder = tmp_path / "task"
    folder.mkdir()
    parking = ParkingStore(folder)
    parking.scaffold()
    return parking


def test_scaffold_creates_every_surface(store):
    for path in (
        store.risks_dir,
        store.judgments_path,
        store.events_path,
        store.index_path,
        store.judge_path,
    ):
        assert path.exists()
    assert store.audit() == ()


def test_scaffold_is_idempotent(store):
    before = sorted(p.name for p in store.root.rglob("*"))
    store.scaffold()
    assert sorted(p.name for p in store.root.rglob("*")) == before


def test_open_risk_writes_file_event_and_views(store):
    risk = store.open_risk("prompt overflow", severity=Severity.BLOCKER, trigger="long runs")
    assert risk.id == "RISK-001"
    assert store.risk_path(risk.id).exists()
    assert [event.event for event in store.list_events()] == ["risk_opened"]
    assert "prompt overflow" in store.index_path.read_text(encoding="utf-8")
    assert store.audit() == ()


def test_risk_ids_increment_independently_of_ledger_sequence(store):
    store.open_risk("first")
    store.open_risk("second")
    assert [risk.id for risk in store.list_risks()] == ["RISK-001", "RISK-002"]


@pytest.mark.parametrize(
    ("target", "legal"),
    [
        (RiskState.PARKED, True),
        (RiskState.ACTIVE, True),
        (RiskState.MITIGATING, True),
        (RiskState.CLOSED, True),
        (RiskState.ARCHIVED, False),
    ],
)
def test_transition_matrix_from_open(store, target, legal):
    risk = store.open_risk("t")
    if legal:
        assert store.transition_risk(risk.id, target, reason="r").state is target
    else:
        with pytest.raises(ParkingError, match="illegal risk transition"):
            store.transition_risk(risk.id, target, reason="r")


def test_transition_requires_a_reason(store):
    risk = store.open_risk("t")
    with pytest.raises(ParkingError, match="reason"):
        store.transition_risk(risk.id, RiskState.PARKED, reason="  ")


def test_transition_appends_history_in_place(store):
    risk = store.open_risk("t")
    store.transition_risk(risk.id, RiskState.PARKED, reason="waiting on the operator")
    body = store.load_risk(risk.id).body
    assert "## History" in body
    assert "open → parked: waiting on the operator" in body


def test_pending_question_does_not_block_the_risk(store):
    risk = store.open_risk("t")
    store.raise_question("ship or defer?", subject=risk.id)
    store.transition_risk(risk.id, RiskState.ACTIVE, reason="work continues")
    snapshot = store.snapshot()
    assert len(snapshot.pending) == 1
    assert snapshot.risks[0].state is RiskState.ACTIVE


def test_answering_appends_rather_than_editing(store):
    risk = store.open_risk("t")
    question = store.raise_question("ship or defer?", subject=risk.id)
    raw_before = store.judgments_path.read_text(encoding="utf-8")
    decision = store.record_decision("defer to v25", question_id=question.id)
    assert decision.supersedes == question.id
    assert raw_before in store.judgments_path.read_text(encoding="utf-8")
    assert store.snapshot().pending == ()


def test_superseding_a_decision_keeps_both_rows(store):
    first = store.record_decision("yes", subject="scope", question="do it?")
    second = store.record_decision("actually no", question_id=first.id)
    settled = store.snapshot().settled
    assert [row.decision for row in settled] == ["yes", "actually no"]
    assert second.supersedes == first.id


def test_standalone_decision_requires_subject_and_question(store):
    with pytest.raises(ParkingError, match="subject and question"):
        store.record_decision("a decision")


def test_judgment_links_back_onto_its_risk(store):
    risk = store.open_risk("t")
    question = store.raise_question("q?", subject=risk.id)
    assert question.id in store.load_risk(risk.id).judgment_refs


def test_views_are_regenerated_from_the_ledgers(store):
    risk = store.open_risk("t")
    store.raise_question("q?", subject=risk.id)
    store.index_path.write_text(
        store.index_path.read_text(encoding="utf-8").replace("Live: 1", "Live: 42"),
        encoding="utf-8",
    )
    assert [item.code for item in store.audit()] == ["VIEW_DRIFT"]
    assert store.render_views() == ()
    assert store.audit() == ()


def test_generated_view_refuses_to_clobber_a_human_file(store):
    store.judge_path.write_text("# my own notes\n", encoding="utf-8")
    assert [item.code for item in store.render_views()] == ["HUMAN_VIEW"]
    assert store.judge_path.read_text(encoding="utf-8") == "# my own notes\n"


def test_malformed_risk_id_is_refused(store):
    with pytest.raises(ParkingError, match="malformed risk id"):
        store.risk_path("not-a-risk")


def test_adoption_is_report_only_until_approved(tmp_path):
    source = tmp_path / "legacy.md"
    source.write_text(
        "# legacy\n\n## §B 活跃\n\n| # | 风险 | 触发 | 处置 |\n|---|---|---|---|\n"
        "| PV-01 | closure gap | on release | monitor |\n",
        encoding="utf-8",
    )
    plan = plan_adoption(source)
    assert [item.legacy_id for item in plan.candidates] == ["PV-01"]
    assert plan.candidates[0].state is RiskState.ACTIVE
    folder = tmp_path / "task"
    folder.mkdir()
    with pytest.raises(ParkingError, match="approval fingerprint"):
        apply_adoption(folder, plan, approval_fingerprint="wrong")
    assert not (folder / "parking").exists()


def test_adoption_preserves_legacy_ids_verbatim(tmp_path):
    source = tmp_path / "legacy.md"
    source.write_text(
        "# legacy\n\n## §C 已闭合\n\n| # | 原风险 | 闭合方式 |\n|---|---|---|\n"
        "| ~~PV-29-原文~~ | superseded row | replaced |\n"
        "| PV-29 | corrected row | closed |\n",
        encoding="utf-8",
    )
    plan = plan_adoption(source)
    folder = tmp_path / "task"
    folder.mkdir()
    created = apply_adoption(folder, plan, approval_fingerprint=plan.fingerprint)
    legacy = {ParkingStore(folder).load_risk(rid).legacy_id for rid in created}
    assert legacy == {"PV-29-原文", "PV-29"}


def test_adoption_never_touches_the_source(tmp_path):
    source = tmp_path / "legacy.md"
    body = "# legacy\n\n## §B 活跃\n\n| # | r | t | d |\n|---|---|---|---|\n| PV-01 | a | b | c |\n"
    source.write_text(body, encoding="utf-8")
    plan = plan_adoption(source)
    folder = tmp_path / "task"
    folder.mkdir()
    apply_adoption(folder, plan, approval_fingerprint=plan.fingerprint)
    assert source.read_text(encoding="utf-8") == body


def test_console_probe_and_status_round_trip(tmp_path, capsys):
    folder = tmp_path / "task"
    folder.mkdir()
    assert parking_main(["--folder", str(folder), "probe"]) == 0
    assert parking_main(["--folder", str(folder), "scaffold"]) == 0
    assert parking_main(["--folder", str(folder), "open", "--title", "x"]) == 0
    assert parking_main(["--folder", str(folder), "status"]) == 0
    assert '"live": 1' in capsys.readouterr().out


def test_console_reports_refusal_as_json(tmp_path, capsys):
    folder = tmp_path / "task"
    folder.mkdir()
    assert (
        parking_main(
            [
                "--folder",
                str(folder),
                "transition",
                "--risk",
                "RISK-404",
                "--to",
                "closed",
                "--reason",
                "r",
            ]
        )
        == 2
    )
    assert "PARKING_REFUSED" in capsys.readouterr().out


def test_console_accepts_folder_after_the_subcommand(tmp_path, capsys):
    """`devola-parking status --folder X` must work, not only `--folder X status`.

    v24 registered `--folder` ahead of the subparsers only, so the natural
    invocation failed with "unrecognized arguments" — a first-contact trap for
    every caller who typed the subcommand first.
    """
    folder = tmp_path / "task"
    folder.mkdir()
    assert parking_main(["scaffold", "--folder", str(folder)]) == 0
    capsys.readouterr()
    assert parking_main(["open", "--folder", str(folder), "--title", "after-order"]) == 0
    capsys.readouterr()

    assert parking_main(["status", "--folder", str(folder)]) == 0
    after = capsys.readouterr().out
    assert parking_main(["--folder", str(folder), "status"]) == 0
    assert capsys.readouterr().out == after, "both argument orders must agree exactly"
    assert "after-order" in after


def test_a_malformed_invocation_still_prints_one_json_object(tmp_path, capsys):
    """The docstring promises one JSON object on stdout; argparse promised nothing."""
    code = parking_main(["frobnicate", "--folder", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 2, "the exit code must not change; only the payload is new"
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["artifact_type"] == "parking-error"
    assert payload["error_kind"] == "usage"
    assert "devola-parking" in payload["usage"]


def test_a_domain_refusal_names_itself_as_one(store, capsys):
    """Exit 2 is shared, so the payload has to say which kind of 2 it is."""
    assert (
        parking_main(
            [
                "transition",
                "--folder",
                str(store.folder),
                "--risk",
                "RISK-404",
                "--to",
                "closed",
                "--reason",
                "nope",
            ]
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_kind"] == "domain"
    assert payload["findings"][0]["code"] == "PARKING_REFUSED"
