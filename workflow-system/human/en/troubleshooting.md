---
title: "Troubleshooting"
description: "Diagnose installation channels, local scaffolds, copied skills, and host bridges."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-27T11:32:38Z"
source_version: "17.5.0"
---

# Troubleshooting

Diagnose installation channels, local scaffolds, copied skills, and host bridges.

## Identify the installation channel first

**npm user install**

```bash
node --version
npx @yorha-agents/devola-flow doctor
npx @yorha-agents/devola-flow update cursor
```

Node must be 18 or newer. npm targets only user-level Cursor and Claude.
Check `DEVOLA_FLOW_REF` when the installed ref is unexpected.

### curl install

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s help
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update --force
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall --dry-run
```

Every snippet is self-contained. curl has `update` and `uninstall`, but no
doctor. Its `update` scans supported host skill-copy locations only, not the
`local` workspace or `standalone` file; rerun either explicit install target
for those surfaces. Use `devola-init-doctor --skills` only when the Python
package is also installed and you want to audit known skill paths.

### pip or wheel install

```bash
python -c "import devolaflow; print(devolaflow.__version__)"
devola-init local --mode=core
devola-init-doctor
```

Wheel-only installs support the local scaffold. If `devola-init cursor` (or
another non-local target) reports that the agent source tree is missing, clone
the repository and install editable:

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

## Local scaffold recovery

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init-doctor
sync-rules
```

`core` intentionally skips rule compilation. `standard` compiles without
examples. `full` compiles and seeds examples. Compilation repair is
`sync-rules` (or `make compile-rules` in a clone).

For global skill installation without the default plugin attempts:

```bash
devola-init cursor --global --no-plugins
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor --global --no-plugins
```

## Skill copy versus host bridge

If the skill is visible but an out-of-scope host write is not blocked, verify
the optional bridge separately. Follow the [host bridge matrix](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/agent/references/host-bridges.md),
confirm the host-specific config and event matcher, trust Codex hooks when
applicable, then test one event before persisting
`DEVOLAFLOW_HOST_ENFORCE=1`. Unsupported hosts remain skill-only.

## Workflow symptoms

- Wrong seed: state the intent explicitly or name a seed.
- One-pass execution: verify the skill is loaded and request a bounded
  multi-step change with measurable checks.
- Repeated convergence: inspect unresolved checklist assertions and blockers;
  bounded retries eventually escalate.

## Harness and archive evidence

Run `make test-harness` for deterministic contracts. W-16 settlement and W-19
cycle archive rollup are manual release-policy steps; there is no automatic
archive hook. Do not diagnose a missing automatic archive as a runtime failure.
