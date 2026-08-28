# Loop v3 Phase 0: Plugin Coupling and Cleanup Audit

## Scope and conclusion

This is a read-only audit of the five rows currently registered in
`workflow-system/agent/knowledge/runtime-plugins.yaml`: `ui-pro`, `rtk`,
`si-chip`, `codegraph`, and `impeccable`. The runtime registry is treated as
the registration SSOT. `workflow-system/agent/plugins.yaml` is treated as the
derived capability, role, and stage-mapping view.

All five rows have a proven live contract. No row meets the threshold for
remove + fully decouple. The current disposition is therefore retention with
explicit optionality, while several coupling and parity problems should be
addressed in a later implementation change:

1. The derived view still contains operational-looking commands and workflow
   claims that are not consumed by the runtime installer and can drift from the
   SSOT.
2. The `curl_install_script` backend applies a generic Cargo fallback to
   `si-chip`, although the Si-Chip row is a hosted installer-script
   integration rather than a demonstrated Rust package.
3. `upgrade_plugin()` executes only `upgrade_cmd` and does not rerun the
   `npm_then_init` integration step. Upgrades for `ui-pro`, `codegraph`, and
   `impeccable` therefore verify the CLI version but do not prove that their
   agent or skill integration files were refreshed.
4. `codegraph` has a substantial documented and tested public wrapper, but no
   production Python caller outside its own package was found. Its current
   live consumption is primarily agent-facing seed/reference wiring and the
   exported API; evidence for automatic use by gate scoring or selective-test
   execution is INSUFFICIENT.
5. `nines-assisted` remains a historical workflow identifier in the Si-Chip
   registration and tests. It is a live template/registry path, but its
   historical naming and single-provider mapping should be reviewed separately
   from the removed NineS plugin.

## Evidence model

Evidence was classified as follows:

- **Confirmed runtime**: a source-level caller invokes the plugin bridge,
  lifecycle hook, installer, or proxy.
- **Confirmed agent-facing**: workflow seeds, SKILL navigation, references, or
  context profiles declare the plugin as a task-stage primitive.
- **Confirmed contract**: tests pin the registry row, command shape, degraded
  behavior, or public API.
- **INSUFFICIENT**: the repository documents or exports a surface, but no
  production caller proving automatic execution was found.

No network, external plugin installation, or plugin binary invocation was
performed for this audit.

## Shared architecture and coupling

### Registry ownership and loading

`workflow-system/agent/knowledge/runtime-plugins.yaml` owns membership,
canonical IDs, backends, install and upgrade commands, version floors,
canonical URLs, and `invoked_by_workflows` (lines 11-22). The five rows are
defined at lines 90-276. `src/devolaflow/_plugin_installer/specs.py` loads and
validates this registry, resolves workflow matches, and constructs
`RuntimePluginSpec` objects (lines 141-193 and 262-320).

`workflow-system/agent/plugins.yaml` declares itself derived and mirrors the
five IDs and their order (lines 1-18 and 29-194). Its presentation data is
loaded by `src/devolaflow/plugins/loader.py`, while
`src/devolaflow/plugins/registry.py` exposes the compatibility
`PluginRegistry`/`PluginSpec` surface. The only source-level construction of
that compatibility registry found outside the plugin package is the adapter
build path in `src/devolaflow/build_skill.py` lines 17-18 and 67-91, where the
import is from `devolaflow.adapters.registry`, not the plugin registry.
Consequently, production use of the legacy plugin capability view is
INSUFFICIENT; tests and compatibility exports are confirmed.

### Common lifecycle

`src/devolaflow/lifecycle/pre_plugin_invocation.py` resolves plugin IDs from
`plugin_ids`, `plugin_id`, or the dispatch `workflow` field (lines 271-331).
Workflow matching reads `runtime-plugins.yaml#plugins[*].invoked_by_workflows`.
When `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` is exactly `"1"`, the install path
passes `auto_install=True`; otherwise the hook is a zero-I/O, zero-subprocess
no-op (module documentation and lines 135-148).

`src/devolaflow/init_project.py` lines 144-207 implements a separate explicit
bundle surface: a global initialization invokes `ensure_plugin()` for every
runtime registry row, unless `--no-plugins` is supplied. Individual failures
are warning-only and do not abort the bundle.

All five rows inherit the registry default `tier: suggest`, and the registry
default `auto_install: false` at lines 278-287. Thus normal probing and
dispatch are optional; explicit global installation and the opt-in lifecycle
flag are the only automatic network-install surfaces confirmed here.

`src/devolaflow/_plugin_installer/refresh.py` provides the CLI-facing
inspection and daily refresh surfaces. It treats every row as stale when no
install event exists and calls `upgrade_plugin()` for stale entries
(lines 21-111). The shared version probe returns `None` for nonzero or
unparseable checks, which is safe but can conflate unavailable and
unrecognized installations.

## Plugin-by-plugin audit

## 1. `ui-pro`

### Live consumers

- **Runtime installer and lifecycle:** the row at
  `workflow-system/agent/knowledge/runtime-plugins.yaml` lines 90-112 is
  resolved by `ensure_plugin()` and by workflow-based pre-plugin invocation.
  The `npm_then_init` backend runs `npm install -g uipro-cli`, then
  `uipro init --ai {ai_platform} --global` for `cursor`, `claude`, and `codex`.
- **Agent-facing workflow:** `workflow-system/agent/templates/seeds/web-design.yaml`
  declares the design-stage UI primitive and pairs `ui-pro` with `impeccable`.
  `tests/test_template_web_design.py` lines 56-67 confirms that both rows are
  registered for `web-design`; lines 69-79 pins the downstream
  `antipatterns-clear` verification assertion.
- **Documentation and navigation:** `workflow-system/agent/SKILL.md` lines
  231-233 references the plugin-adjacent workflow capability, and the
  reference set includes `workflow-system/agent/references/degraded-mode.md`
  and the UI-related integration documentation.
- **Shape contract:** `tests/integration/test_ui_pro_shape_contract.py`
  lines 16-35 pins the `uipro init --ai cursor --global` success-log markers
  (`[uipro]`, `init complete`, `exit_code=0`, `scope=global`, and
  `ai=cursor`).

No dedicated Python UI bridge or source-level call to the `uipro` binary was
found. The live execution contract is installer/lifecycle plus agent-facing
workflow instructions; automatic design invocation from Python is
INSUFFICIENT.

### Public and degraded contract

The public contract is the `uipro` CLI plus its initialized harness skill
files. Successful installation must satisfy the version floor `2.0.0`, then
the init command must succeed for all declared targets. A missing or failed
install is a suggest-tier `PPI001` warning in permissive mode and does not
block dispatch. `tests/test_degraded_mode.py` lines 229-291 confirms this
behavior for `ui-pro`, including strict-mode re-raise.

The shape test is fixture-based rather than a live upstream invocation.
Future upstream output compatibility is therefore covered at the expected
log-shape level, but actual current upstream behavior is INSUFFICIENT.

### Installation and optionality

- Backend: `npm_then_init`.
- Install: `npm install -g uipro-cli`.
- Integration: `uipro init --ai {ai_platform} --global`.
- Targets: `cursor`, `claude`, `codex`.
- Probe: `uipro --version`.
- Default: suggest-tier and no automatic installation unless the operator
  explicitly uses `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` or global
  `devola-init` without `--no-plugins`.

The row is optional in normal operation, but the global bundle currently
attempts all five plugins together. This means a nominally optional UI tool
still participates in a network-heavy global install unless the user opts out
of the entire bundle.

### Actual dependency and coupling points

- `pre_plugin_invocation` couples `ui-pro` to every workflow whose runtime row
  contains `invoked_by_workflows`, not to a dedicated UI stage executor.
- `web-design` couples the UI design assertion to `impeccable`'s later
  anti-pattern gate, making the pair a workflow-level composition rather than
  independent plugins.
- The derived view at `workflow-system/agent/plugins.yaml` lines 33-70
  exposes `stage_mapping`, platform install commands, update, and uninstall
  commands. Those are not fields in `RuntimePluginSpec` and are not executed
  by the runtime installer.
- `plugins.yaml` advertises `demo-showcase`, `full-pipeline`, and
  `feature-enhancement` at lines 53-57, while the runtime SSOT advertises only
  `product-verification` and `web-design` at lines 107-112. Because the view
  is presentation data, this is not a registration violation, but it is a
  concrete operator-facing parity hazard.
- `plugins.yaml` line 36 says `version_command: "uipro versions"` while the
  runtime SSOT line 102 uses `uipro --version`. The derived loader can expose
  this stale probe to compatibility callers. This is confirmed drift in
  operational-looking presentation data.
- The derived view's `stage_mapping` uses
  `.cursor/skills/ui-ux-pro-max/...` (line 60), while the canonical plugin ID
  is `ui-pro` and the runtime initialization command is `uipro init`. The
  upstream payload path may be intentional, but the source of that path and
  its current validity are INSUFFICIENT.

### Parity evidence

Confirmed:

- ID and order parity is enforced by
  `tests/test_plugins.py::TestV15PluginRegistryUnification`.
- `min_version` and repository URL parity are documented in
  `workflow-system/agent/plugins.yaml` lines 10-14.
- `tests/test_runtime_plugins_smoke.py` covers the runtime row shape.
- `tests/test_template_web_design.py` covers UI/refinement workflow parity.
- `tests/integration/test_ui_pro_shape_contract.py` covers the init log shape.

Not confirmed:

- Whether all three declared init targets remain supported by the current
  upstream CLI is INSUFFICIENT.
- Whether the derived stage commands are consumed by any production caller is
  INSUFFICIENT.

### Recommended disposition

**Keep + explicit optional.** `ui-pro` has a live web-design contract and a
tested install/degraded path. It should remain suggest-tier, but the derived
view should be reduced to non-authoritative presentation data or synchronized
for version/probe/workflow claims. The cleanup priority is to remove or clearly
label stale operational fields and to make any global bundle install profile
explicitly UI-optional.

## 2. `rtk`

### Live consumers

- **Runtime installer:** the row at
  `workflow-system/agent/knowledge/runtime-plugins.yaml` lines 114-127
  installs and verifies RTK, including the collision discriminator
  `rtk gain`.
- **Shell proxy runtime:** `src/devolaflow/shell_proxy/proxy.py` owns the
  command-rewrite behavior and checks PATH availability, the strict
  `DEVOLAFLOW_RTK_PROXY=1` activation flag, and `rtk gain`.
- **Lifecycle hook:** `src/devolaflow/lifecycle/pre_shell_call.py` lines
  111-144 delegates to `ShellProxy.wrap_command()` and returns
  `wrapped_cmd`, `proxy_enabled`, and `was_rewritten`.
- **Whitelist and recipe layers:** `src/devolaflow/shell_proxy/registry.py`
  is the single owner of rewrite whitelist rules; `src/devolaflow/shell_proxy/commands.py`
  provides local command-mapping recipes. Both are explicitly described as
  RTK stack components in `workflow-system/agent/references/shell-proxy.md`.
- **Tests:** `tests/test_shell_proxy.py`,
  `tests/test_shell_proxy_commands.py`,
  `tests/test_shell_proxy_disabled_is_noop.py`, and
  `tests/integration/test_rtk_shape_contract.py` cover runtime behavior,
  disabled behavior, local recipes, and captured stdout shape.

RTK has the clearest non-installer production consumer among the five rows.

### Public and degraded contract

When `DEVOLAFLOW_RTK_PROXY` is not exactly `"1"`, the hook preserves the
original command and performs no RTK subprocess work. When enabled, only
whitelisted commands are rewritten; Tier 2 commands require
`DEVOLAFLOW_RTK_PROXY_TIER2=1`. Missing RTK, a failing `rtk gain`, an
unwhitelisted command, or a proxy warning results in safe passthrough.

`tests/test_degraded_mode.py` lines 175-225 confirms that the flag-on plus
missing-binary path leaves the command unchanged and exposes diagnostic
metadata. `tests/integration/test_rtk_shape_contract.py` lines 16-76 pins the
captured `rtk rewrite` output shape.

### Installation and optionality

- Backend: `curl_install_script`.
- Install and upgrade: the RTK hosted install script.
- Probe: `rtk --version`.
- Minimum version: `0.37.2`.
- Distinguish check: `rtk gain`.
- Default: suggest-tier, flag-off, no runtime install unless explicitly
  opted into plugin lifecycle or global plugin bundling.

The proxy is independently optional even when RTK is installed. Installing
the binary does not activate command rewriting.

### Actual dependency and coupling points

- The lifecycle hook is coupled to `ShellProxy`, but rewrite rules remain
  centralized in `shell_proxy/registry.py`; this is a healthy single-owner
  boundary.
- RTK's name collision with `rtk-type-kit` is a real external dependency on
  the `rtk gain` discriminator and the upstream install warning.
- The derived view at `workflow-system/agent/plugins.yaml` lines 76-90
  describes RTK as automatic and env-flag-driven, which is consistent with
  the proxy but is not used by the runtime install path.
- The registry's generic curl backend falls back to Cargo on any curl failure.
  This is appropriate only if the declared canonical resource is a Cargo
  repository; the current RTK row has no explicit Cargo capability field, so
  fallback correctness depends on an unstated upstream packaging assumption.
- The RTK row is listed under `invoked_by_workflows: shell-proxy`, although
  the source comments correctly explain that `shell-proxy` is an activation
  surface rather than a template workflow. This naming is useful for lookup,
  but it mixes workflow and hook concepts.

### Parity evidence

Confirmed:

- Runtime and derived-view ID/order parity is pinned by
  `tests/test_plugins.py::TestV15PluginRegistryUnification`.
- The RTK row and distinguish command are covered by
  `tests/test_runtime_plugins_smoke.py` and `tests/test_plugins.py`.
- `tests/test_degraded_mode.py` covers missing-binary behavior.
- `tests/integration/test_rtk_shape_contract.py` covers the bridge shape.
- `tests/test_shell_proxy_disabled_is_noop.py` covers strict default-off
  behavior.

INSUFFICIENT:

- No live upstream install was performed, so current installer-script output
  and Cargo fallback compatibility are not independently verified.

### Recommended disposition

**Keep + explicit optional.** RTK is a confirmed live runtime integration.
Keep the env-flag default-off contract. Cleanup should separate shell-hook
activation metadata from template workflow metadata and make the fallback
backend explicit rather than inheriting the generic Cargo behavior.

## 3. `si-chip`

### Live consumers

- **Public bridge:** `src/devolaflow/si_chip_bridge/__init__.py` lines 1-97
  exports the typed bridge surface, including `profile`, `count_tokens`,
  `evaluate`, `aggregate_delta`, `apply_or_defer`, and
  `run_dogfood_cycle`.
- **Bridge runner:** `src/devolaflow/si_chip_bridge/runner.py` wraps
  `profile_static.py`, `count_tokens.py`, and `aggregate_eval.py`.
- **Dispatch bridge:** `src/devolaflow/dispatch.py` lines 228-295 exposes
  `dispatch_dogfood_cycle()` for workflow callers and maps
  `skill-optimization`, `self-update`, and `nines-assisted` to the
  DevolaFlow ability.
- **Lifecycle hook:** `src/devolaflow/lifecycle/post_skill_edit.py` invokes
  the dogfood cycle after skill-corpus edits when
  `DEVOLAFLOW_SI_CHIP_DEEP=1`.
- **Runtime lifecycle:** the SSOT row at lines 129-177 resolves Si-Chip for
  the three historical self-improvement workflows.
- **Tests:** `tests/test_si_chip_bridge.py`,
  `tests/integration/test_si_chip_shape_contract.py`,
  `tests/test_dispatch_dogfood_cycle.py`,
  `tests/test_post_skill_edit_hook.py`,
  `tests/test_sichip_iteration_delta_gate.py`, and
  `tests/test_plugin_sichip_registration.py` cover public API, parser shapes,
  dispatch, lifecycle activation, thresholds, and registration.

This is a confirmed runtime bridge, not merely a registry declaration.

### Public and degraded contract

The bridge locates an installation through `find_si_chip_install()`, supports
the `SI_CHIP_HOME` override and known nested install layout, and raises
`SiChipUnavailable` when scripts are absent. The runner raises typed
`SiChipError` for subprocess or malformed-output failures. The lifecycle
surface records an explicit PSE001/deferred result when Si-Chip is unavailable
rather than silently applying a change.

`tests/test_si_chip_bridge.py` lines 58-92 pins the package export surface and
lines 101-200 cover install resolution. The integration shape tests cover
current nested and legacy YAML layouts in
`tests/integration/test_si_chip_shape_contract.py` lines 22-111.

### Installation and optionality

- Backend: `curl_install_script`.
- Install and upgrade: the hosted Si-Chip installer script, targeting the
  global Cursor skill location.
- Probe: a `python3` command that imports
  `devolaflow.si_chip_bridge`, resolves the installation, and reads the
  installed `SKILL.md` version.
- Minimum version: `0.4.0`.
- Default: suggest-tier; deep post-edit automation requires
  `DEVOLAFLOW_SI_CHIP_DEEP=1`, while direct dispatch API calls are explicit
  Python opt-ins.

The row is optional for ordinary workflow execution. It is operationally
important to self-improvement workflows, but those workflows have a defined
deferred path.

### Actual dependency and coupling points

- The version probe is CWD-sensitive: the registry itself states that it
  requires a DevolaFlow checkout containing `src/devolaflow/` (lines 154-162).
  This couples a global plugin status check to the DevolaFlow source tree.
- The install resolver independently searches several home and nested paths.
  That is necessary for the known upstream packaging defect, but it creates a
  compatibility burden across installer, bridge, and tests.
- `post_skill_edit` couples every edit under
  `workflow-system/agent/` to a possible Si-Chip dogfood pass when the deep
  flag is enabled. This is intentionally cross-cutting, but broader than the
  three registry workflows.
- The generic curl backend always falls back to
  `cargo install --git <canonical_url>` on primary failure
  (`src/devolaflow/_plugin_installer/backends.py` lines 262-321). No evidence
  was found that the Si-Chip canonical repository is a Cargo-installable
  binary. This is the strongest concrete backend over-coupling finding:
  a Si-Chip installer failure can trigger an unrelated Rust fallback and
  produce misleading remediation.
- `workflow-system/agent/plugins.yaml` uses `cli_binary: "python"` and a
  version command that is not a simple binary probe (lines 92-106). This is
  presentation metadata, but it can make Si-Chip look like a Python CLI rather
  than a skill payload with scripts.
- `plugins.yaml` stage mappings use home-directory paths and bare `python`
  (lines 120-123), while the runtime source explicitly moved to `python3` for
  portability. The stage mappings are therefore stale or at least
  inconsistent with the runtime contract.
- Upgrade execution runs only the row's `upgrade_cmd`; it does not rerun a
  separate skill refresh step. For Si-Chip the hosted script may itself
  refresh the payload, but that behavior is not represented as a backend
  contract and is INSUFFICIENT without live verification.

### Parity evidence

Confirmed:

- Runtime registration, workflow resolution, and absence of an RTK-style
  discriminator are covered by `tests/test_plugin_sichip_registration.py`.
- Public bridge exports and parser shape are covered by
  `tests/test_si_chip_bridge.py` and
  `tests/integration/test_si_chip_shape_contract.py`.
- Dispatch and deep lifecycle wiring are covered by
  `tests/test_dispatch_dogfood_cycle.py` and
  `tests/test_post_skill_edit_hook.py`.
- The runtime probe uses `python3`; the changelog records this portability
  correction at `CHANGELOG.md` lines 390-393.

Confirmed drift/risk:

- Derived stage mappings still use bare `python` and hard-coded home paths.
- The registry comment says the bridge consumes three scripts, while the
  public surface also exposes evaluation and model/result abstractions; exact
  current upstream payload parity is INSUFFICIENT.

### Recommended disposition

**Keep + explicit optional.** Si-Chip has the strongest typed bridge and
workflow contract after RTK. The cleanup priority is to decouple the
curl-script backend from an unconditional Cargo fallback, and to replace
CWD-sensitive version probing with a dedicated installation/status contract in
a later change. Keep deep self-improvement opt-in and preserve explicit
defer behavior.

## 4. `codegraph`

### Live consumers

- **Runtime installer:** the row at
  `workflow-system/agent/knowledge/runtime-plugins.yaml` lines 179-233 uses
  `npm_then_init`, installs `@colbymchenry/codegraph`, and initializes
  harness integration files.
- **Public CLI wrapper:** `src/devolaflow/codegraph/_cli.py` is the single
  subprocess owner and returns structured unavailable causes.
- **Public researcher API:** `src/devolaflow/codegraph/researcher.py` exports
  `build_context`, `search_symbols`, `get_impact`, `get_callers`, and
  `get_affected_tests`. The wrappers return empty sentinels and issue
  one-time warnings on degraded mode; for example, `build_context` is
  defined at lines 97-138 and `get_impact` at lines 190-221.
- **Marker protocol:** `src/devolaflow/codegraph/markers.py` coordinates
  background indexing with `.codegraph/.indexing`, `.ready`, and `.failed`.
- **Agent-facing workflow seeds:** `repo-init`, `onboarding`,
  `security-audit`, and `product-verification` contain codegraph analysis or
  initialization assertions. `tests/test_codegraph_workflow_wiring.py`,
  `tests/test_codegraph_markers.py`, and
  `tests/ghost/test_features_v12_5.py` pin these surfaces.
- **SKILL and references:** `workflow-system/agent/SKILL.md` lines 80-83 and
  231-233 advertise indexed planning and backgrounded repo-init behavior;
  `workflow-system/agent/references/codegraph.md` documents the CLI, MCP,
  integration map, and degraded contract.

No production Python module outside `src/devolaflow/codegraph/` was found to
import or call the researcher helpers. The automatic use of those helpers by
gate scoring, L0/L1 planning, or selective-test execution is therefore
INSUFFICIENT. The agent-facing seed and reference wiring is confirmed live,
and the public API is confirmed exported and tested.

### Public and degraded contract

The CLI wrapper logs warnings and raises `CodegraphUnavailableError` with one
of `path_missing`, `timeout`, `nonzero_exit`, or `json_parse_error`.
Researchers catch that error and return the documented empty sentinel:
`""` for context, `[]` for list results, and `{}` for impact. Callers are
expected to fall back to Read/Glob/Grep or manual impact analysis.

`tests/test_codegraph.py` covers subprocess invocation and degraded modes;
`tests/test_codegraph_markers.py` lines 36-104 covers marker transitions and
malformed marker payloads. `tests/test_degraded_mode.py` covers the
operator-facing degraded documentation and plugin scenario matrix.

### Installation and optionality

- Backend: `npm_then_init`.
- Install: `npm install -g @colbymchenry/codegraph@latest`.
- Harness integration: `codegraph install --target {ai_platform} --yes` for
  `cursor`, `claude`, and `codex`.
- Probe: `codegraph --version`.
- Minimum version: `0.9.3`.
- Project indexing: separate `codegraph init` operation, backgrounded in the
  repo-init seed when the CLI exists.
- Default: suggest-tier and non-blocking; runtime installation requires the
  existing auto-install opt-in.

The repo-init index is deliberately separate from plugin installation. This
is a sound boundary, but the seed still couples repo initialization to a
potentially large external indexing process.

### Actual dependency and coupling points

- `repo-init` couples scaffold behavior to the codegraph CLI and marker
  protocol, although `src/devolaflow/local/workspace.py` now deterministically
  owns the `.codegraph/` gitignore entry regardless of codegraph outcome.
- Four seeds and the context profile advertise command recipes, while the
  Python researcher API is not wired into those source-level workflow
  executors. This is a split between agent instruction and executable
  integration.
- `plugins.yaml` lines 125-157 advertises both npm and hosted-script install
  methods, while the runtime SSOT declares only `npm_then_init`. The view's
  script method is not represented in `RuntimePluginSpec` and is an
  actionable parity/maintenance hazard.
- The derived view advertises `refactoring` and
  `performance-optimization` (lines 146-152), while the runtime row resolves
  only `repo-init`, `onboarding`, `security-audit`, and
  `product-verification` (lines 229-233). The runtime comment calls the two
  extra names forward-compatible declarations, but no implementation consumer
  was found.
- `plugins.yaml` stage mappings include `codegraph init -i` and commands that
  differ from the runtime's documented `codegraph init <project_root>` and
  `codegraph install --target ...` split. Which mapping is authoritative for
  agents is INSUFFICIENT.
- The wrapper's promise that `get_affected_tests()` can support selective CI
  execution is explicitly telegraphed for a future cycle in
  `src/devolaflow/codegraph/researcher.py` lines 258-272. It is not a live
  consumer today.
- The generic `npm_then_init` upgrade path does not rerun
  `codegraph install`; CLI version freshness and harness-file freshness can
  diverge.

### Parity evidence

Confirmed:

- ID/order and min-version/repository parity are covered by
  `tests/test_plugins.py` and the runtime smoke tests.
- Workflow wiring is covered by
  `tests/test_codegraph_workflow_wiring.py` and the W-18 stanza in
  `tests/ghost/test_features_v12_5.py`.
- CLI wrapper and researcher behavior are covered by
  `tests/test_codegraph.py`.
- Marker behavior is covered by `tests/test_codegraph_markers.py`.
- Reference documentation is covered by
  `tests/test_codegraph_reference_doc.py`.

INSUFFICIENT:

- No source-level caller proves that the researcher API is used
  automatically by the advertised gate/planning consumers.
- No live upstream CLI or MCP invocation was performed.

### Recommended disposition

**Keep + explicit optional.** The plugin has a substantial documented,
tested, and exported contract, even though its automatic Python consumption
is not proven. Cleanup should remove the unconsumed install-script and
forward-workflow claims from the derived view or clearly mark them as
planned, and should either wire researcher calls to real consumers or narrow
the public documentation to the currently live agent-facing path.

## 5. `impeccable`

### Live consumers

- **Runtime installer:** the row at
  `workflow-system/agent/knowledge/runtime-plugins.yaml` lines 235-276 uses
  `npm_then_init`, installs `impeccable`, and runs
  `impeccable skills install --yes`.
- **Agent-facing workflow:** `workflow-system/agent/templates/seeds/web-design.yaml`
  couples `impeccable` to refinement and verification. The seed's
  `antipatterns-clear` assertion is pinned by
  `tests/test_template_web_design.py` lines 69-79.
- **Reference contract:** `workflow-system/agent/references/impeccable.md`
  documents the commands and detector. `tests/test_impeccable_reference_doc.py`
  lines 22-65 pins its six sections, canonical URL, and detector exit-code
  contract.
- **Degraded lifecycle:** `tests/test_degraded_mode.py` lines 293-340
  confirms suggest-tier PPI001 behavior for install failure.

No Python wrapper, detector subprocess bridge, or source-level invocation of
the `impeccable` binary was found. Current execution is installer/lifecycle
plus agent instructions and deterministic verification semantics in the
seed/reference contract; automatic Python detector execution is
INSUFFICIENT.

### Public and degraded contract

The public contract is the 23-command `/impeccable` skill plus
`impeccable detect`. The reference and tests document detector exit `0` as
clean and exit `2` as anti-patterns found. Missing or failed installation is
suggest-tier PPI001 warning/permissive-continue, with strict mode raising the
hook violation.

### Installation and optionality

- Backend: `npm_then_init`.
- Install: `npm install -g impeccable`.
- Integration: `impeccable skills install --yes`, with upstream
  auto-detection of available harnesses.
- Probe: `impeccable --version`.
- Minimum version: `2.0.0`.
- Default: suggest-tier and not automatically installed unless explicit
  plugin lifecycle or global bundle installation is requested.

The runtime's sentinel `init_targets: [auto]` is a backend implementation
detail for running the auto-detecting skill installation exactly once.

### Actual dependency and coupling points

- `web-design` couples UI design from `ui-pro` to refinement and detector
  verification from `impeccable`. This is a deliberate staged composition,
  not a duplicate implementation.
- `plugins.yaml` lines 159-194 exposes provider-specific `platform_install`
  commands and an `update_command` using `npx`, while the runtime row uses
  `npm` package installation and does not model platform providers. These
  fields are useful documentation but are not part of the runtime lifecycle
  contract.
- The runtime upgrade path runs only `npm install -g impeccable@latest` and
  does not run `impeccable skills update`; therefore package freshness and
  installed skill freshness can diverge.
- `plugin_roles.ui_refinement` is a derived role with no Python consumer found.
  Its actual live use is the web-design seed and operator-facing guidance.
- The detector contract is documented and asserted structurally, but no
  production verifier invokes the detector. Automatic gate integration is
  INSUFFICIENT.

### Parity evidence

Confirmed:

- ID/order and min-version/repository parity are covered by
  `tests/test_plugins.py::TestV15PluginRegistryUnification`.
- Runtime shape is covered by
  `tests/test_runtime_plugins_smoke.py`.
- Web-design pairing is covered by
  `tests/test_template_web_design.py` and
  `tests/ghost/test_features_v13_0.py`.
- Reference and detector documentation are covered by
  `tests/test_impeccable_reference_doc.py`.
- Degraded installation behavior is covered by
  `tests/test_degraded_mode.py`.

INSUFFICIENT:

- Current upstream command behavior was not live-probed.
- Automatic execution of `impeccable detect` outside the documented agent
  workflow is not proven.

### Recommended disposition

**Keep + explicit optional.** Impeccable has a confirmed web-design,
reference, detector-shape, and degraded-install contract. Cleanup should
make `skills update` part of any future npm upgrade contract or label the
derived update command as operator-only, and should not claim automatic gate
execution until a production caller exists.

## Cross-cutting stale, redundant, and over-coupled dependencies

### 1. Derived view is operationally over-specified

The derived view is correctly declared non-authoritative for registration,
but it contains version probes, install methods, stage commands, workflow
lists, update commands, and platform install commands. Several of these
fields disagree with or exceed the runtime SSOT:

- `ui-pro`: `uipro versions` versus runtime `uipro --version`; broader
  workflow list in the view.
- `si-chip`: bare `python` and home-directory stage mappings versus the
  runtime `python3` CWD-sensitive probe.
- `codegraph`: hosted-script install method and extra workflows absent from
  the runtime row; differing `init` mapping.
- `impeccable`: `npx` skill install/update commands not consumed by the
  runtime lifecycle.

Concrete cleanup candidate: limit the derived file to capability, role, and
stage presentation fields, or generate all operational fields from the SSOT.
Do not maintain a second set of probes or install commands by hand.

### 2. Generic Cargo fallback is not valid for every curl row

`src/devolaflow/_plugin_installer/backends.py` lines 262-321 hard-code Cargo
fallback for every `curl_install_script` row. RTK may plausibly have a Rust
distribution, but the same fallback is also applied to Si-Chip. The current
registry does not declare a per-row fallback backend or prove that Si-Chip's
canonical repository is Cargo-installable.

Concrete cleanup candidate: make fallback capability explicit per runtime
row, or remove the fallback for rows that only support the hosted installer.
This is a behavior change and was not implemented in this audit.

### 3. Upgrade does not mean integration refresh

`src/devolaflow/_plugin_installer/freshness.py` lines 135-279 shows that
`upgrade_plugin()` runs only `spec.upgrade_cmd` or `spec.install_cmd`, then
probes the version and logs the result. It does not invoke the
`npm_then_init` backend's `init_cmd_template`, nor does it consume the
derived `skill_install_command` or `update_command`.

Affected rows: `ui-pro`, `codegraph`, and `impeccable`. A successful version
upgrade can leave old agent integration or skill files installed. Concrete
cleanup candidate: define and test an explicit distinction between package
upgrade and integration refresh, then make the chosen behavior part of the
runtime spec.

### 4. Global bundle defeats per-plugin optionality

`devola-init --global` installs every runtime row by default through
`install_plugins()` (`src/devolaflow/init_project.py` lines 144-207). All
rows are suggest-tier, but there is only a bundle-wide `--no-plugins`
opt-out, not per-plugin install profiles. This is operationally surprising
for users who want DevolaFlow without UI, indexing, or self-improvement
tools.

Concrete cleanup candidate: retain the bundle but expose explicit optional
profiles or per-plugin selection. The runtime hook already demonstrates the
desired default-off model.

### 5. Compatibility registry surface may be redundant

`src/devolaflow/plugins/loader.py` and `src/devolaflow/plugins/registry.py`
preserve the pre-unification `PluginRegistry` capability view, while the
runtime installer uses `RuntimePluginSpec` from the SSOT. Source-level
production callers of the compatibility plugin registry were not found;
tests and public compatibility exports are confirmed.

Concrete cleanup candidate: audit downstream consumers before deprecating the
compatibility surface. Until that caller audit is complete, disposition is
retain. Evidence for safe removal is INSUFFICIENT.

### 6. Empty `gate_scoring` role is stale scaffolding

`workflow-system/agent/plugins.yaml` lines 244-251 defines `gate_scoring`
with no provider and no primary workflows. This is not one of the five
current plugin rows and is not itself a plugin registration, but it is a
stale role-shaped dependency claim. No current plugin is assigned to it.

Concrete cleanup candidate: remove or explicitly mark the role as reserved
in a separate governance change after checking downstream consumers. It
should not be used as evidence that `codegraph` or `impeccable` is already
automatically integrated into gate scoring.

### 7. Historical `nines-assisted` name requires ownership review

`si-chip` still declares `nines-assisted` in the runtime row, and
`tests/test_plugin_sichip_registration.py` explicitly pins that resolution.
The current repository has removed the NineS runtime plugin, but the
`nines-assisted` workflow remains a historical self-improvement seed and
Si-Chip maps it to the same DevolaFlow ability. This is a live compatibility
contract, not proof of a NineS dependency.

Concrete cleanup candidate: document the identifier as a historical workflow
alias or migrate callers to a current workflow name after a dedicated
workflow compatibility review. Removal from the plugin row without updating
the seed and tests would break a confirmed contract.

## Final disposition matrix

| Plugin | Live contract level | Default behavior | Disposition |
|---|---|---|---|
| `ui-pro` | Installer/lifecycle, web-design seed, init-log shape test | Suggest; explicit install opt-in | Keep + explicit optional |
| `rtk` | Shell proxy, pre-shell lifecycle hook, whitelist, distinguish probe | Suggest; proxy flag default-off | Keep + explicit optional |
| `si-chip` | Typed bridge, dispatch wrapper, post-edit hook, parser and threshold tests | Suggest; deep automation flag opt-in | Keep + explicit optional |
| `codegraph` | Installer, agent-facing workflow wiring, exported wrapper and marker protocol | Suggest; background/non-blocking | Keep + explicit optional |
| `impeccable` | Installer/lifecycle, web-design seed, detector documentation and shape tests | Suggest; explicit install opt-in | Keep + explicit optional |

No remove + fully decouple recommendation is justified by the current
evidence. The most urgent follow-up is backend and registry-contract cleanup,
not plugin deletion.
