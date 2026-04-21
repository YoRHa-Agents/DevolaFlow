# Interview Protocol — repo-init mode=full

> Loaded by L3 task agents executing the `interview` stage of `repo-init` (mode=full).

## 8-Phase Flow

### P1: Ask Intent

Use AskQuestion to determine:
- Which files to set up: project .rules/ only, or also personal prefs
- Whether to set up skills and hooks: both / skills only / hooks only / neither
- Which AI tools are targets: Claude / Cursor / Copilot / Codex (from analyze findings)

### P2: Explore Codebase

Reuse `analyze` stage findings. Supplement by reading:
- manifest files (package.json, pyproject.toml, Cargo.toml, go.mod)
- CI config (.github/workflows/, .gitlab-ci.yml)
- existing AI tool configs (.cursor/rules/, AGENTS.md, .claude/rules/, copilot-instructions.md)
- formatter configs (.prettierrc, ruff.toml, biome.json, rustfmt.toml)
- test configs (jest.config, vitest.config, pytest.ini, conftest.py)

Record what CANNOT be determined from code alone — these become P3 questions.

### P3: Fill Gaps

Use AskQuestion for what code analysis cannot answer:
- Team conventions: branch naming, PR flow, commit style
- Non-obvious build/test commands (especially non-standard flags or sequences)
- Required env vars or setup steps
- Architectural decisions or constraints
- Personal preferences: role, familiarity, communication style

### P4: Generate .rules/ Source Rules

Write `.rules/*.mdc` source files based on P1-P3 findings.
Compile via `sync-rules` or `RuleCompiler` to detected tool formats.
Use `propose_merge()` from `local/merge.py` when files already exist.

### P5: Generate .local/memory/prefs.md

Write personal preferences from P3 to `.local/memory/prefs.md`:
```markdown
# Personal Preferences
- Role: [from P3]
- Familiarity: [from P3]
- Communication: [from P3]
```
Optionally compile to `CLAUDE.local.md` via `compile_prefs()`.

### P6: Create Skills

Use `init_interview.detect_project_tools()` + `suggest_skills()`.
Present suggestions via AskQuestion. For each accepted skill:
- `write_skill(skill, cwd, tool)` writes `.claude/skills/<name>/SKILL.md`
- Repeat for each detected AI tool

### P7: Configure Hooks

Use `init_interview.suggest_hooks()` based on detected formatters.
Present suggestions via AskQuestion. For each accepted hook:
- Claude: write to `.claude/settings.json` hooks array
- Cursor: write to `.cursor/hooks.json` (if supported)
Use `generate_claude_hook_config()` for the JSON structure.

### P8: Summary

Output:
- List of all files created/modified
- Key configuration choices made
- Next steps and optimization suggestions
- Task Quality Score (if Standard+ complexity)

## Dispatch Context

The interview stage L3 agent receives:
- `analyze.findings` (from predecessor stage)
- This protocol page in read-only context
- `init_interview.py` module for detection/generation
- `local/merge.py` for progressive merge
- `local/compiler.py` for prefs compilation
