# Tasks — v9.2.1-self-update-validation

The 7 self-update workflow stages as wave-level tasks. Each stage
produces a named research artefact.

## Wave 1 — Research (Stages 1-3)

### T1 — Stage 1 check-refs
Verify every NEW v9.2.0 reference resolves (SKILL.md →
agent-workspace.md / plan-mode-enforcement.md; slash commands; NEST
sub-fields; A-6 rule; example artifact seeder).
Output: `.local/research/v9.2.1_check_refs.md`

### T2 — Stage 2 research-updates (NineS deep analysis)
`nines analyze --depth deep` on 5 new PV modules. Aggregate HIGH
findings.
Output: `.local/research/v9.2.1_nines_aggregate.md` + per-module JSON

### T3 — Stage 3 decompose
Each NineS HIGH finding → validation task with explicit AC.
Output: `.local/research/v9.2.1_validation_tasks.md`

## Wave 2 — Integrate + Test (Stages 4-5)

### T4 — Stage 4 integrate
Rebuild 4 core + 5 tier-2 adapters within budget; compile-rules zero
diff; `make check-rules-drift` exit 0.
Output: `.local/research/v9.2.1_integration_report.md`

### T5 — Stage 5 test (multi-fixture E2E)
Extend `tests/test_capability_e2e.py` with 4-fixture-shape
parametrization (≤ 4 NEW test functions per W-17 budget).
Output: `.local/research/v9.2.1_e2e_report.md`

## Wave 3 — Evaluate + Release (Stages 6-7)

### T6 — Stage 6 evaluate (NineS self-eval + SI-3 composite)
`nines self-eval --baseline-version 9.2.0`. Compose NineS into SI-3.
Output: `.local/research/v9.2.1_evaluation.md` + JSON

### T7 — Stage 7 release
Bump 9.2.0 → 9.2.1 via `scripts/bump_version.py`. Write CHANGELOG
`[9.2.1]`. Author W-7 retrospective. W-19 idempotent re-archive.
Verify + archive THIS change folder.
Output: `.local/research/v9.2.1_retrospective.md` + archive folder move
