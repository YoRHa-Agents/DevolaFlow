# v15-ADR-007 — L3 Artifact-Quality Evidence vs the "Subagents MUST NOT Score" Doctrine

* **Status**: PROPOSED (L0/human ratifies — REQUIRED BEFORE v14.3.0 starts; see gap analysis §4.2 #2)
* **Date**: 2026-06-12
* **Cycle**: v14.2.0 T5 (SI-1 planning gate for the v14.2.x → v15.0.0 ladder)
* **Feeds**: F-P1-2 (major), with F-P4-2/F-P4-6 as transport prerequisites and F-P4-3 as the
  doctrine-contradiction cleanup, per `.local/research/v15-cycle_design_review_product.md`
  §1.2/§4/§7 ADR-3; gaps G-004, G-002, G-003, G-013. Companion to v15-ADR-003 (enforcement locus).
* **3-condition gate** (verbatim from the product review §7): "Hard to reverse: report-schema
  fields + gates consuming them become contract. Surprising: partial inversion of the v12.1–12.3
  closure that stripped quality_score from subagent reports. Real trade-off: self-assessment
  bias vs L0 re-derivation cost; mitigable by scoring only evidence-backed dimensions (AC
  verdicts, test/cov, scope adherence) and keeping the holistic score L0-side." → **qualifies**.

## Context

For a framework whose north star is single-task deliverable excellence, no rubric anywhere in
the product scores the deliverable itself: `references/task-quality-score.md` §Scoring rules —
"**Never score subagent outputs** … This rubric scores ONLY the user's original request, never
the dispatched agents' work"; gate composite scores a STAGE from findings counts. Meanwhile the
doctrine has an internal contradiction (F-P4-3): `lean-report.yaml` ships
`lean_example.metrics: { …, quality: 92, … }` while SKILL.md line 371 says "Subagent reports DO
NOT include `quality_score` (L0-only…)" and the v12.2.0 PV-04 runtime hook
`reject_subagent_quality_score` checks only the top-level key — "the nested field sails
through". And the evidence that WOULD ground any artifact judgment has no transport (F-P4-2:
`plan_artifact`/`goal_anchor`/BG attestations have no report fields; F-P4-6: no per-AC verdicts,
no diff stats; `artifacts[].delta` capped at "≤15 words") — "excellence evidence dies at the L3
boundary".

The L0 ladder skeleton places "L3 artifact-quality rubric (25th reference, four-place SF-4
sync)" at v14.3.0; the product review maps F-P1-2 to v15.0.0 because of the doctrine inversion.
This ADR resolves the conflict by splitting EVIDENCE from SCORE.

## Decision (recommended)

**Two-phase: L3 emits evidence, never a score; L0 computes the score from evidence.**

1. **v14.2.x (precursor)**: resolve F-P4-3 — rename `metrics.quality` (e.g. `gate_input_score`)
   or drop it from `lean-report.yaml` spec + example, with an explicit "this is NOT Task
   Quality Score" note. One doctrine, taught once.
2. **v14.3.0 (evidence phase)** — all additive on the report side (lean-report.yaml has NO
   `layout_invariant:`, so low-risk per F-P4-2):
   * `self_check: {plan_artifact, goal_anchor, bg_attestations: [{id, verdict, evidence}]}` —
     gives BG-001/BG-004/BG-006/BG-007 their transport.
   * `ac_results: [{id, verdict, cmd_output_digest}]` + `diff_stats: {files, insertions,
     deletions}` — per-AC verdicts from running `acceptance_criteria_v2.verification_cmd`
     intra-task (F-P1-5's self-verify step), diff stats vs the "~50–300 lines changed" sizing
     contract.
   * NEW `workflow-system/agent/references/artifact-quality.md` (25th reference; four-place
     SF-4 sync per C-7: file + `_SF4_REFERENCE_SET` + SKILL Tier-2 row + `MIRRORED_FILES`):
     an L0-applied rubric whose dimensions are ONLY evidence-backed — AC verdict ratio,
     test/coverage delta, scope adherence (diff_stats vs owned_files), self-check completeness.
     Explicitly: verdicts and digests are attestations, **not** numbers L3 invents.
   * `reject_subagent_quality_score` hook unchanged and extended to reject any L3-emitted
     holistic score in the NEW blocks (doctrine stays enforced, now without the F-P4-3 leak).
3. **v15.0.0 (scoring phase)**: L0-side artifact score computed FROM the report evidence fields
   (gate consumes `ac_results`/`diff_stats`/`self_check`; feeds the feedback loop so
   "a task that passes with mediocre-but-acceptable output" finally generates signal per the
   product review §8 feedback-loops deduction). Holistic judgment stays L0-side permanently.

## Consequences

### Positive
* The v12.1–12.3 doctrine is preserved, not inverted: L3 self-assessment bias never enters a
  score — L3 supplies falsifiable evidence (command digests, verdicts, diff stats) that L0 can
  spot-check instead of re-deriving everything from disk.
* The product's scorecard axis "Task output verification 4/10" gains its missing mechanisms in
  dependency order (evidence v14.3.0 → scoring v15.0.0 — "each rung's evidence fields feed the
  next rung's mechanisms").

### Negative
* Report payloads grow (bounded: digests not transcripts; respects C-2 lean format — field
  shapes must specify caps like the existing "≤15 words" delta).
* SF-4 set 24 → 25 requires the four-place sync + count-pin updates (cheaper after G-028's
  derive-from-SSOT lands in v14.2.x).

### Neutral
* Dispatch-side schema untouched (canonical_order 17); only lean-report.yaml + a new reference.

## Alternatives considered

* **A1 — Let L3 self-score the artifact**: inverts the v12.1–12.3 closure; self-assessment bias
  plus the exact ambiguity F-P4-3 documents. Rejected.
* **A2 — No rubric at all (keep gate-composite only)**: stage-granularity scoring from findings
  counts never sees the artifact; north-star axis stays at 4/10. Rejected.
* **A3 — Rubric without report transport**: repeats the behavioral-guidelines failure mode —
  "unverifiable by construction" (F-P4-2). Rejected.
* **A4 — Single-phase landing at v15.0.0 (review's original slot)**: delays the evidence fields
  that v14.4.0's intra-task convergence and v15-ADR-003's `task_stop` handler both consume; the
  two-phase split is what makes the skeleton's dependency order work. Rejected.
