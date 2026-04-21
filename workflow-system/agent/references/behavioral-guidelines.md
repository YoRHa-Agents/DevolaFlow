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
last_updated: "2026-04-21"
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

**Note** (v8.0.0): `line`-tier verification is deferred to v8.2.0; in v8.0.0
it is treated as `function`-tier per AC #2 of patch P-08.

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

## See Also

- ``schemas/lean-dispatch.yaml#layout_invariant`` (canonical position 14)
- ``workflow-system/agent/context_profiles.yaml`` (per-profile defaults)
- ``src/devolaflow/task_adaptive_selector.py:_select_behavioral_sections``
- ``.local/research/v8.0.0_patch_plan.md`` §3 P-08
- ``https://github.com/forrestchang/andrej-karpathy-skills`` (upstream rules)
