---
id: subagent-patterns
version: "11.4.0"
purpose: >
  Canonical 4-pattern subagent taxonomy (Inline Tool / Fan-Out / Agent
  Pool / Teams) per the philschmid 2026 article, mapped to DevolaFlow's
  L0..L3 hierarchy with explicit Pattern 3 forward-compat plan +
  Pattern 4 permanent-NOT-SUPPORTED rationale (P5 invariant). Pairs
  with src/devolaflow/skills/subagent_pattern.py (the pure-function
  selection helper) and W-24 (Subagent Pattern Selection workflow rule).
tier: 2
token_estimate: 3700
last_updated: "2026-08-19"
---

# Subagent Patterns — 4-Pattern Taxonomy and DevolaFlow Coverage

> **Tier-2 reference** — load when the dispatcher needs to decide which
> of the 4 subagent patterns (Inline Tool / Fan-Out / Agent Pool / Teams)
> applies to a wave-decomposition decision. Pairs with `references/grill-mode.md`
> (HUMAN-facing interview pattern; orthogonal to this AGENT-to-AGENT
> dispatch pattern) and supersedes (without removing) the v7.x
> anthropic-coordination-blog mapping at `references/execution-protocol.md`
> §7.3.

## §1 — When to Load

Three trigger surfaces feed subagent-pattern reference activation:

1. **Wave-decomposition decision** — the L1 Stage Agent or L2 Wave
   Agent is about to decompose a stage into a wave-list (or a wave
   into a task-list) and needs to decide whether tasks land as a
   single INLINE dispatch or as a parallel FAN_OUT wave.
2. **Multi-step workflow under design** — a workflow needs persistent
   per-agent conversation history across turns (Pattern 3). At v11.4.0
   this is **forward-compat documentation only** — no API path
   activates Pattern 3; load this reference to consult §5 for the
   v12.0.0+ landing pathway.
3. **Operator question — "should we use Teams for this?"** — the
   operator-education path. Load this reference to consult §6 for the
   verbatim P5 invariant that permanently forbids Pattern 4 plus the
   structured rationale returned by
   `forbidden_pattern_rationale("TEAMS_FORBIDDEN")`.

### 1.1 — Distinction from `references/grill-mode.md`

`grill-mode.md` and `subagent-patterns.md` codify two **orthogonal
axes** that may both be active in a single L0 session:

| Axis | `grill-mode.md` | `subagent-patterns.md` |
|---|---|---|
| Layer of the conversation | HUMAN ↔ L0 (operator-facing interview) | L0 ↔ L1, L1 ↔ L2, L2 ↔ L3 (agent-to-agent dispatch) |
| Activation trigger | Natural-language operator phrases ("grill me", "stress-test the plan") via `classify_grill_intent` | Wave-decomposition decision at dispatch time via `select_pattern` helper invocation |
| Decision time | Plan-time / design-time (BEFORE the plan template is authored) | Dispatch-time (AT wave decomposition; ON the gate.subagent_pattern field in v12.0.0+) |
| Default-OFF mechanism | Returns `NO_GRILL` for any non-trigger prompt | Returns `INLINE` as the conservative default for ambiguous inputs |
| New env flag introduced | NO (W-20 reuse-first; activation purely natural-language) | NO (W-20 reuse-first; activation purely helper-API) |

The two references **compose freely** — a grill-mode interview may
surface a multi-step workflow whose plan template subsequently invokes
`select_pattern` — but they are never substitutes for each other.
Confusing them is the most frequently anticipated v11.4.0
operator-friction failure (gap analysis risk R-11; see §11.4).

### 1.2 — Distinction from `references/execution-protocol.md` §7.3

DevolaFlow's existing v7.x mapping at `references/execution-protocol.md`
§7.3 (lines 485–495) tabulates the **anthropic-coordination-blog**
4-pattern taxonomy: orchestrator-subagent, agent teams, message bus,
shared state. The philschmid 2026 taxonomy that this reference codifies
covers the **same architectural axis** but reframes it through a
**subagent-lifecycle lens** (control-over-the-subagent-lifecycle
ordering: Pattern 1 → Pattern 4) rather than a
**coordination-topology lens** (orchestration shape: orchestrator-subagent,
teams, bus, shared state).

Both references coexist after v11.4.0: `execution-protocol.md` §7.3
remains the canonical v7.x baseline (NOT removed in v11.4.0; v12.0.0
SI-1 may add a 1-line forward-pointer from §7), and this reference is
the canonical v11.4.0+ taxonomy. The §4 coverage matrix makes the
row-level correspondence explicit. The §7.3 row "shared state:
Forbidden by P5" and §6 below (Pattern 4 Teams: Permanent
NOT_SUPPORTED) are the **same architectural commitment under two
different names** — both cite the verbatim P5 invariant from
`repo-governance.mdc` §A-1 P5 as the source-of-truth.

## §2 — The 4 Patterns (Verbatim Citations)

Citations in this section are **verbatim** from the upstream philschmid
article (`https://www.philschmid.de/subagent-patterns-2026`, May 5
2026). Per CO-2 / C-3, file paths, error messages, and quoted strings
are copied EXACTLY; paraphrasing is prohibited.

### 2.1 — Pattern 1: Inline Tool

> The simplest pattern. The main agent calls a tool that spawns a
> subagent and returns the result as the tool response. From the main
> agent's perspective, calling a subagent is identical to calling
> `read_file` or `run_command`.

(philschmid article §1 "Inline Tool: Subagent as a Function Call")

**Tools surface** (verbatim, philschmid article §1):

> The main agent has a tool, e.g. `call_agent`. It sends a task, gets
> a result. The subagent runs in its own context with its own tools
> and instructions. The main agent never manages the subagent's
> lifecycle directly.

**Sync vs. async sub-variant** (verbatim, philschmid article §1):

> Sync (above): The tool call blocks. The main agent's turn is paused
> until the subagent finishes. The result arrives as a normal tool
> response.
>
> Async: The tool returns immediately with an agent ID. The subagent's
> result is injected into the conversation as a notification message
> when it finishes. The main agent can do other tool calls before the
> result arrives.

**When to use** (verbatim):

> Self-contained work. Research lookups, code reviews, file analysis,
> test generation. Most subagent use cases start and stay here.

**Limitations** (verbatim):

> Works with any model that supports tool use, including smaller and
> cheaper ones. Results arrive as a single tool response (sync) or as
> an injected notification message (async). No way to send follow-up
> instructions, check progress, or cancel early. If the subagent
> misunderstands the task, you find out when the result comes back.

**DevolaFlow coupling.** The sync sub-variant maps to L0 / L1 / L2
dispatching a single L3 via the `Task` tool — exactly the sync
`call_agent` shape. The async sub-variant is **NOT supported** by the
current `Task` tool (gap analysis §4.1 row 1b); v12.0.0+ may evaluate
an async-`Task` variant (forecast-indicative, not commitment).

### 2.2 — Pattern 2: Fan-Out

> The main agent spawns subagents and collects results using a
> `wait_agent` tool. Unlike the inline tool, spawning and collecting
> are separate steps. `spawn_agent` always returns immediately. The
> model decides what to do next: call `wait_agent` right away, do its
> own work first, or spawn more agents before waiting.

(philschmid article §2 "Fan-Out: Spawn Agents and Wait for Results")

**Tools surface** (verbatim):

> Two tools: `spawn_agent` dispatches work and returns immediately
> with an ID. `wait_agent` blocks until one or more agents finish.

**Differentiator from Pattern 1** (verbatim):

> The difference from Pattern 1: the model controls when to collect.
> It can spawn 5 agents in parallel, do its own file reads, then call
> `wait_agent`. `wait_agent` can act as a global mailbox that wakes up
> on subagent completion and returns all available results.

**When to use** (verbatim):

> Multiple independent tasks that can run concurrently. The main agent
> does not need intermediate results from one subagent to start
> another.

**Limitations** (verbatim):

> The model needs to correctly decide when to wait. A model that calls
> `wait_agent` immediately after every spawn gets no benefit over
> Pattern 1. The value depends on the model's ability to interleave
> its own work between spawn and wait. Results are collected in batch
> via `wait_agent`, which returns all completed agent outputs since
> the last call. Still fire-and-forget: no way to send follow-up
> instructions or course-correct mid-task to subagents.

**DevolaFlow coupling.** Maps to an L2 wave dispatching N parallel
L3 task agents — first-class DevolaFlow primitive.
`references/agent-hierarchy.md` §5 caps "Max tasks per wave = 5" +
"File ownership within wave: Disjoint (strict)";
`references/execution-protocol.md` §13 documents
`dispatch_wave_tasks(...)` (asyncio.gather + bounded Semaphore). The
"model decides when to wait" interleaving is structurally absent —
L2 always waits at the wave barrier per
`wave_definition.sync_barrier.mode`. Out of scope for v11.4.0.

### 2.3 — Pattern 3: Agent Pool

> The main agent spawns long-lived subagents and communicates with
> them through messages. Agents persist across interactions. The main
> agent can send follow-up instructions, check status, and coordinate
> work between agents.

(philschmid article §3 "Agent Pool: Persistent Agents with Messaging")

**Tools surface** (verbatim):

> This requires a richer tool surface: `spawn_agent`, `send_message`,
> `wait_agent`, `list_agents`, `kill_agent`.

**State semantics** (verbatim):

> Unlike Pattern 2, agents here are stateful and interactive. The main
> agent sends a message, gets a response, and sends another message to
> the same agent. The agent retains its full conversation history.
> This supports multi-step workflows where the main agent coordinates
> between specialists.

**When to use** (verbatim):

> Multi-step workflows where agents need to collaborate. The main
> agent routes information between specialists.

**Limitations** (verbatim):

> The main agent must track multiple agent states, decide when to send
> follow-ups vs wait, and route information correctly. Smaller models
> lose track of which agent has which context, or forget to call
> `kill_agent` when done. Frontier models might handle 2-4 agents
> okayish.

**DevolaFlow coupling.** **NOT MODELLED in v11.x.** P1 + P5 + L3
fresh-context guarantee preclude persistent stateful workers. The
closest analogue is the `change-driven` workflow's `apply ↔ verify`
convergence loop (`references/execution-protocol.md` §12) — each
round dispatches a NEW L3 with fresh context; persistent state lives
in `.local/.agent/active/<id>/STATUS.yaml` artifacts, not
conversation history. Forward-compat-only landing in §5.

### 2.4 — Pattern 4: Teams

> Agents message each other directly without going through the main
> agent. The main agent sets up the team, defines roles, and steps
> back. Agents coordinate among themselves using direct messaging or
> a shared mailbox.

(philschmid article §4 "Teams: Agents Talk to Each Other")

**Cross-agent addressing** (verbatim):

> The tool surface includes cross-agent addressing. Each agent gets
> `send_message` in its own tool set and can address other agents by
> name or path.

**When to use** (verbatim):

> Large tasks where the coordination logic exceeds what a single agent
> can manage step-by-step.

**Limitations** (verbatim):

> Every agent in the team needs frontier-class model capabilities, not
> just the main agent. Each team member must independently decide when
> to message teammates, what to include, and when to report back.
> Models can message the wrong agent, forget to report completion, or
> get stuck in loops. Beyond model capability, there are infrastructure
> challenges: cycle detection (A waits on B, B waits on A), conflict
> resolution (two agents edit the same file), and shutdown coordination.
> Debugging is hard because message chains between agents are difficult
> to trace and failures cascade.

**DevolaFlow coupling.** **PERMANENTLY NOT SUPPORTED.** P5
(artifacts-as-contracts) explicitly forbids cross-agent shared state
and direct messaging. The full P5 verbatim citation and the rationale
for the permanent stance live in §6.

### 2.5 — Cross-pattern principles (philschmid article §"Choosing a Pattern")

Four cross-pattern principles, verbatim from §"Choosing a Pattern":

**Start point** (verbatim):

> Start with Pattern 1. Most tasks that feel like they need a
> multi-agent system work fine with a well-prompted inline tool call.

**Model-capability ladder** (verbatim):

> Each step up requires a more capable model. Pattern 1 works with any
> model that can call tools. Pattern 2 needs a model that reasons
> about when to wait. Pattern 3 needs a model that tracks multi-agent
> state across turns. Pattern 4 needs frontier models for every agent.
> With a smaller or cheaper model, stay with Pattern 1 or 2.

**Result-collection delta** (verbatim):

> Result collection also changes across patterns. Pattern 1 returns
> results inline as a tool response. Pattern 2 batches results via
> `wait_agent`. Pattern 3 delivers results incrementally. Pattern 4
> surfaces only what agents explicitly report back; everything else
> stays inside inter-agent conversations.

**Forward-looking principle** (verbatim, last paragraph of article):

> For patterns 2-4, `spawn_agent` always returns immediately and
> `wait_agent` collects results when the model decides to call it.
> The framework provides the tools. The model controls the
> orchestration. A task that takes 4 coordinated agents today may be
> solvable by a single agent with a better model tomorrow.

The model-capability ladder justifies the helper's §3.2 downgrade
rule — `model_tier in ("small", "balanced")` +
`persistent_state_needed=True` returns INLINE rather than
AGENT_POOL_FORWARD because Pattern 3 demands a model that tracks
multi-agent state across turns.

## §3 — Selection Decision Tree

The operator-quotable selection algorithm. Mirrors gap analysis §5
"Selection Matrix"; implemented at
`src/devolaflow/skills/subagent_pattern.py::select_pattern`.

### 3.1 — Input axes

| Axis | Type | Source / how to derive |
|---|---|---|
| `complexity` | `Literal["TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"]` | `devolaflow.skills.change_activation.classify_complexity(files_count, loc_estimate, is_cross_cutting)` (existing v9.1.2 PV-02 + v11.1.0 PV-02 surface) |
| `model_tier` | `Literal["small", "balanced", "frontier"]` | dispatcher's `model_hint` field per `schemas/lean-dispatch.yaml` (existing canonical position; budget-quality-balanced) |
| `task_count` | `int >= 1` | wave-decomposition output (number of independent tasks within a wave) |
| `parallel_independence` | `bool` | `True` iff tasks are independent (no shared writable files, no data deps) per `references/agent-hierarchy.md` §5 |
| `persistent_state_needed` | `bool` | `True` iff the workflow requires multi-turn agent collaboration with retained per-agent conversation history |

### 3.2 — Decision rule

```
if persistent_state_needed:
    if model_tier == "frontier" and complexity in ("STANDARD", "COMPLEX"):
        → AGENT_POOL_FORWARD            # Pattern 3 — forward-compat plan; v11.4.0 reference-only
    else:
        → INLINE                         # under-resourced; downgrade to Pattern 1
elif task_count >= 2 and parallel_independence:
    → FAN_OUT                            # Pattern 2 — L2 wave dispatch
else:
    → INLINE                             # Pattern 1 — single L3 dispatch via Task tool

# TEAMS_FORBIDDEN is never returned by select_pattern; it is a verdict the
# helper raises on caller request only, in service of operator education
# ("don't reach for this — here's why P5 forbids it"). See §6 + §8.
```

Three exits (INLINE / FAN_OUT / AGENT_POOL_FORWARD) and one
out-of-band verdict (TEAMS_FORBIDDEN) returned only by the
operator-education path `forbidden_pattern_rationale`.

### 3.3 — Per-pattern verdict

| Pattern | Verdict at v11.4.0 cycle close | Rationale | Required graduation step for activation |
|---|---|---|---|
| 1a Inline Tool sync | **ADOPT (already native)** | DevolaFlow's `Task` tool is exactly this pattern; documented surface | No graduation needed — exists today |
| 1b Inline Tool async | **NEST UNDER EXISTING (v12.0.0+ candidate)** | Would require async `Task` tool variant; NEST under existing dispatcher API rather than APPEND new top-level surface | v12.0.0 SI-1 evaluation: does cycle-evidence justify async `Task`? Out of v11.4.0 scope. |
| 2 Fan-Out | **ADOPT (already native)** | L2 wave dispatch with disjoint owned-files per `references/agent-hierarchy.md` §5 | No graduation needed — exists today |
| 3 Agent Pool | **FORWARD-COMPAT-ONLY** | NOT representable in current L0..L3 hierarchy without a NEW L3 sub-type; v11.4.0 documents the landing pathway (a new "persistent worker" role); v12.0.0+ SI-1 evaluates whether to land it | v12.0.0+ SI-1 cycle: design new L3 sub-type with explicit persistent-state contract; evaluate against P1/P5 |
| 4 Teams | **FORBIDDEN (permanent stance)** | Soul-level P5 invariant explicitly forbids cross-agent shared state | Reversal requires SI-1 + ADR + W-21 2-cycle deliberation cadence + SI-3 §3.2 architecture-rationality ≥ 9.5/10 |

### 3.4 — Per-input spot-check table (verification checklist)

Spot-check the helper's output:

| If `complexity` is | And `task_count` is | And `parallel_independence` is | And `model_tier` is | And `persistent_state_needed` is | Then verdict |
|---|---|---|---|---|---|
| TRIVIAL | 1 | n/a | any | False | INLINE (P1 trivial waiver applies) |
| SIMPLE | 1 | n/a | any | False | INLINE (single Task dispatch) |
| SIMPLE | ≥ 2 | True | any | False | FAN_OUT (L2 wave with N parallel L3) |
| STANDARD | 1 | n/a | any | False | INLINE (cascade: L0→L1→L2→single L3) |
| STANDARD | ≥ 2 | True | any | False | FAN_OUT (cascade L0→L1→L2 with parallel L3 wave) |
| STANDARD | ≥ 2 | False | any | False | INLINE (sequential L3s — Pattern 2 needs independence) |
| STANDARD or COMPLEX | any | any | frontier | True | AGENT_POOL_FORWARD (forward-compat reference; v11.4.0 does NOT activate) |
| any | any | any | small or balanced | True | INLINE (downgrade — Pattern 3 needs frontier model) |
| any | any | any | any | n/a + caller asks "should I use Teams?" | TEAMS_FORBIDDEN (operator-education path; helper returns structured rejection) |

Each row is a forward-applicable invariant — divergent helper output
for the same inputs is a release blocker.

### 3.5 — Worked examples (from realistic DevolaFlow cycles)

Three worked examples cross-walk realistic v11.x decompositions:

* **v11.3.0 grill-mode integration.** `STANDARD` / 1 task /
  `parallel_independence=False` / `balanced` / `persistent=False` →
  **INLINE**. Matches the actual cycle: L0→L1→L2→single L3 cascade
  per W-22.1.
* **v11.1.0 cascade-restoration PV-05 batch dispatch.** `COMPLEX` /
  4 tasks / `parallel_independence=True` / `balanced` /
  `persistent=False` → **FAN_OUT**. Matches PV-05's 4 parallel L3s
  across 2 stages per v11.1.0 retrospective L-3.
* **Hypothetical multi-step research workflow.** `STANDARD` / 2
  tasks (researcher + writer) / `parallel_independence=False` /
  `frontier` / `persistent=True` → **AGENT_POOL_FORWARD**
  (forward-compat; v11.4.0 falls back to INLINE round-robin via the
  `apply ↔ verify` convergence loop).

## §4 — DevolaFlow Current Coverage Matrix

The v11.4.0 differential against `references/execution-protocol.md`
§7.3 (v7.x anthropic-coordination-blog baseline). The new taxonomy
reframes the same architectural axis through a subagent-lifecycle
lens; row-level correspondence below.

| # | philschmid pattern | anthropic-blog analog | DevolaFlow status | Maps to L0..L3 hierarchy as | Source citation |
|---|---|---|---|---|---|
| 1a | **Inline Tool (sync)** | orchestrator-subagent (synchronous) | **Native** | L0 / L1 / L2 dispatching a single L3 via the `Task` tool that blocks until report | `workflow-system/agent/SKILL.md` §"AGENT MODE" (`Task` tool delegation contract); `references/agent-hierarchy.md` §3 L0 step 4 (single-Task dispatch); `references/execution-protocol.md` §7.3 row 1 (orchestrator-subagent: Native) |
| 1b | **Inline Tool (async)** | orchestrator-subagent (async — not in anthropic-blog) | **Not supported** | Would require non-blocking `Task` tool (returns immediately + injects notification when complete); current `Task` tool is sync-only | `Task` tool description (host-runtime) explicitly blocks; `dispatch_wave_tasks(...)` is internal to wave orchestration, not surfaced as an async-`Task` analog |
| 2 | **Fan-Out** | orchestrator-subagent (parallel) | **Native** | L2 wave dispatching N parallel L3 tasks (max 5 per wave) with sync barrier collection | `references/agent-hierarchy.md` §5 "Max tasks per wave = 5" + "File ownership within wave: Disjoint (strict)"; `references/execution-protocol.md` §13 `dispatch_wave_tasks(...)` with `asyncio.gather` + bounded `Semaphore`; `wave_definition.sync_barrier.mode: parallel\|all\|any\|n_of(k)` |
| 3 | **Agent Pool** | agent teams (persistent workers) | **Not modelled (forward-compat plan in v11.4.0; landing surface deferred to v12.0.0+)** | NOT representable in current 4-layer hierarchy — would require a NEW L3 sub-type ("persistent worker") that violates the L3 fresh-context guarantee | `references/execution-protocol.md` §7.3 row 2 ("agent teams (persistent workers): Not modelled as a primitive; P1 + L3 fresh-context guarantee preclude persistent workers"); `references/agent-hierarchy.md` §3 L3 "Reports to: Wave Agent" + "Delegates to: Nothing (leaf)" |
| 4 | **Teams** | shared state + agent teams (cross-agent messaging) | **Forbidden by P5 (permanent stance — see §6 below)** | NOT representable — Soul-level P5 invariant explicitly forbids cross-agent shared state and direct messaging | `repo-governance.mdc` §A-1 P5 ("Layers communicate through artifact files, not shared memory or conversation history. … No bidirectional shared state."); `references/execution-protocol.md` §7.3 row 4 ("shared state: Forbidden by P5"); v11.1.0 retrospective §3 D-3 (Soul-set freeze rationale) |

### 4.1 — Coverage summary

| Coverage tier | Count | Patterns |
|---|---:|---|
| Native | 2 | Pattern 1a Inline Tool sync, Pattern 2 Fan-Out |
| Not supported (could be added without P5 violation) | 1 | Pattern 1b Inline Tool async — v12.0.0+ may evaluate |
| Forward-compat only (v11.4.0 reference-only; v12.0.0+ landing surface) | 1 | Pattern 3 Agent Pool |
| Forbidden permanently (Soul-level P5 invariant) | 1 | Pattern 4 Teams |

DevolaFlow's existing 4-layer hierarchy is structurally aligned with
the philschmid taxonomy's first three rows: Patterns 1 + 2 land
cleanly; Pattern 3 has a deliberate landing pathway (NEW L3 sub-type,
not a relaxation of the existing L3 contract); Pattern 4 is
permanently off the table per a Soul-level commitment that the
article's own infrastructure-challenge enumeration validates. Pattern
1b is the **single optionality v11.4.0 pre-stages** for v12.0.0 SI-1
— async `Task` would land it without P5 violation but requires
editing the `Task` tool surface (see §7).

## §5 — Pattern 3 Agent Pool Forward-Compat Plan

Pattern 3 is documented in this reference as **forward-compat plan
only** at v11.4.0. The `select_pattern` helper returns the literal
verdict `AGENT_POOL_FORWARD` when its inputs match the §3.2 decision
rule's Pattern-3 branch, but **no API path actually activates a
persistent agent pool at v11.4.0** — the verdict is a documentation
anchor for the v12.0.0+ landing pathway plus an operator-facing signal
that the workflow's shape is recognized.

### 5.1 — Why deferred

Two structural commitments preclude Pattern 3 at v11.x:

1. **P1 Dispatcher-Not-Implementer.** L0 / L1 / L2 dispatchers MUST
   delegate to L3; persistent worker pools the dispatcher messages
   directly violate the dispatcher-not-implementer invariant.
2. **L3 fresh-context guarantee.** Each L3 receives a fresh
   ~8K-token context per dispatch (`references/agent-hierarchy.md`
   §3 L3 + §6). A persistent worker retaining conversation history
   across dispatches violates the guarantee — behaviour depends on
   prior turns the dispatcher cannot inspect.

Landing Pattern 3 requires a **NEW L3 sub-type** ("persistent
worker") with explicit per-agent state contract, NOT a relaxation of
the existing L3 contract.

### 5.2 — Current operator workaround

Operators needing multi-step collaboration in v11.4.0 fall back to
**INLINE round-robin via the `change-driven` workflow's
`apply ↔ verify` convergence loop** (`references/execution-protocol.md`
§12). Each round dispatches a NEW L3 with fresh context; persistent
state lives in `.local/.agent/active/<id>/STATUS.yaml` artifacts
(`references/agent-workspace.md`), not conversation history. The
workaround is functionally equivalent for most research-and-iterate
workflows; trade-off is per-round artifact re-load vs in-conversation
retention. v12.0.0+ SI-1 will evaluate whether overhead justifies
landing the persistent worker sub-type.

### 5.3 — v12.0.0+ landing surface

v12.0.0 is committed to evaluating Pattern 3 landing under SI-1 / W-1
against P1 + P5. Landing surface (if approved):

* **NEW L3 sub-type "persistent_worker"** — dispatchable from L2 with
  an explicit `per_agent_state_contract` field; distinct from the
  default L3 task type at the schema level.
* **NEW lifecycle hooks** — `pre_pool_spawn`, `post_pool_message`,
  `pre_pool_kill` — wired into `devolaflow.lifecycle.run_hooks` (S-10)
  at byte-id-preserving no-op defaults.
* **Per-pool token-budget envelope** — `pool.context_budget` NESTed
  under a NEW `pool` block (A-2.3); separate from the per-task ~8K
  envelope so pool growth does not silently consume task budget.
* **Convergence-loop reuse** — the existing `apply ↔ verify` machinery
  becomes the orchestration spine; the persistent worker is the loop's
  state carrier rather than its input artifact.

Full design lands in v12.0.0 SI-1 gap analysis + ADR + PV-04 schema
NEST. v11.4.0 codifies only the verdict literal and pathway pointer.

### 5.4 — AGENT_POOL_FORWARD literal semantics at v11.4.0

The `AGENT_POOL_FORWARD` literal is **RESERVED** in the
`PatternVerdict` Literal at v11.4.0: present in the public type alias
(the 4 values are `INLINE`, `FAN_OUT`, `AGENT_POOL_FORWARD`,
`TEAMS_FORBIDDEN`) and returned by `select_pattern` ONLY when ALL three
conditions hold simultaneously — `persistent_state_needed=True` AND
`model_tier="frontier"` AND `complexity in ("STANDARD", "COMPLEX")`
(per §3.2). Even then, **callers receive a forward-compat-only verdict
— no API path activates Pattern 3 at v11.4.0**.

The verdict is a design-time signal that the workflow shape is
recognized as Pattern 3, plus a stable Literal value for v12.0.0+
call-site migration. Returning INLINE for the frontier+persistent
case would silently downgrade and lose that signal — operators would
have no way to audit whether the helper considered Pattern 3. The
reserved literal makes the design intent visible.

## §6 — Pattern 4 Teams: Permanent NOT_SUPPORTED Rationale

Pattern 4 is **permanently NOT supported** by DevolaFlow. The decision
is not a deferral but a Soul-level architectural commitment — reversal
requires the W-21 2-cycle deliberation cadence (§6.3 below).

The grounding invariant is **P5 Artifacts as Contracts**, quoted
verbatim from `repo-governance.mdc` §A-1 P5 (also mirrored in
`AGENTS.md` §A-1 P5):

> Layers communicate through artifact files, not shared memory or
> conversation history. Each artifact has a defined schema. The
> producing layer writes; the consuming layer reads. No bidirectional
> shared state.

(`repo-governance.mdc` §A-1 P5)

### 6.1 — Why P5 forbids Pattern 4

Pattern 4 enables agents to message each other directly. Each agent's
`send_message` recipient receives the message into its own
conversation history; the dispatcher does not see the message unless
an agent explicitly reports back. This violates P5 in two ways:

1. **Cross-agent messaging IS shared state.** When agent A sends
   message M to agent B, M becomes part of agent B's conversation
   history — which is, by P5's definition, "shared memory or
   conversation history" (quoted directly from the invariant).
2. **Peer addressing violates "producing layer writes; consuming
   layer reads".** P5 requires a one-way producer → consumer relation
   with a defined schema. Peer messaging is bidirectional by
   construction (A↔B) and the message has no schema (free-form
   natural language).

The P5 invariant has no "Pattern 4 exception" clause. Adding one
would weaken the invariant from "no bidirectional shared state" to a
default with a rider — not an invariant.

### 6.2 — The article's own infrastructure-challenge validation

Independently of P5, the philschmid article §4 Limitations (verbatim
in §2.4 above) enumerates infrastructure challenges that validate
DevolaFlow's stance. Each item is a class of bug that P5
architecturally prevents:

* **Cycle detection** — impossible under P5 because no agent waits on
  another agent's message; agents wait only for their own dispatched
  L3 (Pattern 1) or for a wave barrier (Pattern 2).
* **Conflict resolution** — impossible because file ownership is
  disjoint within a wave (`references/agent-hierarchy.md` §5).
* **Shutdown coordination** — trivial because L2 owns the shutdown
  contract via the wave barrier; L3s do not coordinate peer shutdown.
* **Debugging cascading failures** — bounded because every failure is
  captured in a TaskReport artifact; message chains are short and
  one-directional.

The article's enumeration is, in effect, independent expert opinion
that the problems P5 prevents are real and material — validation from
the same source that introduces the pattern P5 forbids.

### 6.3 — W-21 reversal pathway

P5 is a Soul-level invariant (S-1..S-10 freeze at v9.0.0); reversing
it would require all four W-21 conditions:

1. **2-cycle telegraph** in cycle N's retrospective (§3 "What was
   deferred and why") flagging a proposed P5 amendment for cycle N+2
   review. Cycle N+1 does NOT consider the amendment.
2. **SI-1 gap-analysis entry in cycle N+2** documenting the
   invariant, why no existing S-* / A-* / W-* rule covers the use
   case, the CI enforcement surface, and the per-cycle review trail.
3. **SI-3 evaluation §3.2 architecture-rationality ≥ 9.5/10** from
   cycle N+2's L0 (stricter than the minor-release ≥ 8.5 / major ≥
   9.0 composite thresholds because Soul amendments are
   highest-priority).
4. **Soul cap.** Post-amendment Soul count MUST stay ≤ 12 (currently
   at 10).

A P5 reversal that preserves the invariant for all current call sites
(adds a tightly-scoped exception rather than deleting the invariant)
would also need a NEW ADR. v11.4.0 does **not** propose a P5
amendment; this section documents the pathway only so future
operators understand what overturning entails. The
`forbidden_pattern_rationale("TEAMS_FORBIDDEN")` helper return value
cites §6 + the verbatim P5 quote, so operators who reach for Pattern
4 receive the structured P5 explanation rather than a bare rejection.

## §7 — v12.0.0 Integration Roadmap (Pre-Staging)

This section pre-stages the v12.0.0 PV-04 schema decision per the
A-2.3 NEST vs APPEND decision rule. The actual schema landing is OUT
of v11.4.0 scope; v12.0.0 SI-1 evaluates the decision against ≥1
month of v11.4.x stability-patch field evidence per the W-21 2-cycle
deliberation cadence.

### 7.1 — NEST vs APPEND verdict for `subagent_pattern`

Applying A-2.3's decision matrix to the proposed `subagent_pattern`
field:

| Test | Verdict for `subagent_pattern` |
|---|---|
| Does the behaviour modify how an existing block is interpreted? | **YES** — `gate.cascade_required` already drives cascade depth; `gate.subagent_pattern` MODIFIES the cascade interpretation by specifying which of the 4 patterns the cascade should adopt. |
| Does the behaviour reuse an existing block's data shape? | **YES** — `gate` already carries cascade Literal sub-fields (`cascade_required: bool` + `cascade_min_layers: int` from v11.1.0 PV-04); adding `subagent_pattern: PatternVerdict` is the same Literal-as-sub-field pattern. |
| Does the behaviour add an orthogonal concern unrelated to existing blocks? | **NO** (marginal) — pattern selection is COUPLED to cascade requirement (a CASCADE_REQUIRED dispatch with subagent_pattern=AGENT_POOL_FORWARD is internally inconsistent). |
| Does the behaviour reference cross-block state? | **NO** — pattern selection is gate-block-local. |
| Is the new field always present together with an existing block? | **YES** — present together with the existing `gate.cascade_required` field. |
| Is the new field independently optional? | **YES** — but the bias is toward NEST when the data shape allows. |

**VERDICT: NEST under `gate.subagent_pattern`** (parallel to v11.1.0
PV-04 cascade NEST precedent at `gate.cascade_required` +
`gate.cascade_min_layers`). The canonical_order length stays at **17**.
A-2.4 multi-baseline byte test 32/32 GREEN unchanged because the new
sub-field is **absence-canonical** — legacy v11.0..v11.4 dispatches
with no `gate.subagent_pattern` pass byte-identically; the NEST
sub-field renders only when the v12.0.0+ helper populates it.

The v11.4.0 cycle adds NO schema fields. The schema NEST decision is
documented HERE for v12.0.0 SI-1 to inherit; this is "pre-staging,
not commitment" in the v11.1.0 retrospective L-1 sense.

### 7.2 — v12.0.0 cycle has 4 orthogonal graduation commitments

v12.0.0 carries FOUR orthogonal graduation commitments, each
requiring its own SI-1 evaluation:

* **D-1 (v11.1.0 retrospective §3)** — A-7 STRICT promotion:
  `validate_cascade_gate_fields` raises `CascadeViolationError`;
  `audit_layer_usage.py --strict` becomes default-ON. **Cross-couples
  with this cycle**: yes (v12.0.0 STRICT validation will check
  `cascade_required + subagent_pattern` consistency).
* **D-2 (v11.1.0 retrospective §3)** — `SHORTCUT_SIMPLE` retirement:
  `ShortcutVerdict` Literal removed; `DEVOLAFLOW_SIMPLE_SHORTCUT` env
  flag retires (8 → 7). **Cross-couples**: yes — `ShortcutVerdict`
  includes `"SHORTCUT_SIMPLE"` / `"NO_SHORTCUT"`; `PatternVerdict`
  includes `"INLINE"`. Both encode "don't cascade for SIMPLE/TRIVIAL";
  v12.0.0 D-2 retirement consolidates the overlap. The v11.4.0 helper
  deliberately introduces the NEW `PatternVerdict` Literal so D-2 can
  retire `ShortcutVerdict` cleanly.
* **D-5 (v11.1.0 retrospective §3)** — CHANGELOG CI lint per-commit
  walker. **Cross-couples**: NO (orthogonal). Listed for completeness.
* **NEW v11.4.0 PREP commitment** — Subagent-pattern selection:
  `gate.subagent_pattern` schema NEST + helper wiring at L0/L1/L2
  dispatch sites + W-24 STRICT promotion (currently reference-only at
  v11.4.0; v12.0.0 STRICT-ON makes helper consultation MANDATORY for
  non-trivial wave dispatch).

### 7.3 — Pre-staging recommendations

Three recommendations v12.0.0 SI-1 should inherit:

1. **2-stage decomposition** (v11.1.0 retrospective L-3) — v12.0.0
   PV-04: S01 schema NEST + helper-wiring + tests in parallel; S02
   W-24 STRICT promotion + audit ratchet sequential.
2. **D-1 + new commitment cross-couple tests** — extend
   `tests/test_cascade_enforcement.py` with a NEW
   `TestCascadePatternConsistency` class (~5-7 tests) pinning the
   `cascade_required + subagent_pattern` consistency check.
3. **D-2 + new commitment Literal-overlap retirement** — specify the
   `ShortcutVerdict` migration: `DeprecationWarning` for one cycle,
   removal at v12.1.0. v11.4.0 does NOT touch
   `change_activation.py::ShortcutVerdict`.

## §8 — Activation Classifier Surface

`src/devolaflow/skills/subagent_pattern.py` — a pure-function module
mirroring `src/devolaflow/skills/grill_mode.py` (per §10.2 of
grill-mode.md) and `src/devolaflow/skills/change_activation.py` (per
A-6.1).

### 8.1 — Public type aliases

```python
PatternVerdict = Literal["INLINE", "FAN_OUT", "AGENT_POOL_FORWARD", "TEAMS_FORBIDDEN"]
ModelTier = Literal["small", "balanced", "frontier"]
```

Four `PatternVerdict` + three `ModelTier` values **ARE the public
contract** — operators rely on the literal strings; adding, removing,
or renaming any value is a release blocker requiring a CHANGELOG
`### Operator-visible behaviour change` entry. 1:1 correspondence to
the four philschmid patterns:

| Literal | Pattern | DevolaFlow status |
|---|---|---|
| `INLINE` | Pattern 1 (Inline Tool sync) | Native |
| `FAN_OUT` | Pattern 2 (Fan-Out) | Native |
| `AGENT_POOL_FORWARD` | Pattern 3 (Agent Pool) | Forward-compat reference (§5) |
| `TEAMS_FORBIDDEN` | Pattern 4 (Teams) | Permanently forbidden (§6) |

### 8.2 — The five public APIs

#### `select_pattern`

```python
def select_pattern(
    complexity: Literal["TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"],
    model_tier: ModelTier,
    task_count: int,
    parallel_independence: bool,
    persistent_state_needed: bool = False,
) -> PatternVerdict: ...
```

Pattern-selection classifier. Returns one of `INLINE` / `FAN_OUT` /
`AGENT_POOL_FORWARD` per the §3.2 decision rule. **Never returns
`TEAMS_FORBIDDEN`** — that verdict is reserved for
`forbidden_pattern_rationale`. Pure function (no I/O, no time
dependence, no random sampling).

#### `validate_inputs`

```python
def validate_inputs(complexity: str, model_tier: str, task_count: int) -> None: ...
```

Input validation. Raises `ValueError` with verbatim messages on
invalid inputs (`task_count < 1`, complexity / model_tier outside
their Literals). Per S-5, invalid inputs MUST surface as explicit
errors. `select_pattern` calls `validate_inputs` internally before
applying the decision rule.

#### `forbidden_pattern_rationale`

```python
def forbidden_pattern_rationale(pattern: PatternVerdict) -> str | None: ...
```

Operator-education path. Returns a structured rationale string for
forbidden verdicts (currently only `TEAMS_FORBIDDEN`); returns `None`
for adopt / forward-compat verdicts. The rationale cites §6 + the
verbatim P5 quote from `repo-governance.mdc` §A-1 P5 so callers
asking "should I use Teams?" receive the structured P5 explanation
rather than a bare rejection. Pure (no I/O, no env-var read); the
rationale text is part of the public contract.

### 8.3 — R5 strict design

The module mirrors `change_activation.py` + `grill_mode.py` design
constraints verbatim (per A-6.1):

* **Pure functions, zero filesystem I/O at import time** — no
  `pathlib.Path.exists()`, no `open()`, no `os.environ` reads at
  module body level.
* **R5 strict default-OFF** — no env-var read; no companion runtime
  probe. Returns `INLINE` (the conservative default) for ambiguous
  inputs falling through the §3.2 Pattern-3 branch without all
  conditions satisfied.
* **Four verdict values are the public contract** — changing any is a
  release blocker.
* **No silent failures (S-5)** — invalid inputs raise
  `TypeError` / `ValueError` via `validate_inputs`; never silent
  coercion.

## §9 — R5 Strict Default-OFF Discipline

Only the **helper-API invocation pattern** is default-active in
v11.4.0. There is no env-flag activation surface, no ambient
behavioural change, and no auto-population of any dispatch field.

### 9.1 — No new env flag (W-20 reuse-first preservation)

Subagent-pattern selection introduces **NO new `DEVOLAFLOW_*`
environment variable**. Activation is purely at the Python helper-API
surface — callers explicitly invoke `select_pattern(...)` from
L0 / L1 / L2 dispatch sites. W-20 is satisfied by NOT introducing a
flag at all rather than by reusing an existing one (pattern selection
is a helper-API concern, not an env-flag-activated runtime surface).
Env-flag count remains at **8** per the v11.3.0 baseline — mirrors
the W-22.4 grill-mode preservation pattern verbatim.

### 9.2 — Conservative default for ambiguous inputs

The §3.2 decision rule's final `else` returns `INLINE` for any input
not matching Pattern-3 or Pattern-2 conditions, making `INLINE` the
**conservative default** (the v11.x baseline single-L3 dispatch via
the existing `Task` tool). Dispatchers calling `select_pattern` with
ambiguous inputs never get a behavioural surprise.

### 9.3 — No auto-activation; callers explicitly invoke

There is no lifecycle hook, no pre-dispatch interceptor, and no
implicit middleware calling `select_pattern` on the dispatcher's
behalf at v11.4.0. The helper is invoked **only when the dispatcher
chooses to consult it**. v12.0.0+ may add an explicit lifecycle hook
(per §7.3 recommendation 2); v11.4.0 keeps the surface minimal so
operators opt in incrementally.

The v11.4.0 helper is **byte-identical no-op when not called** —
importing performs no I/O (per §8.3); not calling any public function
performs no work. `tests/test_subagent_patterns.py` includes a
`test_subagent_pattern_module_zero_io_at_import` assertion pinning
this (mirrors
`tests/test_grill_mode.py::test_grill_mode_disabled_is_byte_identical_noop`).

## §10 — Cross-References

### 10.1 — SKILL.md sections (lands in Wave 2)

* `## Wave Coordination Modes` — gets a 2-3 line cross-reference
  pointer to this reference (gap analysis P1.4 Edit 1).
* `## Reference Navigation Guide` Tier-2 sub-table — adds 1 NEW
  alphabetically-positioned row for `references/subagent-patterns.md`
  (gap analysis P1.4 Edit 2).

Both edits land in Wave 2; this reference does NOT modify SKILL.md.

### 10.2 — Source files (Python API)

`src/devolaflow/skills/subagent_pattern.py` (owned by W1.T1; this
reference does NOT author the module) exposes exactly five public
surfaces — the 2 Literal type aliases + 3 functions:

* `PatternVerdict` — Literal type alias; 4-valued public contract
  (`INLINE` / `FAN_OUT` / `AGENT_POOL_FORWARD` / `TEAMS_FORBIDDEN`).
* `ModelTier` — Literal type alias; 3-valued public contract
  (`small` / `balanced` / `frontier`).
* `select_pattern` — canonical §3.2 decision-rule entry point.
* `validate_inputs` — S-5 explicit-error path; raises `ValueError` on
  invalid inputs.
* `forbidden_pattern_rationale` — operator-education path returning a
  structured P5 rationale string for `TEAMS_FORBIDDEN`; returns `None`
  for adopt / forward-compat verdicts.

Design-pattern templates: `src/devolaflow/skills/change_activation.py`
(A-6.1; Literal-as-public-contract discipline) and
`src/devolaflow/skills/grill_mode.py` (zero-IO-at-import discipline +
`test_*_disabled_is_byte_identical_noop` assertion shape).

### 10.3 — Companion references

* `references/execution-protocol.md` §7.3 — v7.x
  anthropic-coordination-blog mapping reframed here through a
  subagent-lifecycle lens (§1.2); §12 `change-driven` workflow + §13
  `dispatch_wave_tasks(...)` are the canonical L2-wave-dispatch +
  convergence-loop surfaces.
* `references/grill-mode.md` — HUMAN-facing interview pattern;
  orthogonal axis (§1.1).
* `references/agent-hierarchy.md` — §3 anchors the 4-layer hierarchy;
  §5 anchors the wave constraints (max 5 tasks, disjoint owned files).
* `references/agent-workspace.md` — per-change `.local/.agent/active/<id>/`
  contract that the Pattern 3 fallback workaround relies on (§5.2).
* `references/plan-mode-enforcement.md` — PLAN MODE contract;
  composes freely with subagent-pattern selection (plan-time vs
  dispatch-time concerns).

### 10.4 — Rules

* **W-24 — Subagent Pattern Selection** (forward reference; lands in
  Wave 2 via `.rules/workflow.mdc` + `make compile-rules`). Codifies
  the §3 selection rule + the §5 Pattern 3 forward-compat policy +
  the §6 Pattern 4 P5 rationale + the §9 W-20 env-flag-reuse
  preservation. Includes sub-rule W-24.1 mirroring W-22.4.
* **W-22 — Grill Mode Activation Contract** (v11.3.0) —
  authoring-pattern template for W-24.
* **A-7 — Cascade-Depth Invariant** (v11.1.0 PV-05) — assumed SOFT in
  v11.4.0; v12.0.0 D-1 STRICT promotion will check
  `cascade_required + subagent_pattern` consistency (§7.2).
* **W-20 — Env-Flag Reuse** (v9.0.0 PV-05) — satisfied by NOT
  introducing a flag at all (§9.1).
* **W-21 — Soul-Set Freeze** (v9.0.0 PV-07) — NO S-11 proposed; W-24
  lands at Workflow per the Soul-vs-Architecture decision rule.

### 10.5 — Schemas

**None at v11.4.0.** NO new dispatch schema fields (gap analysis §5
R-5); `canonical_order` stays at 17 per A-2.4; multi-baseline byte
test (`tests/test_layout_invariant_multi_baseline.py`) remains 32/32
GREEN. v12.0.0+ schema NEST under `gate.subagent_pattern` is
pre-staged in §7.1; A-2.1 frozen prefix preserved across the
v11.4.0 → v12.0.0 transition.

### 10.6 — Testing surface

* `tests/test_subagent_patterns.py` (owned by W1.T1) — pins all 5
  public `subagent_pattern.py` surfaces + R5-strict zero-IO
  assertion + §3.2 decision-rule spot-checks.
* `tests/test_no_ghost_features.py::test_v11_4_0_new_surfaces_have_coverage`
  (Wave 2) — pins this reference's `# Subagent Patterns` first-line +
  `tier: 2` frontmatter + AST function symbols + §6 P5-Forbidden anchor.

### 10.7 — External

* DevolaFlow / EvoBench: `https://github.com/YoRHa-Agents/DevolaFlow`
* NineS: `https://github.com/YoRHa-Agents/NineS`
* Upstream philschmid article (2026 4-pattern taxonomy):
  `https://www.philschmid.de/subagent-patterns-2026`
* Earlier philschmid post (referenced by article):
  `https://www.philschmid.de/the-rise-of-subagents`
* Anthropic coordination patterns blog (referenced by
  `references/execution-protocol.md` §7.3 baseline): registered as
  `anthropic-coordination-blog` (relevance=5) in
  `workflow-system/agent/knowledge/reference-dependencies.yaml`.

## §11 — Anti-Patterns + Common Mistakes

Concrete operator-friction examples + corrections. Each entry follows
the grill-mode.md §12 format: anti-pattern statement → why it fails →
correction.

### 11.1 — Reaching for Pattern 3 for a single self-contained task

> **Anti-pattern.** L0 reads "the operator wants a research lookup
> followed by a code review" and concludes "this is multi-step;
> Pattern 3 Agent Pool".
> **Why it fails.** Pattern 3 is reserved for workflows that NEED
> persistent per-agent conversation history across turns. A research
> lookup feeding a code review is two single-task dispatches with a
> handoff artifact between them — Pattern 1 INLINE is sufficient.
> **Correction.** Set `persistent_state_needed=False` and let
> `select_pattern` return `INLINE`. The handoff artifact (e.g., the
> research report) is the canonical inter-task communication channel
> per P5; conversation history is not required.

### 11.2 — Reaching for Pattern 4 because the workflow has 4 specialists

> **Anti-pattern.** L0 reads "the workflow has a planner, an
> implementer, a reviewer, and a tester" and concludes "this is 4
> specialists coordinating; Pattern 4 Teams".
> **Why it fails.** Pattern 4 requires agents to message each other
> directly without going through the dispatcher — which P5 forbids
> permanently (§6). The workflow as described needs role
> specialization, not peer messaging.
> **Correction.** Use Pattern 2 Fan-Out (parallel waves of L3 tasks
> with disjoint owned files) for the parallelizable portions. Use
> Pattern 1 INLINE (sequential L3 dispatches with handoff artifacts)
> for the dependent portions. Consult `forbidden_pattern_rationale("TEAMS_FORBIDDEN")`
> for the verbatim P5 explanation if the operator asks why Pattern 4
> is off the table.

### 11.3 — Forgetting to set `persistent_state_needed=True` for a multi-step research workflow

> **Anti-pattern.** A multi-step research workflow with iterative
> fact-checking is dispatched with `persistent_state_needed=False` (the
> default). `select_pattern` returns `INLINE` and the workflow runs
> as a single L3 dispatch; the iterative fact-checking is lost.
> **Why it fails.** The default is conservative (single L3 dispatch);
> opting into persistent multi-agent semantics requires the explicit
> flag. The helper cannot infer "the workflow needs persistence" from
> the other inputs.
> **Correction.** Set `persistent_state_needed=True` explicitly. The
> helper will return `AGENT_POOL_FORWARD` (forward-compat-only at
> v11.4.0) and the operator falls back to the change-driven workflow's
> `apply ↔ verify` convergence loop per §5.2 — which is functionally
> equivalent for most multi-step research workflows.

### 11.4 — Confusing subagent-patterns with grill-mode

> **Anti-pattern.** L0 enters "grill mode" when a wave-decomposition
> decision is needed, OR L0 invokes `select_pattern` when the operator
> says "stress-test the plan".
> **Why it fails.** Grill mode is HUMAN-facing (operator interview);
> subagent-patterns is AGENT-to-AGENT (dispatch-time decision). The
> two solve different problems on different layers (§1.1).
> **Correction.** Use `classify_grill_intent` for operator-utterance
> classification. Use `select_pattern` for wave-decomposition. Both
> may be active in a single session — but they are never substitutes
> for each other.

### 11.5 — Using a small/balanced model for a Pattern 3 dispatch

> **Anti-pattern.** L0 has a Pattern-3-shaped workflow with
> `model_tier="balanced"`; operator pushes for Pattern 3 anyway.
> **Why it fails.** Per the §2.5 model-capability ladder verbatim
> quote, Pattern 3 needs a model that tracks multi-agent state across
> turns; smaller models "lose track of which agent has which context".
> **Correction.** The helper correctly downgrades to `INLINE` when
> `model_tier in ("small", "balanced")`. Verify `model_tier` matches
> the dispatcher's actual model; do not override the downgrade
> manually.

### 11.6 — Hand-populating `gate.subagent_pattern` in a v11.4.0 dispatch payload

> **Anti-pattern.** L0 / L1 / L2 dispatcher manually adds
> `gate.subagent_pattern` to a v11.4.0 dispatch payload to "future-proof
> for v12.0.0".
> **Why it fails.** v11.4.0 adds NO schema fields (§7.1; §10.5);
> `canonical_order` stays at 17. Hand-populating a v12.0.0+ field
> risks A-2.4 multi-baseline byte test failure and is a release
> blocker.
> **Correction.** Wait for v12.0.0 PV-04 schema NEST. v11.4.0 callers
> consume `select_pattern`'s return value at the dispatcher
> application level only; the verdict does NOT round-trip through the
> dispatch payload.

---

**End of `subagent-patterns.md`.** Canonical operating contract for
DevolaFlow's 4-pattern subagent taxonomy. Cross-load
`references/grill-mode.md` (per §1.1),
`references/execution-protocol.md` §7.3 (per §1.2), or
`references/agent-workspace.md` (per §5.2) as the active workflow
demands.
