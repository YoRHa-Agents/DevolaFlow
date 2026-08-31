---
id: "agent/references/wave-dispatch"
version: "1.0.0"
purpose: >
  Documents the L1 Wave asynchronous dispatch boundary, concurrency controls,
  failure isolation, and the Dispatcher-Not-Implementer invariant.
triggers:
  - "dispatching a wave"
  - "choosing parallel wave execution"
  - "reviewing async task outcomes"
tier: 2
token_estimate: 900
dependencies:
  - "agent/SKILL.md"
  - "agent/references/team-roles.md"
last_updated: "2026-08-27"
---

# Wave Dispatch Reference

## Boundary

The L1 Wave dispatcher schedules caller-provided task callables. It does not
implement task work. The public entry point is:

```python
from devolaflow.dispatch import dispatch_wave_tasks

outcomes = dispatch_wave_tasks(
    wave_definition,
    dispatch_factory,
    max_concurrency=4,
)
```

`dispatch_factory` receives one task mapping and returns a zero-argument
callable. The executor owns scheduling; the factory owns task construction.
This preserves Soul Rule S-1.

## Mode resolution

| Mode | Task count | Execution path |
|---|---:|---|
| `parallel` | 2 or more | bounded `asyncio.gather` |
| `parallel` | 1 | sequential fast path |
| `all` | any | sequential |
| `any` / `n_of(k)` | any | sequential until quorum support lands |

Concurrency is selected in this order:
`max_concurrency` keyword, `sync_barrier.max_parallelism`, then the default
cap of 4. The semaphore is always bounded.

## Failure contract

Individual task failures are captured in `TaskOutcome.exception`; sibling
tasks continue. The caller classifies the result under bounded retry and
escalation rules. Malformed wave definitions and non-callable factory output
remain eager contract errors.

## W-30 — Continuous progress and blocker isolation

For long-running external work such as CI, installation, long tests, or
deployment, L1 sets an explicit timeout, records progress heartbeats at least
every five minutes (or the provider's documented cadence), and defines the
abandon/escalation action before waiting. Polling is meaningful only when it
observes new progress or a terminal state. If an independent task is ready and
has no resource or ownership conflict, L1 advances it while the external task
waits.

After signed preflight, an ordinary blocker or `HUMAN_INTERVENE` outcome
pauses only the affected task/item; unaffected siblings continue. L1 labels
the state as `dependency-blocked`, `finding-blocked`, or `wave conflict`.
Only no safely runnable work, a HARD breakpoint or STOP card,
`FULL_ROLLBACK`, an ownership violation, or a destructive-policy violation
justifies stopping the whole workflow. A wave conflict pauses the conflicting
partition, not unrelated ready work.

The async executor is a library boundary. It must be reached through
`devolaflow.dispatch.dispatch_wave_tasks`; no compatibility re-export is
required from `devolaflow.feedback`.
