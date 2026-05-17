# D-D-4 — W-17 Test-Growth Curve + W-18 Cycle-Specific Lint Maintenance Cost (Patch Design Specification)

> **Status:** PDS authored by L3 Task Agent (Wave 3 D-D)
> **Author:** L3 (composer-2-fast)
> **Date:** 2026-05-04
> **Cycle:** v11.0.0 SI-1 planning
> **Source direction:** `.local/research/v10_internal_optimization_directions.md` §3.7 D-D-4
> **PDS schema:** `v11.0.0_decomposition_plan.md` §3
> **Owned files:** `.local/research/v11.0.0_patches/D-D-4.md`
> **External tools (S-7):** DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`

## §1 — Current state (50-150 words; verbatim file path evidence)

`tests/test_no_ghost_features.py` (**5400+ lines, 64 test functions** per `rg ^def test_ tests/test_no_ghost_features.py | wc -l`) carries the W-18 ghost-audit lint surface mandated by `.cursor/rules/repo-governance.mdc` W-18. The file accumulates **24 cycle-specific `test_v*_*_new_symbols_have_coverage` functions** (lines 1160 → 5267 — full version-mapped inventory verbatim in §5.1) plus **6 additional cycle-specific lints** (`test_v9_1_3_handoff_production_caller_exists` line 1753, `test_v9_1_4_nest_preserves_canonical_order_length` line 2009, `test_v9_1_5_agents_md_slice_default_on` line 2246, `test_v9_2_0_cycle_archive_and_extra_prefix` line 2477, `test_v9_2_2_local_target_no_workflow_system_dependency` line 2813, `test_v9_2_3_mode_flag_surface_complete` line 3038) = **30 cycle-specific lints total**, spanning v9.1.0 → v10.3.0 (~14 minor cycles, ~50 PVs over ~18 months).

**W-17 cycle ledger (verbatim from `.local/research/v10.2.4_w17_mid_cycle_audit.md` §1):** v10.2.0 cycle PV-01..PV-05 deltas were 22 → 29 → 24 → 14 → 4 (cumulative 93 / 150-cap; 62.0%); forecast PV-06 ~96 / 150 = 64.0%. Per `v10.0.0_retrospective.md` §3.4 the v10.0.0 MAJOR cycle hit **+216 NEW tests** vs the +150 cap (66 overshoot accepted as "high-information disposition").

## §2 — Patch design (algorithm + files-touched + API/CLI surface)

**Deliverable:** Two complementary artifacts:

1. **`scripts/audit_test_growth_curve.py`** — quantifies test-suite growth trajectory across all cycles since v8.0.0, projecting v11.0.0 → v15.0.0 trajectory under current W-18 lint authoring patterns.
2. **A research artifact `.local/research/v11.0.X_w18_lint_consolidation_proposal.md`** — proposes a generic W-18 helper that future cycles invoke instead of copy-pasting ~150 lines per cycle. The CONSOLIDATION ITSELF is OUT-OF-SCOPE for v11.0.0 (would touch all 30 historical lints, breaking traceability per the v10_internal_optimization_directions.md §3.7 D-D-4 risk note); v11.0.0 ships only the EVIDENCE + PROPOSAL.

**Algorithm (executed by `audit_test_growth_curve.py`):**
1. Walk `git log --all --pretty=format:'%H %ct %s' tests/test_no_ghost_features.py` to extract per-commit test counts via `git show <SHA>:tests/test_no_ghost_features.py | rg -c '^def test_'`.
2. For each version tag (v8.0.0, v8.1.0, ..., v10.3.0), compute test count delta and cycle-specific lint delta.
3. Compute trend metrics: linear regression slope of `(cycle_index, total_test_count)`, projected v15.0.0 count.
4. Compute per-lint cost: `cycle_specific_lint_count` × avg LOC per lint (~150 from §1 line spans) → projected file size.
5. Emit markdown report with: per-cycle table, trend extrapolation, and 4 consolidation proposal patterns.

**Files-touched (≤ 6 owned):**
- `scripts/audit_test_growth_curve.py` (NEW; ~150 LOC)
- `tests/test_audit_test_growth_curve.py` (NEW; ~80 LOC, 6-8 test functions)
- `Makefile` (1-line ADDITION: `audit-test-growth` target)
- `CHANGELOG.md` (entry under v11.0.X)
- `tests/test_no_ghost_features.py` (W-18 lint refresh — adds `test_v11_0_X_audit_test_growth_present`)

**API surface:** `python scripts/audit_test_growth_curve.py [--start-tag v8.0.0] [--project-out CYCLES]`. Pure stdlib + git CLI — zero new dependencies.

**P6 / A-2 invariance:** Audit-only + research artifact. No consolidation of historical lints (preserves traceability — every `test_v9_X_Y_new_symbols_have_coverage` continues to pin its specific cycle's surface).

## §3 — Small project evaluation

**Synthetic test bed:** `synthetic_small_repo/` (per `v11.0.0_evaluation_methodology.md` §2).

**Operations exercised:** `init` + `feature` (small repo bootstrapped without W-18 lint surface).

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4:
- Test count growth (per-cycle delta)
- W-18 cycle-specific lint count

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Trajectory visibility | unknown | 5-cycle projection table | new metric | improve |
| Operator awareness "test_no_ghost_features.py is on a linear-growth curve" | implicit | explicit via audit | +1 signal | improve |
| Small-repo W-18 burden | minimal (small repos don't carry the historical file) | unchanged | 0 | byte-stable |

**Pass criterion:** Audit script projects v11.0.0 → v15.0.0 trajectory and identifies a "consolidation crossover point" (the cycle by which cumulative cost overtakes consolidation cost).

**If no improvement on small project:** N/A — small repos inherit zero historical W-18 lints (each project gets its own ghost-audit). The benefit is the trajectory projection itself, applicable to any DF clone.

## §4 — Large project evaluation

**Test bed:** DevolaFlow self at v10.3.0 baseline.

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4:
- `tests/test_no_ghost_features.py` line count: **5400+** (per §1)
- W-18 cycle-specific lint count: **30** (24 `_new_symbols_have_coverage` + 6 others, per §1 inventory)
- Average lines per cycle-specific lint: **~150** (per §5 empirical data below)
- Test count delta per cycle (W-17 ledger, verbatim from `v10.2.4_w17_mid_cycle_audit.md` §1): PV-01 +22, PV-02 +29, PV-03 +24, PV-04 +14, PV-05 +4
- pytest wall-clock cost: ~17 s total at v10.3.0 (per `v10.0.0_retrospective.md` §2 headline numbers)

**Expected delta (v10.3.0 baseline → post-patch knowledge state):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Trajectory data points | 0 | full v8.0.0 → v15.0.0 projection | +full curve | improve |
| Consolidation proposal | 0 | 4 proposed patterns documented | +4 evidence rows | improve |
| Historical lint count | 30 | 30 (unchanged — preserves traceability) | 0 | byte-stable |
| `test_no_ghost_features.py` LOC | 5400 | 5400 + ~80 (new audit-presence lint) | +80 | within W-17 +30 PV cap |
| Test count delta | N/A | +6-8 (audit script tests + 1 W-18 lint) | +6-8 | within W-17 cap |

**Pass criterion:** Audit produces a projection table matching §5 below (or refined with actual git-log measurements) AND identifies the consolidation crossover point.

**Side-effect check:** Historical W-18 lints unchanged (preserves audit traceability). pytest wall clock unchanged (audit script runs separately).

## §5 — Benefit metrics (≥ 3 quantitative DF-internal metrics + maintenance cost trajectory)

| # | Metric | Baseline (v10.3.0) | Post-patch | Δ |
|---|---|---:|---:|---:|
| 1 | Cycle-specific W-18 lints (`test_v*_*_*` cluster) | 30 (inventoried verbatim per §1) | 30 (unchanged; +1 audit-presence lint) | +1 (audit lint) |
| 2 | Test growth trajectory data | unknown | 5-cycle forward projection table (see §5.1) | +full curve |
| 3 | Projected v15.0.0 file size | unknown | ~24K LOC (see §5.1) | +visibility |
| 4 | Consolidation proposal candidates | 0 | 4 patterns documented in research artifact | +4 evidence rows |
| 5 | Per-cycle author cost (LOC of W-18 lint authoring) | ~150 LOC × N PVs / cycle | unchanged (proposal only; consolidation deferred) | 0 |
| 6 | Test count growth visibility (current W-17 cycle) | manually tracked in `v10.2.4_w17_mid_cycle_audit.md` | scriptable via `audit_test_growth_curve.py` | +automation |
| 7 | Operator time to project "what does test_no_ghost_features.py look like at v12.0.0?" | ~30 min manual tracing | < 1 min (read audit table) | -97% |

**Cross-tier benefit summary:** Both small and large project tiers benefit identically — the trajectory projection is portable evidence. Small repos that are NEW DevolaFlow consumers benefit by understanding the W-18 lint authoring obligation BEFORE accumulating their own per-cycle drift.

### §5.1 Maintenance cost trajectory analysis (per the task's special D-D-4 requirement)

**Full W-18 lint inventory (verbatim from `rg '^def test_v\d+_\d+_\d+_new_symbols_have_coverage'` against `tests/test_no_ghost_features.py`):**

| # | Cycle version | Test function | Source line |
|---|---|---|---:|
| 1 | v9.1.0 | `test_v9_1_0_new_symbols_have_coverage` | 1160 |
| 2 | v9.1.1 | `test_v9_1_1_new_symbols_have_coverage` | 1325 |
| 3 | v9.1.2 | `test_v9_1_2_new_symbols_have_coverage` | 1470 |
| 4 | v9.1.3 | `test_v9_1_3_new_symbols_have_coverage` | 1631 |
| 5 | v9.1.4 | `test_v9_1_4_new_symbols_have_coverage` | 1884 |
| 6 | v9.1.5 | `test_v9_1_5_new_symbols_have_coverage` | 2097 |
| 7 | v9.2.0 | `test_v9_2_0_new_symbols_have_coverage` | 2322 |
| 8 | v9.2.1 | `test_v9_2_1_new_symbols_have_coverage` | 2585 |
| 9 | v9.2.2 | `test_v9_2_2_new_symbols_have_coverage` | 2725 |
| 10 | v9.2.3 | `test_v9_2_3_new_symbols_have_coverage` | 2931 |
| 11 | v9.2.4 | `test_v9_2_4_new_symbols_have_coverage` | 3153 |
| 12 | v9.3.0 | `test_v9_3_0_new_symbols_have_coverage` | 3352 |
| 13 | v9.4.0 | `test_v9_4_0_new_symbols_have_coverage` | 3556 |
| 14 | v9.5.0 | `test_v9_5_0_new_symbols_have_coverage` | 3761 |
| 15 | v9.6.0 | `test_v9_6_0_new_symbols_have_coverage` | 3926 |
| 16 | v9.7.0 | `test_v9_7_0_new_symbols_have_coverage` | 4104 |
| 17 | v10.0.0 | `test_v10_0_0_new_symbols_have_coverage` | 4280 |
| 18 | v10.1.0 | `test_v10_1_0_new_symbols_have_coverage` | 4409 |
| 19 | v10.2.0 | `test_v10_2_0_new_symbols_have_coverage` | 4510 |
| 20 | v10.2.1 | `test_v10_2_1_new_symbols_have_coverage` | 4644 |
| 21 | v10.2.2 | `test_v10_2_2_new_symbols_have_coverage` | 4807 |
| 22 | v10.2.3 | `test_v10_2_3_new_symbols_have_coverage` | 4947 |
| 23 | v10.2.4 | `test_v10_2_4_new_symbols_have_coverage` | 5094 |
| 24 | v10.3.0 | `test_v10_3_0_new_symbols_have_coverage` | 5267 |

**Empirical line spans between consecutive lints:**

| Range | Function ID range | Span (lines) | Avg lines per lint |
|---|---|---:|---:|
| v9.1.0 → v9.1.5 | 1160 → 2097 | 937 | ~156 |
| v9.2.0 → v9.2.4 | 2322 → 3153 | 831 | ~166 |
| v9.3.0 → v9.7.0 | 3352 → 4104 | 752 | ~150 |
| v10.0.0 → v10.3.0 | 4280 → 5267 | 987 | ~140 |

**Average: ~150 lines per cycle-specific lint.**

**Trajectory projection:**

| Cycle | Cumulative cycle-specific lints | Cumulative LOC (cycle-specific only) | Total file LOC est. |
|---|---:|---:|---:|
| v10.3.0 (today) | 30 | ~4500 | ~5400 |
| v11.0.0 (5 PVs forecast) | ~35 | ~5250 | ~6150 |
| v12.0.0 (~30 PVs from v11.0) | ~65 | ~9750 | ~10650 |
| v13.0.0 | ~95 | ~14250 | ~15150 |
| v14.0.0 | ~125 | ~18750 | ~19650 |
| v15.0.0 | ~155 | ~23250 | ~24150 |

**By v15.0.0 the file approaches ~24K lines** — well past the point where any single L0/L3 reading the file for context would survive the C-4 default tier ceiling (< 500). pytest collection time would also degrade noticeably (the v10.3.0 file already takes ~1.5 s to collect alone per `pytest --collect-only tests/test_no_ghost_features.py`).

**Cost dimensions:**

1. **File-size growth:** linear at ~600 LOC per major cycle. Projected to cross 10K LOC at v12.0.0.
2. **Author cost per cycle:** 150 LOC × 4-7 PVs per cycle = 600-1050 LOC of W-18 lint authoring per cycle. Each lint requires manual symbol-extraction from CHANGELOG entries.
3. **Reader cost:** the file is the canonical source for "what features ship in version X" per W-18 — reading it linearly from v9.1.0 forward to verify a v10.X feature requires scrolling past 24 cycle-specific blocks.
4. **Drift cost:** historical lints reference removed/renamed symbols; v9.X lints occasionally fail when v10.X removes a referenced symbol (e.g. v10.0.0 PV-04 retrospective §4.2 "demo/index.html 'automated' lint trip" is a real instance of historical lints failing on later edits).

## §6 — Admission verdict

**Verdict:** **CONDITIONAL_PASS**

**Rationale:** The PASS verdict applies to the AUDIT (script + research artifact) — both small and large tiers benefit (audit is portable + the trajectory data is large-repo-specific but consultable from any clone). However, the "CONDITIONAL" qualifier reflects an explicit limitation flagged in the source v10_internal_optimization_directions.md §3.7 D-D-4 risk: **consolidating the 30 historical lints is OUT-OF-SCOPE** because consolidation would lose the per-cycle traceability that current cycle-close retrospectives rely on (v10.0.0 retrospective §4.2 explicitly cites historical lints as bug-finding aids — "demo/index.html 'automated' lint trip" example).

The patch ships **observability + a 4-pattern consolidation proposal**; the FUTURE consolidation decision is gated on whether v11.1.0+ operators agree the trajectory projection justifies losing per-cycle traceability for some lint subset. G-1 internal-value (7 metrics in §5 + trajectory analysis in §5.1), G-2 both-tier (small + large benefit identically from audit), G-3 zero external deps, G-4 cycle-budget (+6-8 tests), G-5 Soul-freeze (no S-11), G-6 cache-prefix (no canonical_order touched), G-7 compatibility (additive script + 1 W-18 lint), G-8 coverage (6-8 unit tests target ≥ 90% on ~150 LOC), G-9 docs (CHANGELOG + W-18 + research artifact per §2). All gates green; CONDITIONAL_PASS is the correct verdict for an evidence-only patch with explicit deferred-action surface.

## §7 — Effort estimate

**M** (1 PV).

Per source §3.7 D-D-4 estimate; confirmed by §2 file-touched count (5 owned files, ~230 LOC total; the `git log` walking + linear regression projection slightly heavier than D-D-1/D-D-2/D-D-3 audit scripts). Implementation breakdown: ~3 hr script (git-log walker + delta computer + projector) + ~2 hr tests (must mock git log for deterministic test fixtures) + ~2 hr research artifact (4 consolidation proposal patterns, each 50-80 lines of prose) + ~30 min CHANGELOG / W-18 lint = ~7.5 hr.

The M classification matches the source direction's "M (1 PV: 分析 + script)" estimate.

## §8 — Dependencies

**none** — standalone audit. Optionally surfaces enhanced data IF D-D-1 (reference utilization audit) and D-D-3 (line-budget density audit) land in the same cycle — could cross-correlate "high test growth in cycles that ALSO grew references" but this is enhancement-only, not blocking.

## §9 — Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Trajectory projection is linear-extrapolation; the actual curve may be sub-linear (cycles converge to fewer per-cycle lints as the codebase matures) OR super-linear (each cycle adds proportionally more features as the framework scales). | minor | Audit explicitly emits a SLOPE coefficient + R² fit quality alongside the projection. Projections are tagged "linear-extrapolation; confidence bands ± X%". Operators reading the audit understand the projection IS a hypothesis, not a forecast. |
| 2 | The 4 consolidation proposals could prematurely encourage consolidation in v11.1.0+ before the v15.0.0 crossover point arrives; consolidation in v11.1.0 would lose ~5 cycles of per-cycle traceability for marginal LOC savings. | major | Audit's research artifact MUST tag consolidation proposals as "evidence for v13.0.0+ review when projected file LOC > 10K", NOT as a v11.0.x action item. Crossover-point math is shown explicitly: cumulative consolidation savings only exceed traceability cost when N > ~80 cycle-specific lints (per the empirical 150 LOC × N consolidation savings vs the per-cycle bug-detection ROI). |
| 3 | The audit script itself (~150 LOC) adds 6-8 NEW tests to the v11.0.0 cycle's W-17 budget; if other Wave 3 patches also land (D-D-1 + D-D-2 + D-D-3 each adds 5-8 tests), Wave 3 contribution alone could be 22-31 tests — close to the +30 PV cap. | minor | Per §7 cycle-budget calculus: 4 directions × 6-8 tests each = 24-32 tests. If Wave 3 lands as a single PV, total may breach the +30 per-PV cap by 0-2. Mitigation: spread across 2 PVs OR consolidate the 4 audit scripts into a single `scripts/audit_v11.py` orchestrator (M-effort follow-up; deferred). For v11.0.0 admission, if the scheduling demands single-PV land, drop D-D-4's audit-presence W-18 lint to stay at -1 (24-29 net) within the +30 cap. |

---

ADMISSION: CONDITIONAL_PASS | EFFORT: M | DEPS: none | TIER: standard
