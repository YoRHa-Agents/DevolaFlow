"""Focused tests for pure preflight Section 0 drafting."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace import (
    PreflightConfigBaseline,
    PreflightDraftError,
    draft_preflight_section0,
)
from devolaflow.pre_decision import auto_detect
from devolaflow.skills.slash_commands import scaffold_change_folder

_HASH = "0123456789abcdef" * 4
_SIGNED_AT = "2026-08-24T09:30:00Z"


def _seed_python_repo(root: Path, *, remote: str | None = None) -> None:
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "example.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    git = root / ".git"
    git.mkdir(exist_ok=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    config = "[core]\nrepositoryformatversion = 0\n"
    if remote is not None:
        config += f'[remote "origin"]\nurl = {remote}\n'
    (git / "config").write_text(config, encoding="utf-8")


def _baseline(config: dict[str, object], **changes: str) -> PreflightConfigBaseline:
    values = {
        "change_id": "prior-change",
        "authorized_at": _SIGNED_AT,
        "project_config_hash": _HASH,
        "config": config,
    }
    values.update(changes)
    return PreflightConfigBaseline(**values)  # type: ignore[arg-type]


def test_draft_auto_detect_renders_all_eight_sections_without_writes(tmp_path: Path) -> None:
    _seed_python_repo(tmp_path, remote="https://github.com/example/project.git")

    result = draft_preflight_section0(
        tmp_path,
        project_name="example",
        project_purpose="Exercise pure preflight drafting",
        seed_mode="feature-enhancement",
    )

    assert result.mode == "draft"
    assert result.config_inherited_from is None
    assert result.project_config_hash is None
    assert result.changed_fields == ()
    headings = [f"### 0.{index} " for index in range(1, 9)]
    positions = [result.markdown.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert result.config["project"]["existing_codebase"] is True  # type: ignore[index]
    assert result.config["tech_stack"]["primary_language"] == "python"  # type: ignore[index]
    assert result.config["tech_stack"]["dependency_manifest"] == "pyproject.toml"  # type: ignore[index]
    assert result.config["repository"]["mode"] == "github"  # type: ignore[index]
    assert result.config["repository"]["default_branch"] == "main"  # type: ignore[index]
    assert not (tmp_path / ".local").exists()


def test_draft_surfaces_validation_errors_and_auto_fixes(tmp_path: Path) -> None:
    _seed_python_repo(tmp_path)

    result = draft_preflight_section0(
        tmp_path,
        overrides={
            "tech_stack.primary_language": "rust",
            "tech_stack.build_system": "npm",
            "workflow.type": "security_audit",
        },
    )

    findings = {finding.rule: finding for finding in result.validation_findings}
    assert findings["language_build_match"].severity == "error"
    assert findings["security_review_with_audit"].severity == "auto_fix"
    assert result.config["quality"]["security_review_required"] is True  # type: ignore[index]
    assert "security_review_required: true" in result.markdown


def test_inherited_no_drift_collapses_to_hash_line(tmp_path: Path) -> None:
    _seed_python_repo(tmp_path)
    initial = draft_preflight_section0(
        tmp_path,
        project_name="example",
        project_purpose="Stable inherited configuration",
        seed_mode="feature-enhancement",
    )
    baseline_config = deepcopy(initial.config)
    baseline_config.update({"version": "legacy", "created_at": "ignored", "status": "frozen"})
    baseline = _baseline(baseline_config)

    result = draft_preflight_section0(tmp_path, inherited=baseline)

    assert result.mode == "inherited"
    assert result.changed_fields == ()
    assert result.config_inherited_from == "prior-change"
    assert result.project_config_hash == _HASH
    assert result.markdown.splitlines() == [
        f"- Inherited from prior-change (signed {_SIGNED_AT}); "
        f"config hash {_HASH} matches; no drift."
    ]
    assert baseline.config == baseline_config
    with pytest.raises(FrozenInstanceError):
        result.mode = "delta"  # type: ignore[misc]

    raw_baseline = _baseline(asdict(auto_detect(tmp_path)))
    raw_result = draft_preflight_section0(tmp_path, inherited=raw_baseline)
    assert raw_result.mode == "inherited"
    assert raw_result.changed_fields == ()


def test_inherited_detected_drift_renders_only_changed_fields(tmp_path: Path) -> None:
    _seed_python_repo(tmp_path)
    initial = draft_preflight_section0(tmp_path)
    baseline_config = deepcopy(initial.config)
    baseline = _baseline(baseline_config)
    _seed_python_repo(tmp_path, remote="https://github.com/example/project.git")

    result = draft_preflight_section0(tmp_path, inherited=baseline)

    assert result.mode == "delta"
    assert result.project_config_hash is None
    assert result.changed_fields == (
        "repository.mode",
        "repository.remote_url",
        "repository.features",
    )
    assert result.markdown.count("### ") == 1
    assert "### 0.3 Repository" in result.markdown
    assert "previous=local | proposed=github" in result.markdown
    assert "default_branch" not in result.markdown
    assert baseline.config == baseline_config


def test_explicit_overrides_render_delta_and_schema_mappings(tmp_path: Path) -> None:
    _seed_python_repo(tmp_path)
    initial = draft_preflight_section0(tmp_path)
    result = draft_preflight_section0(
        tmp_path,
        inherited=_baseline(deepcopy(initial.config)),
        overrides={
            "repository.mode": "other-git",
            "quality.quality_score_threshold": 90,
            "quality.gate_profile": "relaxed",
            "quality.max_convergence_rounds": 6,
            "quality.benchmark_required": True,
            "workflow.type": "security_audit",
            "workflow.custom_stages": ["triage"],
            "workflow.skip_stages": ["release"],
            "workflow.stage_overrides": {"verify": {"strict": True}},
        },
    )

    quality = result.config["quality"]  # type: ignore[assignment]
    workflow = result.config["workflow"]  # type: ignore[assignment]
    assert result.mode == "delta"
    assert result.config["repository"]["mode"] == "other_git"  # type: ignore[index]
    assert quality["quality_score_threshold"] == 9
    assert quality["gate_profile"] == "minimal"
    assert quality["max_rounds"] == 6
    assert quality["harness_evaluation_required"] is True
    assert workflow == {
        "seed_mode": "security_audit",
        "runtime_loop": "checklist_rounds",
        "seed_overrides": {
            "custom_stages": ["triage"],
            "skip_stages": ["release"],
            "stage_overrides": {"verify": {"strict": True}},
        },
    }
    assert "quality.coverage_target_pct" not in result.changed_fields
    assert "coverage_target_pct" not in result.markdown
    assert "previous=" in result.markdown and "proposed=" in result.markdown


def test_scaffold_uses_runtime_section_zero_and_stays_unsigned(tmp_path: Path) -> None:
    _seed_python_repo(tmp_path)

    folder = scaffold_change_folder("Runtime Section Zero", tmp_path)
    preflight = (folder / "preflight.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(preflight.split("---", 2)[1])

    assert preflight.count("## 0. Project Configuration") == 1
    assert preflight.count("### 0.") == 8
    assert "- primary_language: python |" in preflight
    assert "- dependency_manifest: pyproject.toml |" in preflight
    assert "- name: runtime-section-zero |" in preflight
    for section in range(1, 5):
        assert f"## {section}." in preflight
    assert frontmatter["authorized_at"] is None
    assert frontmatter["project_config_hash"] is None
    assert not (tmp_path / ".local" / "project_config.yaml").exists()


def test_invalid_baseline_or_override_fails_loudly(tmp_path: Path) -> None:
    _seed_python_repo(tmp_path)
    initial = draft_preflight_section0(tmp_path)
    config = deepcopy(initial.config)
    invalid_cases = (
        (_baseline(config, change_id="Bad_ID"), None, "change_id"),
        (_baseline(config, authorized_at="2026-02-30T09:30:00Z"), None, "authorized_at"),
        (_baseline(config, project_config_hash="A" * 64), None, "lowercase hexadecimal"),
        (_baseline(config), {"unknown.field": True}, "unknown dotted override"),
        (_baseline(config), {"workflow.runtime_loop": "stages"}, "checklist_rounds"),
        (
            _baseline(config),
            {"workflow.seed_overrides": {"unknown": True}},
            "unknown dotted override",
        ),
        (_baseline(config), {"quality.min_convergence_rounds": 2}, "unknown dotted override"),
        (None, {"not_dotted": True}, "invalid dotted override"),
    )

    for baseline, overrides, message in invalid_cases:
        with pytest.raises(PreflightDraftError, match=message):
            draft_preflight_section0(tmp_path, inherited=baseline, overrides=overrides)
