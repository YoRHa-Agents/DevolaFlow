# Wave 1 Research Synthesis Report

> **Scope**: Unified synthesis across agent frameworks (WP-1), local workflow patterns (WP-2), and workflow type catalog (WP-3).
> **Purpose**: Extract cross-cutting findings, comparison matrices, and design recommendations for the Agent Workflow Meta-Framework.
> **Date**: 2026-04-04

---

## Executive Summary — 10 Key Findings

1. **Orchestration topology dominates model selection.** The AdaptOrch paper (Feb 2026) showed 12–23% improvement from topology optimization alone, even with identical models. This validates our meta-framework's focus on workflow structure over model choice.

2. **A single set of 11 stage primitives composes all 10 workflow types.** Cross-analysis of WP-1 frameworks, WP-2 local patterns, and WP-3 workflow catalog reveals that `Review/Evaluate` (100%) and `Validate/Verify` (100%) are truly universal, while `Plan` (90%), `Analyze` (80%), and `Implement` (80%) are near-universal. Every workflow is a subset of the Full Pipeline's 8-stage maximal chain.

3. **Three loop-back archetypes cover all iteration needs.** Quality Loops (review → refine, max 3 rounds), Correctness Loops (test → fix, max 5 rounds), and Knowledge Loops (evaluate → investigate, max 2 rounds) are sufficient to express every iterative pattern observed across frameworks and workflow types.

4. **The dispatcher-not-implementer principle is the strongest local pattern.** Extracted from EchoAccess's 17-stage execution, this principle — where the orchestrating agent never performs work, only dispatches — cleanly separates coordination from execution, prevents context pollution, and maps directly to LangGraph's supervisor pattern and Cursor Agent's parent-subagent model.

5. **Graph-based state machines are the only production-proven architecture offering both durability and flexibility.** LangGraph's checkpointing, conditional edges, and state rollback form the most robust execution foundation. No other framework matches its combination of durable execution and workflow expressiveness.

6. **Simple, composable patterns outperform complex frameworks.** Both Anthropic and OpenAI independently converged on the same advice: start with single LLM calls, add complexity only when measurably beneficial. Five composition primitives (Sequence, Parallel, Choice, Loop, Gate) are sufficient to express every workflow type declaratively.

7. **Context isolation is the critical differentiator for multi-agent quality.** MetaGPT's pub-sub message pool, Cursor Agent's subagent context isolation, and OpenHands's sandboxed execution all solve the same problem: preventing context pollution across agent boundaries. The EchoAccess pattern enforces this through narrow file ownership (2–12 files per stage).

8. **Error handling is the primary production differentiator.** Without resilience engineering, agents achieve only 60% success on single runs, dropping to 25% across eight consecutive steps. Classified retry, circuit breakers, and graceful degradation are non-negotiable for production. Only LangGraph provides all three natively.

9. **The Work Package (WP) is a proven atomic planning unit.** Analysis of 98 WPs across 13 local plans shows a mature structure: bounded complexity (L/M/H), explicit subagent delegation, dependency declaration, numbered actions (3–6), and binary done-when criteria. This maps directly to Task-level granularity in the meta-framework.

10. **MCP + A2A constitute the emerging interoperability standard.** MCP standardizes agent-tool communication; A2A standardizes agent-agent communication. Together they form a two-layer protocol stack under the Linux Foundation, future-proofing any meta-framework that adopts them.

---

## Unified Comparison Matrix

### Frameworks × Evaluation Dimensions

| Dimension | CrewAI | AutoGen/AG2 | LangGraph | MetaGPT | ChatDev | OpenHands | Devin | Cursor Agent |
|-----------|--------|-------------|-----------|---------|---------|-----------|-------|-------------|
| **Architecture** | Flow + Crew layers | Event-driven actor model | Graph-based state machine | Pub-sub message pool | 3-layer chat chain | Event-sourced SDK | Sandboxed IDE agent | IDE-embedded + subagents |
| **Collaboration Model** | Sequential / Hierarchical | Conversational multi-turn debate | Explicit graph wiring (supervisor/workers) | Role-based waterfall SOP | Pairwise chat SDLC phases | Single-agent + emerging parallel | Single autonomous agent | Hierarchical parent → subagent |
| **Task Decomposition** | Pre-defined task graph | Emergent from conversation | Developer-defined graph topology | Implicit in role chain | Phase-based SDLC | Dynamic agent reasoning | Internal planning | LLM-driven dynamic |
| **Error Handling** | Task guardrails, structured output | Conversational correction | Conditional error edges, state rollback, durable execution | Code execution feedback loop | Communicative dehallucination | Event replay, sandbox isolation | Self-verification, auto-fix | Subagent isolation, test self-healing (89%) |
| **Checkpointing** | Basic | None built-in | Full (every step) | None built-in | None built-in | Full (event store) | Internal (opaque) | Session-based only |
| **Workflow Flexibility** | Medium (pre-defined tasks, limited branching) | High (emergent, unpredictable) | High (conditional edges, subgraphs) | Low (rigid waterfall) | Low (rigid SDLC phases) | High (autonomous agent loop) | Medium (internal planning) | High (dynamic subagent spawning) |
| **Agent Isolation** | Shared crew context | Accumulated conversation | Typed state across graph | Pub-sub filtered subscriptions | Memory stream per pair | Docker sandbox per agent | Sandboxed IDE | SVFS + isolated subagent contexts |
| **CI/CD Integration** | MCP tool access | MCP tool access | MCP + graph-encoded pipelines | Limited | Limited | GitHub App, MCP | Slack/Linear/API | MCP + IDE integration |
| **Protocol Support** | MCP | MCP | MCP | None | None | MCP, LiteLLM | Proprietary | MCP |
| **Production Maturity** | High (Fortune 500 60%) | Medium (transitioning) | High (v1.0; Klarna, Uber) | Medium | Medium (limited prod evidence) | Medium-High (V1) | High (Goldman Sachs) | High (widespread dev adoption) |
| **License** | Apache 2.0 | MIT | MIT | MIT | Apache 2.0 | MIT | Proprietary | Proprietary |

### Scoring Summary (1–5 scale)

| Dimension | CrewAI | AutoGen | LangGraph | MetaGPT | ChatDev | OpenHands | Devin | Cursor |
|-----------|--------|---------|-----------|---------|---------|-----------|-------|--------|
| Checkpointing/Resume | 2 | 1 | **5** | 1 | 1 | **5** | 3 | 2 |
| Dynamic Decomposition | 2 | 4 | 3 | 1 | 1 | 4 | 3 | **5** |
| Role-Based Team Structure | **5** | 3 | 3 | **5** | 4 | 2 | 1 | 3 |
| Error Resilience | 3 | 2 | **5** | 2 | 2 | 4 | 4 | 4 |
| Parallel Execution | 3 | 2 | 4 | 2 | 1 | 3 | 3 | **5** |
| Context Isolation | 2 | 1 | 3 | 4 | 3 | **5** | 4 | **5** |
| Interoperability | 3 | 3 | 4 | 1 | 1 | 4 | 1 | 3 |
| Simplicity/Composability | 4 | 2 | 2 | 3 | 3 | 3 | 4 | 4 |
| Workflow Definition Lang. | 2 | 1 | **5** | 2 | 2 | 1 | 1 | 1 |
| IDE Integration | 2 | 1 | 2 | 1 | 3 | 3 | 4 | **5** |
| **Average** | **2.8** | **2.0** | **3.6** | **2.2** | **2.1** | **3.4** | **2.8** | **3.7** |

LangGraph and Cursor Agent emerge as the two strongest foundations, each dominating different dimensions. LangGraph excels in durability and formal workflow definition; Cursor Agent excels in dynamic decomposition, parallelism, and IDE integration.

---

## Cross-Cutting Commonality Analysis

### Shared Stage Primitives Across All Three Research Streams

The following primitives appear consistently across agent frameworks (WP-1), local plan patterns (WP-2), and workflow type catalog (WP-3):

| Primitive | WP-1 Framework Evidence | WP-2 Local Pattern Evidence | WP-3 Workflow Type Evidence | Universality |
|-----------|------------------------|----------------------------|----------------------------|-------------|
| **Research / Scout** | Anthropic: "research before acting"; OpenHands: codebase analysis | Scout Reconnaissance pattern (all 13 plans) | 6/10 workflow types include research | Frequent (60%) |
| **Design** | MetaGPT: Architect role; RDRR sub-workflow | Implicit in architecture plans | 4/10 workflow types (RDRR, Full Pipeline, Design-Only) | Specialized (40%) |
| **Plan** | Anthropic: orchestrator-workers; Devin: interactive planning | WP structure (98 WPs), Wave scheduling, Mermaid DAGs | 9/10 workflow types | Near-Universal (90%) |
| **Implement / Execute** | OpenHands: CodeAct; Cursor: subagent execution; Devin: autonomous coding | Stage-Main-Agent dispatches to Coding Sub-agent | 8/10 workflow types | Common (80%) |
| **Review** | MetaGPT: pub-sub filtered review; Anthropic: evaluator-optimizer | Convergence loop Phases 1, 7 (Code Review, SOLID Review) | 10/10 workflow types | **Universal (100%)** |
| **Test** | OpenHands: sandbox execution; LangGraph: test nodes | Convergence loop Phase 3 (TDD Sub-agent) | 7/10 workflow types | Common (70%) |
| **Refine / Fix** | AutoGen: conversational correction; Cursor: test self-healing | Convergence loop Phases 2, 4, 6, 8 (Fix sub-phases) | 3/10 types explicitly, but all loops imply refinement | Specialized but implied universally |
| **Gate** | LangGraph: conditional edges + human interrupts; CrewAI: task guardrails | Gate mechanism with composite quality score formula | 2/10 types have formal gates, but gate logic is embedded in all loops | Specialized (formal), Universal (informal) |
| **Release / Publish** | Devin: PR creation; Cursor: git integration | Not prominent in local patterns | 4/10 workflow types | Specialized (40%) |
| **Analyze / Profile** | Anthropic: planner agent; MetaGPT: Product Manager role | Scout Findings (Verified/Discovered/Gaps) | 8/10 workflow types | Common (80%) |
| **Validate / Verify** | LangGraph: state rollback; Devin: self-verification | Done-When criteria (binary pass/fail) | 10/10 workflow types | **Universal (100%)** |

### Common Collaboration Patterns

| Pattern | Description | Framework Examples | Local Pattern Examples | Strengths | Weaknesses |
|---------|-------------|-------------------|----------------------|-----------|------------|
| **Hub-Spoke (Supervisor)** | Central orchestrator delegates to specialist workers, aggregates results | LangGraph (supervisor node), OpenAI SDK (agents-as-tools), Cursor (parent → subagents) | Project-Main-Agent dispatches to Stage-Main-Agents | Clear control flow, predictable, easy to debug | Single point of failure; orchestrator becomes bottleneck |
| **Pipeline (Sequential)** | Stages execute in fixed order, each consuming predecessor's output | MetaGPT (role chain), ChatDev (chat chains), CrewAI (sequential mode) | Wave execution order, WP dependency chains | Deterministic, easy to reason about | No parallelism; slow for independent tasks |
| **Peer-Review** | Agents evaluate each other's work in structured review cycles | AutoGen (debate/iterate), ChatDev (communicative dehallucination), Anthropic (evaluator-optimizer) | Convergence loop (Code Review ↔ Coding Sub-agent) | Catches errors through diverse perspectives | Expensive (multiple LLM calls); risk of circular disagreements |
| **Hierarchical Delegation** | Multi-level tree: project → stage → task, each level with isolated context | Cursor (parent → subagents), CrewAI (hierarchical mode), EchoAccess 3-tier | Project-Main → Stage-Main → {Coding, TDD, Review} Sub-agents | Scalable decomposition; context isolation at each level | Deep hierarchies increase latency; inter-level communication overhead |
| **Fan-Out / Fan-In** | Parallel dispatch of independent work, then convergence/synthesis | LangGraph (parallel branches), Cursor (parallel subagents) | Wave pattern: N parallel WPs → consolidation WP | Maximum throughput for independent tasks | Synthesis step must handle heterogeneous outputs |
| **Pub-Sub (Message Pool)** | Agents publish to shared pool, consume only relevant messages | MetaGPT (shared message pool with subscriptions) | Not observed in local patterns | Prevents context pollution; agents see only relevant data | Requires message type taxonomy; harder to debug |

### Universal Mechanisms

| Mechanism | Cross-Framework Evidence | Local Pattern Evidence | Workflow Type Evidence |
|-----------|------------------------|----------------------|----------------------|
| **Context Isolation** | Cursor SVFS, OpenHands Docker sandbox, MetaGPT pub-sub filtering | Stage-level file ownership (2–12 files), Dispatcher-not-implementer | Implicit in all multi-agent workflows |
| **Checkpoint / State Persistence** | LangGraph (every step), OpenHands (event store) | Record-keeping system (.local/stages/), per-round artifacts | Gate checkpoints between stages |
| **Retry with Bounds** | Exponential backoff + jitter (cross-framework), classified retry | Convergence loop (min 3 rounds, max 6) | All 3 loop types have max-round bounds (2, 3, or 5) |
| **Quality Gates** | LangGraph conditional edges, CrewAI guardrails, Devin self-verification | Composite quality score: tdd×0.3 + review×0.3 + solid×0.2 + bench×0.2 | TestGate, Review Gate, Release Gate |
| **Graceful Degradation / Escalation** | Circuit breaker → fallback → human escalation (cross-framework) | Gate fail → next round → max rounds → escalation | Loop escalation: auto-retry → scope escalation → human escalation |
| **Structured Handoff** | OpenAI SDK handoffs, Anthropic agent teams bi-directional messaging | Subagent execution contract (input packet → output format) | Stage transitions with typed inputs/outputs |

---

## Stage Primitive Candidates

Synthesizing all three research streams, the meta-framework should adopt the following 12 canonical stage primitives:

| # | Primitive | Type | Description | Triggered By | Produces |
|---|-----------|------|-------------|-------------|----------|
| 1 | **Scout** | Information | Reconnoiter workspace: verify resources exist, discover relevant context, identify gaps | Workflow start, stage entry | Scout report (Verified / Discovered / Gaps) |
| 2 | **Research** | Information | Gather external knowledge: survey prior art, benchmark alternatives, collect evidence | Explicit task need | Research report with comparison matrix |
| 3 | **Analyze** | Information | Examine existing artifacts: profile, assess risks, identify patterns, map dependencies | Existing codebase/system | Analysis report with prioritized findings |
| 4 | **Design** | Synthesis | Create architectural artifacts: interfaces, data models, system specifications | Research/analysis outputs | Design document with ADRs |
| 5 | **Plan** | Synthesis | Decompose design into executable units: WPs, Waves, dependencies, estimates | Design document | Implementation plan (WP list, Wave schedule, DAG) |
| 6 | **Implement** | Execution | Write code, create tests, build infrastructure per task specification | Plan/task specification | Source code, tests, build artifacts |
| 7 | **Review** | Evaluation | Evaluate work quality: code review, design compliance, style adherence | Implementation output | Review verdict (PASS/REVISE) with severity-classified findings |
| 8 | **Test** | Evaluation | Execute automated verification: unit, integration, E2E, performance, security | Implementation output | Test results with pass/fail per suite, coverage report |
| 9 | **Refine** | Remediation | Address findings from Review/Test: fix bugs, resolve comments, improve quality | Review findings or test failures | Updated code/artifacts, refine changelog |
| 10 | **Gate** | Control | Formal quality checkpoint: evaluate composite metrics, block/route progression | Stage completion | Gate verdict (PASS/FAIL/ESCALATE) with metrics |
| 11 | **Release** | Delivery | Package, tag, deploy, announce: create artifacts, update changelog, deploy | Gate PASS | Release artifacts, deployment confirmation |
| 12 | **Validate** | Verification | Post-action correctness check: data reconciliation, smoke test, acceptance criteria | Any stage output | Validation report (PASS/FAIL) |

### Primitive Composition Rules

Every workflow type can be expressed as a composition of these 12 primitives using 5 composition operators:

| Operator | Notation | Semantics |
|----------|----------|-----------|
| **Sequence** | `A → B → C` | Execute in order; B starts after A completes |
| **Parallel** | `A ∥ B ∥ C` | Execute simultaneously; all must complete before next step |
| **Choice** | `if(cond) A else B` | Conditional routing based on gate/review verdict |
| **Loop** | `repeat(A → B) until(cond) max(N)` | Iterate body until condition met or max rounds reached |
| **Gate** | `gate(criteria) → pass: A, fail: B` | Checkpoint that blocks and routes based on metrics |

### Workflow Type → Primitive Mapping

| Workflow Type | Primitive Chain |
|---------------|----------------|
| Research-Only | Scout → Research → Analyze → Validate |
| Design-Only | Scout → Analyze → Design → Review → loop(Refine → Design → Review) → Validate |
| RDRR | Scout → Research → Design → loop(Review → Refine → Design) → Validate |
| Hotfix | Scout → Analyze → Implement → loop(Test → Refine → Implement) → Release |
| Refactoring | Scout → Analyze → Plan → loop(Implement → Test → Refine) → Validate |
| Migration | Scout → Research → Analyze → Plan → loop(Implement → Validate → Refine) → Release |
| Spike/PoC | Scout → Research → Implement → Analyze → Gate(go/no-go) |
| Documentation | Scout → Analyze → Implement → Review → loop(Refine → Implement → Review) → Release |
| Security Audit | Scout → Analyze → Review → Plan → Implement → loop(Test → Refine) → Validate |
| Perf Optimization | Scout → Analyze → Plan → loop(Implement → Test → Analyze → Refine) → Validate |
| Feature Enhancement | Scout → Plan → Implement → Review → Test → loop(Refine → Implement → Review → Test) → Gate → Release |
| Full Pipeline | Scout → Design → Plan → Implement → loop(Review → Refine) → loop(Test → Refine) → Gate → Release |

---

## Recommended Patterns for Our System

### Pattern 1: Graph-Based State Machine as Core Execution Model

**Source**: LangGraph (WP-1), all workflow compositions (WP-3)
**Justification**: The graph-based model is the only architecture that provides typed state flow, checkpointing at every step, conditional branching, and explicit error handling paths simultaneously. Our 12 stage primitives map directly to graph nodes; the 5 composition operators map to edge types (sequential, parallel, conditional, loop-back, gate).
**Trade-off**: Steeper learning curve and verbose definitions for simple workflows. Mitigated by providing pre-composed workflow type templates.

### Pattern 2: Hierarchical Delegation with Context Isolation (Dispatcher-Not-Implementer)

**Source**: Cursor Agent subagent model (WP-1), EchoAccess 3-tier hierarchy (WP-2)
**Justification**: The strongest empirical pattern from local execution. Project-Main never implements — it dispatches to Stage-Mains, which delegate to specialist sub-agents. This creates a clean Project → Stage → Task hierarchy that maps to nested subgraph composition. Each level operates with isolated context (2–12 files per stage), preventing the context pollution that plagues flat multi-agent systems.
**Trade-off**: Delegation overhead for trivially small tasks. Mitigated by allowing single-level execution for L-complexity WPs.

### Pattern 3: Convergence Loop with Composite Quality Gate

**Source**: EchoAccess convergence loop (WP-2), LangGraph conditional edges (WP-1), quality/correctness/knowledge loops (WP-3)
**Justification**: The most sophisticated quality assurance pattern observed. The 8-phase convergence loop (review → fix → test → fix → benchmark → fix → final-review → fix) with a composite score formula (`tdd×0.3 + review×0.3 + solid×0.2 + bench×0.2 ≥ 85`) provides quantified, repeatable quality enforcement. Generalizable to any stage that produces reviewable artifacts.
**Trade-off**: High computational cost (minimum 3 rounds × 8 phases = 24 LLM calls per stage). Mitigated by using abbreviated loops for L-complexity tasks and reserving full convergence for H-complexity stages.

### Pattern 4: Work Package as Atomic Planning Unit

**Source**: 98 WPs across 13 Cursor plans (WP-2)
**Justification**: The WP structure (complexity rating, subagent type, dependency list, numbered actions, done-when criteria) is empirically proven across diverse project types. It maps directly to Task nodes in the graph model. The consistent sizing (15–90 min) ensures WPs fit within a single agent session, preventing context overflow.
**Trade-off**: Formalism overhead for trivially simple changes. Mitigated by auto-generating WP structure for L-complexity tasks.

### Pattern 5: Wave-Based Parallel Scheduling

**Source**: EchoAccess 7-wave execution (WP-2), LangGraph parallel branches (WP-1), fan-out/fan-in pattern (WP-3)
**Justification**: Waves are the proven scheduling unit. Within a wave, independent WPs run in parallel; Wave N+1 starts only after all Wave N WPs complete. The four observed patterns (Research Fan-out, Sequential Pipeline, Staged Dependencies, Subagent Handoff) cover all scheduling needs.
**Trade-off**: Rigid wave boundaries can delay execution if one WP in a wave is slow (convoy effect). Mitigated by allowing fine-grained dependency-based scheduling within waves.

### Pattern 6: Scout Reconnaissance Before Every Workflow

**Source**: Scout Findings pattern (all 13 plans, WP-2), Anthropic "research before acting" (WP-1)
**Justification**: Every plan benefits from a scout phase that inventories the workspace (Verified/Discovered/Gaps). This prevents stale path references (Anti-Pattern 2), identifies missing prerequisites before they block execution, and creates a starting-conditions baseline. The D1/D2/D3 quality scoring of scout output provides plan quality accountability.
**Trade-off**: Adds latency before execution starts. Mitigated by making scout lightweight (file existence checks, not deep analysis).

### Pattern 7: Three-Loop Escalation Hierarchy

**Source**: Cross-type loop analysis (WP-3), circuit breaker pattern (WP-1), convergence loop bounds (WP-2)
**Justification**: All iteration in the system follows one of three patterns — Quality Loop (review → refine, max 3), Correctness Loop (test → fix, max 5), Knowledge Loop (evaluate → investigate, max 2). When max rounds are reached: auto-retry → scope escalation (loop-back to earlier stage) → human escalation (pause with divergence report). This three-level escalation prevents infinite loops while allowing recovery.
**Trade-off**: Fixed max-round limits may be too rigid for some tasks. Mitigated by making limits configurable per workflow type.

### Pattern 8: Declarative Workflow Templates with YAML

**Source**: Composition primitives (WP-3), YAML frontmatter pattern (WP-2), pipeline-as-code CI/CD patterns (WP-3)
**Justification**: Workflow types should be expressed as declarative YAML templates that compose stage primitives. This enables: (a) a workflow type registry, (b) workflow selection heuristics based on task signals, (c) versioned, diffable workflow definitions, and (d) visual rendering via Mermaid. The YAML frontmatter pattern from local plans provides a proven contract format.
**Trade-off**: YAML templates are less flexible than programmatic workflow definitions. Mitigated by supporting dynamic subgraph generation for LLM-driven decomposition within template-defined stages.

### Pattern 9: MCP for Tool Access + Structured Handoffs for Agent Communication

**Source**: MCP/A2A protocols (WP-1), subagent execution contract (WP-2), OpenAI SDK handoffs (WP-1)
**Justification**: MCP provides standardized tool access (the "USB-C of AI integrations"). For agent-agent communication, structured handoffs with typed input/output schemas (inspired by OpenAI SDK handoffs and the EchoAccess subagent contract) prevent context pollution while ensuring consistent evidence quality. A2A adoption future-proofs cross-framework interoperability.
**Trade-off**: Protocol adoption adds integration complexity. Mitigated by providing default MCP tool wrappers and typed handoff schemas.

### Pattern 10: Quantified Done-When Criteria with Anti-Pattern Guards

**Source**: Done-When pattern (WP-2), anti-pattern catalog (WP-2), TestGate criteria (WP-3)
**Justification**: Every WP must have binary pass/fail done-when criteria referencing concrete artifacts (files exist, commands succeed, counts met). Five identified anti-patterns (context overflow, stale references, scope mixing, vague criteria, missing deferred scope) should be checked automatically during plan validation.
**Trade-off**: Strict binary criteria can be hard to define for exploratory tasks. Mitigated by allowing "satisficing" criteria for research-type WPs (e.g., "≥ N sources analyzed, comparison matrix has ≥ M entries").

---

## Gaps and Open Questions

### Gap 1: Cross-Session State Persistence in Cursor

**Problem**: Cursor Agent uses session-based recovery only — no structured checkpoint mechanism survives session interruption. For multi-day workflows (migration, full pipeline), this is a critical limitation.
**None of the frameworks handle this well**: LangGraph's checkpointing requires a separate persistence backend. OpenHands' event store is coupled to its runtime. Devin's state is proprietary and opaque.
**Needed**: A lightweight, file-system-based checkpoint format that works within Cursor's session model. The EchoAccess `.local/stages/` record-keeping system is a manual approximation, but lacks automatic resume.

### Gap 2: Dynamic Workflow Type Selection and Adaptation

**Problem**: No framework provides automated workflow type selection based on task analysis. WP-3 defines selection heuristics (keyword matching), but no framework implements mid-workflow type switching when conditions change (e.g., a "feature enhancement" escalates to "full pipeline" when scope grows).
**Needed**: A workflow routing stage that analyzes the task, selects a workflow type template, and can re-route if mid-execution signals indicate a different type is more appropriate.

### Gap 3: Inter-Agent Communication Beyond Hub-Spoke

**Problem**: Cursor Agent supports only one-way parent → subagent communication. Anthropic Agent Teams introduced bi-directional messaging (Feb 2026), but this is not available in any open framework. Peer-to-peer agent communication (needed for review loops where reviewer and implementer negotiate) is unsupported.
**Needed**: Bidirectional message channels between sibling agents at the same hierarchy level, with structured message types (request, response, finding, clarification).

### Gap 4: Cost-Aware Orchestration

**Problem**: No framework optimizes for token cost across orchestration decisions. AutoGen's conversational pattern is the most expensive (every turn = full LLM call with growing context), but no framework provides cost estimation or budget enforcement at the workflow level.
**Needed**: Token budget allocation per stage/wave/task, with cost tracking and budget-aware routing (e.g., use faster/cheaper model for L-complexity tasks, reserve expensive model for H-complexity).

### Gap 5: Workflow Observability and Progress Reporting

**Problem**: LangGraph provides visualization through LangGraph Studio, but real-time progress reporting for multi-wave workflows is absent from all frameworks. The EchoAccess `overview.md` dashboard is a manual tracking file.
**Needed**: Automated progress dashboards: per-wave completion status, quality scores over time (convergence charts), estimated remaining time, cost accumulator, and risk status.

### Gap 6: Cross-Stage Artifact Contracts

**Problem**: WP-2 identified that dependency between stages is expressed informally (WP-level text, Mermaid arrows). No framework enforces that Stage B's input schema matches Stage A's output schema.
**Needed**: Typed artifact contracts between stages — specifying the exact schema of what one stage produces and the next stage consumes. The EchoAccess "artifact contract" concept (e.g., "UIAdapter trait signature frozen after S2") is the closest existing pattern but lacks machine enforcement.

### Gap 7: Rollback and Partial Completion

**Problem**: When a late-stage gate fails (e.g., TestGate), the system loops back to Refine → Impl. But no framework handles the case where a multi-file implementation partially succeeded — some files are correct, others need rework. Rollback granularity is at the whole-stage level, not file-level.
**Needed**: Fine-grained rollback that preserves correct work and targets only the failing components. Cursor's SVFS (shadow virtual file system) is the closest mechanism, but it operates at merge time, not at rollback time.

### Gap 8: Human-in-the-Loop Escalation Protocol

**Problem**: All frameworks mention human escalation as a fallback, but none define a structured protocol for it. What information should the divergence report contain? How does the human response re-enter the workflow? What happens to the workflow state while waiting for human input?
**Needed**: A formal escalation protocol: divergence report format (what was attempted, what failed, what options exist), pause/resume mechanism, human response schema, and workflow resumption from the human-modified state.

### Gap 9: Workflow Composition and Nesting

**Problem**: Our system needs workflows that embed other workflows (e.g., Full Pipeline's Design stage might spawn a full RDRR sub-workflow). No framework provides clean workflow nesting with proper state isolation between parent and child workflows.
**Needed**: Subgraph composition where a stage in the parent workflow expands into a complete child workflow with its own state, loops, and gates, returning a structured result to the parent upon completion. LangGraph's subgraph feature is the closest, but lacks the workflow-type-aware instantiation we need.

### Gap 10: Learning and Improvement Across Runs

**Problem**: No framework captures execution telemetry to improve future workflow runs. If a workflow type consistently fails at a specific stage, or if certain task types always require more rounds than estimated, this information is lost.
**Needed**: Execution history database recording: workflow type, stage durations, loop round counts, gate pass/fail rates, quality scores. This enables: calibrating time estimates, identifying bottleneck stages, recommending workflow type based on historical performance.

---

## Full References List

### Agent Framework Documentation (WP-1)

| # | Source | Details |
|---|--------|---------|
| 1 | CrewAI Documentation | docs.crewai.com — Flow + Crew architecture, 41K+ stars |
| 2 | AutoGen / AG2 | Microsoft — Event-driven actor model, v0.7 three-layer architecture |
| 3 | LangGraph | LangChain — Graph-based state machine, v1.0 (Oct 2025) |
| 4 | MetaGPT | "Code = SOP(Team)" — Pub-sub message pool, role-based SOP |
| 5 | ChatDev / DevAll | OpenBMB — Chat chain architecture, ChatDev 2.0 visual console |
| 6 | OpenHands (formerly OpenDevin) | Event-sourced SDK, V1 (Nov 2025), 70K+ stars |
| 7 | Devin | Cognition Labs — Autonomous AI engineer, 67% PR merge rate |
| 8 | Cursor Agent | Cursor 2.0/3 — IDE-embedded orchestrator + subagents, SVFS |

### Industry Best Practices (WP-1)

| # | Source | Details |
|---|--------|---------|
| 9 | Anthropic: Building Effective Agents | Dec 2024 — 5 canonical workflow patterns |
| 10 | Anthropic: Claude Agent SDK | May 2025 — Agent Teams with bidirectional messaging |
| 11 | Anthropic: Agent Teams | Feb 2026 — 16 parallel agents, 100K-line C compiler demo |
| 12 | OpenAI Agents SDK | Late 2024 (from Swarm) — Agents-as-tools + Handoffs |
| 13 | Google ADK + A2A Protocol | 2025–2026 — Agent-to-Agent protocol, Linux Foundation |

### Research Papers (WP-1)

| # | Title | Source | Date |
|---|-------|--------|------|
| 14 | AdaptOrch: Task-Adaptive Multi-Agent Orchestration | arXiv 2602.16873 | Feb 2026 |
| 15 | The Orchestration of Multi-Agent Systems | arXiv 2601.13671 | Jan 2026 |
| 16 | Agyn: Multi-Agent System for Autonomous SWE | arXiv 2602.01465 | Feb 2026 |
| 17 | SWE-Bench Pro: Long-Horizon SWE Tasks | arXiv 2509.16941 | Sep 2025 |
| 18 | SWE-rebench V2: Language-Agnostic SWE Tasks | arXiv 2602.23866 | Feb 2026 |
| 19 | ProjectGen: Project-Level Code Generation | arXiv 2511.03404 | Nov 2025 |
| 20 | Agentic AI: Comprehensive Survey | arXiv 2510.25445 | Oct 2025 |
| 21 | MACOG: Multi-Agent Co-Generation for IaC | arXiv 2510.03902 | Oct 2025 |
| 22 | AgentMesh: Cooperative Multi-Agent Framework | arXiv 2507.19902 | 2025 |

### Industry Articles (WP-1)

| # | Source | Details |
|---|--------|---------|
| 23 | The Path to OpenHands v1 | all-hands.dev, Nov 2025 |
| 24 | Multi-Agent Framework Wars | dev.to, Mar 2026 |
| 25 | Building LangGraph: First Principles | blog.langchain.com, 2025 |
| 26 | Devin's 2025 Performance Review | cognition-labs.com, 2025 |
| 27 | MCP: Standardizing Agentic Interoperability | JISEM, 2026 |
| 28 | Harness Design for Long-Running Application Development | anthropic.com/engineering, 2025 |

### Local Pattern Sources (WP-2)

| # | Source | Details |
|---|--------|---------|
| 29 | EchoAccess implementation_plan_design | 658 lines, 17-Stage plan with convergence loops |
| 30 | EchoAccess echoaccess_full_implementation | 142 lines, 7-Wave execution |
| 31 | 13 Cursor plan files (2026-03-31 to 2026-04-04) | 98 WPs across research, design, implementation, migration |

### SDLC and Workflow Methodology (WP-3)

| # | Source | Details |
|---|--------|---------|
| 32 | Iterative and Incremental Development in Practice | TheLinuxCode, 2026 |
| 33 | SDLC Models Comparison Guide | NumberAnalytics |
| 34 | 20 SDLC Models | 8ration, 2026 |
| 35 | Comparative Analysis of Software Dev Methodologies | EWADIRECT |
| 36 | Choosing the Right Branching Strategy | Stefan Polyak, Medium |
| 37 | Git Workflow Strategies | Lukas Niessen |
| 38 | Trunk-Based Development vs GitFlow | BirJob, 2026 |
| 39 | CI/CD Pipeline Design Patterns in 2026 | ZeonEdge |
| 40 | CI/CD Pipeline Testing Guide | HelpMeTest, 2026 |
| 41 | CI/CD Pipeline Design Principles | TheLinuxCode, 2026 |
| 42 | CI/CD Pipeline Best Practices | ZTABS, 2026 |
| 43 | Hotfix Workflow | SpecWeave |
| 44 | Hotfixes in GitOps Workflow | OneUptime, 2026 |
| 45 | The Technical Spike Framework | Erwin Hermanto, Medium, 2026 |
| 46 | Engineering Feasibility Spikes | Microsoft Engineering Playbook |
| 47 | Cloud Migration Step-by-Step | AllDaysTech, 2025–2026 |
| 48 | Software Migrations Guide | Ucodice, 2026 |
| 49 | Web Application Security Audit Workflow | InventiveHQ |
| 50 | Secure SDLC: AppSec Tools per Phase | AppSecSanta, 2026 |
| 51 | Plan-Implement-Refactor AI Coding Workflow | Remio.ai |
| 52 | Refactoring Patterns | DeveloperToolkit.ai |
| 53 | AI Agent Orchestration: LangGraph, Temporal | dev.to, 2026 |
| 54 | Composition — Jido Composer v0.5.0 | HexDocs |
| 55 | Data Pipeline Orchestration Pattern | AbstractAlgorithms.dev |

---

*End of Wave 1 Research Synthesis Report. This document serves as the unified foundation for meta-framework architecture design (Phase 7.5–7.7).*
