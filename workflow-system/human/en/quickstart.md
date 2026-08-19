---
title: "Quick Start Guide"
description: "Getting started with DevolaFlow in under 10 minutes."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-19T22:10:42Z"
source_version: "15.2.0"
---

# Quick Start Guide

Getting started with DevolaFlow in under 10 minutes.

## Prerequisites

- Python 3.11+
- pip
- One of: Cursor, Claude Code, GitHub Copilot, or OpenAI Codex

## Step 1: Install DevolaFlow

Choose the method that fits your setup:

**Option A — One-liner (recommended for most users):**

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

# Install for Cursor (project-local)
curl -fsSL $INSTALLER | bash -s cursor

# Or install for all tools at once
curl -fsSL $INSTALLER | bash -s all
```

**Option B — pip install:**

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project/
devola-init cursor       # Cursor only
devola-init all          # all tools
```

**Option C, Manual (single file):**

Download [SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md) and place it in:

| Tool | Path |
|------|------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `.claude/skills/devola-flow/SKILL.md` |
| Copilot | `.github/copilot-instructions.md` |
| Codex | `~/.codex/skills/devola-flow/SKILL.md` |

## Step 2: Verify Installation

```bash
devola-version   # should print current DevolaFlow version
```

## Step 3: Try Your First Workflow

Open your AI tool and try one of these prompts:

### Example: Fix a Bug (Hotfix Workflow)

```
Fix the login timeout bug — users report 500 errors after 30 seconds of inactivity
```

What happens behind the scenes:
1. DevolaFlow detects **hotfix** intent from "fix" + "bug"
2. **Triage stage**: Agent analyzes the bug, identifies root cause
3. **Fix stage**: Agent implements a minimal targeted fix
4. **Test stage**: Agent runs focused tests on affected code
5. **Release stage**: Agent prepares the patch for deployment

### Example: Build a New Feature (Full Pipeline)

```
Implement a user notification system with email and in-app channels
```

What happens:
1. DevolaFlow selects **full-pipeline** workflow (8 stages)
2. **Design**: Architecture for notification system
3. **Plan**: Break into waves and tasks with dependencies
4. **Implement**: Write code with TDD (target 80% coverage)
5. **Review → Test → Refine**: Convergence loop until quality passes
6. **Gate**: Composite score must reach ≥85 with zero blockers
7. **Release**: Package and tag

Example: Quick Research (No Code)

```
Research the best approach for real-time notifications — compare WebSocket vs SSE vs polling
```

What happens:
1. DevolaFlow selects **research-only** workflow
2. Agent produces a structured comparison report, no code written

## Step 4: Explore More

See all 23 workflow types:[Workflow Types](workflow-types.md)Understand the architecture:[Architecture Overview](architecture-overview.md)Set up for your specific tool:[Integration Guide](integration-guide.md)Customize workflows:[Customization Guide](customization-guide.md)

## Checking for Updates

Ask your AI agent: `"update devola"`, it checks GitHub for newer versions and provides the exact update command.

Or from the terminal:

```bash
# Installer update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip update
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
