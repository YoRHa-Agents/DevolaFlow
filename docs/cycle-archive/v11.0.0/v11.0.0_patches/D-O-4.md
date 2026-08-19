# D-O-4 — SI-10 Gate Chain Growth Curve & Bloat Warning

> **PDS schema v1** per `.local/research/v11.0.0_decomposition_plan.md` §3
> **Wave:** 4b (D-O Observability & Self-Assessment)
> **Author:** L3 Task Agent (composer-2-fast)
> **Date:** 2026-05-04
> **Owned file:** `.local/research/v11.0.0_patches/D-O-4.md`
> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.4 D-O-4 (lines 235-243)
> **Evaluation methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §4.5 (SI-10 gate count)
> **Scope:** ANALYSIS-ONLY (per task spec) — produces a forecast table + reorganization recommendation; does NOT modify Makefile or W-9 governance text in this patch.

## §1 — current_state

DevolaFlow's pre-commit verification chain is codified in **two places** which are **partially coupled**:

1. **`.cursor/rules/repo-governance.mdc` §W-9** (lines 384-398 of `AGENTS.md`) — declares **6 base SI-10 steps** (pytest / ruff check / ruff format / test_version / test_benchmarks / make check-cursor-skill). This is the W-9 normative spec.
2. **`Makefile::release-preflight`** (line 146 of `Makefile`) — actually runs the gate chain. Currently invokes **10 sub-targets** in sequence: `lint test validate-templates build-skill sync-human-docs check-cursor-skill compile-rules check-drift check-rules-drift iteration-delta-gate`. The cycle's CHANGELOG entries (e.g., `CHANGELOG.md` lines 95, 186, 271, 361, 454) consistently call this **"7-step SI-10"** because (a) the 6 base + iteration_delta = 7 are the W-9-canonical gates; (b) other targets like `validate-templates` / `build-skill` / `sync-human-docs` are pre-W-9 hygiene that ships in `release-preflight` but is NOT counted in the W-9 7-step list.

**Verbatim file path evidence:**

* `Makefile` line 146: `release-preflight: lint test validate-templates build-skill sync-human-docs check-cursor-skill compile-rules check-drift check-rules-drift iteration-delta-gate`.
* `Makefile` lines 134-144: declares the 7th step `iteration-delta-gate` target ("v10.2.1 PV-02 (D-S-3 / D-V-1) — 7th SI-10 step: Si-Chip iteration_delta gate").
* `.cursor/rules/repo-governance.mdc` §W-9 (lines 384-398 of `AGENTS.md`) — explicit "all 6 must pass" wording; the 7th iteration_delta step is NOT yet in the governance text but is **telegraphed** for v10.4.0 per `CHANGELOG.md` line 95: "telegraphed for v10.4.0 to formalize as W-9 step #7".
* `CHANGELOG.md` line 538: "**W-9 SI-10 6-gate green** at this commit: pytest / ruff check / ruff format / test_version / test_benchmarks / make check-cursor-skill all pass." — pre-v10.2.1 cycle baseline.
* `CHANGELOG.md` line 454: "**W-9 SI-10 7-gate green** at this commit. The 6 base gates ... PLUS the new 7th step (`tests/test_sichip_iteration_delta_gate.py`) all pass." — post-v10.2.1 cycle.
* `CHANGELOG.md` line 443: "| SI-10 gate count | 6 | 7 (Si-Chip iteration_delta added) | D-V-1 cycle-wide protocol |" — explicit count delta.

**Historical SI-10 gate count progression** (per task spec hint + CHANGELOG cross-reference):

| Cycle close | Gate count | Source citation | New gate(s) added |
|---|---:|---|---|
| v8.0.0 | 4 | per task spec | pytest / ruff check / ruff format / test_version (early baseline; before benchmark + cursor-skill steps) |
| v9.0.0 | 5 | per task spec | + test_benchmarks (added per W-4 codification) |
| v10.0.0 | 6 | `CHANGELOG.md` lines 538, 675, 1033 | + check-cursor-skill (SF-3 mirror parity codified) |
| v10.3.0 | 7 | `CHANGELOG.md` lines 443, 454 | + iteration-delta-gate (D-V-1; Si-Chip dogfood) |
| v10.4.0 (forecast) | 7 (text) → 7 (Makefile) | W-9 governance update only; no new gate | — (governance catches up to Makefile reality) |

**Current trajectory:** **+1 gate per MAJOR cycle on average** since v8.0.0. v8.0 → v9.0 → v10.0 = +1 each = 3 → 4 → 5 → 6 = +1 per minor or major release. The v10.2.1 PATCH-level addition (iteration_delta) is the FIRST PATCH-level addition; prior gate additions all landed at MAJOR or MINOR boundaries.

The W-9 / SI-10 wall-clock cost: per `CHANGELOG.md` line 1059 (v10.0.0 perf overhaul) `pytest tests/ -q` dropped from 55s → 17s; current 7-step preflight likely ~30-45s end-to-end (pytest 17s + ruff 1s × 2 + benchmarks ~5s + cursor-skill 1s + iteration-delta 5s). Each NEW gate adds 1-10 seconds depending on tool category.

## §2 — patch_design

**Scope per task spec: ANALYSIS-ONLY.** This patch produces ONE document; the document is the deliverable. No Makefile edit. No W-9 governance text edit. The output **informs** a future cycle's decision to reorganize (or not).

### 2.1 Algorithm

1. **NEW** `.local/research/v11.0.0_si10_gate_growth_analysis.md` (~ 350 lines; or this PDS file's §2.3 forecast table can be extracted to that artifact during cycle plan synthesis).
2. The artifact contains:
   * Historical gate count table (with verbatim cycle-tag / `CHANGELOG.md` line citations).
   * Forecast table (next 5 MAJOR cycles).
   * Wall-clock impact projection (current ~30s; +5s per added gate).
   * Reorganization recommendation: **at gate count = 10**, partition into parallel groups; defer if gate count < 10.
   * Decision matrix: `append` vs `merge into existing` vs `partition into parallel groups`.
3. The artifact's recommendation feeds the v11.0.0 retrospective §3 ("What was deferred and why") + telegraphs to v11.2.0 (cycle N+2) per W-21 governance pattern (this is NOT a Soul rule addition; W-21 only governs Soul layer; the analogue here is the 2-cycle deliberation rhythm for any cross-cutting governance edit).

### 2.2 Files-touched list

| Path | Operation | Lines |
|---|---|---:|
| `.local/research/v11.0.0_si10_gate_growth_analysis.md` | NEW (analysis artifact) | ~ 350 |
| `CHANGELOG.md` | NEW entry citing the analysis | +5 |
| `tests/test_no_ghost_features.py` | W-18 lint refresh — NEW lint asserting the analysis artifact exists | +5 |

**Zero source code changes. Zero test surface beyond the W-18 lint.** Pure analysis artifact + cite. G-7 compatibility: pure-additive doc.

### 2.3 SI-10 gate count forecast table (the meat of D-O-4)

**Historical baseline:**

| Cycle | Gate count | New gate(s) | Wall-clock (est.) | Source |
|---|---:|---|---:|---|
| v8.0.0 | 4 | pytest, ruff check, ruff format, test_version | ~12s | task spec hint |
| v9.0.0 | 5 | + test_benchmarks | ~17s | task spec hint |
| v10.0.0 | 6 | + check-cursor-skill | ~22s | `CHANGELOG.md` line 538, 675, 1033 |
| v10.3.0 | 7 | + iteration-delta-gate | ~30s | `CHANGELOG.md` lines 443, 454 |

**Linear forecast (assuming +1 gate per MAJOR cycle, the empirical historical rate):**

| Cycle | Forecast gate count | Plausible new gate (extrapolated) | Wall-clock (est.) | Threshold action |
|---|---:|---|---:|---|
| **v11.0.0** | **8** | + W-19 archive validation, OR + reference-rosetta currency lint (D-O-1 follow-up), OR + auto-collection schema check (D-O-2 follow-up) | ~35s | **APPEND OK** (under reorganization threshold) |
| **v12.0.0** | **9** | + degraded-mode contract test (D-C-1 if it lands), OR + bridge contract test (D-C-2 if it lands) | ~40s | **TELEGRAPH reorganization** (1 cycle from threshold) |
| **v13.0.0** | **10** | + multi-tool plugin lifecycle test, OR + per-file iteration_delta granularity gate | ~45s | **EXECUTE reorganization** (threshold reached) |
| **v14.0.0** | **11** (forecast continues if no reorganization) | — | ~50s | red-flag: bloat |
| **v15.0.0** | **12** (forecast continues if no reorganization) | — | ~55s | red-flag: bloat |

**Reorganization recommendation: WHEN gate count = 10 (forecast v13.0.0; ~3 MAJOR cycles from v11.0.0 baseline).**

### 2.4 Reorganization design (deferred to v13.0.0; documented here for telegraph)

When gate count crosses the 10-threshold, partition into **3 parallel groups**:

| Group | Member gates | Wall-clock (est. parallel) | Failure semantics |
|---|---|---:|---|
| **Group A: Hygiene** | pytest, ruff check, ruff format, test_version | ~17s | Any failure → block commit immediately (fail-fast) |
| **Group B: Validation** | test_benchmarks, check-cursor-skill, multi-baseline-byte-test, iteration-delta-gate | ~10s (parallel within group) | Any failure → block commit immediately |
| **Group C: Snapshot** | W-19 archive validation, reference-rosetta currency, auto-collection schema, degraded-mode contract | ~5s (parallel within group) | Failure logged but commit allowed if Group A + B green; cycle-lead reviews at next-PV opening |

**Wall-clock projection post-reorganization:** Group A 17s + Group B 10s + Group C 5s = **32s end-to-end** if groups run **sequentially** (A → B → C); or **17s** if groups run **in parallel** (max of A=17s).

**Compared to the v15.0.0 forecast (no reorganization, 12 sequential gates): ~55s.** Reorganization saves **~38s per commit at v15.0.0**, **~25s per commit at v13.0.0** (when the reorganization first lands).

### 2.5 Decision matrix: append vs merge vs partition

When the next cycle proposes a NEW SI-10 gate, apply this decision rule:

| Test | Action |
|---|---|
| Gate measures the SAME PHENOMENON as an existing gate (e.g., a NEW pytest invocation; a NEW ruff variant) | **MERGE** — extend the existing gate's scope; don't append |
| Gate is independent + fast (< 5s) + critical for correctness | **APPEND** within current group (current `release-preflight` sequential chain) |
| Gate is independent + slow (≥ 5s) + critical for correctness | **APPEND**; once total wall-clock ≥ 60s OR gate count ≥ 10, **PARTITION** at next opportunity |
| Gate is independent + slow + advisory (not block-on-fail) | **PARTITION** into Group C immediately upon addition |

This is the same NEST-vs-APPEND decision rule pattern as A-2.3 (canonical_order) but applied to the gate chain.

### 2.6 What this analysis does NOT do (out-of-scope)

* **Does NOT modify** `Makefile::release-preflight` — that's a future-cycle decision.
* **Does NOT modify** W-9 governance text — that's a W-21-pattern multi-cycle deliberation, not a single-PV change.
* **Does NOT add** new gates — pure analysis of growth.
* **Does NOT replace** the v10.4.0 telegraph to formalize iteration_delta as W-9 step #7 — that telegraph still applies; D-O-4 supplements it with the longer-term forecast.

## §3 — small_project_eval

**Synthetic test bed:** synthetic_small_repo (per `v11.0.0_evaluation_methodology.md` §2)

**Operations exercised:** None — D-O-4 is analysis-only.

**Metric collection:** trivially N/A on small projects. Small projects don't run the full SI-10 gate chain; they run a subset (`make precommit-fast` per D-X-3 if that lands) or run nothing (most small projects don't have benchmarks, multi-baseline byte tests, iteration_delta).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Awareness of gate count growth (count of cycle planners citing D-O-4 forecast) | 0 (forecast doesn't exist) | ≥ 1 per cycle (W-1 SI-1 planning gate cites the forecast for "should we add an SI-10 gate this cycle?") | +1 | improve |
| Pre-commit runtime on small repo | n/a (small repos don't run full SI-10) | n/a | — | no impact |

**Pass criterion:** awareness ≥ 1 per cycle within first 3 MINORs after landing.

**If no improvement on small project:** small project tier benefit is **structural, not numeric** — the analysis doesn't speed up a small repo's commit, but it informs the cycle-lead's decision-making process. Verdict on small tier: **CONDITIONAL_PASS** by construction (analysis-only patches have orthogonal benefit on small vs large).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline)

**Metric collection:** baseline = current 7-gate chain wall-clock + no documented forecast; post-patch = same 7-gate chain (D-O-4 doesn't change the chain) + the forecast artifact informs cycle-lead decisions.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| SI-10 gate count forecast horizon (cycles ahead) | 0 (only telegraph for v10.4.0; no longer forecast) | 5 (v11.0 → v15.0 forecasted) | +5 | improve |
| Reorganization-trigger threshold documented | n/a (no documented threshold) | gate count = 10 (forecast v13.0.0) | +1 explicit threshold | improve |
| Cycle-lead decisions referencing the forecast (per cycle) | 0 | ≥ 1 (every cycle's W-1 SI-1 gate question "should we add an SI-10 step?") | +1 / cycle | improve |
| Pre-commit wall-clock (current 7-step) | ~30s | ~30s (unchanged) | 0 | preserve |
| Test count delta (W-17 budget consumption) | 0 | +5 (W-18 lint only) | +5 (3% of +150 cycle cap) | acceptable cost |

**Pass criterion:** forecast artifact exists AND is cited in v11.X.0 cycle plan(s) AND wall-clock baseline preserved (no regression).

**Side-effect check:**
* `Makefile` byte-stable (zero edits in this patch).
* W-9 governance text byte-stable.
* No new SI-10 gate added; no test count regression beyond +5 W-18 lint.

## §5 — benefit_metrics

| Metric (DF-internal) | Bucket (`v11.0.0_evaluation_methodology.md` §) | Before (v10.3.0) | After (post-D-O-4) | Δ |
|---|---|---:|---:|---:|
| **SI-10 gate count** (current) | §4.5 row 3 | 7 (Makefile) / 6 (W-9 text) | 7 (Makefile) / 6 (W-9 text); **unchanged** | 0 (preserved) |
| **Forecast horizon** (cycles ahead the analysis projects) | §4.5 derived | 0 | **5** (v11.0 → v15.0) | +5 |
| **Reorganization threshold documented** (gate count at which to partition) | §4.5 derived | 0 (no threshold) | **10** | +1 explicit |
| **Decision matrix entries** (append vs merge vs partition test rules) | §4.5 derived | 0 | **4** rules | +4 |
| **Wall-clock projection** (forecast cycles' SI-10 runtime) | §4.5 derived | n/a | 35s (v11.0) → 55s (v15.0 if no reorg) → 32s (v13.0 reorg sequential) → 17s (v13.0 reorg parallel) | new surface |
| **Test count delta** (W-17 budget consumption) | §4.4 row 2 | 0 | +5 (W-18 lint only) | +5 |

All metrics scriptable: `wc -l Makefile`, `grep -c "SI-10" .cursor/rules/repo-governance.mdc`, `time make release-preflight`.

**Zero EvoBench dependency** — every metric is internal. G-1 internal-value gate satisfied.

## §6 — admission_verdict

**Verdict: CONDITIONAL_PASS**

**Justification:**
* **PASS on large project tier** — DevolaFlow self benefits from documented forecast; cycle planners get a concrete threshold + decision matrix instead of ad-hoc "should we add this gate?" judgment per cycle.
* **CONDITIONAL on small project tier** — small repos don't run the SI-10 chain; analysis benefit is structural-only (informs DF cycle-lead, not small-repo operator). No measurable small-project benefit; no regression either.

**G-2 both-tier gate disposition:** CONDITIONAL — applicability bounds explicit ("D-O-4 is meta-governance for the DF cycle-lead role; small-project operators see no direct effect"). Satisfies the v11.0.0 admission checklist §G-2 CONDITIONAL clause: ships with explicit applicability documentation.

**Other gates:**
* G-1 internal-value: PASS (all §5 metrics are DF-internal).
* G-3 zero-deps: PASS (no external tool dependencies).
* G-4 cycle-budget: PASS (S effort = ≤ +10 tests; planned +5 for W-18 lint).
* G-5 Soul-freeze: PASS (zero S-* additions).
* G-6 cache-prefix: PASS (zero canonical_order edits; unrelated surface).
* G-7 compatibility: PASS (pure-analysis artifact; zero behaviour change).
* G-8 test coverage: PASS (W-18 lint asserts artifact existence; CP-2 floor preserved on existing modules).
* G-9 documentation: PASS — CHANGELOG entry + W-18 lint refresh + the analysis artifact IS itself the documentation. No bilingual ST-3 trigger (research artifact, not user-facing guide). No SF-3 sync (research artifacts are not in the canonical mirrored set).

## §7 — effort_estimate

**S (≤ 0.5 PV)**

**Breakdown:**
* Authoring the forecast analysis artifact (~ 350 lines): ~3 hours including data extraction from CHANGELOG / Makefile / W-9 text.
* CHANGELOG entry + W-18 lint refresh: ~30 min.
* PR review feedback iteration: ~1 hour.

**Confirms** the §3 decomposition plan's S estimate (≤ 0.5 PV).

## §8 — dependencies

**None (standalone).**

**Optional synergy:**
* If D-X-3 (W-9 SI-10 fast-path) lands in the same cycle, D-O-4's forecast directly motivates the fast-path partition design — D-O-4's decision matrix (Group A / B / C) provides the topology D-X-3 implements.
* If D-O-2 (auto-collection) lands, the auto-collection step itself becomes a candidate for the v11.0.0 +1 gate (collector schema check) — D-O-4's forecast already accommodates this.

Neither is a hard dependency.

## §9 — risk_register

| Risk | Severity | Description | Mitigation |
|---|---|---|---|
| **R-1** Forecast over-anchors future decisions ("we forecast 8 gates at v11.0; let's add one to hit the forecast") | major | Self-fulfilling-prophecy risk: forecast becomes a quota rather than a warning. | Document explicitly in the artifact §3 ("Reorganization recommendation"): "the forecast is a CEILING, not a floor; cycles MAY add 0 gates and stay under forecast — that is GOOD, not a regression". Add a `tests/test_si10_gate_count_within_forecast.py` lint that asserts the actual gate count ≤ forecast (not ≥); failure direction is "too many gates", not "too few". |
| **R-2** Analysis goes stale as cycles add gates faster than forecast | minor | If v11.X.x adds 2 unforecasted gates (vs the +1 / MAJOR rate), the artifact's threshold + decision matrix may be off. | Refresh the analysis at every MAJOR cycle close (v11.0, v12.0, ...) by re-running the same analysis with the new historical baseline; the artifact path stays the same so cycle planners always read the latest. |
| **R-3** Reorganization recommendation triggers premature partition (e.g., a v12.0 cycle adds a Group C "advisory" gate to skirt the gate-count cap) | minor | The Group A/B/C structure could be abused: any new gate gets dumped in Group C "advisory" to keep total count low. | Document explicitly in the decision matrix: "Group C is for genuinely advisory gates only (no-block-on-fail; cycle-lead reviews at next-PV); if the gate is critical for correctness, it MUST go in Group A or B regardless of count pressure". Add to the cycle-plan template: "for each new SI-10 gate, justify Group placement against this rule". |

---

ADMISSION: CONDITIONAL_PASS | EFFORT: S | DEPS: none | TIER: stretch
