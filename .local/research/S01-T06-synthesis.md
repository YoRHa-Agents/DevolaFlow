---
task_id: S01-T06
title: "Unified Synthesis: W01 Research Reports → Comparison Matrix & Gap Analysis"
team: Research
status: complete
predecessor_reports: 6
sources_synthesized: 23
devolaflow_version_context: "3.8.0"
last_updated: "2026-04-11"
---

# S01-T06 — Unified Research Synthesis & DevolaFlow Gap Analysis

## Executive Summary

This synthesis consolidates findings from 6 predecessor research reports covering
23 distinct external sources (repos, papers, APIs, patterns). It produces: a
unified comparison matrix, gap classification against DevolaFlow v3.8.0, cross-repo
pattern convergence analysis, ranked integration candidates, and self-update
workflow inputs.

**Key findings:**
- 5 patterns are **already addressed** in DevolaFlow v3.7.0–v3.8.0
- 7 gaps classified **high-priority** (high relevance, achievable effort)
- 5 cross-repo meta-patterns show strong convergence (4+ sources each)
- Top 3 integration candidates by impact/effort: rationalization tables,
  lean dispatch compression rules, advisor tool at L3/L1
- 4 repos warrant ongoing tracking for self-update triggers

---

## 1. Unified Comparison Matrix

### 1A. Primary Sources (From T01–T04 Deep-Dives)

| # | Source | Report | Relevance | Key Pattern | DevolaFlow Gap Addressed | Integration Effort | Token Impact | Quality Impact | Priority |
|---|--------|--------|-----------|-------------|--------------------------|-------------------|-------------|---------------|----------|
| 1 | **caveman** | T01 | 4/5 | Output token compression via drop/preserve lists; validate-then-fix loop; intensity levels | CO-1 lean messages lack explicit drop/preserve rules; no compression intensity tiers | Low | -65% output tokens (benchmarked) | Neutral (preserves accuracy) | High |
| 2 | **superpowers** | T01 | 5/5 | Iron Laws, rationalization tables, hard gates; two-stage review; typed status protocol; CSO skill descriptions; model-tiered dispatch | SKILL.md lacks enforcement patterns (levels 3-5 of enforcement ladder); single-pass gate; free-form StatusReport status; no model tiering | Low–High (varies by idea) | Neutral to -10% (progressive disclosure) | +10-20pp (enforcement patterns) | High |
| 3 | **get-shit-done (GSD)** | T02 | 4/5 | 4-type gate taxonomy (pre-flight/revision/escalation/abort); model profiles; prompt injection defense; agent completion contracts; context window awareness | Gate routing on failure is ambiguous; no model profiles; no prompt injection defense; no completion contracts | Medium | Neutral | High (clearer failure handling) | High |
| 4 | **edict (三省六部)** | T02 | 3/5 | Mandatory pre-execution review (Menxia); state machine enforcement; permission matrix; 4-stage progressive recovery; event-driven audit trail | No mandatory pre-execution review; no strict inter-agent permission matrix; binary escalation (not progressive); no event audit log | Medium–High | Neutral | High (prevents bad plans reaching execution) | Medium |
| 5 | **gstack** | T03 | 4/5 | Per-skill tool ACLs; operational learnings JSONL; proactive skill suggestion; cross-model review; `benefits-from` dependency tracking; sprint-sequential routing | Fixed tool sets per team; no cross-session learning; no proactive suggestion; no cross-model review; no artifact dependency tracking | Low–Medium | -5-10% (targeted context loading) | Medium-High (accumulated knowledge) | High |
| 6 | **Karpathy LLM Wiki** | T03 | 3/5 | Persistent wiki (ingest/query/lint); compounding knowledge; index.md catalog; contradiction detection; schema co-evolution | Static knowledge files; no dynamic ingestion; no contradiction detection; no central knowledge index; no lint pass | Medium–High | Neutral | High (compounding knowledge over time) | Medium |
| 7 | **Anthropic Advisor Tool** | T04 | 5/5 | Bottom-up escalation within single API request; Sonnet+Opus advisor at L3/L1; max_uses budgeting; $0.04-0.05/call; 7-33x ROI | L3 escalation is heavyweight (full ExceptionEscalation chain); borderline gate decisions lack secondary opinion; no cost-tiered reasoning | Medium | +$0.15-0.30/workflow | +2.7pp SWE-bench; prevents wasted convergence rounds | High |

### 1B. Expanded Discoveries (From T05)

| # | Source | Report | Relevance | Key Pattern | DevolaFlow Gap Addressed | Integration Effort | Token Impact | Quality Impact | Priority |
|---|--------|--------|-----------|-------------|--------------------------|-------------------|-------------|---------------|----------|
| 8 | **Google Scion** | T05-D1 | 4/5 | Infrastructure-level agent isolation via git worktrees + containers per agent | P2/P5 context isolation is prompt-level only; parallel Wave execution has file conflict risk | Medium | Neutral | High (eliminates file conflicts in parallel waves) | Medium |
| 9 | **SkillRouter** | T05-D2 | 4/5 | Retrieve-and-rerank skill selection (1.2B model); full-text signal critical (hiding impl text = -31-44pp accuracy) | `task_adaptive_selector.py` uses hint-based matching; will degrade as profile count grows | Medium | Neutral | +31-44pp routing accuracy (vs metadata-only) | Medium |
| 10 | **vexp** | T05-D3 | 5/5 | AST dependency graph + centrality ranking for context selection; 65% fewer tokens, +14pp success rate | Context profiles use static section-level budgets; no code-graph-aware context injection | High | -65% tokens (benchmarked on FastAPI) | +14pp task success rate | High |
| 11 | **Self-Improving System** | T05-D4 | 4/5 | Six-component quality loop; "Ralph Loop" knowledge flywheel; post-workflow rule/skill auto-update | No self-improvement feedback loop; completed workflows don't update rules/skills/docs | Medium | Neutral | High (compounding quality improvement) | High |
| 12 | **Agent Skills Security** | T05-D5 | 4/5 | Four-tier trust model (first-party→verified→community→unverified); provenance-based permissions; 26.1% community skills have vulnerabilities | No skill trust levels; no provenance tracking; no vulnerability scanning for SKILL.md/adapter content | Low | Neutral | Medium (security hardening) | Medium |
| 13 | **PrimeLocus/Hydra** | T05-D6 | 4/5 | Strength-based model routing; multi-round deliberation (propose→critique→refine→implement); budget tracking per agent | Single-model per task; no model-strength routing; no multi-model deliberation workflow | Medium | Neutral to +15% | High (exploits model strengths) | Medium |
| 14 | **Ruflo** | T05-D7 | 4/5 | Multi-stage compression pipeline (95-98% target); swarm-aware budgets; intent-based filtering; cross-agent knowledge search via FTS5 | No progressive context throttling; no intent-based compression; no cross-agent knowledge search | High | -40-95% (ambitious targets) | Medium (prevents context depletion) | Low |
| 15 | **ChristopherA Bootstrap Seed** | T05-D8 | 3/5 | Emergent config via reflect→triage→cascade; seeded vs emergent separation; ~1400 token bootstrap | No mechanism for configuration self-evolution from operational experience | Medium | Neutral | Medium (project-specific adaptation) | Low |
| 16 | **Spring AI Agent Skills** | T05-D9 | 3/5 | Three-stage progressive disclosure (discovery→activation→execution); vendor-agnostic portability | DevolaFlow loads full SKILL.md rather than progressively disclosing sections | Low | -20-30% initial load | Low (validates existing approach) | Low |

### 1C. Orchestration Patterns (From T02 Prior Research)

| # | Source | Report | Relevance | Key Pattern | DevolaFlow Gap Addressed | Integration Effort | Token Impact | Quality Impact | Priority |
|---|--------|--------|-----------|-------------|--------------------------|-------------------|-------------|---------------|----------|
| 17 | **Anthropic 5 Coordination Patterns** | T02 | 5/5 | Generator-verifier, orchestrator-subagent, agent teams, message bus, shared state; context-centric decomposition | Only orchestrator-subagent pattern; no shared state for research; no context-centric decomposition principle | Medium | Varies by pattern | High (right pattern → right problem) | already-addressed (v3.7.0 wave coordination modes) |
| 18 | **AdaptOrch** | T02 | 4/5 | Task-adaptive topology selection; O(\|V\|+\|E\|) routing; 12-23% improvement over static baselines | Fixed topology per workflow type | Medium | Neutral | +12-23% on diverse workflows | already-addressed (v3.7.0 DAG analysis) |
| 19 | **Evaluator-Optimizer** | T02 | 4/5 | Task-level generate→evaluate→refine loop; structured feedback; bounded termination | Convergence is stage-level only; task-level fix-verify requires full convergence round | Low | +2-3x per loop iteration | +10-20pp code pass rate | already-addressed (v3.7.0 generator_verifier mode) |
| 20 | **Deterministic Hooks** | T02 | 4/5 | System-level lifecycle enforcement; 100% compliance vs 70-90% prompt-based; PreToolUse/PostToolUse/Stop events | All enforcement was prompt-based | Medium | Neutral | +10-30pp compliance | already-addressed (v3.8.0 lifecycle hooks) |
| 21 | **Reflection / Self-Critique** | T02 | 3/5 | Intra-task generate→reflect→refine; producer-critic separation; 10-20pp improvement | No intra-task reflection mechanism | Low | +10-20% per task | +10-20pp code pass rate | Medium |
| 22 | **Context Engineering** | T02 | 4/5 | Write/Select/Compress/Isolate operations; adaptive allocation; context poisoning defense; predecessor validation | Static budgets; no compaction; no poisoning defense; predecessor summaries are fixed-format | Medium | -20-50% (optimization) | High (prevents degradation) | Medium |
| 23 | **AgentOrchestra TEA** | T02 | 3/5 | Dynamic tool creation via MCP; tool retrieval and reuse; TEA protocol | Fixed tool sets per team; no tool reuse across tasks | High | +15-25% (tool mgmt overhead) | Medium (progressive capability) | Low |

---

## 2. Gap Classification

### 2.1 Already-Addressed (DevolaFlow v3.7.0–v3.8.0 handles this)

| Gap | Addressed By | Version | Evidence |
|-----|-------------|---------|----------|
| Deterministic lifecycle enforcement | 3 hooks: `validate_dispatch`, `check_file_ownership`, `test_on_complete` | v3.8.0 | CHANGELOG: "100% compliance vs 70-90% prompt-based" |
| Generator-verifier coordination mode | Wave auto-selects `generator_verifier` mode via DAG analysis | v3.7.0 | CHANGELOG: "tight generate→evaluate→refine loops within waves" |
| Adaptive topology selection | O(\|V\|+\|E\|) DAG analysis before wave dispatch; parallel/sequential/hybrid modes | v3.7.0 | CHANGELOG: "L2 Wave auto-selects coordination mode" |
| P1 dispatcher-not-implementer enforcement | Agent Mode Execution Protocol (27-line block); tool permissions; P1 Self-Check | v3.6.0 | CHANGELOG: "Explicit L0 role assignment...tool permissions" |
| Task-adaptive context selection | 16 context profiles with section-level priority (critical/important/supplementary/skip) | v2.2.0 + v3.3.0 | CHANGELOG: "Context profiles per task type" |

### 2.2 High-Priority (Relevance 4-5, Low-Medium Effort, Addresses Real Weakness)

| # | Gap | Source(s) | Why High Priority | Classification Rationale |
|---|-----|-----------|-------------------|--------------------------|
| H1 | **Rationalization prevention tables** in SKILL.md | superpowers | Proven effective at countering agent rationalizations for skipping P1/P4; low effort (add tables to existing SKILL.md) | Superpowers testing showed direct improvement; DevolaFlow enforcement ladder has gap at levels 3-5 |
| H2 | **Lean dispatch compression rules** (explicit drop/preserve lists) | caveman | Directly implements CO-1/CO-2 with deterministic rules; low effort (extend lean-dispatch.yaml) | caveman benchmarked 65% output reduction; DevolaFlow lean schemas lack explicit compression rules |
| H3 | **Advisor tool integration at L3 Task + L1 Gate** | Anthropic advisor | Bottom-up escalation fills gap between prompt-based decisions and full ExceptionEscalation; benchmarked +2.7pp quality at -11.9% cost | 7-33x ROI per workflow; reduces convergence round waste |
| H4 | **Typed subagent status protocol** (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED) | superpowers | Replaces free-form status in StatusReport with deterministic routing enum; medium effort | Directly maps to P4 classified response (retry/escalate/abort) |
| H5 | **Operational learnings persistence** (per-project JSONL) | gstack, Karpathy wiki, Self-Improving System | Addresses DevolaFlow's biggest structural gap: no cross-session knowledge accumulation; medium effort | 4 sources converge on this pattern (highest convergence score) |
| H6 | **CSO-inspired skill description format** | superpowers | Prevents agents from shortcutting SKILL.md by following description instead of reading full content; low effort | Testing proved description-as-workflow-summary causes shortcutting |
| H7 | **Self-improving feedback loop** (post-workflow → rule/skill update) | Self-Improving System, gstack, Bootstrap Seed | Enables DevolaFlow quality to compound over time; medium effort | 3 sources converge; DevolaFlow has EvoBench feedback but no automated rule/skill update cycle |

### 2.3 Medium-Priority (Relevance 3-4, Medium Effort)

| # | Gap | Source(s) | Classification Rationale |
|---|-----|-----------|--------------------------|
| M1 | **4-type gate taxonomy** (pre-flight/revision/escalation/abort routing) | GSD | DevolaFlow's gate evaluates pass/fail but routing on failure is ambiguous; medium effort |
| M2 | **Model profiles per agent role** | GSD, superpowers, Hydra | 3 sources converge; enables cost optimization; medium effort to add model_hint to dispatch |
| M3 | **Mandatory pre-execution review** (Menxia pattern) | edict | Catches bad plans before execution; medium effort; partially addressed by `validate_dispatch` hook |
| M4 | **SkillRouter semantic profile matching** | SkillRouter | Improves routing accuracy +31-44pp over metadata-only; medium effort; becomes critical as profiles grow |
| M5 | **Scion git worktree isolation** for parallel waves | Google Scion, Hydra | Infrastructure-level isolation stronger than prompt-level P2; medium effort |
| M6 | **Skills security governance** (trust tiers + vulnerability scanning) | Agent Skills Security paper | 26.1% community skills have vulnerabilities; low effort for trust_level field; medium for scanning |
| M7 | **Two-stage gate verification** (spec compliance → code quality) | superpowers | Prevents "well-tested but wrong scope" from passing; medium effort to extend gate mechanism |
| M8 | **Prompt injection defense hooks** | GSD | Multi-agent YAML messages are injection vectors; low-medium effort to port pattern |
| M9 | **Cross-model gate validation** (dual voices for borderline decisions) | gstack, Hydra | Borderline gate scores get secondary opinion; medium effort |
| M10 | **Intra-task self-review** (reflection pattern) | Reflection/Self-Critique (T02) | Lightweight quality improvement within task context budget; low effort |
| M11 | **Context poisoning defense** (predecessor validation) | Context Engineering (T02) | Prevents hallucinated predecessor summaries from propagating; medium effort |

### 2.4 Low-Priority (Nice-to-Have, High Effort or Niche)

| # | Gap | Source(s) | Classification Rationale |
|---|-----|-----------|--------------------------|
| L1 | **vexp-style graph-based context selection** | vexp | Highest potential impact (+14pp, -65% tokens) but highest effort (AST parsing infrastructure) |
| L2 | **Progressive failure recovery** (retry→escalate L1→escalate L2→rollback) | edict | More resilient than binary escalation; high effort to add snapshot/restore logic |
| L3 | **Ruflo context compression pipeline** | Ruflo | Addresses long-session depletion; high effort; still at proposal stage |
| L4 | **Tool recipe catalog** (cross-task reuse) | AgentOrchestra | Progressive capability; high effort; low urgency for current workflow types |
| L5 | **Event-driven state transitions + audit trail** | edict | Improves observability but requires infrastructure change alongside existing artifact-based system |
| L6 | **Bootstrap self-evolution** (reflect→triage→cascade config) | ChristopherA | Interesting for per-project customization; medium effort; niche applicability |
| L7 | **Spring AI progressive disclosure** for SKILL.md | Spring AI | Validates existing approach; low effort but low impact (SKILL.md is 430 lines, within budget) |
| L8 | **Proactive task suggestion** via execution pattern analysis | gstack | Timeline tracking and pattern prediction; medium effort; requires multiple workflow executions for value |

### 2.5 Not-Applicable (Doesn't Fit DevolaFlow Architecture)

| Gap | Source | Reason |
|-----|--------|--------|
| Redis Streams EventBus | edict | DevolaFlow is artifact-based (P5); event-driven communication is a fundamentally different paradigm |
| Real-time Kanban dashboard (10 panels) | edict | DevolaFlow is a meta-framework consumed by AI coding agents, not a web application with a UI |
| Dynamic runtime tool creation via MCP | AgentOrchestra | DevolaFlow operates within host tool (Cursor/Codex/etc.) tool ecosystems; cannot create new tools at runtime |
| Per-agent hot-swap LLM via dashboard | edict | No dashboard; model selection is dispatch-time configuration, not runtime UI |
| Voice triggers for skill activation | gstack | DevolaFlow is invoked via text prompts in coding IDEs; no voice interface |

---

## 3. Cross-Repo Pattern Synthesis

### 3.1 Lean Messaging / Token Compression

**Convergence: HIGH (6 sources)**

| Source | Implementation | Technique |
|--------|---------------|-----------|
| caveman | Drop/preserve lists, intensity levels (lite/full/ultra) | Deterministic compression-by-rule |
| superpowers | Progressive disclosure, cross-reference by name (not @-load) | Lazy loading of skill content |
| Ruflo | Multi-stage pipeline (size check → intent filter → smart snippet) | Intent-based compression filtering |
| vexp | AST dependency graph + centrality ranking | Code-structure-aware context selection |
| Context Engineering (T02) | Write/Select/Compress/Isolate operations | Systematic context optimization framework |
| Anthropic advisor | Conciseness prompting (-35-45% advisor output) | Prompt-level output compression |

**DevolaFlow status:** CO-1 (lean format) and CO-2 (verbatim extraction) rules exist. Lean message schemas (`lean-dispatch.yaml`, `lean-report.yaml`) are defined. **Gap:** No explicit drop/preserve lists in schemas; no compression intensity tiers; no code-graph-aware selection.

**Confidence:** Very High — 6 independent sources converge on the principle that deterministic compression rules outperform generic terseness instructions.

### 3.2 Gate Enforcement / Mandatory Review

**Convergence: HIGH (5 sources)**

| Source | Implementation | Technique |
|--------|---------------|-----------|
| superpowers | Two-stage review (spec compliance → code quality); iron laws; hard gates | Behavioral enforcement with rationalization countermeasures |
| GSD | 4-type gate taxonomy (pre-flight/revision/escalation/abort) | Behavioral classification of gate outcomes |
| edict | Menxia mandatory institutional review (approve/reject binary) | Architectural enforcement (not optional) |
| Agent Skills Security | Four-tier trust model with provenance-based gate transitions | Graduated deployment capabilities |
| Deterministic Hooks (T02) | System-level lifecycle enforcement at 100% compliance | Code-enforced, outside LLM reasoning chain |

**DevolaFlow status:** Gate mechanism (v2.2.0) with composite scoring. Lifecycle hooks (v3.8.0) for deterministic enforcement. **Gap:** Single-pass gate (not two-stage); no gate type taxonomy for failure routing; no pre-execution mandatory review; no skill trust/provenance gating.

**Confidence:** Very High — 5 sources independently arrived at "mandatory quality gates that cannot be bypassed."

### 3.3 Knowledge Persistence / Self-Update

**Convergence: HIGH (4 sources)**

| Source | Implementation | Technique |
|--------|---------------|-----------|
| gstack | Learnings JSONL (`{skill, type, key, insight, confidence}`); timeline tracking; prune for stale entries | Per-session auto-capture of operational findings |
| Karpathy wiki | Persistent markdown wiki with ingest/query/lint operations | Compounding knowledge artifact |
| Self-Improving System | Six-component quality loop; "Ralph Loop" flywheel | Post-workflow rule/skill auto-update |
| ChristopherA Bootstrap Seed | Reflect→triage→cascade loop; seeded vs emergent config separation | Emergent configuration from operational pressure |

**DevolaFlow status:** Static knowledge files (`principle-mapping.md`, `code-rules-mapping.md`). EvoBench provides benchmark feedback. **Gap:** No cross-session knowledge accumulation; no dynamic ingestion of execution findings; no contradiction detection; no automated rule/skill update from experience.

**Confidence:** High — 4 sources converge on "systems that learn from their own execution get better over time." This is DevolaFlow's largest structural gap.

### 3.4 Role Specialization / Tool Routing

**Convergence: VERY HIGH (7 sources)**

| Source | Implementation | Technique |
|--------|---------------|-----------|
| gstack | Per-skill `allowed-tools` frontmatter; 23+ specialists | Fine-grained tool ACLs per role |
| superpowers | Model tiering (cheap→standard→capable by task complexity) | Cost-aware model selection at dispatch |
| GSD | 5 model profiles (quality/balanced/budget/adaptive/inherit) | Per-agent model override |
| edict | `allowAgents` permission matrix; per-agent LLM selection | Strict inter-agent communication control |
| Hydra | Strength-based routing (Claude=architecture, Gemini=critique, Codex=implementation) | Model-strength exploitation |
| SkillRouter | 1.2B retrieve-and-rerank pipeline; 74.0% Hit@1 at 80K skills | Semantic skill selection at scale |
| AgentOrchestra | TEA protocol; dynamic tool creation and reuse | Runtime tool evolution |

**DevolaFlow status:** 5 fixed team roles (Research, Design, Implement, Test, Review) with team-level tool sets. `task_adaptive_selector.py` uses hint-based profile matching. **Gap:** No per-task tool ACLs; no model tiering at dispatch; hint-based matching degrades at scale; no inter-agent permission matrix.

**Confidence:** Very High — 7 independent sources converge. This is the most universally addressed pattern across the research corpus.

### 3.5 Context Optimization / Adaptive Budgets

**Convergence: HIGH (6 sources)**

| Source | Implementation | Technique |
|--------|---------------|-----------|
| caveman | Intensity-tiered compression (lite/full/ultra) | Configurable compression aggressiveness |
| vexp | AST dependency graph + centrality ranking; 65% fewer tokens | Code-structure-aware context selection |
| Ruflo | Swarm-aware per-agent budgets; progressive throttling | Dynamic budget allocation across agents |
| Context Engineering (T02) | Adaptive allocation by task properties; context poisoning defense | Relevance-based section scoring |
| SkillRouter | Full-text signal critical for routing accuracy (-31-44pp without) | Full implementation text as routing signal |
| Spring AI | Three-stage progressive disclosure (discovery→activation→execution) | Lazy loading by need |

**DevolaFlow status:** 16 context profiles with per-task-type section priorities and token budgets. CO-3 (token budgets), CO-6 (section relevance). **Gap:** Static budgets (not adaptive to task complexity); no code-graph-aware selection; no progressive throttling; no progressive disclosure of SKILL.md.

**Confidence:** High — 6 sources converge on "static budgets are insufficient; context selection must be dynamic and task-aware."

---

## 4. Top 15 Integration Candidates

Ranked by impact/effort ratio. Each includes all required fields.

### Rank 1: Rationalization Prevention Tables

- **Description:** Add `| Excuse | Reality |` tables to SKILL.md for P1/P4 violations
- **Source repo(s):** superpowers
- **DevolaFlow component:** SKILL.md, MVP-SKILL.md
- **Estimated EvoBench impact:** Positive (improves enforcement compliance quality)
- **Confidence:** High (single source, but empirically tested in superpowers)
- **Effort:** Low (~0.5 day)
- **Rationale:** Fills enforcement ladder gap (levels 3-5). Pre-counters specific agent rationalizations like "This is just one file" (P1) and "One more attempt" (P4). Proven effective in superpowers testing.

### Rank 2: Lean Dispatch Compression Rules

- **Description:** Add explicit drop/preserve lists to lean-dispatch.yaml and lean-report.yaml schemas
- **Source repo(s):** caveman
- **DevolaFlow component:** `schemas/lean-dispatch.yaml`, `schemas/lean-report.yaml`
- **Estimated EvoBench impact:** Positive (reduces noise ratio in context injection)
- **Confidence:** High (caveman benchmarked 65% output reduction; deterministic rules)
- **Effort:** Low (~0.5 day)
- **Rationale:** Directly implements CO-1. Define drop list (articles, filler, pleasantries, hedging) and preserve list (paths, hashes, metrics, error messages — already CO-2 mandated). Zero ambiguity.

### Rank 3: Advisor Tool — L3 Task Agent Integration

- **Description:** Enable Sonnet executor + Opus advisor for complex L3 tasks; `max_uses: 3`, `conversation_budget: 6`
- **Source repo(s):** Anthropic advisor tool
- **DevolaFlow component:** `context_profiles.yaml` (new `advisor` section), engine dispatch code, SKILL.md (system prompt extension)
- **Estimated EvoBench impact:** Positive (+2.7pp quality on SWE-bench equivalent tasks)
- **Confidence:** High (Anthropic benchmark data; empirical cost model)
- **Effort:** Medium (~2 days)
- **Rationale:** Highest-volume integration point. Near-Opus quality at Sonnet + ~$0.10/task. Reduces ExceptionEscalation frequency. 7-33x ROI per workflow.

### Rank 4: Advisor Tool — L1 Gate Evaluation

- **Description:** Enable advisor for borderline gate evaluations (composite score within ±5% of threshold); `max_uses: 1`
- **Source repo(s):** Anthropic advisor tool
- **DevolaFlow component:** `gate/scorer.py`, `context_profiles.yaml`
- **Estimated EvoBench impact:** Positive (eliminates borderline gate misjudgments)
- **Confidence:** High (single $0.05 call prevents $1-5 in wasted convergence rounds; ~100x per-call ROI)
- **Effort:** Low (~1 day)
- **Rationale:** Most cost-effective advisor use. ~20% of gate evaluations are borderline.

### Rank 5: Typed Subagent Status Protocol

- **Description:** Replace free-form StatusReport status with enum: DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED
- **Source repo(s):** superpowers
- **DevolaFlow component:** `schemas/lean-report.yaml`, StatusReport schema, SKILL.md dispatch protocol
- **Estimated EvoBench impact:** Positive (cleaner routing reduces noise)
- **Confidence:** High (maps directly to P4 classified response)
- **Effort:** Medium (~1 day)
- **Rationale:** Enables deterministic routing: DONE → proceed, NEEDS_CONTEXT → provide + retry, BLOCKED → escalate. Eliminates ambiguous status interpretation.

### Rank 6: CSO-Inspired Skill Description Format

- **Description:** SKILL.md description says WHEN to use, never summarizes WHAT it does
- **Source repo(s):** superpowers
- **DevolaFlow component:** SKILL.md (frontmatter `description`), SF-2 rule, MVP-SKILL.md
- **Estimated EvoBench impact:** Neutral (description format, not content)
- **Confidence:** High (superpowers testing proved workflow-summarizing descriptions cause shortcutting)
- **Effort:** Low (~0.5 day)
- **Rationale:** Prevents agents from following SKILL.md description as a compressed workflow instead of reading full content. One-line change to SF-2 rule.

### Rank 7: Operational Learnings Persistence

- **Description:** Per-project JSONL file capturing convergence loop findings, recurring violations, project-specific patterns
- **Source repo(s):** gstack, Karpathy wiki, Self-Improving System, Bootstrap Seed
- **DevolaFlow component:** New `workflow-system/agent/knowledge/learnings/` directory, Review Agent post-convergence hook
- **Estimated EvoBench impact:** Positive (over time, as learnings accumulate)
- **Confidence:** Very High (4 sources converge on this pattern)
- **Effort:** Medium (~1.5 days)
- **Rationale:** Addresses DevolaFlow's largest structural gap. Schema: `{stage, task_type, key, insight, confidence, rule_id}`. Loaded during Task Agent LOAD_RULES phase.

### Rank 8: 4-Type Gate Taxonomy

- **Description:** Classify gates as pre-flight/revision/escalation/abort; route differently per type
- **Source repo(s):** GSD
- **DevolaFlow component:** `gate/scorer.py`, gate models, SKILL.md gate section
- **Estimated EvoBench impact:** Positive (clearer failure handling reduces ambiguous outcomes)
- **Confidence:** High (GSD's most mature pattern; 160+ tests)
- **Effort:** Medium (~2 days)
- **Rationale:** Current gate evaluates pass/fail but failure routing is ambiguous. Taxonomy provides deterministic next-action on failure.

### Rank 9: Model Profiles per Agent Role

- **Description:** Add `model_hint` field to TaskDispatch; L2 Wave selects model tier by task complexity
- **Source repo(s):** GSD, superpowers, Hydra
- **DevolaFlow component:** TaskDispatch schema, `context_profiles.yaml`, wave dispatch logic
- **Estimated EvoBench impact:** Neutral (benchmark evaluates context quality, not model selection)
- **Confidence:** Very High (3 sources converge; table stakes for cost optimization)
- **Effort:** Medium (~2 days)
- **Rationale:** Cheap models for mechanical tasks, capable models for architecture/review. Directly reduces orchestration cost.

### Rank 10: Self-Improving Feedback Loop

- **Description:** Post-workflow stage that captures learnings and proposes rule/skill updates
- **Source repo(s):** Self-Improving System (Triangulum9r), gstack, Bootstrap Seed
- **DevolaFlow component:** New post-workflow hook/stage, SKILL.md, `.cursor/rules/`
- **Estimated EvoBench impact:** Positive (compounding quality over workflow executions)
- **Confidence:** High (3 sources converge; builds on Rank 7 learnings persistence)
- **Effort:** Medium (~2 days)
- **Rationale:** Enables DevolaFlow quality to compound. Each completed workflow improves the next. Complements EvoBench feedback with broader scope.

### Rank 11: Knowledge Index

- **Description:** Add `knowledge/index.md` as central catalog of all knowledge pages; auto-update on modification
- **Source repo(s):** Karpathy wiki
- **DevolaFlow component:** `workflow-system/agent/knowledge/index.md`
- **Estimated EvoBench impact:** Neutral to slightly positive (reduces context lookup waste)
- **Confidence:** Medium (abstract pattern, no implementation benchmark)
- **Effort:** Low (~0.5 day)
- **Rationale:** Task Agents read index first, then drill into relevant pages. Reduces unnecessary knowledge loading.

### Rank 12: Prompt Injection Defense Hooks

- **Description:** Pre-dispatch hook scanning TaskDispatch/StatusReport YAML for injection patterns
- **Source repo(s):** GSD
- **DevolaFlow component:** Lifecycle hooks, `validate_dispatch` extension
- **Estimated EvoBench impact:** Neutral (security, not context quality)
- **Confidence:** High (GSD's multi-layer defense is mature and directly portable)
- **Effort:** Low (~1 day)
- **Rationale:** Multi-agent YAML messages are injection vectors. Defense-in-depth. Regex patterns from GSD's `INJECTION_PATTERNS` list.

### Rank 13: Skills Security Trust Levels

- **Description:** Add `trust_level` field to workflow-skill.yaml (first_party/verified/community/untrusted)
- **Source repo(s):** Agent Skills Security paper
- **DevolaFlow component:** `workflow-skill.yaml`, gate mechanism, adapter build pipeline
- **Estimated EvoBench impact:** Neutral
- **Confidence:** High (peer-reviewed paper with empirical data; documented ClawHavoc attack)
- **Effort:** Low (~1 day for field; medium for scanning)
- **Rationale:** As adapter ecosystem grows, attack surface grows. 26.1% vulnerability rate is a warning.

### Rank 14: Reference Dependency Tracking

- **Description:** Add `depends_on_artifacts` field to TaskDispatch; Wave verifies before dispatch
- **Source repo(s):** gstack (`benefits-from` pattern)
- **DevolaFlow component:** TaskDispatch schema, wave dispatch logic
- **Estimated EvoBench impact:** Neutral to slightly positive (prevents missing-context dispatches)
- **Confidence:** Medium (single source, but clean design)
- **Effort:** Low (~1 day)
- **Rationale:** Missing artifact dependencies currently cause Task Agent failures. Verification at dispatch prevents waste.

### Rank 15: Two-Stage Gate Verification

- **Description:** Gate evaluates spec compliance first, then code quality; both must pass
- **Source repo(s):** superpowers
- **DevolaFlow component:** `gate/scorer.py`, gate evaluation flow
- **Estimated EvoBench impact:** Positive (catches "well-tested but wrong scope")
- **Confidence:** Medium (single source; partially overlaps with existing gate composite scoring)
- **Effort:** Medium (~2 days)
- **Rationale:** Prevents "well-built but wrong" code from passing gate. Integrates into `test_on_complete` lifecycle hook.

---

## 5. Self-Update Workflow Inputs

### 5.1 Repos/Resources to Track for Ongoing Changes

| # | Source | URL | Track What | Update Trigger |
|---|--------|-----|-----------|---------------|
| 1 | **Anthropic advisor tool** | https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/advisor-tool | Beta version changes, new model pairs, API parameter additions, pricing changes | Beta header version changes from `advisor-tool-2026-03-01`; new executor/advisor model pairs announced |
| 2 | **superpowers** | https://github.com/obra/superpowers | New skills added, enforcement pattern updates, TDD/review process changes | New SKILL.md files in `skills/`; changes to rationalization tables or iron laws |
| 3 | **get-shit-done** | https://github.com/gsd-build/get-shit-done | Gate taxonomy changes, new hooks, model profile updates, security patterns | Changes to `references/gates.md`; new hooks in `hooks/`; new agent files |
| 4 | **gstack** | https://github.com/garrytan/gstack | Learnings system updates, new specialist skills, review specialist additions | Changes to `learn/SKILL.md`; new skills in root directory; changes to review specialists |

### 5.2 Repos to Monitor Periodically (Lower Frequency)

| # | Source | URL | Check Frequency | Reason |
|---|--------|-----|----------------|--------|
| 5 | **Google Scion** | https://github.com/GoogleCloudPlatform/scion | Monthly | Early/experimental; may mature with useful isolation patterns |
| 6 | **SkillRouter** | https://github.com/zhengyanzhao1997/SkillRouter | Quarterly | Academic paper; new versions may improve accuracy or reduce model size |
| 7 | **Anthropic coordination patterns blog** | https://www.claude.com/blog/multi-agent-coordination-patterns | Monthly | Anthropic publishes new patterns and best practices regularly |
| 8 | **Agent Skills Security** | https://arxiv.org/abs/2602.12430 | Quarterly | Security landscape evolves; new vulnerability data expected |

### 5.3 Update Review Protocol

**Trigger conditions (any one sufficient):**
1. Tracked repo releases a new major/minor version
2. Anthropic advisor tool exits beta or changes API shape
3. A new repo with >5K stars and relevance >=4/5 appears in the agent orchestration space
4. DevolaFlow version bump introduces a feature that changes overlap analysis (re-classify gaps)
5. EvoBench regression detected after context profile changes (check if external pattern addresses it)

**Review actions:**
1. Read the changed files/docs from the tracked source
2. Re-evaluate relevance score against current DevolaFlow version
3. Update gap classification (may move from high→already-addressed or low→high)
4. If a high-priority gap is now addressable with lower effort, create integration task
5. Log review result in `knowledge/learnings/external-sources.jsonl` (when learnings system is implemented)

### 5.4 Staleness Indicators

| Indicator | Action |
|-----------|--------|
| Gap classified `already-addressed` for >2 versions | Remove from active tracking |
| Source repo archived or >6 months inactive | Downgrade tracking frequency; mark patterns as "frozen reference" |
| New source supersedes tracked source | Replace in tracking list; update synthesis |
| DevolaFlow implements a gap at medium+ quality | Reclassify to `already-addressed` with version citation |

---

## Appendix A: Source Coverage Verification

All repos/resources from all 6 predecessor reports are accounted for in the comparison matrix:

| Report | Sources Covered | Matrix Rows |
|--------|----------------|-------------|
| S01-T01 (lean skills) | caveman, superpowers | #1, #2 |
| S01-T02 (orchestration) | get-shit-done, edict | #3, #4 |
| S01-T03 (roles/knowledge) | gstack, Karpathy wiki | #5, #6 |
| S01-T04 (advisor tool) | Anthropic advisor tool | #7 |
| S01-T05 (expanded search) | Scion, SkillRouter, vexp, Self-Improving System, Agent Skills Security, Hydra, Ruflo, Bootstrap Seed, Spring AI | #8–#16 |
| T02 (prior research) | Anthropic 5 Patterns, AdaptOrch, Evaluator-Optimizer, Deterministic Hooks, Reflection, Context Engineering, AgentOrchestra | #17–#23 |
| **Total** | **23 sources** | **23 rows** |

## Appendix B: Confidence Scoring Methodology

| Confidence Level | Criteria |
|-----------------|----------|
| Very High | Multiple independent sources converge (4+); peer-reviewed OR production-tested |
| High | 2-3 sources converge OR single highly credible source (Anthropic, Google, Spring) with benchmarks |
| Medium | Single source with benchmarks OR multiple sources without empirical validation |
| Low | Single source, no benchmarks, early-stage or proposal-only |

## Appendix C: Effort Estimation Scale

| Effort | Definition |
|--------|-----------|
| Low | <1 day; schema/config/documentation changes only; no engine code changes |
| Medium | 1-3 days; engine code changes with test coverage; may require schema extensions |
| High | 3-5+ days; infrastructure changes; new modules or subsystems; significant test investment |
