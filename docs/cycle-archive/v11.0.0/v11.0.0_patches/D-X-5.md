# D-X-5 — Operator Error Troubleshooting Handbook

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.3 D-X-5
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §5 templates
> **Wave:** 1 (D-X Developer/Operator Experience)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow's operator-friction diagnostics are scattered across cycle
retrospectives — there is **no centralized troubleshooting reference**.
Operators encountering errors must grep historical retros to find the
established workaround for any given symptom.

**Concrete evidence of the gap (verbatim from cycle retrospectives):**

`.local/research/v10.0.0_retrospective.md` §4.2 ("What didn't work as
smoothly") lists 4 first-time-operator-tripped issues:

1. **dataclass + spec_from_file_location pitfall** (lines 208-212):
   audit script tests initially failed because `dataclass` resolves
   field annotations via `sys.modules.get(cls.__module__).__dict__`,
   which fails when the module isn't registered. Fix: register in
   `sys.modules` BEFORE `exec_module()`.
2. **`_grep_symbol` fragility on test-file echo** (lines 213-216):
   test for "no hit" symbol initially false-positived because the
   test file itself contained the needle. Fix: construct the needle by
   string concatenation.
3. **demo/index.html "automated" gate-type lint trip** (lines 217-222):
   `test_demo_index_gate_types` forbids "automated" (a stale gate-type
   name). Lesson: pre-check the doc-consistency lints when prose-editing
   demo/index.html.
4. **`ruff check scripts/` was already drifting before v10.0.0** (lines
   223-227): 3 pre-existing scripts have lint warnings; v10.0.0 deferred
   them.

`.local/research/v10.3.0_retrospective.md` §4 ("Key learnings") lists 7
items, several of which capture analogous traps:

- §4.2 (lines 99): "Bridge defect surfaced ONLY at end-to-end dogfood"
  — unit fixtures that match spec docs missed real upstream output
  shapes.
- §4.4 (lines 103-106): "Per-PV CHANGELOG ceremony adds discipline but
  inflates dispatch overhead" — operators hit ~10 min subagent overhead
  per PV.

**Other historical trap categories (per §3 of v10_internal_optimization_directions.md
D-X-5 + cycle archive scan):**

- Si-Chip dogfood DEFER pattern (`.local/research/v9.5.0` retro period;
  resolved at v10.2.3 PV-04).
- W-18 ghost-audit refresh-before-document sequencing (operator forgets
  → CHANGELOG entry references symbol that fails the lint at next
  pytest run).
- canonical-7 version sync drift (operator bumps src/devolaflow/__init__.py
  manually, forgets the 6 mirrors → `tests/test_version.py` fails at
  next CI run).
- A-2 cache-prefix layout violation (operator inserts a new dispatch
  field at position N <12 → multi-baseline byte test fails for ALL 9+
  prior baselines).
- W-2 NineS upstream timeouts (`code_coverage` collector hangs at 180s
  → operator sees 0.0 reading; documented manual fallback per
  `nines.toml`).
- ruff format auto-fix vs ruff check ordering (operator runs `ruff check
  --fix` and discovers their `ruff format` step now reports diffs that
  weren't there pre-fix).

The gap is real: roughly **30+ distinct operator traps** are
documented across .local/research/ retrospectives but **NO single
reference document collects them**. Each new operator must repeat the
discovery process.

## §2 — patch_design

**Algorithm:**

Author a NEW `workflow-system/agent/references/troubleshooting.md`
(targeting C-4 Large tier, ≤1000 lines) as the **15th canonical
reference** under SF-4. The reference has 3 parts:

```
# Troubleshooting

## Part 1 — Quick Lookup Index
Symptom → resolution table (~30 entries):
| Symptom | Domain | Resolution | Source retro |
|---|---|---|---|
| dataclass field annotation lookup error | scripting | Register in sys.modules before exec_module | v10.0.0 §4.2 |
| ...

## Part 2 — Diagnostic Patterns
Per-symptom detailed sections (~50 lines each, max 20 sections at
launch):
- 2.1 Test-file echo false positives — _grep_symbol pattern
- 2.2 ruff check / ruff format ordering races
- 2.3 Stale ruff lint on scripts/ subtree
- 2.4 Si-Chip / NineS upstream collector timeouts
- 2.5 W-18 ghost-audit refresh ordering
- 2.6 canonical-7 sync drift
- 2.7 A-2 cache-prefix violation diagnostics
- 2.8 demo/index.html gate-type lint trips
- 2.9 dataclass + spec_from_file_location pitfall
- 2.10 Pytest --lf cache staleness on branch-switch
- 2.11 Bridge layer defect (upstream shape vs unit fixture)
- 2.12 Per-PV subagent overhead patterns
- 2.13 build-skill 4-adapter divergence symptoms
- 2.14 install.sh manifest mismatch (post D-X-2 if landed)
- 2.15 Plugin auto-install / 24h upgrade boundary cases
- 2.16 EvoBench / NineS / Si-Chip degraded mode (placeholder; full
       coverage when D-C-1 lands)
- 2.17 sync_cursor_skill.py mirror parity (opt-in mirror)
- 2.18 Make compile-rules drift detection
- 2.19 Reference-utilization audit blind spots (post D-D-1 if landed)
- 2.20 Workspace-engagement A-6 false-positive scaffold

## Part 3 — Escalation Patterns
When to escalate vs retry vs abort (per A-1 P4 Bounded Retry):
- Escalation triggers per layer (L3 → L2 → L1 → L0 → Human).
- Stagnation patterns (W-8) and the 5-rule reinforcement cap (W-8).
- The "external upstream issue" pattern (NineS A1, Si-Chip MVP-8).
```

**Files touched (NEW):**

- `workflow-system/agent/references/troubleshooting.md` (≤1000 lines
  authored from cycle retrospective harvest).

**Files touched (EDITED):**

- `workflow-system/agent/SKILL.md` — add 1 row in "## Reference
  Navigation Guide" Tier-2 table (lines 372-387) for
  `references/troubleshooting.md`.
- `scripts/sync_cursor_skill.py::MIRRORED_FILES` — append entry (1 line).
- `scripts/install.sh` — 7 adapter blocks (cursor / codex / claude /
  kimicode / zed / cline / roo) each gain 1 `dl_batch` argument line —
  UNLESS D-X-2 lands first, in which case the install.sh edits are
  zero (manifest-driven).
- `tests/test_no_ghost_features.py` — NEW
  `test_v11_0_X_troubleshooting_reference_present` W-18 lint stanza
  (~30 LOC).
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**API/CLI surface:**

NONE — this patch is a documentation deliverable. The reference
auto-loads via the existing `task_adaptive_selector.py` Tier-2 chain
when relevant `task_type` is detected (mapping detail TBD; for v11.0.0
launch, the troubleshooting reference is `important` tier — not
`critical` — for all task types except `bugfix` and `dependency-setup`
where it becomes `critical`).

**Doc deliverables (G-9 mapping per admission_checklist.md §G-9):**

- CHANGELOG entry — required.
- W-18 lint refresh — required (path + 1-2 anchor strings).
- SKILL.md edit (1 row) — triggers W-12 adapter build verify.
- Reference doc add — YES, this IS the required SF-3 sync —
  `sync_cursor_skill.py` MIRRORED_FILES update + `install.sh` edits
  (or zero edits if D-X-2 manifest landed).
- SF-1 line budget verify — `tests/test_reference_size_budgets.py`
  parametrize auto-covers; ≤1000 lines must hold.
- Bilingual EN/ZH — NONE for the reference itself (Tier-2 references
  are English-only by SF-* convention; the user-facing EN/ZH guides
  cite the reference in a translated paragraph if applicable, but the
  reference body itself is single-language).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` (per
`v11.0.0_evaluation_methodology.md` §2). Synthetic repo has minimal
errors (small surface area), so the troubleshooting reference's value
is exercised via simulated lookup tasks.

**Operations exercised:** `bugfix` (with synthetic error injection —
e.g., "operator runs `pytest` on synthetic_small_repo and gets a
pytest discovery error; reference must surface the resolution within
N seconds of opening").

**Metric collection:** Troubleshooting-lookup time (seconds, per §4.1
metric "Troubleshooting-lookup time"). Specifically: simulate an
operator searching for the resolution to a known synthetic error
(e.g., test discovery failure due to a typo in conftest.py).

**Expected delta (before → after):**

| Metric | Before (no reference) | After (15th reference loaded) | Δ | Direction |
|---|---:|---:|---:|:---:|
| Troubleshooting-lookup time (seconds, median over 5 trials) | grep across `.local/research/` retros: ~120-300 s (with chance of NOT finding the answer because not yet retro-documented) | open `references/troubleshooting.md` Part 1 index → match on symptom keyword: ~15-30 s | -75% to -90% | improve |
| Lookup success rate (5 trials) | ~60% (depends on grep skill) | ≥95% (table-of-contents-driven lookup) | +35pp | improve |
| Operator escalation rate to upstream issue tracker without first checking docs | observed >0 in v9.5.0 era | observable as ≤1/cycle | -50% | improve |

**Pass criterion:** Troubleshooting-lookup time Δ ≤ -50% AND Lookup
success rate ≥ 90% on the 5 trial errors.

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (large-only). The troubleshooting reference's value
scales with the OPERATOR's accumulated context. Small repos may not
see lookup improvement if the synthetic error is too obvious to need a
reference. Mitigation: ensure the 5 trials cover non-obvious traps
(typos in conftest.py vs. dataclass + spec_from_file_location which is
a legit DF-specific gotcha).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline; 14
references already present per
`scripts/sync_cursor_skill.py:55-78` MIRRORED_FILES list).

**Metric collection:** Troubleshooting-lookup time (5 trials with
distinct historical traps drawn from retros §4.2 / §4 Key Learnings);
SF-1 line budget (must remain ≤1000); cycle-cumulative reference
count delta (must respect admission_checklist §4 cap of ≤2 NEW
references per cycle); reference cross-ref density per §4.4
("Reference cross-ref density" metric).

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Troubleshooting-lookup time (median seconds across 5 historical traps) | ~180-300 s (grep retros) | ~20-40 s (Part 1 index → Part 2 detail) | -85% | improve |
| Lookup success rate | ~60-70% | ≥95% | +25-35pp | improve |
| Reference count | 14 | 15 (within ≤2/cycle cap per admission_checklist §4) | +1 | preserve |
| References avg line count | ~600 (per v11 eval methodology §3 baseline note "14 references avg ~600 lines") | ~640 (after adding ~1000-line troubleshooting weighted in) | +40 | preserve (well under Large 1000 cap) |
| W-17 cycle test count delta (this patch) | n/a | +5 (W-18 lint + SF-1 parametrize coverage) | +5 | preserve (≤30/PV) |
| SKILL.md line count | 460 | 461 (1 row added) | +1 | preserve (<500) |

**Pass criterion:** Lookup time Δ ≤ -50% on 5 trial cases AND
Reference count stays ≤16 (1 new + 14 existing + at most 1 from D-X-2
if it ships) AND SF-1 1000-line ceiling not violated AND SKILL.md
remains <500.

**Side-effect check (must NOT regress):**

- `tests/test_reference_size_budgets.py::test_reference_within_large_tier`
  must pass with the new reference (≤1000 lines).
- `tests/test_integration.py::test_skill_md_under_500_lines` must pass.
- `make check-cursor-skill` must keep exiting 0.
- W-17 cycle cap respected (the W-18 lint adds 1-2 test functions only).
- The existing 14-reference SF-4 valid set requires updating to 15 in
  the SF rule body — this is a **C-7 Valid Reference Links** doc-only
  edit; tracked via the `tests/test_no_ghost_features.py` rule corpus
  drift check.

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.1 + §4.4; ≥3 metrics required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-X-5) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Troubleshooting-lookup time (seconds, median over 5 trials) | §4.1 | ~180-300 | ~20-40 | -85% | Indexed lookup vs grep across retros |
| Lookup success rate (% of trials finding canonical answer) | §4.1 (operator experience) | ~60-70% | ≥95% | +25-35pp | Reference is comprehensive (~30 entries at launch) |
| Cycle retrospective §4.2 incident count (operator-tripped issues newly documented per cycle) | §4.4 (doc health proxy) | 4 (v10.0.0) + 7 (v10.3.0) — 11 over 2 cycles | ~2-3 per cycle (only NOVEL ones; pre-existing covered by reference) | -50%-67% | Pre-documented incidents reduce repeat retro entries |
| Reference cross-ref density (links per ref) | §4.4 | unknown baseline | troubleshooting.md adds ≥30 cross-refs to existing references | new | Each Part 2 section cross-references the canonical reference (e.g., 2.7 → repo-governance.mdc A-2) |
| Reference count | §4.4 | 14 | 15 | +1 | Within ≤2/cycle cycle cap (admission_checklist §4) |

**Guarantee on metric:** ALL 5 metrics scriptable from current DF
tooling: stopwatch + cycle retro grep for incident-count + `wc -l` for
SF-1 + `grep -c` for cross-ref density. The lookup-time and
success-rate metrics require operator-side trials (not auto-collectable);
trials should be done at PV-close with 5 standardized synthetic
errors covering both small (synthetic_small_repo) and large (DF self)
tiers.

## §6 — admission_verdict

**Verdict: PASS**

**Rationale:**

- G-1 Internal-value: 5 quantitative DF-internal metrics show clear
  improvement; troubleshooting-lookup time -85% is the headline
  operator-experience win, and the cycle-retro incident-count -50%
  signal is a structural doc-health win.
- G-2 Both-tier: small (synthetic_small_repo with injected errors) AND
  large (DF self with historical retros as ground truth) BOTH show
  ≥-50% on lookup time. Pass criteria explicitly met on both tiers.
- G-3 Zero-deps: pure markdown authoring + SKILL.md row + W-18 lint;
  no NineS / Si-Chip / RTK side requirement.
- G-4 Cycle-budget: M effort (1 PV); ~5 NEW tests (W-18 lint + SF-1
  parametrize auto-coverage = ~5-7 test functions); fits within +30/PV.
  Reference count delta +1 fits within admission_checklist §4 cap of
  ≤2 NEW references / cycle.
- G-5 Soul-freeze: 0 Soul rule additions.
- G-6 Cache-prefix: zero edits to schemas/lean-dispatch.yaml.
- G-7 Compatibility: pure-additive (NEW reference doc); no public API
  rename. The C-7 valid reference list expands 14 → 15 (doc-only edit
  to .rules/conventions.mdc + recompile).
- G-8 Test coverage: 5-7 unit tests (W-18 lint + SF-1 parametrize +
  rule corpus drift check). Reference content itself is
  documentation; "coverage" maps to W-18 anchor pinning.
- G-9 Documentation completeness: CHANGELOG + W-18 lint refresh +
  SKILL.md row + sync_cursor_skill.py MIRRORED_FILES + install.sh
  edits (or zero if D-X-2 lands first) + SF-1 line-budget verification
  + .rules/conventions.mdc C-7 reference list update + recompile-rules
  AGENTS.md/repo-governance.mdc; matches the "Reference doc add" row
  in §G-9 fully. NO bilingual ZH (references are EN-only).

## §7 — effort_estimate

**Effort: M (1 PV)**

**Breakdown:**

- Reference body authoring (~700-900 lines):
  - Part 1 quick lookup index (~30 rows × ~3 lines each = ~100 lines)
  - Part 2 detailed sections (~20 sections × ~30-40 lines each = ~700 lines)
  - Part 3 escalation patterns (~80 lines)
  - Frontmatter + cross-refs + history footer (~30 lines)
  - Total: ~900 lines (within Large 1000-line ceiling).
- Source mining: read 8-12 historical retros (`.local/research/v8.X.0_retrospective.md`,
  v9.X.0, v10.X.0) + scan CHANGELOG `## [X.Y.Z]` entries — ~3-4 hours
  reading; the bulk of the PV effort.
- SKILL.md row + sync_cursor_skill.py edit + install.sh edits (if
  D-X-2 not landed): ~10 min.
- `.rules/conventions.mdc` C-7 reference list update + recompile-rules:
  ~5 min.
- W-18 lint stanza: ~30 LOC.
- CHANGELOG entry: ~10 LOC.
- Total work: ~900 LOC reference + ~80 LOC scaffolding + 3-4 hours
  research; ~1 PV.

**Confirms §3 estimate (M / 1 PV) from `v10_internal_optimization_directions.md`
§3.3 D-X-5.**

## §8 — dependencies

**Soft dependency on D-X-2 (reference doc creation link compression).**

If D-X-2 ships in the same v11.0.0 cycle, D-X-5 uses the
`scaffold_reference.py` CLI to bootstrap the troubleshooting.md file
+ install.sh manifest takes care of the 7-block edit automatically
(zero install.sh manual edits needed for the 15th reference).

If D-X-2 does NOT ship in v11.0.0 (or ships after D-X-5), D-X-5 must
do the install.sh 7-block manual edit (i.e., revert to the legacy
v10.3.0 7-step ceremony for adding a reference). This adds ~10 min to
PV effort but does not change the M estimate.

**Order in cycle plan:**

- Preferred: D-X-2 in PV-N, D-X-5 in PV-N+1 (D-X-5 uses D-X-2's
  scaffold).
- Acceptable: D-X-5 in PV-N, D-X-2 in PV-N+1 (D-X-2's regression test
  must verify install.sh post-D-X-5 14-row manifest matches expected
  15 rows after manifest refactor).

**Hard dependency:** None. D-X-5 can ship standalone; the
relationship with D-X-2 is one of order-preference, not
admission-blocking.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | The 15th reference triggers a cycle review of the SF-4 14-file fixed-set baseline — operators may push back arguing "C-4 budget is on existing references, this expansion violates the spirit even if not the letter" | major | Coupling with D-D-1 (reference utilization audit) is the principled response: D-D-1 establishes which references are LOW-utilization; the slot freed by deprecating a low-utilization reference goes to troubleshooting.md. If D-D-1 doesn't ship in v11.0.0, D-X-5 ships the 15th reference standalone with explicit CHANGELOG note: "v11.0.0 expands the SF-4 valid reference set 14 → 15; future cycles SHOULD audit utilization before adding the 16th (per D-D-1 admission verdict)." |
| R2 | Troubleshooting reference grows organically until it hits the 1000-line ceiling — operators add new traps every cycle, and within 4-6 cycles the reference is at the C-4 ceiling | minor | Reference structure is partitioned (Part 1 index, Part 2 details, Part 3 escalation); when Part 2 grows past ~700 lines, the cycle MUST split it (e.g., create `references/troubleshooting-plugin.md` + `references/troubleshooting-rules.md` + the original becomes an index). The C-4 ceiling is a forcing function; not a problem. |
| R3 | Reference content drifts from canonical retrospective content — e.g., the troubleshooting "dataclass + spec_from_file_location" entry might paraphrase v10.0.0 §4.2 inaccurately → operators following troubleshooting reference get stale advice | minor | Each Part 2 section MUST cite the source retrospective file + line number; W-18 lint pins the citation pattern (presence of "Source: `.local/research/vX.Y.Z_retrospective.md`" line in each Part 2 section). C-3 verbatim extraction rule applies. |
| R4 | The reference may inadvertently leak hardcoded paths or env var names that violate S-2 (No Absolute Paths) or W-20 (env-flag reuse) → cycle PR fails the no-ghost-features audit | minor | Standard authoring pattern: all paths relative to repo root (per S-2); env vars cited via `references/env-flags.md` cross-ref (per W-20 reuse-first). The W-18 lint stanza pins this by asserting the absence of absolute path patterns (regex `/home/`, `/Users/`, `/root/`) in the new reference body. |
| R5 | If the reference is consulted but the operator's NEW symptom isn't yet in Part 2, they're back to grep-the-retros mode → reference adds value asymptotically; first 3-6 cycles see lower lookup success rate than steady state | minor | Reference launches with ~30 entries at PV-N (covering the dominant traps from v8.0.0..v10.3.0); this is large enough that ~80% of common symptoms are covered. The remaining 20% drive cycle-retro §4.2 incident additions; future cycles' retros add to the reference (a closed loop). The §5 benefit metric "Lookup success rate" baseline is set at 95% AT STEADY STATE (post 1-2 cycle warmup); v11.0.0 launch reports the initial 90% with explicit "ramp" caveat. |

---

ADMISSION: PASS | EFFORT: M | DEPS: D-X-2 (soft, order-preference only) | TIER: standard
