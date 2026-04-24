---
id: plan-mode-enforcement
version: "8.4.1"
purpose: >
  Plan-mode L0 operating contract: when a dispatcher detects plan mode, this
  reference defines the canonical plan output template, plan-mode rules,
  reinforcement-loop mechanics, and stagnation-escalation behavior. Pairs
  with the W-8 / SI-9 convergence-round reinforcement primitive in
  src/devolaflow/gate/reinforcement.py and the round-aware dispatch
  escalation in src/devolaflow/task_adaptive_selector.py.
tier: 2
token_estimate: 3200
last_updated: "2026-04-23"
---

# Plan-Mode Enforcement & Reinforcement Loop Contract

> **Tier-2 reference** — load when the dispatcher enters Plan Mode (Cursor
> SwitchMode `plan`, system_reminder "Plan mode is active", explicit user
> "build a plan" / "design first" / "/plan", or env
> `DEVOLAFLOW_PLAN_MODE=1` / filesystem marker `.devolaflow_plan_mode`),
> AND when L1/L2 build a round-N+1 dispatch carrying
> `applicable_rules.reinforcement` payload after a gate FAIL. SKILL.md
> §"Mode Awareness" + §"Reinforcement Rules" carry the 1-paragraph
> summaries; this file carries the full operating contract.

## 1. When to Load

This reference is loaded by L0/L1 dispatchers under any of the following
trigger conditions:

| Trigger                                                          | Source                                                                  | Effect                                                                |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `<system_reminder>` contains "Plan mode is active"               | host runtime (Cursor / Claude Code system message channel)              | force-loads §3 plan template + §4 constraints + §5 rules              |
| `SwitchMode` tool available + current mode is `plan`             | Cursor mode-switch event                                                | same as above                                                         |
| User says "build a plan" / "plan this" / "design first" / "/plan" | NL trigger phrase from prompt                                           | escalates `plan_mode_template` section to `critical` priority         |
| `DEVOLAFLOW_PLAN_MODE` in `{"1","true","yes","on"}`              | env var (per `task_adaptive_selector._detect_plan_mode`)                | applies `_PLAN_MODE_OVERRIDES` block (see §2)                         |
| `.devolaflow_plan_mode` file in cwd                              | filesystem marker (per `task_adaptive_selector._PLAN_MODE_MARKER`)      | same as env var                                                       |
| L1 / L2 building round-N+1 dispatch after gate FAIL              | `ProposalGenerator.generate_round_dispatch()` in `src/devolaflow/feedback.py` | force-loads §6 reinforcement mechanics + §7 convergence loop |

The reference is also discoverable via SKILL.md §"Reference Navigation
Guide" Tier-2 sub-table. L1/L2 agents that detect a mode-handoff arrival
(plan→agent, plan→hotfix) should load this reference to confirm rules
inheritance.

## 2. Plan Mode Detection (priority order)

When multiple signals are present, evaluate in this priority order:

1. `<system_reminder>` contains "Plan mode is active" → **PLAN MODE**
2. `SwitchMode` tool available and current mode is `plan` → **PLAN MODE**
3. User explicitly says "build a plan" / "plan this" / "design first" /
   "/plan" → **PLAN MODE**
4. Otherwise → **AGENT MODE** (default; full orchestration). **v6.1.5+
   runtime hook:** `select_context(plan_mode=True)` (or env
   `DEVOLAFLOW_PLAN_MODE=1`) escalates plan-relevant sections
   (`agent_hierarchy`, `decomposition_gate`, `rationalization_prevention`)
   to `critical` priority and upgrades `model_hint` to `quality`.

### 2.1 `_PLAN_MODE_OVERRIDES` block

Defined in `src/devolaflow/task_adaptive_selector.py` (lines 67-77):

```python
_PLAN_MODE_OVERRIDES: dict[str, Any] = {
    "section_priority_overrides": {
        "agent_hierarchy": "critical",
        "decomposition_gate": "critical",
        "rationalization_prevention": "critical",
        "convergence_loop": "important",
        "execution_protocol": "supplementary",
    },
    "compression_intensity": "minimal",
    "model_hint_override": "quality",
}
```

Effects on the dispatch payload:

- **section_priority_overrides** — the listed sections are bumped to the
  declared priority before budget allocation runs; this guarantees
  agent-hierarchy + decomposition-gate + rationalization-prevention always
  fit even when the budget is tight.
- **compression_intensity: minimal** — disables verbatim → bullet
  contraction in `compressor.py` so plan output retains structural
  fidelity.
- **model_hint_override: quality** — forces the L0 model selector to pick
  the highest-quality tier regardless of profile defaults (plans must not
  cut model corners on the most consequential dispatch — the one humans
  read).

### 2.2 R5 backward-compat for AGENT MODE

When neither plan-mode signal is present, AGENT MODE is active and ALL
sections render under their profile defaults (no overrides applied). The
`_PLAN_MODE_OVERRIDES` payload only injects when `apply_plan_mode_overrides()`
is called explicitly, so the AGENT MODE byte-output is identical to v6.0.x
pre-plan-mode behavior — verified by
`tests/test_task_adaptive_selector_plan_mode.py`.

## 3. Plan Output Template (verbatim contract)

When PLAN MODE is active, the L0 agent writes its plan into the canonical
output target (Cursor: `create_plan` tool; Claude Code: `plan.md`; raw:
markdown stdout) using the following template VERBATIM. The template is the
delegation contract that downstream L1/L2/L3 agents inherit; section
ordering, header levels, and field names must match exactly.

```text
# [Plan Title]

## Overview
[1-2 sentences] | Workflow: [type] | Gate: [standard/strict/relaxed]
Escalation: Task → Wave → Stage → Project → Human

## Execution Model
| Plan Element | Layer | Role |
|---|---|---|
| Stage dispatch | L0 Project | Selects workflow, sequences stages |
| Stage execution | L1 Stage | Decomposes into waves, runs gate |
| Wave dispatch | L2 Wave | Dispatches parallel tasks, checks conflicts |
| Task execution | L3 Task | **Only layer that does work** |

## Stages (gate-before-advance: no stage starts until predecessor gate PASS)

### S01: [primitive] — [name] [L0 dispatches → L1 executes]
- gate_type: [standard|convergence|passthrough] | threshold: [N] | coverage: [N]%
- max_rounds: [N] (convergence only) | on_stagnation: escalate
- context_profile: [type] | deliverables: [artifact paths → consumed by S02]
- L1_receives: stage definition, predecessor gate results, token budget ~5K

#### W01 (parallel | <=5 tasks | disjoint ownership) [L2 dispatches tasks]
| ID | Layer | Type | Task | Team | Writable (<=6) | Read-only | Est. | AC |
|----|-------|------|------|------|----------------|-----------|------|-----|
| T01 | L3 | impl | ... | Implement | ... | ... | ... | ... |

## Constraints Checklist
- [ ] Every task row is L3 (no L0-L2 performing work — P1 enforced)
- [ ] Stage headers specify L1 agent constraints (MUST NOT write code)
- [ ] Execution model section present with per-layer delegation rules
- [ ] Each wave: <=5 tasks, pairwise disjoint writable files
- [ ] Each stage: <=7 waves
- [ ] Task limits: impl <=30min, research <=45min, <=6 writable files
- [ ] Stage DAG: no cycles, gate-before-advance (D4)
- [ ] Convergence stages: max_rounds + stagnation rule specified
- [ ] Predecessors referenced by artifact path, not content copy

## Invariants (ALL enforced)
- P1: L0-L2 dispatch only; only L3 Tasks execute work
- P2: Token budgets — L0: ~3K, L1: ~5K, L2: ~4K, L3: ~8K
- P3: Inter-layer messages use typed YAML (TaskDispatch/StatusReport)
- P4: Every loop has max_iterations; failures: retry/escalate/abort
- P5: Layers communicate through artifact files, not conversation history
```

### 3.1 Field semantics (per-row contract)

- **Workflow type** — must match a registry entry (`workflow-system/agent/templates/registry.yaml`). Free-form names break `TemplateRegistry.load_template()` exact-match.
- **Gate** — `relaxed` (≥70 / ≥60% cov) | `standard` (≥85 / ≥80%) | `strict` (≥90 / ≥90%) | `audit` (≥95 / ≥90%) per `gate/profiles.py`.
- **Escalation** — always upward, never skip levels (per S-9 escalation invariant).
- **Layer** — L0 / L1 / L2 / L3 only; per the 4-layer hierarchy in SKILL.md §"4-Layer Agent Hierarchy". Mixed-layer task rows fail the constraints checklist.
- **gate_type** — `standard` (linear gate-before-advance), `convergence` (gen→verify loop with `max_rounds`), `passthrough` (no gate; rare; only for setup stages).
- **max_rounds** — defaults from gate profile: `relaxed=3`, `standard=5`, `strict=5`, `audit=7`. Required field on `convergence` stages.
- **on_stagnation** — `escalate` (default; emit ExceptionEscalation), `retry` (rare; only for transient I/O), `abort` (very rare).
- **context_profile** — string key into `workflow-system/agent/context_profiles.yaml::profiles`.
- **deliverables** — repo-relative artifact paths consumed by next stage (P5 contract — no shared memory).
- **Writable** — list of repo-relative paths the L3 may modify; pairwise disjoint within a wave (S-8 invariant).
- **Read-only** — list of repo-relative paths the L3 may read; intersect freely across wave tasks.

## 4. Constraints Checklist (verbatim — must verify before finalizing plan)

The 9-item checklist is the gate the plan must clear before it can be
handed to L1 for execution. Each item is binary; partial-pass is not
acceptable.

1. **Every task row is L3** — no L0-L2 performing work. P1 enforced. Trivial
   exception (`< 20 lines`, single file) MAY be inlined into L0 with
   explicit `[trivial waiver]` annotation.
2. **Stage headers specify L1 agent constraints** — explicit "MUST NOT write
   code" / "MUST NOT execute Shell" line in every stage header.
3. **Execution model section present** — the 4-row table from §3 must be
   verbatim in the plan output (P1 reminder for downstream readers).
4. **Each wave: ≤5 tasks, pairwise disjoint writable files** — wave
   coordinator (L2) verifies disjointness at dispatch; conflict detection
   is O(|tasks|²) per wave. The 5-task ceiling matches L2 budget (~4K
   tokens) — exceeding it forces the wave to split.
5. **Each stage: ≤7 waves** — stage dispatcher (L1) verifies. Exceeding the
   7-wave ceiling forces stage split (often resolved by introducing an
   intermediate `gate` primitive).
6. **Task limits: impl ≤30min, research ≤45min, ≤6 writable files** —
   approximate budget; not enforced at runtime but used as a planning
   sanity check. Tasks exceeding 30min are usually candidates for
   sub-decomposition.
7. **Stage DAG: no cycles, gate-before-advance (D4)** — the stage graph
   must be a DAG; a cycle (e.g. design → impl → design) must be modeled
   as a single `convergence` stage with `max_rounds`. D4 = "no stage
   advances until predecessor gate PASS" per `decomposition-gate.md`.
8. **Convergence stages: max_rounds + stagnation rule specified** — every
   `gate_type: convergence` stage MUST have both fields populated; missing
   either is a P4 violation (no infinite loops).
9. **Predecessors referenced by artifact path, not content copy** — P5
   invariant. Plans that embed predecessor content directly violate
   context isolation and break the cached-prefix invariant.

The L0 agent runs the checklist as a self-verify before emitting the plan.
Any fail blocks the plan emission and forces revision.

## 5. Plan Mode Rules — DO and DO NOT

### 5.1 DO

- Use **read-only tools** for plan research: Read, Glob, Grep,
  SemanticSearch (allowed under L0 in plan mode per `_PLAN_MODE_OVERRIDES`).
- Emit the plan via `create_plan` (Cursor) or write `plan.md` (Claude
  Code). Other clients: emit raw markdown to stdout under a `# Plan` H1.
- Embed stage→wave→task decomposition with file ownership and AC for every
  L3 row.
- Annotate each stage's `gate_type`, `context_profile`, and convergence
  parameters (`max_rounds` + `on_stagnation`).
- Annotate every plan element with its delegation layer (L0/L1/L2/L3) so
  downstream readers can audit P1 compliance.
- Verify the §4 Constraints Checklist (especially P1 enforcement items)
  before finalizing.
- Cite predecessor artifacts by repo-relative path (S-2). External
  references use the GitHub URL (S-7).

### 5.2 DO NOT

- Do **NOT** dispatch tasks, write code, run tests, or modify files —
  this violates P1 + the plan-mode operating contract.
- Do **NOT** start execution until the user explicitly approves the plan
  (per the v3.x plan-mode-enforcement contract; user approval is the
  hand-off signal from PLAN MODE → AGENT MODE).
- Do **NOT** over-decompose (the 30min impl / 45min research budget is a
  ceiling, not a target — many tasks are 10-15min). Over-decomposition
  inflates wave count and breaks the ≤7-waves-per-stage invariant.
- Do **NOT** embed tool calls in the plan body — the plan is a
  declarative contract, not an executable script.
- Do **NOT** select model tier without rationale — `model_hint` defaults to
  `inherit`; explicit overrides need a per-task justification annotation.
- Do **NOT** skip the §4 Constraints Checklist. Plans that elide the
  checklist break downstream gate evaluation.
- Do **NOT** copy predecessor content into the plan body. Cite by path
  per P5.

### 5.3 Cursor-specific notes

When running under Cursor, the `SwitchMode` tool is available. The L0 agent
SHOULD call `SwitchMode(target_mode_id="plan")` if the host signals plan
intent but the runtime mode is still `agent`. Conversely,
`SwitchMode(target_mode_id="agent")` is the explicit hand-off after user
approval (do not auto-call without user consent).

### 5.4 Claude Code-specific notes

When running under Claude Code, plan output goes to `plan.md` at the
working-directory root. The Claude Code TUI auto-renders the plan in a
side panel. The user-approval signal is a follow-up message containing
"approve" / "go ahead" / "execute" — at which point L0 transitions to
AGENT MODE and starts dispatch.

## 6. Reinforcement Rules (W-8 / SI-9) — Mechanism + L3 Obligation

When a stage gate FAILS (composite_score < threshold OR blocker count > 0
OR coverage < threshold), the next round's dispatch carries
`applicable_rules.reinforcement` — top-5 prior-round findings (severity ≥
major) injected as MUST-fix mandates.

### 6.1 `applicable_rules.reinforcement` payload shape

```yaml
applicable_rules:
  reinforcement:                          # max 5 entries; severity-filtered
    - id: "R-001"
      severity: blocker | critical | major
      finding: "verbatim from prior-round gate output"
      source_file: "repo/relative/path.py"     # optional; for L3 to locate
      source_line: 142                          # optional
      remediation_hint: "1-sentence delta"      # optional
    # ... up to 4 more entries ...
```

**Severity filter:** blocker > critical > major; ignore minor / info /
warn from reinforcement (those go to `informational` instead). **Selection
order:** by severity descending; within same severity, by gate
chronological order (earliest finding first). **Deduplication:** identical
`(severity, source_file, source_line)` tuples merge into one entry with
combined `finding` + `remediation_hint` text.

### 6.2 L3 obligation

L3 Task Agents that receive a dispatch with non-empty
`applicable_rules.reinforcement` MUST:

1. Address ALL listed reinforcement rules **before** any new work. Failure
   to address any rule = automatic blocker in the next gate (the gate
   evaluator parses the L3 status report for explicit closure of each
   reinforcement entry).
2. Emit per-rule closure markers in the StatusReport's `delta` block:
   `closes_reinforcement: ["R-001", "R-003"]`.
3. If a rule cannot be closed in this round (e.g. dependency on another
   wave's task), explicitly emit `defers_reinforcement: ["R-002 — blocked
   on TaskAgent T03 deliverable"]` so the L1 gate can evaluate
   stagnation correctly.

### 6.3 Python API surface

Two source-of-truth modules:

- `src/devolaflow/gate/reinforcement.py` — `findings_to_reinforcement(findings, max_entries=5)` filters, sorts, and deduplicates findings into the reinforcement payload. ~227 LOC at v8.4.x.
- `src/devolaflow/feedback.py` — `ProposalGenerator.generate_round_dispatch(round_n, prior_findings, base_dispatch)` merges prior-round findings into `base_dispatch.applicable_rules.reinforcement` and bumps the dispatch payload's round counter.

The two are always called together by L1 between gate evaluation and
round-N+1 wave dispatch. Verified end-to-end by
`tests/test_dispatch_emission_runs_hooks.py` and
`tests/test_no_ghost_features.py::test_round_aware_dispatch_escalation_exists`.

### 6.4 Round-aware escalation table

`task_adaptive_selector._ROUND_ESCALATION_DEFAULTS` defines the
per-round-number context budget bumps and `model_hint` upgrades:

| Round | Budget multiplier | `model_hint`     | Notes                                        |
| ----- | ----------------- | ---------------- | -------------------------------------------- |
| 1     | 1.0               | `inherit`        | base round (no reinforcement carried)        |
| 2     | 1.0               | `inherit`        | first reinforcement round; budget unchanged  |
| 3     | 1.2               | `quality`        | +20% budget; force-quality model             |
| 4+    | 1.2               | `quality`        | sustained at +20% / quality                  |

L1 applies the table when calling `generate_round_dispatch()`.

## 7. Convergence Loop Mechanics

The Gen-Verify loop is the convergence wave's runtime topology. It applies
to `gate_type: convergence` stages — typically `review+fix`, `test+fix`,
`benchmark+optimize`, `design+critique`, and `verify+remediate`.

### 7.1 Loop structure

1. L2 Wave dispatches **generator** task + **verifier** task in parallel.
   Generator produces an artifact; verifier evaluates it against
   `acceptance_criteria` (lifted from the wave dispatch payload).
2. Verifier emits `{PASS | FAIL + feedback}`. PASS → wave done; L1 marks
   stage gate PASS. FAIL → L1 calls `generate_round_dispatch()` (see §6.3)
   to build round N+1 dispatch carrying the verifier's findings as
   reinforcement payload.
3. Round N+1 generator addresses the reinforcement (see §6.2 L3
   obligation), produces refined artifact. Verifier re-evaluates.
4. Loop terminates on **any** of:
   - verifier emits PASS (success path; gate PASS),
   - `round_n >= max_rounds` (escalate per §8),
   - composite_score Δ < `stagnation_epsilon` over 2 rounds (stagnation;
     escalate per §8),
   - L1 receives ExceptionEscalation from any task (immediate halt).

### 7.2 `max_rounds` defaults per gate profile

| Profile    | `max_rounds` | Rationale                                                   |
| ---------- | ------------ | ----------------------------------------------------------- |
| `relaxed`  | 3            | low-stakes content; cheap to escalate after 3 attempts      |
| `standard` | 5            | balanced default; matches W-8 / SI-9 hard cap               |
| `strict`   | 5            | same hard cap; higher per-round bar (composite ≥ 90)        |
| `audit`    | 7            | release-blocking; willing to spend more rounds for ≥ 95     |

The `max_rounds` value MUST be specified on every `convergence` stage; the
profile default is a fallback only.

### 7.3 Stagnation detection

Stagnation = composite_score Δ < `stagnation_epsilon` (default 1.0) over
**2 consecutive rounds** with no new blocker introduced. The 2-round
window prevents single-round noise (e.g. a verifier flip-flop) from
falsely triggering escalation.

### 7.4 Verifier criteria sourcing

The verifier reads `acceptance_criteria` from the wave dispatch payload
(per `schemas/lean-dispatch.yaml#layout_invariant.canonical_order`
position `accept`). Acceptance criteria authoring guidance lives in
`references/decomposition-gate.md` §"Acceptance Criteria". For
`convergence` stages, AC SHOULD be expressed as testable assertions
(boolean predicate) rather than descriptive prose, so the verifier can
emit unambiguous PASS / FAIL.

## 8. Stagnation Escalation (P4 Bounded Retry)

When the convergence loop terminates due to `max_rounds` exceeded OR
stagnation, L1 emits an `ExceptionEscalation` upward to L0 per the P4
bounded retry contract.

### 8.1 P4 classification

Every loop has a `max_iterations` ceiling. Every failure triggers a
classified response:

| Classification | Trigger                                        | Action                                                        |
| -------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| `retry`        | transient I/O fault; round_n < max_rounds      | re-dispatch same round payload (no reinforcement bump)        |
| `escalate`     | max_rounds reached OR stagnation OR blocker    | emit ExceptionEscalation upward (Task → Wave → Stage → Project → Human) |
| `abort`        | unrecoverable schema violation OR P1 violation | halt entire workflow; surface to human immediately            |

### 8.2 Escalation chain

The escalation chain is always upward, never skip levels:

```text
L3 Task → L2 Wave → L1 Stage → L0 Project → Human
```

L2 receives Task escalations and decides: address inline (e.g. retry with
adjusted dispatch) or propagate to L1. L1 receives Wave escalations and
decides: re-dispatch wave or propagate to L0. L0 receives Stage
escalations and decides: re-dispatch stage with relaxed profile, or
present options to human. Skipping levels (e.g. L3 → L0 direct) breaks
the audit trail and is a P4 violation.

### 8.3 ExceptionEscalation schema

```yaml
exception_escalation:
  source_id: "<task_id|wave_id|stage_id>"
  source_layer: "L1|L2|L3"
  reason: "max_rounds_exceeded|stagnation|p1_violation|p4_violation|unrecoverable_error"
  classification: "retry|escalate|abort"
  context:
    round_n: <int>                  # only for max_rounds_exceeded / stagnation
    composite_history: [<float>]    # last 5 rounds, oldest first
    blocker_findings: [<str>]       # list of blocker-severity findings
    last_dispatch_id: "<dispatch_id>"
  remediation_hint: "<1-sentence>"  # optional; L1's best-guess fix
```

The schema is canonical per `schemas/exception-escalation.schema.yaml`
(when present) and consumed by L0's `gate.scorer.evaluate_escalation()`.

### 8.4 Per-team escalation routing

Default routing (configurable per `context_profiles.yaml::profiles.<name>.escalation_routing`):

| Team       | Primary escalation target | Rationale                                      |
| ---------- | ------------------------- | ---------------------------------------------- |
| Research   | Stage Agent (L1)          | research blocks usually need scope re-decision |
| Design     | Project Agent (L0)        | design blocks usually need workflow re-routing |
| Implement  | Wave Agent (L2)           | impl blocks often resolve in adjacent wave     |
| Test       | Wave Agent (L2)           | test blocks usually mean code-side fix needed  |
| Review     | Stage Agent (L1)          | review blocks usually mean criteria revision   |

## 9. Cross-References

### 9.1 SKILL.md sections (1-paragraph summaries)

- `## Mode Awareness` — Plan-mode detection priority order + AGENT MODE
  default + `_PLAN_MODE_OVERRIDES` runtime hook.
- `### Reinforcement Rules (v5.1+)` — 1-paragraph summary of §6 above.
- `### Wave Coordination Modes` — Gen-Verify mode selection + topology
  override.
- `## Gate Mechanism` — composite_score formula + per-dimension scoring +
  pass conditions + gate profiles.

### 9.2 Source files (Python API)

- `src/devolaflow/gate/reinforcement.py` — `findings_to_reinforcement()` (W-8 module).
- `src/devolaflow/feedback.py` — `ProposalGenerator.generate_round_dispatch()`.
- `src/devolaflow/task_adaptive_selector.py` — `_PLAN_MODE_OVERRIDES`, `_ROUND_ESCALATION_DEFAULTS`, `apply_plan_mode_overrides()`.
- `src/devolaflow/lifecycle/dispatcher.py` — dispatch event emission +
  `pre_dispatch` / `post_dispatch` hook orchestration.
- `src/devolaflow/lifecycle/__init__.py` — `run_hooks(event, payload, *, strict=False)`.

### 9.3 Schemas

- `schemas/lean-dispatch.yaml` — canonical dispatch payload (lean format);
  `applicable_rules.reinforcement` field at canonical_order position
  `rules`.
- `schemas/lean-report.yaml` — StatusReport schema; `delta.closes_reinforcement`
  / `defers_reinforcement` field semantics.

### 9.4 AGENTS.md rules

- `AGENTS.md` §"P1 Dispatcher-Not-Implementer" — L0-L2 may NOT execute
  work.
- `AGENTS.md` §"P4 Bounded Retry" — every loop has a `max_iterations`
  ceiling.
- `AGENTS.md` §"W-8 — Convergence Round Reinforcement (SI-9)" —
  reinforcement-loop discipline + 2-round stagnation rule.
- `AGENTS.md` §"S-1 — Dispatcher-Not-Implementer Invariant" — Soul-rule
  invariant; trivial exception (single file, < 20 lines) does NOT apply
  to plan mode (plans are inherently dispatcher artifacts).

### 9.5 Testing surface

- `tests/test_no_ghost_features.py::test_round_aware_dispatch_escalation_exists` — pins the round-aware dispatch wiring.
- `tests/test_no_ghost_features.py::test_reinforcement_findings_function_exists` — pins `findings_to_reinforcement()` callable.
- `tests/test_dispatch_emission_runs_hooks.py` — end-to-end pre_dispatch / post_dispatch hook coverage; will land in PV-04 per
  `.local/research/v9.0.0_implementation_plan.md` §6.4.
- `tests/test_task_adaptive_selector_plan_mode.py` — `_detect_plan_mode()`
  + `_PLAN_MODE_OVERRIDES` application coverage.

### 9.6 External

- DevolaFlow repository: https://github.com/YoRHa-Agents/DevolaFlow
- NineS evaluator (used for SI-2 self-eval): https://github.com/YoRHa-Agents/NineS
