# DevolaFlow

[![CI](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Version](https://img.shields.io/badge/version-0.2.0-green.svg)](https://github.com/YoRHa-Agents/DevolaFlow/releases)

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

## Quick Install (Pick One)

### One-liner (no clone needed)

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

curl -fsSL $INSTALLER | bash -s cursor            # Cursor (project-local)
curl -fsSL $INSTALLER | bash -s cursor --global    # Cursor (user-global ~/.cursor/)
curl -fsSL $INSTALLER | bash -s claude             # Claude Code (project-local ./CLAUDE.md)
curl -fsSL $INSTALLER | bash -s claude --global    # Claude Code (user-global ~/.claude/CLAUDE.md)
curl -fsSL $INSTALLER | bash -s copilot            # Copilot (.github/)
curl -fsSL $INSTALLER | bash -s all                # all tools at once
curl -fsSL $INSTALLER | bash -s update             # update existing installs
```

### pip install + init

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project/
devola-init              # auto-detect tools and install
devola-init cursor       # Cursor only (project-local)
devola-init claude --global  # Claude Code only (user-global)
devola-init all          # all tools
```

### Manual (copy one file)

Download [`MVP-SKILL.md`](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/MVP-SKILL.md) and drop it in:

| Tool | Project-local | User-global |
|------|--------------|-------------|
| **Cursor** | `.cursor/skills/devola-flow/SKILL.md` | `~/.cursor/skills/devola-flow/SKILL.md` |
| **Codex** | -- | `~/.codex/skills/devola-flow/SKILL.md` |
| **Claude Code** | `./CLAUDE.md` | `~/.claude/CLAUDE.md` |
| **Copilot** | `.github/copilot-instructions.md` | -- |

### Full Development Setup

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
make test && make validate-templates   # 250 tests, 11 templates
make build-skill                        # generate all 4 tool outputs
devola-init all                         # install to all detected tools
```

## Using DevolaFlow in Your Agent Tool

After installing, DevolaFlow activates automatically when you ask your AI tool to do multi-step work. Here's what to expect in each tool.

### Cursor

DevolaFlow is loaded as a Cursor Skill. It triggers on intent-matched keywords like "implement", "fix bug", "refactor", "full pipeline".

**Try these prompts:**

```
"Implement a user authentication system from scratch"
  -> Agent selects full-pipeline workflow (8 stages: design -> plan -> impl -> review -> test -> refine -> gate -> release)
  -> Sets up 4-layer hierarchy: dispatches Design stage first

"Fix the login timeout bug in production"
  -> Agent selects hotfix workflow (4 stages: triage -> fix -> test -> release)
  -> Skips design/plan, goes straight to triage

"Refactor the database layer to use repository pattern"
  -> Agent selects refactoring workflow (5 stages: scope -> plan -> impl -> test -> review)

"Research the best approach for real-time notifications"
  -> Agent selects research-only workflow (3 stages: research -> compare -> report)
  -> Produces a report, no code
```

**What the agent does differently with DevolaFlow:**

1. **Dispatches instead of diving in** -- the main agent selects a workflow and dispatches stage-by-stage via subagents, instead of trying to do everything in one pass
2. **Uses subagents with isolated context** -- each task gets its own subagent with only the files it needs (~8K token budget), preventing context pollution
3. **Runs quality gates** -- after implementation, the agent runs review + test passes and checks `composite score >= 85` before advancing
4. **Follows convergence loops** -- if review finds issues, the agent refines and re-tests (up to 3 rounds) instead of shipping broken code

### Claude Code

DevolaFlow is loaded as your `CLAUDE.md` file (always active). The same prompts work. Claude Code will follow the hierarchy rules and workflow structure in every session.

### GitHub Copilot

DevolaFlow is loaded as `copilot-instructions.md` (applied to every request). Copilot follows the workflow selection heuristics and hierarchy constraints when generating code suggestions and chat responses.

### Codex CLI

DevolaFlow is loaded as a Codex Skill. It activates on the same intent keywords. Codex will use subagents for parallel task execution within waves.

### Checking for Updates

DevolaFlow includes a built-in update check you can trigger from inside your AI tool. Just ask:

```
"update devola"
"/update-devola"
"update_devola"
```

The agent will compare your installed version against the latest on GitHub and tell you if an update is available, along with the exact command to run. This check is **manual only** -- it never runs automatically, so it won't consume context tokens unless you ask for it.

### Prompt patterns that work well

| Prompt pattern | What it triggers |
|---------------|-----------------|
| "Implement X from scratch" | `full-pipeline` -- full lifecycle with design, plan, implementation, review, test, release |
| "Fix bug in X" / "X is broken" | `hotfix` -- fast 4-stage triage-fix-test-release |
| "Refactor X" / "Clean up X" | `refactoring` -- restructure with regression testing |
| "Research X" / "Compare X vs Y" | `research-only` -- structured report, no code |
| "Design the architecture for X" | `design-only` or `RDRR` -- research-backed design |
| "Add X to existing Y" | `feature-enhancement` -- extend existing system |
| "Migrate from X to Y" | `migration` -- assess, plan, implement, validate, cutover |
| "Is X feasible?" / "Prototype X" | `spike-poc` -- quick experiment |
| "Write docs for X" | `documentation` -- survey, author, review |
| "Security audit of X" | `security-audit` -- threat model, scan, remediate, verify |
| "update devola" | Check for newer version and get update instructions |

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

## Versioning & Updates

DevolaFlow uses unified versioning -- a single version number (`src/devolaflow/__init__.py`) synchronized across all skill files, templates, and docs.

### Checking your version

```bash
devola-version                   # prints "DevolaFlow v0.2.0"
python -c "import devolaflow; print(devolaflow.__version__)"
```

Or ask your AI agent: `"update devola"` -- it will check and report the installed version.

### Updating to the latest version

**From inside your AI tool** (recommended):

Just type `"update devola"` or `"/update-devola"`. The agent checks GitHub for the latest version and provides the right update command for your setup.

**From the terminal:**

```bash
# If installed via pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# If installed via the one-liner installer
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"
curl -fsSL $INSTALLER | bash -s update

# If installed via devola-init
cd DevolaFlow && git pull && pip install -e ".[dev]"
devola-init cursor --global      # re-install updated skill files
devola-init claude --global
```

### Bumping version (for contributors)

```bash
python scripts/bump_version.py 0.3.0            # updates all 7 version locations
python scripts/bump_version.py 0.3.0 --dry-run   # preview without writing
```

## CLI Tools

```bash
devola-version                   # print current version
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
  src/devolaflow/             # Python package (engine code)
    template_engine/          #   YAML parser, 5 composition operators, validator
    pre_decision/             #   repo detection, checklist, workflow recommender
    gate/                     #   composite scorer, profiles, convergence
    adapters/                 #   Cursor / Codex / Claude / Copilot output adapters
    build_skill.py            #   adapter pipeline entry
    cli.py                    #   CLI entry points
  workflow-system/
    agent/                    # Agent-consumed content (md + yaml only)
      SKILL.md                #   Tier 1 entry point (<500 lines)
      MVP-SKILL.md            #   self-contained single-file version
      references/             #   Tier 2: 8 domain reference files (200-500 lines)
      templates/builtin/      #   11 workflow template YAMLs
      examples/               #   Tier 3: 3 execution trace walkthroughs
      knowledge/              #   Tier 3: code-rules + principle mappings
      workflow-skill.yaml     #   canonical source for adapter pipeline
    human/                    # Human-readable documentation + demo
      en/                     #   8 English docs
      zh/                     #   8 Chinese docs
      demo/                   #   interactive web demo (GitHub Pages)
  schemas/                    # All schema definitions (system + primitives)
    *.schema.yaml             #   7 system schemas (template, dispatch, gate, etc.)
    primitives/               #   per-primitive I/O schemas (future)
  doc/designs/                # 14 design documents (~12,700 lines)
  scripts/                    # build/sync/detect shell helpers
  tests/                      # pytest suite
  .github/workflows/          # CI + Release + Pages
  .cursor/rules/              # always-on hard constraints (5 rules)
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
