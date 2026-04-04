#!/usr/bin/env bash
#
# DevolaFlow Quick Installer
#
# Install:
#   curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
#   curl -fsSL ... | bash -s cursor --global
#   curl -fsSL ... | bash -s claude
#   curl -fsSL ... | bash -s update
#
# Targets:  cursor, codex, claude, copilot, mvp, all, auto (default), update
# Flags:    --global   install to ~/.cursor/ (user-wide)
#           --project  install to .cursor/ (repo-local, default)

set -eu

REPO="YoRHa-Agents/DevolaFlow"
BRANCH="main"
BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
AGENT_BASE="${BASE}/workflow-system/agent"
CT=5
MT=15
STAMP=".devola-flow-version"

info() { printf '  \033[34m>\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; }

SCOPE="project"
TARGET="auto"
for arg in "$@"; do
  case "$arg" in
    --global)  SCOPE="global" ;;
    --project) SCOPE="project" ;;
    -*)        ;;
    *)         TARGET="$arg" ;;
  esac
done

dl() {
  local url="$1" dest="$2" name
  name=$(basename "$dest")
  mkdir -p "$(dirname "$dest")"
  if curl -fsSL --connect-timeout "$CT" --max-time "$MT" "$url" -o "$dest" </dev/null 2>/dev/null; then
    printf '    %-35s %s\n' "$name" "ok"
  else
    fail "failed: $name"
    return 1
  fi
}

stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ" > "$1/$STAMP" 2>/dev/null || true; }

# ── Installers ───────────────────────────────────────────────────

install_cursor() {
  local dir
  if [ "$SCOPE" = "global" ]; then
    dir="$HOME/.cursor/skills/devola-flow"
    info "Cursor (global) -> $dir/"
  else
    dir=".cursor/skills/devola-flow"
    info "Cursor (project) -> $dir/"
  fi

  mkdir -p "$dir/references" "$dir/examples"

  dl "$AGENT_BASE/SKILL.md" "$dir/SKILL.md"

  info "references (8 files):"
  for f in agent-hierarchy meta-framework decomposition-gate repo-modes \
           execution-protocol message-schemas team-roles context-isolation; do
    dl "$AGENT_BASE/references/${f}.md" "$dir/references/${f}.md"
  done

  info "examples (3 files):"
  for f in full-pipeline-trace hotfix-trace convergence-loop-trace; do
    dl "$AGENT_BASE/examples/${f}.md" "$dir/examples/${f}.md"
  done

  local rdir
  if [ "$SCOPE" = "global" ]; then rdir="$HOME/.cursor/rules"; else rdir=".cursor/rules"; fi
  mkdir -p "$rdir"
  dl "$BASE/.cursor/rules/workflow-rules.mdc" "$rdir/devola-flow-rules.mdc"

  stamp "$dir"
  ok "Cursor installed (SKILL.md + 8 refs + 3 examples + rules)"
}

install_codex() {
  local dir="${CODEX_HOME:-$HOME/.codex}/skills/devola-flow"
  info "Codex -> $dir/"
  mkdir -p "$dir"
  dl "$AGENT_BASE/MVP-SKILL.md" "$dir/SKILL.md"
  stamp "$dir"
  ok "Codex installed"
}

install_claude() {
  info "Claude Code -> ./CLAUDE.md"
  dl "$AGENT_BASE/MVP-SKILL.md" "CLAUDE.md"
  ok "Claude installed"
}

install_copilot() {
  info "Copilot -> .github/copilot-instructions.md"
  mkdir -p ".github"
  dl "$AGENT_BASE/MVP-SKILL.md" ".github/copilot-instructions.md"
  ok "Copilot installed"
}

install_mvp() {
  info "MVP -> devola-flow-skill.md"
  dl "$AGENT_BASE/MVP-SKILL.md" "devola-flow-skill.md"
  ok "MVP file downloaded"
}

# ── Update ───────────────────────────────────────────────────────

do_update() {
  info "Looking for existing DevolaFlow installs..."
  local found=0

  if [ -f ".cursor/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"; install_cursor; found=1
  fi
  if [ -f "$HOME/.cursor/skills/devola-flow/SKILL.md" ]; then
    SCOPE="global"; install_cursor; found=1
  fi
  local cdir="${CODEX_HOME:-$HOME/.codex}/skills/devola-flow"
  if [ -f "$cdir/SKILL.md" ]; then install_codex; found=1; fi
  if [ -f "CLAUDE.md" ] && head -5 "CLAUDE.md" | grep -q "devola-flow" 2>/dev/null; then
    install_claude; found=1
  fi
  if [ -f ".github/copilot-instructions.md" ] && head -5 ".github/copilot-instructions.md" | grep -q "devola-flow" 2>/dev/null; then
    install_copilot; found=1
  fi

  if [ "$found" -eq 0 ]; then
    warn "No existing installs found. Run: curl ... | bash -s cursor"
    return 1
  fi
}

# ── Auto-detect ──────────────────────────────────────────────────

auto_detect() {
  local found=0
  if [ -d ".cursor" ] || command -v cursor >/dev/null 2>&1; then install_cursor; found=1; fi
  if [ -d "${CODEX_HOME:-$HOME/.codex}" ]; then install_codex; found=1; fi
  if [ -d ".claude" ] || [ -f "CLAUDE.md" ]; then install_claude; found=1; fi
  if [ -d ".github" ]; then install_copilot; found=1; fi

  if [ "$found" -eq 0 ]; then
    warn "No AI tools detected. Pick one explicitly:"
    echo ""
    echo "  curl ... | bash -s cursor             project-local"
    echo "  curl ... | bash -s cursor --global    user-global"
    echo "  curl ... | bash -s claude             Claude Code"
    echo "  curl ... | bash -s copilot            GitHub Copilot"
    echo "  curl ... | bash -s mvp                download standalone file"
    echo ""
  fi
}

# ── Main ─────────────────────────────────────────────────────────

cat << 'BANNER'

  DevolaFlow Installer
  ────────────────────
BANNER
printf '  scope: %s | target: %s\n\n' "$SCOPE" "$TARGET"

case "$TARGET" in
  cursor)  install_cursor ;;
  codex)   install_codex ;;
  claude)  install_claude ;;
  copilot) install_copilot ;;
  mvp)     install_mvp ;;
  update)  do_update ;;
  all)     install_cursor; install_codex; install_claude; install_copilot ;;
  auto)    auto_detect ;;
  *)
    cat << 'USAGE'
  Usage: install.sh [target] [flags]

  Targets:
    cursor    Cursor (SKILL.md + refs + examples + rules)
    codex     Codex (MVP single-file)
    claude    Claude Code (MVP as CLAUDE.md)
    copilot   Copilot (MVP as instructions)
    mvp       Download standalone MVP-SKILL.md
    all       All tools
    update    Re-download latest to existing installs
    auto      Auto-detect (default)

  Flags:
    --project   repo-local .cursor/  (default)
    --global    user-wide ~/.cursor/

  Examples:
    curl -fsSL .../install.sh | bash -s cursor
    curl -fsSL .../install.sh | bash -s cursor --global
    curl -fsSL .../install.sh | bash -s update
USAGE
    exit 1 ;;
esac

echo ""
ok "Done. To update later: curl ... | bash -s update"
printf '  docs:  https://yorha-agents.github.io/DevolaFlow/\n'
printf '  repo:  https://github.com/%s\n\n' "$REPO"
