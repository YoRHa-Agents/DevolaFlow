---
title: "Integration Guide"
description: "Integrating DevolaFlow with Cursor, Claude Code, Copilot, and Codex."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-05-04T08:38:55Z"
source_version: "10.6.0"
---

# Integration Guide

Integrating DevolaFlow with Cursor, Claude Code, Copilot, and Codex.

## Supported Platforms

| Platform | Install Method | Skill Format | Scope |
|----------|---------------|-------------|-------|
| **Cursor** | `devola-init cursor` | SKILL.md + references/ + examples/ | Project or global |
| **Claude Code** | `devola-init claude` | CLAUDE.md (self-contained) | Project or global |
| **Copilot** | `devola-init copilot` | copilot-instructions.md | Project only |
| **Codex** | `devola-init codex` | SKILL.md + openai.yaml | Global only |

## Cursor — Detailed Setup

### Installation

```bash
# Project-local (recommended — per-project)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# Or user-global (applies to all projects)
curl -fsSL $INSTALLER | bash -s cursor --global
```

This installs:
- `.cursor/skills/devola-flow/SKILL.md` — the main skill file
- `.cursor/skills/devola-flow/references/` — 9 domain reference files
- `.cursor/skills/devola-flow/examples/` — 3 execution trace examples

How It Works in Cursor

DevolaFlow is loaded as a **Cursor Skill**. When you send a prompt in Agent mode, Cursor loads the skill content into the agent's context. DevolaFlow's workflow selection heuristics then activate based on your intent keywords.

### Example Session: Building a Feature

1. Open Cursor in your project
2. Switch to **Agent mode** (Cmd+L / Ctrl+L)
3. Type your request:

```
Implement a REST API for user management with CRUD operations, JWT auth, and role-based access
```

4. DevolaFlow activates and the agent:
   - Selects `full-pipeline` workflow
   - **Design stage**: Defines API endpoints, data models, auth flow
   - **Plan stage**: Breaks into waves, auth module (Wave 1), CRUD endpoints (Wave 2), RBAC (Wave 3)
   - **Implement stage**: Creates source files with tests via parallel task agents
   - **Review stage**: Checks code quality, security, style
   - **Test stage**: Runs unit + integration tests, measures coverage
   - **Gate**: Verifies composite score ≥ 85, coverage ≥ 80%
   - **Release stage**: Updates changelog, prepares commit

### Example Session: Hotfix

```
Fix: the /api/users endpoint returns 500 when the email field contains unicode characters
```

The agent selects `hotfix` and:
1. **Triage**: Reads the endpoint code, identifies the encoding issue
2. **Fix**: Adds proper unicode handling (minimal diff)
3. **Test**: Runs focused tests on the affected endpoint
4. **Release**: Prepares the patch

### Tips for Cursor

**Attach the skill manually** for complex tasks: Type`@devola-flow` to explicitly reference the skill
- **Use Plan mode** for architectural decisions: The agent will produce a structured plan instead of executing
- **Subagent support**: Cursor's Task tool maps naturally to DevolaFlow's Wave→Task delegation

## Claude Code, Detailed Setup

### Installation

```bash
# Project-local (applies to current directory)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# User-global (applies to all sessions)
curl -fsSL $INSTALLER | bash -s claude --global
```

This installs a single self-contained `CLAUDE.md` file. Claude Code reads this file at the start of every session.

How It Works in Claude Code

`CLAUDE.md` is always active, Claude Code loads it automatically. Every prompt benefits from DevolaFlow's workflow structure.

### Example Session

```bash
claude

> Implement a caching layer for our database queries with TTL support and cache invalidation
```

Claude Code will:
1. Detect `full-pipeline` intent
2. Use `Task` subagents for parallel implementation
3. Follow the convergence loop for quality
4. Report with a task quality score at the end

Tips for Claude Code

- CLAUDE.md is self-contained, no external references needed
- Works with Claude Code's native subagent support
- Use `"update devola"` to trigger version checks within a session

## GitHub Copilot, Detailed Setup

Installation

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

This installs:
- `.github/copilot-instructions.md`, root instructions
- `.github/instructions/workflow.instructions.md`, workflow-specific instructions

How It Works in Copilot

Copilot reads `copilot-instructions.md` for every request. The workflow heuristics guide Copilot's code suggestions and chat responses to follow structured patterns.

Example Session

In Copilot Chat:
```
@workspace Refactor the payment processing module to use the strategy pattern
```

Copilot follows the `refactoring` workflow: scope analysis → plan → implement → test → review.

## OpenAI Codex, Detailed Setup

Installation

```bash
# Codex uses global skills
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

This installs:
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/agents/openai.yaml`

How It Works in Codex

Codex loads the skill and uses its built-in agent system for task parallelism. DevolaFlow's wave structure maps well to Codex's parallel execution model.

## CI/CD Integration

Add DevolaFlow validation to your CI pipeline:

```yaml
# .github/workflows/ci.yml
- name: DevolaFlow Checks
  run: |
    pip install -e '.[dev]'
    python -m pytest tests/ --cov=devolaflow -q
    ruff check src/ tests/ benchmarks/
    validate-template --all
    build-skill --all
    python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline
```

## EvoBench in CI

The benchmark suite detects context selection regressions. Add `--compare-baseline` to flag regressions > 5% against stored baselines. Generate new baselines after intentional optimizations with `--generate-baseline`.
