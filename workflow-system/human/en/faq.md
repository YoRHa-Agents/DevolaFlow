---
title: "FAQ"
description: "Frequently asked questions about the workflow system."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T08:45:55Z"
source_version: "17.0.0"
---

# FAQ

Frequently asked questions about the workflow system.

## General

What is DevolaFlow?

A composable workflow meta-framework for AI-assisted software development. It turns one of 23 domain checklist seeds into a user-confirmed execution contract, then runs that contract through a three-layer Project → Wave → Task hierarchy and the `change-driven` checklist-round runtime.

### What AI tools does it support?

**Cursor** — loaded as a Cursor Skill (`.cursor/skills/devola-flow/SKILL.md`)
- **Claude Code** — loaded as a Claude Code Skill (`.claude/skills/devola-flow/SKILL.md`)
- **GitHub Copilot** — loaded as `copilot-instructions.md`**OpenAI Codex** — loaded as a Codex Skill

A single source (`workflow-skill.yaml`) is adapted to each tool's format via the `build-skill` pipeline.

Do I need to learn YAML to use DevolaFlow?

No. DevolaFlow activates automatically from natural language. Say "fix the login bug" and it selects the `hotfix` seed. Say "build a new feature from scratch" and it selects `full-pipeline`. You only need YAML to author custom checklist seeds.

### How does DevolaFlow differ from just prompting my AI tool?

Without DevolaFlow, your AI tool may process the whole request in one pass and mix design, implementation, and verification. DevolaFlow anchors measurable checklist assertions with you, executes a bounded set each round, and checks an item only after evidence is verified.

## Workflows

### How does the agent choose a checklist seed?

DevolaFlow uses **intent matching** on your prompt keywords: "fix bug" / "broken" / "crash" →`hotfix`"from scratch" / "new project" →`full-pipeline`"research" / "compare" →`research-only`"refactor" / "clean up" →`refactoring`And so on for all 23 seeds

You can also specify one explicitly: "Use the migration seed to upgrade from React 17 to 18."

Can I reduce the ceremony?

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
- **soul.mdc** (S-1 to S-10): immutable invariants, test coverage floor (≥80%), no ghost features
- **architecture.mdc** (A-1 to A-7): three-layer hierarchy, cache layout, token budgets
- **conventions.mdc** (C-1 to C-9, C-8 retired): SKILL.md line budget, frontmatter, version consistency
- **workflow.mdc** (W-1 to W-24): iteration planning, benchmarks, version bump protocol
- **style.mdc** (ST-1 to ST-13): documentation sync, web demo, bilingual completeness

How does built-in evaluation work?

The built-in harness validates deterministic fixtures, dispatch constraints,
telemetry aggregation, and bounded model-compliance probes.

Run its contract suite with: `python -m pytest tests/harness/ -v`

What happens when a gate fails?

The gate triggers a **convergence loop**: review findings → fix issues → re-test → re-check gate. This repeats up to 3 rounds. If the gate still fails after max rounds, it escalates to the human with a divergence report explaining what's blocking.

## Updates & Versioning

How do I check for updates?

Ask your AI agent: `"update devola"`, or run `devola-version` in the terminal.
To audit every installed copy at once, run `devola-init-doctor --skills`: it
scans all known install locations and reports each install as `current`,
`stale`, or `unknown-version`.

How do I update?

```bash
# pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# installer (skips installs already at the latest version; --force re-downloads)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```

### How do I uninstall?

```bash
# preview what would be removed, then remove for real
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall --dry-run
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall
```
