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
    "review": {"refine", "validate"},
    "test": {"refine", "validate"},
    "refine": {"implement", "design", "review", "test"},
    "validate": {"release", "refine"},
    "release": {"deploy"},
    "deploy": {"monitor"},
    "monitor": {"refine"},
    "gate": set(),
}


class JoinStrategy(Enum):
    ALL = "all"
    ANY = "any"
    N_OF = "n_of"


class OnExhaustion(Enum):
    ESCALATE = "escalate"
    ABORT = "abort"
    CONTINUE = "continue"


class GateFailAction(Enum):
    LOOP_BACK = "loop_back"
    ESCALATE = "escalate"
    ABORT = "abort"


# ── Stage Definition ──────────────────────────────────────────────


@dataclass
class StageDefinition:
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
    stages: list[CompositionNode]


@dataclass
class Parallel:
    stages: list[CompositionNode]
    join: str = "all"
    n_of_count: int | None = None


@dataclass
class Choice:
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
    pass


CompositionNode = StageRef | Sequence | Parallel | Choice | LoopRef | GateRef | Break


# ── Loop / Gate Definitions ───────────────────────────────────────


@dataclass
class LoopDef:
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
    field: str
    operator: str
    value: Any


@dataclass
class GateOnFail:
    action: str
    target: str | None = None


@dataclass
class GateDef:
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

    def stage_ids(self) -> set[str]:
        return {s.id for s in self.stages}

    def stage_by_id(self, stage_id: str) -> StageDefinition | None:
        for s in self.stages:
            if s.id == stage_id:
                return s
        return None
