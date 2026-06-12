# v15-ADR-005 — Benchmark / Golden Baseline Retirement & Tiering Policy

* **Status**: PROPOSED (L0/human ratifies — amends A-2.4's keep-all-forever wording)
* **Date**: 2026-06-12
* **Cycle**: v14.2.0 T5 (SI-1 planning gate for the v14.2.x → v15.0.0 ladder)
* **Feeds**: F-R11 (major), F-R13 (minor) per
  `.local/research/v15-cycle_design_review_repo.md` §2/§7-D2; gap G-014
* **3-condition gate** (verbatim from the repo review §7): "Hard to reverse: deleting golden
  files destroys byte-witnesses that cannot be regenerated from history with confidence.
  Surprising: A-2.4 currently says keep-all-forever; any pruning contradicts written rule. Real
  trade-off: archival integrity vs monotone CI/maintenance growth." → **qualifies**.

## Context

`benchmarks/devolaflow_context/baselines/` contains **62 files**: 10 `layout_invariant_v*.yaml`
goldens + 38 `v*_baseline.json` (every minor from v2.1.0 through v14.1.0) + 14
`v3.2.0_round_*.json` + `v9.3.0_latency.json`/`v9.7.0_latency*.json`. A-2.4 mandates: "Future
schema bumps MUST add a new golden YAML for the new baseline AND keep all prior baselines
passing." Keep-all-forever makes the directory monotone-growing with no retirement path; the 14
`v3.2.0_round_*.json` files serve no current test on a 15-version-old format. Companion waste
(F-R13): `lean-dispatch.yaml` lines 719-738 hand-mirror the test matrix as ten
`v*_baseline_passes: true` booleans "that can never legitimately be false (CI would fail
first)". The planned 5-version ladder mechanically adds ~5 more baselines under current rules.

## Decision (recommended)

Three-tier retention, replacing keep-all-forever:

1. **Tier A — permanent byte-witnesses (NEVER pruned, stay in CI)**: the v7.0.0 frozen-prefix
   witness + one golden per schema-version bump — i.e. the `layout_invariant_v*.yaml` set that
   `tests/test_layout_invariant_multi_baseline.py` loads. These are irreplaceable (cannot be
   regenerated from history with confidence) and are the A-2 governance itself.
2. **Tier B — rolling window (in CI)**: per-minor `v*_baseline.json` for the current + previous
   2 cycles (W-16's comparison window). The newest-baseline pin convention
   (`_newest_baseline_path`) is unaffected.
3. **Tier C — archived (out of CI)**: per-minor JSONs older than the Tier-B window move to
   `docs/cycle-archive/<cycle>/baselines/` (W-19's existing committed-archive surface) via
   `git mv` — history preserved, CI/maintenance cost zero. First sweep prunes the 14
   `v3.2.0_round_*.json` relics and the orphaned latency JSONs (archive, don't delete).
4. **Same-PR coupling**: (a) amend A-2.4's sentence "keep all prior baselines passing" →
   "keep all Tier-A witnesses passing" + recompile; (b) replace the `backward_compat` boolean
   block in `lean-dispatch.yaml` with one comment pointing at
   `tests/test_layout_invariant_multi_baseline.py` (F-R13).
5. **Timing**: ladder slot v14.5.0 per gap analysis §4 (the review proposed v14.3.0 — flagged
   as L0-decision §4.2 #4; the sweep itself is a pure-move patch and can land any time after
   ratification).

## Consequences

### Positive
* Baseline directory becomes bounded: ~5 Tier-A + ~3 Tier-B + pointers; each future bump adds
  one Tier-A witness only when the schema version actually bumps (none since v9.7.0).
* Reader confusion ("which baseline is load-bearing?") resolved structurally by tier.
* The write-only `backward_compat` sync point is eliminated.

### Negative
* A-2.4 — an Architecture rule with multi-cycle citation history — changes wording; every doc
  citing keep-all-forever needs the same-PR sweep.
* Tier-B window misjudgment risk: a regression hunt needing a 3-cycle-old JSON must check out
  the archive path instead of the live dir. Mitigated: files are committed, not deleted.

### Neutral
* `tests/test_layout_invariant_multi_baseline.py` (884 lines) keeps all its goldens — Tier A is
  exactly its load set; the multi-baseline byte test stays green by construction.
* W-16 wholesale-regen mechanics unchanged (regen targets Tier B's newest slot).

## Alternatives considered

* **A1 — Keep-all-forever (status quo)**: zero risk, monotone growth; 62 → ~85 files by
  v16.0.0; perpetuates the F-R11 confusion. Rejected.
* **A2 — Delete (not archive) Tier-C**: destroys byte-witnesses; contradicts the gate's own
  "hard to reverse" finding. Rejected.
* **A3 — Git-history-only retention (delete from tree, rely on `git log`)**: technically
  recoverable but undiscoverable; W-19 already established the committed-archive convention for
  exactly this class of artifact. Rejected.
* **A4 — Tier by file type only (keep all YAML, archive all JSON)**: simpler rule but
  accidentally archives the newest baseline JSON that W-16 pins. Rejected.
