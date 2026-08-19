# Subagent Report: Tests & Benchmarks Infrastructure (v5.4.2 → v6.0.0)

**Agent ID:** 1765ebb5-f756-4aab-9ba9-bcca4bc99064  
**Date:** 2026-04-16  
**Scope:** Test suite, EvoBench coverage, quality, coverage gaps, missing test categories, baseline regression

## Executive Summary

DevolaFlow's `tests/` tree has 26 files and roughly 8K lines, with no pytest.skip/xfail/TODO markers; benchmarks are centralized in `test_benchmarks.py` (28 tests). EvoBench has 29 YAML scenarios including visual, interaction, acceptance, and product-verification task types aligned with v5.4.0-style verification. The evaluator measures section relevance, density, budget use, noise, and an auxiliary `format_compliance` that is NOT part of `composite`; stored baselines in `v2.1.0_baseline.json` cover only a SUBSET of scenarios for `compare_to_baseline`. Low coverage in `cli`, `init_project.main`, and `composer.collect_all_refs` is mostly fixable with targeted tests; `check_drift`'s failure path is integration-only. For v6.0.0, the highest leverage is full baseline/regression coverage, a minimal end-to-end workflow test, and optional golden adapter outputs plus an optional NineS golden corpus.

## 1. Test Suite Inventory

**Layout:** 26 Python modules (25 `test_*.py` + `conftest.py`).

| File | ~LOC | Category |
|------|-----:|----------|
| conftest.py | 30 | infra |
| test_benchmarks.py | 349 | benchmark |
| test_build_skill.py | 54 | integration |
| test_compressor.py | 311 | unit |
| test_doc_consistency.py | 274 | doc |
| test_exercise_modules.py | 74 | smoke |
| test_feedback.py | 467 | unit |
| test_feedback_reinforcement.py | 122 | unit |
| test_gate.py | 903 | unit/gate |
| test_init_project.py | 110 | integration |
| test_install_script.py | 92 | integration |
| test_integration.py | 130 | integration |
| test_learnings.py | 369 | unit |
| test_nines.py | 1488 | unit/integration |
| test_nines_bridge.py | 77 | integration |
| test_nines_commands.py | 157 | unit |
| test_plugins.py | 486 | unit |
| test_pre_decision.py | 571 | unit |
| test_reinforcement.py | 165 | unit |
| test_schema_validation.py | 129 | schema |
| test_schemas.py | 80 | schema |
| test_self_improve_rules.py | 86 | doc |
| test_smoke.py | 61 | smoke |
| test_task_adaptive_selector.py | 581 | unit |
| test_template_engine.py | 677 | unit |
| test_version.py | 146 | version |
| **Total** | **~7,989** | — |

**Markers:** 0 `pytest.skip`, `pytest.xfail`, `TODO`, `FIXME`, or `XXX` in `tests/`.  
`test_benchmarks.py`: 28 test methods.

## 2. EvoBench Coverage

**Scenarios:** 29 YAML files under `benchmarks/devolaflow_context/scenarios/`.

**User-facing verification (v5.4.0) — dedicated scenarios present:**
- `visual_regression_webapp.yaml` (`verify_visual`)
- `interaction_accessibility_test.yaml` (`verify_interaction`)
- `acceptance_verification_feature.yaml` (`verify_acceptance`)
- `product_verification_pipeline.yaml` (`product_verification`)

**Workflow Selection table ↔ scenarios:** All 18 table rows mapped to at least one scenario via `task_type`. No table row without a plausible scenario.

**Baselines:** `v2.1.0_baseline.json` + `v3.2.0_round_0.json` ... `v3.2.0_round_13.json`. Metrics include `composite`, `information_density`, `section_relevance`, `budget_utilization`, `noise_ratio`, `total_tokens`, `budget`, counts.

## 3. Benchmark Quality

**Evaluator dimensions** (`benchmarks/devolaflow_context/evaluator.py`):
- information_density
- section_relevance
- budget_utilization
- noise_ratio
- format_compliance (auxiliary, NOT in composite)

**Missing:** latency, agent output correctness, end-to-end workflow behavior.

**S01-T06 "−65% token reduction":** EvoBench scores density/utilization vs budget, not a standalone before/after token delta benchmark. Unit tests for drop/preserve lists exist in `tests/test_compressor.py`. **No benchmark asserts a fixed "−65% tokens vs uncompressed baseline".**

## 4. Coverage Analysis (Low Modules)

| Module | Why low | Fixability |
|--------|---------|------------|
| cli.py | Thin wrappers; only `validate_template_cmd --all` exercised (`test_exercise_modules.py:33-39`); validation failure branches rarely hit | **Fixable** — subprocess/monkeypatch tests |
| init_project.py | main() branches (--list, unknown target, default tool, all target) less covered | **Partial** — more main() tests with monkeypatch |
| template_engine/composer.py | `collect_all_refs` + some operator paths unused in tests | **Fixable** — targeted unit tests |
| check_drift.py | Depends on real repo layout + frontmatter; error paths rarely exercised | **Acceptable** for floor; fixable with temp trees |
| nines/_cli.py | Subprocess failure modes partially tested via mocks | **Mixed** — branches defensive; acceptable |

## 5. Missing Test Categories

| Type | Present? | Evidence |
|------|----------|----------|
| Property-based (Hypothesis) | **NO** | no `hypothesis` in tests/ |
| Fuzzing/randomized | **NO** | no fuzz harness |
| Load/stress | **NO** | no load tests |
| E2E workflow simulation | **Partial** | `test_integration.py:39-70` simulates gate scoring; no full multi-layer YAML dispatch loop |
| Adapter golden (byte-stable) | **NO** | `test_build_skill.py:18-53` checks budget + file existence, not hashes |

**Highest value for meta-framework:** 
1. E2E artifact-path tests (template + gate + reinforcement round-trip)
2. Golden/snapshot tests for adapter output
3. Property tests for schema/YAML invariants

## 6. Regression-Detection Quality

**`check_drift.py`:** Compares human doc frontmatter `source_version`/`source_files` to agent file frontmatter. **Scope:** documentation sync only — NOT SKILL vs code logic, NOT benchmark baselines.

**SKILL.md across adapter versions:** **NO** test compares full generated SKILL text; only line budget + build success (`test_build_skill.py`, `test_integration.py:104-110`).

## 7. Benchmark Signal-to-Noise

**Composite regression:** `compare_to_baseline` uses 5% drop threshold on `composite`.

**Baseline file used by runner:** `load_baseline` reads ONLY `v2.1.0_baseline.json`, which historically holds **only 3 scenario keys** (`hotfix_jwt`, `feature_middleware`, `full_pipeline_auth`). **Most scenarios lack stored numeric baseline for CI comparison.**

**Noise definition:** `noise_ratio = len(noise) / selected_count` where noise is unexpected section names.

**Relaxed thresholds:** 
- `decomposition_feature.yaml:28-31`: `max_noise_ratio: 0.07`
- `visual_regression_webapp.yaml:20-22`: `0.15`
- `interaction_accessibility_test.yaml:20-22`: `0.15`

**CHANGELOG (recalibration note):** Structural noise for `decomposition_feature`/`model_routing_feature` was relaxed for CI stability.

**v6 tightening opportunity:** Narrow `max_noise_ratio` where profiles are stable; expand baseline file to cover all 29 scenarios; optionally snapshot `select_context` outputs for determinism.

## 8. Golden Test Set for NineS

**Repo search:** NO `golden_test_set` / `data/golden_test_set` references.

**Should DevolaFlow provide one?** Optional but useful for enabling NineS `scoring_accuracy` > 0. Contents:
1. TaskDispatch / StatusReport YAML fixtures
2. Expected gate verdicts / dimension scores
3. Context selector expected outputs per task type
4. Compressor before/after strings with expected compliance

## v6.0.0 Test/Benchmark Candidates

| ID | Title | Type | Effort | Measurable |
|----|-------|------|:------:|------------|
| **C1** | Full EvoBench baseline coverage (all 29 scenarios) | infra/benchmark | L | Regression signal on every scenario |
| **C2** | E2E mini-workflow test (template→gate→reinforcement) | new test class | M | 1 class, 5-15 tests; catches orchestration regressions |
| **C3** | Adapter output golden/snapshot (Cursor) | new test class | M | 1 golden set; catches SKILL drift |
| **C4** | cli.validate_template + error branches | coverage fix | S | cli.py +10-20% coverage |
| C5 | composer.collect_all_refs edge cases | coverage fix | S | composer.py ≥80% |
| C6 | Hypothesis on YAML/schema round-trips | new test class | M | N properties × task types |
| **C7** | Tighten max_noise_ratio + document noise budget | benchmark | S | −noise floor on stable scenarios |
| C8 | Optional `data/golden_test_set/` for NineS | infra | M | NineS scoring_accuracy enabled |
| C9 | Include format_compliance in composite or separate gate | benchmark | L | Aligns lean-format goals with pass/fail |

### Top-5 Priority

1. **C1** — Full baseline + regression for all 29 scenarios
2. **C2** — E2E mini-workflow integration tests
3. **C3** — Adapter golden/snapshot
4. **C7** — Tighten noise thresholds where stable
5. **C4** — cli.py single-template validation paths
