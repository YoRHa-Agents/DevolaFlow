---
last_updated: "2026-08-25"
---

# Evaluator Rosetta — SI-3 × Built-in Harness Cross-Walk

## Purpose

This reference is the canonical **6 × 9** mapping between the six W-3
evaluation dimensions and nine built-in harness signal bundles. It tells an
evaluation author which machine evidence is canonical (**C**), supporting
(**O**), or unrelated (**·**) for each dimension.

The only live evaluation authority is:

```bash
python -m devolaflow.harness evaluate \
  --ledger .local/telemetry/harness.jsonl \
  --repo . \
  --base HEAD~1 \
  --output .local/research/<cycle>_harness_evaluation.json
```

The command reads repository telemetry, collects bounded local signals, and
emits deterministic JSON. No external evaluator is a runtime dependency and
there is no manual fallback for missing machine evidence.

## When to Load

Load this reference when:

* authoring `.local/research/vX.Y.Z_evaluation.md`;
* explaining a dimension score or unavailable subcomponent;
* comparing a cycle with the active W-16 harness baseline;
* updating `src/devolaflow/harness/evaluator.py` signal composition; or
* validating `scripts/generate_evaluator_rosetta.py` output.

## 1. Binding Evaluation Contract

The built-in evaluator emits:

| Field | Contract |
|---|---|
| `scores` | Six ordered W-3 dimensions with score, weight, and subcomponents |
| `composite` | Weighted sum of the six dimension scores |
| `auto_fill_rate` | Available machine slots divided by all required slots |
| `verdict` | `READY`, `NOT_READY`, or `INSUFFICIENT` |
| `harness_summary` | Token, constraint-tier, round, change, and model telemetry |
| `suggestions` | Dimension-keyed unavailable or below-threshold findings |

Verdict mapping:

* `READY` → SI-3 `ACCEPT`; command exit `0`.
* `NOT_READY` → SI-3 `REJECT`; iterate or escalate; command exit `1`.
* `INSUFFICIENT` → release `BLOCKED`; resolve or escalate missing evidence;
  command exit `2`.

`INSUFFICIENT` is not a low score. It means at least one required machine
subcomponent is unavailable. An estimate, prose assertion, or unrelated test
result cannot replace it.

## 2. SI-3 Dimensions

| Dimension | Weight | Built-in score components |
|---|:---:|---|
| **Code quality** | 0.20 | code hygiene + coverage |
| **Architecture rationality** | 0.20 | layout invariant + constraint quantifiability |
| **Test adequacy** | 0.20 | test execution + coverage + W-17 test growth |
| **Maintainability** | 0.15 | formatting hygiene + docstring coverage |
| **Compatibility** | 0.10 | layout invariant + compatibility suite |
| **Performance impact** | 0.15 | token-budget compliance + p95 token headroom |

The weights and component composition mirror
`src/devolaflow/harness/evaluator.py::DIMENSION_WEIGHTS` and
`evaluate_harness`.

## 3. Nine Built-in Signal Bundles

| # | Bundle | Machine source | Included signal keys |
|---:|---|---|---|
| 1 | **Harness code hygiene** | bounded local Ruff probes | `ruff_lint`, `ruff_format` |
| 2 | **Harness test execution** | bounded local Pytest probe | `test_suite` |
| 3 | **Harness coverage** | coverage line parsed from the test probe | `coverage_pct` |
| 4 | **Harness layout invariant** | immutable layout witness suite | `layout_invariant` |
| 5 | **Harness compatibility** | version and compatibility suite | `compatibility_suite` |
| 6 | **Harness W-17 test growth** | bounded Git diff probe | `w17_new_tests` |
| 7 | **Harness docstring coverage** | in-process AST scan | `docstring_coverage_pct` |
| 8 | **Harness constraint quantifiability** | aggregated ledger constraint tiers | `constraints.quantifiable_ratio` |
| 9 | **Harness token budget** | aggregated measured token telemetry | `tokens.budget_compliance_ratio`, `tokens.p95_budget_utilization` |

Bundles group signals by evaluation concern; they do not change the evaluator's
underlying JSON keys. Evaluation reports cite exact key paths and values.

## 4. The 6 × 9 Rosetta

**Cell legend**

* **C** — canonical built-in signal for the row's quantitative score.
* **O** — supporting signal that overlaps but does not own the score.
* **·** — orthogonal; do not cite as evidence for that row.

| SI-3 dim ↓ | Harness code hygiene | Harness test execution | Harness coverage | Harness layout invariant | Harness compatibility | Harness W-17 test growth | Harness docstring coverage | Harness constraint quantifiability | Harness token budget |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Code quality (0.20)** | **C** | O | **C** | · | · | · | O | O | · |
| **Architecture rationality (0.20)** | O | · | · | **C** | · | · | · | **C** | O |
| **Test adequacy (0.20)** | · | **C** | **C** | · | O | **C** | · | · | · |
| **Maintainability (0.15)** | **C** | · | · | · | · | · | **C** | O | · |
| **Compatibility (0.10)** | · | · | · | **C** | **C** | · | · | · | · |
| **Performance impact (0.15)** | · | O | · | · | · | · | · | O | **C** |

### 4.1 C-cell rationale

**Code quality.** `ruff_lint` and `ruff_format` directly measure source
hygiene; `coverage_pct` contributes the evaluator's coverage score. Cite the
subcomponent envelopes verbatim, including `available`, `value`, and `error`
when present.

**Architecture rationality.** `layout_invariant` protects the frozen dispatch
contract. `harness_summary.constraints.quantifiable_ratio` measures how much
injected governance is machine-verifiable. These are the two exact components
used by the dimension.

**Test adequacy.** `test_suite`, `coverage_pct`, and `w17_new_tests` jointly
cover execution success, exercised code, and test-growth discipline. All three
are required; one unavailable component makes the overall verdict
`INSUFFICIENT`.

**Maintainability.** Formatting hygiene is the `ruff_format` half of the code
hygiene bundle. `docstring_coverage_pct` is the AST-derived documentation
signal. The evaluator averages those two components.

**Compatibility.** `layout_invariant` covers byte-stable dispatch witnesses;
`compatibility_suite` covers version and compatibility contracts. Both must be
available.

**Performance impact.** The harness ledger records measured injected tokens
and declared budgets for every dispatch. The evaluator scores
`budget_compliance_ratio` and p95 headroom derived from
`p95_budget_utilization`.

### 4.2 O-cell discipline

An O-cell can explain context but cannot replace a C-cell:

* Test execution supports code-quality confidence but does not replace hygiene
  or coverage.
* Code hygiene can support architectural or maintainability discussion, but it
  does not replace layout or quantifiability evidence.
* Compatibility execution supports test confidence, while test adequacy still
  owns its three C-cells.
* Token and constraint telemetry can reveal architectural overhead, but only
  the exact configured dimension components determine the machine score.

## 5. Evaluation Authoring Workflow

1. Run the built-in evaluator with the release threshold:

   ```bash
   python -m devolaflow.harness evaluate \
     --ledger .local/telemetry/harness.jsonl \
     --repo . \
     --base <cycle-base-ref> \
     --threshold <8.5-or-9.0> \
     --output .local/research/<cycle>_harness_evaluation.json
   ```

2. Preserve the command exit code and JSON bytes as evidence.
3. For each dimension, copy `score`, `weight`, and
   `metadata.subcomponents` verbatim.
4. Use the C-cells in §4 to explain why those values belong to the dimension.
5. Copy `composite`, `auto_fill_rate`, and `verdict` verbatim.
6. Compare `harness_summary.tokens` and `harness_summary.constraints` with the
   active W-16 baseline.
7. Close or escalate every `suggestions` entry. Do not rewrite
   `INSUFFICIENT` as a passing judgment.

For a MAJOR release use threshold `9.0`; for a MINOR or PATCH release use
`8.5`, unless the operator sets a stricter bar.

## 6. Signal Failure Handling

| Condition | Required disposition |
|---|---|
| A local probe fails | Preserve `available: false` and its error; verdict remains `INSUFFICIENT` |
| Ledger missing or malformed | Command exits `2`; repair or recover the append-only telemetry |
| Composite below threshold | `NOT_READY`; iterate from W-1 or escalate |
| Baseline regression exceeds W-4 tolerance | Release blocker even if current composite is otherwise ready |
| Report prose conflicts with JSON | JSON is authoritative; correct the prose |

There is no external-tool or manual bypass. Direct commands may diagnose why a
signal failed, but the built-in evaluator must be rerun successfully before
release.

### 6.1 Model-Probe Model Table (operator note)

`python -m devolaflow.harness probe` accepts an explicit `--provider` +
`--model` pair, or — with both omitted — sweeps the operator-maintained
`meta.probe_models` table in `workflow-system/agent/context_profiles.yaml`
(one profile artifact per configured provider/model pair). Refresh stale
model IDs by editing that table; the per-provider fallbacks hardcoded in
`src/devolaflow/llm_client.py` are byte-compatibility defaults and are NOT
the place to track current model releases. The table ships undeclared:
with the key absent the CLI keeps its explicit single-model contract.

## 7. Historical Provenance

The 6 × 9 format originated as a cross-evaluator reading aid in pre-v16 cycle
artifacts. Those documents remain historical evidence only. Their metrics,
commands, and fallback rules are not live dependencies and must not be copied
into a current evaluation.

The current Rosetta keeps the stable six-row shape while replacing every
column with a bundle sourced from `devolaflow.harness`. This preserves the
machine generator and test identities without preserving retired runtime
coupling.

## 8. Maintenance Contract

When `src/devolaflow/harness/evaluator.py` changes:

1. update the bundle catalog in §3;
2. update the §4 C/O/· matrix;
3. update `scripts/generate_evaluator_rosetta.py::COLUMNS` and `CELLS`;
4. update existing assertions in `tests/test_generate_evaluator_rosetta.py`;
5. run the JSON and markdown generators; and
6. run focused reference, ghost, line-budget, Ruff, and format checks.

Do not add a tenth column for a new raw key when it belongs naturally inside an
existing bundle. Add a column only for an orthogonal evaluation concern.

## 9. Cross-References

* `src/devolaflow/harness/evaluator.py` — six-dimension scoring and verdicts.
* `src/devolaflow/harness/aggregator.py` — strict telemetry aggregation.
* `src/devolaflow/harness/probe.py` — bounded model-compliance probes.
* `scripts/generate_si3_evaluation.py` — current SI-3 report skeleton.
* `scripts/generate_evaluator_rosetta.py` — machine renderer for §4.
* `tests/harness/test_evaluator.py` — deterministic score and exit-code
  contracts.
* `tests/test_generate_evaluator_rosetta.py` — 6 × 9 shape and renderer tests.
* `AGENTS.md` §W-2 — built-in evaluator and no-fallback rule.
* `AGENTS.md` §W-3 — six dimensions and release thresholds.
* `AGENTS.md` §W-4 — harness regression guard.
* `AGENTS.md` §W-16 — baseline settlement.
