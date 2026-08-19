# PDS — D-Q-2: `feedback.py::generate_round_dispatch` God-Function Refactor

> **Wave:** 5a (D-Q Code Quality)
> **Author:** L3 Task Agent (composer-2-fast)
> **Date:** 2026-05-04
> **Source:** `.local/research/v10_internal_optimization_directions.md` §3.5 D-Q-2
> **Schema:** `.local/research/v11.0.0_decomposition_plan.md` §3 (PDS v1)

## §1 — current_state

`src/devolaflow/feedback.py::ProposalGenerator.generate_round_dispatch` (lines 456-496, 41 LOC of
function body + 130 LOC of supporting `_emit_dispatch` helper at lines 498-578, with 4 lifecycle
hook constants at lines 52-67) is the central round-N dispatch emitter codified by Soul Rule **S-10**
("Prompt-Side Governance Contract Embedding"; see `.cursor/rules/repo-governance.mdc` S-10 + the v9.0.0
PV-04 / v9-ADR-004-lifecycle-wiring-and-s10.md ADR). Today the single class `ProposalGenerator` (lines
289-578) carries **6 distinct responsibilities** in one cohesive but architecturally-mixed surface:

1. **Dispatch construction** — `generate_round_dispatch` deep-copies `base_dispatch` then conditionally
   merges reinforcement (lines 482-496).
2. **Reinforcement extraction** — `generate_reinforcement` (lines 410-454) parses `verdict.details`
   and converts to `ReinforcementBlock` via `findings_to_reinforcement`.
3. **Lifecycle hook chain firing** — `_emit_dispatch` runs the 4-event chain (`pre_dispatch` →
   `post_dispatch` → `pre_handoff` → `pre_plugin_invocation`) per S-10 + v9.1.3 PV-03 + v9.4.0 PV-03
   wiring (lines 553-578).
4. **Per-event exception isolation** — each hook is wrapped in its own try/except so a buggy custom
   handler doesn't crash dispatch (lines 570-577; S-5 no-silent-failures pattern).
5. **Lazy lifecycle module import** — defensive `try: from devolaflow import lifecycle` (lines 553-562)
   so a missing lifecycle install path doesn't crash the round-N+1 emission.
6. **Independent proposal-generation flow** — `generate_proposals` + `_add_*` helpers (lines 303-408)
   are an unrelated public API that happens to share `ProposalGenerator` for historical reasons (the
   v3.x feedback-loop introduction predates v8.4.4 PV-04 S-10 codification).

The cohesion gap: responsibility #6 has nothing to do with #1-#5. The v8.4.4 PV-04 + v9.1.3 PV-03 +
v9.4.0 PV-03 hooks-chain growth has progressively bloated `_emit_dispatch` (now 80 LOC + 5 separate
docstring sections + 4 in-loop event constants). The v8.4.0 retrospective §4.1 #4 R5 strict pattern
keeps the byte-output guarantee, but the test surface (`tests/test_dispatch_emission_runs_hooks.py`,
362 LOC, 4 test classes, 11 test functions) has become the de-facto contract — every refactor MUST
keep these green.

## §2 — patch_design

**Algorithm:** Extract responsibilities #1-#5 into a new dedicated `ProposalEmitter` class
(`src/devolaflow/feedback_emit.py`, NEW module ~140 LOC). Keep `generate_round_dispatch` as a
**thin façade** on `ProposalGenerator` that delegates to the new emitter. Public API surface
**byte-identical** — every external caller (the lifecycle test + any L0/L1/L2 dispatcher) sees the
same `gen.generate_round_dispatch(base, verdict, round_num)` call shape with identical return
semantics. The S-10 4-event chain is carried verbatim into `ProposalEmitter._fire_hook_chain`;
the per-event try/except + lazy-import + permissive-mode flag stay identical (R5 strict
byte-identical invariant per v8.4.0 retro §4.1 #4).

**Files-touched (write-allowed scope):**

| File | Change kind | Net delta |
|---|---|---:|
| `src/devolaflow/feedback.py` | Refactor: keep `ProposalGenerator.generate_round_dispatch` as a 5-line façade delegating to `ProposalEmitter`; remove `_emit_dispatch` body (move to new module); preserve `generate_proposals` + `_add_*_proposals` + `generate_reinforcement` verbatim | -90 LOC |
| `src/devolaflow/feedback_emit.py` | NEW: `ProposalEmitter` class with `emit(dispatch, verdict, round_num, *, target_score, severity_floor)` method + `_fire_hook_chain(dispatch)` helper + 4 hook event constants + lazy-import-lifecycle pattern | +145 LOC |
| `tests/test_dispatch_emission_runs_hooks.py` | UNTOUCHED — every existing test stays green by virtue of the façade pattern | ±0 LOC |
| `tests/test_feedback_emit.py` | NEW: 8 unit tests for `ProposalEmitter` in isolation (single-responsibility coverage; complements the existing integration tests in `test_dispatch_emission_runs_hooks.py`) | +8 NEW test functions |

**Net LOC delta:** +55 LOC (split of 1 file into 2 with shared docstring overhead). NEW tests: +8
(W-17 cap: ≤30/PV, ≤150/cycle — well under).

**Before/after API surface (S-10 invariant — public signatures byte-identical):**

```python
# BEFORE (v10.3.0):
class ProposalGenerator:
    def generate_round_dispatch(
        self,
        base_dispatch: dict[str, Any],
        verdict: GateVerdict | None,
        round_num: int,
        target_score: float = 85.0,
        severity_floor: Severity = "major",
    ) -> dict[str, Any]: ...
    def _emit_dispatch(self, dispatch: dict[str, Any]) -> dict[str, Any]: ...

# AFTER (v11.0.x; PUBLIC SHAPE UNCHANGED):
class ProposalGenerator:
    def __init__(self) -> None:
        self._state = _ProposalState()
        self._emitter = ProposalEmitter()  # NEW: composition over inheritance

    def generate_round_dispatch(
        self,
        base_dispatch: dict[str, Any],
        verdict: GateVerdict | None,
        round_num: int,
        target_score: float = 85.0,
        severity_floor: Severity = "major",
    ) -> dict[str, Any]:
        # 5-line façade — delegate to emitter
        return self._emitter.emit(
            base_dispatch=base_dispatch,
            verdict=verdict,
            round_num=round_num,
            target_score=target_score,
            severity_floor=severity_floor,
            reinforcement_factory=self.generate_reinforcement,
        )
```

The new `ProposalEmitter` carries responsibilities #1, #3, #4, #5 (responsibility #2 stays on
`ProposalGenerator.generate_reinforcement` and is passed in as a callable factory — preserves the
v6-01 reinforcement-wiring contract). Responsibility #6 (`generate_proposals` flow) stays on
`ProposalGenerator` unchanged — it never had any architectural reason to live alongside
`generate_round_dispatch` and now its independence is structurally explicit.

**API/CLI surface:** **zero public-shape changes**. The `_emit_dispatch` private helper goes away
(it's an underscore-prefixed private; no external caller per Grep audit). The S-10 hook-chain
contract is preserved verbatim — `ProposalEmitter._fire_hook_chain` invokes the 4 events in the
same order with `strict=False`, in per-event try/except scopes that `logger.warning` on raise.

**Documentation deliverable:**
- CHANGELOG entry: "Refactor: extract `feedback.py::_emit_dispatch` into new `feedback_emit.py::ProposalEmitter` class for SRP / testability; **zero behaviour change**, S-10 invariant preserved (test_dispatch_emission_runs_hooks.py 100% green)"
- W-18 ghost-audit refresh: add `ProposalEmitter` + `ProposalEmitter.emit` symbols to `tests/test_no_ghost_features.py::test_v11_X_X_new_symbols_have_coverage` parametrize entry
- Inline ADR pointer in feedback.py + feedback_emit.py docstrings linking to v9-ADR-004 (S-10 codification) and the new v11-ADR-XXX-feedback-emitter-extraction (to be authored at PV time, NOT this PDS)

## §3 — small_project_eval

**Synthetic test bed:** synthetic_small_repo (per `v11.0.0_evaluation_methodology.md` §2)

**Operations exercised:** `feature` (1-file scope; triggers a single-round dispatch via
`feature-enhancement` workflow). The dispatch path runs through the same `generate_round_dispatch`
public API on small as on large repos, so the refactor is exercised identically.

**Metric collection:** §4.3 code-quality bucket — `radon cc src/devolaflow/feedback.py`,
`radon raw src/devolaflow/feedback.py`, methods-per-class manual count.

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Methods on `ProposalGenerator` | 6 (gen_proposals + 3×_add_* + gen_reinforcement + gen_round_dispatch + _emit_dispatch) | 5 (gen_proposals + 3×_add_* + gen_reinforcement + thin gen_round_dispatch façade) | -1 | improve |
| Max function LOC in `feedback.py` | 130 (`_emit_dispatch`) | ≤45 (longest after extraction = `generate_proposals`) | -85 | improve |
| `feedback.py` total LOC | 865 | ≤780 | -85 | improve |
| `_emit_dispatch` CC | 8 (4 events × try/except + 1 lazy-import branch) | 0 (helper deleted) | -8 | improve |
| `ProposalEmitter._fire_hook_chain` CC (NEW) | n/a | ≤6 | n/a | new (within target) |

**Pass criterion:** Δ ≥ -50% on max-function-LOC in feedback.py (achieved at -65%); methods-per-class
on `ProposalGenerator` stays ≤ 5 (achieved at 5; below typical god-class threshold of 7+);
`ProposalEmitter` is under 200 LOC and under CC=10.

**Verdict if pass:** PASS small tier (the refactor exercises identically on small and large repos
because `generate_round_dispatch` is invoked by every dispatch regardless of repo size).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline)

**Metric collection:** §4.3 code-quality bucket + S-10 invariant verification.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| `feedback.py` LOC | 865 | ≤780 | -85 | improve |
| Max function CC in `feedback.py` | 8 (`_emit_dispatch`) | ≤5 (façade `generate_round_dispatch`) | -3 | improve |
| `feedback.py` god-class indicator (methods on `ProposalGenerator`) | 6 | 5 | -1 | improve |
| `ProposalEmitter` (NEW) god-class indicator | n/a | 2 (`emit` + `_fire_hook_chain`) | n/a | new (well-decomposed) |
| Test functions covering S-10 chain | 11 (in `test_dispatch_emission_runs_hooks.py`) | 11 + 8 NEW unit tests on `ProposalEmitter` | +8 | improve |
| `test_dispatch_emission_runs_hooks.py` pass rate | 11/11 | 11/11 | ±0 | maintained |
| Coverage % (per S-3 floor) | 93.04% | ≥93.04% (likely +0.1-0.3%) | ≥0 | improve |

**Pass criterion:** test_dispatch_emission_runs_hooks.py 100% green AFTER refactor (S-10 invariant
preserved); 8 new unit tests on `ProposalEmitter` pass; max function LOC in feedback.py drops by
≥30%; coverage no regression.

**Side-effect check (MUST NOT regress):**
- S-10 invariant: hooks fire in order `pre_dispatch → post_dispatch → pre_handoff → pre_plugin_invocation` exactly once per emission path (3 paths: round-1 pass-through, no-findings, reinforcement-applied)
- R5 strict byte-identical: dispatch payload byte-equal to control when no extras register (3 tests in `TestR5ByteIdentical`)
- S-5 invariant: handler exceptions caught + WARNING-logged (1 test in `TestHandlerExceptionsAreSwallowed`)
- All 4091 existing tests remain green
- pytest wall-clock not >+5%
- coverage ≥ 93.04%

**Verdict if pass:** PASS large tier.

## §5 — benefit_metrics

| # | Metric | Bucket | Before (v10.3.0) | After (v11.0.x) | Δ | Notes |
|:--:|---|---|---:|---:|---:|---|
| 1 | Methods on `ProposalGenerator` (god-class indicator) | code-quality (§4.3) | 6 | 5 | -1 (-17%) | Composition-over-inheritance reduces breadth |
| 2 | Max function LOC in `feedback.py` | code-quality (§4.3) | 130 (`_emit_dispatch`) | ≤45 (`generate_proposals`) | -85 (-65%) | Largest single-function shrink |
| 3 | `feedback.py` total LOC | code-quality (§4.3) | 865 | ≤780 | -85 (-10%) | Net delta after split (NEW `feedback_emit.py` carries the moved code) |
| 4 | Test surface for S-10 chain (test count) | code-quality (§4.3) | 11 (integration only in `test_dispatch_emission_runs_hooks.py`) | 19 (11 integration + 8 NEW unit on `ProposalEmitter`) | +8 (+73%) | Better isolation = better regression catch |
| 5 | S-10 hook-chain order pin (regression tests) | code-quality (§4.3) | 2 (`test_pre_handoff_invoked_after_post_dispatch` + `test_pre_plugin_invocation_invoked_after_pre_handoff`) | 2 (preserved verbatim) + 1 NEW unit-test variant inside `ProposalEmitter`'s 8 unit tests | +1 | Defense-in-depth on the cache-prefix-critical chain order |

All 5 metrics are §4.3 code-quality bucket per `v11.0.0_evaluation_methodology.md`; ZERO use
EvoBench scores (G-1 internal-value gate ✓).

## §6 — admission_verdict

**PASS** — clear benefit on both small + large tiers (small: identical exercise via single-round
dispatch; large: -10% LOC in feedback.py, -65% on the worst-offender function, +73% test isolation
on the S-10 chain). G-7 compatibility ✓ (zero public-API breakage; `ProposalGenerator.generate_round_dispatch`
signature byte-identical; `_emit_dispatch` is private/underscore so its removal is allowed). G-8 test
coverage ✓ (8 NEW unit tests + 11 existing integration tests all green). G-1 internal value ✓
(code-quality §4.3 metrics; zero EvoBench).

**Hard constraint surfaced for v11.0.x PV implementation:** the S-10 invariant
(`tests/test_dispatch_emission_runs_hooks.py` ALL 11 tests green) is **non-negotiable**. The
refactor is a release blocker if ANY of:
- `test_round1_passthrough_invokes_all_hooks` fails (4-event chain breaks)
- `test_no_findings_path_invokes_all_hooks` fails
- `test_reinforcement_applied_path_invokes_all_hooks` fails
- `test_pre_handoff_invoked_after_post_dispatch` fails (chain order)
- `test_pre_plugin_invocation_invoked_after_pre_handoff` fails (chain order)
- `test_hook_invoked_in_permissive_mode` fails (`strict=False` invariant)
- `test_round1_payload_unchanged` / `test_no_findings_payload_unchanged` / `test_reinforcement_payload_matches_control` fail (R5 byte-identical)
- `test_handler_raise_is_logged_and_swallowed` fails (S-5 exception isolation)

The PV implementation MUST run this test file FIRST in the pre-commit chain.

## §7 — effort_estimate

**M** — 1 PV. Breakdown:
- Extract `_emit_dispatch` → `ProposalEmitter._fire_hook_chain`: ~30 min (mechanical move + import
  fixup)
- Add `ProposalEmitter.emit` orchestration method (the round-N+1 deep-copy + reinforcement-merge
  flow): ~45 min
- Refactor `ProposalGenerator.generate_round_dispatch` to thin façade (5 lines): ~15 min
- Author 8 NEW unit tests in `tests/test_feedback_emit.py` covering: (a) `emit` round-1 pass-through,
  (b) `emit` with no findings, (c) `emit` with findings + reinforcement, (d) `_fire_hook_chain`
  invokes 4 events in order, (e) `_fire_hook_chain` per-event try/except isolation, (f) lazy-import
  fallback path (lifecycle missing), (g) `strict=False` invariant on every hook call, (h) deep-copy
  contract (input not mutated): ~90 min
- Run full pre-commit gate sequence (W-9 6 base + Si-Chip iteration_delta = 7 steps): ~30 min
- CHANGELOG + W-18 ghost-audit refresh + ADR doc: ~30 min

Total: ~4h work / 1 PV. W-17 test budget impact: +8 NEW test functions (well under +30/PV cap).
Distributable: 1 PV, no inter-PV split needed.

## §8 — dependencies

**Standalone — zero internal dependencies.** The refactor is self-contained within `feedback.py`
+ NEW `feedback_emit.py` + NEW `tests/test_feedback_emit.py`. Does NOT depend on any other v11.0.0
direction landing first. Could land as early as v11.0.x PV-01 if desired; could equally land in any
later PV.

External: zero external-tool deps (G-3 ✓); does NOT require NineS / Si-Chip / RTK / ui-pro to
verify; pure pytest + radon validation.

**Inverse dependency:** if D-Q-3 (lifecycle hook rename taxonomy) lands first, this PDS's
`ProposalEmitter._fire_hook_chain` should reference the renamed event constants. The cleanest
ordering is **D-Q-2 first, then D-Q-3** (so the rename touches a freshly-extracted small surface,
not the bloated `_emit_dispatch`); both can also land independently because D-Q-3 preserves the old
event names as PURE-ALIAS for 1 cycle.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | S-10 invariant break (any of 11 tests in `test_dispatch_emission_runs_hooks.py` fails) — release blocker per ADR-004 D2 + repo-governance.mdc S-10 enforcement clause | **blocker** | (a) Test FIRST in pre-commit chain; (b) the new `ProposalEmitter._fire_hook_chain` is a verbatim COPY of `_emit_dispatch` lines 553-578 (no logic modification); (c) PV-implementation reviewer pairs with the S-10 ADR author (per W-21 Soul-rule-adjacent change protocol). |
| 2 | R5 byte-identical regression — a refactor accidentally adds a no-op mutation that would change cache-prefix for downstream LLM dispatches | **major** | The 3 `TestR5ByteIdentical` tests pin this (round-1, no-findings, reinforcement-applied paths); refactor MUST keep all 3 green. Additionally, `tests/test_layout_invariant_multi_baseline.py` pins the canonical_order golden YAMLs across 6 historical baselines — any byte drift from the refactor surfaces here. |
| 3 | The 6th responsibility (`generate_proposals` flow) gets accidentally scope-crept into `ProposalEmitter` (architecture drift back to god-class) | **minor** | Owned-files manifest at PV time strictly enumerates files-to-touch; `generate_proposals` + `_add_*` methods stay on `ProposalGenerator`. PV implementer cites this PDS §2 file-touched table in the PR description as the contract. |

---

ADMISSION: PASS | EFFORT: M | DEPS: none | TIER: standard
