"""Ghost audit — per-cycle W-18 feature stanzas for the v9.4 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v9.4.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# W-18 v9.4.0 ghost-audit refresh — Plugin Auto-Install & Daily Upgrade.
# ---------------------------------------------------------------------------


# v9.4.0 NEW symbols (PV-02..PV-04). Each entry is the minimum import-smoke
# contract that must hold for the symbol to be considered "alive" — i.e. the
# CHANGELOG cites it AND it imports cleanly from its canonical module path.
_V9_4_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-02 lifecycle hook + env flag
    ("devolaflow.lifecycle.pre_plugin_invocation", "pre_plugin_invocation"),
    ("devolaflow.lifecycle.pre_plugin_invocation", "is_auto_install_active"),
    ("devolaflow.lifecycle.pre_plugin_invocation", "ENV_FLAG"),
    ("devolaflow.lifecycle.pre_plugin_invocation", "ENV_FLAG_TRUTHY"),
    ("devolaflow.lifecycle", "PRE_PLUGIN_INVOCATION_EVENT"),
    # PV-03 dispatcher wiring + workflow→plugin helper
    ("devolaflow.plugins.installer", "plugins_for_workflow"),
    ("devolaflow.plugins", "plugins_for_workflow"),
    # PV-04 schema v3 + upgrade surface
    ("devolaflow.plugins.installer", "upgrade_plugin"),
    ("devolaflow.plugins.installer", "refresh_all"),
    ("devolaflow.plugins.installer", "RefreshOutcome"),
    ("devolaflow.plugins.installer", "read_last_checked"),
    ("devolaflow.plugins.installer", "is_plugin_stale"),
    ("devolaflow.plugins.installer", "list_plugins"),
    ("devolaflow.plugins", "upgrade_plugin"),
    ("devolaflow.plugins", "refresh_all"),
    ("devolaflow.plugins", "RefreshOutcome"),
    ("devolaflow.plugins", "list_plugins"),
    ("devolaflow.cli", "plugins_cmd"),
)


# v9.4.0 PV-02 + PV-03 + PV-04 frozen DEFAULT_EVENTS shape. PV-02 bumped
# 8 → 9 with `pre_plugin_invocation` APPENDED at position 9 per A-2.2
# append-only invariant. The v9.4.0 W-18 lint pins the new tail (the
# v9.1.3 lint relaxed its length check to "≥ 8" with pre_handoff frozen
# at position 8 — see _V9_1_3_DEFAULT_EVENTS_MIN above).
_V9_4_0_DEFAULT_EVENTS_LEN: int = 9


_V9_4_0_PRE_PLUGIN_INVOCATION_POSITION: int = 9  # 1-indexed; tuple index 8


# v9.4.0 PV-02 env-flag W-20 §3 documentation contract. The PV-02
# orthogonality justification ships in references/env-flags.md §2.12
# (was §2.13 at v9.4.0 close; renumbered to §2.12 at v12.0.0 PV-03 D-2
# alongside the SHORTCUT_SIMPLE retirement that emptied the former
# §2.12 slot per `.local/research/v12.0.0_gap_analysis.md` §4).
_V9_4_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.12 `DEVOLAFLOW_AUTO_INSTALL_PLUGINS`",
    "DEVOLAFLOW_AUTO_INSTALL_PLUGINS",
    "is_auto_install_active",
    "pre_plugin_invocation",
)


# v9.4.0 PV-04 schema v3 contract: canonical registry must be at
# schema_version 3 AND every plugin must declare an `upgrade_cmd`. The
# `_SUPPORTED_SCHEMA_VERSIONS` constant must include {1, 2, 3} for
# backward-compat with v8.2.x + v8.3.x fixtures.
_V9_4_0_REGISTRY_SCHEMA_VERSION: int = 3


def test_v9_4_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.4.0: every NEW v9.4.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.4.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.4.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.4.0 PV-05 cycle close pins:

    1. **Symbol import smoke** — every NEW public symbol from
       PV-02..PV-04 imports cleanly from its canonical module path.
       Catches accidental name collisions, circular imports, and the
       v6.0.3-style "feature mentioned in CHANGELOG but never wired"
       anti-pattern. 18 symbols enumerated in
       ``_V9_4_0_NEW_SYMBOL_SURFACES``.
    2. **DEFAULT_EVENTS A-2.2 append-only at position 9** — the new
       `pre_plugin_invocation` event must be at 1-indexed position 9
       (tuple index 8); the v9.1.3 frozen position 8 (`pre_handoff`)
       must remain.
    3. **W-20 §3 env-flag doc contract** — the new
       `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` flag MUST appear in
       `references/env-flags.md` §2.13 with the canonical
       orthogonality argument + helper function names.
    4. **Schema v3 contract** — `runtime-plugins.yaml` is at
       schema_version 3 AND every plugin declares an `upgrade_cmd`
       AND `_SUPPORTED_SCHEMA_VERSIONS` includes {1, 2, 3} (backward
       compat preserved).
    5. **`ensure_plugin` dispatcher hit count** — the dead-wire ghost
       is closed: `ensure_plugin` is now referenced from at least 4
       distinct files in `src/devolaflow/` (the AC-3 acceptance
       criterion from the v9.4.0 gap analysis §6).

    Failure modes:
      * "symbol import failed" → CHANGELOG cites a non-existent
        feature; either land it OR remove the entry.
      * "DEFAULT_EVENTS bad position" → the A-2.2 append-only
        contract was violated; restore `pre_plugin_invocation` to
        the tail.
      * "missing env-flag doc literal" → W-20 §7 checklist failed;
        author the §2.13 entry.
      * "schema_version mismatch" → either the v3 bump was lost OR a
        future PV bumped to v4 without updating this lint (acceptable
        — update the constant).
      * "ensure_plugin hit count regression" → the dispatcher wiring
        from PV-03 was removed; restore the `feedback.py` chain.
    """
    import importlib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_4_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.4.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.4.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.4.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — DEFAULT_EVENTS shape.
    from devolaflow.lifecycle import DEFAULT_EVENTS, PRE_PLUGIN_INVOCATION_EVENT

    assert len(DEFAULT_EVENTS) >= _V9_4_0_DEFAULT_EVENTS_LEN, (
        f"W-18 v9.4.0 violation: DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected >= {_V9_4_0_DEFAULT_EVENTS_LEN} "
        f"(v9.4.0 PV-02 bumped 8 → 9 with pre_plugin_invocation APPENDED "
        f"at position {_V9_4_0_PRE_PLUGIN_INVOCATION_POSITION} per A-2.2; "
        f"future PVs may extend further). Current events: {DEFAULT_EVENTS!r}"
    )
    plugin_idx = _V9_4_0_PRE_PLUGIN_INVOCATION_POSITION - 1
    assert DEFAULT_EVENTS[plugin_idx] == PRE_PLUGIN_INVOCATION_EVENT, (
        f"W-18 v9.4.0 violation: DEFAULT_EVENTS[{plugin_idx}] is "
        f"{DEFAULT_EVENTS[plugin_idx]!r}, expected {PRE_PLUGIN_INVOCATION_EVENT!r}; "
        f"pre_plugin_invocation MUST stay at 1-indexed position "
        f"{_V9_4_0_PRE_PLUGIN_INVOCATION_POSITION} per A-2.2 cache-prefix invariant"
    )

    # §3 — Env-flag W-20 §3 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    assert env_flags_path.is_file(), (
        f"W-18 v9.4.0 violation: {env_flags_path.relative_to(project_root)} "
        f"missing — PV-02 W-20 §3 contract requires the env-flag inventory"
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_4_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.4.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-02 W-20 §7 checklist requires the §2.13 entry to "
            f"document the new flag with both the flag name and the helper "
            f"function names. Add the §2.13 block."
        )

    # §4 — Schema v3 contract.
    from devolaflow.plugins import load_registry
    from devolaflow.plugins.installer import _SUPPORTED_SCHEMA_VERSIONS

    assert {1, 2, 3}.issubset(_SUPPORTED_SCHEMA_VERSIONS), (
        f"W-18 v9.4.0 violation: _SUPPORTED_SCHEMA_VERSIONS = "
        f"{_SUPPORTED_SCHEMA_VERSIONS!r}; v9.4.0 PV-04 requires {{1, 2, 3}} "
        f"(v1 + v2 backward compat + v3 new bump)"
    )
    registry = load_registry()
    assert registry["schema_version"] >= _V9_4_0_REGISTRY_SCHEMA_VERSION, (
        f"W-18 v9.4.0 violation: canonical runtime-plugins.yaml is at "
        f"schema_version {registry['schema_version']!r}; v9.4.0 PV-04 "
        f"requires >= {_V9_4_0_REGISTRY_SCHEMA_VERSION}"
    )
    for entry in registry["plugins"]:
        assert "upgrade_cmd" in entry, (
            f"W-18 v9.4.0 violation: plugin {entry.get('id')!r} missing "
            f"upgrade_cmd in v3 canonical registry. The PV-04 contract "
            f"requires every canonical entry to declare upgrade_cmd "
            f"(legacy v1 + v2 fixtures may omit it; the canonical v3 "
            f"file MUST include it)."
        )

    # §5 — ensure_plugin dispatcher hit count (the AC-3 acceptance criterion).
    src_dir = project_root / "src" / "devolaflow"
    files_with_hits: list[Path] = []
    for py_file in src_dir.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "ensure_plugin" in text:
            files_with_hits.append(py_file)
    assert len(files_with_hits) >= 4, (
        f"W-18 v9.4.0 violation: `ensure_plugin` referenced in only "
        f"{len(files_with_hits)} files; v9.4.0 PV-03 contract requires >= 4 "
        f"(installer.py + plugins/__init__.py + lifecycle/pre_plugin_invocation.py + "
        f"≥ 1 dispatcher). The dead-wire ghost reopened — restore the "
        f"feedback.py wiring from PV-03. Files found: "
        f"{[str(p.relative_to(project_root)) for p in files_with_hits]!r}"
    )
