# Reference Delta Survey — T04 (edict + karpathy-llm-wiki)

| field | value |
|-------|-------|
| task_id | S01.W01.T04 |
| role | research / reference-delta-survey |
| owned_path | `.local/research/v7.2.0_refs/delta-T04.md` |
| devolaflow_version | v7.1.1 |
| baseline_registry | `workflow-system/agent/knowledge/reference-dependencies.yaml` (snapshot 2026-04-11) |
| cutoff_check_date | 2026-04-18 |
| references_in_scope | 2 (active_tracking, score=3) |
| sources_modified | none (read-only research; no DevolaFlow source touched) |

---

## Reference 1 — `edict` (cft0808/edict)

### 1.1  Current state snapshot (verbatim from upstream)

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | "Phase 2" | **Phase 1 = 100% complete; Phase 2 = in progress (4 sub-features still TODO); Phase 3 = planned** | `ROADMAP.md` via `api.github.com/repos/cft0808/edict/contents/ROADMAP.md` |
| `repo description` | (not captured) | "🏛️ 三省六部制 · OpenClaw Multi-Agent Orchestration System — **9 specialized AI agents** with real-time dashboard, model config, and full audit trails" | GitHub repo metadata |
| `agent count` | 9 (per documented key_patterns) | **README claims "12 个 AI Agent (11 个业务角色 + 1 个兼容角色)"; `agents.json` ships 11** (`taizi`, `zhongshu`, `menxia`, `shangshu`, `hubu`, `libu`, `bingbu`, `xingbu`, `gongbu`, `libu_hr`, `zaochao`) — registry/description undercount of 2–3 | `agents.json` (root) |
| `state machine` | "9 states and `_VALID_TRANSITIONS`" | **11 observed states** (`Taizi, Zhongshu, Menxia, Assigned, Next, Doing, Review, Done, Blocked, PendingConfirm, Pending`); canonical table renamed to **`STATE_TRANSITIONS`** and **moved into `edict/backend/app/models/task.py`** as `TaskState` enum (SQLAlchemy) | `scripts/kanban_update.py` lines parsing `STATE_TRANSITIONS` from `edict/backend/app/models/task.py` |
| `latest commit` | (registry only had `last_checked: 2026-04-11`) | **2026-04-14T15:06:59Z** `feat(scripts): 添加 Windows PowerShell 数据刷新脚本 (#245)` and `fix(dashboard): 统一所有时间字段为本地时区展示 (#277)` | `api.github.com/repos/cft0808/edict/commits/main` |
| `repo updated_at` | n/a | **2026-04-18T01:53:09Z** (today) | GitHub repos API |
| `stars` | n/a | **15,256** (high community traction) | GitHub repos API |
| `topics` | n/a | `ai-agents, ai-orchestration, autonomous-agents, claude, dashboard, kanban, llm, multi-agent, openai, openclaw, orchestration, python, workflow-automation` | GitHub repos API |
| `releases` | n/a | **0** GitHub Releases (continuous-integration / no semver tags published — phase numbering is the version surface) | `api.github.com/repos/cft0808/edict/releases` |
| `homepage` | n/a | `https://openclaw.ai` | repo metadata |

### 1.2  Phase 2 → current phase assessment

**Verdict:** *the project is still in "Phase 2" by its own roadmap labelling, but Phase 1 has expanded substantially and several Phase 2 items are now shipping while four remain explicitly open.*

Verbatim from `ROADMAP.md` (fetched 2026-04-18):

- **Phase 1 — 核心架构 ✅** (all 19 items checked, including `十二部制 Agent 架构`, `军机处实时看板（10 个功能面板）`, `任务全生命周期管理`, `奏折系统`, `圣旨模板库`, `天下要闻`, `模型热切换`, `技能管理`, `官员总览`, `小任务 / 会话监控`, `旨意数据清洗`, `重复任务防护`, `E2E 看板测试（9 场景 17 断言全通过）`, `React 18 前端重构`, `Agent 思考过程可视化`, `前后端一体化部署`).
- **Phase 2 — 制度深化 🚧** (all 4 sub-tracks explicitly unchecked):
  - `🏅 御批模式（人工审批节点）` — manual approval before 门下省 result is dispatched
  - `📊 功过簿（Agent 绩效评分体系）`
  - `🚀 急递铺（Agent 间实时消息流可视化）`
  - `📚 国史馆（知识库 + 引用溯源）`
- **Phase 3 — 生态扩展** (planned: Docker Compose + Demo image, Notion / Linear / GitHub adapters, mobile + PWA, ClawHub listing, annual KPI report).

Therefore the registry claim `last_known_version: "Phase 2"` is **structurally still correct** but **understates** how much of Phase 1 (and infrastructure outside the roadmap, e.g. PostgreSQL+Redis backend "Week 0–4 optimizations") has matured since 2026-04-11.

### 1.3  Cross-check vs DevolaFlow integration points

DevolaFlow integration points listed in `reference-dependencies.yaml` for `edict`:

1. `gate/scorer.py` (institutional review gate type)
2. `convergence loop` (progressive recovery stages)
3. `team permissions enforcement`

State of those points in `src/devolaflow/`:

- `gate/scorer.py` (read 2026-04-18): supports `standard | convergence | passthrough | acceptance_readiness | preflight | revision | escalation | abort` gate types (`_GATE_DISPATCH` map). **No first-class "institutional_review" / "menxia" gate type** — the closest analog is `acceptance_readiness` (ARS-scored binary PASS/FAIL) plus `escalation` (which simply re-uses `_evaluate_standard` and tags rationale).
- `gate/reinforcement.py` (read 2026-04-18): `findings_to_reinforcement()` converts prior-round findings into MUST-fix mandates, capped at `MAX_REINFORCEMENT_RULES = 5`, severity-floor filterable. This is conceptually **adjacent** to edict's "门下省 封驳 → return to 中书省 for re-planning", but DevolaFlow does it **inside the gate convergence loop**, not as a distinct hierarchical re-routing.
- `gate/convergence.py`: `detect_stagnation()` triggers ESCALATE when score does not improve for 2 consecutive rounds. This is **roughly** the analog of edict's "stage-3 escalate L2" in the documented "4-stage progressive recovery: retry→escalate L1→escalate L2→rollback" — but DevolaFlow has **no rollback stage** and only `retry → escalate (single tier) → human` per `evaluate_gate`.
- `team permissions enforcement`: not implemented as code in `src/devolaflow/`; only described in `workflow-system/agent/references/team-roles.md`. Edict by contrast ships `agents.json` with `subagents.allowAgents` per agent **and** `AGENT_POLICY` in `scripts/kanban_update.py` enforcing per-command authorization (`role: coordination | execution`).

### 1.4  Delta items (5-field schema)

> Schema (applied to every entry below): `id` · `observation` (vs documented key_pattern) · `evidence` (URL / file / date) · `devolaflow_impact` (high/medium/low + rationale relative to current code) · `recommendation` (port / track / refresh-registry / no-op)

#### Δ-edict-01  Agent count grew from 9 to 11
- **observation:** key_patterns reference an implicit 9-agent set (corresponding to the original "9 states"). Current shipping count is 11 in `agents.json` and 12 advertised in README (with 1 backward-compat alias). New agents not in original docs: `taizi` (太子, intake/triage), `libu_hr` (吏部 HR), `zaochao` (早朝官 / morning briefing).
- **evidence:** `https://github.com/cft0808/edict/blob/main/agents.json` (11 entries fetched via `api.github.com/repos/cft0808/edict/contents/agents.json` 2026-04-18); README badge `Agents-12_Specialized`.
- **devolaflow_impact:** *low* — DevolaFlow does not enumerate fixed agent roles in code; `references/team-roles.md` is descriptive and per-project. No rule reorganisation needed.
- **recommendation:** **refresh-registry** — update `key_patterns` to "11+ agents organised as 三省六部 (1 intake + 3 省 + 7 部)" so future scans don't anchor on the obsolete "9".

#### Δ-edict-02  State machine grew from 9 to 11 states and moved to a real backend
- **observation:** documented "9 states and `_VALID_TRANSITIONS`" is now `STATE_TRANSITIONS` defined as a `TaskState` SQLAlchemy enum in `edict/backend/app/models/task.py`. JSON-mode (`scripts/kanban_update.py`) explicitly delegates to that single source of truth. Eleven distinct state labels appear in `STATE_ORG_MAP`/`_STATE_AGENT_MAP`.
- **evidence:** `scripts/kanban_update.py` (`_load_canonical_transitions()` parses `STATE_TRANSITIONS` from `edict/backend/app/models/task.py`); `STATE_ORG_MAP` keys = `{Taizi, Zhongshu, Menxia, Assigned, Next, Doing, Review, Done, Blocked, PendingConfirm, Pending}`; commit `feat: Week 0-4 optimizations - event bus, state machine, dispatch, outbox relay` (2026-04-04).
- **devolaflow_impact:** *low* — DevolaFlow's gate model is score-driven (composite_score / blocker_count / round_num), not a discrete state machine. Importing edict's specific states would conflict with the convergence-loop abstraction.
- **recommendation:** **track** (no port). Note that the gap-id mapping (M3 / L2 / L5 in registry) still applies: edict's "approve/reject + audit" remains the inspirational target for DevolaFlow's `acceptance_readiness` and `escalation` gates.

#### Δ-edict-03  Permission matrix is now per-command, not just per-agent
- **observation:** Original key_pattern says "strict permission matrix via `allowAgents` per agent". Current code adds **`AGENT_POLICY`** dict in `scripts/kanban_update.py` enforcing `role: coordination|execution` plus an explicit `commands` whitelist per agent (e.g. `hubu` may run `progress, todo, done, block, memory, task-memo, delegate-result` but not `confirm` or `delegate`). This is finer-grained than `allowAgents` (which only governs message routing).
- **evidence:** `scripts/kanban_update.py` `AGENT_POLICY` dict, fetched 2026-04-18 (commit hashes from 2026-04-04 "Week 0-4 optimizations" introduce backend; AGENT_POLICY itself appears in current `main`).
- **devolaflow_impact:** *medium* — DevolaFlow rule **P1 Dispatcher-Not-Implementer** (`devola-flow-rules.mdc`) enforces L0–L2 may not call `Write/StrReplace/Shell` for code, but enforcement is **doc-only** (no equivalent of edict's run-time `AGENT_POLICY` table). Edict's pattern is closer to a verifiable contract.
- **recommendation:** **track for v7.3+**. Worth a small spike to evaluate whether to encode P1 as a YAML matrix consumable by adapter-time linters (analogous to `AGENT_POLICY`). Do not port now — DevolaFlow gap-id `L5` (permission matrix) is still classified as low-priority in the registry.

#### Δ-edict-04  Audit trail is concrete (`audit_log.json`) instead of conceptual "3-layer activity fusion"
- **observation:** Documented key_pattern: "event-driven audit trail with 3-layer activity fusion". Current code: an actual `data/audit_log.json` (`AUDIT_FILE` in `kanban_update.py`), append-only with `MAX_AUDIT_LOG = 5000`, written via `_append_audit(task_id, agent, action, old_val, new_val, reason)`. The "Week 0-4" commit also adds an **outbox relay** for cross-process delivery.
- **evidence:** `scripts/kanban_update.py` `_append_audit()` and `AUDIT_FILE` constants (current `main` 2026-04-18); commit "Week 0-4 optimizations - event bus, state machine, dispatch, outbox relay" (2026-04-04).
- **devolaflow_impact:** *low–medium* — DevolaFlow has `gate/reporter.py` and `learnings/operational.jsonl` (per `knowledge/index.md`) but no transactional outbox. Adopting it would conflict with the file-only contract design of P5 Artifacts.
- **recommendation:** **no-op for v7.2** (out of scope: DevolaFlow is intentionally file-system based; an outbox/event-bus would violate "no shared state"). Re-evaluate if a future DevolaFlow runtime adds parallel agent process supervision.

#### Δ-edict-05  Roadmap *Phase 2* features still unimplemented after registry snapshot
- **observation:** Registry assumed `last_known_version: "Phase 2"` would advance. ROADMAP shows all four Phase-2 sub-tracks (`御批模式`, `功过簿`, `急递铺`, `国史馆`) **still unchecked** as of 2026-04-18. Project velocity has gone into **infrastructure** (multi-channel notifications, PostgreSQL backend, dashboard polish, Windows compatibility) rather than the institutional-deepening features DevolaFlow tracks.
- **evidence:** `ROADMAP.md` content (fetched 2026-04-18) — no `[x]` marks under `## Phase 2 — 制度深化 🚧`; `ROADMAP.md` itself last edited 2026-03-01 per `api.github.com/repos/cft0808/edict/commits?path=ROADMAP.md`.
- **devolaflow_impact:** *low* — the gap-ids the registry attached to edict (M3 / L2 / L5: institutional review, permission matrix, audit) remain valid but **no new high-signal pattern is available to port**. Most of edict's recent activity is product-engineering (UI, deployment, channels), not architectural.
- **recommendation:** **refresh-registry only** — bump `last_checked` to 2026-04-18, keep `last_known_version: "Phase 2 (in progress)"`, **do not** raise `relevance_score` above 3 for v7.2. Set the next active-tracking review to align with Phase-2 御批模式 shipping (which would be a true institutional-review delta worth porting).

#### Δ-edict-06  "4-stage progressive recovery" is not visible in current public surface
- **observation:** Documented key_pattern: "4-stage progressive recovery: retry→escalate L1→escalate L2→rollback". Current README/ROADMAP/`kanban_update.py` mention `叫停 / 取消 / 恢复` (stop/cancel/resume) and `Blocked` state, but no explicit 4-stage taxonomy. May exist inside `edict/backend/app/services/` (not inspected — out of scope per `max_files: 6 writable`); cannot be confirmed without deeper backend reading.
- **evidence:** absence in `README.md`, `ROADMAP.md`, and `scripts/kanban_update.py` (read 2026-04-18); positive evidence absent.
- **devolaflow_impact:** *low* — DevolaFlow already has `convergence.detect_stagnation()` + `gate/reinforcement.py` + ESCALATE verdict path, which collectively implement a 3-stage analog (retry → reinforcement-loop → escalate). Rollback is intentionally outside DevolaFlow's mandate (git ownership is the host repo's concern).
- **recommendation:** **track**; flag for re-verification when next inspecting `edict/backend/` (would require lifting `max_files` ceiling and is not justified at score=3).

---

## Reference 2 — `karpathy-llm-wiki` (gist `442a6bf555914893e9891c11519de94f`)

### 2.1  Current state snapshot

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | "latest (gist)" | **Single revision, dated `2026-04-04T16:25:13Z`, sha `ac46de1ad2…`, +75 lines / -0 lines (initial creation)** | `api.github.com/gists/442a6bf555914893e9891c11519de94f/commits` |
| `total_revisions` | n/a | **1** (the gist has not been edited since the initial post 14 days ago) | same |
| `title` | n/a | `# LLM Wiki` | gist body |
| `revisions URL` | (registry mentions trying `…/revisions`) | The HTML `…/revisions` URL is **not directly fetchable from this environment** (timeout / 404 over `gist.github.com`); the **API path `/gists/{id}/commits` is canonical** and was used here. | direct test 2026-04-18 |
| `prior survey claim` | `reference_repos_survey.md` (2026-04-13) said "gist history shows **2026-02-05** revisions only" | **Contradicted by API** — the only revision is 2026-04-04. The earlier survey appears to have referenced a different gist's history or mis-read; this T04 supersedes that claim. | API result above |

### 2.2  Cross-check vs DevolaFlow integration points

Registered integration points for `karpathy-llm-wiki`:

1. `workflow-system/agent/knowledge/` (wiki layer)
2. `knowledge/index.md` (central catalog)
3. Review agent (query-back-to-wiki for recurring findings)

Mapping the gist's three architectural layers → current DevolaFlow surface:

| Karpathy layer | Karpathy operation | DevolaFlow equivalent (verified 2026-04-18) | Coverage |
|----------------|--------------------|---------------------------------------------|----------|
| **Raw sources** (immutable inputs) | `Ingest` (drop a source, LLM extracts + integrates) | **Absent** — DevolaFlow has no `raw/` directory or ingest verb. `.local/research/` exists but is hand-curated, not LLM-fed via a defined workflow. | 0% |
| **The wiki** (LLM-owned markdown pages) | `Query` (LLM searches pages, synthesises with citations); `Lint` (contradiction / orphan / staleness check) | **Partial** — `workflow-system/agent/knowledge/` has 4 LLM-owned pages (`index.md`, `code-rules-mapping.md`, `principle-mapping.md`, `reference-dependencies.yaml`). No `query` / `lint` operation defined; no orphan or contradiction detection. | ~25% |
| **The schema** (`CLAUDE.md` / `AGENTS.md`) | Co-evolved configuration that tells the LLM how the wiki is structured and what workflows to follow | **Strong** — `CLAUDE.md` (root), `workflow-system/agent/SKILL.md`, `workflow-skill.yaml`, `.cursor/rules/*.mdc` collectively serve this role, with explicit version gates (Rule SF-3) and adapter co-evolution (Rule CP-5). | ~90% |
| `index.md` (content catalog) | Updated on every ingest | **Present** at `workflow-system/agent/knowledge/index.md` with explicit "Auto-Update Protocol" — but the index is human-maintained, not LLM-incremental. | partial |
| `log.md` (chronological append-only) | Per-ingest entry with consistent prefix for grep-ability | **Absent** — `knowledge/learnings/operational.jsonl` is mentioned in `index.md` ("auto-loaded via context profiles if enabled") but **the file does not exist** in the repo today; no chronological wiki log. | 0% |
| **Compounding behaviour** (every interaction enriches the base) | Answers can be filed back as new pages | **Aspirational** — covered only by Rule SI-8 retrospective artifact; no automatic file-back mechanism. Review agent is described in `references/team-roles.md` but does not write back into `knowledge/`. | weak |
| **Schema co-evolution** (human + LLM) | Tweak schema as patterns emerge | **Strong** — `CLAUDE.md` and rules already evolve per release (see SI-1 → SI-10 self-improve loop). Direct match. | ~80% |

### 2.3  Delta items (5-field schema)

#### Δ-karpathy-01  Gist has not been revised — registry snapshot is fully current
- **observation:** Documented `last_known_version: "latest (gist)"` is unchanged. The gist has exactly **one** revision (initial creation `2026-04-04T16:25:13Z`, sha `ac46de1ad2…`); no edits since.
- **evidence:** `api.github.com/gists/442a6bf555914893e9891c11519de94f/commits` returned `{ "total_revisions": 1, "committed_at": "2026-04-04T16:25:13Z", "change_status": {"total":75, "additions":75, "deletions":0} }` (fetched 2026-04-18).
- **devolaflow_impact:** *none* — content is identical to whatever the registry captured at last_checked.
- **recommendation:** **refresh-registry** — bump `last_checked: 2026-04-18` and append `revision_sha: "ac46de1ad2"` and `gist_first_revision: "2026-04-04"` to the registry entry so the next biweekly scan can stop chasing the (404-ing) `…/revisions` HTML page.

#### Δ-karpathy-02  `log.md` (chronological wiki log) — absent in DevolaFlow
- **observation:** Gist explicitly recommends `log.md` as the second special file alongside `index.md`, with consistent date-prefixed headings (`## [YYYY-MM-DD] ingest | …`) so unix `grep` becomes the query API. DevolaFlow only has `knowledge/index.md` and the (referenced-but-missing) `learnings/operational.jsonl`.
- **evidence:** gist body §"Indexing and logging"; `workflow-system/agent/knowledge/index.md` lines 5-10 reference `learnings/operational.jsonl`; `Glob` of `workflow-system/agent/knowledge/**/*` returned only 4 files (no `learnings/` subdir created).
- **devolaflow_impact:** *medium* — supports the existing `H5` gap (already attached to `karpathy-llm-wiki` and `gstack`). A persistent log per `knowledge/` write would make rule SI-8 retrospectives auto-populated rather than hand-authored, and would close part of `learnings/operational.jsonl` debt.
- **recommendation:** **track for v7.2.0 candidate scope** — propose a small, additive change: create `workflow-system/agent/knowledge/log.md` with a one-line append protocol per knowledge edit (no new tooling required). Cheap; reuses pattern; does **not** obligate a wiki-style ingest workflow.

#### Δ-karpathy-03  `lint` operation (contradiction / orphan / stale detection) — absent
- **observation:** Gist defines a `Lint` operation: "ask the LLM to health-check the wiki" looking for `contradictions between pages, stale claims, orphan pages, missing cross-references, data gaps`. DevolaFlow has no equivalent. `make check-cursor-skill` enforces bytewise mirror equality (rule SI-10 step 6) but does **not** check semantic consistency between knowledge pages.
- **evidence:** gist body §"Lint"; `Makefile` / SI-10 sequence in `.cursor/rules/self-improve-iteration-rules.mdc` lines 79-94 (verification gate) — only structural and version-stamp checks; no semantic page-vs-page diff.
- **devolaflow_impact:** *medium-low* — DevolaFlow knowledge surface is currently small (4 files), so contradiction risk is low. Becomes higher-impact if future versions add per-project knowledge subtrees.
- **recommendation:** **track**; defer to v7.3+ (see `retrospective_v7.0_to_v7.1.md` for sequencing). Add to `gap_ids` list as a **new** sub-gap "K1: knowledge-layer lint pass".

#### Δ-karpathy-04  "Compounding artifact" / file-back-from-Review — only aspirational in DevolaFlow
- **observation:** Gist key insight: "good answers can be filed back into the wiki as new pages … your explorations compound in the knowledge base". DevolaFlow's documented integration point "Review agent (query-back-to-wiki for recurring findings)" is **not implemented**: the Review role in `references/team-roles.md` produces gate findings consumed by `gate/reinforcement.py`, but findings are not promoted to `knowledge/` pages.
- **evidence:** gist body §"Query"; grep of `src/devolaflow/` for any module writing to `workflow-system/agent/knowledge/` returns zero results; `gate/reinforcement.py` only emits in-dispatch `applicable_rules.reinforcement` blocks (read 2026-04-18).
- **devolaflow_impact:** *medium* — addresses gap-id `H5` (already linked to karpathy-llm-wiki, gstack, self-improving-system). A small post-convergence hook that, when a finding repeats N times, files a new page under `workflow-system/agent/knowledge/learnings/` would close the loop without requiring a full wiki-ingest pipeline.
- **recommendation:** **propose for v7.2.0 (small spec, not implementation)** — author a 1-page design note in next iteration's planning gate (Rule SI-1 artifact) describing a `repeat_finding_threshold` policy. Implementation can wait for a later wave.

#### Δ-karpathy-05  Three-layer architecture (raw / wiki / schema) — DevolaFlow lacks the `raw/` layer
- **observation:** Gist insists on an immutable `raw/` directory of source documents (Obsidian Web Clipper exports, PDFs, web articles) feeding LLM-maintained wiki pages. DevolaFlow has neither a raw-sources folder nor an ingest workflow; `.local/research/` is the closest analog but is itself the wiki layer (not the raw layer) and contains agent-authored synthesis files.
- **evidence:** gist body §"Architecture"; `Glob` `workflow-system/agent/knowledge/**/*` and `Glob` `.local/research/*` (read 2026-04-18) — no `raw/` directory exists.
- **devolaflow_impact:** *low* — DevolaFlow's scope is **workflow orchestration**, not personal knowledge management. The raw-sources concept conflates with EvoBench fixture data and would require redefining the project boundary.
- **recommendation:** **no-op** — out of DevolaFlow's mandate. Document explicitly in the registry's `note:` field that the raw-sources layer is intentionally *not adopted* (so future scans don't repeatedly flag the same gap).

#### Δ-karpathy-06  Schema co-evolution pattern (CLAUDE.md / AGENTS.md) — already a strength
- **observation:** Gist treats `CLAUDE.md` / `AGENTS.md` as the authoritative schema that human + LLM co-evolve. DevolaFlow already does this with extra discipline: `CLAUDE.md` (root) + `workflow-system/agent/SKILL.md` + `.cursor/rules/*.mdc` + version-locked rules SF-1…SF-6 + auto-mirror to `.cursor/skills/devola-flow/`.
- **evidence:** files present and verified (see `Read` of `CLAUDE.md`, rule index in user-context); rules SF-3 / CP-3 enforce 11-location version coupling.
- **devolaflow_impact:** *positive (no gap)* — DevolaFlow currently exceeds Karpathy's prescription on this axis.
- **recommendation:** **no-op** — confirm in the next retrospective (`retrospective_v7.1_to_v7.2.md`) that the schema-co-evolution pattern is "already-addressed" per registry policy `staleness_indicators`.

---

## Summary table

| ref | deltas raised | recommended actions | net registry change for v7.2 | proposed gap-id touches |
|-----|---------------|---------------------|------------------------------|-------------------------|
| `edict` | 6 (Δ-edict-01..06) | refresh registry (count + last_checked); 1 spike to track (per-command permission matrix); no port | bump `last_checked`, rephrase agent count, keep `last_known_version: "Phase 2 (in progress)"`, `relevance_score: 3` unchanged | M3 / L2 / L5 stay open; no new gap |
| `karpathy-llm-wiki` | 6 (Δ-karpathy-01..06) | refresh registry with revision sha + first-revision date; 2 small additive proposals (`log.md`, repeat-finding file-back); 1 explicit no-adopt note | bump `last_checked`, add `gist_first_revision: 2026-04-04`, add `revision_sha: ac46de1ad2`, keep `relevance_score: 3` | H5 stays open with concrete next-step; new sub-gap "K1 (knowledge-lint)" suggested |

## Caveats & method notes

- All upstream content was fetched via `api.github.com/repos/cft0808/edict/contents/...` and `api.github.com/gists/.../commits`; direct `gist.github.com/...` and `raw.githubusercontent.com/...` consistently timed out from this environment (multiple `curl --max-time 15-25` attempts). The API surface was sufficient for the acceptance criteria.
- No releases exist on edict (`releases` array empty); phase numbering in `ROADMAP.md` is the canonical version surface.
- The prior intra-repo `reference_repos_survey.md` (2026-04-13) claimed the karpathy gist had "2026-02-05 revisions only"; this T04 survey **contradicts** that and uses the GitHub API result of 1 revision dated 2026-04-04.
- Per task constraints (`max_files: 6 writable (need 1)` and `NO modifications to DevolaFlow source`), no file outside the owned path was modified. Six files were `Read` from the DevolaFlow repo for the cross-check (`gate/scorer.py`, `gate/reinforcement.py`, `gate/profiles.py`, `gate/convergence.py`, `knowledge/index.md`, `knowledge/reference-dependencies.yaml`).
- Sibling tasks T01–T03 and T05–T07 own different output paths and were not touched.
