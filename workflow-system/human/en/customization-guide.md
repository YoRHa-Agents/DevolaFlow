---
title: "Customization Guide"
description: "Creating non-executable checklist seeds and derived configurations."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T07:21:59Z"
source_version: "16.0.0"
---

# Customization Guide

Creating non-executable checklist seeds and derived configurations.

## Creating Checklist Seeds

Checklist seeds are YAML files under `workflow-system/agent/templates/seeds/`. They follow `schemas/checklist-seed.schema.yaml` and preserve domain decomposition knowledge without creating another executable runtime.

The only executable template is `workflow-system/agent/templates/builtin/change-driven.yaml`. A custom seed is materialized into that shared checklist-round runtime.

### Seed Structure

```yaml
schema_version: "1.0"
kind: checklist-seed
metadata:
  name: code-review
  version: "1.0.0"
  description: "Seed for standalone code review evidence."
  category: composite
  intent_keywords: [review, quality, pull-request]
  source:
    kind: composition
    name: code-review
    path: workflow-system/agent/templates/registry.yaml
    schema_version: "3.0"

placeholders:
  review_command:
    description: "Repository-approved bounded review command."
    required: true
    example: "ruff check src/ tests/"

partitions:
  - key: review
    title_template: "Code review"
    source_stages:                 # provenance only; never execution order
      - {id: review, primitive: review}
    assertions:
      - key: findings-resolved
        statement_template: "Every blocker and critical review finding is resolved"
        suggested_priority: P0
        verify:
          mode: metric
          template: "open_blocker_count == 0 and open_critical_count == 0"
      - key: checks-pass
        statement_template: "The approved static review command passes"
        suggested_priority: P1
        verify:
          mode: command
          template: "{{ review_command }}"
```

### What a Seed May Express

- Intent keywords and optional scenarios
- User-facing checklist partitions
- Measurable assertion templates, each no longer than 25 rendered words
- Suggested P0/P1/P2 priorities that the user can change
- Verification by bounded command, metric, or manual user check
- `source_stages` entries containing only historical source IDs and one of 14 primitive labels

### What a Seed Must Not Express

A seed is not a runtime DAG. Top-level `stages`, `composition`, `loops`, and `gates` are forbidden, as are runtime fields such as `team`, `duration_class`, `input_mapping`, and `skip_condition`. Seed order is presentation-only.

Checkboxes, evidence paths, round numbers, checked-by metadata, and runtime dependencies are also absent. They are assigned only when L0 materializes the seed into a user-confirmed change checklist.

## Registering a Seed

Add one registry entry with a `seed:` path and no executable `path:`. The `change-driven` entry is the only one allowed to declare `path: builtin/change-driven.yaml`.

## Custom Context Profiles

Edit `workflow-system/agent/context_profiles.yaml` to add profiles for new task types. Each profile specifies which SKILL.md sections to include at what priority:

- **critical**: Always included, loaded first
- **important**: Included if token budget allows
- **supplementary**: Included only if space remains
- **skip**: Never included for this task type

## Validating Changes

After customizing, always verify:

```bash
validate-template --all                # 23 seeds + one runtime are valid
python -m pytest tests/ -q             # all tests pass
python -m pytest tests/harness/ -v       # harness contracts pass
build-skill --all                      # adapters build successfully
```
