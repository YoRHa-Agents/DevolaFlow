---
schema_version: 1
change_id: v9.2.1-self-update-validation
delta_target: v9.2.0-cycle-deliverables
delta_kind: lite
---

# Spec — v9.2.1-self-update-validation

## Purpose
Run the 7-stage `self-update` workflow against the v9.2.0 MINOR cycle
deliverables and ship the sustaining validation PATCH. PATCH discipline:
no new Python modules, no new env flags, no new rules, no new schema
extensions.

## ADDED Requirements (PATCH-scope)

### Requirement: Multi-fixture E2E proof
The v9.2.0 e2e contract (`tests/test_capability_e2e.py`) MUST
additionally hold across 4 fixture-repo shapes, validated via pytest
parametrization:

1. `empty`       — no `.local/`, no `.rules/`
2. `local-only`  — `.local/` present, no `.rules/`
3. `rules-only`  — `.rules/` present, no `.local/`
4. `full-stack`  — both surfaces present with active changes + memory cases

#### Scenario: scan_workspace shape-aware detection
- GIVEN a fixture repo shape S
- WHEN L0 calls `scan_workspace(repo_root)`
- THEN `has_local` / `has_agent_dir` / `has_rules` MUST match S
  AND counts MUST equal the fixture's seeded counts

### Requirement: Recursive engagement evidence
PV-07 itself MUST consume the new capability it certifies:
- opened `.local/.agent/active/v9.2.1-self-update-validation/` via
  `scaffold_change_folder` (the `/devola:propose` surface)
- authored ≥ 1 handoff envelope under
  `.local/.agent/handoff/<from>__<to>__v9.2.1-self-update-validation__<seq>.yaml`
- archived the change folder at Stage 7 to
  `.local/.agent/archive/<YYYY-MM-DD>-v9.2.1-self-update-validation/`

### Requirement: Ghost-audit refresh (W-18)
`tests/test_no_ghost_features.py` MUST gain a `test_v9_2_1_*`
lint that pins the 5 `.local/research/v9.2.1_*.md` artefacts
+ the recursive-engagement archive folder move.

## MODIFIED Requirements
None — PATCH discipline.

## REMOVED Requirements
None — PATCH discipline.
