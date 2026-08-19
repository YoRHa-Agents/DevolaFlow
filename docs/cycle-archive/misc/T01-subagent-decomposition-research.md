---
task_id: T01-research
title: "L3 Task Agent Sub-Decomposition: Feasibility Analysis"
team: Research
status: complete
devolaflow_version_context: "3.9.2"
target_version: "4.0.0"
last_updated: "2026-04-12"
predecessor_reports:
  - S04-selection-advisory.md
  - T04-advisor-integration-designs.md
  - S01-T06-synthesis.md
verdict: partially-viable
---

# T01 — L3 Task Agent Sub-Decomposition: Feasibility Research

## Executive Summary

**Verdict: PARTIALLY VIABLE**

Decomposing L3 Task agents into lighter sub-agents using cheaper/faster models is **feasible for a defined subset of task types** but would require careful architectural changes to preserve DevolaFlow's invariants. The research identifies two viable approaches:

1. **Intra-L3 Model Routing** (recommended, low-risk): L3 remains a leaf node but the *host platform* routes L3 tasks to different model tiers based on `model_hint`. No hierarchy change. Already partially implemented via `model_hint` in `task-dispatch.schema.yaml` and `context_profiles.yaml`.

2. **L3 Internal Decomposition** (higher impact, higher risk): L3 gains the ability to spawn lightweight "L3.5" micro-tasks using `model: "fast"` for well-scoped subtasks. Requires relaxing the "MUST NOT spawn sub-agents" constraint with strict guardrails.

The research recommends **Approach 1 for v4.0.0** (completing the model_hint → platform mapping) and **Approach 2 as an experimental opt-in for v4.1.0** after quantitative validation via EvoBench.

---

## 1. Current L3 Constraints Analysis

### Source: `workflow-system/agent/references/agent-hierarchy.md`

The L3 constraint is explicit:

| Layer | MUST NOT |
|---|---|
| **L3 Task** | Spawn sub-agents, delegate work, modify files outside owned set, exceed timeout |

### Why This Constraint Exists

The "MUST NOT spawn sub-agents" rule protects four properties:

| Property | Protection Mechanism | Risk If Violated |
|---|---|---|
| **P1 — Dispatcher-Not-Implementer** | Only L3 does work; if L3 dispatches, it becomes a dispatcher, violating the clean separation | Blurred responsibilities; L3 could rationalize "I'll dispatch this part" instead of doing work |
| **Hierarchy Predictability** | 4-layer depth is fixed (L0→L1→L2→L3). Adding L3.5 creates variable depth | Harder to reason about escalation chains, timeout budgets, and context flows |
| **Context Budget Control** | L3 gets ~8K tokens. Sub-agents would fragment this budget into unpredictable smaller chunks | Sub-agents may lack sufficient context for quality output |
| **Error Escalation** | Task→Wave→Stage→Project→Human is a clean 4-hop chain. Sub-tasks add a 5th hop | Failure classification and retry logic become more complex |

### Assessment

The constraint is *protective, not fundamental*. It exists to maintain system simplicity, not because sub-decomposition is architecturally impossible. The key question is whether the benefits (cost/speed) outweigh the complexity cost.

---

## 2. Host Platform Capabilities

### Cursor Task Tool

The Cursor IDE's `Task` tool supports a `model` parameter:

```
model: "fast"  — cost 1/10, intelligence 5/10
(default)      — inherits from parent
```

This is the primary mechanism for model tier routing. The `fast` model is described as "extremely fast, moderately intelligent, effective for tightly scoped changes, not well-suited for long-horizon tasks."

### DevolaFlow's model_hint System

Already implemented in v3.9.0 (I-13):

**Schema** (`task-dispatch.schema.yaml`):
```yaml
model_hint:
  type: string
  enum: [quality, balanced, budget, inherit]
  default: inherit
  description: "Host IDE interprets this hint to select appropriate model tier"
```

**Resolver** (`task_adaptive_selector.py`):
```python
def resolve_model_hint(task_type, profile_config):
    # 1. Check profile-level overrides
    # 2. Fall back to default_tier
    # 3. Fall back to "inherit"
```

**Profile Configuration** (`context_profiles.yaml`):
```yaml
# Example: feature profile
model_hints:
  default_tier: balanced
  overrides:
    architecture_decisions: quality
    code_review: quality
    simple_implementation: budget
    test_execution: budget
```

### Gap Analysis

| Aspect | Status | Gap |
|---|---|---|
| `model_hint` in dispatch schema | Implemented | None |
| `resolve_model_hint()` in selector | Implemented | None |
| Per-profile overrides | Implemented (15 profiles) | None |
| **model_hint → Cursor `model` param mapping** | **NOT IMPLEMENTED** | **Critical gap** |
| **L2 Wave reading model_hint to set Task tool `model`** | **NOT IMPLEMENTED** | **Critical gap** |
| **Validation that budget-model tasks stay within capability** | **NOT IMPLEMENTED** | **Important gap** |

The infrastructure for model routing exists in DevolaFlow's schema and configuration layers, but the actual dispatch-time translation from `model_hint: budget` → `Task(model="fast")` is not wired up. This is the lowest-hanging fruit for v4.0.0.

---

## 3. Task Decomposition Patterns

### Task Type Suitability for Lighter Models

Analysis based on benchmark scenarios, context profiles, and task type specializations from the agent hierarchy spec:

| Task Category | Example | Current Model | Suitable for Budget Model? | Rationale |
|---|---|---|---|---|
| **Simple implementation** (< 20 LOC) | Add export to barrel file, add config field | balanced | **YES — high confidence** | Tightly scoped, single-file, mechanical |
| **Test execution** | Run `pytest`, report results | balanced | **YES — high confidence** | Shell execution + structured output, no reasoning depth needed |
| **Boilerplate generation** | Create module scaffolding, test stubs | balanced | **YES — high confidence** | Template-driven, low novelty |
| **Lint/format fix** | Apply ruff suggestions, fix imports | balanced | **YES — high confidence** | Deterministic fixes with clear rules |
| **Research/survey** | Compare libraries, survey prior art | balanced | **PARTIAL — medium confidence** | Web search + synthesis needs reasoning; simple lookups are budget-safe |
| **Code review** | Quality scoring, finding classification | quality | **NO — low confidence** | Requires deep code understanding, nuanced judgment |
| **Architecture decisions** | Design API, choose patterns | quality | **NO — very low confidence** | Requires broad knowledge, tradeoff analysis, long-horizon reasoning |
| **Complex implementation** (50+ LOC) | New module with tests | balanced | **NO — medium confidence** | Needs sustained coherent reasoning across files |
| **Bug triage** | Root cause analysis from stack trace | balanced | **PARTIAL — depends on complexity** | Simple bugs → budget; cross-module bugs → quality |

### Quantitative Task Distribution Estimate

Based on typical DevolaFlow workflow compositions (full-pipeline has 15-25 tasks across stages):

| Model Tier | % of Total Tasks | Typical Task Count (full-pipeline) | Cost Multiplier |
|---|---|---|---|
| Quality (Opus-class) | 15-25% | 3-5 tasks | 1.0x (baseline) |
| Balanced (default) | 40-55% | 8-12 tasks | ~0.3-0.5x |
| Budget (fast/Sonnet-class) | 25-40% | 5-8 tasks | ~0.1x |

### Sub-decomposition Candidates Within L3

If L3 could spawn micro-tasks, these patterns emerge:

| L3 Task Type | Sub-decomposable Into | Sub-task Model |
|---|---|---|
| `implement` (with tests) | 1. Write code (balanced) + 2. Write tests (budget) | Mixed |
| `review` | 1. Lint check (budget) + 2. Semantic review (quality) | Mixed |
| `research` | 1. Web search (budget) + 2. Synthesis (balanced) | Mixed |
| `benchmark` | 1. Run benchmark (budget) + 2. Analyze results (balanced) | Mixed |

---

## 4. Model Tier Routing Analysis

### Current State

The `resolve_model_hint()` function provides a 3-level resolution:

```
1. profile.model_hints.overrides[task_type]  →  exact match
2. profile.model_hints.default_tier          →  profile default
3. "inherit"                                 →  use parent's model
```

All 15 context profiles define `model_hints`. Coverage of overrides:

| Override Key | Profiles Using It | Mapped Hint |
|---|---|---|
| `simple_implementation` | 10 of 15 | `budget` |
| `test_execution` | 11 of 15 | `budget` |
| `architecture_decisions` | 5 of 15 | `quality` |
| `code_review` | 3 of 15 | `quality` |
| `analysis` | 4 of 15 | `quality` |
| `benchmark_evaluation` | 2 of 15 | `quality` |

### Proposed model_hint → Platform Mapping

| DevolaFlow Hint | Cursor Mapping | Claude API | OpenAI API |
|---|---|---|---|
| `quality` | (default/inherit) | claude-opus-4 | o3 |
| `balanced` | (default/inherit) | claude-sonnet-4 | gpt-4.1 |
| `budget` | `model: "fast"` | claude-haiku | gpt-4.1-mini |
| `inherit` | (inherit from parent) | (inherit) | (inherit) |

The critical observation: Cursor's Task tool only exposes `fast` vs default. This means DevolaFlow's 4-tier hint system (quality/balanced/budget/inherit) collapses to a 2-tier system on Cursor: `fast` (budget) vs default (everything else). On other platforms (Claude Code, Codex), finer-grained routing may be possible.

### Recommendation

The mapping should be platform-adaptive:

```yaml
# Proposed addition to context_profiles.yaml or a new platform_routing.yaml
platform_model_mapping:
  cursor:
    quality: inherit    # Cursor doesn't support "better than default"
    balanced: inherit
    budget: fast
    inherit: inherit
  codex:
    quality: o3
    balanced: gpt-4.1
    budget: gpt-4.1-mini
    inherit: inherit
  claude_code:
    quality: opus
    balanced: sonnet
    budget: haiku
    inherit: inherit
```

---

## 5. Cost-Speed-Quality Tradeoff Analysis

### Token Budget Implications

| Scenario | L3 Context Budget | Sub-agent Budget | Overhead |
|---|---|---|---|
| **Current** (no sub-agents) | ~8K tokens | N/A | 0 |
| **Approach 1** (model routing, no sub-agents) | ~8K tokens | N/A | 0 — same budget, cheaper model |
| **Approach 2** (L3 spawns micro-tasks) | ~8K tokens | ~3-4K per micro-task | ~2K overhead per spawn (identity + dispatch) |

Approach 2's overhead problem: each micro-task needs its own context injection (~100 tokens identity + ~500 task spec + ~200 behavioral = ~800 minimum). With 2-3 micro-tasks, that's 1.6-2.4K tokens of overhead on top of the ~8K L3 budget. The parent L3 agent also needs tokens to orchestrate.

### Cost Reduction Estimates

**Approach 1 — Model Routing Only (no sub-agents):**

| Metric | Current | With Model Routing | Delta |
|---|---|---|---|
| Per-task cost (budget tasks) | ~$0.10-0.30 | ~$0.01-0.03 | **-90%** |
| Per-task cost (quality tasks) | ~$0.10-0.30 | ~$0.10-0.30 | 0% |
| Per-workflow cost (full-pipeline) | ~$2.00-6.00 | ~$1.00-3.50 | **-35-45%** |
| Per-task latency (budget tasks) | 30-90s | 5-15s | **-75-85%** |
| Quality risk | baseline | Low for scoped tasks | Minimal |

**Approach 2 — L3 Sub-decomposition:**

| Metric | Current | With L3 Sub-agents | Delta |
|---|---|---|---|
| Per-task cost | ~$0.10-0.30 | ~$0.05-0.20 | **-30-50%** |
| Per-task latency | 30-90s | 20-60s (parallelizable) | **-20-40%** |
| Quality risk | baseline | **Medium** — sub-agents have less context | Measurable |
| Orchestration overhead | 0 | ~15-25% of L3 budget | Negative |
| Error handling complexity | 4-hop chain | 5-hop chain | **+25% complexity** |

### Speed Improvement Estimates

Budget-model tasks (Cursor `fast`):
- **Latency**: 3-10x faster than Opus-class models for simple tasks
- **Throughput**: Higher parallelism possible since cheaper models allow more concurrent agents
- **Time-to-completion for full-pipeline**: Estimated 20-35% reduction (budget tasks ~40% of total, each 3-5x faster)

### Quality Risk Assessment

| Task Type | Quality Risk on Budget Model | Mitigation |
|---|---|---|
| Simple implementation | **Low** — mechanical, well-scoped | Acceptance criteria validation |
| Test execution | **Very Low** — shell execution, structured output | Exit code + coverage check |
| Boilerplate generation | **Low** — template-driven | File existence + syntax check |
| Research survey | **Medium** — synthesis quality may degrade | Generator-verifier loop at Wave level |
| Complex implementation | **High** — coherence and design adherence degrade | DO NOT route to budget model |
| Code review | **High** — nuance and severity classification degrade | Always use quality model |

---

## 6. Existing Design Context

### Advisor Integration (T04-advisor-integration-designs.md)

The advisor strategy research already explored cost-optimized model routing at the Wave level via generator-verifier patterns. Key insight: **the Wave-level gen-verify loop is an existing mechanism that achieves some benefits of L3 sub-decomposition without modifying the hierarchy.**

Gen-verify at Wave level:
```
Wave dispatches generator (budget model) → produces draft
Wave dispatches verifier (quality model) → evaluates quality
If FAIL: generator refines (round N+1)
Terminates: verifier PASS, max_rounds, or stagnation
```

This is functionally similar to "L3 sub-decomposition" but implemented at L2 with full DevolaFlow invariant compliance. The generator and verifier are separate L3 tasks with independent context, not sub-agents of a single L3.

### Relevant Feedback (feedback_for_v3.9.2.md)

The feedback explicitly requests investigation of L3 sub-decomposition ("是否面对 task 层级，还可以进一步细分并使用更轻量化的子 agent"), and asks about combining this with the advisor strategy for improved effectiveness. It also requests validation through full EvoBench evaluation.

### Selection Advisory Context (S04-selection-advisory.md)

The v3.9.0 selection advisory notes that `model_hint` (I-13) is fully implemented at the schema and selector level, and that "v4.0.0 should be reserved for a future release that introduces breaking changes (e.g., mandatory learnings, removed gate type aliases, or architectural changes)."

---

## 7. Platform Constraints Analysis

### Cursor IDE

| Capability | Status | Impact on L3 Sub-decomposition |
|---|---|---|
| `Task` tool with `model: "fast"` | Available | Enables budget-model routing for L3 tasks |
| `Task` tool with custom model names | NOT available | Limits to 2-tier (fast vs default), not 4-tier |
| Nested `Task` tool calls (agent spawns sub-agent) | Available | L3 *can technically* spawn sub-agents via Task tool |
| Sub-agent context isolation | Automatic per spawn | Each sub-agent gets fresh context — matches DevolaFlow's isolation model |
| Sub-agent timeout tracking | Available | Sub-tasks inherit or override parent timeout |
| Sub-agent result collection | Synchronous return | L3 gets sub-task result directly — no artifact-mediated communication needed |

### Architectural Implication

Cursor's Task tool already supports the mechanics of L3 sub-decomposition. The constraint is entirely within DevolaFlow's rules (P1 enforcement, hierarchy spec), not platform limitations.

However, Cursor's 2-tier model system (fast vs default) limits the value proposition. The full benefit of 4-tier model routing (quality/balanced/budget/inherit) requires platforms with finer-grained model selection (Claude Code, Codex).

---

## Proposed Architecture

### Approach 1: Complete model_hint → Platform Routing (Recommended for v4.0.0)

**No hierarchy change.** L3 remains a leaf node. The L2 Wave Agent reads `model_hint` from the resolved context profile and passes it to the platform's Task tool.

```
L2 Wave Agent:
  For each task in wave:
    1. resolve_model_hint(task_type, profile) → hint
    2. Map hint to platform parameter:
       - budget → model: "fast" (Cursor)
       - quality/balanced/inherit → default model
    3. Dispatch via Task(model=mapped_model, ...)
```

**Changes required:**

| Component | Change | Complexity |
|---|---|---|
| SKILL.md "Execution Protocol" section | Add model routing instruction to L2 dispatch step | Low (3-5 lines) |
| `context_profiles.yaml` | Already has model_hints — no change | None |
| `task_adaptive_selector.py` | Already has `resolve_model_hint()` — no change | None |
| `task-dispatch.schema.yaml` | Already has `model_hint` field — no change | None |
| New: `platform_routing.yaml` | Platform-specific hint→model mapping table | Low |
| SKILL.md hierarchy table | Add "Model Tier" column or note | Low (2-3 lines) |
| Tests | Validate hint→model mapping, EvoBench regression | Medium |

**P1 compliance:** Fully compliant. L3 is still a leaf worker. The model selection happens at L2 dispatch time.

### Approach 2: L3 Internal Decomposition (Experimental, v4.1.0+)

L3 gains a limited ability to spawn "micro-tasks" with strict guardrails.

```
L3 Task Agent (standard model):
  1. Assess task complexity
  2. IF simple sub-parts identifiable AND model_hint allows decomposition:
     a. Spawn micro-task(s) via Task(model="fast")
     b. Collect results
     c. Integrate into final output
  3. ELSE: execute directly (current behavior)
  4. Produce TaskReport (unchanged)
```

**Guardrails:**

| Guardrail | Rule | Enforcement |
|---|---|---|
| Max micro-tasks | ≤ 3 per L3 agent | Counter in dispatch template |
| Micro-task model | MUST be `budget` (fast) | Hardcoded in L3 decomposition logic |
| Micro-task scope | ≤ 1 file, ≤ 20 LOC | Validated before spawn |
| Token budget split | L3 retains ≥ 50% of its ~8K budget | Budget check before spawn |
| Micro-task timeout | ≤ 25% of L3 timeout | Derived from parent timeout |
| Error handling | Micro-task failure → L3 executes directly (fallback) | No escalation to L2 for micro-task failures |
| Reporting | Micro-tasks are invisible to L2 Wave | L3 produces a single unified TaskReport |

**P1 implications:** This is the contentious point. Strictly read, P1 says "Only Layer 3 Task Agents execute actual work." If L3 spawns micro-tasks, the micro-tasks are also doing work — they are effectively L3-tier agents. The P1 violation is contained if we define micro-tasks as "internal implementation details of L3" rather than "delegated work units." The micro-tasks don't report to L2; they report to their parent L3.

**Hierarchy modification:**

```
Current:    L0 → L1 → L2 → L3 (leaf)
Proposed:   L0 → L1 → L2 → L3 → [L3.µ] (micro-task, invisible above L3)
```

L3.µ micro-tasks are NOT new hierarchy levels — they are implementation details of L3. The Wave Agent does not know about them. The Stage Agent does not know about them. Escalation from L3.µ goes to L3 (which either handles it or escalates normally to L2).

---

## Risk Assessment

### Approach 1 Risks (Model Routing)

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| Budget model produces low-quality output for misclassified task | Medium | Low | Acceptance criteria validation at Wave level; gen-verify fallback |
| Platform doesn't support model selection | Low | Medium | Graceful degradation: if no `model` param, all tasks use default |
| Over-aggressive budget routing | Medium | Low | Conservative default: only explicitly overridden task types use budget |
| EvoBench regression | Medium | Low | Run full benchmark suite; compare composite scores |

### Approach 2 Risks (L3 Sub-decomposition)

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| P1 invariant erosion | **High** | Medium | Strict guardrails; micro-tasks invisible to L2+; opt-in only |
| Context fragmentation | High | Medium | Enforce 50% budget retention; minimize micro-task context injection |
| Error escalation complexity | Medium | Medium | Micro-task failure → L3 fallback (no escalation to L2) |
| Debugging difficulty | Medium | High | Micro-tasks not in execution log → hard to trace failures |
| Rationalization creep | **High** | Medium | Agents may over-decompose, spawning micro-tasks for tasks they should do directly |
| Timeout budget fragmentation | Medium | Low | Cap micro-task timeout at 25% of parent |
| SKILL.md line budget | Low | Medium | Approach 2 needs ~15-20 lines in SKILL.md (447/500 currently, 53 headroom) |

### Combined Risk Matrix

| Approach | Overall Risk | Reward (Cost Savings) | Reward (Speed) | Recommendation |
|---|---|---|---|---|
| **Approach 1** | **Low** | 35-45% workflow cost reduction | 20-35% time reduction | **v4.0.0 — IMPLEMENT** |
| **Approach 2** | **Medium-High** | Additional 10-20% on top of Approach 1 | Additional 10-15% | **v4.1.0 — EXPERIMENT** |
| **Combined** | **Medium** | 45-60% total cost reduction | 30-45% time reduction | Staged rollout |

---

## Quantitative Impact Estimates

### Cost Model (per full-pipeline workflow, ~20 tasks)

| Scenario | Quality Tasks | Balanced Tasks | Budget Tasks | Est. Total Cost | vs Baseline |
|---|---|---|---|---|---|
| **Baseline** (all default) | 20 × $0.20 | — | — | ~$4.00 | — |
| **Approach 1** (model routing) | 4 × $0.20 | 9 × $0.10 | 7 × $0.02 | ~$1.84 | **-54%** |
| **Approach 2** (+ L3 sub-decomp) | 4 × $0.20 | 6 × $0.10 | 10 × $0.02 | ~$1.60 | **-60%** |

*Note: Cost estimates are illustrative. Actual costs depend on token volumes, model pricing, and task complexity distribution.*

### Latency Model (per full-pipeline workflow)

| Scenario | Avg Task Latency | Parallelism Benefit | Est. Wall-Clock | vs Baseline |
|---|---|---|---|---|
| **Baseline** | ~60s/task | Limited by wave structure | ~15-25 min | — |
| **Approach 1** | ~35s/task (weighted avg) | Same wave structure | ~10-18 min | **-25-35%** |
| **Approach 2** | ~30s/task (weighted avg) | Some intra-task parallelism | ~8-15 min | **-35-45%** |

### Quality Impact (estimated from model capability differences)

| Metric | Baseline | Approach 1 | Approach 2 |
|---|---|---|---|
| Gate pass rate (first attempt) | ~70% | ~65-70% | ~60-65% |
| Convergence rounds needed | 1.5 avg | 1.5-1.8 avg | 1.7-2.0 avg |
| Task retry rate | ~10% | ~12-15% | ~15-20% |
| Net quality (after convergence) | Baseline | **Equivalent** (convergence compensates) | **Slight degradation risk** |

The key insight: Approach 1's potential quality dip on budget tasks is compensated by the existing convergence loop mechanism. Budget tasks that fail review get retried — potentially with a higher model tier. Approach 2's additional quality risk from context fragmentation is harder to compensate.

---

## Advisor Strategy Synergy

The feedback specifically asks about combining sub-agent decomposition with the advisor strategy. Analysis:

### Advisor + Model Routing (Approach 1)

The advisor tool (I-16, I-17) can enhance model routing by:

1. **Borderline detection**: When a gate score is near the threshold, the advisor can recommend upgrading specific tasks from `budget` to `balanced` on retry
2. **Complexity estimation**: The advisor can assess task complexity before dispatch and override `budget` → `balanced` for deceptively complex tasks
3. **Post-hoc quality check**: The advisor can evaluate whether budget-model outputs meet quality standards without running the full gate

This synergy is **high-value and low-risk** — it uses existing infrastructure (advisor already implemented in v3.9.0) to make model routing more intelligent.

### Advisor + L3 Sub-decomposition (Approach 2)

Less clear benefit. The advisor operates at L1 gate level, not at L3 internal level. L3 micro-tasks are invisible to the advisor. The advisor could potentially guide L3's decomposition decision ("this task is too complex to sub-decompose"), but this would require extending the advisor to L3 scope — a significant change.

---

## Recommendation for v4.0.0

### Primary Recommendation: Implement Approach 1 (Model Routing)

**Scope:**
1. Create `platform_routing.yaml` with hint→model mapping per platform
2. Update SKILL.md "Execution Protocol" to instruct L2 to read `model_hint` and map to platform `model` parameter
3. Update SKILL.md hierarchy table to note model tier column
4. Add EvoBench scenarios specifically testing model-routed dispatches
5. Wire advisor borderline detection to recommend model tier upgrades on retry
6. Run full EvoBench evaluation to validate no regression

**This is NOT a breaking change** — `model_hint: inherit` is the default, so all existing workflows continue unchanged. The change is purely additive: profiles that already define `model_hints.overrides` will now see those hints translated to actual platform model selection.

**v4.0.0 justification:** This completes the model_hint pipeline end-to-end (schema → selector → dispatch → platform routing), which was partially built in v3.9.0. Combined with other v4.0 changes (caveman compression validation, workflow optimization), it represents a significant capability upgrade.

### Secondary Recommendation: Defer Approach 2 to v4.1.0+

**Rationale:**
- Approach 1 captures ~80% of the cost/speed benefit with ~20% of the risk
- Approach 2 requires modifying the P1 invariant, which is architecturally significant
- Approach 2's incremental benefit (additional 10-20% cost reduction) doesn't justify the complexity for v4.0.0
- EvoBench validation of Approach 2 requires new scenarios (micro-task quality, context fragmentation) that don't exist yet

**Pre-requisites for Approach 2:**
1. Approach 1 deployed and validated in production
2. Quantitative data on budget-model task quality from Approach 1
3. New EvoBench scenarios: `micro_task_quality`, `context_fragmentation`, `l3_decomposition_overhead`
4. Design doc for L3.µ micro-task protocol
5. SKILL.md line budget analysis (needs ~15-20 lines; 53 lines available as of v3.9.2)

---

## Appendix A: Affected Files Summary

| File | Approach 1 Impact | Approach 2 Impact |
|---|---|---|
| `workflow-system/agent/SKILL.md` | +3-5 lines (dispatch protocol) | +15-20 lines (micro-task protocol) |
| `workflow-system/agent/context_profiles.yaml` | No change (already has model_hints) | Add micro-task budget split config |
| `src/devolaflow/task_adaptive_selector.py` | No change (already resolves hints) | Add micro-task decomposition heuristic |
| `schemas/task-dispatch.schema.yaml` | No change (already has model_hint) | Add `allow_decomposition: bool` field |
| `workflow-system/agent/references/agent-hierarchy.md` | No change | Modify L3 MUST NOT to "MUST NOT spawn sub-agents EXCEPT micro-tasks" |
| NEW: `platform_routing.yaml` or equivalent | Platform-specific mapping table | Extended with micro-task constraints |
| `benchmarks/devolaflow_context/scenarios/` | +2-3 model routing scenarios | +3-4 micro-task scenarios |

## Appendix B: EvoBench Validation Plan

### For Approach 1 (v4.0.0)

| Test | What It Validates | Pass Criterion |
|---|---|---|
| Model hint resolution regression | Existing 22 scenarios still pass | 22/22 pass, no score regression |
| Budget-routed hotfix scenario | Budget model on simple impl task | Composite ≥ 80, noise ≤ 0.1 |
| Quality-routed review scenario | Quality model on review task | Composite ≥ 85, relevance ≥ 0.85 |
| Mixed-model full-pipeline | Tasks routed to appropriate tiers | Composite ≥ 80, cost reduction measurable |

### For Approach 2 (v4.1.0+)

| Test | What It Validates | Pass Criterion |
|---|---|---|
| Micro-task context sufficiency | Sub-agents have enough context to produce quality output | Sub-task pass rate ≥ 80% |
| Context fragmentation impact | L3 budget split doesn't degrade parent's orchestration ability | Parent L3 retains coherent output |
| Fallback correctness | Micro-task failure triggers L3 direct execution | 100% fallback success |
| End-to-end quality | Full pipeline with micro-tasks vs without | Gate pass rate within 5% of baseline |

---

## Appendix C: Comparison with Alternative Approaches

| Approach | Description | Cost Savings | Speed | Quality Risk | Complexity | Verdict |
|---|---|---|---|---|---|---|
| **Status quo** | All L3 tasks use default model | 0% | baseline | none | none | Safe but expensive |
| **Approach 1** (model routing) | L2 routes L3 to tier based on hint | 35-55% | +25-35% | low | low | **Recommended** |
| **Approach 2** (L3 sub-decomp) | L3 spawns micro-tasks on fast model | 45-60% | +35-45% | medium | high | Defer to v4.1.0 |
| **Wave-level gen-verify** | L2 dispatches gen(budget)+verify(quality) | 20-30% | +10-20% | low | medium | Already available (v3.9.0) |
| **Deeper hierarchy (L4)** | Add formal L4 layer below L3 | 40-55% | +30-40% | medium | **very high** | Not recommended |
| **Prompt compression only** | Reduce L3 context via caveman compression | 10-20% | +5-10% | low-medium | low | Orthogonal; combine with Approach 1 |
