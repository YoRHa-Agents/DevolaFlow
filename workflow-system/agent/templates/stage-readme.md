<!--
Stub authored under v7.5.0 P-07 Option α (per .local/research/v7.5.0_ghost_audit.md §5)
Per-stage tracking document — L1 Stage Agent maintains this README inside the
stage's working directory; consumed by L2 Wave Agents and downstream stages
as part of the predecessor context bundle (P2 minimal context, ~5K-token slice).

TODO(v7.6.x P-07 Option β): wire into `devola-init` so each stage directory
is bootstrapped with a populated copy; add a `## Cross-references` block
linking to stage-definition.schema.yaml + parent project-status.yaml.
-->

# Stage `<stage_id>` — `<stage_name>`

**Workflow:** `<workflow-template-id>` | **Team:** `<research | design | implement | test | review>`
**Primitive:** `<one of the 13 universal stage primitives>` | **Started:** `<ISO8601>`
**Status:** `<pending | in_progress | gated | passed | failed | escalated>`

## Goal
<!-- Verbatim from the stage definition's `scope.description`. -->

## Predecessor artifacts
<!-- Mirrors task-dispatch.schema.yaml `context.predecessor_artifacts` shape. -->
- `<path>` — `<one-line summary>`

## Owned files
<!-- Repo-relative paths; disjoint from sibling stages per P5. -->
- `<path>`

## Acceptance criteria
- [ ] `<criterion>`

## Wave plan
- [W01](./wave-plan.md) — `<one-line wave purpose>`

## Gate
- Type: `<standard | convergence | passthrough>` | Profile: `<strict | standard | relaxed | audit>`
- Max rounds: `<int>` (P4 bounded retry) | Decision: `<PASS | FAIL | ESCALATE | pending>`

## Round history
<!-- One row per convergence round; standard gates have a single row. -->

| Round | Composite | Blockers | Criticals | Trend       | Timestamp   |
|-------|-----------|----------|-----------|-------------|-------------|
| 1     | `<n>`     | `<n>`    | `<n>`     | `<initial>` | `<ISO8601>` |
