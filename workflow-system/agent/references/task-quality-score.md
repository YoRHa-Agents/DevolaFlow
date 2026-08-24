---
id: "agent/references/task-quality-score"
version: "1.0.0"
purpose: >
  L0-only post-workflow scoring rubric extracted from SKILL.md (v12.3.0
  PV-03) so the section bytes load only at checklist-runtime CLOSE, not during the
  per-dispatch execution loop. Closes feedback_for_v12.1.1.md #2 ("L0 的
  任务分析打分能力，可以拆解一个单独的 skill，在运行完成最后一个阶段后
  再进行加载，以优化上下文表现形式").
triggers:
  - "workflow end"
  - "final report"
  - "task quality score"
  - "L0 closing report"
tier: 3
token_estimate: 900
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-08-25"
---

# Task Quality Score (L0 ONLY)

**L0 ONLY** — Subagents MUST NOT score. This reference is loaded on-demand
after the checklist and archive/completion gate pass, while L0 composes the
final operator report. L1 Wave and L2 Task dispatches MUST NOT request this
reference; `context_profiles.yaml#meta.task_quality_score_skip_layers` keeps
the bytes out of lower-layer context.

## When to load

| Trigger | Action |
|---|---|
| Checklist complete and archive/completion gate passes | L0 loads this reference, computes the score, and appends the §"Output format" block to the operator-facing final report |
| Any L1/L2 dispatch | DO NOT load — the per-dispatch profile sets `task_quality_score: skip` so the bytes never reach lower layers |
| SIMPLE / TRIVIAL single-task shortcut | OPTIONAL — score adds positive reinforcement but is not required when the task spec was 1 sentence |

## Why a separate reference (v12.3.0 PV-03 rationale)

Before v12.3.0 PV-03, the §"Task Quality Score" body lived in SKILL.md (~25 lines / ~120 tokens). It was consumed only at workflow CLOSE but loaded into every dispatch context that included SKILL.md. Per `.local/feedbacks/feedback_for_v12.1.1.md` #2:

> "可以拆解一个单独的 skill，在运行完成最后一个阶段后再进行加载，以优化上下文表现形式"

Extracting to this on-demand Tier 3 reference saves ~120 tokens × every
dispatch that previously included the section and protects the L2 Task 8K
context ceiling. The W-18 v12.1.0 D-1 literal pins (`L0 ONLY` +
`Subagents MUST NOT`) remain in the SKILL.md stub.

## Dimensions (score each 1-5)

L0 evaluates the user's original request along 4 dimensions. Each scored independently 1 (Poor) → 5 (Excellent).

| Dimension | 1 (Poor) | 3 (Adequate) | 5 (Excellent) |
|-----------|----------|--------------|---------------|
| **Clarity** | Vague, ambiguous intent — multiple plausible interpretations | Understandable but imprecise — a couple of interpretations remain | Unambiguous, single interpretation; no clarifying questions needed |
| **Scope** | No boundaries stated — "make this better" / "do everything" | Partial boundaries — some files / phases named, others left open | Clear in/out of scope; explicit file / phase enumeration; defer list present |
| **Success Criteria** | No criteria given — outcome is implicit | Implicit criteria inferable from context | Explicit, testable criteria; pass / fail thresholds; observable behaviour |
| **Context** | No background or constraints | Some context provided — stack named, key constraints mentioned | Full context: stack, prior art links, constraints, performance / compat hints, related cycle archives |

## Output format

L0 appends this block to the final operator-facing report (chat output, NOT dispatch payload). Per v12.3.0 PV-02 Session Banner Contract, the footer line MUST include the literal version string `DevolaFlow vX.Y.Z` so the score artifact is self-describing when extracted from the chat log.

```
📊 Task Quality Score: [total]/20
  Clarity:          [n]/5 — [one-line tip if < 4]
  Scope:            [n]/5 — [one-line tip if < 4]
  Success Criteria: [n]/5 — [one-line tip if < 4]
  Context:          [n]/5 — [one-line tip if < 4]
💡 Tip: [single most impactful improvement suggestion]
🌸 DevolaFlow v12.3.0 · scored at workflow close
```

The trailing footer line ties the score artifact to the orchestrator version per v12.3.0 PV-02 (`.local/feedbacks/feedback_for_v12.1.1.md` #1 closure).

## Scoring rules

* **Always score** — positive reinforcement matters; even 5/5 is meaningful operator feedback that the task spec was well-formed.
* **Keep tips actionable and specific** — `Clarity 3/5 — name the target service` beats `Clarity 3/5 — be clearer`.
* **One tip max per dimension below 4/5** — the goal is a tight signal, not a critique.
* **Do not let scoring delay the workflow** — the score appends to the final report; if scoring takes > 30 seconds, ship the report and skip the tip section.
* **Never score subagent outputs** — L2 StatusReport and L1 WaveReport carry
  no `quality_score` field per the v12.1.0 D-1 closure and the
  `reject_subagent_quality_score` hook. This rubric scores only the user's
  original request.

## Artifact Score (L0-side, v15.0.0+)

The SECOND L0-only score — same doctrine, opposite axis. THIS rubric scores
the operator's REQUEST; the artifact score grades the L2 DELIVERABLE,
computed by L0 from Task evidence. L2 never authors it.

* **When L0 computes it**: round adjudication or workflow close — after L2
  StatusReports carrying `self_check`, `ac_results`, and `diff_stats` have
  been aggregated by L1. Never load this rubric during an L1/L2 dispatch.
* **From what evidence**: `src/devolaflow/gate/artifact_score.py::score_artifact_evidence(report)` consumes a lean StatusReport dict and scores the four `references/artifact-quality.md` §2 dimensions — Correctness (`ac_results` verdict ratios; pass = 100 basis, fail weighted by count, skip-tier verdicts discounted at half credit), Minimal diff (`diff_stats` proportionality vs the dispatch's owned-files count and the ~300-line / 6-file sizing contract), Test evidence (`metrics` pass/fail ratio + coverage vs the 80% S-3 floor, no bonus above the floor), Convention adherence (`self_check` completeness: plan_artifact / goal_anchor / simplicity declared / conflicts+conventions surfaced).
* **Unscored renormalization (never fabricate)**: a dimension whose evidence block is absent is `unscored` — EXCLUDED from the composite, with the remaining dimension weights renormalized. `ArtifactScore.evidence_coverage` (fraction of dimensions scored) is the honesty signal: a 100 composite at 0.25 coverage means ONE dimension had evidence, not that the artifact is excellent. No evidence at all → composite `None`, never a default number.
* **Gate adapter**: `ArtifactScore.to_gate_input()` renders the
  `{dimensions, weights}` shape `devolaflow.gate.scorer.composite_score`
  consumes. L0 may use it as trend or archive-readiness input; item evidence,
  not a score, decides round PASS.
* **Doctrine guard**: a report that smuggles a `quality_score` / `quality` field (top level or inside the `metrics` / `self_check` blocks) raises `EvidenceDoctrineError` — coherent with the strict `reject_subagent_quality_score` hook (v15.0.0 G-038). `metrics.gate_input_score` and predecessor-carried historical scores stay exempt.

### Request score vs artifact score

| | Task Quality Score (this rubric) | Artifact Score (v15.0.0) |
|---|---|---|
| Scores | The operator's ORIGINAL REQUEST | The L2 DELIVERABLE |
| Computed by | L0, manually per §Dimensions above | L0, mechanically via `gate/artifact_score.py` |
| Input | Request text + session context | `ac_results` / `diff_stats` / `metrics` / `self_check` evidence blocks |
| Scale | 4 × 1–5 (total /20) | 4 × 0–100 per dimension + weighted composite (unscored-renormalized) |
| Output surface | Final operator report (chat) | `ArtifactScore` dataclass → `to_gate_input()` |
| Never | Scores subagent outputs | Accepts an L2-authored score (`EvidenceDoctrineError`) |

## Cross-references

* `references/artifact-quality.md` — the OTHER rubric: L2 evidence for the
  artifact itself. THIS file is L0-only scoring of the operator request;
  artifact-quality is evidence the L2 Task emits about its deliverable.
* `src/devolaflow/gate/artifact_score.py` — the v15.0.0 L0-side scorer that turns those evidence blocks into the §"Artifact Score" composite (`score_artifact_evidence` / `ArtifactScore.to_gate_input`).
* SKILL.md §"Task Quality Score (L0 ONLY)" — the stub that points HERE (collapsed in v12.3.0 PV-03)
* SKILL.md §"Version & Update" → "Session Banner Contract" — provides the version literal for the footer line
* `src/devolaflow/lifecycle/reject_subagent_quality_score.py` — v12.2.0 PV-04 runtime hook that flags top-level `quality_score` in dispatch payloads
* `workflow-system/agent/context_profiles.yaml#meta.task_quality_score_skip_layers` — declares which profile tiers MUST skip loading this section
* `.local/feedbacks/feedback_for_v12.1.1.md` — the feedback that motivated this extraction
* `docs/cycle-archive/v12.3.0/v12.3.0_gap_analysis.md` §2 D-2 — the closure decision
