"""Gate quality mechanism — scoring, profiles, reports, convergence.

Design ref: design_decomposition_gate.md §5
"""

from devolaflow.gate.convergence import compute_trend, detect_stagnation
from devolaflow.gate.models import (
    CheckResult,
    ConvergenceRound,
    Finding,
    GateInput,
    GateProfile,
    GateVerdict,
)
from devolaflow.gate.profiles import AUDIT, PROFILES, RELAXED, STANDARD, STRICT
from devolaflow.gate.reporter import generate_markdown_report, generate_yaml_report
from devolaflow.gate.scorer import (
    DEFAULT_DIMENSION_WEIGHTS,
    SEVERITY_WEIGHTS,
    composite_score,
    evaluate_gate,
    quality_score,
    run_gate_cli,
)

__all__ = [
    "AUDIT",
    "DEFAULT_DIMENSION_WEIGHTS",
    "PROFILES",
    "RELAXED",
    "SEVERITY_WEIGHTS",
    "STANDARD",
    "STRICT",
    "CheckResult",
    "ConvergenceRound",
    "Finding",
    "GateInput",
    "GateProfile",
    "GateVerdict",
    "composite_score",
    "compute_trend",
    "detect_stagnation",
    "evaluate_gate",
    "generate_markdown_report",
    "generate_yaml_report",
    "quality_score",
    "run_gate_cli",
]
