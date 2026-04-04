# DevolaFlow

[![CI](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)

**Composable workflow meta-framework** for AI-assisted software development. Define multi-stage delivery pipelines, agent hierarchies, and quality gates as declarative YAML templates -- then let any AI coding tool orchestrate them.

```
User Request
    |
    v
 [Pre-Decision] -> detect repo mode, recommend workflow type
    |
    v
 [Project Agent] -> dispatches stages sequentially
    |
    +-- [Stage Agent: Design]    -> decomposes into waves
    |       +-- [Wave Agent]     -> dispatches tasks in parallel
    |           +-- [Task Agent] -> writes code / runs tests / reviews
    |
    +-- [Stage Agent: Implement] -> convergence loop (review-fix-test-fix)
    |
    +-- [Stage Agent: Release]   -> tag, changelog, publish
    |
    v
 [Gate: composite >= 85, 0 blockers] -> PASS -> advance | FAIL -> refine
```

## 30-Second Setup

```bash
# Clone & install
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"

# Verify everything works
make test                  # run test suite
make validate-templates    # validate all 11 workflow templates
```

## Use with AI Tools

DevolaFlow generates skill/instruction files for four AI coding tools from a single source:

```bash
make build-skill    # generates outputs in dist/
```

| Tool | Output | How to use |
|------|--------|-----------|
| **Cursor** | `dist/cursor/SKILL.md` + `references/` | Copy to `.cursor/skills/devola-flow/` |
| **Codex** | `dist/codex/SKILL.md` + `agents/openai.yaml` | Copy to `~/.codex/skills/devola-flow/` |
| **Claude Code** | `dist/claude/CLAUDE.md` | Copy to project root as `CLAUDE.md` |
| **Copilot** | `dist/copilot/.github/copilot-instructions.md` | Copy to `.github/` |

Or use the **MVP single-file** (`workflow-system/agent/MVP-SKILL.md`) -- drop it into any tool as a standalone instruction file.

## What's Inside

### 11 Built-in Workflow Types

| Type | When to use | Stages |
|------|-------------|--------|
| `full-pipeline` | New feature, greenfield project | design - plan - impl - review - test - refine - gate - release |
| `hotfix` | Production bug, urgent fix | triage - fix - test - release |
| `refactoring` | Tech debt, restructure | scope - plan - impl - test - review |
| `research-only` | Compare alternatives, survey | research - compare - report |
| `design-only` | Architecture, API design | research - design - review |
| `migration` | Upgrade, port systems | assess - plan - impl - validate - cutover |
| `spike-poc` | Prototype, experiment | research - prototype - evaluate |
| `documentation` | Docs, guides, API refs | survey - author - review |
| `security-audit` | Vulnerability scan, compliance | threat - scan - analyze - remediate - verify |
| `feature-enhancement` | Extend existing features | scope - design - plan - impl - review - test - release |
| `RDRR` | Design with research, ADR | research - design - review - refine (loop) |

### 4-Layer Agent Hierarchy

| Layer | Role | Context Budget | Key Rule |
|-------|------|---------------|----------|
| **Project** | Dispatch stages, track status | ~3K tokens | Never reads source code |
| **Stage** | Decompose to waves, run gates | ~5K tokens | Never writes code |
| **Wave** | Parallel-dispatch tasks | ~4K tokens | Never executes task work |
| **Task** | **The only layer that works** | ~8K tokens | Never spawns sub-agents |

### Quality Gate Mechanism

Every stage passes through a quality gate before advancing:

```
composite = test_quality * 0.30 + code_review * 0.30
          + architecture * 0.20 + benchmark * 0.20

PASS when: composite >= 85 AND blockers == 0 AND round >= 1
FAIL: run convergence loop (review -> fix -> test -> fix), max 3 rounds
ESCALATE: produce divergence report for human review
```

## CLI Tools

```bash
validate-template --all          # validate all workflow templates
validate-template path/to.yaml  # validate a single template
validate-gate                    # evaluate a gate checkpoint
detect-repo-mode                 # detect local / github / gitlab / etc.
build-skill --all                # generate outputs for all 4 AI tools
check-drift                      # verify human docs are in sync
```

## Project Structure

```
DevolaFlow/
  src/devolaflow/             # Python package
    template_engine/          #   YAML parser, 5 composition operators, validator
    pre_decision/             #   repo detection, checklist, workflow recommender
    gate/                     #   composite scorer, profiles, convergence
    adapters/                 #   Cursor / Codex / Claude / Copilot adapters
    build_skill.py            #   adapter pipeline
    cli.py                    #   CLI entry points
  workflow-system/
    agent/                    # Agent-consumed skill files
      SKILL.md                #   entry point (<500 lines)
      MVP-SKILL.md            #   self-contained single-file version
      references/             #   8 domain reference files (200-500 lines each)
      templates/builtin/      #   11 workflow template YAMLs
      examples/               #   3 execution trace walkthroughs
      workflow-skill.yaml     #   canonical source for adapter pipeline
    human/                    # Human-readable documentation
      en/                     #   8 English docs
      zh/                     #   8 Chinese docs
      demo/                   #   interactive web demo (GitHub Pages)
  doc/designs/                # 14 design documents (~12,700 lines total)
  schemas/                    # 7 YAML schema definitions
  tests/                      # pytest suite
  .github/workflows/          # CI + Release + Pages
```

## Interactive Demo

Browse the framework architecture, workflow types, and stage primitives interactively:

**[Live Demo](https://yorha-agents.github.io/DevolaFlow/)** (GitHub Pages)

| Page | What it shows |
|------|--------------|
| [Design Architecture](https://yorha-agents.github.io/DevolaFlow/design-architecture/) | Complete framework map: every skill file, design source, tier, token budget, dependency graph |
| [Workflow Visualizer](https://yorha-agents.github.io/DevolaFlow/workflow-visualizer/) | 11 workflow types as interactive pipeline diagrams with teams, gates, and loops |
| [Stage Explorer](https://yorha-agents.github.io/DevolaFlow/stage-explorer/) | 13 stage primitives with I/O types, delegation chains, and context budgets |

Or open locally: `workflow-system/human/demo/index.html`

## Documentation

| Doc | Language |
|-----|----------|
| [Quick Start](workflow-system/human/en/quickstart.md) | English |
| [Architecture Overview](workflow-system/human/en/architecture-overview.md) | English |
| [Workflow Types](workflow-system/human/en/workflow-types.md) | English |
| [快速入门](workflow-system/human/zh/quickstart.md) | 中文 |
| [架构概述](workflow-system/human/zh/architecture-overview.md) | 中文 |
| [Design Documents](doc/designs/) | English (14 specs) |

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make changes following the [5 hard constraints](.cursor/rules/workflow-rules.mdc)
4. Run `make all` to verify
5. Submit a Pull Request (never push directly to `main`)

Commit messages use conventional format: `feat:`, `fix:`, `docs:`, `test:`, `chore:`

## License

MIT
