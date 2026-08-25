---
title: "Quick Start Guide"
description: "Getting started with DevolaFlow in under 10 minutes."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T04:33:10Z"
source_version: "16.0.0"
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
1. DevolaFlow matches the **hotfix checklist seed** from "fix" + "bug"
2. L0 anchors the goal, materialized checklist, and signed preflight with you
3. L0 picks the highest-priority checklist items and groups them into a wave
4. L1 Wave dispatches isolated L2 Tasks for diagnosis, remediation, and evidence
5. L0 verifies the evidence, checks completed assertions, and opens another bounded round if needed

### Example: Build a New Feature (Full Pipeline)

```
Implement a user notification system with email and in-app channels
```

What happens:
1. DevolaFlow selects the **full-pipeline checklist seed**
2. The seed's historical primitive provenance helps materialize measurable design, implementation, review, test, and release assertions; it does not prescribe execution order
3. You confirm the checklist priorities and preflight decisions
4. L0 runs bounded checklist rounds through L1 Waves and isolated L2 Tasks
5. Each checked item carries evidence; unresolved blockers remain open
6. The archive gate requires the checklist contract to pass before source truth changes

Example: Quick Research (No Code)

```
Research the best approach for real-time notifications — compare WebSocket vs SSE vs polling
```

What happens:
1. DevolaFlow selects the **research-only checklist seed**
2. The materialized checklist asks for a structured, evidenced comparison, no code written

## Step 4: Explore More

See all 23 checklist seeds:[Checklist Seed Catalog](workflow-types.md)Understand the architecture:[Architecture Overview](architecture-overview.md)Set up for your specific tool:[Integration Guide](integration-guide.md)Customize workflows:[Customization Guide](customization-guide.md)

## Checking for Updates

Ask your AI agent: `"update devola"`, it checks GitHub for newer versions and provides the exact update command.

Or from the terminal:

```bash
# Installer update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip update
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
