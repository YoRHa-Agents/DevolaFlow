---
id: "agent/references/artifact-quality"
version: "1.0.0"
purpose: >
  EVIDENCE-ONLY rubric for the L3 task artifact itself — what an excellent
  single-task deliverable looks like and what observable evidence the L3
  Task Agent must emit before its first StatusReport. Closes gap G-004
  (v14.2.0 SI-1 §2.1, source F-P1-2) under the v15-ADR-007 doctrine split:
  L3 emits evidence at v14.3.0; numeric scoring stays L0-side and lands
  v15.0.0. Companion to references/task-quality-score.md (the L0-only
  rubric for the OPERATOR REQUEST, never the artifact).
triggers:
  - "authoring an L3 deliverable and self-verifying before StatusReport"
  - "building self_check / ac_results / diff_stats evidence blocks"
  - "L0 VERIFY step checking evidence instead of re-deriving from disk"
  - "artifact quality rubric"
  - "L3 self-verify checklist"
tier: 2
token_estimate: 2600
dependencies:
  - "agent/SKILL.md"
  - "agent/references/execution-protocol.md"
  - "agent/references/behavioral-guidelines.md"
last_updated: "2026-06-11"
---

# Artifact Quality — Evidence Rubric (L3 emits evidence; L0 judges)

## §1 Doctrine — Evidence, Not Scores

**L3 MUST NOT compute or report numeric quality scores — this rubric defines
EVIDENCE.** The doctrine is the two-phase split ratified in
`.local/research/adr/v15-ADR-007-artifact-evidence-vs-scoring-doctrine.md`:

1. **v14.3.0 (evidence phase — THIS document)**: the L3 Task Agent emits
   falsifiable evidence about its own artifact — per-AC verdicts from
   actually-run commands, diff statistics, behavioral-guideline attestations.
   Verdicts and digests are **attestations, not numbers the L3 invents**.
2. **v15.0.0 (scoring phase)**: L0 computes the holistic artifact score FROM
   the report evidence fields. Holistic judgment stays L0-side permanently.

This preserves — and does NOT invert — the v12.1–12.3 closure: subagent
reports carry no `quality_score` field, enforced at runtime by the
`src/devolaflow/lifecycle/reject_subagent_quality_score.py` hook (v12.2.0
PV-04; extended at v14.3.0 to reject any L3-emitted holistic score inside the
new evidence blocks). The rationale is self-assessment bias: an L3 grading its
own work produces a number L0 cannot trust, while an L3 reporting *"AC-001
PASS, digest `3 passed in 0.41s`"* produces a claim L0 can spot-check.

**Boundary with the request rubric**: `references/task-quality-score.md`
scores ONLY the user's original request ("Never score subagent outputs") and
loads at workflow CLOSE. THIS reference covers the opposite axis — the L3
deliverable — and loads at task execution time. The two never overlap.

## §2 The Four Excellence Dimensions

Each dimension is defined by concrete, checkable criteria. "Checkable" means:
a command was run and its output exists, a diff was measured, or a named rule
was walked. Prose self-praise is not evidence.

### §2.1 Correctness

The artifact does what the dispatch asked, provably.

| Criterion | Checkable form |
|---|---|
| Every `acceptance_criteria_v2` entry has a verdict | `ac_results` rows populated from ACTUALLY-RUN `verification_cmd`s (never predicted output) — see `references/execution-protocol.md` §15 |
| Tests pass | Verbatim pass/fail counts from the suite run (`metrics.pass` / `metrics.fail`), per C-3 — never paraphrase metric values |
| No regressions | Pre-existing tests in scope still green; any newly-red pre-existing test is reported as a blocker, not omitted |
| Legacy AC fallback | When no `acceptance_criteria_v2` block exists, each legacy `acceptance_criteria` string maps to one observable evidence line (see §4) |

### §2.2 Minimal Diff

Surgical scope discipline — the smallest change that satisfies the AC.

| Criterion | Checkable form |
|---|---|
| Scope tier respected | Edits stay inside the dispatched `surgical_scope` tier (`line` / `function` / `module`) per `BG-003` (severity: blocker) — see `references/behavioral-guidelines.md` Rule 3 |
| No writes outside owned files | Diff filename set ⊆ `owned_files` (S-8; trivial single-file < 20-line waiver applies) |
| Diff proportionate to task size | `diff_stats` (`{files, insertions, deletions}`) consistent with the SKILL.md task-sizing contract (max 6 writable files, ~50–300 lines changed); a 2,000-line diff for a 1-sentence task is a finding, not a flex |
| No drive-by edits | Zero opportunistic refactors, reformat-only hunks, or unrelated cleanups outside the AC; required out-of-scope edits escalate via `ScopeEscalation` BEFORE editing (BG-003) |

### §2.3 Test Evidence

New or changed behavior is covered, and tests ran before the report.

| Criterion | Checkable form |
|---|---|
| New/changed behavior covered | Each behavioral change names the test(s) exercising it; "tests can be added later" is a Rationalization-Prevention entry, not an option |
| Coverage floor held | `metrics.cov` ≥ 80% for new/modified Python modules per `S-3`; new modules > 0% before merge |
| Test-then-report ordering | The suite run happens BEFORE the StatusReport is authored; the report carries the run's verbatim counts, never a forecast |
| Bounded execution | Every verification shell call sets explicit timeouts per SKILL.md §"Subagent Hang Prevention" (no unbounded runs) |

### §2.4 Convention Adherence

The artifact reads like the repo wrote it.

| Criterion | Checkable form |
|---|---|
| Repo idioms + naming followed | Mirrors sibling modules/files (imports, naming, file layout, frontmatter conventions); deviations carry an inline rationale |
| Lint/format clean | `ruff check` + `ruff format --check` (or repo equivalent) exit 0 on touched files — verbatim exit status, not "should be fine" |
| No new abstractions without justification | The 3-question over-engineering audit per `BG-002` (abstractions for a single use case / unconsumed config knobs / "in case" code) — each YES is a finding |
| Novel patterns surface as conflicts | When the artifact must diverge from an established pattern, the conflict is surfaced (BG-006/BG-007 attestations), not silently embedded |

## §3 Evidence Emission Map

Each dimension lands in a specific lean-report transport field (the
`self_check` / `ac_results` / `diff_stats` blocks are additive
`schemas/lean-report.yaml` fields shipping in the same v14.3.0 release per
G-002/G-003; the report side has NO `layout_invariant:`, so additions are
P6-safe).

| Dimension | Transport field | Shape (bounded per C-2 lean format) |
|---|---|---|
| Correctness — per-AC verdicts | `ac_results` | `[{id, verdict, cmd_output_digest}]` — digest is a verbatim tail-line of the actually-run `verification_cmd`, NOT a transcript |
| Correctness — test counts | `metrics.pass` / `metrics.fail` / `metrics.findings` | numeric-only, verbatim per C-3 |
| Minimal diff — measured scope | `diff_stats` | `{files, insertions, deletions}` from the real diff |
| Minimal diff + convention — BG attestations | `self_check.bg_attestations` | `[{id, verdict, evidence}]` for the dispatched BG rules (e.g. BG-002, BG-003, BG-006, BG-007) |
| Test evidence — coverage | `metrics.cov` | float, from the actual coverage run |
| Plan + goal anchoring | `self_check.plan_artifact` / `self_check.goal_anchor` | path/one-liner giving BG-001/BG-004 their transport |

**Doctrine guard**: none of these fields carries a holistic number. The
`reject_subagent_quality_score` hook rejects any L3-emitted score in the new
blocks exactly as it rejects the top-level `quality_score` key.

### §3.1 Worked example (lean StatusReport evidence blocks)

A SIMPLE-tier impl task with two structured criteria. Every value below is
verbatim-extracted from a real command run or diff measurement (C-3):

```yaml
self_check:
  plan_artifact: ".local/.agent/active/jwt-middleware/tasks.md#T04"
  goal_anchor: "add JWT auth middleware; AC-001/AC-002 green; no regressions"
  bg_attestations:
    - { id: BG-002, verdict: PASS, evidence: "0 YES of 3 — no new abstractions" }
    - { id: BG-003, verdict: PASS, evidence: "diff filenames ⊆ owned_files (module tier)" }
ac_results:
  - { id: AC-001, verdict: PASS, cmd_output_digest: "12 passed in 1.84s" }
  - { id: AC-002, verdict: FAIL, cmd_output_digest: "AssertionError: expected 401, got 500" }
diff_stats: { files: 3, insertions: 184, deletions: 6 }
```

What makes this GOOD evidence: each digest is a tail-line an L0 can re-run
and compare; the BG attestations name their rule ids and the check walked;
`diff_stats` lets L0 sanity-check scope without reading the diff. The AC-002
FAIL row is *kept* — per §5, an honest red row beats a fabricated green one.

The BAD-evidence anti-patterns (each one is itself a finding):

| Anti-pattern | Why it fails the rubric |
|---|---|
| `cmd_output_digest: "should pass"` | Predicted, not run — violates the §1 doctrine and S-5 |
| `verdict: PASS` with no digest | Unverifiable claim; L0 must re-derive from disk (the exact gap G-003 closed) |
| `evidence: "code quality is excellent, 9/10"` | A holistic self-score smuggled into an evidence field — rejected by the doctrine hook |
| `diff_stats` omitted on a 40-file diff | Hides a scope breach the BG-003 tier check would flag |

## §4 Self-Verify Checklist (walk BEFORE the first StatusReport)

Ordered; each item maps to a §2 dimension. Protocol position and bounded
execution rules: `references/execution-protocol.md` §15 "L3 Self-Verify".

1. **[Correctness]** Re-read the dispatch's acceptance criteria verbatim (no
   paraphrasing per C-3).
2. **[Correctness]** Run every `acceptance_criteria_v2.verification_cmd`
   (bounded); record one `ac_results` row per criterion with verdict +
   `cmd_output_digest`. No AC v2 block present → map each legacy criterion to
   one observable evidence line instead.
3. **[Correctness]** Run the relevant test suite; capture verbatim pass/fail
   counts. Any newly-red pre-existing test = regression → fix or report as
   blocker.
4. **[Test evidence]** Confirm every new/changed behavior names a covering
   test; confirm `metrics.cov` ≥ 80% on touched Python modules (S-3).
5. **[Minimal diff]** Measure the diff; populate `diff_stats`. Compare
   against the task-sizing contract (~50–300 lines, ≤ 6 writable files).
6. **[Minimal diff]** Verify diff filename set ⊆ `owned_files` and the
   `surgical_scope` tier held (BG-003); confirm zero drive-by edits.
7. **[Convention]** Run lint + format checks on touched files; record exit
   status.
8. **[Convention]** Walk the BG-002 3-question over-engineering audit; record
   each YES as a finding in `self_check.bg_attestations`.
9. **[Convention]** Confirm repo idioms followed (naming, layout, sibling
   parity); surface any deliberate divergence as a BG-006/BG-007 attestation.
10. **[All]** Populate `self_check` (plan_artifact, goal_anchor,
    bg_attestations) and re-check: does every claim in the draft report trace
    to a command output, diff measurement, or named-rule walk?
11. **[Honesty]** Anything red, missing, or skipped → apply §5 before
    reporting. Maximum 2 self-fix iterations, then report honestly (P4).

## §5 Failure Honesty (when evidence is missing or red)

Per `S-5` (No Silent Failures): **never claim green without command output.**
A claimed-green criterion with no digest is itself a violation — worse than a
reported-red one, because it poisons the L0 evidence channel.

| Situation | Required report behavior |
|---|---|
| A `verification_cmd` FAILED after ≤ 2 self-fix iterations | `ac_results` row carries `verdict: FAIL` + the verbatim failing digest; overall `rs: DONE_WITH_CONCERNS` or `BLOCKED` per the result-status protocol — never `DONE` |
| A `verification_cmd` could not be RUN (missing tool, sandbox limit, timeout) | `verdict: NOT_RUN` + the reason verbatim; do NOT substitute a prediction for the run |
| Evidence for a criterion cannot exist yet (depends on a sibling task / release-close step) | Report the dependency explicitly in `issues.deferred` with the owning task named; do not mark the criterion green |
| Coverage below the S-3 floor | Report the real number; propose the gap as `issues.warnings` or a blocker per the gate profile — never round up |
| Scope had to widen beyond `owned_files` / the BG-003 tier | `ScopeEscalation` BEFORE the edit; if discovered after, report the violation verbatim as a blocker finding |
| Score stagnation: 2 self-fix iterations with no improvement | Stop iterating; escalate upward per P4 (Task → Wave → Stage → Project → Human) with the evidence trail attached |

**Escalation triggers** (emit `NEEDS_CONTEXT` or `BLOCKED` instead of a green
report): ambiguous AC that two runs interpret differently; verification
requiring credentials/resources the L3 lacks; any criterion whose only
possible "evidence" would be the L3's own opinion.

## Cross-references

* `references/execution-protocol.md` §15 "L3 Self-Verify" — protocol position,
  bounded execution, max-2-iteration contract
* `references/task-quality-score.md` — the OTHER rubric: L0-only scoring of
  the operator request; never the artifact
* `references/behavioral-guidelines.md` — BG-001..BG-007 definitions and the
  severity/enforcement matrix this rubric's attestations cite
* `schemas/lean-report.yaml` — `self_check` / `ac_results` / `diff_stats`
  transport blocks (additive, v14.3.0)
* `src/devolaflow/lifecycle/reject_subagent_quality_score.py` — the runtime
  doctrine guard
* `.local/research/adr/v15-ADR-007-artifact-evidence-vs-scoring-doctrine.md`
  — the ratified evidence-vs-scoring split this reference implements
