---
id: "agent/examples/full-pipeline-trace"
version: "2.0.0"
purpose: >
  End-to-end example showing how the full-pipeline checklist seed becomes a
  signed goal/checklist contract and runs through the sole change-driven
  runtime using Project, Wave, and Task agents.
triggers:
  - "Need a full-pipeline checklist-round example"
  - "How does delegation work end-to-end"
  - "Show me a complete three-layer trace"
tier: 3
token_estimate: 2800
last_updated: "2026-08-25"
---

# Full-Pipeline Checklist-Round Trace

## Scenario

A user requests a Rust CLI for bidirectional file synchronization.

```text
Intent mode: full-pipeline
Seed: TemplateRegistry.load_seed("full-pipeline")
Runtime: TemplateRegistry.load_template("change-driven")
Hierarchy: L0 Project → L1 Wave → L2 Task
Budgets: ~5K / ~5K / ~8K tokens
```

The full-pipeline seed contributes decomposition knowledge. Its
`source_stages` retain historical design/plan/implement/review/test/release
labels as provenance only; they do not prescribe an execution DAG.

## Contract Materialization

L0 resolves the seed and drafts the active-change artifacts:

```text
.local/.agent/active/filesync-cli/
├── goal.md
├── checklist.md
├── stage.md
├── preflight.md
├── spec.md
├── STATUS.yaml
├── owned_files.txt
└── evidence/
```

`stage.md` is a round-control artifact, not an agent layer. Before execution,
L0 confirms priorities, verification, dependencies, ownership, and preflight
authorization with the user.

### `goal.md` excerpt

```markdown
# FileSync CLI

## Goals
- G1: Deliver a buildable CLI with documented sync behavior.
- G2: Prove correctness, compatibility, and release readiness.

## Out of scope
- Remote cloud storage providers.
- Background daemon mode.
```

### `checklist.md` excerpt

```markdown
### G1: Deliver a buildable CLI with documented sync behavior
- [ ] C-G1.1 (P0) Architecture defines config, sync, storage, and error interfaces.
      verify: user-check against the design contract
      depends: []
- [ ] C-G1.2 (P0) Core modules compile and expose the approved interfaces.
      verify: cargo build --locked
      depends: [C-G1.1]
- [ ] C-G1.3 (P1) CLI wires config, sync, and storage without unsafe code.
      verify: cargo clippy --all-targets -- -D warnings
      depends: [C-G1.2]

### G2: Prove correctness, compatibility, and release readiness
- [ ] C-G2.1 (P0) Unit and integration suites pass with coverage at least 80%.
      verify: cargo test --all-targets
      depends: [C-G1.3]
- [ ] C-G2.2 (P1) Review finds zero blocker issues.
      verify: user-check of severity-classified review evidence
      depends: [C-G1.3]
- [ ] C-G2.3 (P2) Release artifacts and changelog are complete.
      verify: cargo package --allow-dirty
      depends: [C-G2.1, C-G2.2]
```

Seed-suggested priorities remain advisory until the user confirms them.

## Round 1 — Design Contract

L0 selects `C-G1.1` and creates one wave.

```text
L0 Project
  → L1 Wave R01_W01
    → L2 Task R01_W01_T01: author architecture artifact
    ← StatusReport: design path + self-check + unresolved decisions
  ← WaveReport: evidence proposal for C-G1.1
L0 verifies the manual user-check
  → marks C-G1.1 complete
  → records round PASS and checkpoint in stage.md
```

The Task may report evidence; it cannot mark the checklist item.

## Round 2 — Parallel Core Build

`C-G1.2` is now ready. L0 partitions four independent module tasks into one
wave. Writable ownership is pairwise disjoint.

| Task | Writable scope | Read-only contract |
|---|---|---|
| `R02_W01_T01` | `src/config/**`, `tests/config/**` | architecture artifact |
| `R02_W01_T02` | `src/sync/**`, `tests/sync/**` | architecture artifact |
| `R02_W01_T03` | `src/storage/**`, `tests/storage/**` | architecture artifact |
| `R02_W01_T04` | `src/error.rs`, `tests/error.rs` | architecture artifact |

```text
L0 Project → L1 Wave R02_W01
                 ├─→ L2 T01 ─→ StatusReport
                 ├─→ L2 T02 ─→ StatusReport
                 ├─→ L2 T03 ─→ StatusReport
                 └─→ L2 T04 ─→ StatusReport
              ← WaveReport: conflicts=[], C-G1.2 evidence proposal
L0 runs evidence adjudication → C-G1.2 checked → round PASS
```

The wave remains within the hard limit of 5 tasks. A round may contain at
most 7 waves.

## Round 3 — Integration, Test, and Review

L0 derives execution order from checklist dependencies, not seed order:

1. Wave 1: one integration Task for `C-G1.3`.
2. Wave 2: after integration evidence passes, parallel test and review Tasks
   for `C-G2.1` and `C-G2.2`.

The second wave is valid because test and review are independent and have no
overlapping writable files.

### Lean TaskDispatch

```yaml
hdr: { id: d-r03-w02-t01, parent: r03-w02, layer: wave, timeout: 900 }
task: { id: R03_W02_T01, type: test, title: "Verify FileSync suites" }
goal: "Prove C-G2.1 with bounded test and coverage evidence"
pred:
  - ref: ".local/.agent/active/filesync-cli/evidence/R03_W01_T01.yaml"
    key_facts: ["cargo clippy exit 0", "CLI wiring complete"]
files: ["tests/**"]
rules: { strategy: standard, lang: rust, focus: [correctness, coverage] }
accept:
  - "cargo test --all-targets exits 0"
  - "coverage >= 80%"
gate: { coverage: 80, blockers: 0, retries: 1 }
change_context:
  change_id: filesync-cli
  active_folder: ".local/.agent/active/filesync-cli"
  state: IN_PROGRESS
  owned_files_ref: ".local/.agent/active/filesync-cli/owned_files.txt"
  acceptance_ref: ".local/.agent/active/filesync-cli/checklist.md#C-G2.1"
```

### Lean StatusReport evidence

```yaml
hdr: { id: r-r03-w02-t01, dispatch_id: d-r03-w02-t01, task_id: R03_W02_T01, layer: task }
status: { state: completed, progress_pct: 100, elapsed: 412 }
result:
  metrics: { tests_passed: 59, tests_failed: 0, coverage_pct: 83.1 }
issues: { blockers: [], warnings: [], deferred: [] }
ac_results:
  - { id: C-G2.1, verdict: pass, cmd_digest: "59 passed; coverage 83.1%" }
diff_stats: { files: 1, insertions: 24, deletions: 2 }
```

L1 preserves exact commands, values, and paths when aggregating. L0 checks
the evidence before changing checklist state.

## Round 4 — Release Evidence

After `C-G2.1` and `C-G2.2` are checked, `C-G2.3` becomes selectable. One
release Task prepares the package and changelog. Publication still requires
the relevant human authorization; a Task cannot infer it from seed metadata.

## Completion and Archive

L0 archives only when:

- all six checklist items are checked;
- no user-reverted item remains open;
- every evidence reference validates;
- signed preflight is still valid;
- the archive readiness composite meets 8.5 for lite/minor or 9.0 for
  full/major changes.

Per-round composite scores are trend context only. They never replace
item-level evidence as the round-PASS signal.

## Invariants Demonstrated

- Only L2 Tasks implement, test, review, research, or author deliverables.
- Context budgets are Project 5K, Wave 5K, Task 8K.
- Each wave has at most 5 tasks with disjoint writable ownership.
- Each round has at most 7 waves.
- Evidence flows Task → Wave → Project.
- Escalation flows Task → Wave → Project → Human.
- `goal.md`, `checklist.md`, `stage.md`, `preflight.md`, and `evidence/`
  remain the durable execution contract.
- Seed order and historical `source_stages` remain non-executable provenance.
