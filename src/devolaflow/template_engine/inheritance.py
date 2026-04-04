"""Template inheritance — derivation via ``extends`` + ``overrides``.

Design ref: design_meta_framework.md §5.4

A derived template extends a base template, selectively overriding or
extending specific fields.  The override schema supports:
  - stages.<id>.config   — merge/replace config dict
  - stages.<id>.*        — set scalar fields (skip_condition, etc.)
  - gates.<name>.criteria — replace criteria list
  - environment_modes     — deep-merge
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devolaflow.template_engine.models import WorkflowTemplate


class InheritanceError(Exception):
    """Raised when template inheritance resolution fails."""


def resolve_inheritance(
    template: WorkflowTemplate,
    registry: Any,
) -> WorkflowTemplate:
    """If *template* has an ``extends`` field, load the base from *registry*
    and apply overrides per §5.4.

    Returns a fully-resolved template (no ``extends``).  Chains are resolved
    recursively (A extends B extends C).
    """
    if not template.extends:
        return template

    base_name = template.extends
    base_template = registry.load_template(base_name)
    if base_template is None:
        raise InheritanceError(f"Base template '{base_name}' not found in registry")

    base_template = resolve_inheritance(base_template, registry)

    merged = _merge_templates(base_template, template)
    return merged


def _merge_templates(
    base: WorkflowTemplate,
    child: WorkflowTemplate,
) -> WorkflowTemplate:
    """Apply child overrides on top of base."""
    result = copy.deepcopy(base)

    result.metadata = copy.deepcopy(child.metadata)
    result.schema_version = child.schema_version or base.schema_version
    result.extends = None
    result.overrides = None

    overrides = child.overrides or {}

    _apply_stage_overrides(result, overrides.get("stages", {}))
    _apply_gate_overrides(result, overrides.get("gates", {}))
    _apply_env_overrides(result, overrides.get("environment_modes", {}))

    if child.team_overrides:
        result.team_overrides.update(child.team_overrides)

    return result


def _apply_stage_overrides(
    template: WorkflowTemplate,
    stage_overrides: dict[str, Any],
) -> None:
    for stage_id, overrides in stage_overrides.items():
        stage = template.stage_by_id(stage_id)
        if stage is None:
            continue
        for key, value in overrides.items():
            if key == "config" and isinstance(value, dict):
                stage.config.update(value)
            elif hasattr(stage, key):
                setattr(stage, key, value)


def _apply_gate_overrides(
    template: WorkflowTemplate,
    gate_overrides: dict[str, Any],
) -> None:
    gate_map = {g.name: g for g in template.gates}
    for gate_name, overrides in gate_overrides.items():
        gate = gate_map.get(gate_name)
        if gate is None:
            continue
        if "criteria" in overrides:
            from devolaflow.template_engine.models import GateCriterion

            gate.criteria = [
                GateCriterion(field=c["field"], operator=c["operator"], value=c["value"])
                for c in overrides["criteria"]
            ]


def _apply_env_overrides(
    template: WorkflowTemplate,
    env_overrides: dict[str, Any],
) -> None:
    for env_name, env_cfg in env_overrides.items():
        if env_name not in template.environment_modes:
            template.environment_modes[env_name] = {}
        existing = template.environment_modes[env_name]
        if isinstance(existing, dict) and isinstance(env_cfg, dict):
            existing.update(env_cfg)
        else:
            template.environment_modes[env_name] = env_cfg
