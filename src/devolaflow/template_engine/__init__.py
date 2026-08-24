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
from devolaflow.template_engine.compositions import (
    REGISTRY_SCHEMA_V2,
    CompositionEntry,
    CompositionManifestError,
    CompositionStage,
    CompositionStep,
    composition_to_template,
    load_composition_manifest,
    validate_composition_manifest,
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
from devolaflow.template_engine.runtime import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_MODE,
    evaluate_skip_condition,
    select_stages_for_runtime,
)
from devolaflow.template_engine.validator import (
    ValidationResult,
    validate_all_templates,
    validate_template,
)

__all__ = [
    "DEFAULT_ENVIRONMENT",
    "DEFAULT_MODE",
    "DEPENDENCY_LATTICE",
    "OPERATORS",
    "REGISTRY_SCHEMA_V2",
    "VALID_PRIMITIVES",
    "Break",
    "Choice",
    "ChoiceOp",
    "CompositionEntry",
    "CompositionManifestError",
    "CompositionNode",
    "CompositionStage",
    "CompositionStep",
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
    "composition_to_template",
    "evaluate_skip_condition",
    "load_composition_manifest",
    "parse_composition",
    "parse_template",
    "parse_template_string",
    "resolve_inheritance",
    "select_stages_for_runtime",
    "validate_all_templates",
    "validate_composition_manifest",
    "validate_template",
]
