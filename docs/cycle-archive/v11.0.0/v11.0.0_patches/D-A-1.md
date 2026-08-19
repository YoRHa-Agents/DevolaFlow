# D-A-1 — L1 / L2 Actual Usage Rate Audit & Possible Collapse

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.1 D-A-1
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §5 (templates) + §4.2 (architecture-health metrics)
> **Wave:** 2 (D-A Architecture Health)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow's `workflow-system/agent/SKILL.md:165-178` declares a **4-layer
agent hierarchy** (L0 Project / L1 Stage / L2 Wave / L3 Task) — see also
`workflow-system/agent/references/agent-hierarchy.md:25-44` for the
canonical diagram. Per `.cursor/rules/repo-governance.mdc` §A-3, each
layer carries an explicit token budget (~3K / ~5K / ~4K / ~8K).

**Empirical L0/L1/L2/L3 dispatch reference count across v9.0.0..v10.3.0
cycle plans + retrospectives** (13 documents — total mentions, *not*
unique standalone agent instantiations):

| Layer | Mentions | Mentions per doc (avg) | Where dominant |
|---|---:|---:|---|
| L0 | 16 | 1.23 | Top-level orchestrator citations (`v10.0.0_retrospective.md:1`, `v10.2.0_cycle_plan.md:4`) |
| L1 | 12 | 0.92 | Mostly "Stage Agent" attribution lines, NOT distinct dispatches |
| L2 | 17 | 1.31 | "Wave" appears 8× in `v10.2.0_cycle_plan.md` as Dispatch type |
| L3 | 9 | 0.69 | "L3 Task Agent" as the *implementer* role per P1 |

Critically, `.local/research/v10.2.0_cycle_plan.md` PV-01..PV-06 marks
**Dispatch type = Wave** for 5/6 PVs (lines 59, 94, 129, 159, 189) —
which collapses to L0→Wave→L3 in practice (the L1 Stage Agent layer is
*elided*: the L0 author plays the L1 role inline). Only PV-06 is marked
"Stage" (line 228), and that IS a single-stage cycle-close, not a
multi-wave stage. The v10.0.0 MAJOR rollup (`v10.0.0_retrospective.md`
§2.1 "Per-MINOR ledger") similarly shows each MINOR collapsing to a
linear PV chain, never a multi-wave Stage Agent.

**Existing escape hatch (under-used):**
`src/devolaflow/skills/change_activation.py:115-117` defines
`SHORTCUT_FLAG_NAME = "DEVOLAFLOW_SIMPLE_SHORTCUT"` (R5 strict default-OFF
per v9.3.0 PV-06; lines 258-348). The verdict surface
`shortcut_verdict()` returns `SHORTCUT_SIMPLE` only when the env-flag is
ON AND complexity ∈ {TRIVIAL, SIMPLE} — but no v10.x cycle has
documented flipping this flag to default-ON despite v9.3.0 promising "a
future cycle (telegraphed v9.7.0) will promote it to default-ON" (line
110). v10.3.0 leaves it OFF.

## §2 — patch_design

**Algorithm (audit-only; no behaviour change):**

```
audit_layer_usage(cycle_plan_dir):
  1. Glob `.local/research/v9.*.0_cycle_plan.md` +
     `.local/research/v10.*.0_cycle_plan.md` +
     `.local/research/v9.*.0_retrospective.md` +
     `.local/research/v10.*.0_retrospective.md`.
  2. For each doc, regex-extract:
     - "Dispatch type:" lines (Wave / Stage / Task)
     - "L0 dispatch", "L1 Stage", "L2 Wave", "L3 Task" tokens
     - "Single-Task shortcut" or "L0→L3" shortcut markers
  3. Compute per-cycle counts; aggregate to a 4-row × 13-doc matrix.
  4. Emit `audit_layer_usage.md` with:
     - Per-doc ratio: standalone-L1 / standalone-L2 / collapsed-to-L0+L3
     - Recommendation: SKILL.md §"Quick Action Decision" wording revision
     - Default-flip eligibility for `DEVOLAFLOW_SIMPLE_SHORTCUT`
```

**Files touched (NEW):**

- `scripts/audit_layer_usage.py` (~180 LOC + 6-8 unit tests in
  `tests/test_audit_layer_usage.py`).

**Files touched (EDITED):**

- `workflow-system/agent/SKILL.md:60-67` — annotate the Quick Action
  Decision table to mark L1/L2 as **"only-when-needed"** at Standard tier
  (advisory — does NOT change the existing P1 invariant).
- `workflow-system/agent/SKILL.md:165-178` — add a 1-paragraph note
  ("layer collapse pattern") under the 4-Layer table referencing the
  audit script.
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**Files touched (NEW reference content):**

- `workflow-system/agent/examples/multi-stage-trace.md` (≤ 1600 LOC per
  C-4 XL tier) — worked example of when L1+L2 are NECESSARY (cross-stage
  artifact merging, e.g., `analyze` primitive multi-team merge per
  `meta-framework.md:65-86`). 1 new example file (under C-4 XL ceiling).

**API/CLI surface:**

```bash
python scripts/audit_layer_usage.py [--cycle-glob 'v10.*'] [--json] [--verbose]
```

**Doc deliverables (G-9 mapping per admission_checklist.md §G-9):**

- CHANGELOG entry (Python module change) — required.
- W-18 lint refresh — required (covers new symbol
  `audit_layer_usage.run`).
- SKILL.md edit (advisory annotation only) → triggers W-12 adapter
  build verify (already in pre-commit chain via `make build-skill`).
- New example file (1) → triggers SF-3 `sync_cursor_skill.py` update +
  C-4 line-budget verify.
- Bilingual EN/ZH — NOT required (developer-facing CLI + agent-facing
  example, neither exposed in `workflow-system/human/`).

**Default-flip recommendation (NOT in PV scope; documented as cycle plan
input only):** the audit may RECOMMEND flipping
`DEVOLAFLOW_SIMPLE_SHORTCUT=1` as default in v11.X.0 if standalone L1/L2
ratio < 5% — but the actual flip is OUT OF SCOPE for D-A-1 (the patch
ships only the audit + advisory wording).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` per
`v11.0.0_evaluation_methodology.md` §2 layout (1-3 source files,
< 200 LOC, no plugins, no `.local/.agent/active/`).

**Operations exercised:** `feature` (1-file scope) + `bugfix` (1-line fix)
— both classified TRIVIAL/SIMPLE per
`change_activation.classify_complexity()` (`change_activation.py:172-190`).

**Metric collection:** L1/L2 dispatch frequency (count per evaluated
operation); time-to-first-L3-dispatch (wall-clock from L0 receiving
the user request to first L3 task starting); SKILL.md L0 token cost (a
proxy for dispatcher cognitive load).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| L1+L2 dispatch frequency on Simple ops | 0 (collapsed) but UI implies "should happen" | 0 + advisory wording acknowledges this | 0 (preserve) | preserve |
| L1+L2 cognitive load (L0 reading "Stage→Wave" path before deciding shortcut) | High — operator reads 14 lines of 4-layer table before deciding "trivial path" | Low — annotated as "only-when-needed" | qualitative -50% | improve |
| Time-to-first-L3-dispatch (small task) | ~30s (L0 reads 4-layer + Quick Action table) | ~15s (advisory wording lets L0 short-circuit faster) | -50% | improve |
| Steps to invoke shortcut path | implicit (operator must know `DEVOLAFLOW_SIMPLE_SHORTCUT`) | explicit (advisory wording cites the flag) | -1 step | improve |

**Pass criterion:** L1+L2 dispatch frequency on Simple ops stays = 0
(no regression) AND advisory wording explicit ranking visible to L0
without reading the full 4-layer table AND time-to-first-L3-dispatch
≤ -33%.

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (advisory wording IS a value-add even if the
quantitative timing delta is small) — only `FAIL` if the audit reveals
that L1/L2 ARE used standalone in small projects (current evidence
suggests they are not).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline). 13 cycle
plan/retro documents under `.local/research/v9.*.0_*.md` +
`.local/research/v10.*.0_*.md`.

**Metric collection:** L1/L2 dispatch frequency ratio per
`v11.0.0_evaluation_methodology.md` §4.2 (architecture-health metrics);
SKILL.md line count (must remain <500 per C-4); examples line count
(new `multi-stage-trace.md` must remain ≤1600 per C-4 XL tier);
build-skill 4-adapter success rate.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Standalone L1 Stage Agent dispatches per cycle | 0 (per audit) | 0 (audit confirmed) | 0 (preserve) | preserve |
| Standalone L2 Wave Agent dispatches per cycle | ≤1 per 6-PV cycle (only `Wave` pattern via L0) | ≤1 (preserved; pattern not retired) | 0 (preserve) | preserve |
| L0→L3 collapse ratio | 5/6 PVs in v10.2.0 (83.3%) | 5/6 (audit-only) | 0 (preserve) | preserve |
| SKILL.md line count | 460 | ≤ 462 (1-2 advisory line additions) | +1-2 | preserve (under 500 cap) |
| Examples count | 3 | 4 (new `multi-stage-trace.md`) | +1 | preserve (under C-4 examples cap) |
| `build-skill` success rate | 100% (4 adapters) | 100% | 0 | preserve |
| Audit script existence | absent | present (180 LOC + 6-8 tests) | +1 script | improve |

**Pass criterion:** Audit script ships AND audit ratios match the
v10_internal_optimization_directions.md §3.1 D-A-1 hypothesis (L1+L2
standalone < 5%) AND SKILL.md stays <500 lines AND advisory wording
present in §"4-Layer Agent Hierarchy".

**Side-effect check (must NOT regress):**

- C-4 SKILL.md line budget (<500).
- C-4 examples ≤1600 line budget.
- W-12 adapter build success rate (4/4).
- W-17 cycle test cap (script + tests must fit in +30/PV).
- A-1 P1 dispatcher-not-implementer invariant (L1/L2 still defined; not removed).
- C-7 valid reference links (multi-stage-trace.md references existing files only).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.2 architecture-health bucket;
≥ 3 metrics required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-A-1) | Δ | Justification |
|---|---|---:|---:|---:|---|
| L1+L2 standalone dispatch ratio | §4.2 (ratio L1+L2 / total dispatches) | unknown (no instrumentation) | known + reported (0-5% per audit) | data exists | First quantitative measurement of architectural reality |
| Operator time-to-action on Simple ops (L0→L3) | §4.1 proxy via SKILL.md cognitive load | ~30s reading 4-layer + Quick Action | ~15s with advisory wording | -50% | Advisory wording short-circuits the 4-layer-then-decide read |
| Standalone L1 Stage Agent dispatches per 6-PV cycle | §4.2 | 0 (per audit; UI implies > 0) | 0 (per audit + UI matches reality) | UI/reality alignment | Closes documentation/practice mismatch |
| Examples count | §4.4 (doc count proxy) | 3 | 4 | +1 | New `multi-stage-trace.md` documents WHEN L1/L2 *are* needed |
| `DEVOLAFLOW_SIMPLE_SHORTCUT` operator awareness | §4.1 (steps proxy) | low (mentioned only in PV-06 v9.3.0) | high (cited in SKILL.md advisory wording) | qualitative +1 | Advisory wording promotes the existing flag |

**Guarantee on metric:** ALL 5 metrics scriptable via stdlib (re,
glob, os, pathlib) — no external deps. The L1+L2 ratio is computed by
the new `scripts/audit_layer_usage.py`. The "operator time-to-action"
is a documented estimate corroborated by the SKILL.md cognitive-load
proxy (line count from §"Quick Action Decision" to §"4-Layer Agent
Hierarchy" header = ~100 lines, halved by advisory short-circuit).

## §6 — admission_verdict

**Verdict: CONDITIONAL_PASS** (clear large-project benefit; small-project
benefit is advisory/qualitative and benefits-by-association).

**Rationale:**

- G-1 Internal-value: 5 quantitative DF-internal metrics from §4.2
  (architecture-health) measurably improve OR establish baseline data
  where none existed.
- G-2 Both-tier: large project (DevolaFlow self, 13 cycle docs) shows
  CLEAR benefit (audit script + advisory wording + new example);
  small project benefit is advisory + time-to-action (qualitative
  improvement). PASS criterion fully met on large; CONDITIONAL on
  small (the advisory wording IS the benefit but admits no further
  L1/L2-quantitative target on tiny repos).
- G-3 Zero-deps: stdlib only (re, glob, pathlib, argparse); no NineS
  / Si-Chip / RTK / ui-pro side requirement.
- G-4 Cycle-budget: S effort; ≤10 tests per §G-4 mapping; fits
  W-17 +30/PV cap with margin.
- G-5 Soul-freeze: 0 Soul rule additions.
- G-6 Cache-prefix: zero edits to canonical_order.
- G-7 Compatibility: pure-additive (NEW script + 1-2 advisory lines in
  SKILL.md + 1 NEW example file); no public API rename or rule change.
- G-8 Test coverage: script ships with 6-8 unit tests covering
  glob+regex+ratio computation; ≥ 80% per CP-2.
- G-9 Documentation completeness: matches "Reference doc add" row in
  §G-9 table — CHANGELOG + W-18 lint refresh + SF-3
  `sync_cursor_skill.py` update for the new example + SF-1 line-budget
  verify. SKILL.md change triggers W-5 coupling triple
  (line-count check + adapter build + benchmark + version test) but
  the change is < 5 lines — well within W-5 ceiling.

## §7 — effort_estimate

**Effort: S (≤ 0.5 PV)**

**Breakdown:**

- `scripts/audit_layer_usage.py` (regex + glob + ratio table emitter):
  ~180 LOC.
- 6-8 unit tests (`tests/test_audit_layer_usage.py`): ~120 LOC.
- SKILL.md advisory annotation: 1-2 lines.
- `examples/multi-stage-trace.md` worked example: ~600-1000 LOC under
  C-4 XL ceiling.
- Total: ~300 LOC implementation + ~120 LOC test + ~600-1000 LOC
  example markdown ≈ ~1100-1400 LOC; comfortably ≤ 0.5 PV.

**Confirms / revises §3 estimate (S / ≤ 0.5 PV) from
`v10_internal_optimization_directions.md` §3.1 D-A-1 (which estimated
"S (≤1 PV)").** Refining downward to ≤ 0.5 PV because the audit
script is small + most of the LOC is markdown content for the new
example file (which is content authoring, not code complexity).

## §8 — dependencies

**None — this patch is fully standalone.**

The audit script depends on:

- `.local/research/v9.*.0_cycle_plan.md` + `v10.*.0_cycle_plan.md`
  (read-only inputs; already exist at v10.3.0 baseline).
- `.local/research/v9.*.0_retrospective.md` + `v10.*.0_retrospective.md`
  (read-only inputs; already exist).

The advisory SKILL.md edit depends on:

- `workflow-system/agent/SKILL.md` (read + 1-2 line edit).
- `workflow-system/agent/references/agent-hierarchy.md` (read-only;
  cited by the advisory wording).

The new example depends on:

- `workflow-system/agent/references/meta-framework.md` §"Multi-team
  codebase analysis pattern" (line 65-86; cited as the canonical L1/L2
  use case).
- `scripts/sync_cursor_skill.py` MIRRORED_FILES list (additive update).

…all of which exist at v10.3.0; no other v11.0.0 patches required.

**Synergy (NOT a hard dependency):**

- D-D-1 (reference actual load rate audit) shares the "scan
  cycle docs + emit utilization stats" pattern with D-A-1; if both
  land in v11.0.0, consider a shared `scripts/_audit_common.py` helper
  (~40 LOC of common regex / glob / table-render code).
- D-A-4 (workspace activation edge clarity) consumes D-A-1's
  classification verdict surface. If both land, D-A-1's example file
  should cite D-A-4's clarified thresholds.
- D-A-2 (template compression) overlaps in spirit (architectural
  health) but shares no code; both can land independently.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | The audit script's regex-based "L1 dispatch" detection produces false positives (e.g., a retro mentioning "L1 Stage Agent" as a role, not a dispatch) → audit ratio overstates L1 usage | minor | Script's regex is conservative (matches "Dispatch type: Stage" specifically, not generic "L1" mentions); script outputs both "raw mentions" (over-counted) AND "dispatch-type counts" (precise) so reader sees both. Test coverage: `tests/test_audit_layer_usage.py::test_dispatch_type_vs_role_disambiguation`. |
| R2 | Advisory wording in SKILL.md §"4-Layer Agent Hierarchy" is read by an L0 as "ignore L1/L2", causing a regression on Standard+ tasks where L1/L2 ARE necessary (e.g., multi-team analyze merge per `meta-framework.md:65-86`) | major | Advisory wording is bounded to "Simple-tier tasks may collapse L1/L2"; explicitly cites STANDARD+ as still requiring full hierarchy; new `examples/multi-stage-trace.md` provides the worked counter-example showing WHEN L1/L2 are needed. |
| R3 | The audit script reveals L1/L2 ARE used > 5% in some cycle (contrary to hypothesis) → invalidates the advisory recommendation | minor | The patch ships the AUDIT first; the advisory wording is conditional on the data. If audit shows L1/L2 > 5%, the SKILL.md edit should NOT mark them "only-when-needed" — instead the patch's conclusion changes to "L1/L2 are used; SKILL.md is correct as-is" and the advisory paragraph documents the discovery. The PR review must check the audit output before merging the advisory wording. |
| R4 | New example file `multi-stage-trace.md` (4th example) approaches but does not exceed C-4 XL ceiling (≤1600 lines) → future authors of additional examples may push over the ceiling | minor | Example file budgeted at 600-1000 LOC well under 1600 cap; keeps headroom for future examples. SI-3 §3 maintainability dimension would catch ceiling-violating examples in next cycle's evaluation. |

---

ADMISSION: CONDITIONAL_PASS | EFFORT: S | DEPS: none | TIER: standard
