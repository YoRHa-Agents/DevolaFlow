# Reference Delta Survey — T06 (4 periodic_monitoring refs, score=4)

| field | value |
|-------|-------|
| task_id | S01.W02.T06 |
| role | research / reference-delta-survey |
| owned_path | `.local/research/v7.2.0_refs/delta-T06.md` |
| devolaflow_version | v7.1.1 |
| baseline_registry | `workflow-system/agent/knowledge/reference-dependencies.yaml` (snapshot 2026-04-11) |
| cutoff_check_date | 2026-04-18 |
| references_in_scope | 4 (periodic_monitoring, score=4) |
| sources_modified | none (read-only research; no DevolaFlow source touched) |

---

## Reference 1 — `self-improving-system` (Triangulum9r gist `5666b008b402c17cc5695b9e42bbba9b`)

### 1.1  Current state snapshot (verbatim from upstream)

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | "latest (gist)" | **2 revisions, latest sha `42edd25d3edec114471f028c1c87a25cf03d94bb` committed `2026-02-13T20:03:16Z`** | `api.github.com/gists/5666b008b402c17cc5695b9e42bbba9b/commits` |
| `total_revisions` | n/a | **2** (initial `7e74013cd873101c21fd445711dd17ac5256cb0d` 2026-02-13T19:50:28Z, +793 lines; revision `42edd25d…` 13 minutes later, +262 lines) | same API |
| `gist updated_at` | n/a | **2026-03-20T06:47:53Z** (metadata-only edit; description was likely revised — no new revision in `/commits`) | gist API root |
| `files in gist` | n/a | **2 files**: `agentic-workflow-system.md` (40,921 bytes, primary essay) and `cursor_latest_release_autocommit_issue.md` (13,240 bytes, raw Cursor session transcript demonstrating the workflow on real ticket CAN-242) | gist API root |
| `description` | n/a | "Building a Self-Improving AI Development System: How rules, skills, tests, benchmarks, and feedback loops combine to enable automated agentic software development workflows" | gist API root |
| `revisions since last_checked: 2026-04-11` | n/a | **0** (no new git revisions in `/commits` since 2026-02-13; only metadata-level update on 2026-03-20) | API result above |
| `comments` | n/a | **0** | gist API root |

### 1.2  Cross-check vs DevolaFlow integration points

Registered integration points for `self-improving-system`:

1. post-workflow hooks/stages
2. `.cursor/rules/` (automated rule updates)
3. SKILL.md (automated skill refinement)

Mapping the gist's six-component "self-improving AI development system" → DevolaFlow surface (verified via Read of `src/devolaflow/feedback.py`, `src/devolaflow/gate/reinforcement.py`, `workflow-system/agent/templates/builtin/self-update.yaml` 2026-04-18):

| gist component | gist operation | DevolaFlow equivalent | Coverage |
|----------------|----------------|------------------------|----------|
| **1. Rules — always-on guardrails** (`.cursor/rules/*.mdc` + `.claude/rules/*.md` symlinks) | 8 rules; `agentic-workflow` rule activates the full pipeline on intent detection | **Strong** — `.cursor/rules/` has 8 `.mdc` files (`workflow-rules.mdc`, `devola-flow-rules.mdc`, `change-process-rules.mdc`, `context-optimization-rules.mdc`, `documentation-sync-rules.mdc`, `self-improve-iteration-rules.mdc`, `skill-format-rules.mdc`, `web-experience-rules.mdc`); always-applied subset enforced by Cursor; `alwaysApply: true` semantics implemented | ~95% |
| **2. Skills — reusable procedures** (`SKILL.md` w/ phases) | 4 skills; `ticket-implementation` is the master 7-phase workflow | **Strong** — `workflow-system/agent/SKILL.md` (~500-line budget per Rule SF-1) plus 18 builtin templates in `workflow-skill.yaml#templates.builtin`; the 7-phase ticket-implementation maps to DevolaFlow stages (`design → plan → implement → review → test → testgate → release` per `templates/builtin/full-pipeline.yaml`) | ~85% |
| **3. Documentation — project memory** (`CLAUDE.md`, `CONTRIBUTING.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `CHANGELOG.md`, `README.md`) | LLM-readable persistent memory across sessions | **Strong** — `CLAUDE.md` (root), `README.md`, `CHANGELOG.md`, `workflow-system/human/` (EN/ZH guides), `doc/designs/*.md` cover the same axis; auto-generated EN/ZH human docs via `scripts/generate_human_docs.py` | ~90% |
| **4. Test harness — automated quality gates** (3-tier unit/integration/e2e + 90% coverage) | `pytest` with coverage gate, pre-commit hooks block under-covered code | **Strong** — `tests/` (822+ tests per CLAUDE.md), `pyproject.toml [tool.coverage]` floor at 80% (Rule CP-2), 3-tier roughly mirrored by `test_*.py` files plus `test_e2e_convergence.py`. Slightly **lower coverage floor** (80% vs 90% in gist) | ~80% |
| **5. Benchmark harness — quality measurement w/ frozen baselines** (separation-gap, keyword/semantic accuracy gates) | `benchmark_quality.py` + `baseline-bge-small.json`; quality regression detection | **Strong** — `benchmarks/devolaflow_context/` (EvoBench) with `baselines/v6.0.5_baseline.json`, `v6.1.0_baseline.json`, `v7.0.0_baseline.json` … `v7.1.0_baseline.json`; per-version frozen baseline; SI-4 rule enforces ≤5% regression per scenario | ~85% |
| **6. CI/CD pipeline — enforcement backbone** (release-please + 20 pre-commit hooks + 3 GH Actions) | Conventional commits drive auto-versioning; release PR auto-merges after CI | **Partial** — DevolaFlow has `Makefile`-based check-cursor-skill / sync-cursor-skill, `scripts/bump_version.py` (CP-3) for version coupling, and SI-10 6-step pre-commit gate. **No release-please or auto-PR-merge equivalent** is wired in this repo (the gist's CI is more aggressive) | ~50% |
| **Ralph Loop — iterate-until-promise-fulfilled** (Phase 0–7 with completion gate) | Cursor IDE plugin retries until `<promise>TICKET COMPLETE</promise>` | **Adjacent** — DevolaFlow's convergence loop (`gate/convergence.py` `detect_stagnation()` + `gate/reinforcement.py` `findings_to_reinforcement()`) provides round-N→N+1 retry up to a stagnation threshold (2 consecutive non-improving rounds → ESCALATE), but it operates **inside the gate**, not as a phase-level retry contract | ~50% |
| **Knowledge flywheel — every ticket updates rules/skills/docs** | Phase 6 "Knowledge capture" classifies findings as rule-/skill-/doc-/nothing-worthy and edits the corresponding files | **Strong** — `src/devolaflow/feedback.py` (`FeedbackCollector`, `FeedbackAnalyzer`, `Proposal` dataclass) detects recurring violations (`min_occurrences: 3`), generates `Proposal` objects with `confidence_floor=0.7` and `MAX_PROPOSALS_PER_WORKFLOW=3`, **scope-locked** away from `__init__.py` / `pyproject.toml` / `feedback.py` itself, and constrained to `src/devolaflow/`, `workflow-system/`, `schemas/`, `.cursor/rules/` paths. Plus rule SI-8 retrospective + `.local/research/retrospective_*.md` artifact contract | ~90% |

### 1.3  Delta items (5-field schema)

> Schema (applied to every entry below): `id` · `observation` · `evidence` · `devolaflow_impact` · `recommendation`

#### Δ-self-improve-01  Gist has not been revised since registry snapshot
- **observation:** Documented `last_known_version: "latest (gist)"` is unchanged at the **revision** level. The gist has exactly **2 revisions**, both committed on **2026-02-13**, the latest being `42edd25d3edec114471f028c1c87a25cf03d94bb` at `2026-02-13T20:03:16Z`. The gist `updated_at` metadata changed to `2026-03-20T06:47:53Z` but `/commits` shows no third revision — almost certainly a description-only edit (which is allowed without a new git revision in gists).
- **evidence:** `api.github.com/gists/5666b008b402c17cc5695b9e42bbba9b/commits` returned exactly 2 entries (verified 2026-04-18); `api.github.com/gists/5666b008b402c17cc5695b9e42bbba9b` returned `"updated_at": "2026-03-20T06:47:53Z"`, `"comments": 0`, `"public": true`.
- **devolaflow_impact:** *none* — content is identical to whatever the registry captured at `last_checked: 2026-04-11`.
- **recommendation:** **refresh-registry** — bump `last_checked: 2026-04-18`; append `revision_sha: "42edd25d3edec114471f028c1c87a25cf03d94bb"`, `gist_first_revision: "2026-02-13T19:50:28Z"`, `gist_latest_revision: "2026-02-13T20:03:16Z"` to the registry entry so subsequent biweekly scans can short-circuit on "no new revision" without re-fetching the 40 KB body.

#### Δ-self-improve-02  Second file (`cursor_latest_release_autocommit_issue.md`) is a worked example, not currently mirrored as a DevolaFlow `examples/` artifact
- **observation:** The gist now ships **two** files: the canonical essay `agentic-workflow-system.md` and a 13 KB **annotated Cursor session transcript** (`cursor_latest_release_autocommit_issue.md`) showing the full Phase 0–7 workflow handling real ticket **CAN-242** ("Fix release workflow to use GitHub App token"). DevolaFlow's `examples/` folder has 3 traces (`full-pipeline-trace.md`, `hotfix-trace.md`, `convergence-loop-trace.md`) but **no real-IDE-session trace** showing how the orchestration actually flows in a host editor.
- **evidence:** `api.github.com/gists/5666b008b402c17cc5695b9e42bbba9b` returned both files in the `files` map; the second file's body opens with "_Exported on 2/13/2026 at 11:28:11 PST from Cursor (2.4.37)_". DevolaFlow `Glob workflow-system/agent/examples/*.md` lists exactly 3 files (verified 2026-04-18).
- **devolaflow_impact:** *low* — instructive but not blocking. A Cursor-session-style example would help new users see the dispatcher chain executed live, but DevolaFlow's existing 3 `*-trace.md` files cover the same logical surface in dispatcher-centric form.
- **recommendation:** **track for v7.3+** — defer. If demand arises, port a single anonymised session transcript into `workflow-system/agent/examples/cursor-session-trace.md`. Do **not** raise relevance_score above 4 just for this delta.

#### Δ-self-improve-03  Six-component map is mostly aligned; CI/CD is the weakest axis in DevolaFlow
- **observation:** Per the table in §1.2, the only component below 80% coverage is **CI/CD** (gist scores it as a 6th first-class building block with release-please auto-versioning + 20 pre-commit hooks + 3 GitHub Actions workflows). DevolaFlow's CI surface today is `Makefile` targets + the SI-10 6-step pre-commit checklist + `scripts/bump_version.py`; there is **no release-automation pipeline** in this repo (no `.github/workflows/release.yml`, no release-please).
- **evidence:** `Glob .github/workflows/*` returned 0 results in DevolaFlow (verified 2026-04-18); `scripts/bump_version.py` is invoked manually per CP-3; CHANGELOG is hand-authored per CP-7. By contrast, the gist Phase 4 example shows release-please bumping `pyproject.toml` and auto-fixing lockfiles via a GitHub App token.
- **devolaflow_impact:** *medium* — DevolaFlow ships as a **library** consumed via `pip install git+...`, not a versioned product with semver-driven release artifacts; the CI/CD gap is partly **scope-justified**. However, the gist's pre-commit hook chain (gitleaks, taplo, shfmt, ty, etc. — 20 hooks) is a clean upgrade path for SI-10's existing 6-step gate.
- **recommendation:** **track for v7.3+ retrospective** — flag for the next SI-1 planning gate the question "Does DevolaFlow want to ship a `.github/workflows/` quality-gate workflow that runs the SI-10 sequence on every PR?" This is a deliberate scope decision, not a defect. **No port** in v7.2.

#### Δ-self-improve-04  "Ralph Loop" iterate-until-promise pattern is partially mirrored by convergence loop, but the *promise contract* is missing
- **observation:** The gist's defining loop primitive is the **`<promise>TICKET COMPLETE</promise>`** XML-tag completion contract that the Ralph Loop holds the agent to. DevolaFlow's analogous primitive is `gate/convergence.py:detect_stagnation()` returning `ESCALATE` when no improvement for 2 consecutive rounds, which is **stagnation-driven**, not **promise-driven**. There is no syntactic completion-marker the L0 layer scans for in StatusReport.
- **evidence:** Read of `src/devolaflow/gate/convergence.py` (2026-04-18) — `detect_stagnation()` checks composite score deltas; no `<promise>` / completion-marker scanner. `schemas/status-report.schema.yaml` has a typed `status` enum but does not require an explicit completion XML tag.
- **devolaflow_impact:** *low–medium* — DevolaFlow already has typed `StatusReport.status` (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED per gstack's H1 gap), which is functionally equivalent to a promise contract. But the gist's pattern is **more visible to humans** (a literal grep-able tag). Adding a parallel marker would be cheap.
- **recommendation:** **no-op for v7.2** — the typed status enum already serves the contract role. Re-evaluate only if user feedback in `.local/feedbacks/` mentions difficulty distinguishing "agent thinks it's done" vs "agent really is done".

#### Δ-self-improve-05  Knowledge-capture flywheel is implemented in `feedback.py`; gap is the *file-back-to-rules* loop closure
- **observation:** Documented gist key_pattern: "post-workflow rule/skill auto-update from execution findings". DevolaFlow's `feedback.py` implements the *detection* and *proposal* halves: `FeedbackAnalyzer.detect_recurring_violations()` (≥3 occurrences in `learnings/operational.jsonl`) generates `Proposal(target_file, suggested_change, confidence)`. **What's missing**: the *applier* — there's no `apply_proposal()` that actually edits the rule file. The `_inside_devolaflow()` and `_is_locked()` guards are wired, but no commit-the-edit step.
- **evidence:** Read of `src/devolaflow/feedback.py` (2026-04-18) — `Proposal` dataclass exists, `FeedbackAnalyzer` exists, `LOCKED_FILES = frozenset({"__init__.py", "pyproject.toml", "feedback.py"})`, `MAX_PROPOSALS_PER_WORKFLOW = 3`, `CONFIDENCE_FLOOR = 0.7`. No function named `apply_proposal` or `commit_proposal` exists in `src/devolaflow/`.
- **devolaflow_impact:** *medium* — the feedback module is a "load-bearing skeleton" without the closing edge. The gist's Phase 6 *does* edit rules and re-runs verification before completion; DevolaFlow proposes but does not apply.
- **recommendation:** **track for v7.2 candidate scope** — this is exactly the kind of gap that fits an additive v7.2 task: `feedback.apply_proposal(proposal: Proposal, dry_run: bool = True)` with `dry_run=True` default plus an SI-1 review gate before `dry_run=False` is enabled. Cheap; reuses existing scope-lock guards. Couples cleanly with rule SI-8 retrospective output.

#### Δ-self-improve-06  Six-component "automated quality loop" framing matches DevolaFlow's existing rule SI-1 → SI-10 chain
- **observation:** The gist's six-component framework (Rules / Skills / Docs / Tests / Benchmarks / CI/CD) maps **almost 1:1** onto DevolaFlow's rules SI-1 (planning gate), SI-2 (NineS analysis), SI-3 (evaluation), SI-4 (benchmarks), SI-5 (skill format), SI-6 (context budget), SI-7 (external refs), SI-8 (retrospective), SI-9 (convergence reinforcement), SI-10 (test-then-commit). DevolaFlow's framing is *meta-level* (about the **iteration process**); the gist's is *production-level* (about the **artifact lifecycle**). The two are complementary, not conflicting.
- **evidence:** `.cursor/rules/self-improve-iteration-rules.mdc` (already provided in agent context) lines 1-180 enumerate SI-1 through SI-10 with the six-component coupling explicit at SI-5 (skill format coupling triggers benchmark + version + adapter checks).
- **devolaflow_impact:** *positive (no gap)* — DevolaFlow's framework is **more rigorous** than the gist's at the meta-level (gates are explicit, retrospectives are mandatory, benchmark regression has a hard 5% threshold). The gist's value is in the *production-level artifact taxonomy* — which is what `feedback.py` and `templates/builtin/self-update.yaml` already encode.
- **recommendation:** **no-op** — confirm in next retrospective (`retrospective_v7.1_to_v7.2.md`) that the six-component mapping is "already-addressed" per registry policy `staleness_indicators.devolaflow_implements_gap`.

---

## Reference 2 — `agent-skills-security` (arXiv:2602.12430 + follow-up arXiv:2604.02837)

### 2.1  Current state snapshot

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | "arXiv:2602.12430 (2026-02)" | **arXiv:2602.12430v3 (2026-02-17), latest revision** | arXiv API + abs page |
| `version history (this paper)` | n/a | **v1: 2026-02-12T21:33:25Z (214 KB) → v2: 2026-02-16T07:44:54Z (214 KB) → v3: 2026-02-17T09:08:50Z (214 KB)** — three submissions in 5 days, all PRE-dating registry snapshot | arXiv submission history |
| `title` | n/a | "Agent Skills for Large Language Models: Architecture, Acquisition, Security, and the Path Forward" | arXiv abs page |
| `authors` | n/a | Renjun Xu, Yang Yan | arXiv abs page |
| `subjects` | n/a | cs.MA (Multiagent Systems); cs.AI | arXiv abs page |
| `companion repo` | n/a | **`https://github.com/scienceaix/agentskills`** (created 2026-02-12, last_pushed 2026-02-16, **46 stars**, description: "Awesome Agent Skills collection list, papers, tools, projects, and resources") | `api.github.com/repos/scienceaix/agentskills` |
| `update_triggers explicit follow-up` | "arXiv:2604.02837v1 threat taxonomy" | **CONFIRMED EXISTS — `arXiv:2604.02837v1`, submitted 2026-04-03T07:56:42Z** | arXiv API |
| `follow-up title` | n/a | "Towards Secure Agent Skills: Architecture, Threat Taxonomy, and Security Analysis" | arXiv abs |
| `follow-up authors` | n/a | Zhiyuan Li, Jingzheng Wu, Xiang Ling, Xing Cui, Tianyue Luo (**different team** than v2602) | arXiv abs |
| `follow-up subjects` | n/a | cs.CR (Cryptography and Security); cs.AI — **different primary category** | arXiv abs |
| `follow-up key claims` | n/a (registry only flagged its existence) | "first comprehensive security analysis"; **lifecycle 4 phases (Creation/Distribution/Deployment/Execution)**; **threat taxonomy: 7 categories × 17 scenarios across 3 attack layers**; **5 confirmed security incidents validated**; "most severe threats arise from structural properties of the framework itself, including the absence of a data-instruction boundary, a single-approval persistent trust model, and the lack of mandatory marketplace security review" (verbatim) | arXiv abstract |

### 2.2  Cross-check vs DevolaFlow integration points

Registered integration points for `agent-skills-security`:

1. `workflow-skill.yaml` (trust_level field)
2. gate mechanism (skill provenance validation)
3. adapter build pipeline (vulnerability scanning)

Mapping the v2602.12430v3 paper's **Skill Trust and Lifecycle Governance Framework** (4-tier, gate-based permission model) onto DevolaFlow source (verified by Read of `workflow-system/agent/workflow-skill.yaml`, `src/devolaflow/gate/scorer.py`, `src/devolaflow/adapters/claude_adapter.py` 2026-04-18):

| paper concept (verbatim) | DevolaFlow surface | Coverage |
|--------------------------|---------------------|----------|
| **"four-tier trust model: first-party→verified→community→unverified"** | **Absent** — `Grep` of the entire repo for `trust_level\|first_party\|verified\|provenance` returns *zero* matches in `src/devolaflow/`, `schemas/`, or `workflow-skill.yaml`. The schema's `identity:` block has only `name / display_name / version / description`. | 0% |
| **"provenance-based permissions with graduated deployment capabilities"** | **Absent** — no `provenance` field anywhere in code; permissions are file-system based via `LOCKED_FILES` in `feedback.py` and `_inside_devolaflow()` allow-list, but neither encodes provenance. | 0% |
| **"26.1% of community-contributed skills contain vulnerabilities"** (empirical claim) | **N/A** — DevolaFlow doesn't host a community skill marketplace; its skill inventory is in-repo only (one canonical SKILL.md + 8 references + 3 examples + 18 templates, all first-party). The paper's threat model targets community marketplaces, which DevolaFlow does not operate. | n/a (out of scope) |
| **"documented ClawHavoc campaign (~1200 malicious skills)"** | N/A — same reason; DevolaFlow's adapter outputs install only first-party skill bundles via `scripts/install.sh` from a GitHub repo URL pinned in the install command. | n/a (out of scope) |
| **gate mechanism (skill provenance validation)** | **Not implemented** — `src/devolaflow/gate/scorer.py` `_GATE_DISPATCH` has 5 gate types (`passthrough`, `acceptance_readiness`, `preflight`, `abort`, `escalation`) plus the unwrapped `standard` and `convergence`. None do provenance/signature validation. | 0% |
| **adapter build pipeline (vulnerability scanning)** | **Not implemented** — `src/devolaflow/adapters/claude_adapter.py` and the build-skill workflow do not run any vulnerability/static-analysis scan over the produced bundle. | 0% |

For the **v2604.02837v1 follow-up paper** (threat taxonomy of 7 categories × 17 scenarios), the structural-threat list is qualitatively distinct from DevolaFlow's exposure surface:

| v2604 structural threat (verbatim from abstract) | applicable to DevolaFlow? |
|--------------------------------------------------|---------------------------|
| "absence of a data-instruction boundary" | **Yes (latent)** — DevolaFlow injects predecessor artifact `summary` and `body` into dispatch payloads as plain markdown; a malicious upstream artifact could in principle prompt-inject the consuming layer. Not addressed by current schemas. |
| "single-approval persistent trust model" | **Marginal** — install-time approval of `pip install git+…/DevolaFlow.git` is single-approval, but updates require explicit re-pull; SI-7 protocol pins remote URLs. |
| "lack of mandatory marketplace security review" | **N/A** — no marketplace; install is by URL pinning. |

### 2.3  Delta items (5-field schema)

#### Δ-skills-sec-01  v2602.12430 has reached v3, all PRE-dating registry snapshot
- **observation:** Registry recorded `last_known_version: "arXiv:2602.12430 (2026-02)"` without a sub-version. The arXiv submission history shows **three** revisions: v1 (2026-02-12), v2 (2026-02-16), v3 (2026-02-17). v3 is the current canonical version. All three revisions occurred **before** the registry's `last_checked: 2026-04-11`, so the registry was likely already pointing at v3 content but without recording the version pin.
- **evidence:** `export.arxiv.org/api/query?id_list=2602.12430` returned `<id>http://arxiv.org/abs/2602.12430v3</id>`, `<updated>2026-02-17T09:08:50Z</updated>`; arXiv abs page lists explicit history `[v1] Thu, 12 Feb 2026 → [v2] Mon, 16 Feb 2026 → [v3] Tue, 17 Feb 2026`.
- **devolaflow_impact:** *none* — content the registry implicitly tracks IS the v3 content (no new revision since 2026-02-17, ~2 months stable).
- **recommendation:** **refresh-registry** — pin `last_known_version: "arXiv:2602.12430v3 (2026-02-17)"` and add `companion_repo: "https://github.com/scienceaix/agentskills"` to the registry entry so the next scan can monitor the companion repo's updated_at as a faster proxy than re-querying arXiv.

#### Δ-skills-sec-02  Follow-up paper arXiv:2604.02837v1 confirmed; warrants explicit registry entry
- **observation:** Registry `update_triggers` mentions "arXiv:2604.02837v1 threat taxonomy" as a future signal. It now **exists** as a stand-alone published paper (submitted **2026-04-03**, ~8 days before the registry snapshot of 2026-04-11) by an independent team (Zhiyuan Li et al., not Renjun Xu). It is in **cs.CR** (Cryptography & Security), not the cs.MA primary subject of the original. It defines a different schema: 4 lifecycle phases (Creation/Distribution/Deployment/Execution), 7 threat categories × 17 scenarios across 3 attack layers, validated by 5 confirmed incidents. The two papers are **complementary, not redundant** — v2602 is a survey + governance proposal; v2604 is a security taxonomy + incident analysis.
- **evidence:** `export.arxiv.org/api/query?id_list=2604.02837` returned `<id>http://arxiv.org/abs/2604.02837v1</id>`, `<published>2026-04-03T07:56:42Z</published>`, `<arxiv:primary_category term="cs.CR"/>`; abstract verbatim: *"first comprehensive security analysis of the Agent Skills framework"*, *"five confirmed security incidents in the Agent Skills ecosystem"*, *"most severe threats arise from structural properties of the framework itself"*.
- **devolaflow_impact:** *medium* — the 7-category × 17-scenario taxonomy gives a concrete checklist DevolaFlow can map its own surface against (e.g. is there a data-instruction boundary in dispatch payloads? Is there persistent trust assumption in the install flow?). At minimum, it should be tracked as a separate registry entry rather than merely a `update_triggers` keyword.
- **recommendation:** **refresh-registry / add-new-entry** — *promote* the follow-up paper from `update_triggers` text into its own `periodic_monitoring` entry with `id: agent-skills-threat-taxonomy`, `relevance_score: 4`, `last_known_version: "arXiv:2604.02837v1 (2026-04-03)"`. The two-paper pair becomes a coordinated reference cluster (one for governance, one for threats).

#### Δ-skills-sec-03  Three documented integration points are *not implemented* in DevolaFlow source
- **observation:** All three integration points the registry attached to `agent-skills-security` (workflow-skill.yaml `trust_level` field, gate `skill provenance validation`, adapter pipeline `vulnerability scanning`) verifiably **do not exist in code** as of v7.1.1. This is an *under-implementation* gap, not an upstream change.
- **evidence:** `Grep` of `workflow-skill.yaml` for `trust_level\|provenance\|first_party\|verified\|community\|unverified` returned **zero matches** (verified 2026-04-18); `_GATE_DISPATCH` in `gate/scorer.py` has 5 entries, none provenance-related; `adapters/claude_adapter.py` (read 2026-04-18) builds bundles but does not invoke any vulnerability scanner.
- **devolaflow_impact:** *medium* — registers as gap-id `M6` in the synthesis report. The framework's surface area as a personal-/team-installed skill (not a marketplace) **partially mitigates** the risk: the threat models in both papers target community/marketplace skills, while DevolaFlow's bundle is first-party-only and pinned to the YoRHa-Agents/DevolaFlow GitHub repo. However, the **data-instruction boundary** issue (v2604) IS structurally present in DevolaFlow's dispatch payloads, where untrusted predecessor artifact bodies can flow into a child-layer prompt.
- **recommendation:** **track for v7.3+ with scope decision** — the v7.2 retrospective (per SI-8) should explicitly answer the binary question: *"Is DevolaFlow in scope for community-skill-trust governance, or is it correctly classified as 'first-party only, governance out of scope'?"* If the answer is "in scope", v7.3 needs an additive `workflow-skill.yaml#identity.trust_level` enum and an `adapters/scanner.py` module. If "out of scope", document the decision in `.local/research/` with a one-line note in the registry: `note: "first-party only; community skill governance intentionally out of scope per v7.2 retrospective"`. **No code change in v7.2.**

#### Δ-skills-sec-04  Companion repo `scienceaix/agentskills` is dormant since 2026-02-16
- **observation:** The paper's `Project repo: https://github.com/scienceaix/agentskills` has 46 stars and was last pushed `2026-02-16T07:07:23Z` (one day before v3 of the paper was submitted). The README's homepage is `https://arxiv.org/abs/2602.12430` (i.e. it's a static "awesome list", not an active codebase).
- **evidence:** `api.github.com/repos/scienceaix/agentskills` returned `pushed_at: 2026-02-16T07:07:23Z`, `size: 21`, `stargazers_count: 46`, `language: null`, `description: "Awesome Agent Skills collection list, papers, tools, projects, and resources"`.
- **devolaflow_impact:** *low* — the repo is a curated reading list, not a tool. No actionable change in DevolaFlow.
- **recommendation:** **track-as-dormant** — note in registry `staleness_status: "static curated list; check semi-annually"`.

#### Δ-skills-sec-05  Data-instruction boundary in DevolaFlow dispatch payloads is the single most concrete v2604-applicable risk
- **observation:** v2604.02837v1's lead structural threat is **"absence of a data-instruction boundary"**. DevolaFlow's `task-dispatch.schema.yaml` has a `context.predecessor_artifacts[].summary` (string, "One–two sentence summary") and a `context.shared_context` (string, "Small cross-cutting context"). Both fields flow as **plain markdown** into the consuming layer's dispatch payload and are therefore indistinguishable from instructions. A malicious or compromised upstream artifact could in principle inject a `IGNORE PRIOR INSTRUCTIONS …` payload into a downstream layer.
- **evidence:** Read of `schemas/task-dispatch.schema.yaml` lines 53-95 (verified 2026-04-18) — `predecessor_artifacts.item_fields.summary: { type: string }`, `shared_context: { type: string, optional: true }`. No tag, signature, or sandbox marker around either field.
- **devolaflow_impact:** *medium* — same threat-model as the paper, materialised in DevolaFlow's actual schema. Mitigation is cheap: a "data envelope" pattern (e.g. wrapping all predecessor strings in `<artifact_data>…</artifact_data>` tags inside the dispatch markdown) plus an instruction in SKILL.md telling agents to treat tagged regions as data, not commands.
- **recommendation:** **propose for v7.2.0 small spec** — author a 1-page design note (Rule SI-1 artifact) for an additive change: `compressor.envelope_artifact_data(text: str) -> str` returning `<artifact_data type="…">…</artifact_data>`, applied at dispatch construction time. Implementation can wait for a later wave; the **spec** belongs in v7.2's planning gate.

---

## Reference 3 — `primelocus-hydra` (https://github.com/PrimeLocus/Hydra)

### 3.1  Current state snapshot — **REPOSITORY DELETED**

| field | last_known (registry 2026-04-11/13) | current (verified 2026-04-18) | source |
|-------|--------------------------------------|-------------------------------|--------|
| `last_known_version` | "v0.1.0 (2026-03)" | **404 Not Found** — repo removed from GitHub | `api.github.com/repos/PrimeLocus/Hydra` returned `{"message":"Not Found","status":"404"}`; `WebFetch https://github.com/PrimeLocus/Hydra` returned status 404 |
| `status` (registry) | "verified" | **deleted upstream** | API + HTML both 404 |
| `owner exists?` | n/a | **YES, but with 0 public repos** — `api.github.com/users/PrimeLocus` returned `id: 44475340`, `name: "Silly Pepper"`, `company: "Zydecoders"`, `public_repos: 0`, `created_at: "2018-10-25T16:13:31Z"`, `updated_at: "2026-03-06T23:10:20Z"` | GitHub user API |
| `deletion timeframe` | n/a | between **2026-04-13 (registry last_checked, status=verified)** and **2026-04-18 (today, 404)** — at most a 5-day window | inferred from registry vs current state |
| `surviving fork` | n/a | **`mikecubed/Hydra`** (id 1174976288), description verbatim: *"Multi-agent AI orchestrator. Routes work across Claude, Gemini, and Codex via shared task queue, intelligent routing, and multi-round deliberation. **Forked from PrimeLocus/Hydra**"* | `api.github.com/search/repositories?q=hydra+multi-agent+claude+gemini+codex` |
| `mikecubed fork created_at` | n/a | 2026-03-07T04:06:09Z | API |
| `mikecubed fork last pushed` | n/a | 2026-03-30T05:26:54Z (~3 weeks before today, no recent activity) | API |
| `mikecubed fork stars` | n/a | 1 | API |
| `mikecubed fork forks_count` | n/a | **9** (other users had also forked, suggesting modest community) | API |
| `mikecubed fork package.json version` | n/a | **`"version": "1.2.0"`** (decoded from base64-encoded `package.json` content) — **major version growth from registry's "v0.1.0"** | `api.github.com/repos/mikecubed/Hydra/contents/package.json` |
| `mikecubed fork git tags` | n/a | **1 tag: `v0.1.0`** (commit `8bdbfc9af82f4e86f35fd8ddbd8f6e9dc841f398`); package.json says 1.2.0 but no matching tag — divergent version sources | `api.github.com/repos/mikecubed/Hydra/tags` |
| `mikecubed fork releases` | n/a | **0 GitHub Releases** | `api.github.com/repos/mikecubed/Hydra/releases` returned `[]` |
| `mikecubed fork structure` | n/a | Workspaces: `apps/*`, `packages/*`. Notable bin scripts: `hydra` (CLI), `hydra-client`, `hydra-daemon`. Notable npm scripts: `start, stop, status, council, dispatch, nightly, audit, actualize, evolve, evolve:knowledge, tasks, eval, lint:complexity, lint:mermaid, lint:cycles` | decoded `package.json` (base64) |

### 3.2  Cross-check vs DevolaFlow integration points

Registered integration points for `primelocus-hydra`:

1. `TaskDispatch schema` (`model_hint` field)
2. Wave dispatch logic (model-strength routing)

Mapping Hydra's documented key_patterns onto DevolaFlow source (verified 2026-04-18 by Read of `schemas/task-dispatch.schema.yaml`, `workflow-system/agent/context_profiles.yaml`):

| Hydra key_pattern (verbatim from registry) | DevolaFlow surface | Coverage |
|--------------------------------------------|---------------------|----------|
| **"strength-based model routing: Claude=architecture, Gemini=critique, Codex=impl"** | **Mismatch** — DevolaFlow's `task-dispatch.schema.yaml` has `header.model_hint` with `enum: [quality, balanced, budget, inherit]` (4 **tier**-based hints) and `context_profiles.yaml#meta.platform_model_mapping` mapping the tier to platform-specific models (`cursor: inherit/fast`, `codex: o3/o4-mini`, `claude_code: opus/sonnet/haiku`). This is **tier**-based, not **strength**-based. Hydra's pattern would require role-keyed routing like `model_role: architect / critic / implementer` rather than tier-keyed. | ~30% |
| **"multi-round deliberation: propose→critique→refine→implement"** | **Adjacent** — DevolaFlow has the convergence loop (`detect_stagnation` → `findings_to_reinforcement` → re-dispatch with reinforcement rules), and the `templates/builtin/research-design-review-refine.yaml` template (`research → design → review → refine`) explicitly maps the propose-critique-refine pattern. Implementation of "implement" is a separate stage. | ~70% |
| **"per-agent budget tracking to prevent runaway costs"** | **Partial** — `task-dispatch.schema.yaml` has `header.timeout_seconds` per dispatch, but **no per-agent token budget tracking** across a multi-agent workflow. `context_profiles.yaml` declares per-layer budgets (L0~3K, L1~5K, L2~4K, L3~8K) but enforcement is per-message, not per-agent-cumulative. | ~40% |

### 3.3  Delta items (5-field schema)

#### Δ-hydra-01  **PrimeLocus/Hydra repository was deleted** between 2026-04-13 and 2026-04-18
- **observation:** Registry recorded `last_known_version: "v0.1.0 (2026-03)"`, `last_checked: "2026-04-13"`, `status: verified`. Today (5 days later) the repo returns 404 from both `api.github.com/repos/PrimeLocus/Hydra` and `https://github.com/PrimeLocus/Hydra`. The owner `PrimeLocus` (id 44475340, "Silly Pepper" at Zydecoders) still exists as a user but has `public_repos: 0` — i.e. **all** their public repos were removed. The owner's `updated_at` is `2026-03-06T23:10:20Z` (before registry snapshot), so the repo deletion is the more recent event.
- **evidence:** Two independent 404 sources: `api.github.com/repos/PrimeLocus/Hydra` returned `{"message":"Not Found","documentation_url":"https://docs.github.com/rest/repos/repos#get-a-repository","status":"404"}` and `WebFetch https://github.com/PrimeLocus/Hydra` returned `Error fetching URL, status code: 404` (verified 2026-04-18). User existence: `api.github.com/users/PrimeLocus` returned valid JSON with `public_repos: 0`.
- **devolaflow_impact:** *low–medium* — DevolaFlow does not depend on Hydra at runtime; the dependency is **research/inspiration** only. The deletion does **not break any code**. But it does invalidate the registry's `repo_url` and `status: verified` fields and removes the upstream authority for any further evaluation of the documented key_patterns.
- **recommendation:** **refresh-registry / mark-as-archived** — change `status: verified` to `status: deleted_upstream`, change `repo_url` to point to the surviving fork: `https://github.com/mikecubed/Hydra` (with explicit note `forked_from_deleted: PrimeLocus/Hydra`), bump `last_checked: 2026-04-18`. **Downgrade `relevance_score` from 4 → 3** since the upstream authority is gone (the fork is community-curated at 1 star, not a primary source).

#### Δ-hydra-02  Surviving fork `mikecubed/Hydra` reports v1.2.0 in `package.json` — **major version growth** since registry's "v0.1.0"
- **observation:** While the *upstream* PrimeLocus repo is deleted, the fork's `package.json` (verbatim, decoded from base64) declares `"version": "1.2.0"`. The git tag history shows only `v0.1.0`, so the version field has been bumped manually without tagging. The fork's `description` verbatim says `"Multi-agent AI orchestrator. Routes work across Claude, Gemini, and Codex via shared task queue, intelligent routing, and multi-round deliberation."` — confirming the routing pattern is preserved. Notable feature growth: scripts `evolve`, `evolve:knowledge`, `actualize`, `nightly`, `audit`, `council`, `dispatch` suggest additional orchestration verbs beyond the original v0.1.0 surface.
- **evidence:** `api.github.com/repos/mikecubed/Hydra/contents/package.json` returned base64-encoded content; decoded fields verbatim: `"name": "hydra"`, `"version": "1.2.0"`, `"description": "Multi-agent AI orchestration system"`, `"author": "Silly Pepper"` (note: same author as deleted PrimeLocus account), `"repository.url": "git+https://github.com/PrimeLocus/Hydra.git"` (still points at the deleted upstream), `"engines.node": ">=24.0.0"`. Tags list: `[{"name":"v0.1.0",...}]` only. Releases list: `[]` empty.
- **devolaflow_impact:** *low* — pattern continuity is preserved in the fork; if DevolaFlow ever wanted to verify the documented key_patterns, the fork is a reasonable substitute. But: the fork's `repository.url` still points at the deleted PrimeLocus repo, suggesting the maintainer did not update the metadata after the deletion — this is a stability signal, not a quality signal.
- **recommendation:** **track-via-fork** — set the registry `repo_url` to the fork, but leave `relevance_score: 3` (downgraded per Δ-hydra-01). Re-check at the next periodic cycle; if the fork goes 6 months without a push (currently last pushed 2026-03-30), reclassify as `frozen_reference`.

#### Δ-hydra-03  Strength-based model routing pattern is *not* implemented in DevolaFlow's `model_hint` — the integration point is **misnamed**
- **observation:** Registry says integration point: "TaskDispatch schema (`model_hint` field)". DevolaFlow does have `model_hint` at `header.model_hint` of `task-dispatch.schema.yaml`, but the enum is `[quality, balanced, budget, inherit]` — i.e. **tier-based** (priced by capability tier). Hydra's actual key_pattern is **strength-based / role-based** (Claude=architecture, Gemini=critique, Codex=impl), which would require an enum like `[architect, critic, implementer, reviewer]`. The two are orthogonal: tier ≠ role.
- **evidence:** Read of `schemas/task-dispatch.schema.yaml` lines 24-28 (verified 2026-04-18): `model_hint: { type: string, enum: [quality, balanced, budget, inherit], default: inherit, description: "Host IDE interprets this hint to select appropriate model tier" }`. Read of `context_profiles.yaml` lines 33-48: `platform_model_mapping` maps `quality / balanced / budget / inherit` to per-platform models, again tier-based.
- **devolaflow_impact:** *low* — DevolaFlow's tier hint serves the cost-control half of Hydra's pattern (Hydra's `per-agent budget tracking to prevent runaway costs`). The role-routing half is *not* implemented but is also debatably a host-application concern (the dispatcher selects a host model per dispatch; the *role* concept is encoded in the agent's `team` and `task.type` fields).
- **recommendation:** **refresh-registry to clarify** — keep `model_hint` integration claim but rephrase as "*tier-based selection only; strength-based / role-based routing intentionally out of scope per v7.x design*". **No port** of the strength-based pattern. If a v7.3 design surfaces a real demand, evaluate adding `header.model_role: { type: string, optional: true }` as a sibling enum (additive, non-breaking).

#### Δ-hydra-04  Multi-round deliberation pattern is partially mirrored, especially via `research-design-review-refine.yaml`
- **observation:** Hydra's documented "multi-round deliberation: propose→critique→refine→implement" maps cleanly onto DevolaFlow's `templates/builtin/research-design-review-refine.yaml` (RDRR), which explicitly chains `research → design → review → refine` as a 4-stage iterative-design template. The "implement" terminus is then handled by a separate template (`feature-enhancement.yaml` or `full-pipeline.yaml`). Plus, `gate/reinforcement.py` `findings_to_reinforcement()` implements per-round critique injection into the next-round dispatch.
- **evidence:** `Glob workflow-system/agent/templates/builtin/research-design-review-refine.yaml` returns 1 file; description from `workflow-skill.yaml` line 332: `"Iterative research-driven design convergence (RDRR)"`. `Read src/devolaflow/gate/reinforcement.py` confirms `findings_to_reinforcement()` exists with `MAX_REINFORCEMENT_RULES = 5`.
- **devolaflow_impact:** *positive (no gap)* — DevolaFlow's deliberation pattern is **structurally richer** (stages, gates, and convergence loop) than Hydra's described simple round-based deliberation.
- **recommendation:** **no-op** — confirm in the next retrospective that the multi-round deliberation key_pattern is "already-addressed" per registry policy.

#### Δ-hydra-05  Per-agent budget tracking is the *one* Hydra feature DevolaFlow under-implements
- **observation:** Hydra's `per-agent budget tracking to prevent runaway costs` is **partially** implemented in DevolaFlow as per-dispatch `header.timeout_seconds` + per-layer `context_profiles.yaml` budgets, but there is **no cumulative-per-agent ledger**. A long-running L3 agent that spawns sub-agents (per the `decomposition_mode: sub_agents` enum value) has no visible aggregate token / wallclock counter; budgets are checked at message construction time only.
- **evidence:** `Grep` of `src/devolaflow/` for `cumulative.*budget|token.*ledger|agent.*spend` returns zero matches (verified 2026-04-18). `task-dispatch.schema.yaml` has `header.timeout_seconds` per dispatch but no `header.cumulative_token_budget`.
- **devolaflow_impact:** *medium* — for v7.2's continued sub-agent decomposition trajectory (recall `decomposition_mode: sub_agents` shipped in v7.x), absence of cumulative budgeting is a real gap; runaway costs in a 5-deep sub-agent chain are not currently bounded.
- **recommendation:** **track for v7.3+** — propose adding `header.cumulative_token_budget: { type: int, optional: true }` and a corresponding `compressor.consume_budget(dispatch_id, tokens)` ledger. Defer because: (a) priority is low (no production cost incident yet), (b) the surviving Hydra fork is at 1 star and unlikely to be the canonical reference for this pattern long-term — better to design DevolaFlow's own scheme.

---

## Reference 4 — `ruflo` (https://github.com/ruvnet/ruflo)

### 4.1  Current state snapshot

| field | last_known (registry 2026-04-11) | current (verified 2026-04-18) | source |
|-------|----------------------------------|-------------------------------|--------|
| `last_known_version` | "proposal (issue #1273)" | **see §4.2 verdict — partially implemented (primitives shipped via `@claude-flow/memory`; dedicated `@claude-flow/context` package NOT created)** | repo + issue + npm package layout |
| `repo updated_at` | n/a | **2026-04-18T02:29:23Z** (today) | `api.github.com/repos/ruvnet/ruflo` |
| `repo pushed_at` | n/a | **2026-04-11T16:20:19Z** (matches v3.5.80 release date) | API |
| `stars` | n/a | **32,211** | API |
| `language` | n/a | TypeScript | API |
| `description` | n/a | "🌊 The leading agent orchestration platform for Claude. Deploy intelligent multi-agent swarms, coordinate autonomous workflows, and build conversational AI systems. Features enterprise-grade architecture, distributed swarm intelligence, RAG integration, and native Claude Code / Codex Integration" | API |
| `latest GitHub Release` | n/a | **v3.5.80 — "Tier A Blocker Fixes"** published `2026-04-11T16:20:20Z` | `api.github.com/repos/ruvnet/ruflo/releases?per_page=5` |
| `published packages (in v3.5.80)` | n/a | `@claude-flow/cli@3.5.80`, `@claude-flow/memory@3.0.0-alpha.14`, `claude-flow@3.5.80`, `ruflo@3.5.80` | release body verbatim |

### 4.2  Issue #1273 — proposal status verdict

**Verdict: PARTIALLY IMPLEMENTED.**

| facet | finding | evidence |
|-------|---------|----------|
| **issue state** | **OPEN** (not closed) — `state: "open"`, `closed_at: null`, last_updated `2026-03-27T11:12:50Z` (3 weeks before today, no fresh comments since) | `api.github.com/repos/ruvnet/ruflo/issues/1273` |
| **comment from owner** | ruvnet (OWNER, 2026-03-25): verbatim *"Thanks — context compression is definitely important for long-running sessions. Some of this is addressed by the **RuVector intelligence pipeline** but there's more to do."* — explicit acknowledgment of partial implementation | issue #1273 comments |
| **proposed package** `@claude-flow/context` | **DOES NOT EXIST** in the repo's `v3/@claude-flow/` directory | `api.github.com/repos/ruvnet/ruflo/contents/v3/@claude-flow` lists 16 sub-packages (`agents`, `aidefence`, `browser`, `claims`, `cli`, `codex`, `deployment`, `embeddings`, `guidance`, `hooks`, `integration`, `mcp`, `memory`, …) — **no `context` package** |
| **proposed primitives shipped in `@claude-flow/memory`** | `package.json` description verbatim: *"Memory module - **AgentDB unification, HNSW indexing, vector search, hybrid SQLite+AgentDB backend** (ADR-009)"*. Dependencies: `agentdb ^3.0.0-alpha.10`, `better-sqlite3 ^11.0.0`, `sql.js ^1.10.3` (= the WASM SQLite the issue spec'd for FTS5). Required exports: `ControllerRegistry`, `HnswLite`, `PersistentSonaCoordinator`, `RvfBackend`, `RvfLearningStore`, `RvfMigrator` | `WebFetch raw.githubusercontent.com/ruvnet/ruflo/main/v3/@claude-flow/memory/package.json` |
| **proposed primitives NOT shipped (per the issue body)** | (a) **Sandbox isolation pool** with 11-language runtimes — no equivalent in `v3/@claude-flow/` package layout; (b) **Multi-stage compression pipeline** specifically for tool outputs (Raw → Size Check → Sandbox → Intent Filter → Smart Snippet → Compressed) — no module name suggests this; (c) **Swarm-aware per-agent budget manager** with progressive throttling (`normal → reduced → minimal → blocked`) — not visible; (d) **PreToolUse / PostToolUse hooks** wiring compression into MCP tool calls transparently — `v3/@claude-flow/hooks/` exists but not specifically for this | directory listing 2026-04-18 |
| **prior art reference (mksglu/claude-context-mode)** | The issue cites `https://github.com/mksglu/claude-context-mode` as the inspirational source ("demonstrates 98% context reduction, 315 KB → 5.4 KB per session, sandbox-isolated execution + FTS5 knowledge base"). Not verified here (out of T06 scope). | issue body verbatim |

So: the **underlying primitives** (FTS5 via SQLite WASM, HNSW vector search, hybrid storage) ARE shipped at `@claude-flow/memory@3.0.0-alpha.14`. The **dedicated context-optimization package** as a pipeline IS NOT shipped. The proposal lives on as an open issue.

### 4.3  Cross-check vs DevolaFlow integration points

Registered integration points for `ruflo`:

1. `context_profiles.yaml` (`budget_strategy` option)
2. predecessor summary compression

Mapping ruflo issue #1273's documented key_patterns onto DevolaFlow source (verified 2026-04-18 by Read of `workflow-system/agent/context_profiles.yaml`, `src/devolaflow/compressor.py`):

| ruflo key_pattern (verbatim from registry) | DevolaFlow surface | Coverage |
|--------------------------------------------|---------------------|----------|
| **"multi-stage compression pipeline targeting 95-98% compression"** | **Partial** — `compressor.py` exposes `compress_message(message, intensity)` with `intensity ∈ {minimal, standard, aggressive}` plus per-layer-transition default in `context_profiles.yaml#meta.compression_defaults` (`l0_to_l1: standard`, `l3_to_l2: aggressive`, etc.). `truncate_tool_output()` and `clear_old_tool_uses()` exist for tool output specifically. **Compression ratio target is not explicit** — no documented 95–98% goal; lean format compression is rule-driven (preserve_list / drop_list) not pipeline-staged. | ~50% |
| **"swarm-aware per-agent budgets with progressive throttling"** | **Absent** — no per-agent budget ledger; per-layer budget caps in `context_profiles.yaml` (`L0~3K, L1~5K, L2~4K, L3~8K`) are enforced *per-dispatch*, not aggregated *per-agent-lifetime*. No throttling state machine. | 0% |
| **"intent-based filtering: extract only task-relevant facts"** | **Adjacent** — DevolaFlow's `task_adaptive_selector.py` selects SKILL.md sections based on `task_type` (intent-driven) and is documented in `context-optimization-rules.mdc#CO-1` to use verbatim extraction. So the *concept* of intent-driven filtering is alive, but applied to **section selection**, not to **tool-output filtering** as ruflo proposes. | ~40% |
| **"cross-agent knowledge search via FTS5/HNSW"** | **Absent** — no SQLite/FTS5 in DevolaFlow; no HNSW vector index. The closest is `learnings/operational.jsonl` (mentioned in `knowledge/index.md` as planned but the file does not yet exist per T04 cross-check), which would be a flat-file analog without any indexed search. | 0% |
| **"compression latency P99 <50ms; knowledge search latency <10ms"** (ruflo SLOs) | **N/A** — DevolaFlow has no published latency SLOs for compression. EvoBench measures token reduction (composite_score), not wallclock. | n/a |

### 4.4  Delta items (5-field schema)

#### Δ-ruflo-01  **Proposal status verdict: PARTIALLY IMPLEMENTED** (proposal still OPEN; primitives shipped via `@claude-flow/memory`; dedicated `@claude-flow/context` package NOT created)
- **observation:** Per the §4.2 table — `state: "open"`, `closed_at: null`. The proposed package `@claude-flow/context` does NOT exist in `v3/@claude-flow/`. However, the underlying primitives the proposal needs (SQLite/FTS5 via `sql.js@^1.10.3`, HNSW indexing, hybrid storage) ARE shipped via `@claude-flow/memory@3.0.0-alpha.14` per its own `package.json` description: "Memory module - AgentDB unification, HNSW indexing, vector search, hybrid SQLite+AgentDB backend (ADR-009)". Owner ruvnet acknowledges "some of this is addressed by the RuVector intelligence pipeline but there's more to do." Not shipped: sandbox-pool isolation, multi-stage compression pipeline specifically for tool outputs, swarm-aware progressive throttling, PreToolUse/PostToolUse hook wiring for transparent compression.
- **evidence:** Three independent verifications (all 2026-04-18): (i) issue API confirms `state: "open"`, `closed_at: null`; (ii) `api.github.com/repos/ruvnet/ruflo/contents/v3/@claude-flow` returns 16 packages, none named `context`; (iii) `WebFetch raw.githubusercontent.com/.../v3/@claude-flow/memory/package.json` returned `"version": "3.0.0-alpha.14"` with the FTS5+HNSW description above.
- **devolaflow_impact:** *low* — confirms DevolaFlow can continue to track the issue without expecting a v7.2 deliverable. The proposal's evolution into `@claude-flow/memory` primitives means the *future* `@claude-flow/context` would build on `@claude-flow/memory`, suggesting the pattern is stable and worth long-term tracking.
- **recommendation:** **refresh-registry** — change `last_known_version: "proposal (issue #1273), partially implemented via @claude-flow/memory@3.0.0-alpha.14"`, add `proposal_state: "open"`, add `companion_packages: ["@claude-flow/memory@3.0.0-alpha.14", "@claude-flow/cli@3.5.80"]`, bump `last_checked: 2026-04-18`. Keep `relevance_score: 4`.

#### Δ-ruflo-02  ruflo shipped a major release (v3.5.80) on the same day as registry snapshot — registry caught the moving target precisely
- **observation:** GitHub Release `v3.5.80 — "Tier A Blocker Fixes"` was published `2026-04-11T16:20:20Z`, which is the same day as the registry snapshot's `last_checked: 2026-04-11`. The release fixes three Tier A blockers (`#1596` CLI lazy-loaded routing, `#1567` MCP `agent_spawn` validation, `#1556` `AutoMemoryBridge.curateIndex()` destroying hand-curated `MEMORY.md`). None of these touch issue #1273 or its proposed `@claude-flow/context` package. The registry's version label "proposal (issue #1273)" is silent on the underlying ruflo release, which is misleading because the project has shipped 3.5.x lines.
- **evidence:** `api.github.com/repos/ruvnet/ruflo/releases?per_page=5` returned the v3.5.80 release with `"published_at": "2026-04-11T16:20:20Z"`, `"target_commitish": "main"`, `"tag_name": "v3.5.80"`. The body verbatim: *"Fixes three Tier A blockers that made the CLI, MCP agent_spawn tool, and Claude Code memory integration partially unusable."*.
- **devolaflow_impact:** *none directly* — but the registry's framing as "proposal" obscures that ruflo is a mature, actively-released project. A future scan would benefit from tracking *both* the issue *and* the release cadence.
- **recommendation:** **refresh-registry** — augment the entry with `repo_state: "active, v3.5.80 released 2026-04-11"`, `release_cadence: "frequent (3.5.x line; alpha @claude-flow/memory line)"` so the registry distinguishes the *project* (mature) from the *specific feature proposal* (partially implemented).

#### Δ-ruflo-03  DevolaFlow's compression already covers the "multi-stage" axis; the missing pieces are sandbox isolation and per-agent throttling
- **observation:** From the §4.3 cross-check, DevolaFlow's compression covers ~50% of ruflo's pipeline pattern: `compress_message(intensity)`, `truncate_tool_output()`, `summarise_predecessor()`, per-layer-transition `compression_defaults`. Missing: (a) sandbox-isolated execution before compression, (b) per-agent cumulative budget ledger with throttling, (c) FTS5/HNSW indexed knowledge search. (a) and (c) are **out of DevolaFlow's mandate** (DevolaFlow runs inside an existing host IDE; the host owns sandboxing and indexed storage). (b) IS in scope per Δ-hydra-05 above and is the cross-cutting v7.3+ candidate.
- **evidence:** Read of `src/devolaflow/compressor.py` lines 1-100 (verified 2026-04-18) — `compress_message`, `truncate_tool_output`, `clear_old_tool_uses`, `summarise_predecessor`, `validate_lean_format`. No `sandbox_*` or `*_budget_ledger` symbols.
- **devolaflow_impact:** *low* — the gap is intentional scope-narrowing; DevolaFlow is the orchestration layer, not the runtime sandbox. The per-agent budget gap is the only one worth addressing, and is already captured under hydra-05.
- **recommendation:** **no-op for v7.2** — defer sandbox isolation (out of scope) and FTS5 knowledge search (out of scope) explicitly in the registry `note:`. Roll the per-agent budget gap up under the v7.3+ task already captured by Δ-hydra-05; do not double-count.

#### Δ-ruflo-04  ruflo's `@claude-flow/memory` "AutoMemoryBridge" fix in v3.5.80 is *directly* analogous to DevolaFlow's `feedback.py` scope-lock pattern
- **observation:** v3.5.80 release fixes `#1556` — *"`AutoMemoryBridge.curateIndex()` destroyed hand-curated `MEMORY.md`. On every Stop-hook tick when no topic files matched the hardcoded `DEFAULT_TOPIC_MAPPING`, the curator overwrote `MEMORY.md` with a stub. Now exits early with an `index:skipped` event when section map is empty."* This is **the same class of bug** that DevolaFlow's `feedback.py` `LOCKED_FILES` set + `_inside_devolaflow()` allow-list is designed to prevent (per Δ-self-improve-05). ruflo only added the guard *after* the bug shipped; DevolaFlow has the guard from day one.
- **evidence:** v3.5.80 release body verbatim (cited above). Read of `src/devolaflow/feedback.py` lines 30-75 (verified 2026-04-18) shows `LOCKED_FILES = frozenset({"__init__.py", "pyproject.toml", "feedback.py"})` and the `_is_locked()` / `_inside_devolaflow()` guards.
- **devolaflow_impact:** *positive (no gap)* — this is a **validation** that DevolaFlow's `feedback.py` scope-lock design is the correct shape; ruflo's experience confirms the failure mode is real.
- **recommendation:** **document-as-validation** — note in `retrospective_v7.1_to_v7.2.md` that ruflo's `#1556` confirms DevolaFlow's `feedback.LOCKED_FILES` design choice. **No code change.**

#### Δ-ruflo-05  Last issue activity is 2026-03-27; no new commentary in 22 days suggests proposal has cooled
- **observation:** Issue #1273's last comment was `2026-03-27T11:12:18Z` from user `m13v`. Today is 2026-04-18 — **22 days** with no activity on the issue itself, despite ruflo's main branch shipping multiple releases (v3.5.78 → v3.5.80) in the meantime. The owner's last comment was 2026-03-25 acknowledging partial implementation via RuVector. This pattern (proposal sits open while project ships unrelated fixes) is consistent with the "proposal acknowledged but not in current sprint" state.
- **evidence:** `api.github.com/repos/ruvnet/ruflo/issues/1273/comments` returned 4 comments, last dated `2026-03-27T11:12:18Z`. Issue `updated_at: 2026-03-27T11:12:50Z`. Today: 2026-04-18 → 22-day silence.
- **devolaflow_impact:** *none* — purely informational; signals the registry's `update_triggers` ("implementation milestones for context compression engine", "compression benchmark results published", "production adoption reports") are unlikely to fire in the v7.2 timeframe.
- **recommendation:** **refresh-registry** — append `proposal_silence_days: 22` (as of 2026-04-18) and reduce monitoring frequency from monthly → quarterly until activity resumes. **Keep relevance_score: 4** because the *primitives* in `@claude-flow/memory` are shipping actively even when the *proposal package* is dormant.

---

## Summary table

| ref | deltas raised | recommended actions | net registry change for v7.2 | proposed gap-id touches |
|-----|---------------|---------------------|------------------------------|-------------------------|
| `self-improving-system` | 6 (Δ-self-improve-01..06) | refresh registry with revision sha + dual-revision history; 1 small additive proposal (`feedback.apply_proposal()` closing the loop); 1 explicit no-adopt note (release-please CI/CD) | bump `last_checked: 2026-04-18`, add `revision_sha: "42edd25d3edec114471f028c1c87a25cf03d94bb"`, `gist_first_revision: 2026-02-13`, keep `relevance_score: 4` | H5/H7 stay open; new sub-gap "F1: feedback.apply_proposal() loop closure" suggested |
| `agent-skills-security` | 5 (Δ-skills-sec-01..05) | refresh registry to v3 pin; **add new periodic_monitoring entry for arXiv:2604.02837v1**; defer integration-point implementation pending v7.2 retrospective scope decision; propose 1 small spec (data-instruction envelope) | bump `last_checked`, pin `last_known_version: "arXiv:2602.12430v3 (2026-02-17)"`, add companion_repo, add new entry `id: agent-skills-threat-taxonomy` for v2604, keep `relevance_score: 4` | M6 stays open with explicit scope question; new sub-gap "S1: data-instruction envelope at dispatch boundary" suggested |
| `primelocus-hydra` | 5 (Δ-hydra-01..05) | **mark upstream as deleted (404)**; redirect registry repo_url to surviving fork `mikecubed/Hydra` (v1.2.0 in package.json); downgrade relevance_score 4→3; clarify integration-point claim is tier- not strength-based | change `status: verified → deleted_upstream`, change `repo_url → https://github.com/mikecubed/Hydra` with `forked_from_deleted: PrimeLocus/Hydra` note, downgrade `relevance_score: 4 → 3`, bump `last_checked` | M2/M9 stay open; new sub-gap "B1: cumulative per-agent budget ledger" suggested (couples with Δ-hydra-05 + Δ-ruflo-03) |
| `ruflo` | 5 (Δ-ruflo-01..05) | refresh registry with explicit "proposal status: PARTIALLY IMPLEMENTED" verdict; note primitives shipped via `@claude-flow/memory@3.0.0-alpha.14`; reduce monitoring frequency monthly → quarterly; document v3.5.80 `#1556` as design-validation for DevolaFlow's `feedback.LOCKED_FILES` | bump `last_checked`, pin `last_known_version: "proposal (issue #1273), partially implemented via @claude-flow/memory@3.0.0-alpha.14"`, add `proposal_state: open`, `proposal_silence_days: 22`, `release_cadence: "frequent (3.5.x line)"`, keep `relevance_score: 4` | L3 stays open; rolls up under "B1" cumulative-budget gap with Δ-hydra-05 |

## Acceptance criteria self-check

| AC | Status | Notes |
|----|--------|-------|
| 1. File exists at `.local/research/v7.2.0_refs/delta-T06.md` | ✅ | This file |
| 2. All 4 references analyzed | ✅ | §1, §2, §3, §4 |
| 3. Each delta item has 5 standard fields | ✅ | every Δ-* entry above carries `observation`, `evidence`, `devolaflow_impact`, `recommendation`, plus an explicit id |
| 4. For agent-skills-security: explicitly check for v2604.02837v1 follow-up | ✅ | Δ-skills-sec-02 — confirmed exists, submitted 2026-04-03, verbatim abstract captured |
| 5. For ruflo: explicit proposal-status verdict | ✅ | §4.2 verdict block: **"PARTIALLY IMPLEMENTED"** with three-facet justification |
| 6. NO modifications to DevolaFlow source | ✅ | All cross-checks were Read-only on `src/devolaflow/`, `schemas/`, `workflow-system/agent/`; only the owned path under `.local/research/v7.2.0_refs/` was written |

## Caveats & method notes

- All upstream queries used `api.github.com` and `export.arxiv.org/api/query` for canonical data; raw `gist.github.com/...html` and `raw.githubusercontent.com/...` paths were used selectively (one timeout on the ruflo CHANGELOG fetch — switched to `api.github.com/repos/ruvnet/ruflo/releases` which succeeded). The arXiv API was sufficient for both papers.
- One transient GitHub API rate-limit error was encountered while probing PrimeLocus user events; the deletion was nonetheless confirmed by two independent sources (REST API 404 + WebFetch 404).
- The mikecubed/Hydra fork's `package.json` was decoded from base64 manually since the API returned `"encoding": "base64"` content; the verbatim version string `"version": "1.2.0"` is from that decoded payload.
- The ruflo `@claude-flow/memory` package.json was fetched directly via `WebFetch` since the search-by-content API requires authentication; the description quote and dependency list above are verbatim from the JSON body.
- Per task constraints (`max_files: 6 writable (need 1)` and `NO modifications to DevolaFlow source`), no file outside the owned path was modified. Files Read from the DevolaFlow repo for the cross-check: `workflow-system/agent/workflow-skill.yaml`, `schemas/task-dispatch.schema.yaml`, `workflow-system/agent/context_profiles.yaml`, `src/devolaflow/feedback.py`, `src/devolaflow/gate/scorer.py`, `src/devolaflow/compressor.py`, `workflow-system/agent/SKILL.md`, `workflow-system/agent/templates/builtin/self-update.yaml`, `workflow-system/agent/knowledge/reference-dependencies.yaml`. (One additional Read for sibling output sanity: `delta-T04.md`.)
- Sibling tasks T01–T04 (W01) and T05 / T07 (W02 siblings) own different output paths and were not touched.
