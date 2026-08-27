---
id: "agent/references/pathfinder"
version: "1.0.0"
purpose: >
  Defines the read-only Pathfinder L2 role, its look-ahead scan protocol,
  structured report contract, and bounded remediation handoff.
triggers:
  - "selecting the Pathfinder L2 role"
  - "look-ahead harness reconnaissance"
  - "finding infrastructure gaps before a later wave"
tier: 2
token_estimate: 1800
dependencies:
  - "agent/SKILL.md"
  - "schemas/agent-workspace/pathfinder-report.yaml"
last_updated: "2026-08-27"
---

# Pathfinder

## Purpose
Pathfinder is the read-only L2 reconnaissance role for finding missing or
fragile infrastructure before a later implementation wave needs it. This
reference defines its look-ahead protocol, report contract, activation
heuristics, and handoff boundary.

## When to Load

Load this reference when selecting the Pathfinder L2 role or look-ahead harness reconnaissance.

## Body

### 1. Concept Overview

Pathfinder answers “what will block the next wave?” rather than “is the
current task ready to start?”. It is a sidecar-shaped L2 task: it may inspect
the repository, existing telemetry, schemas, fixtures, and prior artifacts,
but it does not implement product code, tests, or harness repairs.

The role is deliberately separate from:

- `preflight`, which authorizes the current change at t=0;
- `research`, which investigates a question or compares alternatives;
- `review`, which evaluates an already-produced result; and
- `harness-build`, which owns remediation after Pathfinder reports a gap.

Pathfinder may run interleaved with a wave. Its output is evidence for the
dispatcher, never an automatic mutation or an implicit approval.

### 2. Canonical Surfaces

The role is defined by these repository-relative surfaces:

- `workflow-system/agent/references/team-roles.md` — L2 role contract.
- `src/devolaflow/skills/pathfinder.py` — natural-language activation.
- `workflow-system/agent/context_profiles.yaml` — bounded read-only context.
- `workflow-system/agent/templates/seeds/pathfinder.yaml` — reconnaissance
  checklist knowledge.
- `schemas/agent-workspace/pathfinder-report.yaml` — report artifact schema.
- `.local/.agent/active/<change-id>/pathfinder_report.md` — report location.
- `src/devolaflow/harness/gap.py` — gap classification and severity vocabulary.
- `src/devolaflow/agent_workspace/handoff.py` — append-only artifact handoff.

The dispatch schema and plugin registry are intentionally unchanged. The
task type is a specialization selected by `TaskDispatch.task.type`.

### 3. Execution Protocol

1. Read the task goal, owned-file boundary, current checklist, and any
   predecessor evidence.
2. Establish the look-ahead horizon: the next wave, the next gate, or the
   next artifact that depends on the missing capability.
3. Inspect only repository evidence. Use existing gap and harness vocabulary
   where applicable; do not infer a gap solely from an absence of prose.
4. Classify each finding as `BLOCKER`, `RISK`, `BACKLOG`, or `NO_GAP`.
5. Write or refresh `pathfinder_report.md` within the active change folder.
   Keep paths, IDs, errors, and metrics verbatim.
6. Return a structured `StatusReport` with the report path and item-keyed
   findings. Escalate only when a blocker cannot be resolved by a bounded
   harness-build task.

An initial scan inventories the whole relevant capability surface. An
incremental scan compares against the previous report and records only new,
changed, resolved, or still-open findings. The scan is bounded by the
dispatcher's max-iteration policy; Pathfinder must not become a polling loop.

Use the existing gap CLI to ground both scan modes:

```text
python -m devolaflow.harness gap --ledger .local/telemetry/harness.jsonl --repo . --output evidence/pathfinder_gap_round_<n>.json
python -m devolaflow.harness gap --ledger .local/telemetry/harness.jsonl --repo . --output evidence/pathfinder_gap_round_<n>.json --compare evidence/pathfinder_gap_round_<n-1>.json
```

The first command is the initial scan; the second is the incremental scan.

### 4. Report Contract

Every finding should state:

- `gap_id` — stable within the change folder;
- `severity` — one of the four classifications above;
- `horizon` — the wave or gate that is affected;
- `evidence` — repository-relative paths and verbatim observations;
- `impact` — the concrete downstream failure or rework;
- `suggested_owner` — normally `harness-build`, `test`, or `design`;
- `acceptance_signal` — the evidence that closes the finding.

`BLOCKER` findings must include a concrete affected horizon and a closure
signal. A report with no findings must still record the scan scope and the
evidence sources checked. The presence of the report is not itself a failure
or a request to alter the current dispatch.

### 5. Boundaries and Safety

- Pathfinder is read-only with respect to product and test implementation.
- It may write only its owned report and its append-only handoff artifact.
- It must not edit another agent's report, checklist, spec, or source files.
- It must not create a new environment flag, plugin, registry, or schema
  field to make a finding disappear.
- It must preserve the cached dispatch prefix because no dispatch shape change
  is needed for this role.
- A reported gap is a proposal for a separately owned task, not permission
  for Pathfinder to fix it.

### 6. Worked Examples

**Missing fixture before a test wave.** The next wave requires a deterministic
fixture, but the seed references a file that is absent. Report a `BLOCKER`
with the missing relative path, the consuming checklist item, and
`harness-build` as owner. Do not create the fixture.

**Stale baseline before evaluation.** The active harness baseline predates the
current cycle and no settlement artifact exists. Report a `RISK` when the
next step is exploratory, or a `BLOCKER` when W-16 comparison is a release
condition. Point to the exact baseline paths and the expected settlement
signal.

**No actionable gap.** If the relevant schemas, fixtures, baseline, and
verification command are present and current, emit `NO_GAP` with the checked
evidence. Do not manufacture work merely because the scan found ordinary
technical debt outside the look-ahead horizon.

## Cross-References

- `references/meta-framework.md` — workflow primitives
- `references/agent-hierarchy.md` — L0/L1/L2 layering
- `references/agent-workspace.md` — active change artifacts
- `references/harness-construction.md` — remediation task shape
- `references/message-schemas.md` — StatusReport and escalation envelopes

## History

- Scaffolded by `scripts/scaffold_reference.py` (D-X-2).
- Substantive Pathfinder contract landed for the v17.3.0 design cycle.
