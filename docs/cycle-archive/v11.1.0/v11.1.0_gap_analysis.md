# v11.1.0 Cascade-Restoration MINOR Cycle — SI-1 Iteration Planning Gate

> W-1 / Rule SI-1 planning artifact. Authored at cycle start, BEFORE any
> implementation, per `.cursor/rules/repo-governance.mdc` §W-1 / `AGENTS.md`
> §W-1. Predecessor reads validated by L1 Stage
> `feature/v11.1.0-cascade-research-pv01`. Per-PV decomposition is the L0
> cycle plan author's responsibility (sibling Wave 2 L3 Task C); this
> artifact enumerates the gaps + priority ranking + file-level fix scope
> only.

## §1. Cycle frame

* **Cycle name**: v11.1.0 cascade-restoration MINOR cycle.
* **Base version**: v11.0.1 (current `__version__` in `src/devolaflow/__init__.py:6` — verbatim string `"11.0.1"`).
* **Target MINOR**: v11.1.0.
* **Branch**: `feature/v11.1.0-cascade-research-pv01` (this PV-01) — off
  `origin/main` (last commit `cec4cc4 Merge pull request #125 from
  YoRHa-Agents/release/v11.0.1`).
* **Graduation telegraph**: v12.0.0 MAJOR after 1-2 stability patches in
  the v11.1.x line, per the user's "确保有效后，最终提交到一个 Major 版本"
  directive (see §1 verbatim block below).
* **Cycle owner**: this is **PV-01 of the v11.1.0 cycle** — RESEARCH ONLY,
  NO code edits. Per W-1, no implementation may begin until this gap
  analysis is in place + reviewed.
* **Cycle theme**: restore the strict 4-layer cascade dispatch behaviour
  (L0 → L1 → L2 → L3 for medium+ complexity tasks) that the v10.5.0 PV-01
  D-A-1 audit + advisory annotation eroded.

### Verbatim user feedback (source-of-truth — CO-2)

The cycle's source-of-truth direction is the user's feedback at
`.local/feedbacks/feedback_for_v11.0.0.md`. Quoted VERBATIM (CO-2 / S-2 —
do NOT paraphrase, do NOT translate):

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

## §2. Current state vs target

| # | Axis | Current state | Target state |
|---|---|---|---|
| 1 | Strict-cascade enforcement | SKILL.md endorses L0→L3 collapse for SIMPLE/STANDARD via line 64 advisory ("Full hierarchy (L1+L2 only-when-needed; see `examples/multi-stage-trace.md`)") + line 105-107 "Simple task shortcut" + line 180 "Layer collapse pattern (v10.5.0): most cycles collapse L0→L3". `agent-hierarchy.md` §1 still pictures the canonical 4-layer chain (no contradiction at the reference level), but the SKILL.md advisory is the cache-prefix-loaded surface every dispatcher reads. Empirical evidence: `docs/cycle-archive/v11.0.0/other/v10.5.1_layer_usage_audit.md` reports "Total `Dispatch type:` lines: **0**" and "Standalone L1 Stage dispatch ratio: **0.00%**" / "Standalone L2 Wave dispatch ratio: **0.00%**" / "L0->L3 collapse evidence ratio: **0.00%**" — but interpret carefully: the audit MEASURED no `Dispatch type:` lines at all (the regex `Dispatch\s+type\s*[:=]\s*(Wave\|Stage\|Task)` per `scripts/audit_layer_usage.py:88-91` did not match any text in 14 cycle docs), NOT that 100% of dispatches collapsed. The `force_no_change` (v10.5.0 PV-03) + `SHORTCUT_SIMPLE` (v9.3.0 PV-06) verdicts further telegraph cascade-collapse as a first-class shortcut. | Strict cascade (L0→L1→L2→L3) MANDATORY for STANDARD/COMPLEX complexity; collapse permitted ONLY for TRIVIAL (single file <20 LOC) or SIMPLE (1-3 files, clear scope) AND only as an explicit operator override (not the default). The user directive "不能由 L0 直接调动 L3" is the cycle invariant. SKILL.md advisory + multi-stage-trace.md "When NOT to use" rows + agent-hierarchy.md must agree. |
| 2 | Complexity classifier | 4-tier classifier in `src/devolaflow/skills/change_activation.py::classify_complexity` keyed on `(files_count, loc_estimate, is_cross_cutting)` — TRIVIAL (`files_count ≤ 1` AND `loc_estimate < 20` AND NOT cross-cutting), SIMPLE (`files_count ≤ 3` AND NOT cross-cutting), STANDARD (`files_count ≤ 10` OR cross-cutting), COMPLEX (`files_count > 10`). Two override surfaces: `force_no_change=True` (v10.5.0 PV-03 D-A-4) and `shortcut_verdict()` returning `SHORTCUT_SIMPLE` when `DEVOLAFLOW_SIMPLE_SHORTCUT=1` AND complexity ∈ {SIMPLE, TRIVIAL} (v9.3.0 PV-06). 13 unit tests in `tests/test_change_activation_heuristic.py` pin every cell. | A "更好的、更简明的判断标准" (better, simpler standard) — PV-02 picks one of 3 candidates (see G-CLASSIFY-1 in §3); the bar is: a single-line decision rule an operator can quote from memory, with cascade as the unambiguous default for everything except the explicit single-file <20-LOC trivial case. |
| 3 | Plan-mode enforcement | `references/plan-mode-enforcement.md` §3 Plan Output Template (lines 102-154) names L0/L1/L2/L3 in the 4-row Execution Model table (line 117-122) and §4 Constraints Checklist (lines 333-369) enforces P1 with item #1 ("Every task row is L3 — no L0-L2 performing work. P1 enforced. Trivial exception (`< 20 lines`, single file) MAY be inlined into L0 with explicit `[trivial waiver]` annotation"). Items #2-#9 cover wave/stage budgets, DAG, convergence, P5 — but **none** require a STANDARD+ plan to carry an L1 Stage row OR an L2 Wave row before the L3 Task row(s). A plan that lists ONLY L3 task rows directly under L0 (zero L1, zero L2 dispatcher rows) currently passes the 9-item checklist. Plan-mode runtime overrides (`src/devolaflow/task_adaptive_selector.py::_PLAN_MODE_OVERRIDES`) escalate `agent_hierarchy` + `decomposition_gate` + `rationalization_prevention` sections to `critical`; they do not enforce cascade depth structurally. | §4 Constraints Checklist gains a new item: "Every STANDARD+ plan has at least one L1 Stage row AND at least one L2 Wave row before the L3 Task row(s) — cascade-depth check; trivial exception inherits from item #1's `[trivial waiver]` carve-out." Optionally extend `_PLAN_MODE_OVERRIDES` with a `plan_mode_cascade_required: bool` runtime hook (G-PLAN-2). The plan-mode template + checklist should fail-closed for STANDARD+ plans that omit L1/L2. |
| 4 | Test + performance evaluation | Gate composite formula (`workflow-system/agent/references/decomposition-gate.md` §5.3) + standard/strict/audit profiles (§5.4) cover 4-7 dimensions. EvoBench scenarios live at `benchmarks/devolaflow_context/`; per W-4 / SI-4 they regress when `task_adaptive_selector.py`, `context_profiles.yaml`, lean message schemas, SKILL.md sections, or gate modules change — but no scenario currently measures cascade-vs-collapse cost delta. `tests/test_change_activation_heuristic.py` has 13 unit tests pinning the classifier truth table; `tests/test_audit_layer_usage.py` has 9 tests pinning audit-script algorithm correctness; **no test pins cascade compliance** (e.g., no test asserts that STANDARD-tier inputs MUST result in a verdict mandating cascade). `scripts/audit_layer_usage.py::run` is observability-only (returns 0 unconditionally per docstring "always 0 — the audit is observability-only; no docs found is reported as an empty audit, not an error"). | Add cascade-compliance tests (G-TEST-1) pinning the new classifier verdict matrix; extend the audit script to FAIL CI when cascade ratio drops below threshold (G-AUDIT-1); regenerate EvoBench baselines wholesale per W-16 cycle-start with cascade-vs-collapse perf scenarios (G-BENCH-1); run NineS deep self-eval at PV-06 to validate iteration ROI (G-NINES-1). |

## §3. Gap inventory

10 gaps identified. Priority distribution: **4 P0 + 3 P1 + 2 P2 + 1 P3**.
Each entry carries (a) deficiency, (b) priority, (c) proposed fix with
file-level scope. P0 set: G-CASCADE-1, G-CLASSIFY-1, G-PLAN-1, G-TEST-1.
P1 set: G-CASCADE-2, G-BENCH-1, G-NINES-1. P2 set: G-AUDIT-1, G-PLAN-2.
P3 set: G-DOC-1.

### G-CASCADE-1 — SKILL.md cascade restoration

* **(a) Deficiency**: SKILL.md endorses L0→L3 collapse via three coupled
  surfaces that the user's feedback "不能由 L0 直接调动 L3" directly
  rejects:
  1. Line 64 (Quick Action Decision row "Standard"): `"Full hierarchy
     (L1+L2 only-when-needed; see examples/multi-stage-trace.md)"` —
     the "only-when-needed" wording was the v10.5.0 PV-01 D-A-1
     advisory annotation; under v11.1.0 cascade-restoration it must
     change to "Full hierarchy (L1+L2 REQUIRED — see
     `examples/multi-stage-trace.md`)" or equivalent.
  2. Lines 105-107 (Simple task shortcut block):
     `"**Simple task shortcut** (1-3 files, < 1 hour): Skip multi-stage
     hierarchy. Dispatch a **single Task Agent** via Task tool with
     full context. Verify output and report."` — this stays for the
     SIMPLE tier (≤3 files), but must NOT apply to STANDARD+; current
     wording is silent on the STANDARD boundary.
  3. Line 180 (4-Layer Agent Hierarchy section trailer):
     `"**Layer collapse pattern (v10.5.0):** most cycles collapse L0→L3;
     engage standalone L1+L2 only for multi-team analyze with cross-stage
     merge (see examples/multi-stage-trace.md)."` — this line
     EXPLICITLY endorses L0→L3 collapse as the norm. Must be replaced
     with cascade-required wording per the user directive.
* **(b) Priority**: **P0** — blocker for cycle goal (the SKILL.md
  cache-prefix surface is what every dispatcher reads first; without
  this fix every other change is a paper improvement).
* **(c) Proposed fix with file-level scope**:
  - `workflow-system/agent/SKILL.md` — edit:
    * Line 64: replace "L1+L2 only-when-needed" with cascade-required
      wording for STANDARD+ tier; preserve "see
      `examples/multi-stage-trace.md`" cross-reference.
    * Lines 105-107: tighten the "Simple task shortcut" block to bind
      to SIMPLE/TRIVIAL tier only; add explicit "STANDARD+ MUST use
      full hierarchy" sentence.
    * Lines 77-95 (Mode Awareness + AGENT MODE Execution Protocol):
      reinforce the dispatch chain at step 4 ("DISPATCH each task →
      Task tool") to specify the cascade chain L0 → L1 → L2 → L3 for
      STANDARD+.
    * Line 180: REPLACE the "Layer collapse pattern (v10.5.0)" line
      with a cascade-required statement citing the v11.1.0 cycle and
      `examples/multi-stage-trace.md` as the worked walkthrough.
    * Frontmatter `version:` + banner + body "Current version:" text:
      11.0.1 → 11.1.0 at cycle close (canonical 7 sync per CP-3 / SF-3).
  - SF-1 line budget: SKILL.md current 467 / 500 ceiling — net edit
    must stay ≤ 500. The cascade-required rewording is replacement, not
    addition; budget is comfortable.
  - W-18 ghost-audit refresh PRECONDITION: before the v11.1.0 PATCH
    CHANGELOG entry mentions "G-CASCADE-1 cascade restoration", add a
    coverage assertion to `tests/test_no_ghost_features.py` that
    verifies SKILL.md line 180 NO LONGER contains the literal string
    `"Layer collapse pattern"` (negative lint). Then add the CHANGELOG
    entry. Sequence per W-18.

### G-CASCADE-2 — multi-stage-trace.md revision

* **(a) Deficiency**: `workflow-system/agent/examples/multi-stage-trace.md`
  §"When NOT to use this pattern" lines 200-211 lists 4 collapse-OK
  rows that the user's feedback challenges:
  1. "3-file paired source+test edit + spec doc | 1 author, 1 task |
     Single L3 (TRIVIAL or SIMPLE per
     `change_activation.classify_complexity`)" — passes (TRIVIAL/SIMPLE
     are still collapse-OK under v11.1.0).
  2. "Refactor across 8 modules in 1 package | 1 author, 1 task with
     disjoint owned-files manifest | L0 → L3 with a per-task wave
     partition (no L1 stage needed)" — **violates the user directive**:
     8 files is STANDARD per the classifier (`files_count ≤ 10`), and
     the user says STANDARD+ MUST cascade through L1+L2.
  3. "Bug investigation across 3 subsystems | 1 hypothesis test, not 3
     parallel analyses | Single L3 trace + diagnose; if subsystem-
     specific fixes diverge, dispatch from there" — borderline; 3
     subsystems is at the SIMPLE/STANDARD boundary; classifier returns
     SIMPLE if `files_count=3`, STANDARD if cross-cutting=True.
  4. "Audit X across the codebase | 1 read-only walk + 1 report |
     Single L3 audit (the audit IS the artifact)" — **violates the
     user directive** when X spans STANDARD+ scope; the v10.5.1
     audit itself was a single-L3 walk that produced 0 useful
     dispatch-line measurements per the audit summary.
* **(b) Priority**: **P1** — high. The example is loaded by L0/L1/L2
  agents when the multi-team analyze pattern fires; misleading
  collapse-OK rows undermine G-CASCADE-1 even after SKILL.md is fixed.
* **(c) Proposed fix with file-level scope**:
  - `workflow-system/agent/examples/multi-stage-trace.md` — edit:
    * Lines 200-211 §"When NOT to use this pattern": REMOVE rows 2 +
      4 (8-module refactor + codebase-wide audit), or rewrite them to
      MANDATE cascade for STANDARD+ scope. Keep row 1 (TRIVIAL/SIMPLE)
      and tighten row 3's wording so the SIMPLE-tier verdict is
      explicit.
    * Lines 30-46 §"Why this example exists": update the framing —
      the v10.5.0 advisory is being SUPERSEDED by v11.1.0 cascade-
      restoration; this example becomes the WORKED CANONICAL pattern,
      not the COUNTER-CASE.
    * Frontmatter `last_updated:` field: `"2026-05-04"` → `"2026-05-08"`
      (or actual PV-02 date).
  - SF-1 XL tier budget: file is currently 242 / 1600 lines. Net edit
    is small; budget comfortable.
  - W-18 ghost-audit refresh: add coverage assertion that the file
    no longer contains the verbatim string `"L0 → L3 with a per-task
    wave partition (no L1 stage needed)"`.

### G-CLASSIFY-1 — Classifier "更简明" redesign

* **(a) Deficiency**: The user wrote `"对于任务复杂度的判定，需要有一个更好的、更简明的判断标准"`
  (a better, simpler complexity-judgment standard). The current
  4-tier classifier in `src/devolaflow/skills/change_activation.py`
  (lines 140-190) requires the operator to internalise: 4 tiers ×
  3 inputs (`files_count, loc_estimate, is_cross_cutting`) × 2
  override flags (`force_no_change`, `SHORTCUT_SIMPLE` env-flag) ×
  4 thresholds (`_TRIVIAL_FILE_CEILING=1`, `_TRIVIAL_LOC_CEILING=20`,
  `_SIMPLE_FILE_CEILING=3`, `_STANDARD_FILE_CEILING=10`). That is
  **20+ moving parts** for a "simple" judgment. The two override
  surfaces (`force_no_change` D-A-4 + `shortcut_verdict` D-E-4) further
  fragment the decision boundary.
* **(b) Priority**: **P0** — direct user request; cycle cannot ship
  v11.1.0 without addressing it.
* **(c) Proposed fix with file-level scope**: PV-02 picks ONE of
  three candidate redesigns; this PV-01 documents the trade-offs only
  (the actual selection is PV-02's call):

  **Candidate A — 2-tier with single threshold**: Reduce 4 tiers to
  2: `SIMPLE` if `files_count ≤ 3` AND NOT cross-cutting; `STANDARD+`
  for everything else. Merges TRIVIAL into SIMPLE (since both collapse
  to single-L3 anyway), merges STANDARD into COMPLEX (since both
  cascade). Single threshold `files_count = 3`. Operator-quotable as:
  *"3 files or fewer non-cross-cutting → single Task; otherwise full
  cascade."*
  - Trade-off PRO: maximally simple; one threshold to remember.
  - Trade-off CON: loses TRIVIAL waiver granularity (single-file <20
    LOC trivial edits now go through the same SIMPLE shortcut as
    3-file edits — no harm but loses the "P1 waived" semantic that
    SKILL.md line 62 documents).

  **Candidate B — Default cascade with explicit TRIVIAL opt-out**:
  Replace heuristic-thresholds with one decision: "default cascade
  (L0→L1→L2→L3); only opt-out for explicit TRIVIAL (single file <20
  LOC)". 2-tier outcome (TRIVIAL vs CASCADE-REQUIRED). Operator-
  quotable as: *"Cascade unless single-file < 20 LOC — explicit
  trivial waiver only."*
  - Trade-off PRO: aligns most directly with user's "不能由 L0 直接调动
    L3" — the default IS cascade. Easiest cascade-compliance test
    (any non-TRIVIAL input must produce cascade verdict).
  - Trade-off CON: removes the SIMPLE-tier shortcut that operators
    have relied on since v9.3.0 PV-06; SHORTCUT_SIMPLE verdict is
    deprecated. Higher dispatch overhead for 2-3 file tasks.

  **Candidate C — Rule-based 4-tier collapse**: Preserve 4 tiers (no
  schema break for `Complexity` Literal type) but make the verdict
  matrix collapse to ONE rule: "STANDARD+ ⇒ cascade required". Remove
  `SHORTCUT_SIMPLE` auto-collapse (the v9.3.0 PV-06 D-E-4 dispatcher
  shortcut becomes opt-in only when env flag IS set). `force_no_change`
  preserved as the operator escape hatch (D-A-4 surface unchanged).
  Operator-quotable as: *"STANDARD or higher → cascade. SIMPLE/TRIVIAL
  → may collapse but cascade is still allowed."*
  - Trade-off PRO: zero `Complexity` Literal break; existing 13 unit
    tests + ENV_FLAG_NAME / SHORTCUT_FLAG_NAME contracts stay valid
    (only the verdict matrix changes). Smoothest migration; A-6.1
    public contract preserved.
  - Trade-off CON: 4 tiers is still 4 tiers; the user said "更简明"
    (simpler) and 4 tiers is not simpler than 2.

  **Files affected (any candidate)**:
  - `src/devolaflow/skills/change_activation.py` — `classify_complexity`
    body (lines 140-190); `activation_verdict` body (lines 193-259);
    `shortcut_verdict` body (lines 305-369). Threshold constants
    (`_TRIVIAL_FILE_CEILING` etc.) at lines 134-137 may be removed
    (Candidates A + B) or preserved (Candidate C).
  - `tests/test_change_activation_heuristic.py` — entire file
    (current 13 tests + 274 LOC); rewrite for the chosen verdict
    matrix; preserve `test_from_env_truthy_only_on_literal_one` +
    `test_from_env_constants_pin_public_contract` +
    `test_verdict_string_values_are_stable` (env-flag contract is
    untouched per W-20 reuse-first).
  - `workflow-system/agent/SKILL.md` line 60-65 Quick Action Decision
    table — collapse from 4 rows to 2 (Candidates A + B) or rewrite
    "Action" column (Candidate C).
  - `workflow-system/agent/references/agent-workspace.md` §"When to
    Engage" (cited by SKILL.md line 56) — refresh classifier
    references to new tier scheme.
  - `.rules/architecture.mdc` §A-6.1 ("Classification surface" lines
    156-162) — update the public-contract paragraph if 3-valued
    `ActivationVerdict` literal changes (Candidates A + B may need to
    adjust). Recompile via `make compile-rules` per CLAUDE.md.
  - W-18 ghost-audit refresh: add coverage assertion in
    `tests/test_no_ghost_features.py` that names the chosen
    Candidate's primary symbol.

### G-PLAN-1 — Plan-mode structural enforcement

* **(a) Deficiency**: `workflow-system/agent/references/plan-mode-enforcement.md`
  §4 Constraints Checklist (lines 333-369) is the gate every Plan-mode
  L0 runs as a self-verify before emitting the plan. The current 9
  items enforce P1 (item #1 — every task is L3), wave/stage budgets
  (items #4-#5), task limits (#6), DAG (#7), convergence (#8), P5
  (#9), and the Execution Model verbatim table (#3). **None enforces
  cascade depth.** A plan with all L3 task rows directly under L0
  (zero L1 Stage rows, zero L2 Wave rows) currently PASSES the
  checklist. The user wrote `"另外在 Plan 模式中，也需要能够体现出多层级调度的原则，并且真正使其能够实现"`
  (Plan mode must reflect multi-layer dispatch AND truly enforce it).
  Without a cascade-depth check, the principle is unenforced.
* **(b) Priority**: **P0** — direct user request for plan-mode
  cascade enforcement.
* **(c) Proposed fix with file-level scope**:
  - `workflow-system/agent/references/plan-mode-enforcement.md` §4 —
    add new check item between current items 1 and 2 (or appended as
    item 10):
    ```
    10. **Cascade depth (STANDARD+)** — every plan classified as
        STANDARD or COMPLEX (per `change_activation.classify_complexity`)
        MUST contain at least one L1 Stage row AND at least one L2
        Wave row before the L3 Task row(s). TRIVIAL / SIMPLE plans
        inherit item #1's `[trivial waiver]` carve-out and MAY skip
        L1 + L2.
    ```
    Renumber the current 9 items if appended; or insert as #2 and
    bump the rest. PV-04 picks the numbering.
  - `workflow-system/agent/references/plan-mode-enforcement.md` §3
    Plan Output Template (lines 102-154) — no schema-field change
    (Execution Model table already names L0/L1/L2/L3); add a
    one-sentence reminder under §3.1 Field semantics: "**Layer column
    invariant** — STANDARD+ plans require L1 + L2 rows in addition
    to L3 task rows; the cascade depth is verified by §4 Constraints
    Checklist item #10."
  - `workflow-system/agent/references/plan-mode-enforcement.md` §5.1
    DO list (lines 371-...) — add bullet: "Use the cascade chain
    L0→L1→L2→L3 for STANDARD+ plans; collapse to single-L3 only for
    TRIVIAL/SIMPLE."
  - `tests/test_task_adaptive_selector_plan_mode.py` (cited by
    plan-mode-enforcement.md §2.2 line 99) — extend with a
    cascade-compliance regression test that asserts a STANDARD-tier
    plan-render call fails the checklist when L1/L2 rows are absent.
    G-PLAN-2 (P2) telegraphs the optional `_PLAN_MODE_OVERRIDES`
    runtime hook for cascade enforcement; G-PLAN-1 ships the
    checklist + render-time test only.
  - SF-1 Large tier: plan-mode-enforcement.md is currently 810 / 1000
    lines. Net edit ~30 LOC; budget comfortable.
  - W-18 ghost-audit refresh: add coverage for the new checklist
    item by name (e.g., assert SKILL.md or plan-mode-enforcement.md
    contains the verbatim string `"Cascade depth (STANDARD+)"`).

### G-TEST-1 — Cascade-compliance tests

* **(a) Deficiency**: The user wrote `"最重要的是需要有更完整的测试以及性能评估"`
  (the most important thing is more complete tests + performance
  evaluation). Current test surface:
  - `tests/test_change_activation_heuristic.py` (274 LOC, 13 test
    functions): pins classifier truth table, verdict matrix,
    `force_no_change` override, env-flag literal, but NOT cascade
    compliance (no test asserts STANDARD/COMPLEX inputs MUST produce
    a cascade-mandating verdict).
  - `tests/test_audit_layer_usage.py` (233 LOC, 9 test functions):
    pins audit-script algorithm correctness (`extract_layer_signals`,
    `compute_layer_ratios`, `render_markdown_report`, `scan_cycle_docs`,
    `run`), but NOT cascade enforcement (the audit is observability-
    only per `scripts/audit_layer_usage.py:294` "always 0 — the audit
    is observability-only").
  - `tests/test_dispatch_emission_runs_hooks.py` (362 LOC, ~10 test
    functions): pins lifecycle hook chain coverage (`pre_dispatch` →
    `post_dispatch` → `pre_handoff` → `pre_plugin_invocation` per S-10
    + v9.1.3 PV-03 + v9.4.0 PV-03), but NOT cascade compliance — no
    hook event asserts the dispatch's "from-layer / to-layer" honours
    the cascade chain.
* **(b) Priority**: **P0** — direct user request.
* **(c) Proposed fix with file-level scope**:
  - NEW `tests/test_cascade_enforcement.py` — pin:
    * `STANDARD` and `COMPLEX` classifier inputs → verdict that
      mandates cascade (e.g., `cascade_required=True` field on the
      verdict, or new `CascadeVerdict` Literal).
    * `SIMPLE` and `TRIVIAL` classifier inputs → cascade optional
      (single-L3 collapse permitted).
    * `force_no_change=True` overrides cascade verdict (operator
      escape hatch preserved per D-A-4).
    * Plan-render API call (if exposed via `task_adaptive_selector`)
      with STANDARD-tier inputs but L1/L2-omitted rows → fails the §4
      Constraints Checklist.
  - AMEND `tests/test_change_activation_heuristic.py`:
    * Refresh classifier truth-table tests for the chosen G-CLASSIFY-1
      Candidate (A, B, or C — PV-02 picks).
    * Add test pinning that the chosen Candidate's verdict mandates
      cascade for STANDARD+ tier.
    * Preserve `test_from_env_truthy_only_on_literal_one` +
      `test_verdict_string_values_are_stable` (env-flag + verdict
      string contracts unchanged per W-20).
  - W-17 cap awareness: G-TEST-1 PV-05 budget is +12-18 NEW test
    functions (per §7 effort estimate); within the per-PV +30 cap.
  - W-18 ghost-audit refresh: add coverage assertion in
    `tests/test_no_ghost_features.py` that
    `tests/test_cascade_enforcement.py` exists AND defines at least
    one test function whose name contains `"cascade"`.

### G-BENCH-1 — Cascade-vs-collapse perf scenarios

* **(a) Deficiency**: The user wrote `"以及性能评估"` (and performance
  evaluation). The EvoBench suite at `benchmarks/devolaflow_context/`
  measures context density, dispatch overhead, and gate composite
  trends, but no scenario currently measures the **cascade-vs-collapse
  cost delta** — i.e., how much more (or less) token + wall-clock cost
  the strict 4-layer chain incurs vs the L0→L3 collapse for a
  representative STANDARD-tier task. Without this baseline, the
  cycle's claim "cascade is worth it" is unsubstantiated.

  Reference data point: `examples/multi-stage-trace.md` §"Counting
  the work" line 162-175 quotes verbatim:
  > Total dispatch overhead: **~33K tokens** across L0/L1/L2 layers.
  > Versus a single-L3 collapse that would need to load the entire
  > stack into one ~8K context — a 4x token-budget violation per
  > layer. The 4-layer chain trades **one-time dispatch overhead**
  > for **massive context isolation per L3** — every subsystem
  > analysis is pristine, and the merge stage consumes 6 well-defined
  > artifacts rather than a single "the whole stack" blob.

  This text is the qualitative argument; a quantitative EvoBench
  scenario must replace it.
* **(b) Priority**: **P1** — high. Performance evaluation is
  explicit user request; without numbers, the cycle's value-delta is
  un-falsifiable.
* **(c) Proposed fix with file-level scope**:
  - NEW `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json`
    per W-16 wholesale-baseline-regen-on-cycle-start. Per W-16: "when
    a new MAJOR or MINOR cycle starts, the FIRST PV MUST regenerate
    ALL EvoBench / golden-test baselines wholesale". v11.1.0 is a
    MINOR cycle, so PV-01 (this artifact) telegraphs the baseline
    regen task; PV-02 (the classifier redesign) executes the
    `python -m pytest tests/test_benchmarks.py --regenerate-baselines`
    command and commits the new baseline JSON.
  - NEW EvoBench scenarios under `benchmarks/devolaflow_context/`:
    * `cascade_compliant_standard.yaml` — STANDARD-tier task
      (6 files, 200 LOC) dispatched via L0→L1→L2→L3; measures
      total dispatch token cost + per-layer wall-clock + composite
      score.
    * `collapsed_l0_l3_standard.yaml` — same task dispatched via
      L0→L3 collapse; measures the contrast.
    * `cascade_compliant_complex.yaml` — COMPLEX-tier task (15
      files, 600 LOC) via cascade.
    * `collapsed_l0_l3_complex.yaml` — same COMPLEX task via collapse.
  - `tests/test_benchmarks.py` — extend to load the 4 new scenarios;
    pin: cascade_compliant_standard composite ≥ collapsed composite -
    5% (per W-4 SI-4 regression threshold "composite score must not
    drop >5% below baseline per scenario"). Document expected token
    cost delta in scenario header (use the `~33K tokens` number from
    multi-stage-trace.md as the starting point — to be empirically
    confirmed).
  - W-17 cap awareness: G-BENCH-1 adds parametrize expansions of
    EXISTING `tests/test_benchmarks.py` test functions over the 4
    new YAML scenarios — those do NOT count toward the +30 cap per
    W-17 ("Parametrize expansions of EXISTING test functions over
    newly-added data ... do NOT count toward the cap").
  - W-18 ghost-audit refresh: add coverage assertion that
    `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json`
    exists.

### G-NINES-1 — NineS self-eval at PV-06

* **(a) Deficiency**: The user wrote `"我希望你针对该方案进行深入调研和分析，并使用 NineS 进行分解，以确保收益的有效性"`
  (use NineS for decomposition to ensure ROI). Per W-2 / SI-2,
  end-of-iteration self-evaluation runs:
  ```
  nines -f json -c nines.toml self-eval --baseline-version <version>
    --golden-dir data/golden_test_set --samples-dir data/golden_test_set
    --src-dir src/devolaflow --test-dir tests --project-root .
  ```
  This must run at v11.1.0 cycle close to validate the cycle's
  iteration delta (per the v10.0.0..v11.0.0 cycle precedent —
  `.local/research/v10.0.0_nines.json` etc.). Without it, the cycle
  cannot prove the cascade restoration delivered measurable
  improvement (per W-3 / SI-3 readiness threshold composite ≥ 8.5
  for MINOR).
* **(b) Priority**: **P1** — high. NineS is the user-cited evaluator;
  cycle-close evaluation cannot be skipped.
* **(c) Proposed fix with file-level scope**:
  - NEW `.local/research/v11.1.0_nines.json` (raw NineS output;
    gitignored per `.local/` convention).
  - NEW `.local/research/v11.1.0_nines.md` (rendered analysis with
    composite verdict + per-dimension breakdown + comparison vs
    v11.0.1 baseline).
  - NEW `.local/research/v11.1.0_evaluation.md` (W-3 / SI-3 6-dim
    weighted composite; baseline format from
    `.local/research/v11.0.0_evaluation.md`).
  - PV-06 effort: ~60 min (analysis-only; no source edits per W-2).
  - W-17 impact: 0 NEW test functions (NineS run is a script
    invocation + markdown authoring; no test-suite changes).
  - W-18 ghost-audit refresh: add coverage assertion that
    `.local/research/v11.1.0_evaluation.md` exists at PV-06 close.
  - W-7 / SI-8 retrospective at PV-07 cycle close consumes the NineS
    JSON + evaluation MD as inputs.
  - External resource per S-7: NineS canonical URL is
    `https://github.com/YoRHa-Agents/NineS`.

### G-AUDIT-1 — Cascade-compliance audit ratchet

* **(a) Deficiency**: `scripts/audit_layer_usage.py::run` is
  observability-only (returns 0 unconditionally — see line 294
  docstring "always 0 — the audit is observability-only; no docs
  found is reported as an empty audit, not an error"). The user's
  feedback `"另外在 Plan 模式中...真正使其能够实现"` (truly enforce it)
  implies that observation alone is insufficient; the audit must
  ratchet to a CI-failing gate when cascade ratio drops below
  threshold.
* **(b) Priority**: **P2** — medium. The structural enforcement
  surfaces are SKILL.md (G-CASCADE-1), plan-mode checklist (G-PLAN-1),
  and cascade-compliance tests (G-TEST-1); the audit ratchet is a
  belt-and-suspenders observability catch for cycles where the
  prompt-side surfaces drift.
* **(c) Proposed fix with file-level scope**:
  - `scripts/audit_layer_usage.py` — add new CLI flag `--strict`
    (default OFF, R5-strict per W-20-style env-flag philosophy):
    when `--strict` AND `cascade_ratio < threshold` (default
    `threshold=0.80`, configurable via `--threshold`), `run()`
    returns 1 instead of 0. Add new computed field
    `cascade_ratio = (total_stage + total_wave) / total_dispatch`
    in `compute_layer_ratios()`.
  - `tests/test_audit_layer_usage.py` — amend:
    * Add 2-3 NEW test functions:
      - `test_compute_layer_ratios_includes_cascade_ratio` — pins
        the new field exists and is computed correctly.
      - `test_run_strict_mode_fails_below_threshold` — pins that
        `run(repo_root, strict=True, threshold=0.80)` returns 1 when
        cascade_ratio is below threshold.
      - `test_run_strict_mode_default_off_returns_zero` — R5 strict
        backward-compat: default `run()` invocation byte-identical
        to v11.0.x behaviour.
  - SI-3 / NineS pickup at PV-06: G-AUDIT-1 contributes to
    "Test adequacy" dimension (W-3 / SI-3 weight 0.20).
  - W-17 cap impact: +2-3 NEW test functions per PV-05 budget (well
    within the +30 cap).
  - W-18 ghost-audit refresh: add coverage for the `cascade_ratio`
    field name and `--strict` flag.

### G-PLAN-2 — `_PLAN_MODE_OVERRIDES` cascade-required hook

* **(a) Deficiency**: `src/devolaflow/task_adaptive_selector.py`
  `_PLAN_MODE_OVERRIDES` (lines 67-77 per the `references/plan-mode-enforcement.md`
  §2.2 line 96-99 reference) escalates plan-relevant sections
  (`agent_hierarchy`, `decomposition_gate`, `rationalization_prevention`)
  to `critical` and upgrades `model_hint` to `quality`. It does NOT
  inject a cascade-required runtime hook. G-PLAN-1 ships the
  prompt-side checklist enforcement; G-PLAN-2 is the optional
  runtime-side companion that lets a plan-mode call programmatically
  reject a plan with missing L1/L2 rows.
* **(b) Priority**: **P2** — medium. Optional runtime hook;
  prompt-side enforcement (G-PLAN-1) is sufficient for the user's
  "真正使其能够实现" directive at the prompt-side enforcement layer.
  G-PLAN-2 is a future hardening if PV-04 has spare budget.
* **(c) Proposed fix with file-level scope**:
  - `src/devolaflow/task_adaptive_selector.py` — extend
    `_PLAN_MODE_OVERRIDES` with new key `plan_mode_cascade_required:
    bool` (default True under v11.1.0; default False is the v11.0.x
    backward-compat path).
  - `tests/test_task_adaptive_selector_plan_mode.py` — add 2-3 NEW
    test functions for the new override.
  - `workflow-system/agent/references/plan-mode-enforcement.md` §2
    "Activation surface" — document the new override (1-paragraph
    addendum).
  - W-17 cap impact: +2-3 NEW test functions; PV-04 budget allows.
  - W-18 ghost-audit refresh: add coverage for
    `plan_mode_cascade_required` symbol.

### G-DOC-1 — Bilingual demo + version-timeline updates

* **(a) Deficiency**: Per ST-3 bilingual completeness + WX-2 version
  timeline + DS-1 demo "What's New", every operator-visible cycle
  must update:
  - `workflow-system/human/demo/version-timeline/versions.json`
    (NEW v11.1.0 entry per WX-2; required fields: version, date,
    era, headline, summary, highlights, metrics).
  - `workflow-system/human/demo/index.html` "What's New" section.
  - 8 EN guides at `workflow-system/human/en/*.md` + 8 ZH guides at
    `workflow-system/human/zh/*.md` (refreshed via `make
    sync-human-docs`).
  Without these updates, the cycle ships an operator-visible feature
  (cascade restoration) without operator-facing documentation.
* **(b) Priority**: **P3** — low (mechanical refresh; no design
  decisions). Folded into PV-07 cycle-close.
* **(c) Proposed fix with file-level scope**:
  - `workflow-system/human/demo/version-timeline/versions.json` —
    add v11.1.0 entry.
  - `workflow-system/human/demo/index.html` — refresh "What's New".
  - `workflow-system/human/en/*.md` + `workflow-system/human/zh/*.md`
    — `make sync-human-docs`.
  - `README.md` — version badge + "Current version" example bump
    11.0.1 → 11.1.0 (canonical 7 sync per CP-3 / SF-3).
  - W-17 cap impact: 0 NEW test functions (`tests/test_version.py`
    is a parametrize expansion over the canonical 7 — does not count
    per W-17).
  - W-18 ghost-audit refresh: existing `test_v11_*_new_symbols_have_coverage`
    pattern; add `test_v11_1_0_new_symbols_have_coverage` at PV-07
    close.

## §4. Architectural risks (W-21 Soul-set freeze)

The Soul rule layer is **FROZEN at 10 entries** (S-1..S-10) per the
v11.0.0 release. The v11.0.0 retrospective §3 deferral #1 explicitly
documents:
> "S-11 Soul rule candidate 'Parallel Wave Dispatch Invariant' —
> re-telegraphed per W-21 2-cycle cadence. v10.0.0 retrospective §3.5
> first telegraphed → v10.3.0 retrospective §5 re-telegraphed →
> v11.0.0 cycle plan §7 re-telegraphed → D-P-2 analysis
> (`.local/research/v11.0.0_w21_threshold_empirical_check.md`)
> classifies it as **Architecture A-7 candidate** (not Soul) per
> ADR-007 lines 183-188. Either class now requires a SI-1 gap-analysis
> entry at v11.2.0 (cycle N+2 from this telegraph) to continue the
> multi-cycle deliberation cadence. **Defer to: v11.2.0 SI-1.**"

Per W-21 §4 "Soul cap": post-addition Soul layer count MUST stay ≤ 12.
Per W-21 1-4: any S-(N+1) requires (1) 2-cycle telegraph in cycle N's
retrospective, (2) SI-1 gap-analysis entry in cycle N+2, (3) SI-3 §3.2
architecture-rationality score ≥ 9.5/10 from cycle N+2's L0, (4)
post-addition Soul layer count ≤ 12.

**v11.1.0 cycle MUST NOT propose any new Soul rule.** The cascade-
restoration cycle does need a new rule (the cascade-depth invariant),
but per W-21 §"Soul-vs-Architecture" decision rule (per
`.local/research/adr/v9-ADR-007-rule-rebalancing-and-rollup.md` D4 —
referenced in the v11.0.0 D-P-2 analysis cited above), constraints
that are conditional or implementation-coupled belong in **Architecture
(A-7+)**, not Soul.

### Recommended candidate — A-7 Cascade Depth Required for STANDARD+

**Recommended rule placement**: Architecture (A-7), NOT Soul.

**Soul-vs-Architecture decision-rule reasoning**:
1. **Conditional constraint**: cascade is REQUIRED for STANDARD+ but
   OPTIONAL for SIMPLE/TRIVIAL. A Soul rule encodes an immutable
   invariant that holds regardless of context (per `repo-governance.mdc`
   §S "These rules can NEVER be violated regardless of context, task
   type, or agent layer"). Cascade depth is context-conditional →
   Architecture, not Soul.
2. **Implementation-coupled**: the rule cites
   `change_activation.classify_complexity` (the verdict surface) and
   the `examples/multi-stage-trace.md` walkthrough as the worked
   counter-example. Soul rules avoid implementation coupling (per
   `repo-governance.mdc` S-1..S-10 wording — they describe what L0
   MUST do without naming a specific function). Architecture rules
   may name modules and verdict surfaces (cf. A-5.1 "tests/test_no_ghost_features.py::test_registry_single_owner",
   A-6.1 "devolaflow.skills.change_activation.classify_complexity").
3. **W-21 precedent**: the v11.0.0 D-P-2 analysis already classified
   the S-11 candidate "Parallel Wave Dispatch Invariant" as A-7
   (per `v11.0.0_w21_threshold_empirical_check.md` recommendation).
   The cascade-depth rule is structurally analogous (both describe
   dispatcher-layer behaviour; both are conditional + implementation-
   coupled).

**Suggested wording for PV-03 to draft** (verbatim candidate; cite this
gap analysis as source):
```
## A-7 — Cascade Depth Required for STANDARD+ Complexity

When `change_activation.classify_complexity()` returns STANDARD or
COMPLEX, the dispatch chain MUST traverse L0 → L1 → L2 → L3 in order;
direct L0 → L3 dispatch is prohibited. SIMPLE and TRIVIAL inputs MAY
collapse to single-L3 dispatch per the `[trivial waiver]` carve-out
in `references/plan-mode-enforcement.md` §4 Constraints Checklist
item #1.

### A-7.1 — Classification surface
Cascade requirement is the output of
`devolaflow.skills.change_activation.cascade_required(complexity)`
(NEW v11.1.0 PV-02). Complexity classification continues to be the
output of `classify_complexity(...)` per A-6.1.

### A-7.2 — Plan-mode enforcement
`workflow-system/agent/references/plan-mode-enforcement.md` §4
Constraints Checklist item #10 enforces the cascade-depth invariant
at plan-render time. Plans for STANDARD+ tasks that omit L1 Stage
or L2 Wave rows fail the checklist.

### A-7.3 — Runtime enforcement
`tests/test_cascade_enforcement.py` (NEW v11.1.0 PV-05) pins the
cascade verdict matrix; CI-side enforcement.

### A-7.4 — Operator override
`force_no_change=True` (per A-6.3 + D-A-4) preserves the operator
escape hatch for ad-hoc exploratory dispatch; this is the only
sanctioned cascade bypass for STANDARD+ tasks.
```

**Soul cap status post-v11.1.0**: 10 (unchanged). Cascade rule lands
at A-7 (Architecture); Architecture count goes 6 → 7 (well under any
implicit Architecture cap; no W-21-equivalent Architecture freeze
exists, but PV-07 retrospective should note the Architecture-tier
growth for future cycle review).

## §5. Cache-layout impact (A-2)

**Current schema state**:
- `schemas/lean-dispatch.yaml` `canonical_order` length = **17**
  (verbatim from `schemas/lean-dispatch.yaml:544-563`):
  - Frozen prefix (positions 1-12): `hdr` / `task` / `goal` /
    `assumptions` / `pred` / `files` / `rules` / `shared` / `accept` /
    `reinforce` / `verify_cfg` / `gate` (per A-2.1).
  - Append-only tail (positions 13-17): `repos` (v7.2.6 P-06) /
    `behavioral_guidelines` (v8.0.0 P-08) / `acceptance_criteria_v2`
    (v8.0.0 P-10) / `change_context` (v8.3.0 PV-05) /
    `predecessor_dedup_ledger` (v9.7.0 PV-02).
- A-2.1 frozen prefix: positions 1-12 MUST stay byte-stable; ANY
  reordering / renaming / removal is a release blocker.
- A-2.4 multi-baseline byte test
  (`tests/test_layout_invariant_multi_baseline.py`) currently pins
  10 historical baselines (32 / 32 PASS per v11.0.0 retrospective §5).

### A-2.3 nest-vs-append decision rule application

For every cascade-enforcement-related dispatch-payload field change
proposed in §3 fixes, apply the A-2.3 decision matrix:

**Proposed field 1 — `gate.cascade_required: bool`**
- Carries the cascade-required signal to the L3 receiver (so L3 can
  cross-check the dispatch came via the proper chain).
- Decision matrix walk:
  * "Does the behaviour modify how an existing block is interpreted?"
    → **YES** — `gate` block already carries `token_budget` (v8.0.0
    P-03 NEST precedent), `threshold`, `coverage`. Adding
    `cascade_required` modifies how the L3 receiver interprets the
    gate's STANDARD+ profile. → **NEST under `gate`**.
  * "Is the new field always present together with an existing
    block?" → YES (gate is always present; cascade_required is a
    sub-field of the gate's verdict block).
- **Verdict: NEST under `gate.cascade_required`.** Do NOT APPEND.

**Proposed field 2 — `gate.cascade_min_layers: int`**
- Optional sub-field carrying the minimum cascade depth (e.g., 4
  for STANDARD+ = L0→L1→L2→L3; 1 for TRIVIAL waiver).
- Decision matrix walk:
  * "Does the behaviour reuse an existing block's data shape?"
    → YES — `gate` already has int sub-fields (`token_budget.max_tokens`,
    `threshold` numeric).
  * "Is the new field always present together with an existing
    block?" → YES (with `gate.cascade_required`).
- **Verdict: NEST under `gate.cascade_min_layers`.** Do NOT APPEND.

**Why NOT APPEND**: A-2.3 decision-matrix bias is toward NEST
"whenever the data shape allows — every nest preserves cache-prefix
length while every append adds a position the runtime must serialise.
APPEND is reserved for orthogonal payload that does not nest
naturally." Cascade-required and cascade-min-layers are NOT
orthogonal to the `gate` block — they are EXTENSIONS of the gate's
verdict semantics (the gate already carries threshold + coverage +
token_budget; cascade_required is a fourth sibling). NEST is the
correct call.

**Cache-layout invariant proof** (by construction):
- `canonical_order` length stays at **17** (no APPEND).
- Frozen prefix (positions 1-12) stays byte-stable (no edit to
  positions 1-12).
- `tests/test_layout_invariant_multi_baseline.py` 10/10 historical
  baselines stay GREEN by construction (the new sub-fields are NEST
  under `gate` at position 12; gate's frozen-prefix slot does not
  change; absence of the new sub-fields is canonical and matches
  pre-v11.1.0 baseline rendering byte-identically).

**Schema version bump**: NEST extensions historically did NOT bump
schema version (cf. v8.0.0 P-03 `gate.token_budget` NEST; v9.1.4
PV-04 `change_context.{prior_feedback_themes, memory_case_hits,
source_of_truth_excerpt}` NEST per `schemas/lean-dispatch.yaml:299-309`
— "canonical_order length STAYS at 16 — no new top-level dispatch
key"). v11.1.0 NEST extensions follow the same precedent: schema
version stays at 6 (current per
`schemas/lean-dispatch.yaml:332` — "9 historical multi-baseline
byte-tests in `tests/test_layout_invariant_multi_baseline.py` (...)
ALL CONTINUE TO PASS unchanged because the new field's absence is
canonical").

## §6. Compatibility surface

Every operator-facing artifact PV-02..PV-07 will touch, grouped by
domain:

| Domain | File | Touched in PV | Reason |
|---|---|:---:|---|
| **Code** | `src/devolaflow/skills/change_activation.py` | PV-02 | G-CLASSIFY-1 classifier redesign (Candidates A/B/C); preserve env-flag contract per W-20 |
| **Code** | `src/devolaflow/task_adaptive_selector.py` | PV-04 | G-PLAN-2 `_PLAN_MODE_OVERRIDES` extension `plan_mode_cascade_required` |
| **Code** | `src/devolaflow/feedback.py` | PV-04 | If `gate.cascade_required` NEST extension lands, dispatch payload generation must populate the field; S-10 hook chain stays unchanged |
| **Code** | `src/devolaflow/gate/` (validator + scorer) | PV-04 | New `gate.cascade_required` validator (`assert_dispatch_layout` recognises the NEST sub-field); CP-4 mandates full gate test suite re-run |
| **Code** | `scripts/audit_layer_usage.py` | PV-05 | G-AUDIT-1 `--strict` flag + `cascade_ratio` field |
| **Tests** | `tests/test_change_activation_heuristic.py` | PV-02 | Refresh truth table for chosen Candidate |
| **Tests** | `tests/test_cascade_enforcement.py` (NEW) | PV-05 | G-TEST-1 cascade-compliance pins |
| **Tests** | `tests/test_task_adaptive_selector_plan_mode.py` | PV-04 | G-PLAN-1 + G-PLAN-2 plan-mode cascade pins |
| **Tests** | `tests/test_audit_layer_usage.py` | PV-05 | G-AUDIT-1 `--strict` + `cascade_ratio` pins |
| **Tests** | `tests/test_dispatch_emission_runs_hooks.py` | PV-04 | If gate.cascade_required nests under gate, S-10 byte-identity test must stay GREEN — no edit unless byte test fails |
| **Tests** | `tests/test_no_ghost_features.py` | PV-02..PV-07 | W-18 ghost-audit refresh BEFORE every CHANGELOG entry per PV |
| **Tests** | `tests/test_benchmarks.py` | PV-05 | G-BENCH-1 EvoBench scenarios (cascade-vs-collapse) — parametrize expansions over new YAML fixtures |
| **Tests** | `tests/test_layout_invariant_multi_baseline.py` | (no edit) | NEST extension preserves all 10 historical baselines GREEN by construction (A-2.4) |
| **Tests** | `tests/test_version.py` | PV-07 | Canonical 7 sync 11.0.1 → 11.1.0 |
| **Schemas** | `schemas/lean-dispatch.yaml` | PV-04 | NEST `gate.cascade_required` + `gate.cascade_min_layers` per A-2.3 (NEST not APPEND); canonical_order length stays 17; schema version stays 6 |
| **Docs** | `workflow-system/agent/SKILL.md` | PV-03 + PV-07 | G-CASCADE-1 cascade restoration (PV-03); canonical 7 version bump (PV-07) |
| **Docs** | `workflow-system/agent/references/plan-mode-enforcement.md` | PV-04 | G-PLAN-1 §4 Constraints Checklist new item |
| **Docs** | `workflow-system/agent/examples/multi-stage-trace.md` | PV-03 | G-CASCADE-2 §"When NOT to use" rewrite |
| **Docs** | `workflow-system/agent/references/agent-hierarchy.md` | PV-03 | Consistency check (file already canonical-cascade per §1; verify no contradictions with G-CASCADE-1 wording) |
| **Docs** | `workflow-system/agent/references/decomposition-gate.md` | PV-04 | If `gate.cascade_required` NEST extension lands, §5 "Gate Quality Mechanism" gets a 1-paragraph addition |
| **Docs** | `workflow-system/agent/references/agent-workspace.md` | PV-02 | If G-CLASSIFY-1 changes ActivationVerdict surface, §"When to Engage" must refresh |
| **Docs** | `workflow-system/agent/workflow-skill.yaml` | PV-07 | Canonical 7 sync per CP-3 |
| **Rules** | `.rules/architecture.mdc` | PV-04 | NEW §A-7 "Cascade Depth Required for STANDARD+" per §4 recommendation |
| **Rules** | `.cursor/rules/repo-governance.mdc` + `AGENTS.md` | PV-04 (auto) | Recompile via `make compile-rules` per CLAUDE.md (compiled outputs; do NOT hand-edit per `tests/test_no_ghost_features.py::test_rule_surfaces_compile_only`) |
| **Demo / version-timeline** | `workflow-system/human/demo/version-timeline/versions.json` | PV-07 | NEW v11.1.0 entry per WX-2 (real metrics from CHANGELOG only) |
| **Demo / version-timeline** | `workflow-system/human/demo/index.html` | PV-07 | "What's New" per DS-1 |
| **Demo / version-timeline** | `workflow-system/human/demo/benchmark-results/index.html` | PV-07 | `SAMPLE_DATA.version` 11.0.1 → 11.1.0 (canonical 7) |
| **Bilingual guides** | `workflow-system/human/en/*.md` (8 files) | PV-07 | `make sync-human-docs` per ST-3 |
| **Bilingual guides** | `workflow-system/human/zh/*.md` (8 files) | PV-07 | `make sync-human-docs` per ST-3 |
| **CHANGELOG** | `CHANGELOG.md` | PV-02..PV-07 | Per-PATCH entries: `## [11.0.2]` (PV-02 classifier), `## [11.0.3]` (PV-03 SKILL+example), `## [11.0.4]` (PV-04 plan-mode + schema NEST), `## [11.0.5]` (PV-05 tests + bench + audit ratchet), `## [11.0.6]` (PV-06 NineS), `## [11.1.0]` MINOR-close (PV-07 cycle-rollup) |
| **Canonical 7 (CP-3)** | `src/devolaflow/__init__.py`, `pyproject.toml`, `scripts/generate_human_docs.py`, `tests/test_smoke.py`, `README.md`, plus the SKILL.md / workflow-skill.yaml / benchmark-results entries above | PV-07 | `python scripts/bump_version.py 11.1.0` then `python -m pytest tests/test_version.py -v` |
| **Bench baselines (W-16)** | `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json` | PV-02 | W-16 wholesale baseline regen at cycle-start (the FIRST PV after MINOR-digit bump must regenerate ALL EvoBench baselines wholesale per `.local/research/v8.4.0_retrospective.md` §"R-7"). Recommended PV-01 telegraphs (this artifact); PV-02 executes since classifier change is the first behavior-affecting PV |
| **Bench baselines (W-16)** | `benchmarks/devolaflow_context/baselines/` (3 + new cascade scenarios) | PV-05 | G-BENCH-1 cascade-vs-collapse YAML fixtures + parametrize-driven baseline updates |
| **Cycle archive (W-19)** | `docs/cycle-archive/v11.1.0/` | PV-07 | Cycle-close archive: `python scripts/archive_research_artifacts.py 11.1.0` per W-19 |

## §7. Effort estimate

Per-PV wall-clock + tokens + NEW test functions, mindful of **W-17
per-PV cap +30 NEW test functions** and **cumulative ≤ +150 across
the cycle** (mid-cycle audit at PV-05 per W-17).

| PV | Headline | Wall-clock | Tokens (approx) | NEW test functions | W-17 status |
|:---:|---|:---:|:---:|:---:|:---:|
| **PV-01** | This artifact (research-only) | 60 min | ~25K | **0** | ✓ within cap |
| **PV-02** | G-CLASSIFY-1 classifier redesign + W-16 wholesale baseline regen | 60-90 min | ~80K | **+8-12** (refresh `test_change_activation_heuristic.py` for chosen Candidate; preserve 3 contract pins) | ✓ within cap |
| **PV-03** | G-CASCADE-1 SKILL.md cascade restoration + G-CASCADE-2 multi-stage-trace.md revision | 45-60 min | ~50K | **+4-6** (W-18 ghost-audit refresh stanzas + 1-2 SKILL.md content lints) | ✓ within cap |
| **PV-04** | G-PLAN-1 plan-mode structural enforcement + G-PLAN-2 (optional) `_PLAN_MODE_OVERRIDES` + A-7 rule + schema NEST + recompile rules | 60-90 min | ~70K | **+6-10** (Constraints Checklist render-time test, plan-mode override pins, schema NEST validator, S-10 byte-identity guard) | ✓ within cap |
| **PV-05** | G-TEST-1 cascade-compliance tests + G-AUDIT-1 audit ratchet + G-BENCH-1 cascade-vs-collapse perf scenarios + **W-17 mid-cycle audit** | 90-120 min | ~90K | **+12-18** (NEW `test_cascade_enforcement.py` ~10 tests + audit `--strict` 2-3 tests + parametrize over 4 NEW YAML fixtures NOT counted per W-17) | ✓ within cap; mid-cycle audit verifies cumulative ≤ +150 |
| **PV-06** | G-NINES-1 NineS self-eval + W-3 SI-3 evaluation | 60 min | ~30K | **0** (NineS run + markdown authoring; analysis-only) | ✓ within cap |
| **PV-07** | Cycle-close: canonical 7 sync + W-7 SI-8 retrospective + W-19 cycle archive + bilingual demo updates + CHANGELOG MINOR-close | 30-45 min | ~25K | **+2-4** (W-18 `test_v11_1_0_new_symbols_have_coverage` + 1-2 demo lints) | ✓ within cap |

**Cycle totals**:
- Wall-clock: ~6.5-9 hours across 7 PVs.
- Tokens: ~370K cumulative.
- NEW test functions (cumulative): **+32 to +50** — well under the
  **W-17 cumulative cap of +150** across the cycle. Substantial
  headroom for unforeseen reinforcement-round work.

**W-17 mid-cycle audit (PV-05)**: cycle-lead L0 reports cumulative
NEW test function delta against the cycle baseline (v11.0.1 →
v11.0.x..v11.1.0). Forecast at PV-05 should be ~+25-35 cumulative
(PV-02 + PV-03 + PV-04 + PV-05 partial). Forecast remaining-PV
budget: PV-06 (+0) + PV-07 (+2-4) = +2-4 more. Total cycle delta
forecast: +30-40. Well under +150 cap.

**W-19 cycle archive at MINOR close (PV-07)**: per W-19, the L0
cycle-lead MUST run:
```
python scripts/archive_research_artifacts.py 11.1.0
```
The archive copies `.local/research/v11.1.0_*` artifacts into
`docs/cycle-archive/v11.1.0/` (committed per W-19; future v11.2.0
SI-1 can reference v11.1.0 research without depending on `.local/`
which is gitignored on most clones). The MINOR-close PV-07 commit
is the right place per W-19 ("archive is created at cycle CLOSE
... committed as part of the cycle-rollup release commit").

**W-20 reuse-first env-flag policy compliance**: G-CLASSIFY-1 +
G-PLAN-1 + G-PLAN-2 + G-TEST-1 + G-CASCADE-1 + G-CASCADE-2 +
G-AUDIT-1 + G-BENCH-1 + G-NINES-1 + G-DOC-1 require **ZERO new env
flags**. Cascade enforcement either reuses existing surfaces (the
`force_no_change` parameter for the operator override; the existing
`DEVOLAFLOW_AGENT_WORKSPACE` for the workspace activation surface
which already governs cascade-relevant context per Rule A-6) or
introduces the cascade-required signal as a function parameter /
dispatch NEST sub-field (`gate.cascade_required`). Per W-20 §1
reuse-first test: the cascade behaviour activates the SAME runtime
surface as the existing classifier verdict matrix, so adding a new
env flag would FAIL the orthogonality test. Cycle ends with **8 env
flags** (unchanged from v11.0.x).

**W-21 Soul-set freeze compliance**: Cycle proposes ZERO new Soul
rules. The cascade-depth invariant lands as A-7 (Architecture).
Soul-set count stays at **10** (S-1..S-10 — unchanged).

**W-18 ghost-audit refresh sequencing per PV**:
- PV-02: refresh BEFORE adding `## [11.0.2]` CHANGELOG entry (cite
  the chosen Candidate's primary symbol).
- PV-03: refresh BEFORE adding `## [11.0.3]` (cite SKILL.md cascade
  restoration negative lint).
- PV-04: refresh BEFORE adding `## [11.0.4]` (cite Constraints
  Checklist new item + A-7 rule + schema NEST sub-fields).
- PV-05: refresh BEFORE adding `## [11.0.5]` (cite
  `test_cascade_enforcement.py` symbol + audit `--strict` symbol).
- PV-06: refresh BEFORE adding `## [11.0.6]` (cite NineS evaluation
  artifacts).
- PV-07: refresh BEFORE adding `## [11.1.0]` MINOR-close entry
  (cite the W-19 archive directory + cumulative cycle deliverables).

**Test-Then-Commit (W-9 SI-10) per PV**: every PV runs the 6-step
sequence (`pytest tests/ -q` + `ruff check` + `ruff format --check` +
`pytest tests/test_version.py -v` + `pytest tests/test_benchmarks.py
-v` + `make check-cursor-skill`). PV-04 + PV-05 add `pytest
tests/test_layout_invariant_multi_baseline.py -v` (A-2.4 multi-
baseline byte test) per the schema NEST extension; PV-04 + PV-05
also run `pytest tests/test_dispatch_emission_runs_hooks.py -v`
(S-10 byte-identity guard). PV-04 additionally runs `pytest
tests/test_gate.py -v` (CP-4 gate test suite) since it touches
`gate/`.

## §8. Cross-references

- `.local/feedbacks/feedback_for_v11.0.0.md` — verbatim user
  directive (source-of-truth for this cycle).
- `docs/cycle-archive/v11.0.0/v10.5.0_retrospective.md` §1 gap D-A-1
  — original audit + advisory rationale being SUPERSEDED.
- `docs/cycle-archive/v11.0.0/other/v10.5.1_layer_usage_audit.md` —
  empirical evidence (audit measured 0 dispatch lines; do not
  mis-read as 100% collapse).
- `workflow-system/agent/SKILL.md` lines 58-67 + 105-107 + 165-180
  — cascade-collapse signals to be revised in PV-03.
- `src/devolaflow/skills/change_activation.py` lines 75-369 —
  classifier + verdicts to be redesigned in PV-02.
- `workflow-system/agent/references/plan-mode-enforcement.md`
  §3 (lines 102-154) + §4 (lines 333-369) — Plan Output Template
  + Constraints Checklist to be extended in PV-04.
- `workflow-system/agent/references/agent-hierarchy.md` — canonical
  4-layer reference (consistent with A-1; no contradictions to
  resolve).
- `workflow-system/agent/references/decomposition-gate.md` lines
  230-330 — gate composite formula + profiles (PV-04 gate.cascade_required
  validator integration target).
- `workflow-system/agent/examples/multi-stage-trace.md` lines 200-211
  — the 4 collapse-OK rows being revised in PV-03.
- `.rules/architecture.mdc` lines 1-185 — full A-1..A-6 corpus;
  PV-04 adds new §A-7.
- `tests/test_change_activation_heuristic.py` — current 13-test
  classifier surface to be refreshed in PV-02.
- `tests/test_audit_layer_usage.py` — current 9-test audit surface
  to be extended in PV-05.
- `tests/test_dispatch_emission_runs_hooks.py` — S-10 invariant
  guard; PV-04 must keep byte-identical.
- `scripts/audit_layer_usage.py` — observability-only audit;
  PV-05 adds `--strict` flag + `cascade_ratio` field.
- `CHANGELOG.md` `## [11.0.1] - 2026-05-07` and `## [11.0.0] -
  2026-05-04` — current MAJOR + PATCH context; cycle plan author
  drafts per-PV CHANGELOG entries v11.0.2..v11.0.6 + v11.1.0
  MINOR-close.
- `.local/research/v11.0.0_retrospective.md` §3 deferrals — verified
  no overlapping work (S-11 candidate is re-classified as A-7 per
  D-P-2; cascade-restoration A-7 is a DISTINCT new rule motivated by
  user feedback `feedback_for_v11.0.0.md`).
- `schemas/lean-dispatch.yaml` lines 544-563 — canonical_order
  length 17 (frozen prefix 1-12 + append-only tail 13-17); PV-04
  schema NEST extension preserves length 17.
- DevolaFlow canonical URL (S-7): https://github.com/YoRHa-Agents/DevolaFlow
- NineS canonical URL (S-7): https://github.com/YoRHa-Agents/NineS

---

**Artifact verified per acceptance criteria:**
1. ✓ Path `.local/research/v11.1.0_gap_analysis.md` exists (this file).
2. ✓ §1 contains verbatim Chinese feedback (CO-2 — quoted, not translated).
3. ✓ §3 has 10 entries with (a) + (b) + (c) for each (≥7 required).
4. ✓ §4 documents Soul-vs-Architecture rationale; recommends A-7 placement; no Soul rule proposed (W-21 freeze preserved).
5. ✓ §5 confirms NEST-not-APPEND for `gate.cascade_required` + `gate.cascade_min_layers` (A-2.3 decision matrix walked).
6. ✓ §7 effort table has explicit per-PV NEW test counts (W-17 cap awareness; cumulative forecast +30-40 vs cap +150).
7. ✓ Zero source-code, test, schema, SKILL.md, or rule edits made (read-only artifact).
8. ✓ File ownership: only `.local/research/v11.1.0_gap_analysis.md` written.
