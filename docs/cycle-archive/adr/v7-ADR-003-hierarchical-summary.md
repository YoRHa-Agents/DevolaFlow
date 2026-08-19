# v7-ADR-003 — Deterministic Hierarchical Predecessor-Artifact Summarisation

- **Status:** Accepted
- **Date:** 2026-04-17
- **Authors:** Design team L3 task agent for V7.0.0-S02-T01
- **Ships in:** v7.0.2 (see `.local/research/v7.0.0_version_roadmap.md`)
- **Research source:** `.local/research/v7.0.0_context_compression_research.md` §§B.3, F row 2, G row 2, J.3
- **Decides:** Open question K.1 (forced-summarisation threshold), contributes to open question K.6 (NineS V1 golden set authoring)

## 1. Context

DevolaFlow's lean dispatch embeds predecessor artifacts as
`pred[*].key_facts` — **verbatim extractions** (per rule CO-2) from the
source artifact. The extraction itself is currently produced *ad-hoc*
by the dispatching agent: there is no deterministic helper in
`src/devolaflow/compressor.py` that reads an artifact and emits a
bounded-token summary.

This is problematic because:

- When the predecessor artifact is small (≤ 1 KB), agents emit
  `key_facts` that mostly match ground truth by luck.
- When it grows (5–10 KB, as our S01 research report just did at 1022
  lines / ~70 KB / ~15 K tokens), agents paraphrase or omit facts,
  producing hallucinated file paths and softening error strings —
  precisely the failure mode rule CO-2 warns against.
- The Anthropic cookbook (`[ref-6]` in the research report) recommends
  compaction (lossy, model-driven) at ~150 K tokens but explicitly
  notes that multi-document research agents benefit from hierarchical
  summarisation *before* hitting the hard context limit.

Research §F row 2 estimates that a deterministic summariser lifts
EvoBench composite by **+5 to +10** on retention-sensitive scenarios
and NineS `analysis` by **+0.02** via richer keypoint extraction.
Research §J.3 budgets the implementation at ~350 LOC.

This ADR commits DevolaFlow to a **deterministic extractive-by-default**
summariser with an optional abstractive mode and a hard relative token
threshold for when summarisation becomes mandatory.

## 2. Decision

### 2.1 Public API

Add to `src/devolaflow/compressor.py`:

```python
def summarise_predecessor(
    artifact_path: str,
    max_tokens: int = 500,
    mode: str = "extractive",
    schema_hint: str | None = None,
) -> dict:
    """Produce a bounded-token summary of a predecessor artifact.

    Args:
      artifact_path: relative path to the artifact file.
      max_tokens: hard cap on the summary's token count.
      mode: "extractive" (default, deterministic, verbatim per CO-2)
            or "abstractive" (LLM-driven, opt-in per profile).
      schema_hint: optional artifact type ("design" | "research" |
                   "adr" | "gate_report") — controls which extractor
                   runs first.

    Returns a dict:
      - summary_text: str (≤ max_tokens tokens)
      - mode: str (echoed)
      - token_count: int
      - extracted_entities: list[dict] with keys {type, value, source_line}
      - covered_sections: list[str]    # which artifact headings contributed
      - dropped_sections: list[str]    # skipped headings and why
      - was_bounded: bool              # True iff a section had to be truncated
    """

def extract_named_entities(text: str) -> list[dict]:
    """Deterministic NER over DevolaFlow's structured entity classes.

    Detects: file_paths, task_ids, version_strings, commit_hashes,
    metric_values, error_messages, acceptance_criterion_bullets,
    interface_signatures (Python def/class or YAML type: hints).
    Reuses the preserve-list regex patterns in compressor.py.
    """
```

### 2.2 Extractive mode (default)

Algorithm:

1. **Parse artifact** by file extension. Markdown (`.md`) → headings +
   list bullets + code blocks; YAML (`.yaml`) → key/value; JSON (`.json`)
   → leaf-value enumeration.
2. **Extract entities** via `extract_named_entities` on the full body.
   All extracted entities are emitted verbatim.
3. **Select sections** by a `schema_hint`-driven priority:
   - `design`: "Decision" > "Consequences" > "Alternatives".
   - `research`: "Recommendations" > "Open Questions" > "Synthesis".
   - `adr`: "Decision" > "Consequences" > "Test plan".
   - `gate_report`: "Verdict" > "Findings" > "Metrics".
   - default: H2 headings in document order.
4. **Bound by tokens**: fill `max_tokens` budget with selected sections
   in priority order, copying verbatim; emit `was_bounded=True` when
   at least one section was truncated. **No paraphrase, ever.**
5. **Return a structured summary** with `summary_text` prefixed by the
   extracted entities as a `key_facts:` YAML block, followed by the
   selected sections as verbatim markdown.

### 2.3 Abstractive mode (opt-in)

Activated only when a profile sets `summary_mode: abstractive` in
`context_profiles.yaml`. Implementation detail: wraps the extractive
summary with an LLM call using a fixed prompt (stored in
`src/devolaflow/prompts/summarise_abstract.txt`). Abstractive mode
MUST still emit `extracted_entities` verbatim (via the extractive
pass) and is audited by the H.4 persistence probe (v7-ADR-004) to
detect named-entity drift.

### 2.4 Trigger threshold (committed — resolves K.1)

Summarisation is **mandatory** when the predecessor artifact exceeds
**25 % of the consuming layer's token budget**. For default budgets:

| Layer | Budget | Summarise above |
|-------|--------|-----------------|
| L3 Task | 8 000 | 2 000 tokens |
| L2 Wave | 4 000 | 1 000 tokens |
| L1 Stage | 5 000 | 1 250 tokens |
| L0 Project | 3 000 | 750 tokens |

Below the threshold, the dispatcher may embed the artifact body
directly under `pred[*].body`. The threshold is configurable per
profile as `summary_trigger_pct: 25` (meta key in
`context_profiles.yaml`).

### 2.5 Schema addition

`schemas/lean-dispatch.yaml` gains an optional per-pred field
`summary_mode: extractive | abstractive` and a sibling
`summary_max_tokens: int`. Default: `extractive` / `500`. Missing
fields = extractive / 500.

## 3. Consequences

### Positive

- Deterministic, reproducible dispatch content eliminates one of the
  largest current sources of variance in EvoBench scenarios (current
  `standard` profile retention on compression probes is heavily
  dispatch-specific).
- CO-2 (verbatim extraction) is now *enforced by construction* for
  the default mode instead of relying on agent compliance.
- Abstractive mode stays available for teams that need narrative
  summaries (e.g., exec-facing stage reports) behind an explicit
  per-profile opt-in.
- Unlocks the H.1 retention benchmark suite: golden artifacts with
  known probe facts can be synthesised and retention measured
  deterministically.

### Negative

- ~350 LOC in `compressor.py` (the single largest code change in the
  v7.0.0 → v7.1.0 cycle).
- Extractive summaries are *less readable* than abstractive for humans;
  agents must learn the `key_facts:` prefix convention.
- New external assumption: markdown / YAML parsers are available in
  the runtime. Python stdlib handles YAML via PyYAML (already a
  dependency) and markdown via a minimal regex-based parser we ship in
  `compressor.py` to avoid adding a heavy new dep.

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Extractor misses a schema-hinted heading variant (e.g. "Decisions" plural) | P2 | Heading matching is case-insensitive, accepts plural/singular, and falls back to "first H2" when no priority-list match succeeds. Unit tests cover 10+ heading spellings. |
| Abstractive mode hallucinates a named entity not in the source | P1 | H.4 persistence probe (v7-ADR-004) asserts entity carry-through ≥ 90 %; any drop blocks release. |
| Summariser produces summary larger than `max_tokens` due to quirky whitespace | P2 | Hard post-hoc truncation at the token boundary after assembly; emit a `[TRUNCATED]` marker at the break. |
| Schema-hint mismatch (`design` hint on a research artifact) | P3 | Schema-hint inference from filename prefix (`research/`, `designs/`, `adr/`, etc.) is advisory only; default extractor still runs and produces a usable summary. |

## 4. Alternatives Considered

### 4a. **Abstractive only (single LLM pass)**

Skip the extractive path and always summarise via LLM. **Rejected**
because (1) CO-2 mandates verbatim extraction for facts, (2)
abstractive adds per-dispatch cost, (3) the LLM Scaling Paradox
(referenced in `schemas/lean-dispatch.yaml`) shows compaction > summarisation
on retention, which is exactly the metric we optimise.

### 4b. **Defer to the dispatching agent**

Keep the current ad-hoc behaviour; rely on prompt discipline.
**Rejected** because we've seen drift on the v7.0.0 research report
(1022 lines — far exceeds the 25 % threshold) — the dispatcher is
already at the wrong end of the failure curve.

### 4c. **External summariser library (e.g., `sumy`, `lex-rank`)**

Adopt a third-party extractive summariser. **Rejected** because those
libraries target prose and do not preserve code blocks, YAML, or
acceptance-criteria bullets verbatim. DevolaFlow's artifact corpus is
heavily structured — we need a DevolaFlow-aware extractor.

### 4d. **Trigger threshold = absolute 2K tokens**

Use a fixed 2 K token threshold across all layers. **Rejected**
because it starves L2 Wave (budget 4 K) and is luxurious for L3 Task
(budget 8 K). A relative threshold tracks the consuming layer's
budget correctly and scales with future budget tuning.

## 5. Reversibility

**Cost to undo:** Medium.

- Remove `summarise_predecessor` and `extract_named_entities` from
  `compressor.py` (but the latter is also consumed by the persistence
  probe per v7-ADR-004 — leave it).
- Remove the `summary_mode` / `summary_max_tokens` fields from
  `schemas/lean-dispatch.yaml`.
- Remove compression scenarios under
  `benchmarks/devolaflow_context/scenarios/compression_*.json`.
- Revert the SKILL.md "Hierarchical Summary" subsection.

Downstream dispatchers survive rollback because absent fields default
to extractive/500 (and the legacy fallback path kicks in). Rollback
window: ≤ 2 patch versions because ADR-004 depends on
`extract_named_entities`.

## 6. Test Plan

Tests that would falsify this decision:

1. **`tests/test_compressor.py::test_summarise_extractive_preserves_file_paths`** —
   summarise a synthetic 5 K-token design doc; all file paths present
   in the source appear verbatim in `extracted_entities`.
2. **`tests/test_compressor.py::test_summarise_extractive_honours_max_tokens`** —
   `max_tokens=500` produces a summary with `token_count ≤ 500`.
3. **`tests/test_compressor.py::test_summarise_schema_hint_priority`** —
   schema_hint="adr" on an ADR prefers "Decision" over "Context".
4. **`tests/test_compressor.py::test_summarise_unknown_extension`** —
   `.txt` artifact summarised by H2-heading fallback; no exception.
5. **`tests/test_compressor.py::test_summarise_trigger_threshold`** —
   L3 consuming 2 001 tokens of predecessor triggers summarisation;
   L3 consuming 1 999 tokens does not.
6. **`tests/test_compressor.py::test_extract_named_entities_all_types`** —
   synthetic artifact with each of {file_paths, task_ids, version_strings,
   commit_hashes, metric_values, error_messages, acceptance_criterion_bullets,
   interface_signatures}; extractor returns at least one of each.
7. **`benchmarks/devolaflow_context/scenarios/compression_retention_easy.json`** (H.1) —
   retention ≥ 95 % on preserve-list facts after extractive summary.
8. **`benchmarks/devolaflow_context/scenarios/compression_retention_medium.json`** —
   retention ≥ 95 %.
9. **`benchmarks/devolaflow_context/scenarios/compression_retention_hard.json`** —
   retention ≥ 90 % (hardest scenario; 15 K-token artifact at 500-token
   budget).
10. **NineS golden set** — `data/golden_test_set/compression_retention_easy.toml`
    (and medium / hard siblings) score ≥ 0.85 on NineS `scoring_accuracy`
    evaluator at v7.1.0 cut.

Scenario #9 is the stretch goal; #7 and #8 block release.

## 7. Cross-References

- Depends on: **v7-ADR-001** (layout invariant — new schema fields
  appended at stable positions).
- Depended on by: **v7-ADR-004** (persistence probe re-uses
  `extract_named_entities`).
- Related rules: `.cursor/rules/context-optimization-rules.mdc` (CO-2
  verbatim extraction), `.cursor/rules/self-improve-iteration-rules.mdc`
  (SI-6 context-budget enforcement).
- Research §: B.3, F row 2, G row 2, H.1, J.3, K.1, K.6.
