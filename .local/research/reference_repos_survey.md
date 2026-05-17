# Reference Dependencies Survey — Post 2026-04-11 Check

**Research date:** 2026-04-13  
**Scope:** All 17 entries in `workflow-system/agent/knowledge/reference-dependencies.yaml`  
**Cutoff:** Activity **after** `last_checked: 2026-04-11` (GitHub API `commits?since=2026-04-11T00:00:00Z` where applicable; docs/blog manual review)

---

## update_status

Per tracked id — whether material upstream change occurred after the last registry snapshot.

| id | Source | Updates since 2026-04-11? | Evidence (2026-04-13) |
|----|--------|---------------------------|------------------------|
| anthropic-advisor-tool | Anthropic API docs | **No version bump observed** | Fetched page still specifies beta header `advisor-tool-2026-03-01`, `advisor_20260301`, model pairs table (Haiku/Sonnet/Opus 4.6). Matches `last_known_version`. |
| superpowers | obra/superpowers | **No** | `0` commits since cutoff on public GitHub API. |
| anthropic-coordination-blog | claude.com blog | **No new post** after check | Article *Multi-agent coordination patterns* shows **April 10, 2026** publication date — on or before `last_checked` (2026-04-11). |
| vexp | vexp.dev (commercial) | **Unknown** | No public commit API; requires manual site/changelog review. |
| get-shit-done | gsd-build/get-shit-done | **Yes** | Commits after cutoff (e.g. 2026-04-13); **latest release `v1.35.0`** published **2026-04-11** (registry had `v1.34.0`). |
| gstack | garrytan/gstack | **Yes** | Large merge **2026-04-11** (`refactor: AI slop reduction… v0.16.3.0` #941). |
| caveman | JuliusBrussee/caveman | **Yes (minor)** | Commit **2026-04-12** (FUNDING.yml sponsor username) — non-functional for compression patterns. |
| edict | cft0808/edict | **No** | `0` commits since cutoff (public API). |
| karpathy-llm-wiki | gist | **No** (recent) | Gist history shows **2026-02-05** revisions only (no April activity). |
| google-scion | GoogleCloudPlatform/scion | **Yes** | Multiple commits **2026-04-13** (hooks/Kubernetes template follow-ups). |
| skillrouter | zhengyanzhao1997/SkillRouter | **No** | `0` commits since cutoff. |
| self-improving-system | gist | **No** (recent) | No April commits observed in gist history sample. |
| agent-skills-security | arXiv:2602.12430 | **N/A (static)** | Paper version unchanged in spot check. |
| primelocus-hydra | PrimeLocus/Hydra | **Inconclusive** | `api.github.com/repos/PrimeLocus/Hydra` returned **404** from this environment (rate limit, rename, or access). **Manual verification required** before relying on this URL. |
| ruflo | ruvnet/ruflo | **Boundary** | `1` commit dated **2026-04-11** (tier blockers fix v3.5.80); treat as same-day churn relative to `last_checked`. |
| christophera-bootstrap-seed | gist | **No** | Prior revisions **2026-02-05** scale. |
| spring-ai-agent-skills | spring-ai-community/spring-ai-agent-utils | **No** | `0` commits since cutoff. |

**Top relevance tier (score 5) summary:** advisor docs unchanged; superpowers quiet; coordination blog already captured at last check; vexp unverified; **get-shit-done** and **gstack** show the clearest **versioned** movement among high-signal GitHub sources.

---

## gap_analysis

`gap_ids` reference `S01-T06-synthesis.md` (not present in-repo in this survey). Below maps **tracked gap IDs → DevolaFlow state as of v4.5.0** using `CHANGELOG.md` and current artifacts.

### Addressed or materially improved (cite implementation)

| Gap id | Typical theme (inferred) | Status vs v4.5.0 codebase |
|--------|--------------------------|---------------------------|
| **H2** | Deterministic lean compression / caveman-style rules | **Largely addressed** — `src/devolaflow/compressor.py` (v4.1.0), expanded preserve/drop lists, `schemas/lean-dispatch.yaml` / `schemas/lean-report.yaml` compression tiers (v3.9+). |
| **H3** | Advisor-style escalation / borderline quality | **Addressed in design** — Advisor config in context profiles, borderline gate detection in `gate/scorer.py` (v3.9.0 CHANGELOG). *Runtime API coupling to Anthropic advisor tool remains host/IDE concern.* |
| **H1 / H4** (superpowers) | Iron laws, rationalization prevention | **Partial** — Rationalization tables in `SKILL.md` / `MVP-SKILL.md` (v3.9.0). **HARD-GATE tags / full two-stage review automation** not evidenced as enforced in CI. |
| **M1 / M8** (GSD) | Gate taxonomy, profiles | **Partial** — Extended `GateType` and gate scorer routing (v3.9.0). Full GSD-style hook + CI prompt-injection stack **not** mirrored end-to-end. |
| **H5 / H7** (gstack + self-improving) | Learnings JSONL, feedback flywheel | **Partial** — `learnings.py`, `feedback.py`, profile budgets (v3.9.0). `external-sources.jsonl` logging in `reference-dependencies.yaml` still marked **“when implemented”**. |
| **M2** (shared across sources) | Typed status / model hints | **Partial** — `schemas/lean-report.yaml` includes typed status enum (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`); `model_hint` surfaced via selector (v3.9.0). |

### Remaining / weak coverage

| Gap id | Sources | Remaining concern |
|--------|---------|-------------------|
| **H6** | superpowers | Deeper **enforcement ladder** (beyond tables): automated detection of P1 violations in agent runs. |
| **M7** | superpowers | **Two-stage review** (spec vs code) as distinct automated phases with artifacts. |
| **M3, L2, L5** | edict | **Institutional approve/reject**, strict permission matrix, fused audit trail — not first-class in Python gate module. |
| **M4** | SkillRouter | Retrieve-and-rerank skill routing at scale (1.2B pipeline) — DevolaFlow uses profile-based selection, not learned reranker. |
| **M5** | google-scion | **Container/worktree isolation** for every parallel L3 task — not default in DevolaFlow dispatch. |
| **M6** | agent-skills-security | Four-tier **trust model** + provenance in adapter pipeline — partial / policy-level only. |
| **L1** | vexp | AST graph + centrality for context — **not** implemented (tree-sitter graph DB). |
| **L3** | ruflo | 95–98% compression pipeline + swarm budgets — compressor is **rule-based**, not multi-stage neural pipeline. |
| **L6, L7** | christophera, spring-ai | Emergent bootstrap loop; progressive disclosure **across vendors** — aspirational in docs only. |
| **L8** | gstack | **Benefits-from** skill dependency graph as data structure — partial via schemas, not operational graph. |

### v4.5.0-specific note

Release **4.5.0** (CHANGELOG) focuses on **branding, human docs, CI, web demo** — it does **not** close additional `gap_ids` from the registry; gap progress is primarily **4.4.x / 4.3.x / 4.1.x** and earlier.

---

## cross_cutting_patterns

Patterns appearing in **three or more** tracked sources (conceptual consolidation):

1. **Layered quality gates + typed outcomes** — GSD gate taxonomy, superpowers status protocol, DevolaFlow gate models + lean status enum, edict approval binary.
2. **Model tiering / routing** — Anthropic executor↔advisor pairs; superpowers cheap/standard/capable; gstack sprint routing; primelocus/hydra strength routing; DevolaFlow `model_hint` + advisor sections.
3. **Compaction over summarization** — caveman intensity tiers; ruflo intent filtering; Karpathy wiki “verbatim” knowledge; DevolaFlow lean schemas + CO-2 verbatim rules.
4. **Operational memory** — gstack learnings JSONL; Karpathy wiki; self-improving gist; DevolaFlow learnings + feedback modules.
5. **Security / trust boundary** — GSD prompt-guard layers; agent-skills-security tiers; DevolaFlow workflow-skill + gate (policy-level).
6. **Isolation & parallelism** — google-scion worktrees/containers; coordination blog agent teams vs bus; DevolaFlow wave rules + file ownership.

---

## top_5_priorities (v5.0.0)

1. **Close the “tracking → action” loop** — Implement `knowledge/learnings/external-sources.jsonl` (or equivalent) and wire `self-update` / research workflows to **refresh `reference-dependencies.yaml` evidence** on a schedule, with NineS/EvoBench validation hooks (per `.local/feedbacks/feedback_for_v4.5.0.md` direction).
2. **Trust & provenance (M6)** — Explicit **skill/plugin trust tiers** in adapters and CI (map agent-skills-security paper to concrete checks), not only documentation.
3. **Isolation story (M5) optional profile** — Document and optionally automate **worktree/container** isolation for Wave/L3 parallel tasks (scion pattern), even if default remains lightweight.
4. **Graph-augmented context (L1) spike** — Feasibility study: optional `task_adaptive_selector` backend using repo AST/imports (vexp-style) behind a feature flag; benchmark with EvoBench.
5. **Enforcement depth for superpowers gaps (H6/M7)** — Move rationalization content toward **measurable** checks: linter rules for dispatcher-layer tool misuse, two-artifact review template (spec compliance artifact + code review artifact) in `gate/` or workflow templates.

---

## new_tracking_recommendations

| Action | Id / URL | Rationale |
|--------|----------|-----------|
| **Add (active_tracking)** | `https://github.com/forrestchang/andrej-karpathy-skills` | High community signal; **single-file CLAUDE.md** distilling Karpathy coding pitfalls — complements `karpathy-llm-wiki` (gist, wiki ops) with **actionable agent constraints**. Overlap: partial with superpowers (anti-slop) + DevolaFlow SKILL content — track explicitly to avoid duplicate synthesis. Suggested **relevance_score: 4** (or 5 if self-update workflow adopts it as primary checklist). |
| **Refresh** | get-shit-done | Bump `last_known_version` to **v1.35.0**; re-scan `references/gates.md` / hooks for delta worth porting. |
| **Refresh** | gstack | Note **v0.16.3.0**-era slop-scan / error-handling refactors — extract **“no silent failures”** patterns aligned with DevolaFlow rules. |
| **Verify / fix URL** | primelocus-hydra | Resolve **API 404** — confirm repo rename, archival, or access; update or **freeze_reference** per `tracking_policy`. |
| **Remove / downgrade** | *(none mandatory)* | No source clearly superseded; periodic entries remain appropriate for low-churn arXiv/gists. |

---

## andrej-karpathy-skills fit

- **Relationship to `karpathy-llm-wiki`:** Wiki gist emphasizes **persistent knowledge operations**; `andrej-karpathy-skills` is **prescriptive agent behavior** (pitfalls, CLAUDE.md). **Complementary**, not duplicate.
- **Relationship to superpowers:** Both target **failure modes and rationalization**; Karpathy repo is narrower (coding LLM pitfalls) vs superpowers’ broad skill OS. Use Karpathy as **concise supplemental** checklist in `self-update` / research templates.
- **Integration points:** `SKILL.md` / `MVP-SKILL.md` cross-links; optional `references/` doc; NineS research tasks to diff against DevolaFlow conventions.

---

## Method limitations

- GitHub API used **without authentication** — rate limits or errors may hide commits (notably **Hydra**).
- **Anthropic docs** and **blogs** may change without version strings; manual diff of HTML is advised on each biweekly review.
- **vexp.dev** requires manual changelog review.

---

*End of report.*
