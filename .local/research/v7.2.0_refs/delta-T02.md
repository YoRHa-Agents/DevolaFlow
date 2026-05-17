---
task_id: S01.W01.T02
title: "v7.2.0 Reference Delta Survey — Active Tracking (relevance_score=4, group 1)"
team: Research
role: reference-delta-survey
status: complete
devolaflow_version_context: "7.1.1"
target_version: "7.2.0"
references_covered:
  - get-shit-done
  - gstack
  - caveman
last_updated: "2026-04-18"
---

# T02 — Reference Delta Survey (relevance_score=4, group 1)

## Summary Table

| Reference | Old `last_known_version` | New observed state | Top delta | Recommendation |
|---|---|---|---|---|
| `get-shit-done` (gsd) | `v1.35.0` (2026-04-11) | **v1.37.1** (2026-04-17) — two minor releases shipped | `gsd-read-injection-scanner` PostToolUse hook + tiered agent size-budget enforcement (XL 1600 / Large 1000 / Default 500) + parallel `discuss-phase` across independent phases | **monitor** (1 import candidate: agent size-budget enforcement); refresh `last_known_version` to `v1.37.1`, keep `relevance_score: 4` |
| `gstack` | `v0.16.3.0` (2026-04-13) | No releases page; main-branch active (74,979 stars vs prior baseline) — `/learn` skill schema and `Operational Self-Improvement` reflex confirmed first-party | `/learn` operational-learnings JSONL schema is `{skill,type,key,insight,confidence(1-10),source,files?,ts}` with key+type dedup; per-skill reflective `Operational Self-Improvement` block triggers a learning log before completion | **import** (2 candidates: schema-aligned learnings dedup + reflective-log reflex); keep `relevance_score: 4`; mark version `main@2026-04-15` (no semver tags upstream) |
| `caveman` | `latest (2026-04)` (2026-04-11) | Active commits through **2026-04-15**: per-turn UserPromptSubmit reinforcement, natural-language activation/deactivation, `safeWriteFlag` parent-chain hardening, sensitive-file compression refusal, `caveman-help` skill, configurable default mode | Per-turn reinforcement hook + `Auto-Clarity` escape hatch on security/irreversible actions + sensitive-file refusal | **monitor** (1 import candidate: per-turn reinforcement of compression rules); refresh `last_checked` to `2026-04-18`, keep `relevance_score: 4` |

---

## 1. `get-shit-done` (gsd) — `https://github.com/gsd-build/get-shit-done`

### 1.1 Current State

| Field | Old (`reference-dependencies.yaml`) | Observed |
|---|---|---|
| `last_known_version` | `v1.35.0` | **`v1.37.1`** (latest tag, 2026-04-17 16:39 UTC) |
| `last_checked` | `2026-04-13` | `2026-04-18` |
| Repo activity | active | active — `v1.36.0` (2026-04-14) + `v1.37.0` (2026-04-17) + `v1.37.1` (2026-04-17) shipped since pin |
| Stars | (n/a in deps) | 54,449 |

Source: `https://github.com/gsd-build/get-shit-done/releases` (verbatim release titles `[1.37.0] - 2026-04-17`, `[1.36.0] - 2026-04-14`, hotfix `v1.37.1 — 17 Apr 16:39`).

### 1.2 Delta Items

#### D1.1 — `gsd-read-injection-scanner` hook (PostToolUse prompt injection detection)
- **What changed:** v1.37.0 added `gsd-read-injection-scanner` hook (PostToolUse prompt injection detection) ([#2201](https://github.com/gsd-build/get-shit-done/issues/2201)). v1.34.0 already shipped a hardened `gsd-prompt-guard.js` (invisible Unicode detection, encoding obfuscation, structural validation, entropy analysis); v1.37.0 extends defense-in-depth to **post-tool-call** scanning of returned content.
- **Source:** `https://github.com/gsd-build/get-shit-done/releases` ("v1.37.0 — Added — `gsd-read-injection-scanner` hook"); v1.34.0 release notes ("Prompt injection scanner hardened — invisible Unicode detection, encoding obfuscation, structural validation, entropy analysis (#1839)").
- **Integration target:** `src/devolaflow/` (no `lifecycle/` or `hooks/` module exists), and would land alongside `compressor.py` / `gate/` as a new `defense.py` or `hooks.py`. SKILL.md reference would be a new `references/security-hooks.md`.
- **Currently integrated?** **No.** `Grep` for `prompt[-_ ]injection|injection_scan|gsd-prompt|hook` across `src/devolaflow/` returns zero matches in code; only mentions are in `workflow-system/agent/knowledge/reference-dependencies.yaml` (this file's `key_patterns`) and security context within review rubrics (`code-rules-mapping.md` line 64: `security: input validation, injection prevention`). DevolaFlow has no SessionStart / PostToolUse / UserPromptSubmit hook surface at all.
- **Recommended action:** **monitor** — defense-in-depth value is real but DevolaFlow has no host-level hook surface; importing requires building a hook system first (out of scope for v7.2.0 patch release). Re-evaluate when v8.x considers a host-platform abstraction (Cursor + Claude Code + Codex + Copilot have different hook APIs).

#### D1.2 — Tiered agent size-budget enforcement (XL 1600 / Large 1000 / Default 500)
- **What changed:** v1.37.0 added "Agent size-budget enforcement — Tiered line-count limits (XL: 1 600, Large: 1 000, Default: 500) keep agent prompts lean; violations surface in CI" (issue [#2361](https://github.com/gsd-build/get-shit-done/issues/2361)) plus "Shared boilerplate extraction — Mandatory-initial-read and project-skills-discovery logic extracted to reference files, reducing duplication across a dozen agents".
- **Source:** v1.37.0 release notes "v1.37.0 Highlights" section in `https://raw.githubusercontent.com/gsd-build/get-shit-done/main/README.md` lines 92-96.
- **Integration target:** `tests/test_skill_md_under_500_lines` (already exists per SF-1 rule), but a tiered model would require `tests/test_reference_size_budgets.py` covering `workflow-system/agent/references/*.md` + `workflow-system/agent/examples/*.md`.
- **Currently integrated?** **Partially.** SF-1 rule already enforces `SKILL.md ≤ 500 lines` (verified via `wc -l` and `test_skill_md_under_500_lines`). DevolaFlow has only one tier; gsd has three (XL=1600, Large=1000, Default=500) with CI surfacing.
- **Recommended action:** **import** — extend SF-1 to a tiered budget mirroring gsd's taxonomy: keep `SKILL.md ≤ 500` as Default tier; permit `references/*.md` to grow to 1000 (Large); permit `examples/*.md` to grow to 1600 (XL). Add a CI test that iterates the file lists in `scripts/sync_cursor_skill.py` and asserts each file's line count against its tier. Low risk, high SKILL-format hygiene value.

#### D1.3 — Parallel `discuss-phase` across independent phases + `gsd-graphify` knowledge graph
- **What changed:** v1.37.0 added "Parallel discuss across independent phases ([#2268](https://github.com/gsd-build/get-shit-done/issues/2268))". v1.36.0 added "`/gsd-graphify` integration — Knowledge graph for planning agents, enabling richer context connections between project artifacts ([#2164](https://github.com/gsd-build/get-shit-done/pull/2164))" and "`gsd-pattern-mapper` agent — Codebase pattern analysis agent".
- **Source:** v1.37.0 + v1.36.0 release notes; gsd v1.36.0 "What's New" section.
- **Integration target:** `workflow-system/agent/SKILL.md` wave-coordination modes; `references/execution-protocol.md` (parallel dispatch logic); potentially `workflow-system/agent/knowledge/index.md` (graph adjacency between knowledge entries).
- **Currently integrated?** **Partially.** DevolaFlow already does parallel L2 Wave dispatch (the current self-update workflow has 7 parallel research tasks running per the predecessor summary in this dispatch), so the `discuss-phase` parallelism pattern is already covered semantically. The knowledge graph (`/gsd-graphify`) has **no** counterpart — `workflow-system/agent/knowledge/index.md` is a flat catalog with no graph structure.
- **Recommended action:** **monitor** — knowledge-graph adjacency is interesting for future cross-reference recall (see also tracked `vexp` AST graph pattern in `reference-dependencies.yaml#periodic_monitoring`), but redundant with `vexp`'s tree-sitter+SQLite approach. Park until the Karpathy wiki gist (`karpathy-llm-wiki`, score=3) gets re-evaluated for graph extension.

#### D1.4 — Inline execution for small plans (skip subagent overhead)
- **What changed:** v1.36.0 changed "Inline execution for small plans — Default to inline execution, skip subagent overhead for small plans ([#1979](https://github.com/gsd-build/get-shit-done/issues/1979))". Couples with v1.36.0 "Prior-phase context optimization — Limited to 3 most recent phases and includes `Depends on` phases ([#1969](https://github.com/gsd-build/get-shit-done/pull/1969))".
- **Source:** v1.36.0 release notes "Changed" section.
- **Integration target:** `src/devolaflow/task_adaptive_selector.py` (decomposition decision); `workflow-system/agent/context_profiles.yaml` (`decomposition_mode` overrides per task type); `workflow-system/agent/SKILL.md` Stage 2 / Wave decomposition gate.
- **Currently integrated?** **Partially.** DevolaFlow has `decomposition_mode: [single, sub_agents]` in `task-dispatch.schema.yaml` (lines 29-33) and `sub_agent_context_budget: 5000` per profile in `context_profiles.yaml` (line 332, 472, 656, 740, 822, 1112), but the trigger is task-type-based, not "size of plan"-based. The "small plan = inline" heuristic is a complementary lever.
- **Recommended action:** **monitor** — DevolaFlow's existing decomposition gate (`src/devolaflow/gate/`) is the right home, but adding a "plan-size" heuristic risks double-counting decisions already encoded in `context_profiles.yaml`. Defer until empirical EvoBench data shows over-decomposition on small task lists.

#### D1.5 — Configurable `claude_md_path` + project-local skill discovery
- **What changed:** v1.36.0 added "Configurable `claude_md_path` — Custom CLAUDE.md path setting ([#2010](https://github.com/gsd-build/get-shit-done/issues/2010), [#2102](https://github.com/gsd-build/get-shit-done/pull/2102))" and "Project skills awareness — 9 GSD agents now discover and use project-scoped skills ([#2152](https://github.com/gsd-build/get-shit-done/pull/2152))" and "Global skills support — Support `~/.claude/skills/` in `agent_skills` config ([#1992](https://github.com/gsd-build/get-shit-done/issues/1992))".
- **Source:** v1.36.0 release notes "Added" section.
- **Integration target:** `scripts/install.sh` (Cursor + Claude install logic), `.cursor/skills/install-devola-flow/SKILL.md`, `workflow-skill.yaml`.
- **Currently integrated?** **Yes (mostly).** DevolaFlow's `install-devola-flow` skill (per `Recently viewed files`) already targets both `~/.cursor/skills/devola-flow/` and `~/.claude/skills/devola-flow/`; CP-3 rule documents the 11-location version sync; bytewise mirror to `.cursor/skills/devola-flow/` is in place via `scripts/sync_cursor_skill.py`. Only the *configurable* path is missing — DevolaFlow assumes the canonical install paths.
- **Recommended action:** **skip** — configurable paths add a customization surface DevolaFlow does not need; the canonical paths in CP-3 are stable and tested across `tests/test_version.py`. Re-evaluate only if a user reports needing a non-canonical install location.

### 1.3 Relevance Score Refresh
- **Old:** `4`
- **Recommended:** `4` (unchanged) — gsd remains the closest analog to DevolaFlow's "L0 orchestrator + L3 Task Agent + gates" architecture; v1.37.0's tiered agent size-budget pattern (D1.2) directly improves DevolaFlow's SF-1 rule.
- **Refresh:** `last_known_version: v1.37.1`, `last_checked: 2026-04-18`. Add `update_triggers` entry: "agent size-budget tier changes in `agents/*.md` frontmatter".

---

## 2. `gstack` — `https://github.com/garrytan/gstack`

### 2.1 Current State

| Field | Old (`reference-dependencies.yaml`) | Observed |
|---|---|---|
| `last_known_version` | `v0.16.3.0` | **No semver tags / no GitHub Releases page** ("There aren't any releases here") — repo uses team-mode auto-update and `~/.claude/skills/gstack/bin/gstack-update-check` instead |
| `last_checked` | `2026-04-13` | `2026-04-18` |
| Repo activity | active | very active — 74,979 stars (large delta from any v0.16.x baseline) |
| Tools / skills count | 23 | 23+ (`/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/plan-devex-review`, `/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/devex-review`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`, `/pair-agent`) — **34 listed in current README install snippet** |

Source: `https://raw.githubusercontent.com/garrytan/gstack/main/README.md` lines 49 (full skill list in install paste), 188-237 (per-skill descriptions).

### 2.2 Delta Items

#### D2.1 — `/learn` skill: confirmed JSONL schema + key+type deduplication
- **What changed:** The pinned baseline already documents "operational learnings JSONL: {skill, type, key, insight, confidence}" but `/learn`'s SKILL.md (`https://raw.githubusercontent.com/garrytan/gstack/main/learn/SKILL.md`) reveals a fuller schema and an explicit dedup rule: `~/.gstack/projects/{slug}/learnings.jsonl` with entries `{"skill","type","key","insight","confidence":N,"source","files":[...],"ts":...}` (verbatim from the `gstack-learnings-log` invocation in `Operational Self-Improvement` block). Stats use `{key, type}` as a dedup key with last-write-wins on `ts`. Types observed: `pattern / pitfall / preference / architecture / tool / operational`. Confidence is **1-10 integer** in gstack vs **0.0-1.0 float** in DevolaFlow's `Learning` dataclass.
- **Source:** `learn/SKILL.md` lines 433 (`gstack-learnings-log '{"skill":"SKILL_NAME","type":"operational","key":"SHORT_KEY","insight":"DESCRIPTION","confidence":N,"source":"observed"}'`) and lines 677-704 (Stats dedup logic in Bun snippet).
- **Integration target:** `src/devolaflow/learnings.py` (Learning dataclass), `workflow-system/agent/knowledge/learnings/operational.jsonl` (currently empty file, verified — `Read` returns "File is empty.").
- **Currently integrated?** **Schema-divergent.** DevolaFlow's `Learning` schema (verbatim from `src/devolaflow/learnings.py` lines 51-73): `{stage, task_type, key, insight, confidence: float (0.0-1.0), rule_id, timestamp, ttl_days, source_task_id, +v2 ADR-005 fields: confidence_half_life_days, last_accessed, pinned_for_session, promotion_count}`. Differences: DevolaFlow uses `stage` (not `skill`), uses `task_type` (not `type`), uses **0-1 float confidence** (not 1-10 int), has no `files[]` and no `source` field. **No dedup pass on key+type** — the v2 promotion/decay system is timestamp/access-driven instead.
- **Recommended action:** **import** — three additive changes, preserve schema backward compatibility:
  1. Add an optional `files: list[str] = field(default_factory=list)` field to `Learning` dataclass (mirrors gstack's `files:["FILE1"]`) — enables stale-file detection per gstack's `learn prune` flow ("If any referenced files are deleted, flag: STALE: [key] references deleted file [path]" — verbatim from `learn/SKILL.md` lines 614-616).
  2. Add an optional `source: str = ""` field with values `{observed, user-stated, promoted}` — explicit provenance per CO-2 verbatim-extraction principle.
  3. Add a key+type dedup helper `dedup_learnings(entries) -> list[Learning]` that returns the latest-`timestamp` entry per `(task_type, key)` pair — this is what gstack's `BY_TYPE` stats compute. Couples with existing `prune_learnings`, does not change wire format.
- All three are additive (P6 cache-layout invariant unaffected; schemas are not in `lean-dispatch.yaml`/`lean-report.yaml`). Coverage stays ≥80% per CP-2.

#### D2.2 — Reflective `Operational Self-Improvement` block before completion
- **What changed:** Every gstack skill ends with a self-reflection block: "Before completing, reflect on this session: Did any commands fail unexpectedly? Did you take a wrong approach and have to backtrack? Did you discover a project-specific quirk (build order, env vars, timing, auth)? ... If yes, log an operational learning. ... A good test: would knowing this save 5+ minutes in a future session? If yes, log it." (verbatim from `learn/SKILL.md` lines 422-438).
- **Source:** `learn/SKILL.md` lines 422-438; same block appears in every gstack specialist skill per the SKILL contract.
- **Integration target:** `workflow-system/agent/SKILL.md` (L3 Task Agent execution protocol section), `workflow-system/agent/references/execution-protocol.md` (closing/cleanup phase), `schemas/lean-report.yaml` (already has `decisions:` block — extend with optional `learnings:` block).
- **Currently integrated?** **No.** DevolaFlow's `lean-report.yaml result_status_spec` already mirrors gstack's `Completion Status Protocol` (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED — verbatim match in `schemas/lean-report.yaml` line 174), but there is no reflective-log reflex. `workflow-system/agent/knowledge/learnings/operational.jsonl` is empty, suggesting no learnings have ever been captured automatically. The L3 agent never reflects-then-logs.
- **Recommended action:** **import** — add a "Pre-Completion Reflection" subsection to `references/execution-protocol.md` that mandates: (a) check for unexpected command failures in the session, (b) check for backtracking, (c) check for project-specific quirks, (d) if any of (a)-(c) yields a 5+min-savings insight, append to `workflow-system/agent/knowledge/learnings/operational.jsonl` via `capture_learning()`. Couples with D2.1 (`source: "observed"` provenance). Triggered only when `state == DONE | DONE_WITH_CONCERNS` so failed/blocked tasks don't pollute the log.

#### D2.3 — Per-skill `allowed-tools` ACL frontmatter
- **What changed:** The pinned baseline documents this pattern. Verified verbatim in `learn/SKILL.md` lines 15-23: `allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion, Glob, Grep]`.
- **Source:** `learn/SKILL.md` frontmatter lines 15-23.
- **Integration target:** `workflow-system/agent/references/team-roles.md` (per-team Tools/Skills section), `schemas/task-dispatch.schema.yaml` (new optional `allowed_tools` field on the `context` block).
- **Currently integrated?** **No.** `team-roles.md` lines 93-96 list per-role tools as **prose** (`Tools/Skills: WebSearch, WebFetch, Read, Glob, Grep, SemanticSearch, Write, explore subagent type`) but does not have a structured `allowed_tools` ACL on the dispatch schema. `Grep` for `allowed_tools|allowed-tools|tool_acl` across the workspace returns only `reference-dependencies.yaml` (this very entry).
- **Recommended action:** **monitor** — this is a P1 (Dispatcher-Not-Implementer) tightening lever, and the rule already says "L0-L2 MAY use Read, Glob, Grep, SemanticSearch ... MUST NOT use Write, StrReplace, Shell ... or EditNotebook to implement". An ACL field would make this **enforceable at dispatch time** rather than rule-text-only. But adding an `allowed_tools` enum to `task-dispatch.schema.yaml` is a P6 boundary change (new top-level-adjacent key) and would touch `schemas/task-dispatch.schema.yaml`, `schemas/lean-dispatch.yaml`, plus `compressor.py` validators. Defer to v7.3 unless an L0-L2 P1 violation is observed in EvoBench.

#### D2.4 — Cross-model second-opinion (`/codex` skill)
- **What changed:** `/codex` skill provides "independent code review from OpenAI Codex CLI. Three modes: review (pass/fail gate), adversarial challenge, and open consultation. Cross-model analysis when both /review and /codex have run" (verbatim from README line 230). Couples with `/pair-agent` cross-agent browser coordination.
- **Source:** `README.md` lines 230, 263-273.
- **Integration target:** `src/devolaflow/gate/scorer.py` (new `independent_review_score` dimension), `workflow-system/agent/references/team-roles.md` (Review team workflow extension).
- **Currently integrated?** **No.** DevolaFlow's `EXTENDED_DIMENSION_WEIGHTS` (verbatim from `gate/scorer.py` lines 38-46) already has 7 dimensions but no `independent_review` slot. The convergence loop (`gate/convergence.py`) is single-model.
- **Recommended action:** **skip** — overlaps directly with already-tracked `primelocus-hydra` (periodic_monitoring, score=4: "strength-based model routing: Claude=architecture, Gemini=critique, Codex=impl") and `anthropic-advisor-tool` (active_tracking, score=5: "Sonnet+Opus advisor pairs"). gstack's `/codex` adds nothing new beyond what `hydra` and the Anthropic advisor tool already cover. Surfaces in T01 (advisor tool) and T05/T06/T07 (hydra), not here.

#### D2.5 — Skill structure: HARD GATE + Plan Mode safety + Confusion Protocol
- **What changed:** Three reinforcement patterns observed verbatim:
  - "**HARD GATE:** Do NOT implement code changes. This skill manages learnings only." (`learn/SKILL.md` line 560)
  - "**Confusion Protocol** ... STOP. Name the ambiguity in one sentence. Present 2-3 options with tradeoffs. Ask the user. Do not guess on architectural or data model decisions." (lines 384-395)
  - "**Plan Mode Safe Operations**" + "**Skill Invocation During Plan Mode**" (lines 477-515) — explicit safety zones, treat skill as executable instructions not reference material.
- **Source:** `learn/SKILL.md` lines 384-395, 477-515, 560.
- **Integration target:** `workflow-system/agent/SKILL.md` (Stage 2/3 gate sections, confusion-protocol stub), `workflow-system/agent/references/execution-protocol.md`.
- **Currently integrated?** **Partially.** DevolaFlow's P1 rule (`workflow-rules.mdc` Rule 1) is the same governance shape ("Dispatcher agents MUST NOT perform work directly. Only Task Agents execute actual work"). The `superpowers` reference (T01, score=5) already covers `<HARD-GATE>` tags. **Confusion Protocol** has no DevolaFlow analog: the `gate/` module enforces *post-execution* quality, not *pre-execution* ambiguity halts. `Plan Mode Safe Operations` is host-platform-specific (Claude Code only) — not portable.
- **Recommended action:** **monitor** — Confusion Protocol is the genuinely novel piece, but it overlaps strongly with `superpowers` already-tracked at score=5 (`<HARD-GATE>` tags, two-stage review, typed status protocol). Defer to T01's score-5 sibling task to consolidate.

### 2.3 Relevance Score Refresh
- **Old:** `4`
- **Recommended:** `4` (unchanged) — gstack's value to DevolaFlow concentrates in `/learn` schema (D2.1) and reflective-log reflex (D2.2); both are importable in v7.2.0.
- **Refresh:** `last_known_version: "main@2026-04-15"` (note: no semver tags exist upstream — recommend tracking by branch HEAD date instead). Add `update_triggers` entry: "schema field additions in `gstack-learnings-log` invocation across any specialist skill".

---

## 3. `caveman` — `https://github.com/JuliusBrussee/caveman`

### 3.1 Current State

| Field | Old (`reference-dependencies.yaml`) | Observed |
|---|---|---|
| `last_known_version` | `latest (2026-04)` | **`main@2026-04-15`** — most recent commit "chore: sync SKILL.md copies and auto-activation rules [skip ci]" (2026-04-15); no semver releases visible |
| `last_checked` | `2026-04-11` | `2026-04-18` |
| Repo activity | active | very active — 36,959 stars; ≥30 commits in 5 days (Apr 11 → Apr 15) |

Source: `https://github.com/JuliusBrussee/caveman/commits/main` (verbatim commit titles).

### 3.2 Delta Items

#### D3.1 — Per-turn reinforcement in UserPromptSubmit hook
- **What changed:** Three commits between Apr 11-12 ship per-turn reinforcement: "feat: add per-turn reinforcement to UserPromptSubmit hook" (Apr 12) and "Merge PR #119: per-turn reinforcement in UserPromptSubmit" (Apr 15). Couples with "fix: skip reinforcement for independent modes (commit/review/compress)" (Apr 12) and "fix: detect natural language activation/deactivation in mode tracker" (Apr 12).
- **Source:** `https://github.com/JuliusBrussee/caveman/commits/main` (verbatim commit titles, "Commits on Apr 12, 2026" + "Apr 15, 2026" sections).
- **Integration target:** `schemas/lean-dispatch.yaml` (`compression_intensity:` field already exists on line 34 of `task-dispatch.schema.yaml`; per-round reinforcement could augment it via the existing `applicable_rules.reinforcement` block on lines 74-91 of `task-dispatch.schema.yaml`); `src/devolaflow/gate/reinforcement.py` (already implements `findings_to_reinforcement()`).
- **Currently integrated?** **Partially.** DevolaFlow has **convergence-round reinforcement** (`gate/reinforcement.py`, `task-dispatch.schema.yaml` lines 74-91, SI-9 rule) — gate findings from round N feed round N+1. But this is round-level, not turn-level. There is no per-turn (per-message) reinforcement layer because DevolaFlow does not have a host-platform hook surface (verified: `Grep` for `UserPromptSubmit|PostToolUse|SessionStart` returns zero matches in `src/devolaflow/`).
- **Recommended action:** **monitor** — same blocker as D1.1 (no DevolaFlow hook surface). Convergence-round reinforcement is the per-iteration analog and is already P5/SI-9. Re-evaluate when v8.x considers a host-platform abstraction.

#### D3.2 — `Auto-Clarity` escape hatch on security/irreversible actions + sensitive-file refusal
- **What changed:** `caveman/SKILL.md` `## Auto-Clarity` section (verbatim): "Drop caveman for: security warnings, irreversible action confirmations, multi-step sequences where fragment order risks misread, user asks to clarify or repeats question. Resume caveman after clear part done." — example shows a `DROP TABLE users;` warning bypasses caveman compression. Apr 15 commit "fix(security): harden flag-file reads and refuse sensitive-file compression" extends this to `caveman-compress`: refuses to compress sensitive files.
- **Source:** `caveman/SKILL.md` lines under `## Auto-Clarity`; commit "Apr 15: fix(security): harden flag-file reads and refuse sensitive-file compression".
- **Integration target:** `schemas/lean-dispatch.yaml#compression_rules` (current `intensity_tiers` block, lines 169-179 — add a `bypass_conditions:` list); `schemas/lean-report.yaml#compression_rules` (mirror); `src/devolaflow/compressor.py` (decision point).
- **Currently integrated?** **No bypass mechanism.** DevolaFlow's `compression_rules` (lean-dispatch.yaml lines 146-179, lean-report.yaml lines 135-169) defines `preserve_list` (file_paths, error_messages_verbatim, metric_values, commit_hashes, acceptance_criteria, task_ids, artifact_references, version_strings) and `drop_list` (filler_phrases, hedging_language, etc.) and three intensity tiers, but **no escape hatch** for security/irreversible content. The `preserve_list` covers *fields* but not *content categories* like "security warning" or "destructive op".
- **Recommended action:** **import** — add a `bypass_conditions` list to `compression_rules` in both `lean-dispatch.yaml` and `lean-report.yaml`, with values `[security_warning, destructive_operation, multi_step_sequence_with_order_dependency, repeated_user_question]`. When any bypass condition matches, `compressor.py` returns the source verbatim and emits a one-line warning to the wave agent. Additive change (P6-safe — extends existing block, no new top-level key). Ship test in `tests/test_compressor.py::test_compression_bypass_conditions`. Resolves a real safety gap (e.g., `DROP TABLE` warnings could lose criticality under `aggressive` intensity today).

#### D3.3 — `caveman-help` skill + configurable default mode + intensity expansion (wenyan-lite/full/ultra)
- **What changed:** Apr 11 commits: "feat: add caveman-help skill for quick-reference card", "feat: make default caveman mode configurable", "feat: add 'off' default mode to disable auto-activation", "Expand caveman ruleset and add intensity levels". `caveman/SKILL.md` `## Intensity` table now lists 6 levels: lite, full, ultra, wenyan-lite, wenyan-full, wenyan-ultra. Pinned baseline only documented `lite/full/ultra`.
- **Source:** `caveman/SKILL.md` `## Intensity` section (verbatim 6-level table); commits Apr 11-12.
- **Integration target:** `schemas/lean-dispatch.yaml#intensity_tiers` (currently 3 tiers: minimal/standard/aggressive); `schemas/lean-report.yaml` mirror.
- **Currently integrated?** **3-tier vs 6-tier.** DevolaFlow has `[minimal, standard, aggressive]` (`lean-dispatch.yaml` line 179, default `standard`). caveman now has 6 tiers spanning English + classical Chinese. The Chinese tiers are **language-specific** (文言文 character compression) and not portable to mixed-language DevolaFlow contexts.
- **Recommended action:** **skip** — DevolaFlow's 3-tier model is intentionally minimal per CO-1 (Lean Message Format). caveman's 6-tier expansion serves human-readable output diversity; DevolaFlow's compression targets *machine-to-machine* dispatch payloads where 3 tiers map cleanly onto P6's stability requirements. Adding tiers for Chinese-character compression has no DevolaFlow workflow that benefits from it. Re-evaluate if DevolaFlow ever supports mixed-locale agent-to-agent communication.

#### D3.4 — Validate-then-fix loop (already pinned, no significant delta)
- **What changed:** Documented pattern verified verbatim in `caveman-compress/SKILL.md` lines 16-22: "compress → validate → cherry-pick fix (max 2 retries) → if still failing after 2 retries: report error to user, leave original file untouched". No structural change since pin.
- **Source:** `caveman-compress/SKILL.md` `## Process` section.
- **Integration target:** `src/devolaflow/compressor.py` — currently has `assert_dispatch_layout()` (verified: layout invariant validator) but no validate-then-fix retry loop on the *content* itself.
- **Currently integrated?** **Partially.** DevolaFlow validates layout (P6 / `assert_dispatch_layout`) but does not validate-then-fix the dispatch *body* against compression-rule conformance. The closest analog is `gate/convergence.py`'s round-level `compute_trend` + `detect_stagnation` (max-iterations bounded retry, P4 rule), but that is gate-level, not compression-level.
- **Recommended action:** **monitor** — extending `compressor.py` with a content-level validate-then-fix loop is genuinely valuable but couples with D3.2 (bypass conditions need to be validated too). Track jointly with D3.2; ship as a single v7.2 import bundle if D3.2 lands.

### 3.3 Relevance Score Refresh
- **Old:** `4`
- **Recommended:** `4` (unchanged) — caveman remains the cleanest deterministic-compression reference; D3.2 (bypass conditions) is the highest-value 1-day import.
- **Refresh:** `last_known_version: "main@2026-04-15"`, `last_checked: 2026-04-18`. Add `update_triggers` entry: "new entries in caveman/SKILL.md `## Auto-Clarity` section" + "any commit touching `caveman-compress/scripts/__main__.py`".

---

## Cross-Cutting Observations

### CC-1 — Three independent confirmations of the typed status protocol
DevolaFlow's `lean-report.yaml result_status_spec` enum `[DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED]` is now verbatim mirrored by gstack (`learn/SKILL.md` lines 397-403: "DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT"), already mirrored by `superpowers` (per pinned key_patterns), and semantically aligned with caveman's normal-mode escape hatch. **The 4-state convergence is now an industry pattern**, not a DevolaFlow-unique artifact. Action: cite this triple convergence in the v7.2 retrospective as evidence the abstraction is correct; **no code change required** but worth noting in `references/message-schemas.md` as a footnote.

### CC-2 — Hook surface is a structural blocker for security/per-turn reinforcement imports (D1.1, D3.1, partially D2.2)
Three of the highest-impact deltas surveyed (gsd's `gsd-read-injection-scanner` PostToolUse hook, caveman's per-turn UserPromptSubmit reinforcement, and gstack's `Operational Self-Improvement` block executed at every skill end) all require a host-platform hook abstraction DevolaFlow does not have. `Grep` for `SessionStart|PostToolUse|UserPromptSubmit` across the workspace returns only adapter mentions and rule references. Three host platforms have three different hook APIs (Cursor `hooks.json`, Claude Code `~/.claude/hooks/`, Codex `.codex/hooks.json`). Action: park this as an explicit v8.x discovery — **do not attempt a hook abstraction in v7.2** — but document the gap in `.local/research/v7.2.0_refs/` cross-reference notes for the L0 Project Agent's roll-up.

### CC-3 — Learnings infrastructure is half-built and currently dormant
DevolaFlow's `Learning` dataclass has 13 fields (9 v1 + 4 v2 ADR-005), `capture_learning()` / `load_relevant_learnings()` / `prune_learnings()` / `consolidate_session()` / `decay_confidence()` / `pin_learning_for_session()` are all implemented (verified in `src/devolaflow/learnings.py` `__all__`), but `workflow-system/agent/knowledge/learnings/operational.jsonl` is **empty** — verified by `Read` returning "File is empty.". The plumbing exists; the trigger to write into it does not. D2.1 (schema additions) and D2.2 (reflective-log reflex in `references/execution-protocol.md`) together would activate the dormant subsystem. Action: bundle D2.1 + D2.2 as the v7.2 "Learnings Activation" wave; expect the JSONL to start accumulating entries within 2-3 self-update workflow runs.

### CC-4 — Agent size-budget tiering is the cheapest SF-1 upgrade
gsd's tiered budget (D1.2: XL 1600 / Large 1000 / Default 500) is a near-zero-cost extension of DevolaFlow's existing SF-1 rule (verified: `tests/test_skill_md_under_500_lines` already enforces the Default tier). `references/*.md` (8 files) and `examples/*.md` (3 files) are currently held to the same 500-line ceiling with no tier distinction. Action: ship as a single PR — extend `scripts/sync_cursor_skill.py`'s existing file lists with per-file tier metadata and add `tests/test_reference_size_budgets.py`. Estimated ~40 lines of code, fully covered by SI-10's existing pre-commit checklist.

### CC-5 — `caveman-compress`'s compression-by-rule maps onto DevolaFlow's existing preserve_list/drop_list
The pinned key_pattern "deterministic compression-by-rule: explicit drop/preserve lists" is already implemented in DevolaFlow (`lean-dispatch.yaml` lines 146-179, `lean-report.yaml` lines 135-169) — both files have identical `preserve_list` + `drop_list` + `intensity_tiers` blocks. The remaining gap is **bypass conditions** (D3.2) and **content-level validate-then-fix loop** (D3.4). The validate loop already exists at gate/convergence level (P4 bounded retry); only the *compression-time* validate is missing. Action: this is an internal-consistency win — `lean-dispatch.yaml` and `lean-report.yaml` already share the rules; extending both with `bypass_conditions:` keeps that symmetry.

---

## Limitations

1. **No public release tags for `gstack`** — repo uses team-mode auto-update (`gstack-update-check`) instead of GitHub Releases. Tracked-version pinning by date+commit-SHA recommended; `last_known_version: "main@2026-04-15"` is the closest stable identifier this survey could obtain.
2. **GitHub `tree/` view returned empty content** for `garrytan/gstack/learn` and `gsd-build/get-shit-done/hooks` directory listings via `WebFetch`. Specific file contents (e.g., `caveman/SKILL.md`, `learn/SKILL.md`) were retrieved successfully via `raw.githubusercontent.com`. The `gates.md` reference file claimed in the gsd `update_triggers` returned 404 ("Error fetching URL, status code: 404 Not Found") — this implies gsd may have moved or renamed the gates taxonomy doc since the v1.34.0 baseline that introduced it (release notes verbatim: "Gates taxonomy — 4 canonical gate types (pre-flight, revision, escalation, abort) with phase matrix wired into plan-checker and verifier agents (#1781)").
3. **No EvoBench validation performed** — per task scope, this survey identifies deltas only. Recommended-action ratings (`import` / `monitor` / `skip`) are ranked by integration-cost-to-benefit, not by measured EvoBench impact. Per SI-4, any of the 3 marked-`import` items (D1.2, D2.1, D2.2, D3.2) requires a benchmark pass before merge.
4. **No cross-repo timing verification** — the survey took the latest visible state as of `2026-04-18 02:22 UTC`. Sibling tasks T01-T07 may produce contradictory findings if they fetch later commits during their own runs; the L0 roll-up should reconcile.
5. **`anthropic-coordination-blog` and other score-5 references** are out of scope for T02 (handled by T01). Two T02 deltas (D2.4, D2.5) are deferred to T01 because they overlap with `anthropic-advisor-tool` and `superpowers` respectively.
6. **DevolaFlow source code was inspected read-only** per task constraint; no integration code was written. All `Currently integrated?` answers are based on `Grep`/`Read`/`Glob` of the v7.1.1 codebase as of conversation start.
