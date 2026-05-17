# Claude Code Skill Integration Gap Analysis

**Date:** 2026-04-15
**Scope:** Compare DevolaFlow's Claude Code integration with Cursor integration; identify gaps
**Conclusion:** Claude Code supports the SAME skill structure as Cursor. DevolaFlow should install as a skill, not as CLAUDE.md.

---

## 1. Core Finding: Claude Code Fully Supports Skills

Claude Code (as of 2026) supports a skills system **structurally identical** to Cursor:

```
~/.claude/skills/devola-flow/       # Global (all projects)
.claude/skills/devola-flow/         # Project-specific

  SKILL.md                          # Required: YAML frontmatter + markdown body
  references/                       # Optional: on-demand docs (Tier 3)
    agent-hierarchy.md
    meta-framework.md
    ...
  scripts/                          # Optional: executable code
  templates/                        # Optional: file templates
  assets/                           # Optional: static files
```

**Progressive Loading (3 tiers):**

| Tier | What Loads | When | Token Cost |
|------|-----------|------|------------|
| Tier 1 | Skill name + description (frontmatter) | Session start | ~20-50 tokens |
| Tier 2 | Full SKILL.md body | On invocation (`/devola-flow`) or auto-activation | ~4000-5000 tokens |
| Tier 3 | references/, scripts/, assets/ | When SKILL.md references them | Variable |

**Invocation methods:**
- `/devola-flow` — explicit slash command
- Auto-activation via `description` field semantic matching
- Auto-activation via `triggers` frontmatter field
- Auto-activation via `paths` glob patterns (file-based)

---

## 2. CLAUDE.md vs Skills: Different Purposes

| Aspect | CLAUDE.md | Skills (.claude/skills/) |
|--------|-----------|--------------------------|
| **Purpose** | Passive project context (conventions, rules) | Active workflow tooling (on-demand) |
| **Loading** | ALWAYS loaded at session start | Tier 1 at start, Tier 2+ on-demand |
| **Recommended size** | ~200 lines / ~2000 tokens | Up to 500 lines + unlimited references |
| **Token cost** | Paid on EVERY session | Paid only when invoked |
| **Invocation** | Automatic (no choice) | `/command` or auto-trigger |
| **References** | Not supported (single file) | Supported (references/ directory) |
| **Analogous to (Cursor)** | `.cursorrules` / `.cursor/rules/*.mdc` | `.cursor/skills/<name>/SKILL.md` |

**Key insight:** DevolaFlow is a **workflow skill**, not project context. Putting it in CLAUDE.md is like putting a Cursor skill into `.cursorrules` — it works, but wastes tokens and misses features.

---

## 3. Current State (v5.4.1) — How DevolaFlow Integrates

### Cursor (correct approach)
```
.cursor/skills/devola-flow/
  SKILL.md                    # 496 lines, loaded on-demand
  references/                 # 8 files, lazy-loaded
    agent-hierarchy.md
    meta-framework.md
    decomposition-gate.md
    repo-modes.md
    execution-protocol.md
    message-schemas.md
    team-roles.md
    context-isolation.md
  examples/                   # 3 files, lazy-loaded
    full-pipeline-trace.md
    hotfix-trace.md
    convergence-loop-trace.md
.cursor/rules/
  devola-flow-rules.mdc       # Always-on rules (correct for rules)
```

### Claude Code (suboptimal approach)
```
CLAUDE.md                     # 496 lines dumped as root CLAUDE.md
                              # Loaded on EVERY session (~5000 tokens)
                              # No references/ support
                              # No slash command
                              # No progressive loading
```

---

## 4. Gap Analysis

### Gap 1: Token Waste (HIGH)
- **Current:** 496-line SKILL.md loaded as CLAUDE.md → ~5000 tokens consumed at session start, every session
- **Target:** ~50 tokens at start (frontmatter only), ~5000 tokens only when DevolaFlow is needed
- **Impact:** Users who sometimes use DevolaFlow pay ~5000 tokens overhead even for non-DevolaFlow tasks
- **Best practice:** CLAUDE.md should be ≤200 lines of project-specific rules

### Gap 2: No Reference File Support (HIGH)
- **Current:** CLAUDE.md is a flat file; 8 reference docs (~4200 tokens each) are not available
- **Target:** references/ directory with progressive Tier 3 loading
- **Impact:** Claude Code agents can't access agent-hierarchy.md, meta-framework.md, etc. — they get only the SKILL.md summary. Cursor agents get the full reference library.

### Gap 3: No Slash Command (MEDIUM)
- **Current:** DevolaFlow is passive context; users can't explicitly invoke it
- **Target:** `/devola-flow` command triggers the workflow orchestration
- **Impact:** Users can't control when DevolaFlow activates

### Gap 4: No Auto-Activation Control (MEDIUM)
- **Current:** Always loaded (no control)
- **Target:** `triggers` and `paths` in frontmatter control when DevolaFlow auto-activates
- **Impact:** No way to prevent DevolaFlow from loading when not needed, or to ensure it loads when it IS needed

### Gap 5: No Advanced Frontmatter (LOW)
- **Current:** SKILL.md frontmatter designed for Cursor
- **Target:** Claude Code extended frontmatter: `allowed-tools`, `model`, `context`, `hooks`
- **Impact:** Can't leverage Claude-specific features like per-skill model selection or tool restrictions

### Gap 6: Examples Not Available (LOW)
- **Current:** 3 example trace files not available to Claude Code
- **Target:** examples/ directory accessible via Tier 3 loading
- **Impact:** Claude Code agents can't reference workflow execution examples

---

## 5. Recommended Fix

### install.sh `install_claude()` should become:

```bash
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

  stamp "$dir"
  ok "Claude installed (SKILL.md + 8 refs + 3 examples)"
}
```

### Root CLAUDE.md should become a lightweight trigger:

```markdown
---
name: devola-flow-project
description: "Project using DevolaFlow for workflow orchestration"
---

# Project Context

## DevolaFlow Integration
This project uses DevolaFlow for multi-stage workflow orchestration.
Use `/devola-flow` to activate the workflow skill.
```

This matches the Cursor model: skill content in skills/, rules in rules/, and minimal root context.

---

## 6. Feature Parity Comparison

| Feature | Cursor (current) | Claude Code (current) | Claude Code (target) |
|---------|-------------------|----------------------|---------------------|
| Skill directory | `.cursor/skills/devola-flow/` | N/A (flat CLAUDE.md) | `.claude/skills/devola-flow/` |
| SKILL.md | 496 lines, on-demand | 496 lines, always loaded | 496 lines, on-demand |
| References (8) | Lazy-loaded | Not available | Lazy-loaded (Tier 3) |
| Examples (3) | Lazy-loaded | Not available | Lazy-loaded (Tier 3) |
| Rules | `.cursor/rules/*.mdc` | N/A | `.claude/rules/*.md` |
| Slash command | N/A (Cursor uses @) | N/A | `/devola-flow` |
| Token at startup | ~50 (frontmatter only) | ~5000 (full SKILL) | ~50 (frontmatter only) |
| Progressive loading | Yes (3 tiers) | No | Yes (3 tiers) |
| Auto-activation | Via `description` | Always on | Via `description` + `triggers` |

---

## 7. Implementation Priority

| Priority | Change | Impact | Effort |
|----------|--------|--------|--------|
| P0 | Install as `.claude/skills/devola-flow/` with refs + examples | Closes Gaps 1-3, 6 | Medium |
| P0 | Root CLAUDE.md becomes lightweight project rules | Closes Gap 1 | Small |
| P1 | Add Claude Code extended frontmatter (triggers, allowed-tools) | Closes Gaps 4-5 | Small |
| P1 | Update `init_project.py` to mirror new install structure | Consistency | Small |
| P2 | Update `build_skill.py` Claude adapter to produce skill structure | Closes dist gap | Medium |
| P2 | Update bump_version.py for new CLAUDE.md path | Maintenance | Small |
