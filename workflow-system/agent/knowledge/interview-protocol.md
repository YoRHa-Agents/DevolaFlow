# Interview Protocol — `repo-init` Seed, `mode=full`

> Loaded by an L2 Task when a confirmed repo-init checklist item requires
> operator interview. The seed's historical `interview` primitive is
> decomposition provenance, not an executable agent layer or fixed phase.

## Contract

Inputs:

- assigned checklist IDs and owned files;
- predecessor codebase-analysis findings;
- this read-only protocol;
- `init_interview.py` detection/generation helpers;
- `local/merge.py` progressive-merge helpers;
- `local/compiler.py` preference compilation.

Outputs:

- created/modified paths;
- verbatim operator decisions;
- exact verification results;
- unresolved questions or blockers;
- an evidence-bearing StatusReport to L1.

The L2 Task does not author a Task Quality Score. L0 may score the completed
request after checklist/archive gates pass.

## Eight-Step Interview

### P1: Ask Intent

Determine:

- project `.rules/` only or personal preferences too;
- skills/hooks: both, skills only, hooks only, or neither;
- target AI tools detected from analysis.

### P2: Explore Codebase

Reuse predecessor findings. Supplement only where the dispatch permits:

- manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`);
- CI configuration;
- existing agent/rule files;
- formatter and test configuration.

Record facts that code cannot determine; these become P3 questions.

### P3: Fill Gaps

Ask one bounded question at a time about:

- branch/PR/commit conventions;
- non-obvious build/test commands;
- required environment/setup;
- architecture constraints;
- personal role, familiarity, and communication preferences.

Do not infer an answer the operator has not supplied.

### P4: Generate Rule Sources

Write `.rules/*.mdc` from confirmed findings and compile through the repository
rule compiler. If a target file exists, use `propose_merge()` rather than
silently replacing it.

### P5: Generate Preferences

When authorized, write `.local/memory/prefs.md`:

```markdown
# Personal Preferences
- Role: <confirmed>
- Familiarity: <confirmed>
- Communication: <confirmed>
```

Compile to tool-local preference surfaces only when requested.

### P6: Create Skills

Use `init_interview.detect_project_tools()` and `suggest_skills()`. Present
suggestions; call `write_skill(skill, cwd, tool)` only for accepted items.

### P7: Configure Hooks

Use `init_interview.suggest_hooks()` from detected formatters. Present each
hook before writing. Use `generate_claude_hook_config()` for Claude JSON and
the supported Cursor hook schema for Cursor.

### P8: Verify and Report

Report:

- all created/modified files;
- confirmed configuration choices;
- exact compile/validation commands and outcomes;
- next-step suggestions;
- unresolved blockers.

Map each claim to its checklist item and evidence file.

## Round Placement

L0 chooses the interview item by checklist priority/dependencies. L1
dispatches one fresh L2 Task because operator questions are sequential.
Subsequent generation or verification may occupy later waves or rounds.

Limits remain 5 Tasks per wave and 7 waves per round. Escalation is
Task → Wave → Project → Human.
