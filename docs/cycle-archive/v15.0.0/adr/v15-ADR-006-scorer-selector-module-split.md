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

## Retirement criteria (v15.0.0 R2)

*Appended **2026-06-12** at the v15.0.0 W-8 reinforcement round (R2), discharging SI-3
finding R4 (`v15.0.0_evaluation.md` §4 item 4): the Decision's shim clause ("permanent …
lifetime ≥ until v16.0.0, revisit then") lacked dated, testable exit conditions. ADRs are
append-extensible pre-release; the Decision above is unchanged.*

**Scope.** The 24 identity-preserving re-export shims pinned by
`tests/test_module_split_shims.py::_SHIMMED_SYMBOLS` (the executable shim contract,
landed v14.5.0).

**Permanent exemptions — the S-10-named paths (NEVER retire).**

1. **`feedback.py::populate_cascade_gate_fields`** — 1 of the 24 shims
   (`devolaflow.feedback` → `devolaflow.gate.cascade`). Named BY PATH in
   `schemas/lean-dispatch.yaml` (populator clause:
   "`src/devolaflow/feedback.py::populate_cascade_gate_fields`") and inside Soul rule
   S-10's enforcement narrative. The shim stands for as long as those texts stand;
   changing either is a Soul/W-21 surface, out of scope for any retirement PR.
2. **`feedback.py::ProposalGenerator.generate_round_dispatch`** — named verbatim by Soul
   rule S-10. It never moved in the split; it is listed here so no future retirement PR
   relocates it out of `feedback.py` either.

Check (must stay green permanently):
`python -m pytest tests/test_module_split_shims.py::test_s10_named_paths_verbatim_functional -q`

**Retirable set: the remaining 23 shims**, eligible at the dated window below. One of
the 23 (`feedback.py::populate_intra_task_convergence`) is also cited in
`schemas/lean-dispatch.yaml` COMMENTS — its removal PR must update those comment
citations in the same PR (comment-level text, not a Soul/W-21 surface).

### RC-6.1 — Dated window

Earliest removal is **v16.0.0**; removal lands ONLY at a MAJOR. If any criterion below
fails at the v16.0.0 SI-1, the verdict is **EXTEND-to-v17.0.0**, recorded as a dated
deferral in the v16 retrospective §3 (no open-ended "permanent for now" again).

### RC-6.2 — In-repo import migration complete

Every in-repo import of the 23 retirable symbols uses the new owner-module path; the
only file still exercising old paths is `tests/test_module_split_shims.py` itself (its
parametrized contract imports via `importlib.import_module`, so it does not match the
commands below; its S-10 stanza imports only the exempt `populate_cascade_gate_fields`).
**Status at authoring (honest): NOT met** — 9 / 5 / 4 files per module group still
old-path-import (e.g. `tests/test_gate.py:1324` `from devolaflow.gate.scorer import
evaluate_gate, evaluate_ladder`). Check — all three commands MUST print nothing:

```bash
rg -lU "from devolaflow\.gate\.scorer import \(?[^)]*\b(CascadeViolationError|validate_cascade_gate_fields|IntraTaskConvergenceViolationError|validate_intra_task_convergence_fields|VERIFICATION_LADDER_ENV_FLAG|RungChecker|is_verification_ladder_active|evaluate_ladder|METRIC_KIND_COVERAGE|METRIC_KIND_LINT|METRIC_KIND_NUMBER|CommandRunner|CommandRunResult|evaluate_acceptance_criteria_v2|aggregate_criterion_verdicts)\b" src tests
rg -lU "from devolaflow\.task_adaptive_selector import \(?[^)]*\b(select_agents_md_slice|count_agents_md_rules|main)\b" src tests
rg -lU "from devolaflow\.feedback import \(?[^)]*\b(populate_intra_task_convergence|INTRA_TASK_CONVERGENCE_TASK_TYPES|INTRA_TASK_MAX_ROUNDS_DEFAULT|dispatch_wave_tasks|dispatch_dogfood_cycle)\b" src tests
```

### RC-6.3 — One full MAJOR of external-consumer notice via CHANGELOG

The v15.0.0 CHANGELOG shipped the migration notice verbatim — "Prefer the new paths in
NEW code; the shims are PERMANENT (revisit ≥ v16.0.0 per the ADR-006 shim clause)." —
and it must remain published for the entire v15.x series before removal. Check — ≥ 1
match:

```bash
rg -n "revisit ≥ v16.0.0 per the ADR-006 shim clause" CHANGELOG.md
```

### RC-6.4 — v16.0.0 SI-1 gate item (named) + post-removal pin

The v16.0.0 gap analysis (W-1, `.local/research/v16.0.0_gap_analysis.md`) MUST carry the
entry **"ADR-006 shim retirement (23 of 24; S-10 pair exempt)"** that executes RC-6.2 +
RC-6.3 and records a RETIRE / EXTEND-to-v17.0.0 verdict. The removal PR flips the 23
retirable `_SHIMMED_SYMBOLS` rows from presence pins to absence pins ("old path no
longer resolves") while the S-10 stanza stays verbatim. Post-removal check:

```bash
python -m pytest tests/test_module_split_shims.py -q
```
