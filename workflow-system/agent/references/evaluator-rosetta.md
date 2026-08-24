---
last_updated: "2026-08-25"
---

# Evaluator Rosetta — SI-3 × NineS × Si-Chip Cross-Walk

## Purpose

DevolaFlow ships **three concurrently active cycle evaluators** that
all surface in every cycle close. Operators reading per-cycle
`v*_evaluation.md` artifacts cannot tell which axes of the three
signals measure overlapping phenomena vs orthogonal phenomena. This
reference is the **canonical 6 × 9 mapping table** between the three
evaluators, with verbatim citations to per-cell sources of authority.

The rosetta is a **reading-time artifact**: an L2 Task agent authoring
a `.local/research/vX.Y.Z_evaluation.md` looks up the row for the
SI-3 dimension being scored, follows the canonical (**C**-cell)
column to the NineS or Si-Chip metric that is the authoritative
quantitative input, and cites the metric verbatim per Rule C-3
(verbatim extraction).

External tool URLs (Rule S-7 — never hard-code local paths):

* **DevolaFlow / EvoBench:** [https://github.com/YoRHa-Agents/DevolaFlow](https://github.com/YoRHa-Agents/DevolaFlow)
* **NineS:** [https://github.com/YoRHa-Agents/NineS](https://github.com/YoRHa-Agents/NineS)
* **Si-Chip:** [https://github.com/YoRHa-Agents/Si-Chip](https://github.com/YoRHa-Agents/Si-Chip)

## When to Load

Load this reference when:

* **Authoring an SI-3 evaluation report** (`.local/research/vX.Y.Z_evaluation.md`).
  Every per-dimension justification cites the rosetta cell that
  identifies the canonical authority metric.
* **Triaging an evaluator disagreement** — e.g., NineS reports
  `code_coverage: 0.0` but `pytest --cov` reports 93%. The rosetta
  documents which evaluator owns the dimension's authority and what
  the fallback path is.
* **Preparing a cycle retrospective** (W-7 / SI-8). The rosetta lists
  cross-evaluator deltas you should report.
* **Building a new cycle gate** that cites multi-evaluator
  composite — the rosetta keeps the citations honest.

The reference is `important`-tier for most task types and
`critical`-tier for `nines-assisted` and `self-update` workflows where
multi-evaluator reconciliation is the primary deliverable.

## Body

### 1. The three evaluators

| Evaluator | Scale | Composite formula | Authority | Run frequency |
|---|---|---|---|---|
| **SI-3** | 1–10 (weighted composite) | `0.20·CQ + 0.20·Arch + 0.20·Tests + 0.15·Maint + 0.10·Compat + 0.15·Perf` | Binding ACCEPT/REJECT verdict (≥ 8.5 MINOR / ≥ 9.0 MAJOR) | Every pre-release |
| **NineS** | 0.0–1.0 (per-axis); composite = weighted mean | `0.70·capability_mean + 0.30·hygiene_mean` | Advisory research snapshot (Part B of the C-04 split) | Every cycle close + retrospective input |
| **Si-Chip** | scalar `iteration_delta` | `Σ(per-pass score) — N·threshold` | 7th SI-10 step (binding pre-commit gate) | Pre-commit + iteration close |

The C-04 split (`scripts/generate_si3_evaluation.py` lines 9–24)
explicitly separates the binding **Quality Gate** block (SI-3 + EvoBench,
Part A) from the advisory **Research Snapshot** block (NineS, Part B).
Si-Chip's iteration_delta is the v10.2.0+ post-cycle pre-commit gate
codified at `Makefile::release-preflight` line 147.

### 2. Per-evaluator dimension catalog

#### 2.1 SI-3 dimensions (6)

Per `.cursor/rules/repo-governance.mdc` §W-3 and `AGENTS.md` §W-3:

| # | Dimension | Weight | What is measured |
|---|---|:---:|---|
| 1 | **Code quality** | 0.20 | Lint cleanliness (ruff), complexity metrics (radon CC), error-handling discipline (S-5), no-silent-failure compliance |
| 2 | **Architecture rationality** | 0.20 | Separation of concerns, layering, P1–P5 dispatcher invariants, ADR coverage, A-2 cache-prefix invariant, A-5 SSOT-registry invariant |
| 3 | **Test adequacy** | 0.20 | Coverage ≥ 80% (CP-2 floor), edge cases, regression tests, R5 byte-identical contracts, W-17 +30/PV cap honoured |
| 4 | **Maintainability** | 0.15 | Readability, docstring coverage, naming clarity, S-2 / SF-5 path discipline, W-19 cycle-archive presence |
| 5 | **Compatibility** | 0.10 | Schema versions, multi-baseline byte tests passing, cross-platform behaviour, W-20 env-flag reuse-first compliance |
| 6 | **Performance impact** | 0.15 | EvoBench composite delta vs baseline (no > 5% regression), latency budgets, Si-Chip iteration_delta gate |

#### 2.2 NineS dimensions (20 capability + 5 hygiene)

Per `docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.md` lines 28–67 (NineS V3.3.0 schema):

**Capability sub-scores (20 axes; weight 0.70):** scoring_accuracy,
eval_coverage, scoring_reliability, report_quality, scorer_agreement,
source_coverage, source_freshness, change_detection, data_completeness,
collection_throughput, decomposition_coverage, abstraction_quality,
code_review_accuracy, index_recall, structure_recognition,
pipeline_latency, sandbox_isolation, convergence_rate,
cross_vertex_synergy, agent_analysis_quality.

**Hygiene sub-scores (5 axes; weight 0.30):** code_coverage,
test_count, module_count, docstring_coverage, lint_cleanliness.

For the rosetta we group the 20 capability axes into three
**capability sub-bundles** based on what they measure:

| Sub-bundle | Axes |
|---|---|
| **scoring/eval** | scoring_accuracy, eval_coverage, scoring_reliability, report_quality, scorer_agreement, scorer agreement, scoring_throughput |
| **decomposition/abstraction** | abstraction_quality, code_review_accuracy, decomposition_coverage, structure_recognition, cross_vertex_synergy, agent_analysis_quality, change_detection |
| **infra/sandbox** | sandbox_isolation, pipeline_latency, index_recall, convergence_rate, source_coverage, source_freshness, data_completeness, collection_throughput |

The grouping is not part of NineS itself — it's a DevolaFlow-side
reading aid for the rosetta.

#### 2.3 Si-Chip dimensions (per-pass scalars)

Per `docs/cycle-archive/v10.3.0/evaluation/v10.3.0_evaluation.md` lines 24, 55, 60–62 +
`tests/test_sichip_iteration_delta_gate.py`:

* **`iteration_delta`** — the cycle-level performance-improvement
  scalar. Computed as the weighted sum of per-pass scores for the
  cycle's commit set; threshold is configured per cycle. Reported as
  a single APPLY / DEFER / REJECT verdict in the cycle close.
* Si-Chip's per-pass scoring runs a battery of probes (probe.toml
  fixtures) and aggregates with policy weights. In the rosetta we
  treat Si-Chip as **one column** because its output to SI-3 is the
  scalar — the per-probe breakdown lives in the Si-Chip raw artifact
  (`.local/research/vX.Y.Z_sichip.{json,md}`), not in the SI-3
  composite.

### 3. The 6 × 9 rosetta table (the meat of D-O-1)

**Rows (N=6):** SI-3 dimensions (W-3 weighted composite).
**Columns (M=9):** 5 NineS hygiene axes + 3 NineS capability sub-bundles + Si-Chip `iteration_delta` scalar.

**Cell legend:**

* **C** = `covers` — the column metric is the canonical authority for
  the row dimension's QUANTITATIVE sub-component. Use the column's
  value verbatim.
* **O** = `overlaps` — the column metric measures a related-but-
  different aspect of the row dimension. Cite as supporting evidence;
  not the authority.
* **·** = `orthogonal` — the column metric measures an unrelated
  phenomenon. Do not cite under this row.

| SI-3 dim ↓ | NineS `code_coverage` | NineS `lint_cleanliness` | NineS `docstring_coverage` | NineS `test_count` | NineS `module_count` | NineS cap. `scoring/eval` | NineS cap. `decomp/abstract` | NineS cap. `infra/sandbox` | Si-Chip `iteration_delta` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Code quality (0.20)**            | O | **C** | O | · | · | · | O | · | O |
| **Architecture rationality (0.20)** | · | · | · | · | O | · | **C** | O | O |
| **Test adequacy (0.20)**           | **C** | · | · | **C** | · | O | · | O | · |
| **Maintainability (0.15)**          | · | O | **C** | · | O | · | O | · | · |
| **Compatibility (0.10)**            | · | · | · | · | · | · | · | **C** | · |
| **Performance impact (0.15)**       | · | · | · | · | · | O | · | O | **C** |

**C-cell coverage by dimension:**

| Dimension | Canonical authority cell(s) | Rationale |
|---|---|---|
| Code quality | NineS `lint_cleanliness` | Both metrics emit from the same `ruff check` invocation; NineS is the authority surface. |
| Architecture | NineS capability `decomp/abstract` | Captures `abstraction_quality`, `decomposition_coverage`, `code_review_accuracy`, `structure_recognition`. |
| Test adequacy | NineS `code_coverage` + NineS `test_count` (dual) | `code_coverage` for the percentage, `test_count` for the W-17 cap audit. |
| Maintainability | NineS `docstring_coverage` | The single hygiene axis that maps cleanly. |
| Compatibility | NineS capability `infra/sandbox` (specifically `structure_recognition` + `sandbox_isolation`) | Byte-stability axes tied to A-2 + A-5 invariants. |
| Performance impact | Si-Chip `iteration_delta` | The scalar IS the cycle-level performance-improvement gate. |

### 4. Per-cell justifications (verbatim source citations)

Each justification below is the operator's reading guide to the
authority — copy it into the SI-3 evaluation per-dim rationale field
verbatim per Rule C-3.

#### 4.1 Code quality C-cell — NineS `lint_cleanliness`

**Source 1:** `docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.md` line 64:
"lint_cleanliness | 1.0000 | `ruff check src/ tests/` All checks passed!"

**Source 2:** `docs/cycle-archive/v10.0.0/evaluation/v10.0.0_evaluation.md` §2.1 line 33:
"ruff check src/ tests/ — All checks passed!"

Both metrics are emitted by the same `ruff check` invocation. NineS
captures it under `lint_cleanliness`; SI-3 reuses the value verbatim.
The cell is **C** because the metric IS the SI-3 sub-component.

When `lint_cleanliness < 1.0`, the SI-3 deduction prose MUST cite the
specific ruff rule(s) reported in NineS's `details` field — never
paraphrase.

#### 4.2 Code quality O-cells

* **NineS `code_coverage`** — overlaps because high coverage often
  correlates with more disciplined error handling (S-5 compliance),
  but coverage % is owned by **Test adequacy**, not Code quality.
* **NineS `docstring_coverage`** — overlaps because docstring
  presence proxies for thoughtful API design (a code-quality signal),
  but the canonical authority is **Maintainability**.
* **NineS capability `decomp/abstract`** — overlaps via
  `abstraction_quality` (1.0000 in `v10.0.0_nines.md` line 43)
  proxying code structure, but the dimension is **Architecture**.
* **Si-Chip `iteration_delta`** — overlaps because cycles that ship
  cleaner code typically advance the iteration_delta scalar, but the
  scalar is the **Performance impact** authority.

#### 4.3 Architecture rationality C-cell — NineS capability `decomp/abstract`

**Source:** `docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.md` lines 41–44:

```
abstraction_quality        | 1.0000
code_review_accuracy       | 1.0000
decomposition_coverage     | 1.0000
structure_recognition      | 1.0000
```

Together these axes are NineS's canonical architectural signal. SI-3
*Architecture rationality* scoring should cite the worst of the four
when authoring a deduction (e.g., "decomposition_coverage = 0.97 →
−0.3 architecture deduction").

#### 4.4 Architecture O-cells

* **NineS `module_count`** — overlaps as a structural growth
  indicator; large module-count cycles often surface architectural
  drift, but the metric does not measure rationality.
* **NineS capability `infra/sandbox`** — overlaps via
  `structure_recognition` (architecture-byte-stability) but the
  primary authority for that axis is **Compatibility** (A-2 frozen
  prefix invariant).
* **Si-Chip `iteration_delta`** — overlaps because architectural
  improvements usually convert to forward iteration_delta, but the
  Si-Chip scalar's authority is **Performance**.

#### 4.5 Test adequacy DUAL C-cells — NineS `code_coverage` + NineS `test_count`

**Source 1 (coverage):** `docs/cycle-archive/v10.0.0/evaluation/v10.0.0_evaluation.md`
§2.3 line 64: "Coverage 93.13%" + `v10.0.0_nines.md` line 60:
"test_count | 1.0000 | 3906 tests"

**W-2 manual fallback:** when `code_coverage: 0.0` due to the
upstream NineS timeout artifact (per `v10.0.0_nines.md` lines 78–90),
the SI-3 *Test adequacy* score uses `pytest --cov=devolaflow`
directly. The fallback IS the SI-3 authority surface in that
degraded-NineS regime; the rosetta cell stays **C** (the surface
hasn't moved — the fallback computes the same number).

**Source 2 (test count):** the W-17 cap audit (≤ +30 NEW tests per
PV; ≤ +150 cumulative cycle delta) is computed from the
`test_count` delta vs the prior cycle.

When both surfaces conflict (e.g., NineS reports `test_count: 3906`
but `pytest --collect-only -q | tail -1` reports a different number),
trust the local pytest output — NineS's index may be stale; refresh
with `make nines-index-rebuild`.

#### 4.6 Maintainability C-cell — NineS `docstring_coverage`

**Source:** `docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.md` line 62:
"docstring_coverage | 0.9808"

**Cycle citation:** `docs/cycle-archive/v10.3.0/evaluation/v10.3.0_evaluation.md` line 22
cites docstring drift as a `−0.7` deduction in maintainability.
NineS is the canonical authority; SI-3 cites the rate verbatim and
applies the deduction prose.

#### 4.7 Maintainability O-cells

* **NineS `lint_cleanliness`** — overlaps because clean lint
  correlates with maintainable code, but the canonical authority for
  lint is **Code quality**.
* **NineS `module_count`** — overlaps as a growth indicator that
  affects per-file maintainability load, but does not directly
  measure maintainability.
* **NineS capability `decomp/abstract`** — overlaps via
  `abstraction_quality` (well-abstracted code is easier to maintain),
  but its primary authority is **Architecture**.

#### 4.8 Compatibility C-cell — NineS capability `infra/sandbox` (`structure_recognition` + `sandbox_isolation`)

**Source:** `docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.md` lines 46, 48:
"structure_recognition | 1.0000" + "sandbox_isolation | 1.0000"

`structure_recognition` is the **byte-stability axis** explicitly tied
to the A-2 frozen-prefix invariant (`tests/test_layout_invariant_multi_baseline.py`
must stay 10/10 PASS). `sandbox_isolation` covers the cross-
environment behaviour (R5 strict env-flag isolation; W-20 reuse-first
compliance).

SI-3 *Compatibility* dimension scoring at
`docs/cycle-archive/v10.0.0/evaluation/v10.0.0_evaluation.md` §2.5 lines 96–104 enumerates
"10 historical multi-baseline byte tests" — exactly the surface
NineS measures.

#### 4.9 Performance impact C-cell — Si-Chip `iteration_delta`

**Source:** `docs/cycle-archive/v10.3.0/evaluation/v10.3.0_evaluation.md` line 24:
"EvoBench composite scores stable" + line 55: "Si-Chip dogfood
verdict | DEFER → APPLY (passes #3 + #4 = +0.9 each)"

The iteration_delta scalar is the cycle-level performance-improvement
authority post-v10.2.0. Before v10.2.0, SI-3 §2.6 used the EvoBench
composite directly. The v10.2.0 D-V-1 patch promoted `iteration_delta`
to the 7th SI-10 step (`Makefile::release-preflight` line 147).

#### 4.10 Performance impact O-cells

* **NineS `pipeline_latency`** (capability axis 16) — `v10.0.0_nines.md`
  line 47 reports "pipeline_latency | 0.9999". This is an internal
  NineS execution metric (NineS's own pipeline took ~30s), not a
  DevolaFlow performance signal. **Overlaps but not authoritative**.
* **NineS capability `scoring/eval`** — `collection_throughput` and
  related axes are advisory inputs to performance discussion, but
  the cycle-level authority is Si-Chip.

### 5. Evaluator weighting recommendation (R-10 of v11.0.0 cycle plan)

When a future evaluation needs to fuse the three evaluators into a
single composite (currently NOT used — SI-3 is the sole binding gate;
NineS is advisory; Si-Chip iteration_delta is a separate pre-commit
gate), the recommended starting weighting is:

| Composite | Weight | Justification |
|---|:---:|---|
| Objective (auto-collected) | 0.6 | The 19/22 sub-components D-O-2 auto-fills are objective signals (ruff exit, coverage %, baseline pass count) free of Task-author judgment variance. |
| Subjective (L2 deduction prose) | 0.4 | The 3/22 subjective sub-components (architecture rationale, edge-case adequacy, naming clarity) require judgment that auto-collection cannot replace. |

This 0.6 / 0.4 weighting is the **starting point** per the v11.0.0
cycle plan §6 R-10 risk mitigation and the D-O-2 §2.1 decision. If
a cycle's reproducibility variance σ exceeds 0.30 across two L2 Task
authors, escalate to W-7 retrospective for cycle-lead recalibration.

The weighting only applies WHEN auto-collection is in use (D-O-2
shipped); v10.7.0 ships the collector + this weighting recommendation,
but cycle-close composites continue to use the SI-3 binding 6-dim
formula unchanged. The 0.6/0.4 split lives **inside each dim's score
cell** (auto-fill = 0.6 weight, Task prose = 0.4 weight) — not on top
of the dim weights.

### 6. Reading workflow for an SI-3 evaluation report

Step-by-step procedure for the L2 evaluation Task authoring
`.local/research/vX.Y.Z_evaluation.md`:

1. **Run the auto-collector** (D-O-2):

   ```bash
   python scripts/auto_collect_si3_metrics.py \
       --output .local/research/v<X.Y.Z>_si3_metrics.yaml
   ```

2. **Generate the skeleton** with auto-cells filled:

   ```bash
   python scripts/generate_si3_evaluation.py <X.Y.Z> \
       --metrics .local/research/v<X.Y.Z>_si3_metrics.yaml
   ```

3. **For each of the 6 SI-3 dimensions**, look up its row in §3 above.
   The **C**-cell column tells you the canonical authority metric.
   For each dimension:
   * If the auto-collector populated the cell → use the verbatim value.
   * If the auto-collector returned `(unavailable: <reason>)` → fall
     back to the W-2 manual path (typically a direct `pytest --cov`
     or `ruff check` invocation).
   * Cite the source artifact path verbatim in the rationale field
     (per Rule C-3).

4. **Author the deduction prose** for each dimension. The 0.4
   subjective weight (per §5 above) lives here. Aim for ≥ 50 words
   of justification per dim — the v10.7.0 D-O-2 §6 R-1 mitigation
   forbids "rubber-stamp" subjective scoring.

5. **Compute the composite** using the W-3 formula:

   ```
   composite = 0.20·CQ + 0.20·Arch + 0.20·Tests + 0.15·Maint + 0.10·Compat + 0.15·Perf
   ```

6. **Verdict**: composite ≥ 8.5 → ACCEPT (MINOR/PATCH); composite ≥ 9.0
   → ACCEPT (MAJOR). Below threshold → iterate (loop back to W-1
   planning gate) or escalate to human.

7. **Cite this rosetta** in the evaluation report header so future
   cycle-N+1 reviewers can replay the scoring.

### 7. Common evaluator-disagreement patterns

Three patterns surface repeatedly in DevolaFlow's cycle history:

#### 7.1 NineS `code_coverage: 0.0` with pytest reporting healthy %

**Symptom.** `.local/research/vX.Y.Z_nines.json` shows `code_coverage:
0.0` while `pytest --cov=devolaflow` reports 93%.

**Cause.** NineS's `pytest --cov` invocation timed out (default 60s
budget); the timeout artifact is documented in `v10.0.0_nines.md`
lines 78–90.

**Resolution.** Apply the W-2 manual fallback. Re-run NineS with the
180s budget per the A1 closure target (still being chased upstream
in NineS V3.4.0). Until then, SI-3 cites the local `pytest --cov`
output verbatim and notes the NineS timeout in the deduction prose.

**Authority disposition.** SI-3 owns the dimension; NineS is advisory.
The fallback path is canonical (Rule W-2 explicit).

#### 7.2 NineS index staleness (`index_recall < 0.85`)

**Symptom.** `index_recall` reports < 0.85 for multiple consecutive
cycles; per-axis scores look stable but overall composite drifts.

**Cause.** The NineS index (`docs/cycle-archive/misc/nines_codebase_analysis.md`)
is stale — golden_test_set or src/devolaflow/ changed since the last
index rebuild.

**Resolution.** Run `make nines-index-rebuild` (the v8.5.0 PV-05 A3
closure target). This refreshes the index without affecting SI-3's
binding score (NineS is advisory).

**Authority disposition.** Operator-side maintenance; SI-3 unaffected.

#### 7.3 Si-Chip `iteration_delta` DEFER vs SI-3 ACCEPT

**Symptom.** SI-3 composite says ACCEPT (≥ 8.5) but the Si-Chip
iteration_delta gate (`make iteration-delta-gate`) reports DEFER.

**Cause.** Si-Chip's per-pass weighted scoring deemed the cycle's
performance/iteration delta insufficient (e.g., regression on probe
#5 that wasn't bad enough to fail SI-3's Performance impact dim but
was bad enough to fail Si-Chip's threshold).

**Resolution.** Two parallel gates trump composite — both must PASS
for cycle close. If Si-Chip says DEFER, the cycle iterates (loop back
to W-1). The Si-Chip gate is configured at
`tests/test_sichip_iteration_delta_gate.py` and the threshold at the
cycle-specific Si-Chip baseline.

**Authority disposition.** Both gates are binding; SI-3 doesn't
override Si-Chip.

### 8. Reference utilization expectations

Once D-O-1 lands, future evaluations are expected to:

* Cite this rosetta at least once per dim (so 6 cite sites per
  evaluation report). Verifiable via `rg "evaluator-rosetta\.md"
  .local/research/v*_evaluation.md`.
* Reference rate ≥ 80% within the first MINOR after landing.
* L2 evaluation authoring time drops from ~90 min (manual) to ~50
  min (rosetta-assisted) per the D-O-1 §4 expected delta.

The D-O-3 mid-cycle research index (`scripts/index_mid_cycle_research.py`)
will surface `evaluator-rosetta.md` as a Tier-2 reference; the
audit `scripts/generate_evaluator_rosetta.py` (D-O-1 companion)
emits a sanity-check rosetta CSV that operators can diff against
this reference's §3 table.

### 9. Maintenance contract

When upstream evaluators add or rename axes, this reference MUST be
refreshed in the **same PR** that bumps the upstream version pin.
Specifically:

* If NineS V3.4.0 renames `lint_cleanliness` → `lint_health`:
  update §3 column header + §4.1 source citation in the same PR
  that bumps the NineS dependency.
* If Si-Chip MVP-9 changes `iteration_delta` shape (e.g., promotes
  the scalar to a dict): update §2.3 + §3 + §4.9 in the same PR
  that bumps the Si-Chip dependency.
* If SI-3 weights change in `repo-governance.mdc` §W-3: update
  §1 / §2.1 / §6 in the same PR that compiles `.rules/workflow.mdc`.

A CI-time lint at `tests/test_evaluator_rosetta_currency.py`
(deferred to v10.8.x — the lint surface lands when an upstream
version bump first triggers a refresh need; for v10.7.0 the rosetta
ships fresh with no drift to lint against) will eventually pin
this maintenance contract; until then, the W-18 ghost-audit refresh
(`tests/test_no_ghost_features.py::test_v10_7_0_new_symbols_have_coverage`)
asserts the file's presence + frontmatter.

### 10. Cross-references

* `references/decomposition-gate.md` — gate evaluation flow that
  consumes SI-3 composite as the binding ACCEPT input.
* `references/agent-workspace.md` §STATUS.yaml — `gate_score` field
  carries the SI-3 composite in the FSM machine-readable state.
* `references/env-flags.md` — DEVOLAFLOW_* flags that gate the
  auto-collector (none added by v10.7.0; W-20 reuse-first PASS).
* `scripts/auto_collect_si3_metrics.py` (D-O-2) — populates the
  rosetta's C-cells automatically.
* `scripts/generate_evaluator_rosetta.py` (D-O-1 companion) —
  emits a CSV sanity-check matching §3.
* `scripts/generate_si3_evaluation.py` — generates the SI-3
  evaluation report skeleton (with the C-04 split that this rosetta
  cross-walks).
* `Makefile` targets: `iteration-delta-gate` (Si-Chip), `nines-index-rebuild`
  (NineS), `gen-evaluator-rosetta` (D-O-1).
* External: NineS V3.3.0 schema reference at the NineS GitHub repo;
  Si-Chip MVP-8 reference at the Si-Chip GitHub repo.

### 11. Glossary

* **C-04 split** — `scripts/generate_si3_evaluation.py` lines 9–24 —
  the binding (Part A) vs advisory (Part B) split codified in
  v8.5.0 PV-05 to prevent NineS hygiene timeouts from leaking into
  SI-3 ACCEPT/REJECT.
* **iteration_delta** — Si-Chip's per-cycle scalar (positive →
  improvement, negative → regression).
* **W-2 manual fallback** — `repo-governance.mdc` §W-2 — the rule
  that lets SI-3 use direct `pytest --cov` / `ruff check` output
  when the upstream NineS surface is unavailable.
* **rosetta** — the 6 × 9 cross-walk table at §3 above; the term
  comes from the Rosetta Stone analogy for translating between the
  three evaluator vocabularies.
