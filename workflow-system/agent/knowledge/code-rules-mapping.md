---
id: "agent/knowledge/code-rules-mapping"
version: "2.0.0"
purpose: >
  Maps repository rules into bounded L2 Implement and Review Task contexts
  without duplicating the rule source of truth.
triggers:
  - "loading rules for an implementation task"
  - "loading rules for a review task"
  - "choosing a rule-loading strategy"
tier: 3
token_estimate: 1500
last_updated: "2026-08-25"
---

# Code-Rules Integration Mapping

## 1. Current Flow

```text
.rules/*.mdc (source)
  → compiled AGENTS.md / Cursor surface
  → L0 selects relevant rule dimensions
  → L1 writes compact TaskDispatch.rules
  → L2 Implement or Review Task loads its bounded slice
  → StatusReport carries evidence and rule-linked findings
```

The rule corpus is not copied into checklist seeds. Seeds can suggest a
strategy or quality focus as decomposition knowledge; `source_stages` are
provenance and do not prescribe rule-loading phases.

## 2. Dispatch Shape

Canonical lean field:

```yaml
rules:
  strategy: minimal | standard | full
  lang: python
  focus: [security, maintainability]
```

Legacy verbose callers may expose the same data as
`context.applicable_rules`. Treat that name as a compatibility code symbol;
new writers use `rules`.

L1 selects the strategy from checklist scope, risk, and the L2 8K context
budget. L0/L1 do not execute implementation or review work.

## 3. Loading Strategies

| Strategy | Rule slice | Typical use |
|---|---|---|
| `minimal` | Immutable/core MUST rules plus owned-file constraints | trivial fix, narrow hotfix |
| `standard` | Core + language + task-type rules | normal implementation/review |
| `full` | Standard + explicit quality-focus rules | security, migration, audit, complex work |

Priority order:

1. Soul/Architecture invariants;
2. repository conventions and ownership;
3. language rules;
4. task-type rules;
5. dispatched quality-focus rules.

Critical rules are never dropped to fit budget. Remove supplementary prose or
escalate an underspecified dispatch.

## 4. Quality-Focus Dimensions

| Focus | Implement guidance | Review evidence |
|---|---|---|
| Security | validation, authorization, secret handling | located exploit/risk findings |
| Correctness | boundaries, invariants, error propagation | failing case or logic trace |
| Maintainability | dependency direction, naming, cohesion | specific coupling/duplication evidence |
| Performance | measured hot paths, bounded complexity | benchmark/profile delta |
| Testability | interfaces, deterministic dependencies | coverage/gap evidence |
| Accessibility | semantic structure, keyboard/ARIA behavior | standard and failing interaction |

Focus dimensions guide evidence; L2 does not self-author a Task Quality Score.

## 5. Implement Task Usage

An L2 Implement Task:

1. reads the dispatched checklist assertion and owned files;
2. loads the selected rule slice;
3. implements the smallest compliant change;
4. runs bounded verification;
5. reports exact commands, results, and deviations.

Example:

```yaml
self_check:
  plan_artifact: "inline: reproduce → patch → verify"
  goal_anchor: "C-G2.1: missing config → explicit error"
  simplicity: "none"
  conflicts: []
  conventions: []
```

Any MUST-rule violation blocks `DONE`. A justified SHOULD deviation is
reported as a warning with its rule ID.

## 6. Review Task Usage

An L2 Review Task loads the same rule snapshot used by the artifact's
Implement Task. It emits located evidence:

```yaml
findings:
  - id: F003
    severity: critical
    category: security
    location: "src/sync/engine.rs:42"
    description: "user path reaches filesystem without base-path check"
    suggestion: "canonicalize and validate against allowed root"
    rule_id: "security/input-validation-001"
```

`rule_id` enables targeted remediation and false-positive analysis. Findings
use repository severity policy; they are not converted into an L2-authored
score.

## 7. Cross-Round Consistency

Rule snapshots remain stable for one checklist item across implement, review,
and remediation dispatches:

1. L1 records the same `rules` block in successor dispatches.
2. Review evaluates the rules the implementer actually received.
3. Reinforcement adds at most 5 finding-specific mandates; it does not replace
   the base snapshot.
4. A material rule change reopens planning or creates a new checklist item.
5. L0 records the result in `stage.md` round history and evidence.

This prevents moving-goalpost review while allowing explicit later-round
reinforcement.

## 8. Ownership and Handoff

- L0 Project owns checklist and round adjudication.
- L1 Wave owns rule-slice dispatch and evidence aggregation.
- L2 Task owns implementation/review evidence.
- Reports travel Task → Wave → Project.
- Unresolvable conflicts escalate Project → Human.

Rules and findings move through lean TaskDispatch/StatusReport artifacts.
Agents never share mutable rule state.

## 9. External Rule Corpora

If a project uses an external rule corpus, cite its remote URL in
agent-facing artifacts. Never hardcode a local clone path. The repository's
`.rules/` directory remains the source of truth for DevolaFlow governance.

## 10. See Also

- `references/team-roles.md`
- `references/message-schemas.md`
- `references/context-isolation.md`
- `schemas/lean-dispatch.yaml`
- `schemas/lean-report.yaml`
