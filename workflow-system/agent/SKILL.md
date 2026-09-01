---
id: "agent/SKILL"
version: "24.1.0"
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
token_estimate: 4500
last_updated: "2026-08-26"
name: devola-flow
description: >
  Explicit invocation ONLY. Use when the user explicitly types /devola-flow
  or names devola-flow/DevolaFlow and asks for its workflow orchestration.
  Do NOT auto-activate for generic multi-file or multi-step work that does
  not name this skill.
---

> **Now Using DevolaFlow v24.1.0**

# DevolaFlow

## Version & Update
**Current version:** 24.1.0 — check only on explicit update request:
`curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py | grep '__version__'`.

Install details:
`references/troubleshooting.md` §2.17/§2.19. npm provisions matching Python;
curl `all` excludes `standalone`; curl `update` scans supported host skill copies only; runtime-dependent commands:
`devola-local-archive`, `devola-init-doctor`, `devola-version`, and
`python -m devolaflow.*`. Repair with `sync-rules` or
repository-local `make compile-rules`; copied skills are excluded.
Commands: `npx @yorha-agents/devola-flow doctor`,
`npx @yorha-agents/devola-flow update <cursor|claude|all>`,
`scripts/install.sh | bash -s update`, `pip install --upgrade`,
`sync-rules`, and `make compile-rules`.

### Session Banner Contract (v12.3.0+)
L0 emits start: `🌸 DevolaFlow vX.Y.Z active · workflow: <type> · mode: <agent|plan|grill>`;
end: `🌸 DevolaFlow vX.Y.Z complete · <rounds> rounds · <waves> waves · <tasks> tasks`;
and Task Quality Score footer: `DevolaFlow vX.Y.Z`. Banners are
operator chat output only; L1/L2 reports MUST NOT include them.
`reject_subagent_banner_emission` enforces this.

## Workspace Engagement

Before classifying, call `devolaflow.workspace_context.scan_workspace(repo_root)` and inspect:

Read latest three `.local/feedbacks/feedback_for_v*.md`, source-of-truth
`.local/memory/specs/<domain>/spec.md`, enabled memory cases, active
`.local/.agent/active/<id>/` (read `entrance.md` first), `.rules/*.mdc`,
`AGENTS.md`, and `.codegraph/codegraph.db` when present. Every active change/task
MUST materialize `entrance.md` (static router), `goal.md`,
`checklist.md`, `stage.md`, `preflight.md`, `spec.md`, `STATUS.yaml`,
`owned_files.txt`, and `evidence/`; `learnings.jsonl` is opt-in.

Scanning is read-only; auto-writes default-OFF unless `DEVOLAFLOW_AGENT_WORKSPACE=1`. See `references/agent-workspace.md`.

## Quick Action Decision

| Complexity | Signal | Action |
|---|---|---|
| Trivial | One file, <20 lines, obvious | Direct edit under P1 waiver |
| Simple | 1–3 files, clear and bounded | One L2 Task; collapsed path allowed |
| Standard | 3–10 files, multiple checks | L0 → L1 → L2 cascade |
| Complex | 10+ files or cross-cutting | Full cascade, strict preflight |

STANDARD+ requires the three-layer cascade: `cascade_requirement` returns
`CASCADE_REQUIRED`; set gate fields and traverse `L0 Project → L1 Wave → L2 Task`
(default 3 layers). SIMPLE/TRIVIAL is `CASCADE_OPTIONAL`. The S1 short
path is machine-detectable only with StatusReport
`trivial_path.declared_complexity == "TRIVIAL"`,
`is_cross_cutting == false`, and measured `diff_stats` of one file with
`insertions + deletions < 20` (zero files fails). `task_stop`/
`post_task_complete` returns stable violation codes and `upgrade_target`;
strict raises blocker/`HookViolation`, lite (`strict=False`) warns, and
non-TRIVIAL or evidence-free reports are no-ops.

## Mode Awareness

Detection priority: host Plan Mode; Cursor `plan`; user plan/design request;
Grill intent; otherwise Agent Mode.

### PLAN MODE — Draft the Contract, Do Not Execute

L0 produces `entrance.md`, `goal.md`, `checklist.md`, and `preflight.md`;
entrance is a static router/inventory, not a plan. Items include priority,
bounded verification, dependencies, owned and read-only files; no fixed DAG.
Wait for approval and signed preflight. Full contract:
`references/plan-mode-enforcement.md`. L1/L2 MUST NOT call `AskQuestion`, edit,
or implement in PLAN MODE.

### AGENT MODE — Run Checklist Rounds

L0 orchestrates and never performs delegated work. Select
`TemplateRegistry.load_seed(name)`; load only
`TemplateRegistry.load_template("change-driven")`; anchor contract/ownership;
select reverted blockers then P0→P1→P2; partition ≤7 waves and ≤5 tasks/wave;
dispatch L0→L1→parallel L2; run bounded L2
`implement→review→fix→re-review`; aggregate; gate evidence/checks/reinforcement;
iterate/checkpoint; report/archive.

L0 verifies evidence, not vibes. Composite score is a trend signal,
not item evidence.

`checklist.md` pins a `## Progress` header under its H1: an effort-weighted bar
plus `done | doing | todo | total` counts. L0 MUST re-align it on every state
change; `ChangeStore` write paths re-render it and C-9 lint fails on drift.

### GRILL MODE — Stress-Test the Contract

L0 asks one question at a time, grounded in the codebase, glossary, and ADR
ledger. Auto-writes to `CONTEXT.md`, `CONTEXT-MAP.md`, or `docs/adr/` require
explicit consent. Offer an ADR only when Hard to reverse + Surprising without
context + Real trade-off all pass. See `references/grill-mode.md`.

### PATHFINDER ROLE — Look Ahead Without Implementing

For Pathfinder/look-ahead reconnaissance, select the `pathfind` L2 task
specialization. It inspects the next wave's infrastructure shape and writes
only `pathfinder_report.md`; a separate owned task handles every repair.
Natural-language activation is classified by
`devolaflow.skills.pathfinder.classify_pathfind_intent`. See
`references/pathfinder.md`. If `harness_preflight.md` is present, `should_schedule_pathfind` automatically offers Pathfinder in the first execution wave; the operator may opt out naturally.

## Quick Start — Workflow Selection

Match intent to a registry-v3 seed; every selection calls `load_seed(<name>)`
and execution uses the sole `change-driven` runtime. Seed names remain
discoverable here: `hotfix`, `research-only`, `design-only`,
`documentation-only`, `spike-poc`, `refactoring`, `feature-enhancement`,
`full-pipeline`, `performance-optimization`, `security-audit`,
`research-design-review-refine`, `dependency-setup`, `onboarding`,
`demo-showcase`, `product-verification`, `entropy-cleanup`, `local-archive`,
`harness-construction`, `pathfinder`, `retro-digest`, `migration`,
`skill-optimization`, `self-update`, `nines-assisted`, `repo-init`,
`change-driven`, and `web-design`. Match signals compactly:
`research/compare/survey → research-only`; `design/architecture/API/schema →
design-only`; `bug/crash/urgent patch → hotfix`; `refactor/tech debt →
refactoring`; `migrate/upgrade/port → migration`; `prototype/spike/experiment →
spike-poc`; `documentation/guide → documentation-only`; `security/CVE →
security-audit`; `extend/enhance → feature-enhancement`; `greenfield/end-to-end
→ full-pipeline`; `research-led iterative design →
research-design-review-refine`; `demo/showcase/pitch → demo-showcase`;
`performance/latency/benchmark → performance-optimization`;
`dependencies/environment → dependency-setup`; `onboarding → onboarding`;
`skill/context optimization → skill-optimization`; `self-update/reference audit
→ self-update`; `UAT → product-verification`; `historical opaque-ID lookup →
nines-assisted`; `initialize → repo-init`; `explicit lifecycle → change-driven`;
`drift cleanup → entropy-cleanup`; `local archive/clustering → local-archive`;
`harness construction/evaluation → harness-construction`;
`look-ahead reconnaissance → pathfinder`; `retro-digest → retro-digest`;
`frontend/web → web-design`.
| local task archive or clustering | `local-archive` |

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

All depth modes create the canonical workspace paths:

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
background with ready/failed markers; missing CLI warns. See
`references/codegraph.md`.

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

HSC `floor.skill_delivery` covers installation; `skill_loaded` is a runtime fact,
never inferred from the arm or delivery path. If unobservable, record `null` with
status `INSUFFICIENT` and a reason.

### Rationalization Prevention

Dispatcher isolation, runtime-vs-seed order, evidence-based PASS, retry ceilings,
L1 aggregation/L0 adjudication, and L2 self-verification are mandatory; speed,
seed order, composite score, retries, done claims, and deferred tests are never
exceptions.
### Wave Coordination Modes

L1 uses the dependency/ownership map: independent items fan out; dependencies or
shared writable files are sequential; high-risk outputs use generator-verifier;
mixed work partitions, then integrates.
Pattern 3 Agent Pool remains forward-only; shared-state Teams remain
forbidden by P5. See `references/subagent-patterns.md`.

## Stage Primitives Index (Seed Provenance)

Non-executable labels: discover (`research`, `analyze`); shape (`design`,
`plan`); build (`implement`, `refine`); verify (`review`, `test`, `validate`,
`verify`); deliver (`release`, `deploy`, `monitor`); control (`gate`). Labels
define no order, team, duration, loops, or gates. See
`references/meta-framework.md`.

## Gate Mechanism

Round PASS requires valid evidence and checks for selected items, accounted
reinforcement, zero blocker findings, and no ownership/interface conflict.

Quality composite is a trend signal, not round-PASS evidence.

### Built-in Harness Truth

Harness owns cross-change analysis, self-evaluation, aggregation, model probes,
proposals, and approval/application; use
`python -m devolaflow.harness evaluate`. Missing evidence remains
`INSUFFICIENT`, never an implicit manual pass.

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
has its own evidence contract. Roles/evidence:
`references/team-roles.md`.

## Context Isolation

Each L2 starts fresh with its TaskDispatch, owned/read-only files,
relevant contracts, rules, and bounded predecessor summaries. Canonical
budget/isolation contract: `references/agent-hierarchy.md` §8.

Never leak history, sibling internals, full predecessor artifacts, unrelated
errors/scores, or deferred items. Share contracts, decisions, naming,
thresholds, and item criteria by artifact reference. See
`references/context-isolation.md`.

## Subagent Hang Prevention

Timeouts: research 2700s, implementation 1800s, test 900s, review 1200s,
hotfix 600s. L2 `AskQuestion` is forbidden; Recursive `Task` re-entry is forbidden.
Unbounded `Shell` is forbidden; every call carries `block_until_ms`.
Unbounded `WebFetch` and `WebSearch` are forbidden; require upstream `timeout`
or escalation. Internal loops require `max_iterations`.
Long tasks report progress at least every five minutes; timeout or ten minutes
without progress escalates Task → Wave → Project → Human.
Continuous progress (W-30): during any bounded wait, advance a
dependency-ready task when resources and ownership do not conflict; never poll
without new progress. After preflight is
signed, an ordinary blocker or `HUMAN_INTERVENE` pauses only its affected
item/task while independent, unaffected siblings continue. Whole-workflow
stopping is reserved for no safely runnable work, a HARD breakpoint or STOP card,
`FULL_ROLLBACK`, an ownership violation, or a destructive-policy violation.
Classify pauses as `dependency-blocked`, `finding-blocked`, or `wave conflict`.

## Dispatch & Report Protocol

TaskDispatch includes task/checklist IDs, description, predecessor summaries,
owned/read-only files, acceptance criteria, timeout, model hint, compression
intensity, and optional verification config.

L2 StatusReport includes state, progress, artifacts, item-keyed `ac_results`,
command/metric evidence, diff stats, self-check, findings, and reinforcement
closure; L1 WaveReport adds conflict results and checklist evidence proposals.
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

**Tier 2 — Domain references (load only when needed):**
`references/agent-hierarchy.md`, `references/agent-workspace.md`,
`references/artifact-quality.md`, `references/behavioral-guidelines.md`,
`references/codegraph.md`, `references/compression-pipeline.md`,
`references/context-isolation.md`, `references/decomposition-gate.md`,
`references/degraded-mode.md`, `references/domain-awareness.md`,
`references/env-flags.md`, `references/evaluator-rosetta.md`,
`references/execution-protocol.md`, `references/grill-mode.md`,
`references/harness-construction.md`, `references/host-bridges.md`,
`references/host-contract.md`, `references/human-surface.md`,
`references/impeccable.md`, `references/local-archive.md`,
`references/message-schemas.md`, `references/meta-framework.md`,
`references/pathfinder.md`, `references/plan-mode-enforcement.md`,
`references/repo-modes.md`, `references/retro-digest.md`,
`references/risk-parking.md`, `references/memory-router.md`,
`references/subagent-patterns.md`, `references/task-quality-score.md`,
`references/team-roles.md`, `references/troubleshooting.md`,
`references/wave-dispatch.md`, and `references/workspace-compact.md`.

**Tier 3 — On-demand knowledge/examples:**
`knowledge/index.md`, `knowledge/interview-protocol.md`,
`knowledge/code-rules-mapping.md`, `knowledge/principle-mapping.md`,
`knowledge/reference-dependencies.yaml`, `knowledge/runtime-plugins.yaml`,
`examples/full-pipeline-trace.md`, `examples/hotfix-trace.md`,
`examples/multi-stage-trace.md`, and `examples/convergence-loop-trace.md`.

## Task Quality Score

**L0 ONLY** — Subagents MUST NOT score; subagents MUST NOT load, score, or emit this rubric. The rubric loads on-demand from `references/task-quality-score.md` after
workflow completion when explicitly requested. Footer: `DevolaFlow vX.Y.Z`.

## Operational Learnings

Session learnings decay; promote reused learnings, pin blockers, and consolidate
from artifacts, never history.
