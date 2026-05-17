# Subagent Report: Tech Debt & Deprecation Analysis (v5.4.2 → v6.0.0)

**Agent ID:** a8d3b4b5-0897-43b6-9689-d856a77fc861  
**Date:** 2026-04-16  
**Scope:** Technical debt, deprecated APIs, dead code, coverage gaps, rule rot

## Executive Summary

DevolaFlow **5.4.2** centralizes real deprecation on the **NineS-in-gate** path: `evaluate_gate_with_nines` and `run_nines_advisor` emit `DeprecationWarning` and are slated for removal in **v6.0**; production callers are essentially gone, with **tests** in `tests/test_nines.py` as the main consumers. **`_BUILTIN_SPECS`** in `plugins/loader.py` duplicates **`workflow-system/agent/plugins.yaml`** for the same two plugins; YAML is richer (e.g. `platform_install`, `update_command`), and the registry **overwrites** on name collision so builtins are redundant when the repo YAML is present. **MVP-SKILL.md** is still referenced from **README**, human **quickstart** (EN/ZH), **demo**, **generate_human_docs.py**, **reference-dependencies.yaml**, **build-site.sh**, and **PR template** despite CHANGELOG **5.4.1** deprecating it—removal needs a coordinated doc/install sweep. **Coverage** is lowest on **CLI wrappers**, **init_project** filesystem paths, **composer** operator helpers, **check_drift** integration, and **`nines/_cli`** failure branches—mostly fixable with focused unit tests. **Rule rot:** `.cursor/rules/change-process-rules.mdc` **CP-3** still requires **`CLAUDE.md` frontmatter/banner/body version** strings, but **root `CLAUDE.md`** is now lightweight and has **no `version:`** in frontmatter.

## 1. Deprecated API Inventory

| Severity | File:line | Symbol | Reason | Replacement | Callers (src / tests) |
|----------|-----------|--------|--------|-------------|------------------------|
| **Major** | `src/devolaflow/gate/scorer.py:527-602` | `evaluate_gate_with_nines` | `warnings.warn`: NineS is for research, not gate scoring. Export comment: `# deprecated, removal in v6.0` at `gate/__init__.py:65` | `evaluate_gate()`; NineS via `devolaflow.nines.researcher` | **src:** internal call to `run_nines_advisor` in same flow; **tests:** `tests/test_nines.py` (multiple classes) |
| **Major** | `src/devolaflow/nines/advisor.py:95-116` | `run_nines_advisor` | Deprecated gate enrichment | `get_research_advice()` + `evaluate_gate()` | **src:** imported by `gate/scorer.py` (lazy); **tests:** `tests/test_nines.py` |

**Note:** `nines_dimension_scores` is labeled "legacy" in package docstring but has NO `DeprecationWarning` in code — not the same class.

## 2. Dead Code / Unused Modules

### `_BUILTIN_SPECS` vs `plugins.yaml` duplication

- **Evidence:** `src/devolaflow/plugins/loader.py:17-75` defines `_BUILTIN_SPECS` for `nines` and `ui-ux-pro-max`
- **`plugins.yaml`:** `workflow-system/agent/plugins.yaml` defines the **same two** plugins with **richer** fields (e.g. `platform_install`, `update_command`, `uninstall_command` for `ui-ux-pro-max`)
- **Behavior:** `create_default_registry` registers builtins **first**, then YAML (`loader.py:131-144`). Registry **overwrites** on name collision (`registry.py:50-54`) → builtins are **superseded** when YAML loaded
- **Severity:** **Major** (duplication / drift risk)
- **v6.0 action:** Drop `_BUILTIN_SPECS` or reduce to minimal emergency fallback when YAML missing

### Orphan module candidates

- **`feedback.py`:** **NO** `from devolaflow.feedback` in `src/` (only `tests/`). Major if intended as first-class API
- **`compressor.py`:** Imported from `tests/` and `benchmarks/devolaflow_context/evaluator.py`, not from core `src/`
- **`init_project`:** Entry via `pyproject.toml` console script only

### TODO/FIXME/XXX/HACK markers

**0 matches** across `src/devolaflow/**/*.py` — clean codebase.

## 3. Code Complexity Hotspots (>50 lines)

| Rank | Function | File:lines | ~Length | Complexity hints |
|------|----------|------------|---------|------------------|
| 1 | `evaluate_gate_with_nines` | `gate/scorer.py:527-602` | ~76 | `warnings.warn`; multiple `if` / `try`/`except ImportError`; optional NineS path |
| 2 | `score_acceptance_readiness` | `gate/scorer.py:159-225` | ~67 | Several `return` branches; list comprehensions; threshold/fail paths |
| 3 | `generate_markdown_report` | `gate/reporter.py:94-160` | ~67 | `if history` table loop; iteration over `check_results` |
| 4 | `select_context` | `task_adaptive_selector.py:280-350` | ~71 | Budget arithmetic; optional learnings/advisor assembly |
| 5 | `run_self_improve_loop` | `nines/researcher.py:353-416` | ~64 | Sequential steps with early returns on empty CLI results |

**Runner-up:** `_evaluate_convergence` (`gate/scorer.py:462-524`, ~63 lines) — multiple `if` branches (pass / max rounds / stagnation / fail).

## 4. MVP-SKILL.md Deprecation Status (CHANGELOG 5.4.1)

CHANGELOG marks MVP-SKILL.md deprecated with removal "future release". **Active references** still present:

| Severity | Evidence |
|----------|----------|
| Major | `README.md:62`, `README.md:321` |
| Major | `workflow-system/human/en/quickstart.md:48`, `workflow-system/human/zh/quickstart.md:48` |
| Major | `workflow-system/human/demo/index.html:49` |
| Major | `scripts/generate_human_docs.py:162`, `:1146` |
| Minor | `workflow-system/agent/knowledge/reference-dependencies.yaml:52`, `:230` |
| Minor | `doc/designs/design_release_workflow.md:54`, `:61`, `:126` |
| Minor | `.github/PULL_REQUEST_TEMPLATE.md:26` |
| Minor | `scripts/build-site.sh:29` |

**v6.0 action:** Delete MVP-SKILL.md file + sweep all references.

## 5. Schema Duplication

| Duplicate / parallel concept | Where | Notes |
|---------------------|--------|------|
| Dispatch header | `task-dispatch.schema.yaml` `header.*` vs `lean-dispatch.yaml` `hdr` | Same concepts (`dispatch_id`, `parent`, `layer`), different shapes |
| Reinforcement | `task-dispatch.schema.yaml` `applicable_rules.reinforcement` vs `lean-dispatch.yaml` `reinforce` | Two naming schemes (`reinforcement`/`reinforce`; `severity`/`sev`) |
| Acceptance / quality bar | `task-dispatch.schema.yaml` `acceptance.*` vs `lean-dispatch.yaml` `accept` + `gate` | Criteria duplicated |
| **Verification (v5.4.0)** | `task-dispatch.schema.yaml` `verification_config` vs `lean-dispatch.yaml` `verify_cfg` vs `gate-report.schema.yaml` `user_facing_verification` | **Three representations** of one verification story |

**Severity:** Major for verification + reinforcement naming (highest drift risk).

**v6.0 action:** Define single canonical model (JSON Schema or pydantic) and generate lean/verbose views; OR add schema test asserting field parity.

## 6. Coverage Gaps (why low, fixability)

| Module | Coverage | Why low | Fixability |
|--------|-----------|---------|------------|
| `cli.py` | 49% | Thin facade over `sys.argv`, `sys.exit`; only `version_cmd` + partial `validate_template_cmd` exercised | **High** — parametrized tests with `monkeypatch` |
| `init_project.py` | 59% | `main()` branches (`--list`, missing SKILL, `all` target, auto-detect) | **High** — `tmp_path` + monkeypatch |
| `template_engine/composer.py` | 66% | Dataclass operators + `_walk`; rarely-hit branches | **Medium** — targeted tests per operator |
| `check_drift.py` | 73% | Integration-dependent; error path (`yaml.YAMLError`) untested | **Medium** — fixture temp trees |
| `nines/_cli.py` | 76% | Subprocess failure modes; partially tested via mocks | **Medium** — direct unit tests for uncovered branches |

## 7. Rule Rot (`.cursor/rules/*.mdc`)

| Severity | Evidence | Issue |
|----------|----------|------|
| Major | `change-process-rules.mdc:19` **CP-3** | Still lists `CLAUDE.md` (frontmatter + banner + body) as version locations; root `CLAUDE.md` (v5.4.2) has no `version:` frontmatter |
| Minor | `skill-format-rules.mdc:16-23` **SF-3** | Lists 7 locations, omits root `CLAUDE.md` — **inconsistent with CP-3's longer list** |
| Minor | Root `CLAUDE.md:37` | Says "11 locations" while SF-3 lists 7 — internal counting inconsistency |

**v6.0 action:** Reconcile CP-3, SF-3, and CLAUDE.md to one authoritative version-touchpoint list.

## v6.0.0 Tech Debt Candidates (Prioritized)

| ID | Title | Severity | Effort | Measurable improvement |
|----|-------|----------|--------|-------------------------|
| **TD-1** | Remove `evaluate_gate_with_nines` / gate `run_nines_advisor` usage & exports | Major | M | 0 DeprecationWarning in gate path; simpler gate API |
| **TD-2** | Eliminate `_BUILTIN_SPECS` duplication; `plugins.yaml` single source | Major | S | −~60 LOC; no spec drift |
| **TD-3** | MVP-SKILL.md removal + replace all links/docs/site/PR | Major | M | 0 grep hits for `MVP-SKILL` |
| **TD-4** | Unify verification + reinforcement fields across 3 schemas | Major | L | One parity test; fewer drift bugs |
| **TD-5** | CLI + `check_drift` + `init_project` branch tests → 80%+ per module | Critical (CP-2) | M | `cli.py`/`check_drift.py` ≥80% |
| **TD-6** | Refresh `.cursor/rules` version-location text | Major | S | 0 contradictory maintainer instructions |
| **TD-7** | Decide fate of `feedback.py` in-repo API (wire into product or document as external) | Major/Minor | S–M | Clear import graph |

### Top-5 Priority

1. **TD-4** — Schema/lean/gate verification alignment (highest structural payoff)
2. **TD-1** — Finish NineS/gate deprecation (explicit v6.0 promise)
3. **TD-3** — MVP-SKILL removal sweep (user-visible consistency)
4. **TD-2** — Plugin loader deduplication (cheap, removes drift)
5. **TD-6** — Rules reconciliation (cheap, reduces process bugs)
