---
title: "Agent Hierarchy Guide"
description: "Understanding the 4-layer delegation hierarchy."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-05-02T08:42:42Z"
source_version: "9.4.0"
---

# Agent Hierarchy Guide

Understanding the 4-layer delegation hierarchy.

## Why a Hierarchy?

A single AI agent attempting a complex task (e.g., "build an auth system") faces two problems:
1. **Context overflow** — it tries to hold everything in memory at once
2. **Scope creep** — it drifts between design, implementation, and review without structure

DevolaFlow solves this by splitting work across 4 layers, each with a strict context budget and a clear role.

## Layer 0: Project Agent (~3K tokens)

The Project Agent is the **orchestra conductor**. It:
- Receives the user's request and selects a workflow type
- Sequences stages and dispatches them one at a time
- Evaluates gate results to decide: advance, retry, or escalate
- Reports final status to the human

**Never does**: Read source code, write files, run tests, or review code.

## Layer 1: Stage Agent (~5K tokens)

Each Stage Agent owns **one stage** of the workflow (e.g., "Design", "Implement"). It:
- Receives the stage definition and predecessor summaries
- Decomposes the stage into waves (groups of parallel tasks)
- Runs convergence loops if review/test findings require iteration
- Evaluates the stage's quality gate

**Constraints**: Max 7 waves per stage. Gate evaluation is mandatory before advancing.

## Layer 2: Wave Agent (~4K tokens)

A Wave Agent dispatches **parallel tasks** within a wave. It:
- Assigns tasks to Task Agents with disjoint file ownership
- Collects results and checks for cross-task conflicts
- Reports wave completion status to the Stage Agent

**Constraints**: Max 5 tasks per wave. File ownership must not overlap between parallel tasks.

## Layer 3: Task Agent (~8K tokens)

The Task Agent is the **only layer that does actual work**. It:
- Receives a single, atomic task with clear acceptance criteria
- Works within its owned files only (max 6 writable files)
- Produces artifacts (code, tests, docs, reports)
- Reports completion with metrics (tests passed, coverage, findings)

**Constraints**: Max 30 min (implementation) or 45 min (research). Cannot spawn sub-agents.

## Escalation Chain

```
Task Agent → Wave Agent → Stage Agent → Project Agent → Human
```

Escalation always moves **upward**, never skips levels. Every failure is classified:

| Severity | Action |
|----------|--------|
| `AUTO_RECOVER` | Retry up to 3× with exponential backoff |
| `PAUSE` | Pause task, queue question, continue parallel work |
| `HUMAN_INTERVENE` | Stop stage, present options to human |
| `FULL_ROLLBACK` | Rollback to checkpoint, halt everything |

## Communication Protocol

All inter-layer communication uses **typed YAML messages** (not free-form chat):

- **TaskDispatch**: task_id, type, title, description, owned_files, acceptance_criteria, timeout
- **StatusReport**: task_id, state, progress_pct, artifacts, metrics
- **ExceptionEscalation**: severity, context, options for the next layer

## Example: Hotfix Trace

```
Human: "Fix the login timeout bug"
  └─ Project Agent: selects hotfix workflow
       └─ Stage Agent (Triage): dispatches 1 wave
            └─ Wave Agent: dispatches 1 task
                 └─ Task Agent: analyzes bug, identifies root cause
       └─ Stage Agent (Fix): dispatches 1 wave
            └─ Wave Agent: dispatches 1 task
                 └─ Task Agent: implements minimal fix (3 files changed)
       └─ Stage Agent (Test): dispatches 1 wave
            └─ Wave Agent: dispatches 1 task
                 └─ Task Agent: runs focused test suite (42 pass, 0 fail)
       └─ Stage Agent (Release): dispatches 1 wave
            └─ Task Agent: tags v1.2.1, updates changelog
  └─ Project Agent: reports SUCCESS to human
```
