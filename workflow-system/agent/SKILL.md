---
id: "agent/SKILL"
version: "1.0.0"
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
tier: 1
token_estimate: 3500
last_updated: "2026-04-04"
name: workflow-orchestrator
description: >
  Orchestrate multi-stage software workflows using a 4-layer agent hierarchy
  (Project -> Stage -> Wave -> Task) with gate mechanisms, convergence loops,
  and context-isolated task delegation. Use when implementing features,
  fixing bugs, refactoring, migrating, or running any multi-step development
  workflow.
---

# Workflow Orchestrator

## Purpose & Scope
<!-- design ref: design_delivery_architecture.md §3.4 -->

This skill orchestrates multi-stage software development workflows. It covers:

- **10 workflow types**: research-only, design-only, hotfix, refactoring, migration, spike-poc, documentation, security-audit, feature-enhancement, full-pipeline (plus RDRR composite)
- **13 stage primitives**: research, analyze, design, plan, implement, refine, review, test, validate, release, deploy, monitor, gate
- **4-layer agent hierarchy**: Project → Stage → Wave → Task with strict context isolation
- **Gate quality mechanism**: composite scoring with convergence loops and bounded retry

Use when asked to implement features, fix bugs, refactor, migrate, or run any multi-step workflow.
Start by matching user intent to a workflow type in the Quick Start table below.

## Quick Start — Workflow Selection
<!-- design ref: design_meta_framework.md §6 -->

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

**Selection heuristics:**

- Urgency signals (urgent, ASAP, production down) → boost `hotfix`
- "from scratch" / "new project" / "greenfield" → boost `full-pipeline`
- Question-form phrasing (what, how, which, should we) → boost `research-only`
- Explicit type mention → direct match (highest priority)
- Ambiguous or multi-concern → default to `full-pipeline`
- High confidence (≥0.8) → auto-select; Medium (0.5–0.79) → present top 2–3; Low (<0.5) → require explicit choice

## 4-Layer Agent Hierarchy (Summary)
<!-- design ref: design_agent_hierarchy.md §2 -->

| Layer | Role | Context | Delegates To | MUST NOT |
|---|---|---|---|---|
| **L0 Project** | Selects workflow, sequences stages, evaluates gates, reports to human | ~3K tok | Stage Agents | Write code, run tests, read source, author docs |
| **L1 Stage** | Owns one stage; decomposes into waves, runs convergence, evaluates gate | ~5K tok | Wave Agents | Write code, run tests, review, author content |
| **L2 Wave** | Dispatches parallel tasks, collects results, checks cross-task conflicts | ~4K tok | Task Agents | Do any task's work, modify outputs, retry >1 |
| **L3 Task** | **Only layer that does work.** Executes single atomic task | ~8K tok | Nothing (leaf) | Spawn sub-agents, modify files outside owned set |

**Invariant P1 — Dispatcher-Not-Implementer:** Layers 0–2 dispatch, monitor, and report. Only Layer 3 Task Agents execute actual work.

```
  Human
    |
    v
  [L0 Project Agent]  --dispatch-->  [L1 Stage Agent]
                                          |
                                     dispatch
                                          v
                                     [L2 Wave Agent]
                                          |
                                     dispatch (parallel)
                                     +----+----+
                                     v    v    v
                                   [L3] [L3] [L3]   <-- Task Agents (do work)
                                     |    |    |
                                     report report
                                     +----+----+
                                          v
                               [L2] --report--> [L1] --report--> [L0]
```

**Wave constraints:** max 5 tasks/wave, max 7 waves/stage, disjoint file ownership within a wave.
**Task sizing:** max 30 min (impl) / 45 min (research), max 6 writable files, ~50–300 lines changed.

## Stage Primitives Index
<!-- design ref: design_meta_framework.md §2.1 -->

13 universal primitives across 6 categories. Every workflow is a composition of these.

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
Operators nest arbitrarily. Workflow-specific aliases map to primitives (e.g., `bug-triage` → `analyze`).
Full alias table and per-workflow stage sequences: `references/stage-templates.md`

## Gate Mechanism (Summary)
<!-- design ref: design_decomposition_gate.md §5, design_agent_hierarchy.md Appendix A -->

**Composite score formula:**

```
composite = Σ(dimension_score × weight)
  test_quality   × 0.30   (tests_passed/total × 100 or coverage_pct)
  code_review    × 0.30   (quality_score from review findings)
  architecture   × 0.20   (SOLID review score)
  benchmark      × 0.20   (pass rate, or 100 if no benchmarks)
```

**Per-dimension quality score:** `max(0, 100 - Σ(severity_weight × count))`
Severity weights: blocker=25, critical=15, major=5, minor=1, info=0.

**Pass conditions (ALL required):**
1. `composite_score >= threshold` (default 85, configurable via gate profile)
2. Zero blocker findings AND zero MUST-priority violations
3. `coverage >= coverage_threshold` (default 80%)

**On FAIL:** round < max_rounds → run another convergence round.
Score stagnant 2+ rounds → escalate. round >= max_rounds → escalate to Project Agent → human.

**Gate profiles:** `relaxed` (≥70, ≥60% cov), `standard` (≥85, ≥80%), `strict` (≥90, ≥90%), `audit` (≥95, ≥90%).

Full gate specification: `references/gate-mechanism.md`

## AgentTeam Quick Reference
<!-- design ref: design_agent_hierarchy.md §4 -->

| Team | Responsibilities | Primary Tools | Output |
|---|---|---|---|
| **Research** | Survey prior art, benchmark, compare, identify gaps | WebSearch, WebFetch, Read, Glob, SemanticSearch | Research report, comparison matrix |
| **Design** | Architecture, API spec, data models, ADRs, schemas | Read, Write, SemanticSearch, WebSearch | Design document, interface definitions |
| **Implement** | Write code + unit tests, fix issues, configs | Read, Write, StrReplace, Shell, Grep, ReadLints | Source files, test files, build artifacts |
| **Test** | Run test suites, measure coverage, gap analysis | Shell, Read, Write, Grep | Test report, coverage metrics |
| **Review** | Code/design review, quality scoring, SOLID checks | Read, Grep, SemanticSearch, ReadLints | Severity-classified findings, quality score |

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

Full team specifications with input/output contracts: `references/team-roles.md`

## Context Isolation
<!-- design ref: design_agent_hierarchy.md §6 -->

Each Task Agent spawns with a fresh, isolated context. Injection follows this template:

```
context_injection:
  identity:    role, task_id, team                            (~100 tokens)
  task:        title, description, acceptance_criteria         (~500-1500 tokens)
  context:     predecessor_summary, design_excerpt, interfaces (~1000-3000 tokens)
  files:       owned (create/modify), read_only               (~200-500 tokens)
  rules:       loading_strategy, language, quality_focus       (~2000-5000 tokens)
  behavioral:  timeout, max_files, output_format, escalation   (~200 tokens)
```

**Context budget by layer:**

| Layer | Strategy | Budget | Loaded Content |
|---|---|---|---|
| Project | Minimal | ~3K tokens | Workflow template, project config, stage status dashboard |
| Stage | Standard | ~5K tokens | Stage definition, predecessor summaries, wave plan |
| Wave | Minimal | ~4K tokens | Wave task list, task status tracking |
| Task | Standard–Full | ~8K tokens | Task spec, owned files, code-rules, design excerpt |

**MUST NOT leak between sub-agents:** conversation history, file contents from other tasks, full predecessor artifacts, error details from siblings, quality scores from unrelated tasks.

**IS shared (via artifact summaries):** interface contracts (signatures, types), design decisions (ADRs), naming conventions, quality thresholds, acceptance criteria.

Full context injection spec: `references/context-isolation.md`

## Message Protocol (Summary)
<!-- design ref: design_agent_hierarchy.md §3 -->

All inter-layer communication uses typed YAML schemas. Free-form chat between layers is prohibited.

| Message | Direction | Key Fields |
|---|---|---|
| **TaskDispatch** | Parent → Child | dispatch_id, parent_id, task_id, type, title, description, owned_files, acceptance_criteria, timeout_seconds, applicable_rules |
| **StatusReport** | Child → Parent | dispatch_id, task_id, state (pending/in_progress/completed/failed/escalated), artifacts, metrics (tests/coverage/findings), gate_decision |
| **ExceptionEscalation** | Child → Parent | dispatch_id, error_type (recoverable/blocking/fatal), category, description, evidence, impact, suggested_action |

**Error types:** `recoverable` → auto-retry up to max → `blocking` → parent evaluates (modify spec, reassign, escalate) → `fatal` → halt + divergence report for human.

Full schemas with all fields: `references/message-schemas.md`

## Repo Mode Detection
<!-- design ref: design_repo_modes.md §3 -->

Three modes, auto-detected from git remote URL during Pre-Decision Phase:

| Mode | Detection Signal | Key Capabilities |
|---|---|---|
| **local** | No `.git` or no remote configured | Local build/test/lint only; no CI, no release, no PR flow |
| **github** | Remote URL matches `github.com` | GitHub Actions CI, cross-platform matrix, Pages, Releases, PR flow |
| **other-git** | Any other remote (GitLab, Gitea, Bitbucket) | Platform-native CI, MR/PR flow, variant-specific pipeline templates |

Detection: parse `git remote -v` → match URL patterns → fallback to CI config files in repo root.
Override: set `repo_mode` in `.workflow/config.yaml`. Mode drives stage behavior (e.g., `release` skipped in local).

Full detection algorithm and 20-feature toggle matrix: `references/repo-modes.md`

## Reference Navigation Guide
<!-- design ref: design_delivery_architecture.md §3.2 -->

**Tier 2 — Domain references** (load when the topic arises):

| Topic | File | Load When You Need |
|---|---|---|
| 4-layer hierarchy, delegation rules | `references/agent-hierarchy.md` | Layer setup, debugging delegation, per-layer contracts |
| Gate formulas, convergence loops | `references/gate-mechanism.md` | Gate evaluation, threshold config, loop-back rules |
| Repo mode detection, feature toggles | `references/repo-modes.md` | Repo structure detection, mode-specific behavior |
| Workflow → stage sequences, templates | `references/stage-templates.md` | Instantiating a workflow, stage ordering rules |
| Full message YAML schemas | `references/message-schemas.md` | Constructing or parsing dispatch/report/escalation |
| 5 AgentTeam role specifications | `references/team-roles.md` | Task agent config, team capabilities and contracts |
| Context injection templates | `references/context-isolation.md` | Context injection setup, debugging context leaks |

**Tier 3 — On-demand** (load for specific tasks only):

| Topic | File | Load When You Need |
|---|---|---|
| Full-pipeline delegation trace | `examples/full-pipeline-trace.md` | Complete walkthrough of a full-pipeline run |
| Hotfix workflow trace | `examples/hotfix-trace.md` | Hotfix delegation chain example |
| Convergence loop trace | `examples/convergence-loop-trace.md` | Review-fix-test cycle walkthrough |
| TaskDispatch schema | `schemas/task-dispatch.yaml` | Building a TaskDispatch YAML message |
| StatusReport schema | `schemas/status-report.yaml` | Building a StatusReport YAML message |
| Handoff deliverable schema | `schemas/handoff-deliverable.yaml` | Building inter-team handoff envelopes |
| Project status dashboard | `templates/project-status.yaml` | Creating the project tracking dashboard |
| Stage README template | `templates/stage-readme.md` | Creating per-stage tracking documents |
| Wave plan template | `templates/wave-plan.md` | Planning wave decomposition |

## Rules for Dispatchers
<!-- design ref: design_agent_hierarchy.md §2, design_decomposition_gate.md §7 -->

**Per-layer MUST NOT:**

| Layer | Prohibited Actions |
|---|---|
| **L0 Project** | Write code, run tests/shell, read source files, author designs, skip gates, reorder stages |
| **L1 Stage** | Write code, run tests, perform reviews, author content, dispatch >5 tasks per wave |
| **L2 Wave** | Do any task's work, modify task outputs, retry a task more than once, wait indefinitely |
| **L3 Task** | Spawn sub-agents, delegate work, modify files outside owned set, exceed timeout |

**Fail-forward protocol:**

1. **Task fails** → Wave retries once with error context → still fails → escalate to Stage
2. **Wave fails** → Stage retries failed tasks only → still fails → escalate to Project
3. **Stage gate fails** → Project evaluates: loop-back (max 2 retries per stage) or escalate to human
4. **Project loop-back budget:** 3 total across all stages → exceeded → halt with divergence report

**Escalation chain:** Task → Wave → Stage → Project → Human. Always upward, never skip levels.
Every loop has `max_iterations`. Every failure is classified (retry / escalate / abort). No infinite loops.

## Convergence Loop (Summary)
<!-- design ref: design_decomposition_gate.md §5, design_agent_hierarchy.md Appendix C -->

8-phase loop for implementation stages, each phase dispatched as a wave:

```
Round N:
  1. CODE REVIEW        (Review Agent)     5. BENCHMARK      (Test Agent)
  2. FIX review findings (Implement Agent)  6. FIX bench       (Implement Agent)
  3. TEST               (Test Agent)        7. FINAL REVIEW    (Review Agent)
  4. FIX test failures   (Implement Agent)  8. FIX final       (Implement Agent)
  --> Gate: composite >= 85 AND 0 blockers AND round >= min --> PASS
           score < 85 AND round < max --> NEXT ROUND
           round >= max --> ESCALATE
```

Defaults: min_rounds=1, max_rounds=3 (configurable per gate profile, range 1–6).
The Stage Agent orchestrates the loop and never executes any phase directly.

## Template Quick-Reference
<!-- design ref: design_meta_framework.md §4-7 -->

| Template | Stage Sequence | Purpose |
|---|---|---|
| `research-only` | research | Information gathering and comparison report |
| `design-only` | research → design → review | Architecture or API design with review |
| `hotfix` | triage → fix → test → release | Rapid bug fix with minimal ceremony |
| `refactoring` | scope → plan → impl → test → review | Code structure improvement with safety net |
| `migration` | assess → plan → impl → validate → cutover | System/version migration with validation |
| `spike-poc` | research → prototype → evaluate | Feasibility exploration with decision gate |
| `documentation` | survey → author → review | Documentation authoring and quality review |
| `security-audit` | threat-model → scan → analyze → remediate → verify | Security assessment and remediation cycle |
| `feature-enhancement` | design → plan → impl → review → test → release | Extend existing system functionality |
| `full-pipeline` | design → plan → impl → review → test → testgate → release | Complete lifecycle for new features |
| `RDRR` | research → design → review → refine (loop) | Iterative research-driven design convergence |
