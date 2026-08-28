# Loop v3 Phase 0 — Existing Test Inventory

**Audit role:** L2 B3  
**Date:** 2026-08-28  
**Mode:** read-only inventory; no source, test, Makefile, plan, or packaging file was changed.

## 1. Scope and evidence boundary

This report inventories the current `tests/` tree against the live capability
domains and behavioral boundaries in
`.local/tasks/functional_test_system/loop_plan_v3.md` §3. It distinguishes
behavioral assertions from source-shape, import, registry, and historical
ghost evidence. An existing test is not treated as functional coverage merely
because its name contains `e2e`, `smoke`, `coverage`, `integration`, or
`entrypoint`.

Commands and observed evidence:

* `.venv/bin/python -m pytest --collect-only -q` collected **5,535 cases**.
* An AST census found **4,425 hand-declared test functions** before
  parametrization. The difference is parametrized expansion, not 1,110
  additional function bodies.
* The census found 221 ordinary test Python files with 4,193 declared test
  functions, 8 harness files with 53, 3 integration test files with 9, and
  50 ghost/support Python files with 170. Counts include test support files
  where applicable and exclude package `__init__.py` files.
* `pytest --markers` exposes only the repository-specific markers
  `persistence_probe` and `deferred`; `fast` and `slow` markers do not exist.
* Current collection and source inspection do not prove that every installed
  console script or guarded module can be invoked from a consumer
  environment. That evidence is **INSUFFICIENT**.

Evidence labels used below:

* **Behavioral:** deterministic input produces an asserted return value,
  output shape, side effect, exit code, or explicit failure.
* **Unit-only:** the assertion is behavioral but calls an implementation
  function or mocked collaborator rather than a consumer boundary.
* **Integration:** multiple real repository components or a real subprocess
  compose, normally in `tmp_path`.
* **Ghost/existence-only:** confirms symbols, files, text, registry rows, or
  wiring without exercising the claimed runtime behavior.
* **Degraded-path:** specifically exercises absence, timeout, malformed input,
  optional-tool failure, fallback, or permissive behavior.
* **External-callability:** invokes a real console/module/package boundary,
  shell, Node process, or standalone protocol.
* **Uncovered:** no existing test provides the required evidence.

## 2. Suite census and broad disposition

### 2.1 Ordinary tests

The ordinary suite is broad and generally assertion-heavy, but it is mostly
implementation-level. The largest areas are:

* `tests/test_compressor.py` — 253 functions: compression transforms and
  validation; strong unit evidence, with only the marked compression probe
  reaching a multi-stage workspace.
* `tests/test_task_adaptive_selector.py` — 126: profile matching, budgets,
  model hints, escalation, and direct selector CLI calls.
* `tests/test_plugins.py` — 119: registry/installer models and mocked
  subprocess outcomes.
* `tests/test_gate.py` — 106; `tests/test_gate_budget.py` — 75;
  `tests/test_gate_ladder.py` — 56: quality, acceptance, convergence,
  escalation, and budget behavior.
* `tests/test_session_state.py` — 57; `tests/test_pre_decision.py` — 57;
  `tests/test_lifecycle_hooks.py` — 73; `tests/test_learnings.py` — 81;
  `tests/test_legibility.py` — 67: substantial unit and artifact behavior,
  not installed-consumer execution.
* `tests/test_agent_workspace.py` — 82 plus the
  `tests/test_agent_workspace_*.py` family: the strongest repository-artifact
  and ownership evidence, mostly direct API calls against temporary folders.
* `tests/test_template_engine.py` — 72 and
  `tests/test_composer_runtime.py` — 29: strong parser/validator/runtime
  behavior, but no functional matrix runner exists.

Representative cross-cutting behavioral families:

* Feedback and convergence:
  `tests/test_feedback.py::TestFeedbackAnalyzerStagnation`,
  `tests/test_feedback_emit.py`,
  `tests/test_feedback_reinforcement.py`,
  `tests/test_e2e_convergence.py`,
  `tests/test_intra_task_convergence.py`.
* Lifecycle and governance:
  `tests/test_lifecycle_hooks.py::TestValidateDispatch`,
  `::TestCheckFileOwnership`, `::TestTestOnComplete`, and `::TestRunHooks`;
  `tests/test_pre_plugin_invocation.py::TestFailureHandling`;
  `tests/test_handoff_envelope_immutable.py`.
* Memory and predecessor state:
  `tests/test_memory_router.py`, `tests/test_memory_bridge.py`,
  `tests/test_memory_consult_for_dispatch.py`,
  `tests/test_predecessor_dedup.py`.
* Compression:
  `tests/test_e2e_compression.py::TestCarrythroughProbe::test_carrythrough_passes_on_faithful_summary`,
  `tests/test_compression_pipeline.py`,
  `tests/test_compressor.py`.
* Delivery and adapter output:
  `tests/test_build_skill.py`, `tests/test_adapter_golden.py`,
  `tests/test_data_driven_adapter.py`, and the adapter-specific files
  `tests/test_cline_adapter.py`, `tests/test_kimicode_adapter.py`,
  `tests/test_roo_adapter.py`, `tests/test_windsurf_adapter.py`, and
  `tests/test_zed_adapter.py`.

These families are valuable behavioral or unit evidence, but they do not
replace a matrix row with a stable ID, a callable surface, a fixture contract,
and a typed outcome.

### 2.2 Harness and integration tests

The harness suite has 53 declared test functions:

* `tests/harness/test_aggregator.py::test_segmented_ledger_exact_rollup`,
  `::test_empty_or_malformed_ledger_fails_explicitly`,
  `::test_aggregation_is_identical_across_three_runs`.
* `tests/harness/test_evaluator.py::test_exact_six_dimension_rubric_and_composite`,
  `::test_unavailable_or_timed_out_signal_is_insufficient`,
  `::test_module_cli_pins_fixture_style_envelope_and_exit_codes`.
* `tests/harness/test_gap.py::test_builtin_axes_statuses_over_synthetic_ledgers`,
  `::test_absent_ledger_is_evidence_not_error`,
  `::test_cli_exit_codes_and_json_envelope`,
  `::test_compare_gap_reports_transition_matrix`.
* `tests/harness/test_probe.py::test_prompt_and_recursive_response_scoring`,
  `::test_run_probe_profiles_statuses_baseline_and_no_key`,
  `::test_probe_cli_errors_without_model_or_table`.
* `tests/harness/test_proposal.py::test_build_and_write_proposal_are_exact_immutable_and_bounded`,
  `::test_approved_apply_is_atomic_audited_idempotent_and_drift_safe`.
* `tests/harness/test_tiers.py::test_exact_ssot_mappings`,
  `::test_mixed_payload_count_ratio_and_reinforcement_deduplication`,
  `::test_schema_nests_and_layout_remain_version_6_length_17`.
* `tests/harness/test_capacity.py::test_capacity_profile_defaults_when_dark`,
  `::test_dispatch_executor_default_follows_capacity_config`.

These are strong deterministic API contracts and degraded evidence. CLI
coverage in this suite is primarily direct `main`/helper invocation or
fixture-level validation, not a complete installed module boundary.

The three integration test files are:

* `tests/integration/test_si_chip_shape_contract.py` — captured Si-Chip
  YAML shape, legacy/forward-compatible fields, and token-count keys.
* `tests/integration/test_rtk_shape_contract.py` — captured RTK rewrite and
  wrapper stdout shape.
* `tests/integration/test_ui_pro_shape_contract.py` — captured UI-Pro init
  log markers.

They are **integration** and fixture-backed, but they are not live plugin
execution. `tests/integration/conftest.py` supplies version-stamped fixture
loaders. Its module docstring claims a no-network guard, but the file contains
no visible autouse network/subprocess-blocking fixture. The claim is therefore
not sufficient evidence for a functional network gate.

### 2.3 Ghost tests

The ghost corpus contains 170 declared test functions across historical
feature modules, registry checks, schema checks, and rule checks. Examples:

* `tests/ghost/test_features_v19_0.py::test_v19_release_review_contracts_are_present`
  and `::test_v19_facade_import_and_compatibility_boundaries_are_retained`.
* `tests/ghost/test_features_v17_5.py::test_v17_5_local_archive_runtime_and_schema_are_wired`.
* `tests/ghost/test_features_v17_3.py::test_pathfinder_role_surfaces_are_wired`.
* `tests/ghost/test_features_v17_0.py::test_v17_0_0_r2_hostbridge_surface_registered`.
* `tests/ghost/test_features_v14_5.py::test_v14_5_0_si10_chain_reorg_registered`.
* `tests/ghost/test_registries.py::test_registry_single_owner`,
  `::test_registry_yaml_at_canonical_path`, and
  `::test_baselines_dir_matches_strict_tier_a_pin_and_archive`.
* `tests/ghost/test_schema.py::test_existing_schemas_are_declared_in_manifest`.

Ghost tests are useful **ghost/existence-only** evidence unless the named test
also invokes a deterministic behavior. Historical pre-v16 modules are skipped
unless `GHOST_FULL=1`; `tests/ghost/conftest.py::pytest_collection_modifyitems`
implements that policy. A ghost pass must not satisfy a required functional
row for a CLI, package, lifecycle, degraded path, or external consumer.

Specific coverage-looking but non-functional evidence includes:

* `tests/test_exercise_modules.py::test_stub_helpers` imports several
  implementations, asserts only a few helper values, and calls
  `build_all([])` and `run_gate_cli([])` without asserting their output,
  status, or side effects.
* `tests/test_exercise_modules.py::test_validate_gate_cmd`,
  `::test_build_skill_cmd`, and `::test_detect_repo_mode_cmd` invoke
  implementation functions after replacing `sys.argv`; they do not execute
  installed console scripts.
* `tests/ghost/test_features_v10_0.py` through the v19 feature modules often
  inspect source symbols or text and use names such as
  `new_symbols_have_coverage`; those checks do not establish callable
  behavior.
* `tests/test_runtime_plugins_smoke.py` is mostly registry shape and
  resolvability. `::test_registry_contains_expected_6_plugin_ids` is
  misnamed while asserting five IDs, and
  `::test_si_chip_version_check_cmd_executes_cleanly_when_installed` skips
  when Si-Chip is absent. These are useful audit signals, not a required
  fake-binary functional row.
* `tests/test_release_pipeline_alignment.py` and parts of
  `tests/test_npm_package.py` inspect YAML/Makefile command strings. They
  verify release wiring, not that CI or a release runner actually executes
  the workflow.
* `tests/test_module_split_shims.py::test_s10_named_paths_verbatim_functional`
  calls selected compatibility symbols and asserts shape, but its direct
  facade parameterized test is an import/existence check, not consumer
  callability for the entire public API.

## 3. Domain-to-test map

The statuses below are the usable starting point for
`tests/functional/matrix.yaml`. “Partial” means existing tests can be
reused or adapted but do not alone satisfy the Loop v3 row contract.

| Candidate matrix IDs | Existing anchors and evidence | Current status | Fixture and gap |
|---|---|---|---|
| `identity.import.version`; `identity.metadata`; `identity.wheel.local` | `tests/test_smoke.py::test_import_devolaflow` is unit-only import evidence. `tests/test_version.py::test_version_format`, `::test_pyproject_version_matches`, `::test_npm_package_json_version_matches`, and `::test_cli_version_cmd` are behavioral/unit-only. `tests/test_npm_package.py::test_package_json_contract` is static metadata behavior. `tests/test_init_project_pip_wheel.py::test_local_with_no_compile_pip_wheel_install_full_smoke` is an isolated-path simulation. | **Partial; external-callability is INSUFFICIENT.** | Use an isolated temporary wheel build/install with network disabled, then call `import devolaflow`, package exports, metadata, and `devola-init local --no-compile`. Existing “pip wheel” tests monkeypatch `_find_agent_dir`; they do not prove an actual built wheel without checkout. |
| `cli.devola_init`; `cli.devola_version`; `cli.validate_template`; `cli.validate_gate`; `cli.build_skill`; `cli.check_drift`; `cli.detect_repo_mode`; `cli.sync_rules`; `cli.check_rules_drift`; `cli.scaffold_local`; `cli.devola_init_doctor`; `cli.devolaflow_plugins`; `cli.devola_local_archive` | `tests/test_exercise_modules.py` direct command-function tests. `tests/test_validate_gate_cli.py::test_run_gate_cli_no_args_prints_help_and_returns`, `::test_run_gate_cli_help_exits_zero`, `::test_run_gate_cli_pass_scenario_exits_zero`, and malformed-input tests are strong unit CLI behavior. `tests/test_cli_local_commands.py` covers direct sync/drift/scaffold behavior. `tests/test_plugin_upgrade.py::TestPluginsCli::test_cli_list_json_prints_array`, `::test_cli_refresh_force_exits_zero_on_success`, and `::test_cli_refresh_failure_exits_one` use mocked subprocesses. `tests/test_local_archive_cli.py::test_default_invocation_is_report_only_and_zero_write`, `::test_apply_uses_approved_plan_and_moves_only_its_entry`, and `::test_deletion_request_is_rejected_without_mutation` are direct callable CLI behavior. | **Partial; no installed console-script matrix.** | Derive scripts from `pyproject.toml [project.scripts]`; run each installed entrypoint in a sanitized temporary directory with explicit timeout, stdout/stderr, help, valid, and malformed cases. Existing tests must not be copied as rows solely from `sys.argv` patches. `devolaflow-plugins` needs fake registry/probe fixtures; local archive must retain no-delete semantics. |
| `module.harness.help`; `module.harness.valid`; `module.harness.invalid`; `module.hostbridge.protocol`; `module.pre_decision.help`; `module.slash_commands.help`; `module.selector.help`; `module.workspace.help` | `tests/harness/test_evaluator.py::test_module_cli_pins_fixture_style_envelope_and_exit_codes` and `tests/harness/test_gap.py::test_cli_exit_codes_and_json_envelope` provide harness CLI behavior, mostly direct invocation. `tests/test_hostbridge.py::test_cli_e2e_cursor_subprocess` is real `python -m devolaflow.hostbridge` subprocess evidence. `tests/test_hostbridge_session.py::test_resume_subprocess_smoke_three_states` is real subprocess evidence with a 60-second timeout. `tests/test_local_workspace.py::TestVirtualRepoInitFlow::test_python_dash_m_module_scaffolds` is a real module subprocess. `tests/test_slash_commands.py::test_main_propose_exit_code_zero` and `::test_main_dispatches_apply_verify_archive_with_exit_codes` call the module’s main function directly. `tests/test_task_adaptive_selector.py::TestMain` calls `main` directly. | **Partial.** | Discover guarded `__main__.py` files and maintained module CLIs, then run `--help`, representative valid input, malformed input, and bounded failure in isolated subprocesses. Existing process tests demonstrate the pattern but do not cover every discovered module or inventory parity. Hostbridge remains synthetic stdin/stdout only. |
| `template.parse`; `template.compose`; `template.validate`; `template.reachability`; `template.loop_termination`; `template.runtime_select` | `tests/test_template_engine.py::TestParseResearchOnly`, `::TestParseHotfix`, `::TestParseFullPipeline`, `::TestValidationSchemaConformance`, `::TestValidationLoopTermination`, `::TestValidationGateCompleteness`, `::TestValidationReachability`, `::TestRegistry`, and `::TestInheritance` are behavioral unit evidence. `tests/test_composer_runtime.py::test_select_stages_with_choice_walks_both_branches`, `::test_select_stages_with_loop_and_gate_refs_in_composition`, and skip/environment cases exercise runtime selection. `tests/test_template_compositions.py` and `tests/test_template_change_driven.py` add composition fixtures. | **Strong unit; partial functional.** | Reuse builtin YAML fixtures plus a small malformed/unknown-reference corpus. Add a callable template/runtime row that proves selected output, bounded loop termination, and error status through the supported CLI or package boundary. |
| `harness.aggregate`; `harness.evaluate`; `harness.gap`; `harness.probe`; `harness.proposal`; `harness.telemetry.append`; `harness.telemetry.check`; `harness.insufficient` | The eight `tests/harness/` files give strong behavioral and degraded-path API coverage. Exact anchors include `test_empty_or_malformed_ledger_fails_explicitly`, `test_unavailable_or_timed_out_signal_is_insufficient`, `test_absent_ledger_is_evidence_not_error`, `test_compare_gap_reports_transition_matrix`, `test_approved_apply_is_atomic_audited_idempotent_and_drift_safe`, and `test_gate_telemetry_check_requires_pass_for_each_si10_gate` in `tests/test_harness_telemetry.py`. | **Strong API/unit; partial external-callability.** | Use deterministic JSONL/YAML fixtures and temporary ledgers. Add installed `python -m devolaflow.harness` rows with exact JSON envelope, status, and exit code. Preserve `INSUFFICIENT` as a reported result, not a way to hide a required failure. |
| `workspace.scaffold`; `workspace.lint`; `workspace.handoff`; `workspace.resume`; `workspace.archive`; `workspace.requirements_trace`; `workspace.report` | `tests/test_agent_workspace.py::TestChangeRoundTrip`, `::TestHandoffEnvelope`, `::TestHandoffStore`, `::TestArchiveManager`, `::TestLintChange`, `::TestApplyMerge`. `tests/test_agent_workspace_checklist_lint.py`, `tests/test_agent_workspace_harness_preflight.py`, `tests/test_agent_workspace_pathfinder_report.py`, `tests/test_agent_workspace_resume.py`, and `tests/test_requirements_trace.py` cover semantic and degraded cases. `tests/test_agent_workspace.py::TestLintChange::test_cli_main_returns_one_on_hard_failure` is direct CLI behavior. | **Strong behavioral/unit and artifact integration; partial external-callability.** | Use temporary repository-relative change folders with owned-files manifests, valid/invalid envelopes, drift, and malformed artifacts. Add subprocess rows for supported workspace modules. Explicitly assert no home-directory writes and immutable handoff bytes. |
| `gate.score`; `gate.acceptance`; `gate.cascade`; `gate.convergence`; `gate.reinforcement`; `gate.budget`; `gate.artifact_report` | `tests/test_gate.py::TestGateStandard`, `::TestGateConvergence`, `::TestAcceptanceReadinessGate`, `::TestPreflightGate`, `::TestAbortGate`, and `::TestNoiseTolerance`. `tests/test_cascade_enforcement.py`, `tests/test_gate_budget.py`, `tests/test_gate_ladder.py`, `tests/test_artifact_score.py`, and `tests/test_reinforcement.py` cover strict/permissive behavior and bounded loops. `tests/test_validate_gate_cli.py` covers direct CLI input/output and malformed YAML. | **Strong unit/behavioral; partial consumer boundary.** | Reuse small gate YAML fixtures and explicit missing-evidence cases. Add one installed `validate-gate` row and, if `python -m` is maintained, one module row. Required assertions must include status, severity, strictness, and nonzero exit behavior. |
| `selector.route`; `selector.timeout`; `selector.budget`; `selector.fallback`; `selector.hash_contract` | `tests/test_task_adaptive_selector.py::TestMatchProfile`, `::TestSelectContext`, `::TestResolveModelHint`, `::TestSelectContextRoundEscalation`, and `::TestMain`. `tests/test_task_adaptive_selector_plan_mode.py`, `tests/test_selector_lru_cache.py`, `tests/test_selector_warmup.py`, `tests/test_l0_only_section_priorities.py`, and `tests/test_agent_context_overhead.py` extend profile, budget, and cache evidence. `tests/ghost/test_features_v14_5.py::test_v14_5_0_timeout_defaults_registered` is a ghost/config pin. | **Strong unit; external CLI evidence partial.** | Use copied profile YAML and deterministic section text. Assert critical-section retention, timeout class resolution, stable output/hash, fallback, and bounded command output. Existing LRU performance test is skipped by default and must not be a required functional row. |
| `plugin.registry.cleanup`; `plugin.registry.parity`; `plugin.suggest`; `plugin.default_off`; `plugin.explicit_opt_in`; `plugin.version_probe`; `plugin.failure`; `plugin.degraded`; `plugin.live.optional_probe` | `tests/test_plugins.py::TestLoadRegistry`, `::TestResolvePlugin`, `::TestEnsurePluginFailureModes`, `::TestEnsurePluginNpmBackend`, `::TestInstallLog`, and `::TestInstallerEdgeCases` are extensive unit tests with mocked subprocesses. `tests/test_runtime_plugins_smoke.py::test_registry_contains_expected_6_plugin_ids`, `::test_resolve_plugin_returns_valid_spec`, and `::test_codegraph_runtime_entry_smoke` are registry/shape evidence. `tests/test_dispatch_plugin_autoinstall.py::TestDispatchAutoInstall` and `tests/test_pre_plugin_invocation.py::TestActiveDelegation` cover lifecycle callers with mocks. `tests/test_degraded_mode.py::TestSiChipUnreachableEmitsPSE001AndDefers`, `::TestRTKUnreachableBypassesToNativeShell`, `::TestUiProUnreachableEmitsPPI001PermissiveContinues::test_ui_pro_unreachable_emits_ppi001_permissive_continues`, and `::TestUiProUnreachableEmitsPPI001PermissiveContinues::test_impeccable_unreachable_emits_ppi001_permissive_continues` cover degraded behavior. `tests/test_plugin_refresh_first_run.py::test_refresh_all_triggers_upgrade_attempt_for_every_plugin_on_fresh_log` covers first-run staleness using a stub. | **Strong unit/degraded; coupling and external-callability partial.** | Use repository YAML owner plus derived view, fake call-graph evidence, fake binaries that emit versions/fail/time out, and a sanitized environment. Assert all five IDs/order, `tier: suggest`, `auto_install: false`, structured suggestion/degraded result, no network, and explicit opt-in only. A live binary row is optional and must carry a declared prerequisite and exact `SKIP_OPTIONAL` reason. No removal disposition is supported by current evidence. |
| `codegraph.available`; `codegraph.research`; `codegraph.degraded`; `codegraph.markers` | `tests/test_codegraph.py::TestIsCodegraphAvailable`, `::TestRunCodegraphCli`, `::TestBuildContext`, `::TestSearchSymbols`, `::TestGetImpact`, `::TestGetCallers`, `::TestGetAffectedTests`, and `::TestDegradedModeNotificationDeduplication`. These assert useful return values and all subprocess calls are mocked. `tests/test_codegraph_markers.py`, `tests/test_codegraph_workflow_wiring.py`, and `tests/test_codegraph_reference_doc.py` are behavior/config or existence evidence. | **Strong degraded/unit; external-callability uncovered.** | Build a fake executable in `tmp_path/bin` that returns valid JSON, malformed JSON, nonzero, and delayed output. Call the public researcher API without installing codegraph; assert structured result, warning, no install, and timeout. |
| `shell_proxy.disabled`; `shell_proxy.whitelist`; `shell_proxy.rtk_probe`; `shell_proxy.wrap`; `shell_proxy.failure` | `tests/test_shell_proxy.py::TestIsProxyEnabled`, `::TestWhitelistRegistry`, `::TestResolveConfig`, `::TestShellProxyWrapCommand`, and `::TestProxyCommand`. `tests/test_shell_proxy_commands.py` covers command mapping. `tests/test_shell_proxy_disabled_is_noop.py::test_disabled_is_noop_byte_identical` is explicit zero-IO degraded evidence. All RTK subprocess calls in these tests are patched. | **Strong unit/degraded; external-callability uncovered.** | Use fake `rtk` and `rtk gain` executables plus a sanitized PATH. Assert exact default passthrough, literal flag parsing, distinguish behavior, whitelist rewrite, and loud failure. No network is required. |
| `archive.plan_report_only`; `archive.apply_move`; `archive.mapping_append_only`; `archive.index_honesty`; `archive.safety_refusal` | `tests/test_local_archive.py::test_report_only_plan_performs_zero_writes`, `::test_approved_move_preserves_contents_and_writes_mapping`, `::test_symlink_and_traversal_are_refused`, `::test_nested_repository_refuses_action`, `::test_mapping_append_only_and_no_clobber`, and `::test_unknown_candidates_cannot_be_deleted`. `tests/test_local_archive_cli.py::test_default_invocation_is_report_only_and_zero_write`, `::test_apply_uses_approved_plan_and_moves_only_its_entry`, `::test_deletion_request_is_rejected_without_mutation`, and `tests/test_local_archive_doctor.py` cover direct command and doctor behavior. | **Strong behavioral/integration; installed console boundary partial.** | Use temporary git repositories containing clean, dirty, symlinked, nested, protected, duplicate, missing, and human-maintained-index cases. Assert no deletion API/command, unchanged refused candidates, append-only sequence, generated marker, and nonzero refusal statuses. Invoke installed `devola-local-archive` in the slow tier. |
| `hostbridge.synthetic_protocol`; `hostbridge.permission`; `hostbridge.failure_open`; `hostbridge.install_excluded` | `tests/test_hostbridge.py::test_cli_e2e_cursor_subprocess` is the strongest external-callability test: real module subprocess, synthetic JSON stdin, stdout response, and ledger assertions. `::test_cli_exit_code_hosts_and_cursor_json` covers direct `main` for Cursor, Claude, Codex, Kimi, and DSH. `tests/test_hostbridge.py::test_normalize_fixture_shapes`, `::test_decide_denies_unowned_write_quoting_path_and_change_id`, and `::test_decide_shell_advisory_error_is_swallowed_and_ledgered` are fixture/unit behavior. `tests/test_hostbridge_session.py::test_resume_subprocess_smoke_three_states` is real subprocess behavior. | **Partial external-callability; host-consumer integration excluded.** | Use synthetic stdin JSON and temporary change ownership state. Add module inventory/help/malformed rows with explicit timeout. Do not start Cursor, Claude, Copilot, DSH, UI, hooks, or remote hosts. Curl installers and real host consumers remain excluded. |
| `skill_delivery.manifest`; `skill_delivery.adapter`; `skill_delivery.build`; `skill_delivery.parity`; `skill_delivery.budget` | `tests/test_build_skill.py::test_build_all_creates_outputs`, `::test_cursor_output_under_budget`, and `::test_codex_has_openai_yaml` exercise generated output in temporary directories. `tests/test_adapter_golden.py`, `tests/test_adapter_registry.py`, `tests/test_data_driven_adapter.py`, `tests/test_install_manifest.py`, and `tests/test_canonical_manifest_parity.py` provide output/parity behavior. `tests/ghost/test_registries.py::test_skill_reference_links_match_sf4_set` is existence/parity evidence. | **Strong build/parity; external installed callability partial.** | Use manifest-derived source copies, all declared adapters, missing-source fixtures, and deterministic output snapshots. Add installed `build-skill`/doctor command rows; do not treat workflow YAML string checks as adapter execution. |
| `package.npm.syntax`; `package.npm.help`; `package.npm.version`; `package.npm.files`; `package.npm.bad_input`; `package.npm.offline_pack` | `tests/test_npm_package.py::test_bin_node_syntax_check`, `::test_bin_help_and_version_offline`, `::test_bin_file_list_derives_from_manifest`, and `::test_bin_fails_loudly_on_bad_input` are real Node subprocess external-callability evidence when Node is present. `::test_package_json_contract`, `::test_ci_checks_npm_job_contract`, and `::test_npm_publish_workflow_contract` are metadata/workflow assertions. | **Partial; `offline_pack` uncovered.** | Run `node --check`, help/version, bad input, then `npm pack --dry-run --offline` from `packages/npm`; inspect the actual file list against `package.json.files`; execute the packed bin without remote resolution. Node absence currently causes `skipif`, so the functional runner must distinguish an optional prerequisite from a required offline row. |
| `delivery.install_script`; `delivery.curl_excluded` | `tests/test_install_sh.py::test_auto_detect_invokes_install_local_when_local_missing`, `::test_auto_detect_skips_install_local_when_local_present`, and `::test_install_sh_local_target_explicit_still_works` run a real Bash script with a fake `curl`. `tests/test_install_script.py` exercises shell installer branches. | **Integration/degraded, but out of Loop v3 required scope.** | Keep as ordinary installer regression tests. Do not put curl installer execution in the functional matrix; the plan explicitly excludes curl installers. The fake-curl tests prove a local stubbed branch, not safe real network behavior. |

## 4. Live plugin coupling evidence

The current tests support **keep suggest/explicit optional**, not removal:

* `ui-pro`: `tests/test_dispatch_plugin_autoinstall.py::TestPluginsForWorkflowHelper::test_product_verification_resolves_to_ui_pro`,
  `tests/test_degraded_mode.py::TestUiProUnreachableEmitsPPI001PermissiveContinues::test_ui_pro_unreachable_emits_ppi001_permissive_continues`,
  and `tests/test_runtime_plugins_smoke.py::test_ui_pro_invoked_by_web_design`
  (the latter family also pins web-design ordering). Workflow and degraded
  paths are live.
* `rtk`: `tests/test_shell_proxy.py::TestResolveConfig`,
  `::TestShellProxyWrapCommand`, `tests/test_shell_proxy_commands.py`, and
  `tests/test_degraded_mode.py::TestRTKUnreachableBypassesToNativeShell`
  demonstrate shell-proxy coupling and default passthrough.
* `si-chip`: `tests/integration/test_si_chip_shape_contract.py`,
  `tests/test_si_chip_bridge.py`, `tests/test_dispatch_dogfood_cycle.py`,
  `tests/test_sichip_iteration_delta_gate.py`,
  `tests/test_plugin_sichip_registration.py`, and
  `tests/test_degraded_mode.py::TestSiChipUnreachableEmitsPSE001AndDefers`
  demonstrate bridge, gate, workflow, and degraded coupling.
* `codegraph`: `tests/test_codegraph.py`, `tests/test_codegraph_markers.py`,
  `tests/test_codegraph_workflow_wiring.py`,
  `tests/test_codegraph_reference_doc.py`, and
  `tests/test_runtime_plugins_smoke.py::test_codegraph_runtime_entry_smoke`
  demonstrate public API, workflow, marker, registry, and fallback coupling.
* `impeccable`: `tests/test_plugins.py::TestRuntimePluginsYamlContract`,
  `tests/test_plugins.py::TestEnsurePluginNpmBackend`,
  `tests/test_degraded_mode.py::TestUiProUnreachableEmitsPPI001PermissiveContinues::test_impeccable_unreachable_emits_ppi001_permissive_continues`,
  and `tests/test_template_web_design.py` demonstrate web-design and optional
  refinement coupling.

The remaining evidence required for the plugin cleanup row is a single
machine-readable coupling audit that joins owner registry,
`workflow-system/agent/plugins.yaml`, runtime callers, lifecycle hooks,
public wrappers, and tests. Existing tests are distributed across these
surfaces and do not currently provide that normalized audit. The audit is
therefore **INSUFFICIENT** as a matrix-ready artifact, while the disposition
itself is resolved to keep.

## 5. Missing strict behavioral evidence

The following are required Loop v3 behaviors for which no current test is a
complete matrix row:

1. **Matrix source of truth and hard gate:** no
   `tests/functional/matrix.yaml`, `tests/functional/runner.py`, or
   `scripts/check_functional_matrix.py` exists. There is no test that fails
   for a missing row, duplicate ID, missing adapter, duplicate callable
   surface, zero-row matrix, unclassified skip, or unexpected result.
2. **Complete console-script inventory:** implementation-level CLI tests exist,
   but no installed-process test derives all 13 `[project.scripts]` entries
   from `pyproject.toml` and reconciles them with the matrix.
3. **Complete module inventory:** only three package `__main__.py` files were
   discovered (`harness`, `hostbridge`, `pre_decision`), while additional
   maintained CLI modules are directly callable. No generated inventory
   reconciles guarded and maintained module entrypoints.
4. **Wheel-only truth:** the existing pip-wheel tests simulate missing
   `workflow-system/agent/SKILL.md`; they do not build/install a wheel into a
   fresh offline environment and prove package-data boundaries.
5. **Offline npm pack:** `tests/test_npm_package.py` does not run
   `npm pack --dry-run --offline`; the workflow command is inspected as text.
6. **Fake-binary external behavior:** codegraph, RTK, and most plugin tests
   patch `subprocess.run` internally. No required row currently runs a fake
   executable through the public API and validates its process protocol.
7. **Plugin cleanup graph:** tests pin membership and selected workflow
   references, but no normalized per-plugin caller/derived-view/public-wrapper
   graph exists.
8. **Shell proxy external callability:** whitelist and failure behavior are
   unit-tested with mocks; actual fake RTK process execution is uncovered.
9. **Hostbridge complete module matrix:** Cursor has a real subprocess test;
   the other host protocol behaviors are direct `main` calls. Complete
   synthetic stdin/stdout/stderr subprocess coverage is **INSUFFICIENT**.
10. **Slow-tier enforcement:** no test marker or Make target currently
    selects a functional fast/slow matrix. Existing slow-looking tests are
    mixed into ordinary collection or guarded by environment-dependent
    skips.
11. **Network prohibition as an executable gate:** the integration conftest
    documents a guard but does not visibly implement one. A functional runner
    must use a network-disabled subprocess environment and/or a hard network
    interception fixture.
12. **Consumer-facing failure semantics:** many direct CLI tests assert
    `SystemExit` or output, but no common adapter normalizes
    `PASS`, `FAIL`, `SKIP_OPTIONAL`, and `INSUFFICIENT` and rejects a bare
    `pytest.skip` for a required row.

## 6. Fixture strategy and risk register

| Risk surface | Existing evidence | Functional fixture strategy | Risk and timeout |
|---|---|---|---|
| Temporary repository writes | Most workspace, archive, init, and CLI tests use `tmp_path`; local archive uses temporary Git repositories. | Create one isolated fixture factory that exposes only repository-relative paths; snapshot files before/after report-only and refusal cases. | Prevent home/worktree mutation. Default 30 seconds per fast subprocess; archive slow rows 60 seconds. |
| Plugin subprocesses | `tests/test_plugins.py` and `tests/test_codegraph.py` mock subprocesses; `tests/test_install_sh.py` uses a fake `curl`. | Create executable fake binaries in `tmp_path/bin` for success, version output, malformed output, nonzero, and timeout. Sanitize PATH and HOME. | No network or package install. Fake process timeout 10–30 seconds; wrapper timeout 30 seconds. |
| Wheel build/install | Existing `isolated_pip_wheel_repo` simulates a wheel-only location. | Build a wheel once in a slow fixture, install into an isolated virtual environment with `--no-index`/offline policy, and run only supported local behavior. | Build/install can be slow and environment-sensitive; 120–300 seconds. Missing build tooling is **INSUFFICIENT** for the required row, not a green skip. |
| npm package | Real Node syntax/help/version tests exist; `node` absence is `skipif`. | Run `node --check`, help/version, bad input, and `npm pack --dry-run --offline`; inspect tarball/file list and run packed bin. | Node/npm availability must be probed explicitly. Pack row should have a 60–120 second timeout; no remote registry access. |
| Hostbridge | One real Cursor subprocess and direct other-host calls exist. | Feed synthetic JSON through `python -m devolaflow.hostbridge` for Cursor and stderr/exit hosts in temporary repos. | Never start a real host or UI. 30–60 seconds, including malformed stdin. |
| Installer scripts | Bash script tests use a fake `curl`; real curl network path is not tested. | Keep outside the functional matrix. If retained as regression tests, require fake curl and temporary HOME. | Curl installers are explicitly excluded; no network permission should be granted. |
| Existing fixtures | Integration loaders require `captured_from_plugin_version`; harness uses deterministic YAML/JSONL fixtures. | Reuse checked-in repository-relative fixtures and add fake-binary fixtures only under an assigned functional test directory. | Fixture version drift should fail loudly. No local clone paths or absolute paths in matrix/report contracts. |

## 7. Pytest configuration and test-tier feasibility

### Pytest configuration

`pyproject.toml` sets `testpaths = ["tests"]`, `pythonpath = ["src"]`, and
declares:

* `persistence_probe`: cross-stage persistence probe marker.
* `deferred`: opt-in skip marker with a reason.

`tests/conftest.py::pytest_collection_modifyitems` converts strict deferred
markers to skips and non-strict markers to non-strict xfails. It does not
define fast/slow selection. `tests/test_e2e_compression.py` marks the
persistence probe; this is a persistence category, not a functional speed
tier.

Environment-dependent skip/degrade points include:

* Node-dependent tests in `tests/test_npm_package.py`.
* Bash-dependent tests in `tests/test_install_sh.py`.
* Optional Si-Chip probing in `tests/test_runtime_plugins_smoke.py`.
* Installed-agent-source checks in `tests/test_init_project.py` and
  `tests/test_exercise_modules.py`.
* Optional radon and writing-style baselines in the relevant quality tests.
* Pre-v16 ghost modules unless `GHOST_FULL=1`.

These skips are acceptable in ordinary tests where the prerequisite is
explicit, but a required functional matrix row must classify the result
instead of allowing an unowned skip.

### Make targets and release insertion

Relevant current targets:

* `make test`: full verbose suite.
* `make test-core`: quiet suite excluding `tests/harness`,
  `tests/test_version.py`, and `tests/test_sichip_iteration_delta_gate.py`.
* `make test-cov`: full coverage invocation with `GHOST_FULL=1`, JSON
  coverage, and a 70% module checker.
* `make test-harness`: only `tests/harness/`.
* `make ghost-full`: `GHOST_FULL=1` ghost suite.
* `make precommit-fast`: Ruff mutation/format plus `pytest -x --lf`; it is
  explicitly an iteration shortcut, not a release gate.
* `make precommit-full` and `make precommit`: aliases for the full
  `release-preflight`.
* `make release-preflight`: `test-core`, ghost-full, lint, version, harness,
  import graph, language, cursor-skill, iteration-delta, telemetry,
  template/manifest, build, docs, rules, module-size, demo catalog, and site
  checks.
* `make release-dry-run`: delegates to `release-preflight`; there is no
  functional-test target yet.

CI currently gives the shared check job 15 minutes, coverage test job 30
minutes, validation job 20 minutes, and npm job 10 minutes. The checked-in
workflow runs the ordinary full coverage suite and a separate npm
syntax/help/pack command. Although the job comments call it offline-only,
the visible `npm pack --dry-run` command does not include `--offline`; actual
network isolation is therefore **INSUFFICIENT**. CI does not run a Loop v3
matrix or hard gate.

Recommended insertion, subject to later implementation ownership:

* Fast functional rows: a new `test-functional-fast` target, pure APIs,
  checked-in fixtures, fake-binary subprocesses, required CLI/module help,
  registry parity, and report-only safety. Keep it below 2 minutes locally
  where practical and below the existing CI check budget.
* Slow functional rows: a new explicit full/release target that adds wheel
  build/install, npm pack, broader subprocess compositions, archive safety
  cases, and timing/telemetry. Do not hide slow rows behind a new
  `DEVOLAFLOW_*` environment flag.
* Release wiring: add the hard gate only after the matrix and runner emit
  typed results and inventory parity. Existing `release-preflight` is the
  likely full/release insertion point; `precommit-fast` must not be weakened
  to imply full functional coverage.

## 8. W-17 estimate

Current baseline is **0 new functional test functions** and **0 functional
matrix cases**; existing 5,535 collected cases are not a W-17 delta for this
Loop v3 implementation. The functional system should use parametrization so
rows do not become one hand-written function each.

| PV | Proposed work | Estimated new `def test_` functions | Expected collected-case growth |
|---|---|---:|---:|
| PV-0 | Matrix schema, loader, typed outcomes, runner, inventory parity, hard-fail gate, fast fixture factory | 6–10 | 20–40 |
| PV-1 | Identity, console/module boundaries, template/runtime, harness, gates, selector, workspace fast rows | 10–16 | 50–100 |
| PV-2 | Isolated wheel API/local install, skill delivery, npm syntax/help/pack | 5–8 | 20–45 |
| PV-3 | Five-plugin coupling audit, registry parity, suggest/default-off, explicit opt-in, fake probes, degraded rows | 6–10 | 35–70 |
| PV-4 | Slow archive, shell proxy, codegraph fake process, hostbridge protocol, timing and release integration | 7–12 | 35–75 |
| **Cycle total** |  | **34–56** | **160–330** |

Every individual PV estimate is below the +30-function limit, and the
cycle estimate is below the +150 limit only if the implementation reuses
existing functions or combines the high end down. The high-end plan is
therefore a W-17 risk. Recommended budget posture:

* Prefer approximately 4–6 new test functions in PV-0, 8–12 in PV-1,
  5–7 in PV-2, 7–10 in PV-3, and 8–12 in PV-4.
* Forecast **32–47** new functions after reuse, still below +150 but requiring
  a midpoint reconciliation before PV-4.
* Count both `git diff` additions matching `^\+\s*def test_` and collected
  parametrized cases. Do not treat parametrization as free runtime cost.
* Do not add ghost-only tests to satisfy the matrix. If a required row has no
  behavioral adapter within budget, record the gap as **INSUFFICIENT** and
  escalate rather than converting it to existence-only evidence.

## 9. Audit conclusion

The repository has substantial and often high-quality unit, artifact,
degraded, and selected subprocess coverage. It does **not** yet have the
Loop v3 functional-test system: there is no capability matrix, typed
parametrized runner, hard missing-row gate, complete installed console/module
inventory, actual offline wheel test, actual npm pack row, normalized plugin
coupling graph, or common network/skip policy.

The existing evidence supports retaining all five plugins as
`suggest` plus explicit optional installation with `auto_install: false`.
It does not support removing any plugin. Required external-callability,
fake-binary, wheel, npm-pack, strict-tier, and matrix-gate evidence remains
**INSUFFICIENT** and should be carried into PV-0/PV-2/PV-3/PV-4 rather than
inferred from current unit or ghost passes.
