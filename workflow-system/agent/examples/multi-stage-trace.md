---
id: "agent/examples/multi-stage-trace"
version: "2.0.0"
purpose: >
  Standard/Complex walkthrough showing when multiple bounded waves are needed
  in the current Project → Wave → Task hierarchy. The filename is retained
  for link compatibility; stage agents are not part of the current runtime.
triggers:
  - "deciding whether multiple waves are necessary"
  - "cross-subsystem analysis"
  - "knowledge-graph merging across subsystems"
  - "Standard or Complex task with disjoint subsystems"
tier: 3
token_estimate: 2200
last_updated: "2026-08-25"
---

# Multi-Wave Trace for Cross-Subsystem Analysis

> The historical filename remains `multi-stage-trace.md` so existing links do
> not break. Current execution has no Stage Agent.

## Historical Compatibility Note

The v10.5.0 layer-usage audit documented a four-layer
Project → Stage → Wave → Task model and frequent L0-to-leaf collapse. Those
terms are archived semantics, not current instructions. The current required
STANDARD/COMPLEX cascade is:

```text
L0 Project → L1 Wave → L2 Task
```

Simple/trivial work may use a single bounded Task when the applicable
complexity contract allows it.

## Scenario

A repository has six stable subsystems: frontend, API, jobs, infrastructure,
documentation, and CLI. The user asks for bottleneck analysis across the
whole stack and one merged knowledge graph.

This is STANDARD+ because it is cross-cutting and spans many files. L0 selects
the `research-only` checklist seed for decomposition knowledge and the sole
`change-driven` runtime for execution.

## Materialized Checklist

```markdown
### G1: Produce evidence for every subsystem
- [ ] C-G1.1 (P0) Frontend bottlenecks have source-linked evidence.
- [ ] C-G1.2 (P0) API bottlenecks have source-linked evidence.
- [ ] C-G1.3 (P0) Job bottlenecks have source-linked evidence.
- [ ] C-G1.4 (P1) Infrastructure bottlenecks have source-linked evidence.
- [ ] C-G1.5 (P1) Documentation bottlenecks have source-linked evidence.
- [ ] C-G1.6 (P1) CLI bottlenecks have source-linked evidence.

### G2: Produce one consistent cross-system model
- [ ] C-G2.1 (P0) One merged graph deduplicates nodes and preserves source links.
      depends: [C-G1.1, C-G1.2, C-G1.3, C-G1.4, C-G1.5, C-G1.6]
```

The seed's `source_stages` may include historical analyze/merge labels. Their
order is presentation-only; the explicit `depends` field above creates the
actual execution constraint.

## Why One Task Is Insufficient

1. One Task would exceed the ~8K context budget when loading six subsystem
   contracts.
2. Independent subsystem analyses would lose available parallelism.
3. One prose result would hide per-subsystem evidence and weaken P5 artifact
   contracts.
4. The merged graph depends on all six source graphs, so analysis and merge
   cannot safely share one parallel wave.

## Round Plan

L0 partitions the selected items into three waves:

| Wave | Tasks | Purpose |
|---|---:|---|
| `R01_W01` | 3 | frontend, API, jobs analyses |
| `R01_W02` | 3 | infrastructure, docs, CLI analyses |
| `R01_W03` | 1 | merge six source graphs |

This is within 5 tasks per wave and 7 waves per round.

## Delegation Trace

```text
[L0 Project Agent · ~5K]
  Reads: goal.md, checklist.md, preflight.md, current stage.md
  Selects: C-G1.1..C-G2.1
  Partitions: R01_W01, R01_W02, R01_W03
  Dispatches one bounded wave at a time

      │
      ▼

[L1 Wave Agent · ~5K · R01_W01]
  Validates: three independent items, disjoint writable paths
  Dispatches:
    ├─ [L2 Task · ~8K] frontend → evidence/frontend-graph.json
    ├─ [L2 Task · ~8K] API      → evidence/api-graph.json
    └─ [L2 Task · ~8K] jobs     → evidence/jobs-graph.json
  Aggregates StatusReports → WaveReport

[L1 Wave Agent · ~5K · R01_W02]
  Dispatches:
    ├─ [L2 Task · ~8K] infra → evidence/infra-graph.json
    ├─ [L2 Task · ~8K] docs  → evidence/docs-graph.json
    └─ [L2 Task · ~8K] CLI   → evidence/cli-graph.json
  Aggregates StatusReports → WaveReport

[L0 Project Agent]
  Verifies C-G1.1..C-G1.6 evidence and records eligible marks
  Confirms C-G2.1 dependencies are satisfied

[L1 Wave Agent · ~5K · R01_W03]
  Dispatches one L2 merge Task
  Read-only: six source graphs
  Writable: evidence/knowledge-graph.json
  Aggregates merge evidence → WaveReport

[L0 Project Agent]
  Verifies merged graph and configured check
  Marks C-G2.1
  Records round PASS and checkpoint in stage.md
```

Tasks never exchange conversation state. The merge Task receives artifact
references and bounded key facts through its TaskDispatch.

## Ownership Map

| Task | Writable scope | Read-only scope |
|---|---|---|
| subsystem analysis | one subsystem evidence file | corresponding subsystem source |
| merge | `evidence/knowledge-graph.json` | six subsystem graph artifacts |

No two Tasks in the same wave share a writable file.

## Failure Example

If the API analysis times out:

```text
L2 reports TimeoutError evidence
  → L1 classifies and reports the failed Task
    → L0 applies the bounded retry or escalates
      → Human decides if the dependency cannot be resolved
```

The merge wave remains blocked until `C-G1.2` is checked. L0 does not infer a
workaround from seed order.

## Cost and Benefit

| Layer | Budget | Responsibility |
|---|---:|---|
| L0 Project | ~5K | checklist selection, wave partition, evidence adjudication |
| L1 Wave | ~5K | dependency/ownership validation, parallel dispatch, aggregation |
| L2 Task | ~8K each | one subsystem analysis or one merge |

The extra dispatches buy bounded context, parallel work, explicit evidence,
and deterministic dependency handling.

## Cross-References

- `references/agent-hierarchy.md` — current three-layer contracts.
- `references/decomposition-gate.md` — round/wave/task limits and evidence gate.
- `references/meta-framework.md` — seed provenance and sole runtime.
- `examples/full-pipeline-trace.md` — end-to-end checklist materialization.
- `docs/cycle-archive/v11.0.0/other/v10.5.1_layer_usage_audit.md` —
  explicitly historical four-layer audit evidence.
