---
name: devola-flow-repo
description: >
  DevolaFlow repository — composable workflow meta-framework for multi-agent
  orchestration. Use the /devola-flow skill for workflow execution.
---

# DevolaFlow Repository

Use the **devola-flow** skill (`/devola-flow` or auto-activated) for workflow orchestration.
Install the skill via: `curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude`

## Build & Test

```bash
python -m pytest tests/ -q                    # run all tests
ruff check src/ tests/                        # lint
ruff format --check src/ tests/               # format check
python -m pytest tests/test_version.py -v     # version consistency
python -m pytest tests/test_benchmarks.py -v  # EvoBench benchmarks
```

## Project Structure

- `src/devolaflow/` — Python package (gate, template_engine, nines, adapters)
- `workflow-system/agent/` — SKILL.md, references, templates, context profiles
- `workflow-system/human/` — Human docs (EN/ZH), demo pages
- `tests/` — Pytest suite (`python -m pytest tests/ -q` prints the live count)
- `benchmarks/` — EvoBench context density benchmarks
- `schemas/` — YAML message schemas
- `scripts/` — Version bump, doc generation, install

## Rules

DevolaFlow's governance rules live in **`.rules/`** (5 layered `.mdc` files: soul, architecture,
conventions, workflow, style). They are compiled to three distribution targets:

- **`AGENTS.md`** (repo root) — the canonical Markdown corpus loaded by Claude Code, Codex,
  KimiCode, Cline, Roo, and any AGENTS.md-aware tool. Read this for the full rule body.
- **`.cursor/rules/repo-governance.mdc`** — the same corpus rendered as MDC for Cursor.
- **`docs/STYLE-RULES.md`** — the P4 Style layer (ST-1..ST-13) alone, as an on-demand
  tool-agnostic view; AGENTS.md ends with a one-line pointer to it. Consult when editing
  human-facing docs, the web demo, or bilingual content.

To edit a rule: modify the relevant `.rules/<layer>.mdc` source, then recompile:

```bash
make compile-rules    # wraps the sync-rules console script
```

`make all` and `make release-preflight` invoke `compile-rules` automatically; CI's
`tests/test_no_ghost_features.py::test_rule_surfaces_compile_only` blocks any merge
that hand-edits the compiled outputs (drift detection via `.rules/.compile-hashes.json`).

## Conventions

- Python 3.11+, ruff for lint/format, pytest for tests
- Coverage floor: 80% (`pyproject.toml [tool.coverage]`)
- Version tracked across 6 canonical sync locations (7 files, rooted in `src/devolaflow/__init__.py`) — use `scripts/bump_version.py`; README badge + benchmark-demo version are render/load-time derived per C-6
- All paths in agent-facing files must be relative to repo root
