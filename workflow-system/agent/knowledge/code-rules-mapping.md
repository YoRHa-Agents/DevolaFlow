---
id: "agent/knowledge/code-rules-mapping"
version: "1.0.0"
purpose: >
  Maps how the DevolaFlow workflow system integrates with a code-rules
  system for context-aware rule loading, quality enforcement during
  implementation, and compliance checking during review.
triggers:
  - "How are code rules loaded during implementation"
  - "How does the review agent use code rules"
  - "What rules apply to my task"
tier: 3
token_estimate: 2800
last_updated: "2026-04-04"
---

# Code-Rules Integration Mapping

## Overview

The DevolaFlow workflow system integrates with an external code-rules system
(such as the one at `/home/agent/workspace/code-rules`) to provide
context-aware coding standards to Task Agents. Rules flow into the system
through the `applicable_rules` field of `TaskDispatch` messages and are
consumed by Implement and Review team agents.

## Rule Loading During the Implement Stage

### Loading Strategies

The `applicable_rules.loading_strategy` field in TaskDispatch controls how
many rules are loaded into the Task Agent's context window. The strategy
is selected by the Stage Agent based on task complexity and available
context budget.

| Strategy | Rules Loaded | Context Cost | Use When |
|----------|-------------|--------------|----------|
| `minimal` | Core rules only (universal MUST constraints) | ~500 tokens | Hotfix tasks, trivial changes, context-constrained tasks |
| `standard` | Core + language-specific + task-type rules | ~2000 tokens | Normal implementation tasks, most code changes |
| `full` | Core + language + task-type + quality-focus rules | ~5000 tokens | Complex features, security-critical code, audit-profile gates |

### Rule Categories and Loading Order

Rules are loaded in a layered order. Each layer adds specificity:

```
Layer 1: Core Rules (always loaded)
├── universal MUST constraints (e.g., no silent failures, brace rules)
├── project-wide conventions (naming, file organization)
└── error handling patterns

Layer 2: Language Rules (loaded when language is specified)
├── language idioms (e.g., Rust ownership patterns, Python type hints)
├── standard library preferences
└── language-specific anti-patterns

Layer 3: Task-Type Rules (loaded for standard/full strategies)
├── new_feature: scaffolding patterns, test-first workflow
├── bug_fix: regression test requirement, minimal change principle
├── refactoring: behavior preservation, incremental change strategy
└── migration: compatibility checks, fallback patterns

Layer 4: Quality-Focus Rules (loaded for full strategy only)
├── security: input validation, injection prevention, auth checks
├── performance: complexity bounds, allocation patterns, caching
├── maintainability: SOLID compliance, coupling limits, documentation
├── accessibility: WCAG patterns, ARIA requirements
└── testability: dependency injection, mock-friendly interfaces
```

### Context Injection Template Integration

The `applicable_rules` field maps directly to the context injection template
defined in the agent hierarchy design (§6.3). Here is how rules flow into
a Task Agent's context:

```yaml
context_injection:
  # ... identity, task, context, files sections ...

  rules:
    loading_strategy: "standard"    # from TaskDispatch.context.applicable_rules
    language: "rust"                # determines Layer 2 selection
    task_type: "new_feature"        # determines Layer 3 selection
    quality_focus:                  # determines Layer 4 selection (full only)
      - "security"
      - "maintainability"

  # The Task Agent loads rules in this order:
  # 1. Read core rules (always)
  # 2. Read rust-specific rules (language = "rust")
  # 3. Read new_feature rules (task_type = "new_feature")
  # 4. If full: read security + maintainability focus rules
```

### Stage-Level Rule Configuration

The Stage Agent configures `applicable_rules` for each wave based on the
stage's scope and the project's gate profile:

| Gate Profile | Default Strategy | Quality Focus Dimensions |
|-------------|-----------------|-------------------------|
| `relaxed` | `minimal` | (none) |
| `standard` | `standard` | `["maintainability"]` |
| `strict` | `full` | `["security", "maintainability", "performance"]` |
| `audit` | `full` | `["security", "maintainability", "performance", "testability"]` |

## Quality Focus Dimensions

Each quality focus dimension maps to specific rule categories and review
checklist items. These dimensions drive both implementation guidance and
review scoring.

### Dimension Mapping Table

| Dimension | Implement Rules | Review Checklist | Gate Weight |
|-----------|----------------|------------------|-------------|
| **security** | Input validation, parameterized queries, auth checks, secret handling | OWASP top 10 scan, injection points, auth flows, data exposure | Part of `code_review` (0.30) |
| **maintainability** | SOLID principles, max function length, coupling limits, naming conventions | Cyclomatic complexity, code duplication, documentation coverage | Part of `architecture` (0.20) |
| **performance** | Complexity bounds, allocation patterns, caching strategies, lazy evaluation | Hot path analysis, memory profiling, benchmark regression | Part of `benchmark` (0.20) |
| **correctness** | Exhaustive matching, null safety, boundary checks, error propagation | Logic review, edge case coverage, invariant verification | Part of `code_review` (0.30) |
| **testability** | Dependency injection, interface segregation, mock-friendly design | Test coverage gaps, test isolation, fixture quality | Part of `test_quality` (0.30) |

### Composite Score Dimension Alignment

The gate's composite score formula uses 4 dimensions with fixed weights.
Quality focus rules influence scores through these mappings:

```
composite = Σ(dimension_score × weight)

  test_quality   × 0.30  ← influenced by: correctness, testability rules
  code_review    × 0.30  ← influenced by: security, correctness rules
  architecture   × 0.20  ← influenced by: maintainability rules
  benchmark      × 0.20  ← influenced by: performance rules
```

## Review Agent Rule Usage

### Rule-Based Compliance Checking

The Review Agent loads rules using the same `applicable_rules` configuration
as the Implement Agent, then uses them as a review checklist:

```
Review Agent Workflow:
  1. LOAD_RULES  → Load applicable code-rules per loading_strategy
  2. STRUCTURAL  → Check architecture against maintainability rules
  3. BEHAVIORAL  → Check logic against correctness and security rules
  4. STYLISTIC   → Check conventions against language and core rules
  5. SCORE       → Calculate quality_score using severity-weighted formula
  6. REPORT      → Classify each finding by severity and rule_id
```

### Finding-to-Rule Mapping

Each review finding links back to a specific rule when applicable:

```yaml
findings:
  - finding_id: "F003"
    severity: "critical"
    category: "security"
    location: "src/sync/engine.rs:42"
    description: "User-supplied path not sanitized before file system access"
    suggestion: "Use canonicalize() and validate against allowed base paths"
    rule_id: "security/input-validation-001"
```

The `rule_id` field traces findings to the originating code rule, enabling:
- Targeted rule refinement when false positives occur
- Rule coverage analysis across review rounds
- Cross-project compliance reporting

### Severity Classification from Rules

Rules define their own severity level, which the Review Agent uses for
finding classification:

| Rule Severity | Review Finding Severity | Score Impact |
|--------------|------------------------|--------------|
| `MUST` | `blocker` (if violated) | -25 per finding |
| `MUST` | `critical` (if partially violated) | -15 per finding |
| `SHOULD` | `major` (if violated without justification) | -5 per finding |
| `SHOULD` | `minor` (if deviated with justification) | -1 per finding |
| `MAY` | `info` (advisory) | 0 per finding |

## Cross-Stage Rule Consistency

Rules must be consistent across the implement → review → fix cycle within
a convergence loop. The Stage Agent ensures:

1. **Same rules for implement and review:** The Review Agent loads the same
   `applicable_rules` configuration that the Implement Agent used, so
   findings are fair and actionable.

2. **Rules don't change mid-convergence:** The `applicable_rules` for a
   stage are frozen at stage dispatch time. Adding new rules mid-loop
   would invalidate prior review findings.

3. **Fix tasks inherit parent rules:** When the Implement Agent receives
   fix tasks during convergence, it loads the same rules as the original
   implementation task.

## Integration Points Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CODE-RULES INTEGRATION FLOW                      │
│                                                                     │
│  Project Config                                                     │
│    └── gate_profile (standard)                                      │
│         └── default loading_strategy (standard)                     │
│              └── default quality_focus (["maintainability"])         │
│                                                                     │
│  Stage Agent                                                        │
│    └── Configures applicable_rules per task                         │
│         └── Includes in TaskDispatch.context.applicable_rules       │
│                                                                     │
│  Implement Agent (L3)                                               │
│    └── Loads rules per loading_strategy                             │
│         ├── Core rules (always)                                     │
│         ├── Language rules (if specified)                            │
│         ├── Task-type rules (standard+)                              │
│         └── Quality-focus rules (full only)                         │
│    └── Follows rules during implementation                          │
│    └── Self-checks against MUST rules before reporting              │
│                                                                     │
│  Review Agent (L3)                                                  │
│    └── Loads same rules as Implement Agent                          │
│    └── Uses rules as review checklist                               │
│    └── Tags findings with rule_id for traceability                  │
│    └── Calculates quality_score using severity weights              │
│                                                                     │
│  Gate Evaluation (L1)                                               │
│    └── Aggregates quality_score into composite_score                │
│    └── Checks blocker/critical counts against thresholds            │
│    └── PASS/FAIL decision feeds back into convergence loop          │
└─────────────────────────────────────────────────────────────────────┘
```
