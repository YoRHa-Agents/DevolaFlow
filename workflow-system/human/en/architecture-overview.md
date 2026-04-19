---
title: "Architecture Overview"
description: "System architecture: 4-layer hierarchy, stage primitives, gate mechanism."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-19T04:46:26Z"
source_version: "7.2.4"
---

# Architecture Overview

System architecture: 4-layer hierarchy, stage primitives, gate mechanism.

## System Overview

DevolaFlow orchestrates complex software tasks through a **4-layer agent hierarchy** with **quality gates** at every stage boundary. Instead of one agent trying to do everything, work is decomposed into isolated tasks executed by specialized agents.

```
User Request
    │
    ▼
┌─────────────────────┐
│   Pre-Decision       │  Detect repo mode, recommend workflow type
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L0: Project Agent   │  Select workflow, sequence stages    (~3K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L1: Stage Agent     │  Decompose into waves, run gates     (~5K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L2: Wave Agent      │  Dispatch parallel tasks              (~4K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L3: Task Agent      │  **Execute actual work**              (~8K tok)
└─────────────────────┘
```

**Key invariant**: Only Layer 3 (Task Agents) perform actual work — writing code, running tests, reviewing, authoring documents. Layers 0–2 exclusively dispatch, monitor, and report.

## The 4-Layer Hierarchy

| Layer | Role | Context Budget | Delegates To | Must NOT |
|-------|------|---------------|-------------|----------|
| **L0: Project** | Selects workflow, sequences stages, tracks status | ~3K tokens | Stage Agents | Write code, read source files |
| **L1: Stage** | Decomposes stage into waves, runs convergence loops | ~5K tokens | Wave Agents | Write code, execute tests |
| **L2: Wave** | Dispatches parallel tasks, checks for conflicts | ~4K tokens | Task Agents | Modify any task's output |
| **L3: Task** | Executes a single atomic unit of work | ~8K tokens | Nothing (leaf) | Spawn sub-agents |

## 13 Stage Primitives

Every workflow is composed from 13 universal primitives organized into 6 categories:

| Category | Primitives | Purpose |
|----------|-----------|---------|
| **Discover** | `research`, `analyze` | Gather information, assess current state |
| **Shape** | `design`, `plan` | Define architecture, decompose into tasks |
| **Build** | `implement`, `refine` | Write code, fix issues |
| **Verify** | `review`, `test`, `validate` | Check quality, run tests, aggregate results |
| **Deliver** | `release`, `deploy`, `monitor` | Package, ship, observe |
| **Control** | `gate` | Quality checkpoint blocking progression |

Primitives compose via 5 operators: **sequence** (→), **parallel** (||), **choice** (⊕), **loop** (↻), **gate** (⊣).

## Task-Adaptive Context Selection

Each task type has a **context profile** that selects only relevant SKILL.md sections, keeping the context window lean:

- A **hotfix** agent receives: triage procedures, fix guidelines, test requirements — but skips design primitives
- A **research** agent receives: research methodology, comparison frameworks — but skips convergence loops
- A **design** agent receives: architecture patterns, ADR templates — but skips release procedures

Profiles are defined in `workflow-system/agent/context_profiles.yaml`.

## Quality Gate Mechanism

Gates are quality checkpoints between stages. Every gate evaluates a **composite score**:

```
composite = test_quality × 0.30 + code_review × 0.30
          + architecture × 0.20 + benchmark × 0.20
```

**Pass conditions** (all required):
1. `composite_score >= threshold` (default: 85)
2. Zero blocker findings AND zero MUST-priority violations
3. `coverage >= coverage_threshold` (default: 80%)

**On failure**: The gate triggers a convergence loop (review → fix → test → recheck), up to 3 rounds. If still failing, it escalates to the human.

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
- **Task spec**: title, description, acceptance criteria
- **Context**: predecessor summaries, design excerpts, interface contracts
- **Files**: owned files (create/modify) + read-only references
- **Rules**: coding conventions, quality focus areas
- **Behavioral**: timeout, max files, escalation policy

**Never leaked between tasks**: conversation history, file contents from sibling tasks, error details from parallel work, quality scores from unrelated tasks.

## Repository Rules

18 enforceable rules in `.cursor/rules/` codifying iteration lessons:

| Rule File | Covers |
|-----------|--------|
| `skill-format-rules.mdc` (SF-1 to SF-6) | SKILL.md line budget, frontmatter, version consistency, valid references |
| `change-process-rules.mdc` (CP-1 to CP-7) | Test coverage floor (≥80%), no ghost features, version bump protocol |
| `context-optimization-rules.mdc` (CO-1 to CO-6) | Lean messages, verbatim extraction, token budgets, benchmark verification |
