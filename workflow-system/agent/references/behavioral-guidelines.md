---
id: "agent/references/behavioral-guidelines"
version: "1.0.0"
purpose: >
  L3 Task Agent behavioral guidelines (think_first, simplicity_check,
  surgical_scope, goal_loop) — the 4 Karpathy-derived primitives that
  shape Agent execution discipline. Loaded selectively into the L3
  dispatch payload via the top-level ``behavioral_guidelines`` field
  declared in ``schemas/lean-dispatch.yaml`` (canonical position 14).
triggers:
  - "L3 Task Agent execution"
  - "behavioral guideline injection"
  - "Karpathy behavioral primitives"
  - "code quality discipline"
tier: 2
token_estimate: 1100
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-04-23"
---

# Behavioral Guidelines (L3 Task Agent)

L3 Task Agents inherit four behavioral primitives from the dispatch payload's
top-level ``behavioral_guidelines`` field. The four rules are derived from the
Karpathy nano-agent skill set (https://github.com/forrestchang/andrej-karpathy-skills)
and adapted to DevolaFlow's 4-layer hierarchy. Each rule is opt-in per profile
(see ``workflow-system/agent/context_profiles.yaml``), severity-classified, and
self-checkable so a Task Agent can verify compliance without invoking Review.

## Field Shape

```yaml
behavioral_guidelines:
  think_first: bool       # Plan-before-code discipline (Karpathy "Think First")
  simplicity_check: bool  # Reject over-engineering (Karpathy "Simplicity First")
  surgical_scope: str     # 'line' | 'function' | 'module' (Karpathy "Surgical Edits")
  goal_loop: bool         # Re-anchor to user intent each round (Karpathy "Goal-Driven")
```

The field is OPTIONAL in the dispatch payload. When absent, L3 agents fall
back to the v7.x default (no behavioral injection — byte-identical to the
v7.x dispatch shape and preserves the v7.0.0 cache-layout golden baseline).
When present, the dispatcher's ``select_context()`` helper selectively loads
the matching rule sections from this file into the L3 task agent context.

## Rule Application Matrix

| Profile     | think_first | simplicity_check | surgical_scope | goal_loop | Rationale |
|-------------|-------------|------------------|----------------|-----------|-----------|
| trivial     | false       | false            | line           | false     | < 20 line edit; full ceremony unwarranted |
| simple      | true        | false            | function       | false     | 1-3 file scope; require plan-first |
| standard    | true        | true             | function       | false     | 3-10 file scope; add over-engineering check |
| complex     | true        | true             | module         | true      | 10+ files; re-anchor goal each round |

Profile authors override per-profile defaults via
``context_profiles.yaml#profiles.<name>.behavioral_guidelines``. Missing
keys inherit the matrix above per complexity tier classification.

## Rule 1 — think_first

**id**: `BG-001` | **severity**: warn | **applies when**: `think_first=true`

Before producing any code edit, the L3 Task Agent MUST surface an explicit
plan to the dispatcher. The plan is captured in the StatusReport's
``plan_artifact`` field (≤ 5 bullets, each ≤ 20 words) and rendered before
the first ``Write`` / ``StrReplace`` / ``Shell`` tool call.

**Rendered guidance** (injected into L3 dispatch when active):

> Before any source modification, emit a numbered plan describing: target
> files, key abstractions you will introduce or change, the acceptance
> criteria your changes will satisfy, and any assumptions that block work.
> One-line rationale per bullet. Reject the temptation to "just start
> coding" — plan friction is plan correctness.

**Self-check questions**:

1. Did I list every file I intend to write before the first edit?
2. Did I name every new function / class / data type I am introducing?
3. Did I cite the acceptance criterion each change addresses?

**When to skip**: Single-file ≤ 20-line trivial fixes (P1 trivial exception).

## Rule 2 — simplicity_check

**id**: `BG-002` | **severity**: warn | **applies when**: `simplicity_check=true`

Before merging a candidate solution, the L3 Task Agent MUST run a 3-question
over-engineering audit. Each YES is a candidate WARNING in the StatusReport
findings list (severity=major if 2+ YES, blocker if all 3 YES).

**Rendered guidance** (injected into L3 dispatch when active):

> Audit your solution against three over-engineering smells before commit:
> (1) Did I introduce abstractions (classes, factories, registries) for a
> single use case? (2) Did I add configuration knobs nobody asked for?
> (3) Did I write code that exists "in case" rather than "because"? Each
> YES is a finding. The minimal solution that passes acceptance criteria
> wins; cleverness without justification loses.

**Self-check questions**:

1. Could I delete this abstraction and inline the call site without harm?
2. Is every new config field consumed by a passing test?
3. Did I write code paths that have no AC reference?

**When to skip**: Hotfix profile (urgency outweighs purity).

## Rule 3 — surgical_scope

**id**: `BG-003` | **severity**: blocker | **applies when**: `surgical_scope` set

Limits the file-system blast radius of a single L3 task. The value is one
of three tiers; violation classifies as blocker because it directly breaches
the wave-level disjoint-ownership invariant (P2).

| Value     | Constraint | When applied | Verifier |
|-----------|------------|--------------|----------|
| `line`    | Edits restricted to declared line ranges within owned files | Trivial-tier hotfix | Future v8.2.0 work — currently aliased to ``function`` |
| `function`| Edits restricted to declared function bodies in owned files | Standard impl / refactor | Walk diff hunks; reject hunks that cross declared function boundaries |
| `module`  | Edits restricted to ``owned_files`` set; no out-of-scope writes | Complex multi-wave impl | Compare diff filename set against ``owned_files`` |

**Rendered guidance** (injected into L3 dispatch when active):

> Your edits MUST stay within the declared ``surgical_scope`` tier. A
> diff hunk that escapes the tier is a blocker finding, not a stylistic
> choice. If you discover an out-of-scope edit is required, surface a
> ``ScopeEscalation`` exception to the wave agent rather than silently
> widening the diff.

**Self-check questions**:

1. Did every diff hunk stay inside an owned file?
2. Did every diff hunk stay inside the declared function (when applicable)?
3. Did I escalate any required scope expansion BEFORE editing?

**Note** (v8.2.0 PV-04): `line`-tier verification is implemented. When the
resolved `behavioral_guidelines` block carries `surgical_scope='line'`,
`_select_behavioral_sections` augments the dispatch context with the
verbatim list of criteria documented under
[Line-Level Behavioral Criteria](#line-level-behavioral-criteria). The
v8.0.0 P-08 deferred AC #2 closes here; `function` and `module` tier
behaviour stays byte-identical to v8.0.0-p08 (R5 discipline).

## Rule 4 — goal_loop

**id**: `BG-004` | **severity**: warn | **applies when**: `goal_loop=true`

In multi-round convergence work the L3 Task Agent MUST re-anchor each round
to the original user goal verbatim before consuming the prior round's
findings. This counters "goal drift" where successive rounds optimise for
findings instead of intent.

**Rendered guidance** (injected into L3 dispatch when active):

> At the head of each round (round_num >= 2), restate the original user
> request VERBATIM in your StatusReport's ``goal_anchor`` field. Then read
> the prior round's findings. If the findings would push your work AWAY
> from the goal anchor, surface a ``GoalDriftWarning`` finding rather
> than complying.

**Self-check questions**:

1. Did I quote the original user request word-for-word at round start?
2. Did I cross-check each new finding against the goal anchor?
3. Did I flag findings that conflict with the goal rather than silently
   complying?

**When to skip**: Single-round (round_num == 1) tasks; the goal is implicit
in the dispatch and re-anchoring adds no signal.

## Token Cost

Each rule's rendered guidance is bounded at ≈ 30 lines / ≈ 120 tokens. All
four rules together total ≈ 480 tokens — under 5 % of the L3 8 K budget,
sized so they never displace `critical` SKILL.md sections (verified by
``tests/test_behavioral_guidelines.py::test_behavioral_block_token_bounds``).

## Backward Compatibility

When the dispatch payload omits ``behavioral_guidelines``,
``select_context()`` returns a result whose ``assembled_text`` is
byte-identical to the v7.x output. This preserves the v7.0.0 layout
golden baseline (``benchmarks/devolaflow_context/baselines/layout_invariant_v7.0.0.yaml``)
and the v7.3.0 baseline (``...v7.3.0.yaml``). The schema bump
``layout_invariant.version: 2 → 3`` is purely additive per ADR-001 §2.

## Line-Level Behavioral Criteria

Added in v8.2.0 PV-04. Loaded verbatim by
`_select_behavioral_sections` whenever the resolved behavioural block
sets `surgical_scope='line'`. Each criterion below is a self-checkable
rule that the L3 Task Agent MUST audit per touched line before commit;
violations classify as a finding (severity follows BG-003 = blocker).

- LL-001 per-line max length: every touched line stays at or below the
  project's configured ruff/black line-length (default 100 chars); a
  single touched line exceeding the ceiling is a blocker finding.
- LL-002 per-line complexity delta: radon cyclomatic-complexity delta
  per touched line MUST be `< +1`; a single touched line that bumps
  the enclosing function's cc by `+1` or more must be split or
  escalated via `ScopeEscalation`.
- LL-003 per-line cohesion: every touched line MUST belong to a
  single logical change (no piggyback edits — e.g. a line that both
  fixes the bug AND renames a local must be split into two diff
  hunks).
- LL-004 declared-range adherence: every touched line MUST fall inside
  a line range explicitly named in the task spec's
  `owned_files[*].line_ranges` field; lines outside the declared
  ranges are blocker findings, not stylistic choices.
- LL-005 verbatim-line preservation: lines NOT explicitly named in the
  task spec MUST remain byte-identical (no whitespace normalisation,
  no quote-style flips, no import reordering); preserves CO-2 / C-3
  verbatim-extraction discipline at the diff layer.

These criteria compose with BG-003 — a `line`-scope task inherits BG-003
(diff hunks stay within the tier) AND each of LL-001..LL-005. Failing
any criterion is a blocker finding per the BG-003 severity classification.

## S-8 Composition Rule

`surgical_scope` (BG-003) interacts directly with Soul Rule **S-8** ("No
Writes Outside Active Change Owned Files" per `AGENTS.md`). When the
dispatch payload carries BOTH a `change_context.owned_files_ref` AND a
`behavioral_guidelines.surgical_scope` value, the L3 Task Agent MUST
honour the **stricter** of the two:

| `surgical_scope` | `change_context.owned_files_ref` present | Effective constraint |
|------------------|------------------------------------------|----------------------|
| `line` | YES | Edits restricted to declared line ranges within owned_files (S-8 ∩ BG-003 line tier) |
| `function` | YES | Edits restricted to declared function bodies in owned_files (S-8 ∩ BG-003 function tier) |
| `module` | YES | Edits restricted to owned_files (S-8 ≡ BG-003 module tier) |
| (any) | NO (free-floating) | BG-003 alone applies; no S-8 enforcement |

Violations classify per BG-003 severity (= **blocker**). The
`lifecycle/check_file_ownership` hook (v8.2.6 forward-defined) enforces
S-8 at write time; in `mode: lite` it warns + logs, in `mode: full` (or
STRICT) it blocks + escalates per P4. Trivial-tier exception (single file
< 20 lines per S-1 / P1) applies symmetrically — both S-8 and BG-003 are
waived for trivial edits.

## Severity Matrix

| Rule ID | Field / Tier | Severity | On-violation behaviour |
|---------|--------------|----------|------------------------|
| BG-001 | `think_first=true` | warn | Append finding to StatusReport `findings`; no block |
| BG-002 | `simplicity_check=true` (1 YES) | minor | Append finding |
| BG-002 | `simplicity_check=true` (2 YES) | major | Append finding + reduce score |
| BG-002 | `simplicity_check=true` (3 YES) | blocker | Append finding + halt commit |
| BG-003 | `surgical_scope` (any tier) | blocker | Halt commit; require ScopeEscalation |
| BG-004 | `goal_loop=true` (round ≥ 2) | warn | Append `GoalDriftWarning` finding |
| LL-001 | per-line max length | blocker | (line tier) Halt commit |
| LL-002 | per-line cyclomatic delta < +1 | blocker | (line tier) Halt commit |
| LL-003 | per-line cohesion (single logical change) | blocker | (line tier) Halt commit |
| LL-004 | declared-range adherence | blocker | (line tier) Halt commit |
| LL-005 | verbatim-line preservation | blocker | (line tier) Halt commit |
| S-8 | owned_files write | blocker (mode: full) / warn (mode: lite) | Block + escalate per P4 |

The matrix is the single-source-of-truth for L3 self-audit; agents MUST
classify findings using this exact severity wording (no inflation, no
deflation per CO-2 verbatim-extraction discipline).

## v8.2.x Primitive References

The behavioral primitives compose with the runtime primitives shipped in
the v8.x cycle. Each cross-link below identifies the runtime surface that
backs the prompt-side guidance:

| Primitive | Runtime surface | Cycle |
|-----------|-----------------|-------|
| `surgical_scope='line'` verifier | `src/devolaflow/task_adaptive_selector.py:_load_line_level_criteria` | v8.2.0 PV-04 |
| `select_context()` integration | `src/devolaflow/task_adaptive_selector.py:_select_behavioral_sections` | v8.0.0 P-08 |
| `change_context.owned_files_ref` honoring | `src/devolaflow/agent_workspace/change.py::ChangeStore` | v8.2.5 PV-05 |
| Append-only handoff envelope (S-9) | `src/devolaflow/agent_workspace/handoff.py` | v8.2.4+ |
| `lifecycle/check_file_ownership` hook | `src/devolaflow/lifecycle/` (forward-defined v8.2.6) | v8.2.6 |
| Plan-mode prompt-side embedding (S-10) | `references/plan-mode-enforcement.md` (forward-defined v8.4.4 PV-04) | v8.4.4 |
| Reinforcement injection | `src/devolaflow/gate/reinforcement.py::merge_reinforcement_into_dispatch` | v8.0.0 P-04 |
| Token-budget breaker | `src/devolaflow/gate/budget.py::TokenBudgetBreaker` | v8.0.0 P-03 |

Operators triaging behavioral-rule violations consult the runtime surface
for the canonical implementation; the prompt-side guidance documented
above is the L3 contract surface.

## See Also

- ``schemas/lean-dispatch.yaml#layout_invariant`` (canonical position 14)
- ``workflow-system/agent/context_profiles.yaml`` (per-profile defaults)
- ``src/devolaflow/task_adaptive_selector.py:_select_behavioral_sections``
- ``src/devolaflow/task_adaptive_selector.py:_load_line_level_criteria`` (PV-04)
- ``.local/research/v8.0.0_patch_plan.md`` §3 P-08
- ``.local/research/v8.2.0_patch_plan.md`` §3 PV-04
- ``https://github.com/forrestchang/andrej-karpathy-skills`` (upstream rules)
