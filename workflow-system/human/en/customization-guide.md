---
title: "Customization Guide"
description: "Customize seeds, context profiles, rules, and local scaffolds without forking runtime truth."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-09-01T07:31:18Z"
source_version: "24.0.0"
---

# Customization Guide

Customize seeds, context profiles, rules, and local scaffolds without forking runtime truth.

## Checklist seeds

Add a seed under `workflow-system/agent/templates/seeds/` and register it once
in `templates/registry.yaml`. Seeds may define intent, partitions, assertion
templates, suggested priorities, verification, and provenance. They must not
define another executable DAG; `change-driven` remains the runtime.

## Context profiles

Edit `workflow-system/agent/context_profiles.yaml`, keep critical sections
within budget, and inspect affected selectors with
`python -m devolaflow.task_adaptive_selector <task-type> --verbose`.

## Rules

Edit `.rules/*.mdc`, then run `make compile-rules`. Never hand-edit generated
`AGENTS.md`, `.cursor/rules/repo-governance.mdc`, or `docs/STYLE-RULES.md`.

## Local scaffold depth

`devola-init local --mode=core|standard|full` selects scaffolding depth.
Individual `--no-compile`, `--with-examples`, and `--no-with-examples` flags
override mode defaults. Re-running the scaffold is idempotent.
