"""Pinned effort-weighted checklist progress header (v17.0.1).

Covers the derivation math, the idempotent refresh writer, the
``PROGRESS_HEADER`` lint family, and the store-side alignment hooks
(scaffold / revert / round boundary) that keep the header from going
stale through the canonical workflow write paths.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from devolaflow.agent_workspace.change import ChangeStore, ChangeStoreError
from devolaflow.agent_workspace.lint import SemanticViolation, lint_change
from devolaflow.agent_workspace.progress import (
    PROGRESS_HEADING,
    ProgressHeaderError,
    compute_progress_header,
    extract_progress_line,
    refresh_progress_header,
    render_progress_block,
    render_progress_line,
)
from devolaflow.agent_workspace.round_parser import (
    RoundArtifactParseError,
    parse_checklist,
    parse_stage,
)
from devolaflow.skills.slash_commands import scaffold_change_folder

CHANGE_ID = "progress-header"

_ALIGNED_LINE = (
    "`[███████████████▓▓▓▓▓] 75%` — done 1 | doing 1 | todo 0 | total 2 (effort-weighted)"
)


def _checklist_text(*, header_line: str | None = None, effort_line: str = "      effort: 3") -> str:
    header_block = "" if header_line is None else f"## Progress\n\n{header_line}\n\n"
    return (
        "---\n"
        f"parent: {CHANGE_ID}\n"
        "schema_version: 1\n"
        "total_items: 2\n"
        "checked: 1\n"
        "priority_dist: {P0: 1, P1: 1, P2: 0}\n"
        "reverted_open: 0\n"
        "---\n"
        "\n"
        "# Checklist\n"
        "\n"
        f"{header_block}"
        "## G1: Ship the progress header\n"
        "- [x] C-G1.1 (P0) Derivation math is pinned by tests\n"
        "      verify: `python -m pytest tests/test_agent_workspace_progress_header.py -q`\n"
        f"{effort_line}\n"
        "      evidence: evidence/C-G1.1.txt | checked_by: L0 | round: 1 "
        "| at: 2026-08-26T00:00:00Z\n"
        "- [ ] C-G1.2 (P1) The refresh writer is idempotent\n"
        "      verify: metric: refresh_twice == refresh_once\n"
    )


def _stage_text(*, current_round: int = 1, with_row: bool = True) -> str:
    row = "| 1 | C-G1.1(P0), C-G1.2(P1) | W1 | 1/2 | 0 | cp_r1 | - |\n" if with_row else ""
    return (
        "---\n"
        f"parent: {CHANGE_ID}\n"
        "schema_version: 1\n"
        f"current_round: {current_round}\n"
        "max_rounds: 3\n"
        "capacity_per_round: 5\n"
        "---\n"
        "\n"
        "# Stage — Round Control\n"
        "\n"
        "## Priority Settings\n"
        "- 2026-08-26T00:00:00Z initial: P0=[C-G1.1] P1=[C-G1.2] P2=[]\n"
        "\n"
        "## Round History\n"
        "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |\n"
        "|---|---|---|---|---|---|---|\n"
        f"{row}"
        "\n"
        "## Next Round Plan\n"
        "- Candidates: [C-G1.2]\n"
    )


def _write_change(tmp_path: Path, checklist_md: str, stage_md: str) -> tuple[ChangeStore, Path]:
    folder = tmp_path / ".local" / ".agent" / "active" / CHANGE_ID
    folder.mkdir(parents=True)
    (folder / "checklist.md").write_text(checklist_md, encoding="utf-8")
    (folder / "stage.md").write_text(stage_md, encoding="utf-8")
    (folder / "STATUS.yaml").write_text(
        "schema_version: 2\n"
        f"change_id: {CHANGE_ID}\n"
        "state: IN_PROGRESS\n"
        "checklist_checked: 1\n"
        "checklist_total: 2\n"
        "current_round: 1\n",
        encoding="utf-8",
    )
    return ChangeStore(repo_root=tmp_path), folder


# ---------------------------------------------------------------------------
# Effort metadata parsing
# ---------------------------------------------------------------------------


def test_effort_metadata_defaults_to_one_and_parses_declared_values() -> None:
    document = parse_checklist(_checklist_text())
    assert [item.effort for item in document.items] == [3, 1]


@pytest.mark.parametrize("bad_effort", ["0", "9", "3.5", "high", ""])
def test_invalid_effort_metadata_raises_in_strict_parse(bad_effort: str) -> None:
    text = _checklist_text(effort_line=f"      effort: {bad_effort}")
    with pytest.raises(RoundArtifactParseError, match="effort metadata"):
        parse_checklist(text)


# ---------------------------------------------------------------------------
# Derivation + rendering
# ---------------------------------------------------------------------------


def test_compute_progress_header_weights_bar_and_percent_by_effort() -> None:
    items = parse_checklist(_checklist_text()).items
    stage = parse_stage(_stage_text())
    header = compute_progress_header(items, stage)

    assert (header.done, header.doing, header.todo, header.total) == (1, 1, 0, 2)
    assert (header.done_effort, header.doing_effort, header.total_effort) == (3, 1, 4)
    assert header.percent == 75
    assert header.bar == "█" * 15 + "▓" * 5
    assert render_progress_line(header) == _ALIGNED_LINE
    assert render_progress_block(header) == f"{PROGRESS_HEADING}\n\n{_ALIGNED_LINE}"


def test_compute_progress_header_without_stage_reports_no_doing() -> None:
    items = parse_checklist(_checklist_text()).items
    header = compute_progress_header(items, None)
    assert (header.done, header.doing, header.todo) == (1, 0, 1)
    assert header.percent == 75
    assert header.bar == "█" * 15 + "░" * 5

    empty = compute_progress_header((), None)
    assert (empty.percent, empty.bar) == (0, "░" * 20)


def test_compute_progress_header_ignores_history_rows_of_other_rounds() -> None:
    items = parse_checklist(_checklist_text()).items
    stage = parse_stage(_stage_text(current_round=2))
    header = compute_progress_header(items, stage)
    assert header.doing == 0


# ---------------------------------------------------------------------------
# Refresh writer
# ---------------------------------------------------------------------------


def test_refresh_inserts_header_directly_after_h1() -> None:
    refreshed = refresh_progress_header(_checklist_text(), _stage_text())
    body = refreshed.split("---\n", 2)[2]
    assert body.startswith(f"\n# Checklist\n\n{PROGRESS_HEADING}\n\n{_ALIGNED_LINE}\n\n## G1:")
    assert extract_progress_line(body) == _ALIGNED_LINE
    # The parsed contract is unchanged: same items, same metadata.
    assert parse_checklist(refreshed).items == parse_checklist(_checklist_text()).items


def test_refresh_replaces_stale_header_and_is_idempotent() -> None:
    stale = _checklist_text(header_line="`[░░░░░░░░░░░░░░░░░░░░] 0%` — stale")
    once = refresh_progress_header(stale, _stage_text())
    twice = refresh_progress_header(once, _stage_text())
    assert extract_progress_line(once) == _ALIGNED_LINE
    assert once == twice
    assert once == refresh_progress_header(_checklist_text(), _stage_text())


def test_refresh_with_malformed_stage_degrades_loudly_to_no_doing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="devolaflow.agent_workspace.progress"):
        refreshed = refresh_progress_header(_checklist_text(), "# not a stage artifact\n")
    assert "stage.md failed to parse" in caplog.text
    assert "doing 0" in extract_progress_line(refreshed)


def test_refresh_rejects_missing_h1_and_duplicate_headings() -> None:
    without_h1 = _checklist_text().replace("# Checklist\n", "# Tracker\n", 1)
    with pytest.raises(ProgressHeaderError, match="'# Checklist' H1"):
        refresh_progress_header(without_h1)

    duplicated = _checklist_text(
        header_line=f"{_ALIGNED_LINE}\n\n{PROGRESS_HEADING}\n\n{_ALIGNED_LINE}"
    )
    with pytest.raises(ProgressHeaderError, match="at most one"):
        refresh_progress_header(duplicated)


# ---------------------------------------------------------------------------
# PROGRESS_HEADER lint family
# ---------------------------------------------------------------------------


def _progress_findings(tmp_path: Path, change_id: str) -> list[str]:
    report = lint_change(change_id, repo_root=tmp_path)
    return [
        violation.message
        for violation in report.violations
        if isinstance(violation, SemanticViolation) and violation.kind == "PROGRESS_HEADER"
    ]


def test_lint_accepts_scaffold_and_flags_missing_header(tmp_path: Path) -> None:
    folder = scaffold_change_folder("Progress Header", tmp_path, change_id=CHANGE_ID)
    checklist_path = folder / "checklist.md"
    scaffolded = checklist_path.read_text(encoding="utf-8")
    assert extract_progress_line(scaffolded) == (
        "`[░░░░░░░░░░░░░░░░░░░░] 0%` — done 0 | doing 0 | todo 1 | total 1 (effort-weighted)"
    )
    assert _progress_findings(tmp_path, CHANGE_ID) == []

    lines = [
        line
        for line in scaffolded.splitlines()
        if line != PROGRESS_HEADING and not line.startswith("`[")
    ]
    checklist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert _progress_findings(tmp_path, CHANGE_ID) == [
        "checklist.md must pin a '## Progress' section directly after '# Checklist'"
    ]


@pytest.mark.parametrize(
    ("case", "expected_fragment"),
    [
        ("stale-counts", "progress line is stale or malformed"),
        ("invalid-effort", "effort metadata must be an integer between 1 and 8"),
        ("duplicate-heading", "exactly one '## Progress' heading"),
        ("misplaced-heading", "must precede the first goal partition"),
    ],
)
def test_lint_flags_header_drift(tmp_path: Path, case: str, expected_fragment: str) -> None:
    folder = scaffold_change_folder("Progress Header", tmp_path, change_id=CHANGE_ID)
    checklist_path = folder / "checklist.md"
    text = checklist_path.read_text(encoding="utf-8")

    if case == "stale-counts":
        text = text.replace("done 0 | doing 0 | todo 1", "done 1 | doing 0 | todo 0", 1)
    elif case == "invalid-effort":
        text = text.replace("      verify: manual", "      verify: manual\n      effort: 9", 1)
    elif case == "duplicate-heading":
        text = text + f"\n{PROGRESS_HEADING}\n"
    elif case == "misplaced-heading":
        line = extract_progress_line(text)
        block = f"{PROGRESS_HEADING}\n\n{line}\n\n"
        text = text.replace(block, "", 1) + f"\n{PROGRESS_HEADING}\n\n{line}\n"

    checklist_path.write_text(text, encoding="utf-8")
    findings = _progress_findings(tmp_path, CHANGE_ID)
    assert any(expected_fragment in message for message in findings), findings


def test_lint_verifies_effort_weighted_line_against_in_flight_round(tmp_path: Path) -> None:
    folder = scaffold_change_folder("Progress Header", tmp_path, change_id=CHANGE_ID)
    (folder / "stage.md").write_text(
        "---\n"
        f"parent: {CHANGE_ID}\n"
        "schema_version: 1\n"
        "current_round: 1\n"
        "max_rounds: 3\n"
        "capacity_per_round: 5\n"
        "---\n"
        "\n"
        "# Stage — Round Control\n"
        "\n"
        "## Priority Settings\n"
        "- 2026-08-26T00:00:00Z initial: P0=[] P1=[C-G1.1] P2=[]\n"
        "\n"
        "## Round History\n"
        "| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |\n"
        "|---|---|---|---|---|---|---|\n"
        "| 1 | C-G1.1(P1) | W1 | 0/1 | 0 | cp_r1 | - |\n"
        "\n"
        "## Next Round Plan\n"
        "- Candidates: [C-G1.1]\n",
        encoding="utf-8",
    )
    checklist_path = folder / "checklist.md"

    # Header still shows todo — stale against the in-flight round pick.
    assert _progress_findings(tmp_path, CHANGE_ID) != []

    refreshed = refresh_progress_header(
        checklist_path.read_text(encoding="utf-8"),
        (folder / "stage.md").read_text(encoding="utf-8"),
    )
    checklist_path.write_text(refreshed, encoding="utf-8")
    assert extract_progress_line(refreshed) == (
        "`[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 0%` — done 0 | doing 1 | todo 0 | total 1 (effort-weighted)"
    )
    assert _progress_findings(tmp_path, CHANGE_ID) == []


# ---------------------------------------------------------------------------
# Store-side alignment hooks
# ---------------------------------------------------------------------------


def test_store_refresh_progress_header_persists_and_noops(tmp_path: Path) -> None:
    store, folder = _write_change(tmp_path, _checklist_text(), _stage_text())
    checklist_path = folder / "checklist.md"

    store.refresh_progress_header(CHANGE_ID)
    aligned = checklist_path.read_bytes()
    assert extract_progress_line(aligned.decode("utf-8")) == _ALIGNED_LINE

    store.refresh_progress_header(CHANGE_ID)
    assert checklist_path.read_bytes() == aligned

    checklist_path.write_text("no frontmatter\n", encoding="utf-8")
    with pytest.raises(ChangeStoreError, match="cannot refresh progress header"):
        store.refresh_progress_header(CHANGE_ID)


def test_reconcile_round_boundary_realigns_header(tmp_path: Path) -> None:
    stale = _checklist_text(header_line="`[░░░░░░░░░░░░░░░░░░░░] 0%` — stale")
    store, folder = _write_change(tmp_path, stale, _stage_text())

    updated = store.reconcile_round_boundary(CHANGE_ID, at="2026-08-26T00:05:00Z")

    on_disk = (folder / "checklist.md").read_text(encoding="utf-8")
    assert extract_progress_line(on_disk) == _ALIGNED_LINE
    assert updated.checklist_md == on_disk
    assert updated.status["checklist_checked"] == 1
    assert updated.status["current_round"] == 1


def test_store_revert_realigns_header_with_reopened_item(tmp_path: Path) -> None:
    aligned = refresh_progress_header(_checklist_text(), _stage_text())
    store, folder = _write_change(tmp_path, aligned, _stage_text())

    store.revert_checklist_item(
        CHANGE_ID,
        "C-G1.1",
        "needs a second pass",
        actor="user",
        at="2026-08-26T00:10:00Z",
    )

    on_disk = (folder / "checklist.md").read_text(encoding="utf-8")
    # Both items reopened + picked in round 1 → everything is doing.
    assert extract_progress_line(on_disk) == (
        "`[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 0%` — done 0 | doing 2 | todo 0 | total 2 (effort-weighted)"
    )
    assert "reverted: needs a second pass" in on_disk
