---
title: "FAQ"
description: "Frequently asked questions about the workflow system."
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-05T00:00:00Z"
source_version: "1.0.0"
---

# Frequently Asked Questions

## General

**Q: What is DevolaFlow?**

A: A composable workflow meta-framework for AI-assisted software development. It defines multi-stage delivery pipelines as declarative YAML templates, with a 4-layer agent hierarchy (Project/Stage/Wave/Task) and quality gates.

**Q: How many workflow types are supported?**

A: 11 built-in types covering research, design, implementation, hotfix, refactoring, migration, security audit, and more. Plus unlimited custom templates.

**Q: Which AI tools does it support?**

A: Cursor, OpenAI Codex (CLI), Claude Code, and GitHub Copilot. Run `make build-skill` to generate outputs for all four.

## Architecture

**Q: Why a 4-layer hierarchy instead of just agents doing work?**

A: Context isolation. Upper layers (Project/Stage/Wave) only dispatch and monitor -- they never see source code. This prevents context pollution and keeps each Task Agent focused on a single concern with a bounded ~8K token budget.

**Q: Can dispatcher agents (Project/Stage/Wave) write code?**

A: No. This is the strongest invariant in the system (P1: Dispatcher-Not-Implementer). Only Task Agents at Layer 3 perform actual work.

**Q: What are the 13 stage primitives?**

A: research, analyze, design, plan, implement, review, test, validate, refine, release, deploy, monitor, gate. Every workflow is a composition of these primitives.

## Quality Gates

**Q: What is the gate pass threshold?**

A: Default (standard profile): composite score >= 85, zero blocker findings, at least 1 review round. The composite is a weighted sum: test(0.30) + review(0.30) + architecture(0.20) + benchmark(0.20).

**Q: What happens when a gate fails?**

A: If rounds remain (default max: 3), a convergence loop runs: review findings, fix, re-test, re-evaluate. If max rounds are exhausted, the system escalates to the human with a divergence report.

**Q: Can I adjust the quality thresholds?**

A: Yes. Four built-in profiles: `strict` (90/85%/0 criticals), `standard` (85/80%), `relaxed` (70/60%), `audit` (95/90%). Or set custom thresholds per-template.

## Usage

**Q: How do I start? What's the quickest path?**

A: One command: `curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor`. This downloads SKILL.md, 8 references, 3 examples, and rules into `.cursor/skills/devola-flow/`. Add `--global` to install user-wide. Or just download [MVP-SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/MVP-SKILL.md) and drop it in manually.

**Q: Project-local or global install?**

A: Cursor supports both: `--project` (default) installs to `.cursor/skills/` in the current repo, while `--global` installs to `~/.cursor/skills/`. Claude Code also supports both scopes: project-local at `./CLAUDE.md`, user-global at `~/.claude/CLAUDE.md`.

**Q: How do I update to the latest version?**

A: Run `curl -fsSL .../install.sh | bash -s update`. It finds all existing DevolaFlow installs and re-downloads the latest files.

**Q: How do I create a custom workflow?**

A: Create a YAML file in `workflow-system/agent/templates/custom/` following the template schema. Run `validate-template your-file.yaml` to check it. See [Customization Guide](customization-guide.md).

**Q: Do I need Python to use DevolaFlow?**

A: No. The `curl` installer and manual file download work without Python. Python 3.11+ is only needed for the CLI tools (template validation, gate scoring, build pipeline).

## Troubleshooting

**Q: `validate-template` shows lattice warnings. Is that a problem?**

A: No. Lattice warnings are advisory. They flag stage transitions that don't follow the default dependency lattice, but the design explicitly allows this. Only errors (not warnings) block validation.

**Q: My AI tool doesn't seem to follow the hierarchy. What's wrong?**

A: Ensure the SKILL.md or CLAUDE.md is loaded. Check that the P1 rule (Dispatcher-Not-Implementer) is present. If using Cursor, verify the `.cursor/rules/workflow-rules.mdc` file exists with all 5 constraints.
