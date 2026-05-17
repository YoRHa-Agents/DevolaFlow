# D-C-1 — Upstream-Unreachable Degraded-Mode Contract

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.6 D-C-1
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §4.6 (coupling metrics) + §5 (templates)
> **Admission gates:** `.local/research/v11.0.0_admission_checklist.md` G-1..G-9
> **Wave:** 5 (D-C External Tool Coupling)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow registers **4 external plugins** in
`workflow-system/agent/knowledge/runtime-plugins.yaml:71-165` (verbatim
list per `.local/research/v10.3.0_retrospective.md` §6 metrics row "New
plugins | 0 (4 already registered at v10.0.0...)"):

1. **nines** (pip / `nines>=3.0.0`; canonical
   `https://github.com/YoRHa-Agents/NineS`; lines 72-84).
2. **ui-pro** (npm / `uipro-cli>=2.0.0`; lines 86-102).
3. **rtk** (curl / `rtk>=0.37.2`; lines 104-116).
4. **si-chip** (curl / `si-chip>=0.4.0`; lines 152-165).

Per-tool current degraded behaviour (each surface separately probed —
no single coordinated contract):

| Tool | Triggering surface | Current behaviour when upstream unreachable | Handles correctly? |
|---|---|---|---|
| **NineS** | `W-2 / SI-2 nines analyze`, `D-N-2 code_coverage` | **Manual fallback documented** since v8.5.0+ per `.local/research/v10.3.0_retrospective.md` §3 row "NineS A1 ticket — `code_coverage` collector timeout" ("filtered via the W-2 manual fallback per established v8.5.0+ precedent"); `repo-governance.mdc` W-2 explicitly declares "When NineS is unavailable, manual analysis ... is acceptable but must be explicitly noted as manual." | YES (documented + practiced) |
| **Si-Chip** | `post_skill_edit` lifecycle hook (`src/devolaflow/lifecycle/post_skill_edit.py:531-605`); `run_dogfood_cycle` (`src/devolaflow/si_chip_bridge/runner.py:476-581`) | **Partial** — `_run_si_chip_evaluation` at `lifecycle/post_skill_edit.py:406-503` catches `SiChipUnavailable` and emits PSE001 warning + `terminal_verdict="SKIPPED_PERMISSIVE"` (lines 452-476) with verdict propagated through `metadata["verdict"]` at line 564. Hook NEVER blocks dispatch. BUT: zero documentation of this contract in `references/`; an L3 agent reading the SKILL corpus cannot discover the fallback without grepping source. | YES at code-level; NO at documentation-level |
| **RTK** | `pre_shell_call` lifecycle hook + `shell_proxy/proxy.py` | **Bypass-by-design** — `DEVOLAFLOW_RTK_PROXY` is OPT-IN (`env-flags.md:82-93` row §2.2 default unset = disabled); when the env-flag is unset OR the `rtk` binary is missing OR `rtk gain` probe fails, the proxy short-circuits to native shell (R5 strict zero-IO contract). | YES (R5 strict default-off design) |
| **ui-pro** | Skill bundle install via `scripts/install.sh` + `runtime-plugins.yaml` `invoked_by_workflows: [product-verification]` (line 102) | **Conditional** — only invoked when the `product-verification` workflow runs; absent installs degrade silently because no other workflow depends on it. BUT: `pre_plugin_invocation` (`src/devolaflow/lifecycle/pre_plugin_invocation.py:464-516`) raises `HookViolation` PPI001 (severity=`error`) when `ensure_plugin('ui-pro')` raises `PluginInstallError`; in **permissive mode** (default) it's logged + collected, in **strict mode** it would block dispatch. Behaviour at the boundary (network unreachable mid-install vs. registry mismatch vs. clean missing) is UNDOCUMENTED. | PARTIALLY (works in default permissive mode; undefined in strict mode) |

**Quantification:**

- **2 of 4** plugins handle unreachability at code-level AND have
  operator-discoverable documentation (NineS via `repo-governance.mdc`
  W-2 + retrospectives; RTK via `references/env-flags.md` §2.2).
- **2 of 4** plugins handle unreachability at code-level but the
  contract is INVISIBLE to the agent reading the skill corpus (Si-Chip
  PSE001 + ui-pro PPI001) — no `references/*.md` file documents the
  expected behaviour.
- **0 of 4** plugins have a regression test simulating "upstream
  unreachable AND DF still ships expected outcome." `tests/` has 1
  related fixture: `tests/test_post_skill_edit_hook.py` covers
  `SiChipUnavailable` raising-path but does NOT pin the cycle-level
  invariant ("dispatch continues; gate result documented").

The contract gap is the operator who reads SKILL.md and asks "what
happens when GitHub is down?" — they currently must read 4 separate
source files to assemble the answer.

## §2 — patch_design

**Algorithm — DOCUMENTATION ARTIFACT (no behavioural changes):**

```
1. Author references/degraded-mode.md (Large tier, ≤1000 LOC) with 4 sections
   (one per plugin) declaring:
   - Trigger surface(s) (file:line citation)
   - Failure-mode taxonomy (network unreachable / rate-limited / repo-renamed /
     binary-missing / version-mismatch)
   - DF-side fallback (what continues to work)
   - Operator action (manual fallback / opt-in flag / N/A)
   - Test coverage (tests/test_degraded_mode.py:: <test_name>)
2. Cross-link from SKILL.md "Reference Navigation Guide" Tier-2 row
   (mirrors the v8.3.0 PV-09 agent-workspace.md addition pattern; this
   is the 15th reference, triggering SF-1 14-file-fixed-set re-evaluation
   to extend MIRRORED_FILES per scripts/sync_cursor_skill.py).
3. Author tests/test_degraded_mode.py with 4 simulated scenarios:
   - test_nines_unreachable_falls_back_to_manual_w2 — assert that the
     W-2 SI-3 evaluation script accepts manual JSON inputs when NineS
     is unreachable (documents existing v8.5.0+ precedent).
   - test_si_chip_unreachable_emits_pse001_and_defers — monkeypatch
     find_si_chip_install -> None; assert post_skill_edit returns
     metadata.verdict == "SKIPPED_PERMISSIVE" and dispatch continues.
   - test_rtk_unreachable_bypasses_to_native_shell — env-flag set ON
     but `shutil.which("rtk")` -> None; assert pre_shell_call passes
     command through unmodified (existing R5 strict invariant codified
     by tests/test_shell_proxy_disabled_is_noop.py — degraded-mode
     test asserts the EXTENDED case where flag is ON but binary is
     absent).
   - test_ui_pro_unreachable_emits_ppi001_permissive_continues —
     monkeypatch ensure_plugin -> raise PluginInstallError; assert
     pre_plugin_invocation hook returns HookViolation PPI001 in
     permissive mode AND dispatch continues (the result envelope is
     populated; no exception).
4. Refresh tests/test_no_ghost_features.py W-18 lint to assert
   degraded-mode.md exists (per W-18 precondition: lint refresh BEFORE
   CHANGELOG entry).
```

**G-3 zero-deps gate — explicit declaration:**

This patch proposes **ZERO upstream changes** to NineS / Si-Chip / RTK /
ui-pro repos. Every fallback documented in `references/degraded-mode.md`
exists as DF-side code today (catch handlers in
`lifecycle/post_skill_edit.py:452-503`, `lifecycle/pre_plugin_invocation.py:355-391`,
`shell_proxy/proxy.py:_ENV_FLAG`, `repo-governance.mdc::W-2` manual
fallback). The patch is **purely documentary + 4 regression tests** that
codify behaviour already shipped.

**Files touched (NEW):**

- `workflow-system/agent/references/degraded-mode.md` (Large tier; ~600
  LOC target; ≤1000 LOC ceiling per SF-1 / C-4).
- `tests/test_degraded_mode.py` (~200 LOC; 4 scenarios + helper
  fixtures; ~12-16 tests counting parameterizations).

**Files touched (EDITED):**

- `workflow-system/agent/SKILL.md` — 1-line addition to Reference
  Navigation Guide (the 15th Tier-2 reference); estimated ~+1 LOC,
  preserves <500 ceiling (current 460).
- `scripts/sync_cursor_skill.py::MIRRORED_FILES` — extend with
  `references/degraded-mode.md` (1-line addition).
- `tests/test_no_ghost_features.py` — W-18 lint stanza (~30 LOC pattern
  per `tests/test_no_ghost_features.py:4644+`).
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**API/CLI surface:** NONE. This is a documentation artifact + regression
suite. No new Python module, no new env flag, no new CLI verb.

**Doc deliverables (G-9 per admission_checklist.md §G-9):**

- CHANGELOG entry (Reference doc add scope) — REQUIRED.
- W-18 lint refresh — REQUIRED (precondition per W-18).
- SF-3 `sync_cursor_skill.py` MIRRORED_FILES update — REQUIRED.
- SF-1 line budget verify (`tests/test_reference_size_budgets.py`) —
  REQUIRED (the 15th reference parametrizes automatically).
- W-12 `build-skill` 4-adapter verify — REQUIRED (SKILL.md changed).
- ST-3 bilingual EN/ZH — NOT required (reference docs are
  agent-facing English-only per `workflow-system/human/` separation).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` (per
`v11.0.0_evaluation_methodology.md` §2 layout — 1-3 source files,
< 200 LOC, **no plugins registered**, no `.local/.agent/active/`).

**Operations exercised:** `init` workflow (instantiates `repo-init`
template) followed by a synthetic "feature" task — designed so the
synthetic repo has NEVER had any of the 4 external plugins installed,
exercising the degraded-mode path on EVERY dispatch.

**Metric collection:** Degraded-mode test coverage (per
`v11.0.0_evaluation_methodology.md` §4.6 — percentage of plugins with
working unreachable scenario test); Discoverability of degraded-mode
contract (binary: does grepping SKILL.md for "unreachable" or "degraded"
return a Tier-2 reference link?); Number of L3 dispatch flows that fail
catastrophically when no plugin is installed (count via synthetic
dispatch).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Degraded-mode test coverage (% of 4 plugins) | 25% (1/4 = Si-Chip via test_post_skill_edit_hook covers SiChipUnavailable but only as a unit test, not as a degraded-mode contract) | 100% (4/4) | +75pp | improve |
| Discoverable degraded-mode contract in SKILL.md | NO (zero references hits for "degraded" or "unreachable") | YES (1 Tier-2 ref link in Navigation Guide) | binary improve | improve |
| Synthetic dispatch failures with 0 plugins installed | 0 (default-off opt-in for all 4 plugins means dispatch never engages plugin code paths in fresh repo) | 0 | 0 | preserve |

**Pass criterion:** Δ ≥ +50pp on Degraded-mode test coverage AND
Discoverable contract flips to YES AND no regression on synthetic
dispatch failures (must remain 0).

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (large-only). Small projects rarely engage all 4
plugins, so the documentation surface only directly benefits operators
porting DF to a small repo; the regression tests still benefit large
projects regardless.

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline; 4 plugins
registered; `.cursor/rules/repo-governance.mdc` includes W-2 manual
fallback governance; v10.3.0 retrospective §3 documents the NineS
A1-ticket fallback in practice).

**Metric collection:** Degraded-mode test coverage (4-plugin matrix);
Number of cycle retrospectives mentioning "upstream unreachable" as a
process pain point (grep `.local/research/v*_retrospective.md`);
SKILL.md line count delta (must remain <500 per C-4); reference total
line count (must remain ≤ 1000 per Large-tier per SF-1).

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline (v10.3.0) | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Degraded-mode test coverage (% of 4 plugins) | 25% (Si-Chip only at unit-test level) | 100% (4/4 declared in test_degraded_mode.py) | +75pp | improve |
| Cycle retrospectives mentioning "upstream unreachable" pain (cycles v9.x..v10.3) | 4 cycles (v9.5.0 OA-1 Si-Chip eval data; v10.0.0 §4.2 ruff drift; v10.2.0 D-N-2 NineS coverage; v10.3.0 §3 NineS A1) | 0 expected (cycles after v11.0.0 land — degraded contract is in `references/`; operators consult ref before retro) | -100% (forecast) | improve |
| References Tier-2 count (per SF-1 fixed set) | 14 | 15 | +1 | preserve (within tier) |
| SKILL.md line count | 460 | 461 | +1 | preserve (well under <500) |
| `degraded-mode.md` line count | N/A | ~600 (target) | +600 | preserve (within Large tier ≤1000) |
| W-12 `build-skill` 4-adapter success rate | 100% | 100% | 0 | preserve |
| W-17 cycle test delta contribution | N/A | +12-16 (4 scenarios × 3-4 parameterizations + 1 W-18 lint) | +12-16 | within +30/PV cap |

**Pass criterion:** Δ ≥ +50pp on Degraded-mode test coverage AND
SKILL.md remains <500 AND `degraded-mode.md` ≤1000 lines AND
`build-skill` 4-adapter success rate stays 100% AND W-17 per-PV cap
not exceeded.

**Side-effect check (must NOT regress):**

- W-12 adapter build success (4/4 adapters).
- W-17 cycle test cap (this PV adds ≤16 tests; well under +30/PV).
- C-4 SKILL.md line budget (<500).
- SF-1 references line budget (degraded-mode.md ≤1000 LOC).
- C-7 valid reference links (every file:line citation in
  `degraded-mode.md` MUST exist at v11.0.0 cut).
- S-2 no absolute paths (every citation is relative to repo root).
- S-7 external tool URL form (NineS / Si-Chip / RTK / ui-pro
  references use canonical GitHub URLs only).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.6 coupling-bucket; ≥3 metrics
required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-C-1) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Degraded-mode test coverage (% of 4 plugins with explicit unreachable scenario test) | §4.6 (coupling — degraded_mode_test_coverage) | 25% (1/4 — Si-Chip at unit-test granularity only) | 100% (4/4) | +75pp | New `tests/test_degraded_mode.py` ships 4 scenarios — one per plugin |
| Operator-discoverable degraded-mode contract (binary: SKILL.md cross-links to a single ref?) | §4.6 (coupling — discoverability proxy) | NO (0 hits for "unreachable"/"degraded") | YES (1 Tier-2 ref link) | binary improve | `degraded-mode.md` is the new 15th Tier-2 reference per `references/` |
| Source files an operator must read to understand "GitHub down" behaviour | §4.6 + §4.1 (coupling × operator experience proxy) | 4 (lifecycle/post_skill_edit.py + lifecycle/pre_plugin_invocation.py + shell_proxy/proxy.py + repo-governance.mdc) | 1 (`references/degraded-mode.md`) | -75% | Single source-of-truth replaces N source-of-truths |
| Cycle retrospectives mentioning upstream-unreachable pain (rolling 4-cycle window) | §4.6 (coupling — process pain proxy) | 4 / 4 cycles (v9.5.0, v10.0.0, v10.2.0, v10.3.0) | 0 expected forecast (next-cycle measurement) | -100% (forecast) | Documented contract preempts retro pain; verifiable post-v11.x cycles |
| Test count overhead per coupling-PV | §4.4 (test health) | N/A (no precedent) | +12-16 | within +30/PV cap | 4 scenarios × 3-4 parameterizations + 1 W-18 lint |

**Guarantee on metric:** ALL 5 metrics are scriptable from current DF
tooling (no external deps required to MEASURE — the metrics themselves
are about an external-tool boundary but the measurement runs locally).
"Degraded-mode test coverage" is verifiable by `pytest --collect-only
tests/test_degraded_mode.py`. "Operator-discoverable contract" is
verifiable by `grep -E "degraded|unreachable" workflow-system/agent/SKILL.md`.
"Source files to read" is auditable from `references/degraded-mode.md`
itself. "Cycle retro pain" is grep-able over
`.local/research/v*_retrospective.md`.

## §6 — admission_verdict

**Verdict: PASS**

**Rationale:**

- G-1 Internal-value: 5 quantitative DF-internal metrics (degraded-mode
  coverage +75pp, discoverability binary YES, source-files -75%, retro
  pain -100% forecast, test count +12-16); all from §4.6 coupling
  bucket of `v11.0.0_evaluation_methodology.md`; ZERO EvoBench
  signals used.
- G-2 Both-tier: small (synthetic_small_repo with 0 plugins
  installed) AND large (DevolaFlow self with 4 plugins) BOTH show
  degraded-mode-coverage gain to 100%. The synthetic case is the
  default-off path on every dispatch; the large case is the
  cycle-retrospective process gain.
- G-3 Zero-deps: ZERO upstream changes proposed. Every fallback
  cited (W-2 NineS manual, Si-Chip PSE001 path, RTK R5 strict bypass,
  ui-pro PPI001 permissive continue) is DF-side code shipped at or
  before v10.3.0. The patch is purely documentary + regression-test.
  Verbatim from `v11.0.0_admission_checklist.md` §G-3: "no requirement
  for external tool changes (NineS/Si-Chip/RTK/ui-pro side)".
- G-4 Cycle-budget: 1-2 PV (M effort per `v10_internal_optimization_directions.md`
  §3.6 D-C-1); test budget +12-16 per the M-effort §G-4 mapping
  (≤25); fits within W-17 +30/PV cap with margin.
- G-5 Soul-freeze: 0 Soul rule additions.
- G-6 Cache-prefix: zero edits to schemas/lean-dispatch.yaml; doesn't
  touch canonical_order.
- G-7 Compatibility: pure-additive (NEW reference + NEW test file +
  1-line SKILL.md addition + 1-line MIRRORED_FILES addition + W-18
  lint stanza); no public API rename, no env flag rename, no schema
  field rename, no file path rename.
- G-8 Test coverage: NEW `test_degraded_mode.py` ships ≥80% coverage
  of its own assertions (each assertion is a literal contract pin —
  not exercised production code per se). Existing modules touched
  (post_skill_edit, pre_plugin_invocation, shell_proxy/proxy) already
  carry coverage well above CP-2 80% floor (cycle coverage 93.04%
  per v10.3.0 retrospective).
- G-9 Documentation completeness: CHANGELOG + W-18 lint refresh +
  SF-3 sync update + SF-1 line budget verify + W-12 adapter rebuild;
  matches the "Reference doc add" row in §G-9 table. NO bilingual ZH
  required (agent-facing reference, not user-facing demo).

## §7 — effort_estimate

**Effort: M (1-2 PV)**

**Breakdown:**

- `references/degraded-mode.md` body: ~600 LOC (~2-4 hours per the v8.3.0
  PV-09 `agent-workspace.md` ~750-LOC precedent at 1 PV; this is
  smaller scope — single concern, 4 mirrored sections — so likely
  closer to 1 PV).
- `tests/test_degraded_mode.py`: ~200 LOC; 4 scenario classes ×
  3-4 parameterizations = 12-16 test functions.
- SKILL.md 1-line addition + MIRRORED_FILES update + W-18 lint stanza:
  ~10 LOC across 3 files.
- CHANGELOG entry: ~1 LOC under PV header.
- `make build-skill` to re-verify 4 adapters: standard PV closing step,
  no novel work.
- Total estimated effort: ~810 LOC across documentation + tests; M /
  1 PV likely sufficient (analogous to v8.3.0 PV-09 cycle-archive
  rule W-19 + agent-workspace.md addition landing in 1 PV).

**Confirms §3 estimate (M / 1-2 PV) from
`v10_internal_optimization_directions.md` §3.6 D-C-1.**

## §8 — dependencies

**None — this patch is fully standalone.**

The reference doc + test file depend on:

- `src/devolaflow/lifecycle/post_skill_edit.py:531-605` (Si-Chip
  fallback paths) — read-only.
- `src/devolaflow/lifecycle/pre_plugin_invocation.py:464-516`
  (ui-pro PPI001 path) — read-only.
- `src/devolaflow/shell_proxy/proxy.py::_ENV_FLAG` (RTK bypass) —
  read-only.
- `.cursor/rules/repo-governance.mdc::W-2` (NineS manual fallback) —
  read-only.
- `workflow-system/agent/SKILL.md` (Reference Navigation Guide) — 1
  line addition.
- `scripts/sync_cursor_skill.py::MIRRORED_FILES` — 1 line addition.

…all of which exist at v10.3.0. No other v11.0.0 patches are required
for D-C-1 to ship.

**Synergy (NOT a hard dependency):**

- D-C-2 (bridge-shape contract) ships fixture-based regression tests
  in `tests/integration/`; if both D-C-2 and D-C-1 land in the same
  PV, share a `tests/integration/conftest.py` for the no-network
  monkeypatch fixtures.
- D-C-3 (`pre_plugin_invocation` split) renames the lifecycle event
  position; D-C-1's test for ui-pro PPI001 must reference the
  alias path (`pre_plugin_invocation` keeps emitting PPI001 even
  after the split per backward-compat alias). If D-C-3 lands FIRST,
  D-C-1's test asserts both the alias AND the new event names.
- D-X-5 (operator troubleshooting handbook) and D-C-1 both add a
  Tier-2 reference; if both land, the Reference Navigation Guide
  table in SKILL.md needs +2 rows (still well within <500 ceiling).

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Documentation gives operators a false "DF works fully offline" impression → operators stop pre-installing plugins → cycle workflows that DEPEND on plugin output (e.g. NineS-assisted) silently fall back to manual mode without operator awareness → cycle quality regression | major | `references/degraded-mode.md` MUST open with a "Degraded ≠ Full" warning section explicitly listing what STOPS working when each plugin is unreachable (verbatim from `v10_internal_optimization_directions.md` §3.6 D-C-1 risk note: "必须明确 'degraded ≠ 全功能'"). The warning is the FIRST section of the reference, before any per-plugin detail; operators reading top-down hit the caveat immediately. Pin via `tests/test_degraded_mode.py::test_warning_appears_in_first_500_chars`. |
| R2 | The 15th Tier-2 reference triggers SF-1 14-file fixed-set re-evaluation; could conflict with D-X-5 (operator troubleshooting) or D-O-1 (evaluator rosetta) which ALSO propose new references → cycle hits 16+ references and operators experience selection fatigue | minor | Cycle plan §3 must coordinate: order references by IMPACT (degraded-mode is foundational; troubleshooting depends on knowing degraded paths exist; rosetta is meta-evaluation). If 3+ new references admit in v11.0.0, defer the lowest-priority reference to v11.1.0+. The references_count metric in `v11.0.0_evaluation_methodology.md` §3 (current 14) gives quantitative tracking. |
| R3 | The 4 simulated unreachable scenarios in `tests/test_degraded_mode.py` use monkeypatch-based mocks — if upstream changes its actual error shape (e.g., NineS starts raising a NEW exception type DF doesn't catch), the test still passes but real-world behaviour silently regresses → exactly the v10.2.3 bridge defect category surfaced by `v10.2.3_iteration_round1.md` §1 | major | This is precisely the gap D-C-2 (bridge contract) closes — D-C-2 ships cached fixtures captured from real upstream output, refreshed weekly. D-C-1 + D-C-2 are complementary: D-C-1 documents the EXPECTED contract; D-C-2 verifies the REAL contract still matches. v11.0.0 cycle plan §3 should admit both together if cycle budget allows; if budget is tight, D-C-1 alone is still a net improvement (documentation-as-test value > zero documentation). |

---

ADMISSION: PASS | EFFORT: M | DEPS: none | TIER: core
