# v15-ADR-008 — Rule-Corpus History Appendix (v15.0.0 Rule Diet)

* **Status**: ACCEPTED (executes ratified v15-ADR-004 D3 — the v15.0.0 rule-diet)
* **Date**: 2026-06-12
* **Cycle**: v15.0.0 MAJOR rollup, task `v15.0.0-T3-rule-diet`
* **Companion**: `.local/research/adr/v15-ADR-004-rule-cap-denominator-and-rule-diet.md`
  (denominator = full `.rules/` corpus; cap 60 HARD; diet target ≤ 55)

This appendix is the C-3-verbatim landing zone for two diet operations:

1. **§1 Fold map** — W-10..W-15 (pure CP-*/CO-* mirror rules) folded into their
   coupled owners. Every MUST-level obligation survives verbatim at the
   absorbing rule; the retired ids are NOT reused (C-8 precedent, v14.2.1 G-012).
2. **§2 Source-narrative strip** — multi-line `Source:` / history / per-cycle
   narrative blocks moved here VERBATIM from the rule bodies (S-8/S-9/S-10,
   A-4..A-7, C-9, W-16..W-24). Each stripped rule body keeps a one-line
   `Source: v15-ADR-008 §<rule-id>.` pointer.

Rule census after the diet: Soul 10 + Architecture 7 + Conventions 8 +
Workflow 18 + Style 13 = **56** (was 62; cap 60 HARD now has 4 slots headroom).
The ADR-004 target of ≤ 55 is NOT reachable from the ADR-sanctioned fold set
alone (C-8 −1 already landed v14.2.1; W-10..W-15 −6 lands here; no other fold
is authorized without dropping obligations) — 56 is the safe stop, documented
per the diet's "zero obligations dropped" constraint.

---

## §1 Fold map (W-10..W-15 → absorbing owners)

Redirect table — update citations to retired ids via this mapping:

| Retired rule | Mirror of | Absorbing rule | Obligation checklist (all survive verbatim) |
|---|---|---|---|
| W-10 — Version Bump Protocol | CP-3 | **C-6 — Version Consistency** | (1) bump updates ALL tracked locations via `scripts/bump_version.py`; (2) verify with `python -m pytest tests/test_version.py -v` |
| W-11 — Gate Module Changes | CP-4 | **W-4 — Benchmark Regression Guard** | (1) changes to `src/devolaflow/gate/` require the full gate test suite `python -m pytest tests/test_gate.py -v` |
| W-12 — SKILL Changes Require Adapter Build | CP-5 | **W-5 — Skill Format Coupling** | (1) SKILL.md / CLAUDE.md / workflow-skill.yaml changes require `build-skill`; (2) the 4 core adapters (Cursor, Codex, Claude, Copilot) + the registered data-driven adapter set (`adapter_configs/*.yaml`) build successfully; (3) all stay within their budgets |
| W-13 — Context Optimization Benchmarks | CP-6 | **W-4 — Benchmark Regression Guard** | (1) changes to `task_adaptive_selector.py`, `context_profiles.yaml`, or lean message schemas require `python -m pytest tests/test_benchmarks.py -v` — already W-4's verbatim trigger set + command (pure duplicate; zero text loss) |
| W-14 — Benchmark Verification | CO-5 | **W-4 — Benchmark Regression Guard** | (1) context optimization changes must demonstrate improvement (or no regression) via EvoBench benchmarks; (2) baseline metrics are stored in `benchmarks/devolaflow_context/baselines/` |
| W-15 — Section Relevance | CO-6 | **W-6 — Context Budget Enforcement** | (1) task-type-relevant sections marked `critical`, unrelated sections `skip`; (2) verify by running `task_adaptive_selector.py <task_type> --verbose` and inspecting skipped sections |

Downstream id-reference updates landed with the fold (trivial waivers,
single-file < 20 lines each):

* `workflow-system/agent/context_profiles.yaml` `meta.agents_md_slice.profiles`:
  `hotfix`/`review` lists swap `W-11` → `W-4`; `feature`/`refactor` lists drop
  the retired `W-10`..`W-15` ids.
* `tests/test_pv07_agents_md_slice.py`: hotfix slice expectation `W-11` → `W-4`;
  Workflow layer-count pin 24 → 18.
* `workflow-system/human/demo/index.html`: "62 Repository Rules" → "56".

Historical artifacts (`.local/research/`, `docs/cycle-archive/`, deprecated
pointer stubs under `.cursor/rules/`) intentionally keep their original
W-10..W-15 citations — interpret via this redirect table. The legacy stubs'
"CP-3 → W-10 / CP-4 → W-11 / CP-5 → W-12 / CP-6 → W-13 / CO-5 → W-14 /
CO-6 → W-15" mappings now chain through this table to C-6 / W-4 / W-5 / W-6.

## §2 Stripped Source-narrative blocks (verbatim)

### §S-8

> Source: v8.3.0 design.md §3.1 — closes gap H-002 from v8.3.0_gap_analysis.md.
> The `change-driven` workflow ships in v8.2.6; this rule is forward-defined so
> that when v8.2.6 lands, agents already know the constraint.

### §S-9

> Enforcement: `tests/test_handoff_envelope_immutable.py` lints CI runs (lands
> in v8.2.4 with the schema package); `lifecycle/check_envelope_append_only`
> hook blocks at write time in STRICT mode.
>
> Source: v8.3.0 design.md §3.2 — closes gap H-002 from v8.3.0_gap_analysis.md.

(The rule body keeps the enforcement sentence; only the "(lands in v8.2.4 with
the schema package)" shipping-history parenthetical moved here.)

### §S-10

> v8.4.4 ships a permissive no-op default to
> preserve cache bytes; the actual content lands in PV-07 with the
> rule-corpus selectivity slice.
>
> Source: v9.0.0 PV-04 — closes C-03 from
> `.local/research/v9.0.0_gap_analysis.md` §3.1; full rationale in
> `.local/research/adr/v9-ADR-004-lifecycle-wiring-and-s10.md`.

### §A-4

> Source: v8.3.0 design.md §3.4 — closes gap M-004 from v8.3.0_gap_analysis.md
> (in part — full closure happens when v8.2.5 ArchiveManager.propose_merge ships).

### §A-5

The "v8.4.3 baseline" registry table was refreshed to the live census (the
AST test `tests/ghost/test_registries.py` is the live inventory; the rule
table now mirrors `_SSOT_PYTHON_REGISTRIES` + `_SSOT_YAML_REGISTRIES`).
Original frozen table header: "The current 5 SSOT registries (v8.4.3 baseline)".

Stripped §A-5.3 — Staged Rollout (entire subsection, history-only):

> A-5 ships **strict** at v8.4.3 (PV-03 of v9.0.0 cycle): the parity
> tests are wired and pass green against the existing 5 registries
> because no current `DEFAULT_ALLOWLIST` entry collides with a domain-
> SSOT name (R-3 mitigation NOT required at v8.4.3 cut). Per
> `.local/research/adr/v9-ADR-003-a5-ssot-registry.md` §"Staged
> rollout", the contingency informational-then-strict path documented
> there fires only if a future PV introduces an existing-allowlist /
> new-registry collision; at v8.4.3 the strict guard is the live
> default.

Stripped trailing Source block:

> Source: v9.0.0 SI-1 gap analysis §5.3 (PV-03 owned-files manifest);
> v9.0.0 reference review F-13 closure (3 of the 5 registries surface
> in `references/shell-proxy.md` §11).

### §A-6

> Source: v9.2.0 cycle plan §PV-02 (v9.1.2 PATCH). Closes M-007 from
> the v9.0.0 retrospective §3.3 (operator-facing slash command surface
> was telegraphed).

### §A-7

> Source: v11.1.0 PV-05 cycle close per
> `.local/research/v11.1.0_cycle_plan.md` §3 PV-05; closes
> `.local/research/v11.1.0_gap_analysis.md` §3 G-TEST-1 + G-AUDIT-1 +
> G-BENCH-1. The W-21 Soul-set freeze remains preserved at 10 entries;
> this landing is at Architecture (A-7), per ADR-007 §"Soul-vs-Architecture"
> decision-rule on conditional + implementation-coupled invariants.

### §C-9

> (The `lint` module ships in v8.2.5; the `lint_human` entry point + the
> `.local/human/` rows ship in v14.0.0.)
>
> Source: v8.3.0 design.md §3.3 — closes gap H-003 from v8.3.0_gap_analysis.md.
> Human rows: v14.0.0 design.md §4c — see `references/human-surface.md` §4c.

(The live cross-reference to `references/human-surface.md` §4c stays in the
rule body; only the design-history citations moved here.)

### §W-16

Stripped from the v12.3.0 PV-04 clarification paragraph (the normative
contract sentence + the "v12.3.0 PV-04 clarification" anchor stay in the body):

> (per v12.2.0 retrospective §4.2 learning): […] The v12.2.0 cycle is the
> canonical "regen-at-close" example: PV-01 attempted the regen but the
> v12.1.0 baseline stayed GREEN throughout PV-02 → PV-04, so the wholesale
> regen was DEFERRED to cycle close (and turned out to be a no-op because no
> PV drifted the equilibrium). The earlier "MUST at cycle start" wording
> over-prescribed; […] This preserves the original anti-piecemeal-drift
> intent without forcing unnecessary regen overhead.

> Source: `.local/research/v8.4.0_retrospective.md` §"R-7 wholesale-vs-piecemeal baseline lesson"; v12.3.0 PV-04 clarification per `.local/research/v12.2.0_retrospective.md` §4.2 + `.local/research/v12.3.0_gap_analysis.md` §2 D-3.

### §W-17

> flagged by the v8.0.0 retrospective §3.4 (where the cycle added 743 tests
> but coverage stayed at 80% — many tests were redundant scaffolding).
>
> Source: v9.0.0 PV-05 spec — codified per `.local/research/v9.0.0_pv05_design.md` §5.

### §W-18

> This sequencing prevents the v8.4.x-era pattern where CHANGELOG entries
> cited "feature X ships in PV-N" but the ghost audit had no coverage
> assertion for X — the audit silently passed because it was never asked.
>
> Source: v9.0.0 PV-05 spec — codified per `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2. Package split: v14.3.0 per `.local/research/adr/v15-ADR-001-ghost-audit-decomposition.md`.

### §W-19

Stripped rationale bullets (the archive mechanism, format, and timing stay in
the body):

> * Future cycle-N+1 SI-1 planning gates can reference cycle-N research without depending on `.local/` (which is gitignored on most clones).
> * External reviewers / new contributors can read the design history without needing the cycle author's local clone.
> * The retrospective (W-7 / SI-8) has a stable archive URL to cite from `CHANGELOG.md`.
>
> Source: v9.0.0 PV-05 spec — codified per `.local/research/v9.0.0_pv05_design.md` §3.

### §W-20

> Source: v9.0.0 PV-05 spec — codified per `.local/research/v9.0.0_pv05_design.md` §3 + `references/env-flags.md` §7.

### §W-21

> Any proposed S-11 must be telegraphed in v9.0.0's retrospective
> (deferred to v9.2.0 — cycle N+2), gap-analysed in v9.2.0 SI-1, and pass
> v9.2.0 L0's SI-3 §3.2 ≥ 9.5/10.
>
> Source: v9.0.0 PV-07 — codified per
> `.local/research/adr/v9-ADR-007-rule-rebalancing-and-rollup.md` D4
> (Soul-set freeze governance).

### §W-22

> Source: v11.3.0 SI-1 gap analysis §4 P1.5 + §5 risks R-7 +
> R-11 (`.local/research/v11.3.0_gap_analysis.md`).

### §W-23

> Source: v11.3.0 SI-1 gap analysis §4 P1.5 +
> `workflow-system/agent/references/domain-awareness.md`
> (`.local/research/v11.3.0_gap_analysis.md`).

### §W-24

> Source: v11.4.0 SI-1 gap analysis §4 + §5 + §7 + §8 risk register
> (`.local/research/v11.4.0_subagent_pattern_analysis.md`); upstream
> philschmid article at `https://www.philschmid.de/subagent-patterns-2026`.

## §3 W-set telegraph (ADR-004 D5 — "consider, not bind")

Evaluated inside this diet PR per ADR-004 D5: ADOPT as authoring guidance,
NOT as a new rule. A NEW W-rule proposal should cite (a) the SI-1 gap entry,
(b) why no existing W-rule covers it, and (c) the post-addition full-corpus
census vs the 60 HARD cap — the strict full-corpus re-pin in
`tests/ghost/test_rules.py::test_rule_count_under_cap` now makes any addition
visible at CI time, which is the enforcement surface the telegraph needs.
Binding W-21-style cadence for W-rules is deferred (would have been a new
rule, against the diet's purpose).
