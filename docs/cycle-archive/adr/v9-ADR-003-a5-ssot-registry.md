# v9-ADR-003 — Architecture Rule A-5 (Single-Source-of-Truth Registry Pattern)

* **Status**: Accepted
* **Date**: 2026-04-24
* **Cycle**: v9.0.0 PV-03 (`v8.4.3` PATCH)
* **Cycle role**: Codifies the "every domain registry surface has exactly
  ONE owner module" pattern that has been applied informally across 5
  registry generations (v8.2.1 plugin catalog + v8.3.1 runtime plugin
  registry + v8.3.2 shell-proxy whitelist + v8.3.3 memory-router cache +
  v8.3.4 command-mapping recipe). Closes **C-02** of
  `.local/research/v9.0.0_gap_analysis.md` §5.3 (Theme T2 deliverable).
* **Predecessor ADRs**:
  * `v9-ADR-002` (cache-layout governance v2 — sister codification ADR
    of the v9.0.0 cycle; A-2 and A-5 both promote informal practice
    into binding architecture rules).
  * `.local/research/v8.4.0_rtk_nines_analysis.md` §4.1 (the RTK
    `src/discover/registry.rs` analysis that originally established
    "one table, all consumers delegate" as the design discipline for
    the shell-proxy whitelist).
* **Branch**: `feat/v8.4.3-a5-ssot-registry`

## Context

DevolaFlow currently ships **5 domain-SSOT registries** that bridge agent
orchestration to runtime data:

| # | Registry surface | Owner module / file | Format | Introduced |
|---|---|---|---|---|
| 1 | Plugin catalog | `workflow-system/agent/plugins.yaml` (loaded by `devolaflow.plugins.loader`) | YAML | v8.2.1 |
| 2 | Runtime plugin registry | `workflow-system/agent/knowledge/runtime-plugins.yaml` (loaded by `devolaflow.plugins.installer.load_registry`) | YAML | v8.3.1 |
| 3 | Shell-proxy whitelist | `src/devolaflow/shell_proxy/registry.py::WHITELIST` | Python `dict[str, Tier]` | v8.3.2 |
| 4 | Memory-router case type | `src/devolaflow/memory_router/cache.py::MemoryCase` | Frozen dataclass | v8.3.3 |
| 5 | Command-mapping recipe type | `src/devolaflow/shell_proxy/commands.py::CommandMapping` | Frozen dataclass | v8.3.4 |

Each of these registrations was authored under the same implicit discipline
(documented per-PV in module docstrings + the v8.4.0 RTK NineS analysis):

> *"One module owns the registration data; cross-cutting consumers
> import from the owner. Mirrors RTK's `src/discover/registry.rs`
> single-source-of-truth pattern."*
> — `src/devolaflow/shell_proxy/registry.py:1-31` verbatim

But the discipline itself is not codified at the architecture-rule layer.
The v9.0.0 SI-1 reference review (`v9.0.0_reference_review.md` §F-13)
flagged the shell-proxy + memory-router + command-mapping triplet as a
documentation gap — the 3 registries are not explicitly cross-linked
under a shared SSOT pattern, leaving operators to infer the discipline
from prose docstrings rather than a binding rule.

The C-02 gap surfaced two concrete failure modes during the v9.0.0
SI-1 review:

1. A future PV could split a registry's data across two modules
   (e.g. half the `WHITELIST` in `shell_proxy/registry.py` + half in
   `lifecycle/pre_shell_call.py` for "performance reasons") without
   any guard catching it. Such a split invalidates the cache reasoning
   the proxy + the hook depend on (the hook would diverge from the proxy
   on the second half) and would only surface as a runtime mismatch
   once an operator triggered a Tier-2 command the hook never saw.
2. `scripts/detect_dead_apis.py::DEFAULT_ALLOWLIST` is the registry of
   public APIs that intentionally lack an in-repo production caller.
   A future PR could allowlist a domain-SSOT symbol (e.g. drop
   `WHITELIST` into `DEFAULT_ALLOWLIST` "to silence detect_dead_apis"
   when refactoring the proxy). The allowlist would silently mask the
   fact that the registry's only caller had been removed — turning a
   live registry into a dead one without any dispatch-time signal.
   This is exactly the v6.0.3 dead-wire bug class that
   `detect_dead_apis.py` exists to catch.

## Decision

### D1 — Pattern Definition

Architecture Rule **A-5 — Single-Source-of-Truth Registry Pattern** is
codified in `.rules/architecture.mdc` and (via `RuleCompiler.compile_all()`)
mirrored into both `.cursor/rules/repo-governance.mdc` and `AGENTS.md`.
The rule body declares that every domain registry surface (whitelist,
recipe, value-type cache, plugin manifest) MUST have **exactly one
owner module** — the canonical source-of-truth for the registration
data. Cross-cutting consumers import from the owner module; they never
re-define or shadow the registration data locally.

The rule is decomposed into three sub-clauses:

* **A-5.1 Single-Owner Invariant** — adding a NEW whitelist / recipe /
  registry surface requires picking ONE owner module and routing every
  consumer through it. Splitting registration data across two modules
  invalidates cache reasoning and is a release blocker.
* **A-5.2 DEFAULT_ALLOWLIST Hygiene** — domain-SSOT registry symbols
  MUST NOT appear in `scripts/detect_dead_apis.py::DEFAULT_ALLOWLIST`
  because, by definition, such symbols ARE consumed in-repo by their
  owner module's siblings.
* **A-5.3 Staged Rollout** — at v8.4.3 the rule ships strict (R-3 not
  triggered); the contingency informational-then-strict path documented
  below fires only if a future PV introduces a collision.

### D2 — Parity-Test Enforcement

A-5 is enforced at TWO checkpoints, both in CI:

1. **Single-owner AST guard** —
   `tests/test_no_ghost_features.py::test_registry_single_owner` performs
   an AST walk over `src/devolaflow/**/*.py` for each Python-backed
   registry symbol (`WHITELIST`, `MemoryCase`, `CommandMapping`) and
   asserts:
   * Exactly ONE `*.py` file contains a module-level definition
     (`class`, `def`, `Assign`, or `AnnAssign`) of that symbol.
   * The single definer matches the canonical owner path declared in
     `_SSOT_PYTHON_REGISTRIES`.
   For YAML-backed registries (`plugins.yaml`, `runtime-plugins.yaml`)
   the test asserts the file lives at exactly its canonical path —
   file-path uniqueness suffices because the loaders import via
   verbatim paths, not glob patterns.

2. **DEFAULT_ALLOWLIST overlap guard** —
   `scripts/detect_dead_apis.py` ships a new module-level constant
   `SSOT_REGISTRY_QUALIFIED_NAMES: frozenset[str]` listing the
   `module:Name` qualified names of the 3 Python-backed registries, plus
   a helper `_check_allowlist_domain_overlap(allowlist, registry_names)`
   that returns the intersection. The script asserts at IMPORT TIME that
   `DEFAULT_ALLOWLIST` has empty overlap; an A-5.2 violation raises
   `AssertionError` immediately, refusing to load the module under both
   `python scripts/detect_dead_apis.py --strict` (CLI) and
   `tests/test_dead_apis.py` (pytest collection). Per Soul Rule S-5 (No
   Silent Failures), the guard never swallows the violation; the error
   message names every offending qualified name + cites A-5.2.

   The helper is also exercised explicitly by
   `tests/test_dead_apis.py::test_default_allowlist_no_ssot_overlap`
   and `::test_check_allowlist_domain_overlap_helper_detects_collisions`
   so the failure surfaces with a clear A-5 message even when the
   import-time guard somehow passes.

### D3 — Staged Rollout

PV-03 audited the live `DEFAULT_ALLOWLIST` (188 entries at the v8.4.2
HEAD): NONE of the 3 Python-backed SSOT registry qualified names
appears. R-3 (the rollout-blocking contingency for "parity test rejects
EXISTING DEFAULT_ALLOWLIST entries") is therefore NOT triggered at the
v8.4.3 cut, and A-5 ships **strict** from v8.4.3:

* Both parity tests run as ordinary `assert` (no `xfail`).
* The script-import-time guard raises `AssertionError`
  unconditionally on any future violation.

The contingency rollout that R-3 would have required is preserved here
in case a future PV introduces a collision (e.g. v8.5.0 adds a 4th
shell-proxy registry whose qualified name happens to match a
pre-existing allowlist entry):

| Phase | Behavior | Trigger to advance |
|---|---|---|
| v8.4.3 (now) | **STRICT** — both tests + import-time guard active; R-3 mitigation not needed | n/a — R-3 triggered |
| Contingency at v8.5.0 (PV-05) if a future PV trips R-3 | The newly-conflicting test would be marked `@pytest.mark.xfail(strict=False, reason="A-5.2 — pending allowlist cleanup")` for the duration of the conflict | v8.5.x release that removes the colliding allowlist entry per A-5.2 |
| Contingency restoration | Remove the `xfail` marker; restore strict behavior | All conflicts cleared |

The contingency path is documented for completeness — at v8.4.3 cut
the strict behavior is the live default.

### D4 — `references/shell-proxy.md` §11 Cross-Link

`workflow-system/agent/references/shell-proxy.md` gains a NEW §11
"Registry SSOT (A-5)" section that:

* Cross-links the 3 shell-proxy + memory-router registries to A-5 with
  per-registry consumer lists.
* Names the remaining 2 SSOT registries (the YAML pair) so operators
  reading this reference get the full picture without chasing the
  rule file.
* Documents the 2 CI guards by full path so a triage operator can
  re-run them locally.

This closes the F-13 documentation gap (per the v9.0.0 reference
review, F-13 flagged the absence of a "5th canonical lifecycle hook"
discoverability surface; the §11 cross-link addresses the parallel
"3 SSOT registries" discoverability surface that F-13 also called out
implicitly via the `single-source-of-truth pattern` term used in the
RTK NineS analysis evidence).

## Rationale

* **Why register exactly 3 Python symbols, not all 5?** The 2 YAML
  registries (`plugins.yaml`, `runtime-plugins.yaml`) live at fixed
  filesystem paths with no Python symbol to guard at the
  `DEFAULT_ALLOWLIST` layer. File-path uniqueness, asserted by
  `test_registry_single_owner`, is sufficient — no operator can
  accidentally allowlist a YAML file as a Python qualified name.
* **Why import-time guard + dedicated test, not just the test?** Two
  independent triggers protect the invariant against test-only
  bypasses (e.g. a PR that disables the test temporarily for an
  unrelated reason). The CLI invocation
  (`python scripts/detect_dead_apis.py --strict`) is a separate
  surface that must not leak silent A-5 violations.
* **Why ship strict at v8.4.3 instead of starting informational?** R-3
  was not triggered (audit confirmed empty overlap), so the strict
  guard is the strongest statement we can make at zero migration cost.
  The staged rollout in D3 documents the informational fallback for
  posterity, but PV-03 had no need to invoke it.
* **Why `_check_allowlist_domain_overlap` private (`_` prefix)?** The
  helper is internal to `scripts/detect_dead_apis.py` + its test
  module; external consumers should call the script via `--strict`
  exit code, not import its private validators. The leading
  underscore makes the script the public surface and the helper an
  implementation detail (consistent with the existing module's
  `_collect_real_uses` / `_iter_python_files` private helpers).
* **Why nest A-5 sub-clauses (A-5.1 / A-5.2 / A-5.3) instead of
  appending three top-level rules?** Per A-2.3 (Nest-vs-Append
  Decision Rule from v9-ADR-002), the three sub-clauses modify HOW
  the same parent rule is interpreted (the single-owner, allowlist
  hygiene, and rollout dimensions are facets of one pattern, not
  orthogonal concerns). NEST preserves the rule-document's flat
  reference structure (`A-1` … `A-5` instead of `A-1` … `A-7`).

## Consequences

### Positive

* **Future SSOT additions get a binding rule, not a docstring
  convention** — when v8.5.0+ introduces a 6th registry (e.g. a
  `learnings_router/cache.py::LearningCase`), the author's PR is
  blocked at CI if they accidentally split the data across modules
  or if they reach for `DEFAULT_ALLOWLIST` to suppress a
  detect-dead-apis warning.
* **The dead-wire bug class shrinks** — A-5.2 closes the specific
  failure mode where allowlisting a registry symbol could silently
  hide the loss of its only caller. The detect-dead-apis script's
  v6.0.3-bug-catching coverage now extends to "live registry that
  lost its consumer" + "registry split across two owners".
* **Operators get a single binding reference** for the "where does
  registration live?" question. `references/shell-proxy.md §11`
  enumerates the 3 stack-local registries; the AGENTS.md A-5 table
  enumerates all 5.
* **No runtime cost** — both guards run only at test / script-import
  time. Production dispatch paths are byte-identical to v8.4.2.

### Negative

* **+50 LOC in `scripts/detect_dead_apis.py`** (was ~+15 LOC
  forecast in `v9.0.0_gap_analysis.md` §5.3 — the actual surface
  needs the import-time guard + the helper + comprehensive
  docstrings explaining the A-5 link). Net script size 687 → 744
  lines, well under any tier ceiling for the script directory.
* **+~120 LOC in `tests/test_no_ghost_features.py`** for
  `test_registry_single_owner` + the `_module_level_definers` /
  `_node_defines_symbol` helpers + the `_SSOT_PYTHON_REGISTRIES` /
  `_SSOT_YAML_REGISTRIES` declarations. The forecast was +50 LOC;
  the actual surface needs the AST helper + the per-symbol /
  per-yaml-file iteration + the docstrings explaining each branch
  of the AST node match. File line count 711 → 827 lines.
* **`AGENTS.md` grows from 354 → 410 lines** to absorb A-5 + the 3
  sub-clauses + the 5-row registry table. Compiler reports
  5358 / 6000 token budget after the bump (89%); next major rule
  addition will likely require either a ceiling bump or a layered
  compression pass. Tracked as deferred for the v9.0.0
  retrospective.
* **`references/shell-proxy.md` grows from 683 → 720 lines**
  (~+37 LOC for §11). Still 72% of the SF-1 Large tier 1000-line
  ceiling; no headroom risk.

### Neutral

* No SKILL.md change required — A-5 is a `.rules/` rule, not a
  SKILL.md surface. The PV-01 (v8.4.1) headroom reclamation already
  freed enough buffer for any future SKILL.md mention of A-5 if
  v9.0.0 PV-04+ chooses to add one.
* No EvoBench scenario change — A-5 affects rule + test surfaces
  only, not dispatch composition. `tests/test_benchmarks.py` 36/36
  PASS post-PV-03 against the `v9.0.0_baseline.json` floor (per
  W-4 / SI-4).
* No I-8 invariant change — `schemas/lean-dispatch.yaml#layout_invariant`
  is untouched (length 16 / version 5). PV-03 is a pure rule + CI
  patch with no schema or runtime touch.

## Alternatives Considered

### A1 — Defer A-5 to v9.0.0 release roll-up

Postpone codification to the v9.0.0 minor cut and ship PV-03 with
only `references/shell-proxy.md` §11 cross-link.

* **Rejected because**: the v9.0.0 SI-1 cycle plan
  (`.local/research/v9.0.0_implementation_plan.md` §6.3) explicitly
  schedules A-5 as PV-03's primary deliverable; deferring would
  invalidate the cycle's stage-by-stage close-rate accounting and
  push C-02 to the v9.0.0 retrospective without a clear next
  delivery slot.
* **Cost of deferral**: every PV between v8.4.3 and v9.0.0 release
  would ship without A-5 enforcement, leaving the failure modes in
  Context §1-§2 open during the highest-velocity stretch of the
  v9.0.0 cycle.

### A2 — Make A-5 a Soul Rule (S-10) instead of an Architecture Rule

Promote the SSOT registry pattern to a Soul Rule so it gets the
P0 immutability stamp.

* **Rejected because**: Soul Rules govern invariants that NEVER
  change regardless of context (S-1..S-9 are per-message / per-file
  / per-branch / per-resource invariants). A-5 governs the
  *organisation* of code modules, which is an architecture concern
  (cf. A-1 4-layer hierarchy, A-3 token budgets, A-4 spec location).
  Misclassifying A-5 as a Soul Rule would dilute the P0 layer's
  semantic.
* **A1 would also have made `.rules/soul.mdc` cross 100 lines**, an
  unforced compression pressure.

### A3 — Implement parity test only; defer A-5 rule codification

Land just `test_registry_single_owner` + the `_check_allowlist_domain_overlap`
helper without writing the rule into `.rules/architecture.mdc`.

* **Rejected because**: P5 (Artifacts as Contracts) requires a
  rule-level artifact for any guard tied to operator-facing failure
  messages. A test that fails with `assert len(definers) == 1` and
  no `.rules/architecture.mdc` reference would leave operators
  guessing what "1" is correct for; A-5 closes that loop with the
  "exactly one owner module" wording the test cites verbatim.

### A4 — Use a Python decorator (`@ssot_registry`) to mark owner modules

Annotate each registry with a `@ssot_registry` decorator and have
the test enumerate decorated symbols rather than parse a hard-coded
table.

* **Rejected because**: this would force a dependency on
  `devolaflow.<utility>` from each owner module, creating a circular
  import risk (`shell_proxy/registry.py` would import a utility that
  itself depends on `shell_proxy/__init__.py`). The hard-coded
  `_SSOT_PYTHON_REGISTRIES` table is auditable in a single grep,
  has no import topology, and is updated O(1) when a new SSOT
  registry lands.
* **Operational cost**: reviewing a PR for "did you remember to add
  the decorator?" is harder than reviewing "did you add a row to
  the SSOT table?". The flat table is the lower-friction surface.

## Migration

PV-03 is a strictly additive patch — no existing code, schema, or
configuration changes shape:

* `.rules/architecture.mdc` — append A-5 + sub-clauses (~+56 lines)
* `.cursor/rules/repo-governance.mdc` — auto-regenerated via
  `RuleCompiler.compile_all()` (mirrors the architecture layer
  byte-for-byte)
* `AGENTS.md` — auto-regenerated (same compiler call)
* `scripts/detect_dead_apis.py` — append `SSOT_REGISTRY_QUALIFIED_NAMES`
  + `_check_allowlist_domain_overlap` + import-time guard
  (~+57 LOC after docstrings)
* `tests/test_no_ghost_features.py` — append `_SSOT_PYTHON_REGISTRIES`
  + `_SSOT_YAML_REGISTRIES` + `_module_level_definers`
  + `_node_defines_symbol` + `test_registry_single_owner`
  (~+116 LOC after docstrings)
* `tests/test_dead_apis.py` — append `test_default_allowlist_no_ssot_overlap`
  + `test_check_allowlist_domain_overlap_helper_detects_collisions`
  (~+48 LOC after docstrings)
* `workflow-system/agent/references/shell-proxy.md` — append §11
  "Registry SSOT (A-5)" section (~+37 LOC)
* CHANGELOG + 7-canonical version-sync locations — `8.4.2` → `8.4.3`

No production code edited; no schema touched; no SKILL.md touched.

## Test Plan

* **Unit (PV-03 NEW)**:
  * `test_registry_single_owner` (test_no_ghost_features.py) — green
    against current 5 SSOT registries; turn on by removing any
    speculative ghost test pin.
  * `test_default_allowlist_no_ssot_overlap` (test_dead_apis.py) —
    green against current `DEFAULT_ALLOWLIST`.
  * `test_check_allowlist_domain_overlap_helper_detects_collisions`
    (test_dead_apis.py) — green via synthetic fixtures.
* **Integration / system**:
  * `python scripts/detect_dead_apis.py --strict` exits 0 (the
    import-time guard does not raise; the existing 0-dead-API
    invariant continues to hold).
  * `tests/test_local_compiler.py` exercises the full `.rules/`
    layered compile pipeline; A-5 propagates to both `cursor` and
    `agents_md` outputs (verified post-edit; the `cursor` output
    is at 6391/8000 tokens and the `agents_md` output is at
    5358/6000 tokens, both well under budget).
* **Regression**:
  * `tests/test_benchmarks.py` — 36/36 PASS post-PV-03 (no scenario
    drift > 5% per W-4 / SI-4 against `v9.0.0_baseline.json`).
  * Full `pytest tests/ -q` — 3282 passed (was 3279 baseline + 3
    new tests), 17 skipped, 2 xfailed.
* **Pre-commit (W-9 / SI-10)**: all 6 steps PASS as documented in
  `tests/test_smoke.py` post-bump.

## A-5 Compliance for the Rule Itself

A-5 governs registries; it does not register data of its own. The
rule's enforcement surface (the `_SSOT_PYTHON_REGISTRIES` table in
`tests/test_no_ghost_features.py` + the `SSOT_REGISTRY_QUALIFIED_NAMES`
constant in `scripts/detect_dead_apis.py`) lives in **two places**
deliberately, by A-5 design — they enforce the rule from two
orthogonal angles (AST source-of-truth uniqueness vs allowlist
hygiene). They are not themselves SSOT registries; they are
guard-tables that consume the registry list. Future additions to
the SSOT registry list MUST update both tables in the same PR;
this is a documented coupling, not an A-5 violation.

## Cross-References

* **v9.0.0 SI-1 planning gate**: `.local/research/v9.0.0_gap_analysis.md`
  §5.3 (PV-03 owned-files manifest; closes C-02)
* **v9.0.0 SI-1 reference review**: `.local/research/v9.0.0_reference_review.md`
  §F-13 (the `single-source-of-truth pattern` evidence trail in
  the RTK NineS analysis)
* **v9.0.0 SI-1 implementation plan**: `.local/research/v9.0.0_implementation_plan.md`
  §6.3 (5 stages, 5 waves, 7 tasks)
* **Sister codification ADR**: `.local/research/adr/v9-ADR-002-cache-layout-governance-v2.md`
  (A-2 generalisation; same pattern: codify-informal-practice as
  binding architecture rule)
* **Predecessor analysis**: `.local/research/v8.4.0_rtk_nines_analysis.md`
  §4.1 (RTK `src/discover/registry.rs` single-source-of-truth
  pattern that originally inspired the shell-proxy whitelist
  design)
* **Predecessor PVs**: v8.2.1 (plugins.yaml), v8.3.1 (runtime
  plugin registry), v8.3.2 (shell-proxy whitelist), v8.3.3 (memory
  router cache), v8.3.4 (command-mapping recipe) — the 5 PVs that
  shipped the 5 SSOT registries pre-codification
* **DevolaFlow canonical URL** (per S-7): https://github.com/YoRHa-Agents/DevolaFlow
* **NineS canonical URL** (per S-7): https://github.com/YoRHa-Agents/NineS
