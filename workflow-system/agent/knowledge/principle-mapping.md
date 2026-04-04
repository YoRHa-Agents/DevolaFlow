---
id: "agent/knowledge/principle-mapping"
version: "1.0.0"
purpose: >
  Maps how the DevolaFlow workflow system embeds software engineering
  principles (SOLID, TDD, Clean Architecture, DDD) into its stage
  configuration, gate scoring, and code-rules integration points.
triggers:
  - "How does the workflow enforce SOLID principles"
  - "Where is TDD embedded in the workflow"
  - "How are engineering principles checked"
tier: 3
token_estimate: 2600
last_updated: "2026-04-04"
---

# Software Engineering Principle Mapping

## Overview

The DevolaFlow workflow system does not merely recommend software engineering
principles — it embeds them structurally into stage definitions, gate scoring
dimensions, convergence loop phases, and code-rules integration. This document
maps each major principle family to its enforcement mechanism.

## SOLID Principles → Architecture Review Dimension

SOLID principles are enforced through the `architecture` dimension of the
gate composite score (weight: 0.20) and through the `solid_review` gate
check in convergence loops.

### Principle-to-Gate Mapping

| SOLID Principle | Gate Check | Review Dimension | Enforcement Point |
|----------------|-----------|-----------------|-------------------|
| **Single Responsibility (SRP)** | `solid_review.single_responsibility` | Module has one reason to change | Convergence Phase 7 (Final Review) |
| **Open-Closed (OCP)** | `solid_review.open_closed` | Extension without modification | Convergence Phase 7 |
| **Liskov Substitution (LSP)** | `solid_review.liskov` | Subtypes substitutable for base types | Convergence Phase 7 |
| **Interface Segregation (ISP)** | `solid_review.interface_segregation` | No client forced to depend on unused methods | Convergence Phase 7 |
| **Dependency Inversion (DIP)** | `solid_review.dependency_inversion` | Depend on abstractions, not concretions | Convergence Phase 7 |

### Score Calculation

Each SOLID principle is scored 0–100 by the Review Agent in Phase 7 of
the convergence loop. The aggregate `solid_review.quality_score` is the
mean of all 5 principle scores:

```
solid_review.quality_score = mean(SRP, OCP, LSP, ISP, DIP)

Example:
  SRP: 90, OCP: 85, LSP: 90, ISP: 85, DIP: 88
  quality_score = (90 + 85 + 90 + 85 + 88) / 5 = 87.6

This feeds into the composite:
  architecture dimension = 87.6 × 0.20 = 17.52
```

### Code-Rules Integration

SOLID principles are loaded when `quality_focus` includes `"maintainability"`:

```yaml
applicable_rules:
  loading_strategy: "full"
  quality_focus: ["maintainability"]
  # Loads Layer 4 maintainability rules which include:
  # - Max function/method length
  # - Max class responsibility count
  # - Coupling metrics (afferent/efferent)
  # - Interface size limits
  # - Dependency direction checks
```

## TDD → Implement Stage Configuration

Test-Driven Development is embedded in the Implement Team's standard workflow
and in the convergence loop structure.

### TDD in Implementation Tasks

The Implement Team workflow (design_agent_hierarchy.md §4.3) includes
testing as step 5 of 7, and the task output contract requires `tests_written`:

```
Implement Team Standard Workflow:
  1. ORIENT      → Read task spec, design reference
  2. LOAD_RULES  → Load applicable code-rules
  3. SCAFFOLD    → Create file structure, boilerplate
  4. IMPLEMENT   → Write the implementation code
  5. UNIT_TEST   → Write unit tests for implemented code  ← TDD integration
  6. VERIFY      → Run build and lint check
  7. SELF-CHECK  → Review against MUST rules; fix violations
```

### TDD Configuration in TaskDispatch

When TDD is desired, the `task_type` field drives test-first behavior:

| Task Type | Test Strategy | Enforced By |
|-----------|--------------|-------------|
| `new_feature` | Tests written alongside implementation (steps 4–5 interleaved) | Implement Agent workflow |
| `bug_fix` | Regression test written BEFORE fix (test must fail against unfixed code) | Acceptance criterion in TaskDispatch |
| `refactoring` | Existing tests must pass before AND after refactoring | Test Agent in convergence Phase 3 |

### Gate Enforcement of Testing

The `test_quality` dimension (weight: 0.30) in the composite score enforces
test discipline:

```
test_quality = min(pass_rate × 100, coverage_pct)

Gate pass requires:
  - coverage >= coverage_threshold (default 80%)
  - zero test failures (blocker-severity)
```

## Clean Architecture → Dependency Direction Checking

Clean Architecture principles (dependency rule, layer boundaries) are
enforced through the architecture review dimension and through specific
code-rules.

### Dependency Rule Enforcement

The Review Agent checks dependency direction during SOLID review (Phase 7):

| Layer | Allowed Dependencies | Violation Severity |
|-------|---------------------|-------------------|
| Domain/Core | None (pure, no external deps) | `blocker` if depends on infrastructure |
| Application/Use Cases | Domain only | `critical` if depends on infrastructure |
| Interface/Adapters | Application + Domain | `major` if bypasses application layer |
| Infrastructure | Any (outermost ring) | (no restrictions) |

### Code-Rules Integration

When `quality_focus` includes `"maintainability"`, the following Clean
Architecture rules are loaded:

- **Dependency direction:** Imports must flow inward (infrastructure → domain)
- **No framework leaks:** Domain layer must not import framework types
- **Port-adapter pattern:** External dependencies accessed through interfaces
- **Use case isolation:** Each use case function operates on domain types only

### Stage-Level Enforcement

In `design-only` and `full-pipeline` workflows, the Design stage produces
an architecture diagram that the Review stage validates against Clean
Architecture principles. The design_reference_excerpt in TaskDispatch
provides the intended architecture to the Review Agent.

## DDD → Domain Model Alignment in Design Stage

Domain-Driven Design concepts influence the Design stage and are checked
during design review.

### DDD Concept Mapping

| DDD Concept | Workflow Integration | Enforcement Point |
|-------------|---------------------|-------------------|
| **Bounded Context** | Maps to module boundaries in design doc | Design review: modules have clear boundaries |
| **Aggregate Root** | Design specifies aggregate boundaries | Review: no direct access to aggregate internals |
| **Value Object** | Design specifies immutable types | Implement: value objects are immutable |
| **Domain Event** | Design specifies event contracts | Review: events follow contract schema |
| **Ubiquitous Language** | Naming conventions in project config | Code-rules: naming must match domain glossary |
| **Repository Pattern** | Design specifies data access interfaces | Review: persistence behind repository interface |

### Design Stage Checks

The Design Team's output contract includes `requirements_coverage_pct`,
ensuring domain concepts from requirements are traced through the design.
The Review Team validates that design artifacts align with DDD patterns
when the project's design_scope indicates domain modeling.

### Code-Rules Integration

DDD rules are loaded as part of the `maintainability` quality focus:

- **Naming conventions:** Class and method names must use domain vocabulary
- **Aggregate boundaries:** Public API surface limited to aggregate root methods
- **Value object immutability:** No setter methods on value objects
- **Repository interface:** Data access through defined repository interfaces

## Principle-to-Workflow Stage Matrix

This matrix shows where each principle family has its primary enforcement
point across the 7 stages of a full-pipeline workflow:

| Principle | Design | Plan | Implement | Review | Test | TestGate | Release |
|-----------|--------|------|-----------|--------|------|----------|---------|
| **SOLID** | Design for SRP/ISP | — | Follow DIP/OCP | Score all 5 | — | Composite check | — |
| **TDD** | — | Plan test tasks | Write tests | — | Run tests | Coverage gate | — |
| **Clean Arch** | Define layers | Plan per layer | Respect boundaries | Check deps | — | — | — |
| **DDD** | Model domain | — | Use domain types | Check naming | — | — | — |
| **Code Rules** | — | Select strategy | Load & follow | Load & check | — | Quality score | — |

Legend: Bold = primary enforcement, regular = secondary check.

## Integration with Gate Profiles

Different gate profiles emphasize different principle families:

| Profile | SOLID Emphasis | TDD Emphasis | Clean Arch | DDD |
|---------|---------------|-------------|------------|-----|
| `relaxed` | Advisory only | Coverage ≥ 60% | Not checked | Not checked |
| `standard` | Scored, threshold 85 | Coverage ≥ 80% | Basic dep check | Naming only |
| `strict` | Scored, threshold 90 | Coverage ≥ 85% | Full dep audit | Full model check |
| `audit` | Scored, threshold 95 | Coverage ≥ 90% | Full + report | Full + report |

## Principle Violation → Convergence Loop Feedback

When principles are violated, the convergence loop provides structured
feedback through the review → fix cycle:

```
Round N, Phase 7 (Final Review):
  Review Agent detects DIP violation:
    F012: "ConfigManager directly instantiates FileStorage
           instead of depending on StorageBackend trait"
    severity: major
    category: design_compliance
    rule_id: "solid/dependency-inversion-001"
    suggestion: "Inject StorageBackend via constructor parameter"

Round N, Phase 8 (Fix):
  Implement Agent receives F012 with rule context
  Refactors ConfigManager to accept StorageBackend trait object
  Adds constructor injection pattern

Round N+1, Phase 7 (Re-review):
  Review Agent confirms F012 resolved
  DIP score improves: 75 → 88
  Architecture dimension improves in composite score
```

This feedback loop ensures principles are not just aspirational — they
are iteratively enforced through concrete review findings with traceable
rule IDs and measurable score improvements.
