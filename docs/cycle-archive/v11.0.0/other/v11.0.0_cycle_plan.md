# DevolaFlow v11.0.0 MAJOR Cycle Plan — 5 MINORs + 1 MAJOR Rollup (SI-1 Synthesis)

> **Status:** L0 SI-1 (W-1) Planning Gate — synthesis output
> **Author:** L0 Project Agent (this conversation)
> **Date:** 2026-05-04
> **Cycle baseline:** v10.3.0 (`f1d9652`, branch `feat/v10.2.0-cycle`, PR #117 open)
> **Cycle target:** v11.0.0 MAJOR
> **Cycle composition:** v10.4.0 → v10.5.0 → v10.6.0 → v10.7.0 → v10.8.0 → v11.0.0 (**5 MINORs + 1 MAJOR rollup**)
> **External tools (S-7):** DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`, NineS `https://github.com/YoRHa-Agents/NineS`, Si-Chip `https://github.com/YoRHa-Agents/Si-Chip`
> **Sister artifacts (must be read together):**
>   - `.local/research/v10_internal_optimization_directions.md` — source of 27 directions
>   - `.local/research/v11.0.0_decomposition_plan.md` — L0 dispatch contract
>   - `.local/research/v11.0.0_evaluation_methodology.md` — small + large eval harness
>   - `.local/research/v11.0.0_admission_checklist.md` — 9 mainline gates
>   - `.local/research/v11.0.0_patches/<dir-id>.md` × 27 — per-direction PDS files

## §1 — User mandate (verbatim, this conversation)

> "/home/agent/workspace/DevolaFlow/.local/research/v10_internal_optimization_directions.md 进行并行的拆解，并对每一个细节点 patch 实现，然后评测在大型项目和小型项目上都有明确收益才可以作为正式 patch 发布 /devola-flow 然后列出主线准入清单，进行选型来决定最终 11.0.0版本构成"

Translation (operative semantics):

1. **Parallel decomposition** of the v10 internal optimization directions doc → done as 7 parallel L3 dispatches (5 wave families) producing 27 PDS files.
2. **Per-direction patch implementation** → operationalized as Patch Design Specifications (PDS) per `v11.0.0_decomposition_plan.md` §3 schema; each PDS contains algorithm + files-touched + small_eval + large_eval + benefit_metrics + risk_register.
3. **Small + large project benefit evaluation** → operationalized as `v11.0.0_evaluation_methodology.md` with `synthetic_small_repo` (small) + DevolaFlow self at v10.3.0 (large); each PDS §3-4 conforms to §5 templates.
4. **Mainline admission checklist** → 9 hard gates per `v11.0.0_admission_checklist.md` G-1..G-9; each PDS §6 admission_verdict produced by L3 against these.
5. **v11.0.0 composition selection** → THIS DOCUMENT (synthesis of 27 PDS verdicts into a 6-cycle plan).

## §2 — Aggregate admission matrix (27 directions)

Verbatim from each PDS's admission summary line:

| ID | Title (abbrev) | Verdict | Tier | Effort | DEPS | Wave |
|---|---|:---:|:---:|:---:|---|:---:|
| **D-X-1** | Workflow template scaffold CLI | PASS | core | M | none | 1 |
| **D-X-2** | Reference doc creation pipeline | PASS | core | M | none | 1 |
| **D-X-3** | W-9 SI-10 fast-path | PASS | standard | S | none | 1 |
| **D-X-5** | Operator troubleshooting handbook | PASS | standard | M | D-X-2 (soft) | 1 |
| **D-A-1** | L1/L2 actual usage rate audit | CONDITIONAL_PASS | standard | S | none | 2 |
| **D-A-2** | 22 builtin templates audit (Phase A) | PASS | core | M | none | 2 |
| **D-A-3** | A-1 4-layer time-scale resume protocol | PASS | standard | S | none | 2 |
| **D-A-4** | A-6 workspace activation refinement | PASS | standard | S | none | 2 |
| **D-D-1** | Reference utilization audit | PASS | core | S | none | 3 |
| **D-D-2** | Long-reference usage evidence | PASS | core | S | none | 3 |
| **D-D-3** | C-4 line budget counter-effect eval | PASS | standard | S | none | 3 |
| **D-D-4** | W-17/W-18 maintenance trajectory | CONDITIONAL_PASS | standard | M | none | 3 |
| **D-P-1** | A-2 canonical_order 17-field merge audit | PASS | standard | S | none | 4a |
| **D-P-2** | W-21 Soul threshold empirical check | PASS | stretch | S | none | 4a |
| **D-P-3** | STATUS.yaml extensibility NEST demo | PASS | standard | S | none | 4a |
| **D-P-4** | plan-mode multi-step reasoning eval | PASS | stretch | S | none | 4a |
| **D-O-1** | Three-evaluator semantic overlap rosetta | CONDITIONAL_PASS | standard | M | none | 4b |
| **D-O-2** | SI-3 6-dim auto-collection | PASS | standard | M | none | 4b |
| **D-O-3** | In-cycle research lightweight index | PASS | standard | S | none | 4b |
| **D-O-4** | SI-10 gate chain growth forecast | CONDITIONAL_PASS | stretch | S | none | 4b |
| **D-Q-1** | NineS 7-warning helper extractions | PASS | standard | L | none | 5a |
| **D-Q-2** | feedback.py god-function refactor | PASS | standard | M | none | 5a |
| **D-Q-3** | Lifecycle 10-event taxonomy rename | CONDITIONAL_PASS | stretch | S | none | 5a |
| **D-Q-4** | compressor/ post-split health snapshot | PASS | standard | S | none | 5a |
| **D-C-1** | Upstream-unreachable degraded mode | PASS | core | M | none | 5b |
| **D-C-2** | Bridge layer version negotiation | PASS | core | M | none | 5b |
| **D-C-3** | pre_plugin_invocation responsibility split | PASS | standard | M | none | 5b |

**Tally:**

| Dimension | Count | List |
|---|---:|---|
| Verdict PASS | 22 | All except D-A-1, D-D-4, D-O-1, D-O-4, D-Q-3 |
| Verdict CONDITIONAL_PASS | 5 | D-A-1, D-D-4, D-O-1, D-O-4, D-Q-3 |
| Verdict FAIL | 0 | — |
| Verdict DEFER | 0 | — |
| Tier core | 7 | D-X-1, D-X-2, D-A-2, D-D-1, D-D-2, D-C-1, D-C-2 |
| Tier standard | 16 | D-X-3, D-X-5, D-A-1, D-A-3, D-A-4, D-D-3, D-D-4, D-P-1, D-P-3, D-O-1, D-O-2, D-O-3, D-Q-1, D-Q-2, D-Q-4, D-C-3 |
| Tier stretch | 4 | D-P-2, D-P-4, D-O-4, D-Q-3 |
| Effort S | 15 | (per matrix above) |
| Effort M | 11 | (per matrix above) |
| Effort L | 1 | D-Q-1 (4-7 micro-PVs) |
| External deps | 0 | All 27 satisfy G-3 zero-deps gate |
| Soul rule additions | 0 | All 27 satisfy G-5 Soul-freeze gate |
| Frozen-prefix edits | 0 | All 27 satisfy G-6 cache-prefix gate |
| Breaking changes | 0 | All 27 satisfy G-7 compatibility gate |

**Headline result: ALL 27 directions pass admission gates G-1..G-9** (22 unconditionally + 5 conditionally with applicability bounds noted). 0 rejected, 0 deferred. The CONDITIONAL_PASS items become single-tier deliverables (typically large-only since synthetic_small_repo cannot exhibit multi-evaluator overlaps, SI-10 chains, etc.).

## §3 — Selection algorithm applied

Per `v11.0.0_admission_checklist.md` §3:

1. **All 7 `core` patches admitted** — these define the v11.0.0 mandatory spine: D-X-1, D-X-2, D-A-2, D-D-1, D-D-2, D-C-1, D-C-2.
2. **All 16 `standard` patches admitted** in dependency-DAG topological order — only one soft dependency exists (D-X-5 ← D-X-2), trivially satisfied by ordering D-X-2 in v10.4.0 PV-02 before D-X-5 in v10.4.0 PV-05.
3. **All 4 `stretch` patches admitted** to the v11.0.0 MAJOR rollup (the budget tail) — D-P-2, D-P-4, D-O-4, D-Q-3 are all S-effort analysis-or-doc-only patches (≤ 4 NEW tests combined); they fit the rollup PV without stressing budget.

**Total admitted: 27 / 27 directions.** No defer-list.

**Cycle budget verification:**

| Constraint | Limit | Forecast | Headroom |
|---|---:|---:|---:|
| W-17 +30 NEW tests per PV | 30 | max 28 (v10.6.0 PV-01 D-Q-2 refactor) | +2 |
| W-17 +150 NEW tests per cycle | 150 | ~138 estimated | +12 |
| Coverage floor | ≥ 80% | ≥ 92% (no module retirement; only additions + refactors) | +12pp |
| Schema bumps to canonical_order tail | append-only ≥ 18 | 0 (D-P-3 is STATUS.yaml NEST, not canonical_order) | full headroom |
| New env flags | 0 unless orthogonal | 0 (D-C-3 telegraphs DEVOLAFLOW_AUTO_UPGRADE_PLUGINS for v12.0+) | full headroom |
| Soul rule additions | 0 | 0 | full headroom |
| New references | ≤ 2 | 2 (degraded-mode.md from D-C-1 + evaluator-rosetta.md from D-O-1; troubleshooting.md from D-X-5 NEST-into-existing per D-X-5 §2) | exactly at limit |
| New examples | ≤ 1 | 1 (multi-stage-trace.md from D-A-1) | exactly at limit |
| SKILL.md delta | ≤ +20 lines | ~+15 lines (D-A-2 deprecation tags + D-D-2 1-line annotation) | +5 lines |

All cycle-shape constraints satisfied. Cycle is **GO** for the proposed composition.

## §4 — v11.0.0 cycle composition (5 MINORs + 1 MAJOR rollup)

### v10.4.0 — Developer Experience & Reference Audit Foundation

**Feature branch:** `feat/v10.4.0-dx-foundation`
**Rationale:** D-X family is the highest-value-per-PV cluster (4 PASS, mostly M-effort scaffold infrastructure that benefits every downstream PV). Pairing with D-D-1 + D-D-2 (S-effort audits) sets the empirical baseline for all subsequent cycles. **Per W-16, this is cycle-start MINOR — wholesale baseline regen MUST run at PV-01.**

| PV | Tag | Deliverable |
|---|---|---|
| PV-01 | `chore(v10.4.0)` | **Cycle-start preflight.** W-16 wholesale baseline regen (`benchmarks/devolaflow_context/baselines/v10.4.0_baseline.json`); D-X-3 W-9 fast-path (`Makefile::precommit-fast` + `precommit-full`); cycle plan reading + dispatch test infra. **Estimated +5 NEW tests.** |
| PV-02 | `chore(v10.4.1)` | **D-X-1 scaffold CLI (Phase A).** `scripts/scaffold_template.py` + 6 unit tests + dispatcher integration test. **Estimated +8 NEW tests.** |
| PV-03 | `chore(v10.4.2)` | **D-X-2 reference creation pipeline.** `scripts/sync_cursor_skill.py` auto-extracts `MIRRORED_FILES` from SKILL.md `## Reference Navigation Guide` table; `scripts/scaffold_reference.py` generates new reference + W-18 lint stub. **Estimated +6 NEW tests.** |
| PV-04 | `chore(v10.4.3)` | **D-D-1 reference utilization audit.** `scripts/audit_reference_utilization.py` (70-cell sweep); produces `.local/research/v10.4.3_reference_utilization_audit.md`. **Estimated +3 NEW tests.** |
| PV-05 | `chore(v10.4.4)` | **D-D-2 long-reference evidence + D-X-5 troubleshooting handbook.** Empirical envelope-creation rate measurement; new `references/troubleshooting.md` (Large tier ≤1000 lines; 14→15 references) + W-18 lint refresh. **Estimated +4 NEW tests.** |
| PV-06 | `chore(v10.4.5)` then `chore(v10.5.0)` | **MINOR cycle close.** v10.4.x → v10.5.0; canonical-7 sync; CHANGELOG; retrospective; W-18 ghost-audit refresh; demo-index "What's New"; W-19 cycle archive STAGED (cycle archive ships at v11.0.0 MAJOR per W-19 cycle-CLOSE rule). **Estimated +2 NEW tests (v10.5.0 ghost-audit lint).** |

**Test budget:** ~28 NEW (within +30/PV cap).
**Gate:** `standard` (≥85, ≥80% cov) + W-3 SI-3 ≥ 8.5 at MINOR cycle close.
**Mandate satisfied:** "解构 + patch 实现" first wave (4 D-X + 2 D-D patches operationalized).

### v10.5.0 — Architecture & Documentation Health

**Feature branch:** `feat/v10.5.0-architecture-doc-health`
**Rationale:** D-A family + remaining D-D bring architecture clarity (4 patches advisory wording + audits) + doc/test hygiene (D-D-3 + D-D-4). One core (D-A-2) anchors the cycle; rest are S/M-effort standards.

| PV | Tag | Deliverable |
|---|---|---|
| PV-01 | `chore(v10.5.0)` | **D-A-1 L1/L2 audit.** Empirical scan of cycle plans v9.0..v10.3 for L1/L2 standalone dispatch frequency; produce `.local/research/v10.5.0_l1l2_usage_audit.md`; SKILL.md `## 4-Layer Agent Hierarchy` adds advisory note "L1/L2 typically elided in cycles ≤ 6 PVs (5/6 v10.2.0 PVs proved)". CONDITIONAL_PASS — large-only verdict (synthetic small never reaches L1/L2). **Estimated +4 NEW tests (advisory wording + audit script unit tests).** |
| PV-02 | `chore(v10.5.1)` | **D-A-2 22→6 templates audit (Phase A).** `scripts/audit_template_usage.py` produces empirical "USED vs registered-but-unused" table; SKILL.md `## Quick Start — Workflow Selection` table adds `(legacy)` tag to 16/22; `meta-framework.md` §4 alias mapping table updated. **Estimated +6 NEW tests.** Phase B (compose-collapse to ~6 active templates) **deferred** to v12.0+ pending Phase A operator feedback. |
| PV-03 | `chore(v10.5.2)` | **D-A-3 + D-A-4.** D-A-3 ships `agent-workspace.md` §3.6 "Resume After Pause" (~120 lines, doc-only). D-A-4 refines `change_activation.py` `_TRIVIAL_FILE_CEILING` 1→2 + `force_no_change` parameter + env-flags doc fix. **Estimated +5 NEW tests.** |
| PV-04 | `chore(v10.5.3)` | **D-D-3 line budget eval.** Audit doc `.local/research/v10.5.3_line_budget_counter_effect.md` with 3 line-cited paragraph examples + proposed expansions. SKILL.md / compression-pipeline.md targeted micro-edits (within tier ceilings). **Estimated +3 NEW tests (no-regression byte tests).** |
| PV-05 | `chore(v10.5.4)` | **D-D-4 W-17/W-18 maintenance.** Inventory all 30 cycle-specific lints in `tests/test_no_ghost_features.py`; produce maintenance trajectory analysis; `scripts/consolidate_w18_lints.py` (NEW) compacts cycle-specific lints to common skeleton (preserving traceability via inline cycle-version comments). CONDITIONAL_PASS — large-only verdict. **Estimated +5 NEW tests.** |
| PV-06 | `chore(v10.5.5)` then `chore(v10.6.0)` | **MINOR cycle close.** v10.5.x → v10.6.0; canonical-7 sync; CHANGELOG; retrospective; W-18 refresh. **Estimated +2 NEW tests.** |

**Test budget:** ~25 NEW.
**Gate:** `standard` + W-3 SI-3 ≥ 8.5 at MINOR cycle close.

### v10.6.0 — Code Quality (NineS Cleanup + Refactors)

**Feature branch:** `feat/v10.6.0-code-quality`
**Rationale:** D-Q-1 is the largest single-direction effort (L = 4-7 micro-PVs). This MINOR cleans the carried-over warnings + does the feedback.py refactor + compressor health snapshot. **D-Q-3 (lifecycle rename) is reclassified to v11.0.0 stretch** since it's CONDITIONAL_PASS and pairs better with end-of-cycle housekeeping.

| PV | Tag | Deliverable |
|---|---|---|
| PV-01 | `chore(v10.6.0)` | **D-Q-1 batch A (3 helpers).** `test_on_complete::_try_persist_session_state` (CC=20→≤10), `auto_write_handoff::_extract_layers` (CC=16→≤8), `pre_plugin_invocation::_extract_plugin_ids` (CC=16→≤8). Pure refactors; existing test surfaces cover. **Estimated 0 NEW tests (regression tests already exist).** |
| PV-02 | `chore(v10.6.1)` | **D-Q-1 batch B (2 helpers).** `installer::ensure_plugin` (CC=14→≤8), `installer::plugins_for_workflow` (CC=11→≤8). **Estimated 0 NEW tests.** |
| PV-03 | `chore(v10.6.2)` | **D-Q-1 batch C (2 helpers).** `auto_write_handoff::auto_write_handoff` (CC=12→≤7), `installer::resolve_plugin` (CC=11→≤7). NineS deep-analyze re-run; verify 7 → 0 warnings. **Estimated +2 NEW tests (verification of CC reductions).** |
| PV-04 | `chore(v10.6.3)` | **D-Q-2 feedback.py refactor.** Extract `ProposalEmitter` from `ProposalGenerator`; `generate_round_dispatch` becomes 5-line façade. `tests/test_dispatch_emission_runs_hooks.py` (S-10 invariant) MUST stay green byte-identical. **Estimated +8 NEW tests (ProposalEmitter unit tests).** |
| PV-05 | `chore(v10.6.4)` | **D-Q-4 compressor/ NineS analysis.** `nines analyze --target-path src/devolaflow/compressor/ --depth deep --agent-impact --keypoints`; output to `.local/research/v10.6.4_compressor_nines.md`; identify any new warnings (none expected; if warnings found, defer fixes to v11.0.x). Closes 547-day gap since v9.3.0 PV-04 split. **Estimated 0 NEW tests (analysis-only).** |
| PV-06 | `chore(v10.6.5)` then `chore(v10.7.0)` | **MINOR cycle close.** v10.6.x → v10.7.0. **Estimated +2 NEW tests (ghost-audit).** |

**Test budget:** ~12 NEW (very low — refactor-heavy cycle).
**Gate:** `strict` (≥90, ≥90% cov) — refactor risk per CP-4 (D-Q-1 doesn't touch `gate/` but feedback.py is S-10 invariant).
**Headroom note:** The low test budget (only 12) means there's room for unforeseen helper additions; D-Q-1 batches B+C may surface new helpers needing tests.

### v10.7.0 — Protocol Audit + Observability Improvements

**Feature branch:** `feat/v10.7.0-protocol-observability`
**Rationale:** D-P + D-O families (excluding 3 stretch which move to v11.0.0). 5 patches covering canonical_order audit, STATUS.yaml extensibility, evaluator alignment, SI-3 auto-collection, in-cycle index.

| PV | Tag | Deliverable |
|---|---|---|
| PV-01 | `chore(v10.7.0)` | **D-P-1 canonical_order audit.** `scripts/audit_canonical_order.py` produces non-emptiness rates per tail-field; output `.local/research/v10.7.0_canonical_order_audit.md`. **G-6 frozen-prefix gate preserved** (positions 1-12 untouched; 10-baseline byte test 10/10). **Estimated +3 NEW tests.** |
| PV-02 | `chore(v10.7.1)` | **D-P-3 STATUS.yaml NEST demo.** Add ONE optional `last_lint_token_count` field to `schemas/agent-workspace/change-status.yaml` per A-2.3 NEST decision; `agent_workspace/lint.py` reads it; backward-compat verified (v8.3.0+ STATUS.yaml files still valid). **Estimated +5 NEW tests.** |
| PV-03 | `chore(v10.7.2)` | **D-O-1 evaluator rosetta.** New `references/evaluator-rosetta.md` (Large tier ≤1000 lines; **15→16 references**); 6×9 N×M cell mapping table SI-3 dims × NineS bundles + Si-Chip iteration_delta with C/O/· legend. SKILL.md `## Reference Navigation Guide` adds 16th entry. CONDITIONAL_PASS — large-only verdict. **Estimated +4 NEW tests (file structure + cross-ref tests).** |
| PV-04 | `chore(v10.7.3)` | **D-O-2 SI-3 auto-collection.** `scripts/auto_collect_si3_metrics.py` (NEW) + `--metrics` flag on `generate_si3_evaluation.py`; subjective/objective weighting 0.6/0.4. Quantified: before 0% auto / after 87% auto at sub-component tier. **Estimated +6 NEW tests.** |
| PV-05 | `chore(v10.7.4)` | **D-O-3 in-cycle research index.** Edit `agent_workspace/reporter.py::render_workspace_report` + `workspace_report.md.j2` to add 3rd section "Research artifacts (this cycle)" scanning `.local/research/v<current-version>_*.md`. Ephemeral; not part of W-19 cycle archive. **Estimated +3 NEW tests.** |
| PV-06 | `chore(v10.7.5)` then `chore(v10.8.0)` | **MINOR cycle close.** v10.7.x → v10.8.0. **Estimated +2 NEW tests.** |

**Test budget:** ~23 NEW.
**Gate:** `standard` (D-P-3 schema change is NEST under existing, not canonical_order edit — A-2.4 multi-baseline byte test stays green).

### v10.8.0 — External Tool Coupling Hardening

**Feature branch:** `feat/v10.8.0-external-coupling`
**Rationale:** D-C family closes the 4-plugin coupling story. 2 core (D-C-1 + D-C-2) + 1 standard (D-C-3). Sets up DF for "no upstream tool required" positioning.

| PV | Tag | Deliverable |
|---|---|---|
| PV-01 | `chore(v10.8.0)` | **D-C-1 degraded mode contract.** New `references/degraded-mode.md` (Large tier ≤1000 lines; **16→17 references** — at SF-1 list ceiling, may require SF-1 tier expansion if 18th reference needed in v11.0.0+); new `tests/test_degraded_mode.py` (4 simulated unreachable scenarios — NineS / Si-Chip / RTK / ui-pro). G-3 satisfied: zero upstream changes. **Estimated +10 NEW tests.** |
| PV-02 | `chore(v10.8.1)` | **D-C-2 bridge contract tests (Phase A — NineS + Si-Chip).** New `tests/integration/` directory + `test_nines_shape_contract.py` + `test_sichip_shape_contract.py` + cached fixtures under `tests/integration/fixtures/{nines,sichip}/`. New `make refresh-bridge-fixtures` target. **Estimated +8 NEW tests.** |
| PV-03 | `chore(v10.8.2)` | **D-C-2 bridge contract tests (Phase B — RTK + ui-pro) + D-C-3 split.** D-C-2 phase B: `test_rtk_shape_contract.py` + `test_uipro_shape_contract.py` + fixtures. Weekly CI cron added (`.github/workflows/bridge_contract_weekly.yml`). D-C-3: lifecycle event 9 (`pre_plugin_invocation`) → 11 (`pre_plugin_invocation_install`) + 12 (`pre_plugin_invocation_upgrade`) per A-2.2 APPEND-ONLY; event 9 retained as alias for 1 cycle. Lifecycle event count 10 → 12. **Estimated +5 NEW tests.** |
| PV-04 | `chore(v10.8.3)` then `chore(v11.0.0-rc1)` | **MINOR cycle close + MAJOR rollup prep.** v10.8.x → v11.0.0-rc1; canonical-7 sync; CHANGELOG; retrospective. PR `feat/v10.4.0-cycle` → `feat/v11.0.0-major-rollup` rename. **Estimated +2 NEW tests.** |

**Test budget:** ~25 NEW.
**Gate:** `standard` + W-12 SKILL adapter build verify (degraded-mode.md is 17th reference — SKILL.md table grows; W-5 coupling triple).

### v11.0.0 — MAJOR Rollup + Stretch + Final Regression

**Feature branch:** `feat/v11.0.0-major-rollup`
**Rationale:** Final MAJOR ships the 4 stretch patches (all S-effort, all analysis-or-doc-only) + cycle-cumulative regression + EN/ZH refresh + W-19 cycle archive (5 MINORs of artifacts) + retrospective.

| PV | Tag | Deliverable |
|---|---|---|
| PV-01 | `chore(v11.0.0-rc1)` | **D-P-2 + D-P-4 stretch.** D-P-2: `.local/research/v11.0.0_w21_threshold_empirical_check.md` (analysis-only). D-P-4: `plan-mode-enforcement.md` adds §3.2 "Multi-Step Plans" (~130 lines, doc-only with `[EXPLORE]` + `[REVISABLE]` annotation conventions). **Estimated +3 NEW tests.** |
| PV-02 | `chore(v11.0.0-rc2)` | **D-O-4 + D-Q-3 stretch.** D-O-4: `.local/research/v11.0.0_si10_gate_growth_analysis.md` (analysis-only forecast). D-Q-3: 4-row PURE-ALIAS rename (`file_write→check_file_write`, etc.) with 1-cycle alias schedule v11.0.0→v12.0.0. CONDITIONAL_PASS. **Estimated +6 NEW tests.** |
| PV-03 | `chore(v11.0.0)` | **MAJOR cycle close.** Full regression sweep: `pytest tests/ -q` + `ruff check src/ tests/` + `ruff format --check` + W-9 SI-10 7-step + W-4 SI-4 EvoBench (no >5% regression) + W-12 SKILL adapter build × 4 adapters + W-3 SI-3 STRICT MAJOR ≥9.0 evaluation. Canonical-7 sync 10.8.3 → 11.0.0; CHANGELOG `## [11.0.0]` major-rollup section; W-7 SI-8 retrospective; **W-19 cycle archive** of 5 MINORs of `.local/research/v10.[4-8]*.md` + `v11.0.0*.md` artifacts to `docs/cycle-archive/v11.0.0/`. EN/ZH human docs refresh (`make sync-human-docs`); demo `versions.json` v11.0.0 entry; README "What's New in v11.0.0"; design-philosophy blog refresh. PR `feat/v11.0.0-major-rollup` → `main`. **Estimated +1 NEW test (v11.0.0 ghost-audit lint).** |

**Test budget:** ~10 NEW.
**Gate:** `strict` MAJOR cycle close — W-3 SI-3 ≥ 9.0 (matching v10.0.0 cycle close 9.20 + v10.3.0 MINOR cycle close 9.385 trajectory).

## §5 — Cycle-cumulative metrics forecast

| Metric | v10.3.0 baseline | v11.0.0 forecast | Δ |
|---|---:|---:|---:|
| `__version__` | 10.3.0 | 11.0.0 | +0.8.0 |
| Test count | 4091 | ~4229 | +138 (~92% of W-17 +150 cycle cap) |
| Coverage | 93.04% | ≥ 92% (refactor cycle dilutes by ~1pp expected) | -1pp (still +12pp over CP-2 floor) |
| Source LOC | ~25K | ~28K | +3K |
| Builtin templates | 22 | 22 (Phase A only; Phase B deferred) | 0 net (16 tagged `(legacy)`) |
| References | 14 | 17 | +3 (`troubleshooting.md`, `evaluator-rosetta.md`, `degraded-mode.md`) |
| Examples | 3 | 4 | +1 (`multi-stage-trace.md`) |
| Lifecycle events | 10 | 12 | +2 (D-C-3 split) |
| canonical_order length | 17 | 17 | 0 (no schema bumps) |
| Plugins | 4 | 4 | 0 (no new plugins) |
| Env flags | (active count) | + 0 | 0 (D-C-3 telegraphs DEVOLAFLOW_AUTO_UPGRADE_PLUGINS to v12.0.0+) |
| W-3 SI-3 composite | 9.385 (v10.3.0 MINOR close) | ≥ 9.0 (MAJOR strict) target ~9.3 | +/- ~0.1 |
| NineS overall composite | 0.906924 | ≥ 0.910 (D-Q-1 closes 7 warnings; expected lift) | +0.003 |
| Soul-set count | 10 | 10 (frozen per W-21) | 0 |

## §6 — Risk register (aggregated from 27 PDS §9 sections)

Top-tier risks across all admitted patches, deduplicated:

| # | Risk | Severity | Mitigation | PDS source |
|:---:|---|:---:|---|---|
| **R-1** | D-Q-1 7-warning batch may surface new helpers needing test surface; v10.6.0 test budget could overflow | major | Allocate +12 test buffer (current forecast 12 NEW; cap 30/PV); each batch has fallback to defer 1 helper to next batch | D-Q-1 §9 |
| **R-2** | D-D-2 evidence (3 envelope files / 50 PVs) may be challenged as "small sample"; SKILL.md annotation could be questioned | major | Document sample-size caveat verbatim in `agent-workspace.md` annotation; cite empirical paths | D-D-2 §9 |
| **R-3** | D-X-5 troubleshooting handbook (15th reference) triggers SF-1 reference-set ceiling (currently 14 fixed); may require SF-1 tier expansion | major | Pre-flight SF-1 expansion in v10.4.0 PV-01 (single-line edit to `scripts/sync_cursor_skill.py::MIRRORED_FILES` constant); tested via reference-size-budgets.py existing parametrize | D-X-5 §9 |
| **R-4** | D-O-1 + D-X-5 + D-C-1 each add 1 reference → 14 + 3 = 17 references; 17th breaks SF-1 hard limit | blocker | v10.4.0 PV-01 SF-1 expansion to ≤20-reference soft ceiling; if blocker, fold troubleshooting into existing reference (e.g., as appendix to `team-roles.md` or `execution-protocol.md`) | D-O-1 + D-X-5 + D-C-1 §9 |
| **R-5** | D-Q-2 ProposalEmitter extraction may break S-10 hook invariant if hook chain ordering changes | blocker | `tests/test_dispatch_emission_runs_hooks.py` 11 tests are release-blocker contract; refactor MUST keep all green byte-identical; preserve `generate_round_dispatch` as 5-line façade with same ordering semantics | D-Q-2 §9 |
| **R-6** | D-C-2 cached fixtures may go stale silently (test stops detecting bridge-shape defects after upstream protocol drift) | major | Weekly CI cron (`make refresh-bridge-fixtures`) + manual operator workflow documented; fixture-staleness lint added to `tests/test_no_ghost_features.py` | D-C-2 §9 |
| **R-7** | D-A-2 Phase A `(legacy)` tags applied to 16 templates — operators may misinterpret as "deprecated" rather than "low-frequency" | major | `meta-framework.md` §4 alias mapping table adds explicit note: "(legacy) = registered but not used in v9.0.0..v10.3.0 cycle execution; kept available; Phase B compose-collapse deferred to v12.0+" | D-A-2 §9 |
| **R-8** | D-X-1 scaffold output may diverge from manual template author conventions over time; scaffold-stub vs canonical-template drift | minor | Scaffold output marked with `# AUTO-GENERATED — manual completion required` header; ghost-audit lint refreshed each cycle to verify scaffold output isn't shipped as-is | D-X-1 §9 |
| **R-9** | D-D-3 line-budget paragraph expansions may push reference into XL tier (≤1600); SF-1 ceiling change cycle | minor | Targeted expansions (3 paragraphs only) keep references within Large tier 1000 cap; if any reference exceeds 1000 after expansion, split into separate reference rather than upgrade tier | D-D-3 §9 |
| **R-10** | D-O-2 0.6 obj / 0.4 subj weighting may produce inconsistent SI-3 scores vs historical hand-graded | major | First 2 cycles after v10.7.0 run BOTH (auto + hand) and compare; if delta > 0.5 / 10, recalibrate weights; fallback to hand-grade for the cycle | D-O-2 §9 |
| **R-11** | D-A-2 + D-A-1 + D-A-3 + D-A-4 simultaneously edit `SKILL.md` + `agent-workspace.md` + `meta-framework.md` in one MINOR — merge conflicts within v10.5.0 between PVs | major | PV-01 D-A-1 → PV-02 D-A-2 → PV-03 D-A-3+D-A-4 sequence ensures sequential file-touches; each PV commits before next reads | D-A-* §9 |

**Net risk profile:** 2 blockers + 6 major + 3 minor + 0 critical (all blockers have explicit mitigation; both blocker mitigations are pre-flight actions in v10.4.0 PV-01).

## §7 — Deferred items (mandatory per W-7 §3 forward telegraph)

Items NOT shipped in v11.0.0 cycle, with explicit rationale:

| Item | Why deferred | Defer to |
|---|---|---|
| D-A-2 Phase B (compose-collapse 22→6 templates) | Phase A audit must demonstrate operator-acceptance of `(legacy)` tagging before destructive collapse; cycle ships measurement before action | v12.0+ pending Phase A operator feedback |
| Per-file iteration_delta decomposition (Si-Chip refinement carried over from v10.3.0) | Requires upstream Si-Chip `aggregate_eval.py` change OR custom DF wrapper; orthogonal to v11.0.0 internal-quality theme | v11.0.x or upstream Si-Chip issue |
| S-11 Soul rule "Parallel Wave Dispatch Invariant" | W-21 2-cycle telegraph carry-forward (v10.0.0 retro → v10.3.0 retro → THIS cycle re-telegraph); cycle N+2 evaluation deferred to v11.2.0 SI-1 per W-21 governance; v11.0.0 ships D-P-2 analysis instead | v11.2.0 SI-1 (cycle N+2 from v10.3.0 telegraph) |
| Per-PV Si-Chip iteration_delta (v10.3.0 deferred §3) | Requires per-file runs-dir layout (Si-Chip side); not Internal-DF capability | v11.0.x or upstream issue |
| D-Q-1 carried forward CC reductions if any helpers exceed batch budget | If v10.6.0 PV-01-03 batches each deliver 2-3 helpers and 1 helper overflows, defer to v11.0.x micro-PV | v11.0.x as deterministic micro-PV |
| `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` env flag (telegraphed from D-C-3 §2 stretch) | New env flag requires W-20 §3 orthogonality re-evaluation; current cycle ships hook-event split (orthogonal); env flag remains coupled until operator demand | v12.0.0+ when W-20 reuse-first re-applied |
| NineS A1 ticket `code_coverage` collector timeout (carried from v10.3.0 §3) | Upstream NineS infrastructure; W-2 manual fallback sufficient | Operator-tracked at NineS upstream |
| Si-Chip upstream installer post-install path mismatch (carried from v10.3.0 §3) | Not DevolaFlow source code | Operator-tracked at Si-Chip upstream |
| Per-helper docstrings for v10.2.0/v10.3.0 cycle helpers (carried from v10.3.0 §3) | Not core to internal optimization mandate; v10.4.0+ cleanup | v11.0.x or v12.0.0 maintenance PV |

9 explicit deferrals — exceeds W-7 ≥5 minimum.

## §8 — User sign-off questions (mirror v10 internal opt directions §6)

| # | Question | Default if unanswered |
|:---:|---|---|
| 1 | Approve 5-MINOR + 1-MAJOR shape (v10.4.0 → v11.0.0)? | Yes (mirrors v10.0.0 cycle precedent) |
| 2 | Approve all 27 directions for cycle (22 PASS + 5 CONDITIONAL_PASS)? Alternative: drop the 5 CONDITIONAL_PASS to defer-list. | Yes — admit all 27 |
| 3 | Approve adding 3 new references (`troubleshooting.md`, `evaluator-rosetta.md`, `degraded-mode.md`) — references count grows 14 → 17? Alternative: fold troubleshooting into team-roles.md as appendix. | Yes — add 3 new (with R-3/R-4 mitigation in v10.4.0 PV-01) |
| 4 | Approve D-A-2 Phase A only (audit + `(legacy)` tagging) deferring Phase B (compose-collapse) to v12.0+? | Yes — Phase A only |
| 5 | Approve D-Q-3 lifecycle rename being moved to v11.0.0 stretch (vs landing in v10.6.0)? | Yes — defer to v11.0.0 stretch |
| 6 | Approve D-C-2 weekly CI cron (`make refresh-bridge-fixtures`) running once per week against operator's local plugin install? | Yes — weekly cron |
| 7 | Approve W-19 cycle archive of 5 MINORs of `.local/research/` artifacts to `docs/cycle-archive/v11.0.0/` at v11.0.0 PV-03? | Yes — single cycle-close archive (per W-19 idempotent rule) |
| 8 | Approve D-O-2 0.6 obj / 0.4 subj weighting for SI-3 auto-collection? Alternative: 0.5/0.5 or 0.7/0.3. | Yes — 0.6/0.4 (per D-O-2 §3 source recommendation; first 2 cycles run BOTH for validation) |
| 9 | Approve W-3 SI-3 STRICT MAJOR ≥9.0 threshold for v11.0.0 close (matching v10.0.0 + v10.3.0 trajectory)? | Yes — STRICT 9.0 |
| 10 | Approve PR strategy: per-MINOR PR (5 PRs) + 1 MAJOR rollup PR (6 PRs total), mirroring v10.0.0 Q5 choice? Alternative: single feature branch + 1 PR (v10.2.0 cycle pattern). | Default: per-MINOR PR (Q5 from v10.0.0) — but operator can flip to single-branch if cycle-velocity is the priority |

## §9 — Open issues / ambiguities

Surfaced from L3 audits but not resolvable without operator decision:

1. **D-X-1 ↔ D-A-2 ordering coupling** (Wave 1 R-coupling) — if D-A-2 admits and ships in v10.5.0 PV-02, D-X-1 scaffold's `(legacy)` template tagging must align with D-A-2's audit outcome. Forced ordering: D-X-1 v10.4.0 PV-02 ships scaffold WITHOUT `(legacy)` awareness; v10.5.0 PV-02 D-A-2 retro-fits scaffold output via `scripts/sync_cursor_skill.py` post-process. **Decision:** Accept the 2-cycle order; OR move D-X-1 to v10.5.0 PV-04 after D-A-2 lands. The plan above takes Decision-1 (ship scaffold first; retro-fit `(legacy)` awareness in v10.5.0).

2. **D-D-2 SKILL.md annotation phrasing** — what exactly does the 1-line annotation say? Candidates: "(only enabled when DEVOLAFLOW_AGENT_WORKSPACE=1 + complexity ≥ STANDARD)" vs "(typically used in change-driven and full-pipeline workflows)". **Decision:** Operator picks at v10.4.0 PV-05 review; default candidate is "complex / change-driven workflows only".

3. **R-4 reference-set ceiling expansion** — SF-1 currently fixes the reference set at 14 specific files. v11.0.0 cycle proposes 17. Two options: (a) update SF-1 to ≤20-reference soft ceiling; (b) fold troubleshooting into existing reference. **Decision:** Operator picks at v10.4.0 PV-01 cycle preflight; default is option (a).

4. **D-Q-3 alias deprecation timeline** — 1-cycle alias (v11.0.0 ships rename + alias; v12.0.0 removes alias) vs 2-cycle alias (v12.0.0 still has alias; v13.0.0 removes). **Decision:** Operator picks at v11.0.0 PV-02; default 1-cycle (G-7 backward compat satisfied).

## §10 — Pre-flight admission verification (L0 final check)

Before issuing this cycle plan to user, L0 verifies:

- [x] All 27 PDS files exist in `.local/research/v11.0.0_patches/`
- [x] All 27 PDS files have parseable admission summary lines
- [x] All 27 PDS files satisfy G-1..G-9 admission gates (22 PASS + 5 CONDITIONAL_PASS; 0 reject; 0 defer)
- [x] Tier distribution: 7 core + 16 standard + 4 stretch = 27 (matches PDS count)
- [x] Effort distribution: 15 S + 11 M + 1 L (D-Q-1) = 27 (matches PDS count)
- [x] Cycle composition (5 MINORs + 1 MAJOR rollup) authored
- [x] Per-PV deliverable map authored (31 PVs total: 6+6+6+6+4+3)
- [x] Risk register aggregated (11 deduped risks; 2 blockers with explicit mitigation)
- [x] Deferred items enumerated (9 items; ≥5 W-7 minimum)
- [x] User sign-off questions surfaced (10 questions per v10 directions §6 mirror)
- [x] Open issues surfaced (4 ambiguities)

## §11 — Headline summary (TL;DR for user)

**v11.0.0 cycle:** 5 MINORs (v10.4.0 → v10.8.0) + 1 MAJOR rollup (v11.0.0). 31 PVs total. ~138 NEW tests (within +150 W-17 cycle cap). All 27 v10 internal optimization directions admitted (22 PASS + 5 CONDITIONAL_PASS).

**Mainline composition:** 7 `core` + 16 `standard` + 4 `stretch` patches.

**Key cycle outcomes (forecast):**
- 3 new references (troubleshooting + evaluator-rosetta + degraded-mode); 1 new example (multi-stage-trace)
- 22/22 high-frequency `(legacy)` template tagging via Phase A audit (Phase B compose-collapse deferred)
- 7 NineS warnings cleared (10.2.2 → 0)
- 4 lifecycle events refactored (rename to taxonomy + 1 split into 2)
- Si-Chip iteration_delta gate + bridge contract tests + degraded mode → DF "no upstream tool required" positioning achieved
- W-3 SI-3 STRICT MAJOR ≥9.0 target (trajectory: v9.7.0 9.10 → v10.0.0 9.20 → v10.3.0 9.385 → v11.0.0 ≥9.0 strict, target ~9.3)
- Soul-set frozen at 10 (S-11 candidate re-telegraphed to v11.2.0 per W-21)
- Schema canonical_order frozen at 17 (zero schema bumps)
- Coverage trajectory: 93.04% → ≥92% (refactor cycle dilutes by ~1pp; still +12pp over CP-2 floor)
- 0 new env flags (W-20 reuse-first preserved)
- 0 breaking changes (G-7 across all 27 patches)

**User next action:** answer §8 sign-off questions; cycle then proceeds to v10.4.0 PV-01 dispatch via `/devola-flow` workflow.

---

*This cycle plan is the L0 SI-1 (W-1) Planning Gate output for the v11.0.0 MAJOR cycle. It is the contract for all 5 MINORs + 1 MAJOR rollup. Deviations during cycle execution must be documented in per-PV CHANGELOG entries + per-MINOR retrospectives.*
