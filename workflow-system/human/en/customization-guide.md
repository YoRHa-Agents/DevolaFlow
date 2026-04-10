---
title: "Customization Guide"
description: "Creating custom workflow templates and derived configurations."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:14:27Z"
source_version: "3.0.0"
---

# Customization Guide

Creating custom workflow templates and derived configurations.

## Creating Custom Workflow Templates

Workflow templates live in `workflow-system/agent/templates/builtin/`. Create a new YAML file following the schema in `schemas/workflow-template.schema.yaml`.

## Custom Context Profiles

Edit `workflow-system/agent/context_profiles.yaml` to add new task-type profiles. Each profile specifies which SKILL.md sections to include (critical/important/supplementary/skip) and the token budget.

## Deriving Templates

Use the `extends` field in a template YAML to inherit from a builtin template and override specific stages, gates, or constraints.

## Validating Changes

After customizing, run:
```bash
validate-template --all
python -m pytest tests/ -q
python -m benchmarks.devolaflow_context.runner --scenario all
```
