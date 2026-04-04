#!/usr/bin/env bash
#
# DevolaFlow Quick Installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
#   curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude
#
# Supported targets: cursor, codex, claude, copilot, mvp, all
# Default (no arg): auto-detect available tools and install to all found.

set -euo pipefail

REPO="YoRHa-Agents/DevolaFlow"
BRANCH="main"
BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
AGENT_BASE="${BASE}/workflow-system/agent"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

info()  { echo -e "${BLUE}[devola]${NC} $*"; }
ok()    { echo -e "${GREEN}[devola]${NC} $*"; }
warn()  { echo -e "${YELLOW}[devola]${NC} $*"; }

TARGET="${1:-auto}"

# ─── Helpers ──────────────────────────────────────────────────────

download() {
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if command -v curl &>/dev/null; then
    curl -fsSL "$url" -o "$dest"
  elif command -v wget &>/dev/null; then
    wget -q "$url" -O "$dest"
  else
    echo "Error: curl or wget required" >&2; exit 1
  fi
}

install_mvp() {
  local dest="$1"
  info "Downloading MVP-SKILL.md -> $dest"
  download "${AGENT_BASE}/MVP-SKILL.md" "$dest"
  ok "Installed MVP skill to $dest"
}

install_cursor() {
  local dir=".cursor/skills/devola-flow"
  info "Installing Cursor skill to ${dir}/"
  mkdir -p "$dir" "$dir/references" "$dir/examples"

  download "${AGENT_BASE}/SKILL.md" "$dir/SKILL.md"

  for ref in agent-hierarchy meta-framework decomposition-gate repo-modes execution-protocol message-schemas team-roles context-isolation; do
    download "${AGENT_BASE}/references/${ref}.md" "$dir/references/${ref}.md"
  done

  for ex in full-pipeline-trace hotfix-trace convergence-loop-trace; do
    download "${AGENT_BASE}/examples/${ex}.md" "$dir/examples/${ex}.md"
  done

  # Rules
  mkdir -p ".cursor/rules"
  download "${BASE}/.cursor/rules/workflow-rules.mdc" ".cursor/rules/devola-flow-rules.mdc"

  ok "Cursor skill installed: $dir/SKILL.md + 8 references + 3 examples + rules"
}

install_codex() {
  local dir
  if [ -n "${CODEX_HOME:-}" ]; then
    dir="${CODEX_HOME}/skills/devola-flow"
  else
    dir="$HOME/.codex/skills/devola-flow"
  fi
  info "Installing Codex skill to ${dir}/"
  mkdir -p "$dir"
  download "${AGENT_BASE}/MVP-SKILL.md" "$dir/SKILL.md"
  ok "Codex skill installed: $dir/SKILL.md"
}

install_claude() {
  info "Installing Claude Code instructions to ./CLAUDE.md"
  download "${AGENT_BASE}/MVP-SKILL.md" "CLAUDE.md"
  ok "Claude instructions installed: ./CLAUDE.md"
}

install_copilot() {
  info "Installing Copilot instructions to .github/"
  mkdir -p ".github"
  download "${AGENT_BASE}/MVP-SKILL.md" ".github/copilot-instructions.md"
  ok "Copilot instructions installed: .github/copilot-instructions.md"
}

# ─── Auto-detect ──────────────────────────────────────────────────

auto_detect() {
  local found=0

  if [ -d ".cursor" ] || command -v cursor &>/dev/null; then
    install_cursor
    found=1
  fi

  if [ -d "$HOME/.codex" ] || [ -n "${CODEX_HOME:-}" ]; then
    install_codex
    found=1
  fi

  if [ -d ".claude" ] || [ -f "CLAUDE.md" ]; then
    install_claude
    found=1
  fi

  if [ -d ".github" ]; then
    install_copilot
    found=1
  fi

  if [ "$found" -eq 0 ]; then
    warn "No AI tools detected. Installing MVP skill for manual setup."
    install_mvp "devola-flow-skill.md"
    echo ""
    echo "To use, copy devola-flow-skill.md to your tool:"
    echo "  Cursor:  .cursor/skills/devola-flow/SKILL.md"
    echo "  Codex:   ~/.codex/skills/devola-flow/SKILL.md"
    echo "  Claude:  ./CLAUDE.md"
    echo "  Copilot: .github/copilot-instructions.md"
  fi
}

# ─── Main ─────────────────────────────────────────────────────────

echo ""
echo "  ____                  _       _____ _"
echo " |  _ \\  _____   ___  | | __ _|  ___| | _____      __"
echo " | | | |/ _ \\ \\ / / _ \\| |/ _\` | |_  | |/ _ \\ \\ /\\ / /"
echo " | |_| |  __/\\ V / (_) | | (_| |  _| | | (_) \\ V  V /"
echo " |____/ \\___| \\_/ \\___/|_|\\__,_|_|   |_|\\___/ \\_/\\_/"
echo ""
echo " Quick Installer"
echo ""

case "$TARGET" in
  cursor)  install_cursor ;;
  codex)   install_codex ;;
  claude)  install_claude ;;
  copilot) install_copilot ;;
  mvp)     install_mvp "devola-flow-skill.md" ;;
  all)
    install_cursor
    install_codex
    install_claude
    install_copilot
    ;;
  auto)    auto_detect ;;
  *)
    echo "Usage: install.sh [cursor|codex|claude|copilot|mvp|all|auto]"
    exit 1
    ;;
esac

echo ""
ok "Done! DevolaFlow is ready to use."
echo ""
echo "  Docs:  https://yorha-agents.github.io/DevolaFlow/"
echo "  Repo:  https://github.com/${REPO}"
echo ""
