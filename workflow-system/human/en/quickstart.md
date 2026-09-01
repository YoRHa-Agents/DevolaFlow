---
title: "Quick Start Guide"
description: "Install DevolaFlow, verify the correct channel, and run a first checklist workflow."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-09-01T07:32:53Z"
source_version: "24.2.0"
---

# Quick Start Guide

Install DevolaFlow, verify the correct channel, and run a first checklist workflow.

## 1. Choose an installation channel

The channels do not have identical scope.

### npm / npx: user-level Cursor and Claude

Requires Node 18 or newer and works on Windows. The npm meaning of `all` is
only the two user-level targets supported by this package: Cursor and Claude.

```bash
npx @yorha-agents/devola-flow install cursor
npx @yorha-agents/devola-flow install claude
npx @yorha-agents/devola-flow install all
npx @yorha-agents/devola-flow doctor
```

Downloads default to the tag matching the npm package version. Set
`DEVOLA_FLOW_REF` only when you intentionally need a branch, tag, or SHA.

### curl: broader project/global target set

The curl installer defaults to project scope and supports every target listed
by its `help`, including Cursor, Claude, Codex, Copilot, KimiCode, Windsurf,
Zed, Cline, Roo, `local`, and `standalone`.

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude --global
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s all
```

The curl `all` target installs every supported host target plus the `local`
scaffold; it excludes `standalone`. Some hosts are project-only even when
`--global` is requested. A global install also attempts the default-bundled
runtime plugins; Codegraph and impeccable are bundled, while optional plugin
ui-pro remains explicit-only.
Add `--no-plugins` for skill files only. The curl installer has no doctor command.

### pip or wheel: Python runtime and local scaffold

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project
devola-init local --mode=standard
```

A wheel provides the Python runtime, CLIs, and `devola-init local`. It does not
bundle `workflow-system/agent/`, so wheel-only installs cannot copy non-local
host skills.

For `devola-init cursor`, `claude`, `copilot`, `codex`, or `all`, use a source
checkout plus an editable install:

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

The Python meaning of `all` is Cursor, Claude, Copilot, and Codex; it excludes
the local scaffold. With `--global`, default-bundled plugin installation is
attempted unless `--no-plugins` is present. Codegraph and impeccable are
bundled; optional plugin ui-pro remains explicit-only.

**Manual fallback**

Copying only
[`SKILL.md`](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md)
can make basic instructions visible, but it omits the manifest-declared
references and examples. Prefer a channel above for a complete profile.

## 2. Verify the right surface

```bash
# npm-supported user installs and manifest parity
npx @yorha-agents/devola-flow doctor

# Python local workspace structure
devola-init-doctor

# Python audit of known copied-skill locations
devola-init-doctor --skills
```

Skill-copy success does not prove host bridge wiring. Host bridges are an
optional, separate enforcement layer; see the [host bridge reference](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/agent/references/host-bridges.md).
Install the host-specific bridge, verify one supported event reaches the
bridge, and only then persist `DEVOLAFLOW_HOST_ENFORCE=1`.

## 3. Run the first checklist workflow

Open the installed AI host and make a natural-language request:

```text
Fix the login timeout bug and verify the regression.
```

Expected flow:

1. DevolaFlow selects one of the 28 registry-derived
   checklist seeds as decomposition knowledge.
2. You confirm the goal, measurable checklist, P0/P1/P2 priorities, and
   preflight decisions.
3. The sole `change-driven` runtime executes bounded rounds through
   L0 Project → L1 Wave → L2 Task.
4. Tasks return evidence in StatusReports; L0 checks items only after
   verification.

No workflow runner CLI is required.

## 4. Update by channel

```bash
# npm user-level Cursor/Claude copies
npx @yorha-agents/devola-flow update all

# curl-supported host skill copies; --force re-downloads matching stamps
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# local workspace and standalone file: rerun the explicit install target
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s local
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s standalone

# Python runtime or wheel
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init local --mode=standard

# source checkout and copied host skills
git pull
pip install -e ".[dev]"
devola-init cursor
```

curl `update` scans supported host skill-copy locations only. It does not scan
the `local` workspace or `standalone` file; rerun the explicit install target
for either surface. Updating the Python package does not silently refresh
previously copied host skills.
