---
title: "Integration Guide"
description: "Integrating DevolaFlow with existing tools and CI/CD pipelines."
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# Integration Guide

DevolaFlow supports four AI coding tools and three repository modes. This guide covers how to integrate with each.

## AI Tool Integration

### Quick Method: Single File

Copy `workflow-system/agent/MVP-SKILL.md` directly into your tool:

| Tool | Copy to | Notes |
|------|---------|-------|
| Cursor | `.cursor/skills/workflow-orchestrator/SKILL.md` | Loaded on intent match |
| Claude Code | `CLAUDE.md` (project root) | Always loaded at session start |
| Copilot | `.github/copilot-instructions.md` | Loaded per request |
| Codex | `~/.codex/skills/workflow-orchestrator/SKILL.md` | Loaded on intent match |

### Full Method: Build Pipeline

```bash
make build-skill
```

This generates optimized outputs for each tool in `dist/`:

- `dist/cursor/` -- SKILL.md + references + rules (.mdc)
- `dist/codex/` -- SKILL.md + agents/openai.yaml
- `dist/claude/` -- CLAUDE.md (<200 lines compressed)
- `dist/copilot/` -- copilot-instructions.md (<4000 chars)

Copy the entire `dist/<tool>/` directory to the appropriate location.

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
