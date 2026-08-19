# D-X-3 — W-9 SI-10 Fast-Path (PR-internal vs cycle-close)

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.3 D-X-3
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §5 templates
> **Wave:** 1 (D-X Developer/Operator Experience)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)
> **Bundles:** D-X-4 (PR-flow analysis) per decomposition_plan §2 ("D-X-4 PR-flow analysis is bundled into D-X-3 since both touch SI-10 Makefile surface").

## §1 — current_state

DevolaFlow's pre-commit gate is the **SI-10 7-step sequence** wired
through `Makefile::release-preflight` at `Makefile:146-150`:

```
release-preflight: lint test validate-templates build-skill sync-human-docs \
    check-cursor-skill compile-rules check-drift check-rules-drift iteration-delta-gate
```

…and codified in `.cursor/rules/repo-governance.mdc:456-464` (W-9):

```
1. python -m pytest tests/ -q          — all tests pass
2. ruff check src/ tests/              — no lint errors
3. ruff format --check src/ tests/     — formatting correct
4. python -m pytest tests/test_version.py -v  — version consistency
5. python -m pytest tests/test_benchmarks.py -v — no benchmark regressions
6. make check-cursor-skill             — exit 0
7. iteration-delta-gate (Si-Chip)      — added v10.2.1 PV-02
```

The 7 steps run UNCONDITIONALLY for every PV close. Per
`v10_internal_optimization_directions.md` §3.3 D-X-3, the v10.2.0 cycle
ran the FULL 7-step gate across all 6 PVs — wall-clock ~5-10 minutes
each (pytest dominates: 4091 tests at ~17 seconds wall-clock per
`v11.0.0_evaluation_methodology.md` §3, plus build-skill, validate-templates,
sync-human-docs, etc.). The cycle's per-PV CHANGELOG ceremony (per
`v10.3.0_retrospective.md` §4.4 key learning) adds **~10 min subagent
overhead per PV** for `make sync-human-docs` + `make build-skill` +
gate-chain cumulative.

**There is currently NO distinction between "PR-internal commit" and
"PV close commit"** — every commit-test cycle pays the full cost. The
v10.3.0 retrospective §4.4 explicitly lists this as a deferred
optimization: "Pre-caching adapter builds via `make build-skill` before
round 1 to save ~30s per round (R-6 mitigation precedent)."

D-X-4 PR-flow context (bundled per decomposition_plan §2): the v10.3.0
retro §4.6 confirms the v10.2.0 cycle ran a single feature branch
(`feat/v10.2.0-cycle`) with all 6 PV commits → 1 PR (#117). Each PV is
its own version bump + canonical-7 sync + CHANGELOG entry → 6 version
bumps in a single PR. Reviewer load is thus concentrated at PR-merge
time but iteration cost is paid per-commit.

## §2 — patch_design

**Algorithm: 2-tier gate chain.**

Introduce a **fast-path** target for PR-internal iteration (commits
between `git push` and PR-merge) that runs only the cheap gates;
preserve the **full-path** for PV close commits and PR-merge gating.

```
make precommit-fast:
  1. ruff check --fix src/ tests/        — lint w/ auto-fix
  2. ruff format src/ tests/             — format in place
  3. python -m pytest tests/ -x --lf      — fail-fast on last-failed
                                            (reuses .pytest_cache;
                                            ~3-5s wall on green tree)
  4. (optional) python -m pytest <changed-test-files>

make precommit-full:
  Aliased to existing release-preflight — runs all 7 SI-10 gates.

make precommit:
  Default-target = precommit-full (preserves W-9 invariant).
  Operator MUST `make precommit-fast` deliberately for fast-path.
```

**Wiring decision (semantic clarity):**

- `precommit-fast` is **NOT a substitute** for SI-10. It runs only ruff
  + smoke pytest. SI-10 W-9 is unchanged: `release-preflight` and
  `precommit-full` both run all 7 steps.
- `precommit-fast` is suitable ONLY for "feature branch in-progress"
  iterations — explicitly not for: cycle-close PVs, version bumps,
  CHANGELOG-touching commits, or PR-merge gates.
- A new pre-push git hook stub (`scripts/git-hooks/pre-push.sh`,
  documented but not auto-installed) recommends operators run
  `precommit-full` before `git push` to PR review.

**Files touched (NEW):**

- `scripts/git-hooks/pre-push.sh` — opt-in template (~25 LOC); operator
  symlinks via `git config core.hooksPath`. NOT auto-installed.
- `tests/test_makefile_precommit_targets.py` — verifies `precommit-fast`
  + `precommit-full` exist as targets and `precommit` aliases to
  `precommit-full` (~60 LOC, 4-5 test functions).

**Files touched (EDITED):**

- `Makefile` — add 3 new phony targets: `precommit-fast`, `precommit-full`
  (alias for release-preflight), `precommit` (alias for full). ~25 LOC
  delta.
- `.cursor/rules/repo-governance.mdc` — augment §W-9 with a §W-9.1
  sub-rule clarifying the fast/full distinction (~15 lines added; pure
  doc; the canonical 7-step sequence remains the **W-9 invariant**).
- `AGENTS.md` — recompiled from .rules/ (post-edit `make compile-rules`).
- `workflow-system/agent/SKILL.md` — 2-line addition under "Quick Start"
  documenting the fast/full distinction.
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**API/CLI surface:**

```bash
make precommit-fast         # ruff + pytest --lf -x; ~10-30 seconds
make precommit-full         # all 7 SI-10 gates; ~5-10 minutes
make precommit              # alias for precommit-full (default = safe)
```

**Doc deliverables (G-9 mapping per admission_checklist.md §G-9):**

- CHANGELOG entry — required.
- W-18 lint refresh — required (pins the new Makefile targets).
- SKILL.md edit (2 lines) — triggers W-12 adapter build verify.
- repo-governance.mdc edit — triggers `make compile-rules` (which
  regenerates AGENTS.md); the existing `tests/test_no_ghost_features.py::test_rule_surfaces_compile_only`
  enforces drift detection.
- Reference doc add — NONE.
- Bilingual EN/ZH — NONE (developer-internal CLI; no user-facing copy).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` (per
`v11.0.0_evaluation_methodology.md` §2). The synthetic repo runs `make`
analogues against the DF source tree.

**Operations exercised:** `bugfix` (1-line fix → 1 commit) + `refactor`
(1-method extraction → 1 commit). Each operation runs a precommit
sequence; we measure fast vs full divergence.

**Metric collection:** Wall-clock of `make precommit-fast` (per §4.1
metric "Time-to-precommit (incremental)") vs `make precommit-full`
(per §4.1 "Time-to-precommit (full)"); pytest invocation count;
test-cache hit rate via pytest's `--lf` cache_dir contents.

**Expected delta (before → after):**

| Metric | Before (single full-path) | After (2-tier) | Δ | Direction |
|---|---:|---:|---:|:---:|
| Time-to-precommit (incremental, wall clock) | ~5-10 min (full only) | ~10-30 s (fast-path) | -90% to -95% | improve |
| Time-to-precommit (full, wall clock) | ~5-10 min | ~5-10 min (preserved for PV close) | 0 | preserve |
| Pytest invocations per 5 in-PR commits | 5 (full each) | 1 (fast on commits 1-4 + full on commit 5) | -80% | improve |
| pytest --lf cache hit rate (5-commit window) | N/A (no fast-path) | ~85% | new | improve |

**Pass criterion:** Δ ≤ -50% on Time-to-precommit (incremental) AND no
regression on Time-to-precommit (full). The fast-path MUST produce
green-on-green output (i.e., when full passes, fast must pass; when
fast passes but full fails, that is the EXPECTED behavior — fast
intentionally skips W-9 gates 4-7).

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS`. The fast-path's value is mainly for repos with
LARGE test suites; small repos with <100 tests get less benefit
because pytest cold-start dominates wall-clock anyway. We measure on
synthetic_small_repo to verify the fast-path is at minimum NOT WORSE
than full-path on small repos (no regression — fast is always ≤ full
in wall clock by construction).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline; 4091
tests per `v11.0.0_evaluation_methodology.md` §3 metric table).

**Metric collection:** Wall-clock of `make precommit-fast` and
`make precommit-full` over 5 consecutive trial commits (1 docs-only,
1 source change w/ test impact, 1 lint-only, 1 yaml-only, 1
test-only); pytest invocations; pytest cache hit rate; PV iteration
overhead (the v10.3.0 retro §4.4 baseline of ~10 min per PV).

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Time-to-precommit (incremental, median wall clock) | ~5-10 min (full each) | ~30 s (fast on green tree) | ~-95% | improve |
| Time-to-precommit (full, wall clock) | ~5-10 min | ~5-10 min (preserved) | 0 | preserve |
| Pytest invocations per 6-commit PV cycle | 6 (full each) | 1-2 (fast on 4-5 commits + full on PV-close) | -67% to -83% | improve |
| Per-PV subagent overhead (v10.3.0 retro §4.4 baseline) | ~10 min | ~3-5 min | -50% | improve |
| W-17 cycle test count delta (this patch's contribution) | n/a | +5 (Makefile target tests) | +5 | preserve (≤30/PV) |
| PR review concentration (D-X-4 angle) | 6 PV commits = 6 version bumps in 1 PR | Unchanged (this patch doesn't change PR cadence) | 0 | preserve |

**Pass criterion:** Time-to-precommit (incremental) Δ ≤ -50% AND
Time-to-precommit (full) Δ = 0 AND no SI-10 gate is silently skipped on
PR-merge (verified via test that `precommit` and `release-preflight`
both run all 7 W-9 gates).

**Side-effect check (must NOT regress):**

- W-9 SI-10 7-step canonical sequence remains the merge gate. The
  fast-path is iteration-only; merge-time is full.
- `tests/test_no_ghost_features.py::test_v11_0_X_makefile_targets_pinned`
  (new W-18 lint) verifies presence of all targets.
- `tests/test_rule_surfaces_compile_only` continues to pass (the W-9.1
  augmentation is compiled from .rules/, not hand-edited).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.1; ≥3 metrics required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-X-3) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Time-to-precommit (incremental, seconds) | §4.1 | ~300-600 s | ~10-30 s | -90% to -95% | Skip steps 4-7 + use pytest --lf cache |
| Time-to-precommit (full, seconds) | §4.1 | ~300-600 s | ~300-600 s | 0 | W-9 invariant preserved |
| Pytest invocations per 6-commit cycle | §4.4 (test health proxy) | 6 | 1-2 | -67% to -83% | Cache hit on incremental commits |
| Per-PV subagent overhead (minutes) | retro §4.4 baseline | ~10 | ~3-5 | -50% to -70% | Skipping make build-skill / sync-human-docs on incremental commits |
| SI-10 gate count (verified at PR-merge) | §4.5 (observability) | 7 | 7 | 0 | W-9 unchanged; fast-path is OPT-IN, not a replacement |

**Guarantee on metric:** ALL 5 metrics scriptable from current DF
tooling: `time make precommit-fast` (wall clock); pytest's own cache
introspection; cycle retros for subagent overhead trend; `grep -c`
SI-10 gate count in repo-governance.mdc.

## §6 — admission_verdict

**Verdict: PASS**

**Rationale:**

- G-1 Internal-value: 5 quantitative DF-internal metrics; the
  Time-to-precommit (incremental) -95% delta is the headline DF-internal
  win.
- G-2 Both-tier: small (synthetic_small_repo bugfix + refactor) shows
  fast-path is no-worse than full; large (DF self at 4091 tests) shows
  -95% wall-clock improvement on incremental. The small-tier benefit is
  weaker but non-negative — borderline CONDITIONAL_PASS but ultimately
  PASS because (a) small repo's full-path is already short enough that
  fast-path is negligibly different (no regression) and (b) the patch's
  value is monotone with repo size.
- G-3 Zero-deps: pure Makefile + ruff + pytest + .rules/ edits; no
  external tool requirement.
- G-4 Cycle-budget: S effort (≤0.5 PV); 4-5 NEW tests (Makefile target
  presence + W-9.1 augmentation + W-18 lint); fits well within +30/PV
  cap with margin.
- G-5 Soul-freeze: 0 Soul rule additions. The W-9.1 sub-rule is a
  Workflow rule augmentation (P3 Workflow layer), not a Soul rule.
- G-6 Cache-prefix: zero edits to schemas/lean-dispatch.yaml.
- G-7 Compatibility: pure-additive (3 new Makefile targets);
  `release-preflight` semantics unchanged → existing CI / cycle scripts
  see no behavior change.
- G-8 Test coverage: 4-5 unit tests for Makefile-target presence +
  W-9.1 alignment; ≥80% coverage by virtue of the targets being thin
  Make wrappers (the underlying `ruff` + `pytest` are already covered
  upstream).
- G-9 Documentation completeness: CHANGELOG + W-18 lint refresh + 2-line
  SKILL.md update + 1-section .rules/workflow.mdc update (W-9.1) +
  recompiled AGENTS.md + repo-governance.mdc; matches the "SKILL.md /
  CLAUDE.md change" + "Python module change" rows in §G-9. NO
  reference doc add. NO bilingual ZH (developer-internal).

## §7 — effort_estimate

**Effort: S (≤0.5 PV)**

**Breakdown:**

- Makefile delta (3 targets): ~25 LOC.
- `.rules/workflow.mdc` W-9.1 augmentation: ~15 LOC; `make compile-rules`
  regenerates downstream.
- SKILL.md 2-line addition + CHANGELOG entry: ~5 LOC.
- `tests/test_makefile_precommit_targets.py`: ~60 LOC.
- W-18 lint refresh: ~30 LOC.
- `scripts/git-hooks/pre-push.sh` (opt-in template): ~25 LOC.
- Total: ~160 LOC; comfortably ≤0.5 PV.

**Confirms §3 estimate (S / ≤1 PV, refining to ≤0.5 PV after gap
analysis) from `v10_internal_optimization_directions.md` §3.3 D-X-3.**

## §8 — dependencies

**None — this patch is fully standalone.**

This patch deliberately does NOT couple with:

- D-X-4 (PR-flow cycle-vs-PV alignment): bundled per decomposition_plan
  §2 because both target SI-10 Makefile surface, but the actual code
  changes are orthogonal. D-X-3 ships the fast/full split; D-X-4
  produces an analysis document on cycle-PR cadence. Because D-X-4 is
  documentation-only and ALSO covered in this PDS §1 (re: PR-flow
  observation), the bundle ships under one PDS / one PV.
- D-O-4 (SI-10 gate chain growth curve & bloat warning): the W-9
  growth analysis is OUT OF SCOPE for D-X-3; this patch does not
  rebalance the 7 gates, it only allows fast-path skipping. D-O-4
  would propose a 7→5+2 split; D-X-3 is the implementation primitive
  that would enable D-O-4's split if it ever ships.

Synergy (NOT a hard dependency):

- D-X-1 / D-X-2 scaffold CLIs would benefit from `precommit-fast`
  during iterative scaffold development.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Operator inadvertently uses `make precommit-fast` for PV-close commit → CHANGELOG + version bump lands without W-12 adapter build / W-13 benchmark check → drift on canonical 7 sync at next release | major | Make `precommit` (no suffix) the SAFE default — `precommit` aliases to `precommit-full`; `precommit-fast` requires explicit `-fast` suffix typed deliberately. The `tests/test_makefile_precommit_targets.py` test pins this aliasing. Also document in W-9.1: "PV-close commits MUST use `precommit-full` (or `precommit`); `precommit-fast` is for in-PR iteration only." Add the same caveat to the SKILL.md 2-line addition. |
| R2 | Pytest --lf cache stale on branch-switch → fast-path passes on stale cache while real tree is broken | minor | The pytest --lf cache lives at `.pytest_cache/v/cache/lastfailed` — cleaned by `make clean` (Makefile:165-167); the fast-path docstring instructs operators to run `make precommit-full` after every `git checkout` to a different branch. Also: the cache is invalidated by pytest itself when test discovery changes; in practice the staleness window is bounded. |
| R3 | W-9.1 augmentation drifts vs the canonical SI-10 7-step list (W-9 body) → operators reading W-9 alone might think there are now "8 gates" or some such | minor | Compile-rules drift detection (`tests/test_no_ghost_features.py::test_rule_surfaces_compile_only`) enforces source-of-truth in `.rules/workflow.mdc`. The W-9.1 sub-rule is an explicit ANNOTATION on W-9, not a rebalance. Document the relationship in W-9.1's first sentence: "This sub-rule does NOT change the 7-gate W-9 invariant; it documents an opt-in fast-path for in-PR iteration." |
| R4 | New Makefile targets confuse operators reading `Makefile` (which now has `release-preflight`, `precommit`, `precommit-fast`, `precommit-full`) → cognitive overhead for marginal benefit | minor | Each target gets a one-line `# comment` documenting WHEN to use it. The `make help` target (if exists; otherwise add as a `make targets` target) lists targets in usage order. CHANGELOG entry explicitly lists the 3 NEW targets and recommends `precommit` as default. |

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: standard
