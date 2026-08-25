# @yorha-agents/devola-flow

Thin npm installer for the [DevolaFlow](https://github.com/YoRHa-Agents/DevolaFlow)
agent skill. Runs anywhere Node.js >= 18 runs — including Windows, where the
historical `curl | bash` installer (`scripts/install.sh`) is unusable.

## Usage

```bash
npx @yorha-agents/devola-flow install cursor   # -> ~/.cursor/skills/devola-flow/
npx @yorha-agents/devola-flow install claude   # -> ~/.claude/skills/devola-flow/
npx @yorha-agents/devola-flow install all

npx @yorha-agents/devola-flow update all       # overwrite + report previous -> new version
npx @yorha-agents/devola-flow doctor           # report installs, versions, manifest parity
```

Skill files are **not bundled** in this package. The installer downloads them
from GitHub raw at the tag matching the package version
(`https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/v<version>/...`),
so `npx @yorha-agents/devola-flow@16.0.0 install cursor` always installs the
v16.0.0 skill set. Set the `DEVOLA_FLOW_REF` environment variable to download
from another git ref (branch / tag / SHA) instead — useful for CI smoke tests.

## Windows support

Fully supported: the installer uses only Node built-ins (`fetch`, `fs`,
`path`, `os`) and resolves the user-level skill directories from the OS home
directory (`%USERPROFILE%\.cursor\skills\devola-flow` and
`%USERPROFILE%\.claude\skills\devola-flow` on Windows).

## Relationship to scripts/install.sh

`scripts/install.sh` (the curl+bash installer) and this package are two
entrypoints over the **same file-list source of truth**:
`workflow-system/agent/manifest.yaml` (repo rules A-5 / C-7). Both fetch the
manifest at install time and download exactly what the target's install
profile declares — neither hardcodes file lists. `install.sh` covers more
targets (codex, zed, cline, roo, ...); this package covers `cursor` and
`claude` on every OS.
