# Changelog

All notable changes to DevolaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
