---
title: "Quick Start Guide"
description: "Getting started with DevolaFlow in under 10 minutes."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# Quick Start Guide

Get DevolaFlow running and orchestrate your first workflow in under 10 minutes.

## 1. Install

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
```

Verify: `validate-template --all` should report `11 passed, 0 failed`.

## 2. Detect Your Repo Mode

```bash
detect-repo-mode
```

DevolaFlow auto-detects your repository type and adjusts behavior:

| Mode | Detected when | Release? | CI/CD? |
|------|--------------|----------|--------|
| `local` | No `.git` or no remote | Skipped | No |
| `github` | Remote contains `github.com` | GitHub Releases | GitHub Actions |
| `gitlab` | Remote contains `gitlab` | Registry | GitLab CI |

## 3. Pick a Workflow Type

Match your task to a workflow:

| What you're doing | Workflow to use | Command |
|-------------------|----------------|---------|
| Building a new feature from scratch | `full-pipeline` | 8 stages, full lifecycle |
| Fixing a production bug | `hotfix` | 4 stages, fast-track |
| Cleaning up tech debt | `refactoring` | 5 stages with regression tests |
| Evaluating options | `research-only` | 3 stages, no code |
| Designing a system | `design-only` or `RDRR` | Research-backed design loop |

Full list of 11 types: see [Workflow Types](workflow-types.md).

## 4. Understand the 4-Layer Hierarchy

Every workflow executes through a strict 4-layer delegation chain:

```
You (human) give a task
    |
Project Agent  -- picks workflow type, dispatches stages
    |
Stage Agent    -- decomposes into waves, runs quality gate
    |
Wave Agent     -- dispatches tasks in parallel
    |
Task Agent     -- THE ONLY LAYER THAT DOES WORK
                  (writes code, runs tests, reviews)
```

**The golden rule**: Layers 0-2 (Project/Stage/Wave) **never** do actual work. They dispatch, monitor, and evaluate. Only the Task Agent (Layer 3) touches files and tools.

## 5. Use with Your AI Tool

### Option A: Quick Start (Single File)

Copy `workflow-system/agent/MVP-SKILL.md` into your AI tool's instruction location:

- **Cursor**: `.cursor/skills/workflow-orchestrator/SKILL.md`
- **Claude Code**: project root as `CLAUDE.md`
- **Copilot**: `.github/copilot-instructions.md`

### Option B: Full Skill System

```bash
make build-skill    # generates dist/cursor/, dist/codex/, dist/claude/, dist/copilot/
```

Then copy the appropriate `dist/<tool>/` contents to the tool's skill directory.

### Option C: Just Read the Design

The 14 design documents in `doc/designs/` are self-contained specifications. Any AI tool can reference them directly for context on the workflow system.

## 6. Validate a Template

Inspect any workflow template:

```bash
validate-template workflow-system/agent/templates/builtin/hotfix.yaml
```

Or validate all 11 at once:

```bash
validate-template --all
```

## 7. Explore Interactively

Open `workflow-system/human/demo/index.html` in your browser to:

- **Workflow Visualizer**: Select any of the 11 workflow types and see its stage pipeline rendered as a diagram
- **Stage Explorer**: Drill into any of the 13 stage primitives to see teams, duration, gate criteria

Or visit the [online demo](https://yorha-agents.github.io/DevolaFlow/) on GitHub Pages.

## What's Next

| Want to... | Read |
|-----------|------|
| Understand the architecture | [Architecture Overview](architecture-overview.md) |
| See all workflow types | [Workflow Types](workflow-types.md) |
| Learn about quality gates | [Troubleshooting](troubleshooting.md) |
| Create a custom workflow | [Customization Guide](customization-guide.md) |
| Integrate with CI/CD | [Integration Guide](integration-guide.md) |
