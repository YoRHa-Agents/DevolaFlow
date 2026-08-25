---
title: "Architecture Overview"
description: "Three-layer checklist-round architecture, provenance primitives, and evidence gates."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T19:37:27Z"
source_version: "17.0.1"
---

# Architecture Overview

Three-layer checklist-round architecture, provenance primitives, and evidence gates.

## Three layers

| Layer | Responsibility | Boundary |
|---|---|---|
| L0 Project | Confirm goal/checklist/preflight, select rounds, verify evidence | Does not implement |
| L1 Wave | Partition ownership-safe tasks and aggregate reports | Does not alter Task output |
| L2 Task | Implement one atomic assignment and self-verify | Does not spawn agents |

Escalation moves Task → Wave → Project → Human. Every retry loop is bounded.

## Seeds and runtime

The registry currently supplies 23 non-executable checklist
seeds. Their 12 primitive labels
(`analyze`, `deploy`, `design`, `implement`, `plan`, `refine`, `release`, `research`, `review`, `test`, `validate`, `verify`) preserve historical
decomposition provenance; list order is not runtime order. `change-driven` is
the sole executable runtime.

## Evidence contract

A round passes only when selected checklist assertions have valid evidence,
configured checks pass, reinforcement is closed, and blockers are zero.
Composite scores remain trend signals; they do not replace item evidence.

## Context and governance

Task-adaptive selection derives from 24 profiles
in `workflow-system/agent/context_profiles.yaml`. The canonical `.rules/`
sources currently contain 56 rule IDs; generated surfaces
must be compiled rather than hand-edited.

Harness baseline settlement and cycle-archive retention are policy. Cycle leads
perform the archive rollup manually at cycle close; no automatic archive hook
is implemented.
