---
id: "agent/examples/full-pipeline-trace"
version: "1.0.0"
purpose: >
  Complete delegation chain walkthrough for a new CLI tool implementation
  using the full-pipeline workflow. Demonstrates all 4 layers, 6 message
  types, and parallel task dispatch across 7 stages.
triggers:
  - "Need a full-pipeline execution example"
  - "How does delegation work end-to-end"
  - "Show me a complete workflow trace"
tier: 3
token_estimate: 4500
last_updated: "2026-04-04"
---

# Full-Pipeline Delegation Trace

## Scenario

A user requests implementation of a new CLI tool for file synchronization.
The Project Agent selects `full-pipeline` workflow, which defines 7 stages:
design → plan → impl → review → test → testgate → release.

**Project:** `filesync` — a Rust CLI tool for bidirectional file sync.
**Workflow type:** `full-pipeline`
**Gate profile:** `standard` (composite ≥ 85, coverage ≥ 80%)

## Full Delegation Trace

```
TIME  LAYER  AGENT              ACTION                           MESSAGE TYPE
─────────────────────────────────────────────────────────────────────────────────
T+0   L0   Project Agent       Receive user request              —
T+1   L0   Project Agent       Select workflow: full-pipeline    —
T+2   L0   Project Agent       Dispatch Stage: Design            StageDispatch

      L1   Stage:Design        Receive StageDispatch             —
      L1   Stage:Design        Decompose → 2 waves               —
      L1   Stage:Design        Dispatch Wave 1                   WaveDispatch
      L2   Wave:D-W1           Dispatch Task: Research APIs      TaskDispatch
      L3   Task:Research       [WORK] Survey sync protocols      —
      L3   Task:Research       Return research report            StatusReport
      L2   Wave:D-W1           Collect results                   WaveReport
      L1   Stage:Design        Dispatch Wave 2                   WaveDispatch
      L2   Wave:D-W2           Dispatch Task: Write design doc   TaskDispatch
      L3   Task:Design         [WORK] Author architecture        —
      L3   Task:Design         Return design document            StatusReport
      L2   Wave:D-W2           Collect results                   WaveReport
      L1   Stage:Design        Gate evaluation: PASS             —
      L1   Stage:Design        Report to Project                 StageReport(PASS)

T+10  L0   Project Agent       Receive StageReport(PASS)         —
T+11  L0   Project Agent       Dispatch Stage: Plan              StageDispatch

      L1   Stage:Plan          Receive StageDispatch             —
      L1   Stage:Plan          Decompose → 1 wave                —
      L1   Stage:Plan          Dispatch Wave 1                   WaveDispatch
      L2   Wave:P-W1           Dispatch Task: Create plan        TaskDispatch
      L3   Task:Design         [WORK] Decompose into waves       —
      L3   Task:Design         Return implementation plan        StatusReport
      L2   Wave:P-W1           Collect results                   WaveReport
      L1   Stage:Plan          Gate evaluation: PASS             —
      L1   Stage:Plan          Report to Project                 StageReport(PASS)

T+20  L0   Project Agent       Receive StageReport(PASS)         —
T+21  L0   Project Agent       Dispatch Stage: Impl              StageDispatch

      L1   Stage:Impl          Receive StageDispatch             —
      L1   Stage:Impl          Read plan: 3 waves, 9 tasks       —
      L1   Stage:Impl          Dispatch Wave 1 (scaffold)        WaveDispatch

      L2   Wave:I-W1           Dispatch Task: Scaffold project   TaskDispatch
      L3   Task:Implement      [WORK] Create Cargo.toml, main    —
      L3   Task:Implement      Return scaffold                   StatusReport
      L2   Wave:I-W1           Collect results                   WaveReport
      L1   Stage:Impl          Dispatch Wave 2 (parallel core)   WaveDispatch

      L2   Wave:I-W2           Dispatch 4 parallel tasks         TaskDispatch ×4
      L3   Task:Impl-A         [WORK] Implement config module    —  ┐
      L3   Task:Impl-B         [WORK] Implement sync engine      —  │ PARALLEL
      L3   Task:Impl-C         [WORK] Implement storage layer    —  │
      L3   Task:Impl-D         [WORK] Implement error types      —  ┘
      L3   Task:Impl-A         Return code + tests               StatusReport
      L3   Task:Impl-B         Return code + tests               StatusReport
      L3   Task:Impl-C         Return code + tests               StatusReport
      L3   Task:Impl-D         Return code + tests               StatusReport
      L2   Wave:I-W2           Conflict check: OK                —
      L2   Wave:I-W2           Collect results                   WaveReport
      L1   Stage:Impl          Dispatch Wave 3 (integration)     WaveDispatch

      L2   Wave:I-W3           Dispatch 2 tasks                  TaskDispatch ×2
      L3   Task:Impl-E         [WORK] Wire CLI interface         —  ┐ PARALLEL
      L3   Task:Impl-F         [WORK] Integration tests          —  ┘
      L3   Task:Impl-E         Return code                       StatusReport
      L3   Task:Impl-F         Return tests                      StatusReport
      L2   Wave:I-W3           Collect results                   WaveReport
      L1   Stage:Impl          Gate evaluation: PASS             —
      L1   Stage:Impl          Report to Project                 StageReport(PASS)

T+40  L0   Project Agent       Receive StageReport(PASS)         —
T+41  L0   Project Agent       Dispatch Stage: Review            StageDispatch

      L1   Stage:Review        Receive StageDispatch             —
      L1   Stage:Review        Dispatch Wave 1                   WaveDispatch
      L2   Wave:R-W1           Dispatch 3 parallel reviews       TaskDispatch ×3
      L3   Task:Review-Code    [WORK] Code quality review        —  ┐
      L3   Task:Review-Sec     [WORK] Security review            —  │ PARALLEL
      L3   Task:Review-SOLID   [WORK] Architecture review        —  ┘
      L3   Task:Review-Code    Return findings (score: 88)       StatusReport
      L3   Task:Review-Sec     Return findings (score: 92)       StatusReport
      L3   Task:Review-SOLID   Return findings (score: 85)       StatusReport
      L2   Wave:R-W1           Aggregate scores                  WaveReport
      L1   Stage:Review        Composite: 88×0.3+92×0.3+85×0.4  —
                               = 26.4 + 27.6 + 34.0 = 88.0
      L1   Stage:Review        Gate: PASS (88 ≥ 85, 0 blockers) —
      L1   Stage:Review        Report to Project                 StageReport(PASS)

T+50  L0   Project Agent       Dispatch Stage: Test              StageDispatch

      L1   Stage:Test          Decompose → 1 wave, 2 tasks       —
      L1   Stage:Test          Dispatch Wave 1                   WaveDispatch
      L2   Wave:T-W1           Dispatch 2 parallel tasks         TaskDispatch ×2
      L3   Task:Test-Unit      [WORK] Run cargo test (all pass)  —  ┐ PARALLEL
      L3   Task:Test-Integ     [WORK] Run integration suite      —  ┘
      L3   Task:Test-Unit      Return: 47/47 pass, 83% cov      StatusReport
      L3   Task:Test-Integ     Return: 12/12 pass                StatusReport
      L2   Wave:T-W1           Collect results                   WaveReport
      L1   Stage:Test          Gate: PASS (zero failures)        —
      L1   Stage:Test          Report to Project                 StageReport(PASS)

T+55  L0   Project Agent       Dispatch Stage: TestGate          StageDispatch

      L1   Stage:TestGate      Gate type: passthrough             —
      L1   Stage:TestGate      Forward upstream results           —
      L1   Stage:TestGate      Report to Project                 StageReport(PASS)

T+60  L0   Project Agent       Dispatch Stage: Release           StageDispatch

      L1   Stage:Release       Decompose → 1 wave, 1 task        —
      L1   Stage:Release       Dispatch Wave 1                   WaveDispatch
      L2   Wave:Rel-W1         Dispatch Task: Release             TaskDispatch
      L3   Task:Implement      [WORK] git tag v0.1.0              —
                               Update CHANGELOG.md
                               Create release commit
      L3   Task:Implement      Return release artifacts           StatusReport
      L2   Wave:Rel-W1         Collect results                   WaveReport
      L1   Stage:Release       Gate: PASS                         —
      L1   Stage:Release       Report to Project                 StageReport(PASS)

T+65  L0   Project Agent       All 7 stages PASS                 —
      L0   Project Agent       Produce final project report      —
      L0   Project Agent       Present to user                   —
```

## Message Type Examples

### StageDispatch (Project → Stage)

```yaml
task_dispatch:
  header:
    dispatch_id: "d-20260404-003"
    parent_id: "project-root"
    layer: "project"
    timestamp: "2026-04-04T10:45:00Z"
    timeout_seconds: 7200
  task:
    task_id: "S03-impl"
    type: "stage"
    title: "Implementation Stage"
    description: >
      Implement the filesync CLI per the approved design.
      Plan contains 3 waves with 9 total tasks.
  context:
    predecessor_artifacts:
      - artifact_id: "design-doc-v1"
        path: ".local/stages/S01_design/design_document.md"
        summary: "Approved architecture: 4 modules, Rust 1.80+, async I/O"
      - artifact_id: "impl-plan-v1"
        path: ".local/stages/S02_plan/implementation_plan.md"
        summary: "3-wave plan: W1=scaffold, W2=core (4 parallel), W3=integration"
    owned_files: []
    applicable_rules:
      loading_strategy: "full"
      language: "rust"
      task_type: "new_feature"
      quality_focus: ["security", "maintainability"]
    shared_context: "Target: Rust 1.80+, no unsafe, min coverage 80%"
  acceptance:
    criteria:
      - "All 9 tasks completed with PASS status"
      - "cargo build succeeds with zero warnings"
      - "cargo test passes with >= 80% coverage"
    quality_thresholds:
      coverage_pct: 80
      quality_score: 85
      max_blocker_findings: 0
    max_retry_rounds: 2
```

### WaveDispatch (Stage → Wave)

```yaml
task_dispatch:
  header:
    dispatch_id: "d-20260404-012"
    parent_id: "d-20260404-003"
    layer: "stage"
    timestamp: "2026-04-04T11:00:00Z"
    timeout_seconds: 3600
  task:
    task_id: "S03-W02"
    type: "wave"
    title: "Core Module Implementation (Parallel)"
    description: >
      4 parallel tasks implementing config, sync engine, storage, and error types.
      File ownership is disjoint across all tasks.
  context:
    predecessor_artifacts:
      - artifact_id: "scaffold-v1"
        path: "src/main.rs"
        summary: "Scaffold with Cargo.toml, main.rs, lib.rs, error.rs created"
    owned_files: []
    applicable_rules:
      loading_strategy: "standard"
      language: "rust"
```

### TaskDispatch (Wave → Task)

```yaml
task_dispatch:
  header:
    dispatch_id: "d-20260404-015"
    parent_id: "d-20260404-012"
    layer: "wave"
    timestamp: "2026-04-04T11:02:00Z"
    timeout_seconds: 1800
  task:
    task_id: "S03-W02-T01"
    type: "code"
    title: "Implement ConfigManager"
    description: >
      Implement the ConfigManager module per design_document.md §3.2.
      Read config from TOML, env vars, CLI args with merge precedence.
  context:
    predecessor_artifacts:
      - artifact_id: "design-sec-3.2"
        path: ".local/stages/S01_design/design_document.md"
        summary: "ConfigManager: 4 methods, ConfigSource trait, TOML+env+CLI merge"
    owned_files:
      - "src/config/manager.rs"
      - "src/config/mod.rs"
      - "tests/config/manager_test.rs"
    applicable_rules:
      loading_strategy: "standard"
      language: "rust"
      task_type: "new_feature"
      quality_focus: ["maintainability"]
  acceptance:
    criteria:
      - "cargo build succeeds with zero warnings"
      - "cargo test config:: passes with >= 80% coverage"
      - "ConfigManager satisfies all 4 interface methods from design §3.2"
    quality_thresholds:
      coverage_pct: 80
      max_blocker_findings: 0
    max_retry_rounds: 1
```

### StatusReport (Task → Wave)

```yaml
status_report:
  header:
    report_id: "r-20260404-042"
    dispatch_id: "d-20260404-015"
    task_id: "S03-W02-T01"
    layer: "task"
    timestamp: "2026-04-04T11:18:00Z"
  status:
    state: "completed"
    progress_pct: 100
    started_at: "2026-04-04T11:02:00Z"
    completed_at: "2026-04-04T11:18:00Z"
    elapsed_seconds: 960
  result:
    artifacts:
      - artifact_id: "config-manager"
        path: "src/config/manager.rs"
        type: "source"
        summary: "ConfigManager with TOML/env/CLI merge, 4 public methods"
      - artifact_id: "config-tests"
        path: "tests/config/manager_test.rs"
        type: "test"
        summary: "12 unit tests covering all merge precedence cases"
    metrics:
      tests_passed: 12
      tests_failed: 0
      coverage_pct: 87.3
      findings_by_severity:
        blocker: 0
        critical: 0
        major: 0
        minor: 1
        info: 2
  issues:
    blockers: []
    warnings: ["1 minor: consider extracting TOML parsing into separate function"]
    deferred: []
```

### WaveReport (Wave → Stage)

```yaml
status_report:
  header:
    report_id: "r-20260404-050"
    dispatch_id: "d-20260404-012"
    task_id: "S03-W02"
    layer: "wave"
    timestamp: "2026-04-04T11:22:00Z"
  status:
    state: "completed"
    progress_pct: 100
    started_at: "2026-04-04T11:00:00Z"
    completed_at: "2026-04-04T11:22:00Z"
    elapsed_seconds: 1320
  result:
    artifacts:
      - artifact_id: "wave-2-aggregate"
        path: ".local/stages/S03_impl/waves/W02/report.yaml"
        type: "report"
        summary: "4/4 tasks PASS. Config, sync, storage, error modules implemented"
    metrics:
      tests_passed: 47
      tests_failed: 0
      coverage_pct: 83.1
  issues:
    blockers: []
    warnings: ["3 minor findings across 4 tasks"]
    deferred: []
```

### StageReport (Stage → Project)

```yaml
status_report:
  header:
    report_id: "r-20260404-060"
    dispatch_id: "d-20260404-003"
    task_id: "S03-impl"
    layer: "stage"
    timestamp: "2026-04-04T11:40:00Z"
  status:
    state: "completed"
    progress_pct: 100
    started_at: "2026-04-04T10:45:00Z"
    completed_at: "2026-04-04T11:40:00Z"
    elapsed_seconds: 3300
  result:
    artifacts:
      - artifact_id: "impl-complete"
        path: ".local/stages/S03_impl/"
        type: "source"
        summary: "9 tasks, 3 waves. All modules implemented with tests"
    metrics:
      tests_passed: 59
      tests_failed: 0
      coverage_pct: 83.1
      quality_score: 88.0
  issues:
    blockers: []
    warnings: ["5 minor findings deferred to review stage"]
    deferred: []
  gate_decision:
    verdict: "PASS"
    rationale: "composite=88.0 >= 85, zero blockers, coverage 83.1% >= 80%"
    loop_back_target: null
```

## Key Observations

| Metric | Value |
|--------|-------|
| Total Task Agents spawned | 18 (2+1+9+3+2+0+1) |
| Maximum parallelism | 4 tasks (Wave I-W2) |
| Total stages | 7 |
| Total gate evaluations | 7 (6 standard + 1 passthrough) |
| Context per Task Agent | ~8K tokens injected |
| Composite score (review) | 88.0 (88×0.3 + 92×0.3 + 85×0.4) |
| Project Agent decisions | 7 dispatches, 7 gate evaluations |

**Context isolation evidence:**
- No source code ever reached the Project Agent (L0)
- Each Task Agent received only its `owned_files` and a 3-sentence predecessor summary
- Parallel tasks in Wave I-W2 had disjoint file ownership (config/*, sync/*, storage/*, error.rs)
- The Review stage's 3 parallel reviewers each received different review dimensions
- Wave Agents never modified or inspected task outputs directly

**Message type distribution:**
- 7 StageDispatch messages (Project → Stage)
- 8 WaveDispatch messages (Stage → Wave, including convergence-capable stages)
- 18 TaskDispatch messages (Wave → Task)
- 18 StatusReport messages (Task → Wave)
- 8 WaveReport messages (Wave → Stage)
- 7 StageReport messages (Stage → Project)
