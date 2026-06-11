"""Ghost audit — per-cycle W-18 feature stanzas for the v13.0 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v13.0.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.ghost.test_registries import _SF4_REFERENCE_SET

# ---------------------------------------------------------------------------
# W-18 stanzas for v13.0.0 — impeccable plugin + web-design workflow +
# bundled global plugin install
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v13.0.0
# CHANGELOG entry mentioning the impeccable plugin / web-design workflow /
# bundled install. These stanzas pin the v13.0.0 MAJOR-cycle surface:
#
# * workflow-system/agent/plugins.yaml carries the `impeccable:` block under
#   `plugins:` (role ui_refinement) + the NEW `plugin_roles.ui_refinement`
#   block (6th role; provider=impeccable).
# * workflow-system/agent/knowledge/runtime-plugins.yaml `plugins:` list
#   carries the `id: impeccable` entry (backend npm_then_init); ui-pro's
#   invoked_by_workflows gains web-design.
# * workflow-system/agent/knowledge/reference-dependencies.yaml
#   `active_tracking:` list (13th entry) carries the impeccable reference pin.
# * workflow-system/agent/references/impeccable.md exists (23rd SF-4 reference).
# * workflow-system/agent/templates/builtin/web-design.yaml exists + is
#   registered in registry.yaml.
# * src/devolaflow/init_project.py declares install_plugins + _parse_no_plugins.
#
# Source: .local/research/v13.0.0_gap_analysis.md §2-§3.
# ---------------------------------------------------------------------------


def test_v13_0_0_impeccable_registered(project_root: Path) -> None:
    """W-18 v13.0.0: impeccable plugin landed across 3 registries + reference doc.

    (a) plugins.yaml carries the impeccable block + ui_refinement role.
    (b) runtime-plugins.yaml carries the impeccable entry (npm_then_init).
    (c) reference-dependencies.yaml carries the 13th active_tracking entry.
    (d) references/impeccable.md exists (23rd SF-4 reference).
    (e) Companion test files exist.
    """

    # --- (a) plugins.yaml ---------------------------------------------
    plugins_path = project_root / "workflow-system/agent/plugins.yaml"
    payload = yaml.safe_load(plugins_path.read_text(encoding="utf-8"))
    plugins = payload.get("plugins") or {}
    assert "impeccable" in plugins, (
        "W-18 v13.0.0 violation: plugins.yaml missing top-level `impeccable` block."
    )
    imp = plugins["impeccable"]
    assert imp.get("role") == "ui_refinement"
    assert imp.get("min_version") == "2.0.0"
    assert imp.get("repo_url") == "https://github.com/pbakaus/impeccable"
    roles = payload.get("plugin_roles") or {}
    assert "ui_refinement" in roles, (
        "W-18 v13.0.0 violation: plugins.yaml missing plugin_roles.ui_refinement (6th role)."
    )
    assert roles["ui_refinement"].get("provider") == "impeccable"

    # --- (b) runtime-plugins.yaml -------------------------------------
    runtime_path = project_root / "workflow-system/agent/knowledge/runtime-plugins.yaml"
    runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    runtime_plugins = runtime.get("plugins") or []
    by_id = {p.get("id"): p for p in runtime_plugins if isinstance(p, dict)}
    assert "impeccable" in by_id, (
        "W-18 v13.0.0 violation: runtime-plugins.yaml missing `id: impeccable`."
    )
    assert by_id["impeccable"].get("backend") == "npm_then_init"
    assert "web-design" in (by_id["impeccable"].get("invoked_by_workflows") or [])
    # ui-pro now also cites web-design (designs before impeccable refines).
    assert "web-design" in (by_id["ui-pro"].get("invoked_by_workflows") or []), (
        "W-18 v13.0.0 violation: ui-pro invoked_by_workflows must include web-design."
    )

    # --- (c) reference-dependencies.yaml ------------------------------
    refs_path = project_root / "workflow-system/agent/knowledge/reference-dependencies.yaml"
    refs = yaml.safe_load(refs_path.read_text(encoding="utf-8"))
    active_ids = {e.get("id") for e in (refs.get("active_tracking") or []) if isinstance(e, dict)}
    assert "impeccable" in active_ids, (
        "W-18 v13.0.0 violation: reference-dependencies.yaml missing "
        "impeccable active_tracking entry."
    )

    # --- (d) reference doc + SF-4 set ---------------------------------
    assert (project_root / "workflow-system/agent/references/impeccable.md").is_file(), (
        "W-18 v13.0.0 violation: references/impeccable.md missing — release blocker."
    )
    assert "impeccable.md" in set(_SF4_REFERENCE_SET), (
        "W-18 v13.0.0 violation: _SF4_REFERENCE_SET must include impeccable.md (23rd entry)."
    )

    # --- (e) companion tests ------------------------------------------
    assert (project_root / "tests/test_impeccable_reference_doc.py").is_file()
    smoke = (project_root / "tests/test_runtime_plugins_smoke.py").read_text(encoding="utf-8")
    assert "test_impeccable_runtime_entry_smoke" in smoke


def test_v13_0_0_web_design_workflow(project_root: Path) -> None:
    """W-18 v13.0.0: web-design template exists + registered + wires both plugins."""

    tpl_path = project_root / "workflow-system/agent/templates/builtin/web-design.yaml"
    assert tpl_path.is_file(), "W-18 v13.0.0 violation: web-design.yaml missing — release blocker."
    tpl = yaml.safe_load(tpl_path.read_text(encoding="utf-8"))
    assert tpl["metadata"]["name"] == "web-design"
    stage_by_id = {s["id"]: s for s in tpl["stages"]}
    assert stage_by_id["design"]["config"]["ensure_plugins"] == ["ui-pro"]
    assert stage_by_id["refine"]["config"]["ensure_plugins"] == ["impeccable"]
    assert stage_by_id["verify"]["config"]["ensure_plugins"] == ["impeccable"]

    registry = yaml.safe_load(
        (project_root / "workflow-system/agent/templates/registry.yaml").read_text(encoding="utf-8")
    )
    names = {e["name"] for e in registry["templates"]}
    assert "web-design" in names, (
        "W-18 v13.0.0 violation: web-design missing from templates/registry.yaml."
    )
    assert (project_root / "tests/test_template_web_design.py").is_file()


def test_v13_0_0_global_plugin_install(project_root: Path) -> None:
    """W-18 v13.0.0: install_plugins + --no-plugins land in init_project + install.sh."""
    init_text = (project_root / "src/devolaflow/init_project.py").read_text(encoding="utf-8")
    assert "def install_plugins(scope: str) -> None:" in init_text, (
        "W-18 v13.0.0 violation: init_project.py missing install_plugins(scope)."
    )
    assert "def _parse_no_plugins(argv: list[str]) -> bool:" in init_text, (
        "W-18 v13.0.0 violation: init_project.py missing _parse_no_plugins."
    )
    # Wired into main() default-ON for --global.
    assert 'if scope == "global" and not _parse_no_plugins' in init_text, (
        "W-18 v13.0.0 violation: install_plugins not wired into main() for --global."
    )
    install_sh = (project_root / "scripts/install.sh").read_text(encoding="utf-8")
    assert "--no-plugins" in install_sh, (
        "W-18 v13.0.0 violation: install.sh missing --no-plugins flag."
    )
    assert "install_plugins()" in install_sh
