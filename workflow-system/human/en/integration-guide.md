---
title: "Integration Guide"
description: "Integrating DevolaFlow with existing tools and CI/CD pipelines."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:14:27Z"
source_version: "3.0.0"
---

# Integration Guide

Integrating DevolaFlow with existing tools and CI/CD pipelines.

## Supported Platforms

| Platform | Install Method | Skill Format |
|----------|---------------|-------------|
| Cursor | `devola-init cursor` | SKILL.md + references/ |
| Claude Code | `devola-init claude` | CLAUDE.md (self-contained) |
| Copilot | `devola-init copilot` | copilot-instructions.md |
| Codex | `devola-init codex` | SKILL.md + openai.yaml |

## CI/CD Integration

Add to your CI pipeline:

```bash
pip install -e '.[dev]'
python -m pytest tests/ --cov=devolaflow -q
ruff check src/ tests/ benchmarks/
validate-template --all
build-skill --all
python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline
```

## EvoBench in CI

The benchmark suite detects context selection regressions. Add `--compare-baseline` to flag regressions > 5% against stored baselines. Generate new baselines after intentional optimizations with `--generate-baseline`.
