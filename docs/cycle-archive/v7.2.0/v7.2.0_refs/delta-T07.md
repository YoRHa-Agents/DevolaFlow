# Reference Delta Survey — T07 (christophera-bootstrap-seed + spring-ai-agent-skills)

| field | value |
|-------|-------|
| task_id | S01.W02.T07 |
| role | research / reference-delta-survey |
| owned_path | `.local/research/v7.2.0_refs/delta-T07.md` |
| devolaflow_version | v7.1.1 |
| baseline_registry | `workflow-system/agent/knowledge/reference-dependencies.yaml` (snapshot 2026-04-11) |
| cutoff_check_date | 2026-04-18 |
| references_in_scope | 2 (periodic_monitoring, score=3) |
| sources_modified | none (read-only research; no DevolaFlow source touched) |

---

## Reference 1 — `christophera-bootstrap-seed` (gist `fd2985551e765a86f4fbb24080263a2f`)

### 1.1  Current state snapshot (verbatim from upstream)

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | `"latest (gist, 27 stars)"` | **29 stars (+2 / +7.4% over 7 days), 7 forks, 3 comments, 2 file revisions (both 2026-02-05) — content unchanged for 72 days** | GitHub GraphQL `user(login:"ChristopherA") { gist(name:"fd29855…") { stargazerCount forks{totalCount} comments{totalCount} createdAt updatedAt } }` |
| `stargazerCount` | **27** (verbatim from registry note) | **29** | GraphQL response 2026-04-18: `{"stargazerCount":29,"forks":{"totalCount":7},"comments":{"totalCount":3},"updatedAt":"2026-04-07T17:50:05Z","createdAt":"2026-02-05T03:47:25Z"}` |
| `forks` | (not captured) | **7** | same |
| `total_revisions` | (not captured) | **2** — both on day of creation: `edd73c85b0c6bc1e99320392e21ac1572811c6f6` (2026-02-05T03:47:25Z, +210/−0 lines, initial) and `860d3f71fef949ff5692c86bb251c571caf53790` (2026-02-05T03:50:36Z, +2/−2 lines, immediate touch-up). **No revisions in the 72 days since.** | `api.github.com/gists/fd2985551e765a86f4fbb24080263a2f/commits` |
| `gist updatedAt` | n/a | `2026-04-07T17:50:05Z` (gist `updated_at` is bumped by stars/comments/forks, **not** by file edits — see `committed_at` chain above) | GraphQL + REST `commits` endpoint |
| `comments` | n/a | **3** total: `tudorsaitoc` 2026-02-06 ("experimenting now"); `hongjun-bae` 2026-03-24 ("How is it? Is it effective?"); `tudorsaitoc` 2026-03-24 ("make sure everything is wired up (learnings.md) and performance will improve") | gist HTML body via WebFetch 2026-04-18 |
| `files` | n/a | 2 files: `README.md` (6,161 bytes) and `self-improving-claude-code.md` (the seed itself, ~1400 tokens by author claim) | gist body |
| `license` | n/a | **CC-BY-4.0** | gist README §License |
| `attribution` | n/a | "Christopher Allen (@ChristopherA) — with collaborative development via Claude Code (Opus 4.5)" | gist README §Author |

### 1.2  Star + revision comparison vs baseline (acceptance criterion #4)

| metric | 2026-04-11 baseline | 2026-04-18 verified | Δ | classification |
|--------|---------------------|---------------------|---|----------------|
| stars | 27 | **29** | +2 (+7.4%) | mild positive growth (~1.7 stars/week run-rate over 7 days) |
| revisions | implicit "latest" | **2 commits, both 2026-02-05** | 0 new revisions since baseline | content frozen — no upstream signal that requires re-evaluation |
| forks | n/a | **7** | n/a (no baseline number) | low-to-moderate adoption; no notable derivative repos surfaced |
| comments | n/a | **3** | n/a | thin community signal — single user expressing uncertainty about effectiveness |

**Verdict on update_triggers** (registry: "gist revisions or significant fork innovations" + "community adoption or derivative implementations"):

- **Trigger #1 — gist revisions:** *not fired* (zero revisions since 2026-02-05).
- **Trigger #2 — fork innovations:** *low evidence* (7 forks; the GraphQL forks endpoint was not deep-inspected because score=3 does not justify per-fork triage).
- **Trigger #3 — community adoption:** *minimal* (3 comments in 72 days; one explicitly questions effectiveness with no resolution).

### 1.3  Cross-check vs DevolaFlow integration points

Registered integration points for `christophera-bootstrap-seed`:

1. `post-workflow stage (reflect→triage→cascade)`
2. `per-project customization layer`

Mapping the gist's seed mechanics → current DevolaFlow surface:

| Gist primitive | Gist semantics | DevolaFlow equivalent (verified 2026-04-18) | Coverage |
|----------------|----------------|---------------------------------------------|----------|
| **Bootstrap session 1** (use-case discovery via `AskUserQuestion`) | First session asks "Building software / Creating content / Knowledge management / Conversation partner" | **Absent** — DevolaFlow's `install-devola-flow` skill seeds files but does not interactively classify the project. Workflow templates pre-classify by primitive (`hotfix`, `feature`, `pipeline`). | partial (offline equivalent only) |
| **Reflect → Triage → Cascade** core loop | After non-trivial work: reflect → triage each finding (apply / capture / dismiss) → cascade to siblings | **Stronger version present**: `gate/scorer.py` (`acceptance_readiness`, `escalation`, `convergence`) + `gate/reinforcement.py` (`findings_to_reinforcement()` with `MAX_REINFORCEMENT_RULES = 5`) + Rule SI-9 (Convergence Round Reinforcement) — DevolaFlow's loop is **mandatory, scored, and bounded**, not LLM-discretionary. | ~110% (more disciplined than gist) |
| **`learnings.md` capture file** | Append-only LLM-curated journal; promoted to `rules/` after 2+ uses | **Aspirational** — `workflow-system/agent/knowledge/index.md` references `learnings/operational.jsonl` but the file does not exist (per T04 Δ-karpathy-02). Promotion to rules is human-driven via SI-1 planning artifacts. | weak |
| **Anti-proliferation guardrail** ("default is edit existing; new file requires justification") | Stated as anti-pattern in gist | **Strong match** — Rule CO-4 (Relative Paths Only) + Rule SF-1 (line budget) + cursor `<making_code_changes>` rule "ALWAYS prefer editing an existing file to creating a new one" | ~100% |
| **State file pattern** for cross-session continuity | `.claude/`-scoped state file with Goal / Status / Done / Next / Open questions | **Strong match** — DevolaFlow uses TaskDispatch + StatusReport YAML messages (P3 Structured Messages) + artifacts under `.local/research/` and `workflow-system/agent/knowledge/` | ~100% |
| **AskUserQuestion at structural decisions** | Gist mandates `AskUserQuestion` for consolidation, splits, new files, rule promotion | **Intentionally absent** — DevolaFlow's P3 Structured Messages prohibits free-form layer-to-layer prose; user interaction happens at L0 boundaries via SwitchMode (plan/agent), not mid-loop. | divergent by design |
| **Context discipline budgets** (`CLAUDE.md <100 lines`, `rules/ <200 lines total`, `learnings.md` review at ~30 entries) | Numeric budgets stated inline | **Stronger version present** — Rule SF-1 (SKILL.md ≤500 lines), Rule CO-3 (per-layer token budgets 3K/5K/4K/8K), Rule SI-6 (hard-limit enforcement) | ~100% |
| **Evolution mechanics** (promotion @ 2+ uses, consolidation @ ~30 entries, structural emergence @ 50-line rules) | Heuristics inside the seed | **Match in spirit, weaker in mechanism** — DevolaFlow's evolution is human-driven via SI-1 → SI-10 iteration cycle, not auto-triggered by counters. | partial |

### 1.4  Delta items (5-field schema)

> Schema (applied to every entry below): `id` · `observation` (vs documented key_pattern) · `evidence` (URL / file / date) · `devolaflow_impact` (high/medium/low + rationale relative to current code) · `recommendation` (port / track / refresh-registry / no-op)

#### Δ-christophera-01  Stars +7.4%, content frozen 72 days, no revisions since baseline
- **observation:** Registry `last_known_version: "latest (gist, 27 stars)"` advances to **29 stars (+2)**. Forks=7. Total revisions = 2, both `2026-02-05` — i.e. **the gist body has not been edited since the original double-commit on the day of publication**. `updated_at: 2026-04-07T17:50:05Z` reflects social activity (stars/comments), not file changes.
- **evidence:** GraphQL `user(login:"ChristopherA"){gist(name:"fd29855…"){stargazerCount forks{totalCount} comments{totalCount} createdAt updatedAt}}` returned `{"stargazerCount":29,"forks":{"totalCount":7},"comments":{"totalCount":3},"updatedAt":"2026-04-07T17:50:05Z","createdAt":"2026-02-05T03:47:25Z"}` (executed 2026-04-18); `api.github.com/gists/fd2985551e765a86f4fbb24080263a2f/commits` returned `[{version:"860d3f71…",committed_at:"2026-02-05T03:50:36Z",change_status:{additions:2,deletions:2}},{version:"edd73c85…",committed_at:"2026-02-05T03:47:25Z",change_status:{additions:210,deletions:0}}]`.
- **devolaflow_impact:** *low* — registry text needs a numeric refresh, but no behavioural change is implied. The `update_triggers` ("gist revisions or significant fork innovations") **did not fire** in the 7-day window since baseline.
- **recommendation:** **refresh-registry only** — bump `last_checked: 2026-04-18`, update `last_known_version: "v1 (29 stars, 2 revisions both 2026-02-05, 7 forks, 3 comments)"`, and add `revision_sha_latest: 860d3f71`, `content_frozen_since: 2026-02-05` so the next periodic scan can short-circuit if `updated_at` (social) increments without `committed_at` change.

#### Δ-christophera-02  Community signal is thin and openly skeptical of effectiveness
- **observation:** Three comments in 72 days. The most recent thread is a non-author asking "How is it? Is it effective?" with the only response being a 3rd-party hand-wave ("make sure everything is wired up (learnings.md) and performance will improve"). The author (Christopher Allen) has not added validation data, retrospectives, or "after N sessions" reports despite the gist's own stated open-question list ("Untested — This is a hypothesis, not a validated system. Real sessions will reveal gaps.").
- **evidence:** gist comments thread fetched 2026-04-18 (3 comments dated 2026-02-06, 2026-03-24, 2026-03-24); gist README §"Limitations and Open Questions" lists 5 explicit unknowns including "Cold start quality" and "No enforcement".
- **devolaflow_impact:** *low* — supports DevolaFlow's design choice to keep evolution **scored and bounded** (Rule SI-3 dimensional scoring, Rule SI-4 EvoBench regression guard, Rule SI-9 reinforcement) rather than rely on emergent LLM discretion. Gist remains an interesting **negative-control reference** (what a minimal seed looks like when the discipline scaffolding is intentionally absent).
- **recommendation:** **track** — keep `relevance_score: 3`. Annotate the registry entry with `validation_status: "author-acknowledged hypothesis (untested as of 2026-04-18)"` so downstream consumers don't over-weight this reference for production patterns.

#### Δ-christophera-03  `reflect→triage→cascade` loop is structurally weaker than DevolaFlow's gate+reinforcement loop
- **observation:** Gist key_pattern: "emergent config via reflect→triage→cascade loop". Decomposing this against DevolaFlow:
  - **reflect** — gist relies on LLM self-prompting after non-trivial work; DevolaFlow runs `gate/scorer.py` with deterministic dimensional scoring (composite_score, blocker_count, round_num) per Rule SI-3.
  - **triage (apply / capture / dismiss)** — gist offers a 3-way LLM choice; DevolaFlow's `gate/reinforcement.py::findings_to_reinforcement()` converts findings into MUST-fix mandates capped at `MAX_REINFORCEMENT_RULES = 5` with severity-floor filtering, injected into round N+1 dispatch (per Rule SI-9).
  - **cascade** — gist asks LLM "Does this improvement apply to related content?"; DevolaFlow's cascade is the convergence loop itself (`detect_stagnation()` triggers ESCALATE on 2 consecutive non-improving rounds).
- **evidence:** gist body §"Core Loop"; DevolaFlow `src/devolaflow/gate/reinforcement.py` (`MAX_REINFORCEMENT_RULES = 5`), `src/devolaflow/gate/convergence.py` (`detect_stagnation`), `.cursor/rules/self-improve-iteration-rules.mdc` Rule SI-9 lines 73-76.
- **devolaflow_impact:** *low* — DevolaFlow already has a stronger, deterministic version of this loop. Gist's "emergent" framing is **inferior** to DevolaFlow's bounded-retry design (Rule P4) for production workflows. The L6 gap ("Bootstrap self-evolution") is therefore satisfied **in spirit** by the existing gate machinery; only the per-project bootstrap-time customisation aspect is unaddressed.
- **recommendation:** **no-op for v7.2** — do not adopt the LLM-discretionary triage. Optionally (v7.3+) extract the **bootstrap-time use-case classifier** as a thin pre-flight in `install-devola-flow` skill (interactive question during install), but that is a separate gap (post-installation customisation, not loop semantics).

#### Δ-christophera-04  AskUserQuestion at structural decisions — divergent by design from P3 Structured Messages
- **observation:** Gist mandates `AskUserQuestion` at six decision points: bootstrap, consolidation, splits, new files, rule promotion, "when patterns emerge that could reshape the workspace". DevolaFlow's Rule P3 (Structured Messages) **prohibits** free-form natural language between layers; all inter-layer communication uses TaskDispatch / StatusReport / ExceptionEscalation YAML schemas. User interaction is concentrated at L0 boundaries (SwitchMode plan↔agent, install skill prompts) — not threaded through the operating loop.
- **evidence:** gist body §"User Feedback Loop"; `.cursor/rules/workflow-rules.mdc` Rule P3; `schemas/lean-dispatch.yaml` and `schemas/lean-report.yaml` (referenced by Rule CO-1).
- **devolaflow_impact:** *positive (no gap)* — DevolaFlow's choice is **deliberately** different and well-justified by the multi-agent context-isolation contract. Adopting mid-loop `AskUserQuestion` would violate P3 and break the "L3-only does work" invariant.
- **recommendation:** **no-op** — explicitly document this divergence in the registry `note:` field as `"divergent_by_design: gist's AskUserQuestion-in-loop pattern conflicts with DevolaFlow Rule P3 (Structured Messages); gist remains a useful single-agent reference, not multi-agent."`

#### Δ-christophera-05  ~1400-token bootstrap claim vs DevolaFlow SKILL.md ~2800-token estimate
- **observation:** Gist key_pattern: "~1400 token bootstrap prompt for self-improving system". DevolaFlow SKILL.md frontmatter declares `token_estimate: 2800` (read 2026-04-18) — exactly **2× the gist seed**. The two are not directly comparable: the gist seeds a *self-evolving single-agent system*, while DevolaFlow SKILL.md is the *entry point of a 4-layer orchestration framework*. The 2× ratio is therefore an **architecture overhead measurement**, not waste.
- **evidence:** gist README ("A single prompt (~1400 tokens), placed in a project's `.claude/CLAUDE.md`…"); `workflow-system/agent/SKILL.md` line 22 `token_estimate: 2800`.
- **devolaflow_impact:** *low (informational)* — validates that DevolaFlow's SKILL.md is in a reasonable order-of-magnitude range vs a comparable minimal seed (within 2×, not 10×). Rule SF-1 (≤500 lines) keeps this anchored.
- **recommendation:** **track** — when running the next EvoBench round (Rule SI-4), include a `bootstrap_token_overhead_ratio` metric (`SKILL.md tokens / 1400`) so future SKILL.md edits don't drift the ratio above ~2.5× without explicit justification.

#### Δ-christophera-06  Anti-proliferation + state-file + context-budget patterns are 100%-already-in-DevolaFlow
- **observation:** Three patterns documented as gist anti-patterns ("Don't create files preemptively", "End session without state update", "Mix user content into .claude/") map 1-to-1 onto existing DevolaFlow rules: anti-proliferation = `<making_code_changes>` rule + Rule CO-4; state engine = TaskDispatch/StatusReport schemas + `.local/research/` artifacts; workspace separation = Rule SF-5 (no absolute paths) + `workflow-system/agent/` vs project root convention.
- **evidence:** gist body §"Anti-Patterns" table; cursor IDE `<making_code_changes>` system rule (visible in current session); `.cursor/rules/context-optimization-rules.mdc` Rule CO-4; Rule SF-5 in `.cursor/rules/skill-format-rules.mdc`.
- **devolaflow_impact:** *positive (no gap)* — full coverage. Reinforces that the **L6 gap should not be re-classified upward** for v7.2.
- **recommendation:** **no-op** — confirm in next retrospective (`retrospective_v7.1_to_v7.2.md`) that christophera-bootstrap-seed's behavioural primitives are "already-addressed" per registry policy `staleness_indicators`.

---

## Reference 2 — `spring-ai-agent-skills` (`spring-ai-community/spring-ai-agent-utils`)

### 2.1  Current state snapshot (verbatim from upstream)

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | `"Spring AI (2026-01)"` | **`v0.7.0` published 2026-04-06T22:32:11Z** — adds `MemoryTools` (long-term agent memory) + mkdocs-based reference documentation site | `gh api repos/spring-ai-community/spring-ai-agent-utils/releases` |
| `stargazers_count` | n/a (registry only had `relevance_score: 3`) | **289** | repos API 2026-04-18 |
| `forks_count` | n/a | **63** | same |
| `open_issues_count` | n/a | **19** | same |
| `default_branch` | n/a | `main` | same |
| `repo updated_at` | n/a | `2026-04-17T15:53:08Z` (post-baseline metadata bump from social activity) | same |
| `pushed_at` (last code change) | n/a | `2026-04-09T03:23:53Z` | same |
| `latest commit` | n/a | `c07ea0c` 2026-04-09T03:23:43Z `Add documentation site link to README` | `gh api repos/spring-ai-community/spring-ai-agent-utils/commits?per_page=10` |
| `releases total` | n/a | **9** stable releases (no drafts, no prereleases): `v0.1.1, v0.2.0, v0.3.0, v0.4.0, v0.4.1, v0.4.2, v0.5.0, v0.6.0, v0.7.0` | releases API |
| `module structure` | n/a | **4 modules** post-`v0.5.0` extraction: `spring-ai-agent-utils` (core), `spring-ai-agent-utils-common` (subagent SPI), `spring-ai-agent-utils-a2a` (A2A protocol implementation), `spring-ai-agent-utils-bom` (BoM for version mgmt) | `gh api repos/spring-ai-community/spring-ai-agent-utils/contents/` |
| `description` | n/a | "A Spring AI library that brings Claude Code-inspired tools and agent skills to your AI applications." | repo metadata |

### 2.2  Version comparison vs baseline (acceptance criterion #5)

Baseline `last_known_version: "Spring AI (2026-01)"` corresponds to the v0.4.x release line (v0.4.2 was the last 2026-01 release at 2026-01-27T13:21:13Z). Three minor releases have shipped since:

| tag | published_at | headline change (verbatim from release body) | days vs 2026-04-11 baseline | **status at last_checked** |
|-----|--------------|----------------------------------------------|------------------------------|----------------------------|
| `v0.4.2` | 2026-01-27 | `**Full Changelog**: …compare/v0.4.1...v0.4.2` (patch only) | −74 days | **was current at baseline knowledge "2026-01"** |
| `v0.5.0` | 2026-02-24 | "Improve SkillsTool and update skills-demo example"; "Add workspace context support and simplify Read tool"; "Add CommandLineQuestionHandler for AskUserQuestionTool"; "Remove unused ToolContext parameters"; **"Extract subagent SPI into multi-modu…"** (truncated; expanded by repo structure showing new `spring-ai-agent-utils-common` module) | −46 days | **already shipped before baseline — registry was stale** |
| `v0.6.0` | 2026-03-30 | `**Full Changelog**: …compare/v0.5.0...v0.6.0` (no body content) | −12 days | **already shipped before baseline — registry was stale** |
| `v0.7.0` | 2026-04-06 | "Add **MemoryTools for long-term agent memory** by @tzolov in PR #35"; "Add ref docs as mkdocs by @tzolov in PR #38" | −5 days | **already shipped before baseline — registry was stale** |

**Critical registry hygiene finding:** the `last_known_version: "Spring AI (2026-01)"` string in `reference-dependencies.yaml` was **already 5 days behind reality at the moment of `last_checked: 2026-04-11`**. v0.7.0 had been published 5 days earlier and v0.5.0/v0.6.0 had been out for 46 / 12 days respectively. The registry entry conflated `last_checked` (the act of glancing at the URL) with `last_known_version` (the captured version string), and the latter was never refreshed during the 2026-04-11 sweep.

**Verdict on update_triggers** (registry: "Spring AI major releases" + "new agent provider integrations" + "progressive disclosure pattern refinements"):

- **Trigger #1 — Spring AI major releases:** *fired 3 times since 2026-01* (v0.5/v0.6/v0.7), but registry was not updated. Trigger needed retrospective firing.
- **Trigger #2 — new agent provider integrations:** *partially fired* — v0.5.0 extracted the **subagent SPI** into a separate module and added the **A2A protocol module** (`spring-ai-agent-utils-a2a`), enabling pluggable backends beyond the original Claude-only path.
- **Trigger #3 — progressive disclosure pattern refinements:** *not fired* (the SkillsTool's three-stage pattern remained `Discovery → Semantic Matching → Execution` per docs verified 2026-04-18 — no architectural shift).

### 2.3  Cross-check vs DevolaFlow integration points

Registered integration points for `spring-ai-agent-skills`:

1. `SKILL.md (progressive section loading)`
2. `adapter pipeline (vendor-agnostic validation)`

Mapping the spring-ai surface → current DevolaFlow surface:

| Spring AI primitive | Spring AI semantics | DevolaFlow equivalent (verified 2026-04-18) | Coverage |
|---------------------|---------------------|---------------------------------------------|----------|
| **`SkillsTool` three-stage progressive disclosure** | Per `docs/SkillsTool.md` (verified 2026-04-18): "1. **Discovery**: At startup, SkillsTool loads skill names and descriptions; 2. **Semantic Matching**: When a user request matches a skill's description, the AI invokes it; 3. **Execution**: The full skill content is loaded and the AI follows its instructions." Skill format = Markdown + YAML frontmatter (`name`, `description`). | **Strong match** — DevolaFlow SKILL.md uses the **identical** pattern: frontmatter `description:` + `triggers:` array (discovery), agent loads SKILL.md when triggered (activation), references `references/*.md` and `examples/*.md` are loaded on-demand (execution). Confirmed by SKILL.md frontmatter lines 8-23 and Rule SF-2 (required frontmatter keys including `description` for trigger conditions). | ~100% |
| **`SubagentDefinition / Resolver / Executor / Type` SPI** (v0.5.0) | Pluggable subagent backends; ships Claude `markdown-defined local` and A2A `remote agent orchestration` implementations | **Partial match** — DevolaFlow's `Task` tool exposes a fixed enum of `subagent_type` values (`generalPurpose, explore, shell, cursor-guide, best-of-n-runner`) — pluggability is at the **adapter** level (Cursor / Codex / Claude / Copilot), not at the subagent-type level inside one adapter. | ~60% |
| **`AutoMemoryTools` + `AutoAutoMemoryToolsAdvisor`** (v0.7.0, NEW) | Persistent file-based long-term memory: typed memory files (`user`, `feedback`, `project`, `reference`) in a sandboxed directory + `MEMORY.md` index. Companion `AUTO_MEMORY_TOOLS_SYSTEM_PROMPT.md` instructs agent on when/how to use the tools. Optional `memoryConsolidationTrigger` for periodic summarisation. | **Aspirational only** — DevolaFlow `workflow-system/agent/knowledge/index.md` mentions `learnings/operational.jsonl` ("auto-loaded via context profiles if enabled") but **the file does not exist in the repo today** (per T04 Δ-karpathy-02 evidence). No `MEMORY.md`-style index, no typed memory files, no consolidation trigger. | ~10% |
| **`TaskTools` extensible sub-agent system with multi-model routing** (v0.4.0) | "Multi-model routing and pluggable backends" per README §"Task orchestration & multi-agent" | **Strong match** — DevolaFlow `Task` tool already supports `model_hint: "balanced/quality/cost/speed"` field on TaskDispatch (per cross-task references) and ADR-001 cache layout pins this position. | ~95% |
| **`AskUserQuestionTool` with `CommandLineQuestionHandler`** (v0.5.0) | Interactive Q&A during agent execution, with pluggable handler | **Divergent by design** — same divergence as Δ-christophera-04: DevolaFlow Rule P3 prohibits free-form mid-loop user dialogue; equivalent functionality is concentrated at L0 mode-switch boundaries. | divergent |
| **mkdocs-based reference documentation** (v0.7.0) | Reference docs published as a static documentation site (`docs/` + `mkdocs.yml`) | **Different stack** — DevolaFlow uses `workflow-system/human/demo/` + `scripts/generate_human_docs.py` (per Rule CP-3 §"Canonical 7" file #5) producing EN/ZH HTML demos. No mkdocs adoption planned. | divergent (each ecosystem-appropriate) |
| **Vendor-agnostic portability** (key_pattern in registry) | Spring AI itself supports OpenAI / Anthropic / Gemini / etc. as backends; spring-ai-agent-utils inherits portability across vendors that implement Spring AI's `ChatClient` SPI | **Strong analog** — DevolaFlow ships 4 adapters (Cursor / Codex / Claude / Copilot) per Rule CP-5, each within its own budget. Coverage at the **agent-platform** level rather than the **LLM-vendor** level (since Cursor/Codex/Claude internally manage vendor selection). | ~85% (different abstraction altitude) |

### 2.4  Delta items (5-field schema)

#### Δ-spring-ai-01  Registry `last_known_version` was already stale at the moment of `last_checked`
- **observation:** `last_known_version: "Spring AI (2026-01)"` did not match upstream reality at the time the entry was last_checked (2026-04-11). v0.5.0 (2026-02-24), v0.6.0 (2026-03-30), and v0.7.0 (2026-04-06) had **all** shipped before the check, but the version field was never refreshed. This is a registry hygiene defect, not an upstream change.
- **evidence:** `gh api repos/spring-ai-community/spring-ai-agent-utils/releases --jq '.[] | {tag,published_at}'` returned 9 releases including v0.5.0/v0.6.0/v0.7.0 with timestamps `2026-02-24T09:39:40Z`, `2026-03-30T22:15:34Z`, `2026-04-06T22:32:11Z`; `reference-dependencies.yaml` line 417 still shows `last_known_version: "Spring AI (2026-01)"`.
- **devolaflow_impact:** *medium* — affects Rule CP-7 (Pre-Commit Verification) integrity for any future tooling that programmatically diffs `last_known_version` strings. A single stale entry signals that the 2026-04-11 sweep may not have rigorously refreshed all 19 entries.
- **recommendation:** **refresh-registry** — set `last_known_version: "v0.7.0 (2026-04-06): MemoryTools + mkdocs site; preceded by v0.6.0 (2026-03-30) and v0.5.0 (2026-02-24): subagent SPI extraction"`, bump `last_checked: 2026-04-18`, add `releases_total: 9`. **Procedural follow-up:** L0 of the v7.2.0 self-update workflow should add a registry-hygiene checklist requiring `last_known_version` to be a verifiable upstream string (tag / release name / SHA), not a vague time window.

#### Δ-spring-ai-02  No NEW upstream activity since 2026-04-11 baseline; pre-baseline activity was significant
- **observation:** No releases and no commits to `main` between `2026-04-11` (baseline) and `2026-04-18` (this survey). The latest commit `c07ea0c` (2026-04-09T03:23:43Z) is **2 days before** baseline. The repo `updated_at: 2026-04-17` reflects social activity (stars, watchers), not code. Therefore **the actual upstream surface to integrate against is fully encapsulated by v0.7.0**.
- **evidence:** `gh api repos/spring-ai-community/spring-ai-agent-utils/commits?per_page=10` — top commit `c07ea0c | 2026-04-09T03:23:43Z`; all 9 listed commits predate 2026-04-11; `pushed_at: 2026-04-09T03:23:53Z` from repo metadata.
- **devolaflow_impact:** *low* — there is no urgency window. v0.7.0 has been stable for 12 days as of this survey.
- **recommendation:** **no-op for upstream tracking** + **track for v7.2 design** — the integration question is "do we adopt MemoryTools-style memory?" (see Δ-spring-ai-04), not "do we chase a moving target?".

#### Δ-spring-ai-03  Three-stage progressive disclosure (Discovery → Semantic Matching → Execution) is verbatim-confirmed in current SkillsTool docs
- **observation:** The baseline key_pattern `"three-stage progressive disclosure: discovery→activation→execution"` is **exactly** the model documented in `spring-ai-agent-utils/docs/SkillsTool.md` (verified 2026-04-18): "How Skills Work: 1. **Discovery**: At startup, SkillsTool loads skill names and descriptions; 2. **Semantic Matching**: When a user request matches a skill's description, the AI invokes it; 3. **Execution**: The full skill content is loaded and the AI follows its instructions." DevolaFlow SKILL.md frontmatter implements the same pattern: `description:` (lines 25-29) + `triggers:` (lines 8-20) drive discovery; agent activates the skill on trigger match; references/examples are loaded on-demand during execution.
- **evidence:** `gh api repos/spring-ai-community/spring-ai-agent-utils/contents/spring-ai-agent-utils/docs/SkillsTool.md` content (decoded base64, fetched 2026-04-18); `workflow-system/agent/SKILL.md` lines 1-30 (Read 2026-04-18); Rule SF-2 in `.cursor/rules/skill-format-rules.mdc` mandating `description` semantics.
- **devolaflow_impact:** *positive (no gap, validates existing approach)* — DevolaFlow is **already aligned** with Spring AI's progressive disclosure pattern. The registered L7 gap "Spring AI progressive disclosure for SKILL.md" is therefore best characterised as "validation reference, not work item" (which matches the original gap classification "Validates existing approach; low effort but low impact (SKILL.md is 430 lines, within budget)" per `S01-T06-synthesis.md` line 124).
- **recommendation:** **no-op (close gap as VALIDATED)** — propose moving L7 from "open" to "validated_by_external_reference" status in the v7.2.0 retrospective. Do not invest engineering time in re-implementing what is already correctly done.

#### Δ-spring-ai-04  v0.7.0 `AutoMemoryTools` + `AutoAutoMemoryToolsAdvisor` — a NEW pattern not in the registry baseline
- **observation:** v0.7.0 (2026-04-06) introduced a long-term agent memory subsystem **not present in any prior release** and **not captured in the registry's `key_patterns` list**. Per the README (verified 2026-04-18): `AutoMemoryTools` provides "Persistent, file-based long-term memory that survives across conversations. Agents store typed memory files (`user`, `feedback`, `project`, `reference`) in a sandboxed directory and navigate them via a `MEMORY.md` index." Companion system prompt is bundled in the jar. `AutoAutoMemoryToolsAdvisor` wires it into the `ChatClient` advisor pipeline automatically with optional `memoryConsolidationTrigger` for scheduled summarisation. The pattern is explicitly inspired by Claude Code memory and the Claude API SDK memory tool.
- **evidence:** v0.7.0 release body: "Add MemoryTools for long-term agent memory by @tzolov in https://github.com/spring-ai-community/spring-ai-agent-utils/pull/35"; README §"Long-term memory" (`AutoMemoryTools`, `AutoAutoMemoryToolsAdvisor`); examples directory listing showing 3 new memory examples (`memory-tools-demo`, `memory-filesystem-tools-demo`, `memory-tools-advisor-demo`).
- **devolaflow_impact:** *medium* — directly relevant to the **H5 / H7 / L6** gaps (cluster: long-term learning, post-workflow rule-skill update, per-project customisation). Maps onto the existing `learnings/operational.jsonl` aspiration in `workflow-system/agent/knowledge/index.md`. The typed-file + `MEMORY.md`-index pattern is an external proof point that file-based memory is a viable design for the absent `learnings/` substrate.
- **recommendation:** **track for v7.2 candidate scope** — propose an additive design note (Rule SI-1 planning artifact) for v7.2.0 titled `learnings_substrate_design.md` that:
  1. Creates `workflow-system/agent/knowledge/learnings/` with an `index.md`-style catalog (DevolaFlow analogue of `MEMORY.md`).
  2. Defines the four typed entries DevolaFlow would actually use: `feedback` (user critiques captured at retrospective), `pattern` (recurring gate findings), `decision` (ADR-style records), `reference` (cross-project notes). Avoid Spring AI's `user` type (DevolaFlow has no per-user identity).
  3. Wires `gate/reinforcement.py::findings_to_reinforcement()` to optionally append a `pattern` entry when a finding repeats N times across rounds (cheap; reuses existing instrumentation).
  Defer **implementation** to a later wave so v7.2 maintains scope discipline; the design note alone closes the H5 documentation debt.

#### Δ-spring-ai-05  v0.5.0 Subagent SPI extraction + A2A protocol module — pluggable-backend pattern worth tracking
- **observation:** v0.5.0 (2026-02-24) extracted the subagent contract into a dedicated module `spring-ai-agent-utils-common` exposing `SubagentDefinition`, `SubagentResolver`, `SubagentExecutor`, `SubagentType` SPI interfaces, and shipped a separate `spring-ai-agent-utils-a2a` module implementing the SPI over the A2A (agent-to-agent) protocol for remote orchestration. This is a clean separation of "what is a subagent" from "how is it invoked" — orthogonal to DevolaFlow's current adapter abstraction (which is layered above the entire SKILL+rules bundle, not at the subagent-invocation level).
- **evidence:** v0.5.0 release body fragment: "Extract subagent SPI into multi-modu…" (truncated by API); confirmed by current top-level structure `gh api repos/spring-ai-community/spring-ai-agent-utils/contents/` showing modules `spring-ai-agent-utils-common`, `spring-ai-agent-utils-a2a`, `spring-ai-agent-utils-bom`, `spring-ai-agent-utils`; README §"Project Structure" diagram explicitly labels `spring-ai-agent-utils-common` as "Shared subagent SPI (interfaces & records)".
- **devolaflow_impact:** *low–medium* — DevolaFlow's `Task` tool exposes a fixed `subagent_type` enum hardcoded in the Cursor adapter (`generalPurpose, explore, shell, cursor-guide, best-of-n-runner`). A pluggable SPI would let host adapters register custom subagent types. This is theoretically interesting for the M2 (model-hint routing) gap, but DevolaFlow does not currently own the `Task` tool implementation — it only **uses** the Cursor-provided one. So adoption would require coordinating with the host adapter, not just a DevolaFlow internal change.
- **recommendation:** **track** (defer to v7.3+ adapter-layer work). Add to `gap_ids` list as a **referenced pattern** for the M2 gap rather than a new work item. Capture in the registry `key_patterns` for spring-ai: extend with `"pluggable subagent SPI: SubagentDefinition/Resolver/Executor/Type with reference A2A implementation"`.

#### Δ-spring-ai-06  Vendor-agnostic portability claim is structurally true at the Spring AI ecosystem level, not at the spring-ai-agent-utils library level
- **observation:** Baseline key_pattern: "vendor-agnostic portability across OpenAI/Anthropic/Gemini". This is **inherited from Spring AI's `ChatClient` abstraction**, not implemented inside spring-ai-agent-utils itself. The spring-ai-agent-utils tools work with whatever ChatClient backend Spring AI supports (OpenAI, Anthropic, Gemini, Bedrock, Ollama, etc.). The library does not contain per-vendor adapter code; vendor portability is a **transitive property** of the host framework choice. This is structurally analogous to how DevolaFlow's adapter portability (Cursor/Codex/Claude/Copilot) is implemented at the build pipeline (`build-skill` per Rule CP-5), not inside individual rule files.
- **evidence:** README §"Quick Start" example wires only `ChatClient chatClientBuilder` without naming any vendor; project structure shows zero `openai/` `anthropic/` `gemini/` per-vendor packages.
- **devolaflow_impact:** *positive (no gap, structural parallel)* — confirms DevolaFlow's adapter-pipeline approach (Rule CP-5) is the correct altitude for vendor-portability concerns. Per-vendor logic does not belong in SKILL.md or rules.
- **recommendation:** **no-op** — annotate the registry `key_patterns` to clarify the abstraction altitude: change `"vendor-agnostic portability across OpenAI/Anthropic/Gemini"` to `"vendor-agnostic portability inherited from Spring AI ChatClient SPI (analogous to DevolaFlow's adapter pipeline at build-skill level)"`. This avoids future surveys mistaking the absence of per-vendor code for a gap.

---

## Summary table

| ref | deltas raised | recommended actions | net registry change for v7.2 | proposed gap-id touches |
|-----|---------------|---------------------|------------------------------|-------------------------|
| `christophera-bootstrap-seed` | 6 (Δ-christophera-01..06) | refresh registry (stars, revisions, frozen-since); track validation_status; otherwise no-op (DevolaFlow already exceeds gist on 4 of 7 mapped patterns) | bump `last_checked: 2026-04-18`, set `last_known_version: "v1 (29 stars, 2 revisions both 2026-02-05, 7 forks, 3 comments)"`, add `validation_status: "author-acknowledged hypothesis (untested as of 2026-04-18)"` and `note: "divergent_by_design: AskUserQuestion-in-loop pattern conflicts with Rule P3 (Structured Messages)"`; **keep `relevance_score: 3`** | **L6 unchanged** (still open, but framed as "post-installation customisation gap, not loop-semantics gap"); **H7 satisfied-in-spirit** by existing `gate/reinforcement.py` |
| `spring-ai-agent-skills` | 6 (Δ-spring-ai-01..06) | refresh registry (CRITICAL: was already stale at last_checked); document AutoMemoryTools as new pattern; close L7 as VALIDATED | bump `last_checked: 2026-04-18`, set `last_known_version: "v0.7.0 (2026-04-06): MemoryTools + mkdocs site; preceded by v0.6.0 (2026-03-30) and v0.5.0 (2026-02-24): subagent SPI extraction"`, add `releases_total: 9`, extend `key_patterns` with "pluggable subagent SPI" and "AutoMemoryTools long-term memory (typed files + MEMORY.md index)", clarify "vendor-agnostic" altitude; **keep `relevance_score: 3`** | **L7 → VALIDATED-by-external-reference** (close in v7.2.0 retrospective); new design note proposed for v7.2 against **H5/H7** cluster (`learnings_substrate_design.md`); **M2** gets a referenced pattern (Subagent SPI) without new work item |

## Procedural finding (cross-cutting both refs)

Spring AI's registry entry was confirmed **stale at the moment of `last_checked: 2026-04-11`** (Δ-spring-ai-01). This suggests the v7.1 reference sweep may have updated `last_checked` dates without rigorously verifying `last_known_version` strings. Recommended addition to the v7.2.0 self-update workflow's L0 dispatch: a registry-hygiene precondition that requires `last_known_version` to be a **verifiable upstream string** (release tag, commit SHA, gist revision sha, or paper DOI/arXiv version) before bumping `last_checked`. Ties into Rule SI-7 (External Reference Protocol).

## Caveats & method notes

- All upstream content was fetched via `gh api ...` (authenticated against `github.com/shendeguize`) after a brief unauthenticated `curl` rate-limit hit at 02:38 UTC; thereafter all GitHub REST and GraphQL calls used the authenticated path. Direct `gist.github.com/...` HTML scraping consistently timed out from this environment (2 attempts, both `curl --max-time 15`); the GraphQL `Gist` type was used for `stargazerCount`, `forks.totalCount`, and `comments.totalCount`.
- The 27-stars baseline was taken as authoritative per the task spec; the GraphQL `stargazerCount: 29` is the verified current value.
- Per task constraints (`max_files: 6 writable (need 1)` and `NO modifications to DevolaFlow source`), no file outside the owned path was modified. Five files were `Read` from the DevolaFlow repo for the cross-check (`workflow-system/agent/knowledge/reference-dependencies.yaml`, `workflow-system/agent/SKILL.md`, `.local/research/v7.2.0_refs/delta-T04.md` for structure alignment, `.local/research/S01-T06-synthesis.md` for gap-id semantics, `.local/research/v7.0.0_context_compression_research.md` for prior-survey context).
- Sibling tasks: **T05** (vexp / scion / skillrouter) and **T06** (4 periodic refs at score=4) own different output paths under `.local/research/v7.2.0_refs/` and were not touched.
- Three release bodies that referenced PR numbers (`v0.7.0` PR #35 and #38; `v0.5.0` 5 PRs) were not deep-inspected; pull-request bodies could provide finer architectural detail but exceed the score=3 / 2700-second budget.
- `reference_repos_survey.md` (2026-04-13) was not re-read in full because T04 already documented its limitations on a sibling reference (karpathy gist); the same caveats are assumed to apply.
