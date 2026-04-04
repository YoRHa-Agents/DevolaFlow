---
name: workflow-orchestrator-mvp
description: >
  Self-contained workflow orchestration skill using a 4-layer agent hierarchy
  (Project, Stage, Wave, Task) with gate quality mechanisms, convergence loops,
  and context-isolated task delegation. Use when implementing features, fixing
  bugs, refactoring, migrating, or running any multi-step development workflow.
  Supports 11 workflow types from research-only to full-pipeline.
---

# Workflow Orchestrator (MVP)

Orchestrate multi-stage software workflows using a 4-layer agent hierarchy with
gate mechanisms, convergence loops, and context-isolated task delegation. This
file is fully self-contained -- no external references required.

## Workflow Type Selection

Select the workflow type that matches the user's intent:

| Type | Trigger Keywords | Stages |
|------|-----------------|--------|
| research-only | research, compare, evaluate, survey | research -> compare -> report |
| design-only | design, architect, API spec, schema | research -> design -> review |
| hotfix | fix bug, broken, crash, urgent, SEV1 | triage -> fix -> test -> release |
| refactoring | refactor, clean up, tech debt | scope -> plan -> implement -> test -> review |
| migration | migrate, upgrade, port, convert | assess -> plan -> implement -> validate -> cutover |
| spike-poc | try, experiment, prototype, PoC | research -> prototype -> evaluate |
| documentation | document, write docs, README | survey -> author -> review |
| security-audit | security, CVE, vulnerability | threat_model -> scan -> analyze -> remediate -> verify |
| feature-enhancement | add to existing, extend, enhance | scope -> design -> plan -> impl -> review -> test -> release |
| full-pipeline | build from scratch, new project | design -> plan -> impl -> review -> test -> refine -> testgate -> release |
| RDRR | design with research, ADR | research -> design -> review -> refine (loop) |

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

## Stage Dispatch Protocol

When dispatching a stage, send a TaskDispatch message:

```yaml
task_dispatch:
  header:
    dispatch_id: "unique-id"
    parent_id: "parent-dispatch-id"
    layer: "project | stage | wave"
    timeout_seconds: 7200
  task:
    task_id: "S03-impl"
    type: "stage | wave | code | test | review | research"
    title: "Implementation Stage"
    description: "What to do (not how)"
  context:
    predecessor_artifacts:
      - artifact_id: "design-doc-v2"
        path: ".local/stages/S01_design/design_document.md"
        summary: "3-5 sentence summary only"
    owned_files: ["src/module_a.py", "tests/test_a.py"]
    applicable_rules:
      loading_strategy: "standard"
      language: "python"
  acceptance:
    criteria: ["All tests pass", "Coverage >= 80%"]
    quality_thresholds:
      coverage_pct: 80
      max_blocker_findings: 0
```

When reporting completion, send a StatusReport:

```yaml
status_report:
  header:
    report_id: "unique-id"
    dispatch_id: "references-original-dispatch"
    task_id: "S03-impl"
  status:
    state: "completed"
    progress_pct: 100
  result:
    artifacts:
      - path: "src/module_a.py"
        type: "source"
        summary: "Implemented module A"
    metrics:
      tests_passed: 15
      coverage_pct: 87.5
      findings_by_severity:
        blocker: 0
        critical: 0
        major: 2
```

## Gate Mechanism

Every stage has a quality gate evaluated after all waves complete.

**Composite Score Formula**:
`composite = test_quality * 0.30 + code_review * 0.30 + architecture * 0.20 + benchmark * 0.20`

**Quality Score per Dimension**:
`quality_score = max(0, 100 - (blocker*25 + critical*15 + major*5 + minor*1))`

**Pass Conditions** (ALL required):
1. `composite_score >= 85` (standard profile)
2. `blocker_findings == 0`
3. `convergence_round >= 1` (at least one review cycle)

**Fail Actions**:
- round < max_rounds (3) -> Run convergence round: review -> fix -> test -> fix
- round >= max_rounds -> ESCALATE to human with divergence report

**Gate Profiles**:

| Profile | Composite | Coverage | Blockers | Max Rounds |
|---------|-----------|----------|----------|------------|
| strict | >= 90 | >= 85% | 0 | 4 |
| standard | >= 85 | >= 80% | 0 | 3 |
| relaxed | >= 70 | >= 60% | 0 | 2 |
| audit | >= 95 | >= 90% | 0 | 6 |

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
- Maximum 5 tasks per wave
- Each task owns a disjoint set of files
- Waves execute sequentially within a stage: Wave N+1 starts after Wave N completes
- Maximum 7 waves per stage

**Task Sizing**:
- Max 30 min (implementation) or 45 min (research/design)
- Max 6 writable files, ~300 lines net change
- If exceeds bounds, decompose further

## Convergence Loop

When a stage gate evaluates FAIL, run a convergence round (max 3):

```
Phase 1: CODE REVIEW (Review Agent)
Phase 2: FIX review findings (Implement Agent)
Phase 3: TEST (Test Agent)
Phase 4: FIX test failures (Implement Agent)
Phase 5: BENCHMARK (Test Agent) -- if enabled
Phase 6: FIX benchmark issues (Implement Agent)
Phase 7: FINAL REVIEW (Review Agent)
Phase 8: FIX final findings (Implement Agent)
-> RE-EVALUATE GATE
```

**Stagnation**: If score does not improve for 2 consecutive rounds, ESCALATE.

## Fail-Forward Protocol

| Severity | Description | Action |
|----------|-------------|--------|
| AUTO_RECOVER | Network timeout, rate limit, tool crash | Retry up to 3x with exponential backoff |
| PAUSE | Ambiguous spec, missing optional dep | Pause task, queue question, continue parallel work |
| HUMAN_INTERVENE | Architecture decision, security change | Stop stage, present options to human |
| FULL_ROLLBACK | Corrupted state, impossible requirement | Rollback to last checkpoint, halt all |

Escalation chain: Task -> Wave -> Stage -> Project -> Human

## Quick Examples

### Full Pipeline Trace (New Feature)
```
T+0   L0  Project       Select workflow: full-pipeline
T+2   L0  Project       Dispatch Stage: Design            -> StageDispatch
      L1  Stage:Design  Decompose -> 2 waves
      L2  Wave:D-W1     Dispatch Task: Research APIs       -> parallel
      L3  Task          [WORK] Survey, produce report
      L1  Stage:Design  Gate: PASS (score 92)              -> advance
T+10  L0  Project       Dispatch Stage: Plan               -> StageDispatch
      L1  Stage:Plan    Gate: PASS                         -> advance
T+20  L0  Project       Dispatch Stage: Impl               -> StageDispatch
      L1  Stage:Impl    3 waves, 9 tasks (max 4 parallel)
      L1  Stage:Impl    Convergence: R1 score=78, R2 score=88 -> PASS
T+50  L0  Project       Dispatch Review -> Test -> Release
T+70  L0  Project       All PASS -> final report
```

### Hotfix Trace (Bug Fix)
```
T+0   L0  Project       Select workflow: hotfix
T+1   L0  Project       Dispatch Stage: Bug-Triage         -> StageDispatch
      L3  Task          [WORK] Analyze root cause: SEV2
T+5   L0  Project       Dispatch Stage: Fix                -> StageDispatch
      L3  Task          [WORK] Patch + regression test (parallel)
T+10  L0  Project       Dispatch Stage: Test -> Release
T+14  L0  Project       All PASS -> hotfix deployed
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
