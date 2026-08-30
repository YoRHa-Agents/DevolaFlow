---
last_updated: "2026-08-25"
---

# Upstream-Unreachable Degraded-Mode Contract

## ⚠️ Degraded ≠ Full — Read This First

**Degraded mode is NOT "DevolaFlow works offline." Degraded mode is "DevolaFlow
does NOT crash when a specific upstream plugin is unreachable, AND the
surrounding dispatcher / skill workflow continues with the EXPECTED loss of
signal from that plugin."**

When an operator reads this reference and takes away "all upstream-dependent
surfaces are available offline," they have misunderstood the contract. The
contract is narrower:

1. **Plugin-specific**: each registered plugin has its OWN degraded-mode
   story; one plugin
   being unreachable does NOT imply the rest are.
2. **Signal loss is EXPECTED**: ui-pro skipping on install means the skill
   bundle is missing the ui-pro surface.

**What STOPS working when each plugin is unreachable:**

| Plugin | What STOPS working |
|---|---|
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
* **A cycle retrospective is being authored** (W-7 / SI-8) and any of the
  plugins was not available during the cycle — the retrospective MUST
  enumerate the signal loss.
* **A new plugin is being proposed** for addition to
  `runtime-plugins.yaml` — each new plugin needs a matching degraded-mode
  contract entry HERE before it can be marked READY (per the v11.0.0 D-C-1
  admission gate precedent).
* **A PR touches `lifecycle/pre_plugin_invocation.py`,
  or any catch-handler for plugin domain
  exceptions** — re-read the per-plugin section below to confirm the existing
  contract before modifying.

The exact seed ID `nines-assisted` is an opaque historical compatibility key
only; it does not denote an active external evaluator, runtime plugin, or
degraded-mode contract. This reference is `important`-tier for most task types
and `critical`-tier for `self-update` / `product-verification` workflows where
multi-plugin coordination is the primary deliverable.

## Body

### Plugin Matrix — Quick Lookup

| Plugin | Canonical URL | Env flag | Trigger surface | Failure-mode taxonomy | DF-side fallback | Operator action | Test |
|---|---|---|---|---|---|---|---|
| ui-pro | https://github.com/YoRHa-Agents/ui-pro | `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (opt-IN) | `pre_plugin_invocation` hook; `ensure_plugin('ui-pro')`; `uipro init --ai cursor --global` | `PluginInstallError` (npm registry unreachable); `PluginNotFoundError` (registry typo); `PluginVersionMismatch` | PPI001 warning (suggest tier, v15.2.0 B-6) + one-time hint; permissive default continues (explicit strict=True still re-raises) | Check npm registry reachability OR set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` to bypass | `tests/test_degraded_mode.py::test_ui_pro_unreachable_emits_ppi001_permissive_continues` |
| codegraph | https://github.com/colbymchenry/codegraph | `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (opt-IN; **REUSED**, no new flag per W-20) | `devolaflow.codegraph.researcher` helpers; repo-init scaffold and verify provenance | `CodegraphUnavailableError` with structured `cause` (`path_missing` / `timeout` / `nonzero_exit` / `json_parse_error`) | Helpers return empty sentinels and log an explicit warning; callers fall back to Read/Glob/Grep; absent index never blocks required workflows | Install via `npm install -g @colbymchenry/codegraph` or opt into the runtime installer; no action is needed when deliberately degraded | `tests/test_codegraph.py` |
| impeccable | https://github.com/pbakaus/impeccable | `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (opt-IN; **REUSED**, no new flag per W-20) | `pre_plugin_invocation` hook; `ensure_plugin('impeccable')`; web-design refine/verify seed hints; `impeccable detect --json` check | `PluginInstallError` (npm registry unreachable); `PluginNotFoundError` (registry typo); `PluginVersionMismatch`; detector binary missing | PPI001 warning (suggest tier, v15.2.0 B-6) + one-time hint; permissive default continues (explicit strict=True still re-raises); verify evidence becomes a non-gating advisory (signal loss recorded, never fabricated PASS) | Check npm registry reachability OR run `npx impeccable detect` standalone OR set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` to bypass | `tests/test_degraded_mode.py::test_impeccable_unreachable_emits_ppi001_permissive_continues` |

### Section 0 — Capability-Probe → Recipe Selection (first-class mechanism) [v15.2.0 B-6]

Degraded mode is no longer only a warn-and-continue afterthought: since
v15.2.0 B-6 (04 §8.2) **every plugin dependency point declares a 4-tuple**
and the consuming agent SELECTS a recipe instead of failing:

| Field | Meaning |
|---|---|
| Probe | zero-IO capability check (CLI on PATH via `shutil.which`, installed skill dir exists, or an equivalent built-in tool — e.g. no codegraph but `rg` present → research recipe degrades to rg) |
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

### Section 3 — ui-pro (Skill bundle installer)

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

**Trigger surfaces:**

* `src/devolaflow/codegraph/_cli.py::run_codegraph_cli` owns every
  `codegraph` subprocess invocation and raises `CodegraphUnavailableError`
  with a structured `cause`.
* `src/devolaflow/codegraph/researcher.py` provides
  `build_context`, `search_symbols`, `get_impact`, `get_callers`, and
  `get_affected_tests` for L0/L1 planning and L2 tasks.
* The four analyze-oriented seeds retain Codegraph-aware provenance;
  repo-init records the capability and the scaffold/verify contract.

**Failure-mode taxonomy:**

1. `cause="path_missing"` — `shutil.which("codegraph")` returns None.
2. `cause="timeout"` — the CLI exceeds the configured timeout.
3. `cause="nonzero_exit"` — the CLI subcommand fails.
4. `cause="json_parse_error"` — JSON output is empty or malformed.

**DF-side fallback:**

* Researcher helpers catch `CodegraphUnavailableError` and return their
  empty sentinels (`""`, `[]`, `{}`, `[]`, `[]`).
* The first degraded helper call emits a WARNING through
  `devolaflow.codegraph.researcher`; subsequent calls are DEBUG-only.
* Repo-init treats Codegraph as `tier: suggest`: a missing CLI skips the
  optional index with one hint, while a present CLI may initialize the index
  in the background. `.codegraph/.indexing`, `.ready`, and `.failed` make
  progress and failure explicit; neither state blocks required workflows.
* Callers use Read/Glob/Grep when the empty sentinel signals degradation.

**Operator action:**

1. Install the CLI with `npm install -g @colbymchenry/codegraph`.
2. Initialize with `codegraph init .`; inspect health with `codegraph status`.
3. For restricted-network environments, no action is required: correctness
   remains available through the built-in fallback.

**Test coverage:** `tests/test_codegraph.py`,
`tests/test_codegraph_markers.py`, and
`tests/test_codegraph_workflow_wiring.py` pin the CLI, marker, researcher,
and workflow contracts.

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
* `.cursor/rules/repo-governance.mdc::S-5` — "No silent failures"
  invariant every degraded path must satisfy.
* `.cursor/rules/repo-governance.mdc::S-7` — external URLs only (no
  hardcoded local paths in this reference).
* `workflow-system/agent/references/env-flags.md` §2.12 — the
  `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` flag governing ui-pro degraded
  behaviour (renumbered from §2.13 at v12.0.0 PV-03 D-2).
* `workflow-system/agent/references/memory-router.md` — planning-time
  memory-case routing.
* `tests/test_degraded_mode.py` — the regression suite that pins every
  per-plugin fallback contract documented here.
* DevolaFlow canonical URL: https://github.com/YoRHa-Agents/DevolaFlow
* ui-pro canonical URL: https://github.com/YoRHa-Agents/ui-pro
