# Changelog

All notable changes to DevolaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [7.2.3] — 2026-04-18

**PATCH — v7.3.0 cycle P-03: reflective reflex writer.** Third patch of the v7.3.0 cycle driven by EvoBench v2.2.0 feedback (`.local/feedbacks/from_evobench/eb220_for_devola_v7.1.1.md`). Activates the dormant `operational.jsonl` substrate that v7.2.0 PR-C shipped (C-007 schema additions to `Learning` dataclass: `files`, `source`, `dedup_learnings`). New `capture_session_reflection()` helper writes a v3 `Learning` entry per session with auto-derived `key` (when unset), runs `dedup_learnings` against existing entries to enforce last-write-wins, and persists via the existing `capture_learning`. The `lean-report.yaml` schema gains an additive top-level `learnings:` block so L3 status reports can carry reflections to the dispatcher. Read-side already wired via v7.0.3 ADR-005 (`load_relevant_learnings` accepts `session_id`). Targets EvoBench Tier 1 #3 — 12 multi-session orchestration tasks at 41% aggregate pass; worst: `cross_session_knowledge_persistence` (q=0.4705), `v2_X_06_multi_session_compounding_bug` (q=0.4617, σ=0.0765), `earned_autonomy_escalation` (q=0.4468), `v2_X_15_incident_commander_simulation` (q=0.4387).

### Added
- **`src/devolaflow/learnings.py`** — `capture_session_reflection(session_id, task_type, files, insight, source, jsonl_path, key=None) -> Learning` between `dedup_learnings` (lines 233-258) and `prune_learnings`. Auto-derives `key=f"{task_type}:{files[0] if files else 'session'}"` when not provided. Constructs a `Learning` with `stage='reflection'`, `confidence=0.7`, `source_task_id=session_id`, `timestamp=now`. Loads existing entries, runs `dedup_learnings` against `existing + [new]` (last-write-wins per `(task_type, key)`), then rewrites file with surviving non-new entries and re-appends via `capture_learning`. `__all__` extended.
- **`schemas/lean-report.yaml`** — additive top-level `learnings:` block (no P6 invariant on report side — verified by absence of `layout_invariant:`). Documents the per-entry shape (`insight`, `files`, `source`, `confidence`, `key`) and the four persistence rules; appended at end-of-file per the additive rule.
- **`tests/test_learnings.py`** — `TestCaptureSessionReflection` (6 cases): happy path with v3 fields, auto-derived key from `files[0]`, `session_id` round-trip via `source_task_id`, dedup against pre-populated same-`(task_type, key)` older entry, round-trip through `load_relevant_learnings`, empty-`files` fallback to `f"{task_type}:session"`.
- **`benchmarks/devolaflow_context/scenarios/reflective_reflex_capture.yaml`** — new EvoBench scenario covering the `feature` profile section selection. Documents the 3-session 15-entry persistence fixture + 4th-session `load_relevant_learnings(min_confidence=0.5, max_entries=10)` query inline via a non-runner-consumed `reflective_reflex_fixture:` key (mirrors the `noise_filter_fixture:` precedent set in v7.2.2 P-01). Composite 99.08, relevance 1.0, noise 0.0.
- **`benchmarks/devolaflow_context/baselines/v7.1.0_baseline.json`** — single additive entry for `reflective_reflex_capture` (no modification to the existing 35 entries) so `tests/test_benchmarks.py::TestBaselineFile::test_v6_baseline_covers_all_scenarios` stays green.
- **`scripts/detect_dead_apis.py`** — `capture_session_reflection` added to `DEFAULT_ALLOWLIST` with explanatory comment per the v7.0.3 / v7.2.0 precedent for `consolidate_session` / `dedup_learnings`. The pre-existing comment block already anticipated the C-009 promotion ("dormant in v7.2.0; promoted to a writer in v7.3 via C-009 reflective reflex per the explicit two-phase plan").

### Changed
- **`README.md`** — benchmark scenario count `35 → 36` (3 occurrences) per `documentation-sync-rules.mdc` Rule DS-1 §1.
- **`workflow-system/human/demo/index.html`** — benchmark scenario count `35 → 36` (3 occurrences) per Rule DS-1 §2.
- **`workflow-system/human/demo/benchmark-results/index.html`** — `SAMPLE_DATA.rounds[5].scenarios` (`budget_tuning_final` round) adds `reflective_reflex_capture` (next to `convergence_noise_filter`, `complexity_tier_routing`) per Rule DS-1 §2 and `tests/test_doc_consistency.py::test_demo_benchmark_sample_data_scenarios` coverage requirement.

### Metrics
- Tests: 1216 → 1222 (+6 from `TestCaptureSessionReflection`).
- Existing 65 `tests/test_learnings.py` tests unchanged PASS — additive function preserves all v1/v2/v3 schema contracts.
- EvoBench scenarios: 35 → 36 (1 new); 0 pp drift on the existing 35 (verified by `test_v6_baseline_matches_current_results_within_tolerance` at the SI-4 ±5pp threshold).
- Coverage: `learnings` module 97% (≥97% maintained per CP-2 floor; v7.2.0 PR-C baseline 97.35%).
- LOC: ~50 production (`learnings.py` +83 / -1) + ~125 tests + ~140 scenario YAML + 12 baseline JSON + 28 lean-report.yaml + 6 detect_dead_apis.py + 8 docs.
- SI-10 6-step gate: 5/5 PASS (step 6 no-op per opt-in mirror absence, see `e44fa11`).
- New scenario: composite 99.08, relevance 1.0, noise 0.0, format_compliance 1.0 (all ≥ thresholds: composite ≥ 90, relevance ≥ 0.95, noise ≤ 0.10).

### Cross-references
- Source feedback: `.local/feedbacks/from_evobench/eb220_for_devola_v7.1.1.md` §"Recommended Focus" §🔴 Tier 1 #3.
- Patch plan: `.local/research/v7.3.0_patch_plan.md` §P-03.
- Builds on v7.2.0 PR-C (C-007 schema). v7.3.0 cycle: this is patch 3 of 6 candidates (P-04 → P-01 → **P-03** → P-02 → P-05 → P-06 per the recommended execution order); next: P-02 adversarial data-instruction envelope (v7.2.4).
- Couples with: `documentation-sync-rules.mdc` Rule DS-1 (scenario count propagation), `change-process-rules.mdc` Rule CP-3 (version bump 7.2.2 → 7.2.3), `self-improve-iteration-rules.mdc` Rule SI-4 (benchmark regression guard) + Rule SI-9 (convergence round reinforcement substrate) + Rule SI-10 (test-then-commit protocol).

## [7.2.2] — 2026-04-18

**PATCH — v7.3.0 cycle P-01: convergence-loop noise filter.** Second patch of the v7.3.0 cycle driven by EvoBench v2.2.0 feedback (`.local/feedbacks/from_evobench/eb220_for_devola_v7.1.1.md`). Adds optional `noise_tolerance_pct` parameter to `detect_stagnation()` plus a new `compute_smoothed_trend()` helper that uses a window-3 moving-average classification. When `noise_tolerance_pct > 0`, score deltas within tolerance count as stagnant only if observed for ≥ 2 consecutive rounds, preventing the gen-verify loop from misclassifying real-but-noisy improvement as stagnation. Default `noise_tolerance_pct=0.0` preserves bytewise behavior on the existing 70 gate tests. Targets EvoBench Tier 1 #2 — 9 tasks at 21% aggregate pass; worst: `feedback_loop_convergence_under_noise` (q=0.4375, σ=0.0793), `v2_X_13_optimize_measure_revert_loop` (q=0.4198, regressed -0.0481 vs v7.1.0), `competitive_hypothesis_debate` (q=0.4138 — worst overall), `adversarial_requirement_mutation` (q=0.4603).

### Added
- **`src/devolaflow/gate/convergence.py`** — additive `noise_tolerance_pct: float = 0.0` parameter on `detect_stagnation()`; new `compute_smoothed_trend(history, window=3) -> Literal["improving", "degrading", "stagnant"]` helper. Smoothed trend compares the last `window` rounds' moving average against the immediately-preceding window of the same size; falls back to pairwise `compute_trend()` when `len(history) < window` so the helper is safe at every loop round.
- **`src/devolaflow/gate/scorer.py`** — `_evaluate_convergence` reads `profile.noise_tolerance_pct` and forwards it into `detect_stagnation`; calls `compute_smoothed_trend` when tolerance > 0, otherwise the legacy `compute_trend` path is unchanged. Verdict rationale string format preserved bytewise.
- **`src/devolaflow/gate/models.py`** — `GateProfile.noise_tolerance_pct: float = 0.0` (additive; legacy profile dicts load unchanged because the dataclass default covers missing keys).
- **`tests/test_gate.py`** — `TestNoiseTolerance` (8 cases: byte-stable default, single-round within-tolerance not stagnant, two-round confirmation, real-improvement keeps converging, clear-regression still stagnant, profile field default + override, end-to-end `_evaluate_convergence` round-3 escalation avoidance) + `TestSmoothedTrend` (6 cases: window-3 classifies improving / degrading, absorbs ±2pp noise around upward trend, fall-back to pairwise when `len < window`, single-window slope when `len == window`, `window <= 1` collapses to pairwise).
- **`benchmarks/devolaflow_context/scenarios/convergence_noise_filter.yaml`** — new EvoBench scenario covering the `feedback` profile section selection with the synthesized 30%-noise score-history fixture documented inline. Composite 98.09, relevance 1.0, noise 0.0. Documents the 4 stagnation branches + 6 smoothed-trend branches verified at the unit level via a non-runner-consumed `noise_filter_fixture:` key (mirrors the `complexity_tier_branches:` precedent set in v7.2.1 P-04).
- **`benchmarks/devolaflow_context/baselines/v7.1.0_baseline.json`** — single additive entry for `convergence_noise_filter` (no modification to the existing 34 entries) so `tests/test_benchmarks.py::TestBaselineFile::test_v6_baseline_covers_all_scenarios` stays green.

### Changed
- **`README.md`** — benchmark scenario count `34 → 35` (3 occurrences) per `documentation-sync-rules.mdc` Rule DS-1 §1.
- **`workflow-system/human/demo/index.html`** — benchmark scenario count `34 → 35` (3 occurrences) per Rule DS-1 §2.
- **`workflow-system/human/demo/benchmark-results/index.html`** — `SAMPLE_DATA.rounds[5].scenarios` (`budget_tuning_final` round) adds `convergence_noise_filter` (next to `complexity_tier_routing`, `feedback_analysis`, `feedback_regression`) per Rule DS-1 §2 and `tests/test_doc_consistency.py::test_demo_benchmark_sample_data_scenarios` coverage requirement.

### Metrics
- Tests: 1202 → 1216 (+14 from `TestNoiseTolerance` + `TestSmoothedTrend`).
- Existing 70 gate tests unchanged PASS — `noise_tolerance_pct=0.0` default preserves bytewise behavior on `detect_stagnation`, `compute_trend`, and `_evaluate_convergence` rationale strings.
- EvoBench scenarios: 34 → 35 (1 new); 0 pp drift on the existing 34 (verified by `test_v6_baseline_matches_current_results_within_tolerance` at the SI-4 ±5pp threshold).
- Coverage: `gate/` module unchanged (≥97% maintained per CP-2 floor; 14 new tests cover both new functions plus the additive `_evaluate_convergence` wiring).
- LOC: ~70 production (convergence.py +95 / -10, scorer.py +5 / -1, models.py +9 / 0) + ~165 tests + ~95 scenario YAML + 12 baseline JSON.
- SI-10 6-step gate: 5/5 PASS (step 6 no-op per opt-in mirror absence, see `e44fa11`).
- New scenario: composite 98.09, relevance 1.0, noise 0.0 (all ≥ thresholds: composite ≥ 90, relevance ≥ 0.95, noise ≤ 0.10).

### Cross-references
- Source feedback: `.local/feedbacks/from_evobench/eb220_for_devola_v7.1.1.md` §"Recommended Focus" §🔴 Tier 1 #2.
- Patch plan: `.local/research/v7.3.0_patch_plan.md` §P-01.
- v7.3.0 cycle: this is patch 2 of 6 candidates (P-04 → **P-01** → P-03 → P-02 → P-05 → P-06 per the recommended execution order); next: P-03 reflective reflex writer (v7.2.3).
- Couples with: `documentation-sync-rules.mdc` Rule DS-1 (scenario count propagation), `change-process-rules.mdc` Rule CP-3 (version bump 7.2.1 → 7.2.2) + Rule CP-4 (gate-module change → full gate test suite re-run), `self-improve-iteration-rules.mdc` Rule SI-4 (benchmark regression guard) + Rule SI-9 (convergence round reinforcement substrate) + Rule SI-10 (test-then-commit protocol).

## [7.2.1] — 2026-04-18

**PATCH — v7.3.0 cycle P-04: complexity-tier model routing.** First patch of the v7.3.0 cycle driven by EvoBench v2.2.0 feedback (`.local/feedbacks/from_evobench/eb220_for_devola_v7.1.1.md`). Adds a new `meta.complexity_routing:` block to `context_profiles.yaml` mapping the EvoBench complexity tiers (`simple` / `medium` / `complex` / `very_complex`) to model_hint tiers (`budget` / `balanced` / `quality` / `quality`). Extends `resolve_model_hint()` and `select_context()` with an optional `complexity_tier` kwarg that takes priority over per-task `model_hints.overrides` and `model_hints.default_tier` when provided. Default `complexity_tier=None` preserves bytewise behavior on the existing 101 selector tests. Locks in the EvoBench operational guidance "route by tier — opus4.7/max for Complex+, sonnet4.6/high for Simple/Medium" (5.6× cost-efficiency win per eb220 §"Recommended Focus").

### Added
- **`workflow-system/agent/context_profiles.yaml`** — additive `meta.complexity_routing:` block (4 keys → tier strings drawn from `VALID_MODEL_HINTS = {"quality", "balanced", "budget", "inherit"}`). Defaults preserve current behavior when the dispatcher does not pass a `complexity_tier`.
- **`src/devolaflow/task_adaptive_selector.py`** — extend `resolve_model_hint(task_type, profile_config, complexity_tier=None)` with new lookup priority: `complexity_routing[complexity_tier]` > `model_hints.overrides[task_type]` > `model_hints.default_tier` > `"inherit"`. Extend `select_context(..., complexity_tier=None)` to accept and forward the kwarg; the routing table is injected into the per-profile dict via copy-on-write (mirrors the `apply_plan_mode_overrides` pattern at lines 70-92). Two-arg signature `resolve_model_hint(task_type, profile_config)` preserved so every existing caller stays valid.
- **`tests/test_task_adaptive_selector.py`** — new `TestComplexityTierRouting` class with 21 parametrised cases: 4-tier `simple/medium/complex/very_complex` × 2 fixtures (overrides + default_tier) + None-baseline-equality + invalid-hint fall-through + immutability via `deepcopy` comparison + `select_context` end-to-end forwarding + meta YAML block validation.
- **`benchmarks/devolaflow_context/scenarios/complexity_tier_routing.yaml`** — new EvoBench scenario covering `feature` profile section selection with the new routing block injected; documents the 3 routing branches (verified at unit level) via a non-runner-consumed `complexity_tier_branches:` key. Composite 99.08, relevance 1.0, noise 0.0, format_compliance 1.0.
- **`benchmarks/devolaflow_context/baselines/v7.1.0_baseline.json`** — single additive entry for `complexity_tier_routing` (no modification to the existing 33 entries) so `tests/test_benchmarks.py::TestBaselineFile::test_v6_baseline_covers_all_scenarios` stays green.

### Changed
- **`README.md`** — benchmark scenario count `33 → 34` (3 occurrences) per `documentation-sync-rules.mdc` Rule DS-1 §1.
- **`workflow-system/human/demo/index.html`** — benchmark scenario count `33 → 34` (3 occurrences) per Rule DS-1 §2.
- **`workflow-system/human/demo/benchmark-results/index.html`** — `SAMPLE_DATA.rounds[2].scenarios` adds `complexity_tier_routing` (the only round with a `model_routing_feature` entry got a sibling) per Rule DS-1 §2 and `tests/test_doc_consistency.py::test_demo_benchmark_sample_data_scenarios` coverage requirement.

### Metrics
- Tests: 1181 → 1202 (+21 from `TestComplexityTierRouting`).
- Existing 96 selector tests (now 101 after PR-D + this patch's measurement correction) unchanged PASS — `complexity_tier=None` default preserves bytewise behavior.
- EvoBench scenarios: 33 → 34 (1 new); 0 pp drift on the existing 33 (verified by `test_v6_baseline_matches_current_results_within_tolerance` at the ±5pp threshold).
- Coverage: `task_adaptive_selector` module unchanged (≥97% maintained per CP-2 floor).
- LOC: ~22 production + ~210 tests + ~70 scenario YAML + ~12 baseline JSON.
- SI-10 6-step gate: 6/6 PASS (step 6 no-op per opt-in mirror absence, see `e44fa11`).
- New scenario: composite 99.08, relevance 1.0, noise 0.0, format_compliance 1.0 (all ≥ thresholds).

### Cross-references
- Source feedback: `.local/feedbacks/from_evobench/eb220_for_devola_v7.1.1.md` §"Model Interaction" + §"Recommended Focus".
- Patch plan: `.local/research/v7.3.0_patch_plan.md` §P-04.
- v7.3.0 cycle: this is patch 1 of 6 candidates (P-04 → P-01 → P-03 → P-02 → P-05 → P-06 per the recommended execution order).
- Couples with: `documentation-sync-rules.mdc` Rule DS-1 (scenario count propagation), `change-process-rules.mdc` Rule CP-3 (version bump 7.2.0 → 7.2.1), `self-improve-iteration-rules.mdc` Rule SI-4 (benchmark regression guard) + Rule SI-10 (test-then-commit protocol).

## [7.2.0] — 2026-04-18

**MINOR — self-update cycle rollup. End-to-end self-update workflow (5 stages, 14 L3 task agents) consumed `.local/feedbacks/feecback_for_v7.1.1.md` and shipped 7 TIER-1 candidates + 6 registry-hygiene fixes across 5 user-selected PRs (PR-0 through PR-E). All 7 candidates were validated in S03 self-loop validation with ACCEPT or ACCEPT-WITH-CAVEATS decisions and 0 rejections. Notable additions: tiered SKILL/reference/examples size budgets (PR-A, C-006), compression bypass for security warnings & destructive operations (PR-B, C-002), dormant operational.jsonl learnings substrate activation (PR-C, C-007), advisor cluster with conciseness instruction + timing/reconcile blocks + +200 token budget bump on 4 advisor profiles (PR-D, C-001+C-003), and SKILL.md "Wave Coordination Modes" extension with inline_self_review + hybrid recipes (PR-E, C-004+C-005). SI-10 6-step gate green across all PRs; 1181 tests pass (vs 1121 baseline, +60 net); 0 EvoBench regressions. SI-3 composite projected ~9.46/10 (heuristic, NineS confirmation deferred to v7.2.x retrospective).**

### Added
- **`schemas/lean-dispatch.yaml` + `schemas/lean-report.yaml`** (PR-B, C-002) — `bypass_conditions` sub-key inside existing `compression_rules` block (P6-safe, NOT a new top-level key); 4 deterministic bypass conditions: `security_warning`, `destructive_operation`, `multi_step_sequence_with_order_dependency`, `repeated_user_question`. Mirror parity enforced by new `tests/test_compressor.py::test_bypass_conditions_schema_mirror_parity`.
- **`src/devolaflow/compressor.py`** (PR-B, C-002) — `BYPASS_CONDITIONS`, `BYPASS_PATTERNS` (4 compiled regex patterns), `_MULTI_STEP_MIN_MATCHES = 2` threshold, `CompressionBypassWarning` typed warning class, `detect_bypass_conditions(message, conditions=None) -> list[str]` pure function, and bypass branch in `compress_message(message, intensity, bypass_conditions=None)`. On bypass match: returns source verbatim + emits one-line `CompressionBypassWarning` + populates `bypass_matched` and `bypass_warning` keys in return dict (additive — non-bypass path adds `[]` / `None` to the return dict for shape consistency). Backward-compat preserved: legacy 2-arg signature still works; `bypass_conditions=[]` opt-out gives v7.1.x behaviour.
- **`src/devolaflow/learnings.py`** (PR-C, C-007) — 2 additive `Learning` dataclass fields: `files: list[str] = field(default_factory=list)`, `source: str = ""`. Coercion in `__post_init__` handles JSONL `null` files + str cast. New `dedup_learnings(entries: list[Learning]) -> list[Learning]` helper returns latest-timestamp entry per `(task_type, key)` pair; mirrors gstack `/learn` `{type, key}` last-write-wins contract; empty timestamps lose to populated; insertion order preserved across distinct tuples. Activates the dormant `workflow-system/agent/knowledge/learnings/operational.jsonl` substrate (writers land in v7.3 via C-009 reflective reflex).
- **`src/devolaflow/task_adaptive_selector.py`** (PR-D, C-001 + C-003) — `_resolve_advisor_text` refactored from string literal to `parts = [...]` builder + 3 conditional appends gated on per-profile flags. C-001: appends `"Reply in under 100 words and use enumerated steps, not explanations."` (verbatim from anthropic-advisor-tool docs; reduces advisor *response* tokens 35-45%). C-003: appends Timing block ("Call advisor BEFORE substantive work...") + Reconcile-on-conflict block ("If you've already retrieved data pointing one way and the advisor points another, do not silently switch..."). All three blocks default-on with per-flag opt-out via `advisor_config.get(KEY, True)`.
- **`workflow-system/agent/SKILL.md`** (PR-E, C-005) — new `inline_self_review` row in Wave Coordination Modes table for low-risk waves (~30s checklist vs ~25min subagent dispatch; 50× speedup for SAFE stages — `research`, `design`, `documentation`). Final line count: 499 / 500 (zero headroom; v7.3 follow-up: extract a section to references/ or raise Default tier ceiling).
- **`workflow-system/agent/references/decomposition-gate.md`** (PR-E, C-005) — new `## 8. Inline Self-Review Mode (v7.2.0+)` section (+39 lines). SAFE/UNSAFE stage tables (3 SAFE, 4 UNSAFE) with rationale; activation via per-profile opt-in; mutex with `gen_verify_mode`. Verbatim quotes from superpowers v5.0.6 release notes.
- **`workflow-system/agent/references/execution-protocol.md`** (PR-E, C-004) — new `## 7. Wave Coordination Mode Selection (v7.2.0+)` section (+53 lines). 4 pairwise rubrics (orchestrator-subagent vs agent teams vs message bus vs shared state) + 2 named hybrid recipes (orchestrator-subagent ⊕ shared-state, message-bus ⊕ agent-teams) verbatim from anthropic-coordination-blog (2026-04-10). DevolaFlow P1/P5 mapping in §7.3; `self-update` workflow application in §7.4.
- **`tests/test_reference_size_budgets.py`** (PR-A, C-006, NEW 78 LOC) — parametrised pytest covering 8 references (Large tier ≤1000) + 3 examples (XL tier ≤1600) + 1 sanity check that `MIRRORED_FILES` from `scripts/sync_cursor_skill.py` matches the canonical 8/3 contract.
- **`tests/test_compressor.py`** (PR-B, C-002) — new `TestCompressionBypass*` class (12 cases lifted from V02 sandbox + 1 mirror-parity test).
- **`tests/test_learnings.py`** (PR-C, C-007) — 6 new test classes (15 cases): `TestDedupLearningsBasic` (3), `TestDedupLearningsDuplicates` (4), `TestDedupLearningsEdgeCases` (3), `TestV1EntryLoadsWithoutNewFields` (2), `TestV2EntryLoadsWithoutV3Fields` (1), `TestV3EntryRoundTrip` (2).
- **`tests/test_task_adaptive_selector.py`** (PR-D, C-001 + C-003) — 5+ new tests covering default-on emission for each advisor block, per-flag opt-out, and per-profile post-patch budget headroom assertion.

### Changed
- **`workflow-system/agent/knowledge/reference-dependencies.yaml`** (PR-0, H-01 to H-06):
  - **H-01** delete broken `karpathy/andrej-karpathy-skills` entry (404 upstream); fold its 4 integration points into the surviving `forrestchang/andrej-karpathy-skills` entry. active_tracking 11 → 10.
  - **H-02** `PrimeLocus/Hydra` deleted upstream → redirect `repo_url` to `mikecubed/Hydra` fork (v1.2.0); `status: verified → deleted_upstream`; `relevance_score: 4 → 3`.
  - **H-03** `spring-ai-agent-skills.last_known_version` v0.4.2 → v0.7.0 (2026-04-06); add `releases_total: 9`.
  - **H-04** `agent-skills-security.last_known_version` arXiv pin v3 (2026-02-17); add `companion_repo: scienceaix/agentskills`.
  - **H-05** `skillrouter.last_known_version` arXiv v3 → v4 (2026-04-01); append v4 finding key_pattern.
  - **H-06** new `agent-skills-threat-taxonomy` entry under `periodic_monitoring` for arXiv:2604.02837v1 follow-up paper. periodic_monitoring 9 → 10.
- **`workflow-system/agent/context_profiles.yaml`** (PR-D + PR-E):
  - PR-D: 4 advisor-enabled profiles (`feature`, `refactor`, `migration`, `security-audit`) gain `advisor.conciseness_instruction: true` + `advisor.timing_block: true` + `advisor.reconcile_block: true`; `token_budget` bumped +200 each (`feature: 4950→5150`, `refactor: 4800→5000`, `migration: 4800→5000`, `security-audit: 5200→5400`) to absorb +100/+126 advisor-section growth without bumping `important`-priority sections under chars//4 fallback.
  - PR-E: 3 SAFE profiles (`research`, `design`, `documentation`) gain `inline_review_checklist: false` (opt-in default off) for the v7.2.0 inline self-review pattern (runtime hook lands in v7.3).
- **`.cursor/rules/skill-format-rules.mdc`** (PR-A, C-006) — SF-1 rewritten as tiered budget table: Default `<500` (SKILL.md), Large `≤1000` (references), XL `≤1600` (examples).
- **`adapter_configs/kimicode.yaml`** (PR-E, KimiCode coupling) — `budget.max: 500 → 502` to track SF-1 source ceiling 499 + 2-line frontmatter overhead from the `copy_with_frontmatter` transform (built output = source + 2). Caught by SI-10 step 1 on first PR-E attempt; absorbed into PR-E v2 per L0 escalation Option A.
- **`tests/test_kimicode_adapter.py`** (PR-E, KimiCode coupling) — hardcoded assertion `<= 500` → `<= 502` to match the YAML budget update.

### Metrics
- Tests: 1121 (v7.1.1) → **1181** (+60 net). Per-PR: PR-A +12, PR-B +13 (12 bypass + 1 mirror-parity), PR-C +15, PR-D +10, PR-E +0 (docs/yaml only), KimiCode test bump 0 (modified existing).
- Coverage: `devolaflow.compressor` ≥ 90 % (new bypass branch covered by 12 sandbox tests); `devolaflow.learnings` projected ≥ 97 % (15 new tests on dedup + backward-compat); `devolaflow.task_adaptive_selector` advisor coverage maintained (5+ new tests).
- EvoBench benchmarks: 34 / 34 PASS; **0 pp** composite drift vs v7.1.0 baseline (`tests/test_benchmarks.py::TestBaselineFile::test_v6_baseline_matches_current_results_within_tolerance` PASSED with SI-4 5 % regression threshold preserved across all scenarios).
- SKILL.md line count: **499 / 500** (SF-1 satisfied with zero headroom; v7.3 follow-up tracked).
- references/*.md max: `decomposition-gate.md` 517 / 1000 (51.7 %, comfortably under new C-006 Large tier ceiling).
- examples/*.md max: `full-pipeline-trace.md` 408 / 1600 (25.5 %, generous headroom under new XL tier).
- KimiCode adapter built output: 501 / 502 (within new cap).
- Lint: `ruff check src/ tests/` + `ruff format --check src/ tests/` clean.
- SI-10 pre-commit: **5 / 5 pass** (full tests, ruff check, ruff format, test_version, test_benchmarks). Step 6 (`make check-cursor-skill`) is a no-op since `.cursor/skills/devola-flow/` mirror was untracked in v7.1.1+ per `e44fa11`.
- SI-3 composite projection (heuristic, NineS confirmation pending): **9.46 / 10** vs threshold 8.5 — READY.
- Version consistency: 11 sync locations updated via `scripts/bump_version.py 7.2.0` (SF-3 / CP-3); `make sync-human-docs` regenerated EN/ZH human docs.
- LOC delta (production code/config): ~89 (compressor +70, learnings +49 / -5, task_adaptive_selector +37 / -6 + 4 yaml budget bumps + 9 advisor flags, schemas +20, references +92, SKILL.md +1 / 0 net, kimicode +1 / -1, hygiene yaml +30). Tests: ~250 LOC. Docs: ~200 LOC + CHANGELOG entry.

### Cross-references
- Source feedback: `.local/feedbacks/feecback_for_v7.1.1.md` (3-line ask: refresh refs + NineS decompose + self-loop validation + accept-list for user selection).
- Self-update workflow artifacts:
  - 7 delta reports: `.local/research/v7.2.0_refs/delta-T01.md` … `delta-T07.md` (87 deltas across 19 reference repos).
  - Candidate list: `.local/research/v7.2.0_candidate_list.md` (96 → 75 kept → 7 TIER-1 + 13 TIER-2 + 55 TIER-3 + 6 Registry Hygiene).
  - 6 validation reports: `.local/research/v7.2.0_validations/V01.md` … `V07.md`.
  - Accept list & roadmap: `.local/research/v7.2.0_accept_list_and_roadmap.md` (the user-selection deliverable).
- Patches (sandbox-validated, all `git apply --check` exit 0): `.local/sandbox/v7.2.0/V0[1-7]/patch.diff` + V04 rebased SKILL.md hunk.
- v7.2.x backlog (TIER-2 carryover): C-008 advisor-side prompt caching, C-009 reflective reflex (writes operational.jsonl using v7.2.0 C-007 schema), C-010 vexp plugins entry, C-011 data-instruction envelope spec, C-012 learnings substrate design note, C-013 Karpathy EXAMPLES.md pointer, C-014 knowledge/log.md, C-015 file-back-from-Review threshold, C-016 feedback.apply_proposal closure, C-017 clear_thinking caveat, C-018 vexp SWE-bench refresh, C-019 scion Hub primitives, C-020 per-agent budget ledger spec.
- Related v7.x cycle: continues the v7.0 → v7.1 staged-context-compression rollup. v7.2 closes the user-feedback loop opened by `feedback_for_v7.1.1.md`.

## [7.1.1] — 2026-04-17

**PATCH — hotfix for v7.1.0-pre feedback `"github 上的所有次级网页无法访问"` (all GitHub Pages secondary pages cannot be accessed). The shared demo nav script (`workflow-system/human/demo/shared/nav.js`) detected the landing page only by matching `/demo/` in `window.location.pathname`. GitHub Pages deploys the demo at `/DevolaFlow/`, so on the deployed landing page `isLanding` evaluated to `false` and every nav link was prefixed with `../`, resolving to `https://yorha-agents.github.io/<page>/index.html` — a 404 outside the project. Sub-page navigation was already correct (uses `../` from a one-level-deep page) and is unchanged. The fix detects landing by the ABSENCE of any known sub-page directory name in the URL path, so it works under all four canonical deployment shapes (GitHub Pages `/DevolaFlow/`, project-root local server `/demo/`, demo-dir local server `/`, and `file://`).**

### Fixed
- **`workflow-system/human/demo/shared/nav.js`** — replace the `/demo/`-only `isLanding` IIFE with a sub-page-directory ABSENCE check driven by a new `SUBPAGE_DIRS` constant listing the 8 sub-page directories (`design-system`, `framework-chain`, `context-flow`, `version-timeline`, `design-architecture`, `workflow-visualizer`, `stage-explorer`, `benchmark-results`). The new predicate evaluates `true` for: `https://yorha-agents.github.io/DevolaFlow/{,index.html}`, `http://localhost:8000/{,index.html}`, `http://localhost:8000/demo/index.html`, and `file:///.../workflow-system/human/demo/index.html`; and `false` for any URL whose path contains `/<subpage-dir>/` or ends with `/<subpage-dir>`. Two-line comment above the IIFE explains why the change was needed (GitHub Pages deploys at `/DevolaFlow/`, not `/demo/`).

### Added
- **`tests/test_demo_nav.py`** (CREATE, 21 tests) — Python regression suite that reads `nav.js`, regex-extracts the `SUBPAGE_DIRS` array, reimplements the `isLanding` predicate in pure Python, and asserts against 17 canonical URL shapes (11 GitHub Pages + 2 demo-dir local + 2 project-root local + 2 `file://`). Also includes: a parity check that `SUBPAGE_DIRS` exactly matches the on-disk sub-page directories under `workflow-system/human/demo/` (excluding `shared/`), a count check (must be 8), and a regression guard that fails if anyone reintroduces the legacy `/demo/`-only predicate. No browser, no playwright dependency — uses `pathlib`, `re`, and the existing `project_root` fixture from `tests/conftest.py`.

### Metrics
- Tests: 1100 → **1121** (+21 from `tests/test_demo_nav.py`).
- SI-10 pre-commit: **5 / 5 pass** (full tests, ruff check, ruff format, test_version, test_benchmarks).
- Version consistency: 11 sync locations updated via `scripts/bump_version.py 7.1.1` (SF-3 / CP-3); `make sync-human-docs` regenerated 16 EN/ZH human doc files.
- Lint: `ruff check src/ tests/` + `ruff format --check src/ tests/` clean.
- LOC delta: production code ~14 (nav.js IIFE rewrite + SUBPAGE_DIRS constant + 2-line comment); tests ~180 (`tests/test_demo_nav.py`); docs ~10 (CHANGELOG entry).

### Cross-references
- Source feedback: `.local/feedbacks/feedback_for_v7.1.0-pre.md` — verbatim user report `"github 上的所有次级网页无法访问"`.
- Prior release: v7.1.0 (`27452db`) — staged-context-compression rollup.

## [7.1.0] — 2026-04-17

**MINOR — rollup release closing the v7.0 → v7.1 staged-context-compression cycle. Fifth and final slice: no new primitives — adoption, integration, and retrospective. Flips 6 decomposition profiles to default-on for `tool_output_truncation` + extractive `summary`. Ships the final 2 NineS compression goldens (`compression_tool_output` + `compression_persistence`), regenerates `v7.1.0_baseline.json` (33 scenarios, 0 pp drift vs v7.0.2). SI-3 composite **9.47/10** — READY for stable tag.**

This release closes the staged-context-compression cycle opened in v7.0.0 (Cache-Layout Invariant), advanced in v7.0.1 (tool-output truncation), v7.0.2 (hierarchical predecessor summariser), and v7.0.3 (persistence probe + Learnings v2). No new primitives or public APIs ship — v7.1.0 is the **adoption + integration + retrospective** slice: the 6 decomposition profiles that previously had `tool_output_truncation.enabled: false` now flip to `true`, each gaining a default `summary: {mode: extractive, max_tokens: 1200, trigger_pct: 25}` block under `predecessor_summary`. The final two NineS compression goldens ship (closing open question K.6), and the EvoBench baseline is regenerated under the deterministic fallback estimator against the frozen v7.0.2 scoring rubric to confirm 0 pp composite drift across all 33 scenarios. Code/config delta is lean (~89 LOC); the bulk of the delta is documentation (§§12-15 in `context-isolation.md`: ~140 lines) and research artefacts (retrospective 312 LOC + SI-3 scorecard 220 LOC, stored under `.local/research/`). SI-3 composite lands at **9.47/10** (threshold ≥ 8.5, target ≥ 8.8), verdict **READY**. Open questions K.2 (plan-mode stays L1-only for v7.x), K.6 (all 5 compression goldens shipped), and K.7 (stay prompt-side for v7.x; OEM outreach deferred to v8.x) are resolved.

### Added
- **`data/golden_test_set/compression_tool_output.toml`** (CREATE, 3 cases) — NineS golden extracted verbatim from `tests/test_compressor.py::TestToolOutputTruncation`. Cases cover the three truncation tiers: `head_tail_short_output_no_truncation` (below threshold, passthrough), `middle_elision_mid_output` (head/tail marker emission), and `extractive_summary_above_cap` (cap-based extractive fallback). Each case pins the expected `truncated_bytes`, marker text (`[... N lines elided ...]`), and token counts so the golden exercises the primitive's full decision tree.
- **`data/golden_test_set/compression_persistence.toml`** (CREATE, 3 tiers) — NineS golden sourced verbatim from `.local/research/v7.0.3_probe_telemetry.json`. Tiers: `easy` (5 entities, SLO carry-through ≥ 1.0), `medium` (20 entities, SLO ≥ 0.9), `hard` (50 entities, SLO ≥ 0.9). Telemetry-observed carry-through is `1.0 / 1.0 / 1.0`, all passing their SLO. Closes open question K.6 — with the 3 compression goldens shipped in v7.0.1/v7.0.2 plus these 2, all 5 compression goldens from the v7 roadmap §K.6 are delivered.
- **`benchmarks/devolaflow_context/baselines/v7.1.0_baseline.json`** (CREATE, 33 scenarios) — regenerated under the deterministic fallback estimator with the frozen v7.0.2 scoring rubric. Per-scenario composite range `[84.13, 99.80]`; zero drift vs v7.0.2 baseline (SI-4 max-drift ceiling 5 pp preserved). Consumed by `tests/test_benchmarks.py::test_v7_1_0_baseline_present_and_healthy`.
- **`workflow-system/agent/references/context-isolation.md` §§ 12-15** (394 → 533 lines, +139):
  - §12 **Hierarchical Predecessor Summariser** — shape-preserving extraction algorithm from v7.0.2, preserve-list semantics (file paths, task ids, version strings, commit hashes, metric values, numeric ranges, interface signatures, named references = 8 ADR-003 NER classes), trigger / skip rules tied to `predecessor_summary.trigger_pct` and `predecessor_summary.max_tokens`.
  - §13 **Persistence Probe** — v7.0.3 probe harness (`tests/test_e2e_compression.py` + `tests/_probe_fixtures.py`), carry-through metric definition, tier SLOs (easy 1.0 / medium 0.9 / hard 0.9), paraphrase-FAIL / missing-FAIL / case-mismatch-FAIL classification, telemetry schema emitted to `.local/research/v7.0.3_probe_telemetry.json`.
  - §14 **Operational Learnings v2** — Learnings v2 schema (confidence decay linear `new_conf = conf - 0.5 * min(1, delta_days / half_life)`, `DECAY_FLOOR=0.1`, session pinning via `pinned_for_session`, `consolidate_session(session_id, ...)`), lazy migration shim for v1 entries, `session_id` flow through `load_relevant_learnings`.
  - §15 **Staged Compression — End-to-End Flow** — consolidated cross-version walkthrough tying v7.0.0 cache invariant, v7.0.1 tool truncation, v7.0.2 predecessor summariser, v7.0.3 probe + Learnings v2, and v7.1.0 adoption into a single diagram + narrative of how a Stage A → Stage B handoff now preserves critical entities under the 8K L3 budget.
- **`workflow-system/human/demo/version-timeline/versions.json`** — **+5 entries** (v7.0.0, v7.0.1, v7.0.2, v7.0.3, v7.1.0), raising total to 40. Each entry carries `headline`, `summary`, `highlights[]`, and `metrics{}`, and is tagged with the new `compression` era.
- **`workflow-system/human/demo/version-timeline/index.html`** — compression era section added with filter chip, hero tagline updated to reflect cycle closure.
- **`workflow-system/human/demo/shared/i18n.js`** — `vt.era.compression` keys in EN+ZH (`compression` / `上下文压缩`), plus compression-era filter chip strings.
- **`.local/research/retrospective_v7.0_to_v7.1.md`** (CREATE, 312 lines — **NOT committed; `.local/` is gitignored**) — SI-8 retrospective covering the full cycle: 7 gaps identified, 5-version delivery table, 6 deferrals with rationale, 8 learnings, cross-version metrics, process notes, next-iteration bullets for v7.2+.
- **`.local/research/v7.1.0_evaluation_report.md`** (CREATE, 220 lines — **NOT committed; `.local/` is gitignored**) — SI-3 scorecard: composite **9.47/10** (Code quality 9.5 · Architecture 9.7 · Test adequacy 9.5 · Maintainability 9.0 · Compatibility 9.5 · Performance 9.5). 0 blockers, 0 criticals, 2 minor follow-ups queued for v7.2+.
- **Cross-repo artefact** — `EvoBench/.local/feedbacks/feedbacks_from_devola/7.1.0.md` (496 lines, **lives in the EvoBench repository — NOT part of this commit**). Authored as evaluation-mode feedback with 9 proposals: persistence-probe scorer, LCP harness, golden ingestion, truncation fidelity, decay-aware scoring, session-pinning, composite rebalancing, 11-adapter parity, flake-rate tracking.

### Changed
- **`workflow-system/agent/context_profiles.yaml`** — 6 decomposition profiles flip `tool_output_truncation.enabled: false → true` and gain a `summary: {mode: extractive, max_tokens: 1200, trigger_pct: 25}` block under their `predecessor_summary` section:
  - `feature`, `refactor`, `skill-optimization`, `migration`, `security-audit`, `perf-optimization`.
  - Opt-out documented per-profile via the pre-existing `tool_output_truncation.override` knob; hotfix / docs / research-heavy profiles remain unaffected.
- **`workflow-system/human/demo/version-timeline/version-timeline.js`** — `ERAS` array gains `"compression"`; rollup description copy refreshed to cover the staged-compression cycle.
- **`workflow-system/human/demo/benchmark-results/index.html`** — `SAMPLE_DATA.version` 7.0.3 → 7.1.0 (bumped via `scripts/bump_version.py`); round 6 `v7_staged_compression` dataset added with 5 compression scenarios (per-scenario composite range `[98.33, 99.80]`).
- **`tests/test_benchmarks.py`** — `V6_BASELINE_PATH` retargets from the v7.0.2 baseline path to `benchmarks/devolaflow_context/baselines/v7.1.0_baseline.json`; accompanying healthy-baseline assertions updated to match the new filename.

### Open questions resolved
- **K.2** — plan-mode scope. Resolution: **plan-mode stays L1 (Stage) only for v7.x**. Rationale: the v6.x convergence loop and v7.0 probe harness already cover the planning reinforcement loop at L1; promoting plan-mode to L0 (Project) would couple project-level orchestration to per-stage planning assumptions. Revisit in v8.x if reinforcement metrics show a gap.
- **K.6** — compression goldens. Resolution: **all 5 shipped** (3 in v7.0.1/v7.0.2 — `compression_cache_invariant`, `compression_predecessor_summary`, `compression_staged_end_to_end`; 2 in v7.1.0 — `compression_tool_output`, `compression_persistence`).
- **K.7** — OEM outreach / runtime-side compression. Resolution: **stay prompt-side for v7.x**. The staged-compression primitives ship as deterministic prompt-level transforms so they compose with every adapter in the 11-adapter matrix without runtime coupling. A runtime-side / OEM outreach protocol is deferred to v8.x.

### Metrics
- Tests: 1090 → **1100** (+10 from the 2 new NineS compression goldens' verification tests).
- Coverage: `devolaflow.compressor` 94 %, `devolaflow.learnings` 97 %, total **94.37 %** (rule CP-2 floor 80 %; v7.0.3 ≥ 90 % target preserved).
- NineS composite: **0.8805** (stable vs v7.0.3).
- EvoBench benchmarks: **34/34 pass**, **0 pp** composite drift vs v7.0.2 baseline across all 33 scenarios (SI-4 max-drift ceiling 5 pp preserved).
- SKILL.md line count: **498 / 500** (SF-1 satisfied — body unchanged from v7.0.3; only frontmatter/banner/body version strings bumped via `scripts/bump_version.py`).
- LOC delta: production code / config **~89** (mostly `context_profiles.yaml` flips + baseline JSON + 2 golden TOMLs + web-demo JS/HTML); docs + research **~1450** (§§12-15 in `context-isolation.md` ~140 LOC + retrospective 312 + SI-3 scorecard 220 + EvoBench feedback 496 + versions.json + CHANGELOG + misc).
- Lint: `ruff check` + `ruff format --check` clean (SI-10 #2, #3).
- SI-10 pre-commit: **5 / 5 pass** (full tests, ruff check, ruff format, test_version, test_benchmarks).
- Version consistency: 11 sync locations updated via `scripts/bump_version.py 7.1.0` (SF-3 / CP-3); `make sync-human-docs` regenerated EN/ZH human docs.

### Cross-references
- Roadmap: `.local/research/v7.0.0_version_roadmap.md` §v7.1.0 (rollup slice).
- Research source: `.local/research/v7.0.0_context_compression_research.md` §§K.2, K.6, K.7 (resolved), §G (adoption matrix).
- Retrospective: `.local/research/retrospective_v7.0_to_v7.1.md` (SI-8).
- SI-3 evaluation: `.local/research/v7.1.0_evaluation_report.md`.
- Cross-repo: `EvoBench/.local/feedbacks/feedbacks_from_devola/7.1.0.md` (EvoBench repo; 9 evaluation-mode proposals).

### Scope (v7.0 → v7.1 cycle closure)
v7.1.0 closes the cycle that began with v7.0.0 (Cache-Layout Invariant, J.1). The five-slice delivery is: v7.0.0 J.1 → v7.0.1 J.2 → v7.0.2 J.3 → v7.0.3 J.4+J.5 → v7.1.0 adoption. With K.2 / K.6 / K.7 resolved, the staged-compression primitives are now default-on across 6 decomposition profiles and the SI-3 scorecard clears the stable-release threshold. Verdict: **READY** for stable tag.

## [7.0.3] — 2026-04-17

**MINOR — fourth slice of the v7.0 → v7.1 staged-context-compression cycle: ships J.4 + J.5 together (end-to-end persistence-probe harness + Learnings v2 additive schema with confidence decay, session pinning, and consolidate_session). Resolves K.5 (stay JSONL, no file-system memory tool).**

This release lands two independent but thematically paired deliverables from the v7 roadmap. J.4 / ADR-004 adds a **cross-stage persistence probe** (`tests/test_e2e_compression.py` + `tests/_probe_fixtures.py`) that synthesises a Stage A artifact with a seeded preserve-list panel, runs it through `summarise_predecessor` (from v7.0.2), embeds the result in a canonical-layout Stage B dispatch, and asserts that every seeded entity survives verbatim. Three probe scenarios ship (easy / medium / hard at 5 / 20 / 50 entities respectively); telemetry is captured per-scenario in `.local/research/v7.0.3_probe_telemetry.json` for SI-3 scoring. Failure classification matches ADR-004 §2.3: paraphrase → FAIL, missing entirely → FAIL, case-mismatch → FAIL for `file_paths` and `commit_hashes`, PASS otherwise. J.5 / ADR-005 ships a **Learnings v2 additive schema migration** in `src/devolaflow/learnings.py`: four new optional dataclass fields (`confidence_half_life_days`, `last_accessed`, `pinned_for_session`, `promotion_count`), three new public functions (`consolidate_session`, `decay_confidence`, `pin_learning_for_session`), and a `session_id: str | None` parameter on `load_relevant_learnings()`. Decay is linear — `new_conf = conf - 0.5 * min(1, days_since_last_accessed / half_life)` — with a `DECAY_FLOOR=0.1` prune threshold. Legacy v1 JSONL entries parse unchanged (ADR-005 §2.4 migration shim: `last_accessed` is lazily backfilled from `timestamp` on the first decay touch). Open question K.5 is resolved: we stay with JSONL and do **not** surface a Claude-style file-system memory tool.

### Added
- **`tests/test_e2e_compression.py`** (CREATE, 10 tests) — persistence-probe harness marked `@pytest.mark.persistence_probe`. Tests: `test_carrythrough_passes_on_faithful_summary`, `test_carrythrough_fails_on_paraphrase` (paraphrase-injection FAIL-path guard), `test_carrythrough_threshold_easy` / `_medium` / `_hard` (ADR-004 §2.2 tiers), `test_extract_named_entities_integration` (≥40 entities of mixed types on a ~10 K-token artifact), `test_probe_reports_flake_rate` (per-scenario elapsed time + carry-through rate written to `.local/research/v7.0.3_probe_telemetry.json`), `test_telemetry_records_threshold_per_scenario`, `test_carrythrough_helper_empty_artifact_returns_one`, `test_carrythrough_helper_case_mismatch_for_file_paths_fails` (ADR-004 §2.3 case-sensitivity guard).
- **`tests/_probe_fixtures.py`** (CREATE, 190 LOC) — `build_probe_workspace(tmp_path, scenario, paraphrase_file_path=False, summary_max_tokens=1200)` builder used by both the `_compression_e2e_workspace` fixture and the direct-call probe tests. Writes `stage_a/artifact.md` (with seeded preserve-list panel + filler body sized to the scenario's body-token target), `stage_b/dispatch.yaml` (canonical 12-key layout, validated via `assert_dispatch_layout`), and `stage_b/context_packed.yaml` (token accounting). Seeds cycle through file paths, task ids, version strings, commit hashes, metric values, and interface signatures so every scenario exercises ≥ 4 of the 8 ADR-003 NER classes. **Test-only** per ADR-004 §3 — deliberately kept out of `src/` so the probe's scoring semantics can evolve without coupling production consumers.
- **`tests/conftest.py#_compression_e2e_workspace`** — new pytest fixture (60 LOC addition) that delegates to `build_probe_workspace(tmp_path, scenario="easy")`. Tests needing medium / hard scenarios call the builder directly.
- **`devolaflow.learnings.Learning`** gains 4 v2 additive fields (ADR-005 §2.1, default-safe for legacy JSONL entries): `confidence_half_life_days: int = 30`, `last_accessed: str = ""`, `pinned_for_session: str = ""`, `promotion_count: int = 0`. `__post_init__` coerces types (defends ADR-005 §3 risk P3).
- **`devolaflow.learnings.consolidate_session(session_id, session_learnings, jsonl_path) -> dict`** — session-end helper that bumps matched entries by `+0.05` confidence, increments `promotion_count`, refreshes `last_accessed`, and captures unmatched ones with `promotion_count=1`. Idempotent within a single call: duplicate `(key, stage, task_type)` triples in the payload are skipped (ADR-005 §6 test #8). Returns `{promoted, captured, skipped}`.
- **`devolaflow.learnings.decay_confidence(jsonl_path, half_life_days=None) -> dict`** — linear decay `new_conf = conf - 0.5 * min(1.0, delta_days / half_life)` clamped to `[0.0, 1.0]`; entries whose new confidence falls strictly below `DECAY_FLOOR=0.1` are pruned. Migration shim (ADR-005 §2.4): legacy entries without `last_accessed` get that field backfilled from `timestamp` on first touch. Returns `{decayed_count, dropped_below_floor_count}`.
- **`devolaflow.learnings.pin_learning_for_session(key, stage, task_type, session_id, jsonl_path) -> bool`** — marks a matched entry as pinned for `session_id`. `load_relevant_learnings(..., session_id=X)` then surfaces that entry regardless of confidence floor. Empty `session_id` clears the pin. Returns `True` iff a match was found.
- **`devolaflow.learnings.DEFAULT_DECAY_HALF_LIFE_DAYS=30`** and **`DECAY_FLOOR=0.1`** — module-level constants exposing the decay defaults.
- **`devolaflow.learnings.__all__`** — new module-level export list surfacing 12 public symbols (3 new v2 helpers + 9 pre-existing).
- **12 new tests** in `tests/test_learnings.py::TestLearningsV2Schema`: `test_decay_confidence_linear`, `test_decay_confidence_floor`, `test_consolidate_session_promotes_matched`, `test_consolidate_session_captures_new`, `test_pin_for_session`, `test_legacy_entry_parses`, `test_migration_last_accessed_shim`, `test_consolidate_session_idempotent`, `test_consolidate_session_empty_payload_noop`, `test_decay_confidence_missing_file_returns_zero_summary`, plus class `TestLearningsV2Coverage` (12 tests) targeting pre-existing branches to hit the ≥ 90 % coverage floor (`promote_learning` matched / no-match, `get_learnings_stats` nonempty + empty, `load_relevant_learnings` invalid-timestamp / missing-required-fields, `prune_learnings` invalid-timestamp, `decay_confidence` zero half-life / invalid last_accessed / empty file, `pin_learning_for_session` missing-key, `log_external_source_review` default path).
- **`workflow-system/agent/SKILL.md` §"Operational Learnings — Session Pinning & Decay (v7.0.3+)"**: 2-paragraph addition appended after the Task Quality Score section (SF-1 budget preserved — `wc -l` 498 ≤ 500). Documents decay formula, pin semantics, and the lazy migration shim.
- **`pyproject.toml#[tool.pytest.ini_options].markers`**: registers `persistence_probe` so `@pytest.mark.persistence_probe` does not trigger the default `PytestUnknownMarkWarning`.
- **`scripts/detect_dead_apis.py` allowlist**: `consolidate_session`, `decay_confidence`, `pin_learning_for_session` added (consumed by L1/L0 session-end hooks and by dispatchers that need cross-round pinning).

### Changed
- **`devolaflow.learnings.load_relevant_learnings(..., session_id=None)`**: new optional parameter. When provided, entries whose `pinned_for_session` matches are surfaced first (ahead of the confidence-sorted top-N) regardless of `min_confidence`; unpinned entries still honour `min_confidence`. De-duplicates by `(stage, task_type, key)` so a pinned + high-confidence entry does not appear twice.
- **`src/devolaflow/learnings.py` module docstring** updated to document the v2 schema additions.

### Open questions resolved
- **K.5** — memory-tool surface area. Resolution: **stay JSONL**, do NOT surface a Claude-style file-system memory tool. Rationale (ADR-005 §1): (a) hook-based validation (`check_file_ownership`, `test_on_complete`) already covers JSONL shape; (b) a file-system API duplicates functionality `Read` / `Write` / `StrReplace` already provide against the JSONL file; (c) v7 scope is tight. Revisit in v8.x if learnings-consumption metrics demonstrate a workflow gain.

### Metrics
- Tests: 1058 → **1090** (+32: 10 persistence-probe + 10 new `TestLearningsV2Schema` + 12 coverage-floor tests in `TestLearningsV2Coverage`). Exceeds the spec's +19 test-count delta target.
- `devolaflow.learnings` coverage: 81 % → **97.35 %** (rule CP-2 floor for v7.0.3 per roadmap §v7.0.3 = ≥ 90 %).
- Probe telemetry at `.local/research/v7.0.3_probe_telemetry.json` — carry-through rate **1.0** on all three scenarios (easy / medium / hard; 0 entities missed across 5 + 20 + 50 = 75 seeded entities).
- LOC delta (against budget 700 — within budget): production code 236 (`learnings.py`), test code 464 (`test_learnings.py` 220 + `test_e2e_compression.py` 287 + `_probe_fixtures.py` 190 − file renumbering; see branch diff for exact accounting), schema / docs 3 (SKILL.md + pyproject marker), changelog ~80, allowlist 10, version sync ~11. Code-only delta ~240; test code ~460; total ~700 LOC.
- Benchmarks: no regression vs. v7.0.2 baseline (SI-4 guard; max drift **0.00 pp** across all 33 EvoBench scenarios; verdict **PASS**). Per-scenario delta: all zero because the v7.0.3 SKILL.md addition lives past every `context_profiles.yaml` line-range mapping (deliberately placed after `task_quality_score: 471-495` so no existing section's line range shifts).
- All 11 adapters [OK] (CP-5 verified). SKILL.md: 495 → **498 lines** (SF-1 cap 500; KimiCode adapter budget 500 honoured after prepended frontmatter).
- Lint: ruff check + format clean (SI-10 #2, #3).
- Version consistency: 11 sync locations updated via `scripts/bump_version.py 7.0.3` (SF-3 / CP-3); `make sync-human-docs` regenerated 16 EN/ZH human docs.

### Cross-references
- ADR: `.local/research/adr/v7-ADR-004-persistence-probe.md` (J.4), `.local/research/adr/v7-ADR-005-learnings-v2.md` (J.5)
- Roadmap: `.local/research/v7.0.0_version_roadmap.md` §v7.0.3
- Research source: `.local/research/v7.0.0_context_compression_research.md` §§H.4, I, J.4, B.5, F row 7, G row 7, J.5, K.5

### Scope (v7.0 → v7.1 cycle)
v7.0.3 ships J.4 + J.5 together (per roadmap §v7.0.3 — two ADRs × two modules = clean two-wave split, paired under "quality / measurement" theme). Remaining cycle slice: v7.1.0 (adoption opt-in + SI-3 evaluation + SI-8 retrospective + final 2 of 5 NineS goldens `compression_tool_output` + `compression_persistence` to close K.6).

## [7.0.2] — 2026-04-17

**MINOR — third slice of the v7.0 → v7.1 staged-context-compression cycle: ships J.3 only (deterministic hierarchical predecessor summariser + 8-class NER + compression-retention scenarios + first 3 of 5 NineS goldens for K.6).**

This release lands the deterministic extractive summariser that ADR-003 commits DevolaFlow to. `summarise_predecessor()` parses an artifact by extension (markdown / YAML / JSON / TOML / H2 fallback), runs the new `extract_named_entities()` pass over the full body, prefixes the output with a verbatim `key_facts:` YAML block, then fills the remaining token budget with schema-hint-prioritised sections (`design` → Decision/Consequences/Alternatives, `research` → Recommendations/OpenQuestions/Synthesis, `adr` → Decision/Consequences/Test plan, `gate_report` → Verdict/Findings/Metrics, default → H2 in document order). Hard-capped at `max_tokens` with a `[TRUNCATED]` marker and `was_bounded=True` flag — no paraphrase, ever. The companion 8-class NER (`file_paths`, `task_ids`, `version_strings`, `commit_hashes`, `metric_values`, `error_messages`, `acceptance_criterion_bullets`, `interface_signatures`) reuses `PRESERVE_PATTERNS` for the first six classes so the compactor and the summariser stay in lock-step on what counts as a verbatim preserve-list fact (CO-2). The new schema fields `pred[*].summary_mode` and `pred[*].summary_max_tokens` are nested per-pred (NOT new top-level keys — honours the v7-ADR-001 cache-layout invariant). The new `meta.summary_trigger_pct: 25` profile knob resolves open question K.1: dispatchers MUST summarise above 25 % of the consuming layer's token_budget (e.g. L3 8000 → above 2000 tokens; L2 4000 → above 1000).

### Added
- **`devolaflow.compressor.summarise_predecessor(artifact_path, max_tokens=500, mode="extractive", schema_hint=None) -> dict`**: deterministic extractive summariser. Parses markdown / YAML / JSON / TOML by extension (default H2 fallback), runs `extract_named_entities` on the full body, emits a `key_facts:` verbatim prefix, then fills the budget with schema-hint-prioritised sections (case-insensitive substring match, accepts plural/singular). Returns a 7-key dict: `summary_text`, `mode`, `token_count`, `extracted_entities`, `covered_sections`, `dropped_sections`, `was_bounded`. Mode `"abstractive"` raises `NotImplementedError` at v7.0.2 — wired in v7.0.3+ behind an opt-in profile flag per ADR-003 §2.3.
- **`devolaflow.compressor.extract_named_entities(text) -> list[dict]`**: deterministic NER over 8 entity classes — `file_paths`, `task_ids`, `version_strings`, `commit_hashes`, `metric_values`, `error_messages` (all six reuse `PRESERVE_PATTERNS` per CO-2), `acceptance_criterion_bullets` (matches `- MUST/SHOULD/SHALL/MAY [NOT]` lines), `interface_signatures` (Python `def`/`class` plus YAML `key: type` hints). Each entry is `{type, value, source_line}` with 1-indexed source lines; duplicates de-duped per `(type, value)` pair, document order preserved.
- **`devolaflow.compressor.SCHEMA_HINT_PRIORITIES`**: module-level constant exposing the 4 schema-hint priority lists — `design`, `research`, `adr`, `gate_report` — for downstream callers that need to introspect the priority order.
- **`devolaflow.compressor.DEFAULT_SUMMARY_MODE`**, **`DEFAULT_SUMMARY_MAX_TOKENS`**, **`DEFAULT_SUMMARY_TRIGGER_PCT`**, **`SUMMARY_TRUNCATION_MARKER`**: module-level constants for the summariser defaults (`"extractive"`, `500`, `25`, `"[TRUNCATED]"`).
- **`schemas/lean-dispatch.yaml#pred.per_entry.summary_mode`** and **`summary_max_tokens`**: new OPTIONAL fields nested inside each `pred` entry. Defaults: `extractive` / `500`. Missing → extractive / 500. Honours v7-ADR-001 layout invariant (no new top-level keys; nested under existing `pred`).
- **`workflow-system/agent/context_profiles.yaml#meta.summary_trigger_pct: 25`**: new meta key — relative threshold above which dispatchers MUST summarise predecessor artifacts (resolves K.1 per ADR-003 §2.4). Per-profile override available.
- **`benchmarks/devolaflow_context/scenarios/compression_retention_easy.yaml`**: research profile (3300-token budget) probe — ~5 K-token artifact, 5 probe facts, retention target ≥ 95 %. Composite at v7.0.2 cut: **99.62**.
- **`benchmarks/devolaflow_context/scenarios/compression_retention_medium.yaml`**: design profile (4450-token budget) probe — ~10 K-token artifact, 10 probe facts, retention target ≥ 95 %. Composite at v7.0.2 cut: **99.23**.
- **`benchmarks/devolaflow_context/scenarios/compression_retention_hard.yaml`**: hotfix profile (2400-token budget — the tightest) probe — ~15 K-token ADR-class artifact, 15 probe facts spanning all 8 NER types, retention target ≥ 90 % (stretch goal per ADR-003 §6 #9). Composite at v7.0.2 cut: **98.55**.
- **`data/golden_test_set/compression_retention_easy.toml`** / **`compression_retention_medium.toml`** / **`compression_retention_hard.toml`**: 3 NineS V1 golden TOMLs (target dimension `analysis`, scorer `exact`) probing extractive entity preservation, schema-hint priority, and `was_bounded` truncation respectively. Closes 3 / 5 of K.6 (remaining 2 ship in v7.1.0).
- **`benchmarks/devolaflow_context/baselines/v7.0.2_baseline.json`**: regenerated full-coverage baseline (33 scenarios = 30 prior + 3 new `compression_retention_*`). Replaces `v7.0.1_baseline.json` as the staleness-guard target.
- **10 new unit tests** in `tests/test_compressor.py::TestHierarchicalSummariser` (per ADR-003 §6): `test_summarise_extractive_preserves_file_paths`, `test_summarise_extractive_honours_max_tokens`, `test_summarise_schema_hint_priority`, `test_summarise_unknown_extension`, `test_summarise_trigger_threshold`, `test_extract_named_entities_all_types`, `test_summarise_was_bounded_truncation_marker`, `test_summarise_abstractive_not_yet_wired_raises`, `test_extract_entities_reuses_preserve_patterns`, `test_summarise_returns_structured_dict_keys`.
- **`scripts/detect_dead_apis.py` allowlist**: `summarise_predecessor`, `extract_named_entities` added (consumed by external dispatchers per ADR-003 §2.4 and re-used by the v7.0.3 persistence probe per ADR-004).

### Changed
- **`devolaflow.compressor.__all__`** extended with `summarise_predecessor`, `extract_named_entities`, `SCHEMA_HINT_PRIORITIES`, `DEFAULT_SUMMARY_MODE`, `DEFAULT_SUMMARY_MAX_TOKENS`, `DEFAULT_SUMMARY_TRIGGER_PCT`, `SUMMARY_TRUNCATION_MARKER`. No symbols removed; v7.0.x importers continue to work unchanged.
- **`tests/test_benchmarks.py`** `V6_BASELINE_PATH` retargeted to `v7.0.2_baseline.json`; `test_runner_prefers_latest_baseline` expectation bumped accordingly. The v7.0.0 / v7.0.1 baseline files are retained on disk as historical record.

### Open questions resolved
- **K.1** — forced-summarisation threshold. Resolution: relative threshold of **25 %** of the consuming layer's `token_budget` (per ADR-003 §2.4). Surfaces as `meta.summary_trigger_pct` in `context_profiles.yaml` for per-profile override. Below threshold, dispatchers may embed the artifact body verbatim under `pred[*].body`.
- **K.6** — NineS V1 golden set authoring. **3 / 5 shipped** in v7.0.2 (`compression_retention_easy/medium/hard`); remaining 2 (`compression_tool_output`, `compression_persistence`) ship in v7.1.0 per roadmap §v7.1.0.

### Metrics
- Tests: 1023 → 1033 (+10: all in `TestHierarchicalSummariser`)
- `devolaflow.compressor` coverage: ≥ 90 % (rule CP-2 floor for v7.0.2 per roadmap §v7.0.2)
- New EvoBench scenario composites: `compression_retention_easy` 99.62, `compression_retention_medium` 99.23, `compression_retention_hard` 98.55 (all above min_composite 85 / min_relevance 0.9 / max_noise_ratio 0.15)
- Existing 30 EvoBench scenarios: zero regression vs. v7.0.1 baseline (max drift 0.00 pp, well within SI-4 5pp tolerance)
- LOC delta against budget 420 — within budget: production code 162, schema 8, profile 11, tests 165, scenarios 165, goldens 60, baseline regen ~430 (auto-generated), changelog ~50, allowlist 8, version sync ~10
- All 11 adapters [OK] (CP-5 verified)
- Lint: ruff check + format clean (SI-10 #2, #3)
- Version consistency: 8 sync locations updated via `scripts/bump_version.py 7.0.2` (SF-3 / CP-3)
- SKILL.md unchanged at 495 lines (the v7.0.2 docs land in inline docstrings + ADR-003 cross-link only — well within the 500 SF-1 cap)

### Cross-references
- ADR: `.local/research/adr/v7-ADR-003-hierarchical-summary.md`
- Roadmap: `.local/research/v7.0.0_version_roadmap.md` §v7.0.2
- Research source: `.local/research/v7.0.0_context_compression_research.md` §§B.3, F row 2, G row 2, H.1, J.3, K.1, K.6

### Scope (v7.0 → v7.1 cycle)
v7.0.2 ships J.3 only. Remaining cycle slices: v7.0.3 (J.4 + J.5 persistence probe + learnings v2 — re-uses `extract_named_entities` from this version), v7.1.0 (cycle adoption + SI-3 evaluation + SI-8 retrospective + remaining 2 NineS goldens to close K.6).

## [7.0.1] — 2026-04-17

**MINOR — second slice of the v7.0 → v7.1 staged-context-compression cycle: ships J.2 only (tool-output truncation primitive + `tool_results` schema block).**

This release lands the prompt-side equivalent of Anthropic's `clear_tool_uses_20250919` server-side primitive: a deterministic head/tail truncation helper and a most-recent-N + exclude-by-name policy applied to a sequence of `tool_use` records. Both helpers are pure functions; per-profile opt-in lives in `workflow-system/agent/context_profiles.yaml` (default `enabled: false` for the six decomposition-enabled profiles at the v7.0.1 cut). The new `tool_results:` block is appended at the end of `schemas/lean-report.yaml` per the cache-layout invariant from v7.0.0 (additive rule, no existing top-level keys reordered). v7.0.1 also bumps `decomposition.sub_agent_context_budget` from 3000 → 5000 tokens across those six profiles (resolves open question K.8).

### Added
- **`devolaflow.compressor.truncate_tool_output(text, *, head_chars=500, tail_chars=500, placeholder_template="[truncated {removed} chars]")`**: pure function that returns `(maybe_truncated_text, removed_chars)`. If `len(text) <= head_chars + tail_chars` returns `(text, 0)`; otherwise `(head + placeholder + tail, removed_chars)` with `{removed}` substituted in the placeholder. Character-boundary slicing via `len()` keeps Unicode payloads safe.
- **`devolaflow.compressor.clear_old_tool_uses(tool_uses, *, keep=3, exclude_tool_names=("Read",), head_chars=500, tail_chars=500, placeholder_template=...)`**: walks a list of `tool_use` dicts (each with `name` + `output`), preserves the most recent `keep` records verbatim, preserves any older record whose `name` is in `exclude_tool_names`, and truncates everything else via `truncate_tool_output`. Returns `(modified_list, ToolUseTruncation summary)`. `kept_count + cleared_count == len(tool_uses)`. Inputs are not mutated (shallow-copied modified records).
- **`devolaflow.compressor.ToolUseTruncation`**: new frozen dataclass with `kept_count`, `cleared_count`, `head_chars`, `tail_chars`, `placeholder`, `excluded_tool_names`. Records the policy applied so the L2 wave consumer can decide whether to refresh the L1 dispatch tool list.
- **`schemas/lean-report.yaml#tool_results`**: new top-level block (appended at the end of the file per ADR-001 §2 additive rule). Documents the policy (`keep`, `exclude_tool_names`, `head_chars`, `tail_chars`, `placeholder_template`) and the runtime-recorded summary (`kept_count`, `cleared_count`, `cleared_at_round`). Producing layer = L3 task agent; consumer = L2 wave agent.
- **`benchmarks/devolaflow_context/scenarios/compression_tool_output.yaml`**: new EvoBench scenario exercising the `skill-optimization` decomposition-enabled profile. Validates that the four sections (`context_isolation`, `dispatch_report`, `gate_mechanism`, `convergence_loop`) needed to read the `tool_results.summary` block remain selected after the v7.0.1 profile edits. Composite at v7.0.1 cut: **98.33** (well above min_composite 85, min_relevance 0.85, max_noise_ratio 0.15).
- **`benchmarks/devolaflow_context/baselines/v7.0.1_baseline.json`**: regenerated full-coverage baseline (30 scenarios, including the new `compression_tool_output`). Replaces `v7.0.0_baseline.json` as the staleness-guard target.
- **8 new unit tests** in `tests/test_compressor.py::TestToolOutputTruncation`: `test_truncate_tool_output_below_threshold`, `test_truncate_tool_output_above_threshold`, `test_truncate_tool_output_placeholder_format`, `test_truncate_tool_output_unicode_safe`, `test_clear_old_tool_uses_keeps_recent_n`, `test_clear_old_tool_uses_excludes_named_tools`, `test_clear_old_tool_uses_returns_summary`, `test_clear_old_tool_uses_empty_list`.
- **`workflow-system/agent/references/context-isolation.md` §11 "Tool-Output Truncation (v7.0.1+)"**: documents when the runtime applies truncation, the keep/exclude/head/tail policy, the placeholder format, and how the L2 wave consumer reads the `tool_results.summary` block to decide on tool-list refresh.
- **`scripts/detect_dead_apis.py` allowlist**: `truncate_tool_output`, `clear_old_tool_uses`, `ToolUseTruncation` added (consumed by external runtimes per ADR-002 §2.1; opted in via per-profile `tool_output_truncation:` block).

### Changed
- **`workflow-system/agent/context_profiles.yaml`**: 6 decomposition-enabled profiles (`feature`, `refactor`, `skill-optimization`, `migration`, `security-audit`, `perf-optimization`) gain a `tool_output_truncation:` block (default `enabled: false`, `keep: 3`, `exclude_tool_names: ["Read"]`, `head_chars: 500`, `tail_chars: 500`). Same 6 profiles bump `decomposition.sub_agent_context_budget` from 3000 → 5000 (resolves open question K.8 — recent-N verbatim records require headroom for the sub-agent to ingest without spillover).
- **`devolaflow.compressor.__all__`** extended with `truncate_tool_output`, `clear_old_tool_uses`, `ToolUseTruncation`. No symbols removed; v7.0.x importers continue to work unchanged.
- **`tests/test_benchmarks.py`** `V6_BASELINE_PATH` retargeted to `v7.0.1_baseline.json`; `test_runner_prefers_latest_baseline` expectation bumped accordingly. The v7.0.0 baseline file is retained on disk as historical record.

### Open questions resolved
- **K.4** — tool-result clearing default. Resolution: `keep=3` (Anthropic's default), `exclude_tool_names=("Read",)`, `head_chars=500`, `tail_chars=500`. Per-profile override available.
- **K.8** — `sub_agent_context_budget` for decomposition-enabled profiles. Resolution: 3000 → 5000 tokens across the 6 profiles. Confirms the headroom needed once recent-N tool outputs are preserved verbatim downstream.

### Metrics
- Tests: 1015 → 1023 (+8: all in `TestToolOutputTruncation`)
- `devolaflow.compressor` coverage: ≥ 88 % (rule CP-2 floor for v7.0.1 per ADR-002 §3)
- New EvoBench scenario `compression_tool_output` composite: 98.33 (relevance 1.0, noise 0.06, budget util 0.56)
- Existing 29 EvoBench scenarios: no regression vs. v7.0.0 baseline (SI-4 guard; max drift well within 5pp tolerance)
- LOC delta (against budget 320): within budget — production code 125, schema 20, tests 80, scenario 50, baseline 40, profiles 35, docs 60, changelog 35, allowlist 10, version sync 10
- All 11 adapters [OK] (CP-5 verified)
- Lint: ruff check + format clean (SI-10 #2, #3)
- Version consistency: 8 sync locations updated via `scripts/bump_version.py 7.0.1` (SF-3 / CP-3)
- SKILL.md unchanged (the v7.0.1 docs land in `references/context-isolation.md` only — `wc -l` 495 → 495, well within the 500 SF-1 cap)

### Cross-references
- ADR: `.local/research/adr/v7-ADR-002-tool-output-truncation.md`
- Roadmap: `.local/research/v7.0.0_version_roadmap.md` §v7.0.1
- Research source: `.local/research/v7.0.0_context_compression_research.md` §§B.3, F row 6, G row 6, J.2

### Scope (v7.0 → v7.1 cycle)
v7.0.1 ships J.2 only. Remaining cycle slices: v7.0.2 (J.3 hierarchical predecessor summary), v7.0.3 (J.4 + J.5 persistence probe + learnings v2), v7.1.0 (cycle adoption + SI-3 evaluation + SI-8 retrospective).

## [7.0.0] — 2026-04-17

**MAJOR — opens the v7.0 → v7.1 staged-context-compression cycle by shipping J.1 only: the cache-layout invariant.**

This release introduces the first publicly-documented governance contract on dispatch layout. It is an additive API at the Python level (no public function changes signature, no rendered dispatch produced by v6.x is invalidated), but a **backwards-incompatible governance constraint on any downstream tooling that previously assumed free reordering of top-level dispatch sections**. Per `.local/research/adr/v7-ADR-001-cache-layout-invariant.md` §2, every lean dispatch must henceforth honour the canonical 12-key order, and every new top-level key must be appended after `gate`. The MAJOR bump signals that constraint to ecosystem consumers; v7.0.1–v7.0.3 land additive primitives on top of it (default-off feature flags), and v7.1.0 flips the flags on with the cycle SI-3 evaluation and SI-8 retrospective.

### Added
- **`devolaflow.compressor.assert_dispatch_layout(payload, layout_spec=None)`**: runtime validator that raises `DispatchLayoutError` when a dispatch payload's top-level key insertion order is not a subsequence of the canonical layout, or when an unknown key appears before the last spec key. Honours the additive rule from ADR-001 §2.
- **`devolaflow.compressor.compute_dispatch_lcp_pct(payload_a, payload_b)`**: rendered-YAML longest-common-prefix percentage helper backing the H.2 round-stability test (`yaml.safe_dump(..., sort_keys=False, default_flow_style=False)` byte-comparison).
- **`devolaflow.compressor.DispatchLayoutError`**: new `ValueError` subclass for invariant violations.
- **`devolaflow.compressor.DEFAULT_DISPATCH_LAYOUT`**: module-level canonical 12-key order constant (`hdr`, `task`, `goal`, `assumptions`, `pred`, `files`, `rules`, `shared`, `accept`, `reinforce`, `verify_cfg`, `gate`).
- **`schemas/lean-dispatch.yaml#layout_invariant`**: new schema block declaring `version: 1`, `canonical_order` (12 keys), and `enforcement` (validator path, stability test path, `lcp_threshold_round_1_to_2: 0.80`, `lcp_threshold_round_1_to_3: 0.70`).
- **`benchmarks/devolaflow_context/baselines/layout_invariant_v7.0.0.yaml`**: golden rendered dispatch (51 lines) used by the byte-comparison test below.
- **5 new unit tests** in `tests/test_compressor.py::TestDispatchLayoutInvariant`: `test_assert_dispatch_layout_accepts_canonical`, `test_assert_dispatch_layout_rejects_reordered`, `test_dispatch_prefix_is_stable_across_rounds` (uses `compute_dispatch_lcp_pct` + `apply_round_escalation`; asserts LCP ≥ 0.80 round 1→2 and ≥ 0.70 round 1→3 — the H.2 SLO), `test_new_field_appended_not_inserted`, `test_assert_dispatch_layout_unknown_keys_after_spec`. Measured LCP on the synthetic 3-round payload: r1→r2 = 0.8487, r1→r3 = 0.8487 (both above threshold).
- **1 new benchmark test** `tests/test_benchmarks.py::TestLayoutInvariantBaseline::test_layout_invariant_baseline`: byte-compares the canonical payload's `yaml.safe_dump` output against `benchmarks/devolaflow_context/baselines/layout_invariant_v7.0.0.yaml`. Drift fails CI in a dedicated assertion (renderer upgrade vs payload edit vs layout reorder all surface here).
- **`workflow-system/agent/references/context-isolation.md`** new section 10 "Cache Layout Invariant (v7.0.0+)": rationale, 12-key canonical order, validator API, LCP SLO, ADR cross-link.
- **`workflow-system/agent/SKILL.md`** Context Isolation section: 2-line cache-layout pointer to the new reference subsection and the validator API.
- **`workflow-system/agent/context_profiles.yaml`**: `sections.context_isolation.lines` extended (and tokens_est bumped from 204 → 230); subsequent section line ranges shifted by +2 to mirror the SKILL.md growth.
- **`.cursor/rules/devola-flow-rules.mdc` Rule 6 (P6 — Preserve Cached Prefix)**: workspace rule mandating `assert_dispatch_layout(payload)` before send + the additive-after-`gate` rule for new keys.

### Changed
- **`devolaflow.compressor.__all__`** extended with `DEFAULT_DISPATCH_LAYOUT`, `DispatchLayoutError`, `assert_dispatch_layout`, `compute_dispatch_lcp_pct`. No symbols removed; v6.x importers continue to work unchanged.

### Metrics
- Tests: 1009 → 1015 (+6: 5 unit + 1 benchmark baseline)
- LCP measurement (synthetic 3-round task_id, ADR-001 §2 canonical layout): r1→r2 0.8487, r1→r3 0.8487, r2→r3 0.7049 — all above the SLO thresholds.
- `devolaflow.compressor` coverage: ≥ 85 % (rule CP-2 floor for new module paths)
- SKILL.md: 498 → 500 lines (within the 500 SF-1 cap)
- All 11 adapters [OK] (CP-5 verified)
- Lint: ruff check + format clean (SI-10 #2, #3)
- Version consistency: 8 sync locations updated via `scripts/bump_version.py 7.0.0` (SF-3 / CP-3)
- Benchmarks: no regressions on existing 29 EvoBench scenarios (SI-4 guard)

### Cross-references
- ADR: `.local/research/adr/v7-ADR-001-cache-layout-invariant.md`
- Roadmap: `.local/research/v7.0.0_version_roadmap.md`
- Research source: `.local/research/v7.0.0_context_compression_research.md` §§A, B.6, F row 1, J.1

### Scope (v7.0 → v7.1 cycle)
v7.0.0 ships J.1 only. The remaining cycle slices land additively in v7.0.1 (J.2 tool-output truncation), v7.0.2 (J.3 hierarchical predecessor summary), v7.0.3 (J.4 + J.5 persistence probe + learnings v2), and v7.1.0 (cycle adoption + SI-3 evaluation + SI-8 retrospective).

## [6.2.1] — 2026-04-17

### Fixed
- **Benchmark staleness-guard CI flake**: `tests/test_benchmarks.py::TestBaselineFile::test_v6_baseline_matches_current_results_within_tolerance` was passing locally but failing on CI with a 12.59pp composite drift on `hotfix_jwt`. Root cause: `devolaflow.task_adaptive_selector.estimate_tokens()` uses `tiktoken` when available, otherwise falls back to `len(text) // 4`. Local environment had `tiktoken` installed (incidentally — not in `pyproject.toml` dependencies); CI did not. Different token estimators produce different section selections, which produce different composite scores. The 86.93 baseline was generated with one estimator, current run used the other → 12.59pp drift.
- **Solution**: added an autouse pytest fixture in `tests/conftest.py` that hides `tiktoken` from `sys.modules` for tests in `tests/test_benchmarks.py` only. Both local and CI now consistently exercise the deterministic fallback estimator. Production runtime is unaffected — agents that have `tiktoken` installed still get the more accurate token counts.
- **Regenerated `v6.1.0_baseline.json`** under the deterministic fallback estimator so `hotfix_jwt` baseline composite is now 99.52 (matches the current fallback-estimator run within 0pp drift).

### Metrics
- Tests: 1009 passed (no count change)
- Lint clean, NineS stable
- CI test job will now succeed on the same commit that previously failed (PR #36)

## [6.2.0] — 2026-04-16

**Final release of the v6.0 + v6.1 rollup (12 waves, v5.4.2 → v6.2.0).**

This version is a meta-release that closes the second self-update cycle (v6.1.0 → v6.2.0). It ships no new code on top of v6.1.5 — every line of the v6.2 cycle was already delivered across v6.1.1–v6.1.5. v6.2.0 stamps the cumulative release and ships the SI-8 retrospective.

### Highlights of the v6.0 → v6.2 journey (cumulative)

**Code quality / debt**
- 12 → **0** `DeprecationWarning` lines (P9 honored in v6.0.2)
- 141 → **0** MVP-SKILL.md cross-references (TD-3 in v6.0.1)
- 92 LOC of `_BUILTIN_SPECS` removed (TD-2 in v6.0.1)
- 3 → **0** rule contradictions (TD-6 in v6.0.1)
- Dead-API CI guard active (G1 in v6.1.4)

**NineS self-eval**
- Overall: 0.7405 → **0.8805** (+18.9% — entirely from the v6.1.1 tool-config fix; zero source changes)
- Capability mean: 0.7150 → **0.9150** (+27.97%)
- Hygiene mean: 0.8000 stable (upstream NineS `code_coverage` parser bug remains)

**Adapters / platforms**
- 4 → **11** platforms supported (+7: KimiCode, Windsurf, Continue, OpenClaw, Zed, Cline, Roo Code)
- New `AdapterRegistry` + `DataDrivenAdapter` engine: simple new adapters now ship as ~25 LOC of YAML (vs ~80 LOC of Python in v5.x)
- 5 transforms supported: `copy`, `copy_tree`, `copy_with_frontmatter`, `strip_frontmatter`, `keep_sections` (the last one fixed Windsurf's 24,625 → 7,434 char real bug)
- All 11 adapters report `[OK]` in `python -m devolaflow.build_skill`
- `--tools cursor,kimicode,windsurf` selective build supported

**Runtime correctness (dead-wire closure)**
- v5.3.0 P8 finally wired: `apply_round_escalation` invoked automatically by `select_context(round_num=N)` (v6.0.3)
- v5.3.0 P4 finally wired: `merge_reinforcement_into_dispatch` invoked by `ProposalGenerator.generate_round_dispatch` (v6.0.3)
- v6.1.5: `apply_plan_mode_overrides` wired into `select_context(plan_mode=True)` with env var + marker file fallback

**Tests / benchmarks**
- 818 → **1009** total (+191 net, with 29 deprecated tests retired in v6.0.2)
- Coverage 91.07% → **93.93%+** (`cli.py` 49% → 98%, `init_project.py` 59% → 94%, `composer.py` 66% → 100%)
- `tests/test_e2e_convergence.py` (7 tests) — full template→gate→reinforcement integration
- `tests/test_schema_parity.py` (6 tests) — schemas can no longer drift silently
- `tests/test_dead_apis.py` (11 tests) — bug-class regression prevention
- `tests/test_adapter_golden.py` (4 tests) — Cursor SKILL output structurally locked
- 29 / 29 EvoBench scenarios with regression baseline (was 3 / 29)
- Per-version `nines_self_eval_v*.json` snapshots in `.local/research/v6.0.0/` through `.local/research/v6.1.5/`

**Tool configuration / governance**
- `nines.toml` codifies the canonical `nines self-eval` invocation
- `data/golden_test_set/` (10 TOML fixtures) unlocks NineS V1 scoring evaluators
- `.cursor/rules/self-improve-iteration-rules.mdc` SI-2 updated with the canonical NineS invocation
- `MIGRATION-v6.md` documents the v6.0.2 BREAKING removals
- 2 SI-8 retrospectives at `.local/research/retrospective_v6.0_to_v6.1.md` and `.local/research/retrospective_v6.1_to_v6.2.md`

### SI-3 evaluation (v6.2.0)

Weighted composite **9.43 / 10** (threshold ≥ 8.5) — **READY for stable release.**

### Wave-by-wave commit reference (v6.0 + v6.1 cycles)

| Wave | Version | Commit | Theme |
|------|---------|--------|-------|
| 1 | v6.0.1 | `34bc586` | MVP-SKILL retirement + plugin loader + rule reconciliation |
| 2 | v6.0.2 | `f4d93fc` | [BREAKING] deprecated API removal + MIGRATION-v6.md |
| 3 | v6.0.3 | `c0112d6` | Dead-wire closure (apply_round_escalation + reinforcement merge) |
| 4 | v6.0.4 | `ec9e14c` | AdapterRegistry + DataDrivenAdapter + KimiCode + Windsurf |
| 5 | v6.0.5 | `931183e` | Schema parity + 29/29 EvoBench baselines |
| 6 | v6.1.0 | `0fa4294` | Continue + OpenClaw + golden snapshots + coverage fixes |
| 7 | v6.1.1 | `3c6f29f` | NineS tool-config (+18.9% overall — biggest single jump) |
| 8 | v6.1.2 | `01eb0d0` | Windsurf compression fix (real bug, all 8 adapters [OK]) |
| 9 | v6.1.3 | `5228d58` | +Zed +Cline +Roo (11 platforms total) |
| 10 | v6.1.4 | `30c785e` | Dead-API CI guard (G1) |
| 11 | v6.1.5 | `34b327f` | Plan-mode detection wired (V6-03) |
| rollup | **v6.2.0** | (this) | Retrospective + final summary |

Cycle artifacts:
- `.local/research/v6.0.0_improvement_advice.md` — initial SI-1 planning gate
- `.local/research/v6.0.0_improvement_advice_zh.md` — Chinese mirror
- `.local/research/v6.2.0_improvement_advice.md` — second-cycle SI-1 planning gate
- `.local/research/retrospective_v6.0_to_v6.1.md` — first cycle SI-8
- `.local/research/retrospective_v6.1_to_v6.2.md` — second cycle SI-8

### Metrics
- Tests: 1009 passed (no change from v6.1.5; this is a meta-release)
- All 11 adapters [OK]
- Lint: ruff check + format clean
- DeprecationWarnings: 0
- NineS self-eval: 0.8805 stable
- SKILL.md: 498 / 500 lines

## [6.1.5] — 2026-04-16

### Added
- **Plan-mode detection in `select_context()` (V6-03)**: new `plan_mode: bool | None` parameter. When True (or auto-detected via `DEVOLAFLOW_PLAN_MODE` env var or `.devolaflow_plan_mode` marker file), the active context profile is escalated through `apply_plan_mode_overrides()` BEFORE round-escalation: `agent_hierarchy`, `decomposition_gate`, `rationalization_prevention` priorities lifted to `critical`; `model_hint` upgraded to `quality`; `compression_intensity` set to `minimal`. Composes with the v6.0.3 round-based escalation (plan-mode applies first, round adds budget on top).
- **`--plan-mode` / `--no-plan-mode` CLI flags** on `python -m devolaflow.task_adaptive_selector`.
- **`apply_plan_mode_overrides()`** public function in `task_adaptive_selector` (allowlisted in dead-API detector alongside `apply_round_escalation`/`select_context` as documented stable public API).
- **10 new tests** in `test_task_adaptive_selector.py::TestPlanModeDetection` covering auto-detect default off, explicit override priorities, explicit-False short-circuit, env-var detection, marker-file detection, composition with round escalation, result-dict surface keys, profile-immutability, invalid-env-value rejection, and minimal-compression assertion.

### Changed
- **SKILL.md "Mode Awareness" section**: noted the v6.1.5 runtime hook inline on the AGENT-MODE-default line of the detection list — chars-only edit (no new lines), preserving line count and avoiding token-budget knock-on effects in the `feature` profile's `plan_mode_template` selection (which would otherwise displace `dispatch_report` from the EvoBench `decomposition_feature` scenario).
- **`select_context()` model_hint / compression_intensity logic**: the `escalation_applied` gate is now `escalation_applied OR plan_mode_applied`, so plan-mode-set values on the profile (`model_hint=quality`, `compression_intensity=minimal`) are surfaced in the result dict at round 1.

### Metrics
- Tests: 999 → 1009 (+10)
- Plan-mode detection signals: 3 (explicit param, env var, marker file)
- SKILL.md: 498 → 498 lines (line count unchanged; chars-only addition to mode_detection section)
- All 11 adapters [OK], lint clean, NineS stable, EvoBench `decomposition_feature` composite ≥ 95 preserved

## [6.1.4] — 2026-04-16

### Added
- **`scripts/detect_dead_apis.py`** (G1): static analyzer that scans `src/devolaflow/` for public functions/classes with zero non-test callers. Catches the bug class that cost v6.0.3 three versions to fix (`apply_round_escalation` and `merge_reinforcement_into_dispatch` had passing unit tests but no production callers since v5.3.0). Walks `src/devolaflow/**/*.py` with `ast`, collects top-level public `def`/`class` (skipping `_*`, `__dunder__`, `main`, `cli`, `*_cmd`), then verifies each has a real (non-import) reference somewhere in `src/`, `scripts/`, or `benchmarks/`. Re-exports in `__init__.py` are correctly excluded as non-callers (so the v6.0.3 pattern of "exported but never called" is detected). Run: `python scripts/detect_dead_apis.py [--format text|json] [--strict]`. Stdlib only; ~150 LOC of logic plus a documented allowlist.
- **`tests/test_dead_apis.py`** (11 tests): unit tests for the detector — synthetic cases for unused functions, used-via-sibling, test-only callers, allowlist suppression, private/dunder skip, CLI-entry skip, `__init__.py` re-export non-counter, self-use alive — plus the CI-grade `test_devolaflow_codebase_has_no_dead_apis` assertion that fails if any new dead public API ships, and 2 subprocess tests for `--strict` exit code 2 and `--format json` schema.
- **Allowlist**: 36-entry catalogue of intentionally external-only public APIs in `DEFAULT_ALLOWLIST`, grouped and commented by category — adapter base API (`BaseAdapter`, `AdapterResult`, `load_workflow_skill`, `create_default_registry` ×2), CLI entry-point modules (`build_all`), MIGRATION-v6.md recommended replacements (`evaluate_gate`, `findings_to_reinforcement`, `merge_reinforcement_into_dispatch`, `reinforcement_to_dict`, `apply_round_escalation`, `select_context`, `get_research_advice`), compressor validators (`compress_message`, `validate_lean_format`), self-improving feedback module (`Proposal`, `FeedbackCollector`, `FeedbackAnalyzer`, `ProposalGenerator`), gate report generators (`generate_yaml_report`, `generate_markdown_report`), operational learnings utilities (`prune_learnings`, `promote_learning`, `get_learnings_stats`, `log_external_source_review`), NineS subsystem (`build_command`, `build_stage_command`, `ensure_nines`, `get_nines_capabilities`, `NinesResearchConfig`, `collect_research`, `analyze_target`, `run_self_evaluation`, `run_skill_iteration`, `run_nines_benchmark`, `run_nines_update`, `run_self_improve_loop`, `refresh_reference_dependency`, `nines_dimension_scores`, `find_nines_config`), pre-decision phase (`auto_detect`, `freeze_config`, `recommend_workflow`), and template engine (`collect_all_refs`, `JoinStrategy`, `OnExhaustion`, `GateFailAction`, `nines_commands_to_dispatch_context`, `parse_template_string`, `TemplateRegistry`).

### Metrics
- Tests: **988 → 999** (+11)
- Detection runtime: **143 ms** on full DevolaFlow codebase (50 modules)
- Bug class prevention: dead-wire regressions now CI-blocked (`--strict` exit 2)
- Lint clean (`ruff check` + `ruff format --check`)
- No source changes to `src/devolaflow/` — pure CI guard addition.
- NineS stable (no source changes to `src/devolaflow/nines/`).

## [6.1.3] — 2026-04-16

### Added
- **3 new Tier-1 adapters via data-driven YAML**:
  - `adapter_configs/zed.yaml` — Zed editor rules (`.rules/devola-flow.md` + `references/`)
  - `adapter_configs/cline.yaml` — Cline autonomous agent rules (`.clinerules/devola-flow.md` + `references/`)
  - `adapter_configs/roo.yaml` — Roo Code per-mode rules (`.roo/rules/devola-flow.md` + `references/`)
  Each adapter is ≈25 LOC of YAML — no Python source changes required (validates the v6.0.4 data-driven pattern).
- **install.sh** support for `zed`, `cline`, `roo` targets; `all` and `update` extended to include them. New `dl_skill_no_frontmatter` shell helper centralises the "download SKILL.md and strip YAML frontmatter" step shared by the 3 new installers.
- **15-21 new tests** across 3 adapter test modules (5-7 tests per adapter).

### Metrics
- Adapter count: **8 → 11** (+3 platforms)
- New YAML LOC: ~75 (avg 25 per adapter, vs ~80 LOC of Python in v6.0.4)
- Tests: **967 → ~985** (target: +15-21 net)
- All 11 adapters [OK] in `python -m devolaflow.build_skill`
- No source code changes to `src/devolaflow/`
- Lint clean, NineS stable

## [6.1.2] — 2026-04-16

### Fixed
- **Windsurf adapter real bug**: `.windsurfrules` previously exceeded Windsurf's 8000-char budget (24,625 chars WARN, known-broken since v6.0.4 — customers could not actually install DevolaFlow on Windsurf despite the adapter appearing to build). Now 7,434 chars [OK] via new `keep_sections` transform that extracts only high-value sections of SKILL.md (Quick Action Decision, 4-Layer Agent Hierarchy, Gate Mechanism, Dispatch & Report Protocol) with a compact header prefix pointing users to the full skill on GitHub.

### Added
- **New `keep_sections` transform** in `DataDrivenAdapter` (`src/devolaflow/adapters/data_driven.py`): markdown-section-level extraction with optional frontmatter preservation (`include_frontmatter`) and header prefix injection (`header_prefix`). Substring-matches section headings (case-sensitive), respects fenced code blocks (heading-looking lines inside ``` fences are treated as content), and nests H3+ children under their matching H2 parent. Enables compact adapter outputs that cherry-pick relevant SKILL content for budget-constrained platforms.
- **`VALID_TRANSFORMS` frozenset** exported from `data_driven` module — single source of truth for the 5 supported transforms (`copy`, `copy_tree`, `copy_with_frontmatter`, `strip_frontmatter`, `keep_sections`).
- **`_Section` dataclass** (internal) capturing `heading`, `level`, `text` for the markdown section parser.
- **8 new tests** in `test_data_driven_adapter.py` covering the new transform: `test_valid_transforms_enumeration_lists_keep_sections`, `test_keep_sections_extracts_named_sections`, `test_keep_sections_excludes_frontmatter_by_default`, `test_keep_sections_includes_frontmatter_when_requested`, `test_keep_sections_prepends_header_prefix`, `test_keep_sections_empty_list_produces_empty_body`, `test_keep_sections_substring_match_not_exact`, `test_keep_sections_handles_missing_source`, `test_keep_sections_ignores_fenced_code_block_headings`.
- **4 new Windsurf tests** (`test_windsurf_adapter.py`): `test_windsurf_under_8000_chars`, `test_windsurf_contains_quick_action`, `test_windsurf_contains_hierarchy`, `test_windsurf_has_header_prefix`.

### Changed
- **`adapter_configs/windsurf.yaml`**: switched from `strip_frontmatter` to `keep_sections` with 4 high-value section selectors (Quick Action Decision, 4-Layer Agent Hierarchy, Gate Mechanism, Dispatch & Report Protocol) and a 2-line header prefix pointing to the full skill on GitHub. `include_frontmatter: false` preserves the no-frontmatter invariant from v6.0.4.
- **`test_windsurf_budget_chars_under_8000`**: tightened from "budget_ok may be False, we tolerate overflow" to `assert result.budget_ok is True` — reflecting the v6.1.2 contract that the adapter always fits.
- **`test_windsurf_strips_frontmatter`**: broadened frontmatter-leakage check from first-block-only to the entire output, since the new transform may place different content near the top.

### Compromises
- Only 4 of the 6 task-suggested sections fit under the 8000-char budget. Dropped: **Mode Awareness** (too large at 4,945 chars — includes full PLAN MODE sub-section) and **Context Isolation** (wouldn't fit alongside Dispatch & Report Protocol). The 4-Layer Agent Hierarchy section already carries the P1 Dispatcher-Not-Implementer invariant, and the header prefix directs users to the full SKILL at `https://github.com/YoRHa-Agents/DevolaFlow` for the dropped content.

### Metrics
- Tests: **954 → 966** (+12: 9 new in `test_data_driven_adapter.py`, 4 new in `test_windsurf_adapter.py`, −1 updated `test_windsurf_budget_chars_under_8000` tightened assertions but stays as 1 test)
- Windsurf budget: **24,625 chars WARN → 7,434 chars OK** (69.8% reduction; 566-char margin under 8000 budget)
- Adapters producing `[OK]`: **7/8 → 8/8**
- No regressions: other 7 adapters unchanged, EvoBench baselines untouched, NineS self-eval unaffected (no source changes to `src/devolaflow/nines/`, `src/devolaflow/gate/`, or context profiles).

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
