# Loop v3 Functional Test System — SI-1 Gap Analysis

## 1. Objective and current baseline

This document is the SI-1 entry point for Loop v3. Its objective is to define
the evidence and implementation gaps between the repository's current
unit, artifact, ghost, schema, harness, and selected subprocess tests and a
consumer-callable functional test system. The target system is a
domain-first, offline, machine-readable capability matrix with a
parametrized runner and a hard gate. It must exercise live behavior through
the interfaces a consumer receives: installed console scripts,
`python -m` entrypoints, an installed wheel public API, and an offline npm
package.

This is a gap analysis and implementation contract. It does not claim that
the matrix, runner, hard gate, wheel smoke, npm pack row, or normalized plugin
audit already exists.

Current evidence establishes:

- The repository currently reports a v19.0.0 release, a 9.17/10 evaluator
  result, 92.0% global coverage, and explicit `INSUFFICIENT` historical
  deltas in `CHANGELOG.md:8-55`.
- The ordinary suite collected 5,535 cases, with 4,425 hand-declared test
  functions before parametrization. This is not Loop v3 functional coverage.
- Existing tests are broad and often behaviorally strong, but most call
  implementation functions directly, mock subprocesses, inspect source or
  registry shape, or exercise only selected real subprocess boundaries.
- The repository declares 13 console scripts in `pyproject.toml:27-42` and
  maintains a set of guarded or documented module entrypoints, but there is no
  complete installed-consumer inventory or parity gate.
- There is no `tests/functional/matrix.yaml`,
  `tests/functional/runner.py`, or `scripts/check_functional_matrix.py`.
- Fast/slow functional markers and a functional Make target do not yet exist.
  Existing `persistence_probe` and `deferred` markers are not equivalent to
  functional speed tiers.
- Existing wheel tests simulate a wheel-only boundary, but no built wheel
  artifact has been installed and exercised in a fresh offline environment.
- Existing npm tests cover syntax, help, version, and manifest-derived file
  listing, but do not execute the required offline pack inspection.
- Existing evidence supports retaining all five registered plugins as
  `suggest` plus explicit optional installation with `auto_install: false`.
- Static B4 review found safety, boundedness, evidence, and contract
  discrepancies that must become high-priority functional rows or design
  fixes.

The target live scope is limited to currently implemented and wired behavior.
Historical, deferred, aspirational, documentation-only, real host-consumer,
curl-transport, network, remote model, and published-registry claims do not
become required rows merely because they are mentioned in prose.

## 2. Evidence-backed deficiencies by priority

### P0 — Gate integrity and state safety

1. Required gate checks can be skipped while the standard gate passes
   (`B4-GATE-001`). This can convert absent build, test, lint, or acceptance
   evidence into a green result.
2. Synchronous timeout bounds caller waiting but does not stop a worker thread
   (`B4-DISP-002`). A timed-out callable can continue side effects after the
   caller has classified it as failed.
3. Handoff envelope writes have a check-then-replace race
   (`B4-HANDOFF-001`). Concurrent writers can overwrite an existing sequence
   file, violating S-9.
4. Local archive apply can partially move state before persistence failure
   (`B4-LA-002`), and archive consolidation can fail after the physical move
   (`B4-ARCH-001`).
5. The archive CLI implicitly approves every movable entry in a plan
   (`B4-LA-001`), while the documented contract requires exact prior approval
   of a selected subset.
6. The generated archive index can be rendered from the stale full plan
   (`B4-LA-003`), omitting prior mapping history and listing unselected
   entries.
7. A failed W-17 `git diff` probe is represented as available evidence with
   value `31` (`B4-HARNESS-001`), rather than preserving unavailable evidence
   as `INSUFFICIENT`.
8. Proposal scope filtering can accept lexical path substrings outside the
   repository (`B4-FB-001`), creating a containment risk.

Required direction: skipped required checks fail; timeout work adds an async
companion and process isolation for work that must stop; handoff creation uses
exclusive-create semantics; proposal paths use canonical repository-root
containment; archive apply uses a separate approved artifact plus preflight,
recovery, and a mapping-authoritative generated index.

### P1 — Public callable boundaries and extension contracts

1. The parallel dispatch wrapper calls `asyncio.run` and fails from an active
   event loop (`B4-DISP-003`). A supported async companion is required.
2. Explicit `max_parallelism: 0` is treated as absent and silently becomes
   the default rather than being rejected (`B4-DISP-001`). Explicit zero is
   rejected.
3. A structurally accepted third-party compression stage may lack
   `should_bypass`, then fail only during execution (`B4-COMP-001`).
   `should_bypass` is required by the compression protocol.
4. Direct `run_hooks` callers do not receive the same permissive exception
   isolation as the proposal emission adapter (`B4-LIFE-001`). The
   permissive `run_hooks` surface must isolate handler failures, log them, and
   preserve explicit strict behavior where selected.
5. The current test suite has no common typed outcome adapter for
   `PASS`, `FAIL`, `SKIP_OPTIONAL`, and `INSUFFICIENT`, and no hard fail for a
   bare required skip.

### P2 — Coverage, delivery, and documentation coherence

1. Existing tests do not provide a matrix source of truth, complete
   installed console-script execution, complete maintained module execution,
   or inventory parity.
2. The installed wheel public API has no curated stable-surface manifest and
   has no fresh offline build/install smoke.
3. The npm package has no required local `npm pack --dry-run --offline` row.
4. Fake-binary public-process behavior is missing for codegraph, RTK, and
   most plugin paths; mocks alone do not prove process protocol behavior.
5. Network prohibition is described but not established as an executable
   functional gate. The integration conftest's no-network claim has no
   visible autouse interception fixture.
6. Slow rows are not explicitly tiered or scheduled.
7. The derived plugin view contains operational-looking claims that disagree
   with or exceed the runtime registry SSOT.
8. Npm package README target scope is stale relative to the maintained five
   target implementation.
9. Legacy schema and reference prose retains stale L3, quality-score, 16-key,
   or otherwise superseded contract language.

## 3. B4 behavior findings and adjudicated classifications

The following findings preserve the B4 report's exact classifications and
source anchors. They are static findings unless explicitly marked
`INSUFFICIENT`; implementation must add deterministic functional evidence
before treating a behavior as closed.

| ID | Classification | Finding and required closure |
|---|---|---|
| `B4-GATE-001` | `LIKELY CODE BUG`; also a `TEST GAP` | `_evaluate_standard` checks only `"fail"` and can pass skipped checks. Source: `src/devolaflow/gate/scorer.py:1284-1320`, especially `:1288-1293` and PASS construction at `:1307-1313`; contract: `src/devolaflow/gate/scorer.py:1284`, `schemas/gate-report.schema.yaml:55-81`. Required closure: a standard PASS requires every required check to be `pass`; required `skip` fails. |
| `B4-DISP-001` | `LIKELY CODE BUG` | `sync_barrier.get("max_parallelism") or DEFAULT_MAX_CONCURRENCY` changes explicit zero to the default. Source: `src/devolaflow/dispatch.py:197-203`; contract: `src/devolaflow/dispatch.py:164-179`, `workflow-system/agent/references/wave-dispatch.md:49-51`. Required closure: reject explicit `0` and negative values with the documented executor error. |
| `B4-DISP-002` | `LIKELY CODE BUG` | Timed synchronous work runs through `asyncio.to_thread`; `asyncio.wait_for` can return timeout while the thread continues. Source: `src/devolaflow/agent_workspace/dispatch_executor.py:180-260`, `src/devolaflow/dispatch.py:144-151`; contract: `src/devolaflow/dispatch.py:144-151`, `:169-179`. Required closure: add an async companion and process-isolate timeout-sensitive synchronous work so the stop guarantee matches the public contract; add a post-timeout side-effect test. |
| `B4-DISP-003` | `LIKELY CODE BUG`; `TEST GAP` | Parallel `dispatch_wave_tasks` reaches `asyncio.run` and raises inside an active event loop. Source: `src/devolaflow/dispatch.py:223-226`, `src/devolaflow/agent_workspace/dispatch_executor.py:215-260`; contract: `src/devolaflow/dispatch.py:134-142`. Required closure: provide a supported async companion and test sync and async callers. |
| `B4-HANDOFF-001` | `LIKELY CODE BUG` | `write_envelope` checks existence, writes a temporary file, then calls `tmp.replace(target)`, allowing a race to overwrite a sequence file. Source: `src/devolaflow/agent_workspace/handoff.py:367-410`, `:399-409`; contract: `src/devolaflow/agent_workspace/handoff.py:7-15`, `schemas/agent-workspace/handoff-envelope.yaml`. Required closure: use exclusive-create/no-clobber creation and test concurrent same-sequence writers. |
| `B4-FB-001` | `LIKELY CODE BUG` | `_inside_devolaflow` uses lexical prefix/substring checks, so traversal or outside paths can pass. Source: `src/devolaflow/feedback.py:77-90`, `:251-262`; contract: `src/devolaflow/feedback.py:268-273`. Required closure: require a supplied canonical repository root, resolve paths, reject absolute and traversal escapes, and test outside targets. |
| `B4-HARNESS-001` | `LIKELY CODE BUG` | A failed `git diff base_ref -- tests/` probe emits `SignalResult(available=True, value=31)`. Source: `src/devolaflow/harness/evaluator.py:306-320`, `:451-452`; contract: `src/devolaflow/harness/evaluator.py:81-89`, `:764-771`, and unavailable-probe handling at `:306-313`. Required closure: return unavailable evidence with the command error and preserve `INSUFFICIENT`. |
| `B4-COMP-001` | `LIKELY CODE BUG` | `_CompressionStageProtocol` validates only `name` and `transform`, while `run` unconditionally invokes `should_bypass`. Source: `src/devolaflow/compression_pipeline.py:107-120`, `:344-362`, `:411-428`; contract: `src/devolaflow/compression_pipeline.py:111-115`, `:329-332`. Required closure: require `should_bypass` in the protocol and test a third-party stage at construction and execution. |
| `B4-LA-001` | `LIKELY CODE BUG` | `devola-local-archive --apply PLAN` builds approval from every `"move"` entry. Source: `src/devolaflow/cli.py:765-783`, `:803-822`, `src/devolaflow/local/archive.py:786-822`; contract: `src/devolaflow/local/archive.py:1005-1029`, `workflow-system/agent/references/local-archive.md`, `schemas/local-archive.schema.yaml:34-53`. Required closure: require a separate approved archive artifact that selects the exact entries; one approved entry must not approve others. |
| `B4-LA-002` | `LIKELY CODE BUG` | `apply_archive_plan` moves entries and appends mappings incrementally; later failure leaves earlier moves applied. Source: `src/devolaflow/local/archive.py:1087-1112`, `:1102-1110`; contract: `workflow-system/agent/references/local-archive.md`, `AGENTS.md` W-26. Required closure: preflight all operations, provide explicit recovery records/behavior, and ensure refused candidates remain in place or are recoverable by the declared mechanism. |
| `B4-LA-003` | `LIKELY CODE BUG` | Apply renders `render_index(plan)` from the original full plan, without prior mappings and with unselected entries. Source: `src/devolaflow/local/archive.py:1113-1123`, `:841-860`, `src/devolaflow/cli.py:688-727`; contract: `schemas/local-archive.schema.yaml:54-80`, `AGENTS.md` W-27-W-28. Required closure: mapping ledger is authoritative; index is a generated navigation view derived from authoritative current mappings and carries the generated marker. |
| `B4-ARCH-001` | `LIKELY CODE BUG` | `ArchiveManager.archive` moves the change and only then consolidates learnings, so consolidation failure leaves an archived change with an exception. Source: `src/devolaflow/agent_workspace/archive.py:329-338`, `:283-298`; contract: `src/devolaflow/agent_workspace/archive.py:283-289`. Required closure: define preflight/recovery state and make the archive artifact separate from physical move completion. |
| `B4-ARCH-002` | `LIKELY STALE/INCORRECT DOCUMENTATION`; `TEST GAP` | `ChangeStore.move_to_archive` delegates to `shutil.move`, while prose calls it atomic across valid configurations. Source: `src/devolaflow/agent_workspace/change.py:875-905`, contract wording at `:875-877`. Required closure: enforce/document same-device preconditions or describe the actual durability/recovery contract. |
| `B4-LIFE-001` | `TEST GAP`; possible `LIKELY CODE BUG` depending on API contract | `run_hooks` invokes handlers directly; exception isolation exists in `ProposalEmitter._fire_hook_chain`, not uniformly in direct callers. Source: `src/devolaflow/lifecycle/dispatcher.py:306-375`, `src/devolaflow/feedback_emit.py:361-378`; contract: `src/devolaflow/lifecycle/dispatcher.py:13-19`, `src/devolaflow/feedback_emit.py:23-25`. Required closure: make permissive `run_hooks` isolation explicit, log handler failures, and test direct callers plus strict callers. |
| `B4-DOC-001` | `LIKELY STALE/INCORRECT DOCUMENTATION` | Host bridge prose says five hosts while the headed matrix and implementation define six. Source: `workflow-system/agent/references/host-bridges.md:29-40`, `:62-71`; implementation: `src/devolaflow/hostbridge/normalize.py:3-5`, `:40`. Required closure: align prose with the live host contract and mark unsupported/deferred capabilities explicitly. |
| `B4-DOC-002` | `LIKELY STALE/INCORRECT DOCUMENTATION` | Compression prose says stages do not see each other's inputs, while the reducer passes the running payload sequentially. Source: `src/devolaflow/compression_pipeline.py:16-21`, `:209-215`, `:323-327`, `:404-461`. Required closure: document the sequential reducer and its `should_bypass` protocol accurately. |
| `B4-DOC-003` | `LIKELY STALE/INCORRECT DOCUMENTATION` | Wave schema retains L3 task terminology while current hierarchy is L0 Project to L1 Wave to L2 Task. Source: `schemas/wave-definition.schema.yaml:4-5`, `:29-35`; current contract: `workflow-system/agent/references/agent-hierarchy.md`, `src/devolaflow/dispatch.py:64-81`. Required closure: update live schema prose through the rule-controlled process or mark it historical. |

## 4. External callability gaps

The functional matrix must distinguish implementation evidence from consumer
callability. The following boundaries are partial or unavailable today:

- Console scripts: all 13 entries from `pyproject.toml:27-42` need derived
  inventory rows, installed invocation, stable help/valid/malformed behavior,
  stdout/stderr, exit code, timeout, and side-effect contracts. Existing
  direct tests in `tests/test_exercise_modules.py`,
  `tests/test_validate_gate_cli.py`, `tests/test_cli_local_commands.py`,
  `tests/test_plugin_upgrade.py`, and local archive test files do not prove
  installed executable behavior.
- Module entrypoints: maintained paths include
  `devolaflow.harness`, `devolaflow.hostbridge`,
  `devolaflow.pre_decision`, `devolaflow.task_adaptive_selector`,
  `devolaflow.build_skill`, `devolaflow.agent_workspace.reporter`,
  `devolaflow.agent_workspace.lint`, `devolaflow.local.workspace`, and
  `devolaflow.skills.slash_commands`. Existing direct `main` calls must be
  supplemented by isolated subprocess rows. The maintained wrapper
  `scripts/detect-repo-mode.sh:3` invokes
  `python -m devolaflow.pre_decision.detect`, but `detect.py` has no
  `__main__` guard; this entrypoint integrity gap must not be silently
  classified as working.
- Wheel API: `pyproject.toml:44-49` packages source under `src` and includes
  limited package data. `src/devolaflow/__init__.py:6-9` exposes version and
  `learnings` but no root public API manifest. Candidate curated public
  groups are `devolaflow.__version__`, `template_engine`, `gate`,
  `compressor`, `agent_workspace`, `harness`, `local`, `pre_decision`,
  `hostbridge`, `plugins`, and `skills`; optional integration groups remain
  provisional. A fresh offline wheel build/install must verify only the
  supported wheel boundary and must distinguish missing optional dependency
  from package defect.
- Npm: `packages/npm/package.json` and
  `packages/npm/bin/devola-flow.js` have local syntax/help/version/file-list
  evidence, but `npm pack --dry-run --offline` and packed-bin execution are
  uncovered. `packages/npm/README.md:9-15` claims only Cursor and Claude,
  while the bin at lines `26-48` resolves five targets:
  `cursor`, `claude`, `codex`, `kimicode`, and `dsh`. This documentation
  drift must be fixed before the target matrix is stable.
- Hostbridge: synthetic stdin/stdout/stderr protocol execution is in scope;
  real Cursor, Claude Code, Codex, KimiCode, DSH, Copilot, hooks, editors,
  UI, and remote host consumers are explicitly excluded.
- Curl installers, live GitHub/npm/pip downloads, remote model providers, and
  published registry installation are outside the required matrix. Their
  exclusion is a scope decision, not evidence that those integrations work.

Required runner policy: every subprocess has a bounded timeout and captured
stdout/stderr; malformed output, signal termination, unexpected exit, and
missing required prerequisites fail. Optional live-binary rows may return
`SKIP_OPTIONAL` only with a declared prerequisite and exact reason. Required
rows never become green through an unclassified skip.

## 5. Plugin coupling, cleanup, and disposition

The runtime owner is
`workflow-system/agent/knowledge/runtime-plugins.yaml`. The derived
presentation view is `workflow-system/agent/plugins.yaml`. The owner and view
currently contain the same five IDs and order, but the view carries
operational-looking fields that can drift from the owner. The coupling audit
found no basis for removal and requires the following disposition:

| Plugin | Evidence-backed coupling | Required disposition |
|---|---|---|
| `ui-pro` | Runtime installer/lifecycle resolution, `web-design` seed pairing, UI design assertion, and captured init-log shape in `tests/integration/test_ui_pro_shape_contract.py:16-35`. | Keep `suggest`; explicit optional install. Preserve probe-and-degrade. Remove or relabel stale derived probe/workflow/install fields. |
| `rtk` | `src/devolaflow/shell_proxy/` wrapper, `pre_shell_call` lifecycle hook, whitelist/recipe SSOT, `DEVOLAFLOW_RTK_PROXY`, and mandatory `rtk gain` distinction. | Keep `suggest`; explicit optional install. Preserve literal flag default-off and passthrough. Make curl fallback capability explicit rather than generic. |
| `si-chip` | Typed public bridge, dispatch dogfood cycle, post-skill-edit hook, self-improvement workflows, iteration-delta gate, parser contracts, and explicit unavailable/deferred result. | Keep `suggest`; explicit optional install. Preserve deep opt-in and defer behavior. Do not apply an unproven generic Cargo fallback to its hosted installer. |
| `codegraph` | Public researcher API, subprocess wrapper, markers, repo-init and agent-facing workflow wiring, install path, and degraded empty sentinels. Automatic Python consumption by gate/planning/selective-test execution is `INSUFFICIENT`. | Keep `suggest`; explicit optional install. Reduce derived claims or wire a real consumer in a separate owned change; do not infer automatic gate use. |
| `impeccable` | `web-design` refinement and verification stages, detector contract, installer/lifecycle path, and degraded behavior. Automatic production detector invocation is `INSUFFICIENT`. | Keep `suggest`; explicit optional install. Refresh installed skills after upgrades or label update as operator-only. |

Cross-cutting plugin decisions:

1. Retain all five rows as `tier: suggest` with registry
   `auto_install: false`.
2. Explicit optional installation may use existing activation surfaces,
   including `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` where applicable; no new
   `DEVOLAFLOW_*` flag is authorized.
3. Reduce `workflow-system/agent/plugins.yaml` to capability, role, and
   stage presentation, or generate operational fields from the runtime SSOT.
   Do not maintain a second hand-authored set of probes, install commands,
   workflow claims, or update commands.
4. Make curl fallback explicit per plugin. Do not apply generic Cargo fallback
   to `si-chip` without evidence that its canonical resource is
   Cargo-installable; retain only evidence-backed fallback behavior for RTK.
5. Refresh npm-installed integrations after package upgrades for
   `ui-pro`, `codegraph`, and `impeccable`, or explicitly distinguish package
   freshness from integration freshness.
6. Add selectable per-plugin global install profiles. A global bundle must
   not force every suggest-tier tool merely because `--global` was selected;
   keep the bundle-wide opt-out for compatibility.
7. Review historical `nines-assisted` naming separately. It is not evidence
   that the removed NineS plugin is a current dependency.
8. A remove disposition is permitted only after no-live-consumer evidence and
   same-change removal/decoupling of every caller, workflow, derived-view,
   documentation, and test reference. Current evidence does not satisfy it.

## 6. Operator decisions for Loop v3

The following decisions are closed requirements:

- Global coverage target is **at least 90%**.
- Modified/new Python module floor is **75%**, and S-3 must be updated to
  state this settled floor and distinguish it from the global target.
- Skipped required gate checks fail. `SKIP_OPTIONAL` is valid only for an
  optional row with a declared prerequisite and exact reason.
- Explicit parallelism `0` is rejected; it does not mean default or
  unbounded behavior.
- Add an async dispatch companion and process-isolate timeout-sensitive
  synchronous work so timeout semantics are honest.
- Handoff envelope creation uses exclusive-create/no-clobber semantics.
- Proposal containment is checked against the canonical repository root, with
  canonical resolution and rejection of absolute/traversal escapes.
- Archive apply uses a separate approved archive artifact. Preflight checks,
  recovery behavior, and mapping-authoritative index generation are required.
  Deletion remains operator-only.
- `should_bypass` is required in the compression stage protocol.
- `run_hooks` has permissive isolation: handler failures are logged and
  isolated without mutating the dispatch; strict paths retain explicit
  escalation behavior.
- Retain all five plugins as `suggest` with explicit optional installation.
- Reduce the plugin derived view to presentation data.
- Keep curl fallback explicit and per-plugin.
- Refresh npm integrations after upgrades.
- Provide selectable per-plugin global installation.
- Fix stale documentation and schema prose, including host count, compression
  reducer semantics, stale L3 terminology, stale 16-key claims, npm target
  scope, and stale operational plugin fields.
- Use a curated live API scope. Do not treat every importable symbol,
  underscored implementation module, compatibility export, historical
  surface, or optional integration as stable without a declared contract.
- The release version is decided later by evidence and the existing release
  decision rule; this SI-1 artifact does not pre-claim a version.

## 7. O-matrix and PV decomposition

The O-matrix is the implementation-facing reconciliation of objective,
evidence, and closure. `REQ` means required for the live scope,
`OPT` means optional with explicit prerequisite, and `EXCL` means excluded
from the functional loop.

| O-ID | Domain and observable contract | Current evidence | Priority | Status/closure |
|---|---|---|---|---|
| `O-01` | Matrix schema, stable IDs, one adapter per row, typed outcomes | No functional matrix or runner | P0 / REQ | `INSUFFICIENT`; PV-0 |
| `O-02` | Missing row, duplicate ID/surface, missing adapter, zero rows, unclassified skip, and disagreement fail | No hard gate | P0 / REQ | `INSUFFICIENT`; PV-0 |
| `O-03` | All 13 installed console scripts | Direct implementation tests only | P1 / REQ | `INSUFFICIENT`; PV-1 |
| `O-04` | Maintained `python -m` inventory and subprocess contracts | Partial real subprocess evidence | P1 / REQ | `INSUFFICIENT`; PV-1 |
| `O-05` | Gate skipped-check failure, zero parallelism rejection, async dispatch, process timeout | Static B4 findings | P0 / REQ | `INSUFFICIENT`; PV-1 |
| `O-06` | Handoff exclusive create and append-only bytes | Schema/API checks, race untested | P0 / REQ | `INSUFFICIENT`; PV-1 |
| `O-07` | Canonical proposal containment | Lexical filter has static defect | P0 / REQ | `INSUFFICIENT`; PV-1 |
| `O-08` | Archive approved artifact, preflight/recovery, mapping-authoritative index | Direct tests miss race/state combinations | P0 / REQ | `INSUFFICIENT`; PV-4 |
| `O-09` | Compression protocol, sequential reducer, `should_bypass` | Unit coverage plus protocol mismatch | P1 / REQ | `INSUFFICIENT`; PV-1 |
| `O-10` | Permissive `run_hooks` isolation | Adapter-specific isolation only | P1 / REQ | `INSUFFICIENT`; PV-1 |
| `O-11` | Curated installed wheel API and wheel-only local behavior | Simulated wheel tests | P1 / REQ | `INSUFFICIENT`; PV-2 |
| `O-12` | Offline npm syntax/help/version/pack/file list/packed bin | Pack row uncovered; README drift | P2 / REQ | `INSUFFICIENT`; PV-2 |
| `O-13` | Plugin owner/derived parity, all five rows, suggest/default-off/opt-in | Distributed unit and fixture evidence | P1 / REQ | Coupling artifact `INSUFFICIENT`; PV-3 |
| `O-14` | Fake binaries for RTK, codegraph, and plugin degraded paths | Mocked subprocesses | P1 / REQ | `INSUFFICIENT`; PV-3/PV-4 |
| `O-15` | Slow tier, network prohibition, telemetry, release insertion | No functional tier/gate | P2 / REQ | `INSUFFICIENT`; PV-4 |
| `O-16` | Curl installers and real host consumers | Explicitly out of scope | P2 / EXCL | Closed by scope; no required row |
| `O-17` | Optional live binary probe | No live binary required | P2 / OPT | `SKIP_OPTIONAL` only with prerequisite/reason; PV-3 |

Mandatory PV sequence:

### PV-0 — Matrix infrastructure

- Add the machine-readable schema, loader, stable row validation, typed
  outcomes, parametrized runner, fixture factory, inventory parity, network
  prohibition, and hard-fail gate.
- Add fast/slow selection without a new environment flag.
- Emit a deterministic functional result artifact under
  `.local/telemetry/functional-test-results.json`.
- Keep initial test-function additions near 4-6; use parametrization for rows.

### PV-1 — Core entrypoints and high-priority bug fixes

- Cover installed console and maintained module entrypoints for identity,
  templates, harness, gates, selectors, workspace, and core CLI behavior.
- Implement and test skipped required gate failure, explicit zero rejection,
  async dispatch companion, process-isolated timeout behavior, exclusive
  handoffs, canonical proposal containment, required `should_bypass`, and
  permissive hook isolation.
- Add malformed input, bounded failure, and side-effect assertions.
- Keep additions near 8-12 test functions after reuse.

### PV-2 — Wheel, npm, and documentation

- Build/install the wheel offline in an isolated environment and exercise the
  curated live API plus wheel-only local initialization.
- Run node syntax/help/version, offline npm pack, packed-bin execution, and
  file-list inspection.
- Fix npm README target scope and stale core documentation/schema prose.
- Keep additions near 5-7 test functions after reuse.

### PV-3 — Plugin cleanup

- Add the normalized five-plugin coupling audit and owner/derived parity.
- Preserve all five suggest rows and explicit optional installation.
- Add fake-binary success, malformed, nonzero, timeout, missing-binary,
  version-probe, degraded, and no-network rows.
- Implement explicit curl fallback, integration refresh after npm upgrades,
  reduced derived presentation view, and selectable global profiles.
- Keep additions near 7-10 test functions after reuse.

### PV-4 — Remaining slow rows and gate integration

- Complete local archive approval/preflight/recovery/mapping/index rows,
  shell proxy, codegraph process behavior, hostbridge synthetic protocol,
  broader subprocess compositions, timing, and telemetry.
- Wire full/release slow rows into the hard gate and release path.
- Run the full matrix, release integration, and midpoint W-17 reconciliation.
- Keep additions near 8-12 test functions after reuse.

PV boundaries may be combined only when test-function and timeout budgets
remain auditable. Failed rows are repaired or escalated; they are never
deleted or reclassified to make a PV pass.

### W-17 estimate

The baseline for this loop is 0 new functional test functions and 0
functional matrix cases, regardless of the existing 5,535 collected cases.
The preferred budget is:

| PV | Estimated new test functions | Expected collected-case growth |
|---|---:|---:|
| PV-0 | 4-6 | 20-40 |
| PV-1 | 8-12 | 50-100 |
| PV-2 | 5-7 | 20-45 |
| PV-3 | 7-10 | 35-70 |
| PV-4 | 8-12 | 35-75 |
| Cycle total | 32-47 | 160-330 |

The per-PV estimates remain below the +30 ceiling and the cycle estimate
remains below +150. A midpoint audit is mandatory before PV-4 because
collected parametrized cases still impose runtime cost even when they do not
count as new function declarations. If reuse cannot keep the cycle below
+150, defer non-essential rows and record the resulting evidence as
`INSUFFICIENT`; do not reduce the required matrix to fit the budget.

## 8. Acceptance criteria

Loop v3 is accepted only when:

1. This SI-1 analysis and all five Phase 0 reports are present, internally
   reconciled, and required decisions have no hidden `INSUFFICIENT` state.
2. The matrix covers every confirmed live domain, has stable unique IDs,
   validates all paths and adapters, and reconciles all 13 console scripts
   plus maintained module entrypoints.
3. The parametrized runner executes every required fast row and reports
   `PASS`, `FAIL`, `SKIP_OPTIONAL`, and `INSUFFICIENT` separately.
4. The hard gate fails for missing rows, duplicate IDs or surfaces, missing
   adapters, zero-row matrices, required skips, unclassified exceptions,
   unexpected output/exit behavior, missing required prerequisites, and
   plugin cleanup disagreement.
5. Required gate checks cannot be skipped into a PASS; explicit parallelism
   zero is rejected; timeout, handoff, proposal, compression, hook, and
   archive contracts have deterministic regression rows.
6. Console scripts, maintained `python -m` surfaces, the curated installed
   wheel API, and offline npm pack have executable behavioral evidence.
7. Wheel rows work without the source checkout; npm rows use no network;
   curl and real host consumers remain explicitly excluded.
8. Archive tests prove separate approval, preflight/recovery behavior,
   operator-only deletion, append-only mappings, and an honest
   mapping-authoritative generated index.
9. The plugin audit records all five rows, verifies coupling and parity, and
   lands `suggest` plus explicit optional installation with
   `auto_install: false`.
10. Derived plugin data is presentation-only or generated from the runtime
    SSOT; fallback and integration-refresh behavior are explicit.
11. Global coverage is at least 90%, every modified/new Python module meets
    the settled 75% floor, and S-3 is updated to match that policy.
12. Fast and slow tiers, timeouts, network isolation, and telemetry are
    enforced without a new `DEVOLAFLOW_*` flag.
13. W-17 stays within +30 new test functions per PV and +150 per cycle, with
    a midpoint forecast and collected-case growth recorded.
14. SI-10, lint, format, version, harness, template, skill, drift, coverage,
    functional, and release-preflight gates pass with recorded evidence.
15. Release version selection occurs only after evidence and the existing
    release decision rule; no version is claimed by this artifact.

## 9. Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Functional rows duplicate 5,535 existing cases | W-17 overrun and slow CI | Reuse assertions, parameterize rows, count declared functions and collected cases, defer non-essential rows explicitly. |
| Wheel and npm environments vary | False failures or silent skips | Probe prerequisites, classify missing required tooling as `INSUFFICIENT`, use offline isolated environments and bounded timeouts. |
| Process isolation changes timeout semantics | Platform-specific behavior or resource leaks | Add a small explicit process executor, test termination and cleanup, document supported platforms and fallback failure. |
| Exclusive handoff creation races | Lost audit artifacts | Use no-clobber creation, retain immutable sequence checks, and test concurrent writers. |
| Archive recovery is underspecified | Physical and ledger state diverge | Approve a separate artifact, preflight all operations, record recovery state, and derive index only from authoritative mappings. |
| Plugin cleanup removes a live contract | Broken workflows or degraded paths | Require per-plugin caller graph and same-change decoupling before any removal; current disposition is retain. |
| Derived plugin view drifts again | Operators receive stale commands | Make the view presentation-only or generate operational values from the SSOT. |
| Documentation and schemas remain contradictory | Matrix rows encode the wrong contract | Correct stale prose before final gate closure and add parity checks for live terminology/layout. |
| Existing historical/deferred surfaces enter the required matrix | Scope inflation and ghost features | Apply curated live API policy; record excluded or deferred surfaces with evidence instead of promoting them. |

## 10. Explicit INSUFFICIENT evidence to close

The following evidence is explicitly unresolved and must be closed or
escalated before release. It must not be inferred from imports, source
presence, registry membership, direct helper calls, changelog claims, or
ordinary test collection:

- Runtime reproduction of every B4 finding, including skipped checks,
  explicit zero, active-loop dispatch, post-timeout side effects,
  concurrent handoff writers, traversal/absolute proposal paths, failed W-17
  probes, third-party compression stages, hook exceptions, exact archive
  approval subset, partial apply/recovery, stale index, consolidation
  failure, and cross-filesystem archive behavior.
- Complete installed console-script invocation and exit/output evidence for
  all 13 scripts.
- Complete maintained `python -m` subprocess inventory, including the
  `pre_decision.detect` wrapper mismatch.
- Built wheel contents, isolated offline installation, curated API imports
  and calls, package-data behavior, and wheel-only local initialization.
- Actual offline npm pack result, packed-bin help/version, and file-list
  parity. Published registry availability, provenance acceptance, and real
  consumer installation remain excluded.
- A normalized machine-readable plugin coupling graph joining runtime owner,
  derived view, workflow callers, lifecycle hooks, public wrappers, and
  tests.
- Fake executable protocol evidence for codegraph, RTK, and retained plugin
  probes, including timeout, malformed, nonzero, missing, and success cases.
- Executable network denial for the functional runner and proof that required
  rows cannot silently skip due to Node, build, binary, or environment
  absence.
- Actual host-by-host adapter parity and live upstream plugin behavior.
  Synthetic hostbridge protocol is required; real host-consumer execution is
  excluded.
- Current harness artifact-content validation, historical delta closure, and
  final W-2/W-3/W-7/W-16 evidence. Existing explicit `INSUFFICIENT` results
  remain insufficient until resolved by machine evidence.
- Final global coverage and per-module floor measurements after the new
  functional modules are added, plus the required S-3 governance update.
- Release-version tier decision after accepted implementation evidence. This
  analysis intentionally leaves the version undecided.

Until these items are closed, the correct status is `INSUFFICIENT`, not
`PASS`, and the Loop v3 implementation remains ready to start after SI-1,
not already implemented.
