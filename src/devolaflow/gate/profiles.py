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
)

PROFILES: dict[str, GateProfile] = {
    "strict": STRICT,
    "standard": STANDARD,
    "relaxed": RELAXED,
    "audit": AUDIT,
}
