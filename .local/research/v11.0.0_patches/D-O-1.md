# D-O-1 — Three-Evaluator Semantic Overlap Rosetta

> **PDS schema v1** per `.local/research/v11.0.0_decomposition_plan.md` §3
> **Wave:** 4b (D-O Observability & Self-Assessment)
> **Author:** L3 Task Agent (composer-2-fast)
> **Date:** 2026-05-04
> **Owned file:** `.local/research/v11.0.0_patches/D-O-1.md`
> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.4 D-O-1 (lines 208-215)
> **Evaluation methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §4.5 (Evaluator dimension overlap count)
> **External tools (S-7):** DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`, NineS `https://github.com/YoRHa-Agents/NineS`, Si-Chip `https://github.com/YoRHa-Agents/Si-Chip`

## §1 — current_state

DevolaFlow ships **three concurrently active cycle evaluators** that all surface in every cycle close, with **no documented dimension-level mapping** between them. Operators reading `v10.X.0_evaluation.md` cannot tell which axes of the three signals measure overlapping phenomena vs orthogonal phenomena.

**Verbatim file path evidence:**

* `.local/research/v10.0.0_evaluation.md` lines 13-22 — W-3 / SI-3 6-dimension table (Code quality 0.20 / Architecture 0.20 / Tests 0.20 / Maintainability 0.15 / Compatibility 0.10 / Performance 0.15; weighted composite 9.20/10).
* `.local/research/v10.3.0_evaluation.md` lines 17-25 — same 6-dimension structure (composite 9.385/10).
* `.local/research/v10.0.0_nines.md` lines 28-67 — NineS V3.3.0 self-eval: 20 capability axes (capability_mean 0.954980, weight 0.70) + 5 hygiene axes (hygiene_mean 0.796154, weight 0.30); overall composite 0.907332.
* `.local/research/v10.3.0_evaluation.md` lines 55, 60-62 — Si-Chip iteration_delta scalar (`+0.9` APPLY in v10.2.0 cycle); first computable iteration_delta in DevolaFlow history.
* `.cursor/rules/repo-governance.mdc` §W-3 (lines 358-360 of `AGENTS.md`) — 6-dimension weighted composite formula.
* `.cursor/rules/repo-governance.mdc` §S-10 (lines 80-119 of `AGENTS.md`) — Si-Chip iteration_delta wired as 7th SI-10 step in `Makefile::release-preflight` (line 146 of `Makefile`).

The three evaluators are **never reconciled in repo prose**. Cross-references in `v10.0.0_evaluation.md` §5 (lines 151-159) and `v10.3.0_evaluation.md` §3 (line 59) only state *"the NineS overall is on a different scale (0-1 normalized) and is NOT directly comparable to the SI-3 weighted composite (1-10 scale)"* — but they don't enumerate **which dimensions overlap**, leaving operators to infer mapping from naming similarity (a known anti-pattern; e.g., NineS `lint_cleanliness` and SI-3 `code_quality.lint` both measure ruff but the SI-3 dimension is broader).

## §2 — patch_design

### 2.1 Algorithm

1. Author `workflow-system/agent/references/evaluator-rosetta.md` (Large tier, ≤1000 lines per C-4 / SF-1) with the canonical N×M mapping table (§2.3 below) + per-cell verbatim citation.
2. Add `evaluator-rosetta.md` to SKILL.md `## Reference Navigation Guide` Tier-2 list (becomes the 11th reference). This is the only SKILL.md edit; ≤+5 lines.
3. Wire into `scripts/sync_cursor_skill.py::MIRRORED_FILES` (per SF-3) so the opt-in mirror picks up the new reference.
4. Refresh `tests/test_no_ghost_features.py::test_v11_0_0_new_symbols_have_coverage` (W-18 lint precondition) before the CHANGELOG entry.

### 2.2 Files-touched list

| Path | Operation | Lines |
|---|---|---:|
| `workflow-system/agent/references/evaluator-rosetta.md` | NEW | ≤ 800 |
| `workflow-system/agent/SKILL.md` | EDIT (1 line in Reference Navigation Guide) | +1 |
| `scripts/sync_cursor_skill.py` | EDIT (1 line in `MIRRORED_FILES`) | +1 |
| `tests/test_no_ghost_features.py` | EDIT (W-18 lint refresh) | +5 |
| `tests/test_reference_size_budgets.py` | parametrize auto-extends (zero hand-edit per `evaluator-rosetta.md` filename being globbed by the existing fixture) | 0 |
| `tests/test_integration.py::test_skill_md_under_500_lines` | re-runs (no edit; verifies SKILL.md still <500) | 0 |
| `CHANGELOG.md` | NEW entry | +5 |

**Zero source code changes.** Pure documentation patch + 1-line SKILL.md edit + sync_cursor_skill.py registry update. G-7 compatibility: pure-additive.

### 2.3 N×M rosetta mapping table (the meat of D-O-1)

**Rows (N=6):** SI-3 dimensions (W-3 weighted composite; per `repo-governance.mdc` §W-3).
**Columns (M=9):** 5 NineS hygiene axes + 3 NineS capability sub-bundles (the 20 capability axes group naturally into "scoring/eval", "decomposition/abstraction", "infra/sandbox") + Si-Chip iteration_delta scalar.

Cell legend:
* **C** = `covers` — the column metric is the canonical authority for the row dimension's QUANTITATIVE sub-component (use the column value verbatim).
* **O** = `overlaps` — the column metric measures a related-but-different aspect of the row dimension (cite as supporting evidence; not authority).
* **·** = `orthogonal` — the column metric measures an unrelated phenomenon (do not cite under this row).

| SI-3 dim → ↓ | NineS `code_coverage` | NineS `lint_cleanliness` | NineS `docstring_coverage` | NineS `test_count` | NineS `module_count` | NineS capability *scoring/eval* | NineS capability *decomposition/abstraction* | NineS capability *infra/sandbox* | Si-Chip `iteration_delta` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Code quality (0.20)** | O | **C** | O | · | · | · | O | · | O |
| **Architecture rationality (0.20)** | · | · | · | · | O | · | **C** | O | O |
| **Test adequacy (0.20)** | **C** | · | · | **C** | · | O | · | O | · |
| **Maintainability (0.15)** | · | O | **C** | · | O | · | O | · | · |
| **Compatibility (0.10)** | · | · | · | · | · | · | · | **C** (`structure_recognition`, `sandbox_isolation`) | · |
| **Performance impact (0.15)** | · | · | · | · | · | O (`pipeline_latency`, `collection_throughput`) | · | O | **C** |

**Cell justifications (verbatim citations from current artifacts):**

* SI-3 *Code quality* C-cell at NineS `lint_cleanliness` — `v10.0.0_nines.md` line 64: "lint_cleanliness | 1.0000 | `ruff check src/ tests/` All checks passed!"; `v10.0.0_evaluation.md` §2.1 line 33: "ruff check src/ tests/ — All checks passed!". Both metrics are emitted by the same ruff invocation; NineS is the canonical authority.
* SI-3 *Code quality* O-cell at *decomposition/abstraction* — capability sub-bundle includes `abstraction_quality` (1.0000 in `v10.0.0_nines.md` line 43) which proxies code-quality structure but excludes the lint surface SI-3 covers via the deduction rationale.
* SI-3 *Architecture rationality* C-cell at *decomposition/abstraction* — capability sub-bundle includes `abstraction_quality` (1.0000), `code_review_accuracy` (1.0000), `decomposition_coverage` (1.0000); `v10.0.0_nines.md` lines 41-44. These are NineS's canonical architectural signal.
* SI-3 *Test adequacy* dual C-cells at NineS `code_coverage` AND `test_count` — `v10.0.0_evaluation.md` §2.3 line 64: "Coverage 93.13%"; `v10.0.0_nines.md` line 60: "test_count | 1.0000 | 3906 tests". W-2 manual fallback applies when `code_coverage: 0.0` (upstream timeout artifact per `v10.0.0_nines.md` lines 78-90); fallback uses `pytest --cov=devolaflow` directly. The fallback IS the SI-3 authority surface.
* SI-3 *Maintainability* C-cell at NineS `docstring_coverage` — `v10.0.0_nines.md` line 62: "docstring_coverage | 0.9808"; `v10.3.0_evaluation.md` line 22 cites docstring drift as -0.7 deduction in maintainability. NineS is the canonical authority.
* SI-3 *Compatibility* C-cell at NineS `structure_recognition` (capability axis 15) + `sandbox_isolation` (axis 17) — `v10.0.0_nines.md` lines 46, 48: both 1.0000; structure_recognition is the **byte-stability axis** explicitly tied to A-2 frozen prefix invariant. SI-3 *Compatibility* dimension scoring at `v10.0.0_evaluation.md` §2.5 lines 96-104 enumerates "10 historical multi-baseline byte tests" — same surface NineS measures.
* SI-3 *Performance impact* C-cell at Si-Chip `iteration_delta` — `v10.3.0_evaluation.md` line 24: "EvoBench composite scores stable"; `v10.3.0_evaluation.md` line 55: "Si-Chip dogfood verdict | DEFER → APPLY (passes #3 + #4 = +0.9 each)". The iteration_delta scalar is the cycle-level performance-improvement signal post-v10.2.0; before v10.2.0 there was no canonical performance signal authority and SI-3 §2.6 used EvoBench composite directly.
* SI-3 *Performance impact* O-cell at NineS `pipeline_latency` (axis 16) — `v10.0.0_nines.md` line 47: "pipeline_latency | 0.9999"; this is an internal NineS execution metric, not a DevolaFlow performance signal — overlaps but not authoritative.

### 2.4 API/CLI surface

**Pure documentation.** No new functions, no new env flags (W-20 §3 reuse-first satisfied trivially — no flags added), no new schema fields (G-6 cache-prefix gate passes — zero canonical_order edits). The reference is consumed by L3 task agents authoring evaluation reports who **cite the rosetta cell for every per-dimension justification**.

**Reading workflow:** when authoring a `.local/research/vX.Y.Z_evaluation.md`, an L3 agent reads `references/evaluator-rosetta.md` row N for SI-3 dim N, then cites the column's C-cell metric verbatim from the corresponding NineS / Si-Chip raw artifact (no re-derivation; no paraphrasing per C-3 verbatim extraction).

## §3 — small_project_eval

**Synthetic test bed:** synthetic_small_repo (per `v11.0.0_evaluation_methodology.md` §2)

**Operations exercised:** None directly. Rosetta is a reading-time artifact; small project evaluation measures whether the reference is **discoverable and usable** for an L3 evaluating a 1-3-file repo.

**Metric collection:** simulated reading task — given a synthetic small-project SI-3 evaluation skeleton (`scripts/generate_si3_evaluation.py` output for `synthetic_small_repo`), measure the time + accuracy with which an L3 agent maps each of the 6 dimensions to authoritative NineS metrics. Per §4.5 Evaluator dimension overlap count.

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Reading time per dim (seconds, manual mapping) | ~120 | ~15 | -105 (-87%) | improve |
| Cross-evaluator citation accuracy (ratio of correct verbatim cites) | ~0.50 | ≥0.90 | +0.40 | improve |
| L3 evaluation skeleton fill-time (`generate_si3_evaluation.py` TBD → filled, all 6 dims) | ~30 min | ~12 min | -18 min (-60%) | improve |

**Pass criterion:** Δ ≥ -50% on reading time AND citation accuracy ≥ 0.85.

**If no improvement on small project:** small project has no NineS data (NineS isn't run on synthetic_small_repo) so the rosetta degenerates to a 1-evaluator (SI-3 only) lookup — but that path is still useful (it documents which sub-fields SI-3 expects per dim). Verdict downgrade in this case = `CONDITIONAL_PASS` (large-only).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline)

**Metric collection:** baseline = v10.0.0 + v10.3.0 evaluation reports (already in repo); post-patch = v11.0.0 (or first MINOR using the rosetta) cycle-close evaluation re-authored with rosetta cell citations per dim. Quantify cite-density and L3 author-time.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Verbatim cross-evaluator citations per dim (count) | 0.5 (avg; only `v10.0.0_evaluation.md` §5 cross-references NineS, no per-dim mapping) | ≥ 2.0 (every C-cell + at least 1 O-cell cited verbatim) | +1.5 | improve |
| Evaluator-rosetta reference rate (cycles citing it / total cycles) | 0% (doesn't exist) | ≥ 80% (every MINOR + MAJOR close) | +80pp | improve |
| L3 evaluation authoring time (wall-clock, end-to-end SI-3 report) | ~90 min (per v10.3.0 PV-06 commit history) | ~50 min (rosetta lookup eliminates re-derivation) | -40 min (-44%) | improve |
| Operators-confused-about-evaluator-overlap (subjective; cycle retro count) | ≥ 1 mention per cycle (v10.0.0 retro §3 telegraphed evaluator drift) | 0 mentions | -1 | improve |

**Pass criterion:** Cross-evaluator cite count ≥ 2.0 per dim AND reference rate ≥ 80% within first MINOR after landing.

**Side-effect check:** SKILL.md line count stays < 500 (only +1 line); 14 → 15 references (per `references/agent-workspace.md`-style addition; 11 was the last count cited in `references/env-flags.md` §2 but the methodology §3 cites 14 references at v10.3.0 baseline). C-4 large-tier ceiling ≤ 1000 lines respected; we plan ≤ 800 lines for the new reference.

## §5 — benefit_metrics

| Metric (DF-internal) | Bucket (`v11.0.0_evaluation_methodology.md` §) | Before (v10.3.0) | After (post-D-O-1) | Δ |
|---|---|---:|---:|---:|
| **Evaluator dimension overlap count** (canonical mapping cells documented) | §4.5 row 1 | 0 (no rosetta exists) | 54 cells (6 dims × 9 columns) | +54 |
| **Cross-evaluator verbatim citation density** (cites per dim per evaluation) | §4.5 derived | 0.5 | ≥2.0 | +1.5 (+300%) |
| **L3 evaluation authoring time** (wall-clock, full SI-3 report) | §4.1 derived | ~90 min | ~50 min | -40 min (-44%) |
| **C-cell coverage per SI-3 dim** (each dim has ≥1 canonical authority) | §4.5 derived | 0/6 (no canonical authority assignments) | 6/6 | +6 |
| **Reference utilization rate** (`task_adaptive_selector.py --verbose` cycles loading evaluator-rosetta) | §4.4 row 1 | n/a | ≥ 4 task types × ≥ 2 round_nums = ≥ 8 cells loading critical | new surface |

All metrics are scriptable from current DF tooling: `scripts/audit_reference_utilization.py` (ships with D-D-1; fallback: `task_adaptive_selector.py --verbose | grep evaluator-rosetta`); cite count via `rg "evaluator-rosetta\.md" .local/research/v*_evaluation.md | wc -l`; L3 wall-clock via git commit timestamp delta.

**Zero EvoBench dependency** — every metric is internal. G-1 internal-value gate satisfied.

## §6 — admission_verdict

**Verdict: CONDITIONAL_PASS**

**Justification:**
* **PASS on large project tier** — DevolaFlow self-evaluation cycle (v10.0.0, v10.3.0 reports) demonstrably benefits from the rosetta: every dimension's C-cell becomes citable verbatim instead of ad-hoc paraphrase. The +1.5 cite density delta is mechanically achievable.
* **CONDITIONAL on small project tier** — synthetic_small_repo lacks NineS / Si-Chip data by construction (those evaluators run against the DevolaFlow self-repo; small-project simulation has no NineS index, no Si-Chip plugin installed). The rosetta degenerates to a 1-evaluator (SI-3-only) lookup on small projects — still useful (it documents which sub-fields SI-3 expects per dim) but provides no cross-evaluator value.

**G-2 both-tier gate disposition:** CONDITIONAL — applicability bounds are explicit ("rosetta provides multi-evaluator value only on large projects with NineS+Si-Chip available; on small projects it is a single-evaluator dimension-glossary"). This satisfies the v11.0.0 admission checklist §G-2 CONDITIONAL clause: the patch ships with explicit applicability documentation rather than claiming universal benefit.

**Other gates:**
* G-1 internal-value: PASS (all §5 metrics are DF-internal; zero EvoBench dependency).
* G-3 zero-deps: PASS (no external tool changes; the patch consumes existing NineS / Si-Chip outputs as-published).
* G-4 cycle-budget: PASS (S effort = ≤ +10 tests; estimated +4 tests for parametrize + W-18 lint).
* G-5 Soul-freeze: PASS (zero S-* additions).
* G-6 cache-prefix: PASS (zero canonical_order edits).
* G-7 compatibility: PASS (pure-additive — new reference + 1-line SKILL.md edit; no public API change).
* G-8 test coverage: PASS (existing parametrize fixture in `tests/test_reference_size_budgets.py` auto-covers the new file; W-18 lint refresh at +4 tests).
* G-9 documentation: PASS — CHANGELOG entry + W-18 lint refresh + reference link in SKILL.md (SF-3 sync_cursor_skill.py update). Bilingual ST-3 NOT triggered (this is an agent-facing reference, not a user-facing guide).

## §7 — effort_estimate

**M (1 PV)**

**Breakdown:**
* Drafting the rosetta reference (≤ 800 lines including per-cell justifications): ~5 hours of analysis + writing.
* SKILL.md / sync_cursor_skill.py / W-18 lint edits: ~30 min.
* Tests (parametrize auto-coverage + 4 new W-18 lint asserts): ~30 min.
* PR review feedback iteration: ~1 PV slack.

**Confirms** the §3 decomposition plan's M estimate (1 PV).

## §8 — dependencies

**None (standalone).** The rosetta consumes existing v10.0.0 / v10.3.0 evaluation reports + NineS / Si-Chip raw artifacts as-published. No upstream waves block it.

**Optional synergy:**
* If D-O-2 (SI-3 6-dim auto-collection) lands in the same MINOR, the rosetta's C-cells become the canonical "where to find this auto-collected number" map. Synergy multiplies the value of both.
* If D-D-1 (reference utilization audit) lands in the same MINOR, evaluator-rosetta utilization rate becomes a measurable input to D-D-1's audit script (validates the patch's adoption).

But neither D-O-2 nor D-D-1 is a hard dependency; D-O-1 ships standalone.

## §9 — risk_register

| Risk | Severity | Description | Mitigation |
|---|---|---|---|
| **R-1** Cell mappings ossify and drift from evolving NineS/Si-Chip schemas | minor | If NineS V3.4.0 renames `lint_cleanliness` or Si-Chip MVP-9 changes `iteration_delta` shape, rosetta cells go stale. | Add a CI-time lint `tests/test_evaluator_rosetta_currency.py` that asserts every cited NineS column name is present in the latest cached raw output (`.local/research/vX.Y.Z_nines.json` keys); failure → flag for rosetta refresh. |
| **R-2** L3 agents over-cite C-cells and stop reading SI-3 deduction rationale | major | The rosetta's "this column IS the authority" framing risks reducing SI-3 to a metric-lookup table, losing the human-judgment surface SI-3 §2.X "deduction" prose. | Document explicitly in the rosetta header: "C-cell = canonical authority for the QUANTITATIVE sub-component; SI-3 dimension-score still requires the L3's qualitative justification (e.g., the +0.5/-0.5 deduction rationale)." Reinforce in §6 of the rosetta itself. |
| **R-3** Reference count crosses SF-1 implicit ceiling (14 → 15) requiring SKILL Tier-2 list refactor | minor | SF-3 currently caps the canonical mirror at 14 references (per `MIRRORED_FILES` count in `scripts/sync_cursor_skill.py`). Adding the 15th may require SF-1 / SF-3 spec note refresh. | Confirm with reviewer whether 14 is a hard cap or empirical; if hard, defer to a later PV that proposes a SF-3 cap raise alongside the rosetta. Current SF-1 governance text doesn't enumerate a hard ceiling — only the tiered line-count budget — so this risk is procedural-only. |

---

ADMISSION: CONDITIONAL_PASS | EFFORT: M | DEPS: none | TIER: standard
