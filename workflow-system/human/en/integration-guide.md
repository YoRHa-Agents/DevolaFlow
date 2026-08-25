---
title: "Integration Guide"
description: "Manifest-derived host profiles, installation channels, and optional host bridges."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T12:29:02Z"
source_version: "17.0.0"
---

# Integration Guide

Manifest-derived host profiles, installation channels, and optional host bridges.

## Manifest-derived install profiles

The profile names and file sets below come from
`workflow-system/agent/manifest.yaml`. The `references` set currently contains
26 files; consumers derive the list from the manifest.

| Target | Manifest kind | File sets |
|---|---|---|
| `cursor` | `skill-dir` | `core`, `references`, `examples` |
| `claude` | `skill-dir` | `core`, `references`, `examples` |
| `codex` | `skill-dir` | `core`, `references` |
| `kimicode` | `skill-dir` | `core`, `references`, `examples` |
| `copilot` | `rule-file` | `core` |
| `windsurf` | `rule-file` | `core` |
| `zed` | `rule-tree` | `core`, `references` |
| `cline` | `rule-tree` | `core`, `references` |
| `roo` | `rule-tree` | `core`, `references` |

## Channel scope

| Channel | Scope and `all` meaning |
|---|---|
| npm/npx | User-level `cursor`, `claude`, or both via npm `all` |
| curl | Project by default; supported host targets plus separate `local` and `standalone` targets; `--global` where supported; curl `all` installs all supported hosts plus `local` and excludes `standalone` |
| pip/wheel | Runtime CLIs and `devola-init local`; non-local skill copy needs a clone plus editable install |
| Python source | `devola-init all` means Cursor, Claude, Copilot, and Codex; it excludes `local` |

```bash
# Complete, self-contained curl examples
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude --global --no-plugins
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s kimicode
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s zed
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cline
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s roo
```

## Local workspace modes and plugins

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init cursor --global --no-plugins
```

`core` skips compilation and examples, `standard` compiles without examples,
and `full` compiles and seeds examples. Global curl/Python installs attempt
runtime plugins by default; `--no-plugins` keeps only skill files. Plugin
installation is separate from whether the host can discover the copied skill.

## Doctor and update boundaries

```bash
npx @yorha-agents/devola-flow doctor
devola-init-doctor
devola-init-doctor --skills
npx @yorha-agents/devola-flow update all
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s local
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s standalone
```

The first doctor checks npm-supported user locations. The second checks the
current Python workspace. The third scans known copied-skill locations. There
is no curl doctor. curl `update` scans supported host skill-copy locations
only; it does not scan the `local` workspace or `standalone` file. Rerun the
explicit `local` or `standalone` install target for those surfaces.

## Optional host bridge enforcement

Skill copy makes Markdown discoverable. A host bridge separately routes
Cursor, Claude Code, Codex, KimiCode, or DSH tool events through lifecycle
boundary enforcement. Windsurf, Zed, Cline, Roo, and Copilot profiles do not
claim bridge support.

Follow the [host-specific bridge procedure](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/agent/references/host-bridges.md). For example:

```bash
python -m devolaflow.hostbridge install cursor
python -m devolaflow.hostbridge install claude
python -m devolaflow.hostbridge install codex
```

Confirm the host config is active (including Codex `/hooks` trust), exercise
one known-allowed event with a one-shot enforcement environment, and inspect
`.local/telemetry/hostbridge.jsonl`. Only then persist:

```bash
export DEVOLAFLOW_HOST_ENFORCE=1
```

Unsupported hosts remain skill-only; do not describe them as enforced.
