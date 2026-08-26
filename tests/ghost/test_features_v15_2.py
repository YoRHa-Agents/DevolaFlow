"""Ghost audit — per-cycle W-18 feature stanzas for the v15.2 cycle.

Per v15-ADR-001: new W-18 stanzas for a v15.2.x release append HERE; the
next MAJOR/MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
Every symbol pinned below was verified against the working tree at
authoring time (B-6 dependency suggestion-ization) — NOT blind-trusted
from sibling-task descriptions.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def test_v15_2_0_b6_dependency_suggestion_registered(project_root: Path) -> None:
    """W-18 v15.2.0: B-6 dependency suggestion-ization (04 §8) has coverage.

    Discharges the W-18 precondition for the v15.2.0 CHANGELOG entry on
    the B-6 slice (G5 remainder ×3 from the phase2 convergence plan §2.3).
    The stanza pins:

    (a) ``runtime-plugins.yaml`` schema v4: every plugin entry declares
        ``tier: suggest`` and ``defaults.auto_install`` is ``false``.
    (b) ``RuntimePluginSpec.tier`` parses (default ``suggest``), invalid
        values raise, and ``plugin_tier()`` resolves the live registry.
    (c) Checklist seeds carry no executable plugin-install keys; plugin
        workflow ownership remains explicit in runtime-plugins.yaml.
    (d) ``suggest_plugin_once`` one-time-per-session hint semantics.
    (e) The explicit opt-in call sites pass ``auto_install=True`` (the
        env-flag hooks + the ``devola-init --global`` bundling), so the
        ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` install semantics survive
        the default flip.
    (f) The env-flags §2.5 row is a RETIRED tombstone (B-6 mandate:
        delete-or-wire resolved to delete).
    """
    from devolaflow.plugins.installer import (
        _SUPPORTED_SCHEMA_VERSIONS,
        _SUPPORTED_TIERS,
        RegistryDefaults,
        RuntimePluginSpec,
        load_registry,
        plugin_tier,
        resolve_plugin,
    )

    # ── (a) registry data: schema v4, all-suggest, auto_install false ──
    registry_path = project_root / "workflow-system/agent/knowledge/runtime-plugins.yaml"
    raw = load_registry(registry_path)
    assert raw["schema_version"] == 4
    assert 4 in _SUPPORTED_SCHEMA_VERSIONS
    assert frozenset({"require", "suggest"}) == _SUPPORTED_TIERS
    plugin_ids = [e["id"] for e in raw["plugins"]]
    assert plugin_ids == ["ui-pro", "rtk", "si-chip", "codegraph", "impeccable"]
    for entry in raw["plugins"]:
        assert entry.get("tier") == "suggest", (
            f"B-6: plugin {entry.get('id')!r} must ship tier: suggest "
            f"(the require tier is a kept mechanism with no occupant)"
        )
    assert raw["defaults"]["auto_install"] is False

    # ── (b) spec parse + tier lookup ──
    spec = resolve_plugin("ui-pro", raw)
    assert spec.tier == "suggest"
    assert RuntimePluginSpec.__dataclass_fields__["tier"].default == "suggest"
    assert plugin_tier("ui-pro", registry_path=registry_path) == "suggest"
    # absent-key default (v1..v3 entries pass v4 unchanged)
    legacy = {
        "plugins": [
            {
                "id": "x",
                "backend": "pip",
                "package": "x",
                "install_cmd": "pip install x",
                "version_check_cmd": "x --version",
                "min_version": "1.0.0",
            }
        ]
    }
    assert resolve_plugin("x", legacy).tier == "suggest"
    # invalid tier raises loudly (S-5)
    import pytest

    from devolaflow.plugins.exceptions import PluginInstallError

    bad = {"plugins": [{**legacy["plugins"][0], "tier": "mandatory"}]}
    with pytest.raises(PluginInstallError, match="invalid tier"):
        resolve_plugin("x", bad)
    # code-side default fallback mirrors the shipped registry value
    assert RegistryDefaults().auto_install is False

    # ── (c) plugin ownership lives outside non-executable seeds ──
    from devolaflow.template_engine.registry import TemplateRegistry

    template_dir = project_root / "workflow-system/agent/templates"
    registry = TemplateRegistry(template_dir)
    reg = yaml.safe_load((template_dir / "registry.yaml").read_text(encoding="utf-8"))
    entries = reg["compositions"] + reg["templates"]
    assert len(entries) == 24
    for entry in entries:
        seed_path = template_dir / entry["seed"]
        text = seed_path.read_text(encoding="utf-8")
        assert "ensure_plugins:" not in text
        assert "suggest_plugins:" not in text
        assert registry.load_seed(entry["name"]) is not None

    expected_workflows = {
        "si-chip": {"skill-optimization", "self-update", "nines-assisted"},
        "ui-pro": {"product-verification", "web-design"},
        "impeccable": {"web-design"},
    }
    by_id = {entry["id"]: entry for entry in raw["plugins"]}
    for plugin_id, workflows in expected_workflows.items():
        assert workflows <= set(by_id[plugin_id]["invoked_by_workflows"])

    # ── (d) one-time suggestion cache ──
    from devolaflow.plugins import loader

    loader._SESSION_SUGGESTED.discard("__ghost_probe__")
    first = loader.suggest_plugin_once("__ghost_probe__")
    assert first is not None and "DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1" in first
    assert loader.suggest_plugin_once("__ghost_probe__") is None
    loader._SESSION_SUGGESTED.discard("__ghost_probe__")

    # ── (e) explicit opt-in call sites pass auto_install=True ──
    import importlib
    import inspect

    from devolaflow import init_project

    # import the MODULES (the lifecycle package re-exports same-named
    # handler functions, which would shadow a `from` import)
    ppi_alias = importlib.import_module("devolaflow.lifecycle.pre_plugin_invocation")
    ppi_install = importlib.import_module("devolaflow.lifecycle.pre_plugin_invocation_install")

    for mod in (ppi_alias, ppi_install, init_project):
        src = inspect.getsource(mod)
        assert "ensure_plugin(pid, auto_install=True)" in src or (
            "ensure_plugin(plugin_id, auto_install=True)" in src
        ), f"B-6: {mod.__name__} must pass auto_install=True explicitly"

    # tier-aware severity helper is shared by alias + split handler
    assert hasattr(ppi_install, "_ppi001_violation")
    assert "_ppi001_violation" in inspect.getsource(ppi_alias)

    # ── (f) env-flags §2.5 tombstone ──
    env_flags = (project_root / "workflow-system/agent/references/env-flags.md").read_text(
        encoding="utf-8"
    )
    assert "### 2.5 `DEVOLAFLOW_AUTO_INSTALL` — RETIRED" in env_flags
    assert "precondition.config.ensure_plugins" not in env_flags
