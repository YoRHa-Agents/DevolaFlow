# v7-ADR-002 — Tool-Output Truncation Primitive in `compressor.py`

- **Status:** Accepted
- **Date:** 2026-04-17
- **Authors:** Design team L3 task agent for V7.0.0-S02-T01
- **Ships in:** v7.0.1 (see `.local/research/v7.0.0_version_roadmap.md`)
- **Research source:** `.local/research/v7.0.0_context_compression_research.md` §§B.3, F row 6, G row 6, J.2
- **Decides:** Open question K.4 (tool-result clearing default)

## 1. Context

Anthropic's cookbook (`[ref-6]`) describes tool-result clearing as the
"lightest-touch" lever in the context-engineering toolkit: the
`tool_use` record is preserved (so the model knows the call happened)
while the bulky `tool_result` payload is replaced with a short
placeholder once it falls below a recency threshold. OpenAI's
`clear_tool_uses_20250919` ships the same primitive server-side with a
default `keep=3`.

DevolaFlow's `src/devolaflow/compressor.py` today operates only on
natural-language prose (preserve-list / drop-list regex patterns). It
has **zero** coverage of structured tool-result payloads. When an L3
Task Agent attaches large `Read` / `Grep` / `Shell` outputs to a
StatusReport for the parent Wave Agent to consume, those payloads pass
through the lean-report serialiser unmodified. In convergence rounds,
prior rounds' tool outputs accumulate in the dispatched predecessor
context, increasing the dispatch size without proportional information
gain.

Research §F row 6 lists tool-output truncation as a **primary gap** and
estimates an EvoBench composite delta of **+5 to +10** on scenarios
with heavy tool output. §G row 6 places the implementation cost inside
`src/devolaflow/compressor.py` with a recommended signature
`truncate_tool_output(payload, keep_head=N, keep_tail=M,
replace_middle="…")`.

## 2. Decision

We add a tool-output truncation primitive to `src/devolaflow/compressor.py`
and a typed block in `schemas/lean-report.yaml` that describes the
truncation state.

### 2.1 Public API

```python
def truncate_tool_output(
    payload: str,
    keep_head_chars: int = 500,
    keep_tail_chars: int = 500,
    replace_middle: str = "…[truncated {dropped} chars / {dropped_tokens} tokens]…",
) -> dict:
    """Truncate a tool-output payload, preserving head and tail.

    Returns a dict:
      - truncated_text: str
      - original_chars: int
      - original_tokens: int
      - kept_chars: int
      - kept_tokens: int
      - dropped_chars: int
      - dropped_tokens: int
      - was_truncated: bool
    """

def clear_old_tool_uses(
    tool_uses: list[dict],
    keep: int = 3,
    exclude_tool_names: list[str] | None = None,
) -> list[dict]:
    """Replace tool_result payloads for all but the most recent `keep` tool uses.

    Each tool_use is a dict with keys {id, name, args, result}. The
    tool_use record itself is preserved; only its `result` field is
    replaced with a short placeholder "[cleared — call #N]". Tool uses
    whose `name` appears in `exclude_tool_names` are never cleared.
    Ordering of the list is preserved.
    """
```

### 2.2 Defaults (committed)

- `keep=3` (Anthropic's default; open question K.4 resolved).
- `keep_head_chars=500`, `keep_tail_chars=500` — totals 1000 chars
  (~250 tokens) of surviving payload per tool output, which is
  empirically sufficient to preserve error text and file paths in our
  EvoBench compression probes (H.1).
- `exclude_tool_names = ["Read"]` default — `Read` output is
  frequently cited verbatim in code-review waves and must be preserved.
  Operators can override per-profile.

### 2.3 Schema addition

Add to `schemas/lean-report.yaml` a new optional top-level block:

```yaml
tool_results:
  keep: int          # how many most-recent tool results are preserved in full
  cleared_at_round: int | null
  cleared_tool_ids: list[str]  # ids whose result payload was replaced
  head_chars: int
  tail_chars: int
```

The block is **additive** — missing block is interpreted as
`{keep: null, cleared_at_round: null, cleared_tool_ids: []}` (disabled,
legacy behaviour preserved).

### 2.4 Opt-in via context profiles

`workflow-system/agent/context_profiles.yaml` gains a new per-profile
knob `tool_output_truncation:`:

```yaml
tool_output_truncation:
  enabled: true            # default false
  keep: 3
  keep_head_chars: 500
  keep_tail_chars: 500
  exclude_tool_names: ["Read"]
  trigger_round: 2         # only clear starting from round 2
```

Default for every profile at v7.0.1 cut: **disabled**. Explicit opt-in
per profile in v7.0.2 or later after H.1 retention data confirms safety.

## 3. Consequences

### Positive

- Convergence-round dispatches (round 2+) shrink meaningfully when
  prior rounds produced heavy tool output — estimated EvoBench +5 to
  +10 composite on affected scenarios.
- Primitives compose: `clear_old_tool_uses` is independent of
  `truncate_tool_output`; callers can apply one, the other, or both.
- Schema addition is backwards-compatible with existing lean reports.
- Aligns DevolaFlow's prompt-side stack with Anthropic / OpenAI server-
  side defaults, reducing cognitive cost for agents who have been
  trained on those defaults.

### Negative

- Additional surface area in `compressor.py` (~120 LOC of production
  code + ~80 LOC of tests per J.2).
- Agents reading a truncated tool result must understand the
  placeholder format (`[cleared — call #N]`); SKILL.md gets a
  short explainer.
- Per-profile opt-in means the feature's real benefit is realised only
  once profiles actually opt in (likely in v7.0.2).

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Critical information sits in the truncated middle of a tool output | P2 | Head+tail default is 500/500 chars — captures typical error prologue and epilogue. For very large outputs, operators opt out per-profile (`trigger_round: 999`). |
| Tool output contains structured YAML/JSON and truncation breaks parseability | P2 | Truncation happens on character boundaries *after* the payload is embedded as a string in the YAML report; parsing happens at L3 side of the tool call, not on the truncated mirror. The mirror is intended for human-scan and for the *model's* re-ingestion, not for programmatic JSON parsing. |
| Clearing tool results for `Read` would destroy citation context | P1 | `Read` is in the default `exclude_tool_names`. Any profile removing it must document why. |
| Regression: over-aggressive clearing causes hallucinated file paths | P1 | H.4 (persistence probe — v7-ADR-004) catches this; retention ≥ 95 % on preserve-list facts is a release blocker. |

## 4. Alternatives Considered

### 4a. **Summarise tool outputs via LLM**

Route each tool output through a small summariser LLM call instead of
truncating deterministically. **Rejected** because (1) summarisation
introduces hallucination risk per CO-2 (verbatim extraction is the
DevolaFlow baseline), (2) the cost per convergence round doubles, (3)
Anthropic's own cookbook settled on deterministic clearing for exactly
this reason.

### 4b. **Semantic-aware truncation (sentence boundary)**

Truncate on sentence boundaries instead of character boundaries.
**Rejected** because tool outputs are often code, tracebacks, or
non-prose text where sentence detection is unreliable. Character-based
head/tail is predictable and auditable.

### 4c. **Keep default = 5**

Use a more conservative `keep=5` instead of `keep=3`. **Rejected**:
empirical data from Anthropic's cookbook (`[ref-6]`) shows `keep=3`
suffices on real workloads. We keep `keep=3` as the default and let
operators raise it per-profile when H.1 signals a retention regression.

### 4d. **Clear from round 1 onward**

Clear tool outputs immediately, even in round 1. **Rejected** — round 1
has no prior-round payloads to clear (definitionally), and retaining
all round-1 outputs simplifies baseline reproducibility for EvoBench.

## 5. Reversibility

**Cost to undo:** Low.

- Remove `truncate_tool_output` and `clear_old_tool_uses` from
  `compressor.py`.
- Remove `tool_results` block from `schemas/lean-report.yaml`.
- Remove the `tool_output_truncation` knob from `context_profiles.yaml`.
- Remove unit tests in `tests/test_compressor.py`.

Because the feature is opt-in, no profile is affected if the module
disappears. Rollback window: ≤ 1 patch version.

## 6. Test Plan

Tests that would falsify this decision:

1. **`tests/test_compressor.py::test_truncate_tool_output_head_tail`** —
   verify head_chars and tail_chars of the truncated string are
   identical to the original's head and tail.
2. **`tests/test_compressor.py::test_truncate_tool_output_small_input`** —
   input smaller than `keep_head_chars + keep_tail_chars` is returned
   unchanged with `was_truncated=False`.
3. **`tests/test_compressor.py::test_clear_old_tool_uses_preserves_most_recent`** —
   4 tool uses in, `keep=3` → last 3 unchanged, first has `result`
   replaced.
4. **`tests/test_compressor.py::test_clear_old_tool_uses_respects_exclude`** —
   `exclude_tool_names=["Read"]`; all `Read` results preserved even
   when older than `keep=3`.
5. **`tests/test_compressor.py::test_clear_old_tool_uses_keeps_tool_use_record`** —
   verify `id`, `name`, `args` are intact on cleared entries; only
   `result` is replaced.
6. **`tests/test_benchmarks.py::test_truncation_retention`** (H.1
   scenario) — compression_retention_medium.json probe with heavy
   tool output; retention ≥ 95 % on preserve-list facts after
   truncation.
7. **`tests/test_benchmarks.py::test_truncation_token_reduction`** —
   convergence round 2 with tool-output truncation enabled is ≥ 20 %
   smaller (tokens) than round 2 without.

A failure of test #6 blocks the release outright.

## 7. Cross-References

- Depends on: **v7-ADR-001** (the `tool_results` block is appended at
  position ≥ 13 in `lean-report.yaml`, honouring the layout
  invariant).
- Depended on by: **v7-ADR-004** (persistence probe exercises the
  truncation path at stage boundaries).
- Related rules: `.cursor/rules/change-process-rules.mdc` (CP-4 gate
  tests), `.cursor/rules/context-optimization-rules.mdc` (CO-5
  benchmark verification).
- Research §: B.3, F row 6, G row 6, H.1, J.2, K.4.
