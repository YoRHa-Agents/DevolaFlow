# D-P-2 — Patch Design Specification

> **Direction**: Soul rule W-21 threshold empirical check
> **Source**: `.local/research/v10_internal_optimization_directions.md` §3.2 D-P-2 (lines 120-127)
> **Author**: L3 Task Agent, Wave 4a (D-P Protocol Evolution)
> **Date**: 2026-05-04
> **Cycle**: v11.0.0 SI-1 planning
> **Constraints**: ANALYSIS-ONLY per source doc — "仅在本次研究文档中分析；**不修改 W-21 规则本身**" (line 124). G-5 Soul-freeze gate respected: zero new Soul rules; W-21 itself untouched.

---

## §1 — Current State

W-21 (Soul-Set Freeze Governance) was codified at v9.0.0 PV-07 per `.local/research/adr/v9-ADR-007-rule-rebalancing-and-rollup.md` D4 (lines 152-217). The rule freezes the Soul layer at S-1..S-10 and gates any S-11+ addition behind: (1) 2-cycle telegraph in cycle N's retrospective §3, (2) SI-1 gap-analysis entry in cycle N+2, (3) SI-3 §3.2 architecture-rationality ≥ 9.5/10, (4) Soul cap of 12 (post-addition). Current Soul set: 10 entries at v10.3.0 baseline (S-1..S-10 per `.cursor/rules/repo-governance.mdc` §S-1..§S-10).

The S-11 candidate **"Parallel Wave Dispatch Invariant"** has been telegraphed across **4 cycles** and never landed:

* **v10.0.0 retrospective §3.5** (`.local/research/v10.0.0_retrospective.md` lines 149-164) — first telegraph: "Every L2-wave with `parallel_mode: true` MUST go through `dispatch_wave_tasks`". Explicitly noted as "leading hypothesis" pending full A-1 vs Soul-rule analysis.
* **v10.2.0 cycle gap analysis §3.6 D-W-1** — evaluation OUT (orthogonal scope to v10.2.0 user mandate per `.local/research/v10.3.0_retrospective.md` line 89).
* **v10.3.0 retrospective §5** (`.local/research/v10.3.0_retrospective.md` lines 114-120) — re-telegraphed for v10.4.0 (cycle N+2 from v10.2.0).
* **v11.0.0 SI-1** (this cycle) — per the v10.3.0 telegraph, v10.4.0 was the earliest landing slot; v11.0.0 is the next eligible.

The 4-cycle floating pattern matches what `.local/research/v10.0.0_retrospective.md` line 236 calls the "2-cycle telegraph cadence is real" learning — but extended one round further. No quantitative analysis exists today of WHY the proposal floats: is it (a) the W-21 ≥ 9.5/10 bar that no L0 SI-3 evaluator has reached on this candidate, or (b) the proposal is correctly identified as A-1 architectural rather than Soul-immutable?

## §2 — Patch Design

**Algorithm** (analysis-only — zero rule mutation):

1. Author `.local/research/v11.0.0_w21_threshold_empirical_check.md` (~250 LOC). The artifact lives under `.local/research/` (gitignored), is human-readable, and the L0 cycle-lead consumes it during v11.0.0 cycle-plan synthesis.
2. The artifact contains 5 sections:
   * §1 **Telegraph history** — verbatim cite of the 4 telegraphs above with retrospective line citations.
   * §2 **Telegraph-floating root-cause analysis** — apply the W-21 D4 4-criterion checklist to the candidate AS IF it were entering v11.0.0 SI-1. For each criterion, assess: (a) is it satisfied by the candidate's current proposal text, (b) what would be needed to satisfy.
   * §3 **A-1 vs Soul-rule classification test** — apply the Soul-vs-Architecture decision rule from ADR-007 lines 183-188 ("Soul rules accrete only when a new immutable constraint is discovered"). Determine whether "Parallel Wave Dispatch Invariant" is: (a) a true immutable invariant (Soul candidate), (b) an architectural decision better suited for A-7 (Architecture rule N+1), or (c) a workflow rule better suited for W-22 (Workflow rule N+1).
   * §4 **Threshold calibration question** — quantitative table comparing the 9.5/10 threshold to actual SI-3 §3.2 architecture-rationality scores from cycles v9.0.0 → v10.3.0 (data: `.local/research/v9.X.X_evaluation.md` and `v10.X.X_evaluation.md` files). Identify whether 9.5 is achievable historically.
   * §5 **Recommendation for v12.0.0+ deliberation** — neutral problem statement ONLY. Does NOT propose changing W-21 wording / threshold / cycle gap.
3. The artifact is a research deliverable for v11.0.0; W-21 itself stays byte-identical at `.cursor/rules/repo-governance.mdc` §W-21 + `.rules/workflow.mdc` §W-21 + `AGENTS.md` §W-21.

**Files touched**:

* `.local/research/v11.0.0_w21_threshold_empirical_check.md` (NEW; ~250 LOC; gitignored under `.local/`).
* **NONE** in `.cursor/rules/` (G-5 PASS).
* **NONE** in `.rules/` (G-5 PASS — `.rules/workflow.mdc` §W-21 byte-identical).
* **NONE** in `src/devolaflow/` (no source code change).
* **NONE** in `tests/` (no new tests — analysis is qualitative + tabular).

**API surface**: zero. Pure documentation deliverable.

**No Soul rule changes**: G-5 gate explicitly cleared. W-21 wording is preserved verbatim. The artifact is a deliberation INPUT for a future cycle, not a proposal that itself requires W-21 deliberation.

## §3 — Small Project Evaluation

**Synthetic test bed**: `synthetic_small_repo` (per `v11.0.0_evaluation_methodology.md` §2). Small projects DO NOT use parallel L2-wave dispatch (single-task workflows or sequential 2-3 task waves dominate). The "Parallel Wave Dispatch Invariant" is by construction inapplicable to small repos.

**Operations exercised**: `init`, `feature` (1-file scope). NEITHER triggers a parallel L2 wave dispatch; both go L0 → L3 directly per the SKILL.md §"Quick Action Decision" table (lines 60-66) where Trivial/Simple complexity dispatches a single Task Agent with no L1/L2 layer.

**Metric collection** (per §4.2 architecture-health metrics):

* `Soul-rule churn rate` (additions per cycle) — already pinned at 0 per W-21 freeze.
* `Telegraph artifact count` (per cycle) — 0 for small projects.

**Expected delta (before → after)**:

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| W-21 wording (`.rules/workflow.mdc`) | byte-identical | byte-identical | 0 (preserved) | preserve |
| Soul rule count | 10 | 10 | 0 | preserve |
| Telegraph deliberation artifacts in `.local/research/` | 0 | 1 (`v11.0.0_w21_threshold_empirical_check.md`) | +1 | improve (visibility) |

**Pass criterion**: artifact exists, follows §2 5-section template, cites all 4 historical telegraphs by retrospective line. Small-tier passes by virtue of the documentation artifact existing — there is NO small-project runtime impact (correct: this analysis governs a Soul-rule decision that does not surface in small-project execution).

**If no improvement on small project**: this analysis is INHERENTLY a large-project-only deliverable (W-21 governance applies only when multi-wave parallel dispatch is in use, which requires complexity ≥ STANDARD per A-6.1). Per §6 below, the verdict is CONDITIONAL_PASS (large-only) — but the small-tier pass condition above (artifact exists) is met trivially.

## §4 — Large Project Evaluation

**Test bed**: DevolaFlow self at v10.3.0 baseline. v10.0.0 → v10.3.0 cycle history shows 4 documented telegraphs of the same candidate.

**Metric collection** (per §4.2 architecture-health metrics):

* `Soul-rule churn rate` (additions per cycle).
* `Telegraph deliberation artifacts produced` (count, this cycle).
* `Historical SI-3 §3.2 architecture-rationality scores` (data points: 6 cycles v9.0.0 → v10.3.0).

**Expected delta (v10.3.0 baseline → post-patch)**:

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| W-21 telegraph empirical analyses on file | 0 | 1 | +1 | improve (decision input) |
| Soul rule count | 10 | 10 | 0 | preserve (G-5) |
| Quantitative SI-3 §3.2 historical data points indexed | 0 (none indexed in one place) | 6 (cycles v9.0.0 → v10.3.0) | +6 | improve (data) |
| `tests/test_no_ghost_features.py::test_rule_count_under_cap` PASS | yes (≤ 60 cap) | yes | preserve | preserve |
| W-21 verbatim wording in compiled `AGENTS.md` | present | present | 0 | preserve |

**Pass criterion**: artifact contains a quantitative table of historical SI-3 §3.2 scores AND a neutral classification of the "Parallel Wave Dispatch Invariant" candidate as Soul / Architecture / Workflow.

**Side-effect check** (MUST NOT regress):

* `.cursor/rules/repo-governance.mdc` §W-21 — bytes-identical to v10.3.0 baseline.
* `.rules/workflow.mdc` §W-21 — bytes-identical.
* `AGENTS.md` §W-21 — bytes-identical (no recompile triggered).
* `tests/test_no_ghost_features.py::test_rule_count_under_cap` — preserved (no rule added).

## §5 — Benefit Metrics (≥ 3 quantitative; DF-internal)

| # | Metric | Before (v10.3.0) | After (v11.0.x analysis PV) | Δ | Bucket |
|:---:|---|---:|---:|---:|---|
| 1 | W-21 deliberation artifacts on file in `.local/research/` | 0 | 1 (`v11.0.0_w21_threshold_empirical_check.md`) | +1 | §4.2 architecture |
| 2 | Historical SI-3 §3.2 architecture-rationality scores indexed in one place | 0 cycles | 6 cycles (v9.0.0 → v10.3.0) | +6 data points | §4.5 observability |
| 3 | Telegraph cycles documented for "Parallel Wave Dispatch Invariant" candidate | unknown (scattered across 4 retros) | 4 cycles cited in single artifact | +4 (consolidated) | §4.2 architecture |
| 4 | Soul rule additions in v11.0.0 cycle | 0 (forecast) | 0 (preserved) | 0 (G-5 PASS) | §4.2 architecture |
| 5 | LOC change in `.cursor/rules/repo-governance.mdc` | 0 | 0 | 0 (G-5 + ADR-007 D4 preserved) | §4.3 code quality |

NONE of these metrics rely on EvoBench `q` / `pass_rate` / `gap_score` (G-1 PASS).

## §6 — Admission Verdict

**PASS** for the analysis artifact deliverable.

The W-21 rule is preserved bytes-identical. The "Parallel Wave Dispatch Invariant" candidate is NOT proposed for Soul-rule landing in v11.0.0 (telegraph cycle gap is intentional — per W-21 D4 #1 the 2-cycle gap is "mandatory" and v11.0.0 is the FIRST cycle eligible to evaluate the v10.3.0 re-telegraph; this analysis is the SI-1 gap-analysis entry per W-21 D4 #2, but does NOT itself constitute the SI-3 §3.2 ≥ 9.5/10 evaluation that would be needed to land the rule).

The recommendation in §5 of the analysis artifact is for a FUTURE cycle (v12.0.0+) to either:

1. Run the SI-3 §3.2 evaluation against the candidate and either land at S-11 (if score ≥ 9.5) or DEFER again with explicit deliberation of the gap, OR
2. Re-classify the candidate as A-7 (Architecture rule N+1) per ADR-007 lines 183-188 ("Architecture rules emerge naturally from refactor cycles") if SI-3 §3.2 evaluation determines the constraint is architectural rather than immutable invariant.

This patch does NOT bind the future cycle to either path. Its sole deliverable is the analysis input.

## §7 — Effort Estimate

**S** (≤ 0.3 PV) — confirms the source doc estimate (line 125). Breakdown:

* Read 4 historical retrospectives + extract telegraph wording verbatim: ~30 min.
* Read 6 historical evaluations + extract SI-3 §3.2 scores into table: ~45 min.
* Apply ADR-007 Soul-vs-Architecture classification: ~30 min.
* Write artifact + section structure: ~1 hour.

W-17 test budget consumption: **0** NEW test functions (analysis-only). Net W-17 contribution: 0 / +30 per-PV cap.

## §8 — Dependencies

**none** — pure documentation deliverable. Does NOT depend on D-P-1 (audit script), D-P-3 (schema demo), or D-P-4 (plan-mode template). May INFORM future-cycle Soul-rule deliberations independently.

## §9 — Risk Register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | Analysis artifact is mistaken for a W-21 mutation proposal by future operators | minor | Artifact §1 header explicitly states "ANALYSIS-ONLY per v11.0.0 G-5 Soul-freeze gate; W-21 wording preserved bytes-identical"; cites the source doc line 124 instruction verbatim |
| 2 | Recommendation in §5 is interpreted as committing the future cycle to a specific path (Soul vs Architecture) | minor | §5 explicitly enumerates BOTH paths with a "future cycle decides" disclaimer; cites W-21 D4 #1 + #2 + #3 + #4 verbatim as the gating contract |
| 3 | Artifact lifetime exceeds 1 cycle and the data becomes stale (e.g., new retrospective adds 5th telegraph) | minor | Artifact footer includes "valid as of: <date> / re-author when: telegraph count changes OR SI-3 §3.2 evaluation runs"; the cost of re-running this analysis is ≤ 30 min |

ZERO blocker / major risks because the patch is documentation-only.

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: stretch
