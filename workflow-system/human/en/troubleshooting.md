---
title: "Troubleshooting"
description: "Common issues and solutions for workflow execution."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T19:03:11Z"
source_version: "3.5.0"
---

# Troubleshooting

Common issues and solutions for workflow execution.

## Installation Issues

### `devola-init` command not found

The CLI tools require pip installation:
```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
# Or for development:
pip install -e ".[dev]"
```

### Installer fails with "permission denied"

The installer needs write access to the target directory. For global installs:
```bash
# Cursor global
curl -fsSL $INSTALLER | bash -s cursor --global
# This writes to ~/.cursor/skills/ which should be user-writable
```

## Workflow Issues

### Agent doesn't select the right workflow

DevolaFlow uses keyword matching. Make your intent explicit:
- Instead of: "Help me with the login page"
- Try: "Fix the bug in the login page" (→ hotfix) or "Redesign the login page UI" (→ design-only)

You can also specify directly: "Use the refactoring workflow to clean up auth module."

### Agent tries to do everything in one pass

This usually means the skill file isn't loaded. Verify:
1. Check the skill file exists: `ls .cursor/skills/devola-flow/SKILL.md`
2. In Cursor, verify the skill appears in settings
3. Try explicitly attaching: `@devola-flow implement a user system`

### Convergence loop runs too many times

The default max is 3 iterations. If the agent keeps looping:
1. Check if acceptance criteria are too strict
2. Look for conflicting requirements that prevent convergence
3. The agent will escalate to you after max iterations — review the divergence report

## Test & Build Issues

### Tests fail after SKILL.md changes

Run `python -m pytest tests/test_version.py -v` to check version consistency. Use `scripts/bump_version.py` for consistent updates across all version locations.

### `build-skill` reports budget exceeded

SKILL.md must stay under 500 lines (rule SF-1). Check with `wc -l` and compress verbose sections. Run `build-skill --all` to verify after changes.

### Template validation fails

```bash
validate-template path/to/template.yaml
```

Common causes:
- Missing required fields (`schema_version`, `metadata`, `stages`, `composition`)
- Stage references in `composition` that don't match any `stages[].id`
- Loop references that don't match any `loops[].name`
- Invalid primitive names (must be one of the 13 primitives)

## Benchmark Issues

### EvoBench shows regressions

```bash
python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline
```

If a scenario regressed:
1. Check recent changes to `context_profiles.yaml` or SKILL.md section boundaries
2. Review the specific scenario's expected vs actual section selection
3. After fixing, update baselines: `python -m benchmarks.devolaflow_context.runner --generate-baseline`

### Context profiles not loading

Verify `context_profiles.yaml` exists at `workflow-system/agent/context_profiles.yaml` and its section line ranges match the current SKILL.md structure.

## Getting Help

- **GitHub Issues**: [https://github.com/YoRHa-Agents/DevolaFlow/issues](https://github.com/YoRHa-Agents/DevolaFlow/issues)
- **Interactive Demo**: [https://yorha-agents.github.io/DevolaFlow/](https://yorha-agents.github.io/DevolaFlow/)
