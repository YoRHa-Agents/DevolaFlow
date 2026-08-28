# Loop 3 Phase 0 Entrypoint Audit

## Audit boundary

This is a read-only inventory of repository-maintained Python and local npm
surfaces. Evidence is static source, package metadata, and named tests already
present in the repository. No source, test, build, plan, or installer file was
changed.

The report uses `INSUFFICIENT` where the repository does not provide the
requested proof. A direct function test is not treated as proof that an
installed console executable or built wheel works.

Excluded surfaces:

- `scripts/install.sh` and other curl-based installer transport paths. Their
  manifest relationship is noted only where it affects a Python or npm
  contract.
- Real host-consumer integrations. Hostbridge tests use synthetic payloads and
  subprocesses; they do not run inside Cursor, Claude Code, Codex, KimiCode,
  DSH, or Copilot.
- Live GitHub, npm, pip, curl, and external-plugin network operations.

## 1. `project.scripts` console scripts

`pyproject.toml:27-42` declares exactly 13 console scripts. The left side is
the installed command and the right side is its Python call path.

### EP-C01 — `devola-init`

- Repository path: `src/devolaflow/init_project.py`
- Call path: `devola-init` -> `devolaflow.init_project:main` ->
  `_auto_detect` or explicit targets -> `TOOLS[target]`; local initialization
  calls `install_local`, `scaffold_local`, and optional rule compilation.
- Contract: `--list` prints detected tools and returns. Normal execution
  installs selected targets, prints a setup banner, and ends normally. Unknown
  targets print `Unknown target` but do not set a non-zero exit at that branch.
  Invalid `--mode` exits 1. Agent-content targets exit 1 when
  `workflow-system/agent/SKILL.md` is unavailable. `local` is explicitly
  wheel-portable and can succeed without that tree. Global installs optionally
  install registered plugins; plugin failures are warning-only.
- Test evidence: `tests/test_exercise_modules.py::test_init_project_list_target_types`,
  `::test_init_project_unknown_target_errors`, `::test_init_project_all_target`,
  and `::test_init_project_missing_agent_dir`; `tests/test_init_project.py`;
  `tests/test_init_project_pip_wheel.py` covers the absent
  `workflow-system/agent/` scenario and local success.
- Gaps: no test invokes the installed `devola-init` executable from a built
  wheel. `devola-init` has a permissive unknown-target exit contract that
  differs from most validation commands; this is not documented as a stable
  error policy.

### EP-C02 — `devola-version`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devola-version` -> `devolaflow.cli:version_cmd` ->
  `devolaflow.__version__`.
- Contract: prints `DevolaFlow v19.0.0`; the function returns implicitly, so a
  normal process exits 0.
- Test evidence: `tests/test_exercise_modules.py::test_version_cmd`;
  `tests/test_version.py::test_version_consistency` and related version
  checks.
- Gaps: evidence calls the function directly. Installed-executable and
  built-wheel subprocess evidence is `INSUFFICIENT`.

### EP-C03 — `validate-template`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devolaflow.cli:validate_template_cmd` -> either
  `validate_all_templates(all_flag=True)` or
  `parse_template` -> `validate_template`.
- Contract: `--all` exits 0 when all built-in templates validate and 1
  otherwise. A valid path prints `PASS` and exits 0. Missing, parse-invalid,
  or semantically invalid input prints `FAIL` and exits 1. No argument prints
  usage and exits 1.
- Test evidence: `tests/test_exercise_modules.py::test_validate_template_cmd`,
  `::test_cli_validate_template_single_path`, `::test_cli_validate_template_all_flag`,
  `::test_cli_validate_template_missing_file`,
  `::test_cli_validate_template_no_args_exits_1`,
  `::test_cli_validate_template_parse_error`, and
  `::test_cli_validate_template_invalid_content`.
- Gaps: no built-wheel console subprocess test; the all-template path depends
  on repository template files not packaged as `project.package-data`.

### EP-C04 — `validate-gate`

- Repository path: `src/devolaflow/cli.py` and
  `src/devolaflow/gate/scorer.py`
- Call path: `devolaflow.cli:validate_gate_cmd` -> `run_gate_cli(sys.argv[1:])`
  -> YAML load -> `_build_gate_input` -> `evaluate_gate`.
- Contract: `run_gate_cli` documents 0 for PASS, 1 for FAIL or ESCALATE, and
  2 for usage, input I/O, or parse errors. It prints `decision`, optional
  `composite`, `findings`, `profile`, `gate_type`, and `rationale`.
  Empty argument input prints help and returns without raising.
- Test evidence: `tests/test_validate_gate_cli.py::test_validate_gate_cmd_pass`
  and the broader `tests/test_validate_gate_cli.py` suite;
  `tests/test_exercise_modules.py::test_validate_gate_cmd`.
- Gaps: no installed console subprocess or wheel-only test. The direct wrapper
  test proves the scorer path, not packaging or executable metadata.

### EP-C05 — `build-skill`

- Repository path: `src/devolaflow/cli.py` and
  `src/devolaflow/build_skill.py`
- Call path: `devolaflow.cli:build_skill_cmd` -> `build_skill.build_all` ->
  `create_default_registry` -> data-driven adapter loading -> `registry.build_selected`.
- Contract: without `--tools`, builds every registered adapter; with
  `--tools a,b`, builds only the named adapters. It creates `dist/`, prints
  `[OK]` or `[WARN]` result rows, and returns a result list. Unknown adapter
  names print an error and exit 2. Missing workflow skill source prints an
  error and returns an empty list.
- Test evidence: `tests/test_exercise_modules.py::test_build_skill_cmd`,
  `::test_cli_build_skill_cmd_no_tools`, and
  `::test_cli_build_skill_cmd_with_tools`; `tests/test_build_skill.py`;
  `tests/test_adapter_registry.py`.
- Gaps: the console wrapper does not translate a returned empty list into a
  non-zero process status. No built-wheel executable test; the command writes
  generated output by design, so a wheel-only run cannot build repository
  adapter outputs.

### EP-C06 — `check-drift`

- Repository path: `src/devolaflow/cli.py` and
  `src/devolaflow/check_drift.py`
- Call path: `devolaflow.cli:check_drift_cmd` -> `check_drift` ->
  `DeviationScanner(project_root=_find_project_root()).print_report()`.
- Contract: `check_drift` returns `True` when human documentation drift is
  found; the console wrapper exits 1 for drift and 0 otherwise.
- Test evidence: `tests/test_exercise_modules.py::test_check_drift_cmd`,
  `::test_cli_check_drift_cmd_no_drift`; `tests/test_doc_consistency.py`.
- Gaps: no explicit drift-positive console wrapper test and no built-wheel
  executable test. The source-root discovery behavior is tested indirectly,
  so installed-wheel root behavior is `INSUFFICIENT`.

### EP-C07 — `detect-repo-mode`

- Repository path: `src/devolaflow/cli.py` and
  `src/devolaflow/pre_decision/detect.py`
- Call path: `devolaflow.cli:detect_repo_mode_cmd` ->
  `detect_and_print` -> `detect_repo_mode(Path.cwd())`.
- Contract: prints one of `local`, `github`, `other-git` variants, and an
  optional `Remote: ...` line. The function has no explicit `sys.exit`, so
  normal completion exits 0.
- Test evidence: `tests/test_exercise_modules.py::test_detect_repo_mode_cmd`;
  `tests/test_pre_decision.py` covers detection and normalization behavior.
- Gaps: `scripts/detect-repo-mode.sh:3` invokes
  `python -m devolaflow.pre_decision.detect`, but
  `pre_decision/detect.py` has no `__main__` guard. That module invocation is
  therefore not proven to print the same result and is a maintained-wrapper
  gap. The console executable itself has no built-wheel subprocess test.

### EP-C08 — `sync-rules`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devolaflow.cli:sync_rules_cmd` -> `RuleCompiler(config_path)`
  -> `compile_all()`, where `config_path` is
  `.rules/compile-config.yaml` under the current directory.
- Contract: missing config prints `No .rules/compile-config.yaml found. Run
  'devola-init' first.` and exits 1. A present config compiles all configured
  targets, prints token/layer rows and a target count, and normally exits 0.
- Test evidence: `tests/test_cli_local_commands.py::TestSyncRulesCmd::test_happy_path_compiles_all_targets`
  and `::test_missing_config_exits_1`; `tests/test_init_project.py` covers the
  init-to-sync path.
- Gaps: no explicit test for an uncaught compiler failure at this boundary;
  no installed console subprocess or wheel-only test. The command depends on
  user/repository `.rules/` files that are not package data.

### EP-C09 — `check-rules-drift`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devolaflow.cli:check_rules_drift_cmd` ->
  `check_rules_drift(Path.cwd() / ".rules")`.
- Contract: missing `.rules/` prints `No .rules/ directory found.` and exits
  1. It prints one status row per compiled target and exits 1 if any target is
  not `in_sync`; otherwise exits 0.
- Test evidence: `tests/test_cli_local_commands.py::TestCheckRulesDriftCmd`
  covers in-sync, missing-directory, and drifted-output contracts.
- Gaps: no installed console subprocess or wheel-only test; behavior requires
  repository-generated rule outputs and hashes outside the wheel.

### EP-C10 — `scaffold-local`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devolaflow.cli:scaffold_local_cmd` ->
  `devolaflow.local.workspace.scaffold_local(Path.cwd(), dirs=args)`.
- Contract: creates the `.local/` workspace and optional named directories,
  then prints `.local/ workspace initialized.` and exits 0. A
  `ScaffoldVerificationError` or `ScaffoldStructureError` prints `FAIL` and
  exits 1.
- Test evidence: `tests/test_cli_local_commands.py::TestScaffoldLocalCmd`
  covers default, extra directories, and structure-error handling;
  `tests/test_local_workspace.py` covers the scaffold contract.
- Gaps: no installed console subprocess or wheel-only executable test. The
  command is repository-local by design and has no package-data-independent
  end-to-end wheel proof beyond the related `local.workspace` test.

### EP-C11 — `devola-init-doctor`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devolaflow.cli:doctor_cmd` -> default:
  `probe_capabilities` + `check_init_health(Path.cwd())`; `--skills`:
  `_doctor_skills` -> `scan_installed_skills`.
- Contract: default mode exits 0 for a healthy canonical workspace and 1 for
  missing required paths. `--skills` exits 0 when no installs are found or
  every found install is current; it exits 1 for stale or unknown-version
  installs.
- Test evidence: `tests/test_init_doctor.py::TestDoctorCmdCli` covers healthy,
  empty, missing-path, and output contracts; `tests/test_skills_doctor.py`
  covers `--skills`; `tests/test_init_project_pip_wheel.py` covers wheel-only
  local initialization.
- Gaps: no executable-from-wheel test. The default mode can report advisory
  findings while exiting 0; the distinction is documented in source but not
  represented by a single public contract fixture.

### EP-C12 — `devolaflow-plugins`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devolaflow.cli:plugins_cmd` -> argparse subcommand ->
  `plugins.installer.list_plugins` or `refresh_all`.
- Contract: `list` and `status` inspect without installation and exit 0 on
  success; registry `FileNotFoundError` exits 1. `refresh` returns 0 unless
  at least one outcome has `action == "failed"`, then exits 1. Unknown or bad
  invocation is argparse exit 2. `--json` emits machine-readable rows.
- Test evidence: `tests/test_plugin_upgrade.py` covers list, status, refresh,
  JSON, force, filtering, and failure paths; `tests/ghost/test_features_v9_4.py`
  pins the `devolaflow.cli:plugins_cmd` symbol.
- Gaps: no installed console subprocess or wheel-only test. Registry-backed
  plugin refresh depends on external install backends; live backend evidence
  is excluded here and is therefore `INSUFFICIENT`.

### EP-C13 — `devola-local-archive`

- Repository path: `src/devolaflow/cli.py`
- Call path: `devolaflow.cli:local_archive_cmd` -> plan load/validation ->
  `devolaflow.local.archive.build_archive_plan` or
  `apply_archive_plan` -> JSON result.
- Contract: default invocation is report-only and exits 0 without moving or
  deleting anything. `doctor` emits a doctor JSON artifact and maps findings
  to 0 healthy, 3 safety refusal, 4 approval mismatch, or 5 mapping conflict.
  Malformed plans exit 2. `--apply` requires an approved plan and emits a
  result; safety, approval, and mapping findings remain non-zero. Argparse
  rejects unsupported combinations.
- Test evidence: `tests/test_local_archive_cli.py` covers report-only,
  approved apply, failed findings, malformed/changed approval, and deletion
  refusal; `tests/test_local_archive_doctor.py` covers duplicate destinations,
  missing/drifted index, protected entries, and malformed mappings;
  `tests/test_local_archive_wiring.py` covers command wiring.
- Gaps: no installed console subprocess or wheel-only test. Tests use local
  temporary repositories and do not constitute an operator-approved
  production archive run.

## 2. Maintained `python -m` entrypoints

The maintained set below is derived from `__main__` guards, module docstrings,
README/Makefile use, and direct subprocess tests. Private split implementation
modules with guards are not counted as public entrypoints.

### EP-M01 — `python -m devolaflow.harness`

- Repository path: `src/devolaflow/harness/__main__.py`
- Call path: module `main` -> argparse command dispatcher. Commands are
  `aggregate`, `evaluate`, `gap`, `cross-validate`, `probe`, `propose`,
  `apply`, and `telemetry` with `append`, `append-metrics`,
  `append-observation`, and `check`.
- Contract: `aggregate` returns 0; `gap` returns 0 when no current gap and 1
  for current gaps; `cross-validate` returns 0 for `PASS`, 1 otherwise;
  probe maps `PASS` to 0, `FAIL`/`PARTIAL` to 1, and `SKIPPED_NO_KEY` to 2;
  telemetry check returns 2 for `INSUFFICIENT`, otherwise 0; evaluator
  results map `READY` to 0, `NOT_READY` to 1, and `INSUFFICIENT` to 2.
  Aggregation/evaluation/value errors return 2, while telemetry gate errors
  return 1.
- Test evidence: `tests/harness/test_evaluator.py`,
  `tests/harness/test_gap.py`, `tests/harness/test_probe.py`,
  `tests/harness/test_proposal.py`, and `tests/harness/test_aggregator.py`
  exercise the dispatcher and exit semantics. `README.md:275-276` and
  `AGENTS.md` document the evaluator/aggregate invocation.
- Gaps: no full built-wheel subprocess matrix for all subcommands; probe
  live-provider behavior is intentionally excluded and remains
  `INSUFFICIENT` without provider credentials.

### EP-M02 — `python -m devolaflow.hostbridge`

- Repository path: `src/devolaflow/hostbridge/__main__.py`,
  `src/devolaflow/hostbridge/session.py`, and
  `src/devolaflow/hostbridge/install.py`
- Call path: module `main` dispatches normal stdin boundary decisions,
  `install`, or `resume`. Normal decisions call `normalize_event` ->
  `decide` -> `_respond`; install calls `hostbridge.install.main`; resume
  calls `hostbridge.session.main`.
- Contract: Cursor returns JSON `permission` and always exits 0; Copilot
  returns JSON `permissionDecision` and always exits 0; Claude, Codex, Kimi,
  and DSH allow silently with 0 and deny with reason on stderr and 2.
  Malformed argv, stdin, or internal failures fail open with an allow shape
  and exit 0. `resume` is gated by literal
  `DEVOLAFLOW_AGENT_WORKSPACE=1`, is read-only, and always exits 0.
  `install kimi` prints a TOML snippet; other install hosts emit generated
  file statuses and return 0.
- Test evidence: `tests/test_hostbridge.py` covers synthetic stdin,
  Cursor JSON, exit-code hosts, malformed input, and audit rows;
  `tests/test_hostbridge_copilot.py` covers Copilot protocol;
  `tests/test_hostbridge_session.py` covers the strict gate, zero-I/O off
  path, 0/1/multiple changes, goal drift, error audit, and subprocess smoke.
- Gaps: no test runs as a real host hook inside any host consumer. The
  fail-open behavior is deliberately safety-sensitive; production host
  protocol compatibility is `INSUFFICIENT`.

### EP-M03 — `python -m devolaflow.pre_decision`

- Repository path: `src/devolaflow/pre_decision/__main__.py`
- Call path: package guard -> `detect_and_print()` ->
  `detect_repo_mode(Path.cwd())`.
- Contract: prints the detected mode and optional remote and normally exits 0.
- Test evidence: `tests/test_pre_decision.py` covers the detector and
  pre-decision APIs; `tests/test_exercise_modules.py::test_detect_repo_mode_cmd`
  covers the same print surface through the console wrapper.
- Gaps: no direct subprocess test for the package `__main__` path.
  `scripts/detect-repo-mode.sh:3` instead calls
  `python -m devolaflow.pre_decision.detect`; `detect.py` has no module guard,
  so that wrapper path is a likely silent no-op. This is an explicit
  entrypoint-integrity gap.

### EP-M04 — `python -m devolaflow.task_adaptive_selector`

- Repository path: `src/devolaflow/task_adaptive_selector.py` and
  `src/devolaflow/selector_cli.py`
- Call path: `task_adaptive_selector.py` guard -> `selector_cli.main` ->
  `select_context` and optional `select_agents_md_slice`.
- Contract: requires a task type; no task type prints usage and exits 1.
  It prints profile, token budget, selected/skipped sections, and optional
  full context or AGENTS slice. Invalid `--round` falls back to 1 per the
  source contract.
- Test evidence: `tests/test_task_adaptive_selector.py`,
  `tests/test_task_adaptive_selector_plan_mode.py`,
  `tests/test_pv07_agents_md_slice.py`, and
  `tests/test_module_split_shims.py` cover selector behavior, CLI ownership,
  and retired shim absence.
- Gaps: no direct subprocess invocation of this exact module path; most
  evidence calls library functions. The selector reads
  `workflow-system/agent/context_profiles.yaml` and `SKILL.md`, so a wheel-only
  installation cannot be assumed to support it.

### EP-M05 — `python -m devolaflow.build_skill`

- Repository path: `src/devolaflow/build_skill.py`
- Call path: module guard -> `build_all(sys.argv[1:])`.
- Contract: same adapter selection and output behavior as EP-C05. Unknown
  adapter names exit 2; missing source returns an empty result list without
  raising.
- Test evidence: `tests/test_build_skill.py`, `tests/test_adapter_registry.py`,
  and `tests/test_exercise_modules.py` cover the implementation and the
  console wrapper.
- Gaps: no direct subprocess test for this module path; the source's
  missing-input branch does not itself return a non-zero status.

### EP-M06 — `python -m devolaflow.agent_workspace.reporter`

- Repository path: `src/devolaflow/agent_workspace/reporter.py` facade and
  `src/devolaflow/_workspace_reporter/rules_cli.py` implementation
- Call path: facade imports `main` -> `--all`, `--workspace`, `--memory`,
  `--rules`, `--change`, or `--human` renderer -> report file or stdout.
- Contract: successful report generation returns 0; argparse usage errors
  return 2; missing change/file errors return 2; rendering and hard human
  budget failures return 1. `--print` is only valid for one non-`--all`
  flavor.
- Test evidence: `tests/test_reporter.py::TestReporterCli` covers subprocess
  module invocation, stdout mode, all mode, and change mode; the same file
  covers renderers and idempotency.
- Gaps: the facade dynamically re-exports a broad implementation namespace;
  there is no explicit stable export manifest for the reporter. Human report
  behavior with real requirements and test-result joins is only partially
  covered.

### EP-M07 — `python -m devolaflow.agent_workspace.lint`

- Repository path: `src/devolaflow/agent_workspace/lint.py` facade and
  `src/devolaflow/_workspace_lint/cli.py` implementation
- Call path: facade imports `main` -> `lint_change` or `lint_human` ->
  budget/semantic report -> stderr output and exit code.
- Contract: 0 for clean; 1 for hard violations or soft warnings according to
  the report contract; 2 for missing change, legacy layout, or usage errors.
  `--human` selects `.local/human/` input/output linting.
- Test evidence: `tests/test_agent_workspace.py` covers the public API and
  lint path; `tests/test_lint_human.py::TestLintHumanCli` covers clean and
  hard human-surface results.
- Gaps: no direct subprocess test for the exact module path and no built-wheel
  CLI proof. The facade's wildcard export behavior makes the candidate API
  larger than the documented lint command.

### EP-M08 — `python -m devolaflow.local.workspace`

- Repository path: `src/devolaflow/local/workspace.py`
- Call path: module guard -> `scaffold_local(Path.cwd())`, catches
  `ScaffoldVerificationError` and `ScaffoldStructureError`, then prints the
  scaffold confirmation.
- Contract: successful scaffold exits 0; the two known self-check failures
  print `FAIL` and exit 1; unexpected exceptions propagate.
- Test evidence: `tests/test_local_workspace.py::TestStructureContract::test_python_dash_m_module_scaffolds`
  runs a real subprocess and verifies `.local/` and `.gitignore` output.
  `tests/test_cli_local_commands.py` covers the parallel `scaffold-local`
  wrapper.
- Gaps: no wheel-only subprocess test for package-data/template availability;
  the source comment records that this path previously was a silent no-op,
  so the direct subprocess regression is important but narrow.

### EP-M09 — `python -m devolaflow.skills.slash_commands`

- Repository path: `src/devolaflow/skills/slash_commands.py`
- Call path: module guard -> `main` -> argparse -> `run_propose`,
  `run_apply`, `run_verify`, or `run_archive`.
- Contract: 0 on successful lifecycle operation; 1 for domain/runtime
  failures such as `VerifyFailed`, `ChangeStoreError`, `ArchiveError`, or
  hook violations; 2 for invocation errors. Success is stdout; errors are
  stderr plus logging.
- Test evidence: `tests/test_slash_commands.py::test_main_propose_exit_code_zero`,
  `::test_main_propose_no_change_exit_code_zero`, and
  `::test_main_dispatches_apply_verify_archive_with_exit_codes`; the source
  docstring and `tests/ghost/test_features_v9_1.py` also pin the entrypoint.
- Gaps: no direct subprocess test for the module path; tests call `main`
  directly. Archive behavior is local-fixture-only and is not a real
  operator approval integration.

### Private guarded paths not counted as public maintained entrypoints

These files contain `__main__` guards but are implementation slices behind
the public facades above:

- `src/devolaflow/_workspace_lint/cli.py`
- `src/devolaflow/_workspace_reporter/rules_cli.py`

`tests/test_module_split_shims.py` labels `_workspace_lint` and
`_workspace_reporter` as direct implementation facades. Their importability
is tested, but no repository documentation presents their underscored module
paths as operator entrypoints.

## 3. Installed-wheel public API candidate surface

### Packaging evidence

- `pyproject.toml:44-49` uses setuptools package discovery with
  `where = ["src"]`. Package data is explicitly limited to
  `devolaflow.local/compile_config_template.yaml` and
  `devolaflow.agent_workspace.templates/*.md.j2`.
- `src/devolaflow/__init__.py:6-9` defines `__version__ = "19.0.0"` and
  imports `devolaflow.learnings` as `learnings`; it does not define a root
  `__all__` or re-export the domain APIs.
- `tests/test_init_project_pip_wheel.py:1-17` states the wheel-only model:
  `site-packages/devolaflow/` is importable, but
  `workflow-system/agent/SKILL.md` is absent. It requires `local` to work
  and agent-content targets to emit an informative failure.
- `tests/test_smoke.py::test_import_devolaflow` proves only root import and
  version. `tests/test_module_split_shims.py` proves selected facade exports
  and retired shim absence.
- No built wheel artifact is present as audit evidence. Full wheel contents,
  importability of every candidate facade, and package-data behavior are
  therefore `INSUFFICIENT`.

### Candidate groups

The following are candidate public surfaces because their package roots
declare `__all__`, their docstrings describe a public surface, or existing
tests import them as domain APIs. Candidate does not mean that semantic
stability is promised.

- `devolaflow.__version__` and `devolaflow.learnings`: root metadata and
  operational learning functions. Evidence: `src/devolaflow/__init__.py`,
  `src/devolaflow/learnings.py`, `tests/test_smoke.py`, and
  `tests/test_learnings.py`.
- `devolaflow.template_engine`: `WorkflowTemplate`, parser/composer models,
  `TemplateRegistry`, runtime selection, inheritance, and validation.
  Evidence: `src/devolaflow/template_engine/__init__.py:6-112` and
  `tests/test_template_engine.py`.
- `devolaflow.gate`: gate models, `evaluate_gate`, acceptance-v2, ladder,
  ratchet, reinforcement, budget, complexity, and report functions.
  Evidence: `src/devolaflow/gate/__init__.py:6-204`,
  `tests/test_gate.py`, and `tests/test_gate_ladder.py`.
- `devolaflow.compressor`: compression, lean-format validation, dispatch
  layout assertions, envelope wrapping, and summary tools.
  Evidence: `src/devolaflow/compressor/__init__.py:297-340`,
  `tests/test_compressor.py`, and `tests/test_dispatch_layout_v5.py`.
- `devolaflow.agent_workspace`: `Change`, `ChangeStore`, handoff stores,
  archive manager, delta parsing, linting, reports, checkpoints, round
  control, and resume planning. Evidence:
  `src/devolaflow/agent_workspace/__init__.py:7-34,201-343`,
  `tests/test_agent_workspace.py`, and `tests/test_reporter.py`.
- `devolaflow.harness`: aggregation, evaluation, gap reports, probes,
  telemetry, and proposals. Evidence:
  `src/devolaflow/harness/__init__.py:3-115` and `tests/harness/`.
- `devolaflow.hostbridge`: normalized boundary events, decisions, audit
  records, host installation helpers, and response constants. Evidence:
  `src/devolaflow/hostbridge/__init__.py:28-84` and hostbridge tests.
- `devolaflow.local`: local workspace scaffolding, rule compiler/drift, and
  report-only/approved archive primitives. Evidence:
  `src/devolaflow/local/__init__.py:3-45`, `tests/test_local_workspace.py`,
  and `tests/test_local_archive.py`.
- `devolaflow.plugins`: runtime registry, plugin resolution, status, refresh,
  and install errors. Evidence:
  `src/devolaflow/plugins/__init__.py:17-63`, `tests/test_plugins.py`, and
  `tests/test_plugin_upgrade.py`.
- `devolaflow.skills`: change activation, grill mode, Pathfinder intent,
  and subagent-pattern pure functions. Evidence:
  `src/devolaflow/skills/__init__.py:67-113`,
  `tests/test_change_activation_heuristic.py`,
  `tests/test_grill_mode.py`, and `tests/test_cascade_enforcement.py`.
- `devolaflow.pre_decision`: repo mode, checklist, validation, freeze, and
  recommendation APIs. Evidence:
  `src/devolaflow/pre_decision/__init__.py:6-22` and
  `tests/test_pre_decision.py`.
- Optional or integration-sensitive candidates:
  `devolaflow.shell_proxy`, `devolaflow.memory_router`,
  `devolaflow.codegraph`, `devolaflow.si_chip_bridge`,
  `devolaflow.writing_style`, `devolaflow.session`, and
  `devolaflow.legibility`. Their package roots describe public exports, but
  several depend on opt-in flags, external binaries, external scripts, or
  intentionally isolated paths. Existing unit tests provide partial evidence;
  installed-wheel and real external-consumer evidence is `INSUFFICIENT`.

### Wheel/API gaps

- There is no root-level public API manifest. `__all__` is distributed across
  domain packages, while wildcard facades can expose implementation names.
- There is no built-wheel smoke that imports every proposed facade and checks
  package data.
- `devolaflow.init_project` explicitly says the wheel does not bundle
  `workflow-system/`; this makes many source-tree-facing APIs callable but
  not fully operational after wheel installation.
- There is no single policy distinguishing stable API, operator CLI, test-only
  compatibility export, and optional external integration.
- `tests/test_module_split_shims.py` proves some historical exports were
  intentionally retired; this means source importability alone is not a
  sufficient public-API criterion.

## 4. Local npm package surface

### NP-01 — package metadata

- Repository path: `packages/npm/package.json`
- Call path: npm package `@yorha-agents/devola-flow` -> bin
  `packages/npm/bin/devola-flow.js`.
- Contract: version `19.0.0`, Node `>=18`, one bin named `devola-flow`, public
  provenance publishing, and no runtime dependencies. `"files": ["bin/"]`
  means the tarball intentionally ships the installer script rather than the
  skill bundle.
- Test evidence: `tests/test_npm_package.py::test_package_json_contract`,
  `::test_bump_version_manages_npm_package_json`, and
  `tests/test_version.py::test_npm_package_json_version_matches`.
- Gaps: no local packed tarball was inspected during this read-only audit;
  `npm pack --dry-run` is CI-contract evidence, not a published registry
  artifact.

### NP-02 — `devola-flow` bin

- Repository path: `packages/npm/bin/devola-flow.js`
- Call path: `main` -> `parseArgs` -> one of `cmdInstall`, `cmdDoctor`,
  `cmdFiles`, or version/help output. Downloads
  `workflow-system/agent/manifest.yaml` and profile files from
  `https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/<ref>`, unless
  `--manifest-file` supplies an offline manifest.
- Contract: `--help`, `--version`, and `help` exit 0. `install` and `update`
  resolve a target, download manifest-declared files, write a version stamp,
  and print completion; `doctor` reports installed target parity; hidden
  `files` prints one manifest-resolved path per line. Network, HTTP, parse,
  unknown-command, unknown-target, and other errors print `devola-flow: ...`
  and exit 1. `DEVOLA_FLOW_REF` overrides the default `v<package.version>`.
- Test evidence: `tests/test_npm_package.py::test_bin_node_syntax_check`,
  `::test_bin_help_and_version_offline`,
  `::test_bin_file_list_derives_from_manifest` for cursor, claude, codex,
  kimicode, and dsh, and `::test_bin_fails_loudly_on_bad_input`.
  `tests/test_npm_package.py::test_ci_checks_npm_job_contract` pins Node
  syntax/help/version and `npm pack --dry-run` CI checks.
- Gaps: tests use local manifest resolution and offline help/version; no live
  GitHub download, actual user-home installation, or real host-consumer run
  is in scope. Those integration claims are `INSUFFICIENT`.

### NP-03 — README/package contract drift

- Repository paths: `packages/npm/README.md` and
  `packages/npm/bin/devola-flow.js`
- Exact conflict: README lines 9-15 say the package installs only Cursor and
  Claude, and that npm `all` means those two targets. The bin source
  `TARGETS` at lines 26-48 defines five targets: `cursor`, `claude`, `codex`,
  `kimicode`, and `dsh`; `resolveTargets("all")` returns all five.
- Test evidence: `tests/test_npm_package.py::test_bin_file_list_derives_from_manifest`
  explicitly parameterizes all five code targets. `tests/test_canonical_manifest_parity.py`
  checks README-facing npm commands but does not assert the README target
  scope against `TARGETS`.
- Gap: user-facing npm documentation is stale relative to the maintained bin
  implementation. The intended supported target set and meaning of `all` need
  one authoritative contract before the npm surface can be curated.

### NP-04 — npm publishing boundary

- Repository paths: `.github/workflows/npm-publish.yml`,
  `.github/workflows/ci-checks.yml`, and `scripts/bump_version.py`
- Call path: tag `v*` -> reusable CI checks -> tag/package-version check ->
  `npm publish --provenance --access public`.
- Contract: publish requires the checks job, uses read contents plus id-token
  write permission, and checks package version before publish.
- Test evidence: `tests/test_npm_package.py::test_npm_publish_workflow_contract`,
  `::test_ci_checks_npm_job_contract`, and
  `tests/test_release_pipeline_alignment.py`.
- Gaps: no registry publication was attempted. Registry availability,
  provenance acceptance, and consumer installation remain `INSUFFICIENT`.

## 5. Proposed curated public API inventory and matrix IDs

The proposed inventory separates stable Python facades from operator commands
and optional integrations. It intentionally excludes underscored implementation
packages, curl transport, and real host consumers.

- `API-01`: `devolaflow.__version__`; stable package metadata.
- `API-02`: `devolaflow.template_engine`; parse, compose, validate, and
  runtime-select workflow templates.
- `API-03`: `devolaflow.gate`; deterministic gate scoring, models, ladder,
  reinforcement, and reports.
- `API-04`: `devolaflow.compressor`; lean message and dispatch-layout
  validation/compression.
- `API-05`: `devolaflow.agent_workspace`; change, handoff, archive, lint,
  report, checkpoint, and round-control APIs.
- `API-06`: `devolaflow.harness`; telemetry, aggregation, evaluation, gap,
  probe, and proposal APIs.
- `API-07`: `devolaflow.local`; workspace scaffold, rule compiler/drift, and
  approved non-deletion archive APIs.
- `API-08`: `devolaflow.pre_decision`; repository detection and
  pre-decision helpers.
- `API-09`: `devolaflow.hostbridge`; normalized event and decision APIs,
  explicitly marked host-protocol-dependent.
- `API-10`: `devolaflow.plugins`; registry/status/refresh APIs, explicitly
  marked backend-dependent.
- `API-11`: `devolaflow.skills`; pure activation, grill, Pathfinder, and
  pattern-selection helpers.
- `API-12`: optional integration group
  `devolaflow.shell_proxy`, `devolaflow.memory_router`,
  `devolaflow.codegraph`, `devolaflow.si_chip_bridge`,
  `devolaflow.writing_style`, `devolaflow.session`, and
  `devolaflow.legibility`; retain as provisional until wheel and external
  dependency contracts are tested.
- `API-13`: `@yorha-agents/devola-flow` package metadata and
  `devola-flow` bin; resolve the README five-target drift before declaring
  the target matrix stable.

Entrypoint matrix rows are `EP-C01` through `EP-C13` for the 13 console
scripts, `EP-M01` through `EP-M09` for maintained module entrypoints, and
`NP-01` through `NP-04` for the npm surface. The broken/stale module wrapper
is tracked as `EP-M03` rather than silently treating
`python -m devolaflow.pre_decision.detect` as valid.
