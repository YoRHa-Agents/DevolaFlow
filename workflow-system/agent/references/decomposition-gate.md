---
id: "agent/references/decomposition-gate"
version: "1.0.0"
purpose: >
  Covers Stage/Wave/Task decomposition rules with sizing guidelines, the wave
  formation algorithm, task definition schema, gate quality mechanism with
  composite score formula, gate profiles, convergence loop detail, and the
  full failure handling chain. Use this when decomposing work, evaluating
  gate quality, or handling failures.
triggers:
  - "decomposing work into stages/waves/tasks"
  - "evaluating gate quality"
  - "handling failures"
tier: 2
token_estimate: 4800
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-04"
---

# Decomposition & Gate Mechanism Reference

## 1. Decomposition Principles
From §1:

| Principle | Rule |
|-----------|------|
| **D1 Monotonic Granularity** | Project → Stage → Wave → Task. Each level strictly increases granularity. A Task never spans two Stages. |
| **D2 Dependency Completeness** | Every dependency explicitly declared. Graph must be a DAG — cycles prohibited. |
| **D3 Bounded Atomicity** | Tasks atomic: ≤30 min (impl), ≤45 min (research). Exceeds bound → decompose further. |
| **D4 Gate-Before-Advance** | No downstream Stage begins until upstream Stage's gate = PASS. |
| **D5 Deterministic Decomposition** | Same spec + workflow type → same Stage/Wave/Task structure. |

## 2. Stage Decomposition
From §2:

### Stage Boundary Criteria

| Criterion | Description | Example |
|-----------|-------------|---------|
| Team Transition | Primary AgentTeam role changes | Design → Implement |
| Artifact Gate | Significant artifact must be validated | Design doc must pass review |
| Quality Checkpoint | Formal quality evaluation required | Code must pass test/review gate |
| Risk Isolation | Failure should not corrupt prior results | Test failures don't modify reviewed code |
| Context Reset | Working context shifts enough for fresh agent | Research mode → code-writing mode |

### Stage Definition Schema

```yaml
stage_definition:
  stage_id: "S{nn}"                      # S01, S02, etc.
  name: "string"
  type: "research | design | plan | implement | review | test | release | triage | fix"
  description: "string"

  position:
    workflow_type: "string"
    sequence_index: "integer"
    is_loopback_target: "boolean"
    loop_back_from: ["string"]

  scope:
    primary_team: "research | design | implement | test | review"
    estimated_waves: "integer"           # 1–7
    estimated_tasks: "integer"

  inputs:
    required_predecessor_stages: ["string"]
    required_artifacts:
      - artifact_type: "string"
        source_stage: "string"
        required: "boolean"

  outputs:
    produced_artifacts:
      - artifact_type: "string"
        description: "string"
    gate_type: "standard | convergence | passthrough"

  acceptance:
    criteria: ["string"]
    quality_thresholds:
      composite_score_min: "number | null"
      coverage_pct_min: "number | null"
      max_blocker_findings: "integer"
    max_convergence_rounds: "integer"    # default 3
```

### Naming Convention

```
Format:  S{nn}_{snake_case_name}     (e.g., S01_research, S04_implement)
Rules:   Two-digit zero-padded index, snake_case max 20 chars, unique within workflow
```

## 3. Wave Decomposition
From §3:

### Wave Formation Algorithm

```
ALGORITHM: WaveDecomposition(stage_definition, task_list)

1. BUILD dependency graph G (nodes=tasks, edges=depends_on + file conflicts)
2. DETECT cycles → ERROR if found
3. COMPUTE topological layers (Kahn's algorithm):
     layer[0] = tasks with in-degree 0
     layer[n+1] = tasks with all deps in layers 0..n
4. PARTITION each layer into waves:
     FOR each topological layer:
       WHILE unassigned tasks remain:
         wave = new Wave()
         FOR each unassigned task:
           IF wave.count < 5
           AND task.owned_files ∩ wave.owned_files == ∅:
             wave.add(task)
         EMIT wave
5. NUMBER waves: W01, W02, ..., W{nn}
```

### Wave Constraints

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Max tasks per wave | 5 | Prevents Wave Agent context overload |
| Min tasks per wave | 1 | Single-task waves valid (scaffold) |
| Max waves per stage | 7 | Observed ceiling across project analysis |
| File ownership | Disjoint (strict) | No two tasks in a wave write same file |
| Read-only sharing | Allowed | Multiple tasks may read same file |

### Wave Pattern Library
From §3.7:

| Pattern | Structure | Use When |
|---------|-----------|----------|
| scaffold_then_parallel | W01:[scaffold] → W02:[A,B,C,D] → W03:[integration] | Impl stage with independent modules |
| research_fanout | W01:[research_a, research_b] → W02:[synthesis] | Research surveying independent topics |
| sequential_pipeline | W01:[a] → W02:[b] → W03:[c] | Strongly ordered work, same files |
| convergence_round | W01:[review] → W02:[fix] → W03:[test] → W04:[fix] | Inside convergence loop stages |
| parallel_review | W01:[review_code, review_sec, review_arch] → W02:[aggregate] | Multi-dimension review |

## 4. Task Decomposition
From §4:

### Task Sizing Rules

```
HARD LIMITS:
  Max wall-clock:    30 min (implementation) / 45 min (research/design)
  Max files owned:   6 writable files
  Max lines changed: ~300 lines net
  Max files read:    15 files

SOFT TARGETS:
  Ideal wall-clock:  10–20 min
  Ideal files owned: 2–4 writable files
  Ideal lines:       50–150 lines net
  Ideal complexity:  Single concern, single module

DECOMPOSE FURTHER WHEN:
  - Requires understanding > 2 distinct subsystems
  - Has internal sequential dependencies
  - Produces > 2 distinct artifact types
  - Estimated time > 30 min
  - Description exceeds 200 words

DO NOT DECOMPOSE WHEN:
  - Single function/method implementation
  - Single test file
  - Single config file change
  - < 50 lines across ≤ 2 files
```

### Task Definition Schema

```yaml
task_definition:
  task_id: "T{nn}"                       # within wave; globally: S{nn}_W{nn}_T{nn}
  wave_id: "string"
  stage_id: "string"
  type: "code | test | review | research | design | benchmark | config | release"

  specification:
    title: "string"                      # < 80 chars
    description: "string"               # 100–300 words
    acceptance_criteria:
      - criterion: "string"
        verification: "string"
    constraints: ["string"]

  scope:
    owned_files:
      create: ["string"]
      modify: ["string"]
      read_only: ["string"]

  dependencies:
    depends_on_tasks: ["string"]
    interface_contracts:
      - name: "string"
        direction: "produces | consumes"
        signature: "string"

  estimation:
    complexity: "L | M | H"
    estimated_minutes: "integer"         # 5–45
    agent_type: "research | design | implement | test | review"
    model_preference: "fast | default"

  timeout_seconds: "integer"
  max_retries: 1
```

### Task Description Template

```
WHAT: [1-2 sentences: what to produce/accomplish]
WHY:  [1 sentence: why this task exists in stage context]
INPUTS:
  - [artifact or file] from [source]: [brief description]
OUTPUTS:
  - [file path]: [what it contains]
CONSTRAINTS:
  - [constraint 1]
DONE WHEN:
  - [binary testable criterion 1]
  - [binary testable criterion 2]
```

## 5. Gate Quality Mechanism
From §5:

### Gate Types

| Type | Rounds | Checks | Use When |
|------|--------|--------|----------|
| **standard** | 1 | build, test, lint, acceptance_criteria | Research, design, plan, release |
| **convergence** | 1–6 (default 3) | code_review, test, benchmark, SOLID, acceptance | Implementation stages |
| **passthrough** | 0 | none | Intermediate aggregation stages |

### Composite Score Formula
From §5.3:

#### Standard Composite (4 dimensions — backward compatible)

```
composite = Σ(dimension_score × weight)

Dimensions:
  test_quality       × 0.30   (tests_passed / tests_total × 100, or coverage_pct)
  code_review        × 0.30   (quality_score from review findings)
  architecture       × 0.20   (SOLID review score)
  benchmark          × 0.20   (benchmark pass_rate, or 100 if no benchmarks)
```

#### Extended Composite (7 dimensions — when user-facing verification is present)

When the product-verification pipeline is active, three additional dimensions are
added and weights are redistributed:

```
composite = test_quality       × 0.20
          + code_review        × 0.20
          + architecture       × 0.15
          + benchmark          × 0.15
          + visual_fidelity    × 0.10
          + interaction_quality × 0.10
          + acceptance_verification × 0.10
```

Selection logic: if any `user_facing_verification` scores are present in the gate
report, the extended formula applies. Otherwise the standard 4-dimension formula
is used. This ensures full backward compatibility.

### Per-Dimension Quality Score
From §5.3:

```
quality_score = max(0, 100 - Σ(severity_weight × finding_count))

Severity weights:
  blocker  = 25
  critical = 15
  major    = 5
  minor    = 1
  info     = 0
```

### User-Facing Verification Dimension Scores (v5.4.0)

Each user-facing dimension follows the same `quality_score` formula above, applied
to findings within that dimension's scope:

| Dimension | Input Source | Score Computation |
|-----------|------------|-------------------|
| **visual_fidelity** | Screenshot diff results, pixel mismatch counts | `max(0, 100 - Σ(severity_weight × finding_count))` where findings are classified by diff magnitude: >10% pixels = blocker, >5% = critical, >2% = major, >0.5% = minor |
| **interaction_quality** | E2E flow results, accessibility audit | `max(0, 100 - Σ(severity_weight × finding_count))` where findings come from failed user flows (blocker/critical) and accessibility violations (severity mapped from WCAG impact level) |
| **acceptance_verification** | Acceptance criteria test results | `max(0, 100 - Σ(severity_weight × finding_count))` where each unmet criterion is a blocker, partially met is critical, met-with-caveats is minor |

### Pass Conditions (ALL required)

1. `composite_score >= threshold` (default 85)
2. Zero blocker findings AND zero MUST-priority violations
3. `coverage >= coverage_threshold` (default 80%)
4. `round >= min_rounds` (default 1)

### On FAIL

- `round < max_rounds` → run another convergence round
- Score stagnant 2+ rounds → escalate
- `round >= max_rounds` → escalate to Project Agent → human

### Gate Profiles
From §5.4:

| Profile | Composite | Coverage | Blockers | Criticals | Min Rounds | Max Rounds | Visual | Interaction | Acceptance | Use When |
|---------|-----------|----------|----------|-----------|------------|------------|--------|-------------|------------|----------|
| **relaxed** | ≥ 70 | ≥ 60% | 0 | ≤ 5 | 1 | 2 | — | — | — | Prototypes, spikes, PoCs |
| **standard** | ≥ 85 | ≥ 80% | 0 | ≤ 2 | 1 | 3 | ≥ 70 | ≥ 70 | ≥ 80 | Default for most projects |
| **strict** | ≥ 90 | ≥ 85% | 0 | 0 | 2 | 4 | ≥ 85 | ≥ 85 | ≥ 90 | Production, public APIs |
| **audit** | ≥ 95 | ≥ 90% | 0 | 0 | 3 | 6 | ≥ 90 | ≥ 90 | ≥ 95 | Security audits, compliance |

Visual/Interaction/Acceptance thresholds apply only when the extended composite
(7-dimension) formula is active. A dash (—) means user-facing verification is
not enforced at that profile level.

### Gate Evaluation Flowchart

```
Stage Waves Complete
        │
        ▼
   ┌─ Gate Type? ─┐
   │              │
passthrough    standard/convergence
   │              │
   ▼              ▼
Forward      Run gate checks
results         │
   │        ┌───▼───┐
   ▼        │ All   │
Advance     │checks │
            │ pass? │
            └───┬───┘
              No│Yes
               │ │
               │ ▼
               │ PASS → Advance
               ▼
         ┌─ round < max? ─┐
         │                 │
        Yes               No
         │                 │
   Score improving?    ESCALATE
         │                 │
    Yes──► NEXT ROUND      ▼
    No───► ESCALATE    Project Agent
                           │
                    ┌──────┼──────┐
                    ▼      ▼      ▼
                  retry   skip   abort/human
```

## 6. Convergence Loop Detail
From §Appendix C (design_agent_hierarchy.md):

```
CONVERGENCE LOOP (per Stage)

Round N:
  Phase 1: CODE REVIEW        (Review Agent)
  Phase 2: FIX review findings (Implement Agent)
  Phase 3: TEST               (Test Agent)
  Phase 4: FIX test failures   (Implement Agent)
  Phase 5: BENCHMARK           (Test Agent)
  Phase 6: FIX benchmark       (Implement Agent)
  Phase 7: FINAL REVIEW        (Review Agent)
  Phase 8: FIX final findings  (Implement Agent)

Gate Decision:
  composite ≥ threshold AND round ≥ min AND 0 blockers → PASS
  composite < threshold AND round < max               → NEXT ROUND
  round ≥ max                                          → ESCALATE

Each phase dispatched as a Wave with 1 Task.
Stage Agent orchestrates — never executes phases.
```

## 7. Failure Handling Chain
From §7:

### Failure Classification

| Level | Scope | Categories | Default Action |
|-------|-------|------------|----------------|
| **Task failure** | Single task | transient, deterministic, specification, resource | retry / fix_and_retry / escalate |
| **Wave failure** | One+ tasks | partial, conflict, total | retry_failed / rollback_and_reassign / escalate |
| **Stage failure** | Gate FAIL after max | quality, functional, design | add_round / loop_back_impl / loop_back_design |
| **Project failure** | Multiple stages | recoverable, scope_change, terminal | human_fix / re_decompose / divergence_report |

### Failure Handling Flowchart

```
Task Failure
  │
  ├─ transient? ──► Retry (max 1) ──► Pass? ──► OK
  │                                    │
  │                                   Fail
  │                                    ▼
  ├─ deterministic? ──► Auto-fix possible? ──Yes──► Fix + retry
  │                          │
  │                         No
  ▼                          ▼
Wave Failure ◄──────────────┘
  │
  ├─ partial? ──► Retry failed tasks only ──► All pass? ──► OK
  │                                              │
  │                                            Fail
  ├─ conflict? ──► Rollback wave ──► Reassign   │
  │                                              │
  ├─ total? ─────────────────────────────────────┘
  ▼
Stage Failure
  │
  ├─ quality? ──► round < max? ──Yes──► Another convergence round
  │                    │
  │                   No ──► Escalate to Project
  │
  ├─ functional? ──► Loop back to implementation
  │
  ├─ design? ──► Loop back to design
  ▼
Project Failure ──► Human decides:
  ├─ fix direction ──► Resume from specified stage
  ├─ re-scope ──► Re-decompose project
  └─ abort ──► Halt with divergence report
```

### Retry Limits

| Level | Max Retries | On Exhaustion |
|-------|-------------|---------------|
| Task | 1 (by Wave Agent) | Promote to wave failure |
| Wave | 1 (partial retry by Stage) | Promote to stage failure |
| Convergence rounds | 3 default (1–6 per profile) | Promote to project failure |
| Stage | 2 (by Project Agent) | Escalate to human |
| Project loop-back budget | 3 total across all stages | Halt with divergence report |
| Human escalations | 3 max | Suggest project re-scoping |

### Decomposition Validation Checklist

```
STAGE LEVEL:
  □ All stages from workflow template present
  □ Stage ordering matches template
  □ Every stage has a gate configured
  □ No stage depends on itself
  □ All cross-stage artifact dependencies have producers

WAVE LEVEL:
  □ No wave has > 5 tasks
  □ No stage has > 7 waves
  □ Tasks within wave have no file ownership overlaps
  □ Tasks within wave have no data dependencies
  □ Wave ordering is topologically correct

TASK LEVEL:
  □ Every task has type, title, description, acceptance criteria
  □ Every task owns ≤ 6 writable files
  □ Every task duration ≤ 30 min (impl) or ≤ 45 min (research)
  □ Every task description follows template
  □ No file owned by two tasks in same wave

DEPENDENCY GRAPH:
  □ No cycles detected
  □ Critical path identified
  □ All tasks reachable from root
```

## 8. Inline Self-Review Mode (v7.2.0+)

For low-risk waves where a separate verifier subagent would over-engineer the
quality check, L2 may select `inline_self_review` mode (declared in SKILL.md
"Wave Coordination Modes"). The executing agent runs through a pre-defined
checklist in-process at the end of its turn — approximate cost ~30 seconds vs
~25 minutes for the gen_verify subagent dispatch (50× wallclock saving).

**Source:** Imported from superpowers v5.0.6 release notes (verbatim):
"Replaced subagent review loops with inline self-review checklists in
brainstorming and writing-plans skills, reducing review time from ~25 minutes
to ~30 seconds while maintaining comparable defect detection."

### When inline_self_review is SAFE

Apply only to stages where defects are structural/organisational and the
executing agent is well-positioned to detect them via a checklist:

| Stage Type      | Safety Rationale |
|-----------------|-------------------|
| `research`      | Defect = missing source / wrong claim; checklist = "every claim has a source URL" |
| `design`        | Defect = missing interface / inconsistent terminology; checklist = "interface contracts complete, ADR sections present" |
| `documentation` | Defect = stale info / broken link / unclear example; checklist = "links validated, terms defined, examples runnable" |

### When to KEEP gen_verify_mode (UNSAFE for inline)

| Stage Type       | Why subagent verifier is required |
|------------------|-----------------------------------|
| `implement`      | Logic bugs require execution-style verification (run tests, lint) |
| `test`           | Gate validity depends on independent test reproduction |
| `refactor`       | Regression risk requires second-pair-of-eyes review |
| `security-audit` | Defect-cost is high; comparable detection NOT claimed |

### Activation

Opt-in per profile via `context_profiles.yaml`:
`inline_review_checklist: true` (default `false`). Mutually exclusive with
`decomposition.gen_verify_mode: true` — if both are set, gen_verify wins.
