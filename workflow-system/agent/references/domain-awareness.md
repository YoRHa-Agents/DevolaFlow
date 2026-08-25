---
id: domain-awareness
version: "11.3.0"
purpose: >
  Canonical CONTEXT.md authoring rules + ADR format + 3-condition ADR
  gate, providing the prompt-side reference for grill-mode's
  domain-glossary and ADR mechanics. Pairs with grill-mode.md (the
  operating contract) and W-23 (Domain Glossary Maintenance).
triggers:
  - "authoring or updating CONTEXT.md"
  - "authoring or updating CONTEXT-MAP.md"
  - "creating an ADR after a grill-mode decision"
  - "deciding whether a decision warrants an ADR"
  - "inferring single-context vs multi-context layout"
  - "distinguishing CONTEXT.md vocabulary from spec.md behaviour"
  - "format-checking a v11.3.0+ ADR before commit"
tier: 2
token_estimate: 4200
last_updated: "2026-08-25"
---

# Domain Awareness — CONTEXT.md and ADR Authoring Reference

> **Tier-2 reference** — load when an L0/L1 dispatcher needs to AUTHOR
> or UPDATE a `CONTEXT.md`, `CONTEXT-MAP.md`, or ADR file. Pairs with
> `grill-mode.md` (the interview / glossary-update operating contract)
> and W-23 (Domain Glossary Maintenance, lands in v11.3.0).

## §1 — When to Load

Load this reference when ANY of the following trigger surfaces fires:

| Trigger | Source | Effect |
|---|---|---|
| Grill-mode is active AND a fuzzy term has just been resolved during the interview | `grill-mode.md` §"Sharpen fuzzy language" + §"Update CONTEXT.md inline" | Force-load §3 (CONTEXT.md required structure) + §4 ("Be opinionated" rule) so the canonical term lands in the glossary in the upstream-mandated layout |
| Grill-mode is active AND a decision under discussion appears to qualify for an ADR | `src/devolaflow/skills/grill_mode.py::qualifies_as_adr` returns `(True, [])` | Force-load §8 (ADR format) — author the ADR per F-5 numbering + F-6 minimum body before continuing the interview |
| `infer_context_layout(repo_root)` returns `MULTI_CONTEXT` | `src/devolaflow/skills/grill_mode.py::infer_context_layout` | Force-load §6 (Single vs multi-context inference) — the dispatch must read `CONTEXT-MAP.md` first to pick the correct per-context glossary |
| `infer_context_layout(repo_root)` returns `NO_CONTEXT_YET` AND grill-mode just resolved its first term | same | Force-load §7 (Lazy file creation discipline) — the L0 MUST ASK before creating the root `CONTEXT.md` |
| Author or reviewer needs to disambiguate `CONTEXT.md` (vocabulary) vs `.local/memory/specs/<domain>/spec.md` (behaviour) | A-4 source-of-truth ADR | Force-load §2 (Domain glossary as agent-workspace artifact) — these surfaces never overlap |
| Author needs to format-check a v11.3.0+ ADR before commit | This reference + `grill-mode.md` §"ADR offer evaluation" | Force-load §8 (ADR format) + §9 (historical-`docs/cycle-archive/adr/` distinction) |

**NOT this file** when:

* The task is to scaffold a per-change `.local/.agent/active/<change-id>/spec.md` (delta) or to mutate the source-of-truth `.local/memory/specs/<domain>/spec.md` — those are A-4 surfaces; consult `references/agent-workspace.md` §7 (Source-of-Truth Specs) instead. CONTEXT.md and spec.md are orthogonal artifacts (see §2.2 below).
* The task is to populate the per-task dispatch payload's `behavioral_guidelines` field (canonical_order position 14 per A-2.4) — that field is per-task BEHAVIOUR modifier, not domain vocabulary; consult `references/behavioral-guidelines.md` instead (see §2.3).
* The task is repo-init bootstrap (mode=full P1/P3 phases) — the bootstrap interview is a different interview-protocol surface that scopes to AI tool / preference / build-command facts, not domain vocabulary. Consult `workflow-system/agent/knowledge/interview-protocol.md` (Tier-3 knowledge) instead. The grill-mode interview, by contrast, is a design-time stress-test of an in-flight plan against the project's domain language and documented decisions — see `references/grill-mode.md` §1 for the side-by-side distinction.

## §2 — Domain Glossary as Agent-Workspace Artifact

The domain glossary is a **machine-discoverable** artifact that a grill-mode interview reads first (to challenge an utterance against existing language) and writes-to last (to capture a freshly-resolved term). Two structural claims govern its placement in the repo:

### §2.1 — Canonical location

Per `CONTEXT-FORMAT.md` lines 49–77 (verbatim source) the upstream skill recognises two layout shapes:

* **Single context (most repos)**: One `CONTEXT.md` at the repo root.
* **Multiple contexts**: A `CONTEXT-MAP.md` at the repo root lists the contexts, where they live, and how they relate to each other; per-context glossaries live at `<context>/CONTEXT.md` (e.g. `src/ordering/CONTEXT.md`, `src/billing/CONTEXT.md`).

Both shapes obey the upstream **lazy-creation philosophy**:

> Create files lazily — only when you have something to write.

(verbatim from `https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs` SKILL.md line 46)

This invariant means a fresh repo carries NEITHER `CONTEXT.md` nor `CONTEXT-MAP.md` — the grill-mode interview that resolves the first term is the trigger that creates the first glossary file. Pre-creating empty glossary files at repo-init time is an anti-pattern (see §7.4).

### §2.2 — Distinction from `.local/memory/specs/<domain>/spec.md` (per A-4)

Source-of-truth specs at `.local/memory/specs/<domain>/spec.md` are **BEHAVIOURAL** — they describe what the system DOES (the operations the runtime supports, the side-effects of each operation, the invariants the runtime preserves). `CONTEXT.md` is **VOCABULARY** — it describes what the project's domain experts CALL THINGS (the canonical noun for a Customer / Order / Invoice; the relationships between those nouns; the example dialogue that pins their meaning).

These surfaces **DO NOT overlap**. A grill-mode interview that resolves a term ("when you say *account* you mean *Customer*, not *User*") writes to `CONTEXT.md`. A grill-mode interview that resolves a behaviour ("when an Order is placed the system MUST emit an `OrderPlaced` event") writes to the per-change `.local/.agent/active/<id>/spec.md` (which becomes a delta against the source-of-truth at archive time).

| Question the interview answers | Artifact the interview updates |
|---|---|
| "What do we **call** this?" | `CONTEXT.md` (vocabulary) |
| "What does the system **do** with it?" | `.local/.agent/active/<id>/spec.md` (delta) → archive-time merge into `.local/memory/specs/<domain>/spec.md` (behaviour) |

**A-4 — Source-of-Truth Spec Location ADR** (per `AGENTS.md` §A-4 / `.cursor/rules/repo-governance.mdc`): `.local/memory/specs/<domain>/spec.md` is the source-of-truth for current system behaviour. Per-change `.local/.agent/active/<id>/spec.md` files contain DELTAS (ADDED/MODIFIED/REMOVED Requirements) relative to source-of-truth. Source-of-truth is mutated ONLY at archive time, after the gate has PASSED (W-3 / SI-3 composite ≥ 8.5 for minor changes, ≥ 9.0 for major). The full A-4 contract — including the `mergeability_check` + `propose_merge` mechanics that gate archive-time mutations — is documented in `references/agent-workspace.md` §7 (Source-of-Truth Specs).

**Why the strict separation matters.** A glossary that mixes behaviour with
vocabulary becomes a "code glossary" that drifts from the running system.
A spec.md that mixes vocabulary with behaviour is harder for L0/L1/L2 to
scan. Each artifact keeps one concern and one update cadence.

### §2.3 — Distinction from L0 dispatch's `behavioral_guidelines` field

`behavioral_guidelines` is a top-level dispatch-payload field at canonical_order **position 14** per A-2.4 (the multi-baseline byte test pins the v8.0.0 P-08 baseline at position 14). It carries per-task BEHAVIOUR modifiers (BG-001 `think_first`, BG-002 `simplicity_check`, BG-003 `surgical_scope`, BG-004 `goal_loop` — see `references/behavioral-guidelines.md` for the full BG-001..BG-004 spec).

This field is **NOT** a domain vocabulary surface. It carries booleans and
scope levels that nudge an L2 Task's working style for one dispatch. A
grill-mode interview that resolves a term writes to `CONTEXT.md`, never to
`behavioral_guidelines`.

| Surface | Scope | Lifetime | Concern |
|---|---|---|---|
| `CONTEXT.md` | repo (or per-context) | rate-of-domain-language-refinement | vocabulary |
| `.local/memory/specs/<domain>/spec.md` (A-4) | repo (per domain) | rate-of-runtime-change | behaviour |
| `behavioral_guidelines` dispatch field (position 14) | per-task | single-dispatch | working-style modifier |

The three surfaces are independently optional. A repo MAY have a populated `CONTEXT.md` with no source-of-truth specs (early-stage repo whose runtime is still being designed). It MAY have populated source-of-truth specs with no `CONTEXT.md` (late-stage repo whose vocabulary is uncontested). And every dispatch payload may carry `behavioral_guidelines` regardless of either glossary state.

## §3 — CONTEXT.md Required Structure (VERBATIM from CONTEXT-FORMAT.md)

The upstream skill mandates 4 mandatory sections in every `CONTEXT.md`. The structure below is copied verbatim from `CONTEXT-FORMAT.md` lines 1–37.

```md
# {Context Name}

{One or two sentence description of what this context is and why it exists.}

## Language

**Order**:
{A concise description of the term}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account

## Relationships

- An **Order** produces one or more **Invoices**
- An **Invoice** belongs to exactly one **Customer**

## Example dialogue

> **Dev:** "When a **Customer** places an **Order**, do we create the **Invoice** immediately?"
> **Domain expert:** "No — an **Invoice** is only generated once a **Fulfillment** is confirmed."

## Flagged ambiguities

- "account" was used to mean both **Customer** and **User** — resolved: these are distinct concepts.
```

**The 4 mandatory section headers** (in order):

1. `## Language` — one entry per canonical term, bolded term name, single-sentence definition, optional `_Avoid_` aliases line.
2. `## Relationships` — bullet list, bold term names, cardinality where obvious.
3. `## Example dialogue` — blockquote conversation between a developer and a domain expert that demonstrates how the terms interact naturally.
4. `## Flagged ambiguities` — bullet list of terms that were used ambiguously in the past, with the resolution recorded inline.

The 3 sample terms (Order / Invoice / Customer) and their `_Avoid_` lines are
the canonical demonstration the upstream skill ships with. When authoring a
new `CONTEXT.md`, an L2 Task SHOULD use the structure while replacing the
sample terms with project-specific vocabulary.

The remaining 4 upstream rules (`CONTEXT-FORMAT.md` lines 41–48; verbatim) round out the structural contract:

* **Flag conflicts explicitly.** If a term is used ambiguously, call it out in "Flagged ambiguities" with a clear resolution.
* **Keep definitions tight.** One sentence max. Define what it IS, not what it does.
* **Show relationships.** Use bold term names and express cardinality where obvious.
* **Group terms under subheadings** when natural clusters emerge. If all terms belong to a single cohesive area, a flat list is fine.
* **Write an example dialogue.** A conversation between a dev and a domain expert that demonstrates how the terms interact naturally and clarifies boundaries between related concepts.

## §4 — "Be Opinionated" Rule (F-2)

Verbatim from `CONTEXT-FORMAT.md` line 41 (first bullet of the upstream "## Rules" section):

> **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others as aliases to avoid.

This is the F-2 format primitive (per the historical v11.3.0 gap analysis).
The glossary is opinionated by contract: it picks one canonical term and
lists the others under `_Avoid_`. Downstream L2 Tasks then have a
deterministic substring to match.

### §4.1 — Worked example

Suppose a `CONTEXT.md` carries the entry:

```md
**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account
```

When L0 drafts a plan containing "the buyer should receive an email",
`detect_fuzzy_terms(plan_text, glossary)` returns a `FuzzyTerm` for the
Avoid-listed alias. L0 SHOULD propose "Customer" through
`propose_canonical_term`, which returns the canonical term and triggering
`_Avoid_` line.

The agent's surface response: *"You wrote 'the buyer should receive an email'. The glossary lists 'buyer' as an alias to avoid; the canonical term is 'Customer'. Do you mean Customer here, or is 'buyer' a distinct concept that needs its own glossary entry?"*

### §4.2 — Tie-breaking

When two candidate canonical terms appear equally common in the project's natural-language usage, prefer the one that has **fewer overload risks** — i.e. the one whose meaning is least likely to collide with an unrelated concept elsewhere in the codebase.

| Candidate pair | Verdict | Rationale |
|---|---|---|
| `Customer` vs `Account` | Pick `Customer` | `Account` overloads with auth/`User` concepts; `Customer` carries less semantic baggage. |
| `Order` vs `Purchase` | Pick `Order` (per the upstream sample) | `Purchase` overloads with the verb form (an action) vs the noun (an entity). |
| `Invoice` vs `Bill` | Pick `Invoice` (per the upstream sample) | `Bill` overloads with legislative / utility-bill colloquialisms. |
| `Fulfillment` vs `Shipment` | Pick `Fulfillment` (per the upstream multi-context map sample) | `Shipment` is a sub-concept (one event in a fulfillment lifecycle); `Fulfillment` is the bounded context. |

The tie-breaker is a heuristic, not a contract — when domain experts feel strongly that `Account` is the right canonical noun for their project (e.g. a B2B SaaS where `Account` is the legal-contract entity and `Customer` is the human contact within), the human judgment wins. The heuristic exists to break stalemates where the operator is genuinely uncertain.

## §5 — "Only Project-Specific" Rule (F-3)

Verbatim from `CONTEXT-FORMAT.md` line 45 (the fifth bullet of the upstream "## Rules" section):

> **Only include terms specific to this project's context.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the project uses them extensively. Before adding a term, ask: is this a concept unique to this context, or a general programming concept? Only the former belongs.

This is the F-3 format primitive. The glossary is a **project-domain artifact**, not a code glossary. A general programming concept (HTTP timeout, generic error type, debounce pattern) is documented in the codebase's API surface or in language documentation — never in `CONTEXT.md`.

### §5.1 — Decision rule

Before adding a term, the L0 (or grill-mode interviewer) asks:

> *"Is this a concept unique to THIS project's domain, or a general programming concept?"*

Only the former belongs. The decision rule is binary and the answer is usually obvious within ~3 seconds. When the answer is genuinely ambiguous, the interviewer SHOULD probe with a follow-up question — *"Would a developer on a totally different project, with no context about ours, also need to use this term in this exact way?"* — and skip the entry if the answer is yes.

### §5.2 — Examples of what BELONGS

* **Domain entities** — the nouns at the heart of the project's business model. Examples: `Customer`, `Order`, `Invoice`, `Fulfillment`, `Shipment`, `Subscription`, `Tenant`, `Workspace`, `Pipeline`.
* **Domain events** — the verbs (or past-tense noun forms) that domain experts use when describing state transitions. Examples: `OrderPlaced`, `ShipmentDispatched`, `InvoiceGenerated`, `SubscriptionRenewed`, `TenantOnboarded`.
* **Project-specific units** — types whose semantics are project-defined rather than language-defined. Examples: `CustomerId` (a brand on a uuid that means "this is a customer"), a `Money` type when it carries project-specific rounding/currency rules, a `Cadence` type when it has project-specific weekly/monthly semantics.
* **Bounded-context names** in a multi-context layout (per §6) — `Ordering`, `Billing`, `Fulfillment`, `Notifications`, `Catalog`. These name the bounded contexts themselves and live in `CONTEXT-MAP.md` (with per-context detail in `<context>/CONTEXT.md`).

### §5.3 — Examples of what DOES NOT BELONG

* **General HTTP/network concepts** — timeout, retry-after, backoff, connection-pooling, rate-limit. These are infrastructure concepts that every web project shares.
* **Generic error types** — `ValueError`, `TypeError`, `IOError`, `TimeoutError`, generic `ApplicationError`. Document these in the codebase's exception hierarchy, not in the glossary.
* **Common utility patterns** — debounce, throttle, memoize, lazy-init, observer, factory, singleton. These are language/library patterns whose meaning is project-independent.
* **Language keywords / built-ins** — `async`, `await`, `Promise`, `Future`, `lambda`, `closure`. Glossing these is glossing the language.
* **Build / tooling vocabulary** — `pytest`, `ruff`, `pyproject.toml`, `Makefile`, `Dockerfile`. These are tooling concepts; document them in a CONTRIBUTING.md, not in the domain glossary.

### §5.4 — Why this matters

Two reinforcing reasons:

1. **Operator scan-ability.** A `CONTEXT.md` that an L0 dispatcher (or human reviewer) can scan in **<60 seconds at session start** stays useful across many sessions. A glossary that sprawls into general-programming-concept territory becomes a 5K-token document that nobody scans cover-to-cover; the resulting agent reasoning treats the glossary as background noise rather than a binding contract.
2. **Drift toward `code glossary`.** A glossary that documents `ValueError` semantics is implicitly trying to do what `spec.md` does — describe the system's behavioural contracts. When `CONTEXT.md` and `spec.md` start to overlap (per §2.2), both surfaces drift: glossary updates lag the spec because operators forget to mirror them; spec updates leak into glossary because the runtime keeps adding error types. Keeping CONTEXT.md tight is the only stable equilibrium.

## §6 — Single vs Multi-Context Inference (F-4)

Verbatim from `CONTEXT-FORMAT.md` lines 49–77 (the upstream "## Single vs multi-context repos" section):

> **Single context (most repos):** One `CONTEXT.md` at the repo root.
>
> **Multiple contexts:** A `CONTEXT-MAP.md` at the repo root lists the contexts, where they live, and how they relate to each other:
>
> ```md
> # Context Map
>
> ## Contexts
>
> - [Ordering](./src/ordering/CONTEXT.md) — receives and tracks customer orders
> - [Billing](./src/billing/CONTEXT.md) — generates invoices and processes payments
> - [Fulfillment](./src/fulfillment/CONTEXT.md) — manages warehouse picking and shipping
>
> ## Relationships
>
> - **Ordering → Fulfillment**: Ordering emits `OrderPlaced` events; Fulfillment consumes them to start picking
> - **Fulfillment → Billing**: Fulfillment emits `ShipmentDispatched` events; Billing consumes them to generate invoices
> - **Ordering ↔ Billing**: Shared types for `CustomerId` and `Money`
> ```
>
> The skill infers which structure applies:
>
> - If `CONTEXT-MAP.md` exists, read it to find contexts
> - If only a root `CONTEXT.md` exists, single context
> - If neither exists, create a root `CONTEXT.md` lazily when the first term is resolved
>
> When multiple contexts exist, infer which one the current topic relates to. If unclear, ask.

### §6.1 — The inference rule

The 3-line inference rule above is the F-4 format primitive (per gap analysis §2.3). It is reproduced verbatim because every implementing call-site MUST encode the same logic in the same order — `CONTEXT-MAP.md` first (multi-context wins when present), `CONTEXT.md` second (single-context default), neither third (lazy creation).

The order matters: a repo that carries BOTH `CONTEXT-MAP.md` AND a root-level `CONTEXT.md` is multi-context (the map wins; the root `CONTEXT.md` if present is treated as a "system-wide vocabulary" supplement to the per-context glossaries). A repo that carries no marker is `NO_CONTEXT_YET` regardless of how many files in the tree are named `CONTEXT.md` — the inference is rooted at the repo root only.

### §6.2 — The `infer_context_layout(repo_root)` pure function

The 3-line inference rule is codified in `src/devolaflow/skills/grill_mode.py::infer_context_layout` (a pure function — read-only filesystem probe; no IO outside the `repo_root` subtree; no subprocess). The function returns one of:

| Return value | Trigger condition | Caller behaviour |
|---|---|---|
| `SINGLE_CONTEXT` | only `<repo_root>/CONTEXT.md` exists at root level | read the root glossary; treat the whole repo as one bounded context |
| `MULTI_CONTEXT` | `<repo_root>/CONTEXT-MAP.md` exists at root level | read the map first to enumerate contexts; per-topic dispatches load the relevant `<context>/CONTEXT.md` |
| `NO_CONTEXT_YET` | neither file exists at root level | the next resolved-term event MUST trigger lazy creation per §7 — the L0 ASKS the operator before writing |

The 3-valued return contract parallels `change_activation.activation_verdict()` (per A-6.1) — both are pure-function classifiers whose 3-string output is the sole public API surface. Operators rely on the literal string values (`"SINGLE_CONTEXT"` / `"MULTI_CONTEXT"` / `"NO_CONTEXT_YET"`) for downstream branching; renaming any value is a release blocker.

### §6.3 — Worked example: DevolaFlow's own repo

At v11.3.0 cut, DevolaFlow's own repo carries NEITHER `CONTEXT.md` NOR `CONTEXT-MAP.md` at the root. `infer_context_layout(<repo_root>)` returns `NO_CONTEXT_YET`. This is the **correct default** — DevolaFlow has not yet been through a grill-mode interview that resolved a domain term, so no glossary file has been lazily created.

The first grill-mode session held against DevolaFlow that resolves a term (for example: *"when we say 'dispatcher' do we mean the L0 Project Agent, or the lifecycle hook chain dispatcher in `src/devolaflow/lifecycle/dispatcher.py`?"* — both are real DevolaFlow concepts that deserve disambiguation) will trigger §7 lazy creation: the L0 ASKS the operator *"Should I create `CONTEXT.md` at the repo root and record this term?"*, and on consent writes the file with a single `## Language` entry.

## §7 — Lazy File Creation Discipline

Verbatim from `https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs` SKILL.md line 46:

> Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed.

This is the operating discipline that ties §6 (inference) to §7 + §8 (creation). It manifests as 4 sub-rules:

### §7.1 — The "first term resolved" trigger

No `CONTEXT.md` (single-context) or `CONTEXT-MAP.md` (multi-context) file exists until the FIRST term is canonicalised in a grill-mode interview. The L0 (or grill-mode interviewer) does NOT pre-create empty glossary files at session start, at repo-init time, or at workflow-template scaffold time. Empty glossary files are an anti-pattern (see §7.4).

The trigger event is precise: a fuzzy term has been **resolved** — i.e. the operator and the interviewer have agreed on a canonical noun, an `_Avoid_` aliases list (possibly empty), and a one-sentence definition. Resolution-in-progress (the interviewer has proposed a canonical term but the operator has not confirmed) is NOT a trigger; the interviewer must wait for confirmation before creating the file.

### §7.2 — The "first ADR needed" trigger

No `docs/adr/` directory exists until the FIRST decision passes the 3-condition ADR gate (per §8.5). The L0 does NOT pre-create the directory at session start, at repo-init time, or at workflow-template scaffold time. The first decision that passes the gate also creates the directory and the first ADR file (`docs/adr/0001-<slug>.md`) atomically.

The trigger event is precise: `qualifies_as_adr(decision)` returns `(True, [])`. A decision that returns `(False, missing)` for any non-empty `missing` list does NOT trigger creation — the interviewer EXPLICITLY skips the ADR offer (per §8.5 and `grill-mode.md` §"Offer ADRs sparingly").

### §7.3 — R5 strict default-OFF for auto-writes

Cross-reference: `grill-mode.md` §"R5 strict default-OFF for any auto-write side effects" (the v11.3.0 normative section that codifies the auto-write contract).

Lazy creation is **gated by explicit operator consent** every time. The L0 ASKS before creating any of:

* `CONTEXT.md` (root or per-context)
* `CONTEXT-MAP.md` (root)
* `docs/adr/` (directory)
* `docs/adr/<NNNN>-<slug>.md` (file)

Even when the env-flag `DEVOLAFLOW_AGENT_WORKSPACE=1` is set (which would normally enable auto-writes per A-6 / `references/agent-workspace.md` §"Default-OFF auto-write contract"), the grill-mode glossary + ADR creation surfaces remain ASK-first. This is intentional asymmetry: workspace folder scaffolding is a structural setup that the operator opts in to once, but glossary content + ADR content are project-domain artifacts that benefit from per-write confirmation.

### §7.4 — Anti-pattern: pre-creating empty glossary or ADR scaffolding

Pre-creating empty `CONTEXT.md` / empty `docs/adr/` at repo-init time is an **anti-pattern**:

* An empty `CONTEXT.md` lies — it asserts the repo HAS a glossary (`infer_context_layout` returns `SINGLE_CONTEXT` instead of `NO_CONTEXT_YET`), but the glossary is empty, so the F-2 "be opinionated" rule cannot fire and the F-3 "only project-specific" rule has nothing to filter.
* An empty `docs/adr/` directory implies the project has decisions worth recording but has not yet recorded any. A grill-mode interview that finds an empty ADR directory wastes time scanning it for the highest existing number (per §8.4) before realising the next number is 0001.

The repo-init workflow (per SKILL.md §"Repo-Init Pre-Dispatch Contract") creates 8 canonical paths: `.local/feedbacks/`, `.local/tasks/`, `.local/memory/`, `.local/index.md`, `.rules/compile-config.yaml`, `.local/.agent/active/`, `.local/.agent/handoff/`, `.local/.agent/archive/`. **Neither `CONTEXT.md` nor `docs/adr/` is in this list** — they remain absent until grill-mode populates them, which is the correct default per §7.1 and §7.2.

## §8 — ADR Format (VERBATIM from ADR-FORMAT.md)

The upstream skill's ADR format is a deliberately minimalist spec — 1–3 sentences body, 3 optional sections, sequential numbering. Full upstream source: `https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs` `ADR-FORMAT.md` (2,766 bytes).

### §8.1 — Location and numbering (verbatim)

Verbatim from `ADR-FORMAT.md` lines 3–5:

> ADRs live in `docs/adr/` and use sequential numbering: `0001-slug.md`, `0002-slug.md`, etc.
>
> Create the `docs/adr/` directory lazily — only when the first ADR is needed.

The numbering scheme is `<NNNN>-<slug>.md` where `<NNNN>` is a 4-digit zero-padded integer (`0001`, `0002`, `0003`, …) and `<slug>` is a kebab-case short title.

### §8.2 — Template (verbatim)

Verbatim from `ADR-FORMAT.md` lines 7–15:

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

That's it. **An ADR can be a single paragraph. The value is in recording *that* a decision was made and *why* — not in filling out sections.**

The 1–3-sentence body is the contract. An ADR longer than 3 sentences is not "more thorough" — it is **out of contract**. If the operator feels they need 4+ sentences, they should re-evaluate whether the decision actually qualifies (per §8.5) or whether the body is leaking into spec.md territory (behavioural detail belongs in `.local/memory/specs/<domain>/spec.md` per §2.2, not in an ADR).

### §8.3 — Optional sections (verbatim)

Verbatim from `ADR-FORMAT.md` lines 17–23:

> **Only include these when they add genuine value. Most ADRs won't need them.**
>
> * **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — useful when decisions are revisited
> * **Considered Options** — only when the rejected alternatives are worth remembering
> * **Consequences** — only when non-obvious downstream effects need to be called out

Three optional sections, each with its own narrow purpose:

1. **Status frontmatter** — for ADRs whose status changes over time. A `proposed` ADR is one that has been authored but not yet accepted; an `accepted` ADR is the steady state; a `deprecated` ADR is one whose decision has been reversed; a `superseded by ADR-NNNN` ADR is one whose decision has been replaced by a newer ADR (cross-referenced by ID). When a project never revisits its decisions, the Status frontmatter adds noise; when a project revises decisions every quarter, it is essential.
2. **Considered Options** — for ADRs whose rejected alternatives are likely to be re-proposed. Example: "We considered GraphQL and picked REST because of <reason>" — without this section a future engineer will propose GraphQL again in 6 months. When the rejected alternatives are obviously unsuitable (e.g. "we considered SQLite for our 10-billion-row workload"), the section adds noise.
3. **Consequences** — for ADRs whose downstream effects are non-obvious. Example: "Decision to make Customer data owned by the Customer context implies all other contexts MUST reference it by ID only — the implication is enforced at module-boundary review time" — capturing the implication once prevents it from being re-derived in every PR.

### §8.4 — Numbering (verbatim)

Verbatim from `ADR-FORMAT.md` line 27:

> Scan `docs/adr/` for the highest existing number and increment by one.

The numbering is a **scan, not a state machine** — there is no central counter. The next-number computation is `max(existing_numbers) + 1` where `existing_numbers` is the sorted set of `<NNNN>` prefixes in `docs/adr/`. The 4-digit zero-padding ensures sort-correct directory listing through ADR 9999 (which is more than enough headroom for any project).

When `docs/adr/` does not exist (per §7.2 lazy-creation), the next number is `0001`. When it exists but is empty (per the §7.4 anti-pattern), the next number is also `0001` — but the empty-directory state is itself a smell that the ADR-creating workflow should investigate.

### §8.5 — The 3-condition gate (verbatim)

Verbatim from `ADR-FORMAT.md` lines 27–37 (the `## When to offer an ADR` section):

> All three of these must be true:
>
> 1. **Hard to reverse** — the cost of changing your mind later is meaningful
> 2. **Surprising without context** — a future reader will look at the code and wonder "why on earth did they do it this way?"
> 3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons
>
> If a decision is easy to reverse, skip it — you'll just reverse it. If it's not surprising, nobody will wonder why. If there was no real alternative, there's nothing to record beyond "we did the obvious thing."

The gate is **conjunctive** — all 3 conditions must hold. A decision that meets 2 of 3 conditions does NOT qualify for an ADR; the operator skips it and moves on.

| Condition | Failure mode if ignored |
|---|---|
| Hard to reverse | The ADR is wasted — the decision will get reversed and the ADR becomes a liability instead of an asset (the next reader has to figure out which ADR is current). |
| Surprising without context | The ADR is wasted — nobody will read it because nobody will wonder why. |
| Real trade-off | The ADR is empty — the body is "we did the obvious thing", which is not worth recording. |

### §8.6 — The qualifying-decision matrix (verbatim)

Verbatim from `ADR-FORMAT.md` lines 39–47 (the `### What qualifies` sub-section):

> * **Architectural shape.** "We're using a monorepo." "The write model is event-sourced, the read model is projected into Postgres."
> * **Integration patterns between contexts.** "Ordering and Billing communicate via domain events, not synchronous HTTP."
> * **Technology choices that carry lock-in.** Database, message bus, auth provider, deployment target. Not every library — just the ones that would take a quarter to swap out.
> * **Boundary and scope decisions.** "Customer data is owned by the Customer context; other contexts reference it by ID only." The explicit no-s are as valuable as the yes-s.
> * **Deliberate deviations from the obvious path.** "We're using manual SQL instead of an ORM because X." Anything where a reasonable reader would assume the opposite. These stop the next engineer from "fixing" something that was deliberate.
> * **Constraints not visible in the code.** "We can't use AWS because of compliance requirements." "Response times must be under 200ms because of the partner API contract."
> * **Rejected alternatives when the rejection is non-obvious.** If you considered GraphQL and picked REST for subtle reasons, record it — otherwise someone will suggest GraphQL again in six months.

The 7 bullets above are the **qualifying-decision matrix** (per F-7 in gap analysis §2.3). Each bullet is a category of decision that frequently passes the §8.5 3-condition gate; the matrix is a mnemonic for the interviewer rather than an exhaustive enumeration. A decision that matches none of the 7 categories is unlikely to qualify; a decision that matches one or more SHOULD be checked against the §8.5 gate before authoring.

### §8.7 — The `qualifies_as_adr(decision)` pure function

The §8.5 + §8.6 mechanics are codified in `src/devolaflow/skills/grill_mode.py::qualifies_as_adr` (a pure function — no IO, no subprocess; the 3-condition check is a structural inspection of the `DecisionDescriptor` input). The function returns a tuple `(qualifies: bool, missing: list[AdrConditionName])` where:

* `qualifies` is `True` IFF all 3 conditions hold.
* `missing` is the (possibly empty) list of condition names that failed. The names are the literal strings `"hard_to_reverse"`, `"surprising_without_context"`, `"real_trade_off"` — chosen to mirror the 3 condition labels in §8.5 verbatim.

Example return values:

* `(True, [])` — all 3 conditions hold; offer the ADR (and trigger §7.2 lazy creation if `docs/adr/` does not yet exist).
* `(False, ["hard_to_reverse"])` — only 2 of 3 conditions hold; the decision is easy to reverse; skip the ADR per §8.5 ("you'll just reverse it").
* `(False, ["hard_to_reverse", "surprising_without_context"])` — only 1 of 3 conditions holds; the decision is reversible AND non-surprising; trivially skip.
* `(False, ["hard_to_reverse", "surprising_without_context", "real_trade_off"])` — none of the 3 conditions hold; this is "we did the obvious thing"; skip.

The 4-state truth table is exhaustive (2³ = 8 combinations; 1 of them returns `True`, the other 7 return `False` with a non-empty `missing` list). The function's signature is the binding contract for downstream callers; callers MUST surface the `missing` list to the operator (rather than silently dropping the ADR offer) so the operator understands which condition failed and can either argue the case or accept the skip.

## §9 — Distinction from Historical `docs/cycle-archive/adr/` Directory

Per `docs/cycle-archive/v11.3.0/v11.3.0_gap_analysis.md` §3.3 ("Format-primitive gap"):

DevolaFlow's existing `docs/cycle-archive/adr/` directory uses a `vN-ADR-NNN-slug.md` numbering scheme — for example `v9-ADR-007-rule-rebalancing-and-rollup.md`, `v9-ADR-004-lifecycle-wiring-and-s10.md`, `v9-ADR-002-cache-layout-governance-v2.md`. The version-prefix (`v9-`, `v10-`, `v11-`) ties each ADR to the cycle that authored it; the `ADR-NNN` is a 3-digit sequence within that cycle.

The format-primitives F-1..F-7 documented in this reference apply to **NEW v11.3.0+ ADRs only**. Historical ADRs are NOT retrofitted to the upstream `0001-slug.md` numbering — they remain under their version-prefixed scheme as cycle-internal design records.

| Category | Path | Numbering | Body length | Concern |
|---|---|---|---|---|
| Cycle-internal design records (historical, NOT retrofitted) | `.local/research/adr/vN-ADR-NNN-<slug>.md` | `vN-ADR-NNN-<slug>.md` | unbounded — these are full design narratives | DevolaFlow's own iteration history |
| New v11.3.0+ ADRs (project-decision records) | `docs/adr/<NNNN>-<slug>.md` | `<NNNN>-<slug>.md` (zero-padded 4-digit, no version prefix) | 1–3 sentences body per §8.2 | Project-domain decisions that emerge from grill-mode interviews |

Going forward:

* NEW ADRs that emerge from grill-mode interviews land under `docs/adr/<NNNN>-<slug>.md` per F-5. They carry the §8.2 minimum body (1–3 sentences) and the §8.3 optional sections only when warranted.
* Cycle-internal design records (the kind that capture the rationale for a multi-PV refactor, an ADR-driven schema change, a Soul-set-freeze deliberation) continue under `.local/research/adr/vN-ADR-NNN-<slug>.md`. These are NOT subject to the §8.5 3-condition gate — they are research artifacts, not project-domain decisions.

This split avoids disruption (no historical ADR has to move or change format) while introducing the cleaner upstream scheme for future grill-mode-driven ADRs. The two surfaces are deliberately orthogonal: a future cycle-internal `v11-ADR-NNN-<slug>.md` is published in `docs/cycle-archive/adr/`; a future grill-mode-driven `<NNNN>-<slug>.md` is published in `docs/adr/`.

The historical `docs/cycle-archive/adr/` directory exists at v11.3.0 cut and contains 10+ ADRs accumulated across the v8.x and v9.x cycles. Reviewers reading this reference for the first time should understand that "the ADR format documented in §8 above does not match the format of the historical ADRs in `docs/cycle-archive/adr/`" is **expected** and is the §3.3 gap-analysis decision rendered as repo state. Operators authoring NEW ADRs from a grill-mode interview should mechanically follow §8.1–§8.7; operators authoring NEW cycle-internal design records should follow whatever convention the in-flight cycle plan documents (typically: free-form prose, 100–500 lines, headed by an ADR ID like `v11-ADR-001`).

## §10 — Cross-References

The cross-reference layout below mirrors `references/plan-mode-enforcement.md` §9 — six sub-sections (companion / source / rules / schemas / testing / external) in fixed order so that L0/L1 dispatchers can jump to the surface they need without scanning the whole list.

### §10.1 — Companion reference

* `references/grill-mode.md` — the operating contract for grill-mode (one-question-at-a-time interview, codebase-first exploration, fuzzy-term sharpening, scenario probing, inline glossary updates, ADR offer evaluation, R5 strict default-OFF for auto-writes). This file (`domain-awareness.md`) is the **format companion**: when grill-mode RESOLVES a term or DECIDES an ADR-worthy issue, it consults this file for the layout rules.

### §10.2 — Source files (Python API)

* `src/devolaflow/skills/grill_mode.py` — the v11.3.0 pure-function module that codifies the activation + format mechanics. The 4 public functions referenced by this file:
  * `qualifies_as_adr(decision: DecisionDescriptor) -> tuple[bool, list[AdrConditionName]]` — the 3-condition gate of §8.5; see §8.7 for the truth-table.
  * `propose_canonical_term(candidate: str, glossary: dict[str, str]) -> CanonicalTermSuggestion` — the F-2 "be opinionated" rule of §4; takes a candidate term + the existing glossary and returns the canonical term suggestion (with the matched `_Avoid_` line as the trigger evidence).
  * `detect_fuzzy_terms(plan_text: str, glossary: dict[str, str]) -> list[FuzzyTerm]` — the §4.1 worked-example mechanism; scans a plan body for substrings matching any `_Avoid_` alias and returns one `FuzzyTerm` record per hit.
  * `infer_context_layout(repo_root: Path) -> ContextLayout` — the F-4 inference rule of §6.2; returns one of `SINGLE_CONTEXT` / `MULTI_CONTEXT` / `NO_CONTEXT_YET`.

### §10.3 — Rules

* **W-22 — Grill Mode Activation Contract** (lands in v11.3.0 alongside this file) — codifies the natural-language triggers for grill-mode, the parallel-orthogonal relationship with plan-mode, the R5 strict default-OFF for auto-writes, and the 3-condition ADR gate as a normative obligation when grill-mode is active.
* **W-23 — Domain Glossary Maintenance** (lands in v11.3.0 alongside this file) — codifies the lazy file-creation discipline (§7), the "Only project-specific" rule (§5), the "Be opinionated" rule (§4), and the composition with A-4 source-of-truth specs (§2.2).

W-22 and W-23 land at the **Workflow** rule layer (not Soul) per the W-21 Soul-set freeze at 10 entries. The grill-mode invariants are conditional + implementation-coupled — the same Soul-vs-Architecture-vs-Workflow decision pattern that landed A-7 at Architecture in v11.1.0 (per `v9-ADR-007 §"Soul-vs-Architecture decision-rule"`).

### §10.4 — Schemas

This reference does **not** introduce any new dispatch payload field. The dispatch-side `canonical_order` length stays at 17 entries per A-2.4; the multi-baseline byte test (32/32 GREEN at v11.1.x cut) is preserved unchanged. Per the A-2.3 NEST-vs-APPEND decision rule, any future grill-mode dispatch metadata SHOULD nest under the existing `behavioral_guidelines` block (canonical position 14) rather than appending a new top-level key.

### §10.5 — Testing

* `tests/test_domain_awareness.py` — this cycle's positive-substring pin per the v11.1.3 D-3 ghost-audit pattern. Asserts the 4 mandatory section headers (§3), the F-2 + F-3 verbatim phrases (§4 + §5), the §8.5 3-condition strings, the §8.1 lazy-creation phrase, and the §8.2 1–3-sentence body phrase.
* `tests/test_no_ghost_features.py::test_v11_3_0_new_surfaces_have_coverage` — the W-18 ghost-audit refresh that lands in Wave 2 of the v11.3.0 cycle. It pins the AST-level symbol existence for the 4 functions in `grill_mode.py` (per §10.2) AND the surface-level substring existence in this file + `grill-mode.md` + the v11.3.0 CHANGELOG entry.

### §10.6 — External

* DevolaFlow repository: `https://github.com/YoRHa-Agents/DevolaFlow` (per S-7 — local clone paths are operator-provided at runtime; never hardcoded in any agent-facing file).
* Upstream grill-with-docs skill (the verbatim source for §3, §4, §5, §6, §8): `https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs`. The 3 verbatim-source files copied into `docs/cycle-archive/v11.3.0/v11.3.0_grill_with_docs_source/` (`SKILL.md`, `CONTEXT-FORMAT.md`, `ADR-FORMAT.md`; 204 lines combined) are the in-repo cycle-research snapshot — they are NOT the source of truth (the upstream remote is) but they preserve the exact content this reference quotes from.
* Built-in evaluation authority: `python -m devolaflow.harness evaluate` (see W-2 / SI-2). Domain and grill evidence never requires an external evaluator.
