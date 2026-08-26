---
id: harness-construction
version: "1.0.0"
purpose: >
  Canonical operating contract for the harness-construction branch:
  the explicit seed trigger, the machine-grounded gap preflight
  (`python -m devolaflow.harness gap`), the six built-in coverage axes
  plus the custom-axes YAML contract, the `harness_preflight.md`
  artifact, and the archive-time capability review loop. Pairs with
  `schemas/agent-workspace/harness-preflight.yaml`, the
  `devolaflow.harness.gap` module, and the archive existence gate in
  `devolaflow.agent_workspace.archive`.
tier: 2
token_estimate: 3400
last_updated: "2026-08-27"
---

# Harness Construction — Operating Contract

> **Tier-2 reference** — load when the `harness-construction` seed is
> selected, or when the operator asks for harness, evaluation
> infrastructure, observation coverage, telemetry build-out, or
> gap-analysis work. SKILL.md §"Quick Start — Workflow Selection"
> carries the one-row intent mapping; this file carries the full
> operating contract.

## §1 — When to Load

Two trigger surfaces feed harness-construction activation:

1. **Seed selection** — L0 matches harness intent and loads the seed
   via `TemplateRegistry.load_seed("harness-construction")`. Intent
   keywords (seed metadata, verbatim): `harness`,
   `evaluation-infrastructure`, `observability`, `telemetry`,
   `coverage`, `gap-analysis`, `baseline`.
2. **Operator phrasing** — the operator asks to "build the harness",
   "improve observation coverage", "front-load evaluation
   infrastructure", or equivalent. L0 maps the intent to the seed row
   in SKILL.md and loads this reference alongside it.

Execution always uses the sole `change-driven` runtime
(`registry.load_template("change-driven")`); the seed contributes
non-executable decomposition knowledge only, per
`references/meta-framework.md`.

### 1.1 Seed shape

`workflow-system/agent/templates/seeds/harness-construction.yaml` is a
registry-v3 composition with four partitions (checklist skeleton, not
an execution order):

| Partition | Covers | Key assertion |
|---|---|---|
| `inventory` | Existing harness capability survey | every surface inventoried with its machine evidence source |
| `gap-analysis` | Structured gap report (§3) | gap report JSON frozen as preflight evidence; gaps cited verbatim |
| `infra-build` | Observation points / probes / baselines / loop closure | every committed axis implemented with tests |
| `capability-review` | Post-build before/after delta (§5) | archive review records both gap reports and the capability delta |

## §2 — Trigger Contract

### 2.1 v1 — Explicit channel (CURRENT)

The seed is the only activation channel in v1. Selection is purely
natural-language intent matching against the seed keywords — NO new
`DEVOLAFLOW_*` env flag is introduced (W-20 reuse-first; same posture
as grill mode, W-22.4), and NO dispatch schema field carries the
harness flag (A-2.3: the flag is the `harness_preflight.md` artifact
itself, §4).

### 2.2 v2 — Cross-cutting suggest channel (DEFERRED — do not ship)

The design memo (`.local/tasks/add_harness_design/design.md` §2, §7 —
historical provenance, mirrored by the `design_reference` key of
`schemas/agent-workspace/harness-preflight.yaml`) telegraphs a second
channel for a FUTURE cycle. It is documented here so nobody ships it
silently (S-4: this reference documents only what exists; the items
below explicitly DO NOT exist yet):

- **DEFERRED**: at STANDARD+ preflight, when `harness gap` exits 1 AND
  `auto_fill_rate` falls below a suggestion threshold, L0 suggests
  task reordering — build the infrastructure first, then do the
  original task (dependency inversion: infra → nodes → loop).
- **DEFERRED**: an optional `classify_harness_intent` classifier
  returning `HARNESS_REQUESTED` / `HARNESS_SUGGESTED` / `NO_HARNESS`,
  mirroring the grill-mode precedent (W-22.4).
- **OPEN QUESTION** (design §7): the `auto_fill_rate` threshold value
  — to be read from the capacity profile rather than hardcoded, and
  calibrated with real ledger data at the v2 SI-1 gate.

Any PR that lands one of these MUST first clear SI-1 gap analysis for
its cycle; citing this section is not authorization to implement.

## §3 — Preflight Analysis Protocol

Harness-flagged changes complete a machine-grounded gap inventory
BEFORE the preflight is signed. The protocol is prompt-side guidance —
it adds NO field to the `preflight.md` signature schema.

1. **Run the gap inventory** against the live ledger:

   ```bash
   python -m devolaflow.harness gap \
     --ledger .local/telemetry/harness.jsonl \
     --repo . \
     --output evidence/harness_gap_before.json
   ```

   Add `--axes-config <path>` when the change declares custom axes
   (§4.3). Flags: `--ledger` (required), `--repo` / `--repo-root`
   (default `.`), `--axes-config` (optional), `--output` (stdout when
   omitted).

2. **Freeze the before-snapshot** as
   `evidence/harness_gap_before.json` inside the active change folder.
   The frozen JSON is the verbatim source for every gap cited
   downstream (C-3).

3. **Author `harness_preflight.md`** (§4) in the change folder, citing
   the frozen report byte-for-byte in its `## 3. Gap Inventory`
   section.

4. **Add ONE Stop Card** to the signed `preflight.md`:
   "harness preflight incomplete → STOP". This is the only
   `preflight.md` touch — the artifact's eight configuration sections
   and authorization schema are unchanged.

### 3.1 Exit codes

| Exit | Meaning | Evaluate-convention alignment |
|---:|---|---|
| 0 | Every axis `COVERED` (no `PARTIAL`, no `GAP`) | READY |
| 1 | At least one axis `PARTIAL` or `GAP` | NOT_READY |
| 2 | Insufficient or malformed input (§7) | INSUFFICIENT |

An ABSENT ledger is evidence, not an error: ledger-dependent axes
report `GAP` with the verbatim reason `ledger absent` and the run
exits 1. Malformed input (unreadable axes-config, invalid ledger
records) fails loudly per S-5 and exits 2.

### 3.2 Gap report shape (schema_version 1)

```json
{
  "schema_version": 1,
  "sampled_at": "<ISO-8601 UTC>",
  "axes": [
    {"id": "observation", "builtin": true,
     "status": "COVERED|PARTIAL|GAP",
     "evidence": {"...": "machine facts"},
     "gaps": [{"item": "...", "reason": "..."}]}
  ],
  "auto_fill_rate": 0.62,
  "insufficient_slots": ["..."],
  "summary": {"covered": 3, "partial": 2, "gap": 1}
}
```

`auto_fill_rate` and `insufficient_slots` are owned by the
`evaluation` axis (they mirror `evaluate_harness` slot availability).
Custom axes carry `builtin: false` plus their optional `title` /
`rationale` fields.

### 3.3 Public API

```python
from devolaflow.harness.gap import (
    BUILTIN_GAP_AXES,            # ("observation", ..., "loop-closure")
    COMMAND_TIMEOUT_CAP_SECONDS, # 120
    GapConfigError,
    build_gap_report,            # inventory -> report dict
    compare_gap_reports,         # (before, after) -> delta dict
    load_gap_report,             # frozen JSON -> validated report dict
    render_capability_review,    # delta -> review markdown (§5)
)
```

`build_gap_report` is deterministic and byte-stable across runs except
for `sampled_at` (injectable for frozen snapshots). `load_gap_report`
validates the envelope keys, `schema_version == 1`, and the per-axis
`id`/`status` contract so a comparison never runs on garbage.

## §4 — Coverage Axes and the `harness_preflight.md` Artifact

### 4.1 Six built-in axes

Pinned by code and tests (`BUILTIN_GAP_AXES`). The low-intrusion
principle is built in: axes ENUMERATE observation points; they never
propose in-code hooks or instrumentation rewrites.

| Axis id | Checks | Evidence source |
|---|---|---|
| `observation` | L0/L1/L2 dispatch telemetry completeness | per-layer dispatch records in the ledger |
| `evaluation` | W-3 six-dimension slot availability | `evaluate_harness` subcomponents + `auto_fill_rate` |
| `probe` | probe fixtures × model-table coverage | `tests/fixtures/harness/*.yaml` + `meta.probe_models` in `workflow-system/agent/context_profiles.yaml` |
| `baseline` | settled W-16 Tier-B baseline existence | `.local/telemetry/baselines/harness_baseline_*.json` |
| `signal` | local signal collectability (coverage, docstrings, …) | `collect_signals` availability per `SIGNAL_KEYS` |
| `loop-closure` | propose→apply audit trail completeness | `proposal_applied` events in the ledger |

Statuses are three-valued: `COVERED` / `PARTIAL` / `GAP`.

### 4.2 Custom axes YAML (`--axes-config`)

Change-level extension, conventionally
`.local/.agent/active/<change-id>/harness_axes.yaml`:

```yaml
schema_version: 1
axes:
  - id: sim-stage-latency          # lowercase-hyphen slug; must not
    title: Simulation stage latency  # collide with built-in ids
    probe:                         # REQUIRED — an axis without a
      kind: ledger_query           # machine probe fails loudly
      spec: {event: sim_stage_completed, min_count: 1}
    rationale: "latency regressions were invisible in v17 telemetry"
```

Three probe kinds, each with a closed spec shape:

| Kind | Spec (exact keys) | COVERED when |
|---|---|---|
| `file_exists` | `path` (repo-relative; no absolute, `~`, or `..`) | the path exists |
| `command` | `argv` (non-empty string list) + `timeout_seconds` (int 1..120, cap `COMMAND_TIMEOUT_CAP_SECONDS`) | the command exits 0 within the timeout |
| `ledger_query` | `event` + optional `min_count` (int ≥ 1, default 1) | the ledger has ≥ `min_count` matching events |

Every custom axis MUST declare a falsifiable probe — an axis with no
machine probe is rejected at load time (the anti-"vibes-axis" rule).
Any malformed document (wrong keys, bad slug, id collision, out-of-cap
timeout) raises `GapConfigError` naming the file and field verbatim
(S-5), which the CLI maps to exit 2.

### 4.3 `harness_preflight.md`

Schema: `schemas/agent-workspace/harness-preflight.yaml`. OPTIONAL
change-folder artifact; its PRESENCE is the harness flag
(artifact-as-contract per A-1 P5 — no dispatch schema field, no env
flag). Absence means the change is simply not harness-flagged and
lints clean.

- **Frontmatter** (all required): `parent` (must equal the change-id),
  `schema_version: 1`, `gap_report` (path to the frozen
  before-snapshot; must exist; resolved change-folder-first, then repo
  root), `axes_config` (path or `null`; when non-null the file must
  exist under the same resolution order).
- **Body headings**, exact and in order: `# Harness Preflight`, then
  `## 1. Target Observation Surface`, `## 2. Capability Mapping`
  (one row per harness capability surface: telemetry / aggregator /
  evaluator / probe / proposal / capacity), `## 3. Gap Inventory`
  (verbatim citations from the frozen gap report — C-3; no
  paraphrase of paths, items, reasons, or metric values),
  `## 4. Coverage Commitments` (which axes this change advances),
  `## 5. Build Order` (dependency inversion: infrastructure →
  nodes → loop).
- **Token budget** (C-9): soft 800 / hard 1600. Verify with
  `python -m devolaflow.agent_workspace.lint <change-id>`.
- **Lint finding codes** (register `HPF_*`, §7).

## §5 — Review Loop (Archive-Time Capability Delta)

1. **Re-run the gap inventory** before archive with the same axes
   configuration, freezing `evidence/harness_gap_after.json`.
2. **Compare** the two frozen snapshots:

   ```bash
   python -m devolaflow.harness gap \
     --ledger .local/telemetry/harness.jsonl \
     --repo . \
     --compare evidence/harness_gap_before.json \
     --review-output evidence/harness_capability_review.md
   ```

   `--compare` and `--review-output` MUST be given together (mixed
   usage is a CLI error). One invocation builds the CURRENT report
   (the "after" side), diffs it against the frozen before-snapshot
   via `compare_gap_reports`, and renders the review through
   `render_capability_review`. The review records: per-axis status
   transitions (`GAP→COVERED` etc.), the `auto_fill_rate` delta,
   resolved gap items reproduced verbatim (C-3), and regressions.
   The frozen snapshot is loaded through `load_gap_report`, so a
   malformed file fails loudly (exit 2) instead of producing a
   garbage diff. The rendered review is byte-stable for a given
   delta — the only timestamps cited are the compared reports' own
   `sampled_at` values.
3. **Archive gate** (existence-only): a harness-flagged change —
   i.e. `harness_preflight.md` exists in the change folder — REQUIRES
   `evidence/harness_capability_review.md` to exist and be non-empty
   at `ArchiveManager.archive` time. The guard runs BEFORE any STATUS
   mutation, so a failed gate leaves the active folder untouched;
   non-flagged changes pay exactly one flag-file existence test.

**Delta values are trend-only.** Regressions and `auto_fill_rate`
drops are RECORDED for review; they are never a PASS condition and
never change an exit code or gate verdict. This mirrors the composite
score's "recorded trend, not a PASS condition" philosophy
(SKILL.md §"Gate Mechanism") — the gate checks that the review EXISTS,
never what its numbers say.

## §6 — Cycle Roll-Up

Change-level capability diffs feed the EXISTING cycle instruments —
no new cadence is created:

- **W-16 settlement**: the cycle's harness evidence (including
  capability reviews archived with their changes) aggregates into the
  once-per-cycle `harness_baseline_<cycle>.json` settlement. Reviews
  are inputs to settlement, not a parallel baseline track.
- **W-7 retrospective**: the cycle retrospective adds a harness
  subsection summarizing which axes moved (`GAP→COVERED` counts,
  `auto_fill_rate` trend across the cycle's flagged changes) and which
  committed axes were deferred.

Tier-A byte witnesses are untouched: the gap/review flow introduces
no dispatch schema change (A-2.4).

## §7 — Failure Modes

| Failure | Surface | Behaviour |
|---|---|---|
| Ledger file absent | `gap` CLI | NOT an error — ledger-dependent axes report `GAP` with reason `ledger absent`; exit 1 |
| Invalid ledger record | `gap` CLI | `AggregationError` → message on stderr, exit 2 |
| Unreadable / malformed axes-config (bad YAML, wrong keys, bad slug, id collision, timeout outside 1..120) | `gap` CLI | `GapConfigError` naming file + field → exit 2 |
| Repo root missing / not a directory | `gap` CLI / API | `EvaluationError` → exit 2 |
| Malformed frozen gap report (bad JSON, missing envelope keys, wrong `schema_version`, invalid axis status) | `load_gap_report` / compare mode | `GapConfigError` → exit 2 |
| `--compare` without `--review-output` (or vice versa) | `gap` CLI | argparse error naming both flags; exit 2 |
| `harness_preflight.md` frontmatter unparsable or missing required keys | workspace lint | `HPF_FRONTMATTER` finding |
| `schema_version` other than 1 | workspace lint | `HPF_SCHEMA_VERSION` finding |
| Numbered `## N.` headings out of canonical order | workspace lint | `HPF_SECTION_ORDER` finding |
| `gap_report` path dangling | workspace lint | `HPF_GAP_REPORT` finding |
| Non-null `axes_config` path dangling | workspace lint | `HPF_AXES_CONFIG` finding |
| Token budget breach (soft 800 / hard 1600) | workspace lint | warn / fail per C-9 |
| Harness-flagged change archived without a non-empty capability review | `ArchiveManager.archive` | `ArchiveError` naming `evidence/harness_capability_review.md` verbatim; STATUS untouched |

## §8 — Cross-References

- `schemas/agent-workspace/harness-preflight.yaml` — artifact schema
  (frontmatter, canonical headings, capability surfaces, invariants).
- `src/devolaflow/harness/gap.py` — gap inventory + compare engine
  (`build_gap_report`, `compare_gap_reports`, `load_gap_report`,
  `render_capability_review`, `BUILTIN_GAP_AXES`,
  `COMMAND_TIMEOUT_CAP_SECONDS`, `GapConfigError`).
- `src/devolaflow/harness/__main__.py` — the `gap` subcommand wiring
  and exit-code mapping.
- `src/devolaflow/agent_workspace/lint.py` — `HPF_*` finding register
  for `harness_preflight.md`.
- `src/devolaflow/agent_workspace/archive.py` — the existence-only
  archive gate (`HARNESS_PREFLIGHT_FILENAME`,
  `HARNESS_CAPABILITY_REVIEW_RELPATH`).
- `workflow-system/agent/templates/seeds/harness-construction.yaml` —
  the v1 explicit trigger seed (§1.1).
- `references/agent-workspace.md` — change folders, evidence budgets,
  archive lifecycle the harness artifacts live inside.
- `references/meta-framework.md` — registry v3, seeds as
  non-executable knowledge.
- `references/env-flags.md` — the canonical flag inventory this
  branch deliberately does NOT extend (W-20).
- SKILL.md §"Built-in Harness Truth" — evaluate/aggregate/probe/
  propose/apply, the surfaces the six axes inventory.

## History

- Scaffolded by `scripts/scaffold_reference.py` (D-X-2).
- v1 harness-construction branch: seed + `harness gap` CLI (six
  built-in axes, custom-axes YAML, exit codes 0/1/2) +
  `harness_preflight.md` artifact (C-9 800/1600) + archive-time
  capability review with existence-only gate. Design provenance:
  `.local/tasks/add_harness_design/design.md` (decisions 1–5).
