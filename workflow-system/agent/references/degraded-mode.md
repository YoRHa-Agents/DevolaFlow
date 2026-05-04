---
last_updated: "2026-05-04"
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

1. **Plugin-specific**: each of the 4 registered plugins (NineS, Si-Chip, RTK,
   ui-pro) has its OWN degraded-mode story; one plugin being unreachable does
   NOT imply the rest are.
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
| **ui-pro** | Skill bundle install step fails with PPI001 (permissive mode continues; strict mode blocks); any workflow listed under `runtime-plugins.yaml#plugins[*].invoked_by_workflows` for `product-verification` degrades silently on subsequent invocations. |

**What KEEPS working in ALL degraded-mode scenarios:**

* Every L0 → L1 → L2 → L3 dispatch runs to completion (the dispatcher never
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
* **A cycle retrospective is being authored** (W-7 / SI-8) and any of the 4
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
| ui-pro | https://github.com/YoRHa-Agents/ui-pro | `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` (opt-IN) | `pre_plugin_invocation` hook; `ensure_plugin('ui-pro')`; `uipro init --ai cursor --global` | `PluginInstallError` (npm registry unreachable); `PluginNotFoundError` (registry typo); `PluginVersionMismatch` | PPI001 error (permissive mode); dispatch continues; strict mode blocks | Check npm registry reachability OR set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` to bypass | `tests/test_degraded_mode.py::test_ui_pro_unreachable_emits_ppi001_permissive_continues` |

### Section 1 — NineS (Deep-analysis evaluator)

**Trigger surfaces (file:line citations relative to repo root):**

* `W-2 / SI-2 nines analyze` — invoked during every MINOR cycle's SI-1
  planning gate (`.cursor/rules/repo-governance.mdc::W-2`) and end-of-
  iteration self-evaluation.
* `D-N-2 code_coverage` collector path — documented in
  `.local/research/v10.3.0_retrospective.md` §3 row "NineS A1 ticket —
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
   `.local/research/v10.2.3_iteration_round1.md` §1. Closed by v10.2.3
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
  HookViolation `PPI001` (severity `error`); **in permissive mode
  (default) the dispatch continues**; the violation is aggregated onto
  the HookResult for observers.
* In strict mode (opt-in via `strict=True` in `run_hooks`), the
  top-severity violation re-raises.
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

## Cross-References

* `.local/research/v11.0.0_patches/D-C-1.md` — PDS authoring this
  contract.
* `.cursor/rules/repo-governance.mdc::W-2` — NineS manual-fallback
  governance rule.
* `.cursor/rules/repo-governance.mdc::S-5` — "No silent failures"
  invariant every degraded path must satisfy.
* `.cursor/rules/repo-governance.mdc::S-7` — external URLs only (no
  hardcoded local paths in this reference).
* `workflow-system/agent/references/env-flags.md` §2.13 — the
  `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` flag governing ui-pro degraded
  behaviour.
* `workflow-system/agent/references/env-flags.md` §2.14 — the
  `DEVOLAFLOW_SI_CHIP_DEEP` flag governing Si-Chip degraded behaviour.
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
