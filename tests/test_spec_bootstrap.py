"""Tests for v9.1.5 PV-05 :func:`seed_initial_spec` (closes M-004).

Pins the contract for the FIRST-TIME source-of-truth seed surface added
in v9.1.5 PV-05 per the v9.2.0 cycle plan §PV-05:

* **Happy path** — given an archived change with ADDED Requirements,
  ``seed_initial_spec(domain, archive_id, repo_root)`` produces a valid
  ``.local/memory/specs/<domain>/spec.md`` containing the synthesized
  H1 + frontmatter scaffold + the archived Requirements verbatim.
* **A-4 invariant** — refuses to overwrite an existing source-of-truth
  unless ``force=True`` is passed (which logs a WARNING per S-5 and
  proceeds). Subsequent updates of an existing spec MUST go through
  :meth:`ArchiveManager.propose_merge` → :meth:`apply_merge` (the gate-
  score-checked update path).
* **Missing archive** — when the archive folder does not exist,
  :exc:`SpecBootstrapError` is raised verbatim (S-5 — never silent).
* **Gate-score independence** — ``seed_initial_spec`` does NOT call
  :meth:`apply_merge` (which enforces ≥ 8.5 / ≥ 9.0 gate scores). The
  bootstrap is for first-time domain seeding (no existing spec); the
  gate-score check is the contract for UPDATING an existing spec.
* **MergeConflict surfacing** — when ``force=True`` overwrites an
  existing spec whose body already contains a heading collision with
  the archive's ADDED Requirements, the underlying
  :exc:`MergeConflict` is wrapped in :exc:`SpecBootstrapError` with
  the original cause preserved (``__cause__``).

The tests use ``tmp_path`` exclusively — no dependency on a real
``.local/.agent/`` tree on disk.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace.spec_bootstrap import (
    SpecBootstrapError,
    seed_initial_spec,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Return ``tmp_path`` configured as a DevolaFlow repo root with empty subdirs.

    Mirrors the canonical layout under ``.local/.agent/`` + ``.local/memory/``
    expected by :class:`ChangeStore` and :func:`seed_initial_spec`.
    """
    (tmp_path / ".local" / ".agent" / "active").mkdir(parents=True)
    (tmp_path / ".local" / ".agent" / "handoff").mkdir(parents=True)
    (tmp_path / ".local" / ".agent" / "archive").mkdir(parents=True)
    (tmp_path / ".local" / "memory" / "specs").mkdir(parents=True)
    return tmp_path


def _scaffold_archived_change(
    workspace: Path,
    *,
    archive_folder_name: str,
    change_id: str,
    delta_target: str,
    spec_md: str,
    state: str = "ARCHIVED",
) -> Path:
    """Drop a minimal ARCHIVED change folder under ``workspace``.

    Bypasses the ``ArchiveManager.archive`` lifecycle move (those tests
    live in ``tests/test_agent_workspace.py``) and writes the change
    folder directly under ``archive/<archive_folder_name>/`` so the
    seed_initial_spec tests can focus on the bootstrap contract.
    """
    folder = workspace / ".local" / ".agent" / "archive" / archive_folder_name
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "goal.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            id: {change_id}
            created: "2026-04-30T10:00:00Z"
            priority: P2
            intent_class: feature
            ---

            # Goal: {change_id}

            ## Why
            Bootstrap fixture for spec_bootstrap tests.

            ## In scope
            - Tests pass

            ## Out of scope
            - Real users
            """
        ),
        encoding="utf-8",
    )
    (folder / "acceptance.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            ac_count: 1
            ---

            # Acceptance Criteria

            ## Functional
            - [x] AC-1: Seeded
            """
        ),
        encoding="utf-8",
    )
    (folder / "spec.md").write_text(spec_md, encoding="utf-8")
    (folder / "tasks.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            total_tasks: 1
            checked: 1
            ---

            # Tasks

            ## 1. Implementation
            - [x] 1.1 Done
            """
        ),
        encoding="utf-8",
    )
    (folder / "STATUS.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "change_id": change_id,
                "state": state,
                "percent_complete": 100,
                "owner_layer": "L0",
                "owner_session_id": "test",
                "last_updated": "2026-04-30T11:00:00Z",
                "last_handoff_seq": 0,
                "gate_score": 9.5,
                "verify_pass": True,
            },
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    (folder / "owned_files.txt").write_text(
        f"src/devolaflow/agent_workspace/{delta_target}.py\n",
        encoding="utf-8",
    )
    return folder


def _archive_spec_md(*, change_id: str, delta_target: str) -> str:
    """Return a minimal valid OpenSpec delta-spec referencing ``delta_target``.

    Produces a single ADDED Requirement so :func:`seed_initial_spec` writes
    a non-empty bootstrap with one heading.
    """
    return textwrap.dedent(
        f"""\
        ---
        parent: {change_id}
        delta_target: {delta_target}
        delta_kind: lite
        ---

        # Operation Spec for {change_id}

        ## Purpose
        Seed fixture for {delta_target}.

        ## ADDED Requirements

        ### Requirement: First-time bootstrap requirement
        The system MUST be seedable from a verified archive.
        """
    )


# ---------------------------------------------------------------------------
# Tests (6 NEW per cycle plan §PV-05)
# ---------------------------------------------------------------------------


def test_seed_from_valid_archive_creates_spec(workspace: Path) -> None:
    """Happy path — a valid archive seeds .local/memory/specs/<domain>/spec.md.

    Verifies the headline contract: given an ARCHIVED change with ADDED
    Requirements, ``seed_initial_spec`` produces an on-disk source-of-
    truth spec containing the synthesised H1 + frontmatter scaffold +
    the archived Requirements verbatim.
    """
    archive_id = "2026-04-30-pv05-bootstrap"
    change_id = "pv05-bootstrap"
    domain = "agent_workspace"
    _scaffold_archived_change(
        workspace,
        archive_folder_name=archive_id,
        change_id=change_id,
        delta_target=domain,
        spec_md=_archive_spec_md(change_id=change_id, delta_target=domain),
    )

    target_path = workspace / ".local" / "memory" / "specs" / domain / "spec.md"
    assert not target_path.exists(), "test pre-condition: target spec MUST be absent"

    written = seed_initial_spec(domain, archive_id, workspace)

    assert written == target_path, (
        f"seed_initial_spec returned {written!s}, expected {target_path!s}"
    )
    assert target_path.is_file(), "target spec.md must exist on disk after seed"

    text = target_path.read_text(encoding="utf-8")
    assert "First-time bootstrap requirement" in text, (
        "ADDED Requirement heading must appear verbatim in the seeded spec"
    )
    assert "domain: agent_workspace" in text, "synthesized frontmatter must carry domain"
    assert "Source-of-Truth" in text, "synthesized H1 must carry the source-of-truth marker"


def test_seed_refuses_overwrite_without_force(workspace: Path) -> None:
    """A-4 invariant — refuses to overwrite an existing source-of-truth.

    The first-time-seed gate is filesystem absence; pre-existing target
    spec means the caller must use the propose_merge → apply_merge update
    path instead. SpecBootstrapError is raised verbatim (S-5).
    """
    archive_id = "2026-04-30-pv05-noforce"
    change_id = "pv05-noforce"
    domain = "agent_workspace"
    _scaffold_archived_change(
        workspace,
        archive_folder_name=archive_id,
        change_id=change_id,
        delta_target=domain,
        spec_md=_archive_spec_md(change_id=change_id, delta_target=domain),
    )

    target_path = workspace / ".local" / "memory" / "specs" / domain / "spec.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        "---\ndomain: agent_workspace\n---\n\n# Pre-existing\n",
        encoding="utf-8",
    )
    pre_existing = target_path.read_bytes()

    with pytest.raises(SpecBootstrapError) as exc_info:
        seed_initial_spec(domain, archive_id, workspace)

    assert "A-4" in str(exc_info.value), (
        "error message must cite A-4 invariant (the first-time-seed contract)"
    )
    assert "force=True" in str(exc_info.value), (
        "error message must point caller at the force=True escape hatch"
    )
    assert target_path.read_bytes() == pre_existing, (
        "A-4 violation: pre-existing source-of-truth was overwritten"
    )


def test_seed_force_overwrites_with_warning(
    workspace: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """force=True overwrites + emits WARNING (S-5 — never silent).

    When operators explicitly ask to overwrite (e.g. repo-init or
    disaster-recovery scenarios), the function honours the request but
    surfaces a WARNING log so the override is auditable.
    """
    archive_id = "2026-04-30-pv05-force"
    change_id = "pv05-force"
    domain = "agent_workspace"
    _scaffold_archived_change(
        workspace,
        archive_folder_name=archive_id,
        change_id=change_id,
        delta_target=domain,
        spec_md=_archive_spec_md(change_id=change_id, delta_target=domain),
    )

    target_path = workspace / ".local" / "memory" / "specs" / domain / "spec.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        "---\ndomain: agent_workspace\n---\n\n# Stale content to overwrite\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="devolaflow.agent_workspace.spec_bootstrap"):
        written = seed_initial_spec(domain, archive_id, workspace, force=True)

    assert written == target_path
    assert any(
        "force=True" in record.getMessage() and "overwriting" in record.getMessage()
        for record in caplog.records
    ), "S-5 violation: force=True must emit a WARNING log line"
    text = target_path.read_text(encoding="utf-8")
    assert "First-time bootstrap requirement" in text, (
        "force=True must replace stale content with the seeded body"
    )
    assert "Stale content to overwrite" not in text, (
        "force=True must wholly replace, not append to, the stale spec"
    )


def test_seed_raises_when_archive_missing(workspace: Path) -> None:
    """Missing archive folder → SpecBootstrapError (S-5; never silent)."""
    with pytest.raises(SpecBootstrapError) as exc_info:
        seed_initial_spec("agent_workspace", "2026-04-30-not-here", workspace)

    msg = str(exc_info.value)
    assert "archive folder not found" in msg, (
        "error message must explain the missing-archive root cause"
    )
    assert "2026-04-30-not-here" in msg, "archive_id must be echoed for diagnostics"


def test_seed_proposes_merge_does_not_auto_apply(workspace: Path) -> None:
    """A-4 — seed uses propose_merge under the hood but never invokes apply_merge.

    apply_merge enforces a gate-score threshold (≥ 8.5 PATCH/MINOR;
    ≥ 9.0 MAJOR) and is the canonical UPDATE path. The seed surface is
    the FIRST-TIME bootstrap path (no existing spec; gates on filesystem
    absence instead of gate score). This test pins the boundary by
    seeding a domain whose source-of-truth is absent and asserting the
    write path uses the bootstrap atomic-write rather than apply_merge's
    gate-checking helper.
    """
    archive_id = "2026-04-30-pv05-noapply"
    change_id = "pv05-noapply"
    domain = "agent_workspace"
    _scaffold_archived_change(
        workspace,
        archive_folder_name=archive_id,
        change_id=change_id,
        delta_target=domain,
        spec_md=_archive_spec_md(change_id=change_id, delta_target=domain),
        # Set a deliberately-low gate_score; if seed_initial_spec ever called
        # apply_merge, this would raise GateThresholdNotMet (≥ 8.5 PATCH).
        # The test passes ONLY if the bootstrap path bypasses gate-score logic.
    )
    status_path = workspace / ".local" / ".agent" / "archive" / archive_id / "STATUS.yaml"
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    status["gate_score"] = 5.0  # below PATCH/MINOR threshold (8.5)
    status_path.write_text(
        yaml.safe_dump(status, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    target_path = workspace / ".local" / "memory" / "specs" / domain / "spec.md"
    assert not target_path.exists(), "test pre-condition: target spec absent"

    # Should NOT raise GateThresholdNotMet — bootstrap bypasses gate-score.
    written = seed_initial_spec(domain, archive_id, workspace)

    assert written == target_path
    assert target_path.is_file(), "bootstrap must write the spec regardless of gate_score"
    text = target_path.read_text(encoding="utf-8")
    assert "First-time bootstrap requirement" in text


def test_seed_mergeconflict_surfaces_as_spec_bootstrap_error(workspace: Path) -> None:
    """MergeConflict on heading collision → wrapped in SpecBootstrapError.

    The first-time-seed surface ALWAYS produces an empty source-of-truth
    base (force=False refuses if target exists; force=True wipes the
    target before propose_merge so the merge synthesizes a fresh
    scaffold). MergeConflict therefore surfaces only when the archive's
    delta references an existing Requirement that the empty base cannot
    satisfy — i.e. ``MODIFIED Requirements`` or ``REMOVED Requirements``
    on a NEW domain. The underlying :exc:`MergeConflict` is wrapped in
    :exc:`SpecBootstrapError` with the original cause preserved
    (``__cause__``) so callers can recover the heading text for
    diagnostics (S-5 — never silent).
    """
    archive_id = "2026-04-30-pv05-conflict"
    change_id = "pv05-conflict"
    domain = "agent_workspace"
    # Archive has a MODIFIED Requirement (no ADDED). Seeding a NEW
    # domain whose source-of-truth is empty MUST raise MergeConflict
    # because there is no existing Requirement to MODIFY.
    spec_md = textwrap.dedent(
        f"""\
        ---
        parent: {change_id}
        delta_target: {domain}
        delta_kind: lite
        ---

        # Operation Spec for {change_id}

        ## Purpose
        Modify a Requirement that does not exist in a fresh seed.

        ## MODIFIED Requirements

        ### Requirement: Nonexistent for fresh seed
        The system MUST do something different.
        """
    )
    _scaffold_archived_change(
        workspace,
        archive_folder_name=archive_id,
        change_id=change_id,
        delta_target=domain,
        spec_md=spec_md,
    )

    target_path = workspace / ".local" / "memory" / "specs" / domain / "spec.md"
    assert not target_path.exists(), "test pre-condition: target spec absent"

    with pytest.raises(SpecBootstrapError) as exc_info:
        seed_initial_spec(domain, archive_id, workspace)

    msg = str(exc_info.value)
    assert "propose_merge failed" in msg, (
        "wrapper message must identify propose_merge as the failing layer"
    )
    # __cause__ preserves the original MergeConflict (S-5 — never silent).
    from devolaflow.agent_workspace import MergeConflict

    assert isinstance(exc_info.value.__cause__, MergeConflict), (
        f"underlying MergeConflict cause must be preserved via __cause__; "
        f"got {type(exc_info.value.__cause__).__name__}"
    )
    assert "Nonexistent for fresh seed" in str(exc_info.value.__cause__), (
        "MergeConflict message must echo the heading that has no match"
    )
    # Target spec MUST NOT have been written when propose_merge fails.
    assert not target_path.exists(), (
        "S-5 violation: failed propose_merge must not leave a partial spec on disk"
    )
