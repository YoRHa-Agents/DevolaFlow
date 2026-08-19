# DevolaFlow v6.0 → v6.1 Iteration Retrospective

**Iteration:** v5.4.2 → v6.1.0 (5 waves + Wave 6 rollup)
**Date:** 2026-04-16
**Feature branch:** feat/v6.0-rollup

## 1. Gaps identified (from SI-1 v6.0.0 planning gate)

- **P0:** Deferred v6.0 deprecation removals (`evaluate_gate_with_nines`, `run_nines_advisor`, `_BUILTIN_SPECS`, `MVP-SKILL.md`).
- **P0:** Dead-wire bug — `apply_round_escalation` + `merge_reinforcement_into_dispatch` implemented + tested but unwired (no production callers since v5.3.0).
- **P1:** 12 of 16 planned adapter platforms missing (v4.2 → v5.0 proposal never executed).
- **P1:** Schema drift risk across 3 YAMLs (`task-dispatch.schema.yaml`, `lean-dispatch.yaml`, `gate-report.schema.yaml`) with no parity enforcer.
- **P1:** 26 of 29 EvoBench scenarios without regression baseline (only 3/29 had baselines, leaving 89.7pp of coverage blind).
- **P1/P2:** Rule contradictions — CP-3 vs SF-3 vs CLAUDE.md disagreed on the canonical version-location count.

## 2. What was implemented

| Wave | Version | Commit | Delivered |
|---|---|---|---|
| 1 | v6.0.1 | `34bc586` | MVP-SKILL retirement (−141 refs), `_BUILTIN_SPECS` removal (single-source plugins.yaml), rule reconciliation (TD-6) |
| 2 | v6.0.2 | `f4d93fc` | Deprecated API removal (BREAKING), `MIGRATION-v6.md`, DeprecationWarnings 12 → 0 |
| 3 | v6.0.3 | `c0112d6` | Dead-wire closure (`apply_round_escalation` + reinforcement merge) + E2E convergence test |
| 4 | v6.0.4 | `ec9e14c` | `AdapterRegistry` + `DataDrivenAdapter` + `kimicode.yaml` + `windsurf.yaml` |
| 5 | v6.0.5 | `931183e` | Schema parity enforcer (6 tests) + 29/29 EvoBench baseline coverage |
| 6 | v6.1.0 | (pending commit) | `continue.yaml` + `openclaw.yaml` + golden snapshot tests + coverage fixes + SKILL update |

## 3. What was deferred and why

- **V6-04 `unwanted_hints` negative routing** — benchmarks showed 0% improvement on current scenarios; value is preventive, not regressive. Deferred until scenario set grows large enough for routing noise to matter.
- **V6-03 plan-mode detection** — scope vs. ROI trade-off; lower priority than Tier 2 dead-wire closure.
- **V6-05 SkillRouter semantic profile matching** — large effort; not warranted at 8 adapters / 16 profiles.
- **V6-09 Cursor hard-reinforcement hook** — depends on real-world V6-01 rollout telemetry we do not yet have.
- **V6-10 Two-stage gate orchestration** — large effort; separate release scope.
- **V6-11 Skill trust-tier governance** — security initiative, belongs in its own release.

## 4. Key learnings

- **Dead-wire bugs are the highest-leverage v6.0 intervention.** Two infrastructure pieces (`apply_round_escalation`, `merge_reinforcement_into_dispatch`) had passing unit tests since v5.3.0 but zero production callers. Benchmark-measured ROI before wiring: 0. After wiring: +20% round-3 budget, explicit MUST-fix mandates in dispatch. **Next-iteration ask:** add a CI check that fails when a public API has no non-test caller in `src/`.
- **Multi-platform adapter expansion is a YAML problem, not a Python problem.** Every new adapter dropped from ~80 LOC Python to ~25 LOC YAML via `DataDrivenAdapter`. Continue + OpenClaw adapters landed in ~35 LOC total (2 YAML files), plus 4 golden tests to lock the Cursor contract.
- **Honest benchmarks prevent ghost features.** V6-04 `unwanted_hints` showed 0% improvement on current scenarios. We explicitly deferred it instead of shipping a feel-good feature. CP-1 (no ghost features) held.
- **Schema parity needs enforcement.** TD-4 parity tests caught 2 fields that would otherwise have drifted during Wave 4 (new verification fields in `lean-dispatch.yaml` but not `task-dispatch.schema.yaml`).
- **Regression detection needs 100% coverage.** Before v6.0.5, only 3/29 scenarios had baselines — the other 26 could silently regress forever. Fix: auto-generate baselines as a CI step via `benchmarks/devolaflow_context/generate_baseline.py`.
- **SKILL.md edits have benchmark-scoring side effects** (discovered in Wave 6). The line-range extractor in `context_profiles.yaml` uses hardcoded line numbers that drift silently when SKILL.md grows. Wave 6 learned this the hard way: a 2-line insertion inside the Dispatch & Report Protocol section inflated the extracted token count for `lifecycle_hooks` (range 373-383) enough to squeeze out `rationalization_prevention`, dropping `feedback_regression` composite 99.33 → 90.34. The fix was to place the new paragraph AFTER the `Full schemas:` line (outside any range endpoint), and regenerate the baseline (`v6.0.5_baseline.json` → `v6.1.0_baseline.json`). **Next-iteration ask:** migrate `context_profiles.yaml` line ranges to section-id anchors (e.g., `section: dispatch_report`) so line drift stops breaking benchmarks.

## 5. Cross-wave metrics evolution

| Metric | v5.4.2 | v6.0.1 | v6.0.2 | v6.0.3 | v6.0.4 | v6.0.5 | v6.1.0 |
|---|---|---|---|---|---|---|---|
| Tests | 818 | 820 | 791 | 812 | 858 | 871 | 896 |
| DeprecationWarnings | 12 | 12 | 0 | 0 | 0 | 0 | 0 |
| Adapters supported | 4 | 4 | 4 | 4 | 6 | 6 | 8 |
| EvoBench baselines | 3/29 | 3/29 | 3/29 | 3/29 | 3/29 | 29/29 | 29/29 |
| Rule contradictions | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| MVP-SKILL refs | 141 | 0 | 0 | 0 | 0 | 0 | 0 |
| NineS overall | 0.7405 | 0.7405 | 0.7405 | 0.7405 | 0.7405 | 0.7405 | 0.7405 |
| Coverage (overall) | ~91% | ~91% | ~91% | ~91% | ~91% | ~91% | ~94% |
| cli.py coverage | 49% | 49% | 49% | 49% | 49% | 49% | 98% |
| init_project.py coverage | 59% | 59% | 59% | 59% | 59% | 59% | 94% |
| composer.py coverage | 66% | 66% | 66% | 66% | 66% | 66% | 100% |

## 6. SI-3 composite score (v6.1.0)

| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Code quality | 0.20 | 9.5 | Lint clean (ruff check + format), docstring 100%, NineS 1.00 on `code_review_accuracy` dimension |
| Architecture | 0.20 | 9.5 | Registry pattern enables growth; dead-wire closed; schemas unified under parity enforcer |
| Test adequacy | 0.20 | 9.0 | +25 tests (871 → 896); full E2E coverage; schema parity; full 29/29 baseline |
| Maintainability | 0.15 | 9.2 | −420 LOC dead code removed; single-source plugin config; canonical schemas; composer 100% covered |
| Compatibility | 0.10 | 8.5 | Breaking change in v6.0.2 documented; `MIGRATION-v6.md` shipped; YAML adapter format stable since v6.0.4 |
| Performance | 0.15 | 9.5 | No benchmark regressions (29/29 within ±5pp baseline); NineS stable across 7 versions |

**Weighted composite:** `(9.5×0.20 + 9.5×0.20 + 9.0×0.20 + 9.2×0.15 + 8.5×0.10 + 9.5×0.15) ≈ 9.23/10`

**Threshold:** ≥ 8.5 → **READY for stable v6.1.0 release.**

## 7. Next iteration inputs (feed back to SI-1 v6.2 planning)

- **Revisit V6-04** (`unwanted_hints` negative routing) at 50+ scenarios — probability of signal grows with scenario count.
- **V6-03** (plan-mode detection) after user feedback on v6.1.0 adoption.
- **V6-09** (Cursor hook layer) once V6-01 has observable convergence data from real-world use.
- **New:** Add a CI job "dead API detector" — flags public APIs in `src/` with no non-test caller. (Follow-up to Wave 3 dead-wire closure learning.)
- **New:** Windsurf adapter compression transform to bring `.windsurfrules` under the 8 KB char budget (currently WARN at ~24 KB).
- **New:** Expand golden snapshot coverage to Codex/Claude/Copilot adapters (v6.1.0 C3 only locked Cursor).
