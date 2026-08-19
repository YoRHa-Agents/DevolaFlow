# T02 — Caveman Compression Strategy Audit

**Task**: T02-research — Audit the effectiveness of DevolaFlow's caveman-inspired compression strategy across different layer interactions.

**Version audited**: v3.9.2  
**Date**: 2026-04-12  
**Baseline reference**: v3.2.0 round 13 (latest stored), v2.1.0 (original baseline)

---

## Executive Summary

DevolaFlow's caveman-inspired compression strategy is **effective at the schema level but largely untested at the runtime enforcement level**. The lean dispatch/report schemas deliver a documented 45–55% token reduction over verbose originals, and the EvoBench benchmark suite confirms 99.2–99.98 composite scores across all 20 scenarios. However, these scores measure *context selection* quality (which sections the selector picks), not *message compression* quality (whether actual inter-layer messages are compacted per the drop/preserve rules). The compression_rules in the schemas are declarative specifications that lack a runtime enforcement mechanism — no code currently validates that a TaskDispatch or StatusReport produced by a dispatcher actually conforms to the lean format or applies the drop_list.

**Verdict**: Schema design is strong. Runtime enforcement is the critical gap. The gap between specification and implementation means compression effectiveness is dependent on LLM compliance rather than deterministic enforcement.

---

## 1. Per-Schema Analysis

### 1.1 lean-dispatch.yaml (TaskDispatch Compression)

**Token reduction**: Original example ~350–500 tokens → Lean example ~160–220 tokens (45–55% reduction)

| Field | Original | Lean | Compression technique |
|-------|----------|------|----------------------|
| header | 5 keys, full names | `hdr` with 4 abbreviated keys | Key abbreviation |
| task.description | Multi-sentence prose | `goal` (single sentence, ≤40 tokens) | Prose→constraint summary |
| predecessor_artifacts | 2 entries × multi-sentence summary | `pred` with `key_facts` lists (≤8 words each) | Summarization→verbatim extraction |
| owned_files | 3 paths with labels | `files` (bare path list) | Label stripping |
| acceptance.criteria | 7 prose sentences | 6 terse entries (≤15 words, → notation) | Prose→cause-effect shorthand |
| quality_thresholds | 4 key-value pairs + prose | `gate` (numeric-only, 4 keys) | Prose elimination |

**Preserve list** (8 items):
- `file_paths` ✓ — Critical, avoids hallucinated paths
- `error_messages_verbatim` ✓ — Critical per LLM Scaling Paradox
- `metric_values` ✓ — Numeric precision matters
- `commit_hashes` ✓ — Referential integrity
- `acceptance_criteria` ✓ — Contract enforcement
- `task_ids` ✓ — Routing/correlation
- `artifact_references` ✓ — Predecessor traceability
- `version_strings` ✓ — Consistency verification

**Drop list** (6 items):
- `filler_phrases` ✓ — Zero information loss
- `hedging_language` ✓ — Removes ambiguity from instructions
- `pleasantries` ✓ — Zero information loss
- `redundant_narration` ✓ — Self-documenting format replaces narration
- `meta_commentary` ⚠️ — Only dropped at aggressive tier; reasonable
- `apologies` ✓ — Zero information loss

**Assessment**: Preserve list is comprehensive. No critical items are missing. Drop list is conservative and safe.

### 1.2 lean-report.yaml (StatusReport Compression)

**Token reduction**: Original example ~400–600 tokens → Lean example ~150–250 tokens (45–55% reduction)

The report schema adds two items beyond the dispatch preserve list:
- `finding_ids` — Traceability for review findings
- `delta_descriptions` — Preserves what-changed summaries

**Additional compaction rules** (6 rules):
1. Never paraphrase paths/errors/metrics/hashes — matches CO-2
2. Use `→` for cause/effect — concise notation
3. Abbreviate severity keys (B/C/M/m/i) — saves ~15 tokens per findings block
4. Omit zero-value optional fields — conditional compression
5. Structured entries, not prose — format enforcement
6. Delta must name concrete change, not describe purpose — action-oriented

**Result Status Protocol**: The typed enum (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED) adds deterministic routing, avoiding free-form state interpretation. This is a compression gain: 1 enum value replaces ~10–20 tokens of explanatory status text.

**Assessment**: Report schema is well-structured. The additional compaction rules are practical and the severity abbreviation scheme is clever. The delta_descriptions preserve item is important for upward aggregation.

### 1.3 Preserve/Drop Rule Recommendations

**Items that should be added to preserve_list**:
| Item | Rationale |
|------|-----------|
| `environment_identifiers` | Env names (staging/prod) should never be paraphrased — misrouting risk |
| `dependency_versions` | Package versions in error context need verbatim preservation |
| `line_numbers` | Stack trace line numbers are critical for debugging accuracy |
| `timing_values` | Elapsed seconds, latency measurements should be preserved verbatim |

**Items that could be added to drop_list**:
| Item | Rationale | Suggested tier |
|------|-----------|----------------|
| `progress_narration` | "Making good progress on..." — zero signal | standard |
| `obvious_acknowledgments` | "Understood", "Got it", "Will do" | minimal |
| `tool_call_echoing` | Restating what tool was called — already in logs | aggressive |

---

## 2. Intensity Tier Analysis

### 2.1 Tier comparison

| Tier | Active drops | Use case | Token savings (est.) |
|------|-------------|----------|---------------------|
| **minimal** | filler, pleasantries, apologies (3/6) | L2→L3 dispatch (clarity-critical) | 5–10% |
| **standard** | + hedging, redundant_narration (5/6) | Default for all boundaries | 10–20% |
| **aggressive** | + meta_commentary (6/6) | L3→L2 upward reports, batch aggregation | 15–25% |

### 2.2 Tier appropriateness evaluation

**Standard as default** — **Appropriate**. The standard tier drops hedging and redundant narration, which are the highest-volume low-signal categories in LLM output. This is safe because:
- Inter-layer messages are structured YAML, not conversational text
- The lean format itself prevents most hedging by design
- Narration is redundant when fields are self-documenting

**When to use aggressive**:
- L3→L2→L1→L0 upward report aggregation (Wave/Stage combining multiple task reports)
- Batch status dashboards (human-facing summaries can strip meta-commentary)
- Context window pressure scenarios (approaching the 8K hard cap)

**When to use minimal**:
- L2→L3 dispatch to L3 Task Agents (maximum clarity for execution)
- Security-sensitive dispatches (auto-clarity escape hatch applies)
- First-time task types without established patterns

### 2.3 Gap: Tier selection is static

The default_intensity is set globally to `standard`. There is no mechanism to select tier per-layer-boundary or per-task-type. The context_profiles.yaml defines section priorities per task type, but does not set compression intensity. This is a missed opportunity for adaptive compression.

---

## 3. Per-Layer Boundary Analysis

### 3.1 L0→L1 (Project→Stage dispatch)

| Dimension | Assessment | Rating |
|-----------|-----------|--------|
| What's compressed | Stage definition, predecessor summaries, workflow template | |
| Token budget | ~3K tokens (Rule 2) | |
| Lean format applicable? | Partially — L0 sends stage definitions, not full TaskDispatch | |
| Compression effectiveness | **Partially effective** | ⚠️ |

**Rationale**: L0→L1 communication is mostly workflow template + status, not a structured TaskDispatch. The lean-dispatch format is designed for task-level dispatch (L2→L3), not stage-level orchestration. The compression_rules apply if L0 generates dispatch messages, but the primary compression at this boundary is section selection via context profiles.

### 3.2 L1→L2 (Stage→Wave dispatch)

| Dimension | Assessment | Rating |
|-----------|-----------|--------|
| What's compressed | Wave task list, coordination mode, predecessor artifact summaries | |
| Token budget | ~4K tokens (Rule 2) | |
| Lean format applicable? | Yes — wave dispatch is structured | |
| Compression effectiveness | **Effective** | ✓ |

**Rationale**: Stage→Wave dispatch benefits directly from the lean format. The `pred` field with `key_facts` lists replaces verbose artifact summaries. The `accept` field with ≤15-word criteria replaces prose AC. Coordination mode (parallel/sequential/pipeline) is already terse.

### 3.3 L2→L3 (Wave→Task dispatch) — Most critical

| Dimension | Assessment | Rating |
|-----------|-----------|--------|
| What's compressed | Task spec, predecessor context, owned files, rules, acceptance criteria | |
| Token budget | ~8K tokens (Rule 2) | |
| Lean format applicable? | Yes — this is the primary design target | |
| Compression effectiveness | **Effective** | ✓ |

**Rationale**: This is the boundary the lean-dispatch schema was designed for. The example in the schema is literally a Wave→Task dispatch. The 45–55% reduction means a task spec that would be ~500 tokens verbose fits in ~250 tokens lean, leaving more budget for actual file content and rules.

**Risk**: L3 needs maximum clarity for execution. The `minimal` intensity tier should be the default for this boundary, not `standard`. Dropping hedging from dispatch to a task agent is fine, but dropping narration could remove helpful context about *why* a task exists.

### 3.4 L3→L2 (Task→Wave report)

| Dimension | Assessment | Rating |
|-----------|-----------|--------|
| What's compressed | Task result, artifacts, metrics, issues, decisions | |
| Token budget | Report absorbed into Wave's ~4K context | |
| Lean format applicable? | Yes — lean-report is the primary design target | |
| Compression effectiveness | **Effective** | ✓ |

**Rationale**: Task reports are the highest-volume message type. A task producing 3 artifacts with metrics and findings compresses from ~500 tokens to ~200 tokens. The severity abbreviation (B/C/M/m/i) and delta-based artifact descriptions are particularly effective.

### 3.5 L2→L1 (Wave→Stage report)

| Dimension | Assessment | Rating |
|-----------|-----------|--------|
| What's compressed | Aggregated wave results (multiple task reports) | |
| Token budget | Report into Stage's ~5K context | |
| Lean format applicable? | Yes, with aggregation compression | |
| Compression effectiveness | **Partially effective** | ⚠️ |

**Rationale**: Wave→Stage reports aggregate multiple task results. The lean format handles individual task compression well, but there's no defined aggregation compression strategy. When a wave completes 5 tasks, the wave report should compress 5 task reports into a single summary. The current schema doesn't define an aggregation format — it only defines per-task report format.

**Gap**: Need a `wave_summary` section in the lean-report schema that defines how to aggregate multiple task deltas into a wave-level delta.

### 3.6 L1→L0 (Stage→Project report)

| Dimension | Assessment | Rating |
|-----------|-----------|--------|
| What's compressed | Stage results, wave summaries, gate verdicts | |
| Token budget | Report into Project's ~3K context | |
| Lean format applicable? | Partially — needs stage-level aggregation | |
| Compression effectiveness | **Partially effective** | ⚠️ |

**Rationale**: Same aggregation gap as L2→L1. Stage→Project compression must summarize potentially dozens of tasks across multiple waves. The lean format's per-entry structure scales, but without explicit aggregation rules, each layer must improvise its compression strategy.

### Summary: Per-Layer Effectiveness Ratings

| Boundary | Direction | Effectiveness | Primary mechanism |
|----------|-----------|---------------|-------------------|
| L0→L1 | Project→Stage | Partially effective | Section selection (not lean format) |
| L1→L2 | Stage→Wave | Effective | Lean dispatch format |
| L2→L3 | Wave→Task | Effective | Lean dispatch format (primary target) |
| L3→L2 | Task→Wave | Effective | Lean report format (primary target) |
| L2→L1 | Wave→Stage | Partially effective | Lean report + no aggregation rules |
| L1→L0 | Stage→Project | Partially effective | Lean report + no aggregation rules |

---

## 4. Context Profiles Interaction

### 4.1 Section selection as implicit compression

The `context_profiles.yaml` with 15 task-type profiles and `task_adaptive_selector.py` implements a powerful implicit compression layer:

1. **Priority-based budget allocation** (critical→important→supplementary→skip) is itself a compression mechanism: irrelevant sections are never loaded, saving 100% of their tokens.

2. **Token budget enforcement** — Each profile has a hard budget (2375–5200 tokens). The selector fills critical first, then important, then supplementary until budget exhaustion. This is *prevention-based compression* (Morph Methods pattern): don't include noise rather than trying to compress it later.

3. **Task-type specialization** — A hotfix agent skips `stage_primitives`, `convergence_loop`, `reference_navigation` (all skip-priority). A feature agent includes them as critical. This is the highest-ROI compression: section-level filtering eliminates 30–60% of SKILL.md content before any message-level compression even applies.

### 4.2 Interaction with lean dispatch

The two compression layers are **complementary and non-overlapping**:

| Layer | What it compresses | When it acts |
|-------|-------------------|-------------|
| Context profiles | Which SKILL.md sections L3 receives | Dispatch construction (L2 builds dispatch) |
| Lean format | How dispatch/report messages are structured | Message serialization |
| Compression rules | What text patterns are stripped from messages | Message post-processing |

The lean format compresses the *vehicle* (dispatch/report structure). Context profiles compress the *payload* (which content is included). Together they achieve multiplicative compression: a feature dispatch with 10 critical sections in lean format uses ~4800 tokens vs. a naive "full SKILL.md + verbose dispatch" that would use ~8000+ tokens.

### 4.3 Budget utilization from EvoBench

Live v3.9.2 benchmark results show tight budget utilization across all 20 scenarios:

| Profile | Budget | Used | Utilization | Waste |
|---------|--------|------|-------------|-------|
| hotfix | 2400 | 2399 | 99.96% | 1 tok |
| feature | 4800 | 4797 | 99.94% | 3 tok |
| research | 3300 | 3260 | 98.79% | 40 tok |
| refactor | 4800 | 4741 | 98.77% | 59 tok |
| review | 3850 | 3775 | 98.05% | 75 tok |
| design | 4450 | 4377 | 98.36% | 73 tok |
| security-audit | 5200 | 5115 | 98.37% | 85 tok |
| migration | 4800 | 4741 | 98.77% | 59 tok |
| feedback | 2375 | 2343 | 98.65% | 32 tok |
| self_update | 3125 | 3082 | 98.62% | 43 tok |
| spike-poc | 2975 | 2917 | 98.05% | 58 tok |
| documentation | 3400 | 3337 | 98.15% | 63 tok |
| rdrr | 4650 | 4599 | 98.90% | 51 tok |
| demo-showcase | 4450 | 4377 | 98.36% | 73 tok |
| perf-optimization | 4950 | 4872 | 98.42% | 78 tok |
| dependency-setup | 3000 | 2989 | 99.63% | 11 tok |
| onboarding | 3700 | 3635 | 98.24% | 65 tok |
| skill-optimization | 4200 | 4149 | 98.79% | 51 tok |

**Mean utilization**: 98.78%. This indicates budgets are well-calibrated — tight enough to be efficient, with <100 tokens slack in all cases. The hotfix and feature profiles achieve near-perfect 99.9%+ utilization.

---

## 5. EvoBench Metrics Interpretation

### 5.1 Current v3.9.2 scores

| Metric | Range | Mean | Interpretation |
|--------|-------|------|----------------|
| composite | 99.22–99.98 | 99.52 | Near-ceiling performance |
| section_relevance | 1.0 (all scenarios) | 1.0 | All expected sections always included |
| noise_ratio | 0.0 (all scenarios) | 0.0 | No unwanted sections ever selected |
| information_density | 0.9805–0.9996 | 0.9896 | High relevant-token density |
| budget_utilization | 0.9805–0.9996 | 0.9878 | Tight budget usage |

### 5.2 What 99.2–99.98 composite actually means

The composite formula is: `relevance × 40 + density × 30 + (1 - noise) × 20 + utilization × 10`

With relevance=1.0 and noise=0.0 across all scenarios, the composite is dominated by:
- 40 points from perfect section selection
- 20 points from zero noise
- 30 × density + 10 × utilization (varies by budget tightness)

**This means**: The context selection mechanism is **saturated** — it cannot meaningfully improve further within its current evaluation dimensions. Every expected section is selected, no unwanted sections leak through, and budgets are >98% utilized.

### 5.3 Historical improvement trajectory

| Version | Scenarios | Mean composite | Key change |
|---------|-----------|---------------|------------|
| v2.1.0 | 3 | 78.03 | Original baseline (3 scenarios only) |
| v3.2.0 round 0 | 17 | ~95–97 | Initial 14-profile system |
| v3.2.0 round 13 | 17 | 99.47–99.86 | 13 optimization rounds |
| v3.9.2 (live) | 20 | 99.22–99.98 | 20 scenarios, 15 profiles |

The jump from v2.1.0 (78.0) to v3.2.0 round 13 (99.5+) was driven by:
1. Budget tightening (v2.1.0 had 6500-token feature budget → v3.2.0 reduced to 4700–4800)
2. Profile proliferation (3 → 17 → 20 scenarios covering 15 profiles)
3. Section priority refinement (13 optimization rounds)

### 5.4 Saturation implications

At 99.5+ composite, EvoBench is no longer a discriminating measure for context selection quality. Improvements from here require:
1. **New evaluation dimensions** (e.g., measuring whether lean format is *actually used* in generated messages)
2. **Runtime compression metrics** (token count before/after applying compression_rules to real LLM output)
3. **Task success correlation** (does lean-formatted dispatch lead to higher L3 task completion rates?)

---

## 6. Gap Analysis vs. Full Caveman Pattern

### 6.1 Feature mapping

| Caveman feature | DevolaFlow implementation | Gap status |
|----------------|--------------------------|------------|
| **Deterministic drop/preserve lists** | `compression_rules` in both schemas | ✅ Fully mapped |
| **Intensity levels** (lite/full/ultra) | Mapped to minimal/standard/aggressive | ✅ Fully mapped |
| **File-type detection** (natural_language/code/config) | Section-type metadata (`content_type` in context_profiles) | ⚠️ Partial — no runtime detection |
| **Validate-then-fix loop** | Gate mechanism (quality gate scoring) | ⚠️ Different mechanism, same intent |
| **Auto-clarity escape hatch** (security/irreversible) | Not implemented | ❌ Missing |
| **Compression benchmarks** (benchmarks/run.py) | EvoBench suite | ✅ Implemented (but measures selection, not compression) |

### 6.2 Detailed gap analysis

**Gap H2 (from reference-dependencies.yaml): Validate-then-fix for inter-agent messages**

Caveman's core loop: compress → validate → cherry-pick fix (max 2 retries). DevolaFlow's gate mechanism validates task *output* quality, but does not validate *message* quality. There is no mechanism that:
1. Checks if a generated dispatch message conforms to lean format
2. Identifies which fields violated the format
3. Selectively fixes those fields (cherry-pick fix)
4. Retries with targeted instructions (max 2 retries)

**Gap: File-type detection → Content-type routing**

Caveman detects whether input is natural_language, code, or config and applies different compression strategies. DevolaFlow's `content_type` field in context_profiles (metadata, prose, table, spec, formula, constraints, navigation, rules) is richer but only used for *selection priority*, not for *compression strategy selection*. A `prose` section could be compressed more aggressively than a `formula` section, but this distinction isn't leveraged.

**Gap: Auto-clarity escape hatch**

Caveman has an explicit escape hatch: "when in doubt, don't compress" for security/irreversible actions. DevolaFlow's `minimal` intensity tier partially addresses this, but there's no automatic trigger. The security-audit profile doesn't set a different compression intensity — it uses the global `standard` default.

**Gap: Runtime enforcement**

The most critical gap. Caveman's compression is *applied* to text at runtime. DevolaFlow's compression_rules are *documented specifications* that LLM agents are expected to follow. There is no `compress()` function that takes a verbose dispatch and returns a lean dispatch. The "compression" happens implicitly when the dispatcher LLM follows the lean format template.

---

## 7. Recommendations for v4.0.0

### 7.1 High priority

1. **Implement runtime compression validator**
   - Create `src/devolaflow/compressor.py` with `validate_lean_format(message, schema_type)` and `compress_message(message, intensity)`
   - The validator checks preserve_list items are present and drop_list items are absent
   - The compressor applies deterministic text transformations (strip filler phrases, abbreviate severity keys)
   - This closes Gap H2 and makes compression enforcement deterministic

2. **Add per-boundary intensity configuration**
   - Extend `context_profiles.yaml` to include `compression_intensity` per profile
   - Default: `standard` for most, `minimal` for L2→L3 dispatch, `aggressive` for upward aggregation reports
   - Security-audit and migration profiles should default to `minimal`

3. **Define aggregation compression format**
   - Add `wave_summary` and `stage_summary` sections to lean-report.yaml
   - Define how N task reports compress into a single wave-level summary
   - Example: 5 task deltas → 1 wave delta with merged metrics and combined artifact list

### 7.2 Medium priority

4. **Add compression effectiveness metrics to EvoBench**
   - New dimension: `format_compliance` — does the generated message match lean format?
   - New dimension: `compression_ratio` — token count of lean vs. verbose equivalent
   - New dimension: `information_preservation` — are all preserve_list items intact?
   - This addresses the saturation problem (99.5+ composite with no room to improve)

5. **Content-type-aware compression**
   - Leverage existing `content_type` metadata to select compression strategy per section
   - `prose` → aggressive compression (more filler to strip)
   - `table`/`formula` → minimal compression (structured data, low noise)
   - `spec` → standard compression

6. **Auto-clarity escape hatch implementation**
   - When task_type matches security-related hints, automatically downgrade to `minimal` intensity
   - When dispatch contains `irreversible_action: true` flag, force `minimal`
   - Log compression decisions for audit trail

### 7.3 Low priority

7. **Adaptive intensity selection**
   - Monitor actual token savings per intensity tier across real executions
   - If standard and aggressive produce similar savings for a profile, consolidate to standard
   - Track which drop_list items are most frequently triggered

8. **Predecessor summary compression pipeline**
   - Implement the ruflo-inspired intent-based filtering for predecessor artifacts
   - Extract only task-relevant facts from predecessor outputs (not full summaries)
   - This could reduce predecessor context by 30–50% beyond current key_facts approach

### 7.4 Specific metrics to track for v4.0.0

| Metric | Target | Measurement method |
|--------|--------|-------------------|
| **format_compliance_rate** | >95% of dispatches match lean format | Validator on generated messages |
| **compression_ratio** | >40% reduction from verbose to lean | Token count comparison |
| **preserve_list_integrity** | 100% of preserve items present in lean output | Automated check |
| **drop_list_effectiveness** | >80% of drop items absent from lean output | Pattern scanning |
| **aggregation_compression** | >60% reduction in wave-level summaries | Wave report token comparison |
| **per_boundary_intensity** | Configured for all 6 boundaries | Config audit |
| **task_completion_correlation** | Lean dispatch → no decrease in L3 success rate | A/B comparison |
| **evobench_format_compliance** | New dimension scores >90 | New evaluator dimension |

---

## 8. Conclusion

DevolaFlow's caveman-inspired compression is architecturally sound but implementation-incomplete. The schema-level design (lean-dispatch.yaml, lean-report.yaml) with deterministic preserve/drop lists and intensity tiers demonstrates a well-thought-out approach. The context profiles system provides excellent implicit compression through section selection (99.5+ EvoBench composite, 0% noise ratio, 100% section relevance).

The critical gap is the absence of runtime enforcement. The compression strategy is a specification that relies on LLM compliance rather than a deterministic transformation applied to generated messages. For v4.0.0, closing this gap with a runtime validator/compressor and adding format_compliance metrics to EvoBench would make the compression strategy both measurably effective and reliably enforced.

The current EvoBench scores (99.22–99.98 composite) confirm that the *selection* layer is saturated. Further improvement requires measuring *compression* effectiveness — a dimension not currently evaluated by the benchmark suite.
