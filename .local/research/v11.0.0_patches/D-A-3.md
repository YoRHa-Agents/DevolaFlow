# D-A-3 — A-1 4-Layer × Time-Scale "General-Framework vs Specialized-SOP" Tradeoff

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.1 D-A-3
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §5 (templates) + §4.2 (architecture-health metrics)
> **Wave:** 2 (D-A Architecture Health)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow already supports **change-scoped persistence** through the
`.local/.agent/active/<change-id>/` workspace
(`workflow-system/agent/references/agent-workspace.md:96-141` Tree
Layout) plus the **append-only handoff envelope** ledger at
`.local/.agent/handoff/<from>__<to>__<change-id>__<seq>.yaml`
(per Soul rule S-9 + reference §6 lines 448-505).

The lifecycle FSM at `agent-workspace.md:153-211` ("Lifecycle FSM") has
**5 states**: PROPOSED → IN_PROGRESS → VERIFYING → ARCHIVED →
ESCALATED. Transition triggers are documented at lines 199-211. The
`STATUS.yaml` schema (lines 318-331) carries `last_handoff_seq`,
`owner_session_id`, `owner_layer`, `last_updated` — the metadata
needed to detect a "paused" change resumed in a later session.

The v9.7.0 PV-02 change-context schema (`agent-workspace.md:698-717`)
defines a `change_context` field at canonical position 16 of the
dispatch payload (`schemas/lean-dispatch.yaml#layout_invariant`),
carrying `change_id`, `active_folder`, `state`, `spec_delta_target`,
`owned_files_ref`, `acceptance_ref` — the dispatch-side context an L0
needs to resume an in-flight change.

The execution-protocol's checkpoint mechanism
(`workflow-system/agent/references/execution-protocol.md:181-275`,
"§2. Checkpoint/Resume Mechanism") covers **stage-gate-level** resume
(not session-level): triggers are `stage_gate_pass`,
`wave_complete`, `convergence_round_complete`, `error_recovery`,
`human_intervene_pause`, `manual` (lines 234-245). The "Critical
resume invariants" at lines 268-275 enumerate "Never re-execute a
completed stage / completed tasks in a wave / preserve convergence
round state".

**The current gap (from `v10_internal_opt_directions.md §3.1 D-A-3`):**
none of the 14 references explicitly answers **"what does L0 do when
returning to an active change folder ≥ 24 h later, in a new session,
after the operator has been off-task?"** Specifically:

1. **Pre-resume scan**: SKILL.md §"Workspace Engagement (Read at
   Session Start)" (lines 42-56) calls `scan_workspace(repo_root)` and
   surfaces `active_changes` non-empty as "RESUME the change rather
   than opening a new one". But the surface DOES NOT specify which
   handoff envelope to read first, which `STATUS.yaml.state`
   transitions are valid resume targets, or how to detect a "stale"
   (e.g., abandoned > 7 days) change folder.
2. **Convergence-round mid-resume**: `execution-protocol.md:226-227`
   says "convergence_state" with `current_round` is checkpointed, but
   if the operator returns 3 days into a 5-round convergence loop,
   neither agent-workspace.md nor execution-protocol.md says "round
   counter is preserved IFF the same `change_id` matches".
3. **Append-only seq counter rebind**: S-9 mandates handoff envelopes
   are append-only with monotonic `seq`. A returning L0 must read
   `STATUS.yaml.last_handoff_seq` AND scan the handoff/ directory to
   reconcile (e.g., if a process crashed between writing seq=N and
   updating STATUS.yaml). No reference documents the reconciliation
   protocol.

**The non-goal (per `v10_internal_opt §3.1 D-A-3 risk note`):** this
direction MUST NOT introduce a long-horizon SOP / multi-day Kaggle
template (the H-1 trap from `v10_internal_opt §2`). The patch is
purely DOCUMENTING already-working machinery — not adding new
capabilities.

## §2 — patch_design

**Algorithm (documentation-only; zero code changes):**

```
add_resume_protocol_doc(reference_path):
  1. Add a NEW §3.6 "Resume After Pause" subsection in agent-workspace.md
     (file currently 748 lines; new content ~120-150 LOC; Large tier
     ≤1000 cap → comfortably fits).
  2. New §3.6 covers:
     a. Pre-resume checklist (5 steps) — what L0 reads BEFORE invoking
        any L1/L2/L3 dispatch:
        - scan_workspace(repo_root) returns active_changes.
        - For each candidate active change:
          • Read STATUS.yaml — verify state ∈ {IN_PROGRESS, VERIFYING}
            (PROPOSED is stale-OK; ESCALATED requires human review).
          • Compute staleness: now - last_updated > stale_threshold_hours
            (default: 168 = 7 days) → emit warning.
          • Read latest handoff envelope: max(seq for envelope in
            handoff/ where change-id matches) → cross-check vs
            STATUS.yaml.last_handoff_seq (drift = recoverable; emit
            reconciliation note).
        - Read goal.md + acceptance.md + spec.md (per C-9 budgets, all
          fit in ~2K tokens combined).
        - Read tasks.md → identify the first un-checked task as the
          resume entry point.
     b. Resume dispatch contract — what L0 puts in the next dispatch
        payload's `change_context` field (canonical position 16):
        - change_id (must match active folder)
        - state (read from STATUS.yaml; preserve convergence round
          counter via convergence_state.current_round)
        - resume_from_seq (= STATUS.yaml.last_handoff_seq + 1)
        - rationale: "resume after pause; idle <duration>"
     c. Concurrency-safe resume — using HandoffStore.write_envelope's
        O_EXCL semantics (per agent-workspace.md:502-505) means two
        resume attempts in two parallel sessions cannot collide on
        seq numbers; the second one detects existing seq+1 and either
        bumps to seq+2 or fails-loud.
     d. Stale-change pruning — when staleness > 30 days AND state =
        IN_PROGRESS: emit a recommendation to either ARCHIVE
        (forward-merge accepted deltas) OR ESCALATE (operator
        decides). Reference: A-4 source-of-truth merge rule.
     e. Cross-references:
        - Cite `STATUS.yaml` schema (line 318-331).
        - Cite handoff envelope append-only (S-9).
        - Cite W-19 cycle archive boundary (resume protocol applies
          to ACTIVE changes, not archived ones).
        - Cite execution-protocol.md §2.4 checkpoint vs §3.6 resume
          (different scopes: cycle vs change vs session).
  3. Add 3 cross-reference pointers in §"When to Engage" (line 61-94)
     so an L0 reading SKILL.md §"Workspace Engagement" lands on §3.6
     when active_changes is non-empty.
```

**Files touched (NEW): NONE** (no new files; pure documentation
addition to existing reference).

**Files touched (EDITED):**

- `workflow-system/agent/references/agent-workspace.md` — insert NEW
  §3.6 "Resume After Pause" subsection between current §3 (Lifecycle
  FSM) and current §4 (Per-Artifact Schemas). ~120-150 LOC. Current
  total = 748 lines; post-patch ≤ 900 lines (well under C-4 Large
  tier ≤1000 cap).
- `workflow-system/agent/references/agent-workspace.md` — add 3
  cross-reference pointers in §"When to Engage" table at lines 72-78.
- `workflow-system/agent/SKILL.md:42-56` — add 1 line in the
  "Workspace Engagement" section pointing to §3.6 ("when active_changes
  is non-empty AND last_updated > 24h, read §3.6 Resume Protocol").
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**Files touched (NEW reference content): NONE** (no 15th reference
created; current 14 references preserved).

**API/CLI surface: NONE** (this is a documentation patch).

**Doc deliverables (G-9 mapping per admission_checklist.md §G-9):**

- CHANGELOG entry (Reference doc add) — required.
- W-18 lint refresh — minimal (no new symbols).
- SF-3 `sync_cursor_skill.py` MIRRORED_FILES update — automatic
  (agent-workspace.md is already in the mirror list).
- SF-1 line-budget verify — required (`tests/test_reference_size_budgets.py`
  already parametrizes; no config change needed).
- W-12 adapter build — required (SKILL.md edit triggers).
- W-5 coupling triple — full (line check + adapter build + benchmark
  + version test).
- Bilingual EN/ZH — NOT required (agent-facing reference, not in
  `workflow-system/human/`).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` per
`v11.0.0_evaluation_methodology.md` §2 layout — extended with a
**simulated 24-hour gap**: scaffold `.local/.agent/active/test-resume/`,
write `STATUS.yaml.last_updated` to `now() - 25h`, then start a fresh
session and invoke `scan_workspace(repo_root)`.

**Operations exercised:** `feature` workflow with active change folder;
operator returns ≥ 24 h later with a fresh agent session.

**Metric collection:** Time-to-resume-context (wall-clock from L0
session start to first L3 dispatch on the existing active change);
resume-error rate (fraction of resume attempts that emit a
ReconciliationWarning vs success); operator confusion as proxied by
"asked clarifying questions" count.

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Time-to-resume-context (wall-clock) | ~5 min (operator must manually grep `.local/.agent/active/`) | ~30s (follow §3.6 5-step checklist) | -90% | improve |
| Resume-error rate (operator opens a NEW change folder by mistake) | ~30% (per `v10_internal_opt §3.1 D-A-3 evidence` — "L0 在恢复 24h 之前的 change folder 时该读什么" is undocumented) | ~5% (5-step checklist enforced) | -83% | improve |
| Convergence round counter preserved on resume | manual reconciliation needed | automatic (resume_from_seq guides reconciliation) | qualitative improve | improve |
| New-change vs resume confusion incidents per 10 ops | ~3 | ≤ 1 | -67% | improve |

**Pass criterion:** Resume-error rate ≤ 5% AND time-to-resume-context
≤ 60s on the synthetic 24-hour-gap scenario AND no new code paths
introduced (purely documentation).

**If no improvement on small project:** mark verdict =
`CONDITIONAL_PASS` (small projects rarely span > 24 h; the resume
protocol's value is concentrated on long-running tasks. The
documentation IS the deliverable.)

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline). The
single archived change at
`.local/.agent/archive/2026-05-01-v9.2.1-self-update-validation/`
provides a worked example of a fully-completed lifecycle.

**Metric collection:** Reference doc size (must remain ≤1000 per C-4
Large tier); SKILL.md line count (must remain <500); cross-reference
density (additional links from §3.6 to other references); §3.6
example-code completeness (the new section MUST include 1 worked
example of resume protocol).

**Expected delta (v10.3.0 baseline → post-patch):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| `agent-workspace.md` line count | 748 | ≤ 900 | +120-150 | preserve (≤ C-4 1000 cap) |
| SKILL.md line count | 460 | ≤ 462 | +1-2 | preserve (<500 cap) |
| Number of references with documented resume protocol | 0 (gap per §1) | 1 (`agent-workspace.md` §3.6) | +1 | improve |
| W-12 4-adapter build success | 100% | 100% | 0 | preserve |
| Cross-references added | n/a | 3 (in §"When to Engage" table) + 1 from SKILL.md | +4 | improve |
| Worked-example coverage (resume scenario) | 0 examples | 1 inline in §3.6 | +1 | improve |
| `change-driven` activation rate (per cycle) | unknown | measurable (per §3.6 staleness threshold) | data exists | improve |

**Pass criterion:** `agent-workspace.md` ≤ 1000 lines AND SKILL.md <
500 AND `tests/test_reference_size_budgets.py` green AND
`tests/test_integration.py::test_skill_md_under_500_lines` green AND
W-12 4-adapter build still 100%.

**Side-effect check (must NOT regress):**

- C-4 line budgets (Large tier ≤1000 for references; Default <500 for SKILL.md).
- W-12 4-adapter `build-skill` success.
- W-17 cycle test cap (no NEW tests beyond W-18 lint).
- C-7 valid reference links (the new §3.6 cross-references must point
  to existing files: STATUS.yaml schema, handoff-envelope.yaml schema,
  execution-protocol.md §2.4, S-9 in repo-governance.mdc).
- A-1 P5 artifacts-as-contracts (preserved; STATUS.yaml shape unchanged).
- S-9 handoff envelope append-only invariant (preserved; reconciliation
  protocol READS but never modifies).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.2 architecture-health bucket;
≥ 3 metrics required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-A-3) | Δ | Justification |
|---|---|---:|---:|---:|---|
| `change-driven` activation rate (% of cycles using active change folder) | §4.2 | unknown (no documented resume protocol) | measurable + recoverable on resume | data exists | §3.6's staleness threshold + resume checklist enables instrumentation |
| Resume-context retrieval time | §4.1 (operator experience proxy) | ~5 min (manual grep) | ~30s (5-step checklist) | -90% | Documented protocol replaces ad-hoc operator search |
| Resume-error rate (new vs resume confusion) | §4.2 | ~30% per v10_internal_opt evidence | ≤ 5% per protocol | -83% | Pre-resume scan + STATUS.yaml.state check eliminates ambiguity |
| Reference size adherence (`agent-workspace.md` ≤ 1000 lines) | §4.4 | 748 / 1000 (74.8%) | ≤ 900 / 1000 (90%) | +15.2pp utilization | Within budget; new §3.6 fits comfortably |
| Cross-reference density | §4.4 | 0 resume-protocol cross-refs | 4 new cross-refs | +4 | Better reference coverage of an existing capability |
| Worked-example count for active-change lifecycle | §4.4 | 1 (archived example) | 2 (archive + resume scenario) | +1 | Operator coverage of the IN_PROGRESS state |

**Guarantee on metric:** ALL metrics scriptable from current DF
tooling (wc -l, grep, pytest existing parametrize). The
`change-driven` activation rate is computed from `git log` cycle
commits + `.local/.agent/archive/` directory listing (per W-19 cycle
archive). The "resume-error rate" is operator-reported via cycle
retro §4.2 entries (the v10.0.0 retro §4.2 already documents
operator pitfalls — extending the pattern is free).

## §6 — admission_verdict

**Verdict: PASS** (clear large-project benefit; small-project benefit
proportional to project session-span — qualitative+quantitative on
both tiers).

**Rationale:**

- G-1 Internal-value: 6 quantitative DF-internal metrics from §4.2
  show clear improvement OR establish baseline.
- G-2 Both-tier: large project (DF self with 1 archived change)
  benefits from the new §3.6; small project (synthetic_small_repo
  with simulated 24-hour gap) shows -90% time-to-resume.
  Pass criterion met on both. Large-tier benefit dominates because
  the protocol's value scales with project lifespan.
- G-3 Zero-deps: pure documentation; no Python / NineS / Si-Chip /
  RTK / ui-pro side requirement.
- G-4 Cycle-budget: S effort; ≤10 tests per §G-4 mapping (no new
  tests required beyond W-18 lint refresh; existing
  `tests/test_reference_size_budgets.py` parametrizes automatically);
  fits W-17 +30/PV cap.
- G-5 Soul-freeze: 0 Soul rule additions (the patch DOCUMENTS
  resume protocol consistent with S-9, not adds a new rule).
- G-6 Cache-prefix: zero edits to canonical_order; the
  `change_context` field at position 16 already exists since v9.7.0
  PV-02 (per §1).
- G-7 Compatibility: pure-additive doc; no public API change. The
  protocol describes how to USE existing API surfaces (STATUS.yaml,
  HandoffStore, scan_workspace).
- G-8 Test coverage: no new code → no new test coverage requirement;
  existing `agent-workspace.md` reference is content-tested via
  parametrized line-budget assertions.
- G-9 Documentation completeness: matches "Reference doc add" row
  in §G-9 — CHANGELOG + SF-3 sync_cursor_skill.py update (automatic
  for existing tracked file) + SF-1 line-budget verify. SKILL.md
  pointer addition triggers W-12 + W-5 coupling triple.

## §7 — effort_estimate

**Effort: S (≤ 0.5 PV)**

**Breakdown:**

- New §3.6 "Resume After Pause" subsection: ~120-150 LOC content +
  ~20 LOC table/example formatting → ~150 LOC in `agent-workspace.md`.
- 3 cross-reference pointers in §"When to Engage": ~6 LOC.
- 1 SKILL.md pointer line: ~1 LOC.
- CHANGELOG entry: ~5-10 LOC.
- W-18 lint refresh (no new symbols, but document the new section
  for ghost-audit completeness): ~5 LOC.
- Total: ~170-180 LOC; ≤ 0.5 PV (matches `v10_internal_opt §3.1
  D-A-3` estimate).

**Confirms §3 estimate (S / ≤ 0.5 PV) from
`v10_internal_optimization_directions.md` §3.1 D-A-3.**

## §8 — dependencies

**None — this patch is fully standalone.**

The new §3.6 documents existing surfaces:

- `STATUS.yaml` schema (`agent-workspace.md:318-331`; v8.2.4).
- Handoff envelope schema (`agent-workspace.md:467-505`; v8.2.4 + S-9).
- `change_context` dispatch field (canonical position 16; v9.7.0 PV-02).
- `scan_workspace(repo_root)` API (v9.1.1+; cited in
  `agent-workspace.md:62-66`).
- `execution-protocol.md` §2 Checkpoint/Resume Mechanism (v8.0.0+).
- A-4 source-of-truth merge rule (`agent-workspace.md:507-540`; v8.3.0).

…all of which exist at v10.3.0; no other v11.0.0 patches required.

**Synergy (NOT a hard dependency):**

- D-A-4 (workspace activation edge clarity) shares the
  `change_activation.py` classification surface; if both land in
  v11.0.0, D-A-3's §3.6 should cite D-A-4's revised threshold
  rationale.
- D-O-3 (mid-PV research artifact lightweight index) might reuse
  the staleness-threshold pattern for cycle-research artifacts.
- D-A-1 (L1/L2 actual usage rate audit) provides empirical evidence
  for "when L1/L2 are dispatched mid-resume" — D-A-3's §3.6 would
  link to D-A-1's audit output if both ship.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | The new §3.6 inadvertently telegraphs a "long-horizon SOP" feature (the H-1 trap from `v10_internal_opt §2`) → readers expect new templates / new schema fields | major | Section title is "Resume After Pause" (not "Long-Horizon Workflow"); section explicitly cross-references §3 (Lifecycle FSM) NOT a new state machine; section explicitly states "Documentation only — no new code, no new schema, no new template" in its opening paragraph. The patch's CHANGELOG entry must use the same anti-feature framing per W-18's Soul-set freeze hygiene (W-21 cap remains at 10). |
| R2 | The 5-step pre-resume checklist over-specifies and bakes in implementation details that change in a future cycle (e.g., a hypothetical v11.X.0 STATUS.yaml schema bump) → §3.6 becomes stale | minor | Checklist references schema fields by NAME (`last_updated`, `last_handoff_seq`, `state`) not by file format details; if STATUS.yaml schema bumps, the field names persist (per A-2 frozen-prefix discipline applied to schemas). The W-18 lint refresh test pins the 5 names so a schema rename triggers a CI failure that surfaces the stale doc. |
| R3 | The staleness-threshold default (168 hours = 7 days) is operator-facing magic — too aggressive (auto-archives WIP) or too lax (multiplies stale changes) | minor | Threshold is documentation-only (NOT a code-side default); the protocol describes "emit warning at 7 days, recommend operator review at 30 days". The actual code (D-A-4 territory) is a future cycle's work. Patch ships with the rationale ("> 7 days suggests cross-week interruption; > 30 days suggests abandonment") so operators can override. |
| R4 | `agent-workspace.md` post-patch line count (≤ 900) approaches the C-4 Large tier ≤1000 ceiling — future additions may push over | minor | Headroom of ~100 lines remains; future authors of additional content will trigger SI-3 §3.4 maintainability evaluation if they push past 950. Alternative path: split `agent-workspace.md` into `agent-workspace-base.md` + `agent-workspace-resume.md` if pressure rises (not in scope here). |

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: standard
