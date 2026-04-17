---
id: "agent/SKILL"
version: "7.0.2"
purpose: >
  Entry point for the DevolaFlow workflow orchestration skill.
  Orchestrate multi-stage software workflows using a 4-layer agent hierarchy
  with gate mechanisms, convergence loops, and context-isolated task delegation.
triggers:
  - "implement feature"
  - "build from scratch"
  - "fix bug"
  - "refactor code"
  - "migrate system"
  - "full pipeline"
  - "hotfix"
  - "workflow orchestration"
  - "run workflow"
  - "update devola"
  - "update_devola"
  - "/update-devola"
tier: 1
token_estimate: 2800
last_updated: "2026-04-16"
name: devola-flow
description: >
  Use when orchestrating multi-file software tasks, implementing features,
  fixing bugs, refactoring, or running any multi-step development workflow
  that benefits from structured dispatch, quality gates, and context-isolated
  subagents.
---

> **Now Using DevolaFlow v7.0.2**

# DevolaFlow

## Version & Update

**Current version:** 7.0.2 — Check: `curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py | grep '__version__'`
If newer: `pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git`
Only check when user explicitly requests via "update devola" / "update_devola" / "/update-devola".

## Quick Action Decision

| Complexity | Signal | Action |
|-----------|--------|--------|
| **Trivial** | Single file, < 20 lines, obvious fix | Execute directly — P1 waived for minimal edits |
| **Simple** | 1-3 files, clear scope, < 1 hour | Dispatch **single Task Agent** via `Task` tool — no multi-stage workflow |
| **Standard** | 3-10 files, needs design or review | Full hierarchy: dispatch stages via `Task` tool |
| **Complex** | 10+ files, cross-cutting, multi-day | Full hierarchy with strict gate profile |

**Rule**: Match ceremony to complexity. **P1**: For Simple+ tasks, always delegate work to Task Agents — never implement directly.

## Mode Awareness

**Detection (priority order):**
1. `<system_reminder>` contains "Plan mode is active" → **PLAN MODE**
2. `SwitchMode` tool available and current mode is `plan` → **PLAN MODE**
3. User explicitly says "build a plan" / "plan this" / "design first" → **PLAN MODE**
4. Otherwise → **AGENT MODE** (default, full orchestration). **v6.1.5+ runtime hook:** `select_context(plan_mode=True)` (or env `DEVOLAFLOW_PLAN_MODE=1`) escalates plan-relevant sections (`agent_hierarchy`, `decomposition_gate`, `rationalization_prevention`) to `critical` and upgrades `model_hint` to `quality`.

### PLAN MODE — Design the Plan, Do NOT Execute

**You are L0 (Project Agent), designing an execution plan.** The plan must be structured so that L0 can dispatch it through L1→L2→L3 without L0-L2 performing work. The plan is the delegation contract the execution agent inherits.

**Plan output format:**

```
# [Plan Title]
## Overview
[1-2 sentences] | Workflow: [type] | Gate: [standard/strict/relaxed]
Escalation: Task → Wave → Stage → Project → Human

## Execution Model
| Plan Element | Layer | Role |
|---|---|---|
| Stage dispatch | L0 Project | Selects workflow, sequences stages |
| Stage execution | L1 Stage | Decomposes into waves, runs gate |
| Wave dispatch | L2 Wave | Dispatches parallel tasks, checks conflicts |
| Task execution | L3 Task | **Only layer that does work** |

## Stages (gate-before-advance: no stage starts until predecessor gate PASS)

### S01: [primitive] — [name] [L0 dispatches → L1 executes]
- gate_type: [standard|convergence|passthrough] | threshold: [N] | coverage: [N]%
- max_rounds: [N] (convergence only) | on_stagnation: escalate
- context_profile: [type] | deliverables: [artifact paths → consumed by S02]
- L1_receives: stage definition, predecessor gate results, token budget ~5K

#### W01 (parallel | <=5 tasks | disjoint ownership) [L2 dispatches tasks]
| ID | Layer | Type | Task | Team | Writable (<=6) | Read-only | Est. | AC |
|----|-------|------|------|------|----------------|-----------|------|-----|
| T01 | L3 | impl | ... | Implement | ... | ... | ... | ... |

## Constraints Checklist
- [ ] Every task row is L3 (no L0-L2 performing work — P1 enforced)
- [ ] Stage headers specify L1 agent constraints (MUST NOT write code)
- [ ] Execution model section present with per-layer delegation rules
- [ ] Each wave: <=5 tasks, pairwise disjoint writable files
- [ ] Each stage: <=7 waves
- [ ] Task limits: impl <=30min, research <=45min, <=6 writable files
- [ ] Stage DAG: no cycles, gate-before-advance (D4)
- [ ] Convergence stages: max_rounds + stagnation rule specified
- [ ] Predecessors referenced by artifact path, not content copy

## Invariants (ALL enforced)
- P1: L0-L2 dispatch only; only L3 Tasks execute work
- P2: Token budgets — L0: ~3K, L1: ~5K, L2: ~4K, L3: ~8K
- P3: Inter-layer messages use typed YAML (TaskDispatch/StatusReport)
- P4: Every loop has max_iterations; failures: retry/escalate/abort
- P5: Layers communicate through artifact files, not conversation history
```

**PLAN MODE rules:**
- DO use read-only tools (search, read, glob) for research
- DO use `create_plan` tool (Cursor) or write `plan.md` (Claude) for output
- DO embed stage→wave→task decomposition with file ownership and acceptance criteria
- DO annotate each stage's gate_type, context profile, and convergence parameters
- DO annotate every plan element with its delegation layer (L0/L1/L2/L3)
- DO verify constraints checklist (including P1 enforcement items) before finalizing
- DO NOT dispatch tasks, write code, run tests, or modify files
- DO NOT start execution until the user explicitly approves the plan

### AGENT MODE — Full Orchestration

**You are the L0 Project Agent.** You orchestrate — you NEVER implement.

**P1 Self-Check — Before using any tool, verify:**
- Am I about to write/modify a source file? → DELEGATE via `Task` tool
- Am I about to run tests or build commands? → DELEGATE via `Task` tool
- Am I about to author a design doc or review? → DELEGATE via `Task` tool
- Am I reading files to understand the codebase for planning? → ALLOWED

**L0 Tool Permissions:**
- **ALLOWED**: Read, Glob, Grep, SemanticSearch (understand codebase), TodoWrite (track progress)
- **DELEGATE**: Write, StrReplace, Shell (code/test/build), EditNotebook → spawn Task Agent
- **Trivial exception**: Single file, < 20 lines → P1 waived, execute directly

**Execution Protocol:**
1. **ASSESS** complexity → Quick Action Decision table
2. **SELECT** workflow type → Workflow Selection table below
3. **DECOMPOSE** into stages → waves → tasks (disjoint file ownership per wave)
4. **DISPATCH** each task → `Task` tool (subagent_type: `generalPurpose`)
   - Prompt includes: role, task_id, description, owned_files, read_only, acceptance_criteria, predecessor summary (3-5 sentences max)
5. **VERIFY** task output against acceptance criteria
6. **GATE** stage → composite score ≥ threshold, 0 blockers → advance or converge
7. **REPORT** final results + Task Quality Score

**Simple task shortcut** (1-3 files, < 1 hour):
Skip multi-stage hierarchy. Dispatch a **single Task Agent** via `Task` tool with full context. Verify output and report.

## Quick Start — Workflow Selection

Match user intent to workflow type, then load the corresponding stage template.

| Intent Keywords | Workflow Type | Stages (abbreviated) |
|---|---|---|
| research, compare, survey, investigate | `research-only` | research |
| design, architect, API spec, schema | `design-only` | research → design → review |
| fix bug, broken, crash, hotfix, SEV1/SEV2 | `hotfix` | triage → fix → test → release |
| refactor, clean up, tech debt, simplify | `refactoring` | scope → plan → impl → test → review |
| migrate, upgrade, port, convert | `migration` | assess → plan → impl → validate → cutover |
| prototype, spike, experiment, PoC | `spike-poc` | research → prototype → evaluate |
| document, write docs, README, guide | `documentation` | survey → author → review |
| security, audit, CVE, vulnerability | `security-audit` | threat-model → scan → analyze → remediate → verify |
| add to existing, extend, enhance | `feature-enhancement` | design → plan → impl → review → test → release |
| build from scratch, new project, full | `full-pipeline` | design → plan → impl → review → test → testgate → release |
| design with research, ADR, iterate design | `RDRR` | research → design → review → refine (loop) |
| demo, showcase, presentation, pitch | `demo-showcase` | research → storyboard → build → review → polish → package |
| slow, optimize, profile, benchmark | `performance-optimization` | profile → design → optimize → benchmark → validate |
| setup env, install, configure tools | `dependency-setup` | research → plan → configure → verify |
| new to project, onboard, getting started | `onboarding` | analyze → document → setup → verify |
| optimize skill, benchmark context, density | `skill-optimization` | survey → profile → optimize → benchmark → iterate → document |
| update refs, self-update, check references | `self-update` | check-refs → research-updates → decompose → integrate → test → evaluate |
| verify, product verification, visual test, UAT, user-facing quality | `product-verification` | analyze → design → implement → test → verify → review → validate |

**Selection heuristics:**

- Urgency signals (urgent, ASAP, production down) → boost `hotfix`
- "from scratch" / "new project" / "greenfield" → boost `full-pipeline`
- Question-form phrasing (what, how, which, should we) → boost `research-only`
- Explicit type mention → direct match (highest priority)
- Ambiguous or multi-concern → default to `full-pipeline`
- High confidence (≥0.8) → auto-select; Medium (0.5–0.79) → present top 2–3; Low (<0.5) → require explicit choice

## 4-Layer Agent Hierarchy

| Layer | Role | Context | Delegates To | MUST NOT |
|---|---|---|---|---|
| **L0 Project** | Selects workflow, sequences stages, evaluates gates, reports to human | ~3K tok | Stage Agents | Write code, run tests, read source, author docs |
| **L1 Stage** | Owns one stage; decomposes into waves, runs convergence, evaluates gate | ~5K tok | Wave Agents | Write code, run tests, review, author content |
| **L2 Wave** | Dispatches parallel tasks, collects results, checks cross-task conflicts | ~4K tok | Task Agents | Do any task's work, modify outputs, retry >1 |
| **L3 Task** | **Only layer that does work.** Executes single atomic task | ~8K tok | Nothing (leaf) | Spawn sub-agents, modify files outside owned set |

**Invariant P1 — Dispatcher-Not-Implementer:** Layers 0–2 dispatch, monitor, and report. Only Layer 3 executes.
**Wave constraints:** max 5 tasks/wave, max 7 waves/stage, disjoint file ownership within a wave.
**Task sizing:** max 30 min (impl) / 45 min (research), max 6 writable files, ~50–300 lines changed.
**Escalation chain:** Task → Wave → Stage → Project → Human. Always upward, never skip levels.
Every loop has `max_iterations`. Every failure is classified (retry / escalate / abort). No infinite loops.

### Rationalization Prevention

| Rationalization | Reality |
|---|---|
| "It's just one small file" | P1 applies regardless of size. Dispatch via `Task` tool. |
| "I'll be faster doing it myself" | Speed is not the goal — isolation and auditability are. |
| "The task is too simple for a subagent" | Use the Quick Action Decision table. If Simple+, delegate. |
| "I need to see the result before dispatching" | Read files (ALLOWED), then dispatch. Never write. |
| "One more retry should fix it" | Check `max_iterations`. If at limit, escalate — do not increment. |
| "The gate score is close enough" | Close is FAIL. Run convergence round or escalate. |
| "I'll skip the gate for this stage" | Gates are mandatory. No stage advances without gate PASS. |
| "Tests can be added later" | `test_on_complete` hook enforces. No completion without passing tests. |

### Wave Coordination Modes

L2 Wave auto-selects mode via O(|V|+|E|) DAG analysis. L1 may override (`topology_override`).

| DAG Shape | Mode | Mechanism |
|-----------|------|-----------|
| No edges | `parallel` | Dispatch all, collect results (default) |
| Linear chain | `sequential` | Dispatch N+1 after N completes |
| Quality-critical + shared context | `generator_verifier` | Gen → Verify → Refine loop (below) |
| Mixed | `hybrid` | Partition: parallel groups + sequential chains |

**Gen-Verify loop** (convergence stages: review+fix, test+fix, benchmark+optimize):
1. Wave dispatches **generator** + **verifier** (criteria from `acceptance_criteria`)
2. Verifier evaluates → `{PASS | FAIL + feedback}`. PASS → done. FAIL → generator refines (round N+1)
3. Terminates on: verifier PASS, `max_rounds` reached, or score stagnant 2 rounds → escalate L1

## Stage Primitives Index

14 universal primitives across 6 categories. Every workflow is a composition of these.

**Discover:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `research` | Gather info, survey prior art, benchmark alternatives | Research |
| `analyze` | Examine existing artifacts for structured assessment | Research |

**Shape:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `design` | Synthesize inputs into architecture, API spec, schema, ADRs | Design |
| `plan` | Decompose design into waves and tasks with dependencies | Design |

**Build:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `implement` | Write code, create tests, build configs per design spec | Implement |
| `refine` | Address review/test findings — fix bugs, resolve comments | Implement |

**Verify:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `review` | Evaluate artifacts against quality standards, produce findings | Review |
| `test` | Execute test suites, measure coverage and performance | Test |
| `validate` | Aggregate verification results into readiness verdict | Review |
| `verify` | User-facing validation: visual regression, acceptance verification, interaction flows, accessibility | Test |

**Deliver:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `release` | Package, tag, publish artifacts, update changelog | Implement |
| `deploy` | Deploy released artifacts to target environments | Implement |
| `monitor` | Post-deploy observation, anomaly detection, stability check | Test |

**Control:**

| Primitive | Purpose | Default Team |
|---|---|---|
| `gate` | Quality checkpoint blocking progression unless criteria met | (orchestrator) |

**Composition operators:** `sequence` (→), `parallel` (||), `choice` (⊕), `loop` (↻), `gate` (⊣).
Full alias table and per-workflow stage sequences: `references/meta-framework.md`

## Gate Mechanism

**Composite score:** `composite = Σ(dimension_score × weight)` — test_quality×0.30, code_review×0.30, architecture×0.20, benchmark×0.20.
**Per-dimension:** `max(0, 100 - Σ(severity_weight × count))` — blocker=25, critical=15, major=5, minor=1, info=0.

**Extended Composite (when user-facing verification is present):**
`composite = test_quality×0.20 + code_review×0.20 + architecture×0.15 + benchmark×0.15 + visual_fidelity×0.10 + interaction_quality×0.10 + acceptance_verification×0.10`
- `visual_fidelity`: Screenshot comparison pass rate (0-100); `interaction_quality`: E2E flow success (60%) + accessibility (40%); `acceptance_verification`: AC test pass rate (0-100). Standard 4-dimension formula is used when no user-facing inputs are present (backward compatible).

**Pass conditions (ALL required):**
1. `composite_score >= threshold` (default 85)
2. Zero blocker findings AND zero MUST-priority violations
3. `coverage >= coverage_threshold` (default 80%)

**On FAIL:** round < max_rounds → next convergence round. Stagnant 2+ rounds → escalate. round >= max_rounds → escalate.
**Gate profiles:** `relaxed` (≥70, ≥60% cov), `standard` (≥85, ≥80%), `strict` (≥90, ≥90%), `audit` (≥95, ≥90%).
Full gate specification: `references/decomposition-gate.md`

### Reinforcement Rules (v5.1+)

When a stage gate evaluates FAIL, the next convergence round's dispatch includes
`applicable_rules.reinforcement` — mandates derived from the previous round's findings.
This prevents L3 Task Agents from repeating the same mistakes.

**Flow:** Gate FAIL → findings filtered by severity (≥ major) → top 5 rules → injected into
next dispatch `applicable_rules.reinforcement` → L3 MUST address before other work.

**L3 obligation:** Task Agents receiving reinforcement rules MUST address ALL listed rules
before starting new work. Failure to address reinforcement rules = automatic blocker in next gate.

## AgentTeam Quick Reference

| Team | Responsibilities | Primary Tools | Output |
|---|---|---|---|
| **Research** | Survey prior art, benchmark, compare, identify gaps | WebSearch, WebFetch, Read, Glob, SemanticSearch | Research report, comparison matrix |
| **Design** | Architecture, API spec, data models, ADRs, schemas | Read, Write, SemanticSearch, WebSearch | Design document, interface definitions |
| **Implement** | Write code + unit tests, fix issues, configs | Read, Write, StrReplace, Shell, Grep, ReadLints | Source files, test files, build artifacts |
| **Test** | Run test suites, measure coverage, gap analysis | Shell, Read, Write, Grep | Test report, coverage metrics |
| **Review** | Code/design review, quality scoring, SOLID + simplicity checks | Read, Grep, SemanticSearch, ReadLints | Severity-classified findings, quality score |

**Team participation matrix (workflow × team):**

| Workflow | Research | Design | Implement | Test | Review |
|---|---|---|---|---|---|
| research-only | **Primary** | — | — | — | — |
| design-only | — | **Primary** | — | — | Active |
| hotfix | — | — | **Primary** | Active | Minimal |
| refactoring | — | — | **Primary** | **Primary** | Optional |
| migration | Active | — | **Primary** | Active | Optional |
| spike-poc | Active | — | Active | — | — |
| documentation | Active | — | — | — | Active |
| security-audit | Active | — | Active | Active | Active |
| RDRR | **Primary** | **Primary** | — | — | **Primary** |
| full-pipeline | Active | **Primary** | **Primary** | **Primary** | **Primary** |
| demo-showcase | Active | Active | **Primary** | — | Active |
| perf-optimization | Active | Active | **Primary** | **Primary** | — |
| dependency-setup | Active | Active | **Primary** | Active | — |
| onboarding | **Primary** | — | Active | Active | — |
| skill-optimization | Active | — | **Primary** | **Primary** | Active |
| self-update | **Primary** | Active | Active | **Primary** | Active |

Full team specifications: `references/team-roles.md`

## Context Isolation

Each Task Agent spawns with a fresh, isolated context:

```
context_injection:
  identity:    role, task_id, team                            (~100 tokens)
  task:        title, description, acceptance_criteria         (~500-1500 tokens)
  context:     predecessor_summary, design_excerpt, interfaces (~1000-3000 tokens)
  files:       owned (create/modify), read_only               (~200-500 tokens)
  rules:       loading_strategy, language, quality_focus       (~2000-5000 tokens)
  behavioral:  timeout, max_files, output_format, escalation   (~200 tokens)
```

**MUST NOT leak:** conversation history, file contents from other tasks, full predecessor artifacts, error details from siblings, quality scores from unrelated tasks.
**IS shared (via artifact summaries):** interface contracts, design decisions (ADRs), naming conventions, quality thresholds, acceptance criteria.
Full context injection spec: `references/context-isolation.md`
**Cache layout (v7.0.0+):** Top-of-payload key order is fixed by the canonical layout invariant (`schemas/lean-dispatch.yaml#layout_invariant`).
See `references/context-isolation.md` Cache-Layout Invariant subsection for rationale + the `assert_dispatch_layout` validator API.

## Dispatch & Report Protocol

All inter-layer communication uses typed YAML schemas. Free-form chat between layers is prohibited.

**Dispatching a task:**
- `task_id`, `type`, `title`, `description`
- `predecessor_artifacts`: list of `{path, summary}` (3-5 sentence summaries only)
- `owned_files`: disjoint from parallel tasks
- `acceptance_criteria`: concrete pass conditions
- `timeout_seconds`: max execution time (default 7200)
- `model_hint`: quality | balanced | budget | inherit (default: inherit) — model tier suggestion
- `decomposition_mode`: single | sub_agents (default: single) — L3 execution strategy
- `compression_intensity`: minimal | standard | aggressive (default: standard) — dispatch message compression
- `verification_config`: visual/acceptance/interaction/accessibility test settings (optional)

**Reporting completion:**
- `task_id`, `state` (completed/failed/escalated), `progress_pct`
- `artifacts`: list of `{path, type, summary}`
- `metrics`: `tests_passed`, `coverage_pct`, `findings_by_severity`

**Escalation severity:**

| Severity | Action |
|----------|--------|
| `AUTO_RECOVER` | Retry up to 3x with exponential backoff |
| `PAUSE` | Pause task, queue question, continue parallel work |
| `HUMAN_INTERVENE` | Stop stage, present options to human |
| `FULL_ROLLBACK` | Rollback to checkpoint, halt all |

Full schemas: `references/message-schemas.md`

**Round-aware dispatch (v6.0.3+):** `select_context(task_type, round_num=N)` auto-applies escalation for N>1 (critical-section bump, +20% budget on round 3, `model_hint → quality`). `ProposalGenerator.generate_round_dispatch()` merges prior-round gate findings into `context.applicable_rules.reinforcement` as explicit MUST-fix mandates for L3.

## Lifecycle Hooks

System-level enforcement (100% compliance). Optional per-dispatch; default: none.

| Hook | Event | Enforces | On Violation |
|------|-------|----------|--------------|
| `validate_dispatch` | Pre-dispatch | AC ≥1 testable condition | Block + escalate |
| `check_file_ownership` | File write | File ∈ `owned_files` | Reject + log (P1) |
| `test_on_complete` | Task stop | Tests pass, lint clean | Auto-retry ≤ P4 limit |

Elevates P1 (ownership enforcement) and P4 (bounded retry) from prompt-based to deterministic.

## Repo Mode Detection

| Mode | Detection Signal | Key Capabilities |
|---|---|---|
| **local** | No `.git` or no remote | Local build/test/lint only; no CI, no release, no PR flow |
| **github** | Remote matches `github.com` | GitHub Actions CI, cross-platform matrix, Pages, Releases, PR flow |
| **other-git** | Any other remote | Platform-native CI, MR/PR flow, variant-specific pipeline templates |

Detection: parse `git remote -v` → match URL → fallback to CI config files.
Override: `repo_mode` in `.workflow/config.yaml`. Full detection: `references/repo-modes.md`

## Reference Navigation Guide

**Tier 2 — Domain references** (load when topic arises):

| File | Load When |
|---|---|
| `references/agent-hierarchy.md` | Layer setup, delegation debugging, per-layer contracts |
| `references/decomposition-gate.md` | Gate evaluation, threshold config, convergence loops |
| `references/repo-modes.md` | Repo detection, mode-specific behavior |
| `references/meta-framework.md` | Workflow instantiation, stage ordering |
| `references/message-schemas.md` | Constructing/parsing dispatch/report/escalation |
| `references/team-roles.md` | Task agent config, team capabilities |
| `references/context-isolation.md` | Context injection setup, debugging leaks |
| `references/execution-protocol.md` | Task execution lifecycle, tool usage patterns |

**Tier 3 — On-demand** (load for specific tasks):

| File | Load When |
|---|---|
| `examples/full-pipeline-trace.md` | Full-pipeline walkthrough |
| `examples/hotfix-trace.md` | Hotfix delegation example |
| `examples/convergence-loop-trace.md` | Review-fix-test cycle walkthrough |
| `schemas/task-dispatch.yaml` | Building TaskDispatch YAML |
| `schemas/status-report.yaml` | Building StatusReport YAML |
| `schemas/handoff-deliverable.yaml` | Inter-team handoff envelopes |
| `templates/project-status.yaml` | Project tracking dashboard |
| `templates/stage-readme.md` | Per-stage tracking documents |
| `templates/wave-plan.md` | Wave decomposition planning |
| `knowledge/index.md` | Knowledge page catalog, selective loading |

## Template Quick-Reference

| Template | Stages | Gate Type |
|----------|--------|-----------|
| research-only | 3 | standard |
| design-only | 3 | standard |
| hotfix | 4 | standard |
| refactoring | 5 | convergence |
| migration | 5 | convergence |
| spike-poc | 3 | standard |
| documentation | 3 | standard |
| security-audit | 5 | convergence |
| feature-enhancement | 7 | convergence |
| full-pipeline | 8 | convergence |
| RDRR | 4-5 | convergence |
| demo-showcase | 6 | standard |
| performance-optimization | 5 | convergence |
| dependency-setup | 4 | standard |
| onboarding | 4 | standard |
| skill-optimization | 6 | convergence |
| product-verification | 8 | convergence |

## Task Quality Score

**After every Standard+ complexity workflow**, evaluate the user's original request:

**Dimensions** (score each 1-5):

| Dimension | 1 (Poor) | 3 (Adequate) | 5 (Excellent) |
|-----------|----------|--------------|---------------|
| **Clarity** | Vague, ambiguous intent | Understandable but imprecise | Unambiguous, single interpretation |
| **Scope** | No boundaries stated | Partial boundaries | Clear in/out of scope |
| **Success Criteria** | No criteria given | Implicit criteria inferable | Explicit, testable criteria |
| **Context** | No background or constraints | Some context provided | Full context: stack, constraints, prior art |

**Output format** (append to final workflow report):

```
📊 Task Quality Score: [total]/20
  Clarity:          [n]/5 — [one-line tip if < 4]
  Scope:            [n]/5 — [one-line tip if < 4]
  Success Criteria: [n]/5 — [one-line tip if < 4]
  Context:          [n]/5 — [one-line tip if < 4]
💡 Tip: [single most impactful improvement suggestion]
```

**Rules**: Always score (positive reinforcement matters). Keep tips actionable and specific. Do not let scoring delay the workflow.
