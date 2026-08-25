"""Deprecated NineS compatibility API.

This package remains importable in DevolaFlow v16 so existing callers can
migrate away from the legacy integration. It is scheduled for removal in
v17.

Primary research API:
    :func:`collect_research`, :func:`analyze_target`,
    :func:`run_self_evaluation`, :func:`run_skill_iteration`,
    :class:`NinesResearchConfig`, :func:`get_research_advice`.

Scorer API:
    :func:`nines_dimension_scores`.
"""

import warnings

from devolaflow.nines._cli import run_nines_cli
from devolaflow.nines.advisor import (
    NinesAdvisorConfig,
    get_research_advice,
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

warnings.warn(
    "devolaflow.nines is deprecated in v16 and scheduled for removal in v17",
    DeprecationWarning,
    stacklevel=2,
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
