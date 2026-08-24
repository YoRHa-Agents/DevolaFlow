"""Ghost audit — consolidated W-18 feature stanza for the v16.0 M1 slice."""

from __future__ import annotations

from pathlib import Path

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
    for legacy_schema_name in ("change-tasks", "change-acceptance"):
        legacy = _load_yaml(schema_dir / f"{legacy_schema_name}.yaml")
        index_entry = index_entries[legacy_schema_name]
        for document in (legacy, index_entry):
            assert document["deprecated_since"] == "16.0.0"
            assert document["replacement"] == "change-checklist"
            assert document["removal_target"] == "17.0.0"

    assert [layout.value for layout in ChangeLayout] == [
        "LEGACY",
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
        ((), ChangeLayout.LEGACY),
        (("tasks.md",), ChangeLayout.LEGACY),
        (("checklist.md",), ChangeLayout.CHECKLIST),
        (("checklist.md", "acceptance.md"), ChangeLayout.INVALID_MIXED),
    )
    for case_number, (markers, expected_layout) in enumerate(layout_cases):
        folder = tmp_path / f"layout-{case_number}"
        folder.mkdir()
        for marker in markers:
            (folder / marker).write_text("", encoding="utf-8")
        assert detect_change_layout(folder) is expected_layout

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

    expected_c9_budgets = {
        "goal.md": (200, 400),
        "checklist.md": (1200, 2400),
        "stage.md": (400, 800),
        "preflight.md": (600, 1200),
        "spec.md": (1500, 3000),
        "STATUS.yaml": (150, 300),
        "owned_files.txt": (50, 100),
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
    for filename, (soft, hard) in expected_c9_budgets.items():
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
