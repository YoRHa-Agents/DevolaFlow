# v9-ADR-006 — CompressionPipeline Protocol Unification + 5-Primitive B3 Default-On Flip

**Status**: Accepted
**Cycle**: v9.0.0 PV-06 (`v8.5.1` MINOR)
**Date**: 2026-04-24
**Authors**: L0 Project Agent (delegated to L3 Task Agent)

## Context

PV-06 closes the two largest carry-forward surfaces from the v8.x cycle:

* **Theme T3 — CompressionPipeline Protocol Unification.** The v8.0.0+
  cycle shipped six separate compression primitives:
  `compressor.truncate_tool_output` (v7.0.1 ADR-002), the hierarchical
  `compressor.summarise_predecessor` (v7.0.2 ADR-003) with its extractive
  branch + its abstractive **Stage A** heuristic-only branch (v8.0.0 P-12)
  + its abstractive **Stage B** LLM-assisted branch (v8.2.0 PV-01),
  `compressor.directed_compact` (v8.0.0 P-02), and
  `shell_proxy.commands.apply_local_recipe` (v8.3.4 PV-04). Each shipped
  as a free function with its own argument shape, its own logging surface,
  and its own opt-in / opt-out condition. Composing two transforms required
  hand-wiring their argument lists at every call site; testing the
  byte-identical-when-bypassed invariant required separate fixtures per
  primitive. The v9.0.0 SI-1 gap analysis §5.6 flagged this as an
  architecture-rationality 8.5 ceiling blocker.

* **Theme T5 — 5-Primitive B3 Default-On Flip.** Five of the seven v8.0.0
  gate primitives
  (`gate.budget.TokenBudgetBreaker` / P-03,
  `gate.scorer.evaluate_ladder` / P-05,
  `gate.ratchet.MonotonicRatchet` / P-07,
  `gate.complexity_detector.ComplexityDetector` / P-09,
  `ac_generator.ACGenerator` / P-10) shipped as opt-in defaults in v8.0.0
  and have stayed opt-in across 8 minor releases despite every per-primitive
  dogfooding check landing green. Operators who want "full v8.0.0" quality
  still hand-wire the five primitive flags today, and the gap analysis
  flagged this as a test-adequacy 9.0 ceiling blocker (the five primitives
  are well-tested individually but not exercised together under the
  default-on surface). Theme T5 is the B3 closure from the v8.1.0 gap
  analysis §3.2 B3 list that has been outstanding since v8.2.0 PV-05
  closed the first 2 of 7 opt-in flips (`legibility_enabled` +
  `cycle_detector_enabled` on STRICT only).

Plus the coupling surface:

* **T3 #5 — multi-pass filter chain.** RTK's `[filters.<name>]` schema
  supports multi-stage composition via the `compose` field; DevolaFlow's
  v8.3.4 PV-04 local-recipe layer shipped a single-pass substitution only.
  Theme T3 #5 extends `schemas/command-mapping.yaml` from schema_version 1
  to schema_version 2 with an optional `compose: list[str]` field on every
  `FilterRule`, enabling recipes to compose sibling rules into multi-pass
  chains while preserving byte-identical v1 behaviour for recipes that
  omit `compose`.

PV-06 lands both themes in one minor cut. The decomposition analysis
§"Open Decision #5" (bundle-vs-stagger) defaulted to (a) **bundle** all
five primitive flips in PV-06; the fallback stagger path is codified
§"Rollback plan" below.

## Decisions

### D1 — `CompressionStage` protocol + `CompressionPipeline` orchestrator

**Decision**: introduce `devolaflow.compression_pipeline` as the canonical
module hosting a single `CompressionStage(name, transform, bypass,
bypass_conditions, telemetry_key)` dataclass + a matching
`CompressionPipeline(stages, name)` orchestrator. The pipeline is a
frozen dataclass that sequentially reduces an input payload through
every non-bypassed stage's `transform(payload, context) -> payload`
callable. Empty pipelines and pipelines where every stage's `bypass`
predicate returns `True` are byte-identical identity reducers — the R5
strict invariant pinned by
`tests/test_compression_pipeline.py::test_*_byte_identical`.

Each of the six v8.x transforms gains a module-level
`compression_pipeline_stage()` (or `compression_pipeline_stages()` returning
a list) factory that wraps the existing function behind
`make_stage`. The factories import `devolaflow.compression_pipeline`
lazily so host modules stay dependency-free at module-load time (the
pipeline is the consumer, not a foundation library).

**Why not a Protocol-only design with no dataclass?** The dataclass carries
construction-time validation (S-5 — loud on bad construction) and the
telemetry-key + bypass-conditions decorations that the orchestrator
surfaces in `StageResult`. A Protocol-only design would push validation
to the orchestrator, which is an ergonomic loss for every call site.

**Why not `strict=False` as the default?** Per S-5, the pipeline must never
silently swallow a broken transform. Strict-raises-loud is the default;
callers opt into best-effort explicitly (e.g. the recipe stage chaining).

### D2 — 6-transform refactor as concrete `CompressionStage` impls

**Decision**: refactor the six v8.x transforms as concrete
`CompressionStage` instances via module-level factories. Each factory
exports a `compression_pipeline_stage()` (singular) or
`compression_pipeline_stages()` (plural — `compressor.py` hosts three
transforms) function that returns a fresh `CompressionStage` / list of
stages. The factories:

* `devolaflow.compressor.compression_pipeline_stages()` → 3 stages
  (`truncate_tool_output` / `summarise_predecessor` /
  `directed_compact`).
* `devolaflow.llm_client.compression_pipeline_stage()` → Stage B
  LLM-assisted. Bypass predicate returns `True` when
  `context["llm_client"] is None`, preserving v8.0.0-P-10 byte-identical
  behaviour for callers that have not opted into LLM assistance.
* `devolaflow.shell_proxy.commands.compression_pipeline_stage()` →
  `apply_local_recipe`. Bypass predicate reuses the existing PV-02
  env-flag `DEVOLAFLOW_RTK_PROXY` via
  `is_command_mapping_active(ctx.get("env"))`. No new env-flag minted
  per **W-20 reuse-first**.

Schema mirror: `schemas/compression-pipeline.yaml` (schema version 1)
codifies the pipeline declaration shape (`name` / `stages` / `context`
/ `strict`) + the per-stage field shape (`transform_ref` / `bypass_ref`
/ `bypass_conditions` / `params` / `telemetry_key`) so future operator-
side pipeline declarations can be YAML-authored without touching
Python. Shipping with schema v1 keeps the migration path open — v2+
additions are appended (A-2 cache-layout governance is irrelevant for
this schema because the pipeline NESTS under existing dispatch keys per
A-2.3).

### D3 — 5-primitive default-on flip (STRICT + AUDIT only)

**Decision**: flip the five v8.0.0 gate primitives from opt-in to
default-ON for STRICT and AUDIT profiles only. STANDARD and RELAXED
profiles preserve the v8.5.0 byte-stable opt-in defaults. Surface area:

| # | Primitive | Profile flag | Env-flag (R5 strict — EXACTLY "0" opts out) |
|---|---|---|---|
| 1 | `TokenBudgetBreaker` (v8.0.0 P-03) | `budget_breaker_enabled` | `DEVOLAFLOW_TOKEN_BUDGET_BREAKER` |
| 2 | `evaluate_ladder` (v8.0.0 P-05) | `ladder_enabled` | `DEVOLAFLOW_VERIFICATION_LADDER` |
| 3 | `MonotonicRatchet` (v8.0.0 P-07) | `ratchet_enabled` | `DEVOLAFLOW_GATE_RATCHET` |
| 4 | `ComplexityDetector` (v8.0.0 P-09) | `complexity_detector_enabled` | `DEVOLAFLOW_COMPLEXITY_DETECTOR` |
| 5 | `ACGenerator` (v8.0.0 P-10) | `ac_generator_enabled` | `DEVOLAFLOW_AC_GEN` |

Each primitive gains:

* An `ENV_FLAG: str` module constant naming the canonical env-var.
* An `is_{primitive}_active(profile, env=None) -> bool` helper that
  combines the profile flag with the env-flag per R5 strict parsing:
  env value EXACTLY `"1"` forces ON, EXACTLY `"0"` forces OFF, anything
  else (unset, `""`, `"true"`, `"yes"`, `"01"`, `"1 "`, ...) falls back
  to the profile flag.
* A new EvoBench scenario
  `benchmarks/devolaflow_context/scenarios/{primitive}_disabled.yaml`
  that pins the byte-identical-when-opted-out invariant at composite
  floor ≥ 90 (all five scenarios score 96.05/100 in the v9.0.0 baseline).

**Why STRICT + AUDIT only?** These are the two high-rigour profiles that
already cross-opt-in to the related `legibility_enabled` +
`cycle_detector_enabled` flags (per v8.2.0 PV-05). Flipping the five new
primitives on STANDARD would break byte-stability for the majority of
operators who rely on the v7.x-compat STANDARD default; STANDARD users
who want the full v8.0.0 surface opt in per-primitive via env-flag.

**Why env-flag EXACTLY "0"/"1"?** Per **env-flags.md §6 R5 strict** — the
canonical parsing rule used by every DEVOLAFLOW_* flag. Loose-truthy
values like `"true"`, `"yes"`, `"on"`, `"01"` fall back to the profile
flag so operator typos never accidentally flip a primitive on a flipped
profile. The R5 strict discipline is tested by
`tests/test_pv06_primitive_flip.py::test_loose_env_values_fall_back_to_profile_flag`.

### D4 — Multi-pass filter chain (T3 #5 — `compose: list[str]`)

**Decision**: bump `schemas/command-mapping.yaml` from schema_version 1 to
schema_version 2 and add an optional `compose: list[str]` field on every
`FilterRule`. The field lists sibling-rule `raw_pattern` ids that MUST
run AFTER this rule's substitution in the same pre/post pass. The
parent's substitution runs first, then each composed child runs against
the parent's intermediate output in declaration order.

Load-time validation (S-5 loud): `_validate_compose_references` walks
both `pre_filters` and `post_filters` after the `FilterRule` tuple is
constructed and raises `CommandMappingError` when a `compose` entry
references a non-existent sibling. The message carries the recipe id +
the missing child id.

**Back-compat contract**: a v1 recipe is byte-identical to a v2 recipe
whose `compose` fields are all omitted. The loader normalises both
shapes into the same `FilterRule` tuple so consumers
(`apply_local_recipe` + `CompressionPipeline` stages) do not branch on
schema_version at runtime.

## Rationale

### Why bundle all 5 flips in one PV?

The `improvements_zh.md` user feedback §"B3 bundle vs stagger" strongly
recommended bundle because:

1. **Per-primitive dogfooding is already green.** Each of the five
   primitives has shipped with its own unit-test suite, its own
   individual EvoBench scenario, and its own CHANGELOG attribution
   across v8.0.0..v8.4.4. Stagger would add artificial velocity friction
   with no information gain.
2. **Composite regression risk is bounded by the 5 `_disabled.yaml`
   scenarios.** The opt-out path is pinned at composite ≥ 90 per
   primitive; a regression ≥ 5 pp would trigger **R-4** (per playbook
   §6.6.6) and stagger would kick in as the rollback path. The risk
   surface is therefore identical whether we bundle or stagger — bundle
   just ships sooner.
3. **Cycle test cap headroom.** PV-06 is forecast ≤ +25 tests; stagger
   over 2-3 PRs would push the cumulative delta closer to the +150
   cycle cap (per W-17) without buying any extra regression
   mitigation.

### Why the CompressionPipeline is P6-safe (A-2 preserved)

The pipeline adds **zero** top-level dispatch keys. The six transforms
were already reachable from dispatch consumers via
`pred[i].compact_directive` (position 4 — NEST per A-2.3 D3) and the
compression_rules block (position 8 — NEST). Wrapping them in the
CompressionStage protocol is a Python-side refactor that the dispatch
payload never sees. The 16-key `canonical_order` + schema version 5
stay byte-identical (verified by the 6-baseline multi-baseline test per
A-2.4).

### Why the primitive flip does NOT bump the schema version

A flip changes default values of existing dataclass fields (the five
`GateProfile.*_enabled` flags). It does NOT add new dispatch keys, new
nested fields, or new env-flags — every env-flag was already
forward-declared in `env-flags.md §4` since v8.5.0 PV-05. Per A-2.2 the
append-only tail invariant is preserved trivially.

## Consequences

### Operator-visible behaviour change (the MINOR semver justification)

Operators running DevolaFlow under a **STRICT** or **AUDIT** gate profile
will see five primitives activate by default after `v8.5.1`:

1. **`TokenBudgetBreaker`** — max_tokens budget now enforced with
   WARN/BREAK verdicts. Affects any dispatcher that consumes the
   breaker's `BudgetDecision` (the existing v8.0.0 P-03 codepath).
2. **`evaluate_ladder`** — the 6-rung short-circuit ladder replaces
   the single `evaluate_gate` call. Affects gate verdict rationale
   shape (additional `LadderEvaluation` records).
3. **`MonotonicRatchet`** — the 4-verdict ADVANCE/TOLERATE/ROLLBACK/ESCALATE
   machinery now runs against the deterministic oracle score. Affects
   convergence-loop attribution in StatusReports.
4. **`ComplexityDetector`** — NineS subprocess + MOCK fallback runs
   paired with `complexity_weight=0.10`. Affects the composite score
   calculation.
5. **`ACGenerator`** — 11-pattern deterministic injection fills the
   structured `acceptance_criteria_v2` dispatch field. The legacy
   `acceptance_criteria: list[str]` alias path remains the contract
   for v7.x backward compatibility.

Operators who want to preserve v8.5.0 byte-identical behaviour on a
flipped profile opt out per-primitive:

```bash
export DEVOLAFLOW_TOKEN_BUDGET_BREAKER=0
export DEVOLAFLOW_VERIFICATION_LADDER=0
export DEVOLAFLOW_GATE_RATCHET=0
export DEVOLAFLOW_COMPLEXITY_DETECTOR=0
export DEVOLAFLOW_AC_GEN=0
```

Each env-var is R5 strict — only the literal `"0"` opts out; loose-truthy
values fall back to the profile flag. The opt-out path is pinned by
`benchmarks/devolaflow_context/scenarios/{primitive}_disabled.yaml` at
composite ≥ 90.

### Test surface area

PV-06 adds ≤ +25 NEW test functions (actual: 18 in test_compression_pipeline.py
+ 5 in test_pv06_primitive_flip.py = 23). Cumulative cycle delta from
v8.4.0 baseline: +121 → +144 (≤ +150 cap per W-17).

### Cross-cutting references

* `workflow-system/agent/references/compression-pipeline.md` — NEW 14th
  SF-4 canonical Tier-2 reference covering the CompressionStage protocol,
  the CompressionPipeline orchestrator, the 6 canonical transforms, the
  multi-pass filter chain (T3 #5), and the three canonical compositions.
* `workflow-system/agent/references/decomposition-gate.md` §5.5 — default-
  state column updates for primitives 1, 2, 4, 5, 6 (primitives 3 =
  `cycle_detector` and 7 = `legibility_scorer` stay opt-in for a future
  cycle).
* `workflow-system/agent/references/env-flags.md` §2.6..§2.10 — the five
  env-flags promoted from §4 forward-declared to §2 active runtime.

### Cascading coupling updates (landed in lockstep with the 14th reference)

* `tests/test_no_ghost_features.py::_SF4_REFERENCE_SET` 13 → 14
* `tests/test_version.py::_MIRRORED_SKILL_FILES` 16 → 17
* `scripts/sync_cursor_skill.py::MIRRORED_FILES` 16 → 17
* `tests/test_adapter_golden.py::test_cursor_references_golden` `len(actual) == 14`
* `tests/test_reference_size_budgets.py::test_canonical_lists_match_sf3_contract` `len(_REF_FILES) == 14`
* `data/golden_test_set/sf4_reference_set_size.toml` 13 → 14
* SKILL.md Tier-2 nav table gains 1 row (441 → 442 lines; ≤ 500)

## Alternatives Considered

### Alt-1 — Stagger the five primitive flips across 3 PRs

**Rejected.** Would push the cycle test delta toward the +150 cap
without mitigating regression risk (the five `_disabled.yaml` scenarios
already pin the opt-out path per primitive). Net effect: three CI
cycles instead of one, same information content. The stagger path is
retained as **rollback only** (per §"Rollback plan" below) so the cycle
can defer individual primitives if any `_disabled.yaml` regresses < 90.

### Alt-2 — Ship the CompressionPipeline additive-only; defer the B3 flip to v9.1.0

**Rejected.** Would split a single user-visible MINOR cut into two,
neither of which carries the full operator-facing MINOR semver
justification on its own. The bundled cut produces exactly one
CHANGELOG "Adoption notes" section that operators can grep against,
minimising surface-area churn for downstream consumers.

### Alt-3 — Introduce a new top-level `compression_pipeline` dispatch key

**Rejected.** Would force a schema version bump (16 → 17,
`canonical_order` version 5 → 6) and invalidate every cached dispatch
payload. Per A-2.3 NEST decision rule, the pipeline's state is
orthogonal-to-nothing: every pipeline invocation is tied to an existing
dispatch block (`pred[i]` for summariser chains, `compression_rules`
for output truncation, `command_mapping` for recipe chains). NEST under
the existing blocks preserves the frozen prefix byte-identically.

### Alt-4 — Mint a new `DEVOLAFLOW_COMPRESSION_PIPELINE` env-flag

**Rejected** per **W-20 reuse-first**. The pipeline has no activation
surface of its own — every stage honours its source module's existing
opt-in condition (PV-02's env-flag for the recipe stage, Stage B's
`context["llm_client"]` for the LLM stage, profile flags for the gate
primitives). Minting a new flag would violate W-20's orthogonality
test: the pipeline's activation is **reducible** to the five existing
env-flags + context probes.

## Migration

### For operators on STRICT or AUDIT profiles

Upgrade to `v8.5.1` and the five primitives activate automatically.
Monitor gate composite scores for 1-2 rounds. If regression observed:

```bash
# Per-primitive opt-out — EXACTLY "0" required (R5 strict)
export DEVOLAFLOW_TOKEN_BUDGET_BREAKER=0
export DEVOLAFLOW_VERIFICATION_LADDER=0
export DEVOLAFLOW_GATE_RATCHET=0
export DEVOLAFLOW_COMPLEXITY_DETECTOR=0
export DEVOLAFLOW_AC_GEN=0
```

Each opt-out is reversible — unset the var (or set to `""`) and the
profile flag wins.

### For operators on STANDARD or RELAXED profiles

No behavioural change. The five primitives remain opt-in via their
existing env-flag pattern — set to `"1"` to force on:

```bash
export DEVOLAFLOW_TOKEN_BUDGET_BREAKER=1
# ...etc.
```

### For downstream code calling compression transforms directly

No behavioural change. The six transforms retain their original
function signatures; the CompressionStage wrappers are additive. Code
that wants to migrate to the pipeline imports the factory:

```python
from devolaflow.compression_pipeline import CompressionPipeline
from devolaflow.compressor import compression_pipeline_stages

pipeline = CompressionPipeline(
    stages=tuple(compression_pipeline_stages()),
    name="compressor_default",
)
result = pipeline.run(payload, context={"max_tokens": 1200})
```

### For recipe authors (command-mapping schema v1 → v2)

No action required. v1 recipes continue to work byte-identically.
Authors wanting multi-pass chains bump `schema_version: 2` in their
recipe and add `compose: [<sibling-pattern-id>]` to the relevant rules.

## Rollback plan

Per playbook §6.6.6:

* **Single primitive regresses < 90** → stagger: defer that one flip
  (1-line `context_profiles.yaml` toggle per primitive), ship the
  other four, amend the CHANGELOG "Adoption notes" accordingly.
* **All 5 primitives regress < 90** → revert all flips back to
  default-OFF; ship T3 CompressionPipeline only as an additive refactor.
  T5 moves to v9.1.0 with a deeper analysis cycle.
* **SKILL.md +1 row pushes wc > 480** → defer the 14th reference
  (compression-pipeline.md) to v9.0.x sustaining. The core T3 + T5
  still ships. (At cut time wc was 442 — safely under the 500 ceiling.)

All three rollback paths are 1-line reverts per file (or one git revert
on the offending commit), preserving the bulk of the cycle's other
improvements.

## Enforcement

Detected at test time:

* R5 byte-identical invariant → `tests/test_compression_pipeline.py`
  (`test_empty_pipeline_is_byte_identical` +
  `test_all_stages_bypassed_is_byte_identical` +
  `test_identity_stage_is_byte_identical`).
* R5 strict env-flag parsing → `tests/test_pv06_primitive_flip.py`
  (parametrized across 5 primitives × 7 loose-truthy values × 2
  profile flags = 70 assertions).
* STRICT/AUDIT default-on pin →
  `tests/test_pv06_primitive_flip.py::test_strict_audit_default_to_true_for_all_five_primitives`.
* STANDARD/RELAXED default-off pin →
  `tests/test_pv06_primitive_flip.py::test_standard_relaxed_default_to_false_for_all_five_primitives`.
* 5 `_disabled.yaml` scenarios at composite ≥ 90 →
  `tests/test_benchmarks.py::TestEvaluator` + the v9.0.0 baseline pin.
* 14-reference SF-4 set →
  `tests/test_no_ghost_features.py::test_skill_reference_links_match_sf4_set`
  + `tests/test_reference_size_budgets.py::test_canonical_lists_match_sf3_contract`.

Detected at CI-time:

* W-9 / SI-10 6/6 step discipline → invoked by release commit pre-flight.

## Source

* `.local/research/v9.0.0_gap_analysis.md` §5.6 (26-file scope).
* `.local/research/v9.0.0_implementation_plan.md` §6.6 (5-stage / 8-wave
  / 15-task runbook).
* `workflow-system/agent/references/env-flags.md` §2.6..§2.10 (the
  five promoted flags).
* `workflow-system/agent/references/decomposition-gate.md` §5.5 (the
  composition table with post-PV-06 default states).
* `workflow-system/agent/references/compression-pipeline.md` (the
  14th SF-4 canonical reference).
