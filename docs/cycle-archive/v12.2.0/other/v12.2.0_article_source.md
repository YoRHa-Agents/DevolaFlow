Karpathy CLAUDE.md Rules + 8 More: The 12-Rule Template (2026)

EN

Late January 2026: Andrej Karpathy posts a thread on X complaining about how Claude writes code. Three failure modes — silent wrong assumptions, over-complication, orthogonal damage to code it shouldn't have touched. Forrest Chang reads the thread, packages the complaints into 4 behavioral rules in a single CLAUDE.md file, drops it on GitHub. 5,828 stars in the first day. 60,000 bookmarks in two weeks. 120,000 stars by mid-2026. The fastest-growing single-file repo of the year. On May 9, 2026, a verified developer with the handle @mnilax (Mnimiy) posted a long-form X article with one of the year's sharpest engineering claims: they tested the template across 30 codebases for 6 weeks, then added 8 more rules to close the gaps. 2.7 million views, 18,800 bookmarks. This is the full breakdown — and what it means if you're running Claude inside Antigravity (or any other agent IDE) with a [GEMINI.md or AGENTS.md](https://antigravity.codes/blog/antigravity-gemini-md-system-prompt-guide) file.

Get the latest on AI, LLMs & developer tools

New MCP servers, model updates, and guides like this one — delivered weekly.

Subscribe

> — @Mnilax [May 9, 2026](https://twitter.com/Mnilax/status/2053116311132155938?ref_src=twsrc%5Etfw)

The original X post by @mnilax that this article unpacks — 2.7M views, 18.8K bookmarks, May 9, 2026.

## 1. The Viral Moment

Karpathy's original thread wasn't prescriptive. It was a complaint — the kind senior engineers post after a bad afternoon. Three specific failure modes:

1. Silent wrong assumptions. Claude infers what you meant, builds on the wrong inference, never tells you.
2. Over-complication. Claude reaches for abstractions, layers, generic helpers. The 4-line fix becomes 40 lines.
3. Orthogonal damage. Claude "improves" code it shouldn't have touched — whitespace, naming, formatting, adjacent functions that weren't asked about.

Forrest Chang read the thread and did the work nobody else did: he wrote down what Karpathy was implicitly asking for. Four short, imperative rules. One file. 65 lines. Public repo. The pacing matters — Forrest didn't add commentary, didn't turn it into a framework, didn't monetize. Just the rules.

It hit a nerve. Developers who'd been fighting Claude every day suddenly had a one-line install: paste this file at your repo root. The metrics tell the story — 120,000 stars on a file with no code in it. Most of those developers are still running just those four rules today.

## 2. The Original 4 Rules (Karpathy via Forrest Chang)

Here's the floor — the rules in their authored form. If you don't have any CLAUDE.md today, start with these:

Rule 1 — Think Before Coding. No silent assumptions. State what you're assuming. Surface tradeoffs. Ask before guessing. Push back when a simpler approach exists.

Rule 2 — Simplicity First. Minimum code that solves the problem. No speculative features. No abstractions for single-use code. If a senior engineer would call it overcomplicated, simplify.

Rule 3 — Surgical Changes. Touch only what you must. Don't "improve" adjacent code, comments, or formatting. Don't refactor what isn't broken. Match existing style.

Rule 4 — Goal-Driven Execution. Define success criteria. Loop until verified. Don't tell Claude what steps to follow; tell it what success looks like and let it iterate.

Mnimiy's data: these four close ~40% of the failure modes in unsupervised Claude Code sessions. The remaining ~60% live in the gaps the original template doesn't address.

## 3. Why It Needed Extending

The template was written in January 2026. The Claude Code ecosystem in May 2026 is a different animal. The article calls out four post-January realities the original 4 rules don't cover:

- Agent fights. Multi-agent setups where two agents edit the same files and step on each other. Karpathy's rules assume a single autocomplete loop. Real [multi-agent orchestration](https://antigravity.codes/blog/antigravity-agent-orchestration-multi-agent) needs ownership rules.
- Hook cascades. Claude Code hooks fire on every tool call. Without budgets, one chatty hook turns a 200-token request into 8,000 tokens.
- Skill loading conflicts. Multiple [Skills](https://antigravity.codes/blog/antigravity-skills-setup-guide) with overlapping descriptions confuse the description-matching dispatcher. The original template has nothing on how to disambiguate.
- Multi-step workflows. A 6-step refactor going wrong at step 4 means steps 5 and 6 are built on a broken state. The original template treats every Claude turn as a one-shot.

Mnimiy's thesis: the original 4 are foundational, not wrong. They're incomplete.

## 4. The 8 New Rules (Each With the Moment That Earned It)

Each of these came from a specific incident across the 30-codebase study. The article shows the moment, then the rule. Below: same structure, condensed.

### Rule 5 — Don't make the model do non-language work

Deterministic decisions belong in deterministic code. Retry policies, routing, escalation thresholds — not LLM calls. The model decides differently every week.

The moment: A "decide whether to retry on 503" LLM call worked for two weeks, then started flaking because the model began reading the request body as context for the decision. The retry policy went random because the prompt was effectively random.

### Rule 6 — Hard token budgets, no exceptions

Every loop has a chance to spiral into a 50,000-token context dump. The model won't stop on its own. Budgets give you a hard floor.

The moment: A 90-minute debugging session iterating on the same 8KB error message. By the end, Claude was suggesting fixes the user had rejected 40 messages earlier. A token budget would have killed the loop at minute 12.

### Rule 7 — Surface conflicts, don't average them

When two parts of the codebase disagree, Claude tries to please both. The result is incoherent code that combines both patterns and works correctly under neither.

The moment: A codebase had two error-handling patterns — async/await with try/catch and a global error boundary. Claude wrote code that did both. Errors got swallowed twice. 30 minutes to figure out.

### Rule 8 — Read before you write

Karpathy's "Surgical Changes" tells Claude not to touch adjacent code. It doesn't tell Claude to understand adjacent code. Without this addition, Claude writes new code that conflicts with existing code 30 lines away.

The moment: Claude added a function next to an existing identical function it hadn't read. The new one won by import order. The original had been the source of truth for 6 months.

### Rule 9 — Tests are not optional, but they're not the goal

Goal-Driven Execution treats "tests pass" as success. In practice, Claude writes code that passes shallow tests while breaking production behavior.

The moment: 12 tests for an auth function, all passing, auth broken in production. The tests checked the function returned something, not whether it returned the right thing. Function passed because it was returning a constant.

### Rule 10 — Long-running operations need checkpoints

The original template assumes one-shot interactions. Real Claude Code work is multi-step — refactors across 20 files, features over a session, debugging across commits. Without checkpoints, one wrong turn loses all progress.

The moment: A 6-step refactor went wrong on step 4. Claude proceeded to do steps 5 and 6 on top of the broken state. Untangling took longer than redoing the whole refactor.

### Rule 11 — Convention beats novelty

In a codebase with established patterns, Claude likes to introduce its own. Even when its way is "better," introducing a second pattern is worse than either pattern alone.

The moment: Claude introduced React hooks into a class-component codebase. The hooks worked. They also broke the codebase's testing patterns, which assumed`componentDidMount`. Half a day to remove and rewrite.

### Rule 12 — Fail visibly, not silently

The most expensive Claude failures look like success. A function "works" but returns wrong data. A migration "completes" but skipped 30 records. A test "passes" but the assertion was wrong.

The moment: Claude reported a database migration "completed successfully." It had silently skipped 14% of records that hit a constraint violation. The skip was logged but not surfaced. Discovered 11 days later when reports started looking wrong.

## 5. The Numbers

Mnimiy tracked the same 50 representative tasks across 30 codebases over 6 weeks, in three configurations: no CLAUDE.md, original 4 rules, full 12 rules. Mistake rate is the share of tasks that required correction or rewrite to match intent — counted across seven distinct failure types (silent wrong assumption, over-engineering, orthogonal damage, silent failure, convention violation, conflict averaging, missed checkpoint).

RESULTS ACROSS 30 CODEBASES, 50 TASKS, 6 WEEKSNo CLAUDE.md: mistake rate ~41%, no baseline compliance4 rules: mistake rate ~11%, compliance 78%12 rules: mistake rate ~3%, compliance 76%

The headline drop (41% → 3%) is the obvious result. The interesting result is that going from 4 rules to 12 added almost no compliance overhead (78% → 76%) while cutting the mistake rate by another 8 points. The new rules cover failure modes the original 4 didn't touch — they don't compete for the same attention budget.

This is the empirical case for going past 4. If adding rules cost compliance proportionally, you'd stop at 4. It doesn't.

## 6. Where the Original Template Silently Breaks

Four scenarios where Karpathy's 4 are not enough — even before adding rules. The article is explicit that the original isn't wrong, it's addressing January 2026's problem space:

1. Long-running agent tasks. The rules target the moment Claude writes code. They're silent on multi-step pipelines. No budget rule. No checkpoint rule. No fail-loud rule. Pipelines drift.
2. Multi-codebase consistency. "Match existing style" assumes one style. In a monorepo with 12 services, Claude has to pick which style. The original rules don't tell it how. It picks randomly or averages.
3. Test quality. Goal-Driven Execution treats "tests pass" as success. Doesn't say tests have to be meaningful. The result is tests that test nothing useful but make Claude confident.
4. Production vs prototype. The same 4 rules that protect production code from over-engineering also slow down prototypes that legitimately need 100 lines of speculative scaffolding to figure out a direction. "Simplicity First" overfires on early-stage code.

## 7. What Didn't Work (The Failed Experiments)

Possibly the most useful section of the article — not the rules that made the cut, but the patterns that explicitly didn't:

- Rules collected from social media. Most were either restatements of Karpathy's 4 with different words, or domain-specific rules ("always use Tailwind classes") that don't generalize. Cut.
- More than 14 rules. Mnimiy tested up to 18. Compliance dropped from 76% to 52% past 14. The 200-line ceiling Anthropic documents is real — past it, Claude pattern-matches to "rules exist" without actually reading them.
- Tooling-dependent rules. "Always use eslint" breaks silently when eslint isn't installed. Replaced with capability-agnostic phrasings: "match the codebase's enforced style."
- Examples instead of rules. Three examples cost as much context as ~10 rules and Claude over-fits to them. Rules are abstract, examples are specific. Use rules.
- Vague intensifiers. "Be careful," "think hard," "really focus." Compliance ~30% because none of those are testable. Replaced with concrete imperatives like "state assumptions explicitly."
- Identity prompts. Telling Claude to be "senior" doesn't work. Claude already thinks it's senior. The compliance gap is between thinking and doing. Imperatives close it; identity prompts don't.

## 8. The Mental Model

Strip the article down to its load-bearing sentence and you get this:

CLAUDE.md is not a wishlist. It's a behavioral contract that closes specific failure modes you've observed.

Every rule should answer: what mistake does this prevent?

This reframes everything. Most developers treat CLAUDE.md as a personal preferences file — a list of stylistic likes and dislikes that grows over time. The article's argument is that a preferences file is the wrong shape. The right shape is a list of failure modes you've actually hit, with one rule per mode.

It also explains why the article ends with a counterintuitive recommendation:

> A 6-rule CLAUDE.md tuned to your real failure modes beats a 12-rule one with 6 rules you'll never need.

Don't paste all 12 because someone on X said so. Read them, keep the ones that map to mistakes you've made, drop the rest.

## 9. Mapping It to Antigravity (GEMINI.md / AGENTS.md)

The article is Claude-focused, but the abstraction is portable. Antigravity reads procedural rules from two files in the same shape:

- GEMINI.md — the Gemini-specific system prompt file. See our [GEMINI.md guide](https://antigravity.codes/blog/antigravity-gemini-md-system-prompt-guide).
- AGENTS.md — the cross-tool format (works with Claude Code, Cursor, Antigravity). See our [AGENTS.md guide](https://antigravity.codes/blog/antigravity-agents-md-guide).

Both are advisory not enforced, both cap around 200 lines before compliance falls off, both follow the same "state the rule, no examples, no vague intensifiers" discipline. The 12 rules transfer essentially unchanged. Specific Antigravity considerations:

1. Rule 6 (token budgets) becomes critical, not optional. Antigravity quota burns faster than Claude Code does. Pair the rule with our [token-reduction playbook](https://antigravity.codes/blog/antigravity-save-tokens-reduce-quota).
2. Rule 10 (checkpoints) maps to Antigravity's Agent Manager. If a multi-agent run goes wrong on step 4, you want to be able to kill the agent and resume from a previous artifact, not from scratch.
3. Rule 7 (surface conflicts) helps with model swaps. If you switch between Gemini and Claude Opus mid-session (as covered in our [model-swap analysis](https://antigravity.codes/blog/antigravity-model-swap-silent-downgrade-explained)), the new model often inherits stale context from the old one and tries to reconcile incompatible patterns.
4. Rule 12 (fail visibly) is the most underrated for Autopilot. If you run [auto-accept](https://antigravity.codes/blog/antigravity-auto-accept-autopilot-guide), silent failures compound across multiple Cmd-Enter cycles before you see them. Force the agent to surface every skipped step.

Same template, different runtime, same logic.

Get the latest on AI, LLMs & developer tools

New MCP servers, model updates, and guides like this one — delivered weekly.

Subscribe

## 10. The Full 12-Rule Template (Copy-Paste Ready)

Save this as`CLAUDE.md`(or`GEMINI.md` or`AGENTS.md`) at your repo root. The original article notes: keep total file size under 200 lines combined including any project-specific additions below, past that compliance falls off.

# Coding Behavior Contract (12 Rules) ## Core (Karpathy via Forrest Chang) 1. Think before coding. State your assumptions. Surface tradeoffs. Ask before guessing. Push back when a simpler approach exists. 2. Simplicity first. Minimum code that solves the problem. No speculative features. No abstractions for single-use code. 3. Surgical changes. Touch only what is asked. Do not "improve" adjacent code, comments, or formatting. Match existing style. 4. Goal-driven execution. Define success criteria. Loop until verified. Do not narrate steps; tell me what success looks like. ## Extended (Mnimiy, May 2026) 5. Do not make the model do non-language work. Retry policies, routing, escalation thresholds belong in deterministic code. 6. Hard token budgets, no exceptions. Stop and ask if a task is trending past its budget. 7. Surface conflicts, do not average them. If two parts of the codebase disagree, flag the disagreement and ask which to follow. 8. Read before you write. Understand adjacent code (the file and nearby siblings) before adding new code. 9. Tests are required but are not the goal. A passing test that tests nothing useful is a failure. Tests must check behavior. 10. Long-running operations require checkpoints. After every significant step, summarize what was done and confirm before proceeding. 11. Convention beats novelty. In an established codebase, match the existing pattern even if a "better" one exists. 12. Fail visibly, not silently. Surface every skipped record, every rolled-back transaction, every constraint violation. Never report success when something was bypassed. ## Project-specific rules below this line # (Add stack, test commands, error patterns specific to this repo.) # Total file should stay under 200 lines.

That's the file. Two things to do with it:

1. Read the 12 honestly. Which ones map to mistakes you've actually made this month? Keep those. Drop the rest. A 6-rule file tuned to your failure modes beats a 12-rule file with rules you'll never trigger.
2. Append project-specific rules below. Stack-specific ("always use the Repository pattern"), test-runner ("run pnpm test:unit before reporting done"), error patterns. Keep the total under 200 lines.

## 11. FAQ

### What is the CLAUDE.md 12-rule template?

It's an extension of the 4-rule CLAUDE.md file Forrest Chang built around Andrej Karpathy's January 2026 thread on Claude's failure modes. Mnimiy (@mnilax) tested the original across 30 codebases for 6 weeks and published 8 additional rules in May 2026 to cover problems that emerged after the original was written — agent fights, hook cascades, skill loading conflicts, and multi-step workflow drift.

### Who is Karpathy and who packaged the original 4 rules?

Andrej Karpathy is the well-known AI researcher (ex-Tesla, OpenAI). He posted a thread in late January 2026 enumerating three failure modes he kept seeing in Claude's code generation: silent wrong assumptions, over-complication, and orthogonal damage. Forrest Chang read the thread, packaged the complaints into 4 behavioral rules in a single CLAUDE.md file, and put it on GitHub. The repo hit 5,828 stars in the first day and 120,000 stars by mid-2026 — the fastest-growing single-file repo of the year.

### How much do these rules actually reduce mistakes?

Mnimiy's measurements across 30 codebases and 50 representative tasks: with no CLAUDE.md, mistake rate ~41%. With the original 4 rules, ~11%. With the full 12 rules, ~3%. Compliance — how often Claude visibly applied the relevant rule — stayed roughly flat between 4 and 12 rules (78% → 76%), suggesting the new rules cover failure modes the original 4 didn't address, rather than competing for the same attention budget.

### Does this apply to Antigravity, since Antigravity uses Gemini, not Claude?

Yes. Antigravity reads procedural rules from AGENTS.md and GEMINI.md files in the same shape: a Markdown file at the repo root, advisory not enforced, capped around 200 lines before compliance falls off. The 12 rules transfer almost word-for-word. We cover the practical mapping in Antigravity's AGENTS.md and GEMINI.md guides linked below.

### Why 12 rules and not more?

Mnimiy tested up to 18 rules. Compliance dropped from 76% to 52% past 14. The 200-line ceiling that Anthropic documents is real: past that, Claude starts pattern-matching to 'rules exist' without actually reading them. The discipline of the template is keeping it small enough that every rule gets read every session.

### Should I use all 12 rules or pick a subset?

Pick. The article is explicit: 'a 6-rule CLAUDE.md tuned to your real failure modes beats a 12-rule one with 6 rules you'll never need.' Read the 12, keep the ones that map to mistakes you've actually made, drop the rest. If you don't run multi-step pipelines, Rule 10 (checkpoints) doesn't matter for you. If your codebase has one linted style, Rule 11 (convention beats novelty) is redundant.

### Where does the original Karpathy template silently break?

Mnimiy identifies four gaps: (1) long-running agent tasks — no budget, no checkpoint, no fail-loud rules; (2) multi-codebase consistency — 'match existing style' assumes one style, fails in monorepos with multiple services; (3) test quality — 'tests pass' as the only goal means Claude writes tests that test nothing; (4) production vs prototype — 'Simplicity First' overfires on early-stage code that legitimately needs speculative scaffolding.

### What approaches did Mnimiy try that didn't work?

Five things failed: (1) collecting rules from social media — mostly restatements or non-generalizable; (2) more than 14 rules — compliance crash; (3) tooling-dependent rules like 'always use eslint' — fails silently when tool is missing; (4) examples instead of rules — heavier, model over-fits; (5) vague rules like 'be careful' or 'think hard' — compliance ~30% because they're not testable; (6) identity prompts like 'act like a senior engineer' — Claude already thinks it's senior. Imperative rules close the gap; identity prompts don't.

#### Related Guides

- [→ GEMINI.md System Prompt Guide](https://antigravity.codes/blog/antigravity-gemini-md-system-prompt-guide)
- [→ AGENTS.md Cross-Tool Guide](https://antigravity.codes/blog/antigravity-agents-md-guide)
- [→ Antigravity Rules: 50+ Examples](https://antigravity.codes/blog/antigravity-rules-examples)
- [→ Karpathy CLAUDE.md Skills File](https://antigravity.codes/blog/karpathy-claude-code-skills-guide)

#### Go Deeper

- [→ Multi-Agent Orchestration](https://antigravity.codes/blog/antigravity-agent-orchestration-multi-agent)
- [→ Save Tokens & Reduce Quota](https://antigravity.codes/blog/antigravity-save-tokens-reduce-quota)
- [→ Auto-Accept & Autopilot](https://antigravity.codes/blog/antigravity-auto-accept-autopilot-guide)
- [→ Full Troubleshooting Hub](https://antigravity.codes/troubleshooting)

### Get the 12-Rule CLAUDE.md / GEMINI.md / AGENTS.md Template Pack

Download the full template plus three pre-tuned variants — for solo developers, monorepo teams, and Antigravity Autopilot users. Drop-in CLAUDE.md, GEMINI.md, and AGENTS.md files plus the rule-selection worksheet.

Download Free Template Pack

We respect your privacy. Unsubscribe at any time.

Sponsored AI assistant. Recommendations may be paid.