# v15-ADR-001 — Ghost-Audit Decomposition (`tests/test_no_ghost_features.py` → `tests/ghost/` package)

* **Status**: PROPOSED (L0/human ratifies)
* **Date**: 2026-06-12
* **Cycle**: v14.2.0 T5 (SI-1 planning gate for the v14.2.x → v15.0.0 ladder)
* **Feeds**: F-R20 (critical) per `.local/research/v15-cycle_design_review_repo.md` §4/§7-D4; gap G-027
* **3-condition gate**: Hard to reverse — W-18 and S-4 enforcement history all point at one
  filename; splitting changes the append target every future PV uses. Surprising — a
  passing-forever 12K-line test file being split looks like weakening the audit unless the
  contract is restated. Real trade-off — single-file greppability vs merge-conflict surface and
  unbounded growth. → **qualifies**.

## Context

`tests/test_no_ghost_features.py` is currently **12405** lines — 24× growth from **517** lines at
its introduction ("9628d6c 2026-04-20 chore(release): DevolaFlow v7.4.4 — P-01 anti-ghost test
infrastructure"). Composition: 108 `def test_` functions, 2255 comment lines, 118 banner-comment
section dividers — per-test average ~115 lines, mostly prose.

Growth is mandated by W-18: "before a PV authors a CHANGELOG entry mentioning a feature, the
ghost-audit (`tests/test_no_ghost_features.py`) MUST be refreshed" — every feature in every PV
appends to this one file forever. The file is simultaneously: rule-cap enforcer
(`test_rule_count_under_cap`), SF-4 reference-set pin (`_SF4_REFERENCE_SET`), SSOT registry lint
(`test_registry_single_owner`), compile-drift check (`test_rule_surfaces_compile_only`), and
per-feature ghost audit — a god-test-file with the worst merge-conflict surface in the repo
(every concurrent PV touches it). At the observed rate (~1.7K lines/week) it exceeds the entire
`gate/` package within 2 cycles.

## Decision (recommended)

1. **Split into a `tests/ghost/` package by enforcement domain**:
   * `tests/ghost/test_rules.py` — rule-cap, compile-drift, rule-surface lints.
   * `tests/ghost/test_schema.py` — layout/canonical-order companion lints.
   * `tests/ghost/test_registries.py` — A-5 SSOT single-owner, SF-4 reference set, MIRRORED_FILES parity.
   * `tests/ghost/test_features_v<MAJOR>_<MINOR>.py` — per-cycle W-18 feature stanzas (one file
     per MINOR cycle; the append target rotates each cycle, capping any single file's growth).
2. **Keep `tests/test_no_ghost_features.py` as a thin aggregator** for one deprecation cycle:
   it re-exports the shared pins (`_SF4_REFERENCE_SET`, `_SSOT_PYTHON_REGISTRIES`, cap constants)
   so external citations (W-21, ADR-007, C-7) stay valid, and contains a pointer docstring.
   Remove the aggregator only at v15.0.0 with a coordinated rule recompile.
3. **Recompile W-18 + C-7 + A-5 + W-21 rule text in the SAME PR** as the split, renaming the
   target to `tests/ghost/` (W-18's path is cited verbatim in an always-applied rule — R-5 in
   the gap analysis §6).
4. **Archive discipline**: per-cycle feature files older than 2 cycles stay collected but are
   consolidated — prose banners stripped to one-line provenance pointers (history lives in
   `docs/cycle-archive/`), target ≤ 1500 lines per per-cycle file.
5. **Timing**: ladder skeleton slots implementation at v14.5.0; the repo review urged v14.3.0.
   This ADR is timing-neutral but quantifies the cost of waiting (~2 releases × append rate);
   the slot is L0-decision item §4.2 #1 of the gap analysis.

## Consequences

### Positive
* Merge-conflict surface drops from "every PV edits one 12K-line file" to "every PV edits its
  own cycle file"; domain lints become independently greppable and reviewable.
* W-18's contract is preserved verbatim (refresh-then-CHANGELOG) — only the path generalizes.
* Per-test prose discipline becomes enforceable per-file (line ceiling per cycle file).

### Negative
* One-time churn: ~108 test functions move; every doc/rule citation of the old path must be
  updated in the same PR (W-18, C-7, A-5.1, W-21 enforcement notes, SKILL/reference mentions).
* Two-surface period during the deprecation cycle (aggregator + package) — mitigated by the
  aggregator being import-only re-exports, no test bodies.

### Neutral
* Collected test count unchanged; W-17 cap unaffected (moves are not NEW functions).
* No runtime/dispatch surface touched; no schema or benchmark impact.

## Alternatives considered

* **A1 — Keep the monolith, ban prose**: stripping the 2255 comment lines + 118 banners buys
  ~20% once; growth mandate (W-18) is untouched, conflict surface remains. Rejected: treats the
  symptom.
* **A2 — Per-PV files (`test_ghost_pv_*.py`)**: caps growth harder but explodes file count
  (~6-10 files/cycle) and scatters domain lints. Rejected: per-cycle granularity matches the
  W-19 archive cadence.
* **A3 — Move feature audits into each feature's own test module**: dissolves the audit as a
  distinct surface; S-4's value is precisely the centralized "does the CHANGELOG lie?" sweep.
  Rejected.
* **A4 — Slow-lane marker (`@pytest.mark.slow_lane`) instead of split**: addresses runtime (not
  the bottleneck per F-R24 — suite is ~3.7 min) but not conflicts/growth. Rejected.
