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

## 2. Use it

After installing, DevolaFlow activates automatically when you ask your AI tool to do multi-step work. Try these prompts:

```
"Implement a user authentication system from scratch"
```
The agent selects `full-pipeline` (8 stages), sets up a 4-layer hierarchy, and dispatches the Design stage first via a subagent. It will not try to code everything in one pass.

```
"Fix the login timeout bug"
```
The agent selects `hotfix` (4 stages: triage - fix - test - release), skips design/plan, and goes straight to analyzing the bug.

```
"Research the best TUI framework for Rust"
```
The agent selects `research-only` (3 stages), produces a structured comparison report with no code.

### What changes in agent behavior

Without DevolaFlow, agents typically try to do everything in one long pass -- reading entire codebases, writing all files, running all tests, mixing concerns.

With DevolaFlow:

| Without | With DevolaFlow |
|---------|----------------|
| One giant pass | Stage-by-stage dispatch via subagents |
| All context loaded at once | Each task gets ~8K tokens of focused context |
| No quality check before shipping | Gate: composite >= 85, 0 blockers, reviewed |
| If review finds issues, manual fix | Convergence loop: review - fix - test - fix (auto, max 3 rounds) |
| No structure, ad-hoc file editing | Tasks own disjoint file sets, max 5 parallel per wave |

### Prompt patterns

| What you say | Workflow selected | Stages |
|-------------|------------------|--------|
| "Implement X from scratch" | `full-pipeline` | design - plan - impl - review - test - gate - release |
| "Fix bug in X" | `hotfix` | triage - fix - test - release |
| "Refactor X" | `refactoring` | scope - plan - impl - test - review |
| "Research X" / "Compare X vs Y" | `research-only` | research - compare - report |
| "Design architecture for X" | `RDRR` | research - design - review - refine (loop) |
| "Add X to existing Y" | `feature-enhancement` | scope - design - plan - impl - review - test - release |
| "Migrate from X to Y" | `migration` | assess - plan - impl - validate - cutover |
| "Is X feasible?" | `spike-poc` | research - prototype - evaluate |
| "Write docs for X" | `documentation` | survey - author - review |
| "Security audit X" | `security-audit` | threat - scan - analyze - remediate - verify |

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
