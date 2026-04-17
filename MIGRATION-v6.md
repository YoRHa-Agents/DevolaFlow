# DevolaFlow v6.0 Migration Guide

## Breaking changes in v6.0.2

### Removed: `evaluate_gate_with_nines`

- **Old:** `from devolaflow.gate import evaluate_gate_with_nines`
- **New:** `from devolaflow.gate import evaluate_gate`
- **Reason:** NineS is a research/iteration tool, not a gate scorer. The combined function conflated two concerns; separating them reflects the actual architecture per v5.1 rationale.
- **Migration:** Replace the call. If you were using the NineS enrichment features, use `devolaflow.nines.get_research_advice()` (defined in `devolaflow.nines.advisor`) separately and fold results into your own reporting.

### Removed: `run_nines_advisor`

- **Old:** `from devolaflow.nines import run_nines_advisor` or `from devolaflow.nines.advisor import run_nines_advisor`
- **New:** Use the underlying NineS tooling directly, or `from devolaflow.nines import get_research_advice`.
- **Reason:** Advisor was tied to the deprecated `evaluate_gate_with_nines` path.
- **Migration:** Refactor callers to either run NineS as a standalone research step or use `get_research_advice()` from `devolaflow.nines.advisor` (re-exported at the `devolaflow.nines` package level).

#### Also removed (dead code after `run_nines_advisor` removal)

- `should_invoke_advisor` — was only used inside `run_nines_advisor` to decide whether to invoke the NineS CLI.
- Private helpers `_interpret_result`, `_extract_score`, `_extract_reasoning` and the `_SCORE_KEYS` / `_REASONING_KEYS` / `_APPROVE_STATUSES` / `_SCORE_THRESHOLD` constants in `devolaflow.nines.advisor`.

If you depended on `should_invoke_advisor`, branch directly on `config.enabled and verdict.advisor_recommended`.

## What did NOT change in v6.0

- `evaluate_gate()` — stable, recommended
- `findings_to_reinforcement`, `merge_reinforcement_into_dispatch`
- `apply_round_escalation`
- `select_context` — signature unchanged (v6.0.3 extends with optional `round_num` in Wave 3; default behavior preserved)
- All 4 adapters (Cursor, Codex, Claude, Copilot) — outputs byte-stable modulo version bump
