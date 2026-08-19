# S01-T01: Deep-Dive Research — caveman & superpowers

**Task ID:** S01-T01  
**Team:** Research  
**Date:** 2026-04-11  
**DevolaFlow version context:** 3.8.0

---

## 1. Repo: caveman

**URL:** https://github.com/JuliusBrussee/caveman  
**License:** MIT  
**Focus:** Output token compression via constrained communication style  

### 1.1 Architecture & Design Philosophy

Caveman is a **single-purpose skill/plugin** for AI coding agents that forces terse, caveman-style output to cut ~75% of output tokens while preserving 100% technical accuracy. Architecture:

```
caveman/
├── caveman/SKILL.md              # Core skill (63 lines — the entire behavior spec)
├── skills/
│   ├── caveman/SKILL.md          # Identical copy for skills/ namespace
│   ├── caveman-commit/SKILL.md   # Terse commit messages (65 lines)
│   └── caveman-review/SKILL.md   # One-line PR review comments (55 lines)
├── caveman-compress/
│   ├── SKILL.md                  # Input token compression skill (111 lines)
│   └── scripts/
│       ├── compress.py           # Orchestrator: compress → validate → fix loop
│       ├── validate.py           # Structural validator (headings, code blocks, URLs, paths)
│       └── detect.py             # File type classifier (natural language vs code vs config)
├── hooks/
│   ├── caveman-activate.js       # SessionStart hook — writes flag + injects rules
│   └── caveman-mode-tracker.js   # UserPromptSubmit hook — tracks /caveman mode changes
├── benchmarks/run.py             # Real API benchmarks (normal vs caveman output tokens)
└── evals/                        # 3-arm eval harness (baseline vs terse vs skill)
```

**Key design decisions:**

- **Skills as behavior contracts.** Each SKILL.md is a complete, self-contained behavior specification. The core caveman skill is only 63 lines — minimal yet sufficient to change agent output behavior dramatically.
- **Intensity levels as a slider.** Lite/Full/Ultra + Wenyan variants let users trade off readability vs compression. Level persists per session.
- **Auto-Clarity escape hatch.** Caveman drops terse mode for security warnings, irreversible actions, and confusing multi-step sequences. This prevents the optimization from causing harm.
- **Hooks for state persistence.** SessionStart hook writes a flag file; UserPromptSubmit hook tracks mode changes. Flag file bridges hooks (agent-visible) and statusline (user-visible).

### 1.2 Token/Cost Metrics

| Metric | Value | Source |
|--------|-------|--------|
| Output token reduction | 65% avg (22%–87% range) | benchmarks/run.py, 10 prompts |
| Input token reduction (compress) | 45% avg (35%–60% range) | caveman-compress, 5 test files |
| Core skill size | 63 lines | caveman/SKILL.md |
| Commit skill size | 65 lines | skills/caveman-commit/SKILL.md |
| Review skill size | 55 lines | skills/caveman-review/SKILL.md |
| Compress skill size | 111 lines | caveman-compress/SKILL.md |

**Benchmark methodology:** Real Claude API calls, 3 trials per prompt, median token counts. Three-arm eval design (baseline / terse / skill) isolates skill contribution from generic terseness.

### 1.3 Key Patterns & Techniques

1. **Compression-by-rule (not summarization).** Caveman defines explicit drop lists (articles, filler, pleasantries, hedging) and preserve lists (code blocks, URLs, paths, technical terms). This is **deterministic** — no LLM judgment needed for what to compress.

2. **Validate-then-fix loop.** `compress.py` uses a 3-step pipeline: compress → validate → cherry-pick fix. Validation checks structural invariants (heading count, code block preservation, URL integrity). If validation fails, a targeted fix prompt addresses only the specific errors — no full recompression. Max 2 retries, then restore original. This is a bounded convergence loop.

3. **File type detection before action.** `detect.py` classifies files as natural_language/code/config before compression. Uses extension-based classification + content heuristics (code patterns, JSON detection, YAML indicators). Prevents compressing code files.

4. **Pattern-based output format.** The core skill defines a pattern: `[thing] [action] [reason]. [next step].` with positive/negative examples. This is more effective than abstract instructions.

5. **Benchmark-driven README.** Benchmark results are embedded in README via markers (`<!-- BENCHMARK-TABLE-START -->`) and auto-updated by the benchmark script. Numbers are always real, never hand-written.

### 1.4 Quality Enforcement

- **Structural validation** in compress: headings, code blocks, URLs, paths, bullet counts all checked against original.
- **Three-arm evals** in evals/: control for generic terseness effect.
- **Backup-before-overwrite**: .original.md files prevent data loss.
- **Auto-Clarity rule**: automatically drops terse mode for safety-critical contexts.
- **Bounded retry**: MAX_RETRIES=2, restore original on failure.

### 1.5 DevolaFlow Relevance Score: **4/5**

Caveman's compression philosophy directly maps to DevolaFlow's CO-1 (Lean Message Format) and CO-2 (Verbatim Extraction) rules. The validate-then-fix loop mirrors DevolaFlow's convergence loop pattern. The intensity levels concept maps well to context budget tiers. However, caveman focuses on human-readable output compression, while DevolaFlow needs inter-agent message compression — the techniques transfer but the application domain differs.

### 1.6 Integration Ideas for DevolaFlow

| # | Idea | Relevant DevolaFlow Rules | Estimated Effort | Description |
|---|------|--------------------------|-----------------|-------------|
| 1 | **Lean dispatch compression rules** | CO-1, CO-2 | Low | Adapt caveman's explicit drop/preserve lists into lean-dispatch.yaml and lean-report.yaml schemas. Define specific words/patterns to drop from StatusReport.delta and TaskDispatch.key_facts (articles, hedging, filler). Define strict preserve lists (paths, hashes, metric values, error messages — already CO-2 mandated). |
| 2 | **Validate-then-fix for inter-agent messages** | CO-2, CP-4 | Medium | Implement a structural validator analogous to caveman-compress's validate.py for lean messages. Check: all file paths in key_facts exist, error messages are verbatim extractions (not paraphrases), metric values match source. Integrate into lifecycle hooks (validate_dispatch already exists as a hook point). |
| 3 | **Intensity-tiered context profiles** | CO-3, CO-6 | Medium | Extend context_profiles.yaml with compression intensity levels per section. Currently sections have priority (critical/important/supplementary/skip). Add a `compression` field: `full` (include as-is), `terse` (drop filler per caveman rules), `ultra` (telegraphic, arrows for causality). Apply terse/ultra to supplementary sections before including them if within budget. |
| 4 | **Benchmark-embedded documentation** | CO-5, CP-5 | Low | Adopt caveman's pattern of auto-updating benchmark results in README/SKILL.md via markers. Add `<!-- EVOBENCH-SUMMARY-START -->` markers to README.md and auto-fill from latest benchmark run. |
| 5 | **Auto-Clarity for safety** | P4 (bounded retry) | Low | Adopt caveman's Auto-Clarity pattern in DevolaFlow's lean messaging: when a message concerns security warnings, irreversible actions, or escalation (ExceptionEscalation schema), switch from lean to verbose format. Already partially implemented via ExceptionEscalation typed messages, but not explicitly enforced as a compression escape hatch. |

---

## 2. Repo: superpowers

**URL:** https://github.com/obra/superpowers  
**License:** MIT  
**Focus:** Complete composable software development workflow for AI coding agents  

### 2.1 Architecture & Design Philosophy

Superpowers is a **full workflow framework** built on composable skills that chain together to form a mandatory development process. Architecture:

```
superpowers/
├── skills/
│   ├── brainstorming/SKILL.md              # Socratic design refinement (165 lines)
│   ├── writing-plans/SKILL.md              # Detailed implementation planning (150 lines)
│   ├── executing-plans/SKILL.md            # Batch execution with checkpoints (71 lines)
│   ├── subagent-driven-development/SKILL.md # Fresh subagent per task + 2-stage review (278 lines)
│   ├── dispatching-parallel-agents/SKILL.md # Concurrent subagent workflows (183 lines)
│   ├── test-driven-development/SKILL.md     # RED-GREEN-REFACTOR enforcement (372 lines)
│   ├── systematic-debugging/SKILL.md        # 4-phase root cause process (297 lines)
│   ├── verification-before-completion/SKILL.md # Evidence before claims (140 lines)
│   ├── writing-skills/SKILL.md              # Meta-skill: TDD for process docs (656 lines)
│   ├── requesting-code-review/SKILL.md      # Pre-review checklist
│   ├── receiving-code-review/SKILL.md       # Responding to feedback
│   ├── using-git-worktrees/SKILL.md         # Parallel development branches (218 lines)
│   └── finishing-a-development-branch/SKILL.md # Merge/PR decision workflow (201 lines)
├── hooks/
│   ├── hooks.json                           # SessionStart hook config
│   └── session-start                        # Injects using-superpowers as system context
├── commands/
│   ├── brainstorm.md
│   ├── write-plan.md
│   └── execute-plan.md
├── agents/
│   └── code-reviewer.md
└── tests/
    ├── claude-code/                         # Skill triggering, token analysis, SDD tests
    ├── skill-triggering/                    # Prompt-based skill activation tests
    ├── explicit-skill-requests/             # Multiturn skill invocation tests
    └── subagent-driven-dev/                 # Integration tests with real scaffolds
```

**Key design decisions:**

- **Skills as mandatory workflows, not suggestions.** "The agent checks for relevant skills before any task. Mandatory workflows, not suggestions." Skills trigger automatically based on context. The session-start hook injects the `using-superpowers` skill content as `<EXTREMELY_IMPORTANT>` context.
- **Composable skill chain.** brainstorming → writing-plans → (subagent-driven-development | executing-plans) → finishing-a-development-branch. Each skill explicitly declares `REQUIRED SUB-SKILL` dependencies.
- **Controller-implementer separation.** Subagent-driven-development creates a clean dispatcher-implementer split: the coordinator curates context and dispatches fresh subagents per task. Subagents never inherit session history — they get exactly what they need. This preserves coordinator context for orchestration.
- **Two-stage review gate.** After each task: spec compliance review first, then code quality review. Both must pass. Review loops until approved. This is a quality gate, not a suggestion.
- **Rationalization prevention tables.** Skills like TDD and systematic-debugging explicitly enumerate common rationalizations agents make to skip the process, with rebuttals. This is prompt engineering for enforcement.
- **TDD applied to skill creation itself.** The writing-skills meta-skill treats skill authorship as TDD: write pressure tests (RED), write minimal skill (GREEN), close loopholes (REFACTOR).

### 2.2 Token/Cost Metrics

| Metric | Value | Source |
|--------|-------|--------|
| Skill loading | Metadata-only at startup, SKILL.md on-demand | Anthropic best practices |
| Recommended SKILL.md budget | <500 lines body | anthropic-best-practices.md |
| Getting-started skill target | <150 words | writing-skills/SKILL.md |
| Frequently-loaded skill target | <200 words | writing-skills/SKILL.md |
| Other skills target | <500 words | writing-skills/SKILL.md |
| Token analysis tool | tests/claude-code/analyze-token-usage.py | Real session JSONL parsing |
| Model selection for subagents | cheap→standard→capable based on task complexity | subagent-driven-development/SKILL.md |
| Cross-reference strategy | Skill name only, never @ force-load | writing-skills/SKILL.md |

**Key token insight:** Superpowers explicitly warns against `@` links to skills because they force-load 200k+ context before needed. Instead, skills reference each other by name with `REQUIRED SUB-SKILL:` markers. This is progressive disclosure — only load what's needed when needed.

**Cost-aware model selection:** Subagent-driven-development explicitly tiering model selection: cheap models for mechanical 1-2 file tasks, standard for integration, most capable for architecture/review. This is cost-optimization at the dispatch level.

### 2.3 Key Patterns & Techniques

1. **Hard gates.** Brainstorming uses `<HARD-GATE>` tags: "Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it." This is deterministic enforcement in skill content.

2. **Iron Laws.** TDD: "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST." Verification: "NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE." Debugging: "NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST." These are non-negotiable rules stated as absolute constraints.

3. **Red Flags lists.** Each discipline-enforcing skill has a "Red Flags — STOP" section listing specific thought patterns that indicate the agent is about to violate the process. This is metacognitive enforcement — training the agent to recognize its own rationalization.

4. **Rationalization tables.** Structured `| Excuse | Reality |` tables that pre-counter common arguments for skipping the process. These are persuasion countermeasures (backed by Cialdini research, referenced explicitly).

5. **Implementer status protocol.** Subagent-driven-development defines exactly 4 statuses (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED) with specific handling for each. Never ignore escalation, never force retry without changes. This is a typed status contract.

6. **Spirit-over-letter clause.** "Violating the letter of the rules is violating the spirit of the rules." Added early in discipline-enforcing skills to cut off "I'm following the spirit" rationalizations.

7. **Spec compliance before code quality.** Two-stage review enforces order: spec first, quality second. This prevents "well-built but wrong" code from passing.

8. **CSO (Claude Search Optimization).** Writing-skills/SKILL.md defines explicit discovery optimization: descriptions should say WHEN to use, not WHAT the skill does. Testing showed that description-summarized workflows caused Claude to shortcut (follow description instead of reading full skill).

### 2.4 Quality Enforcement

- **Two-stage review gate**: spec compliance → code quality, both must pass with re-review loops.
- **Verification-before-completion**: "Evidence before claims, always." Fresh verification command required before any success claim.
- **Systematic debugging**: 4-phase mandatory process (root cause → pattern analysis → hypothesis → implementation). 3+ failed fixes trigger architectural questioning.
- **TDD Red-Green-Refactor**: Write test → watch fail → minimal code → watch pass → refactor. Code-before-test requires deletion, no exceptions.
- **Pressure testing for skills**: writing-skills requires baseline testing (run scenarios WITHOUT skill first) to identify what agents actually violate.
- **Session transcript analysis**: analyze-token-usage.py parses real JSONL transcripts to measure actual token costs per agent.

### 2.5 DevolaFlow Relevance Score: **5/5**

Superpowers is the closest external analog to DevolaFlow's 4-layer hierarchy. Its controller-implementer pattern directly maps to L0-L3 dispatcher-not-implementer (P1). Its two-stage review maps to DevolaFlow's gate mechanism. Its mandatory workflow enforcement aligns with P3 structured messages. Its subagent model selection maps to DevolaFlow's context budget optimization. The main difference: superpowers is flat (no L0→L1→L2→L3 layering), while DevolaFlow has explicit hierarchy. But the enforcement patterns are directly transferable.

### 2.6 Integration Ideas for DevolaFlow

| # | Idea | Relevant DevolaFlow Rules | Estimated Effort | Description |
|---|------|--------------------------|-----------------|-------------|
| 1 | **Rationalization prevention tables in SKILL.md** | P1, P4 | Low | Add `| Excuse | Reality |` tables to DevolaFlow's SKILL.md for the most violated rules. P1 (Dispatcher-Not-Implementer): "This is just one file" → "File count irrelevant. Delegate to L3." P4 (Bounded Retry): "One more attempt" → "3+ failures = escalate, don't retry." These pre-counter specific agent rationalizations. Already proven effective in superpowers testing. |
| 2 | **Red Flags checklist in agent mode protocol** | P1, Rule 1 | Low | Add a "Red Flags — STOP" section to the Agent Mode Execution Protocol (SKILL.md lines 108-135). List specific thought patterns: "Am I about to use Write/StrReplace/Shell directly?", "Am I rationalizing 'it's just one file'?", "Am I skipping decomposition because the task seems simple?" Complements the existing P1 Self-Check with metacognitive triggers. |
| 3 | **Two-stage gate verification** | CP-4, gate mechanism | Medium | Extend DevolaFlow's existing gate mechanism with superpowers' two-stage pattern: first check spec compliance (do artifacts match acceptance criteria?), then check quality (tests pass, coverage met, lint clean). Currently gate runs as a single pass. Two-stage prevents "well-tested but wrong scope" from passing. Integrate into `test_on_complete` lifecycle hook. |
| 4 | **Typed subagent status protocol** | P3, P4, lean-report.yaml | Medium | Adopt superpowers' 4-status pattern (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED) as a formal enum in StatusReport schema. Currently StatusReport has free-form status. Typed status enables deterministic routing: DONE → proceed, NEEDS_CONTEXT → provide context + retry, BLOCKED → escalate. Maps directly to P4 classified response (retry/escalate/abort). |
| 5 | **CSO-inspired skill description format** | SF-2, SKILL.md structure | Low | Adopt superpowers' CSO insight: SKILL.md description must say WHEN to use, never summarize WHAT it does. Testing proved that workflow-summarizing descriptions caused agents to shortcut instead of reading full skill content. Add this as a guideline to SF-2 rule. Prevents agents from following DevolaFlow SKILL.md description as a compressed workflow instead of reading the full decomposition protocol. |
| 6 | **Model-tiered dispatch in wave coordination** | CO-3, wave coordination | High | Adopt superpowers' model selection pattern for DevolaFlow's L2 Wave dispatch. When dispatching L3 Task Agents: use fast/cheap models for mechanical single-file tasks with clear specs, standard models for multi-file integration, most capable for architecture/design/review. Requires extending TaskDispatch schema with `model_hint` field and L2 logic to assess task complexity. Directly reduces cost in multi-agent orchestration. |

---

## 3. Cross-Repo Pattern Synthesis

### 3.1 Shared Patterns Between caveman and superpowers

| Pattern | caveman Implementation | superpowers Implementation | DevolaFlow Mapping |
|---------|----------------------|---------------------------|-------------------|
| **Bounded loops** | compress → validate → fix, MAX_RETRIES=2 | review → fix → re-review until approved | P4 bounded retry, convergence loop |
| **Preserve lists** | Code blocks, URLs, paths, technical terms | Spec requirements, test assertions | CO-2 verbatim extraction |
| **Drop lists** | Articles, filler, pleasantries, hedging | Hedging, throat-clearing, over-explanation | CO-1 lean format |
| **Safety escape hatches** | Auto-Clarity for security/irreversible actions | Verification-before-completion for all claims | P4 escalation |
| **Typed outputs** | Compression levels (lite/full/ultra) | Implementer statuses (DONE/BLOCKED/NEEDS_CONTEXT) | P3 typed YAML messages |
| **Structural validation** | Heading/code block/URL count verification | Spec compliance before code quality | Gate mechanism |
| **Progressive disclosure** | Core skill 63 lines, compress tool separate | SKILL.md overview, reference files on demand | Context profiles with section priorities |

### 3.2 Key Insight: Enforcement Ladder

Both repos demonstrate an **enforcement ladder** — a progression from soft suggestions to hard constraints:

1. **Behavioral suggestion** (weakest): "Try to be concise" — easily ignored.
2. **Rule with examples** (caveman): "Drop articles. Not: 'Sure! I'd...' Yes: 'Bug in auth...'" — pattern matching.
3. **Iron Law** (superpowers): "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST" — absolute constraint.
4. **Rationalization countermeasure** (superpowers): `| Excuse | Reality |` tables — pre-empts argument.
5. **Hard gate** (superpowers): `<HARD-GATE>` tags — blocks specific actions.
6. **Deterministic hook** (DevolaFlow 3.8.0): lifecycle hooks — code-enforced, not prompt-based.

DevolaFlow is already at level 6 for some constraints (lifecycle hooks). The gap is levels 3-5: Iron Laws, rationalization tables, and hard gates in SKILL.md content. These are **complementary** to deterministic hooks — they handle the cases where prompt-level enforcement is still needed (e.g., planning quality, decomposition decisions).

### 3.3 Key Insight: Token Efficiency in Multi-Agent Systems

Caveman optimizes **single-agent output tokens** (75% reduction). Superpowers optimizes **multi-agent orchestration tokens** via:
- Progressive disclosure (load skills on demand)
- Cross-reference by name, not `@` force-load
- Model tiering (cheap models for simple tasks)
- Controller curates context (subagents get only what they need)

DevolaFlow optimizes **inter-agent message tokens** via context profiles and lean schemas. The three approaches are **complementary layers**:

1. **Message content compression** (caveman rules applied to lean schemas) → CO-1
2. **Context loading optimization** (progressive disclosure of SKILL.md sections) → CO-3, CO-6
3. **Model cost optimization** (tier models by task complexity at dispatch) → new opportunity

---

## 4. Summary Table

| Dimension | caveman | superpowers |
|-----------|---------|-------------|
| **Primary purpose** | Output token compression | Full development workflow |
| **Architecture** | Single skill + compression tool | 12+ composable skills in a chain |
| **Skill size** | 55-111 lines | 71-656 lines |
| **Token approach** | Reduce output/input tokens via style | Reduce context loading via progressive disclosure |
| **Enforcement style** | Rules + intensity levels | Iron Laws + rationalization tables + hard gates |
| **Quality mechanism** | Structural validation | Two-stage review + verification-before-completion |
| **Hook usage** | SessionStart + UserPromptSubmit | SessionStart only |
| **Testing approach** | API benchmarks + 3-arm evals | Pressure scenarios + subagent-driven testing |
| **Agent hierarchy** | None (single agent) | Controller + implementer subagents |
| **DevolaFlow relevance** | **4/5** | **5/5** |
| **Top integration value** | Lean message compression rules | Enforcement patterns + typed status protocol |

---

## 5. Recommended Priority

**Immediate (Low effort, High impact):**
1. Rationalization prevention tables in SKILL.md — from superpowers
2. Lean dispatch compression rules (drop/preserve lists) — from caveman
3. CSO-inspired description format — from superpowers

**Next iteration (Medium effort):**
4. Typed subagent status protocol in StatusReport — from superpowers
5. Validate-then-fix for inter-agent messages — from caveman
6. Two-stage gate verification — from superpowers

**Future (High effort):**
7. Model-tiered dispatch in wave coordination — from superpowers
8. Intensity-tiered context profiles — from caveman
