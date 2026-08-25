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
        "Three-layer checklist-round architecture, provenance primitives, and quality gates.",
        "架构概述",
        "三层清单轮次架构、来源原语与质量门机制。",
    ),
    (
        "workflow-types",
        "Checklist Seed Catalog",
        "23 built-in checklist seeds plus the change-driven runtime.",
        "清单种子目录",
        "23 个内置清单种子与 change-driven 运行时。",
    ),
    (
        "agent-hierarchy-guide",
        "Agent Hierarchy Guide",
        "Understanding the three-layer Project, Wave, and Task hierarchy.",
        "Agent 层级指南",
        "理解 Project、Wave、Task 三层委托架构。",
    ),
    (
        "customization-guide",
        "Customization Guide",
        "Creating non-executable checklist seeds and derived configurations.",
        "自定义指南",
        "创建不可执行的清单种子与派生配置。",
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
SOURCE_VERSION = "17.0.0"


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

**Option A — npm / npx (recommended; works on Windows, no Python needed):**

```bash
# Install into the user-level skill directory (Node >= 18)
npx @yorha-agents/devola-flow install cursor    # ~/.cursor/skills/devola-flow/
npx @yorha-agents/devola-flow install claude    # ~/.claude/skills/devola-flow/
npx @yorha-agents/devola-flow install all       # both

# Later: health check and update
npx @yorha-agents/devola-flow doctor
npx @yorha-agents/devola-flow update all
```

Skill files are downloaded from GitHub at the tag matching the package version
(`DEVOLA_FLOW_REF` overrides the ref). Targets: Cursor and Claude Code,
user-level directories only — for project-local, Copilot, or Codex installs
use Option B.

**Option B — One-liner (curl; all tools, project-local or global):**

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

# Install for Cursor (project-local)
curl -fsSL $INSTALLER | bash -s cursor

# Or install for all tools at once
curl -fsSL $INSTALLER | bash -s all
```

**Option C — pip install:**

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project/
devola-init cursor       # Cursor only
devola-init all          # all tools
```

**Option D — Manual (single file):**

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

### Example: Quick Research (No Code)

```
Research the best approach for real-time notifications — compare WebSocket vs SSE vs polling
```

What happens:
1. DevolaFlow selects the **research-only checklist seed**
2. The materialized checklist asks for a structured, evidenced comparison — no code written

## Step 4: Explore More

- See all 23 checklist seeds: [Checklist Seed Catalog](workflow-types.md)
- Understand the architecture: [Architecture Overview](architecture-overview.md)
- Set up for your specific tool: [Integration Guide](integration-guide.md)
- Customize workflows: [Customization Guide](customization-guide.md)

## Checking for Updates

Ask your AI agent: `"update devola"` — it checks GitHub for newer versions and provides the exact update command.

Or from the terminal:

```bash
# npm installer update (user-level Cursor/Claude installs)
npx @yorha-agents/devola-flow update all

# Installer update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip update
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
"""


def _en_architecture() -> str:
    return """\
## System Overview

DevolaFlow orchestrates complex software work through **checklist rounds** and a **three-layer agent hierarchy**. A user-approved checklist is the execution contract: every item is measurable, every completion has evidence, and every loop is bounded.

```
User Request
    │
    ▼
┌─────────────────────┐
│  Checklist Seed      │  Select domain decomposition knowledge
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L0: Project Agent   │  Anchor checklist, manage rounds     (~5K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L1: Wave Agent      │  Dispatch tasks, aggregate evidence  (~5K tok)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L2: Task Agent      │  **Execute actual work**              (~8K tok)
└─────────────────────┘
```

**Key invariant**: Only L2 Task Agents perform actual work — writing code, running tests, reviewing, or authoring documents. L0 Project and L1 Wave agents only dispatch, monitor, verify evidence, and report.

## The Three-Layer Hierarchy

| Layer | Role | Context Budget | Delegates To | Must NOT |
|-------|------|---------------|-------------|----------|
| **L0: Project** | Anchors goal/checklist/preflight, picks each round, evaluates evidence and gates | ~5K tokens | L1 Wave | Implement or alter Task output |
| **L1: Wave** | Dispatches parallel Tasks, checks ownership conflicts, aggregates evidence proposals | ~5K tokens | L2 Task | Perform any Task's work |
| **L2: Task** | Executes one atomic checklist assignment and reports evidence | ~8K tokens | Nothing (leaf) | Spawn sub-agents or write outside its owned set |

The escalation chain is always upward: **Task → Wave → Project → Human**.

## Checklist-Round Runtime

`change-driven` is the sole executable runtime:

1. **Propose**: L0 and the user anchor numbered goals and a measurable checklist.
2. **Preflight**: The user signs project decisions and blocker pre-authorizations once.
3. **Round**: L0 picks the highest-priority open items, partitions them into waves, and records the plan in `stage.md`.
4. **Execute**: L1 dispatches up to five isolated L2 Tasks per wave.
5. **Verify**: Tasks report evidence; L1 aggregates it; L0 verifies it before checking any item.
6. **Repeat or archive**: A round passes when its picked items are checked with evidence and no blockers remain. Once the full checklist and archive gate pass, the change can be archived.

Composite gate scores remain a trend signal during rounds. They do not replace the primary contract: checked assertions with valid evidence and zero blockers.

## 23 Checklist Seeds and Primitive Provenance

The registry contains **23 non-executable checklist seeds** plus the one `change-driven` runtime. A seed supplies intent keywords, checklist partitions, measurable assertion templates, and verification suggestions. It never supplies a runtime DAG.

Each seed's `source_stages` field is **provenance only**. It preserves the historical source ID and one of 14 primitive labels; list order is presentation-only and must not determine execution order:

| Category | Primitives | Purpose |
|----------|-----------|---------|
| **Discover** | `research`, `analyze` | Gather information, assess current state |
| **Shape** | `design`, `plan` | Define architecture, decompose into tasks |
| **Build** | `implement`, `refine` | Write code, fix issues |
| **Verify** | `review`, `test`, `validate`, `verify` | Check quality, run tests, aggregate results |
| **Deliver** | `release`, `deploy`, `monitor` | Package, ship, observe |
| **Control** | `gate` | Quality checkpoint blocking progression |

## Task-Adaptive Context Selection

Each task type has a **context profile** that selects only relevant SKILL.md sections, keeping the context window lean:

- A **hotfix** agent receives: triage procedures, fix guidelines, test requirements — but skips design primitives
- A **research** agent receives: research methodology, comparison frameworks — but skips convergence loops
- A **design** agent receives: architecture patterns, ADR templates — but skips release procedures

Profiles are defined in `workflow-system/agent/context_profiles.yaml`.

## Quality Gate Mechanism

Gates are quality checkpoints at round and archive boundaries. Every gate can evaluate a **composite score**:

```
composite = test_quality × 0.30 + code_review × 0.30
          + architecture × 0.20 + benchmark × 0.20
```

**Pass conditions** (all required):
1. Every checklist item picked for the round has valid evidence and is checked
2. Zero blocker findings and zero MUST-priority violations
3. Archive additionally satisfies its configured composite and coverage thresholds

**On failure**: Open items and findings enter the next bounded round as reinforcement. If progress stagnates or the round limit is reached, escalation follows Task → Wave → Project → Human.

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
- **Task spec**: checklist item IDs, assertions, verification criteria
- **Context**: predecessor summaries, design excerpts, interface contracts
- **Files**: owned files (create/modify) + read-only references
- **Rules**: coding conventions, quality focus areas
- **Behavioral**: timeout, max files, escalation policy

**Never leaked between tasks**: conversation history, file contents from sibling tasks, error details from parallel work, quality scores from unrelated tasks.

## Human Interaction Surface

Alongside the agent-only `.local/.agent/` workspace, DevolaFlow maintains a durable **`.local/human/`** surface (v14.0.0+). Its three zones separate **immutable INPUT** (what humans want) from **concise OUTPUT** (what agents report back):

| Zone | Ownership and contents |
|------|------------------------|
| **`input/`** | Human-owned and immutable once ratified: constitution, REQ-ID-keyed requirements, and an append-only amendment ledger |
| **`output/`** | Agent-written and concise: `DIGEST.md` plus convergence reports |
| **`archive/`** | Superseded artifacts |

Per-artifact TOKEN budgets keep each file lean. Verify with `python -c "from devolaflow.agent_workspace import lint_human; print(lint_human())"`.

## Repository Rules

62 enforceable rules codifying iteration lessons live in `.rules/` (5 layered
source files), compiled to `AGENTS.md` and `.cursor/rules/repo-governance.mdc`:

| Rule Layer | Covers |
|-----------|--------|
| `soul.mdc` (S-1 to S-10, P0) | Immutable invariants — test coverage floor (≥80%), no ghost features, no silent failures, protected branches |
| `architecture.mdc` (A-1 to A-7, P1) | Three-layer agent hierarchy, cache-layout governance, token budgets, SSOT registries |
| `conventions.mdc` (C-1 to C-9, P2; C-8 retired) | Line budgets, frontmatter, version consistency, lean messages, verbatim extraction |
| `workflow.mdc` (W-1 to W-24, P3) | Iteration planning, benchmark guards, version bump protocol, env-flag policy |
| `style.mdc` (ST-1 to ST-13, P4) | Documentation sync, web experience, bilingual completeness |

The pre-v14.2.1 standalone files (`skill-format-rules.mdc`,
`change-process-rules.mdc`, `context-optimization-rules.mdc`, …) were demoted
to deprecated pointer stubs and retired in v15.0.0 — their SF-/CP-/CO- content
was absorbed into the layers above.
"""


def _en_workflow_types() -> str:
    return """\
## Seed Selection

DevolaFlow matches prompt intent to a checklist seed. You can also name a seed explicitly. The selected seed is materialized into user-confirmed goals and measurable checklist assertions before execution.

| Signal | Selected seed |
|--------|---------------|
| "urgent", "ASAP", "production down" | `hotfix` |
| "from scratch", "new project" | `full-pipeline` |
| Question-form phrasing such as "what", "how", "which" | `research-only` |
| Explicit seed name | Direct match |

## The 23 Built-in Checklist Seeds

All 23 seeds are **non-executable decomposition knowledge**. The primitive lists below are source provenance only: they explain where each seed's domain knowledge came from, but neither list order nor source IDs prescribe runtime order.

| Seed | Use when | Primitive provenance (non-executable) |
|------|----------|---------------------------------------|
| `hotfix` | Urgent defect diagnosis and bounded remediation | analyze, implement, test, release |
| `research-only` | Compare alternatives and produce an evidenced recommendation | research, analyze, validate |
| `design-only` | Create an architecture, API, or schema with review evidence | research, design, review |
| `documentation-only` | Survey, author, and review documentation | research, implement, review |
| `spike-poc` | Test feasibility with a bounded throwaway prototype | research, implement, validate |
| `refactoring` | Restructure code while preserving behavior | analyze, plan, implement, test, review |
| `feature-enhancement` | Extend an existing feature through release evidence | design, plan, implement, review, test, release |
| `full-pipeline` | Build a greenfield or end-to-end capability | design, plan, implement, review, test, refine, gate, release |
| `performance-optimization` | Improve a measured latency, memory, or throughput problem | analyze, design, implement, test, validate |
| `security-audit` | Threat-model, scan, remediate, and verify security | research, analyze, implement, validate |
| `research-design-review-refine` | Iterate on research-backed design | research, design, review, refine |
| `dependency-setup` | Configure an environment, dependency, or toolchain | research, plan, implement, verify |
| `onboarding` | Help a contributor understand and verify a repository setup | analyze, implement, verify |
| `demo-showcase` | Build a presentation-ready demonstration | research, design, implement, review, refine, release |
| `product-verification` | Verify visual, interaction, accessibility, and acceptance quality | analyze, design, implement, test, verify, review, validate |
| `entropy-cleanup` | Find and repair stale documentation or drift | analyze, plan, review, implement |
| `migration` | Upgrade or port a system with rollback readiness | analyze, plan, implement, validate, deploy |
| `skill-optimization` | Profile and improve an agent skill | research, analyze, implement, test, refine |
| `self-update` | Research and integrate reference updates | research, plan, implement, test, validate |
| `nines-assisted` | Apply built-in harness-backed evaluation knowledge | research, design, plan, implement, review, test, refine, validate, release |
| `repo-init` | Initialize repository workspace and governance surfaces | analyze, implement, validate |
| `change-driven` | Materialize an evidence-backed change lifecycle checklist | design, implement, verify, deploy |
| `web-design` | Design, refine, and deterministically verify a frontend | design, implement, refine, verify |

## How a Seed Becomes Work

1. Intent matching selects one seed.
2. L0 renders its partitions and assertion templates into `goal.md` and `checklist.md`.
3. The user confirms wording, P0/P1/P2 priorities, manual checks, and preflight decisions.
4. The `change-driven` runtime executes the confirmed checklist in bounded rounds.

Suggested priorities are advisory. A seed contains no checkboxes, evidence, round state, or runtime dependency state; those belong to the materialized change workspace.

## The Sole Executable Runtime

`change-driven` is the only executable template. Its lifecycle is:

```
propose → preflight → bounded checklist rounds → archive
```

During each round, L0 picks open items, L1 Wave dispatches isolated L2 Tasks, Tasks report evidence, and L0 checks only verified assertions. The same runtime serves all 23 seeds.

## Example Prompts

- `hotfix`: `"Fix the login timeout bug; users get 500 errors after 30 seconds"`
- `security-audit`: `"Audit the authentication module against OWASP Top 10"`
- `research-design-review-refine`: `"Research caching options, design one, and refine it after review"`
- `product-verification`: `"Verify the checkout flow visually and against accessibility requirements"`
- `repo-init`: `"Initialize this repository for DevolaFlow"`
- `web-design`: `"Build and polish a non-generic pricing page"`
"""


def _en_hierarchy() -> str:
    return """\
## Why a Hierarchy?

A single AI agent attempting a complex task (e.g., "build an auth system") faces two problems:
1. **Context overflow** — it tries to hold everything in memory at once
2. **Scope creep** — it drifts between design, implementation, and review without structure

DevolaFlow uses three layers to constrain context drift while keeping the dispatch chain short.

## L0: Project Agent (~5K tokens)

The Project Agent is the **orchestra conductor**. It selects a checklist seed and anchors `goal.md`, `checklist.md`, and `preflight.md` with the user. It also:
- Picks P0/P1/P2 items for each bounded round and partitions them into waves
- Verifies Task evidence before checking assertions
- Evaluates round and archive gates, then decides: advance, retry, or escalate
- Reports final status to the human

**Never does**: Implement, run tests, author deliverables, or modify Task output.

## L1: Wave Agent (~5K tokens)

A Wave Agent coordinates a bounded group of parallel Tasks. It:
- Receives checklist item IDs, verbatim assertions, verification rules, and file ownership
- Dispatches up to five L2 Tasks with disjoint writable files
- Collects StatusReports and checks for cross-task conflicts
- Aggregates evidence and submits a concise check proposal to L0

**Never does**: Perform any Task's work or modify its output.

## L2: Task Agent (~8K tokens)

The Task Agent is the **only implementation layer**. It:
- Receives one atomic assignment tied to checklist item IDs
- Works within its owned files only
- Self-verifies against the supplied assertions without self-scoring
- Reports artifacts, test results, and verbatim evidence to L1

**Constraints**: It cannot spawn sub-agents or write outside the owned set.

## Checklist-Round Flow

```
L0 picks open checklist assertions and records the round in stage.md
  └─ L1 Wave dispatches isolated L2 Tasks
       ├─ L2 Task executes and reports evidence
       └─ L2 Task executes and reports evidence
  └─ L1 aggregates evidence and proposes checks
L0 verifies evidence, checks passing assertions, and closes or repeats the round
```

`stage.md` is a round-control artifact, not an agent role. In checklist seeds, `source_stages` stores only historical source IDs and primitive provenance; it has no executable ordering semantics.

## Escalation Chain

```
Task Agent → Wave Agent → Project Agent → Human
```

Escalation always moves **upward**, never skips levels. Every failure is classified:

| Severity | Action |
|----------|--------|
| `AUTO_RECOVER` | Retry up to 3× with exponential backoff |
| `PAUSE` | Pause task, queue question, continue parallel work |
| `HUMAN_INTERVENE` | Stop the round, present options to the human |
| `FULL_ROLLBACK` | Rollback to checkpoint, halt everything |

## Communication Protocol

All inter-layer communication uses **typed YAML messages** (not free-form chat):

- **TaskDispatch**: task_id, type, title, description, owned_files, acceptance_criteria, timeout
- **StatusReport**: task_id, state, progress_pct, artifacts, metrics
- **ExceptionEscalation**: severity, context, options for the next layer

## Example: Hotfix Trace

```
Human: "Fix the login timeout bug"
  └─ L0 Project: selects hotfix seed; user confirms checklist and preflight
       └─ Round 1 / L1 Wave
            └─ L2 Task: reproduces defect and reports root-cause evidence
       └─ L0: verifies evidence and checks diagnosis assertion
       └─ Round 2 / L1 Wave
            ├─ L2 Task: implements the minimal fix
            └─ L2 Task: runs focused regression tests
       └─ L1: aggregates evidence; L0 verifies and checks both assertions
  └─ L0 Project: archive gate passes; reports SUCCESS to human
```
"""


def _en_faq() -> str:
    return """\
## General

### What is DevolaFlow?

A composable workflow meta-framework for AI-assisted software development. It turns one of 23 domain checklist seeds into a user-confirmed execution contract, then runs that contract through a three-layer Project → Wave → Task hierarchy and the `change-driven` checklist-round runtime.

### What AI tools does it support?

- **Cursor** — loaded as a Cursor Skill (`.cursor/skills/devola-flow/SKILL.md`)
- **Claude Code** — loaded as a Claude Code Skill (`.claude/skills/devola-flow/SKILL.md`)
- **GitHub Copilot** — loaded as `copilot-instructions.md`
- **OpenAI Codex** — loaded as a Codex Skill

A single source (`workflow-skill.yaml`) is adapted to each tool's format via the `build-skill` pipeline.

### Do I need to learn YAML to use DevolaFlow?

No. DevolaFlow activates automatically from natural language. Say "fix the login bug" and it selects the `hotfix` seed. Say "build a new feature from scratch" and it selects `full-pipeline`. You only need YAML to author custom checklist seeds.

### How does DevolaFlow differ from just prompting my AI tool?

Without DevolaFlow, your AI tool may process the whole request in one pass and mix design, implementation, and verification. DevolaFlow anchors measurable checklist assertions with you, executes a bounded set each round, and checks an item only after evidence is verified.

## Workflows

### How does the agent choose a checklist seed?

DevolaFlow uses **intent matching** on your prompt keywords:
- "fix bug" / "broken" / "crash" → `hotfix`
- "from scratch" / "new project" → `full-pipeline`
- "research" / "compare" → `research-only`
- "refactor" / "clean up" → `refactoring`
- And so on for all 23 seeds

You can also specify one explicitly: "Use the migration seed to upgrade from React 17 to 18."

### Can I reduce the ceremony?

Yes, in two ways:
1. **Complexity scaling**: A trivial task (< 20 lines, single file) can use the direct-execution waiver
2. **Seed materialization**: Only relevant assertions are materialized; provenance primitives never force unnecessary runtime work

### Which seeds came from the five v3.0.0 workflow additions?

Historically, v3.0.0 introduced these as executable workflow types. They now preserve that domain knowledge as non-executable checklist seeds:

- **demo-showcase**: Build presentation-ready demos and interactive showcases
- **performance-optimization**: Profile-driven performance improvement with before/after benchmarks
- **dependency-setup**: Configure dev environments, install dependencies, set up tooling
- **onboarding**: Help new contributors understand a codebase and set up their environment
- **skill-optimization**: Optimize agent skills with context profiling, benchmarking, and iterative improvement

## Quality & Gates

### What are the repository rules?

62 enforceable rules in `.rules/` organized into 5 layers, compiled to
`AGENTS.md` + `.cursor/rules/repo-governance.mdc` (the legacy SF-/CP-/CO- rule
files are deprecated pointer stubs since v14.2.1):
- **soul.mdc** (S-1 to S-10): immutable invariants — test coverage floor (≥80%), no ghost features
- **architecture.mdc** (A-1 to A-7): three-layer hierarchy, cache layout, token budgets
- **conventions.mdc** (C-1 to C-9, C-8 retired): SKILL.md line budget, frontmatter, version consistency
- **workflow.mdc** (W-1 to W-24): iteration planning, benchmarks, version bump protocol
- **style.mdc** (ST-1 to ST-13): documentation sync, web demo, bilingual completeness

### How does built-in evaluation work?

The built-in harness validates deterministic fixtures, dispatch constraints,
telemetry aggregation, and bounded model-compliance probes.

Run its contract suite with: `python -m pytest tests/harness/ -v`

### What happens when a gate fails?

The gate triggers a **convergence loop**: review findings → fix issues → re-test → re-check gate. This repeats up to 3 rounds. If the gate still fails after max rounds, it escalates to the human with a divergence report explaining what's blocking.

## Updates & Versioning

### How do I check for updates?

Ask your AI agent: `"update devola"` — or run `devola-version` in the terminal.
To audit every installed copy at once, run `devola-init-doctor --skills`: it
scans all known install locations and reports each install as `current`,
`stale`, or `unknown-version`.

### How do I update?

```bash
# npm (user-level Cursor/Claude installs; also: doctor for a health check)
npx @yorha-agents/devola-flow update all

# pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# installer (skips installs already at the latest version; --force re-downloads)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```

### How do I uninstall?

```bash
# preview what would be removed, then remove for real
# (covers npm-installed copies too — same directories)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall --dry-run
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall
```
"""


def _en_integration() -> str:
    return """\
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

# Or user-global via npm (Node >= 18; no curl/bash needed)
npx @yorha-agents/devola-flow install cursor
```

This installs (per the `cursor` profile in `workflow-system/agent/manifest.yaml`):
- `.cursor/skills/devola-flow/SKILL.md` — the main skill file
- `.cursor/skills/devola-flow/references/` — Tier-2 domain reference files
- `.cursor/skills/devola-flow/examples/` — Tier-3 execution trace examples

### How It Works in Cursor

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

- **Attach the skill manually** for complex tasks: Type `@devola-flow` to explicitly reference the skill
- **Use Plan mode** for architectural decisions: The agent will produce a structured plan instead of executing
- **Subagent support**: Cursor's Task tool maps naturally to DevolaFlow's L1 Wave → L2 Task delegation

## Claude Code — Detailed Setup

### Installation

```bash
# Project-local (applies to current directory)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# User-global (applies to all sessions)
curl -fsSL $INSTALLER | bash -s claude --global

# Or user-global via npm (Node >= 18; no curl/bash needed)
npx @yorha-agents/devola-flow install claude
```

This installs the skill package into `.claude/skills/devola-flow/` (project-local) or `~/.claude/skills/devola-flow/` (with `--global`): `SKILL.md` plus the `references/` and `examples/` trees, per the `claude` profile in `workflow-system/agent/manifest.yaml`.

### How It Works in Claude Code

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

### Tips for Claude Code

- References and examples ship alongside SKILL.md — the skill loads them on demand
- Works with Claude Code's native subagent support
- Use `"update devola"` to trigger version checks within a session

## GitHub Copilot — Detailed Setup

### Installation

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

This installs:
- `.github/copilot-instructions.md` — the full SKILL.md content as root instructions

### How It Works in Copilot

Copilot reads `copilot-instructions.md` for every request. The workflow heuristics guide Copilot's code suggestions and chat responses to follow structured patterns.

### Example Session

In Copilot Chat:
```
@workspace Refactor the payment processing module to use the strategy pattern
```

Copilot uses the `refactoring` seed's historical analyze/plan/implement/test/review primitives as provenance, materializes a checklist, and executes it through the shared round runtime.

## OpenAI Codex — Detailed Setup

### Installation

```bash
# Codex uses global skills
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

This installs (per the `codex` profile in `workflow-system/agent/manifest.yaml`):
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/references/`

### How It Works in Codex

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
"""


def _en_customization() -> str:
    return """\
## Creating Checklist Seeds

Checklist seeds are YAML files under `workflow-system/agent/templates/seeds/`. They follow `schemas/checklist-seed.schema.yaml` and preserve domain decomposition knowledge without creating another executable runtime.

The only executable template is `workflow-system/agent/templates/builtin/change-driven.yaml`. A custom seed is materialized into that shared checklist-round runtime.

### Seed Structure

```yaml
schema_version: "1.0"
kind: checklist-seed
metadata:
  name: code-review
  version: "1.0.0"
  description: "Seed for standalone code review evidence."
  category: composite
  intent_keywords: [review, quality, pull-request]
  source:
    kind: composition
    name: code-review
    path: workflow-system/agent/templates/registry.yaml
    schema_version: "3.0"

placeholders:
  review_command:
    description: "Repository-approved bounded review command."
    required: true
    example: "ruff check src/ tests/"

partitions:
  - key: review
    title_template: "Code review"
    source_stages:                 # provenance only; never execution order
      - {id: review, primitive: review}
    assertions:
      - key: findings-resolved
        statement_template: "Every blocker and critical review finding is resolved"
        suggested_priority: P0
        verify:
          mode: metric
          template: "open_blocker_count == 0 and open_critical_count == 0"
      - key: checks-pass
        statement_template: "The approved static review command passes"
        suggested_priority: P1
        verify:
          mode: command
          template: "{{ review_command }}"
```

### What a Seed May Express

- Intent keywords and optional scenarios
- User-facing checklist partitions
- Measurable assertion templates, each no longer than 25 rendered words
- Suggested P0/P1/P2 priorities that the user can change
- Verification by bounded command, metric, or manual user check
- `source_stages` entries containing only historical source IDs and one of 14 primitive labels

### What a Seed Must Not Express

A seed is not a runtime DAG. Top-level `stages`, `composition`, `loops`, and `gates` are forbidden, as are runtime fields such as `team`, `duration_class`, `input_mapping`, and `skip_condition`. Seed order is presentation-only.

Checkboxes, evidence paths, round numbers, checked-by metadata, and runtime dependencies are also absent. They are assigned only when L0 materializes the seed into a user-confirmed change checklist.

## Registering a Seed

Add one registry entry with a `seed:` path and no executable `path:`. The `change-driven` entry is the only one allowed to declare `path: builtin/change-driven.yaml`.

## Custom Context Profiles

Edit `workflow-system/agent/context_profiles.yaml` to add profiles for new task types. Each profile specifies which SKILL.md sections to include at what priority:

- **critical**: Always included, loaded first
- **important**: Included if token budget allows
- **supplementary**: Included only if space remains
- **skip**: Never included for this task type

## Validating Changes

After customizing, always verify:

```bash
validate-template --all                # 23 seeds + one runtime are valid
python -m pytest tests/ -q             # all tests pass
python -m pytest tests/harness/ -v       # harness contracts pass
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

### Seed or runtime validation fails

```bash
validate-template path/to/template.yaml
```

Common causes:
- Missing seed fields (`schema_version`, `kind`, `metadata`, `placeholders`, `partitions`)
- Executable DAG fields such as top-level `stages`, `composition`, `loops`, or `gates` in a seed
- `source_stages` entries that do not preserve an ID plus one of the 14 provenance primitives
- Command or metric verification without a bounded `template`

## Harness Issues

### Harness contracts fail

```bash
python -m pytest tests/harness/ -v
```

1. Check the failing fixture, telemetry, evaluation, or probe contract
2. Review the reported schema, path, or guard mismatch
3. Fix the source contract; archived baselines remain historical evidence

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

**方式 A — npm / npx（推荐；Windows 可用，无需 Python）：**

```bash
# 安装到用户级 skill 目录（需 Node >= 18）
npx @yorha-agents/devola-flow install cursor    # ~/.cursor/skills/devola-flow/
npx @yorha-agents/devola-flow install claude    # ~/.claude/skills/devola-flow/
npx @yorha-agents/devola-flow install all       # 两者

# 之后：健康检查与更新
npx @yorha-agents/devola-flow doctor
npx @yorha-agents/devola-flow update all
```

skill 文件从 GitHub 按包版本对应的 tag 下载（`DEVOLA_FLOW_REF` 可覆写 ref）。
目标仅限 Cursor 与 Claude Code 的用户级目录——项目级安装、Copilot 或 Codex
请使用方式 B。

**方式 B — 一键安装（curl；全部工具，项目级或全局）：**

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

# 为 Cursor 安装（项目级）
curl -fsSL $INSTALLER | bash -s cursor

# 或为所有工具一次性安装
curl -fsSL $INSTALLER | bash -s all
```

**方式 C — pip 安装：**

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project/
devola-init cursor       # 仅 Cursor
devola-init all          # 所有工具
```

**方式 D — 手动安装（单文件）：**

下载 [SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md) 并放置到：

| 工具 | 路径 |
|------|------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `.claude/skills/devola-flow/SKILL.md` |
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
1. DevolaFlow 从“修复”与“bug”匹配 **hotfix 清单种子**
2. L0 与你共同锚定目标、实体化清单和已签署的 preflight
3. L0 选取最高优先级清单项并划分波次
4. L1 Wave 向隔离的 L2 Task 下发诊断、修复和取证工作
5. L0 核验证据并勾选已通过的断言；如有未完成项，再开启一个有界轮次

### 示例：构建新功能（完整流水线）

```
实现一个用户通知系统，支持邮件和应用内消息两种渠道
```

发生了什么：
1. DevolaFlow 选择 **full-pipeline 清单种子**
2. 种子依据历史原语来源实体化可测的设计、实现、审查、测试和发布断言；这些来源不规定执行顺序
3. 你确认清单优先级和 preflight 决策
4. L0 通过 L1 Wave 与隔离的 L2 Task 运行有界清单轮次
5. 每个已勾选项都附带证据，未解决的 blocker 保持未勾选
6. 只有清单合同通过 archive gate 后，源真相才可变更

### 示例：快速调研（无代码）

```
调研实时通知的最佳方案 — 对比 WebSocket、SSE 和轮询
```

发生了什么：
1. DevolaFlow 选择 **research-only 清单种子**
2. 实体化后的清单要求产出有证据的结构化对比报告，不写代码

## 第四步：深入探索

- 查看全部 23 个清单种子：[清单种子目录](workflow-types.md)
- 了解架构：[架构概述](architecture-overview.md)
- 为你的工具进行设置：[集成指南](integration-guide.md)
- 自定义工作流：[自定义指南](customization-guide.md)

## 检查更新

在 AI 工具中输入：`"update devola"` — 它会从 GitHub 检查新版本并提供更新命令。

或在终端中：

```bash
# npm 安装器更新（用户级 Cursor/Claude 安装）
npx @yorha-agents/devola-flow update all

# 安装器更新
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip 更新
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
"""


def _zh_architecture() -> str:
    return """\
## 系统概述

DevolaFlow 通过 **清单轮次** 与 **三层 Agent 架构** 编排复杂软件任务。经用户确认的 checklist 是执行合同：每项都可测、每次完成都有证据、每个循环都有上限。

```
用户请求
    │
    ▼
┌─────────────────────┐
│   清单种子            │  选择领域分解知识
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L0: Project Agent   │  锚定清单，管理轮次      (~5K tokens)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L1: Wave Agent      │  分派任务，聚合证据      (~5K tokens)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L2: Task Agent      │  **执行实际工作**        (~8K tokens)
└─────────────────────┘
```

**关键不变量**：只有 L2 Task Agent 执行实际工作，包括编写代码、运行测试、审查和撰写文档。L0 Project 与 L1 Wave 只负责分派、监控、核验证据和汇报。

## 三层层级

| 层级 | 角色 | 上下文预算 | 委托给 | 不可以 |
|------|------|-----------|--------|--------|
| **L0: Project** | 锚定 goal/checklist/preflight、每轮取项、核验证据与门控 | ~5K tokens | L1 Wave | 实施或修改 Task 产出 |
| **L1: Wave** | 分派并行 Task、检查文件冲突、聚合证据提案 | ~5K tokens | L2 Task | 执行任何 Task 的工作 |
| **L2: Task** | 执行单一原子清单任务并报告证据 | ~8K tokens | 无（叶节点） | 派生子 Agent 或写出 owned set |

升级链始终向上：**Task → Wave → Project → Human**。

## 清单轮次运行时

`change-driven` 是唯一可执行运行时：

1. **Propose**：L0 与用户锚定编号目标和可测清单。
2. **Preflight**：用户一次性签署项目决策与卡点预授权。
3. **Round**：L0 选取最高优先级未完成项，划分波次，并把计划写入 `stage.md`。
4. **Execute**：L1 每波最多向五个隔离的 L2 Task 下发任务。
5. **Verify**：Task 报告证据，L1 聚合，L0 核验后才可勾选。
6. **Repeat or archive**：本轮取项全部有证据地勾选且无 blocker 才通过；完整清单与 archive gate 均通过后才能归档。

轮次中的合成分只用于趋势观测，不能替代主合同：有有效证据的已勾选断言与零 blocker。

## 23 个清单种子与原语来源

注册表包含 **23 个不可执行的清单种子**，外加唯一的 `change-driven` 运行时。种子提供意图关键词、清单分区、可测断言模板和验证建议，不提供运行时 DAG。

种子中的 `source_stages` **只记录来源**。它保留历史来源 ID 与 14 种原语标签之一；列表顺序仅供展示，不决定执行顺序：

| 类别 | 原语 | 用途 |
|------|------|------|
| **发现** | `research`, `analyze` | 收集信息，评估现状 |
| **塑形** | `design`, `plan` | 定义架构，分解为任务 |
| **构建** | `implement`, `refine` | 编写代码，修复问题 |
| **验证** | `review`, `test`, `validate`, `verify` | 检查质量，运行测试 |
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
1. 本轮取出的每个清单项都有有效证据并已勾选
2. 零 blocker 且零 MUST 优先级违规
3. 归档时还须达到配置的合成分与覆盖率阈值

**失败时**：未完成项和发现会作为 reinforcement 进入下一个有界轮次。进度停滞或达到轮次上限时，按 Task → Wave → Project → Human 升级。

## 人类交互界面

除了仅供 Agent 使用的 `.local/.agent/` 工作区之外，DevolaFlow 还维护持久化的 **`.local/human/`** 界面（v14.0.0+）。这个三区目录树将 **不可变的 INPUT**（人类想要什么）与 **简洁的 OUTPUT**（Agent 回报什么）分离：

| 区域 | 所有权与内容 |
|------|--------------|
| **`input/`** | 由人类拥有，一经批准即不可变：constitution、以 REQ-ID 为键的需求，以及只追加的修订账本 |
| **`output/`** | 由 Agent 写入且简洁：`DIGEST.md` 与收敛报告 |
| **`archive/`** | 已被取代的工件 |

每个工件都有 TOKEN 预算以保持精简。可用 `python -c "from devolaflow.agent_workspace import lint_human; print(lint_human())"` 验证。

## 仓库规则

`.rules/` 中的 62 条可执行规则（5 个分层源文件），编译输出到 `AGENTS.md` 与
`.cursor/rules/repo-governance.mdc`：

| 规则层 | 涵盖内容 |
|---------|---------|
| `soul.mdc`（S-1 到 S-10，P0） | 不可违背的红线 — 测试覆盖率底线（≥80%）、无幽灵功能、无静默失败、保护分支 |
| `architecture.mdc`（A-1 到 A-7，P1） | 三层 Agent 体系、缓存布局治理、令牌预算、单一事实源注册表 |
| `conventions.mdc`（C-1 到 C-9，P2；C-8 已退役） | 行数预算、前置元数据、版本一致性、精简消息、逐字提取 |
| `workflow.mdc`（W-1 到 W-24，P3） | 迭代规划、基准守护、版本升级协议、环境变量复用策略 |
| `style.mdc`（ST-1 到 ST-13，P4） | 文档同步、Web 体验、双语完整性 |

v14.2.1 之前的独立规则文件（`skill-format-rules.mdc`、`change-process-rules.mdc`、
`context-optimization-rules.mdc` 等）曾转换为弃用指针存根，并已于 v15.0.0 退役，
其 SF-/CP-/CO- 内容已并入上述各层。
"""


def _zh_workflow_types() -> str:
    return """\
## 种子选择

DevolaFlow 根据提示词意图匹配清单种子，也可以直接指定种子名。执行前，所选种子会实体化为用户确认的目标和可测清单断言。

| 信号 | 选择的种子 |
|------|------------|
| “紧急”“生产环境故障” | `hotfix` |
| “从零开始”“新项目” | `full-pipeline` |
| “什么”“如何”“哪个”等问题形式 | `research-only` |
| 显式指定种子名 | 直接匹配 |

## 23 个内置清单种子

全部 23 个种子都是 **不可执行的分解知识**。下表中的原语列表只记录来源：它说明领域知识从何而来，但列表顺序与来源 ID 都不规定运行时顺序。

| 种子 | 适用场景 | 原语来源（不可执行） |
|------|----------|----------------------|
| `hotfix` | 紧急缺陷诊断与有界修复 | analyze, implement, test, release |
| `research-only` | 对比方案并给出有证据的建议 | research, analyze, validate |
| `design-only` | 产出带审查证据的架构、API 或 Schema | research, design, review |
| `documentation-only` | 调研、编写并审查文档 | research, implement, review |
| `spike-poc` | 通过有界的一次性原型验证可行性 | research, implement, validate |
| `refactoring` | 在保持行为的前提下重构代码 | analyze, plan, implement, test, review |
| `feature-enhancement` | 扩展现有功能并形成发布证据 | design, plan, implement, review, test, release |
| `full-pipeline` | 构建全新或端到端能力 | design, plan, implement, review, test, refine, gate, release |
| `performance-optimization` | 改善已测量的延迟、内存或吞吐问题 | analyze, design, implement, test, validate |
| `security-audit` | 威胁建模、扫描、修复并验证安全性 | research, analyze, implement, validate |
| `research-design-review-refine` | 迭代调研驱动的设计 | research, design, review, refine |
| `dependency-setup` | 配置环境、依赖或工具链 | research, plan, implement, verify |
| `onboarding` | 帮助贡献者理解并验证仓库环境 | analyze, implement, verify |
| `demo-showcase` | 构建展示级演示 | research, design, implement, review, refine, release |
| `product-verification` | 验证视觉、交互、无障碍与验收质量 | analyze, design, implement, test, verify, review, validate |
| `entropy-cleanup` | 发现并修复过期文档或漂移 | analyze, plan, review, implement |
| `migration` | 在具备回滚准备的前提下升级或迁移系统 | analyze, plan, implement, validate, deploy |
| `skill-optimization` | 分析并改进 Agent Skill | research, analyze, implement, test, refine |
| `self-update` | 调研并集成参考资料更新 | research, plan, implement, test, validate |
| `nines-assisted` | 使用内建 harness 支撑的评估知识 | research, design, plan, implement, review, test, refine, validate, release |
| `repo-init` | 初始化仓库工作区与治理面 | analyze, implement, validate |
| `change-driven` | 实体化有证据的变更生命周期清单 | design, implement, verify, deploy |
| `web-design` | 设计、精修并确定性验证前端 | design, implement, refine, verify |

## 种子如何转化为工作

1. 意图匹配选出一个种子。
2. L0 将分区和断言模板渲染为 `goal.md` 与 `checklist.md`。
3. 用户确认措辞、P0/P1/P2 优先级、人工检查项和 preflight 决策。
4. `change-driven` 运行时以有界轮次执行已确认清单。

建议优先级仅供参考。种子不包含 checkbox、证据、轮次状态或运行时依赖；这些信息只属于实体化后的变更工作区。

## 唯一可执行运行时

`change-driven` 是唯一可执行模板，其生命周期为：

```
propose → preflight → 有界清单轮次 → archive
```

每轮由 L0 取项，L1 Wave 向隔离的 L2 Task 分派任务，Task 报告证据，L0 只勾选核验通过的断言。23 个种子共用这一运行时。

## 示例提示词

- `hotfix`：`"修复登录超时 bug；用户 30 秒后收到 500"`
- `security-audit`：`"按 OWASP Top 10 审计认证模块"`
- `research-design-review-refine`：`"先调研缓存方案，再设计并根据审查精修"`
- `product-verification`：`"从视觉和无障碍要求验证结账流程"`
- `repo-init`：`"为这个仓库初始化 DevolaFlow"`
- `web-design`：`"构建并精修一个非通用的价格页"`
"""


def _zh_hierarchy() -> str:
    return """\
## 为什么需要层级？

单个 AI 代理处理复杂任务（如 "构建认证系统"）面临两个问题：
1. **上下文溢出** — 它试图同时记住所有内容
2. **范围蔓延** — 它在设计、实现和审查之间无序切换

DevolaFlow 用三层架构约束上下文漂移，同时缩短分派链。

## L0: Project Agent（~5K tokens）

Project Agent 是 **乐团指挥**。它选择清单种子，并与用户锚定 `goal.md`、`checklist.md`、`preflight.md`。此外，它还会：
- 每个有界轮次按 P0/P1/P2 取项并划分波次
- 核验 Task 证据后才勾选断言
- 评估轮次门与 archive gate：推进、重试或升级
- 向用户报告最终状态

**绝不会**：实施、运行测试、撰写交付物或修改 Task 产出。

## L1: Wave Agent（~5K tokens）

Wave Agent 协调一组有界并行 Task。它：
- 接收清单项 ID、逐字断言、验证规则与文件所有权
- 向最多五个 L2 Task 分派互不重叠的可写文件
- 收集 StatusReport 并检查跨任务冲突
- 聚合证据，向 L0 提交精简的勾选提案

**绝不会**：执行任何 Task 的工作或修改其产出。

## L2: Task Agent（~8K tokens）

Task Agent 是 **唯一实施层**。它：
- 接收一个与清单项 ID 绑定的原子任务
- 只在 owned files 内工作
- 根据所给断言自证，但不自评分
- 向 L1 报告工件、测试结果和逐字证据

**约束**：不得派生子 Agent，不得写出 owned set。

## 清单轮次流

```
L0 取出未完成清单断言，并在 stage.md 记录本轮
  └─ L1 Wave 向隔离的 L2 Task 分派任务
       ├─ L2 Task 执行并报告证据
       └─ L2 Task 执行并报告证据
  └─ L1 聚合证据并提出勾选建议
L0 核验证据、勾选通过项，然后结束或重复本轮
```

`stage.md` 是轮次管控工件，不是 Agent 角色。清单种子中的 `source_stages` 只保留历史来源 ID 与原语来源，不具备可执行顺序语义。

## 升级链

```
Task Agent → Wave Agent → Project Agent → Human
```

升级始终 **向上** 移动，绝不跳级。每个失败都有分类：

| 严重度 | 动作 |
|--------|------|
| `AUTO_RECOVER` | 重试最多 3 次，指数退避 |
| `PAUSE` | 暂停任务，排队提问，继续并行工作 |
| `HUMAN_INTERVENE` | 停止轮次，向人工展示选项 |
| `FULL_ROLLBACK` | 回滚到检查点，终止所有工作 |

## 通信协议

所有层间通信使用 **类型化 YAML 消息**（非自由文本）：

- **TaskDispatch**：task_id、type、title、description、owned_files、acceptance_criteria、timeout
- **StatusReport**：task_id、state、progress_pct、artifacts、metrics
- **ExceptionEscalation**：severity、context、options

## 示例：热修复追踪

```
用户："修复登录超时 bug"
  └─ L0 Project：选择 hotfix 种子；用户确认清单与 preflight
       └─ 第 1 轮 / L1 Wave
            └─ L2 Task：复现缺陷并报告根因证据
       └─ L0：核验证据并勾选诊断断言
       └─ 第 2 轮 / L1 Wave
            ├─ L2 Task：实现最小修复
            └─ L2 Task：运行聚焦回归测试
       └─ L1：聚合证据；L0 核验并勾选两项断言
  └─ L0 Project：archive gate 通过，向用户报告 SUCCESS
```
"""


def _zh_faq() -> str:
    return """\
## 常规问题

### 什么是 DevolaFlow？

一个用于 AI 辅助软件开发的可组合工作流元框架。它把 23 个领域清单种子之一转为用户确认的执行合同，再通过 Project → Wave → Task 三层架构和 `change-driven` 清单轮次运行时执行。

### 支持哪些 AI 工具？

- **Cursor** — 作为 Cursor Skill 加载
- **Claude Code** — 作为 Claude Code Skill 加载（`.claude/skills/devola-flow/SKILL.md`）
- **GitHub Copilot** — 作为 `copilot-instructions.md` 加载
- **OpenAI Codex** — 作为 Codex Skill 加载

### 我需要学 YAML 才能使用 DevolaFlow 吗？

不需要。DevolaFlow 根据自然语言自动激活。说“修复登录 bug”会选择 `hotfix` 种子，说“从零构建新功能”会选择 `full-pipeline`。只有编写自定义清单种子时才需要 YAML。

### DevolaFlow 和直接提示 AI 工具有什么区别？

没有 DevolaFlow 时，AI 工具可能单轮处理整个请求，混淆设计、实现与验证。DevolaFlow 会与你锚定可测清单断言，每轮只执行一个有界集合，并且仅在证据核验后勾选。

## 工作流

### Agent 如何选择清单种子？

DevolaFlow 使用提示词的 **意图匹配**：
- "修复 bug" / "崩溃" → `hotfix`
- "从零开始" / "新项目" → `full-pipeline`
- "调研" / "对比" → `research-only`
- "重构" / "清理" → `refactoring`

你也可以显式指定：“使用 migration 种子从 React 17 升级到 18。”

### 哪些种子来自 v3.0.0 的五个工作流新增项？

从历史来源看，v3.0.0 曾把以下能力作为可执行工作流类型引入。现在它们以不可执行清单种子保留领域知识：

- **demo-showcase**：构建展示级演示和交互式展示
- **performance-optimization**：基于分析的性能优化，包含前后对比基准测试
- **dependency-setup**：配置开发环境，安装依赖，设置工具链
- **onboarding**：帮助新贡献者了解代码库并设置环境
- **skill-optimization**：优化 Agent 技能，包括上下文分析、基准测试和迭代改进

## 质量与门控

### 什么是仓库规则？

`.rules/` 中的 62 条规则，分为 5 层，编译输出到 `AGENTS.md` 与
`.cursor/rules/repo-governance.mdc`（旧的 SF-/CP-/CO- 规则文件自 v14.2.1 起为弃用指针存根）：
- **soul.mdc**（S-1 至 S-10）：不可违背的红线 — 测试覆盖率底线（≥80%）、无幽灵功能
- **architecture.mdc**（A-1 至 A-7）：三层体系、缓存布局、令牌预算
- **conventions.mdc**（C-1 至 C-9，C-8 已退役）：SKILL.md 格式约束、版本一致性
- **workflow.mdc**（W-1 至 W-24）：迭代规划、基准测试、版本升级协议
- **style.mdc**（ST-1 至 ST-13）：文档同步、Web 演示、双语完整性

### 内建评估如何运作？

内置 harness 负责验证确定性 fixture、dispatch 约束、遥测聚合与有界模型合规探测。
运行：`python -m pytest tests/harness/ -v`

### 质量门失败时会发生什么？

门控触发 **收敛循环**：审查发现 → 修复问题 → 重新测试 → 复查门控。最多 3 轮。如果仍然失败，升级到人工并附上差异报告。

## 更新与版本

### 如何检查更新？

在 AI 工具中输入 `"update devola"` — 或在终端运行 `devola-version`。
要一次性审计所有已安装副本，运行 `devola-init-doctor --skills`：它会扫描
全部已知安装位置，并将每个安装标记为 `current` / `stale` / `unknown-version`。

### 如何更新？

```bash
# npm（用户级 Cursor/Claude 安装；doctor 可做健康检查）
npx @yorha-agents/devola-flow update all

# pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# 安装器（已是最新版本的安装会跳过；--force 强制重新下载）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```

### 如何卸载？

```bash
# 先预览将删除的内容，再实际删除
# （npm 安装的副本也在同一目录，同样被覆盖到）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall --dry-run
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall
```
"""


def _zh_integration() -> str:
    return """\
## 支持的平台

| 平台 | 安装方式 | Skill 格式 | 范围 |
|------|---------|-----------|------|
| **Cursor** | `devola-init cursor` | SKILL.md + references/ + examples/ | 项目或全局 |
| **Claude Code** | `devola-init claude` | SKILL.md + references/ + examples/ | 项目或全局 |
| **Copilot** | `devola-init copilot` | copilot-instructions.md | 仅项目 |
| **Codex** | `devola-init codex` | SKILL.md + references/ | 仅全局 |

各工具的安装文件清单声明在 `workflow-system/agent/manifest.yaml`
（安装清单的单一事实源）— 上表与其 `install_profiles` 段保持一致。

## Cursor — 详细设置

### 安装

```bash
# 项目级安装（推荐）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# 或用户全局安装
curl -fsSL $INSTALLER | bash -s cursor --global

# 或经 npm 做用户全局安装（需 Node >= 18，无需 curl/bash）
npx @yorha-agents/devola-flow install cursor
```

安装内容（依 `workflow-system/agent/manifest.yaml` 的 `cursor` profile）：
- `.cursor/skills/devola-flow/SKILL.md` — 主 skill 文件
- `.cursor/skills/devola-flow/references/` — Tier-2 领域参考文件
- `.cursor/skills/devola-flow/examples/` — Tier-3 执行追踪示例

### 在 Cursor 中如何工作

DevolaFlow 作为 **Cursor Skill** 加载。当你在 Agent 模式中发送提示词时，Cursor 将 skill 内容加载到 Agent 上下文中。DevolaFlow 的种子选择启发式规则根据你的意图关键词激活。

### 示例会话：构建功能

1. 在项目中打开 Cursor
2. 切换到 **Agent 模式**（Cmd+L / Ctrl+L）
3. 输入请求：

```
实现用户管理 REST API，包含 CRUD 操作、JWT 认证和基于角色的访问控制
```

4. DevolaFlow 激活，Agent 将：
   - 选择 `full-pipeline` 清单种子
   - 从原语来源实体化 API 设计、实现、审查、测试和发布断言
   - 请你确认清单优先级与 preflight 决策
   - 运行有界轮次：L0 Project 取项，L1 Wave 向并行 L2 Task 分派任务
   - 核验证据后才勾选断言
   - 在变更源真相前执行 archive gate

### Cursor 使用技巧

- **手动附加 skill**：输入 `@devola-flow` 显式引用
- **使用 Plan 模式**：Agent 会生成结构化计划而不执行
- **子 Agent 支持**：Cursor 的 Task 工具自然映射到 DevolaFlow 的 L1 Wave → L2 Task 委托

## Claude Code — 详细设置

### 安装

```bash
# 项目级
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# 用户全局
curl -fsSL $INSTALLER | bash -s claude --global

# 或经 npm 做用户全局安装（需 Node >= 18，无需 curl/bash）
npx @yorha-agents/devola-flow install claude
```

将 skill 包安装到 `.claude/skills/devola-flow/`（项目级）或 `~/.claude/skills/devola-flow/`（`--global`）：`SKILL.md` 加上 `references/` 与 `examples/` 目录树，依 `workflow-system/agent/manifest.yaml` 的 `claude` profile。

### 在 Claude Code 中如何工作

DevolaFlow 作为 **Claude Code Skill** 加载。它在意图匹配的提示词（实现 / 修复 / 重构 / 调研）上激活，Claude Code 按需读取参考文件，而非每个会话全量加载。

### 示例会话

```bash
claude

> 为数据库查询实现缓存层，支持 TTL 和缓存失效
```

Claude Code 将：
1. 检测 `full-pipeline` 种子意图
2. 锚定可测清单与已签署的 preflight
3. 使用 L1 Wave 协调和 L2 Task 隔离实现
4. 重复有证据的有界轮次，直到 archive gate 通过或需要升级

## GitHub Copilot — 详细设置

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

安装内容：
- `.github/copilot-instructions.md` — 完整 SKILL.md 内容作为根指令

### 在 Copilot 中如何工作

Copilot 为每个请求读取 `copilot-instructions.md`。工作流启发式规则引导 Copilot 的代码建议和聊天回复遵循结构化模式。

## OpenAI Codex — 详细设置

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

安装内容（依 `workflow-system/agent/manifest.yaml` 的 `codex` profile）：
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/references/`

## CI/CD 集成

在 CI 管线中添加 DevolaFlow 验证：

```yaml
# .github/workflows/ci.yml
- name: DevolaFlow Checks
  run: |
    pip install -e '.[dev]'
    python -m pytest tests/ --cov=devolaflow -q
    ruff check src/ tests/
    validate-template --all
    build-skill --all
```
"""


def _zh_customization() -> str:
    return """\
## 创建清单种子

清单种子是 `workflow-system/agent/templates/seeds/` 下的 YAML 文件，遵循 `schemas/checklist-seed.schema.yaml`。它保存领域分解知识，但不会创建新的可执行运行时。

唯一可执行模板是 `workflow-system/agent/templates/builtin/change-driven.yaml`。自定义种子会实体化到这个共享清单轮次运行时中。

### 种子结构

```yaml
schema_version: "1.0"
kind: checklist-seed
metadata:
  name: code-review
  version: "1.0.0"
  description: "独立代码审查证据种子。"
  category: composite
  intent_keywords: [review, quality, pull-request]
  source:
    kind: composition
    name: code-review
    path: workflow-system/agent/templates/registry.yaml
    schema_version: "3.0"

placeholders:
  review_command:
    description: "仓库批准的有界审查命令。"
    required: true
    example: "ruff check src/ tests/"

partitions:
  - key: review
    title_template: "代码审查"
    source_stages:                 # 只记录来源，绝不表示执行顺序
      - {id: review, primitive: review}
    assertions:
      - key: findings-resolved
        statement_template: "所有 blocker 与 critical 审查发现均已解决"
        suggested_priority: P0
        verify:
          mode: metric
          template: "open_blocker_count == 0 and open_critical_count == 0"
      - key: checks-pass
        statement_template: "批准的静态审查命令通过"
        suggested_priority: P1
        verify:
          mode: command
          template: "{{ review_command }}"
```

### 种子可以表达什么

- 意图关键词与可选场景
- 面向用户的清单分区
- 渲染后不超过 25 词的可测断言模板
- 用户可以修改的 P0/P1/P2 建议优先级
- 有界命令、指标或人工检查三种验证方式
- `source_stages` 中仅含历史来源 ID 与 14 种原语标签之一

### 种子禁止表达什么

种子不是运行时 DAG。禁止顶层 `stages`、`composition`、`loops`、`gates`，也禁止 `team`、`duration_class`、`input_mapping`、`skip_condition` 等运行时字段。种子顺序仅供展示。

checkbox、证据路径、轮次号、checked-by 元数据和运行时依赖也不属于种子。只有 L0 将种子实体化为用户确认的变更清单时，才会分配这些信息。

## 注册种子

在注册表中新增一个带 `seed:` 路径且不含可执行 `path:` 的条目。只有 `change-driven` 条目可以声明 `path: builtin/change-driven.yaml`。

## 自定义上下文配置

编辑 `workflow-system/agent/context_profiles.yaml` 添加新任务类型的配置。每个配置指定 SKILL.md 段落的优先级：

- **critical**：始终包含，优先加载
- **important**：预算允许时包含
- **supplementary**：仅剩余空间时包含
- **skip**：对此任务类型永不包含

## 验证更改

自定义后，务必验证：

```bash
validate-template --all                # 23 个种子 + 一个运行时有效
python -m pytest tests/ -q             # 所有测试通过
python -m pytest tests/harness/ -v       # harness 合约通过
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

### 种子或运行时验证失败

```bash
validate-template path/to/template.yaml
```

常见原因：
- 缺少种子必需字段（`schema_version`、`kind`、`metadata`、`placeholders`、`partitions`）
- 种子包含顶层 `stages`、`composition`、`loops` 或 `gates` 等可执行 DAG 字段
- `source_stages` 没有保留 ID 与 14 种来源原语之一
- command 或 metric 验证没有有界 `template`

## Harness 问题

### Harness 合约失败

```bash
python -m pytest tests/harness/ -v
```

1. 检查失败的 fixture、遥测、评估或 probe 合约
2. 审查报告中的 schema、路径或 guard 不匹配
3. 修复源合约；归档基线继续作为历史证据保留

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
