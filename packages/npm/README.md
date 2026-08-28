# @yorha-agents/devola-flow

Thin, zero-dependency npm installer for the
[DevolaFlow](https://github.com/YoRHa-Agents/DevolaFlow) agent skill. It
requires Node 18 or newer and works on Windows.

## Scope

This package installs the five maintained user-level skill profiles:

- Cursor: `~/.cursor/skills/devola-flow/`
- Claude: `~/.claude/skills/devola-flow/`
- Codex: `$CODEX_HOME/skills/devola-flow/` (or `~/.codex/skills/devola-flow/`)
- KimiCode: `~/.kimi/skills/devola-flow/`
- DSH: `$DSH_HOME/skills/devola-flow/` (or `~/.dsh/skills/devola-flow/`)

npm `all` means these five targets. It does not mean the broader target set
supported by the repository's curl installer, and it does not include
Copilot's project-level rule-file installation.

## Install, update, and doctor

```bash
npx @yorha-agents/devola-flow install cursor
npx @yorha-agents/devola-flow install claude
npx @yorha-agents/devola-flow install all

npx @yorha-agents/devola-flow update cursor
npx @yorha-agents/devola-flow update all
npx @yorha-agents/devola-flow doctor
```

`doctor` reports all five supported user locations, installed version stamps,
and file parity against `workflow-system/agent/manifest.yaml`.

## Download ref and file list

Skill files are not bundled in the npm tarball. By default, the installer
downloads from the git tag matching the package version. Set
`DEVOLA_FLOW_REF` to intentionally use another branch, tag, or SHA:

```bash
DEVOLA_FLOW_REF=main npx @yorha-agents/devola-flow install cursor
```

The target file list is derived from the manifest at that same ref. This keeps
the npm package, curl installer, and source checkout on one profile contract.

## More targets and Python tooling

For project-local installation, Copilot, Windsurf, Zed, Cline, Roo, local
workspace scaffolding, or Python doctor commands, use the canonical repository
guides:

- [Quickstart](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/human/en/quickstart.md)
- [Integration guide](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/human/en/integration-guide.md)
- [Troubleshooting](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/human/en/troubleshooting.md)
