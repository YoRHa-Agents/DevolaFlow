---
name: devola-flow-mvp
version: "3.0.0"
description: >
  Self-contained workflow orchestration skill using a 4-layer agent hierarchy
  (Project, Stage, Wave, Task) with gate quality mechanisms, convergence loops,
  and context-isolated task delegation. Use when implementing features, fixing
  bugs, refactoring, migrating, or running any multi-step development workflow.
  Supports 15 workflow types from research-only to full-pipeline.
---

> **Now Using DevolaFlow v3.0.0**

# DevolaFlow (MVP)

Orchestrate multi-stage software workflows using a 4-layer agent hierarchy with
gate mechanisms, convergence loops, and context-isolated task delegation. This
file is fully self-contained -- no external references required.

## Version & Update
<!-- Manually triggered only — do NOT auto-check on every skill load -->

**Current version:** 3.0.0

**To check for updates** (only when user explicitly asks "update devola" or "/update-devola"):

1. Fetch latest: `curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py 2>/dev/null | grep '__version__'`
2. Compare with current version (3.0.0).
3. If newer, advise: `curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update`
4. If current, respond: "DevolaFlow v3.0.0 is the latest version."

**IMPORTANT:** Do NOT auto-check. Only check on explicit user request.

## Quick Action Decision

Before selecting a workflow, assess task complexity:

| Complexity | Signal | Action |
|-----------|--------|--------|
| **Trivial** | Single file, < 20 lines, obvious fix | Execute directly — no workflow needed |
| **Simple** | 1-3 files, clear scope, < 1 hour | Use **hotfix** or **single-stage** — skip hierarchy |
| **Standard** | 3-10 files, needs design or review | Select workflow from table below, use full hierarchy |
| **Complex** | 10+ files, cross-cutting, multi-day | Select workflow, use strict gate profile |

**Rule**: Do not over-orchestrate simple tasks. Match ceremony to complexity.

## Workflow Type Selection

Select the workflow type that matches the user's intent:

| Type | Trigger Keywords | Stages |
|------|-----------------|--------|
| research-only | research, compare, evaluate, survey | research → compare → report |
| design-only | design, architect, API spec, schema | research → design → review |
| hotfix | fix bug, broken, crash, urgent, SEV1 | triage → fix → test → release |
| refactoring | refactor, clean up, tech debt | scope → plan → implement → test → review |
| migration | migrate, upgrade, port, convert | assess → plan → implement → validate → cutover |
| spike-poc | try, experiment, prototype, PoC | research → prototype → evaluate |
| documentation | document, write docs, README | survey → author → review |
| security-audit | security, CVE, vulnerability | threat_model → scan → analyze → remediate → verify |
| feature-enhancement | add to existing, extend, enhance | scope → design → plan → impl → review → test → release |
| full-pipeline | build from scratch, new project | design → plan → impl → review → test → refine → testgate → release |
| RDRR | design with research, ADR | research → design → review → refine (loop) |
| demo-showcase | demo, showcase, presentation, pitch | research → storyboard → build → review → polish → package |
| performance-optimization | slow, optimize, profile, benchmark | profile → design → optimize → benchmark → validate |
| dependency-setup | setup env, install, configure tools | research → plan → configure → verify |
| onboarding | new to project, onboard, get started | analyze → document → setup → verify |

**Selection heuristic**: Match keywords from user request. If multiple match, prefer full-pipeline. If urgency signals present (urgent, ASAP), prefer hotfix.

## 4-Layer Agent Hierarchy

```
Layer 0: PROJECT AGENT (Dispatcher)
  |-- dispatches --> Layer 1: STAGE AGENT (per stage)
                      |-- dispatches --> Layer 2: WAVE AGENT (per wave)
                                          |-- dispatches --> Layer 3: TASK AGENT (worker)
```

| Layer | Role | Context | MUST NOT |
|-------|------|---------|----------|
| Project | Dispatch stages sequentially, evaluate gates, track status | ~3K tokens: workflow template + status dashboard | Read source code, write code, run tests, author documents |
| Stage | Decompose stage into waves, sequence waves, run stage gate | ~5K tokens: stage def + predecessor summaries + wave plan | Write code, run tests, do review, author research |
| Wave | Dispatch tasks in parallel, collect results, check conflicts | ~4K tokens: task list + dependency map | Execute any task work, modify task outputs |
| Task | **ONLY layer that works** -- write code, run tests, review | ~8K tokens: task spec + owned files + rules + design excerpt | Spawn sub-agents, modify files outside owned_files |

**INVARIANT**: Dispatcher agents (Project, Stage, Wave) MUST NOT perform work. Only Task Agents execute actual work using tools.

## Stage Primitives (13 Universal)

| Primitive | Category | Purpose | Default Team |
|-----------|----------|---------|-------------|
| research | Discover | Gather information, survey prior art | Research |
| analyze | Discover | Examine artifacts, produce assessments | Research |
| design | Shape | Synthesize into architecture/API/schema | Design |
| plan | Shape | Decompose design into work units | Design |
| implement | Build | Write code, create tests, build artifacts | Implement |
| refine | Build | Address findings from review/test | Implement |
| review | Verify | Evaluate against quality criteria | Review |
| test | Verify | Execute test suites, measure coverage | Test |
| validate | Verify | Aggregate results into readiness verdict | Review |
| release | Deliver | Package, tag, publish artifacts | Implement |
| deploy | Deliver | Deploy to target environments | Implement |
| monitor | Deliver | Post-deploy observation | Test |
| gate | Control | Quality checkpoint blocking progression | Orchestrator |

## Dispatch & Report Protocol

**Dispatching a task** — include these fields (YAML or structured text):

- `task_id`, `type` (stage/wave/code/test/review/research), `title`, `description`
- `predecessor_artifacts`: list of `{path, summary}` (3-5 sentence summaries only)
- `owned_files`: files this task may create/modify (disjoint from parallel tasks)
- `acceptance_criteria`: concrete pass conditions
- `timeout_seconds`: max execution time (default 7200)

**Reporting completion** — include these fields:

- `task_id`, `state` (completed/failed/escalated), `progress_pct`
- `artifacts`: list of `{path, type, summary}` for produced files
- `metrics`: `tests_passed`, `coverage_pct`, `findings_by_severity`

**Escalating errors** — classify and escalate upward:

- `AUTO_RECOVER`: Network timeout, rate limit → retry up to 3x with backoff
- `PAUSE`: Ambiguous spec, missing dep → pause task, queue question, continue parallel work
- `HUMAN_INTERVENE`: Architecture decision, security change → stop stage, present options
- `FULL_ROLLBACK`: Corrupted state, impossible requirement → rollback to checkpoint, halt

Escalation chain: Task → Wave → Stage → Project → Human. Always upward, never skip levels.

## Gate Mechanism

Every stage has a quality gate evaluated after all waves complete.

**Composite Score**: `test_quality × 0.30 + code_review × 0.30 + architecture × 0.20 + benchmark × 0.20`
**Quality Score per dimension**: `max(0, 100 - (blocker×25 + critical×15 + major×5 + minor×1))`

**Pass** when ALL hold: `composite >= threshold`, `blockers == 0`, `at least 1 review cycle completed`

| Profile | Composite | Coverage | Blockers | Max Rounds |
|---------|-----------|----------|----------|------------|
| strict | >= 90 | >= 85% | 0 | 4 |
| standard | >= 85 | >= 80% | 0 | 3 |
| relaxed | >= 70 | >= 60% | 0 | 2 |
| audit | >= 95 | >= 90% | 0 | 6 |

**On FAIL**: round < max_rounds → run convergence round. Score stagnant 2+ rounds → ESCALATE.

## AgentTeam Quick Reference

| Team | Responsibilities | Tools |
|------|-----------------|-------|
| Research | Survey, benchmark, compare, synthesize reports | WebSearch, WebFetch, Read, Glob |
| Design | Architecture, interfaces, ADRs, specifications | Read, Write, SemanticSearch |
| Implement | Write code, create tests, build infrastructure | Read, Write, Shell, Grep, ReadLints |
| Test | Run test suites, measure coverage, gap analysis | Shell, Read, Write |
| Review | Code review, design review, quality scoring | Read, Grep, SemanticSearch |

## Context Isolation

Each Task Agent receives a context injection with these sections ONLY:

1. **Identity**: role, task_id, team (~100 tokens)
2. **Task spec**: title, description, acceptance criteria (~500-1500 tokens)
3. **Scoped context**: predecessor summary (3-5 sentences), design excerpt (~1000-3000 tokens)
4. **File scope**: owned files + read-only files (~200-500 tokens)
5. **Rules**: code rules per loading strategy (~2000-5000 tokens)
6. **Behavioral**: timeout, max_files_to_read, output format (~200 tokens)

**MUST NOT leak between agents**:
- Prior task's reasoning / tool calls / intermediate outputs
- Source files owned by parallel tasks
- Full predecessor artifacts (summaries only)
- Error details from sibling tasks

## Wave Decomposition Rules

- Tasks within a wave MUST be independent (no shared writable files)
- Maximum 5 tasks per wave, maximum 7 waves per stage
- Each task owns a disjoint set of files
- Waves execute sequentially within a stage: Wave N+1 starts after Wave N completes

**Task Sizing**: Max 30 min (implementation) or 45 min (research/design). Max 6 writable files, ~300 lines net change. If exceeds bounds, decompose further.

## Convergence Loop

When a stage gate evaluates FAIL, run a convergence round (max per profile):

```
Round N:
  1. CODE REVIEW   (Review Agent)    → findings list
  2. FIX findings  (Implement Agent) → patched code
  3. TEST          (Test Agent)      → test results + coverage
  4. FIX failures  (Implement Agent) → patched code
  5. BENCHMARK     (Test Agent)      → perf metrics (if enabled)
  6. FIX bench     (Implement Agent) → optimized code
  7. FINAL REVIEW  (Review Agent)    → final findings
  8. FIX final     (Implement Agent) → final patches
  → RE-EVALUATE GATE
```

**Stagnation**: If score does not improve for 2 consecutive rounds, ESCALATE to human.

## Task Quality Score

**After every workflow completes**, evaluate the user's original request and provide a brief quality score. This helps users learn to write better task descriptions.

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

**Rules**:
- Always score, even for high-quality requests (positive reinforcement matters)
- Keep tips actionable and specific, not generic ("specify the target file" > "be more specific")
- Do not let scoring delay or block the workflow — score is appended after completion
- For trivial/quick-action tasks, skip scoring (only score Standard+ complexity workflows)

## Quick Examples

### Full Pipeline Trace (New Feature)
```
T+0   L0  Project       Select workflow: full-pipeline
T+2   L0  Project       Dispatch Stage: Design            → StageDispatch
      L1  Stage:Design  Decompose → 2 waves
      L2  Wave:D-W1     Dispatch Task: Research APIs       → parallel
      L3  Task          [WORK] Survey, produce report
      L1  Stage:Design  Gate: PASS (score 92)              → advance
T+10  L0  Project       Dispatch Stage: Plan               → StageDispatch
      L1  Stage:Plan    Gate: PASS                         → advance
T+20  L0  Project       Dispatch Stage: Impl               → StageDispatch
      L1  Stage:Impl    3 waves, 9 tasks (max 4 parallel)
      L1  Stage:Impl    Convergence: R1 score=78, R2 score=88 → PASS
T+50  L0  Project       Dispatch Review → Test → Release
T+70  L0  Project       All PASS → final report + task quality score
```

### Hotfix Trace (Bug Fix)
```
T+0   L0  Project       Select workflow: hotfix
T+1   L0  Project       Dispatch Stage: Bug-Triage         → StageDispatch
      L3  Task          [WORK] Analyze root cause: SEV2
T+5   L0  Project       Dispatch Stage: Fix                → StageDispatch
      L3  Task          [WORK] Patch + regression test (parallel)
T+10  L0  Project       Dispatch Stage: Test → Release
T+14  L0  Project       All PASS → hotfix deployed + task quality score
```

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
