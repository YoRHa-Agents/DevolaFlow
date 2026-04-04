---
title: "Architecture Overview"
description: "System architecture: 4-layer hierarchy, stage primitives, gate mechanism."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# Architecture Overview

## System Overview

DevolaFlow uses a 4-layer agent hierarchy to orchestrate complex software development workflows.

## The 4-Layer Hierarchy

| Layer | Role | Context Budget |
|-------|------|---------------|
| Project | Dispatch stages, track status | ~3K tokens |
| Stage | Decompose to waves, run gates | ~5K tokens |
| Wave | Parallel dispatch tasks | ~4K tokens |
| Task | Execute actual work | ~8K tokens |

## Stage Primitives

13 universal primitives: research, analyze, design, plan, implement, review, test, validate, refine, release, deploy, monitor, gate.

## Gate Mechanism

Quality checkpoints between stages. Composite score formula:
`composite = test(0.30) + review(0.30) + arch(0.20) + bench(0.20)`
Pass threshold: >= 85 with zero blockers.
