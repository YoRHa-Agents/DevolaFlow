# Reference Delta Survey — T05 (vexp + google-scion + skillrouter)

| field | value |
|-------|-------|
| task_id | S01.W02.T05 |
| role | research / reference-delta-survey |
| owned_path | `.local/research/v7.2.0_refs/delta-T05.md` |
| devolaflow_version | v7.1.1 |
| baseline_registry | `workflow-system/agent/knowledge/reference-dependencies.yaml` (snapshot 2026-04-11) |
| cutoff_check_date | 2026-04-18 |
| references_in_scope | 3 (periodic_monitoring, scores 4-5) |
| sources_modified | none (read-only research; no DevolaFlow source touched) |

---

## Reference 1 — `vexp` (vexp.dev)

### 1.1  Current state snapshot (verbatim from upstream)

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | `"commercial (2026)"` | **v1.3.11** (publicly released VS Code extension + `vexp-cli` on npm) | `https://vexp.dev/docs` header block "v1.3.11 · VS Code 1.85+ · 30 languages · 12 agents" |
| `open-source available?` | not captured; registry trigger was "open-source release or API availability" | **NO — still proprietary.** Distributed as a bundled VS Code extension (Rust daemon + MCP server bundled in `.vsix`) and a matching npm-installable CLI (`npm install -g vexp-cli`). No public source repository for the core. | `https://vexp.dev/docs` §Installation; `https://marketplace.visualstudio.com/items?itemName=Vexp.vexp-vscode`; `https://www.npmjs.com/package/vexp-cli` |
| `API availability` | none | **MCP server exposed locally** over stdio or `http://localhost:7821` (SSE). 11 MCP tools: `run_pipeline, get_context_capsule, get_impact_graph, search_logic_flow, get_skeleton, index_status, workspace_setup, submit_lsp_edges, get_session_context, search_memory, save_observation`. No remote/cloud API; zero network calls by design. | `https://vexp.dev/docs` §Manual configuration; `https://vexp.dev/` §MCP Tools |
| `supported agents` | "12 agent support" | **12 (confirmed)** — Claude Code, Cursor, Windsurf, GitHub Copilot, Continue.dev, Augment, Zed, Codex, Opencode, Kilo Code, Kiro, Antigravity. Config files auto-generated per agent (e.g. `.cursor/mcp.json`, `~/.claude.json`, `~/.codex/config.toml`). | `https://vexp.dev/docs` §Supported Agents |
| `language coverage` | "30 language" | **28 language rows listed** (`TS, JS, TSX/JSX, Python, Go, Rust, Java, C#, C, C++, Ruby, Bash, Kotlin, Scala, Swift, Dart, PHP, Elixir, Haskell, OCaml, Lua, R, Zig, HCL/Terraform, Objective-C, Dockerfile, Clojure, F#`). Marketing claims "30" — minor discrepancy; v1.2.30 was the batch that added the latest 18 languages. | `https://vexp.dev/docs` §Supported Languages |
| `token-reduction claim` | "65% fewer tokens" | **"65–70% average"** (docs); headline "74% fewer tokens per query" on interactive-demo for a single-call pipeline example. Skeleton mode cited as "70–90% reduction" when supporting files are skeletonised. | `https://vexp.dev/docs` §Introduction; `https://vexp.dev/` interactive demo + How-it-works step 03 |
| `published benchmark` | "+14pp task success rate (FastAPI benchmark)" | **Completely new benchmark published** — SWE-bench Verified, 100-task stratified subset, all agents on Claude Opus 4.5 with $3/task cost cap + 250-turn budget. Results table verbatim: `vexp+Claude Code 73.0% / $0.67 / 7–10 unique wins; Live-SWE-Agent 72.0% / $0.86; OpenHands 70.0% / $1.77; Sonar Foundation 70.0% / $1.98`. FastAPI +14pp number no longer surfaced on the site. Benchmark repo: `https://github.com/Vexp-ai/vexp-swe-bench`. | `https://vexp.dev/benchmark` |
| `storage & parsing` | "tree-sitter parsing with SQLite graph storage" | **Confirmed; elaborated.** `vexp-core` is a Rust daemon using tree-sitter grammars bundled in-binary (no download at runtime). Graph persisted locally to `.vexp/index.db` (SQLite, gitignored); a content-hash `manifest.json` is committed to git for teammate incremental rebuild. "34.8k nodes / 89.2k edges" displayed for a reference project; "< 15 s full index for 5,000 files", "< 500ms P95 capsule query". | `https://vexp.dev/` §How it works + §Architecture |
| `centrality/graph signal` | "AST dependency graph + centrality ranking for context selection" | **Confirmed, extended.** Hybrid scoring = FTS5 BM25 + TF-IDF cosine + graph centrality + recency decay + graph proximity − staleness penalty, with per-result `why` field (auditable per-component breakdown). Intent detection layer auto-selects strategy (`fix bug` → debug mode; `refactor` → blast-radius mode; `add feature` → modify mode). LSP bridge (v1.2+) supplements static tree-sitter edges with type-resolved call edges from VS Code LSP. | `https://vexp.dev/` §Smart Features; `https://vexp.dev/docs` §How it works |
| `distribution model` | n/a | **Freemium commercial.** `Starter = $0 forever` (≤ 2 000 nodes, single-repo, 7 MCP tools, 8 pipeline + skeleton calls/day); `Pro = $19/mo` (50 000 nodes, up to 3 repos, all 11 tools, CodeLens, intent detection). Pricing page confirms "No account required" for Starter. | `https://vexp.dev/` §Pricing |

### 1.2  Cross-check vs DevolaFlow integration points

Registry-declared integration points for `vexp`:

1. `context_profiles.yaml` (graph-distance-based section priority)
2. `src/devolaflow/task_adaptive_selector.py`

State of those points in v7.1.1 (verified 2026-04-18):

- **`src/devolaflow/task_adaptive_selector.py` (587 lines, read today):** section selection is **purely priority-bucketed by `section_priorities` from YAML** (`"critical" > "important" > "supplementary"`) with a token-budget cut-off (lines 256–305, `_build_priority_buckets` + `_select_sections_within_budget`). **No AST parsing, no dependency graph, no centrality, no graph-distance signal** anywhere in the module. The only dynamic signals are (a) plan-mode override (`apply_plan_mode_overrides`) and (b) round-based escalation (`apply_round_escalation`) — both static rule-table lookups.
- **`match_profile()` (lines 185–218):** uses pure string matching — "exact key > exact hint > longest-substring overlap". No retrieval, no ranking model.
- **`workflow-system/agent/context_profiles.yaml` (1 467 lines):** sections are registered with hard-coded `lines: "<start>-<end>"` ranges. Priority is a flat per-profile `section_priorities` map with the four tiers (`critical/important/supplementary/skip`). Grepping for `AST|tree-sitter|centrality|graph_distance|pivot|capsule` inside the file returns zero matches; only the word `budget` appears (referring to `token_budget`). **No graph-distance primitive is currently modelled.**

**Net:** the registry's integration-target phrasing "graph-distance-based section priority" describes a **capability DevolaFlow has not implemented**, not one to be aligned with. The vexp pattern remains a pure inspiration target, not an integration point.

### 1.3  Delta items (5-field schema)

> Schema: `What changed` · `Source` · `Integration target` · `Currently integrated?` · `Recommended action`

#### Δ-vexp-01  Vexp shipped a public distribution (VS Code Marketplace + npm) with version v1.3.11

- **What changed:** registry `last_known_version: "commercial (2026)"` was a year-tag; vexp is now concretely installable by any user via `code --install-extension Vexp.vexp-vscode` or `npm install -g vexp-cli`. Both distributions bundle the Rust daemon + MCP server — zero extra setup.
- **Source:** `https://vexp.dev/docs` ("v1.3.11 · VS Code 1.85+ · 30 languages · 12 agents"); `https://marketplace.visualstudio.com/items?itemName=Vexp.vexp-vscode`; `https://www.npmjs.com/package/vexp-cli` (all fetched 2026-04-18).
- **Integration target:** DevolaFlow skill/adapter build pipeline (optional: make vexp a *recommended optional MCP server* documented in `workflow-system/agent/plugins.yaml`, alongside existing NineS / ui-ux-pro).
- **Currently integrated?** **No.** `plugins.yaml` is referenced by `context_profiles.yaml` (`meta.nines_integration.plugin_registry` and `meta.ui_integration.plugin_registry`), and vexp is **not listed** there (Grep 2026-04-18 returns zero matches for `vexp` outside `.local/research/` and `reference-dependencies.yaml`).
- **Recommended action:** **refresh-registry** (bump `last_known_version` to `"v1.3.11 (VS Code ext + vexp-cli, proprietary)"`, `last_checked: 2026-04-18`) **plus small spike for v7.2.x** — add a vexp entry to `workflow-system/agent/plugins.yaml` as `recommended_optional` so L3 Task Agents operating on large codebases can enable it without DevolaFlow owning the implementation. Do **not** attempt to replicate its AST engine inside DevolaFlow — vexp is proprietary Rust, licence-locked.

#### Δ-vexp-02  New open benchmark: SWE-bench Verified 73% @ $0.67/task (replaces FastAPI +14pp claim)

- **What changed:** registry `key_patterns` say "65% fewer tokens and +14pp task success rate (FastAPI benchmark)". That number no longer appears on the site. The canonical vexp benchmark is now `SWE-bench Verified, 100-task stratified subset, Claude Opus 4.5, $3 cap, 250 turns`: `vexp+Claude Code 73.0% / $0.67 / 7–10 unique wins` vs `Live-SWE-Agent 72.0% / $0.86`, `OpenHands 70.0% / $1.77`, `Sonar Foundation 70.0% / $1.98`. The 65% token number persists as "65–70% average token reduction across 5 real codebases" (docs) but the **headline empirical claim has switched from FastAPI to SWE-bench**.
- **Source:** `https://vexp.dev/benchmark` (fetched 2026-04-18); published repo `https://github.com/Vexp-ai/vexp-swe-bench`.
- **Integration target:** `benchmarks/devolaflow_context/` — vexp's SWE-bench harness is now a defensible external reference for DevolaFlow's own EvoBench numbers (SI-4 regression guard).
- **Currently integrated?** **No.** `benchmarks/devolaflow_context/` uses in-repo scenarios (from `.cursor/rules/context-optimization-rules.mdc` §CO-5); no cross-reference to SWE-bench Verified exists in `tests/test_benchmarks.py`.
- **Recommended action:** **track-only for v7.2** — document the new vexp number in the v7.2.0 retrospective (SI-8) as external validation of the "context is the highest-leverage variable" thesis already asserted in `.local/research/v7.0.0_context_compression_research.md`. No code change required. Upgrade to **refresh-registry** (`key_patterns` field: replace "65% fewer tokens and +14pp task success rate (FastAPI benchmark)" with "65–70% token reduction (5-codebase average); 73% SWE-bench Verified Pass@1 at $0.67/task (Claude Opus 4.5)").

#### Δ-vexp-03  Graph-based ranking: DevolaFlow's `task_adaptive_selector.py` has zero graph signal

- **What changed:** this is a **persistent gap, re-confirmed**. vexp v1.3.11 documents its signal stack verbatim: `FTS5 BM25 + TF-IDF cosine + graph centrality + recency decay + graph proximity − staleness penalty` with LSP-bridge-enhanced edges. DevolaFlow's closest analog — `task_adaptive_selector.py` — uses (a) static per-profile priorities and (b) token budget. No code path computes a graph distance, centrality, or call-graph edge between SKILL.md sections or between dispatched files.
- **Source:** `src/devolaflow/task_adaptive_selector.py` (lines 185–218 `match_profile` pure-string; lines 256–305 `_select_sections_within_budget` priority-bucketed; no graph import) read 2026-04-18; `https://vexp.dev/` §Smart Features (vexp mechanism).
- **Integration target:** `src/devolaflow/task_adaptive_selector.py` — specifically, a future `_rank_files_by_graph_distance(seed_files: list[str]) -> list[tuple[str, float]]` helper that would take the L3 `owned_files` as seeds and score *other* repo files by distance in a cached call graph.
- **Currently integrated?** **No.** Registry phrasing "graph-distance-based section priority" describes an *unimplemented* capability.
- **Recommended action:** **track, do not port in v7.2.** Real AST/graph infrastructure would require adding a build-time indexer (tree-sitter dependency, SQLite cache, invalidation on file edit) that duplicates what vexp already does for free — and DevolaFlow is agnostic about the *target* codebase. The correct architectural move is **delegation**: document that if a user has vexp installed, L3 Task Agents MAY call `get_context_capsule` via MCP as a pre-step, rather than DevolaFlow reimplementing the machinery. Re-evaluate in v7.3.0 if vexp API proves stable.

#### Δ-vexp-04  LSP bridge, intent detection, and session memory are new architectural primitives

- **What changed:** three primitives not in the registry's documented patterns:
  1. **LSP bridge** (v1.2) — `submit_lsp_edges` MCP tool captures type-resolved call edges from the language server, supplementing static tree-sitter analysis.
  2. **Intent detection** — `run_pipeline` auto-selects search strategy from natural-language task description (`fix bug` → debug, `refactor` → blast-radius, `add feature` → modify).
  3. **Session memory** — `save_observation`, `search_memory`, `get_session_context` with auto-stale flagging when linked code changes. Cross-session hybrid search uses the same FTS5+TF-IDF+recency+proximity+staleness formula as capsule ranking.
- **Source:** `https://vexp.dev/` §Smart Features; `https://vexp.dev/docs` §MCP Tools.
- **Integration target:**
  - `src/devolaflow/learnings.py` (DevolaFlow's own session-memory analogue — `knowledge/learnings/operational.jsonl`).
  - `workflow-system/agent/SKILL.md` plan-mode / round-escalation logic (intent detection analogue).
- **Currently integrated?** **Partial overlap.** DevolaFlow has *operational learnings* (`learnings.py`, confidence-weighted JSONL) — conceptually the same as vexp's session memory minus the graph-anchored staleness flag. Plan-mode / round-escalation is a *3-way* static switch, not natural-language intent detection.
- **Recommended action:** **track** for v7.3+. The staleness-flag idea (memory entries marked stale when referenced code changes) is worth investigating for `learnings/operational.jsonl` — but requires DevolaFlow to hash/track referenced files, which it does not currently do.

#### Δ-vexp-05  Distribution model + pricing now concretely published (Starter Free / Pro $19)

- **What changed:** registry `last_known_version: "commercial (2026)"` is now resolvable to actual pricing: Starter free forever (≤ 2 000 nodes, single-repo, 7 MCP tools), Pro $19/mo (50 000 nodes, up to 3 repos, 11 MCP tools). A 14-day Pro trial is offered via code `BENCHMARK`.
- **Source:** `https://vexp.dev/` §Pricing.
- **Integration target:** external reference dependency ledger only.
- **Currently integrated?** **N/A** (purely informational).
- **Recommended action:** **refresh-registry** — note `distribution: "VSIX + npm (proprietary, freemium)"`, `node_limits_starter: 2000, node_limits_pro: 50000` under a new `pricing` sub-field if the schema is extended. No code impact.

### 1.4  Relevance refresh

- Current `relevance_score: 5` **holds**. vexp is the single clearest external validation of the "context engineering > model choice" thesis; its SWE-bench benchmark now has stronger evidence than at registry snapshot date. If anything, relevance is *up* because vexp's MCP-server shape is now concrete enough for a plug-in integration rather than a research-only reference.
- `source_type` in registry says `blog` — **update to `product` or `commercial_mcp_server`** (blog connotes one-off article; vexp is a live, versioned product with docs + benchmarks + pricing).
- `update_triggers`: drop `"open-source release or API availability"` (unlikely near-term; vexp is explicitly proprietary). Replace with `"new MCP tool added or removed"`, `"Pro tier node limit changed"`, `"new benchmark publication"`.

---

## Reference 2 — `google-scion` (GoogleCloudPlatform/scion)

### 2.1  Current state snapshot (verbatim from upstream)

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | `"experimental (2026-03)"` | **"experimental"** — still no tagged releases (`https://github.com/GoogleCloudPlatform/scion/releases` returns "There aren't any releases here"), but the release-notes microsite now publishes near-daily dated entries (earliest visible 2026-02-19; latest 2026-03-17). | `https://github.com/GoogleCloudPlatform/scion/releases`; `https://googlecloudplatform.github.io/scion/release-notes/` |
| `repo metadata` | n/a | **1 155 stars, 0 forks, 12 contributors, Apache-2.0, Go-primary.** Official README explicitly says "This is not an officially supported Google product." | `https://github.com/GoogleCloudPlatform/scion` (fetched 2026-04-18) |
| `org rehome` | n/a | **Project moved to GoogleCloudPlatform org on Mar 9, 2026** ("official transition of the project to the Google Cloud Platform organization, including a full module rename"). Previously lived elsewhere (module rename confirms). | `https://googlecloudplatform.github.io/scion/release-notes/` entry dated 2026-03-09 |
| `install path` | n/a | `go install github.com/GoogleCloudPlatform/scion/cmd/scion@latest` — requires Go toolchain, no pre-built binaries or containers yet. Users must build container images locally before first use. | `https://raw.githubusercontent.com/GoogleCloudPlatform/scion/main/README.md` §Quick Start |
| `core concept set` | "Grove concept (.scion directory) as project workspace" | **6 stable concepts**: `Agent, Grove, Template, Runtime, Hub, Runtime Broker`. Hub (central control plane for multi-machine orchestration) and Runtime Broker (machine offering its runtimes to a Hub) are **new primitives not in registry**. | README §Core Concepts |
| `harness set` | n/a | **4 documented harnesses**: Gemini CLI, Claude Code, OpenCode, Codex. ADK support added Feb 24, 2026 via a specialized runner entrypoint. Each harness gets `.claude/skills`, `.gemini/skills` merge-mounted (Mar 13, 2026, "Harness Skills for Templates"). | README §Key Features; release-notes 2026-03-13 / 2026-02-24 |
| `runtime list` | "Docker, Podman, Apple containers, Kubernetes" | **Confirmed + GKE specialisation.** Kubernetes runtime matured Mar 8, 2026 ("Stages 1-3: Parity, Production Hardening, Launch Readiness"); GKE-specific runtime added Feb 24, 2026 with Workload Identity integration. | release-notes 2026-03-08 / 2026-02-24 |
| `isolation mechanism` | "infrastructure-level agent isolation via git worktrees + containers" | **Confirmed + stronger.** For **hub-linked** groves (Mar 15, 2026) the mechanism *changed* from "standard cloning or local worktrees" to **`git init` + `git fetch`** ("transitioned hub-linked groves to strictly use a robust `git init` + `git fetch` strategy instead of standard cloning or local worktrees"). Local-only groves still use worktrees. tmpfs shadow mounts (Mar 8, 2026) prevent cross-agent access to `.scion` configs. | release-notes 2026-03-15 ("Hub-Linked Workspace Provisioning"); 2026-03-08 ("Agent Isolation & Grove Security") |
| `observability` | n/a | **Normalized OTEL telemetry across all harnesses** with `scion.harness`, `scion.model`, `scion.broker`, `grove_id` labels (Mar 12, 2026). Native GCP Cloud Monitoring/Logging/Trace exporters with auto-credential detection (Mar 6, 2026). OTLP metrics pipeline (Mar 16). | release-notes 2026-03-12 / 2026-03-06 / 2026-03-16 |
| `identity` | n/a | **GCP Identity + metadata-server emulation (Mar 17, 2026)** — each agent authenticates via GCP identity with per-agent rate limiting, iptables interception, audit logging, and OTEL metrics. | release-notes 2026-03-17 |
| `plugin system` | n/a | **Plugin infrastructure added Mar 14, 2026** using `hashicorp/go-plugin`, with reference implementations for message broker and agent harness plugins. | release-notes 2026-03-14 |
| `project status` | "experimental (2026-03)" | **Three-tier published status** (README): `Local mode — relatively stable`; `Hub-based workflows — ~80% verified`; `Kubernetes runtime — early, with known rough edges`. Not a single-knob "experimental" label any more. | README §Project Status |

### 2.2  Cross-check vs DevolaFlow integration points

Registry-declared integration points for `google-scion`:

1. Wave dispatch (git worktree provisioning per L3 task)
2. parallel task execution isolation

State of those points in v7.1.1 (verified 2026-04-18):

- **Worktree provisioning:** Grep across the repo for `worktree` returns exactly **one** hit — `workflow-system/agent/knowledge/reference-dependencies.yaml:264` (the registry line being updated). There is **no DevolaFlow code that creates, manages, or dispatches into a git worktree**.
- **Container isolation:** Grep for `worktree|container|grove|isolation` across `src/devolaflow/` returns matches only in `template_engine/models.py` and `template_engine/validator.py` — both are YAML-schema container types (`dict`, `list`), not process/filesystem containers. DevolaFlow **does not fork processes, does not spawn containers, and does not allocate per-task workspaces**. L3 Task Agents are implemented as the `Task` tool (subagent context inside the same orchestrator).
- **Parallel task execution:** DevolaFlow supports *parallel dispatch* (Wave Agent may dispatch multiple L3 tasks in one message), but the parallelism is at the **agent-driver** level (Cursor/Claude Code subagents sharing the same process tree), not at the worktree/container level.

**Net:** the gap flagged as **M5** in the registry is **still open and structural**. Scion's design is fundamentally ahead of DevolaFlow's on isolation: DevolaFlow has no primitive for per-task worktree/container provisioning and would need a new `Task Agent Runner` subsystem to get there.

### 2.3  Delta items (5-field schema)

#### Δ-scion-01  Project rehomed to GoogleCloudPlatform org + module rename (Mar 9, 2026)

- **What changed:** registry repo URL `https://github.com/GoogleCloudPlatform/scion` was already correct, but this repo became the canonical one on **Mar 9, 2026** ("official transition of the project to the Google Cloud Platform organization, including a full module rename"). Go module import path is now `github.com/GoogleCloudPlatform/scion/cmd/scion`.
- **Source:** release-notes dated 2026-03-09 at `https://googlecloudplatform.github.io/scion/release-notes/`.
- **Integration target:** `reference-dependencies.yaml` URL already up-to-date.
- **Currently integrated?** **N/A** — URL registry.
- **Recommended action:** **refresh-registry only.** Flag the module-path rename as a note (some third-party docs still cite the old import path).

#### Δ-scion-02  Hub / Runtime Broker / Hub-Native Groves are new primitives (post-registry)

- **What changed:** three concepts that the registry `key_patterns` did not capture:
  1. **Hub** — optional central control plane for multi-machine orchestration.
  2. **Runtime Broker** — a machine (laptop or VM) that offers its runtimes to a Hub (so a thin client can dispatch agents onto heavy remote runtimes).
  3. **Hub-Native Groves** (Feb 23, 2026) — project workspaces created directly through the Hub API without an external Git repository; auto-initialised with a seeded `.scion` structure. This is a meaningful departure from the "git worktree is the isolation unit" framing in the registry.
- **Source:** README §Core Concepts + release-notes 2026-02-23 ("Hub-Native Groves").
- **Integration target:** architectural framing for any future DevolaFlow parallel-execution subsystem.
- **Currently integrated?** **No.** DevolaFlow has no multi-machine orchestration concept; all L3 agents run co-located with the dispatcher.
- **Recommended action:** **track.** Update `key_patterns` to add `"Hub + Runtime Broker for multi-machine orchestration"` and `"Hub-Native Groves (no git repo required)"`. The latter is particularly relevant to DevolaFlow because it demonstrates that **isolation need not imply git worktrees** — a pure-FS + container model also works.

#### Δ-scion-03  Hub-linked groves switched from worktrees to `git init` + `git fetch` (Mar 15, 2026)

- **What changed:** registry key_pattern pins the isolation primitive as "git worktrees + containers". The Mar 15, 2026 release-notes explicitly says hub-linked groves were moved **away from worktrees** to "a robust `git init` + `git fetch` strategy instead of standard cloning or local worktrees". Local-only mode still uses worktrees; hub-linked mode does not.
- **Source:** release-notes 2026-03-15 ("Hub-Linked Workspace Provisioning").
- **Integration target:** conceptual — the gap-id **M5** ("git worktree provisioning per L3 task") in `reference-dependencies.yaml` should be reworded to "per-task workspace provisioning (any FS mechanism)".
- **Currently integrated?** **No** (DevolaFlow has neither).
- **Recommended action:** **refresh-registry** `key_patterns` line to read `"per-task workspace provisioning (git worktree for local, git init+fetch for hub-linked) + container isolation"`. This avoids anchoring DevolaFlow's gap-id vocabulary on a mechanism Scion itself is moving away from for distributed workflows.

#### Δ-scion-04  Observability matured: OTEL + GCP Logging/Monitoring/Trace (Feb-Mar 2026)

- **What changed:** not in registry at all. Normalized OTEL telemetry across all harnesses with resource labels `scion.harness`, `scion.model`, `scion.broker`, `grove_id` (Mar 12). Native GCP Cloud Monitoring / Logging / Trace exporters (Mar 6 / Mar 7). Codex-specific telemetry captures tool usage, tool input/output, and detailed token counts (input / output / cached).
- **Source:** release-notes 2026-03-12, 2026-03-06, 2026-03-07.
- **Integration target:** DevolaFlow `gate/reporter.py` + possible future `observability/` module.
- **Currently integrated?** **No.** DevolaFlow writes per-run artifacts to filesystem (per `CP-7` rules) but has no OTEL spans, no per-agent resource labels, and no external exporter.
- **Recommended action:** **track for v7.3+** — if DevolaFlow ever adds a multi-process runtime (which Scion demonstrates is viable with modest code), the label schema `{agent_id, harness, model, stage, wave, task}` is a cheap preview of what instrumentation would look like. For v7.2, out of scope.

#### Δ-scion-05  Plugin system via hashicorp/go-plugin (Mar 14, 2026)

- **What changed:** Scion now has a proper plugin architecture — reference implementations for **message broker** and **agent harness** plugins. Enables extending Scion without forking.
- **Source:** release-notes 2026-03-14.
- **Integration target:** conceptual. DevolaFlow's analog is `workflow-system/agent/plugins.yaml` (mentioned twice in `context_profiles.yaml` for NineS and ui-ux-pro integration) plus adapter-level forks.
- **Currently integrated?** **Partially.** `plugins.yaml` is a static registry, not a runtime plugin-loader. Comparable only at a documentation level.
- **Recommended action:** **no-op.** DevolaFlow is a skill/prompt framework, not a runtime host — a Go-plugin ABI makes no sense here. Keep the parallel only as a comment in the registry note.

#### Δ-scion-06  Still no pre-built binaries or containers (README §Quick Start)

- **What changed:** README explicitly says: "Sadly — as an open source project we are not yet able to provide pre-built binaries or containers. You will need to build images first." This is **unchanged from the registry snapshot** and **still a blocker for "production-readiness milestone" update trigger**.
- **Source:** README §Quick Start (fetched 2026-04-18).
- **Integration target:** update-trigger definition in `reference-dependencies.yaml`.
- **Currently integrated?** **N/A.**
- **Recommended action:** **no-op.** Registry update trigger "major releases or production-readiness milestone" has **not fired** — Scion has no tagged releases (`/releases` page returns "There aren't any releases here") and the README still lists three different maturity levels for local / hub / k8s modes.

### 2.4  Relevance refresh

- Current `relevance_score: 4` **holds**. Scion's isolation mechanism is still the strongest external reference for per-task workspace/container provisioning, and the gap (DevolaFlow has none) is unchanged. The 2026-03 release cadence demonstrates the project is very active, increasing the odds that DevolaFlow will want to track production-readiness milestones.
- `last_checked: 2026-04-18` (refresh).
- `update_triggers` — keep existing three; consider adding `"pre-built binaries or container images published"` as a concrete trigger (currently implicit in "major releases or production-readiness milestone").

---

## Reference 3 — `skillrouter` (zhengyanzhao1997/SkillRouter, arXiv:2603.22455)

### 3.1  Current state snapshot (verbatim from upstream)

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | `"v3 (arXiv:2603.22455v3)"` | **v4 (arXiv:2603.22455v4)** — last revised **1 Apr 2026** | `https://arxiv.org/abs/2603.22455v4` abstract page header ("[v4] Wed, 1 Apr 2026 10:03:20 UTC (436 KB)") |
| `arxiv version history` | v3 | **v1 (23 Mar 2026, 545 KB) → v2 (30 Mar 2026, 438 KB) → v3 (31 Mar 2026, 439 KB) → v4 (1 Apr 2026, 436 KB)** | `https://arxiv.org/abs/2603.22455` §Submission history |
| `core numbers` | "1.2B parameter pipeline", "74.0% Hit@1 at 80K candidate skills", "-31-44pp accuracy drop" | **All unchanged.** v4 abstract verbatim: "SkillRouter, a compact 1.2B full-text retrieve-and-rerank pipeline. SkillRouter achieves 74.0% Hit@1 on our benchmark … while using 13× fewer parameters and running 5.8× faster than the strongest base pipeline". The 31–44 pp drop clause is verbatim retained: "hiding the skill body causes a 31--44 percentage point drop in routing accuracy". | v4 abstract |
| `new in v4` | n/a | **Two new findings surfaced in v4 abstract (not present in registry patterns):** (1) "The ranking gains further generalize to a supplementary benchmark independently constructed from three skill sources." (2) "In a complementary end-to-end study across four coding agents, routing gains transfer to improved task success, with larger gains for more capable agents." | v4 abstract |
| `github repo` | n/a | **44 stars, 0 forks, 0 releases, 0 tags.** Repo description: "SkillRouter: Retrieve-and-Rerank Skill Selection for LLM Agents at Scale". No public model weights surfaced on the landing page summary. | `https://github.com/zhengyanzhao1997/SkillRouter`; `.../releases` ("There aren't any releases here") |
| `benchmark source` | "SkillsBench-derived benchmark with approximately 80K candidate skills" | **Confirmed verbatim in v4** ("SkillsBench-derived benchmark with approximately 80K candidate skills, targeting the practically important setting of large skill registries with heavy overlap"). | v4 abstract |

### 3.2  Cross-check vs DevolaFlow integration points

Registry-declared integration points for `skillrouter`:

1. `src/devolaflow/task_adaptive_selector.py` (`match_profile` augmentation)

State of that point in v7.1.1 (verified 2026-04-18):

- **`match_profile()` in `task_adaptive_selector.py` (lines 185–218):** ranking ladder is **"exact key match → exact hint match → longest substring match"**, pure string overlap (`hint_lower in task_lower`, `task_lower in hint_lower`, `best_score = len(hint_lower)`). **No retrieval component, no rerank stage, no learned model, no embedding.** The number of routable profiles is small (~12 profiles listed under `profiles:` in `context_profiles.yaml`), so a heavy retrieve-and-rerank pipeline would be grossly over-engineered for the current registry size.
- **Grep 2026-04-18 for `skill.?route|skill.?router|retrieve.and.rerank`** anywhere in the repo returns **zero matches**. SkillRouter is tracked as external reference only; no code attempts to adopt its pattern.
- **Registry scale mismatch:** DevolaFlow has ~12 profiles × ~40 sections. SkillRouter is calibrated for **80 000** candidates. The single most important operational conclusion from the paper — "full skill text is a critical routing signal" (the -31 to -44 pp drop) — **is already honored by DevolaFlow**: `match_profile` operates on full `goal_hints` strings (not hashed tokens), and `_select_sections_within_budget` reads the full section text (not metadata) before packing.

**Net:** DevolaFlow is *consistent with the v4 finding* on full-text signal, but uses a trivial matcher because its routing space is tiny. No action required unless DevolaFlow starts routing against thousands of external SKILL bundles.

### 3.3  Delta items (5-field schema)

#### Δ-skillrouter-01  Paper advanced v3 → v4 (1 Apr 2026) — registry stale by one revision

- **What changed:** registry `last_known_version: "v3 (arXiv:2603.22455v3)"` is stale. The current abstract page is **v4** (submitted 1 Apr 2026, 436 KB; registry snapshot date 2026-04-11 *should* have caught this but did not).
- **Source:** `https://arxiv.org/abs/2603.22455v4` abstract page header verbatim: "[v4] Wed, 1 Apr 2026 10:03:20 UTC (436 KB)" (also surfaced on `https://arxiv.org/abs/2603.22455` in the submission-history list).
- **Integration target:** `reference-dependencies.yaml` `last_known_version` field.
- **Currently integrated?** **No** (purely a registry-version tracking field).
- **Recommended action:** **refresh-registry** — set `last_known_version: "v4 (arXiv:2603.22455v4, 2026-04-01)"`, `last_checked: 2026-04-18`.

#### Δ-skillrouter-02  Two new v4 findings: cross-source generalisation + agent-coupled win rate

- **What changed:** v4 adds two sentences to the abstract not present in the registry `key_patterns`:
  1. "The ranking gains further generalize to a supplementary benchmark independently constructed from three skill sources" — an external-validity claim against the SkillsBench-derived setting.
  2. "In a complementary end-to-end study across four coding agents, routing gains transfer to improved task success, with larger gains for more capable agents" — pairs skill-routing accuracy with downstream end-to-end performance, and says the effect scales with model capability.
- **Source:** v4 abstract at `https://arxiv.org/abs/2603.22455v4`.
- **Integration target:** `reference-dependencies.yaml` `key_patterns` list.
- **Currently integrated?** **No.** Registry's three `key_patterns` entries don't mention cross-source generalisation or agent-coupled eval.
- **Recommended action:** **refresh-registry** — append a fourth key_pattern: `"v4 end-to-end study: routing gains transfer to task success, scale with agent capability"`. Do **not** port; DevolaFlow's routing surface is too small to benefit from SkillRouter's architecture.

#### Δ-skillrouter-03  No model weights / code release yet — still paper-backed only

- **What changed:** registry `update_triggers` include "model accuracy improvements or reduced model size". The v4 numbers are **unchanged** (1.2B, 74.0% Hit@1, 13× fewer params than baseline, 5.8× faster). GitHub repo has **0 releases, 0 tags**; no weights or inference code visible from the repo summary page.
- **Source:** `https://github.com/zhengyanzhao1997/SkillRouter/releases` ("There aren't any releases here"); `https://github.com/zhengyanzhao1997/SkillRouter` (summary: "44 stars, 0 forks").
- **Integration target:** update-trigger evaluation.
- **Currently integrated?** **N/A.**
- **Recommended action:** **no-op.** Trigger "model accuracy improvements or reduced model size" has **not fired**. Keep periodic monitoring cadence.

#### Δ-skillrouter-04  v4 finding *supports* DevolaFlow's existing full-text-first design

- **What changed:** the v4 abstract preserves the key operational claim: "hiding the skill body causes a 31–44 percentage point drop in routing accuracy". DevolaFlow's `task_adaptive_selector.py` matches against `goal_hints` (strings) and extracts **full section text** before selecting (`extract_section(skill_text, line_range)` at lines 165–171). This is **consistent** with the paper's recommendation.
- **Source:** v4 abstract; `task_adaptive_selector.py` lines 165–171 and 185–218.
- **Integration target:** `.cursor/rules/skill-format-rules.mdc` rule **SF-2** ("description must describe WHEN/WHY to activate the skill … not WHAT the skill does. This prevents agents from using the description as a compressed substitute for reading the full skill content.").
- **Currently integrated?** **Yes — spiritually aligned.** SF-2 is effectively a verbal restatement of the SkillRouter v3/v4 finding ("description ≠ body, description alone tanks routing accuracy").
- **Recommended action:** **refresh-registry** to note that SF-2 is the DevolaFlow mitigation for the SkillRouter-documented risk. No rule change; this is a *documentation* refresh of the integration ledger.

### 3.4  Relevance refresh

- Current `relevance_score: 4` **holds**. Not upgraded to 5 because (a) DevolaFlow's routing space is two orders of magnitude smaller than SkillRouter's evaluation setting, (b) no code artefact (weights, CLI, service) is publicly released, and (c) v4's new findings strengthen the theoretical case for DevolaFlow's SF-2 rule but do not imply a new implementation task.
- `last_checked: 2026-04-18` (refresh).
- `update_triggers` — keep all three; add one new trigger: `"v5+ arxiv revision with changed Hit@1 or model size"`.

---

## 4.  Cross-cutting observations

### 4.1  All three references converge on the same thesis, with different axes

- **vexp:** local AST + graph centrality = 73% SWE-bench @ $0.67.
- **SkillRouter:** retrieve-and-rerank against full-text skill bodies = 74.0% Hit@1.
- **Scion:** infrastructure-level isolation per-agent = enables the other two patterns to run in parallel without collision.

Each one covers an axis DevolaFlow under-resources:

| axis | vexp | SkillRouter | Scion | DevolaFlow today |
|------|------|-------------|-------|------------------|
| source-code graph signal | ✓ | — | — | **none** |
| full-text routing vs metadata-only | ✓ (tools, memory) | ✓ (skills) | — | **enforced via SF-2 doc rule only** |
| per-task isolation | — | — | ✓ | **none (co-located subagent calls)** |
| cross-session memory with stale flags | ✓ | — | — | **partial (`learnings/operational.jsonl`, no staleness)** |

### 4.2  No DevolaFlow source code touched

All three references are still net-external. Zero `src/devolaflow/**` or `workflow-system/**` files required modification to complete this delta survey. The only write was to the owned path `.local/research/v7.2.0_refs/delta-T05.md`.

### 4.3  Registry refresh summary for v7.2

| ref | registry field | old value | new value | source delta id |
|-----|----------------|-----------|-----------|-----------------|
| vexp | `last_known_version` | `"commercial (2026)"` | `"v1.3.11 (VS Code ext + vexp-cli, proprietary)"` | Δ-vexp-01 |
| vexp | `key_patterns` (empirical claim) | "65% fewer tokens and +14pp task success rate (FastAPI benchmark)" | "65–70% token reduction (5-codebase average); 73% SWE-bench Verified Pass@1 at $0.67/task (Claude Opus 4.5)" | Δ-vexp-02 |
| vexp | `source_type` | `blog` | `product` or `commercial_mcp_server` | §1.4 |
| vexp | `update_triggers` | drop "open-source release or API availability" | add "new MCP tool added/removed", "Pro tier node limit changed", "new benchmark publication" | §1.4 |
| scion | `key_patterns` (isolation) | "infrastructure-level agent isolation via git worktrees + containers" | "per-task workspace provisioning (git worktree for local, git init+fetch for hub-linked) + container isolation" | Δ-scion-03 |
| scion | `key_patterns` (add) | n/a | "Hub + Runtime Broker for multi-machine orchestration", "Hub-Native Groves (no git repo required)" | Δ-scion-02 |
| scion | `update_triggers` | existing three | add "pre-built binaries or container images published" | §2.4 |
| skillrouter | `last_known_version` | `"v3 (arXiv:2603.22455v3)"` | `"v4 (arXiv:2603.22455v4, 2026-04-01)"` | Δ-skillrouter-01 |
| skillrouter | `key_patterns` (add) | n/a | "v4 end-to-end study: routing gains transfer to task success, scale with agent capability" | Δ-skillrouter-02 |
| all three | `last_checked` | 2026-04-11 | 2026-04-18 | — |

---

## 5.  Limitations

1. **vexp is proprietary** — could not inspect the actual Rust `vexp-core` source or verify internal signal weights beyond what docs state. All performance numbers are self-reported (SWE-bench benchmark repo exists at `github.com/Vexp-ai/vexp-swe-bench` but was not independently reproduced).
2. **Scion GitHub API returned minimal data** — the `github.com/GoogleCloudPlatform/scion` page summary showed only star count and links; the raw-README fetch was what actually yielded the feature matrix. Similarly `releases` is empty and all version inference comes from the release-notes microsite (no semver tags). Individual release-notes entries are **dated but unversioned**.
3. **SkillRouter GitHub repo was not inspected at file level** — summary fetch returned only star count + description. If weights or a reference implementation are silently added without a GitHub Release event, this survey would miss it. Full-repo crawl was out of scope per `max_files: 6 writable` (reading was not budget-limited, but fetching a code tree via WebFetch returned no file list — would need `git clone` which was out of scope).
4. **Arxiv v5+ polling** — done by reading `arxiv.org/abs/2603.22455` submission history (showed v1–v4 only as of 2026-04-18). No v5 detection mechanism beyond manual re-check.
5. **DevolaFlow cross-check depth** — verified `src/devolaflow/task_adaptive_selector.py` (587 lines) and `workflow-system/agent/context_profiles.yaml` (first 100 lines + grep). Did **not** read every consumer of `match_profile()` across the codebase, but the integration-target claim ("graph-distance-based section priority") was disproven by inspecting the implementation, which is independent of call-sites.
6. **Siblings T06/T07 scope isolation** — this file touches only the three references specified by the parent dispatch. Output paths `delta-T06.md` and `delta-T07.md` were not read or written.
7. **Per-fetch escalation policy** — executed as specified: no individual unreachable URL was escalated. The `googlecloudplatform.github.io/scion/` main page returned HTTP 503 on first attempt, but the `/release-notes/` sub-page succeeded — so the research surface was not blocked.

---

*End of delta-T05.md · produced 2026-04-18 · no DevolaFlow source modified · 3/3 references analysed · 5/5 acceptance criteria met.*
