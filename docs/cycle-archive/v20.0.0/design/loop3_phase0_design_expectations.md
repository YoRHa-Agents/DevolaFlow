# Loop v3 Phase 0 — Design Expectations Audit

## Scope and reading rule

This is a read-only extraction of behavioral expectations from the current
agent contract, domain references, schemas, and the current `CHANGELOG.md`.
It does not claim that runtime tests were executed. A row is marked **LIVE**
when the current contract or the v19.0.0 changelog presents it as shipped,
**HISTORICAL** when it is retained only for compatibility or provenance, and
**DEFERRED** when the sources explicitly say it must not ship yet.

`Evidence: SUFFICIENT` means the cited sources state an observable behavior and
its result semantics. `Evidence: INSUFFICIENT` means the sources provide only
presence/import metadata, conflicting contracts, or no machine-observable
closure signal. Import, symbol, registry, or file-existence checks alone are
not counted as behavior coverage.

The current release anchor is `CHANGELOG.md:8-55` (`19.0.0`, 2026-08-28).
The v19 entry reports a 9.17/10 evaluator result, 92.0% coverage, zero CJK
violations, and `INSUFFICIENT` historical deltas at `CHANGELOG.md:41-55`.

## 1. Harness and evaluation

### HAR-001 — Built-in evaluator is the live evaluation authority

- **Source anchor:** `workflow-system/agent/references/evaluator-rosetta.md:14-26`;
  `workflow-system/agent/SKILL.md:288-299`.
- **Observable behavior:** Run `python -m devolaflow.harness evaluate` with the
  ledger, repository, base reference, and output path; the evaluator reads
  telemetry, collects bounded local signals, and emits deterministic JSON.
- **Success/error semantics:** `READY` exits 0; `NOT_READY` exits 1 and requires
  iteration or escalation; `INSUFFICIENT` exits 2 and blocks release. Missing
  machine evidence cannot be replaced by prose, estimates, or a manual pass.
- **Proposed matrix row ID:** `HAR-EVAL-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for contract semantics; runtime execution is
  **INSUFFICIENT** in this read-only audit.

### HAR-002 — Evaluation has six weighted dimensions

- **Source anchor:** `workflow-system/agent/references/evaluator-rosetta.md:38-71`.
- **Observable behavior:** Output contains ordered scores and weights for code
  quality (0.20), architecture rationality (0.20), test adequacy (0.20),
  maintainability (0.15), compatibility (0.10), and performance impact (0.15),
  plus composite, `auto_fill_rate`, verdict, summary, and suggestions.
- **Success/error semantics:** All required subcomponents must be available
  for a complete verdict; unavailable required evidence yields `INSUFFICIENT`,
  not a low score.
- **Proposed matrix row ID:** `HAR-EVAL-002`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for the declared output contract; exact current JSON
  shape beyond the cited fields is **INSUFFICIENT** without execution.

### HAR-003 — Rosetta C-cells own dimension evidence

- **Source anchor:** `workflow-system/agent/references/evaluator-rosetta.md:77-139`.
- **Observable behavior:** Dimension explanations use only the canonical
  signal bundles: Ruff, pytest, coverage, layout witnesses, compatibility,
  W-17 growth, docstring coverage, quantifiability, and token budget.
- **Success/error semantics:** Supporting `O` signals cannot replace a
  canonical `C` signal; missing C-cell evidence preserves `available: false`
  and keeps the overall verdict `INSUFFICIENT`.
- **Proposed matrix row ID:** `HAR-EVAL-003`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### HAR-004 — Harness gap inventory reports six coverage axes

- **Source anchor:** `workflow-system/agent/references/harness-construction.md:93-180`.
- **Observable behavior:** `python -m devolaflow.harness gap` emits a
  `schema_version: 1` report with `observation`, `evaluation`, `probe`,
  `baseline`, `signal`, and `loop-closure` axes and three-valued statuses
  `COVERED`, `PARTIAL`, or `GAP`.
- **Success/error semantics:** Exit 0 means every axis is covered; exit 1 means
  at least one partial or gap; exit 2 means insufficient or malformed input.
  An absent ledger is a reported `GAP` with reason `ledger absent`, not a
  parser error; malformed input fails loudly with exit 2.
- **Proposed matrix row ID:** `HAR-GAP-001`.
- **Lifecycle:** LIVE, also recorded in `CHANGELOG.md:265-269`.
- **Evidence:** SUFFICIENT for contract semantics.

### HAR-005 — Custom harness axes require falsifiable probes

- **Source anchor:** `workflow-system/agent/references/harness-construction.md:201-229`;
  `schemas/agent-workspace/harness-preflight.yaml:115-137`.
- **Observable behavior:** A custom axis must have a lowercase-hyphen ID and a
  `file_exists`, bounded `command`, or `ledger_query` probe. The command probe
  timeout is an integer from 1 through 120 seconds.
- **Success/error semantics:** A probe determines `COVERED`; missing probes,
  bad keys, collisions, invalid slugs, and invalid timeouts raise
  `GapConfigError` and map to exit 2. Unverifiable “vibes” axes are rejected.
- **Proposed matrix row ID:** `HAR-GAP-002`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### HAR-006 — Harness preflight is an optional presence flag

- **Source anchor:** `workflow-system/agent/references/harness-construction.md:231-255`;
  `schemas/agent-workspace/harness-preflight.yaml:7-38`.
- **Observable behavior:** The presence of
  `.local/.agent/active/<change-id>/harness_preflight.md` marks a change as
  harness-flagged; its frontmatter references an existing frozen gap report
  and optional axes configuration.
- **Success/error semantics:** Absence produces zero harness-preflight lint
  findings. Malformed frontmatter, wrong schema version, bad section order, or
  dangling references produce the named `HPF_*` finding; token soft breach
  warns and hard breach fails.
- **Proposed matrix row ID:** `HAR-PREFLIGHT-001`.
- **Lifecycle:** LIVE, also recorded in `CHANGELOG.md:271-274`.
- **Evidence:** SUFFICIENT.

### HAR-007 — Capability review compares before and after snapshots

- **Source anchor:** `workflow-system/agent/references/harness-construction.md:257-295`.
- **Observable behavior:** Compare mode requires both `--compare` and
  `--review-output`, loads the frozen report, records axis transitions,
  `auto_fill_rate` delta, resolved gaps, and regressions, and renders a
  deterministic review.
- **Success/error semantics:** Missing either paired CLI option is exit 2;
  malformed frozen JSON is exit 2. Review existence is required for a
  harness-flagged archive, but delta values never alter the gate verdict.
- **Proposed matrix row ID:** `HAR-REVIEW-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### HAR-008 — Cycle harness evidence settles once per cycle

- **Source anchor:** `workflow-system/agent/references/harness-construction.md:297-312`;
  `CHANGELOG.md:28-30`.
- **Observable behavior:** Capability reviews feed the existing W-16
  `harness_baseline_<cycle>.json` settlement and W-7 retrospective; they do
  not create a parallel cadence or modify Tier-A byte witnesses.
- **Success/error semantics:** Settlement is exactly once for a major/minor
  cycle; older active-window baselines are retained in the archive. A v19
  evaluator and settled baseline are reported as present, but matched
  historical deltas remain `INSUFFICIENT`.
- **Proposed matrix row ID:** `HAR-BASELINE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for policy; current artifact-content validation is
  **INSUFFICIENT** here.

### HAR-009 — Current v19 metrics must remain explicit

- **Source anchor:** `CHANGELOG.md:41-55`.
- **Observable behavior:** The current release evidence records `READY`,
  composite 9.17/10, `coverage_pct: 92.0`, suite wall time, CJK violations,
  ghost LOC, AGENTS token count, and `INSUFFICIENT` historical deltas.
- **Success/error semantics:** The 9.17 composite exceeds the major-release
  9.0 threshold; the explicit `INSUFFICIENT` historical result is not treated
  as a pass.
- **Proposed matrix row ID:** `HAR-BASELINE-002`.
- **Lifecycle:** LIVE evidence record.
- **Evidence:** SUFFICIENT for the changelog claim; independent reproduction is
  **INSUFFICIENT** in this audit.

## 2. Gate, convergence, and escalation

### GATE-001 — Round PASS is item-evidence based

- **Source anchor:** `workflow-system/agent/SKILL.md:279-286`;
  `workflow-system/agent/references/decomposition-gate.md:272-313`.
- **Observable behavior:** A round passes only when every selected item has
  valid evidence, its configured check passes, reinforcement is closed or
  user-accepted, blockers are zero, and no ownership/interface conflict
  remains.
- **Success/error semantics:** Composite score is recorded as trend only. A
  high composite cannot replace missing evidence, and a low composite alone
  cannot fail an otherwise valid round.
- **Proposed matrix row ID:** `GATE-ROUND-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### GATE-002 — Archive is stricter than a round pass

- **Source anchor:** `workflow-system/agent/SKILL.md:301-307`;
  `workflow-system/agent/references/agent-workspace.md:337-366`.
- **Observable behavior:** Archive requires all checklist items checked, no
  open reversion, valid evidence references, valid signed preflight,
  mergeability, and a readiness composite of at least 8.5 for lite/minor or
  9.0 for full/major.
- **Success/error semantics:** Failing any archive condition prevents archive
  and source-of-truth mutation.
- **Proposed matrix row ID:** `GATE-ARCHIVE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### GATE-003 — Selection order is deterministic and dependency aware

- **Source anchor:** `workflow-system/agent/references/decomposition-gate.md:88-124`;
  `schemas/agent-workspace/change-stage.yaml:124-161`.
- **Observable behavior:** Select user-reverted items first, then P0, P1, P2,
  satisfied dependencies, and stable checklist order. Blocked dependencies
  are skipped.
- **Success/error semantics:** The round has an explicit capacity and ceiling;
  no selectable item is reported rather than force-scheduled.
- **Proposed matrix row ID:** `GATE-SELECT-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### GATE-004 — Wave partitioning enforces bounded ownership

- **Source anchor:** `workflow-system/agent/references/agent-hierarchy.md:86-103`;
  `workflow-system/agent/references/decomposition-gate.md:138-165`.
- **Observable behavior:** A round has at most 7 waves and a wave at most 5
  tasks; parallel tasks have pairwise-disjoint writable ownership, while
  sequential dependencies move to later waves.
- **Success/error semantics:** Overlapping writable ownership or unresolved
  dependencies rejects the wave; interface dependencies require artifacts or
  typed contracts.
- **Proposed matrix row ID:** `GATE-WAVE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### GATE-005 — Reinforcement is bounded and verbatim

- **Source anchor:** `workflow-system/agent/SKILL.md:309-315`;
  `workflow-system/agent/references/plan-mode-enforcement.md:271-310`.
- **Observable behavior:** After failure, L0 selects at most five
  blocker/critical/major findings and injects them into the next dispatch;
  user-reverted reasons become blocker reinforcement verbatim.
- **Success/error semantics:** L2 addresses or explicitly defers every rule
  and reports closure IDs; unclosed reinforcement is a blocker in aggregation.
- **Proposed matrix row ID:** `GATE-REINFORCE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### GATE-006 — Stagnation and retry ceilings escalate

- **Source anchor:** `workflow-system/agent/references/decomposition-gate.md:231-244`;
  `schemas/agent-workspace/change-stage.yaml:150-161`;
  `workflow-system/agent/references/execution-protocol.md:320-385`.
- **Observable behavior:** Two reinforced rounds without score improvement or
  blocker-count reduction escalate; zero net checklist progress for two rounds,
  three consecutive selections of one incomplete item, or `max_rounds` also
  escalate.
- **Success/error semantics:** Every failure is classified as retry, escalate,
  or abort; retry counters never increase silently. Unknown exceptions
  conservatively become `PAUSE`.
- **Proposed matrix row ID:** `GATE-ESCALATE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### GATE-007 — STANDARD and COMPLEX work requires three layers

- **Source anchor:** `workflow-system/agent/SKILL.md:85-99`;
  `workflow-system/agent/references/decomposition-gate.md:36-42`;
  `schemas/lean-dispatch.yaml:206-246`.
- **Observable behavior:** STANDARD/COMPLEX dispatches set
  `gate.cascade_required: true`, `gate.cascade_min_layers: 3`, and traverse
  L0 Project → L1 Wave → L2 Task. SIMPLE/TRIVIAL work may use the optional
  collapsed path; the documented under-20-line single-file waiver remains.
- **Success/error semantics:** A missing L1 hop is a contract violation.
  Declared minimum depth is validated at face value.
- **Proposed matrix row ID:** `GATE-CASCADE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT in current rules; stale schema comments describing
  L3/default 4 are historical and create a documentation conflict.

### GATE-008 — Preflight signature is non-skippable

- **Source anchor:** `workflow-system/agent/references/execution-protocol.md:24-39`;
  `schemas/agent-workspace/change-preflight.yaml:74-109`.
- **Observable behavior:** The six-step preflight detects, drafts, validates,
  signs, mirrors, and starts only after HBP-01 passes. Signed state requires
  matching configuration and authorization hashes and all stop cards signed.
- **Success/error semantics:** Null authorization, invalid hashes, drift, or
  missing authorization blocks the loop. Configuration/stop-card edits
  invalidate authorization atomically.
- **Proposed matrix row ID:** `GATE-PREFLIGHT-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

## 3. Template, selector, and agent roles

### SEL-001 — Seed selection and runtime loading are separate

- **Source anchor:** `workflow-system/agent/references/meta-framework.md:21-67`;
  `workflow-system/agent/SKILL.md:155-192`.
- **Observable behavior:** Intent loads a registered seed with
  `load_seed(name)`; execution always loads only
  `load_template("change-driven")`. The registry contains 26 intent seeds,
  one executable path, and zero executable composition DAGs.
- **Success/error semantics:** Unknown seeds return `None`; an unavailable
  change-driven runtime returns `None`; discovery does not prove executability.
- **Proposed matrix row ID:** `SEL-TEMPLATE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### SEL-002 — Seed provenance is non-executable

- **Source anchor:** `workflow-system/agent/references/meta-framework.md:119-189`;
  `schemas/checklist-seed.schema.yaml:162-174`.
- **Observable behavior:** Seeds contain placeholders, partitions,
  assertions, suggested priorities, verification templates, and historical
  `source_stages`; materialization produces goal/checklist/preflight
  contracts.
- **Success/error semantics:** Top-level stages/compositions/loops/gates and
  runtime fields are rejected; unresolved placeholders, non-measurable
  assertions, and missing verification templates are invalid. Seed order
  cannot create runtime order.
- **Proposed matrix row ID:** `SEL-SEED-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### TPL-001 — Workflow-template instances have one validated composition shape

- **Source anchor:** `schemas/workflow-template.schema.yaml:8-15`;
  `schemas/workflow-template.schema.yaml:52-80`;
  `schemas/workflow-template.schema.yaml:95-110`.
- **Observable behavior:** A documented workflow-template instance requires
  schema version, metadata, stages, composition, loops, gates, and
  environment modes. Each composition node is exactly one of stage, sequence,
  parallel, choice, loop, or gate.
- **Success/error semantics:** Missing required sections, duplicate stage
  references, invalid composition shapes, or invalid loop/gate references are
  schema failures. This schema documents an instance shape; it does not make
  the historical composition DAG executable.
- **Proposed matrix row ID:** `TPL-SCHEMA-001`.
- **Lifecycle:** LIVE as a documentation/schema contract; executable DAG
  behavior remains HISTORICAL/retired.
- **Evidence:** SUFFICIENT.

### SEL-003 — Historical template aliases preserve migration only

- **Source anchor:** `workflow-system/agent/references/meta-framework.md:219-255`;
  `workflow-system/agent/references/agent-workspace.md:353-361`.
- **Observable behavior:** A historical `load_template(seed_name)` call may
  return a deep copy of the change-driven runtime with seed alias metadata,
  while directing new callers to the explicit two-call form.
- **Success/error semantics:** One alias warning and warning log occur per
  alias per registry instance; old stage behavior is not restored.
- **Proposed matrix row ID:** `SEL-COMPAT-001`.
- **Lifecycle:** HISTORICAL compatibility path.
- **Evidence:** INSUFFICIENT as a current-runtime guarantee because the v17
  changelog also says composition APIs were deleted at `CHANGELOG.md:300-306`;
  the surviving alias boundary needs an executable compatibility assertion.

### SEL-004 — Context profiles allocate by task type

- **Source anchor:** `workflow-system/agent/SKILL.md:329-347`;
  `workflow-system/agent/references/context-isolation.md:216-247`.
- **Observable behavior:** L0, L1, and L2 receive approximately 5K, 5K, and
  8K token contexts respectively, with task-specific loading strategies,
  file limits, timeouts, and priority-based truncation.
- **Success/error semantics:** Hard context caps must not be exceeded; overflow
  truncates lowest-priority sections and adds an explicit marker. Context
  isolation excludes conversation history, sibling file contents, full
  predecessor artifacts, unrelated errors/scores, and deferred items.
- **Proposed matrix row ID:** `SEL-CONTEXT-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for declared policy; actual token-budget
  enforcement is **INSUFFICIENT** without runtime measurements.

### SEL-005 — L2 role profiles are fresh, bounded, and evidence-only

- **Source anchor:** `workflow-system/agent/references/team-roles.md:20-78`;
  `workflow-system/agent/references/agent-hierarchy.md:159-182`.
- **Observable behavior:** `TaskDispatch.task.type` selects one fresh L2 role:
  research, design, implement, test, pathfind, review, preflight, or
  harness-build. Each role stays in its objective/owned files, self-verifies,
  emits typed evidence, and escalates rather than broadening scope.
- **Success/error semantics:** Operational results are `DONE`,
  `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`; L2 never marks a
  checklist item or self-awards a quality score.
- **Proposed matrix row ID:** `SEL-ROLE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### SEL-006 — Pathfinder is read-only look-ahead evidence

- **Source anchor:** `workflow-system/agent/references/pathfinder.md:33-49`;
  `workflow-system/agent/references/pathfinder.md:67-123`;
  `schemas/agent-workspace/pathfinder-report.yaml:61-101`.
- **Observable behavior:** Pathfinder scans the next wave, gate, or dependent
  artifact, classifies findings as `BLOCKER`, `RISK`, `BACKLOG`, or `NO_GAP`,
  and writes only its owned report plus append-only handoff.
- **Success/error semantics:** A BLOCKER must name a horizon and closure signal
  and routes to a separately owned harness-build/design task. A NO_GAP report
  still lists inspected evidence. Pathfinder never repairs, authorizes, or
  changes dispatch shape.
- **Proposed matrix row ID:** `SEL-PATHFINDER-001`.
- **Lifecycle:** LIVE, recorded in `CHANGELOG.md:210-226`.
- **Evidence:** SUFFICIENT.

### SEL-007 — Plan Mode drafts but does not execute

- **Source anchor:** `workflow-system/agent/SKILL.md:101-118`;
  `workflow-system/agent/references/plan-mode-enforcement.md:29-62`.
- **Observable behavior:** Plan Mode produces `goal.md`, `checklist.md`, and
  `preflight.md`, confirms priorities/dependencies/ownership, and waits for
  approval and signed preflight.
- **Success/error semantics:** L0 may inspect and ask questions; L1/L2 may
  return bounded read-only research but must not implement, edit, ask
  questions, or start hidden loops. Missing `ExitPlanMode` must not simulate
  approval.
- **Proposed matrix row ID:** `SEL-PLAN-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

## 4. Compression and message boundaries

### CMP-001 — Dispatch layout preserves the 17-key order

- **Source anchor:** `schemas/lean-dispatch.yaml:913-954`;
  `workflow-system/agent/references/message-schemas.md:235-256`.
- **Observable behavior:** Top-level order is `hdr`, `task`, `goal`,
  `assumptions`, `pred`, `files`, `rules`, `shared`, `accept`, `reinforce`,
  `verify_cfg`, `gate`, `repos`, `behavioral_guidelines`,
  `acceptance_criteria_v2`, `change_context`,
  `predecessor_dedup_ledger`.
- **Success/error semantics:** Positions 1–12 are frozen; positions 13+
  append only. `assert_dispatch_layout` rejects reordering or pre-spec unknown
  keys, and historical Tier-A witnesses remain immutable.
- **Proposed matrix row ID:** `CMP-LAYOUT-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### CMP-002 — Compression preserves required facts and bypasses sensitive text

- **Source anchor:** `schemas/lean-dispatch.yaml:601-655`;
  `workflow-system/agent/references/message-schemas.md:258-274`.
- **Observable behavior:** Paths, verbatim errors, metrics, hashes, IDs,
  acceptance criteria, and artifact references are preserved; filler and
  redundant narration may be dropped. Security warnings, destructive
  operations, order-dependent sequences, and repeated user questions bypass
  compression.
- **Success/error semantics:** Bypass returns the input unchanged. A malformed
  bypass predicate logs a warning and defensively bypasses the stage;
  data-channel imperatives are treated as inert data and surfaced as findings.
- **Proposed matrix row ID:** `CMP-COMPRESS-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### CMP-003 — Data envelopes prevent instruction injection

- **Source anchor:** `workflow-system/agent/references/execution-protocol.md:552-621`;
  `schemas/lean-dispatch.yaml:648-655`.
- **Observable behavior:** Predecessor facts and tool outputs are wrapped in
  `<data channel="...">...</data>`; literal closing tags are escaped and
  injection categories are detected.
- **Success/error semantics:** Imperatives inside data never change tools,
  persona, output channel, or criteria. Detected categories produce an
  `injection_attempt` finding; malformed envelopes raise `ValueError` and
  require immediate escalation.
- **Proposed matrix row ID:** `CMP-SECURITY-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### CMP-004 — Compression pipeline is a deterministic sequential reducer

- **Source anchor:** `workflow-system/agent/references/compression-pipeline.md:40-60`;
  `workflow-system/agent/references/compression-pipeline.md:124-180`;
  `schemas/compression-pipeline.yaml:149-159`.
- **Observable behavior:** Stages run in declaration order; empty or fully
  bypassed pipelines return the input unchanged; an identity transform is not
  counted as applied; stage names are unique.
- **Success/error semantics:** Construction rejects duplicate names and missing
  protocol members. Strict mode propagates the first
  `CompressionStageError` with stage name and cause; lenient mode logs a
  warning, forwards unchanged input, and records `failed_stages`.
- **Proposed matrix row ID:** `CMP-PIPE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for behavior; test execution is **INSUFFICIENT** here.

### CMP-005 — RTK command mapping is default-off and byte-safe

- **Source anchor:** `workflow-system/agent/references/shell-proxy.md:85-109`;
  `workflow-system/agent/references/shell-proxy.md:229-287`;
  `workflow-system/agent/references/shell-proxy.md:463-516`.
- **Observable behavior:** Only literal `"1"` enables
  `DEVOLAFLOW_RTK_PROXY`; Tier 2 additionally requires its own literal `"1"`
  and the primary flag. Enabled proxying requires RTK on PATH and a successful
  `rtk gain` probe. Local recipes precede RTK rewrite, then passthrough.
- **Success/error semantics:** Flag-off paths perform zero IO/subprocess work.
  Missing RTK or failed distinguish probes warn and passthrough. Malformed
  recipe rows warn and are skipped; `wrap_command` remains byte-identical for
  callers that do not apply output recipes.
- **Proposed matrix row ID:** `CMP-RTK-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### CMP-006 — Memory router cache misses are safe

- **Source anchor:** `workflow-system/agent/references/shell-proxy.md:291-375`;
  `workflow-system/agent/references/env-flags.md:152-163`.
- **Observable behavior:** With `DEVOLAFLOW_MEMORY_ROUTER=1`, a fresh matching
  case short-circuits planning; misses, stale versions, expired TTLs, schema
  errors, IO errors, or absent files fall through to the existing planner.
- **Success/error semantics:** Safe `lookup_case()` returns `None` and never
  raises; strict inspection lookup raises `MemoryRouterError`. Disabled mode
  returns `None` with zero IO.
- **Proposed matrix row ID:** `CMP-MEMORY-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### CMP-007 — Structured AC verification produces item evidence

- **Source anchor:** `workflow-system/agent/references/execution-protocol.md:919-956`;
  `schemas/lean-report.yaml:157-166`.
- **Observable behavior:** L2 runs each structured verification command,
  populates one `ac_results` row with verdict and verbatim digest, records
  diff statistics, and reports manual criteria as not run.
- **Success/error semantics:** A failed command remains FAIL after at most two
  self-fix iterations; unavailable commands are `NOT_RUN`; missing evidence
  cannot produce DONE. After the ceiling, report `DONE_WITH_CONCERNS` or
  `BLOCKED`.
- **Proposed matrix row ID:** `CMP-AC-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### MSG-001 — Lean messages preserve typed layer flow and evidence routing

- **Source anchor:** `workflow-system/agent/references/message-schemas.md:20-37`;
  `workflow-system/agent/references/message-schemas.md:67-97`;
  `workflow-system/agent/references/message-schemas.md:120-161`;
  `schemas/lean-report.yaml:157-166`.
- **Observable behavior:** L0 emits TaskDispatch to L1, L1 emits TaskDispatch
  to L2, L2 emits StatusReport evidence to L1, and escalation proceeds
  Task → Wave → Project → Human. Lean fields preserve IDs, paths, errors,
  metrics, hashes, and assertions verbatim.
- **Success/error semantics:** L2 reports evidence rather than a Task Quality
  Score. Reports route as completed, failed, or escalated; recoverable,
  blocking, and fatal failures receive bounded retry, upward resolution, or
  stop/escalation respectively.
- **Proposed matrix row ID:** `MSG-FLOW-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

## 5. Lifecycle and agent workspace

### WS-001 — Workspace scanning is read-only and opt-in scaffolding is strict

- **Source anchor:** `workflow-system/agent/references/agent-workspace.md:22-39`;
  `workflow-system/agent/SKILL.md:67-83`;
  `workflow-system/agent/references/env-flags.md:322-333`.
- **Observable behavior:** Session-start scanning reads feedback, source-of-truth
  specs, active changes, rules, and optional codegraph state without writes.
  STANDARD/COMPLEX work scaffolds only when `DEVOLAFLOW_AGENT_WORKSPACE=1`.
- **Success/error semantics:** Any other flag value is default-off and
  byte-stable. With the flag active, required active-change artifacts precede
  the first L1 dispatch.
- **Proposed matrix row ID:** `WS-ACTIVATE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-002 — Active change ownership is enforced at write time

- **Source anchor:** `workflow-system/agent/references/agent-workspace.md:400-409`;
  `workflow-system/agent/references/agent-workspace.md:411-422`.
- **Observable behavior:** An L2 task may write only its dispatched paths,
  active change folder, and its own append-only handoff outbox.
- **Success/error semantics:** Full/STRICT mode blocks and escalates an
  ownership violation; lite mode warns and logs. Limits are six writable files
  per task, five tasks per wave, and seven waves per round.
- **Proposed matrix row ID:** `WS-OWNERSHIP-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-003 — Handoff envelopes are immutable typed artifacts

- **Source anchor:** `schemas/agent-workspace/handoff-envelope.yaml:8-17`;
  `schemas/agent-workspace/handoff-envelope.yaml:119-241`.
- **Observable behavior:** Each envelope contains exactly one matching
  TaskDispatch, StatusReport, or EscalationEvent variant; filename sequence
  equals the envelope sequence and increments monotonically.
- **Success/error semantics:** Multiple variant blocks, self-handoffs, sequence
  mismatch, mutation, or deletion are schema violations. New information uses
  `seq+1`; schema-v1 records remain read-only compatibility bytes.
- **Proposed matrix row ID:** `WS-HANDOFF-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-004 — Checklist state is evidence-backed and user-controlled

- **Source anchor:** `schemas/agent-workspace/change-checklist.yaml:198-241`;
  `workflow-system/agent/references/agent-workspace.md:169-217`.
- **Observable behavior:** Only L0 or the user can check an item; each checked
  item has matching evidence, actor, round, and timestamp. Only the user may
  reopen an item, preserving the verbatim reason.
- **Success/error semantics:** Missing evidence, failed AC results, invalid
  digest, or open reinforcement blocks checking. Reopening creates blocker
  reinforcement for the next round.
- **Proposed matrix row ID:** `WS-CHECKLIST-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-005 — Checklist progress header is derived and byte-aligned

- **Source anchor:** `schemas/agent-workspace/change-checklist.yaml:76-97`;
  `CHANGELOG.md:285-294`.
- **Observable behavior:** `## Progress` follows the H1, contains a 20-cell
  effort-weighted bar and done/doing/todo/total counts, and is re-rendered on
  each state, effort, item, or round change.
- **Success/error semantics:** The C-9 linter emits `PROGRESS_HEADER` on
  missing, duplicate, misplaced, or drifted bytes. Malformed stage state
  degrades with a warning and `doing=0`.
- **Proposed matrix row ID:** `WS-PROGRESS-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-006 — Preflight and STATUS follow explicit FSMs

- **Source anchor:** `schemas/agent-workspace/change-preflight.yaml:74-109`;
  `schemas/agent-workspace/change-status.yaml:183-233`.
- **Observable behavior:** Preflight is the only execution-before-confirmation
  surface; STATUS follows `PROPOSED → IN_PROGRESS → VERIFYING → ARCHIVED`,
  with `ESCALATED` terminal and verify guards tied to checklist completion.
- **Success/error semantics:** Arbitrary state jumps, invalid hashes, archive
  without gate conditions, or missing escalation envelope are rejected.
  Archived artifacts are copied byte-identically.
- **Proposed matrix row ID:** `WS-FSM-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-007 — Resume planning performs no writes

- **Source anchor:** `workflow-system/agent/references/execution-protocol.md:283-318`;
  `workflow-system/agent/references/agent-workspace.md:102-125`.
- **Observable behavior:** Resume loads the explicit/latest checkpoint, requires
  `convergence_round_complete`, validates hashes/handoffs, cross-checks stage
  and checked IDs, and derives the next priority-ordered selection.
- **Success/error semantics:** Config drift returns `CONFIG_DRIFT`; active
  escalations return `ACTIVE_ESCALATIONS`; checked items are never selected
  again; all checked items return `COMPLETE`.
- **Proposed matrix row ID:** `WS-RESUME-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-008 — Entrance is a static onboarding router

- **Source anchor:** `workflow-system/agent/references/agent-workspace.md:118-146`;
  `schemas/agent-workspace/__init__.yaml:130-145`;
  `CHANGELOG.md:228-242`.
- **Observable behavior:** New change folders contain `entrance.md`, which
  routes session resume, new task, review, and human audit to minimal artifact
  reads without mirroring dynamic progress.
- **Success/error semantics:** Missing pre-v17.2 entrance yields WARN until
  backfilled; parity drift fails. Entrance is not injected into dispatches.
- **Proposed matrix row ID:** `WS-ENTRANCE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### WS-009 — L2 self-verification is distinct from handoff validation

- **Source anchor:** `workflow-system/agent/references/execution-protocol.md:893-917`;
  `workflow-system/agent/references/artifact-quality.md:178-229`.
- **Observable behavior:** L2 first produces command/diff/rule evidence, then
  `pre_handoff` validates the StatusReport evidence envelope.
- **Success/error semantics:** Missing observable evidence yields `NEEDS_CONTEXT`
  or `BLOCKED`, not DONE. The task may self-fix at most twice before honest
  reporting and escalation.
- **Proposed matrix row ID:** `WS-SELFVERIFY-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

## 6. CLI, initialization, and repository mode

### CLI-001 — Repo-init starts with working-tree sanity

- **Source anchor:** `workflow-system/agent/SKILL.md:194-222`;
  `workflow-system/agent/references/troubleshooting.md:388-401`.
- **Observable behavior:** Repo-init runs `git status --short` and
  `git diff --stat HEAD`, records the baseline, preserves pre-existing changes,
  and stops when ownership is uncertain.
- **Success/error semantics:** Pre-existing truncation or drift must be
  restored or escalated before SI-1; the init path must not silently treat a
  damaged tree as a clean baseline.
- **Proposed matrix row ID:** `CLI-INIT-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### CLI-002 — Repo-init creates the canonical eight paths

- **Source anchor:** `workflow-system/agent/SKILL.md:200-218`.
- **Observable behavior:** All depth modes create feedbacks, tasks, memory,
  index, compile config, active, handoff, and archive paths; L0 verifies the
  L2 scaffold owns exactly those paths.
- **Success/error semantics:** Missing or extra ownership fails pre-dispatch
  with `VOF001`. Mode changes depth, not the manifest.
- **Proposed matrix row ID:** `CLI-INIT-002`.
- **Lifecycle:** LIVE.
- **Evidence:** INSUFFICIENT for behavior coverage if checked only by path
  existence; the requested matrix must require a scaffold-and-ownership
  scenario, not an import/path assertion.

### CLI-003 — Codegraph repo-init is suggest-tier and backgrounded

- **Source anchor:** `workflow-system/agent/references/codegraph.md:137-145`;
  `workflow-system/agent/references/codegraph.md:179-209`;
  `workflow-system/agent/SKILL.md:220-222`.
- **Observable behavior:** If the CLI exists, init runs in the background and
  uses `.codegraph/.indexing`, `.ready`, or `.failed` markers. Consumers use a
  ready index, wait no more than 30 seconds while indexing or degrade, and
  degrade immediately on failed/absent.
- **Success/error semantics:** Missing CLI is a non-blocking warning with one
  install hint; indexing failure writes `.failed` and never blocks scaffold.
  Marker precedence is ready over failed over indexing.
- **Proposed matrix row ID:** `CLI-CODEGRAPH-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### CLI-004 — Repository mode controls platform behavior

- **Source anchor:** `workflow-system/agent/references/repo-modes.md:20-37`;
  `workflow-system/agent/references/repo-modes.md:80-150`;
  `workflow-system/agent/references/repo-modes.md:292-312`.
- **Observable behavior:** Mode detection chooses local, github, or other-git
  from repository/remotes and known CI files; explicit config overrides
  detection, which overrides local default. Plugins read the cached profile.
- **Success/error semantics:** Missing mode-specific tools produce a logged
  structured no-op rather than a crash; local mode falls back to local evidence
  and archive-only delivery.
- **Proposed matrix row ID:** `CLI-MODE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for contract; current repo-mode output is
  **INSUFFICIENT** without execution.

### CLI-005 — Wheel-only installs have a documented boundary

- **Source anchor:** `workflow-system/agent/references/troubleshooting.md:370-386`;
  `workflow-system/agent/SKILL.md:48-54`.
- **Observable behavior:** A wheel-only install can use
  `devola-init local --mode=core`; host targets that need
  `workflow-system/agent/` require a clone/editable checkout.
- **Success/error semantics:** Missing source for those targets is an explicit
  installation failure, not a silent fallback. The documented repair is clone
  and editable install.
- **Proposed matrix row ID:** `CLI-INIT-003`.
- **Lifecycle:** LIVE documented limitation.
- **Evidence:** SUFFICIENT for the stated boundary; current wheel behavior is
  **INSUFFICIENT** without the dedicated scenario.

## 7. Local task archive

### ARC-001 — Local archive defaults to report-only

- **Source anchor:** `workflow-system/agent/references/local-archive.md:23-44`;
  `workflow-system/agent/references/local-archive.md:93-108`;
  `schemas/local-archive.schema.yaml:33-53`.
- **Observable behavior:** `devola-local-archive --repo-root .` inventories
  `.local/tasks/` and emits a deterministic plan with source, destination,
  cluster, lifecycle, action, protection, and findings.
- **Success/error semantics:** Default execution does not move, delete,
  rewrite, create an index, or create a mapping ledger. Actions are only
  `move`, `retain`, `review`, or `refuse`; there is no delete action.
- **Proposed matrix row ID:** `ARC-PLAN-001`.
- **Lifecycle:** LIVE, recorded in `CHANGELOG.md:103-134`.
- **Evidence:** SUFFICIENT.

### ARC-002 — Archive source boundary and classification are conservative

- **Source anchor:** `workflow-system/agent/references/local-archive.md:46-69`;
  `schemas/local-archive.schema.yaml:10-32`.
- **Observable behavior:** Only `.local/tasks/` is an input boundary; canonical
  and brownfield task layouts are recognized. Lifecycle is exactly one of
  `active`, `done`, `stale`, or `unknown`; protection is separate.
- **Success/error semantics:** Absolute paths, traversal, unsafe symlinks,
  missing/malformed/conflicting metadata, and protected paths produce explicit
  findings/refusals. Names, mtime, or size cannot infer status.
- **Proposed matrix row ID:** `ARC-INVENTORY-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### ARC-003 — Physical moves require exact prior approval

- **Source anchor:** `workflow-system/agent/references/local-archive.md:110-127`.
- **Observable behavior:** `--apply approved-plan.json` applies only entries
  whose current source, destination, classification, findings, and action
  exactly match the approved plan.
- **Success/error semantics:** Changed, missing, duplicated, or unapproved
  entries are refused; refusal leaves the candidate in place. Approval of one
  entry does not approve others.
- **Proposed matrix row ID:** `ARC-APPLY-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### ARC-004 — Safety checks reject dirty or unsafe moves

- **Source anchor:** `workflow-system/agent/references/local-archive.md:129-150`.
- **Observable behavior:** Apply verifies repository/task boundaries, no
  symlinks, readable source, absent destination, no protected/nested/worktree
  conflict, clean git status, inspected diffs/ignored paths, and worktree
  registry.
- **Success/error semantics:** Dirty, ambiguous, unreadable, nested,
  symlinked, protected, or conflicted paths are explicitly refused. The
  runtime never invokes `git clean -fdx` or an equivalent destructive command.
- **Proposed matrix row ID:** `ARC-SAFETY-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### ARC-005 — Mapping is append-only and index is generated honestly

- **Source anchor:** `workflow-system/agent/references/local-archive.md:160-184`;
  `schemas/local-archive.schema.yaml:54-80`.
- **Observable behavior:** Every physical move appends one mapping document with
  sequence, source, destination, reason, and timestamp. The index carries the
  exact generated marker and is a navigation view, not the source of truth.
- **Success/error semantics:** Sequence increases from the existing maximum;
  duplicate source/destination, human-maintained index, symlinked index, or
  unreadable index is refused or reported as drift, never overwritten.
- **Proposed matrix row ID:** `ARC-LEDGER-001`.
- **Lifecycle:** LIVE, with explicit rule text in `AGENTS.md` W-27/W-28 and
  changelog evidence at `CHANGELOG.md:117-120`.
- **Evidence:** SUFFICIENT.

### ARC-006 — Deletion remains permanently operator-only

- **Source anchor:** `workflow-system/agent/references/local-archive.md:152-158`;
  `CHANGELOG.md:136-140`.
- **Observable behavior:** The runtime can report disposable candidates but
  exposes no deletion API or deletion workflow.
- **Success/error semantics:** Clean checks and plan approval never authorize
  deletion. Any later deletion is outside this runtime and owned by the
  operator.
- **Proposed matrix row ID:** `ARC-DELETION-001`.
- **Lifecycle:** LIVE safety boundary; the related workflow-rule approval was
  historically deferred/unapproved.
- **Evidence:** SUFFICIENT for runtime boundary; approval state is explicitly
  separate and historical/deferred.

## 8. Plugins and degraded mode

### PLG-001 — Plugin auto-install is probe-and-suggest by default

- **Source anchor:** `workflow-system/agent/references/shell-proxy.md:85-109`;
  `workflow-system/agent/references/degraded-mode.md:92-121`.
- **Observable behavior:** Registry defaults set `auto_install: false`;
  bare plugin checks probe and report, while explicit install surfaces pass
  `auto_install=True`.
- **Success/error semantics:** Suggest-tier install failures warn once and
  continue on the degraded path; strict callers may re-raise. No implicit
  network mutation occurs from a bare ensure call.
- **Proposed matrix row ID:** `PLG-INSTALL-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### PLG-002 — Degraded plugins preserve dispatch continuity

- **Source anchor:** `workflow-system/agent/references/degraded-mode.md:5-49`;
  `workflow-system/agent/references/degraded-mode.md:82-121`.
- **Observable behavior:** Plugin absence loses only that plugin's signal;
  L0→L1→L2 dispatch, permissive hooks, active workspace artifacts, and
  dispatch layout continue.
- **Success/error semantics:** Missing signal is logged or represented as a
  structured skip; it must not become a fabricated PASS. Required machine
  evidence remains `INSUFFICIENT` where it is unavailable.
- **Proposed matrix row ID:** `PLG-DEGRADE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### PLG-003 — Codegraph degraded helpers return typed empty sentinels

- **Source anchor:** `workflow-system/agent/references/codegraph.md:150-177`;
  `workflow-system/agent/references/degraded-mode.md:301-386`.
- **Observable behavior:** Missing/failed codegraph returns `""`, `[]`, or
  `{}` from the five researcher helpers, logs WARNING once per process, and
  directs callers to Read/Glob/Grep.
- **Success/error semantics:** Structured causes are `path_missing`, `timeout`,
  `nonzero_exit`, or `json_parse_error`; repo-init skips or marks failure
  without blocking, and gate scoring redistributes the missing impact weight.
- **Proposed matrix row ID:** `PLG-CODEGRAPH-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### PLG-004 — Impeccable detect is deterministic and non-gating when unavailable

- **Source anchor:** `workflow-system/agent/references/impeccable.md:33-61`;
  `workflow-system/agent/references/impeccable.md:94-116`;
  `workflow-system/agent/references/degraded-mode.md:388-437`.
- **Observable behavior:** `impeccable detect` scans supported UI files without
  an LLM or API key; exit 0 means no issue and exit 2 means anti-patterns,
  which loops a web-design verification item to refine.
- **Success/error semantics:** Unavailable install/detector emits a warning
  and continues permissively, but the lost detector signal remains
  unverified/non-gating and never becomes PASS.
- **Proposed matrix row ID:** `PLG-IMPECCABLE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### PLG-005 — RTK collision detection must use `rtk gain`

- **Source anchor:** `workflow-system/agent/references/shell-proxy.md:112-172`;
  `workflow-system/agent/references/degraded-mode.md:188-239`.
- **Observable behavior:** RTK installation/probe checks `rtk --version` and
  mandatory `rtk gain`; failed distinguish indicates the unrelated package or
  a broken install.
- **Success/error semantics:** Primary curl install failure may fall back to
  the canonical GitHub cargo install, never bare `cargo install rtk`; both
  failure paths raise `PluginInstallError` for installation, while runtime
  proxy use warns and passthroughs.
- **Proposed matrix row ID:** `PLG-RTK-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

## 9. Lifecycle hooks and host bridge

### HOST-001 — Every dispatch traverses both dispatch hooks

- **Source anchor:** `workflow-system/agent/SKILL.md:365-376`;
  `workflow-system/agent/references/plan-mode-enforcement.md:304-310`;
  `workflow-system/agent/references/plan-mode-enforcement.md:370-382`.
- **Observable behavior:** Every generated round dispatch passes
  `pre_dispatch` then `post_dispatch`, including round-one pass-through,
  no-reinforcement, and reinforcement paths.
- **Success/error semantics:** Default handlers do not mutate bytes. A custom
  hook failure is logged as a warning by the permissive emission path while
  the dispatch remains available.
- **Proposed matrix row ID:** `HOST-HOOK-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### HOST-002 — Host enforcement is strict opt-in and fail-open

- **Source anchor:** `workflow-system/agent/references/host-bridges.md:49-87`;
  `workflow-system/agent/references/env-flags.md:359-372`.
- **Observable behavior:** Literal `DEVOLAFLOW_HOST_ENFORCE=1` enables host
  event enforcement; all other values allow with zero filesystem IO. Active
  bridge errors yield `error_allow` audit evidence.
- **Success/error semantics:** Unknown/unparseable input, missing Python,
  timeout, and internal exceptions never block the host tool. Flag-off
  decisions are not ledgered.
- **Proposed matrix row ID:** `HOST-ENFORCE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### HOST-003 — File writes enforce the union of active owned manifests

- **Source anchor:** `workflow-system/agent/references/host-bridges.md:89-106`.
- **Observable behavior:** Active `file_write` events check the union of all
  active `owned_files.txt` manifests plus change-folder and handoff
  exemptions. Codex patches are split into per-file targets.
- **Success/error semantics:** `CFO006` denies an unowned target with path and
  change IDs; shell events are always allowed and only carry advisory
  pre-shell metadata.
- **Proposed matrix row ID:** `HOST-OWNERSHIP-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### HOST-004 — Host bridge audit ledger is append-only evidence

- **Source anchor:** `workflow-system/agent/references/host-bridges.md:133-153`.
- **Observable behavior:** Enforced decisions append JSONL with timestamp,
  host, kind, path/command, verdict, reason, latency, active changes, and
  swallowed error/advisory fields where applicable.
- **Success/error semantics:** Ledger write failure is logged and does not
  change the host verdict.
- **Proposed matrix row ID:** `HOST-LEDGER-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for schema; write-failure behavior is
  **INSUFFICIENT** without an execution scenario.

### HOST-005 — Host event normalization has deterministic precedence

- **Source anchor:** `workflow-system/agent/references/host-bridges.md:155-176`.
- **Observable behavior:** Event kind precedence is CLI override, DSH kind,
  tool name, hook hint, shape inference, then unknown; path precedence is
  `path`, `file_path`, `target_file`.
- **Success/error semantics:** Unknown shapes allow and are ledgered when
  enforcement is active. Codex patch markers are checked per target; a patch
  with no target is shell-kind advisory allow.
- **Proposed matrix row ID:** `HOST-NORMALIZE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT.

### HOST-006 — Session resume is wired only for Cursor and Claude

- **Source anchor:** `workflow-system/agent/references/host-bridges.md:178-203`;
  `CHANGELOG.md:324-328`.
- **Observable behavior:** With `DEVOLAFLOW_AGENT_WORKSPACE=1`,
  `hostbridge resume` emits a compact summary for Cursor and Claude session
  hooks; zero active changes is silent and multiple changes emit only IDs.
- **Success/error semantics:** Flag off or any non-literal value returns empty
  stdout, exit 0, and zero IO. Exceptions also return empty stdout and append
  an `error_allow` record. Codex, Kimi, DSH, and Copilot have no session
  injection this round.
- **Proposed matrix row ID:** `HOST-RESUME-001`.
- **Lifecycle:** LIVE for Cursor/Claude; deliberately deferred/degraded for
  the other listed hosts.
- **Evidence:** SUFFICIENT.

### HOST-007 — Host support is tiered and evidence-backed

- **Source anchor:** `workflow-system/agent/references/host-contract.md:21-65`;
  `schemas/host-contract.yaml:23-65`;
  `CHANGELOG.md:181-208`.
- **Observable behavior:** Guaranteed hosts satisfy five floor axes; every
  optional capability has an explicit closed status and evidence. `kimi`
  resolves to canonical `kimicode`.
- **Success/error semantics:** Implemented bridges require captured or
  vendor-doc fixtures; vendor-doc requires a URL. Synthetic/TBD-audit cannot
  substantiate implementation. Unsupported capabilities stay undeclared,
  designed, or broken.
- **Proposed matrix row ID:** `HOST-CONTRACT-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for schema/policy; host-by-host runtime parity is
  **INSUFFICIENT** without running adapters.

## 10. Skill delivery, install, and npm

### DEL-001 — Skill update channel matches installation channel

- **Source anchor:** `workflow-system/agent/SKILL.md:31-54`.
- **Observable behavior:** npm installs update with the npm package, curl
  installs update through the installer, and Python updates the package only.
  Copied skills are not refreshed by Python package updates.
- **Success/error semantics:** `devola-init-doctor` checks workspace health,
  `--skills` checks copied skills, and npm `doctor` checks npm-channel parity.
  Local/standalone surfaces require explicit target handling.
- **Proposed matrix row ID:** `DEL-UPDATE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for documented command routing.

### DEL-002 — Guaranteed host delivery must remain parity checked

- **Source anchor:** `workflow-system/agent/references/host-contract.md:39-47`;
  `workflow-system/agent/references/host-contract.md:79-119`;
  `CHANGELOG.md:142-162`.
- **Observable behavior:** Every guaranteed host has skill delivery,
  instruction format, install channel, doctor status, and test paths; derived
  manifest profiles match the HSC projection.
- **Success/error semantics:** Adding a host/capability requires schema,
  loader/parity, ghost, and evidence-backed tests before changelog claims.
  Missing optional evidence leaves the capability explicitly unsupported.
- **Proposed matrix row ID:** `DEL-HOST-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for governance; actual parity is
  **INSUFFICIENT** without running the declared tests.

### DEL-003 — npm installer is thin, raw-download based, and zero-dependency

- **Source anchor:** `CHANGELOG.md:336-340`;
  `workflow-system/agent/SKILL.md:35-53`.
- **Observable behavior:** `npx @yorha-agents/devola-flow install cursor|claude|all`
  downloads the manifest-derived skill file set from the package-version raw
  tag, uses Node 18 built-ins, and supports `update`, `doctor`, and
  `DEVOLA_FLOW_REF`.
- **Success/error semantics:** The package file list must remain byte-equal to
  the Python manifest projection; tag/version mismatch fails publication.
- **Proposed matrix row ID:** `DEL-NPM-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for documented contract; npm execution is
  **INSUFFICIENT** in this audit.

### DEL-004 — Npm publication is gated by tag/version and reusable CI

- **Source anchor:** `CHANGELOG.md:338-345`.
- **Observable behavior:** Publish CI triggers on `v*` tags, fails fast on tag
  versus npm version mismatch, publishes with provenance, and waits for npm
  package checks.
- **Success/error semantics:** Unreachable or invalid release provenance must
  prevent publication; both release workflows reject tag SHAs not reachable
  from `origin/main` and refuse existing tags.
- **Proposed matrix row ID:** `DEL-NPM-002`.
- **Lifecycle:** LIVE.
- **Evidence:** INSUFFICIENT for actual CI behavior because the source is
  changelog prose and no check run was inspected.

### DEL-005 — Agent-facing language gate is English with narrow exemptions

- **Source anchor:** `CHANGELOG.md:23-27`;
  `CHANGELOG.md:80-84`.
- **Observable behavior:** The current gate inventories intended agent-facing
  surfaces and reports zero CJK violations; v18 states agent-facing CJK fails
  the language gate.
- **Success/error semantics:** A release with disallowed agent-facing CJK is
  not acceptable; v19 records zero current violations.
- **Proposed matrix row ID:** `DEL-LANGUAGE-001`.
- **Lifecycle:** LIVE.
- **Evidence:** SUFFICIENT for the current claim; independent gate execution
  is **INSUFFICIENT**.

## 11. Historical and deferred expectations that must not be promoted

### HIST-001 — Fixed stage DAGs and stage order are retired

- **Source anchor:** `workflow-system/agent/references/meta-framework.md:21-39`;
  `workflow-system/agent/references/meta-framework.md:152-173`;
  `CHANGELOG.md:74-79`.
- **Observable behavior:** Runtime uses checklist rounds, not seed
  `source_stages`, fixed stage DAGs, or historical primitive order.
- **Success/error semantics:** Reconstructing a DAG from seed partitions is a
  contract error. Historical labels remain provenance only.
- **Proposed matrix row ID:** `HIST-RUNTIME-001`.
- **Lifecycle:** HISTORICAL/retired.
- **Evidence:** SUFFICIENT.

### HIST-002 — Legacy tasks/acceptance layout is read-compatibility only

- **Source anchor:** `workflow-system/agent/references/agent-workspace.md:76-82`;
  `schemas/agent-workspace/change-status.yaml:206-219`;
  `CHANGELOG.md:300-306`.
- **Observable behavior:** `checklist.md` is the only current task/acceptance
  surface; legacy folders raise `LegacyChangeLayoutError` or are normalized
  in memory as compatibility data.
- **Success/error semantics:** Legacy bytes are never rewritten in place and
  mixed legacy/current layout is invalid.
- **Proposed matrix row ID:** `HIST-LAYOUT-001`.
- **Lifecycle:** HISTORICAL compatibility.
- **Evidence:** SUFFICIENT.

### HIST-003 — NineS and EvoBench are not live runtime dependencies

- **Source anchor:** `workflow-system/agent/SKILL.md:187-192`;
  `workflow-system/agent/references/shell-proxy.md:36-43`;
  `workflow-system/agent/references/troubleshooting.md:356-368`;
  `CHANGELOG.md:300-304`.
- **Observable behavior:** Current evaluation uses the built-in harness;
  historical NineS/EvoBench artifacts remain archived provenance only.
- **Success/error semantics:** Do not add external evaluator fallback or
  regenerate retired benchmark JSON; missing built-in evidence remains
  `INSUFFICIENT`.
- **Proposed matrix row ID:** `HIST-EVAL-001`.
- **Lifecycle:** HISTORICAL/retired.
- **Evidence:** SUFFICIENT.

### DEFER-001 — Harness v2 cross-cutting suggest channel is not shipped

- **Source anchor:** `workflow-system/agent/references/harness-construction.md:70-91`;
  `CHANGELOG.md:260-263`.
- **Observable behavior:** Current harness activation is explicit seed or
  operator phrasing; there is no automatic `auto_fill_rate` task reorder and
  no `classify_harness_intent` channel.
- **Success/error semantics:** A proposal for either deferred mechanism needs
  a new SI-1 gap analysis and must not be inferred from the current v1
  artifact.
- **Proposed matrix row ID:** `DEFER-HARNESS-001`.
- **Lifecycle:** DEFERRED.
- **Evidence:** SUFFICIENT.

### DEFER-002 — Pattern 3 persistent-state pool remains deferred

- **Source anchor:** `workflow-system/agent/references/agent-hierarchy.md:205-209`;
  `workflow-system/agent/references/meta-framework.md:106-117`;
  `CHANGELOG.md:51-55`, `CHANGELOG.md:92-95`.
- **Observable behavior:** Current selection supports INLINE/FAN_OUT semantics;
  persistent Teams/shared state and the Pattern 3 pool are not executable.
- **Success/error semantics:** Do not treat `AGENT_POOL_FORWARD` compatibility
  text as authorization. New implementation requires SI-1, persistent-state
  schema, and a separate proposal.
- **Proposed matrix row ID:** `DEFER-POOL-001`.
- **Lifecycle:** DEFERRED.
- **Evidence:** SUFFICIENT.

### DEFER-003 — DSH web/progress UI and Tier-C host retention are deferred

- **Source anchor:** `CHANGELOG.md:49-55`, `CHANGELOG.md:92-95`;
  `workflow-system/agent/references/host-bridges.md:196-203`.
- **Observable behavior:** DSH bridge enforcement may be implemented through
  the plugin channel, but session context and web/progress UI are not current
  guarantees; Tier-C retention remains deferred.
- **Success/error semantics:** Absence must degrade explicitly, not be
  reported as full host support or session injection.
- **Proposed matrix row ID:** `DEFER-HOST-001`.
- **Lifecycle:** DEFERRED.
- **Evidence:** SUFFICIENT.

### DEFER-004 — Forward-declared cycle and legibility flags remain inactive

- **Source anchor:** `workflow-system/agent/references/env-flags.md:399-421`.
- **Observable behavior:** `DEVOLAFLOW_CYCLE_DETECTOR` and
  `DEVOLAFLOW_LEGIBILITY_CHECK` have no active runtime contract in the
  current flag inventory.
- **Success/error semantics:** They cannot be treated as enabled or used as
  release evidence until dedicated fixtures and settled telemetry exist.
- **Proposed matrix row ID:** `DEFER-FLAG-001`.
- **Lifecycle:** DEFERRED.
- **Evidence:** SUFFICIENT.

### DEFER-005 — `DEVOLAFLOW_AUTO_INSTALL` is a retired tombstone

- **Source anchor:** `workflow-system/agent/references/env-flags.md:165-172`;
  `workflow-system/agent/references/shell-proxy.md:97-108`.
- **Observable behavior:** Setting the old flag has no production effect;
  current installation control is registry `defaults.auto_install` plus the
  explicit `ensure_plugin(auto_install=...)` parameter.
- **Success/error semantics:** No read site may be added under the retired
  name. Use the current explicit plugin surfaces.
- **Proposed matrix row ID:** `HIST-FLAG-001`.
- **Lifecycle:** HISTORICAL/retired.
- **Evidence:** SUFFICIENT.

## 12. Cross-source contradictions and insufficient closure

### AUDIT-001 — Coverage floor is contradictory

- **Source anchor:** `AGENTS.md` S-3; `workflow-system/agent/references/artifact-quality.md:89-98`;
  `CHANGELOG.md:19-22`; `CHANGELOG.md:63-70`.
- **Observed conflict:** Governance and artifact-quality references require
  at least 80% coverage for new/modified Python modules, while v18 reports a
  70% per-module floor and v19 reports a 75% per-module floor.
- **Expected semantics:** A stable matrix needs one authoritative floor and
  separate global/per-module scope. Until adjudicated, coverage-floor
  assertions are **INSUFFICIENT**, not silently normalized to 75% or 80%.
- **Proposed matrix row ID:** `AUDIT-CONFLICT-001`.
- **Lifecycle:** Current documentation conflict.
- **Evidence:** INSUFFICIENT.

### AUDIT-002 — Legacy schema files retain stale layer and threshold prose

- **Source anchor:** `schemas/lean-dispatch.yaml:206-246`;
  `schemas/status-report.schema.yaml:14-76`;
  `schemas/task-dispatch.schema.yaml:14-150`;
  current contract `workflow-system/agent/references/message-schemas.md:20-37`.
- **Observed conflict:** Legacy schemas describe stage/L3 receivers and
  quality-score fields, while current references require L0/L1/L2, evidence
  only at L2, and no Task Quality Score.
- **Expected semantics:** Current writers and behavior must follow lean schemas,
  current references, and v19 changelog; legacy schema prose is read-only
  provenance unless an explicit compatibility reader is named.
- **Proposed matrix row ID:** `AUDIT-CONFLICT-002`.
- **Lifecycle:** Historical compatibility documentation.
- **Evidence:** INSUFFICIENT until schema parity tests demonstrate which
  legacy files are documentation-only versus active validators.

### AUDIT-003 — Compression reference retains a stale 16-key claim

- **Source anchor:** `workflow-system/agent/references/compression-pipeline.md:49-57`;
  `workflow-system/agent/references/message-schemas.md:235-247`;
  `schemas/lean-dispatch.yaml:913-954`.
- **Observed conflict:** The compression reference says the canonical order has
  16 keys and schema version 5, while the current lean message contract and
  layout schema define 17 keys with append-only positions 13–17.
- **Expected semantics:** Matrix tests must use the current 17-key layout and
  immutable witnesses; the stale 16-key prose must not be used to approve a
  dispatch mutation.
- **Proposed matrix row ID:** `AUDIT-CONFLICT-003`.
- **Lifecycle:** Historical/stale documentation conflict.
- **Evidence:** INSUFFICIENT until all current layout witnesses and validators
  are shown to agree on one live specification.

### AUDIT-004 — Current report is not a substitute for runtime coverage

- **Source anchor:** `workflow-system/agent/references/harness-construction.md:177-180`;
  `workflow-system/agent/references/evaluator-rosetta.md:154-191`;
  `CHANGELOG.md:8-15`.
- **Observed gap:** The repository documents evaluator, gap, archive, host,
  npm, and degraded-mode behaviors, but this audit did not execute commands,
  inspect CI runs, or validate all declared test paths.
- **Expected semantics:** Loop v3 Phase 0 must create matrix rows that exercise
  success, error, fallback, and no-op paths. Import/existence checks alone
  cannot close rows; unavailable machine evidence remains `INSUFFICIENT`.
- **Proposed matrix row ID:** `AUDIT-EVIDENCE-001`.
- **Lifecycle:** LIVE audit requirement.
- **Evidence:** INSUFFICIENT by design; this is the explicit handoff for the
  next verification phase.

## Summary

The current live contract is a checklist-round runtime with a three-layer
L0→L1→L2 cascade, evidence-based gates, bounded retries, strict ownership,
append-only artifacts, built-in harness evaluation, default-safe optional
plugins, explicit host enforcement, and operator-only local-task deletion.
The principal audit blockers are the unresolved 70%/75%/80% coverage-floor
documentation conflict, stale legacy schema prose that still names L3 and
quality scores, and the need to run behavioral success/error/fallback
scenarios rather than counting imports or file presence. Deferred surfaces
must remain explicitly deferred: harness v2 suggest activation, Pattern 3
persistent-state pooling, DSH web/session additions, Tier-C retention, and
the forward-declared cycle/legibility flags.
