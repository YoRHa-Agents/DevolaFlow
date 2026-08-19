# Reference Delta Survey — T03 (Karpathy Skills + Understand-Anything)

**Task:** S01.W01.T03 — research / reference-delta-survey
**DevolaFlow baseline:** v7.1.1
**Generated:** 2026-04-18
**Refs analyzed:** 3 (`andrej-karpathy-skills` × 2, `understand-anything`)
**Owned file:** `.local/research/v7.2.0_refs/delta-T03.md`

---

## 0. Summary Table

| # | Ref id (current) | URL | Resolves? | Last-checked → today | Last-known → current | Δ items | Top-line action |
|---|------------------|-----|-----------|----------------------|----------------------|---------|-----------------|
| 1 | `andrej-karpathy-skills` (alias `karpathy/`) | `https://github.com/karpathy/andrej-karpathy-skills` | **NO — HTTP 404** | 2026-04-13 → 2026-04-18 | "latest (2026-04)" → repo does not exist | 1 metadata-fix + duplicate consolidation | **Delete entry** — URL was never valid; consolidate into the forrestchang entry |
| 2 | `andrej-karpathy-skills` (forrestchang) | `https://github.com/forrestchang/andrej-karpathy-skills` | YES | 2026-04-13 → 2026-04-18 | "latest (2026-04)" → plugin `1.0.0`, head sha `c9a44ae` (2026-04-15) | 6 (3 confirmed, 2 new artifact, 1 metadata) | **Update entry** — adopt new artifacts (`EXAMPLES.md`, `skills/karpathy-guidelines/SKILL.md`, `.claude-plugin/`); 4 principles unchanged so DevolaFlow integration points still valid |
| 3 | `understand-anything` | `https://github.com/Lum1104/Understand-Anything` | YES | 2026-04-14 → 2026-04-18 | `1.0.0` → no tagged release; head sha `aebd6dc` (2026-04-17, 9 commits since) | 5 (4 new capabilities + 1 architecture shift) | **Update entry + raise to score 5** — major capability surface (10-language tree-sitter, 7 multi-platform install paths, `/understand-knowledge` for Karpathy LLM wikis); explicit overlap with NineS deserves an ADR |

**Headline finding:** the *“two karpathy-skills repos divergence”* signal the dispatch flagged is **a non-divergence** — the supposed `karpathy/andrej-karpathy-skills` upstream **does not and never did exist**; only the forrestchang repo is real. See cross-cutting §4 for the consolidation recommendation.

---

## 1. Reference 1 — `karpathy/andrej-karpathy-skills` (the documented "upstream")

### Current State

- **HTTP status:** `404 Not Found` for both `https://github.com/karpathy/andrej-karpathy-skills` and the GitHub API endpoint `https://api.github.com/repos/karpathy/andrej-karpathy-skills`.
- **Web search:** zero result lists `karpathy` as the owner; every secondary article (Dev.to, Playbooks, AIBit, AIToolly) attributes the *repo* to `forrestchang` and only attributes the *ideas* to Andrej Karpathy via [his X post](https://x.com/karpathy/status/2015883857489522876) (no Karpathy-owned GitHub artifact).
- **Cross-check with the existing `karpathy_skills_analysis.md` (2026-04-13):** the older analysis itself declared the canonical URL as `forrestchang/andrej-karpathy-skills` even when summarising "Karpathy-inspired" skills, confirming that the `karpathy/` URL is metadata residue, not a real upstream.
- **Conclusion:** there is **no upstream/fork pair** to compare; the dispatch's premise of "two karpathy-skills repos that may have diverged from each other" is false. They cannot diverge because there is only one.

### Delta Items

#### DELTA-KARP-UPSTREAM-01

- **id:** DELTA-KARP-UPSTREAM-01
- **type:** METADATA_FIX (REMOVE)
- **summary:** documented `repo_url: https://github.com/karpathy/andrej-karpathy-skills` returns HTTP 404 — repo does not exist.
- **evidence:**
  - `WebFetch https://github.com/karpathy/andrej-karpathy-skills` → `Error fetching URL, status code: 404`
  - `WebSearch karpathy andrej-karpathy-skills github` → top 4 hits all point to `forrestchang/andrej-karpathy-skills`
  - Internal artifact `.local/research/karpathy_skills_analysis.md:10` already records `repo_url: "https://github.com/forrestchang/andrej-karpathy-skills"` as canonical
- **recommendation:** **delete** entry at `workflow-system/agent/knowledge/reference-dependencies.yaml:169-189` (the `karpathy/`-URL block); fold its `key_patterns` and `devolaflow_integration_points` into the forrestchang entry (see DELTA-KARP-FRSCH-06 below). **Priority: P1** (incorrect URL is a tracking-system bug; biweekly polling is silently 404-ing). **Effort: S** (single YAML edit).

### Relevance Refresh

- **Recommended status:** **DROP** the entry from `active_tracking` (consolidate into forrestchang). No standalone tracking value because it has nothing to track.

---

## 2. Reference 2 — `forrestchang/andrej-karpathy-skills`

### Current State

| Field | 2026-04-13 (last_checked) | 2026-04-18 (today) | Δ |
|-------|---------------------------|--------------------|---|
| `stargazers_count` | 22,770 | 54,853 | **+141%** in 5 days |
| `forks_count` | not recorded | 4,649 | (note dispatch summary said `0`; the API field is `4649`) |
| `subscribers_count` | not recorded | 312 | — |
| `pushed_at` | implied 2026-04-13 | 2026-04-15T17:47:20Z | +2 days |
| Top-level files | `CLAUDE.md`, `README.md` | `CLAUDE.md` (2,357 B), `README.md` (5,814 B), **`EXAMPLES.md` (14,838 B, NEW since 2026-01-31)**, **`.claude-plugin/`** (NEW), **`skills/`** (NEW) | +3 paths |
| Recent commits since 2026-04-13 | n/a | `c9a44ae` "Update README with project and social media links" (2026-04-15), `331a3ac` same (2026-04-15), `9ec6bef` "Fix readme" (2026-04-15), `fb8fdb0` "Add Multica project link at the top of README (#51)" (2026-04-13) | 4 commits — all README/social, **no behavioural-rule changes** |
| Plugin distribution | (not yet packaged) | `.claude-plugin/plugin.json` v `1.0.0`; `.claude-plugin/marketplace.json` id `karpathy-skills`, source `./`, category `workflow`; `skills/karpathy-guidelines/SKILL.md` (2,518 B, frontmatter `name: karpathy-guidelines`, `license: MIT`) | NEW since 2026-01-31 (per commits `3cf049f`, `68b67a5`, `aa4467f`) |

### Delta Items

#### DELTA-KARP-FRSCH-01

- **id:** DELTA-KARP-FRSCH-01
- **type:** CONFIRMED
- **summary:** the four canonical principles are unchanged in wording and order.
- **evidence:** verbatim in both `CLAUDE.md` and `skills/karpathy-guidelines/SKILL.md` (same SHA-relative content): "1. Think Before Coding", "2. Simplicity First", "3. Surgical Changes", "4. Goal-Driven Execution"; the four documented `key_patterns` ("Think Before Coding: assumption surfacing…" etc., reference-dependencies.yaml:221-224) still match upstream verbatim modulo the colon-summary phrasing.
- **recommendation:** keep all four DevolaFlow integration points referenced at `reference-dependencies.yaml:228-231`. **No code change required.** Bump `last_checked: "2026-04-18"`. **Priority: P3.**

#### DELTA-KARP-FRSCH-02

- **id:** DELTA-KARP-FRSCH-02
- **type:** NEW (artifact)
- **summary:** `EXAMPLES.md` (14.8 KB) added 2026-01-31 (PR #7) — worked examples for each of the 4 principles, including a "What LLMs Do (Wrong) → What Should Happen" diff format.
- **evidence:**
  - GitHub contents API lists `EXAMPLES.md` size `14838` at SHA `6c4283595e031f158870cd38e4e39d281332d621`
  - Commit `60770839…` (`HOLYKEYZ` PR #7, 2026-01-31): "Add examples of common mistakes on each principles"
  - File body contains 8 sub-examples (2 per principle) plus an "Anti-Patterns Summary" table and a "Key Insight" closing — all in the form of code/diff side-by-side
- **recommendation:** treat as **review-rubric source material** for the existing `references/team-roles.md` "Simplicity Check" table (line 413). The `EXAMPLES.md` "Anti-Patterns Summary" maps almost 1:1 onto rows we may want there:
  - "Strategy pattern for single discount calculation" → augment our `Unnecessary abstraction` row
  - "Reformats quotes, adds type hints while fixing bug" → augment a (currently-missing) `Style drift` row
  - "Silently assumes file format, fields, scope" → confirms our `assumptions` field doctrine

  **Action:** add an explicit pointer in `references/team-roles.md` Simplicity-Check section: *"For worked examples, see external reference forrestchang/andrej-karpathy-skills `EXAMPLES.md`."* Do NOT inline the examples (license MIT, but SF-1 line budget and SF-5 absolute-path discipline argue for a single relative reference). **Priority: P2. Effort: S.**

#### DELTA-KARP-FRSCH-03

- **id:** DELTA-KARP-FRSCH-03
- **type:** NEW (artifact)
- **summary:** repository now ships as a **Claude Code plugin** with `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` and a Skill packaged under `skills/karpathy-guidelines/SKILL.md` (frontmatter: `name: karpathy-guidelines`, `description: …Use when writing, reviewing, or refactoring code…`).
- **evidence:**
  - `.claude-plugin/plugin.json` v `1.0.0`, `skills: ["./skills/karpathy-guidelines"]`
  - `.claude-plugin/marketplace.json` exposes plugin id `karpathy-skills`, marketplace id `karpathy-skills`, category `workflow`
  - Two-step install in README: `/plugin marketplace add forrestchang/andrej-karpathy-skills` then `/plugin install andrej-karpathy-skills@karpathy-skills`
  - Commits `b26f4c3c`, `3cf049fa`, `68b67a5b`, `aa4467f0` (all 2026-01-31 → 2026-02-16) added/fixed plugin and marketplace manifests
- **recommendation:** **comparison interest only** — this is the same plugin packaging pattern superpowers and gstack use; we already track those (`reference-dependencies.yaml:32, 79`). The delta is informative for the (separate) PluginRegistry / Gap 6 design conversation but does not require a DevolaFlow source change. **Action:** record in §3.2 of `understand_anything_analysis_report.md` (or future PluginRegistry ADR) as a third concrete data point alongside superpowers and gstack on "single-skill plugin via `.claude-plugin/`". **Priority: P3. Effort: S.**

#### DELTA-KARP-FRSCH-04

- **id:** DELTA-KARP-FRSCH-04
- **type:** CONFIRMED (description format)
- **summary:** the new `SKILL.md` description follows the WHEN/WHY pattern that DevolaFlow rule SF-2 mandates ("Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.").
- **evidence:** `skills/karpathy-guidelines/SKILL.md` frontmatter `description:` field; matches our SF-2 rationale verbatim ("describe WHEN/WHY to activate the skill (trigger conditions), not WHAT the skill does").
- **recommendation:** **independent external validation of SF-2.** No source change. Optionally reference this as a real-world example of SF-2 compliance in `references/meta-framework.md` (only if a Skill-format-rules clarification is in scope for v7.2.0). **Priority: P3. Effort: S.**

#### DELTA-KARP-FRSCH-05

- **id:** DELTA-KARP-FRSCH-05
- **type:** METADATA_FIX
- **summary:** `last_known_version` should be a real version string now (`plugin.json` declares `1.0.0`); `note:` should be updated to mention the EXAMPLES.md and plugin packaging.
- **evidence:** `.claude-plugin/plugin.json` `"version": "1.0.0"`, `.claude-plugin/marketplace.json` `metadata.version: "1.0.0"`; current `reference-dependencies.yaml:218` records `last_known_version: "latest (2026-04)"`.
- **recommendation:** update entry as follows:
  - `last_checked: "2026-04-18"`
  - `last_known_version: "plugin v1.0.0 (head c9a44ae, 2026-04-15)"`
  - extend `key_patterns` with one entry: `"worked examples (EXAMPLES.md): wrong vs surgical diffs per principle"`
  - extend `update_triggers` with `"EXAMPLES.md additions/changes"` and `"plugin.json version bump"`
  - update `note:` to `"complements karpathy-llm-wiki (different focus). Now ships as Claude Code plugin (.claude-plugin/) plus EXAMPLES.md worked-examples corpus (added 2026-01-31)."`

  **Priority: P2. Effort: S.**

#### DELTA-KARP-FRSCH-06

- **id:** DELTA-KARP-FRSCH-06
- **type:** METADATA_FIX (consolidation)
- **summary:** consolidate the two duplicate entries (`reference-dependencies.yaml:169-189` with broken `karpathy/` URL and `:214-233` with valid `forrestchang/` URL) into a single canonical entry; the four DevolaFlow integration points listed under the broken entry are strictly richer than those under the working entry and must be preserved.
- **evidence:**
  - Broken entry (`:184-188`) lists 4 integration points: `schemas/task-dispatch.schema.yaml (explicit_assumptions field)`, `schemas/lean-dispatch.yaml (assumptions entry)`, `references/team-roles.md (Simplicity Check rubric)`, `references/execution-protocol.md (verification-first micro-plan)` — all 4 verified present in repo (`schemas/task-dispatch.schema.yaml:48`, `schemas/lean-dispatch.yaml:110`, `references/team-roles.md:413`, `references/execution-protocol.md:151`).
  - Working forrestchang entry (`:228-231`) lists only 3 points and mis-cites `references/team-roles.md (review rubric)` rather than the more specific `(Simplicity Check rubric)`.
- **recommendation:** delete the broken `karpathy/` entry; on the surviving forrestchang entry, **replace** `devolaflow_integration_points` with the union (the broken entry's 4 items, since they are strict superset and more specific). **Priority: P1. Effort: S.** Couples with DELTA-KARP-UPSTREAM-01.

### Relevance Refresh

- **Score:** keep `4` (could argue `5` given +141% star growth in 5 days, but content is still 4 stable principles; relevance is qualitative, not popularity-based).
- **Cadence:** keep `active_tracking` biweekly. Repo's commit cadence is now ~weekly (mostly README); content layer (CLAUDE.md, SKILL.md, EXAMPLES.md) has not changed since 2026-01-31.
- **Reclassification:** none.

---

## 3. Reference 3 — `Lum1104/Understand-Anything`

### Current State

| Field | 2026-04-14 (last_checked) | 2026-04-18 (today) | Δ |
|-------|---------------------------|--------------------|---|
| `stargazers_count` | (not recorded; ~6.5K at the time of NineS analysis per `understand_anything_analysis_report.md` corollary) | 8,472 | growth continuing |
| `forks_count` | not recorded | 705 | — |
| `pushed_at` | 2026-04-14 (implied) | 2026-04-17T07:10:17Z | +3 days, 9 commits |
| `language` | not recorded | TypeScript (primary; was "Python-leaning" per NineS report) | **architecture shift** |
| `topics` | not recorded | `antigravity-skills`, `business-knowledge`, `claude-code`, `claude-skills`, `codex`, `codex-skills`, `gemini-cli-skills`, `karpathy-llm-wiki`, `knowledge-base`, `knowledge-graph`, `memory`, `opencode-skills`, `pi-agent`, `understandcode` | **massively broadened** |
| Tagged release | `1.0.0` (per dispatch) | **no GitHub release tag in API metadata; `releases_url` returns empty list** — only commit-pinned versions | metadata correction needed |
| Multi-platform install | (none documented in our `key_patterns`) | 10 platforms supported via `.claude-plugin/`, `.codex/`, `.opencode/`, `.openclaw/`, `.cursor-plugin/`, `.copilot-plugin/`, `.vscode/`, `.antigravity/`, `.gemini/`, `.pi/` install manifests | NEW capability surface |
| Slash-commands | (none in tracked patterns) | `/understand`, `/understand-dashboard`, `/understand-chat`, `/understand-diff`, `/understand-explain`, `/understand-onboard`, `/understand-domain`, `/understand-knowledge`, `/understand --auto-update` | NEW |
| Multi-agent pipeline | (none specified) | 7 named agents: `project-scanner`, `file-analyzer`, `architecture-analyzer`, `tour-builder`, `graph-reviewer`, `domain-analyzer`, `article-analyzer` | NEW (was 5 in NineS report; now 7 with `domain-analyzer` and `article-analyzer`) |
| Code extraction backend | LLM-generated regex (per recent commit messages) | bundled tree-sitter for 10 languages (TS, JS, Python, Go, Rust, Java, Ruby, PHP, C/C++, C#) | **architecture maturity step** |

### Delta Items

#### DELTA-UA-01

- **id:** DELTA-UA-01
- **type:** NEW (capability)
- **summary:** code-extraction backend switched from "LLM-generated throwaway regex" to a deterministic tree-sitter + PluginRegistry pipeline supporting 10 languages.
- **evidence:**
  - Commit messages (verbatim from API): `feat: file-analyzer uses bundled tree-sitter script instead of LLM-generated regex`; `feat: add bundled tree-sitter extraction script for file-analyzer agent`; `feat: export LanguageExtractor type and builtinExtractors from core package` — "Completes the language extractor architecture — 10 languages with tree-sitter support (TS, JS, Python, Go, Rust, Java, Ruby, PHP, C/C++, C#)."
  - PR #89 `feat: multi-language tree-sitter extractor architecture (10 languages)`
  - `pnpm-lock.yaml` chore commit confirms tree-sitter parsers bundled: `tree-sitter language parsers (c-sharp, cpp, go, java, php, python, ruby, rust)`
- **recommendation:** **directly informs DevolaFlow's research/analysis stage** (currently delegated to NineS, which is also tree-sitter-adjacent). Two integration moves to consider:
  1. **Cite as second external data point** in any future PluginRegistry ADR (alongside the karpathy-skills plugin manifest from DELTA-KARP-FRSCH-03) for "deterministic-extractor + plugin-loader" pattern.
  2. **For T05/T07 periodic-monitoring siblings (caveman, ruflo)** that own context-compression: note that Understand-Anything's tree-sitter approach gives a free precedent for "structure-aware" extraction the way `vexp` (periodic_monitoring entry `:294`) already proposes for our context profiles.

  **No source change in v7.2.0 unless Gap 6 / PluginRegistry advances.** **Priority: P3. Effort: M (if/when integrated).**

#### DELTA-UA-02

- **id:** DELTA-UA-02
- **type:** NEW (capability)
- **summary:** new `/understand-knowledge` command analyses Karpathy-pattern LLM wikis (e.g. our tracked `karpathy-llm-wiki` gist) into a force-directed knowledge graph with community clustering.
- **evidence:**
  - README §Features: "Point `/understand-knowledge` at a [Karpathy-pattern LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and get a force-directed knowledge graph with community clustering."
  - New agent `article-analyzer`: "Extract entities, claims, and implicit relationships from wiki articles (used by `/understand-knowledge`)"
  - Topics now include `karpathy-llm-wiki`
- **recommendation:** **direct cross-reference between two tracked entries**: this connects our `understand-anything` tracking entry to our `karpathy-llm-wiki` tracking entry (`reference-dependencies.yaml:147`). Add a `note:` to *both* entries: *"Cross-link: Lum1104/Understand-Anything `/understand-knowledge` consumes karpathy-pattern wikis as input."* **Priority: P3. Effort: S.**

#### DELTA-UA-03

- **id:** DELTA-UA-03
- **type:** NEW (capability)
- **summary:** `/understand-diff` provides "Diff Impact Analysis" — predicts which graph nodes a pending change set affects before commit.
- **evidence:** README §Features: "📊 Diff Impact Analysis: See which parts of the system your changes affect before you commit. Understand ripple effects across the codebase." Plus `/understand-diff` command block in README §Quick Start.
- **recommendation:** conceptual sibling to DevolaFlow's gate `reinforcement` mechanism (`src/devolaflow/gate/reinforcement.py`) — both convert "what-changed" into "what-must-happen-next." Worth referencing in a future v7.2.0 ADR if we extend reinforcement to consume a structural model of the diff. **Priority: P3 (advisory). Effort: not in T03 scope.**

#### DELTA-UA-04

- **id:** DELTA-UA-04
- **type:** NEW (distribution)
- **summary:** project now distributes for 10 platforms (Claude Code, Codex, OpenCode, OpenClaw, Cursor, VS Code + Copilot, Copilot CLI, Antigravity, Gemini CLI, Pi Agent), with auto-discovery manifests under platform-specific dotfolders.
- **evidence:** README "Multi-Platform Installation" table; `.claude-plugin/`, `.codex/`, `.opencode/`, `.openclaw/`, `.cursor-plugin/`, `.copilot-plugin/`, `.vscode/`, `.antigravity/`, `.gemini/`, `.pi/` directories implied by README install instructions; commit `45e56a4` "fix: allow /understand to target an arbitrary directory path … broke on alternative CLIs (e.g. OpenClaw) that set CWD to their own workspace directory" confirms multi-CLI runtime adaptation.
- **recommendation:** **directly relevant to our adapter pipeline** (`scripts/install.sh`, the four adapter outputs Cursor/Codex/Claude/Copilot per CP-5). Understand-Anything covers a strict superset of our 4 adapters — they target 10. Worth **examining their `.codex/`, `.copilot-plugin/`, `.cursor-plugin/` install scripts** for patterns DevolaFlow's `install.sh` could borrow (e.g., CWD-detection logic from commit `45e56a4`). **Action:** spawn no work in T03; flag for whoever owns adapter pipeline in v7.2.0. **Priority: P2 (for adapter pipeline owner). Effort: M.**

#### DELTA-UA-05

- **id:** DELTA-UA-05
- **type:** METADATA_FIX
- **summary:** `last_known_version: "1.0.0"` is fictional — repo has **no GitHub release tag** (API `releases_url` is empty); use commit SHA + date instead.
- **evidence:** `https://api.github.com/repos/Lum1104/Understand-Anything` response carries no `releases` array contents; `tags_url` returns nothing tracked. Head sha is `aebd6dc` at 2026-04-17.
- **recommendation:** update `reference-dependencies.yaml:235-253`:
  - `last_checked: "2026-04-18"`
  - `last_known_version: "head aebd6dc (2026-04-17)"`
  - extend `key_patterns` with: `"deterministic tree-sitter extractor (10 languages)"`, `"multi-platform plugin manifests (10 CLIs)"`, `"slash-command surface: /understand, /understand-dashboard, /understand-chat, /understand-diff, /understand-explain, /understand-onboard, /understand-domain, /understand-knowledge"`
  - extend `update_triggers` with: `"new /understand-* slash command added"`, `"new platform install manifest added"`, `"language extractor count changes"`
  - **raise `relevance_score` from 4 to 5** — capability surface now spans research, distribution, and reinforcement-adjacent domains; the `/understand-knowledge` ↔ `karpathy-llm-wiki` link makes it a load-bearing reference, not an isolated comparator.

  **Priority: P1. Effort: S.**

### Relevance Refresh

- **Score:** raise `4 → 5`. Justification: in 4 days the repo's surface area expanded along 4 of DevolaFlow's tracked dimensions simultaneously (analysis backend, distribution channels, adapter pattern, knowledge-graph ↔ tracked-gist linkage). Compare `anthropic-coordination-blog` (`:191`) which sits at 5: that entry is similarly cross-cutting but text-only, while Understand-Anything ships executable patterns we can lift.
- **Cadence:** keep `active_tracking` biweekly; nine commits in three days suggests this is a fast-moving repo, but ours is a delta survey, not a watchdog — biweekly is enough to catch capability-surface expansions.
- **Reclassification:** none.

---

## 4. Cross-Cutting Findings

### 4.1 The "two karpathy-skills repos" question — there is only one

The dispatch's opening framing — "Pay special attention to whether the two karpathy-skills repos have diverged from each other" — is **based on a metadata error** in `reference-dependencies.yaml`. There is no `karpathy/andrej-karpathy-skills` repo. The forrestchang repo *is* the canonical (and only) artifact; secondary articles uniformly call it "the Karpathy-inspired skills repo" (the *ideas* are Karpathy's, the *repo* is forrestchang's). Recommended fix is consolidation into a single entry — see DELTA-KARP-UPSTREAM-01 + DELTA-KARP-FRSCH-06.

This is **signal-rich** in a different way than the dispatch suggested: it surfaces a class of bug in our reference-tracking system where active polling of broken URLs can silently rot for weeks (the entry's `last_checked: 2026-04-13` was honoured even though the URL has been 404 since the entry was created). Suggest **adding a CI check** (T05/T07 sibling territory, not T03's owned scope) that runs `curl -fsI` against every `repo_url` in `reference-dependencies.yaml` and fails on non-2xx. **Priority: P2 (out-of-scope for T03 owned files; raise as v7.2.0 candidate via Wave dispatch).**

### 4.2 Understand-Anything ↔ NineS overlap — complementary, not competing

Both tools "analyse a codebase," but the overlap is shallower than it looks.

| Dimension | NineS | Understand-Anything |
|-----------|-------|---------------------|
| Primary output | Severity-classified findings (4 error / 6 warning / 12 info, per `understand_anything_analysis_report.md` §2) | Interactive knowledge graph (`.understand-anything/knowledge-graph.json`) + dashboard |
| Data model | Lints + complexity + agent-impact + context-economics rolled up to a score | Nodes (file/function/class) and edges (imports/calls/dependency) plus business-domain overlay |
| Consumer | Dispatcher agents reading findings JSON to plan reinforcement | Human dev exploring dashboard; or another agent walking the graph for `/understand-chat` |
| Cadence | One-shot `nines analyze` per audit | Build-once, incrementally update with `--auto-update` post-commit hook |
| Granularity | File / function thresholds | Node-level with parallel batches (5 concurrent, 20-30 files/batch) |
| Persistence | JSON in `.local/research/` (per repo) | Committed `.understand-anything/*.json` (shareable across team) |

**Read:** Understand-Anything is **structural / navigational** (graph you walk); NineS is **judgmental / actionable** (findings you fix). DevolaFlow already uses NineS at the `analyze` boundary (per CLAUDE.md and `nines.toml`). A useful future state would be **NineS findings annotated with Understand-Anything graph coordinates** — e.g., a high-complexity finding could surface "this function is on the critical path between X and Y" — but this is an ADR-level conversation, not a v7.2.0 source change.

**No DevolaFlow source change required from this overlap analysis.** Carry the comparison into the next iteration's gap analysis (SI-1 entry point) for whoever owns research-stage upgrades. **Priority: P3 (advisory).**

### 4.3 `understand-anything` ↔ `karpathy-llm-wiki` cross-link

Newly visible: Understand-Anything's `/understand-knowledge` command and `article-analyzer` agent are designed to ingest exactly the gist we already track at `reference-dependencies.yaml:147` (`karpathy-llm-wiki`). Two of our tracked entries now share an explicit data-flow relationship at the upstream-product level. See DELTA-UA-02 for the recommended bidirectional `note:` update.

### 4.4 Plugin packaging convergence

Three tracked or newly-surveyed repos now use the same `.claude-plugin/plugin.json` + `marketplace.json` shape: superpowers (`obra/superpowers`), gstack (`garrytan/gstack`), and forrestchang/andrej-karpathy-skills. Understand-Anything goes further with parallel manifests for 9 other CLIs. This is the *de-facto* schema for skill distribution. **DevolaFlow's `install.sh` and `.cursor/skills/devola-flow/` mirror layout (rule SF-3) is consistent with this**, but does not yet expose a `.claude-plugin/` manifest of its own. **Out-of-scope for T03; raise as a v7.2.0 candidate work-item ("Should DevolaFlow ship a `.claude-plugin/marketplace.json`?").**

### 4.5 No source modifications made

Per dispatch acceptance criterion 6, this artifact made **no modifications to DevolaFlow source**. All recommended changes are listed as actions for downstream tasks/waves. The only file written is the owned `.local/research/v7.2.0_refs/delta-T03.md`.

---

## 5. Limitations

1. **No upstream Karpathy repo to compare.** The dispatch's central question (fork-vs-upstream divergence) is unanswerable because the upstream is fictional. Treated this as the principal finding (cross-cutting §4.1) rather than padding with synthetic comparison.
2. **GitHub API metadata can lag.** Used live API responses (`repos/{owner}/{name}` and `commits?per_page=…`) but did not verify by cloning; rely on `pushed_at` and head SHA as freshness anchors.
3. **No NineS re-run on Understand-Anything.** The existing `.local/research/nines_understand_anything_analysis.json` is from 2026-04-14 (33,295 bytes); a fresh NineS run on commit `aebd6dc` could move the 22-findings count, but is out-of-scope for T03 (one-shot research, not benchmark).
4. **README is the architecture source-of-truth for Understand-Anything in this survey.** Did not download or inspect the actual TypeScript source of `packages/core/`; capability claims (`/understand-diff`, `/understand-knowledge` etc.) are from README + commit messages, not from runtime verification.
5. **No exhaustive `commits` walk.** Polled the most recent ~10 commits per repo; older history could harbour relevant deltas, but the dispatch's `last_checked` baselines are 5 and 4 days old respectively, so the recent-commits window is the appropriate one.
6. **Star/fork counts are descriptive, not prescriptive.** Cited only as freshness-of-attention signal; relevance scores are based on capability fit, not popularity.
7. **Cannot speak for sibling tasks T01/T02/T04-T07.** Read no other delta-T0X.md files (none exist yet at the time of this writing) and made no claim about their findings; this artifact is self-contained.

---

## 6. Acceptance Self-Check

- [x] File exists at owned path `.local/research/v7.2.0_refs/delta-T03.md`
- [x] All 3 references analyzed (§1, §2, §3)
- [x] Each delta item has the 5 standard fields: `id`, `type`, `summary`, `evidence`, `recommendation`
- [x] Divergence between the two karpathy-skills entries explicitly addressed (cross-cutting §4.1; conclusion: there is no second repo to diverge from)
- [x] understand-anything ↔ NineS overlap assessed (cross-cutting §4.2; verdict: complementary, not competing)
- [x] Zero modifications to DevolaFlow source (only this file under owned path)
