---
id: "agent/references/compression-pipeline"
version: "8.5.1"
purpose: >
  Canonical reference for the v9.0.0 PV-06 CompressionStage protocol +
  CompressionPipeline orchestrator that unify the six v8.0.0+ text-side
  compression transforms (`truncate_tool_output`,
  `summarise_predecessor` extractive + Stage A abstractive + Stage B
  LLM-assisted, `directed_compact`, `apply_local_recipe`) behind one
  `transform(payload, context) -> payload` contract. Pairs with
  `schemas/compression-pipeline.yaml` (declaration schema) and
  `.local/research/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md`
  (the governance ADR).
triggers:
  - "designing a new compression transform"
  - "composing multiple transforms into an ordered pipeline"
  - "diagnosing a byte-identity regression in the 6 canonical transforms"
  - "auditing R5 strict byte-identical pass-through invariants"
  - "choosing between NEST vs APPEND for a new compression primitive"
  - "wiring a pipeline into an L0/L1/L2/L3 dispatcher call site"
tier: 2
token_estimate: 6000
dependencies:
  - "agent/SKILL.md"
  - "agent/references/env-flags.md"
  - "agent/references/decomposition-gate.md"
  - "agent/references/shell-proxy.md"
last_updated: "2026-04-24"
---

# Compression Pipeline — CompressionStage Protocol + 6-Transform Unification

> Tier-2 reference — load when: designing a new compression transform, composing
> multiple transforms into an ordered pipeline, diagnosing a byte-identity
> regression in the `truncate_tool_output` / `summarise_predecessor` /
> `directed_compact` / `apply_local_recipe` / LLM Stage B surface, or auditing
> the v8.0.0+ compression primitives against the **R5 strict byte-identical**
> invariant.

## 1. Purpose

The `CompressionPipeline` orchestrator + `CompressionStage` protocol unify the
six compression transforms that ship across the v8.x cycle behind one
`transform(payload, context) -> payload` contract. Three design goals:

1. **One protocol, six transforms.** Callers stop hand-wiring argument lists
   per-transform; they thread per-stage kwargs through the pipeline `context`
   dict and read the aggregate verdict off `PipelineRunResult`.
2. **Byte-identical bypass is declarative.** When every stage's `bypass`
   predicate returns `True` (or the pipeline is empty), the pipeline is an
   identity reducer. This is the **R5 strict** invariant pinned by
   `tests/test_compression_pipeline.py::test_*_byte_identical`.
3. **P6-safe cache behaviour.** The pipeline adds **zero** top-level dispatch
   keys, zero new env-flags, and zero new nested dispatch fields. The
   16-key `canonical_order` + schema version 5 stay byte-identical (verified
   by `tests/test_layout_invariant_multi_baseline.py` against all 6 historical
   baselines).

Design source: `.local/research/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md`
(v9.0.0 PV-06 / v8.5.1 cycle entry).

---

## 2. The `CompressionStage` protocol

A stage is any object that exposes the shape

```python
class _CompressionStageProtocol(Protocol):
    name: str
    def transform(self, payload: Any, context: Mapping[str, Any]) -> Any: ...
```

The shipped `CompressionStage` dataclass is the canonical implementation. It
adds three orthogonal decorations on top of the bare protocol:

| Field | Role | Default |
|---|---|---|
| `name` | Stable id used in `StageResult.name` + error messages | required |
| `transform` | `Callable[[payload, context], payload]` | required |
| `bypass` | `Callable[[payload, context], bool]` — `True` ⇒ skip the stage | `BYPASS_NEVER` |
| `bypass_conditions` | Free-form labels for status-report attribution (pure doc) | `()` |
| `telemetry_key` | Attribution key surfaced in `StageResult.telemetry` | stage's `name` |

Construction is loud per **S-5** — empty names, non-callable transforms /
bypass predicates all raise at `__post_init__` time.

### 2.1 `make_stage` convenience constructor

Production code uses `make_stage(name, transform, *, bypass=None,
bypass_conditions=None, telemetry_key="")` because it accepts `None` for
`bypass` / `bypass_conditions` (the dataclass treats `None` as a `TypeError`
since the fields are typed). The helper normalises the arguments to the
pipeline-safe dataclass shape.

### 2.2 Bypass predicate discipline

Bypass predicates MUST return a `bool`. The pipeline's `should_bypass` wrapper
is **defensively loud** per S-5:

* Predicate raises → the pipeline logs a `WARNING` with the stage name + the
  exception, then treats the stage as bypassed.
* Predicate returns a non-`bool` → same path: `WARNING` + defensive bypass.

This keeps a buggy predicate from silently mutating the running payload; the
operator sees the broken stage in the log without grep-spelunking.

### 2.3 The two canonical bypass helpers

```python
BYPASS_NEVER(_payload, _context) -> False   # always run the stage
BYPASS_ALWAYS(_payload, _context) -> True   # always skip (test-only)
```

`BYPASS_NEVER` is the default; production stages override it with a
per-primitive predicate (e.g. `apply_local_recipe`'s stage reads the PV-02
env-flag via `is_command_mapping_active(ctx.get("env"))`).
`BYPASS_ALWAYS` is reserved for the byte-identity invariant tests —
production callers SHOULD NOT use it directly (use a real runtime probe
instead).

---

## 3. The `CompressionPipeline` orchestrator

A frozen dataclass that wraps a tuple of stages + a pipeline-level name. Four
invariants (pinned by `tests/test_compression_pipeline.py`):

1. **Empty pipeline** returns input unchanged (`test_empty_pipeline_is_byte_identical`).
2. **All stages bypassed** returns input unchanged (`test_all_stages_bypassed_is_byte_identical`).
3. **Single identity stage** (`transform=lambda p, c: p`) is NOT reported as
   `applied=True` — telemetry hygiene requires a real mutation to count as
   applied.
4. **Stages run in declaration order** — the pipeline is a deterministic
   sequential reducer, not a DAG. Stages receive only the running payload +
   the shared `context` mapping; they do **not** see each other's inputs.

### 3.1 `run(payload, context=None, *, strict=True)`

Signature + return value:

```python
result: PipelineRunResult = pipeline.run(payload, context={"cmd": "pytest"})
# result.payload         — the post-pipeline value
# result.stage_results   — tuple[StageResult, ...] in declaration order
# result.any_applied     — True iff ≥ 1 stage mutated the payload
# result.applied_stages  — tuple[str, ...] — stages that ran AND mutated
# result.bypassed_stages — tuple[str, ...] — stages whose bypass fired
# result.failed_stages   — tuple[str, ...] — lenient-mode failures (empty under strict=True)
```

### 3.2 Strict vs lenient mode (S-5 discipline)

| Mode | Failure policy |
|---|---|
| `strict=True` (default) | First stage that raises propagates a `CompressionStageError` with the stage name + original exception in `__cause__`. The pipeline aborts; downstream stages do NOT run. |
| `strict=False` | Per-stage failures log a `WARNING`, the failing stage's input is forwarded to the next stage unchanged, and the failed stage's name is recorded in `PipelineRunResult.failed_stages`. |

The default is `strict=True` because the pipeline is deterministic and
downstream consumers key off the final payload — a silent mid-pipeline
failure would hide the breaking transform. Callers that want best-effort
(e.g. `apply_local_recipe` with a malformed recipe) opt in explicitly.

### 3.3 Pipeline construction validation

Three construction-time guards (all loud per S-5):

* **Duplicate stage names** → `ValueError` (telemetry attribution requires
  unique ids).
* **Stage without the protocol surface** (missing `name` or `transform`) →
  `TypeError`.
* **List passed where tuple expected** → coerced silently (frozen dataclass
  uses `object.__setattr__` to normalise without side-effects).

### 3.4 `with_extra_stage(stage)` — immutable composition

Callers that build a base pipeline once and customise per-call use
`with_extra_stage` to get a new pipeline with the extra stage appended.
The original pipeline is untouched; this preserves safe shared-state
behaviour when multiple dispatchers share a module-level pipeline constant.

---

## 4. The six v8.5.1 canonical transforms wrapped behind the protocol

Every transform listed here is accessible via its module's
`compression_pipeline_stage()` factory (or `compression_pipeline_stages()`
in `compressor.py` which returns a list of three stages). Each factory
imports `devolaflow.compression_pipeline` lazily so the host module does
not gain a hard dependency on the pipeline runtime at import time.

| # | Transform | Module | Factory | Bypass conditions |
|---|---|---|---|---|
| 1 | `truncate_tool_output` | `devolaflow.compressor` | `compression_pipeline_stages()[0]` | always runs (caller gates via `context["truncate_enabled"]`) |
| 2 | `summarise_predecessor` (extractive + Stage A) | `devolaflow.compressor` | `compression_pipeline_stages()[1]` | always runs (caller passes `mode="extractive"` / `mode="abstractive"`) |
| 3 | `directed_compact` | `devolaflow.compressor` | `compression_pipeline_stages()[2]` | always runs (empty focus_keywords = no-op) |
| 4 | `summarise_predecessor` (Stage B — LLM-assisted) | `devolaflow.llm_client` | `compression_pipeline_stage()` | bypass when `context["llm_client"]` is `None` |
| 5 | `apply_local_recipe` | `devolaflow.shell_proxy.commands` | `compression_pipeline_stage()` | bypass when `DEVOLAFLOW_RTK_PROXY` env-flag unset |

### 4.1 Why three stages in `compressor.compression_pipeline_stages()`?

The `compressor` module hosts three historical transforms (`truncate_tool_output`,
`summarise_predecessor` — whose `mode` dispatches between extractive and
abstractive Stage A — and `directed_compact`). Each gets its own stage so
pipelines can compose them independently. Callers that want only
extractive summarisation instantiate a pipeline with only stage 2.

### 4.2 Stage B's bypass predicate (the non-trivial one)

`llm_client.compression_pipeline_stage()` returns a stage whose bypass is

```python
def _stage_llm_complete_bypass(_payload, ctx):
    return ctx.get("llm_client") is None
```

This preserves the v8.0.0-P-10 byte-identical behaviour for callers that
have not opted into LLM assistance: Stage B never runs without an explicit
`llm_client` in the context dict. There is **no** env-flag governing Stage
B — activation is purely context-driven, which is why it does not appear
in `references/env-flags.md`.

### 4.3 `apply_local_recipe`'s env-flag gate (the PV-02 reuse)

`shell_proxy.commands.compression_pipeline_stage()` returns a stage whose
bypass reuses the existing `DEVOLAFLOW_RTK_PROXY` env-flag (PV-02) rather
than minting a new one. This is the canonical **W-20 reuse-first**
example: the activation surface is identical to PV-02 (the RTK-pattern
command-output mapping layers ON TOP of `rtk rewrite`), so a fresh
checkout / CI runner with the flag unset gets a byte-identical pass-through
with zero IO (no file read, no `shutil.which` lookup).

---

## 5. Multi-pass filter chain (T3 #5)

v8.5.1 PV-06 adds `compose: list[str]` to `schemas/command-mapping.yaml`
(schema version 1 → 2). This promotes a `FilterRule` from a single-pass
substitution to a multi-pass chain:

```yaml
schema_version: 2
pre_filters:
  - pattern: "^\\s*DeprecationWarning:.*$"
    replacement: ""
    compose:
      - "\\n{3,}"          # run this sibling rule AFTER the parent's sub
```

### 5.1 The semantics

* The parent rule's substitution runs first.
* Each `compose` entry (referenced by the sibling rule's `raw_pattern` id)
  runs AFTER the parent, in declaration order, against the parent's
  intermediate output.
* Composed children ALSO run in their own slot in the outer `rules`
  iteration — so the multi-pass chain is **purely additive**: a recipe with
  no `compose` entries is byte-identical to the v1 single-pass behaviour
  (pinned by `tests/test_shell_proxy_commands.py`).

### 5.2 Load-time validation (S-5 loud)

`_validate_compose_references` walks both `pre_filters` and `post_filters`
after the `FilterRule` tuple is constructed, and raises a
`CommandMappingError` when a `compose` entry references a non-existent
sibling. The message carries the recipe id + the missing child id so the
operator can locate the typo without grep-spelunking.

### 5.3 Back-compat contract

A v1 recipe (schema_version: 1) is byte-identical to a v2 recipe whose
`compose` fields are all omitted. The loader normalises both into the same
`FilterRule` tuple. Operators MAY keep their recipes at v1 indefinitely.

---

## 6. R5 strict invariants (the canonical test pins)

| Invariant | Pin |
|---|---|
| Empty pipeline = identity | `test_empty_pipeline_is_byte_identical` |
| All-bypassed = identity | `test_all_stages_bypassed_is_byte_identical` |
| Identity stage not "applied" | `test_identity_stage_is_byte_identical` |
| Declaration order is run order | `test_stages_run_in_declaration_order` |
| Stage validation is loud | `test_stage_validation_rejects_bad_construction` |
| Bypass predicate defensively loud | `test_should_bypass_defensive_paths` |
| Strict mode raises `CompressionStageError` | `test_strict_raises_compression_stage_error` |
| Lenient mode logs + continues | `test_lenient_mode_logs_and_continues` |
| Every shipped transform wraps the protocol | `test_all_stages_implement_protocol` |

Plus the per-primitive `_disabled.yaml` EvoBench scenarios (composite ≥ 90
floor) that pin the byte-identical-when-opted-out invariant for the 5
v8.0.0 gate primitives flipped default-ON in v8.5.1:

* `benchmarks/devolaflow_context/scenarios/token_budget_disabled.yaml`
* `benchmarks/devolaflow_context/scenarios/verification_ladder_disabled.yaml`
* `benchmarks/devolaflow_context/scenarios/ratchet_disabled.yaml`
* `benchmarks/devolaflow_context/scenarios/complexity_detector_disabled.yaml`
* `benchmarks/devolaflow_context/scenarios/ac_generator_disabled.yaml`

---

## 7. Composition recipes (three canonical compositions)

### 7.1 Predecessor summariser (extractive only)

```python
from devolaflow.compression_pipeline import CompressionPipeline
from devolaflow.compressor import compression_pipeline_stages

pipeline = CompressionPipeline(
    stages=(compression_pipeline_stages()[1],),  # summarise_predecessor only
    name="predecessor_extractive",
)
result = pipeline.run(
    artifact_path,
    context={"max_tokens": 1200, "mode": "extractive"},
)
```

### 7.2 Predecessor summariser (extractive + Stage B LLM)

```python
from devolaflow.compression_pipeline import CompressionPipeline
from devolaflow.compressor import compression_pipeline_stages
from devolaflow.llm_client import compression_pipeline_stage as stage_b
from devolaflow.llm_client import LLMClient

pipeline = CompressionPipeline(
    stages=(compression_pipeline_stages()[1], stage_b()),
    name="predecessor_with_llm",
)
result = pipeline.run(
    artifact_path,
    context={"max_tokens": 1200, "mode": "abstractive", "llm_client": LLMClient(...)},
)
```

Stage B bypasses when `llm_client` is missing, so the same pipeline is
safe to use in callers that pass `None` for the client (byte-identical to
stage 2 alone).

### 7.3 Command-mapping + directed compact + truncate

```python
from devolaflow.compression_pipeline import CompressionPipeline, make_stage
from devolaflow.compressor import compression_pipeline_stages
from devolaflow.shell_proxy.commands import (
    apply_local_recipe,
    is_command_mapping_active,
    compression_pipeline_stage as recipe_stage,
)

pipeline = CompressionPipeline(
    stages=(
        recipe_stage(),                           # gated by DEVOLAFLOW_RTK_PROXY
        compression_pipeline_stages()[2],         # directed_compact
        compression_pipeline_stages()[0],         # truncate_tool_output
    ),
    name="command_output_compression",
)
result = pipeline.run(
    tool_output,
    context={
        "cmd": "pytest",
        "focus_keywords": ["FAIL", "ERROR", "PASSED"],
        "head_chars": 500,
        "tail_chars": 500,
    },
)
```

When `DEVOLAFLOW_RTK_PROXY` is unset, the recipe stage bypasses and the
pipeline effectively becomes `directed_compact → truncate` — zero IO spent
on the bypassed stage, zero regression risk from the PV-02 surface.

---

## 8. Adoption guidance

### 8.1 When to use the pipeline vs the raw transform

* **Single transform, one call-site** → call the transform directly. The
  pipeline is an abstraction with a slight `PipelineRunResult` overhead.
* **≥ 2 transforms composed, or telemetry attribution matters** → use the
  pipeline. The `applied_stages` / `bypassed_stages` / `failed_stages`
  aggregation is what makes status reports greppable.
* **Call-site needs an opt-in gate** → wrap the transform in a stage with
  a runtime-probe bypass (e.g. `recipe_stage()` above). This centralises
  the activation check in one place instead of letting every caller
  re-implement the env-flag read.

### 8.2 Telemetry emission (status report integration)

Each `StageResult` carries a `telemetry` mapping of stage-defined metrics.
Consumers that render StatusReports convert the aggregate into verbatim
key_facts per CO-2:

```
applied_stages: [summarise_predecessor, directed_compact]
bypassed_stages: [apply_local_recipe]   # DEVOLAFLOW_RTK_PROXY unset
failed_stages: []
```

No paraphrasing, no summarisation — the stage names, applied / bypassed /
failed verdicts, and the stage-defined telemetry counters go verbatim
into the report.

### 8.3 Error propagation

Strict-mode failures raise `CompressionStageError`. The message format is

```
compression stage 'stage_name' raised ExceptionClass: error message (pipeline='pipeline_name')
```

The original exception is preserved via `__cause__` so tracebacks stay
useful. Callers that want to surface the failure upstream (L3 → L2) should
catch `CompressionStageError` and convert it to a StatusReport exception
per P4 bounded retry — the pipeline itself does NOT classify the failure.

---

## 9. Cross-references

* `.local/research/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md` —
  cycle entry with full rationale + alternatives considered.
* `src/devolaflow/compression_pipeline.py` — the canonical implementation.
* `schemas/compression-pipeline.yaml` — the schema mirror of the Python API.
* `tests/test_compression_pipeline.py` — R5 strict invariant suite.
* `references/env-flags.md` §2.6..§2.10 — the 5 v8.0.0 gate primitives
  flipped default-ON by the same PV.
* `references/shell-proxy.md` §11 — the SSOT registry list that includes
  the `CommandMapping` recipe type (now extended with the `compose` field).
* Governing rules: S-5 (no silent failures), A-2.3 (nest-vs-append — the
  pipeline nests under existing dispatch blocks), W-17 (+30 test cap — the
  pipeline suite stays well under), W-20 (env-flag reuse — stage 5 reuses
  PV-02's flag).
