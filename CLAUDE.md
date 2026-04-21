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
- `tests/` — Pytest suite (822+ tests)
- `benchmarks/` — EvoBench context density benchmarks
- `schemas/` — YAML message schemas
- `scripts/` — Version bump, doc generation, install

## Conventions

- Python 3.11+, ruff for lint/format, pytest for tests
- Coverage floor: 80% (`pyproject.toml [tool.coverage]`)
- Version tracked across 7 canonical sync locations (8 files, rooted in `src/devolaflow/__init__.py`) — use `scripts/bump_version.py`
- All paths in agent-facing files must be relative to repo root
