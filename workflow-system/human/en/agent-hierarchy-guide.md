---
title: "Agent Hierarchy Guide"
description: "Understanding the three-layer Project, Wave, and Task hierarchy."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T08:09:16Z"
source_version: "16.0.0"
---

# Agent Hierarchy Guide

Understanding the three-layer Project, Wave, and Task hierarchy.

## Why a Hierarchy?

A single AI agent attempting a complex task (e.g., "build an auth system") faces two problems:
1. **Context overflow** — it tries to hold everything in memory at once
2. **Scope creep**, it drifts between design, implementation, and review without structure

DevolaFlow uses three layers to constrain context drift while keeping the dispatch chain short.

## L0: Project Agent (~5K tokens)

The Project Agent is the **orchestra conductor**. It selects a checklist seed and anchors `goal.md`, `checklist.md`, and `preflight.md` with the user. It also:
- Picks P0/P1/P2 items for each bounded round and partitions them into waves
- Verifies Task evidence before checking assertions
- Evaluates round and archive gates, then decides: advance, retry, or escalate
- Reports final status to the human

**Never does**: Implement, run tests, author deliverables, or modify Task output.

## L1: Wave Agent (~5K tokens)

A Wave Agent coordinates a bounded group of parallel Tasks. It:
- Receives checklist item IDs, verbatim assertions, verification rules, and file ownership
- Dispatches up to five L2 Tasks with disjoint writable files
- Collects StatusReports and checks for cross-task conflicts
- Aggregates evidence and submits a concise check proposal to L0

**Never does**: Perform any Task's work or modify its output.

## L2: Task Agent (~8K tokens)

The Task Agent is the **only implementation layer**. It:
- Receives one atomic assignment tied to checklist item IDs
- Works within its owned files only
- Self-verifies against the supplied assertions without self-scoring
- Reports artifacts, test results, and verbatim evidence to L1

**Constraints**: It cannot spawn sub-agents or write outside the owned set.

## Checklist-Round Flow

```
L0 picks open checklist assertions and records the round in stage.md
  └─ L1 Wave dispatches isolated L2 Tasks
       ├─ L2 Task executes and reports evidence
       └─ L2 Task executes and reports evidence
  └─ L1 aggregates evidence and proposes checks
L0 verifies evidence, checks passing assertions, and closes or repeats the round
```

`stage.md` is a round-control artifact, not an agent role. In checklist seeds, `source_stages` stores only historical source IDs and primitive provenance; it has no executable ordering semantics.

## Escalation Chain

```
Task Agent → Wave Agent → Project Agent → Human
```

Escalation always moves **upward**, never skips levels. Every failure is classified:

| Severity | Action |
|----------|--------|
| `AUTO_RECOVER` | Retry up to 3× with exponential backoff |
| `PAUSE` | Pause task, queue question, continue parallel work |
| `HUMAN_INTERVENE` | Stop the round, present options to the human |
| `FULL_ROLLBACK` | Rollback to checkpoint, halt everything |

## Communication Protocol

All inter-layer communication uses **typed YAML messages** (not free-form chat):

- **TaskDispatch**: task_id, type, title, description, owned_files, acceptance_criteria, timeout
- **StatusReport**: task_id, state, progress_pct, artifacts, metrics
- **ExceptionEscalation**: severity, context, options for the next layer

## Example: Hotfix Trace

```
Human: "Fix the login timeout bug"
  └─ L0 Project: selects hotfix seed; user confirms checklist and preflight
       └─ Round 1 / L1 Wave
            └─ L2 Task: reproduces defect and reports root-cause evidence
       └─ L0: verifies evidence and checks diagnosis assertion
       └─ Round 2 / L1 Wave
            ├─ L2 Task: implements the minimal fix
            └─ L2 Task: runs focused regression tests
       └─ L1: aggregates evidence; L0 verifies and checks both assertions
  └─ L0 Project: archive gate passes; reports SUCCESS to human
```
