---
title: "Quick Start Guide"
description: "Getting started with DevolaFlow in under 10 minutes."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-07T07:16:17Z"
source_version: "2.1.0"
---

# Quick Start Guide

Getting started with DevolaFlow in under 10 minutes.

## Prerequisites

- Python 3.11+
- pip

## Installation

```bash
pip install -e ".[dev]"
```

## Your First Workflow

1. Run `detect-repo-mode` to identify your repository type
2. Run `validate-template --all` to verify templates are valid
3. Choose a workflow type based on your task
4. Follow the 4-layer hierarchy: Project dispatches Stages

## Checking Your Version

```bash
devola-version   # prints DevolaFlow vX.X.X
```

Or ask your AI agent: `"update devola"` to check the installed version and whether a newer release is available.

## Updating DevolaFlow

**From inside your AI tool** (recommended):

Type `"update devola"` or `"/update-devola"`. The agent checks GitHub for the latest version and provides the right command for your setup.

**From the terminal:**

```bash
# Installer update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip update
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```

## Next Steps

- Read the [Architecture Overview](architecture-overview.md)
- Explore [Workflow Types](workflow-types.md)
