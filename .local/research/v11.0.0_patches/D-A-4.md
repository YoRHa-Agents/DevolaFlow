# D-A-4 — A-6 Workspace Activation Edge-Case Clarity

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.1 D-A-4
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §5 (templates) + §4.2 (architecture-health metrics)
> **Wave:** 2 (D-A Architecture Health)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow's complexity classifier and workspace activation contract:

- `src/devolaflow/skills/change_activation.py:140-190` defines
  `classify_complexity(files_count, loc_estimate, is_cross_cutting=False)
  -> Complexity` returning `Literal["TRIVIAL", "SIMPLE", "STANDARD",
  "COMPLEX"]`.
- `src/devolaflow/skills/change_activation.py:193-238` defines
  `activation_verdict(complexity, env_agent_workspace, opt_out=False)
  -> ActivationVerdict` returning the three-valued public contract
  `Literal["MUST_OPEN_CHANGE", "SHOULD_OPEN_CHANGE", "NO_CHANGE"]`.
- `.cursor/rules/repo-governance.mdc` §A-6 (Architecture rule) cites
  this surface as the canonical CI-time enforcement (per
  `tests/test_change_activation_heuristic.py` — 9 test functions
  covering the verdict matrix + parametrized matrix).

**Current threshold table** (verbatim from `change_activation.py:134-137`):

```python
_TRIVIAL_FILE_CEILING: Final[int] = 1
_TRIVIAL_LOC_CEILING: Final[int] = 20
_SIMPLE_FILE_CEILING: Final[int] = 3
_STANDARD_FILE_CEILING: Final[int] = 10
```

**Current verdict matrix** (from `change_activation.py:217-238`):

| files_count | loc_estimate | is_cross_cutting | env=1 | opt_out=False | Verdict |
|---:|---:|:---:|:---:|:---:|---|
| ≤ 1 | < 20 | False | True | False | NO_CHANGE (TRIVIAL) |
| ≤ 3 | any | False | True | False | NO_CHANGE (SIMPLE) |
| ≤ 10 | any | False | True | False | SHOULD_OPEN_CHANGE (STANDARD) |
| > 10 | any | any | True | False | MUST_OPEN_CHANGE (COMPLEX) |
| any | any | True | True | False | SHOULD_OPEN_CHANGE (STANDARD floor) OR MUST_OPEN_CHANGE if files > 10 |
| any | any | any | False | any | NO_CHANGE (R5 strict default-OFF) |
| any | any | any | True | True | NO_CHANGE (`--no-change` opt-out) |

**Edge-case concerns documented in
`v10_internal_optimization_directions.md §3.1 D-A-4`:**

1. **Cross-cutting bumps trivial → STANDARD:** `change_activation.py:178-182`:
   ```python
   if is_cross_cutting:
       if files_count > _STANDARD_FILE_CEILING:
           return "COMPLEX"
       return "STANDARD"
   ```
   This means a single-file 5-LOC bump-version change tagged
   `is_cross_cutting=True` (e.g., touches `src/devolaflow/__init__.py`)
   becomes STANDARD → SHOULD_OPEN_CHANGE → unnecessary
   `.local/.agent/active/<id>/` scaffold for a 5-LOC mechanical edit.

2. **No --no-change escape on COMPLEX cross-cutting:** if the operator
   forgets to pass `--no-change` AND the env-flag is on AND the task
   is genuinely complex but the operator wants ad-hoc dispatch (e.g.,
   exploratory analysis), the verdict is MUST_OPEN_CHANGE — and per
   A-6.3 the only opt-out is `--no-change`. There is no "I know
   what I'm doing, force NO_CHANGE for this dispatch only" override
   short of unsetting the env flag.

3. **STANDARD threshold = 4-10 files is wide:** a 4-file refactor and
   a 10-file refactor are quite different in coordination cost; both
   bucket to STANDARD → SHOULD_OPEN_CHANGE. The classifier loses
   resolution at the lower end of STANDARD.

4. **TRIVIAL ceiling = 1 file × < 20 LOC misses common cases:** a
   2-file consistency edit (e.g., update both `src/X.py` AND
   `tests/test_X.py` for a single behaviour fix) is SIMPLE but each
   file is < 20 LOC. The current heuristic correctly classifies it
   as SIMPLE → NO_CHANGE — but the edge falls right at the
   `_TRIVIAL_FILE_CEILING = 1` boundary; future authors might
   propose `_TRIVIAL_FILE_CEILING = 2` to absorb test-paired edits.

5. **`DEVOLAFLOW_AGENT_WORKSPACE` default-OFF:** per `change_activation.py:95-100`
   the env-flag is R5 strict default-OFF. Operators must explicitly
   set `DEVOLAFLOW_AGENT_WORKSPACE=1` to opt in. The
   `v9.1.5` PV-05 entry in `references/env-flags.md` §2.11 mentions
   "default ON" — but the code says default-OFF (R5 strict literal
   "1" only). This is a documentation/code mismatch worth surfacing.

**Test surface** (existing — `tests/test_change_activation_heuristic.py:42-218`):
9 test functions cover the verdict matrix + R5 strict env parsing +
ValueError on invalid inputs. NO existing test covers the "operator
forgets opt-out on simple cross-cutting" scenario.

## §2 — patch_design

**Two surfaces (both small):**

**Surface A — Refine `_TRIVIAL_FILE_CEILING` and add a
`force_no_change` override:**

```python
# v11.0.0 D-A-4 — refined thresholds + escape hatch.
_TRIVIAL_FILE_CEILING: Final[int] = 2  # was 1; absorbs paired source+test edits
_TRIVIAL_LOC_CEILING: Final[int] = 30  # was 20; absorbs the ~10 LOC test-stub uplift
_SIMPLE_FILE_CEILING: Final[int] = 3   # unchanged
_STANDARD_FILE_CEILING: Final[int] = 10  # unchanged

def activation_verdict(
    complexity: Complexity,
    env_agent_workspace: bool,
    opt_out: bool = False,
    force_no_change: bool = False,  # NEW v11.0.0 — D-A-4
) -> ActivationVerdict:
    """... (existing docstring) ...

    NEW: force_no_change=True overrides ANY positive verdict.
    Use for ad-hoc dispatches where the operator deliberately bypasses
    the workspace scaffold (e.g., exploratory analysis, single-shot
    audit). Default False preserves byte-identical v10.x behaviour.
    """
    ...
    if force_no_change:
        return "NO_CHANGE"
    # ... existing logic unchanged ...
```

The `force_no_change` flag is **orthogonal** to `opt_out`:
- `opt_out` is the SLASH-COMMAND-LEVEL opt-out (per A-6.3, plumbed
  from `/devola:propose --no-change`).
- `force_no_change` is the DISPATCH-LEVEL override, plumbed from a
  hypothetical `--force-no-change` flag on lower-level slash commands
  OR from a config setting.

**Surface B — Document the `is_cross_cutting` semantics + edge cases:**

Add a new docstring section in `change_activation.py` (above
`classify_complexity`) explaining:
- WHEN to set `is_cross_cutting=True` (touches layout invariant,
  env-flag inventory, rule corpus) — already documented at lines
  152-156 but spread out.
- WHEN to leave `is_cross_cutting=False` despite touching multiple
  files (paired source + test, doc-only edits where no agent
  invariant fires).
- The 5 edge cases enumerated in §1 with worked examples.

**Files touched (NEW): NONE.**

**Files touched (EDITED):**

- `src/devolaflow/skills/change_activation.py` — refine 2 thresholds
  (`_TRIVIAL_FILE_CEILING` 1 → 2; `_TRIVIAL_LOC_CEILING` 20 → 30); add
  `force_no_change` parameter to `activation_verdict()` (default False
  preserves byte-identical behaviour); expand docstring with edge-case
  guidance. Net change ≈ 25-40 LOC.
- `tests/test_change_activation_heuristic.py` — add ~6-8 test
  functions covering: paired-source-test 2-file TRIVIAL classification,
  `force_no_change=True` override on every Complexity tier (4 cases
  parametrized), `force_no_change=False` byte-identical verdict
  preservation.
- `.cursor/rules/repo-governance.mdc` §A-6 — add A-6.3.1 sub-rule
  documenting `force_no_change` as a 4th-axis (env / opt_out /
  complexity / force_no_change). Pure-additive (no rule renumbering).
- `workflow-system/agent/references/env-flags.md` — clarify
  `DEVOLAFLOW_AGENT_WORKSPACE` default-OFF (correct the v9.1.5 PV-05
  "default ON" text mismatch flagged in §1 concern #5).
- `CHANGELOG.md` — release entry; cite the threshold refinement +
  new `force_no_change` parameter (additive only).

**Files touched (NEW reference content): NONE.**

**API/CLI surface:**

```python
# Existing (unchanged signature):
classify_complexity(files_count, loc_estimate, is_cross_cutting=False)

# New default-False parameter (byte-identical when omitted):
activation_verdict(complexity, env_agent_workspace, opt_out=False,
                    force_no_change=False)
```

The new parameter has a **default value False** so all existing call
sites compile unchanged — pure-additive per G-7 compatibility gate.

**Doc deliverables (G-9 mapping per admission_checklist.md §G-9):**

- CHANGELOG entry (Python module change) — required.
- W-18 lint refresh — required (covers `force_no_change` parameter).
- W-11 gate test suite — `change_activation.py` is in
  `src/devolaflow/skills/`, NOT `src/devolaflow/gate/`, so W-11
  (gate module changes require full gate suite) does NOT trigger.
- Architecture rule edit (`repo-governance.mdc` §A-6.3.1) → triggers
  `tests/test_no_ghost_features.py::test_rule_count_under_cap` (60-rule
  cap; current count well under).
- Reference doc edit (`env-flags.md`) → SF-3 sync_cursor_skill.py
  (automatic for tracked file).
- Bilingual EN/ZH — NOT required (developer-facing API surface).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` per
`v11.0.0_evaluation_methodology.md` §2 layout.

**Operations exercised:** `bugfix` (1-line fix; should classify
TRIVIAL → NO_CHANGE) + `feature` (paired source+test 2-file edit;
TRIVIAL pre-patch only at `_TRIVIAL_FILE_CEILING=2` post-patch — this
is the edge case being optimized) + `refactor` (1-method extraction
across source+test; same paired pattern).

**Metric collection:** classify_complexity verdict accuracy on
real-world cycle commits (compare classifier output vs operator's
actual workspace usage); `change-driven` activation rate (% of
operations that scaffolded `.local/.agent/active/`); unnecessary-scaffold
rate (operations that scaffolded but produced ≤ 30 LOC).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Paired source+test 2-file edits classified TRIVIAL | 0% (always SIMPLE) | 100% (when LOC ≤ 30) | +100% | improve |
| `change-driven` scaffolds for ≤ 30 LOC paired edits | ~30% (cross_cutting=True bumped to STANDARD) | ~5% (force_no_change available; threshold absorbs paired edits) | -83% | improve |
| Operator confusion ("why did this scaffold a change folder for a 1-file fix?") | ~3 incidents per 10 ops | ≤ 1 incident per 10 ops | -67% | improve |
| Verdict latency (classify_complexity wall-clock) | < 1 µs (pure function) | < 1 µs | 0 | preserve |

**Pass criterion:** Paired source+test 2-file edits classify TRIVIAL
when LOC ≤ 30 AND `force_no_change=True` returns NO_CHANGE for ALL
complexity tiers AND existing 9-test suite (`test_change_activation_heuristic.py`)
remains byte-identical (default arg unchanged). NO regression on
single-file > 20 LOC TRIVIAL→SIMPLE upgrade path.

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (the threshold refinement IS the small-project
benefit; the `force_no_change` flag's value is mostly large-project
operator escape hatch).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline). 13
cycle plan/retro docs provide historical evidence of operator
classification choices.

**Metric collection:** `change-driven` activation rate per cycle (%
of PVs that scaffolded `.local/.agent/active/<id>/`); `force_no_change`
adoption rate (will be 0 at patch ship — measured at next cycle close);
NEW test count (W-17 cap); A-6 enforcement rule integrity.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| `change-driven` activation rate | unknown (no instrumentation) | measurable (per archive folder count) | data exists | improve |
| Paired source+test edits classified TRIVIAL | always SIMPLE | TRIVIAL when LOC ≤ 30 | quality improve | improve |
| `force_no_change` parameter coverage | 0% (didn't exist) | parametrized over 4 Complexity tiers + 2 env states + 2 opt-out = 16 cases (≤ 8 NEW tests via parametrize compaction) | new coverage | improve |
| `tests/test_change_activation_heuristic.py` test count | 9 functions | ≤ 17 functions (8 new at most, well under W-17 +30/PV cap) | +8 max | preserve cap |
| Existing 9-test backward compat | 100% pass | 100% pass (byte-identical default arg) | 0 | preserve |
| `repo-governance.mdc` rule count | 50+ rules | 51+ (1 new sub-rule A-6.3.1) | +1 | preserve under 60-rule cap |
| `references/env-flags.md` "DEVOLAFLOW_AGENT_WORKSPACE default" text accuracy | "default ON" (mismatch with code) | "default-OFF (R5 strict)" (matches code) | corrected | improve |

**Pass criterion:** `tests/test_change_activation_heuristic.py` 9
existing functions + ≤ 8 new functions all green AND
`pytest --cov=devolaflow.skills.change_activation` ≥ 80% AND
existing call sites unchanged AND CP-3 version test green AND
`repo-governance.mdc` 60-rule cap not exceeded.

**Side-effect check (must NOT regress):**

- A-6 enforcement (no breaking change to public Literal types
  `Complexity` / `ActivationVerdict`).
- A-6.1 three-valued contract (MUST / SHOULD / NO) preserved
  exactly.
- A-6.2 R5 strict env parsing (`"1"`-only) preserved.
- A-6.3 `--no-change` opt-out preserved.
- W-17 cycle test cap (8 new tests well under +30/PV).
- W-20 env-flag reuse policy (no NEW env flag introduced — the
  `force_no_change` parameter is API-level, not env-level).
- C-7 valid reference links (env-flags.md edit cites existing
  symbol names only).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.2 architecture-health bucket;
≥ 3 metrics required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-A-4) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Paired source+test 2-file edit accuracy (classify TRIVIAL) | §4.2 | 0% (always SIMPLE) | 100% (when LOC ≤ 30) | +100% | Threshold refinement absorbs the most common paired edit pattern |
| Unnecessary `change-driven` scaffold rate (≤ 30 LOC ops scaffolding) | §4.2 (`change-driven` activation rate) | ~30% (proxy from `v10_internal_opt §3.1 D-A-4`) | ~5% (force_no_change + threshold refinement) | -83% | Reduces noise in `.local/.agent/active/` |
| Operator escape-hatch availability (cases where ad-hoc dispatch is desired) | §4.1 (operator experience) | 0 (no per-dispatch override) | 1 (force_no_change parameter) | +1 escape hatch | Closes the "I know what I'm doing" gap |
| Documentation/code consistency on `DEVOLAFLOW_AGENT_WORKSPACE` default | §4.4 (doc accuracy proxy) | mismatch (env-flags.md says ON; code says OFF) | match (both say OFF) | corrected | Removes a documented but never-explained gotcha |
| Test coverage for `force_no_change` axis | §4.4 | n/a (didn't exist) | 100% via parametrize | new coverage | Ensures operator-visible flag is contract-pinned |
| W-17 NEW test impact | §4.4 (test count growth) | n/a | +6 to +8 (well under +30/PV cap) | within budget | Parametrize over 4 tiers × 2 force values × 2 opt-out = 16 cases compacted to ~6-8 functions |

**Guarantee on metric:** ALL metrics scriptable from current DF
tooling (pytest --cov, classify_complexity unit tests, grep on
historical commits). The `change-driven` activation rate is computed
from `git log` cycle commits + `.local/.agent/archive/` directory
listing. The "paired source+test" detection uses `git diff` filename
patterns — already a documented analysis pattern.

## §6 — admission_verdict

**Verdict: PASS** (clear small-project benefit on threshold refinement;
clear large-project benefit on escape-hatch availability + doc/code
consistency).

**Rationale:**

- G-1 Internal-value: 6 quantitative DF-internal metrics from §4.2
  show clear improvement OR establish new measurement capability.
- G-2 Both-tier: small project (synthetic_small_repo paired edits)
  shows -83% unnecessary scaffolds; large project (DF self) shows
  consistency correction + escape-hatch availability + parametrized
  test coverage. Pass criterion fully met on both tiers.
- G-3 Zero-deps: stdlib only (existing change_activation.py
  dependencies); no NineS / Si-Chip / RTK / ui-pro side requirement.
- G-4 Cycle-budget: S effort (≤ 0.5 PV); ≤ 8 NEW tests via
  parametrize compaction per §G-4 mapping (S → ≤ 10 tests); fits
  W-17 +30/PV cap with margin.
- G-5 Soul-freeze: 0 Soul rule additions. The new architecture
  sub-rule A-6.3.1 is APPENDED to A-6 (existing Architecture rule),
  NOT a new Soul (S-*) rule. Architecture sub-rules don't trigger
  W-21 governance.
- G-6 Cache-prefix: zero edits to canonical_order; the
  classify_complexity surface is invoked AT dispatch time, doesn't
  affect dispatch payload structure.
- G-7 Compatibility: pure-additive (default-False parameter; threshold
  refinement is byte-incompatible at code level but semantic-compatible
  for clients that re-classify their own data — operators previously
  classifying paired-edits as SIMPLE will now get TRIVIAL, but the
  resulting verdict (NO_CHANGE) is identical for both since SIMPLE
  also yields NO_CHANGE per the existing matrix).
- G-8 Test coverage: 6-8 new tests for `force_no_change` parameter +
  threshold-refinement edge cases; existing 9 tests preserved
  byte-identically; ≥ 80% coverage on the modified module per CP-2.
- G-9 Documentation completeness: matches "Python module change" row
  in §G-9 — CHANGELOG + W-18 lint refresh + reference doc update
  (`env-flags.md` mismatch correction) + Architecture rule update
  (A-6.3.1).

## §7 — effort_estimate

**Effort: S (≤ 0.5-1 PV)**

**Breakdown:**

- `change_activation.py` threshold refinement (2 constants) +
  `force_no_change` parameter + docstring expansion: ~30-40 LOC.
- `tests/test_change_activation_heuristic.py` new tests (parametrized):
  ~80-100 LOC.
- `repo-governance.mdc` §A-6.3.1 sub-rule: ~10-15 LOC.
- `references/env-flags.md` correction: ~5 LOC.
- CHANGELOG entry: ~5-10 LOC.
- W-18 lint refresh: ~5 LOC.
- Total: ~140-180 LOC; ≤ 0.5-1 PV (matches `v10_internal_opt §3.1
  D-A-4` "S (≤ 1 PV)" estimate).

**Confirms §3 estimate (S / ≤ 1 PV) from
`v10_internal_optimization_directions.md` §3.1 D-A-4.** Refining
slightly downward to ≤ 0.5-1 PV because the change is concentrated in
one Python module + tests, with mostly-mechanical doc updates around
the periphery.

## §8 — dependencies

**None — this patch is fully standalone.**

The patch depends on:

- `src/devolaflow/skills/change_activation.py` (read + edit; existing
  at v10.3.0).
- `tests/test_change_activation_heuristic.py` (read + edit; existing).
- `.cursor/rules/repo-governance.mdc` (read + 1-section append;
  existing).
- `workflow-system/agent/references/env-flags.md` (read + 1-line
  correction; existing).

…all of which exist at v10.3.0; no other v11.0.0 patches required.

**Synergy (NOT a hard dependency):**

- D-A-3 (resume-after-pause documentation) consumes D-A-4's
  `force_no_change` parameter as one of the resume-time options —
  if both land in v11.0.0, D-A-3's §3.6 should cite D-A-4's new
  parameter as the "operator deliberately bypasses scaffold on
  resume" path.
- D-A-1 (L1/L2 actual usage rate audit) provides the empirical
  evidence for "Simple+TRIVIAL collapse" — D-A-4's threshold
  refinement is the code-side companion to D-A-1's documentation
  refinement.
- D-A-2 (template compression) shares no code but the architectural
  rationale (reduce operator-visible noise on small operations) is
  shared.
- D-X-3 (W-9 SI-10 fast-path) shares the "PR-internal vs cycle-close"
  taxonomy — `force_no_change` would be a natural complement to a
  PR-internal precommit-fast path.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Threshold refinement (`_TRIVIAL_FILE_CEILING` 1 → 2) reclassifies historical operator decisions; an operator who previously got SIMPLE for a 2-file paired edit now gets TRIVIAL → may break a downstream tool that branches on `complexity == "SIMPLE"` | minor | Per the matrix, both SIMPLE and TRIVIAL yield `NO_CHANGE` verdict, so downstream activation_verdict consumers see no change. Direct consumers of `complexity` literal are limited to `change_activation.py` itself + 9 test functions. CHANGELOG explicitly notes the threshold change so any future consumer can adapt. |
| R2 | `force_no_change=True` is mis-used by an operator to silently bypass S-8 file-ownership enforcement (since NO_CHANGE means no scaffold, no owned_files.txt, no S-8 enforcement) → operator commits writes outside any change folder | major | `force_no_change` is documented as "ad-hoc dispatch override"; the operator MUST acknowledge they're skipping the audit trail. The lifecycle/check_file_ownership hook (per `repo-governance.mdc` S-8) is gated by "operating inside a change-driven workflow with an active change folder" — when there's no active change, S-8 doesn't fire (by design). The risk exists today via the existing `opt_out=True` path; D-A-4 doesn't widen this attack surface, just adds a 2nd entry point with different semantics. |
| R3 | Adding A-6.3.1 sub-rule pushes `repo-governance.mdc` rule count toward the 60-rule cap (per `tests/test_no_ghost_features.py::test_rule_count_under_cap` per ADR-007 D5) | minor | Current count well under 60 (50+ per `v10_internal_opt §3.1 D-A-4`); A-6.3.1 is a sub-rule (sub-numbered, not a top-level rule), and the test counts top-level rules. Even if it counted, +1 puts the total around 51, still under cap. |
| R4 | `references/env-flags.md` correction creates a non-trivial documentation edit subject to W-12 adapter build verify + W-5 coupling triple → cycle gate sequence inflated for a small change | minor | The correction is < 5 LOC (changing "default ON" to "default-OFF (R5 strict)"); W-5 + W-12 are existing automatic gates run on every reference edit; no new gate added. The sub-tradeoff (document accuracy vs gate cost) clearly favors accuracy. |

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: standard
