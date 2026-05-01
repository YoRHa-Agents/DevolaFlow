"""Plan-mode feedback ingestion contract tests (v9.1.4 PV-04).

Pins the contract documented in
``workflow-system/agent/references/plan-mode-enforcement.md`` §5.5
"Automatic Ingestion at Plan-Mode Entry (v9.1.4+)" and surfaced by
``schemas/lean-dispatch.yaml#lean_format_spec.change_context.prior_feedback_themes``.

PV-04 ships the contract as **normative guidance** for L0 agents — there
is no new runtime helper module. The L0 agent reads the feedback files
returned by :func:`devolaflow.workspace_context.scan_workspace` (already
shipping in v9.1.1) using the standard ``Read`` tool, extracts ≤ 5 themes
(≤ 30 chars each), and surfaces them in the dispatch payload's
``change_context.prior_feedback_themes`` sub-field. The tests below pin
the discovery contract (paths returned in mtime-desc order with the cap),
the S-2 repo-relative path invariant, AND the plan-mode-enforcement.md
sub-section content.

Coverage matrix (4 NEW test functions, within W-17 PV-04 budget of +9):

1. ``test_no_feedbacks_dir_returns_empty_recent_feedbacks`` — empty
   ``.local/feedbacks/`` → empty tuple.
2. ``test_recent_feedbacks_paths_relative_via_to_summary_dict`` — S-2
   check: ``WorkspaceContext.to_summary_dict()`` renders feedback paths
   repo-relative (not absolute filesystem paths).
3. ``test_cap_at_three_feedbacks_newest_first_by_mtime`` — 5 feedback
   files with staggered mtime → top 3 by mtime desc; matches the
   documented ``MAX_FEEDBACKS_RETURNED == 3`` cap and the plan-mode
   contract.
4. ``test_plan_mode_enforcement_doc_documents_v9_1_4_ingestion_contract``
   — verifies that the plan-mode-enforcement.md §5.5 sub-section
   contains the v9.1.4+ contract markers (cap ≤ 5 themes, ≤ 30 chars,
   reads via standard Read tool, paths are repo-relative per S-2).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from devolaflow.workspace_context import (
    MAX_FEEDBACKS_RETURNED,
    scan_workspace,
)

# Documented per-theme cap surfaced by
# `schemas/lean-dispatch.yaml#lean_format_spec.change_context.prior_feedback_themes`
# — kept as test-side constants (not exported runtime constants) since the
# extraction itself is normative L0 guidance, not a Python helper.
_DOCUMENTED_MAX_THEMES: int = 5
_DOCUMENTED_MAX_THEME_CHARS: int = 30


def _project_root() -> Path:
    """Return the DevolaFlow repo root (parent of the ``tests/`` directory)."""
    return Path(__file__).resolve().parent.parent


def test_no_feedbacks_dir_returns_empty_recent_feedbacks(tmp_path: Path) -> None:
    """An empty ``.local/feedbacks/`` directory → ``recent_feedbacks=()``.

    The plan-mode contract (§5.5) instructs L0 to call
    :func:`scan_workspace` at plan-mode entry. When no feedback file
    exists yet (legitimate new-repo state — no user has written
    ``.local/feedbacks/feedback_for_v*.md`` yet), the discovery API
    returns the empty tuple AND the L0 agent skips the feedback ingestion
    step entirely. This test pins the cap-with-zero contract.
    """
    # Ensure no .local/feedbacks/ directory exists.
    assert not (tmp_path / ".local" / "feedbacks").exists()

    ctx = scan_workspace(tmp_path)

    assert ctx.recent_feedbacks == (), (
        f"empty .local/feedbacks/ MUST yield recent_feedbacks=(); got {ctx.recent_feedbacks!r}"
    )

    # Also pin the empty-directory case (directory exists but contains no
    # feedback_for_v*.md files) — semantics MUST match the missing-dir case.
    feedbacks_dir = tmp_path / ".local" / "feedbacks"
    feedbacks_dir.mkdir(parents=True)
    (feedbacks_dir / "README.md").write_text("# Feedbacks\n", encoding="utf-8")
    ctx_with_empty_dir = scan_workspace(tmp_path)
    assert ctx_with_empty_dir.recent_feedbacks == (), (
        "feedback dir present but no feedback_for_v*.md files MUST yield "
        "recent_feedbacks=() (the README.md scaffolding is filtered out)"
    )


def test_recent_feedbacks_paths_relative_via_to_summary_dict(tmp_path: Path) -> None:
    """``to_summary_dict()`` renders feedback paths repo-relative (S-2 invariant).

    Per Soul Rule S-2 (No Absolute Paths in Agent Files), every path in
    the dispatch context MUST be repo-relative. The L0 agent surfaces
    ``recent_feedbacks`` paths in plan output and (downstream) in the
    ``change_context.prior_feedback_themes`` block (which cites paths
    by repo-relative POSIX form per §5.5 step 4). This test pins that
    contract by serialising the snapshot through
    :meth:`WorkspaceContext.to_summary_dict` and asserting every
    feedback path string is repo-relative + does NOT start with ``/``.
    """
    feedbacks_dir = tmp_path / ".local" / "feedbacks"
    feedbacks_dir.mkdir(parents=True)
    for ver in ("9.1.0", "9.1.1", "9.1.2"):
        (feedbacks_dir / f"feedback_for_v{ver}.md").write_text(
            f"# Feedback v{ver}\n\n## handoff_auto_write\n## slash_commands_cli\n",
            encoding="utf-8",
        )

    ctx = scan_workspace(tmp_path)
    summary = ctx.to_summary_dict()

    rendered = summary["recent_feedbacks"]
    assert isinstance(rendered, list), "to_summary_dict.recent_feedbacks must be a list"
    assert len(rendered) > 0, "expected at least one feedback path in summary"

    for relpath_str in rendered:
        assert isinstance(relpath_str, str), (
            f"feedback path entry must be str, got {type(relpath_str).__name__}"
        )
        assert not relpath_str.startswith("/"), (
            f"S-2 violation: feedback path {relpath_str!r} is absolute (starts with /); "
            f"plan-mode-enforcement.md §5.5 step 4 + Rule S-2 require repo-relative POSIX form"
        )
        assert relpath_str.startswith(".local/feedbacks/"), (
            f"feedback path {relpath_str!r} must live under .local/feedbacks/ "
            f"(per scan_workspace + plan-mode contract)"
        )

    # Round-trip via json.dumps — the summary dict MUST be JSON-serialisable
    # for dispatch-context injection (no Path objects leak into the wire).
    serialised = json.dumps(summary)
    assert ".local/feedbacks/" in serialised, (
        "JSON round-trip of summary dict must preserve repo-relative feedback paths"
    )


def test_cap_at_three_feedbacks_newest_first_by_mtime(tmp_path: Path) -> None:
    """5 feedback files with staggered mtime → top 3 by mtime desc.

    Pins the ``MAX_FEEDBACKS_RETURNED == 3`` cap shared between
    :mod:`devolaflow.workspace_context` and the plan-mode-enforcement
    contract (§5.5 step 2 cites "the latest 3 by mtime descending — newest
    first"). The test creates 5 staggered-mtime files and asserts the
    discovery API returns exactly 3 in the right order so the L0 agent
    sees the most recent feedback first when extracting themes.
    """
    feedbacks_dir = tmp_path / ".local" / "feedbacks"
    feedbacks_dir.mkdir(parents=True)
    versions = ["9.0.0", "9.0.1", "9.1.0", "9.1.1", "9.1.2"]
    paths: list[Path] = []
    base_mtime = time.time() - 10000
    for idx, ver in enumerate(versions):
        path = feedbacks_dir / f"feedback_for_v{ver}.md"
        path.write_text(
            f"# Feedback v{ver}\n\n## theme_{ver.replace('.', '_')}\n",
            encoding="utf-8",
        )
        # Stagger mtime so the 5 files have a strict total ordering;
        # idx=0 is the oldest, idx=4 is the newest.
        os.utime(path, (base_mtime + idx * 1000, base_mtime + idx * 1000))
        paths.append(path)

    ctx = scan_workspace(tmp_path)

    # The MAX_FEEDBACKS_RETURNED constant MUST be 3 — the test depends
    # on this contract; if it changes the test must be updated in the
    # same PR per the W-18 precondition.
    assert MAX_FEEDBACKS_RETURNED == 3, (
        f"plan-mode contract violation: MAX_FEEDBACKS_RETURNED is "
        f"{MAX_FEEDBACKS_RETURNED}, expected 3 (per "
        f"references/plan-mode-enforcement.md §5.5 + the v9.1.1 PV-01 design)"
    )

    assert len(ctx.recent_feedbacks) == 3, (
        f"5 feedbacks with staggered mtime MUST produce 3 returned paths "
        f"(MAX_FEEDBACKS_RETURNED cap); got {len(ctx.recent_feedbacks)}: "
        f"{[p.name for p in ctx.recent_feedbacks]!r}"
    )

    expected_names = ["feedback_for_v9.1.2.md", "feedback_for_v9.1.1.md", "feedback_for_v9.1.0.md"]
    actual_names = [p.name for p in ctx.recent_feedbacks]
    assert actual_names == expected_names, (
        f"top-3 must be returned newest-first by mtime; expected "
        f"{expected_names}, got {actual_names}. The plan-mode contract "
        f"(§5.5 step 2) cites 'mtime descending (newest first)'."
    )


def test_plan_mode_enforcement_doc_documents_v9_1_4_ingestion_contract() -> None:
    """The plan-mode-enforcement.md §5.5 contains the v9.1.4 ingestion contract.

    Per W-18 (ghost-audit refresh precondition), every CHANGELOG entry
    mentioning a feature MUST have backing coverage. This test pins the
    plan-mode-enforcement.md §"Automatic Ingestion at Plan-Mode Entry
    (v9.1.4+)" sub-section as the canonical contract surface for the
    PV-04 feedback ingestion deliverable.

    Asserts that the document contains:

    * the v9.1.4+ section anchor (proves the sub-section was authored),
    * the documented theme caps (5 themes, 30 chars each — matches
      ``schemas/lean-dispatch.yaml#lean_format_spec.change_context.prior_feedback_themes``),
    * the canonical ``change_context.prior_feedback_themes`` schema cite,
    * the standard ``Read`` tool reference (no new tool permission needed),
    * the S-2 repo-relative path invariant (paths are NOT absolute),
    * a cite of ``MAX_FEEDBACKS_RETURNED`` (or the value 3) so the cap
      contract is locally-discoverable from the doc.
    """
    doc_path = _project_root() / "workflow-system/agent/references/plan-mode-enforcement.md"
    assert doc_path.is_file(), f"plan-mode-enforcement.md missing at {doc_path}"
    body = doc_path.read_text(encoding="utf-8")

    # Section anchor — the sub-section title is the documented stable
    # marker that this contract was authored.
    assert "Automatic Ingestion at Plan-Mode Entry (v9.1.4+)" in body, (
        "plan-mode-enforcement.md §5.5 MUST contain the 'Automatic Ingestion "
        "at Plan-Mode Entry (v9.1.4+)' sub-section heading per the v9.1.4 "
        "PV-04 contract"
    )

    # Theme caps — both must be cited in the section so the L0 agent
    # extracts the right number of themes with the right length cap.
    assert f"≤ {_DOCUMENTED_MAX_THEMES}" in body or f"<= {_DOCUMENTED_MAX_THEMES}" in body, (
        f"plan-mode-enforcement.md MUST cite the ≤ {_DOCUMENTED_MAX_THEMES} themes cap"
    )
    assert (
        f"≤ {_DOCUMENTED_MAX_THEME_CHARS}" in body or f"<= {_DOCUMENTED_MAX_THEME_CHARS}" in body
    ), f"plan-mode-enforcement.md MUST cite the ≤ {_DOCUMENTED_MAX_THEME_CHARS} chars per theme cap"

    # Schema cite — the canonical surface for the surfaced themes.
    assert "change_context.prior_feedback_themes" in body, (
        "plan-mode-enforcement.md MUST cite the canonical "
        "`change_context.prior_feedback_themes` schema field surfaced by "
        "`schemas/lean-dispatch.yaml`"
    )

    # Read-tool reference — no new tool permission required for the L0
    # agent (uses the existing plan-mode-allowed Read tool).
    assert "Read" in body, "plan-mode-enforcement.md MUST cite the standard `Read` tool"

    # S-2 cite — paths surfaced as repo-relative.
    assert "S-2" in body, (
        "plan-mode-enforcement.md MUST cite Soul Rule S-2 (paths are repo-relative, not absolute)"
    )

    # MAX_FEEDBACKS_RETURNED cap (matches the value 3 the discovery API
    # ships in :mod:`devolaflow.workspace_context`).
    assert "MAX_FEEDBACKS_RETURNED" in body or "_RECENT_FEEDBACKS_LIMIT" in body or "3 " in body, (
        "plan-mode-enforcement.md MUST cite the per-PV-04 cap (the "
        "MAX_FEEDBACKS_RETURNED == 3 constant from "
        "devolaflow.workspace_context)"
    )
