---
id: "agent/knowledge/principle-mapping"
version: "2.0.0"
purpose: >
  Maps SOLID, TDD, Clean Architecture, and DDD to checklist assertions,
  L2 Task evidence, code rules, and archive-readiness evaluation.
triggers:
  - "enforcing SOLID or Clean Architecture"
  - "encoding TDD in a checklist"
  - "reviewing DDD alignment"
tier: 3
token_estimate: 1500
last_updated: "2026-08-25"
---

# Software Engineering Principle Mapping

## 1. Enforcement Model

Principles become executable only when translated into:

1. a goal or checklist assertion;
2. a bounded verification command/metric/review question;
3. applicable rule hints in TaskDispatch;
4. L2 evidence with located findings;
5. L0 adjudication and, at archive, readiness evaluation.

Checklist seeds may suggest these assertions. Seed `source_stages` preserve
historical provenance and do not define execution order.

## 2. Principle Families

| Family | Checklist expression | L2 evidence | Primary role |
|---|---|---|---|
| SOLID | named responsibility/dependency assertions | located design/code findings | Review |
| TDD | red/green or before/after test assertion | exact commands and counts | Implement/Test |
| Clean Architecture | allowed dependency-direction assertion | import/dependency graph evidence | Design/Review |
| DDD | glossary/model boundary assertion | traced domain terms and interfaces | Design/Review |

L2 emits evidence only. It does not author Task Quality Scores.

## 3. SOLID

| Principle | Observable review question |
|---|---|
| SRP | Does the changed unit have one dispatched reason to change? |
| OCP | Can the required variation be added without unrelated edits? |
| LSP | Do subtype behaviors preserve the base contract? |
| ISP | Is any consumer forced to depend on unused operations? |
| DIP | Do high-level policies depend on abstractions? |

Enable through:

```yaml
rules:
  strategy: full
  lang: python
  focus: [maintainability]
```

Review evidence includes path/line, violated principle/rule ID, consequence,
and a testable remediation. Severity follows repository policy rather than a
hardcoded principle score.

## 4. TDD and Regression Discipline

| Change kind | Checklist contract |
|---|---|
| Feature | behavioral test covers each public outcome |
| Bug fix | regression reproduces the defect before the fix and passes after |
| Refactor | same behavioral suite passes before and after |
| Migration | compatibility fixtures cover old/new boundary behavior |

Example:

```markdown
- [ ] C-G2.1 (P0) Unicode destination path no longer raises
      verify: `python -m pytest tests/test_paths.py::test_unicode_destination -q`
      depends: []
```

The L2 Task reports the exact command, exit status, count, and output digest.
If a true pre-fix run is unavailable, it states that limitation rather than
claiming a red/green sequence.

## 5. Clean Architecture

| Area | Allowed dependency direction |
|---|---|
| Domain/Core | no infrastructure/framework dependency |
| Application/Use cases | domain abstractions |
| Adapters | application + domain contracts |
| Infrastructure | implements inward-facing interfaces |

Enforcement can use import-boundary tests, architecture linters, or located
review findings. A Design Task records intended boundaries; a later Review
Task verifies them. L1 may dispatch these sequentially when the review depends
on the design artifact.

## 6. Domain-Driven Design

| DDD concept | Artifact/check |
|---|---|
| Bounded Context | module/context boundary and dependency contract |
| Aggregate Root | public mutation boundary |
| Value Object | immutable value semantics |
| Domain Event | typed event contract |
| Ubiquitous Language | canonical project-specific glossary term |
| Repository | domain-facing persistence interface |

Vocabulary belongs in `CONTEXT.md`; behavior belongs in the active
`spec.md` delta. A Design/Review Task checks naming against the domain
glossary and reports avoid-listed aliases. General programming concepts do
not enter the glossary.

## 7. Checklist-Round Composition

Principles do not force a universal sequence. A typical complex round plan is:

```text
Wave 1: independent Design/Research Tasks
Wave 2: Implement Tasks with disjoint ownership
Wave 3: Test and Review Tasks whose dependencies are satisfied
```

L0 may defer later waves or items to another round. Limits remain 5 Tasks per
wave and 7 waves per round.

When evidence fails:

1. L2 reports a located finding.
2. L1 aggregates it without rewriting the artifact.
3. L0 keeps/reopens the checklist item.
4. L0 adds at most 5 severity-filtered reinforcement rules.
5. A later Task performs targeted remediation.

Two no-progress rounds escalate Task → Wave → Project → Human.

## 8. Readiness Evaluation

Per-round PASS means selected checklist items have valid evidence and zero
blockers. Composite is trend-only during rounds.

Archive readiness evaluates the repository's configured dimensions. Principle
evidence commonly contributes to:

- architecture rationality;
- code quality;
- test adequacy;
- maintainability;
- compatibility;
- performance impact.

Readiness threshold is 8.5 for lite/minor and 9.0 for full/major. L0 computes
the evaluation from artifacts; L2 does not self-score.

## 9. Compatibility Names

Legacy verbose dispatches call the rule block `applicable_rules` and archived
documents may organize principles by named workflow phases. Preserve those
code symbols and archive semantics. Current writers use lean `rules` plus
checklist item dependencies.

## 10. See Also

- `knowledge/code-rules-mapping.md`
- `references/team-roles.md`
- `references/decomposition-gate.md`
- `references/domain-awareness.md`
- `references/evaluator-rosetta.md`
