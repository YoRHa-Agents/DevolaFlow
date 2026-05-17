# D-C-2 — Bridge Layer Version Negotiation Protocol (Shape Contract Tests)

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.6 D-C-2
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §4.6 (coupling — bridge_contract_test_count)
> **Admission gates:** `.local/research/v11.0.0_admission_checklist.md` G-1..G-9
> **Wave:** 5 (D-C External Tool Coupling)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow consumes external tool output through 4 bridge / proxy
surfaces (verbatim from `runtime-plugins.yaml`):

1. **Si-Chip bridge** — `src/devolaflow/si_chip_bridge/runner.py` invokes
   3 Si-Chip CLI scripts (`profile_static.py`, `count_tokens.py`,
   `aggregate_eval.py`) and parses their YAML output via
   `src/devolaflow/si_chip_bridge/models.py::MetricsReport.from_yaml_dict`
   (lines 162-237) and `BasicAbilityProfile.from_yaml_dict` (lines
   78-95).
2. **NineS** — invoked via `nines analyze` / `nines self-eval` shell
   commands; output parsed by external scripts and stored in
   `.local/research/v*_nines.{json,md}`. The bridge surface is
   `scripts/nines_to_sichip_eval_adapter.py` (412 LOC, 23 unit tests
   per `v10.3.0_retrospective.md` §6 metrics) which converts NineS
   JSON output into Si-Chip's runs-dir/baseline-dir layout.
3. **RTK** — `src/devolaflow/shell_proxy/proxy.py` invokes
   `rtk rewrite <cmd>` and consumes its stdout; the command-mapping
   layer at `src/devolaflow/shell_proxy/commands.py` consumes
   `.local/memory/commands/<repo>/<cmd>.yaml` recipes (RTK-rewritten
   by way of v8.3.4 PV-04 layer).
4. **ui-pro** — `uipro-cli` invoked once at install (`uipro init
   --ai cursor --global`) per `runtime-plugins.yaml:90-95`; output
   not parsed (init-only side effect).

**The v10.2.3 bridge defect — the canonical witness:**

`src/devolaflow/si_chip_bridge/models.py::MetricsReport.from_yaml_dict`
historically (pre-v10.2.3) read ONLY top-level keys (`composite`,
`task_delta`, `value_vector`, `C1_metadata_tokens`, `C2_body_tokens`).
Si-Chip v0.1.6+ emits all of these as NESTED keys under
`metrics.task_quality.*` / `metrics.context_economy.*` / `summary.*`
(verbatim from `models.py:107-186` docstring + `v10.2.3_iteration_round1.md`
§1).

The pre-v10.2.3 unit tests in `tests/test_*` used HAND-CRAFTED fixtures
that mirrored the legacy top-level shape — they all passed. The defect
surfaced ONLY when PV-03's end-to-end dogfood pass #2 returned
`composite=0.0` for every probed file → DEFER verdict everywhere
(`.local/research/v10.2.3_iteration_round1.md` §1: "Si-Chip's
`aggregate_eval.py` v0.1.6 emits ALL its MVP-8 metrics under nested
paths ... — the top-level keys are absent. The pre-PV-04 bridge
silently zeroed every score → DEFER on every file."). The PV-04 fix
(now `models.py:187-237`) added nested-path lookup with legacy
fallback, but the DEFECT WAS INVISIBLE TO UNIT TESTS for ~2 PVs.

**The systemic risk this surfaces:**

| Bridge surface | Real upstream emit shape captured? | Test fixture source | Gap |
|---|---|---|---|
| Si-Chip `MetricsReport` | NOW (post-v10.2.3 PV-04, fixture mirrors `.local/dogfood/10.2.1/skill-optimization_after_metrics.yaml`) | Captured from real Si-Chip 0.1.6+ output via `v10.2.3_iteration_round1.md` §1 evidence | NEW shape changes (Si-Chip 0.2.0+) will not be detected until next dogfood pass |
| Si-Chip `BasicAbilityProfile` | NO (synthesised from spec docs per `models.py:78-95` "tolerant of missing keys") | Synthesised | Same risk class as MetricsReport pre-v10.2.3 |
| NineS JSON output | Partial — `nines_to_sichip_eval_adapter.py` has 23 unit tests but the test fixtures are synthesised, not captured-from-real-output | Synthesised | Same risk — NineS V3.4.0+ schema changes would not be caught |
| RTK `rtk rewrite` stdout | NO (the rewrite output shape is consumed verbatim by `shell_proxy/proxy.py`; no contract test) | N/A — passthrough | Same risk if RTK changes its rewrite format |

**Test infrastructure status:**

`tests/integration/` directory **does not exist** at v10.3.0 (verified
via `ls /home/agent/workspace/DevolaFlow/tests/integration/`: "No such
file or directory"). The closest existing test
`tests/test_sichip_iteration_delta_gate.py` covers the
`apply_or_defer` semantic but does NOT pin shape contract — it uses
synthesised `MetricsReport` instances built from raw float deltas
(verbatim per `tests/test_sichip_iteration_delta_gate.py:48-67`):

```python
before = MetricsReport(
    composite=0.5,
    metadata_tokens=0,
    body_tokens=0,
    task_delta=0.0,
    value_vector=0.0,
)
```

So the iteration_delta gate is contract-pinned at the SEMANTIC layer
(threshold > epsilon → APPLY) but NOT at the SHAPE layer (real Si-Chip
YAML must parse without zeroing fields).

## §2 — patch_design

**Algorithm — INTEGRATION TEST INFRASTRUCTURE (no production code change):**

```
1. Create tests/integration/ directory with conftest.py providing the
   shared fixture machinery (fixture-loader helper, monkeypatch for
   network-isolation, deterministic clock).
2. Create tests/integration/fixtures/ directory with one subdir per
   plugin (nines/, si-chip/, rtk/, ui-pro/) containing real-output
   YAML/JSON captured from upstream tools at a pinned version.
3. Author 4 contract test files:
     tests/integration/test_si_chip_shape_contract.py
     tests/integration/test_nines_shape_contract.py
     tests/integration/test_rtk_shape_contract.py
     tests/integration/test_ui_pro_shape_contract.py
   Each file:
     - Loads cached fixture from fixtures/<tool>/.
     - Parses via the production bridge code (e.g., MetricsReport.from_yaml_dict).
     - Asserts the parsed dataclass has expected NON-ZERO field values.
     - Asserts forward-compat (unknown nested keys do not crash).
     - Optionally asserts backward-compat (legacy-shape fixture still parses).
4. Add `make refresh-bridge-fixtures` Makefile target that re-captures
   fixtures from the LIVE installed plugin binaries (gated on plugin
   availability — skips with WARNING if plugin missing, never crashes).
5. Add scripts/refresh_bridge_fixtures.py implementing step 4 (~150 LOC).
6. Wire CI matrix: add a weekly schedule job in .github/workflows/
   that runs `make refresh-bridge-fixtures && pytest tests/integration/`
   (separate from the per-PR CI which uses checked-in fixtures only).
   THE DEFAULT PER-PR PYTEST RUN STAYS UNCHANGED — integration tests
   use checked-in fixtures, no live network requirement.
7. Refresh tests/test_no_ghost_features.py W-18 lint to assert
   tests/integration/ exists and contains the 4 contract test files.
```

**G-3 zero-deps gate — explicit declaration:**

This patch proposes **ZERO upstream changes** to NineS / Si-Chip / RTK /
ui-pro. Fixture creation happens ON THE DF SIDE: an operator with the
plugin installed runs `make refresh-bridge-fixtures` which captures the
plugin's live output and saves it under `tests/integration/fixtures/`.
The captured fixture is checked in to the DF repo. No operator action
is required of any upstream maintainer. Verbatim per
`v11.0.0_admission_checklist.md` §G-3: "no requirement for external
tool changes (NineS/Si-Chip/RTK/ui-pro side)".

**Fixture refresh cadence — design decision:**

Two refresh modes ship simultaneously:

| Mode | Trigger | Frequency | Operator action |
|---|---|---|---|
| **Manual** | `make refresh-bridge-fixtures` | Ad-hoc / on demand | Run when operator notices a plugin upstream version bump |
| **CI weekly schedule** | `.github/workflows/bridge-fixture-refresh.yml` cron `0 0 * * 0` | Weekly (Sunday 00:00 UTC) | Auto-creates a draft PR if fixture diff detected; reviewer approves OR investigates regression |

Per the v10.2.3 retrospective lesson #2 (`v10.3.0_retrospective.md` §4
key-learning #2: "end-to-end tests against real plugin outputs ...
catch defects unit fixtures cannot. Future cycles integrating an
upstream tool should ship at least one fixture *captured from* the
upstream tool's real output"), this patch operationalizes that lesson.

**Files touched (NEW — directory + 9 files):**

- `tests/integration/__init__.py` (1 LOC).
- `tests/integration/conftest.py` (~80 LOC; shared fixture loader +
  network monkeypatch).
- `tests/integration/test_si_chip_shape_contract.py` (~150 LOC; 6-8
  scenarios covering MetricsReport + BasicAbilityProfile parsers).
- `tests/integration/test_nines_shape_contract.py` (~120 LOC; 4-6
  scenarios covering NineS analyze JSON shape + adapter conversion).
- `tests/integration/test_rtk_shape_contract.py` (~80 LOC; 3-4
  scenarios covering rtk rewrite stdout shape).
- `tests/integration/test_ui_pro_shape_contract.py` (~60 LOC; 2-3
  scenarios covering uipro init exit code + log shape).
- `tests/integration/fixtures/si-chip/` (3 YAML files: metrics_report,
  basic_ability_profile, count_tokens output).
- `tests/integration/fixtures/nines/` (2 JSON files: analyze output,
  self-eval output).
- `tests/integration/fixtures/rtk/` (2 text files: rtk rewrite stdout
  for `pytest` + for `git diff`).
- `tests/integration/fixtures/ui-pro/` (1 log file: uipro init success).
- `scripts/refresh_bridge_fixtures.py` (~150 LOC).
- `.github/workflows/bridge-fixture-refresh.yml` (~50 LOC; cron job).

**Files touched (EDITED):**

- `Makefile` — `refresh-bridge-fixtures` target (~5 LOC).
- `tests/test_no_ghost_features.py` — W-18 lint stanza (~30 LOC).
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**API/CLI surface:**

```bash
# Refresh all fixtures (gracefully skips plugins that are not installed)
make refresh-bridge-fixtures

# Refresh fixtures for a single plugin
python scripts/refresh_bridge_fixtures.py --plugin si-chip
python scripts/refresh_bridge_fixtures.py --plugin nines

# Run all bridge contract tests (uses checked-in fixtures; no live network)
pytest tests/integration/ -v
```

**Doc deliverables (G-9 per admission_checklist.md §G-9):**

- CHANGELOG entry (Python module change scope) — REQUIRED.
- W-18 lint refresh — REQUIRED.
- NO new env flag (W-20 reuse-first satisfied; the CI matrix uses an
  existing `GITHUB_TOKEN` for PR creation, no DEVOLAFLOW_* flag added).
- NO SKILL.md change (the integration test infra is purely CI / dev
  tooling; doesn't surface to L0/L1/L2/L3 dispatch).
- NO new reference doc (the test-file docstrings ARE the contract
  documentation; no `references/*.md` addition required).
- Bilingual EN/ZH — NOT required (CI infrastructure is dev-facing).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` (per
`v11.0.0_evaluation_methodology.md` §2 layout — 1-3 source files,
< 200 LOC, no plugins).

**Operations exercised:** None of the 5 §2 operations directly
exercise bridge contract tests (init/feature/bugfix/refactor/docs all
operate on the synthetic repo source code, not on plugin output).
The relevant synthetic operation is **"contract test runs in CI for a
small repo with the DF skill installed"** — i.e., does the integration
test infrastructure cleanly skip / pass when the small repo has no
plugins installed?

**Metric collection:** `pytest tests/integration/` exit code on a
synthetic repo with 0 plugins installed (must be 0 — tests use
checked-in fixtures, no live plugin required); test count overhead
when plugins are absent (must be 0 — fixtures present, tests run);
CI runtime impact (per-PR, not weekly schedule — integration tests
use checked-in fixtures so add ~3-5s to total pytest wall clock).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Bridge contract test count (per `v11.0.0_evaluation_methodology.md` §4.6 metric) | 0 | 16-22 (4 files × 4-6 scenarios) | +16-22 | improve |
| `pytest tests/integration/` exit code on small repo with 0 plugins installed | N/A (dir does not exist) | 0 (fixtures checked in; no live network) | N/A → pass | improve |
| Defects of the v10.2.3-bridge class detectable in CI | 0 (only end-to-end dogfood catches them; that's a separate cycle) | 1 per fixture-shape-mismatch (CI catches at PR-time) | +∞ relative | improve |

**Pass criterion:** Δ ≥ +12 on Bridge contract test count (i.e., ≥3
scenarios per plugin, ≥3 plugins covered) AND `pytest tests/integration/`
exits 0 on small repo without live plugins AND CI runtime impact ≤
+10s per PR.

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (large-only). Small projects without plugins do not
exercise the bridge surface in production; the test infrastructure
benefit is largely realized at large-project scale (where the cost
of a v10.2.3-class defect is multi-PV recovery).

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline; 4 plugins
registered; `si_chip_bridge` package present at
`src/devolaflow/si_chip_bridge/`; `nines_to_sichip_eval_adapter.py`
present in `scripts/`; `shell_proxy/proxy.py` present).

**Metric collection:** Bridge contract test count (per `v11.0.0_evaluation_methodology.md`
§4.6); time-to-detect-shape-defect (PVs from defect introduction to
detection — the v10.2.3 case took 2 PVs (PV-02 introduced, PV-03
surfaced at end-to-end dogfood); contract test would catch in 0 PVs
at PR-time); cumulative test count delta per cycle (must stay within
W-17 +30/PV cap); test wall-clock impact on `make precommit-full`
(must stay under +10s).

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline (v10.3.0) | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Bridge contract test count (per `v11.0.0_evaluation_methodology.md` §4.6) | 0 | 16-22 (4 files × 4-6 scenarios) | +16-22 | improve |
| Cached fixtures per plugin (per `v11.0.0_evaluation_methodology.md` §4.6 — a fixture-presence proxy) | 0 (Si-Chip case: pre-PV-04 fixtures were synthesised; post-PV-04 the test_models.py fixture mirrors real output but is NOT in tests/integration/fixtures/) | 8 fixtures across 4 plugin dirs (3+2+2+1) | +8 | improve |
| Time-to-detect bridge-shape defect (PVs from defect-introduction to detection) | 2 (v10.2.3 case: PV-02 introduced bridge wired only to legacy shape; PV-03 dogfood pass #2 surfaced; PV-04 fixed) | 0 (CI catches at PR open against shape contract) | -2 (-100%) | improve |
| `pytest tests/integration/` wall clock | N/A | ~3-5s (16-22 tests; checked-in fixtures; no subprocess) | +3-5s on `make precommit-full` (current ~17s baseline per `v10.3.0_retrospective.md` §6 trend) | preserve (under +10s budget) |
| W-17 cycle test contribution this PV | N/A | +16-22 (within +30/PV cap) | within cap | preserve |
| W-12 `build-skill` 4-adapter success rate | 100% | 100% | 0 | preserve |
| Cycle retrospectives mentioning silent-shape-mismatch pain (rolling 4-cycle window) | 1 (v10.3.0 §4 KL2 documents v10.2.3 bridge defect at length) | 0 (forecast — contract tests preempt the class of defect) | -100% (forecast) | improve |

**Pass criterion:** Δ ≥ +12 on Bridge contract test count AND
time-to-detect drops to 0 PVs AND `pytest tests/integration/` wall
clock ≤ +10s on `make precommit-full` AND W-17 +30/PV cap not exceeded
AND W-12 4-adapter success rate stays 100%.

**Side-effect check (must NOT regress):**

- W-17 cycle test cap (this PV adds ≤22; well under +30/PV cap; still
  leaves ~+128 cycle reservoir per the +150 cap).
- W-12 adapter build success (4/4 adapters; this patch doesn't touch
  SKILL.md / templates).
- CP-2 80% coverage floor (new tests are additive; existing modules
  still covered).
- C-7 valid reference links (none added).
- S-2 no absolute paths (fixture paths under `tests/integration/fixtures/`
  are repo-relative).
- S-7 external tool URL form (the cron workflow declares Si-Chip /
  NineS / RTK / ui-pro install commands by their canonical install
  scripts from `runtime-plugins.yaml` — no URL hardcoding).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.6 coupling-bucket; ≥3 metrics
required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-C-2) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Bridge contract test count | §4.6 (coupling — bridge_contract_test_count: integer per tool) | 0 (no `tests/integration/` dir at v10.3.0) | 16-22 across 4 plugins (4-6 scenarios per plugin file) | +16-22 | New `tests/integration/test_<tool>_shape_contract.py` files (4 files) |
| Cached fixtures per plugin | §4.6 (coupling — proxy: fixture presence under `tests/integration/fixtures/<tool>/`) | 0 | 8 (3 Si-Chip + 2 NineS + 2 RTK + 1 ui-pro) | +8 | New `tests/integration/fixtures/` directory tree |
| Time-to-detect bridge-shape defect (PVs from defect-introduction to detection) | §4.6 + §4.4 (coupling × test health proxy) | 2 PVs (v10.2.3 case: PV-02 introduced + PV-03 surfaced at dogfood) | 0 PVs (caught at PR-time by `pytest tests/integration/` against checked-in fixture) | -2 PVs (-100%) | Contract test runs at PR-time, not at end-of-cycle dogfood |
| Cycle retrospective mentions of silent-shape-mismatch pain (rolling window) | §4.6 (coupling — process pain proxy) | 1 (v10.3.0 retro KL2 dedicates ~250 words to bridge-defect lesson) | 0 (forecast post-v11.x; contract tests preempt the defect class) | -100% (forecast) | Verifiable via grep of post-v11.x retrospectives for "shape mismatch", "silent-zero", "bridge defect" |
| `pytest tests/integration/` wall clock | §4.4 (test health) | N/A | ~3-5s (16-22 tests, checked-in fixtures, no subprocess overhead) | +3-5s on `make precommit-full` | Bound by checked-in fixture I/O + dataclass parsing; no live network |

**Guarantee on metric:** ALL 5 metrics are scriptable from current DF
tooling (no external deps). "Bridge contract test count" via
`pytest --collect-only tests/integration/`. "Cached fixtures per plugin"
via `find tests/integration/fixtures/ -type f | wc -l`. "Time-to-detect"
is auditable from cycle retrospectives (count PVs between defect
introduction commit and defect-fix commit). "Wall clock" via
`pytest --durations=0 tests/integration/`.

## §6 — admission_verdict

**Verdict: PASS**

**Rationale:**

- G-1 Internal-value: 5 quantitative DF-internal metrics from §4.6 +
  §4.4; ZERO EvoBench signals used. The bridge contract test count is
  the SOLE direct measurement of "do we know upstream still emits
  what we parse?" — a question DF cannot answer today.
- G-2 Both-tier: small (synthetic_small_repo with 0 plugins)
  AND large (DevolaFlow self with 4 plugins) BOTH benefit. Small case:
  CI uses checked-in fixtures, runs in 3-5s without live plugin
  installation — no infrastructure burden. Large case: time-to-detect
  drops 2 PVs → 0 PVs (the v10.2.3 defect class is preempted at
  PR-time).
- G-3 Zero-deps: ZERO upstream changes proposed. Fixture creation is
  ON THE DF SIDE — `make refresh-bridge-fixtures` runs DF-owned
  Python which subprocess-invokes the plugin binary AND captures its
  output to `tests/integration/fixtures/`. No NineS/Si-Chip/RTK/ui-pro
  maintainer is involved. Per
  `v11.0.0_admission_checklist.md` §G-3 verbatim.
- G-4 Cycle-budget: 1 PV (M effort per `v10_internal_optimization_directions.md`
  §3.6 D-C-2); test budget +16-22 per the M-effort §G-4 mapping
  (≤25); fits within W-17 +30/PV cap.
- G-5 Soul-freeze: 0 Soul rule additions.
- G-6 Cache-prefix: zero edits to `schemas/lean-dispatch.yaml`.
- G-7 Compatibility: pure-additive (NEW `tests/integration/` directory
  + NEW `scripts/refresh_bridge_fixtures.py` + NEW Makefile target
  + NEW CI workflow file + W-18 lint stanza); no public API rename,
  no env flag rename, no schema field rename, no file path rename.
  The integration tests use existing public bridge APIs
  (`MetricsReport.from_yaml_dict`, `BasicAbilityProfile.from_yaml_dict`)
  unchanged.
- G-8 Test coverage: NEW `tests/integration/*` IS the test surface;
  the production bridge code paths exercised by the contract tests
  ALREADY have coverage above CP-2 80% floor (cycle coverage 93.04%
  per v10.3.0 retrospective). The contract tests add a NEW dimension
  (shape match against real upstream), not new code.
- G-9 Documentation completeness: CHANGELOG + W-18 lint refresh +
  Makefile target (`refresh-bridge-fixtures` is documented in the
  Makefile help target); matches the "Python module change" row in
  §G-9 table. NO reference doc add (the test-file docstrings ARE the
  contract). NO bilingual ZH (CI infrastructure is dev-facing).

## §7 — effort_estimate

**Effort: M (1 PV)**

**Breakdown:**

- `tests/integration/__init__.py` + `conftest.py`: ~80 LOC.
- 4 contract test files (Si-Chip + NineS + RTK + ui-pro): ~410 LOC
  total (~150 + ~120 + ~80 + ~60 LOC respectively).
- 8 fixture files (YAML/JSON/text; captured via `make
  refresh-bridge-fixtures`): ~300 LOC of YAML/JSON (size varies by
  plugin output verbosity — Si-Chip metrics_report ~100 LOC, NineS
  analyze JSON ~150 LOC, RTK rewrite ~30 LOC, ui-pro init log ~20 LOC).
- `scripts/refresh_bridge_fixtures.py`: ~150 LOC.
- `.github/workflows/bridge-fixture-refresh.yml`: ~50 LOC.
- `Makefile` + `tests/test_no_ghost_features.py` W-18 lint: ~35 LOC
  across 2 files.
- `CHANGELOG.md` entry: ~1 LOC under PV header.
- Total estimated effort: ~1025 LOC across implementation + tests +
  fixtures; M / 1 PV (analogous to v10.2.0 PV-03 NineS adapter
  `nines_to_sichip_eval_adapter.py` at 412 LOC + 23 unit tests
  landing in 1 PV per `v10.3.0_retrospective.md` §6).

**Confirms §3 estimate (M / 1 PV) from
`v10_internal_optimization_directions.md` §3.6 D-C-2.**

## §8 — dependencies

**None — this patch is fully standalone.**

The integration tests depend on:

- `src/devolaflow/si_chip_bridge/models.py::MetricsReport` /
  `::BasicAbilityProfile` — read-only.
- `src/devolaflow/si_chip_bridge/runner.py` — read-only (parser
  invocation only; no live subprocess).
- `scripts/nines_to_sichip_eval_adapter.py` — read-only (adapter
  conversion only).
- `src/devolaflow/shell_proxy/proxy.py` — read-only (rewrite
  consumer).
- The `runtime-plugins.yaml` registry (referenced in
  `refresh_bridge_fixtures.py` to discover the install commands) —
  read-only.

…all of which exist at v10.3.0. No other v11.0.0 patches required.

**Synergy (NOT a hard dependency):**

- D-C-1 (degraded-mode contract) ships scenario tests using
  monkeypatch fixtures (synthesised); D-C-2 ships shape contract tests
  using REAL captured fixtures. Together they cover both axes:
  D-C-1 = "what happens when upstream is unreachable"; D-C-2 = "what
  happens when upstream is reachable but emits unexpected shape".
  If both land in v11.0.0, share `tests/integration/conftest.py`
  fixtures.
- D-C-3 (`pre_plugin_invocation` split) reorganizes lifecycle
  events; D-C-2's tests for `nines_to_sichip_eval_adapter` are
  independent of lifecycle hook ordering, so D-C-3 is no
  prerequisite.
- D-O-2 (SI-3 6-dimension auto-collection) consumes NineS JSON
  output in its computation; if D-O-2 lands, the `tests/integration/test_nines_shape_contract.py`
  fixture becomes a dual-use validator.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Cached fixtures go stale silently between weekly refreshes — operator commits a PR that depends on a NEW upstream shape, fixture is OLD, tests pass against old fixture but production bridge fails against real new shape → exact same v10.2.3 defect class the patch is supposed to prevent | major | (a) Weekly CI cron job auto-detects fixture drift and opens a draft PR (per §2 step 6); reviewer is alerted within 7 days. (b) Each fixture file carries a YAML header with `captured_from_plugin_version: <version>` field; `refresh_bridge_fixtures.py` records the live plugin version at capture time. (c) `tests/integration/conftest.py` asserts `captured_from_plugin_version >= runtime_plugins_yaml.min_version` for the corresponding plugin row, so a fixture captured under a too-old plugin fails CI loudly. |
| R2 | The `make refresh-bridge-fixtures` target requires plugins INSTALLED — operators on fresh clones / CI containers WITHOUT plugins cannot refresh; only operators with plugins installed can capture | minor | The target gracefully SKIPS plugins that are not installed (per §2 step 4 design); emits a WARNING log line "plugin <id> not installed; skipping fixture refresh". The weekly CI cron job runs in a container with all 4 plugins pre-installed (the install commands are scriptable from `runtime-plugins.yaml`). The per-PR pytest run uses CHECKED-IN fixtures and does NOT invoke `refresh-bridge-fixtures`. |
| R3 | The 4-plugin contract test suite increases `make precommit-full` wall clock; if it grows unbounded, it could push precommit time over operator-tolerated threshold (~30s) | minor | Per §4 large project eval, the projected wall clock is +3-5s for 16-22 tests (checked-in fixtures + dataclass parsing only; no subprocess). v10.3.0 baseline is ~17s; post-patch projection ~22s — well under 30s. If a future PV adds a 5th plugin or 10× more scenarios per plugin, the per-PR vs weekly schedule split (per §2 step 6) preserves headroom: checked-in fixtures stay in per-PR, refresh + capture stays in weekly schedule. |

---

ADMISSION: PASS | EFFORT: M | DEPS: none | TIER: core
