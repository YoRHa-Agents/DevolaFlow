"""Tests for the v8.2.7 ``devolaflow.agent_workspace.reporter`` module.

Covers AC-1 through AC-8 from ``.local/research/v8.3.0_patch_plan.md``
§v8.2.7 + the per-test list in the L3 dispatch:

* AC-1: ``render_change_report`` produces valid Markdown matching the
  template.
* AC-2: ``render_workspace_report`` enumerates active + recently
  archived changes (with a 7-day window).
* AC-3: ``render_memory_report`` aggregates learnings by ``task_type``
  and surfaces the top-10 by confidence × promotion_count.
* AC-4: ``render_rules_report`` enumerates layers + compile-target
  status from ``.rules/.compile-hashes.json``.
* AC-5: ``regenerate_all`` is byte-identical when invoked twice with a
  pinned ``now`` (idempotency).
* AC-6: ``python -m devolaflow.agent_workspace.reporter --workspace``
  CLI writes the workspace REPORT.
* AC-7: this file pushes coverage on reporter.py to ≥ 80% (verified
  by the coverage check in v8.2.7 Final Verification).
* AC-8: SI-10 6/6 is verified by the orchestrating L2 task agent.

All tests use ``tmp_path`` fixtures so they run in isolation from the
real ``.local/.agent/`` tree on disk.
"""

from __future__ import annotations

import inspect
import json
import logging
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from devolaflow._workspace_reporter.data import (
    _aggregate_by_task_type,
    _load_jsonl_entries,
    _parse_learnings_jsonl,
    _select_top_learnings,
    _summarise_handoff_chain,
    _verification_block,
)
from devolaflow.agent_workspace import (
    HumanBudgetExceededError,
    regenerate_all,
    render_change_report,
    render_human_digest,
    render_human_report,
    render_memory_report,
    render_rules_report,
    render_workspace_report,
)
from devolaflow.agent_workspace.reporter import (
    DEFAULT_ARCHIVE_WINDOW_DAYS,
)
from devolaflow.agent_workspace.reporter import (
    main as reporter_main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


PINNED_NOW = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Return a tmp_path configured with the canonical .local/.agent layout."""
    (tmp_path / ".local" / ".agent" / "active").mkdir(parents=True)
    (tmp_path / ".local" / ".agent" / "handoff").mkdir(parents=True)
    (tmp_path / ".local" / ".agent" / "archive").mkdir(parents=True)
    (tmp_path / ".local" / "memory" / "specs").mkdir(parents=True)
    (tmp_path / ".rules").mkdir()
    return tmp_path


def _scaffold_change(
    folder: Path,
    *,
    change_id: str,
    state: str = "ARCHIVED",
    spec_md: str | None = None,
    goal_md: str | None = None,
    checklist_md: str | None = None,
    owned_files: list[str] | None = None,
    learnings_jsonl: str | None = None,
    status_overrides: dict | None = None,
    handoff_chain: list[dict] | None = None,
) -> Path:
    """Scaffold a populated change folder with the seven artifacts.

    ``folder`` is the on-disk folder (active or archive); the caller is
    responsible for placing it under the right tree. Returns the same
    folder path for convenience.
    """
    folder.mkdir(parents=True, exist_ok=True)

    goal = goal_md or textwrap.dedent(
        f"""\
        ---
        id: {change_id}
        created: "2026-04-22T10:00:00Z"
        priority: P2
        intent_class: feature
        ---

        # Goal: Sample change for {change_id}

        ## Why
        We need a deterministic feature so the reporter test can assert
        verbatim extraction of the goal block.

        ## In scope
        - Tests pass

        ## Out of scope
        - Real users
        """
    )
    (folder / "goal.md").write_text(goal, encoding="utf-8")

    if spec_md is None:
        spec_md = textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            delta_target: agent_workspace
            delta_kind: lite
            ---

            # Operation Spec for {change_id}

            ## Purpose
            Sample purpose: ship the v8.2.7 reporter test fixture.

            ## ADDED Requirements

            ### Requirement: Sample reporter requirement
            The reporter MUST emit a Markdown report.
            """
        )
    (folder / "spec.md").write_text(spec_md, encoding="utf-8")

    if checklist_md is None:
        checklist_md = textwrap.dedent(
            f"""\
            ---
            parent: {change_id}
            schema_version: 1
            total_items: 2
            checked: 0
            priority_dist: {{P0: 2, P1: 0, P2: 0}}
            reverted_open: 0
            ---

            # Checklist

            ## G1: Implementation
            - [ ] C-G1.1 (P0) Write code
                  verify: manual

            ## G2: Tests
            - [ ] C-G2.1 (P0) Write tests
                  verify: manual
            """
        )
    (folder / "checklist.md").write_text(checklist_md, encoding="utf-8")

    status: dict = {
        "schema_version": 1,
        "change_id": change_id,
        "state": state,
        "percent_complete": 100 if state == "ARCHIVED" else 50,
        "owner_layer": "L3",
        "owner_session_id": "test-session-001",
        "last_updated": "2026-04-22T11:30:00Z",
        "last_handoff_seq": 0,
        "gate_score": 9.4,
        "verify_pass": True,
    }
    if status_overrides:
        status.update(status_overrides)
    (folder / "STATUS.yaml").write_text(
        yaml.safe_dump(status, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    if owned_files is None:
        paths = [
            "src/devolaflow/agent_workspace/reporter.py",
            "tests/test_reporter.py",
        ]
    else:
        paths = owned_files
    owned_text = "\n".join(paths)
    if owned_text:
        owned_text += "\n"
    (folder / "owned_files.txt").write_text(
        owned_text,
        encoding="utf-8",
        newline="\n",
    )

    if learnings_jsonl is not None:
        (folder / "learnings.jsonl").write_text(learnings_jsonl, encoding="utf-8", newline="\n")

    if handoff_chain is not None:
        (folder / "handoff_chain.yaml").write_text(
            yaml.safe_dump(handoff_chain, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    return folder


def _scaffold_rules(rules_root: Path) -> None:
    """Populate ``rules_root`` with the canonical 5-layer .mdc files + hashes."""
    layers: dict[str, tuple[bool, list[str]]] = {
        "soul.mdc": (True, ["S-1", "S-2", "S-3"]),
        "architecture.mdc": (True, ["A-1", "A-2"]),
        "conventions.mdc": (True, ["C-1", "C-2", "C-3", "C-4"]),
        "workflow.mdc": (False, ["W-1"]),
        "style.mdc": (False, ["ST-1", "ST-2", "ST-3", "ST-4", "ST-5"]),
    }
    for filename, (always, rules) in layers.items():
        body_lines = [
            "---",
            f'description: "Test layer {filename}"',
            f"alwaysApply: {str(always).lower()}",
            "---",
            "",
            f"# {filename.replace('.mdc', '').title()} Rules",
            "",
        ]
        for rule_id in rules:
            body_lines.append(f"## {rule_id} — Test rule {rule_id}")
            body_lines.append("")
            body_lines.append(f"Body for {rule_id}.")
            body_lines.append("")
        (rules_root / filename).write_text("\n".join(body_lines), encoding="utf-8")

    config = {
        "version": "1.0",
        "source_dir": ".rules",
        "layers": [
            {"name": "soul", "file": "soul.mdc", "priority": 0, "always_include": True},
            {"name": "arch", "file": "architecture.mdc", "priority": 1, "always_include": True},
        ],
        "targets": {
            "cursor": {
                "output": ".cursor/rules/repo-governance.mdc",
                "format": "mdc",
                "token_budget": 8000,
            },
            "agents_md": {
                "output": "AGENTS.md",
                "format": "markdown",
                "token_budget": 6000,
            },
        },
    }
    (rules_root / "compile-config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    (rules_root / ".compile-hashes.json").write_text(
        json.dumps({"cursor": "abc123def456", "agents_md": "fed654cba321"}, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public API surface (test_reporter_imports_via_public_api)
# ---------------------------------------------------------------------------


class TestPublicApiSurface:
    """The five reporter symbols MUST be importable from
    :mod:`devolaflow.agent_workspace`."""

    def test_reporter_imports_via_public_api(self):
        from devolaflow import agent_workspace

        for name in (
            "render_change_report",
            "render_workspace_report",
            "render_memory_report",
            "render_rules_report",
            "regenerate_all",
        ):
            assert hasattr(agent_workspace, name), f"missing {name}"
            assert name in agent_workspace.__all__, f"{name} not in __all__"


# ---------------------------------------------------------------------------
# Per-change report (AC-1)
# ---------------------------------------------------------------------------


class TestChangeReport:
    def test_render_change_report_minimal(self, workspace: Path):
        """Basic archived change → valid Markdown with all expected sections."""
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-min-change"
        _scaffold_change(archive_folder, change_id="min-change")

        text = render_change_report("min-change", repo_root=workspace, now=PINNED_NOW)

        assert text.startswith("# Change Report: min-change")
        # Every section heading from design.md §5.1 must appear.
        for heading in (
            "## What changed",
            "## Why",
            "## How",
            "## Verification",
            "## Files touched",
            "## Learnings extracted",
            "## Handoff chain summary",
        ):
            assert heading in text, f"missing section heading {heading!r}"

    def test_render_change_report_extracts_spec_delta_sections(self, workspace: Path):
        """spec.md ADDED/MODIFIED/REMOVED sections → 'What changed' lists each."""
        spec = textwrap.dedent(
            """\
            ---
            parent: delta-test
            delta_target: agent_workspace
            delta_kind: full
            ---

            # Operation Spec for delta-test

            ## Purpose
            Cover all three delta sections in one fixture.

            ## ADDED Requirements

            ### Requirement: New A
            The system MUST do A.

            ### Requirement: New B
            The system MUST do B.

            ## MODIFIED Requirements

            ### Requirement: Existing C
            The system NOW does C.

            ## REMOVED Requirements

            ### Requirement: Old D
            (Reason for removal.)
            """
        )
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-delta-test"
        _scaffold_change(archive_folder, change_id="delta-test", spec_md=spec)

        text = render_change_report("delta-test", repo_root=workspace, now=PINNED_NOW)
        assert "**ADDED**: New A" in text
        assert "**ADDED**: New B" in text
        assert "**MODIFIED**: Existing C" in text
        assert "**REMOVED**: Old D" in text

    def test_render_change_report_extracts_goal_why(self, workspace: Path):
        """goal.md `## Why` is extracted verbatim into the Why section."""
        goal = textwrap.dedent(
            """\
            ---
            id: why-test
            created: "2026-04-22T10:00:00Z"
            priority: P3
            intent_class: feature
            ---

            # Goal: Why test

            ## Why
            VERBATIM_WHY_MARKER for the test assertion to confirm extraction.

            ## In scope
            - Coverage
            """
        )
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-why-test"
        _scaffold_change(archive_folder, change_id="why-test", goal_md=goal)

        text = render_change_report("why-test", repo_root=workspace, now=PINNED_NOW)
        assert "VERBATIM_WHY_MARKER for the test assertion to confirm extraction." in text

    def test_render_change_report_owned_files_verbatim(self, workspace: Path):
        """owned_files.txt content reproduced verbatim under Files touched."""
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-files-test"
        _scaffold_change(
            archive_folder,
            change_id="files-test",
            owned_files=[
                "src/devolaflow/foo.py",
                "src/devolaflow/bar.py",
                "tests/test_foobar.py",
            ],
        )

        text = render_change_report("files-test", repo_root=workspace, now=PINNED_NOW)
        for path in (
            "`src/devolaflow/foo.py`",
            "`src/devolaflow/bar.py`",
            "`tests/test_foobar.py`",
        ):
            assert path in text, f"missing owned-file mention {path!r}"

    def test_render_change_report_handles_missing_optional_sections(self, workspace: Path):
        """Change with no spec/learnings → still renders cleanly with empty-state markers."""
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-empty-test"
        _scaffold_change(
            archive_folder,
            change_id="empty-test",
            spec_md="---\nparent: empty-test\ndelta_target: empty\ndelta_kind: lite\n---\n",
            checklist_md=(
                "---\nparent: empty-test\nschema_version: 1\ntotal_items: 0\nchecked: 0\n"
                "priority_dist: {P0: 0, P1: 0, P2: 0}\nreverted_open: 0\n---\n\n# Checklist\n"
            ),
            owned_files=[],
            learnings_jsonl=None,
        )

        text = render_change_report("empty-test", repo_root=workspace, now=PINNED_NOW)
        assert "_No requirement deltas recorded._" in text
        assert "_No owned files recorded._" in text
        assert "_No learnings extracted._" in text
        assert "_No handoff envelopes recorded._" in text

    def test_render_change_report_extracts_learnings_with_confidence(self, workspace: Path):
        """learnings.jsonl entries appear under Learnings extracted with confidence."""
        learnings = (
            '{"key":"k1","stage":"impl","task_type":"test",'
            '"insight":"INSIGHT_ONE","confidence":0.92,"promotion_count":3}\n'
            '{"key":"k2","stage":"impl","task_type":"test",'
            '"insight":"INSIGHT_TWO","confidence":0.78,"promotion_count":1}\n'
        )
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-learn-test"
        _scaffold_change(archive_folder, change_id="learn-test", learnings_jsonl=learnings)

        text = render_change_report("learn-test", repo_root=workspace, now=PINNED_NOW)
        assert "INSIGHT_ONE (confidence: 0.92)" in text
        assert "INSIGHT_TWO (confidence: 0.78)" in text

    def test_render_change_report_handoff_chain_rendered(self, workspace: Path):
        """Frozen handoff_chain.yaml entries render as one-line-per-hop summaries."""
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-hop-test"
        _scaffold_change(
            archive_folder,
            change_id="hop-test",
            handoff_chain=[
                {
                    "seq": 1,
                    "from_layer": "L0",
                    "to_layer": "L2",
                    "envelope_kind": "TaskDispatch",
                },
                {
                    "seq": 2,
                    "from_layer": "L2",
                    "to_layer": "L0",
                    "envelope_kind": "StatusReport",
                },
            ],
        )

        text = render_change_report("hop-test", repo_root=workspace, now=PINNED_NOW)
        assert "seq 0001: L0 → L2 (TaskDispatch)" in text
        assert "seq 0002: L2 → L0 (StatusReport)" in text

    def test_render_change_report_raises_when_change_absent(self, workspace: Path):
        from devolaflow.agent_workspace import ChangeNotFoundError

        with pytest.raises(ChangeNotFoundError):
            render_change_report("does-not-exist", repo_root=workspace, now=PINNED_NOW)


# ---------------------------------------------------------------------------
# Workspace report (AC-2)
# ---------------------------------------------------------------------------


class TestWorkspaceReport:
    def test_render_workspace_report_lists_active_and_archived(self, workspace: Path):
        """active/<a>/STATUS.yaml + archive/<date>-<b>/ both appear in correct tables."""
        active_folder = workspace / ".local" / ".agent" / "active" / "active-one"
        _scaffold_change(active_folder, change_id="active-one", state="IN_PROGRESS")

        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-archived-one"
        _scaffold_change(archive_folder, change_id="archived-one", state="ARCHIVED")

        text = render_workspace_report(repo_root=workspace, now=PINNED_NOW)
        assert "Active changes: 1" in text
        assert "Archived (last 7 days): 1" in text
        assert "active-one" in text
        assert "IN_PROGRESS" in text
        assert "archived-one" in text
        assert "2026-04-22" in text

    def test_render_workspace_report_archive_filter_7_days(self, workspace: Path):
        """Archive older than 7 days is excluded from the recently-archived table."""
        new_archive = workspace / ".local" / ".agent" / "archive" / "2026-04-22-recent"
        old_archive = workspace / ".local" / ".agent" / "archive" / "2026-03-15-stale"
        _scaffold_change(new_archive, change_id="recent", state="ARCHIVED")
        _scaffold_change(old_archive, change_id="stale", state="ARCHIVED")

        text = render_workspace_report(repo_root=workspace, now=PINNED_NOW)
        assert "recent" in text
        assert "stale" not in text
        assert "Archived (last 7 days): 1" in text

    def test_render_workspace_report_empty_workspace(self, workspace: Path):
        """Empty active+archive → empty-state markers, headers still present."""
        text = render_workspace_report(repo_root=workspace, now=PINNED_NOW)
        assert "Active changes: 0" in text
        assert "Archived (last 7 days): 0" in text
        assert "_No active changes._" in text
        assert "_No recent archives._" in text

    def test_render_workspace_report_window_days_param_changes_header(self, workspace: Path):
        text = render_workspace_report(repo_root=workspace, now=PINNED_NOW, archive_window_days=14)
        assert "Archived (last 14 days)" in text

    def test_render_workspace_report_accepts_legacy_workspace_root(self, workspace: Path):
        """The compatibility keyword remains in the API and is an explicit no-op."""
        parameter = inspect.signature(render_workspace_report).parameters["workspace_root"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is None
        expected = render_workspace_report(repo_root=workspace, now=PINNED_NOW)
        actual = render_workspace_report(
            repo_root=workspace,
            workspace_root=workspace / "historical-workspace-root",
            now=PINNED_NOW,
        )
        assert actual == expected


class TestReporterDataHelpers:
    def test_malformed_and_legacy_data_paths_are_explicit(self, tmp_path: Path):
        """Data helpers keep malformed rows visible to logs and preserve fallbacks."""
        learnings = _parse_learnings_jsonl(
            '\nnot-json\n[]\n{"confidence": 0.2}\n{"confidence": 0.9}\n'
        )
        assert [row["confidence"] for row in learnings] == [0.9, 0.2]

        jsonl_path = tmp_path / "entries.jsonl"
        jsonl_path.write_text("\nnot-json\n{}\n[]\n", encoding="utf-8")
        assert _load_jsonl_entries(jsonl_path) == [{}]

        assert _aggregate_by_task_type(
            [{"task_type": "review", "confidence": "unknown", "pinned_for_session": " yes "}]
        ) == [{"task_type": "review", "count": 1, "avg_confidence": 0.0, "pinned": 1}]

        assert (
            _select_top_learnings(
                [{"insight": "kept", "timestamp": "not-an-iso-date", "confidence": "unknown"}],
                window_days=30,
                top_n=0,
                now=PINNED_NOW,
            )
            == []
        )

    def test_frozen_handoff_mapping_and_verification_fallbacks(self, tmp_path: Path):
        """Frozen mapping envelopes and malformed verification values stay deterministic."""
        folder = tmp_path / "change"
        folder.mkdir()
        frozen = folder / "handoff_chain.yaml"
        frozen.write_text(
            (
                "envelopes:\n"
                "  - seq: 2\n"
                "    from_layer: L1\n"
                "    to_layer: L2\n"
                "    envelope_kind: StatusReport\n"
            ),
            encoding="utf-8",
        )
        assert _summarise_handoff_chain("change", folder, tmp_path) == [
            "seq 0002: L1 → L2 (StatusReport)"
        ]

        frozen.write_text("[unclosed", encoding="utf-8")
        assert _summarise_handoff_chain("change", folder, tmp_path) == []

        assert _verification_block(
            {"verification": "invalid", "gate_score": "unknown", "coverage_pct": "unknown"}
        ) == {
            "ac_pass_rate": "<unknown>",
            "tests_passed": "<unknown>",
            "coverage": "unknown",
            "lint": "<unknown>",
            "format": "<unknown>",
            "gate_score": "<unknown>",
        }


# ---------------------------------------------------------------------------
# Memory report (AC-3)
# ---------------------------------------------------------------------------


class TestMemoryReport:
    def test_render_memory_report_groups_by_task_type(self, workspace: Path):
        """JSONL with mixed task_types → aggregated rows (sorted alphabetically)."""
        operational = workspace / ".local" / "memory" / "operational.jsonl"
        operational.parent.mkdir(parents=True, exist_ok=True)
        operational.write_text(
            "\n".join(
                json.dumps(e)
                for e in (
                    {
                        "key": "k1",
                        "stage": "impl",
                        "task_type": "implement",
                        "insight": "alpha",
                        "confidence": 0.8,
                        "promotion_count": 1,
                        "timestamp": "2026-04-20T00:00:00Z",
                    },
                    {
                        "key": "k2",
                        "stage": "impl",
                        "task_type": "implement",
                        "insight": "bravo",
                        "confidence": 0.6,
                        "promotion_count": 0,
                        "timestamp": "2026-04-20T00:00:00Z",
                    },
                    {
                        "key": "k3",
                        "stage": "review",
                        "task_type": "review",
                        "insight": "charlie",
                        "confidence": 0.9,
                        "promotion_count": 4,
                        "timestamp": "2026-04-20T00:00:00Z",
                    },
                )
            )
            + "\n",
            encoding="utf-8",
        )

        text = render_memory_report(repo_root=workspace, now=PINNED_NOW)
        # Both task_types must appear in the table.
        assert "| implement | 2 |" in text
        assert "| review | 1 |" in text
        # Total surfaces in the header bar.
        assert "Total learnings: 3" in text

    def test_render_memory_report_top_10_high_confidence(self, workspace: Path):
        """Top 10 ranking is by confidence × (1 + promotion_count) descending."""
        operational = workspace / ".local" / "memory" / "operational.jsonl"
        operational.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for i in range(15):
            rows.append(
                {
                    "key": f"k{i:02d}",
                    "stage": "impl",
                    "task_type": "implement",
                    "insight": f"INSIGHT_{i:02d}",
                    "confidence": 0.5 + (i * 0.03),
                    "promotion_count": i,
                    "timestamp": "2026-04-22T00:00:00Z",
                }
            )
        operational.write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n",
            encoding="utf-8",
        )

        text = render_memory_report(repo_root=workspace, now=PINNED_NOW)
        # Highest score is k14 (0.92 * 15 = 13.8); lowest in top 10 is k05 (0.65 * 6 = 3.9).
        assert "1. INSIGHT_14" in text
        assert "INSIGHT_05" in text
        # Anything below INSIGHT_05 should NOT appear.
        assert "INSIGHT_03" not in text
        # The header is templated with the window value.
        assert "Top 10 high-confidence learnings" in text

    def test_render_memory_report_empty(self, workspace: Path):
        """Empty/missing JSONL → empty-state markers."""
        text = render_memory_report(repo_root=workspace, now=PINNED_NOW)
        assert "Total learnings: 0" in text
        assert "_No learnings recorded._" in text
        assert "_No high-confidence learnings._" in text
        assert "_No external source reviews recorded._" in text

    def test_render_memory_report_external_reviews(self, workspace: Path):
        external = workspace / ".local" / "memory" / "external-sources.jsonl"
        external.parent.mkdir(parents=True, exist_ok=True)
        external.write_text(
            json.dumps(
                {
                    "source_id": "openspec",
                    "review_date": "2026-04-22",
                    "findings_summary": "Adopt delta spec format",
                    "relevance_delta": 5.0,
                    "timestamp": "2026-04-22T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        text = render_memory_report(repo_root=workspace, now=PINNED_NOW)
        assert "openspec" in text
        assert "Adopt delta spec format" in text


# ---------------------------------------------------------------------------
# Rules report (AC-4)
# ---------------------------------------------------------------------------


class TestRulesReport:
    def test_render_rules_report_counts_rules_per_layer(self, workspace: Path):
        """5 layer files → 5 rows; rule counts match heading occurrences."""
        _scaffold_rules(workspace / ".rules")

        text = render_rules_report(repo_root=workspace, now=PINNED_NOW)
        assert "Layers: 5" in text
        # Total rules from the fixture: 3 + 2 + 4 + 1 + 5 = 15.
        assert "Total rules: 15" in text
        assert "soul.mdc | 3 | yes" in text
        assert "architecture.mdc | 2 | yes" in text
        assert "conventions.mdc | 4 | yes" in text
        assert "workflow.mdc | 1 | no" in text
        assert "style.mdc | 5 | no" in text

    def test_render_rules_report_compile_target_status(self, workspace: Path):
        """Reads .rules/.compile-hashes.json → shows hashes for each target."""
        _scaffold_rules(workspace / ".rules")

        text = render_rules_report(repo_root=workspace, now=PINNED_NOW)
        assert "Drift: OK" in text
        assert "abc123def456" in text
        assert "fed654cba321" in text
        assert "cursor" in text
        assert "agents_md" in text

    def test_render_rules_report_handles_missing_layers(self, workspace: Path):
        """Missing .mdc files → row appears with rule_count=0 and <missing> marker."""
        # Only create one of the five expected layer files.
        (workspace / ".rules" / "soul.mdc").write_text(
            "---\nalwaysApply: true\n---\n# Soul\n## S-1 — only one\n",
            encoding="utf-8",
        )
        text = render_rules_report(repo_root=workspace, now=PINNED_NOW)
        assert "Layers: 5" in text
        # The missing layers should still show up but with 0 rule count + <missing>.
        assert "<missing>" in text

    def test_render_rules_report_drift_missing_when_no_hash_file(self, workspace: Path):
        """When .compile-hashes.json is absent, Drift column reads 'missing'."""
        _scaffold_rules(workspace / ".rules")
        (workspace / ".rules" / ".compile-hashes.json").unlink()
        text = render_rules_report(repo_root=workspace, now=PINNED_NOW)
        assert "Drift: missing" in text


# ---------------------------------------------------------------------------
# regenerate_all (AC-5, idempotency)
# ---------------------------------------------------------------------------


class TestRegenerateAll:
    def test_regenerate_all_idempotent(self, workspace: Path):
        """2× call with pinned ``now`` → byte-identical files for every output."""
        _scaffold_rules(workspace / ".rules")
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-idem-test"
        _scaffold_change(archive_folder, change_id="idem-test")

        first = regenerate_all(repo_root=workspace, now=PINNED_NOW)
        first_bytes = {
            str(p): (p.read_bytes() if isinstance(p, Path) and p.exists() else None)
            for key in ("workspace", "memory", "rules")
            for p in [first[key]]
        }
        first_change_bytes = {str(p): p.read_bytes() for p in first["changes"] if p.exists()}

        second = regenerate_all(repo_root=workspace, now=PINNED_NOW)
        for key in ("workspace", "memory", "rules"):
            path = second[key]
            assert isinstance(path, Path) and path.exists()
            assert path.read_bytes() == first_bytes[str(path)], (
                f"{key} report drifted between calls"
            )
        for path in second["changes"]:
            assert path.read_bytes() == first_change_bytes[str(path)], (
                f"per-change report drifted: {path}"
            )

    def test_regenerate_all_returns_dict_of_paths(self, workspace: Path):
        """Returned dict has the expected keys, all valued as Paths (or list[Path])."""
        _scaffold_rules(workspace / ".rules")
        result = regenerate_all(repo_root=workspace, now=PINNED_NOW)
        for key in ("workspace", "memory", "rules"):
            assert key in result, f"missing key {key!r}"
            assert isinstance(result[key], Path)
        assert "changes" in result
        assert isinstance(result["changes"], list)

    def test_regenerate_all_writes_to_canonical_paths(self, workspace: Path):
        """Outputs land at the canonical paths declared in design.md §5."""
        _scaffold_rules(workspace / ".rules")
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-cano-test"
        _scaffold_change(archive_folder, change_id="cano-test")

        result = regenerate_all(repo_root=workspace, now=PINNED_NOW)
        assert result["workspace"] == workspace / ".local" / ".agent" / "REPORT.md"
        assert result["memory"] == workspace / ".local" / "memory" / "REPORT.md"
        assert result["rules"] == workspace / ".rules" / "REPORT.md"
        assert (archive_folder / "REPORT.md") in result["changes"]
        # Every advertised file must actually exist on disk.
        assert result["workspace"].exists()
        assert result["memory"].exists()
        assert result["rules"].exists()
        assert (archive_folder / "REPORT.md").exists()


# ---------------------------------------------------------------------------
# CLI invocation (AC-6)
# ---------------------------------------------------------------------------


class TestReporterCli:
    def test_cli_module_invocation(self, workspace: Path):
        """`python -m devolaflow.agent_workspace.reporter --workspace` writes the file."""
        env_repo = workspace
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "devolaflow.agent_workspace.reporter",
                "--workspace",
                "--repo-root",
                str(env_repo),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"CLI failed: stderr={result.stderr!r}"
        assert (env_repo / ".local" / ".agent" / "REPORT.md").exists()

    def test_cli_main_workspace_print_to_stdout(self, capsys, workspace: Path):
        """`reporter_main(['--workspace', '--print'])` writes to stdout, not disk."""
        rc = reporter_main(
            [
                "--workspace",
                "--repo-root",
                str(workspace),
                "--print",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "Agent Workspace Status" in captured.out
        assert not (workspace / ".local" / ".agent" / "REPORT.md").exists()

    def test_cli_main_now_flag_pins_clock_and_rejects_malformed(self, capsys, workspace: Path):
        """`--now <iso>` yields byte-identical output; malformed values exit 2."""
        argv = [
            "--workspace",
            "--repo-root",
            str(workspace),
            "--print",
            "--now",
            "2026-08-28T00:00:00Z",
        ]
        assert reporter_main(argv) == 0
        first = capsys.readouterr().out
        assert reporter_main(argv) == 0
        second = capsys.readouterr().out
        assert "Last updated: 2026-08-28T00:00:00Z" in first
        assert first == second

        with pytest.raises(SystemExit) as excinfo:
            reporter_main(
                [
                    "--workspace",
                    "--repo-root",
                    str(workspace),
                    "--print",
                    "--now",
                    "not-a-datetime",
                ]
            )
        assert excinfo.value.code == 2
        assert "--now must be an ISO-8601 datetime" in capsys.readouterr().err

    def test_cli_main_all_flag(self, workspace: Path):
        """`reporter_main(['--all'])` regenerates every report."""
        _scaffold_rules(workspace / ".rules")
        rc = reporter_main(["--all", "--repo-root", str(workspace)])
        assert rc == 0
        assert (workspace / ".local" / ".agent" / "REPORT.md").exists()
        assert (workspace / ".local" / "memory" / "REPORT.md").exists()
        assert (workspace / ".rules" / "REPORT.md").exists()

    def test_cli_main_change_flag_writes_archive_report(self, workspace: Path):
        """`--change <id>` writes the per-change REPORT in the archive folder."""
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-cli-change"
        _scaffold_change(archive_folder, change_id="cli-change")

        rc = reporter_main(
            [
                "--change",
                "cli-change",
                "--repo-root",
                str(workspace),
            ]
        )
        assert rc == 0
        assert (archive_folder / "REPORT.md").exists()

    def test_cli_main_change_unknown_returns_2(self, workspace: Path, capsys):
        """Unknown change-id → CLI exits with code 2 (usage / not-found)."""
        rc = reporter_main(
            [
                "--change",
                "no-such-change",
                "--repo-root",
                str(workspace),
            ]
        )
        assert rc == 2
        assert "no-such-change" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Misc invariants
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_default_archive_window_is_seven_days(self):
        assert DEFAULT_ARCHIVE_WINDOW_DAYS == 7

    def test_render_change_report_active_change_falls_back(self, workspace: Path):
        """With no archive folder, render finds the active folder by id."""
        active_folder = workspace / ".local" / ".agent" / "active" / "active-only"
        _scaffold_change(active_folder, change_id="active-only", state="IN_PROGRESS")

        text = render_change_report("active-only", repo_root=workspace, now=PINNED_NOW)
        assert "active-only" in text
        # Active-folder reports get the <active> sentinel for the date.
        assert "<active>" in text

    def test_workspace_report_skips_archive_with_bad_date_prefix(self, workspace: Path):
        """An archive folder with a non-date-looking prefix is skipped (defensive)."""
        odd = workspace / ".local" / ".agent" / "archive" / "no-date-prefix"
        # Only valid kebab-case names are allowed; we still scaffold one to hit
        # the date-parse fallback path safely.
        _scaffold_change(odd, change_id="no-date-prefix", state="ARCHIVED")
        # The folder name has no YYYY-MM-DD prefix → ChangeStore.list_archive
        # will return ("", "no-date-prefix") which should be filtered out.
        text = render_workspace_report(repo_root=workspace, now=PINNED_NOW)
        assert "Archived (last 7 days): 0" in text

    def test_compile_target_status_no_recorded_hash(self, workspace: Path):
        """A compile target with no recorded hash → 'no recorded hash' status."""
        rules_root = workspace / ".rules"
        _scaffold_rules(rules_root)
        # Wipe the recorded hash for one target.
        (rules_root / ".compile-hashes.json").write_text(
            json.dumps({"cursor": "abc123def456"}),
            encoding="utf-8",
        )
        text = render_rules_report(repo_root=workspace, now=PINNED_NOW)
        assert "no recorded hash" in text
        assert "abc123def456" in text

    def test_compile_target_status_output_missing(self, workspace: Path):
        """With recorded hash but missing output file → status keeps the hash."""
        rules_root = workspace / ".rules"
        _scaffold_rules(rules_root)
        # The fixture's compile-config points at .cursor/rules/repo-governance.mdc
        # and AGENTS.md, neither of which exist in tmp_path → exercise the
        # 'output missing' branch.
        text = render_rules_report(repo_root=workspace, now=PINNED_NOW)
        assert "(output missing)" in text
        assert "abc123def456" in text

    def test_render_memory_report_window_zero_disables_filter(self, workspace: Path):
        """`window_days=0` returns all entries regardless of timestamp age."""
        operational = workspace / ".local" / "memory" / "operational.jsonl"
        operational.parent.mkdir(parents=True, exist_ok=True)
        operational.write_text(
            json.dumps(
                {
                    "key": "ancient",
                    "stage": "impl",
                    "task_type": "implement",
                    "insight": "ANCIENT_INSIGHT_MARKER",
                    "confidence": 0.9,
                    "promotion_count": 5,
                    "timestamp": "2020-01-01T00:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        text = render_memory_report(repo_root=workspace, now=PINNED_NOW, window_days=0)
        assert "ANCIENT_INSIGHT_MARKER" in text

    def test_render_memory_report_skips_entries_with_no_insight(self, workspace: Path):
        """JSONL rows with empty `insight` are excluded from the top-N section."""
        operational = workspace / ".local" / "memory" / "operational.jsonl"
        operational.parent.mkdir(parents=True, exist_ok=True)
        operational.write_text(
            "\n".join(
                json.dumps(e)
                for e in (
                    {
                        "key": "k1",
                        "stage": "impl",
                        "task_type": "implement",
                        "insight": "",
                        "confidence": 0.99,
                        "promotion_count": 99,
                        "timestamp": "2026-04-22T00:00:00Z",
                    },
                    {
                        "key": "k2",
                        "stage": "impl",
                        "task_type": "implement",
                        "insight": "REAL_INSIGHT",
                        "confidence": 0.5,
                        "promotion_count": 0,
                        "timestamp": "2026-04-22T00:00:00Z",
                    },
                )
            )
            + "\n",
            encoding="utf-8",
        )
        text = render_memory_report(repo_root=workspace, now=PINNED_NOW)
        assert "REAL_INSIGHT" in text
        assert "Total learnings: 2" in text

    def test_render_change_report_skips_malformed_learnings_lines(self, workspace: Path):
        """Malformed JSONL lines in learnings.jsonl are skipped (loud only via log)."""
        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-bad-jsonl"
        learnings = (
            "this is not json\n"
            '{"key":"k1","stage":"impl","task_type":"test","insight":"GOOD","confidence":0.7}\n'
        )
        _scaffold_change(archive_folder, change_id="bad-jsonl", learnings_jsonl=learnings)
        text = render_change_report("bad-jsonl", repo_root=workspace, now=PINNED_NOW)
        assert "GOOD (confidence: 0.70)" in text

    def test_render_change_report_with_live_handoff_envelopes(self, workspace: Path):
        """Without a frozen handoff_chain.yaml, live envelopes are summarised."""
        from devolaflow.agent_workspace import HandoffEnvelope, HandoffStore

        archive_folder = workspace / ".local" / ".agent" / "archive" / "2026-04-22-live-hop"
        _scaffold_change(archive_folder, change_id="live-hop")
        store = HandoffStore(repo_root=workspace)
        env = HandoffEnvelope(
            seq=1,
            from_layer="L0",
            to_layer="L2",
            change_id="live-hop",
            created="2026-04-22T10:00:00Z",
            envelope_kind="TaskDispatch",
            dispatch={"task_id": "T01", "type": "implement"},
        )
        store.write_envelope(env)
        text = render_change_report("live-hop", repo_root=workspace, now=PINNED_NOW)
        assert "seq 0001: L0 → L2 (TaskDispatch)" in text

    def test_cli_main_no_flags_returns_2(self, workspace: Path):
        """Calling reporter_main with no flavour flag exits 2 (usage error)."""
        with pytest.raises(SystemExit) as exc:
            reporter_main(["--repo-root", str(workspace)])
        assert exc.value.code == 2

    def test_cli_main_print_with_all_returns_2(self, workspace: Path):
        """`--print` plus `--all` is a usage error (exits 2)."""
        with pytest.raises(SystemExit) as exc:
            reporter_main(["--all", "--print", "--repo-root", str(workspace)])
        assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Human convergence report + digest — the FIFTH flavour
# (v14.0.0 Wave-2; design §4 / §6c). Consumes the Wave-3
# ``trace_requirements`` producer; derives the line-1 ``Status`` enum.
# ---------------------------------------------------------------------------


_HUMAN_REQUIREMENTS_MD = textwrap.dedent(
    """\
    # Requirements (`artifact: human-requirements`)

    ## Requirements

    ### REQ-INPUT-01: Ratified requirements are append-only
    - **Acceptance:** `tests/test_human_input_immutability.py` PASSES.
    - **Lifecycle:** RATIFIED 2026-06-03
    - **Status:** Pending

    ### REQ-OUT-01: Digest token budget enforced
    - **Acceptance:** `python -m devolaflow.agent_workspace.lint --human` flags it.
    - **Lifecycle:** DRAFT
    - **Status:** Blocked

    ## Traceability
    | REQ-ID | Acceptance criterion | Cycle | Status |
    |---|---|---|---|
    | REQ-INPUT-01 | append-only lint passes | v14.1.0 | Satisfied |
    | REQ-OUT-01 | digest budget enforced | v14.1.0 | Blocked |
    | **Unmapped** | — | — | **0** ✓ |

    **Version**: 1.0.0 | **Last Amended**: 2026-06-03
    """
)

_ALL_MET_REQUIREMENTS_MD = textwrap.dedent(
    """\
    # Requirements

    ## Requirements

    ### REQ-INPUT-01: Append-only
    - **Acceptance:** `tests/test_x.py` PASSES.
    - **Lifecycle:** RATIFIED 2026-06-03
    - **Status:** Satisfied

    ## Traceability
    | REQ-ID | Acceptance criterion | Cycle | Status |
    |---|---|---|---|
    | REQ-INPUT-01 | append-only | v14.1.0 | Satisfied |

    **Version**: 1.0.0 | **Last Amended**: 2026-06-03
    """
)


def _write_human_requirements(root: Path, body: str = _HUMAN_REQUIREMENTS_MD) -> Path:
    """Write a sample human ``requirements.md`` under ``root`` and return its path."""
    path = root / "requirements.md"
    path.write_text(body, encoding="utf-8")
    return path


class TestHumanReport:
    def test_renders_all_required_sections(self, tmp_path: Path):
        """All §4a sections (status line + verdict + evidence + findings + next) appear."""
        req = _write_human_requirements(tmp_path)
        text = render_human_report(
            "v14.1.0",
            repo_root=tmp_path,
            requirements_path=req,
            findings=[{"severity": "minor", "description": "naming nit"}],
            now=PINNED_NOW,
        )
        assert text.startswith("# Convergence Report — v14.1.0")
        for heading in (
            "> **Status:**",
            "## Verdict",
            "## Requirement evidence",
            "## Blocking findings",
            "## Advisory findings",
            "## Next step",
        ):
            assert heading in text, f"missing section {heading!r}"

    def test_status_passed_all_met_no_blockers(self, tmp_path: Path):
        """All REQ met + no blocking findings → ``passed``."""
        req = _write_human_requirements(tmp_path, _ALL_MET_REQUIREMENTS_MD)
        text = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        assert "> **Status:** passed" in text

    def test_status_gaps_found_unmet_no_blockers(self, tmp_path: Path):
        """≥1 unmet/partial REQ + no blocking findings → ``gaps_found``."""
        req = _write_human_requirements(tmp_path)  # REQ-OUT-01 Blocked → unmet
        text = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        assert "> **Status:** gaps_found" in text

    def test_status_human_needed_when_blocking(self, tmp_path: Path):
        """≥1 blocking (blocker/critical) finding → ``human_needed`` + action rendered."""
        req = _write_human_requirements(tmp_path, _ALL_MET_REQUIREMENTS_MD)
        text = render_human_report(
            "v14.1.0",
            repo_root=tmp_path,
            requirements_path=req,
            findings=[
                {"severity": "blocker", "description": "coverage < 80%", "suggestion": "add tests"}
            ],
            now=PINNED_NOW,
        )
        assert "> **Status:** human_needed" in text
        assert "- coverage < 80% → add tests" in text

    def test_consumes_trace_requirements_verbatim(self, tmp_path: Path):
        """Per-REQ rows come from ``trace_requirements`` with verbatim evidence (C-3)."""
        req = _write_human_requirements(tmp_path)
        text = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        assert "| REQ-INPUT-01 | append-only lint passes | met |" in text
        assert "| REQ-OUT-01 | digest budget enforced | unmet |" in text
        assert "tests/test_human_input_immutability.py" in text

    def test_stagnation_forces_human_needed(self, tmp_path: Path):
        """``stagnation=True`` → ``human_needed`` even when all REQ met + no blockers (§4a)."""
        req = _write_human_requirements(tmp_path, _ALL_MET_REQUIREMENTS_MD)
        text = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, stagnation=True, now=PINNED_NOW
        )
        assert "> **Status:** human_needed" in text

    def test_criterion_column_rendered(self, tmp_path: Path):
        """The §4a 4-column evidence table includes the Acceptance-criterion column."""
        req = _write_human_requirements(tmp_path)
        text = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        assert "| REQ-ID | Acceptance criterion | Result | Evidence |" in text
        assert "| REQ-INPUT-01 | append-only lint passes | met |" in text

    def test_test_results_join_renders_outcome_evidence(self, tmp_path: Path):
        """A threaded ``test_results`` map surfaces verbatim PASS/FAIL evidence (§6c)."""
        from devolaflow.agent_workspace import TestOutcome

        req = _write_human_requirements(tmp_path)
        tr = {
            "tests/test_human_input_immutability.py::test_x": TestOutcome(
                "tests/test_human_input_immutability.py::test_x", "passed", "abc1234"
            )
        }
        # REQ-INPUT-01's Acceptance names a bare file (no ::node), so the join does
        # not apply to it; this asserts threading is wired without error and the
        # matrix derivation still holds for non-node REQs.
        text = render_human_report(
            "v14.1.0",
            repo_root=tmp_path,
            requirements_path=req,
            test_results=tr,
            now=PINNED_NOW,
        )
        assert "| REQ-INPUT-01 | append-only lint passes | met |" in text

    def test_findings_severity_split(self, tmp_path: Path):
        """blocker/critical → Blocking; major/minor/info → Advisory."""
        req = _write_human_requirements(tmp_path, _ALL_MET_REQUIREMENTS_MD)
        text = render_human_report(
            "v14.1.0",
            repo_root=tmp_path,
            requirements_path=req,
            findings=[
                {"severity": "critical", "description": "crit issue", "suggestion": "fix"},
                {"severity": "major", "description": "maj note"},
                {"severity": "info", "description": "info note"},
            ],
            now=PINNED_NOW,
        )
        assert "- crit issue → fix" in text
        assert "- maj note (advisory)" in text
        assert "- info note (advisory)" in text
        assert "> **Status:** human_needed" in text  # critical is blocking

    def test_accepts_finding_objects(self, tmp_path: Path):
        """Findings may be gate ``Finding`` objects (attribute access), not just dicts."""
        from devolaflow.gate.models import Finding

        req = _write_human_requirements(tmp_path, _ALL_MET_REQUIREMENTS_MD)
        finding = Finding(
            finding_id="F1",
            severity="blocker",
            category="test_quality",
            location="tests/",
            description="obj blocker",
            suggestion="do it",
        )
        text = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, findings=[finding], now=PINNED_NOW
        )
        assert "- obj blocker → do it" in text
        assert "> **Status:** human_needed" in text

    def test_unknown_severity_routed_to_advisory_not_dropped(self, tmp_path: Path):
        """A malformed severity is surfaced as advisory (S-5: never silently dropped)."""
        req = _write_human_requirements(tmp_path, _ALL_MET_REQUIREMENTS_MD)
        text = render_human_report(
            "v14.1.0",
            repo_root=tmp_path,
            requirements_path=req,
            findings=[{"severity": "weird", "description": "ODDBALL"}],
            now=PINNED_NOW,
        )
        assert "- ODDBALL (advisory)" in text
        assert "> **Status:** passed" in text  # not blocking → does not escalate

    def test_idempotent_under_pinned_now(self, tmp_path: Path):
        """Two renders with a pinned clock are byte-identical (AC-5)."""
        req = _write_human_requirements(tmp_path)
        findings = [{"severity": "blocker", "description": "b", "suggestion": "s"}]
        first = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, findings=findings, now=PINNED_NOW
        )
        second = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, findings=findings, now=PINNED_NOW
        )
        assert first == second

    def test_missing_requirements_path_raises(self, tmp_path: Path):
        """A supplied-but-absent requirements path is loud (S-5), not a silent empty trace."""
        with pytest.raises(FileNotFoundError):
            render_human_report(
                "v14.1.0",
                repo_root=tmp_path,
                requirements_path=tmp_path / "nope.md",
                now=PINNED_NOW,
            )

    def test_no_requirements_no_findings_is_passed(self, tmp_path: Path):
        """No requirements path + no findings → vacuously ``passed``."""
        text = render_human_report("v14.1.0", repo_root=tmp_path, now=PINNED_NOW)
        assert "> **Status:** passed" in text

    def test_accepts_precomputed_trace_map(self, tmp_path: Path):
        """A pre-computed ``trace`` map is consumed directly (design §6c).

        Passing the ``trace_requirements`` output as the ``trace`` arg yields a
        report byte-identical to passing the same file via ``requirements_path``
        — proving the render "consumes the requirements_trace map".
        """
        from devolaflow.agent_workspace import trace_requirements

        req = _write_human_requirements(tmp_path)
        via_path = render_human_report(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        trace_map = trace_requirements(req)
        via_map = render_human_report("v14.1.0", trace_map, repo_root=tmp_path, now=PINNED_NOW)
        assert via_map == via_path
        assert "| REQ-INPUT-01 | append-only lint passes | met |" in via_map

    def test_supplied_trace_wins_over_requirements_path(self, tmp_path: Path):
        """A supplied ``trace`` map wins; ``requirements_path`` is ignored (not read)."""
        from devolaflow.agent_workspace import RequirementTraceResult

        trace_map = {
            "REQ-X-01": RequirementTraceResult(
                "REQ-X-01", "met", "from the map verbatim", criterion="crit verbatim"
            ),
        }
        text = render_human_report(
            "v14.1.0",
            trace_map,
            repo_root=tmp_path,
            requirements_path=tmp_path / "absent-never-read.md",
            now=PINNED_NOW,
        )
        assert "| REQ-X-01 | crit verbatim | met | from the map verbatim |" in text

    def test_non_mapping_trace_raises(self, tmp_path: Path):
        """A non-mapping ``trace`` is rejected loudly (S-5: no silent failure)."""
        with pytest.raises(TypeError):
            render_human_report(
                "v14.1.0", ["not", "a", "mapping"], repo_root=tmp_path, now=PINNED_NOW
            )


class TestHumanDigest:
    def test_renders_sections_deltas_and_rollup(self, tmp_path: Path):
        """Digest carries §4b sections + this-cycle REQ deltas + ONE rollup line."""
        req = _write_human_requirements(tmp_path)
        text = render_human_digest(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        assert text.startswith("# DevolaFlow Human Digest")
        for heading in (
            "## Where we are",
            "## Open asks for the human",
            "## Requirement coverage",
            "## Latest convergence",
        ):
            assert heading in text, f"missing section {heading!r}"
        assert "- REQ-INPUT-01: met" in text
        assert "rollup: 2 total · 1 satisfied · 1 blocked" in text
        assert "output/convergence/v14.1.0-convergence.md" in text

    def test_open_asks_blocking_only(self, tmp_path: Path):
        """ "Open asks" surfaces BLOCKING findings only — advisory stays in the report."""
        req = _write_human_requirements(tmp_path)
        text = render_human_digest(
            "v14.1.0",
            repo_root=tmp_path,
            requirements_path=req,
            findings=[
                {"severity": "blocker", "description": "BLOCK_ME", "suggestion": "fix"},
                {"severity": "minor", "description": "ADVISE_ME"},
            ],
            now=PINNED_NOW,
        )
        assert "- BLOCK_ME" in text
        assert "ADVISE_ME" not in text

    def test_idempotent_under_pinned_now(self, tmp_path: Path):
        req = _write_human_requirements(tmp_path)
        first = render_human_digest(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        second = render_human_digest(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        assert first == second

    def test_deltas_filtered_to_this_cycle_rollup_counts_all(self, tmp_path: Path):
        """§4b/F-3: digest lists only THIS-cycle REQ deltas; rollup counts the full set."""
        mixed = textwrap.dedent(
            """\
            # Requirements

            ## Requirements

            ### REQ-OLD-01: prior cycle
            - **Acceptance:** `tests/test_old.py` PASSES.
            - **Status:** Satisfied

            ### REQ-NEW-01: this cycle
            - **Acceptance:** `tests/test_new.py` PASSES.
            - **Status:** Pending

            ## Traceability
            | REQ-ID | Acceptance criterion | Cycle | Status |
            |---|---|---|---|
            | REQ-OLD-01 | prior | v14.0.0 | Satisfied |
            | REQ-NEW-01 | current | v14.1.0 | Pending |
            """
        )
        req = _write_human_requirements(tmp_path, mixed)
        text = render_human_digest(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, now=PINNED_NOW
        )
        # Only the this-cycle REQ delta is listed …
        assert "- REQ-NEW-01:" in text
        assert "REQ-OLD-01" not in text
        # … but the rollup still counts the FULL durable set (2 total, 1 satisfied).
        assert "rollup: 2 total · 1 satisfied · 0 blocked" in text

    def test_stagnation_forces_human_needed(self, tmp_path: Path):
        """``stagnation=True`` → ``human_needed`` even with no blocking findings (W-8/SI-9)."""
        req = _write_human_requirements(tmp_path, _ALL_MET_REQUIREMENTS_MD)
        text = render_human_digest(
            "v14.1.0", repo_root=tmp_path, requirements_path=req, stagnation=True, now=PINNED_NOW
        )
        assert "human_needed" in text


class TestRegenerateAllHuman:
    def test_human_key_none_by_default(self, workspace: Path):
        """Without ``human_version`` the ``human`` key is ``None`` (opt-in flavour)."""
        _scaffold_rules(workspace / ".rules")
        result = regenerate_all(repo_root=workspace, now=PINNED_NOW)
        assert result["human"] is None
        for key in ("workspace", "memory", "rules"):
            assert isinstance(result[key], Path)

    def test_human_version_writes_both_artifacts(self, workspace: Path):
        """With ``human_version`` → convergence report + digest written at canonical paths."""
        _scaffold_rules(workspace / ".rules")
        req = _write_human_requirements(workspace)
        result = regenerate_all(
            repo_root=workspace,
            now=PINNED_NOW,
            human_version="v14.1.0",
            human_requirements_path=req,
            human_findings=[{"severity": "blocker", "description": "b", "suggestion": "s"}],
        )
        human = result["human"]
        assert isinstance(human, dict)
        conv = workspace / ".local" / "human" / "output" / "convergence" / "v14.1.0-convergence.md"
        digest = workspace / ".local" / "human" / "output" / "DIGEST.md"
        assert human["convergence"] == conv
        assert human["digest"] == digest
        assert conv.exists()
        assert digest.exists()
        assert "human_needed" in digest.read_text(encoding="utf-8")


class TestHumanReporterCli:
    def test_cli_human_writes_files(self, workspace: Path):
        """`reporter --human <ver> --requirements <req>` writes convergence + digest."""
        req = _write_human_requirements(workspace)
        rc = reporter_main(
            ["--human", "v14.1.0", "--requirements", str(req), "--repo-root", str(workspace)]
        )
        assert rc == 0
        assert (
            workspace / ".local" / "human" / "output" / "convergence" / "v14.1.0-convergence.md"
        ).exists()
        assert (workspace / ".local" / "human" / "output" / "DIGEST.md").exists()

    def test_cli_human_print_to_stdout(self, capsys, workspace: Path):
        """`--human ... --print` writes the convergence report to stdout, not disk."""
        req = _write_human_requirements(workspace)
        rc = reporter_main(
            [
                "--human",
                "v14.1.0",
                "--requirements",
                str(req),
                "--repo-root",
                str(workspace),
                "--print",
            ]
        )
        assert rc == 0
        assert "Convergence Report — v14.1.0" in capsys.readouterr().out
        assert not (workspace / ".local" / "human" / "output" / "DIGEST.md").exists()


class TestDigestBudgetBlocking:
    """REQ-OUT-01 — the digest C-9 budget is BLOCKING since v14.2.0.

    Per the v14.0.0 design telegraph (§8b: "REQ-OUT-01 lint is advisory this
    cycle; promote to blocking in v14.2.0"): the v14.1.0 state was advisory —
    ``lint_human`` flagged an over-budget digest only when separately
    invoked, while the emission paths silently wrote it. Both emission paths
    (``regenerate_all`` + the ``--human`` CLI) now refuse a hard-ceiling
    digest via ``HumanBudgetExceededError``. The soft tier stays advisory
    (WARN log + write proceeds — the documented C-9 escape hatch); zero new
    env flags (W-20 reuse-first).
    """

    def test_regenerate_all_over_hard_digest_raises_and_writes_nothing(self, workspace: Path):
        """Hard-ceiling digest → ``HumanBudgetExceededError``; no human OUTPUT written."""
        _scaffold_rules(workspace / ".rules")
        req = _write_human_requirements(workspace)
        # One blocker whose verbatim "Open asks" line alone exceeds the
        # 1000-token hard ceiling (5000 chars ≈ 1250 tokens).
        findings = [{"severity": "blocker", "description": "x" * 5000, "suggestion": "trim"}]
        with pytest.raises(HumanBudgetExceededError) as excinfo:
            regenerate_all(
                repo_root=workspace,
                now=PINNED_NOW,
                human_version="v14.2.0",
                human_requirements_path=req,
                human_findings=findings,
            )
        assert "REQ-OUT-01" in str(excinfo.value)
        assert excinfo.value.violation.severity == "FAIL"
        assert excinfo.value.violation.filename == "output/DIGEST.md"
        # Neither human OUTPUT artifact was written (no partial pair).
        output = workspace / ".local" / "human" / "output"
        assert not (output / "DIGEST.md").exists()
        assert not (output / "convergence" / "v14.2.0-convergence.md").exists()

    def test_regenerate_all_over_soft_digest_warns_but_writes(
        self, workspace: Path, caplog: pytest.LogCaptureFixture
    ):
        """Soft-tier overrun stays advisory: WARN logged, digest still emitted."""
        _scaffold_rules(workspace / ".rules")
        req = _write_human_requirements(workspace)
        # ~3000 chars ≈ 750 tokens — over soft (600), under hard (1000).
        findings = [{"severity": "blocker", "description": "y" * 3000, "suggestion": "trim"}]
        with caplog.at_level(logging.WARNING, logger="devolaflow.agent_workspace.reporter"):
            result = regenerate_all(
                repo_root=workspace,
                now=PINNED_NOW,
                human_version="v14.2.0",
                human_requirements_path=req,
                human_findings=findings,
            )
        assert result["human"] is not None
        assert (workspace / ".local" / "human" / "output" / "DIGEST.md").exists()
        assert "REQ-OUT-01" in caplog.text

    def test_cli_human_over_hard_digest_returns_one(self, workspace: Path, capsys):
        """The ``--human`` CLI exits 1 on a hard-ceiling digest; nothing written."""
        # 300 matrix-only REQ rows → ~300 digest delta lines ≈ 1500+ tokens.
        rows = "\n".join(f"| REQ-CLI-{i:03d} | c{i} | | Blocked |" for i in range(300))
        body = (
            "# Requirements\n\n## Traceability\n"
            "| REQ-ID | Acceptance criterion | Cycle | Status |\n"
            "|---|---|---|---|\n" + rows + "\n"
        )
        req = _write_human_requirements(workspace, body)
        rc = reporter_main(
            ["--human", "v14.2.0", "--requirements", str(req), "--repo-root", str(workspace)]
        )
        assert rc == 1
        assert "REQ-OUT-01" in capsys.readouterr().err
        output = workspace / ".local" / "human" / "output"
        assert not (output / "DIGEST.md").exists()
        assert not (output / "convergence" / "v14.2.0-convergence.md").exists()


class TestReporterByteStability:
    """v14.1.0 R3 — dedicated 4-flavour AC-5 byte-stability regression.

    The §4 OUTPUT renderers (and the four agent-facing flavours) MUST be
    byte-identical across two invocations under a pinned ``now``. This pins
    that idempotency guarantee for ALL renderers in one place so a future
    refactor that accidentally injects an unpinned timestamp / set-ordering
    is caught immediately.
    """

    def test_all_flavours_byte_stable_under_pinned_now(self, workspace: Path):
        """workspace + memory + rules + human report + human digest all byte-stable."""
        _scaffold_rules(workspace / ".rules")
        req = _write_human_requirements(workspace)
        findings = [{"severity": "blocker", "description": "b", "suggestion": "s"}]

        renderers = {
            "workspace": lambda: render_workspace_report(repo_root=workspace, now=PINNED_NOW),
            "memory": lambda: render_memory_report(repo_root=workspace, now=PINNED_NOW),
            "rules": lambda: render_rules_report(repo_root=workspace, now=PINNED_NOW),
            "human_report": lambda: render_human_report(
                "v14.1.0",
                repo_root=workspace,
                requirements_path=req,
                findings=findings,
                now=PINNED_NOW,
            ),
            "human_digest": lambda: render_human_digest(
                "v14.1.0",
                repo_root=workspace,
                requirements_path=req,
                findings=findings,
                now=PINNED_NOW,
            ),
        }
        for name, render in renderers.items():
            first = render()
            second = render()
            assert first == second, f"{name} renderer is not byte-stable under a pinned now"

    def test_regenerate_all_with_human_is_byte_stable(self, workspace: Path):
        """``regenerate_all`` (incl. the human flavour) writes byte-identical files twice."""
        _scaffold_rules(workspace / ".rules")
        req = _write_human_requirements(workspace)

        def _run() -> dict[str, str]:
            regenerate_all(
                repo_root=workspace,
                now=PINNED_NOW,
                human_version="v14.1.0",
                human_requirements_path=req,
            )
            conv = (
                workspace / ".local" / "human" / "output" / "convergence" / "v14.1.0-convergence.md"
            )
            digest = workspace / ".local" / "human" / "output" / "DIGEST.md"
            return {
                "convergence": conv.read_text(encoding="utf-8"),
                "digest": digest.read_text(encoding="utf-8"),
            }

        assert _run() == _run()
