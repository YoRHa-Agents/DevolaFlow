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
# Targets:  cursor, codex, claude, copilot, kimicode, windsurf,
#           zed, cline, roo, local, standalone, all, auto (default), update
# Flags:    --global   install to the tool's user-wide location
#           --project  install to the repo-local location (default)

set -u

REPO="YoRHa-Agents/DevolaFlow"
BRANCH="main"
BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
AGENT_BASE="${BASE}/workflow-system/agent"
STAMP=".devola-flow-version"
VERSION_URL="${BASE}/src/devolaflow/__init__.py"

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

fetch_version() {
  curl -fsSL --connect-timeout 5 "$VERSION_URL" 2>/dev/null \
    | grep '__version__' | head -1 | sed 's/.*"\(.*\)".*/\1/'
}

stamp() {
  local dir="$1"
  local ver
  ver=$(fetch_version)
  if [ -n "$ver" ]; then
    echo "$ver" > "$dir/$STAMP" 2>/dev/null || true
  else
    date -u +"%Y-%m-%dT%H:%M:%SZ" > "$dir/$STAMP" 2>/dev/null || true
  fi
}

# Download SKILL.md and strip its YAML frontmatter into <dest>.
# Used by adapters that consume rules-style markdown without frontmatter
# (zed, cline, roo). Falls back to a raw copy if awk is unavailable.
dl_skill_no_frontmatter() {
  local dest="$1"
  local tmp
  tmp=$(mktemp 2>/dev/null) || tmp="${dest}.tmp"
  if dl "$AGENT_BASE/SKILL.md" "$tmp" && [ -s "$tmp" ]; then
    if command -v awk >/dev/null 2>&1; then
      awk 'BEGIN{f=0} /^---$/{c++; if(c==2){f=1; next}} f==1' "$tmp" > "$dest"
    else
      cp "$tmp" "$dest"
    fi
    rm -f "$tmp"
    return 0
  fi
  rm -f "$tmp"
  return 1
}

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

  info "references (12 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/agent-workspace.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md" \
    "references/behavioral-guidelines.md" \
    "references/shell-proxy.md" \
    "references/plan-mode-enforcement.md"

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
  ok "Cursor installed (SKILL.md + 12 refs + 3 examples + rules)"
}

install_codex() {
  local dir="${CODEX_HOME:-$HOME/.codex}/skills/devola-flow"
  info "Codex -> $dir/"
  mkdir -p "$dir/references"
  dl "$AGENT_BASE/SKILL.md" "$dir/SKILL.md" || true

  info "references (12 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/agent-workspace.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md" \
    "references/behavioral-guidelines.md" \
    "references/shell-proxy.md" \
    "references/plan-mode-enforcement.md"

  stamp "$dir"
  ok "Codex installed (SKILL.md + 12 refs)"
}

install_claude() {
  local dir
  if [ "$SCOPE" = "global" ]; then
    dir="$HOME/.claude/skills/devola-flow"
    info "Claude Code (global) -> $dir/"
  else
    dir=".claude/skills/devola-flow"
    info "Claude Code (project) -> $dir/"
  fi

  mkdir -p "$dir/references" "$dir/examples"

  dl "$AGENT_BASE/SKILL.md" "$dir/SKILL.md" || true

  info "references (12 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/agent-workspace.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md" \
    "references/behavioral-guidelines.md" \
    "references/shell-proxy.md" \
    "references/plan-mode-enforcement.md"

  info "examples (3 files):"
  dl_batch "$dir" \
    "examples/full-pipeline-trace.md" \
    "examples/hotfix-trace.md" \
    "examples/convergence-loop-trace.md"

  stamp "$dir"
  ok "Claude installed (SKILL.md + 12 refs + 3 examples)"
}

install_copilot() {
  info "Copilot -> .github/copilot-instructions.md"
  mkdir -p ".github"
  dl "$AGENT_BASE/SKILL.md" ".github/copilot-instructions.md" || true
  ok "Copilot installed (full SKILL.md)"
}

install_kimicode() {
  local dir
  if [ "$SCOPE" = "global" ]; then
    dir="$HOME/.kimi/skills/devola-flow"
    info "KimiCode (global) -> $dir/"
  else
    dir=".kimi/skills/devola-flow"
    info "KimiCode (project) -> $dir/"
  fi

  mkdir -p "$dir/references" "$dir/examples"

  dl "$AGENT_BASE/SKILL.md" "$dir/SKILL.md" || true

  info "references (12 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/agent-workspace.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md" \
    "references/behavioral-guidelines.md" \
    "references/shell-proxy.md" \
    "references/plan-mode-enforcement.md"

  info "examples (3 files):"
  dl_batch "$dir" \
    "examples/full-pipeline-trace.md" \
    "examples/hotfix-trace.md" \
    "examples/convergence-loop-trace.md"

  stamp "$dir"
  ok "KimiCode installed (SKILL.md + 12 refs + 3 examples)"
}

install_windsurf() {
  info "Windsurf -> .windsurfrules"
  # Download the canonical SKILL.md, then strip its YAML frontmatter for the
  # single-file Windsurf rules document. Falls back to copying the raw SKILL.md
  # if awk is unavailable.
  local tmp
  tmp=$(mktemp 2>/dev/null) || tmp=".devola-flow-skill.tmp"
  dl "$AGENT_BASE/SKILL.md" "$tmp" || true
  if [ -s "$tmp" ]; then
    if command -v awk >/dev/null 2>&1; then
      awk 'BEGIN{f=0} /^---$/{c++; if(c==2){f=1; next}} f==1' "$tmp" > ".windsurfrules"
    else
      cp "$tmp" ".windsurfrules"
    fi
    rm -f "$tmp"
    stamp "."
    ok "Windsurf installed (.windsurfrules, frontmatter stripped)"
  else
    rm -f "$tmp"
    warn "Windsurf install failed (SKILL.md download empty)"
  fi
}

install_zed() {
  # Mirrors adapter_configs/zed.yaml: .rules/devola-flow.md (frontmatter
  # stripped) + .rules/references/ tree. Global scope targets the Zed
  # user-config rules directory (~/.config/zed/rules/).
  local dir
  if [ "$SCOPE" = "global" ]; then
    dir="$HOME/.config/zed/rules"
    info "Zed (global) -> $dir/"
  else
    dir=".rules"
    info "Zed (project) -> $dir/"
  fi

  mkdir -p "$dir/references"

  if dl_skill_no_frontmatter "$dir/devola-flow.md"; then
    printf '    %-35s %s\n' "devola-flow.md" "ok (frontmatter stripped)"
  else
    warn "Zed install failed (SKILL.md download empty)"
    return 1
  fi

  info "references (12 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/agent-workspace.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md" \
    "references/behavioral-guidelines.md" \
    "references/shell-proxy.md" \
    "references/plan-mode-enforcement.md"

  stamp "$dir"
  ok "Zed installed (devola-flow.md + 12 refs)"
}

install_cline() {
  # Mirrors adapter_configs/cline.yaml: .clinerules/devola-flow.md
  # (frontmatter stripped) + .clinerules/references/ tree. Project-only —
  # Cline reads .clinerules/ relative to the workspace.
  local dir=".clinerules"
  if [ "$SCOPE" = "global" ]; then
    warn "Cline has no user-wide install location; using project scope (.clinerules/)"
  fi
  info "Cline (project) -> $dir/"

  mkdir -p "$dir/references"

  if dl_skill_no_frontmatter "$dir/devola-flow.md"; then
    printf '    %-35s %s\n' "devola-flow.md" "ok (frontmatter stripped)"
  else
    warn "Cline install failed (SKILL.md download empty)"
    return 1
  fi

  info "references (12 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/agent-workspace.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md" \
    "references/behavioral-guidelines.md" \
    "references/shell-proxy.md" \
    "references/plan-mode-enforcement.md"

  stamp "$dir"
  ok "Cline installed (devola-flow.md + 12 refs)"
}

install_roo() {
  # Mirrors adapter_configs/roo.yaml: .roo/rules/devola-flow.md (frontmatter
  # stripped) + .roo/rules/references/ tree. Roo Code reads per-mode rule
  # files from .roo/rules/ inside the workspace.
  local dir=".roo/rules"
  if [ "$SCOPE" = "global" ]; then
    warn "Roo Code has no user-wide install location; using project scope (.roo/rules/)"
  fi
  info "Roo Code (project) -> $dir/"

  mkdir -p "$dir/references"

  if dl_skill_no_frontmatter "$dir/devola-flow.md"; then
    printf '    %-35s %s\n' "devola-flow.md" "ok (frontmatter stripped)"
  else
    warn "Roo Code install failed (SKILL.md download empty)"
    return 1
  fi

  info "references (12 files):"
  dl_batch "$dir" \
    "references/agent-hierarchy.md" \
    "references/agent-workspace.md" \
    "references/meta-framework.md" \
    "references/decomposition-gate.md" \
    "references/repo-modes.md" \
    "references/execution-protocol.md" \
    "references/message-schemas.md" \
    "references/team-roles.md" \
    "references/context-isolation.md" \
    "references/behavioral-guidelines.md" \
    "references/shell-proxy.md" \
    "references/plan-mode-enforcement.md"

  stamp "$dir"
  ok "Roo Code installed (devola-flow.md + 12 refs)"
}

install_local() {
  info "Initializing local workspace..."
  mkdir -p ".local/feedbacks" ".local/tasks"

  if command -v python3 >/dev/null 2>&1 && python3 -c "import devolaflow" 2>/dev/null; then
    python3 -m devolaflow.local.workspace 2>/dev/null || true
  fi

  ok "Local workspace initialized (.local/feedbacks, .local/tasks)"

  if [ ! -d ".rules" ]; then
    info "No .rules/ directory found. Create one with governance rules to use rule compilation."
  fi
}

install_standalone() {
  info "Standalone -> devola-flow-skill.md"
  dl "$AGENT_BASE/SKILL.md" "devola-flow-skill.md" || true
  ok "Standalone SKILL.md downloaded"
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
  if [ -f ".claude/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"; install_claude; found=1
  fi
  if [ -f "$HOME/.claude/skills/devola-flow/SKILL.md" ]; then
    SCOPE="global"; install_claude; found=1
  fi
  if [ -f ".github/copilot-instructions.md" ] && head -5 ".github/copilot-instructions.md" 2>/dev/null | grep -q "devola-flow"; then
    install_copilot; found=1
  fi
  if [ -f ".kimi/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"; install_kimicode; found=1
  fi
  if [ -f "$HOME/.kimi/skills/devola-flow/SKILL.md" ]; then
    SCOPE="global"; install_kimicode; found=1
  fi
  if [ -f ".windsurfrules" ] && head -20 ".windsurfrules" 2>/dev/null | grep -q "devola-flow"; then
    install_windsurf; found=1
  fi
  if [ -f ".rules/devola-flow.md" ]; then
    SCOPE="project"; install_zed; found=1
  fi
  if [ -f "$HOME/.config/zed/rules/devola-flow.md" ]; then
    SCOPE="global"; install_zed; found=1
  fi
  if [ -f ".clinerules/devola-flow.md" ]; then
    install_cline; found=1
  fi
  if [ -f ".roo/rules/devola-flow.md" ]; then
    install_roo; found=1
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
  if [ -d ".claude" ]; then
    SCOPE="project"; install_claude; found=1
  elif [ -d "$HOME/.claude" ]; then
    SCOPE="global"; install_claude; found=1
  fi
  if [ -d ".github" ]; then install_copilot; found=1; fi
  # Auto-init .local/ when missing — feedback #1 root cause (v7.4.2)
  if [ ! -d ".local" ]; then install_local; found=1; fi

  if [ "$found" -eq 0 ]; then
    warn "No AI tools detected. Pick one:"
    echo ""
    echo "  curl ... | bash -s cursor             project-local"
    echo "  curl ... | bash -s cursor --global    user-global"
    echo "  curl ... | bash -s claude             Claude Code (project-local)"
    echo "  curl ... | bash -s claude --global    Claude Code (user-global)"
    echo "  curl ... | bash -s copilot            GitHub Copilot"
    echo "  curl ... | bash -s standalone         download standalone SKILL.md"
    echo ""
  fi
}

# ── Main ─────────────────────────────────────────────────────────

INSTALLED_VERSION=$(fetch_version)
cat << 'BANNER'

  DevolaFlow Installer
  ────────────────────
BANNER
if [ -n "$INSTALLED_VERSION" ]; then
  printf '  version: %s | scope: %s | target: %s\n\n' "$INSTALLED_VERSION" "$SCOPE" "$TARGET"
else
  printf '  scope: %s | target: %s\n\n' "$SCOPE" "$TARGET"
fi

case "$TARGET" in
  cursor)   install_cursor ;;
  codex)    install_codex ;;
  claude)   install_claude ;;
  copilot)  install_copilot ;;
  kimicode) install_kimicode ;;
  windsurf) install_windsurf ;;
  zed)      install_zed ;;
  cline)    install_cline ;;
  roo)      install_roo ;;
  local)      install_local ;;
  standalone) install_standalone ;;
  # Deprecated legacy alias: MVP-SKILL.md was removed in v6.0.1; 'mvp' now maps to
  # 'standalone' (full SKILL.md) for backward compatibility with older install commands.
  mvp)        install_standalone ;;
  update)  do_update ;;
  all)     install_cursor; install_codex; install_claude; install_copilot; \
           install_kimicode; install_windsurf; \
           install_zed; install_cline; install_roo; install_local ;;
  auto)    auto_detect ;;
  help|--help|-h)
    cat << USAGE
  Usage: install.sh [target] [flags]

  Targets:
    cursor      Cursor (SKILL.md + refs + examples + rules)
    codex       Codex (SKILL.md + refs)
    claude      Claude Code (SKILL.md + refs + examples as skill)
    copilot     Copilot (SKILL.md as instructions)
    kimicode    KimiCode (SKILL.md + refs + examples)
    windsurf    Windsurf (.windsurfrules, frontmatter stripped)
    zed         Zed (.rules/devola-flow.md + references; --global supported)
    cline       Cline (.clinerules/devola-flow.md + references; project-only)
    roo         Roo Code (.roo/rules/devola-flow.md + references; project-only)
    local       Initialize .local/ workspace + .rules/ governance (project-only)
    standalone  Download standalone SKILL.md
    all         All tools
    update      Re-download latest to existing installs
    auto        Auto-detect (default)

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
if [ -n "$INSTALLED_VERSION" ]; then
  ok "Now Using DevolaFlow v${INSTALLED_VERSION}"
else
  ok "Done."
fi
printf '  update: curl ... | bash -s update\n'
printf '  docs:   https://yorha-agents.github.io/DevolaFlow/\n'
printf '  repo:   https://github.com/%s\n\n' "$REPO"
