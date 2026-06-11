# DevolaFlow Product Design Review — v14.2.0 → v15.0.0 Ladder Input

* **Date:** 2026-06-12
* **Reviewer:** L3 research agent (v14.2.0 T2)
* **Baseline:** v14.1.0 (`src/devolaflow/__init__.py` __version__; SKILL.md frontmatter `version: "14.1.0"`)
* **Scope:** the PRODUCT operators consume — SKILL.md (492 lines), 24 references, 4 examples,
  23 workflow templates, dispatch/report YAML protocol, 6 runtime plugins, `devola-init` CLI.
* **North star under test:** "在单独任务上做到极致" — quality of the SINGLE L3 task deliverable.
* **Method:** direct file reads; all evidence verbatim per C-3. Counts in the task brief were
  re-verified, not trusted (two were wrong: legacy templates = 16 not 14; examples = 4 not 3).

---

## §1 North-star alignment audit

Classification key: **DIRECT** = directly improves single-task output quality ·
**ENABLING** = improves inputs/feedback to the task · **CEREMONY** = orchestration ritual with no
measurable path to task quality · **GOVERNANCE** = repo-self-management, not product.

### 1.1 Classification table — every SKILL.md major section (v14.1.0, 492 lines)

| # | SKILL.md section (lines) | Class | Rationale |
|---|---|---|---|
| 1 | Frontmatter + triggers (1–30) | ENABLING | Activation surface; routes operator intent into the skill |
| 2 | Version & Update + Session Banner Contract + install note (32–51) | CEREMONY | ~20 lines of banner emoji contract, version-literal repetition, install caveats; zero path to task output quality |
| 3 | Workspace Engagement (53–68) | ENABLING | Feeds accumulated repo state (feedbacks, specs, cases) into dispatch context |
| 4 | Quick Action Decision (70–79) | ENABLING | Right-sizes ceremony to complexity; protects small tasks from over-orchestration |
| 5 | Mode Awareness + PLAN/AGENT/GRILL (81–123) | ENABLING | Plan/grill modes sharpen task inputs (AC, scope, vocabulary) before dispatch |
| 6 | Quick Start — Workflow Selection (125–155, 25 rows) | ENABLING/CEREMONY | Intent routing is enabling; 16 of the routed templates are `(legacy)` never-invoked (see §2) |
| 7 | Repo-Init Pre-Dispatch Contract + working-tree sanity (156–175) | GOVERNANCE | Single-workflow detail incl. a this-repo anecdote ("pre-existing 4787-line CHANGELOG.md truncation") baked into every dispatcher prompt |
| 8 | Selection heuristics (177–184) | ENABLING | Confidence-tiered selection |
| 9 | 4-Layer Agent Hierarchy (186–201) | ENABLING | Isolation + sizing limits protect task-context quality; cascade ritual itself adds no output verification |
| 10 | Rationalization Prevention (203–214) | CEREMONY | 12 lines defending the dispatch ritual ("Speed is not the goal"), not the artifact |
| 11 | Wave Coordination Modes + Gen-Verify loop (216–233) | DIRECT | `generator_verifier` is the product's main output-quality loop (wave-level) |
| 12 | Stage Primitives Index (235–283) | CEREMONY | 48 lines duplicating `references/meta-framework.md` §1–2 tables in Tier-1 |
| 13 | Gate Mechanism + Reinforcement (285–304) | DIRECT | Composite scoring + reinforcement = stage-level output verification & feedback |
| 14 | AgentTeam Quick Reference (306–316) | ENABLING | Duplicates `references/team-roles.md`; demote candidate |
| 15 | Context Isolation (318–335) | ENABLING | Input-side discipline (the framework's strongest axis) |
| 16 | Subagent Hang Prevention (337–350) | ENABLING | Task reliability (timeouts, forbidden patterns) |
| 17 | Dispatch & Report Protocol (352–384) | ENABLING | Input contract; report side under-specified (see §4) |
| 18 | Lifecycle Hooks (386–396) | CEREMONY (today) | Advertises write/stop-time enforcement that has no production caller (F-P1-1) |
| 19 | Repo Mode Detection (398–407) | ENABLING | Niche; demote candidate |
| 20 | Reference Navigation Guide (409–455) | ENABLING | The 24-row Tier-2 map; gaps in Tier-3 (F-P3-2) |
| 21 | Template Quick-Reference (457–485) | CEREMONY | 29 lines; 16/23 rows `(legacy)`; third copy of template info (F-P3-5) |
| 22 | Task Quality Score stub (487–489) | GOVERNANCE/ENABLING | Scores the OPERATOR REQUEST, not the L3 artifact (F-P1-2) |
| 23 | Operational Learnings (491–492) | ENABLING | Cross-session feedback loop; dense API prose in Tier-1 |

**Aggregate:** DIRECT ≈ 2 sections (~37 lines, ~7.5%); CEREMONY ≈ 4 sections (~109 lines, ~22%);
GOVERNANCE ≈ 2 sections (~23 lines); rest ENABLING. The product spends ~3× more always-loaded
prompt on ceremony than on direct output-quality mechanisms.

### 1.2 Findings

**F-P1-1 (critical) — L3 output-closure hooks exist but are unwired; SKILL.md advertises them as live.**
Evidence — `src/devolaflow/lifecycle/__init__.py` docstring (lines 24–27):
> "Hooks are intentionally NOT wired into existing dispatch / write / status-report flows by
> P-05 — that integration is deferred to a future patch (likely v7.6.x) and lives outside this
> module's scope."
The only production caller of `run_hooks` is `src/devolaflow/feedback_emit.py::_fire_hook_chain`,
whose `_HOOK_CHAIN = (pre_dispatch, post_dispatch, pre_handoff, pre_plugin_invocation)` — all
dispatch-emission-time (input-side). `check_file_write`/`file_write` (S-8 ownership) and
`post_task_complete`/`task_stop` (`test_on_complete`) have **zero production call sites**.
Yet SKILL.md §"Lifecycle Hooks" (lines 390–394) presents a table — "`check_file_ownership` |
File write | File ∈ `owned_files` | Reject + log (P1)" / "`test_on_complete` | Task stop | Tests
pass, lint clean | Auto-retry ≤ P4 limit" — implying write/stop-time enforcement.
**Impact:** the north star's OUTPUT side is prompt-only; "deferred to v7.6.x" has now survived
seven major versions (v8→v14). Operators reading SKILL.md believe a safety net exists.
**Recommendation:** v15.0.0 ADR (see §7 ADR-2): either ship an execution-side adapter that fires
the two hooks (e.g. a documented L3 protocol step + verifier), or rewrite the SKILL table to
label them "library-only, caller-supplied" and stop implying runtime enforcement.

**F-P1-2 (major) — the product's only quality rubric scores the operator's request, not the L3 artifact.**
Evidence — `references/task-quality-score.md` §Scoring rules: "**Never score subagent outputs** …
This rubric scores ONLY the user's original request, never the dispatched agents' work." Its 4
dimensions are Clarity/Scope/Success Criteria/Context — all request-side. SKILL.md §"Reporting
completion": "Subagent reports DO NOT include `quality_score`".
**Impact:** for a framework whose declared purpose is single-task deliverable excellence, there
is no rubric anywhere in the product that scores the deliverable itself (gate composite scores a
STAGE, from findings counts, not an artifact rubric).
**Recommendation:** add an artifact-quality rubric (per-artifact, evidence-backed: AC verdicts,
test/coverage deltas, scope adherence) — landing with the §4 report-schema extension; ADR-3.

**F-P1-3 (major) — ~22% of the Tier-1 budget is ceremony/duplication.**
Evidence: §1.1 rows 2, 10, 12, 21 total ≈ 109 lines: Session Banner Contract (incl. 3× literal
"`🌸 DevolaFlow v12.3.0`" examples), Rationalization Prevention, Stage Primitives Index
(duplicates `meta-framework.md`), Template Quick-Reference (triplicate, 70% legacy rows).
**Impact:** every dispatch context pays ~109 lines that cannot affect task output, while the file
sits at 492/500 (F-P3-1) blocking output-side additions.
**Recommendation:** demote rows 12, 21 to references; compress row 2 to ≤6 lines; keep row 10 as
a 4-row table inside §AGENT MODE. Frees ~80 lines for output-closure content.

**F-P1-4 (minor) — repo-self-governance anecdotes leak into the product prompt.**
Evidence — SKILL.md line 175: "The v12.2.0 cycle is the canonical example — PV-01 surfaced a
pre-existing 4787-line CHANGELOG.md truncation + 1786-line test_no_ghost_features.py truncation…"
and line 51's I-001/I-004 issue-tracker note. These are DevolaFlow-repo history, not operator
product contract.
**Recommendation:** move to `references/troubleshooting.md` / CHANGELOG.

**F-P1-5 (info) — DIRECT inventory is thin and never intra-task.**
The complete list of DIRECT output-quality features: gate mechanism (stage granularity),
gen-verify wave mode (wave granularity, "Quality-critical + shared context" only), and
`impeccable detect` exit-code gate (web-design workflow only). There is no general intra-task
gen→verify protocol an L3 runs on its own artifact before reporting. Confirms the prior diagnosis.
**Recommendation:** v14.3.0+ — specify an L3 self-verification step (run `verification_cmd` from
`acceptance_criteria_v2`, attach verdicts to the report) — pairs with F-P4-6.

---

## §2 Template lineage

Verified counts: SKILL.md §"Template Quick-Reference" lists **23** templates, of which **16**
carry `(legacy)` (not 14 as briefed): research-only, design-only, hotfix, refactoring, spike-poc,
documentation-only, security-audit, feature-enhancement, full-pipeline,
research-design-review-refine, demo-showcase, performance-optimization, dependency-setup,
onboarding, product-verification, entropy-cleanup. `templates/registry.yaml` registers 23
(`grep -c "  - name:"` = 23, incl. `web-design`). `templates/builtin/` holds 23 yamls.

**F-P2-1 (major) — the deprecation contract has lapsed by three major versions.**
Evidence — `templates/builtin/hotfix.yaml` line 1: "`# DEPRECATED in v11.0.0; will be removed in
v12.0.0`" (same header on the 16 legacy yamls per D-A-2 Phase A). v12.0.0, v13.0.0, v14.0.0 and
v14.1.0 have shipped; all 16 remain registered, listed in SKILL.md, and routed by the selection
table. `.local/research/v11.0.0_patches/D-A-2.md` §1: utilization "**6 templates** [USED] …
REGISTERED-BUT-UNUSED … **16 templates** … **27% utilization rate**"; §8: "Phase B …
schema bump v1.0 → v2.0 … a future cycle's SI-1 work". Deferral note in SKILL.md line 459:
"Phase B compose-not-define collapse deferred to v12.0+".
**Impact:** operators see a 23-row registry where 70% is dead weight with a broken removal
promise; selection-time and maintenance cost (4 surfaces per template) persist.
**Recommendation:** v15.0.0 executes Phase B (proposal in §2.1 below); ADR-1.

**F-P2-2 (major) — four-surface stage-count drift proves the per-template ledger is unmaintainable.**
Evidence (stage counts: on-disk yaml vs SKILL Quick-Reference vs SKILL selection table vs
`meta-framework.md` §4 catalog):
* `self-update`: **8** stages on disk (`check-refs, research-updates, decompose, integrate,
  si_chip_gate, test, self-improve, evaluate`) vs **7** (quick-ref) vs **6** (selection row) vs
  **2** (`meta-framework.md` row 20: "upgrade-skill → skill-bump").
* `nines-assisted`: **10** on disk vs **9** vs **8** vs **4** ("nines-analyze → nines-eval →
  review → validate").
* `repo-init`: **5** on disk vs **5** vs **5** vs **4** ("analyze → scaffold → compile → verify"
  — missing `interview`).
* `meta-framework.md` §4 header: "The **22 builtin templates**" + 22-row catalog — `web-design`
  (registered v13.0.0) is absent entirely, while the registry holds 23.
**Impact:** the reference an operator is told to load for "Workflow instantiation, stage
ordering" gives stage sequences that are wrong for the 3 most-actively-used templates.
**Recommendation:** v14.2.x — regenerate the catalog FROM the yamls (scriptable; the audit script
from D-A-2 already parses them), or delete per-template stage counts from prose surfaces and
point at the registry.

**F-P2-3 (info) — concrete Phase B collapse proposal (survivor set).** See §2.1.

**F-P2-4 (minor) — selection table routes to two non-templates.**
Evidence — SKILL.md selection rows `shell-proxy` ("RTK shell-proxy + memory_router fast-path
lookup at dispatch time (env-flag opt-in…)") and `grill-driven` have no entry in the Template
Quick-Reference or registry. One is an env-flag subsystem, the other a mode.
**Recommendation:** move both out of the workflow-selection table (shell-proxy → env-flags/
shell-proxy references; grill → Mode Awareness section already covers it).

### 2.1 Collapse proposal — 23 → 7 survivors + named compositions

**Survivors (remain as yaml templates):**

| Survivor | Why it survives |
|---|---|
| `change-driven` | The universal lifecycle chassis (propose → apply ↔ verify → archive); D-A-2 HIGH usage; OpenSpec-aligned |
| `repo-init` | Install-time bootstrap; fires via `devola-init`, not cycle selection |
| `self-update` | HIGH usage (6 cycle mentions, 5 commits) |
| `skill-optimization` | MOD usage; Si-Chip dogfood path |
| `migration` | Only template with cutover/deploy semantics (assess → migrate → cutover → verify) |
| `web-design` | Active (v13.0.0), plugin-bound (ui-pro ⊕ impeccable), refine ↔ verify convergence |
| `nines-assisted` | Cycle-close evaluation pattern (candidate to fold into `self-update` at v15.x) |

**Named compositions (replace the 16 legacy yamls; registry gains a `compositions:` block —
each is `base` + parameter overrides, expressible with the 5 operators in `meta-framework.md` §5):**

| Legacy template | Becomes |
|---|---|
| hotfix | `change-driven(gate=standard, stages={propose:triage, apply:fix, verify:test}, timeout=hotfix)` |
| research-only / design-only / documentation-only | `change-driven(apply.team=Research∣Design∣Implement-docs, skip=archive?)` — propose → apply → verify |
| spike-poc | `change-driven(gate=relaxed, verify=evaluate⊕decide)` |
| refactoring / feature-enhancement / full-pipeline / performance-optimization / security-audit / RDRR | `change-driven(mode=full, gate=convergence, quality_focus=…)` parameterizations; full-pipeline adds `release` tail |
| dependency-setup | `change-driven(mode=install)` (D-A-2 §2 Phase B example, verbatim) |
| onboarding | `repo-init(mode=core)` → `documentation-only` composition (D-A-2 §2, verbatim) |
| demo-showcase / product-verification | `web-design(verify_cfg={visual,interact,a11y,accept})` flavors |
| entropy-cleanup | `change-driven(stages={propose:scan, verify:review})` — already shaped propose/apply/verify |

**Operator-intent preservation:** the SKILL.md selection table keeps ALL intent keyword rows but
its third column becomes `survivor(params)` instead of a template name — selection vocabulary is
unchanged, registry maintenance drops from 23 yamls × 4 surfaces to 7 yamls + 1 manifest.

---

## §3 SKILL.md information architecture

**F-P3-1 (major) — budget saturation: 492/500 (98.4%) with ~109 demotable lines.**
Evidence: `wc -l workflow-system/agent/SKILL.md` = 492; SF-1/C-4 ceiling < 500. Eight lines of
headroom remain while §1.1 identifies ~109 lines of CEREMONY. Every future output-closure feature
(the actual north-star gap) is blocked or forces another extraction PV.
**Recommendation:** v14.5.0 IA pass per F-P1-3; target ≤ 420 lines post-demotion.

**F-P3-2 (major) — Tier-3 navigation omits an example the body itself cites; rule surfaces disagree on counts.**
Evidence: SKILL.md cites "`examples/multi-stage-trace.md`" at lines 76 and 201, but the Tier-3
table (lines 442–455) lists only `full-pipeline-trace` / `hotfix-trace` / `convergence-loop-trace`.
On disk there are **4** examples; `scripts/sync_cursor_skill.py::MIRRORED_FILES` mirrors all 4
(line 140). Meanwhile `repo-governance.mdc` C-4 still budgets "`examples/*.md` (**3 files**)" and
`.cursor/rules/skill-format-rules.mdc` SF-1 claims "the canonical **14-file** set" and
"references/*.md (**10 files**)" against an actual 24 references / 41 mirrored files.
**Impact:** an operator following the navigation guide cannot find the cascade trace the Quick
Action table tells them to read; rule surfaces give three different inventories.
**Recommendation:** v14.2.x — add the Tier-3 row; recompile rule surfaces from one inventory.

**F-P3-3 (minor) — stale frontmatter `token_estimate: 2800`.** 492 lines ≈ 5–6K tokens. The
estimate is consumed by budget allocators; under-declaring Tier-1 cost skews P2 budget math.

**F-P3-4 (minor) — Session Banner Contract hardcodes a stale version three times.**
Evidence — SKILL.md lines 44–46: "`🌸 DevolaFlow v12.3.0 active`", "`🌸 DevolaFlow v12.3.0
complete`", "footer line MUST include literal `DevolaFlow v12.3.0`" — in a v14.1.0 file whose
same section instructs "Use the literal version string from this §'Version & Update' header".
`bump_version.py` patterns evidently don't cover these example literals.
**Recommendation:** v14.2.x — replace with `vX.Y.Z` placeholders (also shrinks the section).

**F-P3-5 (major) — template information is triplicated; primitives/team tables duplicated.**
Evidence: stages-per-template appear in (a) SKILL selection table, (b) SKILL Template
Quick-Reference, (c) `meta-framework.md` §4 catalog — already divergent per F-P2-2. Stage
Primitives Index (SKILL 235–283) duplicates `meta-framework.md` §1–2; AgentTeam Quick Reference
duplicates `team-roles.md`; gate formulas duplicate `decomposition-gate.md`.
**Impact:** N-surface sync cost is the root cause of F-P2-2-class drift; C-3 verbatim discipline
is applied to dispatches but not to the product's own documentation surfaces.
**Recommendation:** one owner surface per fact (A-5 spirit applied to docs); SKILL keeps only the
selection table + pointers.

**F-P3-6 (minor) — reference corpus optimized for governance archaeology, not operator lookup.**
Evidence: 24 references total **13,270 lines** (avg 553). `env-flags.md` spends ~500 lines on 14
flags, each row embedding multi-cycle W-20 justification history (e.g. §2.12's 200+-word
"Why a NEW flag" cell). Load-when triggers are good; in-file signal density is low.
**Recommendation:** style lint for references: contract first, history collapsed to a Sources
footer; defer to v14.5.0 with the IA pass.

---

## §4 Dispatch protocol ergonomics (as the receiving L3)

**F-P4-1 (major) — `acceptance_criteria_v2` auto-generation covers 2 of 17 profiles.**
Evidence — `context_profiles.yaml#meta.ac_generation_defaults`: "`enabled: false`" with per-profile
opt-in; the only `ac_generation: enabled: true` blocks are `feature` (line 910) and `refactor`
(line 1069). The profile set is 17 (hotfix, feature, research, refactor, review, design,
migration, documentation, rdrr, onboarding, self_update, feedback, verify_visual,
verify_acceptance, verify_interaction, product_verification, entropy_scan). `DEVOLAFLOW_AC_GEN`
defaults on only for STRICT/AUDIT (env-flags §2.10).
**Impact:** the single highest-leverage input for task excellence — structured, machine-checkable
AC with `verification_cmd` — is absent by default for hotfix (where regressions hurt most),
migration, design, documentation, and all verify profiles.
**Recommendation:** v14.4.0 — enable for hotfix + migration + documentation with profile-tuned
patterns; measure AC quality via the existing `min_quality_threshold` gate.

**F-P4-2 (critical) — mandated L3 self-check evidence has no transport in the report schema.**
Evidence — `references/behavioral-guidelines.md` BG-001: "The plan is captured in the
StatusReport's ``plan_artifact`` field"; BG-004: "restate the original user request VERBATIM in
your StatusReport's ``goal_anchor`` field"; BG-006/BG-007 mandate `ConflictFinding` /
`ADRRequiredFinding` entries. `schemas/lean-report.yaml#lean_format_spec` defines exactly: `hdr`,
`state`, `artifacts`, `metrics`, `issues`, `decisions` (+ optional `learnings`, `cycle_detected`,
`cycle_details`, `rs`). **None** of `plan_artifact`, `goal_anchor`, or a typed finding entry
exists.
**Impact:** the behavioral-guidelines layer (the product's flagship L3 discipline mechanism) is
unverifiable by construction — L0/L2 cannot check compliance because the contract gives the
attestations nowhere to live. This is the precise mechanism by which "behavioral guidelines are
prompt-only self-checks" (prior diagnosis confirmed).
**Recommendation:** v14.3.0 — append-only additive block in lean-report.yaml (`self_check:
{plan_artifact, goal_anchor, bg_attestations: [{id, verdict, evidence}]}`); lean-report has no
P6 layout invariant ("lean-report.yaml has NO ``layout_invariant:``"), so this is low-risk.

**F-P4-3 (major) — `metrics.quality` contradicts the "no subagent quality_score" doctrine.**
Evidence — lean-report.yaml `lean_example.metrics: { pass: 12, fail: 0, cov: 94.2, quality: 92,
… }` and `lean_format_spec.metrics.fields: { …, quality: float, … }` vs SKILL.md line 371:
"Subagent reports DO NOT include `quality_score` (L0-only…)" and `task-quality-score.md`:
"L1 / L2 / L3 StatusReport / WaveReport / StageReport carry NO `quality_score` field … v12.2.0
PV-04 runtime hook `reject_subagent_quality_score`."
**Impact:** the schema's own canonical example teaches L3 agents to emit a quality number the
governance layer forbids; the runtime hook checks only the top-level key, so the nested field
sails through. Receivers can't tell which doctrine wins.
**Recommendation:** v14.2.x — either rename `metrics.quality` (e.g. `gate_input_score`) with an
explicit "this is NOT Task Quality Score" note, or drop it from the spec/example.

**F-P4-4 (critical) — `predecessor_dedup_ledger` is incoherent with Context Isolation.**
Evidence — lean-dispatch.yaml pos-17 field: "matching summaries are replaced by an
``"@round-N-1:pred-K"`` reference and the ledger records the dedup hit **so the receiver can
decompress**." SKILL.md §Context Isolation: "Each Task Agent spawns with a **fresh, isolated
context**" and "MUST NOT leak: conversation history… full predecessor artifacts". A fresh round-N
L3 has never seen round-N-1's dispatch; the `@round-N-1:pred-K` pointer is unresolvable for it.
The field only works if the same agent context persists across rounds — which the isolation
contract forbids and the gen-verify loop leaves ambiguous ("generator refines (round N+1)").
**Impact:** in the worst case a round-2 fix task loses exactly the predecessor facts it needs
(token savings purchased with input quality — directly anti-north-star).
**Recommendation:** v15.0.0 ADR-4 candidate (see §7): either constrain the ledger to
persistent-generator dispatch shapes (and say so in the schema), or drop population and keep the
key as absence-canonical.

**F-P4-5 (minor) — the dispatch schema is 60%+ governance archaeology.**
Evidence: `schemas/lean-dispatch.yaml` is 739 lines; the actionable spec (`lean_example` +
`lean_format_spec` field shapes + `layout_invariant` data) is < 250; the remainder is per-cycle
comment blocks ("v9.0.0 PV-02 D6 — This block … is byte-identical to its v8.3.0 PV-05 / v8.4.0 /
v8.4.1 form…"). An L3 (or integrator) reading the contract pays for the cache-governance history.
**Recommendation:** move history to an ADR appendix file; keep one-line provenance pointers.

**F-P4-6 (major) — the report schema cannot carry evidence of task excellence.**
Evidence — `lean_format_spec.metrics` = `{pass, fail, cov, quality, findings}` only. There is no
field for: per-AC verdicts (despite dispatch-side `acceptance_criteria_v2.verification_cmd` and
gate-side `evaluate_acceptance_criteria_v2` emitting "per-criterion AcceptanceCriterionVerdict
outcomes" — gate-internal, not report-borne), diff stats (files/LOC changed vs the "~50–300 lines
changed" sizing contract), lint results, or self-check attestations (F-P4-2). `artifacts[].delta`
is capped at "≤15 words".
**Impact:** L0's VERIFY step ("**VERIFY** task output against acceptance criteria") has to
re-derive everything from disk because the report cannot prove anything; excellence evidence
dies at the L3 boundary.
**Recommendation:** v14.3.0 — additive `ac_results: [{id, verdict, cmd_output_digest}]` +
`diff_stats: {files, insertions, deletions}` blocks; feeds the F-P1-2 artifact rubric.

**Field actionability census (for a real L3 receiver):** actionable — `task`, `goal`, `pred`
(key_facts), `files`, `accept`/`acceptance_criteria_v2`, `rules`, `shared`, `reinforce` (round≥2),
`behavioral_guidelines`, `change_context` (workspace on), `hdr.timeout`. Conditionally useful —
`verify_cfg` (verify tasks), `gate` (targets only; L3 never evaluates the gate), `assumptions`.
Dead weight for L3 — `repos` (rare multi-repo), `predecessor_dedup_ledger` (compression
bookkeeping, F-P4-4), `gate.cascade_*`/`gate.subagent_pattern` (dispatch-shape provenance the
leaf can't act on).

---

## §5 Plugin & degraded-mode surface

**F-P5-1 (major) — the two plugin registries disagree on membership and IDs.**
Evidence — `workflow-system/agent/plugins.yaml` defines **5** plugins: `nines`, `si-chip`,
`ui-ux-pro-max`, `codegraph`, `impeccable` (no RTK). `knowledge/runtime-plugins.yaml` defines
**6**: `nines`, `ui-pro`, `rtk`, `si-chip`, `codegraph`, `impeccable`. The same plugin is
`ui-ux-pro-max` in one and `ui-pro` in the other. `degraded-mode.md` asserts "each of the 6
registered plugins". runtime-plugins.yaml line 15 frames plugins.yaml as a "legacy PluginRegistry
catalog, kept intact for backward compatibility" — yet plugins.yaml gained the two NEWEST plugins
(codegraph v12.5.0, impeccable v13.0.0), so it is not frozen-legacy; both surfaces actively grow.
**Impact:** A-5 single-owner is formally satisfied (two registries, two owners) but the product
answer to "what plugins exist, under what ID?" depends on which file you read; `plugins_for_
workflow()` answers differ from capability lookups.
**Recommendation:** v15.0.0 — collapse to one registry (runtime-plugins.yaml as owner; derive the
capability/stage_mapping view) or freeze plugins.yaml for real.

**F-P5-2 (minor) — degraded-mode.md internal and cross-file count/anchor drift.**
Evidence: header says "6 registered plugins (NineS, Si-Chip, RTK, ui-pro, codegraph, impeccable)"
but the same file says "without installing NineS / Si-Chip / RTK / ui-pro" and §When-to-Load
"any of the **4 plugins**". Cross-references cite "`env-flags.md` §2.13 — the
`DEVOLAFLOW_AUTO_INSTALL_PLUGINS` flag" and "§2.14 — the `DEVOLAFLOW_SI_CHIP_DEEP` flag", but
after the v12.0.0 renumbering those live at §2.12 and §2.13 (env-flags.md's own retirement note:
"Subsequent §2.13/§2.14/§2.15 sub-sections were renumbered to §2.12/§2.13/§2.14").
**Recommendation:** v14.2.x doc sweep.

**F-P5-3 (major) — the env-flag "single source of truth" is missing ≥2 runtime flags, and the rule-layer counts don't match it.**
Evidence: SKILL.md consumes `DEVOLAFLOW_MEMORY_CONSULT=1` (line 61) and
`DEVOLAFLOW_AGENT_WORKSPACE=1` (line 66; also A-6 + the runtime `auto_write_handoff` default
handler and `memory_router/cache.py`). Neither has an inventory row in `env-flags.md` §2 —
AGENT_WORKSPACE appears only inside other flags' W-20 justification prose; MEMORY_CONSULT appears
nowhere in the file. Meanwhile §2 documents **14** active rows (§2.1–§2.14), while the rules
layer claims "the env-flag count remains at 8 per v11.1.3 baseline" (W-22.4), "stays at 8 per
v11.3.0 baseline" (W-24.4), and env-flags.md itself says "Env-flag count goes 8 → 7" (v12.0.0
retirement note) and "env-flag count stays at 7 (no growth at v12.5.0)" (§7). No surface defines
the counting basis that yields 7/8 from 14 rows + 2 undocumented flags.
**Impact:** W-20's enforceability premise — "Enforcement requires the reviewer to **see** the
inventory" (env-flags.md §1) — fails for exactly the two flags that gate the workspace/memory
surfaces SKILL.md activates.
**Recommendation:** v14.4.0 — add §2 rows for AGENT_WORKSPACE + MEMORY_CONSULT; define the count
basis (e.g. "opt-in R5-strict runtime activation flags") and restate it everywhere a count is
claimed.

**F-P5-4 (minor) — three activation patterns coexist; R5 strict is not uniform.**
Evidence: strict `"1"` opt-in (RTK_PROXY, MEMORY_ROUTER, …); default-ON opt-OUT `"0"`
(AUTO_INSTALL §2.5, AGENTS_MD_SLICE §2.11); loose-parsing (`PLAN_MODE` §2.1: `{"1","true","yes",
"on"}`, explicitly "NO — historical loose-parsing"). Each is documented, but a new flag author
must pattern-match across 14 rows to pick one.
**Recommendation:** small pattern table at the top of env-flags.md §2 (3 rows: strict-opt-in /
default-on-opt-out / loose-legacy) with the rule "new flags MUST be pattern 1".

**F-P5-5 (info) — degraded-mode coverage is complete (positive), but the only deterministic artifact gate is web-only.**
All 6 runtime plugins have a degraded-mode section + pinned test (matrix rows cite
`tests/test_degraded_mode.py::test_*` / `tests/test_codegraph.py`), satisfying the D-C-1
admission gate. Plugin↔north-star coherence: codegraph (input quality, DIRECT-enabling), ui-pro +
impeccable (DIRECT for web tasks — `impeccable detect` is the product's ONLY no-LLM artifact
output gate, "27 deterministic rules; exit 2 = found"), rtk (token economy), nines + si-chip
(framework self-evaluation — GOVERNANCE-facing, not operator-task-facing).
**Recommendation:** telegraph for v15.x — generalize the impeccable pattern (deterministic
detector + exit-code verify gate) to non-web artifacts (lint/test/AC-cmd bundle as a generic
`detect`-style verify stage).

**F-P5-6 (minor) — plugins.yaml still ships the si-chip version probe that runtime-plugins.yaml explicitly retired.**
Evidence — plugins.yaml `si-chip.version_command: "test -f $HOME/.cursor/skills/si-chip/SKILL.md
|| … && echo si-chip/0.4.0"`; runtime-plugins.yaml v10.2.0 comment: replaced that exact heuristic
"(which ALWAYS reported 0.4.0 regardless of what was actually installed)" with the
`read_installed_si_chip_version` probe. The companion registry never got the fix.
**Recommendation:** fold into F-P5-1's unification, or patch in v14.2.x.

---

## §6 Ladder mapping

| Finding | Land at | Rationale (1 line) |
|---|---|---|
| F-P2-2 | v14.2.x | Doc regeneration from yamls; zero behavior change |
| F-P3-2 | v14.2.x | Add Tier-3 row + recompile rule inventories; trivial |
| F-P3-3 | v14.2.x | One frontmatter number |
| F-P3-4 | v14.2.x | Placeholder literals; shrinks banner section |
| F-P4-3 | v14.2.x | Rename/annotate `metrics.quality`; doctrine clarity |
| F-P5-2 | v14.2.x | Anchor/count sweep in degraded-mode.md |
| F-P5-6 | v14.2.x | Copy the fixed probe into plugins.yaml |
| F-P4-2 | v14.3.0 | Additive report block (`self_check`); no layout invariant on report side |
| F-P4-6 | v14.3.0 | Additive `ac_results` + `diff_stats`; prerequisite for artifact rubric |
| F-P1-5 | v14.3.0 | Specify L3 intra-task self-verify step consuming AC `verification_cmd` |
| F-P4-1 | v14.4.0 | Extend `ac_generation` to hotfix/migration/documentation profiles; needs pattern tuning + EvoBench per W-4 |
| F-P5-3 | v14.4.0 | Inventory completion + counting-basis definition; W-20 enforceability |
| F-P5-4 | v14.4.0 | Pattern table; pairs with F-P5-3 |
| F-P1-3 / F-P3-1 / F-P3-5 | v14.5.0 | SKILL IA pass: demote ceremony, dedupe triplicates; W-5 coupling makes this its own PV |
| F-P1-4 | v14.5.0 | Rides the same IA pass |
| F-P3-6 | v14.5.0 | Reference style lint; same pass |
| F-P2-1 / F-P2-3 / F-P2-4 | v15.0.0 | Phase B collapse 23→7 + composition manifest; registry schema bump (A-2.3 governance), removal already telegraphed since v11.0.0 |
| F-P1-1 | v15.0.0 | Output-closure wiring decision (ADR-2); behavior-changing |
| F-P1-2 | v15.0.0 | Artifact-quality rubric (ADR-3); depends on v14.3.0 report fields |
| F-P4-4 | v15.0.0 | Dedup-ledger semantics (ADR-4 candidate); schema contract change |
| F-P5-1 | v15.0.0 | Registry unification; public-surface change |
| F-P4-5 | defer | Cosmetic for integrators; revisit if schema files split anyway during v15.0.0 |
| F-P5-5 | defer (telegraph v15.x) | Generic deterministic verify-gate generalization needs its own SI-1 slice |

---

## §7 ADR-needed decisions (3-condition gate: hard to reverse + surprising + real trade-off)

**ADR-1 — Template registry collapse (23 → 7 + composition manifest).**
Hard to reverse: deletes 16 public yaml files and bumps registry schema v1.0 → v2.0; downstream
`.workflow/config.yaml` `workflow_type:` references break without the alias layer. Surprising:
selection keywords keep working while the yamls vanish. Real trade-off: per-template explicitness
& greppability vs 4-surface sync cost and 27% utilization. → qualifies.

**ADR-2 — Output-closure enforcement locus for `check_file_write` / `post_task_complete`.**
Hard to reverse: once an execution adapter fires hooks at write/stop time, it becomes a
compatibility surface (R5 zero-IO defaults, strict-mode semantics). Surprising: the hooks have
shipped unwired for 7 major versions while SKILL.md advertised them. Real trade-off: real
enforcement (subprocess/IO cost, harness coupling) vs honest prompt-only labeling (keeps R5
purity, abandons the enforcement claim). → qualifies.

**ADR-3 — L3 artifact-quality scoring vs the "subagents MUST NOT score" doctrine.**
Hard to reverse: report-schema fields + gates consuming them become contract. Surprising: partial
inversion of the v12.1–12.3 closure that stripped quality_score from subagent reports. Real
trade-off: self-assessment bias vs L0 re-derivation cost; mitigable by scoring only
evidence-backed dimensions (AC verdicts, test/cov, scope adherence) and keeping the holistic
score L0-side. → qualifies.

**ADR-4 (evaluated — currently FAILS the gate) — `predecessor_dedup_ledger` semantics.**
Hard to reverse: NO — the field is absence-canonical; ceasing population is byte-stable per the
OPTIONAL contract. Per W-22.3 discipline this is a design fix (F-P4-4), not an ADR, unless the
chosen remedy is "persistent-generator dispatch shape" (which WOULD alter the isolation contract
and then re-enters the gate). Surface in the v15.0.0 SI-1 either way.

---

## §8 Single-task excellence scorecard (product today, 1–10)

| Axis | Score | Justification (2 sentences) |
|---|---|---|
| Task input quality | **8/10** | Context profiles (17 task types with priority-tiered sections), verbatim key_facts, behavioral-guidelines injection, codegraph-accelerated context, and reinforcement-carrying dispatches make the input side genuinely strong and cache-disciplined. Deductions: AC v2 generation covers 2/17 profiles (F-P4-1) and the dedup ledger can silently starve round-N inputs (F-P4-4). |
| Task output verification | **4/10** | Verification exists only above the task: stage gates and the wave-level gen-verify loop; the only deterministic artifact gate is web-only (`impeccable detect`). Write/stop-time hooks are unwired (F-P1-1), behavioral self-checks have no transport (F-P4-2), and no rubric scores the artifact itself (F-P1-2). |
| Task feedback loops | **6/10** | Gate-FAIL reinforcement (top-5 mandates, round-aware escalation, cycle detection) and operational-learnings decay/pinning are real, working loops. But feedback triggers only on stage-gate failure — a task that passes with mediocre-but-acceptable output generates no improvement signal, and per-AC verdicts never flow upward (F-P4-6). |
| Operator ergonomics | **5/10** | Mode awareness, the complexity table, troubleshooting reference, and degraded-mode contracts are operator-friendly; activation is genuinely natural-language. But the operator faces a 25-row selection table that is 70% legacy, a saturated 492-line prompt with ~22% ceremony, 13K lines of changelog-styled references, and three mutually inconsistent counts for templates/flags/examples (F-P2-2, F-P5-3, F-P3-2). |

**Bottom line:** the product is an excellent task-INPUT machine attached to an underbuilt
task-OUTPUT machine. The v14.2→v15 ladder should spend its budget on report-side closure
(v14.3.0), AC coverage (v14.4.0), IA debt (v14.5.0), and the three ADR-gated structural moves
(v15.0.0) — in that order, because each rung's evidence fields feed the next rung's mechanisms.

---

*Findings: 27 total — 3 critical (F-P1-1, F-P4-2, F-P4-4), 12 major, 9 minor, 3 info. All
evidence verbatim from v14.1.0 working tree on 2026-06-12.*
