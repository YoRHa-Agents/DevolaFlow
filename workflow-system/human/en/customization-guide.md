---
title: "Customization Guide"
description: "Creating custom workflow templates and derived configurations."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-24T08:15:36Z"
source_version: "8.4.3"
---

# Customization Guide

Creating custom workflow templates and derived configurations.

## Creating Custom Workflow Templates

Workflow templates are YAML files in `workflow-system/agent/templates/builtin/`. Each template follows the schema defined in `schemas/workflow-template.schema.yaml`.

### Template Structure

```yaml
schema_version: "1.0"

metadata:
  name: my-workflow          # unique kebab-case id
  version: "1.0.0"
  display_name: "My Workflow"
  description: "What this workflow does"
  category: build            # discover | shape | build | deliver | composite
  applicable_scenarios:
    - "When to recommend this workflow"
  tags: [keyword1, keyword2]

stages:
  - id: stage_id
    primitive: implement     # one of 13 primitives
    alias: friendly-name     # optional display name
    description: "What this stage does"
    team: implement          # research | design | implement | test | review
    duration_class: medium   # quick | medium | long
    config:
      test_strategy: tdd
    input_mapping:
      tasks: "previous_stage.output"

composition:
  compose: sequence
  stages:
    - stage: stage_id
    - compose: loop
      ref: my_loop

loops:
  - name: my_loop
    body_stages: [stage_a, stage_b]
    until: "stage_b.pass_rate == 1.0"
    max_iterations: 3
    on_exhaustion: escalate

gates:
  - name: quality_gate
    position: "after:stage_id"
    criteria:
      - field: stage_id.metric
        operator: ">="
        value: 0.80
    on_pass: "next"
    on_fail:
      action: loop_back
      target: stage_id

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

### Example: Custom "Code Review Only" Template

```yaml
schema_version: "1.0"

metadata:
  name: code-review
  version: "1.0.0"
  display_name: "Code Review Only"
  description: "Standalone code review without implementation."
  category: verify
  applicable_scenarios:
    - "Reviewing a PR or code submission"
  tags: [review, quality, check]

stages:
  - id: review
    primitive: review
    description: "Review code for quality, security, and style"
    team: review
    duration_class: medium
    config:
      review_type: code
      pass_threshold: 0.80

composition:
  compose: sequence
  stages:
    - stage: review

loops: []
gates: []

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

## Custom Context Profiles

Edit `workflow-system/agent/context_profiles.yaml` to add profiles for new task types. Each profile specifies which SKILL.md sections to include at what priority:

- **critical**: Always included, loaded first
- **important**: Included if token budget allows
- **supplementary**: Included only if space remains
- **skip**: Never included for this task type

## Deriving Templates

Use the `extends` field to inherit from a builtin template and override specific stages:

```yaml
metadata:
  name: my-enhanced-hotfix
  extends: hotfix

stages:
  - id: notify
    primitive: release
    alias: notify
    description: "Send Slack notification after fix"
```

## Validating Changes

After customizing, always verify:

```bash
validate-template --all                # templates are valid
python -m pytest tests/ -q             # all tests pass
python -m benchmarks.devolaflow_context.runner --scenario all  # no regressions
build-skill --all                      # adapters build successfully
```
