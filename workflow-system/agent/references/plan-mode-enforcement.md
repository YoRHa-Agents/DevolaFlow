---
id: plan-mode-enforcement
version: "11.0.0"
purpose: >
  Plan-mode L0 contract for producing the entrance, goal, checklist, and
  preflight drafts; confirming priorities, verification, dependencies, and
  ownership; and handing the approved contract to the bounded checklist-round
  runtime.
tier: 2
token_estimate: 3000
last_updated: "2026-08-25"
---

# Plan-Mode Enforcement & Reinforcement Contract

## 1. When to Load

Load this reference when:

- the host says Plan Mode is active;
- the user asks to plan or design before execution;
- `DEVOLAFLOW_PLAN_MODE=1` or `.devolaflow_plan_mode` activates the runtime
  detector;
- L0 is building a later-round dispatch with reinforcement.

Plan Mode is an L0 Project activity. It designs the user contract but does not
execute it. L1/L2 may return bounded read-only research, but implementation
begins only after approval and valid preflight.

## 2. Detection and Runtime Overrides

Evaluate signals in this order:

1. host system message says Plan Mode is active;
2. the current Cursor mode is `plan`;
3. the user explicitly asks to plan/design first;
4. runtime env/marker detection;
5. otherwise use Agent Mode.

`select_context(plan_mode=True)` applies `_PLAN_MODE_OVERRIDES` from
`src/devolaflow/task_adaptive_selector.py`:

- `agent_hierarchy`, `decomposition_gate`, and
  `rationalization_prevention` become critical;
- `convergence_loop` becomes important;
- compression becomes minimal;
- `model_hint` becomes `quality`.

When no signal is present, no override is applied. The default Agent Mode
payload remains backward-compatible.

### 2.1 Agent obligations

| Layer | May do | MUST NOT |
|---|---|---|
| L0 | Produce drafts, inspect read-only evidence, ask user questions | Edit implementation files |
| L1 | Research and propose wave grouping when dispatched | Implement, mutate artifacts, call `AskQuestion` |
| L2 | Return bounded read-only research when dispatched | Implement, edit, call `AskQuestion`, or start hidden loops |

`AskQuestion` and `ExitPlanMode` are **L0 ONLY** host interactions. L1/L2 also
MUST NOT use unbounded `WebFetch` or `WebSearch`; return the need to L0 unless
an upstream timeout is explicit. If `ExitPlanMode` is unavailable, L0 says
the plan is ready and waits; it does not simulate approval.

## 3. Canonical Plan Output

Plan Mode produces four drafts: `entrance.md`, `goal.md`, `checklist.md`, and
`preflight.md`. `entrance.md` is the first-batch static router and artifact
inventory, not an execution plan or status mirror. It does not produce a fixed
stage DAG. `stage.md` is created or updated by L0 only when execution begins
and records actual round history.

Use the following output structure:

```text
# [Plan title]

## Overview
[1–2 sentences] | Complexity: [class] | Seed: [registered seed name]
Runtime: TemplateRegistry.load_template("change-driven")
Escalation: Task → Wave → Project → Human

## entrance.md draft
Purpose: static entry router, not an execution plan
Change: [goal title verbatim] (`goal.md`)
Routes: resume | new L2 task | review/verify | human audit → minimal artifact reads
Inventory: entrance, goal, checklist, stage, preflight, spec, STATUS, owned_files, evidence
Pointers: [rule IDs + repository-relative owning files]

## goal.md draft
Why: [problem and desired outcome]
Goals:
- G1: [verifiable outcome]
- G2: [verifiable outcome]
Out of scope:
- [explicit exclusion]

## checklist.md draft
### Progress
`[░░░…] 0%` — done 0 | doing 0 | todo N | total N (effort-weighted)

### G1: [goal title copied verbatim]
- [ ] C-G1.1 (P0) [assertion, <=25 words]
      verify: [bounded command or metric, or user-check]
      depends: []
      effort: [optional workload weight 1..8; default 1]
      owned_files: [repository-relative writable paths]
      read_only: [repository-relative dependencies]
- [ ] C-G1.2 (P1) [...]

### G2: [goal title copied verbatim]
- [ ] C-G2.1 (P2) [...]

## preflight.md draft
Project configuration: [detected values and inherited deltas]
Required decisions: [questions that materially affect execution]
Preauthorized blockers: [bounded actions the user allows]
Denied actions: [actions that always stop]
Verification environment: [commands, credentials state, services]
Authorization state: unsigned

## Execution handoff
Round selection: reverted blockers → P0 → P1 → P2 → stable order
Wave limits: <=5 tasks/wave; <=7 waves/round; writable ownership disjoint
Round PASS: selected items have valid evidence + passing checks + zero blockers
Composite: trend-only per round; archive threshold remains 8.5/9.0

## Constraints Checklist
- [ ] Every goal maps to one checklist section
- [ ] Every checklist item is an assertion, not an activity label
- [ ] Every item has P0, P1, or P2 priority confirmed by the user
- [ ] Every item has a bounded command, metric, or explicit user-check
- [ ] Dependencies use item-level `depends`; no fixed workflow DAG exists
- [ ] Every implementation item declares owned_files and read_only paths
- [ ] Parallel writable ownership is pairwise disjoint
- [ ] Task and round loops have explicit ceilings
- [ ] Predecessors are referenced by repository-relative artifact path
- [ ] Preflight is complete but unsigned until the user approves
```

### 3.1 Goal contract

- Number goals `G1`, `G2`, and so on.
- Keep each goal outcome-focused and verifiable.
- The goal-ID set must equal the checklist section-ID set.
- Preserve the user's wording where it expresses scope or acceptance intent.
- Keep explicit exclusions to prevent silent expansion.

### 3.2 Checklist contract

Each item needs:

| Field | Contract |
|---|---|
| ID | `C-G<n>.<n>`; stable inside the change |
| Priority | P0/P1/P2; advisory seed values require user confirmation |
| Assertion | Testable result, at most 25 words |
| Verify | Bounded command, measurable threshold, or explicit user-check |
| Depends | Item IDs only; empty when independent |
| Effort | Optional workload weight 1..8 (default 1); drives the pinned progress header |
| Owned files | Repository-relative writable scope |
| Read-only | Repository-relative context dependencies |

The scaffolded `checklist.md` pins a `## Progress` header directly under the
H1; the checklist-round runtime re-renders it on every state change and the
C-9 linter enforces byte alignment (`PROGRESS_HEADER`).

Seed partitions and `source_stages` help L0 discover likely assertions. Their
order is presentation-only and MUST NOT become an execution sequence.

### 3.3 Preflight contract

Preflight is the sole execution-before-confirmation surface. It combines:

- detected and inherited project configuration;
- only the configuration deltas needing user attention;
- required credentials/services without copying secrets;
- likely blockers and explicitly preauthorized responses;
- denied/destructive actions that always require a stop;
- verification commands and bounded timeouts;
- a signature/hash binding authorization to the presented content.

No round starts while `authorized_at` is absent, the authorization hash is
invalid, or the project configuration hash has drifted.

### 3.4 Intent and runtime selection

L0 matches intent to one of the 24 registry-v3 seed names:

```python
seed = registry.load_seed(seed_name)
runtime = registry.load_template("change-driven")
```

`load_seed()` provides declarative decomposition knowledge. Only
`load_template("change-driven")` provides executable lifecycle semantics.
Historical `load_template(seed_name)` calls are compatibility aliases; new
plans MUST use the explicit two-call form.

## 4. Plan Constraints Gate

Before presenting the plan, L0 verifies:

1. The four drafts (`entrance.md`, `goal.md`, `checklist.md`, `preflight.md`)
   are present and internally consistent.
2. The first-batch artifact set is complete: `entrance.md`, `goal.md`,
   `checklist.md`, `stage.md`, `preflight.md`, `spec.md`, `STATUS.yaml`,
   `owned_files.txt`, and `evidence/`.
3. Every goal has at least one checklist assertion.
4. Every checklist assertion has a confirmed priority and verification mode.
5. Every command verification has a bounded timeout.
6. Every dependency references an existing checklist item.
7. No dependency cycle blocks all remaining items. A cycle is an item-level
   contract error, not a reason to recreate a workflow DAG.
8. Writable ownership is declared and can be partitioned without parallel
   overlap.
9. Round capacity can fit within 5 tasks per wave and 7 waves per round.
10. Every loop has a maximum.
11. All paths are repository-relative.
12. Preflight clearly distinguishes preauthorized actions from mandatory
    human stops.
13. No seed field is treated as an executable instruction.

A failed item blocks plan handoff and requires plan revision.

### 4.1 `CASCADE_REQUIRED` three-layer contract

STANDARD and COMPLEX work returns `CASCADE_REQUIRED`. Set
`gate.cascade_required: true` and `gate.cascade_min_layers: 3` (default 3),
then traverse:

```text
L0 Project → L1 Wave → L2 Task
```

A claimed cascade without L1 is a violation. SIMPLE/TRIVIAL work returns
`CASCADE_OPTIONAL`; only the documented single-file, under-20-line trivial
waiver may collapse dispatch.

## 5. DO and DO NOT

### 5.1 DO

- Use read-only planning tools to inspect the codebase and workspace.
- Present material uncertainty and decisions to the user.
- Route intent through `load_seed()` and use only the `change-driven` runtime.
- Include P0/P1/P2, verify, depends, owned files, and read-only files.
- Prefer item-level dependencies over prescribed task order.
- Cite artifacts and sources by repository-relative path per S-2.
- Preserve exact paths, metrics, error text, and user constraints.
- Wait for explicit approval and signed preflight before execution.

### 5.2 DO NOT

- Do not implement, run implementation checks, or dispatch tasks in Plan Mode.
- Do not emit a stage-by-stage execution DAG.
- Do not execute checklist seeds or infer order from provenance.
- Do not assign priorities without presenting them for user confirmation.
- Do not leave verification as vague prose such as "works correctly."
- Do not copy full predecessor artifacts into the plan.
- Do not hide an unresolved blocker behind a high composite score.
- L1/L2 do not call `AskQuestion`, or unbounded `WebFetch`/`WebSearch`.

## 6. Feedback Ingestion

At Plan-Mode entry, L0 scans the workspace and reads up to the three newest
feedback files. It extracts concise themes and uses them to challenge scope,
terminology, and defaults in the four drafts.

### Automatic Ingestion at Plan-Mode Entry (v9.1.4+)

1. Call `devolaflow.workspace_context.scan_workspace(repo_root)`.
2. Read `WorkspaceContext.recent_feedbacks`; the public cap is
   `MAX_FEEDBACKS_RETURNED == 3`.
3. Use the standard `Read` tool for each returned path.
4. Extract ≤ 5 short themes, each ≤ 30 characters.
5. Surface them in
   `change_context.prior_feedback_themes`.
6. Cite sources with repository-relative POSIX paths per S-2, for example
   `.local/feedbacks/feedback_for_vX.Y.Z.md`.

Theme extraction is read-only and needs no new env flag. Memory-case
consultation remains separately gated by its existing runtime flag.

## 7. Reinforcement

When a round fails, L0 converts up to five prior findings into
`applicable_rules.reinforcement`.

```yaml
applicable_rules:
  reinforcement:
    - id: "R-001"
      severity: blocker
      finding: "verbatim prior-round finding"
      source_file: "repository/relative/path.py"
      remediation_hint: "bounded delta"
```

Selection order is blocker → critical → major, stable within severity. Minor
and informational findings stay informational. Deduplicate matching source
coordinates without paraphrasing facts.

A user-reverted checklist item becomes blocker reinforcement for the next
round. Its `finding` preserves the user's reason verbatim.

### 7.1 L2 obligation

An L2 Task receiving reinforcement MUST:

1. address every applicable item before new work;
2. report `closes_reinforcement` by ID;
3. report any unavoidable deferral with its dependency;
4. provide fresh verification evidence.

Failure to close or explicitly defer a rule is a blocker in L1 aggregation.

### 7.2 L0 caller responsibility

L0 owns gate evaluation and calls
`findings_to_reinforcement()` plus
`ProposalGenerator.generate_round_dispatch()`. Every emitted dispatch still
runs through `pre_dispatch` → `post_dispatch`. L1 forwards the resulting
task-scoped subset; it does not synthesize reinforcement policy.

## 8. Checklist-Round Loop

```text
L0 selects items and waves
  → L1 dispatches each wave's independent L2 tasks
    → L2 implements and self-verifies
      → L1 checks conflicts and aggregates evidence
        → L0 verifies and updates checklist state
          → round PASS, next round, or escalation
```

Round PASS requires all selected items to have valid evidence and passing
checks, plus zero blockers. Composite score is recorded in `stage.md` as a
trend signal; it is not a round-PASS condition.

After the preflight is signed and execution begins, W-30 applies: an ordinary
blocker or `HUMAN_INTERVENE` pauses only its affected item/task, while
independent siblings continue. Long-running external work must use a bounded
wait, progress heartbeat, and abandon/escalation path; safe dependency-ready
work should advance during the wait. Label paused work
`dependency-blocked`, `finding-blocked`, or `wave conflict`.

Termination:

- all checklist items checked and no reverted item open → archive gate;
- no net checklist progress for 2 consecutive rounds → escalate;
- one item fails in 3 selected rounds → escalate that item;
- `max_rounds` reached → escalate;
- schema, ownership, or preflight violation → abort or escalate by class.

The archive gate separately requires valid evidence references and readiness
composite ≥8.5 for lite/minor or ≥9.0 for full/major.

Task Quality Score is not part of this loop. After completion, the full rubric
loads on-demand from `references/task-quality-score.md` only when the user
asks; this path is **L0 ONLY**, and L1/L2 never emit scores.

## 9. Escalation

```text
L2 Task → L1 Wave → L0 Project → Human
```

| Class | Trigger | Action |
|---|---|---|
| retry | transient fault below retry ceiling | bounded redispatch |
| escalate | affected blocker, stagnation, dependency decision, exhausted limit | send upward while unaffected siblings continue |
| abort | ownership, schema, or destructive-policy violation | halt the required scope and report |

Whole-workflow stopping is permitted only when no task can be safely advanced,
or a HARD breakpoint, preflight STOP card, `FULL_ROLLBACK`, ownership
violation, or destructive-policy violation requires it. A wave conflict stops
only its conflicting partition; it is not an ordinary blocker-wide stop.

```yaml
exception_escalation:
  source_id: "<task_id|wave_id|round_id>"
  source_layer: "L0|L1|L2"
  reason: "stagnation|max_rounds|blocker|contract_violation|unrecoverable_error"
  classification: "retry|escalate|abort"
  context:
    round_n: 2
    checked_delta: 0
    blocker_findings: []
    last_dispatch_id: "..."
  remediation_hint: "one bounded next step"
```

No layer may skip its immediate parent.

## 10. Soul Rule S-10 Hook Chain

Every dispatch returned by
`ProposalGenerator.generate_round_dispatch()` must be visible to
`pre_dispatch` and `post_dispatch`.

| Slot | Responsibility |
|---|---|
| `pre_dispatch` | Validate acceptance criteria, owned files, schema, and prohibited score/banner leakage |
| `post_dispatch` | Permissive extension slot; default handler does not mutate bytes |

The chain runs on round-1 pass-through, no-reinforcement, and
reinforcement-applied paths. L2 does not manipulate dispatcher hooks.

## 11. Cross-References

- `references/agent-hierarchy.md` — three-layer responsibilities.
- `references/decomposition-gate.md` — round/wave/task decomposition and
  evidence gate.
- `references/context-isolation.md` — 5K/5K/8K context contracts.
- `references/artifact-quality.md` — L2 self-verification evidence.
- `schemas/lean-dispatch.yaml` — dispatch layout and reinforcement fields.
- `schemas/lean-report.yaml` — evidence and closure reporting.
