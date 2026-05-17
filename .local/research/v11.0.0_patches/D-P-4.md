# D-P-4 — Patch Design Specification

> **Direction**: plan-mode protocol "multi-step reasoning" eval
> **Source**: `.local/research/v10_internal_optimization_directions.md` §3.2 D-P-4 (lines 138-145)
> **Author**: L3 Task Agent, Wave 4a (D-P Protocol Evolution)
> **Date**: 2026-05-04
> **Cycle**: v11.0.0 SI-1 planning
> **Constraints**: DOCUMENTATION-ONLY refinement of plan-mode template per source doc — "本方向限于文档化" (line 145). Zero schema field additions. G-5 (Soul-freeze) + G-6 (cache-prefix) gates respected: no `schemas/lean-dispatch.yaml` changes; no Soul rule additions.

---

## §1 — Current State

`workflow-system/agent/references/plan-mode-enforcement.md` v8.4.1 (3200-token estimate, line 12) §3 "Plan Output Template" (lines 101-154) defines the canonical plan template as a SINGLE-PASS structure:

```text
# [Plan Title]
## Overview
## Execution Model
## Stages (gate-before-advance ...)
### S01: ...
#### W01 (parallel | <=5 tasks ...)
| ID | Layer | Type | Task | ...
## Constraints Checklist
## Invariants
```

The template implicitly assumes the plan describes ONE horizon: a single goal with stage-by-stage execution. There is NO native template slot for:

* **Multi-step reasoning that branches across horizons** (e.g., "Phase A: research; Phase B: depending on research outcome, EITHER design path X OR design path Y").
* **Plan-internal uncertainty annotation** (which stages are "exploratory probes" vs which are "confident steps", informing how `convergence` stage `max_rounds` should be sized).
* **Plan-revision markers** (which stages are pre-committed vs which are explicitly subject to mid-cycle revision based on stage-N feedback).

The H-4 candidate from the original EvoBench feedback proposed a NEW `multi_horizon_planner` ROLE to handle this — but the user explicitly rejected the role-based path (per `.local/research/v10_internal_optimization_directions.md` §2 line 44 "重定向"). The source doc converts the question to "is the existing `plan-mode-enforcement.md` §3 template ALREADY expressive enough for multi-step plans, or is a thin documentation refinement needed?"

The convergence-loop machinery already supports multi-step at the wave level: `gate_type: convergence` stages have `max_rounds` + `on_stagnation` (lines 162-164) AND the round-aware escalation table (lines 416-428) already handles round-N>1 model upgrades. What is MISSING is the documentation guidance for L0 plan authors on HOW to express a plan that has multiple horizons — i.e., when a `convergence` stage decides between branches at round-2 transition, the `Stages` template doesn't currently document how to lay that out clearly.

## §2 — Patch Design

**Algorithm** (documentation-only):

1. Add a NEW sub-section §3.2 to `workflow-system/agent/references/plan-mode-enforcement.md` titled "Multi-Step Plans (Multi-Horizon Reasoning)". Position: immediately AFTER the existing §3.1 "Field semantics (per-row contract)" (line 156), BEFORE §4 "Constraints Checklist (verbatim — must verify before finalizing plan)" (line 170).
2. The new §3.2 sub-section is approximately 100-130 lines and contains:
   * §3.2.1 **When multi-step plans apply**: 4-bullet trigger list (research-then-design tasks; benchmark-driven branch decisions; spec-first-then-impl-or-defer; revise-after-stage-N-feedback patterns).
   * §3.2.2 **Template extension** (NOT a schema change; uses existing fields): how to express multi-horizon plans within the EXISTING stages × waves × tasks template:
     * Use the `gate_type: convergence` stage with `max_rounds: 2` + `on_stagnation: escalate` for "exploratory probe" stages whose outcome decides the next stage's shape.
     * Use the `context_profile` field to flip between profiles per phase (e.g., `research` profile in Phase A → `convergence_heavy` in Phase B).
     * Use the `deliverables` field to document the FORK semantics: `deliverables: [research-report.md] (consumed by S02 — branch decision input)`.
   * §3.2.3 **Plan-internal uncertainty annotation**: introduce an OPTIONAL convention (NOT a schema change) of annotating exploratory stages with `[EXPLORE]` prefix in the stage title (e.g., `### S01: research — [EXPLORE] feasibility study`). The annotation is plain text in the existing `name` field; no new schema fields.
   * §3.2.4 **Plan-revision markers**: introduce an OPTIONAL convention of annotating `convergence` stages whose round-2 outcome may revise downstream stages with `[REVISABLE: <downstream-stage-id>]` annotation in the stage description. Again, plain text in existing fields; no schema change.
   * §3.2.5 **Worked example**: a 2-stage plan demonstrating the conventions (e.g., `S01 [EXPLORE] research` → `S02 [REVISABLE: S03] design with 2 candidate paths` → `S03 implement chosen path`).
   * §3.2.6 **Cross-references**: cite §3 (Plan Output Template) for the base template; cite §6 (Reinforcement Rules) for round-N>1 mechanics; cite §7 (Convergence Loop Mechanics) for `max_rounds` semantics.
3. The new sub-section is loaded under the SAME tier-2 trigger as the rest of `plan-mode-enforcement.md` — no new SKILL.md changes needed for activation. SKILL.md §"Mode Awareness" (line 69) already cites this reference.
4. Update `last_updated` frontmatter (line 13) from `"2026-04-23"` to v11.0.0 release date. Bump `version` (line 3) from `"8.4.1"` to `"11.0.0"`.
5. ZERO changes to `workflow-system/agent/SKILL.md` (the §"Mode Awareness" block at lines 69-79 already cites the reference; no update needed because the cross-link is unchanged).

**Files touched**:

* `workflow-system/agent/references/plan-mode-enforcement.md` — +100-130 LOC for §3.2 sub-section + 2-line frontmatter version bump.
* **NONE** in `workflow-system/agent/SKILL.md` (cross-link already in place).
* **NONE** in `schemas/` (no schema changes; G-5 + G-6 PASS).
* **NONE** in `src/devolaflow/` (no source code change; `task_adaptive_selector._PLAN_MODE_OVERRIDES` at lines 64-76 of plan-mode-enforcement.md is unchanged because the new sub-section uses EXISTING fields).
* **NONE** in `tests/` (documentation-only; no new test functions BUT W-18 ghost-audit refresh required per W-18 precondition — see §9).

**API surface**: zero. Pure documentation deliverable.

**No schema field additions**: the new sub-section §3.2 introduces ONLY documentation conventions (`[EXPLORE]` and `[REVISABLE: <id>]` text annotations) that live within EXISTING `stage.name` / `stage.description` text fields. The `lean-dispatch.yaml#layout_invariant.canonical_order` is NOT touched. Multi-baseline byte test (10/10) stays green by construction.

**Skill-format coupling check** (W-5 / SI-5):

* Line count: `plan-mode-enforcement.md` is currently ~648 lines (rough); after +130 LOC ~778 lines — well under the 1000-line Large tier ceiling per C-4 / SF-1.
* Adapter build: `build-skill` for all 4 adapters (Cursor / Codex / Claude / Copilot) MUST succeed (W-12 trigger).
* Benchmark run: `python -m pytest tests/test_benchmarks.py -v` MUST pass (W-4 trigger because reference doc is part of context profile).
* Version consistency: `python -m pytest tests/test_version.py -v` — frontmatter `version: "11.0.0"` matches `__version__` at v11.0.0 release.

These 4 W-5 coupled triggers are accounted for in §7 effort estimate.

## §3 — Small Project Evaluation

**Synthetic test bed**: `synthetic_small_repo` (per `v11.0.0_evaluation_methodology.md` §2). Small projects RARELY need multi-step plans — most are single-horizon (init / single feature / single bugfix). The new §3.2 documentation is OPT-IN guidance for L0 plan authors who detect a multi-horizon scenario.

**Operations exercised**: `init` (single-horizon plan — applies §3 base template, NOT §3.2). `feature` with explicit research-then-design ask from operator (could trigger §3.2 application).

**Metric collection** (per §4.1 operator-experience metrics):

* `Plan template line count` (base template + optional §3.2 application).
* `Plan readability score` (qualitative — measured by §3.2 worked example clarity).

**Expected delta (before → after)**:

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| `plan-mode-enforcement.md` total line count | ~648 | ~778 | +130 (under C-4 1000 ceiling) | improve (template guidance) |
| Number of documented multi-horizon conventions | 0 | 2 (`[EXPLORE]` + `[REVISABLE: <id>]`) | +2 | improve (template expressiveness) |
| Worked examples in plan-mode-enforcement.md | 1 (single-horizon) | 2 (single-horizon + multi-horizon) | +1 | improve (documentation) |
| Plan template field count (top-level slots) | unchanged | unchanged | 0 | preserve (no schema change) |

**Pass criterion**: §3.2 sub-section authored, worked example renders correctly, line count under C-4 ceiling.

**If no improvement on small project**: small projects rarely encounter multi-horizon scenarios — this is INHERENTLY a documentation refinement that benefits more complex plans (Standard / Complex per A-6.1). Small-tier passes by virtue of the guidance EXISTING for the rare case it applies.

## §4 — Large Project Evaluation

**Test bed**: DevolaFlow self at v10.3.0 baseline. v10.3.0 cycle history shows multiple multi-horizon plans (e.g., the v10.2.0 cycle plan had a research-then-integrate-then-iterate shape; the v11.0.0 SI-1 planning IS itself a 5-wave multi-horizon plan).

**Metric collection** (per §4.1 + §4.4 buckets):

* `plan-mode-enforcement.md` line count (against C-4 Large tier 1000 ceiling).
* `Reference cross-link integrity` (existing §3 / §6 / §7 cross-references preserved; new §3.2 cross-references valid).
* `Adapter build success rate` (Cursor / Codex / Claude / Copilot — all 4 MUST succeed per W-12).
* `Benchmark composite score delta` (W-4 regression guard).

**Expected delta (v10.3.0 baseline → post-patch)**:

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| `plan-mode-enforcement.md` line count | ~648 | ~778 | +130 | improve (within C-4 1000 ceiling) |
| Reference SF-4 cross-link list | 14 entries (incl. `plan-mode-enforcement.md`) | 14 entries (no list change) | 0 | preserve (G-9 doc-completeness) |
| Adapter build success (Cursor / Codex / Claude / Copilot) | 4/4 | 4/4 | 0 | preserve (W-12) |
| EvoBench benchmark composite (W-4 regression guard) | baseline | -- | within +/- 5% (W-4 threshold) | preserve |
| `tests/test_layout_invariant_multi_baseline.py` PASS | 10/10 | 10/10 | 0 | preserve (G-6 — unrelated) |
| `tests/test_no_ghost_features.py::test_skill_reference_links_match_sf4_set` | PASS | PASS | 0 | preserve (no SF-4 list change) |

**Pass criterion**: §3.2 sub-section authored AND all 4 adapters build green AND benchmark composite within W-4 ±5% threshold AND all SF-4 ghost-audit tests stay PASS.

**Side-effect check** (MUST NOT regress):

* `workflow-system/agent/SKILL.md` — bytes-identical (no SKILL.md change; cross-link is the existing one).
* `tests/test_layout_invariant_multi_baseline.py` — 10/10 PASS (unrelated; this is documentation-only).
* `tests/test_reference_size_budgets.py::test_reference_within_large_tier` — `plan-mode-enforcement.md` stays under 1000 lines (Large tier ceiling per SF-1).
* `python -m pytest tests/test_version.py -v` — frontmatter version bumped 8.4.1 → 11.0.0 in same PR as canonical-7 sync.
* `tests/test_no_ghost_features.py` — W-18 ghost-audit refresh MUST add a coverage check for the new §3.2 sub-section before any CHANGELOG entry mentions it.

## §5 — Benefit Metrics (≥ 3 quantitative; DF-internal)

| # | Metric | Before (v10.3.0) | After (v11.0.x doc PV) | Δ | Bucket |
|:---:|---|---:|---:|---:|---|
| 1 | Multi-horizon plan template documentation conventions | 0 (single-horizon implicit assumption) | 2 (`[EXPLORE]` + `[REVISABLE: <id>]`) | +2 | §4.1 operator experience |
| 2 | Worked examples in `plan-mode-enforcement.md` | 1 (single-horizon) | 2 (+1 multi-horizon) | +1 | §4.4 documentation |
| 3 | `plan-mode-enforcement.md` total line count vs C-4 Large tier ceiling | ~648 / 1000 (64.8% utilisation) | ~778 / 1000 (77.8% utilisation) | +130 LOC; +13% utilisation | §4.4 documentation |
| 4 | Schema field additions | 0 | 0 (uses existing `stage.name` / `stage.description` text fields) | 0 (preserved) | §4.2 architecture |
| 5 | Multi-baseline byte test PASS (G-6 guard, unrelated surface) | 10 / 10 | 10 / 10 | 0 (preserved) | §4.6 coupling |

NONE of these metrics rely on EvoBench `q` / `pass_rate` / `gap_score` (G-1 PASS).

## §6 — Admission Verdict

**PASS** for the documentation refinement.

The patch documents existing template expressiveness (the `convergence` + `context_profile` + `deliverables` fields ALREADY support multi-horizon plans; what was missing was operator-facing guidance) without introducing new schema fields, new Soul rules, or new env flags. The §3.2 sub-section provides 2 OPT-IN annotation conventions (`[EXPLORE]` + `[REVISABLE: <id>]`) that ride within EXISTING text fields and degrade gracefully (older plan parsers see them as plain text in stage names/descriptions and ignore them).

This patch satisfies the source doc constraint (line 145: "本方向限于文档化") and respects the user's H-4 rejection of the role-based path. The H-4 reframing — "现有 plan-mode 是否足以承载多步思考" (line 140) — is answered: YES, the existing template can carry multi-step reasoning when operators have the documentation guidance to express it cleanly.

## §7 — Effort Estimate

**S** (≤ 0.5 PV) — confirms the source doc estimate (line 143). Breakdown:

* Author §3.2 sub-section (5 sub-subsections + worked example): ~2.5 hours.
* Frontmatter version bump (8.4.1 → 11.0.0) + `last_updated` refresh: ~5 min.
* W-5 / SI-5 coupled triggers (W-12 adapter build verify, W-4 benchmark run, version-consistency test): ~30 min total because all 4 are scripted.
* W-18 ghost-audit refresh — add `test_v11_x_x_plan_mode_multi_horizon_section_present` lint asserting §3.2 heading appears verbatim in `plan-mode-enforcement.md`: ~30 min.

W-17 test budget consumption: +1 NEW test function (W-18 ghost-audit lint). Well under +30 per-PV cap.

## §8 — Dependencies

**none** — standalone documentation refinement. Does NOT depend on D-P-1 (audit script), D-P-2 (W-21 analysis), or D-P-3 (STATUS.yaml extension). May be referenced by D-X-1 (workflow template scaffold CLI) if future cycles want the scaffold to emit multi-horizon plan stubs, but no inter-PDS dependency in v11.0.0.

## §9 — Risk Register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | Operators interpret `[EXPLORE]` / `[REVISABLE: <id>]` annotations as REQUIRED rather than OPT-IN, causing every plan to gain noise | minor | §3.2.3 + §3.2.4 sub-sections explicitly state "OPT-IN convention; absence is canonical and equally valid"; worked example §3.2.5 shows BOTH a plain stage and an annotated stage to model the choice |
| 2 | Adapter build (W-12) breaks on the 4 adapters because of unexpected escaping in the `[EXPLORE]` / `[REVISABLE: <id>]` markdown brackets | minor | All 4 adapters tested in CI per W-12 trigger; if one breaks, the bracket markers can be replaced with a different sigil (e.g., `EXPLORE:` prefix) without changing the §3.2 semantics |
| 3 | The §3.2 sub-section becomes stale if a future PV adds new convergence-loop or plan-mode features that affect multi-horizon expression | minor | §3.2.6 cross-references §6 (Reinforcement Rules) + §7 (Convergence Loop Mechanics); future PVs that touch §6 / §7 are expected to re-check §3.2 cross-references; W-18 ghost-audit lint pins the §3.2 heading text so accidental deletion fails CI |

ZERO blocker / major risks because the patch is documentation-only with no schema or runtime impact.

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: stretch
