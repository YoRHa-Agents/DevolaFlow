# v7-ADR-004 — Cross-Stage Persistence Probe Harness

- **Status:** Accepted
- **Date:** 2026-04-17
- **Authors:** Design team L3 task agent for V7.0.0-S02-T01
- **Ships in:** v7.0.3 (see `.local/research/v7.0.0_version_roadmap.md`)
- **Research source:** `.local/research/v7.0.0_context_compression_research.md` §§H.4, I, J.4
- **Decides:** Nothing stand-alone; complements K.1 and K.4 by enforcing named-entity carry-through across stage boundaries.

## 1. Context

Current DevolaFlow test coverage has a blind spot: no end-to-end test
asserts that a named entity introduced in Stage A (research) survives
the L1 → L2 → L3 pipeline and appears verbatim in the Stage B (design)
dispatch. The failure mode is silent — an agent producing a Stage B
implementation spec may paraphrase a file path from Stage A
(`src/devolaflow/compressor.py` → "the compressor module"), break the
P5 artifact contract, and waste an entire convergence round on a
search-instead-of-execute rabbit hole.

Research §H.4 ("Persistence Probe") proposes a harness that:

- Runs a synthetic Stage A whose artifact contains a **preserve-list
  panel** of file paths, task IDs, version strings, commit hashes,
  metric values, and interface signatures.
- Summarises that artifact with `summarise_predecessor` (per ADR-003).
- Dispatches a synthetic Stage B and asserts that every preserve-list
  entity appears verbatim in the Stage B dispatch.

Research §J.4 estimates the harness at ~300 LOC (pure test code, no
production touch). The persistence-probe is the single most important
quality gate added by the v7 iteration because it catches precisely the
"interface paraphrase" failure mode that Section J.3 introduces (one of
ADR-003's explicit risks).

## 2. Decision

We ship a new pytest module `tests/test_e2e_compression.py` (~200 LOC)
plus a fixture module extension in `tests/conftest.py` (~50 LOC) plus
a named-entity extractor promoted from ADR-003 into public use
(`devolaflow.compressor.extract_named_entities`, ~50 LOC delta). All
together, ~300 LOC.

### 2.1 Harness API

```python
def _compression_e2e_workspace(tmp_path: Path) -> dict:
    """Fixture — build a synthetic two-stage workspace.

    Creates:
      - stage_a/artifact.md with a seeded preserve-list panel
      - stage_b/dispatch.yaml rendered by
        devolaflow.template_engine.render_dispatch(...)
      - stage_b/context_packed.yaml (output of
        devolaflow.task_adaptive_selector.select_context(...))
    Returns dict with paths + ground-truth entity list.
    """

def compute_entity_carrythrough_rate(
    stage_a_artifact: Path,
    stage_b_dispatch: Path,
) -> float:
    """Fraction of Stage A entities that appear verbatim in Stage B dispatch."""
```

### 2.2 Probe scenarios

Three scenarios ship with the v7.0.3 release (matching H.1 tiers):

- **easy** — 500-token artifact, 5 entities.
- **medium** — 5 000-token artifact, 20 entities.
- **hard** — 15 000-token artifact, 50 entities.

The assertion is **entity carry-through ≥ 90 %** (pass condition per
research §H.4). Expressed as: at most one entity per ten may be missed
on the hardest scenario; zero misses on easy / medium.

### 2.3 Failure classification

- **Missed verbatim but paraphrased** (file path → module name) → FAIL.
- **Missed entirely** (entity absent from Stage B dispatch) → FAIL.
- **Appears verbatim but duplicated** (appears twice) → PASS (dedup is
  the renderer's job, not the probe's).
- **Appears verbatim but in a different case** → FAIL for commit
  hashes and file paths; PASS for everything else.

### 2.4 CI integration

Added to `tests/test_e2e_compression.py` marked with
`@pytest.mark.persistence_probe`. Runs in the default pytest suite
and in the benchmark CI step (SI-4 / SI-10 step 5 gate).

## 3. Consequences

### Positive

- Catches the single highest-leverage regression (named-entity
  paraphrase) before it reaches production agents.
- Complements ADR-003 (hierarchical summary) by enforcing the contract
  it implicitly assumes; if ADR-003's extractive mode regresses, the
  probe catches it within one CI run.
- Exercises the full L1 → L3 pipeline, covering integrations that no
  unit test touches end-to-end today.
- Produces a measurable `entity_carrythrough_rate` per scenario, which
  we surface in SI-3 evaluation.

### Negative

- Adds ~2–3 seconds to CI wall time (three probe scenarios plus
  workspace setup).
- Requires maintenance of the synthetic seed data; drift between the
  probe and real artifact shape will surface as false positives.
- The `extract_named_entities` helper becomes a *quasi-public* API —
  any change to its regex set is now a benchmark-regression risk and
  must be guarded by ADR-003's unit tests.

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| False positive when a valid acronym (e.g. "API", "TTL") happens to match an entity regex | P3 | Entity regex patterns are scoped (file_paths require a `.ext`, commit hashes require a 7–40 hex run, etc.). Unit tests include negative cases. |
| Probe becomes the only guard, and `extract_named_entities` regresses silently | P2 | ADR-003 requires unit tests on the extractor independently (test #6). The probe is an integration net, not a replacement. |
| Hard scenario is too hard and fails repeatedly, becoming a flaky test | P2 | Start with 50-entity hard scenario; if flake rate > 1 %, reduce to 30 entities and raise threshold to 95 %. Track flake rate in a CI dashboard. |
| Probe drift (synthetic data diverges from real usage) | P3 | Schedule a quarterly review of probe seed data against real artifacts sampled from `.local/research/`. Any mismatch triggers an issue. |

## 4. Alternatives Considered

### 4a. **Unit test on `summarise_predecessor` only**

Rely on ADR-003's own unit tests to catch paraphrase regressions.
**Rejected** because unit tests cover only the summariser, not the
integration point where the summariser output is *consumed* by the
Stage B dispatcher. Real regressions manifest at integration boundaries.

### 4b. **Manual regression test per release**

Leave the probe as a documented manual checklist in SI-3. **Rejected**
because SI-9 reinforcement + SI-10 test-then-commit require
deterministic verification; a manual checklist is not deterministic.

### 4c. **Coverage ≥ 100 % on `compressor.py`**

Target coverage alone as a proxy. **Rejected** — coverage tells us
*which lines execute*, not *which semantic invariants hold*. The
probe tests a semantic invariant (carry-through ≥ 90 %) that coverage
cannot express.

### 4d. **Cross-agent property-based test (Hypothesis)**

Use Hypothesis to generate random artifacts and verify the invariant.
**Rejected** for v7.0.3 because setting up a meaningful property-based
test around `summarise_predecessor` needs a corpus of realistic artifact
shapes (markdown with H1–H4, code fences, YAML fragments) — we don't
have that corpus yet. Consider for v8.x once the probe seed library
stabilises.

## 5. Reversibility

**Cost to undo:** Very low.

- Delete `tests/test_e2e_compression.py`.
- Delete `_compression_e2e_workspace` fixture entries from
  `tests/conftest.py`.
- Keep `extract_named_entities` because ADR-003 uses it; only the
  integration harness disappears.

No production code path is affected. Rollback window: same patch
version.

## 6. Test Plan

This ADR *is* the test plan for ADR-003. Self-referential tests — i.e.,
tests that would falsify *this* decision, rather than the code it
guards — are:

1. **`tests/test_e2e_compression.py::test_carrythrough_passes_on_faithful_summary`** —
   summariser emits verbatim; probe PASSES at 100 %.
2. **`tests/test_e2e_compression.py::test_carrythrough_fails_on_paraphrase`** —
   inject a paraphrased file path into the Stage B dispatch; probe
   FAILS with a clear diagnostic naming the missing entity.
3. **`tests/test_e2e_compression.py::test_carrythrough_threshold_easy`** —
   easy scenario, 0 missing entities → PASS at 100 %.
4. **`tests/test_e2e_compression.py::test_carrythrough_threshold_medium`** —
   medium scenario, at most 2 / 20 missed → PASS.
5. **`tests/test_e2e_compression.py::test_carrythrough_threshold_hard`** —
   hard scenario, at most 5 / 50 missed → PASS.
6. **`tests/test_e2e_compression.py::test_extract_named_entities_integration`** —
   `extract_named_entities` on a 10 K-token artifact returns ≥ 40
   entities of mixed types.
7. **`tests/test_e2e_compression.py::test_probe_reports_flake_rate`** —
   metadata run that collects and records per-scenario elapsed time
   into `.local/research/v7.0.3_probe_telemetry.json` for SI-3 scoring.

Test #2 is the key semantic guard: if we cannot distinguish a paraphrase
from a verbatim extraction, the probe has failed.

## 7. Cross-References

- Depends on: **v7-ADR-001** (layout invariant ensures stable Stage B
  dispatch shape), **v7-ADR-003** (summariser + entity extractor).
- Depended on by: every later ADR that changes compressor behaviour
  (v7-ADR-005 and any v8.x compression ADR).
- Related rules: `.cursor/rules/change-process-rules.mdc` (CP-2
  coverage floor, CP-4 gate tests),
  `.cursor/rules/self-improve-iteration-rules.mdc` (SI-4, SI-10).
- Research §: H.4, I, J.4.
