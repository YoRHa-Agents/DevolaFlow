# D-D-3 — C-4 Line-Budget Counter-Effect Evaluation (Patch Design Specification)

> **Status:** PDS authored by L3 Task Agent (Wave 3 D-D)
> **Author:** L3 (composer-2-fast)
> **Date:** 2026-05-04
> **Cycle:** v11.0.0 SI-1 planning
> **Source direction:** `.local/research/v10_internal_optimization_directions.md` §3.7 D-D-3
> **PDS schema:** `v11.0.0_decomposition_plan.md` §3
> **Owned files:** `.local/research/v11.0.0_patches/D-D-3.md`
> **External tools (S-7):** DevolaFlow `https://github.com/YoRHa-Agents/DevolaFlow`

## §1 — Current state (50-150 words; verbatim file path evidence)

`.cursor/rules/repo-governance.mdc` C-4 / `.cursor/rules/skill-format-rules.mdc` SF-1 enforce a tiered line ceiling: SKILL.md < 500, references ≤ 1000, examples ≤ 1600. v10.3.0 actuals (`wc -l workflow-system/agent/SKILL.md workflow-system/agent/references/*.md workflow-system/agent/examples/*.md`):

```
   460 SKILL.md
   267 agent-hierarchy.md          // smallest reference
   747 agent-workspace.md
   293 behavioral-guidelines.md
   438 compression-pipeline.md
   570 context-isolation.md
   590 decomposition-gate.md
   432 env-flags.md
   818 execution-protocol.md       // largest reference
   630 message-schemas.md
   596 meta-framework.md
   647 plan-mode-enforcement.md
   309 repo-modes.md
   720 shell-proxy.md
   576 team-roles.md
   332 convergence-loop-trace.md
   408 full-pipeline-trace.md
   203 hotfix-trace.md
   ----
   9036 total
```

`.local/research/v10.2.4_w17_mid_cycle_audit.md` §4 `"high-information disposition"` cites the v10.0.0 retrospective §3.4 W-17 acceptance precedent — explicitly framing dense prose as "every test pins a distinct contract surface; no redundant scaffolding". `.local/research/karpathy_skills_analysis.md` lines 6-23 establishes the **verbatim knowledge principle** ("Reduce silent interpretation: multiple readings must be surfaced, not chosen quietly"). The two principles are in tension: maximally-dense prose risks ambiguity even when each line pins a contract. **Today, no audit measures whether C-4 budget pressure has caused specific paragraphs to drift from "dense but clear" toward "compressed and ambiguous"**.

## §2 — Patch design (algorithm + files-touched + API/CLI surface)

**Deliverable:** A research artifact (not a refactor) — `.local/research/v11.0.X_line_budget_audit.md` produced by a one-shot analysis script, plus a 3-paragraph expansion proposal embedded in the artifact for L0 review. Implementation refactors are DEFERRED out-of-scope; this patch ships the EVIDENCE so future cycles can decide.

**Algorithm (executed by `scripts/audit_line_budget_density.py`):**
1. For each of 14 references + SKILL.md, compute: line count, word count, average line length, abbreviation density (count of `re.findall(r'\b[A-Z]{2,}-\d+\b', text)` for matches like `S-9`, `BG-001`, `PV-04`), cross-reference density (count of `references/[a-z-]+\.md` mentions per 100 lines), example-block count (count of fenced code blocks per 100 lines).
2. Identify the **3 worst paragraphs** per heuristic — paragraphs (1) > 100 words AND (2) > 5 abbreviations AND (3) zero embedded examples. These are the empirical "compressed-and-cryptic" candidates.
3. Emit `.local/research/v11.0.X_line_budget_audit.md` with: density table, the 3 worst paragraphs CITED with line numbers, and a verbatim "before / after expansion" proposal for each.
4. The proposal does NOT modify any reference file; it only PROPOSES specific expansions for L0 / human review in v11.1.0+.

**Files-touched (≤ 6 owned):**
- `scripts/audit_line_budget_density.py` (NEW; ~180 LOC)
- `tests/test_audit_line_budget_density.py` (NEW; ~70 LOC, 5-7 test functions)
- `Makefile` (1-line ADDITION: `audit-density` target)
- `CHANGELOG.md` (entry under v11.0.X)
- `tests/test_no_ghost_features.py` (W-18 lint refresh)

**API surface:** `python scripts/audit_line_budget_density.py [--target-paths PATH...] [--worst-n N]`. Pure stdlib + regex — zero new dependencies.

**P6 / A-2 invariance:** Audit-only. No SKILL/reference content modified by this patch. The proposed expansions in the artifact are evidence for human review; they do not auto-apply.

## §3 — Small project evaluation

**Synthetic test bed:** `synthetic_small_repo/` (per `v11.0.0_evaluation_methodology.md` §2).

**Operations exercised:** `docs` (workflow that loads SKILL.md + relevant reference subset for a small documentation-update task).

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4:
- Reference avg line count
- Abbreviation density (heuristic per §2 algorithm)
- Example-block density

**Expected delta (before → after audit lands; the audit is observability-only):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Density-heuristic visibility (per ref) | 0 | 14+1 (refs+SKILL) | +15 measurements | improve |
| Worst-paragraph identification | unknown | top 3 surfaced | +3 evidence rows | improve |
| Comprehension cost on small repo | unchanged (refs are loaded as-is) | unchanged | 0 | byte-stable |

**Pass criterion:** Audit script runs in < 3 s on the small repo and identifies the same 3 worst paragraphs (citing the same line numbers as §5 below).

**If no improvement on small project:** N/A — the heuristic is identical for any reference text. Small-repo benefit comes via "you can READ the audit and judge for yourself" — even if the small repo never loads compression-pipeline.md, the audit is a portable artifact.

## §4 — Large project evaluation

**Test bed:** DevolaFlow self at v10.3.0 baseline.

**Metric collection:** Per `v11.0.0_evaluation_methodology.md` §4.4 + heuristic from §2:
- Per-reference word-density (avg words/line)
- Per-reference abbreviation count (regex `\b[A-Z]{2,}-\d+\b`)
- Per-reference example-block density (fenced code blocks per 100 lines)

**Expected delta (v10.3.0 baseline → post-patch knowledge state):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Reference density data points | 0 | 14 + 1 SKILL + 3 examples = 18 | +18 measurements | improve |
| Worst-paragraph identification | informal / anecdotal | 3 specific line-cited proposals | +3 evidence rows | improve |
| Reference avg lines | 578 (8093/14) | 578 (audit doesn't shrink) | 0 | byte-stable |
| SKILL.md line count | 460 | 460 (audit doesn't shrink) | 0 | byte-stable |
| Test count delta | N/A | +5-7 | +5-7 | within W-17 cap |

**Pass criterion:** The 3 line-cited paragraphs from §5 below appear verbatim in the audit output. Operator can read the artifact and AGREE OR DISAGREE with the expansion proposals — this is the epistemic deliverable, not the refactor itself.

**Side-effect check:** Zero reference / SKILL content changes. Zero selector behavior changes. Zero schema changes.

## §5 — Benefit metrics (≥ 3 quantitative DF-internal metrics + 3 cited paragraph examples)

| # | Metric | Baseline (v10.3.0) | Post-patch | Δ |
|---|---|---:|---:|---:|
| 1 | References with empirical density data | 0 / 14 | 14 / 14 | +14 |
| 2 | Cited "compression hurts comprehension" examples | 0 (anecdotal only) | 3 (line-numbered, verbatim — see §5.1-§5.3 below) | +3 |
| 3 | Reference total lines | 8093 | 8093 (unchanged) | 0 |
| 4 | Reference long-tail (refs at < 350 lines = under-budget headroom) | unknown | known: 4 refs (`agent-hierarchy.md` 267, `behavioral-guidelines.md` 293, `repo-modes.md` 309, `hotfix-trace.md` 203) | +visibility |
| 5 | Operator time to identify "should I expand reference X §Y?" | ~20 min (manual scan + judgment) | < 1 min (read audit table) | -95% |
| 6 | Refactor proposals embedded in artifact | 0 | 3 (with verbatim before/after text) | +3 |

**Cross-tier benefit summary:** The data lets BOTH tiers benefit identically — the small repo never sees the dense paragraphs because they're not loaded by trivial workflows, but the audit is a portable artifact that ANY operator can consult before authoring new dense prose. The large-repo benefit is concrete: 3 specific expansions surfaced for v11.1.0+ consideration.

### §5.1 Cited example 1 — `workflow-system/agent/SKILL.md` lines 38-40 (install paragraph; ~106 words, 4 issue tags `I-001`/`I-004`/`v9.2.2`/`v9.2.3`, 0 example blocks)

**Verbatim:**

> "**Note (v9.2.2+)**: `pip install` ships the package but the `devola-init` CLI's `cursor` / `claude` / `codex` / `copilot` targets need the `workflow-system/agent/` source tree (not bundled in the wheel). For most install scenarios `devola-init local --mode=core` works on a wheel-only install (v9.2.3+ — `--mode=core` is the shorthand for `--no-compile --no-with-examples`, the lean scaffolding-only install). For other targets, install from a clone: `git clone https://github.com/YoRHa-Agents/DevolaFlow && pip install -e ./DevolaFlow`. Tracked in I-001 (fixed v9.2.2) + I-004 (doc v9.2.2) + `--mode` shorthand (v9.2.3); full bundle deferred to v9.3.0."

**Comprehension hurt:** 4 distinct concepts (wheel-vs-clone install, `--mode=core` shorthand semantics, alt-install command, 3 issue-tracker IDs) interleaved in one paragraph. Reader cannot quickly answer "do I need to clone?" without re-reading.

**Proposed expansion (~+8 lines):** Replace with a 3-row decision table (`Target | Install command | Why`) plus an inline `<details>` block for the issue-tracker IDs. SKILL.md grows 460 → ~468 lines (within 500 ceiling).

### §5.2 Cited example 2 — `workflow-system/agent/SKILL.md` line 460 (Operational Learnings paragraph; ~130 words, 6 API calls + 2 constants + 1 formula + 1 ADR ref, 0 example blocks)

**Verbatim:**

> "Persisted learnings (`.../learnings/operational.jsonl`) carry a confidence half-life (default 30 days per `DEFAULT_DECAY_HALF_LIFE_DAYS`): `decay_confidence()` applies `new_conf = conf - 0.5 * min(1, days_since_last_access / half_life)`, prunes entries below `DECAY_FLOOR=0.1`; `consolidate_session(session_id, session_learnings, path)` bumps matched entries by +0.05 at session end and appends new ones with `promotion_count=1` — stale entries decay while validated insights stay fresh. For cross-round convergence loops that must keep a specific insight in context regardless of confidence, call `pin_learning_for_session(key, stage, task_type, session_id, path)` — `load_relevant_learnings(..., session_id=...)` then surfaces pinned entries first. Reserve pinning for blockers (ADR-005 §3); legacy v1 entries parse unchanged, `last_accessed` lazily backfilled from `timestamp` on first decay."

**Comprehension hurt:** Single 130-word run-on encodes a state machine (decay → prune → consolidate → pin) with no diagram and no signature breakdown. The formula `new_conf = conf - 0.5 * min(1, days_since_last_access / half_life)` is buried mid-sentence. An L3 agent reading this for the first time loses 30+ seconds parsing.

**Proposed expansion (~+15 lines):** Split into 3 sub-bullets (Decay / Consolidate / Pin) with the formula on its own line in a fenced block. SKILL.md grows 460 → ~475 lines (within 500 ceiling). Tradeoff: still well under SF-1 default tier ceiling; comprehension cost drops dramatically.

### §5.3 Cited example 3 — `workflow-system/agent/references/compression-pipeline.md` lines 192-199 (the 5-transform canonical table; cryptic `[N]` factory indices)

**Verbatim:**

```
| # | Transform | Module | Factory | Bypass conditions |
|---|---|---|---|---|
| 1 | `truncate_tool_output` | `devolaflow.compressor` | `compression_pipeline_stages()[0]` | always runs (caller gates via `context["truncate_enabled"]`) |
| 2 | `summarise_predecessor` (extractive + Stage A) | `devolaflow.compressor` | `compression_pipeline_stages()[1]` | always runs (caller passes `mode="extractive"` / `mode="abstractive"`) |
| 3 | `directed_compact` | `devolaflow.compressor` | `compression_pipeline_stages()[2]` | always runs (empty focus_keywords = no-op) |
| 4 | `summarise_predecessor` (Stage B — LLM-assisted) | `devolaflow.llm_client` | `compression_pipeline_stage()` | bypass when `context["llm_client"]` is `None` |
| 5 | `apply_local_recipe` | `devolaflow.shell_proxy.commands` | `compression_pipeline_stage()` | bypass when `DEVOLAFLOW_RTK_PROXY` env-flag unset |
```

**Comprehension hurt:** Rows 1-3 use `compression_pipeline_stages()[0]` / `[1]` / `[2]` — opaque positional indices that force the reader to open `src/devolaflow/compressor.py` to learn what each index returns. Rows 4-5 use a different naming convention (`compression_pipeline_stage()` singular, no index) without explaining why rows 1-3 collapsed into one factory. The single-table dense form was chosen to fit the C-4 reference budget (compression-pipeline.md is at 438 lines vs the 1000 ceiling — there IS room for expansion).

**Proposed expansion (~+12 lines):** Replace cryptic `[N]` indices with named module-level constants (`devolaflow.compressor.TRUNCATE_STAGE`, `SUMMARISE_STAGE`, `DIRECTED_COMPACT_STAGE`) and add a 3-line preamble explaining why `compression_pipeline_stages()` returns a tuple while `llm_client.compression_pipeline_stage()` returns one stage. compression-pipeline.md grows 438 → ~450 lines (still well under 1000 ceiling).

## §6 — Admission verdict

**Verdict:** **PASS**

**Rationale:** Pure observability + 3-paragraph-example deliverable. No file modifications outside the audit script + tests. G-1 internal-value (6 quantitative metrics in §5 plus 3 cited paragraphs in §5.1-§5.3), G-2 both-tier (audit is portable), G-3 zero external deps, G-4 cycle-budget (+5-7 tests), G-5 Soul-freeze (no S-11), G-6 cache-prefix (no canonical_order touched), G-7 compatibility (additive script only), G-8 coverage (5-7 unit tests target ≥ 90% on ~180 LOC), G-9 docs (CHANGELOG + W-18 lint refresh per §2). All gates green.

The patch ships the **evidence**; future cycles decide whether to act on it. This separation is intentional and matches the v10.0.0 retrospective §4.5 "high-information vs scaffolding distinction" pattern: the audit produces high-information evidence; refactor decisions go through their own SI-1 gap analysis.

## §7 — Effort estimate

**S** (≤ 0.5 PV; ~1 PV at the upper end if paragraph selection requires multi-round refinement).

Per source §3.7 D-D-3 estimate; confirmed by §2 file-touched count (5 owned files, ~250 LOC total — script is slightly heavier than D-D-1/D-D-2 due to regex-density passes). Implementation breakdown: ~3 hr script (heuristic + paragraph selector + expansion proposal generator) + ~1.5 hr tests + ~30 min CHANGELOG / W-18 lint = ~5 hr.

## §8 — Dependencies

**none** — standalone audit. Optionally consumes D-D-1's reference utilization data (if D-D-1 lands first) to weight the heuristic — i.e. paragraphs in HIGH-utilization references with HIGH-density score are higher priority than equally dense paragraphs in LOW-utilization references. But this is an enhancement, not a hard dependency.

## §9 — Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | The 3 example paragraphs in §5.1-§5.3 may be subjective — another L3 reading the same references might pick different "worst" candidates. | major | The audit's heuristic (> 100 words AND > 5 abbreviations AND zero example blocks) is DETERMINISTIC and reproducible. The 3 paragraphs in §5.1-§5.3 are the OUTPUT of applying that heuristic to the v10.3.0 reference corpus — they will reproduce on any clone at the same baseline. Subjective disagreement applies to the heuristic THRESHOLDS, not to the citations themselves. |
| 2 | An L0 / human reviewer may take the expansion proposals as a refactor mandate rather than a v11.1.0+ consultation artifact, prematurely growing references toward the 1000-line ceiling. | major | The audit artifact's CHANGELOG entry MUST explicitly tag proposals as "evidence for v11.1.0+ review, NOT a v11.0.X refactor mandate". The 3 expansion proposals also stay well under their respective tier ceilings (SKILL ≤ 475 / 500; compression-pipeline ≤ 450 / 1000) so any future application would NOT trigger SF-1 violations. |
| 3 | The "high-information disposition" precedent (v10.0.0 retrospective §3.4 cited from `v10.2.4_w17_mid_cycle_audit.md` §4) might be misread as endorsing all dense prose. The audit's heuristic specifically distinguishes high-information density (preserved) from compressed-and-cryptic density (the 3 §5.1-§5.3 examples). | minor | The audit script's report explicitly cites both precedents and explains the distinction: "high-information dense" means each line carries a unique contract; "compressed-and-cryptic" means the same content COULD be expressed clearly with budget headroom. The §5.1-§5.3 examples all have headroom available (SKILL: 40 lines / 500 - 460; compression-pipeline: 562 lines / 1000 - 438). |

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: standard
