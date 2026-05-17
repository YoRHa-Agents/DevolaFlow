# PDS — D-Q-3: Lifecycle Hook 10-Event Naming Taxonomy (PURE-ALIAS)

> **Wave:** 5a (D-Q Code Quality)
> **Author:** L3 Task Agent (composer-2-fast)
> **Date:** 2026-05-04
> **Source:** `.local/research/v10_internal_optimization_directions.md` §3.5 D-Q-3
> **Schema:** `.local/research/v11.0.0_decomposition_plan.md` §3 (PDS v1)

## §1 — current_state

`src/devolaflow/lifecycle/__init__.py::DEFAULT_EVENTS` (lines 207-218) declares the canonical
**10-event tuple** as of v10.3.0 stable. The events grew incrementally (5 → 6 at v8.4.4 PV-04,
6 → 7 at v9.1.0 W1-02, 7 → 8 at v9.1.3 PV-03, 8 → 9 at v9.4.0 PV-02, 9 → 10 at v9.5.0 PV-04;
each addition APPENDED at the END of the tuple per A-2.4 / cache-prefix invariants). The current
verbatim 10 names + their handlers + their conceptual category:

| Pos | Event name (verbatim) | Default handler module | Category |
|:---:|---|---|---|
| 1 | `pre_dispatch` | `validate_dispatch.py::validate_dispatch` | pre-action |
| 2 | `post_dispatch` | `post_dispatch.py::post_dispatch` (no-op default; S-10 governance slot) | post-action |
| 3 | `file_write` | `check_file_ownership.py::check_file_ownership` | check (file ownership per S-8) |
| 4 | `task_stop` | `test_on_complete.py::test_on_complete` | post-action (verifies test-pass at task end) |
| 5 | `format_on_edit` | `format_on_edit.py::format_on_edit` | post-action (auto-format after edit) |
| 6 | `pre_shell_call` | `pre_shell_call.py::pre_shell_call` | pre-action |
| 7 | `envelope_write` | `check_envelope_append_only.py::check_envelope_append_only` | check (S-9 append-only) |
| 8 | `pre_handoff` | `auto_write_handoff.py::auto_write_handoff` | pre-action |
| 9 | `pre_plugin_invocation` | `pre_plugin_invocation.py::pre_plugin_invocation` | pre-action |
| 10 | `post_skill_edit` | `post_skill_edit.py::post_skill_edit` | post-action |

**Naming inconsistency surfaced** (the heart of D-Q-3): 6 of 10 events use the canonical
`pre_*` / `post_*` taxonomy (positions 1, 2, 6, 8, 9, 10); the remaining 4 use ad-hoc names that
don't telegraph their lifecycle position:

- Position 3: `file_write` — semantically "check_file_write" (handler is `check_file_ownership`,
  enforces S-8 owned-files manifest BEFORE the write completes)
- Position 4: `task_stop` — semantically "post_task_complete" (fires AFTER the L3 Task Agent
  signals completion; verifies tests-pass before the orchestrator records the outcome)
- Position 5: `format_on_edit` — semantically "post_file_edit" (fires AFTER any file edit; the
  "on_edit" middle-fix is non-standard)
- Position 7: `envelope_write` — semantically "check_envelope_write" (handler is
  `check_envelope_append_only`, enforces S-9 BEFORE the envelope write completes)

The taxonomy gap is also noted in the source doc (§3.5 D-Q-3): "命名混杂... 缺统一前缀规则". External
hook registrants (operator skills, test fixtures) need to memorize 4 ad-hoc names that don't follow
the prefix convention every other event uses. The raw cost is small (10 names total) but compounds
with every new event addition (the S-9 v9.1.0 W1-02 author had to choose `envelope_write` over
`check_envelope_write` without a documented rule; without D-Q-3, the next addition will face the
same arbitrary call).

## §2 — patch_design

**Algorithm:** introduce 4 NEW canonical event-name constants (the renames) in
`src/devolaflow/lifecycle/__init__.py`; preserve the 4 OLD event-name constants as **PURE-ALIAS**
(byte-equal string values pointing at the same handlers via `_set_default_hook` registration).
For ONE FULL CYCLE (v11.0.0 → v11.1.0 → v11.2.0), BOTH names work. At v11.2.0 cycle close, OLD names
are deprecated with a `DeprecationWarning` (still functional). At v12.0.0 the OLD names can be
removed (S-7 alias-deletion policy; not in scope of v11.0.0 PDS — telegraph only).

**Rename mapping table (the canonical D-Q-3 contract):**

| # | OLD event name (preserved as alias) | NEW canonical name | Rename rationale | Alias mechanism |
|:---:|---|---|---|---|
| 1 | `file_write` | `check_file_write` | Handler is `check_file_ownership` (S-8 ownership enforcement); `check_*` prefix groups it with envelope_write below | `FILE_WRITE_EVENT: str = CHECK_FILE_WRITE_EVENT` (OLD constant points at NEW string value; NEW string registered by `_set_default_hook`) |
| 2 | `task_stop` | `post_task_complete` | Fires AFTER the L3 task signals completion; `post_*` prefix matches positions 2 / 5 / 10 | `TASK_STOP_EVENT: str = POST_TASK_COMPLETE_EVENT` |
| 3 | `format_on_edit` | `post_file_edit` | Fires AFTER any file edit; `post_*` prefix is the canonical post-action marker; the "on_edit" middle-fix is non-standard | `FORMAT_ON_EDIT_EVENT: str = POST_FILE_EDIT_EVENT` |
| 4 | `envelope_write` | `check_envelope_write` | Handler is `check_envelope_append_only` (S-9 append-only enforcement); `check_*` prefix groups it with check_file_write above | `ENVELOPE_WRITE_EVENT: str = CHECK_ENVELOPE_WRITE_EVENT` |

**Resulting taxonomy (after rename, before deprecation):**

| Prefix group | Events | Count |
|---|---|:---:|
| `pre_*` | `pre_dispatch`, `pre_shell_call`, `pre_handoff`, `pre_plugin_invocation` | 4 |
| `post_*` | `post_dispatch`, `post_task_complete`, `post_file_edit`, `post_skill_edit` | 4 |
| `check_*` | `check_file_write`, `check_envelope_write` | 2 |

10 events total (verbatim count preserved). Categories cleanly partition the surface; each new
event addition will face an unambiguous taxonomy assignment.

**Files-touched (write-allowed scope):**

| File | Change kind | Net delta |
|---|---|---:|
| `src/devolaflow/lifecycle/__init__.py` | Add 4 NEW event-name constants (`CHECK_FILE_WRITE_EVENT`, `POST_TASK_COMPLETE_EVENT`, `POST_FILE_EDIT_EVENT`, `CHECK_ENVELOPE_WRITE_EVENT`); update `__all__`; preserve 4 OLD constants as PURE-ALIAS pointing at NEW string values; add deprecation comment block; bump `DEFAULT_EVENTS` tuple to use NEW names (OLD aliases still in `__all__`) | +30 LOC |
| `src/devolaflow/lifecycle/check_file_ownership.py` | Update `EVENT: str = "check_file_write"`; preserve old behaviour (`_set_default_hook` registers the same handler under the new event name) | ±0 LOC (1-line edit) |
| `src/devolaflow/lifecycle/test_on_complete.py` | Update `EVENT: str = "post_task_complete"` | ±0 LOC |
| `src/devolaflow/lifecycle/format_on_edit.py` | Update `EVENT: str = "post_file_edit"` | ±0 LOC |
| `src/devolaflow/lifecycle/check_envelope_append_only.py` | Update `EVENT: str = "check_envelope_write"` | ±0 LOC |
| `workflow-system/agent/references/env-flags.md` | Update §2.13 (`pre_plugin_invocation` slot description) + §2.14 (`post_skill_edit` slot description) to reference the NEW canonical taxonomy in passing; add a §X "Lifecycle event taxonomy" subsection with the rename mapping table | +25 LOC |
| `workflow-system/agent/references/plan-mode-enforcement.md` | If it references any of the 4 OLD names, swap to NEW names with parenthetical alias note | ±0-5 LOC |
| `tests/test_lifecycle_event_aliases.py` | NEW: 4 unit tests pinning that OLD constant string-equals NEW constant; 1 unit test pinning `DEFAULT_EVENTS` tuple position-stable; 1 unit test confirming `register_hook(OLD_NAME, ...)` equivalent to `register_hook(NEW_NAME, ...)` | +6 NEW test functions |
| `tests/test_layout_invariant_multi_baseline.py` | UNTOUCHED — event names don't appear in canonical_order (positions 1-12) so no cache-prefix break | ±0 LOC |

**Net LOC delta:** +60 LOC. NEW tests: +6 (W-17 cap: ≤30/PV — well under).

**API/CLI surface:** **zero breaking changes** thanks to PURE-ALIAS. Every existing caller using OLD
names continues to work byte-identically. The OLD `EVENT: str = "file_write"` etc. become aliases:

```python
# BEFORE (v10.3.0):
FILE_WRITE_EVENT: str = _FILE_WRITE_EVENT  # _FILE_WRITE_EVENT = "file_write"

# AFTER (v11.0.x):
CHECK_FILE_WRITE_EVENT: str = "check_file_write"  # NEW canonical
FILE_WRITE_EVENT: str = CHECK_FILE_WRITE_EVENT     # OLD as PURE-ALIAS (1-cycle)
```

External callers using `from devolaflow.lifecycle import FILE_WRITE_EVENT` keep working because
`FILE_WRITE_EVENT` still exists and string-equals `"check_file_write"`. Calls
`register_hook("file_write", ...)` ALSO keep working because the lifecycle dispatcher's
`register_hook` does string-equality on the event name; we register the handler ONCE under the NEW
name and add a one-line alias in `_set_default_hook` so the OLD name still routes:

```python
# In lifecycle/__init__.py after _set_default_hook calls:
_alias_event(_FILE_WRITE_EVENT, _CHECK_FILE_WRITE_EVENT)  # OLD → NEW alias
```

(The `_alias_event` helper is a NEW lifecycle/dispatcher.py function; ~15 LOC; just adds the
handler list under both names.)

**Documentation deliverable:**
- CHANGELOG entry: "Refactor: rename 4 lifecycle events to canonical `pre_*`/`post_*`/`check_*` taxonomy; OLD names preserved as PURE-ALIAS for v11.0.x → v11.2.x; deprecation telegraphed for v12.0.0"
- env-flags.md update (per §2 above) — bilingual EN+ZH NOT required (this reference is EN-only per current convention; ST-3 doesn't apply)
- W-18 ghost-audit refresh: add 4 NEW event constants to coverage parametrize entry
- ADR cross-link: new v11-ADR-XXX-lifecycle-event-taxonomy citing this PDS + the 1-cycle alias schedule

## §3 — small_project_eval

**Synthetic test bed:** synthetic_small_repo (per `v11.0.0_evaluation_methodology.md` §2)

**Operations exercised:** `init` (triggers `pre_dispatch` + `post_dispatch` only — small repos
typically don't trigger the renamed events because they don't have plugins (no
`pre_plugin_invocation`), don't have skill-edit cycles (no `post_skill_edit`), don't have agent
workspace (no `pre_handoff` / `envelope_write`). Renamed events that COULD fire on small repo:
`file_write` → `check_file_write` (S-8 ownership; only fires when a `change-driven` workflow is
active, which small synthetic repo lacks); `task_stop` → `post_task_complete` (fires; verifies
tests-pass); `format_on_edit` → `post_file_edit` (fires).

**Metric collection:** §4.6 coupling/contract bucket — count of lifecycle hook events; §4.3
code-quality bucket — average event-name length / consistency.

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Lifecycle hook events count | 10 | 10 (unchanged; rename only) | 0 | neutral |
| Events with `pre_*` / `post_*` / `check_*` prefix | 6 / 10 (60%) | 10 / 10 (100%) | +4 (+40 pp) | improve |
| Distinct prefix groups | 5 (pre_, post_, file_, task_, format_, envelope_, check_) actually 7 distinct prefixes | 3 (`pre_`, `post_`, `check_`) | -4 | improve |
| Operator memorization cost (event-name guess accuracy on a NEW event) | low (no rule) | high (3-prefix taxonomy) | improve | improve |
| Backward compatibility (OLD names still work) | 100% | 100% (PURE-ALIAS) | 0 | neutral |

**Pass criterion:** Δ on prefix consistency from 60% → 100% (achieved); zero behaviour change
verified by 100%-green pytest including `tests/test_lifecycle_hooks.py` + the 6 NEW alias tests.

**Verdict if pass:** PASS small tier (rename is structural; tests confirm zero behavioural delta;
small-repo operators benefit from clearer documentation when they encounter lifecycle hook
references in env-flags.md).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline)

**Metric collection:** §4.6 coupling/contract bucket + S-10 / S-9 / S-8 invariant verification.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Distinct lifecycle event prefixes | 7 (`pre_`, `post_`, `file_`, `task_`, `format_`, `envelope_`, also `pre_`/`post_` shared) | 3 (`pre_`, `post_`, `check_`) | -4 | improve |
| Events without canonical prefix | 4 (`file_write`, `task_stop`, `format_on_edit`, `envelope_write`) | 0 | -4 | improve |
| Cache-prefix bytes (DEFAULT_EVENTS tuple repr) | 156 chars | 168 chars (NEW names slightly longer) | +12 (~+8%) | minor regression (acceptable; tuple is NOT in dispatch payload — A-2 frozen prefix unaffected) |
| `tests/test_lifecycle_hooks.py` pass rate | n/n | n/n (preserved) | 0 | maintained |
| `tests/test_dispatch_emission_runs_hooks.py` pass rate (S-10) | 11/11 | 11/11 (uses constants, not strings — auto-updates) | 0 | maintained |
| `tests/test_handoff_envelope_immutable.py` pass rate (S-9) | n/n | n/n | 0 | maintained |
| `tests/test_change_file_ownership_hook.py` (or equivalent S-8 test) pass rate | n/n | n/n | 0 | maintained |
| Coverage % (per S-3 floor) | 93.04% | ≥93.04% | ≥0 | neutral |

**Pass criterion:** all existing pytest stays 100% green (zero behavioural delta); 6 NEW alias
tests pass; env-flags.md taxonomy section renders correctly; OLD names continue to register hooks
under the NEW name (verified by `register_hook("file_write", h); registered_events()` returns the
NEW name and the handler fires for both `run_hooks("file_write", ...)` AND `run_hooks("check_file_write", ...)`).

**Side-effect check (MUST NOT regress):**
- A-2 frozen prefix invariant: lifecycle event names are NOT in canonical_order positions 1-12; the rename does NOT touch dispatch payload structure (verified — DEFAULT_EVENTS is internal tuple; not serialized into dispatch). `tests/test_layout_invariant_multi_baseline.py` UNTOUCHED.
- S-9 handoff envelope append-only invariant: `check_envelope_append_only` handler still wired correctly under the NEW `check_envelope_write` name; OLD `envelope_write` name routes to the same handler.
- S-8 owned-files invariant: `check_file_ownership` handler still wired correctly under NEW `check_file_write` name.
- S-10 hook chain order: 4-event chain in `feedback.py::_emit_dispatch` (or D-Q-2's `ProposalEmitter._fire_hook_chain`) uses `PRE_DISPATCH_EVENT` / `POST_DISPATCH_EVENT` / `PRE_HANDOFF_EVENT` / `PRE_PLUGIN_INVOCATION_EVENT` constants — NONE of these are renamed by D-Q-3 (they were already on the canonical taxonomy). So D-Q-3 does NOT interact with D-Q-2's S-10 surface.
- pytest wall-clock not >+5%
- coverage ≥ 93.04%

**Verdict if pass:** PASS large tier.

## §5 — benefit_metrics

| # | Metric | Bucket | Before (v10.3.0) | After (v11.0.x) | Δ | Notes |
|:--:|---|---|---:|---:|---:|---|
| 1 | Distinct lifecycle event prefixes | code-quality (§4.3) + coupling (§4.6) | 7 (mixed) | 3 (`pre_` / `post_` / `check_`) | -4 (-57%) | Clean 3-bucket taxonomy |
| 2 | Events with canonical prefix | code-quality (§4.3) | 6 / 10 (60%) | 10 / 10 (100%) | +40 pp | 100% conformance |
| 3 | Operator memorization cost (heuristic — avg prefix uncertainty per event) | doc-health (§4.4) | high (4 ad-hoc names) | low (3-prefix rule) | improve | Documented in env-flags.md taxonomy section |
| 4 | Backward compatibility (OLD names continue to work) | coupling (§4.6) | n/a | 100% (PURE-ALIAS for v11.0.x → v11.2.x) | n/a | G-7 reversible — 1-cycle alias schedule |
| 5 | Lifecycle hook events count | coupling (§4.6) | 10 | 10 (rename only) | 0 | A-2.2 append-only respected; no add/remove |

All 5 metrics are §4.3 / §4.4 / §4.6 buckets per `v11.0.0_evaluation_methodology.md`; ZERO use
EvoBench scores (G-1 internal-value gate ✓).

## §6 — admission_verdict

**CONDITIONAL_PASS** — the benefit is real but modest (taxonomy clarity + future-event-naming
guidance) and the absolute-value impact on operators is small (10 names today, no projected growth
to 20+ in v11.0.0). The rename is structurally clean (3-prefix taxonomy, 100% conformance) and
G-7 reversible (PURE-ALIAS for 1 full cycle). It passes both small + large evaluation by virtue of
zero behavioural delta. The CONDITIONAL classification reflects that operators who never read the
lifecycle hook reference won't notice the change (the benefit is gated on doc-readership), and the
+12 cache-prefix bytes on `DEFAULT_EVENTS` repr is a minor regression on the tuple-serialization
side (acceptable because the tuple is NOT in dispatch payload).

**G-7 compatibility ✓:** PURE-ALIAS preserves OLD names for 1 cycle; deprecation telegraphed for
v12.0.0 (out of v11.0.0 scope).
**G-1 internal value ✓:** code-quality §4.3 + coupling §4.6 metrics; zero EvoBench.
**G-5 Soul-freeze ✓:** zero new Soul rules.
**G-6 cache-prefix ✓:** lifecycle event names are NOT in canonical_order positions 1-12.

## §7 — effort_estimate

**S** — ≤1 PV. Breakdown:
- Add 4 NEW event constants to `lifecycle/__init__.py`: ~20 min (one-line each + alias bindings)
- Add `_alias_event` helper in `lifecycle/dispatcher.py`: ~30 min (15 LOC + 1 unit test)
- Update 4 module-level `EVENT: str = ...` declarations in `check_file_ownership.py`,
  `test_on_complete.py`, `format_on_edit.py`, `check_envelope_append_only.py`: ~10 min
- Update `DEFAULT_EVENTS` tuple to use NEW names + update `__all__`: ~10 min
- Author 6 NEW unit tests in `tests/test_lifecycle_event_aliases.py`: ~60 min
- Update `references/env-flags.md` §2.13 + §2.14 + add NEW taxonomy section: ~45 min
- Run full pre-commit gate sequence (W-9 7 steps): ~30 min
- CHANGELOG + W-18 ghost-audit refresh: ~20 min

Total: ~3.5h work / 0.7 PV. W-17 test budget impact: +6 NEW test functions (well under +30/PV cap).

## §8 — dependencies

**Standalone — zero internal dependencies.** Could land in any v11.0.x PV. Soft preference: land
**after** D-Q-2 (the `feedback.py::_emit_dispatch` god-function refactor) so the rename touches a
freshly-extracted small surface in `ProposalEmitter._fire_hook_chain`. But D-Q-2 + D-Q-3 are also
fully decoupled because D-Q-3 doesn't rename ANY of the 4 events that D-Q-2's S-10 chain uses
(D-Q-2 chain = `pre_dispatch` / `post_dispatch` / `pre_handoff` / `pre_plugin_invocation` — all 4
already on canonical taxonomy).

External: zero external-tool deps (G-3 ✓); pure pytest validation.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | An external operator's hook registration uses the OLD name in a config file (not via the constant); when v12.0.0 finally removes the alias, the operator's hook silently stops firing | **major** | (a) PURE-ALIAS for 1 FULL cycle (v11.0.0 → v11.2.0) gives operators 3+ months notice; (b) at v11.2.0 cycle close, OLD name emits `DeprecationWarning` for 1 patch series; (c) at v12.0.0 cycle SI-1 planning gate, removal MUST be telegraphed in the v11.2.0 retrospective §3 deferred-items list (per W-7 / SI-8); (d) `registered_events()` introspection helper is documented in env-flags.md NEW taxonomy section so operators can verify their registrations resolve to the NEW name. |
| 2 | Cache-prefix +12 bytes on `DEFAULT_EVENTS` tuple repr accidentally invalidates a downstream test that golden-pinned the tuple-as-string | **minor** | Grep audit: `tests/` for `DEFAULT_EVENTS` literal-string usage; pre-PV survey shows only `tests/test_lifecycle_hooks.py` references `DEFAULT_EVENTS` and uses it as a tuple, not a string repr. The +12 bytes never enters dispatch payload (A-2 frozen prefix UNAFFECTED). |
| 3 | The `_alias_event` helper introduces an order-of-registration bug: if extras are registered under OLD name AFTER `_set_default_hook` wires NEW name, the extras might bind only to one entry of the alias map | **major** | The `_alias_event` helper is implemented as a "second-key alias" pattern in the dispatcher's internal handler dict — `register_hook(OLD)` and `register_hook(NEW)` both append to the SAME underlying handler list (single source of truth). 1 NEW test pins this behaviour: `test_register_under_old_name_fires_via_new_name_dispatch` and vice versa. |

---

ADMISSION: CONDITIONAL_PASS | EFFORT: S | DEPS: none | TIER: stretch
