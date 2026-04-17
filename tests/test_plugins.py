"""Comprehensive tests for the DevolaFlow plugin registry system.

Covers: models (PluginSpec, PluginStatus), registry (PluginRegistry),
and loader (load_plugin_specs, create_default_registry).
"""

from __future__ import annotations

import dataclasses
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devolaflow.plugins.loader import create_default_registry, load_plugin_specs
from devolaflow.plugins.models import PluginSpec, PluginStatus
from devolaflow.plugins.registry import PluginRegistry, _meets_minimum

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _sample_spec(**overrides: object) -> PluginSpec:
    defaults: dict = {
        "name": "sample",
        "description": "A sample plugin",
        "cli_binary": "sample-cli",
        "version_command": "sample-cli --version",
        "version_regex": r"(\d+\.\d+\.\d+)",
        "install_methods": {"pip": "pip install sample-cli"},
        "capabilities": ["eval", "analyze"],
        "role": "research",
    }
    defaults.update(overrides)
    return PluginSpec(**defaults)


def _mock_proc(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


# ===========================================================================
# models.py — PluginSpec
# ===========================================================================


class TestPluginSpec:
    def test_frozen_dataclass(self) -> None:
        spec = _sample_spec()
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.name = "other"  # type: ignore[misc]

    def test_default_values(self) -> None:
        spec = _sample_spec()
        assert spec.repo_url == ""
        assert spec.min_version is None
        assert spec.skill_install_command is None
        assert spec.stage_mapping == {}
        assert spec.workflows == []
        assert spec.update_command is None
        assert spec.uninstall_command is None

    def test_optional_fields(self) -> None:
        spec = _sample_spec(
            repo_url="https://example.com",
            min_version="2.0.0",
            skill_install_command="sample install",
            stage_mapping={"research": "sample search {query}"},
            workflows=["research-only", "full-pipeline"],
            update_command="sample update",
            uninstall_command="sample uninstall",
        )
        assert spec.repo_url == "https://example.com"
        assert spec.min_version == "2.0.0"
        assert spec.skill_install_command == "sample install"
        assert spec.stage_mapping == {"research": "sample search {query}"}
        assert spec.workflows == ["research-only", "full-pipeline"]
        assert spec.update_command == "sample update"
        assert spec.uninstall_command == "sample uninstall"


# ===========================================================================
# models.py — PluginStatus
# ===========================================================================


class TestPluginStatus:
    def test_default_values(self) -> None:
        status = PluginStatus(name="test")
        assert status.name == "test"
        assert status.available is False
        assert status.version is None
        assert status.path is None
        assert status.meets_min_version is True
        assert status.capabilities == []

    def test_mutable(self) -> None:
        status = PluginStatus(name="test")
        status.available = True
        status.version = "1.0.0"
        assert status.available is True
        assert status.version == "1.0.0"


# ===========================================================================
# registry.py — PluginRegistry
# ===========================================================================


class TestPluginRegistry:
    def test_register_and_get(self) -> None:
        reg = PluginRegistry()
        spec = _sample_spec()
        reg.register(spec)
        assert reg.get("sample") is spec

    def test_register_duplicate_overwrites(self) -> None:
        reg = PluginRegistry()
        spec1 = _sample_spec(description="first")
        spec2 = _sample_spec(description="second")
        reg.register(spec1)
        reg.register(spec2)
        assert reg.get("sample") is spec2
        assert reg.get("sample").description == "second"

    def test_unregister(self) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec())
        reg.unregister("sample")
        assert reg.get("sample") is None

    def test_unregister_missing_noop(self) -> None:
        reg = PluginRegistry()
        reg.unregister("nonexistent")

    def test_list_plugins(self) -> None:
        reg = PluginRegistry()
        s1 = _sample_spec(name="a")
        s2 = _sample_spec(name="b")
        reg.register(s1)
        reg.register(s2)
        listed = reg.list_plugins()
        assert len(listed) == 2
        assert {s.name for s in listed} == {"a", "b"}

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_detect_available(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="sample-cli 1.2.3")
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.detect("sample")
        assert status.available is True
        assert status.version == "1.2.3"
        assert status.path == "/usr/bin/sample-cli"
        assert status.capabilities == ["eval", "analyze"]

    @patch("devolaflow.plugins.registry.shutil.which", return_value=None)
    def test_detect_not_on_path(self, _which: MagicMock) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.detect("sample")
        assert status.available is False
        assert status.version is None
        assert status.path is None

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_detect_version_parse(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="version 3.14.159")
        reg = PluginRegistry()
        reg.register(_sample_spec(version_regex=r"version\s+(\d+\.\d+\.\d+)"))
        status = reg.detect("sample")
        assert status.version == "3.14.159"

    @patch(
        "devolaflow.plugins.registry.subprocess.run",
        side_effect=subprocess.TimeoutExpired("sample-cli", 30),
    )
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_detect_subprocess_timeout(self, _which: MagicMock, _run: MagicMock) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.detect("sample")
        assert status.available is True
        assert status.version is None
        assert status.path == "/usr/bin/sample-cli"

    @patch(
        "devolaflow.plugins.registry.subprocess.run",
        side_effect=OSError("exec failed"),
    )
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_detect_oserror(self, _which: MagicMock, _run: MagicMock) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.detect("sample")
        assert status.available is True
        assert status.version is None

    def test_detect_unregistered_plugin(self) -> None:
        reg = PluginRegistry()
        status = reg.detect("unknown")
        assert status.available is False
        assert status.name == "unknown"

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_detect_all(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="sample-cli 1.0.0")
        reg = PluginRegistry()
        reg.register(_sample_spec(name="a"))
        reg.register(_sample_spec(name="b"))
        all_status = reg.detect_all()
        assert set(all_status.keys()) == {"a", "b"}
        assert all(s.available for s in all_status.values())

    # ── ensure ──

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_ensure_already_available(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="sample-cli 1.0.0")
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.ensure("sample", auto_install=True)
        assert status.available is True

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which")
    def test_ensure_auto_install_success(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_which.side_effect = [None, "/usr/bin/sample-cli"]
        mock_run.side_effect = [
            _mock_proc(),  # install command
            _mock_proc(stdout="sample-cli 1.0.0"),  # version probe after re-detect
        ]
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.ensure("sample", auto_install=True, method="pip")
        assert status.available is True

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value=None)
    def test_ensure_auto_install_failure(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(returncode=1, stderr="install failed")
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.ensure("sample", auto_install=True, method="pip")
        assert status.available is False

    @patch("devolaflow.plugins.registry.shutil.which", return_value=None)
    def test_ensure_no_install(self, _which: MagicMock) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.ensure("sample", auto_install=False)
        assert status.available is False

    # ── upgrade ──

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_upgrade_success(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.side_effect = [
            _mock_proc(),  # upgrade shell command
            _mock_proc(stdout="sample-cli 2.0.0"),  # version probe after re-detect
        ]
        reg = PluginRegistry()
        reg.register(_sample_spec())
        status = reg.upgrade("sample", method="pip")
        assert status.available is True

    # ── capability / role queries ──

    def test_get_by_role(self) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec(name="a", role="research"))
        reg.register(_sample_spec(name="b", role="ui"))
        reg.register(_sample_spec(name="c", role="research"))
        results = reg.get_by_role("research")
        assert len(results) == 2
        assert {s.name for s in results} == {"a", "c"}

    def test_get_by_role_empty(self) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec(role="research"))
        assert reg.get_by_role("ui") == []

    def test_get_by_capability(self) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec(name="a", capabilities=["eval", "analyze"]))
        reg.register(_sample_spec(name="b", capabilities=["generate"]))
        results = reg.get_by_capability("eval")
        assert len(results) == 1
        assert results[0].name == "a"

    def test_get_by_capability_empty(self) -> None:
        reg = PluginRegistry()
        reg.register(_sample_spec(capabilities=["eval"]))
        assert reg.get_by_capability("deploy") == []

    # ── min_version checks (via detect) ──

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_min_version_check_pass(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="sample-cli 2.0.0")
        reg = PluginRegistry()
        reg.register(_sample_spec(min_version="1.0.0"))
        status = reg.detect("sample")
        assert status.meets_min_version is True

    @patch("devolaflow.plugins.registry.subprocess.run")
    @patch("devolaflow.plugins.registry.shutil.which", return_value="/usr/bin/sample-cli")
    def test_min_version_check_fail(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = _mock_proc(stdout="sample-cli 0.9.0")
        reg = PluginRegistry()
        reg.register(_sample_spec(min_version="1.0.0"))
        status = reg.detect("sample")
        assert status.meets_min_version is False


class TestMeetsMinimum:
    def test_equal_versions(self) -> None:
        assert _meets_minimum("1.0.0", "1.0.0") is True

    def test_greater_version(self) -> None:
        assert _meets_minimum("2.0.0", "1.0.0") is True

    def test_lesser_version(self) -> None:
        assert _meets_minimum("0.9.0", "1.0.0") is False

    def test_prerelease_suffix(self) -> None:
        assert _meets_minimum("2.0.0-rc1", "1.0.0") is True


# ===========================================================================
# loader.py — load_plugin_specs
# ===========================================================================


class TestLoadPluginSpecs:
    def test_load_from_yaml(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            plugins:
              test-plugin:
                description: "Test plugin"
                cli_binary: "test-cli"
                version_command: "test-cli --version"
                version_regex: '(\\d+\\.\\d+\\.\\d+)'
                install_methods:
                  pip: "pip install test-cli"
                capabilities:
                  - eval
                role: "testing"
        """)
        yaml_file = tmp_path / "plugins.yaml"
        yaml_file.write_text(yaml_content)
        specs = load_plugin_specs(yaml_file)
        assert len(specs) == 1
        assert specs[0].name == "test-plugin"
        assert specs[0].cli_binary == "test-cli"
        assert specs[0].role == "testing"

    def test_load_from_yaml_list_format(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            plugins:
              - name: list-plugin
                description: "List format plugin"
                cli_binary: "list-cli"
                version_command: "list-cli --version"
                version_regex: '(\\d+\\.\\d+\\.\\d+)'
                install_methods: {}
                capabilities: []
                role: "test"
        """)
        yaml_file = tmp_path / "plugins.yaml"
        yaml_file.write_text(yaml_content)
        specs = load_plugin_specs(yaml_file)
        assert len(specs) == 1
        assert specs[0].name == "list-plugin"

    def test_load_empty_file(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        specs = load_plugin_specs(yaml_file)
        assert specs == []

    def test_load_missing_file(self, tmp_path: Path) -> None:
        specs = load_plugin_specs(tmp_path / "nonexistent.yaml")
        assert specs == []


# ===========================================================================
# loader.py — create_default_registry
# ===========================================================================


_REPO_ROOT = Path(__file__).resolve().parent.parent
_REPO_PLUGINS_YAML = _REPO_ROOT / "workflow-system" / "agent" / "plugins.yaml"


class TestCreateDefaultRegistry:
    """Exercise ``create_default_registry``.

    ``plugins.yaml`` is the canonical plugin catalog (v6.0.1+); the legacy
    ``_BUILTIN_SPECS`` table was removed in favor of a single YAML source of
    truth. These tests load the real repo YAML so regressions in the catalog
    (missing plugins, bad command strings) fail here.
    """

    def test_creates_registry_from_repo_yaml(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        nines = reg.get("nines")
        assert nines is not None
        assert nines.cli_binary == "nines"
        ui = reg.get("ui-ux-pro-max")
        assert ui is not None
        assert ui.cli_binary == "uipro"

    def test_repo_yaml_nines_pip_install_command(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        nines = reg.get("nines")
        assert nines is not None
        expected = "uv pip install git+https://github.com/YoRHa-Agents/NineS.git"
        assert nines.install_methods["pip"] == expected

    def test_repo_yaml_nines_role_and_version(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        nines = reg.get("nines")
        assert nines is not None
        assert nines.role == "research_and_iteration"
        assert nines.min_version == "1.0.0"

    def test_repo_yaml_nines_capabilities(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        nines = reg.get("nines")
        assert nines is not None
        assert nines.capabilities, "nines plugin should declare capabilities"

    def test_repo_yaml_nines_stage_mapping_and_workflows(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        nines = reg.get("nines")
        assert nines is not None
        assert "research" in nines.stage_mapping
        assert "analyze" in nines.stage_mapping
        assert nines.workflows == ["research-only", "skill-optimization", "self-update"]

    def test_auto_discovers_repo_yaml_when_no_arg(self) -> None:
        reg = create_default_registry()
        assert reg.get("nines") is not None
        assert reg.get("ui-ux-pro-max") is not None

    def test_loads_from_yaml_when_explicit(self, tmp_path: Path) -> None:
        yaml_content = textwrap.dedent("""\
            plugins:
              extra-tool:
                description: "Extra plugin"
                cli_binary: "extra"
                version_command: "extra --version"
                version_regex: '(\\d+\\.\\d+\\.\\d+)'
                install_methods: {}
                capabilities: []
                role: "extra"
        """)
        yaml_file = tmp_path / "plugins.yaml"
        yaml_file.write_text(yaml_content)
        reg = create_default_registry(plugins_yaml=yaml_file)
        # Only plugins from the explicit YAML are registered (no implicit merge
        # with _BUILTIN_SPECS — it no longer exists).
        assert reg.get("extra-tool") is not None
        assert reg.get("nines") is None
        assert reg.get("ui-ux-pro-max") is None

    def test_emergency_stub_when_yaml_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Force auto-discovery to find nothing by cd'ing into an empty dir and
        # patching the package-relative search to also fail.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("devolaflow.plugins.loader._find_repo_plugins_yaml", lambda: None)
        import logging as _logging

        with caplog.at_level(_logging.WARNING, logger="devolaflow.plugins.loader"):
            reg = create_default_registry()
        # Emergency stub provides a minimal NineS entry so detection still works.
        nines = reg.get("nines")
        assert nines is not None
        assert nines.cli_binary == "nines"
        assert "pip" in nines.install_methods
        assert reg.get("ui-ux-pro-max") is None
        assert any("plugins.yaml not found" in rec.message for rec in caplog.records)

    def test_explicit_missing_path_falls_back_to_stub(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When caller explicitly passes a non-existent path, we do NOT silently
        # auto-discover the repo YAML — we fall through to the emergency stub
        # so the caller's intent is preserved.
        monkeypatch.setattr("devolaflow.plugins.loader._find_repo_plugins_yaml", lambda: None)
        reg = create_default_registry(plugins_yaml=tmp_path / "nope.yaml")
        assert reg.get("nines") is not None
        assert reg.get("ui-ux-pro-max") is None
