"""Tests for the pre-decision engine.

Covers:
  - Repo mode detection (no .git, local, github, gitlab, etc.)
  - All 13 workflow recommendation examples from design_meta_framework.md §6.6
  - All 9 consistency validation rules (positive + negative)
  - Checklist auto-detection with mock workspace
  - Config freeze writes valid YAML
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from devolaflow.pre_decision.checklist import (
    PreDecisionChecklist,
    ProjectSection,
    QualitySection,
    ReleaseSection,
    RepositorySection,
    TechStackSection,
    WorkflowSection,
    auto_detect,
)
from devolaflow.pre_decision.detect import (
    detect_repo_mode,
    match_platform,
    normalize_git_url,
)
from devolaflow.pre_decision.freeze import FreezeError, freeze_config
from devolaflow.pre_decision.recommend import (
    confidence_level,
    recommend_workflow,
)
from devolaflow.pre_decision.validate import validate_consistency

# ═══════════════════════════════════════════════════════════════════════════
# 1.  Repo mode detection
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeGitUrl:
    def test_https(self) -> None:
        assert normalize_git_url("https://github.com/user/repo.git") == "github.com/user/repo"

    def test_ssh(self) -> None:
        assert normalize_git_url("git@github.com:user/repo.git") == "github.com:user/repo"

    def test_ssh_protocol(self) -> None:
        out = normalize_git_url("ssh://git@gitlab.corp.io/org/repo.git")
        assert "gitlab.corp.io" in out

    def test_strips_whitespace(self) -> None:
        assert normalize_git_url("  https://github.com/u/r.git  ") == "github.com/u/r"


class TestMatchPlatform:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://github.com/user/repo.git", "github"),
            ("git@github.com:user/repo.git", "github"),
            ("https://gitlab.com/user/repo.git", "gitlab"),
            ("git@gitlab.corp.io:org/repo", "gitlab"),
            ("https://gitea.example.com/user/repo", "gitea"),
            ("https://forgejo.example.com/user/repo", "gitea"),
            ("https://codeberg.org/user/repo", "gitea"),
            ("https://bitbucket.org/user/repo", "bitbucket"),
            ("https://selfhosted.example.com/user/repo", "generic"),
        ],
    )
    def test_patterns(self, url: str, expected: str) -> None:
        assert match_platform(url) == expected


def _make_git_repo(path: Path, remote_url: str | None = None) -> None:
    """Create a minimal .git directory with optional remote."""
    git_dir = path / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    config = git_dir / "config"
    if remote_url:
        config.write_text(
            textwrap.dedent(f"""\
                [remote "origin"]
                    url = {remote_url}
                    fetch = +refs/heads/*:refs/remotes/origin/*
            """)
        )
    else:
        config.write_text("[core]\n\tbare = false\n")


class TestDetectRepoMode:
    def test_no_git_directory(self, tmp_path: Path) -> None:
        result = detect_repo_mode(tmp_path)
        assert result.mode == "local"
        assert result.variant is None
        assert result.remote_url is None

    def test_git_no_remote(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path)
        result = detect_repo_mode(tmp_path)
        assert result.mode == "local"
        assert result.variant is None

    def test_github_remote(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "git@github.com:user/repo.git")
        result = detect_repo_mode(tmp_path)
        assert result.mode == "github"
        assert result.variant is None
        assert result.remote_url == "git@github.com:user/repo.git"

    def test_gitlab_remote(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "https://gitlab.com/org/project.git")
        result = detect_repo_mode(tmp_path)
        assert result.mode == "other-git"
        assert result.variant == "gitlab"

    def test_bitbucket_remote(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "git@bitbucket.org:team/project.git")
        result = detect_repo_mode(tmp_path)
        assert result.mode == "other-git"
        assert result.variant == "bitbucket"

    def test_gitea_remote(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "https://gitea.company.com/user/repo.git")
        result = detect_repo_mode(tmp_path)
        assert result.mode == "other-git"
        assert result.variant == "gitea"

    def test_codeberg_remote(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "https://codeberg.org/user/repo.git")
        result = detect_repo_mode(tmp_path)
        assert result.mode == "other-git"
        assert result.variant == "gitea"

    def test_generic_remote(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "https://selfhosted.example.com/user/repo.git")
        result = detect_repo_mode(tmp_path)
        assert result.mode == "other-git"
        assert result.variant == "generic"

    def test_ci_config_fallback_gitlab(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "https://selfhosted.example.com/user/repo.git")
        (tmp_path / ".gitlab-ci.yml").write_text("stages: [build]")
        result = detect_repo_mode(tmp_path)
        assert result.variant == "gitlab"


# ═══════════════════════════════════════════════════════════════════════════
# 2.  Workflow recommendation — all 13 examples from §6.6
# ═══════════════════════════════════════════════════════════════════════════

_RECOMMENDATION_CASES: list[tuple[str, str, str]] = [
    # (purpose_text, expected_top_workflow, expected_confidence)
    ("fix a bug in the login page", "hotfix", "high"),
    ("design a new API for user management", "design-only", "high"),
    ("design a new system with research", "research-design-review-refine", "high"),
    ("research the best TUI framework for Rust", "research-only", "high"),
    ("build a complete authentication system from scratch", "full-pipeline", "high"),
    ("improve performance of the query engine", "performance-optimization", "high"),
    ("refactor the database layer for better separation", "refactoring", "high"),
    ("migrate from MySQL to PostgreSQL", "migration", "high"),
    ("try using WebSockets instead of polling", "spike-poc", "medium"),
    ("update the README and add API docs", "documentation-only", "high"),
    ("check for CVEs in our dependencies", "security-audit", "high"),
    ("add pagination to the user list endpoint", "feature-enhancement", "medium"),
    ("make the app better", "performance-optimization", "low"),
]


class TestRecommendWorkflow:
    @pytest.mark.parametrize(
        "purpose,expected_wf,expected_confidence",
        _RECOMMENDATION_CASES,
        ids=[c[0][:40] for c in _RECOMMENDATION_CASES],
    )
    def test_recommendation_example(
        self,
        purpose: str,
        expected_wf: str,
        expected_confidence: str,
    ) -> None:
        recs = recommend_workflow(purpose)
        assert len(recs) >= 1
        top = recs[0]

        if expected_confidence == "low":
            # For ambiguous inputs, the expected workflow should appear somewhere
            wf_types = [r.workflow_type for r in recs]
            assert expected_wf in wf_types or "full-pipeline" in wf_types
            assert top.confidence in ("low", "medium")
        else:
            assert top.workflow_type == expected_wf, (
                f"Expected {expected_wf} but got {top.workflow_type} "
                f"(score={top.score}, kws={top.matched_keywords})"
            )
            assert top.confidence == expected_confidence

    def test_returns_at_most_3(self) -> None:
        recs = recommend_workflow("build a new project from scratch")
        assert len(recs) <= 3

    def test_scores_sorted_descending(self) -> None:
        recs = recommend_workflow("design a new API")
        scores = [r.score for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_explicit_type_name_boost(self) -> None:
        recs = recommend_workflow("run a hotfix workflow")
        assert recs[0].workflow_type == "hotfix"

    def test_urgency_heuristic(self) -> None:
        recs = recommend_workflow("we need to fix this urgent production issue")
        assert recs[0].workflow_type == "hotfix"

    def test_question_form_boosts_research(self) -> None:
        recs = recommend_workflow("which database should we use for analytics?")
        assert recs[0].workflow_type == "research-only"


# ═══════════════════════════════════════════════════════════════════════════
# 3.  Consistency validation — all 9 rules
# ═══════════════════════════════════════════════════════════════════════════


def _make_checklist(**overrides: object) -> PreDecisionChecklist:
    """Build a valid baseline checklist, then apply overrides."""
    cl = PreDecisionChecklist(
        project=ProjectSection(name="test", purpose="test purpose"),
        tech_stack=TechStackSection(primary_language="python", build_system="pip"),
        repository=RepositorySection(mode="github"),
        quality=QualitySection(),
        release=ReleaseSection(),
        workflow=WorkflowSection(type="full_pipeline"),
    )
    for key, val in overrides.items():
        parts = key.split(".")
        obj = cl
        for p in parts[:-1]:
            obj = getattr(obj, p)
        setattr(obj, parts[-1], val)
    return cl


class TestValidateConsistency:
    # ── Rule 1: language_build_match ──────────────────────────────────

    def test_rule1_rust_cargo_ok(self) -> None:
        cl = _make_checklist(
            **{"tech_stack.primary_language": "rust", "tech_stack.build_system": "cargo"}
        )
        errors = validate_consistency(cl)
        assert not any(e.rule == "language_build_match" for e in errors)

    def test_rule1_rust_npm_error(self) -> None:
        cl = _make_checklist(
            **{"tech_stack.primary_language": "rust", "tech_stack.build_system": "npm"}
        )
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "language_build_match"]
        assert len(err) == 1
        assert err[0].severity == "error"

    # ── Rule 2: language_build_match_ts ───────────────────────────────

    def test_rule2_ts_npm_ok(self) -> None:
        cl = _make_checklist(
            **{"tech_stack.primary_language": "typescript", "tech_stack.build_system": "npm"}
        )
        errors = validate_consistency(cl)
        assert not any(e.rule == "language_build_match_ts" for e in errors)

    def test_rule2_ts_cargo_error(self) -> None:
        cl = _make_checklist(
            **{
                "tech_stack.primary_language": "typescript",
                "tech_stack.build_system": "cargo",
            }
        )
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "language_build_match_ts"]
        assert len(err) == 1
        assert err[0].severity == "error"

    # ── Rule 3: github_features_require_github_mode ───────────────────

    def test_rule3_github_actions_on_github_ok(self) -> None:
        cl = _make_checklist(**{"repository.mode": "github"})
        cl.repository.features.github_actions = True
        errors = validate_consistency(cl)
        assert not any(e.rule == "github_features_require_github_mode" for e in errors)

    def test_rule3_github_actions_on_local_error(self) -> None:
        cl = _make_checklist(**{"repository.mode": "local"})
        cl.repository.features.github_actions = True
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "github_features_require_github_mode"]
        assert len(err) == 1
        assert err[0].severity == "error"

    # ── Rule 4: cross_platform_needs_targets ──────────────────────────

    def test_rule4_cross_platform_multiple_os_ok(self) -> None:
        cl = _make_checklist()
        cl.repository.features.cross_platform_builds = True
        cl.platforms.os = ["linux", "macos"]
        errors = validate_consistency(cl)
        assert not any(e.rule == "cross_platform_needs_targets" for e in errors)

    def test_rule4_cross_platform_single_os_warning(self) -> None:
        cl = _make_checklist()
        cl.repository.features.cross_platform_builds = True
        cl.platforms.os = ["linux"]
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "cross_platform_needs_targets"]
        assert len(err) == 1
        assert err[0].severity == "warning"

    # ── Rule 5: security_review_with_audit ────────────────────────────

    def test_rule5_auto_fix(self) -> None:
        cl = _make_checklist(**{"workflow.type": "security_audit"})
        cl.quality.security_review_required = False
        errors = validate_consistency(cl)
        assert cl.quality.security_review_required is True
        err = [e for e in errors if e.rule == "security_review_with_audit"]
        assert len(err) == 1
        assert err[0].severity == "auto_fix"

    def test_rule5_already_set(self) -> None:
        cl = _make_checklist(**{"workflow.type": "security_audit"})
        cl.quality.security_review_required = True
        errors = validate_consistency(cl)
        assert not any(e.rule == "security_review_with_audit" for e in errors)

    # ── Rule 6: coverage_within_range ─────────────────────────────────

    def test_rule6_valid_coverage(self) -> None:
        cl = _make_checklist(**{"quality.coverage_target_pct": 80})
        errors = validate_consistency(cl)
        assert not any(e.rule == "coverage_within_range" for e in errors)

    def test_rule6_negative_coverage_error(self) -> None:
        cl = _make_checklist(**{"quality.coverage_target_pct": -5})
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "coverage_within_range"]
        assert len(err) == 1
        assert err[0].severity == "error"

    def test_rule6_over_100_error(self) -> None:
        cl = _make_checklist(**{"quality.coverage_target_pct": 150})
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "coverage_within_range"]
        assert len(err) == 1

    # ── Rule 7: gate_profile_consistency ──────────────────────────────

    def test_rule7_strict_high_coverage_ok(self) -> None:
        cl = _make_checklist(
            **{"quality.gate_profile": "strict", "quality.coverage_target_pct": 95}
        )
        errors = validate_consistency(cl)
        assert not any(e.rule == "gate_profile_consistency" for e in errors)

    def test_rule7_strict_low_coverage_warning(self) -> None:
        cl = _make_checklist(
            **{"quality.gate_profile": "strict", "quality.coverage_target_pct": 70}
        )
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "gate_profile_consistency"]
        assert len(err) == 1
        assert err[0].severity == "warning"

    # ── Rule 8: local_mode_no_publish ─────────────────────────────────

    def test_rule8_local_no_targets_ok(self) -> None:
        cl = _make_checklist(**{"repository.mode": "local"})
        cl.release.publishing_targets = []
        errors = validate_consistency(cl)
        assert not any(e.rule == "local_mode_no_publish" for e in errors)

    def test_rule8_local_with_targets_warning(self) -> None:
        cl = _make_checklist(**{"repository.mode": "local"})
        cl.release.publishing_targets = ["pypi"]
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "local_mode_no_publish"]
        assert len(err) == 1
        assert err[0].severity == "warning"

    # ── Rule 9: version_semver_format ─────────────────────────────────

    def test_rule9_valid_semver(self) -> None:
        cl = _make_checklist(**{"release.initial_version": "0.1.0"})
        errors = validate_consistency(cl)
        assert not any(e.rule == "version_semver_format" for e in errors)

    def test_rule9_valid_semver_prerelease(self) -> None:
        cl = _make_checklist(**{"release.initial_version": "1.0.0-alpha.1"})
        errors = validate_consistency(cl)
        assert not any(e.rule == "version_semver_format" for e in errors)

    def test_rule9_invalid_semver_error(self) -> None:
        cl = _make_checklist(**{"release.initial_version": "not-a-version"})
        errors = validate_consistency(cl)
        err = [e for e in errors if e.rule == "version_semver_format"]
        assert len(err) == 1
        assert err[0].severity == "error"

    def test_rule9_missing_patch(self) -> None:
        cl = _make_checklist(**{"release.initial_version": "1.0"})
        errors = validate_consistency(cl)
        assert any(e.rule == "version_semver_format" for e in errors)


# ═══════════════════════════════════════════════════════════════════════════
# 4.  Checklist auto-detection
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoDetect:
    def test_empty_workspace(self, tmp_path: Path) -> None:
        cl = auto_detect(tmp_path)
        assert cl.status == "collecting"
        assert cl.repository.mode == "local"
        assert cl.project.existing_codebase is False
        assert cl.tech_stack.primary_language == ""

    def test_python_workspace(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("print('hi')")
        (tmp_path / "utils.py").write_text("x = 1")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='foo'")
        cl = auto_detect(tmp_path)
        assert cl.tech_stack.primary_language == "python"
        assert cl.tech_stack.build_system == "pip"
        assert cl.tech_stack.dependency_manifest == "pyproject.toml"
        assert cl.project.existing_codebase is True

    def test_rust_workspace(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.rs").write_text("fn main() {}")
        (tmp_path / "src" / "lib.rs").write_text("pub fn add() {}")
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "foo"')
        cl = auto_detect(tmp_path)
        assert cl.tech_stack.primary_language == "rust"
        assert cl.tech_stack.build_system == "cargo"

    def test_github_repo(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path, "git@github.com:user/proj.git")
        cl = auto_detect(tmp_path)
        assert cl.repository.mode == "github"
        assert cl.repository.features.github_actions is True
        assert cl.repository.features.ci_cd is True

    def test_default_branch_detected(self, tmp_path: Path) -> None:
        _make_git_repo(tmp_path)
        cl = auto_detect(tmp_path)
        assert cl.repository.default_branch == "main"

    def test_created_at_set(self, tmp_path: Path) -> None:
        cl = auto_detect(tmp_path)
        assert cl.created_at != ""


# ═══════════════════════════════════════════════════════════════════════════
# 5.  Classify fields
# ═══════════════════════════════════════════════════════════════════════════


class TestClassifyFields:
    def test_mandatory_fields(self) -> None:
        cl = PreDecisionChecklist()
        fields = cl.classify_fields()
        assert fields["project.name"] == "MANDATORY"
        assert fields["project.purpose"] == "MANDATORY"
        assert fields["tech_stack.primary_language"] == "MANDATORY"

    def test_confirm_fields(self) -> None:
        cl = PreDecisionChecklist()
        fields = cl.classify_fields()
        assert fields["repository.mode"] == "CONFIRM"
        assert fields["tech_stack.build_system"] == "CONFIRM"
        assert fields["workflow.type"] == "CONFIRM"

    def test_defaulted_fields(self) -> None:
        cl = PreDecisionChecklist()
        fields = cl.classify_fields()
        assert fields["quality.coverage_target_pct"] == "DEFAULTED"
        assert fields["release.versioning"] == "DEFAULTED"
        assert fields["platforms.os"] == "DEFAULTED"

    def test_all_fields_classified(self) -> None:
        cl = PreDecisionChecklist()
        fields = cl.classify_fields()
        assert all(v in ("MANDATORY", "DEFAULTED", "CONFIRM") for v in fields.values())


# ═══════════════════════════════════════════════════════════════════════════
# 6.  Config freeze
# ═══════════════════════════════════════════════════════════════════════════


class TestFreezeConfig:
    def test_writes_valid_yaml(self, tmp_path: Path) -> None:
        cl = _make_checklist()
        out = tmp_path / "project_config.yaml"
        freeze_config(cl, out)
        assert out.exists()
        data = yaml.safe_load(out.read_text())
        assert data["status"] == "frozen"
        assert data["project"]["name"] == "test"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        cl = _make_checklist()
        out = tmp_path / "sub" / "deep" / "project_config.yaml"
        freeze_config(cl, out)
        assert out.exists()

    def test_blocking_error_raises(self, tmp_path: Path) -> None:
        cl = _make_checklist(
            **{"tech_stack.primary_language": "rust", "tech_stack.build_system": "npm"}
        )
        with pytest.raises(FreezeError, match="language_build_match"):
            freeze_config(cl, tmp_path / "project_config.yaml")

    def test_warnings_included_in_output(self, tmp_path: Path) -> None:
        cl = _make_checklist(**{"repository.mode": "local"})
        cl.release.publishing_targets = ["pypi"]
        out = tmp_path / "project_config.yaml"
        freeze_config(cl, out)
        data = yaml.safe_load(out.read_text())
        assert "_validation_notes" in data
        assert any(n["rule"] == "local_mode_no_publish" for n in data["_validation_notes"])

    def test_frozen_checklist_roundtrips(self, tmp_path: Path) -> None:
        cl = _make_checklist()
        out = tmp_path / "project_config.yaml"
        freeze_config(cl, out)
        data = yaml.safe_load(out.read_text())
        assert data["version"] == "1.0"
        assert data["tech_stack"]["primary_language"] == "python"
        assert data["quality"]["coverage_target_pct"] == 80


# ═══════════════════════════════════════════════════════════════════════════
# 7.  Confidence-level utility
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceLevel:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.95, "high"),
            (0.65, "high"),
            (0.50, "medium"),
            (0.30, "medium"),
            (0.20, "low"),
            (0.10, "low"),
            (0.05, "none"),
            (0.0, "none"),
        ],
    )
    def test_thresholds(self, score: float, expected: str) -> None:
        assert confidence_level(score) == expected
