# Change — v9.2.1-self-update-validation

Authored via `/devola:propose`. Lifecycle:

1. `/devola:apply` — flip STATUS.yaml `state` to `IN_PROGRESS`.
2. (L3 task agents implement; populate `owned_files.txt` first).
3. `/devola:verify` — run pytest on owned files; flip to `VERIFYING` on PASS.
4. `/devola:archive` — gate on `state == VERIFYING` AND `gate_score >= 8.5`;
   moves the folder to `.local/.agent/archive/<YYYY-MM-DD>-<id>/`.

See `workflow-system/agent/SKILL.md` §"When to engage `change-driven`" and
Rule **A-6** in `.rules/architecture.mdc` for the activation contract.
