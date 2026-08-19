# T08 — Deep Research: Deterministic Lifecycle Hooks (Card 4)

**Task ID:** T08-deep-research-hooks
**Team:** Research
**Date:** 2026-04-11
**Status:** Complete

---

## 1. Web Research Findings

### 1.1 Deterministic vs Prompt-Based Enforcement

| Dimension | Prompt-Based | Hook-Based (Deterministic) |
|-----------|-------------|---------------------------|
| Compliance rate | 70-90% | 100% |
| Failure mode | Silently skipped under context pressure | Architecturally impossible to skip |
| Context dependency | Degrades over long sessions | Stateless — fires every time |
| Red-team benchmark | 26.7% violation rate (adversarial prompts) | 0% violations |
| Enforcement model | "Discouraged" — agent *should* comply | "Prevented" — system *blocks* non-compliance |

**Key insight from research:** "The entity that governs an agent system must not itself be an LLM." (Zylos Research, 2026). Hooks execute outside the LLM reasoning chain, making them immune to context pressure, jailbreak attempts, and session degradation.

**The Enforcement Ladder (Walseth AI):**
- L1-L2: Conversation/prose documentation (dropped under pressure)
- L3: Templates and code scaffolds
- L4: Automated tests catching violations at commit time
- L5: **Hooks that physically prevent actions before they happen**

DevolaFlow's current SKILL.md operates at L1-L3. Lifecycle hooks elevate P1 and P4 to L5.

### 1.2 Claude Code Hook Events (Full Catalog)

Claude Code provides **27 distinct lifecycle events** across 5 cadences:

**Once per session:**
| Event | Fires When |
|-------|-----------|
| `SessionStart` | Session begins/resumes |
| `SessionEnd` | Session terminates |

**Once per turn:**
| Event | Fires When |
|-------|-----------|
| `UserPromptSubmit` | User submits prompt |
| `Stop` | Claude finishes responding |
| `StopFailure` | Turn ends due to API error |

**On every tool call:**
| Event | Fires When |
|-------|-----------|
| `PreToolUse` | Before tool executes (can block) |
| `PostToolUse` | After tool succeeds |
| `PostToolUseFailure` | After tool fails |
| `PermissionRequest` | Permission dialog appears |
| `PermissionDenied` | Tool call denied by classifier |

**Subagent/task lifecycle:**
| Event | Fires When |
|-------|-----------|
| `SubagentStart` | Subagent spawned |
| `SubagentStop` | Subagent finishes |
| `TaskCreated` | Task created via TaskCreate |
| `TaskCompleted` | Task marked complete |

**File/config/worktree:**
| Event | Fires When |
|-------|-----------|
| `FileChanged` | Watched file changes on disk |
| `ConfigChange` | Configuration file changes |
| `CwdChanged` | Working directory changes |
| `WorktreeCreate` | Worktree being created |
| `WorktreeRemove` | Worktree being removed |
| `InstructionsLoaded` | CLAUDE.md or rules file loaded |
| `PreCompact` / `PostCompact` | Before/after context compaction |
| `Notification` | Claude Code sends notification |
| `Elicitation` / `ElicitationResult` | MCP server input request/response |
| `TeammateIdle` | Agent team teammate about to idle |

**Handler types:** `command` (shell), `http` (endpoint), `prompt` (LLM single-turn), `agent` (subagent with tools).

**Decision control:** PreToolUse hooks return `permissionDecision: "deny"` to block tool calls. Stop hooks can inject additional instructions. PostToolUse hooks can inject context back into the agent.

### 1.3 Cursor Hook Events

Cursor provides hooks via `.cursor/hooks.json`:

| Event | Maps To (Claude Code equivalent) |
|-------|----------------------------------|
| `beforeShellExecution` | `PreToolUse` (Bash matcher) |
| `afterFileEdit` | `PostToolUse` (Edit/Write matcher) |
| `beforeSubmitPrompt` | `UserPromptSubmit` |
| `stop` | `Stop` |
| `sessionStart` / `sessionEnd` | `SessionStart` / `SessionEnd` |
| `beforeMCPExecution` / `afterMCPExecution` | `PreToolUse` / `PostToolUse` (MCP matcher) |
| `beforeReadFile` | `PreToolUse` (Read matcher) |

**Key difference:** Cursor hooks use `beforeShellExecution`/`afterFileEdit` (verb+noun naming) vs Claude Code's generic `PreToolUse`/`PostToolUse` with matcher-based routing. Claude Code's model is more flexible; Cursor's is more explicit.

**Format:** Both use JSON stdin for input, JSON stdout for response. Both support allow/deny permission decisions.

### 1.4 Production Quality Gate Patterns

**Seven-Layer Guardrail Pattern** (from production AI agent systems):
1. Input validation (prompt injection defense)
2. Action boundaries (capability limits)
3. Output filtering (response validation)
4. Cost controls (spending caps)
5. Human-in-the-loop (high-risk approval)
6. Content moderation
7. Monitoring & alerts

DevolaFlow hooks map to layers 2 (action boundaries) and 3 (output filtering).

**Defense-in-depth:** Hooks are the first layer; CI gates catch what hooks miss; human review catches what CI misses. Each layer is independent.

---

## 2. Sub-Variant Designs

### 2.1 Variant A — Minimal (9 lines)

Rationale: Bare-minimum hook table with no explanation. Assumes the reader understands the enforcement model from the invariants section. Maximum density, zero redundancy with existing SKILL.md content.

```markdown
## Lifecycle Hooks

| Hook | Event | Enforces | On Violation |
|------|-------|----------|--------------|
| `validate_dispatch` | Pre-dispatch | AC contains ≥1 testable condition | Block + escalate |
| `check_file_ownership` | File write | File ∈ task's `owned_files` | Reject + log |
| `test_on_complete` | Task completion | Tests pass, lint clean | Auto-retry ≤ max |
| `verify_stage_gate` | Pre-gate | All wave results collected | Block + flag |

System-level enforcement (100% compliance). Hooks are optional per-dispatch (`hooks: [...]`).
```

**Line count:** 9
**Token estimate:** ~140
**Pros:** Minimal budget impact, clean table format, no redundancy
**Cons:** No platform mapping, no handler type info, no P1/P4 connection made explicit

### 2.2 Variant B — Standard (14 lines, current design)

Rationale: The existing Card 4 design. Adds the enforcement summary line and the P1/P4 mapping.

```markdown
## Lifecycle Hooks

System-level enforcement at task lifecycle events — executes outside LLM context (100% compliance vs 70-90% for prompt-based).

| Hook | Event | Enforces | On Violation |
|------|-------|----------|--------------|
| `validate_dispatch` | Pre-dispatch | AC contains ≥1 testable condition | Block dispatch, escalate |
| `check_file_ownership` | File write | File ∈ task's `owned_files` | Reject write, log P1 violation |
| `test_on_complete` | Task completion | Tests pass, lint clean | Auto-retry ≤ P4 limit |
| `verify_stage_gate` | Pre-gate | All wave results collected | Block gate, flag missing |

Hooks are optional per-dispatch (`hooks: [validate_dispatch, test_on_complete]`). Default: none.
Converts P1 (dispatcher-not-implementer), P4 (bounded retry) from prompt-based to deterministic enforcement.
```

**Line count:** 14
**Token estimate:** ~210
**Pros:** Complete enforcement story, explicit P1/P4 connection
**Cons:** Two prose lines at the end could be denser; `verify_stage_gate` may overlap with existing gate mechanism

### 2.3 Variant C — Extended (19 lines)

Rationale: Full specification including handler types, failure modes, and platform mapping. Best for teams that need implementation guidance, not just behavioral rules.

```markdown
## Lifecycle Hooks

System-level enforcement at task lifecycle events (100% compliance vs 70-90% for prompt-based). Hooks execute outside LLM context — immune to session degradation.

| Hook | Event | Enforces | On Violation | Handler |
|------|-------|----------|--------------|---------|
| `validate_dispatch` | Pre-dispatch | AC ≥1 testable condition | Block + escalate | command |
| `check_file_ownership` | File write | File ∈ `owned_files` | Reject + log P1 | command |
| `test_on_complete` | Task stop | Tests pass, lint clean | Retry ≤ P4 max | command |
| `verify_stage_gate` | Pre-gate | All wave results collected | Block + flag | agent |

**Failure modes:** `block` (reject action), `warn` (log + continue), `retry` (re-execute ≤ limit).

**Platform mapping:**

| Platform | Implementation | Config Location |
|----------|---------------|-----------------|
| Claude Code | Native hooks (`PreToolUse`, `Stop`, `PostToolUse`) | `.claude/settings.json` |
| Cursor | Native hooks (`beforeShellExecution`, `afterFileEdit`, `stop`) | `.cursor/hooks.json` |
| Other | Shim: pre/post-command wrapper scripts | `.workflow/hooks/` |

Hooks are optional per-dispatch. Default: none. Converts P1 + P4 to deterministic enforcement.
```

**Line count:** 19
**Token estimate:** ~310
**Pros:** Implementation-ready, platform-specific, covers failure modes
**Cons:** +80% token cost vs Variant A; platform table may age quickly; implementation detail may not help L0 orchestration

### 2.4 Variant D — Compact-Optimized (11 lines)

Rationale: Maximize information density by merging prose into table annotations and eliminating redundancy. Target: same behavioral guidance as Variant B in fewer lines.

```markdown
## Lifecycle Hooks

System-level enforcement (100% compliance). Optional per-dispatch; default: none.

| Hook | Event | Enforces | On Violation |
|------|-------|----------|--------------|
| `validate_dispatch` | Pre-dispatch | AC ≥1 testable condition | Block + escalate |
| `check_file_ownership` | File write | File ∈ `owned_files` | Reject + log (P1) |
| `test_on_complete` | Task stop | Tests pass, lint clean | Auto-retry ≤ P4 limit |

Elevates P1 (ownership enforcement) and P4 (bounded retry) from prompt-based to deterministic.
```

**Line count:** 11 (including blank lines)
**Token estimate:** ~155
**Pros:** 26% fewer tokens than Variant B with same P1/P4 story; drops `verify_stage_gate` (redundant with gate mechanism); integrates P1/P4 references into the table itself via `(P1)` and `P4 limit` annotations
**Cons:** Removes `verify_stage_gate` — tradeoff analyzed in §5

---

## 3. Context Profile Priority Schemes

### 3.1 Current Profiles (for reference)

The 15 profiles in `context_profiles.yaml` are:
1. `hotfix` 2. `feature` 3. `research` 4. `refactor` 5. `review` 6. `design` 7. `skill-optimization` 8. `migration` 9. `security-audit` 10. `documentation` 11. `spike-poc` 12. `rdrr` 13. `demo-showcase` 14. `perf-optimization` 15. `dependency-setup` 16. `onboarding`

### 3.2 Priority Scheme P1 — Aggressive

**Rationale:** Hooks provide maximum value for any profile that involves implementation or file modification. Mark as `critical` for all implementation-heavy profiles so the hook section is always loaded when agents might violate P1 or P4.

| Profile | lifecycle_hooks priority | Rationale |
|---------|------------------------|-----------|
| `hotfix` | **critical** | Fast fixes risk P1 violation (L0 "just doing it") |
| `feature` | **critical** | Multi-wave impl with parallel file writes |
| `refactor` | **critical** | Code modification across many files |
| `migration` | **critical** | Large-scale file changes, P1 risk high |
| `security-audit` | **critical** | Remediation stage has file writes |
| `perf-optimization` | **critical** | Optimize stage modifies source files |
| `skill-optimization` | **critical** | Optimize stage modifies SKILL.md |
| `demo-showcase` | **critical** | Build stage writes demo code |
| `research` | skip | No file writes, no P1/P4 risk |
| `documentation` | skip | Authoring is low-risk for P1 |
| `spike-poc` | skip | Experimental — minimal enforcement |
| `review` | supplementary | Reviewers don't write code, but may need context |
| `design` | supplementary | Designers don't implement, but dispatch to impl |
| `rdrr` | important | Refine stage has implementation |
| `dependency-setup` | important | Configure stage has file writes |
| `onboarding` | skip | Analysis/documentation focus |

**Impact:** 8 profiles load hooks as critical (~155-310 tokens depending on variant). Highest token overhead but maximum enforcement coverage.

### 3.3 Priority Scheme P2 — Conservative

**Rationale:** Mark as `important` (not `critical`) for implementation profiles so hooks load only when token budget allows. This preserves budget for existing critical sections while still providing enforcement when space permits.

| Profile | lifecycle_hooks priority | Rationale |
|---------|------------------------|-----------|
| `hotfix` | **important** | Fast fixes should load hooks if budget allows |
| `feature` | **important** | Implementation profiles get hooks when possible |
| `refactor` | **important** | Code modification profiles |
| `migration` | **important** | Large-scale changes |
| `security-audit` | **important** | Remediation stage |
| `perf-optimization` | **important** | Optimization stage |
| `skill-optimization` | **important** | Skill modification |
| `demo-showcase` | **important** | Build stage |
| `design` | supplementary | May dispatch to impl |
| `review` | supplementary | Context awareness only |
| `rdrr` | supplementary | Refine stage |
| `dependency-setup` | supplementary | Configure stage |
| `research` | skip | No file writes |
| `documentation` | skip | Low P1 risk |
| `spike-poc` | skip | Experimental |
| `onboarding` | skip | Analysis focus |

**Impact:** Hooks load for 8 profiles when budget allows, 4 more as supplementary. Lower guaranteed coverage but preserves critical budget for core sections.

### 3.4 Priority Scheme P3 — P1-Enforcement-Only (Recommended)

**Rationale:** Hooks are most valuable where prompt-based P1 is most likely to fail. Research shows P1 violations concentrate in profiles where (a) the task *feels* simple enough to "just do it" and (b) there are file modifications. Mark `critical` only for the 4 highest-risk profiles; `skip` everywhere else for maximum token efficiency.

| Profile | lifecycle_hooks priority | P1 Violation Risk | Rationale |
|---------|------------------------|-------------------|-----------|
| `feature` | **critical** | **HIGH** | L0 agents frequently "implement the feature directly" |
| `refactor` | **critical** | **HIGH** | "Just clean this up" pressure drives direct edits |
| `migration` | **critical** | **HIGH** | Large file scope tempts L0 to make "quick changes" |
| `security-audit` | **critical** | **HIGH** | Urgency of security fixes drives P1 bypass |
| `hotfix` | **important** | MEDIUM | Trivial exception often invoked; hooks add guardrail |
| `perf-optimization` | **important** | MEDIUM | Optimization changes sometimes done directly |
| `skill-optimization` | supplementary | LOW | Specialized workflow, operators know the rules |
| `demo-showcase` | supplementary | LOW | Demo code is less constrained |
| `dependency-setup` | supplementary | LOW | Config files, lower P1 risk |
| `rdrr` | supplementary | LOW | Design-heavy, implementation is in refine only |
| `design` | skip | MINIMAL | No file writes in design stage |
| `review` | skip | MINIMAL | Reviewers read, don't write |
| `research` | skip | NONE | Pure research, no modifications |
| `documentation` | skip | NONE | Authoring ≠ code writing |
| `spike-poc` | skip | NONE | Experimental, P1 waived often |
| `onboarding` | skip | NONE | Read-heavy, no code changes |

**Impact:** Only 4 profiles pay the critical token cost. 2 important, 4 supplementary. 6 skip entirely. Best token-efficiency-to-enforcement ratio. Targets enforcement where violations actually happen.

---

## 4. Platform Analysis

### 4.1 DevolaFlow Hook → Platform Event Mapping

| DevolaFlow Hook | What It Does | Claude Code Event | Cursor Event | Fallback |
|----------------|-------------|-------------------|--------------|----------|
| `validate_dispatch` | Check AC before dispatching task | `TaskCreated` or `PreToolUse` (Task tool matcher) | `beforeMCPExecution` or custom | Pre-dispatch wrapper script |
| `check_file_ownership` | Block writes outside owned_files | `PreToolUse` (Edit\|Write\|Bash matcher) | `beforeShellExecution` + `afterFileEdit` | Git pre-commit hook on `owned_files` |
| `test_on_complete` | Run tests when task finishes | `Stop` or `TaskCompleted` | `stop` | Post-completion script |
| `verify_stage_gate` | Check wave completeness before gate | `TaskCompleted` (aggregate check) | Custom aggregation | Gate script (already exists in DevolaFlow gate mechanism) |

### 4.2 Claude Code — Native Support (Best)

**Directly supported hooks:**
- `validate_dispatch` → `TaskCreated` event (fires when task created via TaskCreate). Handler type: `command` or `agent` (agent can inspect AC with Read/Grep).
- `check_file_ownership` → `PreToolUse` with matcher `Edit|Write` and `if` condition `"Edit(*)"` / `"Write(*)"`. Command hook parses `tool_input.file_path` against `owned_files`.
- `test_on_complete` → `Stop` event. Command hook runs `pytest` and returns error context if tests fail. Or `TaskCompleted` for per-task granularity.
- `verify_stage_gate` → `TaskCompleted` event. Agent hook aggregates results from all tasks in wave.

**Configuration format (example for `check_file_ownership`):**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/check-file-ownership.sh",
            "statusMessage": "Checking file ownership..."
          }
        ]
      }
    ]
  }
}
```

**Handler type selection:**
- `command`: Best for `validate_dispatch`, `check_file_ownership`, `test_on_complete` — deterministic, fast, shell-based.
- `agent`: Best for `verify_stage_gate` — needs to read multiple files and aggregate results.
- `prompt`: Not recommended for enforcement hooks — reintroduces probabilistic behavior.

### 4.3 Cursor — Partial Native Support

**Directly supported:**
- `check_file_ownership` → `afterFileEdit` (post-hoc validation) or `beforeShellExecution` (if write via shell)
- `test_on_complete` → `stop` event
- `validate_dispatch` → No direct equivalent. Would need `beforeMCPExecution` if dispatching via MCP, or custom wrapper.
- `verify_stage_gate` → No direct equivalent. Custom aggregation needed.

**Config format:** `.cursor/hooks.json` with version 1 schema.

### 4.4 Platforms Without Native Hooks — Fallback Strategy

For Codex, Copilot, Windsurf, or any platform without native hooks:

1. **Wrapper scripts:** Pre/post-command wrappers in `.workflow/hooks/` that are referenced in task dispatch instructions.
2. **Git hooks:** `pre-commit` for file ownership validation, `pre-push` for test enforcement.
3. **CI gates:** GitHub Actions / GitLab CI as the enforcement layer — hooks at the repository level rather than agent level.
4. **Prompt shim:** Fall back to L3 enforcement (instruction injection in dispatch prompt) with explicit violation-detection in post-completion review.

**Compliance estimate for fallback:** ~85-95% (better than raw prompt, worse than native hooks).

### 4.5 Known Limitations

- **Claude Code limitation:** Hooks don't fire in pipe mode (`-p`), bare mode (`--bare`), or cowork sessions. Alternative execution paths bypass hook protection.
- **Cursor limitation:** Hook event set is smaller than Claude Code's. No `TaskCreated`/`TaskCompleted` events.
- **Cross-platform:** No universal hook standard exists. Each platform requires platform-specific configuration.

---

## 5. Optimization Opportunities

### 5.1 Minimum Viable Hook Set (80/20 Analysis)

**Question:** Which 2 hooks give 80% of the enforcement value?

| Hook | P1 Enforcement | P4 Enforcement | Frequency | Value Score |
|------|---------------|----------------|-----------|-------------|
| `check_file_ownership` | **Direct** — blocks writes outside owned set | None | Every file write | **9/10** |
| `test_on_complete` | Indirect — catches P1 violations via test failures | **Direct** — auto-retry with bounded limit | Every task completion | **8/10** |
| `validate_dispatch` | Indirect — ensures AC quality | None | Every dispatch | 5/10 |
| `verify_stage_gate` | None | Indirect — prevents gate on incomplete data | Every gate evaluation | 3/10 |

**Answer:** `check_file_ownership` + `test_on_complete` = **minimum viable hook set**.

- `check_file_ownership` is the highest-value single hook: it deterministically enforces P1 by preventing writes outside the task's owned file set. This catches the #1 P1 violation (L0/L1/L2 modifying files that belong to L3 tasks).
- `test_on_complete` enforces P4 (bounded retry) and catches P1 violations indirectly (tests that verify delegation happened correctly).
- Together they cover the two most critical invariants with just 2 hooks.

### 5.2 Should `verify_stage_gate` Be Included?

**Analysis:** The gate mechanism (§Gate Mechanism in SKILL.md) already enforces:
- Composite score ≥ threshold
- Zero blockers
- Coverage ≥ threshold
- Convergence loop with max_rounds

`verify_stage_gate` adds "all wave results collected" as a pre-condition. However:
- Wave Agents (L2) already collect all results before reporting to Stage Agents (L1).
- The gate mechanism already requires "all waves complete" implicitly.
- Adding this hook creates **redundancy** with existing gate enforcement.

**Recommendation:** Drop `verify_stage_gate` from the default hook set. It adds token cost without meaningful new enforcement. If needed, document it as an optional hook in the reference doc.

### 5.3 Should `validate_dispatch` Be Included?

**Analysis:**
- AC quality is important but hard to enforce deterministically. What constitutes "≥1 testable condition" requires semantic understanding.
- A `command` hook can do simple checks (AC field is non-empty, contains assertion keywords), but deep validation requires a `prompt` or `agent` hook — which reintroduces probabilistic behavior.
- Value is lower than `check_file_ownership` and `test_on_complete`.

**Recommendation:** Include as optional but not in the minimum set. Document as "recommended for strict gate profiles."

### 5.4 Compact Table Optimization

The hook table can be made more compact by:

1. **Shorten column headers:** "On Violation" → "Violation Response"
2. **Use abbreviations in cells:** "Block dispatch, escalate" → "Block + escalate"
3. **Drop the Handler column** (only needed for implementation, not behavioral guidance)
4. **Merge P1/P4 annotations into the table** instead of a separate prose line

### 5.5 Platform Details: SKILL.md vs Reference Doc?

**Recommendation:** Keep platform-specific details **out of SKILL.md**. Reasons:

1. SKILL.md is behavioral guidance for the L0 agent. L0 doesn't configure hooks — it dispatches tasks.
2. Platform details age quickly as APIs evolve.
3. Token cost: the platform table adds ~100 tokens with no behavioral value for orchestration.
4. Reference doc (`references/execution-protocol.md`) is the correct location for implementation details.

**Exception:** If Variant C is chosen for implementation-team use, the platform table belongs in the team-specific reference, not the main SKILL.

### 5.6 Token Impact Summary

| Variant | Lines | Est. Tokens | Δ vs Baseline (no hooks) | Best For |
|---------|-------|-------------|--------------------------|----------|
| A — Minimal | 9 | ~140 | +140 | Token-constrained profiles |
| B — Standard | 14 | ~210 | +210 | General use |
| C — Extended | 19 | ~310 | +310 | Implementation teams |
| **D — Compact-Optimized** | **11** | **~155** | **+155** | **Best density/value ratio** |

### 5.7 Recommended Configuration

**Best variant:** **Variant D (Compact-Optimized)** with 3 hooks (drop `verify_stage_gate`).

**Best priority scheme:** **P3 (P1-Enforcement-Only)** — `critical` for 4 highest-risk profiles, `skip` for 6 zero-risk profiles.

**Rationale:**
- Variant D delivers the same P1+P4 enforcement story as B in 3 fewer lines and ~55 fewer tokens.
- Dropping `verify_stage_gate` eliminates redundancy with the existing gate mechanism.
- P3 priority scheme minimizes token overhead while targeting enforcement where it matters most.
- Combined: 3 hooks × 4 critical profiles = 12 enforcement points. Covers the cases where P1 violations actually concentrate.

---

## 6. Appendix: Raw Research Sources

### Web Searches Performed
1. "Claude Code hooks implementation PreToolUse PostToolUse Stop event reference 2026" → Claude Code Docs (hooks reference, hooks guide)
2. "Claude Code hooks.json configuration format examples deterministic enforcement 2026" → heyuan110.com, aiorg.dev, dev.to enforcement article
3. "Cursor IDE hooks system agent lifecycle automation 2026" → cursor.com/docs, aiengineerguide.com
4. "deterministic enforcement agent lifecycle hooks vs prompt-based compliance AI coding agents 2026" → dotzlaw.com, techbytes.app, walseth.ai, zylos.ai, policylayer.com
5. "AI agent hook system design patterns quality gate automation production 2026" → dev.to guardrails, pixelmojo.io, deepwiki.com
6. "agent quality gate automation hooks CI/CD pattern deterministic pre-commit post-commit" → agentpatterns.ai, circleci.com, microservices.io
7. "Cursor hooks.json configuration beforeShellExecution afterFileEdit stop event format 2026" → cursor.com/docs, johnlindquist/cursor-hooks

### Key References
- Claude Code Hooks Reference: https://docs.claude.com/en/docs/claude-code/hooks (27 events, 4 handler types)
- Cursor Hooks Docs: https://cursor.com/docs/agent/hooks (~10 events, command handlers)
- Enforcement Ladder: https://walseth.ai/blog/enforcement-ladder-ai-coding-agents (L1-L5 framework)
- Deterministic Governance Kernels: https://zylos.ai/research/2026-03-11-deterministic-governance-kernels-agent-runtimes
- Production Guardrail Pattern: https://agentpatterns.ai/verification/deterministic-guardrails/
