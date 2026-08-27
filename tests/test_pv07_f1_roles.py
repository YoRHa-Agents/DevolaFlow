"""PV-7 F-1 contracts for the preflight and harness_build L2 roles."""

from __future__ import annotations

from pathlib import Path

import yaml

from devolaflow.task_adaptive_selector import load_profiles, match_profile, select_context
from devolaflow.template_engine.parser import parse_template

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_ROOT = REPO_ROOT / "workflow-system" / "agent"
PROFILES_PATH = AGENT_ROOT / "context_profiles.yaml"


def test_team_roles_declare_f1_boundaries() -> None:
    roles = (AGENT_ROOT / "references" / "team-roles.md").read_text(encoding="utf-8")
    assert (
        "research | design | implement | test | pathfind | review | preflight | harness_build"
        in roles
    )
    assert "| Preflight | Draft configuration and evidence" in roles
    assert "| HarnessBuild | Remediate a Pathfinder blocker" in roles
    assert "authorization_state: NOT_AUTHORIZED" in roles
    assert "Gate semantics, human sign-off, and stop-card decisions remain owned by L0" in roles
    assert "Pathfinder `BLOCKER`" in roles
    assert "harness_build_evidence" in roles


def test_f1_profiles_have_budgets_and_timeout_classes() -> None:
    config = load_profiles(PROFILES_PATH)
    profiles = config["profiles"]
    assert profiles["preflight"]["token_budget"] == 4000
    assert profiles["preflight"]["timeout_class"] == "review"
    assert profiles["harness_build"]["token_budget"] == 5000
    assert profiles["harness_build"]["timeout_class"] == "impl"


def test_f1_role_intent_routes_to_distinct_profiles() -> None:
    config = load_profiles(PROFILES_PATH)
    cases = {
        "preflight": "preflight",
        "draft preflight evidence": "preflight",
        "harness_build": "harness_build",
        "Pathfinder blocker remediation": "harness_build",
    }
    assert {message: match_profile(message, config) for message in cases} == cases


def test_f1_context_selection_respects_role_budgets() -> None:
    for task_type in ("preflight", "harness_build"):
        result = select_context(task_type, profiles_path=PROFILES_PATH)
        assert result["profile_name"] == task_type
        assert result["total_tokens"] <= result["budget"]
        assert result["timeout_seconds"] in {1200, 1800}
        assert result["extra_context"]


def test_f1_seeds_route_intent_and_remediation() -> None:
    change_seed = yaml.safe_load(
        (AGENT_ROOT / "templates" / "seeds" / "change-driven.yaml").read_text(encoding="utf-8")
    )
    harness_seed = yaml.safe_load(
        (AGENT_ROOT / "templates" / "seeds" / "harness-construction.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert {"preflight", "preflight-draft", "harness-build"} <= set(
        change_seed["metadata"]["intent_keywords"]
    )
    assert {"harness_build", "harness-build", "blocker-remediation"} <= set(
        harness_seed["metadata"]["intent_keywords"]
    )
    assert any(
        assertion["key"] == "pathfinder-blockers-remediated"
        for partition in harness_seed["partitions"]
        for assertion in partition["assertions"]
    )


def test_change_driven_template_wires_f1_roles_without_changing_gates() -> None:
    template = parse_template(AGENT_ROOT / "templates" / "builtin" / "change-driven.yaml")
    preflight = template.stage_by_id("preflight")
    round_stage = template.stage_by_id("round")
    assert preflight is not None and preflight.team == "preflight"
    assert preflight.config["scope"] == "drafting_only"
    assert preflight.config["gate_owner"] == "l0_and_human"
    assert round_stage is not None
    assert round_stage.config["blocker_remediation_task_type"] == "harness_build"
    gate = next(item for item in template.gates if item.name == "preflight_gate")
    assert gate.require_human_override is True


def test_execution_protocol_documents_f1_dispatch_wiring() -> None:
    protocol = (AGENT_ROOT / "references" / "execution-protocol.md").read_text(encoding="utf-8")
    assert "TaskDispatch.task.type: preflight" in protocol
    assert "TaskDispatch.task.type: harness_build" in protocol
    assert "preflight_gate` remains an L0 + human decision" in protocol
    assert "canonical_order`" in protocol and "at 17" in protocol


def test_dispatch_order_and_plugin_surfaces_remain_unchanged() -> None:
    dispatch = yaml.safe_load(
        (REPO_ROOT / "schemas" / "lean-dispatch.yaml").read_text(encoding="utf-8")
    )
    order = dispatch["layout_invariant"]["canonical_order"]
    assert len(order) == 17
    assert not any(name in {"preflight", "harness_build"} for name in dispatch.get("plugins", {}))
