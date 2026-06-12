# DevolaFlow Governance Rules Index

Layered rule system compiled to multiple AI tool formats via `src/devolaflow/local/compiler.py`.

Total rules: **56** (cap 60 HARD applies to the FULL on-disk `.rules/` corpus — all 5 layers including Style — per v15-ADR-004, which amends ADR-007 D5's compiled-AGENTS.md denominator; 4 slots headroom. v14.2.1 removed dead rule C-8 per G-012; v15.0.0 rule-diet folded W-10..W-15 into W-4/W-5/W-6/C-6 per v15-ADR-004 — retired ids NOT renumbered/reused; fold map + stripped Source narrative live in `.local/research/adr/v15-ADR-008-rule-corpus-history-appendix.md`).

| Layer | File | Priority | Always Apply | Rule count | Description |
|-------|------|----------|-------------|------------|-------------|
| Soul | `soul.mdc` | P0 | Yes | 10 (S-1..S-10) | Immutable invariants — security red lines, coverage floor, no ghost features, agent-workspace ownership (S-8), handoff append-only (S-9), prompt-side governance contract embedding (S-10). **Frozen at 10 entries per W-21 (ADR-007 D4).** |
| Architecture | `architecture.mdc` | P1 | Yes | 7 (A-1..A-7) | Core architectural decisions — 4-layer hierarchy (A-1), cache layout governance v2 (A-2), token budgets (A-3), source-of-truth spec location (A-4), single-source-of-truth registry pattern (A-5 — added v8.4.3 PV-03 per ADR-003), workspace engagement auto-activation (A-6 — added v9.1.2 PV-02), cascade-depth invariant (A-7 — added v11.1.0 PV-04/PV-05) |
| Conventions | `conventions.mdc` | P2 | Yes | 8 (C-1..C-7, C-9) | Coding & format standards — line budgets, lean messages, version consistency, lightweight agent workspace artifact budgets (C-9). C-8 (C++ braces) removed v14.2.1 per G-012 (dead rule — zero C++ files in repo); remaining ids NOT renumbered. |
| Workflow | `workflow.mdc` | P3 | No | 18 (W-1..W-9, W-16..W-24) | Development process — iteration planning, NineS analysis, benchmarks, ghost-audit refresh, cycle archive, env-flag reuse, Soul-set freeze governance, grill mode, domain glossary, subagent-pattern selection. W-10..W-15 retired by the v15.0.0 rule-diet fold (W-10→C-6, W-11/W-13/W-14→W-4, W-12→W-5, W-15→W-6 per v15-ADR-004 / v15-ADR-008 §1); retired ids NOT reused. |
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

> Token budgets are sourced from `.rules/compile-config.yaml` — bumped from 8000/6000 to 12000/12000 in v9.0.0 PV-07 per ADR-007 D5; bumped 12000 → 14000 in v11.4.0 (cursor + agents_md parity bump) to absorb the new W-24 Subagent Pattern Selection rule. Pre-v11.4.0 cursor utilization was 11979/12000 (saturated; W-24 push silently dropped the Style Rules layer); post-bump 12740/14000 (~9% headroom; all 5 layers preserved). See `.local/research/v11.4.0_subagent_pattern_analysis.md`.

## Source Mapping

Rules were migrated from the legacy `.cursor/rules/*.mdc` files. As of v14.2.1
(G-008) all six fully-migrated legacy files are deprecated pointer stubs
(registered in `devolaflow.local.drift::DEPRECATED_STUB_FILES`); the two
P4 Style sources (`documentation-sync-rules.mdc`, `web-experience-rules.mdc`)
remain in place as on-demand rule files. Original mapping:

- `workflow-rules.mdc` → P1 Architecture (P1–P5)
- `devola-flow-rules.mdc` → P1 Architecture (P1–P6)
- `change-process-rules.mdc` → P0 Soul (CP-1, CP-2), P2 Conventions (CP-7), P3 Workflow (CP-3–CP-6)
- `context-optimization-rules.mdc` → P1 Architecture (CO-3), P2 Conventions (CO-1, CO-2), P0 Soul (CO-4), P3 Workflow (CO-5, CO-6)
- `self-improve-iteration-rules.mdc` → P3 Workflow (SI-1–SI-10)
- `skill-format-rules.mdc` → P2 Conventions (SF-1–SF-4), P0 Soul (SF-5), P1 Architecture (SF-6)
- `documentation-sync-rules.mdc` → P4 Style (DS-1–DS-5)
- `web-experience-rules.mdc` → P4 Style (WX-1–WX-8)
