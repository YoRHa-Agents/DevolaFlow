# @yorha-agents/devola-flow

Thin, zero-npm-dependency installer for the
[DevolaFlow](https://github.com/YoRHa-Agents/DevolaFlow) agent skill. It
requires Node 18 or newer and works on Windows. The installer also provisions
the matching Python runtime through uv.

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
npm install -g @yorha-agents/devola-flow@22.1.1
devola-flow install all

devola-flow update cursor
devola-flow update all
devola-flow doctor
```

`install` and `update` install skill files and provision Python 3.13 through
uv, pinned to the matching `v22.1.1` source tag. If uv bootstrap or runtime
installation is unavailable, skill files remain usable as `docs-only`; the
command prints a copyable repair command. Use `--no-runtime` for an explicit
docs-only install. `doctor` reports runtime state for all five locations and
file parity against `workflow-system/agent/manifest.yaml`.

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

For project-local installation, Copilot, Windsurf, Zed, Cline, Roo, or local
workspace scaffolding, use the canonical repository guides. Runtime console
commands such as `devola-local-archive`, `devola-init-doctor`, and
`devola-version` are available after a full-runtime install. On systems whose
Python is older than 3.11, use the uv-managed runtime rather than system pip:

```bash
uv tool install --force --python 3.13 \
  'devolaflow @ git+https://github.com/YoRHa-Agents/DevolaFlow.git@v22.1.1'
```

For explicit `python -m devolaflow.*` execution, use
`uv run --with 'devolaflow @ git+https://github.com/YoRHa-Agents/DevolaFlow.git@v22.1.1'`
followed by the module command. See the canonical repository guides:

- [Quickstart](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/human/en/quickstart.md)
- [Integration guide](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/human/en/integration-guide.md)
- [Troubleshooting](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/human/en/troubleshooting.md)
