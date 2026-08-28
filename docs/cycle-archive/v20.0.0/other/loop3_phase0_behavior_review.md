# Loop v3 Phase 0 Behavior-versus-Design Review

## Review identity

- Role: L2 audit agent B4
- Review mode: read-only static trace
- Scope: current repository implementation, live agent-facing contracts, schemas, and changelog claims
- Output: behavior-versus-design matrix only
- Runtime evidence: not collected; runtime-dependent conclusions are marked `INSUFFICIENT`
- Classification vocabulary: `LIKELY CODE BUG`, `LIKELY STALE/INCORRECT DOCUMENTATION`, `TEST GAP`, `NO DISCREPANCY`

No source, test, Makefile, plan, or documentation fix was applied by this review.

## Executive findings

The strongest observable discrepancies are concentrated in safety and boundedness boundaries:

1. The local-archive CLI converts every movable entry in a supplied plan into approval, so its CLI surface cannot express the documented exact approved subset.
2. Local-archive application moves entries before all persistence is durable and renders an index from the stale full plan, producing partial state and index drift.
3. Handoff writes use a check-then-replace sequence; concurrent writers can overwrite an existing envelope despite the append-only contract.
4. Synchronous timed dispatches run in worker threads. `wait_for` bounds the await, but cannot cancel the underlying thread, so work may continue after a timeout outcome is returned.
5. The harness marks a failed `git diff` probe as an available value of `31`, rather than preserving unavailable evidence as `INSUFFICIENT`.
6. Feedback proposal scope checking accepts path-like strings outside the repository when they contain an allowed substring.

These findings should be adjudicated before implementation work is scheduled because several can leave externally visible state inconsistent with the reported result.

## Behavior-versus-design matrix

### B4-GATE-001 — skipped standard checks can pass

- Classification: `LIKELY CODE BUG`; also a `TEST GAP`
- Severity: High
- Matrix ID: `B4-GATE-001`
- Observable behavior: `_evaluate_standard` appends failures only when build, test, lint, or acceptance status equals `"fail"`. A `"skip"` status is ignored. A gate with skipped checks and no review blockers/criticals returns `PASS`.
- Implementation anchor: `src/devolaflow/gate/scorer.py:1284-1320`
- Contract anchors:
  - `src/devolaflow/gate/scorer.py:1284` documents this as a single-shot gate where “all checks must pass”.
  - `schemas/gate-report.schema.yaml:55-81` exposes `pass | fail | skip` as distinct check outcomes.
- Evidence: The implementation tests equality with `"fail"` at `src/devolaflow/gate/scorer.py:1288-1293`; there is no `"skip"` handling before the PASS construction at `src/devolaflow/gate/scorer.py:1307-1313`.
- Impact: A missing build, test, or lint signal can be externally reported as a passing standard gate. This is materially different from treating missing evidence as unavailable.
- Adjudication question: Is `skip` intended to be neutral for the standard gate, or must standard PASS require every required check to have status `pass`? If neutral is intended, the “all checks must pass” contract and a regression test should be changed together.

### B4-DISP-001 — explicit zero parallelism silently defaults

- Classification: `LIKELY CODE BUG`
- Severity: Medium
- Matrix ID: `B4-DISP-001`
- Observable behavior: When `max_concurrency` is omitted, `sync_barrier.max_parallelism` is resolved with `or DEFAULT_MAX_CONCURRENCY`. An explicit `0` therefore becomes the default `4` instead of being rejected.
- Implementation anchor: `src/devolaflow/dispatch.py:197-203`
- Contract anchors:
  - `src/devolaflow/dispatch.py:164-179` says the concurrency override must be at least `1` and that invalid resolved concurrency raises `ExecutorError`.
  - `workflow-system/agent/references/wave-dispatch.md:49-51` defines the precedence order and a bounded cap.
- Evidence: `sync_barrier.get("max_parallelism") or DEFAULT_MAX_CONCURRENCY` treats `0` as absent; explicit negative values remain truthy and are handled differently.
- Impact: Configuration behavior depends on the sign of an invalid value. An operator who deliberately sets zero receives parallelism four rather than a loud contract error.
- Adjudication question: Should `0` be rejected as an explicit invalid cap, or is zero intended to mean “use default”? The schema and API documentation should state one rule.

### B4-DISP-002 — synchronous timeout does not stop underlying work

- Classification: `LIKELY CODE BUG`
- Severity: High
- Matrix ID: `B4-DISP-002`
- Observable behavior: Timed synchronous callables are sent through `asyncio.to_thread`; `asyncio.wait_for` can return a timeout outcome while the worker thread continues running. The caller sees timeout, but the callable may continue filesystem, network, or process side effects after dispatch returns.
- Implementation anchors:
  - `src/devolaflow/agent_workspace/dispatch_executor.py:180-260` (executor timeout and sync-to-thread path)
  - `src/devolaflow/dispatch.py:144-151` (default-on timeout contract)
- Contract anchors:
  - `src/devolaflow/dispatch.py:144-151` says a breach cancels the task and surfaces `TaskOutcome(... TimeoutError)`.
  - `src/devolaflow/dispatch.py:169-179` promises bounded task outcomes.
- Evidence: The documented cancellation guarantee is stronger than Python thread cancellation semantics. No cooperative cancellation token or process isolation is visible in the traced dispatch contract.
- Impact: A timed-out task can mutate state after the wave has classified it as failed, violate ownership assumptions, or race with retry work. The timeout bounds the wait, not the execution.
- Adjudication question: Is the intended guarantee only “bounded caller wait”, or “underlying callable stops”? If the latter, should synchronous work be process-isolated or require cooperative cancellation?

### B4-DISP-003 — parallel dispatch is unsafe inside an active event loop

- Classification: `LIKELY CODE BUG`; `TEST GAP`
- Severity: Medium
- Matrix ID: `B4-DISP-003`
- Observable behavior: A parallel wave reaches the executor path through `dispatch_wave_tasks`, which uses `asyncio.run`. Calling it from an already-running event loop raises `RuntimeError`.
- Implementation anchors:
  - `src/devolaflow/dispatch.py:223-226`
  - `src/devolaflow/agent_workspace/dispatch_executor.py:215-260`
- Contract anchor: `src/devolaflow/dispatch.py:134-142` describes the public wrapper as the canonical dispatch boundary but does not document an active-loop restriction or async alternative.
- Evidence: The sequential branch avoids loop initialization, but the parallel branch unconditionally enters the `asyncio.run` path. No active-loop detection or awaitable API was found in the traced wrapper.
- Impact: The same public API works in synchronous callers and fails in asynchronous orchestrators, despite the task execution model being asynchronous.
- Adjudication question: Is `dispatch_wave_tasks` intentionally synchronous-only? If yes, should it reject active-loop use with an explicit contract error; if no, should an async companion be the supported boundary?

### B4-HANDOFF-001 — append-only envelope writes can overwrite on a race

- Classification: `LIKELY CODE BUG`
- Severity: High
- Matrix ID: `B4-HANDOFF-001`
- Observable behavior: `write_envelope` checks `target.exists()`, writes a temporary file, then calls `tmp.replace(target)`. Two writers can both observe an absent target and the later replacement can overwrite the first envelope.
- Implementation anchors:
  - `src/devolaflow/agent_workspace/handoff.py:367-410`
  - `src/devolaflow/agent_workspace/handoff.py:399-409`
- Contract anchors:
  - `src/devolaflow/agent_workspace/handoff.py:7-15` states existing sequence files are immutable.
  - `schemas/agent-workspace/handoff-envelope.yaml` defines the append-only envelope surface.
- Evidence: The collision check is separate from the replacing write. `Path.replace` is replacement semantics, not no-clobber creation.
- Impact: Concurrent L0/L1/L2 writers can lose an envelope without an `EnvelopeImmutableError`, corrupting the audit chain and violating S-9.
- Adjudication question: Must concurrent same-sequence authors be serialized with an exclusive create/link protocol, or is concurrent writing explicitly out of scope? If out of scope, where is that operational boundary enforced?

### B4-FB-001 — proposal path filter accepts outside paths

- Classification: `LIKELY CODE BUG`
- Severity: Medium
- Matrix ID: `B4-FB-001`
- Observable behavior: `_inside_devolaflow` accepts any path that starts with an allowed relative prefix or contains `"/<allowed-prefix>"`. Strings such as `../src/devolaflow/other.py` or `outside-repo/src/devolaflow/other.py` can satisfy the substring test.
- Implementation anchors:
  - `src/devolaflow/feedback.py:77-90`
  - `src/devolaflow/feedback.py:251-262`
- Contract anchor: `src/devolaflow/feedback.py:268-273` says proposals for files outside the repository are rejected.
- Evidence: The predicate has no repository-root argument and performs lexical substring matching rather than canonical containment.
- Impact: A proposal target outside the active repository can pass the scope filter. The downstream proposal writer could then expose or modify an unintended path if it trusts `target_file`.
- Adjudication question: Should scope be checked against a supplied repository root with canonical path containment, and should traversal or absolute paths always be refused?

### B4-HARNESS-001 — failed W-17 probe becomes fabricated available evidence

- Classification: `LIKELY CODE BUG`
- Severity: High
- Matrix ID: `B4-HARNESS-001`
- Observable behavior: If `git diff base_ref -- tests/` returns a nonzero exit code, `collect_signals` emits `SignalResult(available=True, value=31)` for `w17_new_tests`.
- Implementation anchors:
  - `src/devolaflow/harness/evaluator.py:306-320`
  - `src/devolaflow/harness/evaluator.py:451-452`
- Contract anchors:
  - `src/devolaflow/harness/evaluator.py:81-89` defines explicit typed signals with availability.
  - `src/devolaflow/harness/evaluator.py:764-771` declares the overall result `INSUFFICIENT` when required slots are unavailable.
  - `src/devolaflow/harness/evaluator.py:306-313` already uses explicit unavailable evidence for a probe that could not run.
- Evidence: The value `31` is not derived from diff output. It is marked available and then scored as a W-17 failure by `_w17_score`, so the evaluator can remain complete rather than report missing evidence.
- Impact: A failed base-ref probe is represented as a real measured count. This can make evaluator output look complete and can hide the cause of a repository or reference failure.
- Adjudication question: Is `31` a deliberate hard-fail sentinel? If so, where is that sentinel specified? Otherwise, should a nonzero `git diff` return an unavailable signal with the command error?

### B4-COMP-001 — third-party stage protocol is incomplete at runtime

- Classification: `LIKELY CODE BUG`
- Severity: Medium
- Matrix ID: `B4-COMP-001`
- Observable behavior: `_CompressionStageProtocol` requires only `name` and `transform`, and `CompressionPipeline.__post_init__` checks those attributes. `run` then unconditionally calls `stage.should_bypass`, which a structurally conforming third-party object may not provide.
- Implementation anchors:
  - `src/devolaflow/compression_pipeline.py:107-120`
  - `src/devolaflow/compression_pipeline.py:344-362`
  - `src/devolaflow/compression_pipeline.py:411-428`
- Contract anchors:
  - `src/devolaflow/compression_pipeline.py:111-115` says third-party objects can satisfy the protocol.
  - `src/devolaflow/compression_pipeline.py:329-332` describes construction as a composition primitive accepting protocol implementations.
- Evidence: The accepted protocol surface and the invoked runtime surface differ.
- Impact: A plugin stage can pass construction validation and fail with `AttributeError` only when executed. This makes the extension boundary non-deterministic and bypasses the documented strict/best-effort stage error handling.
- Adjudication question: Should `should_bypass` be part of the required protocol, or should the pipeline normalize missing bypass behavior to `False`?

### B4-LA-001 — CLI approval applies every movable entry

- Classification: `LIKELY CODE BUG`
- Severity: Critical
- Matrix ID: `B4-LA-001`
- Observable behavior: `devola-local-archive --apply PLAN` loads the plan and constructs `approved_entries` from every entry whose action is `"move"`. It then passes that complete tuple to `apply_archive_plan`.
- Implementation anchors:
  - `src/devolaflow/cli.py:765-783`
  - `src/devolaflow/cli.py:803-822`
  - `src/devolaflow/local/archive.py:786-822`
- Contract anchors:
  - `src/devolaflow/local/archive.py:1005-1029` requires an explicit approved subset.
  - `workflow-system/agent/references/local-archive.md` describes report-only planning followed by explicit approval of physical moves.
  - `schemas/local-archive.schema.yaml:34-53` defines plan entries and refusal findings but no CLI-wide “approve all move entries” exception.
- Evidence: The library API can accept `Sequence[PlanEntry]` or `Sequence[str]` for a subset, but the CLI has no argument or approval artifact field that selects a subset. Passing the report artifact applies all movable entries.
- Impact: An operator intending to approve one task cannot express that intent through the documented CLI; additional movable entries are approved implicitly.
- Adjudication question: Is `--apply PLAN` intentionally “approve every move in this exact plan”, or must the CLI support an exact approved subset artifact/selection? The answer changes the safety meaning of the command.

### B4-LA-002 — archive apply can leave partial physical progress

- Classification: `LIKELY CODE BUG`
- Severity: High
- Matrix ID: `B4-LA-002`
- Observable behavior: `apply_archive_plan` loops over selected entries, calls `shutil.move`, then appends a mapping. If a later move or mapping append fails, earlier moves remain applied and the result is `refused=True`.
- Implementation anchors:
  - `src/devolaflow/local/archive.py:1087-1112`
  - `src/devolaflow/local/archive.py:1102-1110`
- Contract anchors:
  - `workflow-system/agent/references/local-archive.md` states refused candidates remain in place.
  - `AGENTS.md` W-26 requires refusal findings and leaves refused candidates in place.
- Evidence: The error path returns the already populated `applied` and `mappings` collections; it does not roll back earlier moves.
- Impact: A refused operation can partially reorganize the task tree. Retry behavior then encounters missing sources or existing destinations and requires manual reconciliation.
- Adjudication question: Is partial progress an accepted apply semantic? If not, should apply preflight all persistence operations and use rollback/recovery records, or constrain one apply to one physical move?

### B4-LA-003 — generated index is rendered from stale/incomplete state

- Classification: `LIKELY CODE BUG`
- Severity: High
- Matrix ID: `B4-LA-003`
- Observable behavior: After applying selected entries, the implementation writes `render_index(plan)`, where `plan` is the original full plan. It does not merge prior mapping records, and it includes unselected plan entries.
- Implementation anchors:
  - `src/devolaflow/local/archive.py:1113-1123`
  - `src/devolaflow/local/archive.py:841-860`
  - `src/devolaflow/cli.py:688-727` (doctor drift checks)
- Contract anchors:
  - `schemas/local-archive.schema.yaml:54-80` says the index is generated navigation and the mapping ledger is authoritative.
  - `AGENTS.md W-27-W-28` requires append-only mappings and an honest generated index.
- Evidence: The doctor compares index pairs with current plan and mapping pairs. The apply path can produce an index that lists unselected sources, omits historical mappings, and is therefore inconsistent with the post-apply mapping ledger.
- Impact: The successful physical move can immediately create a drift finding; navigation can point to sources that still exist or omit archived tasks.
- Adjudication question: Should the index represent only current plan entries, all mapping history, or both? Define the exact source set before changing the writer.

### B4-ARCH-001 — archive manager is not transactionally atomic

- Classification: `LIKELY CODE BUG`
- Severity: High
- Matrix ID: `B4-ARCH-001`
- Observable behavior: `ArchiveManager.archive` rewrites STATUS, moves the folder, and only then consolidates learnings. A consolidation exception is raised after the physical move has succeeded.
- Implementation anchors:
  - `src/devolaflow/agent_workspace/archive.py:329-338`
  - `src/devolaflow/agent_workspace/archive.py:283-298`
- Contract anchor: `src/devolaflow/agent_workspace/archive.py:283-289` states that the archive stays atomic while listing consolidation as a raising failure.
- Evidence: The move is a separate completed filesystem operation before `_consolidate_change_learnings` is called; no compensating move or durable recovery marker is shown.
- Impact: The caller receives an exception while the change is already in the archive and STATUS is already `ARCHIVED`. A retry follows the idempotent archived path and does not necessarily complete the failed consolidation.
- Adjudication question: Does “atomic” mean atomic physical move only, or atomic completion of move plus consolidation? If the latter, what recovery state is authoritative after consolidation failure?

### B4-ARCH-002 — “atomically move” overstates cross-filesystem behavior

- Classification: `LIKELY STALE/INCORRECT DOCUMENTATION`; `TEST GAP`
- Severity: Low
- Matrix ID: `B4-ARCH-002`
- Observable behavior: `ChangeStore.move_to_archive` delegates to `shutil.move`.
- Implementation anchor: `src/devolaflow/agent_workspace/change.py:875-905`
- Contract anchor: `src/devolaflow/agent_workspace/change.py:875-877` describes the operation as an atomic move.
- Evidence: Same-filesystem rename can be atomic, but `shutil.move` can copy and remove across filesystems. The implementation does not assert same-device placement.
- Impact: Operators may infer crash-safe atomicity from documentation that is not guaranteed for every valid configured directory.
- Adjudication question: Are active and archive roots required to share a filesystem device? If yes, enforce/document that precondition; if no, replace “atomic” with the actual copy/move durability contract.

### B4-LIFE-001 — direct lifecycle handler exceptions are not isolated

- Classification: `TEST GAP`; possible `LIKELY CODE BUG` depending on API contract
- Severity: Medium
- Matrix ID: `B4-LIFE-001`
- Observable behavior: `run_hooks` invokes each registered handler directly. A handler exception is not converted into a `HookResult`; isolation is supplied by selected callers such as `ProposalEmitter._fire_hook_chain`.
- Implementation anchors:
  - `src/devolaflow/lifecycle/dispatcher.py:306-375`
  - `src/devolaflow/feedback_emit.py:361-378`
- Contract anchors:
  - `src/devolaflow/lifecycle/dispatcher.py:13-19` describes permissive aggregation and strict escalation.
  - `src/devolaflow/feedback_emit.py:23-25` scopes exception isolation to its emission chain.
- Evidence: The dispatcher contract covers violations returned by handlers, while the emitter catches exceptions around `run_hooks`; direct public callers do not receive the same isolation.
- Impact: A buggy extra handler can abort direct lifecycle callers even though the broader lifecycle design emphasizes permissive operation.
- Adjudication question: Is exception isolation a property of `run_hooks` itself or only of dispatch-emission adapters? Add a direct-handler exception test after deciding.

## Documentation and schema discrepancies

### B4-DOC-001 — host bridge purpose says five hosts, matrix contains six

- Classification: `LIKELY STALE/INCORRECT DOCUMENTATION`
- Severity: Low
- Matrix ID: `B4-DOC-001`
- Anchors:
  - `workflow-system/agent/references/host-bridges.md:29-40` says “five hosts” and lists five names in the purpose paragraph.
  - `workflow-system/agent/references/host-bridges.md:62-71` is headed “Six-host matrix” and contains six rows, including GitHub Copilot.
  - `src/devolaflow/hostbridge/normalize.py:3-5` and `src/devolaflow/hostbridge/normalize.py:40` define six supported hosts.
- Evidence: The implementation and table agree on six; only the prose count is inconsistent.
- Impact: Operators may omit Copilot when assessing delivery coverage.
- Adjudication question: Is GitHub Copilot part of the current guaranteed host set or only a declared extra? Align the count with `workflow-system/agent/hosts.yaml` after that decision.

### B4-DOC-002 — compression stage input statement contradicts reducer behavior

- Classification: `LIKELY STALE/INCORRECT DOCUMENTATION`
- Severity: Low
- Matrix ID: `B4-DOC-002`
- Anchors:
  - `src/devolaflow/compression_pipeline.py:16-21` describes stages chained in order.
  - `src/devolaflow/compression_pipeline.py:209-215` says each transform receives the running payload.
  - `src/devolaflow/compression_pipeline.py:323-327` says stages do not see each other’s inputs.
  - `src/devolaflow/compression_pipeline.py:404-461` assigns each stage’s output to `running_payload`.
- Evidence: Runtime behavior is a sequential reducer; the “do NOT see each other’s inputs” sentence is incompatible with the implementation and surrounding contract.
- Impact: Third-party stage authors can implement the wrong data dependency model.
- Adjudication question: Is the intended model sequential composition or independent stage inspection? The code and examples indicate sequential composition.

### B4-DOC-003 — wave schema retains historical L3 wording

- Classification: `LIKELY STALE/INCORRECT DOCUMENTATION`
- Severity: Low
- Matrix ID: `B4-DOC-003`
- Anchors:
  - `schemas/wave-definition.schema.yaml:4-5` calls the wave a group of L3 Task Agent dispatches.
  - `schemas/wave-definition.schema.yaml:29-35` repeats L3 task terminology.
  - `workflow-system/agent/references/agent-hierarchy.md` defines the current Project → Wave → Task hierarchy.
  - `src/devolaflow/dispatch.py:64-81` applies the dispatcher boundary to L1-to-L2 dispatch.
- Evidence: Current governance uses three layers with Task at L2, while this schema retains pre-current L3 language. `workflow-system/agent/references/wave-dispatch.md:42-47` separately documents current `parallel`, `all`, and deferred quorum behavior.
- Impact: Schema consumers can infer a nonexistent layer and misstate ownership.
- Adjudication question: Is `wave-definition.schema.yaml` still a live contract? If yes, update its layer terminology and current mode statement through the rule-controlled process; if historical, mark it explicitly historical.

## Domains with no discrepancy established

The following surfaces were traced sufficiently to find no static behavior-versus-contract discrepancy in the reviewed paths. This is not a runtime certification; missing runtime evidence remains `INSUFFICIENT`.

- Version source: `src/devolaflow/__init__.py:1-9` exposes `19.0.0`; the repository package metadata and current agent skill were reported as aligned. The separately installed user-wide skill surface is outside this repository and was not independently verified.
- Proposal emission and S-10 hook ordering: `src/devolaflow/feedback_emit.py:201-285` deep-copies dispatches and fires the declared chain; `src/devolaflow/feedback_emit.py:287-378` preserves strict pre-dispatch handling and permissive adapter handling.
- Memory router: `src/devolaflow/memory_router/router.py:106-116` provides a zero-IO flag check; `src/devolaflow/memory_router/router.py:201-290` degrades ordinary lookup failures to a cache miss and exposes strict lookup separately.
- Codegraph researcher: `src/devolaflow/codegraph/_cli.py:123-219` bounds subprocess calls and classifies path, timeout, exit, and JSON failures; `src/devolaflow/codegraph/researcher.py:63-95` exposes a logged degraded sentinel.
- Shell proxy: `src/devolaflow/shell_proxy/proxy.py:121-131` implements the literal `"1"` flag check; `src/devolaflow/shell_proxy/proxy.py:153-183` bounds the distinguish probe and logs failure before passthrough.
- Host bridge normalization and response: `src/devolaflow/hostbridge/normalize.py:147-219` normalizes malformed inputs to unknown; `src/devolaflow/hostbridge/__main__.py:118-136` preserves fail-open host responses.
- Handoff schema validation: `src/devolaflow/agent_workspace/handoff.py:174-237` enforces layer, sequence, timestamp, and discriminated-block rules before the race window identified above.
- Harness gap report: `src/devolaflow/harness/gap.py:550-604` produces explicit axis statuses and preserves current-gap exit semantics; comparison trend-only behavior is documented at `src/devolaflow/harness/gap.py:645-720`.
- Local archive report-only default: `src/devolaflow/cli.py:796-801` builds and prints a plan without applying moves when `--apply` is absent. This matches the report-only description; the discrepancy is in approval selection and post-apply state, not the default planning branch.
- Archive safety checks: `src/devolaflow/local/archive.py:825-838` refuses symlinked or human-maintained indexes, and `src/devolaflow/local/archive.py:928-935` rejects persisted absolute and traversal paths.

## Evidence limitations and required follow-up

- No subprocess, filesystem mutation, network call, or test suite was run. Claims about actual host installation, plugin availability, process cancellation timing, filesystem-device boundaries, and concurrent writer scheduling require targeted runtime tests.
- The user-wide installed skill copy is not a repository-relative source surface. Its version relationship to the repository cannot be adjudicated from this report without an explicit external-surface audit.
- The matrix intentionally does not infer undocumented intent for `skip`, approval semantics, index history, or timeout cancellation. Those items have operator questions because the implementation and prose do not fully settle the intended contract.
- Recommended test additions, without implementation in this review: skipped standard checks; zero parallelism; active event-loop dispatch; post-timeout sync side effects; concurrent same-sequence handoff writes; traversal and absolute proposal targets; failed W-17 git probes; third-party compression stages; exact CLI approval subsets; archive failure after first move; index/mapping history after partial apply; and consolidation failure after archive move.
