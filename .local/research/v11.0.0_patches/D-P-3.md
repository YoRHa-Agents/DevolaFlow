# D-P-3 — Patch Design Specification

> **Direction**: STATUS.yaml schema extensibility demo
> **Source**: `.local/research/v10_internal_optimization_directions.md` §3.2 D-P-3 (lines 129-136)
> **Author**: L3 Task Agent, Wave 4a (D-P Protocol Evolution)
> **Date**: 2026-05-04
> **Cycle**: v11.0.0 SI-1 planning
> **Constraints**: Adds ONE OPTIONAL metadata sub-field NEST under existing block per A-2.3 nest-vs-append decision rule. G-6 cache-prefix gate respected: `schemas/lean-dispatch.yaml#layout_invariant.canonical_order` is NOT touched (this patch modifies `schemas/agent-workspace/change-status.yaml`, a SEPARATE schema). The 10-baseline byte test stays green by virtue of being unrelated to this surface.

---

## §1 — Current State

`schemas/agent-workspace/change-status.yaml` (v8.2.4 schema_version 1; `.local/research/v8.3.0_design.md` §2.5) declares 9 required top-level fields (lines 40-50): `schema_version`, `change_id`, `state`, `percent_complete`, `owner_layer`, `owner_session_id`, `last_updated`, `last_handoff_seq`, `gate_score`, `verify_pass`. The schema has been **byte-stable since v8.3.0** (~14 minor cycles) — see `workflow-system/agent/references/agent-workspace.md` §4 lines 318-333 for the schema documentation.

The Python binding lives in `src/devolaflow/agent_workspace/change.py` (lines 109-146) — `Change` dataclass + property accessors `state`, `percent_complete`, `last_handoff_seq`. Round-trip contract (AC-2 of v8.2.5 patch_plan, lines 17-26): `Change.from_active_folder(p).to_active_folder(p2)` produces byte-identical files.

The 14-cycle stability suggests one of two interpretations: (a) the schema is a perfect fit for in-flight FSM state and needs no extension, OR (b) the operator community has stopped attempting extensions because the schema's all-required posture creates friction (every new field would force a `schema_version` bump 1 → 2 + breaking-change handling). The source doc proposes a SAFE EXTENSION DEMO that proves "adding an optional field is cheap" — flipping the latent assumption from (b) to (a) without forcing a hard schema_version bump.

The lint surface at `src/devolaflow/agent_workspace/lint.py::ARTIFACT_BUDGETS` (line 65-74) caps `STATUS.yaml` at soft 100 / hard 200 tokens per Rule C-9. A new optional field MUST fit within that envelope.

## §2 — Patch Design

**Algorithm** (additive optional field — A-2.3 NEST decision):

1. Add ONE new OPTIONAL top-level field to `schemas/agent-workspace/change-status.yaml`: **`last_lint_token_count`**: optional int, default null. Carries the verbatim `BudgetReport.checked_files`-aggregate token count from the most recent `lint_change()` invocation. Field shape: scalar `int | null`, no nested object.
2. NEST rationale per A-2.3 (verbatim from `.local/research/adr/v9-ADR-002-cache-layout-governance-v2.md` D3 lines 87-94 decision matrix):
   * "Does the behaviour modify how an existing block is interpreted?" → **YES** — extends how the STATUS.yaml block describes the change's lint health.
   * "Does the behaviour reuse an existing block's data shape?" → **YES** — reuses the integer/scalar shape of `last_handoff_seq` and `percent_complete`.
   * "Is the new field independently optional?" → **YES** — null when no lint has been run on the change, populated after first `lint_change()` call.
   * Verdict: NEST as a new field within `change-status.yaml` (the existing schema block) rather than introducing a sibling schema file. NOT an APPEND to `schemas/lean-dispatch.yaml#layout_invariant.canonical_order` (different schema surface entirely).
3. Update `instance_top_level_required` list (line 40-50): NEW field is OPTIONAL — does NOT appear in required list. Backward-compat: existing STATUS.yaml files without `last_lint_token_count` continue to validate cleanly.
4. Update `fields:` block (line 54-106): add `last_lint_token_count` definition with `type: int`, `nullable: true`, description.
5. `schema_version` STAYS at 1. The new field is purely additive — no breaking change. Future cycle that bumps to schema_version=2 may make the field required if usage signal warrants.
6. Update `Change` dataclass (`src/devolaflow/agent_workspace/change.py` lines 109-146) to add a property accessor `last_lint_token_count` mirroring the `last_handoff_seq` pattern at line 144-146.
7. Add ONE-line population in `src/devolaflow/agent_workspace/lint.py::lint_change` to optionally write the token-count back to STATUS.yaml when called with `--write-back-status` (NEW opt-in CLI flag).

**Files touched**:

* `schemas/agent-workspace/change-status.yaml` — +12 lines (1 new field definition + comment).
* `src/devolaflow/agent_workspace/change.py` — +6 lines (1 new property accessor).
* `src/devolaflow/agent_workspace/lint.py` — +20 lines (CLI flag + write-back logic).
* `tests/test_change_status_schema_extensibility.py` — NEW; ~80 LOC; 5-7 test functions.
* `workflow-system/agent/references/agent-workspace.md` §4 STATUS.yaml schema block — +3 lines documenting the new optional field.

**API surface** (additive only):

```python
@dataclass
class Change:
    # existing fields...

    @property
    def last_lint_token_count(self) -> int | None:
        """Optional accessor; returns None when STATUS.yaml lacks the field
        (backward-compat with v8.3.0 → v10.3.0 STATUS.yaml files)."""
        raw = self.status.get("last_lint_token_count")
        return int(raw) if raw is not None else None
```

```bash
# NEW opt-in CLI flag (default OFF — preserves v10.3.0 lint behaviour byte-identical):
$ python -m devolaflow.agent_workspace.lint <change-id> --write-back-status
```

**Byte-test that must stay green**: `tests/test_layout_invariant_multi_baseline.py` — all **10 baselines** (v7.0.0 → v10.2.0) MUST continue to PASS unchanged. This patch does NOT touch `schemas/lean-dispatch.yaml` and does NOT touch `src/devolaflow/compressor/layout.py::DEFAULT_DISPATCH_LAYOUT` — the lean-dispatch canonical_order remains length 17 with FROZEN_PREFIX_V7 untouched. The byte-test is preserved by construction (G-6 PASS).

**Backward-compat invariants**:

* Existing STATUS.yaml files without `last_lint_token_count` validate cleanly (field is optional + nullable per schema definition).
* `Change.from_active_folder(p).to_active_folder(p2)` round-trip stays byte-identical for files lacking the new field (yaml.safe_dump with sort_keys=False preserves the absence).
* `lint_change(change_id)` default behaviour (no CLI flag) is byte-identical to v10.3.0 — no STATUS.yaml mutation unless `--write-back-status` is explicitly passed.

## §3 — Small Project Evaluation

**Synthetic test bed**: `synthetic_small_repo` (per `v11.0.0_evaluation_methodology.md` §2). Operations exercised: `init`, `feature` (1-file scope). Both create a `.local/.agent/active/<change-id>/` folder with STATUS.yaml.

**Operations exercised**: `init` (creates STATUS.yaml at PROPOSED state with 9 required fields), then run `python -m devolaflow.agent_workspace.lint <id> --write-back-status` after first artifact authoring.

**Metric collection** (per §4.2 architecture-health metrics):

* `STATUS.yaml schema field count` (before vs after extension).
* `STATUS.yaml round-trip byte stability` (`Change.from_active_folder().to_active_folder()`).
* `lint_change wall-clock time` (with/without --write-back-status).

**Expected delta (before → after)**:

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| STATUS.yaml schema fields (top-level, optional+required) | 9 required | 9 required + 1 optional | +1 optional | improve (extensibility) |
| Schema_version bumps | 0 | 0 (additive — stays at 1) | 0 | preserve (R5 backward-compat) |
| STATUS.yaml round-trip byte-identical for v10.3.0 files (no new field) | yes | yes | 0 | preserve |
| `lint_change` default behaviour (no flag) wall-clock | ~50ms small repo | ~50ms small repo | 0 | preserve |
| `lint_change --write-back-status` wall-clock | N/A | ~55ms small repo | +5ms (1 STATUS.yaml write) | new feature |

**Pass criterion**: schema documents the new optional field AND v10.3.0-shape STATUS.yaml files validate cleanly without modification AND `lint_change` default behaviour stays byte-identical.

**If no improvement on small project**: small projects use STATUS.yaml exactly the same way as large projects — the extensibility demo applies UNIFORMLY across project sizes. Small-tier passes by virtue of the optional field being addable, opt-in usable, and fully backward-compatible.

## §4 — Large Project Evaluation

**Test bed**: DevolaFlow self at v10.3.0 baseline. v10.3.0 has used STATUS.yaml across multiple in-flight changes (sample: any `.local/.agent/archive/<date>-<change-id>/STATUS.yaml`).

**Metric collection** (per §4.2 + §4.5 buckets):

* `STATUS.yaml schema_version stability` (1 → 1, additive only).
* `Multi-baseline byte test PASS count` (10/10 — unrelated schema, must stay green).
* `Existing STATUS.yaml files validation pass-rate` (all v8.3.0+ archived STATUS.yaml files MUST validate post-patch).

**Expected delta (v10.3.0 baseline → post-patch)**:

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| STATUS.yaml schema fields | 9 required | 9 required + 1 optional | +1 optional | improve (extensibility demo) |
| Schema_version | 1 | 1 (additive) | 0 | preserve (R5 backward-compat) |
| Existing archived STATUS.yaml validation pass-rate | 100% | 100% (field optional → absence is canonical) | 0 | preserve |
| `tests/test_layout_invariant_multi_baseline.py` PASS count | 10/10 | 10/10 (unrelated schema) | 0 | preserve (G-6 PASS) |
| `lint_change` Python API surface | 4 public symbols | 4 public symbols (CLI flag added; no new public function) | 0 | preserve (additive) |
| `Change` dataclass property count | 3 (state/percent_complete/last_handoff_seq) | 4 (+last_lint_token_count) | +1 | improve (data accessor) |

**Pass criterion**: zero existing-STATUS.yaml validation failures AND multi-baseline byte test 10/10 PASS AND new CLI flag is opt-in (default behaviour preserved byte-identical).

**Side-effect check** (MUST NOT regress):

* `tests/test_layout_invariant_multi_baseline.py` — all 10 baselines PASS (unrelated to STATUS.yaml; this patch does not touch lean-dispatch.yaml).
* `tests/test_agent_workspace_change_store.py` (or equivalent) — `Change.from_active_folder().to_active_folder()` round-trip stays byte-identical for v8.3.0+ STATUS.yaml shapes.
* `tests/test_agent_workspace_lint.py` (or equivalent) — `lint_change(change_id)` default behaviour produces identical exit code + violation list as v10.3.0.
* `src/devolaflow/agent_workspace/archive.py` — `gate_score` / `verify_pass` field-reading stays byte-identical (unrelated change).
* `python -m pytest tests/test_version.py -v` — schema_version stays 1; no version-consistency surface affected.

## §5 — Benefit Metrics (≥ 3 quantitative; DF-internal)

| # | Metric | Before (v10.3.0) | After (v11.0.x demo PV) | Δ | Bucket |
|:---:|---|---:|---:|---:|---|
| 1 | STATUS.yaml schema optional fields | 0 | 1 (`last_lint_token_count`) | +1 | §4.2 architecture |
| 2 | Schema extensibility precedent artifacts on file (NEW optional field landed via additive contract) | 0 (no STATUS.yaml extension since v8.3.0) | 1 (this patch) | +1 | §4.2 architecture |
| 3 | `Change` dataclass accessor properties | 3 | 4 | +1 | §4.5 observability |
| 4 | Multi-baseline byte test PASS (G-6 guard, unrelated surface) | 10 / 10 | 10 / 10 | 0 (preserved) | §4.6 coupling |
| 5 | Backward-compat for v8.3.0+ archived STATUS.yaml files (validation pass-rate) | 100% | 100% | 0 (preserved) | §4.6 coupling |

NONE of these metrics rely on EvoBench `q` / `pass_rate` / `gap_score` (G-1 PASS).

## §6 — Admission Verdict

**PASS** for the optional field addition.

The patch demonstrates that extending `schemas/agent-workspace/change-status.yaml` with a NEW OPTIONAL field is cheap (12 LOC schema + 6 LOC dataclass + 20 LOC lint write-back + 80 LOC test = ~120 LOC total), bytewise backward-compatible, and respects A-2.3 (NEST under existing block), G-5 (no Soul rule changes), and G-6 (no edits to `schemas/lean-dispatch.yaml#layout_invariant.canonical_order` positions 1-12 or anywhere else; the lean-dispatch byte test stays 10/10 PASS by construction).

The 14-cycle stability of STATUS.yaml is shown to be a SOFT constraint, not a HARD one: optional additive fields are landable without schema_version bump and without breaking existing tooling. Future cycles considering FSM state extensions (e.g. tracking handoff envelope kinds, lint health, or per-task-type owner_layer) now have a cited precedent to follow.

## §7 — Effort Estimate

**S** (≤ 0.5 PV) — confirms the source doc estimate (line 134). Breakdown:

* Schema edit + frontmatter doc-comment: ~30 min.
* `Change` dataclass property accessor: ~15 min.
* `lint_change --write-back-status` CLI flag + write-back logic: ~45 min.
* `tests/test_change_status_schema_extensibility.py` (5-7 test functions covering: absent-field round-trip, present-field round-trip, lint write-back happy path, lint write-back when STATUS.yaml is malformed, lint default behaviour byte-identical to v10.3.0): ~1.5 hours.
* Update `workflow-system/agent/references/agent-workspace.md` §4 STATUS.yaml block: ~15 min.

W-17 test budget consumption: +5-7 NEW test functions (well under +30 per-PV cap).

## §8 — Dependencies

**none** — standalone schema extension. Does NOT depend on D-P-1 / D-P-2 / D-P-4. May be referenced by future PDS that propose further STATUS.yaml extensions.

## §9 — Risk Register

| # | Risk | Severity | Mitigation |
|:---:|---|:---:|---|
| 1 | New optional field accidentally becomes required when a future cycle bumps schema_version 1 → 2 without preserving the optional-default contract | minor | Schema field documentation includes verbatim "OPTIONAL — must remain optional unless schema_version explicitly bumped" comment; companion test in `tests/test_change_status_schema_extensibility.py::test_field_remains_optional_at_schema_v1` pins the contract |
| 2 | `lint_change --write-back-status` mutates STATUS.yaml without `last_updated` refresh, breaking the invariant at `change-status.yaml` line 131 ("last_updated MUST be refreshed on every edit") | major | Write-back implementation MUST refresh `last_updated` simultaneously per the existing FSM invariant; explicit test `test_writeback_refreshes_last_updated` pins the joint write |
| 3 | `last_lint_token_count` data drifts from actual file state if STATUS.yaml is written-back-once but artifacts subsequently grow (the field becomes stale) | minor | Field is informational metadata, not a gate signal; documentation explicitly notes "snapshot at most-recent lint invocation, may be stale"; the `lint_change()` API has no obligation to keep it fresh between invocations |

ZERO blocker risks because the patch is fully additive and opt-in.

---

ADMISSION: PASS | EFFORT: S | DEPS: none | TIER: standard
