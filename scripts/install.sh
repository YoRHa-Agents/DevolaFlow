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
#           zed, cline, roo, local, standalone, all, auto (default),
#           update, uninstall
# Flags:    --global      install to the tool's user-wide location (ALSO
#                         installs default-bundled runtime plugins)
#           --project     install to the repo-local location (default)
#           --no-plugins  with --global, skip the bundled runtime-plugin install
#           --base-url U  override the download base (mirrors / offline
#                         file:// sources / E2E tests). Default is the
#                         raw.githubusercontent.com main-branch tree.
#           --force       with update: reinstall even when the stamped
#                         version already matches the remote version
#           --dry-run     with uninstall: list what would be removed
#                         without deleting anything
#
# File lists are NOT hardcoded here: the installer fetches the install
# manifest (workflow-system/agent/manifest.yaml — the A-5 single source
# of truth shared with sync_cursor_skill.py and devola-init) and downloads
# whatever the target's install profile declares. When the manifest is
# unreachable the installer degrades to a SKILL.md-only install with an
# explicit warning (warn-not-fatal per S-5).

set -u

REPO="YoRHa-Agents/DevolaFlow"
BRANCH="main"
BASE_DEFAULT="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
STAMP=".devola-flow-version"

info() { printf '  \033[34m>\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
errf() { printf '  \033[31m✗\033[0m %s\n' "$*"; }

SCOPE="project"
TARGET="auto"
NO_PLUGINS="false"
BASE_OVERRIDE=""
FORCE="false"
DRY_RUN="false"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --global)      SCOPE="global"; shift ;;
    --project)     SCOPE="project"; shift ;;
    --no-plugins)  NO_PLUGINS="true"; shift ;;
    --force)       FORCE="true"; shift ;;
    --dry-run)     DRY_RUN="true"; shift ;;
    --base-url)    BASE_OVERRIDE="${2:-}"; shift; shift ;;
    --base-url=*)  BASE_OVERRIDE="${1#*=}"; shift ;;
    -h|--help)     TARGET="help"; shift ;;
    # Unknown flags abort instead of silently falling through to a real
    # `auto` install (S-5: no silent failure).
    -*)            printf 'install.sh: unknown option %s (run with "help" for usage)\n' "$1" >&2; exit 2 ;;
    *)             TARGET="$1"; shift ;;
  esac
done

BASE="${BASE_OVERRIDE:-$BASE_DEFAULT}"
AGENT_BASE="${BASE}/workflow-system/agent"
VERSION_URL="${BASE}/src/devolaflow/__init__.py"

# v13.0.0 — capture the operator's REQUESTED scope up-front. do_update() and
# auto_detect() mutate the global SCOPE per detected install, so the bundled
# plugin-install gate at the end MUST key off this immutable requested scope
# (not the post-run SCOPE) — otherwise `install.sh auto` could trigger global
# plugin installs and `install.sh update --global` could skip them.
REQUESTED_SCOPE="$SCOPE"

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

# ── Install manifest (A-5 SSOT) ──────────────────────────────────
# workflow-system/agent/manifest.yaml is the single owner of the per-tool
# install file lists. It is fetched ONCE per run and parsed with the
# line-oriented helpers below (the manifest keeps flat "  - path" lists and
# single-line flow-style profiles specifically so this parser stays trivial).

MANIFEST_FILE=""
trap '[ -n "$MANIFEST_FILE" ] && rm -f "$MANIFEST_FILE"' EXIT

fetch_manifest() {
  if [ -n "$MANIFEST_FILE" ] && [ -s "$MANIFEST_FILE" ]; then
    return 0
  fi
  local tmp
  tmp=$(mktemp 2>/dev/null) || tmp=".devola-flow-manifest.tmp"
  if curl -fsSL --connect-timeout 10 --max-time 30 --retry 2 \
      "${AGENT_BASE}/manifest.yaml" -o "$tmp" </dev/null 2>/dev/null && [ -s "$tmp" ]; then
    MANIFEST_FILE="$tmp"
    return 0
  fi
  rm -f "$tmp"
  return 1
}

# Print the entries of a top-level flat-list section, e.g. `manifest_set references`.
manifest_set() {
  awk -v section="$1:" '
    $0 == section { insec = 1; next }
    insec && /^[a-zA-Z_]/ { insec = 0 }
    insec && /^  - / { sub(/^  - /, ""); print }
  ' "$MANIFEST_FILE"
}

# Print the space-separated set names of a profile, e.g. `manifest_profile_sets cursor`.
manifest_profile_sets() {
  sed -n "s/^  $1: *{.*sets: *\[\([^]]*\)\].*}.*/\1/p" "$MANIFEST_FILE" \
    | tr -d ' ' | tr ',' ' '
}

# Print the full newline-separated file list for a profile.
manifest_profile_files() {
  local tool="$1" sets s
  sets=$(manifest_profile_sets "$tool")
  [ -n "$sets" ] || return 1
  for s in $sets; do
    manifest_set "$s"
  done
}

# Download every file in a profile into a destination directory.
# Falls back to a SKILL.md-only install (with an explicit warning) when the
# manifest is unreachable or lacks the profile — warn-not-fatal per S-5.
install_skill_files() {
  local tool="$1" dir="$2"
  if ! fetch_manifest; then
    warn "install manifest unavailable (${AGENT_BASE}/manifest.yaml)"
    warn "falling back to SKILL.md-only install for '$tool'"
    dl "$AGENT_BASE/SKILL.md" "$dir/SKILL.md" || true
    return 0
  fi
  local files
  files=$(manifest_profile_files "$tool")
  if [ -z "$files" ]; then
    warn "manifest has no install profile for '$tool'"
    warn "falling back to SKILL.md-only install"
    dl "$AGENT_BASE/SKILL.md" "$dir/SKILL.md" || true
    return 0
  fi
  local total=0 ok_count=0 fail_count=0 f
  for f in $files; do
    total=$((total + 1))
    if dl "${AGENT_BASE}/${f}" "${dir}/${f}"; then
      ok_count=$((ok_count + 1))
    else
      fail_count=$((fail_count + 1))
    fi
  done
  if [ "$fail_count" -gt 0 ]; then
    warn "${fail_count}/${total} files failed (${ok_count} succeeded)"
  fi
}

# Download SKILL.md and strip its YAML frontmatter into <dest>.
# Used by adapters that consume rules-style markdown without frontmatter
# (zed, cline, roo, windsurf). Falls back to a raw copy if awk is unavailable.
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

# Frontmatter-stripped SKILL.md + the manifest `references` set — the shared
# body for the rule-tree targets (zed, cline, roo).
install_rule_tree() {
  local tool="$1" dir="$2"
  mkdir -p "$dir/references"

  if dl_skill_no_frontmatter "$dir/devola-flow.md"; then
    printf '    %-35s %s\n' "devola-flow.md" "ok (frontmatter stripped)"
  else
    warn "$tool install failed (SKILL.md download empty)"
    return 1
  fi

  if fetch_manifest; then
    info "references (per manifest):"
    local f total=0 ok_count=0 fail_count=0
    for f in $(manifest_set references); do
      total=$((total + 1))
      if dl "${AGENT_BASE}/${f}" "${dir}/${f}"; then
        ok_count=$((ok_count + 1))
      else
        fail_count=$((fail_count + 1))
      fi
    done
    if [ "$fail_count" -gt 0 ]; then
      warn "${fail_count}/${total} references failed (${ok_count} succeeded) — partial references/ tree"
    fi
  else
    warn "install manifest unavailable — installed the rules file only"
  fi

  stamp "$dir"
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

  mkdir -p "$dir"
  info "files (manifest profile 'cursor'):"
  install_skill_files cursor "$dir"

  # v15.0.0 (clean_repo C1-2, decision D1): the legacy rules download
  # (.cursor/rules/workflow-rules.mdc -> <rules>/devola-flow-rules.mdc)
  # retired with the deprecated pointer stub it copied.

  stamp "$dir"
  ok "Cursor installed (manifest profile 'cursor')"
}

install_codex() {
  local dir="${CODEX_HOME:-$HOME/.codex}/skills/devola-flow"
  info "Codex -> $dir/"
  mkdir -p "$dir"
  info "files (manifest profile 'codex'):"
  install_skill_files codex "$dir"
  stamp "$dir"
  ok "Codex installed (manifest profile 'codex')"
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

  mkdir -p "$dir"
  info "files (manifest profile 'claude'):"
  install_skill_files claude "$dir"
  stamp "$dir"
  ok "Claude installed (manifest profile 'claude')"
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

  mkdir -p "$dir"
  info "files (manifest profile 'kimicode'):"
  install_skill_files kimicode "$dir"
  stamp "$dir"
  ok "KimiCode installed (manifest profile 'kimicode')"
}

install_dsh() {
  local dir
  if [ "$SCOPE" = "global" ]; then
    dir="${DSH_HOME:-$HOME/.dsh}/skills/devola-flow"
    info "DSH (global) -> $dir/"
  else
    dir=".dsh/skills/devola-flow"
    info "DSH (project) -> $dir/"
  fi

  mkdir -p "$dir"
  info "files (manifest profile 'dsh'):"
  install_skill_files dsh "$dir"
  stamp "$dir"
  ok "DSH installed (manifest profile 'dsh')"
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

  install_rule_tree zed "$dir" || return 1
  ok "Zed installed (devola-flow.md + manifest references)"
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

  install_rule_tree cline "$dir" || return 1
  ok "Cline installed (devola-flow.md + manifest references)"
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

  install_rule_tree roo "$dir" || return 1
  ok "Roo Code installed (devola-flow.md + manifest references)"
}

install_local() {
  info "Initializing local workspace..."
  mkdir -p ".local/feedbacks" ".local/tasks"

  # full_review_and_improve Track C-1 (R5 F1-H2/H3): the historic form
  # discarded stderr and ||-true'd the module invocation, AND the module
  # had no __main__ path — so this step was a silent no-op reported as
  # success. Now: run the real scaffold, surface its output, and report
  # the actual outcome (S-5 no silent failures).
  if command -v python3 >/dev/null 2>&1 && python3 -c "import devolaflow" 2>/dev/null; then
    if python3 -m devolaflow.local.workspace; then
      ok "Local workspace scaffolded (.local/ tree + .gitignore entries verified)"
    else
      errf "devolaflow scaffold failed — .local/ may be incomplete (see error above)."
      errf "Fix the reported issue, then re-run: devola-init local"
      return 1
    fi
  else
    warn "python3 + devolaflow package not found — created minimal .local/ only (no .gitignore setup)."
    warn "Install the package (pip install devolaflow), then run: devola-init local"
  fi

  if [ ! -d ".rules" ]; then
    info "No .rules/ directory found. Create one with governance rules to use rule compilation."
  fi
}

install_standalone() {
  info "Standalone -> devola-flow-skill.md"
  dl "$AGENT_BASE/SKILL.md" "devola-flow-skill.md" || true
  ok "Standalone SKILL.md downloaded"
}

# v13.0.0 — bundled runtime-plugin install for --global. The registry's
# default_install field controls bundle membership. Delegates to the
# Python installer (A-5 SSOT: same ensure_plugin path devola-init uses) when
# the devolaflow package is importable; otherwise emits clear guidance.
# Warn-not-fatal (S-5): plugin failures NEVER abort the skill install.
install_plugins() {
  info "Installing runtime plugins (global) ..."
  if command -v python3 >/dev/null 2>&1 && python3 -c "import devolaflow" 2>/dev/null; then
    python3 -c "from devolaflow.init_project import install_plugins; install_plugins('global')" \
      || warn "bundled plugin install reported errors (non-fatal)"
  else
    warn "devolaflow package not importable — skipping bundled plugin install."
    warn "  Install plugins manually, e.g.:"
    warn "    npm install -g @colbymchenry/codegraph"
    warn "    npm install -g impeccable && impeccable skills install --yes"
  fi
}

# ── Update ───────────────────────────────────────────────────────

# Version compare for `update`: an install whose stamp's first line equals the
# remote __version__ is already current — re-downloading it wastes bandwidth
# and (worse) hides real drift behind a always-green "ok" wall. Date-fallback
# stamps (written when the version fetch failed at install time) never match
# a semver string, so they conservatively re-download. `--force` bypasses.
is_up_to_date() {
  [ "$FORCE" = "true" ] && return 1
  [ -n "$INSTALLED_VERSION" ] || return 1
  local stamp_file="$1/$STAMP" local_ver
  [ -f "$stamp_file" ] || return 1
  local_ver=$(head -n 1 "$stamp_file" 2>/dev/null || true)
  [ -n "$local_ver" ] && [ "$local_ver" = "$INSTALLED_VERSION" ]
}

# $1 = stamp dir, $2 = human label, $3 = installer function.
maybe_update() {
  if is_up_to_date "$1"; then
    ok "$2 up-to-date (v${INSTALLED_VERSION}) — skipped; use --force to reinstall"
  else
    "$3"
  fi
}

do_update() {
  info "Looking for existing DevolaFlow installs..."
  if [ "$FORCE" = "true" ]; then
    info "(--force: reinstalling even when already up-to-date)"
  fi
  local found=0

  if [ -f ".cursor/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"
    maybe_update ".cursor/skills/devola-flow" "Cursor (project)" install_cursor
    found=1
  fi
  if [ -f "$HOME/.cursor/skills/devola-flow/SKILL.md" ]; then
    SCOPE="global"
    maybe_update "$HOME/.cursor/skills/devola-flow" "Cursor (global)" install_cursor
    found=1
  fi
  local cdir="${CODEX_HOME:-$HOME/.codex}/skills/devola-flow"
  if [ -f "$cdir/SKILL.md" ]; then
    maybe_update "$cdir" "Codex" install_codex
    found=1
  fi
  if [ -f ".claude/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"
    maybe_update ".claude/skills/devola-flow" "Claude Code (project)" install_claude
    found=1
  fi
  if [ -f "$HOME/.claude/skills/devola-flow/SKILL.md" ]; then
    SCOPE="global"
    maybe_update "$HOME/.claude/skills/devola-flow" "Claude Code (global)" install_claude
    found=1
  fi
  if [ -f ".github/copilot-instructions.md" ] && head -5 ".github/copilot-instructions.md" 2>/dev/null | grep -q "devola-flow"; then
    # Copilot's single-file install carries no version stamp — always refresh.
    install_copilot; found=1
  fi
  if [ -f ".kimi/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"
    maybe_update ".kimi/skills/devola-flow" "KimiCode (project)" install_kimicode
    found=1
  fi
  if [ -f "$HOME/.kimi/skills/devola-flow/SKILL.md" ]; then
    SCOPE="global"
    maybe_update "$HOME/.kimi/skills/devola-flow" "KimiCode (global)" install_kimicode
    found=1
  fi
  local dshdir="${DSH_HOME:-$HOME/.dsh}/skills/devola-flow"
  if [ -f ".dsh/skills/devola-flow/SKILL.md" ]; then
    SCOPE="project"
    maybe_update ".dsh/skills/devola-flow" "DSH (project)" install_dsh
    found=1
  fi
  if [ -f "$dshdir/SKILL.md" ]; then
    SCOPE="global"
    maybe_update "$dshdir" "DSH (global)" install_dsh
    found=1
  fi
  if [ -f ".windsurfrules" ] && head -20 ".windsurfrules" 2>/dev/null | grep -q "devola-flow"; then
    maybe_update "." "Windsurf" install_windsurf
    found=1
  fi
  if [ -f ".rules/devola-flow.md" ]; then
    SCOPE="project"
    maybe_update ".rules" "Zed (project)" install_zed
    found=1
  fi
  if [ -f "$HOME/.config/zed/rules/devola-flow.md" ]; then
    SCOPE="global"
    maybe_update "$HOME/.config/zed/rules" "Zed (global)" install_zed
    found=1
  fi
  if [ -f ".clinerules/devola-flow.md" ]; then
    maybe_update ".clinerules" "Cline" install_cline
    found=1
  fi
  if [ -f ".roo/rules/devola-flow.md" ]; then
    maybe_update ".roo/rules" "Roo Code" install_roo
    found=1
  fi

  if [ "$found" -eq 0 ]; then
    warn "No existing installs found. Run: curl ... | bash -s cursor"
    return 1
  fi
}

# ── Uninstall ────────────────────────────────────────────────────

# Remove a path, honouring --dry-run. Skill dirs are exclusively ours
# (.../skills/devola-flow/) so whole-dir removal is safe; rule-tree targets
# share their directory with user rules, so only devola-owned entries go.
rm_path() {
  local path="$1"
  { [ -e "$path" ] || [ -L "$path" ]; } || return 0
  if [ "$DRY_RUN" = "true" ]; then
    info "would remove: $path"
  else
    rm -rf "$path"
    ok "removed: $path"
  fi
}

# $1 = rule-tree dir: remove devola-flow.md + references/ + stamp, then the
# directory itself only when that left it empty (sibling user rules survive).
uninstall_rule_tree() {
  local dir="$1"
  rm_path "$dir/devola-flow.md"
  rm_path "$dir/references"
  rm_path "$dir/$STAMP"
  if [ "$DRY_RUN" != "true" ]; then
    rmdir "$dir" 2>/dev/null || true
  fi
}

do_uninstall() {
  info "Scanning for DevolaFlow installs to remove..."
  if [ "$DRY_RUN" = "true" ]; then
    info "(--dry-run: nothing will be deleted)"
  fi
  local found=0 d

  for d in ".cursor/skills/devola-flow" "$HOME/.cursor/skills/devola-flow" \
           "${CODEX_HOME:-$HOME/.codex}/skills/devola-flow" \
           ".claude/skills/devola-flow" "$HOME/.claude/skills/devola-flow" \
           ".kimi/skills/devola-flow" "$HOME/.kimi/skills/devola-flow" \
           ".dsh/skills/devola-flow" "${DSH_HOME:-$HOME/.dsh}/skills/devola-flow"; do
    if [ -f "$d/SKILL.md" ]; then
      rm_path "$d"
      found=1
    fi
  done

  if [ -f ".github/copilot-instructions.md" ] && head -5 ".github/copilot-instructions.md" 2>/dev/null | grep -q "devola-flow"; then
    rm_path ".github/copilot-instructions.md"
    found=1
  fi
  if [ -f ".windsurfrules" ] && head -20 ".windsurfrules" 2>/dev/null | grep -q "devola-flow"; then
    rm_path ".windsurfrules"
    rm_path "./$STAMP"
    found=1
  fi
  if [ -f ".rules/devola-flow.md" ]; then uninstall_rule_tree ".rules"; found=1; fi
  if [ -f "$HOME/.config/zed/rules/devola-flow.md" ]; then
    uninstall_rule_tree "$HOME/.config/zed/rules"
    found=1
  fi
  if [ -f ".clinerules/devola-flow.md" ]; then uninstall_rule_tree ".clinerules"; found=1; fi
  if [ -f ".roo/rules/devola-flow.md" ]; then uninstall_rule_tree ".roo/rules"; found=1; fi

  if [ "$found" -eq 0 ]; then
    warn "No DevolaFlow installs found — nothing to remove."
    return 0
  fi
  if [ "$DRY_RUN" = "true" ]; then
    ok "Dry run complete — re-run without --dry-run to delete."
  else
    ok "Uninstall complete."
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
  if [ -d ".kimi" ]; then install_kimicode; found=1; fi
  if [ -d ".dsh" ]; then install_dsh; found=1; fi
  # Auto-init .local/ when missing — feedback #1 root cause (v7.4.2).
  # Track C-1 follow-up: propagate the scaffold's failure instead of
  # swallowing it (S-5) — a broken .gitignore scaffold must not exit 0.
  if [ ! -d ".local" ]; then install_local || return 1; found=1; fi

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
  dsh)      install_dsh ;;
  windsurf) install_windsurf ;;
  zed)      install_zed ;;
  cline)    install_cline ;;
  roo)      install_roo ;;
  local)      install_local || exit 1 ;;
  standalone) install_standalone ;;
  # Deprecated legacy alias: MVP-SKILL.md was removed in v6.0.1; 'mvp' now maps to
  # 'standalone' (full SKILL.md) for backward compatibility with older install commands.
  mvp)        install_standalone ;;
  update)    do_update ;;
  uninstall) do_uninstall ;;
  all)     install_cursor; install_codex; install_claude; install_copilot; \
           install_kimicode; install_dsh; install_windsurf; \
           install_zed; install_cline; install_roo; install_local || exit 1 ;;
  auto)    auto_detect || exit 1 ;;
  help|--help|-h)
    cat << USAGE
  Usage: install.sh [target] [flags]

  Targets:
    cursor      Cursor (manifest profile: SKILL.md + refs + examples)
    codex       Codex (manifest profile: SKILL.md + refs)
    claude      Claude Code (manifest profile: SKILL.md + refs + examples)
    copilot     Copilot (SKILL.md as instructions)
    kimicode    KimiCode (manifest profile: SKILL.md + refs + examples)
    dsh         DeepSeek Harness (manifest profile: SKILL.md + refs + examples)
    windsurf    Windsurf (.windsurfrules, frontmatter stripped)
    zed         Zed (.rules/devola-flow.md + references; --global supported)
    cline       Cline (.clinerules/devola-flow.md + references; project-only)
    roo         Roo Code (.roo/rules/devola-flow.md + references; project-only)
    local       Initialize .local/ workspace + .rules/ governance (project-only)
    standalone  Download standalone SKILL.md
    all         All tools
    update      Refresh existing installs (skips installs whose stamped
                version already matches the remote; --force reinstalls)
    uninstall   Remove all detected DevolaFlow installs (--dry-run to preview)
    auto        Auto-detect (default)

  Flags:
    --project     repo-local install path (default)
    --global      user-wide install path when supported; ALSO installs the
                  default-bundled runtime plugins (codegraph/impeccable)
                  by default — failures are warn-not-fatal
    --no-plugins  with --global, skip the bundled runtime-plugin install
                  (skill files only)
    --force       with update: reinstall even when the stamp matches remote
    --dry-run     with uninstall: list removals without deleting
    --base-url U  override the download base URL (mirror / file:// source);
                  file lists always come from the manifest at
                  <base>/workflow-system/agent/manifest.yaml
USAGE
    exit 0 ;;
  *)
    errf "Unknown target: $TARGET"
    echo "  Run with 'help' to see options."
    exit 1 ;;
esac

# v13.0.0 — a --global skill install ALSO installs default-bundled runtime
# plugins by default (the cycle ask: "make devola install also install all
# plugins"). Optional plugins can remain explicitly selectable without entering
# this bundle. --no-plugins opts out. Project-scope installs stay lean (no
# plugin install).
# uninstall never installs plugins regardless of scope.
if [ "$REQUESTED_SCOPE" = "global" ] && [ "$NO_PLUGINS" = "false" ] && [ "$TARGET" != "uninstall" ]; then
  install_plugins
fi

echo ""
if [ "$TARGET" = "uninstall" ]; then
  ok "Done."
elif [ -n "$INSTALLED_VERSION" ]; then
  ok "Now Using DevolaFlow v${INSTALLED_VERSION}"
else
  ok "Done."
fi
printf '  update: curl ... | bash -s update\n'
printf '  docs:   https://yorha-agents.github.io/DevolaFlow/\n'
printf '  repo:   https://github.com/%s\n\n' "$REPO"
