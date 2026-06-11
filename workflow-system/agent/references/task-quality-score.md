---
id: "agent/references/task-quality-score"
version: "1.0.0"
purpose: >
  L0-only post-workflow scoring rubric extracted from SKILL.md (v12.3.0
  PV-03) so the section bytes load only at workflow CLOSE, not during the
  per-dispatch execution loop. Closes feedback_for_v12.1.1.md #2 ("L0 的
  任务分析打分能力，可以拆解一个单独的 skill，在运行完成最后一个阶段后
  再进行加载，以优化上下文表现形式").
triggers:
  - "workflow end"
  - "final report"
  - "task quality score"
  - "L0 closing report"
tier: 3
token_estimate: 350
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-06-11"
---

# Task Quality Score (L0 ONLY)

**L0 ONLY** — Subagents MUST NOT score. This reference is loaded on-demand at workflow CLOSE (after the last stage gate PASSES and L0 is composing the final operator report). L1 / L2 / L3 dispatchers MUST NOT request this reference — the section is excluded from their context profiles per `workflow-system/agent/context_profiles.yaml#profiles.<L3-tier-profile>.task_quality_score = skip`.

## When to load

| Trigger | Action |
|---|---|
| Final stage gate PASSES (workflow about to close) | L0 loads this reference, computes the score, appends the §"Output format" block below to the operator-facing final report |
| Any L1/L2/L3 dispatch | DO NOT load — the per-dispatch profile sets `task_quality_score: skip` so the bytes never reach lower layers |
| SIMPLE / TRIVIAL single-task shortcut | OPTIONAL — score adds positive reinforcement but is not required when the task spec was 1 sentence |

## Why a separate reference (v12.3.0 PV-03 rationale)

Before v12.3.0 PV-03, the §"Task Quality Score" body lived in SKILL.md (~25 lines / ~120 tokens). It was consumed only at workflow CLOSE but loaded into every dispatch context that included SKILL.md. Per `.local/feedbacks/feedback_for_v12.1.1.md` #2:

> "可以拆解一个单独的 skill，在运行完成最后一个阶段后再进行加载，以优化上下文表现形式"

Extracting to this on-demand Tier 3 reference saves ~120 tokens × every dispatch that previously included the section, and reduces the probability that a `critical`-marked SKILL section gets evicted by the budget allocator at the L3 8K ceiling. The W-18 v12.1.0 D-1 literal pins (`L0 ONLY` + `Subagents MUST NOT`) remain in the SKILL.md stub so the substring-grep guarantee still holds.

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
* **Never score subagent outputs** — L1 / L2 / L3 StatusReport / WaveReport / StageReport carry NO `quality_score` field per the v12.1.0 D-1 closure + v12.2.0 PV-04 runtime hook `reject_subagent_quality_score`. This rubric scores ONLY the user's original request, never the dispatched agents' work.

## Cross-references

* `references/artifact-quality.md` — the OTHER rubric (v14.3.0): the L3-evidence rubric for the artifact itself. THIS file = L0-only scoring of the operator REQUEST; artifact-quality = the evidence the L3 emits about its DELIVERABLE (never a score, per v15-ADR-007).
* SKILL.md §"Task Quality Score (L0 ONLY)" — the stub that points HERE (collapsed in v12.3.0 PV-03)
* SKILL.md §"Version & Update" → "Session Banner Contract" — provides the version literal for the footer line
* `src/devolaflow/lifecycle/reject_subagent_quality_score.py` — v12.2.0 PV-04 runtime hook that flags top-level `quality_score` in dispatch payloads
* `workflow-system/agent/context_profiles.yaml#meta.task_quality_score_skip_layers` — declares which profile tiers MUST skip loading this section
* `.local/feedbacks/feedback_for_v12.1.1.md` — the feedback that motivated this extraction
* `.local/research/v12.3.0_gap_analysis.md` §2 D-2 — the closure decision
