---
id: "agent/references/risk-parking"
version: "24.0.0"
purpose: >
  Define the risk lifecycle, the append-only judgment ledger, and the single
  tool write entry point that keeps generated views agreeing with the ledgers
  they are rendered from.
triggers:
  - "risk parking"
  - "park a risk"
  - "judgment ledger"
  - "pending decision"
  - "record a decision"
tier: 2
token_estimate: 1600
dependencies:
  - "agent/SKILL.md"
  - "agent/references/agent-workspace.md"
  - "agent/references/workspace-compact.md"
last_updated: "2026-09-01"
---

# Risk Parking and the Judgment Ledger

**Tier**: large · **Load when**: registering a risk, queuing a decision, or
recording an operator judgment.

## 1. What problem this solves

An agent working unattended finds things that are wrong but not blocking. The
old habit was to write them into prose — a "risks" section in a design note, a
paragraph in a status report. Prose has three failure modes that matter:

- nobody can query it, so the same risk gets rediscovered every few sessions;
- it has no state, so a fixed risk and a live one look identical;
- it mixes "this threatens the work" with "a human must decide something",
  which are different problems with different owners.

Risk parking separates all three. A risk is a file with a lifecycle. A pending
decision is a row in a ledger. A risk that is waiting on a decision *references*
that row rather than being blocked by it, so work continues.

## 2. Surfaces

Created with the first artifact batch, beside `goal.md` and `checklist.md`:

```
<task-or-change-folder>/parking/
  risks/RISK-NNN.md   # one risk per file: frontmatter + free-form history
  INDEX.md            # generated: live risks, one line each
  judgments.yaml      # append-only: questions and decisions
  judge.md            # generated: pending queue above settled history
  events.yaml         # append-only: every lifecycle transition
```

`judgments.yaml` and `events.yaml` are authoritative. `INDEX.md` and `judge.md`
are rendered from them and carry a generation marker; editing either by hand is
detected as drift rather than silently becoming a second source of truth.

## 3. The only way to write

`devola-parking` is the sole write entry point. Every subcommand prints one
JSON object.

| Command | Purpose |
|---|---|
| `probe` | confirm the runtime and write path are available |
| `scaffold` | create the surface (idempotent) |
| `status` | risks, pending decisions, and any view drift |
| `audit` | drift only; non-zero exit on drift |
| `open` | register a risk |
| `transition` | move a risk to another lifecycle state |
| `update` | append a dated note to a risk's history |
| `ask` | queue a decision without blocking anything |
| `decide` | record an operator decision |
| `adopt` | preview, then apply, adoption of a legacy document |

Hand-writing any of these files is blocked by the `check_parking_write`
lifecycle hook. This is not bureaucracy: a hand-written risk file does not
update the event ledger, so the generated index silently disagrees with reality
and the drift check starts failing for reasons nobody can trace.

### Runtime is a hard prerequisite

If `devola-parking` is unavailable, writes are impossible. Report that plainly
and print the install command:

```
uv tool install --force --python 3.13 \
  'devolaflow @ git+https://github.com/YoRHa-Agents/DevolaFlow.git'
```

Do **not** hand-write the files as a fallback. Reading is unaffected — the files
are plain Markdown and YAML.

## 4. Risk lifecycle

```
open ──▶ parked ──▶ active ──▶ mitigating ──▶ closed ──▶ archived
  └────────┴──────────┴─────────────┴────────────┘
          (closed may reopen to active)
```

| State | Meaning |
|---|---|
| `open` | registered, not yet triaged |
| `parked` | real, deliberately not being worked now |
| `active` | currently threatening the work |
| `mitigating` | a fix is in progress |
| `closed` | no longer threatens the work |
| `archived` | the file has been relocated by compaction |

`archived` is terminal. Reopening it would leave the mapping ledger describing
a relocated file that came back, so a recurrence starts a new risk instead.

"Needs a decision" is deliberately **not** a state. It is a reference into
`judgments.yaml`, so a risk can be actively worked while one of its open
questions waits for the operator.

## 5. Decisions

Ask without blocking:

```bash
devola-parking --folder <task> ask \
  --subject RISK-004 --question "Ship behind the flag or wait?"
```

Record the answer the operator speaks in chat:

```bash
devola-parking --folder <task> decide \
  --question-id J-001 --decision "Ship behind the flag."
```

The ledger is append-only. Answering a question does not edit its row — a new
row is appended whose `supersedes` cites it. Changing your mind later appends
again. The result is a complete, replayable decision history.

`judgments.yaml` is **never compacted at any size**. It is the only durable
record of what was decided and why, which is exactly the thing that is
expensive to reconstruct and cheap to keep.

## 6. Registering a risk from a task agent

L2 agents do not write the surface directly. They report the risk through
`StatusReport` findings; L0 records it with the tool. In a single-agent
session, record it directly. This keeps S-8 file ownership intact without
needing an exception.

## 7. Adopting a legacy document

`adopt` converts an existing prose risk table into the structured surface. It
is report-only until approved with the plan's fingerprint:

```bash
devola-parking --folder <task> adopt --source docs/old-risks.md
devola-parking --folder <task> adopt --source docs/old-risks.md --approve <fingerprint>
```

Adoption preserves the source identifier verbatim in `legacy_id`, including
decorated forms. If a document keeps a superseded row as `~~PV-29-original~~`
beside a corrected `PV-29`, both survive as distinct risks: collapsing them
would fabricate a collision the source does not have and discard the author's
own distinction.

## 8. Budgets

Per C-9, each artifact carries soft/hard token budgets. Splitting one bloated
ledger into many files only helps if each file is bounded; otherwise the bloat
merely relocates.

| Artifact | Soft | Hard |
|---|---:|---:|
| `risks/RISK-NNN.md` | 500 | 1000 |
| `INDEX.md` | 600 | 1200 |
| `judge.md` | 800 | 1600 |

Check with `python -m devolaflow.agent_workspace.lint <change-id>`.

## 9. Related

- `references/workspace-compact.md` — relocating closed risks out of the
  working set
- `references/local-archive.md` — cross-surface archiving (a different tool
  for a different job: whole-folder moves, not in-folder shrinking)
