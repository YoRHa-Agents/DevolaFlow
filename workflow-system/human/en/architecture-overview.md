---
title: "Architecture Overview"
description: "Three-layer checklist-round architecture, provenance primitives, and quality gates."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T07:21:59Z"
source_version: "16.0.0"
---

# Architecture Overview

Three-layer checklist-round architecture, provenance primitives, and quality gates.

## System Overview

DevolaFlow orchestrates complex software work through **checklist rounds** and a **three-layer agent hierarchy**. A user-approved checklist is the execution contract: every item is measurable, every completion has evidence, and every loop is bounded.

```
User Request
    │
    ▼
┌─────────────────────┐
│  Checklist Seed      │  Select domain decomposition knowledge
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L0: Project Agent   │  Anchor checklist, manage rounds     (~5K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L1: Wave Agent      │  Dispatch tasks, aggregate evidence  (~5K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L2: Task Agent      │  **Execute actual work**              (~8K tok)
└─────────────────────┘
```

**Key invariant**: Only L2 Task Agents perform actual work — writing code, running tests, reviewing, or authoring documents. L0 Project and L1 Wave agents only dispatch, monitor, verify evidence, and report.

## The Three-Layer Hierarchy

| Layer | Role | Context Budget | Delegates To | Must NOT |
|-------|------|---------------|-------------|----------|
| **L0: Project** | Anchors goal/checklist/preflight, picks each round, evaluates evidence and gates | ~5K tokens | L1 Wave | Implement or alter Task output |
| **L1: Wave** | Dispatches parallel Tasks, checks ownership conflicts, aggregates evidence proposals | ~5K tokens | L2 Task | Perform any Task's work |
| **L2: Task** | Executes one atomic checklist assignment and reports evidence | ~8K tokens | Nothing (leaf) | Spawn sub-agents or write outside its owned set |

The escalation chain is always upward: **Task → Wave → Project → Human**.

## Checklist-Round Runtime

`change-driven` is the sole executable runtime:

1. **Propose**: L0 and the user anchor numbered goals and a measurable checklist.
2. **Preflight**: The user signs project decisions and blocker pre-authorizations once.
3. **Round**: L0 picks the highest-priority open items, partitions them into waves, and records the plan in `stage.md`.
4. **Execute**: L1 dispatches up to five isolated L2 Tasks per wave.
5. **Verify**: Tasks report evidence; L1 aggregates it; L0 verifies it before checking any item.
6. **Repeat or archive**: A round passes when its picked items are checked with evidence and no blockers remain. Once the full checklist and archive gate pass, the change can be archived.

Composite gate scores remain a trend signal during rounds. They do not replace the primary contract: checked assertions with valid evidence and zero blockers.

## 23 Checklist Seeds and Primitive Provenance

The registry contains **23 non-executable checklist seeds** plus the one `change-driven` runtime. A seed supplies intent keywords, checklist partitions, measurable assertion templates, and verification suggestions. It never supplies a runtime DAG.

Each seed's `source_stages` field is **provenance only**. It preserves the historical source ID and one of 14 primitive labels; list order is presentation-only and must not determine execution order:

| Category | Primitives | Purpose |
|----------|-----------|---------|
| **Discover** | `research`, `analyze` | Gather information, assess current state |
| **Shape** | `design`, `plan` | Define architecture, decompose into tasks |
| **Build** | `implement`, `refine` | Write code, fix issues |
| **Verify** | `review`, `test`, `validate`, `verify` | Check quality, run tests, aggregate results |
| **Deliver** | `release`, `deploy`, `monitor` | Package, ship, observe |
| **Control** | `gate` | Quality checkpoint blocking progression |

## Task-Adaptive Context Selection

Each task type has a **context profile** that selects only relevant SKILL.md sections, keeping the context window lean:

- A **hotfix** agent receives: triage procedures, fix guidelines, test requirements — but skips design primitives
- A **research** agent receives: research methodology, comparison frameworks, but skips convergence loops
- A **design** agent receives: architecture patterns, ADR templates, but skips release procedures

Profiles are defined in `workflow-system/agent/context_profiles.yaml`.

## Quality Gate Mechanism

Gates are quality checkpoints at round and archive boundaries. Every gate can evaluate a **composite score**:

```
composite = test_quality × 0.30 + code_review × 0.30
          + architecture × 0.20 + benchmark × 0.20
```

**Pass conditions** (all required):
1. Every checklist item picked for the round has valid evidence and is checked
2. Zero blocker findings and zero MUST-priority violations
3. Archive additionally satisfies its configured composite and coverage thresholds

**On failure**: Open items and findings enter the next bounded round as reinforcement. If progress stagnates or the round limit is reached, escalation follows Task → Wave → Project → Human.

**Gate profiles**:

| Profile | Threshold | Coverage | Use When |
|---------|-----------|----------|----------|
| relaxed | ≥70 | ≥60% | Prototypes, spikes |
| standard | ≥85 | ≥80% | Normal development |
| strict | ≥90 | ≥90% | Production releases |
| audit | ≥95 | ≥90% | Security, compliance |

## Context Isolation

Each Task Agent spawns with a fresh, isolated context (~8K tokens max):

- **Identity**: role, task_id, team assignment
- **Task spec**: checklist item IDs, assertions, verification criteria
- **Context**: predecessor summaries, design excerpts, interface contracts
- **Files**: owned files (create/modify) + read-only references
- **Rules**: coding conventions, quality focus areas
- **Behavioral**: timeout, max files, escalation policy

**Never leaked between tasks**: conversation history, file contents from sibling tasks, error details from parallel work, quality scores from unrelated tasks.

## Human Interaction Surface

Alongside the agent-only `.local/.agent/` workspace, DevolaFlow maintains a durable **`.local/human/`** surface (v14.0.0+). Its three zones separate **immutable INPUT** (what humans want) from **concise OUTPUT** (what agents report back):

| Zone | Ownership and contents |
|------|------------------------|
| **`input/`** | Human-owned and immutable once ratified: constitution, REQ-ID-keyed requirements, and an append-only amendment ledger |
| **`output/`** | Agent-written and concise: `DIGEST.md` plus convergence reports |
| **`archive/`** | Superseded artifacts |

Per-artifact TOKEN budgets keep each file lean. Verify with `python -c "from devolaflow.agent_workspace import lint_human; print(lint_human())"`.

## Repository Rules

62 enforceable rules codifying iteration lessons live in `.rules/` (5 layered
source files), compiled to `AGENTS.md` and `.cursor/rules/repo-governance.mdc`:

| Rule Layer | Covers |
|-----------|--------|
| `soul.mdc` (S-1 to S-10, P0) | Immutable invariants — test coverage floor (≥80%), no ghost features, no silent failures, protected branches |
| `architecture.mdc` (A-1 to A-7, P1) | Three-layer agent hierarchy, cache-layout governance, token budgets, SSOT registries |
| `conventions.mdc` (C-1 to C-9, P2; C-8 retired) | Line budgets, frontmatter, version consistency, lean messages, verbatim extraction |
| `workflow.mdc` (W-1 to W-24, P3) | Iteration planning, benchmark guards, version bump protocol, env-flag policy |
| `style.mdc` (ST-1 to ST-13, P4) | Documentation sync, web experience, bilingual completeness |

The pre-v14.2.1 standalone files (`skill-format-rules.mdc`,
`change-process-rules.mdc`, `context-optimization-rules.mdc`, …) were demoted
to deprecated pointer stubs and retired in v15.0.0 — their SF-/CP-/CO- content
was absorbed into the layers above.
