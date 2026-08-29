"""Registry-walk smoke tests for the registered runtime plugins.

Closes D-P-4 from `.local/research/v10.2.0_gap_analysis.md` §3.1:
v9.4.0 PV-04 wired schema v3 + 4 plugins; v10.1.0 added zero plugin
work. No CI step had confirmed the 4 registered plugins still resolve
cleanly via `resolve_plugin` until this smoke file landed.

Test surface (pure registry walk + dataclass shape; NO subprocess):

§1 — schema_version is 4 (v15.2.0 B-6 bump); `defaults.upgrade_check_frequency_hours` is 24.
§2 — the 5 expected plugin IDs are present in canonical order.
§3 — every `resolve_plugin(p["id"], registry)` returns a
     RuntimePluginSpec whose backend is one of the 3 supported values
     (pip / npm_then_init / curl_install_script).
§4 — every plugin carries a non-empty `canonical_url` (S-7 compliance).
§5 — the si-chip version_check_cmd introduced by v10.2.0 PV-01 (D-P-3)
     NO LONGER contains the hardcoded `echo si-chip/0.4.0` string AND
     WHEN si-chip is installed locally, the new command probes a real
     version from the SKILL.md frontmatter (skip if si-chip absent).

Source: `.local/research/v10.2.0_gap_analysis.md` §3.1 D-P-4 +
`.local/research/v10.2.0_cycle_plan.md` §3 PV-01.
External tool reference (S-7): https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from devolaflow.plugins import load_registry, resolve_plugin
from devolaflow.plugins.installer import _SUPPORTED_BACKENDS, RuntimePluginSpec

_EXPECTED_PLUGIN_IDS: tuple[str, ...] = (
    "ui-pro",
    "rtk",
    "si-chip",
    "codegraph",
    "impeccable",
)


def test_registry_schema_version_is_3() -> None:
    """Registry schema pin: v3 baseline bumped to v4 by the v15.2.0 B-6 sweep.

    (Function name kept for W-17 diff hygiene — a rename would count as a
    NEW test function in the `+def test_` cap accounting.)
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


def test_registry_contains_expected_6_plugin_ids() -> None:
    """The active registry contains exactly five plugins in canonical order."""
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


def test_si_chip_version_check_cmd_no_longer_hardcoded() -> None:
    """D-P-3 closure: si-chip version_check_cmd reads the installed
    SKILL.md frontmatter instead of echoing a fixed '0.4.0' string.

    The pre-v10.2.0 heuristic was
      `... || ... && echo si-chip/0.4.0`
    which ALWAYS reported 0.4.0 regardless of what was installed. The
    v10.2.0 PV-01 probe calls into
    `devolaflow.si_chip_bridge.install_resolver.read_installed_si_chip_version`.
    This test pins that the hardcoded string is GONE and the probe
    references the real helper.
    """
    registry = load_registry()
    si_chip = resolve_plugin("si-chip", registry)
    assert "echo si-chip/0.4.0" not in si_chip.version_check_cmd, (
        "D-P-3 violation: si-chip version_check_cmd still contains the "
        "pre-v10.2.0 hardcoded `echo si-chip/0.4.0` heuristic. "
        "Restore the read_installed_si_chip_version probe per "
        "v10.2.0 PV-01 cycle-plan §3."
    )
    assert "read_installed_si_chip_version" in si_chip.version_check_cmd, (
        "D-P-3 violation: si-chip version_check_cmd should invoke "
        "`read_installed_si_chip_version` via the bridge module; current "
        f"cmd = {si_chip.version_check_cmd!r}"
    )


def test_si_chip_version_check_cmd_executes_cleanly_when_installed(
    tmp_path: Path,
) -> None:
    """When Si-Chip is installed locally, the new version_check_cmd
    emits a parseable `si-chip/<version>` line.

    Skip when Si-Chip is not reachable from the test environment —
    the probe requires either the default `$HOME/.cursor/skills/si-chip[/si-chip]/`
    install OR the `$SI_CHIP_HOME` / `$DEVOLAFLOW_SI_CHIP_FALLBACK_DIR`
    env-vars to point at an installed payload. This matches the CI-safe
    contract `_probe_version` applies: missing install → returncode
    nonzero → "version unknown" (not a hard failure).

    The test runs the command from the repository root (where
    `src/devolaflow/` is importable) — the v10.2.0 PV-01 probe requires
    this CWD invariant per the yaml entry comment.
    """
    from devolaflow.si_chip_bridge import find_si_chip_install

    if find_si_chip_install() is None:
        pytest.skip("si-chip not installed — probe contract verified offline")

    registry = load_registry()
    si_chip = resolve_plugin("si-chip", registry)
    repo_root = Path(__file__).resolve().parent.parent
    # The registry command targets `python3` on a >=3.11 operator machine
    # (pyproject requires-python). Prepend the running interpreter's dir so
    # dev machines whose system python3 predates 3.11 resolve a valid one —
    # same environment fix as tests/test_install_sh.py.
    env = dict(os.environ)
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
    proc = subprocess.run(
        ["bash", "-c", si_chip.version_check_cmd],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, (
        f"si-chip version_check_cmd failed (returncode={proc.returncode}); "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert proc.stdout.strip().startswith("si-chip/"), (
        f"si-chip version_check_cmd stdout must start with 'si-chip/'; got {proc.stdout.strip()!r}"
    )


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
# v12.5.0 PV-03 D-1.1 — codegraph runtime plugin entry smoke
# ---------------------------------------------------------------------------


def test_codegraph_runtime_entry_smoke() -> None:
    """v12.5.0 PV-03: codegraph runtime entry has the contracted shape.

    Pins the 5 contract fields documented at
    `.local/research/v12.5.0_codegraph_benefit_analysis.md` §3 surface 2:
      * backend = npm_then_init (reuses the ui-pro precedent)
      * package = @colbymchenry/codegraph
      * min_version = 0.9.3
      * canonical_url = https://github.com/colbymchenry/codegraph
      * invoked_by_workflows includes the 4 analyze-stage templates
    """
    registry = load_registry()
    spec = resolve_plugin("codegraph", registry)
    assert spec.id == "codegraph"
    assert spec.backend == "npm_then_init"
    assert spec.package == "@colbymchenry/codegraph"
    assert spec.min_version == "0.9.3"
    assert spec.canonical_url == "https://github.com/colbymchenry/codegraph"
    expected_workflows = {
        "repo-init",
        "onboarding",
        "security-audit",
        "product-verification",
    }
    assert expected_workflows.issubset(set(spec.invoked_by_workflows or [])), (
        f"v12.5.0 PV-03 D-1.1: codegraph invoked_by_workflows must include "
        f"all 4 analyze-stage templates; missing: "
        f"{expected_workflows - set(spec.invoked_by_workflows or [])}"
    )


# ---------------------------------------------------------------------------
# v13.0.0 — impeccable runtime plugin entry smoke
# ---------------------------------------------------------------------------


def test_impeccable_runtime_entry_smoke() -> None:
    """v13.0.0: impeccable runtime entry has the contracted shape.

    Pins the contract fields for the 6th plugin:
      * backend = npm_then_init (reuses the ui-pro / codegraph precedent)
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
