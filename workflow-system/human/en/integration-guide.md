---
title: "Integration Guide"
description: "Integrating DevolaFlow with Cursor, Claude Code, Copilot, and Codex."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T08:45:55Z"
source_version: "17.0.0"
---

# Integration Guide

Integrating DevolaFlow with Cursor, Claude Code, Copilot, and Codex.

## Supported Platforms

| Platform | Install Method | Skill Format | Scope |
|----------|---------------|-------------|-------|
| **Cursor** | `devola-init cursor` | SKILL.md + references/ + examples/ | Project or global |
| **Claude Code** | `devola-init claude` | SKILL.md + references/ + examples/ | Project or global |
| **Copilot** | `devola-init copilot` | copilot-instructions.md | Project only |
| **Codex** | `devola-init codex` | SKILL.md + references/ | Global only |

The per-tool file lists are declared in `workflow-system/agent/manifest.yaml`
(the install-manifest single source of truth) — the table above mirrors its
`install_profiles` section.

## Cursor — Detailed Setup

### Installation

```bash
# Project-local (recommended — per-project)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# Or user-global (applies to all projects)
curl -fsSL $INSTALLER | bash -s cursor --global
```

This installs (per the `cursor` profile in `workflow-system/agent/manifest.yaml`):
- `.cursor/skills/devola-flow/SKILL.md` — the main skill file
- `.cursor/skills/devola-flow/references/` — Tier-2 domain reference files
- `.cursor/skills/devola-flow/examples/`, Tier-3 execution trace examples

How It Works in Cursor

DevolaFlow is loaded as a **Cursor Skill**. When you send a prompt in Agent mode, Cursor loads the skill content into the agent's context. DevolaFlow's seed-selection heuristics then activate from your intent keywords.

### Example Session: Building a Feature

1. Open Cursor in your project
2. Switch to **Agent mode** (Cmd+L / Ctrl+L)
3. Type your request:

```
Implement a REST API for user management with CRUD operations, JWT auth, and role-based access
```

4. DevolaFlow activates and the agent:
   - Selects the `full-pipeline` checklist seed
   - Materializes API design, implementation, review, test, and release assertions from provenance primitives
   - Asks you to confirm checklist priorities and preflight decisions
   - Runs bounded rounds: L0 Project picks items, L1 Wave dispatches parallel L2 Tasks
   - Verifies evidence before checking each assertion
   - Applies the archive gate before changing source truth

### Example Session: Hotfix

```
Fix: the /api/users endpoint returns 500 when the email field contains unicode characters
```

The agent selects the `hotfix` seed, materializes diagnosis and remediation assertions, and runs them through the shared checklist-round runtime. Primitive labels such as analyze, implement, test, and release are provenance for the seed; L0 chooses actual round order from confirmed priorities and dependencies.

### Tips for Cursor

**Attach the skill manually** for complex tasks: Type`@devola-flow` to explicitly reference the skill
- **Use Plan mode** for architectural decisions: The agent will produce a structured plan instead of executing
- **Subagent support**: Cursor's Task tool maps naturally to DevolaFlow's L1 Wave → L2 Task delegation

## Claude Code, Detailed Setup

### Installation

```bash
# Project-local (applies to current directory)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# User-global (applies to all sessions)
curl -fsSL $INSTALLER | bash -s claude --global
```

This installs the skill package into `.claude/skills/devola-flow/` (project-local) or `~/.claude/skills/devola-flow/` (with `--global`): `SKILL.md` plus the `references/` and `examples/` trees, per the `claude` profile in `workflow-system/agent/manifest.yaml`.

How It Works in Claude Code

DevolaFlow is loaded as a **Claude Code Skill**. It activates on intent-matched prompts (implement / fix / refactor / research), and Claude Code pulls in reference files on demand instead of loading everything into every session.

### Example Session

```bash
claude

> Implement a caching layer for our database queries with TTL support and cache invalidation
```

Claude Code will:
1. Detect `full-pipeline` seed intent
2. Anchor a measurable checklist and signed preflight
3. Use L1 Wave coordination and L2 Tasks for isolated implementation
4. Repeat bounded evidence-backed rounds until the archive gate passes or escalation is required

Tips for Claude Code

- References and examples ship alongside SKILL.md, the skill loads them on demand
- Works with Claude Code's native subagent support
- Use `"update devola"` to trigger version checks within a session

## GitHub Copilot, Detailed Setup

Installation

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

This installs:
- `.github/copilot-instructions.md`, the full SKILL.md content as root instructions

How It Works in Copilot

Copilot reads `copilot-instructions.md` for every request. The workflow heuristics guide Copilot's code suggestions and chat responses to follow structured patterns.

Example Session

In Copilot Chat:
```
@workspace Refactor the payment processing module to use the strategy pattern
```

Copilot uses the `refactoring` seed's historical analyze/plan/implement/test/review primitives as provenance, materializes a checklist, and executes it through the shared round runtime.

## OpenAI Codex, Detailed Setup

### Installation

```bash
# Codex uses global skills
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

This installs (per the `codex` profile in `workflow-system/agent/manifest.yaml`):
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/references/`

How It Works in Codex

Codex loads the skill and uses its built-in agent system for task parallelism. DevolaFlow's L1 Wave → L2 Task structure maps to Codex's parallel execution model.

## CI/CD Integration

Add DevolaFlow validation to your CI pipeline:

```yaml
# .github/workflows/ci.yml
- name: DevolaFlow Checks
  run: |
    pip install -e '.[dev]'
    python -m pytest tests/ --cov=devolaflow -q
    ruff check src/ tests/
    validate-template --all
    build-skill --all
    python -m pytest tests/harness/ -v
```

## Built-in harness in CI

The harness suite validates fixture schemas, cache-layout compatibility,
telemetry aggregation, evaluation, proposals, and bounded probe behavior.
