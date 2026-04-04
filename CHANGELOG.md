# Changelog

All notable changes to DevolaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
