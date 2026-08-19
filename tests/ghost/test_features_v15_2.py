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
    (c) The ensure→suggest template rename: NO live template carries an
        ``ensure_plugins`` key; the six known dependency points carry
        ``suggest_plugins`` with unchanged plugin values.
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
    assert len(plugin_ids) >= 6
    for entry in raw["plugins"]:
        assert entry.get("tier") == "suggest", (
            f"B-6: plugin {entry.get('id')!r} must ship tier: suggest "
            f"(the require tier is a kept mechanism with no occupant)"
        )
    assert raw["defaults"]["auto_install"] is False

    # ── (b) spec parse + tier lookup ──
    spec = resolve_plugin("nines", raw)
    assert spec.tier == "suggest"
    assert RuntimePluginSpec.__dataclass_fields__["tier"].default == "suggest"
    assert plugin_tier("nines", registry_path=registry_path) == "suggest"
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

    # ── (c) ensure→suggest rename across live templates ──
    template_dir = project_root / "workflow-system/agent/templates"
    expected_suggest = {
        "builtin/web-design.yaml": 3,
        "builtin/nines-assisted.yaml": 1,
        "builtin/self-update.yaml": 1,
        "builtin/skill-optimization.yaml": 1,
        "registry.yaml": 1,
    }
    for rel, count in expected_suggest.items():
        text = (template_dir / rel).read_text(encoding="utf-8")
        assert "ensure_plugins:" not in text, (
            f"B-6 rename incomplete: {rel} still carries an ensure_plugins key"
        )
        assert text.count("suggest_plugins:") == count
    reg = yaml.safe_load((template_dir / "registry.yaml").read_text(encoding="utf-8"))
    pv = next(c for c in reg["compositions"] if c["name"] == "product-verification")
    assert pv["params"]["suggest_plugins"] == ["ui-pro"]

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
