"""Tests for the validate_owned_files lifecycle hook (v7.5.0 P-05).

Covers:
  - WORKFLOW_MANIFESTS registry contents and parity with repo-init.yaml
  - validate_owned_files() — happy path, missing paths, non-repo-init, non-dict
  - _path_covered() — exact match, prefix match, trailing slash normalization
  - get_canonical_manifest() — known workflow, unknown workflow
  - DoctorFinding / DoctorReport — dataclass behavior
  - check_init_health() — full virtual repo scaffolding test
  - Strict mode raises on violation
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.lifecycle.dispatcher import HookViolation
from devolaflow.lifecycle.validate_owned_files import (
    WORKFLOW_MANIFESTS,
    DoctorFinding,
    DoctorReport,
    _path_covered,
    check_init_health,
    get_canonical_manifest,
    validate_owned_files,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_REPO_INIT_PATHS = [
    ".local/feedbacks/",
    ".local/tasks/",
    ".local/memory/",
    ".local/index.md",
    ".rules/compile-config.yaml",
    # v8.2.3 — A1 .agent/* substrate per .local/research/v8.3.0_design.md §1.1.
    # MUST stay in this exact order — parity-locked with repo-init.yaml and SKILL.md.
    ".local/.agent/active/",
    ".local/.agent/handoff/",
    ".local/.agent/archive/",
]


class TestWorkflowManifests:
    """Tests for the WORKFLOW_MANIFESTS registry."""

    def test_repo_init_manifest_has_eight_paths(self):
        assert len(WORKFLOW_MANIFESTS["repo-init"]) == 8

    def test_repo_init_manifest_paths_match_expected(self):
        assert WORKFLOW_MANIFESTS["repo-init"] == EXPECTED_REPO_INIT_PATHS

    def test_manifest_parity_with_template_yaml(self):
        template_path = (
            REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin" / "repo-init.yaml"
        )
        with open(template_path, encoding="utf-8") as f:
            template = yaml.safe_load(f)

        scaffold_stage = next(s for s in template["stages"] if s["id"] == "scaffold")
        yaml_manifest = scaffold_stage["config"]["canonical_manifest"]
        assert yaml_manifest == WORKFLOW_MANIFESTS["repo-init"]


class TestPathCovered:
    """Tests for the _path_covered() helper."""

    def test_exact_match_file(self):
        assert _path_covered(".local/index.md", {".local/index.md"})

    def test_exact_match_directory(self):
        assert _path_covered(".local/feedbacks/", {".local/feedbacks/"})

    def test_prefix_match(self):
        assert _path_covered(".local/feedbacks/", {".local/feedbacks/TRACKER.md"})

    def test_trailing_slash_normalization(self):
        assert _path_covered(".local/feedbacks/", {".local/feedbacks"})

    def test_no_match(self):
        assert not _path_covered(".local/feedbacks/", {".rules/config.yaml"})


class TestValidateOwnedFiles:
    """Tests for the validate_owned_files() hook."""

    def test_passes_when_all_canonical_paths_present(self):
        payload = {
            "workflow": "repo-init",
            "owned_files": list(EXPECTED_REPO_INIT_PATHS),
        }
        result = validate_owned_files(payload)
        assert result.passed
        assert result.violations == []

    def test_fails_when_missing_paths(self):
        payload = {
            "workflow": "repo-init",
            "owned_files": [".local/feedbacks/", ".local/tasks/"],
        }
        result = validate_owned_files(payload)
        assert not result.passed
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.code == "VOF001"
        assert v.severity == "blocker"
        # 8 canonical - 2 supplied = 6 missing post v8.2.3 (was 3 pre-v8.2.3).
        assert len(v.context["missing_paths"]) == 6

    def test_fails_when_all_paths_missing(self):
        payload = {
            "workflow": "repo-init",
            "owned_files": [],
        }
        result = validate_owned_files(payload)
        assert not result.passed
        v = result.violations[0]
        assert v.code == "VOF001"
        assert v.context["missing_paths"] == EXPECTED_REPO_INIT_PATHS

    def test_passes_for_non_manifest_workflow(self):
        payload = {
            "workflow": "full-pipeline",
            "owned_files": [],
        }
        result = validate_owned_files(payload)
        assert result.passed

    def test_non_dict_payload_passes(self):
        result = validate_owned_files("not a dict")
        assert result.passed
        assert result.violations == []

    def test_missing_workflow_key_passes(self):
        payload = {"owned_files": [".local/feedbacks/"]}
        result = validate_owned_files(payload)
        assert result.passed

    def test_strict_mode_raises_vof001(self):
        payload = {
            "workflow": "repo-init",
            "owned_files": [".local/feedbacks/"],
        }
        with pytest.raises(HookViolation) as exc_info:
            validate_owned_files(payload, strict=True)
        assert exc_info.value.code == "VOF001"

    def test_accepts_prefix_match_for_directory_paths(self):
        payload = {
            "workflow": "repo-init",
            "owned_files": [
                ".local/feedbacks/TRACKER.md",
                ".local/tasks/README.md",
                ".local/memory/MEMORY.md",
                ".local/index.md",
                ".rules/compile-config.yaml",
                # v8.2.3 — sub-paths under .agent/* directories prefix-cover the
                # canonical manifest entries via _path_covered's startswith check.
                ".local/.agent/active/README.md",
                ".local/.agent/handoff/README.md",
                ".local/.agent/archive/README.md",
            ],
        }
        result = validate_owned_files(payload)
        assert result.passed

    def test_accepts_alternate_files_key(self):
        payload = {
            "workflow": "repo-init",
            "files": list(EXPECTED_REPO_INIT_PATHS),
        }
        result = validate_owned_files(payload)
        assert result.passed

    def test_owned_files_not_list_passes(self):
        payload = {
            "workflow": "repo-init",
            "owned_files": "not-a-list",
        }
        result = validate_owned_files(payload)
        assert result.passed
        assert result.violations == []


class TestGetCanonicalManifest:
    """Tests for get_canonical_manifest()."""

    def test_returns_list_for_known_workflow(self):
        result = get_canonical_manifest("repo-init")
        assert isinstance(result, list)
        assert len(result) == 8

    def test_returns_empty_for_unknown_workflow(self):
        assert get_canonical_manifest("unknown") == []

    def test_returns_copy_not_reference(self):
        result = get_canonical_manifest("repo-init")
        result.append("extra")
        assert "extra" not in WORKFLOW_MANIFESTS["repo-init"]


class TestDoctorFinding:
    """Tests for DoctorFinding dataclass."""

    def test_ok_when_found_matches_expected(self):
        f = DoctorFinding(path=".local/feedbacks/", expected=True, found=True, detail="directory")
        assert f.ok

    def test_not_ok_when_mismatch(self):
        f = DoctorFinding(
            path=".local/feedbacks/",
            expected=True,
            found=False,
            detail="missing directory",
        )
        assert not f.ok


class TestDoctorReport:
    """Tests for DoctorReport dataclass."""

    @pytest.fixture()
    def all_ok_findings(self) -> list[DoctorFinding]:
        return [
            DoctorFinding(path=".local/feedbacks/", expected=True, found=True, detail="directory"),
            DoctorFinding(path=".local/tasks/", expected=True, found=True, detail="directory"),
        ]

    @pytest.fixture()
    def one_missing_findings(self) -> list[DoctorFinding]:
        return [
            DoctorFinding(path=".local/feedbacks/", expected=True, found=True, detail="directory"),
            DoctorFinding(
                path=".local/tasks/",
                expected=True,
                found=False,
                detail="missing directory",
            ),
        ]

    def test_healthy_when_all_ok(self, all_ok_findings):
        report = DoctorReport(findings=all_ok_findings)
        assert report.healthy

    def test_unhealthy_when_any_missing(self, one_missing_findings):
        report = DoctorReport(findings=one_missing_findings)
        assert not report.healthy

    def test_missing_lists_unfound_paths(self):
        findings = [
            DoctorFinding(path=".local/feedbacks/", expected=True, found=False, detail="missing"),
            DoctorFinding(path=".local/tasks/", expected=True, found=True, detail="ok"),
            DoctorFinding(path=".local/memory/", expected=True, found=False, detail="missing"),
        ]
        report = DoctorReport(findings=findings)
        assert report.missing == [".local/feedbacks/", ".local/memory/"]

    def test_summary_includes_counts(self, one_missing_findings):
        report = DoctorReport(findings=one_missing_findings)
        s = report.summary()
        assert "1/2 checks passed" in s


class TestCheckInitHealth:
    """Tests for check_init_health() with virtual repo scaffolding."""

    def test_healthy_after_full_scaffold(self, tmp_path):
        from devolaflow.init_project import _find_agent_dir, install_local
        from devolaflow.local.workspace import scaffold_local

        scaffold_local(tmp_path)
        install_local(_find_agent_dir(), tmp_path)

        report = check_init_health(tmp_path)
        assert report.healthy, f"Unhealthy after scaffold: {report.summary()}"

    def test_unhealthy_on_empty_directory(self, tmp_path):
        report = check_init_health(tmp_path)
        assert not report.healthy
        assert len(report.missing) > 0

    def test_unhealthy_when_partial_scaffold(self, tmp_path):
        (tmp_path / ".local" / "feedbacks").mkdir(parents=True)
        report = check_init_health(tmp_path)
        assert not report.healthy
        present = {f.path for f in report.findings if f.found}
        assert ".local/feedbacks/" in present
        missing_set = set(report.missing)
        assert ".local/tasks/" in missing_set
        assert ".local/memory/" in missing_set

    def test_checks_sub_artifacts(self, tmp_path):
        report = check_init_health(tmp_path)
        checked_paths = {f.path for f in report.findings}
        assert ".local/feedbacks/TRACKER.md" in checked_paths
        assert ".local/memory/MEMORY.md" in checked_paths
        assert ".local/feedbacks/README.md" in checked_paths
        assert ".local/tasks/README.md" in checked_paths
        assert ".local/memory/README.md" in checked_paths
