---
id: "agent/references/agent-workspace"
version: "2.0.0"
purpose: >
  Current agent-workspace contract for checklist-driven changes: canonical
  goal/checklist/stage/preflight/evidence artifacts, three-layer ownership,
  resume, append-only handoffs, source-of-truth deltas, archive, and budgets.
triggers:
  - "opening or resuming an active change"
  - "writing checklist-round artifacts"
  - "using append-only handoff envelopes"
  - "archiving a source-of-truth spec delta"
tier: 2
token_estimate: 3600
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-08-26"
---

# Agent Workspace Reference

## 1. When to Engage

At session start, L0 calls
`devolaflow.workspace_context.scan_workspace(repo_root)` and inspects:

| Signal | L0 action |
|---|---|
| `.local/.agent/active/<id>/` exists | Resume its STATUS/checklist state unless the user explicitly opts out |
| `.local/memory/specs/<domain>/spec.md` exists | Treat it as source-of-truth; active `spec.md` is a delta |
| `.local/human/input/` exists | Read REQ IDs and constitution as binding human input |
| `.rules/*.mdc` + `AGENTS.md` exist | Trust the compiled corpus; slice only for the receiving Task |

Workspace scanning is read-only. Auto-scaffolding is R5-strict default-OFF
and engages only when `DEVOLAFLOW_AGENT_WORKSPACE=1`.

For STANDARD/COMPLEX work, L0 selects a checklist seed, loads the sole
`change-driven` runtime, and creates the active-change contract before the
first L1 Wave dispatch. Seed `source_stages` remain non-executable provenance.

## 2. Current Layout

```text
.local/.agent/
├── active/
│   └── <change-id>/
│       ├── entrance.md
│       ├── goal.md
│       ├── checklist.md
│       ├── stage.md
│       ├── preflight.md
│       ├── spec.md
│       ├── STATUS.yaml
│       ├── owned_files.txt
│       └── evidence/
├── handoff/
│   └── <from>__<to>__<change-id>__<seq>.yaml
└── archive/
    └── <YYYY-MM-DD>-<change-id>/
        ├── entrance.md
        ├── goal.md
        ├── checklist.md
        ├── stage.md
        ├── preflight.md
        ├── spec.md
        ├── STATUS.yaml
        ├── owned_files.txt
        ├── evidence/
        ├── REPORT.md
        └── handoff_chain.yaml
```

All paths are repository-relative. Change IDs are lowercase kebab-case.
Handoff sequence numbers start at `0001` and increase monotonically.

### Legacy layout removal (v17.0.0)

The pre-v16 `acceptance.md` + `tasks.md` pair is fully removed. Loading a
change folder that carries them without `checklist.md` raises
`LegacyChangeLayoutError` — migrate the folder to `checklist.md` before
loading. A folder mixing legacy files with `checklist.md` is invalid
(`INVALID_MIXED`). All changes use only the layout above.

## 3. Three-Layer Ownership

```text
L0 Project → L1 Wave → L2 Task
reports:     L2 Task → L1 Wave → L0 Project
escalation:  L2 Task → L1 Wave → L0 Project → Human
```

| Layer | Workspace responsibility | Budget |
|---|---|---:|
| L0 Project | Materialize contracts, select rounds, adjudicate evidence, archive | ~5K |
| L1 Wave | Validate dependency/ownership maps, dispatch Tasks, aggregate evidence | ~5K |
| L2 Task | Perform one scoped task, self-verify, emit StatusReport/evidence | ~8K |

Only L2 performs implementation, test execution, research, review, or
deliverable authoring. L2 cannot mark checklist items or mutate lifecycle
contracts.

## 3.6 Resume After Pause

Before any returning-session dispatch, L0:

1. scans workspace state;
2. reads `STATUS.yaml` and rejects terminal `ARCHIVED`/`ESCALATED` changes;
3. validates `preflight.md` authorization and project-config hash;
4. reconciles `last_handoff_seq` with the append-only envelope ledger;
5. reads `goal.md`, `checklist.md`, `stage.md`, and `preflight.md`;
6. selects only open/reverted items whose dependencies are checked;
7. resumes at the next bounded round coordinate.

Resume planning performs zero writes. Checked items are never selected again.
A user-reopened item retains its verbatim `reverted:` reason and enters the
next round before ordinary P0/P1/P2 work.

Agents joining outside this protocol (fresh sessions, non-DevolaFlow-aware
tools, human auditors) read `entrance.md` FIRST — its scenario routing table
maps each onboarding case to the minimal artifact read order. A pre-v17.2
folder without one is backfilled from the scaffold template on first resume
(lint reports `ENTRANCE_MISSING` as WARN until then).

`force_no_change=True` on `activation_verdict()` remains the explicit
operator escape hatch for an ad-hoc dispatch.

## 4. Artifact Contracts

### `entrance.md`

The agent onboarding entry point — a STATIC ROUTER, not a status mirror:

- Section 1 names the change (goal title verbatim + `goal.md` link) and is
  the only per-change personalized section;
- Section 2 routes each onboarding scenario (session resume, new L2 task,
  review/verify, human audit) to its minimal artifact read order;
- Section 3 inventories every artifact with a one-line role; the lint's
  `ENTRANCE_PARITY` finding keeps it in lockstep with the C-4 budget
  registry;
- Section 4 carries discipline POINTERS only (rule IDs + owning files).

Progress, rounds, and blockers are never restated here — they are read from
`STATUS.yaml`, `stage.md`, and `preflight.md` Section 4. The router is never
injected into dispatch payloads (`hydrate_change_context` and
`schemas/lean-dispatch.yaml` are untouched).
Schema: `schemas/agent-workspace/change-entrance.yaml`.

### `goal.md`

The stable user goal contract:

```markdown
# Goal: <title>

## Why
<problem and desired outcome>

## Goals
- G1: <verifiable outcome>
- G2: <verifiable outcome>

## Out of scope
- <explicit exclusion>
```

Goal IDs and titles must match checklist partitions.
Schema: `schemas/agent-workspace/change-goal.yaml`.

### `checklist.md`

The acceptance and progress truth:

```markdown
---
parent: <change-id>
schema_version: 1
total_items: 2
checked: 0
priority_dist: {P0: 1, P1: 1, P2: 0}
reverted_open: 0
---

# Checklist

## Progress

`[░░░░░░░░░░░░░░░░░░░░] 0%` — done 0 | doing 0 | todo 2 | total 2 (effort-weighted)

## G1: <goal title copied verbatim>
- [ ] C-G1.1 (P0) <measurable assertion, at most 25 words>
      verify: `<bounded command>`
      depends: []
- [ ] C-G1.2 (P1) <measurable assertion>
      verify: metric: <machine-evaluable expression>
      depends: [C-G1.1]
      effort: 2
```

Rules:

- priorities are P0/P1/P2 and user-confirmed;
- dependencies reference checklist item IDs;
- command/metric checks finish within 300 seconds;
- manual checks are user-only;
- L2 reports evidence, L1 aggregates, L0 or the user checks an item;
- only the user may reopen `[x] → [ ]`;
- checked items reference `evidence/C-Gn.m.txt`;
- the pinned `## Progress` header stays byte-aligned with derived state:
  done = checked items, doing = unchecked items picked in the in-flight
  stage.md round, todo = the rest; the bar and percentage weigh each item
  by its optional `effort: 1..8` metadata (default 1). L0 re-renders the
  header on every checkbox flip, effort change, item add/drop, or round
  transition — `ChangeStore.refresh_progress_header`,
  `revert_checklist_item`, and `reconcile_round_boundary` re-align it
  automatically, and the C-4 linter fails on any drift (`PROGRESS_HEADER`).

Schema: `schemas/agent-workspace/change-checklist.yaml`.

### `stage.md`

`stage.md` is a round-control artifact, not an agent layer:

```markdown
---
parent: <change-id>
schema_version: 1
current_round: 0
max_rounds: 5
capacity_per_round: 5
---

# Stage — Round Control

## Priority Settings
<append-only user priority history>

## Round History
| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |

## Next Round Plan
- Candidates: [...]
- Estimated remaining rounds: ...
```

Selection order is: user-reverted items, P0, P1, P2, satisfied dependencies,
then stable checklist order. Each round has at most 7 waves; each wave has at
most 5 Tasks. Composite is recorded as trend-only per round.

Schema: `schemas/agent-workspace/change-stage.yaml`.

### `preflight.md`

The sole pre-execution confirmation surface. It contains:

1. eight project-configuration sections;
2. exhaustive stop cards linked to checklist IDs;
3. user authorization records;
4. the closed permitted-stop list;
5. the latest progress snapshot.

No round starts while `authorized_at` is null, the authorization hash is
invalid, or `.local/project_config.yaml` differs from its signed hash.
Sections 0–3 freeze after signature; progress snapshot updates do not
invalidate authorization.

Schema: `schemas/agent-workspace/change-preflight.yaml`.

### `spec.md`

Per-change behavioral delta relative to
`.local/memory/specs/<domain>/spec.md`:

```markdown
## ADDED Requirements
### Requirement: <stable heading>
The system MUST <observable behavior>.

## MODIFIED Requirements
### Requirement: <existing heading>
<new behavior>

## REMOVED Requirements
### Requirement: <existing heading>
<reason>
```

Source-of-truth changes only at archive time after mergeability and readiness
gates pass. Archive proposes the merge; it does not silently auto-apply it.

Schema: `schemas/agent-workspace/change-spec.yaml`.

### `STATUS.yaml`

Machine-readable lifecycle state:

```yaml
schema_version: 2
change_id: <id>
state: PROPOSED
percent_complete: 0
owner_layer: L0
owner_session_id: <uuid>
last_updated: <ISO-8601>
last_handoff_seq: 0
gate_score: null
verify_pass: null
checklist_checked: 0
checklist_total: 2
current_round: 0
next_blockers: []
```

Current owner layers are `L0|L1|L2`. Schema-v1 `L0|L1|L2|L3` values are
read-time compatibility data normalized in memory and never rewritten.

`last_handoff_summary` is the optional **v10.7.0 D-P-3** NEST demonstration:
its `from_layer`, `to_layer`, timestamp, and sequence remain nested under one
field. Historical L3 values in that optional diagnostic are preserved as
compatibility bytes.

Schema: `schemas/agent-workspace/change-status.yaml`.

### `owned_files.txt` and `evidence/`

`owned_files.txt` lists repository-relative writable paths. Within a wave,
Task writable sets are pairwise disjoint.

Each checked checklist item maps to one evidence file containing:

- the exact command or metric expression;
- exit status or measured value;
- a verbatim final output line plus digest;
- verdict and UTC timestamp.

Evidence files are at most 10 KB each; the directory is at most 50 KB.

## 5. Lifecycle

```text
PROPOSED
  → signed preflight
  → IN_PROGRESS
      → bounded checklist rounds
      → all items checked, no open reversion
  → VERIFYING
      → archive gate PASS
  → ARCHIVED
```

Any exhausted bounded retry may enter `ESCALATED`. `ARCHIVED` and
`ESCALATED` are terminal.

The sole executable template is:

```python
registry.load_template("change-driven")
```

Intent modes are loaded separately with `registry.load_seed(name)`.
Historical `load_template(seed_name)` calls are compatibility aliases, not
separate runtimes.

Round PASS requires all selected items to have valid passing evidence and
zero blockers. Archive additionally requires all items checked, no open
reversion, valid evidence references, valid signed preflight, mergeability,
and readiness composite 8.5 (lite/minor) or 9.0 (full/major).

## 6. Append-Only Handoff Envelopes

The handoff directory is the artifact-mediated inter-agent channel. Current
schema-v2 directions use only `L0`, `L1`, and `L2`.

```text
L0__L1__<change-id>__0001.yaml
L1__L2__<change-id>__0002.yaml
L2__L1__<change-id>__0003.yaml
L1__L0__<change-id>__0004.yaml
```

Every envelope has exactly one discriminated payload:

- `TaskDispatch`;
- `StatusReport`;
- `EscalationEvent`.

Once written, an envelope is immutable and undeletable. New information uses
`seq+1`. Schema-v1 files with legacy L3 tokens remain readable with explicit
legacy provenance and are never migrated in place.

Schema: `schemas/agent-workspace/handoff-envelope.yaml`.

### Handoff Envelope L0-only Metadata Stripping (v12.4.0 PV-05)

Before authoring a lower-layer envelope, strip operator-only session banners,
Task Quality Score footers, and operational-learning management prose from
`predecessor_summary`. The runtime guard
`reject_subagent_banner_emission` rejects newly emitted banner literals; it
does not rewrite historical evidence nested in predecessor artifacts.

## 7. File Ownership (S-8)

An L2 Task in an active `change-driven` change may write only:

1. its dispatched paths from `owned_files.txt`;
2. the active change folder;
3. its own append-only handoff outbox.

In full/STRICT mode, a violation blocks and escalates. In lite mode, it warns
and logs. L0/L1 read-only planning remains unrestricted.

## 8. Bounded Rounds and Escalation

| Limit | Contract |
|---|---|
| Tasks per wave | ≤5 |
| Waves per round | ≤7 |
| Writable files per Task | ≤6 |
| No net checklist progress | 2 rounds → escalate |
| Same open item selected | 3 rounds → item escalation |
| Reinforcement rules | ≤5 per failed round |

Escalation is Task → Wave → Project → Human and never skips a layer.

## 9. Token Budgets (C-4)

| File | Soft | Hard |
|---|---:|---:|
| `entrance.md` | 400 | 800 |
| `goal.md` | 200 | 400 |
| `checklist.md` | 1200 | 2400 |
| `stage.md` | 400 | 800 |
| `preflight.md` | 600 | 1200 |
| `spec.md` | 1500 | 3000 |
| `STATUS.yaml` | 150 | 300 |
| `owned_files.txt` | 50 | 100 |
| Handoff envelope | 600 | 1200 |
| `evidence/` | no token limit | 10 KB/file; 50 KB/directory |

Verify:

```bash
python -m devolaflow.agent_workspace.lint <change-id>
```

Soft breaches warn; hard breaches fail.

## 10. APIs

| API | Use |
|---|---|
| `scan_workspace(repo_root)` | Read workspace engagement state |
| `activation_verdict(...)` | Decide whether to open a change |
| `hydrate_change_context(change_id)` | Load bounded active-change context |
| `lint_change(change_id)` | Validate artifacts and budgets |
| `ArchiveManager.propose_merge(change_id)` | Prepare and validate archive-time SoT delta |
| `ArchiveManager.apply_merge(...)` | Apply an approved merge proposal |
| `consolidate_change_on_archive(...)` | Promote durable learnings |

## 11. References

- `schemas/agent-workspace/change-{goal,checklist,stage,preflight,spec,status}.yaml`
- `schemas/agent-workspace/change-entrance.yaml`
- `schemas/agent-workspace/handoff-envelope.yaml`
- `schemas/agent-workspace/owned-files.yaml`
- `schemas/lean-dispatch.yaml#layout_invariant`
- `workflow-system/agent/templates/builtin/change-driven.yaml`
- `references/agent-hierarchy.md`
- `references/decomposition-gate.md`
- `references/meta-framework.md`
- `references/message-schemas.md`
- Historical OpenSpec origin:
  <https://github.com/Fission-AI/OpenSpec>
