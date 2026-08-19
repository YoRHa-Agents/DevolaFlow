# v9-ADR-008 — v9.0.1 Sustaining: repo-modes Polish + Tier-2 Enterprise Adapter Batch

**Status**: Accepted
**Date**: 2026-04-24
**Cycle**: v9.0.0 (PV-08 sustaining / PATCH `v9.0.1`)
**Supersedes**: n/a (additive sustaining)
**Amended-by**: n/a
**Related**: `v9-ADR-007-rule-rebalancing-and-rollup.md` (MAJOR closure); gap analysis §5.8 + implementation plan §6.8

---

## Context

v9.0.0 cycle closed at PV-07 with SI-3 composite 9.22/10 (+0.22 pp margin above the 9.0 MAJOR threshold) and NineS 0.9037 (within ±0.002 noise floor of the cycle target). Per the implementation plan §6.8, PV-08 is a **conditional ship** sustaining PATCH gated by:

1. **Gate (a)** — PV-07 SI-3 ≥ 9.0 with bandwidth.
2. **Gate (b)** — Open Decision §9.2 #11 (or `decomposition_analysis.md` §"Open Decisions for v9.0.0 SI-1" #11) = approve.

At the v9.0.0 release both gates were conditionally pending. At PV-08 dispatch time:

- Gate (a) is **MET** — `v9.0.0_evaluation.md` §1 verbatim: "composite **9.22/10** ≥ MAJOR threshold 9.0 by **+0.22 pp**".
- Gate (b) is **MET** — operator (L0 dispatcher) instruction "build all unbuilt job" at PV-08 dispatch = APPROVE.

With both gates met, PV-08 ships the full scope declared in gap-analysis §5.8 rather than the scaled-back variant (repo-modes-only):

- **Scope A** — `workflow-system/agent/references/repo-modes.md` sustaining edits (~+24 LOC target, +27 actual):
  - Codeberg variant row + clarification note in §1 "Other-Git Variants"
  - `+verify` and `+monitor` rows added to §6 "Mode-Aware Stage Behavior" table
  - NEW §7 "Plugin / Tool Interaction with Mode Detection"
- **Scope B** — 5 NEW `adapter_configs/*.yaml` Tier-2 enterprise adapter configs (~+109 LOC): `jetbrains`, `amazon_q`, `gemini`, `augment`, `trae`.

Test cap forecast (W-17): ≤ +5 NEW tests (no new tests added — data-only adapter configs are exercised by existing `tests/test_data_driven_adapter.py::test_load_data_driven_adapters_scans_configs` + `tests/test_adapter_registry.py` coverage). EvoBench delta: 0. SKILL.md delta: 0. No Soul / Architecture / Conventions / Workflow rule additions (Soul frozen at 10 per W-21 from PV-07).

---

## Decision D1 — Ship PV-08 at Full Scope as `v9.0.1` PATCH

**Decision**: Ship both Scope A (repo-modes.md sustaining) AND Scope B (5 Tier-2 adapter configs) in a single PR tagged `v9.0.1`.

**Rationale**:

1. **Gate (a) bandwidth is comfortable** — the +0.22 pp margin over the 9.0 MAJOR threshold (and +0.74 pp over the 8.5 PATCH threshold that governs PV-08 itself) is well above the noise floor; SI-3 for a sustaining PATCH should land ≥ 9.0 trivially because the scope is additive-only and test-cap-bounded.
2. **Gate (b) is explicit operator approval** — "build all unbuilt job" is unambiguous full-scope authorization; defer-to-v9.1.0 (the §6.8.6 fallback path) would contradict the instruction.
3. **Coupling is loose** — Scope A touches a single reference doc (no code path); Scope B adds 5 data-only YAML files (no schema change, no test surface change). A PR-level revert is a clean single-step rollback if anything drifts post-merge; blast radius is file-level per §6.8.6.

**Alternatives considered**:

- **(A.1) Scope-A-only (skip adapters)** — would land the reference polish but leave the 5 enterprise adapters unshipped, requiring a second sustaining PR and another test-cycle overhead. Rejected because the user's instruction explicitly covers the full scope and the adapter coverage is zero-risk (YAML data, no code).
- **(A.2) Defer all to v9.1.0 PV-01** — the §6.8.6 R-12 rollback path. Rejected because neither gate is tripping and the sustaining scope is ready-to-ship; deferral would inflate v9.1.0's PV-01 scope without benefit.

---

## Decision D2 — Tier-2 Adapter Config Schema Parity

**Decision**: All 5 NEW adapter YAMLs conform to the existing v1 schema documented in `src/devolaflow/adapters/data_driven.py::DataDrivenAdapter` docstring (lines 57-81) and register as `tier: tier_2` via the existing `load_data_driven_adapters()` loader.

**Schema-mapping table**:

| Adapter | `base_dir` | `SKILL.md` target + transform | `references/` target + transform | Budget |
| --- | --- | --- | --- | --- |
| `jetbrains` | `.idea/devola-flow` | `SKILL.md` / `copy_with_frontmatter` | `references` / `copy_tree` | lines 800 |
| `amazon_q` | `.amazonq/rules` | `devola-flow.md` / `strip_frontmatter` | `references` / `copy_tree` | lines 800 |
| `gemini` | `.gemini` | `devola-flow.md` / `strip_frontmatter` | `references` / `copy_tree` | lines 800 |
| `augment` | `.augment/rules` | `devola-flow.md` / `strip_frontmatter` | `references` / `copy_tree` | lines 800 |
| `trae` | `.trae/rules` | `devola-flow.md` / `strip_frontmatter` | `references` / `copy_tree` | lines 800 |

**Rationale**:

1. **JetBrains retains frontmatter** (via `copy_with_frontmatter` + injected `platform: jetbrains`) because the JetBrains AI Assistant plugin surface (when authored) can parse YAML frontmatter for platform-aware routing — mirrors the existing `kimicode` precedent that also keeps frontmatter for platform-tagging.
2. **Amazon Q / Gemini / Augment / Trae strip frontmatter** because their workspace-rule readers consume the markdown body directly (`.amazonq/rules/*.md`, `.gemini/*.md`, `.augment/rules/*.md`, `.trae/rules/*.md`) and a leading YAML block would surface as user-visible noise at the top of every rule file.
3. **Budget 800 lines** is the Tier-2 standard (matches `cline`, `continue`, `roo`, `zed`) and comfortably accommodates the current SKILL.md (442/500 line source + ~10 line transform delta for frontmatter-stripped variants).
4. **`tier: tier_2`** semantics: Tier-2 adapters register via the `DataDrivenAdapter` loader but are NOT in the `build-skill` default core set (which is `{cursor, codex, claude, copilot}` per `tests/test_adapter_registry.py::test_create_default_registry_has_4_core`). Operators explicitly opt in via `build-skill --tools jetbrains,...`.

**R-3 mitigation**: the `test_create_default_registry_has_4_core` assertion remains green because the 5 new adapters land as `tier_2`, not `core` — adding them does not expand the 4-core set.

**Alternatives considered**:

- **(B.1) Code-path adapters (subclassing `BaseAdapter`)** — would allow per-adapter custom logic but violates the v6.0.4 D1 data-driven principle and multiplies maintenance cost. Rejected — every new enterprise adapter should land as a YAML config unless it needs a transform not in `VALID_TRANSFORMS`.
- **(B.2) Single unified enterprise adapter YAML with variant fan-out** — would concentrate the 5 targets into one file with a templating layer. Rejected because (a) no template machinery exists in `DataDrivenAdapter` today, (b) the per-adapter `base_dir` values diverge enough that templating would hurt readability, (c) single-file-per-adapter mirrors the existing 7 Tier-1/Tier-2 files and keeps the registry loader logic trivial.

---

## Decision D3 — `references/repo-modes.md` Sustaining Edits Scope

**Decision**: Add (a) Codeberg variant row + clarification note to §1; (b) `+verify` and `+monitor` rows to the §6 Mode-Aware Stage Behavior table; (c) NEW §7 "Plugin / Tool Interaction with Mode Detection".

**Rationale**:

1. **Codeberg completeness** — the regex pattern for `codeberg\.org[:/]` is already present in §3 "Regex Patterns" but the Other-Git Variants table in §1 omits it. The inconsistency was flagged as a gap in the v9.0.0 reference review (`.local/research/v9.0.0_reference_review.md`); closing it here removes the surface-area discrepancy between detection logic and operator-facing documentation.
2. **`+verify` and `+monitor` rows** — these two stage names surface in v8.2.6+ change-driven workflow templates but were not yet mapped to per-mode behaviour in the reference. The mode-aware table is the canonical mapping; adding the rows prevents downstream tooling from having to infer the per-mode semantics from first principles.
3. **NEW §7 — plugin/tool interaction** — v8.2.5 + v8.4.3 added `agent_workspace` + `shell_proxy` + `mergeability_check` plugins that ALL consume the detected repo mode. The existing reference had no canonical place to document the plugin → mode-detection contract; §7 codifies the "who consumes, with what fallback" matrix. Plugin degradation pattern (soft-fail on tool absence, returns structured no-op per S-5) is cross-referenced explicitly.

**Alternatives considered**:

- **(C.1) Inline the plugin matrix into §6 Mode-Aware Stage Behavior** — would merge stages and plugins under one heading but would conflate orthogonal concerns (stages are workflow-driven, plugins are runtime-driven). Rejected — separate §6 and §7 preserves the semantic separation.
- **(C.2) Move §7 plugin matrix to a NEW `references/plugin-mode-matrix.md` file** — would grow the reference-file count by 1 (triggering SF-4 15th-reference governance per C-7 valid-reference list invariant). Rejected — the matrix is ~18 LOC and fits cleanly inside `repo-modes.md` without stretching its budget (repo-modes.md now 309/1000 large-tier budget).

---

## Consequences

### Positive

1. **Tier-2 adapter footprint expands 2 → 7** — pre-PV-08 had `openclaw` as the only Tier-2 data-driven adapter; post-PV-08 has 6 (`openclaw` + 5 new). Enterprise operators have canonical YAML configs for JetBrains / Amazon Q / Gemini / Augment / Trae ready to consume via `build-skill --tools <name>`.
2. **Zero code-path risk** — all 5 adapter additions are YAML-only and register via the existing v6.0.4 D1 data-driven loader; no Python module changes, no test surface additions.
3. **Reference completeness for v9.0.0 mode set** — Codeberg is now fully documented in both detection logic AND the variant table, removing the v9.0.0 reference-review gap. Stage/plugin contracts for `repo-modes` are fully codified.
4. **Cycle close confirmed** — v9.0.0 cycle now formally closes at PV-08 (shipped as v9.0.1 sustaining) with 8/8 PVs accepted.

### Negative / Neutral

1. **Budget headroom for `repo-modes.md`** — the file grows from 282 → 309 lines. Still well under the SF-1 Large tier ceiling (1000); +691 lines of headroom remain for future sustaining expansions.
2. **Enterprise adapter catalog maintenance** — the 5 new adapters add a long-tail maintenance surface (tracking upstream tool API changes for JetBrains AI Assistant / Amazon Q / Gemini / Augment / Trae). Mitigation: per-adapter integration is a thin YAML config; drift detection happens organically when operators run `build-skill --tools <name>` and budget-check fails.

### Risk-register update

- **R-3 mitigation confirmed** — `test_create_default_registry_has_4_core` stays green post-merge (5 new adapters are `tier_2`, not `core`).
- **R-12 (sustaining decision stall)** — closed by D1 decision above; does NOT fire.

---

## Enforcement

| Surface | Assertion |
| --- | --- |
| `tests/test_data_driven_adapter.py::test_load_data_driven_adapters_scans_configs` | 5 new configs register without raising (PASS in PV-08 T05 W-9 run) |
| `tests/test_adapter_registry.py::test_create_default_registry_has_4_core` | 4-core set unchanged (`{cursor, codex, claude, copilot}`) — PASS in PV-08 T05 W-9 run |
| `python -m pytest tests/ -q` | All 3430 tests pass; no new failures introduced (PV-08 W-9 Step 1 PASS) |
| `ruff check src/ tests/` | Clean (PV-08 W-9 Step 2 PASS) |
| `ruff format --check src/ tests/` | 191 files already formatted (PV-08 W-9 Step 3 PASS) |
| `python -m pytest tests/test_version.py -v` | 12 passed + 19 skipped (mirror absent self-skip); v9.0.1 consistent across 7 canonical locations post-bump (PV-08 W-9 Step 4 PASS) |
| `python -m pytest tests/test_benchmarks.py -v` | 36 passed; 0 regressions > 5 pp vs `v9.0.0_baseline.json` (PV-08 W-9 Step 5 PASS) |
| `make check-cursor-skill` | exit 0 (mirror absent — opt-in per SF-3; PV-08 W-9 Step 6 PASS) |
| End-to-end adapter build (ad-hoc) | 5 new adapters build within budget: jetbrains 444/800, amazon_q 411/800, gemini 411/800, augment 411/800, trae 411/800 (verified during PV-08 T05) |

---

## Migration / Rollback

**Adoption note for `v9.0.1`** — adopters wanting to use the new adapters run:

```bash
# Build devola-flow skill for JetBrains IDE (output lands in dist/jetbrains/)
python scripts/build-skill.py --tools jetbrains

# Or all 5 Tier-2 enterprise adapters at once
python scripts/build-skill.py --tools jetbrains,amazon_q,gemini,augment,trae
```

**Rollback mechanics** — single-PR revert is sufficient because:

1. The 5 adapter YAMLs are additive (no modifications to existing files);
2. The `repo-modes.md` edits are additive (no removals or rewrites of existing content);
3. ADR-008 itself is gitignored (`.local/research/adr/`); reverting the code-path PR is the rollback.

If any of the 5 adapter configs proves buggy post-release, the operator can simply exclude that adapter from their `build-skill --tools` flag; the other 4 adapters stay operational.

---

## Source / References

- `.local/research/v9.0.0_implementation_plan.md` §6.8 (PV-08 runbook, 5 stages / 5 waves / 7 tasks)
- `.local/research/v9.0.0_gap_analysis.md` §5.8 (PV-08 scope — repo-modes + Tier-2 adapter reserve)
- `.local/research/v9.0.0_evaluation.md` §1 (PV-07 SI-3 9.22/10 verbatim)
- `.local/research/v9.0.0_decomposition_analysis.md` §9 (Skill sync / mirror LAYERED-COHERENT — 11 platform prior art)
- `.local/research/adr/v9-ADR-007-rule-rebalancing-and-rollup.md` D5 (60-rule HARD cap context; PV-08 adds 0 rules)
- `src/devolaflow/adapters/data_driven.py` lines 39-81 (DataDrivenAdapter v1 config schema + VALID_TRANSFORMS)
- `adapter_configs/openclaw.yaml` (Tier-2 reference precedent)
- `workflow-system/agent/references/repo-modes.md` (target file for Scope A)
