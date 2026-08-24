---
id: "agent/examples/convergence-loop-trace"
version: "2.0.0"
purpose: >
  Checklist-round convergence example showing evidence-based PASS/FAIL,
  reinforcement, user-reverted items, bounded retries, and stagnation
  escalation without a fixed review-fix-test stage cycle.
triggers:
  - "How does the checklist-round loop work"
  - "Show me evidence reinforcement across rounds"
  - "What happens when progress stagnates"
tier: 3
token_estimate: 2200
last_updated: "2026-08-25"
---

# Checklist-Round Convergence Trace

## Current Runtime Shape

The sole `change-driven` runtime repeats bounded checklist rounds:

```text
L0 selects ready checklist items
  → partitions at most 7 waves
    → L1 dispatches at most 5 independent L2 Tasks per wave
      → L2 self-verifies and reports evidence
    → L1 validates conflicts and aggregates evidence
  → L0 adjudicates checklist marks and the round gate
```

There is no fixed eight-phase review → fix → test → fix cycle. Historical
workflow seeds may retain those stage names in `source_stages`, but the
current wave shape is derived from unchecked item dependencies, ownership,
priority, and evidence needs.

## Scenario

The FileSync implementation has four open assertions:

```markdown
- [ ] C-G1.1 (P0) All sync tests pass.
      verify: cargo test sync
      depends: []
- [ ] C-G1.2 (P0) Coverage is at least 80%.
      verify: coverage metric
      depends: [C-G1.1]
- [ ] C-G2.1 (P1) Review finds zero blocker or critical issues.
      verify: user-check of review evidence
      depends: []
- [ ] C-G2.2 (P1) Benchmarks stay within the recorded regression budget.
      verify: cargo bench --bench sync
      depends: [C-G1.1]
```

`stage.md` declares `max_rounds: 4`. The composite score is recorded for
trend visibility, not used as the round-PASS condition.

## Round 1 — Evidence Exposes Gaps

L0 selects `C-G1.1` and `C-G2.1`, then creates one wave with disjoint Tasks:

| Task | Checklist item | Result |
|---|---|---|
| `R01_W01_T01` | `C-G1.1` | 50/52 tests pass; two failures |
| `R01_W01_T02` | `C-G2.1` | zero blockers; two critical findings |

L1 emits this evidence proposal:

```yaml
wave_report:
  wave_id: R01_W01
  state: completed
  checklist_proposals:
    - id: C-G1.1
      verdict: fail
      evidence_refs:
        - .local/.agent/active/filesync/evidence/R01_W01_T01.yaml
    - id: C-G2.1
      verdict: fail
      evidence_refs:
        - .local/.agent/active/filesync/evidence/R01_W01_T02.yaml
  blockers: []
  conflicts: []
```

L0 does not check either item.

### Round 1 gate

```yaml
round_gate:
  round_id: R01
  selected_items: [C-G1.1, C-G2.1]
  evidence_valid: true
  passing_checks: []
  blockers: []
  verdict: FAIL
  composite_trend: 78.0
```

The FAIL is caused by failed configured checks, not by `78.0` being below a
legacy stage threshold.

## Reinforcement for Round 2

L0 converts the highest-severity findings into at most five rules:

```yaml
applicable_rules:
  reinforcement:
    - id: R-001
      severity: critical
      finding: "F001: unbounded retry loop in sync scheduler"
      source_file: "src/sync/scheduler.rs"
      remediation_hint: "bound retry attempts and preserve terminal error"
    - id: R-002
      severity: critical
      finding: "F002: query builder accepts unescaped path metadata"
      source_file: "src/storage/query.rs"
      remediation_hint: "use parameter binding"
```

Paths, IDs, and finding text remain verbatim. Each assigned L2 Task must close
or explicitly defer its reinforcement IDs before new work.

## Round 2 — Fix and Re-Verify

The two findings touch disjoint files, so L0 creates:

1. Wave 1: two parallel fix Tasks.
2. Wave 2: after the fix artifacts settle, one test Task and one independent
   review Task.

This uses two of the seven allowed waves. Sequential dependencies are placed
in later waves instead of being hidden inside one parallel wave.

```yaml
round_gate:
  round_id: R02
  selected_items: [C-G1.1, C-G2.1]
  evidence_valid: true
  passing_checks: [C-G1.1, C-G2.1]
  reinforcement_closed: [R-001, R-002]
  blockers: []
  conflicts: []
  verdict: PASS
  composite_trend: 88.0
```

L0 checks `C-G1.1` and, after the configured manual user-check,
`C-G2.1`. It records the round, evidence references, and checkpoint in
`stage.md`.

`C-G1.2` and `C-G2.2` become selectable because `C-G1.1` is now checked.

## User-Reverted Item

Suppose the user reopens `C-G2.1`:

```markdown
- [ ] C-G2.1 (P1) Review finds zero blocker or critical issues.
      reverted: "The Windows-path review omitted junction handling."
```

The next round selects the reverted item before ordinary P0/P1/P2 work and
injects the reason verbatim as blocker reinforcement. L0 may not undo the
reopen or silently weaken the assertion.

## Stagnation

Checklist progress, not score movement alone, drives stagnation:

```text
Round 1: checked_delta = 0 → continue with reinforcement
Round 2: checked_delta = 0 → escalate; two consecutive stagnant rounds
```

One item that fails in three selected rounds also escalates. Reaching
`max_rounds` escalates. Execution never increments a ceiling silently.

```yaml
exception_escalation:
  source_id: R02
  source_layer: L0
  reason: stagnation
  classification: escalate
  context:
    checked_delta: 0
    stagnant_rounds: 2
    open_items: [C-G1.1, C-G2.1]
    blocker_findings: []
  remediation_hint: "Choose one scope or dependency change before another round"
```

## Completion

After later rounds check `C-G1.2` and `C-G2.2`, L0 enters the archive gate.
Archive still requires every item checked, valid evidence, valid signed
preflight, no open reversion, and readiness composite 8.5/9.0. The archive
threshold does not become a per-round gate.

## Dispatcher Isolation

- L0 Project selects items, writes round state, and adjudicates evidence.
- L1 Wave validates dependencies/ownership and aggregates Task reports.
- L2 Task performs the scoped fix, test, review, research, or document work.
- Evidence flows Task → Wave → Project.
- Escalation flows Task → Wave → Project → Human.
