---
title: "Integration Guide"
description: "Integrating DevolaFlow with existing tools and CI/CD pipelines."
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-05T00:00:00Z"
source_version: "1.0.0"
---

# Integration Guide

DevolaFlow supports four AI coding tools and three repository modes. This guide covers how to integrate with each.

## AI Tool Integration

### Fastest: One Command

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

curl -fsSL $INSTALLER | bash -s cursor            # project-local
curl -fsSL $INSTALLER | bash -s cursor --global    # user-global (~/.cursor/)
curl -fsSL $INSTALLER | bash -s claude             # Claude Code (project-local)
curl -fsSL $INSTALLER | bash -s claude --global    # Claude Code (user-global ~/.claude/CLAUDE.md)
curl -fsSL $INSTALLER | bash -s copilot            # Copilot
curl -fsSL $INSTALLER | bash -s update             # update existing installs
```

### Alternative: pip + devola-init

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init cursor               # auto-copies skill files to .cursor/skills/devola-flow/
devola-init claude --global      # installs to ~/.claude/CLAUDE.md
```

### Manual: Single File

Download [MVP-SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/MVP-SKILL.md) and copy to:

| Tool | Project-local | User-global |
|------|--------------|-------------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` | `~/.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `./CLAUDE.md` | `~/.claude/CLAUDE.md` |
| Copilot | `.github/copilot-instructions.md` | -- |
| Codex | -- | `~/.codex/skills/devola-flow/SKILL.md` |

### Full Build Pipeline (for contributors)

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git && cd DevolaFlow
pip install -e ".[dev]"
make build-skill    # generates dist/cursor/, dist/codex/, dist/claude/, dist/copilot/
```

## Repository Mode Integration

DevolaFlow auto-detects your repository type:

```bash
detect-repo-mode    # prints: local, github, gitlab, gitea, bitbucket, or generic
```

### Local Mode

No CI/CD. All validation runs locally via Make:

```bash
make all    # lint + test + validate-templates + build-skill + check-drift
```

### GitHub Mode

DevolaFlow ships with ready-to-use GitHub Actions:

- `.github/workflows/ci.yml` -- lint, test, validate on every push/PR
- `.github/workflows/release.yml` -- build + test + release + Pages deploy on tag

Push a tag to trigger a release:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

### GitLab / Other Git

Adapt the CI templates from `doc/designs/design_repo_modes.md` section 4.3 to your platform's CI config format.

## Drift Detection

Keep human docs in sync with agent source:

```bash
make check-drift    # reports stale human docs
make sync-human-docs    # regenerate from agent source
```
