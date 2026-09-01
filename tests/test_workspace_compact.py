"""v24.0.0 — non-destructive workspace compaction."""

from __future__ import annotations

import pytest

from devolaflow.parking import ParkingStore, RiskState
from devolaflow.workspace_compact import (
    Category,
    CompactError,
    apply_plan,
    audit_digest,
    build_plan,
    load_mappings,
    locate,
    measure_file,
    render_handoff_index,
    resident_tokens,
    restore,
    scan_bloat,
    set_agent_section,
    suggestion_text,
    verify_integrity,
    write_handoff_index,
)
from devolaflow.workspace_compact.bloat import measure_folder
from devolaflow.workspace_compact.console import main as compact_main
from devolaflow.workspace_compact.engine import archived_root, digest_path


@pytest.fixture
def folder(tmp_path):
    target = tmp_path / "task"
    target.mkdir()
    (target / "goal.md").write_text("# goal\n", encoding="utf-8")
    (target / "loops").mkdir()
    for index in range(2):
        (target / "loops" / f"round{index}.md").write_text(
            f"round {index} narration PV-16b disposition\n" * 40, encoding="utf-8"
        )
    store = ParkingStore(target)
    store.scaffold()
    store.open_risk("live risk")
    closed = store.open_risk("settled risk")
    store.transition_risk(closed.id, RiskState.CLOSED, reason="mitigated")
    return target


def test_plan_writes_nothing(folder):
    before = {p: p.stat().st_mtime_ns for p in folder.rglob("*") if p.is_file()}
    plan = build_plan(folder)
    assert plan.movable
    assert {p: p.stat().st_mtime_ns for p in folder.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    ("name", "category"),
    [
        ("goal.md", Category.PROTECTED),
        ("parking/judgments.yaml", Category.PROTECTED),
        ("parking/risks/RISK-001.md", Category.LIVE),
        ("parking/risks/RISK-002.md", Category.CLOSED_RISK),
        ("loops/round0.md", Category.HISTORICAL_OUTPUT),
    ],
)
def test_classification(folder, name, category):
    entries = {entry.source: entry for entry in build_plan(folder).entries}
    assert entries[name].category is category


def test_operator_named_include_is_the_channel_for_hand_written_files(folder):
    (folder / "legacy.md").write_text("legacy body\n" * 20, encoding="utf-8")
    plan = build_plan(folder, include=["legacy.md"])
    entry = next(item for item in plan.movable if item.source == "legacy.md")
    assert entry.category is Category.OPERATOR_NAMED
    assert "legacy.md" not in {item.source for item in build_plan(folder).movable}


def test_apply_requires_a_matching_fingerprint(folder):
    plan = build_plan(folder)
    result = apply_plan(folder, plan, approval_fingerprint="nope")
    assert result.refused
    assert result.findings == ("APPROVAL_MISMATCH: approval does not match the current plan",)
    assert not archived_root(folder).exists()


def test_apply_relocates_and_records_hashes(folder):
    plan = build_plan(folder)
    result = apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    assert result.success
    assert result.tokens_after < result.tokens_before
    rows = load_mappings(folder)
    assert len(rows) == len(result.applied)
    assert all(row["sha256"] for row in rows)
    assert verify_integrity(folder) == ()


def test_apply_refuses_when_content_changed_since_the_plan(folder):
    plan = build_plan(folder)
    (folder / "loops" / "round0.md").write_text("different\n", encoding="utf-8")
    result = apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    assert result.refused
    assert any(item.startswith("CONTENT_CHANGED") for item in result.findings)


def test_apply_is_not_a_delete(folder):
    plan = build_plan(folder)
    sources = {entry.source for entry in plan.movable}
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    destinations = {str(row["destination"]) for row in load_mappings(folder)}
    assert sources
    assert all((folder / destination).exists() for destination in destinations)


def test_closed_risk_archival_is_recorded_in_the_event_ledger(folder):
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    events = [event.event for event in ParkingStore(folder).list_events()]
    assert "risk_archived" in events


def test_locate_finds_relocated_content(folder):
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    hits = locate(folder, "PV-16b")
    assert hits
    assert hits[0].original_source.startswith("loops/")
    assert "PV-16b" in hits[0].excerpt


def test_locate_requires_a_query(folder):
    with pytest.raises(CompactError, match="non-empty query"):
        locate(folder, "  ")


def test_restore_copies_back_and_keeps_the_archive(folder):
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    source = str(load_mappings(folder)[0]["source"])
    restored = restore(folder, source)
    assert restored.exists()
    assert verify_integrity(folder) == ()
    with pytest.raises(CompactError, match="refusing to overwrite"):
        restore(folder, source)


def test_restore_refuses_an_unmapped_source(folder):
    with pytest.raises(CompactError, match="no mapping records"):
        restore(folder, "nothing.md")


def test_digest_is_generated_and_drift_is_detected(folder):
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    assert audit_digest(folder) == ()
    target = digest_path(folder)
    target.write_text(target.read_text(encoding="utf-8") + "hand appended\n", encoding="utf-8")
    assert [item.code for item in audit_digest(folder)] == ["DIGEST_DRIFT"]


def test_agent_narration_requires_resolvable_anchors(folder):
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    destination = str(load_mappings(folder)[0]["destination"])
    problems = set_agent_section(folder, "- the loops narrate rounds")
    assert any(item.startswith("UNANCHORED_CLAIM") for item in problems)
    problems = set_agent_section(folder, f'- claim [[{destination}#L999]] "missing"')
    assert any(item.startswith("BROKEN_ANCHOR") for item in problems)
    good = f'- rounds are narration [[{destination}#L1]] "round 0 narration PV-16b disposition"'
    assert set_agent_section(folder, good) == ()
    assert audit_digest(folder) == ()


def test_a_broken_narration_does_not_report_the_moves_as_refused(folder):
    """RISK-002: refusal used to absorb whatever the digest complained about.

    Every move and every ledger row can commit and the digest can still find
    an anchor that no longer resolves. Reporting that as ``refused`` tells an
    operator nothing moved, which is the opposite of what happened.
    """
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    destination = str(load_mappings(folder)[0]["destination"])
    set_agent_section(folder, f'- claim [[{destination}#L999]] "missing"')

    (folder / "notes.md").write_text("later notes\n" * 20, encoding="utf-8")
    second = build_plan(folder, include=("notes.md",))
    result = apply_plan(folder, second, approval_fingerprint=second.fingerprint)

    assert result.applied
    assert result.findings == ()
    assert result.refused is False
    assert result.success is True
    assert any(item.startswith("BROKEN_ANCHOR") for item in result.digest_findings)
    assert result.digest_current is False


def test_a_broken_narration_still_leaves_the_table_current(folder):
    """The table comes from the append-only ledger, not from agent prose.

    Withholding it over a narration problem hides the very rows the digest
    exists to list, and the narration is preserved so the flagged claim stays
    visible to whoever has to judge it.
    """
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    destination = str(load_mappings(folder)[0]["destination"])
    set_agent_section(folder, f'- claim [[{destination}#L999]] "missing"')

    (folder / "notes.md").write_text("later notes\n" * 20, encoding="utf-8")
    second = build_plan(folder, include=("notes.md",))
    apply_plan(folder, second, approval_fingerprint=second.fingerprint)

    text = digest_path(folder).read_text(encoding="utf-8")
    for row in load_mappings(folder):
        assert str(row["destination"]) in text
    assert "missing" in text


def test_measurement_skips_binary_suffixes(tmp_path):
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\x00\x01\x02")
    text = tmp_path / "note.md"
    text.write_text("hello world\n", encoding="utf-8")
    assert measure_file(binary).tokens == 0
    assert measure_file(text).tokens > 0


def test_resident_tokens_excludes_the_archive(folder):
    plan = build_plan(folder)
    apply_plan(folder, plan, approval_fingerprint=plan.fingerprint)
    with_archive = resident_tokens(folder)
    without = resident_tokens(folder, exclude=(archived_root(folder),))
    assert without < with_archive


def test_handoff_index_is_read_only(tmp_path):
    handoff = tmp_path / ".local" / ".agent" / "handoff"
    handoff.mkdir(parents=True)
    envelope = handoff / "L1__L2__demo-change__0001.yaml"
    envelope.write_text("subject: first dispatch\npayload: {}\n", encoding="utf-8")
    before = envelope.read_bytes()
    index, findings = write_handoff_index(tmp_path)
    assert findings == ()
    assert index is not None
    assert "first dispatch" in index.read_text(encoding="utf-8")
    assert envelope.read_bytes() == before


def test_handoff_index_renders_empty_state():
    assert "No envelopes." in render_handoff_index(())


def test_bloat_scan_flags_only_folders_over_threshold(tmp_path):
    tasks = tmp_path / ".local" / "tasks"
    (tasks / "small").mkdir(parents=True)
    (tasks / "small" / "note.md").write_text("tiny\n", encoding="utf-8")
    (tasks / "large").mkdir()
    (tasks / "large" / "note.md").write_text("word " * 5000, encoding="utf-8")
    findings = scan_bloat(tmp_path, threshold_tokens=1000)
    assert [item.folder for item in findings] == [".local/tasks/large"]
    assert "devola-compact plan" in suggestion_text(findings)
    assert "No workspace folder" in suggestion_text(())
    # The message must quote the threshold the scan actually used, not the
    # default, or every number in the report becomes suspect.
    assert "1500 resident tokens" in suggestion_text(findings, threshold=1500)
    assert "1500 resident tokens" in suggestion_text((), threshold=1500)


def test_bloat_scan_excludes_already_archived_content(tmp_path):
    task = tmp_path / ".local" / "tasks" / "t"
    task.mkdir(parents=True)
    (task / "live.md").write_text("word " * 3000, encoding="utf-8")
    archive = task / "compact" / "archived" / "0001"
    archive.mkdir(parents=True)
    (archive / "old.md").write_text("word " * 9000, encoding="utf-8")
    resident, _, _, archived = measure_folder(task)
    assert archived > resident
    assert scan_bloat(tmp_path, threshold_tokens=resident + 1) == ()


def test_console_plan_apply_verify_flow(folder, capsys):
    assert compact_main(["--folder", str(folder), "plan"]) == 0
    payload = capsys.readouterr().out
    fingerprint = payload.split('"fingerprint": "', 1)[1].split('"', 1)[0]
    assert compact_main(["--folder", str(folder), "apply", "--approve", fingerprint]) == 0
    assert compact_main(["--folder", str(folder), "verify"]) == 0
    assert '"zero_loss": true' in capsys.readouterr().out


def test_console_refuses_apply_without_matching_approval(folder, capsys):
    assert compact_main(["--folder", str(folder), "apply", "--approve", "bad"]) == 3
    assert "APPROVAL_MISMATCH" in capsys.readouterr().out


# --------------------------------------------------------------------------
# v24.1.0 — friction fixes found by dogfooding v24 on real workspaces
# --------------------------------------------------------------------------


def test_plan_surfaces_include_candidates_when_nothing_is_auto_eligible(tmp_path):
    """A folder that is too big but has no eligible entry must still say what to do.

    Every over-threshold folder in the real workspace planned to zero movable
    entries, because the weight sits in hand-written documents that automatic
    classification retains. `scan` said "run plan", `plan` said "nothing", and
    the `--include` escape hatch existed but appeared nowhere in the output.
    """
    target = tmp_path / "task"
    target.mkdir()
    (target / "goal.md").write_text("# goal\n", encoding="utf-8")
    (target / "design.md").write_text("# Superseded design\n" + "word " * 4000, encoding="utf-8")

    plan = build_plan(target)
    assert plan.movable == (), "precondition: nothing is automatically eligible here"

    candidates = plan.candidates
    assert [entry.source for entry in candidates] == ["design.md"], (
        "the heaviest retained non-canonical file must be offered as a candidate; "
        "goal.md is protected and must never appear"
    )
    assert candidates[0].summary == "Superseded design", (
        "a candidate needs a recognisable subject; a bare path does not tell the "
        "operator whether the file still earns its place in the reading path"
    )


def test_plan_prices_the_digest_it_would_write(tmp_path):
    """Relocation is not free: the plan must report what the digest costs.

    v24's retrospective measured a move that saved 432 tokens and spent nearly
    all of them on the digest it wrote. That reading was only available after
    the fact; here it is available before approval.
    """
    target = tmp_path / "task"
    target.mkdir()
    (target / "big.md").write_text("word " * 4000, encoding="utf-8")

    plan = build_plan(target, include=["big.md"])
    assert plan.movable_tokens > 0
    assert plan.digest_tokens > 0, "a plan that moves something must price its digest"
    assert plan.net_tokens == plan.movable_tokens - plan.digest_tokens
    assert plan.pays_for_itself


def test_a_move_smaller_than_its_digest_is_reported_as_not_paying(tmp_path):
    """The guard's whole point is the case where compacting makes things worse."""
    target = tmp_path / "task"
    target.mkdir()
    (target / "loops").mkdir()
    (target / "loops" / "tiny.md").write_text("ok\n", encoding="utf-8")

    plan = build_plan(target)
    assert plan.movable, "precondition: the historical-output file is eligible"
    assert plan.digest_tokens > plan.movable_tokens
    assert not plan.pays_for_itself
    assert plan.net_tokens < 0


def test_empty_plan_is_not_charged_for_a_digest(tmp_path):
    """`apply` refuses an empty approval, so no digest is written and none is priced."""
    target = tmp_path / "task"
    target.mkdir()
    (target / "goal.md").write_text("# goal\n", encoding="utf-8")

    plan = build_plan(target)
    assert plan.movable == ()
    assert plan.digest_tokens == 0
    assert plan.net_tokens == 0


def test_console_accepts_folder_after_the_subcommand(folder, capsys):
    """`devola-compact plan --folder X` must work, not only `--folder X plan`.

    The tool's own bloat suggestion printed the post-subcommand order, which
    argparse rejected with "unrecognized arguments" — the recommended
    invocation was the one that could not run.
    """
    assert compact_main(["plan", "--folder", str(folder)]) == 0
    after = capsys.readouterr().out
    assert compact_main(["--folder", str(folder), "plan"]) == 0
    assert capsys.readouterr().out == after, "both argument orders must agree exactly"


def test_bloat_finding_reports_overage_against_the_scan_threshold(tmp_path):
    """`over_by` must use the threshold the scan filtered on, not the module default."""
    task = tmp_path / ".local" / "tasks" / "t"
    task.mkdir(parents=True)
    (task / "notes.md").write_text("word " * 3000, encoding="utf-8")

    findings = scan_bloat(tmp_path, threshold_tokens=1000)
    assert findings
    assert findings[0].over_by == findings[0].tokens - 1000


def test_suggestion_text_points_at_the_include_escape_hatch(tmp_path):
    """The suggestion must lead somewhere; "run plan" alone dead-ends."""
    task = tmp_path / ".local" / "tasks" / "t"
    task.mkdir(parents=True)
    (task / "notes.md").write_text("word " * 3000, encoding="utf-8")

    text = suggestion_text(scan_bloat(tmp_path, threshold_tokens=1000), threshold=1000)
    assert "--include" in text
    assert "candidates" in text
