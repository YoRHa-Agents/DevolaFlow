---
id: "agent/references/workspace-compact"
version: "24.0.0"
purpose: >
  Define non-destructive in-folder compaction: content-bound per-run approval,
  relocation into an append-only mapping ledger, and a dual-layer digest whose
  narration must carry resolvable verbatim anchors.
triggers:
  - "workspace compaction"
  - "compact task folder"
  - "archive closed risks"
  - "locate archived content"
  - "restore archived file"
tier: 2
token_estimate: 1600
dependencies:
  - "agent/SKILL.md"
  - "agent/references/agent-workspace.md"
  - "agent/references/risk-parking.md"
last_updated: "2026-09-01"
---

# Workspace Compaction

**Tier**: large · **Load when**: compacting a task or change folder —
plan/apply/locate/restore, the mapping ledger, and the DIGEST.

## 1. What compaction means here

Not summarise-and-discard. **Relocate and index.**

A conversational compactor replaces history with a summary and the original is
gone. That is acceptable for a chat transcript and unacceptable for a task
workspace, where the discarded detail is the audit trail. Here every relocated
file is moved intact into an archive, its content hash is recorded, and a
generated digest states where it went. "Nothing was lost" is a checkable claim:
`devola-compact verify` re-hashes every archived original.

The unit of work is **one task or change folder**, named explicitly. Compaction
never roams the repository.

## 2. Surfaces

```
<task-or-change-folder>/compact/
  DIGEST.md            # generated: what moved, what it was about, where it is
  mappings.yaml        # append-only: source, destination, hash, bytes, tokens
  archived/<seq>/...   # the originals, byte-identical, at their original paths
```

## 3. Commands

| Command | Purpose |
|---|---|
| `probe` | confirm the runtime and write path are available |
| `plan` | classify the folder; report what would move. Always free, always report-only |
| `apply` | relocate an approved plan; requires `--approve <fingerprint>` |
| `locate` | search the archived originals |
| `restore` | copy one archived original back into place |
| `verify` | re-hash every archived original; non-zero on mismatch |
| `audit` | digest drift and broken narration anchors |
| `summarize` | replace the digest's agent narration section |
| `scan` | report folders an agent can no longer read in one pass |
| `telemetry` | summarise the compaction telemetry ledger |
| `handoff-index` | render a read-only index of handoff envelopes |

### Approval is per-run and never pre-authorised

`apply` requires the fingerprint of the plan you just read. The fingerprint
covers each moving file's source, destination, and content hash, so a file that
changed after the plan was produced invalidates the approval. Approving one
file is not approving a different one that took its place.

There is deliberately no pre-authorisation and no auto-apply. During unattended
work, produce a plan and leave it queued; that is the expected outcome, not a
failure, and it is recorded as a `planned` telemetry event.

## 4. What moves and what never moves

| Category | Behaviour |
|---|---|
| `closed_risk` | a risk in `closed` state — moves |
| `historical_output` | contents of `loops/`, `rounds/`, `history/`, `logs/` — moves |
| `operator_named` | explicitly passed via `--include` — moves |
| `protected` | never moves automatically |
| `live` | still in use — retained |

Protected artifacts include `goal.md`, `checklist.md`, `spec.md`,
`STATUS.yaml`, `owned_files.txt`, `entrance.md`, and the generated views. The
strongest case is `judgments.yaml`: the only durable record of what the
operator decided, never compacted at any size.

Symlinks are skipped and reported, never followed.

## 5. Reading the numbers honestly

Two different measurements answer two different questions. Report both.

- **Working set** — what an agent must read to orient: the generated index plus
  the one file the question is about. This is the number that reflects agent
  efficiency.
- **Resident tokens** — the sum of everything still in the folder. This is the
  counterweight, because splitting one blob into per-file records *adds*
  structure and can raise the total even as it lowers the working set.

Measured on the v2.8.6 sample: working set fell 8679 → 1284 tokens (85.2%),
while resident tokens fell only 39.4%. Reporting only the first would flatter
the feature; reporting only the second would hide its actual benefit.

Compaction also has a fixed cost: the digest it writes is itself tokens. On a
small folder the digest can cost about what the moved files saved, which is
precisely why compaction is *suggested* above a size threshold rather than run
by default.

## 6. Recovering something that moved

```bash
devola-compact --folder <task> locate --query "PV-16b disposition"
devola-compact --folder <task> restore --source parking/risks/RISK-007.md
```

`locate` searches archived originals and returns the archived path, the
original path, the line number, and the matching excerpt. Measured recovery
cost on the v2.8.6 sample was 77 tokens on average versus 8679 to read the
source document — under 1%.

`restore` copies a file back without deleting the archived copy or editing the
mapping ledger, so restoring is not a way to lose the audit trail.

## 7. The DIGEST is two layers

The **structural layer** is generated from `mappings.yaml` and is the guarantee:
sequence, subject, original path, archive path, tokens, hash.

The **agent narration layer** is optional, explicitly labelled unverified, and
every claim must carry a verbatim anchor:

```
[[compact/archived/0001/parking/risks/RISK-001.md#L14]] "the blast radius, not the bad row"
```

`audit` resolves each anchor against the archived file and fails on any that
does not. An unanchored assertion in the narration section is a lint failure —
a summary an agent wrote about text it cannot point to is exactly the failure
mode the structural layer exists to prevent.

## 8. Deletion

Never automatic. There is no deletion API, no deletion workflow, and no
`git clean` equivalent anywhere in the runtime. Compaction relocates; only the
operator removes. See W-26.

## 9. Telemetry

Compaction events go to `.local/telemetry/compact.jsonl`, deliberately **not**
the shared harness ledger. Three outcomes are recorded: `applied`, `planned`
(waiting for consent), and `bypassed`. The reader skips a damaged row rather
than aborting, so broken evidence degrades to less evidence, never to none.

That separation is a lesson from this cycle: one unparseable row in the shared
harness ledger made every downstream evaluation unavailable.

## 10. Related

- `references/risk-parking.md` — the risk lifecycle that produces
  `closed_risk` candidates
- `references/local-archive.md` — moving whole folders between surfaces, a
  different tool for a different job
