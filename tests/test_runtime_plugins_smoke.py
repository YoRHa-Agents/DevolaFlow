"""Registry-walk smoke tests for the registered runtime plugins.

Closes D-P-4 from `.local/research/v10.2.0_gap_analysis.md` §3.1:
v9.4.0 PV-04 wired schema v3 + the runtime plugin catalog; v10.1.0 added zero plugin
work. No CI step had confirmed the 4 registered plugins still resolve
cleanly via `resolve_plugin` until this smoke file landed.

Test surface (pure registry walk + dataclass shape; NO subprocess):

§1 — schema_version is 4 (v15.2.0 B-6 bump); `defaults.upgrade_check_frequency_hours` is 24.
§2 — the 3 expected plugin IDs are present in canonical order.
§3 — every `resolve_plugin(p["id"], registry)` returns a
     RuntimePluginSpec whose backend is one of the 3 supported values
     (pip / npm_then_init / curl_install_script).
§4 — every plugin carries a non-empty `canonical_url` (S-7 compliance).

Source: `.local/research/v10.2.0_gap_analysis.md` §3.1 D-P-4 +
`.local/research/v10.2.0_cycle_plan.md` §3 PV-01.
External tool reference (S-7): https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import shutil

import pytest

from devolaflow.plugins import load_registry, resolve_plugin
from devolaflow.plugins.installer import _SUPPORTED_BACKENDS, RuntimePluginSpec

_EXPECTED_PLUGIN_IDS: tuple[str, ...] = (
    "ui-pro",
    "codegraph",
    "impeccable",
)


def test_registry_schema_version_is_4() -> None:
    """Registry schema pin: v3 baseline bumped to v4 by the v15.2.0 B-6 sweep.

    (v15.2.0 B-6 added the tier/default-install fields without removing
    support for schema versions 1 through 3.)
    """
    registry = load_registry()
    assert registry["schema_version"] == 4, (
        f"runtime-plugins.yaml schema_version must be 4 "
        f"(v9.4.0 PV-04 v3 baseline + v15.2.0 B-6 tier/auto_install bump); "
        f"got {registry['schema_version']!r}"
    )


def test_registry_upgrade_check_frequency_defaults_24h() -> None:
    """Daily upgrade cadence is the documented contract (gap §3.2 D-P-5)."""
    registry = load_registry()
    defaults = registry.get("defaults") or {}
    assert defaults.get("upgrade_check_frequency_hours") == 24, (
        "defaults.upgrade_check_frequency_hours must be 24 (daily); "
        "the user mandate 'auto-upgrade daily' requires this value."
    )


def test_registry_contains_expected_3_plugin_ids() -> None:
    """The active registry contains exactly three plugins in canonical order."""
    registry = load_registry()
    registered = tuple(p["id"] for p in registry["plugins"])
    assert registered == _EXPECTED_PLUGIN_IDS


@pytest.mark.parametrize("plugin_id", _EXPECTED_PLUGIN_IDS)
def test_resolve_plugin_returns_valid_spec(plugin_id: str) -> None:
    """`resolve_plugin` yields a well-formed RuntimePluginSpec with a
    supported backend + non-empty canonical_url (S-7 compliance)."""
    registry = load_registry()
    spec = resolve_plugin(plugin_id, registry)
    assert isinstance(spec, RuntimePluginSpec)
    assert spec.id == plugin_id
    assert spec.backend in _SUPPORTED_BACKENDS, (
        f"plugin {plugin_id!r} backend {spec.backend!r} not in {sorted(_SUPPORTED_BACKENDS)!r}"
    )
    assert spec.canonical_url, (
        f"plugin {plugin_id!r} has empty canonical_url — S-7 requires "
        f"external tools to carry their remote GitHub URL"
    )
    assert spec.canonical_url.startswith("https://"), (
        f"plugin {plugin_id!r} canonical_url must be an https:// URL; got {spec.canonical_url!r}"
    )
    assert spec.install_cmd, (
        f"plugin {plugin_id!r} has empty install_cmd — would make ensure_plugin unusable"
    )
    assert spec.version_check_cmd, (
        f"plugin {plugin_id!r} has empty version_check_cmd — would make _probe_version unusable"
    )
    assert spec.min_version, f"plugin {plugin_id!r} has empty min_version"
    expected_default_install = plugin_id in {"codegraph", "impeccable"}
    assert spec.default_install is expected_default_install


def test_all_plugins_use_python_or_shell_that_is_available() -> None:
    """`shutil.which` finds at least one of the runtime prerequisites
    referenced by plugin install_cmd values (pip / npm / curl / bash).

    This is a smoke check for the CI environment itself — it does NOT
    actually install anything. If EVERY prerequisite is missing, the
    test fails with an informative message so the operator knows their
    shell environment is misconfigured BEFORE they hit an opaque
    `PluginInstallError` at dispatch time.
    """
    prerequisites = ["bash", "pip", "npm", "curl"]
    found = [p for p in prerequisites if shutil.which(p) is not None]
    assert found, (
        f"None of the plugin install prerequisites {prerequisites!r} "
        f"are on PATH. Plugin auto-install cannot proceed in this "
        f"environment; provision at least one backend's toolchain."
    )


# ---------------------------------------------------------------------------
# v12.5.0 PV-03 — codegraph runtime plugin entry smoke
# ---------------------------------------------------------------------------


def test_codegraph_runtime_entry_smoke() -> None:
    """Codegraph runtime registration keeps its optional install contract."""
    registry = load_registry()
    spec = resolve_plugin("codegraph", registry)
    assert spec.id == "codegraph"
    assert spec.tier == "suggest"
    assert spec.default_install is True
    assert spec.backend == "npm_then_init"
    assert spec.package == "@colbymchenry/codegraph"
    assert spec.min_version == "0.9.3"
    assert spec.canonical_url == "https://github.com/colbymchenry/codegraph"
    assert {
        "repo-init",
        "onboarding",
        "security-audit",
        "product-verification",
    }.issubset(set(spec.invoked_by_workflows or []))


# ---------------------------------------------------------------------------
# v13.0.0 — impeccable runtime plugin entry smoke
# ---------------------------------------------------------------------------


def test_impeccable_runtime_entry_smoke() -> None:
    """v13.0.0: impeccable runtime entry has the contracted shape.

    Pins the contract fields for the 6th plugin:
      * backend = npm_then_init (reuses the ui-pro precedent)
      * package = impeccable
      * canonical_url = https://github.com/pbakaus/impeccable
      * init_targets = [auto] (impeccable `skills install` auto-detects the
        harness; the init template carries no {ai_platform} placeholder)
      * version_check_cmd = "impeccable --version" (prints pkg.version)
      * invoked_by_workflows includes web-design
    """
    registry = load_registry()
    spec = resolve_plugin("impeccable", registry)
    assert spec.id == "impeccable"
    assert spec.backend == "npm_then_init"
    assert spec.package == "impeccable"
    assert spec.canonical_url == "https://github.com/pbakaus/impeccable"
    assert spec.init_targets == ["auto"], (
        f"impeccable init_targets must be the single sentinel [auto] (skills "
        f"install auto-detects the harness); got {spec.init_targets!r}"
    )
    assert "{ai_platform}" not in (spec.init_cmd_template or ""), (
        "impeccable init_cmd_template must NOT carry a {ai_platform} placeholder "
        "— `impeccable skills install` auto-detects the harness (no --ai flag)"
    )
    assert spec.version_check_cmd == "impeccable --version"
    assert "web-design" in (spec.invoked_by_workflows or []), (
        "impeccable invoked_by_workflows must include web-design"
    )


def test_ui_pro_invoked_by_web_design() -> None:
    """v13.0.0: ui-pro now also cites web-design (designs before impeccable refines)."""
    registry = load_registry()
    spec = resolve_plugin("ui-pro", registry)
    assert "web-design" in (spec.invoked_by_workflows or []), (
        "ui-pro invoked_by_workflows must include web-design (ui-pro DESIGNS, "
        "impeccable REFINES); plugins_for_workflow('web-design') resolves to "
        "[ui-pro, impeccable] in registry order"
    )


def test_plugins_for_web_design_resolves_ui_pro_then_impeccable() -> None:
    """v13.0.0: plugins_for_workflow('web-design') == ['ui-pro', 'impeccable']."""
    from devolaflow.plugins.installer import plugins_for_workflow

    assert plugins_for_workflow("web-design") == ["ui-pro", "impeccable"], (
        "registry order must yield ui-pro (design) before impeccable (refine)"
    )
