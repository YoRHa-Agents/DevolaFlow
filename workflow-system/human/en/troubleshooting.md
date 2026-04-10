---
title: "Troubleshooting"
description: "Common issues and solutions for workflow execution."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:14:27Z"
source_version: "3.0.0"
---

# Troubleshooting

Common issues and solutions for workflow execution.

## Common Issues

### Tests fail after SKILL.md changes
Run `python -m pytest tests/test_version.py -v` to check version consistency. Use `scripts/bump_version.py` for consistent updates.

### build-skill reports budget exceeded
SKILL.md must stay under 500 lines. Check with `wc -l` and remove redundant sections. Run `build-skill --all` to verify.

### EvoBench shows regressions
Run `python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline` and check which scenario regressed. Review changes to `context_profiles.yaml` or SKILL.md section boundaries.

### Context profiles not loading
Verify `context_profiles.yaml` exists at `workflow-system/agent/context_profiles.yaml` and its section line ranges match the current SKILL.md.
