"""Current-cycle ghost audit for the v18 F-1 role contracts."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_v18_f1_roles_are_registered_across_profile_and_template_surfaces(
    project_root: Path,
) -> None:
    """The preflight and harness-build roles remain discoverable and bounded."""
    agent_root = project_root / "workflow-system" / "agent"
    profiles = yaml.safe_load((agent_root / "context_profiles.yaml").read_text(encoding="utf-8"))
    for task_type, budget in (("preflight", 4000), ("harness_build", 5000)):
        profile = profiles["profiles"][task_type]
        assert profile["token_budget"] == budget
        assert profile["timeout_class"] in {"review", "impl"}

    roles = (agent_root / "references" / "team-roles.md").read_text(encoding="utf-8")
    assert "preflight" in roles
    assert "harness_build" in roles

    template = yaml.safe_load(
        (agent_root / "templates" / "builtin" / "change-driven.yaml").read_text(encoding="utf-8")
    )
    stages = {stage["id"]: stage for stage in template["stages"]}
    assert stages["preflight"]["team"] == "preflight"
    assert stages["round"]["config"]["blocker_remediation_task_type"] == "harness_build"
