# DevolaFlow Governance Rules Index

Layered rule system compiled to multiple AI tool formats via `src/devolaflow/local/compiler.py`.

Total rules: **51** (cap 60 HARD applies to the FULL on-disk `.rules/` corpus — all 5 layers including Style — per v15-ADR-004, which amends ADR-007 D5's compiled-AGENTS.md denominator; 9 slots headroom. v14.2.1 removed dead rule C-8 per G-012; v15.0.0 rule-diet folded W-10..W-15 into W-4/W-5/W-6/C-6 per v15-ADR-004 — v19.0.0 folded only approved duplicate headings while retaining their clauses; retired ids NOT renumbered/reused; fold map + stripped Source narrative live in `docs/cycle-archive/adr/v15-ADR-008-rule-corpus-history-appendix.md`).

| Layer | File | Priority | Always Apply | Rule count | Description |
|-------|------|----------|-------------|------------|-------------|
| Soul | `soul.mdc` | P0 | Yes | 10 (S-1..S-10) | Immutable invariants — security red lines, coverage floor, no ghost features, agent-workspace ownership (S-8), handoff append-only (S-9), prompt-side governance contract embedding (S-10). **Frozen at 10 entries per W-21 (ADR-007 D4).** |
| Architecture | `architecture.mdc` | P1 | Yes | 7 (A-1..A-7) | Core architectural decisions — 3-layer Project → Wave → Task hierarchy (A-1), cache layout governance v2 (A-2), token budgets (A-3), source-of-truth spec location (A-4), single-source-of-truth registry pattern (A-5 — added v8.4.3 PV-03 per ADR-003), workspace engagement auto-activation (A-6 — added v9.1.2 PV-02), cascade-depth invariant (A-7 — added v11.1.0 PV-04/PV-05) |
| Conventions | `conventions.mdc` | P2 | Yes | 5 (C-1, C-2, C-4, C-6, C-7) | Coding & format standards — pre-commit, lean/verbatim messages, version consistency, and line/frontmatter/agent-workspace artifact budgets. C-8 (C++ braces) removed v14.2.1 per G-012 (dead rule — zero C++ files in repo); remaining ids NOT renumbered. |
| Workflow | `workflow.mdc` | P3 | No | 22 (W-1..W-9, W-16..W-18, W-20..W-29) | Development process — iteration planning, harness analysis and settlement, retrospective/cycle archive, ghost-audit refresh, env-flag reuse, Soul-set freeze governance, grill mode, domain glossary, subagent-pattern selection, Host Support Contract evidence, local-archive safety, and Retro-Digest evidence/consent. W-10..W-15 retired by the v15.0.0 rule-diet fold (W-10→C-6, W-11/W-13/W-14→W-4, W-12→W-5, W-15→W-6 per v15-ADR-004 / v15-ADR-008 §1); W-19 is folded into W-7; retired ids NOT reused. |
| Style | `style.mdc` | P4 | No | 7 (ST-1, ST-2, ST-3, ST-4, ST-6, ST-8, ST-11) | Documentation & presentation — doc registry/demo consistency, visual identity, bilingual completeness, version propagation, showcase navigation/design-system obligations, and SKILL-to-showcase cascade |

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

## v19.0.0 Rule Lineage

The following counted headings were consolidated only after their normative
clauses, references, and enforcement mappings were retained under the listed
owner. Retired identifiers remain lineage labels and are not renumbered or
reused.

| Retained owner | Folded heading | Preserved contract |
|---|---|---|
| A-1 | A-1/P1 duplicate prohibition | S-1 pointer plus all P1–P5 hierarchy clauses and budgets |
| C-2 | C-3 | lean structured messages and verbatim extraction |
| C-4 | C-5, C-9 | frontmatter, agent-workspace, and human-surface budgets |
| W-7 | W-19 | retrospective, W-16 ordering, archive layout, and idempotence |
| ST-1 | ST-5 | human-facing registry and demo consistency checklist |
| ST-3 | ST-12 | guide and showcase bilingual parity |
| ST-4 | ST-7 | literal version locations and derived timeline behavior |
| ST-6 | ST-13 | showcase routes, CTA links, and graph integrity |
| ST-8 | ST-9, ST-10 | motion, token, and component showcase cases |

`A-3`/`W-6`, `C-1`/`W-9`, and `W-22`/`W-23` remain separate discoverable
headings. `ST-11` remains separate. W-26, W-27, and W-28 remain independent
local-archive rules.

## v19.0.0 Local-Archive Enforcement Map

| Rule | Canonical reference | Enforcement |
|---|---|---|
| W-26 | `workflow-system/agent/references/local-archive.md` §§6–7 | `src/devolaflow/local/archive.py`; `tests/test_local_archive.py`; `tests/ghost/test_features_v17_5.py` |
| W-27 | `workflow-system/agent/references/local-archive.md` §8 | `src/devolaflow/local/archive.py::append_mapping_record`; `tests/test_local_archive.py::test_mapping_append_only_and_no_clobber`; `tests/ghost/test_rules.py` |
| W-28 | `workflow-system/agent/references/local-archive.md` §8 | `src/devolaflow/local/archive.py::render_index` / `_validate_index_target`; `tests/test_local_archive.py`; `tests/ghost/test_rules.py` |
| W-29 | `workflow-system/agent/references/retro-digest.md` | `src/devolaflow/skills/retro_digest.py`; `tests/test_retro_digest.py`; `tests/ghost/test_features_v20_1.py` |
