# v15-ADR-002 — Template Registry Phase B Collapse (23 → 7 survivors + composition manifest)

* **Status**: PROPOSED (L0/human ratifies; v15.0.0 executes "IF its ADR approves" per ladder skeleton)
* **Date**: 2026-06-12
* **Cycle**: v14.2.0 T5 (SI-1 planning gate for the v14.2.x → v15.0.0 ladder)
* **Feeds**: F-P2-1 (major), F-P2-3, F-P2-4 per `.local/research/v15-cycle_design_review_product.md`
  §2/§2.1/§7 ADR-1; gap G-017
* **3-condition gate** (verbatim from the product review §7): "Hard to reverse: deletes 16 public
  yaml files and bumps registry schema v1.0 → v2.0; downstream `.workflow/config.yaml`
  `workflow_type:` references break without the alias layer. Surprising: selection keywords keep
  working while the yamls vanish. Real trade-off: per-template explicitness & greppability vs
  4-surface sync cost and 27% utilization." → **qualifies**.

## Context

SKILL.md §"Template Quick-Reference" lists **23** templates, of which **16** carry `(legacy)`
(not 14 as previously briefed). `templates/builtin/hotfix.yaml` line 1: "`# DEPRECATED in
v11.0.0; will be removed in v12.0.0`" — the same header sits on all 16 legacy yamls, and
v12.0.0, v13.0.0, v14.0.0 and v14.1.0 have shipped with all 16 still registered, listed, and
routed. D-A-2 measured "**6 templates** [USED] … **16 templates** [REGISTERED-BUT-UNUSED] …
**27% utilization rate**" and §8 telegraphed "Phase B … schema bump v1.0 → v2.0 … a future
cycle's SI-1 work". Each template costs 4 sync surfaces (yaml, registry.yaml, SKILL selection
table, SKILL quick-ref) — the root cause of the F-P2-2 four-surface stage-count drift.

## Decision (recommended)

Execute Phase B at **v15.0.0** (MAJOR — the removal has been telegraphed since v11.0.0):

1. **Survivor set (7 yamls)** per product review §2.1: `change-driven`, `repo-init`,
   `self-update`, `skill-optimization`, `migration`, `web-design`, `nines-assisted`
   (the last flagged as a candidate to fold into `self-update` at v15.x — defer that fold).
2. **`compositions:` block in `templates/registry.yaml`** (schema v1.0 → v2.0): each of the 16
   legacy names becomes `base` + parameter overrides expressible with the 5 operators in
   `meta-framework.md` §5 (e.g. `hotfix` → `change-driven(gate=standard, stages={propose:triage,
   apply:fix, verify:test}, timeout=hotfix)`; `dependency-setup` → `change-driven(mode=install)`
   — D-A-2 §2 Phase B example, verbatim).
3. **Alias layer for ≥ 1 MAJOR**: legacy `workflow_type:` values in `.workflow/config.yaml`
   resolve to their composition with a deprecation WARNING (S-5: no silent rewrite). Hard
   removal of aliases no earlier than v16.0.0.
4. **Operator-intent preservation**: the SKILL.md selection table keeps ALL intent keyword rows;
   its third column becomes `survivor(params)` instead of a template name. Also remove the 2
   non-template rows (`shell-proxy`, `grill-driven`) per F-P2-4.
5. **Interim (v14.2.x)**: correct the stale "will be removed in v12.0.0" headers on all 16
   legacy yamls to cite this ADR + the v15.0.0 target, so the deprecation contract stops lying.

## Consequences

### Positive
* Registry maintenance drops from 23 yamls × 4 surfaces to 7 yamls + 1 manifest; the F-P2-2
  drift class loses most of its surface.
* The lapsed deprecation promise is finally honored; operators see an honest selection table.
* Compositions make the parameterization explicit and diffable (vs 16 near-clone yamls).

### Negative
* Registry schema bump v1.0 → v2.0 — loader, `validate-templates`, and template tests change;
  composition resolution needs its own test fixture set (~8–10 NEW tests, offset by deleting
  the 16 legacy templates' per-yaml tests — net likely negative per W-17).
* Greppability regression: "what stages does hotfix run?" now requires resolving a composition.
  Mitigated by a `devola-init`-style `--explain <name>` resolver or generated catalog (which
  also fixes F-P2-2 permanently by deriving docs from resolution).

### Neutral
* No dispatch-schema impact (canonical_order 17 untouched); template selection is upstream of
  dispatch.

## Alternatives considered

* **A1 — Delete the 16 outright, no aliases**: simplest, but breaks every existing
  `.workflow/config.yaml` in operator repos with no migration signal — violates the spirit of
  the alias precedent set by prior renames. Rejected.
* **A2 — Keep all 23, just fix the headers**: zero churn, but permanently institutionalizes
  27% utilization and the 4-surface sync cost; the deprecation contract has already lapsed 3
  majors — keeping it lapsed erodes every other deprecation promise. Rejected.
* **A3 — Collapse to `change-driven` only (1 survivor)**: over-collapse; `migration` (cutover/
  deploy semantics), `web-design` (plugin-bound refine↔verify), `repo-init` (install-time, fires
  via `devola-init`) and `self-update` have genuinely distinct lifecycle shapes. Rejected.
* **A4 — Land at v14.5.0 instead of v15.0.0**: removal of public surfaces belongs in a MAJOR per
  semver expectations and the ladder skeleton; v14.x rungs are already budgeted. Rejected.
