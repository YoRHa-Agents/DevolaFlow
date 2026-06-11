# DevolaFlow Repo-Internal Design-Logic Review (v15 cycle entry)

- **Date:** 2026-06-12
- **Reviewer:** L3 research agent (v14.2.0 T1)
- **Baseline:** v14.1.0 (`cc54dda 2026-06-05 Merge pull request #144 from YoRHa-Agents/feat/v14.1.0-release`), 4715 tests collected, ruff clean
- **Scope:** internal design logic across 5 dimensions; feeds SI-1 gap analysis for the ladder v14.2.0 → v14.3.0 → v14.4.0 → v14.5.0 → v15.0.0 (MAJOR rollup)
- **Method:** direct file reads + bounded shell measurement; all quotes verbatim per C-3

---

## §1 Rule corpus rationality

Measured state: `.rules/soul.mdc` 10 rules / `architecture.mdc` 7 / `conventions.mdc` 9 / `workflow.mdc` 24 / `style.mdc` 13 (DS+WX as ST-1..ST-13) = **63 total**. Compiled `AGENTS.md` = 902 lines carrying 50 rules (S/A/C/W); `.cursor/rules/repo-governance.mdc` = 980 lines carrying all 63.

### F-R1 — Triple-loading of the rule corpus into every agent session — **critical**
- **Evidence:** `.cursor/rules/change-process-rules.mdc`, `context-optimization-rules.mdc`, `self-improve-iteration-rules.mdc`, `skill-format-rules.mdc` all carry `alwaysApply: true` frontmatter, AND `repo-governance.mdc` carries `alwaysApply: true`, AND `AGENTS.md` (902 lines) auto-loads. `.rules/index.md` Source Mapping confirms the legacy files were fully migrated: `self-improve-iteration-rules.mdc → P3 Workflow (SI-1–SI-10)`, `change-process-rules.mdc → P0 Soul (CP-1, CP-2), P2 Conventions (CP-7), P3 Workflow (CP-3–CP-6)`. Total always-loaded rule text: `.cursor/rules/*.mdc` = 3615 lines + `AGENTS.md` 902 lines + `CLAUDE.md`; SI-1..SI-10 appear verbatim twice (as SI-* and again as W-1..W-9), CP-* content three times (CP-*, C-1/W-10..13, S-3/S-4).
- **Impact:** every session — including every L3 Task Agent budgeted at "~8K tokens" per A-3 — pays the corpus 2–3×. Directly contradicts A-1 P2 "Each agent layer receives only the context it needs". This is the single largest per-dispatch context-waste in the repo.
- **Recommendation:** convert the 4 migrated legacy files to deprecated pointer stubs (exact pattern already proven by `workflow-rules.mdc` / `devola-flow-rules.mdc`: "This stub remains as a discoverable cross-reference"). Zero behaviour change; reclaims ~300 lines × every session and removes the contradiction surface (see F-R7).

### F-R2 — Rule-cap denominator mismatch: corpus is over its own documented cap — **major**
- **Evidence:** `.rules/index.md` line 5: "Total rules: **63** … cap 60 HARD per ADR-007 D5". The enforcement test counts a different denominator — `tests/test_no_ghost_features.py:1220`: "test_rule_count_under_cap — total compiled-AGENTS.md rule count ≤ 60 (HARD per ADR-007 D5). Rule count = sum of `^## ([SACW]|ST)-\d+` headings in AGENTS.md", with `_RULE_COUNT_CAP_HARD: int = 60` (line 1240). AGENTS.md contains 50 S/A/C/W headings and zero ST headings (Style compiles only to the cursor target), so the test passes at 50/60 while the documented corpus total is 63.
- **Impact:** the regex includes `ST` for a surface where ST never appears — the cap silently excludes 13 rules. Either the corpus violates its own 60 cap, or the cap means "AGENTS.md only" and index.md misstates it. Governance number that operators quote is ambiguous.
- **Recommendation:** ADR amendment pinning the denominator (recommend: full-corpus 63 ≤ cap, raise cap or run a rule-diet at v15.0.0), then make the test count the canonical denominator.

### F-R3 — `.rules/index.md` stale per-layer counts — **minor**
- **Evidence:** `.rules/index.md` line 10: "Architecture | `architecture.mdc` | P1 | Yes | 5 (A-1..A-5)" — actual `architecture.mdc` contains 7 (`## A-1` … `## A-7`; A-6 v9.2.0, A-7 v11.1.0).
- **Impact:** the corpus's own index lies about layer size; small but it is the file that documents the cap.
- **Recommendation:** v14.2.x doc fix; add an index-vs-on-disk parity assertion to the existing rule-count test.

### F-R4 — Compile-budget saturation with **silent layer drops** (S-5 violation pattern) — **major**
- **Evidence:** `.rules/index.md` line 28: "Pre-v11.4.0 cursor utilization was 11979/12000 (saturated; W-24 push silently dropped the Style Rules layer)". `.rules/compile-config.yaml` comment: "~8180/8000 (over budget, dropped workflow layer)". Budget history: 8000 → 12000 (v9.0.0 PV-07) → 14000 (v11.4.0); current utilization "12740/14000 (~9% headroom)".
- **Impact:** the compiler's overflow behaviour is *drop a whole layer silently* — twice in history an entire rule layer vanished from the compiled output until noticed. This is exactly the failure S-5 prohibits, in the tool that distributes S-5.
- **Recommendation:** make `RuleCompiler` fail hard (non-zero exit) on budget overflow instead of dropping; land in v14.2.x (small, testable). The recurring bump-the-budget pattern is the symptom; F-R5 is the cause.

### F-R5 — Workflow layer growth is unbounded by design: +1 W-rule per minor cycle — **major**
- **Evidence:** `workflow.mdc` holds 24 of the 50 compiled rules. Per `.rules/index.md` line 12: "W-16..W-20 added v8.5.0 … W-21 added v9.0.0 … W-22 + W-23 added v11.3.0 … W-24 added v11.4.0". Recent W-rules embed full design rationale (W-22 has 4 subsections; W-24 has 5 subsections + risk-register citations).
- **Impact:** at the observed rate, the planned 5-version ladder adds ~3–5 more W-rules, re-saturating the 14000 budget and the 60 cap mid-cycle. Rule bodies double as ADR narrative ("Source: v11.4.0 SI-1 gap analysis §4 + §5 + §7 + §8 risk register"), inflating every prompt with history that belongs in `docs/cycle-archive/`.
- **Recommendation:** v15.0.0 rule-diet: strip `Source:`/history blocks from rule bodies into ADRs (rule = normative statement + enforcement pointer only); fold W-10..W-15 (pure CP-*/CO-* mirrors) into their C-* duplicates.

### F-R6 — Dead rule: C-8 governs a language absent from the repo — **minor**
- **Evidence:** `conventions.mdc` / compiled `AGENTS.md`: "## C-8 — Always Use Braces for If — Always use braces for if, else if, and else branches in C++." Measured: `find . -name "*.cpp" -o -name "*.cc" -o -name "*.hpp" -o -name "*.cxx"` → **0 files**.
- **Impact:** pure cost (carried in every compiled output and every session) with zero benefit; also a counter-example to the cap-pressure story — the corpus retains dead rules while bumping budgets.
- **Recommendation:** delete in v14.2.x (frees one slot under the cap).

### F-R7 — Always-applied rule files give contradictory counts for the same artifacts — **major**
- **Evidence:** `.cursor/rules/skill-format-rules.mdc` SF-1 (alwaysApply: true): "Large | ≤ 1000 | `workflow-system/agent/references/*.md` (10 files)" and "XL | ≤ 1600 | `workflow-system/agent/examples/*.md` (3 files)" and "the canonical 14-file set listed in `scripts/sync_cursor_skill.py::MIRRORED_FILES`". Measured reality: `ls workflow-system/agent/references/ | wc -l` → **24**; `examples/` → **4**; `MIRRORED_FILES` → **27 entries**. Compiled C-4 says "references/*.md (24 files)". SF-4 likewise lists "Current valid references:" with only 10 names.
- **Impact:** two always-on rule surfaces disagree by 2.4× on the same invariant; an agent following SF-1/SF-4 literally would mis-validate. Confirms F-R1's stub-conversion as the fix rather than dual maintenance.
- **Recommendation:** same stub conversion as F-R1 (v14.2.x); single source remains C-4/C-7 + `tests/test_reference_size_budgets.py`.

### F-R8 — W-21 Soul-freeze health: GREEN — **info**
- **Evidence:** `soul.mdc` = 10 rules (S-1..S-10); W-21: "Current Soul-set freeze locks at **10 entries** (S-1..S-10) at v9.0.0 release"; cap 12. No pending S-11 telegraph found in recent retros.
- **Impact:** the one rule-governance mechanism with real friction (2-cycle telegraph) has demonstrably held since v9.0.0 — five cycles of additions all landed at A-*/W-* instead. Model to emulate for the W-layer.
- **Recommendation:** none required; consider an analogous "W-set telegraph" at v15.0.0 (see F-R5).

### F-R9 — W-17's published verification recipe cannot work — **minor**
- **Evidence:** W-17 (`workflow.mdc` / AGENTS.md): "git diff <previous-tag>..HEAD --stat -- tests/ | grep -cE \"test_[a-z_]+\\(.*\\):\"" — `git diff --stat` emits filenames + change-count bars, never function definitions; the grep matches 0 lines for any diff. The "what the cap actually counts" command is structurally broken.
- **Impact:** the per-PV ≤+30 test cap has no working measurement procedure; compliance is asserted, not measured (rule-without-enforcement-surface class).
- **Recommendation:** v14.2.x: replace with `git diff <tag>..HEAD -- tests/ | grep -cE '^\+\s*def test_'` and/or a collect-only delta script; same patch can wire it into the PV-05 mid-cycle audit.

---

## §2 Schema governance

Measured state: `schemas/lean-dispatch.yaml` = 739 lines; `layout_invariant.version: 6`; `canonical_order` = 17 keys (12 FROZEN PREFIX + 5 append-only tail ending `predecessor_dedup_ledger # pos 17 — v9.7.0 PV-02`); `tests/test_layout_invariant_multi_baseline.py` = 884 lines.

### F-R10 — A-2 frozen-prefix mechanism is working as designed — **info**
- **Evidence:** `canonical_order` length has been stable at 17 since v9.7.0 (4+ minor cycles). The v12.0.0 schema comment: "gate.subagent_pattern NEST (A-2.3); canonical_order length STAYS at 17 and version STAYS at 6 … absence is canonical, so all 14 prior baselines pass byte-identically."
- **Impact:** the NEST-vs-APPEND decision rule (A-2.3) is demonstrably steering additions into NESTs (`gate.cascade_required`, `gate.cascade_min_layers`, `gate.subagent_pattern`) — cache-prefix length preserved. The core governance benefit is real.
- **Recommendation:** keep; the costs are at the edges (F-R11, F-R12, F-R14).

### F-R11 — Baseline-artifact sprawl: 62 files, including 14 dead v3.2.0 relics — **major**
- **Evidence:** `benchmarks/devolaflow_context/baselines/` contains 10 `layout_invariant_v*.yaml` goldens + 38 `v*_baseline.json` (every minor from v2.1.0 through v14.1.0) + 14 `v3.2.0_round_*.json` + `v9.3.0_latency.json`/`v9.7.0_latency*.json`. A-2.4: "Future schema bumps MUST add a new golden YAML for the new baseline AND keep all prior baselines passing."
- **Impact:** keep-all-forever makes the baseline directory monotone-growing with no retirement path; the 14 `v3.2.0_round_*.json` files serve no current test on a 15-version-old format. Each schema bump permanently adds CI work and reader confusion about which baseline is load-bearing.
- **Recommendation:** ADR (see §7-D2) defining a tiering policy: permanently keep the v7.0.0 frozen-prefix witness + each schema-version bump witness (5 files); move per-minor JSON baselines older than 2 cycles to `docs/cycle-archive/`. Prune `v3.2.0_round_*` in v14.3.0.

### F-R12 — Schema file is 66% comments and the comments drift — **minor**
- **Evidence:** 485 of 739 lines in `schemas/lean-dispatch.yaml` are comments. Stale: line 126 "# length stays 13 and version stays 2 (P6 cache-layout invariant" and line 163 "# stays 13 and version stays 2 (P6 cache-layout invariant preserved" — actual length is 17, version 6.
- **Impact:** the schema doubles as a history ledger; historical "stays N" claims fossilize and now state false invariants in the canonical schema file. Readers must know which comments are era-scoped.
- **Recommendation:** v14.2.x: rewrite stale absolutes as era-scoped ("at v8.0.0: stayed 13/2"); longer term, move per-PV narration to cycle archives, keep schema comments declarative.

### F-R13 — `backward_compat` block hand-mirrors the test matrix — **minor**
- **Evidence:** `lean-dispatch.yaml` lines 719-738: `v7_0_0_baseline_passes: true` … `v10_2_0_baseline_passes: true` — ten hand-maintained boolean keys restating what `tests/test_layout_invariant_multi_baseline.py` proves on every run.
- **Impact:** a write-only sync point: booleans that can never legitimately be false (CI would fail first), updated by hand at each bump per A-2.4. Pure maintenance cost.
- **Recommendation:** replace the boolean list with one comment pointing at the test file; fold into the F-R11 ADR.

### F-R14 — A-5 SSOT registry table is point-in-time and already superseded — **minor**
- **Evidence:** A-5 in compiled corpus: "The current 5 SSOT registries (v8.4.3 baseline)" — while `tests/test_no_ghost_features.py:1199` enforces single-ownership generically ("module-level owners {rel_definers}; expected exactly 1"). The rule's enumerated table is frozen at v8.4.3 while the codebase has since added registry-like surfaces (e.g. `adapter_configs/` 12-file catalog, `src/devolaflow/adapters/registry.py`).
- **Impact:** the normative content (single owner) is enforced by AST test and healthy; the enumerated table in the rule body is the stale part — same rule-body-as-snapshot disease as F-R5.
- **Recommendation:** v15.0.0 rule-diet: keep A-5.1 normative text, drop the version-stamped table (test is the live inventory).

---

## §3 Module architecture hotspots

Measured: 137 modules, 48,355 LOC under `src/devolaflow/`. Top of `wc -l | sort -rn`: `gate/scorer.py` 2545, `compressor/transforms.py` 2198, `task_adaptive_selector.py` 2051, `agent_workspace/reporter.py` 1783, `plugins/installer.py` 1710, `shell_proxy/commands.py` 1268, `learnings.py` 1052, `feedback.py` 987.

### F-R15 — `gate/scorer.py` (2545 lines, 57 top-level defs) bundles ≥6 distinct concerns — **major**
- **Evidence:** symbol map shows in one file: cascade enforcement (`class CascadeViolationError` line 100, `validate_cascade_gate_fields` line 179 — A-7 dispatch-shape validation, not scoring); pure scoring (`quality_score` 360, `composite_score` 370, `visual_fidelity_score` 388); 6-rung ladder (`_check_lint` 894 … `evaluate_ladder` 1219); acceptance-criteria-v2 execution incl. a subprocess runner (`_default_command_runner` 1620, `evaluate_acceptance_criteria_v2` 1658); budget/cycle/ratchet/complexity/legibility attachment (`_apply_breaker_check` 1887 … `_apply_complexity_and_legibility` 1977); orchestration (`evaluate_gate` 2016) plus `import argparse` for a CLI.
- **Impact:** cohesion is low — cascade validation has zero data dependency on scoring (its own docstring says "The validator does NOT modify `evaluate_gate` or any existing scorer function"); every W-11 "full gate test suite" obligation and every gate change funnels reviewers through a 2.5K-line file. Cheapest-to-extract concern (cascade) is also the one most likely to change at v15.0.0 strict-flip.
- **Recommendation:** v14.5.0 split with re-export shims preserving import paths: `gate/cascade.py` (lines ~100–360), `gate/ladder.py` (~863–1352), `gate/acceptance_v2.py` (~1606–1820), keep `scorer.py` = pure scoring + `evaluate_gate` orchestration. Needs §7-D3 ADR (public import surface).

### F-R16 — `task_adaptive_selector.py` (2051 lines) carries 3 separable subsystems — **major**
- **Evidence:** symbol map: core selection (`load_profiles` 315 … `select_context` 1085); a complete AGENTS.md-slicing subsystem (`_agents_md_slice_env_override` 1403, `_split_agents_md_into_layers` 1479, `count_agents_md_rules` 1531, `select_agents_md_slice` 1658 — ~380 lines); and a CLI block (`_print_cli_usage` 1788 … `main()` 1889 — ~190 lines across 8 functions).
- **Impact:** the module CP-6/W-13 marks as benchmark-coupled (any change → EvoBench run) includes pure CLI printing helpers — formatting tweaks trigger heavyweight verification obligations. The AGENTS.md slicer is conceptually a rules-distribution concern (pairs with `local/compiler.py`), not context selection.
- **Recommendation:** v14.5.0: extract `agents_md_slice.py` and `selector_cli.py` (re-export shims); scope the W-13 benchmark trigger to the selection core.

### F-R17 — `context_profiles.yaml` (2414 lines): 17 near-duplicate priority maps + 4 orphan top-level keys — **major**
- **Evidence:** top-level keys: `meta:` (11), `section_anchors:` (482), `sections:` (542), `profiles:` (756), then **outside** `profiles:` at column 0: `complex_feature:` (2222), `abstractive_llm:` (2275), `legibility_audit:` (2335), `session_state:` (2387). Under `profiles:` are 17 profiles (hotfix…entropy_scan) each repeating a full `section_priorities:` map (~103 column-2 section keys exist; e.g. hotfix lists `frontmatter: skip`, `version_update: skip`, `quick_action_decision: critical`, … per profile).
- **Impact:** adding one SKILL.md section requires touching up to 17 priority maps; omissions are silent (W-15 verification is manual `--verbose` inspection). The 4 orphan blocks (summary-mode configs) sharing the file/namespace with profiles invites key-collision and confuses `match_profile` semantics.
- **Recommendation:** v14.4.0: introduce `defaults:` + per-profile delta overlay (selector already centralizes loading at `_load_profiles_cached`, so this is one-module change + benchmark run per W-6/W-13); relocate the 4 summary-mode blocks under an explicit `summary_modes:` parent in the same change.

### F-R18 — `feedback.py` hosts dispatch-schema population and wave execution alongside feedback — **minor**
- **Evidence:** symbol map: `class FeedbackCollector` 89, `class FeedbackAnalyzer` 138, `class ProposalGenerator` 262, then `populate_cascade_gate_fields` 543 (the function `schemas/lean-dispatch.yaml` line 683 names as its own populator: "`src/devolaflow/feedback.py::populate_cascade_gate_fields` populates `gate.subagent_pattern`"), `dispatch_wave_tasks` 755, `dispatch_dogfood_cycle` 879.
- **Impact:** the schema's canonical populator lives in a module named for a different concern; S-10 binds `ProposalGenerator.generate_round_dispatch` to the hook chain, so this file is simultaneously feedback-domain and dispatch-infrastructure — two reasons to change.
- **Recommendation:** bundle with the F-R15 v14.5.0 refactor: move `populate_cascade_gate_fields` beside the cascade module; move `dispatch_wave_tasks`/`dispatch_dogfood_cycle` to a dispatch module. Re-export shims mandatory (S-10 names the path).

### F-R19 — Secondary hotspots are domain-cohesive; no action — **info**
- **Evidence:** `compressor/transforms.py` 2198 (one transform family), `agent_workspace/reporter.py` 1783, `plugins/installer.py` 1710, `shell_proxy/commands.py` 1268 — each maps to a single A-5 registry or one subsystem.
- **Impact:** size alone is not the criterion; these show high cohesion unlike F-R15/F-R16.
- **Recommendation:** defer-next-cycle; monitor `reporter.py` (mixed report formats) if it crosses ~2K lines.

---

## §4 Test architecture

Measured: 178 test files, 4053 `def test_` functions, 4715 collected (expansion ratio 1.16×); full suite ~3.7 min (given); `tests/test_version.py` + `tests/test_benchmarks.py` together = "71 passed … in 1.93s".

### F-R20 — `test_no_ghost_features.py`: 12,405 lines, 24× growth in ~7 weeks, structurally unbounded — **critical**
- **Evidence:** current `wc -l` = **12405**; at introduction ("9628d6c 2026-04-20 chore(release): DevolaFlow v7.4.4 — P-01 anti-ghost test infrastructure") it was **517** lines. Composition: 108 `def test_` functions, 2255 comment lines, 118 banner-comment section dividers. Growth is mandated: W-18 requires "before a PV authors a CHANGELOG entry mentioning a feature, the ghost-audit (`tests/test_no_ghost_features.py`) MUST be refreshed" — every feature in every PV appends to this one file forever.
- **Impact:** the file is on track to exceed the entire `gate/` package within 2 cycles; per-test average ~115 lines (mostly prose). It is simultaneously: rule-cap enforcer, SF-4 reference-set pin, SSOT registry lint, compile-drift check, and per-feature ghost audit — a god-test-file with the worst merge-conflict surface in the repo (every concurrent PV touches it).
- **Recommendation:** v14.3.0: split into `tests/ghost/` package by domain (rules / schema / registries / per-cycle features), keep the W-18 contract by renaming the target to the package; archive per-cycle feature audits older than 2 cycles to a slow-lane marker. Needs §7-D4 ADR (W-18 names the file path verbatim in an always-applied rule).

### F-R21 — Count-pin sprawl: ≥8 hardcoded inventory pins that break on every legitimate addition — **major**
- **Evidence (verbatim):** `tests/test_adapter_golden.py:190` "assert len(actual) == 24, f\"expected 24 reference files, got {len(actual)}\"" and `:205` "assert len(actual) == 4, f\"expected 4 example files, got {len(actual)}\""; `tests/test_agent_workspace_schemas.py:1038` "assert len(files) == 10, f\"expected exactly 10 schema files, got {len(files)}\"" and `:1048` "assert artifact_count == 9"; `tests/test_ac_generator.py:101` "assert len(canonical) == 17"; `tests/test_audit_canonical_order_emptiness.py:85` "assert len(report.rows) == 17" (and `:176`).
- **Impact:** the canonical_order-17 pins are *intentional* A-2 governance and correct. The file-inventory pins (24/4/10/9) are incidental: adding one reference file (a routine C-7 4-step procedure) requires editing 3+ test files in addition to `_SF4_REFERENCE_SET` (`test_no_ghost_features.py:448`). Friction lands on exactly the doc/skill additions that serve L3 quality.
- **Recommendation:** v14.2.x: for incidental pins, derive expected counts from the SSOT (e.g. `len(_SF4_REFERENCE_SET)`, `MIRRORED_FILES`) so one edit propagates; keep explicit literals only where the pin IS the governance (canonical_order, Soul count).

### F-R22 — Parametrize discipline below W-17's stated preference — **minor**
- **Evidence:** 4053 test functions → 4715 collected = 1.16× expansion. W-17: "Parametrize expansions of EXISTING test functions over newly-added data … do NOT count toward the cap — those are cheap schema checks".
- **Impact:** the cap's escape valve (parametrize) is barely used; combined with F-R9 (broken measurement recipe), W-17 is aspirational. The "+150/cycle" ceiling cannot currently be audited mechanically.
- **Recommendation:** fix measurement (F-R9) first; then in v14.3.0 convert inventory-style suites (adapters × golden assertions, baselines × byte-checks) to parametrized fixtures — the same change that fixes F-R21.

### F-R23 — SI-10 chain: rule text (6 steps) vs Makefile (7 gates) drift; steps 4–5 are subsets of step 1 — **minor**
- **Evidence:** compiled W-9 lists 6 numbered steps ending "6. `make check-cursor-skill` — exit 0". `Makefile` comment at `precommit-full`: "the SI-10 invariant remains unchanged at 7 gates" with `iteration-delta-gate: python -m pytest tests/test_sichip_iteration_delta_gate.py` as the 7th, and `release-preflight: lint test validate-templates build-skill sync-human-docs check-cursor-skill compile-rules check-drift check-rules-drift iteration-delta-gate` = 10 targets. Steps 4 (`tests/test_version.py`) and 5 (`tests/test_benchmarks.py`) re-run 71 tests (1.93 s) already executed inside step 1's full run.
- **Impact:** runtime cost is trivial; the real cost is normative ambiguity — "all 6 must pass" vs "7 gates" vs 10 preflight targets means operators cannot state the gate set precisely. The redundant steps also train agents to treat the checklist as ritual rather than measurement.
- **Recommendation:** v14.2.x: re-compile W-9 to enumerate the Makefile's actual gate set (single source: `release-preflight` target); note steps 4–5 as "subset re-verification, skippable when step 1 ran in the same working tree".

### F-R24 — Suite runtime and fast-path are healthy — **info**
- **Evidence:** 4715 tests / ~3.7 min full; `precommit-fast` exists ("v10.4.0 PV-05 (D-X-3) — SI-10 fast-path / full-path split … ruff + smoke pytest (`-x --lf`)").
- **Impact:** wall-clock is not the bottleneck; maintenance surface (F-R20/F-R21) is.
- **Recommendation:** none; protect the 3.7 min by enforcing W-17 once measurable.

---

## §5 Version sync machinery

### F-R25 — Release-time sync fan-out spans ≥6 independent mechanisms; rule text undercounts the script — **major**
- **Evidence:** `scripts/bump_version.py::VERSION_LOCATIONS` contains **11** pattern entries across 8 files (SKILL.md ×3 patterns, README.md ×2), while CP-3 states "The script performs 7 pattern replacements across the canonical files". Beyond the script: ST-7 "Whenever `__version__` changes, `workflow-system/human/demo/version-timeline/versions.json` MUST gain a new entry in the same PR" (hand-edited); `make sync-human-docs` (driver `scripts/generate_human_docs.py` = **2065 lines**, regenerating 8 EN + 8 ZH guides); `scripts/sync_cursor_skill.py` (27 `MIRRORED_FILES`, opt-in); `compile-rules` + `.rules/.compile-hashes.json`; CHANGELOG.
- **Impact:** a version bump is a 6-mechanism choreography; the always-applied rule misdescribes the primary script's own size. Each mechanism has its own drift detector (test_version.py, check-drift, check-rules-drift, check-cursor-skill) — detection is good, but the *number of places a version string lives* is the root cost.
- **Recommendation:** v14.4.0: reduce sync points — README badge and demo `SAMPLE_DATA` version can be render-time injected (badge via shields URL param already; HTML via the existing `generate_human_docs.py` pass), eliminating 3 of 11 patterns; correct CP-3's count at next recompile (with F-R23's fix).

### F-R26 — `bump_version.py` partial-failure mode is SKIP-and-continue — **minor**
- **Evidence:** `scripts/bump_version.py` lines 125-126: on regex miss it prints "  SKIP  {loc['path']} (pattern not found)" and proceeds; exit code stays 0. Each pattern uses `count=1` (`pattern.subn(replacement, text, count=1)`).
- **Impact:** a drifted target file (e.g. someone reworded the README badge) yields a silent partial bump caught only later by `tests/test_version.py` — works, but inverts S-5's spirit in the one script whose whole job is consistency.
- **Recommendation:** v14.2.x: exit non-zero when any expected location SKIPs (the file-not-found SKIP for the opt-in mirror stays soft). ~5-line change.

### F-R27 — Adapter-build rule text frozen at 4 while the surface is 4 core + 12 data-driven — **minor**
- **Evidence:** CP-5/W-12: "running `build-skill` and verifying all 4 adapter outputs (Cursor, Codex, Claude, Copilot)". `src/devolaflow/adapters/registry.py` registers exactly those 4 as `tier="core"`, but `adapter_configs/` holds 12 YAML configs (`amazon_q.yaml augment.yaml cline.yaml continue.yaml gemini.yaml jetbrains.yaml kimicode.yaml openclaw.yaml roo.yaml trae.yaml windsurf.yaml zed.yaml`) loaded by `load_data_driven_adapters` (`adapters/data_driven.py:323`), each with its own test file (`test_zed_adapter.py` etc.).
- **Impact:** the W-12 verification obligation silently covers 25% of the adapter fleet; the data-driven 12 rely only on their unit tests. Either the rule under-verifies or the 12 are second-class — undocumented either way.
- **Recommendation:** v14.3.0: recompile W-12 to "4 core + registered data-driven set"; have `build-skill` iterate `registry.names()` + `adapter_configs/` so the count is never hand-written again.

### F-R28 — Env-flag count pinned in rules ("8") is unverifiable against the inventory — **minor**
- **Evidence:** W-22.4: "the env-flag count remains at 8 per v11.1.3 baseline"; W-24.4: "env-flag count stays at 8 per v11.3.0 baseline". Measured distinct `DEVOLAFLOW_*` identifiers across `src/devolaflow/` + `references/env-flags.md`: **26** (including `DEVOLAFLOW_VERIFICATION_LADDER`, `DEVOLAFLOW_CODEGRAPH`, `DEVOLAFLOW_MEMORY_ROUTER`, `DEVOLAFLOW_AC_GEN`, `DEVOLAFLOW_AGENTS_MD_SLICE`, …).
- **Impact:** even granting that some identifiers are test keys or sub-tier variants, "8" cannot be reproduced from any obvious filter; W-20's reuse-first policy depends on an accurate inventory.
- **Recommendation:** v14.2.x: make `references/env-flags.md` §2 machine-checkable (one table row per active flag; a ghost-audit entry asserts table-rows == grep-derived active set), then stop hand-pinning the number in W-22/W-24 prose.

---

## §6 Ladder mapping

| Finding | Severity | Land at | Rationale (1 line) |
|---|---|---|---|
| F-R1 triple-loaded rule corpus | critical | v14.2.x | Stub-conversion is proven pattern (2 precedents), zero behaviour change, immediate token win for every L3 |
| F-R2 cap denominator mismatch | major | v14.3.0 | Needs ADR-007 amendment first (§7-D1); test change is then trivial |
| F-R3 stale index.md counts | minor | v14.2.x | Doc fix + parity assertion; no risk |
| F-R4 silent layer drop in compiler | major | v14.2.x | Small hard-fail change in `local/compiler.py`; prevents recurrence before ladder adds rules |
| F-R5 unbounded W-layer growth | major | v15.0.0 | Rule-diet is a breaking re-compile of operator-facing corpus; belongs in MAJOR with strict-flip |
| F-R6 dead C-8 rule | minor | v14.2.x | Single deletion + recompile; frees cap slot |
| F-R7 contradictory always-on counts | major | v14.2.x | Resolved by same stub conversion as F-R1 |
| F-R8 Soul freeze healthy | info | defer-next-cycle | No action; cite as model in v15.0.0 rule-diet ADR |
| F-R9 broken W-17 verify recipe | minor | v14.2.x | One-line command fix in `.rules/workflow.mdc` + recompile |
| F-R10 A-2 mechanism healthy | info | defer-next-cycle | Keep as-is |
| F-R11 baseline sprawl (62 files) | major | v14.3.0 | Prune relics after §7-D2 ADR sets retirement policy |
| F-R12 stale schema comments | minor | v14.2.x | Comment-only edit; baselines unaffected (byte tests don't cover comments — verify in PR) |
| F-R13 hand-mirrored backward_compat booleans | minor | v14.3.0 | Fold into the §7-D2 ADR change to avoid two schema-comment PRs |
| F-R14 A-5 stale registry table | minor | v15.0.0 | Part of rule-diet (F-R5); normative content unchanged |
| F-R15 scorer.py split | major | v14.5.0 | Architecture refactor; justified by 6-concern evidence + v15 strict-flip touching cascade; needs §7-D3 ADR |
| F-R16 selector split | major | v14.5.0 | Same refactor window as F-R15; scoped W-13 trigger reduces future benchmark churn |
| F-R17 context_profiles defaults+delta | major | v14.4.0 | Data-file restructure, fully benchmark-guarded (W-6/W-14); earlier than code splits since it unblocks profile additions |
| F-R18 feedback.py mixed concerns | minor | v14.5.0 | Ride along with F-R15 refactor; S-10 path shims mandatory |
| F-R19 secondary hotspots | info | defer-next-cycle | Cohesive; monitor only |
| F-R20 ghost-audit god-file | critical | v14.3.0 | Split before the ladder's PVs append 4 more cycles of growth; needs §7-D4 ADR (W-18 names the path) |
| F-R21 count-pin sprawl | major | v14.2.x | Derive-from-SSOT is low-risk test hygiene; reduces friction for all later ladder work |
| F-R22 parametrize discipline | minor | v14.3.0 | Depends on F-R9 measurement fix; pair with F-R21 conversion |
| F-R23 SI-10 6-vs-7 drift | minor | v14.2.x | Recompile W-9 from Makefile truth; doc-only |
| F-R24 suite runtime healthy | info | defer-next-cycle | No action |
| F-R25 sync fan-out / CP-3 undercount | major | v14.4.0 | Render-time injection removes 3 patterns; CP-3 text fix rides v14.2.x recompile |
| F-R26 bump SKIP-and-continue | minor | v14.2.x | ~5-line hard-fail; aligns the consistency tool with S-5 |
| F-R27 adapter count frozen at 4 | minor | v14.3.0 | Recompile W-12 + make build-skill registry-driven |
| F-R28 unverifiable "8 flags" pin | minor | v14.2.x | Machine-checkable inventory; prerequisite for honest W-20 reviews |

---

## §7 ADR-needed decisions (3-condition gate applied)

- **D1 — Rule-cap denominator and cap value (feeds F-R2, F-R5).** Hard to reverse: the cap number is cited in ADR-007 D5, test code, and index.md — re-pinning it rewrites governance history every later cycle builds on. Surprising without context: "63 rules under a 60 HARD cap, test green" is incomprehensible without the AGENTS.md-only denominator story. Real trade-off: full-corpus cap (honest, forces Style diet) vs compiled-target cap (status quo, but Style becomes ungoverned). → ADR before v14.3.0.
- **D2 — Baseline retirement/tiering policy (feeds F-R11, F-R13).** Hard to reverse: deleting golden files destroys byte-witnesses that cannot be regenerated from history with confidence. Surprising: A-2.4 currently says keep-all-forever; any pruning contradicts written rule. Real trade-off: archival integrity vs monotone CI/maintenance growth. → ADR before any file is moved (v14.3.0).
- **D3 — `gate/scorer.py` + `feedback.py` public import-surface split (feeds F-R15, F-R16, F-R18).** Hard to reverse: downstream operators and S-10/W-11/schema text reference `feedback.py::populate_cascade_gate_fields` and scorer symbols by path; shim lifetimes must be declared. Surprising: rules cite file paths as contracts (S-10 "R5 strict triple codification" names `feedback.py`). Real trade-off: cohesion gain vs path-contract churn at the exact modules the v15.0.0 strict-flip touches. → ADR in v14.4.0, implement v14.5.0.
- **D4 — Ghost-audit decomposition (feeds F-R20).** Hard to reverse: W-18 and S-4 enforcement history all point at one filename; splitting changes the append target every future PV uses. Surprising: a passing-forever 12K-line test file being split looks like weakening the audit unless the contract is restated. Real trade-off: single-file greppability vs merge-conflict surface and unbounded growth. → ADR in v14.2.x, implement v14.3.0.
- **Explicitly NOT ADR-worthy:** F-R6 (dead rule deletion — reversible, unsurprising), F-R23/F-R25 text fixes (recompiles from existing truth), F-R21 (test-internal refactor).

## §8 North-star tension ("在单独任务上做到极致")

1. **Context budget inversion (F-R1, F-R5).** A-1 P2 grants an L3 Task Agent "~8K tokens (task spec + owned files + rules)", yet the always-applied rule load alone is ~2,200+ lines with 2–3× duplication — the governance apparatus consumes the budget that was supposed to buy single-task focus. The repo's most leveraged optimization is not a new feature: it is deleting duplicate prompt mass.
2. **Maintenance gravity grows superlinearly with versions, L3 capacity does not (F-R11, F-R20, F-R25).** Each release permanently adds: ≥1 baseline JSON, ghost-audit appendage (~1.7K lines/week observed), a versions.json entry, 11 regex bumps, EN+ZH doc regen, and often a new W-rule. These are O(version-count) obligations serviced by the same agents who should be doing task work. The planned 5-version ladder, executed under current rules, mechanically produces ~5 more baselines, ~3–5 W-rules, and (at observed rate) a >20K-line ghost file — none of which improves a single L3 deliverable.
3. **Self-referential rule mass vs task-quality rule mass.** Of the 24 W-rules, the majority (W-1/2/3/7/16/17/18/19/21 and the version-bump/benchmark mirrors W-10..W-14) govern the repo's *own release process*; rules that directly shape L3 deliverable quality (W-8 reinforcement, W-15 section relevance, W-22/23 grill+glossary, W-24 pattern selection) are a minority. The corpus optimizes the factory more than the product. The v15.0.0 rule-diet (F-R5) should rebalance toward task-quality rules and demote process narration to archives.
4. **Healthy counter-evidence:** the A-2 frozen prefix (F-R10) and the Soul freeze (F-R8) are governance that *pays for itself* — both are small, mechanically enforced, and protect properties (cache hits, invariant memorability) that directly serve dispatch quality. The ladder should converge the rest of the apparatus toward that shape: few rules, hard enforcement, zero narrative payload.

---
*End of review — 28 findings: 2 critical, 10 major, 12 minor, 4 info.*
