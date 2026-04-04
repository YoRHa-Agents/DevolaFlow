"""Pre-decision phase — repo detection, checklist, validation, recommendation.

Design ref: design_execution_protocol.md §2-§3
"""

from devolaflow.pre_decision.checklist import PreDecisionChecklist, auto_detect
from devolaflow.pre_decision.detect import RepoMode, detect_repo_mode
from devolaflow.pre_decision.freeze import freeze_config
from devolaflow.pre_decision.recommend import Recommendation, recommend_workflow
from devolaflow.pre_decision.validate import ValidationError, validate_consistency

__all__ = [
    "PreDecisionChecklist",
    "Recommendation",
    "RepoMode",
    "ValidationError",
    "auto_detect",
    "detect_repo_mode",
    "freeze_config",
    "recommend_workflow",
    "validate_consistency",
]
