# DevolaFlow Governance Rules Index

Layered rule system compiled to multiple AI tool formats via `src/devolaflow/local/compiler.py`.

Total rules: **50** (v8.3.0 — added S-8, S-9, A-4, C-9 in v8.2.2 patch per `.local/research/v8.3.0_design.md` §3).

| Layer | File | Priority | Always Apply | Rule count | Description |
|-------|------|----------|-------------|------------|-------------|
| Soul | `soul.mdc` | P0 | Yes | 9 (S-1..S-9) | Immutable invariants — security red lines, coverage floor, no ghost features, agent-workspace ownership (S-8) + handoff append-only (S-9) |
| Architecture | `architecture.mdc` | P1 | Yes | 4 (A-1..A-4) | Core architectural decisions — 4-layer hierarchy, context isolation, cache layout, source-of-truth spec location (A-4) |
| Conventions | `conventions.mdc` | P2 | Yes | 9 (C-1..C-9) | Coding & format standards — line budgets, lean messages, version consistency, lightweight agent workspace artifact budgets (C-9) |
| Workflow | `workflow.mdc` | P3 | No | 15 (W-1..W-15) | Development process — iteration planning, NineS analysis, benchmarks, version bumps |
| Style | `style.mdc` | P4 | No | 13 (ST-1..ST-13) | Documentation & presentation — doc sync, web experience, bilingual completeness |

## Compilation

```bash
python -c "from devolaflow.local.compiler import RuleCompiler; RuleCompiler('.rules/compile-config.yaml').compile_all()"
```

## Targets

| Target | Output | Format | Token Budget |
|--------|--------|--------|-------------|
| cursor | `.cursor/rules/repo-governance.mdc` | MDC | 8000 |
| agents_md | `AGENTS.md` | Markdown | 6000 |

## Source Mapping

Rules are migrated from `.cursor/rules/*.mdc`:

- `workflow-rules.mdc` → P1 Architecture (P1–P5)
- `devola-flow-rules.mdc` → P1 Architecture (P1–P6)
- `change-process-rules.mdc` → P0 Soul (CP-1, CP-2), P2 Conventions (CP-7), P3 Workflow (CP-3–CP-6)
- `context-optimization-rules.mdc` → P1 Architecture (CO-3), P2 Conventions (CO-1, CO-2), P0 Soul (CO-4), P3 Workflow (CO-5, CO-6)
- `self-improve-iteration-rules.mdc` → P3 Workflow (SI-1–SI-10)
- `skill-format-rules.mdc` → P2 Conventions (SF-1–SF-4), P0 Soul (SF-5), P1 Architecture (SF-6)
- `documentation-sync-rules.mdc` → P4 Style (DS-1–DS-5)
- `web-experience-rules.mdc` → P4 Style (WX-1–WX-8)
