# v15-ADR-003 — Output-Closure Enforcement Locus (`file_write` / `task_stop` hooks: wire vs stop advertising)

* **Status**: PROPOSED (L0/human ratifies — REQUIRED BEFORE v14.3.0 starts; see gap analysis §4.2 #3)
* **Date**: 2026-06-12
* **Cycle**: v14.2.0 T5 (SI-1 planning gate for the v14.2.x → v15.0.0 ladder)
* **Feeds**: F-P1-1 (critical) per `.local/research/v15-cycle_design_review_product.md` §1.2/§7
  ADR-2; gap G-001. Companion to v15-ADR-007 (evidence transport) — together they close the
  "task output verification 4/10" scorecard axis.
* **3-condition gate** (verbatim from the product review §7): "Hard to reverse: once an execution
  adapter fires hooks at write/stop time, it becomes a compatibility surface (R5 zero-IO
  defaults, strict-mode semantics). Surprising: the hooks have shipped unwired for 7 major
  versions while SKILL.md advertised them. Real trade-off: real enforcement (subprocess/IO cost,
  harness coupling) vs honest prompt-only labeling (keeps R5 purity, abandons the enforcement
  claim)." → **qualifies**.

## Context

`src/devolaflow/lifecycle/__init__.py` docstring (lines 24–27): "Hooks are intentionally NOT
wired into existing dispatch / write / status-report flows by P-05 — that integration is
deferred to a future patch (likely v7.6.x) and lives outside this module's scope." The only
production caller of `run_hooks` is `src/devolaflow/feedback_emit.py::_fire_hook_chain`, whose
`_HOOK_CHAIN = (pre_dispatch, post_dispatch, pre_handoff, pre_plugin_invocation)` — all
dispatch-emission-time (input-side). `check_file_write`/`file_write` (S-8 ownership) and
`post_task_complete`/`task_stop` (`test_on_complete`) have **zero production call sites**.

Yet SKILL.md §"Lifecycle Hooks" (lines 390–394) presents "`check_file_ownership` | File write |
File ∈ `owned_files` | Reject + log (P1)" / "`test_on_complete` | Task stop | Tests pass, lint
clean | Auto-retry ≤ P4 limit" — implying write/stop-time enforcement. S-8's own enforcement
clause ("Detected at file-write time via `lifecycle/check_file_ownership` hook") is likewise
prompt-only today. "Deferred to v7.6.x" has survived v8→v14.

The L0 ladder skeleton pre-commits "`file_write`/`task_stop` hook wiring with PERMISSIVE
defaults" at v14.3.0 and "hooks strict" at v15.0.0 — this ADR ratifies that locus and shape
(the product review had mapped the decision wholesale to v15.0.0; the skeleton's two-phase
landing is the stricter-but-safer reading).

## Decision (recommended)

**WIRE the hooks — two-phase, per the established DEFAULTS-PERMISSIVE-IN-MINOR /
STRICT-IN-NEXT-MAJOR pattern:**

1. **v14.2.x (interim honesty)**: annotate the SKILL.md Lifecycle Hooks table rows for the two
   unwired events as "library-only until v14.3.0" — stop implying live runtime enforcement
   (doc-only; reverses cleanly when wiring lands).
2. **v14.3.0 (PERMISSIVE wiring)**: ship the execution-side adapter that fires `file_write`
   before owned-file writes and `task_stop` at L3 report emission. Defaults: warn + log per S-8
   "mode: lite"; zero-IO default handlers per the R5 strict pattern; activation reuses
   `DEVOLAFLOW_AGENT_WORKSPACE=1` per W-20 reuse-first (same surface S-8 already binds to) — NO
   new env flag. The `task_stop` default handler consumes the new report-side `self_check` /
   `ac_results` blocks (v15-ADR-007) rather than spawning subprocesses.
3. **v15.0.0 (STRICT flip)**: block + escalate per S-8 "mode: full"; rides the G-038
   strict-graduation cluster (`asyncio.wait_for` default-on, `reject_subagent_quality_score`
   strict, banner hook default-wired).

## Consequences

### Positive
* S-8 becomes enforceable as written; the north star's OUTPUT side gains its first
  non-prompt-only, non-web-only enforcement point.
* The 7-major-version advertising debt is closed in the direction operators already believe.
* Two-phase landing gives one full MINOR of permissive telemetry before any blocking behavior.

### Negative
* New compatibility surface: hook firing order, payload shape, and permissive/strict semantics
  become contract (must be pinned by tests at v14.3.0, frozen at v15.0.0).
* Harness coupling: write-time interception depends on the executing agent honoring the
  protocol; out-of-band writes (raw shell) bypass it. Mitigation: document the bypass honestly
  in the SKILL table; `task_stop` evidence checks catch the net effect.

### Neutral
* Lifecycle `DEFAULT_EVENTS` tuple growth is cache-layout-sensitive (the v14.1.0 retro §3
  deferred `check_human_input_append_only` for exactly this reason) — the v14.3.0 PR must treat
  the event-tuple change as a telegraphed, test-re-pinned decision, not a drive-by.

## Alternatives considered

* **A1 — Stop advertising (relabel "library-only, caller-supplied")**: honest, zero runtime
  cost, preserves R5 purity — but permanently abandons the enforcement claim and leaves the
  north star's output side prompt-only; S-8's enforcement clause would need a rewrite to match.
  Rejected (kept as fallback if v14.3.0 wiring slips: the v14.2.x honesty label stands alone).
* **A2 — Strict immediately at v14.3.0**: violates the permissive-first pattern every prior
  graduation followed (cascade A-7, banner hook, quality-score hook); no telemetry before
  blocking. Rejected.
* **A3 — Wire only `task_stop`, drop `file_write`**: halves the surface but leaves S-8
  unenforceable at write time (its stated detection point); `file_write` is the cheaper hook
  (path-set membership check, zero IO). Rejected.
