---
id: "agent/references/agent-hierarchy"
version: "1.0.0"
purpose: >
  Defines the three-layer Project → Wave → Task hierarchy, including each
  layer's responsibilities, context budget, delegation contract, evidence
  flow, ownership boundaries, and bounded escalation behavior.
triggers:
  - "setting up agent hierarchy"
  - "debugging delegation"
  - "understanding layer roles"
tier: 2
token_estimate: 2400
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-08-25"
---

# Agent Hierarchy Reference

## 1. Architecture Overview

DevolaFlow uses three layers. No intermediate orchestration layer or fixed
workflow DAG sits between Project and Wave.

```text
Human
  │ goals, priorities, approvals
  ▼
L0 Project Agent ── round/wave dispatch ──► L1 Wave Agent
  ▲                                             │
  │ evidence proposal                           │ parallel task dispatch
  │                                             ▼
  └────────────────────────────────────── L2 Task Agents
                                                  │
                                           implementation + evidence
```

**P1 — Dispatcher-Not-Implementer:** L0 Project and L1 Wave dispatch,
coordinate, and report. Only L2 Task performs implementation, test execution,
research, review, or document authoring.

**P5 — Artifacts as Contracts:** layers exchange typed dispatches, reports,
and repository-relative artifact references. They do not share conversation
memory.

## 2. Layer Contract Summary

| Aspect | L0 Project | L1 Wave | L2 Task |
|---|---|---|---|
| Role | Round orchestrator and evidence adjudicator | Parallel task coordinator | Leaf implementer |
| Lifespan | Entire change | One wave | One task |
| Does task work? | No | No | **Yes** |
| Context budget | ~5K tokens | ~5K tokens | ~8K tokens |
| Receives | User goal, seed, lifecycle state, round reports | Wave plan, task specs, dependency state | TaskDispatch, owned files, rules, AC |
| Produces | Goal/checklist/preflight contracts, round decisions, final report | WaveReport and checklist-evidence proposal | StatusReport and task artifacts |
| Reports to | Human | L0 Project | L1 Wave |
| Delegates to | L1 Wave | L2 Task | Nothing |

The total dispatch budget is approximately 18K tokens per full cascade:
5K Project + 5K Wave + 8K Task. Budgets are ceilings, not fill targets.

## 3. L0 Project Agent

L0 owns the user-visible change contract and the checklist-round loop.

### 3.1 Before execution

1. Scan the workspace and classify complexity.
2. Select a registered checklist seed from user intent with
   `TemplateRegistry.load_seed(name)`.
3. Load the sole executable runtime with
   `TemplateRegistry.load_template("change-driven")`.
4. Draft `goal.md`, `checklist.md`, and `preflight.md`.
5. Confirm goal wording, P0/P1/P2 priorities, verification recipes,
   dependencies, ownership scope, and preflight authorization with the user.
6. Refuse to start the first round until preflight is signed and valid.

Seed order and `source_stages` are provenance only. L0 MUST NOT synthesize a
fixed execution DAG from them.

### 3.2 Every round

1. Read unchecked checklist items.
2. Sort: reverted blockers first, then P0 → P1 → P2, then satisfied
   dependencies, then stable checklist order.
3. Select bounded items and partition them into at most 7 waves, at most
   5 tasks per wave.
4. Assign pairwise-disjoint writable ownership within each wave.
5. Dispatch each wave to L1.
6. Verify the aggregated evidence and checks against checklist item IDs.
7. Mark eligible checklist items complete; L2 never self-checks an item.
8. Evaluate the round gate:
   - every selected item has valid evidence and a passing check;
   - zero blocker findings;
   - composite score is recorded as trend-only context.
9. On FAIL, build up to 5 severity-filtered reinforcement rules for the next
   round. On PASS, checkpoint and select the next round.
10. Refresh progress state and report material changes to the user.

### 3.3 Completion and archive

L0 may archive only when every checklist item is checked, no reverted item is
open, evidence references validate, and readiness composite meets 8.5 for
lite/minor changes or 9.0 for full/major changes.

### 3.4 MUST NOT

- Implement task outputs, run implementation tests, or perform a delegated
  review.
- Treat seed presentation order as execution order.
- Advance a failed round by using a composite score as a substitute for
  checklist evidence.
- Change a signed checklist assertion or priority without user confirmation.
- Revert a checked item; `[x] → [ ]` belongs to the user.

L0 may update lifecycle-control artifacts such as `stage.md`, checklist state,
gate verdicts, and STATUS. Those are orchestration records, not task outputs.

## 4. L1 Wave Agent

L1 receives one bounded wave and coordinates its L2 tasks.

### 4.1 Dispatch contract

1. Validate every task has an ID, checklist item IDs, description,
   acceptance criteria, dependency state, owned files, read-only files,
   timeout, and output format.
2. Reject a wave with unresolved task dependencies or overlapping writable
   ownership.
3. Dispatch independent tasks in parallel. Sequential dependencies belong in
   different waves.
4. Apply explicit timeouts and bounded retry classification.

### 4.2 Aggregation contract

After all tasks settle, L1:

- records completion, failure, and escalation state per task;
- checks cross-task file and interface conflicts;
- preserves verbatim paths, errors, metric values, and command evidence;
- aggregates `ac_results` by checklist item ID;
- emits a lean WaveReport with an evidence-backed checklist proposal;
- never marks `checklist.md` itself and never alters task artifacts.

The evidence summary SHOULD remain within 600 tokens. Full evidence stays in
referenced artifacts.

### 4.3 Failure handling

L1 may retry a transient task once when the round budget permits. Deterministic
failure, ownership conflict, exhausted retry, or an unresolvable dependency is
reported to L0 with a classified `ExceptionEscalation`.

## 5. L2 Task Agent

L2 is the only implementation layer and always receives a fresh context.

1. Read the TaskDispatch and confirm scope before work.
2. Implement exactly the assigned atomic task.
3. Modify only `owned_files`; shared dependencies are read-only.
4. Run bounded self-verification against every assigned checklist assertion.
5. Report `ac_results` keyed by checklist item ID, command/metric evidence,
   artifacts, diff statistics, and unresolved findings.
6. Close applicable reinforcement before new work.
7. Emit a StatusReport on success, failure, or escalation.

L2 MUST NOT spawn subagents, modify lifecycle contracts, self-award a quality
score, mark checklist items complete, or write outside its owned set.

Typical task specializations:

| Type | Typical work | Required evidence |
|---|---|---|
| code/config | Implement scoped change | diff + bounded tests/lint |
| test/benchmark | Execute and record checks | command + exit status + metrics |
| review/security | Inspect artifacts | severity-classified findings |
| research/design/docs | Author scoped artifact | source/criteria self-check |

## 6. Delegation and Escalation

```text
Dispatch:   Project → Wave → Task
Reports:    Task → Wave → Project
Escalation: Task → Wave → Project → Human
```

Escalation always moves upward and never skips a layer. Every loop declares a
ceiling and classifies failure as retry, escalate, or abort.

| Constraint | Limit |
|---|---|
| Tasks per wave | 5 |
| Waves per round | 7 |
| Writable files per task | 6 |
| Readable files per task | 15 |
| Implementation task target | ≤30 minutes |
| Research/design task target | ≤45 minutes |
| Writable overlap inside a wave | Forbidden |

## 7. Evidence Handshake

The completion path is deliberately two-step:

```text
L2 StatusReport evidence
  → L1 validates and aggregates an item-level proposal
    → L0 verifies evidence and checks
      → L0 records checklist completion
```

This prevents self-certification. A Task may state that a command passed; it
cannot decide that the user contract is complete.

Minimum Task evidence:

- checklist item ID;
- verification mode and executed command or metric;
- exit status or measured value;
- artifact path and digest where applicable;
- self-check result;
- explicit unresolved or deferred findings.

## 8. Context and Message Boundaries

| Layer | Context contents |
|---|---|
| L0 Project | seed metadata, goal/checklist/preflight state, current round, prior WaveReports |
| L1 Wave | current task list, dependency map, ownership map, compact predecessor evidence |
| L2 Task | one task spec, owned/read-only files, applicable rules, relevant interfaces |

Use typed TaskDispatch, StatusReport, WaveReport, and ExceptionEscalation
messages. Paths are repository-relative. Preserve exact file paths, error
messages, metric values, and command output facts.

## 9. Active Change Layout

```text
.local/.agent/active/<change-id>/
├── goal.md
├── checklist.md
├── stage.md
├── preflight.md
├── spec.md
├── STATUS.yaml
├── owned_files.txt
└── evidence/
```

`stage.md` is a round-control artifact, not an agent layer. It records round
selection, wave partitioning, gate results, checkpoints, and priority changes.

## 10. Self-Audit

Before a cascade begins, confirm:

- L0 Project, L1 Wave, and L2 Task are the only active layers.
- All implementation work is assigned to L2.
- Context budgets are 5K/5K/8K.
- Every wave has at most 5 tasks and disjoint writable ownership.
- Every round has at most 7 waves.
- Evidence flows Task → Wave → Project before a checklist mark changes.
- Escalation is Task → Wave → Project → Human.
- No fixed workflow DAG was inferred from checklist-seed provenance.
