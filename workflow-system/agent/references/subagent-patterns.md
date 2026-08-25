---
id: subagent-patterns
version: "2.0.0"
purpose: >
  Selects an agent-to-agent dispatch shape for the current
  Project→Wave→Task hierarchy while preserving the external four-pattern
  taxonomy and DevolaFlow's artifact-isolation invariants.
triggers:
  - "choosing inline versus parallel Task dispatch"
  - "evaluating persistent-worker requests"
  - "explaining why agent teams are unsupported"
tier: 2
token_estimate: 2200
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-08-25"
---

# Subagent Patterns

## 1. Scope

This reference maps Phil Schmid's external 2026 taxonomy—**Inline Tool**,
**Fan-Out**, **Agent Pool**, and **Teams**—onto DevolaFlow's current
L0 Project → L1 Wave → L2 Task hierarchy.

Upstream taxonomy:
<https://www.philschmid.de/subagent-patterns-2026>

The pattern answers: “How should agents dispatch this work?” It does not
select checklist content, workflow intent, or a model.

### Disambiguation from grill mode

`grill-mode.md` governs HUMAN-facing clarification. Subagent-pattern
selection governs AGENT-to-AGENT dispatch shape. They are orthogonal:
grill an ambiguous plan, then select Inline or Fan-Out for its ready items.

## 2. Current Mapping

| External pattern | DevolaFlow mapping | Status |
|---|---|---|
| 1. Inline Tool | L1 Wave dispatches one fresh L2 Task | Native |
| 2. Fan-Out | L1 Wave dispatches 2–5 independent L2 Tasks, then synchronizes | Native |
| 3. Agent Pool | Persistent workers with private state | Forward-compat verdict only |
| 4. Teams | Shared state / direct cross-agent messaging | Permanently forbidden by P5 |

Each checklist round has at most 7 waves. Each wave has at most 5 Tasks with
pairwise-disjoint writable ownership. Every L2 Task receives a fresh,
bounded context of approximately 8K tokens.

## 3. Public Selection API

```python
PatternVerdict = Literal[
    "INLINE",
    "FAN_OUT",
    "AGENT_POOL_FORWARD",
    "TEAMS_FORBIDDEN",
]
ModelTier = Literal["small", "balanced", "frontier"]
```

Public functions:

```python
validate_inputs(complexity, model_tier, task_count) -> None

select_pattern(
    complexity,
    model_tier,
    task_count,
    parallel_independence,
    persistent_state_needed=False,
) -> PatternVerdict

forbidden_pattern_rationale(pattern) -> str | None
```

`validate_inputs` raises `ValueError` for unknown complexity/model tiers or
`task_count < 1`. Inputs are never silently coerced.

`select_pattern` returns:

```text
if persistent_state_needed
   and model_tier == frontier
   and complexity in {STANDARD, COMPLEX}:
    AGENT_POOL_FORWARD
elif persistent_state_needed:
    INLINE
elif task_count >= 2 and parallel_independence:
    FAN_OUT
else:
    INLINE
```

The helper never returns `TEAMS_FORBIDDEN`. That literal is reserved for the
operator-education path through `forbidden_pattern_rationale`.

## 4. Pattern 1 — Inline Tool

Choose `INLINE` when:

- there is one atomic task;
- candidate tasks overlap writable files;
- ordering requires one result before the next dispatch;
- parallelism would cost more context than it saves;
- persistent state was requested but no supported pool contract exists.

Current execution:

```text
L0 Project selects ready item
  → L1 Wave validates scope/ownership
    → one L2 Task executes and self-verifies
      → L1 aggregates evidence
        → L0 adjudicates checklist progress
```

“Inline” means one leaf dispatch, not that L0/L1 performs the work.

## 5. Pattern 2 — Fan-Out

Choose `FAN_OUT` only when two or more Tasks are independent:

```text
L1 Wave
  ├── L2 Task A — owned files A
  ├── L2 Task B — owned files B
  └── L2 Task C — owned files C
        ↓ append-only StatusReports
      L1 synchronization barrier
```

Preconditions:

1. writable sets are pairwise disjoint;
2. no Task depends on another Task in the same wave;
3. each Task has one objective and bounded verification;
4. combined Tasks do not exceed the 5-task wave cap;
5. L1 can aggregate results without rewriting Task artifacts.

If more than 5 ready Tasks exist, partition them across waves while keeping
the round under 7 waves. Preserve dependency order.

Suitable examples:

- independent documentation pages;
- platform-specific implementations behind a stable interface;
- separate review dimensions;
- bounded research questions with a later synthesis Task.

Unsuitable examples:

- multiple Tasks editing the same registry;
- generator and verifier dispatched simultaneously;
- migrations requiring output N before N+1;
- ambiguity requiring a human decision.

## 6. Pattern 3 — Agent Pool

`AGENT_POOL_FORWARD` is a forward-compat signal, not an executable runtime.
It can be selected only for STANDARD/COMPLEX work on a frontier model when
`persistent_state_needed=True`.

Current behavior falls back to bounded Inline dispatches and artifact-based
continuity:

```text
fresh L2 Task
  → evidence / append-only report
  → fresh later L2 Task receives bounded predecessor facts
```

Landing a real pool would require an explicit persistent-state schema,
ownership/lifetime rules, restart recovery, budget enforcement, and an SI-1
architecture decision. A pool may not become hidden shared memory.

## 7. Pattern 4 — Teams

`TEAMS_FORBIDDEN` names the unsupported external taxonomy row. DevolaFlow P5
requires artifacts as contracts and prohibits direct cross-agent messaging
or shared state.

Use:

```python
forbidden_pattern_rationale("TEAMS_FORBIDDEN")
```

The returned rationale cites the Soul-level invariant and the reversal path.
Overturning this stance requires SI-1, an ADR, W-21 cadence, and SI-3
architecture rationality ≥9.5/10.

Allowed cooperation:

- append-only TaskDispatch/StatusReport envelopes;
- immutable predecessor artifacts;
- L1 synchronization and aggregation;
- L0 checklist adjudication.

Forbidden cooperation:

- peer-to-peer mutable memory;
- one Task editing another Task's report;
- unschematized direct messages;
- shared writable files inside a parallel wave.

## 8. Decision Examples

| Inputs | Verdict | Current execution |
|---|---|---|
| SIMPLE, one task | `INLINE` | one L2 Task |
| STANDARD, three independent tasks | `FAN_OUT` | one L1 wave, three L2 Tasks |
| COMPLEX, eight independent tasks | `FAN_OUT` | at least two waves |
| STANDARD, persistent state, frontier | `AGENT_POOL_FORWARD` | forward signal; bounded Inline fallback |
| Any, persistent state, balanced | `INLINE` | artifact-mediated continuity |
| Direct shared-state team request | education path | `forbidden_pattern_rationale("TEAMS_FORBIDDEN")` |

## 9. Composition with Checklist Rounds

Pattern selection happens after L0 selects ready checklist items:

1. L0 reads `goal.md`, `checklist.md`, `stage.md`, and `preflight.md`.
2. L0 chooses a bounded round set by priority/dependencies.
3. L1 groups the set into waves.
4. L1 calls `select_pattern` for each wave shape.
5. L2 Tasks execute and emit evidence.
6. L0 checks passing items or records reinforcement for a later round.

Checklist seeds contribute decomposition hints and `source_stages` provenance.
They never force a role chain or executable workflow graph.

## 10. Historical Compatibility

The v11.4.0 source comments and archived analyses describe Pattern 2 as an
“L2 wave dispatching L3 tasks” in the former hierarchy. Preserve those bytes
in source/archive records. Current interpretation normalizes that historical
pair to L1 Wave dispatching L2 Tasks.

The external taxonomy still has four rows. “Four” describes the upstream
taxonomy, not DevolaFlow's number of agent layers.

## 11. Invariants

- Pattern selection performs zero filesystem I/O at import.
- No new `DEVOLAFLOW_*` environment flag.
- Invalid inputs raise explicit errors.
- `select_pattern` never returns `TEAMS_FORBIDDEN`.
- Fan-Out always obeys max 5 Tasks per wave.
- Round planning always obeys max 7 waves.
- Reports flow Task → Wave → Project; unresolved failures continue to Human.

## 12. See Also

- `references/agent-hierarchy.md`
- `references/decomposition-gate.md`
- `references/agent-workspace.md`
- `references/execution-protocol.md`
- `references/grill-mode.md`
- `src/devolaflow/skills/subagent_pattern.py`
