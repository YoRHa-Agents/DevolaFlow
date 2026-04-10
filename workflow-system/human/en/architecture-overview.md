---
title: "Architecture Overview"
description: "System architecture: 4-layer hierarchy, stage primitives, gate mechanism."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:14:27Z"
source_version: "3.0.0"
---

# Architecture Overview

System architecture: 4-layer hierarchy, stage primitives, gate mechanism.

## System Overview

DevolaFlow uses a 4-layer agent hierarchy to orchestrate complex workflows.

## The 4-Layer Hierarchy

| Layer | Role | Context Budget |
|-------|------|---------------|
| Project | Dispatch stages, track status | ~3K tokens |
| Stage | Decompose to waves, run gates | ~5K tokens |
| Wave | Parallel dispatch tasks | ~4K tokens |
| Task | Execute actual work | ~8K tokens |

## Task-Adaptive Context Selection

Each task type (hotfix, feature, research, refactor, review, design) has a context profile that selects only task-relevant SKILL.md sections. A hotfix agent skips design-stage primitives; a research agent skips convergence-loop details. Profiles are defined in `workflow-system/agent/context_profiles.yaml`.

## Stage Primitives

13 universal primitives: research, analyze, design, plan, implement, review, test, validate, refine, release, deploy, monitor, gate.

## Gate Mechanism

Quality checkpoints between stages. Composite score formula:
`composite = test(0.30) + review(0.30) + arch(0.20) + bench(0.20)`
Pass threshold: >= 85 with zero blockers.

## Repository Rules

18 enforceable rules in `.cursor/rules/` covering: SKILL format constraints (line budget, frontmatter, version consistency), change process guardrails (test coverage floor, no ghost features, pre-commit checklist), and context optimization rules (lean messages, verbatim extraction, benchmark verification).
