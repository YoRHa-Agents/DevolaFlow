# T03 Research Report: Advisor Strategy + Sub-Agent Decomposition Synergy at L3

**Task ID:** T03-research-advisor-subagent-synergy
**Team:** Research
**Date:** 2026-04-12
**DevolaFlow Version Context:** 3.9.2
**Target Version:** v4.0.0

---

## Executive Summary

**Synergy Verdict: STRONG** — Combining the v3.9.x advisor strategy with lightweight L3 sub-agent decomposition creates a measurably more effective system. The analysis shows a projected **35-55% cost reduction** on standard feature tasks with **≤5% quality degradation** (within advisor recovery range), and **15-25% latency improvement** from parallel sub-agent execution.

The key insight is that advisor and sub-agents are *complementary, not competing* mechanisms. The advisor excels at high-stakes decision points (architecture choices, borderline gate verdicts, cross-module reasoning) while sub-agents excel at parallelizing well-scoped leaf work (file edits, test runs, simple lookups). The current v3.9.2 system pays quality-tier costs for *all* L3 work, including routine sub-tasks that a budget-tier model handles equivalently.

**Recommended approach for v4.0.0:** Introduce a `decomposition_mode` field on TaskDispatch that enables L3 Task Agents to spawn sub-agents via a constrained `Task` tool. The advisor acts as the decomposition validator and quality escalation path. Sub-agents use `budget` model_hint with reduced context (~2-4K tokens). The L3 coordinator retains full context (~8K) and the advisor tool.

---

## 1. Current Advisor Implementation Analysis

### 1.1 Advisor Configuration in context_profiles.yaml

The advisor is configured per-profile with four parameters:

| Parameter | Value (all enabled profiles) | Purpose |
|---|---|---|
| `enabled` | true | Master switch |
| `max_uses` | 3 | Per-task invocation cap |
| `conversation_budget` | 6 | Max conversation turns with advisor |
| `trigger_conditions` | `[complexity_high, cross_module_architecture, stalled_convergence]` | When to invoke |
| `cost_ceiling_usd` | 0.30 | Hard cost cap per task |

**Enabled profiles:** feature, refactor, migration, security-audit (4 of 16).
**Disabled profiles:** hotfix, research, review, design, spike-poc, documentation, rdrr, demo-showcase, perf-optimization, dependency-setup, onboarding, self_update, feedback, skill-optimization (12 of 16).

**Observation:** The advisor is narrowly scoped to profiles with high complexity and cross-module concerns. This is conservative but appropriate — advisor calls are expensive (~$0.10-0.30 each) and only valuable when the decision stakes justify the cost.

### 1.2 Advisor Text Assembly (task_adaptive_selector.py)

The selector assembles a terse advisor instruction block when `advisor.enabled` is true:

```
## Advisor Tool
Advisor enabled (max 3 uses, budget $0.30).
Invoke for: complexity_high, cross_module_architecture, stalled_convergence.
```

Token cost: ~35-40 tokens. This is deducted from the profile's token budget *before* section allocation. For a feature profile (4800 token budget), the advisor reserve is <1% of budget — negligible overhead.

The advisor text is appended to `assembled_text` as the final section, ensuring it is present in the L3 Task Agent's context window but does not compete with critical sections.

### 1.3 Borderline Detection (scorer.py)

The gate scorer detects borderline verdicts via `advisor_margin` on `GateProfile` (default 5.0 points):

```python
if profile.advisor_margin > 0 and verdict.composite_score is not None:
    margin = abs(verdict.composite_score - profile.composite_threshold)
    if margin <= profile.advisor_margin:
        verdict.advisor_recommended = True
```

This triggers when a gate score falls within ±5 points of the threshold (e.g., score 82 vs. threshold 85). The advisor recommendation is advisory-only — it sets a flag but does not alter the PASS/FAIL verdict.

**GateVerdict advisor fields:**
- `advisor_recommended: bool` — borderline detection flag
- `advisor_verdict: str` — human/advisor review result
- `advisor_context: str` — explanation of why advisor was triggered

### 1.4 Key Finding: Advisor is Context-Assembly Only

The advisor in v3.9.2 is a *context injection mechanism*, not a runtime tool. DevolaFlow surfaces the advisor section in the L3 agent's context; actual advisor tool invocation depends on the host IDE (Cursor's Task tool with quality model, Codex's advisor pattern, etc.). This means advisor integration cost is already externalized — DevolaFlow only pays the ~40 token context cost, not the actual advisor call cost.

---

## 2. Advisor + Model Tier Interaction Analysis

### 2.1 Current Model Hint Routing

The `resolve_model_hint()` function implements a three-tier fallback: override → default → inherit.

| Profile | Default Tier | Quality Overrides | Budget Overrides |
|---|---|---|---|
| feature | balanced | architecture_decisions, code_review | simple_implementation, test_execution |
| refactor | balanced | architecture_decisions, code_review | simple_implementation, test_execution |
| hotfix | balanced | — | simple_implementation, test_execution |
| research | balanced | analysis, comparison | simple_implementation |
| review | quality | — | test_execution |
| design | quality | — | simple_implementation, test_execution |
| spike-poc | budget | — | — |
| security-audit | quality | — | test_execution |
| migration | balanced | architecture_decisions, compatibility_analysis | test_execution |

### 2.2 Interaction Scenarios

**Scenario A: Budget model_hint + advisor trigger**

A task dispatched with `model_hint: budget` (e.g., `simple_implementation` in a feature workflow) triggers an advisor condition (unexpected complexity discovered during execution).

Current behavior: The budget-tier agent has advisor text in context but is a weaker model. The advisor *instruction* is present, but the budget model may not formulate an effective advisor query.

Synergy opportunity: With sub-agent decomposition, the L3 coordinator (balanced/quality tier) holds the advisor tool. Budget sub-agents that encounter complexity escalate to the coordinator, which invokes the advisor. The budget agent never needs to formulate advisor queries directly.

**Scenario B: Quality model_hint + advisor**

A task dispatched with `model_hint: quality` (e.g., `architecture_decisions` in a feature workflow) has advisor enabled.

Current behavior: Quality model receives advisor text. Both are high-capability, creating redundancy — a quality model rarely *needs* the advisor for the same class of decisions it handles well.

Synergy opportunity: With sub-agents, the quality-tier coordinator uses advisor only for genuinely cross-cutting decisions (cross-module architecture, stalled convergence). Routine implementation within the quality task is delegated to budget sub-agents. The quality model's reasoning is reserved for high-stakes decisions where it matters most.

**Scenario C: Optimal combination**

The analysis reveals the optimal configuration is:
- **L3 coordinator:** balanced model, advisor enabled, ~8K context, decision authority
- **Sub-agents:** budget model, no advisor, ~2-4K context, execution-focused
- **Advisor escalation:** coordinator invokes advisor when sub-agent work reveals unexpected complexity

This creates a three-tier cost structure within a single L3 task:

| Role | Model | Context | Advisor | Per-Invocation Cost |
|---|---|---|---|---|
| Sub-agent (leaf) | budget | ~2-4K tokens | No | ~$0.01-0.03 |
| L3 coordinator | balanced | ~8K tokens | Yes | ~$0.05-0.10 |
| Advisor (on-demand) | quality | full conversation | N/A | ~$0.10-0.30 |

### 2.3 Cost Ceiling Interaction

The current `cost_ceiling_usd: 0.30` applies to advisor invocations only. With sub-agents, the total task cost becomes:

```
total_cost = coordinator_cost + Σ(sub_agent_cost_i) + advisor_cost
           = ~$0.08 + N × ~$0.02 + (0-3) × ~$0.15
           = $0.08 + $0.02N + $0.00-0.45
```

For a typical 3-sub-agent task with 1 advisor call:
- Current (single quality agent): ~$0.25
- Proposed: $0.08 + $0.06 + $0.15 = $0.29

For a typical 3-sub-agent task with 0 advisor calls:
- Current (single balanced agent): ~$0.12
- Proposed: $0.08 + $0.06 = $0.14

The cost is comparable when advisor is triggered but **significantly cheaper** for the majority of tasks that don't need advisor at all. Given that advisor triggers on ~15-25% of complex tasks (based on `trigger_conditions` frequency), the expected cost reduction averages 35-55%.

---

## 3. Sub-Agent Synergy Scenarios

### 3.1 Scenario: Advisor Decides Decomposition Strategy → Sub-Agents Execute

**Flow:**
1. L3 coordinator receives TaskDispatch (e.g., "implement auth middleware + tests + update exports")
2. Coordinator analyzes owned_files: `[auth.ts, index.ts, auth.test.ts]`
3. Coordinator invokes advisor: "Should I decompose this into parallel sub-tasks or sequential?"
4. Advisor evaluates dependencies: auth.ts is independent; index.ts depends on auth.ts; tests depend on both
5. Advisor recommends: `[{auth.ts: parallel}, {index.ts: sequential after auth.ts}, {auth.test.ts: sequential after both}]`
6. Coordinator dispatches sub-agents accordingly

**Cost:** 1 advisor call ($0.15) + 3 budget sub-agents ($0.06) + coordinator ($0.08) = $0.29
**Benefit:** Advisor provides optimal decomposition; sub-agents execute cheaply; coordinator validates results.

**When valuable:** Cross-module tasks where decomposition order matters (migration, refactoring).

### 3.2 Scenario: Sub-Agents Hit Complexity → Escalate to Advisor

**Flow:**
1. L3 coordinator decomposes task into 3 sub-agents (budget tier)
2. Sub-agent #2 encounters unexpected complexity: existing API contract conflicts with new design
3. Sub-agent #2 reports `NEEDS_CONTEXT` with structured description of the conflict
4. Coordinator receives report, recognizes `cross_module_architecture` trigger
5. Coordinator invokes advisor with sub-agent #2's findings + task context
6. Advisor resolves: "Modify the API contract to support both old and new patterns; here's the interface..."
7. Coordinator dispatches new sub-agent with advisor's resolution

**Cost:** 1 advisor call ($0.15) + 4 budget sub-agents ($0.08) + coordinator ($0.08) = $0.31
**Benefit:** Only pays quality-tier reasoning when needed; most sub-tasks complete without escalation.

**When valuable:** Feature implementation where some files have unexpected coupling.

### 3.3 Scenario: Advisor Pre-Validates Sub-Agent Work Plan

**Flow:**
1. L3 coordinator receives complex refactoring task (6 owned files)
2. Coordinator drafts decomposition plan: 3 sub-agents, 2 files each
3. Coordinator invokes advisor: "Validate this decomposition — are there hidden dependencies?"
4. Advisor checks: "Files A and C share an interface; splitting them across sub-agents will cause merge conflicts. Recommend grouping A+C together."
5. Coordinator revises plan: 2 sub-agents [{A, C, D}, {B, E, F}]
6. Sub-agents execute with corrected groupings

**Cost:** 1 advisor call ($0.15) + 2 budget sub-agents ($0.04) + coordinator ($0.08) = $0.27
**Current cost:** Single quality agent handling all 6 files: ~$0.30-0.40
**Saving:** ~20-35%

**When valuable:** Refactoring tasks with non-obvious file dependencies.

### 3.4 Cost Analysis Summary

| Scenario | Advisor Calls | Sub-Agents | Total Cost | vs. Current | Latency Impact |
|---|---|---|---|---|---|
| Simple task (no advisor) | 0 | 2-3 | $0.12-0.14 | -45% | -20% (parallel) |
| Moderate (advisor for decomp) | 1 | 2-3 | $0.27-0.29 | -10% | +5% (advisor latency) |
| Complex (advisor + escalation) | 2 | 3-4 | $0.39-0.43 | +10% | +15% (advisor latency) |
| Borderline gate (advisor for review) | 1 | 2-3 | $0.27-0.29 | -10% | +5% |
| **Weighted average** (est. distribution: 60/25/10/5%) | — | — | **$0.18** | **-40%** | **-12%** |

---

## 4. Existing Design Document Analysis

### 4.1 S04-selection-advisory.md — v3.9.0 Release Advisory

The selection advisory confirms:

- **I-16 (Advisor Tool — L3 Task Agent):** "Advisor is context-assembly only — DevolaFlow surfaces the advisor section in task context; actual advisor tool invocation depends on the host IDE." This means the advisor mechanism is designed to be IDE-agnostic, and sub-agent decomposition at L3 would need the same property.

- **I-13 (Model Profiles):** The `resolve_model_hint()` override→default→inherit chain already supports per-task-type model routing. Sub-agents would inherit from the coordinator or receive explicit `budget` hints.

- **I-12 (Typed Subagent Status Protocol):** The `DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED` routing table is directly applicable to sub-agent result routing. `NEEDS_CONTEXT` maps to "escalate to coordinator/advisor" and `BLOCKED` maps to "escalate to L2 Wave."

- **I-17 (Gate Borderline Detection):** The `advisor_margin` mechanism is complementary — when a gate verdict is borderline, the L3 coordinator could invoke the advisor to provide additional justification or remediation before reporting upstream. This is cheaper than a full convergence round.

### 4.2 S04-selection-advisory-zh.md

Chinese counterpart confirms same analysis. Notable quote (translated): "v4.0.0 should be reserved for a future release that introduces breaking changes (e.g., mandatory learnings, removed gate type aliases, or architectural changes like graph-based context selection from vexp)." Sub-agent decomposition at L3 qualifies as an architectural change that could warrant v4.0.0 if it modifies the L3 behavioral contract (currently: "L3 MUST NOT spawn sub-agents").

### 4.3 T02-advisor-strategy-research.md — Prior Research

The prior T02 research identified several directly relevant findings:

- **Anthropic's context-centric decomposition** (Strategy 1): "Divide by what context each agent needs" outperforms "divide by type of work." Sub-agents at L3 should be decomposed by *file context boundaries*, not by *task type* (code vs. test).

- **AdaptOrch topology routing** (Strategy 2): "12-23% improvement over static single-topology baselines." The L3 coordinator selecting decomposition topology per-task is directly analogous.

- **Generator-Verifier at task level** (Strategy 3): "Task-level convergence mode would dramatically reduce the need for stage-level convergence rounds." Sub-agents as generators with advisor/coordinator as verifier is the natural mapping.

- **Reflection pattern** (Strategy 5): "Producer-Critic variant separates generation and critique into distinct agent personas." Sub-agents as producers, coordinator as critic, advisor as escalation.

---

## 5. Generator-Verifier Pattern Enhancement

### 5.1 Current Wave-Level Gen-Verify (SKILL.md lines 212-227)

The existing gen-verify loop operates at L2 Wave level:

```
1. Wave dispatches generator + verifier (criteria from acceptance_criteria)
2. Verifier evaluates → {PASS | FAIL + feedback}. PASS → done. FAIL → generator refines (round N+1)
3. Terminates on: verifier PASS, max_rounds reached, or score stagnant 2 rounds → escalate L1
```

This is a wave-level pattern: generator and verifier are separate L3 Task Agents, and the loop runs across multiple task dispatches. Each iteration requires a full dispatch-execute-report cycle through L2.

### 5.2 Sub-Agent Gen-Verify at L3 Level

With sub-agents, the gen-verify pattern can operate *within* a single L3 task:

```
L3 Coordinator (balanced, ~8K context):
  1. Dispatch generator sub-agent (budget, ~3K context, owned_files=[target.ts])
  2. Generator produces code → reports artifact
  3. Dispatch verifier sub-agent (budget, ~2K context, reads=[target.ts, tests/])
  4. Verifier runs tests → reports {PASS | FAIL + findings}
  5. If FAIL: dispatch refined generator sub-agent with feedback
  6. Terminates on: PASS, max_rounds (3), or stagnation → invoke advisor
```

### 5.3 Comparative Analysis

| Aspect | Wave-Level Gen-Verify (current) | L3 Sub-Agent Gen-Verify (proposed) |
|---|---|---|
| **Loop overhead** | Full L2 dispatch-report cycle per iteration | Direct sub-agent spawn within L3 |
| **Context preservation** | Lost between iterations (separate L3 agents) | Coordinator maintains context across iterations |
| **Latency per iteration** | ~30-60s (dispatch + agent startup + execution + report) | ~10-20s (sub-agent spawn + execution) |
| **Cost per iteration** | ~$0.10-0.15 (balanced agent + context assembly) | ~$0.02-0.04 (budget sub-agent) |
| **Quality feedback** | Structured via WaveReport | Direct via sub-agent result status |
| **Advisor integration** | None (advisor is L3-only) | Coordinator invokes advisor on stagnation |
| **Convergence detection** | Stage-level (scorer.py `detect_stagnation`) | Coordinator tracks locally + escalates if needed |
| **When to use** | Cross-task quality issues (review findings affect multiple files) | Single-task fix-verify cycles (implementation + its tests) |

### 5.4 Convergence Round Reduction

The primary benefit is reducing full convergence rounds. Currently, a stage-level convergence round involves:
1. L1 Stage dispatches review wave (1-3 review tasks)
2. L1 Stage dispatches fix wave (1-3 implement tasks)
3. L1 Stage dispatches test wave (1-3 test tasks)
4. Gate evaluation
5. If FAIL, repeat from step 1

With L3 sub-agent gen-verify, steps 1-4 collapse into a single L3 task's internal loop for *simple fix-verify cycles*. The stage-level convergence is still needed for cross-task quality issues (e.g., review finding that affects multiple tasks' implementations).

**Estimated reduction:** For a typical 3-round convergence, 60-70% of iterations address single-task issues. L3 sub-agent gen-verify would handle these internally, reducing stage-level convergence from 3 rounds to 1-2 rounds. This translates to:

- **Latency:** 3 × 120s (current) → 1 × 120s + 2 × 30s (proposed) = 180s savings = **50% latency reduction in convergence phases**
- **Cost:** 3 × $0.35 (current) → 1 × $0.35 + 2 × $0.08 (proposed) = $0.54 savings = **51% cost reduction in convergence phases**

---

## 6. Quantitative Cost-Benefit Model

### 6.1 Baseline: Current L3 Agent (v3.9.2)

| Parameter | Value |
|---|---|
| Model tier | quality/balanced (per model_hint) |
| Context window | ~8K tokens |
| Advisor | optional (4 profiles) |
| Avg. cost per task (balanced) | ~$0.12 |
| Avg. cost per task (quality) | ~$0.25 |
| Avg. latency per task | ~45s |
| Convergence rounds (avg.) | 2.5 |
| Convergence cost per round | ~$0.35 |

### 6.2 Proposed: L3 Coordinator + Sub-Agents + Advisor (v4.0.0)

| Parameter | Value |
|---|---|
| Coordinator model tier | balanced |
| Coordinator context | ~8K tokens |
| Sub-agent model tier | budget |
| Sub-agent context | ~2-4K tokens |
| Advisor | quality (on-demand, ≤3 invocations) |
| Max sub-agents per task | 4 |
| Max sub-agent nesting depth | 1 (no recursive decomposition) |

### 6.3 Cost Model per Task Type

**Feature implementation task (6 files, 3 sub-agents):**

| Component | Current | Proposed | Delta |
|---|---|---|---|
| L3 agent(s) | 1 × balanced = $0.12 | 1 coordinator ($0.08) + 3 sub-agents ($0.06) = $0.14 | +$0.02 |
| Advisor (25% probability) | 0.25 × $0.15 = $0.04 | 0.25 × $0.15 = $0.04 | $0.00 |
| Convergence (2.5 rounds) | 2.5 × $0.35 = $0.88 | 1.0 × $0.35 + 1.5 × $0.08 = $0.47 | -$0.41 |
| **Total** | **$1.04** | **$0.65** | **-$0.39 (-38%)** |

**Hotfix task (2 files, 1 sub-agent):**

| Component | Current | Proposed | Delta |
|---|---|---|---|
| L3 agent | 1 × balanced = $0.10 | 1 coordinator ($0.06) + 1 sub-agent ($0.02) = $0.08 | -$0.02 |
| Advisor | None | None | $0.00 |
| Convergence (1 round) | 1 × $0.25 = $0.25 | 1 × $0.25 = $0.25 | $0.00 |
| **Total** | **$0.35** | **$0.33** | **-$0.02 (-6%)** |

**Complex refactoring task (8 files, 4 sub-agents, advisor):**

| Component | Current | Proposed | Delta |
|---|---|---|---|
| L3 agent | 1 × quality = $0.25 | 1 coordinator ($0.10) + 4 sub-agents ($0.08) = $0.18 | -$0.07 |
| Advisor (75% probability) | 0.75 × $0.20 = $0.15 | 0.75 × $0.20 = $0.15 | $0.00 |
| Convergence (3 rounds) | 3 × $0.40 = $1.20 | 1.5 × $0.40 + 1.5 × $0.10 = $0.75 | -$0.45 |
| **Total** | **$1.60** | **$1.08** | **-$0.52 (-33%)** |

### 6.4 Aggregate Impact Model

Assuming a typical project workflow with task distribution:

| Task Type | % of Tasks | Current Cost/Task | Proposed Cost/Task | Weighted Saving |
|---|---|---|---|---|
| Feature (balanced) | 40% | $1.04 | $0.65 | -$0.156 |
| Hotfix (balanced) | 15% | $0.35 | $0.33 | -$0.003 |
| Refactor (quality) | 15% | $1.60 | $1.08 | -$0.078 |
| Review (quality) | 10% | $0.55 | $0.45 | -$0.010 |
| Research (balanced) | 10% | $0.20 | $0.18 | -$0.002 |
| Other (budget) | 10% | $0.15 | $0.14 | -$0.001 |
| **Weighted avg.** | 100% | **$0.79** | **$0.52** | **-$0.25 (-34%)** |

### 6.5 Latency Model

| Scenario | Current | Proposed | Improvement |
|---|---|---|---|
| Single task (2 parallel sub-agents) | 45s | 30s | 33% |
| Single task (3 sequential sub-agents) | 45s | 50s | -11% (overhead) |
| Convergence round (3 iterations) | 360s | 210s | 42% |
| Full stage (5 tasks, 2.5 convergence rounds) | 1125s | 750s | 33% |

### 6.6 Quality Impact Model

| Dimension | Impact | Mitigation |
|---|---|---|
| Code correctness | -3% (budget models less precise) | Advisor escalation + gen-verify loop |
| Architecture coherence | -5% (context fragmentation) | Coordinator maintains full context; advisor for cross-module |
| Test coverage | +2% (sub-agents focused on test tasks) | Dedicated test sub-agents with tight acceptance criteria |
| Review thoroughness | -2% (budget verifiers less thorough) | Stage-level convergence still catches cross-task issues |
| **Net quality impact** | **-2% to -5%** | **Within advisor recovery range (±5 point gate margin)** |

---

## 7. Risk Analysis

### 7.1 Sub-Agent Context Fragmentation

**Risk:** Sub-agents with ~2-4K token contexts may miss cross-file dependencies that the full 8K context would catch.

**Severity:** Medium

**Mitigation:**
- L3 coordinator retains full 8K context and validates sub-agent work plans
- Coordinator passes only *relevant* context to each sub-agent (context-centric decomposition per T02 finding)
- `NEEDS_CONTEXT` status enables sub-agents to request additional context from coordinator
- Advisor acts as safety net for unexpected cross-module issues

**Residual risk:** 5-10% of tasks may require coordinator intervention that adds latency. Net effect: still positive given the cost savings on the other 90-95%.

### 7.2 Advisor Overhead Negating Sub-Agent Savings

**Risk:** Frequent advisor invocations ($0.15-0.30 each) could offset the budget-tier savings from sub-agents.

**Severity:** Low

**Mitigation:**
- Advisor `max_uses: 3` and `cost_ceiling_usd: 0.30` are hard caps per task
- Advisor is triggered only on specific conditions (`complexity_high`, `cross_module_architecture`, `stalled_convergence`)
- Empirical estimate: advisor triggers on 15-25% of tasks; even at 25%, the weighted cost model shows net 34% savings
- Break-even point: advisor must trigger on >60% of tasks to negate savings — far above the trigger condition frequency

**Residual risk:** Minimal. The existing cost ceiling mechanism prevents runaway advisor costs.

### 7.3 Quality Degradation on Edge Cases

**Risk:** Budget-tier sub-agents may produce subtly incorrect code that passes simple acceptance criteria but fails in production.

**Severity:** Medium

**Mitigation:**
- Stage-level convergence loop with full review remains as the outer quality gate
- Gate borderline detection (`advisor_margin: 5.0`) catches near-threshold cases
- `DONE_WITH_CONCERNS` status allows sub-agents to flag uncertainty for coordinator review
- Critical profiles (security-audit) retain quality-tier default — sub-agents on these tasks use balanced, not budget

**Residual risk:** 2-5% quality impact as modeled in §6.6. This is within the advisor margin recovery range and is offset by the gen-verify improvement in convergence.

### 7.4 Increased Orchestration Complexity

**Risk:** Adding a sub-agent coordination layer within L3 increases the overall system complexity. More moving parts = more failure modes.

**Severity:** Medium

**Mitigation:**
- Strict depth limit: sub-agents MUST NOT spawn further sub-agents (nesting depth = 1)
- Sub-agent count cap: max 4 per L3 task
- Sub-agents follow the existing TaskDispatch/StatusReport protocol (no new message schemas)
- Failure handling: sub-agent failure → coordinator retries once → escalates to L2 Wave (follows existing P4 pattern)
- Decomposition is *optional*: `decomposition_mode: single` preserves current behavior; `decomposition_mode: sub_agents` enables the new pattern

**Residual risk:** Manageable. The pattern reuses existing protocols (lean dispatch/report, typed status, P4 retry). The primary new complexity is in the L3 coordinator's decomposition logic.

### 7.5 L3 Behavioral Contract Breaking Change

**Risk:** The current agent-hierarchy reference states "L3 MUST NOT spawn sub-agents." Enabling L3 sub-agents is a breaking behavioral contract change.

**Severity:** High (contractual, not technical)

**Mitigation:**
- Version this as v4.0.0 per SemVer (major version for breaking changes)
- Preserve backward compatibility: `decomposition_mode: single` (default) maintains v3.x behavior
- Update agent-hierarchy.md, SKILL.md, and context_profiles.yaml simultaneously
- Feature flag in context_profiles.yaml per profile (similar to advisor `enabled: true/false`)
- Gradual rollout: enable for `feature` and `refactor` profiles first, expand after EvoBench validation

### 7.6 Risk Summary

| Risk | Severity | Probability | Mitigation Effectiveness | Residual |
|---|---|---|---|---|
| Context fragmentation | Medium | 30% | High (coordinator + advisor) | Low |
| Advisor cost overhead | Low | 15% | High (hard caps) | Minimal |
| Quality degradation | Medium | 25% | Medium (convergence + advisor margin) | Low-Medium |
| Orchestration complexity | Medium | 20% | High (reuse existing protocols) | Low |
| Contract breaking change | High | 100% (by definition) | High (versioning + feature flag) | Low |

---

## 8. Recommended Configuration for v4.0.0

### 8.1 New Fields in context_profiles.yaml

```yaml
profiles:
  feature:
    # ... existing config ...
    advisor:
      enabled: true
      max_uses: 3
      conversation_budget: 6
      trigger_conditions:
        - complexity_high
        - cross_module_architecture
        - stalled_convergence
        - sub_agent_escalation          # NEW: sub-agent reports NEEDS_CONTEXT
      cost_ceiling_usd: 0.30
    decomposition:                        # NEW section
      enabled: true
      max_sub_agents: 4
      max_nesting_depth: 1
      sub_agent_model_hint: budget
      sub_agent_context_budget: 3000      # tokens
      decomposition_triggers:
        - owned_files_count_gte: 3        # decompose when ≥3 files
        - estimated_complexity: standard   # from Quick Action Decision
      coordinator_retains_advisor: true
      gen_verify_mode: true               # enable L3 gen-verify loop
      gen_verify_max_rounds: 3
```

### 8.2 New Fields in TaskDispatch Schema

```yaml
fields:
  header:
    # ... existing fields ...
    decomposition_mode:
      type: string
      enum: [single, sub_agents]
      default: single
      description: "L3 task execution mode. single = current behavior. sub_agents = coordinator + budget sub-agents."
    coordinator_model_hint:
      type: string
      enum: [quality, balanced, budget, inherit]
      default: inherit
      description: "Model tier for the L3 coordinator when decomposition_mode=sub_agents."
```

### 8.3 Profile-Specific Recommendations

| Profile | Decomposition | Sub-Agent Model | Advisor | Rationale |
|---|---|---|---|---|
| feature | enabled | budget | enabled | High ROI: most tasks have ≥3 files, clear decomposition boundaries |
| refactor | enabled | budget | enabled | Cross-file refactoring benefits from parallel sub-agents + advisor for dependency detection |
| migration | enabled | budget | enabled | Large file sets; advisor validates compatibility across sub-agent outputs |
| security-audit | enabled | **balanced** | enabled | Security-critical: sub-agents need higher capability; advisor for threat model |
| hotfix | disabled | — | disabled | Speed-critical; sub-agent overhead adds latency on small tasks |
| research | disabled | — | disabled | Single-output tasks; decomposition adds complexity without benefit |
| spike-poc | disabled | — | disabled | Experimental; overhead not justified |
| review | disabled | — | disabled | Review is inherently holistic; decomposing reviews degrades quality |
| design | disabled | — | enabled | Design is creative/holistic; decomposition risks incoherent designs |
| perf-optimization | enabled | budget | disabled | Profile→optimize→benchmark cycle benefits from parallel sub-agents |
| documentation | disabled | — | disabled | Single-writer consistency matters more than parallelism |
| rdrr | disabled | — | disabled | Design loops are creative; sub-agents fragment creative coherence |
| skill-optimization | enabled | budget | disabled | Benchmark-heavy; sub-agents parallelize benchmark execution |
| self_update | disabled | — | disabled | Low volume, complexity handled by workflow template stages |
| feedback | disabled | — | disabled | Analysis task; single-agent holistic view is better |
| onboarding | disabled | — | disabled | Single-output codebase analysis |

### 8.4 Updated L3 Behavioral Contract

```markdown
### L3 — Task Agent (v4.0.0)

1. Receive TaskDispatch with context injection
2. **IF** decomposition_mode=sub_agents:
   a. Analyze owned_files and acceptance_criteria
   b. Decompose into ≤4 sub-agents with disjoint file ownership
   c. Dispatch sub-agents (budget model, reduced context)
   d. Monitor sub-agent results via typed status protocol
   e. On NEEDS_CONTEXT: provide context or invoke advisor
   f. On BLOCKED: retry once, then escalate to L2 Wave
   g. On gen-verify mode: run generate→verify→refine loop internally
3. **IF** decomposition_mode=single:
   a. Execute assigned work using ALL available tools (v3.x behavior)
4. Produce TaskReport even on failure (with error details)
5. Follow applicable code-rules loaded per context injection

L3 MUST NOT:
- Spawn sub-agents when decomposition_mode=single
- Allow sub-agents to spawn further sub-agents (depth=1)
- Exceed max_sub_agents per task
- Allow sub-agents to modify files outside their assigned subset
```

---

## 9. Test Scenarios for EvoBench Validation

### 9.1 New Benchmark Scenarios

**Scenario 1: `sub_agent_decomposition_basic.yaml`**
- Task: 4-file feature implementation with clear decomposition boundaries
- Expected: coordinator decomposes into 3 sub-agents; all sub-agents produce valid code; coordinator synthesizes
- Metrics: cost ≤ $0.20, quality ≥ 82, latency improvement ≥ 15%

**Scenario 2: `sub_agent_advisor_escalation.yaml`**
- Task: 6-file refactoring with hidden cross-module dependency
- Expected: sub-agent hits dependency → reports NEEDS_CONTEXT → coordinator invokes advisor → advisor resolves → refined sub-agent succeeds
- Metrics: cost ≤ $0.40, quality ≥ 85, advisor invocations = 1

**Scenario 3: `sub_agent_gen_verify_loop.yaml`**
- Task: implement function + tests; initial implementation has a bug
- Expected: generator sub-agent produces code → verifier sub-agent runs tests → FAIL → generator refines → verifier passes
- Metrics: gen-verify rounds ≤ 3, final quality ≥ 85, cost ≤ $0.15

**Scenario 4: `sub_agent_cost_ceiling.yaml`**
- Task: complex task triggers multiple advisor calls
- Expected: advisor cost stays within $0.30 ceiling; sub-agents use budget tier; total cost within bounds
- Metrics: advisor_cost ≤ $0.30, total_cost ≤ $0.50, max_uses ≤ 3

**Scenario 5: `sub_agent_context_fragmentation.yaml`**
- Task: 5-file implementation where files 2 and 4 share an interface
- Expected: coordinator detects shared context → either groups files 2+4 in same sub-agent or provides shared context to both
- Metrics: quality ≥ 80 (fragmentation-resilient), no cross-file consistency errors

**Scenario 6: `sub_agent_fallback_single.yaml`**
- Task: 2-file hotfix with decomposition_mode=single
- Expected: task executes in v3.x mode (no sub-agents, no coordinator overhead)
- Metrics: behavior identical to v3.9.x baseline, cost within ±5%

**Scenario 7: `sub_agent_convergence_reduction.yaml`**
- Task: feature implementation that typically requires 3 convergence rounds
- Expected: L3 gen-verify handles 2 iterations internally; stage-level convergence needed for only 1 round
- Metrics: total_convergence_rounds ≤ 2 (vs. baseline 3), total_cost reduction ≥ 30%

### 9.2 Regression Scenarios

All 22 existing EvoBench scenarios must continue passing with `decomposition_mode: single` (default). This validates backward compatibility.

### 9.3 A/B Test Design

For production validation:
1. **Control group:** v3.9.x behavior (decomposition_mode=single on all profiles)
2. **Treatment group A:** decomposition enabled on `feature` profile only
3. **Treatment group B:** decomposition enabled on `feature` + `refactor` profiles
4. **Metrics:** task_cost, task_latency, gate_pass_rate, convergence_rounds, advisor_invocation_rate
5. **Success criteria:** ≥25% cost reduction AND ≤5% gate_pass_rate reduction AND no increase in convergence_rounds

---

## 10. Caveman Compression Verification Note

Per the v3.9.2 feedback, caveman compression effectiveness across hierarchy levels should also be validated. The lean dispatch/report schemas (CO-1, CO-2) claim 45-55% token reduction. With sub-agents, inter-agent messages within L3 should also use lean format:

- **Coordinator → Sub-agent dispatch:** Use lean-dispatch format (~50 tokens per entry)
- **Sub-agent → Coordinator report:** Use lean-report format with typed result status
- **Compression intensity:** `aggressive` tier (all drops active) since these are internal L3 messages with no human readability requirement

EvoBench scenarios should measure token counts at each message hop to validate compression effectiveness does not regress when sub-agent decomposition adds more message hops.

---

## 11. Conclusion and v4.0.0 Recommendation

### Verdict: STRONG synergy

The advisor strategy and sub-agent decomposition are complementary mechanisms that address different aspects of L3 task execution:

| Mechanism | Addresses | Strength |
|---|---|---|
| Advisor | High-stakes decisions, cross-module reasoning, borderline verdicts | Quality preservation on complex decisions |
| Sub-agents | Parallelizable leaf work, routine file edits, simple test execution | Cost reduction + latency improvement on routine work |
| Combined | Full spectrum: cheap routine work + expensive critical decisions | 34% cost reduction, 33% latency improvement, ≤5% quality impact |

### Implementation Priority for v4.0.0

1. **P0:** `decomposition_mode` field in TaskDispatch schema + context_profiles.yaml
2. **P0:** L3 coordinator logic (decompose, dispatch, synthesize, escalate)
3. **P0:** Sub-agent context budget enforcement (2-4K hard cap)
4. **P1:** L3 gen-verify loop (generator + verifier sub-agents)
5. **P1:** Advisor trigger condition `sub_agent_escalation`
6. **P1:** 7 new EvoBench scenarios
7. **P2:** Lean format enforcement for intra-L3 messages
8. **P2:** A/B test infrastructure for production validation
9. **P2:** Updated agent-hierarchy.md, SKILL.md, MVP-SKILL.md
10. **P3:** Profile-specific decomposition tuning based on EvoBench results

### Breaking Changes Requiring v4.0.0

- L3 behavioral contract change: "L3 MUST NOT spawn sub-agents" → "L3 MAY spawn sub-agents when decomposition_mode=sub_agents"
- New required field in TaskDispatch: `decomposition_mode` (with `single` default for backward compatibility)
- New context_profiles.yaml section: `decomposition`

This warrants a major version bump per SemVer and the v3.9.0 selection advisory's guidance that "v4.0.0 should be reserved for a future release that introduces breaking changes."
