# Subagent Report: Adapter & Platform Expansion Gap (v5.4.2 → v6.0.0)

**Agent ID:** ae305755-a3b1-4936-a4c3-9c56496c333f  
**Date:** 2026-04-16  
**Scope:** Current adapter inventory, v5.0 proposal delta, registry & data-driven gap, new platforms

## Executive Summary

As of `__version__ = "5.4.2"`, DevolaFlow ships exactly **4 hand-written adapters** (Cursor, Codex, Claude, Copilot) and a hard-coded build loop in `build_skill.py`, with no `AdapterRegistry`, no `--tools` selective build (CLI forwards `sys.argv` but `build_all` ignores it), and no `DataDrivenAdapter` or `adapter_configs/` in the tree. The 2026 integration proposal's 16+ platform matrix remains mostly aspirational: only the original four platforms have Python adapters; KimiCode, OpenClaw, Windsurf, Zed, Cline, Roo, Continue, JetBrains, Amazon Q, Gemini, Augment, and Trae are **not implemented**. `install.sh` matches the same four targets plus `standalone`, `all`, `auto`, and `update` — none of the additional proposed platforms have installers. The highest-leverage v6.0.0 work is structural (registry + optional YAML-driven engine) before scaling many new file layouts, because today every new tool requires editing `build_skill.py` and duplicating copy/transform patterns. Changing `BaseAdapter.build()` would break all four adapters and their tests, so any registry work should preserve the current method signature or provide a compatibility shim.

## 1. Current Adapter Inventory

**Directory:** `/home/agent/workspace/DevolaFlow/src/devolaflow/adapters/`

| File | LOC | Platform | Output structure |
|------|----:|----------|------------------|
| `base.py` | 39 | (shared) | `AdapterResult`, `BaseAdapter`, `load_workflow_skill()` |
| `__init__.py` | 5 | — | No adapters |
| `cursor_adapter.py` | 73 | Cursor | `SKILL.md`; tree `references/`; tree `examples/`; `rules/workflow-hard-rules.mdc` |
| `codex_adapter.py` | 65 | OpenAI Codex | `SKILL.md` (frontmatter + body + "Hard Rules"); `agents/openai.yaml` |
| `claude_adapter.py` | 119 | Claude Code | `CLAUDE.md` (compressed); `.claude/settings.json` |
| `copilot_adapter.py` | 92 | GitHub Copilot | `.github/copilot-instructions.md`; `.github/instructions/workflow.instructions.md` |

### build_skill.py orchestration

```
adapters = [
    ("cursor", CursorAdapter()),
    ("codex", CodexAdapter()),
    ("claude", ClaudeAdapter()),
    ("copilot", CopilotAdapter()),
]
# build_skill.py:42-46
```

## 2. v5.0.0 Proposal Delta (16 Platforms)

| Platform | Implemented? | Evidence |
|----------|:-----:|----------|
| Cursor | ✅ | `cursor_adapter.py` + build_skill list |
| Codex | ✅ | `codex_adapter.py` |
| Claude | ✅ | `claude_adapter.py` |
| Copilot | ✅ | `copilot_adapter.py` |
| KimiCode | ❌ | NOT FOUND |
| OpenClaw | ❌ | NOT FOUND |
| Windsurf | ❌ | NOT FOUND |
| Zed | ❌ | NOT FOUND |
| Cline | ❌ | NOT FOUND |
| Roo Code | ❌ | NOT FOUND |
| Continue | ❌ | NOT FOUND |
| JetBrains | ❌ | NOT FOUND |
| Amazon Q | ❌ | NOT FOUND |
| Gemini | ❌ | NOT FOUND |
| Augment | ❌ | NOT FOUND |
| Trae | ❌ | NOT FOUND |

**4/16 platforms = 25% coverage** vs proposal.

## 3. AdapterRegistry Gap

| Question | Answer |
|----------|--------|
| Registry mechanism today? | **NOT FOUND** — grep for `AdapterRegistry` returns 0 matches |
| Adapter list hardcoded? | **YES** — explicit list in `build_skill.py:42-46` |
| Selective build (`build-skill --tools cursor,kimicode`)? | **NOT IMPLEMENTED** — `build_skill_cmd` passes `sys.argv[1:]` but `build_all(args)` never uses `args` |

```python
def build_all(args: Sequence[str]) -> list[AdapterResult]:
    """Build all adapter outputs from workflow-skill.yaml."""
    # args is declared but never referenced — build_skill.py:28-29
```

## 4. Data-Driven Adapter Mechanism Gap

| Artifact | Status |
|----------|--------|
| `DataDrivenAdapter` class | **NOT FOUND** |
| `adapter_configs/` directory | **NOT FOUND** |
| YAML in adapters | Partial — `base.py` loads `workflow-skill.yaml`; `codex_adapter.py` uses `yaml.dump` for openai.yaml. **No per-platform YAML configs.** |

## 5. install.sh Support

Documented targets (header + help, lines 12, 291-299): `cursor`, `codex`, `claude`, `copilot`, `standalone`, `all`, `auto`, `update`.

**Missing:** KimiCode, OpenClaw, Windsurf, Zed, Cline, Roo, Continue, JetBrains, Amazon Q, Gemini, Augment, Trae — **0 installer functions or case branches**.

## 6. New Platforms (2025-2026)

| Tool | Probable format | Probable path | Strategic value |
|------|-----------------|---------------|-----------------|
| Google Gemini CLI + Antigravity | Mix YAML + markdown | `.gemini/`, repo config | Large model ecosystem, enterprise Google Cloud |
| OpenAI Codex terminal workflows | Markdown or JSON bundles | `~/.codex` or dotdir | Risk of format drift from current adapter |
| Amazon Q Developer CLI + IDE | Markdown rules | `.amazonq/` | Enterprise AWS shops |
| OpenHands-style runners | `AGENTS.md`, YAML | Repo root / `.openhands` | CI-integrable; self-hosted teams |
| JetBrains Junie / AI Assistant | Markdown rules | `.aiassistant/rules` | Large JVM/Python IDE share |

## 7. Architectural Refactor Opportunity

### Shared boilerplate extractable

- `output_dir.mkdir(parents=True, exist_ok=True)` — every adapter
- `shutil.copytree` after `rmtree` pattern — Cursor refs/examples
- Budget checks (line/char counting) — similar across adapters
- `rules = source.get("content", {}).get("rules", [])` — Codex, Claude, Copilot

### Minimal registry surface

- Keep `build(self, source, agent_dir, output_dir) -> AdapterResult` stable
- Registry maps id → instance/factory; CLI filters keys
- Optional `metadata` (tier, install path hints) for install.sh generation

### Risks if BaseAdapter signature changes

- 4 concrete adapters break until updated
- Test construction + AdapterResult fields break
- External consumers (NOT FOUND beyond tests/docs) would need compatibility period

## v6.0.0 Adapter/Platform Candidates

| ID | Title | Scope | Effort | Measurable benefit |
|----|-------|-------|--------|---------------------|
| **R1** | AdapterRegistry + `--tools` filtering | registry; build_skill + cli | M | Selective builds; foundation for 12+ platforms |
| **D1** | DataDrivenAdapter + `adapter_configs/*.yaml` + schema validation | data-driven engine | L | New simple adapter ≈ 20 LOC YAML (vs 80 LOC Python) |
| **A1** | KimiCode adapter + install | new adapter; install.sh | S-M | +1 platform; low friction |
| **A2** | Windsurf `.windsurfrules` | new adapter | S | +1 platform; validates data-driven |
| **A3** | Continue.dev | new adapter | M | +1 platform; hybrid YAML+MD |
| **A4** | OpenClaw (file + optional manifest) | new adapter | M | +1 platform; OSS gateway |
| **I1** | install.sh parity for each shipped adapter | install.sh | M | Curl-install same set as build-skill |
| **T1** | Tests per adapter + registry contract | tests | M | Coverage floor maintained |

### Top-5 Priority

1. **R1** — AdapterRegistry + `--tools` (unblocks selective CI + multi-platform growth)
2. **D1** — Data-driven engine (aligns with unexecuted v5.0.0 proposal)
3. **A1** — KimiCode (near-zero SKILL.md alignment)
4. **A2** — Windsurf (simple flat file, validates data-driven path)
5. **A3** — Continue (hybrid YAML+MD, high OSS reach)
