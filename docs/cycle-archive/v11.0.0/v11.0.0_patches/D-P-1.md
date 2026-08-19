# D-P-1 — Patch Design Specification

> **Direction**: A-2 canonical_order 17-field "merge-eligible" audit
> **Source**: `.local/research/v10_internal_optimization_directions.md` §3.2 D-P-1 (lines 111-118)
> **Author**: L3 Task Agent, Wave 4a (D-P Protocol Evolution)
> **Date**: 2026-05-04
> **Cycle**: v11.0.0 SI-1 planning
> **Constraints**: AUDIT-ONLY per source doc — "审计本身**不动 schema**——仅产出建议" (line 116). G-6 frozen-prefix gate respected: positions 1-12 NEVER modified.

---

## §1 — Current State

`schemas/lean-dispatch.yaml` (lines 542-563) declares `layout_invariant.canonical_order` length 17 (schema version 6, last bumped at v9.7.0 PV-02). The 17 keys split into:

* **FROZEN PREFIX** (positions 1-12, A-2.1): `hdr` / `task` / `goal` / `assumptions` / `pred` / `files` / `rules` / `shared` / `accept` / `reinforce` / `verify_cfg` / `gate` — pinned to v7.0.0 baseline; reorder is a release blocker enforced by `src/devolaflow/compressor/layout.py::FROZEN_PREFIX_V7` (lines 134-147) and `assert_layout_spec_invariant` (lines 171-224).
* **APPEND-ONLY TAIL** (positions 13-17, A-2.2): `repos` (v7.2.6 P-06) / `behavioral_guidelines` (v8.0.0 P-08) / `acceptance_criteria_v2` (v8.0.0 P-10) / `change_context` (v8.3.0 PV-05) / `predecessor_dedup_ledger` (v9.7.0 PV-02).

Five historical NEST decisions live as sub-fields per A-2.3 (`gate.token_budget`, `pred[*].compact_directive`, `pred[*].summary_mode`, `compression_rules.bypass_conditions`, `compression_rules.data_envelope_required`). Multi-baseline byte test at `tests/test_layout_invariant_multi_baseline.py` pins **10 baselines** (v7.0.0 → v10.2.0) — drift in any one fails CI.

What is NOT measured today: the **non-emptiness rate per tail field**. No tooling exists to scan `.local/.agent/handoff/` envelopes or historical dispatch payloads to determine which tail fields are populated in 80%+ of dispatches vs which are < 5% (the threshold above which APPEND was the right call vs below which NEST may have been more economical).

## §2 — Patch Design

**Algorithm** (audit-only — zero schema change):

1. New script `scripts/audit_canonical_order.py` (~150 LOC). Public entry `audit_canonical_order(handoff_dir: Path, since: str | None = None) -> CanonicalOrderReport`.
2. Walk `.local/.agent/handoff/*.yaml` envelopes and (optionally) historical retros that embed dispatch fixtures. For every dispatch payload, count per-canonical-position non-emptiness.
3. Emit `non_empty_rate` (float in [0, 1]) per position 13-17. Positions 1-12 are reported but flagged "FROZEN — non-emptiness rate informational only; reorder/merge prohibited per G-6 + A-2.1".
4. Output `.local/research/v11.0.0_canonical_order_audit.md` with a table: `position | key | non_empty_rate | nest_candidate? | rationale`. The `nest_candidate?` column applies the A-2.3 decision matrix mechanically (lines 87-94 of `v9-ADR-002`) — flags TAIL fields whose data shape COULD be NEST under an existing block.
5. Companion CLI flag `--include-positions 1-12` is REJECTED at argparse-time with the explicit reminder that positions 1-12 are FROZEN per `src/devolaflow/compressor/layout.py::FROZEN_PREFIX_V7`.

**Files touched**:

* `scripts/audit_canonical_order.py` (NEW; ~150 LOC).
* `tests/test_audit_canonical_order.py` (NEW; ~120 LOC; 6-8 test functions).
* `.local/research/v11.0.0_canonical_order_audit.md` (NEW; report output, gitignored under `.local/`).

**API surface** (zero public Python additions in `src/devolaflow/__init__.py`; the script is a developer tool, not a runtime API):

```python
def audit_canonical_order(
    handoff_dir: Path = Path(".local/.agent/handoff"),
    since: str | None = None,
) -> CanonicalOrderReport: ...

@dataclass
class CanonicalOrderReport:
    sampled_count: int
    per_position_rates: dict[str, float]   # key → non_empty_rate
    nest_candidates: list[str]             # tail keys with rate < 0.05
    frozen_prefix_warning: str             # always present; G-6 reminder
```

**No schema changes**: `schemas/lean-dispatch.yaml` is read-only for this patch. `tests/test_layout_invariant_multi_baseline.py` is NOT modified — the 10 existing baselines stay frozen.

## §3 — Small Project Evaluation

**Synthetic test bed**: `synthetic_small_repo` (per `v11.0.0_evaluation_methodology.md` §2). The small repo has only the `init` operation invoking `repo-init` workflow, which produces a single dispatch with `pred=[]`, `repos=[]`, `behavioral_guidelines={}`, `acceptance_criteria_v2=[]`, `change_context=null`, `predecessor_dedup_ledger=null` (round 1).

**Operations exercised**: `init`, `feature` (1-file scope), `bugfix` (1-line fix). Each generates 1 dispatch payload.

**Metric collection** (per §4.2 architecture-health metrics):

* `canonical_order field non-emptiness rate` (per field, per dispatch).
* `audit script wall-clock time` (seconds).

**Expected delta (before → after)**:

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Tail-field non-emptiness rate (pos 13-17, mean) on small repo | unknown | ~0.10 (only `change_context` populated when workspace engaged) | informational only | improve (visibility) |
| Audit script wall-clock for small repo (3 dispatches) | N/A | ≤ 0.5s | new measurement | improve (visibility) |
| Number of `nest_candidate` flags raised on small repo | N/A | 4 of 5 tail fields (small repos rarely populate `repos` / `behavioral_guidelines` / `acceptance_criteria_v2` / `predecessor_dedup_ledger`) | new measurement | improve (data point) |

**Pass criterion**: audit script completes < 1s on a 3-dispatch sample; `nest_candidate` count is reported (any number is informational — the audit succeeds when it produces a parseable report, NOT when it recommends specific merges).

**If no improvement on small project**: small projects produce trivially-correct audit data (low signal, high noise). The audit is INHERENTLY a large-project tool — small-tier passes by virtue of the script running, not by recommending merges.

## §4 — Large Project Evaluation

**Test bed**: DevolaFlow self at v10.3.0 baseline.

**Metric collection** (per §4.2 architecture-health metrics):

* `canonical_order field non-emptiness rate` (per tail field; sampled across `.local/.agent/handoff/` and historical retros).
* `nest_candidate count` (number of tail fields where merge to NEST would be data-shape-legal per A-2.3).
* `multi-baseline byte test status` (must stay 10/10 PASS).

**Expected delta (v10.3.0 baseline → post-patch)**:

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Tail-field non-emptiness rates documented | 0 fields measured | 5 fields measured | +5 | improve (visibility) |
| `nest_candidate` flags raised (informational) | unknown | expected 1-3 of 5 (`predecessor_dedup_ledger` populated only on round-N>1; `behavioral_guidelines` defaults injected by profile so likely 100%; `repos` populated only on multi-repo dispatches) | new measurement | improve (decision input) |
| `tests/test_layout_invariant_multi_baseline.py` PASS count | 10/10 | 10/10 | 0 | preserve (G-6) |
| `assert_layout_spec_invariant` invocation count | unchanged | unchanged | 0 | preserve (G-6) |
| LOC added to `src/devolaflow/` | 0 | 0 | 0 | preserve (audit lives under `scripts/`) |

**Pass criterion**: report enumerates non-emptiness rate for ALL 5 tail fields AND multi-baseline byte test stays 10/10 PASS.

**Side-effect check** (MUST NOT regress):

* `tests/test_layout_invariant_multi_baseline.py` — all 10 baselines (v7.0.0 → v10.2.0) MUST stay PASS. Touched zero schema bytes.
* `src/devolaflow/compressor/layout.py::FROZEN_PREFIX_V7` — bytes-identical to v9.0.0 PV-02 baseline.
* `tests/test_compressor.py::TestDispatchLayoutInvariant` — all assertions stay green.

## §5 — Benefit Metrics (≥ 3 quantitative; DF-internal)

| # | Metric | Before (v10.3.0) | After (v11.0.x audit PV) | Δ | Bucket |
|:---:|---|---:|---:|---:|---|
| 1 | `canonical_order` tail fields with documented non-emptiness rate | 0 / 5 | 5 / 5 | +5 fields (+100%) | §4.2 architecture |
| 2 | Schema-evolution decision input artifacts in `.local/research/` | 0 | 1 (`v11.0.0_canonical_order_audit.md`) | +1 | §4.2 architecture |
| 3 | Audit script wall-clock for DevolaFlow self (estimated handoff sample ~50 dispatches) | N/A | ≤ 5s | new measurement | §4.2 architecture |
| 4 | Multi-baseline byte test PASS count (regression guard) | 10 / 10 | 10 / 10 | 0 (preserved) | §4.6 coupling |
| 5 | LOC change in `src/devolaflow/compressor/layout.py` | 0 | 0 | 0 (G-6 enforcement) | §4.3 code quality |

NONE of these metrics rely on EvoBench `q` / `pass_rate` / `gap_score` (G-1 PASS).

## §6 — Admission Verdict

**PASS** for the audit script + report deliverable. The script provides DF-internal signal (per-field non-emptiness rates) that informs FUTURE schema evolution decisions, with zero schema mutation in v11.0.0.

**DEFER** any actual schema merge (NEST conversion of an APPENDED tail key) to a future cycle that:

1. Re-runs the multi-baseline byte test for ALL existing baselines (v7.0.0 → v10.2.0 → that cycle's new pin).
2. Authors a fresh ADR documenting the merge per A-2.3 decision matrix.
3. Adds a new `layout_invariant_v<NEW>.yaml` baseline pin.
4. Verifies `compute_dispatch_lcp_pct` ≥ 1.0 for the smaller payload (D2 append-only verification chain at `tests/test_layout_invariant_multi_baseline.py::TestMultiBaselineLCP`).

The audit-only verdict respects the source doc's explicit instruction (line 116) and the G-6 cache-prefix gate. No PDS in v11.0.0 should propose touching positions 1-12.

## §7 — Effort Estimate

**S** (≤ 0.5 PV) — confirms the source doc estimate. Breakdown:

* `scripts/audit_canonical_order.py` authoring: ~2 hours (script logic + argparse + walk loop + report renderer).
* `tests/test_audit_canonical_order.py` authoring: ~1.5 hours (6-8 test functions covering empty-handoff dir, single dispatch, multi-dispatch sampling, frozen-prefix protection at argparse-time).
* Run audit + emit `.local/research/v11.0.0_canonical_order_audit.md` and verify multi-baseline byte test still 10/10: ~30 min.

W-17 test budget consumption: +6-8 NEW test functions (well under +30 per-PV cap).

## §8 — Dependencies

**none** — standalone audit script. Does NOT depend on D-P-2 / D-P-3 / D-P-4 or any other PDS in this wave.

## §9 — Risk Register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | Audit produces a `nest_candidate` flag that operators interpret as "merge this immediately" rather than "consider in future cycle" | minor | Report header includes verbatim DEFER notice + link to A-2.3 decision matrix + cite `v9-ADR-002` D2 append-only contract; flags are advisory not actionable |
| 2 | Sampled handoff envelopes are not representative (most envelopes were authored in a single cycle so all carry similar field shapes) | minor | Report footer documents sample composition (count, date range, originating cycles); operator can re-run with `--since` filter for narrower window |
| 3 | Audit accidentally reads dispatch payloads that should be redacted (e.g., handoffs containing operator PII in `pred[*].key_facts`) | minor | Audit reads ONLY top-level key non-emptiness (boolean: present? non-empty?); never serialises field bodies in the report. Add explicit unit test for payload-content non-leakage |

ZERO blocker / major risks because the patch is read-only.

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: standard
