---
id: "agent/references/message-schemas"
version: "1.0.0"
purpose: >
  Full YAML schemas for TaskDispatch, StatusReport, and ExceptionEscalation
  messages used in inter-layer communication. Includes field-by-field
  documentation, complete examples, and an ASCII sequence diagram of message
  flow between layers.
triggers:
  - "constructing dispatch messages"
  - "parsing status reports"
  - "handling escalations"
tier: 2
token_estimate: 3600
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-04"
---

# Message Schemas Reference

## 1. Protocol Rules
From §3:

- All inter-layer communication uses typed YAML schemas
- Free-form natural language between layers is **prohibited**
- Messages are written to the project tracking directory
- Three message types: TaskDispatch (down), StatusReport (up), ExceptionEscalation (up)

## 2. TaskDispatch Schema (Parent → Child)
From §3.1:

Used at every layer boundary: Project→Stage, Stage→Wave, Wave→Task.

```yaml
task_dispatch:
  header:
    dispatch_id: "string (UUID)"        # unique identifier
    parent_id: "string (UUID)"          # parent's dispatch_id
    layer: "project | stage | wave"     # dispatching layer
    timestamp: "ISO8601"
    timeout_seconds: "integer"          # hard timeout for child

  task:
    task_id: "string"                   # human-readable (S03, W02, T04)
    type: "string"                      # stage | wave | code | test | review
                                        #   | research | design | benchmark
    title: "string"                     # short descriptive title
    description: "string"              # what to do (not how)

  context:
    predecessor_artifacts:              # artifacts from prior stages/waves
      - artifact_id: "string"
        path: "string"                  # file path
        summary: "string"              # 1-2 sentence summary (NOT full content)
    owned_files:                        # authorized read/modify files
      - "string (file path)"
    applicable_rules:                   # code-rules loading config
      loading_strategy: "minimal | standard | full"
      language: "string | null"
      task_type: "string | null"
      quality_focus: ["string"]
    shared_context: "string | null"    # project-wide context (max 500 tokens)

  acceptance:
    criteria:                           # testable done-when conditions
      - "string"
    quality_thresholds:
      coverage_pct: "number | null"
      quality_score: "number | null"
      max_blocker_findings: "integer"   # typically 0
    max_retry_rounds: "integer"
```

### Field Documentation

| Field | Required | Description |
|-------|----------|-------------|
| `dispatch_id` | YES | UUID; used for traceability across all messages |
| `parent_id` | YES | Links to parent's dispatch_id; "project-root" for L0 |
| `layer` | YES | Which layer is dispatching; determines context scope |
| `timeout_seconds` | YES | Hard deadline; child must complete or fail |
| `task_id` | YES | Human-readable; unique within parent scope |
| `type` | YES | Determines AgentTeam role at L3 |
| `title` | YES | < 80 chars; used in progress dashboard |
| `description` | YES | Detailed spec; 100-500 tokens |
| `predecessor_artifacts` | NO | Summaries only — never full artifact content |
| `owned_files` | YES (L3) | Empty for L0→L1 dispatches |
| `applicable_rules` | YES (L3) | Code-rules loading configuration |
| `shared_context` | NO | Max 500 tokens; project-wide constraints |
| `criteria` | YES | Binary testable conditions |
| `quality_thresholds` | NO | Numeric gates; null = no threshold |
| `max_retry_rounds` | YES | How many retries on failure |

### Example — Project Agent dispatching Impl stage

```yaml
task_dispatch:
  header:
    dispatch_id: "d-20260404-001"
    parent_id: "project-root"
    layer: "project"
    timestamp: "2026-04-04T10:30:00Z"
    timeout_seconds: 7200

  task:
    task_id: "S03-impl"
    type: "stage"
    title: "Implementation Stage"
    description: >
      Implement the designed architecture per the approved plan.
      Plan contains 3 waves with 11 total tasks.
      Each wave must complete before the next begins.

  context:
    predecessor_artifacts:
      - artifact_id: "design-doc-v2"
        path: ".local/stages/S01_design/design_document.md"
        summary: "Approved architecture with 5 modules, 3 external interfaces"
      - artifact_id: "impl-plan-v1"
        path: ".local/stages/S02_plan/implementation_plan.md"
        summary: "3-wave plan: W1=scaffold, W2=core modules, W3=integration"
    owned_files: []
    applicable_rules:
      loading_strategy: "full"
      language: "rust"
      task_type: "new_feature"
      quality_focus: ["security", "maintainability"]
    shared_context: "Target: Rust 1.80+, no unsafe, min coverage 80%"

  acceptance:
    criteria:
      - "All 11 tasks completed with PASS status"
      - "cargo build succeeds with zero warnings"
      - "cargo test passes with >= 80% coverage"
      - "Zero blocker findings in final review"
    quality_thresholds:
      coverage_pct: 80
      quality_score: 85
      max_blocker_findings: 0
    max_retry_rounds: 2
```

## 3. StatusReport Schema (Child → Parent)
From §3.2:

```yaml
status_report:
  header:
    report_id: "string (UUID)"
    dispatch_id: "string"              # references original dispatch
    task_id: "string"
    layer: "stage | wave | task"
    timestamp: "ISO8601"

  status:
    state: "pending | in_progress | completed | failed | escalated"
    progress_pct: "integer (0-100)"
    started_at: "ISO8601"
    completed_at: "ISO8601 | null"
    elapsed_seconds: "integer"

  result:
    artifacts:                          # files produced
      - artifact_id: "string"
        path: "string"
        type: "source | test | document | report | config"
        summary: "string"
    metrics:
      tests_passed: "integer | null"
      tests_failed: "integer | null"
      coverage_pct: "number | null"
      quality_score: "number | null"
      findings_by_severity:
        blocker: "integer"
        critical: "integer"
        major: "integer"
        minor: "integer"
        info: "integer"

  issues:
    blockers: ["string"]               # prevented completion
    warnings: ["string"]               # non-blocking concerns
    deferred: ["string"]               # pushed to later stages

  gate_decision:                        # only for Stage-level reports
    verdict: "PASS | FAIL | ESCALATE | null"
    rationale: "string"
    loop_back_target: "string | null"
```

### Field Documentation

| Field | Required | Description |
|-------|----------|-------------|
| `report_id` | YES | UUID; unique per report |
| `dispatch_id` | YES | Links back to the originating dispatch |
| `state` | YES | Current execution state |
| `progress_pct` | YES | 0-100; estimated completion percentage |
| `artifacts` | NO | Files produced; empty if task failed early |
| `metrics` | NO | Quantitative results; null fields = not measured |
| `findings_by_severity` | NO | Severity breakdown; all zeros if no review done |
| `blockers` | NO | Items preventing completion |
| `gate_decision` | STAGE ONLY | null for wave/task level reports |
| `verdict` | STAGE ONLY | PASS/FAIL/ESCALATE |
| `loop_back_target` | STAGE ONLY | Which stage to return to on FAIL |

### Example — Task Agent reporting completion

```yaml
status_report:
  header:
    report_id: "r-20260404-007"
    dispatch_id: "d-20260404-007"
    task_id: "S03_W02_T01"
    layer: "task"
    timestamp: "2026-04-04T11:15:00Z"

  status:
    state: "completed"
    progress_pct: 100
    started_at: "2026-04-04T10:55:00Z"
    completed_at: "2026-04-04T11:15:00Z"
    elapsed_seconds: 1200

  result:
    artifacts:
      - artifact_id: "config-manager-src"
        path: "src/config/manager.rs"
        type: "source"
        summary: "ConfigManager impl with TOML + env + CLI merge"
      - artifact_id: "config-manager-test"
        path: "tests/config/manager_test.rs"
        type: "test"
        summary: "12 unit tests covering all 4 interface methods"
    metrics:
      tests_passed: 12
      tests_failed: 0
      coverage_pct: 87.3
      quality_score: null
      findings_by_severity:
        blocker: 0
        critical: 0
        major: 0
        minor: 0
        info: 0

  issues:
    blockers: []
    warnings: []
    deferred: []

  gate_decision: null
```

## 4. ExceptionEscalation Schema (Child → Parent)
From §3.3:

```yaml
exception_escalation:
  header:
    escalation_id: "string (UUID)"
    dispatch_id: "string"
    task_id: "string"
    layer: "stage | wave | task"
    timestamp: "ISO8601"

  error:
    error_type: "recoverable | blocking | fatal"
    category: "tool_failure | context_overflow | ambiguous_spec
              | dependency_missing | quality_threshold | timeout | conflict"
    description: "string"             # human-readable description
    evidence: "string | null"         # relevant output (max 500 tokens)

  impact:
    affected_tasks: ["string"]        # task_ids affected
    blocking_downstream: "boolean"    # blocks subsequent work?
    data_loss_risk: "boolean"         # could retrying corrupt data?

  suggested_action:
    action: "retry | skip | abort | reassign | request_human_input | modify_spec"
    details: "string"                 # specific recommendation
    estimated_resolution: "string"    # time estimate
```

### Error Type Classification

| Error Type | Definition | Parent Response |
|-----------|------------|-----------------|
| `recoverable` | Transient failure (network, rate limit). Retrying likely succeeds. | Auto-retry up to max. Exhausted → promote to `blocking`. |
| `blocking` | Cannot proceed without intervention. Ambiguous spec, missing dep, conflicts. | Evaluate: modify spec, reassign, or escalate further. |
| `fatal` | Unrecoverable. Corrupted state, impossible requirement, persistent failures. | Halt stage. Project Agent produces divergence report. |

### Example — Task Agent escalating a blocking error

```yaml
exception_escalation:
  header:
    escalation_id: "esc-20260404-001"
    dispatch_id: "d-20260404-008"
    task_id: "S03_W02_T02"
    layer: "task"
    timestamp: "2026-04-04T11:20:00Z"

  error:
    error_type: "blocking"
    category: "ambiguous_spec"
    description: >
      Design doc §3.2 specifies ConfigSource trait with Result<Config>,
      but §4.1 SyncAdapter expects Result<RawConfig>. These types are
      incompatible — cannot implement both interfaces as specified.
    evidence: |
      § 3.2: fn load(&self) -> Result<Config, ConfigError>
      § 4.1: fn adapter_config(&self) -> Result<RawConfig, SyncError>

  impact:
    affected_tasks: ["S03_W02_T02", "S03_W03_T01"]
    blocking_downstream: true
    data_loss_risk: false

  suggested_action:
    action: "modify_spec"
    details: >
      Reconcile §3.2 and §4.1 error types. Recommend unifying on
      a single AppError type. Requires design stage loop-back.
    estimated_resolution: "30 min design fix + re-implementation"
```

## 5. Message Flow Diagram
From §3.4:

```
  Human                Project          Stage           Wave            Task
    │                   Agent            Agent           Agent           Agent
    │                    │                │               │               │
    │──User Request────►│                │               │               │
    │                    │                │               │               │
    │                    │─StageDispatch─►│               │               │
    │                    │                │               │               │
    │                    │                │─WaveDispatch─►│               │
    │                    │                │               │               │
    │                    │                │               │─TaskDispatch─►│(A)
    │                    │                │               │─TaskDispatch─►│(B)
    │                    │                │               │─TaskDispatch─►│(C)
    │                    │                │               │               │
    │                    │                │               │◄─StatusReport─│(A)
    │                    │                │               │◄─StatusReport─│(B)
    │                    │                │               │◄─StatusReport─│(C)
    │                    │                │               │               │
    │                    │                │◄─WaveReport───│               │
    │                    │                │               │               │
    │                    │                │ (evaluate gate)│               │
    │                    │◄─StageReport───│               │               │
    │                    │                │               │               │
    │                    │ (gate FAIL?)   │               │               │
    │                    │─Re-dispatch───►│               │               │
    │                    │                │               │               │
    │◄─Project Report───│                │               │               │
    │                    │                │               │               │
```

**Error flow (escalation):**

```
  Task ──ExceptionEscalation──► Wave
  Wave ──ExceptionEscalation──► Stage
  Stage ──ExceptionEscalation──► Project
  Project ──Decision Request──► Human
```

## 6. Message Storage Locations
From §Appendix B:

```
.local/stages/
├── S01_design/
│   ├── dispatch.yaml              # StageDispatch (Project → Stage)
│   ├── report.yaml                # StageReport (Stage → Project)
│   └── waves/
│       ├── W01/
│       │   ├── dispatch.yaml      # WaveDispatch (Stage → Wave)
│       │   ├── report.yaml        # WaveReport (Wave → Stage)
│       │   └── tasks/
│       │       ├── T01_dispatch.yaml  # TaskDispatch (Wave → Task)
│       │       └── T01_report.yaml    # StatusReport (Task → Wave)
│       └── W02/ ...
└── S02_plan/ ...

.local/escalations/
└── ESC_001.yaml                   # ExceptionEscalation records
```
