"""Ghost audit for the Pathfinder role surfaces."""

from __future__ import annotations

from pathlib import Path

import yaml

from devolaflow.agent_workspace import lint as workspace_lint
from devolaflow.agent_workspace.lint import CHECKLIST_ARTIFACT_BUDGETS
from devolaflow.skills import classify_pathfind_intent, should_schedule_pathfind


def test_pathfinder_role_surfaces_are_wired(project_root: Path) -> None:
    """W-18: role, reference, seed, profile, schema, and budget agree."""
    reference = project_root / "workflow-system/agent/references/pathfinder.md"
    skill = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    roles = (project_root / "workflow-system/agent/references/team-roles.md").read_text(
        encoding="utf-8"
    )
    manifest = yaml.safe_load(
        (project_root / "workflow-system/agent/manifest.yaml").read_text(encoding="utf-8")
    )
    assert reference.is_file()
    assert "references/pathfinder.md" in skill
    assert (
        "type: research | design | implement | test | pathfind | review | preflight | harness_build"
        in roles
    )
    assert "references/pathfinder.md" in manifest["references"]
    assert classify_pathfind_intent("run Pathfinder look-ahead") == "PATHFIND_REQUESTED"
    assert callable(should_schedule_pathfind)
    assert "should_schedule_pathfind" in skill
    lint_source = (project_root / "src/devolaflow/_workspace_lint/advanced_semantics.py").read_text(
        encoding="utf-8"
    )
    assert workspace_lint.PATHFINDER_REPORT_FILENAME == "pathfinder_report.md"
    assert "_check_pathfinder_report(" in lint_source
    assert "PFR_BLOCKER_SIGNAL" in lint_source

    registry = yaml.safe_load(
        (project_root / "workflow-system/agent/templates/registry.yaml").read_text(encoding="utf-8")
    )
    entry = next(item for item in registry["compositions"] if item["name"] == "pathfinder")
    assert entry["seed"] == "seeds/pathfinder.yaml"
    seed = yaml.safe_load(
        (project_root / "workflow-system/agent/templates/seeds/pathfinder.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert seed["metadata"]["name"] == "pathfinder"
    assert len(seed["partitions"]) == 3

    profiles = yaml.safe_load(
        (project_root / "workflow-system/agent/context_profiles.yaml").read_text(encoding="utf-8")
    )
    profile = profiles["profiles"]["pathfind"]
    assert profile["token_budget"] == 5000
    assert profile["timeout_class"] == "research"
    assert "references/pathfinder.md" in profile["extra_context"]

    schema = yaml.safe_load(
        (project_root / "schemas/agent-workspace/pathfinder-report.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert schema["schema_name"] == "pathfinder-report"
    assert schema["token_budget"]["soft"] == 800
    assert schema["token_budget"]["hard"] == 1600
    assert schema["token_budget"]["units"] == "tokens"
    assert CHECKLIST_ARTIFACT_BUDGETS["pathfinder_report.md"] == (800, 1600)
