"""Tests for :mod:`devolaflow.workspace_context.scan_workspace`.

These tests pin the v9.1.1 PV-01 discovery API (per
``.local/research/v9.1.1_pv01_design.md``):

1. :func:`scan_workspace` returns a frozen :class:`WorkspaceContext`
   snapshot with sane defaults when paths are absent.
2. Detection rules match the contract in SKILL.md §"Workspace Engagement"
   and ``references/agent-workspace.md`` §1 "When to Engage".
3. PermissionError is absorbed into a WARNING (S-5 explicit error state)
   without raising, so the L0 dispatcher can call ``scan_workspace``
   unconditionally at session start without a try/except around it.

Every test uses ``tmp_path`` fixtures — zero network I/O, zero writes
outside the per-test scratch directory, fully parallelisable.
"""

from __future__ import annotations

import dataclasses
import json
import os
import platform
import time
from pathlib import Path

import pytest

from devolaflow.workspace_context import (
    MAX_FEEDBACKS_RETURNED,
    WorkspaceContext,
    scan_workspace,
)


def test_empty_repo_returns_all_false_or_empty(tmp_path: Path) -> None:
    """A repo with no ``.local/`` and no ``.rules/`` returns the empty snapshot.

    Per the discovery contract, missing paths NEVER raise — the snapshot
    reports each surface as absent so the L0 dispatcher can skip the
    matching dispatch-context branches without defensive code.
    """
    ctx = scan_workspace(tmp_path)

    assert isinstance(ctx, WorkspaceContext)
    assert ctx.repo_root == tmp_path.resolve()
    assert ctx.has_local is False
    assert ctx.has_rules is False
    assert ctx.has_agent_dir is False
    assert ctx.active_changes == ()
    assert ctx.recent_feedbacks == ()
    assert ctx.source_of_truth_specs == ()
    assert ctx.memory_cases_count == 0
    assert ctx.rules_layer_set == ()
    assert ctx.compiled_corpora == ()


def test_full_stack_repo_detects_all_surfaces(tmp_path: Path) -> None:
    """A populated repo surfaces every detection rule positively.

    Fixture layout mirrors what ``devola-init local --with-examples`` will
    produce in v9.2.0 PV-06: ``.local/feedbacks/feedback_for_v*.md``,
    ``.local/memory/specs/<domain>/spec.md``,
    ``.local/memory/cases/<id>.md``,
    ``.local/.agent/active/<change-id>/STATUS.yaml``, ``.rules/soul.mdc``,
    plus the compiled ``AGENTS.md``.
    """
    (tmp_path / ".local" / "feedbacks").mkdir(parents=True)
    (tmp_path / ".local" / "feedbacks" / "feedback_for_v9.1.0.md").write_text(
        "# Feedback for DevolaFlow v9.1.0\n",
        encoding="utf-8",
    )

    (tmp_path / ".local" / "memory" / "specs" / "foo").mkdir(parents=True)
    (tmp_path / ".local" / "memory" / "specs" / "foo" / "spec.md").write_text(
        "# Spec for foo\n",
        encoding="utf-8",
    )

    (tmp_path / ".local" / "memory" / "cases").mkdir(parents=True)
    (tmp_path / ".local" / "memory" / "cases" / "bar.md").write_text(
        "# Case bar\n",
        encoding="utf-8",
    )
    (tmp_path / ".local" / "memory" / "cases" / "README.md").write_text(
        "(scaffold)",
        encoding="utf-8",
    )
    (tmp_path / ".local" / "memory" / "cases" / "index.yaml").write_text(
        "cases: []\n",
        encoding="utf-8",
    )

    (tmp_path / ".local" / ".agent" / "active" / "baz").mkdir(parents=True)
    (tmp_path / ".local" / ".agent" / "active" / "baz" / "STATUS.yaml").write_text(
        "state: PROPOSED\n",
        encoding="utf-8",
    )

    (tmp_path / ".rules").mkdir()
    (tmp_path / ".rules" / "soul.mdc").write_text(
        "# Soul rules\n",
        encoding="utf-8",
    )

    (tmp_path / "AGENTS.md").write_text("# Agents corpus\n", encoding="utf-8")

    ctx = scan_workspace(tmp_path)

    assert ctx.has_local is True
    assert ctx.has_rules is True
    assert ctx.has_agent_dir is True
    assert ctx.active_changes == ("baz",)
    assert len(ctx.recent_feedbacks) == 1
    assert ctx.recent_feedbacks[0].name == "feedback_for_v9.1.0.md"
    assert len(ctx.source_of_truth_specs) == 1
    assert ctx.source_of_truth_specs[0].name == "spec.md"
    assert ctx.source_of_truth_specs[0].parent.name == "foo"
    assert ctx.memory_cases_count == 1
    assert ctx.rules_layer_set == ("soul",)
    assert ctx.compiled_corpora == ("AGENTS.md",)


def test_recent_feedbacks_returns_at_most_3_newest_first(tmp_path: Path) -> None:
    """``recent_feedbacks`` caps at 3 entries, newest first by mtime.

    Authors 5 feedback files with staggered ``os.utime`` timestamps
    (1-second spacing) and asserts ``scan_workspace`` returns exactly the
    3 newest in mtime-descending order. This pins the
    ``_RECENT_FEEDBACKS_LIMIT = 3`` contract that the SKILL.md
    Workspace Engagement section relies on.
    """
    feedbacks = tmp_path / ".local" / "feedbacks"
    feedbacks.mkdir(parents=True)

    versions = ["v8.0.0", "v8.1.0", "v9.0.0", "v9.1.0", "v9.2.0"]
    base = time.time() - 100
    for i, ver in enumerate(versions):
        path = feedbacks / f"feedback_for_{ver}.md"
        path.write_text(f"# Feedback for DevolaFlow {ver}\n", encoding="utf-8")
        os.utime(path, (base + i, base + i))

    ctx = scan_workspace(tmp_path)

    assert len(ctx.recent_feedbacks) == 3
    names = [p.name for p in ctx.recent_feedbacks]
    assert names == [
        "feedback_for_v9.2.0.md",
        "feedback_for_v9.1.0.md",
        "feedback_for_v9.0.0.md",
    ]


def test_active_changes_excludes_readme_and_dot_files(tmp_path: Path) -> None:
    """``active_changes`` filters scaffolding entries.

    ``.local/.agent/active/README.md`` (created by ``devola-init local``)
    and any dot-prefixed entries (``.keep``, ``.gitkeep``) are excluded
    from the change-folder enumeration so callers see only real in-flight
    changes — the surface the SKILL.md Workspace Engagement table
    instructs L0 to RESUME rather than re-open.
    """
    active = tmp_path / ".local" / ".agent" / "active"
    active.mkdir(parents=True)
    (active / "README.md").write_text("(scaffold)", encoding="utf-8")
    (active / ".keep").write_text("", encoding="utf-8")
    (active / ".gitkeep").write_text("", encoding="utf-8")
    (active / "real-change").mkdir()
    (active / "real-change" / "STATUS.yaml").write_text(
        "state: IN_PROGRESS\n",
        encoding="utf-8",
    )

    ctx = scan_workspace(tmp_path)

    assert ctx.has_agent_dir is True
    assert ctx.active_changes == ("real-change",)


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX permission-mode test (chmod 000) — Windows ACL semantics differ",
)
def test_unreadable_path_does_not_raise(tmp_path: Path) -> None:
    """``scan_workspace`` absorbs PermissionError into a WARNING (S-5).

    Creates ``.local/.agent/active/`` with mode 000 (unreadable) and
    asserts ``scan_workspace`` returns defaults without raising. The
    test is POSIX-only — Windows ACL permission semantics differ from
    chmod's mode bits and the test would be a no-op there.

    Cleanup restores read permissions in a ``finally`` block so
    ``tmp_path`` teardown can remove the fixture without an
    EACCES storm.
    """
    if os.geteuid() == 0:  # pragma: no cover - root bypasses chmod
        pytest.skip("running as root; chmod 000 is bypassed by CAP_DAC_READ_SEARCH")

    active = tmp_path / ".local" / ".agent" / "active"
    active.mkdir(parents=True)

    original_mode = active.stat().st_mode
    try:
        active.chmod(0o000)
        ctx = scan_workspace(tmp_path)
        assert ctx.has_agent_dir is True
        assert ctx.active_changes == ()
    finally:
        active.chmod(original_mode)


def test_workspace_context_is_immutable_dataclass(tmp_path: Path) -> None:
    """``WorkspaceContext`` is a frozen dataclass.

    Pins the design contract that consumers cannot mutate a snapshot
    in flight. Verifies:

    * :func:`dataclasses.is_dataclass` returns ``True``.
    * Attribute assignment raises :exc:`dataclasses.FrozenInstanceError`.
    * :func:`dataclasses.replace` works (the supported way to derive a
      modified copy).
    """
    ctx = scan_workspace(tmp_path)

    assert dataclasses.is_dataclass(ctx)

    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.has_local = True

    derived = dataclasses.replace(ctx, has_local=True)
    assert derived.has_local is True
    assert ctx.has_local is False


def test_to_summary_dict_is_json_serializable(tmp_path: Path) -> None:
    """``WorkspaceContext.to_summary_dict()`` round-trips through ``json``.

    The discovery snapshot is intended for injection into the dispatch
    context (the ``change_context`` block surfaced in v9.1.4 PV-04). The
    summary dict MUST be JSON-serialisable so :func:`json.dumps` succeeds
    without a custom encoder, AND every dataclass field MUST be present
    in the output (the schema is self-documenting; no field is silently
    dropped).

    Pins:

    * :data:`MAX_FEEDBACKS_RETURNED` is exposed as a public module-level
      constant equal to ``3`` (the plan-mode feedback-ingestion default).
    * ``json.dumps(ctx.to_summary_dict())`` succeeds (no custom encoder).
    * Every dataclass field surfaces under its own key in the summary
      dict.
    * :class:`Path` fields are rendered as repo-root-relative POSIX
      strings — the dispatch consumer never needs to know the
      consumer-repo's absolute path.
    """
    assert MAX_FEEDBACKS_RETURNED == 3

    (tmp_path / ".local" / "feedbacks").mkdir(parents=True)
    (tmp_path / ".local" / "feedbacks" / "feedback_for_v9.1.0.md").write_text(
        "# Feedback\n", encoding="utf-8"
    )
    (tmp_path / ".local" / "memory" / "specs" / "auth").mkdir(parents=True)
    (tmp_path / ".local" / "memory" / "specs" / "auth" / "spec.md").write_text(
        "# Auth spec\n", encoding="utf-8"
    )
    (tmp_path / ".rules").mkdir()
    (tmp_path / ".rules" / "soul.mdc").write_text("# Soul\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")

    ctx = scan_workspace(tmp_path)
    summary = ctx.to_summary_dict()

    serialised = json.dumps(summary)
    assert isinstance(serialised, str)

    parsed = json.loads(serialised)
    expected_keys = {
        "repo_root",
        "has_local",
        "has_rules",
        "has_agent_dir",
        "active_changes",
        "recent_feedbacks",
        "source_of_truth_specs",
        "memory_cases_count",
        "rules_layer_set",
        "compiled_corpora",
    }
    assert set(parsed) == expected_keys, (
        f"to_summary_dict() schema drift — expected {expected_keys}, got {set(parsed)}"
    )

    assert parsed["has_local"] is True
    assert parsed["has_rules"] is True
    assert parsed["memory_cases_count"] == 0
    assert parsed["rules_layer_set"] == ["soul"]
    assert parsed["compiled_corpora"] == ["AGENTS.md"]
    assert parsed["recent_feedbacks"] == [".local/feedbacks/feedback_for_v9.1.0.md"]
    assert parsed["source_of_truth_specs"] == [".local/memory/specs/auth/spec.md"]
    for path_str in parsed["recent_feedbacks"] + parsed["source_of_truth_specs"]:
        assert not path_str.startswith("/"), (
            f"to_summary_dict() must emit repo-relative POSIX paths, "
            f"not absolute paths; saw {path_str!r}"
        )
