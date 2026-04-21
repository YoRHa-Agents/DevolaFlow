---
title: "Workflow Types Catalog"
description: "17 built-in workflow types with selection guidance."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-21T19:12:15Z"
source_version: "7.8.0"
---

# Workflow Types Catalog

17 built-in workflow types with selection guidance.

## Workflow Selection

DevolaFlow automatically selects the right workflow based on your prompt. You can also specify one explicitly.

**Selection heuristics:**
- Urgency signals ("urgent", "ASAP", "production down") → `hotfix`
- "From scratch" / "new project" → `full-pipeline`
- Question-form phrasing ("what", "how", "which") → `research-only`
- Explicit type mention → direct match (highest priority)

## All 17 Built-in Workflow Types

### Discover Workflows

#### `research-only`
**When to use**: Survey prior art, compare alternatives, evaluate options.
**Stages**: research → compare → report
**Teams**: Research (primary)
**Example prompt**: `"Research the best ORM for our Python project — compare SQLAlchemy, Peewee, and Tortoise"`

#### `onboarding`
**When to use**: New contributor joining, understanding an unfamiliar codebase, resuming a dormant project.
**Stages**: analyze (codebase survey) → document (onboarding docs) → setup (dev environment) → verify (smoke tests)
**Teams**: Research, Implement, Test
**Example prompt**: `"I'm new to this project — help me understand the codebase and set up my dev environment"`

### Optimize Workflows

#### `skill-optimization`
**When to use**: Optimize agent skills, benchmark context density, improve information routing.
**Stages**: survey → profile → optimize → benchmark → iterate → document
**Teams**: Research, Implement, Test, Review
**Example prompt**: `"Optimize the DevolaFlow skill — benchmark context density and reduce noise"`

### Shape Workflows

#### `design-only`
**When to use**: Architecture decisions, API design, schema design.
**Stages**: research → design → review
**Teams**: Design (primary), Review
**Example prompt**: `"Design the API for a multi-tenant notification service"`

#### `RDRR` (Research-Design-Review-Refine)
**When to use**: Iterative design that needs research backing and multiple review rounds.
**Stages**: research → design → review → refine (loop)
**Teams**: Research, Design, Review (all primary)
**Example prompt**: `"Design a caching architecture — research options first, then iterate the design"`

### Build Workflows

#### `hotfix`
**When to use**: Production bug, urgent fix, security patch.
**Stages**: triage → fix → test → release
**Teams**: Implement (primary), Test
**Example prompt**: `"Fix the login timeout bug — users get 500 errors after 30 seconds"`

#### `refactoring`
**When to use**: Tech debt, code restructuring, simplification.
**Stages**: scope → plan → implement → test → review
**Teams**: Implement, Test (both primary)
**Example prompt**: `"Refactor the payment module to use the strategy pattern"`

#### `migration`
**When to use**: Upgrade frameworks, port between systems, database migrations.
**Stages**: assess → plan → implement → validate → cutover
**Teams**: Research, Implement, Test
**Example prompt**: `"Migrate from Express.js to Fastify — keep all existing endpoints"`

#### `performance-optimization`
**When to use**: Slow app, high latency, memory issues, build time optimization.
**Stages**: profile → design (optimization plan) → optimize → benchmark → validate
**Teams**: Research, Design, Implement, Test
**Example prompt**: `"Our API response time is >2 seconds — profile and optimize the hot paths"`

#### `dependency-setup`
**When to use**: Setting up dev environment, adding major dependencies, configuring tooling.
**Stages**: research → plan (dependency graph) → configure → verify
**Teams**: Research, Design, Implement, Test
**Example prompt**: `"Set up Docker development environment with hot reloading for our Python API"`

#### `feature-enhancement`
**When to use**: Adding to existing features, extending functionality.
**Stages**: scope → design → plan → implement → review → test → release
**Teams**: All (Design and Implement primary)
**Example prompt**: `"Add dark mode support to the settings page"`

#### `full-pipeline`
**When to use**: Greenfield features, new projects, anything requiring the full lifecycle.
**Stages**: design → plan → implement → review → test → refine → gate → release
**Teams**: All (all primary)
**Example prompt**: `"Build a user authentication system with OAuth2, JWT, and role-based access"`

### Verify Workflows

#### `security-audit`
**When to use**: Vulnerability scanning, compliance checks, CVE remediation.
**Stages**: threat-model → scan → analyze → remediate → verify
**Teams**: Research, Implement, Test, Review (all active)
**Example prompt**: `"Run a security audit on our authentication module — check for OWASP Top 10"`

### Deliver Workflows

#### `documentation`
**When to use**: Writing or updating docs, README, API references, tutorials.
**Stages**: survey → author → review
**Teams**: Research, Review
**Example prompt**: `"Write comprehensive API documentation for the payments module"`

#### `demo-showcase`
**When to use**: Building demos for stakeholders, interactive showcases, conference presentations.
**Stages**: research → storyboard (design) → build-demo → demo-review → polish → package
**Teams**: Research, Design, Implement, Review
**Example prompt**: `"Build an interactive demo showcasing our new dashboard — make it presentation-ready"`

### Composite Workflows

#### `spike-poc`
**When to use**: Testing feasibility, prototyping, evaluating new tech.
**Stages**: research (hypothesis) → prototype → evaluate
**Teams**: Research, Implement
**Example prompt**: `"Prototype real-time collaboration using CRDTs — is it feasible for our scale?"`

#### `self-update`
**When to use**: Track external reference dependencies and integrate improvements.
**Stages**: check-refs → research-updates → decompose → integrate → test → evaluate
**Teams**: Research, Implement, Test
**Example prompt**: `"update refs"`, `"self-update"`, `"check references"`

## Quick Reference Table

| Type | Trigger Keywords | Stages | Gate Profile |
|------|-----------------|--------|-------------|
| `research-only` | research, compare, survey | 3 | — |
| `design-only` | design, architect, API spec | 3 | standard |
| `hotfix` | fix bug, broken, crash, SEV1 | 4 | relaxed |
| `refactoring` | refactor, clean up, tech debt | 5 | standard |
| `migration` | migrate, upgrade, port | 5 | standard |
| `spike-poc` | prototype, experiment, PoC | 3 | — |
| `documentation` | write docs, README, guide | 3 | relaxed |
| `security-audit` | security, audit, CVE | 5 | strict |
| `feature-enhancement` | add to, extend, enhance | 7 | standard |
| `full-pipeline` | from scratch, new project | 8 | standard |
| `RDRR` | design with research, ADR | 4 (loop) | standard |
| `demo-showcase` | demo, showcase, presentation | 6 | relaxed |
| `performance-optimization` | slow, optimize, benchmark | 5 | standard |
| `dependency-setup` | setup, install, configure env | 4 | relaxed |
| `onboarding` | new to project, getting started | 4 | — |
| `skill-optimization` | optimize skill, benchmark context | 6 | convergence |
| `self-update` | update refs, self-update, check references | 6 | standard |
