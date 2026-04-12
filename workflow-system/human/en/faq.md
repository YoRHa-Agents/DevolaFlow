---
title: "FAQ"
description: "Frequently asked questions about the workflow system."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-12T05:08:03Z"
source_version: "3.9.0"
---

# FAQ

Frequently asked questions about the workflow system.

## General

### What is DevolaFlow?

A composable workflow meta-framework for AI-assisted software development. It defines multi-stage delivery pipelines as declarative YAML templates and orchestrates them through a 4-layer agent hierarchy with quality gates. Think of it as a project management framework that your AI coding tool follows automatically.

### What AI tools does it support?

- **Cursor** — loaded as a Cursor Skill (`.cursor/skills/devola-flow/SKILL.md`)
- **Claude Code** — loaded as `CLAUDE.md` (always active in every session)
- **GitHub Copilot** — loaded as `copilot-instructions.md`
- **OpenAI Codex** — loaded as a Codex Skill

A single source (`workflow-skill.yaml`) is adapted to each tool's format via the `build-skill` pipeline.

### Do I need to learn YAML to use DevolaFlow?

No. DevolaFlow activates automatically based on your natural language prompts. Say "fix the login bug" and it selects the hotfix workflow. Say "build a new feature from scratch" and it selects full-pipeline. You only need YAML if you want to create custom workflow templates.

### How does DevolaFlow differ from just prompting my AI tool?

Without DevolaFlow, your AI tool processes the entire request in a single pass, often losing context or mixing concerns (designing while coding while testing). With DevolaFlow, work is decomposed into isolated stages with quality checkpoints, so the agent designs first, then plans, then implements, then reviews — with gates ensuring quality at each boundary.

## Workflows

### How does the agent choose a workflow?

DevolaFlow uses **intent matching** on your prompt keywords:
- "fix bug" / "broken" / "crash" → `hotfix`
- "from scratch" / "new project" → `full-pipeline`
- "research" / "compare" → `research-only`
- "refactor" / "clean up" → `refactoring`
- And so on for all 17 types

You can also specify explicitly: "Use the migration workflow to upgrade from React 17 to 18."

### Can I skip stages?

Yes, in two ways:
1. **Complexity scaling**: For trivial tasks (< 20 lines, single file), DevolaFlow skips the workflow entirely
2. **Environment modes**: In `local` mode, release stages are typically skipped

### What are the 5 new workflow types in v3.0.0+?

- **demo-showcase**: Build presentation-ready demos and interactive showcases
- **performance-optimization**: Profile-driven performance improvement with before/after benchmarks
- **dependency-setup**: Configure dev environments, install dependencies, set up tooling
- **onboarding**: Help new contributors understand a codebase and set up their environment
- **skill-optimization**: Optimize agent skills with context profiling, benchmarking, and iterative improvement

## Quality & Gates

### What are the repository rules?

18 enforceable rules in `.cursor/rules/` organized into 3 files:
- **skill-format-rules.mdc** (SF-1 to SF-6): SKILL.md line budget, frontmatter, version consistency
- **change-process-rules.mdc** (CP-1 to CP-7): test coverage floor (≥80%), no ghost features
- **context-optimization-rules.mdc** (CO-1 to CO-6): lean messages, verbatim extraction, benchmarks

### What is EvoBench?

A built-in benchmark suite that measures how effectively context is routed to agents. It scores:
- **Section relevance**: Are the right SKILL.md sections selected for each task type?
- **Information density**: Quality per token
- **Noise ratio**: Irrelevant sections included

Run with: `python -m benchmarks.devolaflow_context.runner --scenario all`

### What happens when a gate fails?

The gate triggers a **convergence loop**: review findings → fix issues → re-test → re-check gate. This repeats up to 3 rounds. If the gate still fails after max rounds, it escalates to the human with a divergence report explaining what's blocking.

## Updates & Versioning

### How do I check for updates?

Ask your AI agent: `"update devola"` — or run `devola-version` in the terminal.

### How do I update?

```bash
# pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# installer
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```
