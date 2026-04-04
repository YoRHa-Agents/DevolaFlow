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


@dataclass
class ValidationError:
    """One consistency-check result."""

    rule: str
    severity: str  # error | warning | auto_fix
    message: str
    field: str = ""


def validate_consistency(checklist: PreDecisionChecklist) -> list[ValidationError]:
    """Run all 9 consistency rules from design_execution_protocol.md §3.4.

    Returns an empty list when the checklist is fully consistent.
    """
    errors: list[ValidationError] = []

    lang = checklist.tech_stack.primary_language
    build = checklist.tech_stack.build_system

    # Rule 1 — language_build_match (Rust → cargo)
    if lang == "rust" and build and build != "cargo":
        errors.append(
            ValidationError(
                rule="language_build_match",
                severity="error",
                message="Rust projects must use cargo as build system",
                field="tech_stack.build_system",
            )
        )

    # Rule 2 — language_build_match_ts (TypeScript → JS package manager)
    js_managers = {"npm", "yarn", "pnpm", "bun"}
    if lang == "typescript" and build and build not in js_managers:
        errors.append(
            ValidationError(
                rule="language_build_match_ts",
                severity="error",
                message="TypeScript projects must use a JS package manager (npm/yarn/pnpm/bun)",
                field="tech_stack.build_system",
            )
        )

    # Rule 3 — github_features_require_github_mode
    feats = checklist.repository.features
    if feats.github_actions and checklist.repository.mode != "github":
        errors.append(
            ValidationError(
                rule="github_features_require_github_mode",
                severity="error",
                message="GitHub Actions requires repository mode 'github'",
                field="repository.features.github_actions",
            )
        )

    # Rule 4 — cross_platform_needs_targets
    if feats.cross_platform_builds and len(checklist.platforms.os) < 2:
        errors.append(
            ValidationError(
                rule="cross_platform_needs_targets",
                severity="warning",
                message="Cross-platform builds enabled but only one OS target specified",
                field="platforms.os",
            )
        )

    # Rule 5 — security_review_with_audit (auto-fix)
    if (
        checklist.workflow.type == "security_audit"
        and not checklist.quality.security_review_required
    ):
        checklist.quality.security_review_required = True
        errors.append(
            ValidationError(
                rule="security_review_with_audit",
                severity="auto_fix",
                message="Set quality.security_review_required = true (security_audit workflow)",
                field="quality.security_review_required",
            )
        )

    # Rule 6 — coverage_within_range
    cov = checklist.quality.coverage_target_pct
    if cov < 0 or cov > 100:
        errors.append(
            ValidationError(
                rule="coverage_within_range",
                severity="error",
                message=f"Coverage target must be between 0 and 100, got {cov}",
                field="quality.coverage_target_pct",
            )
        )

    # Rule 7 — gate_profile_consistency
    if checklist.quality.gate_profile == "strict" and cov < 90:
        errors.append(
            ValidationError(
                rule="gate_profile_consistency",
                severity="warning",
                message=(f"Strict gate profile typically uses >= 90% coverage. Current: {cov}%"),
                field="quality.coverage_target_pct",
            )
        )

    # Rule 8 — local_mode_no_publish
    if checklist.repository.mode == "local" and len(checklist.release.publishing_targets) > 0:
        errors.append(
            ValidationError(
                rule="local_mode_no_publish",
                severity="warning",
                message=(
                    "Publishing targets set but repo mode is local. Publishing requires a remote."
                ),
                field="release.publishing_targets",
            )
        )

    # Rule 9 — version_semver_format
    ver = checklist.release.initial_version
    if checklist.release.versioning == "semver" and ver and not _SEMVER_RE.match(ver):
        errors.append(
            ValidationError(
                rule="version_semver_format",
                severity="error",
                message=f"Initial version must be valid semver (e.g., 0.1.0), got '{ver}'",
                field="release.initial_version",
            )
        )

    return errors
