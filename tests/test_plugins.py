"""Comprehensive tests for the DevolaFlow plugin registry system.

Covers: models (PluginSpec, PluginStatus), registry (PluginRegistry),
and loader (load_plugin_specs, create_default_registry).
"""

from __future__ import annotations

import dataclasses
import json
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

    ``plugins.yaml`` is the derived capability view of the A-5 SSOT owner
    ``knowledge/runtime-plugins.yaml`` (v15.0.0 G-021; pre-v15 it was the
    standalone "canonical plugin catalog"). The legacy ``_BUILTIN_SPECS``
    table was removed in v6.0.1 in favor of a single YAML source. These
    tests load the real repo YAML so regressions in the view (missing
    plugins, bad command strings) fail here.
    """

    def test_creates_registry_from_repo_yaml(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        ui = reg.get("ui-pro")
        assert ui is not None
        assert ui.cli_binary == "uipro"

    def test_auto_discovers_repo_yaml_when_no_arg(self) -> None:
        reg = create_default_registry()
        assert reg.get("ui-pro") is not None
        assert len(reg.list_plugins()) == 3

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
        assert reg.get("ui-pro") is None

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
        assert reg.list_plugins() == []
        assert any("plugins.yaml not found" in rec.message for rec in caplog.records)

    def test_explicit_missing_path_falls_back_to_stub(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When caller explicitly passes a non-existent path, we do NOT silently
        # auto-discover the repo YAML — return an empty registry so the
        # caller's explicit path intent is preserved.
        monkeypatch.setattr("devolaflow.plugins.loader._find_repo_plugins_yaml", lambda: None)
        reg = create_default_registry(plugins_yaml=tmp_path / "nope.yaml")
        assert reg.list_plugins() == []


# ===========================================================================
# v8.2.1 — Plugin Runtime Auto-Install (new public surface)
# ---------------------------------------------------------------------------
# Design ref: .local/research/v8.3.0_design.md §6
# Closes gap H-001 from .local/research/v8.3.0_gap_analysis.md
#
# Coverage targets:
#   AC-3  runtime-plugins.yaml schema validates
#   AC-4  precondition stage is first in both workflow YAMLs
#   AC-8  8 failure-mode scenarios from design.md §6.5 — all mocked subprocess
#   AC-9  ui-pro per-target init failure raises PluginInstallError loudly
# ===========================================================================

from devolaflow.plugins import (  # noqa: E402 — grouped with v8.2.1 suite
    PluginBackendUnsupported,
    PluginInstallError,
    PluginNotFoundError,
    PluginVersionMismatch,
    RuntimePluginSpec,
    ensure_plugin,
    load_registry,
    resolve_plugin,
)
from devolaflow.plugins import installer as _installer_mod  # noqa: E402

_REPO_ROOT_V821 = Path(__file__).resolve().parent.parent
_RUNTIME_PLUGINS_YAML = (
    _REPO_ROOT_V821 / "workflow-system" / "agent" / "knowledge" / "runtime-plugins.yaml"
)


def _mock_completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


def _write_runtime_registry(
    tmp_path: Path,
    *,
    nines_local_fallback: str | None = None,
    extra_plugin_yaml: str = "",
    schema_version: int = 1,
) -> Path:
    """Write a minimal runtime-plugins.yaml into ``tmp_path`` and return the path.

    ``extra_plugin_yaml`` is inserted into the top-level ``plugins:`` list —
    caller MUST pre-indent each row so it aligns with ``  - id: nines`` (two
    leading spaces). The helper does not re-indent.
    """
    local_fallback_repr = "null" if nines_local_fallback is None else f'"{nines_local_fallback}"'
    base_plugins = textwrap.dedent(
        f"""\
        schema_version: {schema_version}
        last_updated: "2026-04-22"

        plugins:
          - id: nines
            backend: pip
            package: nines
            install_cmd: "pip install --upgrade nines"
            version_check_cmd: "nines --version"
            min_version: "3.0.0"
            expected_sha256: null
            canonical_url: "https://example.com/nines-fixture"
            local_fallback_path: {local_fallback_repr}
            invoked_by_workflows:
              - nines-assisted

          - id: ui-pro
            backend: npm_then_init
            package: uipro-cli
            install_cmd: "npm install -g uipro-cli"
            init_cmd_template: "uipro init --ai {{ai_platform}} --global"
            init_targets:
              - cursor
              - claude
              - codex
            version_check_cmd: "uipro --version"
            min_version: "2.0.0"
            expected_sha256: null
            canonical_url: "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"
            local_fallback_path: null
            invoked_by_workflows:
              - product-verification
        """
    )
    tail = textwrap.dedent(
        f"""\

        defaults:
          auto_install: true
          prefer_local_fallback: true
          network_timeout_seconds: 90
          install_log_path: "{tmp_path / "plugin_install.log"}"

        backends:
          - id: pip
            description: "Python package manager"
          - id: npm_then_init
            description: "npm install + per-AI init"
        """
    )
    content = base_plugins + extra_plugin_yaml + tail
    registry_file = tmp_path / "runtime-plugins.yaml"
    registry_file.write_text(content)
    return registry_file


# ---------------------------------------------------------------------------
# AC-3: runtime-plugins.yaml schema validates
# ---------------------------------------------------------------------------


class TestRuntimePluginsYamlContract:
    """Verify the canonical registry at workflow-system/agent/knowledge/runtime-plugins.yaml."""

    def test_registry_yaml_loads(self) -> None:
        raw = load_registry(_RUNTIME_PLUGINS_YAML)
        # schema_version history:
        #   v1 (v8.2.1) — initial registry schema
        #   v2 (v8.3.1 PV-01) — curl_install_script backend
        #   v3 (v9.4.0 PV-04) — upgrade_cmd + upgrade_check_frequency_hours
        #   v4 (v15.2.0 B-6) — tier: require|suggest + auto_install default flip
        # v1..v3 entries continue to load via _SUPPORTED_SCHEMA_VERSIONS.
        assert raw["schema_version"] == 4
        assert isinstance(raw["plugins"], list)
        assert len(raw["plugins"]) == 3

    def test_registry_contains_ui_pro_npm_then_init(self) -> None:
        registry = load_registry(_RUNTIME_PLUGINS_YAML)
        spec = resolve_plugin("ui-pro", registry)
        assert spec.backend == "npm_then_init"
        assert spec.package == "uipro-cli"
        assert spec.install_cmd == "npm install -g uipro-cli"
        assert spec.init_cmd_template == "uipro init --ai {ai_platform} --global"
        assert spec.init_targets == ["cursor", "claude", "codex"]
        assert spec.canonical_url == "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"

    def test_registry_defaults_honour_schema(self) -> None:
        raw = load_registry(_RUNTIME_PLUGINS_YAML)
        defaults = raw["defaults"]
        # v15.2.0 B-6 — flipped true → false: the default path is
        # probe + suggest; explicit opt-in surfaces pass auto_install=True.
        assert defaults["auto_install"] is False
        assert defaults["prefer_local_fallback"] is True
        assert defaults["network_timeout_seconds"] >= 60
        assert defaults["install_log_path"].startswith(".local/")


# ---------------------------------------------------------------------------
# AC-4: precondition stage wiring in workflow templates
# ---------------------------------------------------------------------------


class TestWorkflowPreconditionWiring:
    """Assert plugin ownership and seed provenance survive registry v3."""

    @staticmethod
    def _load_template(rel_path: str) -> dict:
        import yaml as _yaml

        path = _REPO_ROOT_V821 / rel_path
        return _yaml.safe_load(path.read_text())

    def test_nines_assisted_precondition_stage_first(self) -> None:
        """The opaque historical seed remains available without plugin wiring."""
        from devolaflow.template_engine.registry import TemplateRegistry

        registry = TemplateRegistry(_REPO_ROOT_V821 / "workflow-system/agent/templates")
        seed = registry.load_seed("nines-assisted")
        assert seed is not None
        assert ("precondition", "implement") in seed.source_stage_sequence()
        assert not hasattr(seed, "composition")

    def test_product_verification_precondition_carried_by_composition(self) -> None:
        """Product-verification retains precondition provenance only."""
        from devolaflow.template_engine.registry import TemplateRegistry

        registry = TemplateRegistry(_REPO_ROOT_V821 / "workflow-system/agent/templates")
        seed = registry.load_seed("product-verification")
        assert seed is not None
        assert ("precondition", "implement") in seed.source_stage_sequence()
        assert not hasattr(seed, "composition")

        plugin = resolve_plugin("ui-pro", load_registry(_RUNTIME_PLUGINS_YAML))
        assert "product-verification" in plugin.invoked_by_workflows


# ---------------------------------------------------------------------------
# Registry loader + resolver unit tests
# ---------------------------------------------------------------------------


class TestLoadRegistry:
    def test_load_registry_parses_tmp_path_yaml(self, tmp_path: Path) -> None:
        path = _write_runtime_registry(tmp_path)
        raw = load_registry(path)
        assert raw["schema_version"] == 1
        assert {p["id"] for p in raw["plugins"]} == {"nines", "ui-pro"}

    def test_load_registry_missing_file_raises_filenotfound(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_registry(tmp_path / "missing.yaml")

    def test_load_registry_malformed_yaml_raises_plugininstallerror(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(":::not valid yaml:::\n- [")
        with pytest.raises(PluginInstallError) as exc:
            load_registry(bad)
        assert "Failed to parse" in str(exc.value)

    def test_load_registry_wrong_schema_version_raises(self, tmp_path: Path) -> None:
        path = _write_runtime_registry(tmp_path, schema_version=99)
        with pytest.raises(PluginInstallError) as exc:
            load_registry(path)
        assert "schema_version" in str(exc.value)

    def test_load_registry_non_mapping_top_level_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "list.yaml"
        bad.write_text("- a\n- b\n")
        with pytest.raises(PluginInstallError) as exc:
            load_registry(bad)
        assert "mapping" in str(exc.value)


class TestResolvePlugin:
    def test_resolve_found_returns_spec(self, tmp_path: Path) -> None:
        registry = load_registry(_write_runtime_registry(tmp_path))
        spec = resolve_plugin("nines", registry)
        assert isinstance(spec, RuntimePluginSpec)
        assert spec.id == "nines"
        assert spec.backend == "pip"

    def test_resolve_missing_id_raises_pluginnotfounderror(self, tmp_path: Path) -> None:
        registry = load_registry(_write_runtime_registry(tmp_path))
        with pytest.raises(PluginNotFoundError) as exc:
            resolve_plugin("does-not-exist", registry)
        assert "does-not-exist" in str(exc.value)

    def test_resolve_unsupported_backend_raises(self, tmp_path: Path) -> None:
        # Pre-indented so it lands inside the `plugins:` list (see helper docstring).
        extra = (
            "  - id: weird\n"
            "    backend: pyinstaller\n"
            "    package: weirdtool\n"
            '    install_cmd: "weird install"\n'
            '    version_check_cmd: "weird --version"\n'
            '    min_version: "1.0.0"\n'
            "    expected_sha256: null\n"
            '    canonical_url: "https://example.com"\n'
        )
        registry = load_registry(_write_runtime_registry(tmp_path, extra_plugin_yaml=extra))
        with pytest.raises(PluginBackendUnsupported):
            resolve_plugin("weird", registry)

    def test_resolve_npm_backend_missing_init_targets_raises(self, tmp_path: Path) -> None:
        extra = (
            "  - id: halfbaked\n"
            "    backend: npm_then_init\n"
            "    package: halfbaked\n"
            '    install_cmd: "npm install -g halfbaked"\n'
            '    init_cmd_template: "halfbaked init {ai_platform}"\n'
            '    version_check_cmd: "halfbaked --version"\n'
            '    min_version: "1.0.0"\n'
            "    expected_sha256: null\n"
            '    canonical_url: "https://example.com"\n'
        )
        registry = load_registry(_write_runtime_registry(tmp_path, extra_plugin_yaml=extra))
        with pytest.raises(PluginInstallError) as exc:
            resolve_plugin("halfbaked", registry)
        assert "init_targets" in str(exc.value)


# ---------------------------------------------------------------------------
# AC-8: 8 failure-mode scenarios from design.md §6.5
# ---------------------------------------------------------------------------


class TestEnsurePluginFailureModes:
    """Each test corresponds to one row in design.md §6.5.

    All subprocess calls mocked via ``unittest.mock.patch`` so no real
    ``pip install`` / ``npm install`` runs. This is the AC-8 contract.
    """

    # ── Scenario 1: plugin already installed at >= min_version ──────────

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_1_already_installed_returns_version_no_install(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = _mock_completed(stdout="nines, version 3.3.0")
        registry_path = _write_runtime_registry(tmp_path)
        version = ensure_plugin("nines", registry_path=registry_path)
        assert version == "3.3.0"
        # Only the version probe ran — no install command
        assert mock_run.call_count == 1
        invoked_cmd = mock_run.call_args.args[0]
        assert "nines --version" in " ".join(invoked_cmd)

    # ── Scenario 2: plugin missing, auto_install=true, network OK ───────

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_2_missing_auto_install_succeeds(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(stdout="", returncode=1),  # pre-install probe fails
            _mock_completed(stdout="Successfully installed nines-3.3.0"),  # install
            _mock_completed(stdout="nines, version 3.3.0"),  # post-install probe
        ]
        registry_path = _write_runtime_registry(tmp_path)
        version = ensure_plugin("nines", registry_path=registry_path)
        assert version == "3.3.0"
        assert mock_run.call_count == 3
        install_cmd = " ".join(mock_run.call_args_list[1].args[0])
        assert "pip install --upgrade nines" in install_cmd

    # ── Scenario 3: plugin missing, auto_install=false ──────────────────

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_3_auto_install_disabled_raises_versionmismatch(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = _mock_completed(stdout="", returncode=1)
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginVersionMismatch) as exc:
            ensure_plugin("nines", registry_path=registry_path, auto_install=False)
        assert "auto_install=False" in str(exc.value)
        # No install command should have been attempted
        assert mock_run.call_count == 1  # only the version probe

    # ── Scenario 4: network unreachable, local_fallback_path set ────────

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_4_local_fallback_used_when_network_unreachable(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        fake_local = tmp_path / "nines_editable"
        fake_local.mkdir()
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe fails
            _mock_completed(stdout="Installing from local..."),  # local install
            _mock_completed(stdout="nines, version 3.3.0"),  # post-install probe
        ]
        registry_path = _write_runtime_registry(tmp_path, nines_local_fallback=str(fake_local))
        version = ensure_plugin("nines", registry_path=registry_path)
        assert version == "3.3.0"
        # Assert the install command was `pip install -e <fake_local>` and NOT
        # the remote `pip install --upgrade nines` path.
        install_call = " ".join(mock_run.call_args_list[1].args[0])
        assert f"pip install -e {fake_local}" in install_call
        assert "pip install --upgrade nines" not in install_call

    # ── Scenario 5: network unreachable, no local fallback ──────────────

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_5_network_unreachable_no_fallback_raises(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe fails
            _mock_completed(
                returncode=1,
                stderr="ERROR: Could not fetch URL (network unreachable)",
            ),
        ]
        registry_path = _write_runtime_registry(tmp_path)  # local_fallback_path=null
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("nines", registry_path=registry_path)
        assert "pip install failed" in str(exc.value)
        assert "network unreachable" in str(exc.value)

    # ── Scenario 6: install succeeds but version < min_version ──────────

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_6_version_mismatch_post_install_raises(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe fails
            _mock_completed(stdout="Successfully installed nines-2.5.0"),  # install
            _mock_completed(stdout="nines, version 2.5.0"),  # post probe, too old
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginVersionMismatch) as exc:
            ensure_plugin("nines", registry_path=registry_path)
        assert "2.5.0" in str(exc.value)
        assert "3.0.0" in str(exc.value)

    # ── Scenario 7: expected_sha256 set and post-install hash mismatches ──
    # Note: the current v8.2.1 _verify_sha256() is best-effort; see design.md
    # §6 "expected_sha256" implementation hint. We cover the skeleton by
    # simulating a raise from _verify_sha256 via monkeypatch and asserting
    # the expected uninstall+raise flow. Full per-artifact hashing ships in a
    # follow-up patch.

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_7_sha_mismatch_uninstalls_and_raises(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe
            _mock_completed(stdout="Successfully installed nines-3.3.0"),  # install
            _mock_completed(stdout="nines, version 3.3.0"),  # post-install probe
            _mock_completed(stdout="Successfully uninstalled nines-3.3.0"),  # uninstall
        ]

        def _fake_sha_check(spec: RuntimePluginSpec) -> None:
            raise PluginInstallError(
                "Plugin sha mismatch (simulated)",
                details={"plugin_id": spec.id, "expected_sha256": "deadbeef"},
            )

        monkeypatch.setattr(_installer_mod, "_verify_sha256", _fake_sha_check)
        monkeypatch.setattr(
            _installer_mod.shutil, "which", lambda name: "/usr/bin/pip" if name == "pip" else None
        )

        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("nines", registry_path=registry_path)
        assert "sha mismatch" in str(exc.value)
        # Verify uninstall attempted
        uninstall_cmd = " ".join(mock_run.call_args_list[-1].args[0])
        assert "pip uninstall -y nines" in uninstall_cmd

    # ── Scenario 8: subprocess timeout ──────────────────────────────────

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_scenario_8_install_timeout_raises(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe
            subprocess.TimeoutExpired(cmd="pip install", timeout=90),
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("nines", registry_path=registry_path)
        assert "timeout" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# AC-9: npm_then_init backend — per-target init failure raises loudly
# ---------------------------------------------------------------------------


class TestEnsurePluginNpmBackend:
    """Coverage for the ui-pro 2-step npm install + per-AI init flow."""

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_then_init_success_for_all_targets(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe fails
            _mock_completed(stdout="added 1 package"),  # npm install
            _mock_completed(stdout="cursor initialized"),  # init cursor
            _mock_completed(stdout="claude initialized"),  # init claude
            _mock_completed(stdout="codex initialized"),  # init codex
            _mock_completed(stdout="uipro-cli/2.1.0"),  # post-install probe
        ]
        registry_path = _write_runtime_registry(tmp_path)
        version = ensure_plugin("ui-pro", registry_path=registry_path)
        assert version == "2.1.0"
        # Confirm each init target invoked with correct {ai_platform}
        cmds = [" ".join(c.args[0]) for c in mock_run.call_args_list]
        assert any("uipro init --ai cursor --global" in c for c in cmds)
        assert any("uipro init --ai claude --global" in c for c in cmds)
        assert any("uipro init --ai codex --global" in c for c in cmds)

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_then_init_one_target_fails_raises_loudly(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe fails
            _mock_completed(stdout="added 1 package"),  # npm install OK
            _mock_completed(stdout="cursor initialized"),  # cursor OK
            _mock_completed(returncode=1, stderr="claude init: permission denied"),  # claude FAILS
            _mock_completed(stdout="codex initialized"),  # codex OK
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("ui-pro", registry_path=registry_path)
        assert "claude" in str(exc.value)
        assert "failed_targets" in exc.value.details
        failed = exc.value.details["failed_targets"]
        assert len(failed) == 1
        assert failed[0]["ai_platform"] == "claude"

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_then_init_multiple_targets_fail_all_reported(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe fails
            _mock_completed(stdout="added 1 package"),  # npm install
            _mock_completed(returncode=1, stderr="cursor init broke"),  # cursor FAIL
            _mock_completed(returncode=1, stderr="claude init broke"),  # claude FAIL
            _mock_completed(stdout="codex initialized"),  # codex OK
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("ui-pro", registry_path=registry_path)
        failed = exc.value.details["failed_targets"]
        assert {entry["ai_platform"] for entry in failed} == {"cursor", "claude"}

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_install_failure_raises_before_init(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe
            _mock_completed(returncode=1, stderr="npm ERR! permission denied"),  # npm FAILS
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("ui-pro", registry_path=registry_path)
        assert "npm install failed" in str(exc.value)

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_init_timeout_on_single_target_captured(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe
            _mock_completed(stdout="added 1 package"),  # npm install
            _mock_completed(stdout="cursor initialized"),
            subprocess.TimeoutExpired(cmd="uipro init", timeout=90),
            _mock_completed(stdout="codex initialized"),
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("ui-pro", registry_path=registry_path)
        failed = exc.value.details["failed_targets"]
        assert failed[0]["ai_platform"] == "claude"
        assert "timeout" in failed[0]["reason"].lower()


# ---------------------------------------------------------------------------
# Version parsing / comparison helpers
# ---------------------------------------------------------------------------


class TestVersionParsing:
    def test_parse_dotted_triplet(self) -> None:
        assert _installer_mod._parse_version("nines, version 3.3.0") == "3.3.0"

    def test_parse_uipro_slash_format(self) -> None:
        assert _installer_mod._parse_version("uipro-cli/2.1.0") == "2.1.0"

    def test_parse_two_component_version(self) -> None:
        assert _installer_mod._parse_version("tool v1.5 released") == "1.5"

    def test_parse_empty_returns_none(self) -> None:
        assert _installer_mod._parse_version("") is None

    def test_parse_no_version_returns_none(self) -> None:
        assert _installer_mod._parse_version("no version here") is None

    def test_meets_min_equal(self) -> None:
        assert _installer_mod._meets_min("3.0.0", "3.0.0") is True

    def test_meets_min_greater(self) -> None:
        assert _installer_mod._meets_min("3.3.0", "3.0.0") is True

    def test_meets_min_lesser(self) -> None:
        assert _installer_mod._meets_min("2.9.9", "3.0.0") is False


# ---------------------------------------------------------------------------
# Install log (JSONL event journal)
# ---------------------------------------------------------------------------


class TestInstallLog:
    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_success_writes_plugin_installed_event(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),
            _mock_completed(stdout="Successfully installed nines-3.3.0"),
            _mock_completed(stdout="nines, version 3.3.0"),
        ]
        log_file = tmp_path / "install.log"
        registry_path = _write_runtime_registry(tmp_path)
        ensure_plugin("nines", registry_path=registry_path, log_path=log_file)
        assert log_file.is_file()
        events = [json.loads(line) for line in log_file.read_text().splitlines() if line]
        kinds = [e["event"] for e in events]
        assert "plugin_installed" in kinds

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_failure_writes_plugin_install_failed_event(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),
            _mock_completed(returncode=1, stderr="pip broke"),
        ]
        log_file = tmp_path / "install.log"
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError):
            ensure_plugin("nines", registry_path=registry_path, log_path=log_file)
        events = [json.loads(line) for line in log_file.read_text().splitlines() if line]
        assert any(e["event"] == "plugin_install_failed" for e in events)

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_already_installed_writes_plugin_already_installed_event(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = _mock_completed(stdout="nines, version 3.3.0")
        log_file = tmp_path / "install.log"
        registry_path = _write_runtime_registry(tmp_path)
        ensure_plugin("nines", registry_path=registry_path, log_path=log_file)
        events = [json.loads(line) for line in log_file.read_text().splitlines() if line]
        kinds = [e["event"] for e in events]
        assert "plugin_already_installed" in kinds


# ---------------------------------------------------------------------------
# Additional edge-case coverage for installer.py branches
# ---------------------------------------------------------------------------


class TestInstallerEdgeCases:
    """Cover the defensive branches not exercised by the 8 main scenarios."""

    def test_resolve_plugin_missing_required_keys_raises(self, tmp_path: Path) -> None:
        extra = (
            "  - id: partial\n"
            "    backend: pip\n"
            '    package: ""\n'  # empty package triggers required-keys check
            '    install_cmd: "pip install partial"\n'
            '    version_check_cmd: "partial --version"\n'
            '    min_version: "1.0.0"\n'
            "    expected_sha256: null\n"
            '    canonical_url: "https://example.com"\n'
        )
        registry = load_registry(_write_runtime_registry(tmp_path, extra_plugin_yaml=extra))
        with pytest.raises(PluginInstallError) as exc:
            resolve_plugin("partial", registry)
        assert "missing required keys" in str(exc.value)

    def test_resolve_plugin_npm_backend_missing_init_cmd_template_raises(
        self, tmp_path: Path
    ) -> None:
        extra = (
            "  - id: bareinit\n"
            "    backend: npm_then_init\n"
            "    package: bareinit\n"
            '    install_cmd: "npm install -g bareinit"\n'
            "    init_targets: [cursor]\n"
            '    version_check_cmd: "bareinit --version"\n'
            '    min_version: "1.0.0"\n'
            "    expected_sha256: null\n"
            '    canonical_url: "https://example.com"\n'
        )
        registry = load_registry(_write_runtime_registry(tmp_path, extra_plugin_yaml=extra))
        with pytest.raises(PluginInstallError) as exc:
            resolve_plugin("bareinit", registry)
        assert "init_cmd_template" in str(exc.value)

    def test_resolve_plugin_skips_non_dict_entries(self, tmp_path: Path) -> None:
        # Hand-craft a registry with a list entry interleaved with dicts to
        # exercise the ``isinstance(entry, dict)`` continue branch.
        bad = tmp_path / "mixed.yaml"
        bad.write_text(
            textwrap.dedent(
                """\
                schema_version: 1
                plugins:
                  - "not a dict"
                  - id: okay
                    backend: pip
                    package: okay
                    install_cmd: "pip install okay"
                    version_check_cmd: "okay --version"
                    min_version: "1.0.0"
                    canonical_url: "https://example.com"
                """
            )
        )
        registry = load_registry(bad)
        spec = resolve_plugin("okay", registry)
        assert spec.id == "okay"

    def test_load_defaults_with_non_dict_defaults_uses_fallbacks(self, tmp_path: Path) -> None:
        # ``defaults:`` is a list → _load_defaults coerces to {} and returns
        # all fallback values; ensure_plugin still works.
        bad = tmp_path / "baddefaults.yaml"
        bad.write_text(
            textwrap.dedent(
                """\
                schema_version: 1
                plugins:
                  - id: nines
                    backend: pip
                    package: nines
                    install_cmd: "pip install --upgrade nines"
                    version_check_cmd: "nines --version"
                    min_version: "3.0.0"
                    canonical_url: "https://example.com/nines-fixture"
                defaults:
                  - "this is a list not a mapping"
                """
            )
        )
        with patch("devolaflow.plugins.installer.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed(stdout="nines, version 3.3.0")
            version = ensure_plugin("nines", registry_path=bad)
        assert version == "3.3.0"

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_post_install_version_unparseable_raises(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe
            _mock_completed(stdout="ok"),  # install OK
            _mock_completed(stdout="WEIRD NO VERSION HERE"),  # probe returns no version
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("nines", registry_path=registry_path)
        assert "did not return a parseable version" in str(exc.value)

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_probe_version_oserror_treated_as_absent(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            OSError("cannot exec probe"),  # pre-install probe raises OSError
            _mock_completed(stdout="ok"),  # install succeeds
            _mock_completed(stdout="nines, version 3.3.0"),  # post-install probe OK
        ]
        registry_path = _write_runtime_registry(tmp_path)
        version = ensure_plugin("nines", registry_path=registry_path)
        assert version == "3.3.0"

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_pip_install_oserror_is_wrapped_as_plugininstallerror(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe fails
            OSError("fork failed"),  # pip install fails at exec time
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("nines", registry_path=registry_path)
        assert "os-error" in str(exc.value)

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_install_oserror_is_wrapped_as_plugininstallerror(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe
            OSError("npm binary missing"),  # npm install OSError
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("ui-pro", registry_path=registry_path)
        assert "os-error" in str(exc.value)

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_install_timeout_is_wrapped_as_plugininstallerror(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),
            subprocess.TimeoutExpired("npm install", 90),
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("ui-pro", registry_path=registry_path)
        assert "timeout" in str(exc.value).lower()

    @patch("devolaflow.plugins.installer.subprocess.run")
    def test_npm_init_oserror_captured_as_failed_target(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = [
            _mock_completed(returncode=1),  # pre-install probe
            _mock_completed(stdout="added 1 package"),  # npm install
            OSError("cursor init exec failed"),  # cursor init OSError
            _mock_completed(stdout="claude ok"),
            _mock_completed(stdout="codex ok"),
        ]
        registry_path = _write_runtime_registry(tmp_path)
        with pytest.raises(PluginInstallError) as exc:
            ensure_plugin("ui-pro", registry_path=registry_path)
        failed = exc.value.details["failed_targets"]
        assert failed[0]["ai_platform"] == "cursor"
        assert "os-error" in failed[0]["reason"]

    def test_append_log_handles_unwritable_path(self, tmp_path: Path) -> None:
        # Simulate _append_log with a path whose ``.open()`` raises OSError —
        # verify the function does NOT propagate (documented side-channel per
        # S-5 best-effort exception) and logs a warning instead. Uses a
        # throwaway stand-in rooted at tmp_path so nothing leaks into the
        # repo root.

        class _BadPath:
            """Stand-in for Path whose .open raises OSError."""

            def __init__(self, parent: Path) -> None:
                self.parent = parent

            def open(self, *_args: object, **_kwargs: object) -> None:
                raise OSError("disk full (simulated)")

        bad = _BadPath(tmp_path)
        # Must not raise despite the OSError raised by .open()
        _installer_mod._append_log(bad, "test_event", "nines", {"note": "x"})
        # Reached here without exception ⇒ PASS
        assert True

    def test_attempt_pip_uninstall_logs_warning_when_pip_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When pip is not on PATH, _attempt_pip_uninstall should log + return
        # without raising (best-effort per design.md §6 "uninstall" semantic).
        monkeypatch.setattr(_installer_mod.shutil, "which", lambda _name: None)
        spec = RuntimePluginSpec(
            id="nines",
            backend="pip",
            package="nines",
            install_cmd="pip install nines",
            version_check_cmd="nines --version",
            min_version="3.0.0",
            canonical_url="https://example.com/nines-fixture",
        )
        # Should complete silently (no raise) even with pip missing.
        _installer_mod._attempt_pip_uninstall(spec, timeout=5)


# ===========================================================================
# v12.5.0 PV-03 — Codegraph plugin registration
# ===========================================================================


class TestV1250CodegraphRegistration:
    """Codegraph capability metadata mirrors the runtime SSOT."""

    def test_codegraph_spec_registered(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        codegraph = reg.get("codegraph")
        assert codegraph is not None
        assert codegraph.cli_binary == "codegraph"
        assert codegraph.role == "code_intelligence"
        assert codegraph.min_version == "0.9.3"
        assert codegraph.repo_url == "https://github.com/colbymchenry/codegraph"

    def test_codegraph_install_methods(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        codegraph = reg.get("codegraph")
        assert codegraph is not None
        assert codegraph.install_methods["npm"] == ("npm install -g @colbymchenry/codegraph@latest")
        assert "install.sh" in codegraph.install_methods["script"]

    def test_codegraph_capabilities(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        codegraph = reg.get("codegraph")
        assert codegraph is not None
        assert {
            "smart_context_building",
            "full_text_search",
            "impact_analysis",
            "callers_callees_trace",
            "file_structure_lookup",
            "test_impact_selection",
            "framework_route_awareness",
            "multi_language_index",
        }.issubset(set(codegraph.capabilities))

    def test_codegraph_workflows(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        codegraph = reg.get("codegraph")
        assert codegraph is not None
        assert {
            "repo-init",
            "onboarding",
            "security-audit",
            "product-verification",
        }.issubset(set(codegraph.workflows))

    def test_codegraph_stage_mapping(self) -> None:
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        codegraph = reg.get("codegraph")
        assert codegraph is not None
        assert {"analyze", "scaffold", "research", "impact"} <= set(codegraph.stage_mapping)

    def test_code_intelligence_role_present(self) -> None:
        import yaml

        payload = yaml.safe_load(_REPO_PLUGINS_YAML.read_text(encoding="utf-8"))
        role = (payload.get("plugin_roles") or {}).get("code_intelligence")
        assert role is not None
        assert role["provider"] == "codegraph"
        assert role["invocation"] == "on_demand"


class TestV13ImpeccableRegistration:
    """v13.0.0 — impeccable block + ui_refinement role.

    Loads the real repository ``plugins.yaml`` (canonical source-of-truth per
    A-5 SSOT) and asserts the impeccable integration ships with the contract
    documented at ``.local/research/v13.0.0_gap_analysis.md`` §3 Phase 1.
    """

    def test_impeccable_spec_registered(self) -> None:
        """``plugins.yaml`` declares the impeccable plugin block."""
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        imp = reg.get("impeccable")
        assert imp is not None, (
            "v13.0.0 violation: impeccable plugin block missing from "
            "workflow-system/agent/plugins.yaml. The block MUST exist for the "
            "v13.0.0 impeccable integration to function."
        )
        assert imp.cli_binary == "impeccable"
        assert imp.role == "ui_refinement"
        assert imp.min_version == "2.0.0"
        assert imp.repo_url == "https://github.com/pbakaus/impeccable"

    def test_impeccable_install_method_npm(self) -> None:
        """impeccable declares the npm install method."""
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        imp = reg.get("impeccable")
        assert imp is not None
        assert imp.install_methods.get("npm") == "npm install -g impeccable"

    def test_impeccable_capabilities(self) -> None:
        """impeccable declares its v13.0.0 capabilities incl. antipattern_detection."""
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        imp = reg.get("impeccable")
        assert imp is not None
        expected = {
            "design_refinement",
            "ux_design_critique",
            "technical_quality_audit",
            "antipattern_detection",
        }
        assert expected.issubset(set(imp.capabilities)), (
            "v13.0.0: impeccable capabilities MUST include the core refine/"
            f"critique/audit/detect surfaces; missing: {expected - set(imp.capabilities)}"
        )

    def test_impeccable_workflows_include_web_design(self) -> None:
        """impeccable workflows include the new web-design template."""
        reg = create_default_registry(plugins_yaml=_REPO_PLUGINS_YAML)
        imp = reg.get("impeccable")
        assert imp is not None
        assert "web-design" in imp.workflows, (
            "v13.0.0: impeccable workflows MUST include web-design"
        )

    def test_ui_refinement_role_present(self) -> None:
        """``plugins.yaml`` declares the NEW ui_refinement role (provider=impeccable)."""
        import yaml

        with _REPO_PLUGINS_YAML.open(encoding="utf-8") as f:
            payload = yaml.safe_load(f)
        plugin_roles = payload.get("plugin_roles", {})
        ur = plugin_roles.get("ui_refinement")
        assert ur is not None, (
            "v13.0.0 violation: plugin_roles.ui_refinement missing from "
            "plugins.yaml. The 6th role MUST exist (provider=impeccable)."
        )
        assert ur.get("provider") == "impeccable"
        assert ur.get("invocation") == "on_demand"
        assert "web-design" in (ur.get("primary_workflows") or [])
        for stage in ("refine", "verify"):
            assert stage in (ur.get("stage_affinity") or [])


# ===========================================================================
# v15.0.0 G-021 — plugin registry unification (A-5 single-owner)
# ===========================================================================
#
# `knowledge/runtime-plugins.yaml` is the single A-5 SSOT owner of plugin
# REGISTRATION data; `plugins.yaml` is its DERIVED capability/role/
# stage_mapping view. These tests are the "generated-from truth" lint
# cited by both file headers and by `.rules/architecture.mdc` §A-5 row 1:
# membership/ID/order parity, registration-truth field agreement, and the
# derived-view header declaration. Source:
# `.local/research/v14.2.0_gap_analysis.md` §2.4 (F-P5-1 / F-P5-6).
# ===========================================================================

_RUNTIME_PLUGINS_YAML = (
    _REPO_ROOT / "workflow-system" / "agent" / "knowledge" / "runtime-plugins.yaml"
)


class TestV15PluginRegistryUnification:
    """G-021 — the derived view mirrors the SSOT owner (A-5.1)."""

    @staticmethod
    def _owner_entries() -> list[dict]:
        import yaml

        raw = yaml.safe_load(_RUNTIME_PLUGINS_YAML.read_text(encoding="utf-8"))
        return list(raw["plugins"])

    @staticmethod
    def _view_plugins() -> dict:
        import yaml

        raw = yaml.safe_load(_REPO_PLUGINS_YAML.read_text(encoding="utf-8"))
        return raw["plugins"]

    def test_derived_view_ids_mirror_owner_set_and_order(self) -> None:
        """plugins.yaml keys == runtime-plugins.yaml ids, in owner order."""
        owner_ids = [entry["id"] for entry in self._owner_entries()]
        view_ids = list(self._view_plugins().keys())
        assert view_ids == owner_ids, (
            f"A-5.1 / G-021 violation: derived view plugins.yaml ids {view_ids!r} "
            f"must mirror the SSOT owner runtime-plugins.yaml ids {owner_ids!r} "
            f"(same set AND order). Register new plugins in the OWNER first, "
            f"then mirror the view."
        )

    def test_derived_view_registration_truth_agrees_with_owner(self) -> None:
        """min_version + repo_url in the view match the owner's truth fields."""
        owner_by_id = {entry["id"]: entry for entry in self._owner_entries()}
        for plugin_id, view_entry in self._view_plugins().items():
            owner_entry = owner_by_id[plugin_id]
            assert view_entry.get("min_version") == owner_entry.get("min_version"), (
                f"G-021 violation: {plugin_id!r} min_version diverged — view "
                f"{view_entry.get('min_version')!r} vs owner "
                f"{owner_entry.get('min_version')!r}. The owner is the truth; "
                f"update runtime-plugins.yaml first, then mirror."
            )
            assert view_entry.get("repo_url") == owner_entry.get("canonical_url"), (
                f"G-021 violation: {plugin_id!r} repo_url diverged — view "
                f"{view_entry.get('repo_url')!r} vs owner canonical_url "
                f"{owner_entry.get('canonical_url')!r} (S-7 URL truth lives in "
                f"the owner)."
            )

    def test_derived_view_declares_generated_from_header(self) -> None:
        """plugins.yaml header names the owner and its own derived status."""
        text = _REPO_PLUGINS_YAML.read_text(encoding="utf-8")
        header = "\n".join(text.splitlines()[:30])
        assert "DERIVED" in header, (
            "G-021: plugins.yaml header must declare the file a DERIVED view "
            "(generated-from truth) — see v14.2.0 gap analysis §2.4"
        )
        assert "knowledge/runtime-plugins.yaml" in header, (
            "G-021: plugins.yaml header must cite the A-5 SSOT owner path "
            "workflow-system/agent/knowledge/runtime-plugins.yaml"
        )
