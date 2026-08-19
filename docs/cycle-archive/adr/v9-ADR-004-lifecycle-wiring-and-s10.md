# v9-ADR-004 — Lifecycle Wiring + Soul Rule S-10 + ArchiveManager.apply_merge + REPORT.md auto-trigger

* **Status**: Accepted
* **Date**: 2026-04-24
* **Cycle**: v9.0.0 PV-04 (`v8.4.4` PATCH)
* **Cycle role**: Closes 3 long-standing gaps in a single coordinated PATCH and
  promotes the wiring discipline into the Soul-set as Rule S-10
  ("Prompt-Side Governance Contract Embedding"). Closes **C-03** (lifecycle
  wiring + S-10) + **M-004** (`ArchiveManager.apply_merge`) + **I-PV07-A**
  (REPORT.md auto-trigger) of `.local/research/v9.0.0_gap_analysis.md` §3.1.
* **Predecessor ADRs**:
  * `v9-ADR-003` (A-5 SSOT registry) — sister PATCH ADR; both promote
    informal practice into binding rules.
  * `v9-ADR-002` (cache-layout governance v2) — A-2.4 multi-baseline byte
    test stays green across this ADR's changes (no canonical_order edits).
  * `.local/research/v8.4.0_retrospective.md` §4.1 #4 — the R5 strict
    pattern this ADR re-applies for the lifecycle-hook injection.
  * v6.0.3 retro precedent — cited verbatim as the highest-ROI dead-wire
    fix in DevolaFlow history; PV-04 mirrors that precedent for the
    `pre_dispatch` lifecycle hook.
* **Branch**: `feat/v8.4.4-lifecycle-wiring-and-s10`

---

## Context

Three independent gaps were tracked through v9.0.0 SI-1 with overlapping
file scope and shared verification surface:

### C-03 — Dead-wire in dispatch emission

`src/devolaflow/lifecycle/__init__.py` has registered the `pre_dispatch`
event with `validate_dispatch` (default) + `validate_owned_files` (extra)
since v7.0.x. Yet the canonical dispatch emission point —
`src/devolaflow/feedback.py::ProposalGenerator.generate_round_dispatch`
— never invoked `lifecycle.run_hooks("pre_dispatch", dispatch, ...)` on
any of its 3 return paths. Round-N+1 dispatches flowed straight from
`merge_reinforcement_into_dispatch` to L3 task agents without
acceptance-criteria validation, schema compliance, or owned-files checks.

The root cause was documented in `references/plan-mode-enforcement.md`
§9.2 lines 466-467 as "dispatch event emission + `pre_dispatch` /
`post_dispatch` hook orchestration" — aspirational text describing a
contract that the implementation never honored. The v9.0.0 SI-1 reference
review flagged this as **C-03 BLOCKER** because:

* Every L3 task agent receives a dispatch payload that bypasses the
  prompt-side enforcement surface — schema drift, missing acceptance
  criteria, and owned-file violations all reach L3 silently.
* The hook chain is the canonical pattern for prompt-side governance
  contracts (Soul-set version embedding, rule-manifest URLs,
  reinforcement state) — none of which can be validated until the
  emission point fires the hook.
* The dead-wire mirrors the v6.0.3 retro's highest-ROI precedent, which
  established the principle: "if a contract surface exists but no
  caller invokes it, the contract effectively does not exist".

### M-004 — ArchiveManager.apply_merge deferred since v8.2.5

`src/devolaflow/agent_workspace/archive.py::ArchiveManager.propose_merge`
shipped in v8.2.5 with the explicit "write side ships in v8.2.7 reporter"
deferral. The v8.2.7 reporter shipped (`reporter.py`) but the write side
never landed — `propose_merge` returns a `ProposedMerge` dataclass
carrying the merged content, but no caller writes it to disk. Per
A-4 ADR (`.cursor/rules/repo-governance.mdc` §"A-4 — Source-of-Truth
Spec Location"), source-of-truth specs are mutated ONLY at archive time
AFTER the gate has PASSED — without `apply_merge`, the source-of-truth
update lifecycle is dead-wired in the same way as C-03.

### I-PV07-A — REPORT.md auto-trigger deferred since v8.2.7

The v8.2.7 reporter module ships 4 render functions
(`render_change_report`, `render_workspace_report`, `render_memory_report`,
`render_rules_report`) plus the `regenerate_all` orchestrator. All are
documented as opt-in: "existing workflows do NOT auto-trigger them"
(reporter.py docstring). The CLI `python -m devolaflow.agent_workspace
.reporter --all` is the only caller in the v8.4.3 baseline — so
archiving a change leaves the per-archive `REPORT.md` and the
workspace-wide `.local/.agent/REPORT.md` stale until an operator
remembers to invoke the CLI.

### Why coordinate the 3 closures in one PATCH

All three gaps share the dispatch / archive lifecycle as the integration
surface:

* C-03 fires on every dispatch emission.
* M-004 fires on every archive (with the gate ≥ 8.5 / ≥ 9.0 guard).
* I-PV07-A fires on every archive (independent of the gate).

Coordinating the 3 closures in one PATCH lets us:

1. Land them with a single SI-3 evaluation pass (one set of risk
   recalibrations).
2. Promote the lifecycle wiring discipline into the Soul-set (Rule S-10)
   in the same PR — Soul-set additions are always release-blocking
   under W-3 / SI-3, so they need their own evaluation cycle.
3. Honor the v8.4.0 retro §4.1 #4 R5 strict pattern in one place — all
   3 closures preserve byte-identical existing behavior when extras /
   gates / opt-out flags decline the new path.

---

## Decision

### D1 — Wire `pre_dispatch` + `post_dispatch` hooks into `feedback.py`

`src/devolaflow/feedback.py::ProposalGenerator.generate_round_dispatch`
now routes EVERY return path through a private helper
`_emit_dispatch(dispatch)` that invokes
`lifecycle.run_hooks("pre_dispatch", dispatch, strict=False)` followed
by `lifecycle.run_hooks("post_dispatch", dispatch, strict=False)`. The
helper:

* Catches any exception raised by a custom hook handler, logs it at
  WARNING level via `logger.warning`, and returns the dispatch
  unchanged. S-5 (no silent failures) — the failure is logged; the
  dispatch path stays resilient.
* Uses permissive mode (`strict=False`) — violations only emit
  WARNINGs; the round-N+1 dispatch never raises out of the emission
  path, even when the dispatch is malformed (the existing handler
  contract is preserved).

### D2 — Codify Soul Rule S-10 (Soul-set 9 → 10)

`.rules/soul.mdc` gains a new ## S-10 section codifying the wiring
discipline:

> Every dispatch payload returned by
> `src/devolaflow/feedback.py::ProposalGenerator.generate_round_dispatch`
> MUST be visible to the lifecycle hook chain
> (`pre_dispatch` → `post_dispatch`) via
> `devolaflow.lifecycle.run_hooks(event, payload, strict=False)`.

The rule lifts the wiring from "implementation detail" to "Soul-set
invariant", protecting future refactors from regressing the dead-wire.
S-10 is enforced by the regression test
`tests/test_dispatch_emission_runs_hooks.py` (3 invocation tests + 3
R5 byte-identical tests + 1 handler-exception swallowing test).

### D3 — `ArchiveManager.apply_merge` (M-004 / A-4 closure)

`src/devolaflow/agent_workspace/archive.py::ArchiveManager.apply_merge`
wraps `propose_merge` with the gate-threshold check and an atomic
write:

```python
def apply_merge(
    self,
    change_id: str,
    *,
    is_major_change: bool = False,
    require_gate_score: float | None = None,
) -> AppliedMerge:
    proposal = self.propose_merge(change_id)
    change = self.store.get(change_id)
    gate_score = float(change.status["gate_score"])
    threshold = require_gate_score or (
        GATE_THRESHOLD_MAJOR if is_major_change else GATE_THRESHOLD_DEFAULT
    )
    if gate_score < threshold:
        raise GateThresholdNotMet(...)
    # Atomic write via .tmp sibling + POSIX rename.
    tmp = applied_path.with_suffix(applied_path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(applied_path)
    return AppliedMerge(...)
```

Defaults: `GATE_THRESHOLD_DEFAULT = 8.5` (PATCH/MINOR), `GATE_THRESHOLD_MAJOR
= 9.0`. Both align with W-3 / SI-3 composite thresholds.

The atomic write uses a `.tmp` sibling + POSIX `rename` so readers
never see a half-written spec. On Windows the rename is a non-atomic
copy+delete — accepted because DevolaFlow's primary deployment is
POSIX.

### D4 — REPORT.md auto-trigger via `archive()` opt-in default

`ArchiveManager.archive` gains a new keyword argument
`auto_regenerate_reports: bool = True` (defaults to `True` per I-PV07-A
closure). When True, the helper `_auto_regenerate_reports(change_id,
archive_path)` runs at the end of the archive sequence (after
consolidation and optional `propose_merge`):

* Renders the per-change REPORT.md to `<archive_path>/REPORT.md`.
* Renders the workspace-wide REPORT.md to
  `.local/.agent/REPORT.md`.
* Both renders are wrapped in try/except blocks that log failures at
  WARNING but never raise — REPORT.md is a presentation surface, not
  an integrity contract.

Tests pin the auto-trigger via
`TestArchiveAutoRegenerateReports::test_archive_auto_regenerates_per_change_report`
and the opt-out via
`test_archive_opt_out_skips_report_regen` (so existing tests that need
byte-pinned filesystem state can pass `auto_regenerate_reports=False`).

---

## R5 Strict Triple Codification

Per the v8.4.0 retro §4.1 #4 R5 strict pattern, this ADR ships 3
codifications (hook + schema + test) that together preserve
byte-identical existing behavior when no extras / opt-out flags decline
the new path:

| Codification | Owner module | Test |
|---|---|---|
| Hook | `src/devolaflow/lifecycle/__init__.py::DEFAULT_EVENTS` (length 5 → 6 with `post_dispatch` no-op default) | `tests/test_lifecycle_hooks.py::test_default_events_match_skill_md_table` |
| Schema | `src/devolaflow/feedback.py::ProposalGenerator._emit_dispatch` (3 call sites for the 3 return paths) | `tests/test_dispatch_emission_runs_hooks.py::TestHookInvocation` (3 tests) |
| Test | `tests/test_dispatch_emission_runs_hooks.py::TestR5ByteIdentical` (3 control comparisons against pre-PV-04 deepcopy + `merge_reinforcement_into_dispatch`) | self-pinning |

The triple guarantees that a future refactor cannot regress C-03
without breaking at least one of the 3 codifications.

For M-004 (D3): `apply_merge` is a NEW public surface — no R5 strict
backward-compat concern for existing callers (they all use
`propose_merge`, which is unchanged).

For I-PV07-A (D4): the opt-out `auto_regenerate_reports=False` is the
backward-compat escape valve. Existing tests that would be affected by
auto-regenerated REPORT.md files set the flag to False in their
fixtures; the `TestApplyMerge` class follows this convention.

---

## Rationale

### Why hook indirection (vs direct call)

Three alternatives were considered for D1:

1. **Direct `validate_dispatch(dispatch)` call from `feedback.py`** —
   simplest implementation but couples `feedback.py` to one specific
   handler. Rejected: future governance contracts (S-10's PV-07
   handler) would require a second direct call site, then a third,
   etc.
2. **Hook indirection via `lifecycle.run_hooks`** — the chosen design.
   Adds one indirection but keeps `feedback.py` decoupled from the
   handler list. The `_set_default_hook` + `register_hook` pattern
   already supports plugin-style additions.
3. **Hook indirection + per-feature feature flag** — rejected: feature
   flags add lifecycle complexity (deprecation timeline, rollout
   plan). The permissive default + try/except wrapper achieves the
   same risk profile (zero behaviour change when no extras register)
   without the lifecycle overhead.

### Why `post_dispatch` (vs reusing `pre_dispatch`)

S-10 is best codified as TWO slots:

* `pre_dispatch` — validates dispatch CONTENT (existing semantics:
  acceptance criteria, owned files, schema compliance).
* `post_dispatch` — future-extensibility slot for governance contracts
  (Soul-set version embedding, rule-manifest URL, reinforcement state)
  that fire AFTER content validation but BEFORE the dispatch is
  released to the consumer.

Reusing `pre_dispatch` for both content + governance would conflate
the two concerns and force every governance handler to inspect the
payload first to decide whether to act. The new `post_dispatch` slot
ships with a permissive no-op default in `lifecycle/post_dispatch.py`
so the actual handler can land in PV-07 with the rule-corpus
selectivity slice (per V-PV07-A) without re-touching `DEFAULT_EVENTS`.

### Why threshold defaults (8.5 / 9.0)

D3's gate-threshold defaults match W-3 / SI-3:

* PATCH/MINOR change → composite ≥ 8.5
* MAJOR change       → composite ≥ 9.0

These are the same thresholds the gate enforces for release-blocking
SI-3 evaluations. Using a different threshold for `apply_merge` would
create a confusing two-tier policy where a change can pass W-3 / SI-3
but fail `apply_merge` (or vice versa). The single threshold preserves
the principle "the gate is the single source of truth for change
quality".

The `require_gate_score: float | None = None` parameter is the
explicit override path for callers with custom gate policies (e.g. a
research workflow that uses ≥ 7.0 as its release bar).

### Why opt-in default `True` for REPORT.md auto-trigger

Three options for D4:

1. **Opt-in default `False`** — existing behavior; reporter is opt-in.
   Rejected: defeats the whole point of I-PV07-A (the gap is that
   REPORT.md is stale by default; flipping the default keeps it
   stale).
2. **Opt-in default `True` + opt-out flag** — the chosen design.
   Honors I-PV07-A while letting tests + scripts that need pinned
   filesystem state opt out. The opt-out is documented in the
   `archive()` docstring AND in the test class docstring, so future
   maintainers can find the escape valve.
3. **Always on, no opt-out** — rejected: tests like
   `TestApplyMerge.test_apply_merge_atomic_via_tmp` need
   `_auto_regenerate_reports` NOT to fire (they need exclusive
   control over the on-disk state under `tmp_path`).

---

## Consequences

### Positive

* Closes 3 BLOCKER gaps in a single PATCH (C-03 + M-004 + I-PV07-A).
* Promotes wiring discipline into the Soul-set (S-10) — protected by
  release-blocking SI-3 evaluation under W-3.
* Maintains R5 byte-identical existing behavior when no extras
  register / `is_major_change=False` / `auto_regenerate_reports=True`
  (defaults preserve all existing callers).
* Adds 21 net new tests (8 dispatch-emission + 11 agent-workspace +
  2 lifecycle-hooks); under the test cap forecast of +20 tests.
* Reduces "stale REPORT.md" operator surprise — every archive now
  emits both per-change and workspace-wide REPORT.md as a side effect.

### Negative

* 5 file touch radius for the lifecycle wiring (`feedback.py` +
  `lifecycle/__init__.py` + `lifecycle/post_dispatch.py` +
  `lifecycle/dispatcher.py` (no edit, just re-imported) +
  `tests/test_lifecycle_hooks.py`). Each is small but the breadth
  raises code-review surface.
* `+1` Soul rule (S-10) raises Soul-set surface from 9 to 10. Per
  C-09 governance the Soul-set is a binding gate; future Soul-set
  additions need same-rigour SI-3 evaluation. Mitigated by the
  v9.0.0 SI-1 forecast that Soul-set adds ≤ 60 cap-aware (current 10
  / 60).
* `apply_merge` introduces a new public exception class
  (`GateThresholdNotMet`); callers must handle it explicitly per
  S-5 (no silent failures). Suppressed N818 lint per the
  established `MergeConflict` precedent (parent class
  `ArchiveError` carries the suffix).

### Carry-forward

* The `post_dispatch` permissive no-op default ships in v8.4.4; the
  actual governance-contract handler lands in **PV-07** with the
  rule-corpus selectivity slice (V-PV07-A). PV-07 will register the
  governance handler as an extra on `post_dispatch` via
  `register_hook(POST_DISPATCH_EVENT, governance_contract_check)` —
  no edits to `DEFAULT_EVENTS` needed.

---

## Alternatives Considered

### Alternative 1 — Land C-03 only, defer M-004 + I-PV07-A

* **Pros**: smaller PR; isolated risk for C-03.
* **Cons**: 3 SI-3 evaluation cycles instead of 1; M-004 + I-PV07-A
  carry-forward to PV-05/PV-07 raises the chance they get bumped to
  PV-08 or v10.0.0.
* **Verdict**: rejected because the 3 closures share the dispatch /
  archive lifecycle as the integration surface — coordinating them
  amortizes the SI-3 cost.

### Alternative 2 — Land S-10 as `informational` first, promote in PV-05

* **Pros**: lets PV-04 ship without Soul-set surface change.
* **Cons**: reverses the v6.0.3 retro precedent (lifting wiring into
  Soul-set is precisely how DevolaFlow protects against future
  dead-wires).
* **Verdict**: rejected because the regression test
  `tests/test_dispatch_emission_runs_hooks.py` already pins the
  invariant — promoting to Soul-set is the cheapest way to raise the
  protection level (Soul-rule == release blocker via W-3 / SI-3).

### Alternative 3 — Auto-trigger REPORT.md inside the reporter CLI instead of `archive()`

* **Pros**: keeps the reporter standalone; archive() stays focused.
* **Cons**: requires the operator to run the CLI after every archive
  — exactly the opt-in pattern I-PV07-A is meant to eliminate.
* **Verdict**: rejected; the opt-in pattern is the bug, not the
  feature.

### Alternative 4 — Ship `apply_merge` write side as a separate `apply.py` module

* **Pros**: smaller `archive.py` diff; cleaner separation.
* **Cons**: callers would need to import from two modules
  (`archive.ArchiveManager` for `archive()` + `propose_merge()`,
  `apply.ApplyManager` for `apply_merge()`). The whole point of
  `ArchiveManager` is to be the single entry point for the archive
  lifecycle.
* **Verdict**: rejected; `apply_merge` is a method on `ArchiveManager`
  for the same reason `propose_merge` already is.

---

## Cross-References

* Closes **C-03** (lifecycle wiring + S-10) +
  **M-004** (`ArchiveManager.apply_merge`) +
  **I-PV07-A** (REPORT.md auto-trigger) of
  `.local/research/v9.0.0_gap_analysis.md` §3.1.
* Implements `.local/research/v9.0.0_implementation_plan.md` §6.4
  (PV-04 runbook).
* Design doc: `.local/research/v9.0.0_pv04_design.md` §1-7.
* Predecessor ADRs: `v9-ADR-001`, `v9-ADR-002`, `v9-ADR-003` —
  v9.0.0 cycle PATCH series.
* Precedent: v6.0.3 retro highest-ROI dead-wire fix; v8.4.0 retro
  §4.1 #4 R5 strict pattern.
* Source-of-truth contract: A-4 ADR
  (`.cursor/rules/repo-governance.mdc` §"A-4 — Source-of-Truth Spec
  Location").
* Reference docs: `references/plan-mode-enforcement.md` §10 (S-10
  contract), `references/decomposition-gate.md` §6.1 (lifecycle hook
  cross-link).
* Test surface: `tests/test_dispatch_emission_runs_hooks.py` (8
  tests), `tests/test_agent_workspace.py::TestApplyMerge` (7 tests),
  `tests/test_agent_workspace.py::TestArchiveAutoRegenerateReports`
  (4 tests), `tests/test_lifecycle_hooks.py` (3 new tests for
  `post_dispatch` + DEFAULT_EVENTS length 6).
