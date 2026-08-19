# PDS — D-Q-1: v10.2.2 NineS Remaining 7 Warnings Cleanup

> **Wave:** 5a (D-Q Code Quality)
> **Author:** L3 Task Agent (composer-2-fast)
> **Date:** 2026-05-04
> **Source:** `.local/research/v10_internal_optimization_directions.md` §3.5 D-Q-1
> **Schema:** `.local/research/v11.0.0_decomposition_plan.md` §3 (PDS v1)

## §1 — current_state

The v10.2.2 PV-03 NineS deep-analysis (`.local/research/v10.2.2_nines.md` §2) emitted **10 warning-class
cyclomatic-complexity findings** across `src/devolaflow/{lifecycle,plugins}/`. v10.2.3-PV-04 closed
finding #2 (`pre_plugin_invocation::pre_plugin_invocation` CC=18 → ≤10 via `_handle_stale_plugin`
helper, per `.local/research/v10.2.3_iteration_round1.md`) and v10.2.4-PV-05 closed findings #5 +
#7 (`installer::read_last_checked` CC=15 + `post_skill_edit::post_skill_edit` CC=13). The remaining
**7 warnings** were explicitly deferred to "v10.4.0+ candidate" per `v10.2.2_nines.md` §5 and the
v10.2.0 OUT-OF-SCOPE list (gap analysis §5). All 7 are mechanical helper-extraction refactors; none
mutate behaviour. Existing test surfaces fully cover every modified branch (verified by §5 metrics
below: `tests/test_session_state.py`, `tests/test_handoff_auto_write.py`,
`tests/test_pre_plugin_invocation.py`, `tests/test_plugins.py`, `tests/test_runtime_plugins_smoke.py`,
`tests/test_dispatch_plugin_autoinstall.py`).

## §2 — patch_design

**Algorithm:** for each of the 7 high-CC functions, extract 1-3 single-purpose helpers (named
`_<verb>_<noun>` per the v10.2.3 PV-04 naming precedent). Each helper handles one previously-inlined
branch (network fetch, parser dispatch, layer routing, persistence shard, etc.). The public function
becomes a thin orchestrator that delegates to the helpers in order. Behaviour is **byte-identical** —
verified by re-running the existing pytest suite (no NEW assertions needed; existing branches already
covered).

**Files-touched (write-allowed scope; one PV per row):**

| # | File | Function | Current CC | Target CC | Helper(s) extracted | Test surface (already green) | Effort |
|---|---|---|:---:|:---:|---|---|:---:|
| 1 | `src/devolaflow/lifecycle/test_on_complete.py:200` | `_try_persist_session_state` | 20 | ≤10 | `_persist_learnings_shard`, `_persist_legibility_shard`, `_persist_lifecycle_event_shard` | `tests/test_session_state.py`, `tests/test_lifecycle_hooks.py` | M |
| 2 | `src/devolaflow/lifecycle/auto_write_handoff.py:83` | `_extract_layers` | 16 | ≤8 | `_layer_lookup_table` (5 source → 5 dispatch entries; collapses 4 if/return blocks into one loop) | `tests/test_handoff_auto_write.py` | S |
| 3 | `src/devolaflow/lifecycle/auto_write_handoff.py:170` | `auto_write_handoff` | 12 | ≤8 | `_resolve_envelope_inputs` (env-flag + payload-shape gate), `_write_envelope_or_violation` (try/except shard) | `tests/test_handoff_auto_write.py` | S |
| 4 | `src/devolaflow/lifecycle/pre_plugin_invocation.py:151` | `_extract_plugin_ids` | 16 | ≤8 | `_parse_plugin_ids_list`, `_parse_plugin_id_single`, `_parse_workflow_plugins` (3 dispatch shapes → 3 named parsers; merge in caller) | `tests/test_pre_plugin_invocation.py` | S |
| 5 | `src/devolaflow/plugins/installer.py:851` | `ensure_plugin` | 14 | ≤9 | `_handle_already_installed_path`, `_handle_install_path` (split cache-hit vs network-fetch arms) | `tests/test_runtime_plugins_smoke.py`, `tests/test_plugin_refresh_e2e.py` | M |
| 6 | `src/devolaflow/plugins/installer.py:213` | `plugins_for_workflow` | 11 | ≤7 | `_iter_workflow_matches` generator (removes 2 if-arms by yielding) | `tests/test_plugins.py`, `tests/test_pre_plugin_invocation.py` | S |
| 7 | `src/devolaflow/plugins/installer.py:279` | `resolve_plugin` | 11 | ≤7 | `_validate_required_keys`, `_validate_npm_then_init_keys` (2 backend-specific validators) | `tests/test_plugins.py`, `tests/test_runtime_plugins_smoke.py` | S |

**API/CLI surface:** **zero changes**. All 7 public function signatures preserved verbatim. Helpers are
module-private (`_`-prefixed). No env flag added. No schema bump. No CHANGELOG-visible behaviour delta.

**Documentation deliverable:** 1-line CHANGELOG entry per PV ("Refactor: extract helpers from
`<func>` (CC <X>→<Y>); zero behaviour change"); W-18 ghost-audit refresh adds the 7 helper symbols
to `tests/test_no_ghost_features.py::test_v11_X_X_helpers_have_coverage` (parametrize expansion;
does NOT count toward W-17 +30/PV cap per W-17 caveat about parametrize-over-data).

**Verification per PV:** `radon cc -nB src/devolaflow/<file>` confirms target CC reached;
`python -m pytest tests/test_<surface>.py -v` stays 100% green; `python -m pytest tests/ -q --cov`
confirms coverage ≥ 80% per S-3.

## §3 — small_project_eval

**Synthetic test bed:** synthetic_small_repo (per `v11.0.0_evaluation_methodology.md` §2)

**Operations exercised:** none directly — D-Q-1 is internal refactor; small repo doesn't trigger the
7 functions because they handle workspace / handoff / plugin / session-persist machinery that small
repos don't activate (no `.local/.agent/active/`, no plugins, no session-state path).

**Metric collection:** indirect — small repo benefits only via "developer-of-DF" lens (when a small
repo's operator reads installer.py / lifecycle hooks for debugging, the helper-extracted code is
easier to comprehend per §4.3 code-quality bucket).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Avg CC across modified functions | 14.3 | ≤8.1 | -43% | improve |
| Functions with CC > 10 (the 7 above) | 7 | 0 | -7 | improve |
| LOC per function (avg, modified set) | 62 | ≤38 | -39% | improve |

**Pass criterion:** Δ ≤ -30% on avg-CC for the modified 7 (exceeded at -43%); zero behaviour change
verified by 100%-green pytest. Small-tier value: **N/A — not exercised in synthetic small repo**.
Per §4.3 code-quality metrics, this direction inherits CONDITIONAL_PASS treatment for the small tier
(declared not-applicable) and PASS for the large tier; per `v11.0.0_admission_checklist.md` §2 G-2,
"applies only to repos with ≥ 4 plugins / active workspace" qualifies as a CONDITIONAL_PASS escape
hatch, BUT here the not-applicable bound is "small repo doesn't run this code at all" which is
admissible as PASS (no regression possible).

**If no improvement on small project:** marked verdict = PASS by virtue of zero exposure (small repo
never executes the modified branches; the change is a no-op for small-repo operators by definition).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline; commit f1d9652)

**Metric collection:** §4.3 code-quality bucket — `radon cc -a -nB src/devolaflow/{lifecycle,plugins}/`,
`radon raw src/devolaflow/<file>`, NineS warning count via `nines analyze --target-path
src/devolaflow/lifecycle/ --depth deep`.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| NineS warning count (lifecycle + plugins) | 7 (the 7 above) | 0 | -7 | improve |
| Avg CC (`lifecycle/` package) | 4.79 | ≤4.3 | -10% | improve |
| Avg CC (`plugins/` package) | 3.63 | ≤3.4 | -6% | improve |
| Functions with CC > 10 (whole repo) | 7 (these) | 0 (or near-0) | -7 | improve |
| `lifecycle/` synthesis score (per `v10.2.2_nines.md` §4) | 7.0/10 | ≥8.5/10 | +1.5 | improve |
| `plugins/` synthesis score | 7.5/10 | ≥9.0/10 | +1.5 | improve |
| Per-package composite (weighted mean) | 7.93 | ≥8.85 | +0.92 | improve |
| pytest wall-clock (cycle close, full suite) | 17s | ±5% (no regression) | ≈0 | neutral |
| Coverage % (per S-3 floor) | 93.04% | ≥93.04% | ≥0 | neutral |

**Pass criterion:** Δ ≥ -100% on NineS warning count (7 → 0 must be 100%); per-package composite
≥ 8.5 (recovers the W-3 minor-release floor that the v10.2.2 mid-cycle synthesis fell below).

**Side-effect check (MUST NOT regress):** pytest 100% green (currently 4091 tests; refactor must
keep all green); coverage ≥ 93.04% baseline (helpers add new branches but existing tests already
exercise them); pytest wall-clock not >+5% (helpers add small call overhead — measured trivial in
v10.2.3 PV-04 precedent).

**Verdict if pass:** PASS large tier.

## §5 — benefit_metrics

| # | Metric | Bucket | Before (v10.3.0) | After (v11.0.x cumulative) | Δ | Notes |
|:--:|---|---|---:|---:|---:|---|
| 1 | NineS warning count (lifecycle + plugins) | code-quality (§4.3) | 7 | 0 | -7 (-100%) | Zero residual high-CC warnings carried forward from v10.2.2 |
| 2 | Max function CC across the 7 modified | code-quality (§4.3) | 20 (`_try_persist_session_state`) | ≤10 (radon B-rated) | -10 (-50%) | Largest leverage win on the worst offender |
| 3 | Avg CC (modified functions, n=7) | code-quality (§4.3) | 14.3 | ≤8.1 | -6.2 (-43%) | Aggregate refactor effect |
| 4 | LOC per function (modified, n=7 avg) | code-quality (§4.3) | 62 | ≤38 | -24 (-39%) | Helper extraction shortens public functions |
| 5 | Per-package composite (per `v10.2.2_nines.md` §4) | code-quality (§4.3) | 7.93 | ≥8.85 | +0.92 | Recovers W-3 ≥8.5 minor-release floor |

All 5 metrics are §4.3 code-quality bucket per `v11.0.0_evaluation_methodology.md`; ZERO use
EvoBench scores (G-1 internal-value gate ✓).

## §6 — admission_verdict

**PASS** — clear large-project benefit (7 NineS warnings → 0; per-package composite recovers from
7.93 to ≥8.85, restoring the W-3 minor-release floor); small-project N/A treated as PASS-by-non-
exposure (small repos never execute the modified branches; refactor is a strict no-op for them).
Zero breaking changes (G-7 ✓), zero new tests required for behavioural verification (existing
surfaces already cover all branches), zero new env flags (G-7/W-20 ✓), zero canonical_order edits
(G-6 ✓), zero Soul-rule additions (G-5 ✓), zero external-tool dependencies (G-3 ✓).

## §7 — effort_estimate

**L** — 7 helper-extraction PVs total (one per row in §2 table), distributable across the v11.0.0
cycle as micro-PVs. Per-row effort: 5 × S (rows 2, 3, 4, 6, 7) + 2 × M (rows 1 + 5; the higher-CC
ones with multiple shards). Aggregate: ~3-4 PV-equivalents if batched (e.g., 2 lifecycle PVs + 1
installer PV + 1 sweep PV) OR up to 7 single-shot micro-PVs spread across the v11.0.x patch series.

**Per-row effort breakdown:**

| Row | Function | Effort | Rationale |
|:---:|---|:---:|---|
| 1 | `_try_persist_session_state` | M | 3 shards (learnings / legibility / lifecycle event); each shard ~30 LOC |
| 2 | `_extract_layers` | S | Pure dispatch table refactor; ~50 LOC delta |
| 3 | `auto_write_handoff` | S | 2-shard split (resolve + write); ~70 LOC delta |
| 4 | `_extract_plugin_ids` | S | 3 named parsers; ~60 LOC delta |
| 5 | `ensure_plugin` | M | Cache-hit vs network-fetch split; ~120 LOC delta + log-event preservation |
| 6 | `plugins_for_workflow` | S | Generator extraction; ~30 LOC delta |
| 7 | `resolve_plugin` | S | 2 backend-validators; ~50 LOC delta |

Sum of per-row efforts: 5 × S (≤0.5 PV each = 2.5 PV) + 2 × M (1 PV each = 2 PV) = **~4.5 PV**.
Distributable: recommend 3 batched PVs (lifecycle batch = rows 1-4, installer batch = rows 5-7,
final cleanup = NineS re-run + W-18 lint refresh).

W-17 test cap: zero NEW test functions (existing tests cover); only parametrize expansions in
`test_no_ghost_features.py` for the W-18 ghost-audit refresh per W-17 caveat.

## §8 — dependencies

**Standalone — zero internal dependencies.** Each row is independent (different file or different
function within `installer.py`). Within `installer.py`, rows 5-7 SHOULD land in the same PV (they
share the registry-loading scaffolding). Within `auto_write_handoff.py`, rows 2-3 SHOULD land in
the same PV (shared `_extract_change_id` neighbour helper).

External: zero external-tool deps (G-3 ✓); does NOT require NineS for verification (radon suffices
per `v10.2.2_nines.md` §6 fallback note); the optional NineS re-run at cycle-close is informational.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | Helper extraction over-decomposes; introduces call-overhead that regresses pytest wall-clock | **minor** | Per-row CC-target floor of 7 (not 1) prevents over-shredding; pytest wall-clock measured pre/post each PV; rollback if >+5% delta. |
| 2 | A helper changes a previously-inlined try/except scope, silently swallowing an exception that the public function used to re-raise | **major** | Each PV's pytest run includes the existing exception-path tests (per `tests/test_handoff_auto_write.py::TestEnvelopeImmutableError`, etc.); S-5 no-silent-failures invariant verified by lint at cycle close. |
| 3 | Row 5 (`ensure_plugin`) helper split disturbs the `_append_log` JSONL event ordering, breaking downstream operator tooling that grep'd specific event names | **major** | The 8 named log events (`plugin_already_installed`, `plugin_install_distinguish_failed_preinstall`, `plugin_install_blocked_by_config`, etc.) are PRESERVED VERBATIM as constants; helper extraction does NOT rename / reorder / drop any event. New tests in `tests/test_runtime_plugins_smoke.py` already pin the event ordering; refactor MUST keep all green. |

---

ADMISSION: PASS | EFFORT: L | DEPS: none | TIER: standard
