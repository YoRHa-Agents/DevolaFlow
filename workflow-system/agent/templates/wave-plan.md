<!-- L0 plans the wave; L1 Wave owns dispatch, conflict checks, and evidence aggregation. -->

# Round `<round_n>` / Wave `<wave_id>` — `<purpose>`

**Checklist:** `<change-id>` | **Runtime:** `change-driven`
**L1 owner:** `<wave-agent-id>` | **Status:** `<pending | dispatching | aggregating | passed | failed | escalated>`
**Max parallelism:** `5` | **Sync barrier:** `<all | dependency>`

## Selected checklist items

| Task ID | Item ID | Assertion | Verify | Depends on |
|---|---|---|---|---|
| `R01-W01-T01` | `C-G1.1` | `<verbatim checklist assertion>` | `<bounded command or metric>` | `<item IDs or —>` |

## Ownership and read context

| Task ID | Owned files | Read-only files |
|---|---|---|
| `R01-W01-T01` | `<repository-relative paths>` | `<repository-relative paths>` |

## Pre-dispatch conflict check

- [ ] Writable ownership is pairwise disjoint.
- [ ] Item dependencies are satisfied or sequenced into a later wave.
- [ ] Shared interfaces are explicit artifact contracts.
- [ ] Preflight authorizes every required environment or external action.

Unresolved conflicts:
- `<none | item IDs + exact conflict>`

## Reinforcement carried into this wave

| Rule ID | Severity | Checklist item | Verbatim finding | Required closure evidence |
|---|---|---|---|---|
| `<R-001>` | `<blocker | critical | major>` | `<C-G1.1>` | `<finding>` | `<evidence requirement>` |

## L1 evidence aggregation

| Item ID | Task state | Verification evidence | Reinforcement closed | Conflict result | Proposal |
|---|---|---|---|---|---|
| `C-G1.1` | `<completed | failed | escalated>` | `<artifact path + command/metric result>` | `<IDs | n/a>` | `<clear | unresolved>` | `<check | keep-open>` |

## Wave report to L0

- Evidence proposal: `<check item IDs | keep open with reasons>`
- Blockers/findings: `<none | severity + verbatim finding>`
- Ownership/interface conflicts: `<none | exact conflict>`
- Next action: `<round gate | bounded redispatch | escalate>`
