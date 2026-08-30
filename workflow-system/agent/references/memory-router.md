---
id: "agent/references/memory-router"
version: "1.0.0"
purpose: >
  Defines the v8.3.3 memory-router planning fast-path
  (`src/devolaflow/memory_router/`) and its cache-case schema. The router is
  runtime-opt-in via `DEVOLAFLOW_MEMORY_ROUTER=1` and remains R5 strict
  default-off (zero IO and zero behavior change when disabled).
triggers:
  - "authoring a memory-router case recipe"
  - "investigating a `lookup_case` cache miss"
  - "auditing memory-router invalidation"
  - "diagnosing R5 strict cache behavior"
tier: 2
token_estimate: 2800
dependencies:
  - "agent/SKILL.md"
  - "agent/references/agent-hierarchy.md"
  - "agent/references/execution-protocol.md"
  - "agent/references/decomposition-gate.md"
  - "agent/references/message-schemas.md"
last_updated: "2026-08-31"
---

# Memory Router Reference

The v8.3.3 cycle shipped the **memory-router fast-path** for L0/L1 planning.
It consults prior workflow cases before re-deriving a plan from SKILL.md;
a cache hit short-circuits planning context while a miss falls through to
the existing planner.

## 1. When to Load This Reference

Load when the task involves:

| Trigger | What you'll be doing |
|---|---|
| Authoring a memory-router case recipe | Need `schemas/memory-case.yaml` and the multi-level routing keys |
| Investigating a cache miss | Need the safe miss and invalidation behavior |
| Auditing strict behavior | Need the zero-IO disabled-path contract |

If a task does not touch `src/devolaflow/memory_router/` or
`.local/memory/cases/`, this reference is optional.

## 2. Activation Surface

| Flag | Source PV | Default | Activates |
|---|---|---|---|
| `DEVOLAFLOW_MEMORY_ROUTER` | v8.3.3 PV-03 | unset | When `"1"`: `lookup_case()` consults `.local/memory/cases/index.yaml` before L0/L1 planning |

Only the literal string `"1"` enables the router. `"01"`, `"true"`, `"yes"`,
and other values leave it disabled.

## 3. Fast-Path API

```python
from devolaflow.memory_router import lookup_case

case = lookup_case(
    workflow_type="full-pipeline",
    task_type="implement",
    repo_signal=None,
)
if case is not None:
    summary = case.summary
    recipe_path = case.recipe_path
    version_stamp = case.version_stamp
else:
    dispatch_template = derive_from_skill_md(...)
```

`lookup_case()` is the safe variant: it never raises and degrades to `None`
on schema break, IO error, or a missing file. Verification and operator
inspection paths use `lookup_case_strict()`, which raises
`MemoryRouterError`. A corrupt index can therefore never block production
planning.

## 4. `MemoryCase` Value Type

```python
@dataclass(frozen=True)
class MemoryCase:
    case_id: str
    workflow_type: str
    task_type: str
    summary: str
    recipe_path: str
    version_stamp: str
    ttl_days: int = DEFAULT_TTL_DAYS
    last_accessed: str = ""
    last_updated: str = ""
    repo_signal: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
```

`summary` is a verbatim one-sentence summary of at most 160 characters.
`recipe_path` MUST start with `.local/memory/cases/`, and `version_stamp` MUST
equal `devolaflow.__version__`.

## 5. Invalidation Predicates

Two predicates run for every match before returning a hit:

1. `is_version_stale(case, current_version)` uses exact string equality with
   `devolaflow.__version__`. Pre-release tags also invalidate a case.
2. `is_ttl_expired(case, today=...)` uses `last_accessed` first, then
   `last_updated`; both empty means fresh-but-undated and returns `False`.

Either predicate turns the result into a cache miss, so the caller continues
with the existing planner unchanged.

## 6. Lazy Loading and Index Format

`MemoryRouter()` construction performs no IO. The index is loaded on the first
lookup into an immutable snapshot, then reused. Tests may inject `cases=[...]`
to skip IO entirely.

```yaml
# .local/memory/cases/index.yaml
schema_version: 1
last_updated: "2026-04-23"
cases:
  - case_id: "workflow-case"
    workflow_type: "change-driven(feature-enhancement)"
    task_type: "implement"
    summary: "A verbatim summary of the reusable workflow case."
    recipe_path: ".local/memory/cases/workflow-case.md"
    version_stamp: "8.3.3"
    ttl_days: 30
    last_updated: "2026-04-23"
    tags: ["workflow", "case"]
```

The recipe markdown body is free-form. Only the `index.yaml` row is
validated. Required fields are `case_id`, `workflow_type`, `task_type`,
`summary`, `recipe_path`, and `version_stamp`.

## 7. Operator-Local Seed Kit

The `.local/memory/cases/` tree is gitignored under `.local/*`. Operators
populate the library lazily via the `consolidate_session()` learnings
substrate. A case recipe consists of an index row and a markdown playbook
covering trigger, dispatch shape, predecessor references, owned files, gate
hints, and notes.

## 8. R5 Strict Invariants

| Invariant | Contract |
|---|---|
| Disabled flag | `lookup_case()` returns `None` without reading files |
| Cache miss | Returns `None` and preserves the existing planner path |
| Corrupt input | Safe lookup logs/degrades; strict lookup raises |
| Version drift | Stale cases are ignored |
| TTL expiry | Expired cases are ignored |
| Construction | `MemoryRouter()` performs no IO |

The unit suite `tests/test_memory_router.py` pins the zero-IO disabled path,
invalidation, lazy loading, and safe/strict lookup behavior. Historical
benchmark and cycle artifacts retain their original provenance separately.

## 9. Cross-References

* `src/devolaflow/memory_router/` — runtime implementation
* `schemas/memory-case.yaml` — case-index schema
* `tests/test_memory_router.py` — behavioral and R5 strict tests
* `references/env-flags.md` — `DEVOLAFLOW_MEMORY_ROUTER` inventory row
* `references/execution-protocol.md` — planning fast-path execution contract
