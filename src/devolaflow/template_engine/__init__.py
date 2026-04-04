"""Workflow template engine — parse, compose, validate.

Design ref: design_meta_framework.md §2-§5
"""

from devolaflow.template_engine.composer import (
    OPERATORS,
    ChoiceOp,
    GateOp,
    LoopOp,
    ParallelOp,
    SequenceOp,
    collect_all_refs,
    collect_stage_refs,
)
from devolaflow.template_engine.inheritance import (
    InheritanceError,
    resolve_inheritance,
)
from devolaflow.template_engine.models import (
    DEPENDENCY_LATTICE,
    VALID_PRIMITIVES,
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
from devolaflow.template_engine.parser import (
    TemplateParseError,
    parse_composition,
    parse_template,
    parse_template_string,
)
from devolaflow.template_engine.registry import TemplateRegistry
from devolaflow.template_engine.validator import (
    ValidationResult,
    validate_all_templates,
    validate_template,
)

__all__ = [
    "DEPENDENCY_LATTICE",
    "OPERATORS",
    "VALID_PRIMITIVES",
    "Break",
    "Choice",
    "ChoiceOp",
    "CompositionNode",
    "GateCriterion",
    "GateDef",
    "GateOnFail",
    "GateOp",
    "GateRef",
    "InheritanceError",
    "LoopDef",
    "LoopOp",
    "LoopRef",
    "Parallel",
    "ParallelOp",
    "Sequence",
    "SequenceOp",
    "StageDefinition",
    "StageRef",
    "TemplateMetadata",
    "TemplateParseError",
    "TemplateRegistry",
    "ValidationResult",
    "WorkflowTemplate",
    "collect_all_refs",
    "collect_stage_refs",
    "parse_composition",
    "parse_template",
    "parse_template_string",
    "resolve_inheritance",
    "validate_all_templates",
    "validate_template",
]
