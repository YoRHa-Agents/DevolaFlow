"""Predefined gate profiles.

Design ref: design_decomposition_gate.md §5.4
"""

from devolaflow.gate.models import GateProfile

STRICT = GateProfile(
    name="strict",
    composite_threshold=90,
    coverage_threshold=85,
    max_blocker=0,
    max_critical=0,
    max_rounds=4,
    min_rounds=2,
    lint_policy="zero_warnings",
    benchmark_policy="required",
    acceptance_readiness_threshold=90,
    visual_fidelity_threshold=95,
    interaction_quality_threshold=95,
    accessibility_threshold=95,
    acceptance_verification_threshold=95,
)

STANDARD = GateProfile(
    name="standard",
    composite_threshold=85,
    coverage_threshold=80,
    max_blocker=0,
    max_critical=2,
    max_rounds=3,
    min_rounds=1,
    lint_policy="zero_errors",
    benchmark_policy="optional",
    acceptance_readiness_threshold=80,
    visual_fidelity_threshold=90,
    interaction_quality_threshold=90,
    accessibility_threshold=90,
    acceptance_verification_threshold=90,
)

RELAXED = GateProfile(
    name="relaxed",
    composite_threshold=70,
    coverage_threshold=60,
    max_blocker=0,
    max_critical=5,
    max_rounds=2,
    min_rounds=1,
    lint_policy="zero_errors",
    benchmark_policy="disabled",
    acceptance_readiness_threshold=70,
    visual_fidelity_threshold=80,
    interaction_quality_threshold=80,
    accessibility_threshold=80,
    acceptance_verification_threshold=80,
)

AUDIT = GateProfile(
    name="audit",
    composite_threshold=95,
    coverage_threshold=90,
    max_blocker=0,
    max_critical=0,
    max_rounds=6,
    min_rounds=3,
    lint_policy="zero_warnings",
    benchmark_policy="required_with_regression_check",
    acceptance_readiness_threshold=95,
    visual_fidelity_threshold=98,
    interaction_quality_threshold=98,
    accessibility_threshold=95,
    acceptance_verification_threshold=98,
)

PROFILES: dict[str, GateProfile] = {
    "strict": STRICT,
    "standard": STANDARD,
    "relaxed": RELAXED,
    "audit": AUDIT,
}
