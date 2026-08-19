# Release Workflow Design

> Defines the end-to-end release process for DevolaFlow: from development through PR, version bump, git tagging, GitHub Release, and Pages deployment.

---

## 1. Overview

DevolaFlow uses a **trunk-based workflow** with short-lived feature branches merged into `main` via Pull Requests. Releases are **tag-driven**: pushing a `v*` tag to `main` triggers the automated release pipeline (GitHub Release creation + GitHub Pages deployment).

```
Feature Branch ──PR──> main ──tag v*──> Release Workflow
                                          ├── test (human-docs, drift, EvoBench, lint, pytest, validate, build-skill)
                                          ├── release (GitHub Release with auto-generated notes)
                                          └── deploy-pages (build _site/ → GitHub Pages)
```

---

## 2. Release Process — Step by Step

### 2.1 Pre-Release Checklist

Before starting a release, verify all quality gates pass:

```bash
make release-preflight
```

This runs: lint → test → validate-templates → build-skill → sync-human-docs → check-drift.

Manual checks:
- [ ] CHANGELOG.md has a section for the new version with correct date
- [ ] All 16 version locations are consistent (use `python -m pytest tests/test_version.py -v`)
- [ ] All adapter outputs build within budget
- [ ] EvoBench benchmarks show no regressions: `python -m pytest tests/test_benchmarks.py -v`

### 2.2 Version Bump

```bash
python scripts/bump_version.py X.Y.Z --tag
```

This updates all version locations AND creates an annotated git tag `vX.Y.Z`. Use `--dry-run` first to preview:

```bash
python scripts/bump_version.py X.Y.Z --tag --dry-run
```

Locations updated by `bump_version.py` (11 patterns across 8 files — see `bump_version.py` `VERSION_LOCATIONS` for the canonical list):
1. `src/devolaflow/__init__.py` — `__version__` (source of truth)
2. `pyproject.toml` — `version`
3. `workflow-system/agent/SKILL.md` — frontmatter `version:`, banner, body "Current version:" (3 patterns)
4. `workflow-system/agent/workflow-skill.yaml` — identity `version:`
5. `scripts/generate_human_docs.py` — `SOURCE_VERSION`
6. `tests/test_smoke.py` — version assertion
7. `README.md` — badge and version example (2 patterns)
8. `workflow-system/human/demo/benchmark-results/index.html` — `SAMPLE_DATA.version`

See `scripts/bump_version.py` for the full pattern list.

After bumping, also run `make sync-human-docs` to propagate version into generated doc files.

### 2.3 Commit and Push

```bash
git add -A
git commit -m "chore: bump version to X.Y.Z"
git push origin main --tags
```

Pushing the tag triggers `.github/workflows/release.yml`:
1. **test** — regenerates human docs, checks drift, runs EvoBench benchmarks, runs lint, runs pytest with coverage, validates templates, and builds skill adapters
2. **release** — creates GitHub Release with auto-generated notes (from PR titles since last tag)
3. **deploy-pages** — builds site via `scripts/build-site.sh` and deploys to GitHub Pages

### 2.4 Post-Release Verification

After the release workflow completes:
- [ ] GitHub Release page shows correct tag and generated notes
- [ ] GitHub Pages site is updated: https://yorha-agents.github.io/DevolaFlow/
- [ ] `pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git` installs the new version
- [ ] Download links on the demo page serve updated SKILL files

---

## 3. Automation Components

### 3.1 CI Pipeline (`.github/workflows/ci.yml`)

Triggers: push to `main`, PR to `main`.

| Job | Steps |
|-----|-------|
| `check` | ruff format --check, ruff check |
| `test` | pytest with coverage, EvoBench benchmarks |
| `validate` | validate-template --all, build-skill, check-drift |

### 3.2 Release Pipeline (`.github/workflows/release.yml`)

Triggers: push of tags matching `v*`.

| Job | Steps | Depends On |
|-----|-------|-----------|
| `test` | sync-human-docs, check-drift, EvoBench, lint, pytest, validate-template, build-skill | — |
| `release` | GitHub Release (softprops/action-gh-release) | test |
| `deploy-pages` | build-site.sh → upload → deploy | release |

### 3.3 Pages Pipeline (`.github/workflows/pages.yml`)

Triggers: push to `main`, manual dispatch.

Deploys the same site content as the release pipeline, ensuring Pages stay current with every `main` push (not just releases).

### 3.4 Shared Site Builder (`scripts/build-site.sh`)

Single source of truth for the `_site/` layout. Used by both `pages.yml` and `release.yml` to prevent drift between release and continuous deployments.

```
_site/
├── (demo pages — landing)
├── docs-en/     ← workflow-system/human/en/*.md
├── docs-zh/     ← workflow-system/human/zh/*.md
├── designs/     ← docs/designs/*.md
├── download/    ← SKILL.md
└── templates/   ← builtin/*.yaml
```

### 3.5 Version Bump Script (`scripts/bump_version.py`)

```bash
python scripts/bump_version.py 4.0.0           # bump only
python scripts/bump_version.py 4.0.0 --tag     # bump + create annotated git tag
python scripts/bump_version.py 4.0.0 --dry-run # preview changes
```

---

## 4. Branch & PR Strategy

### 4.1 Branch Naming

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat/` | New features | `feat/v3.4.0-release-workflow` |
| `fix/` | Bug fixes | `fix/installer-path-resolution` |
| `docs/` | Documentation only | `docs/v3.3.0-readme-update` |
| `refactor/` | Code restructuring | `refactor/consolidate-adapters` |
| `chore/` | Maintenance | `chore/update-dependencies` |
| `test/` | Test improvements | `test/gate-edge-cases` |

### 4.2 Commit Convention

Uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add user role middleware
fix: resolve JWT token expiry edge case
docs: update integration guide for Copilot
test: add convergence loop benchmark
chore: bump version to 3.4.0
```

### 4.3 PR Workflow

1. Create feature branch from `main`
2. Implement changes following repository rules (`.cursor/rules/`)
3. Run `make all` locally to verify
4. Open PR using the PR template (`.github/PULL_REQUEST_TEMPLATE.md`)
5. CI runs automatically on PR (lint, test, validate)
6. Review, address feedback, merge to `main`
7. Pages auto-deploy on merge

### 4.4 Release Cadence

No fixed schedule. Releases are cut when a meaningful set of changes is ready:
- **Patch (X.Y.Z+1)**: Bug fixes, minor doc updates
- **Minor (X.Y+1.0)**: New features, workflow additions, profile expansion
- **Major (X+1.0.0)**: Breaking changes to SKILL format, schema changes, hierarchy redesign

---

## 5. CHANGELOG Maintenance

Format: [Keep a Changelog](https://keepachangelog.com/) with Semantic Versioning.

### Required Sections

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Modifications to existing features

### Fixed
- Bug fixes

### Metrics
- Test counts, coverage, benchmark scores
```

### Rules

1. Every PR with user-visible changes must update CHANGELOG.md (rule CP-1)
2. Version sections are ordered newest-first
3. Dates use ISO 8601 (YYYY-MM-DD)
4. Metrics section records test count, coverage, EvoBench scores, adapter status

---

## 6. Retroactive Tags

For releases that were published without git tags (v0.1.0 through v3.3.0), retroactive tags can be created from the merge commits:

```bash
git tag -a v3.3.0 <merge-commit-sha> -m "Release v3.3.0"
git push origin v3.3.0
```

This enables the release workflow to create GitHub Releases for historical versions.
