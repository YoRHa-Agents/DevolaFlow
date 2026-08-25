"""Ghost audit — per-cycle W-18 feature stanzas for the v9.7 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v9.7.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# W-18 v9.7.0 ghost-audit refresh — Performance Overhaul #2.
# ---------------------------------------------------------------------------


# v9.7.0 NEW symbols (PV-02..PV-04). Each entry is the minimum import-smoke
# contract that must hold for the symbol to be considered "alive" — i.e. the
# CHANGELOG cites it AND it imports cleanly from its canonical module path.
_V9_7_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-02 predecessor summary delta-compression
    ("devolaflow.compressor", "dedup_predecessor_summaries"),
    ("devolaflow.compressor", "DEDUP_HASH_PREFIX_LENGTH"),
    ("devolaflow.compressor.transforms", "dedup_predecessor_summaries"),
    ("devolaflow.compressor.transforms", "_hash_summary"),
    ("devolaflow.compressor.transforms", "_build_dedup_index"),
    # PV-03 auto-wired async wave dispatch (defined on devolaflow.feedback at
    # v9.7.0; moved to the ADR-006 owner module devolaflow.dispatch at
    # v14.5.0; the old-path re-export shim was retired in v17.0.0)
    ("devolaflow.dispatch", "dispatch_wave_tasks"),
    # PV-04 selector cache warmup
    ("devolaflow.task_adaptive_selector", "warmup_selector_cache"),
    ("devolaflow.task_adaptive_selector", "WARMUP_ENV_FLAG"),
    ("devolaflow.task_adaptive_selector", "WARMUP_TRUTHY_VALUE"),
    ("devolaflow.task_adaptive_selector", "WARMUP_TASK_TYPES"),
    ("devolaflow.task_adaptive_selector", "WARMUP_ROUND_NUMS"),
)


# v9.7.0 PV-02 schema-v6 invariants — canonical_order length 17, version 6.
_V9_7_0_CANONICAL_ORDER_LENGTH: int = 17


_V9_7_0_LAYOUT_VERSION: int = 6


_V9_7_0_NEW_CANONICAL_KEY: str = "predecessor_dedup_ledger"


# v9.7.0 PV-05 baseline files — every CHANGELOG entry that cites the
# cumulative perf gain pins these files. The W-18 contract requires them
# to be present + parseable.
_V9_7_0_BASELINE_PATHS: tuple[Path, ...] = (
    Path("docs/cycle-archive/v15.2.0/evobench-baselines/v9.7.0_latency.json"),
    Path("docs/cycle-archive/v15.2.0/evobench-baselines/v9.7.0_baseline.json"),
    Path("docs/cycle-archive/v15.2.0/evobench-baselines/v9.7.0_latency_intermediate.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v9.7.0.yaml"),
)


# v9.7.0 PV-04 env-flag W-20 §7 documentation contract. The §2.14 anchor
# was §2.15 at v9.7.0 close; renumbered to §2.14 at v12.0.0 PV-03 D-2
# alongside the SHORTCUT_SIMPLE retirement that emptied the former §2.12
# slot per `.local/research/v12.0.0_gap_analysis.md` §4.
_V9_7_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = (
    "### 2.14 `DEVOLAFLOW_WARMUP`",
    "DEVOLAFLOW_WARMUP",
    "warmup_selector_cache",
    "WARMUP_TASK_TYPES",
)


# v9.7.0 PV-03 auto-wire reference doc anchor.
_V9_7_0_REFERENCE_DOC_ANCHORS: tuple[tuple[str, str], ...] = (
    (
        "workflow-system/agent/references/execution-protocol.md",
        "## 13. L2-Wave Async Dispatch Auto-Wire (v9.7.0+)",
    ),
)


def test_v9_7_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.7.0: every NEW v9.7.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.7.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.7.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.7.0 PV-06 cycle close pins:

    1. **NEW public symbols (PV-02..PV-04)** import cleanly from their
       canonical module paths. The 11 entries cover predecessor dedup
       (PV-02), async wave auto-wire (PV-03), and selector warmup
       (PV-04).
    2. **Schema v6 17-element canonical_order (PV-02)** —
       schemas/lean-dispatch.yaml#layout_invariant.version is 6 and
       canonical_order length is 17 with predecessor_dedup_ledger at
       position 17. The frozen-prefix invariant (positions 1-12) is
       PRESERVED (the v8.4.0 / v9.2.0 / v9.3.0 byte-baselines all
       continue to pass per A-2.4 multi-baseline byte test).
    3. **PV-05 baseline files** exist on disk and parse cleanly. The
       CHANGELOG cites the cumulative 97.5% select_context.p95
       improvement which is derived FROM these files; missing files
       = unprovable claim.
    4. **PV-04 env-flag W-20 §7 documentation contract** — the
       env-flags.md §2.15 entry header + flag name + helper function
       names appear together in the file.
    5. **PV-03 reference doc anchor** — the §13 heading appears
       verbatim in execution-protocol.md.

    Failure modes:
      * "symbol import failed" → CHANGELOG cites a non-existent
        feature; either land it or remove the entry.
      * "canonical_order length wrong" → A-2 frozen prefix or
        position-17 APPEND regressed.
      * "missing baseline file" → run the PV-01 / PV-05 latency
        harness CLI to regenerate; OR the cycle didn't honour the
        wholesale-regen-or-per-PV-baseline invariant.
      * "missing env-flag doc literal" → W-20 §7 checklist failed;
        author the §2.15 block.
      * "missing reference-doc anchor" → PV-03 reference doc edit
        was reverted; re-author the §13 subsection.
    """
    import importlib

    import yaml as yaml_lib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_7_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.7.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.7.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.7.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — Schema v6 17-element canonical_order.
    schema_path = project_root / "schemas" / "lean-dispatch.yaml"
    schema = yaml_lib.safe_load(schema_path.read_text(encoding="utf-8"))
    canonical = schema["layout_invariant"]["canonical_order"]
    assert len(canonical) == _V9_7_0_CANONICAL_ORDER_LENGTH, (
        f"W-18 v9.7.0 violation: canonical_order length is {len(canonical)}, "
        f"expected {_V9_7_0_CANONICAL_ORDER_LENGTH} (PV-02 schema v6 APPEND)"
    )
    assert canonical[-1] == _V9_7_0_NEW_CANONICAL_KEY, (
        f"W-18 v9.7.0 violation: last canonical key is {canonical[-1]!r}, "
        f"expected {_V9_7_0_NEW_CANONICAL_KEY!r} (PV-02 APPEND at position 17)"
    )
    assert schema["layout_invariant"]["version"] == _V9_7_0_LAYOUT_VERSION, (
        f"W-18 v9.7.0 violation: layout_invariant.version is "
        f"{schema['layout_invariant']['version']}, expected "
        f"{_V9_7_0_LAYOUT_VERSION} (PV-02 bumped 5 → 6)"
    )

    # §3 — PV-05 baseline files exist + parse.
    for baseline_rel in _V9_7_0_BASELINE_PATHS:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v9.7.0 violation: archived PV-05 evidence or layout "
            f"witness {baseline_rel} is missing."
        )
        if baseline_path.suffix == ".json":
            import json as _json

            _json.loads(baseline_path.read_text(encoding="utf-8"))
        elif baseline_path.suffix == ".yaml":
            yaml_lib.safe_load(baseline_path.read_text(encoding="utf-8"))

    # §4 — PV-04 env-flag W-20 §7 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_7_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.7.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-04 W-20 §7 checklist requires the §2.15 entry to "
            f"document the new flag with both the flag name and the "
            f"helper function names. Add the §2.15 block."
        )

    # §5 — PV-03 reference doc anchor.
    for rel_path, anchor in _V9_7_0_REFERENCE_DOC_ANCHORS:
        ref_file = project_root / rel_path
        assert ref_file.is_file(), f"W-18 v9.7.0 violation: reference doc {rel_path} missing"
        text = ref_file.read_text(encoding="utf-8")
        assert anchor in text, (
            f"W-18 v9.7.0 violation: anchor {anchor!r} missing from "
            f"{rel_path}. PV-03 cited this anchor in the CHANGELOG; "
            f"either restore the §13 subsection OR remove the CHANGELOG "
            f"entry."
        )
