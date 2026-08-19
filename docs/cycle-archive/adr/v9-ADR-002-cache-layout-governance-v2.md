# v9-ADR-002 — Cache-Layout Governance v2 (Nest-vs-Append + Multi-Baseline Byte Test)

* **Status**: Accepted
* **Date**: 2026-04-24
* **Cycle**: v9.0.0 PV-02 (`v8.4.2` PATCH)
* **Cycle role**: Codifies the load-bearing decision rule that has been
  applied informally across 5 prior schema generations (v7.2.6 P-06,
  v8.0.0 P-08, v8.0.0 P-10, v8.3.0 PV-05, and the 4 v8.4.0 cycle PVs that
  added NESTED knobs without bumping the schema). Closes the codification gap
  flagged as **B-02** in `.local/research/v9.0.0_gap_analysis.md` §5.2.
* **Renumbering note**: previously planned as `v9-ADR-001` per
  `.local/research/v9.0.0_gap_analysis.md` §5.2 + §8; renumbered to ADR-002
  per `.local/research/v9.0.0_erratum.md` G-01 because PV-01 ships
  `v9-ADR-001-skill-headroom-reclamation.md` chronologically first.
* **Predecessor ADR**: `.local/research/adr/v7-ADR-001-cache-layout-invariant.md`
  (the original v7.0.0 cache-layout invariant that this ADR generalises).

## Context

DevolaFlow's `schemas/lean-dispatch.yaml#layout_invariant.canonical_order`
declares a single canonical top-level key order for every lean dispatch
payload. The order is the **cached prefix** that downstream LLM KV-caches
key on; any reordering forces the host to rebuild the cache from the first
divergent byte (typically a 5–10× cost delta on long convergence sessions
per `v7-ADR-001` §1).

Since v7.0.0 the canonical order has grown additively four times:

| Schema version | Canonical order length | Added key | Position | Cycle |
|----------------|------------------------|-----------|----------|-------|
| v1 (v7.0.0) | 12 | (initial set) | 1-12 | v7.0.0 |
| v2 (v7.2.6) | 13 | `repos` | 13 | P-06 |
| v3 (v8.0.0) | 14 | `behavioral_guidelines` | 14 | P-08 |
| v4 (v8.0.0) | 15 | `acceptance_criteria_v2` | 15 | P-10 |
| v5 (v8.3.0) | 16 | `change_context` | 16 | PV-05 |

In parallel, the SAME 5 cycles ALSO landed many feature-flag-style changes
WITHOUT bumping `version` — they nested new knobs under existing top-level
keys (e.g., `gate.token_budget`, `pred[*].compact_directive`,
`pred[*].summary_mode`, `compression_rules.bypass_conditions`,
`compression_rules.data_envelope_required`). Each of those decisions was
made ad-hoc per ADR; the **decision rule itself** has never been codified.

The B-02 gap surfaced this in two concrete failure modes during the
v9.0.0 SI-1 review:

1. `references/context-isolation.md` §10 (line 322, pre-PV-02) declared
   *"Canonical order (12 keys)"* — the schema had grown 12 → 16 in 4
   intervening cycles without the canonical reference catching up. The
   doc was 4 schema generations stale.
2. `tests/test_compressor.py` had byte-baselines for v7.0.0 + v7.3.0 only;
   the v8.0.0 P-08 / P-10 + v8.3.0 PV-05 baselines were verified VIA the
   v7.0.0 test (additivity proof), not pinned with their OWN golden
   YAMLs. A future "additive" ADR that mistakenly reordered prefix keys
   would fail the v7.0.0 baseline late, only after the layout was
   already changed in code.

## Decision

### D1 — Frozen Prefix (positions 1-12)

The first **12** positions of `canonical_order` are the **FROZEN PREFIX**.
They MUST remain byte-identical to the v7.0.0 canonical sequence:

```
hdr → task → goal → assumptions → pred → files → rules → shared →
accept → reinforce → verify_cfg → gate
```

Reordering any of these 12 keys is a **release blocker** per Soul Rule S-2
extension and Architecture Rule A-2 extension. Re-renaming any of these 12
keys is also a release blocker. Removing any key is a release blocker.

### D2 — Append-Only Tail (positions 13+)

Positions 13 onward are **APPEND-ONLY**. New top-level dispatch keys land
at position N+1 where N is the current `len(canonical_order)`, never
inserted into a lower slot. This preserves the prefix property: a v8.4.x
payload renders as a byte-extending continuation of the v7.0.0 baseline.

### D3 — Nest-vs-Append Decision Rule

When introducing a new dispatch behaviour, authors choose between
**nesting** under an existing canonical key and **appending** a new
canonical key. The rule is:

| Test | Verdict |
|------|---------|
| Does the behaviour modify how an existing block is interpreted? | NEST under that block |
| Does the behaviour reuse an existing block's data shape? | NEST as a new field |
| Does the behaviour add an orthogonal concern unrelated to existing blocks? | APPEND a new top-level key |
| Does the behaviour reference cross-block state? | APPEND a new top-level key |
| Is the new field always present together with an existing block? | NEST as a sub-field |
| Is the new field independently optional? | Either is acceptable; prefer NEST when the data shape allows |

The bias is toward **NEST**: every nest preserves the cache-prefix
length, while every append adds a position the runtime must serialise.
The 5 historical NEST decisions (token_budget, compact_directive,
summary_mode, bypass_conditions, data_envelope_required) were correct
because each modified an existing block's interpretation; the 4 historical
APPEND decisions (repos, behavioral_guidelines, acceptance_criteria_v2,
change_context) were correct because each carries cross-block payload
that does not naturally nest.

### D4 — Multi-Baseline Byte Test (CI Enforcement)

A NEW pytest module
`tests/test_layout_invariant_multi_baseline.py` validates positions 1..N
for **every** prior baseline:

| Baseline | Length | Test name | Golden YAML |
|----------|--------|-----------|-------------|
| v7.0.0 | 12 | `test_v7_0_0_baseline_byte_identical` | `layout_invariant_v7.0.0.yaml` (existing) |
| v7.3.0 | 13 | `test_v7_3_0_baseline_byte_identical` | `layout_invariant_v7.3.0.yaml` (existing) |
| v8.0.0 P-08 | 14 | `test_v8_0_0_p08_baseline_byte_identical` | `layout_invariant_v8.0.0.yaml` (NEW) |
| v8.0.0 P-10 | 15 | `test_v8_0_0_p10_baseline_byte_identical` | (covered by v8.0.0 + v8.3.0 prefix) |
| v8.3.0 PV-05 | 16 | `test_v8_3_0_pv05_baseline_byte_identical` | `layout_invariant_v8.3.0.yaml` (NEW) |
| v8.4.0 | 16 stable | `test_v8_4_0_baseline_byte_identical` | `layout_invariant_v8.4.0.yaml` (NEW) |

Each test renders the canonical payload via
`yaml.safe_dump(..., sort_keys=False, default_flow_style=False)` and
byte-compares against its golden YAML. Any drift fails CI.

### D5 — Validator Extension (`assert_dispatch_layout`)

`devolaflow.compressor.assert_dispatch_layout()` gains:

1. A new module-level constant `FROZEN_PREFIX_V7` containing the 12 v7.0.0
   keys verbatim.
2. A new public helper `assert_layout_spec_invariant(spec)` that asserts
   `spec[:12] == FROZEN_PREFIX_V7` and raises
   `LayoutSpecInvariantError` (a new subclass of `DispatchLayoutError`)
   when the FROZEN PREFIX has drifted.
3. A docstring extension on `assert_dispatch_layout` referencing this ADR
   and the nest-vs-append rule.
4. Existing payload-level checks remain UNCHANGED (additive). The
   nest-vs-append rule is enforced at the **spec level**, not the payload
   level — payload reorder rejection is a separate, byte-exact check that
   already exists.

### D6 — Schema Documentation (Doc Comments Only)

`schemas/lean-dispatch.yaml#layout_invariant` gets ~10 LOC of new YAML
**comment lines** documenting D1-D5 inline. **No structural data
changes**. `version` stays at `5`. `canonical_order` stays at length 16
with the same 16 keys in the same order. This protects I-8 (the cycle's
hard invariant) by construction.

### D7 — Governance Rule Extension (A-2)

`.cursor/rules/repo-governance.mdc` and `.rules/architecture.mdc` Rule A-2
gain a "nest-vs-append" sub-section (~+45 LOC) that:

- States D1 (frozen prefix) and D2 (append-only tail) verbatim
- Enumerates the historical NEST and APPEND decisions
- Cites this ADR (`v9-ADR-002`) as the source-of-truth
- Cross-links to `tests/test_layout_invariant_multi_baseline.py` as the
  CI enforcement vehicle

`AGENTS.md` is REGENERATED via `devolaflow.local.compiler.RuleCompiler`
after the .rules/ edit (auto-generated header preserved).

## Rationale

### Why codify now (v9.0.0 PV-02)?

The 4 nest decisions and 4 append decisions made in v8.0.0 + v8.3.0 + v8.4.0
were each correct, but the rule was implicit. The v9.0.0 SI-1 reference
review surfaced two distinct failure modes (stale doc + missing baseline)
that both stem from the same gap: there is no codified contract for how
the canonical order may evolve. PV-02 closes 9 ref findings + introduces
the nest-vs-append rule, so the codification rides naturally with the
reference cascade — the documentation cost is amortised across the same
PR.

### Why "frozen prefix at 12" instead of "frozen prefix at N"?

12 is the v7.0.0 canonical baseline. It is the longest prefix that has
been stable across **every** subsequent schema generation. Choosing 12
fixes the LLM cache-prefix invalidation cost ceiling at the v7.0.0
boundary: no future PV can reorder positions 1-12 without explicit ADR +
multi-baseline test churn. Choosing N=16 (the current length) would
forbid future churn that is already permitted (positions 13-16 may, in
principle, still reorder under append-only semantics — though no such
reorder is currently planned). Choosing N=10 (the v6.x ad-hoc baseline)
would weaken the contract by allowing positions 11-12 (`verify_cfg` +
`gate`) to drift, which they have NOT done across 5 generations.

### Why multi-baseline byte tests (not just additivity proof)?

Today's v7.0.0 + v7.3.0 byte tests prove additivity by transitive logic:
"if v7.0.0 still passes after v7.3.0 was added, the new key was appended,
not inserted." That logic depends on **only one** prior baseline being
pinned at any given time. With FOUR prior schema generations live (v7.0.0,
v7.3.0, v8.0.0 P-08, v8.3.0 PV-05) and ANY of them being a valid LLM
cache target, byte-pinning each generation independently catches three
distinct attack surfaces:

1. **Renamer**: a key rename (e.g., `pred` → `predecessors`) would pass
   the v7.0.0 baseline by coincidence if the rename happened in a NEW
   appended key — only an enumeration of the prefix per generation
   catches this.
2. **Re-orderer**: a swap of two prefix positions (e.g., `accept` ↔
   `reinforce`) would fail v7.0.0 immediately, BUT a swap below the
   v7.0.0 horizon (e.g., `repos` ↔ `behavioral_guidelines`) would pass
   v7.0.0 and v7.3.0 — only the v8.0.0 P-08 baseline would catch this.
3. **Sneaky inserter**: a NEW key inserted between `behavioral_guidelines`
   (position 14) and `acceptance_criteria_v2` (position 15) would pass
   the v7.0.0 + v7.3.0 baselines but corrupt the v8.0.0 P-10 prefix —
   only the v8.0.0 P-10 baseline catches this.

The combinatorial coverage scales O(N) with prior baselines while
additivity-by-transitive-logic only catches O(1) violations.

## Consequences

### Positive

* **Cache-prefix preservation is structurally enforced.** Any future PV
  that touches `canonical_order` MUST add a new golden YAML for its
  baseline AND keep all prior baselines passing. CI cannot be silently
  bypassed.
* **The nest-vs-append decision becomes a 6-row table review instead of
  a per-feature debate.** Authors apply D3 mechanically.
* **AGENTS.md gains a concrete A-2 contract** that L0/L1/L2/L3 dispatchers
  can cite when reviewing new dispatch keys. Closes a documentation gap
  that has lingered since v7.2.6.
* **Future operators understand WHY positions 1-12 are frozen** without
  archaeology — the rule is documented inline in the schema YAML, the
  rule file, and the ADR.

### Negative

* **+3 NEW golden YAML fixtures** (`layout_invariant_v8.0.0.yaml`,
  `layout_invariant_v8.3.0.yaml`, `layout_invariant_v8.4.0.yaml`) live
  in `benchmarks/devolaflow_context/baselines/` (~+50/+60/+70 LOC each).
  Each baseline must be regenerated atomically when a new schema
  generation lands; a future ADR that bumps to v6 must add a v9.0.0 +
  v8.4.0 + v8.3.0 + ... + v7.0.0 cumulative golden set.
* **+~60 LOC in `compressor.py`** for the FROZEN_PREFIX_V7 constant +
  `assert_layout_spec_invariant` helper + `LayoutSpecInvariantError`
  class.
* **+~45 LOC in `.cursor/rules/repo-governance.mdc` + `.rules/architecture.mdc`**
  for the A-2 extension. AGENTS.md regenerates ~+30 LOC net.
* **AGENTS.md auto-regenerates** — devs who hand-edit AGENTS.md (which
  the auto-generated header explicitly forbids) will trip the drift
  detector.

## Alternatives Considered

### A1 — Full Schema Versioning + Migration Layer

Replace the additive contract with a versioned schema (each version
declares its own canonical_order; runtime translates between versions).

**Rejected** because:
- Translation cost defeats the LLM cache-prefix optimisation.
- Operator complexity (every payload must declare its schema version).
- Existing tooling (`devolaflow.compressor`) assumes a single canonical
  layout; bifurcating the validator would touch 600+ LOC.
- The additive contract has held for 5 generations without strain; the
  cost of full versioning is unjustified.

### A2 — Reorder-On-Demand (Renderer-Level Sort)

Let dispatch authors emit keys in any order; have the renderer
canonicalise via `yaml.safe_dump(..., sort_keys=True)` or a custom sort.

**Rejected** because:
- `sort_keys=True` would alphabetise, breaking the cached prefix
  immediately (alphabetic order ≠ canonical order).
- A custom sort would need to know the canonical_order list at render
  time — equivalent to enforcement at write time, but with worse
  observability.
- The render step happens AFTER validation; a sort that hides reorder
  bugs would make CI silently green while production cache hit rates
  collapse.

### A3 — Freeze the Entire Current Order (positions 1-16)

Treat the current 16-key order as the FROZEN baseline; forbid reorder of
ANY position.

**Rejected** because:
- Positions 13-16 were appended in chronological version order; they have
  not "earned" the same freeze guarantee as positions 1-12 (which have
  been stable across 5 generations).
- A future ADR may legitimately want to reorder positions 13-16 (e.g.,
  if a deprecation removes one, the remaining 3 don't shift up — they
  stay at their original positions per APPEND-ONLY).
- Freezing positions 13-16 would forbid future deprecation of
  `behavioral_guidelines` or `acceptance_criteria_v2` if they are
  superseded by a successor key.

### A4 — No Codification (Keep the Implicit Rule)

Status quo: leave the rule informal; trust that future authors apply it
correctly.

**Rejected** because:
- The B-02 gap proves the implicit rule has already failed
  (`references/context-isolation.md` was 4 schema generations stale).
- The reference review identified `tests/test_compressor.py` as carrying
  only v7.0.0 + v7.3.0 byte-pinned baselines; the v8.0.0 + v8.3.0 schema
  generations rely on additivity-by-transitive-logic which is a weaker
  guarantee.
- The cost of codifying now (this ADR + +110 LOC across compressor + rule
  + 3 golden YAMLs + 1 test module) is amortised across the PV-02 cascade
  PR; the cost of NOT codifying compounds with every future schema
  generation.

## Migration

### M1 — Pre-PV-02 (no action required)

The 5 schema generations (v7.0.0 / v7.2.6 / v8.0.0 P-08 / v8.0.0 P-10 /
v8.3.0 PV-05) are already deployed; no payload migration needed.

### M2 — During PV-02 (this PR)

1. Add `FROZEN_PREFIX_V7` constant + `assert_layout_spec_invariant`
   helper to `src/devolaflow/compressor.py` (D5).
2. Add doc comments to `schemas/lean-dispatch.yaml#layout_invariant`
   citing this ADR (D6).
3. Create `tests/test_layout_invariant_multi_baseline.py` with 6 tests
   (D4).
4. Author 3 NEW golden YAMLs (`layout_invariant_v8.0.0.yaml`,
   `layout_invariant_v8.3.0.yaml`, `layout_invariant_v8.4.0.yaml`) by
   running the canonical payload constructors and saving the
   `yaml.safe_dump` output.
5. Extend `.cursor/rules/repo-governance.mdc` and `.rules/architecture.mdc`
   A-2 with the nest-vs-append clause (D7).
6. Regenerate `AGENTS.md` via `RuleCompiler.compile_all()`.

### M3 — Post-PV-02 (forward-defined for future schema generations)

When a future PV bumps `canonical_order` from length 16 → 17:

1. Add a NEW golden YAML
   `benchmarks/devolaflow_context/baselines/layout_invariant_v<NEW>.yaml`
   carrying the new key at position 17.
2. Add a NEW test
   `tests/test_layout_invariant_multi_baseline.py::test_v<NEW>_baseline_byte_identical`.
3. ALL prior baselines (v7.0.0 through v8.4.0) MUST CONTINUE TO PASS.
   This is the multi-baseline contract.
4. Bump `version` in `schemas/lean-dispatch.yaml#layout_invariant` (5 →
   6) AND extend `DEFAULT_DISPATCH_LAYOUT` in `src/devolaflow/compressor.py`.
5. Author a corresponding ADR documenting the new key + nest-vs-append
   verdict (D3 table) + cross-link to this ADR.

### M4 — Future Deprecation Path

If a top-level key is ever **deprecated** (e.g., `repos` superseded by a
multi-tenant successor), the deprecation MUST:

1. Mark the key as `deprecated: true` in `schemas/lean-dispatch.yaml`
   doc comments.
2. KEEP the key in `canonical_order` at its original position (do NOT
   remove — that would shift later positions and break the prefix).
3. Update the validator to accept payloads with the key absent (already
   the default — every position is optional).
4. Add a runtime warning when the deprecated key is present; remove the
   warning + key after a 2-cycle telegraph period.
5. Even after removal from `canonical_order`, the multi-baseline tests
   for prior generations MUST continue passing because they reference
   their own pinned canonical_order, not the live one.

## Test Plan

* `pytest tests/test_layout_invariant_multi_baseline.py -v` — 6 tests
  covering all 6 historical baselines.
* `pytest tests/test_compressor.py::TestDispatchLayoutInvariant -v` — 5
  pre-existing tests (UNCHANGED — additive extension).
* `pytest tests/test_benchmarks.py::TestLayoutInvariantBaseline -v` — 3
  pre-existing tests (UNCHANGED — additive extension).
* `pytest tests/test_no_ghost_features.py::test_reference_skill_md_tier2_parity -v`
  — PV-01 parity test (UNCHANGED — additive).
* `rg "nest-vs-append" .cursor/rules/repo-governance.mdc AGENTS.md` —
  ≥ 1 hit each (D7 verbatim).
* `rg "FROZEN_PREFIX_V7" src/devolaflow/compressor.py` — ≥ 1 hit (D5).

## Cross-References

* **Predecessor ADR**: `.local/research/adr/v7-ADR-001-cache-layout-invariant.md`
* **Cycle plan**: `.local/research/v9.0.0_implementation_plan.md` §6.2
* **Gap analysis**: `.local/research/v9.0.0_gap_analysis.md` §5.2 (B-02)
* **Reference review**: `.local/research/v9.0.0_reference_review.md` F-02 + F-03
* **Erratum**: `.local/research/v9.0.0_erratum.md` G-01 (renumber rationale)
* **Cascade plan**: `.local/research/v9.0.0_pv02_ref_cascade_plan.md`
* **Implementation surface**:
  * `src/devolaflow/compressor.py::assert_dispatch_layout` (extended D5)
  * `src/devolaflow/compressor.py::assert_layout_spec_invariant` (NEW D5)
  * `src/devolaflow/compressor.py::FROZEN_PREFIX_V7` (NEW constant D5)
  * `src/devolaflow/compressor.py::LayoutSpecInvariantError` (NEW exception D5)
  * `schemas/lean-dispatch.yaml#layout_invariant` (doc comments D6)
  * `tests/test_layout_invariant_multi_baseline.py` (NEW test module D4)
  * `benchmarks/devolaflow_context/baselines/layout_invariant_v8.0.0.yaml` (NEW)
  * `benchmarks/devolaflow_context/baselines/layout_invariant_v8.3.0.yaml` (NEW)
  * `benchmarks/devolaflow_context/baselines/layout_invariant_v8.4.0.yaml` (NEW)
  * `.cursor/rules/repo-governance.mdc` A-2 (extended D7)
  * `.rules/architecture.mdc` A-2 (extended D7)
  * `AGENTS.md` (regenerated D7)

## I-8 Invariant Compliance

This ADR is explicitly designed to leave the I-8 invariant intact:

* `schemas/lean-dispatch.yaml#layout_invariant.version` = `5` (unchanged)
* `schemas/lean-dispatch.yaml#layout_invariant.canonical_order` = length 16
  (unchanged)
* The 16 keys appear in the same order (unchanged)
* `DEFAULT_DISPATCH_LAYOUT` in `src/devolaflow/compressor.py` is the same
  16 keys in the same order (unchanged)
* All 5 backward-compat byte-baselines (`v7_0_0` / `v7_3_0` /
  `v8_0_0_p08` / `v8_0_0_p10`) continue to pass (unchanged)
* The new `assert_layout_spec_invariant` helper validates a NEW
  invariant on the SPEC, not the PAYLOAD — payload-level checks remain
  bytewise identical
* The new multi-baseline tests are additive (3 NEW tests + 3 NEW golden
  YAMLs) — no existing test is modified

If `pytest tests/test_compressor.py -v` fails after these changes, that
failure is an I-8 trigger (release blocker per the dispatch's "Critical:
I-8 invariant" clause). The PR MUST be halted, the offending change
reverted, and the I-8 trigger reported to L0.

---

*ADR-002 codifies the nest-vs-append decision rule and the multi-baseline
byte test as the v9.0.0-cycle generalisation of v7-ADR-001's additive rule.
The rule has been applied informally across 5 prior schema generations;
this ADR makes it CI-enforced. The 12-key FROZEN PREFIX matches the v7.0.0
baseline exactly; positions 13-16 remain APPEND-ONLY. Companion artifacts:
`v9.0.0_pv02_ref_cascade_plan.md` (10 ref hunks closing F-02..F-15), the
PV-02 commit (this PR), and the v8.4.2 release tag. Closes B-02 from
`v9.0.0_gap_analysis.md` §5.2.*
