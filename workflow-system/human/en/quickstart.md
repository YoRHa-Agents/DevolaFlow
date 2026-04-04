---
title: "Quick Start Guide"
description: "Getting started with DevolaFlow in under 5 minutes."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# Quick Start Guide

Get DevolaFlow into your AI tool in under 5 minutes.

## 1. Install (pick one)

### Fastest: one command

```bash
# Cursor (project-local)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# Cursor (user-global, shared across all projects)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor --global

# Claude Code
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# Copilot
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

### Alternative: pip

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init cursor       # or: devola-init claude / copilot / all
```

### Simplest: one file

Download [MVP-SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/MVP-SKILL.md) and put it at:

| Tool | Where to put it |
|------|----------------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` or `~/.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `./CLAUDE.md` (project root) |
| Copilot | `.github/copilot-instructions.md` |
| Codex | `~/.codex/skills/devola-flow/SKILL.md` |

## 2. Verify it works

Ask your AI tool:

> "Implement a new feature using the full-pipeline workflow"

It should respond by setting up a 4-layer hierarchy (Project Agent dispatching Stage Agents) and selecting the `full-pipeline` workflow with 8 stages.

## 3. Update to latest

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```

This finds all existing DevolaFlow installs and re-downloads the latest files.

## 4. Understand the basics

### 11 workflow types

| What you're doing | Use this workflow |
|-------------------|------------------|
| New feature from scratch | `full-pipeline` (8 stages) |
| Fix a production bug | `hotfix` (4 stages) |
| Clean up tech debt | `refactoring` (5 stages) |
| Evaluate options | `research-only` (3 stages) |
| Design a system | `design-only` or `RDRR` |

### 4-layer hierarchy

```
Project Agent  -- picks workflow, dispatches stages (never writes code)
  Stage Agent  -- decomposes into waves, runs gate (never writes code)
    Wave Agent -- dispatches parallel tasks (never writes code)
      Task Agent -- THE ONLY LAYER THAT WORKS (writes code, tests, reviews)
```

### Quality gates

After each stage: `composite = test*0.30 + review*0.30 + arch*0.20 + bench*0.20 >= 85`

## What's next

| Want to... | Read |
|-----------|------|
| See all workflow types | [Workflow Types](workflow-types.md) |
| Understand the architecture | [Architecture Overview](architecture-overview.md) |
| Create a custom workflow | [Customization Guide](customization-guide.md) |
| Integrate with CI/CD | [Integration Guide](integration-guide.md) |
| Troubleshoot gate failures | [Troubleshooting](troubleshooting.md) |
| Explore interactively | [Online Demo](https://yorha-agents.github.io/DevolaFlow/) |
