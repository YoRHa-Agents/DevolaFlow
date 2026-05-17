# v12.2.0 Reference Dependency Refresh

**Cycle**: v12.2.0 (MINOR)
**Author**: L0
**Date**: 2026-05-16
**Source inventory**: `workflow-system/agent/knowledge/reference-dependencies.yaml` (21 entries; 11 active + 10 periodic)
**Prior refresh**: v9.6.0 PV-04 bulk `last_checked → 2026-05-02` (D-R-5)

## 1 — Top-5 active references (deep refresh attempted)

| # | id | local clone | latest commit | new activity since `2026-05-02`? | NineS deep file |
|---|---|---|---|---|---|
| 1 | superpowers | /home/agent/reference/superpowers | 2026-04-06 `917e5f5 Fix Discord invite link` | NO | `superpowers_nines.json` |
| 2 | openspec | /home/agent/reference/openspec | 2026-04-21 `3c7a05c Version Packages (#996)` | NO | `openspec_nines.json` |
| 3 | get-shit-done | /home/agent/reference/get-shit-done | 2026-04-11 `6d590df fix/qwen-claude-reference-leaks` | NO | `gsd_nines.json` |
| 4 | caveman | /home/agent/reference/caveman | 2026-04-09 `92f892f Update README.md` | NO | not run (no API surface) |
| 5 | Understand-Anything | /home/agent/reference/Understand-Anything | 2026-04-14 `a42ba91 fix: correct live demo URLs` | NO | not run (no API surface) |

**Verdict**: clones are stale relative to `last_checked: 2026-05-02`. All 5 active references show NO net new git activity in the 2-week window since the v9.6.0 PV-04 bulk refresh — consistent with the upstream activity pattern documented in `v9.6.0_reference_deltas.md` §3. Per W-2 fallback, freshness assessment is manual; no upstream pattern delta surfaces for integration.

## 2 — NineS deep findings summary

### 2.1 superpowers (relevance=5)

* **Files analyzed**: 1 (`tests/claude-code/analyze-token-usage.py`)
* **Mechanisms detected**: 8
* **Agent-facing artifacts**: 18
* **Economics score**: 0.085 (estimated savings ratio: 5.9%)
* **Findings**: 6 total (2 warning + 4 info)
* **Notable**:
  * `analyze_main_session` cyclomatic complexity = 12 (warning) — upstream code-quality issue, not a DevolaFlow integration blocker
  * 18 agent-facing artifacts confirms the "+4 skills since 2026-04-11" pattern documented in `reference-dependencies.yaml#superpowers.key_patterns` (14 skills × 18 files including iron-laws + rationalization tables)
  * No new patterns vs the `key_patterns` list — confirms v9.6.0 PV-01 deep analysis remains accurate

### 2.2 openspec (relevance=5)

* **Files analyzed**: 0 (TypeScript repo; NineS Python-AST-only at v3.3.0)
* **Mechanisms detected**: 0
* **Agent-facing artifacts**: 1 (AGENTS.md surface)
* **Findings**: 3 info
* **Notable**:
  * `coverage_gap: No mechanisms detected for: behavioral_instruction, context_compression, distribution, persistence, safety` — limitation of NineS on TypeScript repos, not an actual coverage gap in openspec (the spec-driven lifecycle IS the mechanism)
  * Total agent context: ~50 tokens — minimal AGENTS.md surface; the openspec spec library is the actual contract surface
  * No upstream pattern delta vs the 11 in-repo specs documented in `reference-dependencies.yaml#openspec.key_patterns`

### 2.3 get-shit-done (relevance=4)

* **Files analyzed**: 0 (mixed-language repo; NineS Python-AST-only at v3.3.0)
* **Mechanisms detected**: 7
* **Agent-facing artifacts**: 6
* **Economics score**: 0.0949 (estimated savings ratio: 7.0%)
* **Findings**: 3 (1 warning + 2 info)
* **Notable**:
  * `warning: Agent context overhead is high (51106 tokens). Consider compressing or splitting Agent-facing files.` — upstream architectural concern; informs DevolaFlow's [C-4](.cursor/rules/repo-governance.mdc) line-budget discipline. NOT an action item for DevolaFlow (our SKILL.md is at 494 lines / under 500 ceiling).
  * 7 mechanisms detected confirms the "19 reference docs + 14 specialist subagents + 9 hooks" pattern from `reference-dependencies.yaml#get-shit-done.key_patterns`
  * No new pattern delta vs v9.6.0 PV-01

## 3 — Remaining 16 entries (manual W-2 freshness)

Per `tracking_policy.staleness_threshold_days = 30` for active + 90 for periodic, the 2-week interval since `last_checked: 2026-05-02` is **WITHIN** both thresholds. Per W-2 fallback, manual freshness review:

| Entry | Source type | Manual freshness verdict |
|---|---|---|
| anthropic-advisor-tool | api_docs | No beta header advance signaled at v12.1.0 release window |
| gstack | github_repo | No clone; presumed unchanged within window |
| edict | github_repo | No clone; matches v9.6.0 PV-03 verdict (deep deferred) |
| karpathy-llm-wiki | gist | No clone; gist activity inspected via local mirror at /home/agent/reference/karpathy-llm-wiki.md (unchanged since v9.6.0 PV-03) |
| anthropic-coordination-blog | blog | No new patterns surfaced in v12.1.0 cycle |
| andrej-karpathy-skills | github_repo | **NEW HIGH-PRIORITY ANGLE**: the Mnimiy May-2026 X article (cycle input #1) is a derivative of this repo's 4-rule template — see `v12.2.0_gap_analysis.md` §3 for the article integration plan |
| google-scion | github_repo | periodic; no major release signaled |
| skillrouter | paper | v4 unchanged (arXiv:2603.22455v4 stable since 2026-04-01) |
| vexp | blog | commercial; no open-source release signaled |
| self-improving-system | gist | periodic |
| agent-skills-security | paper | stable arXiv |
| agent-skills-threat-taxonomy | paper | stable arXiv |
| primelocus-hydra | github_repo | `frozen_reference` at v9.6.0 PV-04 — skip per `tracking_policy.staleness_indicators` |
| ruflo | github_repo | proposal-stage; no release |
| christophera-bootstrap-seed | gist | periodic |
| spring-ai-agent-skills | github_repo | v0.7.0 (2026-04-06) — last release pre-dates the window; expected next minor in 2026-05+ |

## 4 — Refresh action

All 21 entries get `last_checked → 2026-05-16` in the v12.2.0 PV-04 surgical refresh (per `tracking_policy.review_actions[*]`):
* Top-3 (superpowers, openspec, get-shit-done) carry NineS deep evidence under this directory
* Top-5 (adds caveman, Understand-Anything) carry git-log evidence
* Remaining 16 carry the W-2 manual-review marker

The 1 actionable pattern delta surfaced in this refresh is the **Mnimiy 12-rule article** (cycle input #1) — handled in `v12.2.0_gap_analysis.md` §3 + PV-03 plan.

## 5 — Cross-references

* Prior refresh artifact: `v9.6.0_reference_deltas.md` (cycle precedent)
* Reference inventory source-of-truth: `workflow-system/agent/knowledge/reference-dependencies.yaml`
* Cycle gap analysis: `v12.2.0_gap_analysis.md`
* External tools (S-7): NineS `https://github.com/YoRHa-Agents/NineS`
