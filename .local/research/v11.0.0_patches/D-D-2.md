# D-D-2 — Long-Reference "Actually-Used" Evidence Audit (Patch Design Specification)

> **Status:** PDS authored by L3 Task Agent (Wave 3 D-D)
> **Author:** L3 (composer-2-fast)
> **Date:** 2026-05-04
> **Cycle:** v11.0.0 SI-1 planning
> **Source direction:** `.local/research/v10_internal_optimization_directions.md` §3.7 D-D-2
> **PDS schema:** `v11.0.0_decomposition_plan.md` §3
> **Owned files:** `.local/research/v11.0.0_patches/D-D-2.md`
> **External tools (S-7):** DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`

## §1 — Current state (50-150 words; verbatim file path evidence)

The three longest references collectively encode the workflow's heavy-coordination machinery:

- `workflow-system/agent/references/agent-workspace.md` (**747 lines**) — §3 Lifecycle FSM (lines 153-216 — `PROPOSED → IN_PROGRESS → VERIFYING → ARCHIVED` state machine); §6 Handoff Protocol (lines 448-505 — append-only envelope semantics, S-9 enforcement)
- `workflow-system/agent/references/execution-protocol.md` (**818 lines**) — §2.4 (referenced from SKILL.md line 384) is the resume-after-pause protocol surface
- `workflow-system/agent/references/decomposition-gate.md` (**590 lines**) — convergence loop + reinforcement spec

**Empirical envelope evidence (gathered from `.local/.agent/handoff/` at v10.3.0 baseline):**

```
$ ls -la .local/.agent/handoff/
-rw-r--r-- 786 May  1 21:13 L0__L1__v9.2.1-self-update-validation__0001.yaml
-rw-r--r-- 8630 May  3 05:52 L0__operator__v10.2.0-cycle-close__0001.yaml
-rw-r--r-- 810 May  1 21:13 L1__L0__v9.2.1-self-update-validation__0002.yaml
README.md
```

**3 actual handoff envelope files spanning 2 distinct change-ids** (`v9.2.1-self-update-validation` with a 2-envelope L0↔L1 roundtrip; `v10.2.0-cycle-close` with a 1-envelope L0→operator notification). `.local/.agent/archive/` contains **1 archived change** (`2026-05-01-v9.2.1-self-update-validation`). `.local/.agent/active/` contains **0 active changes** (only README).

The handoff envelope mechanism shipped at v8.3.0 (per `.local/research/v8.3.0_design.md` cited from `agent-workspace.md` lines 98 + 155); v8.3.0 → v10.3.0 spans **~11 minor cycles** (v8.3.x, v8.4.x, v9.0.x, v9.1.x, v9.2.x, v9.3.x, v9.4.x, v9.5.x, v9.6.x, v9.7.x, v10.0.x, v10.1.x, v10.2.x, v10.3.0) and **~50+ PVs** total. **Empirical envelope creation rate ≈ 3 envelopes / 50+ PVs ≈ 6%.**

## §2 — Patch design (algorithm + files-touched + API/CLI surface)

**Deliverable:** `scripts/audit_handoff_envelope_usage.py` — a NEW audit script that quantifies the long-reference machinery's empirical use rate, plus a one-line annotation in SKILL.md and the long references that flags them as "complex-only" surfaces.

**Algorithm:**
1. Walk `.local/.agent/handoff/*.yaml` + `.local/.agent/archive/*/handoff_chain.yaml` (when present).
2. Parse each filename per `<from>__<to>__<change-id>__<seq>.yaml` (per `references/agent-workspace.md` §6.1 lines 455-465); extract: `(from_layer, to_layer, change_id, seq, mtime)`.
3. Walk `.local/.agent/archive/*/` directories; extract change-id + archive date.
4. Cross-reference against `git log --all --since='v8.3.0'` to derive PV count denominator.
5. Emit markdown report at `.local/research/v11.0.X_handoff_usage.md` with: (a) raw counts (envelopes / changes / archives), (b) per-cycle creation rate (`<cycle>: <envelopes>/<PV-count>`), (c) inbox-fill ratio (`% of changes that received ≥ 1 envelope`), (d) recommended SKILL.md annotation snippet.

**Files-touched (≤ 6 owned):**
- `scripts/audit_handoff_envelope_usage.py` (NEW; ~120 LOC)
- `tests/test_audit_handoff_envelope_usage.py` (NEW; ~70 LOC, 5-7 test functions)
- `Makefile` (1-line ADDITION: `audit-handoff` target)
- `workflow-system/agent/SKILL.md` (1-line ADDITION near line 375 in the Reference Navigation Guide table — annotate `agent-workspace.md` row "Load When" column with `(Complex/change-driven only — see audit metrics)`)
- `CHANGELOG.md` (entry under v11.0.X)
- `tests/test_no_ghost_features.py` (W-18 lint refresh)

**API surface:** Single CLI: `python scripts/audit_handoff_envelope_usage.py [--repo-root PATH] [--since-version VERSION]`. Pure stdlib + yaml — zero new dependencies.

**P6 / A-2 invariance:** Audit-only + 1-line SKILL annotation. The SKILL line addition stays well below the < 500 line ceiling (v10.3.0 SKILL.md = 460 lines per `wc -l`; +1 = 461). The annotation is text-only and DOES NOT change frontmatter or Reference Navigation Guide structure — preserves cache prefix.

## §3 — Small project evaluation

**Synthetic test bed:** `synthetic_small_repo/` (per `v11.0.0_evaluation_methodology.md` §2).

**Operations exercised:** `init` (small repo with `devola-init local --mode=core` scaffolds `.local/.agent/active/` + `handoff/` + `archive/` per the canonical 8-path manifest in SKILL.md lines 142-154); the audit then reports "0 envelopes / 0 changes / 0 archives" — the expected NULL state for a fresh small repo.

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4:
- **Reference doc utilization** — for `agent-workspace.md` specifically, % of dispatches that load it
- **Reference avg line count** — `wc -l` (no change; audit doesn't shrink the ref)

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Operator awareness "agent-workspace.md is opt-in" | implicit | explicit (SKILL annotation) | +1 signal | improve |
| Time to identify "do I need handoff envelopes for this small task?" | N/A (must read 747-line ref) | < 5 s (read SKILL annotation) | -∞ | improve |
| Misuse rate (operator scaffolds change folder for trivial task) | unknown | observable via STATUS.yaml count | new metric | improve |

**Pass criterion:** SKILL annotation appears in the navigation table; audit script returns "0 envelopes" cleanly on the empty small repo.

**If no improvement on small project:** N/A — the small repo benefit is the explicit "you don't need this for trivial work" signal, which is positive even when the small repo never engages the machinery. The audit produces a green "0/0" report which IS the small-repo evidence.

## §4 — Large project evaluation

**Test bed:** DevolaFlow self at v10.3.0 baseline.

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4 + §4.2:
- Empirical envelope creation count (raw): **3** (verbatim from §1 ls)
- Distinct change-ids: **2** (`v9.2.1-self-update-validation`, `v10.2.0-cycle-close`)
- Archived changes: **1** (`2026-05-01-v9.2.1-self-update-validation`)
- PV denominator (v8.3.0 → v10.3.0): **~50** (5 v9.X cycles × 6 PVs avg + 6 v10.X cycles × 6 PVs avg − overlap = ~50)

**Expected delta (v10.3.0 baseline → post-patch knowledge state):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Empirical envelope-rate visibility | unknown | **3 envelopes / ~50 PV ≈ 6%** | +empirical signal | improve |
| `agent-workspace.md` Tier-2 ranking in SKILL Reference Navigation Guide | implicit (line 375) | explicit "(complex/change-driven only)" annotation | +1 signal | improve |
| Operator decision time on "engage workspace?" | scan 747-line ref + SKILL ~Workspace Engagement (15 lines) | scan annotation row + complexity table (3 lines) | -90% | improve |
| `agent-workspace.md` line count | 747 | 747 (unchanged — audit, not refactor) | 0 | byte-stable |
| Test count delta | N/A | +5-7 (audit script tests) | +5-7 | within W-17 cap |

**Pass criterion:** Audit report shows the **6% creation rate** verbatim AND identifies a < 30% threshold below which the reference qualifies for the "complex-only" annotation.

**Side-effect check:** No selector behavior change; `agent-workspace.md` itself unchanged (only one annotation in the SKILL navigation guide).

## §5 — Benefit metrics (≥ 3 quantitative DF-internal metrics)

| # | Metric | Baseline (v10.3.0) | Post-patch | Δ |
|---|---|---:|---:|---:|
| 1 | Handoff envelope count (cycle range v8.3.0 → v10.3.0) | unknown | **3** (verbatim) | +visibility |
| 2 | Distinct change-ids using envelopes | unknown | **2** | +visibility |
| 3 | Archived change count | unknown | **1** | +visibility |
| 4 | Envelope creation rate (envelopes / PV) | unknown | **3 / ~50 ≈ 6%** | +empirical signal |
| 5 | `change_context` dispatch field non-empty rate (canonical position 16; per A-2.2) | unknown | inferable from STATUS.yaml count = ~2/50 ≈ **4%** | +empirical signal |
| 6 | Operator time to identify "complex-only" reference | scan 747 LOC | scan 1 SKILL annotation row | -99.9% |
| 7 | SKILL.md line count delta | 460 | 461 | +1 (well below 500 ceiling) |

**Cross-tier benefit summary:** Both the small-repo "you don't need this" signal and the large-repo "we built it but barely use it" data are improvements. The action this enables (a future cycle deciding to either MARKET handoff envelopes harder OR DOWNGRADE the reference's Tier-2 status) is OUT-OF-SCOPE for v11.0.0 — the patch only delivers the data + annotation.

## §6 — Admission verdict

**Verdict:** **PASS**

**Rationale:** Pure observability + 1-line documentation annotation. Both tiers benefit identically — the audit is a no-op on the small repo (cleanly reports zeros, which IS the signal "you don't need this here") and produces actionable data on the large repo (6% creation rate is below most reasonable utility thresholds; the long-reference machinery is empirically over-built relative to actual use). G-1 internal-value (4 quantitative metrics in §5), G-2 both-tier (small = "skip this", large = "we have data"), G-3 zero external deps, G-4 cycle-budget (+5-7 tests), G-5 Soul-freeze (no S-11), G-6 cache-prefix (1-line SKILL annotation in non-frontmatter / non-canonical-order zone), G-7 compatibility (additive script + 1-line SKILL annotation), G-8 coverage (5-7 unit tests target 90%+ on ~120 LOC), G-9 docs (CHANGELOG + W-18 + SKILL annotation per §2). All gates green.

## §7 — Effort estimate

**S** (≤ 0.5 PV).

Per source §3.7 D-D-2 estimate; confirmed by §2 file-touched count (6 owned files, ~190 LOC total). Implementation breakdown: ~1.5 hr filename parser + glob walker + ~1 hr tests + ~30 min SKILL annotation review + ~30 min CHANGELOG / W-18 lint = ~3.5 hr.

## §8 — Dependencies

**none** — standalone audit. Adjacent direction D-D-1 (reference utilization audit, also Wave 3) is independent: D-D-1 audits selector-side `extra_context` declarations; D-D-2 audits filesystem-side envelope creation. Together they form a 2-axis "is this reference actually used?" signal but neither blocks the other.

## §9 — Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | The 6% creation rate ignores envelopes that may have lived in `.local/.agent/handoff/` and been deleted (S-9 says append-only, but pre-v8.2.4 there was no enforcement — early v8.3.x envelopes may have been wiped during repo-init experiments). | minor | Script's report explicitly notes "this measurement is the lower bound — pre-v8.2.4 envelopes may have been deleted before S-9 enforcement". Acceptable because the measurement floor of 3 is itself dramatically below any reasonable utility threshold (e.g. 1 per PV). |
| 2 | An operator reading "6% creation rate" might propose deprecating the 747-line reference entirely — but `agent-workspace.md` also serves as the spec for `change-driven` workflow, source-of-truth specs (A-4 / M-004), and the 4 REPORT.md surfaces. Deprecation would orphan working machinery. | major | Script output INCLUDES the annotation text "(Complex/change-driven only — see audit metrics)" which is explicitly NOT a deprecation tag. The patch ships the data + annotation only; deprecation/restructuring is out-of-scope and would require its own SI-1 gap analysis. The SKILL annotation language was chosen specifically to avoid the "low usage = remove" misread. |
| 3 | Small-repo synthesis test may surface "0 envelopes" but produce a confusing report layout if the script doesn't gracefully handle the empty-archive case. | minor | Tests in `tests/test_audit_handoff_envelope_usage.py` MUST cover: (a) empty `.local/.agent/handoff/`, (b) empty `.local/.agent/archive/`, (c) `.local/.agent/` missing entirely. All three return "0 envelopes / 0 changes" with a non-error exit code. |

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: core
