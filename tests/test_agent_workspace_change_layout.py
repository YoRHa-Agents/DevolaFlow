"""Focused checklist-layout tests for v17 agent-workspace change storage."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace import (
    ARTIFACT_FILES_V16,
    ArchiveManager,
    Change,
    ChangeLayout,
    ChangeNotFoundError,
    ChangeStore,
    ChangeStoreError,
    LegacyChangeLayoutError,
    detect_change_layout,
    lint_change,
    parse_checklist,
)
from devolaflow.agent_workspace.lint import (
    CHECKLIST_ARTIFACT_BUDGETS,
    EVIDENCE_DIRECTORY_MAX_BYTES,
    EVIDENCE_FILE_MAX_BYTES,
)
from devolaflow.skills.slash_commands import scaffold_change_folder

CHECKLIST_ARTIFACTS = (
    "goal.md",
    "checklist.md",
    "stage.md",
    "preflight.md",
    "spec.md",
    "STATUS.yaml",
    "owned_files.txt",
    "learnings.jsonl",
)


def _status(change_id: str, *, state: str = "IN_PROGRESS") -> dict:
    return {
        "schema_version": 2,
        "change_id": change_id,
        "state": state,
        "percent_complete": 100,
        "owner_layer": "L2",
        "owner_session_id": "layout-test",
        "last_updated": "2026-08-24T12:00:00Z",
        "last_handoff_seq": 0,
        "gate_score": 9.0,
        "verify_pass": state == "VERIFYING",
        "checklist_checked": 1,
        "checklist_total": 1,
        "current_round": 1,
        "next_blockers": [],
    }


def _write_common(folder: Path, change_id: str, *, state: str = "IN_PROGRESS") -> None:
    folder.mkdir(parents=True)
    (folder / "goal.md").write_text(f"# Goal: {change_id}\n", encoding="utf-8")
    (folder / "spec.md").write_text(f"# Spec: {change_id}\n", encoding="utf-8")
    (folder / "STATUS.yaml").write_text(
        yaml.safe_dump(_status(change_id, state=state), sort_keys=False),
        encoding="utf-8",
    )
    (folder / "owned_files.txt").write_text(
        "src/devolaflow/agent_workspace/change.py\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_legacy(folder: Path, change_id: str) -> Path:
    _write_common(folder, change_id)
    (folder / "acceptance.md").write_text("# Acceptance\n", encoding="utf-8")
    (folder / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    return folder


def _write_checklist(
    folder: Path,
    change_id: str,
    *,
    state: str = "IN_PROGRESS",
    evidence: dict[str, str] | None = None,
) -> Path:
    _write_common(folder, change_id, state=state)
    (folder / "checklist.md").write_text("# Checklist\n", encoding="utf-8")
    (folder / "stage.md").write_text("# Stage — Round Control\n", encoding="utf-8")
    (folder / "preflight.md").write_text("# Preflight\n", encoding="utf-8")
    evidence_dir = folder / "evidence"
    evidence_dir.mkdir()
    for basename, text in (evidence or {}).items():
        (evidence_dir / basename).write_text(text, encoding="utf-8")
    return folder


def _canonical_checklist(
    *,
    checked: bool,
    frontmatter_checked: int,
    frontmatter_reverted: int,
) -> str:
    checkbox = "x" if checked else " "
    completion = (
        "      evidence: evidence/C-G1.1.txt | checked_by: user | round: 2 "
        "| at: 2026-08-24T11:00:00Z\n"
        if checked
        else ""
    )
    prior_revert = (
        "      reverted: Reopen this exact assertion. | at: 2026-08-24T10:30:00Z\n"
        if checked
        else ""
    )
    return f"""\
---
parent: guarded-change
schema_version: 1
total_items: 1
checked: {frontmatter_checked}
priority_dist: {{P0: 1, P1: 0, P2: 0}}
reverted_open: {frontmatter_reverted}
---

# Checklist

## G1: Guard state from the parsed checklist body
- [{checkbox}] C-G1.1 (P0) The parsed body controls lifecycle readiness
      verify: manual
{prior_revert}{completion}"""


def _canonical_stage() -> str:
    return """\
---
parent: guarded-change
schema_version: 1
current_round: 2
max_rounds: 4
capacity_per_round: 5
---

# Stage — Round Control

## Priority Settings
- 2026-08-24T09:00:00Z initial: P0=[C-G1.1] P1=[] P2=[]

## Round History
| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |
|---|---|---|---|---|---|---|

## Next Round Plan
- Candidates: []
- Estimated remaining rounds: 0
"""


@pytest.mark.parametrize(
    ("markers", "expected"),
    [
        ((), ChangeLayout.CHECKLIST),
        (("checklist.md",), ChangeLayout.CHECKLIST),
        (("tasks.md",), LegacyChangeLayoutError),
        (("acceptance.md",), LegacyChangeLayoutError),
        (("tasks.md", "acceptance.md"), LegacyChangeLayoutError),
        (("checklist.md", "tasks.md"), ChangeLayout.INVALID_MIXED),
        (("checklist.md", "acceptance.md"), ChangeLayout.INVALID_MIXED),
    ],
)
def test_detect_change_layout(marker_folder: Path, markers: tuple[str, ...], expected) -> None:
    marker_folder.mkdir()
    for marker in markers:
        (marker_folder / marker).write_text("", encoding="utf-8")
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected, match=r"removed in v17\.0\.0"):
            detect_change_layout(marker_folder)
    else:
        assert detect_change_layout(marker_folder) is expected


@pytest.fixture
def marker_folder(tmp_path: Path) -> Path:
    return tmp_path / "layout-case"


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_detect_change_layout_rejects_non_directory(tmp_path: Path, kind: str) -> None:
    target = tmp_path / kind
    if kind == "file":
        target.write_text("", encoding="utf-8")
    with pytest.raises(ChangeNotFoundError):
        detect_change_layout(target)


def test_legacy_layout_raises_removal_error(tmp_path: Path) -> None:
    assert [layout.value for layout in ChangeLayout] == [
        "CHECKLIST",
        "INVALID_MIXED",
    ]
    assert Change("checklist-default").layout is ChangeLayout.CHECKLIST

    folder = _write_legacy(tmp_path / "legacy-change", "legacy-change")
    with pytest.raises(
        LegacyChangeLayoutError,
        match=r"tasks\.md/acceptance\.md dual-track removed in v17\.0\.0; "
        r"migrate to\s+checklist\.md",
    ):
        detect_change_layout(folder)
    with pytest.raises(LegacyChangeLayoutError, match="removed in v17"):
        Change.from_active_folder(folder)
    assert issubclass(LegacyChangeLayoutError, ChangeStoreError)


def test_checklist_load_roundtrip_uses_only_v16_artifacts_and_verbatim_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = {
        "C-G1.1.txt": "命令: pytest\nfinal line without newline",
        "C-G1.2.txt": "digest=abc123\n",
    }
    source = _write_checklist(tmp_path / "checklist-source", "checklist-source", evidence=evidence)

    change = Change.from_active_folder(source)
    assert change.layout is ChangeLayout.CHECKLIST
    assert change.evidence_files == evidence
    assert ARTIFACT_FILES_V16 == CHECKLIST_ARTIFACTS

    target = tmp_path / "checklist-target"
    hooked: list[str] = []
    monkeypatch.setattr(
        "devolaflow.agent_workspace.change._fire_file_write_hook",
        lambda path, _owned_files, change_folder: hooked.append(
            path.relative_to(change_folder).as_posix()
        ),
    )
    change.to_active_folder(target)
    assert not (target / "acceptance.md").exists()
    assert not (target / "tasks.md").exists()
    for filename in CHECKLIST_ARTIFACTS[:-1]:
        assert (target / filename).read_bytes() == (source / filename).read_bytes()
    for basename, text in evidence.items():
        assert (target / "evidence" / basename).read_text(encoding="utf-8") == text
    assert hooked == [
        "goal.md",
        "checklist.md",
        "stage.md",
        "preflight.md",
        "spec.md",
        "STATUS.yaml",
        "owned_files.txt",
        "evidence/C-G1.1.txt",
        "evidence/C-G1.2.txt",
    ]


def test_mixed_layout_is_detected_and_rejected_explicitly(tmp_path: Path) -> None:
    folder = _write_checklist(tmp_path / "mixed-layout", "mixed-layout")
    (folder / "tasks.md").write_text("# legacy task\n", encoding="utf-8")

    assert detect_change_layout(folder) is ChangeLayout.INVALID_MIXED
    with pytest.raises(ChangeStoreError, match="INVALID_MIXED"):
        Change.from_active_folder(folder)


def test_to_active_folder_refuses_implicit_layout_migration(tmp_path: Path) -> None:
    target = _write_legacy(tmp_path / "existing-target", "existing-target")
    checklist = Change(
        change_id="existing-target",
        status=_status("existing-target"),
        layout=ChangeLayout.CHECKLIST,
        checklist_md="# Checklist\n",
    )

    with pytest.raises(LegacyChangeLayoutError, match=r"removed in v17\.0\.0"):
        checklist.to_active_folder(target)
    assert (target / "tasks.md").read_text(encoding="utf-8") == "# Tasks\n"
    assert not (target / "checklist.md").exists()


def test_with_state_and_store_preserve_checklist_layout(tmp_path: Path) -> None:
    active = tmp_path / ".local" / ".agent" / "active"
    checklist_path = _write_checklist(
        active / "checklist-change",
        "checklist-change",
        evidence={"C-G1.1.txt": "PASS\n"},
    )
    store = ChangeStore(repo_root=tmp_path)

    checklist = store.get("checklist-change")
    updated = checklist.with_state("VERIFYING")

    assert checklist.layout is ChangeLayout.CHECKLIST
    assert checklist.source_folder == checklist_path
    assert updated.layout is ChangeLayout.CHECKLIST
    assert updated.checklist_md == checklist.checklist_md
    assert updated.stage_md == checklist.stage_md
    assert updated.preflight_md == checklist.preflight_md
    assert updated.evidence_files == checklist.evidence_files
    assert updated.evidence_files is not checklist.evidence_files


def test_checklist_lint_uses_v16_budgets_and_evidence_limits(tmp_path: Path) -> None:
    assert CHECKLIST_ARTIFACT_BUDGETS == {
        "goal.md": (200, 400),
        "checklist.md": (1200, 2400),
        "stage.md": (400, 800),
        "preflight.md": (600, 1200),
        "spec.md": (1500, 3000),
        "STATUS.yaml": (150, 300),
        "owned_files.txt": (50, 100),
        # OPTIONAL harness pre-analysis artifact (harness-construction).
        "harness_preflight.md": (800, 1600),
    }
    assert EVIDENCE_FILE_MAX_BYTES == 10_240
    assert EVIDENCE_DIRECTORY_MAX_BYTES == 51_200

    folder = scaffold_change_folder("lint checklist", tmp_path)
    (folder / "preflight.md").write_text("x" * (1200 * 4 + 4), encoding="utf-8")
    for index in range(5):
        (folder / "evidence" / f"C-G1.{index + 1}.txt").write_bytes(
            b"x" * (EVIDENCE_FILE_MAX_BYTES + 1)
        )

    report = lint_change("lint-checklist", repo_root=tmp_path)

    assert "acceptance.md" not in report.checked_files
    assert "tasks.md" not in report.checked_files
    assert any(
        violation.filename == "preflight.md"
        and violation.severity == "FAIL"
        and getattr(violation, "hard_budget", None) == 1200
        for violation in report.violations
    )
    assert (
        sum(
            getattr(violation, "kind", None) == "EVIDENCE_FILE_SIZE"
            for violation in report.violations
        )
        == 5
    )
    assert any(
        getattr(violation, "kind", None) == "EVIDENCE_DIRECTORY_SIZE"
        for violation in report.violations
    )


def test_archive_manager_preserves_checklist_artifacts_and_evidence(tmp_path: Path) -> None:
    active = tmp_path / ".local" / ".agent" / "active"
    source = _write_checklist(
        active / "archive-checklist",
        "archive-checklist",
        state="VERIFYING",
        evidence={"C-G1.1.txt": "verify: pytest\nPASS\n"},
    )
    before = {
        relative: (source / relative).read_bytes()
        for relative in (
            "goal.md",
            "checklist.md",
            "stage.md",
            "preflight.md",
            "spec.md",
            "owned_files.txt",
            "evidence/C-G1.1.txt",
        )
    }
    manager = ArchiveManager(store=ChangeStore(repo_root=tmp_path))

    result = manager.archive(
        "archive-checklist",
        archive_date="2026-08-24",
        auto_regenerate_reports=False,
    )

    assert not source.exists()
    for relative, content in before.items():
        assert (result.archive_path / relative).read_bytes() == content
    archived = manager.store.get("archive-checklist")
    assert archived.layout is ChangeLayout.CHECKLIST
    assert archived.state == "ARCHIVED"
    assert archived.evidence_files == {"C-G1.1.txt": "verify: pytest\nPASS\n"}


def test_store_guards_verifying_and_reconciles_user_revert_at_round_boundary(
    tmp_path: Path,
) -> None:
    active = tmp_path / ".local" / ".agent" / "active"
    folder = _write_checklist(active / "guarded-change", "guarded-change")
    checklist_path = folder / "checklist.md"
    stage_path = folder / "stage.md"
    checklist_path.write_text(
        _canonical_checklist(
            checked=False,
            frontmatter_checked=1,
            frontmatter_reverted=0,
        ),
        encoding="utf-8",
    )
    stage_path.write_text(_canonical_stage(), encoding="utf-8")
    store = ChangeStore(repo_root=tmp_path)

    with pytest.raises(ChangeStoreError, match="CHECKLIST_NOT_READY"):
        store.transition_state("guarded-change", "VERIFYING")

    checklist_path.write_text(
        _canonical_checklist(
            checked=True,
            frontmatter_checked=0,
            frontmatter_reverted=1,
        ),
        encoding="utf-8",
    )
    verifying = store.transition_state("guarded-change", "VERIFYING")
    assert verifying.state == "VERIFYING"
    assert verifying.status["checklist_checked"] == 1
    assert verifying.status["checklist_total"] == 1
    assert verifying.status["percent_complete"] == 100

    stage_before = stage_path.read_bytes()
    with pytest.raises(ValueError, match="REVERT_ACTOR_FORBIDDEN"):
        store.revert_checklist_item(
            "guarded-change",
            "C-G1.1",
            "dispatcher may not reopen",
            actor="L0",
            at="2026-08-24T12:00:00Z",
        )

    reverted = store.revert_checklist_item(
        "guarded-change",
        "C-G1.1",
        'Preserve "verbatim" -> reason.',
        actor="user",
        at="2026-08-24T12:00:00Z",
    )
    parsed = parse_checklist(reverted.checklist_md)
    assert parsed.artifact.frontmatter["checked"] == 0
    assert parsed.artifact.frontmatter["reverted_open"] == 1
    assert parsed.items[0].reverted_reason == 'Preserve "verbatim" -> reason.'
    assert store.get("guarded-change").state == "VERIFYING"
    assert stage_path.read_bytes() == stage_before

    reconciled = store.reconcile_round_boundary(
        "guarded-change",
        at="2026-08-24T12:05:00Z",
    )
    assert reconciled.state == "IN_PROGRESS"
    assert reconciled.status["checklist_checked"] == 0
    assert reconciled.status["checklist_total"] == 1
    assert reconciled.status["percent_complete"] == 0
    assert reconciled.status["current_round"] == 2
    assert reconciled.status["gate_score"] is None
    assert reconciled.status["verify_pass"] is None
    assert stage_path.read_bytes() == stage_before
