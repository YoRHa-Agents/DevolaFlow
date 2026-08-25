# Agent Workspace Schemas — Reference

> Patch slot: **v8.2.4** (`feat/v8.3.0-pv04-agent-workspace-schemas`).
> Closes gaps **C-002, M-003, M-005** from `docs/cycle-archive/v8.3.0/v8.3.0_gap_analysis.md`.
> Authoritative spec: [`docs/cycle-archive/v8.3.0/design/v8.3.0_design.md` §2](../docs/cycle-archive/v8.3.0/design/v8.3.0_design.md).

Human-readable companion to the 10 artifact schemas (plus the index) under
[`schemas/agent-workspace/`](../schemas/agent-workspace/). Use this when
authoring `.local/.agent/active/<change-id>/` artifacts by hand between the
v8.2.3 scaffold and the v8.2.5 Python API + CLI lint. Schemas are declarative
YAML in the existing DevolaFlow convention (`design_reference` + `schema_name`
+ `instance_top_level_required` + `fields`); validation runs via
`yaml.safe_load` + structural assertions in
[`tests/test_agent_workspace_schemas.py`](../tests/test_agent_workspace_schemas.py)
(154 cases) and [`tests/test_gitignore_policy.py`](../tests/test_gitignore_policy.py)
(37 cases). Run both with:

```bash
python -m pytest tests/test_agent_workspace_schemas.py tests/test_gitignore_policy.py -v
```

A runtime CLI (`python -m devolaflow.agent_workspace.lint <change-id>`) lands
in v8.2.5 and turns hard-budget breaches into commit failures.

## Index

| # | Schema | Target file | Token budget (soft / hard) | Format |
|---|--------|-------------|----------------------------|--------|
| 1 | `change-goal` | `.local/.agent/active/<id>/goal.md` | 200 / 400 | markdown + frontmatter |
| 2 | `change-checklist` | `.local/.agent/active/<id>/checklist.md` | 1200 / 2400 | markdown + frontmatter |
| 3 | `change-stage` | `.local/.agent/active/<id>/stage.md` | 400 / 800 | markdown + frontmatter |
| 4 | `change-preflight` | `.local/.agent/active/<id>/preflight.md` | 600 / 1200 | markdown + frontmatter |
| 5 | `change-spec` | `.local/.agent/active/<id>/spec.md` | 1500 / 3000 | markdown + OpenSpec deltas |
| 6 | `change-status` | `.local/.agent/active/<id>/STATUS.yaml` | 100 / 200 | pure YAML |
| 7 | `owned-files` | `.local/.agent/active/<id>/owned_files.txt` | 50 / 100 | plaintext |
| 8 | `handoff-envelope` | `.local/.agent/handoff/<from>__<to>__<id>__<seq>.yaml` | 600 / 1200 | YAML (discriminated union) |
| 9 | `agent-config` | `.local/.agent/config.yaml` | 400 / 800 | pure YAML |
| 10 | `source-of-truth-spec` | `.local/memory/specs/<domain>/spec.md` | 2000 / 4000 | markdown + frontmatter |

History: v16.0.0 replaced the per-change `acceptance.md` + `tasks.md` pair with
the single `checklist.md` contract (plus `stage.md` / `preflight.md`); the
`change-acceptance` and `change-tasks` schemas rode dual-track for one MAJOR
and were **removed in v17.0.0** at their declared `removal_target`. Loading a
folder that still carries `tasks.md`/`acceptance.md` without `checklist.md`
raises `LegacyChangeLayoutError` — migrate the folder to `checklist.md`.

## 1. `change-goal`

Single-paragraph intent statement opening an in-flight change; first artifact
written at `/devola:propose` and frozen verbatim at archive time. Frontmatter:
`id`, `created` (ISO-8601 UTC), `priority` (`P1..P4`), `intent_class`
(`feature|bugfix|refactor|migration|spike|docs|ops`). Body sections in
order: `# Goal: <one-line title>` (≤ 120 chars), `## Why` (1–2 sentences),
`## In scope` (1–8 bullets), `## Out of scope` (0–8 bullets). Schema:
[`change-goal.yaml`](../schemas/agent-workspace/change-goal.yaml). Validate
with `pytest tests/test_agent_workspace_schemas.py -k change_goal -v`.

## 2. `change-checklist`

Single per-change execution contract (v16.0.0): goals as `## G<n>: <title>`
H2 headings, items as `- [ ] C-G<n>.<m> (P0|P1|P2) <text>` with an indented
`verify:` line; checked items carry an
`evidence: evidence/<item>.txt | checked_by: ... | round: N | at: <ISO>` line.
Frontmatter: `parent`, `schema_version`, `total_items`, `checked`,
`priority_dist`, `reverted_open` (all derived from the body). When ALL items
are `[x]`, the change MAY transition `IN_PROGRESS → VERIFYING`. Replaces the
removed `change-acceptance` + `change-tasks` pair. Schema:
[`change-checklist.yaml`](../schemas/agent-workspace/change-checklist.yaml).
Validate with `pytest tests/test_agent_workspace_schemas.py -k change_checklist -v`.

## 3. `change-stage` and 4. `change-preflight`

`stage.md` records the current round's focus and hand-back notes (soft 400 /
hard 800). `preflight.md` is the signed pre-execution authorization surface
(soft 600 / hard 1200) read by the preflight guard before any owned-file
write. Schemas:
[`change-stage.yaml`](../schemas/agent-workspace/change-stage.yaml),
[`change-preflight.yaml`](../schemas/agent-workspace/change-preflight.yaml).
Validate with `pytest tests/test_agent_workspace_schemas.py -k "change_stage or change_preflight" -v`.

## 5. `change-spec`

Operation spec in **OpenSpec delta format** — per Rule **A-4** (M-004 ADR),
this file carries deltas relative to the source-of-truth at
`.local/memory/specs/<delta_target>/spec.md`. Three delta sections recognised
(at least one MUST be present, capitalisation enforced verbatim):

| Section heading | Body template marker |
|-----------------|----------------------|
| `## ADDED Requirements` | `### Requirement: <stable heading>` + RFC 2119 verb body + `#### Scenario:` block |
| `## MODIFIED Requirements` | `### Requirement: <existing heading>` + `(Previously: ...)` marker |
| `## REMOVED Requirements` | `### Requirement: <existing heading>` + `(Reason ...)` marker |

Frontmatter: `parent`, `delta_target` (domain), `delta_kind` (`lite` ⇒ gate
threshold 8.5; `full` ⇒ 9.0 per W-3 / SI-3). Schema:
[`change-spec.yaml`](../schemas/agent-workspace/change-spec.yaml). External
adoption: see `docs/cycle-archive/v8.3.0/other/v8.3.0_openspec_deep_analysis.md` and
[OpenSpec](https://github.com/Fission-AI/OpenSpec). Validate with
`pytest tests/test_agent_workspace_schemas.py -k change_spec -v`.

## 6. `change-status`

Pure YAML FSM block — the only artifact that mutates frequently. Encodes
the canonical lifecycle:

```
PROPOSED ─▶ IN_PROGRESS ─┬─▶ VERIFYING ─▶ ARCHIVED
                         │       │
                         │       └─▶ IN_PROGRESS  (verify FAIL → bounded retry)
                         └─▶ ESCALATED  (P4 bounded retry exhausted)
```

All 10 fields are required: `schema_version`, `change_id`, `state` (enum
`[PROPOSED, IN_PROGRESS, VERIFYING, ARCHIVED, ESCALATED]`), `percent_complete`
(0..100), `owner_layer` (`L0..L3`), `owner_session_id`, `last_updated` (ISO-8601
UTC), `last_handoff_seq`, `gate_score` (float|null), `verify_pass` (bool|null).
`gate_score` and `verify_pass` MAY be `null` in pre-VERIFYING states — explicit
null is **required**, MUST NOT be omitted. Schema:
[`change-status.yaml`](../schemas/agent-workspace/change-status.yaml).
Validate with `pytest tests/test_agent_workspace_schemas.py -k change_status -v`.

## 7. `owned-files`

Plaintext file-ownership manifest: one repo-relative POSIX path per line,
**max 6 paths**, no comments, no blank lines, trailing newline required, LF
only. The authoritative source for Rule **S-8** (No Writes Outside Active
Change Owned Files) — the lifecycle hook reads this file before every L3
write. Per-line constraints: pattern `^[A-Za-z0-9._/-]+$`, MUST NOT start
with `/` (S-2), no `..` segments, no glob characters. Implicit ownership
exceptions: anything inside the change folder itself plus the agent's own
outbox under `.local/.agent/handoff/` (append-only per S-9). Schema:
[`owned-files.yaml`](../schemas/agent-workspace/owned-files.yaml). Validate
with `pytest tests/test_agent_workspace_schemas.py -k owned_files -v`.

## 8. `handoff-envelope`

The only supported channel for inter-agent messaging in DevolaFlow's 4-layer
hierarchy. Filename pattern: `<FROM>__<TO>__<change-id>__<seq4>.yaml` where
FROM/TO are layer ids `L0..L3` (MUST differ — no self-handoff) and `seq4` is
exactly 4 zero-padded digits (`0001` ... `9999`). **Append-only invariant**
(Rule **S-9**): once a file exists, it is immutable; new info requires a
`seq+1` envelope. Discriminated union via `envelope_kind`:

| `envelope_kind` | Variant block | Direction | Use case |
|-----------------|---------------|-----------|----------|
| `TaskDispatch` | `dispatch:` | parent → child | Work assignment with AC + owned-files refs |
| `StatusReport` | `report:` | child → parent | Completion / progress / metrics |
| `EscalationEvent` | `escalation:` | child → parent (or upward) | P4 retry exhausted; needs intervention |

Required envelope-level fields: `schema_version`, `seq` (≥ 1), `from_layer`,
`to_layer`, `change_id`, `created`, `envelope_kind`. At archive time, all
envelopes for the change-id are compacted into
`.local/.agent/archive/<date>-<id>/handoff_chain.yaml`. Schema:
[`handoff-envelope.yaml`](../schemas/agent-workspace/handoff-envelope.yaml).
Validate with `pytest tests/test_agent_workspace_schemas.py -k envelope -v`.

## 9. `agent-config`

Per-project DevolaFlow agent config read at every L0 boot. Fields:
`schema_version`, `schema` (default `change-driven`), `context` (free-form
prose ≤ 800 chars — tech stack / conventions / house rules), `rules`
(per-artifact-kind rule lists for goal / acceptance / spec / tasks),
`mode` (`lite` runs gate steps 1–3; `full` runs all 6 SI-10 steps),
`plugin_runtime` (overrides for v8.2.1's installer — `auto_install`,
`prefer_local_fallback`). Schema:
[`agent-config.yaml`](../schemas/agent-workspace/agent-config.yaml).
Validate with `pytest tests/test_agent_workspace_schemas.py -k agent_config -v`.

## 10. `source-of-truth-spec`

Per Rule **A-4** (M-004 ADR), the authoritative source-of-truth for current
system behavior in `<domain>`; mutated **only** at archive time AFTER the
gate has PASSED (W-3 / SI-3 composite ≥ 8.5 lite / 9.0 full). Sole writer:
`ChangeArchive.propose_merge` (ships v8.2.5). Delta application rules per
kind: `ADDED` appends in canonical order, `MODIFIED` replaces verbatim,
`REMOVED` deletes — all keyed on the stable `### Requirement: <heading>`
line. Body contract: `# Spec: <Domain> — Source-of-Truth` H1 + 0+
`## Requirement: <stable heading>` sections; **NO delta sections** (those
live in per-change spec.md only). Schema:
[`source-of-truth-spec.yaml`](../schemas/agent-workspace/source-of-truth-spec.yaml).
Validate with `pytest tests/test_agent_workspace_schemas.py -k source_of_truth_spec -v`.

## Cross-cutting governance

The 10 artifact schemas above are bound to four rules introduced in v8.2.2:

| Rule | Layer | Summary | Bound schemas |
|------|-------|---------|---------------|
| **S-8** | Soul (P0) | No writes outside active change `owned_files`. | owned-files, change-spec, change-checklist |
| **S-9** | Soul (P0) | Handoff envelopes are append-only. | handoff-envelope |
| **C-9** | Conventions (P2) | Per-artifact token budgets (table above). | all 10 artifact schemas |
| **A-4** | Architecture (P1) | Source-of-truth at `.local/memory/specs/<domain>/spec.md`; mutated only at archive after gate PASS. | source-of-truth-spec, change-spec |

## Q-5 `agent_plus_specs` `.gitignore` policy

`.gitignore` re-includes the union of `.local/.agent/**` (active + handoff +
archive + config) and `.local/memory/specs/**` (source-of-truth) while keeping
the rest of `.local/` plus `operational.jsonl`, `session_state.json`,
`prefs.md`, and `plugin_install.log` ignored. Per-change `learnings.jsonl`
files are also re-ignored as defense in depth (treated as secrets). Verify:

```bash
python -m pytest tests/test_gitignore_policy.py -v
git check-ignore -v .local/.agent/config.yaml          # rule starts with `!` → TRACKED
git check-ignore -v .local/memory/operational.jsonl    # rule does NOT start with `!` → IGNORED
```

## Cross-references

- [`schemas/agent-workspace/__init__.yaml`](../schemas/agent-workspace/__init__.yaml) — index of all 10 schemas with byte-identical token budgets.
- [`tests/test_agent_workspace_schemas.py`](../tests/test_agent_workspace_schemas.py) — 154 schema tests.
- [`tests/test_gitignore_policy.py`](../tests/test_gitignore_policy.py) — 37 gitignore policy tests.
- [`.cursor/rules/repo-governance.mdc`](../.cursor/rules/repo-governance.mdc) + [`AGENTS.md`](../AGENTS.md) — compiled rule-layer copies of S-8 / S-9 / C-9 / A-4.
- `docs/cycle-archive/v8.3.0/design/v8.3.0_design.md` §2, §3 — authoritative design.
- `docs/cycle-archive/v8.3.0/v8.3.0_patch_plan.md` §v8.2.4 — patch decomposition.
- `docs/cycle-archive/v8.3.0/v8.3.0_gap_analysis.md` §2.1 C-002, §2.3 M-003, M-005 — gap context.
- DevolaFlow source: `https://github.com/YoRHa-Agents/DevolaFlow`
- OpenSpec source: `https://github.com/Fission-AI/OpenSpec`
