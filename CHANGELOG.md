# Changelog

All notable changes to DevolaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2026-04-10

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
  - Dedicated context profile with 6000-token budget
- **3 New EvoBench Scenarios**: `skill_optimization`, `design_workflow`, `refactor_tech_debt` (6 total)
- **EvoBench Round Tracking**: `--round N` and `--round-label` flags for multi-round optimization
- **Benchmark History Storage**: `benchmarks/devolaflow_context/history/optimization_history.json` with per-round results and delta tracking
- **Benchmark Results Web Page**: Interactive visualization at `demo/benchmark-results/index.html` showing per-round metrics, composite scores, and improvement tracking
- **Claude/Copilot Plan Mode**: Both adapters now include condensed plan-mode constraint stanzas
- **Workflow type counts updated to 16** across SKILL.md, MVP-SKILL.md, Claude adapter, Copilot adapter, README, demo page

### Changed
- SKILL.md Plan mode template: lightweight → rigid hierarchy-enforcing format
- Context profiles section line ranges: updated to match current SKILL.md layout
- Hotfix profile token budget: 4500 → 3500 (improves budget utilization)
- Claude adapter workflow table: 11 → 16 types
- Copilot adapter workflow list: 10 → 16 types
- Demo landing page: "11 types" → "16 types", "v3.0.0" → "v3.2.0", new benchmark results card
- Human docs (EN + ZH): workflow-types.md and customization-guide.md updated with skill-optimization workflow

### Metrics
- Tests: 309 passed (0 new failures)
- Coverage: 88.63% (threshold: 80%)
- EvoBench: 6/6 scenarios PASS, 0 regressions
- EvoBench composite improvement: +6.2 avg (+7.6%) over 2 optimization rounds
- Lint: All checks pass (ruff check + format)
- Adapters: All 4 build within budget (Cursor 363/500, Codex 352/500, Claude 67/200, Copilot 1925/4000)

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
