"""Constraint-tier metadata and deterministic dispatch summaries.

Tier annotations are optional, nested dispatch metadata.  The helpers in this
module never mutate their inputs; callers must opt in to annotation so legacy
payloads remain byte-identical.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Final, Literal, TypeAlias

ConstraintTier: TypeAlias = Literal["invariant", "guard", "advisory"]

_VALID_TIERS: Final[frozenset[str]] = frozenset({"invariant", "guard", "advisory"})

BEHAVIORAL_FIELD_TIERS: Final[dict[str, ConstraintTier]] = {
    "think_first": "advisory",
    "simplicity_check": "advisory",
    "surgical_scope": "guard",
    "goal_loop": "advisory",
    "no_llm_for_deterministic": "advisory",
    "surface_conflicts": "advisory",
    "convention_first": "advisory",
    "line_level_criteria": "guard",
}

SOURCE_TIERS: Final[dict[str, ConstraintTier]] = {
    "gate_scalar_leaf": "invariant",
    "checklist_item": "guard",
    "machine_acceptance_v2": "guard",
    "manual_or_legacy_acceptance": "advisory",
    "rules_focus": "advisory",
    "quality_focus": "advisory",
    "reinforcement_rule": "guard",
}

_LEAN_RULE_METADATA: Final[frozenset[str]] = frozenset({"strategy", "lang"})
_FULL_RULE_METADATA: Final[frozenset[str]] = frozenset(
    {"loading_strategy", "language", "task_type", "reinforcement"}
)


def _constraint_tiers(
    value: object,
    *,
    field: str,
) -> dict[str, ConstraintTier]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a field-name-to-tier mapping")

    validated: dict[str, ConstraintTier] = {}
    for name, tier in value.items():
        if not isinstance(name, str) or tier not in _VALID_TIERS:
            raise ValueError(
                f"{field} contains invalid explicit tier {tier!r} for {name!r}; "
                "expected invariant, guard, or advisory"
            )
        validated[name] = tier
    return validated


def _explicit_rule_tier(rule: Mapping[str, Any], *, field: str) -> ConstraintTier | None:
    if "tier" not in rule:
        return None
    tier = rule["tier"]
    if tier not in _VALID_TIERS:
        raise ValueError(
            f"{field} has invalid explicit tier {tier!r}; expected invariant, guard, or advisory"
        )
    return tier


def annotate_behavioral_guidelines(
    block: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a fresh behavioral block carrying field-level tier metadata.

    Known fields use :data:`BEHAVIORAL_FIELD_TIERS`.  Unknown fields are
    preserved and default to ``advisory`` unless they carry valid explicit
    metadata.  Stale metadata for absent fields is discarded.
    """

    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise ValueError("behavioral_guidelines must be a mapping")

    annotated = deepcopy(dict(block))
    explicit = _constraint_tiers(
        annotated.pop("constraint_tiers", None),
        field="behavioral_guidelines.constraint_tiers",
    )
    if not annotated:
        return annotated

    annotated["constraint_tiers"] = {
        name: BEHAVIORAL_FIELD_TIERS.get(name, explicit.get(name, "advisory")) for name in annotated
    }
    return annotated


def _annotate_rule_block(
    block: object,
    *,
    field: str,
    metadata_fields: frozenset[str],
    canonical_fields: Mapping[str, ConstraintTier],
) -> None:
    if not isinstance(block, dict) or not block:
        return
    explicit = _constraint_tiers(
        block.pop("constraint_tiers", None),
        field=f"{field}.constraint_tiers",
    )
    constraint_fields = [
        name for name in block if name not in metadata_fields and name != "constraint_tiers"
    ]
    if constraint_fields:
        block["constraint_tiers"] = {
            name: canonical_fields.get(name, explicit.get(name, "advisory"))
            for name in constraint_fields
        }


def _annotate_reinforcement(block: object, *, field: str) -> None:
    if not isinstance(block, dict):
        return
    rules = block.get("rules")
    if not isinstance(rules, list):
        return
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        _explicit_rule_tier(rule, field=f"{field}.rules[{index}].tier")
        rule["tier"] = SOURCE_TIERS["reinforcement_rule"]


def annotate_rule_surfaces(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a fresh payload with lean and full rule surfaces annotated."""

    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    annotated = deepcopy(dict(payload))

    _annotate_rule_block(
        annotated.get("rules"),
        field="rules",
        metadata_fields=_LEAN_RULE_METADATA,
        canonical_fields={"focus": SOURCE_TIERS["rules_focus"]},
    )
    _annotate_reinforcement(annotated.get("reinforce"), field="reinforce")

    context = annotated.get("context")
    if isinstance(context, dict):
        applicable = context.get("applicable_rules")
        _annotate_rule_block(
            applicable,
            field="context.applicable_rules",
            metadata_fields=_FULL_RULE_METADATA,
            canonical_fields={"quality_focus": SOURCE_TIERS["quality_focus"]},
        )
        if isinstance(applicable, dict):
            _annotate_reinforcement(
                applicable.get("reinforcement"),
                field="context.applicable_rules.reinforcement",
            )
    return annotated


def _scalar_leaf_count(value: object) -> int:
    if isinstance(value, Mapping):
        return sum(_scalar_leaf_count(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_scalar_leaf_count(item) for item in value)
    return int(value is not None)


def _active_constraint(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return value is not None and value != "" and value != [] and value != {}


def _add(breakdown: dict[str, int], tier: ConstraintTier, count: int = 1) -> None:
    breakdown[tier] += count


def _summarize_behavioral(payload: Mapping[str, Any], breakdown: dict[str, int]) -> None:
    block = payload.get("behavioral_guidelines")
    if not isinstance(block, Mapping):
        return
    explicit = _constraint_tiers(
        block.get("constraint_tiers"),
        field="behavioral_guidelines.constraint_tiers",
    )
    for name, value in block.items():
        if name == "constraint_tiers":
            continue
        if isinstance(value, list):
            count = sum(_active_constraint(item) for item in value)
        else:
            count = int(_active_constraint(value))
        if count:
            _add(breakdown, explicit.get(name, "advisory"), count)


def _summarize_rule_block(
    block: object,
    *,
    field: str,
    metadata_fields: frozenset[str],
    canonical_fields: Mapping[str, ConstraintTier],
    breakdown: dict[str, int],
) -> None:
    if not isinstance(block, Mapping):
        return
    explicit = _constraint_tiers(
        block.get("constraint_tiers"),
        field=f"{field}.constraint_tiers",
    )
    for name, value in block.items():
        if name in metadata_fields or name == "constraint_tiers":
            continue
        if isinstance(value, list):
            count = sum(_active_constraint(item) for item in value)
        else:
            count = int(_active_constraint(value))
        if count:
            _add(
                breakdown,
                explicit.get(name, canonical_fields.get(name, "advisory")),
                count,
            )


def _reinforcement_rules(payload: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    surfaces: list[tuple[str, object]] = [("reinforce", payload.get("reinforce"))]
    context = payload.get("context")
    if isinstance(context, Mapping):
        applicable = context.get("applicable_rules")
        if isinstance(applicable, Mapping):
            surfaces.append(
                (
                    "context.applicable_rules.reinforcement",
                    applicable.get("reinforcement"),
                )
            )

    rules: list[tuple[str, Mapping[str, Any]]] = []
    for field, block in surfaces:
        if not isinstance(block, Mapping) or not isinstance(block.get("rules"), list):
            continue
        for index, rule in enumerate(block["rules"]):
            if isinstance(rule, Mapping):
                rules.append((f"{field}.rules[{index}].tier", rule))
    return rules


def _summarize_reinforcement(payload: Mapping[str, Any], breakdown: dict[str, int]) -> None:
    seen: set[tuple[object, object]] = set()
    for field, rule in _reinforcement_rules(payload):
        _explicit_rule_tier(rule, field=field)
        raw_key = (rule.get("id"), rule.get("mandate"))
        key = tuple(
            value if isinstance(value, (str, int, float, bool, type(None))) else repr(value)
            for value in raw_key
        )
        if key not in seen:
            seen.add(key)
            _add(breakdown, SOURCE_TIERS["reinforcement_rule"])


def _summarize_acceptance(payload: Mapping[str, Any], breakdown: dict[str, int]) -> None:
    structured = payload.get("acceptance_criteria_v2")
    mirrored_descriptions: dict[str, ConstraintTier] = {}
    if isinstance(structured, list):
        for criterion in structured:
            machine = (
                isinstance(criterion, Mapping)
                and criterion.get("verification_type") in {"test", "metric"}
                and isinstance(criterion.get("verification_cmd"), str)
                and bool(criterion["verification_cmd"].strip())
            )
            tier = (
                SOURCE_TIERS["machine_acceptance_v2"]
                if machine
                else SOURCE_TIERS["manual_or_legacy_acceptance"]
            )
            _add(breakdown, tier)
            if isinstance(criterion, Mapping):
                description = criterion.get("description")
                if isinstance(description, str) and (normalized := description.strip()):
                    prior = mirrored_descriptions.get(normalized)
                    mirrored_descriptions[normalized] = (
                        "advisory" if prior == "advisory" or tier == "advisory" else "guard"
                    )

    for field in ("accept", "acceptance_criteria"):
        legacy = payload.get(field)
        if isinstance(legacy, list):
            for criterion in legacy:
                normalized = criterion.strip() if isinstance(criterion, str) else None
                if normalized and normalized in mirrored_descriptions:
                    # The exact AC-v2 mirror already contributed its machine-derived tier.
                    continue
                _add(breakdown, SOURCE_TIERS["manual_or_legacy_acceptance"])

    acceptance = payload.get("acceptance")
    if isinstance(acceptance, Mapping) and isinstance(acceptance.get("criteria"), list):
        _add(
            breakdown,
            SOURCE_TIERS["manual_or_legacy_acceptance"],
            len(acceptance["criteria"]),
        )


def summarize_constraints(
    payload: Mapping[str, Any],
) -> tuple[int, dict[str, int], float]:
    """Summarize dispatch constraints and their machine-quantifiable ratio."""

    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    breakdown = {"invariant": 0, "guard": 0, "advisory": 0}

    gate = payload.get("gate")
    if isinstance(gate, Mapping):
        _add(breakdown, SOURCE_TIERS["gate_scalar_leaf"], _scalar_leaf_count(gate))

    change_context = payload.get("change_context")
    if isinstance(change_context, Mapping) and isinstance(
        change_context.get("checklist_items"), list
    ):
        _add(
            breakdown,
            SOURCE_TIERS["checklist_item"],
            len(change_context["checklist_items"]),
        )

    _summarize_acceptance(payload, breakdown)
    _summarize_behavioral(payload, breakdown)
    _summarize_rule_block(
        payload.get("rules"),
        field="rules",
        metadata_fields=_LEAN_RULE_METADATA,
        canonical_fields={"focus": SOURCE_TIERS["rules_focus"]},
        breakdown=breakdown,
    )

    context = payload.get("context")
    if isinstance(context, Mapping):
        _summarize_rule_block(
            context.get("applicable_rules"),
            field="context.applicable_rules",
            metadata_fields=_FULL_RULE_METADATA,
            canonical_fields={"quality_focus": SOURCE_TIERS["quality_focus"]},
            breakdown=breakdown,
        )
    _summarize_reinforcement(payload, breakdown)

    count = sum(breakdown.values())
    quantifiable_ratio = (breakdown["invariant"] + breakdown["guard"]) / count if count else 0.0
    return count, breakdown, quantifiable_ratio


def should_fold_advisory(model_hint: object) -> bool:
    """Return whether advisory prose may fold for this explicit model hint."""

    return model_hint in {"quality", "frontier"}
