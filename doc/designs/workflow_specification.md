# Unified Workflow Specification

> **Version**: 1.0.0
> **Date**: 2026-04-04
> **Status**: Specification Complete
> **Purpose**: Consolidated specification for the Agent Workflow Meta-Framework — integrating hierarchy, meta-framework, decomposition, repo modes, execution protocol, delivery architecture, code-rules, and design principles into a single authoritative reference.

---

## 1. System Overview & Design Principles

### 1.1 Mission

The Agent Workflow Meta-Framework orchestrates multi-stage software development workflows using a 4-layer agent hierarchy with quality gates, convergence loops, and context-isolated task delegation. It replaces ad-hoc agent prompting with declarative, template-driven workflow orchestration grounded in empirical patterns from 8 agent frameworks, 13 local execution plans, and industry best practices.

### 1.2 Governing Principles

| # | Principle | Source | Enforcement |
|---|-----------|--------|-------------|
| P1 | **Dispatcher-Not-Implementer** — orchestrating agents never perform work | EchoAccess 17-stage plan, Cursor subagent model | Hard constraint at L0–L2 |
| P2 | **Minimal Context Per Layer** — each agent receives only what it needs | Code-rules loading protocol (guide.md) | Context budget caps per layer |
| P3 | **Structured Message Passing** — typed YAML schemas, no free-form chat | MetaGPT pub-sub, OpenHands event-sourced patterns | Message schema validation |
| P4 | **Fail-Forward with Bounded Retry** — every loop has max iterations | Cross-framework convergence analysis | Loop ceilings + escalation chain |
| P5 | **Artifacts as Contracts** — layers communicate through files, not shared memory | EchoAccess file ownership, LangGraph typed state | Artifact schema enforcement |
| P6 | **Gate-Before-Advance** — no stage starts until predecessor gate passes | LangGraph conditional edges, convergence loops | Gate evaluation at every stage boundary |
| P7 | **Primitives Over Monoliths** — every workflow composes universal stage primitives | Cross-type analysis of 10 workflow types | 13 primitives + 5 composition operators |
| P8 | **Declarative Templates, Imperative Execution** — YAML defines structure, engine decides scheduling | Pipeline-as-code CI/CD patterns | Template schema + runtime engine |

### 1.3 Research Foundation

The system synthesizes findings from three research streams (ref: `research_synthesis_report.md`):

- **WP-1**: 8 agent frameworks (CrewAI, AutoGen, LangGraph, MetaGPT, ChatDev, OpenHands, Devin, Cursor Agent) — LangGraph and Cursor Agent scored highest (3.6 and 3.7/5.0 average)
- **WP-2**: 98 Work Packages across 13 local Cursor plans — yielded the dispatcher-not-implementer pattern, convergence loops, and wave scheduling
- **WP-3**: 10 workflow types cataloged with stage primitive mappings — all expressible as subsets of the Full Pipeline's 8-stage maximal chain

### 1.4 10 Key Findings Driving Design

1. Orchestration topology dominates model selection (12–23% improvement)
2. 11 stage primitives compose all 10 workflow types
3. Three loop-back archetypes cover all iteration (Quality/Correctness/Knowledge)
4. Dispatcher-not-implementer is the strongest local pattern
5. Graph-based state machines are the only production-proven durable architecture
6. Simple, composable patterns outperform complex frameworks
7. Context isolation is the critical multi-agent quality differentiator
8. Error handling is the primary production differentiator
9. Work Package is a proven atomic planning unit
10. MCP + A2A constitute the emerging interoperability standard

---

## 2. Agent Hierarchy

> Full detail: `design_agent_hierarchy.md`

### 2.1 4-Layer Architecture

```
┌──────────┬────────────┬──────────────┬──────────────┬─────────────────┐
│  Layer   │   Count    │   Lifespan   │  Does Work?  │  Context Size   │
├──────────┼────────────┼──────────────┼──────────────┼─────────────────┤
│ L0 Project │     1      │ Entire run   │     NO       │   ~3K tokens    │
│ L1 Stage   │   3–8      │ Per stage    │     NO       │   ~5K tokens    │
│ L2 Wave    │   1–7/stg  │ Per wave     │     NO       │   ~4K tokens    │
│ L3 Task    │  1–5/wave  │ Per task     │    YES       │   ~8K tokens    │
└──────────┴────────────┴──────────────┴──────────────┴─────────────────┘
```

- **L0 Project Agent**: Selects workflow type, dispatches stages sequentially, evaluates gates, reports to human. Never reads source code.
- **L1 Stage Agent**: Decomposes stage into waves, sequences wave execution, runs convergence loops, evaluates stage gate. Never writes code.
- **L2 Wave Agent**: Dispatches tasks in parallel, collects results, checks cross-task conflicts. Never performs task work.
- **L3 Task Agent**: The only layer that performs actual work — writes code, runs tests, authors designs, conducts reviews.

### 2.2 5 AgentTeam Roles

Task Agents at L3 are specialized by role. Each team has distinct input/output contracts (ref: `design_agent_hierarchy.md` §4):

| Team | Primary Responsibility | Key Tools |
|------|----------------------|-----------|
| **Research** | Gather, compare, synthesize information | WebSearch, WebFetch, SemanticSearch |
| **Design** | Architecture, API specs, data models, ADRs | Read, Write, SemanticSearch |
| **Implement** | Write production code + unit tests following code-rules | Read, Write, Shell, ReadLints |
| **Test** | Execute test suites, measure coverage, validate acceptance | Shell, Read, Write |
| **Review** | Evaluate artifacts against quality standards, produce findings | Read, Grep, SemanticSearch |

### 2.3 Inter-Layer Communication

Three message schemas govern all communication (ref: `design_agent_hierarchy.md` §3):

1. **TaskDispatch** (parent → child): task_id, type, description, owned_files, acceptance criteria, applicable code-rules, timeout
2. **StatusReport** (child → parent): state, artifacts, metrics, findings by severity, gate_decision
3. **ExceptionEscalation** (child → parent): error_type (recoverable/blocking/fatal), evidence, impact, suggested action

### 2.4 Team Handoff Protocol

Teams exchange work through typed `HandoffDeliverable` envelopes containing artifact paths, key decisions, constraints imposed, and self-assessed quality. Receiving teams run a 4-check acceptance validation (completeness, parsability, scope alignment, blocker-free) before starting work.

---

## 3. Workflow Meta-Framework

> Full detail: `design_meta_framework.md`

### 3.1 13 Stage Primitives

Every workflow is a composition of these universal primitives organized into 6 categories:

| Category | Primitives | Default Team |
|----------|-----------|-------------|
| **Discover** | `research`, `analyze` | Research |
| **Shape** | `design`, `plan` | Design |
| **Build** | `implement`, `refine` | Implement |
| **Verify** | `review`, `test`, `validate` | Review / Test |
| **Deliver** | `release`, `deploy`, `monitor` | Implement / Test |
| **Control** | `gate` | Orchestrator |

Each primitive has a typed input/output contract, preconditions, postconditions, and configurable parameters. Domain-specific stage names (e.g., "bug-triage" for `analyze` in hotfix) are aliases mapped to universal primitives.

### 3.2 5 Composition Operators

| Operator | Notation | YAML Key | Semantics |
|----------|----------|----------|-----------|
| Sequence | A → B → C | `compose: sequence` | Execute in order |
| Parallel | A ∥ B ∥ C | `compose: parallel` | Execute concurrently, join strategy |
| Choice | if P then A else B | `compose: choice` | Conditional branch on state predicate |
| Loop | repeat {A→B} until P max N | `compose: loop` | Bounded iteration with exhaustion policy |
| Gate | A ⊣[criteria] B | `compose: gate` | Quality checkpoint blocking progression |

### 3.3 Workflow Template Schema (v1.0)

Templates are versioned YAML files with sections for metadata, stage definitions, composition graph, named loops, named gates, team overrides, and environment modes. Key schema elements:

- `metadata`: name, version, category, applicable_scenarios, tags
- `stages[]`: id, primitive, alias, team, duration_class, config, input_mapping, skip_condition
- `composition`: nested CompositionNode tree
- `loops[]`: name, body_stages, until predicate, max_iterations, on_exhaustion policy
- `gates[]`: name, position, criteria (field/operator/value), on_pass, on_fail
- `environment_modes`: per-mode skip_stages and gate_overrides (local/github/gitlab)

### 3.4 Template Registry

```
.workflow/
├── registry.yaml              # master index
├── templates/
│   ├── builtin/               # 12 shipped templates (read-only)
│   ├── custom/                # user-defined
│   └── derived/               # inherited + overridden
├── primitives/schemas/        # JSON Schema per primitive I/O
└── state/                     # runtime state files
```

Discovery priority: custom > derived > builtin. Templates support inheritance via `extends` with selective `overrides`.

### 3.5 Auto-Recommendation Engine

A 3-stage pipeline (Intent Detection → Candidate Scoring → Confidence Ranking) recommends workflow types from user task descriptions. Keyword-to-workflow mapping tables with primary/secondary/negative weights produce normalized scores mapped to confidence levels: High (≥0.8, auto-select), Medium (0.5–0.79, present top 3), Low (0.2–0.49, require selection), None (<0.2, default to full-pipeline).

---

## 4. Task Decomposition & Gate Mechanism

> Full detail: `design_decomposition_gate.md`

### 4.1 Decomposition Hierarchy

**Stage** (coarsest) → **Wave** (parallelism group) → **Task** (atomic work unit)

| Level | Boundary Criterion | Naming Convention | Constraints |
|-------|-------------------|-------------------|-------------|
| Stage | Team transition, artifact gate, quality checkpoint, risk isolation | `S{nn}_{name}` | 3–8 per workflow |
| Wave | Parallel-independent task group | `W{nn}` (stage-scoped) | Max 7 per stage, max 5 tasks each |
| Task | Single-concern atomic work unit | `T{nn}` (wave-scoped) | Max 30 min (impl), 6 writable files, ~300 lines |

### 4.2 Wave Formation Algorithm

Waves are formed by topological sorting of task dependencies, then partitioning each layer into groups respecting: (1) max 5 tasks, (2) disjoint file ownership, (3) no intra-wave data dependencies. Four common wave patterns: scaffold-then-parallel, research-fanout, sequential-pipeline, convergence-round.

### 4.3 Gate Mechanism

Every stage has exactly one gate. Three gate types:

| Type | Rounds | Use When |
|------|--------|----------|
| **Standard** | 1 | Research, design, plan, release stages |
| **Convergence** | 1–6 (default 3) | Implementation stages requiring iterative quality |
| **Passthrough** | 0 | Intermediate aggregation stages |

**Composite Score Formula**: `Σ(dimension_score × weight)` where test_quality=0.30, code_review=0.30, architecture=0.20, benchmark=0.20. Individual scores: `max(0, 100 - Σ(severity_weight × count))` with blocker=25, critical=15, major=5, minor=1.

**Pass conditions**: composite ≥ threshold (default 85) AND zero blockers AND coverage ≥ threshold AND round ≥ min_rounds.

**Gate profiles**: strict (≥90, coverage≥85%), standard (≥85, coverage≥80%), relaxed (≥70, coverage≥60%), audit (≥95, coverage≥90%).

### 4.4 Dependency Matrix

Auto-generated from decomposition, capturing stage adjacency, task-level edges (data/artifact/file/interface), file ownership map, interface contracts, and critical path. Cycle detection uses 3-color DFS; critical path uses longest-path through the DAG.

---

## 5. Repository Modes

> Full detail: `design_repo_modes.md`

### 5.1 Three Modes

| Mode | Remote | CI/CD | Review Flow | Release |
|------|--------|-------|-------------|---------|
| **Local** | None | None (Makefile) | Self-review | None |
| **GitHub** | github.com | GitHub Actions | PR-based | Tag → Actions → Release |
| **Other-Git** | GitLab/Gitea/Bitbucket | Platform-native | MR/PR-based | Tag → Pipeline → Registry |

### 5.2 Auto-Detection

Mode is detected from `git remote -v` URL matching (`github.com` → GitHub, `gitlab.*` → GitLab, etc.) with fallback to CI config file detection (`.gitlab-ci.yml`, `.github/workflows/`). User override via `.workflow/config.yaml`.

### 5.3 Feature Matrix (20 features × 3 modes)

Features range from always-available (local build, test, doc gen) through mode-implied (CI/CD, review flow, release workflow) to optional activation (cross-platform builds, registry publish, Pages deployment, online demo). Mode transitions are detected automatically when remotes change.

### 5.4 Mode-Aware Stage Behavior

Stages adapt per mode: Review stage creates PRs in GitHub mode vs. self-review in Local; Gate stage checks CI status in GitHub mode vs. local gate script; Release stage is skipped entirely in Local mode.

---

## 6. Execution Protocol

> Full detail: `design_execution_protocol.md`

### 6.1 Pre-Decision Phase

A 6-step initialization runs before any stage dispatches:

1. **DETECT** — auto-detect repo mode, language, platform, build system
2. **COLLECT** — present checklist with 3 field categories: MANDATORY (no default), DEFAULTED (sensible default), CONFIRM (auto-detected)
3. **VALIDATE** — check consistency (e.g., Rust + npm = error)
4. **FREEZE** — write `project_config.yaml`, lock decisions
5. **RECOMMEND** — auto-recommend workflow type, present for confirmation
6. **DISPATCH** — hand frozen config to Project Agent

The checklist covers 8 sections: project identity, tech stack, repository mode, localization, target platforms, quality standards, release strategy, and workflow selection.

### 6.2 Checkpoint/Resume

Checkpoints are created at stage gate boundaries, wave completion, convergence rounds, error recovery, and human intervention pauses. Schema captures full project state: completed stages with artifact hashes, current wave/task progress, convergence round state, quality snapshot, deferred items, and active escalations.

Resume logic: never re-execute completed stages, only re-dispatch incomplete tasks in interrupted waves, verify artifact integrity via hash comparison, require user approval for config drift.

### 6.3 Exception Severity Classification

| Level | Auto-Action | Human? |
|-------|------------|--------|
| **AUTO_RECOVER** | Retry ≤3 with exponential backoff | No |
| **PAUSE** | Pause affected task, continue parallel work, batch questions | Batched |
| **HUMAN_INTERVENE** | Stop affected stage, present options | Yes, immediately |
| **FULL_ROLLBACK** | Rollback to last checkpoint, produce failure report | Yes |

### 6.4 Human Intervention Breakpoints

7 hard breakpoints (workflow must stop): pre-decision confirmation, architecture design approval, security-sensitive changes, external service config, release publication, divergence reports, rollback acknowledgment. 6 soft breakpoints (workflow can continue with defaults): style preferences, tool selection, optional features, doc detail level, edge case tests, dependency versions.

### 6.5 Progress Reporting

Live dashboard in `.local/stages/overview.md` with stage progress table, summary metrics, active blockers, and deferred scope. Execution log in `.local/execution_log.jsonl` records ~250 events per full-pipeline run across lifecycle, quality, exception, checkpoint, and handoff categories.

---

## 7. Delivery Architecture

> Full detail: `design_delivery_architecture.md`

### 7.1 Cross-Tool Compatibility

The workflow knowledge must be delivered to 4 AI tools with different formats:

| Tool | Entry File | Trigger | Budget |
|------|-----------|---------|--------|
| Cursor | `SKILL.md` (YAML frontmatter) | Intent-matched | <500 lines |
| Codex | `SKILL.md` (3-tier loading) | Intent-matched | <500 lines |
| Claude Code | `CLAUDE.md` (plain markdown) | Always-on | <200 lines |
| GitHub Copilot | `copilot-instructions.md` | Always-on | <1000 lines |

### 7.2 Single Source Architecture

A canonical `workflow-skill.yaml` defines all content (identity, activation policy, rules, body sections, references, examples, schemas, templates, scripts) in a tool-agnostic format. Per-tool adapters (`build-skill.py`) transform this source into each tool's native format, respecting line budgets and structural constraints.

### 7.3 3-Tier Knowledge Hierarchy

- **Tier 1 (Entry)**: ~400-line SKILL.md with workflow overview, quick-start decision tree, hierarchy summary, stage index, gate summary, team index, reference navigation guide
- **Tier 2 (Domain References)**: 200–500 lines each for agent-hierarchy, gate-mechanism, repo-modes, stage-templates, message-schemas, team-roles, context-isolation
- **Tier 3 (On-Demand)**: examples (full-pipeline trace, hotfix trace), schemas (dispatch/report/handoff YAML), templates (project-status, stage-readme), scripts (detect-repo-mode, validate-gate)

Loading strategy per layer: Project Agent loads Tier 1 only (~2.5K tokens), Stage Agent adds selective Tier 2 (~4K), Wave Agent uses Tier 1 index only (~1.5K), Task Agent uses Tier 2 + Tier 3 (~6K).

---

## 8. Code-Rules Integration

> Sources: `guide.md` (loading protocol), `architecture.md` (4-layer rule structure)

### 8.1 Code-Rules System Overview

The code-rules system provides 250–350 machine-parseable rules across a 4-layer architecture: Core Principles → Quality Dimensions → Language Rules → Task Overlays. Each rule has structured metadata (id, priority MUST/SHOULD/MAY, severity, applies_when condition, linter mapping, ISO 25010 mapping).

### 8.2 Workflow Stage × Code-Rules Mapping

| Workflow Stage | Loading Strategy | Code-Rules Files Loaded | Rationale |
|---------------|-----------------|------------------------|-----------|
| **Pre-Decision** | Minimal | `index.md` only | Determine language, detect loading strategy |
| **Research** | None | — | No code generation; information gathering only |
| **Design** | Standard | `core/principles.md` + `quality/maintainability.md` + `quality/extensibility.md` | Architecture decisions reference maintainability/extensibility rules |
| **Plan** | Minimal | `core/principles.md` | Plan decomposition references naming and scope rules |
| **Implement** | Full | `core/principles.md` + `languages/{lang}.md` + `tasks/new_feature.md` + `quality/security.md` + `quality/maintainability.md` | Full rule set for code generation |
| **Implement (bug_fix)** | Full | `core/principles.md` + `languages/{lang}.md` + `tasks/bug_fix.md` + `quality/security.md` | Bug fix overlay with security focus |
| **Implement (refactoring)** | Full | `core/principles.md` + `languages/{lang}.md` + `tasks/refactoring.md` + `quality/maintainability.md` + `quality/readability.md` | Refactoring overlay with maintainability focus |
| **Review** | Full | All applicable files (full rule set) | Review agents check against complete rule set |
| **Test** | Standard | `core/principles.md` + `languages/{lang}.md` + `quality/testability.md` + `tasks/test_writing.md` | Test writing overlay with testability focus |
| **Refine** | Full | Same as original Implement stage | Fixes applied under same rule constraints |
| **Release** | Minimal | `core/principles.md` | Release mechanics, not code generation |

### 8.3 Code-Rules in Context Injection

The `TaskDispatch.context.applicable_rules` field specifies which code-rules to load:

```yaml
applicable_rules:
  loading_strategy: "standard | full"   # from guide.md §7
  language: "rust"                       # maps to languages/rust.md
  task_type: "new_feature"               # maps to tasks/new_feature.md
  quality_focus: ["security", "maintainability"]  # maps to quality/*.md
```

Task Agents load rules per the guide.md 5-step protocol: index → core → language → task → quality. The override chain (task > language > quality > core) resolves conflicts.

---

## 9. Design Principles Mapping

### 9.1 Principle × Team Responsibility Matrix

| Principle / Practice | Design Team | Implement Team | Review Team | Test Team |
|---------------------|-------------|----------------|-------------|-----------|
| **SRP** (Single Responsibility) | Enforce in component design; each module has one reason to change | Follow SRP in implementation; flag violations during self-review | Check SRP compliance in structural review dimension | Verify modules are independently testable |
| **OCP** (Open/Closed) | Design extension points (traits, interfaces, plugin hooks) | Implement using abstractions; avoid modifying closed modules | Check for modification-instead-of-extension patterns | Test that extensions work without modifying core |
| **LSP** (Liskov Substitution) | Define interface contracts with pre/post conditions | Implement subtypes honoring parent contracts | Verify subtype behavioral compatibility | Property-based tests for substitutability |
| **ISP** (Interface Segregation) | Split fat interfaces into role-specific traits | Implement only consumed interface methods | Flag unused interface dependencies | Test each interface independently |
| **DIP** (Dependency Inversion) | Define abstractions owned by high-level modules | Depend on abstractions, inject implementations | Check dependency direction (high → low via abstractions) | Mock abstractions for unit isolation |
| **TDD** (Red-Green-Refactor) | Define testable acceptance criteria | Execute TDD cycle: write failing test → implement → refactor | Verify test-first evidence (test files created before/with impl) | Validate test quality: AAA pattern, FIRST principles |
| **DDD** (Domain-Driven Design) | Model bounded contexts, aggregates, value objects | Implement ubiquitous language in code naming | Check domain model alignment, verify bounded context boundaries | Integration tests at context boundaries |
| **Clean Architecture** | Layer separation: entities → use cases → adapters → frameworks | Respect dependency rule (inward only) | Verify no framework imports in domain layer | Test each layer independently |
| **SOLID Composite Score** | Produces architecture with SOLID compliance as design goal | Self-review against SOLID before submission | Calculates `solid_review.quality_score` (per-principle scores) | N/A (verified by Review Team) |

### 9.2 Quality Dimension → Code-Rules File Mapping

| Quality Dimension | Code-Rules File | Gate Check Weight | Rule Count |
|------------------|----------------|-------------------|------------|
| Security | `quality/security.md` (SEC.*) | Included in code_review | 25–30 |
| Performance | `quality/performance.md` (PERF.*) | benchmark dimension (0.20) | 15–20 |
| Maintainability | `quality/maintainability.md` (MAINT.*) | architecture dimension (0.20) | 20–25 |
| Readability | `quality/readability.md` (READ.*) | Included in code_review | 15–20 |
| Testability | `quality/testability.md` (TEST.*) | test_quality dimension (0.30) | 10–15 |
| Extensibility | `quality/extensibility.md` (EXT.*) | Included in architecture | 10–15 |
| Portability | `quality/portability.md` (PORT.*) | Included in code_review | 10–15 |

---

## 10. Workflow Metadata Schema

### 10.1 `workflow.yaml` — Complete Instance Schema

```yaml
# workflow.yaml — Describes a complete workflow instance
schema_version: "1.0"

instance:
  id: "string (UUID)"
  name: "string"
  created_at: "ISO8601"
  updated_at: "ISO8601"
  status: "initializing | running | paused | completed | failed | aborted"
  current_stage_id: "string | null"
  run_id: "string"

template:
  name: "string"                    # e.g., "full-pipeline"
  version: "string"                 # semver of template used
  source: "builtin | custom | derived"
  path: "string"                    # path to template YAML file

pre_decision:
  config_path: "string"            # path to frozen project_config.yaml
  config_hash: "string"            # SHA256 for drift detection
  project_name: "string"
  primary_language: "string"
  repo_mode: "local | github | other-git"
  workflow_type: "string"
  gate_profile: "strict | standard | relaxed | audit"
  quality_thresholds:
    coverage_pct: "number"
    composite_score: "number"
    max_blockers: "integer"

stage_progress:
  - stage_id: "string"
    name: "string"
    type: "string"                  # primitive type
    status: "pending | active | completed | failed | skipped"
    gate_type: "standard | convergence | passthrough"
    gate_verdict: "PASS | FAIL | ESCALATE | null"
    composite_score: "number | null"
    convergence_rounds:
      current: "integer"
      max: "integer"
    waves:
      total: "integer"
      completed: "integer"
    tasks:
      total: "integer"
      completed: "integer"
      failed: "integer"
    started_at: "ISO8601 | null"
    completed_at: "ISO8601 | null"
    gate_report_path: "string | null"
    artifact_paths: ["string"]

checkpoints:
  latest: "string"                  # path to latest checkpoint
  count: "integer"
  entries:
    - checkpoint_id: "string"
      trigger: "stage_gate_pass | wave_complete | convergence_round | error_recovery | manual"
      timestamp: "ISO8601"
      path: "string"

escalations:
  active: "integer"
  resolved: "integer"
  entries:
    - escalation_id: "string"
      severity: "auto_recover | pause | human_intervene | full_rollback"
      status: "active | resolved"
      description: "string"
      created_at: "ISO8601"
      resolved_at: "ISO8601 | null"

metrics:
  total_progress_pct: "number"
  elapsed_seconds: "integer"
  estimated_remaining_seconds: "integer | null"
  total_tasks_spawned: "integer"
  max_parallel_tasks: "integer"
  exceptions_by_severity:
    auto_recover: "integer"
    pause: "integer"
    human_intervene: "integer"
    full_rollback: "integer"

deferred_items: ["string"]
```

---

## 11. End-to-End Example

### Scenario: "Build me a CLI tool in Rust"

A complete walkthrough showing every decision point and artifact produced.

#### Phase 0: Pre-Decision (Layer -1)

**Auto-detection results**: No `.git` detected → repo mode: Local. No source files → greenfield project. Language: undetectable (MANDATORY prompt).

**Checklist presented**:
```
⬚ Project name: ___________          (MANDATORY)
⬚ Primary purpose: ___________       (MANDATORY)
☑ Repo mode: local (no git remote)   (CONFIRM)
○ Language: rust                      (user specified in request)
○ Coverage target: 80%               (DEFAULTED)
○ Gate profile: standard             (DEFAULTED)
```

**User confirms**: name=`file-sync`, purpose="CLI tool for syncing local directories", language=rust. All defaults accepted.

**Workflow recommendation**: keywords ["build", "CLI", "tool"] match `full-pipeline` (score 0.88, confidence: High). User confirms.

**Frozen config** written to `.local/project_config.yaml`.

#### Phase 1: Design Stage (S01)

**Project Agent dispatches** `StageDispatch` to Stage Agent with workflow type `full-pipeline`, stage type `design`.

**Stage Agent decomposes** into 2 waves:
- W01: T01-Research (Research Team) — survey Rust CLI patterns, clap vs. argh
- W02: T02-DesignDoc (Design Team) — author architecture document

**Code-rules loaded**: Standard strategy — `core/principles.md` + `quality/maintainability.md`

**Artifacts produced**: `design_document.md` (5 modules: config, sync-engine, storage, error, CLI)

**Gate**: Standard gate, PASS (design spec exists, ADRs recorded). Checkpoint created.

**HBP-02 triggered**: Architecture Design Approval — user reviews and approves.

#### Phase 2: Plan Stage (S02)

**Stage Agent dispatches** 1 wave, 1 task: Create implementation plan.

**Artifacts produced**: `implementation_plan.md` — 3 waves, 9 tasks, dependency matrix.

**Gate**: Standard gate, PASS. Checkpoint created.

#### Phase 3: Implement Stage (S03)

**Stage Agent reads plan**, creates 3 waves:

**Wave 1** (scaffold): 1 task
- T01: Create Cargo.toml, src/main.rs, src/lib.rs, src/error.rs
- Code-rules: Full — `core/principles.md` + `languages/rust.md` + `tasks/new_feature.md` + `quality/security.md` + `quality/maintainability.md`
- Result: PASS. Wave checkpoint.

**Wave 2** (parallel core): 4 tasks in parallel
- T02: ConfigManager (src/config/*) — depends on T01
- T03: SyncEngine (src/sync/*) — depends on T01
- T04: StorageBackend (src/storage/*) — depends on T01
- T05: ErrorTypes (src/error.rs modify) — depends on T01
- File ownership: strictly disjoint. No task shares writable files.
- Result: T02 ✅, T03 ✅, T04 ✅, T05 ✅. Wave checkpoint.

**Wave 3** (integration): 2 tasks
- T06: Wire CLI interface (src/main.rs, src/lib.rs)
- T07: Integration tests (tests/*)
- Result: PASS. Wave checkpoint.

**Convergence Loop begins** (max 3 rounds):

*Round 1:*
- Phase 1: Code Review (Review Agent) — loads full code-rules, score: 82
- Phase 2: Fix findings (Implement Agent) — addresses 2 critical, 3 major
- Phase 3: Test (Test Agent) — loads `quality/testability.md`, coverage: 76%
- Phase 4: Fix test failures (Implement Agent)
- Phase 7: SOLID Review (Review Agent) — SRP=90, OCP=85, LSP=88, ISP=92, DIP=80, score: 87
- Phase 8: Fix SOLID findings
- **Gate evaluation**: composite = 82×0.30 + 82×0.30 + 87×0.20 + 100×0.20 = 86.6 ≥ 85. Coverage 76% < 80%. **FAIL** (coverage).

*Round 2:*
- Implement Agent writes additional tests (coverage → 83%)
- Code review score: 89, SOLID score: 88
- **Gate evaluation**: composite = 89×0.30 + 89×0.30 + 88×0.20 + 100×0.20 = 91.0 ≥ 85. Coverage 83% ≥ 80%. Zero blockers. **PASS**.

Stage gate checkpoint created. **StageReport(PASS)** to Project Agent.

#### Phase 4: Review Stage (S04)

3 parallel review tasks: code quality, security, architecture. Aggregate score: 88. Gate PASS.

#### Phase 5: Test Stage (S05)

Test Agent runs `cargo test --release`, coverage 83%, all pass. Gate PASS.

#### Phase 6: TestGate (S06)

Passthrough gate — validates all upstream gates passed. PASS.

#### Phase 7: Release Stage (S07)

Repo mode is Local → release stage **skipped** (per environment_modes.local.skip_stages).

**Final project report** presented to user:
- 6 stages completed (1 skipped), 18 tasks spawned, max 4 parallel
- Composite score: 91, coverage: 83%, zero blockers
- 2 convergence rounds in Implement stage
- 1 AUTO_RECOVER exception (build timeout, resolved on retry)
- 3 deferred items: GUI frontend, Windows ARM, plugin system

#### Artifacts Summary

| Artifact | Stage | Path |
|----------|-------|------|
| Design document | S01 | `.local/stages/S01_design/artifacts/design_document.md` |
| Implementation plan | S02 | `.local/stages/S02_plan/artifacts/implementation_plan.md` |
| Source code (6 modules) | S03 | `src/**/*.rs` |
| Unit tests | S03 | `tests/**/*.rs` |
| Review report | S04 | `.local/stages/S04_review/gate_report.yaml` |
| Test results | S05 | `.local/stages/S05_test/gate_report.yaml` |
| Final dashboard | — | `.local/stages/overview.md` |

---

## 12. Reusable Templates Gallery

The system ships with 12 built-in workflow templates (ref: `design_meta_framework.md` §5):

| # | Template | Category | Stages | Key Loop | Use When |
|---|----------|----------|--------|----------|----------|
| 1 | `research-only` | Discover | research → analyze → validate | Knowledge loop (max 3) | Technology evaluation, literature survey |
| 2 | `design-only` | Shape | research → design → review | Design-review loop (max 3) | API design, schema design |
| 3 | `research-design-review-refine` | Composite | research → design → review → refine | Design-refine loop with gap research | ADR workflows, architecture decisions |
| 4 | `hotfix` | Build | bug-triage → fix → test → release | Fix-test loop (max 3) | Production bugs, CVE patches |
| 5 | `refactoring` | Build | scope → plan → implement → test → review | Impl-test loop (max 3) | Tech debt, code cleanup |
| 6 | `migration` | Build | assess → plan → implement → validate → cutover | Impl-validate loop | Database/platform migrations |
| 7 | `spike-poc` | Discover | hypothesis → prototype → evaluate → decide | None (single pass) | Feasibility assessment |
| 8 | `documentation-only` | Deliver | survey → author → review | Author-review loop | README, API docs, guides |
| 9 | `security-audit` | Verify | threat-model → scan → analyze → remediate → verify | Remediate-verify loop | Vulnerability assessment |
| 10 | `performance-optimization` | Build | profile → plan → optimize → benchmark | Optimize-benchmark loop | Latency/throughput improvements |
| 11 | `feature-enhancement` | Composite | scope → implement → review → test → release | Review-test-refine loop | Extending existing features |
| 12 | `full-pipeline` | Composite | design → plan → impl → review → test → testgate → release | Nested review-refine + test-fix loops | Greenfield features, new projects |

Users create custom templates in `templates/custom/` or derive from builtins via `extends` + `overrides`.

---

## Appendix A: Glossary of Terms

| Term | Definition |
|------|-----------|
| **AgentTeam** | Role classification (Research/Design/Implement/Test/Review) determining Task Agent specialization |
| **Checkpoint** | Persistent snapshot of workflow state enabling crash-recovery and resume |
| **Code-Rules** | 4-layer rule system (core → quality → language → task) governing code generation quality |
| **Composite Score** | Weighted quality metric: `test×0.30 + review×0.30 + architecture×0.20 + benchmark×0.20` |
| **Convergence Loop** | Multi-round quality improvement cycle (review→fix→test→fix) with bounded iterations |
| **Dispatcher** | Any L0–L2 agent that delegates work but never performs it directly |
| **Gate** | Quality checkpoint that blocks stage progression unless criteria are met |
| **Gate Profile** | Configurable strictness level (strict/standard/relaxed/audit) with preset thresholds |
| **HandoffDeliverable** | Typed envelope for inter-team artifact transfer with acceptance validation |
| **Layer** | Hierarchy level: L0=Project, L1=Stage, L2=Wave, L3=Task |
| **Primitive** | One of 13 universal stage building blocks (research, analyze, design, plan, etc.) |
| **Repo Mode** | Repository hosting context (Local/GitHub/Other-Git) determining available features |
| **Stage** | Coarsest decomposition unit — a distinct functional phase in the workflow |
| **Task** | Atomic work unit executed by a single L3 agent in a single session |
| **TaskDispatch** | Typed message from parent to child specifying work, context, and acceptance criteria |
| **Template** | Declarative YAML file defining a workflow type's stage composition and gate configuration |
| **Wave** | Group of independent tasks within a stage that execute in parallel |
| **Work Package (WP)** | Historical term from local plan analysis; maps to Task in the meta-framework |
| **Workflow Type** | Named category of workflow (e.g., hotfix, full-pipeline) with a predefined template |

---

## Appendix B: Cross-Reference Index

| Topic | Primary Document | Specification Section |
|-------|-----------------|----------------------|
| Agent hierarchy layers | `design_agent_hierarchy.md` | §2 |
| AgentTeam role contracts | `design_agent_hierarchy.md` §4 | §2.2 |
| Auto-recommendation engine | `design_meta_framework.md` §6 | §3.5 |
| Checkpoint/resume | `design_execution_protocol.md` §4 | §6.2 |
| Code-rules architecture | `architecture.md` | §8.1 |
| Code-rules loading protocol | `guide.md` | §8.2, §8.3 |
| Composition operators | `design_meta_framework.md` §3 | §3.2 |
| Convergence loop | `design_agent_hierarchy.md` Appendix C | §4.3 |
| Delivery/skill architecture | `design_delivery_architecture.md` | §7 |
| Dependency matrix | `design_decomposition_gate.md` §6 | §4.4 |
| Exception classification | `design_execution_protocol.md` §5 | §6.3 |
| Failure handling chain | `design_decomposition_gate.md` §7 | §6.3 |
| Gate mechanism | `design_decomposition_gate.md` §5 | §4.3 |
| Human breakpoints | `design_execution_protocol.md` §6 | §6.4 |
| Inter-layer messages | `design_agent_hierarchy.md` §3 | §2.3 |
| Pre-decision checklist | `design_execution_protocol.md` §2 | §6.1 |
| Repo mode detection | `design_repo_modes.md` §3 | §5.2 |
| Research synthesis | `research_synthesis_report.md` | §1.3 |
| Stage primitives | `design_meta_framework.md` §2 | §3.1 |
| Template schema | `design_meta_framework.md` §4 | §3.3 |
| Template registry | `design_meta_framework.md` §5 | §3.4 |
| Wave decomposition | `design_decomposition_gate.md` §3 | §4.2 |
| Workflow metadata schema | (new in this document) | §10 |

---

*Specification compiled: 2026-04-04 | Integrates 7 design documents + 2 code-rules references | Authoritative reference for implementation planning*
