# DevolaFlow v7.0 → v7.1 Iteration Retrospective (SI-8)

**Iteration:** v7.0.0 → v7.1.0 (4 sub-version slices + rollup)
**Date:** 2026-04-17
**Feature branch:** feat/v7.0-staged-context-compression
**Predecessor planning gate:** `.local/research/v7.0.0_context_compression_research.md`
**Design doc:** `.local/research/v7.0.0_staged_compression_design.md`
**Roadmap:** `.local/research/v7.0.0_version_roadmap.md`
**ADR set:** `.local/research/adr/v7-ADR-001-cache-layout-invariant.md` … `v7-ADR-005-learnings-v2.md`

## 1. Gaps identified (from SI-1 v7.0.0 planning gate)

The v7.0.0 planning gate (research report + 5 ADRs) enumerated seven gaps
between the v6.2.1 baseline and the target "staged context compression"
end state. Each gap was articulated verbatim in the research report and
decided via a dedicated ADR:

- **Cache instability across convergence rounds.** DevolaFlow produced
  a dispatch payload whose top-level section order could shift when
  `apply_round_escalation()` prepended a round-2 reinforcement block.
  Any downstream harness caching on the rendered prefix had to rebuild
  across rounds. Research §§A + B.6 + F row 1 + J.1; decided in
  `v7-ADR-001-cache-layout-invariant.md`.
- **Tool-output accumulation in multi-round dispatch.** Large `Read` /
  `Grep` / `Shell` payloads emitted as StatusReport tool_results
  accumulated verbatim into round-2+ predecessor context with no
  structured truncation primitive. Research §§B.3 + F row 6 + G row 6
  + J.2; decided in `v7-ADR-002-tool-output-truncation.md`.
- **Predecessor artifact bloat.** `pred[*].key_facts` extraction was
  produced ad hoc by the dispatching agent; on 5-10 KB artifacts
  agents paraphrased or softened error strings, producing the
  hallucination risk CO-2 was written to prevent. Research §§B.3 +
  F row 2 + G row 2 + J.3; decided in
  `v7-ADR-003-hierarchical-summary.md`.
- **No empirical measurement of cross-stage persistence.** The
  "评估方式" (evaluation methodology) ask from the original
  `.local/feedbacks/feedback_for_v6.3.x.md` pointed out we had zero
  end-to-end tests that an entity introduced in Stage A survived the
  L1 → L2 → L3 dispatch pipeline. Research §§H.4 + I + J.4; decided
  in `v7-ADR-004-persistence-probe.md`.
- **Learnings schema lacked decay / session scoping.** `learnings/
  operational.jsonl` was append-only with frozen confidence: a
  learning captured at 0.8 stayed 0.8 until `promote_learning()`
  bumped it or TTL expired. No mechanism for unused entries to
  decay, no way to pin a critical learning for a specific session.
  Research §§B.5 + F row 7 + G row 7 + J.5; decided in
  `v7-ADR-005-learnings-v2.md`.
- **Anthropic cookbook `[ref-6]` compaction primitives not yet
  ported.** The three first-party long-horizon primitives
  (compaction, tool-result clearing, memory) mapped 1:1 onto the
  cookbook's three classes of context growth, but DevolaFlow
  implemented sub-agent isolation only. The two remaining prompt-side
  levers (tool-result clearing and hierarchical summary as a
  compaction proxy) were gap items. Research §§B.2–B.3 + F rows 2 +
  6 + 7.
- **NineS golden set lacked compression scenarios.** The v6.1.1
  tool-config fix shipped 10 golden TOMLs under `data/golden_test_set/`
  but none exercised the compressor module; open question K.6 asked
  whether we could author 3-5 compression-specific golden tests in
  time for v7.0.0. Research §§H.3 + I + K.6.

## 2. What was implemented

| Wave | Version | Commit | Delivered |
|------|---------|--------|-----------|
| 1 | v7.0.0 | `dd0ef61` | **J.1 — Cache-Layout Invariant (ADR-001).** `devolaflow.compressor.assert_dispatch_layout()` + `DispatchLayoutError` + `DEFAULT_DISPATCH_LAYOUT` (12-key canonical order); `schemas/lean-dispatch.yaml#layout_invariant` block; workspace rule P6; H.2 LCP stability benchmark baseline (r1→r2=0.8487, r1→r3=0.8487, thresholds 0.80/0.70); +6 tests. The MAJOR bump signals the new governance constraint to ecosystem consumers. |
| 2 | v7.0.1 | `ef3a2d5` | **J.2 — Tool-Output Truncation Primitive (ADR-002).** `truncate_tool_output()` + `clear_old_tool_uses()` + `ToolUseTruncation` dataclass; `schemas/lean-report.yaml#tool_results` block (appended per P6 additive rule); 6 decomposition-enabled profiles gained `tool_output_truncation:` block (`enabled: false`); `sub_agent_context_budget` lifted 3000 → 5000 tokens (resolves K.8); +8 tests + 1 new EvoBench scenario (`compression_tool_output` composite 98.33). |
| 3 | v7.0.2 | `261070e` | **J.3 — Hierarchical Predecessor Summariser (ADR-003).** `summarise_predecessor()` (extractive-by-default, `key_facts:` verbatim prefix + schema-hint-prioritised sections, no paraphrase) + `extract_named_entities()` (8-class NER reusing `PRESERVE_PATTERNS` for the first six classes per CO-2); `meta.summary_trigger_pct: 25` (resolves K.1); nested per-pred `summary_mode` + `summary_max_tokens` schema fields (honours P6 — no new top-level keys); +10 unit tests + 3 EvoBench retention scenarios (easy 99.62 / medium 99.23 / hard 98.55) + 3 NineS goldens (closes 3/5 of K.6). |
| 4 | v7.0.3 | `0c3f2e2` | **J.4 + J.5 — Persistence Probe + Learnings v2 (ADR-004 + ADR-005).** `tests/test_e2e_compression.py` + `tests/_probe_fixtures.py` persistence probe with easy/medium/hard scenarios (5/20/50 entities), measuring `carry_through=1.0/1.0/1.0`; Learnings v2 adds 4 additive dataclass fields + 3 helpers (`consolidate_session`, `decay_confidence`, `pin_learning_for_session`) + `session_id` parameter on `load_relevant_learnings()`; `DECAY_FLOOR=0.1` + lazy migration shim (ADR-005 §2.4) keeps legacy v1 entries parsing unchanged; resolves K.5 (stay JSONL, no file-system memory tool); +32 tests. |
| rollup | v7.1.0 | (this) | **Adoption + SI-8 + SI-3.** Flips `tool_output_truncation.enabled: true` + `summary_mode: extractive` default across 6 decomposition profiles; ships the final 2 of 5 NineS goldens (`compression_tool_output.toml` + `compression_persistence.toml`, closing K.6); regenerates `benchmarks/devolaflow_context/baselines/v7.1.0_baseline.json`; authors this retrospective + SI-3 scorecard + cycle CHANGELOG entry. |

## 3. What was deferred and why

- **Semantic / abstractive summariser** (ADR-003 §4.3 option B). Deferred
  to v7.2 or later. The deterministic extractive pipeline met all three
  retention scenarios (easy / medium / hard at retention ≥ 95 % / ≥ 95 %
  / ≥ 90 %) and every persistence-probe tier (carry_through = 1.0
  across easy / medium / hard, 75/75 seeded entities); adding an
  LLM-based summariser would introduce non-determinism in the test
  path without a measurable gain at current corpus sizes (artifacts
  typically 1–15 K tokens). ADR-003 §2.3 keeps the hook in place
  (`mode: "abstractive"` is still a valid schema value) so a future
  iteration can flip it on behind a profile flag.
- **File-system-shaped memory tool** (Claude-style
  `view`/`create`/`str_replace`/`insert`/`delete`/`rename`). Deliberately
  rejected per K.5 (decided in ADR-005 §4a). JSONL + confidence decay
  + session pinning is sufficient at our current session scale, and a
  file-system API would duplicate functionality the `Read` / `Write`
  / `StrReplace` tools already provide against `operational.jsonl`.
  Revisit in v8.x only if learnings-consumption metrics show a
  workflow gain.
- **Plan-mode propagation into L2 Wave Agents.** v6.1.5 wired plan-mode
  detection into the L0 / L1 profile via `apply_plan_mode_overrides()`;
  v7.x keeps that scope. Research open question K.2 explicitly notes
  the L2 budget (4 K tokens) is the smallest in the hierarchy and may
  bloat if plan-mode escalations were propagated downward. Planned for
  v8.x once decomposition telemetry justifies the allocation.
- **v8.x outreach-protocol mission.** Research open question K.7 asked
  whether we should proactively negotiate prompt-cache telemetry with
  Cursor (and/or Anthropic) to replace the LCP proxy with real
  cache-hit metrics. For v7.x we stayed strictly inside the prompt
  side (research §D.5). Cross-tool caching negotiation is a v8-level
  concern — addressing it first would have blocked v7.0.0 on an open
  question we do not control.
- **Semantic auto-promotion of learnings.** Learnings v2 keeps
  `promote_learning()` and `consolidate_session()` as explicit,
  auditable operations. An auto-promote mode based on embedding
  similarity was considered (ADR-005 §4c) and rejected: it would
  introduce non-determinism into tests, require a model call per
  read, and duplicate `task_type` filtering that already works.
- **Two more reference adapters** (parity with the v6.1.3 Zed / Cline /
  Roo Code push). Out of scope for this cycle's compression theme.
  The data-driven adapter engine is stable (`DataDrivenAdapter` has
  shipped with zero edits since v6.0.4); adapter batches belong in a
  dedicated release. Tier-2 enterprise adapters (JetBrains, Amazon Q,
  Gemini, Augment, Trae) remain on the v6.3 / v7.2 backlog.

## 4. Key learnings

1. **Invariants first, primitives second.** Every v7 primitive that
   followed v7.0.0 landed cleanly because the cache-layout invariant
   (ADR-001 §2) had a defined position for every new field *before* it
   was written. The `tool_results` block (ADR-002) appended after
   `gate`; the `summary_mode` / `summary_max_tokens` fields (ADR-003)
   nested inside the existing `pred` entry instead of taking new
   top-level positions; the probe (ADR-004) consumed the canonical
   dispatch shape for its Stage B target; learnings v2 (ADR-005) was
   additive-by-construction because it never touched the dispatch
   surface at all. The v7.0.0 governance rule P6 converted a future
   rebase-hell failure mode ("why did three ADRs fight over position
   13?") into a one-line decision ("append after `gate`").

2. **Test-only primitives are cheap.** The persistence probe
   (ADR-004) shipped as 220 LOC of test code + 60 LOC of fixture
   helpers + a 50 LOC extension to `extract_named_entities` (reused
   from ADR-003). Production code was untouched. The probe
   immediately produced the `carry_through=1.0/1.0/1.0` measurement
   cited in research §H.4 as the gap indicator, turning "we have no
   end-to-end test" from a qualitative gap into a quantitative SLO
   with a value (`.local/research/v7.0.3_probe_telemetry.json`).
   Every dollar of test-only investment bought a new SI-3 dimension.

3. **Additive schemas beat breaking ones.** Learnings v2 (ADR-005)
   added 4 fields + 3 helpers to the `Learning` dataclass with zero
   legacy-entry migration required. The §2.4 shim pattern is worth
   stealing: legacy entries without `last_accessed` have the field
   lazily backfilled from `timestamp` on first `decay_confidence()`
   touch. No bulk migration script, no rewrite pass, no backwards-
   compat flag; the shim makes the migration invisible. Contrast
   this with v6.0.2's BREAKING deprecation removal, which required a
   separate MIGRATION-v6.md document and shipped as its own version.
   Additive wins on operator cost every time the semantics allow it.

4. **Deterministic beats heuristic at small corpus sizes.** ADR-003
   shipped an extractive summariser rather than an LLM-based one.
   The three retention SLOs (≥ 95 % / ≥ 95 % / ≥ 90 % on easy /
   medium / hard scenarios) and all three persistence-probe tiers
   passed without a single model call. The "abstractive" mode stays
   available as a profile opt-in (ADR-003 §2.3 keeps the schema
   field), but it never had to land to meet the acceptance criteria.
   Practitioners' warning from research §B.2 — "diagnose your
   bottleneck class first, then pick the matching primitive" —
   validated: the bottleneck was verbatim preservation, not
   narrative quality.

5. **Opt-in → default-on discipline.** Every primitive v7.0.1 through
   v7.0.3 shipped with `enabled: false`. The decision to flip
   `tool_output_truncation.enabled: true` and `summary_mode:
   extractive` (default) happened in v7.1.0 *after* three versions'
   worth of benchmark evidence said the primitives were safe. The
   SI-4 regression guard ran on every interim version; SKILL.md
   documentation landed alongside the primitives so opt-in
   discoverability was never the blocker. The discipline cost one
   extra release (v7.1.0) but bought zero rollback risk on the flip.

6. **NineS golden set doubled under a single theme.** The v6.1.1
   tool-config fix shipped 10 goldens under `data/golden_test_set/`;
   v7.x added 5 more (`compression_retention_easy/medium/hard.toml`
   in v7.0.2, `compression_tool_output.toml` +
   `compression_persistence.toml` in v7.1.0) — closing open question
   K.6. The `compression_persistence` golden explicitly encodes the
   carry-through SLO (research §H.4) as a NineS-scored artifact,
   turning the probe telemetry into a dimension NineS can track
   across future iterations.

7. **SF-1 budget discipline held across 5 versions.** SKILL.md
   entered v7.0.0 at 498 / 500 lines and exited v7.1.0 at 498 / 500
   lines. Every primitive added pointer-only cross-links inside the
   Context Isolation section; the documentation weight lived in
   `references/context-isolation.md` (loaded on-demand per the
   progressive-disclosure pattern research §B.5 recommends). The
   v7.0.2 addition ("Operational Learnings — Session Pinning &
   Decay") was placed *after* the last `context_profiles.yaml`
   line-range mapping, which preserved zero-drift benchmark results
   (lesson from v6.1.0 retrospective §4 #6: SKILL.md edits have
   benchmark-scoring side effects via line-range drift).

8. **Research → ADR → roadmap → commits held tight.** The v7 cycle
   produced four deliverable artifacts before a single commit landed:
   the research report (~1022 lines), the design doc (~1290 lines),
   the version roadmap, and the 5 ADRs. Each ADR pinned a decision
   (`keep=3`, `summary_trigger_pct=25 %`, `DECAY_FLOOR=0.1`,
   carry-through ≥ 90 %, LCP ≥ 80 % / 70 %) that went directly into
   a test assertion. Downstream waves never re-litigated a decision
   at implementation time, which is the single biggest reason the
   cycle shipped in four consecutive commits with zero revert.

## 5. Cross-version metrics (v6.2.1 → v7.1.0)

| Version | Tests | `compressor` cov | `learnings` cov | NineS overall | Goldens | SKILL.md | Notes |
|---------|------:|----------:|----------:|--------------:|--------:|---------:|-------|
| v6.2.1 | 1009 | 88 % | 92 % | 0.8805 | 10 | 498 | Baseline — tiktoken CI flake fixed |
| v7.0.0 | 1015 | ≥ 85 % | 92 % | 0.8805 | 10 | 500 | +6 layout tests + H.2 baseline (ADR-001) |
| v7.0.1 | 1023 | ≥ 88 % | 92 % | 0.8805 | 10 | 495 | +8 truncation tests + `compression_tool_output` scenario (ADR-002) |
| v7.0.2 | 1033 | ≥ 90 % | 92 % | 0.8805 | **13** | 495 | +10 summariser tests + 3 retention scenarios + 3 goldens (ADR-003) |
| v7.0.3 | **1090** | ≥ 90 % | **97.35 %** | 0.8805 | 13 | 498 | +32: probe + learnings v2 + coverage-floor class (ADR-004 + ADR-005) |
| v7.1.0 | 1100 | 94 % | 97 % | 0.8805 | **15** | 498 | +10 post-baseline verify + 2 final goldens; truncation + extractive default-on |

**Net deltas (v6.2.1 → v7.1.0):**

- Tests: 1009 → 1100 (**+91 net**, of which 19 landed in v7.0.3 as the
  probe + v2-schema coverage class).
- `devolaflow.compressor` coverage: 88 % → 94 % (+6 pp; CP-2 floor
  raised from 80 % to 90 % per roadmap §v7.0.2).
- `devolaflow.learnings` coverage: 92 % → 97.35 % (+5.35 pp; CP-2
  floor raised to 90 % per roadmap §v7.0.3).
- NineS overall: 0.8805 **stable** across all 5 versions (no
  regression — SI-4 guard held).
- Goldens: 10 → 15 (+5 compression-specific fixtures; closes K.6).
- Carry-through SLO: unmeasured → 1.0 / 1.0 / 1.0 (easy / medium /
  hard; 75/75 seeded entities preserved).
- Cache-layout LCP: unmeasured → 0.8487 (r1→r2) / 0.8487 (r1→r3),
  both above the committed 0.80 / 0.70 thresholds.
- SKILL.md: 498 / 500 lines stable (SF-1 cap honoured across every
  version).
- Default opt-ins at v7.1.0: `tool_output_truncation.enabled: true`
  on 6 decomposition-enabled profiles; `summary_mode: extractive`
  default on every profile that consumes predecessor artifacts.

## 6. Process notes

**What worked.** The cycle held its shape because we committed to the
research report → 5 ADRs → roadmap → 5 commits sequence before the
first line of production code landed. Every wave opened with a dispatch
that cited one ADR and one roadmap section; every wave closed with a
CHANGELOG entry that cross-referenced the same two pointers. Decisions
were resolved once (in the ADR) and never re-litigated at implementation
time. The `assert_dispatch_layout(payload)` runtime check (ADR-001) paid
for itself three times: v7.0.1's `tool_results` block appended after
`gate` cleanly because the validator would have raised otherwise; ADR-003
nested its new fields inside `pred` after the validator reported a
position-13 shortage; ADR-004 consumed the canonical shape without any
integration-test rewrite.

**What to change next cycle.** At the S01 → S02 hand-off of v7.0.0, the
baseline regenerator step was briefly forgotten — the cycle's S01 close
intended to write `benchmarks/devolaflow_context/baselines/v7.1.0_baseline.json`
and update the new-baseline test reference in `tests/test_benchmarks.py`
together, but the latter missed the first pass and was caught during
the v7.1.0 S03 rollup. Bake both operations into
`scripts/bump_version.py` so the step never gets missed again: when the
bump target is a cycle-closing version (`x.y.0` following `x.(y-1).*`),
the script should regenerate the baseline file, re-point
`V6_BASELINE_PATH` in `tests/test_benchmarks.py`, and run the regression
comparison in one operation. This folds the v7.0.1 retargeting pattern
(manually done across v7.0.1, v7.0.2, v7.0.3) into a single scripted
step. Separately: the v7.0.3 changelog ended up larger than necessary
because we documented every test in both `TestLearningsV2Schema` and
`TestLearningsV2Coverage` class by class. A future iteration should
draft the CHANGELOG from a shorter template that lists the class and
one-line per theme, then lets the commit message carry the full
enumeration.

## 7. Next iteration (feeds v7.2+ / v8.x SI-1 planning gate)

- **Semantic summariser A/B test.** Once repository-internal corpus
  sizes cross the 30 K-token per-artifact threshold (likely when the
  v8 design doc lands), A/B the abstractive mode (ADR-003 §2.3) against
  the extractive baseline using the existing H.1 retention scenarios.
  Trigger condition: probe tier "hard" drops below the 90 %
  retention SLO under the extractive path.
- **Plan-mode propagation into L2.** The v6.1.5 plan-mode detection
  still stops at L1. Open question K.2 stays open. Candidate design:
  a new `apply_context_modifiers(profile, *, plan_mode, round_num)`
  composer that fuses `apply_plan_mode_overrides()` and
  `apply_round_escalation()` and is called at every layer. Prerequisite:
  L2 Wave budget telemetry to confirm we have 1 K tokens of headroom.
- **Cross-tool caching negotiation (v8 theme).** Research open
  question K.7 stays prompt-side for v7.x by explicit decision. For
  v8.x, propose reaching out to Cursor / Anthropic for per-model
  cache-hit telemetry; the H.2 LCP metric becomes the canary we use
  to correlate our internal rendering stability against real cache
  behaviour.
- **Adaptive decay half-life based on task type.** Learnings v2 ships
  a single global `confidence_half_life_days = 30`. Empirically,
  `rdrr` and `research` learnings have shorter useful lives than
  `convention` or `adapter-registry` ones. Per-task-type half-life
  overrides would let us decay volatile operational lessons faster
  without dropping durable architectural decisions.
- **Compression telemetry dashboard in the web demo.** Surface
  `carry_through` + LCP + `was_bounded` + `cleared_count` as live
  KPIs in `workflow-system/human/demo/benchmark-results/index.html`,
  next to the existing EvoBench composite. Three visible SLOs with
  thresholds set by ADR-001 / ADR-003 / ADR-004 would let operators
  spot a compression regression at a glance without reading
  `v*.0_baseline.json`.
- **Semantic entity-match extension for the probe** (research §E.7 /
  `[ref-30]`). Today `compute_entity_carrythrough_rate` requires
  verbatim match. A graph-coverage variant (dependency edges between
  named entities) would catch the paraphrase class Karpathy flags as
  the next-largest fidelity gap, at the cost of a tree-sitter
  dependency. Evaluate for v7.2 once the probe corpus stabilises.
