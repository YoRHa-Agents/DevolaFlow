---
id: "agent/references/local-archive"
version: "17.5.0"
purpose: >
  Define the explicit local-task archive workflow for bounded inventory,
  report-only planning, approved non-deletion moves, strict safety checks,
  and append-only archive provenance.
triggers:
  - "local archive"
  - "task archive"
  - "task clustering"
  - "archive mapping"
  - "task index"
tier: 2
token_estimate: 2600
dependencies:
  - "agent/SKILL.md"
  - "agent/references/agent-workspace.md"
  - "agent/references/meta-framework.md"
last_updated: "2026-08-27"
---

# Local Task Archive

## Purpose

`local-archive` is the recurring workflow for inventorying and, only after
explicit approval, physically organizing task folders below `.local/tasks/`.
It is separate from the `entropy-cleanup` workflow: entropy cleanup addresses
stale or drifting artifacts, while local archive addresses task inventory,
classification, approved non-deletion moves, mapping, and index verification.
The `local-archive` seed is declarative decomposition knowledge; the explicit
`devola-local-archive` command owns the bounded runtime behavior.

## 1. When to load

Load this reference when an operator requests a local-task archive, task
clustering, archive mapping, or the task index. Select the
`local-archive` checklist seed and use the existing `change-driven` runtime
for workflow execution. Do not extend or reinterpret `entropy-cleanup`.

No new environment variable or dispatch-schema key activates this workflow.
Selection is explicit operator intent or the bounded command. The dispatch
canonical order and cache prefix are unchanged.

## 2. Source boundary and inventory

The default source boundary is exactly `.local/tasks/`. Public paths are
repository-relative POSIX paths; absolute paths and traversal are refused.
Non-task `.local/` directories and source/config surfaces are not archive
inputs.

The inventory recognizes both layouts:

- **Canonical:** `.local/tasks/<cluster>/active/<task-id>/` and
  `.local/tasks/<cluster>/archive/<period>/<task-id>/`.
- **Brownfield:** direct child task folders such as
  `.local/tasks/<task-id>/`, even when the surrounding DevolaFlow scaffolding
  is absent or incomplete.

Inventory is read-only. A task folder is inspected through explicit metadata,
not through its name, mtime, or size. Missing, malformed, conflicting, or
unsupported metadata produces a finding and conservative classification.
Unrelated files and directories remain untouched.

Cluster identity is a stable, human-readable key from the canonical path or
explicit task metadata. The six clusters from the one-off cleanup report are
only a reference example; they are not a fixed manifest, required count, or
registry. Zero or any other approved number of clusters is valid.

## 3. Lifecycle and protection

Every candidate receives exactly one lifecycle value:

`active` · `done` · `stale` · `unknown`

`protected` is not a lifecycle value. Protection is a separate verdict and
reason. A protected candidate remains ineligible regardless of its lifecycle.
The default protected set includes:

- `.local/.agent/`
- `.local/memory/specs/`
- `.local/research/`
- `.local/human/input/`
- `.rules/`
- all source/config surfaces, including `src/`, `schemas/`, `scripts/`, and
  `workflow-system/`

The task archive source remains `.local/tasks/`; a path outside that boundary,
an unsafe symlink, an unreadable source, or a protected surface is reported
with an explicit refusal rather than guessed into an eligible task.

## 4. Report-only default

The default invocation is a report-only plan:

```text
devola-local-archive --repo-root .
```

It inventories and renders an exact plan without moving, deleting, rewriting,
creating an index, or creating a mapping ledger. The plan reports each
source, destination, stable cluster key, lifecycle classification, action,
protection verdict/reason, and findings. Actions are `move`, `retain`,
`review`, or `refuse`; there is no delete action.

The report is safe to repeat. It is not approval, and a dry run never implies
permission to apply a move.

## 5. Explicit approval and physical moves

Physical moves are non-deletion moves and require explicit approval of an
earlier plan. Apply only the exact approved subset:

```text
devola-local-archive --repo-root . --apply approved-plan.json
```

The approved entry must still match the current plan's source, destination,
classification, findings, and action. Changed, missing, duplicated, or
unapproved entries are refused. Approval of one entry does not approve other
entries. Task-local context moves with the task folder; it is not replaced by
a summary.

An approved move is permitted only after the strict safety inspection passes.
Any refusal leaves the candidate in place. Existing change folders under
`.local/.agent/` and research archives remain outside this task workflow.

## 6. Strict safety checks

Before a migration-sensitive action, the command verifies all of the
following:

1. source and destination stay inside the repository and `.local/tasks/`
   boundary;
2. neither path nor any descendant is a symlink;
3. the source is a readable directory and the destination does not already
   exist;
4. the source is not a protected surface, nested repository, or registered
   worktree;
5. `git status --short --untracked-files=all` is empty;
6. staged and unstaged diffs are inspected;
7. ignored review/note paths are checked; and
8. the worktree registry is inspected.

Dirty, ambiguous, missing, unreadable, nested-repository, symlink, protected,
or worktree-conflicted paths produce explicit findings and refuse the action.
A clean check is a precondition, not permission to delete or run `git clean`.
The command never invokes `git clean -fdx` or an equivalent destructive
operation.

## 7. Permanent deletion boundary

Deletion is permanently operator-only. The local-archive runtime exposes no
automatic deletion API and no deletion workflow mode. It may report a
disposable candidate set, but the operator owns any later deletion decision
and action outside this runtime. Clean checks and plan approval do not change
that boundary.

## 8. Mapping and generated index ownership

Every physical move appends one dedicated task-archive mapping row to
`.local/tasks/archive-mappings.yaml`. The YAML document stream records:
`sequence`, `source`, `destination`, `reason`, and `timestamp`. Sequence
values increase from the existing maximum. Existing rows are immutable;
duplicate source or destination paths are refused.

This mapping ledger is a dedicated task-archive record, not an existing
`.local/.agent/` handoff envelope. Existing handoff envelopes are never edited
or deleted; a later operation appends a new record where its own contract
requires one.

`.local/tasks/INDEX.md` is a generated navigation view owned by the local
archive index renderer. Its generated marker is:

```text
<!-- devolaflow: generated task archive index -->
```

The mapping ledger is authoritative; the index is not. A missing index may be
created only by an apply operation. A human-maintained index without the
marker, a symlinked index, or an unreadable index is never silently
overwritten. The renderer must report a refusal or drift finding rather than
clobber operator bytes.

## 9. Canonical and brownfield operation

For a canonical workspace, inspect `.local/tasks/` and the protected
`.local/.agent/` surfaces, inventory without mutation, classify, render the
report, obtain explicit approval, apply only approved moves, then verify
unique destinations, one disposition per source, the generated index, and
the append-only mapping.

For a brownfield flat workspace, inspect `.local/tasks/` if present even when
canonical scaffolding is incomplete. Treat every child as unknown until
metadata and path safety are inspected. Do not infer disposability from
`tmp`, `old`, `done`, or `archive` in a name. The operator may retain the
flat layout, adopt clusters gradually, or approve only a subset. Missing
index or mapping files are findings, not a reason to scaffold unrelated
workspace surfaces.

## 10. Existing surfaces remain unchanged

The default `scan_workspace` discovery remains narrow and does not enumerate
`.local/tasks/`, infer task status, or inject archive mappings. Task inventory
is owned by the explicit local-archive command so unrelated sessions retain
their existing context and cache behavior.

The existing local workspace `generate_index` behavior for `.local/index.md`
is unchanged. W-7 continues to own versioned research archiving under
`docs/cycle-archive/`. `ChangeStore` and `ArchiveManager` continue to own the
`.local/.agent/` active-change lifecycle and are not reused for task moves.

## Cross-references

- `schemas/local-archive.schema.yaml` — plan, index, and mapping contracts
- `src/devolaflow/local/archive.py` — inventory, plan, safety, apply, index,
  and mapping owner
- `workflow-system/agent/templates/seeds/local-archive.yaml` — declarative
  checklist seed
- `workflow-system/agent/references/agent-workspace.md` — active-change
  folders, handoffs, and change archives
- `workflow-system/agent/references/meta-framework.md` — non-executable seed
  and registry semantics
