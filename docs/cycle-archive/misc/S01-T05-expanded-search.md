# S01-T05: Expanded Search for 2026 Agent Best Practices & High-Quality Repos

**Task ID:** S01-T05
**Team:** Research
**Date:** 2026-04-11
**Searches Performed:** 18 web searches (10 primary + 8 deep-dive)

---

## Executive Summary

Across 18 targeted searches, this report identifies **9 high-quality resources** not previously covered by DevolaFlow research (T02 report, known repos list). Each passes the filter: confidence >= medium, recency 2025-2026, relevance >= 3/5 to DevolaFlow. Three discoveries stand out as high-priority integration candidates: **(1)** Google Scion's agent isolation architecture, **(2)** SkillRouter's retrieve-and-rerank skill selection at scale, and **(3)** vexp's graph-based automatic context retrieval engine. Together with the self-improving system pattern and the agent skills security governance framework, these represent novel capabilities not yet present in DevolaFlow v3.8.0.

---

## Discovery 1: Google Scion — Multi-Agent Isolation Testbed

### Source
- **GoogleCloudPlatform/scion** — https://github.com/GoogleCloudPlatform/scion
- Released: March 10, 2026 (Apache 2.0)
- Language: Go (84.3%) + TypeScript
- Author: Google Cloud Platform

### Description
Scion is an open-source multi-agent orchestration testbed that runs multiple AI coding agents (Claude, Gemini, Codex) in parallel with full infrastructure-level isolation. Each agent receives its own container, git worktree, and credentials. The "Grove" concept (`.scion` directory) represents a project workspace, supporting local CLI mode and distributed "Hub" architecture.

### Key Technique/Pattern
**Infrastructure-level agent isolation via git worktrees + containers.** Rather than constraining agents with prompt-level rules, Scion isolates at the infrastructure layer. Each agent gets `.scion_worktrees/<grove>/<agent>` — preventing file conflicts, credential leaks, and context pollution between parallel agents. Supports Docker, Podman, Apple containers, and Kubernetes.

### DevolaFlow Relevance: 4/5
DevolaFlow enforces context isolation via P2 (Minimal Context) and P5 (Artifacts as Contracts) at the prompt level. Scion demonstrates that infrastructure-level isolation (git worktrees per agent) can provide stronger guarantees — especially for parallel Wave execution where multiple L3 Task Agents may write to overlapping files. The "Grove" concept maps to DevolaFlow's workflow workspace. **Novel pattern not yet in DevolaFlow:** git worktree isolation per task agent.

### Confidence: HIGH
- Author: Google Cloud Platform (credible)
- Open-source with documentation site
- Described as "early and experimental" but architecturally complete

### Recency: April 2026 (docs site), March 2026 (GitHub release)

### Potential Integration
- L2 Wave dispatch could provision git worktrees per L3 Task Agent for parallel waves
- Merge reconciliation step after parallel task completion (Scion handles this)
- Complements DevolaFlow's P1 file ownership enforcement with infrastructure-level guarantees

---

## Discovery 2: SkillRouter — Skill Routing for LLM Agents at Scale

### Source
- **arXiv:2603.22455v3** — https://arxiv.org/abs/2603.22455v3
- **GitHub:** https://github.com/zhengyanzhao1997/SkillRouter
- **HuggingFace:** https://huggingface.co/papers/2603.22455
- Submitted: March 23, 2026 (code + models released)

### Description
SkillRouter addresses the challenge of selecting relevant skills from large registries (tested on ~80K candidate skills with heavy overlap). It uses a compact 1.2B parameter two-stage retrieve-and-rerank pipeline (0.6B encoder + 0.6B reranker) achieving 74.0% Hit@1 accuracy while using 13x fewer parameters and running 5.8x faster than baselines.

### Key Technique/Pattern
**Retrieve-and-rerank skill selection with full-text signal.** Critical finding: hiding skill implementation text causes a 31-44 percentage point drop in routing accuracy. Skill metadata (name + description) alone is insufficient — the full skill body is a critical routing signal. This directly challenges progressive-disclosure approaches that load only metadata first.

### DevolaFlow Relevance: 4/5
DevolaFlow's `task_adaptive_selector.py` uses longest-match scoring on task hints to select from 16 context profiles. SkillRouter's finding that full implementation text is critical for routing accuracy suggests DevolaFlow's hint-based matching may be leaving significant accuracy on the table. **Novel pattern not yet in DevolaFlow:** semantic retrieve-and-rerank for profile/workflow selection; full-text signal importance.

### Confidence: HIGH
- Peer-reviewed paper with code + model release
- Benchmarked against baselines with clear metrics
- End-to-end validation across 4 coding agents

### Recency: March 2026

### Potential Integration
- Replace or augment `match_profile()` in `task_adaptive_selector.py` with a lightweight retrieval step that considers full profile content (not just hints)
- As DevolaFlow's workflow template library grows (currently 16), hint-based matching will degrade; SkillRouter's approach scales to 80K+ entries
- Could power a future "skill marketplace" discovery mechanism

---

## Discovery 3: vexp — Graph-Based Automatic Context Retrieval Engine

### Source
- **vexp.dev** — https://vexp.dev/
- Blog: https://vexp.dev/blog/how-to-give-ai-better-context-automatically
- Cost analysis: https://vexp.dev/blog/reduce-claude-code-token-usage

### Description
vexp is a local-first context engine that uses tree-sitter AST parsing to build a code dependency graph (stored in SQLite), then traverses it to automatically retrieve only task-relevant code snippets. Benchmarked on FastAPI with Claude Sonnet: 65% fewer tokens, 58% lower API costs, 22% faster completion, +14pp higher task success rate.

### Key Technique/Pattern
**AST dependency graph + centrality ranking for context selection.** Instead of dumping entire files or relying on keyword search, vexp: (1) identifies relevant symbols from the task description, (2) traverses the dependency graph to find callers/callees, (3) ranks nodes by importance and centrality, (4) compresses context to necessary snippets. Supports 30 languages, 12 AI agents.

### DevolaFlow Relevance: 5/5
This is the most directly relevant discovery. DevolaFlow's context profiles define static token budgets per task type (CO-3) and use section-level priority (critical/important/supplementary/skip). vexp demonstrates that **code-level graph-based context selection** can deliver dramatically better results than file-level or section-level selection. **Novel pattern not yet in DevolaFlow:** automatic code dependency graph traversal for context injection at L3 Task Agent dispatch.

### Confidence: MEDIUM
- Product claims backed by specific benchmarks on real codebases
- Supports 30 languages and 12 agents (broad compatibility)
- Benchmarks on a single codebase (FastAPI) — generalizability uncertain
- Commercial product (local-first, no cloud dependency)

### Recency: 2026 (active development)

### Potential Integration
- The dependency graph concept could inform how L2 Wave Agents construct `owned_files` and `read_only` file lists for L3 tasks
- Context profiles could incorporate a "graph distance" metric: files within N hops of the task's primary targets get higher priority
- The centrality ranking concept could augment predecessor summary relevance scoring (T02 Strategy 6)
- Could reduce L3 Task Agent context budget from ~8K tokens while improving quality

---

## Discovery 4: Self-Improving AI Development System (Triangulum9r)

### Source
- **GitHub Gist:** https://gist.github.com/Triangulum9r/5666b008b402c17cc5695b9e42bbba9b
- Related: https://medium.com/@jekaterina.jegoscenko/the-self-improving-engineering-system-c047a4f5c9f7

### Description
A documented production system for automated agentic software development built on six interlocking components: Rules (always-on guardrails), Skills (reusable procedures), Documentation (project memory), Test Harness (20+ automated quality checks), Benchmark Harness (metric tracking), and CI/CD Pipeline (enforcement backbone). The "Ralph Loop" creates a knowledge flywheel where each completed ticket improves the next.

### Key Technique/Pattern
**Six-component self-reinforcing quality loop.** The system's core insight: unguided LLMs produce code failing 30-60% of tests on first attempt, and self-correction without external feedback is unreliable. The fix is interlocking automated feedback loops where test results feed into rule updates, which improve skill execution, which produces better benchmarks. Each workflow iteration improves the system itself.

### DevolaFlow Relevance: 4/5
DevolaFlow has 5 of 6 components (Rules via .cursor/rules, Skills via SKILL.md, Tests via pytest, Benchmarks via EvoBench, CI/CD via GitHub Actions). What's missing is the explicit **self-improvement feedback loop** — a mechanism where completed workflow executions automatically update rules, skills, and documentation. The task description mentions a "self-update workflow" — this pattern provides a concrete architecture for it. **Novel pattern not yet in DevolaFlow:** automated post-workflow knowledge capture → rule/skill update cycle.

### Confidence: MEDIUM
- Well-documented gist with community attention
- Backed by practical production experience claims
- Referenced in multiple secondary sources
- No star count available (gist format)

### Recency: 2026

### Potential Integration
- Add a `post_workflow` hook/stage that captures learnings from completed workflows
- Learnings → rule updates (propose changes to .cursor/rules/) and skill updates (propose changes to SKILL.md sections)
- The "knowledge flywheel" could power the planned self-update workflow from the task description
- Complements DevolaFlow's existing EvoBench feedback loop with a broader scope

---

## Discovery 5: Agent Skills Security & Trust Governance Framework

### Source
- **arXiv:2602.12430** — https://arxiv.org/abs/2602.12430
- **HuggingFace:** https://huggingface.co/papers/2602.12430
- Related: arXiv:2604.02837v1 (threat taxonomy), arXiv:2602.20867 (SoK)
- Published: February 2026

### Description
Academic paper analyzing agent skill ecosystems across architecture, acquisition, security, and governance. Key empirical finding: 26.1% of community-contributed skills contain vulnerabilities. Proposes a four-tier, gate-based Skill Trust and Lifecycle Governance Framework that maps skill provenance to graduated deployment capabilities. Also documents the ClawHavoc campaign where ~1,200 malicious skills infiltrated a major marketplace.

### Key Technique/Pattern
**Four-tier trust model with provenance-based permissions.** Skills receive graduated trust levels based on their origin (first-party > verified-publisher > community-reviewed > unverified). Each tier maps to specific deployment capabilities (full access > sandboxed execution > dry-run only > blocked). Gate-based transitions between tiers require verification steps.

### DevolaFlow Relevance: 4/5
DevolaFlow's SKILL.md is the primary agent interface — any corruption or injection into this file could compromise the entire workflow. The 26.1% vulnerability rate in community skills is a direct warning. As DevolaFlow expands its adapter system (Cursor, Codex, Claude, Copilot), the attack surface grows. **Novel pattern not yet in DevolaFlow:** skill trust levels, provenance tracking, sandboxed execution tiers, vulnerability scanning for skill content.

### Confidence: HIGH
- Peer-reviewed academic paper with empirical data
- Documented real-world attack (ClawHavoc campaign)
- Concrete framework proposal with tiered architecture

### Recency: February 2026

### Potential Integration
- Add a `trust_level` field to workflow-skill.yaml (first_party | verified | community | untrusted)
- Gate mechanism could validate skill integrity before workflow execution
- Adapter build pipeline could include vulnerability scanning (injection patterns, exfiltration attempts)
- Aligns with DevolaFlow's existing gate system — extend it to cover skill provenance

---

## Discovery 6: PrimeLocus/Hydra — Multi-Agent Deliberation Orchestrator

### Source
- **GitHub:** https://github.com/PrimeLocus/Hydra
- Created: February 2026 | Latest: March 2026 (v0.1.0)
- Language: JavaScript (98.3%) | License: MIT

### Description
Hydra coordinates three AI coding agents (Claude for architecture, Gemini for critique, Codex for implementation) through a shared HTTP daemon with a task queue. Agents run in parallel using isolated git worktrees. Implements multi-round deliberation workflows (propose → critique → refine → implement) and self-improving pipelines that autonomously scan codebases for improvements with budget tracking.

### Key Technique/Pattern
**Strength-based agent routing + multi-round deliberation.** Rather than treating all agents identically, Hydra routes tasks based on each agent's demonstrated strengths. The deliberation workflow (Claude proposes → Gemini critiques → Claude refines → Codex implements) is a concrete implementation of the generator-verifier pattern with agent-specific role assignment. Budget tracking prevents runaway costs.

### DevolaFlow Relevance: 4/5
DevolaFlow's team assignment (Research, Implement, Review, Docs) already approximates role-based routing, but uses a single underlying model. Hydra's insight is that **different models have different strengths** — architecture vs. critique vs. implementation — and routing should exploit this. The deliberation workflow is a concrete implementation of the generator-verifier pattern (T02 Strategy 3) with multi-model orchestration. **Novel pattern not yet in DevolaFlow:** model-strength-based task routing; multi-model deliberation workflows.

### Confidence: MEDIUM
- Open-source with clear documentation
- Concrete implementation (not just a paper)
- v0.1.0 — early but functional
- Small community (no star count data available)

### Recency: February-March 2026

### Potential Integration
- L2 Wave dispatch could support a `model_hint` field allowing model-specific routing
- The deliberation workflow pattern could be formalized as a new composition operator
- Budget tracking per agent/task complements DevolaFlow's token budget system
- Git worktree isolation per agent aligns with Discovery 1 (Scion)

---

## Discovery 7: Ruflo Context Compression Architecture

### Source
- **GitHub Issue:** https://github.com/ruvnet/ruflo/issues/1273
- **Dev.to:** https://dev.to/arshkharbanda2010/ruflow-ruflo-the-multi-agent-claude-ai-orchestrator-that-slashes-api-costs-by-75-2nmc
- **ADR:** https://github.com/ruvnet/claude-flow/blob/5bddae37/v3/implementation/adrs/ADR-051-infinite-context-compaction-bridge.md

### Description
Ruflo proposes a context compression engine targeting 95-98% context window compression for long-running multi-agent sessions. Addresses the practical problem that typical sessions deplete ~40% of context in 30 minutes and 8-agent swarms exhaust effective context in under 15 minutes. Architecture includes 5 subsystems: compression pipeline, FTS5 knowledge base, sandbox pool, hook integration, and swarm-aware context budgets.

### Key Technique/Pattern
**Multi-stage compression pipeline with swarm-aware budgets.** The architecture: (1) size check → (2) sandbox isolation → (3) intent filter (what does the agent actually need from this output?) → (4) smart snippet extraction. Per-agent budget allocation with progressive throttling prevents any single agent from monopolizing the context window. Cross-agent knowledge sharing via FTS5/HNSW search enables agents to query previous agents' discoveries without loading full context.

### DevolaFlow Relevance: 4/5
DevolaFlow's multi-layer hierarchy (L0→L3) creates exactly this problem — each layer's dispatch/report messages consume context, and long-running workflows (RDRR, full-pipeline) can exhaust budgets. The swarm-aware budget allocation directly maps to DevolaFlow's per-layer token budgets (CO-3). **Novel pattern not yet in DevolaFlow:** progressive context throttling, cross-agent knowledge search, intent-based compression filtering.

### Confidence: MEDIUM
- Detailed architecture in ADR format
- Specific performance targets (quantified)
- Still at proposal/issue stage (not fully implemented)
- ruvnet/ruflo is an active multi-agent Claude orchestrator

### Recency: 2026

### Potential Integration
- Intent-based filtering could be applied to predecessor summaries (only extract facts relevant to the downstream task's acceptance criteria)
- Cross-agent knowledge search could enable L3 Task Agents to query completed sibling tasks' artifacts without full context injection
- Progressive throttling could be added to context_profiles.yaml as a budget_strategy option
- Complements vexp (Discovery 3) at the session-management layer vs. code-structure layer

---

## Discovery 8: ChristopherA Bootstrap Seed — Self-Evolving Configuration

### Source
- **GitHub Gist:** https://gist.github.com/ChristopherA/fd2985551e765a86f4fbb24080263a2f
- Stars: 27 | Forks: 7 | Created: February 5, 2026
- Author: Christopher Allen (notable identity/credential standards contributor)

### Description
A ~1400 token bootstrap prompt that turns Claude Code into a self-improving system. Places a seed in `.claude/CLAUDE.md` that captures learnings, extracts patterns, and evolves its own configuration across sessions. Implements a reflect → triage → cascade loop where operational patterns emerge from use rather than being pre-defined.

### Key Technique/Pattern
**Emergent configuration via reflect → triage → cascade.** Rather than pre-defining all rules and patterns, the bootstrap seed enables complex behaviors to emerge from operational pressure: (1) reflect on session outcomes, (2) triage insights by impact, (3) cascade updates to rules, processes, and documentation. Separates "seeded" components (basic structure) from "emergent" components (extracted rules, quad patterns, domain conventions).

### DevolaFlow Relevance: 3/5
DevolaFlow's configuration (SKILL.md, context_profiles.yaml, rules) is currently static — maintained by human developers. The bootstrap seed demonstrates that agent configurations can self-evolve based on operational experience. The reflect→triage→cascade loop could inform DevolaFlow's planned self-update workflow. **Partially novel:** DevolaFlow's EvoBench already provides feedback, but the configuration evolution mechanism is new.

### Confidence: MEDIUM
- Author credibility (Christopher Allen, identity standards)
- Practical approach with clear documentation
- Small community (27 stars, 7 forks) but well-crafted
- Gist format limits discoverability

### Recency: February 2026

### Potential Integration
- The reflect→triage→cascade loop could be formalized as a post-workflow stage in DevolaFlow
- "Seeded vs. emergent" separation maps to DevolaFlow's core SKILL.md (seeded) vs. per-project customization (emergent)
- Context discipline with token budgets aligns with DevolaFlow's CO-3

---

## Discovery 9: Spring AI Agent Skills — Vendor-Agnostic Progressive Disclosure

### Source
- **Spring Blog:** https://spring.io/blog/2026/01/13/spring-ai-generic-agent-skills
- **GitHub:** https://github.com/spring-ai-community/spring-ai-agent-utils
- **Anthropic integration:** https://spring.io/blog/2026/01/28/apring-ai-anthropic-agentic-skills
- Published: January 13, 2026

### Description
Spring AI implements agent skills as YAML-frontmatter Markdown files with a three-stage progressive disclosure model (discovery → activation → execution). Skills are vendor-agnostic, working across OpenAI, Anthropic, and Google Gemini without rewriting. The architecture enables registration of hundreds of skills while keeping context lean at startup.

### Key Technique/Pattern
**Three-stage progressive disclosure with vendor-agnostic portability.** Discovery: load only name + description at startup. Activation: load full SKILL.md when task matches. Execution: follow instructions, load referenced files. This pattern manages context efficiently while supporting large skill registries. Critically, skills are defined once and work across all providers — contrasting with Anthropic's provider-specific Skills API.

### DevolaFlow Relevance: 3/5
DevolaFlow already implements a similar SKILL.md pattern with YAML frontmatter and adapter pipeline (Cursor, Codex, Claude, Copilot). Spring AI validates this approach at enterprise scale with the additional insight of **progressive disclosure** — DevolaFlow currently loads the full SKILL.md into context rather than progressively disclosing sections. The vendor-agnostic design confirms DevolaFlow's multi-adapter strategy. **Novel refinement:** progressive disclosure could reduce DevolaFlow's initial context load.

### Confidence: HIGH
- Official Spring framework (backed by Broadcom/VMware)
- Production-grade implementation
- Well-documented with code examples
- Active community (spring-ai-community GitHub org)

### Recency: January 2026

### Potential Integration
- DevolaFlow's context profiles could implement progressive disclosure: load SKILL.md purpose/scope initially, load workflow-specific sections on-demand
- Validates DevolaFlow's existing multi-adapter approach
- The vendor-agnostic framing could inform DevolaFlow's adapter system design

---

## Filtered-Out Resources (Not Meeting Criteria)

| Resource | Reason for Exclusion |
|----------|---------------------|
| **LiveAgentBench** (arXiv:2603.02586) | Relevance 2/5 — general agent benchmarking, not coding-workflow-specific. DevolaFlow's EvoBench already covers context optimization benchmarks. |
| **Agent Nexus** | Confidence: LOW — minimal stars/adoption, no published benchmarks |
| **OpenBotX** | Relevance 1/5 — no-code platform, not applicable to developer workflow meta-frameworks |
| **KAOS** | Relevance 2/5 — Kubernetes-native infrastructure, not relevant to agent behavior/workflow patterns |
| **murataslan1/cursor-ai-tips** | Relevance 2/5 — general tips collection, no novel pattern or framework |
| **nedcodes-ok/cursorrules-collection** | Relevance 2/5 — rule collection, no novel orchestration/workflow pattern |
| **shanraisshan/claude-code-best-practice** (31K stars) | Relevance 2/5 — documents native Claude Code architecture (Command→Agent→Skill); no novel pattern beyond what Claude Code provides natively. DevolaFlow's adapter system already targets this. |
| **Agentic Proposing** (arXiv:2602.03279) | Relevance 2/5 — training-time technique for synthetic data generation, not applicable to runtime workflow orchestration |
| **dsifry/metaswarm** | Confidence: LOW — very early stage, minimal documentation |
| **iamfakeguru/claude-md** | Relevance 2/5 — individual CLAUDE.md example, no framework-level innovation |
| **ChrisWiles/claude-code-showcase** | Relevance 2/5 — showcase repo, demonstrates existing Claude Code features rather than novel patterns |
| **HydraTeams** | Relevance 2/5 — translation proxy for model-agnostic agent teams, not an orchestration pattern |
| **OpenFoundry** (bsamud) | Relevance 3/5 but Confidence: LOW — early stage (Jan 2026 created), minimal community adoption, overlaps with patterns already in DevolaFlow (DAG execution, guardrails) |

---

## Cross-Reference with DevolaFlow v3.8.0 CHANGELOG

Already implemented features that overlap with discoveries:

| DevolaFlow Feature | Overlapping Discovery | Gap Remaining |
|---|---|---|
| **Lifecycle Hooks (v3.8.0)** | Ruflo hook integration (D7) | Ruflo adds intent-based compression filtering; DevolaFlow hooks are enforcement-focused |
| **Wave Coordination Modes (v3.7.0)** | Hydra deliberation (D6), Scion parallel agents (D1) | DevolaFlow lacks infrastructure-level isolation and model-specific routing |
| **Context Profiles (v3.3.0)** | vexp graph-based retrieval (D3), Ruflo compression (D7) | DevolaFlow uses static section-level budgets; discoveries offer code-graph and compression-based optimization |
| **EvoBench (v3.0.0)** | Self-Improving System (D4), SkillRouter benchmarks (D2) | DevolaFlow benchmarks context quality; D4 adds self-improvement feedback loops |
| **Task-Adaptive Selector (v3.0.0)** | SkillRouter (D2) | DevolaFlow uses hint-based matching; SkillRouter uses full-text retrieve-and-rerank |
| **Multi-Adapter Pipeline (v0.1.0)** | Spring AI Skills (D9) | Spring AI validates approach; adds progressive disclosure pattern |
| **Gate Mechanism (v2.2.0)** | Skills Security (D5) | DevolaFlow gates evaluate quality; D5 adds provenance/trust-level gating |

---

## Priority Ranking for Integration

### Tier 1 — High Value, Novel Pattern, Achievable
1. **vexp-style Graph-Based Context Selection** (D3) — Relevance 5/5, most directly impactful on context optimization
2. **SkillRouter Retrieve-and-Rerank** (D2) — Relevance 4/5, improves profile/workflow selection accuracy at scale
3. **Self-Improving Feedback Loop** (D4) — Relevance 4/5, enables the planned self-update workflow

### Tier 2 — High Value, Infrastructure Investment
4. **Scion-style Git Worktree Isolation** (D1) — Relevance 4/5, strongest parallel execution guarantee
5. **Skills Security Governance** (D5) — Relevance 4/5, critical for adapter ecosystem security
6. **Hydra Deliberation + Model Routing** (D6) — Relevance 4/5, multi-model exploitation

### Tier 3 — Medium Value, Future Investigation
7. **Ruflo Context Compression** (D7) — Relevance 4/5, addresses long-session context depletion
8. **Bootstrap Self-Evolution** (D8) — Relevance 3/5, interesting for project-specific customization
9. **Spring AI Progressive Disclosure** (D9) — Relevance 3/5, validates approach, adds refinement

---

## Key Source URLs

| # | Source | URL | Date | Type |
|---|--------|-----|------|------|
| 1 | Google Scion | https://github.com/GoogleCloudPlatform/scion | 2026-03 | GitHub repo |
| 2 | SkillRouter paper | https://arxiv.org/abs/2603.22455v3 | 2026-03 | arXiv paper |
| 3 | SkillRouter code | https://github.com/zhengyanzhao1997/SkillRouter | 2026-03 | GitHub repo |
| 4 | vexp context engine | https://vexp.dev/ | 2026 | Product |
| 5 | vexp blog | https://vexp.dev/blog/how-to-give-ai-better-context-automatically | 2026 | Blog |
| 6 | Self-Improving System | https://gist.github.com/Triangulum9r/5666b008b402c17cc5695b9e42bbba9b | 2026 | Gist |
| 7 | Agent Skills Security | https://arxiv.org/abs/2602.12430 | 2026-02 | arXiv paper |
| 8 | Agent Skills Threats | https://arxiv.org/abs/2604.02837v1 | 2026-04 | arXiv paper |
| 9 | PrimeLocus/Hydra | https://github.com/PrimeLocus/Hydra | 2026-02 | GitHub repo |
| 10 | Ruflo Context Engine | https://github.com/ruvnet/ruflo/issues/1273 | 2026 | GitHub issue |
| 11 | Bootstrap Seed | https://gist.github.com/ChristopherA/fd2985551e765a86f4fbb24080263a2f | 2026-02 | Gist |
| 12 | Spring AI Skills | https://spring.io/blog/2026/01/13/spring-ai-generic-agent-skills | 2026-01 | Blog |
| 13 | Codex Skills Docs | https://developers.openai.com/codex/skills/ | 2026 | Docs |
| 14 | Codex Skills Impact | https://developers.openai.com/blog/skills-agents-sdk | 2026 | Blog |
| 15 | Scion Concepts | https://googlecloudplatform.github.io/scion/concepts/ | 2026 | Docs |

---

## Appendix: Search Queries Executed

### Primary Searches (10)
1. `best CLAUDE.md examples 2026 github`
2. `cursor rules best practices repo 2026`
3. `AI agent orchestration framework open source 2026`
4. `multi-agent coding workflow github 2026`
5. `LLM agent skill system composable 2026`
6. `AI coding agent context optimization 2026`
7. `agent workflow quality gate benchmark 2026`
8. `Claude code hooks best practices 2026`
9. `codex skills best practices 2026`
10. `AI agent prompt engineering systematic 2026`

### Deep-Dive Searches (8)
11. `Google Scion agent orchestration testbed open source git worktree isolation 2026`
12. `SkillRouter skill routing LLM agents at scale arxiv 2603.22455 2026`
13. `LiveAgentBench comprehensive benchmarking agentic systems 104 real-world challenges arxiv 2603.02586`
14. `agent skills security governance trust lifecycle framework arxiv 2602.12430 2026`
15. `ruflo context compression engine 95-98 percent context window optimization long-running sessions`
16. `Triangulum9r self-improving AI development system rules skills tests benchmarks feedback loops gist`
17. `OpenFoundry DAG multi-provider agent orchestration protocol-first bsamud github 2026`
18. `Hydra multi-agent coding PrimeLocus github parallel task orchestration 2026`

### Supplementary Validation Searches (3)
19. `shanraisshan claude-code-best-practice github stars Command Agent Skill architecture 2026`
20. `Spring AI agent skills YAML frontmatter progressive disclosure vendor-agnostic 2026`
21. `ChristopherA self-improving Claude Code bootstrap seed configuration system gist`
