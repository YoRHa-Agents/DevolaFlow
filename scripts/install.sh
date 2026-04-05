#!/usr/bin/env bash
#
# DevolaFlow Quick Installer
#
# Install:
#   curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
#   curl -fsSL ... | bash -s cursor --global
#   curl -fsSL ... | bash -s claude
#   curl -fsSL ... | bash -s claude --global
#   curl -fsSL ... | bash -s update
#
# Targets:  cursor, codex, claude, copilot, mvp, all, auto (default), update
# Flags:    --global   install to the tool's user-wide location
#           --project  install to the repo-local location (default)

set -u

REPO="YoRHa-Agents/DevolaFlow"
BRANCH="main"
BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
AGENT_BASE="${BASE}/workflow-system/agent"
STAMP=".devola-flow-version"

info() { printf '  \033[34m>\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
errf() { printf '  \033[31m✗\033[0m %s\n' "$*"; }

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
  local url="$1" dest="$2" name attempt
  name=$(basename "$dest")
  mkdir -p "$(dirname "$dest")"

  for attempt in 1 2 3; do
    if curl -fsSL --connect-timeout 10 --max-time 30 --retry 2 "$url" -o "$dest" </dev/null 2>/dev/null; then
      printf '    %-35s %s\n' "$name" "ok"
      return 0
    fi
    if [ "$attempt" -lt 3 ]; then
      sleep 1
    fi
  done

  errf "failed: $name (after 3 attempts)"
  return 1
}

dl_batch() {
  local dest_dir="$1"
  shift
  local total=$#
  local ok_count=0
  local fail_count=0

  for name in "$@"; do
    if dl "${AGENT_BASE}/${name}" "${dest_dir}/${name}"; then
      ok_count=$((ok_count + 1))
    else
      fail_count=$((fail_count + 1))
    fi
  done

  if [ "$fail_count" -gt 0 ]; then
    warn "${fail_count}/${total} files failed (${ok_count} succeeded)"
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

  dl "$AGENT_BASE/SKILL.md" "$dir/SKILL.md" || true

  info "references (8 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md"

  info "examples (3 files):"
  dl_batch "$dir" \
    "examples/full-pipeline-trace.md" \
    "examples/hotfix-trace.md" \
    "examples/convergence-loop-trace.md"

  local rdir
  if [ "$SCOPE" = "global" ]; then rdir="$HOME/.cursor/rules"; else rdir=".cursor/rules"; fi
  mkdir -p "$rdir"
  dl "$BASE/.cursor/rules/workflow-rules.mdc" "$rdir/devola-flow-rules.mdc" || true

  stamp "$dir"
  ok "Cursor installed (SKILL.md + 8 refs + 3 examples + rules)"
}

install_codex() {
  local dir="${CODEX_HOME:-$HOME/.codex}/skills/devola-flow"
  info "Codex -> $dir/"
  mkdir -p "$dir"
  dl "$AGENT_BASE/MVP-SKILL.md" "$dir/SKILL.md" || true
  stamp "$dir"
  ok "Codex installed"
}

install_claude() {
  local dest
  if [ "$SCOPE" = "global" ]; then
    dest="$HOME/.claude/CLAUDE.md"
    info "Claude Code (global) -> $dest"
  else
    dest="CLAUDE.md"
    info "Claude Code (project) -> ./$dest"
  fi

  dl "$AGENT_BASE/MVP-SKILL.md" "$dest" || true
  ok "Claude installed"
}

install_copilot() {
  info "Copilot -> .github/copilot-instructions.md"
  mkdir -p ".github"
  dl "$AGENT_BASE/MVP-SKILL.md" ".github/copilot-instructions.md" || true
  ok "Copilot installed"
}

install_mvp() {
  info "MVP -> devola-flow-skill.md"
  dl "$AGENT_BASE/MVP-SKILL.md" "devola-flow-skill.md" || true
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
  if [ -f "CLAUDE.md" ] && head -5 "CLAUDE.md" 2>/dev/null | grep -q "devola-flow"; then
    install_claude; found=1
  fi
  if [ -f "$HOME/.claude/CLAUDE.md" ] && head -5 "$HOME/.claude/CLAUDE.md" 2>/dev/null | grep -q "devola-flow"; then
    SCOPE="global"; install_claude; found=1
  fi
  if [ -f ".github/copilot-instructions.md" ] && head -5 ".github/copilot-instructions.md" 2>/dev/null | grep -q "devola-flow"; then
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
  if [ -d ".claude" ] || [ -f "CLAUDE.md" ]; then
    SCOPE="project"; install_claude; found=1
  elif [ -f "$HOME/.claude/CLAUDE.md" ] || [ -d "$HOME/.claude" ]; then
    SCOPE="global"; install_claude; found=1
  fi
  if [ -d ".github" ]; then install_copilot; found=1; fi

  if [ "$found" -eq 0 ]; then
    warn "No AI tools detected. Pick one:"
    echo ""
    echo "  curl ... | bash -s cursor             project-local"
    echo "  curl ... | bash -s cursor --global    user-global"
    echo "  curl ... | bash -s claude             Claude Code (project-local)"
    echo "  curl ... | bash -s claude --global    Claude Code (user-global)"
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
  help|--help|-h)
    cat << USAGE
  Usage: install.sh [target] [flags]

  Targets:
    cursor    Cursor (SKILL.md + refs + examples + rules)
    codex     Codex (MVP single-file)
    claude    Claude Code (MVP as CLAUDE.md / ~/.claude/CLAUDE.md)
    copilot   Copilot (MVP as instructions)
    mvp       Download standalone MVP-SKILL.md
    all       All tools
    update    Re-download latest to existing installs
    auto      Auto-detect (default)

  Flags:
    --project   repo-local install path (default)
    --global    user-wide install path when supported
USAGE
    exit 0 ;;
  *)
    errf "Unknown target: $TARGET"
    echo "  Run with 'help' to see options."
    exit 1 ;;
esac

echo ""
ok "Done. To update later: curl ... | bash -s update"
printf '  docs:  https://yorha-agents.github.io/DevolaFlow/\n'
printf '  repo:  https://github.com/%s\n\n' "$REPO"
