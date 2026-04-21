<!--
Stub authored under v7.5.0 P-07 Option α (per .local/research/v7.5.0_ghost_audit.md §5)
Wave decomposition planning document — L2 Wave Agent authors this artifact
during planning, before dispatching L3 Task Agents. Encodes the disjoint
owned-files contract (P5) and links to dependency-matrix.schema.yaml so
reviewers verify the plan before any L3 dispatch goes out.

TODO(v7.6.x P-07 Option β): add a `## Dependency matrix` section linking
to the dependency-matrix.schema.yaml instance; wire into a `devola-plan-wave`
CLI (planned for v7.6.0) that auto-derives owned_files from a stage spec.
-->

# Wave `<wave_id>` — `<wave_purpose>`

**Stage:** `<stage_id>` | **Sync barrier:** `<all | any | n_of(k)>` <!-- composer honours `all` -->
**Max parallelism:** `<int>` | **Status:** `<pending | dispatching | gated | passed | failed | escalated>`

## Goal
<!-- Verbatim from the wave-definition's `description`. -->

## Tasks

| Task ID   | Title     | Team     | Owned files | Depends on        |
|-----------|-----------|----------|-------------|-------------------|
| `W01-T01` | `<title>` | `<team>` | `<paths>`   | `<task_ids or —>` |

## Disjoint-scope verification (P5)
<!-- Confirm every entry in dependency-matrix.schema.yaml#file_ownership has exactly one owner_task_id. -->
- [ ] No file path appears in more than one `Owned files` cell.
- [ ] Every `Depends on` edge corresponds to a real artifact produced by the upstream task.

## Gate
- Type: `<standard | convergence | passthrough>` | Profile: `<strict | standard | relaxed | audit>`
- Max rounds: `<int>` (P4 bounded retry) | Decision: `<PASS | FAIL | ESCALATE | pending>`

## Risks / open questions
<!-- Surfaces ambiguity to the L1 Stage Agent before dispatch. -->
- `<risk or question>`
