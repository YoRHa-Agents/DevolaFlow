---
task_id: S01-T03
title: "Deep-Dive Research: gstack and Karpathy LLM Wiki"
team: Research
status: complete
sources_consulted: 2
confidence: high
last_updated: "2026-04-11"
---

# S01-T03 — Role Routing, Knowledge Persistence, and Artifact Patterns

## Executive Summary

This report analyzes two external sources for patterns relevant to DevolaFlow's
agent hierarchy and knowledge management:

1. **gstack** (github.com/garrytan/gstack) — a slash-command-based specialist
   routing system for Claude Code, built by Garry Tan (YC CEO). 23+ specialist
   roles, SKILL.md-driven, sequential sprint workflow.
2. **Karpathy LLM Wiki** (gist by Andrej Karpathy) — a pattern for LLM-maintained
   persistent knowledge bases with ingest/query/lint operations and structured
   markdown artifacts.

Both offer patterns that map directly to DevolaFlow's team-role specialization
(5 AgentTeams) and P5 artifacts-as-contracts principle. Key takeaways: gstack
demonstrates production-grade role routing via SKILL.md frontmatter and proactive
skill suggestion; Karpathy's wiki pattern offers a compounding knowledge layer
that DevolaFlow currently lacks.

---

## Source 1: gstack

### 1.1 Overview

- **Repository:** github.com/garrytan/gstack (MIT license)
- **Cloned to:** /home/agent/reference/gstack
- **Architecture:** Collection of SKILL.md files, each defining a specialist
  agent role. Installed as Claude Code skills at `~/.claude/skills/gstack/`.
  Each skill is a self-contained directory with a `SKILL.md` (generated from
  `.tmpl` template) and optional supporting files.
- **Scale:** 23+ specialist skills, 8 power tools, supports 8 AI coding agents
  (Claude Code, Codex, Cursor, Factory, Slate, Kiro, OpenCode, OpenClaw).

### 1.2 Role Routing and Specialization Patterns

#### 1.2.1 SKILL.md Frontmatter as Role Definition

Each specialist is defined by YAML frontmatter in its SKILL.md:

```yaml
name: office-hours          # slash-command name
preamble-tier: 3            # context priority level
version: 2.0.0
description: |              # natural language trigger conditions
  YC Office Hours — two modes. Use when asked to "brainstorm",
  "I have an idea", "help me think through this"...
allowed-tools:              # tool ACL per role
  - Bash
  - Read
  - Write
  - AskUserQuestion
  - WebSearch
voice-triggers:             # speech-to-text activation phrases
  - "brainstorm this"
benefits-from: [office-hours]  # skill dependency chain
```

**DevolaFlow comparison:** DevolaFlow defines team roles via the `team-roles.md`
reference document with input/output contracts per team (Research, Design,
Implement, Test, Review). gstack's per-skill frontmatter is more granular —
each skill specifies its own tool ACL, trigger conditions, and dependency chain.
DevolaFlow's teams have fixed tool sets; gstack's skills have per-role tool sets.

#### 1.2.2 Sprint-Based Sequential Routing

gstack enforces a process order: **Think → Plan → Build → Review → Test → Ship → Reflect**

| Phase | gstack Skills | DevolaFlow Equivalent |
|-------|--------------|----------------------|
| Think | `/office-hours` | Research stage |
| Plan | `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review` | Design stage |
| Build | (manual implementation) | Implement stage |
| Review | `/review`, `/codex` (cross-model) | Review stage |
| Test | `/qa`, `/qa-only`, `/benchmark`, `/cso` | Test stage |
| Ship | `/ship`, `/land-and-deploy`, `/canary` | Release stage |
| Reflect | `/retro`, `/document-release` | (no equivalent) |

**Key difference:** gstack's skills are invoked by a single human operator via
slash commands. DevolaFlow's stages are orchestrated by L0-L2 dispatcher agents
with structured TaskDispatch messages. gstack's routing is user-initiated or
proactively suggested; DevolaFlow's routing is computed by the decomposition gate.

#### 1.2.3 Proactive Skill Suggestion

gstack uses conversation-context analysis to proactively suggest relevant skills:

- Detects keywords ("does this work?" → suggest `/qa`, bug description → suggest
  `/investigate`)
- Configurable via `gstack-config set proactive true/false`
- Pattern tracking via `timeline.jsonl` to predict next skill from recent sequence

**DevolaFlow gap:** DevolaFlow has no proactive task suggestion mechanism. The
Project Agent (L0) decomposes requirements into stages, but there is no feedback
loop where past execution patterns inform future task routing.

#### 1.2.4 Cross-Model Review (Dual Voices)

gstack's `/autoplan` runs parallel reviews from Claude AND Codex (OpenAI),
producing consensus tables per dimension (architecture, security, performance).
Disagreements are classified as "taste decisions" surfaced to the user.

**DevolaFlow comparison:** DevolaFlow's Review team operates as a single-model
reviewer. The convergence loop handles iterative fix cycles but does not support
cross-model validation or consensus mechanisms.

#### 1.2.5 Review Specialists

The `review/specialists/` directory contains domain-specific review checklists:
`api-contract.md`, `data-migration.md`, `maintainability.md`, `performance.md`,
`red-team.md`, `security.md`, `testing.md`.

**DevolaFlow comparison:** DevolaFlow's code-rules system
(`knowledge/code-rules-mapping.md`) provides similar layered rule loading
(core → language → task-type → quality-focus) with severity-weighted scoring.
gstack's approach is simpler (markdown checklists per domain) but more
immediately extensible by end users.

### 1.3 Knowledge Persistence and Artifact Management

#### 1.3.1 Learnings System (`/learn`)

gstack implements persistent cross-session learning via JSONL files:

- **Storage:** `~/.gstack/projects/{slug}/learnings.jsonl`
- **Schema:** `{skill, type, key, insight, confidence, source, files}`
- **Types:** pattern, pitfall, preference, architecture, tool, operational
- **Operations:** search, prune (stale file detection, contradiction check),
  export (to markdown for CLAUDE.md), stats, manual add
- **Automatic ingestion:** Every skill session reflects on failures and logs
  operational learnings before completion

**DevolaFlow comparison:** DevolaFlow has no cross-session learning persistence.
Knowledge exists only in the `workflow-system/agent/knowledge/` directory
(principle-mapping.md, code-rules-mapping.md) as static reference documents.
These are versioned but not dynamically updated from execution feedback.

#### 1.3.2 Session Timeline and Context Recovery

- **Timeline:** `~/.gstack/projects/{slug}/timeline.jsonl` — records skill
  start/complete events with branch, duration, outcome
- **Context recovery:** On session start, reads recent artifacts, last session
  info, and latest checkpoint to restore context
- **Pattern prediction:** Analyzes last 3 completed skills to suggest next action

**DevolaFlow comparison:** DevolaFlow's P5 (artifacts as contracts) defines
artifact schemas but has no cross-session timeline or context recovery mechanism.
Each workflow execution starts fresh with only the predecessor summary provided
by the parent dispatcher.

#### 1.3.3 Design Doc Lineage

Office hours sessions produce design docs at `~/.gstack/projects/{slug}/`
with branch-specific naming and `Supersedes:` metadata for revision chains.
Downstream skills automatically discover and read prior design docs.

**DevolaFlow comparison:** DevolaFlow's Stage Agents pass `predecessor_summaries`
downstream but there is no persistent design doc lineage that accumulates
across workflow executions.

#### 1.3.4 Builder Profile

gstack tracks user behavior across sessions in `builder-profile.jsonl`:
signal count, design doc history, resource dedup, tier progression
(introduction → welcome_back → regular → inner_circle).

**DevolaFlow gap:** No user/project profile that evolves across executions.

### 1.4 Session/Memory Management

| Mechanism | gstack Implementation |
|-----------|-----------------------|
| Session tracking | `~/.gstack/sessions/$PPID` touch files, 2hr TTL |
| Multi-session awareness | Count active sessions, enter "ELI16 mode" at 3+ |
| Analytics | Local JSONL + optional remote Supabase telemetry |
| State persistence | `.gstack/browse.json` (daemon), config.yaml (preferences) |
| Restore points | `/autoplan` saves plan state before modification |

### 1.5 Cross-Agent Handoff Mechanisms

| Mechanism | Description |
|-----------|-------------|
| `benefits-from` | Skill dependency: `/autoplan` benefits from `/office-hours` output |
| Design doc discovery | `ls -t ~/.gstack/projects/$SLUG/*-design-*.md` in every plan skill |
| Review log system | `gstack-review-log` writes JSONL, `/ship` reads Review Readiness Dashboard |
| `conductor.json` | External parallel sprint orchestrator (10-15 sessions) |
| `/pair-agent` | Cross-agent browser sharing with scoped tokens and tab isolation |

**DevolaFlow comparison:** DevolaFlow's handoff mechanism is structured
StatusReport YAML messages flowing upward through the hierarchy (Task → Wave →
Stage → Project). gstack uses filesystem-based artifact discovery — each skill
reads known paths. DevolaFlow's approach is more formal; gstack's is more
pragmatic and immediately extensible.

### 1.6 DevolaFlow Relevance Score: 4/5

**Rationale:** gstack's role routing patterns, per-skill tool ACLs, proactive
skill suggestion, cross-model review, and learnings system are all directly
applicable to DevolaFlow. The sprint-sequential workflow maps cleanly to
DevolaFlow's stage pipeline. The learnings system addresses a gap DevolaFlow
currently has. Only docked 1 point because gstack targets single-human-operator
usage (slash commands) rather than multi-layer agent orchestration.

### 1.7 Integration Ideas (gstack → DevolaFlow)

1. **Per-Team Tool ACLs in TaskDispatch:** Adopt gstack's frontmatter
   `allowed-tools` pattern. Instead of fixed tool sets per AgentTeam in
   `team-roles.md`, include an `allowed_tools` field in TaskDispatch that the
   Wave Agent configures per task based on team role + task type. This enables
   finer-grained tool control (e.g., a Research task that needs WebSearch vs.
   one that only needs file reading).

2. **Operational Learnings JSONL for Convergence Loops:** Implement a
   gstack-style learnings system scoped to DevolaFlow workflows. After each
   convergence loop completes, the Review Agent logs operational findings
   (rule violations that recurred, common fix patterns, project-specific
   quirks) to a per-project JSONL at
   `workflow-system/agent/knowledge/learnings/{project-slug}.jsonl`. Future
   Task Agents in the same project load relevant learnings during LOAD_RULES.
   Schema: `{stage, task_type, key, insight, confidence, rule_id}`.

3. **Cross-Model Gate Validation:** Adopt gstack's "dual voices" consensus
   pattern for DevolaFlow's gate evaluation. When a gate decision is borderline
   (composite score within 5 points of threshold), dispatch a secondary review
   to a different model. Produce a consensus table. Disagreements escalate to
   the Stage Agent with both perspectives. This directly strengthens the Review
   stage without changing the hierarchy.

4. **Proactive Task Suggestion via Execution Pattern Analysis:** Implement
   timeline tracking similar to gstack's `timeline.jsonl`. After each stage
   completes, log `{stage, outcome, duration, findings_count}`. The Project
   Agent (L0) can analyze patterns across executions to suggest workflow
   adjustments (e.g., "Design stage consistently produces 5+ Review findings
   related to test coverage — consider adding a Test-focused Design sub-task").

5. **Reference Dependency Tracking via `benefits-from`:** Adopt gstack's
   `benefits-from` frontmatter field as a reference dependency mechanism. Each
   DevolaFlow stage/task can declare which predecessor artifacts it benefits
   from. The Wave Agent verifies these dependencies exist before dispatching.
   Missing dependencies trigger a warning or auto-insertion of the prerequisite
   task. Implementation: add `depends_on_artifacts: [path]` to TaskDispatch
   schema.

---

## Source 2: Karpathy LLM Wiki

### 2.1 Overview

- **Source:** gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- **Saved to:** /home/agent/reference/karpathy-llm-wiki.md
- **Nature:** Abstract pattern description (not a codebase). Describes how to
  use LLMs to build and maintain persistent, structured knowledge bases.
- **Key insight:** Instead of RAG (re-deriving knowledge per query), the LLM
  incrementally builds and maintains a persistent wiki — a compounding artifact
  where cross-references, contradictions, and synthesis are pre-computed.

### 2.2 Architecture (Three Layers)

| Layer | Description | Mutability |
|-------|-------------|------------|
| **Raw Sources** | Curated source documents (articles, papers, data files) | Immutable — LLM reads only |
| **The Wiki** | LLM-generated markdown files (summaries, entity pages, synthesis) | LLM-owned — creates, updates, cross-references |
| **The Schema** | Configuration file (CLAUDE.md/AGENTS.md) defining wiki structure and conventions | Co-evolved by human + LLM |

**DevolaFlow mapping:**

| Karpathy Layer | DevolaFlow Equivalent | Gap |
|----------------|----------------------|-----|
| Raw Sources | Cloned repos, spec files, prior artifacts | Exists — read-only references in TaskDispatch |
| The Wiki | `workflow-system/agent/knowledge/` + `references/` | Partial — static docs, not dynamically maintained |
| The Schema | SKILL.md + context_profiles.yaml | Exists — but no wiki maintenance schema |

### 2.3 Operations Pattern (Ingest / Query / Lint)

#### 2.3.1 Ingest

Source is added → LLM reads it → extracts key information → integrates into
existing wiki pages → updates index → appends to log.

"A single source might touch 10-15 wiki pages."

**DevolaFlow comparison:** DevolaFlow's Research team performs SCOPE → GATHER →
ANALYZE → SYNTHESIZE → SELF-CHECK. The output is a report written to
`report_path`. But this report is a standalone artifact — it does not update
a persistent knowledge base or cross-reference existing knowledge pages.

#### 2.3.2 Query

Questions are answered by searching the wiki (via index.md), reading relevant
pages, and synthesizing answers with citations. Good answers are filed back
into the wiki as new pages.

**DevolaFlow comparison:** DevolaFlow's knowledge files
(`principle-mapping.md`, `code-rules-mapping.md`) serve a query-like role — Task
Agents load them during LOAD_RULES. But there is no mechanism to file new
discoveries back into the knowledge base from execution results.

#### 2.3.3 Lint

Periodic health-check: find contradictions between pages, stale claims
superseded by newer sources, orphan pages, missing cross-references, data gaps.

**DevolaFlow comparison:** No equivalent. DevolaFlow's knowledge files are
manually maintained. There is no automated lint pass that detects stale
principle mappings, outdated code-rules references, or knowledge gaps.

### 2.4 Indexing and Logging

| File | Purpose | DevolaFlow Equivalent |
|------|---------|----------------------|
| `index.md` | Content catalog — pages with summaries, organized by category | None — no central knowledge index |
| `log.md` | Chronological append-only record of operations | StatusReport chain (but not persisted across executions) |

### 2.5 Knowledge Persistence Pattern Analysis

The core insight is **compounding knowledge** — each interaction makes the
knowledge base richer, not just the conversation history. Key properties:

1. **Persistent artifact:** The wiki persists across sessions (it's just
   markdown files on disk).
2. **Incremental update:** New sources update existing pages rather than
   creating parallel standalone docs.
3. **Cross-referencing:** Links between pages are maintained automatically.
4. **Contradiction detection:** New data is compared against existing claims.
5. **Schema co-evolution:** The configuration file evolves as the domain
   becomes better understood.

**DevolaFlow P5 comparison:** DevolaFlow's P5 (artifacts as contracts) defines
that layers communicate through artifact files, each with a defined schema.
The wiki pattern extends P5 by making artifacts **mutable and accumulative**
rather than write-once. P5 artifacts are contracts (produce once, consume once);
wiki pages are living documents (produce once, update many times, consume many
times).

### 2.6 Session/Memory Management

The wiki IS the memory management layer. Unlike conversation-history-based
memory (which is bounded by context window) or RAG (which re-derives on every
query), the wiki provides:

- Pre-computed synthesis that survives context window limits
- Structured navigation via index and cross-references
- Explicit contradiction tracking across sources

### 2.7 Cross-Agent Handoff Mechanisms

The gist does not describe multi-agent scenarios, but the pattern naturally
supports them:

- **Shared wiki:** Multiple agents can read/write the same wiki directory
- **Index as coordination:** The index.md file serves as a shared catalog
- **Log as audit trail:** The log.md provides temporal ordering of operations
- **Schema as protocol:** The schema file (CLAUDE.md) is the shared convention

### 2.8 DevolaFlow Relevance Score: 3/5

**Rationale:** The wiki pattern is highly relevant to DevolaFlow's knowledge
management gap, but the gist is abstract (no implementation). The ingest/query/
lint operations and compounding knowledge model directly address DevolaFlow's
need for reference dependency tracking and cross-session knowledge persistence.
Docked 2 points because: (1) the pattern requires significant implementation
work to integrate, and (2) it does not address role routing, agent hierarchy,
or structured inter-layer communication — which are DevolaFlow's core concerns.

### 2.9 Integration Ideas (Karpathy Wiki → DevolaFlow)

1. **Knowledge Wiki Layer for DevolaFlow Projects:** Add a
   `workflow-system/agent/knowledge/wiki/` directory that is LLM-maintained
   across workflow executions. After each Research task completes, its findings
   are ingested into the wiki (updating entity pages, adding cross-references,
   noting contradictions with prior findings). The wiki serves as the persistent
   knowledge substrate that all Task Agents can query during LOAD_RULES or
   GATHER phases. Requires: (a) `index.md` as central catalog, (b) `log.md`
   as append-only operation record, (c) ingest protocol triggered by Research
   task completion.

2. **Wiki Lint as a Maintenance Stage:** Add a periodic "Knowledge Lint" task
   type to the Research team's capabilities. This task scans the knowledge wiki
   for: stale principle-to-code mappings (referenced files deleted or renamed),
   contradictions between knowledge pages, orphan pages with no inbound
   references, knowledge gaps flagged by recent Review findings. Output:
   a lint report with suggested updates, filed as a StatusReport to the
   Project Agent. Implementation: add `knowledge_lint` to Research team's
   task type enum, with acceptance criteria covering contradiction count,
   orphan count, and staleness percentage.

3. **Query-Back-to-Wiki for Review Findings:** When the Review Agent discovers
   a recurring pattern (same rule_id violated across multiple tasks/stages),
   file this pattern back into the knowledge wiki as a "project pitfall" page.
   Future Implement Agents loading rules for the same project receive this
   pitfall as additional context. This implements Karpathy's principle that
   "good answers can be filed back into the wiki as new pages." Schema:
   `{pitfall_id, rule_id, occurrence_count, last_seen, description,
   recommended_fix}`.

4. **Schema Co-Evolution via context_profiles.yaml:** Treat
   `context_profiles.yaml` as the wiki's "schema" layer. After each workflow
   execution, the Project Agent evaluates whether context profiles should be
   updated (e.g., a task type consistently under-budgets tokens → increase
   budget, a knowledge section is consistently skipped → mark as `skip`). This
   co-evolution mirrors Karpathy's "you and the LLM co-evolve [the schema]
   over time."

---

## Comparative Analysis

### Role Routing Patterns

| Dimension | gstack | Karpathy Wiki | DevolaFlow |
|-----------|--------|---------------|------------|
| **Role definition** | SKILL.md frontmatter (per-skill) | N/A (single agent) | team-roles.md (per-team, 5 teams) |
| **Routing mechanism** | Slash commands + proactive suggestion | N/A | Decomposition gate + TaskDispatch |
| **Tool ACL** | Per-skill `allowed-tools` | N/A | Per-team fixed tool set |
| **Role count** | 23+ specialists | 1 (wiki maintainer) | 5 teams × N tasks |
| **Cross-model** | Dual voices (Claude + Codex) | N/A | Single model per task |

### Knowledge Persistence Patterns

| Dimension | gstack | Karpathy Wiki | DevolaFlow |
|-----------|--------|---------------|------------|
| **Persistence format** | JSONL (learnings, timeline, reviews) | Markdown wiki (pages + index + log) | Static markdown (knowledge/, references/) |
| **Update trigger** | End of each skill session | Each source ingest + each query | Manual versioning only |
| **Cross-referencing** | Skill→artifact path conventions | Wiki internal links, index catalog | Tier/dependency fields in frontmatter |
| **Contradiction detection** | `/learn prune` (stale file check) | Lint operation (explicit) | None |
| **Compounding** | Learnings + timeline grow per session | Wiki pages enriched per source | No compounding mechanism |

### Artifact Management Patterns

| Dimension | gstack | Karpathy Wiki | DevolaFlow |
|-----------|--------|---------------|------------|
| **Artifact schema** | Informal (design doc template, review JSONL) | Schema file (CLAUDE.md/AGENTS.md) | Formal YAML schemas (TaskDispatch, StatusReport) |
| **Inter-layer handoff** | Filesystem path conventions | Shared wiki directory | Typed YAML messages (P3) |
| **Dependency tracking** | `benefits-from` frontmatter field | `index.md` + internal links | `predecessor_summaries` in dispatch |
| **Lineage** | `Supersedes:` field in design docs | Version history via git | None (each execution is independent) |

### Session/Memory Management

| Dimension | gstack | Karpathy Wiki | DevolaFlow |
|-----------|--------|---------------|------------|
| **Cross-session persistence** | Timeline, learnings, builder profile | Wiki is the memory | None (P5 artifacts are per-execution) |
| **Context recovery** | Reads recent artifacts on session start | Wiki already contains synthesis | Fresh start with predecessor summaries |
| **Pattern detection** | Recent skill sequence analysis | Lint detects gaps and contradictions | None |

---

## Prioritized Integration Recommendations for DevolaFlow

### High Priority (addresses existing gaps)

1. **Operational Learnings System** (from gstack `/learn`)
   - Add per-project JSONL learnings file
   - Auto-populate from Review Agent convergence loop findings
   - Load during Task Agent LOAD_RULES phase
   - Effort: ~1 day implementation, ~0.5 day tests

2. **Reference Dependency Tracking** (from gstack `benefits-from`)
   - Add `depends_on_artifacts` field to TaskDispatch schema
   - Wave Agent verifies dependencies before dispatch
   - Missing dependencies trigger prerequisite task insertion
   - Effort: ~0.5 day schema change, ~0.5 day validation logic

3. **Knowledge Index** (from Karpathy `index.md`)
   - Add `knowledge/index.md` as central catalog of all knowledge pages
   - Auto-update when knowledge files are modified
   - Task Agents read index first, then drill into relevant pages
   - Effort: ~0.5 day implementation

### Medium Priority (strengthens existing mechanisms)

4. **Cross-Model Gate Validation** (from gstack dual voices)
   - Borderline gate decisions dispatched to secondary model
   - Consensus table produced, disagreements escalate
   - Effort: ~1 day design, ~1 day implementation

5. **Knowledge Lint Task Type** (from Karpathy lint)
   - Periodic scan for stale mappings, contradictions, orphans
   - New task type for Research team
   - Effort: ~1 day implementation

### Lower Priority (nice-to-have, larger scope)

6. **Wiki-Style Knowledge Layer** (from Karpathy full pattern)
   - LLM-maintained wiki directory with ingest/query/lint
   - Research findings auto-ingested into wiki pages
   - Largest effort, highest long-term value
   - Effort: ~3 days design + implementation

7. **Proactive Task Suggestion** (from gstack pattern detection)
   - Execution timeline tracking
   - Project Agent suggests workflow adjustments from patterns
   - Effort: ~2 days design + implementation

---

## Appendix A: Source File Inventory

### gstack (cloned to /home/agent/reference/gstack)

| File | Purpose | Lines Read |
|------|---------|------------|
| README.md | Project overview, skill catalog, install instructions | 406 |
| SKILL.md | Root skill definition (browse + preamble) | 882+ |
| AGENTS.md | Codex-compatible agent instructions | 50 |
| CLAUDE.md | Development guide, project structure, conventions | 498 |
| ARCHITECTURE.md | Design decisions, daemon model, security model | 362 |
| DESIGN.md | Design system (typography, color, spacing) | 87 |
| ETHOS.md | Builder philosophy (Boil the Lake, Search Before Building) | 165 |
| conductor.json | Parallel sprint orchestrator config | 7 |
| agents/openai.yaml | OpenAI Codex agent interface config | 6 |
| learn/SKILL.md | Learnings management skill definition | 708 |
| office-hours/SKILL.md.tmpl | Office hours skill template (product diagnostic) | 883 |
| autoplan/SKILL.md.tmpl | Auto-review pipeline template | 842 |
| review/specialists/*.md | 7 domain-specific review checklists | (listed) |

### Karpathy LLM Wiki (saved to /home/agent/reference/karpathy-llm-wiki.md)

| Section | Key Content |
|---------|-------------|
| Core idea | Persistent wiki vs. RAG — compounding artifact |
| Architecture | Three layers: raw sources, wiki, schema |
| Operations | Ingest, query, lint |
| Indexing | index.md (content catalog), log.md (chronological record) |
| Tips | Obsidian integration, CLI tools, git version history |

### DevolaFlow Context (read-only reference)

| File | Purpose |
|------|---------|
| workflow-system/agent/knowledge/principle-mapping.md | SOLID/TDD/CleanArch/DDD enforcement mapping |
| workflow-system/agent/knowledge/code-rules-mapping.md | Code-rules integration flow (loading strategies, quality focus) |
| workflow-system/agent/references/team-roles.md | 5 AgentTeam definitions with I/O contracts |
