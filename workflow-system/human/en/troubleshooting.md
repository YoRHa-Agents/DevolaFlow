---
title: "Troubleshooting"
description: "Common issues and solutions for workflow execution."
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# Troubleshooting

## Template Validation Fails

**Symptom**: `validate-template --all` reports FAIL for a template.

**Common causes**:

| Error | Meaning | Fix |
|-------|---------|-----|
| Missing required field | A stage or metadata field is absent | Check against the schema in `schemas/workflow-template.schema.yaml` |
| Stage reference integrity | Composition references a stage ID not in the stages list | Ensure every stage `id` in `composition` exists in `stages[]` |
| Loop without termination | A loop is missing `until` or `max_iterations` | Add both fields to every loop definition |
| Orphan stage | A stage is defined but never referenced in composition | Either use it in composition or remove it |
| Lattice warning | A stage transition violates the dependency lattice | Usually safe to ignore (warning only). If intentional, document why |

## Gate Score Too Low

**Symptom**: Convergence loop runs max rounds and escalates.

**Diagnosis**:

1. Check the gate report: which dimension scored lowest?
2. Common low scorers:
   - **code_review** < 85: too many findings. Check `blocker` (25pts each) and `critical` (15pts each)
   - **test_quality** < 85: coverage below threshold or test failures
   - **architecture** < 85: SOLID principle violations flagged by review

**Fix**: Address the highest-severity findings first. One blocker drops the score by 25 points.

**Quick formula**: `quality_score = max(0, 100 - blocker*25 - critical*15 - major*5 - minor*1)`

## Convergence Stagnation

**Symptom**: Score does not improve for 2 consecutive rounds.

**Causes**:
- Fix agent is addressing wrong findings (not the highest-severity ones)
- New findings introduced while fixing old ones
- Specification is ambiguous, causing review agent to keep flagging

**Fix**: The system escalates to human. Provide direction: which findings to address first, or lower the quality threshold.

## Context Overflow

**Symptom**: Task agent produces low-quality output or misses requirements.

**Causes**: Too much context injected (exceeding ~8K token budget).

**Fix**:
- Ensure task descriptions are concise (100-300 words)
- Use summaries for predecessor artifacts, not full content
- Limit `owned_files` to 6 or fewer
- Limit `read_only` files to 15 or fewer

## Build-Skill Fails

**Symptom**: `make build-skill` reports budget violations.

| Tool | Budget | Fix if exceeded |
|------|--------|----------------|
| Cursor | <500 lines | Trim SKILL.md sections or move content to references |
| Claude | <200 lines | Already compressed; check for verbose sections |
| Copilot | <4000 chars | Shorten descriptions; use abbreviations |

## Repo Mode Detection Wrong

**Symptom**: `detect-repo-mode` returns incorrect mode.

**Fix**: Override in `.workflow/config.yaml`:

```yaml
repo_mode: github
platform_variant: null
```
