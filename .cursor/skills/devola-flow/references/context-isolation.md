---
id: "agent/references/context-isolation"
version: "1.0.0"
purpose: >
  Defines the context isolation strategy including the 3 failure modes it
  prevents, how subagents get isolated context windows, the full context
  injection template (YAML), what must NOT leak between agents (6 categories),
  what IS shared, and context budget management by layer with max files/tokens.
triggers:
  - "setting up context injection"
  - "debugging context leaks"
  - "configuring agent budgets"
tier: 2
token_estimate: 3400
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-04"
---

# Context Isolation Reference

## 1. Isolation Principles
From §6.1:

Context isolation prevents three failure modes:

| # | Failure Mode | Description | Consequence If Not Prevented |
|---|-------------|-------------|------------------------------|
| 1 | **Context pollution** | Task Agent's working memory fills with irrelevant information from other tasks | Degraded output quality; agent reasoning contaminated |
| 2 | **Cross-task interference** | Parallel tasks inadvertently share or conflict on information | Inconsistent results; hidden dependencies |
| 3 | **Budget exhaustion** | Accumulated context from multiple phases exceeds effective context window | Degraded reasoning; important details lost from attention |

These failure modes are observed across agent frameworks (MetaGPT pub-sub
pollution, OpenHands context overflow). The isolation strategy prevents
all three through enforcement at spawn time.

## 2. Isolation Mechanisms
From §6.2:

### Mechanism 1 — Fresh Context Per Spawn

Every Task Agent (Layer 3) starts with an empty context window. It receives
ONLY the TaskDispatch message and the files listed in `owned_files`. No
conversation history from prior tasks leaks in.

### Mechanism 2 — File Ownership Boundaries

Each Task Agent is authorized to read/modify ONLY files listed in its
`TaskDispatch.context.owned_files`. File ownership is partitioned at the
Wave level — no two tasks in the same wave share a writable file.

### Mechanism 3 — Artifact-Mediated Communication

Tasks never directly communicate. When Task B depends on Task A's output:

```
Task A writes to file
  → Wave Agent collects result
    → Task B receives a SUMMARY REFERENCE in context injection
      (NOT the full content)
```

## 3. Context Injection Template
From §6.3:

Every Task Agent receives this structured context at spawn time. This is
the ONLY information the Task Agent has access to (beyond its own tool outputs).

```yaml
context_injection:

  # Section 1: Identity and role (~100 tokens)
  identity:
    role: "string"                     # research | design | implement | test | review
    task_id: "string"                  # e.g., S03_W02_T01
    team: "string"                     # AgentTeam role template to follow

  # Section 2: Task specification (500-1500 tokens)
  task:
    title: "string"                    # short descriptive title
    description: "string"             # detailed what-to-do
    acceptance_criteria: ["string"]    # testable done-when conditions
    constraints: ["string"]           # non-negotiable boundaries

  # Section 3: Scoped context (1000-3000 tokens)
  context:
    predecessor_summary: "string"      # 3-5 sentence summary (NOT full artifacts)
    design_reference_excerpt: "string | null"  # relevant section ONLY (NOT full doc)
    relevant_interfaces: ["string"]    # interface signatures to respect

  # Section 4: File scope (200-500 tokens)
  files:
    owned:                             # files agent can create/modify
      - path: "string"
        purpose: "string"             # why this file is relevant
    read_only:                         # files agent can read but NOT modify
      - path: "string"
        purpose: "string"

  # Section 5: Rules (loaded per guide.md protocol) (2000-5000 tokens)
  rules:
    loading_strategy: "minimal | standard | full"
    language: "string | null"
    task_type: "string | null"
    quality_focus: ["string"]

  # Section 6: Behavioral constraints (~200 tokens)
  behavioral:
    timeout_seconds: "integer"
    max_files_to_read: "integer"       # prevent context blow-up
    output_format: "string"            # expected output structure
    escalation_contact: "wave_agent"   # who to escalate to
```

### Section Token Budgets

| Section | Tokens | Content |
|---------|--------|---------|
| Identity | ~100 | role, task_id, team |
| Task spec | 500–1500 | title, description, acceptance_criteria, constraints |
| Scoped context | 1000–3000 | predecessor_summary, design_excerpt, interfaces |
| File scope | 200–500 | owned files (create/modify), read_only files |
| Rules | 2000–5000 | Loaded per code-rules protocol |
| Behavioral | ~200 | timeout, max_files, output_format, escalation |
| **Total** | **~3800–10300** | Leaves 150K–490K for reasoning + tool outputs |

### Example Context Injection

```yaml
context_injection:
  identity:
    role: "implement"
    task_id: "S04_W02_T01"
    team: "Implement"

  task:
    title: "Implement ConfigManager module"
    description: >
      Implement the ConfigManager module that reads, validates, and merges
      configuration from TOML files, environment variables, and CLI
      arguments, following the design in design_document.md §3.2.
    acceptance_criteria:
      - "cargo build succeeds with zero warnings"
      - "cargo test config:: passes with >= 80% line coverage"
      - "ConfigManager satisfies all 4 interface methods from design §3.2"
    constraints:
      - "Must use the ConfigSource trait from config_types.rs"
      - "No unwrap() calls; all errors must use the project error type"
      - "Environment variables take precedence over TOML values"

  context:
    predecessor_summary: >
      S04_W01 created the project scaffold: Cargo.toml, src/main.rs,
      src/lib.rs, src/error.rs with the AppError type. The config_types
      module defines ConfigSource trait and Config struct.
    design_reference_excerpt: >
      §3.2 ConfigManager: 4 methods — new(sources: Vec<Box<dyn ConfigSource>>),
      load() -> Result<Config>, get(key) -> Option<Value>,
      validate() -> Result<()>. Merge order: defaults < TOML < env < CLI.
    relevant_interfaces:
      - "trait ConfigSource { fn load(&self) -> Result<Config, AppError>; }"
      - "struct Config { settings: HashMap<String, Value> }"

  files:
    owned:
      - path: "src/config/manager.rs"
        purpose: "ConfigManager implementation"
      - path: "src/config/mod.rs"
        purpose: "Module declaration"
      - path: "tests/config/manager_test.rs"
        purpose: "Unit tests"
    read_only:
      - path: "src/config/types.rs"
        purpose: "ConfigSource trait definition"
      - path: "src/error.rs"
        purpose: "AppError type"

  rules:
    loading_strategy: "standard"
    language: "rust"
    task_type: "new_feature"
    quality_focus: ["maintainability", "error_handling"]

  behavioral:
    timeout_seconds: 1800
    max_files_to_read: 10
    output_format: "TaskReport"
    escalation_contact: "wave_agent"
```

## 4. What MUST NOT Leak Between SubAgents
From §6.4:

| # | Category | What Must Not Leak | Why |
|---|----------|-------------------|-----|
| 1 | **Conversation history** | Prior task's internal reasoning, tool calls, intermediate outputs | Pollutes new task's reasoning with irrelevant context |
| 2 | **File contents from other tasks** | Source code files owned by other parallel tasks | Prevents false dependencies and conflicting assumptions |
| 3 | **Full predecessor artifacts** | Complete research reports, design documents, review reports | Context budget exhaustion; summaries are sufficient |
| 4 | **Error details from siblings** | Stack traces, failure logs from sibling tasks | Irrelevant to current task; may confuse the agent |
| 5 | **Quality scores from other tasks** | Review scores, coverage metrics from unrelated modules | Could create false pressure to match or exceed |
| 6 | **Deferred items from other stages** | Items explicitly pushed to later stages | Not actionable for the current task |

## 5. What IS Shared (Via Artifact Summaries)
From §6.4:

| Category | How Shared | Example |
|----------|-----------|---------|
| Interface contracts | Function signatures, type definitions from predecessor stages | `trait ConfigSource { fn load(&self) -> Result<Config>; }` |
| Design decisions | ADR summaries that constrain the current task | "Decision: use TOML over YAML for config (rationale: ...)" |
| Naming conventions | Project-wide patterns from code-rules | `snake_case` for Rust, module naming patterns |
| Quality thresholds | Acceptance criteria from project configuration | "coverage >= 80%, zero blockers" |
| Acceptance criteria | From the task's own TaskDispatch | Binary testable conditions |

**Key rule:** Share summaries and contracts, never full content.
Predecessor artifacts are summarized to 3-5 sentences max.

## 6. Context Budget Management by Layer
From §6.5:

| Layer | Strategy | Budget | What's Loaded | Max Files | Max Tokens |
|-------|----------|--------|---------------|-----------|------------|
| L0 Project | Minimal | ~3K | Workflow template, project config, stage status dashboard | 3 | 3000 |
| L1 Stage | Standard | ~5K | Stage definition, predecessor artifact summaries, wave plan | 5 | 5000 |
| L2 Wave | Minimal | ~4K | Wave task list, task status tracking | 3 | 4000 |
| L3 Task | Standard–Full | ~8K | Task spec, owned files, code-rules, design excerpt | 15 (read) + 6 (write) | 8000 |

### Loading Strategy Reference

| Strategy | Description | Used By |
|----------|-------------|---------|
| **Minimal** | Only essential context; no file contents, no deep references | L0 Project, L2 Wave |
| **Standard** | Essential context + key excerpts from predecessor artifacts | L1 Stage, L3 Task (typical) |
| **Full** | Standard + complete code-rules + detailed design references | L3 Task (complex tasks) |

### Budget Enforcement Rules

1. **Hard caps:** No layer may exceed its token budget for context injection
2. **Summarization:** Artifacts exceeding budget are auto-summarized before injection
3. **Prioritization:** Identity > Task spec > Rules > Context > Files (in priority order)
4. **Overflow handling:** If budget exceeded after prioritization, truncate lowest-priority
   sections and add `[TRUNCATED — load full content via Read tool if needed]` marker

### File Limits by Layer

| Layer | Max Writable Files | Max Readable Files | File Content in Context? |
|-------|-------------------|-------------------|-------------------------|
| L0 Project | 2 (dashboard, config) | 3 | NO (paths only) |
| L1 Stage | 2 (README, report) | 5 | Summaries only |
| L2 Wave | 0 (in-memory only) | 3 | NO (paths only) |
| L3 Task | 6 | 15 | YES (owned files loaded) |

## 7. Context Injection Checklist

Use this checklist when building context injection for a Task Agent:

```
CONTEXT INJECTION CHECKLIST
════════════════════════════

□ Identity section populated (role, task_id, team)
□ Task description is self-contained (not referencing external docs by name only)
□ Acceptance criteria are binary-testable
□ Predecessor summary is ≤ 5 sentences (not full artifact)
□ Design excerpt is the relevant section ONLY (not full doc)
□ Interface signatures are complete (types, return types, constraints)
□ Owned files listed with purpose annotations
□ Read-only files listed (dependencies the task needs to reference)
□ No file appears in both owned AND another parallel task's owned
□ Rules loading strategy matches task complexity
□ Timeout is set (default: estimated_minutes × 120 seconds)
□ max_files_to_read is set (prevents context explosion)
□ Total token estimate is within layer budget (~8K for L3)

LEAK PREVENTION CHECKS:
□ No conversation history from prior tasks included
□ No file contents from other parallel tasks included
□ No full predecessor artifacts (summaries only)
□ No error details from sibling tasks
□ No quality scores from unrelated tasks
□ No deferred items from other stages
```

## 8. Information Density Optimization (v2.2.0)

Context injection now supports density-aware loading:

**Task-Adaptive Profiles**: Six profiles (hotfix, research, design, refactor, review, feature) control which SKILL.md sections load per task type. Defined in `context_profiles.yaml`.

**Lean Message Format**: Inter-layer messages (TaskDispatch, StatusReport) use structured compact format. Key changes:
- `key_facts` lists replace paragraph summaries (verbatim extraction, zero hallucination)
- Cause→effect notation for acceptance criteria (e.g., "expired → 401")
- Abbreviated severity codes (B/C/M/m/i)

**Acceptance Readiness Gate**: Pre-workflow validation of acceptance criteria quality. Prevents budget exhaustion from rework caused by vague criteria.

## 9. Debugging Context Issues

### Symptom → Cause → Fix

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Task produces output inconsistent with design | Design excerpt missing or truncated | Expand design_reference_excerpt to cover relevant section |
| Task modifies files it shouldn't | owned_files misconfigured | Audit owned_files list; ensure disjoint within wave |
| Task reasoning seems confused | Context pollution from prior task | Verify fresh context spawn; check no history leakage |
| Task runs out of context mid-reasoning | Budget exhaustion; too much injected | Reduce context injection; use Minimal loading strategy |
| Parallel tasks produce conflicting code | Shared file ownership | Re-partition files; ensure disjoint ownership in wave |
| Task ignores interface contracts | relevant_interfaces not populated | Add interface signatures to context.relevant_interfaces |
| Task quality low despite good design | Rules not loaded or wrong strategy | Check rules.loading_strategy matches task complexity |
