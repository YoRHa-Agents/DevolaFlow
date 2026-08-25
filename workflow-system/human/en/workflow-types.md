---
title: "Checklist Seed Catalog"
description: "23 built-in checklist seeds plus the change-driven runtime."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T07:21:59Z"
source_version: "16.0.0"
---

# Checklist Seed Catalog

23 built-in checklist seeds plus the change-driven runtime.

## Seed Selection

DevolaFlow matches prompt intent to a checklist seed. You can also name a seed explicitly. The selected seed is materialized into user-confirmed goals and measurable checklist assertions before execution.

| Signal | Selected seed |
|--------|---------------|
| "urgent", "ASAP", "production down" | `hotfix` |
| "from scratch", "new project" | `full-pipeline` |
| Question-form phrasing such as "what", "how", "which" | `research-only` |
| Explicit seed name | Direct match |

## The 23 Built-in Checklist Seeds

All 23 seeds are **non-executable decomposition knowledge**. The primitive lists below are source provenance only: they explain where each seed's domain knowledge came from, but neither list order nor source IDs prescribe runtime order.

| Seed | Use when | Primitive provenance (non-executable) |
|------|----------|---------------------------------------|
| `hotfix` | Urgent defect diagnosis and bounded remediation | analyze, implement, test, release |
| `research-only` | Compare alternatives and produce an evidenced recommendation | research, analyze, validate |
| `design-only` | Create an architecture, API, or schema with review evidence | research, design, review |
| `documentation-only` | Survey, author, and review documentation | research, implement, review |
| `spike-poc` | Test feasibility with a bounded throwaway prototype | research, implement, validate |
| `refactoring` | Restructure code while preserving behavior | analyze, plan, implement, test, review |
| `feature-enhancement` | Extend an existing feature through release evidence | design, plan, implement, review, test, release |
| `full-pipeline` | Build a greenfield or end-to-end capability | design, plan, implement, review, test, refine, gate, release |
| `performance-optimization` | Improve a measured latency, memory, or throughput problem | analyze, design, implement, test, validate |
| `security-audit` | Threat-model, scan, remediate, and verify security | research, analyze, implement, validate |
| `research-design-review-refine` | Iterate on research-backed design | research, design, review, refine |
| `dependency-setup` | Configure an environment, dependency, or toolchain | research, plan, implement, verify |
| `onboarding` | Help a contributor understand and verify a repository setup | analyze, implement, verify |
| `demo-showcase` | Build a presentation-ready demonstration | research, design, implement, review, refine, release |
| `product-verification` | Verify visual, interaction, accessibility, and acceptance quality | analyze, design, implement, test, verify, review, validate |
| `entropy-cleanup` | Find and repair stale documentation or drift | analyze, plan, review, implement |
| `migration` | Upgrade or port a system with rollback readiness | analyze, plan, implement, validate, deploy |
| `skill-optimization` | Profile and improve an agent skill | research, analyze, implement, test, refine |
| `self-update` | Research and integrate reference updates | research, plan, implement, test, validate |
| `nines-assisted` | Apply built-in harness-backed evaluation knowledge | research, design, plan, implement, review, test, refine, validate, release |
| `repo-init` | Initialize repository workspace and governance surfaces | analyze, implement, validate |
| `change-driven` | Materialize an evidence-backed change lifecycle checklist | design, implement, verify, deploy |
| `web-design` | Design, refine, and deterministically verify a frontend | design, implement, refine, verify |

## How a Seed Becomes Work

1. Intent matching selects one seed.
2. L0 renders its partitions and assertion templates into `goal.md` and `checklist.md`.
3. The user confirms wording, P0/P1/P2 priorities, manual checks, and preflight decisions.
4. The `change-driven` runtime executes the confirmed checklist in bounded rounds.

Suggested priorities are advisory. A seed contains no checkboxes, evidence, round state, or runtime dependency state; those belong to the materialized change workspace.

## The Sole Executable Runtime

`change-driven` is the only executable template. Its lifecycle is:

```
propose → preflight → bounded checklist rounds → archive
```

During each round, L0 picks open items, L1 Wave dispatches isolated L2 Tasks, Tasks report evidence, and L0 checks only verified assertions. The same runtime serves all 23 seeds.

## Example Prompts

- `hotfix`: `"Fix the login timeout bug; users get 500 errors after 30 seconds"`
- `security-audit`: `"Audit the authentication module against OWASP Top 10"`
- `research-design-review-refine`: `"Research caching options, design one, and refine it after review"`
- `product-verification`: `"Verify the checkout flow visually and against accessibility requirements"`
- `repo-init`: `"Initialize this repository for DevolaFlow"`
- `web-design`: `"Build and polish a non-generic pricing page"`
