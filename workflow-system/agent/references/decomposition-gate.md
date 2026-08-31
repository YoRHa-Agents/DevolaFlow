---
id: "agent/references/decomposition-gate"
version: "1.0.0"
purpose: >
  Defines round → wave → task decomposition, priority and dependency
  selection, ownership-safe parallelism, evidence-based round gates,
  trend-only composite scoring, reinforcement, and bounded failure handling.
triggers:
  - "decomposing checklist work"
  - "evaluating round evidence"
  - "handling task or wave failures"
tier: 2
token_estimate: 3000
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-08-25"
---

# Decomposition & Gate Reference

## 1. Runtime Shape

The executable hierarchy is:

```text
checklist contract
  → bounded round
    → one or more waves
      → atomic tasks
```

Fixed workflow DAGs are retired. Checklist seeds may preserve historical
`source_stages`, but those records are non-executable provenance and their
order is presentation-only.

### 1.1 `CASCADE_REQUIRED`

STANDARD/COMPLEX work sets `gate.cascade_required: true` and
`gate.cascade_min_layers: 3` (default 3), then traverses
L0 Project → L1 Wave → L2 Task. A missing L1 hop is a contract violation.
SIMPLE/TRIVIAL work is `CASCADE_OPTIONAL`; only the documented single-file,
under-20-line trivial waiver may collapse the chain.

| Principle | Rule |
|---|---|
| Contract first | Every task traces to a signed checklist assertion |
| Monotonic granularity | Round → Wave → Task strictly narrows scope |
| Item dependencies | Dependencies use checklist item IDs, not workflow stages |
| Ownership safety | Parallel tasks have disjoint writable files |
| Evidence before completion | L0 checks Task evidence before marking an item |
| Bounded execution | Tasks, waves, retries, and rounds declare ceilings |
| Stable selection | Equal-priority items retain checklist order |

## 2. Checklist Item Readiness

A checklist item is selectable only when it has:

- a stable ID such as `C-G1.2`;
- one measurable assertion of at most 25 words;
- user-confirmed P0, P1, or P2 priority;
- `verify.mode` of command, metric, or manual;
- a bounded verification command where command execution applies;
- item-level dependencies;
- writable `owned_files` and `read_only` references;
- no unresolved placeholder.

Example:

```yaml
checklist_item:
  id: C-G1.2
  priority: P0
  assertion: "Registry exposes exactly one executable template path"
  verify:
    mode: command
    command: "python -m pytest tests/test_template_change_driven.py -q"
    timeout_seconds: 300
  depends: [C-G1.1]
  owned_files:
    - workflow-system/agent/templates/registry.yaml
  read_only:
    - schemas/checklist-seed.schema.yaml
```

Manual verification is user-check-only. An agent cannot convert a manual item
to PASS by self-attestation.

## 3. Round Selection

L0 Project owns round selection and writes the result to `stage.md`.

### 3.1 Stable selection order

Sort unchecked items by:

1. user-reverted items, which carry blocker reinforcement;
2. P0 before P1 before P2;
3. dependencies satisfied before blocked items;
4. original checklist order.

Blocked items are skipped, not force-scheduled. L0 reports a dependency set
that leaves no selectable item.

### 3.2 Capacity and bounds

| Limit | Value |
|---|---|
| Tasks per wave | ≤5 |
| Waves per round | ≤7 |
| Tasks in a maximally partitioned round | ≤35 |
| Default round capacity | 5 items |
| Writable files per task | ≤6 |
| Read-only files per task | ≤15 |
| Implementation task target | ≤30 minutes |
| Research/design task target | ≤45 minutes |

Default `max_rounds` is:

```text
ceil(total_items / capacity_per_round) + 2
```

The user may change the proposed ceiling during preflight. Execution never
silently increments it.

### 3.3 Round record

```yaml
round_plan:
  round_id: R03
  selected_items: [C-G1.2, C-G2.1]
  deferred_blocked: [C-G3.1]
  waves: [W01]
  max_waves: 7
  prior_reinforcement: [R-002]
```

## 4. Wave Formation

L0 partitions selected items into waves. L1 Wave validates and dispatches one
wave at a time.

```text
1. Build item dependency and writable-ownership maps.
2. Exclude items whose `depends` entries are not checked.
3. Group up to 5 independent tasks.
4. Reject any writable-file intersection.
5. Put sequential dependencies or shared writable files in later waves.
6. Stop at 7 waves; defer remaining items to a later round.
```

Parallel read-only sharing is allowed. Interface dependencies must be
represented by an artifact or typed contract, not hidden conversation state.

Useful wave shapes:

| Shape | Use |
|---|---|
| fan-out | Independent files or research axes |
| sequential | Item B consumes Item A's artifact |
| generator-verifier | Independent verification is required |
| hybrid | Independent partitions fan out; dependent integration follows |

The shape is derived from the selected checklist items. It is not loaded from
a seed DAG.

## 5. Task Definition

Each L2 Task receives one atomic assignment:

```yaml
task_definition:
  task_id: R03_W01_T02
  checklist_items: [C-G1.2]
  type: code
  title: "Enforce one executable template path"
  description: "Implement only the registry-path assertion."
  acceptance_criteria:
    - id: C-G1.2
      assertion: "Registry exposes exactly one executable template path"
      verification: "bounded command from checklist"
  scope:
    owned_files: []
    read_only: []
  dependencies:
    checklist_items: [C-G1.1]
    artifacts: []
  timeout_seconds: 1800
  max_retries: 1
  output_format: StatusReport
```

### 5.1 Sizing

Decompose further when a task:

- spans distinct concerns or subsystems;
- has internal sequential dependencies;
- needs more than 6 writable files;
- is expected to exceed its time target;
- produces unrelated artifact types;
- cannot be verified with one coherent evidence bundle.

Do not split a cohesive small change merely to fill a wave.

### 5.2 Intra-task convergence and self-verification

For implementation-class `code`, `test`, or `config` tasks with non-empty
`acceptance_criteria_v2`, dispatch populates
`gate.intra_task_convergence: true` and `gate.intra_task_max_rounds: 2`.
L2 runs:

```text
implement → review → fix → re-review
```

Each loop is bounded by `intra_task_max_rounds`; exhaustion escalates instead
of silently passing. Before reporting, L2:

1. runs each assigned command or metric check within its timeout;
2. records item-level verdicts and raw fact digests;
3. performs the applicable artifact-quality self-check;
4. reports changed files and unresolved findings;
5. closes or explicitly defers reinforcement IDs.

L2 reports evidence, never a self-awarded quality score and never a checklist
mark.

## 6. Evidence Aggregation

### 6.0 Stagnation detection (v9.6.0)

The v9.6.0 integration with
<https://github.com/gsd-build/get-shit-done> established two signals that
remain current under checklist rounds:

- **Score stagnation**: the recorded quality trend does not improve for two
  reinforced rounds.
- **Issue-count stagnation**: the number of open blocker/critical findings
  does not decrease for two reinforced rounds.

Either signal causes L0 to stop automatic repetition and escalate
Task → Wave → Project → Human. The external source's phase labels are
historical taxonomy; DevolaFlow records the signal in `stage.md`.

L1 waits for all wave tasks to settle, then:

- validates task IDs and checklist coverage;
- checks writable and interface conflicts;
- preserves exact paths, error messages, commands, exit codes, and metrics;
- groups `ac_results` by checklist item ID;
- identifies missing, contradictory, or stale evidence;
- sends L0 a lean evidence proposal.

Example proposal:

```yaml
wave_report:
  wave_id: R03_W01
  state: completed
  checklist_proposals:
    - id: C-G1.2
      verdict: pass
      evidence_refs:
        - .local/.agent/active/example/evidence/R03_W01_T02.yaml
  blockers: []
  conflicts: []
```

L1 cannot edit Task output or mark checklist state.

## 7. Round Gate

L0 evaluates the gate after all waves in the round complete.

### 7.1 PASS conditions

All are required:

1. every selected checklist item has valid evidence;
2. every selected item's configured check passes;
3. all applicable reinforcement is closed or explicitly accepted by the user;
4. zero blocker findings;
5. no unresolved cross-task ownership or interface conflict.

The checklist-evidence decision is the primary signal.

### 7.2 Composite is trend-only

Existing quality dimensions may still produce a composite:

```text
test_quality × 0.30
+ code_review × 0.30
+ architecture × 0.20
+ benchmark × 0.20
```

When user-facing verification exists, its configured dimensions may be
included by the current scorer. L0 records the result in `stage.md` so the
user can see quality direction.

When L0 supplies lean StatusReports through
`evaluate_gate(artifact_evidence=...)`, the profile's
`artifact_evidence_weight` shifts the composite by
`weight × (mean_composite − 50)`. Defaults are `0.05` for
STRICT/STANDARD/AUDIT and `0.0` for RELAXED. Missing evidence is an
absence-safe no-op; L2 never authors the score.

Composite score is **not** a round-PASS threshold. A high score cannot replace
missing item evidence, and a low score alone cannot fail an otherwise valid
round. A declining trend is reported and may motivate a user-approved
checklist or priority change.

### 7.3 FAIL behavior

- Missing/failed evidence with budget remaining → reinforce and schedule a
  later round.
- W-30(b): after signed preflight, an ordinary blocker or `HUMAN_INTERVENE` pauses only its affected item/task; continue independent, unaffected siblings. Label `dependency-blocked`, `finding-blocked`, or `wave conflict`; a wave conflict pauses its partition, not unrelated ready work. Whole-workflow stop requires no safely runnable task, or a HARD breakpoint, preflight STOP card, `FULL_ROLLBACK`, ownership violation, or destructive-policy violation.
- Zero net checklist progress for 2 rounds → escalate.
- Same item selected and not completed for 3 rounds → item-level escalation.
- `max_rounds` reached → escalate to the user.

## 8. Archive Gate

Archive remains stricter than a round gate. All are required:

- every checklist item checked;
- no user-reverted item open;
- every evidence reference exists and validates;
- signed preflight remains valid;
- source-of-truth mergeability checks pass;
- readiness composite ≥8.5 for lite/minor changes;
- readiness composite ≥9.0 for full/major changes.

The 8.5/9.0 archive threshold protects source-of-truth mutation. It does not
restore composite scoring as a per-round PASS condition.

## 9. Reinforcement

After a failed round, L0 selects at most five findings:

```text
blocker → critical → major
```

The next TaskDispatch carries them under
`applicable_rules.reinforcement`. User-reverted items enter as blockers with
the user's reason preserved verbatim.

L2 handles reinforcement before new work and reports closure IDs. L1 validates
closure evidence. L0 decides whether the checklist item may be marked.

## 10. Failure and Escalation (W-30(a))

```text
L2 Task → L1 Wave → L0 Project → Human
```

| Scope | Examples | Default response |
|---|---|---|
| Task | transient command failure | retry once if authorized |
| Task | deterministic failure, scope mismatch | report to Wave |
| Wave | ownership conflict, contradictory evidence | pause conflicting partition; report to Project and continue unrelated ready work |
| Round | blocker, stagnation, exhausted item retries | reinforce or escalate |
| Project | invalid preflight, scope decision, archive failure | human decision |

Every response is classified as retry, escalate, or abort. No retry counter is
raised automatically. Long-running external work (CI, installation, long tests, deployment) requires a timeout, progress heartbeat, and abandon/escalation path; advance ready work when dependencies, resources, and ownership permit instead of idle or meaningless polling.

## 11. Validation Checklist

```text
ROUND
□ Selection order follows reverted → P0 → P1 → P2 → stable order
□ Blocked dependencies are not scheduled
□ No more than 7 waves
□ max_rounds is explicit

WAVE
□ No more than 5 tasks
□ Writable ownership is pairwise disjoint
□ Sequential dependencies are in later waves
□ Evidence aggregation covers every settled task

TASK
□ Checklist item IDs and assertions match the signed contract
□ Verification is bounded and executable, or explicitly manual
□ Writable files ≤6; read-only files ≤15
□ L2 self-verification evidence is present

GATE
□ Every selected item has evidence and a passing check
□ Reinforcement closure is accounted for
□ Zero blockers and zero unresolved conflicts
□ Composite is recorded as trend-only
□ Archive alone applies 8.5/9.0 readiness thresholds
```

## 12. Inline and Independent Verification

L2 self-verification is mandatory for every task. An independent verifier is
additional and is warranted for high-risk implementation, security,
cross-interface changes, or checks whose producer could easily miss a defect.

Low-risk research, design, and documentation tasks may use a bounded inline
self-review checklist when their acceptance criteria are structural and
machine-checkable. Inline review does not waive L1 evidence aggregation or
L0 checklist adjudication.
