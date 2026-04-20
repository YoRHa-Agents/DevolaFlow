"""YAML → WorkflowTemplate parser.

Design ref: design_meta_framework.md §4.1 (schema), §4.2 (CompositionNode)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from devolaflow.template_engine.models import (
    Break,
    Choice,
    CompositionNode,
    GateCriterion,
    GateDef,
    GateOnFail,
    GateRef,
    LoopDef,
    LoopRef,
    Parallel,
    Sequence,
    StageDefinition,
    StageRef,
    TemplateMetadata,
    WorkflowTemplate,
)


class TemplateParseError(Exception):
    """Raised when a template YAML file cannot be parsed."""


def parse_template(yaml_path: Path) -> WorkflowTemplate:
    """Load a YAML template file and construct the dataclass tree."""
    with open(yaml_path) as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise TemplateParseError(f"Template root must be a mapping, got {type(raw).__name__}")
    return _build_template(raw)


def parse_template_string(text: str) -> WorkflowTemplate:
    """Parse a YAML string into a WorkflowTemplate."""
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise TemplateParseError(f"Template root must be a mapping, got {type(raw).__name__}")
    return _build_template(raw)


def _build_template(raw: dict[str, Any]) -> WorkflowTemplate:
    """Construct a WorkflowTemplate from a parsed YAML dict."""
    metadata = _parse_metadata(raw.get("metadata", {}))
    stages = [_parse_stage(s) for s in raw.get("stages", [])]
    comp_raw = raw.get("composition")
    composition = parse_composition(comp_raw) if comp_raw else Sequence(stages=[])
    loops = [_parse_loop(lp) for lp in raw.get("loops", [])]
    gates = [_parse_gate(g) for g in raw.get("gates", [])]

    return WorkflowTemplate(
        schema_version=raw.get("schema_version", "1.0"),
        metadata=metadata,
        stages=stages,
        composition=composition,
        loops=loops,
        gates=gates,
        team_overrides=raw.get("team_overrides", {}) or {},
        environment_modes=raw.get("environment_modes", {}) or {},
        extends=raw.get("extends"),
        overrides=raw.get("overrides"),
        parameters=raw.get("parameters", {}) or {},
    )


def _parse_metadata(raw: dict[str, Any]) -> TemplateMetadata:
    """Extract TemplateMetadata fields from a raw YAML mapping."""
    return TemplateMetadata(
        name=raw.get("name", ""),
        version=raw.get("version", ""),
        display_name=raw.get("display_name", ""),
        description=raw.get("description", ""),
        category=raw.get("category", ""),
        applicable_scenarios=raw.get("applicable_scenarios", []) or [],
        tags=raw.get("tags", []) or [],
        author=raw.get("author"),
        created=str(raw["created"]) if raw.get("created") else None,
        updated=str(raw["updated"]) if raw.get("updated") else None,
    )


def _parse_stage(raw: dict[str, Any]) -> StageDefinition:
    """Extract a StageDefinition from a raw YAML mapping."""
    return StageDefinition(
        id=raw["id"],
        primitive=raw["primitive"],
        alias=raw.get("alias"),
        description=raw.get("description"),
        team=raw.get("team"),
        duration_class=raw.get("duration_class"),
        config=raw.get("config", {}) or {},
        input_mapping=raw.get("input_mapping", {}) or {},
        skip_condition=raw.get("skip_condition"),
        timeout_minutes=raw.get("timeout_minutes"),
    )


def _parse_sequence(node_dict: dict[str, Any]) -> Sequence:
    children = [parse_composition(s) for s in node_dict.get("stages", [])]
    return Sequence(stages=children)


def _parse_parallel(node_dict: dict[str, Any]) -> Parallel:
    children = [parse_composition(s) for s in node_dict.get("stages", [])]
    join = node_dict.get("join", "all")
    n_of_count = None
    if isinstance(join, str) and join.startswith("n_of("):
        n_of_count = int(join[5:-1])
        join = "n_of"
    return Parallel(stages=children, join=join, n_of_count=n_of_count)


def _parse_choice(node_dict: dict[str, Any]) -> Choice:
    return Choice(
        condition=node_dict["condition"],
        if_true=parse_composition(node_dict["if_true"]),
        if_false=parse_composition(node_dict["if_false"]),
    )


def _parse_loop_or_gate_ref(node_dict: dict[str, Any], cls: type) -> CompositionNode:
    ref = node_dict.get("ref") or node_dict.get("name", "")
    return cls(ref=ref)


_COMPOSE_DISPATCH: dict[str, object] = {
    "sequence": _parse_sequence,
    "parallel": _parse_parallel,
    "choice": _parse_choice,
    "loop": lambda nd: _parse_loop_or_gate_ref(nd, LoopRef),
    "gate": lambda nd: _parse_loop_or_gate_ref(nd, GateRef),
}


def parse_composition(node_dict: dict[str, Any] | str) -> CompositionNode:
    """Recursively parse a composition node from its dict representation.

    Handles all 7 CompositionNode variants:
      1. StageRef     — ``{ stage: "id" }``
      2. Sequence     — ``{ compose: "sequence", stages: [...] }``
      3. Parallel     — ``{ compose: "parallel", stages: [...], join: "..." }``
      4. Choice       — ``{ compose: "choice", condition: ..., if_true: ..., if_false: ... }``
      5. LoopRef      — ``{ compose: "loop", ref: "name" }``
      6. GateRef      — ``{ compose: "gate", ref: "name" }``
      7. Break        — ``{ break: true }``
    """
    if isinstance(node_dict, str):
        return StageRef(stage=node_dict)

    if not isinstance(node_dict, dict):
        raise TemplateParseError(
            f"CompositionNode must be a dict or string, got {type(node_dict).__name__}"
        )

    if node_dict.get("break"):
        return Break()

    if "stage" in node_dict:
        return StageRef(stage=node_dict["stage"])

    compose_type = node_dict.get("compose")
    if compose_type is None:
        raise TemplateParseError(f"CompositionNode missing 'compose' or 'stage': {node_dict}")

    handler = _COMPOSE_DISPATCH.get(compose_type)
    if handler is None:
        raise TemplateParseError(f"Unknown compose type: {compose_type}")
    return handler(node_dict)


def _parse_loop(raw: dict[str, Any]) -> LoopDef:
    """Extract a LoopDef from a raw YAML mapping."""
    return LoopDef(
        name=raw["name"],
        body_stages=raw.get("body_stages", []),
        until=raw.get("until", ""),
        max_iterations=raw.get("max_iterations", 0),
        quality_threshold=raw.get("quality_threshold"),
        on_exhaustion=raw.get("on_exhaustion", "escalate"),
        escalation_target=raw.get("escalation_target"),
        escalation_max=raw.get("escalation_max"),
    )


def _parse_gate(raw: dict[str, Any]) -> GateDef:
    """Extract a GateDef from a raw YAML mapping."""
    criteria = [
        GateCriterion(
            field=c["field"],
            operator=c["operator"],
            value=c["value"],
        )
        for c in raw.get("criteria", [])
    ]

    on_fail_raw = raw.get("on_fail", {})
    if isinstance(on_fail_raw, dict) and on_fail_raw:
        on_fail = GateOnFail(
            action=on_fail_raw.get("action", ""),
            target=on_fail_raw.get("target"),
        )
    else:
        on_fail = GateOnFail(action="")

    return GateDef(
        name=raw["name"],
        position=raw.get("position", ""),
        criteria=criteria,
        on_pass=raw.get("on_pass", "next"),
        on_fail=on_fail,
        require_human_override=raw.get("require_human_override", False),
        auto_insert=raw.get("auto_insert", False),
    )
