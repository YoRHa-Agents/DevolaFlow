---
title: "Customization Guide"
description: "Creating custom workflow templates and derived configurations."
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# Customization Guide

DevolaFlow ships with 11 built-in workflow templates. You can extend these by creating custom templates or deriving from existing ones.

## Option 1: Create a Custom Template

Create a new YAML file in `workflow-system/agent/templates/custom/`:

```yaml
schema_version: "1.0"

metadata:
  name: my-team-review
  version: "0.1.0"
  display_name: "My Team Review"
  description: "Custom review workflow with extra security pass."
  category: composite
  applicable_scenarios:
    - "Internal code review with security focus"
  tags: [review, security, custom]

stages:
  - id: review
    primitive: review
    team: review
    duration_class: medium
    config:
      review_type: code
      pass_threshold: 0.85

  - id: security_review
    primitive: review
    team: review
    duration_class: medium
    config:
      review_type: security
      pass_threshold: 0.90

composition:
  compose: sequence
  stages:
    - stage: review
    - stage: security_review

loops: []
gates: []

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

Validate: `validate-template workflow-system/agent/templates/custom/my-team-review.yaml`

## Option 2: Derive from a Built-in

Create a derived template that inherits from a built-in and overrides specific settings:

```yaml
schema_version: "1.0"

metadata:
  name: full-pipeline-relaxed
  version: "1.0.0"
  display_name: "Full Pipeline (Relaxed)"
  description: "Full pipeline with lower quality thresholds for prototyping."

extends: full-pipeline

overrides:
  stages:
    impl:
      config:
        test_strategy: test_after
        target_coverage: 0.60
  gates:
    release_gate:
      criteria:
        - field: test.pass_rate
          operator: ">="
          value: 0.90
```

Place in `workflow-system/agent/templates/derived/`. Derived templates automatically shadow their base when discovered by name.

## Discovery Priority

When looking up a template by name:

1. `templates/custom/` (highest priority -- your overrides)
2. `templates/derived/` (inherits from builtins)
3. `templates/builtin/` (shipped defaults)

## Adding to the Registry

After creating a template, add it to `workflow-system/agent/templates/registry.yaml`:

```yaml
templates:
  - name: my-team-review
    path: custom/my-team-review.yaml
    source: custom
    version: "0.1.0"
    category: composite
    tags: [review, security, custom]
```
