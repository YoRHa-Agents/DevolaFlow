## Summary

<!-- 1-3 bullet points describing what this PR does and why -->

-

## Changes

<!-- List key files/areas changed -->

-

## W-9 Pre-Commit Gates (all 7 must pass — or run `make precommit-full`)

- [ ] `make test-core`
- [ ] `ruff check src/ tests/`
- [ ] `ruff format --check src/ tests/`
- [ ] `make test-version`
- [ ] `make test-harness`
- [ ] `make check-cursor-skill`
- [ ] `make iteration-delta-gate`

## Rule Checklist (S/A/C/W/ST — compiled corpus: `.cursor/rules/repo-governance.mdc` / `AGENTS.md`; sources: `.rules/*.mdc`)

- [ ] **S (Soul)**: no ghost features (S-4); coverage >= 80% (S-3); no absolute paths in agent-facing files (S-2); no silent failures (S-5); feature branch + PR, never push protected branches (S-6)
- [ ] **A (Architecture)**: dispatch layout invariant intact if `schemas/` touched (A-2) — `python -m pytest tests/test_layout_invariant_multi_baseline.py -v`
- [ ] **C (Conventions)**: CHANGELOG.md updated if user-visible (C-1); version bumped via `scripts/bump_version.py` + `make test-version` (C-6); reference links valid (C-7)
- [ ] **W (Workflow)**: ghost-audit refreshed BEFORE authoring the CHANGELOG entry (W-18); built-in harness contracts pass for selector/profiles/schemas/SKILL.md/gate changes; `build-skill` + adapter budgets pass if SKILL.md/CLAUDE.md/workflow-skill.yaml changed (W-5)
- [ ] **ST (Style)**: EN/ZH bilingual sync (ST-3) + demo page checklist (ST-5) if `workflow-system/human/` touched; `make sync-human-docs` if version bumped (ST-4)
- [ ] Conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`)

## Release Impact

<!-- If this PR is part of a release, note which version and any migration steps -->

N/A
