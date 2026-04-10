---
title: "FAQ"
description: "Frequently asked questions about the workflow system."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:14:27Z"
source_version: "3.0.0"
---

# FAQ

Frequently asked questions about the workflow system.

## What is DevolaFlow?

A composable workflow meta-framework for AI-assisted software development. It defines multi-stage delivery pipelines as declarative YAML templates and orchestrates them through a 4-layer agent hierarchy with quality gates.

## What AI tools does it support?

Cursor, Claude Code, GitHub Copilot, and OpenAI Codex. A single source (`workflow-skill.yaml`) is adapted to each tool's format via the build-skill pipeline.

## What are the repository rules?

18 enforceable rules in `.cursor/rules/` organized into 3 files:
- **skill-format-rules.mdc** (SF-1 to SF-6): SKILL.md constraints
- **change-process-rules.mdc** (CP-1 to CP-7): testing and versioning guardrails
- **context-optimization-rules.mdc** (CO-1 to CO-6): lean messages and benchmarks

## What is EvoBench?

A built-in benchmark suite that measures context selection quality. It scores section relevance, information density, and noise ratio across task types. Run with: `python -m benchmarks.devolaflow_context.runner --scenario all`

## How do I check for updates?

Ask your AI agent: `"update devola"` or run `devola-version` in the terminal.
