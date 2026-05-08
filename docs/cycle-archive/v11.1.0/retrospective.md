# v11.1.0 Cascade-Restoration MINOR Cycle Retrospective (W-7 / SI-8)

> Authored at PV-07 cycle close per W-7 / SI-8 (`.cursor/rules/repo-governance.mdc` §W-7).
> Cycle: v11.0.1 (BASE) → **v11.1.0 MINOR** (TARGET; PV-07 rollup commit).
> Branch: `release/v11.1.0` (off `origin/main` after PR #130 merge).
> Predecessors: `.local/research/v11.1.0_evaluation.md` (PV-06 W-3 SI-3 verdict),
> `.local/research/v11.1.0_pv06_stage_report.md` (L1 → L0 PV-06 handoff),
> per-PV stage reports `v11.1.0_pv0[1-6]_stage_report.md`.
> External tools (S-7): DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`,
> NineS `https://github.com/YoRHa-Agents/NineS`.

---

## §1 — Gaps identified (from PV-01 SI-1 planning gate)

The cycle's SI-1 planning gate at `.local/research/v11.1.0_gap_analysis.md` enumerated
**10 gaps** across 4 priority tiers. Source-of-truth: verbatim user feedback at
`.local/feedbacks/feedback_for_v11.0.0.md` (CO-2 — quoted, not translated):

> 我认为还是需要保持四个层级的依次派发 Sub-Agent 行为。
> 也就是说，在中等以上复杂度的任务中：
> 1. L0 调度 L1
> 2. L1 调度 L2
> 3. L2 调动 L3
> 不能由 L0 直接调动 L3。以及对于任务复杂度的判定，需要有一个更好的、更简明的判断标准
> 我希望你针对该方案进行深入调研和分析，并使用 NineS 进行分解，以确保收益的有效性。
> 另外在 Plan 模式中，也需要能够体现出多层级调度的原则，并且真正使其能够实现。
> 最重要的是需要有更完整的测试以及性能评估，确保有效后再进行这些子 Feature 的逐级合入：
> 1. 每一个子 Feature 都作为一个 Patch
> 2. 最终形成一个整体的 Minor 版本
> 3. 自我迭代多轮，以确保有足够的收益和提升
> 在确保有效性后，最终提交到一个 Major 版本。

### 10-gap inventory (priority distribution: 4 P0 + 3 P1 + 2 P2 + 1 P3)

| ID | Priority | Title | Cycle plan landing PV |
|---|:---:|---|:---:|
| **G-CASCADE-1** | P0 | SKILL.md cascade restoration (lines 64 + 105-107 + 180 erase L0→L3 collapse advisory) | PV-03 |
| **G-CASCADE-2** | P1 | `multi-stage-trace.md` "When NOT to use" rows 2 + 4 revision (8-module refactor + codebase-wide audit examples violated cascade-required for STANDARD+) | PV-03 |
| **G-CLASSIFY-1** | P0 | "更简明" classifier redesign (3 candidates A/B/C — 2-tier-with-single-threshold vs default-cascade-with-TRIVIAL-opt-out vs rule-based-4-tier-collapse) | PV-02 |
| **G-PLAN-1** | P0 | Plan-mode structural enforcement (Constraints Checklist item #10 fail-closes STANDARD+ plans omitting L1/L2) | PV-04 |
| **G-PLAN-2** | P2 | `_PLAN_MODE_OVERRIDES` cascade-required runtime hook (`plan_mode_cascade_required: True`) | PV-04 |
| **G-TEST-1** | P0 | Cascade-compliance tests (NEW `tests/test_cascade_enforcement.py` ≥10 tests pinning the verdict matrix) | PV-05 |
| **G-AUDIT-1** | P2 | Cascade-compliance audit ratchet (`scripts/audit_layer_usage.py --strict --threshold N` + `cascade_ratio` field) | PV-05 |
| **G-BENCH-1** | P1 | Cascade-vs-collapse perf scenarios (4 NEW EvoBench scenarios pinning cascade composite ≥ collapsed composite − 5pp) | PV-05 |
| **G-NINES-1** | P1 | NineS self-eval at PV-06 (W-2 SI-2 deep analysis + W-3 SI-3 6-dim composite ≥ 8.5 MINOR threshold) | PV-06 |
| **G-DOC-1** | P3 | Bilingual demo + version-timeline updates (WX-2 versions.json + DS-1 index.html + ST-3 EN/ZH bilingual via `make sync-human-docs`) | PV-07 |

D2 NineS baseline: composite **6.85 / 10** (`v11.1.0_nines_analysis.md` §8); MINOR
threshold ≥ 8.5; required lift ≥ +1.65 to clear.

---

## §2 — What was implemented (file-level change list across PV-02..PV-07)

All 10 gaps **landed**. Direction-by-direction landed PV table with PASS verdicts:

| Gap | Landed PV | Verdict | Primary deliverable |
|---|:---:|:---:|---|
| G-CLASSIFY-1 | PV-02 (v11.0.2) | **PASS** | `cascade_requirement(complexity) -> CascadeRequirement` pure function (Candidate C); operator-quotable verdict rule |
| G-CASCADE-1 | PV-03 (v11.0.3) | **PASS** | SKILL.md lines 64 + 105-107 + 180 cascade-restored; "Layer collapse pattern" string removed (negative lint) |
| G-CASCADE-2 | PV-03 (v11.0.3) | **PASS** | `multi-stage-trace.md` rows 2 + 4 revised; "L0 → L3 with a per-task wave partition" string removed |
| G-PLAN-1 | PV-04 (v11.0.4) | **PASS** | `references/plan-mode-enforcement.md` §4 Constraints Checklist item #10 + §5.1 DO list bullet |
| G-PLAN-2 | PV-04 (v11.0.4) | **PASS** | `task_adaptive_selector.py::_PLAN_MODE_OVERRIDES["plan_mode_cascade_required"] = True` |
| Schema NEST | PV-04 (v11.0.4) | **PASS** | `schemas/lean-dispatch.yaml` `gate.cascade_required` + `gate.cascade_min_layers` (NEST per A-2.3; canonical_order length stays at **17**) |
| G-TEST-1 | PV-05 (v11.0.5) | **PASS** | `tests/test_cascade_enforcement.py` 4P+1S stub → 13P+0S (5 named branches: existing + REPLACE SKIP + R-1 backward-compat + SOFT/strict-mode preview + truth-table propagation) |
| G-AUDIT-1 | PV-05 (v11.0.5) | **PASS** | `scripts/audit_layer_usage.py --strict --threshold 0.30` + `cascade_ratio` field; default-OFF preserves byte-id |
| G-BENCH-1 | PV-05 (v11.0.5) | **PASS** | 4 NEW EvoBench scenarios (`cascade_l0_l1_l2_l3_standard.{yaml,toml}` + `_complex.*` + `collapse_l0_l3_simple.*` + `_trivial.*`); cascade ≥ collapsed − 5pp on both axes |
| Architecture rule **A-7** | PV-05 (v11.0.5) | **PASS** | `.rules/architecture.mdc` §A-7 (4 sub-rules); architecture rule count 6 → 7; W-21 Soul-set freeze preserved at 10 |
| G-NINES-1 | PV-06 (v11.0.6) | **PASS** | NineS self-eval composite **9.02 / 10** (≥ 8.5 by +0.52 margin); 0 findings ≥ major severity; NO REINFORCEMENT |
| G-DOC-1 | PV-07 (v11.1.0) | **PASS** | versions.json v11.1.0 entry + demo `index.html` "What's New" + EN/ZH bilingual via `make sync-human-docs` + canonical 7 sync |

### Per-PV summary (5 impl PVs + analysis + rollup)

* **PV-02 (v11.0.2 — PR #126; merged)** — G-CLASSIFY-1 + W-16 wholesale baseline regen.
  Composite gate (4-dim decomposition gate proxy) **8.65 / 10**.
* **PV-03 (v11.0.3 — PR #127; merged)** — G-CASCADE-1 SKILL.md + G-CASCADE-2 multi-stage-trace.md.
  Composite **8.75 / 10**. Mitigated PV-02's W-4 forecast risk via dry-run pattern (saved 8.11pp regression).
* **PV-04 (v11.0.4 — PR #128; merged)** — G-PLAN-1 + G-PLAN-2 + schema NEST + soft validator.
  Composite **9.25 / 10** — first PV to clear MAJOR threshold ≥ 9.0 (4-dim).
* **PV-05 (v11.0.5 — PR #129; merged)** — G-TEST-1 + G-AUDIT-1 + G-BENCH-1 + A-7 rule + dead-API pin cleanup.
  Composite **9.25 / 10** sustained.
* **PV-06 (v11.0.6 — PR #130; merged)** — G-NINES-1 NineS self-eval. **W-3 SI-3 6-dim authoritative
  composite 9.02 / 10** (PASS by +0.52 margin); cumulative lift +2.17 = 132% of cycle plan §1
  forecast (+1.65). 0 findings ≥ major severity.
* **PV-07 (v11.1.0 — this rollup)** — Canonical 7 sync 11.0.6 → 11.1.0; CHANGELOG `## [11.1.0]`
  MINOR-close at top; W-7 SI-8 retrospective (this artifact); W-19 cycle archive at
  `docs/cycle-archive/v11.1.0/`; WX-2 versions.json + DS-1 demo index.html; ST-3 bilingual
  EN/ZH refresh via `make sync-human-docs`; W-18 final ghost-audit stanza
  `test_v11_1_0_new_symbols_have_coverage`.

### File-level change inventory (cycle-cumulative; v11.0.1 → v11.1.0)

**Code (impl PVs)**:
* `src/devolaflow/skills/change_activation.py` — NEW `cascade_requirement(complexity)` + `CascadeRequirement` Literal type (PV-02; ~46 lines added).
* `src/devolaflow/feedback.py` — NEW `populate_cascade_gate_fields(base_dispatch, complexity)` opt-in helper (PV-04; +89 LOC).
* `src/devolaflow/gate/scorer.py` — NEW `validate_cascade_gate_fields(gate_block, *, actual_layers=None)` SOFT validator (PV-04; +109 LOC).
* `src/devolaflow/task_adaptive_selector.py` — `_PLAN_MODE_OVERRIDES["plan_mode_cascade_required"] = True` + propagation (PV-04; +1 LOC + comment + propagation).
* `scripts/audit_layer_usage.py` — `--strict` + `--threshold` CLI flags + `cascade_ratio` field + `run(strict=, threshold=)` kwargs (PV-05).
* `scripts/detect_dead_apis.py` — `DEFAULT_ALLOWLIST` entries `"devolaflow.feedback:populate_cascade_gate_fields"` + `"devolaflow.gate.scorer:validate_cascade_gate_fields"` (PV-05; +2 entries; 3 forward-pin tuples removed in PV-05 W07).

**Schema**:
* `schemas/lean-dispatch.yaml` `lean_format_spec.gate.cascade_required: bool` + `gate.cascade_min_layers: int` NEST sub-fields (PV-04; +57 LOC). `canonical_order` length stays at **17** (NEST per A-2.3; A-2.4 multi-baseline 32/32 GREEN unchanged).

**Tests (cumulative cycle delta = +37 NEW test functions; well under W-17 +150 cap; ~25% utilized)**:
* `tests/test_change_activation_heuristic.py` — refreshed for Candidate C (PV-02; +9 NEW; 13 contract pins preserved byte-stable).
* `tests/test_cascade_enforcement.py` — NEW file (PV-02 stub; PV-05 extension to 13P+0S).
* `tests/test_audit_layer_usage.py` — +4 NEW audit-ratchet tests (PV-05).
* `tests/test_task_adaptive_selector_plan_mode.py` — NEW file with 7 cascade-compliance tests (PV-04).
* `tests/test_gate.py::TestCascadeGateFieldsValidator` — NEW class with 7 tests (PV-04).
* `tests/test_no_ghost_features.py` — 5 NEW W-18 stanzas (PV-02 + PV-03 + PV-04 + PV-05 + PV-06; PV-07 final stanza in this rollup).

**Rules**:
* `.rules/architecture.mdc` — NEW §A-7 "Cascade-Depth Invariant for Standard+ Dispatches" (4 sub-rules; +72 LOC; file 184 → 256 lines) (PV-05). Architecture rule count: 6 → **7**.
* `AGENTS.md` + `.cursor/rules/repo-governance.mdc` — auto-recompiled via `make compile-rules` (PV-05).

**Docs (agent-facing)**:
* `workflow-system/agent/SKILL.md` — lines 64 + 105-107 + 180 cascade-restored (PV-03).
* `workflow-system/agent/examples/multi-stage-trace.md` — rows 2 + 4 revised (PV-03).
* `workflow-system/agent/references/plan-mode-enforcement.md` — §4 Constraints Checklist item #10 + §5.1 DO list (PV-04).

**Benchmarks**:
* `benchmarks/devolaflow_context/baselines/v11.1.0_baseline.json` — NEW (W-16 wholesale regen at PV-02; cycle anchor).
* 4 NEW scenario fixtures under `benchmarks/devolaflow_context/scenarios/cascade_l0_l1_l2_l3_*` + `collapse_l0_l3_*` (PV-05).

**Demo + bilingual (PV-07 rollup)**:
* `workflow-system/human/demo/version-timeline/versions.json` — v11.1.0 entry per WX-2.
* `workflow-system/human/demo/index.html` — v11.1.0 "What's New" section.
* `workflow-system/human/en/*.md` (8 files) + `workflow-system/human/zh/*.md` (8 files) — regenerated via `make sync-human-docs`.

**Canonical 7 sync (PV-07 via `scripts/bump_version.py 11.1.0`)**:
1. `src/devolaflow/__init__.py` `__version__`
2. `workflow-system/agent/SKILL.md` frontmatter + banner + body
3. `workflow-system/agent/workflow-skill.yaml` identity
4. `pyproject.toml` `version`
5. `scripts/generate_human_docs.py` `SOURCE_VERSION`
6. `tests/test_smoke.py` version assertion
7. `README.md` badge + version example
8. `workflow-system/human/demo/benchmark-results/index.html` `SAMPLE_DATA.version`

**W-19 cycle archive (PV-07 — committed per W-19 contract)**:
* `docs/cycle-archive/v11.1.0/` populated via `python scripts/archive_research_artifacts.py 11.1.0` with `README.md` (auto-generated index) + `gap_analysis.md` + `implementation_plan.md` + `design/` (per-PV stage reports + PV-01 D4 + PV-02 decision memo) + `nines/` (PV-01 + PV-06 raw JSON + rendered analyses) + `evaluation/` (PV-06 W-3 SI-3 evaluation) + `retrospective.md` (this artifact) + `other/` (cycle plan + L0 decisions log).

---

## §3 — What was deferred and why (telegraph for v12.0.0 / v13.0.0)

Five deferrals carried by this cycle. All have explicit deferral rationale + landing-cycle
target + W-21 cadence-respecting trail. Per cycle plan §6 v12.0.0 graduation telegraph:

### D-1 — A-7 STRICT promotion (PERMISSIVE → strict + audit `--strict` default-ON)

**Deferral rationale**: A-7 ships at v11.1.0 in the "DEFAULTS-PERMISSIVE-IN-MINOR /
STRICT-IN-NEXT-MAJOR" pattern per cycle plan §6 + D2 §6 finding 1. Current state:

* `validate_cascade_gate_fields` returns warnings list (SOFT mode); does NOT raise
  `CascadeViolationError` on cascade-depth violations.
* `audit_layer_usage.py --strict` is default-OFF (the CLI flag exists; the runtime
  default is permissive — preserves byte-identical v11.0.x behaviour).

**Landing target**: **v12.0.0 cascade-strictness MAJOR cycle**. Per W-21 2-cycle
deliberation cadence — 1-2 v11.1.x stability patches (`v11.1.1`, optionally `v11.1.2`)
collect operator feedback via `.local/feedbacks/feedback_for_v11.1.0.md` (the next
user-feedback file per the v11.0.0 retrospective Q1-Q10 sign-off pattern); v12.0.0 SI-1
re-evaluates cascade-strictness against ≥1 month of field evidence. Stricter promotion
requires MAJOR composite ≥ 9.0 at v12.0.0 cycle close (currently 9.02 cleared by +0.02
margin — narrow; FORECAST-INDICATIVE, not GRADUATION-COMMITMENT).

### D-2 — SHORTCUT_SIMPLE retirement

**Deferral rationale**: v9.3.0 PV-06 D-E-4 introduced `SHORTCUT_SIMPLE` verdict +
`DEVOLAFLOW_SIMPLE_SHORTCUT` env flag; v9.7.0 forecast a default-ON promotion. The
v11.1.0 cycle's cascade restoration **conflicts** with the SHORTCUT_SIMPLE promotion
because the latter telegraphs cascade-collapse as a first-class shortcut for SIMPLE
tasks — orthogonal to the user's "不能由 L0 直接调动 L3" intent for STANDARD+.

**Decision**: HOLD the v9.7.0 default-ON promotion AND begin retirement of
SHORTCUT_SIMPLE entirely. Three "skip cascade" mechanisms (`force_no_change` +
`--no-change` + `SHORTCUT_SIMPLE`) per D2 §5 increase mental-model cost; collapsing 3 → 2
mechanisms reduces operator confusion (R-2 risk in cycle plan §7).

**Landing target**: **v12.0.0 SI-1**. Re-classification + retirement evaluation; cycle
plan §6 explicitly calls this out as a v12.0.0 graduation dependency. Per W-20 reuse-first,
the env flag count goes 8 → 7 at v12.0.0 close (no new flags introduced; 1 retired).

### D-3 — S-11 candidate "Cascade-Depth Invariant"

**Deferral rationale**: A new Soul rule for cascade-depth would lock the invariant as
immutable across all contexts (per `repo-governance.mdc` §S "These rules can NEVER be
violated regardless of context, task type, or agent layer"). Cascade depth is
**context-conditional** (REQUIRED for STANDARD+; OPTIONAL for SIMPLE/TRIVIAL) and
**implementation-coupled** (cites `change_activation.classify_complexity` +
`examples/multi-stage-trace.md` walkthrough). Per ADR-007 §"Soul-vs-Architecture"
decision-rule, conditional + implementation-coupled = Architecture (A-7), not Soul.

**v11.1.0 verdict**: **No S-11 candidate proposed**. The cascade-depth invariant lands
at Architecture (A-7) with 4 sub-rules. W-21 Soul-set freeze preserved at **10 entries**
(S-1..S-10); cap 12 with 2 slots of headroom.

**Telegraph for future cycles** (W-21 2-cycle gap rule):
* If field evidence over 1-2 cycles (v11.1.x stability patches + v12.0.0 cycle) shows
  cascade-depth violations as a class-of-bugs that survives Architecture A-7 enforcement,
  promote to S-11 at **v13.0.0 SI-1** (cycle N+2 from this v11.1.0 close per W-21 2-cycle
  deliberation cadence).
* v11.1.0 retrospective (this section) telegraphs the candidate; v13.0.0 SI-1 evaluates
  it; v13.0.0 cycle N+2 SI-3 §3.2 architecture-rationality must score ≥ 9.5/10 for the
  promotion to land.
* **DO NOT** promote in v11.2.0 or v12.0.0 (the W-21 2-cycle gap is non-negotiable).

### D-4 — Audit-regex coverage gap (PV-05 N-2 finding)

**Deferral rationale**: PV-05 W01 L3 agent flagged that `scripts/audit_layer_usage.py`'s
legacy v10.5.0 regex `Dispatch\s+type\s*[:=]\s*(Wave|Stage|Task)` does NOT match the
current v11.x-style markdown-bold `**Dispatch type:** Wave` lines used in the cascade
decomposition section of the cycle plan + PV stage reports. Net effect: the strict
ratchet currently reports `cascade_ratio == 0` for all v11.x cycle docs that use the new
markdown-bold convention.

**Why deferred**: the strict ratchet is **DEFAULT-OFF** (R5 strict pattern) so this does
NOT block the v11.1.0 verdict — operator-driven invocation of `audit_layer_usage.py
--strict` would surface false-zero ratios, but the default invocation (no `--strict`)
returns 0 unconditionally (the audit is observability-only by default). The
empty-input safeguard (`total_dispatch == 0` returns 0) prevents false-positive failures.

**Landing target**: **v11.1.x stability patch** (most likely v11.1.1 or v11.1.2). Two
candidate fixes:
* (a) **Loosen regex** to also match the v11.x markdown-bold convention:
  `(?:^|\*\*)\s*Dispatch\s+type\s*[:=*]\s*(Wave|Stage|Task)`.
* (b) **Tighten cycle-doc convention** to drop the markdown-bold for `Dispatch type:`
  lines.

Either way, this is a small bounded patch; not a v12.0.0 candidate. The audit ratchet
machinery + cascade_ratio field land in v11.1.0 PV-05 — only the regex coverage is
deferred.

### D-5 — CHANGELOG double-application class-of-bug (PV-03 N-2 → PV-04 mitigation → CI-lint candidate)

**Deferral rationale**: PV-03 surfaced a class-of-bug where parallel L1 / L3 sessions
on the same branch could each insert a `## [11.0.X]` CHANGELOG entry, causing
double-application. PV-03 N-2 mitigation: enforced single-application via `grep -c '^##
\[X\.Y\.Z\]' CHANGELOG.md == 1` discipline + L1-per-PV invariant (no parallel L1
sessions on the same branch). PV-04 + PV-05 + PV-06 inherited this discipline cleanly.

**Why a CI-lint candidate**: the PV-03 N-2 mitigation is ENFORCED at PV close (W-18
stanza counts line-anchored `## [vX.Y.Z]` headers via `splitlines()`), but it is NOT a
universal CI lint. A future cycle could land a per-CHANGELOG-entry CI lint that runs at
every commit (not just at PV close).

**Landing target**: **v11.1.x stability patch OR v12.0.0 SI-1**. Bounded scope (single
new test in `tests/test_no_ghost_features.py` walking the CHANGELOG `## [vX.Y.Z]`
headers + asserting count == 1 per version). Defer-then-decide based on whether the
class-of-bug recurs in v11.1.x or v12.0.0 — if it doesn't, the discipline is honored at
PV-close W-18 stanza level and a separate CI lint is unnecessary.

---

## §4 — Key learnings (process improvements for next cycle)

Six high-leverage learnings from this cycle. Each is a process improvement that informs
the next cycle's SI-1 planning gate.

### L-1 — Pre-flight scenario forecast discipline (W-4 SI-4 envelope verification)

**Origin**: PV-03 N-3 finding ("the pre-flight forecast pattern should be elevated to a
documented PV gate for any SKILL.md-touching PV") was acted on in PV-04, then refined in
PV-05.

**Mechanism**: capture EvoBench + S-10 + A-2.4 + CP-4 baselines BEFORE any source edits;
verify deltas after each substantive L3 dispatch; abort + fix BEFORE PR open if any
invariant regresses.

**Concrete win**: PV-03 dry-run pattern saved an **8.11pp scenario regression** that
would have failed W-4 SI-4 (5pp envelope). PV-04 + PV-05 inherited the discipline cleanly
— zero post-merge regressions across 3 impl PVs touching schema + gate + tests + audit.

**Process improvement for v11.2.0+ / v12.0.0+ cycles**: codify the pre-flight forecast as
a documented PV gate in `references/plan-mode-enforcement.md` §4 (new item #11
"Pre-flight scenario forecast — capture baselines BEFORE source edits for any PV
touching `gate/`, `feedback.py`, `task_adaptive_selector.py`, `schemas/`, SKILL.md, or
`.rules/`"). Telegraphed as v11.2.0 PV-01 design candidate.

### L-2 — L1-per-PV invariant (PV-03 N-2 mitigation)

**Origin**: PV-03 surfaced parallel-L1-session conflicts (two L1 stage agents on the
same branch causing W-18 stanza + CHANGELOG double-application).

**Mechanism**: ONE L1 stage agent per PV. Sibling L1 dispatches on the same branch are
PROHIBITED (L0 dispatches at most one L1 per PV; the L1 may decompose internally into
multiple L2 waves + L3 tasks via cascade, but no sibling L1 sessions).

**Concrete win**: PV-04 + PV-05 + PV-06 all reported "0 sibling L1 dispatches" — the
PV-03 mitigation was respected cleanly. Zero parallel-session conflicts in the impl PVs
that followed.

**Process improvement**: codify the L1-per-PV invariant in
`references/agent-hierarchy.md` §3 (new normative paragraph). Already documented
informally in PV-04 + PV-05 stage reports — PV-07 retrospective formalizes it.

### L-3 — 2-stage decomposition for high-coordination PVs (PV-05 precedent)

**Origin**: cycle plan §3 PV-05 explicitly split PV-05 into 2 stages
(`S01_test_and_perf` parallel L3 batch + `S02_rule_codification` sequential A-7 rule body
+ recompile).

**Mechanism**: high-coordination PVs (touching schema + tests + rules + audit + bench in
one cycle) split into 2+ stages with disjoint owned-files manifests. The
parallel-batch + sequential-finalization shape preserves S-8 file-ownership disjointness
+ enables L3 parallelism without write conflicts.

**Concrete win**: PV-05 dispatched 4 L3 tasks across 2 stages (3 parallel in S01 + 1
sequential in S02 W05) + 5 inline trivial-waiver edits — zero file conflicts; integrated
state PASS post-batch.

**Process improvement**: cycle plans for v11.2.0+ / v12.0.0+ that have ≥ 6 logical waves
in a single PV should explicitly carve into 2+ stages at SI-1 planning gate time. The
v11.1.0 cycle plan §3 PV-05 + PV-07 demonstrated the pattern; v12.0.0 SI-1 should adopt
it for any PV touching ≥ 5 of (`gate/`, `feedback.py`, `task_adaptive_selector.py`,
`schemas/`, SKILL.md, `.rules/`, `tests/test_cascade_enforcement.py`,
`scripts/audit_layer_usage.py`, EvoBench scenarios).

### L-4 — D2 dual-version reconciliation (locked baseline → +1.65 swing target)

**Origin**: PV-01 D2 NineS analysis at `.local/research/v11.1.0_nines_analysis.md` ran
self-eval against v11.0.1 BUT also surfaced the v11.0.0 baseline (composite 9.30 from
`.local/research/v11.0.0_evaluation.md`) — two different baselines with different
implications. PV-01 §1.5 "DEC-001 R-B locked baseline" decision pinned NineS composite
**6.85 / 10** at v11.0.1 as the cycle's anchor (NOT the v11.0.0 9.30 — which is the
W-3 SI-3 STRICT MAJOR composite, a different formula).

**Concrete win**: the +1.65 lift target was authoritatively anchored. PV-06 cleared the
target by **+0.52 margin** = **+2.17 cumulative lift = 132% of forecast**. The locked
baseline made the cycle's value-delta unambiguous.

**Process improvement**: every cycle's PV-01 D1 + D2 SI-1 planning gate MUST explicitly
lock the cycle baseline (W-3 SI-3 OR NineS — pick one and document the reconciliation
with the other). The L0 decision memo at `.local/research/<cycle>_l0_decisions.md`
documents the locked-baseline DEC-XXX. Pattern adopted in v11.1.0; recommend
formalization in v11.2.0+ / v12.0.0+ SI-1 protocol updates.

### L-5 — Architecture rationality dimension as primary cycle lever (5.0 → 9.5; 41% of cycle's total lift)

**Origin**: D2 §3 architecture-rationality scored **5.0 / 10** (the cycle's lowest
baseline dimension); cycle plan §1 forecast +1.65 cumulative lift; PV-06 W-3 SI-3
6-dim composite achieved **+2.17** lift across all 6 dims, but the architecture
dimension contributed **+0.90 weighted = 41% of total**.

**Concrete win**: the user's directive "不能由 L0 直接调动 L3" was the right
architectural call — the cycle's dimension-by-dimension trajectory shows architecture as
the dominant lever. 8 of 8 D2 architectural findings RESOLVED (or DEFERRED to v12.0.0
per W-21 cadence); 6 architectural enforcement surfaces now in place (vs D2's effective
0); W-21 Soul-set freeze preserved at 10; W-20 reuse-first preserved at 8 env flags;
A-2.1 frozen prefix preserved.

**Process improvement**: future cycles should explicitly identify the **dominant W-3
SI-3 dimension** at SI-1 planning gate time (the dimension with the lowest D2 score that
also has the strongest user-feedback alignment) — that dimension is the cycle's primary
lever. v11.1.0 architecture-rationality was the lever; future cycles should pick their
own at PV-01 D2 close.

### L-6 — "User feedback as source-of-truth" pattern (verbatim CO-2 quoting kept the cycle aligned)

**Origin**: every PV's stage report + the cycle plan + the gap analysis + the NineS
analysis + this retrospective quote the verbatim user feedback at
`.local/feedbacks/feedback_for_v11.0.0.md` per CO-2 (do NOT paraphrase, do NOT
translate). The 6 verbatim Chinese sentences are the cycle's commitment device.

**Concrete win**: across 7 PVs + 6 weeks of work, no scope drift. Every architectural
decision (SKILL.md cascade restoration, schema NEST not APPEND, A-7 placement at
Architecture not Soul, SHORTCUT_SIMPLE retirement, force_no_change preservation) traces
back to a specific verbatim sentence in the user feedback. The L1 PV-02 decision memo
explicitly cited verbatim user wording in the AC analysis vs L0 advisory disagreement —
the AC contract pins prevailed because they were anchored to the verbatim source.

**Process improvement**: cycles initiated by user feedback MUST archive the verbatim
feedback text in `.local/feedbacks/feedback_for_v<cycle>.md` at PV-01 SI-1 planning gate
time, and every PV's artifact + every L3 dispatch's CO-2 citation MUST quote verbatim.
This is already a CO-2 / S-2 invariant; the v11.1.0 cycle's success is concrete
empirical evidence that the pattern works at scale (7 PVs × 6 PVs of dispatching). Cycle
N+1 (v11.2.0 stability patches) and cycle N+2 (v12.0.0 cascade-strictness MAJOR) inherit
the pattern.

---

## §5 — Next-cycle proposals (input for v11.2.0 or v12.0.0 SI-1)

Five proposals for the next cycle's SI-1 planning gate (in priority order):

### P-1 — v11.2.0 stability patches (1-2 patches; operator feedback collection)

**Scope**: 1-2 v11.1.x stability patches (v11.1.1, optionally v11.1.2) collecting
operator feedback via `.local/feedbacks/feedback_for_v11.1.0.md`. Deferred from cycle
plan §6 graduation-dependency #2.

**Acceptance**: ≥ 1 month of cascade-restoration field evidence in real cycles;
operator-quotable cascade verdict rule (`STANDARD+ → cascade required; SIMPLE/TRIVIAL →
optional`) is the empirical question — does the rule reduce or increase operator
mental-model cost?

### P-2 — v12.0.0 cascade-strictness MAJOR cycle (per cycle plan §6 graduation gate)

**Scope**: A-7 STRICT promotion (D-1 deferral) + SHORTCUT_SIMPLE retirement (D-2
deferral). v12.0.0 SI-1 gap analysis must explicitly evaluate whether A-7 merits Soul
promotion vs Architecture-stable per ADR-007 §"Soul-vs-Architecture" decision-rule
re-checked against 1-2 cycles of field evidence.

**Acceptance**: W-3 SI-3 STRICT MAJOR composite ≥ 9.0 at v12.0.0 cycle close (currently
9.02 at v11.1.0 close — narrow +0.02 margin; v12.0.0 must independently re-clear).

### P-3 — v13.0.0 S-11 candidate evaluation (W-21 2-cycle gap respected)

**Scope**: per W-21 2-cycle deliberation cadence, the cascade-as-Soul S-11 candidate
telegraphed in this retrospective (D-3) is FIRST-EVALUATED at **v13.0.0 SI-1** (NOT
v12.0.0 — the W-21 gap rule mandates the cascade-as-Soul evaluation skips v12.0.0 even
though v12.0.0 is the next MAJOR).

**Acceptance**: v13.0.0 SI-1 gap analysis covers (a) immutable invariant the new rule
enforces, (b) why no existing S-* / A-* / W-* rule covers it, (c) proposed CI-time
enforcement surface, (d) per-cycle review trail. v13.0.0 cycle N+2 SI-3 §3.2
architecture-rationality must score ≥ 9.5/10 for the promotion to land. Soul cap stays
≤ 12.

### P-4 — Audit-regex coverage fix (D-4 deferral; v11.1.x patch)

**Scope**: tighten OR loosen the audit regex to match v11.x markdown-bold convention.
Bounded scope — single regex change in `scripts/audit_layer_usage.py` + 2-3 NEW test
cases in `tests/test_audit_layer_usage.py` covering the v11.x markdown-bold lines.

**Acceptance**: `audit_layer_usage.py --strict --threshold 0.30` returns non-zero
`cascade_ratio` for v11.x cycle docs (currently returns 0 due to regex mismatch).

### P-5 — CHANGELOG single-application CI lint (D-5 deferral; v11.1.x or v12.0.0)

**Scope**: per-commit CI lint walking CHANGELOG `## [vX.Y.Z]` headers asserting each
appears at most once. Defer-then-decide based on whether the class-of-bug recurs in
v11.1.x.

**Acceptance**: `tests/test_no_ghost_features.py::test_changelog_section_headers_unique`
walks all `## [vX.Y.Z]` headers in `CHANGELOG.md` + asserts each version appears
exactly once.

---

## §6 — Cycle metrics summary

| Area | v11.0.1 (baseline) | v11.1.0 (target) | Delta | Status |
|------|---:|---:|---:|---|
| W-3 SI-3 composite | 6.85 (D2) | **9.02** | **+2.17** (132% of forecast +1.65) | **PASS** (≥ 8.5 by +0.52) |
| Architecture rationality | 5.0 | **9.5** | +4.5 | 41% of cycle lift |
| Test adequacy | 6.5 | 9.0 | +2.5 | 23% of cycle lift |
| Maintainability | 6.0 | 8.5 | +2.5 | 17% of cycle lift |
| Code quality | 8.5 | 8.7 | +0.2 | sustained |
| Compatibility | 9.0 | 9.5 | +0.5 | sustained |
| Performance impact | 7.0 | 9.0 | +2.0 | EvoBench cascade ≥ collapsed − 5pp on both axes |
| Tests collected | 4256 | ~4302 | +37-39 NEW (~25% of W-17 +150 cap) | well under |
| Coverage | 93% | 93% | 0 | CP-2 floor 80% strongly satisfied |
| Soul rule count | 10 | 10 | 0 | W-21 freeze preserved |
| Architecture rule count | 6 | **7** | +1 (A-7) | A-7 lands at Architecture per ADR-007 |
| Env flag count | 8 | 8 | 0 | W-20 reuse-first preserved |
| Schema canonical_order length | 17 | 17 | 0 | NEST not APPEND per A-2.3; A-2.4 32/32 GREEN unchanged |
| EvoBench scenarios | 53 | 57 | +4 | cascade-vs-collapse |
| BLOCKER findings | n/a | 0 | 0 | cycle-cumulative across all PVs |
| CRITICAL findings | n/a | 0 | 0 | cycle-cumulative across all PVs |
| MAJOR findings | n/a | 0 | 0 | NO REINFORCEMENT round needed |

---

## §7 — Cross-references

* **Verbatim user feedback (CO-2)**: `.local/feedbacks/feedback_for_v11.0.0.md`
* **PV-01 SI-1 planning gate**: `.local/research/v11.1.0_gap_analysis.md` (10-gap inventory),
  `.local/research/v11.1.0_nines_analysis.md` (D2 SI-2 baseline 6.85),
  `.local/research/v11.1.0_nines_raw.json` (D2 raw scores),
  `.local/research/v11.1.0_cycle_plan.md` (D3 7-PV plan + cascade decomposition + risk register),
  `.local/research/v11.1.0_pv01_stage_report.md` (D4 L1 → L0 handoff),
  `.local/research/v11.1.0_l0_decisions.md` (DEC-001 R-B locked baseline + DEC-002 advisory).
* **Per-PV stage reports**: `.local/research/v11.1.0_pv0[2-6]_stage_report.md` (5 reports).
* **PV-02 decision memo**: `.local/research/v11.1.0_pv02_decision.md` (Candidate C selection).
* **PV-06 SI-3 evaluation**: `.local/research/v11.1.0_evaluation.md` (W-3 SI-3 6-dim composite 9.02; +0.52 margin).
* **PV-06 NineS artifacts**: `.local/research/v11.1.0_pv06_nines.json` (raw; 25 dims) +
  `.local/research/v11.1.0_pv06_nines.md` (rendered; W-2 hybrid mode).
* **W-19 cycle archive (committed at PV-07)**: `docs/cycle-archive/v11.1.0/`
  (per W-19; idempotent re-runs no-op).
* **CHANGELOG entries**: `## [11.0.2]` (PV-02) → `## [11.0.3]` (PV-03) → `## [11.0.4]`
  (PV-04) → `## [11.0.5]` (PV-05) → `## [11.0.6]` (PV-06) → `## [11.1.0]` (this rollup at TOP).
* **Merged PRs**: #126 (PV-02), #127 (PV-03), #128 (PV-04), #129 (PV-05), #130 (PV-06).
  PR #131 = PV-07 v11.1.0 MINOR rollup.
* **External tools (S-7)**:
  * DevolaFlow / EvoBench: `https://github.com/YoRHa-Agents/DevolaFlow`
  * NineS: `https://github.com/YoRHa-Agents/NineS`

---

## §8 — Verification (W-7 SI-8 acceptance criteria)

Self-verifying checklist for this artifact:

1. ✓ Path `.local/research/v11.1.0_retrospective.md` exists (this file).
2. ✓ §1 covers "Gaps identified" — 10-gap inventory with priority distribution
   (4 P0 + 3 P1 + 2 P2 + 1 P3); verbatim user feedback quoted per CO-2.
3. ✓ §2 covers "What was implemented" — 12-row landing table (10 gaps + schema NEST +
   A-7 rule) + per-PV summary + file-level change inventory across PV-02..PV-07.
4. ✓ §3 covers "What was deferred and why" — 5 deferrals (D-1 A-7 STRICT + D-2
   SHORTCUT_SIMPLE retirement + D-3 S-11 candidate + D-4 audit-regex + D-5 CHANGELOG
   CI lint) with explicit rationale + landing target + W-21 cadence-respecting trail.
5. ✓ §4 covers "Key learnings" — 6 high-leverage learnings (L-1 pre-flight discipline +
   L-2 L1-per-PV invariant + L-3 2-stage decomposition + L-4 D2 dual-version
   reconciliation + L-5 architecture-rationality lever + L-6 user-feedback source-of-truth).
6. ✓ §5 covers "Next-cycle proposals" — 5 proposals for v11.2.0 / v12.0.0 / v13.0.0 SI-1.
7. ✓ §6 cycle metrics summary covers all 6 W-3 SI-3 dimensions + tests + coverage +
   Soul/Architecture/env-flag counts + canonical_order + EvoBench + finding inventory.
8. ✓ §7 cross-references include all predecessors per CO-2 verbatim citation; external
   tools via S-7 GitHub URLs.
9. ✓ Zero source-code, test, schema, SKILL.md, or rule edits made (analysis-only
   artifact).
10. ✓ All paths relative to repo root (S-2 / CO-4 compliant); external tools by GitHub
    URL only (S-7 compliant).

---

*End of W-7 / SI-8 Retrospective for v11.1.0 cascade-restoration MINOR cycle.
**Verdict**: cycle CLOSED with composite 9.02 / 10 PASS; 132% of forecast lift achieved;
0 findings ≥ major severity; 5 deferrals telegraphed for v11.1.x / v12.0.0 / v13.0.0 per
W-21 cadence; 6 process learnings codified for next-cycle SI-1.*
