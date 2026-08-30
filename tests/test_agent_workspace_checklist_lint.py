"""Focused tests for checklist-layout agent-workspace linting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import devolaflow.agent_workspace.preflight as preflight_module
from devolaflow.agent_workspace import (
    LegacyChangeLayoutError,
    PreflightAuthorization,
    PreflightAuthorizationError,
    PreflightConfigBaseline,
    draft_preflight_section0,
    invalidate_preflight,
    sign_preflight,
)
from devolaflow.agent_workspace.lint import (
    CHECKLIST_ARTIFACT_BUDGETS,
    EVIDENCE_DIRECTORY_MAX_BYTES,
    EVIDENCE_FILE_MAX_BYTES,
    LEARNINGS_JSONL_MAX_BYTES,
    BudgetViolation,
    SemanticViolation,
    lint_change,
)
from devolaflow.agent_workspace.lint import main as lint_main
from devolaflow.skills.slash_commands import _entrance_md, scaffold_change_folder

CHANGE_ID = "checklist-lint"
CHECKED_ITEM = "C-G1.1"
MIRROR_BYTES = b"project:\n  name: checklist-lint\n"


def _goal_text(*, goals_count: int = 2) -> str:
    return f"""\
---
id: {CHANGE_ID}
created: "2026-08-24T12:00:00Z"
priority: P2
intent_class: feature
goals_count: {goals_count}
---

# Goal: Exercise checklist lint contracts

## Why
The v16 checklist layout requires deterministic semantic validation.

## Goals
- G1: Validate evidence-backed completion → checklist.md ## G1
- G2: Preserve compatibility → checklist.md ## G2

## Out of scope
- Production implementation changes
"""


def _checklist_text(
    *,
    total_items: int = 3,
    checked: int = 1,
    priority_dist: str = "{P0: 1, P1: 1, P2: 1}",
    reverted_open: int = 0,
) -> str:
    return f"""\
---
parent: {CHANGE_ID}
schema_version: 1
total_items: {total_items}
checked: {checked}
priority_dist: {priority_dist}
reverted_open: {reverted_open}
---

# Checklist

## Progress

`[██████░░░░░░░░░░░░░░] 33%` — done 1 | doing 0 | todo 2 | total 3 (effort-weighted)

## G1: Validate evidence-backed completion
- [x] C-G1.1 (P0) Focused checklist lint passes
      verify: `python -m pytest tests/test_agent_workspace_checklist_lint.py -q`
      evidence: evidence/C-G1.1.txt | checked_by: L0 | round: 1 | at: 2026-08-24T12:05:00Z
- [ ] C-G1.2 (P1) Open checklist state remains measurable
      verify: metric: open_count == 0

## G2: Preserve compatibility
- [ ] C-G2.1 (P2) Legacy folders retain budget-only linting
      verify: manual
"""


def _preflight_text(
    *,
    authorized_at: str | None = "2026-08-24T12:00:00Z",
    project_config_hash: str | None = "matching",
    authorization_hash: str | None = "computed",
) -> str:
    if project_config_hash == "matching":
        project_config_hash = hashlib.sha256(MIRROR_BYTES).hexdigest()
    inherited_hash = (
        project_config_hash
        if isinstance(project_config_hash, str) and len(project_config_hash) == 64
        else hashlib.sha256(MIRROR_BYTES).hexdigest()
    )
    authorized_yaml = "null" if authorized_at is None else f'"{authorized_at}"'
    hash_yaml = "null" if project_config_hash is None else f'"{project_config_hash}"'
    sections_0_to_3 = (
        "## 0. Project Configuration\n"
        f"- Inherited from prior-change (signed 2026-08-23T12:00:00Z); config hash "
        f"{inherited_hash} matches; no drift.\n\n"
        "## 1. Stop Cards\n"
        "| ID | Category | Description | Checklist Items | Disposition |\n"
        "|---|---|---|---|---|\n\n"
        "## 2. Authorization Record\n\n"
        "## 3. Permitted Stops\n"
        "1. STOP-1: A Section 1 card with disposition=reserved_stop is reached.\n"
        "2. STOP-2: The two-round stagnation rule fires or max_rounds is reached.\n"
        "3. STOP-3: A FULL_ROLLBACK exception reports state corruption or data loss.\n"
        "4. STOP-4: The user reopens an item and the verbatim reverted reason "
        "explicitly instructs a stop."
    )
    if authorization_hash == "computed" and authorized_at is not None and project_config_hash:
        metadata = {
            "parent": CHANGE_ID,
            "schema_version": 1,
            "authorized_at": authorized_at,
            "config_inherited_from": "prior-change",
            "project_config_hash": project_config_hash,
        }
        seal_payload = (
            json.dumps(
                metadata,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=False,
            ).encode()
            + b"\n"
            + sections_0_to_3.encode()
        )
        authorization_hash = hashlib.sha256(seal_payload).hexdigest()
    elif authorization_hash == "computed":
        authorization_hash = None
    authorization_hash_yaml = "null" if authorization_hash is None else f'"{authorization_hash}"'
    return f"""\
---
parent: {CHANGE_ID}
schema_version: 1
authorized_at: {authorized_yaml}
snapshot_round: 1
config_inherited_from: prior-change
project_config_hash: {hash_yaml}
authorization_hash: {authorization_hash_yaml}
---

# Preflight

{sections_0_to_3}

## 4. Progress Snapshot
- Checked: 1/3 (P0: 1/1, P1: 0/1, P2: 0/1)
"""


def _scaffold_checklist(tmp_path: Path) -> Path:
    folder = tmp_path / ".local" / ".agent" / "active" / CHANGE_ID
    folder.mkdir(parents=True)
    (tmp_path / ".local" / "project_config.yaml").write_bytes(MIRROR_BYTES)

    artifacts = {
        "goal.md": _goal_text(),
        "checklist.md": _checklist_text(),
        "stage.md": """\
---
parent: checklist-lint
schema_version: 1
current_round: 1
max_rounds: 3
capacity_per_round: 5
---
# Stage — Round Control
""",
        "preflight.md": _preflight_text(),
        "spec.md": "# Operation Spec\n\n## ADDED Requirements\n",
        "STATUS.yaml": """\
schema_version: 2
change_id: checklist-lint
state: IN_PROGRESS
checklist_checked: 1
checklist_total: 3
current_round: 1
""",
        "owned_files.txt": "tests/test_agent_workspace_checklist_lint.py\n",
        "entrance.md": _entrance_md(CHANGE_ID, "Exercise checklist lint contracts"),
    }
    for filename, text in artifacts.items():
        (folder / filename).write_text(text, encoding="utf-8")

    evidence_dir = folder / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / f"{CHECKED_ITEM}.txt").write_text("PASS\n", encoding="utf-8")
    return folder


def _semantic_kinds(report) -> list[str]:
    return [
        violation.kind
        for violation in report.hard_failures
        if isinstance(violation, SemanticViolation)
    ]


def _section0_draft(repo_root: Path, change_id: str):
    return draft_preflight_section0(
        repo_root,
        project_name=change_id,
        project_purpose=f"Complete {change_id}",
        seed_mode="feature-enhancement",
    )


def _replace_section0(preflight_path: Path, markdown: str) -> None:
    text = preflight_path.read_text(encoding="utf-8")
    prefix, remainder = text.split("## 0. Project Configuration\n", 1)
    _old_section0, suffix = remainder.split("\n\n## 1. Stop Cards", 1)
    preflight_path.write_text(
        f"{prefix}## 0. Project Configuration\n{markdown}\n\n## 1. Stop Cards{suffix}",
        encoding="utf-8",
        newline="\n",
    )


def _authorization(quote: str = 'Approved "verbatim" with a \\ path') -> PreflightAuthorization:
    return PreflightAuthorization(
        card_id="PF-A1",
        disposition="reserved_stop",
        quote=quote,
    )


def _signed_prior(repo_root: Path) -> tuple[PreflightConfigBaseline, bytes]:
    prior_id = "prior-change"
    draft = _section0_draft(repo_root, prior_id)
    folder = scaffold_change_folder("Prior Change", repo_root, change_id=prior_id)
    signature = sign_preflight(
        repo_root,
        prior_id,
        draft=draft,
        authorizations=[_authorization()],
        authorized_at="2026-08-24T11:00:00Z",
    )
    baseline = PreflightConfigBaseline(
        change_id=prior_id,
        authorized_at=signature.authorized_at,
        project_config_hash=signature.project_config_hash,
        config=draft.config,
    )
    return baseline, (folder / "preflight.md").read_bytes()


@pytest.mark.parametrize("archived", [False, True], ids=["active", "archived"])
def test_valid_v16_checklist_layout_passes(tmp_path: Path, archived: bool) -> None:
    folder = _scaffold_checklist(tmp_path)
    if archived:
        (folder / "preflight.md").write_text(
            _preflight_text(project_config_hash="0" * 64),
            encoding="utf-8",
        )
        archived_folder = tmp_path / ".local" / ".agent" / "archive" / "2026-08-24-checklist-lint"
        archived_folder.parent.mkdir(parents=True)
        folder.rename(archived_folder)
        folder = archived_folder

    report = lint_change(CHANGE_ID, repo_root=tmp_path)

    assert report.exit_code == 0
    assert report.violations == []
    assert report.change_folder == folder
    assert set(CHECKLIST_ARTIFACT_BUDGETS) <= set(report.checked_files)
    assert f"evidence/{CHECKED_ITEM}.txt" in report.checked_files


def test_entrance_missing_fails_hard(tmp_path: Path) -> None:
    """Absent entrance.md is an ENTRANCE_MISSING hard failure."""
    folder = _scaffold_checklist(tmp_path)
    (folder / "entrance.md").unlink()

    report = lint_change(CHANGE_ID, repo_root=tmp_path)

    assert report.exit_code == 1
    failed = [
        violation
        for violation in report.hard_failures
        if isinstance(violation, SemanticViolation) and violation.kind == "ENTRANCE_MISSING"
    ]
    assert len(failed) == 1
    assert failed[0].severity == "FAIL"
    assert "materialize" in failed[0].message


@pytest.mark.parametrize(
    ("case", "old", "new", "expected_kind"),
    [
        (
            "parent-mismatch",
            f"parent: {CHANGE_ID}",
            "parent: other-change",
            "ENTRANCE_PARENT",
        ),
        (
            "schema-version",
            "schema_version: 1",
            "schema_version: 2",
            "ENTRANCE_SCHEMA_VERSION",
        ),
        (
            "section-absent",
            "## 4. Discipline Pointers",
            "## 4. Renamed Pointers",
            "ENTRANCE_SECTION",
        ),
        (
            "parity-missing-row",
            "| `spec.md` | Behaviour delta (Rule A-4) |\n",
            "",
            "ENTRANCE_PARITY",
        ),
        (
            "parity-surplus-row",
            "| `evidence/` | Per-item verification evidence |",
            "| `evidence/` | Per-item verification evidence |\n| `extra.md` | Bogus row |",
            "ENTRANCE_PARITY",
        ),
    ],
)
def test_entrance_semantic_violations_fail(
    tmp_path: Path,
    case: str,
    old: str,
    new: str,
    expected_kind: str,
) -> None:
    """A present-but-malformed entrance.md fails loud with its ENTRANCE_* kind."""
    folder = _scaffold_checklist(tmp_path)
    entrance_path = folder / "entrance.md"
    text = entrance_path.read_text(encoding="utf-8")
    assert old in text, f"fixture drift for case {case}: {old!r} not found"
    entrance_path.write_text(text.replace(old, new), encoding="utf-8")

    report = lint_change(CHANGE_ID, repo_root=tmp_path)

    assert report.exit_code == 1
    assert expected_kind in _semantic_kinds(report)


@pytest.mark.parametrize(
    ("case", "filename", "old", "new", "expected_kind"),
    [
        (
            "goal-link-id",
            "goal.md",
            "- G2: Preserve compatibility → checklist.md ## G2",
            "- G2: Preserve compatibility → checklist.md ## G1",
            "GOAL_ALIGNMENT",
        ),
        (
            "partition-title",
            "checklist.md",
            "## G2: Preserve compatibility",
            "## G2: Renamed partition",
            "GOAL_ALIGNMENT",
        ),
        (
            "partition-missing",
            "checklist.md",
            "## G2: Preserve compatibility",
            "## Notes",
            "GOAL_ALIGNMENT",
        ),
        (
            "partition-syntax",
            "checklist.md",
            "## G2: Preserve compatibility",
            "## G2 Preserve compatibility",
            "GOAL_ALIGNMENT",
        ),
        (
            "goals-section-missing",
            "goal.md",
            "## Goals",
            "## Outcomes",
            "GOAL_ALIGNMENT",
        ),
        (
            "frontmatter-opening",
            "goal.md",
            "---\n",
            "not-frontmatter\n",
            "FRONTMATTER_PARSE",
        ),
        (
            "frontmatter-closing",
            "goal.md",
            "goals_count: 2\n---",
            "goals_count: 2",
            "FRONTMATTER_PARSE",
        ),
        (
            "frontmatter-invalid-yaml",
            "goal.md",
            "goals_count: 2",
            "goals_count: [",
            "FRONTMATTER_PARSE",
        ),
        (
            "frontmatter-nonmapping",
            "preflight.md",
            None,
            None,
            "FRONTMATTER_PARSE",
        ),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_goal_and_partition_mismatches_fail(
    tmp_path: Path,
    case: str,
    filename: str,
    old: str | None,
    new: str | None,
    expected_kind: str,
) -> None:
    folder = _scaffold_checklist(tmp_path)
    target = folder / filename
    if case == "frontmatter-nonmapping":
        target.write_text("---\n- first\n- second\n---\n\n# Preflight\n", encoding="utf-8")
    else:
        assert old is not None and new is not None
        target.write_text(
            target.read_text(encoding="utf-8").replace(old, new, 1),
            encoding="utf-8",
        )

    report = lint_change(CHANGE_ID, repo_root=tmp_path)
    kinds = _semantic_kinds(report)

    assert report.exit_code == 1
    assert expected_kind in kinds
    if expected_kind == "FRONTMATTER_PARSE":
        assert kinds == ["FRONTMATTER_PARSE"]


@pytest.mark.parametrize(
    ("filename", "old", "new", "field_name"),
    [
        ("goal.md", "goals_count: 2", "goals_count: 3", "goals_count"),
        ("checklist.md", "total_items: 3", "total_items: 4", "total_items"),
        ("checklist.md", "checked: 1", "checked: 2", "checked"),
        (
            "checklist.md",
            "priority_dist: {P0: 1, P1: 1, P2: 1}",
            "priority_dist: {P0: 2, P1: 0, P2: 1}",
            "priority_dist",
        ),
        (
            "checklist.md",
            "      verify: metric: open_count == 0",
            "      verify: metric: open_count == 0\n"
            "      reverted: retry required | at: 2026-08-24T12:10:00Z",
            "reverted_open",
        ),
        ("goal.md", "goals_count: 2", "goals_count: true", "goals_count"),
    ],
    ids=["goal-count", "total", "checked", "priorities", "reverted", "strict-int-type"],
)
def test_body_derived_frontmatter_mismatches_fail(
    tmp_path: Path,
    filename: str,
    old: str,
    new: str,
    field_name: str,
) -> None:
    folder = _scaffold_checklist(tmp_path)
    target = folder / filename
    target.write_text(target.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    report = lint_change(CHANGE_ID, repo_root=tmp_path)
    findings = [
        violation
        for violation in report.hard_failures
        if isinstance(violation, SemanticViolation) and violation.kind == "DERIVED_FIELD"
    ]

    assert report.exit_code == 1
    assert any(field_name in finding.message for finding in findings)


@pytest.mark.parametrize(
    ("case", "expected_kind"),
    [
        ("missing", "EVIDENCE_PATH"),
        ("mismatched-declaration", "EVIDENCE_PATH"),
        ("malformed-declaration", "EVIDENCE_PATH"),
        ("duplicate-declaration", "EVIDENCE_PATH"),
        ("symlink", "EVIDENCE_PATH"),
        ("directory-is-file", "EVIDENCE_DIRECTORY"),
        ("directory-symlink", "EVIDENCE_DIRECTORY"),
        ("nested-directory", None),
        ("file-at-limit", None),
        ("file-over-limit", "EVIDENCE_FILE_SIZE"),
        ("directory-at-limit", None),
        ("directory-over-limit", "EVIDENCE_DIRECTORY_SIZE"),
    ],
)
def test_checked_evidence_paths_and_size_boundaries(
    tmp_path: Path,
    case: str,
    expected_kind: str | None,
) -> None:
    folder = _scaffold_checklist(tmp_path)
    evidence_dir = folder / "evidence"
    target = evidence_dir / f"{CHECKED_ITEM}.txt"

    if case == "missing":
        target.unlink()
    elif case == "mismatched-declaration":
        checklist = folder / "checklist.md"
        checklist.write_text(
            checklist.read_text(encoding="utf-8").replace(
                f"evidence/{CHECKED_ITEM}.txt",
                "evidence/C-G2.1.txt",
            ),
            encoding="utf-8",
        )
    elif case == "malformed-declaration":
        checklist = folder / "checklist.md"
        checklist.write_text(
            checklist.read_text(encoding="utf-8").replace(
                f"evidence: evidence/{CHECKED_ITEM}.txt |",
                f"evidence: evidence/{CHECKED_ITEM}.txt malformed |",
            ),
            encoding="utf-8",
        )
    elif case == "duplicate-declaration":
        checklist = folder / "checklist.md"
        checklist.write_text(
            checklist.read_text(encoding="utf-8").replace(
                f"      evidence: evidence/{CHECKED_ITEM}.txt |",
                f"      evidence: evidence/{CHECKED_ITEM}.txt |\n"
                f"      evidence: evidence/{CHECKED_ITEM}.txt |",
            ),
            encoding="utf-8",
        )
    elif case == "symlink":
        target.unlink()
        outside = tmp_path / "outside-evidence.txt"
        outside.write_text("PASS\n", encoding="utf-8")
        target.symlink_to(outside)
    elif case == "directory-is-file":
        target.unlink()
        evidence_dir.rmdir()
        evidence_dir.write_text("not a directory\n", encoding="utf-8")
    elif case == "directory-symlink":
        target.unlink()
        evidence_dir.rmdir()
        outside = tmp_path / "outside-evidence"
        outside.mkdir()
        (outside / f"{CHECKED_ITEM}.txt").write_text("PASS\n", encoding="utf-8")
        evidence_dir.symlink_to(outside, target_is_directory=True)
    elif case == "nested-directory":
        (evidence_dir / "nested").mkdir()
    elif case == "file-at-limit":
        target.write_bytes(b"x" * EVIDENCE_FILE_MAX_BYTES)
    elif case == "file-over-limit":
        target.write_bytes(b"x" * (EVIDENCE_FILE_MAX_BYTES + 1))
    elif case in {"directory-at-limit", "directory-over-limit"}:
        target.write_bytes(b"x" * EVIDENCE_FILE_MAX_BYTES)
        for index in range(4):
            (evidence_dir / f"aux-{index}.txt").write_bytes(b"x" * EVIDENCE_FILE_MAX_BYTES)
        if case == "directory-over-limit":
            (evidence_dir / "one-more-byte.txt").write_bytes(b"x")

    report = lint_change(CHANGE_ID, repo_root=tmp_path)
    kinds = _semantic_kinds(report)

    if expected_kind is None:
        assert report.exit_code == 0
        assert not any(kind.startswith("EVIDENCE_") for kind in kinds)
    else:
        assert report.exit_code == 1
        assert expected_kind in kinds
    if case in {"directory-at-limit", "directory-over-limit"}:
        expected_size = EVIDENCE_DIRECTORY_MAX_BYTES + (case == "directory-over-limit")
        assert sum(path.stat().st_size for path in evidence_dir.iterdir()) == expected_size


@pytest.mark.parametrize(
    ("case", "authorized_at", "config_hash", "expected_kind"),
    [
        ("signed-match", "2026-08-24T12:00:00Z", "matching", None),
        ("unsigned", None, None, None),
        ("signed-without-hash", "2026-08-24T12:00:00Z", None, "PREFLIGHT_AUTHORIZATION"),
        ("invalid-signature", "2026-08-24T12:00:00+00:00", "matching", "PREFLIGHT_AUTHORIZATION"),
        ("invalid-hash", "2026-08-24T12:00:00Z", "ABC", "PREFLIGHT_HASH"),
        ("mirror-mismatch", "2026-08-24T12:00:00Z", "0" * 64, "PREFLIGHT_HASH"),
        ("mirror-missing", "2026-08-24T12:00:00Z", "matching", "PREFLIGHT_HASH"),
    ],
)
def test_preflight_signature_and_mirror_hash_cases(
    tmp_path: Path,
    case: str,
    authorized_at: str | None,
    config_hash: str | None,
    expected_kind: str | None,
) -> None:
    folder = _scaffold_checklist(tmp_path)
    resolved_hash = (
        hashlib.sha256(MIRROR_BYTES).hexdigest() if config_hash == "matching" else config_hash
    )
    (folder / "preflight.md").write_text(
        _preflight_text(
            authorized_at=authorized_at,
            project_config_hash=resolved_hash,
        ),
        encoding="utf-8",
    )
    if case == "mirror-missing":
        (tmp_path / ".local" / "project_config.yaml").unlink()

    report = lint_change(CHANGE_ID, repo_root=tmp_path)

    if expected_kind is None:
        assert report.exit_code == 0
    else:
        assert report.exit_code == 1
        assert expected_kind in _semantic_kinds(report)


@pytest.mark.parametrize("mode", ["draft", "inherited", "delta"])
def test_sign_preflight_commits_canonical_first_inherited_and_delta_paths(
    tmp_path: Path,
    mode: str,
) -> None:
    if mode == "draft":
        draft = _section0_draft(tmp_path, CHANGE_ID)
        folder = scaffold_change_folder("Checklist Lint", tmp_path, change_id=CHANGE_ID)
        prior_mirror = None
    else:
        baseline, _prior_preflight = _signed_prior(tmp_path)
        draft = draft_preflight_section0(
            tmp_path,
            inherited=baseline,
            overrides={"quality.max_rounds": 4} if mode == "delta" else None,
        )
        prior_mirror = (tmp_path / ".local" / "project_config.yaml").read_bytes()
        folder = scaffold_change_folder("Checklist Lint", tmp_path, change_id=CHANGE_ID)
        _replace_section0(folder / "preflight.md", draft.markdown)

    quote = 'Approved "verbatim" with a \\ path'
    signature = sign_preflight(
        tmp_path,
        CHANGE_ID,
        draft=draft,
        authorizations=[_authorization(quote)],
        authorized_at="2026-08-24T12:00:00Z",
    )

    preflight = (folder / "preflight.md").read_text(encoding="utf-8")
    frontmatter = preflight_module.parse_frontmatter(
        preflight,
        filename="preflight.md",
    ).frontmatter
    mirror_bytes = signature.mirror_path.read_bytes()
    assert draft.mode == mode
    assert frontmatter["authorized_at"] == signature.authorized_at
    assert frontmatter["project_config_hash"] == hashlib.sha256(mirror_bytes).hexdigest()
    assert frontmatter["authorization_hash"] == signature.authorization_hash
    assert json.dumps(quote, ensure_ascii=False) in preflight
    assert not [
        finding
        for finding in lint_change(CHANGE_ID, repo_root=tmp_path).hard_failures
        if isinstance(finding, SemanticViolation)
    ]
    if mode == "inherited":
        assert mirror_bytes == prior_mirror
    elif mode == "delta":
        assert mirror_bytes != prior_mirror


@pytest.mark.parametrize(
    "case",
    [
        "stale-draft",
        "blocking-finding",
        "orphan-authorization",
        "multiline-quote",
        "preflight-replace-failure",
    ],
)
def test_sign_preflight_failures_leave_targets_byte_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    draft = _section0_draft(tmp_path, CHANGE_ID)
    folder = scaffold_change_folder("Checklist Lint", tmp_path, change_id=CHANGE_ID)
    preflight_path = folder / "preflight.md"
    mirror_path = tmp_path / ".local" / "project_config.yaml"
    authorizations = [_authorization()]

    if case == "stale-draft":
        stale = preflight_path.read_text(encoding="utf-8").replace(
            "- name: checklist-lint |",
            "- name: stale |",
            1,
        )
        preflight_path.write_text(stale, encoding="utf-8", newline="\n")
    elif case == "blocking-finding":
        draft = draft_preflight_section0(
            tmp_path,
            project_name=CHANGE_ID,
            project_purpose=f"Complete {CHANGE_ID}",
            seed_mode="feature-enhancement",
            overrides={
                "tech_stack.primary_language": "rust",
                "tech_stack.build_system": "npm",
            },
        )
        _replace_section0(preflight_path, draft.markdown)
    elif case == "orphan-authorization":
        authorizations = [PreflightAuthorization("PF-X9", "reserved_stop", "Orphan approval")]
    elif case == "multiline-quote":
        authorizations = [_authorization("line one\nline two")]
    elif case == "preflight-replace-failure":
        real_replace = preflight_module.os.replace

        def fail_preflight_replace(source: Path, target: Path) -> None:
            if Path(target) == preflight_path:
                raise OSError("injected preflight replacement failure")
            real_replace(source, target)

        monkeypatch.setattr(preflight_module.os, "replace", fail_preflight_replace)

    before_preflight = preflight_path.read_bytes()
    before_mirror = mirror_path.read_bytes() if mirror_path.exists() else None
    with pytest.raises(PreflightAuthorizationError):
        sign_preflight(
            tmp_path,
            CHANGE_ID,
            draft=draft,
            authorizations=authorizations,
            authorized_at="2026-08-24T12:00:00Z",
        )

    assert preflight_path.read_bytes() == before_preflight
    assert (mirror_path.read_bytes() if mirror_path.exists() else None) == before_mirror


def test_invalidate_preflight_is_atomic_idempotent_and_preserves_body_and_mirror(
    tmp_path: Path,
) -> None:
    draft = _section0_draft(tmp_path, CHANGE_ID)
    folder = scaffold_change_folder("Checklist Lint", tmp_path, change_id=CHANGE_ID)
    sign_preflight(
        tmp_path,
        CHANGE_ID,
        draft=draft,
        authorizations=[_authorization()],
        authorized_at="2026-08-24T12:00:00Z",
    )
    preflight_path = folder / "preflight.md"
    mirror_path = tmp_path / ".local" / "project_config.yaml"
    before_text = preflight_path.read_text(encoding="utf-8")
    before_body = before_text.split("---", 2)[2]
    before_mirror = mirror_path.read_bytes()

    assert invalidate_preflight(tmp_path, CHANGE_ID) is True
    invalidated = preflight_path.read_text(encoding="utf-8")
    frontmatter = preflight_module.parse_frontmatter(
        invalidated,
        filename="preflight.md",
    ).frontmatter
    assert frontmatter["authorized_at"] is None
    assert frontmatter["project_config_hash"] is None
    assert frontmatter["authorization_hash"] is None
    assert invalidated.split("---", 2)[2] == before_body
    assert mirror_path.read_bytes() == before_mirror

    first_invalidation = preflight_path.read_bytes()
    assert invalidate_preflight(tmp_path, CHANGE_ID) is False
    assert preflight_path.read_bytes() == first_invalidation
    assert mirror_path.read_bytes() == before_mirror


@pytest.mark.parametrize(
    ("case", "expected_kind"),
    [
        ("section-order", "PREFLIGHT_SECTION_ORDER"),
        ("section-zero", "PREFLIGHT_SECTION_0"),
        ("stop-card", "PREFLIGHT_STOP_CARD"),
        ("authorization", "PREFLIGHT_AUTHORIZATION"),
        ("permitted-stops", "PREFLIGHT_PERMITTED_STOPS"),
        ("seal", "PREFLIGHT_SEAL"),
        ("archived-seal", "PREFLIGHT_SEAL"),
    ],
)
def test_preflight_sections_and_seal_emit_stable_findings(
    tmp_path: Path,
    case: str,
    expected_kind: str,
) -> None:
    folder = _scaffold_checklist(tmp_path)
    path = folder / "preflight.md"
    text = path.read_text(encoding="utf-8")
    if case == "section-order":
        text = (
            text.replace(
                "## 1. Stop Cards",
                "## SWAP",
                1,
            )
            .replace(
                "## 2. Authorization Record",
                "## 1. Stop Cards",
                1,
            )
            .replace(
                "## SWAP",
                "## 2. Authorization Record",
                1,
            )
        )
    elif case == "section-zero":
        text = text.replace("- Inherited from prior-change", "- Inherited by prior-change", 1)
    elif case == "stop-card":
        text = text.replace(
            "|---|---|---|---|---|",
            "| PF-A1 | external_resource | Risk. | C-G1.1 | reserved_stop |",
            1,
        )
    elif case == "authorization":
        text = text.replace(
            "## 2. Authorization Record\n\n",
            "## 2. Authorization Record\n"
            '- PF-A1: reserved_stop at 2026-08-24T12:00:00Z — "Approved"\n\n',
            1,
        )
    elif case == "permitted-stops":
        text = text.replace("1. STOP-1:", "1. STOP-ONE:", 1)
    elif case in {"seal", "archived-seal"}:
        text = text.replace(
            "|---|---|---|---|---|",
            "|---|---|---|---|---|\n"
            "| PF-A1 | human_touch | Valid new risk. | C-G1.1 | reserved_stop |",
            1,
        )
        text = text.replace(
            "## 2. Authorization Record\n\n",
            "## 2. Authorization Record\n"
            '- PF-A1: reserved_stop at 2026-08-24T12:00:00Z — "Approved"\n\n',
            1,
        )
    path.write_text(text, encoding="utf-8", newline="\n")

    if case == "archived-seal":
        archived = tmp_path / ".local" / ".agent" / "archive" / "2026-08-24-checklist-lint"
        archived.parent.mkdir(parents=True)
        folder.rename(archived)
        (tmp_path / ".local" / "project_config.yaml").unlink()

    report = lint_change(CHANGE_ID, repo_root=tmp_path)
    assert expected_kind in _semantic_kinds(report)


@pytest.mark.parametrize(
    "case",
    [
        "mixed-api",
        "cli-pass",
        "cli-quiet-semantic-fail",
        "cli-hard-budget-fail",
        "cli-soft-budget-warn",
        "cli-learnings-over-limit",
        "cli-missing",
        "legacy-api",
        "cli-legacy",
    ],
)
def test_mixed_layout_reports_explicit_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    case: str,
) -> None:
    if case == "cli-missing":
        assert lint_main(["--repo-root", str(tmp_path), "not-found"]) == 2
        assert "no folder for 'not-found'" in capsys.readouterr().err
        return

    if case in {"legacy-api", "cli-legacy"}:
        # v17.0.0 removal: a tasks.md/acceptance.md folder is a loud error,
        # never a silently-linted layout (S-5).
        folder = tmp_path / ".local" / ".agent" / "active" / "legacy-lint"
        folder.mkdir(parents=True)
        (folder / "acceptance.md").write_text("legacy acceptance\n", encoding="utf-8")
        (folder / "tasks.md").write_text("legacy tasks\n", encoding="utf-8")
        if case == "legacy-api":
            with pytest.raises(LegacyChangeLayoutError, match=r"removed in v17\.0\.0"):
                lint_change("legacy-lint", repo_root=tmp_path)
        else:
            assert lint_main(["--repo-root", str(tmp_path), "legacy-lint"]) == 2
            assert "removed in v17.0.0" in capsys.readouterr().err
        return

    folder = _scaffold_checklist(tmp_path)
    if case in {"cli-hard-budget-fail", "cli-soft-budget-warn"}:
        # spec.md is budget-linted but not semantically parsed, so the
        # scaffold stays semantics-green while the budget tier trips.
        size = 12004 if case == "cli-hard-budget-fail" else 6100
        (folder / "spec.md").write_text("x" * size, encoding="utf-8")
        rc = lint_main(["--repo-root", str(tmp_path), CHANGE_ID])
        stderr = capsys.readouterr().err
        if case == "cli-hard-budget-fail":
            assert rc == 1
            assert "hard ceiling violation(s)" in stderr
        else:
            assert rc == 0
            assert "soft budget warning(s)" in stderr
        report = lint_change(CHANGE_ID, repo_root=tmp_path)
        assert not any(isinstance(v, SemanticViolation) for v in report.violations)
        violation = next(v for v in report.violations if v.filename == "spec.md")
        assert isinstance(violation, BudgetViolation)
        assert violation.severity == ("FAIL" if case == "cli-hard-budget-fail" else "WARN")
        return

    if case == "cli-learnings-over-limit":
        (folder / "learnings.jsonl").write_bytes(b"x" * (LEARNINGS_JSONL_MAX_BYTES + 1))
        rc = lint_main(["--repo-root", str(tmp_path), CHANGE_ID])
        assert rc == 1
        assert "learnings.jsonl" in capsys.readouterr().err
        return

    if case in {"mixed-api", "cli-quiet-semantic-fail"}:
        (folder / "tasks.md").write_text("# Legacy tasks\n", encoding="utf-8")

    if case == "mixed-api":
        report = lint_change(CHANGE_ID, repo_root=tmp_path)
        assert report.exit_code == 1
        assert _semantic_kinds(report) == ["INVALID_MIXED"]
        return

    argv = ["--repo-root", str(tmp_path), CHANGE_ID]
    if case == "cli-quiet-semantic-fail":
        argv.append("--quiet")
    rc = lint_main(argv)
    stderr = capsys.readouterr().err
    if case == "cli-pass":
        assert rc == 0
        assert f"{CHANGE_ID}/goal.md" in stderr
        assert " OK" in stderr
    else:
        assert rc == 1
        assert " OK" not in stderr
        assert "[INVALID_MIXED]" in stderr
        assert "hard/semantic violation(s)" in stderr
