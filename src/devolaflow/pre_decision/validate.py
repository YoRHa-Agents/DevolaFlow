"""Consistency validation for the pre-decision checklist.

Design ref: design_execution_protocol.md §3.4
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devolaflow.pre_decision.checklist import PreDecisionChecklist

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_JS_MANAGERS = {"npm", "yarn", "pnpm", "bun"}


@dataclass
class ValidationError:
    """One consistency-check result."""

    rule: str
    severity: str  # error | warning | auto_fix
    message: str
    field: str = ""


# ── Individual rule checkers ─────────────────────────────────────────────


def _check_language_build_match(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 1 — Rust projects must use cargo."""
    lang = checklist.tech_stack.primary_language
    build = checklist.tech_stack.build_system
    if lang != "rust":
        return None
    if not build:
        return None
    if build == "cargo":
        return None
    return ValidationError(
        rule="language_build_match",
        severity="error",
        message="Rust projects must use cargo as build system",
        field="tech_stack.build_system",
    )


def _check_language_build_match_ts(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 2 — TypeScript projects must use a JS package manager."""
    lang = checklist.tech_stack.primary_language
    build = checklist.tech_stack.build_system
    if lang != "typescript":
        return None
    if not build:
        return None
    if build in _JS_MANAGERS:
        return None
    return ValidationError(
        rule="language_build_match_ts",
        severity="error",
        message="TypeScript projects must use a JS package manager (npm/yarn/pnpm/bun)",
        field="tech_stack.build_system",
    )


def _check_github_features_require_github_mode(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 3 — GitHub Actions requires repository mode 'github'."""
    if not checklist.repository.features.github_actions:
        return None
    if checklist.repository.mode == "github":
        return None
    return ValidationError(
        rule="github_features_require_github_mode",
        severity="error",
        message="GitHub Actions requires repository mode 'github'",
        field="repository.features.github_actions",
    )


def _check_cross_platform_needs_targets(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 4 — Cross-platform builds need multiple OS targets."""
    if not checklist.repository.features.cross_platform_builds:
        return None
    if len(checklist.platforms.os) >= 2:
        return None
    return ValidationError(
        rule="cross_platform_needs_targets",
        severity="warning",
        message="Cross-platform builds enabled but only one OS target specified",
        field="platforms.os",
    )


def _check_security_review_with_audit(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 5 — security_audit workflow auto-enables security_review_required."""
    if checklist.workflow.type != "security_audit":
        return None
    if checklist.quality.security_review_required:
        return None
    checklist.quality.security_review_required = True
    return ValidationError(
        rule="security_review_with_audit",
        severity="auto_fix",
        message="Set quality.security_review_required = true (security_audit workflow)",
        field="quality.security_review_required",
    )


def _check_coverage_within_range(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 6 — Coverage target must be 0–100."""
    cov = checklist.quality.coverage_target_pct
    if 0 <= cov <= 100:
        return None
    return ValidationError(
        rule="coverage_within_range",
        severity="error",
        message=f"Coverage target must be between 0 and 100, got {cov}",
        field="quality.coverage_target_pct",
    )


def _check_gate_profile_consistency(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 7 — Strict gate profile expects >= 90% coverage."""
    if checklist.quality.gate_profile != "strict":
        return None
    cov = checklist.quality.coverage_target_pct
    if cov >= 90:
        return None
    return ValidationError(
        rule="gate_profile_consistency",
        severity="warning",
        message=f"Strict gate profile typically uses >= 90% coverage. Current: {cov}%",
        field="quality.coverage_target_pct",
    )


def _check_local_mode_no_publish(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 8 — Local repos shouldn't have publishing targets."""
    if checklist.repository.mode != "local":
        return None
    if len(checklist.release.publishing_targets) == 0:
        return None
    return ValidationError(
        rule="local_mode_no_publish",
        severity="warning",
        message="Publishing targets set but repo mode is local. Publishing requires a remote.",
        field="release.publishing_targets",
    )


def _check_version_semver_format(
    checklist: PreDecisionChecklist,
) -> ValidationError | None:
    """Rule 9 — Initial version must be valid semver when versioning='semver'."""
    if checklist.release.versioning != "semver":
        return None
    ver = checklist.release.initial_version
    if not ver:
        return None
    if _SEMVER_RE.match(ver):
        return None
    return ValidationError(
        rule="version_semver_format",
        severity="error",
        message=f"Initial version must be valid semver (e.g., 0.1.0), got '{ver}'",
        field="release.initial_version",
    )


_CONSISTENCY_RULES = [
    _check_language_build_match,
    _check_language_build_match_ts,
    _check_github_features_require_github_mode,
    _check_cross_platform_needs_targets,
    _check_security_review_with_audit,
    _check_coverage_within_range,
    _check_gate_profile_consistency,
    _check_local_mode_no_publish,
    _check_version_semver_format,
]


def validate_consistency(checklist: PreDecisionChecklist) -> list[ValidationError]:
    """Run all 9 consistency rules from design_execution_protocol.md §3.4.

    Returns an empty list when the checklist is fully consistent.
    """
    errors: list[ValidationError] = []
    for rule_fn in _CONSISTENCY_RULES:
        result = rule_fn(checklist)
        if result is not None:
            errors.append(result)
    return errors
