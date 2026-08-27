---
title: "Checklist Seed Catalog"
description: "Registry-derived checklist seeds and the sole change-driven runtime."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-27T09:07:22Z"
source_version: "17.4.2"
---

# Checklist Seed Catalog

Registry-derived checklist seeds and the sole change-driven runtime.

## Registry catalog

The table is generated from `workflow-system/agent/templates/registry.yaml`;
membership is not maintained in this guide.

| Seed ID | Category | Canonical description | Intent tags |
|---|---|---|---|
| `hotfix` | `build` | Rapid bug triage, minimal fix, focused test, fast-track release. | `bug`, `fix`, `hotfix`, `patch`, `urgent` |
| `research-only` | `discover` | Pure research and comparison with a validated report. | `research`, `compare`, `evaluate` |
| `design-only` | `shape` | Research-backed design and architecture review. | `design`, `research`, `review`, `architecture` |
| `documentation-only` | `deliver` | Documentation survey, authoring, and review. | `documentation`, `docs`, `write`, `review` |
| `spike-poc` | `discover` | Bounded throwaway prototype with an explicit evaluation verdict. | `spike`, `poc`, `prototype`, `experiment` |
| `refactoring` | `build` | Evidence-backed technical-debt restructuring. | `refactor`, `tech-debt`, `improve`, `restructure` |
| `feature-enhancement` | `composite` | Extend an existing feature through design, implementation, and release evidence. | `feature`, `enhance`, `extend`, `modify` |
| `full-pipeline` | `composite` | Greenfield or end-to-end build decomposition knowledge. | `full`, `pipeline`, `feature`, `implementation`, `release` |
| `performance-optimization` | `build` | Profile, optimize, benchmark, and validate measurable performance. | `performance`, `optimize`, `profiling`, `benchmark`, `speed`, `latency` |
| `security-audit` | `composite` | Threat modeling, scanning, analysis, remediation, and verification. | `security`, `audit`, `vulnerability`, `CVE`, `scan` |
| `research-design-review-refine` | `composite` | Iterative research, design, review, refinement, and knowledge-gap closure. | `research`, `design`, `review`, `refine`, `iterate` |
| `dependency-setup` | `build` | Environment and tooling setup with bounded verification. | `setup`, `install`, `dependency`, `environment`, `tooling`, `configuration` |
| `onboarding` | `discover` | Contributor onboarding through analysis, documentation, setup, and verification. | `onboarding`, `setup`, `getting-started`, `contributor`, `codebase` |
| `demo-showcase` | `composite` | Demo and presentation decomposition with visual-quality evidence. | `demo`, `showcase`, `presentation`, `prototype`, `ui`, `visual`, `pitch` |
| `product-verification` | `composite` | User-facing verification across visual, interaction, accessibility, and acceptance axes. | `verify`, `visual`, `acceptance`, `interaction`, `accessibility`, `uat`, `e2e`, `product`, `quality` |
| `entropy-cleanup` | `control` | Stale-documentation and drift cleanup knowledge. | `entropy`, `gc`, `cleanup`, `freshness`, `drift`, `maintenance`, `meta`, `documentation` |
| `harness-construction` | `composite` | Harness infrastructure construction (observation/evaluation/probe/baseline/signal/loop-closure coverage) with machine-grounded gap analysis and an archive capability review. | `harness`, `evaluation-infrastructure`, `observability`, `telemetry`, `coverage`, `gap-analysis`, `baseline` |
| `pathfinder` | `control` | Read-only look-ahead reconnaissance that reports infrastructure and harness gaps before a later wave. | `pathfinder`, `path-find`, `look-ahead`, `infrastructure`, `harness`, `gap-analysis`, `reconnaissance` |
| `migration` | `build` | Systematic migration with validation, cutover, and rollback readiness. | `migrate`, `upgrade`, `transition`, `port` |
| `skill-optimization` | `composite` | Agent-skill profiling, optimization, validation, and documentation knowledge. | `skill`, `optimize`, `benchmark`, `context`, `compress`, `iterate`, `density` |
| `self-update` | `control` | Reference dependency research, integration, testing, and evaluation knowledge. | `self-update`, `update`, `upgrade`, `refs`, `validate`, `meta` |
| `nines-assisted` | `composite` | Built-in harness-backed historical research and iteration decomposition knowledge. | `harness`, `evaluation`, `analysis`, `pipeline`, `self-eval`, `review`, `assisted`, `full` |
| `repo-init` | `discover` | Repository workspace and governance initialization knowledge. | `init`, `scaffold`, `bootstrap`, `repo`, `workspace`, `rules` |
| `change-driven` | `composite` | The sole executable checklist-round lifecycle runtime. | `change`, `propose`, `preflight`, `round`, `archive`, `lifecycle`, `agent-workspace`, `opsx` |
| `web-design` | `composite` | Frontend design, implementation, refinement, and deterministic verification knowledge. | `web-design`, `frontend`, `landing-page`, `ui`, `design`, `polish`, `impeccable`, `ui-pro` |

## Selection and execution

Intent selects decomposition knowledge. L0 then materializes a measurable
goal/checklist/preflight contract. Priorities, satisfied dependencies, file
ownership, and round state determine execution order; `source_stages` does not.
Every seed runs through the sole `change-driven` runtime.
