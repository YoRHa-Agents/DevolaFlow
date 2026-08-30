"""Loop v3 PV-3 plugin ownership, profiles, fallback, and refresh contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from devolaflow.plugins import load_registry
from devolaflow.plugins.installer import (
    available_plugin_profiles,
    select_plugin_profile,
    upgrade_plugin,
)
from devolaflow.plugins.loader import create_default_registry

_ROOT = Path(__file__).resolve().parent.parent
_RUNTIME = _ROOT / "workflow-system/agent/knowledge/runtime-plugins.yaml"
_VIEW = _ROOT / "workflow-system/agent/plugins.yaml"
_PLUGIN_IDS = ["ui-pro", "codegraph", "impeccable"]
_DEFAULT_PLUGIN_IDS = ["codegraph", "impeccable"]


def test_runtime_plugins_remain_optional_suggest_tier() -> None:
    registry = load_registry(_RUNTIME)
    assert [entry["id"] for entry in registry["plugins"]] == _PLUGIN_IDS
    assert all(entry.get("tier") == "suggest" for entry in registry["plugins"])
    assert registry["defaults"]["auto_install"] is False


def test_global_profiles_are_explicit_and_ssot_derived() -> None:
    assert available_plugin_profiles(registry_path=_RUNTIME) == {
        "all": _DEFAULT_PLUGIN_IDS,
        "global": _DEFAULT_PLUGIN_IDS,
        **{plugin_id: [plugin_id] for plugin_id in _PLUGIN_IDS},
    }
    assert select_plugin_profile("ui-pro", registry_path=_RUNTIME) == ["ui-pro"]
    with pytest.raises(ValueError, match="Unknown plugin profile"):
        select_plugin_profile("missing", registry_path=_RUNTIME)


def test_singleton_global_profile_delegates_explicit_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devolaflow.plugins import installer

    calls: list[tuple[str, bool]] = []

    def fake_ensure(plugin_id: str, **kwargs: object) -> str:
        calls.append((plugin_id, kwargs["auto_install"]))
        return "0.0.0-test"

    monkeypatch.setattr(installer, "ensure_plugin", fake_ensure)
    assert installer.install_plugin_profile("ui-pro", registry_path=_RUNTIME) == {
        "ui-pro": "0.0.0-test"
    }
    assert calls == [("ui-pro", True)]


def test_loader_uses_runtime_values_over_stale_presentation_values(tmp_path: Path) -> None:
    view_path = tmp_path / "workflow-system/agent/plugins.yaml"
    runtime_path = view_path.parent / "knowledge/runtime-plugins.yaml"
    runtime_path.parent.mkdir(parents=True)
    runtime_path.write_text(_RUNTIME.read_text(encoding="utf-8"), encoding="utf-8")

    view = yaml.safe_load(_VIEW.read_text(encoding="utf-8"))
    view["plugins"]["ui-pro"]["min_version"] = "0.0.0"
    view["plugins"]["ui-pro"]["repo_url"] = "https://stale.example.invalid"
    view["plugins"]["ui-pro"]["workflows"] = ["stale-workflow"]
    view_path.write_text(yaml.safe_dump(view, sort_keys=False), encoding="utf-8")

    registry = create_default_registry(plugins_yaml=view_path)
    ui_pro = registry.get("ui-pro")
    assert ui_pro is not None
    assert ui_pro.min_version == "2.0.0"
    assert ui_pro.repo_url == "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"
    assert ui_pro.workflows == ["product-verification", "web-design"]


def test_npm_upgrade_refreshes_every_declared_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = yaml.safe_load(_RUNTIME.read_text(encoding="utf-8"))
    entry = next(item for item in source["plugins"] if item["id"] == "ui-pro")
    entry["init_targets"] = ["cursor", "claude"]
    entry["init_cmd_template"] = "uipro init --ai {ai_platform} --global"
    entry["upgrade_cmd"] = "npm upgrade uipro-cli"
    registry_path = tmp_path / "runtime-plugins.yaml"
    registry_path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")

    calls: list[str] = []

    def fake_run(command: str, *, timeout: int) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            args=["bash", "-c", command],
            returncode=0,
            stdout="uipro 99.99.99",
            stderr="",
        )

    from devolaflow.plugins import installer

    monkeypatch.setattr(installer, "_run_cmd", fake_run)
    version = upgrade_plugin(
        "ui-pro",
        registry_path=registry_path,
        log_path=tmp_path / "plugin_install.log",
    )

    assert version == "99.99.99"
    assert calls[0] == "npm upgrade uipro-cli"
    assert calls[1] == "uipro --version"
    assert calls[2:] == [
        "uipro init --ai cursor --global",
        "uipro init --ai claude --global",
    ]
