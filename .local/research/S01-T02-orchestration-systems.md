# S01-T02: Deep-Dive Research — Orchestration Systems

**Task:** Deep-dive research on get-shit-done and edict repos
**Team:** Research | **Date:** 2026-04-11
**Status:** Complete

---

## 1. get-shit-done (GSD)

**Repo:** https://github.com/gsd-build/get-shit-done
**Stars:** ~15K+ | **Language:** JavaScript/Markdown | **License:** MIT
**Clone status:** Success (shallow clone to /home/agent/reference/get-shit-done)

### 1.1 Orchestration Architecture

GSD is a **meta-prompting framework** for spec-driven development. It layers on top of AI coding agents (Claude Code, Gemini CLI, Codex, Copilot, Cursor, etc.) to provide structured orchestration.

**Architecture layers (4-tier, top-down):**

| Layer | Components | Responsibility |
|-------|-----------|----------------|
| Command | `commands/gsd/*.md` (69 total) | User-facing entry points (slash commands) |
| Workflow | `workflows/*.md` (68 total) | Orchestration logic — loads context, spawns agents, manages state |
| Agent | `agents/*.md` (24 total) | Specialized roles with fresh context windows |
| CLI Tools | `bin/gsd-tools.cjs` + 19 modules | State, config, phase, roadmap, verify, template operations |

**Core pipeline:** `new-project → discuss-phase → plan-phase → execute-phase → verify-work → ship`

**Key architectural patterns:**
- **Thin orchestrators, heavy agents:** Workflows never do heavy lifting; they spawn specialized agents with focused prompts. Each agent gets a fresh 200K–1M context window.
- **File-based state:** All state lives in `.planning/` as human-readable Markdown/JSON. No database, no server. Survives context resets.
- **Orchestrator→Agent pattern:** Load context via `gsd-tools.cjs init` → Resolve model → Spawn agent with prompt + context + tools → Collect result → Update state.

### 1.2 Gate/Quality Enforcement Mechanisms

GSD uses a **4-type gate taxonomy** (defined in `references/gates.md`):

| Gate Type | Purpose | Behavior | Examples |
|-----------|---------|----------|----------|
| **Pre-flight** | Validate preconditions before starting | Block entry if unmet; no partial work | Check REQUIREMENTS.md exists before planning |
| **Revision** | Evaluate output quality, loop if insufficient | Loop back to producer with feedback (bounded by cap) | Plan-checker reviewing PLAN.md (max 3 iterations) |
| **Escalation** | Surface unresolvable issues to human | Pause workflow, present options, wait for input | Revision loop exhausted after 3 iterations |
| **Abort** | Terminate to prevent damage/waste | Stop immediately, preserve state, report reason | Context window critically low during execution |

**Additional quality mechanisms:**
- `gsd-plan-checker` agent validates plans before execution (max 3 revision iterations)
- `gsd-verifier` checks phase deliverables against success criteria post-execution
- `gsd-integration-checker` catches cross-phase integration issues
- `gsd-nyquist-auditor` validates verification coverage (sampling audit)
- Post-merge test gate catches cross-plan conflicts after worktree merges
- Regression gate runs prior phases' tests before verification
- Schema drift detection flags ORM changes missing migrations

### 1.3 Wave/Phase Scheduling and DAG Handling

**Wave execution model:** Plans within a phase are grouped into dependency waves.

```
Wave Analysis:
  Plan 01 (no deps)      ─┐
  Plan 02 (no deps)      ─┤── Wave 1 (parallel)
  Plan 03 (depends: 01)  ─┤── Wave 2 (waits for Wave 1)
  Plan 04 (depends: 02)  ─┘
  Plan 05 (depends: 03,04) ── Wave 3 (waits for Wave 2)
```

**Key wave features:**
- Plans are automatically grouped based on `depends_on` frontmatter in PLAN.md files
- Within a wave: parallel execution if `parallelization=true` (via git worktrees)
- Across waves: strictly sequential (Wave N+1 waits for Wave N)
- Intra-wave file overlap detection: if two plans share `files_modified`, they run sequentially
- Post-wave worktree cleanup with orchestrator-owned file protection (STATE.md, ROADMAP.md)
- STATE.md file locking with `O_EXCL` atomic creation for concurrent writes
- Cross-AI delegation support (pipe prompts to external AI runtimes via stdin)

### 1.4 Inter-Agent Communication

- **Agent contracts** define completion markers per agent (e.g., `## PLANNING COMPLETE`, `## VERIFICATION PASSED`)
- **Handoff contracts** define required fields between stages (e.g., Planner→Executor via PLAN.md frontmatter + XML structure)
- **No direct agent-to-agent communication** — all coordination goes through the orchestrator workflow
- **Artifact-based:** Agents produce files (PLAN.md, SUMMARY.md, VERIFICATION.md) that downstream agents consume
- **Model resolution:** Orchestrators call `gsd-tools.cjs resolve-model <agent-name>` before spawning, supporting 5 profiles: quality, balanced, budget, adaptive, inherit

### 1.5 State Management and Artifacts

**Core artifacts (in `.planning/`):**

| Artifact | Purpose |
|----------|---------|
| PROJECT.md | Project vision, constraints, decisions |
| REQUIREMENTS.md | Scoped v1/v2 requirements with phase traceability |
| ROADMAP.md | Phase breakdown with status tracking |
| STATE.md | Living memory: position, decisions, blockers, metrics |
| config.json | Workflow configuration |
| PLAN.md (per plan) | Atomic task with XML structure, verification steps |
| SUMMARY.md (per plan) | Execution outcome, commits, self-check |
| VERIFICATION.md (per phase) | Post-execution verification report |

**Session management:** `pause-work` writes HANDOFF.json, `resume-work` restores from it. STATE.md tracks last completed plan, current wave, pending checkpoints.

### 1.6 Security / Prompt Injection Defenses

- `gsd-prompt-guard.js` (PreToolUse hook): scans Write/Edit operations targeting `.planning/` files for prompt injection patterns (role override, instruction bypass, system tag injection). Advisory-only (does not block).
- `security.cjs` module: path traversal prevention, prompt injection detection, safe JSON parsing, shell argument validation.
- `gsd-read-guard.js`: prevents Edit/Write on files not yet read in session.
- CI-ready injection scanner (`prompt-injection-scan.test.cjs`) scans all agent/workflow/command files.

### 1.7 DevolaFlow Overlap Analysis

| Feature | DevolaFlow | GSD | Overlap |
|---------|-----------|-----|---------|
| Multi-layer hierarchy | 4-layer (L0–L3) | 4-layer (Command→Workflow→Agent→CLI) | **High** — same conceptual layers |
| Gate mechanism | Composite scoring (quality_score, composite_score) | 4-type taxonomy (pre-flight/revision/escalation/abort) | **Medium** — different approaches; DevolaFlow is formula-based, GSD is behavioral |
| Wave scheduling | Wave coordination modes in SKILL.md | Dependency-based wave grouping with parallel worktrees | **High** — GSD has more mature execution |
| Context isolation | Context profiles per task type | Fresh context window per agent | **Medium** — DevolaFlow is more granular (token budgets per section) |
| Convergence loops | detect_stagnation(), compute_trend() | Plan-checker revision loop (max 3) | **Medium** — DevolaFlow tracks score trends; GSD uses iteration caps |
| Lifecycle hooks | v3.8.0 hooks | 9 hooks (statusline, context-monitor, prompt-guard, etc.) | **High** — GSD hooks are more mature and numerous |
| Model profiles | N/A (single model assumption) | 5 profiles (quality/balanced/budget/adaptive/inherit) with per-agent overrides | **Low** — GSD is far ahead |
| Prompt injection defense | N/A | Multi-layer defense (prompt-guard hook, security.cjs, CI scanner) | **None** — DevolaFlow lacks this |

**DevolaFlow Relevance Score: 4/5**

GSD is the most architecturally similar system to DevolaFlow. Its spec-driven dispatch, wave execution, and gate taxonomy directly map to DevolaFlow concepts.

---

## 2. edict (三省六部)

**Repo:** https://github.com/cft0808/edict
**Stars:** ~14.9K | **Language:** Python/JavaScript | **License:** MIT
**Clone status:** Failed (network timeout); analyzed via web fetch of README.md and docs/task-dispatch-architecture.md (~55K of documentation read)

### 2.1 Orchestration Architecture

Edict implements a **multi-agent orchestration system** modeled after China's Tang Dynasty imperial government (三省六部 / Three Departments and Six Ministries). It runs on OpenClaw and coordinates 12 specialized AI agents.

**Agent hierarchy:**

```
User (皇上) → Taizi (太子, triage) → Zhongshu (中书省, planning)
  → Menxia (门下省, mandatory review) → Shangshu (尚书省, dispatch)
  → Six Ministries (六部, parallel execution) → Report back
```

| Agent | Role | Analog |
|-------|------|--------|
| 太子 (taizi) | Message triage — chat vs. work order | L0 dispatcher |
| 中书省 (zhongshu) | Planning, requirement decomposition | L1 stage planner |
| 门下省 (menxia) | Mandatory quality review (can reject/block) | Gate mechanism |
| 尚书省 (shangshu) | Task dispatch and coordination | L2 wave coordinator |
| 六部 (6 ministries) | Parallel domain execution | L3 task agents |
| 吏部 (libu_hr) | Agent management, HR | Meta-agent |
| 早朝官 (zaochao) | Daily briefing, news aggregation | Utility agent |

### 2.2 Gate/Quality Enforcement Mechanisms

**Institutional review (门下省/Menxia)** — the core innovation:

- Every plan from Zhongshu MUST pass through Menxia review. Not optional, not a plugin — it's architectural.
- Menxia can **approve (准奏)** or **reject/block (封驳)** plans.
- Rejection sends the plan back to Zhongshu for revision. Loop bounded to 3 rounds.
- After 3 rejections, escalation to Shangshu for coordination.

**State machine enforcement:**
- 9 states: Pending → Taizi → Zhongshu → Menxia → Assigned → Doing → Review → Done/Cancelled
- `kanban_update.py` enforces `_VALID_TRANSITIONS` — illegal state jumps are rejected and logged.
- Terminal states (Done/Cancelled) are immutable.

**Permission matrix (strict inter-agent communication):**
- Defined in `openclaw.json` via `allowAgents` per agent.
- Taizi can only call Zhongshu. Zhongshu can only call Menxia/Shangshu. Shangshu can call all six ministries. Six ministries cannot call anyone externally.
- Code-level enforcement via `can_dispatch_to()` function.

### 2.3 Wave/Phase Scheduling and DAG Handling

**Scheduling system (4-stage progressive recovery):**

| Stage | Trigger | Action |
|-------|---------|--------|
| **Retry** | `elapsed > stallThreshold` AND `retryCount < maxRetry` | Re-dispatch to current agent |
| **Escalation L1** | Retry exhausted | Wake Menxia for coordination |
| **Escalation L2** | L1 did not resolve | Wake Shangshu for coordination |
| **Auto-rollback** | L2 exhausted AND `autoRollback=true` | Restore task to snapshot state, re-dispatch |

**Scheduling metadata per task:**
- `stallThresholdSec`: 180 (default)
- `maxRetry`: 1
- `escalationLevel`: 0–2
- `snapshot`: saved state for rollback
- Scheduler scan runs every 60 seconds

**DAG handling:**
- `orchestrator_worker.py` handles DAG-based task decomposition and dependency resolution
- `dispatch_worker.py` supports parallel execution with exponential backoff retry and resource locking
- Tasks within Shangshu dispatch can run in parallel across multiple ministries

### 2.4 Inter-Agent Communication

**Event-driven architecture:**
- **Redis Streams EventBus** (`event_bus.py`): publish/subscribe for inter-service communication
- **Outbox Relay** (`outbox_relay.py`): transactional outbox pattern for reliable event delivery (at-least-once semantics)
- **Event structure:** `{event_id, trace_id, timestamp, topic, event_type, producer, payload, meta}`
- **Key topics:** `task.created`, `task.planning`, `task.review.request`, `task.review.result`, `task.dispatch`, `agent.thoughts`, `agent.todo.update`, `task.status`, `heartbeat`
- **WebSocket subscriptions** for real-time dashboard updates with partial streaming

**Data fusion (3-layer activity stream):**
1. `flow_log` — state transition records (Zhongshu → Menxia)
2. `progress_log` — agent real-time work reports with token/cost/elapsed metrics
3. `session JSONL` — agent internal thinking, tool calls, conversation history

### 2.5 State Management and Artifacts

**Task schema (JSON-based):**
- `id`, `title`, `official`, `org`, `state`, `priority`, `block`, `reviewRound`
- `flow_log[]`: complete state transition chain
- `progress_log[]`: agent work reports with todos snapshots and resource consumption
- `_scheduler{}`: dispatch metadata (retry count, escalation level, snapshot for rollback)
- `output`, `ac` (acceptance criteria)

**Observability (Military Cabinet Dashboard — 10 panels):**
- Kanban board with status columns, department filter, full-text search
- Agent health monitoring (heartbeat badges: active/stalled/alert)
- Memorial archive (completed tasks with 5-stage timeline)
- Template library (9 preset templates with parameter forms)
- Token consumption leaderboard
- Model configuration per agent (hot-swap LLM)
- Skill management (view/add skills per agent)
- Court discussion (multi-agent debate on topics)

### 2.6 DevolaFlow Overlap Analysis

| Feature | DevolaFlow | Edict | Overlap |
|---------|-----------|-------|---------|
| Multi-layer hierarchy | 4-layer (L0–L3) | 5-layer (User→Taizi→Sansheng→Shangshu→Liubu) | **High** — similar layering |
| Gate mechanism | Composite scoring with configurable profiles | Institutional mandatory review (Menxia) with reject/approve binary | **Medium** — Edict's is simpler but architecturally enforced |
| Convergence loops | Score-based stagnation detection | State machine with bounded review rounds (max 3) + auto-rollback | **Medium** — different approach, same goal |
| Wave coordination | Wave modes in SKILL.md | Parallel dispatch to 6 ministries via Shangshu | **Low** — Edict is less sophisticated for wave scheduling |
| Inter-agent communication | Artifact-based (files) | Event-driven (Redis Streams + Outbox) | **Low** — fundamentally different paradigms |
| Permission control | Context isolation via profiles | Strict permission matrix (`allowAgents`) | **Medium** — Edict has explicit agent-to-agent access control |
| State management | File-based (YAML/Markdown) | JSON-based with 3-layer activity fusion | **Low** — different storage, similar purpose |
| Observability | Reporter module (YAML/Markdown reports) | Real-time Kanban dashboard (10 panels, WebSocket) | **Low** — Edict far ahead in observability |
| Lifecycle hooks | v3.8.0 hooks system | Event-driven hooks via EventBus | **Medium** — different mechanisms |
| Model profiles | N/A | Per-agent LLM hot-swap via dashboard | **None** — Edict has runtime model switching |
| Scheduling/retry | max_rounds ceiling in convergence | 4-stage progressive recovery (retry→escalate→escalate→rollback) | **Medium** — Edict is more sophisticated |

**DevolaFlow Relevance Score: 3/5**

Edict's institutional review mechanism and event-driven architecture offer novel patterns, but its tight coupling to OpenClaw and different communication paradigm (event bus vs. artifact files) limits direct integration potential.

---

## 3. Integration Ideas

### 3.1 From GSD (get-shit-done)

| # | Integration Idea | Estimated Effort | Impact |
|---|-----------------|-----------------|--------|
| 1 | **Adopt 4-type gate taxonomy** — Replace DevolaFlow's single gate evaluation with GSD's pre-flight/revision/escalation/abort classification. Each DevolaFlow gate type (`standard`, `convergence`, `passthrough`, `acceptance_readiness`) maps to one or more GSD types. Add gate type selection heuristic: "Start with pre-flight. If check happens after work, it's revision. If revision can't resolve, escalate. If continuing is dangerous, abort." | **Medium** (2–3 days) — Extend `gate/scorer.py` with gate type classification; update `evaluate_gate()` to route differently per type; add pre-flight checks to stage dispatch. | High — clearer failure handling, reduces ambiguous gate outcomes |
| 2 | **Add prompt injection defense hooks** — Port GSD's `gsd-prompt-guard.js` pattern to DevolaFlow's lifecycle hooks system. Scan dispatched task prompts and status reports for injection patterns (role override, instruction bypass, system tag injection) before they enter agent context. | **Low** (1 day) — Add a `pre_dispatch` hook that applies regex patterns from GSD's `INJECTION_PATTERNS` list against `TaskDispatch` and `StatusReport` YAML content. | Medium — defense-in-depth against prompt injection in multi-agent workflows |
| 3 | **Model profiles per agent role** — Implement GSD's model profile system (quality/balanced/budget/adaptive/inherit) in DevolaFlow. Map to the 4-layer hierarchy: L0/L1 use stronger models (opus), L2 uses balanced, L3 varies by task type. Allow per-agent overrides in `context_profiles.yaml`. | **Medium** (2–3 days) — Add `model_profiles` section to `context_profiles.yaml`; extend `TaskDispatch` schema with `model` field; add profile resolution logic. | High — enables cost optimization without quality sacrifice |
| 4 | **Agent completion contracts** — Formalize agent completion detection using GSD's agent contract pattern. Define expected completion markers per team role (Research: `## RESEARCH COMPLETE`, Implementation: `## IMPLEMENTATION COMPLETE`) and structured handoff schemas (required fields per artifact type). | **Low** (1 day) — Add `agent_contracts.yaml` schema to `workflow-system/agent/`; document required completion markers and handoff fields per team. | Medium — reduces ambiguity in multi-agent handoffs |
| 5 | **Context window awareness for dispatch** — Port GSD's adaptive context enrichment (500K+ models get richer prompts, <200K models get thinned prompts). Integrate with DevolaFlow's existing context profiles by adding a `context_window` parameter that modulates which sections are included. | **Low** (1 day) — Add `context_window` field to dispatch; extend `task_adaptive_selector.py` to adjust token budgets based on available window size. | Medium — better utilization of large-context models |

### 3.2 From Edict (三省六部)

| # | Integration Idea | Estimated Effort | Impact |
|---|-----------------|-----------------|--------|
| 1 | **Mandatory pre-execution review stage** — Adapt Edict's Menxia (门下省) pattern as a mandatory review gate between DevolaFlow's planning and execution stages. Unlike the current optional convergence gate, this would be architectural: no plan proceeds to execution without passing a dedicated review agent. Implement as a new gate type `institutional_review` with approve/reject binary outcome and bounded retry (max 3 rounds). | **Medium** (2–3 days) — Add `institutional_review` to `GateType`; create new `evaluate_institutional_review()` in `scorer.py`; wire into stage transitions between plan and execute stages. | High — prevents low-quality plans from reaching execution, catches issues earlier |
| 2 | **Event-driven state transitions with audit trail** — Adapt Edict's event bus pattern to DevolaFlow's artifact-based communication. Instead of replacing artifacts, add an event log (`workflow_events.yaml`) that records every state transition, gate verdict, and agent action with timestamp, source, target, and rationale. This creates the "complete audit trail" that Edict achieves with its 3-layer activity fusion. | **Medium** (2–3 days) — Add `WorkflowEvent` dataclass to `gate/models.py`; create `event_log.py` module that appends events to `workflow_events.yaml`; hook into `evaluate_gate()`, stage transitions, and dispatch. | Medium — improves observability and debugging of complex workflows |
| 3 | **Progressive failure recovery (retry→escalate→rollback)** — Adapt Edict's 4-stage scheduling pattern to DevolaFlow's convergence loop. Currently, DevolaFlow detects stagnation and escalates. Edict adds: (a) automatic retry with the same agent, (b) two levels of escalation (first to peer, then to parent), (c) automatic rollback to last known good state. Add `_scheduler` metadata to `ConvergenceRound` tracking retry count, escalation level, and state snapshot. | **High** (3–5 days) — Extend `ConvergenceRound` with scheduler fields; add `progressive_recovery()` to `convergence.py`; create state snapshot/restore logic; integrate with `evaluate_gate()` escalation path. | High — makes DevolaFlow more resilient to agent failures |
| 4 | **Strict inter-agent permission matrix** — Adapt Edict's `allowAgents` pattern to DevolaFlow's team-based architecture. Define which agent teams can dispatch to which other teams. For example, Research agents can only produce artifacts consumed by Design agents; Implementation agents cannot modify Research artifacts. Enforce at dispatch time. | **Low** (1–2 days) — Add `permission_matrix` to `context_profiles.yaml` or a new `team_permissions.yaml`; add validation check in dispatch logic. | Medium — prevents unauthorized cross-team interactions |

---

## 4. Comparative Summary

| Dimension | GSD | Edict | DevolaFlow |
|-----------|-----|-------|------------|
| **Philosophy** | Meta-prompting for solo devs; complexity hidden, simple UX | Imperial governance metaphor; institutional checks and balances | Composable workflow meta-framework; configurable profiles |
| **Hierarchy depth** | 4 layers (Command→Workflow→Agent→CLI) | 5 layers (User→Taizi→Sansheng→Shangshu→Liubu) | 4 layers (Project→Stage→Wave→Task) |
| **Gate approach** | Behavioral taxonomy (pre-flight/revision/escalation/abort) | Institutional mandatory review (binary approve/reject) | Formula-based scoring (composite_score >= threshold) |
| **Communication** | File-based artifacts + completion markers | Event-driven (Redis Streams + Outbox) | File-based artifacts (YAML schemas) |
| **Scheduling** | Wave-based DAG with worktree isolation | 4-stage progressive recovery | Convergence loop with stagnation detection |
| **Observability** | Hooks (statusline, context monitor) | Real-time Kanban dashboard (10 panels) | YAML/Markdown reports |
| **Security** | Multi-layer prompt injection defense | Permission matrix enforcement | Context isolation (token budgets) |
| **Model management** | 5 profiles + per-agent overrides | Per-agent hot-swap via dashboard | N/A (planned) |
| **Maturity** | Very mature (v1.34.0, 160+ tests, 15K+ stars) | Growing (Phase 2, ~15K stars) | Active development (v3.8.0) |

---

## 5. Key Takeaways for DevolaFlow

1. **Gate taxonomy is complementary, not competing.** DevolaFlow's formula-based scoring and GSD's behavioral taxonomy serve different purposes. DevolaFlow should adopt the taxonomy for *routing* (what happens on failure) while keeping composite scoring for *evaluation* (pass/fail determination).

2. **Mandatory review is the highest-impact missing pattern.** Both GSD (plan-checker with max 3 iterations) and Edict (Menxia institutional review) enforce pre-execution quality gates. DevolaFlow's current gate is post-execution focused. Adding a pre-execution review gate would catch more issues earlier and at lower cost.

3. **Prompt injection defense is a gap.** GSD's multi-layer defense (hook + library + CI scanner) is mature and directly applicable. DevolaFlow processes YAML messages between agent layers — these are potential injection vectors that need scanning.

4. **Model profiles are table stakes.** Both GSD and Edict support per-agent model selection. DevolaFlow should add this to its context profiles system to enable cost optimization.

5. **Event-driven observability enhances file-based state.** Edict's 3-layer activity fusion (flow_log + progress_log + session JSONL) provides far richer debugging data than DevolaFlow's current report generation. Adding an event log alongside existing artifacts would improve debuggability without changing the core architecture.

6. **Progressive failure recovery is more robust than binary escalation.** DevolaFlow's current stagnation → escalate path is two-stage. Edict's retry → escalate L1 → escalate L2 → rollback pattern is more resilient and recovers automatically from common failures (agent crashes, transient errors).
