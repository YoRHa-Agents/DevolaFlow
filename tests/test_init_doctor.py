"""Tests for the devola-init doctor command and end-to-end init health verification.

Creates virtual (temporary) repositories, runs initialization, verifies health,
and cleans up. This is the regression gate for the v7.4.1/v7.5.0/v7.7.0
three-time repo-init owned_files drift issue.

Strategy:
  - Virtual repos are created in tmp_path (auto-cleaned by pytest)
  - Each test creates a fresh empty "repo", runs init, then checks doctor
  - Tests verify both positive (healthy after proper init) and negative
    (unhealthy on partial/missing scaffolding) scenarios
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from devolaflow.cli import doctor_cmd
from devolaflow.init_project import _find_agent_dir, install_local
from devolaflow.lifecycle.validate_owned_files import (
    WORKFLOW_MANIFESTS,
    check_init_health,
    validate_owned_files,
)
from devolaflow.local.workspace import scaffold_local


@pytest.fixture()
def agent_dir() -> Path:
    """Locate the agent directory; skip the test if SKILL.md is absent."""
    d = _find_agent_dir()
    if not (d / "SKILL.md").exists():
        pytest.skip("agent dir with SKILL.md not found (installed-package run)")
    return d


CANONICAL_MANIFEST = WORKFLOW_MANIFESTS["repo-init"]


# ---------------------------------------------------------------------------
# TestDoctorCmdCli — CLI entry-point behaviour
# ---------------------------------------------------------------------------


class TestDoctorCmdCli:
    """Verify ``doctor_cmd()`` exit codes and stdout output."""

    def test_doctor_exits_zero_after_full_init(
        self, tmp_path: Path, agent_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        install_local(agent_dir, tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            doctor_cmd()
        assert exc_info.value.code == 0

    def test_doctor_exits_one_on_empty_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            doctor_cmd()
        assert exc_info.value.code == 1

    def test_doctor_output_shows_missing_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            doctor_cmd()
        out = capsys.readouterr().out
        assert "missing" in out.lower()
        for p in CANONICAL_MANIFEST:
            assert p in out

    def test_doctor_output_shows_all_green_after_init(
        self,
        tmp_path: Path,
        agent_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)
        install_local(agent_dir, tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            doctor_cmd()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "\u2705" in out  # ✅
        assert "healthy" in out.lower()
        assert "\u274c" not in out  # ❌ should be absent


# ---------------------------------------------------------------------------
# TestVirtualRepoInitFlow — core end-to-end virtual-repo tests
# ---------------------------------------------------------------------------


class TestVirtualRepoInitFlow:
    """Create virtual repos in tmp_path, run init, and verify canonical paths."""

    def test_fresh_empty_repo_init_creates_canonical_manifest(
        self, tmp_path: Path, agent_dir: Path
    ) -> None:
        install_local(agent_dir, tmp_path)
        for p in CANONICAL_MANIFEST:
            full = tmp_path / p
            if p.endswith("/"):
                assert full.is_dir(), f"Expected directory: {p}"
            else:
                assert full.is_file(), f"Expected file: {p}"

    def test_fresh_repo_with_git_init(self, tmp_path: Path, agent_dir: Path) -> None:
        subprocess.run(
            ["git", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        assert (tmp_path / ".git").is_dir()

        install_local(agent_dir, tmp_path)
        for p in CANONICAL_MANIFEST:
            full = tmp_path / p
            if p.endswith("/"):
                assert full.is_dir(), f"Expected directory: {p}"
            else:
                assert full.is_file(), f"Expected file: {p}"

    def test_fresh_nextjs_style_repo(self, tmp_path: Path, agent_dir: Path) -> None:
        """Mirrors the v7.7.0 feedback scenario: a create-next-app project."""
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "my-app", "version": "0.1.0"}), encoding="utf-8"
        )
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "page.tsx").write_text("export default () => <h1>Hi</h1>;\n")
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / ".gitkeep").touch()

        install_local(agent_dir, tmp_path)
        for p in CANONICAL_MANIFEST:
            full = tmp_path / p
            if p.endswith("/"):
                assert full.is_dir(), f"Expected directory: {p}"
            else:
                assert full.is_file(), f"Expected file: {p}"

    def test_fresh_python_style_repo(self, tmp_path: Path, agent_dir: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "mylib"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "__init__.py").touch()

        install_local(agent_dir, tmp_path)
        for p in CANONICAL_MANIFEST:
            full = tmp_path / p
            if p.endswith("/"):
                assert full.is_dir(), f"Expected directory: {p}"
            else:
                assert full.is_file(), f"Expected file: {p}"

    def test_init_then_doctor_healthy(self, tmp_path: Path, agent_dir: Path) -> None:
        install_local(agent_dir, tmp_path)
        report = check_init_health(tmp_path)
        assert report.healthy, f"Expected healthy report, got: {report.summary()}"
        assert report.missing == []

    def test_partial_init_then_doctor_unhealthy(self, tmp_path: Path) -> None:
        """Only scaffold_local (no .rules/) → doctor reports compile-config.yaml missing."""
        scaffold_local(tmp_path)
        report = check_init_health(tmp_path)
        assert not report.healthy
        assert ".rules/compile-config.yaml" in report.missing

    def test_double_init_is_idempotent(self, tmp_path: Path, agent_dir: Path) -> None:
        install_local(agent_dir, tmp_path)
        marker = tmp_path / ".local" / "feedbacks" / "user_note.md"
        marker.write_text("do not overwrite", encoding="utf-8")

        install_local(agent_dir, tmp_path)

        report = check_init_health(tmp_path)
        assert report.healthy, f"Second init broke health: {report.summary()}"
        assert marker.read_text(encoding="utf-8") == "do not overwrite"


# ---------------------------------------------------------------------------
# TestCanonicalPathsExistence — detailed per-artifact verification
# ---------------------------------------------------------------------------


class TestCanonicalPathsExistence:
    """Verify individual artifacts produced by install_local."""

    @pytest.fixture(autouse=True)
    def _init_workspace(self, tmp_path: Path, agent_dir: Path) -> None:
        install_local(agent_dir, tmp_path)
        self.root = tmp_path

    def test_feedbacks_dir_has_tracker_and_readme(self) -> None:
        fb = self.root / ".local" / "feedbacks"
        assert (fb / "TRACKER.md").is_file()
        assert (fb / "README.md").is_file()
        tracker_content = (fb / "TRACKER.md").read_text(encoding="utf-8")
        assert "Feedback Tracker" in tracker_content

    def test_tasks_dir_has_readme(self) -> None:
        tasks = self.root / ".local" / "tasks"
        assert (tasks / "README.md").is_file()
        readme_content = (tasks / "README.md").read_text(encoding="utf-8")
        assert "tasks/" in readme_content

    def test_memory_dir_has_memory_md_and_readme(self) -> None:
        mem = self.root / ".local" / "memory"
        assert (mem / "MEMORY.md").is_file()
        assert (mem / "README.md").is_file()
        memory_content = (mem / "MEMORY.md").read_text(encoding="utf-8")
        assert "Memory Index" in memory_content

    def test_index_md_lists_subdirs(self) -> None:
        index = self.root / ".local" / "index.md"
        assert index.is_file()
        content = index.read_text(encoding="utf-8")
        assert "feedbacks" in content
        assert "tasks" in content
        assert "memory" in content

    def test_compile_config_is_valid_yaml(self) -> None:
        config = self.root / ".rules" / "compile-config.yaml"
        assert config.is_file()
        parsed = yaml.safe_load(config.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)
        assert "version" in parsed
        assert "layers" in parsed
        assert "targets" in parsed


# ---------------------------------------------------------------------------
# TestPromptOnlyContractSimulation — validate_owned_files dispatch payloads
# ---------------------------------------------------------------------------


class TestPromptOnlyContractSimulation:
    """Simulate dispatch payloads and verify validate_owned_files enforcement.

    This is the regression gate for the v7.4.1/v7.5.0/v7.7.0 bug where
    the L0 Project Agent fabricated incorrect owned_files paths (e.g.
    ``.workflow/config.yaml``, ``.local/project_status.yaml``) instead of
    using the canonical manifest from WORKFLOW_MANIFESTS["repo-init"].
    """

    def test_dispatch_with_canonical_manifest_passes_validation(self) -> None:
        payload = {
            "workflow": "repo-init",
            "owned_files": list(CANONICAL_MANIFEST),
        }
        result = validate_owned_files(payload)
        assert result.passed, f"Canonical manifest should pass: {result.violations}"

    def test_dispatch_with_self_created_paths_fails_validation(self) -> None:
        """The v7.7.0 wrong paths — L0 hallucinated these instead of canonical ones.

        Note: paths must NOT accidentally prefix-match any canonical entry.
        E.g. ``.local/tasks/task_001.yaml`` would cover ``.local/tasks/``
        via _path_covered's startswith check, so we use paths that share
        no prefix with the canonical manifest.
        """
        payload = {
            "workflow": "repo-init",
            "owned_files": [
                ".workflow/config.yaml",
                ".local/project_status.yaml",
                ".local/project_plan.yaml",
                ".devola/settings.json",
                "config/init.yaml",
            ],
        }
        result = validate_owned_files(payload)
        assert not result.passed
        assert len(result.violations) == 1
        violation = result.violations[0]
        assert violation.code == "VOF001"
        assert "missing" in violation.message.lower()
        missing = violation.context["missing_paths"]
        for p in CANONICAL_MANIFEST:
            assert p in missing

    def test_dispatch_missing_single_path_fails(self) -> None:
        incomplete = [p for p in CANONICAL_MANIFEST if p != ".rules/compile-config.yaml"]
        payload = {
            "workflow": "repo-init",
            "owned_files": incomplete,
        }
        result = validate_owned_files(payload)
        assert not result.passed
        assert any(
            ".rules/compile-config.yaml" in v.context.get("missing_paths", [])
            for v in result.violations
        )

    def test_dispatch_with_superset_passes(self) -> None:
        superset = list(CANONICAL_MANIFEST) + [
            "src/main.py",
            "README.md",
            "tests/test_foo.py",
        ]
        payload = {
            "workflow": "repo-init",
            "owned_files": superset,
        }
        result = validate_owned_files(payload)
        assert result.passed, f"Superset should pass: {result.violations}"

    def test_dispatch_non_repo_init_workflow_ignored(self) -> None:
        payload = {
            "workflow": "feature-impl",
            "owned_files": ["whatever.py"],
        }
        result = validate_owned_files(payload)
        assert result.passed

    def test_dispatch_empty_owned_files_for_repo_init_fails(self) -> None:
        payload = {
            "workflow": "repo-init",
            "owned_files": [],
        }
        result = validate_owned_files(payload)
        assert not result.passed
        assert result.violations[0].code == "VOF001"

    def test_dispatch_directory_path_covered_by_child(self) -> None:
        """owned_files containing a child of a manifest directory should pass."""
        owned = []
        for p in CANONICAL_MANIFEST:
            if p.endswith("/"):
                owned.append(p.rstrip("/") + "/README.md")
            else:
                owned.append(p)
        payload = {
            "workflow": "repo-init",
            "owned_files": owned,
        }
        result = validate_owned_files(payload)
        assert result.passed


# ---------------------------------------------------------------------------
# TestStructureContract — full_review_and_improve Track C-2 (R5 F3)
# ---------------------------------------------------------------------------


class TestStructureContract:
    """The scaffold structure contract: single owner, scaffold assertion,
    doctor reuse, and 4-deviation-class detection."""

    def test_expected_scaffold_paths_cover_all_required_dirs(self) -> None:
        """Contract parity with the scaffold's own constants (A-5 owner)."""
        from devolaflow.local.workspace import (
            MEMORY_SUBDIRS,
            REQUIRED_DIRS,
            expected_scaffold_paths,
        )

        contract_paths = {p for p, _ in expected_scaffold_paths()}
        for d in [*REQUIRED_DIRS, *MEMORY_SUBDIRS]:
            assert f".local/{d}/" in contract_paths, f"contract lost dir {d!r}"
        assert ".local/feedbacks/TRACKER.md" in contract_paths
        assert ".local/memory/MEMORY.md" in contract_paths
        assert ".local/index.md" in contract_paths

    def test_doctor_covers_human_surface(self, tmp_path: Path) -> None:
        """The v14.0.0 human surface is now doctor-checked (the pre-C-2
        hand-maintained extras list had drifted and never covered it)."""
        scaffold_local(tmp_path)

        report = check_init_health(tmp_path)
        checked = {f.path for f in report.findings}
        assert ".local/human/input/" in checked
        assert ".local/human/input/README.md" in checked
        human_findings = [f for f in report.findings if f.path.startswith(".local/human/")]
        assert human_findings and all(f.found for f in human_findings)

    @pytest.mark.parametrize(
        ("deviation", "expect_missing", "expect_advisory"),
        [
            ("missing-dir", ".local/human/input/", None),
            ("wrong-name", ".local/feedbacks/", None),
            ("missing-stub", ".local/feedbacks/TRACKER.md", None),
            ("skeleton-break", None, ".local/tasks/README.md"),
        ],
    )
    def test_doctor_detects_injected_deviations(
        self,
        tmp_path: Path,
        deviation: str,
        expect_missing: str | None,
        expect_advisory: str | None,
    ) -> None:
        """The 4 deviation classes from the Track C plan §4: missing dir /
        wrong name / missing stub → blocking; skeleton break → advisory."""
        import shutil

        scaffold_local(tmp_path)
        # Baseline-complete workspace so only the injected deviation shows.
        (tmp_path / ".rules").mkdir()
        (tmp_path / ".rules" / "compile-config.yaml").write_text("version: 1\n")
        assert check_init_health(tmp_path).healthy, "fixture precondition"

        if deviation == "missing-dir":
            shutil.rmtree(tmp_path / ".local" / "human" / "input")
        elif deviation == "wrong-name":
            (tmp_path / ".local" / "feedbacks").rename(tmp_path / ".local" / "feedback")
        elif deviation == "missing-stub":
            (tmp_path / ".local" / "feedbacks" / "TRACKER.md").unlink()
        elif deviation == "skeleton-break":
            readme = tmp_path / ".local" / "tasks" / "README.md"
            readme.write_text("Totally custom content\n", encoding="utf-8")

        report = check_init_health(tmp_path)
        if expect_missing is not None:
            assert not report.healthy
            assert expect_missing in report.missing
        if expect_advisory is not None:
            assert report.healthy, "skeleton drift must stay non-blocking"
            assert expect_advisory in report.advisories

    def test_verify_scaffold_structure_clean_after_scaffold(self, tmp_path: Path) -> None:
        from devolaflow.local.workspace import verify_scaffold_structure

        scaffold_local(tmp_path)

        missing, drifted = verify_scaffold_structure(tmp_path)
        assert missing == []
        assert drifted == []

    def test_scaffold_raises_structure_error_on_gap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """S-5: a scaffold that cannot produce the contracted structure must
        fail loudly with the exact missing paths."""
        from devolaflow.local import workspace as ws

        monkeypatch.setattr(ws, "generate_tracker", lambda _dir: _dir)

        with pytest.raises(ws.ScaffoldStructureError) as excinfo:
            ws.scaffold_local(tmp_path)

        assert ".local/feedbacks/TRACKER.md" in excinfo.value.missing_paths

    def test_install_local_reports_contract_verification(
        self,
        tmp_path: Path,
        agent_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        install_local(agent_dir, tmp_path)

        out = capsys.readouterr().out
        assert "structure contract verified" in out
