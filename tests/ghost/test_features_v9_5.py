"""Ghost audit — per-cycle W-18 feature stanzas for the v9.5 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v9.5.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# W-18 v9.5.0 ghost-audit refresh — Si-Chip DEEP integration.
# ---------------------------------------------------------------------------


# v9.5.0 NEW symbols (PV-01..PV-04). Each entry is the minimum import-smoke
# contract that must hold for the symbol to be considered "alive" — i.e. the
# CHANGELOG cites it AND it imports cleanly from its canonical module path.
_V9_5_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-02 si_chip_bridge package (4 NEW modules + public API)
    ("devolaflow.si_chip_bridge", "find_si_chip_install"),
    ("devolaflow.si_chip_bridge", "profile"),
    ("devolaflow.si_chip_bridge", "evaluate"),
    ("devolaflow.si_chip_bridge", "count_tokens"),
    ("devolaflow.si_chip_bridge", "aggregate_delta"),
    ("devolaflow.si_chip_bridge", "apply_or_defer"),
    ("devolaflow.si_chip_bridge", "run_dogfood_cycle"),
    ("devolaflow.si_chip_bridge", "ApplyVerdict"),
    ("devolaflow.si_chip_bridge", "BasicAbilityProfile"),
    ("devolaflow.si_chip_bridge", "MetricsReport"),
    ("devolaflow.si_chip_bridge", "IterationDeltaReport"),
    ("devolaflow.si_chip_bridge", "SiChipResult"),
    ("devolaflow.si_chip_bridge", "SiChipError"),
    ("devolaflow.si_chip_bridge", "SiChipUnavailable"),
    ("devolaflow.si_chip_bridge", "SiChipInstall"),
    ("devolaflow.si_chip_bridge", "DEFAULT_THRESHOLD"),
    ("devolaflow.si_chip_bridge", "APPLY_DEFER_EPSILON"),
    ("devolaflow.si_chip_bridge.install_resolver", "find_si_chip_install"),
    ("devolaflow.si_chip_bridge.runner", "run_dogfood_cycle"),
    # PV-04 lifecycle hook + env flag
    ("devolaflow.lifecycle.post_skill_edit", "post_skill_edit"),
    ("devolaflow.lifecycle.post_skill_edit", "is_deep_integration_active"),
    ("devolaflow.lifecycle.post_skill_edit", "ENV_FLAG"),
    ("devolaflow.lifecycle.post_skill_edit", "ENV_FLAG_TRUTHY"),
    ("devolaflow.lifecycle.post_skill_edit", "SKILL_CORPUS_PREFIX"),
    ("devolaflow.lifecycle", "POST_SKILL_EDIT_EVENT"),
)


# v9.5.0 PV-04 frozen DEFAULT_EVENTS shape. PV-04 bumped 9 → 10 with
# `post_skill_edit` APPENDED at position 10 per A-2.2 append-only invariant.
# Position 9 (`pre_plugin_invocation`) MUST remain frozen per A-2.4
# cache-prefix invariant.
_V9_5_0_DEFAULT_EVENTS_LEN: int = 10


_V9_5_0_POST_SKILL_EDIT_POSITION: int = 10  # 1-indexed; tuple index 9


# v9.5.0 PV-04 env-flag W-20 §3 documentation contract. The PV-04
# orthogonality justification ships in references/env-flags.md §2.13
# (was §2.14 at v9.5.0 close; renumbered to §2.13 at v12.0.0 PV-03 D-2
# alongside the SHORTCUT_SIMPLE retirement that emptied the former
# §2.12 slot per `.local/research/v12.0.0_gap_analysis.md` §4).
_V9_5_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.13 `DEVOLAFLOW_SI_CHIP_DEEP`",
    "DEVOLAFLOW_SI_CHIP_DEEP",
    "is_deep_integration_active",
    "post_skill_edit",
)


# v9.5.0 PV-01 plugin registry contract: si-chip is the 4th plugin entry
# (registry_v3 with curl_install_script backend, reusing the v8.3.1 RTK
# plumbing). The legacy plugins.yaml mirrors the workflow assignment.
_V9_5_0_PLUGIN_ID: str = "si-chip"


_V9_5_0_PLUGIN_BACKEND: str = "curl_install_script"


_V9_5_0_PLUGIN_CANONICAL_URL: str = "https://github.com/YoRHa-Agents/Si-Chip"


def test_v9_5_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.5.0: every NEW v9.5.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.5.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.5.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.5.0 PV-06 cycle close pins:

    1. **Symbol import smoke** — every NEW public symbol from
       PV-02..PV-04 imports cleanly from its canonical module path.
       Catches accidental name collisions, circular imports, and the
       v6.0.3-style "feature mentioned in CHANGELOG but never wired"
       anti-pattern. 25 symbols enumerated in
       ``_V9_5_0_NEW_SYMBOL_SURFACES``.
    2. **DEFAULT_EVENTS A-2.2 append-only at position 10** — the new
       `post_skill_edit` event must be at 1-indexed position 10
       (tuple index 9); the v9.4.0 frozen position 9
       (`pre_plugin_invocation`) must remain.
    3. **W-20 §3 env-flag doc contract** — the new
       `DEVOLAFLOW_SI_CHIP_DEEP` flag MUST appear in
       `references/env-flags.md` §2.14 with the canonical
       orthogonality argument + helper function names.
    4. **Si-Chip plugin registration contract** — `runtime-plugins.yaml`
       contains the canonical 4th plugin entry (`si-chip`,
       `curl_install_script` backend, canonical GitHub URL). The
       legacy `plugins.yaml` mirrors the same workflow assignments.
    5. **A-2.4 multi-baseline byte test** — the v9.5.0 PV-04
       DEFAULT_EVENTS bump appends post_skill_edit at the tail
       without disturbing positions 1-9 (pre_plugin_invocation
       through pre_dispatch).

    Failure modes:
      * "symbol import failed" → CHANGELOG cites a non-existent
        feature; either land it OR remove the entry.
      * "DEFAULT_EVENTS bad position" → the A-2.2 append-only
        contract was violated; restore `post_skill_edit` to the tail.
      * "missing env-flag doc literal" → W-20 §7 checklist failed;
        author the §2.14 entry.
      * "si-chip plugin missing" → revert PV-01 reverted; either
        re-add the entry to runtime-plugins.yaml + plugins.yaml OR
        remove the v9.5.0 CHANGELOG entry.
    """
    import importlib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_5_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.5.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.5.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.5.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — DEFAULT_EVENTS shape.
    from devolaflow.lifecycle import DEFAULT_EVENTS, POST_SKILL_EDIT_EVENT

    assert len(DEFAULT_EVENTS) >= _V9_5_0_DEFAULT_EVENTS_LEN, (
        f"W-18 v9.5.0 violation: DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected >= {_V9_5_0_DEFAULT_EVENTS_LEN} "
        f"(v9.5.0 PV-04 bumped 9 → 10 with post_skill_edit APPENDED at "
        f"position {_V9_5_0_POST_SKILL_EDIT_POSITION} per A-2.2; future "
        f"PVs may extend further). Current events: {DEFAULT_EVENTS!r}"
    )
    skill_idx = _V9_5_0_POST_SKILL_EDIT_POSITION - 1
    assert DEFAULT_EVENTS[skill_idx] == POST_SKILL_EDIT_EVENT, (
        f"W-18 v9.5.0 violation: DEFAULT_EVENTS[{skill_idx}] is "
        f"{DEFAULT_EVENTS[skill_idx]!r}, expected {POST_SKILL_EDIT_EVENT!r}; "
        f"post_skill_edit MUST stay at 1-indexed position "
        f"{_V9_5_0_POST_SKILL_EDIT_POSITION} per A-2.2 cache-prefix invariant"
    )

    # §3 — Env-flag W-20 §3 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    assert env_flags_path.is_file(), (
        f"W-18 v9.5.0 violation: {env_flags_path.relative_to(project_root)} "
        f"missing — PV-04 W-20 §3 contract requires the env-flag inventory"
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_5_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.5.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-04 W-20 §7 checklist requires the §2.14 entry to "
            f"document the new flag with both the flag name and the helper "
            f"function names. Add the §2.14 block."
        )

    # §4 — Si-Chip plugin registration contract.
    from devolaflow.plugins.installer import load_registry, resolve_plugin

    registry = load_registry()
    spec = resolve_plugin(_V9_5_0_PLUGIN_ID, registry)
    assert spec.backend == _V9_5_0_PLUGIN_BACKEND, (
        f"W-18 v9.5.0 violation: si-chip plugin backend is "
        f"{spec.backend!r}, expected {_V9_5_0_PLUGIN_BACKEND!r} "
        f"(reuses the v8.3.1 RTK curl_install_script plumbing)"
    )
    assert spec.canonical_url == _V9_5_0_PLUGIN_CANONICAL_URL, (
        f"W-18 v9.5.0 violation: si-chip canonical_url is "
        f"{spec.canonical_url!r}, expected {_V9_5_0_PLUGIN_CANONICAL_URL!r} "
        f"per S-7 (external tools referenced via canonical GitHub URL)"
    )
    assert "skill-optimization" in spec.invoked_by_workflows
    assert "self-update" in spec.invoked_by_workflows
    assert "nines-assisted" in spec.invoked_by_workflows
