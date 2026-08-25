"""Tests for the v9.5.0 PV-01 Si-Chip plugin registration.

Pins the contract for the 4th `runtime-plugins.yaml` entry (`si-chip`):

1. **Canonical registry has si-chip** — schema_version 4 (v15.2.0 B-6 bump) + plugins
   (`ui-pro`, `rtk`, `si-chip`, `codegraph`, `impeccable`) with the v3 `upgrade_cmd`
   field present.
2. **Schema parses si-chip** — `resolve_plugin('si-chip', registry)`
   returns a `RuntimePluginSpec` with the documented fields
   (backend=curl_install_script, canonical_url=GitHub URL, etc.).
3. **Workflow → plugin resolution** — `plugins_for_workflow` returns
    `si-chip` for the 3 workflows it is invoked by (`skill-optimization`,
   `self-update`, `nines-assisted`).
4. **Legacy plugins.yaml backward-compat** — the legacy catalog has the
   `si-chip` entry too (same spec shape used by pre-v8.2.1 callers).
5. **No verify_distinguish_cmd** — Si-Chip has no name collision; the
   field MUST be absent (or None) per the v9.5.0 gap analysis §3.1
   D-S-1 design decision.

Source: `.local/research/v9.5.0_gap_analysis.md` §3.1 D-S-1 + §6 AC-1
+ AC-2.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from devolaflow.plugins.installer import (
    RuntimePluginSpec,
    load_registry,
    plugins_for_workflow,
    resolve_plugin,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_KNOWLEDGE_DIR = _REPO_ROOT / "workflow-system" / "agent" / "knowledge"
_RUNTIME_PLUGINS_YAML = _KNOWLEDGE_DIR / "runtime-plugins.yaml"
_LEGACY_PLUGINS_YAML = _REPO_ROOT / "workflow-system" / "agent" / "plugins.yaml"


# ---------------------------------------------------------------------------
# §1 — canonical registry has si-chip
# ---------------------------------------------------------------------------


class TestSiChipInCanonicalRegistry:
    """Pin the 4th entry in `runtime-plugins.yaml`."""

    def test_canonical_registry_loads_with_si_chip(self) -> None:
        """v9.5.0: 4 plugins; v12.5.0: codegraph appended 5th; v13.0.0: impeccable 6th.

        si-chip remains the 4th plugin (registry-order discipline preserved); each
        cycle appends the new plugin at the END of the list (append-only, A-2).
        """
        raw = load_registry(_RUNTIME_PLUGINS_YAML)
        assert raw["schema_version"] == 4, (
            "schema_version must be 4 (v9.4.0 PV-04 v3 + v15.2.0 B-6 bump)"
        )
        plugin_ids = [p["id"] for p in raw["plugins"]]
        assert plugin_ids == ["ui-pro", "rtk", "si-chip", "codegraph", "impeccable"]

    def test_si_chip_resolves_via_resolve_plugin(self) -> None:
        registry = load_registry(_RUNTIME_PLUGINS_YAML)
        spec = resolve_plugin("si-chip", registry)
        assert isinstance(spec, RuntimePluginSpec)
        assert spec.id == "si-chip"
        assert spec.backend == "curl_install_script", (
            "v9.5.0 PV-01 contract: si-chip reuses the RTK v8.3.1 "
            "curl_install_script backend (same plumbing)"
        )
        assert spec.package == "si-chip"
        assert spec.min_version == "0.4.0"
        assert spec.canonical_url == "https://github.com/YoRHa-Agents/Si-Chip", (
            "S-7: si-chip MUST be referenced by its canonical GitHub URL"
        )

    def test_si_chip_install_cmd_uses_yorha_pages_install_script(self) -> None:
        """Si-Chip ships a single install.sh on yorha-agents.github.io."""
        registry = load_registry(_RUNTIME_PLUGINS_YAML)
        spec = resolve_plugin("si-chip", registry)
        assert "yorha-agents.github.io/Si-Chip/install.sh" in spec.install_cmd, (
            f"si-chip install_cmd MUST point at the canonical GitHub Pages "
            f"install script (S-7 — no local clone path). Actual: {spec.install_cmd!r}"
        )
        assert "--target cursor" in spec.install_cmd
        assert "--scope global" in spec.install_cmd
        assert "--yes" in spec.install_cmd, (
            "Non-interactive install — `--yes` flag required for CI/CD use"
        )

    def test_si_chip_upgrade_cmd_matches_install_cmd(self) -> None:
        """Si-Chip installer is idempotent per its v0.4.0 spec — upgrade = install."""
        registry = load_registry(_RUNTIME_PLUGINS_YAML)
        spec = resolve_plugin("si-chip", registry)
        assert spec.upgrade_cmd == spec.install_cmd, (
            "v9.4.0 PV-04 schema v3 contract: when the installer is "
            "idempotent (curl_install_script backend), upgrade_cmd "
            "should equal install_cmd. Author MUST declare it explicitly "
            "rather than relying on the None fallback for clarity."
        )

    def test_si_chip_has_no_verify_distinguish_cmd(self) -> None:
        """v9.5.0 design decision: Si-Chip has no known name collision."""
        registry = load_registry(_RUNTIME_PLUGINS_YAML)
        spec = resolve_plugin("si-chip", registry)
        assert spec.verify_distinguish_cmd is None, (
            "Si-Chip has no documented name collision (the RTK distinguish-cmd "
            "exists only because of the rtk-type-kit collision per RTK INSTALL.md). "
            "Adding a distinguish-cmd here would be cargo-culting."
        )


# ---------------------------------------------------------------------------
# §2 — workflow → plugin resolution
# ---------------------------------------------------------------------------


class TestSiChipWorkflowResolution:
    """Pin `plugins_for_workflow` returns si-chip for the 3 wired workflows."""

    def test_workflow_resolution_includes_si_chip_for_skill_optimization(self) -> None:
        plugins = plugins_for_workflow("skill-optimization")
        assert "si-chip" in plugins, (
            f"PV-01 AC-2: si-chip MUST resolve for skill-optimization "
            f"workflow (the canonical optimisation pipeline). Got {plugins!r}"
        )
        assert plugins == ["si-chip"]

    def test_workflow_resolution_includes_si_chip_for_self_update(self) -> None:
        plugins = plugins_for_workflow("self-update")
        assert "si-chip" in plugins, (
            f"PV-01 AC-2: si-chip MUST resolve for self-update workflow "
            f"(the canonical self-improvement pipeline). Got {plugins!r}"
        )

    def test_workflow_resolution_includes_si_chip_for_nines_assisted(self) -> None:
        plugins = plugins_for_workflow("nines-assisted")
        assert "si-chip" in plugins, (
            f"PV-01 AC-2: si-chip MUST resolve for nines-assisted workflow "
            f"(the harness-backed historical evaluation seed). "
            f"Got {plugins!r}"
        )
        assert plugins == ["si-chip"]

    def test_workflow_resolution_excludes_unrelated_workflows(self) -> None:
        """si-chip must NOT resolve for workflows it isn't wired into."""
        for unrelated in (
            "feature-enhancement",
            "documentation-only",
            "demo-showcase",
            "shell-proxy",
            "hotfix",
        ):
            plugins = plugins_for_workflow(unrelated)
            assert "si-chip" not in plugins, (
                f"si-chip MUST NOT resolve for {unrelated!r}; only "
                f"skill-optimization / self-update / nines-assisted are "
                f"wired per the v9.5.0 gap analysis §3.1 D-S-1. Got {plugins!r}"
            )


# ---------------------------------------------------------------------------
# §3 — legacy plugins.yaml backward-compat
# ---------------------------------------------------------------------------


class TestSiChipInLegacyPluginsYaml:
    """Pin the legacy catalog at `plugins.yaml` (pre-v8.2.1 callers)."""

    def test_legacy_plugins_yaml_has_si_chip(self) -> None:
        raw = yaml.safe_load(_LEGACY_PLUGINS_YAML.read_text(encoding="utf-8"))
        plugins = raw.get("plugins", {})
        assert "si-chip" in plugins, (
            "v9.5.0 PV-01 contract: legacy plugins.yaml MUST also have "
            "si-chip for backward-compat with pre-v8.2.1 callers (the "
            "PluginRegistry.load() path). Both registries must agree on "
            "the canonical 4-plugin set."
        )
        si_chip = plugins["si-chip"]
        assert si_chip["repo_url"] == "https://github.com/YoRHa-Agents/Si-Chip"
        assert si_chip["min_version"] == "0.4.0"
        assert si_chip["role"] == "skill_self_improvement"

    def test_legacy_plugins_yaml_si_chip_workflows_match_runtime_registry(self) -> None:
        """Both registries must declare the same set of invoking workflows."""
        legacy_raw = yaml.safe_load(_LEGACY_PLUGINS_YAML.read_text(encoding="utf-8"))
        runtime = load_registry(_RUNTIME_PLUGINS_YAML)
        runtime_si_chip = next(p for p in runtime["plugins"] if p["id"] == "si-chip")
        legacy_workflows = set(legacy_raw["plugins"]["si-chip"]["workflows"])
        runtime_workflows = set(runtime_si_chip["invoked_by_workflows"])
        assert legacy_workflows == runtime_workflows, (
            f"v9.5.0 PV-01: legacy plugins.yaml workflows {legacy_workflows!r} "
            f"must match runtime-plugins.yaml invoked_by_workflows "
            f"{runtime_workflows!r} for the SAME plugin id. Single-source-of-truth "
            f"per A-5 SSOT registry pattern (the runtime registry is the "
            f"primary owner; legacy mirrors for backward-compat)."
        )

    def test_legacy_plugins_yaml_si_chip_role_registered_in_plugin_roles(self) -> None:
        """The new role 'skill_self_improvement' must be registered in plugin_roles."""
        raw = yaml.safe_load(_LEGACY_PLUGINS_YAML.read_text(encoding="utf-8"))
        plugin_roles = raw.get("plugin_roles", {})
        assert "skill_self_improvement" in plugin_roles, (
            "v9.5.0 PV-01: the new role 'skill_self_improvement' MUST be "
            "documented in plugin_roles section so role-based lookups work."
        )
        role = plugin_roles["skill_self_improvement"]
        assert role["provider"] == "si-chip"
        assert "skill-optimization" in role["primary_workflows"]
        assert "self-update" in role["primary_workflows"]
