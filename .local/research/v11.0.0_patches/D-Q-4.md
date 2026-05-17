# PDS — D-Q-4: `compressor/` Post-Split Health Snapshot (NineS deep-analyze)

> **Wave:** 5a (D-Q Code Quality)
> **Author:** L3 Task Agent (composer-2-fast)
> **Date:** 2026-05-04
> **Source:** `.local/research/v10_internal_optimization_directions.md` §3.5 D-Q-4
> **Schema:** `.local/research/v11.0.0_decomposition_plan.md` §3 (PDS v1)

## §1 — current_state

`src/devolaflow/compressor/` was **split from a monolithic single file** at v9.3.0 PV-04 (per
`.local/research/v9.3.0_nines_compressor.json` — the LAST NineS analysis on this surface, which
ran against the pre-split `src/devolaflow/compressor.py` 2541-LOC monolith and reported
**avg_complexity 4.98 + 2 warning-class CC findings** at `extract_named_entities` CC=11 +
`_assemble_abstractive_summary` CC=11). After the v9.3.0 PV-04 split, the surface became 4 files
totaling **3,085 LOC + 1 package init** (verified via `wc -l src/devolaflow/compressor/*.py`):

| File | LOC | Role |
|---|---:|---|
| `src/devolaflow/compressor/__init__.py` | 339 | Package re-exports + back-compat surface (`devolaflow.compressor.X` imports for tests + downstream) + module-level constants (`DEFAULT_DISPATCH_LAYOUT`, `FROZEN_PREFIX_V7`) |
| `src/devolaflow/compressor/layout.py` | 327 | Cache-layout governance: `assert_dispatch_layout`, `assert_layout_spec_invariant`, `compute_dispatch_lcp_pct` (A-2 frozen-prefix enforcement) |
| `src/devolaflow/compressor/patterns.py` | 221 | Compiled regex patterns + bypass conditions (`BYPASS_CONDITIONS`, `BYPASS_PATTERNS`, `_DATA_ENVELOPE_*_RE`) |
| `src/devolaflow/compressor/transforms.py` | **2,198** | The 4 canonical text-side transforms (truncate, summarise extractive/abstractive, directed_compact) + ~40 supporting helpers + Stage A / Stage B utilities |

**Total: 3,085 LOC across 4 files** (vs 2,541 LOC pre-split — a +21% net add, attributable to per-file
docstring overhead + the v9.3.0 PV-04 reorganization metadata).

**The v10.2.2 PV-03 NineS deep-analysis explicitly EXCLUDED `compressor/`** — confirmed by
`.local/research/v10.2.2_nines.md` §1 which lists only `si_chip_bridge/`, `plugins/`, `lifecycle/`
as analyzed packages, AND by the source doc §3.5 D-Q-4: *"v10.2.2 NineS 仅分析了 si_chip_bridge /
plugins / lifecycle 3 个包；compressor/ 未被深度分析"*. The most recent NineS data on this surface is
**1.3 years stale** (v9.3.0 cycle, against the pre-split monolith). Since then:
- v9.3.0 PV-04 — file split (4-way decomposition)
- v9.4.0 PV-03 — minor selector updates (lazy section eviction)
- v9.6.0 PV-02 — golden test set integration into compression scoring
- v9.7.0 PV-02/PV-03 — performance overhaul (selector LRU, async dispatch wiring)
- v10.0.0 — A-2 cache-layout governance v2 (frozen prefix codified)
- v10.2.X — Si-Chip integration touched layout.py for cache-prefix audit
- v10.3.0 — current baseline

The `transforms.py` file at **2,198 LOC is the largest single Python file in the entire
`src/devolaflow/` tree** (verified by Glob + Shell wc audit). It is the single biggest unaudited
risk surface for hidden complexity warnings.

## §2 — patch_design

**Algorithm:** Run NineS deep-analysis against `src/devolaflow/compressor/` to generate a fresh
post-split health snapshot. Emit the JSON output, derive a markdown synthesis (analogous to
`v10.2.2_nines.md`), and identify any new complexity hotspots. **D-Q-4 is essentially a 1-PV
auditing direction; the analysis IS the deliverable.** Any subsequent CC reductions found by NineS
become micro-PVs in v11.0.x (analogous to D-Q-1's helper-extraction series).

**Files-touched (write-allowed scope at PV implementation time; D-Q-4 is design-only here):**

| File | Change kind | Net delta |
|---|---|---:|
| `.local/research/v11.0.X_compressor_nines.json` | NEW: raw NineS JSON output | +~5-10 KB |
| `.local/research/v11.0.X_compressor_nines.md` | NEW: markdown synthesis (analogous to `v10.2.2_nines.md` schema: §1 per-package summary, §2 top findings, §3 keypoints, §4 hygiene sub-scoring, §5 PV candidates, §6 references) | +~80-150 LOC |

**Zero source-code changes.** Zero test changes. Zero schema bumps. Zero env-flag additions. The
direction is pure-audit; any actionable findings go to v11.0.x cycle plan as separate micro-PVs.

**NineS command (the canonical W-2 / SI-2 invocation per `repo-governance.mdc` W-2):**

```bash
nines -f json analyze \
  --target-path src/devolaflow/compressor/ \
  --depth deep \
  --agent-impact \
  --keypoints \
  > .local/research/v11.0.X_compressor_nines.json 2>&1
```

(Where `v11.0.X` = the actual PV version at implementation time, e.g. `v11.0.1`.)

**Manual fallback** (per W-2 manual fallback note: *"When NineS is unavailable, manual analysis
following the same dimensions is acceptable but must be explicitly noted as manual"*):

```bash
# Per-file CC analysis
radon cc -a -nB src/devolaflow/compressor/

# Per-file LOC + complexity raw metrics
radon raw src/devolaflow/compressor/

# High-CC function detection (warn threshold = 10)
radon cc src/devolaflow/compressor/ --min B --no-assert
```

The manual fallback yields radon's CC + Halstead + maintainability index but lacks NineS's
agent-impact / keypoints surfaces. Per `v10.2.2_nines.md` §3 the agent-impact surface is degenerate-
empty for compressor anyway (compressor is internal Python; no agent-facing markdown), so the
manual fallback covers ~95% of the actionable signal.

**Expected output schema (mirrors `v10.2.2_nines.md` — section markers below use `[Section N]`
in this PDS template to avoid colliding with the L0 synthesizer's `## §N` PDS-section regex; the
ACTUAL synthesis file authored at PV time uses the `## §N — <title>` heading style verbatim from
`v10.2.2_nines.md`):**

```markdown
# v11.0.X compressor NineS Deep Analysis Synthesis

[Section 1 — Per-package summary]
Table columns: Package | Findings count | Files | Total lines | Functions | Avg complexity | Top severity
Single row: src/devolaflow/compressor/ | <N> | 4 | 3,085 | <M> | <X.XX> | warning ×K  OR  info (no warnings)

[Section 2 — Top findings (severity-sorted)]
Table of warning-class CC findings, severity-sorted; 1 row per finding.

[Section 3 — Keypoints (per-file, NineS-extracted)]
- transforms.py — size + responsibility characterization
- layout.py — A-2 governance role + frozen-prefix invariant impact
- patterns.py — regex maintainability
- __init__.py — back-compat re-export surface

[Section 4 — Agent-impact / hygiene sub-scoring]
Table columns: Package | Findings/file | Warning ratio | Avg CC | Synthesis score (1-10)
Single row: compressor | <N/4> | <%> | <X.XX> | <Y.Y>

[Section 5 — Findings flagged for v11.0.X+ self-iteration]
PV candidate #N — src/devolaflow/compressor/<file>:<line> <func> CC=<X> → propose <helper> extraction.
Estimated CC reduction: <X> → <=<Y>. Test surface: tests/test_compressor.py::Test<Class>.

[Section 6 — References]
- Raw JSON: .local/research/v11.0.X_compressor_nines.json
- NineS shape comparison reference: .local/research/v9.3.0_nines_compressor.json (v9.3.0 pre-split baseline)
- External tools (S-7): NineS https://github.com/YoRHa-Agents/NineS
```

**API/CLI surface:** zero changes. Pure-audit direction.

**Documentation deliverable:**
- 1-line CHANGELOG entry: "Audit: NineS deep-analysis run on `src/devolaflow/compressor/` (post-split health snapshot since v9.3.0); see `.local/research/v11.0.X_compressor_nines.md`"
- W-18 ghost-audit refresh: NOT REQUIRED (no NEW symbols introduced; only research artifacts added)
- W-19 cycle-archive: at v11.0.0 cycle close, the new `v11.0.X_compressor_nines.{json,md}` files get archived to `docs/cycle-archive/v11.0.0/nines/` per W-19

## §3 — small_project_eval

**Synthetic test bed:** synthetic_small_repo (per `v11.0.0_evaluation_methodology.md` §2)

**Operations exercised:** `init` exercises the compressor's dispatch payload generation path
(every dispatch invokes `assert_dispatch_layout` from `compressor/layout.py` per A-2.1 enforcement);
`feature` exercises a single-round dispatch which exercises selector context compression in
`compressor/transforms.py`. Small repos exercise compressor at PRECISELY the same depth as large
repos (the compressor is invoked once per dispatch regardless of repo size).

**Metric collection:** §4.3 code-quality bucket — radon CC + raw + maintainability index;
§4.5 observability bucket — count of NineS warning-class findings (the audit's primary output).

**Expected delta (before → after):**

D-Q-4 is an AUDIT direction; "before/after" is interpreted as **before-audit / after-audit-knowledge**:

| Metric | Before D-Q-4 | After D-Q-4 | Δ | Direction |
|---|---:|---:|---:|:---:|
| Known-NineS-warning count for `compressor/` | UNKNOWN (no analysis since v9.3.0) | <documented count from snapshot> | knowledge gain | improve (visibility) |
| Last-NineS-snapshot age for `compressor/` | 1.3 years (v9.3.0 → v10.3.0) | 0 days (fresh) | -1.3 yr | improve |
| Coverage in `v10.2.2_nines.md` §1 surface | 3 packages (excludes compressor) | 4 packages (includes compressor) | +1 | improve |

**Pass criterion:** the NineS analysis runs to completion (or manual fallback completes); the JSON
+ markdown synthesis files are committed; any high-CC findings (CC > 10) are enumerated in §5 of
the synthesis with PV-implementation candidate notes (analogous to `v10.2.2_nines.md` §5).

**If no warning-class findings emerge** (best case — compressor/ is genuinely healthy):
verdict = **PASS** still; the audit confirmed the post-split decomposition is structurally sound;
this is itself a valuable signal for v11.0.0 evaluation (W-3 SI-3 §3.2 architecture-rationality
input).

**If warning-class findings emerge** (likely given the 2,198-LOC `transforms.py` size):
verdict = **PASS for the audit itself**; subsequent CC reductions become **micro-PVs in v11.0.x**
analogous to the D-Q-1 7-row series. The audit itself is the v11.0.0 deliverable; the cleanups are
v11.0.1+ deliverables.

**Verdict if pass:** PASS small tier (the compressor is exercised on small repos identically to
large; the audit produces actionable visibility either way).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline)

**Metric collection:** §4.3 code-quality bucket + §4.5 observability bucket.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline (v10.3.0) | Post-patch (v11.0.X) | Δ | Direction |
|---|---:|---:|---:|:---:|
| NineS-analyzed packages count | 3 (`si_chip_bridge`, `plugins`, `lifecycle`) | 4 (+ `compressor`) | +1 | improve |
| Last-NineS-snapshot age for `compressor/` | 547 days (since v9.3.0) | 0 days | -547 d | improve |
| Documented complexity warnings for `compressor/` | 0 (because not analyzed; UNKNOWN in reality) | <N> (documented in synthesis) | knowledge gain | improve |
| `transforms.py` LOC | 2,198 (largest in `src/devolaflow/`) | 2,198 (audit only; no source change) | 0 | neutral |
| Cycle-archive completeness (per W-19) | partial (3/4 packages NineS-tracked) | full (4/4 packages NineS-tracked) | improve | improve |

**Pass criterion:** the NineS run completes (or manual fallback completes); the synthesis md file
is authored to the `v10.2.2_nines.md` schema; any actionable findings are flagged in §5 with PV-
implementation candidate notes.

**Side-effect check (MUST NOT regress):**
- A-2 frozen prefix invariant: the audit READS `compressor/layout.py` source; it does NOT modify the file. `tests/test_layout_invariant_multi_baseline.py` UNTOUCHED.
- pytest 100% green (audit doesn't touch tests)
- pytest wall-clock unchanged
- coverage unchanged (no source delta)

**Verdict if pass:** PASS large tier.

## §5 — benefit_metrics

| # | Metric | Bucket | Before (v10.3.0) | After (v11.0.X) | Δ | Notes |
|:--:|---|---|---:|---:|---:|---|
| 1 | NineS-analyzed package count for `src/devolaflow/` | observability (§4.5) + code-quality (§4.3) | 3 of ~20 packages | 4 of ~20 packages | +1 (+33% of analyzed; +5% of total) | Closes the post-v9.3.0-split coverage gap for the LARGEST file in the tree |
| 2 | Last-NineS-snapshot age for `compressor/` | observability (§4.5) | 547 days (v9.3.0 → v10.3.0) | 0 days | -547 d (-100%) | Fresh data for v11.0.0 W-3 SI-3 evaluation input |
| 3 | Documented complexity warnings for `compressor/` (knowledge metric) | code-quality (§4.3) | 0 (UNKNOWN, not analyzed) | <N> (documented; 0 ≤ N ≤ ~10 estimated based on transforms.py size) | knowledge gain | Either confirms healthy decomposition (N=0, structural validation) OR enumerates actionable PV candidates (N>0, refactor leverage) |
| 4 | Cycle-archive completeness (per W-19 cycle-end committed artifact) | doc-health (§4.4) | 3/4 packages NineS-tracked in `docs/cycle-archive/v11.0.0/nines/` | 4/4 | +1/4 (+25%) | Future-cycle SI-1 planning gates have full per-package NineS history to draw on |
| 5 | `transforms.py` known-CC-floor on its 40+ functions | code-quality (§4.3) | UNKNOWN (no per-function CC data since v9.3.0 pre-split) | radon-rated B or A on every function (or actionable list of B+/C+ functions) | knowledge gain | Direct input to v11.0.x decision: "is `transforms.py` due for a sub-decomposition (S/M effort) or healthy as-is?" |

All 5 metrics are §4.3 / §4.4 / §4.5 buckets per `v11.0.0_evaluation_methodology.md`; ZERO use
EvoBench scores (G-1 internal-value gate ✓).

## §6 — admission_verdict

**PASS** — the audit ITSELF is the deliverable; it produces clear small + large project benefit
(closes a 547-day NineS-coverage gap on the largest file in the tree; provides architecture-
rationality input to W-3 SI-3 evaluation; potentially surfaces actionable refactor candidates for
v11.0.x micro-PVs analogous to D-Q-1's 7-row series).

The verdict for D-Q-4 = **PASS for the analysis itself**; any subsequent CC reductions become
**micro-PVs in v11.0.x** (similar in spirit to how the v10.2.2 NineS report spawned the v10.2.3
PV-04 + v10.2.4 PV-05 closures + the carry-forward 7 that became D-Q-1 in this PDS).

**Strict separation:** D-Q-4 admits the AUDIT to v11.0.0; any actionable refactor candidates
surfaced by the audit are NOT in v11.0.0 scope by virtue of D-Q-4's PDS — they require a separate
PDS at v11.0.x time (analogous to D-Q-1's structure). This separation honors W-1 / SI-1 (no
implementation without documented gap analysis).

**G-7 compatibility ✓:** zero source-code changes; pure-audit research artifacts.
**G-3 zero-deps ✓:** NineS is preferred but NOT required; manual radon fallback documented.
**G-1 internal value ✓:** code-quality §4.3 + observability §4.5 + doc-health §4.4 metrics; zero EvoBench.
**G-9 docs completeness ✓:** CHANGELOG entry + cycle-archive (per W-19) + the synthesis md itself IS the documentation.

## §7 — effort_estimate

**S** — ≤0.5 PV. Breakdown:
- Run NineS deep-analysis command (or manual radon fallback): ~15 min (mostly tool runtime)
- Author the markdown synthesis file at `.local/research/v11.0.X_compressor_nines.md`
  (mirroring `v10.2.2_nines.md` schema; ~80-150 LOC): ~90 min
- Cross-reference findings to existing test surfaces (`tests/test_compressor.py`,
  `tests/test_dispatch_layout.py`, etc.) to support PV-candidate § notes: ~30 min
- Run pre-commit gate sequence (W-9 7 steps; verify no source delta): ~15 min
- CHANGELOG entry: ~10 min

Total: ~2.5h work / 0.4 PV. W-17 test budget impact: **+0 NEW test functions** (audit-only;
zero NEW source code = zero NEW tests required by S-3 / S-4 / W-18).

## §8 — dependencies

**Standalone — zero internal dependencies.** Could land as the FIRST direction in v11.0.0 PV-01
(audit-first per W-1 SI-1 spirit) OR as the last direction in v11.0.0 cycle close (audit-as-final-
deliverable per W-19 cycle-archive timing). Neither D-Q-1 nor D-Q-2 nor D-Q-3 depend on D-Q-4 or
vice versa.

External: **soft dependency on NineS availability**. If NineS is unreachable at PV time, the
manual radon fallback (per W-2) is fully sufficient — the markdown synthesis schema can be
populated from radon output (§1 metrics, §2 high-CC findings, §3 keypoints from raw + maintainability
index). The manual fallback MUST be explicitly noted in the synthesis file's preamble per W-2.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | NineS unavailable at PV implementation time (network / repo / API drift) | **minor** | Manual radon fallback fully covers §1 + §2 + §4; agent-impact surface is degenerate-empty for compressor (per `v10.2.2_nines.md` §3) so its absence is a non-issue. Synthesis preamble notes "manual analysis per W-2 fallback" if so. |
| 2 | The audit surfaces a HIGH count of warning-class findings (>5) — risk that the v11.0.x cycle gets pulled into a multi-PV refactor scope-creep | **major** | D-Q-4 PDS strictly separates audit (this PDS) from refactor (separate per-finding PDSes at v11.0.x time, analogous to D-Q-1's 7-row series). The v11.0.0 cycle plan composer (L0) decides whether to admit any compressor refactor PVs based on the audit + cycle budget; D-Q-4 itself doesn't pre-commit any refactor effort. |
| 3 | The audit surfaces ZERO findings (compressor is genuinely healthy) — risk that operators interpret "spent 0.4 PV on a no-op audit" | **minor** | Even a zero-finding result is valuable signal: it confirms the v9.3.0 PV-04 split was structurally sound and provides positive input to W-3 SI-3 §3.2 architecture-rationality scoring at v11.0.0 cycle close. The synthesis file itself (with the §1 metrics + §3 keypoints) is the deliverable regardless of finding count. |

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: standard
