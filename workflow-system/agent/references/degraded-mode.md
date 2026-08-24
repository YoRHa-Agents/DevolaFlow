---
last_updated: "2026-08-25"
---

# Upstream-Unreachable Degraded-Mode Contract

## ⚠️ Degraded ≠ Full — Read This First

**Degraded mode is NOT "DevolaFlow works offline." Degraded mode is "DevolaFlow
does NOT crash when a specific upstream plugin is unreachable, AND the
surrounding dispatcher / skill workflow continues with the EXPECTED loss of
signal from that plugin."**

When an operator reads this reference and takes away "I can run DevolaFlow
without installing NineS / Si-Chip / RTK / ui-pro," they have misunderstood the
contract. The contract is narrower:

1. **Plugin-specific**: each of the 6 registered plugins (NineS, Si-Chip, RTK,
   ui-pro, codegraph, impeccable) has its OWN degraded-mode story; one plugin
   being unreachable does NOT imply the rest are.
2. **Signal loss is EXPECTED**: SI-3 evaluations without NineS lose the
   capability / hygiene axes; Si-Chip dogfood gates without Si-Chip produce
   `SKIPPED_PERMISSIVE` verdicts; RTK passthrough without `rtk` gives you the
   native shell command; ui-pro skipping on install means the skill bundle is
   missing the ui-pro surface.
3. **Operator must confirm the signal loss was intended**: a cycle that relies
   on Si-Chip's `iteration_delta` APPLY/DEFER verdict and then silently runs
   without Si-Chip installed is NOT a valid cycle — the retrospective MUST
   document the signal loss and the cycle-lead MUST manually evaluate.

**What STOPS working when each plugin is unreachable:**

| Plugin | What STOPS working |
|---|---|
| **NineS** | Deep-analysis scoring; `--depth deep --agent-impact` score breakdowns; SI-3 evaluator rosetta cross-walk's NineS-authoritative axes (code quality, architecture rationality, test adequacy) lose their quantitative backing and must be manually scored per Rule W-2 fallback. |
| **Si-Chip** | `iteration_delta` APPLY/DEFER gate; post-skill-edit dogfood cycle verdict; `MetricsReport` composite / `task_delta` / `value_vector` scoring; every skill edit under `workflow-system/agent/**` loses its auto-evaluation signal until Si-Chip is back. |
| **RTK** | Shell command rewriting (`git add`, `git commit`, `pytest`, etc. run as native commands; no RTK value-add); command-mapping layer `apply_recipe_to_output` still works for already-captured recipe files but NO new RTK rewrites are captured. |
| **ui-pro** | Skill bundle install step fails with PPI001 (suggest tier since v15.2.0 B-6: severity warning + one-time hint; permissive default continues); a product-verification checklist item that requests ui-pro loses that signal. |
| **impeccable** | Skill bundle install step fails with PPI001 (suggest tier since v15.2.0 B-6: severity warning + one-time hint; permissive default continues); web-design refine/verify assertions materialized from seed provenance lose the `/impeccable polish|critique|audit` surface and degrade `impeccable detect` to a non-gating advisory (signal loss recorded; never a fabricated PASS). |

**What KEEPS working in ALL degraded-mode scenarios:**

* Every L0 → L1 → L2 dispatch runs to completion (the dispatcher never
  aborts because of a plugin unavailability).
* Every `run_hooks(event, payload, strict=False)` call returns a HookResult
  with violations ENUMERATED, not raised.
* Every `.local/.agent/active/<id>/` artifact write succeeds (plugin
  unreachability does NOT affect workspace-lifecycle operations).
* Every `schemas/lean-dispatch.yaml#layout_invariant.canonical_order` position
  1-16 is populated correctly (cache-prefix invariant preserved regardless of
  plugin state).

**If this distinction is unclear, STOP and consult the cycle-lead before
proceeding.** Shipping a cycle whose key signal was silently missing is a
release-blocker class of bug.

## When to Load

Load this reference when:

* **An operator reports "my CI is different from my laptop"** — one host has
  the plugin installed, the other does not; the degraded paths explain the
  divergence.
* **A cycle retrospective is being authored** (W-7 / SI-8) and any of the 6
  plugins was not available during the cycle — the retrospective MUST
  enumerate the signal loss.
* **A new plugin is being proposed** for addition to
  `runtime-plugins.yaml` — each new plugin needs a matching degraded-mode
  contract entry HERE before it can be marked READY (per the v11.0.0 D-C-1
  admission gate precedent).
* **A PR touches `lifecycle/post_skill_edit.py`, `lifecycle/pre_plugin_invocation.py`,
  `shell_proxy/proxy.py`, or any catch-handler for plugin domain
  exceptions** — re-read the per-plugin section below to confirm the existing
  contract before modifying.

The reference is `important`-tier for most task types and `critical`-tier for
`nines-assisted` / `self-update` / `product-verification` workflows where
multi-plugin coordination is the primary deliverable.

## Body

### Plugin Matrix — Quick Lookup

| Plugin | Canonical URL | Env flag | Trigger surface | Failure-mode taxonomy | DF-side fallback | Operator action | Test |
|---|---|---|---|---|---|---|---|
| NineS | https://github.com/YoRHa-Agents/NineS | (none — W-2 manual fallback) | `W-2 / SI-2 nines analyze`; `D-N-2 code_coverage` | network-unreachable / binary-missing / `nines-type-kit` collision / schema-drift (v3.x → v4.x) | Manual SI-3 scoring per W-2 precedent | Document "NineS unavailable; W-2 manual fallback applied" in retrospective | `tests/test_degraded_mode.py::test_nines_unreachable_falls_back_to_manual_w2` |
| Si-Chip | https://github.com/YoRHa-Agents/Si-Chip | `DEVOLAFLOW_SI_CHIP_DEEP` (opt-IN) | `post_skill_edit` hook; `run_dogfood_cycle`; `iteration_delta_gate` | `SiChipUnavailable` (binary missing); `SiChipError` (subprocess fail); network-unreachable mid-install | PSE001 warning; `metadata["verdict"] = "SKIPPED_PERMISSIVE"`; dispatch continues | Install Si-Chip per canonical URL OR document SKIPPED verdict in retrospective | `tests/test_degraded_mode.py::test_si_chip_unreachable_emits_pse001_and_defers` |
| RTK | https://github.com/rtk-ai/rtk | `DEVOLAFLOW_RTK_PROXY` (opt-IN) | `pre_shell_call` hook; `shell_proxy/proxy.py::ShellProxy.wrap_command` | env-flag unset; binary missing on PATH; `rtk gain` probe fail (rtk-type-kit collision) | R5 strict passthrough to native shell; zero subprocess work | No action needed — RTK is OPT-IN by default | `tests/test_degraded_mode.py::test_rtk_unreachable_bypasses_to_native_shell` |
| ui-pro | https://github.com/YoRHa-Agents/ui-pro | `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (opt-IN) | `pre_plugin_invocation` hook; `ensure_plugin('ui-pro')`; `uipro init --ai cursor --global` | `PluginInstallError` (npm registry unreachable); `PluginNotFoundError` (registry typo); `PluginVersionMismatch` | PPI001 warning (suggest tier, v15.2.0 B-6) + one-time hint; permissive default continues (explicit strict=True still re-raises) | Check npm registry reachability OR set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` to bypass | `tests/test_degraded_mode.py::test_ui_pro_unreachable_emits_ppi001_permissive_continues` |
| impeccable | https://github.com/pbakaus/impeccable | `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (opt-IN; **REUSED**, no new flag per W-20) | `pre_plugin_invocation` hook; `ensure_plugin('impeccable')`; web-design refine/verify seed hints; `impeccable detect --json` check | `PluginInstallError` (npm registry unreachable); `PluginNotFoundError` (registry typo); `PluginVersionMismatch`; detector binary missing | PPI001 warning (suggest tier, v15.2.0 B-6) + one-time hint; permissive default continues (explicit strict=True still re-raises); verify evidence becomes a non-gating advisory (signal loss recorded, never fabricated PASS) | Check npm registry reachability OR run `npx impeccable detect` standalone OR set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` to bypass | `tests/test_degraded_mode.py::test_impeccable_unreachable_emits_ppi001_permissive_continues` |
| codegraph | https://github.com/colbymchenry/codegraph | `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (opt-IN; **REUSED**, no new flag per W-20) | `devolaflow.codegraph.researcher.{build_context,search_symbols,get_impact,get_callers,get_affected_tests}`; `repo-init.scaffold.codegraph_init`; `repo-init.verify.codegraph_smoke` (mode=full only) | `CodegraphUnavailableError` with structured `cause` (one of: `path_missing` / `timeout` / `nonzero_exit` / `json_parse_error`) | Helper returns empty sentinel (`""` for build_context, `[]` for list helpers, `{}` for get_impact); WARNING fires once per process (subsequent at DEBUG); caller falls back to Read/Glob/Grep planning; gate scoring drops `codegraph_impact` dimension and redistributes weight | Install codegraph per canonical URL (`npm install -g @colbymchenry/codegraph`) OR set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` to opt into runtime install | `tests/test_codegraph.py::TestRunCodegraphCli::test_path_missing_raises_unavailable` + sister tests across the 5 helpers |

### Section 0 — Capability-Probe → Recipe Selection (first-class mechanism) [v15.2.0 B-6]

Degraded mode is no longer only a warn-and-continue afterthought: since
v15.2.0 B-6 (04 §8.2) **every plugin dependency point declares a 4-tuple**
and the consuming agent SELECTS a recipe instead of failing:

| Field | Meaning |
|---|---|
| Probe | zero-IO capability check (CLI on PATH via `shutil.which`, installed skill dir exists, or an equivalent tool — e.g. no codegraph but `rg` present → research recipe degrades to rg) |
| Recipe A (present) | the enhanced path that uses the plugin |
| Recipe B (absent) | the built-in degraded path — the workflow ALWAYS continues |
| Hint | ONE per-session suggestion via `devolaflow.plugins.loader.suggest_plugin_once` (never repeated in the same session; S-5 — degradation is logged, never silent) |

Supporting contracts:

* Checklist seeds preserve `config.suggest_plugins: [...]` hints (renamed
  from `ensure_plugins` at v15.2.0 — a PROBE instruction, not a hard
  precondition). L0 materializes only relevant hints; the per-section recipes
  below are the Recipe A/B bodies.
* `runtime-plugins.yaml` schema v4 adds `tier: require | suggest` per
  entry (all shipped entries are `suggest`; `require` is a kept mechanism
  with no occupant). Suggest-tier install failures under
  `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` surface as PPI001 **warnings**
  (the permissive default — the only shipped wiring — proceeds on the
  degraded path; explicit `strict=True` callers still re-raise per the
  unchanged `finalize` contract); require-tier keeps PPI001 **error**.
* `defaults.auto_install` is `false` since v15.2.0: bare
  `ensure_plugin(pid)` probes and reports instead of network-installing;
  the explicit opt-in surfaces (the `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`
  hooks, `devola-init --global` bundling) pass `auto_install=True`.

### Section 1 — NineS (Deep-analysis evaluator)

**Trigger surfaces (file:line citations relative to repo root):**

* `W-2 / SI-2 nines analyze` — invoked during every MINOR cycle's SI-1
  planning gate (`.cursor/rules/repo-governance.mdc::W-2`) and end-of-
  iteration self-evaluation.
* `D-N-2 code_coverage` collector path — documented in
  `docs/cycle-archive/v10.3.0/v10.3.0_retrospective.md` §3 row "NineS A1 ticket —
  `code_coverage` collector timeout" — the first surfaced NineS-
  unreachability pain point.
* `scripts/nines_to_sichip_eval_adapter.py` — the adapter consumes NineS
  JSON output; unreachable NineS → adapter cannot produce Si-Chip
  `runs-dir` layout.

**Failure-mode taxonomy:**

1. **network-unreachable** — `curl -fsSL https://yorha-agents.github.io/NineS/install.sh`
   returns non-zero; operator has no binary at all.
2. **binary-missing** — `shutil.which("nines") is None` at the moment
   of invocation (operator uninstalled; `$PATH` misconfigured).
3. **nines-type-kit collision** — similar to RTK: some distros ship an
   unrelated `nines` binary (`nines-type-kit`); `nines analyze` exits
   non-zero because it's the wrong tool. The v10.3.0 A1 ticket had this
   exact symptom.
4. **schema-drift** — NineS v3.x → v4.x JSON schema change; the adapter
   fails on a `KeyError: 'scoring_accuracy'`.

**DF-side fallback (what continues to work):**

* `.cursor/rules/repo-governance.mdc::W-2` explicitly declares: "When
  NineS is unavailable, manual analysis following the same dimensions
  (code quality, architecture, tests, maintainability) is acceptable but
  must be explicitly noted as manual."
* The SI-3 evaluation template (`.local/research/vX.Y.Z_evaluation.md`)
  accepts manual JSON inputs; the evaluator rosetta §4 documents which
  axes lose NineS-authoritative backing and fall to manual scoring.
* `scripts/auto_collect_si3_metrics.py` (v10.7.0 D-O-2) short-circuits
  with `available=False` + non-empty `error` when NineS is absent; the
  dim's score reflects the average of AVAILABLE subs.

**Operator action:**

1. Confirm the NineS absence is intentional (bandwidth constraint,
   air-gapped CI, transient outage).
2. Run manual SI-3 scoring per the 6-dim template in `.cursor/rules/`
   (code quality / architecture / test adequacy / maintainability /
   compatibility / performance).
3. Document "NineS unavailable; W-2 manual fallback applied" in the
   cycle retrospective §3 "What was deferred and why" OR §4 "Key
   learnings" depending on the severity of the impact.

**Test coverage:** `tests/test_degraded_mode.py::test_nines_unreachable_falls_back_to_manual_w2`
pins the W-2 manual-fallback contract — asserts that the SI-3
evaluation script accepts manual JSON inputs when NineS is unreachable.

### Section 2 — Si-Chip (Skill iteration-delta evaluator)

**Trigger surfaces:**

* `src/devolaflow/lifecycle/post_skill_edit.py` — the `post_skill_edit`
  hook at lifecycle position 10 (per v9.5.0 PV-04 D-S-4 closure). The
  hook fires after any commit touching `workflow-system/agent/**` when
  `DEVOLAFLOW_SI_CHIP_DEEP=1`.
* `src/devolaflow/lifecycle/post_skill_edit.py::_run_si_chip_evaluation`
  (the helper that drives `run_dogfood_cycle` and classifies the
  outcome).
* `src/devolaflow/si_chip_bridge/runner.py::run_dogfood_cycle` — the
  3-script orchestration (`profile_static.py` → `count_tokens.py` →
  `aggregate_eval.py`).

**Failure-mode taxonomy:**

1. **SiChipUnavailable** — the domain exception raised by
   `devolaflow.si_chip_bridge.find_si_chip_install` when `shutil.which`
   fails to find any of the 3 scripts; documented in
   `src/devolaflow/lifecycle/post_skill_edit.py` catch block.
2. **SiChipError** — subprocess fail (non-zero exit from one of the 3
   Si-Chip scripts); documented in the same catch block.
3. **Schema drift (MVP-8 nested vs legacy top-level)** — exposed by the
   v10.2.2 bridge defect chronicled in
   `docs/cycle-archive/v10.3.0/other/v10.2.3_iteration_round1.md` §1. Closed by v10.2.3
   PV-04 via the `MetricsReport.from_yaml_dict` nested-path lookup.
4. **Network-unreachable mid-install** — the canonical `curl install.sh`
   pipeline can partial-succeed and leave the binary in a broken state;
   subsequent `run_dogfood_cycle` calls raise `SiChipError` with a
   non-obvious diagnostic.

**DF-side fallback:**

* `post_skill_edit` catches `SiChipUnavailable` and emits HookViolation
  `PSE001` (severity `warning`); sets `metadata["verdict"] = "SKIPPED_PERMISSIVE"`;
  dispatch continues. Observed-verbatim behavior pinned by
  `tests/test_post_skill_edit_hook.py`.
* Catches `SiChipError` and emits HookViolation `PSE002` (severity
  `error`); sets `metadata["verdict"] = "ERROR"`; dispatch continues.
* An unexpected non-domain exception (e.g. `OSError` on disk full) is
  logged at WARNING and RE-RAISED per S-5 — the handler never silently
  swallows non-domain failures.
* The install-hint string (`curl -fsSL ... install.sh | bash -s -- ...`)
  is captured verbatim in the PSE001 violation context so the operator
  can copy-paste it to recover.

**Operator action:**

1. If PSE001 fired: install Si-Chip per the canonical URL; re-run the
   cycle's post-commit hook chain.
2. If PSE002 fired: check the subprocess error captured in
   `violation.context["details"]`; the most common cause is a stale
   Si-Chip install (v0.1.5 or older) incompatible with the v10.2.3
   MVP-8 nested schema — reinstall per the canonical URL.
3. Document the SKIPPED / ERROR verdict in the cycle retrospective
   §3 "What was deferred and why" — an unresolved PSE001 across 2+
   cycles escalates per W-8 SI-9 (stagnation → human escalation).

**Test coverage:** `tests/test_degraded_mode.py::test_si_chip_unreachable_emits_pse001_and_defers`
pins the PSE001 + SKIPPED_PERMISSIVE verdict path + dispatch-continue
invariant. The existing `tests/test_post_skill_edit_hook.py` covers the
raising-path at unit-test granularity; the degraded-mode test covers
the cycle-level invariant ("dispatch continues; gate result documented").

### Section 3 — RTK (Shell command rewriter)

**Trigger surfaces:**

* `src/devolaflow/lifecycle/pre_shell_call.py` — the `pre_shell_call`
  hook at lifecycle position 6 (per v8.3.1 PV-01 closure).
* `src/devolaflow/shell_proxy/proxy.py::ShellProxy.wrap_command` — the
  per-command decision point.
* `src/devolaflow/shell_proxy/proxy.py::_resolve_config` — the activation
  context captured once per ShellProxy instantiation.

**Failure-mode taxonomy:**

1. **env-flag unset** (default state) — `DEVOLAFLOW_RTK_PROXY` absent
   or not exactly `"1"`. Zero IO, zero subprocess. This is NOT a
   failure mode; it is the INTENTIONAL default.
2. **binary-missing** — env-flag set, but `shutil.which("rtk") is None`.
   Logs a WARNING with the install URL; `proxy_enabled = False`;
   passthrough to native command.
3. **rtk-type-kit collision** — env-flag set, rtk binary present, but
   `rtk gain` exits non-zero because it's the unrelated
   `reachingforthejack/rtk` package on PATH. Logs WARNING with
   install-script URL per S-5 actionable-error contract.
4. **distinguish-probe timeout** — `rtk gain` hangs longer than
   `_DISTINGUISH_TIMEOUT_SECONDS` (5.0s); subprocess killed;
   passthrough falls back.

**DF-side fallback:**

* All 4 failure modes → `ShellProxyConfig(proxy_enabled=False)` +
  `wrap_command()` returns input unchanged. Pinned by
  `tests/test_shell_proxy_disabled_is_noop.py` (existing R5 strict
  baseline).
* The extended case (env-flag ON but binary absent) codified by
  `tests/test_degraded_mode.py::test_rtk_unreachable_bypasses_to_native_shell`.
* The `pre_shell_call` hook surfaces `metadata["proxy_enabled"] = False`
  + `metadata["was_rewritten"] = False` in its HookResult; observers
  can detect the degraded state without parsing log output.

**Operator action:**

* RTK is OPT-IN by default — no action required when unreachable.
* If operator wants RTK value-add and the rtk-type-kit collision is
  the symptom: reinstall via the canonical URL's install script.
* If the distinguish-probe times out repeatedly: check rtk version
  (`rtk --version`); older versions had a known hang on `rtk gain` in
  certain OS configurations (documented in RTK INSTALL.md).

**Test coverage:** `tests/test_degraded_mode.py::test_rtk_unreachable_bypasses_to_native_shell`
asserts that when `DEVOLAFLOW_RTK_PROXY=1` AND `shutil.which("rtk")`
returns None, `wrap_command(cmd)` returns `cmd` unchanged AND the
`pre_shell_call` HookResult metadata says `was_rewritten=False`.

### Section 4 — ui-pro (Skill bundle installer)

**Trigger surfaces:**

* `src/devolaflow/lifecycle/pre_plugin_invocation.py` — the
  `pre_plugin_invocation` hook at lifecycle position 9 (per v9.4.0 PV-02
  D-P-1 closure). After the v10.8.0 D-C-3 split, the install path
  delegates to `pre_plugin_invocation_install` at position 11.
* `src/devolaflow/plugins/installer.py::ensure_plugin` — the install
  primitive invoked per plugin candidate.
* `workflow-system/agent/knowledge/runtime-plugins.yaml` lines 86-102 —
  the registry row declaring `invoked_by_workflows: [product-verification]`.

**Failure-mode taxonomy:**

1. **PluginInstallError** — `npm install -g uipro-cli` exits non-zero
   (network-unreachable; registry 5xx; disk full).
2. **PluginNotFoundError** — the registry row is missing or the
   plugin_id is typoed in the dispatch payload.
3. **PluginVersionMismatch** — `uipro-cli` installed at
   a version below `runtime-plugins.yaml#plugins[ui-pro].min_version`.
4. **PluginBackendUnsupported** — the operator's environment lacks
   `npm` (or lacks `curl`, depending on the plugin's install backend).

**DF-side fallback:**

* `pre_plugin_invocation` catches the 4 domain exceptions and emits
  HookViolation `PPI001` — severity `warning` since v15.2.0 B-6
  (ui-pro is suggest-tier), with a one-time per-session hint appended;
  **the permissive default (the only shipped wiring) continues**; the
  violation is aggregated onto the HookResult for observers. Explicit
  `strict=True` callers still re-raise the top violation (`finalize`
  semantics unchanged — strict is strict).
* A require-tier plugin (kept mechanism; no shipped occupant) would
  keep severity `error` and re-raise in strict mode.
* An unexpected non-domain exception logs at WARNING and RE-RAISES per
  S-5 — the handler never silently swallows non-domain failures.
* The `metadata["install_outcomes"]` field (populated on the
  HookResult) lists per-plugin install attempts so downstream observers
  can inspect which IDs succeeded vs failed.

**Operator action:**

1. Check npm registry reachability with `npm ping`.
2. If PluginNotFoundError: confirm `runtime-plugins.yaml` has the
   expected row; fix the plugin_id typo in the dispatch payload.
3. If PluginVersionMismatch: `npm install -g uipro-cli@latest` OR
   pin the expected version in `runtime-plugins.yaml`.
4. If PluginBackendUnsupported: install the missing backend (`apt
   install npm` / `brew install npm` / `curl` as needed).
5. For operators who want to opt-OUT of pre-flight install entirely:
   `export DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` (or unset) — the hook
   becomes a byte-identical no-op.

**Test coverage:** `tests/test_degraded_mode.py::test_ui_pro_unreachable_emits_ppi001_permissive_continues`
pins the PPI001 + permissive-continue invariant. The test
monkeypatches `ensure_plugin` to raise `PluginInstallError`; the
handler aggregates the violation and returns a HookResult; no exception
propagates to the caller.

### Section 5 — codegraph (Pre-indexed code knowledge graph) [v12.5.0 PV-05]

**Trigger surfaces (file:line citations relative to repo root):**

* `src/devolaflow/codegraph/_cli.py::run_codegraph_cli` — the single
  owner of every `codegraph` subprocess invocation; raises
  `CodegraphUnavailableError` with structured `cause`.
* `src/devolaflow/codegraph/researcher.py::{build_context,
  search_symbols, get_impact, get_callers, get_affected_tests}` — the
  5 public researcher helpers consumed by L0/L1 dispatchers and L2 Tasks.
* `workflow-system/agent/templates/seeds/repo-init.yaml` —
  historical `scaffold.config.codegraph_init` provenance (suggest-tier + backgrounded per
  Track C-3 D-11; `on_failure: warn`; probe + tri-state markers per
  `references/codegraph.md` §4.6) AND `verify.config.codegraph_smoke`
  provenance (mode=full only; `on_missing: warn`; marker-aware wording).
* `workflow-system/agent/templates/seeds/{onboarding, security-audit,
  product-verification}.yaml` — historical analyze primitive's
  `config.codegraph_commands` hint (informational; L0 materializes on demand).

**Failure-mode taxonomy:**

1. **`cause="path_missing"`** — `shutil.which("codegraph")` returns
   None (CLI not installed; `npm install -g @colbymchenry/codegraph`
   never ran).
2. **`cause="timeout"`** — `subprocess.run` raised `TimeoutExpired`
   beyond the configured timeout (default 60s; cold-cache `codegraph
   context` on monorepos may need longer).
3. **`cause="nonzero_exit"`** — CLI present but the specific
   subcommand exited non-zero (corrupt `.codegraph/codegraph.db`;
   parser version drift; index incompatible with installed CLI).
4. **`cause="json_parse_error"`** — CLI returned non-JSON output where
   JSON was expected (typically empty stdout from a subcommand that
   should always emit JSON; surfaces a malformed-index signal).

**DF-side fallback:**

* The 5 researcher helpers (`build_context`, `search_symbols`,
  `get_impact`, `get_callers`, `get_affected_tests`) catch
  `CodegraphUnavailableError` and return their respective empty
  sentinels (`""`, `[]`, `{}`, `[]`, `[]`).
* The first degraded helper call in a process emits a
  research-layer **WARNING** through
  `logging.getLogger("devolaflow.codegraph.researcher")`; subsequent
  calls log at DEBUG (deduplicated via the module-level
  `_DEGRADED_MODE_NOTIFIED` sentinel) so the operator gets the signal
  once without log spam.
* Repo-init scaffold step's `codegraph_init` honours `on_failure:
  warn` — probe absent → SKIP with one hint suggesting `npm install -g
  @colbymchenry/codegraph`; probe present → background init whose
  failure lands in `.codegraph/.failed` (S-5, never silent); NEVER
  blocks scaffold either way.
* Verify smoke at mode=full honours `on_missing: warn` — the verify
  suite reports PASS even when `.codegraph/codegraph.db` is absent
  (codegraph index absence is a degraded-mode signal, not a
  verification failure).
* Gate scoring drops the `codegraph_impact` dimension when
  `get_impact()` returns `{}`; weight redistributes proportionally to
  the other gate inputs.

**Operator action:**

1. **Install the CLI**: `npm install -g @colbymchenry/codegraph` —
   ~28KB package + bundled Node runtime; MIT-licensed.
2. **Initialise the index**: `cd <repo> && codegraph init .` (the
   repo-init scaffold step launches this as a BACKGROUND task when the
   CLI is present — suggest-tier per Track C-3 D-11; progress is
   reported via the `.codegraph/.indexing|.ready|.failed` markers).
3. **Opt into auto-install**: `export DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`
   (REUSES the existing flag per W-20; NO new env flag).
4. **Verify health**: `codegraph status` reports the index path,
   symbol count, and last-sync timestamp.
5. **Forcing a sync**: `codegraph sync` flushes pending file-event
   debounce.
6. For environments deliberately running without codegraph (cost-
   conscious CI, restricted networks): no action needed — the
   degraded-mode contract preserves correctness.

**Test coverage:**
`tests/test_codegraph.py::TestRunCodegraphCli::test_path_missing_raises_unavailable`
+ `test_timeout_raises_unavailable` + `test_nonzero_exit_raises_unavailable`
+ `test_parse_json_invalid_raises_unavailable` pin the 4 structured-
cause invariants. The 5 researcher helper tests (`TestBuildContext`,
`TestSearchSymbols`, `TestGetImpact`, `TestGetCallers`,
`TestGetAffectedTests`) each pin `test_degraded_returns_empty_*`.
`TestDegradedModeNotificationDeduplication` pins the once-per-process
WARNING dedup contract.

### Section 6 — impeccable (Design refinement + anti-pattern detector) [v13.0.0]

**Trigger surfaces:**

* `pre_plugin_invocation` lifecycle hook → `ensure_plugin('impeccable')`
  (backend `npm_then_init`: `npm install -g impeccable` then
  `impeccable skills install --yes`, harness auto-detected).
* `workflow-system/agent/templates/seeds/web-design.yaml` — historical
  `refine` provenance carries `config.suggest_plugins: [impeccable]`
  (suggest tier since v15.2.0 B-6; formerly `ensure_plugins`) and historical
  `verify` provenance carries the `impeccable detect --json` assertion.

**Failure modes (the 4 plugin domain exceptions, mirroring ui-pro):**

1. **PluginInstallError** — npm registry unreachable / `npm install -g
   impeccable` non-zero.
2. **PluginNotFoundError** — plugin_id typoed in the dispatch payload.
3. **PluginVersionMismatch** — installed below
   `runtime-plugins.yaml#plugins[impeccable].min_version` (2.0.0).
4. **PluginBackendUnsupported** — environment lacks `npm`.

**Degraded behaviour:**

* `pre_plugin_invocation` catches the domain exceptions and emits
  HookViolation `PPI001` — severity `warning` since v15.2.0 B-6
  (impeccable is suggest-tier), with a one-time per-session hint;
  **the permissive default continues** (explicit `strict=True` still
  re-raises per the unchanged `finalize` contract).
* A materialized web-design verification item degrades `impeccable detect`
  to a **non-gating advisory** when the detector is unavailable — the agent
  RECORDS the lost anti-pattern signal and NEVER fabricates a PASS
  verdict (S-5: explicit signal-loss state, not a silent success).
* The detector also runs standalone via `npx impeccable detect` with no
  harness install — the recommended path for restricted-network CI.

**Operator action:**

1. **Install**: `npm install -g impeccable` (~537KB; Node 18+).
2. **Skills install**: `impeccable skills install --yes` (auto-detects
   `.cursor` / `.claude` / `.agents` / `.gemini` harness folders).
3. **Opt into auto-install**: `export DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`
   (REUSES the existing flag per W-20; NO new env flag).
4. **Standalone detector** (no harness): `npx impeccable detect src/`.

**Test coverage:**
`tests/test_degraded_mode.py::test_impeccable_unreachable_emits_ppi001_permissive_continues`
pins the PPI001 + permissive-continue invariant (mirrors the ui-pro
contract — monkeypatches `ensure_plugin` to raise `PluginInstallError`;
the handler aggregates the violation and returns a HookResult; no
exception propagates).

## Cross-References

* `docs/cycle-archive/v11.0.0/v11.0.0_patches/D-C-1.md` — PDS authoring this
  contract.
* `.cursor/rules/repo-governance.mdc::W-2` — NineS manual-fallback
  governance rule.
* `.cursor/rules/repo-governance.mdc::S-5` — "No silent failures"
  invariant every degraded path must satisfy.
* `.cursor/rules/repo-governance.mdc::S-7` — external URLs only (no
  hardcoded local paths in this reference).
* `workflow-system/agent/references/env-flags.md` §2.12 — the
  `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` flag governing ui-pro degraded
  behaviour (renumbered from §2.13 at v12.0.0 PV-03 D-2).
* `workflow-system/agent/references/env-flags.md` §2.13 — the
  `DEVOLAFLOW_SI_CHIP_DEEP` flag governing Si-Chip degraded behaviour
  (renumbered from §2.14 at v12.0.0 PV-03 D-2).
* `workflow-system/agent/references/shell-proxy.md` — the RTK / shell-
  proxy subsystem (includes `DEVOLAFLOW_RTK_PROXY`).
* `workflow-system/agent/references/evaluator-rosetta.md` — the 6 × 9
  cross-walk identifies which SI-3 axes lose their NineS-authoritative
  backing under degraded NineS.
* `tests/test_degraded_mode.py` — the regression suite that pins every
  per-plugin fallback contract documented here.
* DevolaFlow canonical URL: https://github.com/YoRHa-Agents/DevolaFlow
* NineS canonical URL: https://github.com/YoRHa-Agents/NineS
* Si-Chip canonical URL: https://github.com/YoRHa-Agents/Si-Chip
* RTK canonical URL: https://github.com/rtk-ai/rtk
* ui-pro canonical URL: https://github.com/YoRHa-Agents/ui-pro
