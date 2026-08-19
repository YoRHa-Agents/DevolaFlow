# D-X-2 — Reference Doc Creation Link Compression

> **Direction source:** `.local/research/v10_internal_optimization_directions.md` §3.3 D-X-2
> **PDS schema:** `.local/research/v11.0.0_decomposition_plan.md` §3
> **Eval methodology:** `.local/research/v11.0.0_evaluation_methodology.md` §5 templates
> **Wave:** 1 (D-X Developer/Operator Experience)
> **Author:** L3 Task Agent (this artifact)
> **Baseline:** v10.3.0 (`f1d9652`)

## §1 — current_state

DevolaFlow's `workflow-system/agent/references/` directory ships **14
canonical references** (the SF-4 valid set) already exceeding the
`SKILL.md:368-388` Tier-2 navigation table's 14 listed references — the
`workflow-system/agent/SKILL.md "## Reference Navigation Guide"` table at
lines 368-388 enumerates all 14: agent-hierarchy, agent-workspace,
behavioral-guidelines, compression-pipeline, context-isolation,
decomposition-gate, env-flags, execution-protocol, message-schemas,
meta-framework, plan-mode-enforcement, repo-modes, shell-proxy, team-roles.

Adding a new (15th) reference doc currently requires the operator to
manually edit/create artifacts across **at least 7 surfaces** (verbatim
from `v10_internal_optimization_directions.md` §3.3 D-X-2):

1. Author `workflow-system/agent/references/<name>.md` (≤1000 lines per
   C-4 Large tier ceiling).
2. Add a row to `workflow-system/agent/SKILL.md` "## Reference Navigation
   Guide" Tier-2 table (lines 372-387).
3. Add an entry to `scripts/sync_cursor_skill.py::MIRRORED_FILES` (the
   list at lines 55-78); the comment block above the list reminds the
   author to edit `scripts/install.sh::install_cursor` "in lockstep" —
   i.e., the install.sh `dl_batch` blocks at lines 134-147 (Cursor),
   170-184 (Codex), 204-218 (Claude), 251-265 (KimiCode), 322-336 (Zed),
   361-375 (Cline), 400-414 (Roo) — **7 places in install.sh** must be
   updated for one new reference.
4. `tests/test_reference_size_budgets.py` parametrize automatically
   covers the new file (zero-config when the file appears under
   `references/*.md`).
5. `tests/test_integration.py::test_skill_md_under_500_lines` enforces
   SKILL.md still <500 (post-edit).
6. Add a `tests/test_no_ghost_features.py::test_v<X>_<Y>_<Z>_new_symbols_have_coverage`
   stanza pinning the new reference's path + (typically) one anchor
   string from its body (the W-18 pattern).
7. `make sync-cursor-skill` to mirror to `.cursor/skills/devola-flow/`
   (no-op if mirror absent; idempotent).

Steps 1-3 + 6 are manual; step 3 alone touches **7 install.sh blocks +
the MIRRORED_FILES list = 8 mechanical edits in 2 files** for one
reference. The "7 步中 (1)、(2)、(3)、(6) 是人工" estimate in
`v10_internal_optimization_directions.md` §3.3 D-X-2 captures this — and
specifically calls out that the 7 install.sh blocks are an O(N) hidden
maintenance cost not surfaced anywhere.

## §2 — patch_design

**Algorithm:**

```
scaffold_reference(name, *, tier=large, load_when="<placeholder>",
                   dry_run=False):
  1. Validate <name> against MIRRORED_FILES list (no collision).
  2. Render references/<name>.md skeleton (frontmatter + 5-section
     template: Purpose / When to Load / Body / Cross-References / History).
  3. Insert row into SKILL.md "## Reference Navigation Guide" table
     (insertion point: after the last alphabetically-prior row).
  4. Append entry to scripts/sync_cursor_skill.py::MIRRORED_FILES list.
  5. **NEW: derive install.sh dl_batch blocks from MIRRORED_FILES**
     instead of manual sync. Refactor install.sh to source a manifest
     file (workflow-system/agent/references/_install_manifest.txt) that
     scripts/sync_cursor_skill.py emits from MIRRORED_FILES at sync
     time. Each install_<adapter> function reads the manifest and loops
     over it via dl_batch. NO functional change to what gets installed,
     only single-source-of-truth for the file list.
  6. Print W-18 lint stanza (path + anchor-string presence assertion)
     for paste into tests/test_no_ghost_features.py.
  7. Print CHANGELOG entry skeleton.
```

**Files touched (NEW):**

- `scripts/scaffold_reference.py` (~200 LOC executable + argparse;
  6-8 unit tests in `tests/test_scaffold_reference.py`).
- `workflow-system/agent/references/_install_manifest.txt` — generated
  artifact (one path per line; emitted by `sync_cursor_skill.py`).

**Files touched (EDITED):**

- `scripts/sync_cursor_skill.py` — at the end of `sync()`, after
  `STAMP_FILE.write_text(...)`, also emit the manifest file at
  `_install_manifest.txt` containing each MIRRORED_FILES entry on its
  own line. Idempotent (compare-and-skip).
- `scripts/install.sh` — refactor each `install_<adapter>` function to
  read the manifest via `while read -r path; do dl_batch "$dir" "$path";
  done < manifest`. Saves ~70 lines of duplication across 7 adapters.
- `Makefile` — new `scaffold-reference` phony target wrapping the
  scaffold script (5 LOC).
- `workflow-system/agent/SKILL.md` — 1-line "Quick Start" pointer to
  `scripts/scaffold_reference.py`.
- `CHANGELOG.md` — release entry under PV-N where this patch lands.

**API/CLI surface:**

```bash
python scripts/scaffold_reference.py <name> \
    --tier large \
    --load-when "<short trigger description for SKILL.md table>"

python scripts/scaffold_reference.py <name> ... --dry-run
```

**Doc deliverables (G-9 mapping per admission_checklist.md §G-9):**

- CHANGELOG entry — required (Python module change).
- W-18 lint refresh — required.
- SKILL.md edit (1 line) — triggers W-12 adapter build verify.
- Reference doc add — only if the operator USES the scaffold to add a
  reference; the scaffold script itself is NOT a reference doc.
- Bilingual EN/ZH — NONE (developer-facing CLI).

## §3 — small_project_eval

**Synthetic test bed:** `synthetic_small_repo/` (per
`v11.0.0_evaluation_methodology.md` §2). The synthetic repo has NO
`workflow-system/agent/references/` substrate by default, BUT the
scaffold script can be invoked against the DF source tree FROM the
synthetic_small_repo to test "operator adopts DF skill, then wants to
add a custom reference."

**Operations exercised:** `init` + `docs` (the synthetic repo creates
1 trivial reference doc named `synthetic-test-ref.md` to walk the same
7-step path).

**Metric collection:** Steps-to-add-reference (manual count); install.sh
edit count (per the 7-block hidden cost); time to add 1 reference (wall
clock).

**Expected delta (before → after):**

| Metric | Before | After | Δ | Direction |
|---|---:|---:|---:|:---:|
| Steps-to-add-reference | 7 | 3 | -4 (-57%) | improve |
| install.sh edit count per reference add | 7 (block per adapter) | 0 (manifest-driven) | -7 (-100%) | improve |
| Time to add 1 reference (wall clock, median) | ~25 min | ~10 min | -15 min (-60%) | improve |
| Drift incidents (forgot 1 of 7 install.sh blocks) | observed in v8.5.0+ refresh PVs | 0 | -100% | improve |

**Pass criterion:** Δ ≥ -50% on Steps-to-add-reference AND zero
remaining manual install.sh edits per reference add.

**If no improvement on small project:** Mark verdict =
`CONDITIONAL_PASS` (large-only). Small repos rarely add references
(value derives mostly from the install.sh manifest refactor, which IS
universal). However the manifest refactor is invisible to small repos
that don't ship references — so small repos primarily benefit through
the scaffold step-reduction. The metric chain is still scriptable from
synthetic_small_repo.

## §4 — large_project_eval

**Test bed:** DevolaFlow self (this repo at v10.3.0 baseline; 14
references already present per
`scripts/sync_cursor_skill.py:55-78` MIRRORED_FILES list).

**Metric collection:** Steps-to-add-reference (DF's 7-step ceremony
above); install.sh edit count per reference add; SKILL.md line count
(must remain <500 per C-4); install.sh LOC delta (savings expected from
the manifest refactor).

**Expected delta (v10.3.0 baseline → post-patch with 1 trial reference
added via scaffold):**

| Metric | Baseline | Post-patch | Δ | Direction |
|---|---:|---:|---:|:---:|
| Steps-to-add-reference | 7 | 3 | -4 (-57%) | improve |
| install.sh edit count per reference add | 7 blocks (one per adapter) | 0 (manifest-driven) | -7 | improve |
| install.sh total LOC | ~593 (current size) | ~520 (after dedup) | -73 (-12%) | improve |
| SKILL.md line count | 460 | 461 (+1 for scaffold pointer) | +1 | preserve (<500) |
| Reference docs count | 14 | 15 (synthetic test addition) | +1 | preserve (within ≤2 cycle-cumulative budget per admission_checklist §4) |
| Time-to-add-reference (real-world median) | ~25 min | ~10 min | -15 min | improve |

**Pass criterion:** Δ ≥ -50% on Steps-to-add-reference AND install.sh
LOC reduces by ≥10% AND SKILL.md remains <500 lines.

**Side-effect check (must NOT regress):**

- All 9 install adapters (cursor, codex, claude, copilot, kimicode,
  windsurf, zed, cline, roo, local, standalone) keep working — the
  manifest-driven refactor is byte-equivalent to the existing manual
  blocks; CI regression test must verify (e.g., new
  `tests/test_install_manifest_consistency.py`).
- `tests/test_reference_size_budgets.py` continues to pass (auto-covers
  new references; no change needed).
- `tests/test_integration.py::test_skill_md_under_500_lines` continues
  to pass.
- `make check-cursor-skill` keeps exiting 0 (mirror parity, no-op when
  absent).

## §5 — benefit_metrics

**Quantified before/after table (DF-internal metrics from
`v11.0.0_evaluation_methodology.md` §4.1 + §4.4; ≥3 metrics required):**

| Metric | Source/bucket | Before (v10.3.0) | After (post-D-X-2) | Δ | Justification |
|---|---|---:|---:|---:|---|
| Steps-to-add-reference | §4.1 (operator experience) | 7 | 3 | -4 (-57%) | Scaffold collapses steps 1+2+3+6 into 1 invocation; manifest eliminates the install.sh duplication |
| install.sh edit count per reference add | §4.1 (operator experience) | 7 (per-adapter blocks) | 0 (manifest-driven) | -7 (-100%) | Single-source-of-truth refactor: MIRRORED_FILES → manifest → install.sh loop |
| install.sh LOC | §4.1 proxy + §4.6 coupling proxy | ~593 | ~520 | -73 (-12%) | Manifest refactor dedupes 7 adapter blocks into a single loop |
| Time-to-add-reference (median, min) | §4.1 (operator experience) | ~25 | ~10 | -15 (-60%) | Time saved on cross-file boilerplate |
| Drift incidents per cycle (operator forgot install.sh sync) | §4.1 (operator experience) | observed >0 in v8.5.0+ refresh cycles | 0 | -100% | Manifest is the source-of-truth; impossible to forget |

**Guarantee on metric:** ALL 5 metrics are scriptable from current DF
tooling (`wc -l`, `git log --stat`, `cycle retrospectives §4.2 grep`).
"Drift incidents" is observable via grep-pattern in retros (e.g., "forgot
install.sh" / "manifest mismatch") — though admittedly a soft signal;
the harder signal is install.sh LOC reduction (deterministic post-PR).

## §6 — admission_verdict

**Verdict: PASS**

**Rationale:**

- G-1 Internal-value: 5 quantitative DF-internal metrics show clear
  improvement; install.sh LOC reduction is the cleanest single signal.
- G-2 Both-tier: small (synthetic_small_repo `docs` operation invoking
  scaffold) AND large (DF self, 14 → 15 references) BOTH show ≥-50% on
  Steps-to-add-reference. The install.sh refactor (manifest-driven)
  benefits BOTH tiers symmetrically (every install.sh invocation reads
  the manifest, not just DF's own use). Hence PASS not CONDITIONAL_PASS.
- G-3 Zero-deps: all manipulations are inside DF (sync_cursor_skill.py
  emits manifest; install.sh consumes manifest); no external tool
  required.
- G-4 Cycle-budget: 1 PV (M effort); 6-8 tests for scaffold + 1-2 tests
  for manifest consistency = ≤10 tests; well within +30/PV W-17 cap.
- G-5 Soul-freeze: 0 Soul rule additions.
- G-6 Cache-prefix: zero edits to schemas/lean-dispatch.yaml.
- G-7 Compatibility: install.sh refactor is byte-equivalent in OUTPUT
  (each adapter still receives the same files); the per-adapter `dl_batch`
  loop body changes, but the contract is preserved. The new
  scaffold_reference.py script is pure-additive.
- G-8 Test coverage: 6-8 scaffold tests + 1-2 manifest-consistency tests;
  ≥80% module coverage per CP-2.
- G-9 Documentation completeness: CHANGELOG + W-18 lint refresh + 1-line
  SKILL.md update; matches the "Python module change" + "Schema-adjacent
  refactor" rows in §G-9. NOT a "Reference doc add" trigger because the
  scaffold script is NOT itself a reference doc.

## §7 — effort_estimate

**Effort: M (1 PV)**

**Breakdown:**

- Scaffold renderers (markdown skeleton + SKILL.md row + MIRRORED_FILES
  insertion): ~110 LOC.
- argparse + collision check + dry-run: ~50 LOC.
- W-18 lint stanza + CHANGELOG skeleton stdout printers: ~40 LOC.
- 6-8 unit tests for scaffold: ~120 LOC.
- `sync_cursor_skill.py` manifest emit (~30 LOC delta) + matching test
  (~40 LOC).
- `install.sh` manifest-consume refactor (~80 LOC removed + ~30 LOC
  added); regression test that all 9 adapters still install the same
  file set (~80 LOC test).
- Total: ~200 LOC scaffold + ~30 LOC sync_cursor_skill.py delta + ~50
  LOC install.sh delta + ~240 LOC tests ≈ ~520 LOC; 1 PV.

**Confirms §3 estimate (M / 1 PV) from `v10_internal_optimization_directions.md`
§3.3 D-X-2.**

## §8 — dependencies

**None — this patch is fully standalone.**

Synergy (NOT a hard dependency):

- D-X-1 (workflow template scaffold CLI) and D-X-2 share the
  scaffold-CLI design pattern. If both ship in v11.0.0, factor common
  argparse + dry-run + stdout-print machinery into
  `scripts/_scaffold_common.py`.
- D-X-5 (operator troubleshooting handbook) is a USE CASE for D-X-2 —
  it adds the 15th reference. If D-X-5 ships AFTER D-X-2 in the same
  cycle, D-X-5 uses D-X-2's scaffold. If D-X-5 ships FIRST, it manually
  authors the reference and is the canonical "before" baseline for
  D-X-2's PV-internal eval.
- D-D-1 (reference utilization audit) provides post-shipping evidence
  of how many references are actually needed — D-X-2 makes adding NEW
  references CHEAPER, which couples directly with D-D-1's question
  "are we adding references that won't get used?". V11.0.0 should land
  D-D-1's audit BEFORE D-X-2's scaffold goes live, so we have utilization
  data BEFORE making it easy to inflate.

## §9 — risk_register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | install.sh manifest refactor breaks one of 9 adapters silently (e.g., `dl_batch` argument order changes) → users running `curl ... | bash -s zed` get an empty install | major | Author a dedicated regression test `tests/test_install_manifest_consistency.py` that for each adapter (cursor, codex, claude, kimicode, zed, cline, roo) runs install.sh against a temp dir + asserts the FULL set of files is downloaded. Include in `make all` chain. |
| R2 | Generated W-18 lint pattern (path + anchor string) misses if the operator immediately edits the new reference body and the anchor string disappears → CI fails post-CHANGELOG | minor | The lint generator picks an anchor that's a stable structural marker (`# Purpose` heading from the skeleton); the skeleton's first non-empty H1 stays stable across edits. Document this stability rule in the script's docstring + the W-18 stanza comment. |
| R3 | Reference utilization risk (R3 from D-D-1 perspective): D-X-2 makes adding references trivially cheap → cycle could inflate the reference count past the C-4 + admission_checklist §4 cycle-cumulative ≤2 cap | major | Couple with D-D-1: scaffold script prints an INFO line at invocation time stating current reference count + utilization (if D-D-1's audit landed). Hard cap: scaffold script REFUSES to add a reference if cycle-cumulative count would exceed 2 unless `--force` is passed; the print also reminds the author of the C-4 ≤1000-line ceiling and SF-1 14-file fixed-set baseline. |
| R4 | Manifest-emit ordering must match install.sh expectations (one path per line, no comments) → if `sync_cursor_skill.py` regression introduces a comment line or whitespace, install.sh's `while read` loop misbehaves | minor | The manifest emit is one-shot deterministic from MIRRORED_FILES; bytewise round-trip test in `tests/test_install_manifest_consistency.py` asserts the manifest line count == len(MIRRORED_FILES) and each line matches the list element exactly. Failure mode is loud (test fail) not silent (broken install). |

---

ADMISSION: PASS | EFFORT: M | DEPS: none | TIER: core
