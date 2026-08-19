---
id: "agent/references/human-surface"
version: "1.0.0"
purpose: >
  Defines the `.local/human/` human-facing interaction surface introduced
  in DevolaFlow v14.0.0. Covers the two-zone (INPUT / OUTPUT) + dated
  archive directory layout, the immutable-INPUT schemas (constitution.md
  amendable principles + stable REQ-ID requirements + append-only
  amendments ledger), the anti-flooding OUTPUT artifacts (conclusion-first
  convergence report + read-first DIGEST), the per-artifact C-9 token
  budgets, the human↔agent separation boundary (INPUT-only git tracking),
  the `scan_workspace` discovery fields + When-to-Engage routing, and the
  `trace_requirements` / `lint_human` / `render_human_report` Python APIs.
  Use this when authoring or consuming `.local/human/` artifacts, wiring
  human INPUT as authoritative plan-mode context, or emitting the
  convergence digest at workflow close.
triggers:
  - "authoring durable human requirements or a project constitution"
  - "recording an amendment to a ratified requirement"
  - "reading human INPUT as authoritative plan-mode context"
  - "emitting the convergence report / DIGEST at workflow close"
  - "linting human-surface token budgets"
  - "tracing REQ-IDs to acceptance evidence"
  - "discovering the human surface via scan_workspace at session start"
tier: 2
token_estimate: 6500
dependencies:
  - "agent/SKILL.md"
  - "agent/references/agent-workspace.md"
  - "agent/references/plan-mode-enforcement.md"
last_updated: "2026-08-19"
---

# Human Surface Reference

The human surface is DevolaFlow's first-class, durable, human-authored
tier under `.local/human/`. It sits beside the agent substrate
(`.local/.agent/`), the accumulated knowledge tier (`.local/memory/`),
and the per-cycle research tier (`.local/research/`). It exists to close
two long-standing gaps the v13.0.0 driver feedback named:

1. **Immutable long-term human INPUT** — durable requirements + constraints
   with regression value (引导回测). Immutability comes from an append-only
   amendment ledger (Rule S-9 discipline), NOT from write-locking files.
2. **Concise human OUTPUT** — conclusion-first, budget-capped convergence
   reports + a read-first digest, so human-facing output never floods.

Authoritative design: `docs/cycle-archive/v14.0.0/design/v14.0.0_design.md` (§2–§9). This
reference is the SKILL-surface summary of that design.

## 1. When to Load This Reference

Load when the task involves any of:

| Trigger | What you'll be doing |
|---|---|
| Authoring `.local/human/input/constitution.md` | Need the constitution schema + Governance protocol + per-file version stamp |
| Authoring `.local/human/input/requirements.md` | Need the REQ-ID schema, Traceability matrix, Out-of-Scope table, shard policy |
| Recording an amendment | Need the append-only amendments ledger format (Rule S-9 discipline) |
| Reading human INPUT in plan mode | Need the When-to-Engage row: human INPUT is BINDING context |
| Emitting the convergence report / DIGEST | Need the OUTPUT schemas, status enum, C-9 budgets, `render_human_report` API |
| Linting human-surface budgets | Need the C-9 budget table + `lint_human` API |
| Tracing REQ-IDs to evidence | Need the `trace_requirements` API + `RequirementTraceResult` shape |
| Discovering the surface at session start | Need the `scan_workspace` fields (`has_human_dir` et al.) |

If the task does NOT touch `.local/human/`, this reference is OPTIONAL.

## 2. Directory Layout

`.local/human/` holds exactly two zones (INPUT, OUTPUT) plus a dated
archive — a small fixed file set, not a sprawling tree. All paths are
relative to the repository root (Rule S-2 — never absolute).

```
.local/human/
├── README.md                          # role + write-owner conventions (human-INPUT vs agent-draft-OUTPUT)
├── input/                             # WRITE-OWNER: human. Immutable post-ratification (§3).
│   ├── constitution.md                # amendable principles/constraints; per-file Version|Ratified|Last-Amended + Governance
│   ├── requirements.md                # REQ-<DOMAIN>-NN entries + Traceability matrix + Out-of-Scope; shards on overflow (§3b)
│   ├── requirements/                  # (overflow only) per-domain REQ shards, one REQ-<DOMAIN>-* family per file
│   │   └── <domain>.md                #   created lazily when the aggregate would exceed the §4 hard ceiling
│   └── amendments/                    # append-only amendment ledger (Rule S-9 discipline) — the 引导回测 lineage
│       └── <YYYY-MM-DD>-<slug>.md      #   one amendment per file; NEVER edited or deleted
├── output/                            # WRITE-OWNER: agent drafts → human approves (§4). Anti-flooding.
│   ├── README.md                      # write-owner conventions for the OUTPUT zone
│   ├── DIGEST.md                      # ≤100-line read-first STATE digest
│   └── convergence/                   # per-cycle convergence reports
│       └── <version>-convergence.md    # conclusion-first, ≤500 words, status enum, per-REQ evidence rows
└── archive/                           # dated frozen snapshots of superseded INPUT + closed OUTPUT (A-4 "why")
    └── <YYYY-MM-DD>-<slug>/            # frozen prior version of a requirement / closed cycle report
```

### Separation boundary (who owns what)

| Tree | Write-owner | Lifecycle | Tracked? | Role |
|---|---|---|---|---|
| `.local/human/input/` | **human** | durable, forward, immutable post-ratification | **tracked (D-4)** | authoritative requirements/constraints |
| `.local/human/output/` | agent-draft → human-approve | per-cycle, bounded | private (ignored) | convergence digest + reports |
| `.local/human/archive/` | frozen snapshot | dated, on supersede | private (ignored) | superseded INPUT + closed OUTPUT |
| `.local/.agent/` | agent | in-flight change folders + handoff | private (ignored) | machine substrate (S-8/S-9) |
| `.local/memory/` | agent (auto-memory) + A-4 specs | accumulated; specs at archive-time | only `specs/` tracked | learnings + source-of-truth behaviour |
| `.local/research/` | human/agent (cycle authors) | per-cycle research | tracked | gap analyses, designs, retros |
| `.local/feedbacks/` | human (reactive) | per-version, post-hoc | private | reactive feedback + TRACKER |

Distinctions: vs `.local/feedbacks/` (reactive / post-hoc),
`.local/human/input/` is **forward / durable** — "what every future
version MUST honour". Vs `.local/memory/specs/` (agent BEHAVIOUR, per
Rule W-23.4) it is **human INTENT**. They never overlap: a behaviour
decided in grill mode goes to a `spec.md`; a durable requirement goes to
`requirements.md`.

## 3. INPUT Design — Immutable + Regression Value

The INPUT zone realizes "immutable for regression value WITHOUT literal
write-locking" via two schemas + an append-only amendment ledger.

### 3a. `constitution.md` — amendable principles

Durable principles/constraints that supersede ad-hoc practice; carries a
per-file version-stamp footer + a Governance amendment protocol.
**Version stamps are PER-FILE:** `constitution.md` and `requirements.md`
each carry their OWN `Version` stamp and version independently — an
amendment bumps the stamp of the file whose ratified block changed.

```markdown
---
artifact: human-constitution
version: <CONSTITUTION_VERSION>      # bumped on every ratified amendment (semver)
---
# DevolaFlow Constitution

## Principle <N>: <Title>
<RFC-2119 statement: the project MUST / MUST NOT / SHOULD ...>
Rationale: <1-2 lines>

## Governance
- This constitution supersedes ad-hoc practice when they conflict.
- Amendments require: (1) documented rationale, (2) human approval, (3) a migration note.
- Amendments are recorded by APPENDING a dated file under `input/amendments/`;
  the prior text is preserved verbatim (Rule S-9 discipline) — never edited in place.

**Version**: <X.Y.Z> | **Ratified**: <YYYY-MM-DD> | **Last Amended**: <YYYY-MM-DD>
```

### 3b. `requirements.md` — stable REQ-IDs + traceability

```markdown
# Requirements (`artifact: human-requirements`)

## Requirements
### REQ-<DOMAIN>-NN: <title>            # DOMAIN = uppercase tag; NN = zero-padded
- **Constraint:** <RFC-2119 statement>
- **Acceptance:** <checkable criterion — a test/metric/observable, not prose>
- **Lifecycle:** DRAFT | RATIFIED <YYYY-MM-DD>   # append-only trigger — DISTINCT from Status
- **Status:** Pending | Satisfied | Blocked       # satisfaction progress — orthogonal to Lifecycle
- **Amendments:** <none> | `input/amendments/<YYYY-MM-DD>-<slug>.md`

## Traceability
| REQ-ID | Acceptance criterion | Cycle | Status |
|---|---|---|---|
| REQ-<DOMAIN>-NN | <criterion> | <version> | <status> |
| **Unmapped** | — | — | **0** ✓ |        # scope-reduction detection: never silently drop scope

## Out of Scope
| Item | Reason |
|---|---|
| <explicitly excluded item> | <why> |

**Version**: <X.Y.Z> | **Last Amended**: <YYYY-MM-DD>   # requirements.md's OWN per-file stamp
```

**Lifecycle vs Status (a load-bearing distinction).** `Lifecycle`
(`DRAFT` → `RATIFIED <date>`) is the SOLE append-only trigger — it
governs immutability. `Status` (`Pending` / `Satisfied` / `Blocked`)
tracks satisfaction progress and is orthogonal. A `RATIFIED` REQ can
still be `Pending`. The immutability hook (§3c) keys ONLY on `Lifecycle`
and never inspects `Status`.

**Rotation & overflow.** `requirements.md` holds only the ACTIVE durable
REQ set; two policies stop monotonic growth from colliding with the §4
hard ceiling:

1. **Supersede → archive.** When an amendment replaces a REQ, the prior
   REQ block moves to `archive/<YYYY-MM-DD>-<slug>/` (frozen, with its
   amendment trail). Only LIVE REQs count against the budget.
2. **Shard on overflow.** When the live set would still exceed the
   2500-token hard ceiling, split by domain into
   `input/requirements/<domain>.md` (one `REQ-<DOMAIN>-*` family per
   file). The C-9 budget then applies **PER FILE** (§4c), and
   `requirements.md` degrades to a thin index (Governance pointer + the
   global Traceability matrix + per-domain links). The aggregate cap
   therefore never silently truncates scope — `Unmapped: 0 ✓` is
   preserved across shards.

### 3c. Immutability mechanism

| Phase | Rule | Enforcement — keyed on `Lifecycle`, NOT `Status` |
|---|---|---|
| **Pre-ratification** | A requirement/principle is freely editable while its lifecycle is `DRAFT` | per-REQ `Lifecycle: DRAFT` (constitution: no `Ratified:` stamp yet) |
| **Ratification gate** | Human ratifies → text becomes a binding contract | per-REQ `Lifecycle: DRAFT → RATIFIED <date>` (constitution: `Ratified` stamp set); THIS transition is the sole append-only trigger |
| **Post-ratification** | A `RATIFIED` block is IMMUTABLE; changes APPEND a new dated `input/amendments/<date>-<slug>.md` and bump that file's version stamp — the prior text stays verbatim | Rule S-9 append discipline (reused — NOT a new Soul rule) |

**Append-only amendment ledger format** (`input/amendments/<date>-<slug>.md`):

```markdown
# Amendment <YYYY-MM-DD> — <slug>
- **Target:** REQ-<DOMAIN>-NN (or Principle <N>)
- **Rationale:** <why the ratified text must change>
- **Delta:** <what changed — old → new>
- **Migration note:** <how downstream consumers adapt>
```

One delta + WHY per file; the file is NEVER edited or deleted once
written (mirrors the handoff-envelope append-only invariant, Rule S-9).

The immutability predicate is implemented by the lifecycle hook
`devolaflow.lifecycle.check_human_input_append_only` (§5). It reads the
per-REQ `Lifecycle` field (a `### REQ-*` block is frozen **iff**
`Lifecycle: RATIFIED *`) and the constitution's `Ratified:` stamp; an
in-place edit to such a block (vs adding an amendment + version bump)
warns in `lite`, blocks in `full` / STRICT — mirroring
`check_envelope_append_only` (S-9) + `check_file_ownership` (S-8). A
`Lifecycle: DRAFT` block is exempt, so the hook never inspects `Status`.

### 3d. Regression / 引导回测 lineage

Each requirement carries a checkable lineage so coverage is provable and
drift is auditable (Rule A-4: truth + delta + dated archive):

```
REQ-<DOMAIN>-NN  →  acceptance criterion (checkable)  →  Traceability row (cycle, status)
                 →  input/amendments/<date>-<slug>.md  (every post-ratification change, append-only, WHY)
                 →  archive/<date>-<slug>/             (frozen prior version when superseded)
```

The amendment ledger is the regression anchor: a future cycle can diff
"what REQ-INPUT-01 required at ratification vs now" to verify no
requirement silently regressed.

## 4. OUTPUT Design — Concise, Anti-Flooding

Two artifacts: a per-cycle convergence report and a read-first digest.
Both are conclusion-first and budget-capped. Write-owner is
agent-draft → human-approve: the render is opt-in (no auto-trigger), and
it NEVER mutates the INPUT zone.

### 4a. `output/convergence/<version>-convergence.md`

```markdown
# Convergence Report — <version>
> **Status:** passed | gaps_found | human_needed      <- line-1 conclusion (status enum)
> Date: <YYYY-MM-DD> | Cycle: <version> | Author-layer: L0

## Verdict
<1-3 sentences, conclusion-first: did we converge, against which requirements?>

## Requirement evidence            # evidence-before-claims
| REQ-ID | Acceptance criterion | Result | Evidence (verbatim per C-3) |
|---|---|---|---|
| REQ-<DOMAIN>-NN | <criterion> | met / partial / unmet | `tests/test_x.py::test_y` PASS @ <commit> |

## Blocking findings               # MUST resolve before human approval
- <finding> → <required action>

## Advisory findings               # do NOT block approval
- <finding> (advisory)

## Next step
<owner + single action>           # decide in <3 min
```

**Status enum** (line-1 conclusion, DERIVED — see §6c):

- `passed` — all traced REQ `met` AND no blocking findings.
- `gaps_found` — ≥1 REQ `partial` / `unmet`, no blockers (advisory-resolvable).
- `human_needed` — ≥1 blocking finding or stagnation → human decision
  (maps to P4 escalation).

### 4b. `output/DIGEST.md` — read-first STATE digest

```markdown
# DevolaFlow Human Digest
> Updated: <YYYY-MM-DD> | Latest cycle: <version> | Status: passed|gaps_found|human_needed

## Where we are            (≤5 lines)
## Open asks for the human (≤5 items; BLOCKING only — advisory lives in the report)
## Requirement coverage    (THIS-cycle REQ deltas only, ≤1 line each) + rollup: <N total · M satisfied · K blocked>
## Latest convergence → output/convergence/<version>-convergence.md
```

The digest is the "read-once, know where we are" surface — a DIGEST, not
an archive. Refreshed (overwritten) each cycle; superseded reports rotate
to `archive/`. **Coverage rollup:** the coverage section lists only REQs
added/changed THIS cycle (≤1 line each) plus ONE rollup line
(`N total · M satisfied · K blocked`); it never re-lists every durable
REQ verbatim, so the DIGEST budget stays flat as the REQ set grows. The
full REQ→status matrix lives in `input/requirements.md` (or its
per-domain shards, §3b).

### 4c. Explicit budgets — the C-9 human rows

The human artifacts are governed by Rule C-9 token budgets, enforced in
TOKENS only (matching the token-only `agent_workspace.lint`):

| File | Soft budget | Hard ceiling | Rationale |
|---|---|---|---|
| `.local/human/input/constitution.md` | 800 tokens | 1500 | Durable principles; opinionated, terse |
| `.local/human/input/requirements.md` | 1200 tokens | 2500 | REQ list + matrix + out-of-scope; degrades to a thin index once sharded (§3b) |
| `.local/human/input/requirements/<domain>.md` (shard) | 1200 tokens | 2500 | **PER-FILE** cap; one `REQ-<DOMAIN>-*` family per file |
| `.local/human/input/amendments/<date>-<slug>.md` | 400 tokens | 800 | One delta + WHY per file |
| `.local/human/output/DIGEST.md` | 600 tokens | 1000 | Read-first skim surface (~100 lines) |
| `.local/human/output/convergence/<version>-convergence.md` | 700 tokens | 1000 | Decide-in-3-min, conclusion-first (~500 words) |

**TOKENS are the sole enforced unit:** every budget above is linted in
TOKENS via `estimate_tokens` (the parenthetical line/word figures are
authoring guidance only, NOT a second linted axis — no new measurement
machinery). Soft over → warn; hard over → fail commit (full / STRICT) —
identical semantics to the existing C-9 agent-workspace rows. The
canonical rows live in `.cursor/rules/repo-governance.mdc` C-9 (compiled
from `.rules/conventions.mdc`) and are mirrored in
`references/agent-workspace.md` §9.

### 4d. Relationship to `reporter.py` and CHANGELOG/retrospective

- Rendered by the FIFTH `reporter.py` flavour `render_human_report`
  (§5), reusing the Jinja2 + pinned-clock idempotency + opt-in semantics
  (no auto-trigger); `regenerate_all` gains a `"human"` key. The existing
  four flavours (per-change / workspace / memory / rules) stay
  byte-identical.
- **No duplication of CHANGELOG / retrospective:** the report *cites*
  them by path (`CHANGELOG.md` `## [<version>]`,
  `.local/research/<version>_retrospective.md`), never restates — it
  answers "did we satisfy the human's REQ-IDs", which neither records.

## 5. Python API Surface

Three public surfaces back the human surface. All are pure / S-5-safe
(explicit error states, never silent failures).

### 5a. Discovery — `devolaflow.workspace_context`

`scan_workspace(repo_root)` (the pure, read-only discovery function L0
calls at session start) gains four fields, APPENDED after the existing
`WorkspaceContext` fields (additive; existing `to_summary_dict` keys
unchanged):

| Field | Type | Semantics | Default |
|---|---|---|---|
| `has_human_dir` | `bool` | `.local/human/` exists as a directory | `False` |
| `human_constitution` | `Path \| None` | path to `input/constitution.md` when present | `None` |
| `human_requirements` | `Path \| None` | path to `input/requirements.md` when present | `None` |
| `human_digest` | `Path \| None` | path to `output/DIGEST.md` when present | `None` |

Private `_scan_human_input` / `_scan_human_output` helpers mirror the
existing `_scan_*` (S-5: PermissionError / OSError → WARNING + absent,
never raise).

### 5b. Traceability — `devolaflow.agent_workspace.requirements_trace`

| Symbol | Description |
|---|---|
| `trace_requirements(requirements_path, *, test_results=None) -> dict[str, RequirementTraceResult]` | REQ-ID → evidence checker; joins `requirements.md`'s `## Traceability` matrix (status + `Acceptance criterion` + `Cycle`) with the per-REQ `Acceptance` text. Keys the **union** of block ∪ matrix REQs (both-way S-5). When `test_results` is supplied, the §6c test-run join overrides matrix status with the actual PASS/FAIL outcome |
| `RequirementTraceResult` | Frozen per-REQ trace row (`result` ∈ `met`/`partial`/`unmet`, `evidence: str` verbatim per C-3, `criterion: str`, `cycle: str`) |
| `TestOutcome` | Frozen `{node_id, outcome, commit}` — the §6c test-run join input |
| `parse_pytest_report(report_path, *, commit="") -> dict[str, TestOutcome]` | Reads a pytest `--report-log` JSONL (keeps `call`-phase `TestReport` records) → `{node-id → TestOutcome}`; S-5 loud on missing/malformed |
| `RequirementsTraceError` | Raised on structurally-invalid input |
| `TRACE_RESULTS` | Canonical `("met", "partial", "unmet")` tuple |
| `NO_EVIDENCE` | S-5 sentinel for a REQ with no `## Traceability` row |

S-5 behaviour (both directions): a REQ block with no matching matrix row
maps to `result="unmet", evidence="no evidence"`; a matrix row with no REQ
block maps to `result="unmet", evidence="matrix row without REQ block"`
(criterion/cycle preserved) — never a silent drop in EITHER direction. A
missing
requirements file raises `FileNotFoundError`; an invalid path type raises
`RequirementsTraceError`. The trace keys `result` off the matrix *Status*,
never off a block's `Lifecycle` field (the §3c distinction).

### 5c. Budget lint — `devolaflow.agent_workspace.lint`

| Symbol | Description |
|---|---|
| `lint_human(repo_root=None, *, human_root=None) -> BudgetReport` | Lints `.local/human/` INPUT + OUTPUT zones against the §4c budgets; sibling entry point to `lint_change` (NOT overloaded) |
| `HUMAN_ARTIFACT_BUDGETS` | `dict[str, tuple[int, int]]` mapping each canonical artifact pattern → `(soft, hard)` token budget |

`lint_human` walks `input/**` + `output/**`, maps each file to its
`HUMAN_ARTIFACT_BUDGETS` row, and applies the TOKEN budget via the shared
`estimate_tokens` heuristic. The per-file `input/requirements/<domain>.md`
shard cap and the `input/amendments/` ledger files each apply PER FILE.
The dated `archive/` zone is excluded (frozen snapshots). An absent
`.local/human/` yields an EMPTY report (a valid opt-in state, NOT an
error). Returns a `BudgetReport` with `change_id="human"`.

### 5d. Render — `devolaflow.agent_workspace.reporter`

| Symbol | Description |
|---|---|
| `render_human_report(version, trace=None, *, repo_root=None, requirements_path=None, test_results=None, findings=None, verdict=None, next_step=None, author_layer="L0", stagnation=False, now=None) -> str` | FIFTH flavour — the §4a convergence report (4-col `REQ-ID \| Acceptance criterion \| Result \| Evidence` table); line-1 `Status` enum DERIVED from two producers (§6c); `test_results` threads the §6c join; `stagnation=True` → `human_needed` (W-8/SI-9) |
| `render_human_digest(...) -> str` | The §4b read-first DIGEST |
| `regenerate_all(repo_root) -> dict[str, Path]` | Now also emits the `"human"` key alongside the four legacy reports |

Idempotent under a pinned clock (`now=`). Opt-in only — no existing
workflow auto-triggers the render. It does NOT mutate INPUT.

### 5e. Immutability hook — `devolaflow.lifecycle.check_human_input_append_only`

A lifecycle hook with the uniform `(payload, *, strict=False) -> HookResult`
signature shared by `check_envelope_append_only` (S-9) and
`check_file_ownership` (S-8). Payload is a prior↔proposed diff of ONE
input file (`prior`, `proposed`, optional `amendment_added`, optional
`path`). Permissive default (WARNING via the lifecycle logger); strict
mode re-raises the top-severity `HookViolation` (`blocker` for in-place
edits of ratified blocks, `error` for incomplete amendments). It is
exported additively but is NOT wired into `lifecycle.DEFAULT_EVENTS`
(event count pinned at 16); callers invoke it directly or register it via
`register_hook(EVENT, check_human_input_append_only)`.

## 6. Integration Contract

### 6a. Discovery + When to Engage

Every L0 dispatcher calls `scan_workspace(repo_root)` at session start.
When `has_human_dir=True`, L0 MUST READ `human_requirements` +
`human_constitution` as authoritative ground truth (see the When-to-Engage
row in `references/agent-workspace.md` §1). The scan itself is read-only
(S-2 relative-paths-only) and always performed.

### 6b. Plan-mode ingestion consumes human INPUT as AUTHORITATIVE

Per `references/plan-mode-enforcement.md` §5.5, L0 already reads
`recent_feedbacks` as *advisory themes*. The human INPUT is STRONGER — it
is *binding*:

- At plan-mode entry L0 reads `human_constitution` + `human_requirements`
  with the standard `Read` tool (no new permission — exactly like the
  feedback read).
- Constitution principles are binding constraints; the REQ-ID set is the
  scope contract the plan MUST cover — dropping a REQ is a flagged gap
  (scope-reduction detection).
- The primary path needs NO dispatch field (file reads only). An optional
  dispatch surfacing rides the existing `change_context` NEST sub-field
  (`human_input_refs`) per A-2.3 — no top-level key, canonical-order
  length unchanged.

### 6c. Workflow-close emits the convergence digest

At workflow / cycle close, L0 (opt-in, no auto-trigger) invokes
`render_human_report` to (1) write
`output/convergence/<version>-convergence.md` and (2) refresh
`output/DIGEST.md`. Idempotent under a pinned clock. It does NOT mutate
INPUT.

**Two DISTINCT producers feed the render.** The SI-3 composite gate emits
a 6-dimension score + `findings_by_severity` — it does NOT key evidence
by REQ-ID, so the per-REQ rows cannot come from it. The render therefore
consumes two separate inputs:

1. **Per-REQ `Result`/`Evidence` rows ← `trace_requirements` (§5b)**, NOT
   the gate. The trace maps each `REQ-<DOMAIN>-NN` to its acceptance
   evidence by joining `requirements.md`'s Traceability matrix with the
   per-REQ blocks. Evidence strings are verbatim per C-3.
2. **`Blocking` / `Advisory` finding sections ← the gate's
   `findings_by_severity`** (`blocker` / `critical` → Blocking;
   `major` / `minor` / `info` → Advisory).

The line-1 `Status` enum is then DERIVED: `passed` (all REQ `met` ∧ no
blockers) · `gaps_found` (≥1 REQ `partial`/`unmet`, no blockers) ·
`human_needed` (≥1 blocker **OR** `stagnation=True`, the W-8/SI-9
score-stagnated escalation).

**Test-run-artifact join (IMPLEMENTED v14.1.0).** The per-REQ rows can be
keyed off *actual* test outcomes rather than the optimistic matrix Status.
The caller contract at workflow close is:

1. Run the suite with the pytest report-log plugin:
   `pytest --report-log=<path>` (the `pytest-reportlog` plugin emits one
   JSON record per line).
2. Capture the workflow HEAD commit (e.g. `git rev-parse --short HEAD`).
3. `test_results = parse_pytest_report(<path>, commit=<hash>)` →
   `{node-id → TestOutcome}`.
4. Pass it through: `render_human_report(version, requirements_path=...,
   test_results=test_results)` (or `regenerate_all(..., human_version=...,
   human_test_results=...)`).

For each REQ whose `Acceptance` text NAMES a pytest node-id
(`path/to/test.py::test_name`) present in the map, the join sets
`result` = `met` (outcome `passed`) / `unmet` (else) and the evidence to
the verbatim `"<node_id> <PASS|FAIL> @ <commit>"` (C-3) — overriding the
matrix Status so the report can never over-claim a `Satisfied` cell whose
test actually failed. A REQ that names no resolvable node-id (or whose
node-id is absent from the map) falls back to the matrix derivation, so
mixing tested + manually-verified REQs in one cycle is supported. Omitting
`test_results` entirely preserves the v14.0.0 matrix-only behaviour
byte-for-byte.

## 7. Git-Tracking & De-Pollution

### 7a. INPUT-only tracking (operator-ratified)

`.local/` is private-by-default under the selective whitelist
(`local/workspace.py::_LOCAL_WHITELIST_BLOCK_LINES`). The human INPUT
zone must be authoritative ⇒ tracked, durable, PR-reviewable. The
whitelist delta tracks ONLY `.local/human/input/**`:

```gitignore
!.local/human/
!.local/human/input/
!.local/human/input/**
```

Per the operator decision (2026-06-03), `output/` + `archive/` stay
PRIVATE (ignored) — the bounded (C-9-capped) convergence reports + digest
are local-only, not PR-visible. D-4 is closed via the tracked `input/`
zone (the authoritative, reviewable, durable requirements/constraints).

### 7b. sichip-deferred relocation

Agent-authored `sichip_deferred_*.md` DEFER docs (+ the
`.sichip_deferred_fingerprints.txt` dedup sidecar) move OUT of the
human-facing `.local/feedbacks/` into the private agent tree at
`.local/.agent/sichip-deferred/` — these are agent OUTPUT, NOT human
INPUT, so they do NOT belong in `.local/human/`. The relocation
preserves the dedup fingerprint set verbatim (a transition-window
dual-read protects against a duplicate DEFER re-emit during migration).

### 7c. TRACKER fate

`.local/feedbacks/TRACKER.md` is retained ONLY as the reactive
feedback-resolution ledger, with its banner corrected from
"Auto-maintained" (a false claim) to "Human-maintained". The durable
coverage SSOT is `requirements.md`'s Traceability matrix
(`Unmapped: 0 ✓`), NOT TRACKER.

## 8. Worked Example

```markdown
# --- input/constitution.md (excerpt) ---
## Principle 2: Human intent is immutable post-ratification
The project MUST treat a ratified requirement as immutable: changes are recorded by
APPENDING a dated amendment, never by editing the ratified text in place.
Rationale: preserves regression/引导回测 value — the original intent stays auditable.

**Version**: 1.0.0 | **Ratified**: 2026-06-03 | **Last Amended**: 2026-06-03

# --- input/requirements.md (excerpt) ---
### REQ-INPUT-01: Ratified requirements are append-only
- **Constraint:** A `Lifecycle: RATIFIED` `### REQ-*` block MUST NOT be edited in place; a change
  MUST add `input/amendments/<YYYY-MM-DD>-<slug>.md` AND bump THIS file's version stamp.
- **Acceptance:** `tests/test_human_input_immutability.py` PASSES — a git diff that mutates a
  `RATIFIED` REQ block without a paired amendment file fails the lint.
- **Lifecycle:** RATIFIED 2026-06-03      # append-only trigger — DISTINCT from Status
- **Status:** Pending                     # a RATIFIED REQ can be Pending
- **Amendments:** none

**Version**: 1.0.0 | **Last Amended**: 2026-06-03

# --- output/convergence/v14.1.0-convergence.md (within budget) ---
# Convergence Report — v14.1.0
> **Status:** gaps_found
> Date: 2026-07-01 | Cycle: v14.1.0 | Author-layer: L0

## Verdict
Implemented `.local/human/` INPUT + scan_workspace surface; 2 of 3 tracked REQs satisfied.

## Requirement evidence
| REQ-ID | Acceptance criterion | Result | Evidence (verbatim) |
|---|---|---|---|
| REQ-INPUT-01 | append-only lint passes | met | `tests/test_human_input_immutability.py` PASS @ a1b2c3d |
| REQ-OUT-01 | digest token budget enforced | partial | `lint_human` row added; emission blocking lands v14.2.0 |

## Blocking findings
- none

## Advisory findings
- REQ-OUT-01 was advisory in v14.1.0; BLOCKING since v14.2.0 — `enforce_digest_budget` fails emission on a hard-ceiling violation (soft tier stays WARN-only).

## Next step
L0 → none for REQ-OUT-01; the digest budget blocks at emission since v14.2.0 (owner: L0).
```

## 9. References

### Internal

- `docs/cycle-archive/v14.0.0/design/v14.0.0_design.md` — full design (this reference is the SKILL-surface summary)
- `references/agent-workspace.md` — sibling `.local/.agent/` tree; §9 C-9 budgets (shared rule surface)
- `references/plan-mode-enforcement.md` §5.5 — feedback ingestion (the advisory counterpart to binding human INPUT)
- `.cursor/rules/repo-governance.mdc` — S-9 (append-only), C-9 (token budgets), A-4 (truth/delta/archive ADR), W-23.4 (vocabulary vs spec separation)
- `src/devolaflow/workspace_context.py` — `scan_workspace` + the four `has_human_dir`/`human_*` fields
- `src/devolaflow/agent_workspace/requirements_trace.py` — `trace_requirements` REQ-ID → evidence checker
- `src/devolaflow/agent_workspace/lint.py` — `lint_human` + `HUMAN_ARTIFACT_BUDGETS`
- `src/devolaflow/agent_workspace/reporter.py` — `render_human_report` / `render_human_digest`
- `src/devolaflow/lifecycle/check_human_input_append_only.py` — the §3c immutability hook

### External

- spec-kit: `https://github.com/github/spec-kit` — amendable-constitution pattern (Rule S-7)
- OpenSpec: `https://github.com/Fission-AI/OpenSpec` — archive preserves what + why
- gsd: `https://github.com/gsd-build/get-shit-done` — named-file set + STATE digest + scope-reduction detection
- DevolaFlow source: `https://github.com/YoRHa-Agents/DevolaFlow` (per S-7)
