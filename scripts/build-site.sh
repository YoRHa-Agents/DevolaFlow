#!/usr/bin/env bash
# Shared site builder for GitHub Pages — used by both pages.yml and release.yml
# Produces _site/ with demo, docs (en/zh), designs, downloads, and templates.
# NOTE (OPT-4): the cp inventory below is mirrored by the `paths:` filter in
# .github/workflows/pages.yml — update that filter whenever a cp line changes.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="${REPO_ROOT}/_site"

rm -rf "$SITE"
mkdir -p "$SITE"

# Demo pages (landing page)
cp -r "$REPO_ROOT/workflow-system/human/demo/"* "$SITE/"

# EN docs
mkdir -p "$SITE/docs-en"
cp "$REPO_ROOT/workflow-system/human/en/"*.md "$SITE/docs-en/"

# ZH docs
mkdir -p "$SITE/docs-zh"
cp "$REPO_ROOT/workflow-system/human/zh/"*.md "$SITE/docs-zh/"

# Design docs
mkdir -p "$SITE/designs"
cp "$REPO_ROOT/docs/designs/"*.md "$SITE/designs/"

# Downloadable skill files
mkdir -p "$SITE/download"
cp "$REPO_ROOT/workflow-system/agent/SKILL.md" "$SITE/download/"

# Templates for architecture page
mkdir -p "$SITE/templates"
cp "$REPO_ROOT/workflow-system/agent/templates/builtin/"*.yaml "$SITE/templates/" 2>/dev/null || true

echo "Site built → $SITE  ($(find "$SITE" -type f | wc -l) files)"
