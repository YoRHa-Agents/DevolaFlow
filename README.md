# DevolaFlow

*From the guardians of YoRHa — a framework that watches over your code.*

[![CI](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Version](https://img.shields.io/badge/version-11.4.0-green.svg)](https://github.com/YoRHa-Agents/DevolaFlow/releases)

**Composable workflow meta-framework** for AI-assisted software development. Define multi-stage delivery pipelines, agent hierarchies, and quality gates as declarative YAML templates — then let any AI coding tool orchestrate them.

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

# v9.2.3 mode shorthand (consolidates --no-compile / --with-examples)
devola-init local --mode=core      # lean install — scaffolding only
devola-init local --mode=standard  # default — compile rules, no examples
devola-init local --mode=full      # full demo — compile + seed examples
```

### Troubleshooting installs

**`pip install` failing on a corporate mirror?** Some internal mirrors
(e.g. `https://*.baidubce.com/pypi/...`) ship `setuptools` versions older
than the `>=68.0` floor required to install DevolaFlow's editable build
backend. Override the index URL while keeping the corporate proxy active:

```bash
pip install --index-url https://pypi.org/simple/ \
    git+https://github.com/YoRHa-Agents/DevolaFlow.git
```

**`devola-init` exits with `Error: Agent source not found ...` after a
pip install?** Resolved in **v9.2.2** (I-001). `devola-init local` now
succeeds on pip-wheel-only installs (the wheel does not bundle
`workflow-system/` and `install_local` doesn't need it). The other
targets (`cursor` / `claude` / `codex` / `copilot`) still require a
clone install — `git clone https://github.com/YoRHa-Agents/DevolaFlow
&& pip install -e ./DevolaFlow` — because they copy the
`workflow-system/agent/` source tree into the consumer-side skill
directory.

**Want the shortest possible bootstrap?** `devola-init local --mode=core`
is the lean recipe (skips rule compilation + example seeds; works on
wheel-only installs from v9.2.3 onward).

### Manual (copy one file)

Download [`SKILL.md`](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md) and drop it in:

| Tool | Project-local | User-global |
|------|--------------|-------------|
| **Cursor** | `.cursor/skills/devola-flow/SKILL.md` | `~/.cursor/skills/devola-flow/SKILL.md` |
| **Codex** | — | `~/.codex/skills/devola-flow/SKILL.md` |
| **Claude Code** | `./CLAUDE.md` | `~/.claude/CLAUDE.md` |
| **Copilot** | `.github/copilot-instructions.md` | — |

Full Development Setup

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
make test && make validate-templates   # 3092 tests, 22 templates
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

1. **Dispatches instead of diving in** — the main agent selects a workflow and dispatches stage-by-stage via subagents, instead of trying to do everything in one pass
2. **Uses subagents with isolated context**, each task gets its own subagent with only the files it needs (~8K token budget), preventing context pollution
3. **Runs quality gates**, after implementation, the agent runs review + test passes and checks `composite score >= 85` before advancing
4. **Follows convergence loops** — if review finds issues, the agent refines and re-tests (up to 3 rounds) instead of shipping broken code

Claude Code

DevolaFlow is loaded as your `CLAUDE.md` file (always active). The same prompts work. Claude Code will follow the hierarchy rules and workflow structure in every session.

GitHub Copilot

DevolaFlow is loaded as `copilot-instructions.md` (applied to every request). Copilot follows the workflow selection heuristics and hierarchy constraints when generating code suggestions and chat responses.

Codex CLI

DevolaFlow is loaded as a Codex Skill. It activates on the same intent keywords. Codex will use subagents for parallel task execution within waves.

### Checking for Updates

DevolaFlow includes a built-in update check you can trigger from inside your AI tool. Just ask:

```
"update devola"
"/update-devola"
"update_devola"
```

The agent will compare your installed version against the latest on GitHub and tell you if an update is available, along with the exact command to run. This check is **manual only** — it never runs automatically, so it won't consume context tokens unless you ask for it.

### Prompt Patterns

| Prompt pattern | What it triggers |
|---------------|-----------------|
| "Implement X from scratch" | `full-pipeline` — full lifecycle with design, plan, implementation, review, test, release |
| "Fix bug in X" / "X is broken" | `hotfix` — fast 4-stage triage-fix-test-release |
| "Refactor X" / "Clean up X" | `refactoring` — restructure with regression testing |
| "Research X" / "Compare X vs Y" | `research-only` — structured report, no code |
| "Design the architecture for X" | `design-only` or `RDRR` — research-backed design |
| "Add X to existing Y" | `feature-enhancement` — extend existing system |
| "Migrate from X to Y" | `migration` — assess, plan, implement, validate, cutover |
| "Is X feasible?" / "Prototype X" | `spike-poc`, quick experiment |
| "Write docs for X" | `documentation`, survey, author, review |
| "Security audit of X" | `security-audit`, threat model, scan, remediate, verify |
| "Build a demo of X" / "Showcase X" | `demo-showcase`, presentation-ready demo with polished UI |
| "X is slow" / "Optimize X" | `performance-optimization`, profile, optimize, benchmark |
| "Set up dev environment" / "Install X" | `dependency-setup`, research, configure, verify |
| "I'm new to this project" | `onboarding`, codebase survey, docs, env setup |
| "Optimize SKILL.md" / "EvoBench" | `skill-optimization`, survey → profile → optimize → benchmark → iterate → document |
| "update refs" / "check references" | `self-update`, track and integrate external reference changes |
| "update devola" | Check for newer version and get update instructions |

## What's New in v10.3.0 (MINOR cycle close)

The v10.3.0 release closes the v10.2.0 cycle (5 PATCH PVs + this MINOR cycle close). The user mandate from `.local/feedbacks/feedback_for_v10.2.0.md` was: deep-review plugin mode + verify auto-install + daily auto-upgrade; formally integrate Si-Chip; NineS-analyse the self-repo + validate Si-Chip iteration effectiveness; multi-round self-iteration with one PATCH per round; bump MINOR to v10.3.0. All five bullets shipped with verbatim evidence. Headline numbers:

| Area | v10.0.0 baseline | v10.3.0 | Delta |
|------|---:|---:|---:|
| Plugins registered | 4 | 4 | unchanged (deepened via plugin-infra deep review) |
| Lifecycle events | 10 | 10 | unchanged (no new hooks this cycle) |
| Si-Chip dogfood verdict | DEFER (v9.5.0 deferred) | **APPLY** (passes #3 + #4 = +0.9 each) | **first APPLY in DevolaFlow history** |
| NineS-to-Si-Chip eval adapter | n/a | **412 LOC + 23 tests** | NEW; closes v9.5.0 OA-1 blocker |
| iteration_delta CI gate | not in CI | wired as 7th SI-10 step | `Makefile::release-preflight` |
| New env flags | n/a | **0** (W-20 reuse-first) | unchanged |
| W-3 SI-3 composite | 9.20 (v10.0.0) | **9.39** | +0.19 (margin +0.39 over STRICT MINOR-cycle-close ≥9.0) |

### What landed (per PV)

1. **PV-01 (v10.2.0) — Plugin deep review + W-16 wholesale baseline regen.** Closes 4 plugin-infra gaps (D-P-1 end-to-end `refresh_all`, D-P-3 si-chip `version_check_cmd` real probe, D-P-4 registry-walk smoke, D-P-6 never-installed staleness). Ships 3 new test files + 1 install_resolver helper. W-16 wholesale `v10.2.0_baseline.json` byte-identical to v9.7.0 (zero drift since v10.0.0).
2. **PV-02 (v10.2.1) — Formal Si-Chip integration + 7-step SI-10 + daily-upgrade scheduler.** Closes 5 gaps including D-P-2 BLOCKER. NEW `dispatch_dogfood_cycle` wrapper exposes Si-Chip at the L0/L1 dispatch surface. NEW Si-Chip `iteration_delta` CI gate is wired into `Makefile::release-preflight` as the 7th SI-10 step.
3. **PV-03 (v10.2.2) — NineS deep self-analysis + Si-Chip eval adapter prototype.** Closes D-N-1 + D-N-3. NEW `scripts/nines_to_sichip_eval_adapter.py` (412 LOC, 23 tests) — adapter verdict APPROVE; v9.5.0 OA-1 blocker resolved. 3 NineS deep-analyses on `si_chip_bridge`, `plugins`, `lifecycle` (62 findings, 10 complexity warnings).
4. **PV-04 (v10.2.3) — Self-iteration round 1.** Bridge defect FIX in `MetricsReport.from_yaml_dict` (MVP-8 nested-key support; legacy fallback preserved) unblocks the `iteration_delta` machinery — dogfood pass #3 verdict APPLY with `iteration_delta = +0.9` across all 4 probed files. Plus 2 mechanical CC reductions (`pre_plugin_invocation` 18→≤10, `post_skill_edit` 13→≤7) per PV-03 NineS hotspots.
5. **PV-05 (v10.2.4) — Self-iteration round 2 + W-17 mid-cycle audit + W-8 stagnation predicate.** 1 mechanical CC reduction (`installer.read_last_checked` 15→8 via `_parse_log_event_timestamp` extraction) + dogfood pass #4 (+0.9 byte-identical to pass #3 — round-1 effects persist). W-8 stagnation predicate evaluated FALSE → CONTINUE. W-17 cycle-cumulative count 93/150 — well within cap.
6. **PV-06 (v10.3.0) — Cycle close MINOR.** Version bump 10.2.4 → 10.3.0 across canonical 7 sync locations. NineS cycle-close self-eval (overall 0.906924; byte-stable vs v10.0.0 0.907332). W-3 SI-3 evaluation composite **9.385/10** (margin +0.385 over STRICT MINOR-cycle-close ≥9.00). W-7 SI-8 retrospective (4 mandatory sections + 8 explicit deferrals + 7 key learnings + W-21 v10.4.0 telegraph). W-19 cycle archive at `docs/cycle-archive/v10.3.0/` (25 files). PR `feat/v10.2.0-cycle` ready for review.

### Breaking changes

**None.** Every change in the cycle is additive: NEW `dispatch_dogfood_cycle` (v10.2.1), NEW `iteration_delta_gate` test surface, NEW `dedup_feedback_doc` behaviour (idempotent — repeats are no-ops), NEW `read_installed_si_chip_version` helper, NEW MVP-8 nested-key support in `MetricsReport.from_yaml_dict` (legacy top-level shape preserved). Zero new env flags (W-20 §3 reuse-first applied — D-P-2 daily-upgrade integration REUSES `DEVOLAFLOW_AUTO_INSTALL_PLUGINS`). Schema v6 (17-position canonical_order) byte-stable across all 10 historical multi-baseline byte tests. Soul-set count remains at 10 (W-21 freeze; S-11 candidate "Parallel Wave Dispatch Invariant" re-telegraphed for v10.4.0).

## What's New in v10.0.0 (MAJOR cycle close)

The v10.0.0 release is the cycle-close MAJOR rollup of the 5-MINOR v10.0.0 cycle (v9.3 → v9.7 → v10.0.0). Headline numbers:

| Area | v9.2.4 baseline | v10.0.0 | Delta |
|------|---:|---:|---:|
| `select_context.p95` | ~80,000 us | ~2,027 us | **-97.5%** (40× speedup) |
| `full_dispatch.p95` | ~250,000 us | ~4,255 us | **-98.3%** |
| pytest wall-clock | ~55 s | ~17 s | **3.3× faster** |
| Lifecycle events | 8 | **10** | +2 (`pre_plugin_invocation`, `post_skill_edit`) |
| Dispatch schema | v5 (16 keys) | **v6 (17 keys)** | +1 canonical position (`predecessor_dedup_ledger` APPEND) |
| Plugins registered | 3 | **4** | +Si-Chip (BasicAbility optimisation factory) |
| Tracked references | 19 (stale comment) | **21 (all NineS-refreshed)** | +2 catch-up + freshness sweep |
| Feedback regression audit | n/a | **57 files / 0 FAILs** | 100% addressed-or-deferred |

### What landed (per MINOR)

1. **v9.3.0 Performance Overhaul #1**, `load_profiles` / `load_skill_md` / `estimate_tokens` LRU cache absorbed 96.6% of dispatch wall-clock (the big one). Compressor split into a 3-module package. AsyncDispatchExecutor library-only landing.
2. **v9.4.0 Plugin Auto-Install & Daily Upgrade**, `pre_plugin_invocation` lifecycle hook + dispatcher wiring (closes the `ensure_plugin()` dead-wire). Schema v3 with per-plugin `upgrade_cmd` + new `devolaflow plugins refresh` CLI.
3. **v9.5.0 Si-Chip DEEP Integration**, `si_chip_bridge` typed Python module (~1070 LOC across 4 sub-modules). `post_skill_edit` always-on lifecycle hook gated `DEVOLAFLOW_SI_CHIP_DEEP=1`. Apply-or-defer gate with +0.10 IEEE-754 epsilon. Dogfood pass DEFERRED per user requirement (real-LLM eval data out of scope).
4. **v9.6.0 Reference Library Refresh**, ALL 21 tracked external references re-audited via NineS deep analysis (5 deep + 16 W-2 manual review). 4 NEW reference-doc subsections wired into `team-roles.md` / `decomposition-gate.md` / `execution-protocol.md` / `meta-framework.md`.
5. **v9.7.0 Performance Overhaul #2**, Predecessor summary delta-compression (12-char sha256 hash; schema v6 APPEND at canonical position 17). Async L2-wave dispatch auto-wire. Selector cache pre-warmup (`DEVOLAFLOW_WARMUP=1`).

### What landed in the v10.0.0 MAJOR rollup itself

- **PV-01**, Version bump 9.7.0 → 10.0.0 across the canonical 7 sync locations (pattern-replace by `scripts/bump_version.py`) — **PV-02**, NEW.`scripts/audit_feedback_ac.py` (~370 LOC) + 31 NEW tests cross-checks 57 historical feedback files against the live repo state. Result: **0 FAILs, 100% addressed-or-deferred** (5 PASS + 49 SUPERSEDED + 2 DEGRADED + 1 DEFERRED). Closes the user's mandate to ensure no AC has regressed.
- **PV-03**, Comprehensive human-docs refresh: 16 EN/ZH user guides regenerated; demo landing page top-of-page v10.0.0 What's New section; `version-timeline/versions.json` v10.0.0 entry; this README block.
- **PV-04**, NineS self-eval + W-3 SI-3 evaluation (MAJOR-gate composite ≥9.0) + W-7 SI-8 retrospective + W-19 cycle-archive at `docs/cycle-archive/v10.0.0/` — **PV-05**,.`CHANGELOG.md` MAJOR entry + W-18 ghost-audit refresh + SI-10 6-gate green + final PR open.

### New env flags (4, all R5-strict, all W-20 §3 orthogonality justified)

- `DEVOLAFLOW_SIMPLE_SHORTCUT=1` (v9.3.0), opt-in skip L1+L2 for SIMPLE/TRIVIAL tasks (default-ON in v10.1+).
- `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` (v9.4.0), opt-in plugin auto-install on dispatch.
- `DEVOLAFLOW_SI_CHIP_DEEP=1` (v9.5.0), DEEP Si-Chip dogfood always-on (`post_skill_edit` hook).
- `DEVOLAFLOW_WARMUP=1` (v9.7.0), pre-populate selector cache on session start.

### Breaking changes

**None.** Every change in the cycle is additive: The`compressor` package re-exports all public symbols at the same import paths (`from devolaflow.compressor import ...` works byte-identically).
- Schema v6 is append-only at canonical position 17 (A-2.2 invariant); all 9 historical multi-baseline byte tests pass byte-identically because the new field's absence is canonical.
- Both new lifecycle events were appended at the tail (positions 9 + 10); positions 1-8 byte-stable since v9.1.3 — All new env flags are default-OFF; absent or any value other than literal.`"1"` preserves prior behaviour.

## What's New in v7.4.3

**Stale Doc Refs Closed (v7.4.3, P-02)**, 12 minor stale numeric/version references in `README.md`, `CLAUDE.md`, `workflow-system/agent/workflow-skill.yaml` aligned with v7.4.2 reality (template count `17→20`, scenario count `20→39`, test count `434+→1343`, rule count `19 process→9 .mdc files`, version-bump location count `11/16→7 canonical sync locations`) — **.`repo-init` Template Landed (v7.4.2)**, Closed v7.4.0's S-4 / CP-1 ghost-feature gap: new `workflow-system/agent/templates/builtin/repo-init.yaml` (4 stages: analyze → scaffold → compile → verify) with `parameters.mode: {minimal | standard | deep}` enum defaulted to `standard` for Claude Code `/init` parity (no heavy verify execution by default) — **CLI Coverage Restored (.v7.4.1)**, `tests/test_cli_local_commands.py` (+7 tests) lifted `src/devolaflow/cli.py` from 63% → 99% coverage; CP-2 / S-3 floor restored after the v7.4.0 staged work — **.`.rules/` 5-Layer Governance (v7.4.0)**, Soul Rules P0 → Architecture P1 → Conventions P2 → Workflow P3 → Style P4 model; rule compiler emits `.cursor/rules/repo-governance.mdc` and `AGENTS.md` from a single canonical source — **.`.local/` Workspace Scaffolding (v7.4.0)**, Structured local dev workspace with `.local/feedbacks/`, `.local/tasks/`, `.local/research/`, and `index.md` navigation; auto-detected by `devola-init` and the curl-installer one-liner.

## What's Inside

### 22 Built-in Workflow Types

| Type | When to use | Stages |
|------|-------------|--------|
| `full-pipeline` | New feature, greenfield project | design → plan → impl → review → test → refine → gate → release |
| `hotfix` | Production bug, urgent fix | triage → fix → test → release |
| `refactoring` | Tech debt, restructure | scope → plan → impl → test → review |
| `research-only` | Compare alternatives, survey | research → compare → report |
| `design-only` | Architecture, API design | research → design → review |
| `migration` | Upgrade, port systems | assess → plan → impl → validate → cutover |
| `spike-poc` | Prototype, experiment | research → prototype → evaluate |
| `documentation` | Docs, guides, API refs | survey → author → review |
| `security-audit` | Vulnerability scan, compliance | threat → scan → analyze → remediate → verify |
| `feature-enhancement` | Extend existing features | scope → design → plan → impl → review → test → release |
| `RDRR` | Design with research, ADR | research → design → review → refine (loop) |
| `demo-showcase` | Demos, presentations, showcases | research → storyboard → build → review → polish → package |
| `performance-optimization` | Slow app, latency, profiling | profile → design → optimize → benchmark → validate |
| `dependency-setup` | Environment setup, tooling | research → plan → configure → verify |
| `onboarding` | New contributor, codebase intro | analyze → document → setup → verify |
| `skill-optimization` | SKILL.md / skills, EvoBench, context density | survey → profile → optimize → benchmark → iterate → document |
| `self-update` | Update references, track external changes | check-refs → research-updates → decompose → integrate → test → evaluate |
| `product-verification` | verify, visual, acceptance, uat, e2e, product | composite |
| NineS-Assisted | Full pipeline with NineS evaluation and quality gates | `nines eval`, quality, benchmark |
| `repo-init` | init repo, scaffold workspace, setup rules, 初始化仓库 | analyze → scaffold → compile → verify (mode: minimal \| standard \| deep) |
| `change-driven` | OpenSpec-style in-flight change folder lifecycle | propose → apply → verify → archive (mode: lite \| full) |
| `entropy-cleanup` | Periodic GC, stale docs, drift audit, retention rules | scan → propose → review → apply |

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

### EvoBench Context Benchmarks

DevolaFlow includes a built-in benchmark suite (57 scenarios covering all 22 workflow types) that measures how effectively context is routed to agents:

```bash
python -m benchmarks.devolaflow_context.runner --scenario all              # run all 57 scenarios
python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline  # detect regressions
python -m benchmarks.devolaflow_context.runner --generate-baseline          # update baseline after improvements
python -m benchmarks.devolaflow_context.runner --round N --round-label "description"  # save optimization round
python -m pytest tests/test_benchmarks.py -v                               # run benchmark tests
```

Current avg composite: **99.49/100** with 100% relevance and 0% noise across all 57 scenarios. Baselines are stored in `benchmarks/devolaflow_context/baselines/` for regression detection. Compare runs visually on the **[Benchmark Results](https://yorha-agents.github.io/DevolaFlow/benchmark-results/)** page (local: `workflow-system/human/demo/benchmark-results/index.html`).

### Task Quality Score

After every workflow completes, DevolaFlow evaluates your original request on 4 dimensions (1-5 each, total /20):

- **Clarity**, Was the intent unambiguous?
- **Scope**, Were boundaries defined?
- **Success Criteria**, Were pass/fail conditions stated?
- **Context**, Was relevant background provided?

The score appears at the end of the workflow report with actionable tips to improve future requests. Scoring is skipped for trivial tasks.

### Repository Development Rules

9 enforceable rule files in `.cursor/rules/` codifying iteration lessons:

| Rule File | Rules | What It Enforces |
|-----------|-------|-----------------|
| `repo-governance.mdc` | S-1..S-7, A-1..A-3, C-1..C-8, W-1..W-15, ST-1..ST-13 | Compiled aggregate: Soul invariants, architecture, conventions, workflow, style |
| `workflow-rules.mdc` | P1..P5 | 4-layer hierarchy: Dispatcher-Not-Implementer, Minimal Context, Structured Messages, Bounded Retry, Artifacts as Contracts |
| `devola-flow-rules.mdc` | P1..P6 | DevolaFlow-specific: P1..P5 + P6 cache-prefix invariant |
| `skill-format-rules.mdc` | SF-1..SF-6 | SKILL.md line budget, frontmatter, version consistency, valid references, no absolute paths |
| `change-process-rules.mdc` | CP-1..CP-7 | No ghost features, test coverage floor (>=80%), version bump protocol, pre-commit checklist |
| `context-optimization-rules.mdc` | CO-1..CO-6 | Lean message format, verbatim extraction, token budgets, benchmark verification |
| `self-improve-iteration-rules.mdc` | SI-1..SI-10 | Iteration planning gate, NineS analysis, evaluation, retrospective, test-then-commit |
| `web-experience-rules.mdc` | WX-1..WX-8 | Four theme showcases, additive design tokens, motion patterns, bilingual showcase pages |
| `documentation-sync-rules.mdc` | DS-1..DS-5 | Human-facing content registry, NieR identity, bilingual completeness, version propagation |

## Versioning & Updates

DevolaFlow uses unified versioning, a single version number (`src/devolaflow/__init__.py`) synchronized across all skill files, templates, and docs.

Checking your version

```bash
devola-version                   # prints "DevolaFlow v11.4.0"
python -c "import devolaflow; print(devolaflow.__version__)"
```

Or ask your AI agent: `"update devola"`, it will check and report the installed version.

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

Bumping version (for contributors)

```bash
python scripts/bump_version.py 7.4.3            # updates all 11 version locations (7 canonical sync locations across 8 files per CP-3)
python scripts/bump_version.py 7.4.3 --dry-run   # preview without writing
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
      SKILL.md                #   Tier 1 entry point (<500 lines, self-contained)
      references/             #   Tier 2: 10 domain reference files (190-710 lines)
      templates/builtin/      #   22 workflow template YAMLs
      examples/               #   Tier 3: 3 execution trace walkthroughs
      knowledge/              #   Tier 3: code-rules + principle mappings
      workflow-skill.yaml     #   canonical source for adapter pipeline
    human/                    # Human-readable documentation + demo
      en/                     #   8 English docs
      zh/                     #   8 Chinese docs
      demo/                   #   interactive web demo (GitHub Pages)
  benchmarks/
    devolaflow_context/        # EvoBench context density benchmarks
      evaluator.py             #   scoring: relevance, density, noise, utilization
      runner.py                #   CLI runner with baseline comparison
      scenarios/               #   45 benchmark scenarios (all 22 workflow types)
      baselines/               #   stored baseline results for regression detection
  schemas/                    # All schema definitions (system + primitives)
    *.schema.yaml             #   7 system schemas (template, dispatch, gate, etc.)
    lean-dispatch.yaml        #   lean TaskDispatch format spec
    lean-report.yaml          #   lean StatusReport format spec
    primitives/               #   per-primitive I/O schemas (future)
  doc/designs/                # 15 design documents (~12,700 lines)
  scripts/                    # build/sync/detect shell helpers
  tests/                      # pytest suite (3092+ tests, 94.76% coverage)
  .github/workflows/          # CI + Release + Pages
  .cursor/rules/              # always-on hard constraints (9 .mdc rule files)
```

## Interactive Demo

Browse the framework architecture, workflow types, and stage primitives interactively:

**[Live Demo](https://yorha-agents.github.io/DevolaFlow/)** (GitHub Pages)

| Page | What it shows |
|------|--------------|
| [Design Architecture](https://yorha-agents.github.io/DevolaFlow/design-architecture/) | Complete framework map: every skill file, design source, tier, token budget, dependency graph |
| [Workflow Visualizer](https://yorha-agents.github.io/DevolaFlow/workflow-visualizer/) | Built-in workflow types as interactive pipeline diagrams with teams, gates, and loops |
| [Benchmark Results](https://yorha-agents.github.io/DevolaFlow/benchmark-results/) | EvoBench scenario scores, baseline comparison, and trend-style visualization |
| [Stage Explorer](https://yorha-agents.github.io/DevolaFlow/stage-explorer/) | 13 stage primitives with I/O types, delegation chains, and context budgets |

Or open locally: `workflow-system/human/demo/index.html`

## Documentation

### User Guides (English)

| Doc | Description |
|-----|-------------|
| [Quick Start](workflow-system/human/en/quickstart.md) | Install, verify, and run your first workflow in 10 minutes |
| [Architecture Overview](workflow-system/human/en/architecture-overview.md) | 4-layer hierarchy, primitives, gates, context isolation |
| [Workflow Types](workflow-system/human/en/workflow-types.md) | All 22 workflow types with examples and selection guidance |
| [Agent Hierarchy Guide](workflow-system/human/en/agent-hierarchy-guide.md) | Deep dive into each layer with escalation and communication |
| [Integration Guide](workflow-system/human/en/integration-guide.md) | Per-tool setup: Cursor, Claude Code, Copilot, Codex with examples |
| [Customization Guide](workflow-system/human/en/customization-guide.md) | Create custom templates, context profiles, derived configs |
| [FAQ](workflow-system/human/en/faq.md) | Common questions about workflows, tools, gates, updates |
| [Troubleshooting](workflow-system/human/en/troubleshooting.md) | Installation, workflow, test, and benchmark issues |

### 用户指南（中文）

| 文档 | 说明 |
|------|------|
| [快速入门](workflow-system/human/zh/quickstart.md) | 10 分钟内安装、验证并运行你的第一个工作流 |
| [架构概述](workflow-system/human/zh/architecture-overview.md) | 4 层层级、原语、质量门、上下文隔离 |
| [工作流类型](workflow-system/human/zh/workflow-types.md) | 全部 22 种工作流类型，含示例和选择指南 |
| [Agent 层级指南](workflow-system/human/zh/agent-hierarchy-guide.md) | 每层详解，含升级链和通信协议 |
| [集成指南](workflow-system/human/zh/integration-guide.md) | 逐工具设置：Cursor、Claude Code、Copilot、Codex 含示例 |
| [自定义指南](workflow-system/human/zh/customization-guide.md) | 创建自定义模板、上下文配置 |
| [常见问题](workflow-system/human/zh/faq.md) | 工作流、工具、质量门、更新相关问题 |
| [故障排查](workflow-system/human/zh/troubleshooting.md) | 安装、工作流、测试和基准测试问题 |

Design Documents

| Doc | Description |
|-----|-------------|
| [Design Documents](doc/designs/) | 15 internal design specs (architecture, meta-framework, delivery, etc.) |

## Contributing

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make changes following the [repository rules](.cursor/rules/) (9 .mdc rule files)
4. Run `make all` to verify (tests, lint, templates, adapters, docs sync, drift check)
5. Update `CHANGELOG.md` if your changes are user-visible
6. Submit a Pull Request using the [PR template](.github/PULL_REQUEST_TEMPLATE.md) (never push directly to `main`)

Commit messages use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`

### Editing rules

Governance rules are sourced from `.rules/*.mdc` (5 layered files: soul, architecture, conventions, workflow,
style) and compiled to two distribution targets, `AGENTS.md` (the canonical Markdown corpus loaded by Codex /
Claude Code / KimiCode / Cline / Roo) and `.cursor/rules/repo-governance.mdc` (the MDC rendering for Cursor).
After editing any `.rules/*.mdc` source, refresh both targets with:

```bash
make compile-rules
# or directly: sync-rules
```

`make all` and `make release-preflight` invoke `compile-rules` automatically. CI runs
`tests/test_no_ghost_features.py::test_rule_surfaces_compile_only` to catch any drift between sources and
compiled outputs (hash-based, pinned in `.rules/.compile-hashes.json`). See `.rules/index.md` for the full
layer table and token-budget breakdown.

### Release Process (Maintainers)

```bash
make release-preflight                          # run all quality gates
python scripts/bump_version.py X.Y.Z --dry-run  # preview version bump
python scripts/bump_version.py X.Y.Z --tag      # bump 7 canonical sync locations + create git tag
git add -A && git commit -m "chore: bump version to X.Y.Z"
git push origin main --tags                      # triggers release workflow
```

Pushing a `v*` tag triggers the [release workflow](.github/workflows/release.yml): test → GitHub Release → Pages deploy. See [Release Workflow Design](doc/designs/design_release_workflow.md) for full details.

## License

MIT, [LICENSE](LICENSE)

---

<p align="center"><em>
"...For the Glory of Mankind."
<br>
Named for <a href="https://nierautomata.wiki.fextralife.com/Devola">Devola</a>, who never stopped watching over others, even when the world forgot her purpose.
</em></p>
