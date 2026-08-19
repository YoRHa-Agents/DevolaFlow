# v9-ADR-007 — Rule Taxonomy Rebalancing + Per-Task-Type Selectivity + Soul-Set Freeze + 7-PV Cycle Rollup

**Status**: Accepted
**Cycle**: v9.0.0 PV-07 (`v9.0.0` MAJOR — cycle headline)
**Date**: 2026-04-24
**Authors**: L0 Project Agent (delegated to L3 Task Agent for PV-07 execution)

---

## Context

PV-07 is the MAJOR semver headline of the v9.0.0 cycle and closes the four
remaining structural debts in the rule-surface taxonomy that PV-01..PV-06
deferred:

* **Theme T6 #1 — Rule-surface DUPLICATION between `.cursor/rules/` and `.rules/`.** The legacy v3.x-era `.cursor/rules/devola-flow-rules.mdc` (34 lines, 6 rules) and `.cursor/rules/workflow-rules.mdc` (26 lines, 5 rules) carried verbatim duplicates of the canonical `.rules/architecture.mdc` §A-1 (P1-P5) + §A-2 (P6) rules. The v9.0.0 SI-1 overlap matrix Finding #3 flagged these as the canonical source of inter-tool rule drift — when an architectural decision evolved (e.g., A-2 cache-layout governance v2 in PV-02), the canonical `.rules/architecture.mdc` got the full v2 sub-clauses while the `.cursor/rules/` stubs stayed pinned at the v7.0.0 single-clause text. Operators on cursor-only flows would silently consume the stale stub text.

* **Theme T6 #2 — Per-task-type AGENTS.md slicing is missing.** AGENTS.md compiled to a single 538-line / 7612-token bundle spanning Soul + Architecture + Conventions + Workflow layers. A hotfix Task Agent received the full Workflow layer (W-1..W-20 = 20 cycle-process rules) when only W-9 (SI-10 pre-commit gate) and W-11 (gate module changes) actually applied to a 1-bug fix. A research Task Agent received the full Architecture layer (A-2 cache-layout governance, A-5 SSOT registry pattern) when only A-1 (4-layer hierarchy) applied to a single-stage research task. The over-broad rule corpus consumed L3 budget that should have routed to task-relevant context.

* **Theme T6 #3 — Soul-set growth is unbounded.** S-10 (Prompt-Side Governance Contract Embedding) was added in PV-04 (v8.4.4); the cycle observed no governance gate that would prevent unconstrained Soul rule additions every cycle. A 50-rule total cap exists per `improvements_zh.md` §"Rule cap" (later widened to 60 by PV-05 to absorb W-16..W-20), but no rule existed that specifically constrained the Soul layer (the layer with the most binding semantics — every Soul rule is an immutable invariant). Without a freeze governance rule, Soul could drift to S-15 / S-20 across the next two cycles, blunting the "immutable invariant" semantics.

* **Theme T6 #4 — Rule count cap is informational, not enforced.** The 60-rule HARD cap from improvements §"Rule cap" lived in design docs and the `repo-governance.mdc` body but had no CI-time enforcement. A future PV could silently push the count past 60 (the existing v8.x-era pattern where CHANGELOG entries cited "feature X ships in PV-N" but `test_no_ghost_features.py` had no coverage assertion for X — silent drift). PV-05 W-18 closed the ghost-audit refresh precondition for features; the rule-count cap needed the same lint discipline.

* **Theme T6 #5 — `.cursor/rules/*.mdc` files have no compile-only invariant.** The `.rules/` 5-layer source compiles to `.cursor/rules/repo-governance.mdc` + `AGENTS.md` via `RuleCompiler.compile_all()`. The compiler stores per-target SHA-256 hashes in `.rules/.compile-hashes.json`. But there was no test that asserted the compiled `.cursor/rules/repo-governance.mdc` matched its stored hash — meaning a hand-edit to the compiled file would silently survive until the next compile run.

PV-07 lands all five themes in one MAJOR cut. The decomposition analysis §"Theme T6" line 192 verbatim called this an "operator-visible breaking change to the governance contract" — per-task-type AGENTS.md slicing changes the rule corpus visible to cached-prefix L0 dispatchers. The MAJOR semver bump is justified by D3 (selectivity) and D4 (Soul-set freeze) — both are operator-facing semantic changes that downstream tools may need to adopt.

PV-07 is also the **cycle rollup** — the 7th and headline patch of the v9.0.0
cycle (PV-01..PV-06 shipped patches v8.4.1..v8.5.1; PV-07 ships the MAJOR
v9.0.0). The rollup deliverables (W-3 SI-3 evaluation, W-7 SI-8 retrospective,
W-16 wholesale baseline, W-19 cycle-archive, ST-7 versions.json append) are
codified in §6 below and land in lockstep with the rule rebalancing.

---

## Decisions

### D1 — Rule promotion: `.rules/*.mdc` is the canonical 5-layer source

**Decision**: confirm `.rules/{soul,architecture,conventions,workflow,style}.mdc`
as the sole canonical rule source. The 5 layer files compose into 2 compile
targets (`.cursor/rules/repo-governance.mdc` + `AGENTS.md`) via
`devolaflow.local.compiler.RuleCompiler` reading
`.rules/compile-config.yaml`. Layer file headings (`^## <prefix>-<N>`) are the
sole rule-count source-of-truth — every `^## ` heading under the 5 layer files
counts as exactly 1 rule.

**Rationale**: `.rules/*.mdc` already contains the canonical body of every rule
(verified at PV-07 S01 audit — every `.cursor/rules/devola-flow-rules.mdc` rule
has a byte-identical or strictly-richer canonical owner under
`.rules/architecture.mdc`). Promoting the 5 layer files to canonical-source
status is therefore a documentation + governance step, not a content move.

**Why not a single canonical file?** Layer separation enforces priority
discipline: Soul (P0) is `always_include: true` (per
`compile-config.yaml`), Architecture (P1) is also `always_include: true`,
and Conventions / Workflow / Style are dropped first when token budgets are
exhausted (per `_truncate_to_budget` in `compiler.py`). Collapsing to one
file would break that priority machinery.

### D2 — Stub deprecation: `.cursor/rules/{devola-flow,workflow}-rules.mdc` → cross-reference scaffolds

**Decision**: cut both legacy stubs to ≤ 50-line cross-reference scaffolds
that point operators at `.rules/` for the canonical rule body. The new stub
shape:

```
---
description: "DEPRECATED — use .rules/{soul,architecture,...}.mdc instead"
alwaysApply: true
---

# Deprecated — see .rules/

This file used to carry P1-P{5,6} dispatcher invariants. As of v9.0.0
(PV-07 ADR-007), the canonical rule source is `.rules/architecture.mdc` (A-1
4-layer hierarchy + A-2 cache-layout governance). This file remains as a
stub so existing `.cursor/rules/` discovery paths still load *something*;
the actual rules now live in:

| Layer | Canonical file |
|---|---|
| Soul (P0) | `.rules/soul.mdc` |
| Architecture (P1) | `.rules/architecture.mdc` |
| Conventions (P2) | `.rules/conventions.mdc` |
| Workflow (P3) | `.rules/workflow.mdc` |
| Style (P4) | `.rules/style.mdc` |

Compiled outputs:
* `.cursor/rules/repo-governance.mdc` (full corpus, MDC format, 8K budget)
* `AGENTS.md` (Soul + Arch + Conv + Workflow, Markdown, 8K budget)

Run `python -c "from devolaflow.local.compiler import RuleCompiler;
RuleCompiler('.rules/compile-config.yaml').compile_all()"` to regenerate.
```

**Rationale**: keeping the stubs as discoverable cross-references serves three
purposes: (a) operators on cursor-only flows that auto-load `.cursor/rules/*.mdc`
still see a clear pointer to the canonical source instead of a 404 / stale text;
(b) the deprecation is reversible — a future cycle can promote the stubs back
without breaking discovery; (c) the stub line count (≤ 50) is well under the
default tier ceiling per C-4 SF-1, leaving headroom for the deprecation note +
canonical-file table.

**Why not delete the stubs entirely?** Some downstream Cursor-tool integrations
(specifically the v3.6.0..v6.x-era `cursor` adapter and a handful of installed
projects that reference the stubs verbatim) would emit a "rule file missing"
warning on startup. Keeping the stubs as cross-reference scaffolds preserves
zero-downtime upgrade for those operators while making the deprecation
explicit.

### D3 — Per-task-type AGENTS.md slicing (the OPERATOR-VISIBLE breaking change)

**Decision**: introduce a NEW `select_agents_md_slice(task_type) -> dict`
function in `src/devolaflow/task_adaptive_selector.py` + a NEW
`meta.agents_md_slice` block in `workflow-system/agent/context_profiles.yaml`.
The slice filters the compiled AGENTS.md content per a per-task-type layer-prefix
mapping, hiding rules irrelevant to the task. The 9 canonical task-profile
slices are documented verbatim in `.local/research/v9.0.0_pv07_rule_audit.md` §2.2.

**Default `enabled: false`** — preserves v8.5.1 byte-identical full-AGENTS.md
behaviour for every L0/L1/L2/L3 dispatcher that has not opted in.

**Activation**: operators flip `meta.agents_md_slice.enabled: true` in their
local `context_profiles.yaml` (or pass `--slice` to the
`task_adaptive_selector` CLI) to enable per-task slicing. Per
`references/env-flags.md` §7 W-20 reuse-first analysis: the slicing has a
NEW activation surface (post-compile filter rather than runtime hook reuse),
so the new YAML knob is justified — it does NOT need a separate `DEVOLAFLOW_*`
env-flag because the activation surface is the YAML config, not the env.

**MAJOR semver justification** (per playbook §6.7.1):

> *T6 是 breaking change to governance contract — per-task-type AGENTS.md
> slicing changes the rule corpus visible to cached-prefix L0 dispatchers
> per `v9.0.0_decomposition_analysis.md` §"Theme T6" line 192 verbatim.*

When an operator opts into slicing, the cached prefix that L0 sends to L1/L2/L3
dispatchers shrinks by 15-70% depending on task type. For long-running L0
sessions that cache the AGENTS.md prefix between dispatches, this is an
observable change in the input prompt — downstream tools that audit / log
prompts will see different content. The default `enabled: false` makes the
breaking change opt-in, but the existence of the opt-in surface IS the MAJOR
semver justification per the v9.0.0 SI-1 contract.

**Why a runtime selector and not a compile-time slice?** Compile-time slicing
would require N compiled AGENTS.md files (one per task profile), multiplying
the canonical surface and creating drift opportunities. Runtime selection
keeps a single canonical AGENTS.md and applies the filter at dispatch time,
preserving the SSOT pattern A-5 codified in PV-03.

### D4 — Soul-set freeze governance: W-21 — Soul-Set Freeze Governance

**Decision**: add **W-21 — Soul-Set Freeze Governance** to
`.rules/workflow.mdc`. The new W-rule codifies a 2-cycle telegraph + retrospective entry requirement before any future Soul (S-*) addition:

> *The Soul rule layer is FROZEN at S-1..S-10 as of v9.0.0 (PV-07). Any
> future Soul addition (S-11+) MUST be preceded by:*
>
> 1. *A 2-cycle telegraph: an explicit deferral note in cycle N's
>    retrospective (§3 "Deferred and why") flagging the proposed S-X for
>    cycle N+2 review (not N+1 — the 2-cycle gap forces deliberate
>    consideration across at least one full release cadence).*
> 2. *A SI-1 gap-analysis entry in cycle N+2 documenting (a) the immutable
>    invariant the new S-X enforces, (b) why no existing S-* / A-* / W-*
>    rule covers the invariant, (c) the proposed CI-time enforcement
>    surface (test name + module path).*
> 3. *A unanimous SI-3 evaluation §3.2 (architecture rationality) score
>    of 9.5+ from cycle N+2's L0 — Soul additions are by definition
>    architectural decisions of the highest priority.*

**Rationale**: Soul rules are immutable invariants — the lifetime cost of
each S-* is the multiplicative product of (every future agent dispatch) ×
(every future code change) × (every future audit). A 2-cycle deliberation
gate ensures Soul additions have crossed at least one cycle's worth of
real-world usage before ratification. The retrospective-first protocol
(rule 1 above) means any L0 proposing an S-* in cycle N writes the
deferral note in their own cycle's retrospective — putting the rationale on
the public record for cycle N+2's L0 to inherit.

**Why not freeze the Architecture / Workflow layers similarly?** Architecture
rules are constraint-bearing but their evolution maps to schema / module
refactor cycles (e.g., A-5 SSOT registry pattern emerged from PV-03's M-001 +
M-002 work). Workflow rules are process-bearing and naturally evolve with
each cycle's lessons (e.g., W-16..W-20 codified the v9.0.0 cycle's process
discoveries in PV-05). Soul rules are immutable INVARIANTS — they don't
naturally evolve; they accrete only when a new immutable constraint is
discovered. The 2-cycle telegraph is calibrated for that accretion rate.

**W-21 wording** (full text lands in `.rules/workflow.mdc` per T07 / T05):

```
## W-21 — Soul-Set Freeze Governance

The Soul rule layer (S-1..S-N) is FROZEN at the count established by the
most recent MAJOR or MINOR cycle release. Any proposed addition (S-(N+1))
MUST satisfy ALL of the following BEFORE landing:

1. **2-cycle telegraph**: the proposing L0 / human authors a deferral note
   in cycle N's retrospective (§3 "What was deferred and why") flagging
   the proposed S-(N+1) for cycle N+2 review. Cycle N+1 explicitly
   does NOT consider the addition — the 2-cycle gap is mandatory.
2. **SI-1 gap-analysis entry in cycle N+2** documenting: (a) the
   immutable invariant the new rule enforces, (b) why no existing
   S-* / A-* / W-* rule covers the invariant, (c) the proposed CI-time
   enforcement surface (test name + module path), (d) the per-cycle
   review trail (the §3 deferral note from cycle N).
3. **SI-3 evaluation §3.2 architecture-rationality score ≥ 9.5/10**
   from cycle N+2's L0 (Soul additions are architectural decisions of
   the highest priority — the score floor is stricter than the
   minor-release composite ≥ 8.5 / major ≥ 9.0 thresholds).
4. **Soul cap**: post-addition Soul layer count MUST stay ≤ 12. Beyond
   that, the Soul layer's immutable-invariant semantics weaken; future
   additions move to Architecture (P1) instead.

Source: v9.0.0 PV-07 — codified per ADR-007 D4 (Soul-set freeze
governance).
```

The current Soul-set freeze locks at **10 entries** (S-1..S-10) at v9.0.0
release. Any proposed S-11 must be telegraphed in v9.0.0's retrospective
(deferred to v9.2.0 — cycle N+2), gap-analysed in v9.2.0 SI-1, and pass
v9.2.0 L0's SI-3 §3.2 ≥ 9.5/10.

### D5 — CI-time rule-count cap: `test_rule_count_under_cap`

**Decision**: add a NEW lint `tests/test_no_ghost_features.py::test_rule_count_under_cap`
that walks `^## ([SACW]|ST)-\d+` headings under AGENTS.md and asserts the
total count ≤ **60** (HARD cap from `improvements_zh.md` §"Rule cap" + PV-05
W-rule additions). Failure means the next PV cannot land its rule addition
without first either (a) deferring an existing rule, or (b) explicitly
raising the cap via a documented ADR.

**60-cap rationale**: the v8.4.0 baseline was 50 rules (Soul 9 + Arch 4 +
Conv 9 + WF 15 + Style 13). The v9.0.0 cycle added 7 net rules (PV-03 A-5,
PV-04 S-10, PV-05 W-16..W-20, PV-07 W-21) bringing the total to 58 — within
the 60 cap by 2 entries. A future cycle proposing a single new rule has
1 entry of headroom; proposing 2 requires deferral or cap raise. The 60
cap is the absolute upper bound — beyond that, the cumulative rule
corpus exceeds the L3 dispatch budget (~8K tokens) per A-3.

**Companion lint `test_rule_surfaces_compile_only`**: verifies the compiled
`.cursor/rules/repo-governance.mdc` SHA-256 matches the value stored in
`.rules/.compile-hashes.json` (the drift surface that
`devolaflow.local.compiler.RuleCompiler.compile_all()` populates). Failure
means a hand-edit was made to the compiled file without re-running the
compiler — the canonical source-vs-compiled invariant is broken. Also
verifies the deprecated `.cursor/rules/{devola-flow,workflow}-rules.mdc`
stubs match expected stub-template content (a hand-edit to either stub
fails the lint).

---

## Rationale

### Why bundle T6 #1..#5 + cycle rollup in PV-07?

The v9.0.0 SI-1 cycle plan §6.7 deliberately scoped PV-07 as the cycle
headline because:

1. **Theme T6 is structurally coupled.** The 5 sub-themes share a single
   surface (the rule taxonomy) — staggering them would multiply the
   surface-area churn across 3 PVs without buying any regression
   mitigation. T6 #1 (rule promotion) + T6 #2 (slicing) + T6 #3 (Soul
   freeze) + T6 #4 (CI cap) + T6 #5 (compile-only lint) are 5 facets of
   the same rule-rebalancing decision.

2. **The MAJOR semver bump is the right granularity.** Per the v9.0.0 SI-1
   gap analysis §1.2 line 69 verbatim: *"Cycle size estimate: 8 PVs = 4
   PATCH (PV-01..PV-04) + 2 MINOR (PV-05, PV-06) + 1 MAJOR (PV-07) + 1
   optional sustaining PATCH (PV-08)"*. PV-07 is the cycle's only MAJOR
   bump — bundling the 5 sub-themes here gives operators one MAJOR
   "Adoption notes" section to grep against instead of fragmenting the
   change across PV-07a / PV-07b / PV-07c minor-release scenarios.

3. **The cycle rollup naturally lands in PV-07.** The 7-PV cycle has accumulated
   the SI-3 / NineS / EvoBench evidence + retrospective material across
   PV-01..PV-06; aggregating them in PV-07 (the MAJOR cut) produces a
   single navigable cycle-archive snapshot per W-19. The `docs/cycle-archive/v9.0.0/`
   tree + `versions.json` v9.0.0 entry per ST-7 + the SI-8 4-section
   retrospective per W-7 all benefit from the bundle.

### Why MAJOR (v9.0.0) and not MINOR (v8.6.0)?

Per the playbook §6.7.6 risk handling **R-1** (MAJOR justification fails at S05
sign-off): the contingency is to downgrade to v8.6.0 MINOR with T6 deferred.
The decision to ship as MAJOR instead of MINOR rests on D3 — per-task-type
AGENTS.md slicing changes the rule corpus visible to cached-prefix L0
dispatchers, even though the activation surface defaults to OFF. Operators
running long-lived L0 sessions that cache the prefix WILL observe a different
input prompt when they opt in. The semver contract (per `https://semver.org`)
says any change that breaks the API contract is MAJOR; the prefix
contract IS the API contract for cached-prefix dispatchers.

### Why the deprecated stubs stay as ≤ 50-line scaffolds (not deleted)?

Per D2 rationale: zero-downtime upgrade for cursor-only flows. Deletion would
emit a "rule file missing" warning at startup for some downstream
integrations; a 50-line cross-reference scaffold preserves discoverability
without carrying the duplicate content. The stub size cap is enforced by
`tests/test_no_ghost_features.py::test_rule_surfaces_compile_only` (which
verifies the stub content matches the expected stub template — preventing
both content drift AND scope creep back to a full rule set).

### Why the W-21 freeze locks Soul at 10 (not 9 or 12)?

The S-10 addition in PV-04 (Prompt-Side Governance Contract Embedding) closed
C-03 from the v9.0.0 SI-1 gap analysis §3.1 — the most recent immutable
invariant codified for the v9.0.0 cycle. Locking the freeze at the post-PV-04
count (10) preserves the closure without inflating the layer further. Future
additions go through the W-21 2-cycle telegraph; the absolute Soul cap is 12
(per W-21 D4 #4) — beyond that, the immutable-invariant semantics weaken
because the cumulative invariant set becomes unmemorable.

---

## Consequences

### Operator-visible behaviour change (the MAJOR semver justification)

Operators running DevolaFlow under per-task-type slicing (opt-in via
`meta.agents_md_slice.enabled: true`) will see the AGENTS.md prefix length
change per task type after `v9.0.0`:

| Task profile | AGENTS.md tokens (full) | AGENTS.md tokens (sliced) | Reduction |
|---|---:|---:|---:|
| hotfix | ~7600 | ~4500 | ~40% |
| feature | ~7600 | ~6500 | ~15% |
| research | ~7600 | ~2300 | ~70% |
| refactor | ~7600 | ~6100 | ~20% |
| review | ~7600 | ~3800 | ~50% |
| design | ~7600 | ~5300 | ~30% |
| convergence / rdrr | ~7600 | ~7600 | 0% (full set) |
| documentation | ~7600 | ~4600 | ~40% |
| default (unmatched) | ~7600 | ~7600 | 0% (full set, safe fallback) |

**Operators on the v8.5.1 byte-stable surface** (default `enabled: false`)
get **zero behaviour change**. The slicing is opt-in via YAML; operators
who want byte-identical v8.5.1 behaviour leave the new `agents_md_slice`
block at its default. The ADR-007 enforcement test
`test_rule_count_under_cap` is independent of the slicing — it always
exercises the full AGENTS.md compile output regardless of slicing state.

### Deprecated `.cursor/rules/*` files

Operators relying on the legacy `.cursor/rules/devola-flow-rules.mdc` or
`.cursor/rules/workflow-rules.mdc` files for rule body content will see ≤ 50-line
cross-reference scaffolds pointing at `.rules/`. The actual rule content is
unchanged — it lives in `.rules/architecture.mdc` (A-1 + A-2) and is
compiled into the canonical `.cursor/rules/repo-governance.mdc` target.
Migration: switch tooling to read `.cursor/rules/repo-governance.mdc` (the
compiled full corpus) or `.rules/architecture.mdc` (the canonical source).

### Soul-set freeze: any future S-11 requires the W-21 protocol

After v9.0.0 release, the Soul layer is locked at S-1..S-10. Cycle authors
proposing S-11+ MUST follow the 2-cycle telegraph (retrospective deferral in
cycle N → SI-1 gap analysis in cycle N+2 → SI-3 §3.2 ≥ 9.5/10 in cycle N+2).
The protocol is enforced by W-21's normative wording in `.rules/workflow.mdc`
(no automated CI lint — the gating is human-side per the multi-cycle
deliberation requirement; W-21's enforcement surface is the SI-3 §3.2
review).

### Test surface area

PV-07 adds **+8 NEW test functions** (within the +30 per-PV cap per W-17):

* `tests/test_no_ghost_features.py::test_rule_count_under_cap` — counts rules in compiled AGENTS.md, asserts ≤ 60.
* `tests/test_no_ghost_features.py::test_rule_surfaces_compile_only` — SHA-256 drift detection on `.cursor/rules/repo-governance.mdc` + stub-template parity for the 2 deprecated stubs.
* `tests/test_pv07_agents_md_slice.py::test_slice_disabled_returns_full_byte_identical` — R5 strict pin (default OFF preserves v8.5.1 byte-stable AGENTS.md).
* `tests/test_pv07_agents_md_slice.py::test_slice_hotfix_includes_only_relevant_layers` — slicing semantic for hotfix profile.
* `tests/test_pv07_agents_md_slice.py::test_slice_research_minimal_corpus` — slicing semantic for research profile.
* `tests/test_pv07_agents_md_slice.py::test_slice_convergence_full_corpus` — slicing semantic for convergence (no reduction).
* `tests/test_pv07_agents_md_slice.py::test_slice_unmatched_falls_back_to_full` — fallback semantic.
* `tests/test_pv07_agents_md_slice.py::test_slice_skipped_layer_drops_layer_header` — top-level layer header dropping when no rule survives.

Cumulative cycle delta from v8.4.0 baseline (per W-17 mid-cycle audit at
PV-05): +75 NEW test functions through PV-06 + 8 from PV-07 = **+83**
cumulative, well under the +150 cycle cap.

### Cross-cutting references

* `workflow-system/agent/references/` — no new reference; the SF-4 set stays at **14** (the PV-06 `compression-pipeline.md` was the most recent addition).
* `.rules/workflow.mdc` gains W-21 (~+30 LOC).
* `.rules/index.md` count comment updates (51 → 58).
* `.rules/.compile-hashes.json` is regenerated by `RuleCompiler.compile_all()` after the W-21 addition.
* `AGENTS.md` is regenerated to absorb W-21 (~ 538 → ~ 565 lines after full recompile).

### Cascading-coupling updates landed in lockstep

* `tests/test_no_ghost_features.py` adds 2 new tests (rule cap + compile-only drift); pre-existing 28 tests untouched.
* `tests/test_pv07_agents_md_slice.py` is NEW (6 tests).
* `workflow-system/agent/context_profiles.yaml` adds the `meta.agents_md_slice` block (~ +30 LOC nested under existing `meta:`).
* `src/devolaflow/task_adaptive_selector.py` adds the `select_agents_md_slice` function (~ +150 LOC).
* `src/devolaflow/local/compiler.py` extends to support per-target stub-template hashing (~ +60 LOC).
* `src/devolaflow/local/drift.py` extends to expose `check_stub_drift` for the 2 deprecated stubs (~ +40 LOC).
* `.cursor/rules/devola-flow-rules.mdc` reduced to a ≤ 50-line cross-reference stub (−~ 50 LOC delta from previous text).
* `.cursor/rules/workflow-rules.mdc` reduced to a ≤ 50-line cross-reference stub (−~ 50 LOC delta).
* `CHANGELOG.md` `## [9.0.0]` entry with explicit "Adoption notes" listing the 3 breaking-change facets (rule-surface semantics, deprecated stubs, Soul-set freeze).
* 7 canonical version-sync locations updated 8.5.1 → 9.0.0 via `scripts/bump_version.py`.
* `benchmarks/devolaflow_context/baselines/v9.0.0_baseline.json` regenerated wholesale per W-16.
* `workflow-system/human/demo/version-timeline/versions.json` appends v9.0.0 entry per ST-7.
* `docs/cycle-archive/v9.0.0/` populated per W-19.

---

## Alternatives Considered

### Alt-1 — Additive-only (no `.cursor/rules/` deprecation)

**Rejected.** Would leave the duplicate stubs in place, perpetuating the
inter-tool rule drift discovered by the v9.0.0 SI-1 overlap matrix Finding
#3. The legacy stubs already drift from `.rules/architecture.mdc` (e.g.,
the stubs' Rule 6 references the v7.0.0 single-clause P6 text while
`.rules/architecture.mdc` §A-2 carries the full v8.0.0 + v9.0.0 PV-02
v2 sub-clauses). Keeping the stubs as full duplicates compounds the drift
every cycle.

### Alt-2 — Compile-time slicing (multiple AGENTS.md files)

**Rejected.** Would require N compiled AGENTS.md files (one per task profile),
multiplying the canonical surface and creating drift opportunities (the
SSOT pattern A-5 explicitly forbids splitting a single canonical surface
across multiple files). Runtime selection preserves the single canonical
AGENTS.md and applies the filter at dispatch time.

### Alt-3 — Mint a new `DEVOLAFLOW_AGENTS_MD_SLICE` env-flag

**Rejected** per W-20 reuse-first analysis. The slicing's activation surface
is the YAML config block (`meta.agents_md_slice.enabled`), NOT the env. A
new env-flag would add a third activation knob (env + YAML + CLI), violating
W-20's reuse-first contract. The YAML knob is the natural surface because
slicing is a per-deployment configuration, not a per-process toggle.

### Alt-4 — Defer T6 #4 (60-cap CI lint) to v9.1.0

**Rejected.** Without the CI cap, a future PV could silently push the rule
count past 60 (the v8.4.x-era pattern where CHANGELOG entries cited
"feature X ships in PV-N" but `test_no_ghost_features.py` had no coverage
assertion for X). PV-05 W-18 closed the ghost-audit refresh precondition for
features; the rule-count cap needs the same lint discipline IN THE SAME PV
to prevent the inverse drift (rules added without test coverage).

### Alt-5 — Defer T6 #5 (compile-only invariant) to v9.0.x sustaining

**Rejected.** Without the compile-only lint, hand-edits to
`.cursor/rules/repo-governance.mdc` would silently survive until the next
compile run — the exact drift pattern that the SHA-256 hash store in
`.rules/.compile-hashes.json` was designed to prevent. The lint is the
invocation that makes the hash store enforceable; deferring it leaves the
hash store as a passive artifact.

### Alt-6 — Soul cap at 9 (revert PV-04 S-10) instead of 10

**Rejected.** S-10 closed C-03 from the v9.0.0 SI-1 gap analysis §3.1 — the
prompt-side governance contract embedding is a foundational invariant for
the lifecycle hook chain (per `v9-ADR-004` D1). Reverting S-10 would re-open
C-03 and break the `tests/test_dispatch_emission_runs_hooks.py` regression
suite that pins the invariant at the test layer. The freeze locks at 10
because that's the count established by PV-04's closure of C-03.

---

## Migration

### For operators on default `meta.agents_md_slice.enabled: false`

**No action required.** The slicing is opt-in; operators on the v8.5.1
byte-stable surface get zero behaviour change. The full AGENTS.md (post-W-21
addition, ~ 565 lines) loads byte-identically to the v8.5.1 surface plus the
new W-21 section (the only delta).

### For operators wanting per-task-type slicing

Edit `workflow-system/agent/context_profiles.yaml` and flip
`meta.agents_md_slice.enabled: true`. The default per-profile layer mapping
(documented in `.local/research/v9.0.0_pv07_rule_audit.md` §2.2) covers the
9 canonical task profiles (hotfix, feature, research, refactor, review,
design, convergence, documentation, default). Operators with custom profiles
add new entries under `meta.agents_md_slice.profiles.<profile_name>`:

```yaml
meta:
  agents_md_slice:
    enabled: true
    profiles:
      my_custom_profile:
        soul: all                    # all S-* rules
        architecture: ["A-1", "A-2"]  # only A-1 + A-2
        conventions: ["C-1"]         # only C-1
        workflow: ["W-9"]            # only W-9
        style: []                    # no style rules
    fallback: full                   # unmatched → return full AGENTS.md
```

### For operators relying on `.cursor/rules/{devola-flow,workflow}-rules.mdc`

Switch tooling to read either:

* `.cursor/rules/repo-governance.mdc` — the compiled full corpus (MDC format,
  8K budget), regenerated from `.rules/*.mdc` by every `RuleCompiler.compile_all()`
  invocation; OR
* `.rules/architecture.mdc` — the canonical Architecture rule body (A-1
  4-layer hierarchy + A-2 cache-layout governance).

The deprecated stubs remain as ≤ 50-line cross-reference scaffolds for
discoverability; operators reading them MUST follow the cross-reference
table to the canonical files for the actual rule content.

### For cycle authors proposing future Soul (S-11+) rules

Follow the W-21 protocol in full:

1. **Cycle N** retrospective (`§3 What was deferred and why`) carries an
   explicit deferral note flagging the proposed S-(N+1) for cycle N+2 review.
2. **Cycle N+1** explicitly does NOT consider the addition (the 2-cycle
   gap is mandatory per W-21 #1).
3. **Cycle N+2** SI-1 gap analysis documents the immutable invariant + why
   no existing rule covers it + the proposed CI-time enforcement.
4. **Cycle N+2** SI-3 §3.2 architecture-rationality scores the proposal
   ≥ 9.5/10. Below that → the addition fails W-21 and the proposal is
   either revised + re-telegraphed or abandoned.

---

## Rollback plan

Per playbook §6.7.6 R-1 (MAJOR justification fails at S05 sign-off):

* **R-1** triggers (MAJOR justification fails) → propose downgrade to v8.6.0
  MINOR; T6 deferred to v9.x sustaining; PV-07 becomes "additive selectivity
  only" minor scope; annotated tag → v8.6.0; v9.0.0 cycle restarts at SI-1.
* **R-8** triggers (rule count > 60) → defer 1-2 W-rules from PV-05 to v9.x
  sustaining; `test_rule_count_under_cap` as `xfail(strict=False)` + retrospective entry.
* **R-9** triggers (cached-prefix break) → selector falls back to full AGENTS.md;
  MAJOR semver still justified; CHANGELOG adds "selector is opt-in for v9.0.0;
  default = full AGENTS.md".
* **SI-3 < 9.0** → revert PR + re-enter SI-1 + evaluate downgrade to v8.6.0
  MINOR. REPORT TO L0; do not auto-resolve.

All rollback paths preserve the cycle's other improvements (PV-01..PV-06
already shipped as patches v8.4.1..v8.5.1) and target only the PV-07 surface.

---

## Enforcement

Detected at test time:

* **R5 byte-identical invariant** (slicing default OFF) →
  `tests/test_pv07_agents_md_slice.py::test_slice_disabled_returns_full_byte_identical`.
* **Per-profile slicing semantic** →
  `tests/test_pv07_agents_md_slice.py::test_slice_{hotfix,research,convergence,documentation}_*`.
* **Rule count ≤ 60 HARD cap** →
  `tests/test_no_ghost_features.py::test_rule_count_under_cap`.
* **Compile-only invariant for `.cursor/rules/*`** →
  `tests/test_no_ghost_features.py::test_rule_surfaces_compile_only`.
* **W-21 Soul-set freeze content presence** →
  `tests/test_no_ghost_features.py::test_skill_reference_links_match_sf4_set`
  (extended at PV-07 to assert W-21 heading present in compiled AGENTS.md;
  the SF-4 set stays at 14, no reference change).

Detected at CI-time:

* **W-9 / SI-10 6/6 step discipline** → invoked by release commit pre-flight.
* **Layout invariant unchanged** →
  `tests/test_layout_invariant_multi_baseline.py` continues passing for
  all 6 historical baselines (v7.0.0, v7.3.0, v8.0.0 P-08, v8.0.0 P-10,
  v8.3.0 PV-05, v8.4.0).

---

## Source

* `.local/research/v9.0.0_gap_analysis.md` §5.7 (21-file scope + cycle rollup deliverables).
* `.local/research/v9.0.0_implementation_plan.md` §6.7 (5-stage / 9-wave / 20-task runbook — most complex PV).
* `.local/research/v9.0.0_pv07_rule_audit.md` (PV-07 S01 deliverable: T01 rule deprecation audit + T02 per-task-type slice design).
* `.local/research/v9.0.0_decomposition_analysis.md` §"Theme T6" (line 192 verbatim — MAJOR semver justification).
* `.local/research/v9.0.0_overlap_matrix.md` Finding #3 (rule duplication evidence).
* Prior cycle ADRs (chronological): v9-ADR-001 (PV-01 SKILL headroom) → v9-ADR-002 (PV-02 cache layout v2) → v9-ADR-003 (PV-03 A-5 SSOT registry) → v9-ADR-004 (PV-04 S-10 lifecycle wiring) → v9-ADR-005 (PV-05 W-rules + nines hygiene) → v9-ADR-006 (PV-06 compression pipeline + B3 flip) → **v9-ADR-007 (PV-07 — this ADR)**.
* `workflow-system/agent/references/env-flags.md` §7 (W-20 reuse-first analysis applied to D3 activation surface).
* Canonical rule sources: `.rules/{soul,architecture,conventions,workflow,style}.mdc`.
