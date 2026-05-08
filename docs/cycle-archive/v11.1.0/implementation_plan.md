# v11.1.0 Cascade-Restoration MINOR Cycle Plan

> **Status:** v11.1.0 PV-01 D3 — multi-PV cycle plan synthesizing sibling
> Wave 1 D1 (gap analysis) + D2 (NineS analysis).
> **Author:** L3 Task C of Wave 2 (Wave 1 sibling outputs already written;
> this artifact closes the PV-01 W-1 / SI-1 planning gate).
> **Branch:** `feature/v11.1.0-cascade-research-pv01` (research-only;
> `.local/` is gitignored — no commit, the whole PV-01 lands as a PR for
> review per Decision Point #1).
> **Cycle baseline:** v11.0.1 (`src/devolaflow/__init__.py` `__version__ = "11.0.1"`;
> last commit `cec4cc4 Merge pull request #125 from YoRHa-Agents/release/v11.0.1`).
> **Cycle target:** v11.1.0 MINOR (cascade restoration).
> **Sister artifacts (must be read together):**
> - `.local/research/v11.1.0_gap_analysis.md` — D1 SI-1 planning gate (10-gap inventory; 4 P0 + 3 P1 + 2 P2 + 1 P3).
> - `.local/research/v11.1.0_nines_analysis.md` — D2 SI-2 NineS-driven analysis (composite **6.85/10** baseline; 8 findings F-001..F-008).
> - `.local/research/v11.1.0_nines_raw.json` — D2 raw NineS evaluator scores (16 quality + 5 hygiene dimensions).
> - `.local/feedbacks/feedback_for_v11.0.0.md` — verbatim user feedback (cycle source-of-truth).
> **External tools (S-7):** DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`, NineS `https://github.com/YoRHa-Agents/NineS`.

---

## §1. Cycle goal

### Verbatim user feedback (CO-2 — DO NOT paraphrase, DO NOT translate)

The cycle's source-of-truth direction is the user's feedback at
`.local/feedbacks/feedback_for_v11.0.0.md`. Quoted VERBATIM
(CO-2 / S-2 — strict literal extraction):

```
我认为还是需要保持四个层级的依次派发 Sub-Agent 行为。

也就是说，在中等以上复杂度的任务中：
1. L0 调度 L1
2. L1 调度 L2
3. L2 调动 L3

不能由 L0 直接调动 L3。以及对于任务复杂度的判定，需要有一个更好的、更简明的判断标准

我希望你针对该方案进行深入调研和分析，并使用 NineS 进行分解，以确保收益的有效性。

另外在 Plan 模式中，也需要能够体现出多层级调度的原则，并且真正使其能够实现。

最重要的是需要有更完整的测试以及性能评估，确保有效后再进行这些子 Feature 的逐级合入：

1. 每一个子 Feature 都作为一个 Patch
2. 最终形成一个整体的 Minor 版本
3. 自我迭代多轮，以确保有足够的收益和提升

在确保有效性后，最终提交到一个 Major 版本。
```

### Target version path

```
v11.0.1 (current __version__ — base)
   │
   ▼
v11.0.2  (PV-02 — G-CLASSIFY-1 classifier redesign + W-16 wholesale baseline regen)
v11.0.3  (PV-03 — G-CASCADE-1 SKILL.md + G-CASCADE-2 multi-stage-trace.md)
v11.0.4  (PV-04 — G-PLAN-1 plan-mode + optional G-PLAN-2 + schema NEST `gate.cascade_required`)
v11.0.5  (PV-05 — G-TEST-1 cascade tests + G-AUDIT-1 ratchet + G-BENCH-1 perf scenarios + Architecture rule A-7)
v11.0.6  (PV-06 — G-NINES-1 self-eval + W-3 SI-3 evaluation; multi-round reinforcement starts here if composite < 8.5)
   │
   ▼
v11.1.0  MINOR rollup (PV-07 — single tag bump 11.0.6 → 11.1.0; CHANGELOG MINOR-close + W-19 archive + canonical 7 sync)
   │
   │ 1-2 stability patches (v11.1.1, optionally v11.1.2 — operator feedback collection per `.local/feedbacks/feedback_for_v11.1.0.md`)
   ▼
v12.0.0  MAJOR (TELEGRAPHED — NOT a v11.1.0 commitment; graduation deferred to v12.0.0 SI-1 per W-21 2-cycle cadence)
```

### One-line bridge between user voice and version path

> Per the user's "每一个子 Feature 都作为一个 Patch / 最终形成一个整体的 Minor
> 版本 / 自我迭代多轮 / 最终提交到一个 Major 版本", the patch-then-MINOR-then-MAJOR
> shape is mandated; self-iteration is baked in via the W-8 / SI-9 convergence
> reinforcement loop at PV-06 + the PV-05 → PV-06 self-eval gate.

### Cycle theme

**Restore the strict 4-layer cascade dispatch behaviour for STANDARD+
complexity per A-1 canonical** (L0 → L1 → L2 → L3). The v10.5.0 PV-01
D-A-1 audit + advisory annotation
(`workflow-system/agent/SKILL.md:180` "Layer collapse pattern (v10.5.0):
most cycles collapse L0→L3") eroded this canonical chain into an
"only-when-needed" advisory; the user's feedback "不能由 L0 直接调动 L3"
explicitly rejects that erosion. The cycle restores cascade as the
MANDATED default for STANDARD/COMPLEX tier and reserves L0→L3 collapse
exclusively for TRIVIAL (single file < 20 LOC) / SIMPLE (1-3 files)
tier per the chosen G-CLASSIFY-1 candidate.

### Cycle non-goals

* Do **NOT** propose new Soul rules. W-21 freezes Soul at 10 entries
  (S-1..S-10) for v11.0.0..v11.1.x; the cascade-depth invariant lands at
  Architecture A-7 per D1 §4 + D2 §3 finding 4 + ADR-007 D4.
* Do **NOT** introduce new env flags. W-20 reuse-first: cascade
  enforcement reuses `DEVOLAFLOW_AGENT_WORKSPACE` for activation surface
  and the `force_no_change=True` function parameter for operator escape
  hatch. Cycle ends with **8 env flags** unchanged from v11.0.x.
* Do **NOT** touch `canonical_order` positions 1-12. A-2.1 frozen prefix
  is byte-stable; cascade dispatch fields NEST under existing `gate`
  block per A-2.3 — `gate.cascade_required: bool` and
  `gate.cascade_min_layers: int` (canonical_order length stays at 17).

---

## §2. PV-by-PV table

7 PVs. Each PV is a single PATCH (`v11.0.X`) with the MINOR rollup tag
(`v11.1.0`) landing on the PV-07 commit. Multi-round self-iteration is
absorbed into PV-05 (test/bench reinforcement target) and PV-06 (NineS
self-eval rounds 1-N) per W-8 / SI-9.

W-17 cap: ≤ +30 NEW test functions per PV. Cumulative cap: ≤ +150 across
the cycle. Mid-cycle audit at PV-05 verifies cumulative trajectory.

| PV | Scope summary | Owned files | Acceptance criteria | Version bump | Gate profile | Wall-clock | NEW test functions |
|:---:|---|---|---|:---:|:---:|:---:|:---:|
| **PV-01** | Research artifacts: D1 gap analysis + D2 NineS analysis + D3 cycle plan + D4 stage report. Branch: `feature/v11.1.0-cascade-research-pv01`. RESEARCH ONLY — no source/test/schema/SKILL/rule edits. | `.local/research/v11.1.0_gap_analysis.md` (D1) + `.local/research/v11.1.0_nines_analysis.md` (D2) + `.local/research/v11.1.0_nines_raw.json` (D2 raw) + `.local/research/v11.1.0_cycle_plan.md` (D3 — this file) + `.local/research/v11.1.0_pv01_stage_report.md` (D4 — L1 → L0 stage report). | (1) D1 ≥ 7 gaps with (a)/(b)/(c); (2) D2 6 W-3 dimensions scored; (3) D3 ≥ 7 PVs with cascade decomposition; (4) D4 wave/task decomposition justified; (5) zero source-code edits. | (none — `.local/` is gitignored; PR for review only) | `relaxed` (research stage gate qualitative) | 60 min | **0** |
| **PV-02** | G-CLASSIFY-1 classifier redesign + W-16 wholesale baseline regen. New `cascade_requirement(complexity)` sibling pure function preserving the `Complexity` Literal contract byte-stable. `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json` authored wholesale per W-16 cycle-start. | `src/devolaflow/skills/change_activation.py` + `tests/test_change_activation_heuristic.py` + `workflow-system/agent/SKILL.md` (Quick Action Decision sub-table only — full SKILL.md rewrite in PV-03) + `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json` (NEW) + `CHANGELOG.md` (`## [11.0.2]` PATCH entry) + `tests/test_no_ghost_features.py` (W-18 refresh). | (1) Chosen classifier Candidate (A/B/C from D1 G-CLASSIFY-1) lands; operator can quote the verdict rule from memory in 1 sentence; (2) `cascade_requirement(complexity)` returns `"CASCADE_REQUIRED"` for STANDARD+, `"CASCADE_OPTIONAL"` otherwise; (3) `tests/test_change_activation_heuristic.py` truth table refreshed (env-flag + verdict-string contract preserved per W-20); (4) `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json` exists + matches schema + composite within ±5% of `v10.5.0_baseline.json` cohort; (5) `tests/test_layout_invariant_multi_baseline.py` 10/10 historical baselines GREEN unchanged. | 11.0.1 → **11.0.2** | `standard` (≥ 85, ≥ 80% cov) | 60-90 min | **+8 to +12** |
| **PV-03** | G-CASCADE-1 SKILL.md cascade restoration + G-CASCADE-2 multi-stage-trace.md revision. SKILL.md line 64 + lines 105-107 + line 180 cascade-required rewordings. `examples/multi-stage-trace.md` §"When NOT to use this pattern" 4 collapse-OK rows revised. SF-1 line budget verified ≤ 500. SI-5 / W-5 SKILL coupling: 4 adapter builds + version + benchmark + line count. | `workflow-system/agent/SKILL.md` (lines 64 + 105-107 + 165-180) + `workflow-system/agent/examples/multi-stage-trace.md` (lines 200-211 + frontmatter `last_updated`) + `workflow-system/agent/references/agent-hierarchy.md` (consistency check; likely no edit per A-1 trivial waiver) + `CHANGELOG.md` (`## [11.0.3]` PATCH entry) + `tests/test_no_ghost_features.py` (W-18 refresh). | (1) SKILL.md line 180 contains the literal cascade-required text and NO LONGER contains the literal substring `"Layer collapse pattern"` (negative lint); (2) line 64 contains the literal text `"Cascade required for STANDARD+"` (or close paraphrase agreed in PV-03 design); (3) lines 105-107 explicitly bind the shortcut to SIMPLE/TRIVIAL only; (4) `multi-stage-trace.md` "When NOT to use" rows 2 + 4 revised to MANDATE cascade for STANDARD+ (rows 1 + 3 preserved with tightened SIMPLE-tier wording); (5) SKILL.md line count ≤ 500 (SF-1); W-5 SKILL coupling 4 verifications PASS (line count + adapter build + benchmark + version). | 11.0.2 → **11.0.3** | `standard` | 45-60 min | **+1 to +2** (W-18 negative-lint stanzas; doc edits otherwise verified by existing tests) |
| **PV-04** | G-PLAN-1 plan-mode structural enforcement + optional G-PLAN-2 `_PLAN_MODE_OVERRIDES` cascade hook + schema NEST `gate.cascade_required` + `gate.cascade_min_layers` per A-2.3 (NEST not APPEND). Multi-baseline byte test stays GREEN by construction. CP-4 mandates `pytest tests/test_gate.py -v` since `gate/` is touched. | `workflow-system/agent/references/plan-mode-enforcement.md` (§3.1 + §4 new item #10 + §5.1 DO list) + `src/devolaflow/task_adaptive_selector.py` (G-PLAN-2 optional `_PLAN_MODE_OVERRIDES` extension) + `tests/test_task_adaptive_selector_plan_mode.py` (extend) + `schemas/lean-dispatch.yaml` (NEST `gate.cascade_required` + `gate.cascade_min_layers` under existing `gate` block — canonical_order length stays at **17**) + `src/devolaflow/feedback.py` (dispatch payload populates new sub-fields) + `src/devolaflow/gate/scorer.py` (cascade-required validator integration) + `CHANGELOG.md` (`## [11.0.4]`) + `tests/test_no_ghost_features.py` (W-18 refresh). | (1) Plan-mode Constraints Checklist item #10 enforces cascade depth (SKILL.md or `plan-mode-enforcement.md` contains literal text `"Cascade depth (STANDARD+)"`); (2) plan-render call with STANDARD-tier inputs + L1/L2-omitted rows fails the checklist; (3) `schemas/lean-dispatch.yaml#layout_invariant.canonical_order` length stays at **17** (NEST not APPEND per A-2.3); (4) `tests/test_layout_invariant_multi_baseline.py` 10/10 baselines GREEN; (5) `tests/test_dispatch_emission_runs_hooks.py` byte-identical (S-10 hook-chain invariant); (6) `pytest tests/test_gate.py -v` PASS (CP-4). | 11.0.3 → **11.0.4** | `standard` (CP-4 gate suite + A-2.4 multi-baseline + S-10 byte-id) | 60-90 min | **+5 to +7** |
| **PV-05** | G-TEST-1 cascade-compliance tests + G-AUDIT-1 audit ratchet + G-BENCH-1 cascade-vs-collapse perf scenarios + new Architecture rule A-7 + W-17 mid-cycle audit. `tests/test_cascade_enforcement.py` NEW. `audit_layer_usage.py --strict` flag + `cascade_ratio` field. 4 EvoBench scenarios (cascade_l0_l1_l2_l3_standard / _complex; collapse_l0_l3_simple / _trivial). `.rules/architecture.mdc` appends §A-7 + recompile via `make compile-rules`. | NEW `tests/test_cascade_enforcement.py` + `scripts/audit_layer_usage.py` (`--strict` flag + `cascade_ratio` field) + `tests/test_audit_layer_usage.py` (amend) + 4 NEW EvoBench scenario fixtures under `benchmarks/devolaflow_context/scenarios/` (`cascade_l0_l1_l2_l3_standard.{yaml,toml}` + `cascade_l0_l1_l2_l3_complex.*` + `collapse_l0_l3_simple.*` + `collapse_l0_l3_trivial.*`) + `tests/test_benchmarks.py` (parametrize over the 4 NEW scenarios) + `.rules/architecture.mdc` (NEW §A-7 cascade-depth rule) + `AGENTS.md` + `.cursor/rules/repo-governance.mdc` (auto-recompiled via `make compile-rules`) + `CHANGELOG.md` (`## [11.0.5]`) + `tests/test_no_ghost_features.py` (W-18 refresh). | (1) `tests/test_cascade_enforcement.py::test_standard_complexity_mandates_cascade` PASSes; file contains ≥ 10 cascade tests; (2) `cascade_ratio` field exists on audit `compute_layer_ratios` output; (3) `audit_layer_usage.py --strict --threshold 0.30` returns 1 when ratio violated (default OFF preserves byte-identical v11.0.x behaviour); (4) 4 NEW EvoBench scenarios load cleanly; cascade_compliant_standard composite ≥ collapsed composite − 5% (W-4 SI-4); (5) A-7 rule lands in `.rules/architecture.mdc` + `make compile-rules` regenerates `AGENTS.md` + `.cursor/rules/repo-governance.mdc` cleanly (drift hash matches per `.rules/.compile-hashes.json`); (6) W-17 mid-cycle forecast: cumulative ≤ +35 through PV-05; remaining-PV budget ≤ +6 (PV-06 zero + PV-07 ~2-4). | 11.0.4 → **11.0.5** | `standard` (W-4 SI-4 EvoBench regression + W-17 mid-cycle audit) | 90-120 min | **+12 to +15** (parametrize expansions over 4 NEW YAML scenarios in `tests/test_benchmarks.py` do **NOT** count per W-17) |
| **PV-06** | G-NINES-1 NineS self-eval re-run (`nines self-eval --baseline-version 11.0.5`). Composite must clear ≥ **8.5** MINOR threshold. If composite ≥ 8.5: GO to MINOR rollup. If < 8.5: convergence round (W-8 / SI-9 reinforcement; max 5 rounds; stagnation 2+ rounds → escalate to user per P4 bounded retry). Multi-round reinforcement re-dispatches PV-05 failing test/bench tasks under cascade. | `.local/research/v11.1.0_pv06_nines.json` (raw) + `.local/research/v11.1.0_pv06_nines.md` (rendered analysis) + `.local/research/v11.1.0_evaluation.md` (W-3 SI-3 6-dim composite) + `CHANGELOG.md` (`## [11.0.6]`) + `tests/test_no_ghost_features.py` (W-18 refresh) — analysis-only; NO source/test/schema edits unless reinforcement round triggers PV-05 re-execution. | (1) NineS run completes (re-uses `nines.toml` config from cycle baseline); (2) **W-3 SI-3 composite ≥ 8.5 / 10** (MINOR threshold); (3) per-dimension scores documented in `v11.1.0_evaluation.md`; (4) trajectory delta vs **v11.0.1 baseline composite 6.85** (D2 §8) shows positive lift ≥ +1.65; (5) if composite < 8.5: W-8 SI-9 reinforcement payload generated (top-5 prior-round findings ≥ major severity per `gate/reinforcement.py::findings_to_reinforcement`). | 11.0.5 → **11.0.6** | `strict` (W-3 SI-3 ≥ 8.5 gate; cycle's MINOR-close convergence point) | 60 min nominal; up to 5× wall-clock if reinforcement rounds fire | **0** (analysis-only; reinforcement re-runs PV-05 fixes via existing test surfaces) |
| **PV-07** | MINOR cycle close. CHANGELOG `## [11.1.0]` MINOR entry. Canonical 7 sync (`scripts/bump_version.py 11.1.0`). W-19 archive (`python scripts/archive_research_artifacts.py 11.1.0` → `docs/cycle-archive/v11.1.0/`). Retrospective at `.local/research/v11.1.0_retrospective.md`. WX-2 demo `versions.json` entry. EN/ZH bilingual refresh via `make sync-human-docs`. W-9 / SI-10 7-step regression. | `src/devolaflow/__init__.py` + `pyproject.toml` + `workflow-system/agent/SKILL.md` (frontmatter + banner + body) + `workflow-system/agent/workflow-skill.yaml` + `scripts/generate_human_docs.py` + `tests/test_smoke.py` + `README.md` + `workflow-system/human/demo/benchmark-results/index.html` (canonical 7 — `python scripts/bump_version.py 11.1.0`) + `workflow-system/human/demo/version-timeline/versions.json` (NEW v11.1.0 entry per WX-2) + `workflow-system/human/demo/index.html` ("What's New" per DS-1) + `workflow-system/human/en/*.md` + `workflow-system/human/zh/*.md` (via `make sync-human-docs`) + `CHANGELOG.md` (`## [11.1.0]` MINOR-close at top) + `.local/research/v11.1.0_retrospective.md` (W-7 / SI-8) + `docs/cycle-archive/v11.1.0/` (W-19 — committed) + `tests/test_no_ghost_features.py` (`test_v11_1_0_new_symbols_have_coverage`). | (1) `python scripts/bump_version.py 11.1.0` runs cleanly; `python -m pytest tests/test_version.py -v` PASS (canonical 7 sync); (2) `docs/cycle-archive/v11.1.0/` populated per W-19 with `gap_analysis.md` + `implementation_plan.md` + `design/` + `nines/` + `evaluation/` + `retrospective.md` + `README.md`; the archive is **COMMITTED** (not gitignored — that is the W-19 contract); (3) `versions.json` v11.1.0 entry with real metrics from CHANGELOG only (WX-2); (4) bilingual EN+ZH refreshed via `make sync-human-docs` (ST-3 / ST-4); (5) retrospective covers W-7 4 mandatory sections; (6) full **W-9 / SI-10 7-step regression** PASS (see §5); (7) `make check-cursor-skill` exit 0. | 11.0.6 → **11.1.0** (single tag bump; MINOR rollup) | `relaxed` for doc-mostly close; `standard` for the W-9 SI-10 regression sweep | 30-45 min nominal | **+2 to +4** (W-18 final ghost-audit refresh `test_v11_1_0_new_symbols_have_coverage` + 1-2 demo lints) |

**Cycle totals**:

* Wall-clock: **~6.5 – 9 hours** across 7 PVs (nominal, no reinforcement
  rounds). Reinforcement loop adds ~30 min per round at PV-06 + ~60 min
  per re-execution of PV-05 fixes (W-8 / SI-9; max 5 rounds; stagnation
  2+ rounds → escalate per P4 bounded retry).
* Tokens: **~370K** cumulative (research + impl + eval).
* NEW test functions cumulative: **~28 to ~40** (PV-02 ~10 + PV-03 ~1-2
  + PV-04 ~5 + PV-05 ~13 + PV-06 0 + PV-07 ~2-4 ≈ ~30) — well under
  W-17 cumulative cap of **+150**. Substantial headroom for unforeseen
  reinforcement work.
* CHANGELOG entries: 5 PATCH (`## [11.0.2]` .. `## [11.0.6]`) + 1 MINOR
  rollup (`## [11.1.0]`) at top of file.

---

## §3. Cascade decomposition for each impl PV (the demonstration the user asked for)

This section is the cycle's **commitment device**: every impl PV
(PV-02..PV-07) explicitly states the L0 → L1 → L2 → L3 cascade structure
that the L0 cycle-lead MUST honour at runtime. This is the user-requested
"在 Plan 模式中，也需要能够体现出多层级调度的原则" expressed as a
plan-side normative contract. Per A-1 + the user feedback "不能由 L0
直接调动 L3", every dispatch in this cycle (TRIVIAL waiver excluded)
flows:

```
L0 (cycle-lead, this conversation's heir)
  │ dispatches via Task tool, generalPurpose subagent
  ▼
L1 Stage Agent (per-PV; e.g., L1-PV02 owns the classifier-redesign stage)
  │ dispatches via Task tool, generalPurpose subagent
  ▼
L2 Wave Agent (per-wave within the PV; max 5 tasks per wave per A-1 P3)
  │ dispatches via Task tool, generalPurpose subagent
  ▼
L3 Task Agents (per-task; the only layer that writes code/tests/docs/rules)
```

Inline single-author L3 work is permitted ONLY for the trivial waiver
(single file < 20 lines) per S-1 / A-1 P1.

### PV-02 — Classifier redesign + W-16 baseline regen

```
L0: receives "v11.0.2 classifier redesign" gap-analysis ref →
    dispatches L1 Stage S01_classifier_redesign (gate: standard, max_rounds=3)
                              + L1 Stage S02_baseline_regen (gate: relaxed, max_rounds=1)
L1 S01_classifier_redesign:
  L2 W01_pure_function_pin (sequential — same file):
    L3 T01_cascade_requirement_function:
      owned: src/devolaflow/skills/change_activation.py
      read-only: tests/test_change_activation_heuristic.py + .local/research/v11.1.0_*.md + workflow-system/agent/SKILL.md
      AC: cascade_requirement() returns "CASCADE_REQUIRED" for STANDARD+, "CASCADE_OPTIONAL" otherwise;
          ValueError on invalid complexity input; force_no_change semantics preserved (S-5);
          chosen Candidate (A/B/C) implemented per D1 G-CLASSIFY-1; existing 13 contract pins preserved.
      wall-clock: 25 min
  L2 W02_test_pin (parallel — disjoint test fixtures, runs after W01 completes):
    L3 T01_classifier_unit_tests:
      owned: tests/test_change_activation_heuristic.py (extension)
      AC: 8-10 NEW test functions covering cascade_requirement() truth table;
          test_from_env_truthy_only_on_literal_one preserved; W-17 cap respected.
      wall-clock: 20 min
    L3 T02_dispatcher_integration_tests:
      owned: tests/test_cascade_enforcement.py (NEW — minimal stub; full ≥10-test surface lands in PV-05)
      AC: cascade_requirement() flows through into dispatch payload via gate.cascade_required NEST sub-field;
          tests/test_layout_invariant_multi_baseline.py 10/10 GREEN.
      wall-clock: 25 min
L1 S02_baseline_regen:
  L2 W01_baseline_regen (sequential — write-amp risk; single L3 single-author):
    L3 T01_baseline_regen:
      owned: benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json (NEW)
      AC: file exists; matches schema; composite scores within ±5% of v10.5.0_baseline.json
          cohort means (per W-16 wholesale-regen-on-cycle-start); the baseline is the single
          v11.1.0 anchor for all subsequent PVs in the cycle.
      wall-clock: 30 min (NineS-driven)
```

Cascade-compliance self-check: every Wave dispatch produced ≥ 2 L3
dispatches per A-1 P3 wave-budget; no L0 → L3 direct dispatch in this
PV's history (verifiable via `scripts/audit_layer_usage.py` post-PV).

### PV-03 — SKILL.md cascade restoration + multi-stage-trace.md revision

```
L0: receives "v11.0.3 SKILL.md cascade restoration" + "multi-stage-trace.md revision" →
    dispatches L1 Stage S01_skill_cascade_restoration (gate: standard, max_rounds=2)
L1 S01_skill_cascade_restoration:
  L2 W01_doc_revisions (parallel — disjoint files):
    L3 T01_skill_md_rewording:
      owned: workflow-system/agent/SKILL.md (lines 64 + 105-107 + 165-180 ONLY)
      read-only: workflow-system/agent/SKILL.md (other sections; consistency check),
                 .local/research/v11.1.0_gap_analysis.md §G-CASCADE-1
      AC: line 180 contains literal cascade-required text; the substring "Layer collapse pattern"
          NO LONGER appears anywhere in SKILL.md (negative lint via tests/test_no_ghost_features.py);
          line 64 mandates cascade for STANDARD+; lines 105-107 explicitly bind the shortcut to
          SIMPLE/TRIVIAL only; SF-1 line count ≤ 500.
      wall-clock: 25 min
    L3 T02_multi_stage_trace_revision:
      owned: workflow-system/agent/examples/multi-stage-trace.md (lines 200-211 + frontmatter last_updated)
      AC: §"When NOT to use this pattern" rows 2 + 4 revised to MANDATE cascade for STANDARD+
          (8-module refactor + codebase-wide audit examples REMOVED or REWRITTEN);
          rows 1 + 3 preserved with SIMPLE-tier wording tightened;
          frontmatter last_updated bumped; SF-1 XL tier ≤ 1600 lines.
      wall-clock: 20 min
  L2 W02_w18_changelog (sequential after W01):
    L3 T01_w18_refresh_and_changelog:
      owned: tests/test_no_ghost_features.py + CHANGELOG.md (## [11.0.3] entry)
      AC: ghost-audit refresh test asserts SKILL.md no longer contains "Layer collapse pattern"
          AND multi-stage-trace.md no longer contains the verbatim row-2 string
          "L0 → L3 with a per-task wave partition (no L1 stage needed)";
          CHANGELOG entry follows W-18 sequencing (refresh BEFORE entry).
      wall-clock: 15 min
```

Note: `references/agent-hierarchy.md` consistency check is L1's READ-ONLY
verification (per A-1 P1 trivial waiver — single file, < 20 lines if
edits needed; otherwise zero edits expected).

### PV-04 — Plan-mode + schema NEST + recompile rules

This PV is the cycle's **highest-coordination** impl PV — touches schema,
plan-mode reference, runtime overrides, gate validator, recompiled rule
outputs (`AGENTS.md` + `.cursor/rules/repo-governance.mdc`), and 4 test
files. Cascade discipline matters most here.

```
L0: receives "v11.0.4 plan-mode + schema NEST + A-7 wiring" →
    dispatches L1 Stage S01_plan_mode_enforcement (gate: standard, max_rounds=3)
L1 S01_plan_mode_enforcement:
  L2 W01_schema_and_runtime (parallel — disjoint files):
    L3 T01_schema_nest:
      owned: schemas/lean-dispatch.yaml (NEST gate.cascade_required + gate.cascade_min_layers under existing gate block)
      AC: canonical_order length stays at 17 (NEST not APPEND per A-2.3);
          frozen prefix positions 1-12 byte-identical;
          schema version stays at 6 (NEST historical precedent — v9.1.4 PV-04 NEST inside change_context).
      wall-clock: 20 min
    L3 T02_runtime_override:
      owned: src/devolaflow/task_adaptive_selector.py (G-PLAN-2 optional `_PLAN_MODE_OVERRIDES` extension)
      AC: new override key `plan_mode_cascade_required: bool` (default True under v11.1.0;
          default False is v11.0.x backward-compat path); 2-3 NEW unit tests in
          tests/test_task_adaptive_selector_plan_mode.py.
      wall-clock: 20 min
    L3 T03_plan_mode_doc:
      owned: workflow-system/agent/references/plan-mode-enforcement.md (§3.1 + §4 item #10 + §5.1 DO list)
      AC: §4 Constraints Checklist gains item #10 with literal text "Cascade depth (STANDARD+)";
          §5.1 DO list gains "Use the cascade chain L0 → L1 → L2 → L3 for STANDARD+ plans";
          SF-1 Large tier ≤ 1000 lines.
      wall-clock: 20 min
  L2 W02_validator_and_dispatch (parallel after W01 — touches gate + feedback):
    L3 T01_gate_validator:
      owned: src/devolaflow/gate/scorer.py + src/devolaflow/feedback.py
      AC: dispatch payload populates gate.cascade_required + gate.cascade_min_layers;
          assert_dispatch_layout recognises the NEST sub-fields;
          tests/test_dispatch_emission_runs_hooks.py byte-identical (S-10 hook-chain invariant);
          CP-4 mandate: pytest tests/test_gate.py -v PASS.
      wall-clock: 25 min
    L3 T02_plan_render_test:
      owned: tests/test_task_adaptive_selector_plan_mode.py (cascade-compliance regression test)
      AC: STANDARD-tier plan-render call with L1/L2-omitted rows fails item #10;
          TRIVIAL plan with single L3 row passes (trivial waiver per A-1 P1).
      wall-clock: 20 min
  L2 W03_w18_changelog (sequential after W02 — depends on all prior changes):
    L3 T01_w18_refresh_and_changelog:
      owned: tests/test_no_ghost_features.py + CHANGELOG.md (## [11.0.4] entry)
      AC: ghost-audit refresh covers gate.cascade_required + plan_mode_cascade_required +
          new checklist item #10 verbatim string;
          tests/test_layout_invariant_multi_baseline.py 10/10 GREEN by construction
          (NEST under gate at frozen position 12 — baselines unchanged);
          CHANGELOG entry follows W-18 sequencing.
      wall-clock: 15 min
```

W-1 P5 contract: T07-equivalent (rule recompile via `make compile-rules`)
is **deferred to PV-05** because the new A-7 rule body lands in PV-05
(co-located with the test surface that codifies it). PV-04 ships the
**runtime + schema + plan-mode** prerequisites; PV-05 ships A-7 + the
recompile.

### PV-05 — A-7 rule + cascade tests + audit ratchet + EvoBench scenarios

```
L0: receives "v11.0.5 cascade tests + A-7 rule + audit ratchet + EvoBench" →
    dispatches L1 Stage S01_test_and_perf (gate: standard, max_rounds=3)
                              + L1 Stage S02_rule_codification (gate: standard, max_rounds=2)
L1 S01_test_and_perf:
  L2 W01_cascade_tests (parallel — disjoint test files):
    L3 T01_cascade_enforcement_tests:
      owned: tests/test_cascade_enforcement.py (extend the PV-02 stub to ≥10 tests)
      AC: covers truth table for cascade_requirement() AND dispatch payload assertions
          (gate.cascade_required + gate.cascade_min_layers populated for STANDARD+);
          force_no_change=True override preserved (operator escape hatch);
          plan-render with STANDARD inputs but L1/L2-omitted rows fails the §4 checklist.
      wall-clock: 30 min
    L3 T02_audit_ratchet:
      owned: scripts/audit_layer_usage.py + tests/test_audit_layer_usage.py (amend)
      AC: --strict CLI flag (default OFF; R5 strict env-flag philosophy);
          --threshold X (default 0.30 — 30% cascade-ratio floor);
          new computed field cascade_ratio in compute_layer_ratios();
          2-3 NEW tests pinning the new field + --strict behavior;
          default invocation byte-identical to v11.0.x.
      wall-clock: 25 min
  L2 W02_perf_scenarios (parallel — disjoint scenario fixtures):
    L3 T01_evobench_fixtures:
      owned: benchmarks/devolaflow_context/scenarios/cascade_l0_l1_l2_l3_standard.{yaml,toml} +
             cascade_l0_l1_l2_l3_complex.* + collapse_l0_l3_simple.* + collapse_l0_l3_trivial.*
      AC: 4 NEW scenario fixtures load cleanly; pin both token-cost and quality-score per scenario;
          documented expected delta (cascade_l0_l1_l2_l3_standard composite ≥
          collapsed_l0_l3_simple composite − 5% per W-4 SI-4).
      wall-clock: 20 min
    L3 T02_test_benchmarks_parametrize:
      owned: tests/test_benchmarks.py (parametrize over the 4 NEW YAML scenarios)
      AC: parametrize expansions over EXISTING test functions (per W-17 carve-out — does NOT count toward +30 cap);
          regression threshold pinned per W-4 SI-4 (<5% drop).
      wall-clock: 15 min
L1 S02_rule_codification:
  L2 W01_rule_append (sequential — single rule append):
    L3 T01_a7_rule_body:
      owned: .rules/architecture.mdc (append §A-7 cascade-depth-required-for-STANDARD+)
      read-only: .local/research/v11.1.0_gap_analysis.md §4 (suggested A-7 wording)
      AC: A-7 lands with §A-7.1 classification surface +
          §A-7.2 plan-mode enforcement + §A-7.3 runtime enforcement +
          §A-7.4 operator override (force_no_change); architecture rule count 6 → 7;
          Soul cap unchanged at 10 (W-21 freeze respected).
      wall-clock: 25 min
  L2 W02_recompile (sequential after W01):
    L3 T01_recompile_corpus:
      owned: AGENTS.md + .cursor/rules/repo-governance.mdc (auto-regenerated via `make compile-rules`)
      AC: tests/test_no_ghost_features.py::test_rule_surfaces_compile_only PASS
          (drift detection via .rules/.compile-hashes.json per CLAUDE.md);
          AGENTS.md header "Auto-generated" preserved; no hand-edits to compiled outputs.
      wall-clock: 10 min
  L2 W03_w17_audit_and_changelog (sequential after W02):
    L3 T01_w17_audit:
      owned: (no file write — audit via Shell git diff per W-17 verification command)
      AC: cumulative NEW test fns (PV-02 + PV-03 + PV-04 + PV-05) ≤ +35 forecast;
          remaining-PV budget ≤ +6 forecast (PV-06 0 + PV-07 ~2-4);
          well under +150 cycle cap.
      wall-clock: 5 min
    L3 T02_w18_refresh_and_changelog:
      owned: tests/test_no_ghost_features.py + CHANGELOG.md (## [11.0.5] entry)
      AC: ghost-audit refresh covers tests/test_cascade_enforcement.py + audit_layer_usage --strict +
          cascade_ratio + A-7 symbol; CHANGELOG entry follows W-18 sequencing.
      wall-clock: 15 min
```

### PV-06 — NineS self-eval + W-3 SI-3 evaluation (+ multi-round if needed)

PV-06 is **analysis-only on the happy path** (composite ≥ 8.5 first
round) — single-author L3 by W-2 / SI-2 norm (NineS run + markdown
authoring is the canonical "1 author, 1 task" carve-out per
`multi-stage-trace.md` §"When NOT to use this pattern" row 1 SIMPLE).

```
L0: receives "v11.0.6 NineS self-eval + W-3 SI-3 evaluation" →
    dispatches L1 Stage S01_nines_self_eval (gate: strict, max_rounds=5 — convergence loop allowed)
L1 S01_nines_self_eval:
  L2 W01_nines_run (sequential — single L3 single-author):
    L3 T01_nines_run_and_evaluation:
      owned: .local/research/v11.1.0_pv06_nines.json (raw) +
             .local/research/v11.1.0_pv06_nines.md (rendered) +
             .local/research/v11.1.0_evaluation.md (W-3 SI-3 6-dim composite)
      read-only: nines.toml + .local/research/v11.1.0_nines_analysis.md (D2 baseline)
      AC: NineS run completes (re-uses nines.toml from cycle baseline);
          W-3 SI-3 composite ≥ 8.5 (MINOR threshold);
          per-dimension scores documented;
          trajectory delta vs v11.0.1 baseline (D2 §8 = 6.85) ≥ +1.65;
          if composite < 8.5 → W-8 SI-9 reinforcement payload generated.
      wall-clock: 60 min nominal; up to 5× (300 min) if reinforcement loop fires.
  L2 W02_changelog_or_reinforce (conditional on W01 verdict):
    Path A (composite ≥ 8.5 — happy path):
      L3 T01_w18_refresh_and_changelog:
        owned: tests/test_no_ghost_features.py + CHANGELOG.md (## [11.0.6] entry)
        AC: ghost-audit covers .local/research/v11.1.0_evaluation.md existence;
            CHANGELOG entry follows W-18 sequencing.
        wall-clock: 10 min
    Path B (composite < 8.5 — convergence loop):
      L0 emits ExceptionEscalation upward; L0 re-dispatches PV-05's failing
      tasks via the standard cascade with reinforcement payload
      (top-5 prior-round findings ≥ major severity per
      gate/reinforcement.py::findings_to_reinforcement);
      PV-06 round-counter persists in .local/research/v11.1.0_pv06_round_<N>.md.
      Max 5 rounds; stagnation 2+ rounds → escalate to user per P4 bounded retry.
```

**Rationale for shorter cascade**: per `multi-stage-trace.md` §"When NOT
to use this pattern" row 1 (SIMPLE-tier 1 author / 1 task), an evaluation
that consists of one CLI invocation + one markdown authoring is a
canonical SIMPLE task — collapse to W01 single-L3 is permitted under
the user's directive ("L0 → L3 collapse permitted ONLY for TRIVIAL or
SIMPLE"). The L1 / L2 dispatch ceremony is preserved for cascade-discipline
demonstration but does not multiply L3 work.

### PV-07 — MINOR cycle close (canonical 7 + retrospective + W-19 archive + bilingual)

PV-07 is the **highest-coordination cycle-close** PV. Touches the
canonical 7 (8 files), the demo + bilingual surfaces, the retrospective,
and the W-19 archive. Two stages — release + archive.

```
L0: receives "v11.1.0 MINOR rollup + W-19 archive + retrospective" →
    dispatches L1 Stage S01_release (gate: standard, max_rounds=2)
                              + L1 Stage S02_archive_and_retro (gate: relaxed, max_rounds=1)
L1 S01_release:
  L2 W01_canonical_7_bump (sequential — single L3 single-author per SF-3):
    L3 T01_canonical_7_bump:
      owned: src/devolaflow/__init__.py + pyproject.toml + workflow-system/agent/SKILL.md
             (frontmatter + banner + body) + workflow-system/agent/workflow-skill.yaml +
             scripts/generate_human_docs.py + tests/test_smoke.py + README.md +
             workflow-system/human/demo/benchmark-results/index.html
             (all via `python scripts/bump_version.py 11.1.0`)
      AC: pytest tests/test_version.py -v PASS (canonical 7 sync);
          mirror parity tests skip if .cursor/skills/devola-flow/ absent (expected);
          SI-5 / W-5 SKILL coupling 4 verifications PASS.
      wall-clock: 10 min
  L2 W02_demo_and_bilingual (parallel — disjoint files):
    L3 T01_versions_json_entry:
      owned: workflow-system/human/demo/version-timeline/versions.json (NEW v11.1.0 entry)
      AC: WX-2 — required fields version + date + era + headline + summary + highlights + metrics;
          metrics from CHANGELOG only (no invention).
      wall-clock: 10 min
    L3 T02_demo_index:
      owned: workflow-system/human/demo/index.html ("What's New" section)
      AC: DS-1 demo "What's New"; cross-reference to versions.json entry.
      wall-clock: 10 min
    L3 T03_bilingual_sync:
      owned: workflow-system/human/en/*.md + workflow-system/human/zh/*.md (regenerated via `make sync-human-docs`)
      AC: ST-3 / ST-4 bilingual completeness; EN/ZH version updated.
      wall-clock: 10 min
L1 S02_archive_and_retro:
  L2 W01_retrospective_and_archive (parallel — disjoint files):
    L3 T01_retrospective:
      owned: .local/research/v11.1.0_retrospective.md (W-7 / SI-8 4-section template)
      AC: covers 4 mandatory sections (Gaps identified / What was implemented /
          What was deferred and why / Key learnings); telegraphs S-11 / SHORTCUT_SIMPLE
          retirement / cascade-ratio threshold tightening for v12.0.0 / v13.0.0
          per W-21 2-cycle cadence.
      wall-clock: 20 min
    L3 T02_w19_archive:
      owned: docs/cycle-archive/v11.1.0/ (NEW; via `python scripts/archive_research_artifacts.py 11.1.0`)
      AC: archive contains README.md (auto-generated index) + gap_analysis.md +
          implementation_plan.md + design/ (per-PV designs) + nines/ (raw JSON + analysis) +
          evaluation/ (PV-06 NineS report) + retrospective.md;
          archive is COMMITTED (not gitignored — that is the W-19 contract);
          script is idempotent (re-runs are no-ops if destination exists).
      wall-clock: 10 min
  L2 W02_changelog_close (sequential after W01):
    L3 T01_changelog_minor_close:
      owned: CHANGELOG.md (## [11.1.0] MINOR-close section at TOP) +
             tests/test_no_ghost_features.py (test_v11_1_0_new_symbols_have_coverage W-18 final)
      AC: MINOR-close entry distinct from PATCH entries (enumerates all 7 PVs +
          cascade restoration goal); W-18 ghost-audit refresh landed BEFORE the entry;
          full W-9 / SI-10 7-step regression PASS (see §5).
      wall-clock: 15 min
```

**Rationale for 2-stage S01 + S02 split**: per `multi-stage-trace.md`
§"When TO use this pattern" row "concurrent multi-team workstreams",
the release stage (canonical 7 bump + demo + bilingual) has different
file-ownership concerns from the archive stage (retrospective + W-19
archive script invocation). Splitting preserves S-8 file-ownership
disjointness and lets W-19 archive script run in parallel with the
demo-bilingual L2 wave.

---

## §4. Self-iteration protocol (W-3 / SI-3 + W-8 / SI-9)

The user's directive **"自我迭代多轮，以确保有足够的收益和提升"**
(multi-round self-iteration to ensure sufficient gain) is operationalised
via the W-8 / SI-9 reinforcement-round mechanism. The contract:

* **max_rounds = 5** per the W-8 / SI-9 standard profile default. PV-06
  is the cycle's primary convergence point (W-3 / SI-3 gate at
  composite ≥ 8.5).
* **Reinforcement on FAIL**: gate findings from round N (severity ≥
  major) are converted via
  `src/devolaflow/gate/reinforcement.py::findings_to_reinforcement` into
  the `applicable_rules.reinforcement` payload of round N+1 dispatch.
  Top-5 severity-filtered findings only (per `gate/reinforcement.py`
  cap). L3 Task Agents that receive a dispatch with non-empty
  `reinforcement` MUST address ALL listed rules **before** any new
  work (per `plan-mode-enforcement.md` §6.2 contract); per-rule closure
  markers are emitted in `delta.closes_reinforcement` of the
  StatusReport.
* **Stagnation rule**: composite_score Δ < 1.0 over 2+ consecutive
  rounds (no new blocker introduced) → L1 emits ExceptionEscalation
  upward to L0 → L0 escalates to user per P4 bounded retry. This is
  the cycle's hard halt — the user is the only authority who can
  authorise round 6+ OR composite-threshold relaxation OR cycle-scope
  reduction (e.g., defer G-AUDIT-1 ratchet to v11.1.x patch).
* **Per-PV convergence**: every impl PV (PV-02..PV-06) follows
  convergence loop if its gate FAILs. If round 5 hits without PASS for
  a non-PV-06 PV → escalate to PV-(N+1) with relaxed profile (e.g.,
  demote PV-04 from `standard` to `relaxed`) OR escalate to user.
* **Cycle-level convergence**: PV-06 NineS gate (composite ≥ 8.5) is
  the cycle's MINOR-close convergence point. If composite < 8.5 even
  after PV-05 + PV-06 sub-rounds → escalate to user (re-scope; defer
  to v11.2.0 OR add a stretch PV).
* **Round-aware dispatch escalation**: per `task_adaptive_selector.py
  ::_ROUND_ESCALATION_DEFAULTS`, round 3+ bumps context budget to 1.2×
  and forces `model_hint=quality`. The cycle inherits these defaults
  (no override).

**Convergence loop applies at**:

1. **PV-05 → PV-06 boundary** if PV-05 composite < 8.5 (rare; G-TEST-1
   + G-BENCH-1 should land cleanly first round).
2. **PV-06 SI-3 self-eval** if composite < 8.5 (the primary expected
   reinforcement trigger; D2 §8 baseline 6.85 → +1.65 lift required to
   clear MINOR threshold 8.5).
3. **PV-07 W-9 SI-10 regression** if any of the 7 steps fail
   (escalates immediately per P4 abort; not a reinforcement loop —
   regression failures block the MINOR tag).

---

## §5. MINOR-close criteria (W-3 / SI-3 + W-9 / SI-10 + W-19)

The v11.1.0 MINOR tag (PV-07 commit `chore(v11.1.0)`) ships ONLY when
**ALL** of the following are GREEN. Each bullet cites its enforcing
rule + the verbatim shell command(s) the cycle-lead L0 MUST run.

### 5.1 — W-3 / SI-3 STRICT MINOR composite ≥ 8.5

* **NineS self-eval at PV-06** runs:

  ```bash
  nines -f json -c nines.toml self-eval \
    --baseline-version 11.0.5 \
    --golden-dir data/golden_test_set \
    --samples-dir data/golden_test_set \
    --src-dir src/devolaflow \
    --test-dir tests \
    --project-root . \
    > .local/research/v11.1.0_pv06_nines.json \
    2> .local/research/v11.1.0_pv06_nines_stderr.log
  ```
* Composite weighted per W-3 (code_quality 0.20 + architecture 0.20 +
  test_adequacy 0.20 + maintainability 0.15 + compatibility 0.10 +
  performance 0.15) **≥ 8.5 / 10**.
* No regression at PV-07 (no further changes to the 6 dimensions
  between PV-06 close and PV-07 close).

### 5.2 — W-9 / SI-10 7-step regression sweep PASS

```bash
python -m pytest tests/ -q                              # step 1: all tests pass
ruff check src/ tests/                                  # step 2: 0 errors
ruff format --check src/ tests/                         # step 3: formatted correctly
python -m pytest tests/test_version.py -v               # step 4: canonical 7 sync agreement
python -m pytest tests/test_benchmarks.py -v            # step 5: no regressions vs v11.1.0_baseline.json
make check-cursor-skill                                 # step 6: exit 0
python -m pytest tests/test_layout_invariant_multi_baseline.py -v  # step 7: 10/10 baselines GREEN (10/10 because A-2.4 currently pins 10 historical baselines per the test docstring; if PV-04 added a v11.1.0 baseline, it becomes 11/11)
```

PV-04 + PV-05 add an extra step that PV-07 inherits:

```bash
python -m pytest tests/test_dispatch_emission_runs_hooks.py -v   # S-10 byte-identity guard
python -m pytest tests/test_gate.py -v                            # CP-4 gate suite (gate/ touched)
```

### 5.3 — W-19 cycle archive at `docs/cycle-archive/v11.1.0/`

```bash
python scripts/archive_research_artifacts.py 11.1.0
```

* Idempotent (re-runs no-op if destination exists).
* Archive contents: `README.md` (auto-generated index) +
  `gap_analysis.md` + `implementation_plan.md` + `design/` (per-PV
  designs) + `nines/` (raw JSON + analysis) + `evaluation/` (PV-06
  NineS report) + `retrospective.md`.
* Archive is **COMMITTED** (not gitignored — that is the W-19 contract).

### 5.4 — `CHANGELOG.md` `## [11.1.0]` entry with W-18 ghost-audit refresh BEFORE

* W-18 sequencing: `tests/test_no_ghost_features.py` gains
  `test_v11_1_0_new_symbols_have_coverage` BEFORE the CHANGELOG entry
  is authored.
* MINOR-close section sits at the TOP of `CHANGELOG.md` (distinct shape
  from PATCH entries; enumerates all 7 PVs + cascade restoration goal).

### 5.5 — Canonical 7 sync via `scripts/bump_version.py 11.1.0`

```bash
python scripts/bump_version.py 11.1.0     # bumps canonical 7 + auto-syncs mirror IFF present
make sync-human-docs                       # regenerates EN/ZH human docs
python -m pytest tests/test_version.py -v  # asserts canonical 7; mirror tests skip if absent
```

### 5.6 — Bilingual demo + version-timeline (ST-3 / WX-2)

* `make sync-human-docs` regenerates EN/ZH guides (8 + 8 files).
* `workflow-system/human/demo/version-timeline/versions.json` gains a
  v11.1.0 entry per WX-2 (real metrics from CHANGELOG only — no
  invention).

---

## §6. MAJOR graduation criteria (telegraphed; NOT a v11.1.0 commitment)

The user's directive **"在确保有效性后，最终提交到一个 Major 版本"** is
telegraphed for v12.0.0. The graduation gate runs at v12.0.0 SI-1 (cycle
N+2 from this v11.1.0 close per W-21 2-cycle deliberation cadence) and
requires ALL of the following:

1. **W-3 / SI-3 STRICT MAJOR composite ≥ 9.0 / 10** at v12.0.0 cycle
   close (stricter than the v11.1.0 MINOR threshold ≥ 8.5).
2. **1-2 v11.1.x stability patches** (v11.1.1, optionally v11.1.2) with
   operator feedback collected via
   `.local/feedbacks/feedback_for_v11.1.0.md` (the next user-feedback
   file per the v11.0.0 retrospective Q1-Q10 sign-off pattern).
   Stability period observation: cascade behaviour in real cycles for
   ≥ 1 month before MAJOR.
3. **W-21 deferral protocol respected**: this cycle (v11.1.0) does NOT
   propose new Soul rules. If cascade enforcement matures into an
   immutable invariant — "the multiplicative cost of (every future
   agent dispatch) × (every future code change)" per W-21 §3 — the
   v11.1.0 retrospective §3 (W-7 / SI-8) telegraphs an **S-11 candidate
   for v13.0.0 SI-1** (per the W-21 2-cycle gap rule: cycle N telegraph
   → cycle N+2 SI-1 evaluation; v11.1.0 → v13.0.0 honours the
   2-MINOR-cycle gap). DO NOT promise S-11 in v11.1.0.
4. **v12.0.0 SI-1 gap analysis** must explicitly evaluate whether A-7
   (the v11.1.0 cascade rule) merits Soul promotion vs Architecture-stable.
   The decision-rule reasoning in D1 §4 (conditional + implementation-coupled
   = Architecture, not Soul) must be re-checked against 1-2 cycles of
   field evidence. If field evidence shows cascade-depth violations
   are class-of-bugs that survive Architecture A-7 enforcement,
   promote to S-11 (after the W-21 2-cycle gap).
5. **A-7 STRICT promotion** — currently lands at v11.1.0 in
   PERMISSIVE / WARN-ONLY mode (DEFAULTS-PERMISSIVE-IN-MINOR /
   STRICT-IN-NEXT-MAJOR pattern per D2 §6 finding 1); v12.0.0 PV-X
   promotes to hard-fail in plan-mode validation + audit `--strict`
   default-ON (G-AUDIT-1 ratchet).
6. **SHORTCUT_SIMPLE retirement** — v9.3.0 PV-06 D-E-4 SHORTCUT_SIMPLE
   verdict + `DEVOLAFLOW_SIMPLE_SHORTCUT` env flag are deprecated in
   v11.1.0 retrospective §3 deferral; removal scheduled for v12.0.0
   SI-1.

---

## §7. Risk register

| ID | Risk | Probability | Impact | Mitigation |
|---|---|:---:|:---:|---|
| **R-1** | Cascade overhead regression — extra L1+L2 dispatches inflate token cost ~2-3× for STANDARD tier (per D2 §7 cost model: STANDARD goes from ~8K (collapse) → ~12-20K (cascade)) | High | Medium | (a) PV-05 EvoBench scenarios pin cascade composite ≥ collapsed composite − 5% (W-4 / SI-4 regression threshold); (b) PV-02 keeps `force_no_change=True` parameter as legitimate operator override (D-A-4 surface preserved); (c) v11.1.0 ships A-7 in PERMISSIVE / WARN-ONLY mode (DEFAULTS-PERMISSIVE-IN-MINOR per D2 §6 finding 1); v12.0.0 promotes to STRICT only after 1-2 stability patches collect operator feedback; (d) D2 §7 cost model documents the trade explicitly so operator expectations are anchored. |
| **R-2** | Operator confusion during transition — operators trained on "L1+L2 only-when-needed" advisory now see strict cascade requirement; 3 different "skip cascade" mechanisms (`force_no_change` + `--no-change` + `SHORTCUT_SIMPLE`) per D2 §5 increase mental model cost | High | Medium | (a) PV-03 SKILL.md rewording is explicit + clear (line 64 + 105-107 + 180 all carry the same cascade-required wording); (b) PV-04 G-PLAN-1 §5.1 DO list documents `force_no_change` as the primary surface (function parameter; W-20 reuse-first); (c) v11.1.0 retrospective §3 telegraphs SHORTCUT_SIMPLE retirement for v12.0.0 — collapse 3 surfaces → 2; (d) PV-07 bilingual EN/ZH demo refresh (`workflow-system/human/en/getting-started.md` + `workflow-system/human/zh/getting-started.md`) explicitly documents the 3-surface state during the transition. |
| **R-3** | Cache-layout drift — schema changes affect canonical_order positions 13-17 OR (worst case) the frozen prefix 1-12 | Low | Critical | (a) D1 §5 + this plan §3 PV-04 explicitly NEST `gate.cascade_required` + `gate.cascade_min_layers` per A-2.3 (NEST not APPEND) — `canonical_order` length stays at **17**; (b) `tests/test_layout_invariant_multi_baseline.py` 10/10 historical baselines GREEN by construction (NEST under existing `gate` block at frozen position 12; baselines unchanged); (c) PV-04 W03 explicitly verifies the multi-baseline byte test as part of the changelog wave; (d) S-10 byte-identity invariant verified via `tests/test_dispatch_emission_runs_hooks.py`. |
| **R-4** | W-17 test count cap exceeded — cumulative test additions exceed +150 cycle ceiling | Low | Medium | (a) §2 effort table forecasts +28 to +40 cumulative — well under +150 cap with substantial headroom; (b) PV-05 W03 explicitly runs the W-17 mid-cycle audit (`git diff cec4cc4..HEAD --stat -- tests/`); (c) parametrize expansions over EvoBench YAML scenarios (PV-05 W02 T02) do **NOT** count per W-17 ("Parametrize expansions of EXISTING test functions over newly-added data ... do NOT count toward the cap"); (d) W-17 escape valve: defer non-essential tests to v11.1.x patches if forecast drifts > +50 at PV-05. |
| **R-5** | NineS unavailable in CI / blocked dependency — PV-06 cannot run self-eval | Low | High | (a) sibling Wave 1 D2 already proved hybrid mode works (NineS 3.3.0 ran successfully at v11.0.1 baseline; binary at `/root/miniforge/bin/nines`); (b) `nines.toml` config is committed at repo root (not gitignored); (c) PV-06 fallback per W-2 normative note — "manual analysis following the same dimensions is acceptable but must be explicitly noted as manual"; (d) v11.0.0 cycle precedent: pre-v11 self-loop completed end-to-end with NineS available — same toolchain in v11.1.0. |
| **R-6** | Cascade vs `force_no_change` semantic conflict — operator sets `force_no_change=True` but A-7 cascade-required mandates the chain | Medium | Low | (a) PV-02 `cascade_requirement(complexity)` is evaluated **SEPARATELY** from `activation_verdict()`; the two contracts compose orthogonally — cascade applies to dispatch shape (gate.cascade_required); `force_no_change` applies to workspace activation only (per A-6.3); (b) PV-02 docstring in `change_activation.py` documents the orthogonality + the worked example "operator sets force_no_change=True on a STANDARD task → workspace not engaged BUT cascade still required for the dispatch chain"; (c) PV-02 release notes explicitly separate the two semantics. |
| **R-7** | `SHORTCUT_SIMPLE` v9.7.0 promote-to-default-ON plan conflicts with cascade restoration (v9.3.0 PV-06 D-E-4 docstring telegraphs default-ON for v9.7.0) | Medium | Medium | (a) PV-06 (or telegraph to v11.2.0) defers the v9.7.0 promotion until cascade-strictness lands in v12.0.0; pure documentation deferral in `references/env-flags.md` §"Future plans"; (b) v11.1.0 retrospective §3 deferral list explicitly carries the SHORTCUT_SIMPLE retirement for v12.0.0 SI-1 evaluation; (c) D2 §3 finding 3 documents the conflict; (d) zero code changes required in v11.1.0 — pure documentation deferral. |
| **R-8** | Multi-round reinforcement at PV-06 stalls (composite < 8.5 after 5 rounds + stagnation 2+ rounds → P4 escalate to user) | Low | High | (a) §4 self-iteration protocol explicitly defines stagnation Δ < 1.0 over 2+ rounds → ExceptionEscalation upward to L0 → L0 escalates to user; (b) the user is the only authority who can authorise round 6+ OR composite-threshold relaxation OR cycle-scope reduction (e.g., defer G-AUDIT-1 ratchet to v11.1.x patch); (c) §8 Decision Point #3 is the user touchpoint for this path; (d) D2 §8 forecast lift +1.65 over 5 rounds is achievable per cycle precedent (v8.4.0 cycle hit composite 8.7 after 3 rounds of reinforcement). |

---

## §8. Decision points (user-approval gates)

The cycle has **4 explicit user-decision touchpoints**. At each, the
user gets to APPROVE / REDIRECT / ABORT.

### Decision Point #1 — After PV-01 (NOW — this stage report)

**When**: after the L1 stage report (D4) returns to L0 and L0 surfaces
the PV-01 artifact set to the user.

**L0 surfaces**:

* The 4 PV-01 artifacts (D1 gap analysis + D2 NineS analysis + D3 this
  cycle plan + D4 stage report) and their AC verdicts.
* The G-CLASSIFY-1 Candidate selection question (A 2-tier-with-single-
  threshold vs B default-cascade-with-explicit-TRIVIAL-opt-out vs C
  rule-based-4-tier-collapse from D1 G-CLASSIFY-1 §3); this plan does
  **NOT** select — PV-02 is the deliberate PV that picks per the
  user's directive "对于任务复杂度的判定，需要有一个更好的、更简明的判断标准".
* The PV-02..PV-07 cycle scope summary (this §2 table).
* The cascade-restoration cycle goal verbatim (§1 Chinese feedback).
* Branch push authorisation question (the L1 stage report includes a
  GO / HOLD / ESCALATE recommendation).

**User options**:

* **APPROVE** → proceed to PV-02 (classifier redesign + W-16 baseline
  regen).
* **REDIRECT** → request scope changes (e.g., reduce gap inventory;
  defer specific gaps to v11.2.0; pre-select Candidate C for the
  classifier; demand additional research artifact like a v10.5.0 PV-01
  ADR re-read).
* **ABORT** → cancel the cycle (e.g., user decides cascade restoration
  is not needed; revert to v10.5.0 advisory state).

### Decision Point #2 — After PV-04 (plan-mode + schema NEST + runtime override land)

**When**: after PV-04 ships G-PLAN-1 plan-mode Constraints Checklist
item #10 + schema NEST + runtime override. The user sees the FIRST
functional cascade enforcement surface ("plans for STANDARD+ tasks
that omit L1 + L2 fail the checklist").

**L0 surfaces**:

* PV-04 retrospective summary;
* First plan-mode rejection case (a deliberately-broken plan that
  fails item #10);
* Operator-facing behaviour-change note (3-surface state: `force_no_change`
  + plan-mode item #10 + runtime `_PLAN_MODE_OVERRIDES`);
* Cumulative test count delta vs cycle baseline (W-17 mid-cycle
  preview).

**User options**:

* **APPROVE** → proceed to PV-05 (the high-token-cost PV with EvoBench
  scenarios + A-7 rule + audit ratchet).
* **REDIRECT** → adjust enforcement strictness (e.g., switch from FAIL
  to WARN-ONLY for SIMPLE-boundary tasks); request additional doc
  surfacing for the 3-mechanism collapse plan; defer G-PLAN-2 runtime
  override to v11.1.x patch.
* **ABORT** → revert PV-04 if the enforcement is too aggressive
  (operator feedback shows excess false-positive plan rejections).

### Decision Point #3 — At MINOR close (PV-07; v11.1.0 tag)

**When**: after PV-07 W-9 / SI-10 7-step regression PASSES + retrospective
+ archive ready.

**L0 surfaces**:

* Full cycle retrospective per W-7 / SI-8 (4 mandatory sections:
  Gaps identified + What was implemented + What was deferred and why
  + Key learnings);
* W-3 / SI-3 final composite (per PV-06 NineS self-eval);
* Risk-register actuals (which R-X fired during the cycle, how
  mitigated);
* Deferral list for v12.0.0 SI-1 telegraph (S-11 candidate;
  SHORTCUT_SIMPLE retirement; A-7 STRICT promotion; cascade ratio
  threshold tightening 30% → 10%);
* Cumulative test count delta vs +150 cap.

**User options**:

* **APPROVE** → tag v11.1.0; merge MR; proceed to v11.1.x stability
  patches.
* **REDIRECT** → reopen reinforcement loop if composite borderline
  (8.5 ± 0.2); request additional W-9 / SI-10 step (e.g., manual
  cascade-ratio audit on v11.1.0-modified cycle docs); demand
  retrospective rewrite if §3 deferral list is incomplete.
* **ABORT** → block tag; defer cascade restoration to v11.2.0 (rare;
  only if cascade overhead regression is unacceptable per R-1
  EvoBench evidence).

### Decision Point #4 — Before MAJOR (v12.0.0 SI-1)

**When**: after 1-2 v11.1.x stability patches collect operator feedback
via `.local/feedbacks/feedback_for_v11.1.0.md`.

**L0 surfaces**:

* v11.1.x patch retrospectives + operator feedback summary;
* v12.0.0 SI-1 gap analysis with §6 candidate items (composite ≥ 9.0;
  A-7 STRICT promotion; SHORTCUT_SIMPLE retirement; cascade ratio
  tightening);
* W-21 retrospective deferral cadence — the v11.1.0 retrospective §3
  S-11 candidate (cascade-as-Soul-rule) is FIRST-TELEGRAPHED at
  v11.1.0 and would be SI-1-evaluated at v13.0.0 (NOT v12.0.0 — the
  W-21 2-cycle gap rule mandates the cascade-as-Soul evaluation skips
  v12.0.0 even though v12.0.0 is the next MAJOR).

**User options**:

* **APPROVE** → proceed to v12.0.0 cascade-strictness MAJOR cycle.
* **REDIRECT** → adjust the 4 §6 candidates (e.g., keep
  SHORTCUT_SIMPLE; demote A-7 strict to WARN-only); demand additional
  v11.1.x patch (v11.1.3) before MAJOR consideration.
* **ABORT** → no v12.0.0 cycle (cascade restoration ships at v11.1.x
  level permanently; A-7 stays in PERMISSIVE / WARN-ONLY mode).

---

## §9. Cross-references

* **Predecessor artifacts (verbatim per CO-2)**:
  * `.local/feedbacks/feedback_for_v11.0.0.md` — verbatim user
    directive (§1 source-of-truth).
  * `.local/research/v11.1.0_gap_analysis.md` — D1 SI-1 planning gate
    (10 gaps, 4 P0 + 3 P1 + 2 P2 + 1 P3, drives §2 PV scope).
  * `.local/research/v11.1.0_nines_analysis.md` — D2 SI-2 NineS-driven
    analysis (composite **6.85/10** baseline; 8 findings F-001..F-008
    feed §3 cascade decomposition rationale).
  * `.local/research/v11.1.0_nines_raw.json` — D2 raw NineS evaluator
    scores (16 quality + 5 hygiene dimensions).
  * `.local/research/v11.1.0_pv01_stage_report.md` — D4 stage report
    back to L0 (sibling artifact authored by L1 stage agent).
* **Owned files (this PV — cycle plan author scope)**:
  * `.local/research/v11.1.0_cycle_plan.md` (this file) — sole
    writable file per dispatcher manifest.
* **Cycle-archive precedents (S-7 + W-19)**:
  * `docs/cycle-archive/v11.0.0/v10.5.0_retrospective.md` §1 D-A-1 —
    original audit + advisory rationale being SUPERSEDED by this cycle.
  * `docs/cycle-archive/v11.0.0/other/v10.5.1_layer_usage_audit.md` —
    empirical evidence (audit measured 0 dispatch lines across 14
    cycle docs; do NOT mis-read as 100% collapse).
  * `.local/research/v11.0.0_cycle_plan.md` — v11.0.0 cycle plan
    template (5 PVs + 1 MAJOR rollup precedent for the 7-PATCH +
    MINOR-rollup structure adopted here).
  * `.local/research/v11.0.0_retrospective.md` §3 deferrals — verified
    no overlapping work (S-11 candidate is re-classified as A-7 per
    D-P-2; cascade-restoration A-7 is a DISTINCT new rule motivated
    by `feedback_for_v11.0.0.md`).
  * `.local/research/v11.0.0_evaluation.md` — v11.0.0 W-3 / SI-3
    STRICT MAJOR evaluation (composite 9.30; template for §5 PV-06
    evaluation format).
* **Owned-file targets across the cycle (PV-02..PV-07 — read-only at
  PV-01)**:
  * `workflow-system/agent/SKILL.md` — current `__version__` 11.0.1;
    cascade-collapse signals at lines 64 + 105-107 + 165-180 (revised
    in PV-03).
  * `workflow-system/agent/examples/multi-stage-trace.md` — current XL
    tier (242 lines / 1600 budget); rows 200-211 §"When NOT to use"
    revised in PV-03.
  * `workflow-system/agent/references/plan-mode-enforcement.md` —
    current Large tier (~810 lines / 1000 budget); §3.1 + §4 item #10
    + §5.1 extended in PV-04.
  * `workflow-system/agent/references/agent-hierarchy.md` — canonical
    4-layer reference (consistent with A-1; no contradictions to
    resolve; PV-03 consistency check is read-only per A-1 trivial
    waiver).
  * `src/devolaflow/skills/change_activation.py` — current 385 LOC;
    `classify_complexity` + `activation_verdict` + new sibling pure
    function `cascade_requirement` redesigned in PV-02.
  * `src/devolaflow/task_adaptive_selector.py` — current
    `_PLAN_MODE_OVERRIDES` at lines 67-77; G-PLAN-2 optional extension
    in PV-04.
  * `src/devolaflow/feedback.py` —
    `ProposalGenerator.generate_round_dispatch` + S-10 hook chain
    wiring (preserved BYTE-IDENTICAL through PV-04 NEST extension).
  * `src/devolaflow/gate/scorer.py` — `evaluate_gate` (PV-04
    cascade-required validator integration; CP-4 mandates full gate
    test suite re-run).
  * `scripts/audit_layer_usage.py` — observability-only audit; PV-05
    adds `--strict` flag + `cascade_ratio` field (G-AUDIT-1).
  * `tests/test_change_activation_heuristic.py` — current 13 tests
    (per D2 §4 inspection); refresh in PV-02.
  * `tests/test_audit_layer_usage.py` — current 9-11 tests (per D2 §4
    inspection); extend in PV-05.
  * `tests/test_dispatch_emission_runs_hooks.py` — S-10 invariant
    guard; PV-04 must keep BYTE-IDENTICAL.
  * `tests/test_layout_invariant_multi_baseline.py` — currently pins
    10 historical baselines (per the test docstring: v7.0.0, v7.3.0,
    v8.0.0 P-08, v8.0.0 P-10, v8.3.0 PV-05, v8.4.0, v9.2.0, v9.3.0,
    v9.7.0, v10.2.0); PV-04 must keep all 10 GREEN by construction
    (NEST under `gate` at frozen position 12).
  * `.rules/architecture.mdc` — current §A-1..A-6; PV-05 appends §A-7
    cascade-depth rule.
  * `AGENTS.md` + `.cursor/rules/repo-governance.mdc` — auto-recompiled
    via `make compile-rules` in PV-05 (do NOT hand-edit per
    `tests/test_no_ghost_features.py::test_rule_surfaces_compile_only`).
  * `schemas/lean-dispatch.yaml` lines 544-563 — `canonical_order`
    length **17** (frozen prefix 1-12 + append-only tail 13-17:
    `repos` / `behavioral_guidelines` / `acceptance_criteria_v2` /
    `change_context` / `predecessor_dedup_ledger`); PV-04 NEST
    preserves length 17.
  * `CHANGELOG.md` — PV-02..PV-06 add per-PATCH entries
    (`## [11.0.2]` .. `## [11.0.6]`); PV-07 adds `## [11.1.0]`
    MINOR-close at top.
* **External tools (S-7 — GitHub URLs only; no local clone paths
  hardcoded)**:
  * DevolaFlow / EvoBench: `https://github.com/YoRHa-Agents/DevolaFlow`
  * NineS: `https://github.com/YoRHa-Agents/NineS`

---

**Artifact verified per acceptance criteria (this cycle plan's own gate)**:

1. ✓ Path `.local/research/v11.1.0_cycle_plan.md` exists (this file).
2. ✓ §1 contains verbatim Chinese feedback (CO-2 — quoted, not translated).
3. ✓ §2 PV table has **7 rows** (PV-01 through PV-07); each row carries
   ID + Scope + Owned files (5-10 items) + AC (3-5 testable items) +
   Version bump + Gate profile + Wall-clock + NEW test functions.
4. ✓ §3 has explicit cascade decomposition for each impl PV (PV-02..PV-07)
   with L0 dispatch + L1 Stage(s) + L2 Wave(s) + L3 Task(s) for each.
5. ✓ §4 self-iteration protocol with max_rounds = 5 + reinforcement on
   FAIL + stagnation rule (Δ < 1.0 over 2+ rounds → P4 escalate to user).
6. ✓ §5 MINOR-close 6-bullet checklist with verbatim shell commands
   (W-3 SI-3 + W-9 SI-10 7-step + W-19 archive + CHANGELOG + canonical 7
   + bilingual demo).
7. ✓ §6 MAJOR graduation telegraphed (NOT committed); W-21 freeze
   respected (zero new Soul rules; A-7 is Architecture).
8. ✓ §7 risk register with **8 risks** (R-1..R-8) + probability + impact
   + mitigation; covers cascade overhead, operator confusion, cache-layout,
   W-17 cap, NineS unavailability, force_no_change conflict, SHORTCUT_SIMPLE
   conflict, multi-round stagnation.
9. ✓ §8 **4 decision points** (≥ 4 user-approval gates: after PV-01;
   after PV-04; at MINOR close; before MAJOR).
10. ✓ Zero source-code, test, schema, SKILL.md, or rule edits made
    (read-only artifact; all references are to FUTURE PV scope).
11. ✓ File ownership: only `.local/research/v11.1.0_cycle_plan.md`
    written by this artifact author; `.local/` is gitignored per repo
    convention (artifact lives in working tree only).
12. ✓ External tools by GitHub URL only (S-7); no local clone paths.
