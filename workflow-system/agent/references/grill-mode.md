---
id: grill-mode
version: "11.3.0"
purpose: >
  Canonical operating contract for DevolaFlow's grill-mode behaviour:
  one-question-at-a-time interview discipline, codebase-first
  exploration, fuzzy-term sharpening, scenario probing, and the
  3-condition ADR gate that prevents ADR sprawl. Pairs with
  domain-awareness.md (CONTEXT.md and ADR format), W-22 (Grill Mode
  Activation Contract), and W-23 (Domain Glossary Maintenance).
tier: 2
token_estimate: 3200
last_updated: "2026-08-25"
---

# Grill Mode — Operating Contract

> **Tier-2 reference** — load when grill-mode triggers fire (explicit
> "grill" / "interview me" / "stress-test plan" / "challenge the plan" /
> "interrogate" / "sharpen terminology" / "sharpen the domain") OR when
> `classify_grill_intent` returns `GRILL_REQUESTED` / `GRILL_SUGGESTED`.
> SKILL.md §"Mode Awareness" carries the 1-paragraph summary; this file
> carries the full operating contract.

## §1 — When to Load

Three trigger surfaces feed grill-mode activation:

1. **Natural-language phrase from the prompt** — the operator says
   one of the verbatim phrases listed in §2.1. The activation
   classifier `devolaflow.skills.grill_mode.classify_grill_intent`
   returns `GRILL_REQUESTED` for these explicit triggers.
2. **`classify_grill_intent` SUGGESTED verdict** — softer phrases
   ("can you push back on this?", "what's wrong with this idea?")
   surface as `GRILL_SUGGESTED`. The L0 dispatcher MAY enter grill
   mode but SHOULD ask the operator to confirm before doing so.
3. **Operator slash command** — `/grill` (and aliases `/interview`,
   `/challenge`) MAY be wired into a host-specific shortcut. Slash-
   command activation is byte-identical to the REQUESTED path.

Grill mode is a **parallel, orthogonal** axis to PLAN MODE: both
modes can be active simultaneously, neither is a prerequisite for
the other. When the operator says "build a plan but grill me
first", the L0 enters BOTH modes concurrently — see §8.

Grill mode is **NOT** the same as the existing `interview-protocol.md`
(`workflow-system/agent/knowledge/interview-protocol.md`, Tier-3,
81 lines). That file scopes to the **repo-init bootstrap mode
only** — it codifies the interview an L2 Task runs when
scaffolding `.rules/` / `.local/memory/prefs.md` / skill bundles
for a fresh repo. Grill mode is a **plan-time / design-time**
stress test against an in-flight plan — it interviews the operator,
not the repo. The two surfaces never compose: repo-init runs once
at bootstrap; grill-mode interviews run any time an operator
invites adversarial questioning of an unfolding plan or spec
(gap analysis §3.1 row 1; risk R-11).

## §2 — Grill Mode Detection

### 2.1 Trigger taxonomy

`classify_grill_intent(message: str) -> GrillVerdict` returns one
of three literal strings:

| Verdict | Trigger phrases (case-insensitive substring) | Dispatcher behaviour |
|---|---|---|
| `GRILL_REQUESTED` | "grill me", "grill this", "grill the plan", "interview me", "stress-test the plan", "challenge the plan", "challenge this design", "interrogate this", "sharpen the terminology", "sharpen the domain", "/grill", "/interview", "/challenge" | Activate grill mode immediately; load this reference; begin §3 interview discipline. |
| `GRILL_SUGGESTED` | "push back on this", "what's wrong with this idea", "are these the right terms", "talk me through the assumptions", "challenge my thinking", "what am i missing" | Surface a confirmation prompt: "It sounds like you'd benefit from a grill-mode interview. Confirm to enter (yes/no)." Activate only on operator consent. |
| `NO_GRILL` | (default — no trigger phrase matched) | Standard dispatch; grill mode inactive; this reference is NOT loaded. |

The REQUESTED phrase list is the public contract — operators rely
on the literal strings. Adding a new REQUESTED phrase is an
operator-visible behaviour change requiring a CHANGELOG
`### Operator-visible behaviour change` entry.

### 2.2 Parallel-orthogonal relationship with PLAN MODE

Grill mode and PLAN MODE occupy independent axes:

| PLAN MODE | GRILL MODE | Resulting L0 behaviour |
|:-:|:-:|---|
| OFF | OFF | Standard AGENT MODE orchestration. |
| ON | OFF | PLAN MODE only (`references/plan-mode-enforcement.md` §3 plan template). |
| OFF | ON | Grill mode only — interview operator about unfolding intent without a plan template. |
| ON | ON | Both modes active. Grill the operator on AC + scope FIRST (§3 / §5), THEN write the plan template per `references/plan-mode-enforcement.md` §3. |

Neither mode is a prerequisite for the other. The plan template
inherits operator clarifications surfaced during grilling.

### 2.3 Companion env-var posture

**No new environment variable is introduced.** Grill-mode
activation is purely natural-language. The default-OFF posture is
preserved by the classifier itself: any prompt without a grill
trigger phrase returns `NO_GRILL`. This complies with W-20 reuse-
first env-flag policy (gap analysis §5 risk R-7). The R5 strict
default-OFF discipline is enforced at three layers: activation
(returns `NO_GRILL` for non-trigger inputs), read (`infer_context_
layout` is read-only), and write (the `grill_mode.py` module never
writes — see §9 for the auto-write consent contract).

## §3 — Interview Discipline (Primitive 1: One-Question-at-a-Time)

The first behavioural primitive — and the one most distinct from
DevolaFlow's existing surfaces — is asking **exactly one question
at a time** and **waiting for a real answer before continuing**.
Verbatim from upstream SKILL.md lines 7–9:

> Ask the questions one at a time, waiting for feedback on each
> question before continuing.

This is a **conversation-shape** discipline: the L0 in grill mode
treats the chat history as a tree of design decisions, walks it
depth-first, and never batches questions into a list the operator
must answer in one turn.

### 3.1 The walking-the-design-tree pattern

The L0 in grill mode:

1. Identifies the **root question** — the central ambiguity in
   the operator's stated intent ("you want to refactor billing;
   what changes — data model, API surface, or integrations?").
2. Asks the root + provides a recommended answer (§3.2). Waits.
3. From the operator's response, identifies the next-level
   ambiguity — typically a specific aspect of the resolved root.
4. Asks that question + recommended answer. Waits.
5. Continues until either the design tree is fully resolved or
   the operator explicitly halts ("OK, you have enough — let's
   plan").

Depth-first because surfacing every leaf-level ambiguity at the
root level overwhelms the operator and surfaces contradictions
out of order.

### 3.2 The recommended-answer obligation

The upstream skill obliges the L0 to propose an answer for every
question (upstream SKILL.md line 6):

> For each question, provide your recommended answer.

The recommended answer is NOT a guess — it is the L0's best
reading of operator intent, codebase, and loaded glossary
entries. Format: one-sentence proposal + one-sentence rationale.
Example:

> **L0:** Should partial cancellation reduce the **Order** total
> proportionally, or generate a separate refund **Invoice**?
> **Recommended:** generate a separate refund **Invoice** —
> consistent with `src/billing/invoice.py:42` (existing
> `Invoice.kind == "refund"` field).

The pattern serves three purposes: anchoring (operator critiques
rather than authoring), surfacing assumptions (rationale exposes
the L0's mental model), and disagreement detection (operator
correction surfaces contradictions in the L0's reasoning).

### 3.3 Wait-for-feedback discipline

"Waiting for feedback" means the L0 emits exactly one question
per turn and renders control back to the operator. The L0 does
NOT: emit a list of questions, speculate about the operator's
likely answer to a downstream question before the upstream
question is resolved, or continue interviewing the codebase for
the next question while the current question is open.

The wait is total: the L0 issues the question, then yields. There
is no `await_operator_response()` API; adherence is a behavioural
primitive codified in this reference and in W-22.

### 3.4 Anti-pattern: the question-batch dump

The most common operator-friction failure is the L0 emitting a
formatted list of 8 questions in one turn ("I have 8 questions:
1. Redis or in-memory? 2. Cache key shape? 3. TTL? …"). The dump
forces the operator to answer interleaved questions **out of
dependency order** — typically producing inconsistent answers
(e.g., answering #3 TTL before #1 backend choice; TTL semantics
differ between Redis and in-memory).

The corrected interview asks the cache-backend question first
with a recommended answer ("Redis — `src/cache.py:18` already
imports `redis-py`"), waits for the answer, THEN emits the next
question. Dependencies resolve in order; the operator's mental
model stays consistent across the chain.

## §4 — Codebase-First Exploration (Primitive 2)

The second primitive defers operator questions whenever the
answer is in the code. Verbatim from upstream SKILL.md line 11:

> If a question can be answered by exploring the codebase,
> explore the codebase instead.

Grill mode adds **normative urgency** to PLAN MODE's existing
read-permission contract: when an operator question is answerable
from source, the L0 MUST read first and propose the answer back,
not interrupt the operator with the question.

### 4.1 The L0 read-permission alignment

The L0 in grill mode inherits the AGENT MODE tool-permission
contract:

- **ALLOWED**: Read, Glob, Grep, SemanticSearch, TodoWrite.
- **DELEGATE**: Write, StrReplace, Shell (code/test/build),
  EditNotebook → spawn Task Agent.
- **Trivial exception**: single file, < 20 lines → P1 waived.

The grill-mode-specific addition is the **explore-before-ask
heuristic**: every candidate question is first checked against
"can I answer this by reading the code in < 30 seconds?". If
yes, read first; ask only if the read produced ambiguous
evidence.

### 4.2 Cross-reference with code (sub-primitive)

When the operator's verbal claim conflicts with what the source
actually does, the L0 SURFACES the contradiction (upstream
SKILL.md lines 61–64):

> When the user states how something works, check whether the
> code agrees. If you find a contradiction, surface it: "Your
> code cancels entire Orders, but you just said partial
> cancellation is possible — which is right?"

Three steps: (1) **restate the operator's claim verbatim** —
prevents repudiation of a paraphrase; (2) **cite the
contradicting code by repo-relative path + line** — forces the
conversation to a specific source location; (3) **ask which
side is correct** — the L0 does NOT propose a resolution at
this step; the operator decides whether the code is wrong (and
needs a code change) or the verbal claim was imprecise.

### 4.3 The explore-before-ask decision rule

| Operator claim / question | Codebase signal | L0 action |
|---|---|---|
| "How are expired sessions handled?" | `src/auth/session.py::expire_session()` called from `src/api/middleware.py:42` | READ both; propose "middleware calls `expire_session` when `last_active_at > 30 min`" — operator confirms. |
| "Do we cache user permissions?" | `Grep -r "permissions" src/` → 14 files; no cache imports | READ the 14 hits; REPORT "no in-source cache; every check hits DB" — operator confirms. |
| "Should the new module be `src/billing/` or `src/orders/`?" | no codebase signal (design decision) | DO NOT explore further; ASK with recommendation ("`src/billing/` — reads `Invoice`, writes `Refund`"). |

The heuristic reduces operator-facing latency on questions the
operator implicitly answered by writing the code. Operators
report it as "less interrogating" because the L0 only asks
design questions, not factual ones.

## §5 — Domain Language Sharpening (Primitives 6 & 7)

The fifth and sixth primitives address the most under-codified
operator-side failure mode in DevolaFlow's existing flow: vague
or overloaded verbal terms that the L0 should sharpen BEFORE the
plan template is authored (gap analysis §3.1 primitives 6 + 7,
both `❌ missing` in v11.1.3 baseline).

### 5.1 Fuzzy-term sharpening (Primitive 6)

Verbatim from upstream SKILL.md lines 53–55:

> When the user uses vague or overloaded terms, propose a precise
> canonical term. "You're saying 'account' — do you mean the
> Customer or the User? Those are different things."

The prompt-side codification is `propose_canonical_term`
(signature in §10). The function takes the candidate fuzzy term
and the loaded `CONTEXT.md` glossary, returns a
`CanonicalTermSuggestion` with the proposed precise term and a
list of alternative readings — or `None` when the candidate is
already unique.

Worked example:

> **Operator:** I want the **account** to receive an email when
> the **payment** fails.
> **L0 (grill mode):** "You're saying **account** — your
> `CONTEXT.md` defines two concepts: a **Customer** ('a person or
> organization that places orders') and a **User** ('a login
> identity in our auth system'). Do you mean Customer (email goes
> to the billing contact) or User (email goes to the logged-in
> identity)? **Recommended:** Customer — `src/billing/notify.py:12`
> routes payment-failure emails to `customer.billing_email`."

The L0 cites the glossary verbatim, surfaces both candidates with
their definitions, and proposes the more likely reading with a
code citation.

### 5.2 Concrete scenario probing (Primitive 7)

Verbatim from upstream SKILL.md lines 57–59:

> When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

The L0 invents short, concrete forced-choice prompts that surface
the distinction the operator's verbal model is papering over.

Worked scenarios (each ≤ 2 sentences):

1. **Order partial fulfillment + customer cancellation mid-flight.**
   "What happens when an **Order** is partially fulfilled (3 of 5
   items shipped) and the **Customer** cancels the remaining 2?
   Refund **Invoice** for the cancelled 2, credit on the existing
   **Invoice**, or do the 2 just disappear without a billing
   artifact?"
2. **Invoice timing contradicts CONTEXT.md.** "Your `CONTEXT.md`
   says 'an **Invoice** is only generated once a **Fulfillment**
   is confirmed' — but you just said the **Customer** is billed
   at order time. Which is canonical: bill-then-fulfil or
   fulfil-then-bill?"
3. **Two Users sharing one Customer (B2B).** "If a B2B
   **Customer** has a billing **User** and a shipping **User**,
   and the shipping **User** initiates a return, who gets the
   refund email?"

Each scenario is short enough to answer in one turn, long enough
to force a concrete answer that disambiguates the verbal model.

### 5.3 Glossary collision detection (sub-primitive of Primitive 3)

When the operator uses a term that conflicts with an existing
`CONTEXT.md` entry, the L0 surfaces the collision immediately
(upstream SKILL.md lines 49–51):

> When the user uses a term that conflicts with the existing
> language in `CONTEXT.md`, call it out immediately. "Your
> glossary defines 'cancellation' as X, but you seem to mean Y —
> which is it?"

The prompt-side codification is `detect_fuzzy_terms` (signature
in §10). The function takes the operator's plan body and the
loaded glossary; returns a list of `FuzzyTerm` records — each
carrying the candidate term, the existing definition, and the
inferred new meaning. The L0 emits a single one-question turn
per surfaced collision (per §3 / §3.2 recommended-answer format).
On operator confirmation that the new meaning supersedes the
recorded one, the L0 proposes a `CONTEXT.md` edit (see §6 / §9
for the consent contract).

## §6 — Inline Glossary Updates (Primitive 5)

The fifth primitive is a **streaming-edit** discipline: when a
fuzzy term is resolved during the interview, the resolution is
recorded in `CONTEXT.md` immediately, not batched at session end
(upstream SKILL.md lines 64–66):

> When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen.

### 6.1 The "right there" discipline

The streaming-edit pattern keeps the glossary aligned with the
operator's evolving mental model, turn by turn:

1. The L0 emits a fuzzy-term question (per §5.1) and waits.
2. On resolution, the L0 emits a follow-up turn proposing the
   glossary edit verbatim:

   > **L0:** Confirmed: **account** in this context means
   > **Customer**. Shall I record in `CONTEXT.md` the entry:
   > **Customer**: "The B2B or B2C entity that places Orders.
   > Avoid: account, client, buyer." ?

3. On operator consent, the L0 hands the write to a Task Agent
   (or trivial-exception waiver per §9.3).
4. On operator dissent, the L0 records the meaning in the
   running session log but does NOT propose another glossary
   edit until the operator re-opens the topic.

The discipline prevents **glossary drift**: when 8 fuzzy-term
resolutions are batched at session end, operators typically
reject half (mismemory of which resolution went which way) and
the L0 has to re-interview.

### 6.2 Distinction from `.local/.agent/active/<id>/spec.md`

`CONTEXT.md` and the per-change `spec.md` (per A-4 — see
`references/agent-workspace.md`) are **non-overlapping**:

| Aspect | `CONTEXT.md` | `.local/.agent/active/<id>/spec.md` |
|---|---|---|
| Scope | Domain **vocabulary** | Per-change **behaviour** delta |
| Lifecycle | Repo-long-lived | Per-change ephemeral |
| Edited by | Grill-mode resolutions | `change-driven` propose/apply |
| Cardinality | 1 per repo (or per context) | 1 per active change |

The distinction prevents two anti-patterns: (a) authors writing
glossary terms into `spec.md` (mixes vocabulary into behaviour
delta — confuses reviewers); (b) authors writing per-change
behaviour into `CONTEXT.md` (turns the glossary into a changelog).
When a grill-mode resolution surfaces both a glossary edit AND a
behaviour change, the L0 routes them separately.

### 6.3 Mechanics — defer to companion reference

The CONTEXT.md required structure (Language / Relationships /
Example dialogue / Flagged ambiguities), the "Be opinionated"
rule, the "Only project-specific" rule, the single-vs-multi-
context inference, and the lazy file-creation discipline are NOT
redocumented here. They live in `references/domain-awareness.md`
§3 and §7. Cross-load that reference alongside this one when a
`CONTEXT.md` edit is on the line.

## §7 — ADR 3-Condition Gate (Primitive 4)

The fourth primitive is the most-cited element of the upstream
skill: ADRs are offered **only when all three conditions hold
simultaneously** (upstream SKILL.md lines 71–80):

> Only offer to create an ADR when all three are true:
>
> 1. **Hard to reverse** — the cost of changing your mind later
>    is meaningful
> 2. **Surprising without context** — a future reader will wonder
>    "why did they do it this way?"
> 3. **The result of a real trade-off** — there were genuine
>    alternatives and you picked one for specific reasons
>
> If any of the three is missing, skip the ADR.

This is a **suppression** rule, not a generation rule. Default
disposition for any decision is **no ADR**; only the small subset
that pass all three qualify. The gate exists to prevent **ADR
sprawl** — the anti-pattern where every minor design preference
is recorded as a formal ADR, drowning the genuinely architectural
decisions in noise.

### 7.1 The qualification matrix

The upstream `ADR-FORMAT.md` (lines 39–53) enumerates seven
categories that DO qualify when the gate passes:

> **Architectural shape.** "We're using a monorepo." "The write
> model is event-sourced, the read model is projected into
> Postgres."
> **Integration patterns between contexts.** "Ordering and
> Billing communicate via domain events, not synchronous HTTP."
> **Technology choices that carry lock-in.** Database, message
> bus, auth provider, deployment target. Not every library —
> just the ones that would take a quarter to swap out.
> **Boundary and scope decisions.** "Customer data is owned by
> the Customer context; other contexts reference it by ID only."
> The explicit no-s are as valuable as the yes-s.
> **Deliberate deviations from the obvious path.** "We're using
> manual SQL instead of an ORM because X." Anything where a
> reasonable reader would assume the opposite.
> **Constraints not visible in the code.** "We can't use AWS
> because of compliance requirements." "Response times must be
> under 200ms because of the partner API contract."
> **Rejected alternatives when the rejection is non-obvious.**
> If you considered GraphQL and picked REST for subtle reasons,
> record it — otherwise someone will suggest GraphQL again in
> six months.

Categories are necessary-but-not-sufficient — a decision in one
of these categories STILL must pass the 3-condition gate.

### 7.2 The `qualifies_as_adr` pure function

The prompt-side codification is `qualifies_as_adr` (signature in
§10). The function takes a `DecisionDescriptor` and returns
`(qualifies: bool, missing_conditions: list[str])`. The
`missing_conditions` list lets the L0 surface to the operator
WHICH of the three conditions failed:

> **L0:** I don't think this needs an ADR. **Hard to reverse?**
> No — switching from `argparse` to `click` is a one-line import
> change. **Surprising?** No — both are stdlib-adjacent.
> **Real trade-off?** Marginal — `click` adds richer help text
> but also adds a third-party dependency. Two of three fail; the
> third is marginal. **Recommended:** skip the ADR.

The function is **pure** — no I/O, no env-var read, no auto-
write. The `missing_conditions` payload makes the gate visible
to the operator, who can disagree on a specific condition rather
than disagreeing in the abstract.

### 7.3 Anti-pattern: ADR sprawl

| Decision | Hard to reverse? | Surprising? | Real trade-off? | Verdict |
|---|:-:|:-:|:-:|---|
| `argparse` over `click` for new CLI | NO (1-line import) | NO (stdlib-adjacent) | Marginal | SKIP |
| 4-space indentation in Python source | NO (formatter config) | NO (PEP 8 default) | NO (no alternative) | SKIP |
| Name new module `src/billing/refund.py` | NO (rename = `git mv`) | NO (descriptive) | NO | SKIP |
| Switch write model to event-sourcing | YES (data migration + call-site rewrite) | YES (most readers expect sync) | YES (alts: sync, CQRS) | ADR |
| Restrict auth to `OIDC-only` (no SAML, no LDAP) | YES (re-adding protocol = quarter) | YES (enterprise expects SAML) | YES (alts considered) | ADR |

The first three rows fail trivially. The last two pass all
three. Borderline cases (e.g., choosing Pydantic v2 for new HTTP
models — hard-to-reverse YES, surprising NO, trade-off YES) are
SKIP unless the operator surfaces a non-obvious rationale.

### 7.4 Minimum-body discipline + numbering scheme

When an ADR DOES pass the gate, the upstream skill constrains
the body itself (`ADR-FORMAT.md` lines 9–21):

> # {Short title of the decision}
>
> {1-3 sentences: what's the context, what did we decide, and why.}
>
> That's it. An ADR can be a single paragraph. The value is in
> recording *that* a decision was made and *why* — not in filling
> out sections.

ADRs use sequential numbering (`0001-slug.md`, `0002-slug.md`,
…) under `docs/adr/`. The directory is created **lazily** —
only when the first ADR is needed. On creation, the L0 scans
`docs/adr/` for the highest existing number and increments by
one. Detailed numbering mechanics: `references/domain-
awareness.md` §8.

### 7.5 Distinction from historical `docs/cycle-archive/adr/`

DevolaFlow's existing repo carries a `docs/cycle-archive/adr/`
directory of historical cycle-decision ADRs (e.g.,
`v9-ADR-007-rule-rebalancing-and-rollup.md`) under an
`vN-ADR-NNN-slug.md` ad-hoc scheme. These are **NOT**
retrofitted to the upstream `0001-slug.md` scheme. The upstream
scheme applies only to v11.3.0+ NEW ADRs (gap analysis §3.3 +
risk R-12).

## §8 — Pairing with Plan Mode

### 8.1 Mode composition (run order when both active)

When both modes are active, the L0 follows a strict sequential
order:

1. **Grill phase** — operator-facing interview (§3 / §4 / §5 /
   §6 / §7). Terminates when (a) the operator explicitly halts
   ("OK, you have enough — let's plan"), OR (b) the design tree
   is fully resolved.
2. **Plan phase** — at grill-phase termination, the L0 enters
   PLAN MODE template authoring per
   `references/plan-mode-enforcement.md` §3. The plan template
   inherits operator clarifications surfaced during grilling —
   Overview text uses the operator-confirmed language, AC lists
   reference the resolved scenarios, qualifying ADR candidates
   surface as deliverable artifacts.
3. **Approval gate** — operator approves; L0 transitions to
   AGENT MODE and dispatches L1 Waves / L2 Tasks per the plan.

The transition is **one-directional** within a session — the L0
does not re-enter grilling after beginning the plan template.
If the plan-template authoring surfaces a NEW fuzzy term, the L0
emits a single-turn question without formally re-entering grill
mode.

### 8.2 Reinforcement loop interaction (W-8 / SI-9)

Grill mode does NOT participate in the checklist-round
reinforcement loop. Reinforcement is a **round-failure recovery
mechanism** operating on L2-produced artifacts. Grill
mode is an **operator-side** mechanism operating on operator
utterances. The two compose freely but neither reduces to the
other. The `applicable_rules.reinforcement` dispatch field is
NEVER populated by grill-mode logic.

### 8.3 Convergence loop interaction (gen-verify)

The Gen-Verify convergence loop (per
`references/plan-mode-enforcement.md` §7) is the runtime topology
of `gate_type: convergence` waves. Grill mode runs **at PLAN MODE
entry, BEFORE a verification wave dispatches L2 generators +
verifiers**. Grilling produces operator-confirmed inputs to the
plan; the plan dispatches the gen-verify loop. Grill mode is
upstream of the loop in the time dimension, not a participant
in it.

### 8.4 Dispatch payload posture

Grill mode adds **no new dispatch schema fields** (gap analysis
§5 risk R-5). The dispatch payload's `canonical_order` length
stays at 17 per A-2.4. Any grill-mode metadata that DOES need
dispatch-payload visibility NESTS under the existing
`behavioral_guidelines` field at canonical position 14 per A-2.3
nest-vs-append decision rule. The frozen-prefix invariant
(positions 1–12 per A-2.1) is preserved unconditionally.

## §9 — R5 Strict Default-OFF for Auto-Writes

Only the **question-asking pattern** is default-active in grill
mode. Any auto-write to `CONTEXT.md`, `docs/adr/`, or any
project file requires **explicit operator consent per session**.

### 9.1 The consent prompt

The canonical consent prompt:

> **L0:** Shall I record this in `CONTEXT.md` as **&lt;term&gt;**:
> "&lt;definition&gt;" (Avoid: &lt;aliases&gt;)?

For ADRs:

> **L0:** Shall I record this as
> `docs/adr/&lt;NNNN&gt;-&lt;slug&gt;.md`? Body:
> "&lt;1–3 sentence body&gt;"

The prompt MUST present the verbatim text the L0 intends to
write. The operator MAY reject and propose an edit; the L0
incorporates the edit and re-asks consent on the revised text.
Consent is per-write, not per-session — an operator that consents
to the first edit does not implicitly consent to a second.

### 9.2 Per-session escalation override

The operator MAY escalate consent to per-session ("yes to all
glossary edits this session") at the cost of opting out of the
per-write review. The escalation is OPERATOR-INITIATED — the L0
NEVER proposes the escalation, because doing so dilutes the R5
strict default-OFF discipline. Per-session consent applies only
to the artifact class explicitly named.

### 9.3 The grill_mode.py module never writes

The Python module `src/devolaflow/skills/grill_mode.py` itself
NEVER writes to disk. Every public function in §10 is either a
pure-function classifier (`classify_grill_intent`,
`detect_fuzzy_terms`, `qualifies_as_adr`,
`propose_canonical_term`) or a read-only filesystem probe
(`infer_context_layout`). The module's docstring asserts this
contract; the test suite (`tests/test_grill_mode.py`) pins it.

The L0 in grill mode that needs to author a `CONTEXT.md` edit
under §9.1 consent MUST delegate the write to a Task Agent
unless the trivial exception applies. Trivial-exception writes
by the L0 itself are allowed for glossary edits because each
edit is a single-line addition under one of the CONTEXT.md
sections — well under the 20-line waiver threshold.

The companion reference `references/domain-awareness.md` §7
covers the lazy file-creation discipline (no `CONTEXT.md` is
created until the first term is resolved; no `docs/adr/` is
created until the first ADR is needed).

## §10 — Activation Classifier Surface

The Python prompt-side codification of grill-mode behaviour
lives in `src/devolaflow/skills/grill_mode.py` — a pure-function
module that mirrors the design pattern of
`src/devolaflow/skills/change_activation.py` (per A-6.1).

### 10.1 The `classify_grill_intent` function

```python
def classify_grill_intent(message: str) -> GrillVerdict: ...
```

`GrillVerdict` is the public type alias:

```python
GrillVerdict = Literal["GRILL_REQUESTED", "GRILL_SUGGESTED", "NO_GRILL"]
```

The three literal strings ARE the public contract — operators
rely on them. Adding a fourth verdict is a release blocker
requiring a CHANGELOG `### Operator-visible behaviour change`
entry. The function is **pure**: identical inputs always
produce identical outputs; no filesystem touches; no time-of-
day dependence; no random sampling. The match is a verbatim
substring scan against the §2.1 phrase lists — case-insensitive
but otherwise byte-exact.

### 10.2 R5 strict design

The module mirrors `change_activation.py`'s design constraints
verbatim (per A-6.1):

- **Pure functions, zero filesystem I/O at import time.** All
  filesystem touches happen inside explicit functions
  (`infer_context_layout` is the only one) and return frozen
  dataclasses.
- **R5 strict default-OFF.** No env-var read; no companion
  runtime probe. Returns `NO_GRILL` for any input that does
  not match a REQUESTED or SUGGESTED phrase.
- **Three verdict values are the public contract.** Changing
  any of them is a release blocker.
- **No silent failures (S-5).** Invalid inputs raise
  `TypeError` / `ValueError` with verbatim messages.

### 10.3 The five public APIs

The module exposes exactly five public functions; each addresses
one of the upstream primitives.

#### `classify_grill_intent`

```python
def classify_grill_intent(message: str) -> GrillVerdict: ...
```

Activation classifier. Returns `GRILL_REQUESTED` /
`GRILL_SUGGESTED` / `NO_GRILL` based on substring match against
§2.1 phrase lists. Pure function; canonical entry point.

#### `detect_fuzzy_terms`

```python
def detect_fuzzy_terms(
    plan_text: str,
    glossary: dict[str, str],
) -> list[FuzzyTerm]: ...
```

Glossary-collision detector (primitive 3 sub-pattern
§"Challenge against the glossary"). Scans `plan_text` for terms
whose surface form matches a `glossary` entry but whose
contextual meaning appears to diverge. Returns a list of
`FuzzyTerm` records — empty means no candidates surfaced.

#### `qualifies_as_adr`

```python
def qualifies_as_adr(
    decision: DecisionDescriptor,
) -> tuple[bool, list[str]]: ...
```

Three-condition ADR gate (primitive 4). Returns
`(qualifies, missing_conditions)` — `missing_conditions` lists
the failed condition names so the L0 can surface WHICH condition
the decision failed (per §7.2).

#### `propose_canonical_term`

```python
def propose_canonical_term(
    candidate: str,
    glossary: dict[str, str],
) -> CanonicalTermSuggestion | None: ...
```

Fuzzy-term sharpening (primitive 6). Returns a
`CanonicalTermSuggestion` with the proposed precise term and
alternative readings, OR `None` when the candidate is already
unique. Pure function; no I/O.

#### `infer_context_layout`

```python
def infer_context_layout(repo_root: Path) -> ContextLayout: ...
```

Context-layout probe (primitive 3 / format-primitive F-4).
Returns one of `SINGLE_CONTEXT` / `MULTI_CONTEXT` /
`NO_CONTEXT_YET`. The only filesystem-touching public function;
uses `pathlib.Path.exists()` only — no reads of file content.

## §11 — Cross-References

### 11.1 SKILL.md sections (lands in Wave 2)

- `## Mode Awareness` — NEW sub-section §"GRILL MODE —
  Interrogate the Plan, Sharpen the Domain" points at this
  reference (gap analysis P1.4 Edit 1).
- `## Reference Navigation Guide` Tier-2 sub-table — adds 2 NEW
  rows for `references/domain-awareness.md` and
  `references/grill-mode.md` (P1.4 Edit 2).
- `## Quick Start — Workflow Selection` — adds 1 NEW row for
  `grill-driven` workflow type (P2.1).

### 11.2 Source files (Python API)

- `src/devolaflow/skills/grill_mode.py` — prompt-side
  codification module. Public functions: `classify_grill_intent`,
  `detect_fuzzy_terms`, `qualifies_as_adr`,
  `propose_canonical_term`, `infer_context_layout`.
- `src/devolaflow/skills/change_activation.py` — design-pattern
  reference (A-6.1); grill_mode mirrors its R5-strict pure-
  function pattern.

### 11.3 Companion references

- `references/domain-awareness.md` — `CONTEXT.md` required
  structure, "Be opinionated" rule, "Only project-specific" rule,
  single-vs-multi-context inference, lazy file-creation
  discipline, ADR format + numbering scheme. Cross-load whenever
  a glossary or ADR write is on the line.
- `references/plan-mode-enforcement.md` — PLAN MODE contract
  (plan template, constraints checklist, reinforcement rules,
  convergence loop). Cross-load when both modes are active per §8.
- `references/behavioral-guidelines.md` — L2 think_first /
  simplicity_check / surgical_scope / goal_loop primitives.
  Orthogonal axis to grill mode (operator-facing vs. dispatch-
  payload-facing); the two compose freely.
- `references/agent-workspace.md` — per-change `spec.md` (A-4
  source-of-truth) vs. CONTEXT.md (vocabulary) distinction
  (§6.2 above).

### 11.4 Rules

- **W-22 — Grill Mode Activation Contract** (forward reference;
  lands in Wave 2 via `.rules/workflow.mdc` + compile-rules).
  Codifies NL triggers, parallel-orthogonal relationship with
  PLAN MODE, R5 strict default-OFF, and the 3-condition ADR gate.
  NOT YET in `AGENTS.md` as of v11.1.3 baseline.
- **W-23 — Domain Glossary Maintenance** (forward reference;
  lands in Wave 2). Lazy file-creation discipline, "Only
  project-specific" rule, "Be opinionated" rule, A-4 composition
  invariant. NOT YET in `AGENTS.md` as of v11.1.3 baseline.
- **W-21 — Soul-Set Freeze** preserved at 10; grill invariants
  land at Workflow per gap analysis R-4.
- **W-20 — Env-Flag Reuse** preserved; NO new env flag (R-7).
- **A-2.x cache-layout** preserved; NO new dispatch keys (R-5).

### 11.5 Schemas

**None.** Grill mode introduces no new schema fields.
`canonical_order` stays at 17. Multi-baseline byte test
(`tests/test_layout_invariant_multi_baseline.py`) 32/32 unchanged.
Future grill-mode dispatch metadata NESTS under
`behavioral_guidelines` (canonical position 14) per A-2.3.

### 11.6 Testing surface

- `tests/test_grill_mode.py` — owned by Wave 1.T1 (sibling task;
  this reference does NOT author tests). Pins all five public
  `grill_mode.py` functions + R5 strict default-OFF assertion.
- `tests/test_no_ghost_features.py::test_v11_3_0_new_surfaces_have_coverage` —
  W-18 ghost-audit refresh (lands in Wave 2 per gap analysis
  P1.7). Pins this reference's `# Grill Mode` first-line and
  `tier: 2` frontmatter substrings + 5 AST function symbols.

### 11.7 External

- DevolaFlow / EvoBench: `https://github.com/YoRHa-Agents/DevolaFlow`
- NineS: `https://github.com/YoRHa-Agents/NineS`
- Upstream `grill-with-docs`:
  `https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs`
  (source of the 7 primitives + 7 format primitives this
  reference embeds)

## §12 — Anti-Patterns + Common Mistakes

### 12.1 — Question-batch dump

> **Anti-pattern.** L0 emits a numbered list of 8 questions in
> one turn and asks the operator to answer them all.
> **Why it fails.** Operators answer interleaved questions out
> of dependency order; answers are mutually inconsistent.
> **Correction.** Walk the design tree depth-first; one question
> per turn; wait for the answer (§3.1 + §3.4).

### 12.2 — Skipped codebase exploration

> **Anti-pattern.** L0 asks a factual question ("how does the
> auth middleware handle expired tokens?") that is fully answered
> by reading `src/auth/middleware.py:42`.
> **Why it fails.** Operator perceives the L0 as "interrogating"
> — every question feels redundant against work already done.
> **Correction.** Read first (Read / Glob / Grep / SemanticSearch
> are ALLOWED for L0 per §4.1); propose the answer back. Ask only
> if the read produced ambiguous evidence (§4.3).

### 12.3 — ADR for an easily-reversible decision

> **Anti-pattern.** L0 proposes an ADR for "use `argparse`
> instead of `click` in the new CLI module".
> **Why it fails.** Fails the "Hard to reverse" condition (1-line
> import change). Recording trivial decisions drowns genuinely
> architectural decisions in noise.
> **Correction.** Apply the 3-condition gate via
> `qualifies_as_adr` (§7.2); surface the failed condition
> explicitly and SKIP the ADR (§7.3).

### 12.4 — Silent CONTEXT.md edit without operator consent

> **Anti-pattern.** L0 resolves a fuzzy term and silently writes
> the new entry to `CONTEXT.md` without asking the operator.
> **Why it fails.** Violates the R5 strict default-OFF discipline
> (§9). Operator MAY have accepted the resolution but NOT
> consented to record it as a glossary entry.
> **Correction.** Always emit the §9.1 consent prompt before
> writing. Consent is per-write unless the operator escalates
> (§9.2). The `grill_mode.py` module itself never writes (§9.3).

### 12.5 — Confused CONTEXT.md and spec.md

> **Anti-pattern.** L0 records per-change behaviour delta into
> `CONTEXT.md`, OR records glossary entries into per-change
> `spec.md`.
> **Why it fails.** `CONTEXT.md` is **vocabulary** (long-lived,
> repo-wide); `spec.md` is **behaviour delta** (per-change,
> ephemeral). Mixing defeats both contracts.
> **Correction.** Route glossary edits to `CONTEXT.md`;
> behaviour deltas to `.local/.agent/active/<id>/spec.md` (§6.2;
> A-4 in `references/agent-workspace.md`).

### 12.6 — Skipped recommended-answer

> **Anti-pattern.** L0 asks "Redis or in-memory cache?" and
> yields the turn without proposing an answer.
> **Why it fails.** The operator authors the entire answer from
> scratch — slow, less-anchored. Upstream obliges a recommended
> answer per question (§3.2).
> **Correction.** Always propose a recommended answer + 1-sentence
> rationale. The operator critiques the proposal (§3.2 format).

### 12.7 — Continued grilling after operator halt signal

> **Anti-pattern.** Operator says "OK, you have enough — let's
> plan", and the L0 emits another grill question.
> **Why it fails.** Ignoring the halt erodes trust and wastes
> the operator's plan-time budget.
> **Correction.** Treat halt phrases ("let's plan" / "let's move
> on" / "stop questioning") as grill-phase termination per §8.1;
> transition to PLAN MODE template authoring.

### 12.8 — Confusing grill mode with the repo-init interview

> **Anti-pattern.** L0 loads
> `workflow-system/agent/knowledge/interview-protocol.md` (Tier-3
> repo-init bootstrap) during a plan-time grilling session.
> **Why it fails.** The repo-init interview scopes to fresh-repo
> bootstrap (`.rules/`, prefs, skill bundles). It does not
> interview the operator about the unfolding plan.
> **Correction.** Load `grill-mode.md` for plan-time grilling;
> load `interview-protocol.md` ONLY when `repo-init` workflow is
> active. The two never compose (§1; gap analysis R-11).

---

**End of `grill-mode.md`.** Canonical operating contract for
DevolaFlow's grill mode. Cross-load `references/domain-awareness.md`
whenever a `CONTEXT.md` or ADR write is on the line; cross-load
`references/plan-mode-enforcement.md` whenever both modes are
active simultaneously per §8.
