---
id: retro-digest
version: "20.0.0"
purpose: >
  Define the approved v20 loop-improve retrospective digest: a bounded,
  evidence-first path from operator decision to report-only historical
  learning, with explicit consent at the persistence boundary.
triggers:
  - "retro digest"
  - "retrospective digest"
  - "digest the retrospectives"
  - "cycle learnings"
tier: 2
token_estimate: 2200
last_updated: "2026-08-28"
name: retro-digest
description: >
  Load when an operator requests a retrospective digest, cycle learning
  review, or the v20 loop-improve method, so historical evidence is reviewed
  without silently changing operational learning state.
---

# Retro Digest — v20 Loop-Improve Contract

Load this reference when `classify_retro_digest_intent` returns
`DIGEST_REQUESTED` or `DIGEST_SUGGESTED`, or when selecting the
`retro-digest` seed for cycle-close learning. Execution still uses the sole
`change-driven` runtime; the seed supplies bounded checklist knowledge.

## 1. Approved loop-improve method

The method is four bounded phases. It improves the next cycle from evidence;
it does not turn a retrospective into an unreviewed configuration writer.

1. **Grill the decision contract.** Before extraction, L0 asks one question at
   a time and anchors the scope, evidence window, lesson/benefit distinction,
   curation choice, and persistence decision. The operator confirms what is
   being reviewed and whether persistence is even eligible.
2. **Phase 0 — read-only B1–B5 audits.** Run the following audits without
   modifying source or operational state:
   - **B1 Inventory:** discover all historical retrospective and evaluation
     inputs under `.local/research/` and `docs/cycle-archive/`.
   - **B2 Evidence shape:** identify supported learning/findings sections and
     mark missing or malformed evidence explicitly.
   - **B3 Provenance:** retain exact source text, repository-relative path,
     cycle, and inclusive source line span.
   - **B4 Determinism:** use stable source and record ordering; repeat the
     report and require byte-identical output.
   - **B5 Boundary:** separate lessons eligible for learning from evaluation
     benefits that remain report-only; default to report-only.
3. **Bounded PV implementation.** Implement only the selected, evidenced
   improvement in a bounded PV. L0 curation is optional metadata over
   immutable records: it may select or label record IDs, but cannot rewrite,
   summarize, normalize, or substitute `DigestRecord.text` / `raw_text`.
   Every PV has a declared ceiling and closes with its checks and evidence.
4. **Cycle close.** Render the stable digest, preserve its provenance, record
   `OK` or explicit `INSUFFICIENT`, and offer persistence only after the
   operator reviews the exact selected entries. Close the cycle with the
   report and evidence; do not infer missing inputs.

## 2. Runtime digest contract

The canonical implementation is
`src/devolaflow/skills/retro_digest.py`; the checklist composition is
`workflow-system/agent/templates/seeds/retro-digest.yaml`.

- **Inputs:** consider all discoverable historical retrospective and
  evaluation Markdown inputs in `.local/research/` and
  `docs/cycle-archive/`. Current research takes precedence over a duplicate
  archived copy for the same cycle.
- **Ordering:** discovery and rendered records use deterministic stable
  ordering by repository-relative record ID. Identical inputs produce
  identical reports.
- **Verbatim evidence:** the exact passage content is retained in `text` and
  the original source line is retained in `raw_text`, with repository-relative
  provenance (`path#Lstart-Lend`). Provenance is data, not a replacement for
  the source passage.
- **Curation:** `DigestCuration` is optional L0 selection/label metadata.
  Curation can change which immutable records are shown or learned from; it
  cannot change their source text or provenance.
- **Benefits:** evaluation findings are a separate `Benefits` report section
  and are report-only. `to_learning_entries` excludes benefits from
  operational learnings.
- **Default:** discovery, extraction, rendering, and review are report-only.
  No automatic write follows a successful digest.
- **Persistence:** writing selected lessons to
  `.local/memory/operational.jsonl` requires explicit operator consent for
  that write. Only then may the L0 invoke the explicit
  `capture_digest_entries` boundary. Consent to review or curate is not
  consent to persist.
- **Persistence is incremental (v24.3.0):** `to_learning_entries` converts
  lessons from the current and previous cycle only. This repository's digest
  reaches back more than twenty cycles; adopting all of it would file
  conclusions about deleted code as live operational guidance, ranked beside
  what the last release actually learned. Older cycles stay in the rendered
  report, where a reader weighs them in context. Pass `cycles` to override the
  window; pass `()` to convert everything.
- **Two kinds of silence (v24.3.0):** a discovered source that contributes no
  record is always listed in `silent_sources`. If its learnings or findings
  heading was *found* and still yielded nothing, it is additionally listed in
  `unparsed_sources` and the whole digest is `INSUFFICIENT` — a heading
  promised evidence that did not arrive. A source with no such heading may
  genuinely have none, so it is reported without downgrading the result.
- **Learning metadata:** persisted lesson entries use confidence `0.9`,
  `ttl_days: 90`, and the standard learning confidence decay
  (`DEFAULT_DECAY_HALF_LIFE_DAYS`). These values do not apply to report-only
  benefits.
- **Activation surface:** natural-language activation only. This method adds
  no new CLI and no new `DEVOLAFLOW_*` flag.
- **Missing evidence:** absent, unsupported, or insufficient source material
  yields explicit `INSUFFICIENT`; it is never an implicit pass or a manual
  success.

## 3. Small operator flow

```text
NL: "Please create a retro digest"
  → classify as DIGEST_REQUESTED
  → grill scope + persistence decision, one question at a time
  → run Phase 0 B1–B5 read-only audits
  → show stable Lessons and separate report-only Benefits
  → optionally select immutable record IDs
  → ask: "Persist these exact lessons to operational.jsonl? (yes/no)"
  → only explicit yes enables capture_digest_entries
```

`DIGEST_SUGGESTED` requires operator confirmation before entering the flow;
`NO_DIGEST` is the default. Until explicit consent is received, there are no
automatic writes to `operational.jsonl` or any other operational artifact.

## 4. Cross-references

- `references/grill-mode.md` — one-question-at-a-time grilling and consent
- `references/meta-framework.md` — seed selection and sole runtime
- `references/human-surface.md` — report-oriented human output
- `src/devolaflow/skills/retro_digest.py` — runtime API and status contract
- `workflow-system/agent/templates/seeds/retro-digest.yaml` — PV checklist

## History

- v20.0.0: approved loop-improve method and report-only retro digest contract.
