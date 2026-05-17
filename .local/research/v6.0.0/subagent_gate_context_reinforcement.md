# Subagent Report: Gate, Context, Reinforcement Subsystems (v5.4.2 → v6.0.0)

**Agent ID:** 44f42c73-2c4d-4130-8f97-ca8ced47a293  
**Date:** 2026-04-16  
**Scope:** Gate mechanism, context selection, reinforcement, v5.1 roadmap status, H1-H7/M1-M11

## Executive Summary

DevolaFlow **v5.4.2** implements a rich **gate stack**: composite scoring (4- or 7-dimension), four numeric profiles, convergence stagnation escalation in `evaluate_gate`, and a typed `GateType` union including preflight/revision/escalation/abort plus dedicated evaluators for several. **Reinforcement** (`findings_to_reinforcement`, `merge_reinforcement_into_dispatch`) and the feedback bridge (`ProposalGenerator.generate_reinforcement`) are implemented and tested, but **`merge_reinforcement_into_dispatch` has NO production callers** — only tests and package exports — so round-to-round injection is **not wired into runtime orchestration**. Context selection remains **goal-hint substring matching** with 16 profiles; **`apply_round_escalation` exists but is NOT called from `select_context()`**, so P8 is only partially realized. The v5.1 roadmap P5–P8 and v5.1-final P1–P4 items are largely reflected in CHANGELOG 5.2.0–5.3.0, while P9–P11 remain open or partial. S01-T06 H1/H2/H4/H5/H6 are largely addressed in-repo; H3/H7 and most M-items still have meaningful gaps.

## 1. Gate Mechanism Status

### Scoring dimensions

- **Default composite (4-dim)**: `test_quality`, `code_review`, `architecture`, `benchmark` (`gate/scorer.py:33-38`)
- **Extended composite (7-dim)** when user-facing inputs present (`gate/scorer.py:40-48`, selection logic `:147-156`)
- **Acceptance Readiness Score (ARS)** — 5 sub-dimensions for `acceptance_readiness` gate (`gate/scorer.py:50-56`, `:159-168`)

### Gate profiles

Four profiles **strict/standard/relaxed/audit** with thresholds, coverage, blocker/critical limits, v5.4.0 user-facing thresholds (`gate/profiles.py:8-74`).

### Reinforcement flow

- `findings_to_reinforcement` filters by `severity_floor`, sorts, caps at `MAX_REINFORCEMENT_RULES = 5` (`reinforcement.py:15-23`, `:48-65`)
- `merge_reinforcement_into_dispatch` injects into `context.applicable_rules.reinforcement` (`reinforcement.py:113-125`)
- `ProposalGenerator.generate_reinforcement` bridges verdict findings (`feedback.py:368-410`)

### Cross-check vs decomposition-gate.md

- **Aligned:** composite formulas, severity weights, pass conditions, profile table, convergence escalation narrative
- **Drift:** Reference §5 "Gate Types" lists only **standard/convergence/passthrough** (line 233-239); code defines **`GateType`** including **preflight/revision/escalation/abort/acceptance_readiness** (`gate/models.py:13-22`)

### Two-stage gate (spec → code quality)

**NOT IMPLEMENTED** as a chained call inside `evaluate_gate`. `acceptance_readiness` is a separate gate path (`scorer.py:326-330`), not an automatic stage-1 → stage-2 pipeline. (Note: S01-T06 H1 is *rationalization tables*; the 2-stage gate pattern is M7.)

### Gate-type taxonomy (M1)

**PARTIAL** — types defined in models; handlers exist for preflight/abort/escalation; `standard`/`convergence` alias to `revision` via `GATE_TYPE_ALIASES` (`gate/models.py:24-27`).

## 2. Context-Selection Mechanism Status

### Algorithm

Goal-hint routing: exact profile key → exact hint match → longest substring overlap (`task_adaptive_selector.py:126-159`). **Not semantic/AST.**

### Profile count & budgets

- **16 task profiles** in `context_profiles.yaml` (hotfix through product_verification)
- Meta hard cap `budget_hard_cap_tokens: 8000` (line 15); per-profile `token_budget`

### Round-based escalation (v5.3.0 P8)

**Implemented as standalone function** `apply_round_escalation` (`task_adaptive_selector.py:373-412`) — but **NOT INTEGRATED** into `select_context()` (lines 280-350 have no call to it). Callers found: only tests (`test_feedback_reinforcement.py`) and CHANGELOG entry.

### Plan-mode detection (feedback_for_skill.md)

**NOT IMPLEMENTED** in selector. Config signal exists: `mode_detection` + `plan_mode_template` sections in `context_profiles.yaml:85-93`. Adapters mention Plan mode (e.g. `claude_adapter.py:85`) but selector has no branch.

### `unwanted_hints` (v3.2 Candidate 3)

**NOT IMPLEMENTED** in selector. EvoBench uses `unwanted_sections` in scenarios/evaluator (`evaluator.py:59-80`) — not profile-driven `unwanted_hints` in selector.

### select_context() complexity

- Lines 280-350 → ~71 lines
- Cyclomatic ~3 (manual count): 1 entry + 2 explicit `if` branches (learnings, advisor)

## 3. Reinforcement Mechanism Status

### Findings → rules

- Severity filter default `severity_floor = "major"`
- Sorted by `SEVERITY_ORDER`, capped `eligible[:MAX_REINFORCEMENT_RULES]`

### **CRITICAL: Integration not wired**

- **`merge_reinforcement_into_dispatch` callers:** `reinforcement.py` definition, `gate/__init__.py` export, **`tests/test_reinforcement.py` ONLY** — grep found NO production orchestration usage
- **`generate_reinforcement`:** implemented in `feedback.py`; **callers = tests ONLY** (`test_feedback_reinforcement.py`)
- **Rule SI-9** documents the intended convergence use — **policy exists**, **runtime wiring not evidenced**

## 4. v5.1 Roadmap Status (P5-P11)

| ID | Item | Status @ v5.4.2 | Evidence |
|----|------|-----------------|----------|
| P5 | Template nines_commands execution | Addressed (agent-consumable bridge) | CHANGELOG 5.2.0 Template NineS Bridge |
| P6 | Unified NineS command SSOT | Addressed | CHANGELOG 5.2.0 `nines/commands.py` |
| P7 | PluginRegistry orchestration integration | **Partial** | PluginRegistry exists; no CHANGELOG claims full stage orchestration |
| P8 | Round-based context switching | **Partial** | `apply_round_escalation` exists but not called from `select_context` |
| **P9** | **Remove deprecated `evaluate_gate_with_nines`, `run_nines_advisor`** | **PENDING** | Still exported in gate/__init__.py:64-65 |
| **P10** | **Eliminate `_BUILTIN_SPECS` hardcoding** | **PENDING** | Still in `plugins/loader.py:17-47` |
| **P11** | **Cursor hard reinforcement layer** | **NOT STARTED** | No grep hit for "hard reinforcement" |

## 5. S01-T06 Synthesis Candidates (H1-H7) @ v5.4.2

| ID | Candidate | State | Evidence |
|----|-----------|-------|----------|
| H1 | Rationalization tables | **Implemented** | SKILL.md §Rationalization Prevention (lines 200-211) |
| H2 | Lean dispatch compression | **Implemented in schema** | `schemas/lean-dispatch.yaml:142-173` |
| H3 | Advisor L3/L1 | **Partial** | Profile advisor section assembly; gate advisor margin hook; Anthropic-style advisor tool not first-class |
| H4 | Typed status | **In schema** | `schemas/lean-report.yaml:174` enum |
| H5 | Learnings JSONL | **Implemented** | `learnings.py` + selector integration |
| H6 | CSO skill description | **Largely aligned** | SKILL.md description is trigger-focused; `workflow-skill.yaml` identity still capability-focused |
| H7 | Self-improving loop | **Partial** | `feedback.py` proposals + safeguards; no fully automated post-workflow rule/skill writer |

## 6. M1-M11 Status (still open / partial)

| ID | Status | Notes |
|----|--------|-------|
| M1 | Partial | Types + handlers exist; reference doc not aligned |
| M2 | Partial | model_hint in selector; not full GSD-style dispatch profiles |
| M3 | Partial | Hooks exist; strict Menxia-style gate not evidenced |
| M4 | **Open** | Still hint-based substring matching |
| M5 | **Open** | No Scion/worktree orchestration |
| M6 | **Open** | No `trust_level` field |
| M7 | **Open** | No 2-stage gate chain in `evaluate_gate` |
| M8 | **Open** | No injection-pattern defense |
| M9 | Partial | Advisor recommendation on borderline; not full cross-model gate |
| M10 | **Open** | No intra-task reflection module |
| M11 | **Open** | CO-2 verbatim rules at policy level; no validator |

## 7. Convergence Loop Quality (Templates)

| Template | Loop | max_iter | Escalation |
|----------|------|:--------:|------------|
| full-pipeline | impl_review_test_cycle | 3 | on_exhaustion: escalate, target: plan |
| skill-optimization | optimize_benchmark_loop | 3 | target: null |
| research-design-review-refine | design_review_refine_loop | 3 | on_exhaustion: abort |
| product-verification | verification_cycle | 3 | target: design_tests, max: 1 |

**Gap:** stagnation rule is in Python gate (`scorer.py:503-514`), NOT in YAML templates. Templates use simple `max_iterations` + `on_exhaustion` only.

## v6.0.0 Gate/Context/Reinforcement Candidates

| ID | Title | Source | Status | Effort | Measurable |
|----|-------|--------|:------:|:------:|------------|
| **V6-01** | **Wire `merge_reinforcement_into_dispatch` + `generate_reinforcement` into convergence orchestration** | P4/SI-9/H7 | not started | M | −N wasted rounds; +rule fix rate |
| **V6-02** | **Integrate `apply_round_escalation` into `select_context(..., round_num=...)` + CLI** | P8/feedback | partial | S | −N% context noise on late rounds |
| **V6-03** | Plan-mode branch in context selection | feedback_for_skill | not started | M | +plan compliance score |
| **V6-04** | Profile `unwanted_hints` / negative routing | Candidate 3 | not started | M | +N scenarios with 0 noise |
| V6-05 | SkillRouter-style semantic routing | M4 | not started | L | +routing accuracy |
| **V6-06** | Remove deprecated gate/NineS APIs | P9 | not started | S | 0 DeprecationWarning |
| **V6-07** | Replace `_BUILTIN_SPECS` | P10 | not started | M | No config drift |
| V6-08 | Document gate taxonomy in references | M1/drift | not started | S | 0 reference drift |
| V6-09 | Optional Cursor hard-reinforcement hook | P11 | not started | M | +enforcement vs prompt-only |
| **V6-10** | Two-stage gate orchestration | M7 | not started | L | +scope correctness |
| V6-11 | `trust_level` + governance on skills/adapters | M6 | not started | M | Security posture |

### Top-7 Priority

1. V6-01 — Reinforcement merge in real dispatch paths (closes SI-9/P4 last mile)
2. V6-02 — `apply_round_escalation` inside `select_context` (finish P8)
3. V6-10 — Two-stage gate orchestration (M7)
4. V6-04 — `unwanted_hints` in selector
5. V6-03 — Plan-mode-aware context
6. V6-06 — Remove deprecated APIs (P9, pre-6.0 cleanup)
7. V6-07 — Replace `_BUILTIN_SPECS` (P10)
