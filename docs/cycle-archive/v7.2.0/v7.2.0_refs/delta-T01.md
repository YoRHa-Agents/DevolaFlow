# S01.W01.T01 — High-Relevance Active Refs Delta Report

**Generated:** 2026-04-18
**References analyzed:** 3 (anthropic-advisor-tool, superpowers, anthropic-coordination-blog)
**Last_checked baseline:** 2026-04-11
**DevolaFlow current version:** v7.1.1

## Summary Table

| Ref ID | Old Version | Current Version | New Patterns Found | Recommended Action |
|---|---|---|---|---|
| anthropic-advisor-tool | beta (advisor-tool-2026-03-01) | beta (advisor-tool-2026-03-01) — public beta launched 2026-04-09 | 5 (system prompt blocks, advisor-side caching, clear_thinking caveat, usage.iterations cost tracking, conciseness instruction) | 3 import / 2 monitor |
| superpowers | latest (2026-04) | v5.0.7 (released 2026-03-31; HEAD commits through 2026-04-16) | 3 (inline self-review checklists, Codex plugin sync tooling, agent-facing contributor guardrails) | 1 import / 2 monitor |
| anthropic-coordination-blog | latest (2026-04) | published 2026-04-10 (no edits since baseline) | 2 (pattern-pair decision criteria, hybrid-pattern recipes) | 1 import / 1 monitor |

---

## anthropic-advisor-tool

### Current State
- fetch_status: success (URL `https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/advisor-tool`, 25.6 KB / 637 lines)
- detected_version: `advisor-tool-2026-03-01` (unchanged)
- last_modified: not exposed by docs site; corroborated by web search — public beta launched 2026-04-09 (post-baseline by 2 days)
- supported model pairs (verbatim from §Model compatibility):
  - Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) → Claude Opus 4.7 (`claude-opus-4-7`)
  - Claude Sonnet 4.6 (`claude-sonnet-4-6`) → Claude Opus 4.7
  - Claude Opus 4.6 (`claude-opus-4-6`) → Claude Opus 4.7
  - Claude Opus 4.7 → Claude Opus 4.7

### Delta Items

#### Delta-1: Suggested system prompt blocks for executor (timing + reconcile-on-conflict)
- **What changed:** Docs now ship two verbatim prompt blocks under "Suggested system prompt for coding tasks" — (1) timing guidance ("Call advisor BEFORE substantive work … On tasks longer than a few steps, call advisor at least once before committing to an approach and once before declaring done"), and (2) advice-handling guidance ("If you've already retrieved data pointing one way and the advisor points another: don't silently switch. Surface the conflict in one more advisor call — 'I found X, you suggest Y, which constraint breaks the tie?'"). These were not part of the documented `key_patterns`.
- **Source:** advisor-tool docs §Best practices → "Prompting for coding and agent tasks" (lines 583–610 of fetched content)
- **DevolaFlow integration target:** `workflow-system/agent/SKILL.md` (L3 Task Agent system prompt extension), `src/devolaflow/task_adaptive_selector.py::_build_advisor_section` (already emits "## Advisor Tool" — extend with timing block)
- **Currently integrated?** No. `task_adaptive_selector.py` line ~227 emits `f"Advisor enabled (max {max_uses} uses, budget ${cost_ceiling}). Invoke for: {triggers_str}."` but does NOT include the timing/reconcile blocks.
- **Recommended action:** import
- **Rationale:** The two blocks are first-party Anthropic guidance with internal-eval evidence ("highest intelligence at near-Sonnet cost"). Low integration cost (~50-line patch to one helper); high signal for L3 agents that already have advisor enabled in 6 task profiles (feature, refactoring, migration, security_audit, performance_optimization, full_pipeline).

#### Delta-2: Conciseness instruction cuts advisor output 35–45%
- **What changed:** New documented optimisation: "The advisor should respond in under 100 words and use enumerated steps, not explanations." (verbatim) — claimed to reduce advisor output tokens 35–45% with no call-frequency change.
- **Source:** advisor-tool docs §Best practices → "Trimming advisor output length" (lines 612–621)
- **DevolaFlow integration target:** `src/devolaflow/task_adaptive_selector.py` advisor-section emitter; `workflow-system/agent/context_profiles.yaml` (add optional `advisor.conciseness_instruction: bool` flag per profile)
- **Currently integrated?** No.
- **Recommended action:** import
- **Rationale:** Direct cost win (~40% of advisor tokens). Aligns with DevolaFlow's existing `cost_ceiling_usd: 0.30` budget per profile. Trivial 1-line addition to the emitted prompt; benchmarkable via `tests/test_benchmarks.py` cost dimension.

#### Delta-3: Advisor-side prompt caching (`caching: {type: ephemeral, ttl: "5m"|"1h"}`)
- **What changed:** New tool parameter `caching` enables advisor's own transcript caching across calls. Break-even at ≥3 advisor calls per conversation (writes cost more than reads save below that threshold). Setting must remain stable across the conversation — toggling causes cache misses.
- **Source:** advisor-tool docs §Tool parameters table + §Advisor prompt caching (lines 290–298, 495–531)
- **DevolaFlow integration target:** `workflow-system/agent/context_profiles.yaml` (advisor section: add `caching` subkey alongside `enabled`, `max_uses`, `conversation_budget`); `src/devolaflow/task_adaptive_selector.py` (forward `caching` config into emitted advisor section)
- **Currently integrated?** No. Current advisor schema in `context_profiles.yaml` is `{enabled, max_uses, conversation_budget, trigger_conditions, cost_ceiling_usd}`.
- **Recommended action:** import
- **Rationale:** Convergence-loop stages (refactoring, full_pipeline, security_audit) easily exceed 3 advisor calls per conversation given `gen_verify_max_rounds: 3` × multiple waves; advisor-side cache hits would compound across rounds. Default `caching: null` preserves backward compat.

#### Delta-4: `clear_thinking` (default `keep: thinking_turns, value: 1`) silently breaks advisor-side cache
- **What changed:** New documented warning: "When extended thinking is enabled without explicit `clear_thinking` configuration, the API defaults to `keep: {type: 'thinking_turns', value: 1}`, which triggers this behavior. Set `keep: 'all'` to preserve advisor cache stability."
- **Source:** advisor-tool docs §Advisor prompt caching → final paragraph (lines 525–531)
- **DevolaFlow integration target:** `workflow-system/agent/references/execution-protocol.md` (add interaction-with-thinking caveat); `workflow-system/agent/context_profiles.yaml` (document recommended `clear_thinking.keep: all` when `advisor.caching` is enabled)
- **Currently integrated?** No.
- **Recommended action:** monitor
- **Rationale:** Pure cost-degradation, not correctness — only worth importing once Delta-3 ships. Track as a paired follow-up.

#### Delta-5: `usage.iterations[]` array exposes per-call cost split (executor vs advisor model rates)
- **What changed:** Top-level `usage` reports executor tokens only; advisor sub-inferences appear as iteration entries `{type: "advisor_message", model, input_tokens, output_tokens, ...}`. Output token aggregation differs by field.
- **Source:** advisor-tool docs §Usage and billing (lines 449–489)
- **DevolaFlow integration target:** would touch a not-yet-existent observability/cost-tracking module (no current direct integration point); closest existing surface is `src/devolaflow/gate/scorer.py::_apply_advisor_detection` which sets `advisor_recommended` but does not surface costs.
- **Currently integrated?** No (DevolaFlow has no per-iteration cost tracker).
- **Recommended action:** monitor
- **Rationale:** Useful for future cost-attribution feature, but no consumer surface today; the documented `cost_ceiling_usd: 0.30` is enforced as a static client-side budget rather than from `usage.iterations`. Park until a cost dashboard / `nines self-eval` cost dimension is in scope.

### Relevance Score Refresh
- documented: 5
- recommended: **5** (unchanged) — public beta launch (2026-04-09) plus 3 importable improvements (Delta-1/2/3) keeps this on the highest tier; no breaking changes to existing integration pattern (`advisor_margin` in `gate/scorer.py`, `advisor:` block in `context_profiles.yaml`).

---

## superpowers

### Current State
- fetch_status: success
  - `https://github.com/obra/superpowers` — landing page (157,833 stars; `0` forks reported, likely a render artifact)
  - `https://raw.githubusercontent.com/obra/superpowers/main/README.md` — full README
  - `https://github.com/obra/superpowers/commits/main` — commit history through 2026-04-16
- detected_version: **v5.0.7** (released 2026-03-31, per WebSearch + commit "Release v5.0.7: Copilot CLI support, OpenCode fixes")
- last commit on main: 2026-04-16 (formatting / README updates / install reorder)
- previous release: v5.0.6 (2026-03-25) — *both* releases predate baseline `2026-04-11` by ≥17 days, so they are not literally "new" relative to baseline; however they are not represented in current `key_patterns`, so the deltas below capture undocumented-but-current state.

### Delta Items

#### Delta-1: Inline self-review checklists replace subagent review loops in brainstorming + writing-plans skills
- **What changed:** v5.0.6 release notes (verbatim from WebSearch summary): "Replaced subagent review loops with inline self-review checklists in brainstorming and writing-plans skills, reducing review time from ~25 minutes to ~30 seconds while maintaining comparable defect detection." This is a *new* enforcement pattern not present in our key_patterns list (which mentions "two-stage review: spec compliance then code quality" but not the inline-checklist alternative).
- **Source:** superpowers v5.0.6 release notes (commit `Release v5.0.6: inline self-review, brainstorm server restructure, owner-PID fixes`, dated 2026-03-25); also visible on https://github.com/obra/superpowers/blob/main/RELEASE-NOTES.md
- **DevolaFlow integration target:** `workflow-system/agent/SKILL.md` "Wave Coordination Modes" — could add an `inline_self_review` mode for low-risk waves where dispatching a separate verifier subagent is overkill; `workflow-system/agent/references/decomposition-gate.md` — alternative to `gen_verify_mode` for design-only / documentation stages
- **Currently integrated?** No. DevolaFlow currently always pairs generator with separate verifier in `generator_verifier` wave mode (SKILL.md lines 220–227); there is no inline-checklist shortcut for cheap stages.
- **Recommended action:** import
- **Rationale:** 50× speedup with comparable defect detection is a strong signal. Low-risk addition: opt-in `inline_review_checklist` flag in context profile, default off. Aligns with the "match ceremony to complexity" principle in SKILL.md Quick Action Decision table. Interesting EvoBench candidate (`tests/test_benchmarks.py`) for context-density wins on documentation/research workflows.

#### Delta-2: New `sync-to-codex-plugin` tooling — fork-clone + PR + heredoc-aligned plugin metadata
- **What changed:** Multiple commits on 2026-04-14 added a Codex plugin mirror system: `adds tooling to mirror superpowers as a codex plugin with the appropriate metadata changes`, `rewrites sync tool to clone the fork, open a PR, and regenerate overlays inline`, `sync-to-codex-plugin: align plugin.json heredoc with current live shape`, `sync-to-codex-plugin: anchor EXCLUDES patterns to source root`, `sync-to-codex-plugin: exclude assets/, add --bootstrap flag`, `sync-to-codex-plugin: seed interface.defaultPrompt` (PR #1180 merged 2026-04-15).
- **Source:** https://github.com/obra/superpowers/commits/main — 2026-04-14 / 2026-04-15
- **DevolaFlow integration target:** `scripts/sync_cursor_skill.py` (current Cursor mirror), `scripts/install.sh` (per CP-3 / SF-3 rules); could extend with similar `sync-to-codex-plugin` for consistent multi-adapter publishing
- **Currently integrated?** Partially — DevolaFlow has its own `sync_cursor_skill.py` for the `.cursor/skills/devola-flow/` mirror (12 files + stamp) and Codex adapter in `~/.codex/skills/devola-flow/`; the mirror is bytewise per SF-3. The PR-back-to-fork pattern is novel.
- **Recommended action:** monitor
- **Rationale:** Implementation detail, not a behavioural pattern. DevolaFlow's adapter pipeline (4 adapters per CP-5) covers similar ground. Worth monitoring if our adapter coverage drifts.

#### Delta-3: Agent-facing contributor guidelines to "reduce agentic slop PRs"
- **What changed:** Two commits on 2026-03-31 (just before baseline): `Add contributor guidelines to reduce agentic slop PRs`, `Add agent-facing guardrails to contributor guidelines`. This is a new enforcement-meta pattern: writing CONTRIBUTING-style guardrails *for* agent contributors (not just human contributors).
- **Source:** https://github.com/obra/superpowers/commits/main — 2026-03-31
- **DevolaFlow integration target:** `CONTRIBUTING.md` (does not currently exist at root — verified via Glob); `workflow-system/agent/references/team-roles.md` (could embed as Review-team checklist for community PRs)
- **Currently integrated?** Partially — DevolaFlow has `.cursor/rules/change-process-rules.mdc` (CP-1..CP-7) which serves a similar role for AI authors but is rules-engine-targeted, not contributor-PR-targeted.
- **Recommended action:** monitor
- **Rationale:** Adjacent concern, not core to v7.2 scope. Track for future contributor-onboarding stage.

### Relevance Score Refresh
- documented: 5
- recommended: **5** (unchanged) — Delta-1 (inline self-review) is genuinely novel and importable; the project remains the canonical reference for skill-format enforcement patterns (Iron Laws, rationalization tables, CSO descriptions, typed status — three of which are already integrated per `CHANGELOG.md` lines 972–977). Repo activity is steady (commits through 2026-04-16) and star count remains an outlier (~157K).

---

## anthropic-coordination-blog

### Current State
- fetch_status: success (`https://www.claude.com/blog/multi-agent-coordination-patterns`, 31.9 KB)
- detected_version: post dated **2026-04-10** (one day before baseline `2026-04-11`); no visible edits since
- author: Cara Phillips, with contributions from Eugene Yan, Jiri De Jonghe, Samuel Weller, Erik S.
- announced follow-ups: "In upcoming posts, we will examine each pattern in depth with production implementations and case studies" — no follow-up posts visible yet (related posts on the page are dated Apr 10, Apr 2, Mar 5, Jan 23, all pre/early-April)

### Delta Items

#### Delta-1: Pattern-pair decision criteria + hybrid-pattern recipes
- **What changed:** Section "Choosing and evolving between patterns" provides explicit pairwise decision rubrics that were not captured in our `key_patterns` list:
  - Orchestrator-subagent vs. agent teams: "When subagents need to retain state across invocations, agent teams are the better fit."
  - Orchestrator-subagent vs. message bus: "As conditional logic accumulates in the orchestrator to handle an expanding variety of cases, the message bus makes that routing explicit and extensible."
  - Agent teams vs. shared state: "Once teammates need to communicate with each other rather than only share final results, shared state makes that more natural."
  - Message bus vs. shared state: "If agents in a message bus system are publishing events to share findings rather than trigger actions, shared state is a better fit."
  - Hybrids (verbatim): "A common hybrid uses orchestrator-subagent for the overall workflow with shared state for a collaboration-heavy subtask. Another uses message bus for event routing with agent team-style workers handling each event type."
- **Source:** anthropic-coordination-blog §Choosing and evolving between patterns + §Getting started (lines 155–212 of fetched content)
- **DevolaFlow integration target:** `workflow-system/agent/SKILL.md` "Wave Coordination Modes" table (currently 4 rows: parallel / sequential / generator_verifier / hybrid — `hybrid` row is undocumented as to *which* hybrids); `workflow-system/agent/references/execution-protocol.md` (add coordination-mode selection rubric)
- **Currently integrated?** Partially. SKILL.md already has `generator_verifier` and `hybrid` modes, and the L0-L3 hierarchy IS the orchestrator-subagent pattern. But:
  - `agent_teams` is **not** modelled as a distinct mode (DevolaFlow Task Agents are always one-shot — Wave dispatches them, they terminate; no persistent worker pattern).
  - `message_bus` is **not** modelled (no event-driven routing primitive).
  - `shared_state` is **not** modelled (P5 explicitly says "No bidirectional shared state").
  - The decision criteria for *when* to switch are absent.
- **Recommended action:** import
- **Rationale:** The blog gives DevolaFlow a vocabulary to (a) document why P5 (artifacts as contracts) intentionally rejects the shared-state pattern for inter-layer comm, and (b) extend Wave Coordination Modes with one or two new entries when the use case fits. The hybrid recipe ("orchestrator-subagent for the overall workflow with shared state for a collaboration-heavy subtask") is a near-perfect characterisation of the existing `self-update` workflow research stage (multiple T01-T07 task agents producing parallel delta reports for L1 to synthesise) — worth surfacing explicitly. Could also justify a new `agent_team` mode for persistent code-review subagents in `feature-enhancement` workflows.

#### Delta-2: Reactive-loop hazard for shared-state pattern + first-class termination requirement
- **What changed:** New documented failure mode (verbatim): "The harder failure mode is reactive loops. For example, Agent A writes a finding, Agent B reads it and writes a follow-up, Agent A sees the follow-up and responds. The system keeps burning tokens on work that isn't converging. … Reactive loops are a behavioral problem and need first-class termination conditions: a time budget, a convergence threshold (no new findings for N cycles), or a designated agent whose job is to decide when the store contains a sufficient answer."
- **Source:** anthropic-coordination-blog §Pattern 5: Shared state → Where it struggles (lines 149–153)
- **DevolaFlow integration target:** `workflow-system/agent/references/decomposition-gate.md` (convergence loop already has `max_rounds` + stagnation detection — the "no new findings for N cycles" framing is a nice rephrase); `src/devolaflow/gate/convergence.py::detect_stagnation` (already implements the "stagnant 2 rounds → escalate" rule per `_evaluate_convergence` in `gate/scorer.py` line 501)
- **Currently integrated?** Yes (sufficiently). DevolaFlow's `detect_stagnation` + `compute_trend` + `max_rounds` covers exactly this hazard for convergence stages. P4 Bounded Retry rule is the policy expression.
- **Recommended action:** monitor
- **Rationale:** Validates existing DevolaFlow design rather than adding new requirements. Reference-friendly framing if we ever document why P5 is a strict rule.

### Relevance Score Refresh
- documented: 5
- recommended: **5** (unchanged) — Delta-1 unlocks 1-2 high-value SKILL.md edits in v7.2; Delta-2 validates existing design. Blog is recent (1 week before baseline), authored by an Anthropic team, and announces follow-up posts — high "monitor for next deep-dive" value.

---

## Cross-Cutting Observations

### Patterns appearing in multiple sources
- **Cost-controlled bottom-up escalation:** Both `anthropic-advisor-tool` (advisor pattern, Delta-1/2/3) and `anthropic-coordination-blog` (generator-verifier, orchestrator-subagent) describe the same shape: cheap executor + expensive consultant invoked at decision points. DevolaFlow already integrates this via `gate/scorer.py::_apply_advisor_detection` + `context_profiles.yaml::advisor.*`. The advisor-tool delta items refine the prompt; the coordination-blog deltas refine the topology.
- **Termination is first-class, not an afterthought:** Both `superpowers` (subagent-driven-development with two-stage review) and `coordination-blog` (Pattern 1 generator-verifier "iterative loops can stall … maximum iteration limit with a fallback strategy", Pattern 5 shared-state "reactive loops") echo DevolaFlow's P4 Bounded Retry rule. Validates the design.
- **Match ceremony to complexity:** `superpowers` Delta-1 (inline self-review checklists for 30-second review of low-risk artifacts) and SKILL.md's existing Quick Action Decision table both express this. Delta-1 is the missing low-end of DevolaFlow's `generator_verifier` mode.

### Conflicts with current DevolaFlow design
- **shared-state pattern vs. P5 (Artifacts as Contracts):** The coordination blog's Pattern 5 ("agents read/write a shared store directly, no central coordinator") is structurally incompatible with DevolaFlow's P5 rule ("Layers communicate through artifact files, not shared memory or conversation history. … No bidirectional shared state"). This is intentional — DevolaFlow opts for unidirectional artifact handoff to preserve auditability and cache stability — but the blog should be cited in `references/meta-framework.md` to make the trade-off explicit.
- **agent-teams (persistent workers) vs. fresh-context Task Agents:** DevolaFlow's L3 Task Agents are explicitly one-shot ("MUST NOT spawn sub-agents"; SKILL.md line 192). The agent-teams pattern (workers persist across many assignments) would require relaxing this for specific workflows — *not* recommended as a general primitive, but acceptable as an opt-in mode for stateful subtasks (e.g., long-running migration of a single service).

### Quick wins (low effort, high signal)
1. **Advisor Delta-2** — single-line prompt addition ("under 100 words, enumerated steps") for ~40% advisor cost reduction. Verifiable via `tests/test_benchmarks.py` cost dimension.
2. **Advisor Delta-1** — extend `task_adaptive_selector.py::_build_advisor_section` to emit the timing + reconcile blocks. ~50-line patch, single file.
3. **Superpowers Delta-1** — opt-in `inline_review_checklist` flag in context profile for documentation/research stages. ~30-line patch, validates against EvoBench.
4. **Coord-blog Delta-1** — annotate SKILL.md "Wave Coordination Modes" `hybrid` row with the two named hybrid recipes from the blog (orchestrator+shared-state, message-bus+agent-team-workers) plus a one-line decision rubric per pattern pair. Documentation-only, 5-10 line edit.

---

## Limitations
- `https://github.com/obra/superpowers/blob/main/README.md` returned an empty page when fetched (rendered HTML wrapper); the raw URL `https://raw.githubusercontent.com/obra/superpowers/main/README.md` worked. No data lost.
- Did not fetch `https://github.com/obra/superpowers/releases` directly; relied on WebSearch results citing v5.0.7 (2026-03-31) and v5.0.6 (2026-03-25) plus the commits-on-main page for changes through 2026-04-16. Suggest follow-up to read `RELEASE-NOTES.md` directly if a richer changelog is required for Delta-1 (inline self-review pattern).
- The advisor-tool docs page does not expose a `last_modified` header; version anchored on the beta header value `advisor-tool-2026-03-01` and corroborated by web search ("public beta on April 9, 2026").
- Coordination-blog page has no edit history or revision marker; treated as a snapshot of the 2026-04-10 publication. The "in upcoming posts" promise was checked against related-posts list (no follow-up patterns deep-dives visible as of 2026-04-18).
- Did not search for "Anthropic Engineering" blog posts that might cross-reference the coordination patterns post; out of scope for T01.
