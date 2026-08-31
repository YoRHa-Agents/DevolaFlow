---
id: "agent/SKILL"
version: "22.1.0"
purpose: >
  Entry point for DevolaFlow checklist-round orchestration using a three-layer
  Project → Wave → Task hierarchy, evidence-backed completion, bounded retry,
  and context-isolated task delegation.
triggers:
  - "/devola-flow"
  - "devola-flow"
  - "devolaflow"
  - "use devola"
  - "update devola"
  - "update_devola"
  - "/update-devola"
tier: 1
token_estimate: 6000
last_updated: "2026-08-26"
name: devola-flow
description: >
  Explicit invocation ONLY. Use when the user explicitly types /devola-flow
  or names devola-flow/DevolaFlow and asks for its workflow orchestration.
  Do NOT auto-activate for generic multi-file or multi-step work that does
  not name this skill.
---

> **Now Using DevolaFlow v22.1.0**

# DevolaFlow

## Version & Update
**Current version:** 22.1.0 — Check only on explicit update request:
`curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py | grep '__version__'`.

Use the channel that created the installation:

- npm/npx copied skills: `npm install -g @yorha-agents/devola-flow@<version> && devola-flow install all`
  copies skills and provisions the matching Python runtime through uv; `npx @yorha-agents/devola-flow update <cursor|claude|all>` repeats both steps;
- curl-installer copied skills:
  `curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update`
  scans supported host skill copies only;
- Python runtime: `uv tool install --force --python 3.13 'devolaflow @ git+https://github.com/YoRHa-Agents/DevolaFlow.git@v<version>'`;
  Python 3.11+ operators may use `pip install --upgrade` with the same pinned URL. runtime-dependent commands are `devola-local-archive`, `devola-init-doctor`, `devola-version`, and `python -m devolaflow.*`; see troubleshooting §2.19.

curl `all` installs all supported host targets plus `local`; it excludes
`standalone`. curl `update` does not scan local workspaces or standalone files;
rerun the explicit `local` or `standalone` install target for those surfaces.
Updating the Python package does not auto-refresh copied skills. Editable
checkout users pull the checkout and rerun the relevant `devola-init` target.
If uv bootstrap or runtime installation fails, skill files remain **docs-only** and the installer prints a copyable repair command. Workspace health is `devola-init-doctor`; copied-skill audit is
`devola-init-doctor --skills`; npm-channel parity is
`npx @yorha-agents/devola-flow doctor`. Repair rule compilation with
`sync-rules` or repository-local `make compile-rules`.
Wheel-only limits: `references/troubleshooting.md` §2.17.

### Session Banner Contract (v12.3.0+)

L0 emits:

- start: `🌸 DevolaFlow vX.Y.Z active · workflow: <type> · mode: <agent|plan|grill>`;
- end: `🌸 DevolaFlow vX.Y.Z complete · <rounds> rounds · <waves> waves · <tasks> tasks`;
- Task Quality Score footer containing `DevolaFlow vX.Y.Z`.

Banners are operator chat output only. L1/L2 reports MUST NOT include them;
`reject_subagent_banner_emission` enforces the prohibition.

## Workspace Engagement

Before classifying work, call `devolaflow.workspace_context.scan_workspace(repo_root)` and inspect:

| Surface | L0 use |
|---|---|
| `.local/feedbacks/feedback_for_v*.md` | Read latest three themes for planning |
| `.local/memory/specs/<domain>/spec.md` | Treat as source-of-truth behavior |
| `.local/memory/cases/*.md` | Consult when memory routing is enabled |
| `.local/.agent/active/<id>/` | Resume active state instead of duplicating it |
| `.local/.agent/active/<id>/entrance.md` | MUST be written in the first change/task artifact batch; read first, then only scenario-needed artifacts |
| `.rules/*.mdc` and `AGENTS.md` | Apply governance contract |
| `.codegraph/codegraph.db` | Prefer indexed planning lookup when available |
Every active change/task first-batch write MUST include `entrance.md` with `goal.md`, `checklist.md`, `stage.md`, `preflight.md`, `spec.md`, `STATUS.yaml`, `owned_files.txt`, and `evidence/`; `learnings.jsonl` remains opt-in.
`entrance.md` is a required write artifact, not only a read surface.

Scanning is always read-only. Workspace auto-writes remain default-OFF unless `DEVOLAFLOW_AGENT_WORKSPACE=1`. See `references/agent-workspace.md`.

## Quick Action Decision

| Complexity | Signal | Action |
|---|---|---|
| Trivial | One file, <20 lines, obvious | Direct edit under P1 waiver |
| Simple | 1–3 files, clear and bounded | One L2 Task; collapsed path allowed |
| Standard | 3–10 files, multiple checks | L0 → L1 → L2 cascade |
| Complex | 10+ files or cross-cutting | Full cascade, strict preflight |

STANDARD+ requires the three-layer cascade. For STANDARD/COMPLEX,
`cascade_requirement` returns `CASCADE_REQUIRED`; set the gate fields and traverse
L0 Project → L1 Wave → L2 Task (default 3 layers). SIMPLE/TRIVIAL is
`CASCADE_OPTIONAL`.
The S1 short path is machine-detectable only when StatusReport execution metadata has `trivial_path.declared_complexity == "TRIVIAL"` and `trivial_path.is_cross_cutting == false`, while measured `diff_stats` has `files == 1` and `insertions + deletions < 20`; zero files fails. The canonical `task_stop`/`post_task_complete` chain returns stable violation codes plus `upgrade_target`; strict mode raises blocker/`HookViolation`, lite (`strict=False`) warns, and non-TRIVIAL or declaration/evidence-free reports remain no-ops.

## Mode Awareness

Detection priority:

1. host says Plan Mode is active;
2. Cursor current mode is `plan`;
3. user asks to plan/design first;
4. grill intent activates Grill Mode alongside the current mode;
5. otherwise Agent Mode.

### PLAN MODE — Draft the Contract, Do Not Execute

L0 produces `goal.md`, `checklist.md`, and `preflight.md` drafts. Every
checklist item includes P0/P1/P2 priority, bounded verification,
item-level dependencies, owned files, and read-only files. There is no fixed
workflow DAG. Execution waits for user approval and signed preflight. Full
template: `references/plan-mode-enforcement.md`. L1/L2 MUST NOT call
`AskQuestion`, edit files, or begin implementation in PLAN MODE.

### AGENT MODE — Run Checklist Rounds

L0 orchestrates and never performs delegated task work.

Execution protocol:

1. **ASSESS** complexity and active-change state.
2. **SELECT SEED** from intent with `TemplateRegistry.load_seed(name)`.
3. **LOAD RUNTIME** only with `TemplateRegistry.load_template("change-driven")`.
4. **ANCHOR** goal, checklist, preflight, priorities, and ownership with user.
5. **SELECT ROUND**: reverted blockers → P0 → P1 → P2 → stable order.
6. **PARTITION** into ≤7 waves/round and ≤5 tasks/wave.
7. **DISPATCH** L0 → L1 Wave → parallel L2 Tasks.
8. **INTRA-TASK CONVERGENCE** — L2 runs bounded
   `implement → review → fix → re-review` loops with `max_iterations`, then
   reports evidence.
9. **AGGREGATE** L1 checks conflicts and submits item-level evidence proposals.
10. **GATE** L0 verifies evidence/checks, zero blockers, and reinforcement closure.
11. **ITERATE** with bounded reinforcement or checkpoint a passing round.
12. **REPORT** progress, decisions, archive result, and Task Quality Score.

L0 verifies evidence, not vibes. Composite score is round trend only; it does
not replace item evidence.

`checklist.md` pins a `## Progress` header under its H1: an effort-weighted bar
plus `done | doing | todo | total` counts. L0 MUST re-align it on every state
change; `ChangeStore` write paths re-render it and C-9 lint fails on drift.

### GRILL MODE — Stress-Test the Contract

L0 asks one question at a time, grounded in the codebase, glossary, and ADR
ledger. Auto-writes to `CONTEXT.md`, `CONTEXT-MAP.md`, or `docs/adr/` require
explicit consent. Offer an ADR only when Hard to reverse + Surprising without
context + Real trade-off all pass. See `references/grill-mode.md`.

### PATHFINDER ROLE — Look Ahead Without Implementing

When the operator requests a Pathfinder or look-ahead reconnaissance, select
the `pathfind` L2 task specialization. It inspects the next wave's
infrastructure shape and writes only `pathfinder_report.md`; a separate
owned task handles every repair. Natural-language activation is classified by
`devolaflow.skills.pathfinder.classify_pathfind_intent`. See
`references/pathfinder.md`. If `harness_preflight.md` is present, `should_schedule_pathfind` automatically offers Pathfinder in the first execution wave; the operator may opt out naturally.

## Quick Start — Workflow Selection

Match intent to a registry-v3 checklist seed. Every row uses
`load_seed(<name>)`; execution always uses the sole `change-driven` runtime.

| Intent | Checklist seed |
|---|---|
| research, compare, survey | `research-only` |
| design, architecture, API/schema | `design-only` |
| bug, crash, urgent patch | `hotfix` |
| refactor, tech debt | `refactoring` |
| migrate, upgrade, port | `migration` |
| prototype, spike, experiment | `spike-poc` |
| documentation, guide | `documentation-only` |
| security, CVE, vulnerability | `security-audit` |
| extend or enhance feature | `feature-enhancement` |
| greenfield or end-to-end build | `full-pipeline` |
| research-led iterative design | `research-design-review-refine` |
| demo, showcase, pitch | `demo-showcase` |
| performance, latency, benchmark | `performance-optimization` |
| dependencies, environment setup | `dependency-setup` |
| contributor onboarding | `onboarding` |
| skill/context optimization | `skill-optimization` |
| self-update or reference audit | `self-update` |
| user-facing verification/UAT | `product-verification` |
| historical compatibility lookup (opaque ID only) | `nines-assisted` |
| initialize repository workspace | `repo-init` |
| change lifecycle explicitly | `change-driven` |
| stale docs or drift cleanup | `entropy-cleanup` |
| local task archive or clustering | `local-archive` |
| harness construction, evaluation infrastructure, observation coverage | `harness-construction` |
| look-ahead infrastructure or harness reconnaissance | `pathfinder` |
| retrospective digest, cycle learning, loop-improve | `retro-digest` |
| frontend/web design | `web-design` |

Seeds are non-executable decomposition knowledge. `source_stages` retain
historical provenance only; order does not imply execution order. Details:
`references/meta-framework.md`.
`nines-assisted` is an opaque historical seed ID, not an external evaluator or
plugin recommendation. New evaluation work uses `skill-optimization` and the
built-in harness.

### Repo-Init Pre-Dispatch Contract

Run the **Working-tree sanity check (v12.3.0 PV-04)** first:
`git status --short` plus `git diff --stat HEAD`. Record the baseline, preserve
pre-existing user changes, and stop when write ownership is uncertain.

#### Canonical manifest

All depth modes create the canonical paths:

| # | Path |
|---:|---|
| 1 | `.local/feedbacks/` |
| 2 | `.local/tasks/` |
| 3 | `.local/memory/` |
| 4 | `.local/index.md` |
| 5 | `.rules/compile-config.yaml` |
| 6 | `.local/.agent/active/` |
| 7 | `.local/.agent/handoff/` |
| 8 | `.local/.agent/archive/` |

L0 verifies the L2 scaffold task owns all eight paths. Missing or extra
ownership fails `pre_dispatch` as blocker `VOF001`. Mode selects depth, not
files. Post-init workspace health: `devola-init-doctor`; installed copies:
`devola-init-doctor --skills`.

The repo-init seed marks codegraph suggest-tier; indexing runs in the
background with explicit ready/failed markers. A missing CLI is a non-blocking
warning. See `references/codegraph.md`.

## 3-Layer Agent Hierarchy

Entry-point summary; normative shared contract:
`references/agent-hierarchy.md` §§2, 6–8. L2 role profiles/evidence:
`references/team-roles.md`.

| Layer | Context | Responsibilities | MUST NOT |
|---|---:|---|---|
| **L0 Project** | ~5K | Goal/checklist/preflight; round selection; wave plan; gates; reinforcement; reporting | Perform delegated task work |
| **L1 Wave** | ~5K | Dispatch ≤5 parallel tasks; detect conflicts; aggregate evidence | Implement, edit Task output, mark checklist |
| **L2 Task** | ~8K | Implement one atomic task; self-verify; report evidence | Spawn agents, self-score, exceed ownership |
Shared constraints: escalation is **Task → Wave → Project → Human**; waves allow
≤5 tasks and rounds ≤7 waves with pairwise-disjoint writable ownership.

### Host Dispatch Vocabulary

Native delegation follows the HSC: Cursor/Claude Code/Codex/KimiCode use
`Task`; DSH uses `subagent`; Copilot is `undeclared`. Host syntax maps to
L0 → L1 → L2 without bypassing ownership or cascade checks.

### Skill Residency Observation

HSC `floor.skill_delivery` declares installation delivery only; `skill_loaded` is a runtime fact, never inferred from the skill-on arm or delivery path.
If unobservable, record `null` with status `INSUFFICIENT` and an explicit reason.
### Rationalization Prevention

| Rationalization | Reality |
|---|---|
| "I can implement this faster as L0/L1" | Dispatcher isolation is the contract |
| "The seed says this step comes next" | Seed order is provenance, not runtime |
| "The composite is high enough" | Round PASS needs evidence, checks, zero blockers |
| "One more retry" | Respect the declared ceiling |
| "The Task says done" | L1 aggregates; L0 adjudicates |
| "Tests can come later" | L2 self-verifies before reporting |
### Wave Coordination Modes

L1 chooses from the current dependency and ownership map:

| Shape | Mode |
|---|---|
| Independent items | parallel fan-out |
| Item dependency/shared writable file | sequential waves |
| High-risk producer output | generator-verifier |
| Mixed | independent partitions then integration |
Pattern 3 Agent Pool remains forward-only; shared-state Teams remain forbidden
by P5. See `references/subagent-patterns.md`.
## Stage Primitives Index (Seed Provenance)

These 14 historical labels preserve seed provenance; they are not executable:

| Category | Primitives |
|---|---|
| Discover | research, analyze |
| Shape | design, plan |
| Build | implement, refine |
| Verify | review, test, validate, verify |
| Deliver | release, deploy, monitor |
| Control | gate |

They do not define order, team, duration, loops, or gates. See
`references/meta-framework.md`.

## Gate Mechanism

Round PASS requires all selected checklist items to have valid evidence and
passing configured checks, all reinforcement accounted for, zero blocker
findings, and no unresolved ownership/interface conflict.

Existing quality composite remains a recorded trend signal. It is not a
round-PASS condition.

### Built-in Harness Truth

Cross-change analysis and self-evaluation use
`python -m devolaflow.harness evaluate`; aggregation, bounded model probes,
proposal generation, and explicit approval/application live in the same
`devolaflow.harness` domain. Missing evidence remains `INSUFFICIENT`, never an
implicit manual pass. The historical NineS compatibility package was removed
in v17.0.0.

When evidence is supplied, `evaluate_gate(artifact_evidence=...)` adds the
profile's `artifact_evidence_weight` dimension: `0.05` in
STRICT/STANDARD/AUDIT and `0.0` in RELAXED. Absence is a no-op.

Archive requires:

1. every checklist item checked;
2. no reverted item open;
3. valid evidence references and signed preflight;
4. mergeability checks pass;
5. readiness composite ≥8.5 for lite/minor or ≥9.0 for full/major.

### Reinforcement Rules

On round FAIL, L0 injects up to five blocker/critical/major findings into
`applicable_rules.reinforcement`. User-reverted items become blocker
reinforcement with the reason preserved verbatim. L2 closes reinforcement
before new work; L1 verifies closure evidence. See
`references/plan-mode-enforcement.md`.

## AgentTeam Quick Reference

Teams are L2 task specializations, not hierarchy layers. Select from Research,
Design, Implement, Test, Pathfind, Review, Preflight, or HarnessBuild; each role
has its own evidence contract. Full role profiles and evidence requirements:
`references/team-roles.md`.

## Context Isolation

Each L2 Task starts fresh with only its TaskDispatch, owned/read-only files,
relevant contracts, rules, and bounded predecessor summaries. The canonical
budget and isolation contract is `references/agent-hierarchy.md` §8.

Never leak conversation history, sibling internals, full predecessor artifacts,
unrelated errors/scores, or deferred items. Share interface contracts, decisions,
naming, thresholds, and item acceptance criteria by artifact reference. See
`references/context-isolation.md`.

## Subagent Hang Prevention

Set task-type timeouts: research 2700s, implementation 1800s, test 900s, review
1200s, hotfix 600s. L2 `AskQuestion` is forbidden because agents below L0 have
no direct human channel; Recursive `Task` re-entry is forbidden because no
child-agent spawning.
Unbounded `Shell` is forbidden; every call carries `block_until_ms` for bounded
Shell execution. Unbounded `WebFetch` and `WebSearch` are forbidden; require an
upstream `timeout` or escalation. Internal loops require `max_iterations`.
Long tasks report progress at least every five minutes; timeout or ten minutes
without progress escalates Task → Wave → Project → Human.

## Dispatch & Report Protocol

TaskDispatch includes task/checklist IDs, description, predecessor artifact
summaries, owned/read-only files, acceptance criteria, timeout, model hint,
compression intensity, and optional verification config.

L2 StatusReport includes state, progress, artifacts, item-keyed `ac_results`,
command/metric evidence, diff stats, self-check, findings, and reinforcement
closure. L1 WaveReport adds conflict results and checklist evidence proposals.
Subagents DO NOT include `quality_score`; L2 emits falsifiable evidence, not a
numeric score; L0 alone supplies it to `evaluate_gate(artifact_evidence=...)`.

All inter-layer messages use typed YAML. Paths are repository-relative.

## Lifecycle Hooks

Strict engaged-runtime hooks:

| Hook | Event | Check |
|---|---|---|
| `validate_dispatch` | pre-dispatch | AC and schema |
| `check_file_ownership` | file write | path is owned |
| `test_on_complete` | task stop | evidence/tests/lint |

Every round dispatch runs `pre_dispatch` → `post_dispatch` per S-10. Default
handlers preserve bytes when no extension is active.

## Repo Mode Detection

| Mode | Signal | Capability |
|---|---|---|
| local | no git/remote | local build/test |
| github | GitHub remote | Actions, PR, release |
| other-git | other remote | platform-native CI/MR |

Override with `repo_mode` in `.workflow/config.yaml`. See
`references/repo-modes.md`.

## Reference Navigation Guide

**Tier 2 — Domain references**:

| File | Load when |
|---|---|
| `references/agent-hierarchy.md` | Layer responsibilities and evidence flow |
| `references/agent-workspace.md` | Change folders and archive |
| `references/artifact-quality.md` | L2 self-verification evidence |
| `references/behavioral-guidelines.md` | Task behavior primitives |
| `references/codegraph.md` | Indexed code exploration |
| `references/compression-pipeline.md` | Dispatch compression |
| `references/context-isolation.md` | Context budgets and leak prevention |
| `references/decomposition-gate.md` | Round/wave/task and gates |
| `references/degraded-mode.md` | Upstream capability fallback |
| `references/domain-awareness.md` | Glossary and ADRs |
| `references/env-flags.md` | Runtime flag inventory |
| `references/evaluator-rosetta.md` | Evaluation cross-walk |
| `references/execution-protocol.md` | Task lifecycle and checkpoints |
| `references/grill-mode.md` | Plan stress-testing |
| `references/harness-construction.md` | Harness gap preflight and capability review |
| `references/host-bridges.md` | wiring host-agent tool events (Cursor/Claude/Codex/Kimi/DSH hooks) into boundary enforcement, or configuring DEVOLAFLOW_HOST_ENFORCE |
| `references/host-contract.md` | checking host support tiers, delivery floor, and evidence-backed capability declarations |
| `references/human-surface.md` | Human input/output contracts |
| `references/impeccable.md` | Design refinement checks |
| `references/local-archive.md` | Explicit local-task inventory, approved non-deletion moves, and archive mapping |
| `references/message-schemas.md` | Typed dispatch/report fields |
| `references/meta-framework.md` | Registry v3 and seeds |
| `references/pathfinder.md` | selecting the Pathfinder L2 role or look-ahead harness reconnaissance |
| `references/plan-mode-enforcement.md` | Three-draft Plan Mode contract |
| `references/repo-modes.md` | Repository capability detection |
| `references/retro-digest.md` | Running the approved loop-improve retrospective digest workflow |
| `references/memory-router.md` | Planning-time memory-case routing |
| `references/subagent-patterns.md` | Wave dispatch patterns |
| `references/task-quality-score.md` | Workflow-close L0 rubric |
| `references/team-roles.md` | L2 task specializations |
| `references/troubleshooting.md` | Failure diagnostics |
| `references/wave-dispatch.md` | L1 Wave async dispatch boundary |

**Tier 3 — On-demand knowledge and examples**

| File | Load when |
|---|---|
| `knowledge/index.md` | Discovering the knowledge catalog |
| `knowledge/interview-protocol.md` | Running a bounded interview |
| `knowledge/code-rules-mapping.md` | Mapping rules across tools |
| `knowledge/principle-mapping.md` | Tracing principles to checks |
| `knowledge/reference-dependencies.yaml` | Resolving reference dependencies |
| `knowledge/runtime-plugins.yaml` | Resolving plugin capabilities |
| `examples/full-pipeline-trace.md` | Inspecting a full trace |
| `examples/hotfix-trace.md` | Inspecting a hotfix trace |
| `examples/multi-stage-trace.md` | Inspecting historical provenance |
| `examples/convergence-loop-trace.md` | Inspecting convergence evidence |

## Task Quality Score

**L0 ONLY** — Subagents MUST NOT score; L1/L2 subagents MUST NOT load, score, or emit this rubric. The full
rubric loads on-demand from `references/task-quality-score.md` only after
workflow completion and only when the user explicitly asks to score the
original request. The footer includes `DevolaFlow vX.Y.Z`.

## Operational Learnings

Session learnings decay by confidence, promote when reused, and may be pinned for one session; reserve pinning for blockers.
Consolidation and decay operate on artifact state, never hidden conversation history.
