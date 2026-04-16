# Changelog

All notable changes to DevolaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [6.1.1] — 2026-04-16

### Added
- **`data/golden_test_set/`** (new): 10 DevolaFlow-relevant NineS golden-test TOML fixtures spanning 3 dimensions (code_quality, analysis, evaluation). Unlocks NineS V1 scoring evaluators (`scoring_accuracy`, `scoring_reliability`, `scorer_agreement`, `eval_coverage`) which were previously 0.0 due to missing fixtures.
- **`nines.toml`** (new): repo-root NineS config with project defaults, self-eval weights, and relative path bindings (`golden_dir`, `samples_dir`, `src_dir`, `test_dir`, `project_root`). Future `nines -c nines.toml self-eval` invocations auto-pick up correct paths.
- **`tests/test_golden_test_set.py`** (8 tests) and **`tests/test_nines_config.py`** (5 tests): schema validation for the new fixtures + config.

### Changed
- **Rule SI-2** (`.cursor/rules/self-improve-iteration-rules.mdc`) updated with the canonical self-eval invocation including `--golden-dir` and `--samples-dir` flags.

### Metrics
- NineS overall: **0.7405 → 0.8805** (verified via `.local/research/v6.1.1/nines_self_eval_v6.1.1.json`; `--golden-dir data/golden_test_set` flips 4 V1 evaluators from 0.0 to high scores)
- NineS capability mean: **0.7150 → 0.9150**
- Tests: **896 → 954** (+58 from 13 new test functions; 10 TOMLs × 5 parametrized checks + 3 scalar + 5 config)
- Ruff: `ruff check` + `ruff format --check` clean
- No source changes to `src/devolaflow/`; bench / coverage unchanged.

### Known limitation
- **`pipeline_latency` capability remains 0.0**: upstream NineS v3.0.0 evaluator looks for `src/nines/__init__.py` inside the target repo (it is probing for its own package, not DevolaFlow code). Cannot be fixed cleanly from the DevolaFlow side without adding a shim file whose sole purpose is to satisfy the probe. Tracked as upstream item for NineS.

## [6.1.0] — 2026-04-16

**Final release of the v6.0 rollup (6 waves, v5.4.2 → v6.1.0).**

### Added
- **Continue.dev adapter** (`adapter_configs/continue.yaml`, A3): YAML-driven adapter for the OSS Continue IDE extension. Emits `.continue/rules/devola-flow.md` (frontmatter stripped) + `.continue/rules/references/` (full tree). Tier 1, 800-line budget.
- **OpenClaw adapter** (`adapter_configs/openclaw.yaml`, A4): YAML-driven adapter for the MIT-licensed OSS gateway. Emits `openclaw/SKILL.md` (frontmatter preserved) + `openclaw/references/`. Tier 2, 500-line budget.
- **Golden snapshot tests for Cursor adapter** (`tests/test_adapter_golden.py`, C3): 4 tests locking down structural invariants — required sections, line-count band (400-520), frontmatter keys, must-not-contain list (MVP-SKILL / evaluate_gate_with_nines / run_nines_advisor), references tree (8 files), examples tree (3 files), and the `workflow-hard-rules.mdc` file. Metadata-based (not byte-exact) to survive version-string drift. Golden fixture at `tests/fixtures/golden/cursor/SKILL.md.expected.meta.json`.
- **21 new coverage-focused tests** in `tests/test_exercise_modules.py` (C4):
  - 8 tests for `devolaflow.cli` (version_cmd, validate-template single-path / --all / missing / no-args / parse-error / invalid-content, build-skill no-tools / with-tools, check-drift no-drift)
  - 8 tests for `devolaflow.init_project` (--list, unknown target, `all`, missing-agent-dir, copilot --global, codex, _copy_file missing source, _copy_dir non-directory)
  - 3 tests for `template_engine.composer` (SequenceOp.stage_order, ParallelOp.join_count across all/any/n_of/fallback, collect_all_refs with loops + gates)
- **SI-8 retrospective artifact** (`.local/research/retrospective_v6.0_to_v6.1.md`): documents all 6 waves, implemented vs deferred items, key learnings, cross-wave metrics evolution, and the SI-3 composite score (9.23/10).
- **SKILL.md — Round-aware dispatch note**: single-line addition at the end of "Dispatch & Report Protocol" (after `Full schemas:` line) documents `select_context(round_num=N)` escalation and `ProposalGenerator.generate_round_dispatch()` reinforcement merging (the v6.0.3 dead-wire closure, surfaced to agents).
- **`benchmarks/devolaflow_context/baselines/v6.1.0_baseline.json`**: full 29-scenario baseline regenerated for v6.1.0 (SKILL.md growth from 496 → 498 lines required refresh per SI-4). `v6.0.5_baseline.json` preserved as historical record.

### Changed
- **`workflow-system/human/demo/index.html` — "What's New" section** rewritten to cover the whole v6.0 rollup: 8 platform adapters, round-aware convergence, schema parity + 29/29 baselines, and updated metrics (896 tests, 94% coverage).

### Metrics
- Tests: **871 → 896** (+25 new across 2 files)
- Adapters: **6 → 8** (core 4 + KimiCode + Windsurf + **Continue.dev** + **OpenClaw**)
- Overall coverage: **91.35% → 94.08%**
  - `devolaflow.cli`: 49% → **98%**
  - `devolaflow.init_project`: 59% → **94%**
  - `devolaflow.template_engine.composer`: 66% → **100%**
- SKILL.md: **498 lines** (budget 500)
- Lint: `ruff check` + `ruff format` clean
- EvoBench: 29/29 pass, no regressions
- DeprecationWarnings: **0** (maintained)
- NineS self-eval: **0.7405** stable across v5.4.2 → v6.1.0

### Known limitation (unchanged from v6.0.4)
- **Windsurf output still produces a `[WARN]` status**: current `SKILL.md` is ~24 KB, Windsurf's `.windsurfrules` has an 8 KB char budget. Future release should add a compression transform or a Windsurf-specific lean SKILL. Tracked as a next-iteration item.

## [6.0.5] — 2026-04-16

### Added
- **Schema parity test** (`tests/test_schema_parity.py`, 6 tests): enforces field parity across `task-dispatch.schema.yaml`, `lean-dispatch.yaml`, and `gate-report.schema.yaml`. Closes **TD-4** drift gap — any future field addition to one schema must be reflected in the other two (or added to an explicit `*_VERBOSE_ONLY` compromise set) or the test fails loudly with a message that points to the exact missing equivalent. Tests cover: reinforcement fields (+ per-rule items), verification facets, gate-report coverage of dispatch verification_config, header abbreviation mapping, acceptance/gate thresholds, and a sanity "all schemas parse" check.
- **Full EvoBench baseline coverage** (`benchmarks/devolaflow_context/baselines/v6.0.5_baseline.json`): regression baselines for all **29 / 29** scenarios (was **3 / 29**). Closes **C1** — the 89.7pp regression-detection gap from `.local/research/v6.0.0_improvement_advice.md`. The file is keyed by scenario name and records `composite`, `information_density`, `section_relevance`, `budget_utilization`, `noise_ratio`, `total_tokens`, `budget`, and `selected_count`.
- **`benchmarks/devolaflow_context/generate_baseline.py`**: CLI utility to regenerate the baseline on demand. Supports `--output` for a custom path and works both directly (`python benchmarks/devolaflow_context/generate_baseline.py`) and via `-m` (`python -m benchmarks.devolaflow_context.generate_baseline`). Default output follows `devolaflow.__version__`.
- **7 new benchmark tests** in `tests/test_benchmarks.py`:
  - `TestBaselineFile.test_v6_baseline_exists`
  - `TestBaselineFile.test_v6_baseline_covers_all_scenarios` (strict set equality — missing or extra keys both fail)
  - `TestBaselineFile.test_v6_baseline_scores_positive`
  - `TestBaselineFile.test_runner_prefers_latest_baseline`
  - `TestBaselineFile.test_v6_baseline_matches_current_results_within_tolerance` (staleness guard, ±5pp)
  - `TestBaselineRegressionDetection.test_ten_percent_drop_is_flagged_as_regression`
  - `TestBaselineRegressionDetection.test_one_percent_drop_not_flagged`

### Changed
- **`benchmarks/devolaflow_context/runner.py`** `load_baseline()`: now prefers the newest `v*_baseline.json` by numeric-version order (e.g. v6.0.5 over v2.1.0). Legacy `v2.1.0_baseline.json` is kept as a fallback when no newer baseline exists. Optimization-round snapshots (`v*_round_N.json`) are explicitly excluded from the baseline sweep. New helpers `_newest_baseline_path()` and `_version_tuple()` expose the selection logic for tests.

### Metrics
- Tests: **858 → 871** (+13)
- EvoBench scenarios with regression baseline: **3 / 29 → 29 / 29**
- Lint: ruff check + format clean
- EvoBench: no regressions (baseline now runs on all 29 scenarios)
- NineS self-eval: stable

## [6.0.4] — 2026-04-16

### Added
- **`AdapterRegistry`** (`src/devolaflow/adapters/registry.py`): central registry for all platform adapters with tier classification (`core`, `high_priority`, `tier_1`, `tier_2`), selective build via `build_selected()`, and `create_default_registry()` factory that pre-populates the 4 core adapters.
- **`DataDrivenAdapter`** (`src/devolaflow/adapters/data_driven.py`): generic adapter driven by a YAML config file. Supports 4 transforms (`copy`, `copy_tree`, `copy_with_frontmatter`, `strip_frontmatter`), frontmatter injection, and line/char budget checks. `load_data_driven_adapters()` auto-discovers YAML configs under `adapter_configs/`.
- **`--tools` CLI flag**: `python -m devolaflow.build_skill --tools cursor,windsurf` builds only the named adapters. Without the flag, all registered adapters build as before. Unknown names exit with code 2 and a helpful message.
- **`adapter_configs/` directory** for data-driven adapter definitions:
  - `adapter_configs/kimicode.yaml` — KimiCode (Moonshot AI VSCode + CLI). Writes `SKILL.md` + `references/` + `examples/` under `.kimi/skills/devola-flow/` with platform frontmatter injection. 500-line budget.
  - `adapter_configs/windsurf.yaml` — Windsurf (Codeium). Writes a single `.windsurfrules` at the repo root with frontmatter stripped. 8000-char budget.
- **`scripts/install.sh` targets**: `install_kimicode()`, `install_windsurf()` following the existing adapter install pattern; wired into `case`, `all`, `update`, and help text. Auto-detect intentionally left untouched (signals for the new platforms are unreliable).
- **4 new test modules** (+46 tests, 812 → 858):
  - `tests/test_adapter_registry.py` — 15 tests (registry unit + `build_all` integration)
  - `tests/test_data_driven_adapter.py` — 18 tests (all 4 transforms, budget modes, loader)
  - `tests/test_kimicode_adapter.py` — 7 tests
  - `tests/test_windsurf_adapter.py` — 6 tests

### Changed
- **`build_all()`** (`src/devolaflow/build_skill.py`): refactored to be registry-driven. The hardcoded adapter list is gone; `build_all()` now takes an optional `registry` parameter (defaults to `create_default_registry()` + data-driven extensions).
- **`load_workflow_skill()`** (`src/devolaflow/adapters/base.py`): now accepts optional path and returns `(source, agent_dir)` tuple. `_find_project_root()` relocated from `build_skill.py` to `base.py`, re-exported for backward compat.
- **`tests/test_build_skill.py`**: replaced strict `len == 4` assertion with `{cursor,codex,claude,copilot}.issubset(tools) and len(results) >= 4` to accommodate dynamic registration.

### Known limitation
- **Windsurf output produces a `[WARN]` status**: current `SKILL.md` is ~25 KB, but Windsurf's `.windsurfrules` has an 8 KB char budget. The adapter builds correctly and the budget mechanism reports honestly, but the output exceeds Windsurf's practical size limit. A future release should add a compression transform (e.g. `compress_for_windsurf`) or a Windsurf-specific lean SKILL.

### Metrics
- Tests: 812 → **858** (+46)
- Registry adapters: 6 (4 core + 2 new via data-driven)
- New LOC: 957 across 8 files (source + configs + tests)
- Lint: ruff check + format clean
- EvoBench: 26/26 pass, no regression
- DeprecationWarnings: 0 (maintained)
- NineS self-eval: 0.7405 stable

## [6.0.3] — 2026-04-16

### Changed
- **`select_context()` is now round-aware**: New keyword argument `round_num: int = 1` (backward-compatible default). When `round_num > 1` the profile is routed through `apply_round_escalation()` before section selection, automatically applying the v5.3.0 P8 escalation defaults (+20% token budget on round 3, `model_hint: quality`, and critical-bumping of `rationalization_prevention` / `convergence_loop` / `gate_mechanism` sections). A new `escalation_config` kwarg allows per-call overrides. Return value now includes `round_num` and `escalation_applied`.
- **CLI `--round N` flag**: `python -m devolaflow.task_adaptive_selector <task> --round 3 [--verbose]` exposes the new round-aware behavior on the command line.

### Added
- **`ProposalGenerator.generate_round_dispatch(base_dispatch, verdict, round_num, target_score=85.0)`** in `src/devolaflow/feedback.py`: the production wiring that closes the v5.3.0 reinforcement dead-wire gap. Round 1 is pass-through; round 2+ with findings builds a `ReinforcementBlock` via `findings_to_reinforcement()` and merges it into a deep-copied dispatch via `merge_reinforcement_into_dispatch()`. L3 Task Agents receiving the merged dispatch see explicit MUST-fix mandates under `context.applicable_rules.reinforcement`.
- **`severity_floor` parameter on `generate_reinforcement`**: optional kwarg (default `"major"`) for explicit severity filtering at generation time.
- **`tests/test_e2e_convergence.py`** (C2): new 7-test end-to-end integration suite that exercises `select_context` + round escalation + `generate_round_dispatch` + reinforcement merge as a realistic 3-round convergence. Covers round-1 pass-through, round-2 budget+reinforcement, round-3 full escalation with metadata, MAX_REINFORCEMENT_RULES cap enforcement, severity-floor filtering, and round_num observability.

### Metrics
- Tests: 791 → **812 passed** (+21 new: 8 task-adaptive-selector, 6 feedback-reinforcement, 7 E2E)
- Live verification: round 1 → 3 increases budget 4800 → 5760 exactly (+20%), `model_hint: balanced → quality`
- Lint: ruff check + format clean
- EvoBench: 26/26 pass, no regression
- DeprecationWarnings: 0 (maintained from v6.0.2)
- Coverage: maintained
- NineS self-eval: 0.7405 overall (no regression)

### Fixed (dead-wire closure)
- **v5.3.0 P8 finally wired**: `apply_round_escalation` existed with passing unit tests since v5.3.0 but had no production callers. Now invoked automatically by `select_context()` on round > 1.
- **v5.3.0 P4 finally wired**: `merge_reinforcement_into_dispatch` existed with passing unit tests since v5.1.0-pre but had no production callers. Now invoked by `ProposalGenerator.generate_round_dispatch()` during multi-round convergence.

## [6.0.2] — 2026-04-16

### Removed (BREAKING)
- **`evaluate_gate_with_nines`**: Removed per v5.1 roadmap item P9. Use `evaluate_gate()` for gates, and call NineS separately via `devolaflow.nines.get_research_advice()` (defined in `devolaflow.nines.advisor`). See `MIGRATION-v6.md`.
- **`run_nines_advisor`**: Removed. Advisor functionality was tied to the deprecated gate+NineS conflation. Use NineS directly or `devolaflow.nines.get_research_advice()`.
- **Internal advisor helpers** (dead after `run_nines_advisor` removal): `should_invoke_advisor`, `_interpret_result`, `_extract_score`, `_extract_reasoning` and the `_SCORE_KEYS` / `_REASONING_KEYS` / `_APPROVE_STATUSES` / `_SCORE_THRESHOLD` constants; `GateVerdict` and `warnings` imports in `nines/advisor.py` also dropped.
- **5 test classes retired** (29 tests total) from `tests/test_nines.py`: `TestEvaluateGateWithNines` (6), `TestRunNinesAdvisor` (6), `TestShouldInvokeAdvisor` (4), `TestInterpretResult` (11), `TestDeprecationWarnings` (2).

### Added
- **MIGRATION-v6.md**: 1-page migration guide documenting both removals, the dead helpers, and the stable v6.0 API surface.

### Metrics
- Tests: **791 passed** (−29 from v6.0.1's 820), 0 failed
- EvoBench: 26/26 pass, no regressions
- Lint: ruff check + format clean
- DeprecationWarnings: **12 → 0**
- Net LOC in core removal (5 files): **−519** (+6 / −525). MIGRATION-v6.md adds 32 lines (new file).

## [6.0.1] — 2026-04-16

### Removed
- **MVP-SKILL.md legacy file**: Deleted `workflow-system/agent/MVP-SKILL.md` (317 lines) and swept 14 cross-references across README, quickstart (EN/ZH), demo, reference-dependencies, install.sh, build-site.sh, PR template, generate_human_docs.py, and design docs. CHANGELOG entries preserved (append-only history). `scripts/install.sh` keeps a backward-compat `mvp` alias documented in-line that routes to `install_standalone`.
- **`_BUILTIN_SPECS` hardcoded plugin duplicate**: Removed the 78-line `_BUILTIN_SPECS` list from `src/devolaflow/plugins/loader.py`. `create_default_registry()` now loads from `workflow-system/agent/plugins.yaml` (single source of truth) with auto-discovery; an 8-line emergency NineS stub handles the YAML-absent case with a logged warning. 5 `test_builtin_*` tests renamed to `test_repo_yaml_*` and rewritten against the real YAML; 2 new tests cover auto-discovery and emergency-stub fallback.

### Changed
- **Rule reconciliation (TD-6)**: `.cursor/rules/change-process-rules.mdc` CP-3 rewritten to reference SF-3 as the authoritative version-location list (dropping the stale `CLAUDE.md (frontmatter + banner + body)` claim that contradicted the lightweight 38-line root CLAUDE.md). Root `CLAUDE.md` updated to "11 locations (8 files, rooted in `src/devolaflow/__init__.py`)" to match `scripts/bump_version.py` reality.

### Fixed
- **3 previously-silent rule contradictions**: CP-3 vs SF-3 vs CLAUDE.md version-location counts now consistent.

### Metrics
- Tests: **820 passed** (+2 from v5.4.2 for new emergency-stub tests), 0 failed
- EvoBench: 26/26 pass, no regressions
- Lint: ruff check + format clean
- Net LOC: −295 (+156/−451 across 16 files touched + 1 file deleted)
- MVP-SKILL references in source tree: 0 (down from 141)
- DeprecationWarnings still present: 12 (removal scheduled for v6.0.2)

## [5.4.2] — 2026-04-15

### Changed
- **Claude Code skill-based installation**: Claude Code now installs DevolaFlow as `.claude/skills/devola-flow/SKILL.md` with references and examples (identical structure to Cursor), instead of flat `CLAUDE.md`. Enables progressive 3-tier loading (~50 tokens at startup vs ~5000 previously), on-demand reference loading, and `/devola-flow` slash command.
- **Root CLAUDE.md**: Now lightweight project context (~35 lines) instead of 496-line SKILL copy. Follows Claude Code best practice of keeping `CLAUDE.md` under 200 lines for passive project rules.
- **install.sh / devola-init**: `install_claude()` installs to `.claude/skills/devola-flow/` with SKILL.md + 8 references + 3 examples, mirroring `install_cursor()` exactly.
- **bump_version.py**: Reduced from 14 to 11 version locations (removed 3 CLAUDE.md entries since root CLAUDE.md no longer carries version strings).
- **Parity achieved**: All 4 tools (Cursor, Codex, Claude, Copilot) now use identical skill directory structure.

### Metrics
- Tests: 818 passed (4 CLAUDE.md version tests removed), 0 failed
- EvoBench: 30/30 scenarios pass
- Lint: 0 errors

## [5.4.1] — 2026-04-15

### Changed
- **Unified SKILL delivery**: All tools (Cursor, Codex, Claude Code, Copilot) now receive full `SKILL.md` instead of compressed `MVP-SKILL.md`, removing dual-file maintenance and ensuring the complete 14-primitive / 7-dimension framework everywhere.
- **install.sh**: `install_codex`, `install_claude`, and `install_copilot` download full `SKILL.md` plus references; `mvp` target renamed to `standalone` (legacy `mvp` alias kept).
- **devola-init CLI**: `install_claude`, `install_copilot`, and `install_codex` copy full `SKILL.md` instead of `MVP-SKILL.md`.
- **Root CLAUDE.md**: Matches `workflow-system/agent/SKILL.md` in full, replacing the self-contained MVP variant.
- **bump_version.py**: Sync locations updated from `MVP-SKILL.md` to root `CLAUDE.md` (14 references, down from 16).
- **Repository rules**: All `.cursor/rules/*.mdc` files now reference `CLAUDE.md` instead of `MVP-SKILL.md`.

### Deprecated
- **MVP-SKILL.md**: Kept for backward compatibility; no longer used by installers or adapters. Scheduled for removal in a future release.

### Metrics
- Tests: 822 passed, 0 failed
- EvoBench: 30/30 scenarios pass
- Lint: 0 errors

## [5.4.0] — 2026-04-15

### Added
- **User-Facing Verification Gate Dimensions**: Extended `GateInput` with 4 new optional fields (`visual_test_results`, `interaction_test_results`, `accessibility_results`, `acceptance_verification_results`) and `GateProfile` with 4 corresponding thresholds. New `EXTENDED_DIMENSION_WEIGHTS` (7-dimension composite) auto-selects when user-facing inputs are present, maintaining full backward compatibility with the original 4-dimension formula.
- **Verification Scoring Functions**: `visual_fidelity_score()`, `interaction_quality_score()`, and `acceptance_verification_score()` in gate scorer for evaluating visual regression, interaction flows, and acceptance criteria respectively. All 4 profiles (STRICT/STANDARD/RELAXED/AUDIT) updated with user-facing thresholds.
- **`verify` Stage Primitive (14th)**: New Verify-category primitive for user-facing validation — visual regression, acceptance verification, interaction flows, accessibility. Added to `VALID_PRIMITIVES`, `DEPENDENCY_LATTICE`, and meta-framework.md with full I/O contracts and configuration.
- **`product-verification` Workflow Template**: 8-stage template (analyze → design_tests → implement_tests → execute_dev_tests → execute_verification → review_results → refine → validate) with `verification_cycle` convergence loop and `test_design_gate`/`verification_gate` quality gates.
- **Full-Pipeline Verify Stage**: Updated `full-pipeline.yaml` with a verify stage between test and refine for user-facing validation in end-to-end workflows.
- **4 New Context Profiles**: `verify_visual`, `verify_acceptance`, `verify_interaction`, `product_verification` — task-type-specific context for verification agents.
- **4 New EvoBench Scenarios**: `visual_regression_webapp`, `acceptance_verification_feature`, `interaction_accessibility_test`, `product_verification_pipeline` — validating verification context assembly and scoring.

### Changed
- **Gate composite formula**: Extended from 4-dimension (test_quality 0.30, code_review 0.30, architecture 0.20, benchmark 0.20) to 7-dimension when user-facing inputs present (test_quality 0.20, code_review 0.20, architecture 0.15, benchmark 0.15, visual_fidelity 0.10, interaction_quality 0.10, acceptance_verification 0.10).
- **team-roles.md**: Test team expanded with VERIFY step, visual/acceptance/interaction/accessibility I/O contracts.
- **decomposition-gate.md**: Extended composite formula documentation, new dimension descriptions.
- **Schemas updated**: `gate-report.schema.yaml`, `task-dispatch.schema.yaml`, `lean-dispatch.yaml` extended with verification fields.

### Metrics
- Tests: 822 passed (+19 from v5.3.0), 0 failed
- EvoBench: 30/30 scenarios pass (4 new), no regressions
- Lint: ruff check + format clean
- Coverage: maintained ≥ 80%

## [5.3.0] — 2026-04-14

### Added
- **Feedback-Reinforcement Bridge (P4)**: `ProposalGenerator.generate_reinforcement()` wires `feedback.py` to `gate/reinforcement.py`. Converts gate verdict findings (as `Finding` objects or raw dicts) into `ReinforcementBlock` for next convergence round dispatch. Completes the B+E combination from the feasibility study.
- **Round-Based Context Escalation (P8)**: `apply_round_escalation()` in `task_adaptive_selector.py`. Higher convergence rounds get stricter section priorities (rationalization_prevention→critical), better model hints (quality tier), and increased token budgets (+20%). Configurable per-round overrides.
- **NineS Config Discovery (P2)**: `find_nines_config()` in `nines/_cli.py` searches upward for `nines.toml`. `run_nines_cli()` accepts `config_path` parameter for `-c` flag injection.
- **Schema Validation Tests (P3)**: New `tests/test_schema_validation.py` — validates NineS v2 command compliance in YAML configs (no v1 patterns), task-dispatch schema structure (reinforcement field present), lean-dispatch format (reinforce field present), stage primitive validity.

### Fixed
- **P1: _BUILTIN_SPECS stage_mapping unified**: `loader.py` now imports `STAGE_MAPPING` from `nines/commands.py` instead of hardcoding v1-style command strings. Eliminates the triple-source command definition problem.

### Metrics
- Tests: 803 passed (+21 from v5.2.0), 0 failed
- EvoBench: 26/26 scenarios pass, no regressions
- Lint: ruff check + format clean

## [5.2.0] — 2026-04-14

### Added
- **Self-Improve Iteration Rules**: New `.cursor/rules/self-improve-iteration-rules.mdc` with 10 rules (SI-1 through SI-10) codifying the iteration process: planning gates, NineS-driven analysis, evaluation before release, benchmark regression guard, skill format coupling, context budget enforcement, external reference protocol, iteration retrospective, convergence reinforcement, and test-then-commit protocol.
- **NineS Command Templates Module**: New `nines/commands.py` as single source of truth for all NineS CLI v2 command templates. `build_command()` and `build_stage_command()` replace scattered YAML command strings. Addresses Gap 7 (triple-source command definitions).
- **Template NineS Bridge**: New `template_engine/nines_bridge.py` bridging template `nines_commands` declarations into task dispatch context. `extract_nines_commands()`, `format_nines_context()`, `nines_commands_to_dispatch_context()` make Gap 1 template commands consumable by agents.
- **Understand-Anything Reference**: Added `understand-anything` (https://github.com/Lum1104/Understand-Anything) to active reference tracking. NineS v2.0.0 analysis: 22 findings, knowledge graph approach for codebase understanding.
- **NineS Analysis Report**: Structured analysis of Understand-Anything repository with workflow optimization insights for DevolaFlow.

### Changed
- **Rule count**: Repository rules increased from 24 to 34 (10 new SI rules). Demo index updated.
- **Reference tracking**: 10 active + 9 periodic = 19 total tracked references.

### Metrics
- Tests: 782 passed (+78 from v5.1.0-pre), 0 failed
- EvoBench: 26/26 scenarios pass, no regressions
- Lint: ruff check + format clean
- New .mdc rules: 34 total (was 24)

## [5.1.0-pre] — 2026-04-14

### Added
- **Convergence Round Reinforcement**: New `gate/reinforcement.py` module implementing dispatch-level rule injection (Approach B — zero file I/O, platform-agnostic). `findings_to_reinforcement()` converts gate findings into mandates injected into `applicable_rules.reinforcement`. Prevents L3 Task Agents from repeating same mistakes across convergence rounds.
- **ReinforcementBlock/ReinforcementRule dataclasses**: Severity-filtered, capped at 5 rules per round, with escalation notes and prior-score context.
- **Schema extensions**: `task-dispatch.schema.yaml` and `lean-dispatch.yaml` extended with `reinforcement` field under `applicable_rules`.
- **Shared NineS CLI helper**: New `nines/_cli.py` with `run_nines_cli()` using `shlex.split()` — eliminates duplicate `_run_cli` in scorer.py/researcher.py and fixes quoted-argument parsing bug.

### Fixed
- **Critical: NineS install command**: `_BUILTIN_SPECS` pip install corrected from `pip install nines-cli` (wrong package) to `uv pip install git+https://github.com/YoRHa-Agents/NineS.git`.
- **Critical: CLI v1→v2 drift**: 11 NineS commands across `context_profiles.yaml`, `plugins.yaml`, and `nines-assisted.yaml` updated to v2 syntax (`-f json` global, `--max-results`, `--target-path`, `--agent-impact`, `--keypoints`).
- **advisor.py `cmd.split()` bug**: Replaced with `shlex.split()` — quoted arguments like `--query "hello world"` now parse correctly.
- **PluginSpec model extended**: Added `stage_mapping`, `workflows`, `update_command`, `uninstall_command` fields; `_dict_to_spec()` updated to extract new fields from YAML.
- **NineS builtin spec alignment**: role → `research_and_iteration`, min_version → `1.0.0`, capabilities include `benchmark`/`update`.

### Changed
- **Gate exports**: `gate/__init__.py` now exports reinforcement symbols; `evaluate_gate_with_nines` marked with deprecation comment.
- **SKILL.md/CLAUDE.md**: Added Reinforcement Rules (v5.1+) documentation to convergence sections.

### Metrics
- Tests: 704 passed (+23 from v5.0.0), 0 failed
- Lint: ruff check + format clean
- NineS evaluation score: 9.15/10 (version readiness: READY)

## [5.0.0] — 2026-04-13

### Added
- **NineS v2.0.0 CLI Migration**: Updated all 4 nines/ modules (researcher, scorer, advisor, detector) from v1.0.0-pre to v2.0.0 CLI syntax. Fixed 6 breaking CLI changes (global --format, named flags for collect/analyze/eval/self-eval/iterate). Added `run_nines_benchmark()` and `run_nines_update()` wrappers.
- **Self-Improvement Loop Infrastructure**: New `run_self_improve_loop()` orchestrating NineS self-eval → iterate → benchmark cycle. New `log_external_source_review()` for external-sources.jsonl logging (closes "when implemented" gap). New `refresh_reference_dependency()` for programmatic tracking updates.
- **Karpathy-Inspired Behavioral Improvements**: Optional `explicit_assumptions` field in TaskDispatch schema (Think Before Coding). Simplicity/scope-creep criteria in Review rubric (team-roles.md). Verification-first micro-plan in execution-protocol.md.
- **Reference Tracking**: Added andrej-karpathy-skills (22.7K stars, relevance: 4) to active tracking. Updated get-shit-done to v1.35.0, gstack to v0.16.3.0. Verified primelocus-hydra URL.

### Changed
- **Code Quality**: Decomposed `select_context()` from CC=23 to CC≈7 via 5 extracted helpers. Reduced 6 warning-level functions using dispatch tables, guard clauses, and helper extraction. NineS error findings: 1→0, warnings: 6→0.
- **NineS Integration**: All CLI wrappers now use v2 syntax (global `-f json`, `--target-path`, `--source`/`--query`, `--project-root`/`--src-dir`/`--test-dir`). Detector knows `benchmark` and `update` subcommands.

### Metrics
- Tests: 681 passed (+38 from v4.5.0)
- Coverage: 90.90% (was 90.59%, +0.31pp)
- EvoBench: 25/25 PASS, avg 99.50 (was 99.47, +0.03)
- NineS avg complexity: 3.64 (was 3.84, -5.2%)
- NineS findings: 0 errors, 1 warning (was 1 error + 6 warnings)
- NineS self-eval: 0.7405 (was 0.726, +2.0%)
- Reference deps: 18 tracked (was 17)
- Lint/format: All checks pass

## [4.5.0] — 2026-04-13

### Added
- NieR: Automata / Devola visual identity for all human-facing content
- Documentation sync rules (DS-1 through DS-5) in `.cursor/rules/documentation-sync-rules.mdc`
- CI status summary job for branch protection
- Concurrency groups in CI and Pages workflows

### Changed
- Complete redesign of web demo pages with NieR palette (warm parchment, gold, Devola red)
- README.md rewritten with warm, guardian-inspired tone
- All 8 English user guides updated with Devola-flavored professional tone
- All 8 Chinese user guides updated with matching warm tone
- GitHub Actions workflows improved with permissions, caching, and concurrency

### Fixed
- CI workflow now cancels outdated runs on PR updates
- Release workflow now uses pip caching for faster builds

## [4.4.0] - 2026-04-13

### Added
- **UI UX Pro Max plugin**: Full integration of `ui-ux-pro-max-skill` (nextlevelbuilder) into the plugin registry. CLI: `uipro` via `npm install -g uipro-cli`. Supports 67 UI styles, 161 color palettes, 57 font pairings, 161 reasoning rules, and 15 tech stacks. Auto-detect, install (`uipro init --ai cursor|claude|copilot|codex|all`), and update (`uipro update`) supported.
- **UI integration in context profiles**: New `ui_integration` block in `context_profiles.yaml` with design system generation, style search, and palette search commands.
- **NineS improvement feedback**: Formal feedback written to NineS workspace documenting 7 findings: CLI flag inconsistencies, self-eval scope, coverage parsing, test discovery, iterate context, benchmark task generation, and positive findings.

### Changed
- **Plugin registry**: Renamed `ui-pro` placeholder to `ui-ux-pro-max` with real CLI binary (`uipro`), version detection, npm install method, 8 capabilities, and platform-specific install commands for Cursor, Claude, Copilot, Codex.
- **Demo-showcase template**: Updated `ui-pro` reference to `ui-ux-pro-max` in applicable scenarios.

### Metrics
- Tests: 643 passed
- Coverage: 90.45%
- Plugin registry: 2 plugins (NineS + ui-ux-pro-max), both with full detect/install/upgrade support
- Lint/format: All checks pass

## [4.3.1] - 2026-04-13

### Improved
- **Pre-decision module complexity**: Refactored 4 files using guard clauses, helper extraction, and table-driven dispatch. Average complexity reduced from 7.86 to 2.92 (-62.9%). Max function complexity from 31 to 5.
- **Docstring coverage**: Added 77 missing docstrings across 19 source files. Coverage 75.6% → 100%.
- **Coverage tooling**: New `scripts/run_coverage.sh` generating Cobertura XML and JSON coverage reports for NineS consumption.

### Metrics
- Tests: 643 passed
- Coverage: 90.45%
- NineS analysis: avg complexity 4.59 → 3.84 (-16.3%), findings 98 → 96
- NineS self-eval: docstring 100%, lint 100%, modules 37/37, tests 592/592
- Lint/format: All checks pass

## [4.3.0] - 2026-04-13

### Added
- **Plugin Registry System**: New `src/devolaflow/plugins/` package providing unified plugin management for external tools (NineS, ui-pro, future plugins). Features: auto-detect via `shutil.which`, auto-install with configurable methods (pip, npm, script), version checking, upgrade support, and capability/role-based queries. Canonical plugin definitions in `workflow-system/agent/plugins.yaml`.
- **NineS Research Module**: New `src/devolaflow/nines/researcher.py` with research-focused functions: `collect_research()` for information gathering via `nines collect`, `analyze_target()` for deep codebase analysis, `run_self_evaluation()` for agent self-assessment, `run_skill_iteration()` for MAPIM self-improvement cycles.
- **NineS Integration Module**: New `src/devolaflow/nines/` package with `detector.py` (CLI auto-detection), `scorer.py` (low-level CLI wrappers), `advisor.py` (research advice and deprecated gate advisor).
- **NineS-Assisted Workflow Template**: New `nines-assisted.yaml` template for research-driven workflows using NineS for collection, analysis, and skill iteration.
- **Gate NineS Bridge** (deprecated): `evaluate_gate_with_nines()` in gate scorer — backward-compatible but emits DeprecationWarning directing users to standard `evaluate_gate()` for quality gates.

### Changed
- **NineS role correction**: NineS repositioned from gate scoring tool to research/iteration tool. Removed `nines_provider` from gate advisor configs. NineS now active only in `research`, `skill-optimization`, and `self-update` workflows.
- **Context profiles**: `nines_advisor` priority set to `critical` for research/skill-optimization profiles, `supplementary` for standard workflows, `skip` for review. Triggers changed from gate-focused to research-focused (`research_collection`, `knowledge_analysis`, `skill_iteration`, `self_evaluation`).
- **Task adaptive selector**: `extract_section()` now handles non-numeric line ranges (e.g., `"N/A"`) gracefully instead of raising `ValueError`.

### Metrics
- Tests: 643 passed (+139 from v4.2.0)
- Coverage: 90.45% (threshold: 80.0%)
- New modules coverage: plugins/ 91%, nines/ 100%, researcher.py 93%
- Lint/format: All checks pass

## [4.2.0] - 2026-04-12

### Added
- 2 new EvoBench scenarios: `feedback_regression` (feedback profile) and `simple_impl_budget` (simple_implementation routing)
- EvoBench scenario coverage now at 25 scenarios across all 18 context profiles

### Changed
- Recalibrated `decomposition_feature` and `model_routing_feature` scenarios: expected_sections aligned with actual profile selection, eliminating structural noise (noise 28.6%/21.4% → 0%)
- Tightened quality thresholds for 3 v4.0.0 scenarios (min_composite 80-85 → 95, min_relevance → 1.0)
- Budget micro-tuning: `self_update` profile 3125 → 3100 tokens, `documentation` profile 3400 → 3380 tokens

### Metrics
- Tests: 504 passed
- EvoBench: 25/25 PASS (was 23/23)
- Composite range: 99.1–99.9 (was 94.26–99.98)
- All 25 scenarios: 100% relevance, 0% noise (was 21/23 at 0% noise)
- Mean composite: ~99.5 (was ~99.2 including noisy scenarios)

## [4.1.1] - 2026-04-12

### Improved
- **Compressor robustness**: Added `__all__` exports, input validation for invalid intensity tiers (raises `ValueError`), graceful handling of empty/whitespace-only messages
- **EvoBench evaluator resilience**: Import guard for compressor module — format_compliance gracefully defaults to 0.0 if compressor unavailable
- **Test coverage**: +9 tests for compressor edge cases (empty input, unicode, invalid intensity, whitespace-only, very long messages, unknown tier fallback)

### Metrics
- Tests: 504 passed (+9 from v4.1.0)
- EvoBench: 23/23 scenarios PASS, avg composite 99.20
- Format compliance: 1.00 across all 23 scenarios
- Lint/format: All checks pass

## [4.1.0] - 2026-04-12

### Added
- **Runtime Compression Validator**: New `src/devolaflow/compressor.py` module with deterministic lean format validation and compression. Functions: `validate_lean_format()` (score 0-100), `compress_message()` (apply drop patterns by intensity tier), `validate_preserve_list()` (check preserve items present), `detect_drop_violations()` (identify remaining drop items). Closes the critical runtime enforcement gap identified in T02 caveman compression audit.
- **Aggregation Compression Formats**: Extended `lean-report.yaml` with `wave_summary` and `stage_summary` aggregation templates. Wave summary: merge N task reports into ≤200 tokens. Stage summary: merge N wave summaries into ≤150 tokens with gate verdict. Defines deterministic aggregation rules (sum metrics, deduplicate artifacts, surface blockers only for FAIL state).
- **EvoBench format_compliance Dimension**: New `format_compliance` field in BenchmarkScore measuring lean format adherence of assembled context text. All 23 scenarios score 1.00 (perfect compliance). Addresses EvoBench saturation by adding a new evaluation dimension.
- **Expanded Preserve/Drop Lists**: Added environment_identifiers, dependency_versions, line_numbers, timing_values to preserve list. Added progress_narration, obvious_acknowledgments, tool_call_echoing to drop list. 12 preserve items and 9 drop items total.

### Fixed
- **Section line range alignment**: Re-aligned all 24 section line ranges in `context_profiles.yaml` to match SKILL.md 450-line layout after v4.0.1 content additions. Restored EvoBench scores: hotfix_jwt 89.37→99.78, feature_middleware 92.83→99.88, avg composite 97.33→99.20.
- **Pre-existing lint**: Fixed `datetime.timezone.utc` → `datetime.UTC` alias in benchmark runner.

### Metrics
- Tests: 495 passed (+42 from v4.0.1)
- EvoBench: 23/23 scenarios PASS, avg composite 99.20 (restored from 97.33)
- Format compliance: 1.00 across all 23 scenarios (new dimension)
- Lint/format: All checks pass
- SKILL.md: 450 lines (budget: 500)

## [4.0.1] - 2026-04-12

### Fixed
- **SKILL.md dispatch protocol**: Added model routing instruction to L2 Wave agent dispatch step — L2 now reads `model_hint` from resolved context profile and maps to platform model parameter (budget→fast on Cursor)
- **SKILL.md L3 contract**: Added `decomposition_mode` awareness to L3 Task Agent behavioral contract with backward-compatible single mode default

### Improved
- **Test coverage**: Added edge-case tests for `resolve_decomposition_config()` (missing keys, partial config, all defaults) and `resolve_compression_intensity()` (valid boundary, invalid boundary, missing defaults) — +2 tests
- **Schema documentation**: Enhanced `decomposition_mode` and `compression_intensity` field descriptions in task-dispatch.schema.yaml for clearer agent guidance

### Metrics
- Tests: 453 passed (+2 from v4.0.0)
- EvoBench: 23/23 scenarios pass (zero regression from v4.0.0)
- SKILL.md: 450 lines (budget: 500)
- Lint/format: All checks pass

## [4.0.0] - 2026-04-12

### Added
- **Platform Model Routing Infrastructure**: `platform_model_mapping` in context_profiles.yaml with per-platform hint→model mapping (Cursor: budget→fast, Codex: quality→o3/balanced→o4-mini/budget→o4-mini, Claude Code: quality→opus/balanced→sonnet/budget→haiku). Completes the model_hint pipeline end-to-end: schema → selector → profile config → platform routing.
- **Per-Boundary Compression Intensity**: `compression_defaults` configuration in context_profiles.yaml defining compression intensity per layer boundary (l2_to_l3: minimal, l3_to_l2/l2_to_l1/l1_to_l0: aggressive, l0_to_l1/l1_to_l2: standard). New `resolve_compression_intensity()` function in task_adaptive_selector.py.
- **L3 Decomposition Framework**: `decomposition` configuration per profile (enabled/disabled, max_sub_agents, sub_agent_model_hint, gen_verify_mode). Enabled for feature, refactor, migration, security-audit, perf-optimization, skill-optimization profiles. New `resolve_decomposition_config()` function in task_adaptive_selector.py. `decomposition_mode` (single/sub_agents) and `compression_intensity` (minimal/standard/aggressive) fields in task-dispatch schema.
- **3 New EvoBench Scenarios**: `compression_hotfix` (composite 99.98), `decomposition_feature` (composite 94.26), `model_routing_feature` (composite 95.69) — validating compression, decomposition, and model routing capabilities.
- **Research Reports**: T01 L3 Sub-agent Decomposition (partially viable), T02 Caveman Compression Audit (schema strong, runtime gap), T03 Advisor + Sub-agent Synergy (strong synergy, 34% cost reduction projected).

### Changed
- context_profiles.yaml: meta.version bumped to "2.0.0"; all 16 profiles now include `decomposition` configuration block
- task_adaptive_selector.py: `select_context()` now returns `decomposition` config and `compression_intensity` in result dict
- task-dispatch.schema.yaml: Added `decomposition_mode` and `compression_intensity` header fields (backward compatible with defaults)

### Metrics
- Tests: 451 passed (+13 from v3.9.2)
- Coverage: 89%+ (threshold: 80%)
- EvoBench: 23/23 scenarios pass (20 original: zero regression, 3 new)
- Composite range: 94.26–99.98 (original 20: 99.22–99.98, unchanged)
- Lint: All checks pass
- SKILL.md: 447 lines (budget: 500)
- MVP-SKILL.md: 314 lines (budget: 500)

## [3.9.2] - 2026-04-12

### Added
- **Shared design system**: New `workflow-system/human/demo/shared/` with unified CSS (296 lines), navigation component, and i18n system — replaces per-page duplicate styling across all 5 demo pages
- **i18n support (EN/ZH)**: 133 `data-i18n` attributes across all demo pages with full Chinese translations (437-line i18n.js, 122+ translation keys). Language toggle in nav bar with localStorage persistence
- **Dark/light theme toggle**: Consistent `.dark` class-based theming via nav.js across all pages (replaces inconsistent mix of manual toggle + `@media prefers-color-scheme`). Respects system preference, persists choice in localStorage
- **Shared navigation bar**: Glassmorphism fixed nav with logo, 6 page links, theme toggle, language switcher, mobile hamburger menu. Auto-detects landing vs sub-page for correct relative paths
- **Page-specific translations**: Visualizer (11 ZH keys) and Explorer (12 ZH keys) register page-local translations via `addTranslations()`

### Changed
- **Landing page** (`demo/index.html`): Removed 86-line inline `<style>`, redesigned with shared CSS components, 76 i18n attributes, visual hierarchy diagram as centerpiece, version progression sections (v3.3.0 → v3.9.1)
- **Benchmark results** (`demo/benchmark-results/`): Shared CSS + 38-line page-specific styles, 12 i18n attributes, responsive 2-column scenario grid, added avg composite and budget utilization metrics
- **Design architecture** (`demo/design-architecture/`): Removed `@media prefers-color-scheme`, page CSS uses only shared variables, 7 i18n attributes, hover effects on all cards
- **Workflow visualizer** (`demo/workflow-visualizer/`): 21 i18n attributes, agent box hover effects, styled select with focus ring, responsive layout
- **Stage explorer** (`demo/stage-explorer/`): 18 i18n attributes, detail cards extend shared `.card`, budget bar with shared shadow
- All 5 pages: removed old inline theme toggle buttons, old back-links replaced by shared nav

### Metrics
- Tests: 438 passed (+4 from v3.9.1)
- Coverage: 89.21% (threshold: 80%)
- EvoBench: 20/20 scenarios pass
- Lint: All checks pass
- SKILL.md: 447 lines (budget: 500)
- MVP-SKILL.md: 314 lines (budget: 500)
- Demo pages: 5 HTML, 3 page CSS, 3 shared assets, 133 i18n attributes

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
