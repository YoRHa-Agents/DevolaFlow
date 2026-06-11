# v15-ADR-006 — `gate/scorer.py` + `task_adaptive_selector.py` + `feedback.py` Split Boundaries

* **Status**: PROPOSED (L0/human ratifies before v14.5.0 implementation; review suggested ADR in
  v14.4.0, implement v14.5.0 — authored early at the SI-1 gate)
* **Date**: 2026-06-12
* **Cycle**: v14.2.0 T5 (SI-1 planning gate for the v14.2.x → v15.0.0 ladder)
* **Feeds**: F-R15 (major), F-R16 (major), F-R18 (minor) per
  `.local/research/v15-cycle_design_review_repo.md` §3/§7-D3; gap G-025
* **3-condition gate** (verbatim from the repo review §7): "Hard to reverse: downstream
  operators and S-10/W-11/schema text reference `feedback.py::populate_cascade_gate_fields` and
  scorer symbols by path; shim lifetimes must be declared. Surprising: rules cite file paths as
  contracts (S-10 'R5 strict triple codification' names `feedback.py`). Real trade-off: cohesion
  gain vs path-contract churn at the exact modules the v15.0.0 strict-flip touches." →
  **qualifies**.

## Context

`gate/scorer.py` (2545 lines, 57 top-level defs) bundles ≥6 concerns: cascade enforcement
(`class CascadeViolationError` line 100, `validate_cascade_gate_fields` line 179 — A-7
dispatch-shape validation, not scoring); pure scoring (`quality_score` 360, `composite_score`
370, `visual_fidelity_score` 388); the 6-rung ladder (`_check_lint` 894 … `evaluate_ladder`
1219); AC-v2 execution incl. a subprocess runner (`_default_command_runner` 1620,
`evaluate_acceptance_criteria_v2` 1658); budget/cycle/ratchet/legibility attachment
(`_apply_breaker_check` 1887 …); orchestration (`evaluate_gate` 2016) + `import argparse` CLI.

`task_adaptive_selector.py` (2051 lines) carries 3 separable subsystems: core selection, a
~380-line AGENTS.md-slicing subsystem (`select_agents_md_slice` 1658 — conceptually a
rules-distribution concern pairing with `local/compiler.py`), and a ~190-line CLI block — yet
the whole module is CP-6/W-13 benchmark-coupled, so "formatting tweaks trigger heavyweight
verification obligations". `feedback.py` hosts `populate_cascade_gate_fields` 543 (named by
`schemas/lean-dispatch.yaml` line 683 as its canonical populator) + `dispatch_wave_tasks` 755 +
`dispatch_dogfood_cycle` 879 alongside the feedback classes. The cheapest-to-extract concern
(cascade) is the one the v15.0.0 strict-flip touches most.

## Decision (recommended)

Implement at **v14.5.0** ("ADR-approved architecture refactors only" rung), one PV, with
**permanent re-export shims** (lifetime ≥ until v16.0.0, revisit then):

1. **Out of `gate/scorer.py`** (which keeps pure scoring + `evaluate_gate` orchestration):
   * `gate/cascade.py` — lines ~100–360 (CascadeViolationError, validate_cascade_gate_fields).
   * `gate/ladder.py` — lines ~863–1352 (the 6-rung ladder).
   * `gate/acceptance_v2.py` — lines ~1606–1820 (AC-v2 + subprocess runner) — the module the
     v14.4.0 metric runners then extend in place.
2. **Out of `task_adaptive_selector.py`**: `agents_md_slice.py` + `selector_cli.py`
   (re-export shims in the selector). **Scope the W-13/CP-6 benchmark trigger to the selection
   core** post-split (rule recompile in the same PR).
3. **Out of `feedback.py`**: `populate_cascade_gate_fields` moves beside `gate/cascade.py`;
   `dispatch_wave_tasks` / `dispatch_dogfood_cycle` move to a dispatch module. **Shims at the
   old paths are mandatory and permanent** — S-10 names `feedback.py` verbatim and
   `lean-dispatch.yaml:683` names `feedback.py::populate_cascade_gate_fields`; neither text
   changes in this PR (NO Soul edit; the shim preserves the path contract).
4. **Verification gates (binding)**: W-11 full gate suite (`tests/test_gate.py`), W-4/W-13
   EvoBench, plus byte-identical public-signature assertions per the v12.5.0 PV-02 precedent
   (`tests/test_v12_5_0_complexity_targets.py` signature literal-match pattern).

## Consequences

### Positive
* Cascade — the v15.0.0 strict-flip surface — becomes a small reviewable module instead of a
  slice of a 2.5K-line file; W-11 review funnel narrows per concern.
* Benchmark-trigger scoping ends the "CLI printing tweak → EvoBench obligation" false coupling.
* v14.4.0's AC-v2 metric runners and v14.3.0's `validate_dispatch` checks gain natural homes.

### Negative
* Import-surface churn managed by shims, but doc/text citations of line numbers (reviews,
  retros) go stale — acceptable for archival artifacts.
* Shim modules are permanent surface area (small: import + `__all__`); tracking table needed in
  the dispatch module docstring.

### Neutral
* Zero dispatch-payload change: no schema, no canonical_order, no env flags; S-10's hook-chain
  triple codification untouched (the test
  `tests/test_dispatch_emission_runs_hooks.py` must stay green unmodified — its target path is
  shimmed, not moved).

## Alternatives considered

* **A1 — No split**: every gate change keeps funneling reviewers through 2545 lines; the
  strict-flip lands in the god-file. Rejected.
* **A2 — Split without shims (update all citations)**: requires editing S-10 (a Soul rule —
  W-21 friction for a refactor) + schema text + operator docs in one PR; high blast radius for
  zero functional gain over shims. Rejected.
* **A3 — Full `gate/` package restructure (scorer → 6+ modules incl. breaker/ratchet)**:
  over-scoped; breaker/ratchet attachment is cohesive with orchestration today. Defer until a
  concrete change pressures it.
* **A4 — Move cascade into `skills/change_activation.py`** (where `cascade_requirement` lives):
  mixes dispatch-shape VALIDATION with complexity CLASSIFICATION; A-7 cites both sides
  separately. Rejected.
