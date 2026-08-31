"""Ghost audit — per-cycle W-18 feature stanzas for the v9.3 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v9.3.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# W-18 v9.3.0 ghost-audit refresh — Performance Overhaul #1.
# ---------------------------------------------------------------------------


# v9.3.0 Performance Overhaul #1 retained symbols (PV-03..PV-05). The PV-02
# EvoBench latency harness was intentionally retired; its JSON evidence remains
# in the v15.2.0 cycle archive and must not be imported as live code.
_V9_3_0_NEW_SYMBOL_SURFACES: tuple[tuple[str, str], ...] = (
    # PV-03 LRU cache
    ("devolaflow.task_adaptive_selector", "_load_profiles_cached"),
    ("devolaflow.task_adaptive_selector", "_load_skill_md_cached"),
    ("devolaflow.task_adaptive_selector", "_estimate_tokens_tiktoken_cached"),
    ("devolaflow.task_adaptive_selector", "_estimate_tokens_fallback_cached"),
    # PV-04 compressor split
    ("devolaflow.compressor", "assert_dispatch_layout"),
    ("devolaflow.compressor.layout", "assert_dispatch_layout"),
    ("devolaflow.compressor.patterns", "PRESERVE_LIST"),
    ("devolaflow.compressor.transforms", "compress_message"),
    # PV-05 async dispatch executor
    ("devolaflow.agent_workspace.dispatch_executor", "AsyncDispatchExecutor"),
    ("devolaflow.agent_workspace.dispatch_executor", "TaskOutcome"),
    ("devolaflow.agent_workspace.dispatch_executor", "ExecutorError"),
    ("devolaflow.agent_workspace.dispatch_executor", "DEFAULT_MAX_CONCURRENCY"),
    # PV-06 simple-task auto-shortcut — RETIRED at v12.0.0 PV-03 D-2 per
    # ``.local/research/v12.0.0_gap_analysis.md`` §4 + the v11.1.0
    # retrospective §3 D-2 telegraph. The 5 PV-06 symbols
    # (``shortcut_from_env`` / ``shortcut_verdict`` / ``ShortcutVerdict`` /
    # ``SHORTCUT_FLAG_NAME`` / ``SHORTCUT_FLAG_TRUTHY``) were removed from
    # the import-smoke set in the same PV that deleted them; the v12.0.0
    # PV-03 retirement lint
    # ``test_v12_0_0_pv03_d2_shortcut_simple_retirement`` carries the
    # NEGATIVE pins (asserts the symbols do NOT appear at module scope).
)


# v9.3.0 PV-02 latency baselines — every CHANGELOG entry that cites the
# numerical perf gain pins these files. The W-18 contract requires them
# to be present + parseable.
_V9_3_0_LATENCY_BASELINE_PATHS: tuple[Path, ...] = (
    Path("docs/cycle-archive/v15.2.0/evobench-baselines/v9.3.0_latency.json"),
    Path("docs/cycle-archive/v15.2.0/evobench-baselines/v9.3.0_baseline.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v9.3.0.yaml"),
)


# v9.3.0 PV-06 env-flag documentation pins — RETIRED at v12.0.0 PV-03 D-2
# alongside the source-side surface deletion. The §2.12 entry in
# ``references/env-flags.md`` was removed (subsequent §2.13/§2.14/§2.15
# subsections renumbered to §2.12/§2.13/§2.14 to close the gap); the
# v12.0.0 PV-03 retirement lint
# ``test_v12_0_0_pv03_d2_shortcut_simple_retirement`` carries the NEGATIVE
# pin (asserts the literal ``DEVOLAFLOW_SIMPLE_SHORTCUT`` does NOT appear
# in the env-flag inventory). The empty tuple here keeps the §3 loop a
# zero-iteration no-op so the v9.3.0 ghost-audit lint stays GREEN
# post-retirement.
_V9_3_0_ENV_FLAG_DOC_LITERALS: tuple[str, ...] = ()


def test_v9_3_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.3.0: every NEW v9.3.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.3.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.3.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.3.0 PV-07 cycle close pins:

    1. Every retained public symbol from PV-03..PV-05 imports cleanly
       from its canonical module path (the PV-02 EvoBench latency harness
       and the PV-06 simple-task auto-shortcut are retired; the latter's
       symbols are RETIRED at v12.0.0 PV-03 D-2 per the v11.1.0
       retrospective §3 D-2 telegraph; the negative-pin lives in the
       sister test ``test_v12_0_0_pv03_d2_shortcut_simple_retirement``).
       Catches accidental name collisions, circular imports, and the
       v6.0.3-style "feature mentioned in CHANGELOG but never wired"
       anti-pattern.
    2. The 3 W-16 wholesale baseline files (composite + latency + layout
       invariant) exist on disk. The CHANGELOG cites the empirical
       perf-gain numbers (97.5% select_context p95 improvement) which
       are derived FROM these files; missing files = unprovable claim.
    3. The v9.3.0 PV-06 env-flag documentation lint is RETIRED at
       v12.0.0 PV-03 D-2 alongside the source-side retirement. The §3
       loop is a no-op (the literals tuple is empty); the canonical
       inventory check moved to the sister negative-pin lint
       ``test_v12_0_0_pv03_d2_shortcut_simple_retirement``.
    4. The PV-04 compressor split remains present alongside the additive
       `context.py` and `evidence.py` modules. A future PV that accidentally
       collapses the split or changes the package shape would break this test.

    Failure modes:
      * "symbol import failed" → the CHANGELOG cites a feature that
        doesn't exist; either land the feature or remove the entry.
      * "missing baseline file" → restore the archived evidence or the
        immutable layout witness; do not regenerate retired EvoBench data.
      * "compressor package member count drift" → either accept the
        additive structure (and update this test in the same PR) OR
        restore the historical split.
    """
    import importlib

    # §1 — Symbol import smoke.
    for module_name, symbol_name in _V9_3_0_NEW_SYMBOL_SURFACES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"W-18 v9.3.0 violation: module {module_name!r} failed to "
                f"import: {exc}. The CHANGELOG cites symbols from this "
                f"module; either land the module OR remove the CHANGELOG entry."
            )
        assert hasattr(module, symbol_name), (
            f"W-18 v9.3.0 violation: {module_name}.{symbol_name} missing. "
            f"The v9.3.0 CHANGELOG cites this symbol; ghost-audit blocks "
            f"the merge until either the symbol is landed OR the CHANGELOG "
            f"entry is removed."
        )

    # §2 — W-16 wholesale baseline file presence + parseability.
    import json

    for baseline_rel in _V9_3_0_LATENCY_BASELINE_PATHS:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v9.3.0 violation: archived PV-02 evidence or layout "
            f"witness {baseline_rel} is missing."
        )
        # Smoke-parse to catch corrupt files.
        if baseline_path.suffix == ".json":
            json.loads(baseline_path.read_text(encoding="utf-8"))
        elif baseline_path.suffix == ".yaml":
            yaml.safe_load(baseline_path.read_text(encoding="utf-8"))

    # §3 — PV-06 env-flag W-20 §7 documentation contract.
    env_flags_path = project_root / "workflow-system" / "agent" / "references" / "env-flags.md"
    assert env_flags_path.is_file(), (
        f"W-18 v9.3.0 violation: {env_flags_path.relative_to(project_root)} "
        f"missing — PV-06 W-20 §7 contract requires the env-flag inventory"
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for literal in _V9_3_0_ENV_FLAG_DOC_LITERALS:
        assert literal in env_flags_text, (
            f"W-18 v9.3.0 violation: env-flags.md missing literal {literal!r}. "
            f"The PV-06 W-20 §7 checklist requires the §2.12 entry to "
            f"document the new flag with both the flag name and the "
            f"helper function names. Add the §2.12 block."
        )

    # §4 — PV-04 split plus additive context/evidence package modules.
    compressor_pkg = project_root / "src" / "devolaflow" / "compressor"
    assert compressor_pkg.is_dir(), (
        "W-18 v9.3.0 violation: src/devolaflow/compressor/ is not a directory. "
        "PV-04 split compressor.py into a package; restore the package shape."
    )
    # v21.0.0 T2 adds bounded evidence transport as an additive package module.
    expected_pkg_files = {
        "__init__.py",
        "context.py",
        "evidence.py",
        "layout.py",
        "patterns.py",
        "transforms.py",
    }
    actual_pkg_files = {p.name for p in compressor_pkg.iterdir() if p.is_file()}
    assert actual_pkg_files == expected_pkg_files, (
        f"W-18 v21.0.0 T2 violation: compressor package member set drifted. "
        f"Expected exactly {sorted(expected_pkg_files)!r}; got "
        f"{sorted(actual_pkg_files)!r}. The bounded evidence module must remain "
        f"alongside the historical split."
    )

    # §5 — Compressor v9.3.0 LOC sanity (the cycle's headline maintainability claim).
    # The original compressor.py was 2541 LOC; the post-split package is ≤ 3000 LOC
    # total (some overhead from re-export shims + module preambles is expected and
    # accepted). Catches a future PV that bloats one of the modules > 2000 LOC
    # individually (a sign that the split's "thematically tight" contract is
    # decaying).
    # transforms.py is the largest. Cap raised 2200 → 2300 in v9.7.0 PV-02
    # to accommodate the new ``dedup_predecessor_summaries`` helper +
    # 2 internal helpers (~220 LOC of canonical, well-isolated v9.7.0
    # PV-02 deliverable per A-2.2 append-only). Retrospective coverage
    # in `.local/research/v9.7.0_perf_research.md` §2 + the v9.7.0
    # CHANGELOG entry under PV-02. Cap raised 2300 → 2350 in v15.0.0
    # for the G-007 dedup-digest code (``DEDUP_DIGEST_MAX_CHARS`` +
    # ``_digest_summary`` + ``_DEDUP_REF_RE`` ref-exclusion — the
    # self-contained ledger-entry digest emission pinned by
    # ``tests/ghost/test_features_v15_0.py``). A future PV that crosses
    # the new 2350 cap should either decompose the file further OR bump
    # the cap again with similar provenance coverage.
    per_file_max = 2350
    package_total = 0
    for p in compressor_pkg.iterdir():
        if p.is_file() and p.suffix == ".py":
            line_count = len(p.read_text(encoding="utf-8").splitlines())
            assert line_count <= per_file_max, (
                f"W-18 v9.3.0 violation: compressor/{p.name} grew to "
                f"{line_count} lines (cap {per_file_max}). The PV-04 "
                f"3-module split's 'thematically tight' contract is "
                f"decaying — consider further decomposition OR bumping the "
                f"per-file cap with explicit retrospective coverage."
            )
            package_total += line_count
    # Cap raised 3000 → 3200 in v9.7.0 PV-02 to accommodate
    # ``dedup_predecessor_summaries`` + 2 helpers (~220 LOC of canonical
    # additive deliverable). Pre-PV-04 single-file was 2541 LOC; the
    # post-split + v9.7.0 PV-02 total stays ≤ 26 % bloat (3200 / 2541).
    # Retrospective coverage: `.local/research/v9.7.0_perf_research.md` §2.
    # Cap raised 3200 → 3250 in v15.0.0 for the G-007 dedup-digest code
    # in transforms.py (same provenance as the per-file 2300 → 2350 bump
    # above; pinned by ``tests/ghost/test_features_v15_0.py``).
    assert package_total <= 3250, (
        f"W-18 v9.3.0 violation: compressor package total LOC is "
        f"{package_total} (cap 3250, raised from 3200 in v15.0.0 G-007). "
        f"The pre-PV-04 single-file compressor.py was 2541 LOC; the "
        f"post-split overhead should stay ≤ 28% bloat."
    )
