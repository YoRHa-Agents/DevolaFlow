"""Ghost audit — consolidated W-18 feature stanza for the v16.0 M1 slice."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.ghost._helpers import _load_yaml


def test_v16_0_0_m1_checklist_artifact_contract_registered(
    project_root: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """W-18 v16.0.0 M1: checklist schemas, runtime, lint, and budgets are wired."""
    from devolaflow.agent_workspace import (
        ARTIFACT_FILES_V16,
        ChangeLayout,
        LegacyChangeLayoutError,
        detect_change_layout,
        hydrate_change_context,
        lint_change,
    )
    from devolaflow.agent_workspace.lint import (
        CHECKLIST_ARTIFACT_BUDGETS,
        EVIDENCE_DIRECTORY_MAX_BYTES,
        EVIDENCE_FILE_MAX_BYTES,
    )
    from devolaflow.agent_workspace.memory_bridge import _CHECKLIST_HYDRATE_BUDGETS
    from devolaflow.skills.slash_commands import run_propose

    schema_dir = project_root / "schemas" / "agent-workspace"
    index = _load_yaml(schema_dir / "__init__.yaml")
    index_entries = {entry["id"]: entry for entry in index["schemas"]}
    new_schema_contracts = {
        "change-checklist": (
            "change-checklist.yaml",
            (1200, 2400),
            {
                "parent",
                "schema_version",
                "total_items",
                "checked",
                "priority_dist",
                "reverted_open",
            },
        ),
        "change-stage": (
            "change-stage.yaml",
            (400, 800),
            {"parent", "schema_version", "current_round", "max_rounds", "capacity_per_round"},
        ),
        "change-preflight": (
            "change-preflight.yaml",
            (600, 1200),
            {
                "parent",
                "schema_version",
                "authorized_at",
                "snapshot_round",
                "config_inherited_from",
                "project_config_hash",
            },
        ),
    }
    for schema_id, (filename, budget, required_fields) in new_schema_contracts.items():
        entry = index_entries[schema_id]
        assert entry["file"] == filename
        assert (entry["token_budget"]["soft"], entry["token_budget"]["hard"]) == budget
        schema = _load_yaml(schema_dir / filename)
        assert schema["schema_name"] == schema_id
        assert schema["schema_version"] == 1
        assert (schema["token_budget"]["soft"], schema["token_budget"]["hard"]) == budget
        assert set(schema["frontmatter"]["required"]) == required_fields

    goal_schema = _load_yaml(schema_dir / "change-goal.yaml")
    status_schema = _load_yaml(schema_dir / "change-status.yaml")
    assert goal_schema["schema_version"] == 2
    assert "goals_count" in goal_schema["frontmatter"]["required"]
    assert goal_schema["compatibility"]["schema_version_1"]["history_rewrite"] == "forbidden"
    assert status_schema["schema_version"] == 2
    assert status_schema["fields"]["owner_layer"]["enum"] == ["L0", "L1", "L2"]
    assert status_schema["instance_top_level_required"][-4:] == [
        "checklist_checked",
        "checklist_total",
        "current_round",
        "next_blockers",
    ]
    assert status_schema["compatibility"]["schema_version_1"]["owner_layer_mapping"] == {
        "L0": "L0",
        "L1": "L0",
        "L2": "L1",
        "L3": "L2",
    }
    # v17.0.0 removal (G17-A2): the dual-track schemas hit their declared
    # removal_target — files deleted, registry entries dropped. Names are
    # assembled from stems so repo-wide greps for the removed ids stay empty.
    for legacy_schema_name in (f"change-{stem}" for stem in ("tasks", "acceptance")):
        assert not (schema_dir / f"{legacy_schema_name}.yaml").exists()
        assert legacy_schema_name not in index_entries

    assert [layout.value for layout in ChangeLayout] == [
        "CHECKLIST",
        "INVALID_MIXED",
    ]
    assert ARTIFACT_FILES_V16 == (
        "goal.md",
        "checklist.md",
        "stage.md",
        "preflight.md",
        "spec.md",
        "STATUS.yaml",
        "owned_files.txt",
        "learnings.jsonl",
    )
    layout_cases = (
        ((), ChangeLayout.CHECKLIST),
        (("checklist.md",), ChangeLayout.CHECKLIST),
        (("checklist.md", "acceptance.md"), ChangeLayout.INVALID_MIXED),
    )
    for case_number, (markers, expected_layout) in enumerate(layout_cases):
        folder = tmp_path / f"layout-{case_number}"
        folder.mkdir()
        for marker in markers:
            (folder / marker).write_text("", encoding="utf-8")
        assert detect_change_layout(folder) is expected_layout
    legacy_folder = tmp_path / "layout-legacy"
    legacy_folder.mkdir()
    (legacy_folder / "tasks.md").write_text("", encoding="utf-8")
    with pytest.raises(LegacyChangeLayoutError, match=r"removed in v17\.0\.0"):
        detect_change_layout(legacy_folder)

    monkeypatch.delenv("DEVOLAFLOW_AGENT_WORKSPACE", raising=False)
    scaffold = run_propose("V16 Ghost Audit", tmp_path)
    assert detect_change_layout(scaffold) is ChangeLayout.CHECKLIST
    for artifact in (*ARTIFACT_FILES_V16[:-1], "README.md"):
        assert (scaffold / artifact).is_file(), f"v16 scaffold missing {artifact}"
    assert (scaffold / "evidence").is_dir()
    for retired_artifact in ("tasks.md", "acceptance.md"):
        assert not (scaffold / retired_artifact).exists()

    hydrated = hydrate_change_context("v16-ghost-audit", active_root=scaffold.parent)
    assert set(hydrated) == {
        "goal",
        "checklist",
        "stage",
        "preflight",
        "spec",
        "status",
        "owned_files",
        "learnings",
        "evidence",
    }
    assert hydrated["status"]["schema_version"] == 2
    assert hydrated["evidence"] == {}
    report = lint_change("v16-ghost-audit", repo_root=tmp_path)
    assert report.exit_code == 0, [
        violation.render(report.change_id) for violation in report.violations
    ]
    assert not report.hard_failures

    # The seven v16 rows carried verbatim by the C-9 rules table
    # (.rules/conventions.mdc).
    c9_rules_table_rows = {
        "goal.md": (200, 400),
        "checklist.md": (1200, 2400),
        "stage.md": (400, 800),
        "preflight.md": (600, 1200),
        "spec.md": (1500, 3000),
        "STATUS.yaml": (150, 300),
        "owned_files.txt": (50, 100),
    }
    expected_c9_budgets = {
        **c9_rules_table_rows,
        # OPTIONAL harness pre-analysis artifact (harness-construction);
        # not part of the v16 C-9 rules table.
        "harness_preflight.md": (800, 1600),
        # Agent onboarding router (v17.2.0 change-entrance design);
        # not part of the v16 C-9 rules table.
        "entrance.md": (400, 800),
        # Read-only look-ahead report (v17.3.0 Pathfinder design).
        "pathfinder_report.md": (800, 1600),
    }
    assert expected_c9_budgets == CHECKLIST_ARTIFACT_BUDGETS
    assert _CHECKLIST_HYDRATE_BUDGETS == {
        "goal": 400,
        "checklist": 2400,
        "stage": 800,
        "preflight": 1200,
        "spec": 3000,
        "status": 300,
        "owned_files": 100,
    }
    assert EVIDENCE_FILE_MAX_BYTES == 10 * 1024
    assert EVIDENCE_DIRECTORY_MAX_BYTES == 50 * 1024
    c9_source = (project_root / ".rules" / "conventions.mdc").read_text(encoding="utf-8")
    for filename, (soft, hard) in c9_rules_table_rows.items():
        assert f"| {filename} | {soft} | {hard} |" in c9_source
    assert "| evidence/ | No token limit | ≤ 10 KB/file; ≤ 50 KB/directory |" in c9_source

    companion_suites = {
        "tests/test_agent_workspace_schemas.py": "test_index_token_budgets_match_per_schema_files",
        "tests/test_agent_workspace_change_layout.py": "test_detect_change_layout",
        "tests/test_agent_workspace.py": "class TestLintChange",
        "tests/test_memory_bridge.py": "class TestHydrateChangeContext",
        "tests/test_slash_commands.py": "test_propose_creates_change_folder",
    }
    for relative_path, coverage_anchor in companion_suites.items():
        test_source = (project_root / relative_path).read_text(encoding="utf-8")
        assert coverage_anchor in test_source, (
            f"focused companion coverage missing {coverage_anchor!r} from {relative_path}"
        )


def test_v16_0_0_m2_round_dispatch_context_registered(project_root: Path) -> None:
    """W-18 v16.0.0 M2: round selection is emitted through one public NEST helper."""
    import devolaflow.agent_workspace as agent_workspace
    import devolaflow.harness as harness

    schema = _load_yaml(project_root / "schemas" / "lean-dispatch.yaml")
    fields = schema["lean_format_spec"]["change_context"]["fields"]
    checklist_items = fields["checklist_items"]
    round_context = fields["round_context"]

    assert checklist_items["min_items"] == 1
    assert checklist_items["max_items"] == 5
    assert checklist_items["required_with"] == "round_context"
    assert checklist_items["per_entry"]["assert"]["verbatim"] is True
    assert checklist_items["per_entry"]["verify"]["verbatim"] is True
    assert checklist_items["per_entry"]["priority"]["enum"] == ["P0", "P1", "P2"]
    assert round_context["required_with"] == "checklist_items"
    assert round_context["fields"]["round_n"]["minimum"] == 1
    assert round_context["fields"]["reverted_ids"]["unique_items"] is True
    assert round_context["fields"]["reverted_ids"]["subset_of"] == "checklist_items[*].id"
    assert schema["layout_invariant"]["version"] == 6
    assert len(schema["layout_invariant"]["canonical_order"]) == 17

    assert hasattr(agent_workspace, "populate_round_change_context")
    assert "populate_round_change_context" in agent_workspace.__all__
    result = agent_workspace.populate_round_change_context(
        {"change_context": {"change_id": "ghost-round-dispatch"}},
        SimpleNamespace(
            items=(
                SimpleNamespace(
                    item_id="C-G1.1",
                    assertion='Preserve "verbatim" assertion',
                    verify="python -m pytest tests/test_x.py -q",
                ),
            )
        ),
        SimpleNamespace(
            selected=(
                SimpleNamespace(
                    item_id="C-G1.1",
                    priority="P0",
                    reverted=True,
                ),
            )
        ),
        round_n=2,
    )
    assert result["change_context"]["checklist_items"][0] == {
        "id": "C-G1.1",
        "assert": 'Preserve "verbatim" assertion',
        "verify": "python -m pytest tests/test_x.py -q",
        "priority": "P0",
    }
    assert result["change_context"]["round_context"] == {
        "round_n": 2,
        "reverted_ids": ["C-G1.1"],
    }

    focused_tests = (project_root / "tests" / "test_agent_workspace_round_dispatch.py").read_text(
        encoding="utf-8"
    )
    assert "test_populate_round_change_context_emits_selected_items_verbatim" in focused_tests

    telemetry_exports = {
        "build_dispatch_record",
        "append_harness_record",
        "record_dispatch_telemetry",
    }
    assert telemetry_exports <= set(harness.__all__)
    assert all(callable(getattr(harness, name)) for name in telemetry_exports)
    assert harness.HARNESS_SEGMENT_MAX_BYTES == 64 * 1024
    assert harness.LAYER_TOKEN_BUDGETS == {"L0": 5_000, "L1": 5_000, "L2": 8_000}

    lifecycle_source = (
        project_root / "src" / "devolaflow" / "lifecycle" / "__init__.py"
    ).read_text(encoding="utf-8")
    default_anchor = "_set_default_hook(_POST_DISPATCH_EVENT, post_dispatch)"
    telemetry_anchor = "register_hook(_POST_DISPATCH_EVENT, record_dispatch_telemetry)"
    assert lifecycle_source.index(default_anchor) < lifecycle_source.index(telemetry_anchor)

    telemetry_tests = (project_root / "tests" / "test_harness_telemetry.py").read_text(
        encoding="utf-8"
    )
    for coverage_anchor in (
        "test_build_dispatch_record_uses_exact_schema_and_stable_yaml",
        "test_append_harness_record_is_compact_and_rotates_without_rewrite",
        "test_warm_handler_mean_under_five_ms_and_payload_unchanged",
    ):
        assert coverage_anchor in telemetry_tests

    import devolaflow.agent_workspace.checkpoint as checkpoint
    import devolaflow.agent_workspace.preflight as preflight
    import devolaflow.agent_workspace.preflight_runtime as preflight_runtime
    import devolaflow.agent_workspace.resume as resume
    import devolaflow.lifecycle.preflight_authorization as preflight_guard

    m3_symbols = {
        checkpoint: (
            "load_checkpoint",
            "write_checkpoint",
        ),
        preflight: (
            "discover_preflight_baseline",
            "draft_preflight_section0",
            "sign_preflight",
            "invalidate_preflight",
        ),
        preflight_runtime: (
            "evaluate_permitted_stops",
            "refresh_preflight_snapshot",
        ),
        resume: (
            "ChecklistResumePlan",
            "ResumeDisposition",
            "plan_checklist_resume",
        ),
        preflight_guard: (
            "HBP_CODE",
            "guard_preflight_authorization",
        ),
    }
    for module, symbols in m3_symbols.items():
        for symbol in symbols:
            assert hasattr(module, symbol), (
                f"v16 M3 ghost symbol missing: {module.__name__}.{symbol}"
            )

    resume_tests = (project_root / "tests" / "test_agent_workspace_resume.py").read_text(
        encoding="utf-8"
    )
    for coverage_anchor in (
        "test_mid_round_interruption_resumes_without_rechecking_completed_items",
        "test_between_round_resume_returns_ready_or_complete",
    ):
        assert coverage_anchor in resume_tests

    protocol = (
        project_root / "workflow-system" / "agent" / "references" / "execution-protocol.md"
    ).read_text(encoding="utf-8")
    for contract_anchor in (
        "## 1. Preflight Phase",
        "standalone `pre_decision`",
        "HBP-01",
        "non-skippable",
        "checklist",
    ):
        assert contract_anchor in protocol
