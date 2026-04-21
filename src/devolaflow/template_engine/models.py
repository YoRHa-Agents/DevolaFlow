"""Dataclass IR for workflow templates.

Design ref: design_meta_framework.md §2 (primitives), §3 (composition), §4 (schema)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

VALID_PRIMITIVES = frozenset(
    {
        "research",
        "analyze",
        "design",
        "plan",
        "implement",
        "review",
        "test",
        "verify",
        "validate",
        "refine",
        "release",
        "deploy",
        "monitor",
        "gate",
    }
)

DEPENDENCY_LATTICE: dict[str, set[str]] = {
    "research": {"analyze", "design"},
    "analyze": {"design", "plan", "refine"},
    "design": {"plan", "review"},
    "plan": {"implement"},
    "implement": {"review", "test"},
    "review": {"refine", "validate", "verify"},
    "test": {"refine", "validate", "verify"},
    "verify": {"gate", "validate", "release", "refine"},
    "refine": {"implement", "design", "review", "test", "verify"},
    "validate": {"release", "refine"},
    "release": {"deploy"},
    "deploy": {"monitor"},
    "monitor": {"refine"},
    "gate": set(),
}


class JoinStrategy(Enum):
    """Enumerate parallel-join strategies (all, any, n_of)."""

    ALL = "all"
    ANY = "any"
    N_OF = "n_of"


class OnExhaustion(Enum):
    """Enumerate loop-exhaustion actions (escalate, abort, continue)."""

    ESCALATE = "escalate"
    ABORT = "abort"
    CONTINUE = "continue"


class GateFailAction(Enum):
    """Enumerate gate-failure actions (loop_back, escalate, abort)."""

    LOOP_BACK = "loop_back"
    ESCALATE = "escalate"
    ABORT = "abort"


# ── Stage Definition ──────────────────────────────────────────────


@dataclass
class StageDefinition:
    """Represent a single stage's identity, primitive, and configuration."""

    id: str
    primitive: str
    alias: str | None = None
    description: str | None = None
    team: str | None = None
    duration_class: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    input_mapping: dict[str, Any] = field(default_factory=dict)
    skip_condition: str | None = None
    timeout_minutes: int | None = None


# ── Composition Nodes (union type) ────────────────────────────────


@dataclass
class StageRef:
    """Reference to a single stage by id."""

    stage: str


@dataclass
class Sequence:
    """Represent an ordered list of composition nodes executed sequentially."""

    stages: list[CompositionNode]


@dataclass
class Parallel:
    """Represent composition nodes executed concurrently with a join strategy."""

    stages: list[CompositionNode]
    join: str = "all"
    n_of_count: int | None = None


@dataclass
class Choice:
    """Represent a conditional branch selecting one of two composition paths."""

    condition: str
    if_true: CompositionNode
    if_false: CompositionNode


@dataclass
class LoopRef:
    """Reference to a named loop definition."""

    ref: str


@dataclass
class GateRef:
    """Reference to a named gate definition."""

    ref: str


@dataclass
class Break:
    """Represent a loop-exit node in the composition tree."""


CompositionNode = StageRef | Sequence | Parallel | Choice | LoopRef | GateRef | Break


# ── Loop / Gate Definitions ───────────────────────────────────────


@dataclass
class LoopDef:
    """Define a named convergence loop with termination conditions."""

    name: str
    body_stages: list[str]
    until: str
    max_iterations: int
    quality_threshold: float | None = None
    on_exhaustion: str = "escalate"
    escalation_target: str | None = None
    escalation_max: int | None = None


@dataclass
class GateCriterion:
    """Represent a single field-operator-value check within a gate."""

    field: str
    operator: str
    value: Any


@dataclass
class GateOnFail:
    """Represent the action and target to execute when a gate fails."""

    action: str
    target: str | None = None


@dataclass
class GateDef:
    """Define a named quality gate with criteria and pass/fail paths."""

    name: str
    position: str
    criteria: list[GateCriterion]
    on_pass: str
    on_fail: GateOnFail
    require_human_override: bool = False
    auto_insert: bool = False


# ── Template Metadata / Top-level ─────────────────────────────────


@dataclass
class TemplateMetadata:
    """Represent workflow template identity and catalog information."""

    name: str
    version: str
    display_name: str = ""
    description: str = ""
    category: str = ""
    applicable_scenarios: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    author: str | None = None
    created: str | None = None
    updated: str | None = None


@dataclass
class WorkflowTemplate:
    """Top-level container for a complete workflow template definition."""

    schema_version: str
    metadata: TemplateMetadata
    stages: list[StageDefinition]
    composition: CompositionNode
    loops: list[LoopDef] = field(default_factory=list)
    gates: list[GateDef] = field(default_factory=list)
    team_overrides: dict[str, str] = field(default_factory=dict)
    environment_modes: dict[str, Any] = field(default_factory=dict)
    extends: str | None = None
    overrides: dict[str, Any] | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def stage_ids(self) -> set[str]:
        """Return the set of all stage ids defined in this template."""
        return {s.id for s in self.stages}

    def stage_by_id(self, stage_id: str) -> StageDefinition | None:
        """Look up a stage definition by its id, or return None."""
        for s in self.stages:
            if s.id == stage_id:
                return s
        return None
