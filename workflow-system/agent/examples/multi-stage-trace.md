---
id: "agent/examples/multi-stage-trace"
version: "1.0.0"
purpose: >
  Worked walkthrough showing WHEN the L1 Stage Agent and L2 Wave Agent
  are necessary in DevolaFlow's 4-layer hierarchy. The v10.5.0 PV-01
  D-A-1 audit (`scripts/audit_layer_usage.py`) shows that most v9.x
  and v10.x cycles collapse L0->L3 in practice; this example documents
  the COUNTER-CASE — a multi-team analyze stage with cross-stage
  artifact merging where the standalone L1 + L2 layers genuinely earn
  their cost.
triggers:
  - "deciding whether L1 + L2 layers are necessary"
  - "multi-team / cross-subsystem analyze stage"
  - "knowledge-graph merging across subsystems"
  - "Standard / Complex tier with > 3 disjoint subsystems"
tier: 3
token_estimate: 5500
last_updated: "2026-05-08"
---

# Multi-Stage Trace — When L1 Stage Agent + L2 Wave Agent Earn Their Keep

> Companion to `references/agent-hierarchy.md` and the
> `examples/full-pipeline-trace.md` walkthrough. Cross-references the
> `meta-framework.md` §2.2.1 Multi-team codebase analysis pattern.

## Why this example exists

The v10.5.0 PV-01 D-A-1 audit
(`docs/cycle-archive/v11.0.0/other/v10.5.1_layer_usage_audit.md`)
measured how often the L1 Stage Agent and L2 Wave Agent were
dispatched as the primary target across `.local/research/v9.*.0_*.md`
and `v10.*.0_*.md` cycle docs. The headline finding was that 5 of
6 PVs in v10.2.0 were dispatched as `Dispatch type: Wave` but each
collapsed to L0 → single L3 in practice — leading the v10.5.0 PV-01
advisory to mark L1+L2 as "only-when-needed" at the Standard tier.

The v11.1.0 cascade-restoration cycle (per the user feedback at
`.local/feedbacks/feedback_for_v11.0.0.md`) reverses that advisory:
**for STANDARD/COMPLEX complexity, the full L0 → L1 → L2 → L3
cascade is REQUIRED** per `cascade_requirement(complexity)`
(`src/devolaflow/skills/change_activation.py`). The example below
is therefore the WORKED CANONICAL pattern operators apply on every
STANDARD+ task, not the counter-case to a default.

L0→L3 collapse is reserved for SIMPLE/TRIVIAL tier per
`cascade_requirement()` returning `"CASCADE_OPTIONAL"`.

## The scenario — multi-team codebase analysis

Setup: a 6-subsystem repo (frontend + backend-api + backend-jobs +
infra + docs + cli). The user asks "where are the bottlenecks across
the whole stack — frontend rendering, backend latency, cron-job
scheduling, deploy lead time"?

This is a Standard-tier task by the SKILL.md classifier
(`change_activation.classify_complexity(files_count=~30,
loc_estimate=~0, is_cross_cutting=True)` -> `STANDARD`). Per the
advisory wording added in v10.5.0, an operator might be tempted to
collapse L0 -> L3 with a single all-encompassing analyze prompt. This
example shows why that collapse is the wrong call here.

## Why a single L3 analyze fails this scenario

A single L3 Task Agent dispatched with "analyze the bottlenecks
across the whole stack" runs into 3 hard limits:

1. **Token budget**: each subsystem is ~ 30-50 KLOC. Loading them
   all into one L3 context blows past the ~8K token L3 budget per
   `references/agent-hierarchy.md`. The L3 must either skip
   subsystems or summarize aggressively, losing fidelity.
2. **Parallelism wasted**: subsystems are independent. A linear
   single-L3 walk of all 6 subsystems takes 6x as long as 6
   parallel L3 analyses.
3. **No artifact discipline**: the single L3's output is one big
   prose blob — there's no per-subsystem knowledge-graph artifact
   the downstream Design / Implement stages can consume per
   `meta-framework.md` §P5 Artifacts as Contracts.

## Why L0 -> L1 -> L2 -> L3 succeeds

The 4-layer chain decomposes the problem into shape that fits each
layer's budget:

```
[L0 Project Agent]
  Receives: "analyze bottlenecks across the whole stack"
  Reads: SKILL.md + references/meta-framework.md + repo manifest
  Decides: this needs the analyze primitive with multi-team merge
  Dispatches: 1x L1 Stage Agent for the analyze stage

      |
      v

[L1 Stage Agent — analyze stage]
  Receives: stage definition + 6 subsystem boundaries
  Reads: meta-framework.md §2.2.1 (multi-team analyze pattern)
  Decides: parallelize across 6 subsystems then merge
  Dispatches: 1x L2 Wave Agent for the parallel-analyze wave
                + 1x L2 Wave Agent for the merge wave (sequential)

      |
      v

[L2 Wave Agent — parallel-analyze wave]
  Receives: 6 disjoint subsystem targets
  Decides: max 5 tasks per wave (P3 wave constraint),
           split into 2 waves of 3 + 3
  Dispatches: 6x L3 Task Agent in 2 parallel waves

      |    |    |    |    |    |
      v    v    v    v    v    v

  [L3]  [L3]  [L3]  [L3]  [L3]  [L3]
  fe    api   jobs  infra docs  cli

  Each L3 Task Agent:
    Owned files: <subsystem>/  + tests/<subsystem>/
    Read-only:   the rest
    Output:      <subsystem>-knowledge-graph.json artifact
                 (frozen-shape per the Phase 0 step 4 pattern from
                  https://github.com/Lum1104/Understand-Anything)

      |    |    |    |    |    |
      v    v    v    v    v    v

[L2 Wave Agent — merge wave]
  Receives: 6 per-subsystem knowledge graphs
  Decides: dispatch a single L3 for the merge (no parallelism here)
  Dispatches: 1x L3 Task Agent

      |
      v

[L3 Task Agent — merge]
  Owned files: knowledge-graph.json
  Read-only:  6 per-subsystem graphs
  Output:     one merged knowledge-graph.json with deduplicated
              nodes + edges (the upstream tool ships a 70-line
              merge-subdomain-graphs.py reference implementation)

      |
      v

[L1 Stage Agent — gate]
  Reads: knowledge-graph.json + per-subsystem graphs
  Runs:  gate composite check (>= 85, zero blockers)
  Reports up to L0

      |
      v

[L0 Project Agent — final report]
  Composite gate passed
  Reports to user with the merged knowledge-graph.json artifact
  Task Quality Score: append
```

## Counting the work — why 4 layers is justified

Layer-by-layer cost:

| Layer | Dispatches | Token cost | Wall-clock | Justification |
|------|-----------|------------|-----------|----------------|
| L0 | 1 (workflow selection) | ~3K | < 1 min | Selects analyze + multi-team merge pattern |
| L1 Stage | 1 (analyze stage) | ~5K | < 1 min | Sequences parallel-analyze -> merge -> gate |
| L2 Wave x 2 | 2 (parallel + merge) | ~4K each | < 1 min each | Wave constraints: 5 tasks max per wave; cross-task conflict checks |
| L3 Task x 7 | 6 parallel + 1 merge | ~8K each | 5-15 min each | Each subsystem analysis fits L3 budget |

Total dispatch overhead: **~33K tokens** across L0/L1/L2 layers. Versus
a single-L3 collapse that would need to load the entire stack into
one ~8K context — a 4x token-budget violation per layer. The 4-layer
chain trades **one-time dispatch overhead** for **massive context
isolation per L3** — every subsystem analysis is pristine, and the
merge stage consumes 6 well-defined artifacts rather than a single
"the whole stack" blob.

## When does this pattern apply?

Per `meta-framework.md` §2.2.1, the multi-team analyze pattern fires
when:

1. `len(targets) >= 3`, AND
2. The targets are themselves **logical subsystems with stable
   boundaries** (a frontend / backend split is stable; "this 3-file
   region of one module" is not).

In v10.x cycle docs, the audit found 0 such patterns — every cycle
in v9.x..v10.x was either:

- Single-team (refactor / hotfix / feature-enhancement),
- Or a documentation-only walk (research-only / migration-plan), or
- A cycle-rollup retrospective (W-7 / SI-8) — which is itself a
  single-stage analyze.

That is why the audit recommended marking L1 + L2 "only-when-needed"
at the Standard tier — but "only-when-needed" carries the support
set: when an operator does encounter a multi-team analyze stage, the
4-layer chain SHOULD fire.

## When NOT to use this pattern

Patterns that look multi-stage but are actually single-team in
disguise:

| Symptom | What's actually happening | Right answer |
|--------|---------------------------|---------------|
| 1. ≤3-file paired source+test edit + spec doc | 1 author, 1 task | Single L3 (TRIVIAL/SIMPLE tier; `cascade_requirement` returns `CASCADE_OPTIONAL`) |
| 2. Refactor across 8 modules in 1 package | Multi-file STANDARD+ scope | **Cascade L0→L1→L2→L3** (8 files = STANDARD per classifier; `cascade_requirement` returns `CASCADE_REQUIRED`); L1 Stage decomposes into per-package waves |
| 3. Bug investigation across ≤3 subsystems | 1 hypothesis test, not 3 parallel analyses | Single L3 trace + diagnose IFF SIMPLE-tier; STANDARD+ (cross-cutting investigation across many subsystems) **MUST cascade** |
| 4. "Audit X across the codebase" | STANDARD+ scope read-only walk | **Cascade L0→L1→L2→L3** when the audit spans STANDARD+ scope; the v10.5.1 audit itself was a single-L3 walk that produced 0 useful dispatch-line measurements per its own summary — that experience is the empirical case for cascading STANDARD+ audits |

## Cross-references

- `references/agent-hierarchy.md` §"4-Layer Agent Hierarchy" —
  canonical layer definitions + token budgets.
- `references/meta-framework.md` §2.2.1 — multi-team codebase
  analysis pattern (the upstream `understand-anything/skills/
  understand` Phase 0 step 4 reference).
- `examples/full-pipeline-trace.md` — single-team full-pipeline
  walkthrough (the contrast case).
- `examples/hotfix-trace.md` — single-team minimal-ceremony
  walkthrough (the SIMPLE-tier collapse case).
- `scripts/audit_layer_usage.py` — the v10.5.0 PV-01 audit that
  produced the empirical evidence.
- `.local/research/v10.5.1_layer_usage_audit.md` — the audit's
  output (gitignored; re-run via `make audit-layers` per the
  v10.5.0 Makefile target).

## Notes for future authors

If you find a real-world multi-team scenario in the DevolaFlow
codebase or in a downstream project, append a 1-paragraph case study
under "## Real-world cases" below. The audit will pick up the new
mention on the next run and the SKILL.md advisory wording can be
re-evaluated based on the empirical support.

## Real-world cases

(none yet — v10.5.0 PV-01 ships with the synthetic 6-subsystem
walkthrough above. The audit's recommendation is data-driven on the
current corpus; future cycles may surface concrete cases.)
