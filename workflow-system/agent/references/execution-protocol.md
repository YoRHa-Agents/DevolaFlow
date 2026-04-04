---
id: "agent/references/execution-protocol"
version: "1.0.0"
purpose: >
  Covers the pre-decision phase (6 steps, 8-section checklist, auto-detection
  rules), checkpoint/resume mechanism, exception severity classification
  (4 levels), human intervention breakpoints (7 HARD, 6 SOFT), execution
  log format, and progress calculation.
triggers:
  - "running pre-decision phase"
  - "checkpoint management"
  - "handling exceptions"
  - "resuming workflow"
tier: 2
token_estimate: 4600
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-04"
---

# Execution Protocol Reference

## 1. Pre-Decision Phase
From §2:

### Phase Sequence (6 Steps)

```
Step 1: DETECT   — Auto-detect repo mode, language, platform
Step 2: COLLECT  — Present checklist to user with detected values
Step 3: VALIDATE — Check consistency (e.g., Rust + npm = error)
Step 4: FREEZE   — Write project_config.yaml, lock decisions
Step 5: RECOMMEND— Auto-recommend workflow type, present for confirmation
Step 6: DISPATCH — Hand off frozen config to Project Agent
```

### Checklist (8 Sections)
From §2.3:

```yaml
pre_decision_checklist:
  # Section 1: Project Identity
  project:
    name: ""                           # MANDATORY
    purpose: ""                        # MANDATORY
    existing_codebase: false           # CONFIRM — detected from scan

  # Section 2: Tech Stack
  tech_stack:
    primary_language: ""               # MANDATORY (auto-detect → CONFIRM)
    build_system: ""                   # CONFIRM — auto-detected
    dependency_manifest: ""            # CONFIRM — auto-detected
    runtime_version: ""                # DEFAULTED — "latest stable"

  # Section 3: Repository Mode
  repository:
    mode: ""                           # CONFIRM — auto-detected
    remote_url: ""                     # CONFIRM — auto-detected
    default_branch: "main"             # CONFIRM
    features:
      ci_cd: false                     # DEFAULTED per mode
      release_publishing: false        # DEFAULTED per mode

  # Section 4: Language & Localization
  localization:
    primary_language: "en"             # DEFAULTED
    code_comments_language: "en"       # DEFAULTED

  # Section 5: Target Platforms
  platforms:
    os: ["linux"]                      # DEFAULTED — current OS
    architectures: ["x86_64"]          # DEFAULTED — current arch

  # Section 6: Quality Standards
  quality:
    coverage_target_pct: 80            # DEFAULTED
    quality_score_threshold: 85        # DEFAULTED
    gate_profile: "standard"           # DEFAULTED
    max_convergence_rounds: 3          # DEFAULTED

  # Section 7: Release Strategy
  release:
    versioning: "semver"               # DEFAULTED
    initial_version: "0.1.0"           # DEFAULTED

  # Section 8: Workflow Selection
  workflow:
    type: ""                           # CONFIRM — auto-recommended
    skip_stages: []                    # DEFAULTED
```

### Decision Point Categories

| Category | Symbol | Rule | Blocking? |
|----------|--------|------|-----------|
| **MANDATORY** | `⬚` | No default; user MUST provide | YES |
| **DEFAULTED** | `○` | Has sensible default; user CAN override | NO |
| **CONFIRM** | `☑` | Auto-detected; user should verify | SOFT |

### Auto-Detection Rules
From §2.4:

| Target | Method | Examples |
|--------|--------|---------|
| Repository mode | `git remote -v` | `github.com` → github; no remote → local |
| Primary language | File extension frequency | `*.rs` > 50% → rust |
| Build system | Manifest file presence | `Cargo.toml` → cargo; `package.json` → npm |
| Framework | Dependency analysis | `actix-web` → actix; `react` → react |
| Workflow type | Keyword heuristics | "fix bug" → hotfix; "build from scratch" → full_pipeline |

### Consistency Validation Rules
From §3.4:

| Rule | Condition | Severity |
|------|-----------|----------|
| language_build_match | Rust + not cargo | error |
| github_features_need_github | GitHub Actions + not github mode | error |
| cross_platform_needs_targets | Cross-platform build + < 2 OS targets | warning |
| security_review_with_audit | security_audit workflow + no security review | auto_fix |
| coverage_in_range | coverage < 0 or > 100 | error |
| gate_profile_consistency | strict profile + coverage < 90% | warning |
| local_no_publish | local mode + publishing targets | warning |

## 2. Checkpoint/Resume Mechanism
From §4:

### Checkpoint Storage

```
.local/
├── checkpoints/
│   ├── checkpoint_latest.yaml          # symlink → most recent
│   ├── cp_20260404T103000Z_S01_gate.yaml
│   ├── cp_20260404T110000Z_S02_gate.yaml
│   └── ...
├── project_config.yaml                 # frozen pre-decision config
└── project_status.yaml                 # live dashboard
```

### Checkpoint Schema

```yaml
checkpoint:
  metadata:
    checkpoint_id: "cp_{timestamp}_{trigger}"
    timestamp: "ISO8601"
    trigger: "stage_gate_pass | wave_complete | manual | error_recovery"
    workflow_run_id: "string"

  project_state:
    workflow_type: "string"
    config_hash: "sha256:..."          # drift detection

  stage_progress:
    completed_stages:
      - stage_id: "string"
        gate_verdict: "PASS"
        artifacts: [{ path, hash }]
    current_stage:
      stage_id: "string"
      status: "in_progress"
      current_wave: "string"
      waves_completed: ["string"]
    pending_stages: ["string"]

  convergence_state:
    current_round: "integer"
    max_rounds: "integer"
    round_history: [{ round, score, timestamp }]

  quality_snapshot:
    last_composite_score: "number | null"
    last_coverage_pct: "number | null"
    total_findings: { blocker, critical, major, minor, info }
```

### Checkpoint Trigger Rules
From §4.4:

| Trigger | When | Retention |
|---------|------|-----------|
| stage_gate_pass | After gate evaluates PASS | Permanent |
| stage_gate_fail | After gate evaluates FAIL | Permanent |
| wave_complete | After all tasks in wave complete | Rolling (next wave replaces) |
| convergence_round_complete | After all 8 convergence phases finish | Until stage gates PASS |
| error_recovery | After AUTO_RECOVER retry succeeds | Until wave completes |
| human_intervene_pause | When workflow pauses for human | Permanent |
| manual | User explicitly requests | Permanent |

### Resume Logic
From §4.5:

```
Workflow Start Request
  │
  ├─ checkpoint_latest.yaml exists?
  │   ├─ NO → Start fresh (Pre-Decision Phase)
  │   └─ YES → Load checkpoint
  │       ├─ Config hash matches? → Identify resume point
  │       └─ Config drift? → Present diff → User approves? → Update / Restart
  │
  ├─ Active escalations? → Present to user first → Resolve → Resume
  │
  └─ Resume from checkpoint:
      ├─ current_stage completed → Advance to next pending stage
      ├─ current_wave completed → Dispatch next wave
      ├─ tasks partially complete → Re-dispatch only incomplete tasks
      └─ no tasks complete → Re-dispatch entire wave
```

**Critical resume invariants:**
1. Never re-execute a completed stage (gate PASS = done)
2. Never re-execute completed tasks in a wave
3. Verify artifact integrity (hash check) before resuming
4. Preserve convergence round state (resume mid-round)
5. Config drift requires user approval

## 3. Exception Severity Classification
From §5:

### 4 Severity Levels

| Level | Description | Auto-Action | Human? |
|-------|-------------|-------------|--------|
| **AUTO_RECOVER** | Transient errors (network, rate limit, tool timeout, flaky test) | Retry up to 3× with exponential backoff (2s, 4s, 8s) | NO — promote to PAUSE if exhausted |
| **PAUSE** | Non-urgent info gaps (ambiguous spec, missing optional dep, style decision) | Pause affected task. Queue question. Continue parallel work | BATCHED — at wave boundary or 3 questions |
| **HUMAN_INTERVENE** | Decisions needing human judgment (arch trade-offs, security, credentials, irreversible ops) | Stop affected stage. Present options. Wait | YES — immediately with structured options |
| **FULL_ROLLBACK** | Fundamental errors (corrupted state, impossible requirement, persistent tool failure, data loss) | Rollback to last checkpoint. Halt all execution | YES — with failure report |

### Classification Rules
From §5.2:

**AUTO_RECOVER triggers:**
- network_timeout (retry_count < 3)
- rate_limit (retry_count < 3)
- tool_timeout (retry_count < 3, elapsed < timeout)
- flaky_test (was passing before, retry_count < 2)
- build_cache_stale (clean build not yet attempted)
- git_lock (lock age < 60s)

**PAUSE triggers:**
- ambiguous_specification
- optional_dependency_missing
- style_decision (multiple valid approaches)
- non_critical_test_failure
- auto_recover_exhausted

**HUMAN_INTERVENE triggers:**
- architecture_decision (DB selection, API paradigm)
- security_sensitive (crypto, auth, permissions)
- external_service_config (API keys, service accounts)
- irreversible_operation (production migration, public API)
- license_compliance (GPL in MIT project)
- cost_implication (paid API, cloud resources)
- scope_expansion

**FULL_ROLLBACK triggers:**
- state_corruption (hash mismatch, missing files)
- impossible_requirement
- persistent_tool_failure (all retries exhausted)
- data_loss_detected
- dependency_incompatibility

### Escalation Flow

```
Task Agent encounters error
  │
  ├─ AUTO_RECOVER? → Retry (up to 3)
  │   ├─ Success → Continue, log recovery
  │   └─ Exhausted → Promote to PAUSE
  │
  ├─ PAUSE? → Pause task, queue question
  │   Wave continues other tasks
  │   Batch trigger → present to user → Resume
  │
  ├─ HUMAN_INTERVENE? → Report upward: Wave → Stage → Project → User
  │   Present structured decision → Wait → Resume with decision
  │
  ├─ FULL_ROLLBACK? → Halt immediately
  │   Rollback to last valid checkpoint → Present failure report
  │
  └─ Unknown → Classify as PAUSE (conservative default)
```

### Layer Responsibility

| Severity | L3 Task | L2 Wave | L1 Stage | L0 Project | Human |
|----------|---------|---------|----------|------------|-------|
| AUTO_RECOVER | **Handles** | Notified | — | — | — |
| PAUSE | **Detects** | Continues parallel, batches | Aggregates | **Presents** batch | Answers |
| HUMAN_INTERVENE | **Detects** | Passes through | Passes through | **Presents** options | **Decides** |
| FULL_ROLLBACK | **Detects** | Halts tasks | **Executes** rollback | **Reports** | Reviews |

## 4. Human Intervention Breakpoints
From §6:

### HARD Breakpoints (7) — Workflow MUST Stop

| ID | Name | When | Skip Condition |
|----|------|------|----------------|
| HBP-01 | Pre-Decision Confirmation | Before first stage dispatches | Never |
| HBP-02 | Architecture Design Approval | After Design stage gates PASS | hotfix, refactoring, documentation |
| HBP-03 | Security-Sensitive Change | Task modifies auth/crypto/secrets | security_review=false AND test files only |
| HBP-04 | External Service Configuration | Needs API key or service account | Never when credentials needed |
| HBP-05 | Release Publication Approval | Before publishing to registries | local mode OR no publishing targets |
| HBP-06 | Divergence Report Review | Max convergence rounds reached | Never |
| HBP-07 | Full Rollback Acknowledgment | After FULL_ROLLBACK event | Never |

### SOFT Breakpoints (6) — Workflow CAN Continue

| ID | Name | Default Behavior |
|----|------|------------------|
| SBP-01 | Style/Naming Preference | Use language-idiomatic naming |
| SBP-02 | Tool Selection | Use language default (cargo test, jest, pytest) |
| SBP-03 | Optional Feature Inclusion | Skip; log as deferred scope |
| SBP-04 | Documentation Detail Level | API docs + README |
| SBP-05 | Test Strategy for Edge Cases | Write tests up to 90% coverage |
| SBP-06 | Dependency Version Selection | Use latest stable compatible |

All SOFT breakpoints are batched and user can override.

## 5. Execution Log Format
From §7.3:

**Storage:** `.local/execution_log.jsonl` (JSON Lines, append-only)

```yaml
execution_log_entry:
  timestamp: "ISO8601"
  run_id: "string"
  event_type: "string"
  layer: "project | stage | wave | task"
  agent_id: "string"
  stage_id: "string | null"
  wave_id: "string | null"
  task_id: "string | null"
```

**Event types:** `workflow_start`, `stage_dispatch`, `stage_complete`,
`wave_dispatch`, `wave_complete`, `task_dispatch`, `task_complete`,
`gate_evaluation`, `convergence_round`, `quality_score_change`,
`exception_raised`, `auto_recover_attempt`, `pause_queued`,
`human_intervene_requested`, `human_intervene_resolved`,
`rollback_initiated`, `checkpoint_created`, `checkpoint_resumed`,
`handoff_delivered`, `handoff_rejected`

## 6. Progress Calculation
From §7.4:

### Stage Weight Formula

```
total_progress = Σ(stage_weight × stage_progress)

Stage weights (full-pipeline):
  design:   0.10    review:   0.15
  plan:     0.05    test:     0.15
  impl:     0.40    testgate: 0.05
                    release:  0.10
```

### Stage Progress

| Status | Progress |
|--------|----------|
| pending | 0% |
| active (no convergence) | (completed_waves / total_waves) × 100 |
| active (with convergence) | (waves × 0.6) + (rounds / max_rounds × 0.4) |
| completed | 100% |
| skipped | 100% |

### Status Icons

| Icon | Meaning |
|------|---------|
| ✅ PASS | Completed successfully |
| ❌ FAIL | Completed with failure |
| 🔄 ACTIVE | Currently executing |
| ⏳ PENDING | Not yet started |
| ⏸ PAUSED | Waiting for input |
| 🚫 BLOCKED | Cannot proceed |
| ⏭ SKIPPED | Intentionally skipped |
| ⏮ ROLLBACK | Rolled back |

### Estimated Remaining Time

```
remaining = elapsed × (remaining_weight / completed_weight)

Adjustments:
  + 50% if current stage in convergence loop
  + 30% per active blocker
  + 25% if first run (no historical data)
```
