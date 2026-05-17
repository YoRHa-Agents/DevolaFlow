#!/usr/bin/env bash
# Local-source mirror of `scripts/install.sh cursor --global` AND
# `scripts/install.sh claude --global`. Copies files from the local
# repo (no network) into ~/.cursor/skills/devola-flow/ and
# ~/.claude/skills/devola-flow/ + the matching rules.
#
# Use when the canonical curl-based installer cannot reach
# raw.githubusercontent.com (sandboxed environments).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
AGENT="$REPO_ROOT/workflow-system/agent"
RULES_SRC="$REPO_ROOT/.cursor/rules/workflow-rules.mdc"
VERSION_FILE="$REPO_ROOT/src/devolaflow/__init__.py"
VERSION="$(grep -E '^__version__' "$VERSION_FILE" | sed -E 's/.*"([^"]+)".*/\1/')"
STAMP_NAME=".devola-flow-version"
TIMESTAMP="$(date -Iseconds)"

REFERENCES=(
  "references/agent-hierarchy.md"
  "references/meta-framework.md"
  "references/decomposition-gate.md"
  "references/repo-modes.md"
  "references/execution-protocol.md"
  "references/message-schemas.md"
  "references/team-roles.md"
  "references/context-isolation.md"
)

EXAMPLES=(
  "examples/full-pipeline-trace.md"
  "examples/hotfix-trace.md"
  "examples/convergence-loop-trace.md"
)

info() { printf '  > %s\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
errf() { printf '  ✗ %s\n' "$*" >&2; }

copy_file() {
  local src="$1" dst="$2"
  if [ ! -f "$src" ]; then
    warn "missing source: $src"
    return 1
  fi
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
}

stamp_dir() {
  local dir="$1"
  printf '%s\n%s\n' "$VERSION" "$TIMESTAMP" > "$dir/$STAMP_NAME"
}

install_one() {
  local label="$1" dir="$2"
  info "$label -> $dir/"
  rm -rf "$dir/references" "$dir/examples"
  mkdir -p "$dir/references" "$dir/examples"

  copy_file "$AGENT/SKILL.md" "$dir/SKILL.md" || return 1
  ok "SKILL.md copied"

  info "references (${#REFERENCES[@]} files):"
  for rel in "${REFERENCES[@]}"; do
    copy_file "$AGENT/$rel" "$dir/$rel"
  done
  ok "references copied"

  info "examples (${#EXAMPLES[@]} files):"
  for rel in "${EXAMPLES[@]}"; do
    copy_file "$AGENT/$rel" "$dir/$rel"
  done
  ok "examples copied"

  stamp_dir "$dir"
  ok "$label installed (v$VERSION)"
}

main() {
  echo "DevolaFlow local-source installer"
  echo "  source repo : $REPO_ROOT"
  echo "  source ver  : v$VERSION"
  echo

  install_one "Cursor (global)" "$HOME/.cursor/skills/devola-flow"

  local rules_dir="$HOME/.cursor/rules"
  mkdir -p "$rules_dir"
  copy_file "$RULES_SRC" "$rules_dir/devola-flow-rules.mdc"
  ok "Cursor rules copied to $rules_dir/devola-flow-rules.mdc"

  echo
  install_one "Claude Code (global)" "$HOME/.claude/skills/devola-flow"

  echo
  ok "Done."
}

main "$@"
