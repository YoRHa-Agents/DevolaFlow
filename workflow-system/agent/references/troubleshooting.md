---
last_updated: "2026-08-19"
---

# Troubleshooting

## Purpose

Centralized handbook for the operator-friction patterns DevolaFlow's cycle
retrospectives have surfaced over v8.x → v10.x. Use it as a first stop when
a dispatch fails, a gate FAILs, a lifecycle hook raises, the version-bump
chain drifts, or a CI lint trips with no immediate explanation. The
reference pairs with `references/env-flags.md` (env-var inventory),
`references/decomposition-gate.md` (gate evaluation), and
`references/agent-workspace.md` (change-driven workspace machinery).

## When to Load

Load this reference when an operator (or agent) hits an opaque failure mode
and needs the canonical resolution path. The reference is `important`-tier
for most task types and `critical`-tier for `bugfix` / `dependency-setup`
flows where troubleshooting throughput is the primary deliverable.

## Body

### 1. Quick Lookup Index

Search this table by the symptom text the operator sees. Each row links to
a Part 2 §-section with the diagnostic + fix pattern.

| Symptom (verbatim where possible) | Domain | §-Section | Source retro |
|---|---|---|---|
| `VOF001` blocker on dispatch (file not in `owned_files`) | dispatch validation | §2.1 | v9.2.3 (M-001) |
| `PPI001` (error) on plugin install | plugin lifecycle | §2.2 | v10.2.1 PV-02 |
| `PPI002` (warning) plugin payload malformed | plugin lifecycle | §2.2 | v10.2.1 PV-02 |
| `PPI003` (warning) plugin daily-upgrade boundary | plugin lifecycle | §2.2 | v10.2.1 PV-02 |
| `FOE001` format-on-edit failure | lifecycle hooks | §2.3 | v9.4.0 |
| `PSE001` / `PSE002` post-skill-edit failure | lifecycle hooks | §2.3 | v10.2.1 PV-02 |
| `AWH001` / `AWH002` auto-write handoff failure | lifecycle hooks | §2.3 | v10.0.0 PV-04 |
| `CEA002` envelope-append-only violation | S-9 enforcement | §2.4 | v8.2.4 |
| `TOC001..TOC006` test-on-complete | lifecycle hooks | §2.3 | v8.0.0 P-08 |
| Gate FAIL but composite ≥ threshold | gate semantics | §2.5 | v9.0.0 PV-04 |
| Gate stagnation 2+ rounds | gate / convergence | §2.5 | v9.0.0 PV-04 |
| `pytest tests/test_version.py` mismatch | version drift | §2.6 | v10.0.0 §4.2 |
| `make check-cursor-skill` exits 1 | mirror parity | §2.6 | v8.0.0 P-08 |
| `_SF4_REFERENCE_SET` cardinality assertion fails | reference set drift | §2.6 | v9.0.0 PV-01 |
| `assert_dispatch_layout` raises | A-2 cache prefix | §2.7 | v9.0.0 PV-04 (ADR-002) |
| `test_layout_invariant_multi_baseline` fails | A-2 cache prefix | §2.7 | v9.0.0 PV-04 |
| `dataclass + spec_from_file_location` lookup error | scripting / tests | §2.8 | v10.0.0 §4.2 |
| `_grep_symbol` false positive on test-file echo | scripting / tests | §2.8 | v10.0.0 §4.2 |
| `ruff check --fix` produces format diff | tooling | §2.9 | v10.0.0 §4.2 |
| `pytest --lf` cache stale on branch switch | tooling | §2.9 | v10.3.0 PV-06 |
| W-18 ghost-audit refresh missing pre-CHANGELOG | governance | §2.10 | v9.0.0 PV-05 |
| Soul-set freeze (W-21) violation on PR | governance | §2.10 | v9.0.0 PV-07 |
| W-20 env-flag reuse rejected | governance | §2.10 | v9.0.0 PV-05 |
| `nines self-eval` upstream timeout | NineS integration | §2.11 | v9.0.0 PV-05 |
| Si-Chip iteration_delta DEFER pattern | Si-Chip integration | §2.12 | v10.2.3 PV-04 |
| MR/PR rejection on protected branch push | git workflow | §2.13 | v9.5.0 |
| `test_demo_index_gate_types` "automated" trip | doc consistency | §2.14 | v10.0.0 §4.2 |
| Reference doc loaded but never cited in artefacts | reference utilization | §2.15 | v10.4.0 (D-D audit) |
| `assert len(actual) == N` adapter golden mismatch | reference set drift | §2.6 | v9.0.0 PV-01 |
| `EnvelopeRecord` filename parse rejection | handoff schema | §2.4 | v8.2.4 |
| Bridge defect (upstream shape vs unit fixture) | Si-Chip / NineS | §2.12 | v10.2.3 PV-04 |
| Baseline regen scores diverge ~7pp from pytest scoring | tokenization determinism | §2.16 | v11.1.3 D-3 |
| `devola-init` target fails on a pip-wheel-only install | install / CLI | §2.17 | v9.2.2 (I-001/I-004) |
| Pre-existing working-tree corruption at cycle entry | working-tree sanity | §2.18 | v12.2.0 retro §4.3 |

### 2. Diagnostic Patterns

Each section follows a 3-block layout: **Symptom**, **Root cause**, **Fix**.

#### 2.1 `VOF001` — file write outside `owned_files`

* **Symptom**: a lifecycle-hook chain raises `HookViolation(code="VOF001", ...)`
  or a CI run fails on `tests/test_validate_owned_files.py`. The hook
  message names the offending file path and the change-id whose
  `owned_files.txt` lacks it.
* **Root cause** (S-8): an L3 Task Agent attempted to write a file outside
  the union of (a) paths in `.local/.agent/active/<change-id>/owned_files.txt`,
  (b) the change folder itself, (c) `.local/.agent/handoff/`. STRICT mode
  blocks; lite mode warns.
* **Fix**:
  1. Confirm the file SHOULD belong to this change. If yes — author a new
     handoff envelope (`L3 → L2`, seq+1) requesting `owned_files.txt` to be
     extended; never edit the file outside the workflow.
  2. If no — refactor the change so the file is owned by the producing
     L3 (move the work to the correct dispatch boundary).
  3. For trivial single-file edits < 20 lines, the P1 waiver still
     applies; cite it explicitly in the dispatch report.
* See `references/agent-workspace.md` §6 for the handoff protocol and
  `references/execution-protocol.md` §3 for the P1 waiver.

#### 2.2 `PPI001` / `PPI002` / `PPI003` — plugin lifecycle

* **Symptom**: `pre_plugin_invocation` hook raises one of the three codes
  during a dispatch that consults the plugin registry
  (`workflow-system/agent/knowledge/runtime-plugins.yaml`).
* **Root cause**:
  * `PPI001` (error) — `ensure_plugin` raised a domain exception
    (`PluginNotFoundError`, `PluginInstallError`,
    `PluginVersionConflictError`).
  * `PPI002` (warning) — payload schema malformed: `plugin_id` is not a
    string, or `plugin_ids` is not a `list[str]`.
  * `PPI003` (warning) — stale plugin daily-upgrade boundary detected
    (24h threshold, REUSED `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` per W-20);
    does NOT block the dispatch (warning only).
* **Fix**:
  1. For `PPI001`, run `python -m devolaflow.plugins.installer install <plugin_id>`
     manually and inspect the stderr; the most common upstream error is
     a missing pinned version in `runtime-plugins.yaml`.
  2. For `PPI002`, validate the payload against
     `schemas/lean-dispatch.yaml#layout_invariant.canonical_order`
     position 16 (`change_context`) — most often the dispatcher built
     `plugin_id: ["foo"]` instead of `plugin_ids: ["foo"]` or vice versa.
  3. For `PPI003`, the dispatch proceeds; manually run
     `python -m devolaflow.plugins.installer upgrade <plugin_id>` to
     refresh and silence next-cycle.

#### 2.3 `FOE001`, `PSE001..PSE002`, `TOC001..TOC006` — lifecycle hooks

* **Symptom**: format-on-edit, post-skill-edit, or test-on-complete hooks
  raise. The hook name + code is in the violation payload.
* **Root cause**: a strict-mode hook detected a contract breach.
  * `FOE001` — ruff formatter exited non-zero on a SKILL/CLAUDE/yaml
    write.
  * `PSE001` / `PSE002` — fingerprint-based dedup mismatch on
    `_write_feedback_doc`; usually the operator hand-edited the
    `.sichip_deferred_fingerprints.txt` sidecar.
  * `TOC001..TOC006` — covers test failure, lint fail, coverage drop,
    timeout, environment misconfig, and abort-after-retry. The exact
    code is mapped in `src/devolaflow/lifecycle/test_on_complete.py`.
* **Fix**: read the hook stderr; the message includes the canonical
  remediation (run `ruff format`, regenerate fingerprint sidecar,
  re-run the failing test in strict mode). For `TOC005` (env misconfig),
  most often the env-var set differs between dispatch + execution; cross
  check `references/env-flags.md` §2 active runtime flags.

#### 2.4 `CEA002` — envelope append-only violation (S-9)

* **Symptom**: `lifecycle/check_envelope_append_only` raises `CEA002` when
  an agent tries to mutate or delete an existing
  `<from>__<to>__<change-id>__<seq>.yaml`.
* **Root cause** (S-9): handoff envelopes are append-only. To convey new
  information, write a NEW envelope at `seq+1`; never edit the prior one.
* **Fix**: revert the envelope edit, author a new envelope with the next
  sequence number, and re-run the dispatch. The `audit_long_reference_usage.py`
  audit (D-D-2) confirms envelope creation patterns over time.

#### 2.5 Gate FAIL diagnostics

* **Symptom A — composite ≥ threshold but gate FAILs**: usually means
  zero blocker AND zero MUST-priority violations is NOT met (there's at
  least one blocker), OR coverage < `coverage_threshold`. Check
  `gate.report.findings_by_severity` and the coverage column.
* **Symptom B — gate stagnation 2+ rounds**: per W-8, the L0 must
  escalate to human (the reinforcement mechanism's max-5-rules cap is
  insufficient). The escalation payload should cite the round-N
  composite trajectory and the per-round severity histogram.
* **Symptom C — gate threshold not met after max_rounds**: P4 bounded
  retry — the round count exhausted; escalate Wave → Stage → Project →
  Human via the standard escalation chain.
* See `references/decomposition-gate.md` §3 for the full pass/fail
  matrix and `references/plan-mode-enforcement.md` §"Reinforcement
  Rules" for the W-8 / SI-9 contract.

#### 2.6 Version drift diagnostics

* **Symptom A — `tests/test_version.py` mismatch**: the canonical 7
  locations don't agree (e.g., `pyproject.toml` says 10.3.0 but
  `src/devolaflow/__init__.py` says 10.4.0 because someone edited one
  by hand).
* **Fix A**: re-run `python scripts/bump_version.py <target-version>`
  which atomically rewrites the canonical 7. Do NOT hand-edit; the
  pattern-matching is regex-anchored.
* **Symptom B — `make check-cursor-skill` exits 1**: the project-local
  `.cursor/skills/devola-flow/` mirror has drifted from
  `workflow-system/agent/`. The mirror is opt-in (gitignored).
* **Fix B**: `make sync-cursor-skill` if you have the mirror locally
  installed; otherwise no action needed (the script self-skips when
  the mirror is absent).
* **Symptom C — `_SF4_REFERENCE_SET` cardinality assertion fails**:
  someone added a reference under `workflow-system/agent/references/`
  without bumping the matching counts in
  `tests/test_no_ghost_features.py::_SF4_REFERENCE_SET`,
  `tests/test_version.py::_MIRRORED_SKILL_FILES`,
  `tests/test_reference_size_budgets.py`,
  `tests/test_adapter_golden.py::test_cursor_references_golden`, and
  the `data/golden_test_set/sf4_reference_set_size.toml` fixture.
* **Fix C**: bump all 5 surfaces in lockstep. The CHANGELOG entry under
  the PV header should cite the cascading-coupling list verbatim
  (precedent: v9.0.0 PV-01 for `plan-mode-enforcement.md`).

#### 2.7 A-2 cache-prefix layout violations

* **Symptom**: `devolaflow.compressor.assert_dispatch_layout(payload)`
  raises, OR `tests/test_layout_invariant_multi_baseline.py` fails on
  one or more historical baselines.
* **Root cause** (A-2.1): the FROZEN PREFIX (positions 1–12 of
  `schemas/lean-dispatch.yaml#layout_invariant.canonical_order`) is
  byte-stable; any reorder/remove/insert there is a release blocker.
  Positions 13+ are APPEND-ONLY (A-2.2).
* **Fix**:
  1. Use the v9-ADR-002 D3 nest-vs-append decision rule. New behaviour
     that modifies an existing block's interpretation → NEST under that
     block. Orthogonal cross-block payload → APPEND a new top-level
     key at position N+1.
  2. Add a new golden YAML for the new baseline AND keep all prior
     baselines passing.
  3. See `references/compression-pipeline.md` §"Cache-Layout
     Invariant" for the round-trip guarantee.

#### 2.8 `dataclass` + `spec_from_file_location` pitfall

* **Symptom**: an audit script test fails with
  `KeyError: '__dict__'` or `AttributeError: 'NoneType' object has no
  attribute '__dict__'` when loading a script via `importlib.util`.
* **Root cause**: `dataclass` resolves field annotations by looking up
  `sys.modules.get(cls.__module__).__dict__`. When a script is loaded
  via `spec_from_file_location` and not registered in `sys.modules`,
  the lookup returns None.
* **Fix**:

  ```python
  spec = importlib.util.spec_from_file_location("script_name", path)
  module = importlib.util.module_from_spec(spec)
  sys.modules["script_name"] = module  # MUST register BEFORE exec
  spec.loader.exec_module(module)
  ```

  Source: `docs/cycle-archive/v10.0.0/v10.0.0_retrospective.md` §4.2 #1.

* **Sub-pattern — `_grep_symbol` test-file echo**: when a test searches
  for a symbol that's literally absent from the codebase, the test FILE
  itself contains the needle as a string literal — false positive.
  Mitigation: build the needle by string concatenation (`"PRE" + "FIX_NAME"`),
  splitting it across literal boundaries so a verbatim-text search
  doesn't hit. Source: v10.0.0 retro §4.2 #2.

#### 2.9 Tooling races (ruff / pytest cache)

* **Symptom A — `ruff check --fix` produces format diff**: operator runs
  `ruff check --fix src/`, then `ruff format --check src/` reports
  diffs. The auto-fix introduced changes the formatter wants to
  re-format.
* **Fix A**: ALWAYS run `ruff format` AFTER `ruff check --fix`, in
  that order. The new `make precommit-fast` (D-X-3) bakes this in.
* **Symptom B — `pytest --lf` cache stale on branch switch**: operator
  switches branches, runs `pytest --lf`, and the cached "last failed"
  set is from the previous branch.
* **Fix B**: run `make clean` (which clears `.pytest_cache/`) when
  switching branches, or use `pytest --cache-clear` explicitly.
  Recommended workflow: `make precommit-full` (full SI-10 chain) after
  every branch switch, then `make precommit-fast` for in-branch
  iteration.

#### 2.10 W-18 / W-20 / W-21 governance

* **Symptom A — W-18 violation**: a CHANGELOG entry under `## [vX.Y.Z]`
  cites a feature symbol, but `tests/test_no_ghost_features.py` has
  no coverage assertion for that symbol's code path. The
  `test_ghost_audit_refresh_present` lint fails at CI.
* **Fix A**: refresh the ghost-audit FIRST (add a new test function or
  parametrize entry pinning the new symbol), then add the CHANGELOG
  entry. The sequencing is: ghost-audit refresh → run audit pytest →
  THEN author CHANGELOG. Per W-18.
* **Symptom B — W-20 violation**: a PR adds a new `DEVOLAFLOW_*` env
  flag without applying the reuse-first test. Reviewer rejects.
* **Fix B**: consult `references/env-flags.md` §2 for the active flag
  inventory. Apply the 3-step orthogonality test:
  (a) does an existing flag activate the same surface? → REUSE;
  (b) does an existing flag's R5 strict pattern apply? → adopt the
  same parsing + zero-IO design;
  (c) is the new behaviour orthogonal? → only then author a new flag.
* **Symptom C — W-21 violation**: a PR proposes adding S-11 (or
  beyond). W-21 requires a 2-cycle telegraph + cycle-N+2 SI-1 entry +
  SI-3 architecture-rationality ≥ 9.5/10.
* **Fix C**: the proposing L0 / human authors a deferral note in the
  current cycle's retrospective §3 ("What was deferred and why")
  flagging the proposed S-(N+1) for cycle N+2 review. Cycle N+1
  explicitly does NOT consider the addition.

#### 2.11 NineS upstream collector timeouts (W-2)

* **Symptom**: `nines -f json self-eval` hangs at 180s on `code_coverage`,
  or `nines analyze` returns `index_recall: 0.8` despite a fresh
  `make nines-index-rebuild` invocation.
* **Root cause** (v9.0.0 PV-05 A1): NineS v3.3.0 hardcodes the cov
  timeout at 54s; the `nines.toml [hygiene] cov_timeout = 180` key is
  forward-declared for v3.4+ but not honoured by v3.3.0 binaries.
* **Fix**:
  1. R-6 fallback active: `pyproject.toml [tool.coverage.run] parallel = false`
     prevents host-side cov-data fragmentation; this is set in v8.5.0+.
  2. For `index_recall`, the upstream caches the index between
     invocations; the `make nines-index-rebuild` mechanism ships the
     rebuild signal but v3.3.0 does NOT honour it at `self-eval` time.
     Operators run the 2-step `make nines-index-rebuild && nines self-eval`.
  3. Manual fallback: when NineS is unavailable, manual analysis
     following the same dimensions (code quality, architecture, tests,
     maintainability) is acceptable but MUST be noted as manual.

#### 2.12 Si-Chip iteration_delta DEFER + bridge defect

* **Symptom A — DEFER pattern**: Si-Chip iteration_delta returns DEFER
  rather than APPLY despite the operator believing the SKILL.md edit
  was substantive.
* **Root cause A**: prior to v10.2.3 PV-04 (bridge defect fix), the
  unit-fixture `MetricsReport.from_yaml_dict` consumed legacy
  top-level keys (`T1_pass_rate`, `baseline_delta`, etc.) but the
  v3.3.0+ MVP-8 nested keys
  (`metrics.task_quality.T1_pass_rate`,
  `summary.baseline_delta`,
  `metrics.context_economy.{C1_metadata_tokens,C2_body_tokens}`)
  silently fell through.
* **Fix A**: pin to DevolaFlow ≥ v10.2.3 (the bridge layer reads MVP-8
  nested keys with legacy top-level shape preserved as backward-compat
  fallback). Upgrade via `pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow`.
* **Symptom B — bridge defect surfaced ONLY at end-to-end dogfood**:
  unit fixtures pass green but `make iteration-delta-gate` produces
  a stale verdict.
* **Fix B**: end-to-end smoke test BEFORE landing the cycle. The
  v10.3.0 retro §4 codified this as: "schedule a real-data dogfood
  pass with the freshly-bumped wheel before authoring the CHANGELOG".

#### 2.13 Protected branch push rejection

* **Symptom**: `git push origin yc_dev` (or `main`, `master`,
  `production`) is rejected with a CI/server-side hook message.
* **Root cause** (S-6): protected branches must NEVER receive direct
  pushes. Always create a feature branch and propose a Merge Request /
  Pull Request.
* **Fix**:

  ```bash
  git checkout -b feat/<short-description>
  git cherry-pick <SHA>      # or rebase your work onto the new branch
  git push -u origin HEAD
  gh pr create --base yc_dev --title "..." --body "..."
  ```

#### 2.14 Doc-consistency lint trips (`test_demo_index_gate_types`)

* **Symptom**: `tests/test_doc_consistency.py::test_demo_index_gate_types`
  fails with "forbidden gate type 'automated' present".
* **Root cause**: the demo landing's gate-type list has a stale name.
  Per v6.x, gate types are `relaxed | standard | strict | audit`;
  "automated" was removed but lingered in the demo HTML.
* **Fix**: `grep -rn '"automated"' workflow-system/human/demo/` and
  rewrite the offending line. The lint exists specifically to catch
  this drift; do not disable.

#### 2.15 Reference loaded but never cited (D-D audit signal)

* **Symptom**: `audit_reference_utilization.py` reports a reference at
  < 20% utilization (the long-tail row).
* **Root cause**: the reference was added in cycle-N for an opt-in
  surface, but no profile in `context_profiles.yaml` declares it under
  `extra_context`. Common for `compression-pipeline.md` (advanced
  opt-in) and `shell-proxy.md` (RTK opt-in).
* **Fix**:
  1. Confirm the reference is intended to be opt-in. If yes, the
     long-tail signal is correct; tag the reference's SKILL.md row
     with "(opt-in)" so future cycle authors don't misread the metric.
  2. If no, audit the profile's `extra_context` declarations; the
     reference may have drifted out of `feature` / `research` /
     `migration` profiles during a prior compaction round.
  3. Run `python scripts/audit_long_reference_usage.py --output
     .local/research/v<NEXT>_long_reference_usage.md` for the
     filesystem-side signal (envelopes + research artefacts citing
     the reference).

#### 2.16 Token-estimation determinism (W-16 baseline regen)

* **Symptom**: an operator regenerates EvoBench baselines via a
  standalone script (anything that imports `devolaflow.benchmarks` or
  invokes the regen entry-point WITHOUT going through the pytest
  harness) and the resulting `benchmarks/devolaflow_context/baselines/
  *_baseline.json` composite scores differ from the pytest-side scores
  reported by `pytest tests/test_benchmarks.py -v` by roughly **7
  percentage points** on the composite axis. Subsequent W-4 / SI-4
  regression checks then trip on every PV until someone realises the
  baseline itself is mis-anchored.
* **Root cause**: `tests/conftest.py::_force_fallback_token_estimator`
  is an autouse pytest fixture that monkeypatches
  `sys.modules["tiktoken"] = None` for the duration of every
  `test_benchmarks.py` test. With `tiktoken` hidden,
  `devolaflow.task_adaptive_selector.estimate_tokens` falls back to
  the deterministic `len(text) // 4` heuristic. Both estimators are
  deterministic, but their absolute counts differ, leading to the
  ~7pp composite divergence. The fixture is INTENTIONAL — it pins
  pytest scoring so CI and dev laptops agree regardless of whether
  `tiktoken` is installed. The bug is *not* the fixture; the bug is
  that operator-side regen scripts run OUTSIDE pytest and therefore
  never see the fixture fire.
* **Fix** (3 options, in order of preference):
  1. **Option A — invoke under pytest** (preferred). Run the regen as
     `pytest tests/test_benchmarks.py --regenerate-baselines` (or the
     equivalent flag the regen entry-point exposes). conftest is
     loaded automatically; the autouse fixture fires; scores match
     pytest-side composites byte-for-byte modulo float-formatting.
  2. **Option B — pre-set `sys.modules["tiktoken"] = None` BEFORE
     importing devolaflow** in the regen script. Order is load-bearing:
     ```python
     import sys
     sys.modules["tiktoken"] = None
     from devolaflow import ...  # noqa: E402 — order matters
     ```
     Imports BEFORE the assignment still resolve to the real
     `tiktoken` if it's installed.
  3. **Option C — uninstall tiktoken from the venv** (`pip uninstall
     tiktoken`). Heavy-handed; affects every workflow in the env, not
     just the regen. Reserve for dedicated CI venvs whose only purpose
     is baseline regeneration; do not run on dev laptops that use
     tiktoken for unrelated work.
* See `tests/conftest.py::_force_fallback_token_estimator` for the
  fixture body + matching docstring; the v11.1.0 cycle's W-16
  wholesale baseline regen at PV-02 was the first cycle where this
  divergence surfaced empirically. Source: `docs/cycle-archive/
  v11.1.0/retrospective.md` cycle-close summary; v11.1.3 D-3 closed
  the documentation gap.

#### 2.17 `devola-init` on a pip-wheel-only install (I-001 / I-004)

* **Symptom**: a `devola-init` target aborts on a fresh `pip install`
  because the `workflow-system/agent/` source tree is missing.
* **Root cause / contract** (absorbed verbatim from SKILL.md
  §"Version & Update" at v14.5.0, G-019 / F-P1-4): `pip install` ships
  the package but the `devola-init` CLI's `cursor` / `claude` / `codex` /
  `copilot` targets need the `workflow-system/agent/` source tree (not
  bundled in the wheel). For most install scenarios `devola-init local
  --mode=core` works on a wheel-only install (v9.2.3+ — `--mode=core` is
  the shorthand for `--no-compile --no-with-examples`, the lean
  scaffolding-only install).
* **Fix**: for other targets, install from a clone:
  `git clone https://github.com/YoRHa-Agents/DevolaFlow && pip install -e ./DevolaFlow`.
  Tracked in I-001 (fixed v9.2.2) + I-004 (doc v9.2.2) + `--mode`
  shorthand (v9.2.3); full bundle deferred to v9.3.0. See also
  `tests/test_init_project_pip_wheel.py` (the I-001 closure pins).

#### 2.18 Pre-existing working-tree corruption at cycle entry

* **Symptom**: the SKILL.md §"Repo-Init Pre-Dispatch Contract"
  working-tree sanity check (`git status` + `git diff --stat HEAD --
  '*.md' '*.py'` at cycle-entry PV-01) surfaces truncated / drifted
  files left by a prior interrupted session.
* **Canonical case study** (absorbed verbatim from SKILL.md at v14.5.0,
  G-019 / F-P1-4): The v12.2.0 cycle is the canonical example — PV-01
  surfaced a pre-existing 4787-line CHANGELOG.md truncation +
  1786-line test_no_ghost_features.py truncation that would have
  silently invalidated W-18 ghost-audit if not restored first.
* **Fix**: restore drifted files via `git restore <path>` BEFORE
  proceeding so the SI-1 entry gate operates on a clean baseline
  (source: `docs/cycle-archive/v12.2.0/v12.2.0_retrospective.md` §4.3).

### 3. Escalation Patterns

DevolaFlow's escalation chain (P4 Bounded Retry) is **always upward**:
Task → Wave → Stage → Project → Human. Never skip levels.

| Severity tag | Action | Receiver |
|---|---|---|
| `AUTO_RECOVER` | Retry up to 3× with exponential backoff | Same agent |
| `PAUSE` | Pause task, queue question, continue parallel work | Wave / Stage |
| `HUMAN_INTERVENE` | Stop stage, present options to human | Human |
| `FULL_ROLLBACK` | Rollback to checkpoint, halt all | Human (mandatory) |

**Stagnation pattern (W-8 / SI-9)**: if the gate composite stagnates for
2+ rounds despite the reinforcement payload (max 5 severity-filtered
rules), the L0 escalates to Human regardless of `max_rounds`. The
escalation report MUST cite the 2 trailing composites + the
reinforcement-rule trajectory + the per-round finding histogram.

**External-upstream pattern**: when the failure is in NineS A1 (cov
timeout), Si-Chip MVP-8 (nested-key contract change), or any other
external dependency, the escalation should distinguish "DevolaFlow
implementation defect" from "upstream issue" and recommend the manual
fallback (per §2.11) rather than blocking the cycle.

## Cross-References

- `references/agent-hierarchy.md` — L0/L1/L2/L3 dispatcher contracts
  and the P1 dispatcher-not-implementer invariant.
- `references/agent-workspace.md` — change-driven workspace, handoff
  envelopes (S-9), and the `.local/.agent/` tree.
- `references/compression-pipeline.md` — `assert_dispatch_layout`
  validator and the cache-layout invariant.
- `references/decomposition-gate.md` — gate evaluation matrix,
  composite formula, and pass/fail thresholds.
- `references/env-flags.md` — `DEVOLAFLOW_*` runtime flag inventory
  and W-20 reuse-first policy.
- `references/execution-protocol.md` — task lifecycle, P1 waiver, and
  the standard escalation chain.
- `references/message-schemas.md` — TaskDispatch / StatusReport /
  HandoffEnvelope shapes.
- `references/meta-framework.md` — workflow primitives + alias
  mapping.
- `references/plan-mode-enforcement.md` — plan-mode L0 contract,
  reinforcement rules, convergence loop.
- `references/shell-proxy.md` — RTK plugin, command mapping recipes,
  memory-router fast-path.
- `references/team-roles.md` — team participation matrix, per-team
  responsibilities.

## History

- v10.4.0 PV-05 (this cycle) — initial author of the troubleshooting
  reference. ~30 distinct operator-trip patterns harvested from cycle
  retrospectives v8.0.0 → v10.3.0. Pairs with the new
  `audit_reference_utilization.py` (D-D-1) + `audit_long_reference_usage.py`
  (D-D-2) audit scripts and the `scaffold_template.py` (D-X-1) +
  `scaffold_reference.py` (D-X-2) operator CLIs.
- Future cycles append new symptom rows to §1 and new diagnostic
  sections to §2; when §2 grows past ~700 lines, split per the v8.x
  reference-spawning pattern (e.g.,
  `references/troubleshooting-plugin.md`).
