# T02 Research Report: Agent Orchestration Strategies for DevolaFlow Enhancement

**Task ID:** T02-research-advisor-strategy  
**Team:** Research  
**Date:** 2026-04-11  
**Searches Performed:** 11 web searches + 3 full-page fetches  

---

## Executive Summary

Research into "Claude advisor strategy" reveals that the term does not refer to a single named pattern. Instead, Anthropic and the broader agent-engineering community have converged on a **family of coordination patterns** for multi-agent systems. This report documents **7 distinct strategies/patterns** found across Anthropic's official blog series (Jan-Apr 2026), academic papers (AdaptOrch, AgentOrchestra), and practitioner literature. Each is analyzed for its mechanism, advantages, differences from DevolaFlow's current 4-layer hierarchy, and integration potential.

Key finding: DevolaFlow already implements a strong hierarchical orchestrator-subagent pattern. The highest-value enhancements are: **(1)** adaptive topology selection per-task, **(2)** deterministic lifecycle hooks for quality gates, **(3)** the generator-verifier pattern as a first-class convergence mechanism, **(4)** context-centric decomposition as a formal principle, and **(5)** shared-state collaboration for research-heavy workflows.

---

## Strategy 1: Anthropic's Five Multi-Agent Coordination Patterns

### Source
- **Anthropic Official Blog** (April 10, 2026): "Multi-agent coordination patterns: Five approaches and when to use them"
- URL: https://www.claude.com/blog/multi-agent-coordination-patterns
- Author: Cara Phillips et al.
- **Companion post** (Jan 23, 2026): "Building multi-agent systems: When and how to use them"
- URL: https://www.claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them

### Core Mechanism

Anthropic identifies **five canonical coordination patterns**, each suited to different structural properties of the work:

| Pattern | When to Use | Coordination Model |
|---------|------------|-------------------|
| **Generator-Verifier** | Quality-critical output, explicit evaluation criteria | Loop: generate → evaluate → refine until PASS or max_rounds |
| **Orchestrator-Subagent** | Clear task decomposition, bounded subtasks | Hierarchy: lead decomposes → delegates → synthesizes |
| **Agent Teams** | Parallel, independent, long-running subtasks | Persistent workers: coordinator assigns → workers accumulate context |
| **Message Bus** | Event-driven pipelines, growing agent ecosystem | Pub/sub: agents publish/subscribe to topics, router delivers |
| **Shared State** | Collaborative research, agents share discoveries | Decentralized: agents read/write shared store, no central coordinator |

Key insight from Anthropic: **context-centric decomposition** (divide by what context each agent needs) outperforms **problem-centric decomposition** (divide by type of work). The "telephone game" effect degrades fidelity when agents are split by role (planner, implementer, tester, reviewer) rather than by context boundary.

### Advantages
- Covers the full spectrum from simple (generator-verifier) to complex (shared state)
- Each pattern has clear "when to use" and "where it struggles" guidance
- Hybrid combinations are explicitly supported (e.g., orchestrator + shared state)
- Backed by production deployment experience at Anthropic

### How It Differs from DevolaFlow
DevolaFlow currently implements a **fixed orchestrator-subagent hierarchy** (L0→L1→L2→L3). It does not:
- Support **generator-verifier** as a first-class coordination mode (convergence loops approximate this but are stage-level, not task-level)
- Support **agent teams** with persistent workers that accumulate context across tasks
- Support **message bus** or **shared state** patterns
- Apply **context-centric decomposition** as a formal decision criterion (DevolaFlow decomposes by workflow type → stage primitive → team role)

### Potential Synergies with DevolaFlow's 4-Layer Hierarchy
- L2 Wave could support **agent teams** mode where workers persist across wave iterations
- L1 Stage convergence loops could adopt the **generator-verifier** protocol formally
- A new **shared state** option could be offered for research-heavy workflows (research-only, RDRR)
- The decision framework (context-centric vs problem-centric) could inform DevolaFlow's team assignment logic

### Preliminary Integration Approach

**Generator-Verifier at L2 Wave level:** Extend Wave Agents with a `coordination_mode` field (`orchestrator` | `generator_verifier` | `team`). When `generator_verifier` is selected, the Wave spawns exactly two task agents — a generator and a verifier — and runs the generate→evaluate→refine loop with the existing `max_rounds` parameter. This directly enhances convergence stages (review, test, validate) where the current approach spawns separate tasks without a tight feedback loop.

**Context-Centric Decomposition Advisor:** Add a pre-decomposition step at L1 Stage that classifies planned task boundaries as "context-aligned" or "context-crossing." If a proposed wave splits work that shares heavy context (e.g., implementation + its tests), the advisor recommends merging them into a single task. This could be implemented as a lightweight check in the stage dispatch logic — enumerate planned tasks, check for context overlap (shared files, dependent artifacts), and warn/merge before dispatch.

---

## Strategy 2: AdaptOrch — Task-Adaptive Topology Selection

### Source
- **Paper:** "AdaptOrch: Task-Adaptive Multi-Agent Orchestration in the Era of LLM Performance Convergence"
- arXiv: https://arxiv.org/abs/2602.16873 (February 2026)
- HuggingFace: https://huggingface.co/papers/2602.16873

### Core Mechanism

AdaptOrch dynamically selects among **four canonical topologies** based on task characteristics:
- **Parallel** — for independent subtasks
- **Sequential** — for ordered dependencies
- **Hierarchical** — for delegated subplans
- **Hybrid** — combining multiple approaches

Three key technical contributions:
1. **Performance Convergence Scaling Law** — formalizes when orchestration topology matters more than model selection (LLMs now cluster within 2-5% on benchmarks)
2. **Topology Routing Algorithm** — maps task decomposition DAGs to optimal patterns in O(|V| + |E|) time
3. **Adaptive Synthesis Protocol** — provides termination guarantees and consistency scoring for parallel outputs

### Advantages
- **12-23% improvement** over static single-topology baselines across SWE-bench, GPQA, and RAG tasks
- Works even when using identical underlying models (orchestration > model selection)
- O(|V| + |E|) routing is computationally cheap
- Termination guarantees prevent runaway iteration

### How It Differs from DevolaFlow
DevolaFlow uses a **fixed hierarchical topology** for all 16 workflow types. AdaptOrch argues that topology should be **dynamic per-task**, not fixed per-workflow. A research task within a full-pipeline might benefit from parallel topology, while an implementation task needs sequential, and a review-fix cycle needs a generator-verifier loop — all within the same workflow execution.

### Potential Synergies
- DevolaFlow's Wave layer (L2) is the natural insertion point for topology routing
- The existing `parallel` composition operator in stage primitives is a partial implementation
- Task DAG analysis at dispatch time could select optimal topology per-wave

### Preliminary Integration Approach

**Topology Router at L2 Wave dispatch:** Before a Wave Agent dispatches tasks, it analyzes the task DAG (dependency edges, resource contention, context requirements) and selects the optimal topology. This could be implemented as an extension to the Wave Agent's dispatch logic: (1) Build a mini-DAG of the wave's tasks, (2) Classify edges as dependency (sequential) vs. independent (parallel), (3) Check for context overlap (hierarchical delegation beneficial), (4) Select topology and configure dispatch accordingly. The existing `parallel` and `sequence` composition operators already support this; the addition is making the selection **automatic** based on task properties rather than requiring the L1 Stage to specify it in advance.

**Adaptive Synthesis for parallel outputs:** When multiple tasks complete in parallel, add a synthesis step that scores output consistency before passing results to the gate. If consistency is below threshold, the Wave can trigger a reconciliation task rather than passing conflicting outputs upstream.

---

## Strategy 3: Evaluator-Optimizer (Generator-Verifier Loop)

### Source
- **Anthropic Official Blog** (March 5, 2026): "Common workflow patterns for AI agents—and when to use them"
- URL: https://www.claude.com/blog/common-workflow-patterns-for-ai-agents-and-when-to-use-them
- **AgentPatterns.ai**: "Evaluator-Optimizer Pattern for AI Agent Development"
- URL: https://agentpatterns.ai/agent-design/evaluator-optimizer/
- **Anthropic Official Blog** (April 10, 2026): Generator-Verifier as Pattern 1 in coordination patterns
- URL: https://www.claude.com/blog/multi-agent-coordination-patterns

### Core Mechanism

The evaluator-optimizer separates **generation** from **evaluation** into distinct agent roles:

```
Generator → produces output → Evaluator → {PASS: accept, FAIL: structured feedback} → Generator (refine) → loop
```

Key design elements:
- **Structured feedback:** Evaluator returns JSON with verdict + specific issues (not prose)
- **Termination conditions:** Primary = evaluator PASS; Fallback = max_rounds reached
- **Machine-checkable criteria:** For code, tests provide deterministic termination; for docs, rubrics provide semi-deterministic evaluation
- **Anti-pattern — "early victory":** Verifiers declare success after superficial checks. Mitigation: require comprehensive test runs, negative tests, explicit coverage thresholds

This is described as embodying **"System 2" thinking** — artificial reflection and critique that transforms probabilistic LLM outputs into deterministic, enterprise-grade assets.

### Advantages
- 10-20 percentage point improvement in code generation pass rates (Reflexion framework data)
- Clean separation of concerns: generator focuses on creation, evaluator on quality
- Predictable cost model: typically 2-3 iterations sufficient
- Structured feedback prevents the "telephone game" degradation

### How It Differs from DevolaFlow
DevolaFlow's convergence loops operate at **stage level** (L1) with composite gate scores. The evaluator-optimizer pattern operates at **task level** — a single task can internally loop between generation and evaluation. DevolaFlow currently spawns separate `implement` and `review` tasks in different waves, requiring a full stage-level convergence round to feed review findings back into implementation. This is heavyweight for simple fix-verify cycles.

### Potential Synergies
- DevolaFlow's gate mechanism already computes composite scores — this could be repurposed as the evaluator's quality criteria
- The `refine` stage primitive exists but requires a full stage cycle; a task-level loop would be faster
- Convergence detection (stagnation rules) is already implemented at stage level

### Preliminary Integration Approach

**Task-Level Convergence Mode:** Add an optional `convergence_mode` to Task Agent dispatch that enables internal generate-evaluate loops. When enabled, the task agent: (1) generates output, (2) spawns a lightweight evaluator (using prompt-based or tool-based verification), (3) if FAIL, refines based on structured feedback, (4) terminates on PASS or max_rounds. This operates entirely within the L3 Task Agent's context budget (~8K tokens) using the existing `max_iterations` parameter. The evaluator criteria would be derived from the task's `acceptance_criteria` field, making it automatic. This would dramatically reduce the need for stage-level convergence rounds for straightforward fix-verify cycles, while preserving the full convergence loop for complex cross-task quality issues.

---

## Strategy 4: Deterministic Hooks / Lifecycle Quality Gates

### Source
- **Dotzlaw Consulting**: "Claude Code Hooks: The Deterministic Control Layer for AI Agents"
- URL: https://www.dotzlaw.com/insights/claude-hooks/
- **Dev.to** (2026): "Claude Code Hooks, Subagents & Power Features: The Complete Guide"
- URL: https://dev.to/vibehackers/claude-code-hooks-subagents-power-features-the-complete-guide-2026-c71
- **PixelMojo** (2026): "Claude Code Hooks Reference: All 12 Events"
- URL: https://www.pixelmojo.io/blogs/claude-code-hooks-production-quality-ci-cd-patterns
- **CircleCI Blog**: "What are test hooks in AI-native development?"
- URL: http://blog.circleci.com/blog/test-hooks-ai-development/

### Core Mechanism

Hooks are **system-level enforcement mechanisms** that fire at agent lifecycle events with 100% reliability, compared to prompt-based instructions which achieve only 70-90% compliance. They operate **outside the LLM's reasoning chain**, ensuring critical actions execute regardless of context pressure.

**Handler types:**
1. **Command hooks** — shell scripts receiving JSON event data
2. **HTTP hooks** — POST to external services/CI
3. **Prompt hooks** — single-turn LLM evaluation for fuzzy checks
4. **Agent hooks** — spawn subagents for complex validation

**Key lifecycle events:**
- `PreToolUse` / `PostToolUse` — validate/enforce before and after every tool call
- `Stop` — run test suite at task completion, block if tests fail
- `FileChanged` — trigger linting after every file edit
- `SubagentStart` / `SubagentStop` — enforce subagent constraints
- `TaskCreated` / `TaskCompleted` — enforce task-level quality gates

### Advantages
- **100% compliance** vs 70-90% for prompt-based enforcement
- Operates outside LLM context, so cannot be "forgotten" during long sessions
- Catches issues while agent is in context (faster than CI feedback loops)
- Composable: hooks can trigger other hooks or subagents

### How It Differs from DevolaFlow
DevolaFlow's quality gates operate **between stages** (L1 gate mechanism) and rely on **composite scores** computed from task outputs. There is no mechanism for:
- **Intra-task enforcement** (ensuring a task agent runs linter after every file edit)
- **Pre-dispatch validation** (checking that a task's acceptance criteria are well-formed before dispatch)
- **Deterministic post-completion checks** (automatically running test suites when a task reports completion)

DevolaFlow's P4 (bounded retry) and escalation chain are prompt-based instructions to agents, not system-level enforcement.

### Potential Synergies
- DevolaFlow's escalation severity levels (AUTO_RECOVER, PAUSE, HUMAN_INTERVENE, FULL_ROLLBACK) could be triggered by hooks rather than relying on agent judgment
- The gate mechanism's composite scoring could be triggered as a hook at stage completion
- P1 (dispatcher-not-implementer) could be enforced via PreToolUse hooks rather than relying on prompt compliance

### Preliminary Integration Approach

**Hook Layer at L2/L3 boundary:** Introduce a `hooks` configuration in Wave dispatch that defines deterministic checks at task lifecycle events. Implementation: (1) `on_task_complete` hook runs the test suite and lint checks before accepting task output — if failures, the task is automatically retried (up to P4 limits) without requiring a full convergence round. (2) `on_file_write` hook validates that the file is within the task's `owned_files` set — enforcing P1 at the system level rather than the prompt level. (3) `on_dispatch` hook validates that task acceptance criteria contain at least one testable condition. These hooks would be defined in the wave plan YAML and executed by the Wave Agent's dispatch infrastructure, outside the Task Agent's context window. This converts DevolaFlow's currently prompt-based invariants (P1, P4, P5) into deterministic system-level enforcement.

---

## Strategy 5: Reflection / Self-Critique Pattern

### Source
- **Zylos Research** (March 2026): "AI Agent Reflection and Self-Evaluation Patterns"
- URL: https://zylos.ai/research/2026-03-06-ai-agent-reflection-self-evaluation-patterns
- **arXiv** (March 2026): "ReflexiCoder: Teaching LLMs to Self-Reflect on Generated Code"
- URL: https://arxiv.org/abs/2603.05863v1
- **HopX AI**: "The Reflection Pattern: Building Self-Correcting AI Systems"
- URL: https://hopx.ai/blog/ai-agents/reflection-pattern-self-correcting-ai/

### Core Mechanism

The reflection pattern adds a **generate → reflect → refine** cycle within a single agent:

1. **Generate** — Agent produces output (code, plans, analysis)
2. **Reflect** — Same or separate agent evaluates against criteria (correctness, completeness, style)
3. **Refine** — Agent revises based on self-critique, optionally repeats

**Producer-Critic variant:** Separates generation and critique into distinct agent personas to avoid cognitive bias (single-agent self-review tends to "rubber-stamp" its own work).

**ReflexiCoder results (2026):** RL framework that internalizes reflection achieves 94.51% on HumanEval, 81.80% on MBPP, with ~40% reduction in inference compute.

### Advantages
- Improves code pass rates by 10-20 percentage points (Reflexion framework)
- Self-contained: no external verification infrastructure needed
- Episodic memory across attempts enables learning from mistakes
- Producer-critic separation avoids self-confirmation bias

### How It Differs from DevolaFlow
DevolaFlow's review/refine cycle is **externalized** — separate review tasks in separate waves evaluate implementation tasks. The reflection pattern operates **within a single task's execution**, allowing the implementing agent to self-critique before reporting completion. DevolaFlow has no mechanism for intra-task reflection.

### Potential Synergies
- Could be embedded in L3 Task Agent execution protocol as a mandatory pre-completion step
- Complements the evaluator-optimizer pattern (Strategy 3) at a finer granularity
- Aligns with DevolaFlow's existing `refine` stage primitive but at task level

### Preliminary Integration Approach

**Mandatory Self-Review Step in Task Execution Protocol:** Extend the L3 Task Agent execution protocol with an optional `self_review: true` flag. When enabled, before the task agent reports completion, it: (1) re-reads its own output files, (2) evaluates against the acceptance criteria using a structured self-review prompt, (3) identifies issues and fixes them within the same context window. This is lightweight (no additional agent spawn, no additional context window) and can be enabled selectively for implementation tasks where the acceptance criteria are testable. The key design choice is to use a **distinct evaluation prompt** (not just "check your work") that forces the agent to evaluate from a reviewer's perspective — listing specific criteria and checking each one. This prevents the rubber-stamping problem while staying within the task's ~8K token budget.

---

## Strategy 6: Context Engineering / Adaptive Context Isolation

### Source
- **LangChain Blog**: "Context Engineering for Agents"
- URL: https://blog.langchain.com/context-engineering-for-agents
- **Dev.to** (2026): "Context Engineering: The Complete Guide for AI-Assisted Coding"
- URL: https://dev.to/vibehackers/context-engineering-the-complete-guide-for-ai-assisted-coding-2026-13m6
- **ToolHalla AI** (2026): "Context Engineering for AI Agents: The Complete Guide"
- URL: https://toolhalla.ai/blog/context-engineering-ai-agents-2026
- **Towards Data Science**: "Deep Dive into Context Engineering for AI Agents"
- URL: https://towardsdatascience.com/deep-dive-into-context-engineering-for-ai-agents/

### Core Mechanism

Context engineering treats the agent's information environment as a **first-class optimization target**. Four primary operations:

| Operation | Description |
|-----------|-------------|
| **Write** | Persist information to memory/tools for future retrieval |
| **Select** | Choose which information to include based on task relevance |
| **Compress** | Reduce token count while preserving essential information |
| **Isolate** | Spawn separate context windows to prevent pollution |

**Four context failure modes:**
1. **Context Poisoning** — hallucinations enter context and propagate as ground truth
2. **Context Distraction** — accumulated information overwhelms training-time knowledge (accuracy drops around 32K-64K tokens)
3. **Context Confusion** — irrelevant information influences decisions
4. **Context Clash** — conflicting information across context parts

**Key finding:** Context quality outweighs model capability. Clean, well-structured context on a weaker model outperforms cluttered context on a stronger model.

### Advantages
- Claude Code achieves 5.5x fewer tokens than competitors via aggressive context isolation
- Addresses the "Lost in the Middle" phenomenon where LLMs attend poorly to middle tokens
- Selective loading (tools, skills, data on-demand) reduces initialization cost
- Context compaction automatically triggers near limits, preserving working state

### How It Differs from DevolaFlow
DevolaFlow already implements context isolation (each task gets a fresh context) and has token budgets per layer (L0: ~3K, L1: ~5K, L2: ~4K, L3: ~8K). However:
- DevolaFlow's `context_profiles.yaml` defines **static** budgets per task type, not **adaptive** allocation
- There is no mechanism for **context compaction** when approaching limits
- Predecessor summaries are limited to "3-5 sentences" — a fixed format, not optimized per-task
- The "select" and "compress" operations are implicit, not systematically applied
- No defense against context poisoning (hallucinated outputs from predecessor tasks propagating)

### Potential Synergies
- DevolaFlow's existing `context_injection` structure maps directly to the Write/Select/Compress/Isolate framework
- The `key_facts` requirement in CO-2 (verbatim extraction) already prevents summarization hallucination
- Context profiles could be extended with adaptive allocation based on task complexity

### Preliminary Integration Approach

**Adaptive Context Budget Allocation:** Extend `context_profiles.yaml` with a `budget_strategy` field that can be `fixed` (current behavior) or `adaptive`. In adaptive mode, the context budget is allocated dynamically: (1) Critical sections always receive their full allocation, (2) Predecessor summaries are scaled based on relevance score (how many shared files/interfaces exist between predecessor and current task), (3) Rules and behavioral sections are compressed when the task is well-defined (high clarity score) and expanded when ambiguous. Implementation: add a `context_allocator.py` module that takes the task dispatch, computes relevance scores for each context section, and produces an optimized context injection within the token budget. This directly enhances CO-3 (Context Token Budgets) by making the allocation dynamic rather than static.

**Context Poisoning Defense:** Add a `predecessor_validation` step at L2 Wave dispatch that cross-checks predecessor artifact summaries against the actual artifact files. If summaries contain claims not supported by the artifacts (detected via simple keyword/metric verification), the summary is regenerated from the artifact directly. This prevents hallucinated predecessor summaries from poisoning downstream tasks.

---

## Strategy 7: AgentOrchestra — Dynamic Tool Creation via TEA Protocol

### Source
- **arXiv** (June 2025, v3 updated 2026): "AgentOrchestra: A Hierarchical Multi-Agent Framework for General-Purpose Task Solving"
- URL: https://arxiv.org/abs/2506.12508v3
- HuggingFace: https://huggingface.co/papers/2506.12508

### Core Mechanism

AgentOrchestra introduces the **Tool-Environment-Agent (TEA) Protocol** which treats environments, agents, and tools as first-class resources. Its key innovation is the **MCP Manager Agent** that enables:
- **Dynamic tool creation** — agents can create new tools at runtime to solve novel problems
- **Tool retrieval** — previously created tools are stored and retrieved for reuse
- **Tool reuse** — successful tool compositions are cached and offered to future tasks

Architecture: Central planning agent decomposes objectives → specialized sub-agents with general programming tools + specialized capabilities → MCP Manager enables tool evolution.

**Benchmark performance:** 83.39% on GAIA benchmark (state-of-the-art for general-purpose agents).

### Advantages
- Tool evolution means the system gets more capable over time
- Sub-agents aren't limited to pre-defined tool sets
- TEA Protocol provides unified resource management
- Hierarchical planning + modular agents = scalable architecture

### How It Differs from DevolaFlow
DevolaFlow assigns **fixed tool sets per team** (Research gets WebSearch/Read/Glob, Implement gets Write/Shell/StrReplace, etc.). AgentOrchestra allows tools to be **dynamically created, composed, and shared** across agents. DevolaFlow has no mechanism for:
- Runtime tool creation
- Tool reuse across tasks/workflows
- Adaptive tool selection based on task needs (beyond team assignment)

### Potential Synergies
- DevolaFlow's MCP integration (already referenced in SKILL.md context) could be extended with an MCP Manager pattern
- Tool recipes created by one task could be stored and offered to similar future tasks
- The team→tool mapping could become a default rather than a constraint

### Preliminary Integration Approach

**Tool Recipe Catalog:** Add a `tool_recipes/` artifact directory where task agents can register successful multi-tool compositions. Format: YAML files with `name`, `description`, `tool_sequence`, `preconditions`, `expected_output`. At task dispatch time, the Wave Agent scans the catalog for relevant recipes and includes them in the task's context as "known approaches." This is a lightweight version of dynamic tool creation that works within DevolaFlow's existing artifact-based communication (P5) without requiring runtime tool compilation. Over time, the catalog grows as workflows execute, making the system progressively more capable — similar to AgentOrchestra's tool evolution but using artifacts rather than runtime MCP tool creation.

---

## Comparison Matrix

| Dimension | Anthropic 5 Patterns | AdaptOrch | Evaluator-Optimizer | Deterministic Hooks | Reflection | Context Engineering | AgentOrchestra |
|---|---|---|---|---|---|---|---|
| **Integration Effort** | Medium | Medium | Low | Medium | Low | Medium | High |
| **Token Cost Impact** | +3-10x (multi-agent) | Neutral (routing only) | +2-3x per loop | Neutral | +10-20% per task | -20-50% (optimization) | +15-25% (tool mgmt) |
| **Quality Improvement** | High (right pattern → right problem) | 12-23% over static | 10-20pp code pass rate | 100% vs 70-90% compliance | 10-20pp code pass rate | Indirect (prevents degradation) | 83% GAIA (SoTA) |
| **DevolaFlow Layer** | L1 (Stage) + L2 (Wave) | L2 (Wave dispatch) | L3 (Task internal) | L2/L3 boundary | L3 (Task internal) | All layers (L0-L3) | L2 (Wave) + artifacts |
| **Current DevolaFlow Gap** | Only uses orchestrator-subagent | Fixed topology per workflow | Stage-level only, not task-level | All enforcement is prompt-based | No intra-task reflection | Static budgets, no compaction | Fixed tool sets per team |
| **Implementation Priority** | HIGH (foundational framework) | HIGH (directly addresses topology rigidity) | HIGH (low effort, high impact) | MEDIUM (infrastructure change) | MEDIUM (easy to add incrementally) | MEDIUM (extends existing CO work) | LOW (most complex, least urgent) |

---

## Recommended Integration Priorities

### Tier 1 — High Value, Achievable Now

1. **Generator-Verifier at Wave Level** (from Strategies 1 + 3)
   - Add `coordination_mode: generator_verifier` to Wave dispatch
   - Tight generate→evaluate→refine loop within a wave, using existing max_rounds
   - Directly reduces stage-level convergence round count

2. **Adaptive Topology Selection** (from Strategy 2)
   - Add DAG analysis at L2 Wave dispatch to auto-select parallel/sequential/hierarchical
   - Extend existing `parallel` and `sequence` composition operators
   - Expected: 12-23% improvement on diverse workflows

3. **Task-Level Self-Review** (from Strategy 5)
   - Add `self_review: true` flag to task dispatch
   - Mandatory structured self-evaluation before completion report
   - Low cost (~10-20% token overhead), high quality improvement

### Tier 2 — Medium Value, Moderate Effort

4. **Deterministic Hook Infrastructure** (from Strategy 4)
   - System-level enforcement of P1, P4, P5 invariants
   - `on_task_complete` hooks for automatic test/lint verification
   - Requires infrastructure changes to dispatch/report pipeline

5. **Adaptive Context Budget Allocation** (from Strategy 6)
   - Dynamic context allocation based on task properties
   - Predecessor summary relevance scoring
   - Extends existing context_profiles.yaml and CO-3

### Tier 3 — Future Investigation

6. **Shared State for Research Workflows** (from Strategy 1)
   - Research-only and RDRR workflows could use shared knowledge base
   - Agents write findings to shared store, read each other's discoveries
   - Requires new coordination pattern beyond current hierarchy

7. **Tool Recipe Catalog** (from Strategy 7)
   - Cross-task/workflow tool composition reuse
   - Artifact-based storage, included in dispatch context
   - Progressive capability improvement over time

---

## Key Source URLs

| # | Source | URL | Date |
|---|--------|-----|------|
| 1 | Anthropic: Multi-agent coordination patterns | https://www.claude.com/blog/multi-agent-coordination-patterns | 2026-04-10 |
| 2 | Anthropic: Building multi-agent systems | https://www.claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them | 2026-01-23 |
| 3 | Anthropic: Common workflow patterns | https://www.claude.com/blog/common-workflow-patterns-for-ai-agents-and-when-to-use-them | 2026-03-05 |
| 4 | AdaptOrch paper | https://arxiv.org/abs/2602.16873 | 2026-02 |
| 5 | AgentOrchestra paper | https://arxiv.org/abs/2506.12508v3 | 2025-06 (v3 2026) |
| 6 | AgentPatterns.ai: Evaluator-Optimizer | https://agentpatterns.ai/agent-design/evaluator-optimizer/ | 2026 |
| 7 | Dotzlaw: Claude Code Hooks | https://www.dotzlaw.com/insights/claude-hooks/ | 2026 |
| 8 | AAIA: Hierarchical Agent Patterns | https://aaia.app/research/hierarchical-agent-patterns | 2026 |
| 9 | LangChain: Context Engineering | https://blog.langchain.com/context-engineering-for-agents | 2026 |
| 10 | Zylos: Reflection Patterns | https://zylos.ai/research/2026-03-06-ai-agent-reflection-self-evaluation-patterns | 2026-03 |
| 11 | CircleCI: Test Hooks | http://blog.circleci.com/blog/test-hooks-ai-development/ | 2026 |
| 12 | PixelMojo: Claude Hooks Reference | https://www.pixelmojo.io/blogs/claude-code-hooks-production-quality-ci-cd-patterns | 2026 |
| 13 | Eesel AI: Claude Code Multiple Agent Systems | https://www.eesel.ai/en/blog/claude-code-multiple-agent-systems-complete-2026-guide | 2026 |
| 14 | ReflexiCoder paper | https://arxiv.org/abs/2603.05863v1 | 2026-03 |
| 15 | Atoms.dev: Planner-Executor Pattern | https://atoms.dev/insights/the-planner-executor-agent-pattern-a-comprehensive-review/ | 2026 |

---

## Appendix: Search Queries Performed

1. `Claude Code advisor strategy agent pattern 2026`
2. `Anthropic Claude agent orchestration patterns multi-agent 2026`
3. `advisor vs executor agent pattern LLM coding workflow`
4. `LLM agent planning advisor pattern multi-agent hierarchy 2026`
5. `Claude system prompt best practices agent hierarchy workflow orchestration`
6. `AdaptOrch adaptive topology selection multi-agent parallel sequential hierarchical 2026`
7. `evaluator optimizer agent pattern iterative refinement convergence loop LLM 2026`
8. `context engineering LLM agent context window optimization isolation strategy 2026`
9. `AgentOrchestra MCP manager dynamic tool creation hierarchical framework GAIA benchmark`
10. `agent reflection pattern inner monologue self-critique LLM coding 2026`
11. `deterministic hooks agent lifecycle automation CI quality gate pattern 2026`
