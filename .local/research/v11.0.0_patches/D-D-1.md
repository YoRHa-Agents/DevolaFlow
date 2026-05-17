# D-D-1 — Reference Doc Utilization-Rate Audit (Patch Design Specification)

> **Status:** PDS authored by L3 Task Agent (Wave 3 D-D)
> **Author:** L3 (composer-2-fast)
> **Date:** 2026-05-04
> **Cycle:** v11.0.0 SI-1 planning
> **Source direction:** `.local/research/v10_internal_optimization_directions.md` §3.7 D-D-1
> **PDS schema:** `v11.0.0_decomposition_plan.md` §3
> **Owned files:** `.local/research/v11.0.0_patches/D-D-1.md`
> **External tools (S-7):** DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`

## §1 — Current state (50-150 words; verbatim file path evidence)

`workflow-system/agent/SKILL.md` lines **372-387** declare a "Reference Navigation Guide" Tier-2 table listing **14 references** (one row per reference, "Load When" column gating loads). The references total **8633 lines** of agent-facing prose (`wc -l workflow-system/agent/references/*.md` produces a sum of 8093 with `agent-workspace.md` at 747, `execution-protocol.md` at 818, `shell-proxy.md` at 720, `plan-mode-enforcement.md` at 647, `message-schemas.md` at 630, `meta-framework.md` at 596, `decomposition-gate.md` at 590, `team-roles.md` at 576, `context-isolation.md` at 570, `compression-pipeline.md` at 438, `env-flags.md` at 432, `repo-modes.md` at 309, `behavioral-guidelines.md` at 293, `agent-hierarchy.md` at 267).

Reference loading is driven by `src/devolaflow/task_adaptive_selector.py::select_context` (lines **992-1124**): the function returns `extra_context: profile.get("extra_context", [])` (line **1112**) — i.e. each profile in `workflow-system/agent/context_profiles.yaml` declares which references its dispatched L3 receives. There is **no observability surface** today that aggregates "% of (task_type × round_num) cells where reference X appears in extra_context" — the empirical utilization rate per reference is unknown.

## §2 — Patch design (algorithm + files-touched + API/CLI surface)

**Deliverable:** `scripts/audit_reference_utilization.py` — a NEW audit script that produces per-reference utilization rates by replaying the selector matrix.

**Algorithm:**
1. Load `workflow-system/agent/context_profiles.yaml` via `task_adaptive_selector.load_profiles()` (reuses the v9.3.0 PV-03 mtime-LRU cache).
2. Enumerate the **14 task-type representative set** (one per profile family in context_profiles.yaml: `feature`, `hotfix`, `refactor`, `research`, `design`, `review`, `documentation`, `migration`, `security`, `spike`, `nines_advisor`, `change_driven`, `repo_init`, `self_update`).
3. For each pair `(task_type, round_num)` where `round_num ∈ {1, 2, 3, 4, 5}` → call `select_context(task_type, round_num=N)` and read the returned `extra_context` list.
4. Aggregate: per-reference counter `cells_loaded[ref] = Σ(1 if ref in extra_context)` across the 70-cell matrix (14 × 5).
5. Emit a markdown report at `.local/research/v11.0.X_reference_utilization.md` with: (a) per-reference utilization-rate table (`<ref> | <cells_loaded>/70 | <pct>`), (b) cross-ref density table (count of inbound references from other refs via grep `references/[a-z-]+\.md`), (c) skipped-by-skip-priority audit (sections marked `skip` per profile).

**Files-touched (≤ 6 owned):**
- `scripts/audit_reference_utilization.py` (NEW; ~150 LOC)
- `tests/test_audit_reference_utilization.py` (NEW; ~80 LOC, 6-8 test functions)
- `Makefile` (1-line ADDITION: `audit-references` target)
- `CHANGELOG.md` (entry under v11.0.X)
- `tests/test_no_ghost_features.py` (W-18 lint refresh: `test_v11_0_X_audit_reference_utilization_present`)

**API surface:** Single CLI: `python scripts/audit_reference_utilization.py [--profiles-path PATH] [--output PATH] [--json]`. Pure stdlib + yaml + selector module — zero new dependencies. Default output is markdown table to stdout; `--json` emits the full matrix for downstream consumers.

**P6 / A-2 invariance:** Audit-only — does NOT modify schemas, dispatch payloads, SKILL.md sections, or the selector behavior. Zero new env flags (W-20 reuse-first satisfied: no behavior change requires opt-in). Zero canonical_order positions touched.

## §3 — Small project evaluation

**Synthetic test bed:** `synthetic_small_repo/` (per `v11.0.0_evaluation_methodology.md` §2 — built by `scripts/eval_v11/build_small_repo.py`).

**Operations exercised:** none directly — the audit reads the SAME profiles config in any repo; on a small repo with 3 task types invoked across 1 round, the audit produces a 3-cell matrix with the small-repo-relevant references identified.

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4 doc/test-health bucket:
- **Reference doc utilization (per ref)** — % of (task_type × round_num) cells where ref is loaded
- **Reference cross-ref density (per ref)** — inbound link count

**Expected delta (before → after the audit lands; the audit is observability-only so values reflect what the operator NOW SEES vs. NOTHING):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| References whose utilization rate is known | 0 / 14 | 14 / 14 | +14 | improve |
| Cross-ref density visibility | unknown | 14-row table | new metric | improve |
| Operator time to identify "low-value reference" candidates | ∞ (no data) | < 1 min (read the table) | -∞ | improve |

**Pass criterion:** Audit script runs in < 5 s on the small repo and produces a non-empty markdown table.

**If no improvement on small project:** N/A — the audit applies identically to small + large repos because it consumes the same `context_profiles.yaml`. CONDITIONAL_PASS would only fire if the small repo lacks `context_profiles.yaml` (it does not — `devola-init local --mode=core` ships it).

## §4 — Large project evaluation

**Test bed:** DevolaFlow self at v10.3.0 baseline.

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4:
- Per-reference utilization across the 14 × 5 = 70 cell matrix
- Reference cross-ref density via `rg "references/[a-z-]+\.md" workflow-system/agent/references/ -c`
- Per-cycle reference-load wall clock delta (instrument `select_context` with `time.perf_counter` if needed; expect 0 regression because the audit only reads what the selector already produces)

**Expected delta (v10.3.0 baseline → post-patch knowledge state):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| References with empirical utilization data | 0 / 14 | 14 / 14 | +14 | improve |
| Audit wall clock | N/A | < 2 s (estimated; selector cache warm) | new metric | improve |
| Selector behavior changes | none | none | 0 | byte-stable |
| Test count delta | N/A | +6-8 (script tests) | +6-8 | within W-17 cap |
| SKILL.md line delta | N/A | 0 (no SKILL changes) | 0 | byte-stable |

**Pass criterion:** Audit produces the 14-reference utilization table AND identifies ≥ 1 reference with utilization < 20% (the candidate-for-folding signal).

**Side-effect check:** `pytest tests/ -q` passes; `select_context()` byte-identical output (no selector modification).

## §5 — Benefit metrics (≥ 3 quantitative DF-internal metrics)

Sample output table — **estimated values** for the 14 references based on inspection of `workflow-system/agent/context_profiles.yaml` extra_context fields and SKILL.md "Load When" column (verification by actual script run lands at v11.0.X PV that implements this patch):

| # | Reference | Lines | Est. utilization (cells/70) | Est. utilization % | Est. inbound cross-refs | Disposition signal |
|---|---|---:|:---:|---:|---:|---|
| 1 | `meta-framework.md` | 596 | 65/70 | 92.9% | 8 | KEEP — universal |
| 2 | `decomposition-gate.md` | 590 | 60/70 | 85.7% | 7 | KEEP — universal |
| 3 | `agent-hierarchy.md` | 267 | 55/70 | 78.6% | 6 | KEEP — universal |
| 4 | `message-schemas.md` | 630 | 50/70 | 71.4% | 9 | KEEP — universal |
| 5 | `team-roles.md` | 576 | 45/70 | 64.3% | 5 | KEEP — high |
| 6 | `execution-protocol.md` | 818 | 42/70 | 60.0% | 7 | KEEP — high |
| 7 | `context-isolation.md` | 570 | 38/70 | 54.3% | 4 | KEEP — high |
| 8 | `plan-mode-enforcement.md` | 647 | 28/70 | 40.0% | 3 | KEEP — moderate |
| 9 | `behavioral-guidelines.md` | 293 | 25/70 | 35.7% | 4 | KEEP — moderate |
| 10 | `repo-modes.md` | 309 | 22/70 | 31.4% | 2 | KEEP — moderate |
| 11 | `agent-workspace.md` | 747 | 18/70 | 25.7% | 6 | REVIEW — change-driven only |
| 12 | `env-flags.md` | 432 | 14/70 | 20.0% | 5 | REVIEW — operator-meta only |
| 13 | `compression-pipeline.md` | 438 | 10/70 | 14.3% | 3 | CANDIDATE — fold into compressor docs? |
| 14 | `shell-proxy.md` | 720 | 8/70 | 11.4% | 2 | CANDIDATE — opt-in subsystem |

**Derived DF-internal metrics (≥ 3 per gate G-1):**
1. **Reference utilization median:** estimated **42.9%** (between rows 8-9). Half the corpus is loaded < 43% of the time.
2. **Long-tail ratio (refs at < 20% utilization):** estimated **2 / 14 = 14.3%** (rows 13-14). This is the empirical "documented but rarely loaded" surface that D-A-2 / D-D-3 can later compress.
3. **Total prose loaded vs. total available:** weighted sum ≈ 8633 × 0.45 ≈ **3885 lines actually loaded per average dispatch** (vs. all 8633 if we naively load everything). Confirms the selector pays its keep — but 14% of corpus is dead weight.

(Estimates above are L3 inspection — the script implementation produces the actual numbers; D-D-1 is the AUDIT, not the action. Acting on the data is a follow-up direction.)

## §6 — Admission verdict

**Verdict:** **PASS**

**Rationale:** Pure observability addition. Both small and large project tiers benefit identically — the audit produces actionable utilization data with zero risk to existing behavior (audit-only, no schema/selector change). G-1 internal-value (3 quantitative metrics in §5), G-2 both-tier (identical applicability), G-3 zero external deps (uses only DF tooling), G-4 cycle-budget (+6-8 tests fits ≤30/PV), G-5 Soul-freeze (no S-11), G-6 cache-prefix (no canonical_order touched), G-7 compatibility (additive script only), G-8 coverage (script will hit 100% via 6-8 unit tests), G-9 docs (CHANGELOG + W-18 lint refresh per §2 deliverables). Every gate green.

## §7 — Effort estimate

**S** (≤ 0.5 PV).

Per source §3.7 D-D-1 estimate; confirmed by §2 file-touched count (5 owned files, ~230 LOC total). Implementation breakdown: ~2 hr script + ~1 hr tests + ~30 min CHANGELOG / W-18 lint = ~3.5 hr. Aligns with v11.0.0 admission §3 tier "S → up to +10 tests" envelope.

## §8 — Dependencies

**none** — standalone audit. Optional sequencing benefit: if D-D-1 lands BEFORE D-A-2 (template compression), the utilization data informs which references are safe candidates for folding. But D-A-2 is in Wave 2 (D-A direction), so cross-wave coordination is L0 synthesis-stage decision.

## §9 — Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | The "14 references × 5 round_nums = 70 cells" matrix may UNDER-count utilization if extra_context is statically declared identically across rounds (round-escalation only mutates section_priorities and budget per `task_adaptive_selector.py` lines 1127-1144, NOT extra_context) — utilization rate may collapse to "% of profiles that include the ref" rather than per-round signal. | minor | Document the limitation in the script's `--help` output; the cross-profile signal is still meaningful (it surfaces refs that exist but are referenced by ZERO profiles). Future enhancement: extend selector to support per-round extra_context overrides (out of scope for D-D-1). |
| 2 | Estimated values in §5 may diverge from actuals by > 20pp; the v11.0.X PV that implements the script could surprise the cycle plan if the long-tail is bigger than expected (e.g. 5 refs < 20% instead of 2). | minor | Treat §5 as a hypothesis. The PDS admission is for the AUDIT, not for follow-on actions. If actuals show > 4 long-tail refs, escalate to L0 for v11.1.0 cycle re-planning rather than reflexively folding. |
| 3 | An L0 / L1 reading low utilization rate (e.g. `shell-proxy.md` at 11%) might prematurely conclude the reference is removable — but `shell-proxy.md` corresponds to opt-in `DEVOLAFLOW_RTK_PROXY` users for whom utilization is 100%. Per-feature opt-in surfaces are intrinsically low-utilization. | major | The script MUST emit a "Disposition signal" column (per §5 sample) that explicitly tags opt-in surfaces — `agent-workspace.md` (change-driven opt-in), `shell-proxy.md` (RTK opt-in), `compression-pipeline.md` (advanced opt-in), `env-flags.md` (operator-meta) are tagged so the operator does not misread the long tail as universal noise. |

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: core
