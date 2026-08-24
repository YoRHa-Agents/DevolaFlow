---
id: "agent/examples/hotfix-trace"
version: "2.0.0"
purpose: >
  Hotfix checklist-round trace for a critical Unicode path bug, showing how a
  hotfix seed materializes a compact contract without becoming a static
  triage-fix-test-release DAG.
triggers:
  - "Need a hotfix checklist example"
  - "How does hotfix delegation differ from full-pipeline"
  - "Show me a minimal checklist-round trace"
tier: 3
token_estimate: 1900
last_updated: "2026-08-25"
---

# Hotfix Checklist-Round Trace

## Scenario

The FileSync CLI corrupts files when a Windows target path contains non-ASCII
characters.

```text
Intent mode: hotfix
Seed: TemplateRegistry.load_seed("hotfix")
Runtime: TemplateRegistry.load_template("change-driven")
Severity: SEV2
Hierarchy: L0 Project → L1 Wave → L2 Task
```

The seed's historical triage/fix/test/release `source_stages` explain where
its assertions came from. They are provenance, not a required execution
sequence.

## Confirmed Contract

### `goal.md`

```markdown
# Unicode Path Hotfix

## Goals
- G1: Stop path corruption for supported Unicode path classes.
- G2: Prove the fix and produce release-ready evidence.

## Out of scope
- A general filesystem abstraction rewrite.
```

### `checklist.md`

```markdown
### G1: Stop path corruption for supported Unicode path classes
- [ ] C-G1.1 (P0) Root cause is reproduced with a failing regression test.
      verify: cargo test unicode_path_regression
      depends: []
- [ ] C-G1.2 (P0) Path handling preserves CJK, emoji, combining-mark, and RTL paths.
      verify: cargo test unicode_path_regression
      depends: [C-G1.1]

### G2: Prove the fix and produce release-ready evidence
- [ ] C-G2.1 (P0) The full test suite passes with no regression.
      verify: cargo test --all-targets
      depends: [C-G1.2]
- [ ] C-G2.2 (P1) Release notes describe the fixed behavior and evidence.
      verify: user-check
      depends: [C-G2.1]
```

L0 confirms the two P0 priorities and signs `preflight.md` with the user.

## Round 1 — Reproduce

```text
L0 selects C-G1.1
  → L1 Wave R01_W01
    → L2 Task: add one owned regression-test file and run it
    ← StatusReport: expected failing digest + test artifact
  ← WaveReport: C-G1.1 evidence proposal
L0 verifies the failure matches the reported corruption
  → checks C-G1.1
  → records round PASS in stage.md
```

The red test is positive evidence for this item because the signed assertion
requires reproduction before the fix.

## Round 2 — Fix

L0 selects `C-G1.2`. The implementation and test files share behavior and
must not be edited concurrently by separate Tasks, so L0 creates one cohesive
Task rather than forcing parallelism.

```yaml
hdr: { id: d-r02-w01-t01, parent: r02-w01, layer: wave, timeout: 600 }
task: { id: R02_W01_T01, type: code, title: "Fix Unicode path handling" }
goal: "Make C-G1.2 pass without filesystem redesign"
pred:
  - ref: ".local/.agent/active/unicode-path/evidence/R01_W01_T01.yaml"
    key_facts: ["unicode_path_regression failed before fix", "scope: sync_engine/path.rs"]
files:
  - "sync_engine/path.rs"
  - "tests/regression/unicode_path_test.rs"
rules: { strategy: minimal, lang: rust, focus: [correctness, surgical-scope] }
accept:
  - "Unicode regression cases pass"
  - "no unrelated path abstraction added"
gate: { blockers: 0, retries: 1 }
change_context:
  change_id: unicode-path
  active_folder: ".local/.agent/active/unicode-path"
  state: IN_PROGRESS
  owned_files_ref: ".local/.agent/active/unicode-path/owned_files.txt"
  acceptance_ref: ".local/.agent/active/unicode-path/checklist.md#C-G1.2"
```

The L2 Task self-verifies, reports exact test output, and does not mark the
checklist. L1 checks ownership and aggregates; L0 adjudicates and checks
`C-G1.2`.

## Round 3 — Verification and Release Notes

After the fix item passes, L0 selects `C-G2.1` and `C-G2.2`. They can run in
one wave because their writable scopes are disjoint:

| Task | Work | Writable scope |
|---|---|---|
| `R03_W01_T01` | Run full suite and record evidence | evidence file only |
| `R03_W01_T02` | Draft release-note delta | `CHANGELOG.md` |

The user-check for `C-G2.2` remains open until the operator approves the
wording. An agent cannot self-attest a manual verification.

## Failure Path

If the fix fails after the single authorized retry:

```text
L2 Task → L1 Wave → L0 Project → Human
```

The escalation preserves the failing command digest, affected checklist item,
and one bounded remediation option. No layer skips its immediate parent.

## Hotfix vs Full-Pipeline Seed

| Dimension | Hotfix seed | Full-pipeline seed |
|---|---|---|
| Typical goal breadth | One urgent defect | End-to-end product outcome |
| Suggested checklist | Reproduce, fix, regress, release evidence | Design, build, integrate, verify, release evidence |
| Runtime | `change-driven` | `change-driven` |
| Executable seed DAG | None | None |
| Round bounds | Explicit in `stage.md` | Explicit in `stage.md` |
| Hierarchy | Project → Wave → Task | Project → Wave → Task |

Ceremony differs because the materialized checklist differs. The runtime,
budgets (5K/5K/8K), wave/round limits, ownership, evidence, and escalation
contracts remain identical.
