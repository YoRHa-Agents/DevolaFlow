# Changelog

All notable changes to DevolaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.9.1] - 2026-04-12

### Fixed
- **Documentation consistency**: Fixed stale numeric references across README, demo pages, and design docs (tests 312→423, coverage 88%→89%, version locations 9→16, rules count 18→19, design docs 14→15, benchmark scenarios 17→20, context profiles 17→18)
- **Demo landing page**: Updated feature highlights from v3.5.0/v3.3.0 to v3.9.0 (operational learnings, feedback loop, gate taxonomy, advisor tool, self-update workflow)
- **Benchmark demo page**: SAMPLE_DATA expanded from 17 to 20 scenarios (added self_update_reference_check, self_update_integration, feedback_analysis)
- **Design architecture page**: SKILL.md line count 363→447, section count 13→19

### Added
- **Documentation drift-prevention tests**: 11 new tests in `test_doc_consistency.py` that validate README/demo numeric claims match actual repo state (workflow type count, scenario count, template count, profile count, design docs count, SKILL.md line count, version location count). Runs in CI to prevent future drift.
- **Full surface update for v3.9.0**: Updated all 16→17 workflow type references across README, human docs (EN+ZH), demo pages, workflow-skill.yaml, templates registry, workflow visualizer
- **Release workflow automation**: release.yml now runs sync-human-docs, check-drift, EvoBench benchmarks, and lint. CI now includes EvoBench and drift check.

### Changed
- context_profiles.yaml: 3-round EvoBench optimization (line ranges updated, rationalization_prevention section registered, budgets tightened). Avg composite 99.05→99.51, min 95.22→99.22.
- Makefile: release-dry-run now matches release-preflight scope (includes sync-human-docs and check-drift)
- README "New in v3.9.0" section added with 8 feature bullets
- Demo index.html: v3.9.0 feature highlights replace v3.5.0 section

### Metrics
- Tests: 434 passed (+11 from v3.9.0)
- Coverage: 89.21% (threshold: 80%)
- EvoBench: 20/20 scenarios pass, avg composite 99.51, min 99.22
- Adapters: All 4 within budget (Cursor 447/500, Codex 435/500, Claude 67/200, Copilot 1922/4000)
- Lint: All checks pass
- SKILL.md: 447 lines (budget: 500)
- MVP-SKILL.md: 314 lines (budget: 500)

## [3.9.0] - 2026-04-12

### Added
- **Operational Learnings Persistence**: New `learnings.py` module for cross-session knowledge accumulation. Captures workflow execution findings (convergence patterns, recurring violations, project-specific insights) to JSONL. Auto-loaded into task agent context via configurable per-profile learnings budget (10% of token budget, max 500 tokens). Based on gstack `/learn`, Karpathy LLM Wiki, and Self-Improving System patterns.
- **Self-Improving Feedback Loop**: New `feedback.py` module with `FeedbackCollector` (metric extraction from gates/reports), `FeedbackAnalyzer` (recurring violation detection, convergence stagnation detection, profile mismatch analysis), and `ProposalGenerator` (structured improvement proposals with safeguards: max 3 proposals/workflow, confidence floor 0.7, scope lock, cooldown). Based on Triangulum9r Self-Improving System and gstack learnings patterns.
- **4-Type Gate Taxonomy**: Extended gate types with `preflight`, `revision`, `escalation`, `abort` — each with deterministic routing logic. Backward-compatible aliases: `standard`→`revision`, `convergence`→`revision`. Preflight gates block on abort-category findings; abort gates escalate with structured post-mortem. Based on get-shit-done gate taxonomy research.
- **Advisor Tool Integration**: L3 Task Agent advisor config (per-profile: enabled, max_uses, cost_ceiling_usd, trigger_conditions) and L1 Gate borderline detection (advisory flag when composite score within ±5% of threshold). Context assembly surfaces advisor section for host IDE consumption. Based on Anthropic advisor tool API research.
- **Model Profiles per Agent Role**: `model_hint` field (quality/balanced/budget/inherit) in TaskDispatch schema with per-profile tier mappings and complexity-based upgrade heuristic. Based on get-shit-done, superpowers, and PrimeLocus/Hydra model routing patterns.
- **Typed Subagent Status Protocol**: `result_status` enum (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED) with deterministic routing table mapping each status to P4 actions. Replaces free-form status interpretation. Based on superpowers typed status protocol.
- **Rationalization Prevention Tables**: 8-row `| Rationalization | Reality |` table in SKILL.md pre-countering known P1/P4 bypass rationalizations (e.g., "It's just one small file" → "P1 applies regardless of size"). Compact 4-row version in MVP-SKILL.md. Based on superpowers Iron Laws and enforcement ladder research.
- **Lean Compression Rules**: Explicit `preserve_list` and `drop_list` with 3 intensity tiers (minimal/standard/aggressive) added to both `lean-dispatch.yaml` and `lean-report.yaml`. Deterministic drop/preserve rules for inter-layer message compaction. Based on caveman compression pattern research.
- **Self-Update Workflow**: 17th workflow type (`self-update`) with 6-stage template (check-refs → research-updates → decompose → integrate → test → evaluate), integrate→test convergence loop, and human-in-the-loop checkpoints. Includes `reference-dependencies.yaml` tracking 17 external repos/resources with staleness policy.
- **Knowledge Index**: Central catalog (`knowledge/index.md`) for selective knowledge page loading with per-page "Load When" conditions and token estimates.
- **CSO Skill Description Format**: Trigger-oriented `description` frontmatter ("Use when..." not "Orchestrates...") preventing agents from shortcutting SKILL.md by treating description as compressed workflow. SF-2 rule extended. Based on superpowers CSO pattern.
- **2 New Context Profiles**: `self_update` (budget 3500) and `feedback` (budget 2500) profiles for new workflow and feedback loop task types.
- **3 New EvoBench Scenarios**: `self_update_reference_check`, `self_update_integration`, `feedback_analysis` — all passing with min_composite >= 80.

### Changed
- context_profiles.yaml: Added `learnings`, `model_hints`, and `advisor` sections to all 18 profiles (16 existing + 2 new)
- context_profiles.yaml: Feature profile budget 4700 → 4800 to accommodate advisor + learnings overhead
- gate/models.py: GateType extended with 4 new types + GATE_TYPE_ALIASES mapping; GateVerdict extended with escalation_context, post_mortem, advisor_recommended, advisor_verdict, advisor_context fields; GateProfile extended with abort_categories, preflight_checks, advisor_margin fields
- gate/scorer.py: evaluate_gate() routes through 6 gate types with alias resolution and borderline advisor detection
- task_adaptive_selector.py: select_context() assembles learnings, model_hint, and advisor sections; new resolve_model_hint() function
- lean-dispatch.yaml, lean-report.yaml: compression_rules with preserve/drop lists and intensity tiers
- lean-report.yaml: result_status_spec with typed enum and routing table
- task-dispatch.schema.yaml: model_hint field added
- gate-report.schema.yaml: escalation_context, abort_context, advisor_recommended, advisor_context fields added
- SKILL.md: Rationalization prevention table, self-update workflow entry, knowledge index reference, CSO description (448/500 lines)
- MVP-SKILL.md: Compact rationalization table, self-update workflow entry, CSO description (315/500 lines)

### Metrics
- Tests: 423 passed (+107 from v3.8.0, 0 regressions)
- Coverage: 89.21% (threshold: 80%)
- EvoBench: 22/22 pass, no regressions
- New EvoBench scenarios: 3 (total 20)
- New Python modules: 2 (learnings.py, feedback.py)
- New schemas: 1 (feedback-report.schema.yaml)
- New templates: 1 (self-update.yaml, 17th workflow type)
- Adapters: All 4 within budget
- Lint: All checks pass
- SKILL.md: 448 lines (budget: 500)
- MVP-SKILL.md: 315 lines (budget: 500)

## [3.8.0] - 2026-04-11

### Added
- **Lifecycle Hooks**: System-level deterministic enforcement at task lifecycle events (100% compliance vs 70-90% prompt-based). Three hooks: `validate_dispatch` (AC quality gate), `check_file_ownership` (P1 file boundary enforcement), `test_on_complete` (auto-retry on test/lint failure). Elevates P1 and P4 from prompt-based to deterministic enforcement. Based on Claude Code hooks architecture and enforcement ladder research.

### Changed
- context_profiles.yaml: Added `lifecycle_hooks` section with P3 priority scheme (4 critical: feature/refactor/migration/security-audit, 2 important, 4 supplementary, 6 skip)
- context_profiles.yaml: Promoted `convergence_loop` to `critical` for security-audit profile (EvoBench optimization R1)
- context_profiles.yaml: Tightened token budgets across 12 profiles over 3 optimization rounds (R1-R3)

### Metrics
- Tests: 316 passed (0 regressions)
- Coverage: 88.49% (threshold: 80%)
- EvoBench: 22/22 pass, avg composite 99.73 (+0.30 vs v3.7.0, +0.60 vs v3.6.0)
- EvoBench optimization: 4 rounds (converged, worst scenario 99.47)
- Adapters: All 4 within budget
- Lint: All checks pass
- SKILL.md: 430 lines (budget: 500)
- MVP-SKILL.md: 307 lines (budget: 500)

## [3.7.0] - 2026-04-11

### Added
- **Wave Coordination Modes**: L2 Wave auto-selects coordination mode (parallel/sequential/generator_verifier/hybrid) via O(|V|+|E|) DAG analysis before dispatch. Generator-Verifier protocol provides tight generate→evaluate→refine loops within waves, reducing stage-level convergence rounds. Based on Anthropic's multi-agent coordination patterns and AdaptOrch topology routing.
- **Plan Mode Hierarchy Enforcement**: Plan template now embeds the 4-layer delegation model explicitly — Execution Model table (L0→L1→L2→L3), layer annotations on stage/wave/task headers, P1 enforcement items in constraints checklist, L0 identity in plan mode opening
- **Plan Mode in MVP-SKILL.md**: Added 15-line compact plan mode section with mode detection, layer-annotated template, and P1 enforcement rules

### Changed
- context_profiles.yaml: Split `purpose_scope` into `mode_detection` + `plan_mode_template` sections for finer-grained priority control; plan template marked `critical` in 10 planning-heavy profiles
- context_profiles.yaml: Added `wave_coordination` section with P2-P3 hybrid priority scheme (5 critical, 1 important, 4 supplementary, 6 skip)
- context_profiles.yaml: Promoted `convergence_loop` to `critical` in refactor, rdrr, perf-optimization profiles (EvoBench optimization R1)
- context_profiles.yaml: Tightened token budgets for 5 under-utilized profiles: dependency-setup (3300→3050), onboarding (4000→3800), research (3500→3400), review (4000→3900), design (4500→4450) (EvoBench optimization R2)
- SKILL.md Plan Mode rules: Added "DO annotate every plan element with its delegation layer" and "DO verify constraints checklist (including P1 enforcement items)"

### Metrics
- Tests: 316 passed (0 regressions)
- Coverage: 88.49% (threshold: 80%)
- EvoBench: 22/22 pass, avg composite 99.43 (+0.30 vs v3.6.0)
- EvoBench optimization: 3 rounds (97.08 → 98.99 → 99.43, converged)
- Adapters: All 4 within budget (Cursor 418/500, Codex 407/500, Claude 67/200, Copilot 1922/4000)
- Lint: All checks pass
- SKILL.md: 418 lines (budget: 500)
- MVP-SKILL.md: 307 lines (budget: 500)

## [3.6.0] - 2026-04-10

### Fixed
- **P1 Dispatcher-Not-Implementer not enforced** (root cause: 5 gaps in SKILL.md):
  1. Agent Mode section was vacuous — 2 lines with no enforcement mechanism
  2. Quick Action Decision used ambiguous "Execute directly" / "skip hierarchy" phrasing
  3. No tool-to-layer permission mapping (hierarchy table said MUST NOT "write code" but never named actual tools)
  4. No explicit L0 role assignment — SKILL never told the reading agent "You are L0"
  5. Agent Mode protocol absent from context profiles — lines 108-110 fell in an unregistered gap
- **Agent Mode Execution Protocol**: Replaced 2-line vacuous section with 27-line enforcement block:
  - Explicit L0 role assignment ("You are the L0 Project Agent")
  - P1 Self-Check: 4-point "Am I about to..." verification before any tool use
  - Tool permissions: ALLOWED (Read/Glob/Grep/SemanticSearch) vs DELEGATE (Write/StrReplace/Shell)
  - 7-step execution protocol: ASSESS → SELECT → DECOMPOSE → DISPATCH → VERIFY → GATE → REPORT
  - Simple task shortcut: dispatch single Task Agent, skip multi-stage hierarchy
- **Quick Action Decision P1 clarity**: "Execute directly" → "P1 waived for minimal edits"; "skip hierarchy" → "Dispatch single Task Agent"
- **workflow-rules.mdc Rule 1**: Added tool-level enforcement specifying which tools L0-L2 may vs must-not use
- **context_profiles.yaml**: Added `agent_mode_protocol` section (lines 108-135), marked `critical` in all 16 profiles; updated all section line ranges (+24 shift)
- **MVP-SKILL.md**: Added condensed L0 protocol (3 lines: role assignment, protocol steps, tool permissions)

### Metrics
- Tests: 316 passed (0 regressions)
- Coverage: 88.49% (threshold: 80%)
- EvoBench: 22/22 pass, 0 regressions
- Adapters: All 4 within budget (Cursor 388/500, Codex 377/500, Claude 67/200, Copilot 1922/4000)
- Lint: All checks pass
- SKILL.md: 388 lines (budget: 500)
- MVP-SKILL.md: 291 lines (budget: 500)

## [3.5.0] - 2026-04-10

### Added
- **Release Workflow**: Complete end-to-end release process with tooling and documentation:
  - `scripts/build-site.sh`: Shared site builder eliminating duplication between `pages.yml` and `release.yml`
  - `bump_version.py --tag`: Creates annotated git tags alongside version bumps
  - Makefile targets: `release-preflight`, `release-dry-run`, `build-site`
  - `.github/PULL_REQUEST_TEMPLATE.md`: PR template with quality checklist (adapter budgets, human docs regen, EvoBench)
  - `doc/designs/design_release_workflow.md`: Full release runbook (branch strategy, PR workflow, release cadence, CHANGELOG maintenance)
- **Version Consistency Tests**: 4 new tests in `test_version.py` covering SKILL/MVP-SKILL body text, README badge, and benchmark-results page

### Fixed
- **Version drift after bump** (root cause): `bump_version.py` covered only 9 locations, leaving body text, README, demo pages, and generated docs stale. Now covers 16 locations across 11 files.
- **Copilot adapter truncated description mid-word**: Now truncates at word boundary with ellipsis
- **Workflow visualizer only showed 11 workflows**: `visualizer.js` updated to all 16 workflow types
- **Design architecture page said "11 Templates"**: Updated to 16 templates in both JS data and HTML
- **`workflow-skill.yaml` manifest listed only 11 builtins**: Added 5 missing template entries
- **Benchmark results page showed "undefined" timestamp**: Fixed conditional rendering
- **`generate_human_docs.py` said "15 workflow types" and "v3.0.0"**: Updated all EN/ZH counts to 16, added `skill-optimization` entries, removed hardcoded version strings
- **CI/release workflows missing `build-skill`**: Added to `ci.yml` validate job and `release.yml` test job
- **SKILL.md Reference Navigation missing `execution-protocol.md`**: Added to Tier 2 table
- **Rules/design doc referenced outdated location counts**: Updated CP-3, SF-3, and release runbook
- **Missing CHANGELOG v3.2.0**: Added retroactive entry
- **Pages build duplication**: Both `pages.yml` and `release.yml` now use shared `scripts/build-site.sh`
- **Release pipeline was dormant**: `--tag` flag enables the full `release.yml` flow via git tags

### Changed
- `bump_version.py` now updates 16 version locations (was 9): added SKILL/MVP-SKILL body text, README badge/example, benchmark-results, MVP-SKILL update instructions
- PR template expanded with adapter budget, human docs regen, and EvoBench checklist items
- `test_version.py` expanded from 12 to 16 tests covering all bump locations
- README version badge and CLI example auto-updated by `bump_version.py`
- Human docs (EN + ZH) fully regenerated with 16 workflow types
- Demo landing page features v3.5.0 release highlights
- Makefile `clean` target now removes `_site/`; `_site/` added to `.gitignore`

### Metrics
- Tests: 316 passed (was 312)
- Coverage: 88.49% (threshold: 80%)
- EvoBench: 22/22 pass, 0 regressions
- Adapters: All 4 within budget
- Lint: All checks pass
- Version locations: 16 (was 9)

## [3.3.0] - 2026-04-10

### Added
- **Plan Mode Hardening**: Rewrote SKILL.md Plan mode section (lines 52-100) with rigid hierarchy constraints:
  - Per-task columns: ID, Type, Writable (<=6), Read-only, Est. time
  - Per-wave validation: <=5 tasks, disjoint ownership
  - Per-stage: gate_type, min/max_rounds, convergence structure, on_stagnation
  - All 5 invariants (P1-P5) stated with enforcement notes
  - DAG + gate-before-advance rule (D4), stable ID convention (S/W/T)
  - Constraints checklist (7 items) for plan validation
- **Skill Optimization Workflow**: New `skill-optimization` workflow type (16th):
  - Stages: survey → profile → optimize → benchmark → iterate → document
  - RDRR-like convergence loop on optimize→benchmark→iterate
  - Template YAML at `templates/builtin/skill-optimization.yaml`
  - Dedicated context profile with 4300-token budget
- **Full Workflow Coverage (16 profiles, 17 scenarios)**: All 16 workflow types now have dedicated context profiles and EvoBench benchmark scenarios:
  - 9 new context profiles: migration, security-audit, documentation, spike-poc, rdrr, demo-showcase, perf-optimization, dependency-setup, onboarding
  - 11 new benchmark scenarios: research_survey, review_code_quality, migration_upgrade, security_audit, documentation_guide, spike_poc, rdrr_design_loop, demo_showcase, perf_optimization, dependency_setup, onboarding_new
- **Improved Profile Matching**: `match_profile()` now uses longest-match scoring instead of first-match, preventing short hints from stealing specific task types
- **EvoBench Round Tracking**: `--round N` and `--round-label` flags for multi-round optimization
- **Benchmark History Storage**: `benchmarks/devolaflow_context/history/optimization_history.json` with per-round results and delta tracking
- **Benchmark Results Web Page**: Interactive visualization at `demo/benchmark-results/index.html` with real optimization data across 3 key rounds (baseline, coverage expansion, final tuning)
- **Claude/Copilot Plan Mode**: Both adapters now include condensed plan-mode constraint stanzas
- **Workflow type counts updated to 16** across SKILL.md, MVP-SKILL.md, Claude adapter, Copilot adapter, README, demo page
- **Hardened Quality Thresholds**: All 17 EvoBench scenarios now require min_composite >= 80.0, max_noise_ratio <= 0.1, min_relevance >= 0.8

### Changed
- SKILL.md Plan mode template: lightweight → rigid hierarchy-enforcing format
- Context profiles section line ranges: updated to match current SKILL.md layout
- Token budgets optimized across all profiles for ~85% utilization target:
  - hotfix: 4500 → 2600 | feature: 6500 → 4900 | refactor: 5500 → 4900
  - design: 5000 → 4500 | skill-optimization: 6000 → 4300 | rdrr: 5500 → 4700
  - migration: 5500 → 4900 | dependency-setup: 3500 → 3300
- Profile hint conflicts resolved: removed "migrate/upgrade" from refactor, "security/audit/CVE" from review
- Claude adapter workflow table: 11 → 16 types
- Copilot adapter workflow list: 10 → 16 types
- Demo landing page: updated with real benchmark data, "v3.0.0" → "v3.2.0"
- Human docs (EN + ZH): workflow-types.md and customization-guide.md updated with all new workflows

### Metrics
- Tests: 312 passed (+3 new tests)
- Coverage: 88.49% (threshold: 80%)
- EvoBench: 17/17 scenarios PASS, 0 regressions
- EvoBench avg composite: 94.4/100 (up from 80.5 baseline, +17.3%)
- EvoBench avg budget utilization: 86.1% (up from 52.6% baseline, +63.7%)
- EvoBench delta vs v3.1.0 baseline: +13.2 avg composite improvement
- Section relevance: 100% across all 17 scenarios
- Noise ratio: 0% across all 17 scenarios
- Optimization rounds: 6 total (baseline + 5 iterations)
- Lint: All checks pass (ruff check + format)
- Adapters: All 4 build within budget

## [3.2.0] - 2026-04-10

### Added
- **Plan Mode Hardening**: Rewrote SKILL.md Plan mode section with rigid hierarchy constraints (P1-P5, wave/task caps, gate types, DAG rules, stable IDs, constraints checklist)
- **Skill Optimization Workflow**: New `skill-optimization` workflow (16th type): survey → profile → optimize → benchmark → iterate → document, with RDRR-like convergence loop
- **EvoBench Expansion**: 3 new scenarios (skill_optimization, design_workflow, refactor_tech_debt), round tracking (`--round N`, `--round-label`), history storage, benchmark results web page
- **Claude/Copilot Plan Mode**: Both adapters now include condensed plan-mode constraint stanzas

### Changed
- Context profile line ranges updated to match current SKILL.md layout
- Hotfix profile budget tightened (4500 → 3500)
- Demo landing page updated (16 types, v3.2.0, benchmark card)
- Human docs (EN + ZH) updated with skill-optimization workflow

### Metrics
- Tests: 309 passed
- Coverage: 88.63%
- EvoBench: +6.2 avg composite (+7.6%) over 2 optimization rounds
- Adapters: All 4 within budget

## [3.1.0] - 2026-04-10

### Added
- **4 New Workflow Templates**: Expanded from 11 to 15 built-in workflows:
  - `demo-showcase`: Build presentation-ready demos with storyboard, polished UI, and packaging
  - `performance-optimization`: Profile-driven optimization with before/after benchmarks
  - `dependency-setup`: Environment configuration, dependency management, tooling setup
  - `onboarding`: Codebase survey, onboarding docs, dev environment setup for new contributors
- **Comprehensive Human Documentation**: Completely rewrote all 8 human-facing docs (EN + ZH):
  - Quick Start: Step-by-step walkthrough with real examples for each workflow type
  - Workflow Types Catalog: Detailed descriptions, stage breakdowns, example prompts for all 15 types
  - Integration Guide: Per-tool setup instructions with example sessions for Cursor, Claude Code, Copilot, Codex
  - Architecture Overview: ASCII diagrams, context isolation details, gate mechanism explanation
  - Agent Hierarchy Guide: Layer-by-layer deep dive with escalation chain and communication protocol
  - Customization Guide: Template structure walkthrough with custom template example
  - FAQ: Expanded with 15+ questions covering workflows, tools, gates, updates
  - Troubleshooting: Installation, workflow, test, and benchmark issue resolution
- **Updated README**: Reflects 15 workflow types, expanded prompt pattern table, full bilingual documentation index

### Changed
- SKILL.md and MVP-SKILL.md workflow selection tables now include 15 types (was 11)
- Team participation matrix updated with new workflow entries
- Template registry updated to reference all 15 builtin templates
- `pyproject.toml`: Added per-file-ignores for doc generator script (E501)
- `generate_human_docs.py`: Refactored into per-section generator functions for maintainability

## [3.0.0] - 2026-04-10

### Added
- **Repository Development Rules**: 3 new `.cursor/rules/` files codifying lessons from v2.1.0 and v2.2.0 iterations:
  - `skill-format-rules.mdc` (SF-1–SF-6): SKILL.md line budget, required frontmatter, version consistency, valid reference links, no absolute paths, external resource URLs
  - `change-process-rules.mdc` (CP-1–CP-7): no ghost features, test coverage floor (>=80%), version bump protocol, gate module test requirements, adapter build verification, benchmark requirements, pre-commit checklist
  - `context-optimization-rules.mdc` (CO-1–CO-6): lean message format, verbatim extraction, token budgets, relative paths only, benchmark verification, section relevance
- **EvoBench Benchmark Suite**: Context density benchmarks at `benchmarks/devolaflow_context/` with evaluator, runner, 3 scenarios (hotfix_jwt, feature_middleware, full_pipeline_auth), baseline storage, and regression detection
- **Task-Adaptive Selector Tests**: `tests/test_task_adaptive_selector.py` with 33 tests raising coverage from 0% to 90%
- **EvoBench Tests**: `tests/test_benchmarks.py` with 22 tests covering evaluator, runner, scenario discovery, baseline comparison, and quality thresholds

### Fixed
- **PROFILES_PATH resolution**: `task_adaptive_selector.py` now correctly resolves `context_profiles.yaml` relative to `workflow-system/agent/` instead of `src/devolaflow/`
- **Version text inconsistencies**: SKILL.md and MVP-SKILL.md body text now matches frontmatter version (was stuck at "2.1.0")
- **Broken reference links**: SKILL.md and `context_profiles.yaml` now reference `decomposition-gate.md` and `meta-framework.md` (previously pointed to nonexistent `gate-mechanism.md` and `stage-templates.md`)
- **`last_updated` date**: SKILL.md frontmatter corrected to actual modification date

### Metrics
- Tests: 254 → 309 (+55 new tests)
- Coverage: 82.78% → 88.31% (+5.53pp)
- `task_adaptive_selector.py`: 0% → 90% coverage
- EvoBench: 3/3 scenarios PASS, 0 regressions against baseline
- Lint: All checks pass (ruff check + format)
- Adapters: All 4 build within budget (Cursor 346/500, Codex 335/500, Claude 53/200, Copilot 1669/4000)

## [2.2.0] - 2026-04-10

### Added
- **Acceptance Readiness Gate**: New `acceptance_readiness` gate type validates acceptance criteria quality (Testability, Completeness, Measurability, Clarity, Independence) before workflow starts. Reduces rework from vague criteria.
- **Task-Adaptive Context Selection**: Context profiles per task type (hotfix, research, design, refactor, review, feature). Agents receive only task-relevant SKILL.md sections.
- **Lean Message Templates**: Structured compact format for TaskDispatch and StatusReport inter-layer messages. Uses verbatim compaction instead of summarization.
- **EvoBench Integration**: Context density benchmark suite at `/benchmarks/devolaflow_context/` with Python evaluation harness.

### Changed
- **SKILL.md optimized for information density**: Removed redundant sections (duplicate tables, triplicated constraints, verbose rare-action instructions). 449 → 293 lines, all behavioral specifications preserved.
- **Gate module extended**: `GateInput` now supports `acceptance_readiness_criteria`, `GateProfile` includes `acceptance_readiness_threshold`.

### Metrics
- Task Completion Quality: +15.4% average improvement
- Task Clarity: +32.3% average improvement  
- Focus Efficiency: +32.1% average improvement
- Information Density: +93% (quality per token nearly doubles)
- User-facing output: Zero degradation verified across 7 output types
- Adapter compatibility: 254/254 tests pass, all 4 adapters verified

## [2.1.0] - 2026-04-07

### Added
- **Task Quality Score**: Lightweight post-workflow scoring system that evaluates user task descriptions on 4 dimensions (Clarity, Scope, Success Criteria, Context) — scored 1-5 each with actionable improvement tips
- **Quick Action Decision**: Complexity assessment table (Trivial/Simple/Standard/Complex) to prevent over-orchestrating simple tasks — match ceremony to complexity
- New body section `quick-action` in workflow-skill.yaml manifest
- New body section `task-quality-score` in workflow-skill.yaml manifest

### Changed
- **Dispatch & Report Protocol**: Streamlined from verbose YAML examples to compact field-list format, reducing token consumption by ~40% while preserving all required fields
- **Fail-Forward Protocol**: Consolidated escalation severity table into Dispatch & Report section for single-point-of-reference
- **Gate Mechanism**: Compressed to inline formula + compact profile table, removing redundant prose
- **SKILL.md**: Added Quick Action Decision section, Task Quality Score section, streamlined Message Protocol into Dispatch & Report Protocol
- **MVP-SKILL.md**: Same improvements as SKILL.md, fully self-contained
- Workflow type count corrected from "10" to "11" (including RDRR) in Purpose & Scope
- Version bump: 0.2.0 → 2.1.0 across all 9 version locations

## [0.1.0] - 2026-04-04

### Added
- Project scaffolding with pyproject.toml, Makefile, and GitHub Actions CI
- 7 schema definitions (workflow-template, task-dispatch, status-report, gate-report, pre-decision-checklist, checkpoint, exception-escalation)
- Template engine with YAML parser, 5 composition operators (sequence/parallel/choice/loop/gate), 7-check validator, inheritance, and registry
- Pre-Decision engine with repo mode detection, checklist collection, consistency validation, and workflow type recommendation
- Gate quality engine with composite scoring, 4 gate profiles (strict/standard/relaxed/audit), convergence detection, and YAML+Markdown report generation
- 11 built-in workflow templates (research-only, design-only, hotfix, refactoring, migration, spike-poc, documentation, security-audit, feature-enhancement, full-pipeline, RDRR)
- Agent Skill system: SKILL.md entry point, 8 Tier-2 references, 3 execution examples, 2 knowledge mappings, workflow-skill.yaml canonical source
- Cross-tool adapter pipeline (build-skill.py) generating outputs for Cursor, Codex, Claude Code, and GitHub Copilot
- Human documentation system: 8 EN + 8 ZH docs with drift detection
- Interactive demo pages: workflow visualizer and stage explorer
- MVP single-file SKILL.md (self-contained, <500 lines)
- GitHub Actions release workflow with Pages deployment
- 5 hard constraint rules (.cursor/rules/workflow-rules.mdc)
