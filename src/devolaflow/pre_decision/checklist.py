"""Pre-decision checklist — 8-section configuration template.

Design ref: design_execution_protocol.md §2.3
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from devolaflow.pre_decision.detect import detect_repo_mode

# ── Section dataclasses ──────────────────────────────────────────────────

_SOURCE_EXTENSIONS: dict[str, str] = {
    ".rs": "rust",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

_MANIFEST_MAP: dict[str, tuple[str, str]] = {
    "Cargo.toml": ("cargo", "Cargo.toml"),
    "package.json": ("npm", "package.json"),
    "pyproject.toml": ("pip", "pyproject.toml"),
    "setup.py": ("pip", "setup.py"),
    "go.mod": ("go", "go.mod"),
    "build.gradle": ("gradle", "build.gradle"),
    "build.gradle.kts": ("gradle", "build.gradle.kts"),
    "pom.xml": ("maven", "pom.xml"),
    "Makefile": ("make", "Makefile"),
}


@dataclass
class ProjectSection:
    """Represent project identity fields (name, purpose, scope)."""

    name: str = ""
    purpose: str = ""
    scope_keywords: list[str] = field(default_factory=list)
    existing_codebase: bool = False


@dataclass
class TechStackSection:
    """Represent technology stack configuration (language, framework, build)."""

    primary_language: str = ""
    secondary_languages: list[str] = field(default_factory=list)
    framework: str = ""
    build_system: str = ""
    dependency_manifest: str = ""
    runtime_version: str = "latest stable"
    pinned_dependencies: list[str] = field(default_factory=list)
    banned_dependencies: list[str] = field(default_factory=list)


@dataclass
class RepositoryFeatures:
    """Represent boolean feature flags for repository capabilities."""

    ci_cd: bool = False
    cross_platform_builds: bool = False
    github_actions: bool = False
    github_pages: bool = False
    online_demo: bool = False
    release_publishing: bool = False
    merge_requests: bool = False
    readme: bool = True
    user_guide: bool = False
    changelog: bool = True


@dataclass
class RepositorySection:
    """Represent repository configuration (mode, branch, features)."""

    mode: str = ""
    remote_url: str = ""
    default_branch: str = "main"
    branching_strategy: str = "feature"
    features: RepositoryFeatures = field(default_factory=RepositoryFeatures)


@dataclass
class LocalizationSection:
    """Represent language and localization preferences."""

    primary_language: str = "en"
    secondary_language: str = ""
    bilingual_output: bool = False
    doc_language: str = "en"
    code_comments_language: str = "en"


@dataclass
class PlatformsSection:
    """Represent target platform constraints (OS, architecture)."""

    os: list[str] = field(default_factory=lambda: ["linux"])
    architectures: list[str] = field(default_factory=lambda: ["x86_64"])
    additional_targets: list[str] = field(default_factory=list)
    min_os_versions: dict[str, str] = field(default_factory=dict)


@dataclass
class QualitySection:
    """Represent quality gate thresholds and review requirements."""

    coverage_target_pct: int = 80
    quality_score_threshold: int = 85
    lint_strictness: str = "strict"
    gate_profile: str = "standard"
    max_convergence_rounds: int = 3
    min_convergence_rounds: int = 1
    security_review_required: bool = False
    benchmark_required: bool = False


@dataclass
class ReleaseSection:
    """Represent release strategy and versioning configuration."""

    versioning: str = "semver"
    initial_version: str = "0.1.0"
    channels: list[str] = field(default_factory=lambda: ["release"])
    publishing_targets: list[str] = field(default_factory=list)
    signing: bool = False
    changelog_format: str = "keepachangelog"


@dataclass
class WorkflowSection:
    """Represent workflow type selection and stage customization."""

    type: str = ""
    custom_stages: list[str] = field(default_factory=list)
    skip_stages: list[str] = field(default_factory=list)
    stage_overrides: dict[str, object] = field(default_factory=dict)


@dataclass
class PreDecisionChecklist:
    """Complete 8-section pre-decision checklist (design_execution_protocol.md §2.3)."""

    version: str = "1.0"
    created_at: str = ""
    status: str = "draft"

    project: ProjectSection = field(default_factory=ProjectSection)
    tech_stack: TechStackSection = field(default_factory=TechStackSection)
    repository: RepositorySection = field(default_factory=RepositorySection)
    localization: LocalizationSection = field(default_factory=LocalizationSection)
    platforms: PlatformsSection = field(default_factory=PlatformsSection)
    quality: QualitySection = field(default_factory=QualitySection)
    release: ReleaseSection = field(default_factory=ReleaseSection)
    workflow: WorkflowSection = field(default_factory=WorkflowSection)

    def classify_fields(self) -> dict[str, str]:
        """Classify every field as MANDATORY / DEFAULTED / CONFIRM per §3.2."""
        return {
            # Section 1 — Project Identity
            "project.name": "MANDATORY",
            "project.purpose": "MANDATORY",
            "project.scope_keywords": "DEFAULTED",
            "project.existing_codebase": "CONFIRM",
            # Section 2 — Tech Stack
            "tech_stack.primary_language": "MANDATORY",
            "tech_stack.secondary_languages": "DEFAULTED",
            "tech_stack.framework": "DEFAULTED",
            "tech_stack.build_system": "CONFIRM",
            "tech_stack.dependency_manifest": "CONFIRM",
            "tech_stack.runtime_version": "DEFAULTED",
            "tech_stack.pinned_dependencies": "DEFAULTED",
            "tech_stack.banned_dependencies": "DEFAULTED",
            # Section 3 — Repository Mode
            "repository.mode": "CONFIRM",
            "repository.remote_url": "CONFIRM",
            "repository.default_branch": "CONFIRM",
            "repository.branching_strategy": "DEFAULTED",
            "repository.features": "CONFIRM",
            # Section 4 — Localization
            "localization.primary_language": "DEFAULTED",
            "localization.secondary_language": "DEFAULTED",
            "localization.bilingual_output": "DEFAULTED",
            "localization.doc_language": "DEFAULTED",
            "localization.code_comments_language": "DEFAULTED",
            # Section 5 — Platforms
            "platforms.os": "DEFAULTED",
            "platforms.architectures": "DEFAULTED",
            "platforms.additional_targets": "DEFAULTED",
            "platforms.min_os_versions": "DEFAULTED",
            # Section 6 — Quality Standards
            "quality.coverage_target_pct": "DEFAULTED",
            "quality.quality_score_threshold": "DEFAULTED",
            "quality.lint_strictness": "DEFAULTED",
            "quality.gate_profile": "DEFAULTED",
            "quality.max_convergence_rounds": "DEFAULTED",
            "quality.min_convergence_rounds": "DEFAULTED",
            "quality.security_review_required": "DEFAULTED",
            "quality.benchmark_required": "DEFAULTED",
            # Section 7 — Release Strategy
            "release.versioning": "DEFAULTED",
            "release.initial_version": "DEFAULTED",
            "release.channels": "DEFAULTED",
            "release.publishing_targets": "DEFAULTED",
            "release.signing": "DEFAULTED",
            "release.changelog_format": "DEFAULTED",
            # Section 8 — Workflow Selection
            "workflow.type": "CONFIRM",
            "workflow.custom_stages": "DEFAULTED",
            "workflow.skip_stages": "DEFAULTED",
            "workflow.stage_overrides": "DEFAULTED",
        }


# ── Auto-detection ───────────────────────────────────────────────────────


def _detect_primary_language(repo_path: Path) -> str:
    """Determine the dominant source language by file-extension frequency."""
    counts: dict[str, int] = {}
    for p in repo_path.rglob("*"):
        lang = _SOURCE_EXTENSIONS.get(p.suffix) if p.is_file() else None
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return ""
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _detect_build_system(repo_path: Path) -> tuple[str, str]:
    """Return (build_system, manifest_filename) by checking for known manifests."""
    for filename, (system, manifest) in _MANIFEST_MAP.items():
        if (repo_path / filename).exists():
            return system, manifest
    return "", ""


def _detect_existing_codebase(repo_path: Path) -> bool:
    """Return True if the repository contains any recognized source files."""
    return any(p.is_file() and p.suffix in _SOURCE_EXTENSIONS for p in repo_path.rglob("*"))


def _branch_from_head(repo_path: Path) -> str | None:
    """Extract branch name from .git/HEAD ref pointer."""
    git_head = repo_path / ".git" / "HEAD"
    if not git_head.exists():
        return None
    content = git_head.read_text().strip()
    prefix = "ref: refs/heads/"
    return content.removeprefix(prefix) if content.startswith(prefix) else None


def _is_branch_section(section: str) -> bool:
    """True when *section* is a ``[branch "..."]`` git-config section."""
    return section.startswith('branch "') and section.endswith('"')


def _branch_from_config(repo_path: Path) -> str | None:
    """Extract the first branch name from .git/config sections."""
    git_config = repo_path / ".git" / "config"
    if not git_config.exists():
        return None
    parser = configparser.ConfigParser()
    parser.read(git_config)
    for section in parser.sections():
        if _is_branch_section(section):
            return section[8:-1]
    return None


def _detect_default_branch(repo_path: Path) -> str:
    """Determine the default branch name from .git/HEAD or config."""
    branch = _branch_from_head(repo_path)
    if branch:
        return branch
    branch = _branch_from_config(repo_path)
    if branch:
        return branch
    return "main"


_MODE_FEATURES: dict[str, dict[str, bool]] = {
    "github": {
        "ci_cd": True,
        "github_actions": True,
        "release_publishing": True,
        "changelog": True,
    },
    "other-git": {
        "ci_cd": True,
        "merge_requests": True,
        "changelog": True,
    },
}


def _apply_mode_features(features: RepositoryFeatures, mode: str) -> None:
    """Set repository feature flags based on the detected hosting mode."""
    for attr, value in _MODE_FEATURES.get(mode, {}).items():
        setattr(features, attr, value)


def auto_detect(repo_path: Path) -> PreDecisionChecklist:
    """Populate CONFIRM fields from workspace scan (§2.4)."""
    checklist = PreDecisionChecklist(
        created_at=datetime.now(UTC).isoformat(),
        status="collecting",
    )

    repo_mode = detect_repo_mode(repo_path)
    checklist.repository.mode = repo_mode.mode
    checklist.repository.remote_url = repo_mode.remote_url or ""
    _apply_mode_features(checklist.repository.features, repo_mode.mode)

    checklist.repository.default_branch = _detect_default_branch(repo_path)

    lang = _detect_primary_language(repo_path)
    if lang:
        checklist.tech_stack.primary_language = lang

    build, manifest = _detect_build_system(repo_path)
    if build:
        checklist.tech_stack.build_system = build
        checklist.tech_stack.dependency_manifest = manifest

    checklist.project.existing_codebase = _detect_existing_codebase(repo_path)

    return checklist
