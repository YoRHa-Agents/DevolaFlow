# DevolaFlow Governance Rules Index

Layered rule system compiled to multiple AI tool formats via `src/devolaflow/local/compiler.py`.

Total rules: **57** (cap 60 HARD applies to the FULL on-disk `.rules/` corpus — all 5 layers including Style — per v15-ADR-004, which amends ADR-007 D5's compiled-AGENTS.md denominator; 3 slots headroom. v14.2.1 removed dead rule C-8 per G-012; v15.0.0 rule-diet folded W-10..W-15 into W-4/W-5/W-6/C-6 per v15-ADR-004 — retired ids NOT renumbered/reused; fold map + stripped Source narrative live in `docs/cycle-archive/adr/v15-ADR-008-rule-corpus-history-appendix.md`).

| Layer | File | Priority | Always Apply | Rule count | Description |
|-------|------|----------|-------------|------------|-------------|
| Soul | `soul.mdc` | P0 | Yes | 10 (S-1..S-10) | Immutable invariants — security red lines, coverage floor, no ghost features, agent-workspace ownership (S-8), handoff append-only (S-9), prompt-side governance contract embedding (S-10). **Frozen at 10 entries per W-21 (ADR-007 D4).** |
| Architecture | `architecture.mdc` | P1 | Yes | 7 (A-1..A-7) | Core architectural decisions — 3-layer Project → Wave → Task hierarchy (A-1), cache layout governance v2 (A-2), token budgets (A-3), source-of-truth spec location (A-4), single-source-of-truth registry pattern (A-5 — added v8.4.3 PV-03 per ADR-003), workspace engagement auto-activation (A-6 — added v9.1.2 PV-02), cascade-depth invariant (A-7 — added v11.1.0 PV-04/PV-05) |
| Conventions | `conventions.mdc` | P2 | Yes | 8 (C-1..C-7, C-9) | Coding & format standards — line budgets, lean messages, version consistency, lightweight agent workspace artifact budgets (C-9). C-8 (C++ braces) removed v14.2.1 per G-012 (dead rule — zero C++ files in repo); remaining ids NOT renumbered. |
| Workflow | `workflow.mdc` | P3 | No | 19 (W-1..W-9, W-16..W-25) | Development process — iteration planning, built-in harness analysis and baseline settlement, ghost-audit refresh, cycle archive, env-flag reuse, Soul-set freeze governance, grill mode, domain glossary, subagent-pattern selection, and Host Support Contract evidence. W-10..W-15 retired by the v15.0.0 rule-diet fold (W-10→C-6, W-11/W-13/W-14→W-4, W-12→W-5, W-15→W-6 per v15-ADR-004 / v15-ADR-008 §1); retired ids NOT reused. |
| Style | `style.mdc` | P4 | No | 13 (ST-1..ST-13) | Documentation & presentation — doc sync, web experience, bilingual completeness |

## Compilation

```bash
python -c "from devolaflow.local.compiler import RuleCompiler; RuleCompiler('.rules/compile-config.yaml').compile_all()"
```

## Targets

| Target | Output | Format | Token Budget |
|--------|--------|--------|-------------|
| cursor | `.cursor/rules/repo-governance.mdc` | MDC | 14000 |
| agents_md | `AGENTS.md` | Markdown | 14000 |
| style_md | `docs/STYLE-RULES.md` | Markdown | 4000 |

> Token budgets are sourced from `.rules/compile-config.yaml` — bumped from 8000/6000 to 12000/12000 in v9.0.0 PV-07 per ADR-007 D5; bumped 12000 → 14000 in v11.4.0 (cursor + agents_md parity bump) to absorb the new W-24 Subagent Pattern Selection rule. Pre-v11.4.0 cursor utilization was 11979/12000 (saturated; W-24 push silently dropped the Style Rules layer); post-bump 12740/14000 (~9% headroom; all 5 layers preserved). See `docs/cycle-archive/v11.4.0/other/v11.4.0_subagent_pattern_analysis.md`.
>
> The third target `style_md` (added in the v15.0.x series — clean_repo C2-1, decision D2) renders the P4 Style layer ALONE into the tool-agnostic on-demand view `docs/STYLE-RULES.md` (token_budget 4000 ≈ 50% headroom over the ~2K-token layer). The `agents_md` target emits a one-line `postscript` pointer ("Style (P4) rules: see `docs/STYLE-RULES.md`") after its compiled body so AGENTS.md-aware tools discover the Style corpus without loading it into every session (A-1 P2 / A-3). Drift-hash coverage is automatic — `check_rules_drift` enumerates the `targets` map.

## Source Mapping

Rules were migrated from the legacy `.cursor/rules/*.mdc` files. The six
fully-migrated legacy files (`workflow-rules` / `devola-flow-rules` /
`change-process-rules` / `context-optimization-rules` /
`self-improve-iteration-rules` / `skill-format-rules`) were demoted to
deprecated pointer stubs (v9.0.0 PV-07 / v14.2.1 G-008) and **retired
2026-08-19 in the v15.0.0 series** (clean_repo C1-2, decision D1 — dated
retirement record in the CHANGELOG; resurrection blocked by
`tests/ghost/test_rules.py::test_rule_surfaces_compile_only`; the SI-* /
CP-* / CO-* / SF-* → S-*/A-*/C-*/W-* lineage lives in
`docs/cycle-archive/adr/v15-ADR-008-rule-corpus-history-appendix.md`).
The two hand-maintained P4 Style on-demand copies
(`documentation-sync-rules.mdc` → DS-1–DS-5, `web-experience-rules.mdc`
→ WX-1–WX-8) were **retired 2026-08-19 in the v15.0.x series**
(clean_repo C2-1, decision D2 — they carried no hash/drift protection
and had demonstrably drifted from the canonical corpus). Their absorbed
content lives in `.rules/style.mdc` (ST-1..ST-13) and compiles to the
tool-agnostic `docs/STYLE-RULES.md` (the `style_md` target) in addition
to the always-loaded `repo-governance.mdc`; `AGENTS.md` carries a
one-line postscript pointer to it. `.cursor/rules/` is now exactly one
file: the compiled `repo-governance.mdc`.
