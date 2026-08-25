---
parent: v16-checklist-rounds
schema_version: 1
authorized_at: "2026-08-24T09:30:00Z"
snapshot_round: 0
config_inherited_from: null
project_config_hash: "692ef77add6ddb7bd0019372b25af3feff73217db9fe680f3c26049f893ff5e3"
---

# Preflight

## 0. Project Configuration
### 0.1 Project
- name: DevolaFlow | decision: MANDATORY | source: "user fixture contract"
- purpose: Deterministic v16 checklist-round fixture | decision: MANDATORY | source: "user fixture contract"
- scope_keywords: [agent-workspace, checklist-rounds] | decision: DEFAULTED | source: "goal.md"
- existing_codebase: true | decision: CONFIRM | source: "repository scan"

### 0.2 Tech Stack
- primary_language: python | decision: CONFIRM | source: "pyproject.toml"
- runtime_version: "3.11+" | decision: CONFIRM | source: "pyproject.toml"
- dependency_manifest: pyproject.toml | decision: CONFIRM | source: "repository scan"

### 0.3 Repository
- mode: github | decision: CONFIRM | source: "git remote"
- default_branch: main | decision: CONFIRM | source: "git metadata"
- branching_strategy: feature | decision: CONFIRM | source: "governance rules"

### 0.4 Localization
- primary_language: en | decision: CONFIRM | source: "repository convention"
- bilingual_output: false | decision: CONFIRM | source: "user fixture contract"
- doc_language: en | decision: CONFIRM | source: "repository convention"
- code_comments_language: en | decision: DEFAULTED | source: "repository convention"

### 0.5 Platforms
- os: [linux, macos, windows] | decision: CONFIRM | source: "project support matrix"
- architectures: [x86_64, arm64] | decision: CONFIRM | source: "project support matrix"

### 0.6 Quality
- coverage_target_pct: 80 | decision: CONFIRM | source: "pyproject.toml"
- gate_profile: standard | decision: CONFIRM | source: "project configuration"
- max_rounds: 3 | decision: CONFIRM | source: "stage.md"

### 0.7 Release
- versioning: semver | decision: CONFIRM | source: "project convention"
- channels: [release] | decision: CONFIRM | source: "project configuration"

### 0.8 Workflow
- seed_mode: feature-enhancement | decision: CONFIRM | source: "change intent"
- runtime_loop: checklist_rounds | decision: DEFAULTED | source: "schema default"

## 1. Stop Cards
| ID | Category | Description | Checklist Items | Disposition |
|---|---|---|---|---|
| PF-E1 | environment_dependency | Python 3.11 and PyYAML are available for deterministic fixture parsing. | C-G1.1 | verified_pass |

## 2. Authorization Record
- PF-E1: verified_pass at 2026-08-24T09:30:00Z — "Use the verified repository toolchain for fixture validation."

## 3. Permitted Stops
1. STOP-1: A Section 1 card with disposition=reserved_stop is reached.
2. STOP-2: The two-round stagnation rule fires or max_rounds is reached.
3. STOP-3: A FULL_ROLLBACK exception reports state corruption or data loss.
4. STOP-4: The user reopens an item and the verbatim reverted reason explicitly instructs a stop.

## 4. Progress Snapshot
- Checked: 0/3 (P0: 0/1, P1: 0/1, P2: 0/1)
- Remaining stop cards: [] | Reached this round: []
- Estimated remaining rounds: 1
- Current blockers: none
