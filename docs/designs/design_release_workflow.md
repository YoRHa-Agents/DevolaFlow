# Release Workflow Design

> Defines the end-to-end release process for DevolaFlow: from development through PR, version bump, git tagging, GitHub Release, and Pages deployment.

---

## 1. Overview

DevolaFlow uses a **trunk-based workflow** with short-lived feature branches
merged into `main` via Pull Requests. Releases are **tag-driven**: the
`release-prep.yml` workflow can mechanically prepare the version PR, and the
`auto-tag-release.yml` workflow tags a newly merged stable version. The local
tagging sequence remains supported for operators who do not use Actions.

```
Feature Branch: release-prep (bump → preflight) ──PR/merge──> main
                                                               │
                                              auto-tag v* (if version changed)
                                                               │
                                            verify-release-ref (ancestor gate)
                                                 ├── checks (shared CI)
                                                 └── release-extras
                                                        │
                                                     release
                                                        │
                                                  deploy-pages
```

---

## 2. Release Process — Step by Step

### 2.1 Version Bump

Phase one updates version files only:

```bash
python scripts/bump_version.py X.Y.Z --dry-run
python scripts/bump_version.py X.Y.Z
make sync-human-docs
```

Do not use `--tag` in this phase. A non-dry tag request refuses while the
current package version differs from `X.Y.Z`; this prevents a tag from pointing
at the commit before the version bump.

The source of truth is `src/devolaflow/__init__.py`. The seven canonical sync
locations are:

1. `workflow-system/agent/SKILL.md` — frontmatter, banner, and current-version text
2. `workflow-system/agent/workflow-skill.yaml` — identity version
3. `pyproject.toml` — package version
4. `scripts/generate_human_docs.py` — generated-guide source version
5. `tests/test_smoke.py` — version assertion
6. `README.md` — executable version example
7. `packages/npm/package.json` — npm installer version

Together with the source of truth, this is eight files. The README badge is
derived from `pyproject.toml`. The benchmark page derives its displayed
version from the newest `version-timeline/versions.json` entry at load time;
neither derived display is bumped by `scripts/bump_version.py`.

### 2.2 Automated Release Preparation

From the Actions tab, run `.github/workflows/release-prep.yml` on `main` with
the next stable `X.Y.Z` version. It starts from the current remote `main`,
refuses stale, dirty, duplicate-tag, duplicate-branch, and non-forward
requests, then runs:

```text
scripts/bump_version.py → make sync-human-docs → make release-preflight
```

The workflow requires a dated `## [X.Y.Z]` entry to already exist in
`CHANGELOG.md`; it never writes release-note prose. It commits only the
verified mechanical changes to a new `release/vX.Y.Z` branch and opens the
release PR with the repository `GITHUB_TOKEN`.

### 2.3 Preflight and Release Commit

Run the authoritative preflight after every generated version surface has been
updated, then commit the verified result:

```bash
make release-preflight
git add -A
git commit -m "chore: bump version to X.Y.Z"
```

Push the feature branch through the normal repository workflow, open a Pull
Request, wait for required CI and review, and merge it into protected `main`.
Do not create the release tag on the feature branch or on an unmerged local
`main` commit.

The preflight preserves the seven W-9 gates in order: `test-core` → Ruff check
→ Ruff format → `test-version` → `test-harness` → `check-cursor-skill` →
`iteration-delta-gate`. Release-only validation, adapter, documentation,
compiler, and drift checks run afterward. Once those prerequisites complete,
the preflight checks the generated demo seed catalog and builds `_site/`.

Manual checks:
- [ ] CHANGELOG.md has a section for the new version with correct date
- [ ] All seven canonical sync locations across eight files are consistent (use `python -m pytest tests/test_version.py -v`)
- [ ] All adapter outputs build within budget
- [ ] Built-in harness contracts pass: `make test-harness`
- [ ] The active W-16 harness baseline comparison has no threshold breach
- [ ] The generated seed catalog is current: `make check-demo-seed-catalog`
- [ ] The local Pages inventory builds successfully: `make build-site`

### 2.4 Tag and Push

Phase two starts only after the release PR is merged. Refresh local `main`
before asking the script to perform its read-only readiness preview:

```bash
git checkout main
git fetch origin main
git pull --ff-only origin main
python scripts/bump_version.py X.Y.Z --tag --dry-run
python scripts/bump_version.py X.Y.Z --tag
git push origin vX.Y.Z
```

The non-dry `--tag` command requires `X.Y.Z` to be committed at the current
`HEAD`, requires branch `main` and a clean tracked worktree, and refuses an
existing `vX.Y.Z` tag. When `refs/remotes/origin/main` exists, `HEAD` must
equal that fetched commit. It ignores untracked files and creates an annotated
tag at that exact verified `HEAD`; it never edits version files or creates a
commit. The dry run performs the same read-only readiness checks when the
requested version already matches, so branch, merge, cleanliness, and
duplicate-tag blockers appear before any ref is created.

After the release PR merges, a push that changes
`src/devolaflow/__init__.py` invokes `.github/workflows/auto-tag-release.yml`.
It checks the predecessor and current versions, stable tag format, current
`origin/main` SHA, and local/remote tag absence before creating an annotated
`vX.Y.Z` tag. A `GITHUB_TOKEN` tag push does not trigger workflows, so the
workflow directly calls both release workflows with the exact tag and commit
SHA. A manually pushed local tag still triggers `.github/workflows/release.yml`
normally.

The tag-triggered and reusable-call paths both run:
1. **verify-release-ref** — fetches full history plus `origin/main`, validates
   the exact tag/SHA pair, then requires
   `git merge-base --is-ancestor "$RELEASE_SHA" origin/main`
2. **checks** — after ref verification, invokes the shared CI workflow on the
   tagged SHA
3. **release-extras** — after ref verification, regenerates human docs,
   rejects generated-output drift, checks the generated seed catalog, builds
   `_site/`, and runs the documentation drift check
4. **release** — after both gates pass, creates the GitHub Release with
   auto-generated notes
5. **deploy-pages** — after the GitHub Release succeeds, checks out the tagged
   SHA, rebuilds `_site/`, uploads it, and deploys to the `github-pages`
   environment

`.github/workflows/npm-publish.yml` independently reruns the shared CI checks.
Its `publish` job then fetches `origin/main`, repeats the ancestor test, checks
tag/package version parity, and only then invokes `npm publish`.

### 2.5 Post-Release Verification

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
| `test` | full pytest with coverage, including `tests/harness`, as the standalone W-9 verification |
| `validate` | regenerate and diff human docs, check the seed catalog, build `_site/`, validate templates, build adapters, and run drift/mirror checks |
| `npm-package` | syntax and offline package smoke checks, then `npm pack --dry-run` |

### 3.2 Release Pipeline (`.github/workflows/release.yml`)

Triggers: push of tags matching `v*`, or a reusable `workflow_call` carrying
the exact `release_tag` and `release_sha`. The called path checks out the SHA
explicitly and passes it through every shared check.

| Job | Steps | Depends On |
|-----|-------|-----------|
| `verify-release-ref` | full checkout, fetch `origin/main`, ancestor check | — |
| `checks` | reusable CI checks on the tag | `verify-release-ref` |
| `release-extras` | generated-doc diff, seed-catalog check, and site build | `verify-release-ref` |
| `release` | GitHub Release (`softprops/action-gh-release`) | `checks`, `release-extras` |
| `deploy-pages` | tagged-SHA checkout → build → upload → deploy | `release` |

### 3.3 npm Publication Pipeline (`.github/workflows/npm-publish.yml`)

Triggers: push of tags matching `v*`, or a reusable `workflow_call` carrying
the exact `release_tag` and `release_sha`. The existing `NPM_TOKEN` secret is
inherited only by the auto-tag caller; no new secret is required.

| Job | Steps | Depends On |
|-----|-------|-----------|
| `checks` | reusable CI checks on the tag | — |
| `publish` | full checkout → fetch/ancestor check → tag/package parity → provenance publish | `checks` |

The workflow defaults to no permissions. Shared checks receive only
`contents: read`; publication receives `contents: read` plus
`id-token: write` for npm provenance.

### 3.4 Pages Pipeline (`.github/workflows/pages.yml`)

Triggers: site-relevant pushes to `main`, plus manual dispatch. Filters include
the human-doc and seed-catalog generators, registry and seed YAML, generated
human/demo output, design docs, site builder, and both Pages-related workflow
definitions.

The main and tag paths both serialize through the repository-wide `pages`
concurrency group. Each uses the shared site builder and official Pages
artifact/deployment actions, so a main deployment cannot race a tag
deployment.

### 3.5 Shared Site Builder (`scripts/build-site.sh`)

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

### 3.6 Version Bump Script (`scripts/bump_version.py`)

```bash
python scripts/bump_version.py 4.0.0             # phase 1: bump only
python scripts/bump_version.py 4.0.0 --dry-run   # preview phase 1
# run mandatory release-preflight, commit, open/merge the PR, then refresh main
git checkout main
git fetch origin main
git pull --ff-only origin main
python scripts/bump_version.py 4.0.0 --tag       # phase 2: tag current HEAD
python scripts/bump_version.py 4.0.0 --tag --dry-run
git push origin v4.0.0                           # push tag only
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
7. Pages auto-deploys on site-relevant merges to `main`; path filters skip
   unrelated merges

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
4. Metrics section records test count, coverage, harness evaluation evidence, adapter status

---

## 6. Retroactive Tags

For releases that were published without git tags (v0.1.0 through v3.3.0),
retroactive tags can be created from their historical merge commits:

```bash
git tag -a v3.3.0 <merge-commit-sha> -m "Release v3.3.0"
git push origin v3.3.0
```

This historical-only path deliberately does not use the current-HEAD local
finalizer. The release workflow still requires the selected merge commit to be
reachable from `origin/main` before creating a GitHub Release or deploying.
