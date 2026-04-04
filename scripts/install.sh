#!/usr/bin/env bash
#
# DevolaFlow Quick Installer
#
# Usage:
#   curl -fsSL https://devolaflow.sh | bash                     # auto-detect, project-local
#   curl -fsSL https://devolaflow.sh | bash -s cursor           # Cursor only, project-local
#   curl -fsSL https://devolaflow.sh | bash -s cursor --global  # Cursor only, user-global
#   curl -fsSL https://devolaflow.sh | bash -s update           # re-download latest files
#
# Targets:  cursor, codex, claude, copilot, mvp, all, auto (default), update
# Flags:    --global  install to user home (~/.cursor/) instead of project (.cursor/)
#           --project install to current project directory (default)

set -euo pipefail

REPO="YoRHa-Agents/DevolaFlow"
BRANCH="main"
BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
AGENT_BASE="${BASE}/workflow-system/agent"
TIMEOUT=10
VERSION_FILE=".devola-flow-version"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
DIM='\033[2m'
NC='\033[0m'

info()  { echo -e "${BLUE}[devola]${NC} $*"; }
ok()    { echo -e "${GREEN}[devola]${NC} $*"; }
warn()  { echo -e "${YELLOW}[devola]${NC} $*"; }
dim()   { echo -e "${DIM}         $*${NC}"; }

# Parse args
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

# ─── Download helper with timeout ─────────────────────────────────

download() {
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if command -v curl &>/dev/null; then
    curl -fsSL --connect-timeout "$TIMEOUT" --max-time 30 "$url" -o "$dest" 2>/dev/null
  elif command -v wget &>/dev/null; then
    wget -q --timeout="$TIMEOUT" "$url" -O "$dest" 2>/dev/null
  else
    echo "Error: curl or wget required" >&2; exit 1
  fi
}

# Download multiple files in parallel, show progress
download_batch() {
  local base_url="$1" dest_dir="$2"
  shift 2
  local files=("$@")
  local total=${#files[@]}
  local pids=()

  mkdir -p "$dest_dir"
  for f in "${files[@]}"; do
    download "${base_url}/${f}" "${dest_dir}/${f}" &
    pids+=($!)
  done

  local done_count=0
  local failed=0
  for pid in "${pids[@]}"; do
    if wait "$pid" 2>/dev/null; then
      done_count=$((done_count + 1))
    else
      failed=$((failed + 1))
      done_count=$((done_count + 1))
    fi
    printf "\r         [%d/%d] downloading...  " "$done_count" "$total" >&2
  done
  printf "\r         [%d/%d] done            \n" "$total" "$total" >&2

  if [ "$failed" -gt 0 ]; then
    warn "$failed file(s) failed to download"
    return 1
  fi
  return 0
}

# ─── Version tracking for update support ──────────────────────────

stamp_version() {
  local dir="$1"
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%d")
  echo "installed: ${ts}" > "${dir}/${VERSION_FILE}"
  echo "source: ${REPO}@${BRANCH}" >> "${dir}/${VERSION_FILE}"
}

check_existing() {
  local dir="$1"
  if [ -f "${dir}/${VERSION_FILE}" ]; then
    local prev
    prev=$(head -1 "${dir}/${VERSION_FILE}" 2>/dev/null || echo "unknown")
    warn "Existing install found (${prev})"
    info "Updating in place..."
    return 0
  fi
  return 1
}

# ─── Tool installers ──────────────────────────────────────────────

resolve_cursor_dir() {
  if [ "$SCOPE" = "global" ]; then
    echo "$HOME/.cursor/skills/devola-flow"
  else
    echo ".cursor/skills/devola-flow"
  fi
}

install_cursor() {
  local dir
  dir=$(resolve_cursor_dir)
  local rules_dir

  if [ "$SCOPE" = "global" ]; then
    rules_dir="$HOME/.cursor/rules"
    info "Installing Cursor skill (global) to ${dir}/"
  else
    rules_dir=".cursor/rules"
    info "Installing Cursor skill (project) to ${dir}/"
  fi
  dim "scope: ${SCOPE} | use --global for user-wide, --project for repo-local"

  check_existing "$dir" || true
  mkdir -p "$dir/references" "$dir/examples"

  # Download SKILL.md first (fast, validates connectivity)
  download "${AGENT_BASE}/SKILL.md" "$dir/SKILL.md"

  # Download references in parallel
  info "Downloading 8 reference files..."
  download_batch "${AGENT_BASE}/references" "$dir/references" \
    agent-hierarchy.md meta-framework.md decomposition-gate.md repo-modes.md \
    execution-protocol.md message-schemas.md team-roles.md context-isolation.md

  # Download examples in parallel
  info "Downloading 3 example files..."
  download_batch "${AGENT_BASE}/examples" "$dir/examples" \
    full-pipeline-trace.md hotfix-trace.md convergence-loop-trace.md

  # Rules
  mkdir -p "$rules_dir"
  download "${BASE}/.cursor/rules/workflow-rules.mdc" "$rules_dir/devola-flow-rules.mdc"

  stamp_version "$dir"
  ok "Cursor: ${dir}/SKILL.md + 8 references + 3 examples + rules"
}

install_codex() {
  local dir
  if [ -n "${CODEX_HOME:-}" ]; then
    dir="${CODEX_HOME}/skills/devola-flow"
  else
    dir="$HOME/.codex/skills/devola-flow"
  fi
  info "Installing Codex skill to ${dir}/"
  check_existing "$dir" || true
  mkdir -p "$dir"
  download "${AGENT_BASE}/MVP-SKILL.md" "$dir/SKILL.md"
  stamp_version "$dir"
  ok "Codex: ${dir}/SKILL.md"
}

install_claude() {
  info "Installing Claude Code to ./CLAUDE.md"
  download "${AGENT_BASE}/MVP-SKILL.md" "CLAUDE.md"
  ok "Claude: ./CLAUDE.md"
}

install_copilot() {
  info "Installing Copilot to .github/copilot-instructions.md"
  mkdir -p ".github"
  download "${AGENT_BASE}/MVP-SKILL.md" ".github/copilot-instructions.md"
  ok "Copilot: .github/copilot-instructions.md"
}

install_mvp() {
  local dest="${1:-devola-flow-skill.md}"
  info "Downloading MVP-SKILL.md -> $dest"
  download "${AGENT_BASE}/MVP-SKILL.md" "$dest"
  ok "MVP: $dest"
}

# ─── Update: re-install to all existing locations ─────────────────

do_update() {
  info "Checking for existing DevolaFlow installs..."
  local found=0

  # Project-local Cursor
  if [ -f ".cursor/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"
    install_cursor
    found=1
  fi

  # Global Cursor
  if [ -f "$HOME/.cursor/skills/devola-flow/SKILL.md" ]; then
    SCOPE="global"
    install_cursor
    found=1
  fi

  # Codex
  local codex_dir="${CODEX_HOME:-$HOME/.codex}/skills/devola-flow"
  if [ -f "$codex_dir/SKILL.md" ]; then
    install_codex
    found=1
  fi

  # Claude
  if [ -f "CLAUDE.md" ] && grep -q "devola-flow" "CLAUDE.md" 2>/dev/null; then
    install_claude
    found=1
  fi

  # Copilot
  if [ -f ".github/copilot-instructions.md" ] && grep -q "devola-flow" ".github/copilot-instructions.md" 2>/dev/null; then
    install_copilot
    found=1
  fi

  if [ "$found" -eq 0 ]; then
    warn "No existing DevolaFlow installs found. Run without 'update' to install fresh."
    exit 1
  fi
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
    warn "No AI tools detected in current directory."
    echo ""
    echo "  Install for a specific tool:"
    echo "    curl ... | bash -s cursor             # project-local (.cursor/)"
    echo "    curl ... | bash -s cursor --global     # user-global (~/.cursor/)"
    echo "    curl ... | bash -s claude              # Claude Code (./CLAUDE.md)"
    echo "    curl ... | bash -s copilot             # Copilot (.github/)"
    echo "    curl ... | bash -s mvp                 # standalone file"
    echo ""
    exit 0
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
info "Installer | scope: ${SCOPE} | target: ${TARGET}"
echo ""

case "$TARGET" in
  cursor)  install_cursor ;;
  codex)   install_codex ;;
  claude)  install_claude ;;
  copilot) install_copilot ;;
  mvp)     install_mvp "devola-flow-skill.md" ;;
  update)  do_update ;;
  all)
    install_cursor
    install_codex
    install_claude
    install_copilot
    ;;
  auto)    auto_detect ;;
  *)
    echo "Usage: install.sh [target] [flags]"
    echo ""
    echo "Targets:"
    echo "  cursor    Install for Cursor (SKILL.md + refs + examples + rules)"
    echo "  codex     Install for Codex (MVP single-file)"
    echo "  claude    Install for Claude Code (MVP as CLAUDE.md)"
    echo "  copilot   Install for GitHub Copilot (MVP as instructions)"
    echo "  mvp       Download MVP-SKILL.md standalone file"
    echo "  all       Install for all tools"
    echo "  update    Re-download latest files to all existing installs"
    echo "  auto      Auto-detect tools (default)"
    echo ""
    echo "Flags:"
    echo "  --project   Install to current project directory (default)"
    echo "  --global    Install to user home directory (~/.cursor/)"
    echo ""
    echo "Examples:"
    echo "  curl -fsSL https://raw.githubusercontent.com/${REPO}/${BRANCH}/scripts/install.sh | bash"
    echo "  curl -fsSL ... | bash -s cursor"
    echo "  curl -fsSL ... | bash -s cursor --global"
    echo "  curl -fsSL ... | bash -s update"
    exit 1
    ;;
esac

echo ""
ok "Done! DevolaFlow is ready."
dim "To update later: curl ... | bash -s update"
echo ""
echo "  Docs:  https://yorha-agents.github.io/DevolaFlow/"
echo "  Repo:  https://github.com/${REPO}"
echo ""
