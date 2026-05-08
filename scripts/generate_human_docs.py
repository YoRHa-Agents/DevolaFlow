#!/usr/bin/env python3
"""Generate human-readable docs from agent system files.

Design ref: design_dual_system.md section 4.1-4.2
Simplified v0.1.0: generates structured docs with practical content.

v10.1.0: pipes generated content through the writing-style humanizer
before write-out. Opt-out via `--no-humanize`; default is ON for
EN/ZH guides per Q-B (in-pipeline + `make humanize-docs` target).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    from devolaflow.writing_style import (
        apply_transforms,
        profile_for_path,
    )

    _HUMANIZE_AVAILABLE = True
except ImportError:  # pragma: no cover — writing_style ships at v10.1.0
    apply_transforms = None  # type: ignore[assignment]
    profile_for_path = None  # type: ignore[assignment]
    _HUMANIZE_AVAILABLE = False

DOCS = [
    (
        "quickstart",
        "Quick Start Guide",
        "Getting started with DevolaFlow in under 10 minutes.",
        "快速入门指南",
        "10 分钟内开始使用 DevolaFlow。",
    ),
    (
        "architecture-overview",
        "Architecture Overview",
        "System architecture: 4-layer hierarchy, stage primitives, gate mechanism.",
        "架构概述",
        "系统架构：4 层层级、阶段原语、质量门机制。",
    ),
    (
        "workflow-types",
        "Workflow Types Catalog",
        "22 built-in workflow types with selection guidance.",
        "工作流类型目录",
        "22 种内置工作流类型及选择指南。",
    ),
    (
        "agent-hierarchy-guide",
        "Agent Hierarchy Guide",
        "Understanding the 4-layer delegation hierarchy.",
        "Agent 层级指南",
        "理解 4 层委托层级架构。",
    ),
    (
        "customization-guide",
        "Customization Guide",
        "Creating custom workflow templates and derived configurations.",
        "自定义指南",
        "创建自定义工作流模板和派生配置。",
    ),
    (
        "integration-guide",
        "Integration Guide",
        "Integrating DevolaFlow with Cursor, Claude Code, Copilot, and Codex.",
        "集成指南",
        "将 DevolaFlow 与 Cursor、Claude Code、Copilot 和 Codex 集成。",
    ),
    (
        "troubleshooting",
        "Troubleshooting",
        "Common issues and solutions for workflow execution.",
        "故障排查",
        "工作流执行中的常见问题和解决方案。",
    ),
    (
        "faq",
        "FAQ",
        "Frequently asked questions about the workflow system.",
        "常见问题",
        "关于工作流系统的常见问题解答。",
    ),
]

SOURCE_FILES = ["SKILL.md"]
SOURCE_VERSION = "11.1.3"


def _gen_doc(
    slug: str,
    title: str,
    desc: str,
    lang: str,
    output_dir: Path,
    *,
    humanize: bool = True,
) -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fm = f'---\ntitle: "{title}"\ndescription: "{desc}"\nsource_files:\n'
    for sf in SOURCE_FILES:
        fm += f'  - "{sf}"\n'
    fm += f'auto_generated: true\nlast_synced: "{now}"\nsource_version: "{SOURCE_VERSION}"\n---\n\n'
    content = fm + f"# {title}\n\n{desc}\n\n"

    if lang == "en":
        content += _gen_en_content(slug)
    else:
        content += _gen_zh_content(slug)

    if humanize and _HUMANIZE_AVAILABLE:
        rel_path = f"workflow-system/human/{lang}/{slug}.md"
        profile = profile_for_path(rel_path)
        result = apply_transforms(content, profile)
        content = result.after

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def _gen_en_content(slug: str) -> str:
    sections = {
        "quickstart": _en_quickstart(),
        "architecture-overview": _en_architecture(),
        "workflow-types": _en_workflow_types(),
        "agent-hierarchy-guide": _en_hierarchy(),
        "faq": _en_faq(),
        "integration-guide": _en_integration(),
        "customization-guide": _en_customization(),
        "troubleshooting": _en_troubleshooting(),
    }
    return sections.get(slug, f"## {slug.replace('-', ' ').title()}\n\nContent coming soon.\n")


def _gen_zh_content(slug: str) -> str:
    sections = {
        "quickstart": _zh_quickstart(),
        "architecture-overview": _zh_architecture(),
        "workflow-types": _zh_workflow_types(),
        "agent-hierarchy-guide": _zh_hierarchy(),
        "faq": _zh_faq(),
        "integration-guide": _zh_integration(),
        "customization-guide": _zh_customization(),
        "troubleshooting": _zh_troubleshooting(),
    }
    return sections.get(slug, f"## {slug.replace('-', ' ').title()}\n\n内容即将推出。\n")


# ═══════════════════════════════════════════════════════════════════
# English content generators
# ═══════════════════════════════════════════════════════════════════


def _en_quickstart() -> str:
    return """\
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

**Option C — Manual (single file):**

Download [SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md) and place it in:

| Tool | Path |
|------|------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `./CLAUDE.md` |
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

### Example: Quick Research (No Code)

```
Research the best approach for real-time notifications — compare WebSocket vs SSE vs polling
```

What happens:
1. DevolaFlow selects **research-only** workflow
2. Agent produces a structured comparison report — no code written

## Step 4: Explore More

- See all 22 workflow types: [Workflow Types](workflow-types.md)
- Understand the architecture: [Architecture Overview](architecture-overview.md)
- Set up for your specific tool: [Integration Guide](integration-guide.md)
- Customize workflows: [Customization Guide](customization-guide.md)

## Checking for Updates

Ask your AI agent: `"update devola"` — it checks GitHub for newer versions and provides the exact update command.

Or from the terminal:

```bash
# Installer update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip update
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
"""


def _en_architecture() -> str:
    return """\
## System Overview

DevolaFlow orchestrates complex software tasks through a **4-layer agent hierarchy** with **quality gates** at every stage boundary. Instead of one agent trying to do everything, work is decomposed into isolated tasks executed by specialized agents.

```
User Request
    │
    ▼
┌─────────────────────┐
│   Pre-Decision       │  Detect repo mode, recommend workflow type
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L0: Project Agent   │  Select workflow, sequence stages    (~3K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L1: Stage Agent     │  Decompose into waves, run gates     (~5K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L2: Wave Agent      │  Dispatch parallel tasks              (~4K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L3: Task Agent      │  **Execute actual work**              (~8K tok)
└─────────────────────┘
```

**Key invariant**: Only Layer 3 (Task Agents) perform actual work — writing code, running tests, reviewing, authoring documents. Layers 0–2 exclusively dispatch, monitor, and report.

## The 4-Layer Hierarchy

| Layer | Role | Context Budget | Delegates To | Must NOT |
|-------|------|---------------|-------------|----------|
| **L0: Project** | Selects workflow, sequences stages, tracks status | ~3K tokens | Stage Agents | Write code, read source files |
| **L1: Stage** | Decomposes stage into waves, runs convergence loops | ~5K tokens | Wave Agents | Write code, execute tests |
| **L2: Wave** | Dispatches parallel tasks, checks for conflicts | ~4K tokens | Task Agents | Modify any task's output |
| **L3: Task** | Executes a single atomic unit of work | ~8K tokens | Nothing (leaf) | Spawn sub-agents |

## 13 Stage Primitives

Every workflow is composed from 13 universal primitives organized into 6 categories:

| Category | Primitives | Purpose |
|----------|-----------|---------|
| **Discover** | `research`, `analyze` | Gather information, assess current state |
| **Shape** | `design`, `plan` | Define architecture, decompose into tasks |
| **Build** | `implement`, `refine` | Write code, fix issues |
| **Verify** | `review`, `test`, `validate` | Check quality, run tests, aggregate results |
| **Deliver** | `release`, `deploy`, `monitor` | Package, ship, observe |
| **Control** | `gate` | Quality checkpoint blocking progression |

Primitives compose via 5 operators: **sequence** (→), **parallel** (||), **choice** (⊕), **loop** (↻), **gate** (⊣).

## Task-Adaptive Context Selection

Each task type has a **context profile** that selects only relevant SKILL.md sections, keeping the context window lean:

- A **hotfix** agent receives: triage procedures, fix guidelines, test requirements — but skips design primitives
- A **research** agent receives: research methodology, comparison frameworks — but skips convergence loops
- A **design** agent receives: architecture patterns, ADR templates — but skips release procedures

Profiles are defined in `workflow-system/agent/context_profiles.yaml`.

## Quality Gate Mechanism

Gates are quality checkpoints between stages. Every gate evaluates a **composite score**:

```
composite = test_quality × 0.30 + code_review × 0.30
          + architecture × 0.20 + benchmark × 0.20
```

**Pass conditions** (all required):
1. `composite_score >= threshold` (default: 85)
2. Zero blocker findings AND zero MUST-priority violations
3. `coverage >= coverage_threshold` (default: 80%)

**On failure**: The gate triggers a convergence loop (review → fix → test → recheck), up to 3 rounds. If still failing, it escalates to the human.

**Gate profiles**:

| Profile | Threshold | Coverage | Use When |
|---------|-----------|----------|----------|
| relaxed | ≥70 | ≥60% | Prototypes, spikes |
| standard | ≥85 | ≥80% | Normal development |
| strict | ≥90 | ≥90% | Production releases |
| audit | ≥95 | ≥90% | Security, compliance |

## Context Isolation

Each Task Agent spawns with a fresh, isolated context (~8K tokens max):

- **Identity**: role, task_id, team assignment
- **Task spec**: title, description, acceptance criteria
- **Context**: predecessor summaries, design excerpts, interface contracts
- **Files**: owned files (create/modify) + read-only references
- **Rules**: coding conventions, quality focus areas
- **Behavioral**: timeout, max files, escalation policy

**Never leaked between tasks**: conversation history, file contents from sibling tasks, error details from parallel work, quality scores from unrelated tasks.

## Repository Rules

18 enforceable rules in `.cursor/rules/` codifying iteration lessons:

| Rule File | Covers |
|-----------|--------|
| `skill-format-rules.mdc` (SF-1 to SF-6) | SKILL.md line budget, frontmatter, version consistency, valid references |
| `change-process-rules.mdc` (CP-1 to CP-7) | Test coverage floor (≥80%), no ghost features, version bump protocol |
| `context-optimization-rules.mdc` (CO-1 to CO-6) | Lean messages, verbatim extraction, token budgets, benchmark verification |
"""


def _en_workflow_types() -> str:
    return """\
## Workflow Selection

DevolaFlow automatically selects the right workflow based on your prompt. You can also specify one explicitly.

**Selection heuristics:**
- Urgency signals ("urgent", "ASAP", "production down") → `hotfix`
- "From scratch" / "new project" → `full-pipeline`
- Question-form phrasing ("what", "how", "which") → `research-only`
- Explicit type mention → direct match (highest priority)

## All 22 Built-in Workflow Types

### Discover Workflows

#### `research-only`
**When to use**: Survey prior art, compare alternatives, evaluate options.
**Stages**: research → compare → report
**Teams**: Research (primary)
**Example prompt**: `"Research the best ORM for our Python project — compare SQLAlchemy, Peewee, and Tortoise"`

#### `onboarding`
**When to use**: New contributor joining, understanding an unfamiliar codebase, resuming a dormant project.
**Stages**: analyze (codebase survey) → document (onboarding docs) → setup (dev environment) → verify (smoke tests)
**Teams**: Research, Implement, Test
**Example prompt**: `"I'm new to this project — help me understand the codebase and set up my dev environment"`

### Optimize Workflows

#### `skill-optimization`
**When to use**: Optimize agent skills, benchmark context density, improve information routing.
**Stages**: survey → profile → optimize → benchmark → iterate → document
**Teams**: Research, Implement, Test, Review
**Example prompt**: `"Optimize the DevolaFlow skill — benchmark context density and reduce noise"`

### Shape Workflows

#### `design-only`
**When to use**: Architecture decisions, API design, schema design.
**Stages**: research → design → review
**Teams**: Design (primary), Review
**Example prompt**: `"Design the API for a multi-tenant notification service"`

#### `RDRR` (Research-Design-Review-Refine)
**When to use**: Iterative design that needs research backing and multiple review rounds.
**Stages**: research → design → review → refine (loop)
**Teams**: Research, Design, Review (all primary)
**Example prompt**: `"Design a caching architecture — research options first, then iterate the design"`

### Build Workflows

#### `hotfix`
**When to use**: Production bug, urgent fix, security patch.
**Stages**: triage → fix → test → release
**Teams**: Implement (primary), Test
**Example prompt**: `"Fix the login timeout bug — users get 500 errors after 30 seconds"`

#### `refactoring`
**When to use**: Tech debt, code restructuring, simplification.
**Stages**: scope → plan → implement → test → review
**Teams**: Implement, Test (both primary)
**Example prompt**: `"Refactor the payment module to use the strategy pattern"`

#### `migration`
**When to use**: Upgrade frameworks, port between systems, database migrations.
**Stages**: assess → plan → implement → validate → cutover
**Teams**: Research, Implement, Test
**Example prompt**: `"Migrate from Express.js to Fastify — keep all existing endpoints"`

#### `performance-optimization`
**When to use**: Slow app, high latency, memory issues, build time optimization.
**Stages**: profile → design (optimization plan) → optimize → benchmark → validate
**Teams**: Research, Design, Implement, Test
**Example prompt**: `"Our API response time is >2 seconds — profile and optimize the hot paths"`

#### `dependency-setup`
**When to use**: Setting up dev environment, adding major dependencies, configuring tooling.
**Stages**: research → plan (dependency graph) → configure → verify
**Teams**: Research, Design, Implement, Test
**Example prompt**: `"Set up Docker development environment with hot reloading for our Python API"`

#### `feature-enhancement`
**When to use**: Adding to existing features, extending functionality.
**Stages**: scope → design → plan → implement → review → test → release
**Teams**: All (Design and Implement primary)
**Example prompt**: `"Add dark mode support to the settings page"`

#### `full-pipeline`
**When to use**: Greenfield features, new projects, anything requiring the full lifecycle.
**Stages**: design → plan → implement → review → test → refine → gate → release
**Teams**: All (all primary)
**Example prompt**: `"Build a user authentication system with OAuth2, JWT, and role-based access"`

### Verify Workflows

#### `security-audit`
**When to use**: Vulnerability scanning, compliance checks, CVE remediation.
**Stages**: threat-model → scan → analyze → remediate → verify
**Teams**: Research, Implement, Test, Review (all active)
**Example prompt**: `"Run a security audit on our authentication module — check for OWASP Top 10"`

### Deliver Workflows

#### `documentation`
**When to use**: Writing or updating docs, README, API references, tutorials.
**Stages**: survey → author → review
**Teams**: Research, Review
**Example prompt**: `"Write comprehensive API documentation for the payments module"`

#### `demo-showcase`
**When to use**: Building demos for stakeholders, interactive showcases, conference presentations.
**Stages**: research → storyboard (design) → build-demo → demo-review → polish → package
**Teams**: Research, Design, Implement, Review
**Example prompt**: `"Build an interactive demo showcasing our new dashboard — make it presentation-ready"`

### Composite Workflows

#### `spike-poc`
**When to use**: Testing feasibility, prototyping, evaluating new tech.
**Stages**: research (hypothesis) → prototype → evaluate
**Teams**: Research, Implement
**Example prompt**: `"Prototype real-time collaboration using CRDTs — is it feasible for our scale?"`

#### `self-update`
**When to use**: Track external reference dependencies and integrate improvements.
**Stages**: check-refs → research-updates → decompose → integrate → test → evaluate
**Teams**: Research, Implement, Test
**Example prompt**: `"update refs"`, `"self-update"`, `"check references"`

#### `change-driven`
**When to use**: Manage an in-flight change with structured `.local/.agent/active/<id>/` artifacts (goal, acceptance, spec, tasks, STATUS, owned_files); archive on success with auto-generated REPORT.md and propose delta merge to source-of-truth specs.
**Stages**: propose → apply → verify → archive (mode: lite \\| full)
**Teams**: Design, Implement, Test
**Example prompt**: `"propose change to add dark mode"`, `"apply v8.3.0-pv09"`, `"archive add-auth-bug"`

## Quick Reference Table

| Type | Trigger Keywords | Stages | Gate Profile |
|------|-----------------|--------|-------------|
| `research-only` | research, compare, survey | 3 | — |
| `design-only` | design, architect, API spec | 3 | standard |
| `hotfix` | fix bug, broken, crash, SEV1 | 4 | relaxed |
| `refactoring` | refactor, clean up, tech debt | 5 | standard |
| `migration` | migrate, upgrade, port | 5 | standard |
| `spike-poc` | prototype, experiment, PoC | 3 | — |
| `documentation` | write docs, README, guide | 3 | relaxed |
| `security-audit` | security, audit, CVE | 5 | strict |
| `feature-enhancement` | add to, extend, enhance | 7 | standard |
| `full-pipeline` | from scratch, new project | 8 | standard |
| `RDRR` | design with research, ADR | 4 (loop) | standard |
| `demo-showcase` | demo, showcase, presentation | 6 | relaxed |
| `performance-optimization` | slow, optimize, benchmark | 5 | standard |
| `dependency-setup` | setup, install, configure env | 4 | relaxed |
| `onboarding` | new to project, getting started | 4 | — |
| `skill-optimization` | optimize skill, benchmark context | 6 | convergence |
| `self-update` | update refs, self-update, check references | 6 | standard |
| `change-driven` | change, propose, apply, archive, lifecycle, OpenSpec | 4 | convergence |
"""


def _en_hierarchy() -> str:
    return """\
## Why a Hierarchy?

A single AI agent attempting a complex task (e.g., "build an auth system") faces two problems:
1. **Context overflow** — it tries to hold everything in memory at once
2. **Scope creep** — it drifts between design, implementation, and review without structure

DevolaFlow solves this by splitting work across 4 layers, each with a strict context budget and a clear role.

## Layer 0: Project Agent (~3K tokens)

The Project Agent is the **orchestra conductor**. It:
- Receives the user's request and selects a workflow type
- Sequences stages and dispatches them one at a time
- Evaluates gate results to decide: advance, retry, or escalate
- Reports final status to the human

**Never does**: Read source code, write files, run tests, or review code.

## Layer 1: Stage Agent (~5K tokens)

Each Stage Agent owns **one stage** of the workflow (e.g., "Design", "Implement"). It:
- Receives the stage definition and predecessor summaries
- Decomposes the stage into waves (groups of parallel tasks)
- Runs convergence loops if review/test findings require iteration
- Evaluates the stage's quality gate

**Constraints**: Max 7 waves per stage. Gate evaluation is mandatory before advancing.

## Layer 2: Wave Agent (~4K tokens)

A Wave Agent dispatches **parallel tasks** within a wave. It:
- Assigns tasks to Task Agents with disjoint file ownership
- Collects results and checks for cross-task conflicts
- Reports wave completion status to the Stage Agent

**Constraints**: Max 5 tasks per wave. File ownership must not overlap between parallel tasks.

## Layer 3: Task Agent (~8K tokens)

The Task Agent is the **only layer that does actual work**. It:
- Receives a single, atomic task with clear acceptance criteria
- Works within its owned files only (max 6 writable files)
- Produces artifacts (code, tests, docs, reports)
- Reports completion with metrics (tests passed, coverage, findings)

**Constraints**: Max 30 min (implementation) or 45 min (research). Cannot spawn sub-agents.

## Escalation Chain

```
Task Agent → Wave Agent → Stage Agent → Project Agent → Human
```

Escalation always moves **upward**, never skips levels. Every failure is classified:

| Severity | Action |
|----------|--------|
| `AUTO_RECOVER` | Retry up to 3× with exponential backoff |
| `PAUSE` | Pause task, queue question, continue parallel work |
| `HUMAN_INTERVENE` | Stop stage, present options to human |
| `FULL_ROLLBACK` | Rollback to checkpoint, halt everything |

## Communication Protocol

All inter-layer communication uses **typed YAML messages** (not free-form chat):

- **TaskDispatch**: task_id, type, title, description, owned_files, acceptance_criteria, timeout
- **StatusReport**: task_id, state, progress_pct, artifacts, metrics
- **ExceptionEscalation**: severity, context, options for the next layer

## Example: Hotfix Trace

```
Human: "Fix the login timeout bug"
  └─ Project Agent: selects hotfix workflow
       └─ Stage Agent (Triage): dispatches 1 wave
            └─ Wave Agent: dispatches 1 task
                 └─ Task Agent: analyzes bug, identifies root cause
       └─ Stage Agent (Fix): dispatches 1 wave
            └─ Wave Agent: dispatches 1 task
                 └─ Task Agent: implements minimal fix (3 files changed)
       └─ Stage Agent (Test): dispatches 1 wave
            └─ Wave Agent: dispatches 1 task
                 └─ Task Agent: runs focused test suite (42 pass, 0 fail)
       └─ Stage Agent (Release): dispatches 1 wave
            └─ Task Agent: tags v1.2.1, updates changelog
  └─ Project Agent: reports SUCCESS to human
```
"""


def _en_faq() -> str:
    return """\
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
- And so on for all 22 types

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
"""


def _en_integration() -> str:
    return """\
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

### How It Works in Cursor

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
   - **Plan stage**: Breaks into waves — auth module (Wave 1), CRUD endpoints (Wave 2), RBAC (Wave 3)
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

- **Attach the skill manually** for complex tasks: Type `@devola-flow` to explicitly reference the skill
- **Use Plan mode** for architectural decisions: The agent will produce a structured plan instead of executing
- **Subagent support**: Cursor's Task tool maps naturally to DevolaFlow's Wave→Task delegation

## Claude Code — Detailed Setup

### Installation

```bash
# Project-local (applies to current directory)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# User-global (applies to all sessions)
curl -fsSL $INSTALLER | bash -s claude --global
```

This installs a single self-contained `CLAUDE.md` file. Claude Code reads this file at the start of every session.

### How It Works in Claude Code

`CLAUDE.md` is always active — Claude Code loads it automatically. Every prompt benefits from DevolaFlow's workflow structure.

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

### Tips for Claude Code

- CLAUDE.md is self-contained — no external references needed
- Works with Claude Code's native subagent support
- Use `"update devola"` to trigger version checks within a session

## GitHub Copilot — Detailed Setup

### Installation

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

This installs:
- `.github/copilot-instructions.md` — root instructions
- `.github/instructions/workflow.instructions.md` — workflow-specific instructions

### How It Works in Copilot

Copilot reads `copilot-instructions.md` for every request. The workflow heuristics guide Copilot's code suggestions and chat responses to follow structured patterns.

### Example Session

In Copilot Chat:
```
@workspace Refactor the payment processing module to use the strategy pattern
```

Copilot follows the `refactoring` workflow: scope analysis → plan → implement → test → review.

## OpenAI Codex — Detailed Setup

### Installation

```bash
# Codex uses global skills
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

This installs:
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/agents/openai.yaml`

### How It Works in Codex

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
"""


def _en_customization() -> str:
    return """\
## Creating Custom Workflow Templates

Workflow templates are YAML files in `workflow-system/agent/templates/builtin/`. Each template follows the schema defined in `schemas/workflow-template.schema.yaml`.

### Template Structure

```yaml
schema_version: "1.0"

metadata:
  name: my-workflow          # unique kebab-case id
  version: "1.0.0"
  display_name: "My Workflow"
  description: "What this workflow does"
  category: build            # discover | shape | build | deliver | composite
  applicable_scenarios:
    - "When to recommend this workflow"
  tags: [keyword1, keyword2]

stages:
  - id: stage_id
    primitive: implement     # one of 13 primitives
    alias: friendly-name     # optional display name
    description: "What this stage does"
    team: implement          # research | design | implement | test | review
    duration_class: medium   # quick | medium | long
    config:
      test_strategy: tdd
    input_mapping:
      tasks: "previous_stage.output"

composition:
  compose: sequence
  stages:
    - stage: stage_id
    - compose: loop
      ref: my_loop

loops:
  - name: my_loop
    body_stages: [stage_a, stage_b]
    until: "stage_b.pass_rate == 1.0"
    max_iterations: 3
    on_exhaustion: escalate

gates:
  - name: quality_gate
    position: "after:stage_id"
    criteria:
      - field: stage_id.metric
        operator: ">="
        value: 0.80
    on_pass: "next"
    on_fail:
      action: loop_back
      target: stage_id

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

### Example: Custom "Code Review Only" Template

```yaml
schema_version: "1.0"

metadata:
  name: code-review
  version: "1.0.0"
  display_name: "Code Review Only"
  description: "Standalone code review without implementation."
  category: verify
  applicable_scenarios:
    - "Reviewing a PR or code submission"
  tags: [review, quality, check]

stages:
  - id: review
    primitive: review
    description: "Review code for quality, security, and style"
    team: review
    duration_class: medium
    config:
      review_type: code
      pass_threshold: 0.80

composition:
  compose: sequence
  stages:
    - stage: review

loops: []
gates: []

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

## Custom Context Profiles

Edit `workflow-system/agent/context_profiles.yaml` to add profiles for new task types. Each profile specifies which SKILL.md sections to include at what priority:

- **critical**: Always included, loaded first
- **important**: Included if token budget allows
- **supplementary**: Included only if space remains
- **skip**: Never included for this task type

## Deriving Templates

Use the `extends` field to inherit from a builtin template and override specific stages:

```yaml
metadata:
  name: my-enhanced-hotfix
  extends: hotfix

stages:
  - id: notify
    primitive: release
    alias: notify
    description: "Send Slack notification after fix"
```

## Validating Changes

After customizing, always verify:

```bash
validate-template --all                # templates are valid
python -m pytest tests/ -q             # all tests pass
python -m benchmarks.devolaflow_context.runner --scenario all  # no regressions
build-skill --all                      # adapters build successfully
```
"""


def _en_troubleshooting() -> str:
    return """\
## Installation Issues

### `devola-init` command not found

The CLI tools require pip installation:
```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
# Or for development:
pip install -e ".[dev]"
```

### Installer fails with "permission denied"

The installer needs write access to the target directory. For global installs:
```bash
# Cursor global
curl -fsSL $INSTALLER | bash -s cursor --global
# This writes to ~/.cursor/skills/ which should be user-writable
```

## Workflow Issues

### Agent doesn't select the right workflow

DevolaFlow uses keyword matching. Make your intent explicit:
- Instead of: "Help me with the login page"
- Try: "Fix the bug in the login page" (→ hotfix) or "Redesign the login page UI" (→ design-only)

You can also specify directly: "Use the refactoring workflow to clean up auth module."

### Agent tries to do everything in one pass

This usually means the skill file isn't loaded. Verify:
1. Check the skill file exists: `ls .cursor/skills/devola-flow/SKILL.md`
2. In Cursor, verify the skill appears in settings
3. Try explicitly attaching: `@devola-flow implement a user system`

### Convergence loop runs too many times

The default max is 3 iterations. If the agent keeps looping:
1. Check if acceptance criteria are too strict
2. Look for conflicting requirements that prevent convergence
3. The agent will escalate to you after max iterations — review the divergence report

## Test & Build Issues

### Tests fail after SKILL.md changes

Run `python -m pytest tests/test_version.py -v` to check version consistency. Use `scripts/bump_version.py` for consistent updates across all version locations.

### `build-skill` reports budget exceeded

SKILL.md must stay under 500 lines (rule SF-1). Check with `wc -l` and compress verbose sections. Run `build-skill --all` to verify after changes.

### Template validation fails

```bash
validate-template path/to/template.yaml
```

Common causes:
- Missing required fields (`schema_version`, `metadata`, `stages`, `composition`)
- Stage references in `composition` that don't match any `stages[].id`
- Loop references that don't match any `loops[].name`
- Invalid primitive names (must be one of the 13 primitives)

## Benchmark Issues

### EvoBench shows regressions

```bash
python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline
```

If a scenario regressed:
1. Check recent changes to `context_profiles.yaml` or SKILL.md section boundaries
2. Review the specific scenario's expected vs actual section selection
3. After fixing, update baselines: `python -m benchmarks.devolaflow_context.runner --generate-baseline`

### Context profiles not loading

Verify `context_profiles.yaml` exists at `workflow-system/agent/context_profiles.yaml` and its section line ranges match the current SKILL.md structure.

## Getting Help

- **GitHub Issues**: [https://github.com/YoRHa-Agents/DevolaFlow/issues](https://github.com/YoRHa-Agents/DevolaFlow/issues)
- **Interactive Demo**: [https://yorha-agents.github.io/DevolaFlow/](https://yorha-agents.github.io/DevolaFlow/)
"""


# ═══════════════════════════════════════════════════════════════════
# Chinese content generators
# ═══════════════════════════════════════════════════════════════════


def _zh_quickstart() -> str:
    return """\
## 前置条件

- Python 3.11+
- pip
- 以下工具之一：Cursor、Claude Code、GitHub Copilot 或 OpenAI Codex

## 第一步：安装 DevolaFlow

选择适合你的安装方式：

**方式 A — 一键安装（推荐）：**

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

# 为 Cursor 安装（项目级）
curl -fsSL $INSTALLER | bash -s cursor

# 或为所有工具一次性安装
curl -fsSL $INSTALLER | bash -s all
```

**方式 B — pip 安装：**

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project/
devola-init cursor       # 仅 Cursor
devola-init all          # 所有工具
```

**方式 C — 手动安装（单文件）：**

下载 [SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md) 并放置到：

| 工具 | 路径 |
|------|------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `./CLAUDE.md` |
| Copilot | `.github/copilot-instructions.md` |
| Codex | `~/.codex/skills/devola-flow/SKILL.md` |

## 第二步：验证安装

```bash
devola-version   # 应输出当前 DevolaFlow 版本
```

## 第三步：尝试你的第一个工作流

打开你的 AI 工具，尝试以下提示词：

### 示例：修复一个 Bug（热修复工作流）

```
修复登录超时 bug — 用户在 30 秒不活动后报告 500 错误
```

幕后发生了什么：
1. DevolaFlow 从 "修复" + "bug" 检测到 **hotfix** 意图
2. **分诊阶段**：Agent 分析 bug，定位根因
3. **修复阶段**：Agent 实现最小化修复
4. **测试阶段**：Agent 对受影响代码运行聚焦测试
5. **发布阶段**：Agent 准备补丁部署

### 示例：构建新功能（完整流水线）

```
实现一个用户通知系统，支持邮件和应用内消息两种渠道
```

发生了什么：
1. DevolaFlow 选择 **full-pipeline** 工作流（8 个阶段）
2. **设计**：通知系统架构
3. **规划**：分解为批次和任务
4. **实现**：TDD 编写代码（目标 80% 覆盖率）
5. **审查 → 测试 → 修正**：收敛循环直到质量达标
6. **质量门**：复合评分须达到 ≥85 且零阻断问题
7. **发布**：打包和标签

### 示例：快速调研（无代码）

```
调研实时通知的最佳方案 — 对比 WebSocket、SSE 和轮询
```

发生了什么：
1. DevolaFlow 选择 **research-only** 工作流
2. Agent 生成结构化对比报告 — 不写代码

## 第四步：深入探索

- 查看全部 22 种工作流：[工作流类型](workflow-types.md)
- 了解架构：[架构概述](architecture-overview.md)
- 为你的工具进行设置：[集成指南](integration-guide.md)
- 自定义工作流：[自定义指南](customization-guide.md)

## 检查更新

在 AI 工具中输入：`"update devola"` — 它会从 GitHub 检查新版本并提供更新命令。

或在终端中：

```bash
# 安装器更新
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip 更新
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
"""


def _zh_architecture() -> str:
    return """\
## 系统概述

DevolaFlow 通过 **4 层代理层级** 和 **质量门** 来编排复杂的软件任务。工作被分解为隔离的任务，由专门的代理执行，而不是让一个代理尝试完成所有事情。

```
用户请求
    │
    ▼
┌─────────────────────┐
│   预决策              │  检测仓库模式，推荐工作流类型
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L0: 项目代理         │  选择工作流，排序阶段    (~3K tokens)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L1: 阶段代理         │  分解为批次，运行质量门  (~5K tokens)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L2: 批次代理         │  分派并行任务            (~4K tokens)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L3: 任务代理         │  **执行实际工作**        (~8K tokens)
└─────────────────────┘
```

**关键不变量**：只有 L3（任务代理）执行实际工作 — 编写代码、运行测试、审查代码、撰写文档。L0–L2 只负责分派、监控和汇报。

## 4 层层级

| 层级 | 角色 | 上下文预算 | 委托给 | 不可以 |
|------|------|-----------|--------|--------|
| **L0: 项目** | 选择工作流，排序阶段 | ~3K tokens | 阶段代理 | 写代码、读源文件 |
| **L1: 阶段** | 分解为批次，运行收敛循环 | ~5K tokens | 批次代理 | 写代码、执行测试 |
| **L2: 批次** | 分派并行任务，检查冲突 | ~4K tokens | 任务代理 | 修改任务输出 |
| **L3: 任务** | 执行单个原子工作单元 | ~8K tokens | 无（叶节点） | 派生子代理 |

## 13 个阶段原语

每个工作流由 13 个通用原语组合而成：

| 类别 | 原语 | 用途 |
|------|------|------|
| **发现** | `research`, `analyze` | 收集信息，评估现状 |
| **塑形** | `design`, `plan` | 定义架构，分解为任务 |
| **构建** | `implement`, `refine` | 编写代码，修复问题 |
| **验证** | `review`, `test`, `validate` | 检查质量，运行测试 |
| **交付** | `release`, `deploy`, `monitor` | 打包，发布，观测 |
| **控制** | `gate` | 阻断推进的质量检查点 |

## 任务自适应上下文选择

每种任务类型有一个 **上下文配置**，只选择相关的 SKILL.md 段落：

- **热修复** 代理接收：分诊流程、修复指南、测试要求 — 跳过设计原语
- **调研** 代理接收：调研方法、对比框架 — 跳过收敛循环
- **设计** 代理接收：架构模式、ADR 模板 — 跳过发布流程

## 质量门机制

```
composite = test_quality × 0.30 + code_review × 0.30
          + architecture × 0.20 + benchmark × 0.20
```

**通过条件**（全部必须满足）：
1. `composite_score >= 85`
2. 零阻断问题
3. `coverage >= 80%`

**失败时**：触发收敛循环（审查 → 修复 → 测试 → 复查），最多 3 轮。仍失败则升级到人工。

## 仓库规则

`.cursor/rules/` 中的 18 条可执行规则：

| 规则文件 | 涵盖内容 |
|---------|---------|
| `skill-format-rules.mdc` (SF-1 到 SF-6) | SKILL.md 行数预算、前置元数据、版本一致性 |
| `change-process-rules.mdc` (CP-1 到 CP-7) | 测试覆盖率底线（≥80%）、无幽灵功能 |
| `context-optimization-rules.mdc` (CO-1 到 CO-6) | 精简消息、逐字提取、基准验证 |
"""


def _zh_workflow_types() -> str:
    return """\
## 工作流选择

DevolaFlow 根据你的提示词自动选择合适的工作流。你也可以显式指定。

**选择策略：**
- 紧急信号（"紧急"、"生产环境故障"）→ `hotfix`
- "从零开始" / "新项目" → `full-pipeline`
- 问题形式（"什么"、"如何"、"哪个"）→ `research-only`
- 显式指定类型 → 直接匹配（最高优先级）

## 全部 22 种内置工作流类型

### 发现类工作流

#### `research-only`
**适用场景**：调研先例、比较方案、评估选项。
**阶段**：research → compare → report
**示例**：`"调研最适合我们 Python 项目的 ORM — 对比 SQLAlchemy、Peewee 和 Tortoise"`

#### `onboarding`
**适用场景**：新成员加入、了解陌生代码库、恢复休眠项目。
**阶段**：analyze → document → setup → verify
**示例**：`"我是这个项目的新人 — 帮我了解代码库并设置开发环境"`

### 优化类工作流

#### `skill-optimization`
**适用场景**：优化 Agent 技能、基准测试上下文密度、改进信息路由。
**阶段**：survey → profile → optimize → benchmark → iterate → document
**示例**：`"优化 DevolaFlow 技能 — 基准测试上下文密度并减少噪声"`

### 塑形类工作流

#### `design-only`
**适用场景**：架构决策、API 设计、Schema 设计。
**阶段**：research → design → review
**示例**：`"设计多租户通知服务的 API"`

#### `RDRR`（调研-设计-审查-精炼）
**适用场景**：需要调研支撑的迭代设计。
**阶段**：research → design → review → refine（循环）
**示例**：`"设计缓存架构 — 先调研选项，然后迭代设计"`

### 构建类工作流

#### `hotfix`
**适用场景**：生产 bug、紧急修复、安全补丁。
**阶段**：triage → fix → test → release
**示例**：`"修复登录超时 bug — 用户 30 秒后报 500 错误"`

#### `refactoring`
**适用场景**：技术债务、代码重构、简化。
**阶段**：scope → plan → implement → test → review
**示例**：`"将支付模块重构为策略模式"`

#### `migration`
**适用场景**：升级框架、系统迁移、数据库迁移。
**阶段**：assess → plan → implement → validate → cutover
**示例**：`"从 Express.js 迁移到 Fastify — 保留所有现有端点"`

#### `performance-optimization`
**适用场景**：应用慢、延迟高、内存问题、构建时间优化。
**阶段**：profile → design → optimize → benchmark → validate
**示例**：`"我们的 API 响应时间超过 2 秒 — 分析并优化热路径"`

#### `dependency-setup`
**适用场景**：搭建开发环境、添加依赖、配置工具链。
**阶段**：research → plan → configure → verify
**示例**：`"为我们的 Python API 搭建 Docker 开发环境，支持热重载"`

#### `feature-enhancement`
**适用场景**：扩展现有功能。
**阶段**：scope → design → plan → implement → review → test → release
**示例**：`"为设置页面添加暗色模式"`

#### `full-pipeline`
**适用场景**：全新功能、新项目、需要完整生命周期的任务。
**阶段**：design → plan → implement → review → test → refine → gate → release
**示例**：`"构建用户认证系统，支持 OAuth2、JWT 和角色权限"`

### 验证类工作流

#### `security-audit`
**适用场景**：漏洞扫描、合规检查、CVE 修复。
**阶段**：threat-model → scan → analyze → remediate → verify
**示例**：`"对认证模块进行安全审计 — 检查 OWASP Top 10"`

### 交付类工作流

#### `documentation`
**适用场景**：编写或更新文档、README、API 参考。
**阶段**：survey → author → review
**示例**：`"为支付模块编写完整的 API 文档"`

#### `demo-showcase`
**适用场景**：为利益相关者构建演示、交互式展示、会议演讲。
**阶段**：research → storyboard → build-demo → demo-review → polish → package
**示例**：`"构建一个交互式演示展示我们的新仪表板 — 要展示级别的质量"`

### 复合工作流

#### `spike-poc`
**适用场景**：可行性测试、原型开发、评估新技术。
**阶段**：research → prototype → evaluate
**示例**：`"使用 CRDT 原型实现实时协作 — 在我们的规模下可行吗？"`

#### `self-update`
**适用场景**：跟踪外部参考依赖并集成改进。
**阶段**：check-refs → research-updates → decompose → integrate → test → evaluate
**示例**：`"update refs"`、`"self-update"`、`"check references"`

#### `change-driven`
**适用场景**：以结构化 `.local/.agent/active/<id>/` 工件（goal、acceptance、spec、tasks、STATUS、owned_files）管理在制品变更；成功后归档并自动生成 REPORT.md，向 source-of-truth 规范提议增量合并。
**阶段**：propose → apply → verify → archive（mode: lite \\| full）
**示例**：`"propose change to add dark mode"`、`"apply v8.3.0-pv09"`、`"archive add-auth-bug"`

## 快速参考表

| 类型 | 触发关键词 | 阶段数 | 门控配置 |
|------|-----------|--------|---------|
| `research-only` | 调研, 比较, 评估 | 3 | — |
| `design-only` | 设计, 架构, API | 3 | standard |
| `hotfix` | 修复, bug, 崩溃 | 4 | relaxed |
| `refactoring` | 重构, 清理, 技术债 | 5 | standard |
| `migration` | 迁移, 升级, 转换 | 5 | standard |
| `spike-poc` | 原型, 实验, PoC | 3 | — |
| `documentation` | 写文档, README | 3 | relaxed |
| `security-audit` | 安全, 审计, CVE | 5 | strict |
| `feature-enhancement` | 添加, 扩展, 增强 | 7 | standard |
| `full-pipeline` | 从零开始, 新项目 | 8 | standard |
| `RDRR` | 带调研的设计, ADR | 4 (循环) | standard |
| `demo-showcase` | 演示, 展示, 演讲 | 6 | relaxed |
| `performance-optimization` | 慢, 优化, 基准测试 | 5 | standard |
| `dependency-setup` | 搭建, 安装, 配置环境 | 4 | relaxed |
| `onboarding` | 新加入项目, 入门 | 4 | — |
| `skill-optimization` | 优化技能, 基准测试上下文 | 6 | convergence |
| `self-update` | 更新引用, 自更新, 检查参考 | 6 | standard |
| `change-driven` | 变更, 提议, 应用, 归档, 生命周期, OpenSpec | 4 | convergence |
"""


def _zh_hierarchy() -> str:
    return """\
## 为什么需要层级？

单个 AI 代理处理复杂任务（如 "构建认证系统"）面临两个问题：
1. **上下文溢出** — 它试图同时记住所有内容
2. **范围蔓延** — 它在设计、实现和审查之间无序切换

DevolaFlow 通过 4 层架构解决这个问题，每层都有严格的上下文预算和明确的角色。

## L0: 项目代理（~3K tokens）

项目代理是 **乐团指挥**。它：
- 接收用户请求，选择工作流类型
- 按顺序排列阶段并逐一分派
- 评估质量门结果：推进、重试或升级
- 向用户报告最终状态

**绝不会**：读源代码、写文件、运行测试、审查代码。

## L1: 阶段代理（~5K tokens）

每个阶段代理拥有工作流中的 **一个阶段**。它：
- 接收阶段定义和前驱摘要
- 将阶段分解为批次（并行任务组）
- 在审查/测试发现问题时运行收敛循环
- 评估阶段的质量门

**约束**：每阶段最多 7 个批次。质量门评估是推进前的强制步骤。

## L2: 批次代理（~4K tokens）

批次代理在一个批次内分派 **并行任务**。它：
- 为任务代理分配不相交的文件所有权
- 收集结果并检查跨任务冲突
- 向阶段代理报告批次完成状态

**约束**：每批次最多 5 个任务。并行任务的文件所有权不得重叠。

## L3: 任务代理（~8K tokens）

任务代理是 **唯一执行实际工作的层级**。它：
- 接收一个原子任务，有明确的验收标准
- 只在其所拥有的文件范围内工作（最多 6 个可写文件）
- 产出制品（代码、测试、文档、报告）
- 报告完成状态（测试通过数、覆盖率、发现的问题）

**约束**：实现类最长 30 分钟，调研类最长 45 分钟。不能派生子代理。

## 升级链

```
任务代理 → 批次代理 → 阶段代理 → 项目代理 → 人工
```

升级始终 **向上** 移动，绝不跳级。每个失败都有分类：

| 严重度 | 动作 |
|--------|------|
| `AUTO_RECOVER` | 重试最多 3 次，指数退避 |
| `PAUSE` | 暂停任务，排队提问，继续并行工作 |
| `HUMAN_INTERVENE` | 停止阶段，向人工展示选项 |
| `FULL_ROLLBACK` | 回滚到检查点，终止所有工作 |

## 通信协议

所有层间通信使用 **类型化 YAML 消息**（非自由文本）：

- **TaskDispatch**：task_id、type、title、description、owned_files、acceptance_criteria、timeout
- **StatusReport**：task_id、state、progress_pct、artifacts、metrics
- **ExceptionEscalation**：severity、context、options

## 示例：热修复追踪

```
用户："修复登录超时 bug"
  └─ 项目代理：选择 hotfix 工作流
       └─ 阶段代理（分诊）：分派 1 个批次
            └─ 批次代理：分派 1 个任务
                 └─ 任务代理：分析 bug，定位根因
       └─ 阶段代理（修复）：分派 1 个批次
            └─ 批次代理：分派 1 个任务
                 └─ 任务代理：实现最小修复（修改 3 个文件）
       └─ 阶段代理（测试）：分派 1 个批次
            └─ 批次代理：分派 1 个任务
                 └─ 任务代理：运行聚焦测试（42 通过，0 失败）
       └─ 阶段代理（发布）：分派 1 个批次
            └─ 任务代理：标记 v1.2.1，更新 changelog
  └─ 项目代理：向用户报告 SUCCESS
```
"""


def _zh_faq() -> str:
    return """\
## 常规问题

### 什么是 DevolaFlow？

一个用于 AI 辅助软件开发的可组合工作流元框架。它通过声明式 YAML 模板定义多阶段交付流水线，由 4 层代理层级和质量门机制进行编排。可以把它理解为一个你的 AI 编程工具会自动遵循的项目管理框架。

### 支持哪些 AI 工具？

- **Cursor** — 作为 Cursor Skill 加载
- **Claude Code** — 作为 `CLAUDE.md` 加载（每个会话自动生效）
- **GitHub Copilot** — 作为 `copilot-instructions.md` 加载
- **OpenAI Codex** — 作为 Codex Skill 加载

### 我需要学 YAML 才能使用 DevolaFlow 吗？

不需要。DevolaFlow 根据你的自然语言提示词自动激活。说 "修复登录 bug" 它就选择 hotfix 工作流，说 "从零构建新功能" 它就选择 full-pipeline。只有创建自定义工作流模板时才需要 YAML。

### DevolaFlow 和直接提示 AI 工具有什么区别？

没有 DevolaFlow 时，AI 工具在单轮中处理整个请求，经常丢失上下文或混淆关注点（一边设计一边编码一边测试）。有了 DevolaFlow，工作被分解为隔离的阶段并带有质量检查点，代理先设计，再规划，再实现，再审查 — 每个边界都有质量门确保质量。

## 工作流

### Agent 如何选择工作流？

DevolaFlow 使用提示词的 **意图匹配**：
- "修复 bug" / "崩溃" → `hotfix`
- "从零开始" / "新项目" → `full-pipeline`
- "调研" / "对比" → `research-only`
- "重构" / "清理" → `refactoring`

你也可以显式指定："使用 migration 工作流从 React 17 升级到 18。"

### v3.0.0+ 的 5 种新工作流是什么？

- **demo-showcase**：构建展示级演示和交互式展示
- **performance-optimization**：基于分析的性能优化，包含前后对比基准测试
- **dependency-setup**：配置开发环境，安装依赖，设置工具链
- **onboarding**：帮助新贡献者了解代码库并设置环境
- **skill-optimization**：优化 Agent 技能，包括上下文分析、基准测试和迭代改进

## 质量与门控

### 什么是仓库规则？

`.cursor/rules/` 中的 18 条规则，分为 3 个文件：
- **skill-format-rules.mdc** (SF-1 至 SF-6)：SKILL.md 格式约束
- **change-process-rules.mdc** (CP-1 至 CP-7)：测试覆盖率底线（≥80%）
- **context-optimization-rules.mdc** (CO-1 至 CO-6)：精简消息和基准测试

### 什么是 EvoBench？

内置的上下文密度基准测试套件。运行：`python -m benchmarks.devolaflow_context.runner --scenario all`

### 质量门失败时会发生什么？

门控触发 **收敛循环**：审查发现 → 修复问题 → 重新测试 → 复查门控。最多 3 轮。如果仍然失败，升级到人工并附上差异报告。

## 更新与版本

### 如何检查更新？

在 AI 工具中输入 `"update devola"` — 或在终端运行 `devola-version`。

### 如何更新？

```bash
# pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# 安装器
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```
"""


def _zh_integration() -> str:
    return """\
## 支持的平台

| 平台 | 安装方式 | Skill 格式 | 范围 |
|------|---------|-----------|------|
| **Cursor** | `devola-init cursor` | SKILL.md + references/ + examples/ | 项目或全局 |
| **Claude Code** | `devola-init claude` | CLAUDE.md（自包含） | 项目或全局 |
| **Copilot** | `devola-init copilot` | copilot-instructions.md | 仅项目 |
| **Codex** | `devola-init codex` | SKILL.md + openai.yaml | 仅全局 |

## Cursor — 详细设置

### 安装

```bash
# 项目级安装（推荐）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# 或用户全局安装
curl -fsSL $INSTALLER | bash -s cursor --global
```

安装内容：
- `.cursor/skills/devola-flow/SKILL.md` — 主 skill 文件
- `.cursor/skills/devola-flow/references/` — 9 个领域参考文件
- `.cursor/skills/devola-flow/examples/` — 3 个执行追踪示例

### 在 Cursor 中如何工作

DevolaFlow 作为 **Cursor Skill** 加载。当你在 Agent 模式中发送提示词时，Cursor 将 skill 内容加载到代理上下文中。DevolaFlow 的工作流选择启发式规则根据你的意图关键词激活。

### 示例会话：构建功能

1. 在项目中打开 Cursor
2. 切换到 **Agent 模式**（Cmd+L / Ctrl+L）
3. 输入请求：

```
实现用户管理 REST API，包含 CRUD 操作、JWT 认证和基于角色的访问控制
```

4. DevolaFlow 激活，Agent 将：
   - 选择 `full-pipeline` 工作流
   - **设计阶段**：定义 API 端点、数据模型、认证流程
   - **规划阶段**：分解为批次 — 认证模块（批次 1）、CRUD 端点（批次 2）、RBAC（批次 3）
   - **实现阶段**：通过并行任务代理创建源文件和测试
   - **审查阶段**：检查代码质量、安全性、风格
   - **测试阶段**：运行单元 + 集成测试，测量覆盖率
   - **质量门**：验证复合评分 ≥ 85、覆盖率 ≥ 80%
   - **发布阶段**：更新 changelog，准备提交

### Cursor 使用技巧

- **手动附加 skill**：输入 `@devola-flow` 显式引用
- **使用 Plan 模式**：Agent 会生成结构化计划而不执行
- **子代理支持**：Cursor 的 Task 工具自然映射到 DevolaFlow 的 Wave→Task 委托

## Claude Code — 详细设置

### 安装

```bash
# 项目级
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# 用户全局
curl -fsSL $INSTALLER | bash -s claude --global
```

安装一个自包含的 `CLAUDE.md` 文件。Claude Code 在每个会话开始时自动读取。

### 在 Claude Code 中如何工作

`CLAUDE.md` 始终生效 — Claude Code 自动加载。每个提示词都受益于 DevolaFlow 的工作流结构。

### 示例会话

```bash
claude

> 为数据库查询实现缓存层，支持 TTL 和缓存失效
```

Claude Code 将：
1. 检测 `full-pipeline` 意图
2. 使用 `Task` 子代理进行并行实现
3. 遵循收敛循环确保质量
4. 最后报告任务质量评分

## GitHub Copilot — 详细设置

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

安装内容：
- `.github/copilot-instructions.md` — 根指令
- `.github/instructions/workflow.instructions.md` — 工作流指令

### 在 Copilot 中如何工作

Copilot 为每个请求读取 `copilot-instructions.md`。工作流启发式规则引导 Copilot 的代码建议和聊天回复遵循结构化模式。

## OpenAI Codex — 详细设置

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

安装内容：
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/agents/openai.yaml`

## CI/CD 集成

在 CI 管线中添加 DevolaFlow 验证：

```yaml
# .github/workflows/ci.yml
- name: DevolaFlow Checks
  run: |
    pip install -e '.[dev]'
    python -m pytest tests/ --cov=devolaflow -q
    ruff check src/ tests/ benchmarks/
    validate-template --all
    build-skill --all
```
"""


def _zh_customization() -> str:
    return """\
## 创建自定义工作流模板

工作流模板是 `workflow-system/agent/templates/builtin/` 中的 YAML 文件。每个模板遵循 `schemas/workflow-template.schema.yaml` 中定义的架构。

### 模板结构

```yaml
schema_version: "1.0"

metadata:
  name: my-workflow          # 唯一的 kebab-case id
  version: "1.0.0"
  display_name: "我的工作流"
  description: "这个工作流的用途"
  category: build            # discover | shape | build | deliver | composite
  applicable_scenarios:
    - "何时推荐这个工作流"
  tags: [关键词1, 关键词2]

stages:
  - id: stage_id
    primitive: implement     # 13 个原语之一
    alias: friendly-name     # 可选显示名
    description: "这个阶段的用途"
    team: implement          # research | design | implement | test | review
    duration_class: medium   # quick | medium | long
    config:
      test_strategy: tdd

composition:
  compose: sequence
  stages:
    - stage: stage_id
    - compose: loop
      ref: my_loop

loops:
  - name: my_loop
    body_stages: [stage_a, stage_b]
    until: "stage_b.pass_rate == 1.0"
    max_iterations: 3
    on_exhaustion: escalate

gates: []

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

### 示例：自定义 "仅代码审查" 模板

```yaml
schema_version: "1.0"

metadata:
  name: code-review
  version: "1.0.0"
  display_name: "仅代码审查"
  description: "独立的代码审查，不包含实现。"
  category: verify
  applicable_scenarios:
    - "审查 PR 或代码提交"
  tags: [review, quality, check]

stages:
  - id: review
    primitive: review
    description: "审查代码的质量、安全性和风格"
    team: review
    duration_class: medium
    config:
      review_type: code
      pass_threshold: 0.80

composition:
  compose: sequence
  stages:
    - stage: review

loops: []
gates: []

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

## 自定义上下文配置

编辑 `workflow-system/agent/context_profiles.yaml` 添加新任务类型的配置。每个配置指定 SKILL.md 段落的优先级：

- **critical**：始终包含，优先加载
- **important**：预算允许时包含
- **supplementary**：仅剩余空间时包含
- **skip**：对此任务类型永不包含

## 验证更改

自定义后，务必验证：

```bash
validate-template --all                # 模板有效
python -m pytest tests/ -q             # 所有测试通过
python -m benchmarks.devolaflow_context.runner --scenario all  # 无回退
build-skill --all                      # 适配器构建成功
```
"""


def _zh_troubleshooting() -> str:
    return """\
## 安装问题

### `devola-init` 命令未找到

CLI 工具需要 pip 安装：
```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
# 或开发版：
pip install -e ".[dev]"
```

### 安装器报 "权限拒绝"

安装器需要对目标目录的写入权限。全局安装写入 `~/.cursor/skills/`，应该是用户可写的。

## 工作流问题

### Agent 没有选择正确的工作流

DevolaFlow 使用关键词匹配。让你的意图更明确：
- 不要说："帮我处理登录页面"
- 改为说："修复登录页面的 bug"（→ hotfix）或 "重新设计登录页面 UI"（→ design-only）

也可以直接指定："使用 refactoring 工作流清理认证模块。"

### Agent 试图一次完成所有事情

通常意味着 skill 文件未加载。检查：
1. 确认 skill 文件存在：`ls .cursor/skills/devola-flow/SKILL.md`
2. 在 Cursor 设置中确认 skill 可见
3. 尝试显式附加：`@devola-flow 实现用户系统`

### 收敛循环运行太多次

默认最大 3 次迭代。如果持续循环：
1. 检查验收标准是否过于严格
2. 查找阻止收敛的冲突需求
3. 达到最大迭代后 Agent 会升级到你 — 查看差异报告

## 测试与构建问题

### 修改 SKILL.md 后测试失败

运行 `python -m pytest tests/test_version.py -v` 检查版本一致性。使用 `scripts/bump_version.py` 进行统一更新。

### `build-skill` 报告超出预算

SKILL.md 必须保持在 500 行以内（规则 SF-1）。运行 `build-skill --all` 验证。

### 模板验证失败

```bash
validate-template path/to/template.yaml
```

常见原因：
- 缺少必需字段（`schema_version`、`metadata`、`stages`、`composition`）
- `composition` 中的阶段引用与 `stages[].id` 不匹配
- 循环引用与 `loops[].name` 不匹配
- 无效的原语名称（必须是 13 个原语之一）

## 基准测试问题

### EvoBench 显示回退

```bash
python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline
```

如果某个场景回退：
1. 检查近期对 `context_profiles.yaml` 或 SKILL.md 段落边界的更改
2. 审查特定场景的预期 vs 实际段落选择
3. 修复后更新基线：`python -m benchmarks.devolaflow_context.runner --generate-baseline`

## 获取帮助

- **GitHub Issues**: [https://github.com/YoRHa-Agents/DevolaFlow/issues](https://github.com/YoRHa-Agents/DevolaFlow/issues)
- **交互式演示**: [https://yorha-agents.github.io/DevolaFlow/](https://yorha-agents.github.io/DevolaFlow/)
"""


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    human_dir = root / "workflow-system" / "human"

    do_en = (
        "--all" in sys.argv
        or "--lang" not in sys.argv
        or ("--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "en")
    )
    do_zh = "--all" in sys.argv or (
        "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "zh"
    )

    # Humanize is ON by default per Q-B (in-pipeline humanization).
    # `--no-humanize` opts out (useful for drift-lint diffs that want
    # to inspect raw generator output).
    humanize = "--no-humanize" not in sys.argv

    count = 0
    for slug, en_title, en_desc, zh_title, zh_desc in DOCS:
        if do_en:
            _gen_doc(slug, en_title, en_desc, "en", human_dir / "en", humanize=humanize)
            count += 1
        if do_zh:
            _gen_doc(slug, zh_title, zh_desc, "zh", human_dir / "zh", humanize=humanize)
            count += 1

    suffix = "" if humanize else " (no-humanize)"
    print(f"Generated {count} human doc files{suffix}.")


if __name__ == "__main__":
    main()
