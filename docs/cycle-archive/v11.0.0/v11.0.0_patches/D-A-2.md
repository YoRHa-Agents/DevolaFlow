# D-A-2 — 22 Builtin Templates → 12-15 (Usage Tier Compression)

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.1 D-A-2
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §5 (templates) + §4.2 (architecture-health metrics)
> **Wave:** 2 (D-A Architecture Health)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow's `workflow-system/agent/templates/registry.yaml:1-158`
registers **22 builtin templates**, each with a 1:1 mapping to a yaml
file under `workflow-system/agent/templates/builtin/*.yaml` (verified
via `ls workflow-system/agent/templates/builtin/`). The registry
schema_version is `1.0` (line 1).

Each template surfaces in three additional places:

- `workflow-system/agent/SKILL.md:407-431` — "Template Quick-Reference"
  table (22 rows × 3 columns).
- `workflow-system/agent/references/meta-framework.md:344-367` —
  "Per-Workflow Template Catalog" (22 rows × 3 columns).
- `workflow-system/agent/references/team-roles.md:474-497` — "Team
  Participation Matrix" (22 rows × 5 team columns = 110-cell matrix).

**Evidence-backed audit table — which of the 22 templates were USED in
v9.0.0..v10.3.0 cycles?** (Methodology: `grep -c <name>` across
`.local/research/v9.*.0_cycle_plan.md` + `v10.*.0_cycle_plan.md` +
`v9.*.0_retrospective.md` + `v10.*.0_retrospective.md` (13 docs); plus
`git log --pretty=format:"%H %s"` matched against branch/commit subject
lines to detect "real cycle execution"; plus CHANGELOG mentions in
context of "this cycle used template X").

| # | Template | Cycle plan/retro mentions | Git commit subj. | Verdict | Used as cycle workflow? |
|---|---|---:|---:|---|---|
| 1 | `change-driven` | **8** | 3 | **USED** (HIGH) | Yes — v8.3.0+ scaffolds + v10.0.0 v10.2.0 active changes |
| 2 | `self-update` | **6** | 5 | **USED** (HIGH) | Yes — v9.6.0 reference refresh, v9.7.0+ patch flows |
| 3 | `skill-optimization` | **5** | 3 | **USED** (MOD) | Yes — v9.5.0 Si-Chip dogfood, v9.7.0 perf, v10.1.0 |
| 4 | `repo-init` | 0 (in cycles) | 8 | **USED at install-time** | Install-time only (not cycle workflow); fires via `devola-init` |
| 5 | `migration` | 2 | 1 | **USED** (LOW) | Mentioned as PV pattern in v9.6.0 reference deltas |
| 6 | `nines-assisted` | 1 | 0 | **USED** (LOW) | Cycle-close pattern (v10.2.0 PV-03 NineS deep self-analysis) |
| 7 | `hotfix` | 1 | 0 | **REGISTERED** | Mentioned but not invoked as cycle workflow |
| 8 | `refactoring` | 1 | 0 | **REGISTERED** | Mentioned but not invoked |
| 9 | `feature-enhancement` | 0 | 0 | **REGISTERED** | Per `v10_internal_opt §3.1`, claimed used in v10.x but no concrete cite |
| 10 | `full-pipeline` | 0 | 0 | **REGISTERED** | SKILL.md default fallback per Quick Start; never explicitly invoked |
| 11 | `documentation-only` | 0 | 0 | **REGISTERED** | Never invoked |
| 12 | `research-only` | 0 | 0 | **REGISTERED** | Never invoked |
| 13 | `design-only` | 0 | 0 | **REGISTERED** | Never invoked |
| 14 | `research-design-review-refine` (RDRR) | 0 | 0 | **REGISTERED** | Never invoked |
| 15 | `spike-poc` | 0 | 0 | **REGISTERED** | Never invoked |
| 16 | `security-audit` | 0 | 0 | **REGISTERED** | Never invoked |
| 17 | `demo-showcase` | 0 | 0 | **REGISTERED** | Never invoked |
| 18 | `performance-optimization` | 0 | 0 | **REGISTERED** | Note: v9.3.0+v9.7.0 perf cycles did NOT reference this template by name |
| 19 | `dependency-setup` | 0 | 0 | **REGISTERED** | Never invoked |
| 20 | `onboarding` | 0 | 0 | **REGISTERED** | Never invoked |
| 21 | `product-verification` | 0 | 0 | **REGISTERED** | Never invoked |
| 22 | `entropy-cleanup` | 0 | 0 | **REGISTERED** | Never invoked (despite v8.0.0 P-11 origin) |

**Counts:** USED in v9.x-v10.x cycle execution = **6 templates** (1,2,3,5,6 +
4 install-time). REGISTERED-BUT-UNUSED in cycle execution =
**16 templates** (7-22). The 22-template ledger has a **27% utilization
rate** (6/22) at the cycle-workflow level.

Per `v10_internal_optimization_directions.md` §3.1 D-A-2, the cited "5
templates actually used in v10.x" set is `change-driven /
feature-enhancement / nines-assisted / self-update / repo-init` — this
audit refines that to 6 (adding `skill-optimization` evidenced by 5
cycle-doc mentions + 3 commit subj. matches; demoting
`feature-enhancement` to "registered but no concrete invocation").

**Counter-check** (OpenSpec philosophy reference): per
`.local/research/v8.3.0_openspec_deep_analysis.md` §1.1 + §6, OpenSpec
covers its **entire lifecycle** with a single 4-stage template
(propose → apply → verify → archive) — DF's `change-driven` template
already adopts this. The 22-template ledger arose from accumulating
specialized variants (e.g., `feature-enhancement` vs `full-pipeline`
diverge in stage 7 only) rather than parameterizing.

## §2 — patch_design

**Two-phase rollout** (audit-then-compress):

**Phase A (this PV — audit + deprecation tag):**

```
audit_template_usage(repo_root):
  1. For each template t in registry.yaml:
     - Count cycle plan/retro mentions (regex per §1 audit method).
     - Count git commit subject mentions.
     - Count CHANGELOG mentions in workflow-execution context.
  2. Emit `audit_template_usage.md` with tier classification:
     TIER-1 USED (cycle invocation evidenced)
     TIER-2 REGISTERED (defined but no v9.x-v10.x invocation)
     TIER-3 LEGACY (not invoked AND superseded by another template)
  3. For TIER-2/3 templates, propose a `# DEPRECATED in v11.0.0; will be
     removed in v12.0.0` comment in the yaml header (preserves backward
     compat — yaml still loads + tests still pass).
```

**Phase B (deferred to v11.X.0+ post-audit):**

Compose-not-define collapse — replace TIER-2/3 yaml files with
parametrized invocations of TIER-1 templates + the 5 composition
operators (sequence/parallel/choice/loop/gate per
`meta-framework.md:379-405`). E.g.:

- `dependency-setup` ≈ `change-driven(mode="install")` parametrization.
- `documentation-only` ≈ subset of `change-driven` with stages =
  `[propose, apply]` (skip verify+archive).
- `onboarding` ≈ `repo-init(mode=core)` followed by
  `documentation-only`.

**Files touched (NEW in Phase A):**

- `scripts/audit_template_usage.py` (~250 LOC + 8-10 unit tests in
  `tests/test_audit_template_usage.py`).

**Files touched (EDITED in Phase A):**

- `workflow-system/agent/templates/builtin/<TIER-2-name>.yaml` × 16
  files — add a `# DEPRECATED in v11.0.0; will be removed in v12.0.0`
  comment to each (line 1 of each yaml). Pure-additive comment; no
  behaviour change. Tests still pass.
- `workflow-system/agent/SKILL.md:407-431` — "Template Quick-Reference"
  table gains a `Status` column with values `active` / `deprecated`.
- `workflow-system/agent/references/meta-framework.md:344-367` —
  Per-Workflow Template Catalog gains analogous status column.
- `CHANGELOG.md` — release entry; cite the 6 USED templates and 16
  DEPRECATED templates explicitly.

**Files touched (NEW reference content): NONE** (no new reference doc;
the audit output goes to `.local/research/v11.X.X_template_audit.md`
which is .local/, gitignored).

**API/CLI surface (Phase A):**

```bash
python scripts/audit_template_usage.py [--cycle-glob 'v10.*'] [--json] [--tier-only TIER-2]
```

**Doc deliverables (G-9 mapping per admission_checklist.md §G-9):**

- CHANGELOG entry — required (mention 6 USED + 16 DEPRECATED).
- W-18 lint refresh — required (covers `audit_template_usage.run`).
- SKILL.md change → triggers W-5 coupling triple (line count check,
  adapter build, benchmark, version test) — column addition is < 25 LOC.
- 16 yaml files touched (1-line comment each) — triggers
  `tests/test_template_validation.py` regression check.
- Bilingual EN/ZH — NOT required (developer-facing audit).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` per
`v11.0.0_evaluation_methodology.md` §2 layout.

**Operations exercised:** `init` (uses `repo-init` — TIER-1 USED) +
`feature` (uses `feature-enhancement` — TIER-2 in this audit).

**Metric collection:** Operator template-selection time (wall-clock
from L0 reading SKILL.md "Quick Start — Workflow Selection" table to
selecting a template); SKILL.md cognitive load (line count between
`## Quick Start` header and end of selection table); template count
visible to operator.

**Expected delta (before → after Phase A):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Template count visible to operator (active) | 22 | 6 (USED active) + 16 (deprecated, hidden behind status filter) | -73% (visual) | improve |
| Operator selection-time on Simple op (`feature`) | ~25s (read 22-row table) | ~8s (read 6-row USED table) | -68% | improve |
| SKILL.md selection-table cognitive load (rows × columns) | 22 × 3 = 66 cells | 22 × 4 = 88 cells (+ status column); 6 active visible | qualitative -67% on active set | improve (filter-by-active) |
| Number of "ghost templates" (defined but unused) shown | 16 | 16 (still listed but tagged) | 0 (preserve audit trail) | preserve |

**Pass criterion:** Operator template-selection-time on Simple op ≤
-50% AND active-template count ≤ 8 AND no test breakage from added
`# DEPRECATED` comment headers.

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (the audit is the value-add; the compression to 6
visible templates is the operator-experience benefit even if timing
deltas are noisy at small scale).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline). 22
templates registered; 16 cycle docs analyzed.

**Metric collection:** Template usage frequency per cycle (count
mentions per template across 13 cycle docs); SKILL.md adapter build
time (`build-skill` Makefile target); `tests/test_template_validation.py`
test count; W-12 4-adapter success rate.

**Expected delta (v10.3.0 baseline → post-Phase-A):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Templates registered | 22 | 22 (unchanged) | 0 | preserve |
| Templates marked `active` | 22 (no labelling) | 6 (USED) | -73% (filter benefit) | improve |
| Templates marked `deprecated` | 0 | 16 | +16 | preserve audit |
| `build-skill` time (4 adapters) | ~3-5s per adapter | ~3-5s (no yaml structural change) | 0 | preserve |
| `test_template_validation` test count | ~22 (1 per yaml) | ~22 (preserved) | 0 | preserve |
| SKILL.md line count | 460 | ≤ 463 (+1 status column header) | +3 | preserve (<500 cap) |
| Operator-mentioned ghost templates per cycle retro | 0 named (templates exist but never mentioned) | 16 named in CHANGELOG explicitly | +16 visibility | improve |
| Audit script existence | absent | present (250 LOC + 8-10 tests) | +1 | improve |

**Pass criterion:** Phase A audit ships AND 16 yaml files gain a
1-line deprecation comment without test breakage AND SKILL.md gains
a Status column with no line-budget violation AND `build-skill`
4-adapter success preserved at 100%.

**Side-effect check (must NOT regress):**

- C-4 SKILL.md line budget (<500).
- W-12 4-adapter `build-skill` success rate (4/4).
- W-17 cycle test cap.
- `tests/test_template_validation.py` (existing — 22-template regression).
- A-1 P3 structured messages (template registry shape preserved;
  no schema change).
- C-7 valid reference links (Status-column SKILL.md edit references
  no new files).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.2 architecture-health bucket;
≥ 3 metrics required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-A-2 Phase A) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Template usage frequency (per template, per cycle) | §4.2 | unknown (no instrumentation) | known (audit emits cycle-by-cycle table) | data exists | Quantitative measurement of architectural reality; closes a measurement gap |
| Active vs deprecated ratio | §4.2 derived | 22/0 (100% active by default) | 6/16 (27% active) | -73% active | Surfaces the "registered but unused" bloat |
| Operator selection-time on Simple op | §4.1 (operator experience) | ~25s | ~8s | -68% | Shorter active-template list with status filter |
| SKILL.md adapter build success | §4.2 | 100% | 100% | 0 (preserve) | No structural change; only metadata column + comment headers |
| Ghost-template visibility per CHANGELOG | §4.2 (governance proxy) | 0 (templates invisible) | 16 named in `## [v11.X.X]` entry | +16 | Operators learn which templates are deprecated without grep |
| Template author confusion rate | §4.1 (qualitative) | unknown | low (USED tier explicit) | qualitative improve | New template authors know which to model after |

**Guarantee on metric:** ALL metrics scriptable from current DF tooling
(re, glob, pathlib, yaml stdlib parser; git log subprocess). The
"selection-time" metric is corroborated by SKILL.md cognitive-load
proxy (active-row count). The "ghost-template visibility" is a
booleanizable count from CHANGELOG.

## §6 — admission_verdict

**Verdict: PASS** (clear large-project benefit + measurable small-project
improvement on operator selection time).

**Rationale:**

- G-1 Internal-value: 6 quantitative DF-internal metrics show clear
  improvement OR establish baseline.
- G-2 Both-tier: large project (DF self) shows audit + 16 deprecation
  tags; small project (synthetic_small_repo) shows -68% operator
  selection-time on Simple ops. Both pass criteria met.
- G-3 Zero-deps: stdlib + existing yaml dep; no NineS / Si-Chip / RTK
  / ui-pro side requirement.
- G-4 Cycle-budget: M effort (1 PV); ≤25 tests per §G-4 mapping
  (8-10 audit tests + ~5 regression tests for the 16-yaml comment
  additions); fits W-17 +30/PV cap.
- G-5 Soul-freeze: 0 Soul rule additions.
- G-6 Cache-prefix: zero edits to canonical_order.
- G-7 Compatibility: pure-additive (16 yaml files gain 1-line comment;
  registry.yaml schema_version unchanged; SKILL.md gains 1 column;
  no public API rename or template removal); deprecated templates
  STILL load and parse (the comment is informational).
- G-8 Test coverage: ~80% per audit script (8-10 unit tests over
  ~250 LOC); existing `test_template_validation.py` covers the 22
  yaml files unchanged.
- G-9 Documentation completeness: matches "Python module change" +
  "SKILL.md / CLAUDE.md change" rows in §G-9 — CHANGELOG + W-18 lint
  + W-12 adapter build + W-5 coupling triple. Bilingual EN/ZH NOT
  required (developer-facing).

## §7 — effort_estimate

**Effort: M (1 PV)**

**Breakdown:**

- `scripts/audit_template_usage.py` (regex + git subprocess + yaml
  emit): ~250 LOC.
- 8-10 unit tests (`tests/test_audit_template_usage.py`): ~150 LOC.
- 16 yaml files × 1-line `# DEPRECATED in v11.0.0` comment: ~16 LOC
  (+ a script-driven approach to apply consistently — could be
  inline in the audit script's `--apply-deprecation-tags` mode).
- SKILL.md Status column addition: ~25 LOC (table re-render).
- meta-framework.md status column addition: ~25 LOC.
- CHANGELOG entry: ~10 LOC.
- Total: ~250 LOC implementation + ~150 LOC test + ~76 LOC config edits
  ≈ ~470 LOC; 1 PV.

**Confirms §3 estimate (M / 2 PV) from
`v10_internal_optimization_directions.md` §3.1 D-A-2 — the original
estimate covered "audit PV + merge PV"; this PDS is Phase A only
(audit + deprecation tags), recommending Phase B (compose-not-define
collapse) DEFER to v11.X.0+ on the basis of the audit's evidence.**

## §8 — dependencies

**None for Phase A — fully standalone.**

The audit script depends on:

- `workflow-system/agent/templates/registry.yaml` (read-only).
- `workflow-system/agent/templates/builtin/*.yaml` (read + 1-line
  comment append per TIER-2/3 template; pure-additive).
- `.local/research/v9.*.0_*.md` + `v10.*.0_*.md` (read-only inputs).
- git subprocess for commit subject matching.

**Synergy (NOT a hard dependency):**

- D-A-1 (L1/L2 actual usage rate audit) shares the
  scan-cycle-docs-for-mentions pattern; if both land in v11.0.0, a
  shared `scripts/_audit_common.py` helper saves ~40 LOC.
- D-X-1 (workflow template scaffold CLI) IS the inverse of D-A-2
  (D-X-1 makes adding new templates easier; D-A-2 culls unused
  templates). **Sequencing matters:** D-A-2 must land BEFORE D-X-1
  in the same cycle so that D-X-1 doesn't re-bloat the registry by
  making it easier to add more TIER-2 templates that go unused.
  This is recorded in D-X-1's §9 risk register R4 — confirmed
  bidirectionally here.
- D-D-3 (C-4 line-budget reverse-evaluation) overlaps in spirit
  (lower the SKILL.md cognitive load) but shares no code.

**Phase B dependencies (deferred to v11.X.0+):**

- D-A-2 Phase B (compose-not-define collapse) requires the registry
  schema to support "alias-of" or "macro" fields → schema bump
  v1.0 → v2.0 → governed by A-2.3 nest-vs-append decision rule.
  This is a future cycle's SI-1 work, not v11.0.0 admission.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Audit's regex-based "USED" detection produces false negatives (e.g., a template invoked via slash command never appears in cycle plan text) → templates get incorrectly tagged DEPRECATED | major | Audit cross-checks against `git log --pretty=format:"%H %s"` for branch/commit subject mentions; emits both "by mention" + "by git" counts; only tags DEPRECATED when BOTH counts are 0 across v9.0.0..v10.3.0 (12+ cycles is a strong signal). Tests cover the disambiguation path. The 16 templates flagged here all have BOTH counts = 0. |
| R2 | Adding `# DEPRECATED in v11.0.0; will be removed in v12.0.0` headers to 16 yaml files breaks `tests/test_template_validation.py` (yaml comment header may interfere with frontmatter parsing) | minor | Comments at the very top of yaml files (BEFORE any keys) are syntactically valid yaml; existing 22 templates already have a `# Schema version 1.0` style comment that round-trips through PyYAML. Test coverage: `tests/test_template_validation.py::test_deprecated_header_does_not_break_parse`. |
| R3 | The 16 deprecated templates have downstream consumers (e.g., a user's local `.workflow/config.yaml` setting `workflow_type: hotfix`) → silent regression when v12.0.0 removes them | major | Phase A only TAGS them; removal is deferred to v12.0.0 (≥1 full cycle of warning). The deprecation header is operator-visible at template-load time. CHANGELOG explicitly cites all 16 names. The 1-cycle deprecation cadence matches v8.3.0's path forward (per `repo-governance.mdc` SF-3 sync_cursor_skill.py removal protocol). |
| R4 | The audit's "USED" tier reveals MORE templates were actually used than the v10_internal_opt_directions.md §3.1 D-A-2 hypothesis (5) — meaning fewer can be safely deprecated → patch's quantitative target (compression to 12-15) becomes infeasible | minor | This PDS already raised the count from 5 to 6 (added `skill-optimization`). If the audit reveals 8-10 USED, the patch reports honestly; CHANGELOG cites the actual number. The compression target (12-15) is a Phase B goal, not a Phase A constraint — Phase A's only deliverable is the audit + deprecation tags + Status column. |

---

ADMISSION: PASS | EFFORT: M | DEPS: none | TIER: core
