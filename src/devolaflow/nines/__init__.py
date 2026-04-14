"""NineS integration — research, analysis, and skill-iteration.

Provides detector, CLI wrappers, research utilities, and advisor
bridges to the NineS CLI.  All imports are safe when NineS is not
installed; functions return graceful fallback values.

Primary research API (preferred):
    :func:`collect_research`, :func:`analyze_target`,
    :func:`run_self_evaluation`, :func:`run_skill_iteration`,
    :class:`NinesResearchConfig`, :func:`get_research_advice`.

Legacy scorer/advisor API (backward-compatible, deprecated for gates):
    :func:`nines_dimension_scores`, :func:`run_nines_advisor`.
"""

from devolaflow.nines._cli import run_nines_cli
from devolaflow.nines.advisor import (
    NinesAdvisorConfig,
    get_research_advice,
    run_nines_advisor,
    should_invoke_advisor,
)
from devolaflow.nines.commands import (
    COMMANDS,
    DEFAULT_PARAMS,
    STAGE_MAPPING,
    build_command,
    build_stage_command,
)
from devolaflow.nines.detector import (
    NinesStatus,
    detect_nines,
    ensure_nines,
    get_nines_capabilities,
)
from devolaflow.nines.researcher import (
    NinesResearchConfig,
    SelfImproveResult,
    analyze_target,
    collect_research,
    refresh_reference_dependency,
    run_nines_benchmark,
    run_nines_update,
    run_self_evaluation,
    run_self_improve_loop,
    run_skill_iteration,
)
from devolaflow.nines.scorer import (
    NinesScorerConfig,
    nines_dimension_scores,
    run_nines_analyze,
    run_nines_eval,
)

__all__ = [
    # Shared CLI helper
    "run_nines_cli",
    # Command templates
    "COMMANDS",
    "DEFAULT_PARAMS",
    "STAGE_MAPPING",
    "build_command",
    "build_stage_command",
    # Research API (preferred)
    "NinesResearchConfig",
    "SelfImproveResult",
    "analyze_target",
    "collect_research",
    "get_research_advice",
    "refresh_reference_dependency",
    "run_nines_benchmark",
    "run_nines_update",
    "run_self_evaluation",
    "run_self_improve_loop",
    "run_skill_iteration",
    # Advisor
    "NinesAdvisorConfig",
    "get_research_advice",
    "run_nines_advisor",
    "should_invoke_advisor",
    # Detector
    "NinesStatus",
    "detect_nines",
    "ensure_nines",
    "get_nines_capabilities",
    # Legacy scorer (backward-compatible)
    "NinesScorerConfig",
    "nines_dimension_scores",
    "run_nines_analyze",
    "run_nines_eval",
]
