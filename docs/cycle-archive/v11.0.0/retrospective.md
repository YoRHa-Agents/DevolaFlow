# v11.0.0 Retrospective — MAJOR Cycle Close (5-MINOR rollup + stretch)

> Per W-7 / SI-8 (`.cursor/rules/repo-governance.mdc` + `AGENTS.md` §W-7):
> every MAJOR cycle ships a retrospective covering: gaps identified,
> what was implemented, what was deferred and why, and key learnings.
> Cycle: v11.0.0 MAJOR rollup, capping 5 MINORs (v10.4.0 → v10.5.0 →
> v10.6.0 → v10.7.0 → v10.8.0) + 1 MAJOR (v11.0.0).
> Date: 2026-05-04.
> External tools (S-7): DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`,
> NineS `https://github.com/YoRHa-Agents/NineS`, Si-Chip `https://github.com/YoRHa-Agents/Si-Chip`.

## 1. Gaps identified (from v11.0.0 SI-1 planning gate)

The v11.0.0 cycle plan (`.local/research/v11.0.0_cycle_plan.md`) was
the L0 SI-1 (W-1) Planning Gate output synthesising **27 Patch Design
Specifications (PDS)** from `.local/research/v11.0.0_patches/D-*-*.md`
into a 5-MINOR + 1-MAJOR rollup shape. The PDS pile derived from
`.local/research/v10_internal_optimization_directions.md` — a user-authored
inventory of 27 internal-quality optimization directions accumulated
across v9.x → v10.3.0 cycles. The directions spanned 5 thematic waves:

* **Wave 1 — Developer Experience & Reference Audit Foundation** (D-X
  family + D-D baseline audits): operator-facing tooling gaps (scaffold
  CLI for templates + references, SI-10 fast-path Makefile target,
  reference-utilization empirical audit, long-reference evidence audit,
  troubleshooting handbook).
* **Wave 2 — Architecture & Documentation Health** (D-A family + D-D
  hygiene): A-1 hierarchy empirical audit, 22-template legacy-tagging,
  A-6 workspace-activation refinement, line-budget counter-effect eval,
  W-17/W-18 maintenance trajectory.
* **Wave 3 — Protocol Audit + Observability Improvements** (D-P + D-O
  families, standard tier): canonical_order tail-field non-emptiness
  audit, STATUS.yaml extensibility NEST demo, three-evaluator rosetta
  reference, SI-3 6-dim auto-collector, in-cycle research index.
* **Wave 4 — Code Quality (NineS Cleanup + Refactors)** (D-Q family,
  most ambitious): 7 NineS warning closures via helper extractions,
  feedback.py god-function refactor, compressor/ post-split health
  snapshot.
* **Wave 5 — External Tool Coupling Hardening** (D-C family): degraded
  mode contract for 4 plugins, bridge shape contract tests (ends 2-year
  integration-test gap), pre_plugin_invocation responsibility split.

Plus 4 **stretch-tier** patches held for the MAJOR rollup (D-P-2 W-21
threshold empirical check, D-P-4 plan-mode multi-step reasoning eval,
D-O-4 SI-10 gate chain growth forecast, D-Q-3 lifecycle 10-event
taxonomy rename — the pure-alias rename shipping in v11.0.0 PV-02).

**Admission matrix**: 22 PASS + 5 CONDITIONAL_PASS (D-A-1, D-D-4,
D-O-1, D-O-4, D-Q-3) + 0 REJECT + 0 DEFER per G-1..G-9 gates, at
`v11.0.0_cycle_plan.md` §2. The CONDITIONAL_PASS tier reflects
single-tier applicability (typically large-project-only; the
synthetic small repo cannot exhibit multi-evaluator overlaps, SI-10
chains, L1/L2 dispatch cadence, W-17/W-18 lint accumulation, or
lifecycle-event taxonomy concerns).

**User sign-off** on the cycle plan (per `v11.0.0_cycle_plan.md` §8
Q1-Q10 sign-off questions + the Chinese-language selection list
`.local/research/v11.0.0_选型清单_中文版.md`, Option A):

* Q1 5-MINOR + 1-MAJOR shape — YES.
* Q2 all 27 directions admitted — YES.
* Q3 +3 new references (troubleshooting + evaluator-rosetta +
  degraded-mode) — YES (with R-3/R-4 pre-flight SF-1 expansion).
* Q4 D-A-2 Phase A only (defer Phase B to v12.0+) — YES.
* Q5 D-Q-3 deferred to v11.0.0 stretch — YES.
* Q6 D-C-2 weekly CI cron — YES.
* Q7 W-19 cycle archive at v11.0.0 PV-03 — YES (idempotent single-archive rule).
* Q8 SI-3 auto-collector 0.6 obj / 0.4 subj weighting — YES (validate across 2 cycles).
* Q9 W-3 SI-3 STRICT MAJOR ≥9.0 threshold for v11.0.0 close — YES.
* Q10 single-branch + 1 PR pattern (v10.2.0 precedent) — YES.

## 2. What was implemented

**Cycle-cumulative summary** (across 5 MINORs + 1 MAJOR):

### 2.1 v10.4.0 — Developer Experience & Reference Audit Foundation

* D-X-3 W-9 SI-10 fast-path (`Makefile::precommit-fast` + `precommit-full`).
* D-X-1 scaffold CLI (`scripts/scaffold_template.py` + `scripts/scaffold_reference.py`).
* D-X-2 reference creation pipeline (auto-extracts `MIRRORED_FILES`
  from SKILL.md Reference Navigation Guide; generates W-18 lint stub).
* D-X-5 troubleshooting handbook (NEW `references/troubleshooting.md`;
  the 15th SF-4 canonical reference).
* D-D-1 reference utilization audit
  (`scripts/audit_reference_utilization.py` 70-cell sweep).
* D-D-2 long-reference evidence
  (empirical envelope-creation rate measurement).
* W-16 wholesale baseline regen at PV-01 (cycle-start precedent).
* Retrospective at `.local/research/v10.4.0_retrospective.md`.

### 2.2 v10.5.0 — Architecture & Documentation Health

* D-A-1 L1/L2 audit (empirical scan of v9.0.0..v10.3.0 cycle plans;
  advisory SKILL.md wording).
* D-A-2 Phase A template usage audit
  (`scripts/audit_template_usage.py`; 16/22 templates tagged `(legacy)`;
  Phase B deferred to v12.0+ per Q4 sign-off).
* D-A-3 agent-workspace §3.6 "Resume After Pause" (~120 LOC doc-only).
* D-A-4 change_activation.py `_TRIVIAL_FILE_CEILING` 1→2 + `force_no_change` param.
* D-D-3 line-budget counter-effect audit.
* D-D-4 W-17/W-18 maintenance trajectory audit
  (telegraphed consolidation for v11.0.x / v12.0.0+).
* Retrospective at `.local/research/v10.5.0_retrospective.md`.

### 2.3 v10.6.0 — Code Quality (NineS Cleanup + Refactors)

* D-Q-1 seven-helper extraction batch (CC ≥ 10 reductions in
  `test_on_complete`, `auto_write_handoff`, `pre_plugin_invocation`,
  `installer` helpers; 7 NineS warnings closed 39 → 32).
* D-Q-2 feedback.py `ProposalEmitter` extraction (5-line façade;
  S-10 invariant preserved byte-identically).
* D-Q-4 compressor/ NineS analysis
  (closes 547-day gap since v9.3.0 PV-04 split; zero new warnings).
* Retrospective at `.local/research/v10.6.0_retrospective.md`.

### 2.4 v10.7.0 — Protocol Audit + Observability Improvements

* D-P-1 canonical_order audit
  (`scripts/audit_canonical_order.py`; 10-baseline byte test PASS preserved).
* D-P-3 STATUS.yaml extensibility NEST demo (one optional field via A-2.3).
* D-O-1 evaluator rosetta (NEW `references/evaluator-rosetta.md`;
  16th SF-4 canonical reference; 6×9 C/O/· cell mapping).
* D-O-2 SI-3 6-dim auto-collector
  (`scripts/auto_collect_si3_metrics.py`; 0.6 obj / 0.4 subj per Q8).
* D-O-3 in-cycle research index
  (`agent_workspace/reporter.py::render_workspace_report` +
  `workspace_report.md.j2` 3rd section).
* Retrospective at `.local/research/v10.7.0_retrospective.md`.

### 2.5 v10.8.0 — External Tool Coupling Hardening

* D-C-1 degraded-mode contract (NEW `references/degraded-mode.md`;
  17th SF-4 canonical reference; opens with "Degraded ≠ Full" warning
  per R1; 4-plugin coverage).
* D-C-2 bridge shape contract tests
  (NEW `tests/integration/` package; 12 contract tests + 8 captured
  fixtures with `captured_from_plugin_version:` headers +
  `scripts/refresh_bridge_fixtures.py` + weekly CI cron).
* D-C-3 pre_plugin_invocation split
  (DEFAULT_EVENTS positions 11 + 12 per A-2.2 APPEND; position 9 alias
  preserved byte-identically; `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` telegraphed
  for v12.0.0+).
* Retrospective at `.local/research/v10.8.0_retrospective.md`.

### 2.6 v11.0.0 — MAJOR Rollup + Stretch + Final Regression

* **PV-01 (chore(v11.0.0-rc1))**: D-P-2 + D-P-4 stretch (analysis +
  doc-only; zero src/ changes). NEW
  `.local/research/v11.0.0_w21_threshold_empirical_check.md` (D-P-2;
  5-section structure per D-P-2 §2; W-21 wording byte-stable; verdict:
  threshold appropriately calibrated; recommendation: classify the S-11
  candidate "Parallel Wave Dispatch Invariant" as Architecture A-7
  rather than Soul per ADR-007 183-188). `plan-mode-enforcement.md`
  adds §3.2 "Multi-Step Plans" (~210 LOC; `[EXPLORE]` +
  `[REVISABLE: <stage-id>]` opt-in annotation conventions; zero schema
  field additions; reference 647 → 810 LOC within Large tier).
* **PV-02 (chore(v11.0.0-rc2))**: D-O-4 + D-Q-3 stretch. NEW
  `.local/research/v11.0.0_si10_gate_growth_analysis.md` (D-O-4;
  forecasts +1 gate per MAJOR cycle to 10 gates at v13.0.0;
  recommends reorganization trigger at gate_count = 10). D-Q-3
  PURE-ALIAS rename at `src/devolaflow/lifecycle/__init__.py`:
  4 NEW canonical event names appended at DEFAULT_EVENTS positions
  13-16 per A-2.2; 4 OLD names at positions 3/4/5/7 preserved
  BYTE-IDENTICALLY via `dispatcher._EVENT_ALIASES` map (1-cycle
  schedule; v12.0.0 removal target telegraphed). +5 NEW alias tests
  at `tests/test_lifecycle_hooks.py`; env-flags.md §7.A
  "Lifecycle event taxonomy" subsection documents the rename.
* **PV-03 (chore(v11.0.0))** — this commit:
  * Canonical-7 version sync 10.8.0 → 11.0.0 (8 files).
  * W-19 cycle archive `docs/cycle-archive/v11.0.0/` with the 5-MINOR
    artifact bundle + v11.0.0 rollup artifacts.
  * `CHANGELOG.md` `## [11.0.0] - 2026-05-04` MAJOR-rollup section
    at the TOP of the file (distinct shape from MINOR entries;
    enumerates all 27 directions + landed PV).
  * `workflow-system/human/demo/version-timeline/versions.json`
    v11.0.0 entry per WX-2.
  * EN/ZH human docs refreshed via `make sync-human-docs`.
  * W-7 / SI-8 retrospective (this document).
  * W-3 / SI-3 MAJOR evaluation at
    `.local/research/v11.0.0_evaluation.md` (composite ≥ 9.0).
  * W-18 ghost-audit refresh (`test_v11_0_0_new_symbols_have_coverage`)
    BEFORE the CHANGELOG entry lands.

**27 / 27 directions shipped. 0 rejected. 0 deferred to future cycles**
(5 CONDITIONAL_PASS items all landed in their assigned PVs with
single-tier applicability; see §3 for the items carried forward to
future cycles, which are distinct from "deferred directions").

## 3. What was deferred and why

The following items are carried forward explicitly for future cycle
planning gates (W-1 / SI-1). This is **not** a list of rejected
directions — all 27 v10 internal optimization directions shipped.
These are operator-/maintainer-facing items that surfaced during the
cycle and were triaged to later cycles.

1. **S-11 Soul rule candidate "Parallel Wave Dispatch Invariant"** —
   re-telegraphed per W-21 2-cycle cadence. v10.0.0 retrospective
   §3.5 first telegraphed → v10.3.0 retrospective §5 re-telegraphed
   → v11.0.0 cycle plan §7 re-telegraphed → D-P-2 analysis
   (`.local/research/v11.0.0_w21_threshold_empirical_check.md`)
   classifies it as **Architecture A-7 candidate** (not Soul) per
   ADR-007 lines 183-188. Either class now requires a SI-1 gap-analysis
   entry at v11.2.0 (cycle N+2 from this telegraph) to continue the
   multi-cycle deliberation cadence. **Defer to: v11.2.0 SI-1.**

2. **D-A-2 Phase B (compose-collapse 22 templates → ~6)** — per Q4
   sign-off: Phase A audit (v10.5.0 PV-02) must demonstrate operator
   acceptance of `(legacy)` tagging before destructive collapse. 2+
   cycle operator feedback runway needed. **Defer to: v12.0+ pending
   Phase A operator feedback.**

3. **`DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` env flag (D-C-3 telegraph)** —
   new env flag requires W-20 §3 orthogonality re-evaluation; current
   v10.8.0 cycle shipped the hook-event split (orthogonal responsibility
   separation) but kept the single env flag during the 1-cycle alias
   window. **Defer to: v12.0.0+ when W-20 reuse-first re-applied.**

4. **Lifecycle 4-event alias removal (D-Q-3 deprecation runway)** —
   v11.0.0 PV-02 ships the PURE-ALIAS rename with OLD names
   (`file_write`, `task_stop`, `format_on_edit`, `envelope_write`)
   preserved byte-identically at DEFAULT_EVENTS positions 3/4/5/7.
   1-cycle schedule: OLD names emit `DeprecationWarning` at v11.2.0
   cycle close; v12.0.0 cycle SI-1 evaluates removal. **Defer to:
   v12.0.0 SI-1.**

5. **W-18 lint consolidation** — the `tests/test_no_ghost_features.py`
   cycle-stanza count reached ~30 at v10.8.0 close. D-D-4's v10.5.4
   audit projected ~24K LOC by v15.0.0 if linear extrapolation holds.
   The cycle deferred consolidation to preserve per-cycle traceability
   per `v10.5.0_retrospective.md` §3.3. D-D-4 telegraphed
   `scripts/consolidate_w18_lints.py` as the proposed mechanism
   (cycle-specific lints collapse into common skeleton with inline
   cycle-version comments). **Defer to: v11.0.x or v12.0.0+ per D-D-4.**

6. **Three NineS `error` findings (CC ≥ 21)** — carried forward from
   the v10.3.0 baseline unchanged through the cycle:
   * `src/devolaflow/gate/scorer.py:1654` `evaluate_gate` CC=22.
   * `src/devolaflow/shell_proxy/commands.py:389` `build_mapping_from_dict` CC=21.
   * `src/devolaflow/writing_style/transforms/bullets.py:41` `_collapse_block` CC=25.
   D-Q-1 scope was warning-only by design (closed 7 warnings per
   `v10.6.0_retrospective.md` §2.1); errors deferred as separate
   refactor cycle. **Defer to: v11.0.x or v12.0.0 micro-PVs.**

7. **DEFAULT_EVENTS multi-baseline byte test** — the dispatch-payload
   `canonical_order` has a 32/32 multi-baseline byte test
   (`tests/test_layout_invariant_multi_baseline.py`) but lifecycle
   `DEFAULT_EVENTS` does not. Post D-Q-3 alias rename (positions
   13-16 appended; positions 1-12 byte-stable), the case for a
   unified-invariant test surface grows. Telegraphed in the pre-v11
   SI-3 evaluation §6 item 2. **Defer to: v11.0.x.**

8. **Automated per-PV W-17 audit gate** — `make audit-w17-cycle-budget`
   consuming `git log --since=<cycle-start>` to mechanise per-PV test
   count auditing. Currently a PR-author responsibility; the v10.8.0
   cycle had one mid-implementation forecast-vs-cap drift (33-43 vs
   cap 30) resolved via W-17 spirit consolidation. Telegraphed for
   automation per pre-v11 SI-3 §6 item 3. **Defer to: v11.0.x.**

9. **`task_adaptive_selector.py` section_anchors migration** — 18
   pytest `DeprecationWarning: section … resolved via deprecated
   line-based lookup` warnings from
   `src/devolaflow/task_adaptive_selector.py:614` (telegraphed in
   `.local/research/v8.2.0_patch_plan.md` §3 PV-05 AC #1; migration
   from line-range lookup to registry-named anchors). Not cycle-
   introduced; pre-cycle baseline backlog. **Defer to: v11.0.x or
   v12.0.0+ cleanup cycle.**

10. **Bridge-fixture staleness lint** — telegraphed at v10.8.0
    retrospective §3.1 once the `bridge-fixture-refresh.yml` weekly
    cron has ≥4 data points. The proposed lint: fail CI when
    `captured_from_plugin_version` lags `runtime-plugins.yaml
    min_version` by > 2 minor versions. **Defer to: v11.0.x after
    ≥4 cron data points accumulated.**

11. **Per-PV / per-file Si-Chip iteration_delta decomposition**
    (carried from v10.3.0 deferred items) — requires upstream
    Si-Chip `aggregate_eval.py` change OR custom DF wrapper;
    orthogonal to v11.0.0 internal-quality theme. **Defer to:
    v11.0.x or upstream Si-Chip issue.**

12. **NineS A1 `code_coverage` collector timeout** (carried from
    v10.3.0 deferred items) — upstream NineS infrastructure; W-2
    manual fallback sufficient. **Defer to: NineS upstream tracker.**

**Total deferrals: 12 items** (far exceeds W-7 §3 minimum of 5).

## 4. Key learnings

1. **5-MINOR + 1-MAJOR rollup shape holds under scale.** The v10.0.0
   cycle was the precedent (5 MINORs → MAJOR); v11.0.0 is the second
   time this shape was executed. Cycle-cumulative coordination cost
   stayed bounded (each MINOR shipped independently; each MINOR
   retrospective is standalone + feeds the MAJOR retrospective via
   §2 aggregation). Per-MINOR PR would have produced 6 PRs; single-branch
   (Q10) produced 1 PR. Single-branch wins when the cycle-to-cycle
   gap analysis is predictable (all 27 directions admitted upfront).

2. **PURE-ALIAS refactors are the best-ROI refactor pattern under
   cache-layout constraints.** D-Q-3 (lifecycle rename) + D-C-3
   (pre_plugin_invocation split) both used the 1-cycle-alias pattern.
   Both shipped with zero behavioural delta + full observability of
   the NEW canonical names. The alternative — immediate rename without
   alias — would have forced every downstream operator hook to update
   in the same cycle, greatly increasing coordination cost. A-2.2
   APPEND-ONLY + the alias lookup in the dispatcher is the cheap
   primitive that enables this pattern.

3. **Stretch-tier patches absorb rollup time cleanly.** The 4 stretch
   patches (D-P-2, D-P-4, D-O-4, D-Q-3) together added 6 NEW test
   functions + ~340 LOC (mostly documentation + analysis). They
   shipped in 2 PVs of the MAJOR rollup without stressing the cycle
   budget. Stretch tier is the right classifier for analysis-only +
   doc-only + pure-alias-refactor patches — they defer cleanly from
   MINOR budgets when NineS / refactor load is heavy.

4. **Auto-collector + subjective half is the right SI-3 shape.**
   D-O-2's `scripts/auto_collect_si3_metrics.py` ran end-to-end in
   ~65 s on the pre-v11 baseline (per `v10.8.x_pre_v11_evaluation.md`
   §2) with 100% auto-fill rate. The auto-collector's sole known
   artifact (the W-17 sub-score hardcoding the per-PV +30 cap even
   when handed a cycle-cumulative base-ref) was correctly compensated
   by the subjective half (+9.5 on Test adequacy despite the
   mechanical 6.67 from the auto-collector). 0.6 obj / 0.4 subj
   weighting (Q8 sign-off) produced a 9.30 composite on the pre-v11
   self-loop — above the 9.0 STRICT MAJOR threshold with +0.30 margin,
   matching the cycle plan §5 forecast `target ~9.3` exactly.

5. **W-21 Soul-set freeze discipline held for 2 full cycles.**
   S-11 candidate "Parallel Wave Dispatch Invariant" was telegraphed
   at v10.0.0 retrospective, re-telegraphed at v10.3.0, and
   re-telegraphed again at v11.0.0 cycle plan + D-P-2 analysis
   (`v11.0.0_w21_threshold_empirical_check.md`). D-P-2's analysis
   classified the candidate as Architecture A-7 (per ADR-007
   183-188), which is a narrower gate than Soul but still requires
   the cycle-N+2 deliberation. This multi-cycle deliberation cadence
   is exactly what W-21 §3 rationale asks for — the "lifetime cost
   of immutable invariants is multiplicative" argument plays out
   empirically when 3 consecutive cycles must each carry the telegraph
   forward without landing the rule.

6. **Reference count at 17 tests the SF-1 expansion threshold.** The
   cycle added 3 references (troubleshooting + evaluator-rosetta +
   degraded-mode); the R-3/R-4 pre-flight in v10.4.0 PV-01 was the
   right call — `scripts/sync_cursor_skill.py::MIRRORED_FILES` +
   `tests/test_version.py::_MIRRORED_SKILL_FILES` both extended cleanly.
   Future cycles adding references > 17 should re-audit whether the
   canonical list is accumulating or whether individual references
   should split / merge.

7. **Cycle-cumulative W-17 discipline requires mid-cycle audit
   ritual.** The v10.8.0 PR had a mid-implementation +33-43 vs +30
   cap drift resolved by consolidation. A `make audit-w17-cycle-budget`
   Makefile target (deferred; §3 item 8) would mechanise this. Until
   then, the W-17 mid-cycle audit at PV-05 (per `repo-governance.mdc`
   W-17) remains a human-side discipline that the cycle-lead L0 must
   perform.

8. **ADR-driven governance evolution works.** v9.0.0 PV-07 ADR-007
   rule-rebalancing + W-21 Soul-set freeze produced 2 consecutive
   cycles (v10.0.0, v11.0.0) where the Soul rule count stayed at 10
   without friction. The A-5..A-7 architecture tier absorbed 2 new
   rules (A-5 SSOT registry at v8.4.3, A-6 workspace auto-activation
   at v9.1.2) without S-* promotion. This validates the rule-tier
   separation.

## 5. Verification (W-9 SI-10 6-step + extras at PV-03 close)

**Base W-9 SI-10 6-step:**

1. `python -m pytest tests/ -q` — ~4226 passed, 25 skipped, 2 xfailed
2. `ruff check src/ tests/` — clean (288 files)
3. `ruff format --check src/ tests/` — clean (288 files)
4. `python -m pytest tests/test_version.py -v` — 12 passed, 23 skipped (mirror absent)
5. `python -m pytest tests/test_benchmarks.py -v` — 36 passed
6. `make check-cursor-skill` — exit 0 (mirror absent per SF-3 opt-in)

**Additional gates (PV-03 MAJOR-cycle close):**

* `python -m pytest tests/test_dispatch_emission_runs_hooks.py -v` —
  10 passed, byte-identical per S-10 invariant (D-Q-3 §4 large_eval R1 mitigation).
* `python -m pytest tests/test_layout_invariant_multi_baseline.py -v` —
  32 passed, A-2.4 multi-baseline byte test green.
* `python -m pytest tests/test_lifecycle_hooks.py -v` — 75 passed
  (70 baseline + 5 D-Q-3 alias regression tests).
* `make build-skill` — all 4 adapters (Cursor, Codex, Claude, Copilot)
  build successfully within budgets per W-12.
* W-3 / SI-3 MAJOR evaluation composite ≥ 9.0 per
  `.local/research/v11.0.0_evaluation.md`.
* W-7 / SI-8 retrospective (this file) with 4 mandatory sections +
  ≥5 deferrals (shipped 12 above).
* W-19 cycle archive — `docs/cycle-archive/v11.0.0/` populated with
  5 MINORs of artifacts + v11.0.0 MAJOR artifacts (idempotent per W-19).

## 6. Cross-references

* `.local/research/v11.0.0_cycle_plan.md` — L0 SI-1 planning gate output
  (the cycle contract; §4 per-PV deliverable map).
* `.local/research/v11.0.0_选型清单_中文版.md` — user selection list (Option A).
* `.local/research/v11.0.0_decomposition_plan.md` — L0 dispatch contract.
* `.local/research/v11.0.0_evaluation_methodology.md` — small + large eval harness.
* `.local/research/v11.0.0_admission_checklist.md` — 9 mainline gates.
* `.local/research/v11.0.0_patches/D-*-*.md` × 27 — per-direction PDS files.
* `.local/research/v10.[4,5,6,7,8].0_retrospective.md` — 5 prior MINOR retrospectives.
* `.local/research/v10.8.x_pre_v11_evaluation.md` — pre-v11 self-loop
  SI-3 evaluation (composite 9.30; baseline for v11.0.0 evaluation).
* `.local/research/v10.8.x_pre_v11_self_loop_report.md` — pre-v11 self-loop GREEN verdict.
* `.local/research/v11.0.0_w21_threshold_empirical_check.md` — D-P-2 analysis (PV-01).
* `.local/research/v11.0.0_si10_gate_growth_analysis.md` — D-O-4 analysis (PV-02).
* `.local/research/v11.0.0_evaluation.md` — W-3 SI-3 MAJOR evaluation (this cycle).
* `docs/cycle-archive/v11.0.0/` — W-19 cycle archive (bundled in this commit).
* `CHANGELOG.md` `## [11.0.0] - 2026-05-04` — the user-visible rollup entry.
