# v7-ADR-001 — Prompt-Cache Layout Invariant for Inter-Layer Dispatch

- **Status:** Accepted
- **Date:** 2026-04-17
- **Authors:** Design team L3 task agent for V7.0.0-S02-T01
- **Ships in:** v7.0.0 (see `.local/research/v7.0.0_version_roadmap.md`)
- **Research source:** `.local/research/v7.0.0_context_compression_research.md` §§A, B.6, F row 1, J.1
- **Decides:** Open question K.3 (cache-layout SLO — committed thresholds)

## 1. Context

The `@trq212` (Thariq Shihipar, Anthropic Claude Code) practitioner corpus
identifies prompt-cache discipline as the single largest operational lever
for long agent sessions: a 90 % cache-hit rate reduces cost from roughly
USD 50–100 per long Opus session to USD 10–19 — a 5–10× delta
(`[ref-3]` in the research report).

DevolaFlow's stack does **not** currently enforce a cache-layout invariant.
`src/devolaflow/compressor.py` operates on the prose content of a dispatch
but does not assert the *structural ordering* of the rendered YAML. The
lean dispatch schema (`schemas/lean-dispatch.yaml`) defines per-field
shape but not the top-of-payload *section order*. Today's
`apply_round_escalation()` can prepend a round-2 reinforcement block to
the dispatch; depending on the rendering strategy, this can restructure
the cached prefix across rounds and force Cursor (or any downstream
caching harness) to rebuild the prefix cache on every convergence round.

We cannot directly observe Cursor's KV-cache behaviour (research §D.5 +
open question K.7). We *can*, however, enforce a necessary condition:
**the rendered dispatch prefix is structurally stable across rounds** for
the same task_id. This ADR codifies that invariant, the structural
ordering it enforces, and the runtime validator that makes a regression
unambiguous.

## 2. Decision

We adopt a **single canonical section order for every lean dispatch**.
The order is additive — each later section may be absent, but no section
may be reordered above an earlier section. The order is declared once in
`schemas/lean-dispatch.yaml` under a new top-level key `layout_invariant:`
and enforced at runtime by a new helper
`devolaflow.compressor.assert_dispatch_layout(payload: dict, layout_spec:
list[str]) -> None` that raises `DispatchLayoutError` (new exception
class) when the payload's top-level key order does not match.

**Canonical order (v7.0.0 baseline):**

1. `hdr` (envelope — stable per task_id)
2. `task` (work unit identity — stable per task_id)
3. `goal`
4. `assumptions` (optional)
5. `pred` (predecessor artifacts — append-only across rounds)
6. `files`
7. `rules`
8. `shared`
9. `accept`
10. `reinforce` (round-specific — appended in round 2+, never inserted earlier)
11. `verify_cfg` (optional)
12. `gate`

**Cache-hit-rate proxy SLO (committed):** The structural stability test
(`H.2` in research §H) asserts that the **longest common prefix (LCP) of
the rendered YAML is ≥ 80 % of the round-1 payload size when comparing
round 1 → round 2**, and **≥ 70 %** when comparing round 1 → round 3. A
test failure is a hard blocker on release.

**Additive-only rule:** Any new top-level key introduced after v7.0.0
must be appended *after* `gate` (position 12 or later) unless a new
major version explicitly revises the invariant. Schema-level breakage
requires a successor ADR.

## 3. Consequences

### Positive

- Round-over-round dispatch payloads preserve a stable cached prefix,
  which is a necessary (though not sufficient) condition for Cursor's
  KV-cache to hit on rounds 2 and 3.
- `apply_round_escalation()` gains a clear contract: it may only modify
  the `reinforce` block (position 10) and pass-through fields *below* it
  in the canonical order.
- Future debugging of cache-hit regressions reduces to `git blame` on
  the invariant file plus the stability test.
- The invariant is a measurable SI-3 dimension: LCP-per-round is an
  observable metric we can feed back into SI-3 evaluation of v7.0.0.

### Negative

- Any compressor change that introduces a new dispatch field now
  requires a schema edit *and* an invariant edit — two touchpoints
  instead of one.
- Round-N reinforcement cannot appear at the top of the dispatch even
  when urgency would rhetorically argue for it; agents reading the
  dispatch must be trained to scan the `reinforce` block *below* the
  acceptance criteria rather than expecting it up-front.
- Adoption cost: every downstream dispatcher (L0→L1, L1→L2, L2→L3) must
  route through the validator or its renderer helper. Legacy free-form
  YAML dispatches from pre-v7 codepaths will fail the validator.

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| False-positive validator failure on whitespace drift | P3 | Normalise YAML dump via `yaml.safe_dump(..., sort_keys=False, default_flow_style=False)` before computing LCP. |
| Round-escalation needs to mutate `pred` (e.g., add a new predecessor) | P2 | ADR permits *append* within `pred`; insertion order is the `pred` list, not the top-level key order. List-element stability is not asserted by this ADR. |
| Downstream dispatcher renders keys in different Python dict order | P1 | Enforce `dict` → `OrderedDict` normalisation inside `assert_dispatch_layout`. Python 3.11+ preserves insertion order, but the validator must not rely on caller discipline. |
| LCP threshold over-fits to current rendering library versions | P2 | Store the round-1 rendered sample alongside the baseline JSON and compare byte-for-byte in CI so that accidental library updates surface as a dedicated failure rather than a stability regression. |

## 4. Alternatives Considered

### 4a. **Full platform-side telemetry**

Ask the user / deployment to expose Cursor's cache-hit telemetry and
enforce cache-hit ≥ 90 % directly. **Rejected** because (1) Cursor does
not publish per-model cache-hit rate (research §D.5), (2) we cannot
block CI on data we do not control, (3) this blocks v7.0.0 on an open
question (K.7). We revisit platform-side telemetry in v8.x once Anthropic
or Cursor ships it publicly.

### 4b. **Soft guidance in SKILL.md only**

Document "do not reorder sections" in SKILL.md and trust dispatch
authors. **Rejected** because SI-9 reinforcement already demonstrates
that prompt-side guidance is insufficient to prevent regressions in
subsequent rounds. The P4-bounded-retry principle applies: anything we
expect to enforce every round must be a test, not a prompt.

### 4c. **Schema-level ordering only (no runtime check)**

Declare the order in `schemas/lean-dispatch.yaml` without a validator.
**Rejected** because YAML schemas describe shape, not output order, and
Python `dict` ordering is implementation-defined even when insertion
order is preserved at the language level. Downstream dispatchers
serialise via multiple libraries; only a rendered-output assertion is
robust.

### 4d. **Cache-aware renderer (reorder into canonical form)**

Write a renderer that always reorders keys into canonical form,
silently fixing mis-ordered input. **Rejected** because silent fixups
mask the underlying bug. We prefer fail-fast: the validator raises and
the dispatcher is responsible for emitting the correct order.

## 5. Reversibility

**Cost to undo:** Low-to-medium.

- Remove `devolaflow.compressor.assert_dispatch_layout` and the
  `DispatchLayoutError` class.
- Remove `layout_invariant:` from `schemas/lean-dispatch.yaml`.
- Remove the H.2 stability test.
- Revert the SKILL.md "Cache Layout" subsection.

All dispatchers will continue to function because the invariant is
additive and the renderer does not rewrite inputs. Rollback affects
only enforcement, not runtime behaviour. Rollback window ≤ 1 patch
version.

## 6. Test Plan

Tests that would falsify this decision:

1. **`tests/test_compressor.py::test_assert_dispatch_layout_accepts_canonical`** —
   render a synthetic dispatch in canonical order, confirm validator
   returns None.
2. **`tests/test_compressor.py::test_assert_dispatch_layout_rejects_reordered`** —
   swap `reinforce` and `pred`, confirm `DispatchLayoutError` raised
   with a descriptive message pointing at the first out-of-order key.
3. **`tests/test_compressor.py::test_dispatch_prefix_is_stable_across_rounds`** —
   build rounds 1 / 2 / 3 of the same task_id; assert LCP ≥ 80 %
   (1→2) and ≥ 70 % (1→3). This is the H.2 benchmark; regression below
   the threshold blocks CI.
4. **`tests/test_compressor.py::test_new_field_appended_not_inserted`** —
   when a hypothetical new field `cache_hint` is added, confirm it
   lands at position 13 (after `gate`), not between existing fields.
5. **`tests/test_benchmarks.py::test_layout_invariant_baseline`** —
   record the canonical rendered bytes of a golden dispatch in
   `benchmarks/devolaflow_context/baselines/layout_invariant_v7.0.0.yaml`;
   any change to the canonical byte output fails CI (signed by a
   separate PR).

A failure of test #3 over two consecutive CI runs is a hard block on
the release.

## 7. Cross-References

- Depends on: nothing (this ADR is the first v7 change).
- Depended on by: **v7-ADR-002** (tool-output truncation appends
  `tool_results` to `lean-report.yaml` under the same additive
  principle), **v7-ADR-003** (predecessor summarisation mutates
  `pred[*].key_facts` but not top-level key order).
- Related rules: `.cursor/rules/devola-flow-rules.mdc` (workspace Rule
  P1-P5), `.cursor/rules/context-optimization-rules.mdc` (CO-1, CO-2).
- Research §: A, B.6, F row 1, G row 1, H.2, J.1, K.3.
