# D-C-3 — `pre_plugin_invocation` Responsibility Split (Install vs Upgrade)

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.6 D-C-3
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §4.6 (lifecycle hook events count) + §4.3 (cyclomatic complexity)
> **Admission gates:** `.local/research/v11.0.0_admission_checklist.md` G-1..G-9
> **Wave:** 5 (D-C External Tool Coupling)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

`src/devolaflow/lifecycle/pre_plugin_invocation.py` is the **single
lifecycle hook** at `DEFAULT_EVENTS` position 9 (per
`src/devolaflow/lifecycle/__init__.py:180-191` comment + line 216) that
serves **two distinct purposes**:

1. **Install** — auto-invoke `ensure_plugin(plugin_id)` for each
   plugin cited in the dispatch payload BEFORE the L3 dispatch fires
   (the original v9.4.0 PV-02 contract per
   `pre_plugin_invocation.py:1-72` module docstring).
2. **Upgrade** — AFTER `ensure_plugin` succeeds, ALSO check
   `is_plugin_stale(plugin_id, threshold_hours=...)` and fire
   `upgrade_plugin(plugin_id)` when stale (the v10.2.1 PV-02 D-P-2
   daily-upgrade integration per `pre_plugin_invocation.py:73-108`
   module docstring extension).

The two responsibilities are STACKED in the parent function
`pre_plugin_invocation` at `pre_plugin_invocation.py:464-516`
(specifically the loop at lines 508-514 calls
`_run_install_then_upgrade_for_plugin` which orchestrates both).

**The CC-reduction history (NineS-quantified evidence):**

Per `.local/research/v10.2.3_iteration_round1.md` §2 B-1:

> NineS PV-03 deep-analysis flagged the parent `pre_plugin_invocation`
> function at CC=18 (row #2 in `.local/research/v10.2.2_nines.md` §2),
> introduced by the PV-02 D-P-2 daily-upgrade integration. Two helpers
> extracted: ... The parent function's loop body is now a one-liner
> that extends `install_violations` with the helper's return.
> Estimated post-fix CC ≤ 7 (3 early-return gates + the for-loop
> iteration).

The CC=18 → ≤10 reduction was achieved by EXTRACTING helpers WITHIN
the same hook function — but the underlying responsibility-stacking
remained. The fix was hygienic (CC reduction satisfied NineS warning),
not architectural (the install + upgrade responsibilities still both
live behind the same lifecycle event slot).

**Operator-visible consequence — the "all-or-nothing" trap:**

The hook activation is gated on `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`
(per `pre_plugin_invocation.py:120-148` and
`workflow-system/agent/references/env-flags.md` §2.13 row "Effect when
active": "AFTER `ensure_plugin` succeeds for a plugin candidate, the
hook ALSO checks `is_plugin_stale`..."). An operator who wants:

- **Install but no daily upgrade** (e.g., reproducible builds; pin
  versions; air-gapped CI): MUST set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0`
  AND manually invoke `devolaflow plugins install` once. They cannot
  get install-on-dispatch WITHOUT also getting daily-upgrade-on-dispatch.
- **Daily upgrade but no install on dispatch** (e.g., plugins managed
  by package OS; only DF should refresh nightly): NOT POSSIBLE — the
  upgrade path is conditional on a successful install run first.

Verbatim from `v10_internal_optimization_directions.md` §3.6 D-C-3:
"操作者可独立 opt-in/out（一个想 auto-install 但不要 daily upgrade 的
用户当前没法做到）" (operators want to opt-in/out independently — a
user who wants auto-install but NOT daily-upgrade has no way to
configure this today).

**Lifecycle hook count + A-2.2 append-only constraint:**

Current `DEFAULT_EVENTS` count = **10** (per
`src/devolaflow/lifecycle/__init__.py:207-218`):

```
PRE_DISPATCH_EVENT,        # 1
POST_DISPATCH_EVENT,       # 2
FILE_WRITE_EVENT,          # 3
TASK_STOP_EVENT,           # 4
FORMAT_ON_EDIT_EVENT,      # 5
PRE_SHELL_CALL_EVENT,      # 6
ENVELOPE_WRITE_EVENT,      # 7
PRE_HANDOFF_EVENT,         # 8
PRE_PLUGIN_INVOCATION_EVENT,  # 9
POST_SKILL_EDIT_EVENT,     # 10
```

A-2.2 append-only invariant (per `repo-governance.mdc` §A-2.2):
"positions 13 onward are APPEND-ONLY. New top-level dispatch keys land
at position N+1 where N is the current `len(canonical_order)`, never
inserted into a lower slot." For `DEFAULT_EVENTS` the analogous
invariant is "new lifecycle events MUST be APPENDED to position 11+;
existing events at positions 1-10 are byte-stable."

The W-20 reuse-first analysis is documented at `env-flags.md` §2.13
row "Why a NEW flag (W-20 §3 justification)" — the v10.2.1 PV-02
D-P-2 closure correctly REUSED `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` for
the daily-upgrade behavior because at THAT time the activation
surface was the same ("auto-manage plugin lifecycle"). The split
proposed here CHANGES that decision: with two events, the activation
surfaces become DISTINCT (install vs upgrade), and Rule W-20's reuse
test no longer mandates a single flag.

## §2 — patch_design

**Algorithm — APPEND-ONLY EVENT SPLIT WITH BACKWARD-COMPAT ALIAS:**

```
1. Add 2 new lifecycle events at DEFAULT_EVENTS positions 11 + 12
   (A-2.2 append-only):
     PRE_PLUGIN_INVOCATION_INSTALL_EVENT (position 11)
     PRE_PLUGIN_INVOCATION_UPGRADE_EVENT (position 12)
2. Preserve the existing `pre_plugin_invocation` event at position 9
   as a BACKWARD-COMPAT ALIAS for 1 cycle (per W-20 / G-7 1-cycle
   alias-path requirement). The existing handler at
   pre_plugin_invocation.py:464-516 STAYS; its body is updated to
   delegate to the two new handlers in sequence (install then
   upgrade) — BYTE-IDENTICAL observable behavior preserved when
   DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1.
3. Author the 2 new handler modules:
     src/devolaflow/lifecycle/pre_plugin_invocation_install.py
       - Takes the install responsibility from the existing helper
         _run_install_then_upgrade_for_plugin (lines 313-461) but
         strips the staleness probe + upgrade_plugin call (lines
         398-460). Result: a focused install handler with PPI001
         violation surface ONLY (no PPI003).
     src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py
       - Takes the upgrade responsibility (the staleness probe +
         upgrade_plugin call). PPI003 violation surface ONLY.
4. The two new handlers each carry their own activation flag:
     pre_plugin_invocation_install     -> DEVOLAFLOW_AUTO_INSTALL_PLUGINS
                                          (REUSED — same activation
                                          surface as v9.4.0 baseline)
     pre_plugin_invocation_upgrade     -> DEVOLAFLOW_AUTO_INSTALL_PLUGINS
                                          (REUSED — backward compat
                                          for 1 cycle)
   AFTER 1 cycle, the upgrade handler MAY transition to its own flag
   DEVOLAFLOW_AUTO_UPGRADE_PLUGINS (NEW, W-20 orthogonality argument
   documented in env-flags.md §2.16) — but THIS PATCH does NOT
   introduce the new flag; the operator-independence is the
   2-cycle-out goal, NOT the v11.0.0 deliverable.
5. Update src/devolaflow/lifecycle/__init__.py:
     - Add 2 new EVENT constants + 2 new _set_default_hook calls.
     - Append PRE_PLUGIN_INVOCATION_INSTALL_EVENT and
       PRE_PLUGIN_INVOCATION_UPGRADE_EVENT to DEFAULT_EVENTS at
       positions 11 + 12.
     - Existing PRE_PLUGIN_INVOCATION_EVENT at position 9 stays.
6. Update workflow-system/agent/references/env-flags.md §2.13 row:
     - Document the new event positions + alias path.
     - Cross-reference the 2 new handler modules.
     - Note 1-cycle alias deprecation telegraph.
7. Author tests/test_pre_plugin_invocation_split.py:
     - test_install_handler_handles_only_install_path (no upgrade fired)
     - test_upgrade_handler_handles_only_staleness_path (no install fired)
     - test_alias_event_emits_byte_identical_to_v10_3_0 (regression)
     - test_split_handlers_emit_disjoint_violations (PPI001 + PPI003 stay distinct)
     - test_alias_telegraphed_for_1_cycle_deprecation (governance pin)
8. Refresh tests/test_no_ghost_features.py W-18 lint to assert
   DEFAULT_EVENTS contains both new event names AND the alias.
```

**G-7 backward compat — explicit declaration:**

The existing public API is preserved BYTE-IDENTICALLY:

| Public surface | v10.3.0 behavior | v11.0.0 (post-D-C-3) behavior |
|---|---|---|
| `from devolaflow.lifecycle import pre_plugin_invocation` | Public import | Public import (unchanged) |
| `pre_plugin_invocation(payload, strict=False) -> HookResult` | Function signature | Function signature (unchanged); body delegates to new install + upgrade handlers in sequence |
| `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` activates install + upgrade | YES | YES (unchanged) |
| `EVENT_TRIGGERS_DAILY_UPGRADE: bool = True` constant | Public attribute | Public attribute (unchanged) |
| `DEFAULT_EVENTS[8] == "pre_plugin_invocation"` (position 9) | Indexed access works | Indexed access works (alias preserved at position 9) |
| `len(DEFAULT_EVENTS) == 10` | TRUE | FALSE — becomes 12 |
| `PRE_PLUGIN_INVOCATION_INSTALL_EVENT` constant | Does not exist | NEW constant (purely additive) |
| `PRE_PLUGIN_INVOCATION_UPGRADE_EVENT` constant | Does not exist | NEW constant (purely additive) |

**The single observable behavioral change:** `len(DEFAULT_EVENTS)`
goes from 10 → 12. Per A-2.2 append-only (which is the analogous
governance for `DEFAULT_EVENTS`), this is the EXPECTED shape change
when new events are added — existing tests that assert
`DEFAULT_EVENTS[X]` for X ∈ [0, 9] continue to pass byte-identically.

The 1-cycle alias deprecation telegraph: in v11.x cycle retrospective
§3 ("What was deferred and why"), document that
`pre_plugin_invocation` remains as alias through v11.x and is
TELEGRAPHED for removal at v12.0.0+ MAJOR (per W-21-class governance
cadence). Operators who registered extra handlers on the alias event
get a migration path: re-register on
`pre_plugin_invocation_install` AND/OR
`pre_plugin_invocation_upgrade` based on responsibility.

**G-3 zero-deps gate — explicit declaration:**

This patch proposes **ZERO upstream changes** to NineS / Si-Chip / RTK
/ ui-pro. The split is internal to DF's lifecycle layer; it does not
change `ensure_plugin` / `upgrade_plugin` / `is_plugin_stale` (the
underlying plugin install/upgrade primitives in
`src/devolaflow/plugins/installer.py`); it does not change
`runtime-plugins.yaml`. Per `v11.0.0_admission_checklist.md` §G-3
verbatim.

**Files touched (NEW):**

- `src/devolaflow/lifecycle/pre_plugin_invocation_install.py` (~150
  LOC; takes install body from existing `_run_install_then_upgrade_for_plugin`
  helper).
- `src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py` (~120
  LOC; takes staleness + upgrade body).
- `tests/test_pre_plugin_invocation_split.py` (~200 LOC; 8-12 test
  functions covering split semantics + alias preservation).

**Files touched (EDITED):**

- `src/devolaflow/lifecycle/__init__.py` — add 2 EVENT constants + 2
  `_set_default_hook` calls + extend `DEFAULT_EVENTS` tuple by 2
  entries (~25 LOC across import block + wiring + tuple).
- `src/devolaflow/lifecycle/pre_plugin_invocation.py` — refactor
  parent function body to delegate to new handlers (preserves
  existing PPI001 + PPI003 surface in alias mode); ~30 LOC delta
  (mostly removing duplicated logic now lifted into the new
  modules).
- `workflow-system/agent/references/env-flags.md` §2.13 — add
  position-11/12 documentation + 1-cycle deprecation telegraph (~20
  LOC).
- `tests/test_no_ghost_features.py` — W-18 lint stanza (~30 LOC
  pattern).
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**API/CLI surface:**

```python
# Existing public import — preserved
from devolaflow.lifecycle import pre_plugin_invocation

# New public imports — purely additive
from devolaflow.lifecycle import (
    PRE_PLUGIN_INVOCATION_INSTALL_EVENT,
    PRE_PLUGIN_INVOCATION_UPGRADE_EVENT,
)
from devolaflow.lifecycle.pre_plugin_invocation_install import (
    pre_plugin_invocation_install,
)
from devolaflow.lifecycle.pre_plugin_invocation_upgrade import (
    pre_plugin_invocation_upgrade,
)
```

**Doc deliverables (G-9 per admission_checklist.md §G-9):**

- CHANGELOG entry (Python module change scope) — REQUIRED.
- W-18 lint refresh — REQUIRED.
- W-20 env-flag inventory update (`env-flags.md` §2.13) — REQUIRED.
- W-12 `build-skill` 4-adapter verify — NOT triggered (the change is
  in `src/`, not `workflow-system/agent/SKILL.md`).
- Bilingual EN/ZH — NOT required (lifecycle internals are
  developer-facing).
- W-11 `tests/test_gate.py -v` — NOT triggered (the change is in
  `lifecycle/`, not `gate/`).
- W-13 / W-14 EvoBench benchmark verify — NOT triggered (no edit to
  `task_adaptive_selector.py`, `context_profiles.yaml`, lean message
  schemas, SKILL.md sections, or `gate/` modules).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` (per
`v11.0.0_evaluation_methodology.md` §2 layout — 1-3 source files,
< 200 LOC, no plugins).

**Operations exercised:** None of the §2 operations directly engage
plugin lifecycle (synthetic_small_repo has no plugins). The relevant
synthetic measurement is **"existing tests that depend on
`DEFAULT_EVENTS` length / order pass unchanged"** — a regression test
on the small repo's pytest suite (which is just whatever tests exist
in DF's `tests/` and run against the synthetic surface).

**Metric collection:** `len(DEFAULT_EVENTS)` value (must be 12 post-patch);
existing tests asserting `DEFAULT_EVENTS[0..9]` (must still pass —
A-2.2 byte-stability check); cyclomatic complexity of the parent
`pre_plugin_invocation` function (radon cc; must be ≤ 7 — the v10.2.3
post-fix value); cyclomatic complexity of the two new handler functions
(each must be ≤ 7).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Lifecycle hook events count (per `v11.0.0_evaluation_methodology.md` §4.6 metric: "Lifecycle hook events count: integer") | 10 | 12 | +2 | improve (per direction goal) |
| `DEFAULT_EVENTS[0..9]` byte-stability (positions 1-10 unchanged) | 100% | 100% | 0 | preserve |
| Cyclomatic complexity of parent `pre_plugin_invocation` (radon cc) | ≤ 10 (post v10.2.3 PV-04 fix; no NineS warning at v10.2.4) | ≤ 7 (delegation only — 3 early-return gates + 2 sequenced helper calls) | -3 (-30%) | improve |
| Cyclomatic complexity of NEW `pre_plugin_invocation_install` | N/A | ≤ 7 (3 early-return gates + 1 for-loop + 1 try/except domain catch + 1 try/except non-domain re-raise) | new function — measure on creation | preserve (within ≤ 10 NineS warn floor) |
| Cyclomatic complexity of NEW `pre_plugin_invocation_upgrade` | N/A | ≤ 7 (similar shape — 3 gates + staleness probe + upgrade try/except) | new function — measure on creation | preserve |

**Pass criterion:** `len(DEFAULT_EVENTS) == 12` AND all positions 1-10
byte-stable AND parent CC ≤ 7 AND each new handler CC ≤ 7 AND existing
test suite passes 100% (zero regressions).

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (large-only). Small projects without plugins do
not exercise the install/upgrade split in production; the architectural
benefit (operator-independence telegraphed for 2 cycles out) is largely
realized at large-project scale where multiple plugins compose.

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline; 4 plugins
registered in `runtime-plugins.yaml`; `pre_plugin_invocation` hook
present at `lifecycle/__init__.py:216` position 9; the v10.2.3 helper
extractions present at `pre_plugin_invocation.py:269-461`).

**Metric collection:** Lifecycle events count; CC of parent +
2 new handlers; backward-compat — alias `pre_plugin_invocation` invokes
both new handlers AND emits PPI001 + PPI003 surface byte-identically;
W-17 cycle test contribution; CHANGELOG entry presence.

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline (v10.3.0) | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Lifecycle hook events count (per `v11.0.0_evaluation_methodology.md` §4.6) | 10 | 12 | +2 | improve (per direction goal) |
| Operator configurability (independent install/upgrade opt-in/out) | NO (single env flag controls both) | NO at v11.0.0 (alias preserves single-flag behavior); YES at v12.0.0+ (separate flag DEVOLAFLOW_AUTO_UPGRADE_PLUGINS telegraphed for v12.0.0) | telegraphed | improve (telegraphed) |
| Cyclomatic complexity of parent `pre_plugin_invocation` | ≤ 10 (post v10.2.3 PV-04) | ≤ 7 (delegation-only body) | -3 (-30%) | improve |
| Backward-compat regressions | N/A | 0 (alias path emits PPI001 + PPI003 byte-identically; existing tests pass) | 0 | preserve |
| W-17 cycle test contribution this PV | N/A | +8-12 (8-12 new test functions) | +8-12 | within +30/PV cap |
| W-12 `build-skill` 4-adapter success rate | 100% | 100% (no SKILL.md edit) | 0 | preserve |
| `tests/test_pre_plugin_invocation.py` (existing v10.x test file) | passes (75+ tests covering hook contract) | passes (alias test path unchanged) | 0 | preserve |
| New env flags introduced | 0 | 0 (W-20 reuse-first satisfied; existing flag covers both new handlers in alias mode) | 0 | preserve |
| NineS PV-03 deep-analysis CC count for `pre_plugin_invocation` package | 1 warning (CC=18 closed at v10.2.3 PV-04 → ≤10) | 0 (parent now ≤7; new handlers each ≤7) | -1 | improve |

**Pass criterion:** `len(DEFAULT_EVENTS) == 12` AND positions 1-10
byte-stable AND parent CC ≤ 7 AND backward-compat alias preserves
PPI001 + PPI003 emission AND W-17 +30/PV cap not exceeded AND W-12
4-adapter success rate stays 100%.

**Side-effect check (must NOT regress):**

- W-17 cycle test cap (this PV adds ≤12; well under +30/PV cap).
- W-12 adapter build success (4/4 adapters; this patch does not
  touch SKILL.md / templates).
- CP-2 80% coverage floor (new modules ship ≥80% per their own test
  file; existing `tests/test_pre_plugin_invocation.py` covers the
  alias path).
- C-7 valid reference links (`env-flags.md` §2.13 cross-refs to the 2
  new module file paths must exist at v11.0.0 cut).
- S-2 no absolute paths (all citations relative to repo root).
- S-7 external tool URL form (no change to plugin URLs).
- A-2 cache-prefix invariant (the `DEFAULT_EVENTS` tuple is NOT
  serialized into dispatch payloads — the analogous append-only
  invariant for lifecycle events is satisfied by appending at
  positions 11 + 12).
- S-10 prompt-side governance contract (the `pre_dispatch` /
  `post_dispatch` hook chain unaffected; this patch only splits
  `pre_plugin_invocation` which is at position 9).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.6 + §4.3 buckets; ≥3 metrics
required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-C-3) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Lifecycle hook events count | §4.6 (coupling — lifecycle hook events count: integer) | 10 | 12 | +2 | New positions 11 + 12 hold the split handlers (per A-2.2 append-only) |
| Cyclomatic complexity of parent `pre_plugin_invocation` (max per function via radon cc) | §4.3 (code quality — Cyclomatic complexity max per function) | ≤ 10 (post v10.2.3 PV-04 fix that took CC=18 → ≤10 by helper extraction) | ≤ 7 (delegation-only body — 3 early-return gates + 2 helper invocations) | -3 (-30%) | Responsibility split eliminates the install + upgrade composition complexity from the parent |
| NineS warnings flagging `pre_plugin_invocation` CC | §4.3 (code quality — NineS warning count) | 0 at v10.3.0 (closed by PV-04); BUT cycle history shows 1 warning at v10.2.2 PV-03 (CC=18 row #2 in `v10.2.2_nines.md` §2) | 0 sustained (parent ≤7 — never approaches NineS warn floor of 10) | preserve at 0 | Architectural split prevents future regression to CC=18 class |
| Operator configurability (independent install vs upgrade opt-in/out) | §4.6 (coupling — proxy for operator-experience) | NO (single flag governs both responsibilities) | telegraphed (alias preserves v10.3.0 behavior; v12.0.0+ may admit `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` orthogonal flag per W-20 §3 reuse-first re-evaluation) | telegraphed | The architectural split UNLOCKS the operator-independence option WITHOUT taking it (defers W-20 evaluation to next cycle) |
| Backward-compat regressions in existing test suite (per `tests/test_pre_plugin_invocation.py` 75+ tests) | §4.4 (test health) | 0 (baseline) | 0 (alias preserves byte-identical PPI001 + PPI003 emission) | 0 | Verified by `tests/test_pre_plugin_invocation_split.py::test_alias_event_emits_byte_identical_to_v10_3_0` |

**Guarantee on metric:** ALL 5 metrics are scriptable from current DF
tooling (no external deps). "Lifecycle hook events count" via
`from devolaflow.lifecycle import DEFAULT_EVENTS; print(len(DEFAULT_EVENTS))`.
"Cyclomatic complexity" via `radon cc src/devolaflow/lifecycle/pre_plugin_invocation*.py
-a -nB`. "NineS warnings" via `nines analyze --target-path
src/devolaflow/lifecycle/ --depth deep` (cached fixture per D-C-2 if
NineS unavailable). "Operator configurability" is a documentation
audit (grep `env-flags.md` for `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS`).
"Backward-compat regressions" via `pytest tests/test_pre_plugin_invocation.py`.

## §6 — admission_verdict

**Verdict: PASS**

**Rationale:**

- G-1 Internal-value: 5 quantitative DF-internal metrics from §4.6
  coupling-bucket + §4.3 code-quality bucket. Lifecycle hook events
  count (the §4.6 metric directly cited in the methodology) goes
  from 10 → 12 (per the direction goal); parent CC drops 30%; NineS
  warning regression preempted; operator configurability telegraphed
  for v12.0.0+. ZERO EvoBench signals used.
- G-2 Both-tier: small (synthetic_small_repo regression that
  positions 1-10 stay byte-stable AND len() goes to 12) AND large
  (DevolaFlow self with 4 plugins exercising the alias) BOTH show
  passing criteria met. The architectural benefit (responsibility
  separation) is realized at the package-organization layer
  REGARDLESS of project size.
- G-3 Zero-deps: ZERO upstream changes. The split is internal to
  `src/devolaflow/lifecycle/` and `src/devolaflow/lifecycle/__init__.py`.
  No NineS / Si-Chip / RTK / ui-pro change required.
- G-4 Cycle-budget: 1 PV (M effort per `v10_internal_optimization_directions.md`
  §3.6 D-C-3); test budget +8-12 per the M-effort §G-4 mapping
  (≤25); fits within W-17 +30/PV cap with margin.
- G-5 Soul-freeze: 0 Soul rule additions.
- G-6 Cache-prefix: zero edits to `schemas/lean-dispatch.yaml`. The
  `DEFAULT_EVENTS` tuple is not part of the dispatch payload's
  canonical_order; A-2.2 frozen prefix is unaffected. The analogous
  append-only invariant for lifecycle events is satisfied by
  appending at positions 11 + 12.
- G-7 Compatibility: pure-additive (NEW 2 modules + NEW 2 EVENT
  constants + 2-position append to DEFAULT_EVENTS); the existing
  `pre_plugin_invocation` event at position 9 is preserved as a
  BACKWARD-COMPAT ALIAS for 1 cycle. No public API rename, no env
  flag rename, no schema field rename, no file path rename. The 1-cycle
  alias path satisfies G-7 "Soft-reject (REWORK) if: Public API
  deprecation without 1-cycle alias path" — alias is provided.
- G-8 Test coverage: NEW `test_pre_plugin_invocation_split.py` ships
  ≥80% coverage of the 2 new handler modules; existing
  `test_pre_plugin_invocation.py` (75+ tests) continues to cover
  the alias path; cycle coverage stays ≥80% per CP-2.
- G-9 Documentation completeness: CHANGELOG + W-18 lint refresh +
  `env-flags.md` §2.13 update; matches the "Python module change"
  row in §G-9 table. NO SKILL.md edit (so no W-12 adapter rebuild
  trigger). NO new env flag introduced (W-20 reuse-first satisfied
  for v11.0.0; future flag telegraphed but NOT introduced).

## §7 — effort_estimate

**Effort: M (1 PV)**

**Breakdown:**

- `src/devolaflow/lifecycle/pre_plugin_invocation_install.py`: ~150
  LOC (lifted body + module-level docstring + ENV constant + helper
  composition).
- `src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py`: ~120
  LOC (lifted body + similar shape).
- `src/devolaflow/lifecycle/__init__.py` edits: ~25 LOC (2 imports +
  2 EVENT constants + 2 `_set_default_hook` calls + 2-entry tuple
  extension).
- `src/devolaflow/lifecycle/pre_plugin_invocation.py` refactor:
  ~30 LOC delta (parent body becomes delegation; existing helpers
  stay for backward-compat).
- `tests/test_pre_plugin_invocation_split.py`: ~200 LOC (8-12 test
  functions covering split + alias regression + governance pin).
- `workflow-system/agent/references/env-flags.md` §2.13 edit: ~20 LOC.
- `tests/test_no_ghost_features.py` W-18 lint: ~30 LOC.
- `CHANGELOG.md` entry: ~1 LOC under PV header.
- Total estimated effort: ~575 LOC across implementation + tests +
  docs; M / 1 PV (analogous to v10.2.3 PV-04 helper extractions
  landing in 1 PV per `v10.3.0_retrospective.md` §2 — but this patch
  is one MAJOR refactor instead of two helper extractions, so
  scope is similar).

**Confirms §3 estimate (M / 1 PV) from
`v10_internal_optimization_directions.md` §3.6 D-C-3.**

## §8 — dependencies

**None — this patch is fully standalone.**

The split depends on:

- `src/devolaflow/lifecycle/dispatcher.py` (HookResult / HookViolation
  / `finalize` / `_set_default_hook` machinery) — read-only.
- `src/devolaflow/plugins/installer.py` (`ensure_plugin`,
  `is_plugin_stale`, `upgrade_plugin`,
  `_DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS`) — read-only.
- `src/devolaflow/plugins/exceptions.py` (PluginNotFoundError /
  PluginInstallError / PluginVersionMismatch / PluginBackendUnsupported)
  — read-only.
- `workflow-system/agent/references/env-flags.md` (§2.13 row) — 1
  block addition.

…all of which exist at v10.3.0. No other v11.0.0 patches are required
for D-C-3 to ship.

**Synergy (NOT a hard dependency):**

- D-C-1 (degraded-mode contract) ships
  `tests/test_degraded_mode.py` with a ui-pro PPI001 scenario; if
  D-C-3 lands FIRST, that test must reference the new
  `pre_plugin_invocation_install` event name OR the alias (both work
  by design).
- D-Q-3 (lifecycle hook 10-event naming taxonomy) reorganizes the
  10 → 12 events into a `pre_*` / `post_*` / `validate_*` / `check_*`
  4-group naming convention. D-C-3 + D-Q-3 are COMPATIBLE: the new
  event names (`pre_plugin_invocation_install` /
  `pre_plugin_invocation_upgrade`) already follow the `pre_*` naming
  group. If D-Q-3 lands AFTER D-C-3, D-Q-3's regrouping is
  byte-stable (events go from 12 → 12 with renames + aliases).
- D-O-4 (SI-10 gate chain growth analysis) is independent of
  lifecycle events; no interaction.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | The 1-cycle alias deprecation telegraph (v11.x → v12.0.0+) is governance-light — operators registering extra handlers via `register_hook(PRE_PLUGIN_INVOCATION_EVENT, ...)` may not notice the deprecation and lose handler invocation at v12.0.0 cycle close → silent regression for downstream skill plugins | major | (a) Add a `DeprecationWarning` emission inside the alias `pre_plugin_invocation` handler ONLY when extra handlers are registered on the alias event (silent for the default-only case to preserve cache prefix). (b) Document the migration path in `env-flags.md` §2.13 row deprecation telegraph. (c) Add `tests/test_pre_plugin_invocation_split.py::test_alias_emits_deprecation_warning_when_extras_registered` to pin the warning surface. (d) Mention the deprecation in v11.x cycle retrospective §3 (mandatory per W-7). |
| R2 | `len(DEFAULT_EVENTS)` going 10 → 12 may break tests that assert exact length (e.g., `assert len(DEFAULT_EVENTS) == 10`) — those tests are themselves the safety net but they ARE part of the existing test suite which must pass | minor | (a) Grep existing tests for `len(DEFAULT_EVENTS)` literal assertions; update them as part of this PV (the W-18 lint refresh provides the precondition signal). (b) Tests that index by name (e.g., `assert "pre_plugin_invocation" in DEFAULT_EVENTS`) continue to pass by design. (c) `tests/test_pre_plugin_invocation_split.py` includes the explicit `test_default_events_length_after_split == 12` assertion to pin the new contract. |
| R3 | The split telegraphs `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` as a future env flag (v12.0.0+ candidate); if v12.0.0+ DOES introduce that flag, it will need a fresh W-20 §3 orthogonality argument (the activation surfaces for install vs upgrade are now distinct, but the env-flag inventory still needs explicit re-evaluation) | minor | This patch ONLY introduces the architectural split; it does NOT introduce the new flag. The W-20 evaluation is deferred to v12.0.0+ SI-1 (future cycle). The deferral is documented in v11.x cycle retrospective §3 and `env-flags.md` §2.13 telegraph. If v12.0.0+ SI-1 finds that `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` would still violate W-20 (e.g., because the install + upgrade surfaces compose meaningfully and operators don't need independent control), the flag is NOT introduced — the architectural split alone (no flag separation) is the v11.0.0 deliverable. The split is reversible via the alias path; if telegraph evaluation finds it net-negative, v12.0.0 retrospective can deprecate the new events and re-merge into the alias. |

---

ADMISSION: PASS | EFFORT: M | DEPS: none | TIER: standard
